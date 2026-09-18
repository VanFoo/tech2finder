"""Checks the import against the published SDE rather than a fixture.

Skipped unless a real dump is present, so the suite stays hermetic and fast.
Point TECH2FINDER_SDE at one, or run `python -m tech2finder.sde`, to enable it.

The values asserted here are the ones verified independently in
`docs/research/industry-formulas.md`. This is the test that would catch CCP
reshaping the data under us, which no synthetic fixture can.
"""

import os
from pathlib import Path

import pytest

from tech2finder.sde.importer import import_sde
from tech2finder.sde.repository import decryptors, invention_targets, manufacturing_materials
from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect

DUMP = Path(os.environ.get("TECH2FINDER_SDE", "data/sde/sde.db"))

pytestmark = pytest.mark.skipif(
    not DUMP.is_file(), reason=f"no SDE dump at {DUMP}; run `python -m tech2finder.sde`"
)

MEDIUM_CORE_DEFENSE_FIELD_EXTENDER_II = 31796
T2_BLUEPRINT = 31797
#: "Shield Rigs", the branch holding Medium Shield Rigs (1235) where the test
#: item lives. Selecting the branch must pull in its children.
SHIELD_RIG_MARKET_GROUP = 965
#: "Rigs", one level higher again.
ALL_RIGS_MARKET_GROUP = 1111


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("real") / "store.db"
    bootstrap(path)
    with connect(path) as conn:
        import_sde(conn, DUMP)
    return path


def test_reproduces_the_verified_bill_of_materials(store: Path) -> None:
    with connect(store) as conn:
        materials = manufacturing_materials(conn, T2_BLUEPRINT)

    assert {(m.name, m.quantity) for m in materials} == {
        ("Power Circuit", 6),
        ("Logic Circuit", 6),
        ("Enhanced Ward Console", 3),
        ("R.A.M.- Shield Tech", 1),
    }


def test_the_t2_rig_needs_no_intermediate_components(store: Path) -> None:
    # ADR-0009's buy-everything decision rests on this.
    with connect(store) as conn:
        materials = manufacturing_materials(conn, T2_BLUEPRINT)
        groups = {
            conn.execute(
                "SELECT group_id FROM sde_type WHERE type_id = ?", (m.type_id,)
            ).fetchone()[0]
            for m in materials
        }

    assert groups == {754, 332}, "salvaged materials and one tool, nothing manufactured"


def test_all_eight_decryptors_carry_the_verified_modifiers(store: Path) -> None:
    with connect(store) as conn:
        found = {d.name: d for d in decryptors(conn)}

    assert len(found) == 8

    accelerant = found["Accelerant Decryptor"]
    assert (
        accelerant.probability_multiplier,
        accelerant.run_modifier,
        accelerant.me_modifier,
        accelerant.te_modifier,
    ) == pytest.approx((1.2, 1, 2, 10))

    augmentation = found["Augmentation Decryptor"]
    assert (
        augmentation.probability_multiplier,
        augmentation.run_modifier,
        augmentation.me_modifier,
        augmentation.te_modifier,
    ) == pytest.approx((0.6, 9, -2, 2))


def test_rigs_invent_at_one_run_per_bpc_and_two_datacores_of_each_type(store: Path) -> None:
    with connect(store) as conn:
        targets = invention_targets(conn, [SHIELD_RIG_MARKET_GROUP])

    target = next(t for t in targets if t.product_type_id == MEDIUM_CORE_DEFENSE_FIELD_EXTENDER_II)

    assert target.runs_per_bpc == 1, "a rig BPC has 1 run, not the 10 a module gets"
    assert target.base_probability == pytest.approx(0.34)
    assert sorted(d.quantity for d in target.datacores) == [2, 2]


def test_selecting_a_branch_pulls_in_its_children(store: Path) -> None:
    # The item sits in Medium Shield Rigs, two levels below Rigs. Picking a
    # branch in the in-game tree has to mean the branch, not just the node.
    with connect(store) as conn:
        shield = invention_targets(conn, [SHIELD_RIG_MARKET_GROUP])
        every_rig = invention_targets(conn, [ALL_RIGS_MARKET_GROUP])

    assert len(shield) > 5
    assert len(every_rig) > len(shield)
    assert all(t.runs_per_bpc >= 1 for t in every_rig)


def test_every_rig_in_the_branch_inverts_at_one_run(store: Path) -> None:
    # The fact that makes invention the binding pipeline for this category.
    with connect(store) as conn:
        targets = invention_targets(conn, [ALL_RIGS_MARKET_GROUP])

    assert {t.runs_per_bpc for t in targets} == {1}
