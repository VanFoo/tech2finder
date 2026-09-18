import sqlite3
from collections.abc import Iterator

import pytest

from tech2finder.store.connection import connect


@pytest.fixture
def conn(tmp_path) -> Iterator[sqlite3.Connection]:  # type: ignore[no-untyped-def]
    """An on-disk store, so tests exercise the same connection setup production uses."""
    with connect(tmp_path / "test.db") as connection:
        yield connection
