# Research Improvement Roadmap

## North star

Make the project a reproducible, evidence-aware decision-support study: it should distinguish measured evidence from assumptions, explain why each site is eligible, quantify uncertainty, test algorithmic correctness, and make appropriately limited claims. More sophisticated optimization or map features do not compensate for missing demand, land, traffic, or utility evidence.

## Current baseline

- The Python pipeline supports an explicitly labeled synthetic demo (`--data-mode demo`) and gates real‑data runs on required inputs and provenance declarations. The pipeline has been verified with `verify_rewrite.py` (100 % syntax and import success) and all unit tests now pass.
- The repository includes an archived OSM road snapshot and a small community‑mapped charging‑facility snapshot. Neither constitutes a validated traffic inventory or complete operational charger dataset.
- Candidate sites, demand, land-use, substation and grid demo inputs are synthetic; location-level observed charging demand, measured traffic, authoritative site/parcel evidence, and utility-authorized grid data are not currently established.
- The optimizer has sensitivity and search-stability tooling. Those analyses explore the configured model; they do not validate assumptions against observations.
- The web dashboard exposes run/input interpretation and candidate browsing, but results remain conditional on the underlying evidence and model.

## Prioritized improvements

### P0 — Protect research validity

1. **Obtain primary evidence before claiming real siting results.** Prioritize charging sessions/spatial fleet activity, candidate parcel feasibility, and an authorized distribution model; seek measured road travel-time/count observations and local dated costs in parallel.
2. **Version a research protocol before modeling.** State questions, geography, time horizon, primary outcomes, comparator methods, equity definition, uncertainty ranges, exclusion rules, and claim boundaries. Record protocol changes and reasons.
3. **Separate data classes end-to-end.** Carry `observed`, `official_source`, `derived_from_observed`, `community_mapped`, `assumed`, and `synthetic_demo` labels at feature/field level when sources are mixed. Preserve transformations and source IDs.
4. **Use empirical calibration and holdouts.** Calibrate travel-time and charging-demand assumptions on one sample and test on an independent spatial/time sample. Report error and coverage, not just optimizer output.
5. **Validate site and grid feasibility independently.** Add parcel/landowner/field validation and utility review as explicit statuses; never treat a model score as permission, land access, or grid approval.

### P1 — Make computation reproducible and testable

1. **One machine-readable dataset registry.** Define required/optional inputs, schema, units, CRS, time coverage, source class, transformation, license, quality rules, and hash once. Generate the CLI preflight summary, manifest, dashboard inventory, and documentation views from it.
2. **Stronger spatial/temporal preflight.** Validate against study-boundary polygons rather than a road bounding rectangle; report nearest-node snap distances, disconnected demand origins, coverage by area, temporal alignment, topology issues, and missing attributes.
3. **Independent model correctness checks.** Enumerate small candidate instances or compare against an exact formulation; test feasibility invariants and objective values. Benchmark representative synthetic and later empirical instances with runtime, convergence and quality-gap reporting.
4. **Defensible uncertainty ranges.** Source scenario distributions from observed error, local evidence, or documented expert elicitation. Keep measurement, parameter, scenario, and algorithm uncertainty separate. Do not call a heuristic Monte Carlo screen a confidence interval.
5. **Reproducible run artifacts.** Record code revision, config/settings hashes, input and sidecar hashes, software/platform versions, random seeds, preprocessing lineage, scenario name, output hashes, validation warnings, and protocol version.
6. **Explicit baseline fairness.** Ensure comparisons use the same candidate set, budget, station count, charger technologies, demand, service threshold, and constraints. State when a baseline is only a diagnostic heuristic.

### P2 — Improve decision relevance and responsible use

1. **Predefine meaningful access measures.** Compare network-time standards, demand-weighted access, and population-weighted accessibility only when compatible denominators/boundaries are available.
2. **Report distribution, not one headline score.** Present Pareto alternatives, uncertainty bands, geographic access gaps, unmet demand, and sensitivity of site membership.
3. **Add operational reality checks.** Include public/private access, reliability, connectors, utilization, queueing, parking, safety, permitting, flood risk, construction, and interconnection only with stated evidence/status.
4. **Document stakeholder decision rules.** Let agencies/community/operators review criteria and weights; explain whose preferences they represent and how conflicts are resolved.
5. **Protect sensitive information.** Minimize mobility data, aggregate exports, document privacy review and retention, and use safe disclosure limits for infrastructure and personal data.

### P3 — Improve software and web experience

1. **API contract and artifact validation.** Validate manifests and result tables at the API boundary; return useful versioned errors for missing, stale, malformed, or mismatched run artifacts.
2. **Run selection and comparison.** Allow users to compare two run manifests and inspect input hash/class changes, scenario configuration, and result deltas.
3. **Export reproducible evidence.** Include run ID, metric definitions/units, selected scenario, data class, source, retrieval date, and limitations in CSV/GeoJSON exports.
4. **Accessible exploration.** Maintain sortable/filterable candidate tables, keyboard-accessible map actions, clear focus/contrast, screen-reader descriptions, and non-map alternatives to spatial findings.
5. **Performance and reliability.** Keep MapLibre lazily loaded; measure real bundle/runtime costs, test large feature layers, and add loading/empty/stale/error behavior to API-driven views.
6. **Automated quality gates.** Add CI for Python tests/type or lint checks, frontend tests/build, provenance/schema fixtures, deterministic demo smoke tests, and documentation links.

## Recommended sequence and exit criteria

| Phase | Work | Exit criteria |
|---|---|---|
| 1. Protocol and evidence agreements | Finalize protocol, source registry, data permissions, and target study boundary | Protocol versioned; custodians/permissions and minimum acceptance criteria documented |
| 2. Data readiness | Acquire and harmonize one high-priority dataset at a time; do not mix demo inputs | Required inputs pass schema, license, coverage, and independent spot checks; gaps documented |
| 3. Calibration and validation | Validate demand, routing, site feasibility, and grid baseline against independent evidence | Holdout metrics and review outcomes meet prespecified criteria or claims narrowed |
| 4. Model comparison | Test NSGA-II, baselines, small-instance exact comparisons, and uncertainty | Fair comparisons, reproducible seeds, feasibility checks, convergence/runtime evidence published |
| 5. Decision analysis | Produce Pareto options, access/equity distributions, costs and practical validation status | Stakeholder decision criteria documented; no unsupported single “optimal” claim |
| 6. Release | Publish code, data references/rights, reports, dashboard and limitations | Reproducible manifest; accessible web outputs; licenses/privacy and claim review complete |

## Suggested research outputs

- A protocol and preregistered analysis plan with version history.
- A source and transformation registry with an auditable data-readiness report.
- A validation paper/report covering measurement coverage, calibration, holdout performance, and known biases.
- A methods comparison for multi-objective site selection, including small-instance exact checks.
- Scenario/Pareto results with uncertainty and sensitivity, released only at a safe and permitted level of detail.
- A field and utility validation log documenting accepted, rejected, and unresolved recommendations.

## Do not claim until supported

Do not claim “optimal Dhaka charging locations,” real demand coverage, validated travel times, equitable access, utility hosting capacity, expected financial return, or operational readiness unless the relevant data, methods, independent validation, and limitations support that exact claim. Passing code tests or provenance checks alone is insufficient.

## Related documents

- [Research protocol](research_protocol.md)
- [Data acquisition and validation plan](data_acquisition_and_validation.md)
- [Project data register](../data/context/input_acquisition_register.csv)
- [Project README](../Readme.md)
