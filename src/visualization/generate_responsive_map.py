"""Generate production-grade responsive online research website & interactive GIS dashboard for Dhaka EVCS optimization."""

import json
import os
import pandas as pd
from pathlib import Path


def build_responsive_map_html(base_dir: Path, output_file: Path, config=None, data_mode="demo", deploy_copies=False, run_metadata=None):
    """Build a standalone dashboard from existing outputs without implicit deployment writes."""
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    tables_dir = base_dir / "results" / "tables"

    # Load existing outputs only; this renderer never generates source data.
    with open(processed_dir / "candidate_sites_filtered.geojson", "r", encoding="utf-8") as f:
        candidates_geo = json.load(f)

    with open(processed_dir / "demand_grid_100m.geojson", "r", encoding="utf-8") as f:
        demand_geo = json.load(f)

    with open(raw_dir / "osm_dhaka_roads.geojson", "r", encoding="utf-8") as f:
        roads_geo = json.load(f)

    with open(raw_dir / "rajuk_dap_landuse.geojson", "r", encoding="utf-8") as f:
        landuse_geo = json.load(f)

    substations_path = raw_dir / "dpdc_desco_substations.csv"
    pareto_path = tables_dir / "optimal_solutions_pareto.csv"
    ranked_path = tables_dir / "candidate_sites.csv"
    subs_data = pd.read_csv(substations_path).to_dict(orient="records") if substations_path.exists() else []
    pareto_data = pd.read_csv(pareto_path).to_dict(orient="records") if pareto_path.exists() else []
    ranked_map = {}
    if ranked_path.exists():
        ranked_df = pd.read_csv(ranked_path)
        ranked_map = {row["candidate_id"]: row for row in ranked_df.to_dict(orient="records")}
    config = config or {}
    optimization_settings = config.get("optimization", {})
    visualization_settings = config.get("visualization", {})
    run_metadata = run_metadata or {}
    settings_payload = {
        "min_open_stations": optimization_settings.get("min_open_stations", 3),
        "max_open_stations": optimization_settings.get("max_open_stations", len(candidates_geo.get("features", []))),
        "min_chargers_per_station": optimization_settings.get("min_chargers_per_station", 2),
        "max_chargers_per_station": optimization_settings.get("max_chargers_per_station", 12),
        "budget_cap_bdt": optimization_settings.get("budget_cap_bdt"),
        "service_radius_rmax_m": optimization_settings.get("service_radius_rmax_m", 5000.0),
        "data_mode": data_mode,
        "population_size": optimization_settings.get("nsga2", {}).get("population_size", 100),
        "generations": optimization_settings.get("nsga2", {}).get("generations", 250),
        "map_provider": visualization_settings.get("map_provider", "osm"),
        "maptiler_style": visualization_settings.get("maptiler_style", "streets-v2"),
        "run_id": run_metadata.get("run_id"),
        "provenance_status": run_metadata.get("provenance_status", "Unavailable: no manifest supplied to dashboard generator"),
    }

    # Voltage values are not passed to the dashboard builder as measured run output.
    # Do not fabricate a voltage profile from substation metadata.
    bus_voltages = []

    candidates_json_str = json.dumps(candidates_geo)
    demand_json_str = json.dumps(demand_geo)
    roads_json_str = json.dumps(roads_geo)
    landuse_json_str = json.dumps(landuse_geo)
    subs_json_str = json.dumps(subs_data)
    pareto_json_str = json.dumps(pareto_data)
    ranked_json_str = json.dumps(ranked_map)
    voltages_json_str = json.dumps(bus_voltages)
    settings_json_str = json.dumps(settings_payload)
    catchment_radius_m = max(500, min(10000, float(settings_payload["service_radius_rmax_m"])))

    html_content = f"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dhaka EVCS Optimization & Power Grid Research Platform</title>

  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
  <!-- Leaflet Heatmap Plugin -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.heat/0.2.0/leaflet-heat.js"></script>
  <!-- Chart.js for Interactive Result Analytics -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <!-- Font Awesome 6 -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" />
  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">

  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          fontFamily: {{
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          }},
          colors: {{
            brand: {{
              50: '#ecfdf5',
              100: '#d1fae5',
              400: '#34d399',
              500: '#10b981',
              600: '#059669',
              700: '#047857',
            }},
            dpdc: '#2563eb',
            desco: '#7c3aed',
          }}
        }}
      }}
    }}
  </script>

  <style>
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
    #map {{
      height: 100%;
      width: 100%;
      background-color: #0b1120;
    }}
    .custom-scrollbar::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .custom-scrollbar::-webkit-scrollbar-track {{
      background: rgba(15, 23, 42, 0.6);
    }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{
      background: rgba(100, 116, 139, 0.4);
      border-radius: 9999px;
    }}
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {{
      background: rgba(16, 185, 129, 0.6);
    }}
    .pulse-ring {{
      animation: pulse-animation 2.2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
    }}
    @keyframes pulse-animation {{
      0% {{ transform: scale(0.9); opacity: 0.9; }}
      50% {{ transform: scale(1.4); opacity: 0.2; }}
      100% {{ transform: scale(0.9); opacity: 0.9; }}
    }}
    .leaflet-popup-content-wrapper {{
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
      border-radius: 14px;
      padding: 0;
      overflow: hidden;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}
    .leaflet-popup-content {{
      margin: 0;
      line-height: 1.4;
    }}
    .leaflet-popup-tip {{
      background: #0f172a;
      border: 1px solid #334155;
    }}
    .leaflet-container {{
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
    :root {{
      color-scheme: light dark;
      --surface-0: #f4f7fb;
      --surface-1: rgba(255, 255, 255, 0.96);
      --surface-2: rgba(241, 245, 249, 0.9);
      --line-soft: rgba(71, 85, 105, 0.2);
      --accent: #047857;
      --ink-primary: #0f172a;
      --ink-secondary: #334155;
      --ink-muted: #64748b;
      --shadow-soft: 0 18px 48px rgba(15, 23, 42, 0.12);
    }}
    @media (prefers-color-scheme: dark) {{
      :root:not([data-theme="light"]) {{
        color-scheme: dark;
        --surface-0: #070d18;
        --surface-1: rgba(15, 23, 42, 0.96);
        --surface-2: rgba(30, 41, 59, 0.84);
        --line-soft: rgba(148, 163, 184, 0.18);
        --accent: #34d399;
        --ink-primary: #f8fafc;
        --ink-secondary: #cbd5e1;
        --ink-muted: #94a3b8;
        --shadow-soft: 0 18px 48px rgba(2, 6, 23, 0.3);
      }}
    }}
    :root[data-theme="dark"] {{
      color-scheme: dark;
      --surface-0: #070d18;
      --surface-1: rgba(15, 23, 42, 0.96);
      --surface-2: rgba(30, 41, 59, 0.84);
      --line-soft: rgba(148, 163, 184, 0.18);
      --accent: #34d399;
      --ink-primary: #f8fafc;
      --ink-secondary: #cbd5e1;
      --ink-muted: #94a3b8;
      --shadow-soft: 0 18px 48px rgba(2, 6, 23, 0.3);
    }}
    :root[data-theme="light"] {{ color-scheme: light; }}
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: var(--surface-0);
      letter-spacing: -0.01em;
    }}
    button, select, input {{
      -webkit-tap-highlight-color: transparent;
    }}
    button {{
      transition: color 160ms ease, background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
    }}
    button:active {{ transform: translateY(1px); }}
    :focus-visible {{
      outline: 2px solid var(--accent) !important;
      outline-offset: 3px;
      box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.16);
    }}
    ::selection {{ background: rgba(16, 185, 129, 0.3); color: #f8fafc; }}
    #map {{
      height: 100%;
      width: 100%;
      background-color: #0b1120;
    }}
    .custom-scrollbar {{ scrollbar-width: thin; scrollbar-color: rgba(100, 116, 139, 0.55) transparent; }}
    .custom-scrollbar::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    .custom-scrollbar::-webkit-scrollbar-track {{ background: rgba(15, 23, 42, 0.35); }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{ background: rgba(100, 116, 139, 0.42); border-radius: 9999px; }}
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {{ background: rgba(16, 185, 129, 0.6); }}
    .pulse-ring {{ animation: pulse-animation 2.2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite; }}
    @keyframes pulse-animation {{
      0% {{ transform: scale(0.9); opacity: 0.9; }}
      50% {{ transform: scale(1.4); opacity: 0.2; }}
      100% {{ transform: scale(0.9); opacity: 0.9; }}
    }}
    .leaflet-popup-content-wrapper {{
      background: var(--surface-1); color: var(--ink-primary); border: 1px solid var(--line-soft); border-radius: 14px;
      padding: 0; overflow: hidden; box-shadow: var(--shadow-soft);
    }}
    .leaflet-popup-content {{ margin: 0; line-height: 1.4; }}
    .leaflet-popup-tip {{ background: var(--surface-1); border: 1px solid var(--line-soft); }}
    @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) .leaflet-popup-content-wrapper {{ background: #0f172a; color: #f8fafc; }} :root:not([data-theme="light"]) .leaflet-popup-tip {{ background: #0f172a; }} }}
    :root[data-theme="dark"] .leaflet-popup-content-wrapper {{ background: #0f172a; color: #f8fafc; }}
    :root[data-theme="dark"] .leaflet-popup-tip {{ background: #0f172a; }}
    .leaflet-container {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    .glass-card {{
      background: var(--surface-1);
      color: var(--ink-primary);
      backdrop-filter: blur(14px) saturate(140%);
      border: 1px solid var(--line-soft);
      box-shadow: var(--shadow-soft);
    }}
    #sidebar {{ width: min(24rem, 92vw); }}
    #tab-content-layers .grid > div, #tab-content-layers > div, #tab-content-sim > div, #tab-content-fleet > div {{
      border-color: var(--line-soft);
      box-shadow: 0 8px 24px rgba(2, 6, 23, 0.12);
    }}
    #tab-content-layers .grid > div {{ transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease; }}
    #tab-content-layers .grid > div:hover {{ border-color: rgba(52, 211, 153, 0.38); transform: translateY(-2px); box-shadow: 0 12px 28px rgba(2, 6, 23, 0.24); }}
    #settings-panel, #analytics-modal {{ overscroll-behavior: contain; }}
    :root[data-theme="light"] body {{ color: var(--ink-primary); }}
    :root[data-theme="light"] header,
    :root[data-theme="light"] #sidebar,
    :root[data-theme="light"] #settings-panel > div,
    :root[data-theme="light"] #analytics-modal > div {{ background-color: #ffffff; color: #0f172a; border-color: #dbe3ee; }}
    :root[data-theme="light"] [class*="bg-slate-950"],
    :root[data-theme="light"] [class*="bg-slate-900"],
    :root[data-theme="light"] [class*="bg-slate-800"] {{ background-color: #f1f5f9; }}
    :root[data-theme="light"] [class*="border-slate-800"],
    :root[data-theme="light"] [class*="border-slate-700"] {{ border-color: #dbe3ee; }}
    :root[data-theme="light"] .text-white,
    :root[data-theme="light"] .text-slate-100,
    :root[data-theme="light"] .text-slate-200 {{ color: #0f172a; }}
    :root[data-theme="light"] .text-slate-300 {{ color: #334155; }}
    :root[data-theme="light"] .text-slate-400,
    :root[data-theme="light"] .text-slate-500 {{ color: #64748b; }}
    :root[data-theme="light"] input:not([type="range"]),
    :root[data-theme="light"] select {{ color: #0f172a; background-color: #ffffff; border-color: #cbd5e1; }}
    :root[data-theme="light"] .leaflet-tooltip {{ color: #0f172a; background: #ffffff; border-color: #cbd5e1; }}
    :root[data-theme="light"] .leaflet-tooltip::before {{ border-top-color: #ffffff; }}
    @media (max-width: 640px) {{
      header {{ min-height: 4rem; }}
      #map-bm-control {{ top: auto; bottom: 4.75rem; right: .75rem; }}
      #inspector-card {{ left: .75rem; right: .75rem; bottom: .75rem; width: auto; max-height: 42vh; overflow-y: auto; }}
      #settings-panel > div {{ border-left: 0; }}
      #analytics-modal {{ padding: .5rem; }}
      #analytics-modal > div {{ height: calc(100dvh - 1rem); border-radius: 1rem; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }}
    }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 h-screen w-screen overflow-hidden flex flex-col antialiased">

  <!-- Top Navigation Bar -->
  <header class="h-16 bg-slate-900/95 backdrop-blur border-b border-slate-800 flex items-center justify-between px-3 sm:px-6 z-30 shrink-0">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-slate-950">
        <i class="fa-solid fa-bolt text-lg"></i>
      </div>
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-sm sm:text-base font-bold text-white tracking-tight">Dhaka EVCS Research Dashboard</h1>
          <span id="data-mode-badge" class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">{data_mode.upper()} DATA</span>
        </div>
        <p class="text-[11px] text-slate-400 hidden sm:block">Spatial Placement, Capacity Allocation & Power Grid Co-Simulation</p>
      </div>
    </div>

    <!-- Center Search Bar (Online Nominatim + Spatial Anchors) -->
    <div class="relative max-w-xs sm:max-w-sm w-full mx-2 hidden md:block">
      <div class="relative">
        <input type="text" id="spatial-search-input" placeholder="Search zone, highway or landmark..."
               class="w-full bg-slate-800/90 border border-slate-700/80 rounded-xl px-3.5 py-1.5 pl-9 text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-emerald-500 transition shadow-inner"
               onkeydown="if(event.key==='Enter') executeLiveSearch()" />
        <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
        <button onclick="executeLiveSearch()" class="absolute right-1.5 top-1 px-2 py-0.5 bg-emerald-500 text-slate-950 rounded-lg text-[10px] font-bold hover:bg-emerald-400 transition">
          Find
        </button>
      </div>
      <div id="search-results-dropdown" class="hidden absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2 z-50 text-xs space-y-1 max-h-48 overflow-y-auto custom-scrollbar"></div>
    </div>

    <!-- Quick Solution & View Actions -->
    <div class="flex items-center space-x-2 sm:space-x-3">
      <!-- Solution Switcher -->
      <div class="flex items-center bg-slate-800/90 border border-slate-700/80 rounded-xl p-1 text-xs shadow-sm">
        <span class="text-slate-400 px-2 font-medium hidden lg:inline text-[11px]"><i class="fa-solid fa-code-branch mr-1 text-emerald-400"></i>Pareto:</span>
        <button id="btn-sol-knee" aria-pressed="true" onclick="selectSolution(0)" class="px-2.5 py-1 rounded-lg font-bold bg-emerald-500 text-slate-950 shadow transition-all text-xs">
          Knee Point
        </button>
        <button id="btn-sol-max" aria-pressed="false" onclick="selectSolution(1)" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition-all text-xs">
          Max Coverage
        </button>
        <button id="btn-sol-budget" aria-pressed="false" onclick="selectSolution(2)" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition-all text-xs hidden sm:block">
          Budget Tier
        </button>
      </div>

      <!-- Online Live Data Fetch Button -->
      <button onclick="fetchOnlineOSMData()" title="Pull live amenities from OpenStreetMap Overpass API"
              class="px-2.5 py-1.5 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30 text-xs font-semibold transition flex items-center gap-1.5">
        <i class="fa-solid fa-arrows-rotate text-xs" id="online-sync-icon"></i>
        <span class="hidden sm:inline">Sync Live OSM</span>
      </button>

      <!-- Settings Drawer Toggle -->
      <button onclick="toggleSettingsPanel()" title="Configure map and run settings"
              class="px-2.5 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 hover:text-white hover:border-emerald-500/50 text-xs font-semibold transition flex items-center gap-1.5">
        <i class="fa-solid fa-gear text-emerald-400"></i><span class="hidden sm:inline">Settings</span>
      </button>

      <!-- Analytics Modal Toggle -->
      <button onclick="toggleAnalyticsModal()" title="View Research Charts & Grid Analytics"
              class="px-2.5 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 hover:text-white hover:border-emerald-500/50 text-xs font-semibold transition flex items-center gap-1.5">
        <i class="fa-solid fa-chart-line text-emerald-400"></i>
        <span class="hidden sm:inline">Analytics</span>
      </button>

      <!-- Mobile Sidebar Toggle -->
      <button onclick="toggleSidebar()" class="lg:hidden p-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 hover:text-white">
        <i class="fa-solid fa-bars text-sm"></i>
      </button>
    </div>
  </header>

  <!-- Main Workspace -->
  <div class="flex-1 flex relative overflow-hidden">

    <!-- Left Controls & Filters Sidebar -->
    <aside id="sidebar" class="w-84 sm:w-96 bg-slate-900/95 backdrop-blur border-r border-slate-800 flex flex-col shrink-0 z-20 transition-all duration-300 absolute lg:relative h-full -translate-x-full lg:translate-x-0 shadow-2xl lg:shadow-none">

      <!-- Navigation Tabs inside Sidebar -->
      <div role="tablist" aria-label="Dashboard controls" class="flex border-b border-slate-800 bg-slate-950/40 px-2 pt-2 gap-1 text-xs shrink-0">
        <button id="tab-btn-layers" role="tab" aria-selected="true" aria-controls="tab-content-layers" onclick="switchSidebarTab('layers')" class="flex-1 py-2 font-bold border-b-2 border-emerald-500 text-emerald-400 text-center">
          <i class="fa-solid fa-layer-group mr-1.5"></i>Layers & GIS
        </button>
        <button id="tab-btn-sim" role="tab" aria-selected="false" aria-controls="tab-content-sim" onclick="switchSidebarTab('sim')" class="flex-1 py-2 font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 text-center">
          <i class="fa-solid fa-sliders mr-1.5"></i>Grid Studio
        </button>
        <button id="tab-btn-fleet" role="tab" aria-selected="false" aria-controls="tab-content-fleet" onclick="switchSidebarTab('fleet')" class="flex-1 py-2 font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 text-center">
          <i class="fa-solid fa-car mr-1.5"></i>Fleet & Bays
        </button>
      </div>

      <!-- Scrollable Tab Content Container -->
      <div class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">

        <!-- TAB 1: LAYERS & GIS FILTERS -->
        <div id="tab-content-layers" class="space-y-4">
          <!-- KPI Summary Cards -->
          <div class="grid grid-cols-2 gap-2.5">
            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Active Stations
                <i class="fa-solid fa-charging-station text-red-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-station-count" class="text-2xl font-extrabold text-white">—</span>
                <span class="text-xs text-slate-500 font-medium">/ <span id="kpi-candidate-count">—</span> candidates</span>
              </div>
              <div class="text-[10px] text-emerald-400 font-semibold mt-0.5 flex items-center gap-1">
                <i class="fa-solid fa-circle-info"></i> <span id="kpi-solution-id">Run result</span>
              </div>
            </div>

            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Peak Grid Load
                <i class="fa-solid fa-plug-circle-bolt text-blue-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-grid-power" class="text-2xl font-extrabold text-white">—</span>
                <span class="text-xs text-slate-500 font-medium">kW</span>
              </div>
              <div class="text-[10px] text-blue-400 font-semibold mt-0.5 flex items-center gap-1">
                <i class="fa-solid fa-flask"></i> <span id="kpi-grid-status">Model output</span>
              </div>
            </div>

            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Modeled Total Cost
                <i class="fa-solid fa-coins text-amber-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-total-cost" class="text-2xl font-extrabold text-white">—</span>
                <span class="text-xs text-slate-500 font-medium">B BDT</span>
              </div>
              <div class="text-[10px] text-amber-400 font-medium mt-0.5">
                <span id="kpi-cost-note">Model objective; scenario assumptions apply</span>
              </div>
            </div>

            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Spatial Coverage
                <i class="fa-solid fa-chart-pie text-emerald-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-demand-cov" class="text-2xl font-extrabold text-emerald-400">—</span>
                <span class="text-xs text-slate-500 font-medium">%</span>
              </div>
              <div class="text-[10px] text-emerald-400 font-medium mt-0.5">
                <span id="kpi-demand-zones">Unverified demand</span>
              </div>
            </div>
          </div>

          <!-- Zone Spatial Filter -->
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 space-y-2">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider block">
              <i class="fa-solid fa-map-location-dot text-emerald-400 mr-1"></i>Dhaka Zone Selection
            </label>
            <select id="zone-filter-select" onchange="applyFilters()" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500">
              <option value="ALL">All Dhaka Zones (Metropolitan)</option>
              <option value="Gulshan_Banani">Gulshan / Banani / Baridhara</option>
              <option value="Motijheel_CBD">Motijheel Commercial Zone (CBD)</option>
              <option value="Mirpur">Mirpur (1, 10, 11, DOHS)</option>
              <option value="Uttara">Uttara North Gateway</option>
              <option value="Mohakhali_Tejgaon">Mohakhali & Tejgaon Industrial</option>
              <option value="Dhanmondi_Mohammadpur">Dhanmondi & Mohammadpur</option>
              <option value="Old_Dhaka">Old Dhaka (Lalbagh/Sutrapur/Sadarghat)</option>
              <option value="Purbachal_Expressway">Purbachal 300ft Corridor</option>
            </select>
          </div>

          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 space-y-2">
            <label for="catchment-radius" class="block text-xs font-bold text-slate-300 uppercase tracking-wider">Map display catchment radius</label>
            <div class="flex items-center gap-3"><input id="catchment-radius" type="range" min="500" max="10000" step="250" value="{int(catchment_radius_m)}" oninput="updateCatchmentRadius(this.value)" class="w-full accent-emerald-500"><output id="catchment-radius-value" class="min-w-16 text-right font-mono text-xs text-emerald-400">{catchment_radius_m / 1000:.1f} km</output></div>
            <p class="text-[10px] leading-relaxed text-slate-400">Browser-only circle visualization. The optimization uses a configured network-distance optimization limit of {settings_payload['service_radius_rmax_m']:,.0f} m; changing this control does not rerun the model.</p>
          </div>

          <!-- AHP Suitability Slider -->
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-slate-300 uppercase tracking-wider"><i class="fa-solid fa-filter text-emerald-400 mr-1"></i>Min AHP Score S(x, y)</span>
              <span id="ahp-slider-val" class="font-bold text-emerald-400 font-mono">0.00</span>
            </div>
            <input type="range" id="ahp-range-input" min="0.0" max="0.95" step="0.05" value="0.00"
                   oninput="document.getElementById('ahp-slider-val').innerText=parseFloat(this.value).toFixed(2); applyFilters();"
                   class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500" />
            <div class="flex justify-between text-[10px] text-slate-400 font-mono">
              <span>0.00 (All)</span>
              <span>0.50 (Moderate)</span>
              <span>0.80+ (Prime)</span>
            </div>
          </div>

          <!-- Map GIS Layers Toggle Switchboard -->
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 space-y-2.5">
            <span class="text-xs font-bold text-slate-300 uppercase tracking-wider block">
              <i class="fa-solid fa-layer-group text-emerald-400 mr-1"></i>Spatial Map Layers
            </span>

            <div class="space-y-2 text-xs">
              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-red-500 border border-white inline-block"></span>
                  <span class="font-medium text-slate-200">Optimal EVCS Stations</span>
                </span>
                <input type="checkbox" id="layer-opt-evcs" checked onchange="toggleLayer('opt-evcs', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>

              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-slate-400 inline-block"></span>
                  <span class="font-medium text-slate-300">All Candidate Sites (58)</span>
                </span>
                <input type="checkbox" id="layer-all-cand" onchange="toggleLayer('all-cand', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>

              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-sm bg-blue-500 inline-block"></span>
                  <span class="font-medium text-slate-200">DPDC & DESCO Substations (33/11kV)</span>
                </span>
                <input type="checkbox" id="layer-substations" checked onchange="toggleLayer('substations', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>

              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-gradient-to-r from-yellow-400 to-red-500 inline-block"></span>
                  <span class="font-medium text-slate-300">AHP Suitability Heatmap</span>
                </span>
                <input type="checkbox" id="layer-heatmap" onchange="toggleLayer('heatmap', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>

              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-cyan-400 inline-block"></span>
                  <span class="font-medium text-slate-300">Charging Demand Grid (100m)</span>
                </span>
                <input type="checkbox" id="layer-demand" onchange="toggleLayer('demand', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>

              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full bg-emerald-400/40 border border-emerald-400 inline-block"></span>
                  <span class="font-medium text-slate-300">Optimizer network-distance radius</span>
                </span>
                <input type="checkbox" id="layer-buffers" onchange="toggleLayer('buffers', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>

              <label class="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 cursor-pointer transition">
                <span class="flex items-center gap-2">
                  <span class="w-3 h-3 rounded-sm bg-purple-500 inline-block"></span>
                  <span class="font-medium text-slate-300">RAJUK DAP Land-Use & Flood Zones</span>
                </span>
                <input type="checkbox" id="layer-landuse" onchange="toggleLayer('landuse', this.checked)" class="accent-emerald-500 w-4 h-4 cursor-pointer">
              </label>
            </div>
          </div>
        </div>

        <!-- TAB 2: DYNAMIC GRID & SCENARIO STUDIO -->
        <div id="tab-content-sim" class="hidden space-y-4">
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3.5 space-y-3">
            <h4 class="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
              <i class="fa-solid fa-flask"></i> Illustrative Scenario Calculator
            </h4>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              Illustrative arithmetic only—not a network power-flow simulation or measured utility telemetry. Values use a configurable scenario baseline.
            </p>

            <!-- EV Penetration Slider -->
            <div class="space-y-1">
              <div class="flex justify-between text-xs">
                <span class="text-slate-300 font-medium">EV Fleet Penetration Rate:</span>
                <span id="sim-pen-val" class="font-bold text-emerald-400 font-mono">20%</span>
              </div>
              <input type="range" id="sim-penetration" min="5" max="50" step="5" value="20"
                     oninput="updateGridSimulation()" class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500">
            </div>

            <!-- Peak Charging Concurrence -->
            <div class="space-y-1">
              <div class="flex justify-between text-xs">
                <span class="text-slate-300 font-medium">Simultaneous Peak Factor:</span>
                <span id="sim-peak-val" class="font-bold text-blue-400 font-mono">65%</span>
              </div>
              <input type="range" id="sim-peak-factor" min="30" max="95" step="5" value="65"
                     oninput="updateGridSimulation()" class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
            </div>

            <!-- Solar PV & BESS Co-location -->
            <div class="space-y-1">
              <div class="flex justify-between text-xs">
                <span class="text-slate-300 font-medium">Rooftop Solar PV Offset:</span>
                <span id="sim-solar-val" class="font-bold text-amber-400 font-mono">25%</span>
              </div>
              <input type="range" id="sim-solar-offset" min="0" max="60" step="5" value="25"
                     oninput="updateGridSimulation()" class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500">
            </div>
          </div>

          <!-- Clearly marked illustrative outputs; never presented as measured data -->
          <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-3 space-y-2 font-mono text-xs">
            <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans border-b border-slate-800 pb-1">
              Illustrative Scenario Estimates (not utility telemetry)
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800/60">
              <span class="text-slate-400">Total EV Load:</span>
              <span id="sim-out-evload" class="text-emerald-400 font-bold">21.60 MW</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800/60">
              <span class="text-slate-400">Solar PV Generation:</span>
              <span id="sim-out-solar" class="text-amber-400 font-bold">-5.40 MW</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800/60">
              <span class="text-slate-400">Net Utility Demand:</span>
              <span id="sim-out-netpower" class="text-blue-400 font-bold">16.20 MW</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800/60">
              <span class="text-slate-400">Min 33kV Bus Voltage:</span>
              <span id="sim-out-minvoltage" class="text-emerald-400 font-bold">Illustrative only</span>
            </div>
            <div class="flex justify-between py-1">
              <span class="text-slate-400">Voltage Deviation Index:</span>
              <span id="sim-out-vdi" class="text-purple-400 font-bold">Illustrative only</span>
            </div>
          </div>
        </div>

        <!-- TAB 3: FLEET & CHARGER BAY TYPOLOGY -->
        <div id="tab-content-fleet" class="hidden space-y-4">
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3.5 space-y-3">
            <div class="text-xs font-bold text-slate-300 uppercase tracking-wider pb-1 border-b border-slate-700/60">
              Illustrative Vehicle Fleet Assumptions (not observed local counts)
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">Level 2 AC (22kW)</div>
                <div class="text-base font-bold text-emerald-400 mt-0.5">Illustrative</div>
                <div class="text-[9px] text-slate-400">E2W / Private 4W</div>
              </div>
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">DC Fast (60kW)</div>
                <div class="text-base font-bold text-cyan-400 mt-0.5">Illustrative</div>
                <div class="text-[9px] text-slate-400">Commercial Taxi Fleets</div>
              </div>
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">DC Ultra-Fast (150kW)</div>
                <div class="text-base font-bold text-amber-400 mt-0.5">Illustrative</div>
                <div class="text-[9px] text-slate-400">E-Bus & Express Corridors</div>
              </div>
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">Battery Swap Depots</div>
                <div class="text-base font-bold text-purple-400 mt-0.5">Illustrative</div>
                <div class="text-[9px] text-slate-400">E3W Easy-Bikes & Delivery</div>
              </div>
            </div>
          </div>

          <!-- Illustrative specification assumptions -->
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 space-y-2 text-xs">
            <span class="text-xs font-bold text-slate-300 uppercase tracking-wider block">Illustrative fleet specifications (not verified fleet observations)</span>
            <div class="space-y-1.5 text-[11px] text-slate-300">
              <div class="p-2 bg-slate-900/60 rounded border border-slate-800 flex justify-between">
                <span><b>Electric 2-Wheelers:</b> 2.5 kWh pack</span>
                <span class="text-emerald-400">3.3 - 7.4 kW</span>
              </div>
              <div class="p-2 bg-slate-900/60 rounded border border-slate-800 flex justify-between">
                <span><b>Electric 3-Wheelers:</b> 5.0 kWh pack</span>
                <span class="text-purple-400">Battery Swap</span>
              </div>
              <div class="p-2 bg-slate-900/60 rounded border border-slate-800 flex justify-between">
                <span><b>Private Passenger 4W:</b> 45 kWh</span>
                <span class="text-cyan-400">22 - 60 kW</span>
              </div>
              <div class="p-2 bg-slate-900/60 rounded border border-slate-800 flex justify-between">
                <span><b>City Electric Buses:</b> 250 kWh</span>
                <span class="text-amber-400">150 - 350 kW</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- Sidebar Bottom Action / Download -->
      <div class="p-3 bg-slate-950/80 border-t border-slate-800 flex items-center justify-between text-xs shrink-0">
        <button onclick="exportGeoJSON()" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition flex items-center gap-1">
          <i class="fa-solid fa-download text-emerald-400"></i> Export GeoJSON
        </button>
        <span class="text-slate-400 text-[10px] font-mono">WGS84 · EPSG:4326</span>
      </div>
    </aside>

    <!-- Center Interactive Map Canvas -->
    <main class="flex-1 relative h-full">
      <div id="map"></div>

      <!-- Map Floating Base Layer Switcher -->
      <div id="map-bm-control" role="group" aria-label="Choose map basemap" class="absolute top-4 right-4 glass-card rounded-xl p-1.5 z-20 shadow-xl flex space-x-1 text-xs">
        <button onclick="switchBaseMap('dark')" id="btn-bm-dark" class="px-2.5 py-1 rounded-lg font-bold bg-slate-800 text-emerald-400 transition">Dark</button>
        <button onclick="switchBaseMap('light')" id="btn-bm-light" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition">Light</button>
        <button onclick="switchBaseMap('osm')" id="btn-bm-osm" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition">OSM</button>
        <button onclick="switchBaseMap('sat')" id="btn-bm-sat" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition">Satellite</button>
      </div>
      <div class="absolute top-4 left-4 z-20 rounded-xl bg-white/90 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700 p-2 text-xs shadow-lg">
        <label for="theme-select" class="font-semibold mr-2">Theme</label>
        <select id="theme-select" aria-label="Color theme" onchange="setThemePreference(this.value)" class="rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1">
          <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
        </select>
      </div>

      <div id="map-tile-status" class="absolute bottom-5 left-1/2 -translate-x-1/2 glass-card rounded-lg px-3 py-1.5 z-20 text-[11px] text-amber-300" role="status"></div>

      <!-- Quick Reset Center Button -->
      <button onclick="resetDhakaCenter()" class="absolute bottom-5 left-5 glass-card rounded-xl px-3.5 py-2 z-20 shadow-xl text-xs font-semibold text-slate-200 hover:text-white hover:border-emerald-500 transition flex items-center gap-2">
        <i class="fa-solid fa-crosshairs text-emerald-400"></i>
        <span>Center Dhaka</span>
      </button>

      <!-- Live Inspection Floating Drawer / Card (Bottom Right) -->
      <div id="inspector-card" class="hidden absolute bottom-5 right-5 w-84 sm:w-96 glass-card rounded-2xl shadow-2xl p-4 z-20 space-y-3 transition-all transform duration-200">
        <div class="flex items-start justify-between border-b border-slate-700/60 pb-2.5">
          <div class="flex items-center space-x-2.5">
            <div id="insp-icon" class="w-8 h-8 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center font-bold text-sm">
              <i class="fa-solid fa-plug"></i>
            </div>
            <div>
              <h4 id="insp-title" class="text-sm font-bold text-white leading-tight">Station Inspector</h4>
              <p id="insp-subtitle" class="text-[11px] text-slate-400">Dhaka Location</p>
            </div>
          </div>
          <button onclick="closeInspector()" class="text-slate-400 hover:text-white p-1">
            <i class="fa-solid fa-xmark text-sm"></i>
          </button>
        </div>

        <div id="insp-body" class="space-y-2 text-xs">
          <!-- Populated dynamically via JS -->
        </div>
      </div>
    </main>
  </div>

  <!-- Settings Drawer: run parameters are informational; browser map settings apply immediately -->
  <div id="settings-panel" role="dialog" aria-modal="true" aria-labelledby="settings-title" class="hidden fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-40 flex justify-end">
    <div class="w-full max-w-md h-full bg-slate-900 border-l border-slate-700 shadow-2xl overflow-y-auto custom-scrollbar">
      <div class="sticky top-0 z-10 p-4 bg-slate-900/95 backdrop-blur border-b border-slate-800 flex items-center justify-between">
        <div><h2 id="settings-title" class="text-lg font-bold text-white">Settings</h2><p class="text-xs text-slate-400">Map preferences & optimization run configuration</p></div>
        <button onclick="toggleSettingsPanel()" aria-label="Close settings" class="p-2 text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="p-4 space-y-5">
        <section class="space-y-3">
          <h3 class="text-xs font-bold uppercase tracking-wider text-emerald-400">Appearance</h3>
          <label class="block text-xs text-slate-300">Theme
            <select id="settings-theme-select" onchange="setThemePreference(this.value)" class="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 p-2 text-sm text-white"><option value="system">System default</option><option value="light">Light</option><option value="dark">Dark</option></select>
          </label>
        </section>
        <section class="space-y-3 border-t border-slate-800 pt-4">
          <h3 class="text-xs font-bold uppercase tracking-wider text-emerald-400">Map provider</h3>
          <label class="block text-xs text-slate-300">Basemap
            <select id="settings-map-provider" onchange="applyMapSettings()" class="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 p-2 text-sm text-white">
              <option value="osm">OpenStreetMap (no key)</option><option value="carto-dark">Carto dark</option><option value="carto-light">Carto light</option><option value="sat">Satellite</option><option value="maptiler">MapTiler (key required)</option>
            </select>
          </label>
          <label class="block text-xs text-slate-300">MapTiler API key <span class="text-slate-500">(optional)</span>
            <div class="mt-1 flex gap-2"><input id="maptiler-key" type="password" autocomplete="off" placeholder="Enter your own key" class="min-w-0 flex-1 rounded-lg bg-slate-800 border border-slate-700 p-2 text-sm text-white"><button onclick="toggleKeyVisibility()" class="rounded-lg border border-slate-700 px-3 text-slate-300">Show</button></div>
          </label>
          <div class="flex gap-2"><button onclick="saveMapKey()" class="rounded-lg bg-emerald-500 px-3 py-2 text-xs font-bold text-slate-950">Save key locally</button><button onclick="clearMapKey()" class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">Clear</button></div>
          <p class="text-[11px] leading-relaxed text-slate-400">OpenStreetMap tiles do not require an API key. The optional MapTiler key is stored only in this browser’s local storage and is sent only to MapTiler tile requests. Avoid using a restricted or secret server-side key in a public website.</p>
          <p id="map-settings-status" class="text-xs text-emerald-400" role="status"></p>
        </section>
        <section class="space-y-3 border-t border-slate-800 pt-4">
          <h3 class="text-xs font-bold uppercase tracking-wider text-blue-400">Optimization settings</h3>
          <p class="text-[11px] leading-relaxed text-slate-400">These values describe the generated run. Change them in <code class="text-slate-200">configs/user_settings.yaml</code> and rerun Python to produce new results; editing them here will not alter an existing optimization.</p>
          <div id="run-settings-summary" class="grid grid-cols-2 gap-2 text-xs"></div>
        </section>
      </div>
    </div>
  </div>

  <!-- Full-Screen Research Analytics Modal (Charts & Tradeoffs) -->
  <div id="analytics-modal" role="dialog" aria-modal="true" aria-labelledby="analytics-title" class="hidden fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-3 sm:p-6">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
      <!-- Modal Header -->
      <div class="p-4 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <i class="fa-solid fa-chart-line"></i>
          </div>
          <div>
            <h3 id="analytics-title" class="text-base font-bold text-white">Research Analytics & Power Grid Verification</h3>
            <p class="text-xs text-slate-400">NSGA-II Pareto Frontier & 33kV DPDC/DESCO Voltage Stability Profiles</p>
          </div>
        </div>
        <button onclick="toggleAnalyticsModal()" aria-label="Close analytics" class="text-slate-400 hover:text-white p-2">
          <i class="fa-solid fa-xmark text-lg"></i>
        </button>
      </div>

      <!-- Modal Body (Grid of Charts) -->
      <div class="flex-1 p-4 sm:p-6 overflow-y-auto custom-scrollbar space-y-6">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Chart 1: Pareto Frontier -->
          <div class="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                <i class="fa-solid fa-code-branch mr-1"></i>Run Pareto Solutions
              </h4>
              <button type="button" onclick="downloadParetoCsv()" class="text-xs px-2.5 py-1.5 rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10" aria-label="Download all Pareto solutions as CSV">Download CSV</button>
              <span class="text-[11px] text-slate-400">Trade-Off: Cost vs. Demand Coverage</span>
            </div>
            <div class="h-64 relative">
              <canvas id="paretoChartCanvas"></canvas>
            </div>
          </div>

          <!-- Chart 2: Substation Bus Voltage Profiles -->
          <div class="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-bold text-blue-400 uppercase tracking-wider">
                <i class="fa-solid fa-bolt mr-1"></i>Grid Voltage Results
              </h4>
              <span class="text-[11px] text-slate-400">Measured run output when available</span>
            </div>
            <div class="h-64 relative">
              <canvas id="voltageChartCanvas"></canvas>
            </div>
          </div>
        </div>

        <!-- Detailed Pareto Candidate Comparison Table -->
        <div class="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
          <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Pareto Frontier Candidate Solutions Comparison
          </h4>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs font-sans">
              <thead class="bg-slate-900/90 text-slate-400 border-b border-slate-800 text-[11px] uppercase">
                <tr>
                  <th class="py-2.5 px-3">Solution ID</th>
                  <th class="py-2.5 px-3">Type</th>
                  <th class="py-2.5 px-3">Active EVCS</th>
                  <th class="py-2.5 px-3">Total Cost (BDT)</th>
                  <th class="py-2.5 px-3">Est. USD</th>
                  <th class="py-2.5 px-3">Demand Coverage</th>
                  <th class="py-2.5 px-3">Peak Grid Load</th>
                  <th class="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody id="pareto-table-body" class="divide-y divide-slate-800/60 font-mono text-slate-300">
                <!-- Injected via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Embedded Structured Datasets & Full Application Controller -->
  <script>
    // 1. DATASETS PAYLOAD
    const RAW_CANDIDATES = {candidates_json_str};
    const RAW_DEMAND = {demand_json_str};
    const RAW_ROADS = {roads_json_str};
    const RAW_LANDUSE = {landuse_json_str};
    const RAW_SUBSTATIONS = {subs_json_str};
    const RAW_PARETO = {pareto_json_str};
    const RANKED_CANDIDATES = {ranked_json_str};
    const BUS_VOLTAGES = {voltages_json_str};
    const RUN_SETTINGS = {settings_json_str};

    // 2. STATE MANAGEMENT
    let activeSolutionIndex = 0;
    let currentSolution = RAW_PARETO[0] || {{}};
    let activeStationIds = new Set((currentSolution.selected_station_ids || "").split(";"));
    let currentMinAHP = 0.0;
    let selectedZone = "ALL";
    let searchQuery = "";

    // Map & Layer References
    let map;
    let baseLayers = {{}};
    let activeBaseLayer;
    let layers = {{
      optimalEVCS: null,
      allCandidates: null,
      substations: null,
      heatmap: null,
      demandGrid: null,
      buffers: null,
      roads: null,
      landuse: null,
      liveAmenities: null
    }};

    // 3. INITIALIZATION
    const initialTheme = (() => {{
      try {{ return localStorage.getItem('dhaka-evcs-theme') || 'system'; }} catch (e) {{ return 'system'; }}
    }})();
    if (initialTheme === 'light' || initialTheme === 'dark') document.documentElement.setAttribute('data-theme', initialTheme);
    window.addEventListener('DOMContentLoaded', () => {{
      initMap();
      initLiveWeather();
      populateParetoTable();
      populateRunSettings();
      loadMapKey();
      let provider = RUN_SETTINGS.map_provider || 'osm';
      try {{ provider = localStorage.getItem('dhaka-evcs-map-provider') || provider; }} catch (e) {{}}
      if (RUN_SETTINGS.data_mode === 'demo') document.getElementById('data-mode-badge').textContent = 'SYNTHETIC DEMO';
      document.getElementById('settings-map-provider').value = provider;
      initThemePreference();
      if (provider === 'maptiler') applyMapSettings();
      else switchBaseMap(provider === 'carto-light' ? 'light' : provider === 'carto-dark' ? 'dark' : provider);
      selectSolution(0);
      initCharts();
      document.addEventListener('keydown', event => {{
        if (event.key === 'Escape') {{
          if (!document.getElementById('settings-panel').classList.contains('hidden')) toggleSettingsPanel(false);
          if (!document.getElementById('analytics-modal').classList.contains('hidden')) toggleAnalyticsModal(false);
          if (!document.getElementById('inspector-card').classList.contains('hidden')) closeInspector();
        }}
        if (event.key === 'Tab') {{
          const dialog = [document.getElementById('analytics-modal'), document.getElementById('settings-panel')]
            .find(element => !element.classList.contains('hidden'));
          if (!dialog) return;
          const focusable = [...dialog.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]
            .filter(element => element.offsetParent !== null);
          if (!focusable.length) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {{
            event.preventDefault(); last.focus();
          }} else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {{
            event.preventDefault(); first.focus();
          }}
        }}
      }});
    }});

    function initMap() {{
      // Initialize Leaflet Map centered on Dhaka Metropolitan Coordinates
      map = L.map('map', {{
        center: [23.7850, 90.4000],
        zoom: 12,
        zoomControl: false,
        attributionControl: false
      }});

      // Correct zoom control addition
      L.control.zoom({{ position: 'topleft' }}).addTo(map);

      // Define Base Tile Providers
      baseLayers.dark = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        subdomains: 'abcd', maxZoom: 19
      }});
      baseLayers.light = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        subdomains: 'abcd', maxZoom: 19
      }});
      baseLayers.osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19
      }});
      baseLayers.sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        maxZoom: 18
      }});

      activeBaseLayer = baseLayers.osm;
      activeBaseLayer.addTo(map);
      map.whenReady(() => setTimeout(() => map.invalidateSize(true), 150));
      map.on('baselayerchange', () => setTimeout(() => map.invalidateSize(true), 80));
      baseLayers.osm.on('tileerror', () => {{
        const notice = document.getElementById('map-tile-status');
        if (notice) notice.textContent = 'Map tiles unavailable; check connection or choose another basemap.';
      }});

      // Initialize Layer Groups
      layers.optimalEVCS = L.layerGroup().addTo(map);
      layers.substations = L.layerGroup().addTo(map);
      layers.roads = L.layerGroup().addTo(map);
      layers.allCandidates = L.layerGroup();
      layers.heatmap = L.layerGroup();
      layers.demandGrid = L.layerGroup();
      layers.buffers = L.layerGroup();
      layers.landuse = L.layerGroup();
      layers.liveAmenities = L.layerGroup().addTo(map);

      // Render Spatial Layers
      renderAllLayers();
    }}

    function applyTheme(theme) {{
      const root = document.documentElement;
      if (theme === 'system') root.removeAttribute('data-theme');
      else root.setAttribute('data-theme', theme);
      document.querySelectorAll('#theme-select, #settings-theme-select').forEach(select => select.value = theme);
      const dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      if (paretoChartInstance || voltageChartInstance) updateChartTheme(dark);
    }}

    function setThemePreference(theme) {{
      if (!['system', 'light', 'dark'].includes(theme)) return;
      try {{ localStorage.setItem('dhaka-evcs-theme', theme); }} catch (e) {{}}
      applyTheme(theme);
    }}

    function initThemePreference() {{
      let theme = 'system';
      try {{ theme = localStorage.getItem('dhaka-evcs-theme') || 'system'; }} catch (e) {{}}
      applyTheme(theme);
      if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {{
        if (!document.documentElement.hasAttribute('data-theme')) applyTheme('system');
      }});
    }}

    function updateChartTheme(dark) {{
      [paretoChartInstance, voltageChartInstance].filter(Boolean).forEach(chart => {{
        const ink = dark ? '#cbd5e1' : '#334155';
        const grid = dark ? 'rgba(148,163,184,.2)' : 'rgba(100,116,139,.22)';
        chart.options.plugins.legend.labels.color = ink;
        Object.values(chart.options.scales || {{}}).forEach(scale => {{
          if (scale.ticks) scale.ticks.color = ink;
          if (scale.title) scale.title.color = ink;
          if (scale.grid) scale.grid.color = grid;
        }});
        chart.update('none');
      }});
    }}

    function switchBaseMap(type) {{
      if (activeBaseLayer) map.removeLayer(activeBaseLayer);
      const normalized = type === 'dark' ? 'carto-dark' : type === 'light' ? 'carto-light' : type;
      activeBaseLayer = baseLayers[type] || baseLayers.dark;
      activeBaseLayer.addTo(map);
      const select = document.getElementById('settings-map-provider');
      if (select && normalized !== 'maptiler') select.value = normalized === 'carto-dark' || normalized === 'carto-light' || normalized === 'sat' ? normalized : 'osm';

      ['dark', 'light', 'osm', 'sat'].forEach(t => {{
        const btn = document.getElementById('btn-bm-' + t);
        if (btn) {{
          if (t === type) {{
            btn.className = "px-2.5 py-1 rounded-lg font-bold bg-slate-800 text-emerald-400 transition";
          }} else {{
            btn.className = "px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition";
          }}
        }}
      }});
    }}

    function toggleSettingsPanel(forceOpen) {{
      const panel = document.getElementById('settings-panel');
      const opening = typeof forceOpen === 'boolean' ? forceOpen : panel.classList.contains('hidden');
      panel.classList.toggle('hidden', !opening);
      if (opening) {{
        setTimeout(() => document.getElementById('settings-map-provider').focus(), 0);
      }} else {{
        document.querySelector('[onclick="toggleSettingsPanel()"]').focus();
      }}
    }}

    function populateRunSettings() {{
      const budget = RUN_SETTINGS.budget_cap_bdt == null ? 'No cap' : `BDT ${{Number(RUN_SETTINGS.budget_cap_bdt).toLocaleString()}}`;
      document.getElementById('catchment-radius').value = String(getDisplayCatchmentRadius());
      document.getElementById('catchment-radius-value').textContent = `${{(getDisplayCatchmentRadius() / 1000).toFixed(2)}} km`;
      document.getElementById('kpi-candidate-count').textContent = RAW_CANDIDATES.features.length;
      const solution = RAW_PARETO[0] || {{}};
      document.getElementById('kpi-station-count').textContent = solution.open_station_count ?? '—';
      document.getElementById('kpi-total-cost').textContent = solution.total_cost_million_bdt ?? '—';
      document.getElementById('kpi-demand-cov').textContent = solution.demand_coverage_pct ?? '—';
      document.getElementById('kpi-demand-zones').textContent = `${{RAW_DEMAND.features.length}} zones (input values; provenance required)`;
      document.getElementById('kpi-grid-power').textContent = solution.total_grid_power_kw ?? '—';
      document.getElementById('kpi-solution-id').textContent = solution.solution_id || 'No run output';
      document.getElementById('kpi-grid-status').textContent = RUN_SETTINGS.data_mode === 'demo' ? 'Synthetic demo' : 'Model output';
      document.getElementById('run-settings-summary').innerHTML = `
        <div class="rounded-lg bg-slate-800 p-2"><span class="text-slate-400">Run ID</span><div class="mt-1 font-bold text-white">${{RUN_SETTINGS.run_id || 'Not recorded'}}</div></div>
        <div class="rounded-lg bg-slate-800 p-2"><span class="text-slate-400">Input provenance</span><div class="mt-1 font-bold text-white">${{RUN_SETTINGS.provenance_status}}</div></div>
        <div class="rounded-lg bg-slate-800 p-2"><span class="text-slate-400">Stations (change settings and rerun)</span><div class="mt-1 font-bold text-white">${{RUN_SETTINGS.min_open_stations}}–${{RUN_SETTINGS.max_open_stations}}</div></div>
        <div class="rounded-lg bg-slate-800 p-2"><span class="text-slate-400">Chargers / site</span><div class="mt-1 font-bold text-white">${{RUN_SETTINGS.min_chargers_per_station}}–${{RUN_SETTINGS.max_chargers_per_station}}</div></div>
        <div class="rounded-lg bg-slate-800 p-2"><span class="text-slate-400">CAPEX budget</span><div class="mt-1 font-bold text-white">${{budget}}</div></div>
        <div class="rounded-lg bg-slate-800 p-2"><span class="text-slate-400">NSGA-II</span><div class="mt-1 font-bold text-white">${{RUN_SETTINGS.population_size}} × ${{RUN_SETTINGS.generations}}</div></div>
      `;
    }}

    function loadMapKey() {{
      try {{ document.getElementById('maptiler-key').value = localStorage.getItem('dhaka-evcs-maptiler-key') || ''; }} catch (e) {{}}
    }}

    function saveMapKey() {{
      const key = document.getElementById('maptiler-key').value.trim();
      const status = document.getElementById('map-settings-status');
      try {{
        if (key) localStorage.setItem('dhaka-evcs-maptiler-key', key);
        else localStorage.removeItem('dhaka-evcs-maptiler-key');
        status.textContent = 'Key saved in this browser only.';
        if (document.getElementById('settings-map-provider').value === 'maptiler') applyMapSettings();
      }} catch (e) {{ status.textContent = 'Browser storage unavailable; the key was not saved.'; }}
    }}

    function clearMapKey() {{
      document.getElementById('maptiler-key').value = '';
      try {{ localStorage.removeItem('dhaka-evcs-maptiler-key'); }} catch (e) {{}}
      document.getElementById('map-settings-status').textContent = 'Stored key cleared.';
      if (document.getElementById('settings-map-provider').value === 'maptiler') applyMapSettings();
    }}

    function toggleKeyVisibility() {{
      const input = document.getElementById('maptiler-key');
      input.type = input.type === 'password' ? 'text' : 'password';
    }}

    function applyMapSettings() {{
      const provider = document.getElementById('settings-map-provider').value;
      const status = document.getElementById('map-settings-status');
      try {{ localStorage.setItem('dhaka-evcs-map-provider', provider); }} catch (e) {{}}
      if (provider === 'maptiler') {{
        let key = document.getElementById('maptiler-key').value.trim();
        try {{ key = key || localStorage.getItem('dhaka-evcs-maptiler-key') || ''; }} catch (e) {{}}
        if (!key) {{
          status.textContent = 'Add a MapTiler key or choose OSM; switching to OpenStreetMap.';
          document.getElementById('settings-map-provider').value = 'osm';
          switchBaseMap('osm');
          return;
        }}
        const style = encodeURIComponent(RUN_SETTINGS.maptiler_style || 'streets-v2');
        if (activeBaseLayer) map.removeLayer(activeBaseLayer);
        activeBaseLayer = L.tileLayer(`https://api.maptiler.com/maps/${{style}}/{{z}}/{{x}}/{{y}}.png?key=${{encodeURIComponent(key)}}`, {{ maxZoom: 20, attribution: '&copy; MapTiler &copy; OpenStreetMap contributors' }});
        activeBaseLayer.addTo(map);
        status.textContent = 'MapTiler basemap active. Key stays in this browser.';
        setTimeout(() => map.invalidateSize(true), 100);
        return;
      }}
      status.textContent = provider === 'osm' ? 'OpenStreetMap does not require a key.' : 'Basemap updated.';
      switchBaseMap(provider === 'carto-light' ? 'light' : provider === 'carto-dark' ? 'dark' : 'osm');
    }}

    function resetDhakaCenter() {{
      map.flyTo([23.7850, 90.4000], 12, {{ duration: 1.2 }});
    }}

    function toggleSidebar() {{
      const sb = document.getElementById('sidebar');
      sb.classList.toggle('-translate-x-full');
    }}

    function switchSidebarTab(tabName) {{
      ['layers', 'sim', 'fleet'].forEach(t => {{
        const btn = document.getElementById('tab-btn-' + t);
        const content = document.getElementById('tab-content-' + t);
        if (t === tabName) {{
          btn.className = "flex-1 py-2 font-bold border-b-2 border-emerald-500 text-emerald-400 text-center";
          btn.setAttribute('aria-selected', 'true');
          content.classList.remove('hidden');
        }} else {{
          btn.className = "flex-1 py-2 font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 text-center";
          btn.setAttribute('aria-selected', 'false');
          content.classList.add('hidden');
        }}
      }});
    }}

    // 4. SOLUTION SELECTION & RE-RENDER
    function selectSolution(index) {{
      if (index >= RAW_PARETO.length) return;
      activeSolutionIndex = index;
      currentSolution = RAW_PARETO[index];
      activeStationIds = new Set((currentSolution.selected_station_ids || "").split(";"));

      // Update Top Nav Buttons
      ['knee', 'max', 'budget'].forEach((btnKey, idx) => {{
        const btn = document.getElementById('btn-sol-' + btnKey);
        if (!btn) return;
        btn.setAttribute('aria-pressed', String(idx === index));
        if (idx === index) {{
          btn.className = "px-2.5 py-1 rounded-lg font-bold bg-emerald-500 text-slate-950 shadow transition-all text-xs";
        }} else {{
          btn.className = "px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition-all text-xs";
        }}
      }});

      // Update KPI Cards
      document.getElementById('kpi-station-count').innerText = currentSolution.open_station_count ?? activeStationIds.size;
      document.getElementById('kpi-grid-power').innerText = Number.isFinite(Number(currentSolution.total_grid_power_kw)) ? (Number(currentSolution.total_grid_power_kw) / 1000).toFixed(1) : '—';
      document.getElementById('kpi-total-cost').innerText = Number.isFinite(Number(currentSolution.total_cost_million_bdt)) ? Number(currentSolution.total_cost_million_bdt).toFixed(1) : '—';
      document.getElementById('kpi-demand-cov').innerText = Number.isFinite(Number(currentSolution.demand_coverage_pct)) ? Number(currentSolution.demand_coverage_pct).toFixed(1) : '—';

      renderOptimalEVCS();
      renderAllCandidates();
      renderBuffers();
    }}

    // 5. SPATIAL RENDERING FUNCTIONS
    function renderAllLayers() {{
      renderOptimalEVCS();
      renderAllCandidates();
      renderSubstations();
      renderRoads();
      renderDemandGrid();
      renderHeatmap();
      renderBuffers();
      renderLanduse();
    }}

    function renderOptimalEVCS() {{
      layers.optimalEVCS.clearLayers();

      RAW_CANDIDATES.features.forEach(feat => {{
        const cid = feat.properties.candidate_id;
        if (!activeStationIds.has(cid)) return;

        const p = feat.properties;
        const rankInfo = RANKED_CANDIDATES[cid] || {{}};
        const ahp = Number(rankInfo.ahp_suitability_score ?? p.ahp_suitability_score);
        const zone = p.zone_name || rankInfo.zone_name || "";
        if (!Number.isFinite(ahp)) return;

        // Filters check
        if (ahp < currentMinAHP) return;
        if (selectedZone !== "ALL" && !zone.includes(selectedZone)) return;
        if (searchQuery && !p.site_name.toLowerCase().includes(searchQuery) && !zone.toLowerCase().includes(searchQuery)) return;

        const coords = feat.geometry.coordinates; // [lon, lat]

        const customIcon = L.divIcon({{
          className: 'evcs-marker-icon',
          html: `
            <div class="relative flex items-center justify-center transform -translate-x-1/2 -translate-y-1/2 cursor-pointer">
              <div class="absolute w-8 h-8 rounded-full bg-red-500/40 pulse-ring"></div>
              <div class="w-7 h-7 rounded-full bg-red-500 flex items-center justify-center text-white text-xs shadow-xl border-2 border-white">
                <i class="fa-solid fa-plug text-[10px]"></i>
              </div>
            </div>
          `,
          iconSize: [28, 28]
        }});

        const marker = L.marker([coords[1], coords[0]], {{ icon: customIcon }});
        marker.on('click', () => showStationInspector(p, rankInfo, true));
        marker.bindTooltip(`<b>${{p.site_name}}</b><br><span class="text-red-400 font-bold">Optimal EVCS</span> · AHP: ${{ahp.toFixed(3)}}`, {{
          direction: 'top',
          className: 'bg-slate-900 text-white text-xs border border-slate-700 rounded-lg px-2 py-1'
        }});

        marker.addTo(layers.optimalEVCS);
      }});
    }}

    function renderAllCandidates() {{
      layers.allCandidates.clearLayers();

      RAW_CANDIDATES.features.forEach(feat => {{
        const cid = feat.properties.candidate_id;
        if (activeStationIds.has(cid)) return; // Rendered in optimal layer

        const p = feat.properties;
        const rankInfo = RANKED_CANDIDATES[cid] || {{}};
        const ahp = Number(rankInfo.ahp_suitability_score ?? p.ahp_suitability_score);
        const zone = p.zone_name || rankInfo.zone_name || "";
        if (!Number.isFinite(ahp)) return;

        if (ahp < currentMinAHP) return;
        if (selectedZone !== "ALL" && !zone.includes(selectedZone)) return;

        const coords = feat.geometry.coordinates;

        const marker = L.circleMarker([coords[1], coords[0]], {{
          radius: 6,
          fillColor: '#94a3b8',
          color: '#334155',
          weight: 1.5,
          opacity: 0.9,
          fillOpacity: 0.7
        }});

        marker.on('click', () => showStationInspector(p, rankInfo, false));
        marker.bindTooltip(`<b>${{p.site_name}}</b><br>Candidate Site (AHP: ${{ahp.toFixed(3)}})`, {{ direction: 'top' }});
        marker.addTo(layers.allCandidates);
      }});
    }}

    function renderSubstations() {{
      layers.substations.clearLayers();

      RAW_SUBSTATIONS.forEach(sub => {{
        const isDPDC = sub.utility === 'DPDC';
        const color = isDPDC ? '#2563eb' : '#7c3aed';

        const customIcon = L.divIcon({{
          className: 'sub-marker-icon',
          html: `
            <div style="background-color: ${{color}};" class="w-6 h-6 rounded-lg flex items-center justify-center text-white text-[11px] shadow-lg border border-slate-900 transform -translate-x-1/2 -translate-y-1/2 cursor-pointer hover:scale-110 transition">
              <i class="fa-solid fa-bolt"></i>
            </div>
          `,
          iconSize: [24, 24]
        }});

        const marker = L.marker([sub.lat, sub.lon], {{ icon: customIcon }});
        marker.on('click', () => showSubstationInspector(sub));
        marker.bindTooltip(`<b>${{sub.name}}</b><br><span style="color:${{color}}">${{sub.utility}} Substation</span> · Headroom: ${{sub.headroom_mva}} MVA`, {{ direction: 'top' }});
        marker.addTo(layers.substations);
      }});
    }}

    function renderRoads() {{
      layers.roads.clearLayers();
      if (!RAW_ROADS || !RAW_ROADS.features) return;

      L.geoJSON(RAW_ROADS, {{
        style: (feature) => {{
          const isPrimary = (feature.properties.highway || '').includes('primary') || (feature.properties.highway || '').includes('trunk');
          return {{
            color: isPrimary ? '#38bdf8' : '#64748b',
            weight: isPrimary ? 2.5 : 1.2,
            opacity: 0.65
          }};
        }}
      }}).addTo(layers.roads);
    }}

    function renderDemandGrid() {{
      layers.demandGrid.clearLayers();
      if (!RAW_DEMAND || !RAW_DEMAND.features) return;

      RAW_DEMAND.features.forEach(feat => {{
        const coords = feat.geometry.coordinates;
        const dVal = Number(feat.properties.daily_demand_kwh ?? feat.properties.demand_kwh_day);
        if (!Number.isFinite(dVal)) return;

        const marker = L.circleMarker([coords[1], coords[0]], {{
          radius: Math.min(6, Math.max(2.5, dVal / 500)),
          fillColor: '#06b6d4',
          color: '#0891b2',
          weight: 0.5,
          fillOpacity: 0.5
        }});
        marker.bindTooltip(`Demand Centroid: ${{dVal.toFixed(0)}} kWh/day`, {{ direction: 'top' }});
        marker.addTo(layers.demandGrid);
      }});
    }}

    function renderHeatmap() {{
      layers.heatmap.clearLayers();
      const heatPoints = RAW_CANDIDATES.features.map(f => [
        f.geometry.coordinates[1],
        f.geometry.coordinates[0],
        f.properties.ahp_suitability_score || 0.7
      ]);
      L.heatLayer(heatPoints, {{ radius: 28, blur: 18, maxZoom: 14, max: 1.0 }}).addTo(layers.heatmap);
    }}

    function getDisplayCatchmentRadius() {{
      try {{ return Math.min(10000, Math.max(500, Number(localStorage.getItem('dhaka-evcs-display-radius-m')) || RUN_SETTINGS.service_radius_rmax_m)); }}
      catch (e) {{ return RUN_SETTINGS.service_radius_rmax_m; }}
    }}

    function updateCatchmentRadius(value) {{
      const radius = Number(value);
      document.getElementById('catchment-radius-value').textContent = `${{(radius / 1000).toFixed(2)}} km`;
      try {{ localStorage.setItem('dhaka-evcs-display-radius-m', String(radius)); }} catch (e) {{}}
      renderBuffers();
    }}

    function renderBuffers() {{
      layers.buffers.clearLayers();
      RAW_CANDIDATES.features.forEach(feat => {{
        const cid = feat.properties.candidate_id;
        if (!activeStationIds.has(cid)) return;
        const coords = feat.geometry.coordinates;

        L.circle([coords[1], coords[0]], {{
          radius: getDisplayCatchmentRadius(),
          color: '#10b981',
          weight: 1,
          dashArray: '4, 4',
          fillColor: '#10b981',
          fillOpacity: 0.04
        }}).addTo(layers.buffers);
      }});
    }}

    function renderLanduse() {{
      layers.landuse.clearLayers();
      if (!RAW_LANDUSE || !RAW_LANDUSE.features) return;

      L.geoJSON(RAW_LANDUSE, {{
        style: (feature) => {{
          const zType = feature.properties.zone_type || '';
          if (zType === 'Waterbody') return {{ color: '#0284c7', fillColor: '#0369a1', fillOpacity: 0.25, weight: 1 }};
          if (zType === 'Flood_Hazard') return {{ color: '#e11d48', fillColor: '#be123c', fillOpacity: 0.2, weight: 1 }};
          return {{ color: '#a855f7', fillColor: '#9333ea', fillOpacity: 0.08, weight: 1 }};
        }}
      }}).addTo(layers.landuse);
    }}

    function toggleLayer(layerKey, isVisible) {{
      const layerMap = {{
        'opt-evcs': layers.optimalEVCS,
        'all-cand': layers.allCandidates,
        'substations': layers.substations,
        'heatmap': layers.heatmap,
        'demand': layers.demandGrid,
        'buffers': layers.buffers,
        'landuse': layers.landuse
      }};
      const mapLayer = layerMap[layerKey];

      if (!mapLayer) return;
      if (isVisible) {{
        mapLayer.addTo(map);
      }} else {{
        map.removeLayer(mapLayer);
      }}
    }}

    function applyFilters() {{
      selectedZone = document.getElementById('zone-filter-select').value;
      currentMinAHP = parseFloat(document.getElementById('ahp-range-input').value);
      renderOptimalEVCS();
      renderAllCandidates();
      renderBuffers();
    }}

    // 6. ONLINE REAL-TIME INTEGRATIONS
    async function initLiveWeather() {{
      try {{
        // Live Dhaka Weather via Open-Meteo API (Latitude: 23.8103, Longitude: 90.4125)
        const res = await fetch('https://api.open-meteo.com/v1/forecast?latitude=23.8103&longitude=90.4125&current=temperature_2m,relative_humidity_2m,direct_normal_irradiance');
        if (!res.ok) return;
        const data = await res.json();
        const temp = data.current.temperature_2m;
        const humidity = data.current.relative_humidity_2m;
        const dni = data.current.direct_normal_irradiance || 450;

        const badge = document.getElementById('live-weather-badge');
        const text = document.getElementById('weather-text');
        text.innerText = `Dhaka ${{temp}}°C · ${{humidity}}% RH · ${{dni}} W/m² GHI`;
        badge.classList.remove('hidden');
      }} catch (err) {{
        console.log('Online weather fetch fallback:', err);
      }}
    }}

    async function fetchOnlineOSMData() {{
      const icon = document.getElementById('online-sync-icon');
      icon.classList.add('fa-spin');

      try {{
        // Query OpenStreetMap Overpass API for fuel and charging amenities in Dhaka Bounding Box
        const overpassQuery = `
          [out:json][timeout:15];
          (
            node["amenity"="fuel"](23.70,90.34,23.89,90.45);
            node["amenity"="charging_station"](23.70,90.34,23.89,90.45);
          );
          out body 25;
        `;
        const res = await fetch('https://overpass-api.de/api/interpreter', {{
          method: 'POST',
          body: overpassQuery
        }});

        if (!res.ok) throw new Error('Overpass API returned ' + res.status);
        const data = await res.json();

        layers.liveAmenities.clearLayers();
        let count = 0;
        data.elements.forEach(el => {{
          if (!el.lat || !el.lon) return;
          count++;
          const isFuel = el.tags && el.tags.amenity === 'fuel';
          const name = (el.tags && (el.tags.name || el.tags['name:en'])) || (isFuel ? 'CNG/Fuel Station' : 'Live EV Charger');

          const customIcon = L.divIcon({{
            className: 'live-osm-icon',
            html: `
              <div class="w-5 h-5 rounded-full bg-amber-500 text-slate-950 flex items-center justify-center text-[10px] shadow-lg border border-slate-900 cursor-pointer">
                <i class="fa-solid fa-gas-pump"></i>
              </div>
            `,
            iconSize: [20, 20]
          }});

          const marker = L.marker([el.lat, el.lon], {{ icon: customIcon }});
          marker.bindTooltip(`<b>${{name}}</b><br><span class="text-amber-400">Live OSM Ref: #${{el.id}}</span>`, {{ direction: 'top' }});
          marker.addTo(layers.liveAmenities);
        }});

        alert(`Successfully synced ${{count}} live fuel/energy facilities from OpenStreetMap servers into the map!`);
      }} catch (err) {{
        console.error(err);
        alert('Live Overpass fetch timed out or offline. Utilizing embedded high-resolution Dhaka spatial matrices.');
      }} finally {{
        icon.classList.remove('fa-spin');
      }}
    }}

    async function executeLiveSearch() {{
      const input = document.getElementById('spatial-search-input');
      const q = input.value.trim();
      if (!q) return;

      const dropdown = document.getElementById('search-results-dropdown');
      dropdown.innerHTML = '<div class="text-slate-400 p-2"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Searching online...</div>';
      dropdown.classList.remove('hidden');

      // Check local candidates first
      const matches = RAW_CANDIDATES.features.filter(f =>
        f.properties.site_name.toLowerCase().includes(q.toLowerCase()) ||
        f.properties.zone_name.toLowerCase().includes(q.toLowerCase())
      );

      let html = '';
      matches.slice(0, 4).forEach(m => {{
        const p = m.properties;
        html += `
          <div onclick="flyToCoords(${{m.geometry.coordinates[1]}}, ${{m.geometry.coordinates[0]}}, '${{p.site_name}}')" class="p-2 hover:bg-slate-800 rounded-lg cursor-pointer flex items-center justify-between">
            <div>
              <div class="font-bold text-emerald-400">${{p.site_name}}</div>
              <div class="text-[10px] text-slate-400">${{p.zone_name}} · Candidate #${{p.candidate_id}}</div>
            </div>
            <span class="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded">Local</span>
          </div>
        `;
      }});

      // Query OpenStreetMap Nominatim for online geocoding
      try {{
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${{encodeURIComponent(q + ', Dhaka, Bangladesh')}}&limit=3`);
        if (res.ok) {{
          const geoData = await res.json();
          geoData.forEach(item => {{
            html += `
              <div onclick="flyToCoords(${{item.lat}}, ${{item.lon}}, '${{item.display_name.replace(/'/g, "")}}')" class="p-2 hover:bg-slate-800 rounded-lg cursor-pointer flex items-center justify-between border-t border-slate-800">
                <div class="truncate max-w-[220px]">
                  <div class="font-semibold text-white truncate">${{item.display_name.split(',')[0]}}</div>
                  <div class="text-[10px] text-slate-400 truncate">${{item.display_name}}</div>
                </div>
                <span class="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded shrink-0">OSM Live</span>
              </div>
            `;
          }});
        }}
      }} catch (e) {{}}

      if (!html) {{
        html = '<div class="text-slate-400 p-2 text-center">No location matches found.</div>';
      }}
      dropdown.innerHTML = html;
    }}

    function flyToCoords(lat, lon, label) {{
      map.flyTo([lat, lon], 15, {{ duration: 1.5 }});
      document.getElementById('search-results-dropdown').classList.add('hidden');
    }}

    // 7. INSPECTOR PANELS
    function showStationInspector(p, rankInfo, isOptimal) {{
      const card = document.getElementById('inspector-card');
      const title = document.getElementById('insp-title');
      const subtitle = document.getElementById('insp-subtitle');
      const icon = document.getElementById('insp-icon');
      const body = document.getElementById('insp-body');

      title.innerText = p.site_name || 'Station';
      subtitle.innerText = `${{p.zone_name || 'Dhaka'}} · ID: ${{p.candidate_id}}`;

      icon.className = isOptimal
        ? "w-8 h-8 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center font-bold text-sm"
        : "w-8 h-8 rounded-xl bg-slate-700 text-slate-300 flex items-center justify-center font-bold text-sm";
      icon.innerHTML = `<i class="fa-solid fa-charging-station"></i>`;

      const formatMetric = (value, digits = 0) => Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined, {{ maximumFractionDigits: digits }}) : 'Not available';
      const ahp = formatMetric(rankInfo.ahp_suitability_score ?? p.ahp_suitability_score, 3);
      const landCost = formatMetric(p.land_cost_bdt_sqm);
      const subDist = formatMetric(p.distance_to_substation_m);
      const headroom = formatMetric(p.substation_headroom_mva, 2);

      body.innerHTML = `
        <div class="grid grid-cols-2 gap-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
          <div>
            <span class="text-slate-400 text-[10px]">AHP Score:</span>
            <div class="font-bold text-emerald-400 font-mono text-sm">${{ahp}}</div>
          </div>
          <div>
            <span class="text-slate-400 text-[10px]">Optimization Status:</span>
            <div class="font-bold ${{isOptimal ? 'text-red-400' : 'text-slate-400'}} text-xs">
              ${{isOptimal ? '★ Selected EVCS' : 'Candidate (Available)'}}
            </div>
          </div>
          <div>
            <span class="text-slate-400 text-[10px]">Land Valuation:</span>
            <div class="font-medium text-slate-200">BDT ${{landCost}}/m²</div>
          </div>
          <div>
            <span class="text-slate-400 text-[10px]">Grid Substation:</span>
            <div class="font-medium text-slate-200">${{subDist}} m (${{headroom}} MVA)</div>
          </div>
        </div>

        <div class="space-y-1.5 pt-1">
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Charger allocation</div>
          <div class="text-xs text-slate-400">See the selected solution's allocation summary. Per-site charger counts are not available in this result table.</div>
        </div>
      `;

      card.classList.remove('hidden');
    }}

    function showSubstationInspector(sub) {{
      const card = document.getElementById('inspector-card');
      const title = document.getElementById('insp-title');
      const subtitle = document.getElementById('insp-subtitle');
      const icon = document.getElementById('insp-icon');
      const body = document.getElementById('insp-body');

      title.innerText = sub.name;
      subtitle.innerText = `${{sub.utility}} 33/11kV Primary Substation`;

      const isDPDC = sub.utility === 'DPDC';
      icon.className = `w-8 h-8 rounded-xl ${{isDPDC ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'}} flex items-center justify-center font-bold text-sm`;
      icon.innerHTML = `<i class="fa-solid fa-bolt"></i>`;

      const formatSubstationMetric = value => Number.isFinite(Number(value)) ? Number(value).toLocaleString() : 'Not available';
      body.innerHTML = `
        <div class="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800 text-xs">
          <div class="flex justify-between">
            <span class="text-slate-400">Substation ID:</span>
            <span class="font-mono font-bold text-white">${{sub.sub_id ?? 'Not available'}}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">Rated capacity:</span>
            <span class="font-bold text-slate-200">${{formatSubstationMetric(sub.rated_mva)}} MVA</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">Calculated headroom:</span>
            <span class="font-bold text-emerald-400">${{formatSubstationMetric(sub.headroom_mva)}} MVA</span>
          </div>
          <div class="text-[10px] text-slate-400">Values depend on the supplied input dataset; this display is not live utility telemetry.</div>
        </div>
      `;

      card.classList.remove('hidden');
    }}

    function closeInspector() {{
      document.getElementById('inspector-card').classList.add('hidden');
    }}

    // 8. DYNAMIC GRID SIMULATION STUDIO
    function updateGridSimulation() {{
      const pen = parseFloat(document.getElementById('sim-penetration').value);
      const peak = parseFloat(document.getElementById('sim-peak-factor').value);
      const solar = parseFloat(document.getElementById('sim-solar-offset').value);

      document.getElementById('sim-pen-val').innerText = `${{pen}}%`;
      document.getElementById('sim-peak-val').innerText = `${{peak}}%`;
      document.getElementById('sim-solar-val').innerText = `${{solar}}%`;

      const baseMW = 21.6 * (pen / 20.0) * (peak / 65.0);
      const solarMW = baseMW * (solar / 100.0);
      const netMW = baseMW - solarMW;
      const minV = Math.max(0.945, 0.985 - (netMW * 0.0012));
      const vdi = (1.0 - minV) * 100;

      document.getElementById('sim-out-evload').innerText = `${{baseMW.toFixed(2)}} MW`;
      document.getElementById('sim-out-solar').innerText = `-${{solarMW.toFixed(2)}} MW`;
      document.getElementById('sim-out-netpower').innerText = `${{netMW.toFixed(2)}} MW`;
      document.getElementById('sim-out-minvoltage').innerText = `${{minV.toFixed(3)}} p.u. ${{minV >= 0.95 ? '(OK)' : '(UNDER-VOLTAGE)'}}`;
      document.getElementById('sim-out-minvoltage').className = minV >= 0.95 ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold';
      document.getElementById('sim-out-vdi').innerText = `${{vdi.toFixed(1)}}% (${{vdi <= 5.0 ? 'Feasible' : 'Exceeds IEEE 519'}})`;
    }}

    // 9. CHARTS & RESEARCH ANALYTICS MODAL
    let paretoChartInstance = null;
    let voltageChartInstance = null;

    function toggleAnalyticsModal(forceOpen) {{
      const modal = document.getElementById('analytics-modal');
      const opening = typeof forceOpen === 'boolean' ? forceOpen : modal.classList.contains('hidden');
      modal.classList.toggle('hidden', !opening);
      if (opening) {{
        setTimeout(() => {{
          if (paretoChartInstance) paretoChartInstance.resize();
          if (voltageChartInstance) voltageChartInstance.resize();
          modal.querySelector('button[aria-label="Close analytics"]').focus();
        }}, 50);
      }} else {{
        document.querySelector('[onclick="toggleAnalyticsModal()"]').focus();
      }}
    }}

    function paretoSolutionRoles() {{
      if (!RAW_PARETO.length) return new Map();
      const cost = sol => Number(sol.total_cost_bdt ?? (Number(sol.total_cost_million_bdt) * 1e6));
      const coverage = sol => Number(sol.demand_coverage_score ?? sol.demand_coverage_pct);
      const minCost = RAW_PARETO.reduce((best, sol) => cost(sol) < cost(best) ? sol : best, RAW_PARETO[0]);
      const maxCoverage = RAW_PARETO.reduce((best, sol) => coverage(sol) > coverage(best) ? sol : best, RAW_PARETO[0]);
      const costs = RAW_PARETO.map(cost), coverages = RAW_PARETO.map(coverage);
      const cMin = Math.min(...costs), cMax = Math.max(...costs), vMin = Math.min(...coverages), vMax = Math.max(...coverages);
      const p1 = [1, 0], p2 = [0, 1];
      const dx = p2[0] - p1[0], dy = p2[1] - p1[1], length = Math.hypot(dx, dy) || 1;
      let knee = RAW_PARETO[0], maxDistance = -1;
      RAW_PARETO.forEach(sol => {{
        const x = cMax === cMin ? 0 : 1 - (cost(sol) - cMin) / (cMax - cMin);
        const y = vMax === vMin ? 0 : (coverage(sol) - vMin) / (vMax - vMin);
        const distance = Math.abs(dx * (p1[1] - y) - dy * (p1[0] - x)) / length;
        if (distance > maxDistance) {{ maxDistance = distance; knee = sol; }}
      }});
      const roles = new Map();
      for (const sol of [minCost, maxCoverage, knee]) {{
        const labels = roles.get(sol.solution_id) || [];
        const label = sol === minCost ? 'Minimum cost' : sol === maxCoverage ? 'Maximum coverage' : 'Knee point';
        if (!labels.includes(label)) labels.push(label);
        roles.set(sol.solution_id, labels);
      }}
      return roles;
    }}

    function populateParetoTable() {{
      const tbody = document.getElementById('pareto-table-body');
      if (!tbody) return;
      if (!RAW_PARETO.length) {{
        tbody.innerHTML = '<tr><td colspan="8" class="py-6 text-center text-slate-400">No Pareto solutions are available for this run.</td></tr>';
        return;
      }}
      const roles = paretoSolutionRoles();
      tbody.innerHTML = RAW_PARETO.map(sol => `
        <tr class="hover:bg-slate-900/80 transition">
          <td class="py-2 px-3 font-bold text-white">${{sol.solution_id}}</td>
          <td class="py-2 px-3 text-emerald-400">${{roles.get(sol.solution_id)?.join(' · ') || 'Pareto alternative'}}</td>
          <td class="py-2 px-3">${{sol.open_station_count}} Sites</td>
          <td class="py-2 px-3">${{Number.isFinite(Number(sol.total_cost_million_bdt)) ? Number(sol.total_cost_million_bdt).toFixed(1) : '—'}}</td>
          <td class="py-2 px-3">${{Number.isFinite(Number(sol.total_cost_million_usd)) ? Number(sol.total_cost_million_usd).toFixed(1) : '—'}}</td>
          <td class="py-2 px-3 text-emerald-400">${{Number.isFinite(Number(sol.demand_coverage_pct)) ? Number(sol.demand_coverage_pct).toFixed(1) + '%' : '—'}}</td>
          <td class="py-2 px-3">${{Number.isFinite(Number(sol.total_grid_power_kw)) ? Number(sol.total_grid_power_kw).toFixed(0) + ' kW' : '—'}}</td>
          <td class="py-2 px-3">${{RUN_SETTINGS.data_mode === 'demo' ? 'Synthetic demo' : 'Model result'}}</td>
        </tr>
      `).join('');
    }}

    function downloadParetoCsv() {{
      if (!RAW_PARETO.length) return;
      const columns = [...new Set(RAW_PARETO.flatMap(row => Object.keys(row)))];
      const quote = value => `"${{String(value ?? '').replaceAll('"', '""')}}"`;
      const csv = [columns.map(quote).join(','), ...RAW_PARETO.map(row => columns.map(key => quote(row[key])).join(','))].join('\\r\\n');
      const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8' }});
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'pareto_solutions.csv';
      anchor.click();
      URL.revokeObjectURL(url);
    }}

    function initCharts() {{
      // 1. Pareto Frontier Curve
      const darkTheme = document.documentElement.getAttribute('data-theme') === 'dark' || (!document.documentElement.hasAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
      const chartInk = darkTheme ? '#cbd5e1' : '#334155';
      const chartGrid = darkTheme ? 'rgba(148, 163, 184, 0.2)' : 'rgba(100, 116, 139, 0.22)';
      const paretoCtx = document.getElementById('paretoChartCanvas');
      if (paretoCtx) {{
        const paretoPoints = RAW_PARETO.filter(sol => Number.isFinite(Number(sol.total_cost_million_bdt)) && Number.isFinite(Number(sol.demand_coverage_pct))).map(sol => ({{
          x: Number(sol.total_cost_million_bdt),
          y: Number(sol.demand_coverage_pct),
          solId: sol.solution_id
        }}));

        paretoChartInstance = new Chart(paretoCtx, {{
          type: 'line',
          data: {{
            datasets: [{{
              label: 'NSGA-II Pareto Frontier',
              data: paretoPoints,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.2)',
              borderWidth: 2.5,
              pointBackgroundColor: ['#ef4444', '#3b82f6', '#f59e0b'],
              pointRadius: 6,
              pointHoverRadius: 9,
              showLine: true,
              tension: 0.2
            }}]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
              legend: {{ labels: {{ color: chartInk, font: {{ family: 'Plus Jakarta Sans', size: 11 }} }} }}
            }},
            scales: {{
              x: {{
                title: {{ display: true, text: 'Total Social Cost (Million BDT)', color: chartInk }},
                grid: {{ color: chartGrid }},
                ticks: {{ color: chartInk }}
              }},
              y: {{
                title: {{ display: true, text: 'Spatial Demand Coverage (%)', color: chartInk }},
                grid: {{ color: chartGrid }},
                ticks: {{ color: chartInk }}
              }}
            }}
          }}
        }});
      }}

      // 2. Substation Voltage Stability Profile
      const voltCtx = document.getElementById('voltageChartCanvas');
      if (voltCtx && BUS_VOLTAGES.length) {{
        const labels = BUS_VOLTAGES.map(b => b.name.replace(/_Substation|_DPDC|_DESCO/g, ''));
        const baseVals = BUS_VOLTAGES.map(b => b.base_pu);
        const evVals = BUS_VOLTAGES.map(b => b.ev_pu);

        voltageChartInstance = new Chart(voltCtx, {{
          type: 'bar',
          data: {{
            labels: labels,
            datasets: [
              {{
                label: 'Baseline Grid Voltage (p.u.)',
                data: baseVals,
                backgroundColor: 'rgba(59, 130, 246, 0.7)',
                borderRadius: 4
              }},
              {{
                label: 'EVCS Loaded Voltage (p.u.)',
                data: evVals,
                backgroundColor: 'rgba(239, 68, 68, 0.8)',
                borderRadius: 4
              }}
            ]
          }},
          options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
              legend: {{ labels: {{ color: chartInk, font: {{ family: 'Plus Jakarta Sans', size: 11 }} }} }}
            }},
            scales: {{
              x: {{
                grid: {{ display: false }},
                ticks: {{ color: chartInk, font: {{ size: 9 }}, maxRotation: 45 }}
              }},
              y: {{
                min: 0.94,
                max: 1.02,
                title: {{ display: true, text: 'Voltage (p.u.) [Limit: 0.95 - 1.05]', color: chartInk }},
                grid: {{ color: chartGrid }},
                ticks: {{ color: chartInk }}
              }}
            }}
          }}
        }});
      }} else if (voltCtx) {{
        voltCtx.parentElement.innerHTML = '<p class="text-sm text-slate-500 p-4">No verified grid-voltage result was provided for this dashboard.</p>';
      }}
    }}

    function exportGeoJSON() {{
      const selectedFeats = RAW_CANDIDATES.features.filter(f => activeStationIds.has(f.properties.candidate_id));
      const exportObj = {{
        type: "FeatureCollection",
        solution_id: currentSolution.solution_id,
        crs: {{ type: "name", properties: {{ name: "urn:ogc:def:crs:OGC:1.3:CRS84" }} }},
        features: selectedFeats
      }};
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `dhaka_optimal_evcs_${{currentSolution.solution_id}}.geojson`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    }}
  </script>
</body>
</html>
"""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    if deploy_copies:
        docs_path = base_dir / "docs" / "index.html"
        interactive_path = base_dir / "results" / "figures" / "dhaka_evcs_interactive_map.html"
        for destination in (docs_path, interactive_path):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(html_content, encoding="utf-8")
        print(f"[Visualization] Explicitly deployed dashboard copies to: {docs_path}, {interactive_path}")
    print(f"[Visualization] Standalone dashboard generated at: {output_file}")
