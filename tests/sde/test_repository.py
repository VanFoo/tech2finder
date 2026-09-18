"""Reading the imported SDE. Returns plain dataclasses; no interpretation of
what the numbers mean, which belongs to the cost model."""

from pathlib import Path

import pytest

from tech2finder.sde.importer import import_sde
from tech2finder.sde.repository import (
    decryptors,
    invention_paths,
    manufacturing_materials,
    market_groups,
    rig_bonuses,
)
from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect

from .synthetic_dump import ACCELERANT, T1_BLUEPRINT, T2_BLUEPRINT, T2_RIG, build


@pytest.fixture
def store(tmp_path: Path) -> Path:
    path = tmp_path / "store.db"
    bootstrap(path)
    with connect(path) as conn:
        import_sde(conn, build(tmp_path / "sde.db"))
    return path


def test_lists_decryptors_with_their_four_modifiers(store: Path) -> None:
    with connect(store) as conn:
        found = decryptors(conn)

    accelerant = next(d for d in found if d.type_id == ACCELERANT)
    assert accelerant.name == "Accelerant Decryptor"
    assert accelerant.probability_multiplier == pytest.approx(1.2)
    assert accelerant.run_modifier == 1
    assert accelerant.me_modifier == 2
    assert accelerant.te_modifier == 10


def test_finds_decryptors_by_their_group_rather_than_a_hardcoded_list(store: Path) -> None:
    # Enumerating the group is what keeps this correct if CCP adds one.
    with connect(store) as conn:
        assert [d.type_id for d in decryptors(conn)] == [ACCELERANT]


def test_the_scan_universe_is_invention_reachable_items_in_the_chosen_groups(
    store: Path,
) -> None:
    with connect(store) as conn:
        targets = invention_paths(conn, market_group_ids=[1000])

    assert len(targets) == 1
    target = targets[0]
    assert target.t1_blueprint_id == T1_BLUEPRINT
    assert target.t2_blueprint_id == T2_BLUEPRINT
    assert target.product_type_id == T2_RIG
    assert target.product_name == "Medium Core Defense Field Extender II"


def test_a_target_carries_the_bpc_run_count_read_from_its_own_blueprint(store: Path) -> None:
    with connect(store) as conn:
        target = invention_paths(conn, market_group_ids=[1000])[0]

    # One run, because it is a rig — read from the blueprint, not assumed from
    # the category default of ten that modules get.
    assert target.runs_per_bpc == 1
    assert target.base_probability == pytest.approx(0.34)


def test_a_target_carries_its_invention_inputs_and_durations(store: Path) -> None:
    with connect(store) as conn:
        target = invention_paths(conn, market_group_ids=[1000])[0]

    assert target.invention_seconds == 10800
    assert target.manufacturing_seconds == 1200
    # Rig invention burns two datacores of each type, not one as a small module does.
    assert sorted((d.type_id, d.quantity) for d in target.datacores) == [(20412, 2), (20418, 2)]


def test_selecting_a_parent_market_group_includes_its_children(store: Path) -> None:
    # The user picks from the in-game tree, where choosing a branch means the
    # branch, not just the node.
    with connect(store) as conn:
        assert len(invention_paths(conn, market_group_ids=[1001])) == 1


def test_an_unrelated_market_group_yields_nothing(store: Path) -> None:
    with connect(store) as conn:
        assert invention_paths(conn, market_group_ids=[2000]) == ()


def test_lists_manufacturing_materials_at_their_published_quantities(store: Path) -> None:
    with connect(store) as conn:
        materials = manufacturing_materials(conn, T2_BLUEPRINT)

    assert [(m.type_id, m.quantity) for m in materials] == [
        (11484, 1),
        (25617, 6),
        (25619, 6),
        (25625, 3),
    ]
    assert materials[1].name == "Power Circuit"


def test_exposes_the_market_group_tree(store: Path) -> None:
    with connect(store) as conn:
        groups = {g.market_group_id: g for g in market_groups(conn)}

    assert groups[1000].name == "Shield Rigs"
    assert groups[1000].parent_id == 1001
    assert groups[1001].parent_id is None


def test_reads_rig_bonuses_and_their_security_multipliers(store: Path) -> None:
    with connect(store) as conn:
        bonus = rig_bonuses(conn, 37146)

    assert bonus.material_bonus == pytest.approx(-2.0)
    assert bonus.time_bonus == pytest.approx(0.0)
    # The multipliers sit on the rig, not the structure, which is the evidence
    # they scale the rig's bonus only.
    assert bonus.security_multiplier("highsec") == pytest.approx(1.0)
    assert bonus.security_multiplier("lowsec") == pytest.approx(1.9)
    assert bonus.security_multiplier("nullsec") == pytest.approx(2.1)


def test_a_material_whose_type_row_is_missing_is_still_returned(
    store: Path, tmp_path: Path
) -> None:
    # Dropping it would silently understate what the item costs to build.
    with connect(store) as conn:
        conn.execute("DELETE FROM sde_type WHERE type_id = 25617")  # Power Circuit

    with connect(store) as conn:
        materials = manufacturing_materials(conn, T2_BLUEPRINT)

    assert [(m.type_id, m.quantity) for m in materials] == [
        (11484, 1),
        (25617, 6),
        (25619, 6),
        (25625, 3),
    ]
    assert next(m for m in materials if m.type_id == 25617).name == "type 25617"


def test_rig_bonuses_are_hashable_and_immutable(store: Path) -> None:
    with connect(store) as conn:
        bonus = rig_bonuses(conn, 37146)

    assert {bonus}  # a frozen value should be usable as a key
    with pytest.raises(AttributeError):
        bonus.highsec = 99.0  # type: ignore[misc]


def test_a_decryptor_missing_a_modifier_is_skipped_not_fatal(store: Path) -> None:
    # Enumerating the group means a future decryptor appears automatically; one
    # malformed row must not take the whole list down with it.
    with connect(store) as conn:
        conn.execute(
            "INSERT INTO sde_type (type_id, name, group_id, portion_size, published) "
            "VALUES (99999, 'Half-Published Decryptor', 1304, 1, 1)"
        )
        conn.execute("INSERT INTO sde_type_attribute VALUES (99999, 1112, 1.5)")  # probability only

    with connect(store) as conn:
        found = decryptors(conn)

    assert [d.type_id for d in found] == [ACCELERANT]


def test_an_invention_path_without_a_published_probability_is_dropped(store: Path) -> None:
    # Expected blueprint cost divides by the chance, so a path without one
    # cannot be costed; a NULL reaching the cost model would fail far from here.
    with connect(store) as conn:
        conn.execute("DELETE FROM sde_invention_probability")

    with connect(store) as conn:
        assert invention_paths(conn, [1000]) == ()
