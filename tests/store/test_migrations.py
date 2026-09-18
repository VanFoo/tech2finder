"""The migration runner is tested against fixture migrations rather than the
project's own, so these tests do not move every time a later ticket adds a table."""

import sqlite3
from pathlib import Path

import pytest

from tech2finder.store.migrations import apply_migrations


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "0001_widgets.sql").write_text("CREATE TABLE widgets (id INTEGER PRIMARY KEY);")
    (d / "0002_gadgets.sql").write_text("CREATE TABLE gadgets (id INTEGER PRIMARY KEY);")
    return d


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r[0] for r in rows}


def test_applies_every_migration_to_a_fresh_database(
    conn: sqlite3.Connection, migrations_dir: Path
) -> None:
    applied = apply_migrations(conn, migrations_dir)

    assert applied == ["0001_widgets", "0002_gadgets"]
    assert {"widgets", "gadgets"} <= table_names(conn)


def test_applies_migrations_in_filename_order(conn: sqlite3.Connection, tmp_path: Path) -> None:
    d = tmp_path / "ordered"
    d.mkdir()
    # 0002 depends on the table 0001 creates, so it only succeeds in order.
    (d / "0002_add_column.sql").write_text("ALTER TABLE widgets ADD COLUMN label TEXT;")
    (d / "0001_widgets.sql").write_text("CREATE TABLE widgets (id INTEGER PRIMARY KEY);")

    assert apply_migrations(conn, d) == ["0001_widgets", "0002_add_column"]


def test_is_idempotent(conn: sqlite3.Connection, migrations_dir: Path) -> None:
    apply_migrations(conn, migrations_dir)

    assert apply_migrations(conn, migrations_dir) == []


def test_applies_only_the_migrations_that_are_new(
    conn: sqlite3.Connection, migrations_dir: Path
) -> None:
    apply_migrations(conn, migrations_dir)
    (migrations_dir / "0003_sprockets.sql").write_text(
        "CREATE TABLE sprockets (id INTEGER PRIMARY KEY);"
    )

    assert apply_migrations(conn, migrations_dir) == ["0003_sprockets"]


def test_a_failing_migration_leaves_no_partial_schema_behind(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "0001_ok.sql").write_text("CREATE TABLE ok (id INTEGER PRIMARY KEY);")
    (d / "0002_broken.sql").write_text(
        "CREATE TABLE half (id INTEGER PRIMARY KEY); THIS IS NOT SQL;"
    )

    with pytest.raises(sqlite3.Error):
        apply_migrations(conn, d)

    names = table_names(conn)
    assert "ok" in names, "the migration that succeeded should have been kept"
    assert "half" not in names, "the failing migration should have rolled back entirely"

    # The failure must not have been recorded as applied, so a retry tries it again.
    (d / "0002_broken.sql").write_text("CREATE TABLE half (id INTEGER PRIMARY KEY);")
    assert apply_migrations(conn, d) == ["0002_broken"]


def test_rejects_a_migration_whose_name_does_not_follow_the_convention(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    d = tmp_path / "badly_named"
    d.mkdir()
    (d / "oops'; DROP TABLE schema_migrations; --.sql").write_text("SELECT 1;")

    with pytest.raises(ValueError, match="NNNN_description"):
        apply_migrations(conn, d)
