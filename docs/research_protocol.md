# Research Protocol: EV Charging Siting in Dhaka

## Protocol status

This is a proposed protocol for a future evidence-supported study, not a report of completed empirical work. The repository currently contains synthetic demonstration inputs and contextual snapshots, but no verified location-level charging demand or utility-authorized distribution-grid model. Until the evidence gates below are met, results must be presented as scenario demonstrations and data-readiness findings, not as validated optimal locations.

## Proposed title

**Evidence-Constrained Planning of Public Electric-Vehicle Charging Infrastructure in Dhaka: A Multi-Objective, Network-Aware and Distribution-Grid-Constrained Study**

## Study purpose

Develop and validate a transparent decision-support method for identifying candidate public charging locations and station portfolios under observed travel demand, feasible land access, and distribution-network constraints. Evaluate trade-offs among demand access, investment cost, network performance, and spatial equity. Do not interpret modeled site rankings as a construction recommendation without independent field, landowner, utility, and operator validation.

## Research questions

1. Under measured or defensibly estimated spatial charging demand, how do feasible station portfolios trade off demand accessibility and total life-cycle cost?
2. How much do candidate selection and demand coverage change when road travel times, charger mix, service radius, budget, and demand assumptions vary within evidence-based ranges?
3. Where are modeled access gaps, and do those gaps persist when access is population-weighted using compatible, appropriately licensed small-area demographic data?
4. Which candidate locations remain feasible under authorized feeder, transformer, voltage, and thermal limits?
5. How much do results change when candidate parcels, charger availability, utility connections, or current charging facilities are confirmed or rejected during field validation?

Questions 3–5 are conditional on obtaining the corresponding demographic, land, grid, and validation evidence. They must not be answered with synthetic substitutes presented as observations.

## Scope and unit of analysis

- **Geographic scope:** declare the municipal/study boundary, reference date, and coordinate reference system before analysis. Do not assume a single road-network bounding box is a sufficient study-area boundary.
- **Demand unit:** a spatial demand cell or validated origin with an explicit temporal period and an observed or documented derivation of energy/charging demand.
- **Candidate unit:** an identified, georeferenced, legally and physically plausible parcel or site with a source, access status, land constraint, and field-verification status.
- **Network unit:** a directed road link for travel analysis and an authorized electrical bus/line/transformer representation for grid analysis.
- **Decision unit:** the selected candidate portfolio and charger allocation for a declared budget, planning period, charger technology set, and service standard.

The geographic extent, time period, facility types, vehicle classes, and treatment of private versus public charging must be defined in the study protocol before estimation.

## Conceptual workflow

1. **Define the decision and evidence boundary.** Specify the intended users, geography, planning horizon, charging modes, service criteria, cost perspective, and claims the study will and will not make.
2. **Acquire and register inputs.** Record source, custodian, license, retrieval date, geographic/time coverage, units, transformations, quality flags, and intended role for every dataset.
3. **Validate and harmonize data.** Validate identifiers, geometries, coordinate systems, temporal coverage, units, gaps, duplicates, and study-boundary alignment. Preserve raw source files and transformations separately.
4. **Estimate demand transparently.** Prefer anonymized observed charging sessions and vehicle activity. If a proxy is unavoidable, publish its derivation, uncertainty, category coverage, spatial allocation, and a sensitivity range. Do not derive neighborhood demand by simply distributing citywide vehicle totals.
5. **Build and calibrate travel impedance.** Use directed road paths and measured time/speed observations where available. Separate mapped geometry from observed speed and from assumed speed/traffic values.
6. **Screen feasible candidate sites.** Apply documented land-use, access, parcel, ownership/consent, construction, safety, and permitting criteria. Record exclusions and reasons.
7. **Evaluate alternatives.** Compare the multi-objective optimizer with transparent baselines and, on small instances, an exact or independently implemented solution. Report Pareto alternatives, not only a selected “winner.”
8. **Check grid feasibility.** Use utility-authorized topology, ratings, baseline loads, and operating conditions. A simulation against generic limits is a screening result, not utility validation.
9. **Quantify uncertainty and equity.** Propagate uncertainty from inputs and model parameters; report subgroup access only with compatible denominators and boundaries. Distinguish spatial coverage from socioeconomic equity.
10. **Validate independently.** Use held-out observations where possible, field audits for candidate feasibility, and utility/operator review for electrical and operational assumptions.
11. **Publish reproducible artifacts.** Archive the protocol version, data manifest, configuration, software versions, code revision, run identifier, outputs, and limitations.

## Outcomes and metrics

Predefine each metric, its unit, denominator, and interpretation before a production analysis.

| Outcome | Definition to specify | Evidence needed |
|---|---|---|
| Demand access/coverage | Share of documented demand served within a declared network-time or distance standard; state whether demand is energy-, trip-, or vehicle-weighted | Spatial demand, travel impedance, service rule |
| User travel burden | Network travel time/distance under a stated assignment and time period | Validated origins, destinations, directed network and calibration observations |
| Capital and life-cycle cost | Cost components, currency/base year, discount rate, asset life, replacement, land, connection, and operations treatment | Dated local prices, tariffs, technology and land evidence |
| Electrical feasibility | Voltage, line/transformer loading, hosting capacity, and contingencies under declared operating scenarios | Authorized grid model and baseline/forecast loads |
| Spatial equity | Population-weighted access or a prespecified distributional statistic over comparable areas | Official small-area population and harmonized boundaries; selected equity definition |
| Portfolio stability | Site/portfolio selection frequency or overlap across specified perturbations and optimizer seeds | Repeated deterministic runs; scenario distributions justified by evidence |
| Candidate feasibility | Share of modeled sites confirmed available, accessible, and permitted | Dated site/landowner/agency field validation |

Avoid presenting a single composite score without the criteria, normalization, weights, sensitivity, and stakeholder rationale that produced it.

## Modeling and comparison plan

- Retain NSGA-II as a search method only if tests establish its implementation behavior and independent comparisons show acceptable performance for representative instances.
- Compare solutions against interpretable baselines (for example, ranked suitability and demand-greedy selection) using equal budget, station count, charger assumptions, and feasibility rules. Describe baseline differences accurately.
- On small instances, enumerate feasible portfolios or use a trusted exact formulation as a correctness check. State the instance size and optimality gap where known.
- Test feasibility invariants: station limits, charger counts, budget, demand assignment, reachability, and electrical thresholds.
- Calibrate travel times and demand assignment against held-out measured observations when data permit; report error metrics, sample design, and time/geographic split.
- Select a final alternative through a documented decision process with stakeholder rationale. The algorithm does not choose policy preferences.

## Uncertainty and sensitivity plan

Separate:

- **Measurement uncertainty:** sampling, location error, missing observations, and sensor/session coverage.
- **Parameter uncertainty:** cost, service standards, demand growth, charger power, and measured travel-time variation.
- **Scenario uncertainty:** policy, technology, budget, land availability, and grid reinforcement alternatives.
- **Algorithmic variability:** optimizer seed, population, stopping criteria, and implementation.

Set parameter ranges from measurement uncertainty, published evidence, operator/utility input, or explicit expert elicitation. Label elicited values and do not imply probability distributions are empirical if they are not. Report the distribution of outcomes and portfolio overlap, not just a mean or “stable” ranking. Current Monte Carlo screens and seed comparisons are exploratory algorithm/scenario checks, not empirical validation.

## Evidence and release gates

Do not label a result “real-data,” “validated,” or “optimal” solely because files have provenance sidecars or the optimizer completed.

1. **Data-readiness gate:** required data are present; source, license, date, units, coverage, and transformations are recorded; schemas and spatial/temporal coverage are validated.
2. **Demand gate:** demand has a defensible observational or documented derivation basis, and its category and temporal limitations are quantified.
3. **Travel gate:** road topology and travel impedance have appropriate coverage; assumed attributes remain identifiable; calibration is reported where measurements exist.
4. **Site gate:** candidate sites have a documented eligibility basis and independent availability/feasibility status.
5. **Grid gate:** utility-authorized model and operating assumptions are reviewed; simulated outcomes are distinguished from utility approval.
6. **Model gate:** tests, baseline comparisons, small-instance checks, sensitivity analysis, and reproducibility artifacts are published.
7. **Claim gate:** conclusions are bounded to the evidence, geography, period, and scenarios actually analyzed.

## Ethics, privacy, and responsible use

- Obtain authorization and ethics/privacy review before collecting or processing potentially identifiable charging, mobility, or landowner information.
- Minimize and aggregate session or mobility data; document de-identification risks, retention, access, and disclosure controls.
- Respect source licenses, community mapping attribution, data-custodian restrictions, and local legal requirements.
- Do not expose sensitive infrastructure details or individual travel traces in public exports.
- Report who may benefit or be excluded, and avoid labeling a spatial access proxy as equity without relevant population and distributional evidence.

## Current interpretation

The present repository supports software testing, synthetic scenario exploration, and research preparation. The OSM road archive is community-mapped geometry, not measured traffic. The small charger map is not a complete operational inventory. The synthetic candidate/demand/grid inputs are not evidence of actual Dhaka sites, charging behavior, land cost, utility capacity, or feasibility. Use `--data-mode demo` for demonstration; use a real-data run only after satisfying the input and evidence gates above.

## Related documents

- [Research improvement roadmap](research_improvement_roadmap.md)
- [Data acquisition and validation plan](data_acquisition_and_validation.md)
- [Project data register](../data/context/input_acquisition_register.csv)
- [Source-reported context and limitations](../data/context/source_reported_metrics.csv)
- [Project README](../Readme.md)
