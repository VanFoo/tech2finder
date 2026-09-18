"""Builds a miniature SDE dump with the real column names and real values.

Tests run against this rather than the published 136 MB dump, so they are fast
and hermetic. The rows are the Medium Core Defense Field Extender II chain
verified in `docs/research/industry-formulas.md`, so a failure here means the
import is wrong rather than that a fixture was invented badly.
"""

import sqlite3
from pathlib import Path

MANUFACTURING = 1
INVENTION = 8

#: The T1 rig blueprint that invents the T2 one.
T1_BLUEPRINT = 31791
#: The T2 rig blueprint it invents, which manufactures the T2 rig.
T2_BLUEPRINT = 31797
#: Medium Core Defense Field Extender II, the item itself.
T2_RIG = 31796

ACCELERANT = 34201
DECRYPTOR_GROUP = 1304
RIG_GROUP = 1826


def build(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE invTypes (
            typeID INTEGER PRIMARY KEY, groupID INTEGER, typeName TEXT,
            portionSize INTEGER, published INTEGER, marketGroupID INTEGER
        );
        CREATE TABLE invMarketGroups (
            marketGroupID INTEGER PRIMARY KEY, parentGroupID INTEGER,
            marketGroupName TEXT, hasTypes INTEGER
        );
        CREATE TABLE industryBlueprints (typeID INTEGER PRIMARY KEY, maxProductionLimit INTEGER);
        CREATE TABLE industryActivity (typeID INTEGER, activityID INTEGER, time INTEGER);
        CREATE TABLE industryActivityMaterials (
            typeID INTEGER, activityID INTEGER, materialTypeID INTEGER, quantity INTEGER
        );
        CREATE TABLE industryActivityProducts (
            typeID INTEGER, activityID INTEGER, productTypeID INTEGER, quantity INTEGER
        );
        CREATE TABLE industryActivityProbabilities (
            typeID INTEGER, activityID INTEGER, productTypeID INTEGER, probability REAL
        );
        CREATE TABLE dgmTypeAttributes (
            typeID INTEGER, attributeID INTEGER, valueInt INTEGER, valueFloat REAL
        );
        """
    )

    conn.executemany(
        "INSERT INTO invTypes VALUES (?, ?, ?, ?, ?, ?)",
        [
            (T2_RIG, RIG_GROUP, "Medium Core Defense Field Extender II", 1, 1, 1000),
            (T1_BLUEPRINT, 105, "Medium Core Defense Field Extender I Blueprint", 1, 1, None),
            (T2_BLUEPRINT, 105, "Medium Core Defense Field Extender II Blueprint", 1, 1, None),
            (25617, 754, "Power Circuit", 1, 1, 2000),
            (25619, 754, "Logic Circuit", 1, 1, 2000),
            (25625, 754, "Enhanced Ward Console", 1, 1, 2000),
            (11484, 332, "R.A.M.- Shield Tech", 1, 1, 2000),
            (20412, 333, "Datacore - Hydromagnetic Physics", 1, 1, 2000),
            (20418, 333, "Datacore - Quantum Physics", 1, 1, 2000),
            (ACCELERANT, DECRYPTOR_GROUP, "Accelerant Decryptor", 1, 1, 3000),
            (37146, RIG_GROUP, "Standup M-Set Basic Medium Ship Manufacturing ME I", 1, 1, 4000),
        ],
    )
    conn.executemany(
        "INSERT INTO invMarketGroups VALUES (?, ?, ?, ?)",
        [
            (1000, 1001, "Shield Rigs", 1),
            (1001, None, "Ship Modifications", 0),
            (2000, None, "Salvaged Materials", 1),
            (3000, None, "Decryptors", 1),
            (4000, None, "Structure Modifications", 1),
        ],
    )
    conn.executemany(
        "INSERT INTO industryBlueprints VALUES (?, ?)",
        [(T1_BLUEPRINT, 300), (T2_BLUEPRINT, 1)],
    )
    conn.executemany(
        "INSERT INTO industryActivity VALUES (?, ?, ?)",
        [(T2_BLUEPRINT, MANUFACTURING, 1200), (T1_BLUEPRINT, INVENTION, 10800)],
    )
    conn.executemany(
        "INSERT INTO industryActivityMaterials VALUES (?, ?, ?, ?)",
        [
            (T2_BLUEPRINT, MANUFACTURING, 25617, 6),
            (T2_BLUEPRINT, MANUFACTURING, 25619, 6),
            (T2_BLUEPRINT, MANUFACTURING, 25625, 3),
            (T2_BLUEPRINT, MANUFACTURING, 11484, 1),
            (T1_BLUEPRINT, INVENTION, 20412, 2),  # Datacore - Hydromagnetic Physics
            (T1_BLUEPRINT, INVENTION, 20418, 2),  # Datacore - Quantum Physics
        ],
    )
    conn.executemany(
        "INSERT INTO industryActivityProducts VALUES (?, ?, ?, ?)",
        [
            (T2_BLUEPRINT, MANUFACTURING, T2_RIG, 1),
            # Invention yields the T2 *blueprint*; quantity is the BPC run count.
            (T1_BLUEPRINT, INVENTION, T2_BLUEPRINT, 1),
        ],
    )
    conn.executemany(
        "INSERT INTO industryActivityProbabilities VALUES (?, ?, ?, ?)",
        [(T1_BLUEPRINT, INVENTION, T2_BLUEPRINT, 0.34)],
    )
    conn.executemany(
        "INSERT INTO dgmTypeAttributes VALUES (?, ?, ?, ?)",
        [
            (ACCELERANT, 1112, None, 1.2),  # probability multiplier
            (ACCELERANT, 1113, None, 2.0),  # ME modifier
            (ACCELERANT, 1114, None, 10.0),  # TE modifier
            (ACCELERANT, 1124, None, 1.0),  # max run modifier
            (37146, 2594, None, -2.0),  # material bonus
            (37146, 2355, None, 1.0),  # hiSecModifier
            (37146, 2356, None, 1.9),  # lowSecModifier
            (37146, 2357, None, 2.1),  # nullSecModifier
            (37146, 2095, 32, None),  # an int-valued attribute, to prove the coalesce
        ],
    )
    conn.commit()
    conn.close()
    return path
