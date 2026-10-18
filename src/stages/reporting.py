"""Stage 7 — Research report and run manifest generation."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def write_run_manifest(path, manifest):
    """Atomically persist JSON run metadata without exposing secrets."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _format_baseline_table(baseline_df):
    lines = [
        "| Strategy | Stations | System cost (BDT) | Coverage (%) | Budget feasible |",
        "|---|---:|---:|---:|:---:|",
    ]
    for row in baseline_df.itertuples(index=False):
        lines.append(
            f"| {row.strategy} | {row.station_count} | {row.system_cost_bdt:,.2f} "
            f"| {row.demand_coverage_pct:.2f} | {row.budget_feasible} |"
        )
    return "\n".join(lines)


def generate_report(base_dir, context):
    """Write a concise, run-specific reproducibility and limitation report."""
    source_lines = [
        f"- **{record['label']}**: `{record['path']}` ({record.get('data_class', 'unclassified')}); "
        f"SHA-256 `{record.get('sha256', 'not recorded')}`."
        for record in context["inputs"]
        if record.get("path")
    ]
    baseline_table = _format_baseline_table(context["baselines"])
    sensitivity = context["sensitivity_path"]
    extensions = context["research_extensions"]
    extension_outputs = extensions["outputs"]
    lines = [
        f"# EVCS research run {context['run_id']}",
        "",
        f"- **Created:** {context['created_at']}",
        f"- **Data mode/class:** {context['data_mode']} — {context['data_class']}",
        f"- **Selected Pareto solution:** {context['solution']['solution_id']}",
        f"- **Stations / modeled coverage:** {context['solution']['open_station_count']} / {context['solution']['demand_coverage_pct']}%",
        f"- **Modeled life-cycle social cost:** BDT {context['solution']['total_cost_bdt']:,.2f}",
        "",
        "## Data inventory and provenance",
        "",
        *source_lines,
        "",
        f"Candidate sites: {context['candidate_count']}; demand zones: {context['demand_count']}; "
        f"routable road segments: {context['road_edge_count']}; road graph nodes: {context['road_node_count']}.",
        f"Road attribute provenance counts (tagged/assumed/unclassified values): "
        f"`{json.dumps(context['road_attribute_sources'], sort_keys=True)}`.",
        f"Demand-to-candidate OD distance and time matrices use `{context['od_routing_method']}`; "
        f"disconnected pairs fail the run rather than receiving straight-line substitutes.",
        f"Candidate-to-candidate ordered routes: {context['route_count']} of {context['route_pair_count']} "
        f"have a distinct road-node route; {context['same_node_count']} pairs share a snapped node; "
        f"{context['unrouted_count']} ordered pairs are disconnected.",
        "",
        "## Baseline comparison",
        "",
        "The AHP/TOPSIS and demand-greedy baselines use the same station count and charger allocations "
        "as the selected optimizer solution; only the station sites change. They are diagnostic "
        "comparisons, not equivalent independent optimizations.",
        "",
        baseline_table,
        "",
        "## Grid-model check",
        "",
        f"- Voltage range: {context['grid_voltage']['min_v_pu']}–{context['grid_voltage']['max_v_pu']} p.u.; "
        f"voltage-limit check: **{'pass' if context['grid_voltage']['is_compliant'] else 'fail'}**.",
        f"- Maximum line/transformer loading: {context['grid_thermal']['max_line_loading_pct']}% / "
        f"{context['grid_thermal']['max_trafo_loading_pct']}%; loading check: "
        f"**{'pass' if context['grid_thermal']['is_thermal_compliant'] else 'fail'}**.",
        "- These checks validate the simulation against configured thresholds, not against utility "
        "observations. Treat grid conclusions as unvalidated unless source provenance and utility "
        "measurements are independently confirmed.",
        "",
        "## Robustness analysis",
        "",
        (
            f"Sensitivity analysis: `{sensitivity}`. Per-scenario knee solutions are in "
            f"`{Path(sensitivity).with_name('sensitivity_knee_summary.csv')}`; alternate-seed "
            f"site selection frequencies are in "
            f"`{Path(sensitivity).with_name('optimizer_seed_site_stability.csv')}`. "
            "Seed stability is optimizer-search robustness, not empirical validation."
        ) if sensitivity else (
            "Sensitivity analysis was not run. Use `python main.py --sensitivity` to run the "
            "documented demand, budget, service-radius, and optimizer-seed perturbations."
        ),
        f"Monte Carlo site-screen: `{extension_outputs['uncertainty_site_screen']}` and per-sample "
        f"results `{extension_outputs['uncertainty_scenario_metrics']}`; "
        f"{extensions['uncertainty_summary']['samples']} samples produce reachable-demand "
        f"p05/mean/p95 of "
        f"{extensions['uncertainty_summary']['reachable_demand_pct_p05']:.1f}%/"
        f"{extensions['uncertainty_summary']['reachable_demand_pct_mean']:.1f}%/"
        f"{extensions['uncertainty_summary']['reachable_demand_pct_p95']:.1f}%. "
        f"Most frequently selected: {', '.join(extensions['most_frequently_selected_sites']) or 'none'}. "
        "This is a heuristic site-selection screen, not repeated NSGA-II optimization.",
        "",
        "## Access, operations, grid, and investment screens",
        "",
        f"- Zone-level spatial access proxy (not socioeconomic equity): `{extension_outputs['equity_accessibility']}`.",
        f"- Assumed time-of-day, day-type, and seasonal load profiles: `{extension_outputs['time_of_day_load_profile']}`.",
        f"- Peak-hour M/M/c queue estimates: `{extension_outputs['queueing_screen']}`; arrival and service distributions are assumed.",
        f"- Candidate transformer/feeder upgrade cost screen: `{extension_outputs['grid_upgrade_screen']}`; nearest-substation headroom and distance are input proxies, not utility studies.",
        f"- Budget, operating-tariff, payback, and emissions scenarios: `{extension_outputs['investment_scenarios']}`; these are assumption-based and are not financial or emissions forecasts.",
        f"- Blank field visit worksheet for selected sites: `{extension_outputs['field_validation_template']}`.",
        f"- All editable extension assumptions: `{extension_outputs['assumptions']}`.",
        "",
        "## Limitations and interpretation",
        "",
        "- Demo-mode inputs are synthetic, not observed Dhaka data. A provenance sidecar documents declared source and processing details but does not independently authenticate the source or its license.",
        "- The candidate-pair distances use road-edge lengths and nearest-node snapping; sparse graphs can create large snap offsets or shared-node results. Estimated speed, lane, and flow values from the OSM downloader are explicitly labeled assumptions, not measured traffic.",
        "- Demand coverage is conditional on the configured demand inputs, charger assumptions, and routing model; it is not measured utilization or a demand forecast.",
        "- The geographic access table is not a socioeconomic-equity analysis; demographic and income data are not supplied. Hourly profiles, queue estimates, connection upgrades, tariffs, and emissions factors are illustrative assumptions.",
        "- Replace assumed demand, fleet, road traffic, land costs, charger costs, and grid parameters with dated, licensed local measurements before making investment or policy claims.",
        "",
        "## Output files",
        "",
        *[f"- `{output}`" for output in context["outputs"]],
        "",
    ]
    report_path = os.path.join(base_dir, "results", "reports", f"run_{context['run_id']}.md")
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

