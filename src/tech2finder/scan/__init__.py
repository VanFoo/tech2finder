"""The scan engine: the project's primary seam.

A single entry point will take a Production Profile, a market-group selection
and a store, and return a scan result. It performs no I/O of its own —
everything it needs has already been persisted — which is what makes nearly
the whole domain testable in one place, with no network and no clock.

Not implemented yet; see the scan engine ticket.
"""
