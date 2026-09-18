"""Reading the imported SDE.

Returns plain dataclasses carrying the published numbers. What a run count or a
rig bonus *means* is the cost model's problem; this module only fetches.
"""

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

MANUFACTURING = 1
INVENTION = 8

#: Decryptors are enumerated by group rather than by a hardcoded list of ids,
#: so a new one CCP publishes is picked up by the next import.
DECRYPTOR_GROUP = 1304

# Invention modifiers carried by a decryptor. CCP's typo in 1112 is theirs.
PROBABILITY_MULTIPLIER = 1112
ME_MODIFIER = 1113
TE_MODIFIER = 1114
MAX_RUN_MODIFIER = 1124

# Engineering-rig bonuses, and the multipliers that scale them by space.
RIG_TIME_BONUS = 2593
RIG_MATERIAL_BONUS = 2594
RIG_COST_BONUS = 2595
SECURITY_MULTIPLIER = {"highsec": 2355, "lowsec": 2356, "nullsec": 2357}


@dataclass(frozen=True)
class Material:
    type_id: int
    name: str
    quantity: int


@dataclass(frozen=True)
class Decryptor:
    type_id: int
    name: str
    probability_multiplier: float
    run_modifier: int
    me_modifier: int
    te_modifier: int


@dataclass(frozen=True)
class MarketGroup:
    market_group_id: int
    parent_id: int | None
    name: str


@dataclass(frozen=True)
class RigBonuses:
    type_id: int
    material_bonus: float
    time_bonus: float
    cost_bonus: float
    #: One field per band rather than a dict: a mutable field on a frozen
    #: dataclass is both unhashable and quietly mutable, which are the two
    #: things frozen exists to prevent.
    highsec: float
    lowsec: float
    nullsec: float

    def security_multiplier(self, band: str) -> float:
        try:
            value = getattr(self, band)
        except AttributeError:
            raise KeyError(band) from None
        return float(value)


@dataclass(frozen=True)
class InventionPath:
    """One way of inventing one item: the whole chain, in one row.

    T1 blueprint --invent--> T2 blueprint --manufacture--> the item.

    A product can have **several paths**, and they do not agree. In the current
    SDE 48 products are invented from more than one source blueprint, and every
    one of those differs in probability and run count — T3 subsystems from
    intact, malfunctioning and wrecked relics run 0.26/20, 0.21/10 and 0.14/3
    respectively. So this is deliberately not keyed by product: choosing among
    paths is a decision for the scan engine, in the same way choosing a
    decryptor is, and collapsing them here would silently pick one at random.
    """

    t1_blueprint_id: int
    t2_blueprint_id: int
    product_type_id: int
    product_name: str
    #: Runs on the invented BPC, read from this blueprint rather than assumed
    #: from its category.
    runs_per_bpc: int
    base_probability: float
    invention_seconds: int
    manufacturing_seconds: int
    datacores: tuple[Material, ...]


def decryptors(conn: sqlite3.Connection) -> tuple[Decryptor, ...]:
    rows = conn.execute(
        """
        SELECT t.type_id, t.name,
               MAX(CASE WHEN a.attribute_id = ? THEN a.value END) AS probability,
               MAX(CASE WHEN a.attribute_id = ? THEN a.value END) AS runs,
               MAX(CASE WHEN a.attribute_id = ? THEN a.value END) AS me,
               MAX(CASE WHEN a.attribute_id = ? THEN a.value END) AS te
        FROM sde_type t
        JOIN sde_type_attribute a ON a.type_id = t.type_id
        WHERE t.group_id = ?
        GROUP BY t.type_id, t.name
        ORDER BY t.name
        """,
        (PROBABILITY_MULTIPLIER, MAX_RUN_MODIFIER, ME_MODIFIER, TE_MODIFIER, DECRYPTOR_GROUP),
    ).fetchall()

    # A decryptor missing any of the four modifiers is skipped rather than
    # allowed to raise: the point of enumerating the group is that a new one
    # CCP publishes is picked up automatically, and one malformed row should
    # not take the whole list down with it.
    return tuple(
        Decryptor(
            type_id=r["type_id"],
            name=r["name"],
            probability_multiplier=float(r["probability"]),
            run_modifier=int(r["runs"]),
            me_modifier=int(r["me"]),
            te_modifier=int(r["te"]),
        )
        for r in rows
        if None not in (r["probability"], r["runs"], r["me"], r["te"])
    )


def market_groups(conn: sqlite3.Connection) -> tuple[MarketGroup, ...]:
    rows = conn.execute(
        "SELECT market_group_id, parent_id, name FROM sde_market_group ORDER BY name"
    ).fetchall()
    return tuple(MarketGroup(r["market_group_id"], r["parent_id"], r["name"]) for r in rows)


def rig_bonuses(conn: sqlite3.Connection, type_id: int) -> RigBonuses:
    values = {
        row["attribute_id"]: row["value"]
        for row in conn.execute(
            "SELECT attribute_id, value FROM sde_type_attribute WHERE type_id = ?", (type_id,)
        )
    }
    return RigBonuses(
        type_id=type_id,
        material_bonus=values.get(RIG_MATERIAL_BONUS, 0.0),
        time_bonus=values.get(RIG_TIME_BONUS, 0.0),
        cost_bonus=values.get(RIG_COST_BONUS, 0.0),
        # A rig with no multipliers is a highsec-only structure rig; 1.0 is then
        # the correct scaling everywhere rather than a missing value.
        highsec=values.get(SECURITY_MULTIPLIER["highsec"], 1.0),
        lowsec=values.get(SECURITY_MULTIPLIER["lowsec"], 1.0),
        nullsec=values.get(SECURITY_MULTIPLIER["nullsec"], 1.0),
    )


def manufacturing_materials(conn: sqlite3.Connection, blueprint_id: int) -> tuple[Material, ...]:
    return _materials(conn, blueprint_id, MANUFACTURING)


def invention_paths(
    conn: sqlite3.Connection, market_group_ids: Iterable[int]
) -> tuple[InventionPath, ...]:
    """Every way of inventing an item whose market group is in, or under, the given ones.

    One row per (source blueprint, product) pair, so a product with several
    sources appears several times. See `InventionPath`.
    """
    wanted = list(market_group_ids)
    if not wanted:
        return ()

    placeholders = ", ".join("?" for _ in wanted)
    rows = conn.execute(
        f"""
        WITH RECURSIVE branch(market_group_id) AS (
            SELECT market_group_id FROM sde_market_group
            WHERE market_group_id IN ({placeholders})
            UNION
            SELECT g.market_group_id FROM sde_market_group g
            JOIN branch b ON g.parent_id = b.market_group_id
        )
        SELECT
            invented.blueprint_id      AS t1_blueprint_id,
            invented.product_type_id   AS t2_blueprint_id,
            built.product_type_id      AS product_type_id,
            item.name                  AS product_name,
            invented.quantity          AS runs_per_bpc,
            p.probability              AS base_probability,
            COALESCE(it.seconds, 0)    AS invention_seconds,
            COALESCE(mt.seconds, 0)    AS manufacturing_seconds
        FROM sde_activity_product invented
        JOIN sde_activity_product built
          ON built.blueprint_id = invented.product_type_id AND built.activity_id = ?
        JOIN sde_type item ON item.type_id = built.product_type_id
        JOIN branch ON branch.market_group_id = item.market_group_id
        -- Inner, deliberately: expected blueprint cost divides by the
        -- invention chance, so a path without a published probability cannot
        -- be costed at all. Eight such rows exist in the current SDE, all
        -- structure modules. Dropping them here is better than letting a NULL
        -- reach the cost model and fail far from its cause.
        JOIN sde_invention_probability p
          ON p.blueprint_id = invented.blueprint_id
         AND p.product_type_id = invented.product_type_id
        LEFT JOIN sde_activity_time it
          ON it.blueprint_id = invented.blueprint_id AND it.activity_id = ?
        LEFT JOIN sde_activity_time mt
          ON mt.blueprint_id = invented.product_type_id AND mt.activity_id = ?
        WHERE invented.activity_id = ?
        ORDER BY item.name
        """,
        # Bound in the order the placeholders appear: the CTE's group ids first,
        # then built/invention-time/manufacturing-time/invented activity ids.
        (*wanted, MANUFACTURING, INVENTION, MANUFACTURING, INVENTION),
    ).fetchall()

    datacores = _materials_for(conn, {r["t1_blueprint_id"] for r in rows}, INVENTION)

    return tuple(
        InventionPath(
            t1_blueprint_id=r["t1_blueprint_id"],
            t2_blueprint_id=r["t2_blueprint_id"],
            product_type_id=r["product_type_id"],
            product_name=r["product_name"],
            runs_per_bpc=r["runs_per_bpc"],
            base_probability=r["base_probability"],
            invention_seconds=r["invention_seconds"],
            manufacturing_seconds=r["manufacturing_seconds"],
            datacores=datacores.get(r["t1_blueprint_id"], ()),
        )
        for r in rows
    )


def _materials_for(
    conn: sqlite3.Connection, blueprint_ids: set[int], activity: int
) -> dict[int, tuple[Material, ...]]:
    """Materials for many blueprints at once, to avoid a query per result row."""
    if not blueprint_ids:
        return {}

    placeholders = ", ".join("?" for _ in blueprint_ids)
    rows = conn.execute(
        f"""
        SELECT m.blueprint_id, m.material_type_id, t.name, m.quantity
        FROM sde_activity_material m
        LEFT JOIN sde_type t ON t.type_id = m.material_type_id
        WHERE m.activity_id = ? AND m.blueprint_id IN ({placeholders})
        ORDER BY m.blueprint_id, m.material_type_id
        """,
        (activity, *blueprint_ids),
    ).fetchall()

    grouped: dict[int, list[Material]] = {}
    for r in rows:
        grouped.setdefault(r["blueprint_id"], []).append(
            Material(
                r["material_type_id"], r["name"] or f"type {r['material_type_id']}", r["quantity"]
            )
        )
    return {key: tuple(value) for key, value in grouped.items()}


def _materials(conn: sqlite3.Connection, blueprint_id: int, activity: int) -> tuple[Material, ...]:
    rows: Sequence[sqlite3.Row] = conn.execute(
        """
        SELECT m.material_type_id, t.name, m.quantity
        FROM sde_activity_material m
        -- LEFT, deliberately: a material whose type row is missing from the
        -- dump must still appear. Dropping it would silently understate what
        -- the item costs to build, which is the worst kind of wrong here.
        LEFT JOIN sde_type t ON t.type_id = m.material_type_id
        WHERE m.blueprint_id = ? AND m.activity_id = ?
        ORDER BY m.material_type_id
        """,
        (blueprint_id, activity),
    ).fetchall()
    return tuple(
        Material(r["material_type_id"], r["name"] or f"type {r['material_type_id']}", r["quantity"])
        for r in rows
    )
