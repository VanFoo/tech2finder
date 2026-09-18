"""Reading the EVE Static Data Export.

The SDE is a foreign schema: published by CCP, repackaged by Fuzzwork, read by
this project and never owned by it. The import therefore translates names and
nothing else — no interpretation, no derived values. Working out what a run
count or a rig bonus *means* is the cost model's job, and keeping that line
sharp is what lets a later SDE change be absorbed here alone.
"""
