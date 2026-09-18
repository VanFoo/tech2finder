# Invention is modelled as expected value, not simulated

Expected blueprint cost is `attempt cost / invention chance`, amortised over the resulting BPC's runs. There is no Monte Carlo and no RNG anywhere in the core.

This yields one comparable number per item that a user can check by hand — which matters for a tool whose output is a ranking the user must trust. Variance analysis remains possible later as a bolt-on over the same deterministic cost model.

## Consequences

The word *simulation* is deliberately avoided in favour of **Scenario** (see `CONTEXT.md`): one evaluation of the cost model under a given Production Profile, with no randomness implied.
