"""What the status page shows.

The view builds one of these and the template renders it. Nothing here is
computed in a template, which is the constraint ADR-0012 imposes so that
swapping the frontend later stays cheap.
"""

from dataclasses import dataclass
from pathlib import Path

from tech2finder.store.connection import connect
from tech2finder.store.migrations import apply_migrations

#: Key under which the SDE import records the dump's md5sum. Fuzzwork publishes
#: a checksum alongside the dump, so a later import can ask "has the SDE
#: changed?" for a few bytes rather than re-downloading 136 MB.
SDE_MD5 = "sde_md5"


@dataclass(frozen=True)
class StoreStatus:
    store_path: Path
    applied_migrations: list[str]
    sde_md5: str | None

    @property
    def has_sde(self) -> bool:
        return self.sde_md5 is not None


def store_status(store_path: Path) -> StoreStatus:
    with connect(store_path) as conn:
        apply_migrations(conn)
        names = [row[0] for row in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (SDE_MD5,)).fetchone()

    return StoreStatus(
        store_path=store_path,
        applied_migrations=names,
        sde_md5=row["value"] if row else None,
    )
