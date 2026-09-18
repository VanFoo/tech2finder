# Production Profile in config, overrides ephemeral by default

Skills, facility and its ME/TE rigs, facility tax, broker fee and sales tax live in a TOML config file as defaults and are overridable per run in the UI. Also in the profile, because the formulas need them:

- **Security band of the manufacturing system** (highsec / lowsec / nullsec). Structure rig bonuses are scaled by 1.0, 1.9 and 2.1 respectively, so the same rig in the same structure gives materially different results by location. The multiplier is an attribute of the rig, not the structure.
- **SCC surcharge rate.** A global rate rather than a player-specific one, but it has changed four times since 2023 and ESI does not publish it, so it is configuration rather than a constant.
- **Structure job-fee bonus** (Raitaru 3%, Azbel 4%, Sotiyo 5%), which reduces the system-cost-index term of the installation fee. An override lives for the session and changes nothing permanent; promoting one into the baseline is an explicit "save as default" action.

This matches the Scenario framing of ADR-0003 — a Scenario is a throwaway evaluation, so only a deliberate act should move one into the baseline. Writing overrides back automatically would destroy the reference point: the user could no longer tell their real profile from a what-if.

## Consequences

The **System Cost Index is deliberately excluded** from the Production Profile. It is always fetched live from ESI and never configured, so a stale number cannot silently skew every result. The manufacturing system it is looked up for follows from the configured facility.

The tool uses **no ESI authentication**: character skills are entered by hand rather than fetched, so only public market and industry-index endpoints are called.
