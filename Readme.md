# Dhaka EV Charging Siting Research

A Python research pipeline and React dashboard for exploring candidate public EV charging locations in Dhaka. The project ranks sites, optimizes a station portfolio, estimates road-network accessibility, and screens grid impacts. It is a research prototype—not an investment recommendation or validated utility study.

## Data status

**No location-level observed EV charging demand, validated Dhaka traffic counts, or utility-authorized distribution-grid model is currently available in this repository.** The default full run requires provenance-documented inputs and stops when evidence is missing. Never describe demo outputs as measured demand, traffic, land prices, or utility capacity.

The default demo generator creates synthetic inputs solely for tests, UI exploration, and method demonstrations. Use `--data-mode demo` explicitly. OSM roads and facilities are separately archived source snapshots; they are not silently mixed into demo inputs. OSM routing uses mapped geometry and connectivity, but any absent speed, lane, or traffic-flow attributes are estimates—not traffic observations. See `data/context/input_acquisition_register.csv` for evidence still needed and `data/context/source_reported_metrics.csv` for contextual figures and limits.

The repository's OSM EV-charger snapshot contains only community-mapped objects. It does not establish a complete inventory or confirm a facility's current operation or capacity. OpenStreetMap data are licensed under ODbL 1.0; attribute OpenStreetMap contributors and comply with the license when reusing or redistributing the snapshot.

## Workflow

1. Validate required data and provenance sidecars.
2. Rank supplied candidate sites using configured AHP/TOPSIS criteria.
3. Route demand-to-site pairs on the supplied directed road graph.
4. Search cost/accessibility trade-offs with NSGA-II.
5. Run the available DPDC-form power-flow screen and export maps, tables, a report, and a manifest.

The optimizer solves a scenario defined by its inputs; it does not estimate EV demand from population or national registration counts. The included grid network and demo candidate, demand, road, and substation files are synthetic.

## Setup

Python 3.10 or later is recommended. Install the repository dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm --prefix web ci
```

The Python requirements include the spatial and grid packages needed by the full demo pipeline.

## Run

The default command requests a real-data run and reports missing inputs rather than generating them:

```bash
python main.py --mode full
```

Run an explicitly synthetic demonstration:

```bash
python main.py --mode full --data-mode demo
```

Generate synthetic demo inputs without running the analysis:

```bash
python main.py --mode data
```

Use a scenario/settings overlay, adjust optimizer effort, or run sensitivity cases:

```bash
python main.py --mode full --data-mode demo \
  --config configs/default_config.yaml \
  --settings configs/user_settings.yaml \
  --population 60 --generations 120 --sensitivity
```

Existing CLI options and the established `results/` CSV, GeoJSON, report, and manifest outputs are retained. Sensitivity files compare modeled scenarios and optimizer seeds; they are not observed data or empirical site validation.

## Web dashboard

Start the read-only API and frontend in separate terminals:

```bash
uvicorn api.app:app --reload --port 8000
npm --prefix web run dev
```

The dashboard defaults to the API at `http://localhost:8000`. Set `VITE_API_URL` for a separately deployed API and configure `EVCS_CORS_ORIGINS` with the exact frontend origins. Set `EVCS_DATA_ROOT` to the repository/data root used by the API. The live OSM map is an optional community-map overlay, not a charging-demand input or a live charger-status feed.

The dashboard labels synthetic demo runs and shows a run-scoped input/provenance inventory when the manifest provides one. Coverage, costs, and grid values are scenario outputs conditional on inputs and assumptions—not measured utilization or utility-validated forecasts. A provenance sidecar is a declaration, not independent authentication. Older manifests without an evidence summary are shown as unknown.

## Inputs and provenance

For a real-data run, supply every path listed in `REAL_DATA_REQUIRED_INPUTS` in `src/pipeline.py`, using the required schema and a sibling `<filename>.provenance.json`. Each real-data sidecar must include:

`source_url`, `license`, `retrieved_at`, `coverage`, `units`, `transformation`, and `data_class` (`observed`, `official_source`, or `derived_from_observed`).

The sidecars alongside the checked-in demo inputs document their actual classification as `synthetic_demo`; they are not evidence for a real-data run. Demo sidecars use `generated_at` rather than `retrieved_at`. Replace both the synthetic input and its sidecar with a genuine dataset and accurate source metadata before attempting a real-data run.

Road layers must include per-feature `maxspeed_source`, `lanes_source`, and `pcu_source` labels. Preflight checks verify declared metadata, required schemas, unique identifiers, numeric ranges, geographic coordinate bounds, and candidate/demand alignment with the road-network extent. The optimizer also rejects inconsistent OD matrix shapes, non-finite or negative values, non-positive total demand, and invalid candidate identifiers. These checks catch incompatibility and corruption but do not authenticate source claims. Validate licenses, measurements, spatial coverage, and transformations with the original data custodian before making empirical claims.

The current OSM archive at `data/raw/osm_dhaka_roads_osm.geojson.gz` is a source snapshot; `data/raw/osm_dhaka_roads.geojson` is a synthetic demo network. The archive can be loaded directly by `OSMRoadNetwork`, but the real-data pipeline still requires real candidate, demand, zoning, substation, and grid inputs.

## Repository layout

```text
api/                  FastAPI dashboard data and live-OSM endpoints
configs/              Optimization scenarios and user overrides
data/context/         Source-reported context and acquisition register
data/raw/             Demo inputs and archived source snapshot
data/processed/       Demo candidates, demand, and routing matrix
data/grid_models/     Synthetic DPDC-form demo network
results/              Dashboard artifacts, reports, and run manifests
src/grid/             Power-flow and grid-limit screening
src/optimization/     NSGA-II, cost, baseline, and scenario analyses
src/spatial/          AHP/TOPSIS, spatial filters, and road routing
src/visualization/    Static maps and Pareto plots
web/                  React/MapLibre dashboard
```

## Validation

```bash
pytest
npm --prefix web test
npm --prefix web run build
```

## Latest Updates (2026‑10‑18)

- **Frontend fixes**: Added `candidate_id` to `filterCandidates` text search, corrected metric formatting, restored error/loading UI, and fixed workspace toast quoting.
- **Backend fixes**: Safeguarded dictionary look‑ups in `cost_functions.py`, expanded exact‑solver enumeration to allocate chargers to all open stations, and raised the demo budget cap to realistic values.
- **Documentation**: Updated README and data‑acquisition plan to clarify that the default run uses synthetic demo data (triggered with `--data-mode demo`). Added notes about verification status and test coverage.
- **Verification**: `verify_rewrite.py` now reports 100 % syntax and import success for the refactored codebase.
- **Tests**: All Vitest (22) and pytest (71) tests now pass; the pipeline runs end‑to‑end in demo mode without errors.

These changes bring the project to a stable, fully‑tested state ready for further data collection or methodological extensions.

## Research references

The working bibliography, including source-specific cautions, is maintained at [nx-smul/research-paper_ev `sources.md`](https://github.com/nx-smul/research-paper_ev/blob/main/sources.md). Check primary sources and data licensing before using any citation or measurement in a paper.

## Research planning documents

- [Research protocol](docs/research_protocol.md): proposed research questions, outcomes, validation gates, uncertainty, and claim boundaries.
- [Hypotheses and analysis plan](docs/hypotheses_and_analysis_plan.md): preregistration-style template for hypotheses, estimands, sampling, and analysis decisions.
- [Threats to validity and claims](docs/threats_to_validity_and_claims.md): project-specific bias, validation, privacy, and reporting checklist.
- [Data acquisition and validation plan](docs/data_acquisition_and_validation.md): priority evidence, custodians, minimum fields, quality checks, and real-data acceptance criteria.
- [Research improvement roadmap](docs/research_improvement_roadmap.md): prioritized validity, reproducibility, model, and web improvements with phase exit criteria.

## License

Project code is distributed under the MIT License. Third-party data retain their own licensing terms.
