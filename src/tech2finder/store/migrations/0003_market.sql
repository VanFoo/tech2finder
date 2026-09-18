-- Market data fetched from ESI.
--
-- Persisted and reused across runs because ESI is the bottleneck: re-running a
-- Scenario with a tweaked Production Profile recomputes locally and touches the
-- network not at all.

-- One row per type per day that actually traded. ESI emits no row for a day
-- with no trades — never a row with volume 0 — so absence here means "did not
-- trade", and the row count within a window is itself a liquidity signal.
CREATE TABLE market_history (
    type_id      INTEGER NOT NULL,
    date         TEXT    NOT NULL,   -- ISO date, as published
    average      REAL    NOT NULL,
    highest      REAL    NOT NULL,
    lowest       REAL    NOT NULL,
    order_count  INTEGER NOT NULL,
    volume       INTEGER NOT NULL,
    PRIMARY KEY (type_id, date)
);
CREATE INDEX market_history_date ON market_history (date);

-- CCP's adjusted price, which job installation fees are assessed on. Not a
-- market price and not derivable from one. Absent is not zero: an item with no
-- published adjusted price cannot have its job fee computed.
CREATE TABLE adjusted_price (
    type_id         INTEGER PRIMARY KEY,
    adjusted_price  REAL,
    average_price   REAL
);

-- The live System Cost Index, read and never computed: CCP made the published
-- formula more volatile in 2023 and never published a replacement.
CREATE TABLE system_cost_index (
    solar_system_id  INTEGER NOT NULL,
    activity         TEXT    NOT NULL,
    cost_index       REAL    NOT NULL,
    PRIMARY KEY (solar_system_id, activity)
);

-- When each resource was last fetched, and the earliest ESI permits asking
-- again. `expires_at` is a floor on re-fetching, never a trigger: data is held
-- as long as it stays useful, which for a long-term planning tool is well past
-- its cache lifetime.
CREATE TABLE esi_fetch (
    resource    TEXT PRIMARY KEY,   -- 'history:<type_id>', 'prices', 'systems'
    fetched_at  TEXT NOT NULL,
    expires_at  TEXT
);
