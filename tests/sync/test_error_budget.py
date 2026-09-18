"""The error budget governs concurrency. Getting this wrong means an API
lockout, so every rule in ADR-0011 is pinned here.

Time is injected: these tests assert on scheduling, and must not sleep.
"""

import asyncio

import pytest

from tech2finder.sync.budget import CEILING, FLOOR, ErrorBudget
from tech2finder.sync.transport import Response


class FakeClock:
    """A monotonic clock that only advances when someone sleeps on it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)  # let other tasks run


def budget(remaining: int = 100) -> tuple[ErrorBudget, FakeClock]:
    clock = FakeClock()
    return ErrorBudget(now=lambda: clock.now, sleep=clock.sleep, remaining=remaining), clock


def headers(remaining: int, reset: int = 60) -> dict[str, str]:
    return {
        "X-ESI-Error-Limit-Remain": str(remaining),
        "X-ESI-Error-Limit-Reset": str(reset),
    }


def test_starts_at_the_hard_ceiling() -> None:
    b, _ = budget()

    assert b.capacity == CEILING


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [
        (100, 15),  # full budget: the ceiling, not remaining - floor
        (70, 15),  # still the ceiling
        (65, 15),  # the last point before the band
        (64, 14),  # throttling begins
        (55, 5),
        (51, 1),
        (50, 0),  # halt
        (10, 0),
        (0, 0),
    ],
)
def test_capacity_is_the_ceiling_lowered_by_the_budget_never_raised(
    remaining: int, expected: int
) -> None:
    # A throttle-down band rather than a cliff: the cap holds at the ceiling
    # down to FLOOR + CEILING remaining, then degrades to nothing at FLOOR.
    b, _ = budget(remaining)

    assert b.capacity == expected


async def test_never_admits_more_than_the_ceiling_at_once() -> None:
    b, _ = budget()
    peak = 0
    in_flight = 0

    async def one() -> None:
        nonlocal peak, in_flight
        async with b.slot():
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0)
            in_flight -= 1

    await asyncio.gather(*(one() for _ in range(60)))

    assert peak <= CEILING
    assert peak == CEILING, "should actually use the ceiling, not serialise"


async def test_a_response_lowers_capacity_as_the_budget_drains() -> None:
    b, _ = budget()

    b.observe(Response(status=420, headers=headers(remaining=55), body=b""))

    assert b.capacity == 5


async def test_waits_for_the_reset_window_when_the_budget_runs_low() -> None:
    b, clock = budget()
    b.observe(Response(status=420, headers=headers(remaining=FLOOR, reset=30), body=b""))

    assert b.capacity == 0
    async with b.slot():
        pass

    # It slept for the reset window rather than hammering on.
    assert clock.slept and sum(clock.slept) >= 30


async def test_the_budget_refills_after_the_reset_window() -> None:
    b, clock = budget()
    b.observe(Response(status=420, headers=headers(remaining=FLOOR, reset=5), body=b""))

    async with b.slot():
        pass

    assert b.capacity == CEILING
    assert clock.now >= 5


async def test_a_successful_response_still_updates_the_budget() -> None:
    # ESI reports the headers on success too, so a scan learns it is in trouble
    # without having to fail first.
    b, _ = budget()

    b.observe(Response(status=200, headers=headers(remaining=60), body=b""))

    assert b.capacity == 10


async def test_ignores_a_response_carrying_no_budget_headers() -> None:
    b, _ = budget()

    b.observe(Response(status=200, headers={}, body=b""))

    assert b.capacity == CEILING


async def test_never_raises_capacity_above_the_ceiling_however_large_the_budget() -> None:
    b, _ = budget()

    b.observe(Response(status=200, headers=headers(remaining=10_000), body=b""))

    assert b.capacity == CEILING


async def test_a_slot_is_released_even_when_the_work_raises() -> None:
    b, _ = budget()

    with pytest.raises(RuntimeError):
        async with b.slot():
            raise RuntimeError("boom")

    assert b.in_flight == 0
