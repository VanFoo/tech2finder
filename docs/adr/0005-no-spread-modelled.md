# No buy/sell spread is modelled

Inputs and output are valued at the same basis. ESI daily history carries no buy-side/sell-side split, and the spread is at least as volatile as the spot prices rejected in ADR-0004, so it is not a long-term planning input either.

Output is assumed **sold via sell orders** (listed and waited on), not dumped into standing buy orders. The player tactic of dumping when the spread is narrow is an execution-time decision, not something the ranking tries to predict.

## Consequences

Both **broker fee and sales tax** apply, since listing incurs both where dumping to a buy order would incur only sales tax.

The residual bias is most likely **conservative**. With `A = sell_out − avg_out` and `B = sell_in − avg_in`, modelled profit minus real profit is `B − A`: cost is understated by B (inputs are really bought from sell orders, above average) and revenue is understated by A (output is really listed at sell prices, above average). For T2 items A typically exceeds B, because inputs are liquid minerals, salvage and datacores while the output has the wider spread.
