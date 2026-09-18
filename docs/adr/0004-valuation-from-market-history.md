# Value everything from daily market history, not live order books

All prices come from the **median of ESI daily history `average` over a configurable window (default 15 days)**, with the interquartile range reported alongside as a volatility indicator. Live order-book prices are not used for valuation at all.

This is a long-term planning tool. Top-of-book prices are trivially manipulated — a single small order moves them — and fluctuate far faster than a production decision plays out. A median over days is robust to both.

## Considered options

A **volume-weighted mean** was rejected: weighting by daily volume better reflects an achievable price, but it hands a single high-volume manipulated day proportionally more influence, which is the exact failure mode being avoided.

## Consequences

A reader expecting live prices will find none — this is deliberate, not an unfinished feature. It also means the tool cannot answer "what can I sell this for right now", and is not trying to.
