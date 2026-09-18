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

Coordination uses an Event rather than a Condition so that releasing a slot is
**synchronous** and therefore cannot be cancelled half-done, and so that a
recovering budget wakes every waiter rather than one.
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

#: How long to wait when the budget is spent and ESI has not said when the
#: window resets. ESI's window is 60s; waiting a whole one is the conservative
#: reading, and the alternative — treating "unknown" as "now" — turns the halt
#: into a no-op.
UNKNOWN_RESET_SECONDS = 60.0

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
        #: None until a response tells us. Deliberately *not* ``now()``: a
        #: deadline already in the past makes the halt below sleep zero seconds
        #: and declare the budget whole, which is exactly the lockout this
        #: class exists to prevent.
        self._resets_at: float | None = None
        self._in_flight = 0
        self._changed = asyncio.Event()

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
        if remain is None:
            return

        try:
            updated = int(remain)
        except ValueError:
            return

        rose = updated > self._remaining
        self._remaining = updated

        reset = response.header(RESET_HEADER)
        if reset is not None:
            with suppress(ValueError):
                self._resets_at = self._now() + float(reset)

        if rose:
            # Capacity may have grown; waiters are asleep and will not find out
            # on their own.
            self._changed.set()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one of the permitted in-flight slots for the duration."""
        await self._acquire()
        try:
            yield
        finally:
            self._release()

    async def _acquire(self) -> None:
        while True:
            # No await between the test and the increment, and asyncio is
            # single-threaded, so admission cannot exceed capacity.
            if self.capacity > 0 and self._in_flight < self.capacity:
                self._in_flight += 1
                return

            if self.capacity == 0:
                await self._wait_out_the_window()
                continue

            self._changed.clear()
            await self._changed.wait()

    async def _wait_out_the_window(self) -> None:
        """Sleep until ESI's error window resets, then treat the budget as whole."""
        if self._resets_at is None:
            delay = UNKNOWN_RESET_SECONDS
        else:
            delay = max(0.0, self._resets_at - self._now())

        await self._sleep(delay)

        self._remaining = WINDOW
        # Forgotten rather than kept: a spent deadline reused later would let a
        # subsequent halt pass through instantly.
        self._resets_at = None
        self._changed.set()

    def _release(self) -> None:
        """Synchronous on purpose: a cancellation here would otherwise leak a
        slot and strand every waiter. Wakes all of them, not one — a single
        notification cannot express that capacity grew by more than one."""
        self._in_flight -= 1
        self._changed.set()
