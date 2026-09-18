"""The client: identification, retries, and parsing. Budget arithmetic lives in
test_error_budget; this asserts that the client actually consults it."""

import json
from datetime import UTC, datetime

import pytest

from tech2finder.sync.budget import ErrorBudget
from tech2finder.sync.esi import THE_FORGE, EsiClient, UnidentifiedClient
from tech2finder.sync.transport import Response

from .fake_transport import FakeTransport

UA = "tech2finder/0.1 (pilot@tech2finder.test)"


def ok(payload: object, **headers: str) -> Response:
    return Response(status=200, headers=headers, body=json.dumps(payload).encode())


def client(transport: FakeTransport, **kwargs: object) -> EsiClient:
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    budget = ErrorBudget(now=lambda: 0.0, sleep=sleep)
    c = EsiClient(transport=transport, budget=budget, user_agent=UA, sleep=sleep, **kwargs)  # type: ignore[arg-type]
    c.slept = slept  # type: ignore[attr-defined]
    return c


async def test_identifies_itself_on_every_request() -> None:
    # CCP asks third-party clients to identify themselves; unidentified traffic
    # is what gets throttled, which would be an ironic way to lose the budget.
    transport = FakeTransport(responses=[ok([])])

    await client(transport).market_history(THE_FORGE, 31796)

    assert transport.requests[0].headers["User-Agent"] == UA


@pytest.mark.parametrize(
    "user_agent",
    ["", "   ", "tech2finder", "tech2finder (your-email-here@example.com)"],
)
async def test_refuses_to_start_without_a_real_contact_address(user_agent: str) -> None:
    # Failing to start is better than running unidentified: the consequence of
    # the latter is losing API access, which is not locally visible.
    with pytest.raises(UnidentifiedClient):
        EsiClient(transport=FakeTransport(), budget=None, user_agent=user_agent)  # type: ignore[arg-type]


async def test_parses_market_history() -> None:
    rows = [
        {
            "date": "2026-09-17",
            "average": 16870000.0,
            "highest": 16960000.0,
            "lowest": 16600000.0,
            "order_count": 410,
            "volume": 1568,
        }
    ]
    transport = FakeTransport(responses=[ok(rows, Expires="Sat, 19 Sep 2026 11:05:00 GMT")])

    result = await client(transport).market_history(THE_FORGE, 31796)

    assert len(result.rows) == 1
    assert result.rows[0].date == "2026-09-17"
    assert result.rows[0].average == pytest.approx(16870000.0)
    assert result.rows[0].volume == 1568
    assert result.expires == datetime(2026, 9, 19, 11, 5, tzinfo=UTC)


async def test_market_history_asks_for_one_type_at_a_time() -> None:
    transport = FakeTransport(responses=[ok([])])

    await client(transport).market_history(THE_FORGE, 31796)

    assert "markets/10000002/history" in transport.requests[0].url
    assert "type_id=31796" in transport.requests[0].url


async def test_parses_adjusted_prices_for_every_type_in_one_call() -> None:
    payload = [
        {"type_id": 34, "adjusted_price": 5.5, "average_price": 5.9},
        {"type_id": 35, "adjusted_price": 11.0},
    ]
    transport = FakeTransport(responses=[ok(payload)])

    result = await client(transport).market_prices()

    assert len(transport.requests) == 1, "one call covers every type"
    assert result.prices[34].adjusted_price == pytest.approx(5.5)
    # Job fees are assessed on adjusted_price; a missing one is not a zero.
    assert result.prices[35].average_price is None


async def test_parses_system_cost_indices() -> None:
    payload = [
        {
            "solar_system_id": 30000142,
            "cost_indices": [
                {"activity": "manufacturing", "cost_index": 0.0421},
                {"activity": "invention", "cost_index": 0.0035},
            ],
        }
    ]
    transport = FakeTransport(responses=[ok(payload)])

    result = await client(transport).industry_systems()

    assert result.indices[(30000142, "manufacturing")] == pytest.approx(0.0421)
    assert result.indices[(30000142, "invention")] == pytest.approx(0.0035)


async def test_retries_a_server_error_and_backs_off() -> None:
    transport = FakeTransport(
        responses=[
            Response(status=503, headers={}, body=b"down"),
            Response(status=503, headers={}, body=b"still down"),
            ok([]),
        ]
    )
    c = client(transport)

    await c.market_history(THE_FORGE, 31796)

    assert len(transport.requests) == 3
    assert c.slept == [1.0, 2.0], "backoff should grow, not hammer"  # type: ignore[attr-defined]


async def test_retries_an_error_limited_response() -> None:
    transport = FakeTransport(
        responses=[Response(status=420, headers={}, body=b"error limited"), ok([])]
    )

    await client(transport).market_history(THE_FORGE, 31796)

    assert len(transport.requests) == 2


async def test_gives_up_after_the_retry_budget_and_says_why() -> None:
    transport = FakeTransport(responses=[Response(status=503, headers={}, body=b"")] * 5)

    with pytest.raises(OSError, match="503"):
        await client(transport, retries=2).market_history(THE_FORGE, 31796)


async def test_does_not_retry_a_client_error() -> None:
    # A 404 will not become a 200 by asking again; retrying only spends budget.
    transport = FakeTransport(responses=[Response(status=404, headers={}, body=b"")])

    with pytest.raises(OSError, match="404"):
        await client(transport).market_history(THE_FORGE, 31796)

    assert len(transport.requests) == 1


async def test_teaches_the_budget_from_every_response() -> None:
    transport = FakeTransport(
        responses=[ok([], **{"X-ESI-Error-Limit-Remain": "58", "X-ESI-Error-Limit-Reset": "12"})]
    )
    c = client(transport)

    await c.market_history(THE_FORGE, 31796)

    assert c.budget.remaining == 58
    assert c.budget.capacity == 8
