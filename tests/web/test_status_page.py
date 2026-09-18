"""The boundary ADR-0012 cares about: the view builds a plain dataclass and the
template only renders it. If a number has to be computed to show it, that
computation belongs behind the boundary, not in the template."""

from dataclasses import is_dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from tech2finder.store.connection import connect
from tech2finder.web.app import create_app
from tech2finder.web.status import store_status


def test_the_status_page_renders(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "store.db"))

    response = client.get("/")

    assert response.status_code == 200
    assert "tech2finder" in response.text


def test_the_status_page_reports_the_migrations_that_have_been_applied(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "store.db"))

    response = client.get("/")

    assert "0001_meta" in response.text


def test_the_view_hands_the_template_a_plain_dataclass(tmp_path: Path) -> None:
    status = store_status(tmp_path / "store.db")

    assert is_dataclass(status)
    assert status.applied_migrations == ["0001_meta"]
    assert status.store_path.name == "store.db"


def test_a_fresh_store_reports_no_sde_imported(tmp_path: Path) -> None:
    status = store_status(tmp_path / "store.db")

    assert status.sde_md5 is None
    assert status.has_sde is False


def test_an_imported_sde_is_reported_with_its_fingerprint(tmp_path: Path) -> None:
    path = tmp_path / "store.db"
    store_status(path)  # applies migrations

    with connect(path) as conn:
        conn.execute("INSERT INTO meta (key, value) VALUES ('sde_md5', 'de0092ef')")
        conn.commit()

    status = store_status(path)

    assert status.sde_md5 == "de0092ef"
    assert status.has_sde is True
