"""Forward-only SQL migrations.

Migrations are ``.sql`` files named ``NNNN_description.sql`` and applied in
filename order. Each runs in its own transaction together with the row that
records it, so a failure leaves the schema at the last good migration rather
than half-applied or applied-but-unrecorded.
"""

import re
import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"

#: A migration's stem. Restricting it keeps the name safe to inline into SQL
#: below, where a bound parameter is not available inside ``executescript``.
NAME = re.compile(r"\A[0-9]{4}_[a-z0-9_]+\Z")

_BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def apply_migrations(conn: sqlite3.Connection, directory: Path = MIGRATIONS) -> list[str]:
    """Apply every migration in ``directory`` not yet recorded. Returns those applied.

    Not safe to call concurrently: apply migrations once at startup rather than
    from a request handler.
    """
    if not directory.is_dir():
        # Returning an empty list would be indistinguishable from "already up to
        # date", and the real failure would surface later as a missing table.
        raise FileNotFoundError(f"migrations directory not found: {directory}")

    conn.execute(_BOOKKEEPING)
    conn.commit()

    already = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    pending = sorted(directory.glob("*.sql"), key=lambda p: p.name)

    applied: list[str] = []
    for migration in pending:
        name = migration.stem
        if not NAME.match(name):
            raise ValueError(
                f"migration {migration.name!r} must be named NNNN_description.sql "
                f"(digits, then lowercase words separated by underscores)"
            )
        if name in already:
            continue

        # executescript cannot take bound parameters and implicitly commits any
        # open transaction, so the transaction is opened inside the script. The
        # name is safe to inline because NAME has just constrained it. The
        # explicit ';' guards against a file whose last statement omits one,
        # which would otherwise glue onto the INSERT below.
        try:
            conn.executescript(
                "BEGIN;\n"
                f"{migration.read_text()}\n;\n"
                f"INSERT INTO schema_migrations (name) VALUES ('{name}');\n"
                "COMMIT;"
            )
        except sqlite3.Error:
            conn.rollback()
            raise

        applied.append(name)

    return applied
