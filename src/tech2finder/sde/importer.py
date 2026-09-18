"""Copying the SDE subset into the store.

The dump is attached and the rows moved with INSERT ... SELECT, so the work
happens inside SQLite rather than being marshalled through Python a row at a
time.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from tech2finder.store.bootstrap import SDE_MD5

#: Tables the import needs to find in a dump before it will trust it.
REQUIRED = (
    "invTypes",
    "invMarketGroups",
    "industryBlueprints",
    "industryActivity",
    "industryActivityMaterials",
    "industryActivityProducts",
    "industryActivityProbabilities",
    "dgmTypeAttributes",
)

#: Target table -> the SELECT that fills it from the attached dump.
#:
#: Column order matches each table's declaration. The SDE splits an attribute's
#: value across valueInt and valueFloat, which is the one place the import
#: reshapes rather than renames.
COPY: dict[str, str] = {
    "sde_type": """
        SELECT typeID, typeName, groupID, marketGroupID,
               COALESCE(portionSize, 1), COALESCE(published, 0)
        FROM sde.invTypes WHERE typeName IS NOT NULL
    """,
    "sde_market_group": """
        SELECT marketGroupID, parentGroupID, marketGroupName
        FROM sde.invMarketGroups WHERE marketGroupName IS NOT NULL
    """,
    "sde_blueprint": """
        SELECT typeID, COALESCE(maxProductionLimit, 1) FROM sde.industryBlueprints
    """,
    "sde_activity_time": """
        SELECT typeID, activityID, COALESCE(time, 0) FROM sde.industryActivity
    """,
    "sde_activity_material": """
        SELECT typeID, activityID, materialTypeID, quantity
        FROM sde.industryActivityMaterials
    """,
    "sde_activity_product": """
        SELECT typeID, activityID, productTypeID, quantity
        FROM sde.industryActivityProducts
    """,
    "sde_invention_probability": """
        SELECT typeID, productTypeID, probability
        FROM sde.industryActivityProbabilities WHERE activityID = 8
    """,
    "sde_type_attribute": """
        SELECT typeID, attributeID, COALESCE(valueFloat, valueInt)
        FROM sde.dgmTypeAttributes WHERE COALESCE(valueFloat, valueInt) IS NOT NULL
    """,
}


@dataclass(frozen=True)
class ImportSummary:
    rows: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.rows.values())


def import_sde(
    conn: sqlite3.Connection, dump_path: Path, fingerprint: str | None = None
) -> ImportSummary:
    """Replace the store's SDE tables with the contents of ``dump_path``.

    Replaces rather than merges: a dump is a complete snapshot, so a row absent
    from a newer one has been removed from the game and should not survive.
    """
    if not dump_path.is_file():
        raise FileNotFoundError(f"SDE dump not found: {dump_path}")

    _reject_unless_it_looks_like_an_sde(dump_path)

    conn.execute("ATTACH DATABASE ? AS sde", (str(dump_path),))
    try:
        counts: dict[str, int] = {}
        for table, select in COPY.items():
            conn.execute(f"DELETE FROM {table}")
            # Duplicate keys are possible in a foreign dump; the last row wins
            # rather than aborting an import over one bad row.
            conn.execute(f"INSERT OR REPLACE INTO {table} {select}")
            counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

        if fingerprint is None:
            # Leaving a previous dump's fingerprint in place would have the
            # status page claim an SDE that is no longer the one in the store.
            conn.execute("DELETE FROM meta WHERE key = ?", (SDE_MD5,))
        else:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (SDE_MD5, fingerprint),
            )
        # The whole import is one transaction, and it has to be closed before
        # detaching: SQLite refuses to DETACH while a transaction is open.
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute("DETACH DATABASE sde")

    return ImportSummary(rows=counts)


def _reject_unless_it_looks_like_an_sde(dump_path: Path) -> None:
    """Fail before touching the store, so a wrong file cannot empty it."""
    # Opened by path, not as a file: URI, because a path containing '#' or '?'
    # would be parsed as a URI fragment or query and silently open a different,
    # empty database — reporting a perfectly good dump as invalid.
    probe = sqlite3.connect(dump_path)
    try:
        probe.execute("PRAGMA query_only = ON")
        present = {row[0] for row in probe.execute("SELECT name FROM sqlite_master")}
    finally:
        probe.close()

    missing = [name for name in REQUIRED if name not in present]
    if missing:
        raise ValueError(
            f"{dump_path} does not look like an EVE SDE dump; missing tables: {', '.join(missing)}"
        )
