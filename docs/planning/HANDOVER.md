# tech2finder — session handover

Written 2026-09-18. Read this first when picking the project back up.

## Where the project stands

Design complete and three tickets built. A 39-decision grilling interview closed with an empty frontier,
the decisions became 14 ADRs, the industry maths was researched against primary sources, and the spec was
split into ten GitHub issues with live dependencies.

**Built so far — #2, #3, #5, all on `main` and pushed:**

- **Scaffold** — FastAPI + Jinja2 over SQLite, forward-only migrations, and both test seams in place.
- **SDE import** — downloads Fuzzwork's dump, imports the subset used (769k rows, 25 MB from a 475 MB
  dump), exposes it as dataclasses. Re-running takes 1.8s when unchanged.
- **ESI sync** — three endpoints, the `Expires` floor, and the error budget governing concurrency.

**127 tests, ruff clean, mypy strict clean.** Everything is committed and pushed; the working tree is clean.

### What is actually runnable

```bash
./scripts/setup.sh                                  # environment, idempotent
uv run python -m tech2finder.sde                    # download + import the SDE
export TECH2FINDER_USER_AGENT="tech2finder/0.1 (you@yourdomain.com)"
uv run python -m tech2finder.sync --market-group 965   # fetch market data
uv run python -m tech2finder                        # status page on :8000
```

`data/` is gitignored and holds the SDE dump and the store. Deleting it costs one re-import.

### Frontier

**#4 (config and Production Profile)** and **#6 (Valuation Basis)** are both ready and independent.
#6 is the smaller and more natural next step: the data it needs is already in the store, and it is
median + IQR over a 15-day window, with the row count doubling as the liquidity signal.

## Where things live

| What | Where | Status |
|---|---|---|
| Glossary / domain language | `CONTEXT.md` | committed |
| Architecture decisions (14) | `docs/adr/0001`–`0014` | committed |
| Code | `src/tech2finder/`, `tests/` | committed |
| EVE industry formulas | `docs/research/industry-formulas.md` | committed |
| Agent conventions | `docs/agents/` | committed |
| This handover | `docs/planning/HANDOVER.md` | committed |

| Spec and tickets | GitHub issues #1–#10 | #2, #3, #5 closed |

The grilling progress file (`docs/planning/grilling-progress.md`) was deleted once its content reached
the ADRs. If the reasoning behind a decision is not in an ADR, it is gone — so add to the ADR rather than
assuming there is a fuller record elsewhere.

## Working agreements with the user

These are user preferences, not inferences. They held throughout the design session and should be assumed
to still hold:

- **Ask one question at a time.** Not a batched round of questions.
- **Do not infer decisions from devcontainer tooling.** The devcontainer carries a TS/Node/Vite setup; it is
  available tooling, not a choice. (The stack chosen is Python — see ADR-0012.)
- **Keep production and trading separate.** The user pushed back hard when the design drifted into inventory,
  cash flow and time-to-sell. See ADR-0001: if a question is about how ISK moves through the market rather
  than what it costs to build a thing, it is out of scope.
- **Record decisions as they land**, not in a batch at the end.

## The shape of the thing, in one paragraph

A local web app (FastAPI + Jinja2 + HTMX + SQLite) that scans one or more market-group branches of invention-reachable
T2 items, ranks them by achievable **ISK per day**, and shows a cost breakdown on drill-down. Personal,
single-user, no ESI authentication — skills are typed in, not fetched. Everything is priced from a median of
daily market history at Jita; no spread is modelled. Starting category: **Rigs**.

## Decided parameters that are config, not ADRs

These came out of the interview but were too easily reversed to deserve an ADR. They belong in the TOML
config file (ADR-0013) with the noted defaults.

| Parameter | Default | Source |
|---|---|---|
| Valuation window | 15 days, median of daily `average`, IQR shown | ADR-0004 |
| Demand cutoff — relative share | ~20% of daily traded volume | ADR-0007 |
| Demand cutoff — absolute floor | 10 units/day | ADR-0007 |
| Demand cutoff — minimum days of history | 15 (the full window) | ADR-0007 |
| ESI concurrency ceiling | 15, hard | ADR-0011 |
| Error-budget safety floor | 50 of 100 | ADR-0011 |
| SCC surcharge | 4% (volatile — see G10) | ADR-0013 |
| Facility tax (NPC station) | 0.25% | research §5.4 |

Two implementation facts settled 2026-09-18, both verified live:

- **SDE download**: `https://www.fuzzwork.co.uk/dump/latest-sqlite.db.gz` is a stable URL (136 MB), with a companion
  `.md5sum` that makes "has the SDE changed?" answerable without re-downloading. The timestamped files under
  `dump/latest/` are *not* stable — do not build a URL from them.
- **ESI User-Agent**: must identify the app and carry a contact address. App string along the lines of
  `xrayape tech2 finder`. The contact address is supplied from **local config only** — this is a public repo,
  so it is deliberately not committed or written into an issue.

Undecided values are genuinely open and should be picked deliberately, not guessed at.

## The formulas, in brief

Full detail with sources in `docs/research/industry-formulas.md`. The headline forms:

```text
materialModifier = (1 - ME/100) * (1 - structureBonus/100) * (1 - rigBonus/100 * securityMultiplier)
required         = max(runs, ceil(round(runs * baseQuantity * materialModifier, 2)))
                   # round to 2dp, THEN ceil. Per job, not per run.

inventionChance  = baseProbability
                 * (1 + EncryptionLevel/40 + (Science1Level + Science2Level)/30)
                 * decryptorProbabilityMultiplier

EIV              = runs * SUM over materials of (baseQuantity_at_ME0 * adjusted_price)
totalJobCost     = EIV * ((systemCostIndex * activityMultiplier * structureCostBonus)
                          + facilityTax + sccSurcharge)

securityMultiplier: highsec 1.0 | lowsec 1.9 | nullsec 2.1   (applies to RIG bonuses only)
slots:              manufacturing = 1 + MassProduction + AdvancedMassProduction        (max 11)
                    science       = 1 + LaboratoryOperation + AdvancedLaboratoryOperation (max 11)
```

Two facts that shape the model more than they look:

- **Invented T2 rig BPCs come out at 1 run** (modules get 10), and rig invention burns **2 datacores of each
  type**. Invention is therefore very likely the binding pipeline for the starting category — which is why
  ADR-0008 models both pipelines rather than manufacturing alone.
- **Job fees are assessed on CCP's `adjusted_price`, not market price.** Job cost is insensitive to where
  materials are actually sourced.

## Three ESI feeds needed

Only the first scales per item, which is what the whole error-budget discipline in ADR-0011 is about.

- `/markets/{region_id}/history/` — one call **per `type_id`**. The Valuation Basis.
- `/markets/prices/` — one call, **all types**. `adjusted_price` for job fees.
- `/industry/systems/` — one call, **all systems**. System Cost Index; read, never computed.

Static data comes from Fuzzwork's prebuilt SQLite SDE dump.

## Open work, in rough priority order

1. **#6 — Valuation Basis.** Median of daily `average` over a configurable 15-day window, plus IQR as a
   volatility indicator. Data is already in `market_history`.
2. **#4 — Config and Production Profile.** TOML; every value is already decided (see the table above).
3. **#7 — Cost model**, then **#8 — Scan engine**, then **#9 — Web layer**.
4. **#10 — Validate the four load-bearing formula gaps against real in-game jobs.** This one needs the
   user at the keyboard in game, recording real jobs at low run counts, and cannot be done from sources:
   - **G1/G2** — the modern facility term in the material formula is undocumented; the `round(x, 2)` step
     rests on a single 2016 source. High confidence on shape, medium on that step.
   - **G9** — sources disagree on whether the invention job fee scales with runs.
   - **G10** — tax rates have changed four times since 2023. Configuration, and worth re-checking.
   - **G3** — the wormhole security multiplier is unconfirmed (community assumes the nullsec 2.1).

## Things learned while building, that are easy to get wrong again

- **ESI history omits untraded days entirely** — no row, never `volume: 0`. So the minimum-days cutoff is
  a *liquidity* filter, not a data-sufficiency check, and the row count is a free liquidity signal.
  The series also lags one to two days behind today.
- **Invention is many-to-many in both directions.** 48 products have several sources that *disagree* on
  probability and runs; 74 sources invent several products, and the player picks which. But probability
  and run count never vary by product within a source, so the whole invention leg belongs to the source
  and can be computed once and reused. Asserted in the real-dump tests, since it is observed rather than
  documented by CCP.
- **The error budget is where a bug costs API access.** Two shipped in the first pass: the halt was a
  no-op when ESI omitted the `Reset` header, and concurrency could fall but never recover. Both are
  pinned by regression tests now. Treat `budget.py` as code to change carefully.
- **Settling is a property of the calendar, not the data.** The trailing edge of history must be anchored
  on today, not on the newest row — otherwise a dormant item's months-old rows are rewritten forever.

## Working practice that has held up

Each ticket: TDD at the agreed seams, then `/code-review`, then fix what it finds, reproducing each
finding before fixing and re-verifying after. The review has caught a real defect every single time,
including two that would have cost API access. Do not skip it.

## Everything is committed

`main` is clean and pushed. There is nothing outstanding in the working tree.
