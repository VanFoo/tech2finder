# Python backend, HTMX frontend, SQLite store

A local web app: Python serving server-rendered templates with HTMX, over SQLite holding both the Fuzzwork SDE dump (already published in that format) and the persisted market cache.

Python was chosen on the maintainer's own fluency, which outweighs the marginal one-language advantages a TypeScript stack would have had. HTMX then cancels that choice's one real drawback: with no JSON API there is no second definition of the cost model's shapes in a frontend language, so nothing can drift.

## Consequences

The implementation must stay **swappable to an SPA later**. Concretely: the cost model and scan-result layer return plain dataclasses, and templates may only render them — no domain arithmetic in a template, no ORM objects in the view. Adding a JSON API then means serialising the same objects at the same seam rather than reworking anything behind it.

Nothing here blocks a public version later. The obstacles to that are per-user Production Profiles and auth, not the language. ESI's error budget is tracked per source IP, which cuts in favour: prices are Jita-only, so market data is identical for every user and one shared cache serves all of them.
