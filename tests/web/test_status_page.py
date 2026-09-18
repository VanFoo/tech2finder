"""The boundary ADR-0012 cares about: the view builds a plain dataclass and the
template only renders it. If a number has to be computed to show it, that
computation belongs behind the boundary, not in the template."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import is_dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect
from tech2finder.store.migrations import MIGRATIONS
from tech2finder.web.app import create_app
from tech2finder.web.status import store_status


@pytest.fixture
def store(tmp_path: Path) -> Path:
    path = tmp_path / "store.db"
    bootstrap(path)
    return path


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # Entered as a context manager so lifespan runs; that is what migrates.
    with TestClient(create_app(store_path=tmp_path / "store.db")) as c:
        yield c


def test_the_status_page_renders(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "tech2finder" in response.text


def test_the_status_page_reports_the_migrations_that_have_been_applied(
    client: TestClient,
) -> None:
    assert "0001_meta" in client.get("/").text


def test_starting_the_app_migrates_the_store(tmp_path: Path) -> None:
    path = tmp_path / "store.db"

    with TestClient(create_app(store_path=path)):
        pass

    # Compared against the files on disk rather than a hardcoded list, so
    # adding a migration does not mean editing this test.
    expected = tuple(sorted(p.stem for p in MIGRATIONS.glob("*.sql")))
    assert store_status(path).applied_migrations == expected


def test_the_view_hands_the_template_a_plain_dataclass(store: Path) -> None:
    status = store_status(store)

    assert is_dataclass(status)
    assert status.applied_migrations == tuple(sorted(p.stem for p in MIGRATIONS.glob("*.sql")))
    assert status.store_path.name == "store.db"


def test_a_fresh_store_reports_no_sde_imported(store: Path) -> None:
    status = store_status(store)

    assert status.sde_md5 is None
    assert status.has_sde is False


def test_an_imported_sde_is_reported_with_its_fingerprint(store: Path) -> None:
    with connect(store) as conn:
        conn.execute("INSERT INTO meta (key, value) VALUES ('sde_md5', 'de0092ef')")

    status = store_status(store)

    assert status.sde_md5 == "de0092ef"
    assert status.has_sde is True


def test_the_status_is_hashable(store: Path) -> None:
    # A frozen dataclass exists to be a value: it should be usable as a dict key
    # and be genuinely immutable, which a list field defeats.
    assert {store_status(store)}


def test_concurrent_requests_do_not_collide_over_migrations(client: TestClient) -> None:
    # Views are sync, so FastAPI dispatches them to a threadpool and several
    # genuinely run at once. Migrating per request races; migrating at startup
    # does not.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(client.get, "/") for _ in range(16)]
        statuses = [f.result().status_code for f in futures]

    assert statuses == [200] * 16
