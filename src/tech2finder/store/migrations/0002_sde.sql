-- The subset of the EVE Static Data Export this project reads.
--
-- Columns are renamed to this project's conventions, but the data is otherwise
-- copied as published: the SDE is a foreign schema we read and never own, so
-- interpretation belongs in the cost model, not in the import.
--
-- Tables are copied whole rather than filtered. They are small (the largest is
-- a few hundred thousand rows) and filtering now would mean a re-import later
-- the first time a formula needs a column that was left behind.

CREATE TABLE sde_type (
    type_id          INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    group_id         INTEGER NOT NULL,
    market_group_id  INTEGER,
    portion_size     INTEGER NOT NULL DEFAULT 1,
    published        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE sde_market_group (
    market_group_id  INTEGER PRIMARY KEY,
    parent_id        INTEGER,
    name             TEXT    NOT NULL
);
CREATE INDEX sde_market_group_parent ON sde_market_group (parent_id);

CREATE TABLE sde_blueprint (
    blueprint_id          INTEGER PRIMARY KEY,
    max_production_limit  INTEGER NOT NULL
);

CREATE TABLE sde_activity_time (
    blueprint_id  INTEGER NOT NULL,
    activity_id   INTEGER NOT NULL,
    seconds       INTEGER NOT NULL,
    PRIMARY KEY (blueprint_id, activity_id)
);

CREATE TABLE sde_activity_material (
    blueprint_id      INTEGER NOT NULL,
    activity_id       INTEGER NOT NULL,
    material_type_id  INTEGER NOT NULL,
    quantity          INTEGER NOT NULL,
    PRIMARY KEY (blueprint_id, activity_id, material_type_id)
);

-- For invention (activity 8) the product is the T2 *blueprint*, not the T2
-- item, and `quantity` is the run count of the resulting BPC. Reading it here
-- is what keeps run counts per-blueprint rather than assumed from a category.
CREATE TABLE sde_activity_product (
    blueprint_id     INTEGER NOT NULL,
    activity_id      INTEGER NOT NULL,
    product_type_id  INTEGER NOT NULL,
    quantity         INTEGER NOT NULL,
    PRIMARY KEY (blueprint_id, activity_id, product_type_id)
);
CREATE INDEX sde_activity_product_product ON sde_activity_product (product_type_id, activity_id);

CREATE TABLE sde_invention_probability (
    blueprint_id     INTEGER NOT NULL,
    product_type_id  INTEGER NOT NULL,
    probability      REAL    NOT NULL,
    PRIMARY KEY (blueprint_id, product_type_id)
);

CREATE TABLE sde_type_attribute (
    type_id       INTEGER NOT NULL,
    attribute_id  INTEGER NOT NULL,
    value         REAL    NOT NULL,
    PRIMARY KEY (type_id, attribute_id)
);
