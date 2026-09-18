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
from tech2finder.sde.repository import decryptors, invention_paths, manufacturing_materials
from tech2finder.store.bootstrap import bootstrap
from tech2finder.store.connection import connect

#: Anchored to the repository root, not the process cwd: a relative default
#: means running pytest from a subdirectory silently skips this whole file —
#: the one file that would catch CCP reshaping the data under us.
REPO_ROOT = Path(__file__).resolve().parents[2]
DUMP = Path(os.environ.get("TECH2FINDER_SDE", REPO_ROOT / "data" / "sde" / "sde.db"))

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
#: The whole branch, which contains T3 subsystems and their multiple paths.
SHIP_AND_MODULE_MODIFICATIONS = 955
#: Where the Hawk and the Harpy live, both invented from a Merlin blueprint.
#: "Assault Frigates". Note there are two market groups with this name; the
#: Hawk and Harpy sit under this one, via its Caldari child (434).
ASSAULT_FRIGATES = 432


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
        targets = invention_paths(conn, [SHIELD_RIG_MARKET_GROUP])

    target = next(t for t in targets if t.product_type_id == MEDIUM_CORE_DEFENSE_FIELD_EXTENDER_II)

    assert target.runs_per_bpc == 1, "a rig BPC has 1 run, not the 10 a module gets"
    assert target.base_probability == pytest.approx(0.34)
    assert sorted(d.quantity for d in target.datacores) == [2, 2]


def test_selecting_a_branch_pulls_in_its_children(store: Path) -> None:
    # The item sits in Medium Shield Rigs, two levels below Rigs. Picking a
    # branch in the in-game tree has to mean the branch, not just the node.
    with connect(store) as conn:
        shield = invention_paths(conn, [SHIELD_RIG_MARKET_GROUP])
        every_rig = invention_paths(conn, [ALL_RIGS_MARKET_GROUP])

    assert len(shield) > 5
    assert len(every_rig) > len(shield)
    assert all(t.runs_per_bpc >= 1 for t in every_rig)


def test_every_rig_in_the_branch_inverts_at_one_run(store: Path) -> None:
    # The fact that makes invention the binding pipeline for this category.
    with connect(store) as conn:
        targets = invention_paths(conn, [ALL_RIGS_MARKET_GROUP])

    assert {t.runs_per_bpc for t in targets} == {1}


def test_a_product_can_have_several_disagreeing_invention_paths(store: Path) -> None:
    # 48 products in the current SDE are invented from more than one source,
    # and every one of them differs in probability and run count — T3
    # subsystems from intact, malfunctioning and wrecked relics. A caller that
    # keyed by product would silently pick one at random, which is why a row is
    # a path rather than a target.
    with connect(store) as conn:
        paths = invention_paths(conn, [SHIP_AND_MODULE_MODIFICATIONS])

    by_product: dict[int, set[tuple[float, int]]] = {}
    for path in paths:
        by_product.setdefault(path.product_type_id, set()).add(
            (path.base_probability, path.runs_per_bpc)
        )

    disagreeing = {p: v for p, v in by_product.items() if len(v) > 1}
    assert disagreeing, "expected at least one product with differing paths"


def test_one_source_blueprint_can_invent_several_different_products(store: Path) -> None:
    # The mirror of the many-sources case above: a Merlin blueprint invents
    # either a Hawk or a Harpy. 74 of 1113 source blueprints invent more than
    # one product, up to 16 from one, so neither end of the relationship is
    # safe to key by.
    with connect(store) as conn:
        merlin = conn.execute(
            "SELECT type_id FROM sde_type WHERE name = 'Merlin Blueprint'"
        ).fetchone()["type_id"]
        paths = invention_paths(conn, [ASSAULT_FRIGATES])

    from_merlin = {p.product_name: p for p in paths if p.t1_blueprint_id == merlin}

    assert set(from_merlin) == {"Hawk", "Harpy"}
    # Same hull, same datacores, same odds — they differ downstream, in what the
    # T2 item costs to build and what the market pays for it.
    assert sorted(p.base_probability for p in from_merlin.values()) == pytest.approx([0.3, 0.3])
    assert {p.runs_per_bpc for p in from_merlin.values()} == {1}


def test_probability_and_run_count_are_properties_of_the_source_not_the_product(
    store: Path,
) -> None:
    # Across all 74 source blueprints that invent more than one product, neither
    # probability nor run count varies by which product is chosen. So the whole
    # invention leg — odds, runs, datacores — is a property of the source, and
    # sibling products differ only downstream, in their bill of materials and
    # what the market pays.
    #
    # This is an observed property of the SDE, not a documented CCP guarantee,
    # which is exactly why it is asserted here: anything built on it should
    # break loudly if CCP changes it.
    with connect(store) as conn:
        varying = conn.execute(
            """
            SELECT count(*) FROM (
                SELECT blueprint_id FROM sde_invention_probability
                GROUP BY blueprint_id
                HAVING count(*) > 1 AND count(DISTINCT probability) > 1
            )
            """
        ).fetchone()[0]
        varying_runs = conn.execute(
            """
            SELECT count(*) FROM (
                SELECT blueprint_id FROM sde_activity_product WHERE activity_id = 8
                GROUP BY blueprint_id
                HAVING count(*) > 1 AND count(DISTINCT quantity) > 1
            )
            """
        ).fetchone()[0]

    assert varying == 0, "probability is expected to be a property of the source blueprint"
    assert varying_runs == 0, "run count is expected to be a property of the source blueprint"
