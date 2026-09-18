"""Fetching market data and keeping it.

Two policies live here, both from ADR-0011:

**`Expires` is a floor, never a trigger.** Nothing is re-fetched sooner than ESI
permits, and nothing refreshes on a schedule. Data is held as long as it is
useful, which for a long-term planning tool is well past its cache lifetime.

**A closed day never changes.** Past history rows are written once and left
alone; only the trailing edge, which may still be settling, is replaced.
"""

import asyncio
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from tech2finder.sync.esi import EsiClient, History, HistoryRow

#: How many of the newest days are treated as still settling and replaced on
#: every fetch. ESI's series lags one to two days behind today, so a row is
#: usually already closed when it first appears; three is that lag plus margin.
TRAILING_EDGE_DAYS = 3

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class SyncSummary:
    fetched: int
    skipped: int
    rows: int
    #: Types whose fetch failed. Kept rather than raised: one bad type should
    #: not throw away the rest of a run that spent real error budget.
    failures: tuple[tuple[int, BaseException], ...] = ()

    @property
    def total(self) -> int:
        return self.fetched + self.skipped + len(self.failures)


async def sync_history(
    conn: sqlite3.Connection,
    client: EsiClient,
    region_id: int,
    type_ids: Iterable[int],
    now: datetime,
    on_progress: ProgressCallback | None = None,
) -> SyncSummary:
    """Bring each type's daily history up to date, respecting the Expires floor."""
    wanted = list(type_ids)
    due = [type_id for type_id in wanted if _is_due(conn, f"history:{type_id}", now)]
    skipped = len(wanted) - len(due)

    if not due:
        return SyncSummary(fetched=0, skipped=skipped, rows=0)

    rows = 0
    total = len(wanted)
    done = skipped

    # The client's budget bounds how many of these are actually in flight; they
    # are all launched and it decides.
    async def fetch(type_id: int) -> History:
        history = await client.market_history(region_id, type_id)
        # Reported here rather than in the storage loop below, which runs only
        # after every request has finished — progress that arrives all at once,
        # at the end, is not progress.
        nonlocal done
        done += 1
        if on_progress is not None:
            on_progress(done, total)
        return history

    # return_exceptions, deliberately: without it one failed type discards every
    # successful fetch in the run, nothing is recorded, and the next invocation
    # pays the whole error budget again.
    results = await asyncio.gather(*(fetch(type_id) for type_id in due), return_exceptions=True)

    today = now.date()
    succeeded = 0
    failures: list[tuple[int, BaseException]] = []
    for type_id, result in zip(due, results, strict=True):
        if isinstance(result, BaseException):
            failures.append((type_id, result))
            continue
        rows += _store_history(conn, result, today)
        _record_fetch(conn, f"history:{result.type_id}", now, result.expires)
        succeeded += 1

    conn.commit()
    return SyncSummary(fetched=succeeded, skipped=skipped, rows=rows, failures=tuple(failures))


async def sync_prices(conn: sqlite3.Connection, client: EsiClient, now: datetime) -> SyncSummary:
    """One call covering every type. Adjusted price, which job fees are assessed on."""
    if not _is_due(conn, "prices", now):
        return SyncSummary(fetched=0, skipped=1, rows=0)

    result = await client.market_prices()
    conn.executemany(
        "INSERT INTO adjusted_price (type_id, adjusted_price, average_price) VALUES (?, ?, ?) "
        "ON CONFLICT (type_id) DO UPDATE SET "
        "adjusted_price = excluded.adjusted_price, average_price = excluded.average_price",
        [(p.type_id, p.adjusted_price, p.average_price) for p in result.prices.values()],
    )
    _record_fetch(conn, "prices", now, result.expires)
    conn.commit()
    return SyncSummary(fetched=1, skipped=0, rows=len(result.prices))


async def sync_systems(conn: sqlite3.Connection, client: EsiClient, now: datetime) -> SyncSummary:
    """One call covering every system. The index is read, never computed."""
    if not _is_due(conn, "systems", now):
        return SyncSummary(fetched=0, skipped=1, rows=0)

    result = await client.industry_systems()
    conn.executemany(
        "INSERT INTO system_cost_index (solar_system_id, activity, cost_index) VALUES (?, ?, ?) "
        "ON CONFLICT (solar_system_id, activity) DO UPDATE SET cost_index = excluded.cost_index",
        [(system, activity, index) for (system, activity), index in result.indices.items()],
    )
    _record_fetch(conn, "systems", now, result.expires)
    conn.commit()
    return SyncSummary(fetched=1, skipped=0, rows=len(result.indices))


def _store_history(conn: sqlite3.Connection, history: History, today: date) -> int:
    if not history.rows:
        return 0

    settled, trailing = _split_trailing_edge(history.rows, today)

    # A closed day never changes: written once and left alone. If ESI ever
    # contradicts itself about a past date, the stored value wins rather than
    # shifting the Valuation Basis under a ranking already acted on.
    written = conn.executemany(
        "INSERT OR IGNORE INTO market_history "
        "(type_id, date, average, highest, lowest, order_count, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(history.type_id, *_values(row)) for row in settled],
    ).rowcount
    # The newest days may still be settling, so they are replaced.
    written += conn.executemany(
        "INSERT OR REPLACE INTO market_history "
        "(type_id, date, average, highest, lowest, order_count, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(history.type_id, *_values(row)) for row in trailing],
    ).rowcount
    # Rows actually written, not rows offered: a re-fetch that changed nothing
    # should not report thousands of rows.
    return max(0, written)


def _split_trailing_edge(
    rows: Sequence[HistoryRow], today: date
) -> tuple[list[HistoryRow], list[HistoryRow]]:
    """Settled days and still-settling ones, split by date relative to **today**.

    Two ways to get this wrong, both tried:

    - By row count. History is sparse, so the last three rows can span months
      and a long-settled day gets rewritten as though it were the tail.
    - By the newest *row's* date. For an item that last traded in June, the
      cutoff lands in June too, and those months-old rows are rewritten forever.
      That hits illiquid items hardest — exactly the ones whose Valuation Basis
      is most fragile.

    Settling is a property of the calendar, not of the data.
    """
    cutoff = today - timedelta(days=TRAILING_EDGE_DAYS - 1)
    ordered = sorted(rows, key=lambda row: row.date)

    settled = [row for row in ordered if date.fromisoformat(row.date) < cutoff]
    trailing = [row for row in ordered if date.fromisoformat(row.date) >= cutoff]
    return settled, trailing


def _values(row: HistoryRow) -> tuple[object, ...]:
    return (row.date, row.average, row.highest, row.lowest, row.order_count, row.volume)


def _is_due(conn: sqlite3.Connection, resource: str, now: datetime) -> bool:
    """Whether ESI permits asking again yet. Never whether we ought to."""
    row = conn.execute(
        "SELECT expires_at FROM esi_fetch WHERE resource = ?", (resource,)
    ).fetchone()
    if row is None:
        return True
    if row["expires_at"] is None:
        return True
    return now >= datetime.fromisoformat(row["expires_at"])


def _record_fetch(
    conn: sqlite3.Connection, resource: str, now: datetime, expires: datetime | None
) -> None:
    conn.execute(
        "INSERT INTO esi_fetch (resource, fetched_at, expires_at) VALUES (?, ?, ?) "
        "ON CONFLICT (resource) DO UPDATE SET "
        "fetched_at = excluded.fetched_at, expires_at = excluded.expires_at",
        (resource, now.isoformat(), expires.isoformat() if expires else None),
    )
