# FastAPI with Jinja2 templates

ADR-0012 committed to Python and a server-rendered HTMX frontend but named no framework. The framework is FastAPI, rendering Jinja2 templates.

Three things decided it, in order of weight:

**The sync layer is the demanding module.** Fetching market history is I/O-bound concurrency against a live error budget (ADR-0011), where getting the bounded-concurrency logic wrong means an API lockout. FastAPI is async-native, so that module is written in the idiom it wants rather than against the grain with threads.

**An ORM would be a liability here.** The SDE is a 136 MB prebuilt database with a schema this project reads and never owns. A framework whose ORM expects to define and migrate the schema would be bypassed for precisely the data that matters. FastAPI imposes no ORM.

**It carries ADR-0012's escape hatch.** That ADR records type drift between a Python cost model and a future frontend as the known cost of choosing Python, and names generated types from an API schema as the mitigation. FastAPI produces OpenAPI the moment JSON routes are added, so the mitigation is already in the box rather than being work to bolt on.

## Considered options

**Django** was the real alternative — its admin would be genuinely useful for eyeballing imported SDE data. Rejected because its ORM's ownership of the schema fits badly with a foreign prebuilt dump, and its async story is the weaker one for the module that most needs it.

**Flask** is the smallest thing to learn, but synchronous: the bounded-concurrency discipline of ADR-0011 would be threads rather than asyncio, which is workable but more error-prone in the one module where an error means being locked out of ESI.

## Consequences

Config, migrations and templating wiring are assembled rather than inherited. That is the price of not carrying a schema-owning ORM, and it is small at this project's size.

HTMX is unaffected by the choice — it works identically under all three candidates.
