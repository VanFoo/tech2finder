"""SQLite connection handling.

One place decides how a connection to the store is configured, so every caller
gets the same pragmas rather than each remembering to set them.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    """Open the store at ``path``, creating it and its parents if absent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # WAL lets the web layer read while a scan writes; without it a long
        # import would block the UI.
        connection.execute("PRAGMA journal_mode = WAL")
        yield connection
    finally:
        connection.close()
