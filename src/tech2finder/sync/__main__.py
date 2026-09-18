"""Fetch market data for a market group: ``python -m tech2finder.sync``.

Safe to re-run, and cheap to: nothing is fetched before ESI's Expires floor
allows it, so re-running soon after does nothing but check. Running it *is* the
refresh control — there is no scheduled refresh (ADR-0011).
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from tech2finder.sde.repository import invention_paths
from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect
from tech2finder.sync.budget import CEILING, ErrorBudget
from tech2finder.sync.esi import THE_FORGE, EsiClient, UnidentifiedClient
from tech2finder.sync.market import sync_history, sync_prices, sync_systems

USER_AGENT_ENV = "TECH2FINDER_USER_AGENT"


def progress(done: int, total: int) -> None:
    print(f"\r  history {done}/{total}", end="", flush=True)


async def run(store_path: Path, market_groups: list[int], user_agent: str) -> None:
    bootstrap(store_path)

    with connect(store_path) as conn:
        paths = invention_paths(conn, market_groups)
        type_ids = sorted({path.product_type_id for path in paths})

    if not type_ids:
        print(f"No invention-reachable items in market groups {market_groups}.")
        print("Has the SDE been imported? Run: python -m tech2finder.sde")
        return

    print(f"{len(type_ids)} items in {len(market_groups)} market group(s)")

    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as http:
        from tech2finder.sync.transport import HttpxTransport

        client = EsiClient(
            transport=HttpxTransport(http),
            budget=ErrorBudget(now=asyncio.get_running_loop().time, sleep=asyncio.sleep),
            user_agent=user_agent,
        )

        with connect(store_path) as conn:
            now = datetime.now(UTC)

            history = await sync_history(
                conn, client, THE_FORGE, type_ids, now=now, on_progress=progress
            )
            print()
            print(
                f"  history  fetched {history.fetched}, skipped {history.skipped} "
                f"(still inside the Expires floor), {history.rows:,} rows"
            )

            prices = await sync_prices(conn, client, now=now)
            print(f"  prices   {'fetched' if prices.fetched else 'skipped'}, {prices.rows:,} types")

            systems = await sync_systems(conn, client, now=now)
            print(
                f"  systems  {'fetched' if systems.fetched else 'skipped'}, "
                f"{systems.rows:,} indices"
            )

        print(
            f"\nerror budget: {client.budget.remaining}/100 remaining, "
            f"concurrency ceiling {CEILING}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch ESI market data")
    parser.add_argument("--store", type=Path, default=Path("data/tech2finder.db"))
    parser.add_argument(
        "--market-group",
        type=int,
        action="append",
        default=None,
        help="market group id to fetch; repeatable. Children are included.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.environ.get(USER_AGENT_ENV, ""),
        help=f"app name and a contact address. Defaults to ${USER_AGENT_ENV}.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.store, args.market_group or [1111], args.user_agent))
    except UnidentifiedClient as exc:
        # Refusing to start is better than running unidentified: the cost of the
        # latter is losing API access, and that is not locally visible.
        print(f"error: {exc}", file=sys.stderr)
        print(
            f"\nSet {USER_AGENT_ENV}, e.g.\n"
            f'  export {USER_AGENT_ENV}="tech2finder/0.1 (you@example.org)"',
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
