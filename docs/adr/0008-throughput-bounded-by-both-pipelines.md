# Throughput is bounded by both invention and manufacturing

Daily output is `min(BPC supply rate from invention, manufacturing capacity)`, and the binding side is reported as a diagnostic so a result reads "invention-bound" or "manufacturing-bound". EVE runs manufacturing and science slots as separate pools, so the two pipelines run concurrently — a serialised "invention time + build time" cycle would be wrong arithmetic.

Assuming BPCs are always on hand would overstate output for exactly the items whose invention is slow or low-yield, which is where the interesting errors live.

## Consequences

**T1 BPCs are treated as infinite and free.** Copying is done on alpha characters, of which a player can have effectively unlimited, so copy time, copy slots and T1 BPO capital are not modelled at all and copying can never be the binding constraint.

Invented BPC run counts make this concrete: modules come out at 10 runs, but **ships and rigs come out at 1**, and rig invention consumes two datacores of each type rather than one. For the starting category, invention is therefore very likely the binding pipeline — modelling manufacturing slots alone would have overstated rig throughput by close to an order of magnitude. (Read run counts per blueprint from the SDE rather than assuming the category default.)

**One character.** Slot counts come from a single skill set in the Production Profile; scaling to more characters is done by the user multiplying the result, which sidesteps mixed skill levels rather than modelling them.
