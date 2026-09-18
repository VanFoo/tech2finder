# Demand enters as a filter, not as a cap on the ranked number

Items whose Jita demand is too thin are **removed before ranking**; the ranked ISK/day figure itself is never reduced by market size. Three configurable cutoffs apply, and an item must clear all of them: a relative share test (projected daily output as a share of daily traded volume, default ~20%), an absolute minimum units/day (default 10), and a minimum number of days of price history (default: the full 15-day window).

Capping throughput by absorbable market volume was considered and rejected: production is deliberately spread across many items so as not to crash any one market, which makes "how much of item X could I dump" the wrong question. The tool only needs to exclude what cannot be sold.

## Consequences

The relative test alone has a hole — 20% of nearly nothing is still nothing — which is why the absolute floor exists alongside it. That floor is deliberately **low**: its only job is removing items that barely trade, leaving the relative test to do the real filtering. Two filters doing distinct jobs stay independently tunable; a high absolute floor would duplicate the relative test and make either one hard to reason about. A floor set too low shows junk that can be eyeballed, where one set too high hides items silently.

The history threshold defaults to the **full valuation window**, so an item must have traded on all 15 days to be ranked. Consequence: the "short window" flag is dormant at the default and only becomes meaningful if the threshold is lowered. Consequence worth watching: if ESI history returns rows only for days that actually traded — to be verified — then this threshold doubles as a sporadicity filter, catching the item that averages well because it sold once in bulk and nothing since.

Because three independent filters can drop an item, the UI shows an **"excluded, and why" list** next to the ranking. A silent exclusion is indistinguishable from an unprofitable item, and a threshold the user cannot see firing cannot be tuned.
