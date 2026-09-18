# EVE Online industry formulas — implementation reference

**Sources fetched: 2026-09-18.** Every numeric claim below is traceable to a cited source.
Where a source is old enough that it may have drifted from the live game, it is marked
⚠️ inline and listed again under [Gaps and uncertainties](#gaps-and-uncertainties).

## Source trust ladder used here

| Rank | Source | Notes |
|---|---|---|
| 1 | Game static data (SDE), served by [EVE Ref ref-data](https://ref-data.everef.net/) and cross-checked against [ESI](https://esi.evetech.net/ui/) | Authoritative for per-blueprint numbers: invention base probability, output runs, datacore counts, decryptor attributes, structure-rig attributes. Not a formula source. |
| 2 | [EVE University wiki](https://wiki.eveuniversity.org/) | Main target. Pages cited individually. Last-edited dates recorded below. |
| 3 | CCP dev blogs / patch notes | Cited by the wiki; several predate current mechanics. |
| 4 | [*Formulas for EVE Industry*, Qoi, v2.2, 2016-03-11 (PDF)](https://eve-industry.org/export/IndustryFormulas.pdf) | ⚠️ 2016. Linked from the wiki's [Research](https://wiki.eveuniversity.org/Research) page as its external formula reference. **This is the only source for the exact material rounding expression and the time formula.** Its *facility* numbers are pre-Upwell and are wrong today; its *formula shapes* are still what every calculator implements. |

EVE University page last-edited dates (via MediaWiki API, 2026-09-18):
Manufacturing 2026-01-25 · Invention 2026-01-07 · Research 2026-03-21 · Upwell structure 2026-05-23 · Rigs 2026-01-30 · Industry 2025-12-30.

---

## What an implementer needs to know

```text
# ---- MANUFACTURING MATERIALS (per material, per job) ----
materialModifier = (1 - ME/100)
                 * (1 - structureMaterialBonus/100)
                 * (1 - rigMaterialBonus/100 * securityMultiplier)

required = max( runs,
                ceil( round( runs * baseQuantity * materialModifier, 2 ) ) )
# round to 2 dp FIRST, then ceil, then floor-clamp at `runs`.
# Rounding is PER JOB, not per run.

# ---- MANUFACTURING TIME ----
timeModifier  = (1 - TE/100)
              * (1 - structureTimeBonus/100)
              * (1 - rigTimeBonus/100 * securityMultiplier)
              * (1 - 0.04 * IndustryLevel)
              * (1 - 0.03 * AdvancedIndustryLevel)

skillModifier = PRODUCT over each required science skill k of (1 - 0.01 * Level(k))

productionTime = baseProductionTime * timeModifier * skillModifier * runs

# ---- INVENTION ----
inventionChance = baseProbability
                * (1 + EncryptionLevel/40 + (Science1Level + Science2Level)/30)
                * decryptorProbabilityMultiplier          # 1.0 if no decryptor

inventionTime   = baseInventionTime
                * (1 - structureTimeBonus/100)
                * (1 - rigTimeBonus/100 * securityMultiplier)
                * (1 - 0.03 * AdvancedIndustryLevel)

outputRuns = baseRuns + decryptorRunModifier      # baseRuns: 10 modules/ammo, 1 ships & rigs
outputME   = 2 + decryptorMEModifier              # clamp: never below 0
outputTE   = 4 + decryptorTEModifier              # clamp: never below 0

# ---- JOB INSTALLATION COST (all activities) ----
EIV = runs * SUM over all manufacturing materials of ( baseQuantity * adjusted_price )
#   baseQuantity = ME 0, no bonuses. adjusted_price from ESI /markets/prices/, NOT market price.

totalJobCost = EIV * ( (systemCostIndex * activityMultiplier * structureCostBonus)
                       + facilityTax + sccSurcharge + alphaCloneTax )
# activityMultiplier: 1.0 manufacturing; 0.02 invention & copying.
# facilityTax 0.0025 at NPC stations; sccSurcharge 0.04 (manufacturing & invention).

# ---- SECURITY MULTIPLIER (applies to STRUCTURE RIG bonuses only) ----
highsec 1.0 · lowsec 1.9 · nullsec & wormhole 2.1

# ---- SLOTS ----
manufacturing jobs = 1 + MassProduction + AdvancedMassProduction          # max 11
science/invention  = 1 + LaboratoryOperation + AdvancedLaboratoryOperation # max 11
```

**The one question of fact:** Tech 2 rigs do **not** require intermediate manufactured
components. They are built from salvaged materials plus a single R.A.M. tool.
See [Tech 2 rigs](#the-question-of-fact-do-t2-rigs-need-intermediate-components).

---

## 1. Manufacturing materials

### 1.1 The formula

Source: [*Formulas for EVE Industry* v2.2 (2016), §1 "Required Materials for Production Job"](https://eve-industry.org/export/IndustryFormulas.pdf) — verbatim:

> `required = max(runs, ceil(round(runs * baseQuantity * materialModifier, 2)))`
>
> `materialModifier` is a product of the ME modifier (1.0 to 0.90 or 0% to 10% reduction)
> and the facility modifier … All four modifiers are multiplied together.

⚠️ The PDF's *examples* of facility modifiers ("1.05 for Rapid Assembly Arrays, 1.0 for NPC
Station, 0.98 for most POS arrays") are from the POS era and no longer exist. The *shape* —
one product of independent multiplicative modifiers, then `round(.,2)` → `ceil` → `max(runs, .)` —
is what current calculators implement. See [Gaps](#gaps-and-uncertainties) item G1.

### 1.2 Order of operations — state this explicitly

1. Multiply `runs * baseQuantity`.
2. Multiply by every efficiency modifier (ME, structure, rig-with-security), all multiplicative.
3. `round(x, 2)` — round to two decimal places. This absorbs floating-point dust before the ceiling.
4. `ceil(...)` — round **up** to the next whole unit.
5. `max(runs, ...)` — enforce the per-run minimum of one unit of each material.

Rounding happens **once, per job — not per run**. Sources agree on this explicitly:

> "The rounding is done per job instead of per run. A single industry job with 3 runs can use
> *less* material than 3 single jobs from the same blueprint!"
> — [EVE University: Manufacturing § "Beware of rounding errors!"](https://wiki.eveuniversity.org/Manufacturing)

> "It is important to note that material rounding happens *after* you have multiplied by the
> number of runs. … Materials will always round up to the next whole number."
> — [EVE University: Research § Material Efficiency Research](https://wiki.eveuniversity.org/Research)

> "Materials are calculated per-job rather than per-run" and "every run requires a minimum of
> one unit of every listed material."
> — [CCP dev blog: *EVE Industry — All you want to know*](https://www.eveonline.com/news/view/eve-industry-all-you-want-to-know) (Crius, 2014)

The `max(runs, …)` clamp is the "at least one per run" rule, and it is a hard floor that ME
cannot beat — critical for T2, where every T2 item consumes exactly one T1 item per run:

> "You will always need 10 Rifters to build 10 Jaguars, never 9, even if your Jaguar blueprint
> is fully researched." — [EVE University: Research](https://wiki.eveuniversity.org/Research)

### 1.3 Material efficiency (ME)

| Property | Value | Source |
|---|---|---|
| ME range on a researched BPO | 0 to 10, in steps of 1 | [Research](https://wiki.eveuniversity.org/Research) |
| Reduction per ME point | 1% | [Research](https://wiki.eveuniversity.org/Research) |
| ME modifier | `1 - ME/100` (1.00 → 0.90) | [Formulas PDF §1](https://eve-industry.org/export/IndustryFormulas.pdf) |
| ME on an invented T2 BPC | 2 (before decryptor) | [Invention](https://wiki.eveuniversity.org/Invention) |
| T2 BPCs are researchable? | **No** — "The only activity you can do with a T2 BPC is to manufacture it" | [Invention](https://wiki.eveuniversity.org/Invention) |

### 1.4 Structure (facility) material bonus

Engineering complexes, role bonus to manufacturing material requirement
([EVE University: Upwell structure § Engineering complexes](https://wiki.eveuniversity.org/Upwell_structure)):

| Structure | Material bonus | Time bonus | Job-fee bonus |
|---|---|---|---|
| Raitaru (M) | 1% | 15% | 3% |
| Azbel (L) | 1% | 20% | 4% |
| Sotiyo (XL) | 1% | 30% | 5% |
| NPC station | 0% | 0% | 0% |

The 1% material bonus is also stated on [Manufacturing](https://wiki.eveuniversity.org/Manufacturing):
"Engineering complexes provide a modest material savings (1%) and significant time savings
(15% - 30% depending on size) over NPC stations."

The structure role bonus is **not** multiplied by the security multiplier — only rig bonuses are
(see 1.6). See [Gaps](#gaps-and-uncertainties) G2.

### 1.5 Structure rig material bonus

Rig bonuses come from the rig item's own dogma attributes. Verified from game data
(ref-data.everef.net, fetched 2026-09-18):

| Rig (type id) | `attributeEngRigMatBonus` (2594) | `attributeEngRigTimeBonus` (2593) |
|---|---|---|
| Standup M-Set Equipment Manufacturing Material Efficiency I (43920) | −2.0 | 0 |
| Standup M-Set Equipment Manufacturing Material Efficiency II (43921) | −2.4 | 0 |
| Standup M-Set Advanced Component Manufacturing Material Efficiency I (43867) | −2.0 | 0 |
| Standup M-Set Equipment Manufacturing Time Efficiency I (37160) | 0 | −20.0 |
| Standup M-Set Invention Accelerator I (43880) | 0 | −20.0 |
| Standup M-Set Invention Accelerator II (43881) | 0 | −24.0 |

Values are **negative percentages** (a −2.0 mat bonus = 2% fewer materials). Read the actual
attribute off the rig type rather than hardcoding — the set above is a sample, not the full list.
Rigs are category-scoped (Equipment / Ship / Ammunition / Advanced Component / …), so a rig only
applies if the product falls in its category.

### 1.6 Security-space multiplier on rig bonuses

Every Standup industry rig carries three attributes giving the multiplier applied to its bonus
by the security status of the system the structure sits in. Verified on all six rigs sampled
above — the values are identical across them:

| Attribute id | Name | Value |
|---|---|---|
| 2355 | `hiSecModifier` | **1.0** |
| 2356 | `lowSecModifier` | **1.9** |
| 2357 | `nullSecModifier` | **2.1** |

So a Standup M-Set Equipment Manufacturing ME II rig (−2.4%) gives 2.4% in highsec,
4.56% in lowsec, and 5.04% in nullsec. Wormhole space uses the nullsec multiplier
(2.1) — ⚠️ this last point is **not** confirmed by any source I fetched; see [Gaps](#gaps-and-uncertainties) G3.

The multiplier scales the **rig bonus only**, not the structure role bonus and not ME.
This is inference from the attributes living on the rig rather than on the structure;
see [Gaps](#gaps-and-uncertainties) G2.

---

## 2. Manufacturing time

### 2.1 The formula

Source: [*Formulas for EVE Industry* v2.2, §1 "Production Time"](https://eve-industry.org/export/IndustryFormulas.pdf) — verbatim:

> `productionTime = baseProductionTime * timeModifier * skillModifier * runs`
>
> `skillModifier = PRODUCT(k=1..d) of (1 - 0.01 * Level(k))`
>
> Where *d* is the number of science skills … required for manufacturing this particular item …
> This currently mostly applies to Tech II manufacturing.
>
> `timeModifier` is a product of the TE modifier (1.0 to 0.80 or 0% to 20% reduction), the
> facility modifier …, [and] the skills Industry (4% per level, down to modifier 0.80) and
> Advanced Industry (3% per level, down to modifier 0.85) affect it. … All … modifiers are
> multiplied together.

Note that time scales **linearly with runs and is not rounded per run** — unlike materials, there
is no ceiling step. ⚠️ Whether the final value is truncated to whole seconds is not stated by any
source; see [Gaps](#gaps-and-uncertainties) G4.

### 2.2 Constants

| Modifier | Value | Source |
|---|---|---|
| TE range | 0 to 20, in steps of 2 | [Research](https://wiki.eveuniversity.org/Research); [Formulas PDF §2](https://eve-industry.org/export/IndustryFormulas.pdf) |
| Reduction per TE research step | 2% (10 steps → 20% total) | [Research](https://wiki.eveuniversity.org/Research) |
| TE modifier | `1 - TE/100` (1.00 → 0.80) | [Formulas PDF §1](https://eve-industry.org/export/IndustryFormulas.pdf) |
| **Industry** skill | 4% reduction per level → ×0.80 at V | [Manufacturing](https://wiki.eveuniversity.org/Manufacturing); [Formulas PDF §1](https://eve-industry.org/export/IndustryFormulas.pdf) |
| **Advanced Industry** skill | 3% reduction per level → ×0.85 at V. Applies to manufacturing **and** research **and** invention | [Manufacturing](https://wiki.eveuniversity.org/Manufacturing), [Skills:Production](https://wiki.eveuniversity.org/Skills:Production) ("3% reduction in all manufacturing and research times per skill level"), [Research](https://wiki.eveuniversity.org/Research) |
| Per-item science skills | 1% reduction per level, each, multiplicative | [Manufacturing](https://wiki.eveuniversity.org/Manufacturing) ("Most of these skills also give a 1% time efficiency bonus per level"); [Formulas PDF Table 2](https://eve-industry.org/export/IndustryFormulas.pdf) |
| Structure time bonus | Raitaru 15% / Azbel 20% / Sotiyo 30% | [Upwell structure](https://wiki.eveuniversity.org/Upwell_structure) |
| Rig time bonus | read `attributeEngRigTimeBonus` off the rig, × security multiplier | SDE (see 1.5, 1.6) |

⚠️ The 2014 Crius dev blog states Advanced Industry gives "a build time reduction of 1% per
level". This is **stale**: both the current wiki and the 2016 PDF say 3%. Use 3%.

The science skills carrying the 1%-per-level manufacturing time reduction
([Formulas PDF Table 2](https://eve-industry.org/export/IndustryFormulas.pdf)): Advanced
Small/Medium/Large/Industrial Ship Construction; Amarr/Caldari/Gallente/Minmatar Starship
Engineering; Electromagnetic Physics; Electronic Engineering; Graviton Physics; High Energy
Physics; Hydromagnetic Physics; Laser Physics; Mechanical Engineering; Molecular Engineering;
Nuclear Physics; Plasma Physics; Quantum Physics; Rocket Science.

Only the skills a given blueprint actually requires enter the product. Read them from the
blueprint's `manufacturing.required_skills` in the SDE.

---

## 3. Invention

### 3.1 Probability

Source: [EVE University: Invention § Maximizing invention success](https://wiki.eveuniversity.org/Invention) — verbatim:

> Success chance = Base × ( 1 + (Science skill 1 + Science skill 2)/30 + Racial encryption method/40 )
> × ( 1 + Probability Multiplier of Decryptor / 100% )

Cross-checked against [*Formulas PDF* §4](https://eve-industry.org/export/IndustryFormulas.pdf),
which gives the same thing with the decryptor as a plain multiplier:

> `inventionChance = baseChance * SkillModifier * DecryptorModifier`
> `SkillModifier = 1 + EncryptionLevel/40 + (Datacore1Level + Datacore2Level)/30`

**Use the plain-multiplier form.** The game data stores the decryptor effect as a direct
multiplier (`inventionPropabilityMultiplier` = 1.2, 1.8, 0.6 …), so the wiki's
"+20 … /100%" phrasing and the PDF's `DecryptorModifier` are the same number expressed
differently. With no decryptor the multiplier is 1.0.

Skill effect restated: each science skill level is worth 1/30 = 3.333% of base; each encryption
skill level is worth 1/40 = 2.5% of base. Both sources state this. Note these are multipliers on
*base*, not additive percentage points on the final chance.

At all-V skills: `1 + 5/40 + 10/30 = 1.4583…`, so a module's 34% base becomes 49.58% before decryptors.

### 3.2 Base probability per item type

Base probability is a **per-blueprint SDE value** (`activities.invention.products[].probability`),
not a lookup by category — read it from the blueprint. The category table is a summary.

[EVE University: Invention](https://wiki.eveuniversity.org/Invention):

| Base chance | Item types |
|---|---|
| 34% | Modules, rigs, ammo |
| 30% | Frigates, destroyers |
| 26% | Cruisers, battlecruisers, mining barges, haulers, intact ancient relics |
| 22% | Battleships |
| 21% | Malfunctioning ancient relics |
| 18% | Freighters |
| 14% | Wrecked ancient relics |

Spot-checked against SDE (fetched 2026-09-18), all confirming the table for T2:

| T1 blueprint | type id | probability | output runs | datacores |
|---|---|---|---|---|
| Medium Core Defense Field Extender I BP (rig) | 31791 | **0.34** | **1** | Hydromagnetic Physics ×2, Quantum Physics ×2 |
| Nanofiber Internal Structure I BP (module) | 2604 | **0.34** | **10** | Nanite Engineering ×1, Molecular Engineering ×1 |
| Rifter BP (frigate) | 691 | **0.30** | **1** | ×2 each |
| Rupture BP (cruiser) | 974 | **0.26** | **1** | ×8 each |
| Apocalypse BP (battleship) | 996 | **0.22** | **1** | ×32 each |

⚠️ The 2016 PDF's Table 1 gives **different** relic numbers (intact 34%, malfunctioning 30%,
wrecked 22%) and also lists a 100% "Perpetual Motion Unit I" entry. The T2 rows agree exactly;
only the T3-relic rows conflict. Prefer the wiki. Out of scope for T2 anyway. See G5.

### 3.3 What the invented T2 BPC comes out as

Base values, before decryptors
([EVE University: Invention](https://wiki.eveuniversity.org/Invention), citing
[CCP: *EVE Industry — All you want to know*](https://www.eveonline.com/news/view/eve-industry-all-you-want-to-know)):

| Property | Value |
|---|---|
| ME | **2** |
| TE | **4** |
| Runs — most items (modules, ammo) | **10** |
| Runs — **ships and rigs** | **1** |

> "Regardless of the research performed on the T1 BPC, the result will have exactly ME 2% and TE 4%."
> "T2 BPCs for ships and rigs have 1 run."

Decryptor modifiers are **added** to these base values:

> "Add the values from the decryptor to the base values to calculate the final outcome of the T2 BPC."

The input BPC's own ME / TE / remaining runs are irrelevant:
> "The ME, TE, and Runs Remaining on the input BPC do not impact the resulting invented BPC."

⚠️ The 2016 PDF adds two special cases not mentioned by the current wiki: "Perpetual Motion Unit II"
gets 1 run and "Rapid Heavy Missile Launcher II" gets 20. Unconfirmed against current data — read
`activities.invention.products[].quantity` from the SDE per blueprint and this never matters. See G6.

### 3.4 Invention job time

Source: [*Formulas PDF* §4](https://eve-industry.org/export/IndustryFormulas.pdf) — verbatim:

> `inventionTime = baseInventionTime * facilityModifier * (1 - 0.03 * AdvancedIndustryLevel)`

Notable: **only Advanced Industry** affects invention time. The Industry skill, the science
skills, the encryption skill and TE do not. `baseInventionTime` is the blueprint's
`activities.invention.time` in the SDE (e.g. 15600 s for the rig above, 13800 s for the module,
192000 s for the Apocalypse).

The structure side of `facilityModifier` today is the engineering complex science-job duration
role bonus (Raitaru 15% / Azbel 20% / Sotiyo 30% — it covers "manufacturing and science job
duration", [Upwell structure](https://wiki.eveuniversity.org/Upwell_structure)) plus any
Standup Invention Accelerator rig (−20% for I, −24% for II, × security multiplier).
[Invention](https://wiki.eveuniversity.org/Invention) confirms qualitatively:
"Engineering complexes provide significant innate reductions (from 15% to 30% depending on
complex size) to job duration and installation cost, and further reductions in time and cost are
possible if the complex owner has installed the appropriate rigs."
⚠️ The exact combination order is not stated anywhere — see G7.

### 3.5 Datacore consumption

- **Two types** per job, determined by the T1 blueprint (they match the two science skills).
- **Quantity scales with hull/item size.** From SDE (above): rig 2 each, small module 1 each,
  frigate 2 each, cruiser 8 each, battleship 32 each.
  [Invention](https://wiki.eveuniversity.org/Invention): "Small modules only require one datacore
  of each type while battleships require 32 of each type."
- **Consumed on failure as well as success:** "Whether the invention job is successful or not,
  these datacores will be consumed." Same for the decryptor. The T1 BPC is returned with one
  fewer run (and is consumed outright if it had only one run left).
- **Decryptors do not change datacore consumption.** The decryptor types carry exactly four
  functional attributes — `inventionPropabilityMultiplier`, `inventionMaxRunModifier`,
  `inventionMEModifier`, `inventionTEModifier` (verified on all eight, 2026-09-18). There is no
  material-quantity attribute. ⚠️ This is an argument from absence, not a positive statement in a
  source; see G8.
- Read counts from `activities.invention.materials` in the SDE. Do not derive from size.

### 3.6 Invention job runs

An invention job can have more than one run: each run consumes one run off the T1 BPC and rolls
independently, and the job fee scales with runs
([*Formulas PDF* §4](https://eve-industry.org/export/IndustryFormulas.pdf):
`jobFee = baseJobCost * systemCostIndex * 0.02 * runs`). Datacores and decryptors scale with runs
in the same way.

---

## 4. Decryptors — complete table

Wiki table ([Invention § Decryptor Stats](https://wiki.eveuniversity.org/Invention)) verified
attribute-by-attribute against the SDE (fetched 2026-09-18). **They agree exactly.**

| Decryptor | type id | Probability multiplier | Runs | ME | TE |
|---|---|---|---|---|---|
| Accelerant | 34201 | **×1.2** (+20%) | +1 | +2 | +10 |
| Attainment | 34202 | **×1.8** (+80%) | +4 | −1 | +4 |
| Augmentation | 34203 | **×0.6** (−40%) | +9 | −2 | +2 |
| Optimized Attainment | 34207 | **×1.9** (+90%) | +2 | +1 | −2 |
| Optimized Augmentation | 34208 | **×0.9** (−10%) | +7 | +2 | 0 |
| Parity | 34204 | **×1.5** (+50%) | +3 | +1 | −2 |
| Process | 34205 | **×1.1** (+10%) | 0 | +3 | +6 |
| Symmetry | 34206 | **×1.0** (0%) | +2 | +1 | +8 |

SDE attribute ids: 1112 `inventionPropabilityMultiplier` (note CCP's typo), 1124
`inventionMaxRunModifier`, 1113 `inventionMEModifier`, 1114 `inventionTEModifier`.

Resulting BPC (base ME 2 / TE 4 / runs 10 or 1):

| Decryptor | ME | TE | Runs, modules & ammo | Runs, ships & rigs |
|---|---|---|---|---|
| *(none)* | 2 | 4 | 10 | 1 |
| Accelerant | 4 | 14 | 11 | 2 |
| Attainment | 1 | 8 | 14 | 5 |
| Augmentation | 0 | 6 | 19 | 10 |
| Optimized Attainment | 3 | 2 | 12 | 3 |
| Optimized Augmentation | 4 | 4 | 17 | 8 |
| Parity | 3 | 2 | 13 | 4 |
| Process | 5 | 10 | 10 | 1 |
| Symmetry | 3 | 12 | 12 | 3 |

Augmentation's −2 ME lands exactly on ME 0. No decryptor pushes ME or TE negative from the
T2 base, so a clamp at 0 is defensive only. ⚠️ ME/TE upper bounds on an invented BPC are not
documented; nothing in the table exceeds ME 5 / TE 14, well inside the ME 10 / TE 20 research
ceilings, so this does not bite. Decryptors are consumed whether the job succeeds or fails.

---

## 5. Job cost / fees

### 5.1 Total installation fee

Source: [EVE University: Manufacturing § Total job cost](https://wiki.eveuniversity.org/Manufacturing),
citing [CCP: Viridian expansion notes, "Tax reforms"](https://www.eveonline.com/news/view/viridian-expansion-notes) — verbatim:

> Total job cost = Estimated item value × ( ( System cost index × Structure bonuses )
> + Facility tax + SCC surcharge + Alpha clone tax )

The Viridian notes give the same thing as `TIF = EIV * ((SCI * bonuses) + FacilityTax + SCC + AlphaClone)`.

**The structure cost bonus multiplies only the system-cost-index term.** The taxes are flat
percentages of EIV and a structure cannot discount them.

### 5.2 Estimated item value (EIV)

Source: [Manufacturing](https://wiki.eveuniversity.org/Manufacturing) — verbatim:

> Estimated item value = SUM over all materials ( Material quantity × Material adjusted price )
>
> "The estimated item's approximate value is the cost estimation of the materials for a **ME0
> blueprint with no bonuses applied**."

Three things implementations get wrong:

1. **It uses `adjusted_price`, not market price.** Confirmed twice.
   The wiki: "the adjusted prices of the items (found in ESI `/markets/prices/` endpoint)".
   CCP's [*Industry & 3rd Party Developers*](https://www.eveonline.com/news/view/industry-3rd-party-developers):
   "Multiply each material quantity by the market **adjustedPrice** as returned from the
   `/market/prices/` endpoint and sum them all together." The endpoint returns three fields per
   type — `type_id`, `average_price`, `adjusted_price` — and `adjusted_price` is the one CCP
   describes as "adjusted market price which is used in industry calculations". It is a
   CCP-computed internal index, not an order-book price; it does not respond to your buy orders,
   so job cost is insensitive to where you actually source materials.
2. **It uses the base ME 0 quantities**, never your ME-reduced quantities. Researching a blueprint
   does not reduce the job fee.
3. **It uses the *manufacturing* material list of the item being produced**, for every activity —
   including invention and copying. Explicitly noted on
   [Research](https://wiki.eveuniversity.org/Research): "Surprisingly for both invention and
   copying the Material Adjusted price is still based on the Manufacturing inputs of the final
   item. … for invention it will be based on the manufacturing inputs for the T2 item itself."
   So an invention job's EIV comes from the **T2** blueprint's manufacturing materials.

### 5.3 Activity multipliers and run scaling

Source: [CCP: *Industry & 3rd Party Developers*](https://www.eveonline.com/news/view/industry-3rd-party-developers) — verbatim:

> - **Manufacturing:** baseCost × numberOfRuns
> - **Research:** *Sum for each level(* baseCost × 0.02 × researchMultiplierForLevel
> - **Copying:** baseCost × 0.02 × runsPerCopy × numberOfRuns
> - **Invention + Reverse Engineering:** baseCost × 0.02

The [*Formulas PDF* §4](https://eve-industry.org/export/IndustryFormulas.pdf) additionally scales
invention by runs: `jobFee = baseJobCost * systemCostIndex * 0.02 * runs`.
⚠️ CCP's line omits the `× runs`; the PDF includes it. See G9.

### 5.4 Tax rates

[Manufacturing](https://wiki.eveuniversity.org/Manufacturing), with patch-note citations:

| Component | Value | Notes |
|---|---|---|
| Facility tax — NPC station | **0.25%** | Fixed |
| Facility tax — player structure | Set by owner | Capped at **10%** |
| SCC surcharge | **4%** | 0.25% → 0.75% (21.05, 2023-07-06) → 1.5% (21.05 R2, 2023-09-12) → 4% (21.06, 2024-02-01) |
| Alpha clone tax | **0.25%** | Alpha clones only |

⚠️ The Viridian notes (June 2023) state the SCC surcharge as 0.25%; that is the value **at
introduction** and has since been raised three times to 4%. Do not use the Viridian figure.

⚠️ SCC surcharge for **ME and TE research** was cut to 50% of baseline (effectively 2%) in the
2025-07-17 Legion update ([Exploration & Industry Balance Rework](https://www.eveonline.com/news/view/exploration-and-industry-balance-rework)).
This applies to research only — **not** manufacturing and **not** invention. See G10.

⚠️ The 2016 PDF gives a **different, now-wrong** tax structure: `facilityTax = jobFee × taxRate/100`
with "taxRate is 10 for NPC Stations". Viridian (2023) moved taxes onto EIV and NPC facility tax
is now 0.25%. Ignore the PDF for fees.

### 5.5 System cost index

[Manufacturing](https://wiki.eveuniversity.org/Manufacturing) / [Research](https://wiki.eveuniversity.org/Research),
citing [CCP: *EVE Industry — All you want to know*](https://www.eveonline.com/news/view/eve-industry-all-you-want-to-know):

> System cost index = sqrt( Work hours done in system in past 28 days / Work hours done in universe in past 28 days )

⚠️ **Do not implement this.** The wiki carries an explicit warning box:

> "Caution: the information about the system cost index calculation is probably no longer correct,
> considering this patch note 'We have adjusted the System Cost Index formula to make it more
> volatile.' which was published in Version 21.05 Release 2023-09-12.1"

Fetch the index from ESI instead. It is per-system **and per-activity**.

### 5.6 ESI endpoints

Verified against the live [ESI OpenAPI spec](https://esi.evetech.net/meta/openapi.json) and live
responses, 2026-09-18:

| Data | Endpoint | Auth | Shape |
|---|---|---|---|
| System cost indices | `GET /industry/systems/` | none | `[{ solar_system_id, cost_indices: [{ activity, cost_index }] }]` — activities seen live: `manufacturing`, `researching_time_efficiency`, `researching_material_efficiency`, `copying`, `invention`, `reaction` |
| Adjusted prices | `GET /markets/prices/` | none | `[{ type_id, adjusted_price, average_price }]` |
| Facility list | `GET /industry/facilities/` | none | NPC stations and public structures |

Use `cost_indices[activity == "manufacturing"]` for build jobs and
`cost_indices[activity == "invention"]` for invention jobs — they differ.

Blueprint base quantities, base times, invention probabilities, output runs and datacore
requirements are **not** in ESI. They live in the SDE (`blueprints.yaml`), per CCP's
[*Industry & 3rd Party Developers*](https://www.eveonline.com/news/view/industry-3rd-party-developers):
"Fetch the base material quantities for manufacturing the item from your blueprint, from the
`blueprints.yaml` file in the SDE." A convenient mirror is
[`https://ref-data.everef.net/blueprints/{blueprint_type_id}`](https://ref-data.everef.net/).

---

## 6. Slots

### 6.1 Manufacturing jobs

[EVE University: Manufacturing § Skills](https://wiki.eveuniversity.org/Manufacturing) — verbatim:

> "By default, all characters can run 1 manufacturing job at a time."
> **Mass Production** — "Allows 1 additional job per level … from 2 jobs at I up to 6 jobs at V."
> **Advanced Mass Production** — "Allows 1 additional job per level … Having this skill at IV
> gives you 10 manufacturing lines (1 + 5 + 4)."

```
manufacturingSlots = 1 + MassProduction + AdvancedMassProduction
```
Base 1, max **11** (1 + 5 + 5). Advanced Mass Production requires Mass Production V.

### 6.2 Science / invention jobs

[EVE University: Research § Skills](https://wiki.eveuniversity.org/Research) — verbatim:

> **Laboratory Operation** — "allows you to perform one additional research or copying job per
> level. Every character starts off with the ability to run a single research or copying job
> without needing to train this skill … if you train it to V, you can run 6 research or copying
> jobs at once."
> **Advanced Laboratory Operation** — "Once you have trained Laboratory Operation to V, you can
> then train this skill to increase still further the number of concurrent research or copying
> jobs you can perform **to a maximum of 11 jobs**."

```
scienceSlots = 1 + LaboratoryOperation + AdvancedLaboratoryOperation
```
Base 1, max **11**. [Invention](https://wiki.eveuniversity.org/Invention) confirms these are the
governing skills for invention: "Laboratory Operation and Advanced Laboratory Operation will
govern how many concurrent science jobs you can perform."

Manufacturing and science pools are **separate** — one character can run 11 of each concurrently.
Copying, ME research, TE research and invention all draw on the **same** science pool.

### 6.3 Remote job range (not a slot limit, but adjacent)

- **Supply Chain Management** — manufacturing jobs, +5 jumps/level, max 25 ([Manufacturing](https://wiki.eveuniversity.org/Manufacturing)).
- **Scientific Networking** — science jobs, +5 jumps/level, max 25 ([Research](https://wiki.eveuniversity.org/Research)).

---

## The question of fact: do T2 rigs need intermediate components?

**No. Tech 2 rigs are built directly from salvaged materials plus one R.A.M. tool. They require
no advanced/racial construction components, no moon-material intermediates, no morphite, no
planetary commodities, and no T1 rig.**

Verified from game data, blueprint `activities.manufacturing.materials`
(ref-data.everef.net, fetched 2026-09-18):

**Medium Core Defense Field Extender II** (blueprint 31797 → product 31796):

| Qty | Material | type id | Group |
|---|---|---|---|
| 6 | Power Circuit | 25617 | 754 Salvaged Materials |
| 6 | Logic Circuit | 25619 | 754 Salvaged Materials |
| 3 | Enhanced Ward Console | 25625 | 754 Salvaged Materials |
| 1 | R.A.M.- Shield Tech | 11484 | 332 Tool |

**Large Trimark Armor Pump II** (blueprint 26303):

| Qty | Material | Group |
|---|---|---|
| 20 | Intact Armor Plates | 754 Salvaged Materials |
| 15 | Nanite Compound | 754 Salvaged Materials |
| 23 | Interface Circuit | 754 Salvaged Materials |
| 1 | R.A.M.- Armor/Hull Tech | 332 Tool |

Contrast — a T2 **module**, **Nanofiber Internal Structure II** (blueprint 2606):

| Qty | Material | Group |
|---|---|---|
| 1 | Morphite | 18 Mineral |
| 1 | Nanofiber Internal Structure I | 763 (the T1 module) |
| 1 | R.A.M.- Armor/Hull Tech | 332 Tool |
| 8 | Construction Blocks | 1034 Planetary commodity |

The T2 module consumes its T1 counterpart; the T2 rig does not consume a T1 rig. Both consume a
R.A.M., which is a manufactured T1 item but is freely market-traded (it is not a T2-gated
intermediate). Both bills of materials are entirely market-buyable, so the tool's
buy-all-inputs decision holds for T2 rigs with no special-casing.

Corroborating prose, [EVE University: Rigs](https://wiki.eveuniversity.org/Rigs):
> "Rigs are manufactured by players, using salvaged material."

The wiki does not distinguish T1 from T2 rigs on this point, which is why the blueprint data is
the load-bearing source here.

Two further facts worth carrying into the tool:
- **A T2 rig BPC has 1 run**, like a ship, not 10 like a module. Confirmed from both
  [Invention](https://wiki.eveuniversity.org/Invention) ("T2 BPCs for ships and rigs have 1 run")
  and the SDE (`invention.products[].quantity` = 1 on blueprint 31791, and
  `max_production_limit` = 1 on the T2 rig blueprints).
  This makes run-boosting decryptors (Augmentation +9, Optimized Augmentation +7) disproportionately
  valuable for rigs, exactly as the wiki suggests.
- **Rig invention consumes 2 datacores of each type**, not 1 as for a small module
  (blueprint 31791: Hydromagnetic Physics ×2, Quantum Physics ×2).

---

## Invention is many-to-many, and the invention leg belongs to the source

Measured against the full SDE (2026-09-18), not inferred:

- **Several sources per product.** 48 products are invented from more than one source blueprint,
  and every one of those differs in probability and run count — T3 subsystems from intact,
  malfunctioning and wrecked relics at 0.26/20, 0.21/10 and 0.14/3.
- **Several products per source.** 74 of 1113 source blueprints invent more than one product, up
  to 16 from one. A Merlin blueprint invents either a Hawk or a Harpy, and **the player chooses
  which** at invention time.
- **Probability and run count never vary by product within a source.** Across all 74 multi-product
  sources: zero exceptions, for both.

The third point is the useful one. It means the entire invention leg — odds, BPC runs, and the
datacores consumed — is a property of the **source blueprint**, so expected blueprint cost per run
is identical for every sibling product. Two items invented from the same hull differ only
downstream: in their bill of materials and what the market pays for them.

⚠️ This is an observed property of the current SDE, not a documented CCP guarantee. It is asserted
in the real-dump tests so that a change surfaces loudly rather than silently skewing results.

---

## ESI market history omits days with no trades

Measured against the live API (2026-09-18, The Forge / Jita):

| type | rows | span | missing days | zero-volume rows |
|---|---|---|---|---|
| Medium Core Defense Field Extender II | 413 | 413 d | 0 | 0 |
| XL Torpedo Launcher II | 407 | 412 d | 5 | 0 |
| XL Cruise Missile Launcher II | 352 | 412 d | 60 | 0 |
| Ymir | 2 | 15 d | 13 | 0 |

**A day with no trades produces no row at all** — never a row with `volume: 0`. Across four items
spanning 0 to 60 missing days, not one zero-volume row appeared.

Consequences for the tool:

- The **minimum-days Demand Cutoff is a liquidity filter, not a data-sufficiency check.** At its
  default of 15 (the full valuation window) an item must have traded on *every one of the last 15
  days* to be ranked. That is considerably stricter than "has 15 days of history", and it silently
  subsumes the sporadicity filter that was considered and deferred during design.
- **Row count is a usable liquidity signal in its own right**: days-traded-out-of-window needs no
  extra request, because it is just the number of rows returned.
- The series **lags by one to two days** — the newest row observed was yesterday or the day before,
  never today. So "how many days behind is the newest row" must tolerate a lag of at least two
  before treating data as stale.

---

## Gaps and uncertainties

Things I could **not** confirm, or where sources disagree. None of these are papered over above.

**G1 — The material formula's modern facility term is not in any primary source.**
The exact expression `max(runs, ceil(round(runs * baseQuantity * materialModifier, 2)))` comes
**only** from the 2016 Qoi PDF. EVE University states the *behaviour* (round up, per job, minimum
one per run) but never writes the formula. CCP has never published it. In particular the
intermediate `round(x, 2)` step is attested by the PDF alone. It matters only at floating-point
boundaries, but at those boundaries it is the difference between a correct and an off-by-one
material count. **Confidence: high on shape, medium on the 2-dp rounding step.** Worth validating
against a handful of real in-game jobs once the tool has data.

**G2 — Whether structure and rig material bonuses are multiplicative with each other and with ME
is not documented.** The PDF says "all modifiers are multiplied together" but its modifier list is
POS-era (ME × facility × two team bonuses) and predates Upwell structures entirely. That the
security multiplier scales the rig bonus and not the structure role bonus is my **inference** from
`hiSecModifier`/`lowSecModifier`/`nullSecModifier` being attributes of the *rig item*, with no
equivalent on the structure. Plausible and universally implemented, but not sourced.
**Confidence: medium.**

**G3 — Wormhole space security multiplier.** I found no source stating which multiplier applies in
J-space. The attribute set only has hi/low/null. Community consensus is that wormholes use the
nullsec value (2.1), but **I could not confirm this** from the wiki, CCP, or game data.

**G4 — Time rounding.** No source states whether `productionTime` is truncated, rounded, or kept
fractional before being shown as a job duration. The PDF gives an unrounded product. Sub-second,
so it will not affect profit ranking, but it will cause small mismatches against in-game numbers.

**G5 — Ancient-relic invention base chances disagree between sources.** Wiki: intact 26%,
malfunctioning 21%, wrecked 14%. 2016 PDF Table 1: intact 34%, malfunctioning 30%, wrecked 22%.
The T2 rows (34/30/26/22) agree exactly, so this is a T3-only conflict and out of scope for
tech2finder. Prefer the wiki (current) if it ever matters. Not independently resolved.

**G6 — Special-case invention run counts.** The 2016 PDF claims "Perpetual Motion Unit II" gets
1 run and "Rapid Heavy Missile Launcher II" gets 20 runs. I did not verify either against current
data. Reading `invention.products[].quantity` per blueprint from the SDE makes this moot — **do
that rather than assuming 10-for-modules / 1-for-ships-and-rigs**.

**G7 — Invention time: how structure and rig bonuses combine.** The PDF's formula predates Upwell
structures and folds everything into an undefined `facilityModifier`. That the engineering complex
role bonus and the Invention Accelerator rig bonus are multiplicative, and that the security
multiplier applies to the rig leg, follows the manufacturing pattern — but is **not sourced for
invention specifically**. **Confidence: medium.**

**G8 — Decryptors and datacore counts.** No source positively states that decryptors leave datacore
consumption unchanged. My conclusion rests on the eight decryptor types carrying only four
functional attributes (probability / runs / ME / TE), with no material modifier. Strong, but it is
an argument from absence.

**G9 — Does the invention job fee scale with runs?** CCP's dev blog gives
"Invention + Reverse Engineering: baseCost × 0.02" with no run term. The 2016 PDF gives
`baseJobCost × systemCostIndex × 0.02 × runs`. **Sources disagree.** The PDF is almost certainly
right (an N-run invention job consumes N BPC runs and N sets of datacores, so a flat fee would be
strange), and CCP's line is probably describing the per-run base. Unresolved — if the tool models
multi-run invention jobs, verify in game.

**G10 — Tax rates are the most volatile numbers here.** The SCC surcharge has changed four times
since 2023 (0.25 → 0.75 → 1.5 → 4%, plus a research-only halving to 2% in July 2025). The wiki
page carrying the 4% figure was last edited 2026-01-25; I could not find any change between then
and the fetch date of 2026-09-18, but **absence of evidence is not confirmation**. Treat the SCC
surcharge and facility tax as configuration, not constants.

**G11 — System cost index formula is known-stale.** The published `sqrt(system/universe)` form was
explicitly made "more volatile" by CCP in Version 21.05 R2 (2023-09-12) and no replacement formula
has been published. The wiki flags this itself. **Do not compute it — read it from
`/industry/systems/`.**

**G12 — Structure job-fee bonus semantics.** Raitaru 3% / Azbel 4% / Sotiyo 5% are listed on the
Upwell structure page as "Job fee" role bonuses. That these enter the total-cost formula as the
"Structure bonuses" multiplier on the system cost index term (i.e. `× (1 - 0.03)` for a Raitaru)
is the natural reading of the Viridian formula, but the wiki never joins the two statements
explicitly, and cost-reduction rigs (`attributeEngRigCostBonus`, attribute 2595) would presumably
multiply in alongside. **Confidence: medium.**

**G13 — No source lists the full set of Standup industry rigs.** The six sampled in §1.5 are
illustrative. Enumerate the rig group from the SDE and read attributes 2593/2594/2595 and
2355/2356/2357 off each type rather than hardcoding a table.
