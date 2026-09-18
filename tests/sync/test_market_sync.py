"""Persistence and staleness. Expires is a floor on re-fetching, never a
trigger, and a closed day never changes."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect
from tech2finder.sync.budget import ErrorBudget
from tech2finder.sync.esi import THE_FORGE, EsiClient
from tech2finder.sync.market import sync_history, sync_prices, sync_systems
from tech2finder.sync.transport import Response

from .fake_transport import FakeTransport

UA = "tech2finder/0.1 (pilot@tech2finder.test)"
NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


async def nosleep(_: float) -> None:
    return None


def make_client(transport: FakeTransport) -> EsiClient:
    return EsiClient(
        transport=transport,
        budget=ErrorBudget(now=lambda: 0.0, sleep=nosleep),
        user_agent=UA,
        sleep=nosleep,
    )


def history_response(rows: list[dict[str, object]], expires: datetime | None = None) -> Response:
    headers = {}
    if expires is not None:
        headers["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    return Response(status=200, headers=headers, body=json.dumps(rows).encode())


def day(date: str, average: float = 100.0, volume: int = 10) -> dict[str, object]:
    return {
        "date": date,
        "average": average,
        "highest": average * 1.1,
        "lowest": average * 0.9,
        "order_count": 5,
        "volume": volume,
    }


@pytest.fixture
def store(tmp_path: Path) -> Path:
    path = tmp_path / "store.db"
    bootstrap(path)
    return path


async def test_stores_history_rows(store: Path) -> None:
    transport = FakeTransport(responses=[history_response([day("2026-09-16"), day("2026-09-17")])])

    with connect(store) as conn:
        await sync_history(conn, make_client(transport), THE_FORGE, [31796], now=NOW)

    with connect(store) as conn:
        rows = conn.execute("SELECT date, volume FROM market_history ORDER BY date").fetchall()

    assert [(r["date"], r["volume"]) for r in rows] == [("2026-09-16", 10), ("2026-09-17", 10)]


async def test_does_not_refetch_before_the_expires_floor(store: Path) -> None:
    expires = NOW + timedelta(hours=6)
    transport = FakeTransport(responses=[history_response([day("2026-09-17")], expires)])
    with connect(store) as conn:
        await sync_history(conn, make_client(transport), THE_FORGE, [31796], now=NOW)

    # Nothing queued: asking again would fail the fake.
    quiet = FakeTransport()
    with connect(store) as conn:
        summary = await sync_history(conn, make_client(quiet), THE_FORGE, [31796], now=NOW)

    assert quiet.requests == []
    assert summary.skipped == 1
    assert summary.fetched == 0


async def test_refetches_once_the_floor_has_passed(store: Path) -> None:
    expires = NOW + timedelta(hours=6)
    transport = FakeTransport(responses=[history_response([day("2026-09-17")], expires)])
    with connect(store) as conn:
        await sync_history(conn, make_client(transport), THE_FORGE, [31796], now=NOW)

    later = FakeTransport(responses=[history_response([day("2026-09-18")])])
    with connect(store) as conn:
        summary = await sync_history(
            conn, make_client(later), THE_FORGE, [31796], now=NOW + timedelta(hours=7)
        )

    assert summary.fetched == 1


async def test_holds_data_far_past_its_expiry_rather_than_refreshing_on_a_schedule(
    store: Path,
) -> None:
    # Expires is a floor, not a trigger: nothing re-fetches on its own.
    transport = FakeTransport(
        responses=[history_response([day("2026-09-17")], NOW + timedelta(minutes=5))]
    )
    with connect(store) as conn:
        await sync_history(conn, make_client(transport), THE_FORGE, [31796], now=NOW)

    with connect(store) as conn:
        rows = conn.execute("SELECT count(*) FROM market_history").fetchone()[0]

    assert rows == 1, "a month later the data is still here, untouched, until asked for"


async def test_a_closed_day_is_never_rewritten(store: Path) -> None:
    # A history record for a past date never changes. If ESI ever contradicts
    # itself about one, the stored value wins rather than silently shifting the
    # Valuation Basis under a ranking the user has already acted on.
    old = [day("2026-09-01", average=100.0), day("2026-09-17", average=200.0)]
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(old)])),
            THE_FORGE,
            [31796],
            now=NOW,
        )

    contradicting = [day("2026-09-01", average=999.0), day("2026-09-17", average=200.0)]
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(contradicting)])),
            THE_FORGE,
            [31796],
            now=NOW + timedelta(days=1),
        )

    with connect(store) as conn:
        average = conn.execute(
            "SELECT average FROM market_history WHERE date = '2026-09-01'"
        ).fetchone()[0]

    assert average == pytest.approx(100.0)


async def test_the_trailing_edge_is_still_refreshed(store: Path) -> None:
    # The newest days may still be settling, and ESI lags a day or two behind
    # today, so the tail is replaced while the settled past is not.
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response([day("2026-09-17", 200.0)])])),
            THE_FORGE,
            [31796],
            now=NOW,
        )

    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response([day("2026-09-17", 250.0)])])),
            THE_FORGE,
            [31796],
            now=NOW + timedelta(days=1),
        )

    with connect(store) as conn:
        average = conn.execute(
            "SELECT average FROM market_history WHERE date = '2026-09-17'"
        ).fetchone()[0]

    assert average == pytest.approx(250.0)


async def test_reports_progress_while_prefetching(store: Path) -> None:
    transport = FakeTransport(responses=[history_response([day("2026-09-17")]) for _ in range(3)])
    seen: list[tuple[int, int]] = []

    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(transport),
            THE_FORGE,
            [1, 2, 3],
            now=NOW,
            on_progress=lambda done, total: seen.append((done, total)),
        )

    assert seen == [(1, 3), (2, 3), (3, 3)]


async def test_stores_adjusted_prices(store: Path) -> None:
    payload = [{"type_id": 34, "adjusted_price": 5.5, "average_price": 5.9}]
    transport = FakeTransport(
        responses=[Response(status=200, headers={}, body=json.dumps(payload).encode())]
    )

    with connect(store) as conn:
        await sync_prices(conn, make_client(transport), now=NOW)

    with connect(store) as conn:
        row = conn.execute("SELECT * FROM adjusted_price WHERE type_id = 34").fetchone()

    assert row["adjusted_price"] == pytest.approx(5.5)


async def test_stores_system_cost_indices(store: Path) -> None:
    payload = [
        {
            "solar_system_id": 30000142,
            "cost_indices": [{"activity": "manufacturing", "cost_index": 0.0421}],
        }
    ]
    transport = FakeTransport(
        responses=[Response(status=200, headers={}, body=json.dumps(payload).encode())]
    )

    with connect(store) as conn:
        await sync_systems(conn, make_client(transport), now=NOW)

    with connect(store) as conn:
        row = conn.execute(
            "SELECT cost_index FROM system_cost_index WHERE solar_system_id = 30000142"
        ).fetchone()

    assert row["cost_index"] == pytest.approx(0.0421)


async def test_the_trailing_edge_is_measured_in_days_not_rows(store: Path) -> None:
    # History is sparse: ESI emits no row for a day that did not trade, so the
    # last three rows can span months. Splitting by position would treat a long
    # settled day as the trailing edge and rewrite it.
    sparse = [day("2026-06-01", 100.0), day("2026-07-01", 100.0), day("2026-09-17", 100.0)]
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(sparse)])),
            THE_FORGE,
            [31796],
            now=NOW,
        )

    contradicting = [day("2026-06-01", 999.0), day("2026-07-01", 999.0), day("2026-09-17", 250.0)]
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(contradicting)])),
            THE_FORGE,
            [31796],
            now=NOW + timedelta(days=1),
        )

    with connect(store) as conn:
        by_date = dict(conn.execute("SELECT date, average FROM market_history").fetchall())

    assert by_date["2026-06-01"] == pytest.approx(100.0), "settled months ago"
    assert by_date["2026-07-01"] == pytest.approx(100.0), "also settled"
    assert by_date["2026-09-17"] == pytest.approx(250.0), "the actual trailing edge"


async def test_settled_days_of_an_illiquid_item_are_never_rewritten(store: Path) -> None:
    # Anchoring the trailing edge on the newest *row* puts the cutoff wherever
    # that item last traded, so a dormant item's months-old rows are rewritten
    # forever. Settling is a property of the calendar, not of the data — and
    # this hits illiquid items hardest, whose Valuation Basis is most fragile.
    dormant = [day("2026-01-10", 100.0), day("2026-05-30", 100.0), day("2026-06-01", 100.0)]
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(dormant)])),
            THE_FORGE,
            [31796],
            now=NOW,
        )

    contradicting = [day("2026-01-10", 999.0), day("2026-05-30", 999.0), day("2026-06-01", 999.0)]
    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(contradicting)])),
            THE_FORGE,
            [31796],
            now=NOW + timedelta(days=1),
        )

    with connect(store) as conn:
        averages = [r[0] for r in conn.execute("SELECT average FROM market_history")]

    assert averages == pytest.approx([100.0, 100.0, 100.0]), "all three settled months ago"


async def test_one_failed_type_does_not_discard_the_rest_of_the_run(store: Path) -> None:
    # Without this, a single 404 throws away every successful fetch, records
    # nothing, and makes the next run pay the whole error budget again.
    transport = FakeTransport(
        responses=[
            history_response([day("2026-09-17")]),
            Response(status=404, headers={}, body=b""),
            history_response([day("2026-09-17")]),
        ]
    )

    with connect(store) as conn:
        summary = await sync_history(conn, make_client(transport), THE_FORGE, [1, 2, 3], now=NOW)

    assert summary.fetched == 2
    assert len(summary.failures) == 1
    assert summary.failures[0][0] in (1, 2, 3)

    with connect(store) as conn:
        stored = {r[0] for r in conn.execute("SELECT DISTINCT type_id FROM market_history")}
    assert len(stored) == 2, "the successful fetches were kept"


async def test_a_failed_type_is_retried_next_run_while_the_others_are_not(store: Path) -> None:
    transport = FakeTransport(
        responses=[
            history_response([day("2026-09-17")], NOW + timedelta(hours=6)),
            Response(status=404, headers={}, body=b""),
        ]
    )
    with connect(store) as conn:
        await sync_history(conn, make_client(transport), THE_FORGE, [1, 2], now=NOW)

    again = FakeTransport(responses=[history_response([day("2026-09-17")])])
    with connect(store) as conn:
        summary = await sync_history(conn, make_client(again), THE_FORGE, [1, 2], now=NOW)

    assert summary.fetched == 1, "only the one that failed"
    assert summary.skipped == 1, "the one that succeeded is inside its Expires floor"


async def test_reports_rows_written_not_rows_offered(store: Path) -> None:
    rows = [day("2026-06-01"), day("2026-06-02")]
    with connect(store) as conn:
        first = await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(rows)])),
            THE_FORGE,
            [31796],
            now=NOW,
        )

    with connect(store) as conn:
        second = await sync_history(
            conn,
            make_client(FakeTransport(responses=[history_response(rows)])),
            THE_FORGE,
            [31796],
            now=NOW + timedelta(days=1),
        )

    assert first.rows == 2
    assert second.rows == 0, "a re-fetch that changed nothing wrote nothing"


async def test_progress_is_reported_while_fetching_not_after(store: Path) -> None:
    seen: list[int] = []

    class Watching(FakeTransport):
        async def get(self, url: str, headers: dict[str, str] | None = None) -> Response:
            # Progress reported so far, observed from inside a request.
            seen.append(len(reported))
            return await super().get(url, headers)

    reported: list[tuple[int, int]] = []
    transport = Watching(responses=[history_response([day("2026-09-17")]) for _ in range(4)])

    with connect(store) as conn:
        await sync_history(
            conn,
            make_client(transport),
            THE_FORGE,
            [1, 2, 3, 4],
            now=NOW,
            on_progress=lambda done, total: reported.append((done, total)),
        )

    assert reported[-1] == (4, 4)
    assert max(seen) > 0, "progress should arrive during the fetch, not only after it"
