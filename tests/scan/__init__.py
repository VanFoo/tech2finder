"""Seam 1: the scan entry point.

Material and time formulas, invention expected value, decryptor selection,
Throughput and which pipeline binds, ISK per Day and ROI per Day, all three
Demand Cutoffs and the contents of the exclusion list are all asserted here,
through the returned scan result rather than at a per-formula seam.

Prefer fixtures built from the real verified items in
`docs/research/industry-formulas.md` over invented ones: a failure should mean
the maths is wrong, not that the fixture was unrealistic.
"""
