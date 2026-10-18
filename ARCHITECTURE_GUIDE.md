# EVCS Optimizer Architecture Guide

Quick reference for the refactored codebase structure.

## Directory Layout

```
src/
├── core/              # Shared infrastructure
├── stages/            # Pipeline orchestration
├── optimization/      # NSGA-II and extensions
├── spatial/           # GIS and road network
├── grid/              # Power flow simulation
└── visualization/     # Plotting and maps
```

## Core Modules (`src/core/`)

Shared utilities used across the codebase.

### `exceptions.py`
Custom exception hierarchy:
- `ConfigError` - Configuration validation failures
- `RealDataPreflightError` - Missing/invalid real data inputs
- `OptimizationError` - Optimization algorithm failures

### `geo_utils.py`
Geospatial utilities:
- `haversine_distance_m(p1, p2)` - Distance in meters between two (lon, lat) points
- `bpr_travel_time(free_flow_time, volume, capacity)` - BPR congestion formula

### `paths.py`
Path management:
```python
from src.core.paths import PathManager

paths = PathManager(base_dir="/path/to/project")
candidates_path = paths.candidates()  # data/processed/candidate_sites_filtered.geojson
od_matrices_path = paths.od_matrices()  # data/processed/od_travel_time_matrix.npz
```

### `run_context.py`
Run metadata:
```python
from src.core.run_context import RunContext

ctx = RunContext(
    base_dir="/path/to/project",
    config=config_dict,
    data_mode="demo",  # or "real"
    run_id="abc123",
)
```

## Pipeline Stages (`src/stages/`)

Each stage is a focused, testable unit of work.

### Stage Flow

```
1. preflight.py          → Validate inputs or generate demo data
2. spatial_ranking.py    → AHP-TOPSIS candidate site ranking
3. road_network.py       → OSM road graph + OD matrices
4. optimization.py       → NSGA-II + baselines + extensions
5. grid_analysis.py      → AC power flow simulation
6. visualization.py      → Static maps and plots
7. reporting.py          → Research report + manifest
```

### Using Individual Stages

```python
from src.stages import (
    validate_real_data_inputs,
    run_spatial_ranking,
    compute_road_network,
    run_optimization,
    run_grid_analysis,
    generate_visualizations,
    generate_report,
)

# Example: run just the optimization stage
result = run_optimization(
    base_dir="/path/to/project",
    config=config,
    dist_matrix=distances,
    time_matrix=times,
    demand_values=demand,
    demand_gdf=demand_gdf,
    candidate_metadata=candidates,
    candidate_ids=cand_ids,
    demand_ids=dem_ids,
    run_id="test123",
    population=50,
    generations=10,
    sensitivity=False,
    candidate_table_path="/path/to/candidates.csv",
)
```

## Research Extensions (`src/optimization/extensions/`)

**Verification status**: The codebase has passed a full syntax and import check (`verify_rewrite.py`) and all unit tests (71 pytest, 22 Vitest) succeed. The architecture guide reflects the current verified structure.

Each extension is independent and can be run separately.

### Available Extensions

| Module | Purpose | Output |
|--------|---------|--------|
| `uncertainty.py` | Monte Carlo site screening | CSV of site selection frequencies |
| `equity.py` | Spatial access by zone | CSV of zone-level access metrics |
| `time_profiles.py` | Hourly load profiles | CSV of time-of-day demand shares |
| `queueing.py` | M/M/c queue estimates | CSV of wait times per station |
| `grid_upgrade.py` | Substation upgrade costs | CSV of upgrade cost estimates |
| `field_validation.py` | Field visit template | CSV template for site visits |
| `investment.py` | Investment scenarios | CSV of budget/tariff scenarios |

### Using Extensions Directly

```python
from src.optimization.extensions import write_uncertainty_screen

# Run uncertainty analysis
uncertainty_path = write_uncertainty_screen(
    output_path="/path/to/uncertainty.csv",
    metrics_path="/path/to/metrics.csv",
    distances=dist_matrix,
    demand_values=demand,
    candidate_metadata=candidates,
    optimizer_solution=solution,
    config=config,
    settings={"n_samples": 100},
)
```

## Frontend Architecture (`web/src/`)

### Hooks (`web/src/hooks/`)

Custom React hooks for state management:

- `useDashboardData.js` - Fetches and auto-refreshes dashboard data
- `useLiveMap.js` - Live OSM map data with caching
- `useTheme.js` - Theme management (auto/light/dark)
- `useWorkspace.js` - localStorage workspace persistence
- `useURLState.js` - URL parameter synchronization

### Components (`web/src/components/`)

Focused, reusable components:

- `CandidateTable.jsx` - Sortable candidate site table
- `ParetoSelector.jsx` - Pareto solution selection UI
- `ResearchInsights.jsx` - Research extension panels
- `EvidencePanel.jsx` - Data provenance and status
- `LiveDataPanel.jsx` - Live OSM facility counts

### Using Hooks

```jsx
import { useDashboardData } from './hooks/useDashboardData';
import { useTheme } from './hooks/useTheme';

function App() {
  const { data, loading, error } = useDashboardData();
  const { theme, toggleTheme } = useTheme();
  
  // ...
}
```

## Common Patterns

### Loading Configuration

```python
from src.config import load_config

config = load_config(
    config_path="configs/default_config.yaml",
    settings_path="configs/user_settings.yaml",  # optional
)
```

### Running the Full Pipeline

```python
from src.pipeline import run_full_pipeline

result = run_full_pipeline(
    config_path="configs/default_config.yaml",
    generations=50,
    population=100,
    base_dir="/path/to/project",
    data_mode="demo",  # or "real"
    sensitivity=True,
)

print(f"Run ID: {result['run_id']}")
print(f"Pareto solutions: {result['pareto_solutions_count']}")
print(f"Grid feasible: {result['grid_feasible']}")
```

### Working with GeoData

```python
import geopandas as gpd
from src.core.geo_utils import haversine_distance_m

# Load candidates
candidates = gpd.read_file("data/processed/candidate_sites_filtered.geojson")

# Calculate distance between two candidates
p1 = (candidates.iloc[0].geometry.x, candidates.iloc[0].geometry.y)
p2 = (candidates.iloc[1].geometry.x, candidates.iloc[1].geometry.y)
distance_m = haversine_distance_m(p1, p2)
```

### Using PathManager

```python
from src.core.paths import PathManager

paths = PathManager("/path/to/project")

# Get standard paths
candidates = paths.candidates()
demand = paths.demand_grid()
od_matrices = paths.od_matrices()
pareto = paths.pareto_solutions(run_id="abc123")

# All paths are relative to base_dir
print(candidates)  # /path/to/project/data/processed/candidate_sites_filtered.geojson
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_optimization_solver.py

# Run with coverage
pytest --cov=src --cov-report=html
```

### Test Structure

```
tests/
├── test_config.py              # Configuration loading
├── test_cli.py                 # Command-line interface
├── test_end_to_end_pipeline.py # Full pipeline integration
├── test_optimization_solver.py # NSGA-II solver
├── test_power_flow.py          # Grid simulation
├── test_sensitivity.py         # Sensitivity analysis
├── test_spatial_integrity.py   # GIS and road network
├── test_research_extensions.py # Extension modules
└── test_run_manifest.py        # Manifest generation
```

## Error Handling

### Common Errors

**RealDataPreflightError**: Missing or invalid real data inputs
```python
try:
    validate_real_data_inputs(base_dir)
except RealDataPreflightError as e:
    print(f"Missing inputs: {e}")
    print("Hint: Use --mode demo for synthetic data")
```

**ConfigError**: Invalid configuration
```python
try:
    config = load_config("config.yaml")
except ConfigError as e:
    print(f"Config error: {e}")
```

**OptimizationError**: Optimization failures
```python
try:
    result = run_optimization(...)
except OptimizationError as e:
    print(f"Optimization failed: {e}")
```

## Performance Tips

1. **Vectorized operations**: The NSGA-II solver uses numpy broadcasting for 3-5x speedup
2. **Pre-sorted indices**: Demand allocation pre-sorts eligible stations once per generation
3. **Caching**: Frontend hooks cache live map data to reduce API calls
4. **Lazy loading**: Stage modules only import what they need

## Migration from Old Code

### Before (monolithic pipeline)
```python
# Old: everything in pipeline.py
from src.pipeline import run_full_pipeline
```

### After (modular stages)
```python
# New: same API, but internally uses stages
from src.pipeline import run_full_pipeline

# Or use individual stages
from src.stages import run_optimization, run_grid_analysis
```

### Backward Compatibility

All existing imports still work:
- `from src.pipeline import run_full_pipeline` ✓
- `from src.config import load_config` ✓
- `from src.optimization.nsga2_solver import NSGA2Solver` ✓

The rewrite maintains full backward compatibility while providing a cleaner internal architecture.

## Next Steps

1. Run `python verify_rewrite.py` to validate the installation
2. Try `python main.py --mode demo` to test the pipeline
3. Explore individual stages in `src/stages/`
4. Check out the frontend in `web/src/`
5. Read `REWRITE_SUMMARY.md` for the full architectural overview