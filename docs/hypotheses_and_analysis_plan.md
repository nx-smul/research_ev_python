# Hypotheses and Analysis Plan Template

## Status and use

This is a preregistration‑style template for a future empirical study. It is not a record of completed experiments or results. Fill in and version the bracketed fields before examining final outcome data. **The current repository's candidate, demand, land‑use, substation, and grid files are synthetic demo inputs** (generated when running the pipeline with `--data-mode demo`). Analyses using these files can test software and demonstrate scenarios but cannot test the empirical hypotheses below. Real‑world data must be supplied to evaluate the hypotheses.

## Study registration

- **Protocol ID/version:** `[assign before confirmatory analysis]`
- **Date approved:** `[YYYY-MM-DD]`
- **Lead and responsible data custodian(s):** `[names/roles]`
- **Study geography/boundary version:** `[boundary source, date, CRS]`
- **Analysis period:** `[start/end, time zone]`
- **Planning horizon and base year:** `[period]`
- **Primary study population / charging modes:** `[vehicle categories, public/private scope]`
- **Data authorization, privacy, and ethics review:** `[reference or not applicable with reason]`
- **Code revision and environment lock:** `[commit and lockfile]`
- **Data manifest and protocol hash:** `[path/hash]`
- **Deviations from this plan:** `[none initially; record dated deviations and reasons]`

## Research questions and hypotheses

### Primary question

Among sites that meet documented land, access, and grid eligibility criteria, what cost–access trade-offs are available for public EV charging portfolios under measured or transparently derived spatial demand in `[study boundary]` during `[reference period]`?

### Primary hypothesis (only after the demand and road-validation gates pass)

**H1:** Under equal budget, charger mix, station-count constraints, candidate set, service rule, and demand inputs, the selected multi-objective portfolio provides greater `[predefined primary access metric]` than `[predefined comparator]` without exceeding the declared feasibility constraints.

- **Primary comparator:** `[ranked suitability / demand-greedy / other]`
- **Estimand:** `[difference in percentage points, travel-time reduction, or another defined quantity]`
- **Practical effect threshold:** `[minimum change considered decision-relevant, justified before analysis]`
- **Uncertainty interval/test:** `[define and justify; do not use optimizer seeds as sampling uncertainty]`

The hypothesis must be revised if no valid observed/derived spatial demand is available. For synthetic data, call the output a software demonstration, not a test of H1.

### Secondary questions and conditional hypotheses

- **H2 — Travel impedance:** Replacing uncalibrated speed assumptions with independently measured, time-specific travel times changes the feasible portfolio or access metric by `[prespecified materiality threshold]`. Test only with matched link/time observations and a defined held-out sample.
- **H3 — Robustness:** A specified subset of sites remains selected across evidence-supported measurement and parameter uncertainty ranges. Define portfolio overlap (for example, Jaccard similarity) and a decision-relevance threshold before evaluating results. A high frequency under arbitrary perturbations is not evidence of empirical robustness.
- **H4 — Spatial distribution:** Population-weighted access gaps differ from demand-weighted gaps across `[prespecified area groups]`. Test only after confirming official population denominators, boundary compatibility, small-area coverage, and the substantive equity estimand.
- **H5 — Grid feasibility:** A portfolio passes the stated operational scenarios when evaluated on an authorized and baseline-validated network model. Utility review/approval is a separate outcome and cannot be inferred from simulation compliance.
- **H6 — Site viability:** A prespecified fraction of model-ranked candidate sites pass independent parcel/access/permission checks. Specify sampling design, minimum pass fraction, nonresponse treatment, and evidence standard in advance.

Do not run every exploratory metric and later select the one that appears favorable. Mark analyses as confirmatory, secondary, or exploratory before looking at final outcomes.

## Population, sampling, and partitions

Specify:

- Sampling frame for sessions, vehicles, traffic observations, sites, and grid operating states.
- Inclusion/exclusion rules, observation duration, operator/area/time coverage, and nonresponse.
- Whether sampling is clustered by station, operator, road, day, or season.
- Calibration/training partition and holdout partition; avoid splitting repeated observations from one station or one time cluster across train and test if that would leak information.
- Spatial and temporal validation scheme, including buffer/embargo rules where nearby observations are correlated.
- Minimum required coverage and the action to take when a source fails it.

Use a spatially and temporally independent holdout where data quantity permits. If only one small sample exists, report that validation is exploratory and avoid generalization claims.

## Definitions and primary estimands

Complete before running production analysis:

| Item | Prespecified definition |
|---|---|
| Demand quantity | `[kWh, charging events, vehicles, trips, or population; source and reference period]` |
| Service impedance | `[directed network travel time/distance; time-of-day; access mode]` |
| Access threshold(s) | `[one primary threshold and justified secondary thresholds]` |
| Access denominator | `[total valid weighted demand/population; exclusions and missingness]` |
| Cost | `[currency and price year; CAPEX, land, grid, replacements, OPEX, discounting]` |
| Grid feasibility | `[base/peak/contingency scenarios and authorized limits]` |
| Feasible portfolio | `[station counts, charger count/type, budget, land, electrical, and service constraints]` |
| Candidate eligibility | `[land/access/permission/permit/exclusion rules and proof required]` |
| Equity comparison | `[area grouping, population denominator, access measure, disparity statistic]` |
| Material difference | `[decision-relevant effect threshold with rationale]` |

Do not compare percentages with different denominators or cost values in different price years without explicit conversion.

## Analysis sequence

1. Freeze a source/transform manifest and record protocol/code/configuration versions.
2. Apply the data-readiness gates; publish a missingness and coverage report before optimization.
3. Produce descriptive data checks by source, time, geography, and relevant vehicle/road/site/grid category.
4. Estimate or prepare demand using the prespecified method. Quantify measurement and derivation error separately from modeled scenarios.
5. Construct and validate directed road travel impedance. Report snap distances, disconnected demand points, observed-versus-modeled travel-time errors, and class/time strata.
6. Screen candidate sites using documented hard exclusions; publish counts and reasons at a privacy-safe level.
7. Run the prespecified primary optimizer, fixed baselines, and small-instance correctness tests with matching constraints.
8. Evaluate all feasible Pareto alternatives. Apply a decision rule fixed before reviewing the final outcomes; otherwise present the front without choosing a winner.
9. Run prespecified secondary uncertainty, equity, grid, and site-validation analyses only where their evidence gates pass.
10. Run exploratory analyses separately and label them clearly; do not use them to retroactively validate the primary hypothesis.
11. Export complete tables, diagnostics, run manifest, definitions, and limitations. Re-run from the documented environment to check reproducibility.

## Model comparison and multiplicity

- Use identical inputs and feasible decision sets across optimizer and baselines.
- State whether baselines optimize the same objectives or are merely ranking heuristics.
- On small instances, compare NSGA-II objective values and feasibility with enumeration or a trusted exact solver; report optimality gap/runtime if available.
- Run multiple fixed, recorded seeds to assess algorithmic repeatability. Do not treat these repeated solver runs as independent data samples or confidence intervals.
- Identify the primary comparison. Report secondary outcomes and multiple comparisons transparently; adjust or qualify confirmatory inference where appropriate.

## Missing data, exclusions, and deviations

For each input, prespecify:

- Missingness handling and whether the affected record/area is excluded.
- Treatment of outliers, duplicated IDs, invalid geometries, unlocated activity, censored sessions, and incomplete operator coverage.
- Whether any imputation is permitted; method, predictors, uncertainty, and sensitivity check.
- Conditions that stop the study rather than trigger a silent default or success-shaped fallback.
- How protocol deviations will be dated, justified, and separated from the initial plan.

Never impute empirical demand, land feasibility, or grid headroom from synthetic demo values.

## Interpretation template

Use language of this form, filling only with supported values:

> In `[geography]` over `[period]`, using `[data sources/classes]` and `[validation design]`, the modeled portfolios produced `[defined outcome]` under `[constraints/scenarios]`. The estimate is conditional on `[major assumptions]`; `[validation evidence]` supports/does not support `[specific inference]`. It does not establish `[unsupported claims such as measured future utilization, a construction recommendation, or utility approval]`.

## Analysis completion checklist

- [ ] Protocol frozen before final outcome inspection.
- [ ] Data permissions, source licenses, data classes, and hashes recorded.
- [ ] Study boundary, time period, definitions, units, and denominators fixed.
- [ ] Coverage, missingness, and data-quality report reviewed.
- [ ] Demand and travel validation/holdout scheme completed or limitations disclosed.
- [ ] Candidate eligibility and grid evidence are independently reviewed.
- [ ] Baseline fairness and small-instance model checks reported.
- [ ] Uncertainty sources and distributions justified; algorithm variability kept distinct.
- [ ] All primary, secondary, exploratory, and null findings reported.
- [ ] Output manifest, reproducibility steps, and claim boundaries included.

## Related documents

- [Research protocol](research_protocol.md)
- [Threats to validity and claims](threats_to_validity_and_claims.md)
- [Data acquisition and validation plan](data_acquisition_and_validation.md)
- [Research improvement roadmap](research_improvement_roadmap.md)
