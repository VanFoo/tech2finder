"""What the status page shows.

The view builds one of these and the template renders it. Nothing here is
computed in a template, which is the constraint ADR-0012 imposes so that
swapping the frontend later stays cheap.

Reads only. Bringing the schema up to date is a startup concern — see
``tech2finder.store.bootstrap``.
"""

from dataclasses import dataclass
from pathlib import Path

from tech2finder.store.bootstrap import SDE_MD5
from tech2finder.store.connection import connect


@dataclass(frozen=True)
class StoreStatus:
    store_path: Path
    #: A tuple, not a list: a frozen dataclass synthesises __hash__ from its
    #: fields, and a list field would make the value both unhashable and
    #: quietly mutable.
    applied_migrations: tuple[str, ...]
    sde_md5: str | None

    @property
    def has_sde(self) -> bool:
        return self.sde_md5 is not None


def store_status(store_path: Path) -> StoreStatus:
    with connect(store_path) as conn:
        names = tuple(
            row[0] for row in conn.execute("SELECT name FROM schema_migrations ORDER BY name")
        )
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (SDE_MD5,)).fetchone()

    return StoreStatus(
        store_path=store_path,
        applied_migrations=names,
        sde_md5=row["value"] if row else None,
    )
