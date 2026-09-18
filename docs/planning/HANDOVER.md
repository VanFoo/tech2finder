# tech2finder — session handover

Written 2026-09-18, at the end of the design phase. Read this first when picking the project back up.

## Where the project stands

**Design is complete. No code has been written.** A 39-decision grilling interview closed with an empty
frontier, the decisions were distilled into 13 ADRs, and the industry maths was researched and written up.
Nothing is committed — everything below is untracked or modified in the working tree.

## Where things live

| What | Where | Status |
|---|---|---|
| Glossary / domain language | `CONTEXT.md` | committed |
| Architecture decisions (14) | `docs/adr/0001`–`0014` | committed |
| EVE industry formulas | `docs/research/industry-formulas.md` | committed |
| Agent conventions | `docs/agents/` | committed |
| This handover | `docs/planning/HANDOVER.md` | committed |

`README.md` has an uncommitted edit adding a note about eve-industry.org — the unmaintained site that does
part of this job one blueprint at a time. Scanning and ranking a whole category is the gap this tool fills.

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

1. **Validate the load-bearing formula gaps against real in-game jobs.** Four matter (full list under
   "Gaps and uncertainties" in the research file):
   - **G1/G2** — the modern facility term in the material formula is undocumented; the `round(x, 2)` step
     rests on a single 2016 source. High confidence on shape, medium on that step.
   - **G9** — sources actively disagree on whether the invention job fee scales with runs. CCP says no run
     term; the 2016 PDF says there is one.
   - **G10** — tax rates have changed four times since 2023. Treat as configuration and re-check.
   - **G3** — the wormhole security multiplier is unconfirmed (community assumes the nullsec 2.1).
2. ~~Decide the three undecided config defaults.~~ **Done 2026-09-18** — all three settled and recorded in their ADRs.
3. **Verify one ESI fact that changes a filter's meaning**: does `/markets/{region_id}/history/` return rows only for days that traded, or also zero-volume days? If the former, ADR-0007's minimum-days threshold doubles as a sporadicity filter; if the latter, it is purely a data-sufficiency check.
4. **Read per-blueprint values from the SDE rather than hardcoding category defaults** — invention run
   counts especially (research G6), and the Standup rig attribute set (G13).
5. **Start implementation.** ADR-0012 constrains the shape: cost model and scan-result layer return plain
   dataclasses, templates only render them — no domain arithmetic in a template, no ORM objects in the view.
   That seam is what keeps an SPA swap cheap later.

## Nothing is committed

`git status` at handover: `README.md` modified; `CONTEXT.md`, `docs/adr/`, `docs/planning/`, `docs/research/`
untracked. Committing this design work is a reasonable first act of the next session.
