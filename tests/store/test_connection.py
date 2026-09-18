import sqlite3
from pathlib import Path

import pytest

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


def test_commits_writes_when_the_block_exits_cleanly(tmp_path: Path) -> None:
    # sqlite3.connect used directly as a context manager commits on clean exit,
    # so a connect() that did not would silently lose writes for any caller
    # copying that habit.
    path = tmp_path / "store.db"
    with connect(path) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")

    with connect(path) as conn:
        assert [row[0] for row in conn.execute("SELECT x FROM t")] == [1]


def test_rolls_back_writes_when_the_block_raises(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    with connect(path) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")

    with pytest.raises(RuntimeError), connect(path) as conn:
        conn.execute("INSERT INTO t VALUES (1)")
        raise RuntimeError("boom")

    with connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 0
