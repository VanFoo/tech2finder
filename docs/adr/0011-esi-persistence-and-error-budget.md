# Persist ESI data; treat `Expires` as a floor and the error budget as a hard limit

ESI is the performance bottleneck, so fetched market data is written to a local store and reused across runs. Static data comes from Fuzzwork's prebuilt SQLite SDE dump.

**`Expires` is a lower bound on refetching, never a trigger.** The tool never refetches sooner than the header allows, including on a manual refresh, but is free to hold data far longer — this is a long-term planning tool, so market data stays relevant well past its cache lifetime. There is no TTL-driven auto-refresh.

**Past daily history is immutable**: a record for a closed date never changes, so only the trailing edge of the series is ever refetched. Staleness for history means "how many days behind is the newest row", not "how old is the cached response".

## Consequences

A category scan costs one history call per `type_id`, so the first scan of a category is a few hundred requests and every later one is cheap.

Three ESI feeds are needed, and only the first scales per item:

- `/markets/{region_id}/history/` — the Valuation Basis (ADR-0004). **One call per `type_id`.**
- `/markets/prices/` — CCP's `adjusted_price`, which job installation fees are assessed on rather than market price. **One call returns every type.**
- `/industry/systems/` — the System Cost Index. **One call returns every system.** The published index formula was made more volatile by CCP in 2023 with no replacement published, so this value is read, never computed.

The last two cost effectively nothing against the error budget, so the concurrency discipline above is governed entirely by the per-item history calls.

Request concurrency is governed by the **error budget, not a fixed number**: N requests in flight are N simultaneous potential errors, and being locked out is unacceptable. `X-ESI-Error-Limit-Remain` and `-Reset` are read on every response, in-flight requests are capped at `min(configured concurrency, remaining − safety floor)`, and the scan halts and waits for the reset window when the budget runs low. There is a **hard ceiling of 15 concurrent requests**, which the budget-derived cap may only lower, never raise.

Re-running a Scenario with a tweaked Production Profile costs no network at all — the cost model recomputes locally while the market data stays put.
