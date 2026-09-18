"""The import copies the SDE subset into the store. It should translate names
and nothing else — interpretation belongs in the cost model, not here."""

from pathlib import Path

import pytest

from tech2finder.sde.importer import import_sde
from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect
from tech2finder.web.status import store_status

from .synthetic_dump import (
    ACCELERANT,
    INVENTION,
    MANUFACTURING,
    T1_BLUEPRINT,
    T2_BLUEPRINT,
    T2_RIG,
    build,
)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    path = tmp_path / "store.db"
    bootstrap(path)
    return path


@pytest.fixture
def dump(tmp_path: Path) -> Path:
    return build(tmp_path / "sde.db")


def test_reports_what_it_imported(store: Path, dump: Path) -> None:
    with connect(store) as conn:
        summary = import_sde(conn, dump)

    assert summary.rows["sde_type"] == 11
    assert summary.rows["sde_activity_material"] == 6
    assert summary.total > 0


def test_imports_the_bill_of_materials_exactly_as_published(store: Path, dump: Path) -> None:
    with connect(store) as conn:
        import_sde(conn, dump)

    with connect(store) as conn:
        rows = conn.execute(
            "SELECT material_type_id, quantity FROM sde_activity_material "
            "WHERE blueprint_id = ? AND activity_id = ? ORDER BY material_type_id",
            (T2_BLUEPRINT, MANUFACTURING),
        ).fetchall()

    assert [(r[0], r[1]) for r in rows] == [
        (11484, 1),  # R.A.M.- Shield Tech
        (25617, 6),  # Power Circuit
        (25619, 6),  # Logic Circuit
        (25625, 3),  # Enhanced Ward Console
    ]


def test_invention_products_are_blueprints_and_carry_the_bpc_run_count(
    store: Path, dump: Path
) -> None:
    with connect(store) as conn:
        import_sde(conn, dump)

    with connect(store) as conn:
        row = conn.execute(
            "SELECT product_type_id, quantity FROM sde_activity_product "
            "WHERE blueprint_id = ? AND activity_id = ?",
            (T1_BLUEPRINT, INVENTION),
        ).fetchone()

    assert row["product_type_id"] == T2_BLUEPRINT, "invention yields a blueprint, not the item"
    assert row["quantity"] == 1, "a T2 rig BPC has 1 run; read per blueprint, never per category"


def test_collapses_int_and_float_attribute_values_into_one_column(store: Path, dump: Path) -> None:
    # The SDE splits an attribute's value across valueInt and valueFloat.
    with connect(store) as conn:
        import_sde(conn, dump)

    with connect(store) as conn:
        values = dict(
            conn.execute(
                "SELECT attribute_id, value FROM sde_type_attribute WHERE type_id = 37146"
            ).fetchall()
        )

    assert values[2594] == -2.0, "float-valued"
    assert values[2095] == 32.0, "int-valued"


def test_is_idempotent_and_replaces_rather_than_duplicates(store: Path, dump: Path) -> None:
    with connect(store) as conn:
        first = import_sde(conn, dump)
    with connect(store) as conn:
        second = import_sde(conn, dump)

    assert first.rows == second.rows

    with connect(store) as conn:
        assert conn.execute("SELECT count(*) FROM sde_type").fetchone()[0] == 11


def test_records_the_fingerprint_so_a_later_import_can_skip_the_download(
    store: Path, dump: Path
) -> None:
    with connect(store) as conn:
        import_sde(conn, dump, fingerprint="de0092efcdcaf701ecfe1b6522ab963c")

    assert store_status(store).sde_md5 == "de0092efcdcaf701ecfe1b6522ab963c"


def test_rejects_a_dump_that_is_not_an_sde(store: Path, tmp_path: Path) -> None:
    not_an_sde = tmp_path / "empty.db"
    with connect(not_an_sde) as conn:
        conn.execute("CREATE TABLE unrelated (x INTEGER)")

    with connect(store) as conn, pytest.raises(ValueError, match="does not look like"):
        import_sde(conn, not_an_sde)


def test_rejects_a_dump_that_is_missing(store: Path, tmp_path: Path) -> None:
    with connect(store) as conn, pytest.raises(FileNotFoundError):
        import_sde(conn, tmp_path / "absent.db")


def test_leaves_the_store_untouched_when_the_dump_is_rejected(store: Path, dump: Path) -> None:
    with connect(store) as conn:
        import_sde(conn, dump)

    with connect(store) as conn, pytest.raises(FileNotFoundError):
        import_sde(conn, store.parent / "absent.db")

    with connect(store) as conn:
        assert conn.execute("SELECT count(*) FROM sde_type").fetchone()[0] == 11


def test_the_decryptor_attributes_survive_the_round_trip(store: Path, dump: Path) -> None:
    with connect(store) as conn:
        import_sde(conn, dump)

    with connect(store) as conn:
        values = dict(
            conn.execute(
                "SELECT attribute_id, value FROM sde_type_attribute WHERE type_id = ?",
                (ACCELERANT,),
            ).fetchall()
        )

    # Accelerant, verified against the wiki and the SDE in the research file.
    assert values[1112] == pytest.approx(1.2)  # probability multiplier
    assert values[1124] == 1.0  # +1 run
    assert values[1113] == 2.0  # +2 ME
    assert values[1114] == 10.0  # +10 TE


def test_the_manufactured_item_is_reachable_from_the_t1_blueprint(store: Path, dump: Path) -> None:
    # The chain the scan engine walks: T1 blueprint -> invent -> T2 blueprint ->
    # manufacture -> T2 item.
    with connect(store) as conn:
        import_sde(conn, dump)

    with connect(store) as conn:
        row = conn.execute(
            """
            SELECT item.product_type_id AS item_id, t.name
            FROM sde_activity_product invented
            JOIN sde_activity_product item
              ON item.blueprint_id = invented.product_type_id AND item.activity_id = 1
            JOIN sde_type t ON t.type_id = item.product_type_id
            WHERE invented.blueprint_id = ? AND invented.activity_id = 8
            """,
            (T1_BLUEPRINT,),
        ).fetchone()

    assert row["item_id"] == T2_RIG
    assert row["name"] == "Medium Core Defense Field Extender II"


def test_an_import_without_a_fingerprint_clears_a_stale_one(store: Path, dump: Path) -> None:
    # Otherwise the status page keeps claiming an SDE that is no longer the one
    # in the store.
    with connect(store) as conn:
        import_sde(conn, dump, fingerprint="de0092efcdcaf701ecfe1b6522ab963c")
    with connect(store) as conn:
        import_sde(conn, dump)

    assert store_status(store).sde_md5 is None


def test_accepts_a_dump_whose_path_contains_uri_punctuation(store: Path, tmp_path: Path) -> None:
    # Opened as a file: URI, '#' would be read as a fragment and silently open a
    # different, empty database — rejecting a perfectly good dump.
    awkward = tmp_path / "cache#1"
    awkward.mkdir()
    build(awkward / "sde.db")

    with connect(store) as conn:
        summary = import_sde(conn, awkward / "sde.db")

    assert summary.total > 0
