# Rank by ISK per day, projected at full devotion

The primary ranking metric is **absolute Manufacturing Profit in ISK per day**. Per-unit profit and margin % are insufficient: both ignore how fast an item can actually be produced. ROI per day — ISK per day over average capital employed (cost per job × jobs in flight) — is shown as a secondary column, never as the sort key.

Each item is projected **as if every job slot were devoted to it alone**. The user composes a portfolio manually from the ranking; the tool does not model a split.

## Consequences

Full devotion makes the Demand Cutoff's share test (ADR-0007) **pessimistic** — it measures the footprint of an item you might only produce part-time, and will exclude some items you could in fact have sold. The share threshold is configurable to compensate.
