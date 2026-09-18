"""ESI's error budget, and the concurrency it governs.

ESI allows a fixed number of errors per rolling window and reports the state on
every response, success or failure. Exhausting it locks the client out, so
concurrency here is derived from the live budget rather than fixed: N requests
in flight are N simultaneous potential errors, and a burst of failures — an ESI
degradation, not one bad request — can spend a lot of budget quickly.

The rule (ADR-0011): in-flight requests are capped at
``min(CEILING, remaining - FLOOR)``. The ceiling is hard and the budget may only
lower it. That gives a throttle-down band rather than a cliff: capacity holds at
CEILING while remaining is above FLOOR + CEILING, then degrades over the next
CEILING errors before reaching zero at FLOOR.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

from tech2finder.sync.transport import Response

#: Hard ceiling on requests in flight. The budget may lower it, never raise it.
CEILING = 15

#: Halt here rather than at zero. Half of ESI's 100-error window is held in
#: reserve: nothing is bought by spending it, and the headroom is what lets a
#: scan notice a burst of failures and stop cleanly instead of discovering the
#: problem at zero.
FLOOR = 50

#: What ESI grants per window, assumed until a response says otherwise.
WINDOW = 100

REMAIN_HEADER = "X-ESI-Error-Limit-Remain"
RESET_HEADER = "X-ESI-Error-Limit-Reset"


class ErrorBudget:
    """Admits work only while the error budget allows it.

    ``now`` and ``sleep`` are injected so the scheduling can be tested without
    a test suite that actually waits.
    """

    def __init__(
        self,
        now: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
        remaining: int = WINDOW,
    ) -> None:
        self._now = now
        self._sleep = sleep
        self._remaining = remaining
        self._resets_at = now()
        self._in_flight = 0
        self._free = asyncio.Condition()

    @property
    def capacity(self) -> int:
        """How many requests may be in flight right now."""
        return max(0, min(CEILING, self._remaining - FLOOR))

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def remaining(self) -> int:
        return self._remaining

    def observe(self, response: Response) -> None:
        """Learn the budget from a response. ESI reports it on success too, so a
        scan finds out it is in trouble without having to fail first."""
        remain = response.header(REMAIN_HEADER)
        reset = response.header(RESET_HEADER)
        if remain is None:
            return

        try:
            self._remaining = int(remain)
        except ValueError:
            return

        if reset is not None:
            with suppress(ValueError):
                self._resets_at = self._now() + float(reset)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one of the permitted in-flight slots for the duration."""
        await self._acquire()
        try:
            yield
        finally:
            await self._release()

    async def _acquire(self) -> None:
        while True:
            async with self._free:
                if self.capacity == 0:
                    wait_for = max(0.0, self._resets_at - self._now())
                else:
                    if self._in_flight < self.capacity:
                        self._in_flight += 1
                        return
                    await self._free.wait()
                    continue

            # Sleeping outside the lock, so releases can still be recorded.
            await self._sleep(wait_for)
            self._refill()

    def _refill(self) -> None:
        """The window has passed, so the budget is whole again."""
        if self._now() >= self._resets_at:
            self._remaining = WINDOW

    async def _release(self) -> None:
        async with self._free:
            self._in_flight -= 1
            self._free.notify()
