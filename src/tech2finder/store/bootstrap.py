"""Bringing a store up to date.

Separate from reading it, because migrating is a startup concern: it takes the
write lock and is not safe to run concurrently, so it must not happen inside a
request handler.
"""

from pathlib import Path

from tech2finder.store.connection import connect
from tech2finder.store.migrations import apply_migrations

#: Key under which the SDE import records the dump's md5sum. Lives here, beside
#: the migration that creates `meta`, so neither `sde` nor `web` has to depend
#: on the other to name it.
SDE_MD5 = "sde_md5"


def bootstrap(path: Path) -> list[str]:
    """Create the store if absent and bring its schema up to date."""
    with connect(path) as conn:
        return apply_migrations(conn)
