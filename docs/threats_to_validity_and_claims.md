# Threats to Validity and Claim Boundaries

## Purpose

This document is a project-specific checklist for evaluating what an EV charging siting analysis can support. It should be completed for each empirical run. The current repository run artifacts and mapped context do not remove the evidence gaps described below.

## Current evidence boundary

The repository includes synthetic demo candidates, demand, land-use, substation, and grid model inputs; an archived OpenStreetMap road snapshot; a small community-mapped charging snapshot; and secondary-source contextual statistics. The OSM road geometry is not measured traffic. OSM facility counts are not a complete or operationally verified inventory. No verified location-level charging demand or utility-authorized grid model is currently established. Therefore, demo model metrics are conditional demonstrations, not empirical evidence of Dhaka charging coverage, optimal sites, investment returns, or electrical hosting capacity.

## Threat register

| Threat | Why it matters | Diagnostic / mitigation | Claim boundary until addressed |
|---|---|---|---|
| Demand construct validity | A fleet count, registration total, ridership total, or population total does not directly measure public charging demand by location and time | Obtain anonymized sessions/energy or defensible spatial fleet activity; define vehicle category and public-charge share; quantify coverage and derivation error | Do not claim observed demand, utilization, forecast accuracy, or demand-weighted coverage |
| Spatial sampling/coverage bias | Operator participation, mapped facility, traffic count, or survey coverage may overrepresent central/commercial locations | Publish coverage maps and strata; compare included/excluded areas; use sampling weights only when justified | Do not generalize sample-derived demand to all Dhaka without a coverage argument |
| Temporal mismatch | Demand, traffic, tariffs, land, and grid baselines from different years/seasons may not describe one coherent planning scenario | Record temporal coverage/time zones; align periods or model an explicit bridge; test peak/seasonal periods | Do not describe a static average as current peak or future demand |
| Proxy substitution | Assumed fleet allocation, population allocation, speed, PCU, land cost, or headroom can dominate output | Label attributes at field level; calibrate where possible; perform evidence-based ranges; show contribution to ranking | Do not call proxies measured, official at the modeled resolution, or validated |
| Spatial reference and extent error | CRS mismatch, bad geocoding, poor snapping, or a sparse graph can produce misleading distances and unreachable/misrouted pairs | Validate source CRS and coordinate ranges; inspect stratified points; report snap distance, network connectivity, and uncovered origins against a declared boundary | Do not claim calibrated access or citywide coverage from a bounding-box check |
| Road topology and impedance error | Community mapping or inferred speed/one-way attributes may not match actual traffic conditions | Separate geometry, tags, and measured travel times; check one-way direction, closures, class/time error, and held-out observations | Do not call routed distance/time actual travel time without calibration |
| Candidate construct and selection bias | Generated or convenient candidate points omit parcels that are inaccessible, unavailable, unsafe, or not permitted | Use parcel-level evidence; publish hard-exclusion rules and rejection counts; audit a stratified sample in the field | Do not call ranked points feasible sites or recommend acquisition |
| Land cost uncertainty | Broad neighborhood price assumptions do not equal site-specific lease/transaction and connection cost | Use dated comparable transactions/quotes, parcel attributes, price-year conversion, and range analysis | Do not report investment-grade CAPEX, payback, or affordability |
| Grid model validity | A generic network or nearest-substation proxy cannot represent utility topology, loading, protection, voltage, or hosting capacity | Obtain authorized topology/baseline; validate power flow against observed operating data; secure utility review | Do not claim grid compliance, capacity, or utility approval from configured-threshold simulation |
| Objective and weight subjectivity | AHP weights, service radius, objective scaling, and “knee” selection encode value judgments | Elicit and document stakeholders; publish pairwise matrix/consistency; compare alternatives under plausible weights and decision rules | Do not call a composite ranking objectively optimal |
| Algorithmic validity | NSGA-II can converge to an incomplete/biased Pareto set or return seed-dependent portfolios | Test invariants, repeat fixed seeds, compare against baselines and exact small-instance solutions, report convergence/runtime | Do not equate optimizer completion or repeatability with global optimality |
| Baseline unfairness | A heuristic baseline may use different constraints or objective information | Match site set, budget, station count, charger mix, demand, and feasibility; state diagnostic limitations | Do not claim superiority unless comparison is aligned and predeclared |
| Model-form uncertainty | Distance decay, queue assumptions, temporal profiles, energy/service rules, and grid upgrade heuristics may be misspecified | Justify from evidence; compare alternative forms; test residuals and fit; report limitations | Do not imply scenario profiles or queues are observed or predictive |
| Equity measurement error | Access by zone without suitable population denominators or social indicators is not socioeconomic equity | Use matched official small-area data, denominators, spatial crosswalks, and stakeholder-defined fairness criteria | Do not describe an unweighted zone access proxy as equitable or inequitable |
| Software/implementation error | Correct-looking maps and output files can conceal unit, indexing, CRS, or numerical errors | Unit/domain tests, property tests, deterministic fixtures, independent calculations, artifact schema checks, code review | Do not infer scientific validity from software tests alone |
| Reproducibility and provenance overclaim | A sidecar is a declaration, not proof of origin, accuracy, or rights | Verify custodian/release/license; hash inputs and transformations; preserve raw data; record run environment and protocol | Do not say “verified data” when only a sidecar/schema check passed |
| Privacy and disclosure | Location/time traces, operator data, or sensitive assets may identify individuals or create infrastructure risk | Minimize, aggregate, obtain review/permission, suppress small cells, control access, and assess re-identification | Do not publish raw session traces or restricted network detail |

## Claim ladder

Use the strongest claim whose evidence gate is actually met:

1. **Software demonstration:** synthetic data and code exercise pipeline behavior; no inference about real places or demand.
2. **Mapped-context description:** community-mapped objects or archived geometry are described with coverage/date and incompleteness caveats.
3. **Scenario result:** a conditional model result is reported for explicit inputs/assumptions, with no prediction or empirical validation implied.
4. **Evidence-supported estimate:** specified observed/derived data and validation support a bounded estimate for a defined population, geography, and period.
5. **Operationally reviewed option:** evidence-supported result has passed site, operator, land, and utility review; it is still not a final investment/permit decision unless authorized bodies decide so.

Passing provenance and schema checks alone does not move a result from one level to another.

## Per-run claim review

Before publication, document:

- **Run and protocol:** run ID, code revision, protocol version, analysis period, geography, and decision context.
- **Data class:** observed, official, derived, community mapped, assumed, synthetic; identify any mixed-class fields.
- **Coverage:** spatial/temporal sample, missingness, study-boundary exclusions, disconnected/unsnapped origins, and site-screening losses.
- **Validation:** demand, travel-time, candidate feasibility, cost, and grid validation data/design/results; identify unavailable validations explicitly.
- **Comparisons:** primary comparator, matched constraints, exact small-case benchmark where applicable, and algorithm seeds/stopping rule.
- **Uncertainty:** which uncertainty types are represented, distributions/ranges and their evidence basis, and important omitted sources.
- **Equity/privacy/licensing:** denominator and definition, subgroup coverage, permissions, suppression, and reuse constraints.
- **Claims:** mark every statement as descriptive, scenario-based, predictive, causal, comparative, or normative; justify each type separately.
- **Limitations:** list the largest threats that could change the site/portfolio ranking and what evidence would resolve them.

## Recommended wording

Prefer:

- “The configured scenario allocates modeled demand to these candidate points.”
- “The site ranking changes under the tested assumptions.”
- “The OSM snapshot contains these mapped objects as of the recorded retrieval date.”
- “The power-flow model passes the configured limits; the model has not been validated against utility operating measurements.”
- “This is a spatial access proxy, not a socioeconomic equity measure.”

Avoid unless independently established:

- “These are the optimal sites for Dhaka.”
- “This percentage of Dhaka EV demand is covered.”
- “Traffic conditions show…”
- “This substation has capacity for…”
- “The result proves equitable access or financial viability.”

## Related documents

- [Research protocol](research_protocol.md)
- [Hypotheses and analysis plan template](hypotheses_and_analysis_plan.md)
- [Data acquisition and validation plan](data_acquisition_and_validation.md)
- [Research improvement roadmap](research_improvement_roadmap.md)
