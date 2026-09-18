# tech2finder

Find profitable Tech 2 items to manufacture in EVE Online.

Scans whole market-group branches of invention-reachable T2 items and ranks them
by **ISK per Day** — achievable Manufacturing Profit per day for your own
Production Profile — rather than by per-unit margin, which ignores how fast you
can build a thing and whether Jita can absorb it.

[eve-industry.org/calc](https://eve-industry.org/calc/) implements much of this
maths but is no longer maintained and only checks one blueprint at a time.
Scanning and ranking a whole category is the gap this fills.

## Status

Early. The design is complete and the scaffold is in place; the cost model,
ESI sync and UI are not built yet. See the [issues](https://github.com/VanFoo/tech2finder/issues)
for what is being worked on.

## Documentation

- **`CONTEXT.md`** — the domain glossary. Read this first; the code uses these
  terms deliberately and avoids their near-synonyms.
- **`docs/adr/`** — architecture decisions, with the reasoning and the rejected
  alternatives. Worth reading before changing anything that looks odd.
- **`docs/research/industry-formulas.md`** — the EVE industry formulas with
  sources and per-claim confidence levels. **Implement from this, not from
  memory**: the rounding rules and operation order are where implementations
  usually go wrong.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). The devcontainer
installs both.

```bash
uv sync --extra dev          # create .venv and install
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy                  # typecheck (strict)
uv run python -m tech2finder # dev server on http://127.0.0.1:8000
```

### Layout

```
src/tech2finder/
  domain/   plain dataclasses that cross the boundary out of the domain
  scan/     the scan engine — seam 1, the primary test seam
  store/    SQLite connection handling and forward-only migrations
  sync/     everything that talks to ESI — seam 2, over an injectable Transport
  web/      FastAPI views and Jinja2 templates
```

Two test seams, agreed up front:

1. **The scan entry point.** Takes a Production Profile, a selection and a
   store; returns a scan result. No I/O, so nearly the whole domain is testable
   in one place.
2. **The ESI sync layer**, over an injectable `Transport`. Its rate-limit and
   staleness policy is invisible through seam 1 and is asserted against a fake.

Views are tested through FastAPI's test client. They are not a seam: they build
a dataclass and render it, and should contain nothing else.
