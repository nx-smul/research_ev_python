# Data Acquisition and Validation Plan

## Purpose and current status

This plan translates the research protocol into data collection, acceptance, and validation work. **The default pipeline run uses synthetic demo data** (triggered with `--data-mode demo`). These generated candidate, demand, road, land‑use, substation, and grid files are synthetic demonstration data; their sidecars explicitly identify them as such. Real‑world evidence (observed charging demand, validated traffic counts, authoritative site/parcel inventory, and a utility‑authorized distribution grid model) is not included in the repository and must be supplied for a production‑grade run.

The source register in [`data/context/input_acquisition_register.csv`](../data/context/input_acquisition_register.csv) tracks high-level gaps. Update that register as evidence is acquired, but preserve source files, versions, licenses, and decisions in the run-specific data manifest as well.

## Acquisition principles

1. Contact primary data custodians and obtain written permission, the data-use terms, and a named responsible contact before using restricted data.
2. Prefer dated, geographically explicit measurements to citywide totals or undocumented proxies.
3. Record source-native fields and units before transformation. Never silently convert, impute, or reclassify observed data.
4. Keep immutable raw data separate from cleaned/derived products. Record hashes, retrieval date, software/code version, parameters, and transformation lineage.
5. Distinguish `observed`, `official_source`, `derived_from_observed`, `community_mapped`, `assumed`, and `synthetic_demo`. Only the first three are currently eligible in the real-data input gate; eligibility still does not prove truth or quality.
6. Document missingness, selection bias, geocoding precision, temporal mismatch, representativeness, and license constraints.
7. Align all layers to an explicitly declared study boundary. A bounding-box overlap is a basic check, not proof that each demand origin has a connected, valid route.

## Priority datasets and minimum acceptance requirements

| Priority | Dataset | Preferred custodians / route | Minimum content and acceptance checks | Use / blocking issue |
|---|---|---|---|---|
| Critical | Public charging sessions and energy | Charging operators, relevant ministry/agency, research partnership | Station/location ID, timestamp/time zone, energy (kWh), connector/power, anonymized session ID, operational status, sampling period and coverage; privacy approval; duplicate, missingness, outlier and station-coverage audit | Demand and queue calibration. No verified open location-level session dataset currently available. |
| Critical | Spatial EV fleet/activity | BRTA and statistical agencies; fleet/operator records; ethically collected surveys where necessary | Vehicle category and definition, count/reference date, spatial unit and boundary, registration vs active use distinction, sampling/coverage, documented allocation method | Demand proxy/scenario only if charging-session observations are unavailable; do not equate national/registered counts to active local charging demand. |
| High | Classified traffic and travel-time observations | Transport coordination authority, transport projects, field counts, probe/operator partnership | Road/link or junction ID and coordinates, direction, timestamp, count duration, vehicle class, count, speed distribution, PCU method, weather/events if relevant | Calibrate time-dependent travel impedance. Keep OSM tags and inferred values separate from measured traffic. |
| Critical | Candidate parcels and land feasibility | RAJUK/municipal authorities, landowners, site surveys | Stable site/parcel ID, polygon, access, current use/zoning, exclusion constraints, owner/consent or public status, lease/transaction evidence and date, parking/construction/permit status | Candidate eligibility and cost. An illustrative point or broad land-use polygon is not a feasible site. |
| Critical | Distribution grid model and operating state | DPDC/DESCO or authorized utility custodian | Georeferenced bus/feeder/transformer topology, line/transformer ratings, baseline loads and voltage, time/reference date, substation and feeder ID, protection/operational constraints, model version and authorization | Grid feasibility and hosting-capacity analysis. Generic pandapower examples are not utility models. |
| High | Charger technology and local costs | Operators, procurement records, manufacturers, tariff/market sources | Power, connector, utilization/duty constraints, reliability, purchase/installation/maintenance/replacement cost, currency/base year, tariff, source date | Cost and capacity assumptions. Distinguish quoted, contracted, and illustrative prices. |
| Medium, conditional | Population and equity boundaries | Bangladesh Bureau of Statistics and DNCC/DSCC | Licensed small-area population tables, stable identifiers, boundary files/version, reference period, denominator definitions, suppressed values and geographic crosswalks | Population-weighted access and distributional assessment. Do not substitute citywide aggregates or a spatial access proxy for socioeconomic equity. |
| Context only | Existing public charging and fuel facilities | OSM and operator/custodian inventory | Geometry, facility identity, connector/power/capacity, public access, operating status, source/date and independent verification | Context or network supply, only after completeness/operational status is assessed. OSM absence is not evidence of absence. |

## Data-specific collection notes

### Charging demand and vehicle activity

Request an aggregate extract where possible rather than personally identifiable sessions. Include all participating operators or document coverage by operator and geography. Establish whether energy is delivered, requested, or estimated; whether unsuccessful sessions and private chargers are represented; and how vehicle categories map to the public-charging use case. Use a holdout time period or stations for validation. Do not allocate a Dhaka-wide total across wards by population unless that allocation is explicitly treated as a weak scenario and its consequences are tested.

### Traffic and road travel time

Match observed count locations to network links with documented positional tolerance and link direction. Keep counts by vehicle class and sampling interval; preserve the PCU conversion formula and source. Validate routing connectivity, one-way restrictions, travel-time distributions, and disconnected origins. Report model error against held-out observations by road class/time period. OSM `maxspeed`, lane, or traffic-flow fields must not be called measured unless the source and measurement process establish that status.

### Candidate land and site feasibility

Maintain a candidate rejection log with a reason and evidence date. Distinguish public land, private parcels with permission, candidate access points, and illustrative points. Confirm road access, zoning, safe access, flood/environmental constraints, landholder consent, grid connection, construction constraints, and permitting. Do not publish sensitive owner details.

### Distribution grid

Obtain utility authorization and agree on a safe publication level. Check model version, topology consistency, nominal voltages, units, ratings, baseline loading, missing assets, and time alignment with charging scenarios. Validate a baseline power flow against utility-provided voltage/loading observations where permitted. Record whether load growth, contingencies, and reinforcement are modeled; a pass against configured generic thresholds is not evidence of hosting capacity approval.

## Cross-dataset harmonization and validation

Before modeling:

- Declare the study boundary, CRS, spatial precision, time zone, and reference period.
- Confirm valid geometries, coordinate bounds, expected geometry types, stable unique IDs, and documented duplicate handling.
- Normalize fields without overwriting source-native values; retain unit conversion and category crosswalks.
- Check demand/candidate/road/grid spatial coverage and report the number of demand origins with no valid network snap, excessive snap distance, shared nodes, or disconnected paths.
- Check temporal compatibility: demand, traffic, costs, grid loads, land status, and population must refer to compatible periods or have an explicit scenario bridge.
- Quantify missingness, class imbalance, positional uncertainty, sample coverage, and likely selection bias.
- Independently inspect a stratified sample of geocodes and transformations.
- Run schema and range validation plus domain checks; a valid schema is not evidence that observations are representative or authoritative.

The current preflight compares demand/candidate locations with the road-network extent. For research readiness, extend this to actual study-boundary polygons, network snapping/connectivity, road attribute provenance, time coverage, and grid candidate connectivity. Record warnings and diagnostics in machine-readable form.

## File layout and provenance record

Retain the project's established source paths for pipeline inputs. Preserve source-native downloads in a versioned raw archive or immutable object store; place cleaned files in derived locations and keep transformations in code. Do not overwrite synthetic demo files with real data until the true origin, license, schema, and tests of the replacement are confirmed. Consider a separate `data/real/` staging area or explicit configuration to avoid accidental mixing.

Each input sidecar must include:

```json
{
  "source_url": "https://primary-custodian.example/dataset",
  "license": "Exact license or written agreement reference",
  "retrieved_at": "YYYY-MM-DD",
  "coverage": "Geographic extent and temporal period",
  "units": "Units of every modeled field",
  "transformation": "None, or a versioned and reproducible transformation description",
  "data_class": "observed"
}
```

Use `official_source` for an authentic public/official dataset and `derived_from_observed` for a reproducible derivation from documented observations. State contact/release/version and caveats in a companion manifest when the sidecar schema is extended. A sidecar documents claims; verify the source and rights separately. The repository's six demo input sidecars use `data_class: synthetic_demo` and `generated_at`; they must not be edited to claim observational status.

## Acceptance gates for a real-data run

- Every required input exists and its provenance/classification is eligible.
- Custodian, access authority, and license are verified and reusable for the planned analysis/publication.
- Domain schema checks pass; all required units, IDs, geometry, and date fields are defined.
- Study boundary and CRS are explicitly aligned; material spatial/temporal coverage gaps are resolved or bounded.
- Demand and travel assumptions are documented, calibrated where data permit, and kept distinct from measured values.
- Candidate and grid evidence are sufficiently specific for the intended claims.
- A reviewer can reproduce all transformations from source inputs and can interpret the run manifest and report.

If a gate cannot be met, narrow the research question, state the limitation, and report scenario results only. Do not mark data “real” merely to make the CLI proceed.

## Related documents

- [Research protocol](research_protocol.md)
- [Research improvement roadmap](research_improvement_roadmap.md)
- [Project data register](../data/context/input_acquisition_register.csv)
- [Project README](../Readme.md)
