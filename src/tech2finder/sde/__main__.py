"""Download and import the SDE: ``python -m tech2finder.sde``.

Safe to re-run. The published fingerprint is checked first, so an unchanged SDE
costs one small request and no download.
"""

import argparse
import asyncio
from pathlib import Path

import httpx

from tech2finder.sde.download import ensure_dump
from tech2finder.sde.importer import import_sde
from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect
from tech2finder.sync.transport import HttpxTransport

#: Fuzzwork is not ESI, so CCP's contact-address rule does not apply here, but
#: identifying the client is good manners either way. No address: this is a
#: public repository.
USER_AGENT = "tech2finder (+https://github.com/VanFoo/tech2finder)"


async def run(store_path: Path, cache: Path) -> None:
    bootstrap(store_path)

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=900.0, headers={"User-Agent": USER_AGENT}
    ) as client:
        print(f"Checking {cache} against the published SDE fingerprint...")
        dump = await ensure_dump(cache, HttpxTransport(client))

    print(
        f"{'Downloaded' if dump.downloaded else 'Already current'}: "
        f"{dump.path} ({dump.fingerprint})"
    )

    print("Importing...")
    with connect(store_path) as conn:
        summary = import_sde(conn, dump.path, fingerprint=dump.fingerprint)

    width = max(len(name) for name in summary.rows)
    for table, count in summary.rows.items():
        print(f"  {table:<{width}}  {count:>9,}")
    print(f"  {'total':<{width}}  {summary.total:>9,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and import the EVE SDE")
    parser.add_argument("--store", type=Path, default=Path("data/tech2finder.db"))
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("data/sde"),
        help="where the downloaded dump is kept between runs",
    )
    args = parser.parse_args()
    asyncio.run(run(args.store, args.cache))


if __name__ == "__main__":
    main()
