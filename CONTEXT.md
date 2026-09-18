# tech2finder

A personal tool to find profitable Tech2 items to manufacture in EVE Online.

## Language

**Manufacturing Profit**:
The margin between an item's build cost (materials, invention, fees) and its market sell price, both priced at the same trade hub. This is the only kind of profit this tool calculates.
_Avoid_: Profit (ambiguous — always qualify as Manufacturing Profit)

**Valuation Basis**:
The price series everything is valued at: the **median of ESI daily history `average` over a configurable window, default 15 days**, with the interquartile range reported alongside as a volatility indicator. Never a live order-book price — the tool plans production over long horizons, where spot prices are both manipulable and volatile.
Inputs and output are valued at the *same* basis: no buy/sell spread is modelled, because daily history carries no buy/sell split and the spread is itself too volatile to plan on. The residual bias is most likely conservative, since the output's spread is typically wider than that of liquid inputs like minerals, salvage and datacores.
_Avoid_: Spot price, current price, top of book (all name the thing this deliberately is not)

**Trade Profit**:
Margin captured by buying an item in one region and selling it in another (arbitrage). Explicitly out of scope — this tool only prices everything at a single hub (Jita), so cross-region price differences never enter the calculation.
Trading concerns generally are outside this tool's subject: inventory held awaiting sale, cash flow, time-to-sell and capital locked in listed goods are all market behaviour, not build cost. The dividing line: if a question is about *how ISK moves through the market* rather than *what it costs to build a thing*, it belongs to the trade domain and not here.
_Avoid_: Arbitrage profit, regional profit

**Invention**:
The process of turning a T1 blueprint copy into a T2 blueprint copy by consuming datacores (and optionally a decryptor) on a roll that succeeds with some probability. The only way this tool assumes a T2 blueprint is obtained, so every T2 blueprint carries a probability-weighted expected cost.
_Avoid_: Research (means something else in EVE), copying

**T2 BPO**:
An original T2 blueprint, obtainable only from long-retired lottery drops. Out of scope entirely — this tool never models a zero-cost blueprint.

**Production Profile**:
The set of player- and place-specific inputs that a Manufacturing Profit figure depends on: invention-relevant skills, facility and its ME/TE rigs, facility tax, and market-fee rates (broker fee, sales tax). Two players get different Manufacturing Profit for the same item because they have different Production Profiles. Stored as defaults in a TOML config file and overridable per run in the UI; an override is ephemeral unless explicitly saved as the new default.
_Avoid_: Settings, character sheet, environment

**System Cost Index**:
The live per-system industry index that scales job installation fees. Deliberately *not* part of the Production Profile — it is fetched data, never a configured value, so a stale number can't silently skew every result.

**Scenario**:
One evaluation of the cost model under a given Production Profile. Re-running with a tweaked profile produces a new Scenario, which is what the UI's override controls are for.
_Avoid_: Simulation (implies randomness in the core; there is none — invention is modeled as an expected value, not a roll)

**Demand Cutoff**:
A configurable threshold that removes items whose Jita demand is too thin to sell into, applied as a *filter* before ranking rather than as a cap on the ranked number. Three thresholds, all configurable, and an item must clear all of them: a **relative** one (projected daily production must not exceed a configured share, default ~20%, of Jita's daily traded volume), an **absolute** one (a minimum units/day traded, which stops a near-dead item from passing the relative test simply by being small), and a **minimum days of price history** (below it the item is excluded; just above it, it is ranked with a short-window flag). Items dropped by any of the three appear in an "excluded, and why" list beside the ranking, since a silent exclusion is indistinguishable from an unprofitable item. Chosen over folding market capacity into the profit figure because production is spread across many items rather than maxed on one — the tool's job is to exclude what can't be sold, not to model dumping a single item. Stored as a default in config, overridable per run in the UI.
_Avoid_: Saturation cap, absorbable volume (both imply the ranking number is reduced by market size; it is not)

**Throughput**:
The daily unit output the Production Profile can sustain for a given item, computed as `min(BPC supply rate from invention, manufacturing capacity)` and projected at **full devotion** — as if every job slot were committed to that one item. The binding side of the `min` is reported, so a result reads "invention-bound" or "manufacturing-bound". Copying is never a constraint: T1 BPCs are treated as infinite and free.
_Avoid_: Capacity (ambiguous — slots, or output?), production rate

**ISK per Day**:
Achievable Manufacturing Profit per day at full-devotion Throughput. The tool's **primary ranking metric** — the list sorts by this.
_Avoid_: Profit (see Manufacturing Profit), daily yield

**ROI per Day**:
ISK per Day divided by **average capital employed** — cost per job multiplied by the number of jobs in flight, which makes the figure duration-aware: a short job recycles the same ISK many times a day and scores higher for it. Shown alongside ISK per Day as a secondary column, never as the sort key.
_Avoid_: Return, margin (margin is a per-unit ratio and ignores time entirely)
