# Buy every input; never model building intermediates

All materials — minerals, salvage, components, datacores, decryptors — are priced at the Valuation Basis. Nothing below the final item is manufactured.

T1 manufacturing is highly contested, and many producers self-mine and treat minerals as free, so building T1 inputs is not competitive when costed at market. Reactions and PI materials are difficult to run at all.

## Consequences

Manufacturing slots serve the final item only, which keeps ADR-0008's `min(...)` to two terms rather than growing a component tier that would compete for the same slots and multiply the decryptor search across a tree.

Verified against blueprint bills of materials: **T2 rigs need no intermediate components at all** — a Medium Core Defense Field Extender II is salvage (Power Circuit, Logic Circuit, Enhanced Ward Console) plus one R.A.M. tool. So for the starting category this decision costs nothing. It starts to matter when the tool is pointed at T2 modules, which *do* consume their T1 counterpart.

Separate calculators for reaction and PI chains are plausible future work, deliberately not part of this tool.
