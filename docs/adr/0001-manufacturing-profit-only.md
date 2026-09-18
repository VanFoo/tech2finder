# Manufacturing Profit only — trading is a separate domain

This tool calculates one thing: the margin between an item's build cost and its sale price, with everything priced at a single hub (Jita). Cross-hub price differences are Trade Profit and are out of scope, and so is trading behaviour generally — inventory awaiting sale, cash flow, time-to-sell, capital locked in listed goods, order strategy, relisting and fee minimisation.

The dividing line: if a question is about *how ISK moves through the market* rather than *what it costs to build a thing*, it belongs to the trade domain and not here.

## Consequences

Broker fee and sales tax are both charged against the sale, but as **flat configured inputs, not levers** — the tool never optimises them. Pricing at a single hub also means the tool never needs multi-region market data, which is a large simplification in the data layer.
