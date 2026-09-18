# Demand enters as a filter, not as a cap on the ranked number

Items whose Jita demand is too thin are **removed before ranking**; the ranked ISK/day figure itself is never reduced by market size. Three configurable cutoffs apply, and an item must clear all of them: a relative share test (projected daily output as a share of daily traded volume, default ~20%), an absolute minimum units/day, and a minimum number of days of price history.

Capping throughput by absorbable market volume was considered and rejected: production is deliberately spread across many items so as not to crash any one market, which makes "how much of item X could I dump" the wrong question. The tool only needs to exclude what cannot be sold.

## Consequences

The relative test alone has a hole — 20% of nearly nothing is still nothing — which is why the absolute floor exists alongside it.

Because three independent filters can drop an item, the UI shows an **"excluded, and why" list** next to the ranking. A silent exclusion is indistinguishable from an unprofitable item, and a threshold the user cannot see firing cannot be tuned.
