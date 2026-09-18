import sqlite3
from pathlib import Path

from tech2finder.store.connection import connect


def test_creates_the_database_file_and_any_missing_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "store.db"

    with connect(path):
        pass

    assert path.exists()


def test_enforces_foreign_keys(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_returns_rows_that_can_be_addressed_by_column_name(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE t (name TEXT)")
    conn.execute("INSERT INTO t (name) VALUES ('Jita')")

    row = conn.execute("SELECT name FROM t").fetchone()

    assert row["name"] == "Jita"


def test_closes_the_connection_on_exit(tmp_path: Path) -> None:
    with connect(tmp_path / "store.db") as connection:
        pass

    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return
    raise AssertionError("connection should be closed after the context manager exits")
