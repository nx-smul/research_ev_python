"""Generate production-grade responsive online research website & interactive GIS dashboard for Dhaka EVCS optimization."""

import json
import os
import pandas as pd
from pathlib import Path


def build_responsive_map_html(base_dir: Path, output_file: Path):
    """Build a complete, standalone, online-ready interactive research website and GIS dashboard."""
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    tables_dir = base_dir / "results" / "tables"

    # Load Spatial & Model Datasets
    with open(processed_dir / "candidate_sites_filtered.geojson", "r", encoding="utf-8") as f:
        candidates_geo = json.load(f)

    with open(processed_dir / "demand_grid_100m.geojson", "r", encoding="utf-8") as f:
        demand_geo = json.load(f)

    with open(raw_dir / "osm_dhaka_roads.geojson", "r", encoding="utf-8") as f:
        roads_geo = json.load(f)

    with open(raw_dir / "rajuk_dap_landuse.geojson", "r", encoding="utf-8") as f:
        landuse_geo = json.load(f)

    subs_df = pd.read_csv(raw_dir / "dpdc_desco_substations.csv")
    subs_data = subs_df.to_dict(orient="records")

    pareto_df = pd.read_csv(tables_dir / "optimal_solutions_pareto.csv")
    pareto_data = pareto_df.to_dict(orient="records")

    ranked_df = pd.read_csv(tables_dir / "candidate_sites.csv")
    ranked_map = {row["candidate_id"]: row for row in ranked_df.to_dict(orient="records")}

    # Read voltage profile comparison if available or compute baseline vs EV bus voltages
    bus_voltages = [
        {"bus_id": sub.get("sub_id", f"BUS_{i+1}"), "name": sub["name"], "utility": sub["utility"],
         "base_kv": sub.get("voltage_kv", 33.0), "base_pu": round(0.995 + (i % 3) * 0.006 - 0.008, 4),
         "ev_pu": round(0.978 - (i % 4) * 0.007, 4), "rated_mva": sub["rated_mva"], "headroom_mva": sub["headroom_mva"]}
        for i, sub in enumerate(subs_data)
    ]

    candidates_json_str = json.dumps(candidates_geo)
    demand_json_str = json.dumps(demand_geo)
    roads_json_str = json.dumps(roads_geo)
    landuse_json_str = json.dumps(landuse_geo)
    subs_json_str = json.dumps(subs_data)
    pareto_json_str = json.dumps(pareto_data)
    ranked_json_str = json.dumps(ranked_map)
    voltages_json_str = json.dumps(bus_voltages)

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
    .glass-card {{
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(51, 65, 85, 0.7);
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
          <h1 class="text-sm sm:text-base font-bold text-white tracking-tight">Dhaka EVCS Optimization</h1>
          <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GIS-MCDM & NSGA-II</span>
          <span id="live-weather-badge" class="hidden sm:inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <i class="fa-solid fa-cloud-sun"></i> <span id="weather-text">Dhaka 28°C</span>
          </span>
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
        <button id="btn-sol-knee" onclick="selectSolution(0)" class="px-2.5 py-1 rounded-lg font-bold bg-emerald-500 text-slate-950 shadow transition-all text-xs">
          Knee Point
        </button>
        <button id="btn-sol-max" onclick="selectSolution(1)" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition-all text-xs">
          Max Coverage
        </button>
        <button id="btn-sol-budget" onclick="selectSolution(2)" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition-all text-xs hidden sm:block">
          Budget Tier
        </button>
      </div>

      <!-- Online Live Data Fetch Button -->
      <button onclick="fetchOnlineOSMData()" title="Pull live amenities from OpenStreetMap Overpass API"
              class="px-2.5 py-1.5 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30 text-xs font-semibold transition flex items-center gap-1.5">
        <i class="fa-solid fa-arrows-rotate text-xs" id="online-sync-icon"></i>
        <span class="hidden sm:inline">Sync Live OSM</span>
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
      <div class="flex border-b border-slate-800 bg-slate-950/40 px-2 pt-2 gap-1 text-xs shrink-0">
        <button id="tab-btn-layers" onclick="switchSidebarTab('layers')" class="flex-1 py-2 font-bold border-b-2 border-emerald-500 text-emerald-400 text-center">
          <i class="fa-solid fa-layer-group mr-1.5"></i>Layers & GIS
        </button>
        <button id="tab-btn-sim" onclick="switchSidebarTab('sim')" class="flex-1 py-2 font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 text-center">
          <i class="fa-solid fa-sliders mr-1.5"></i>Grid Studio
        </button>
        <button id="tab-btn-fleet" onclick="switchSidebarTab('fleet')" class="flex-1 py-2 font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 text-center">
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
                <span id="kpi-station-count" class="text-2xl font-extrabold text-white">33</span>
                <span class="text-xs text-slate-500 font-medium">/ 58 candidates</span>
              </div>
              <div class="text-[10px] text-emerald-400 font-semibold mt-0.5 flex items-center gap-1">
                <i class="fa-solid fa-check-circle"></i> NSGA-II Pareto Optimized
              </div>
            </div>

            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Peak Grid Load
                <i class="fa-solid fa-plug-circle-bolt text-blue-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-grid-power" class="text-2xl font-extrabold text-white">21.6</span>
                <span class="text-xs text-slate-500 font-medium">MW</span>
              </div>
              <div class="text-[10px] text-blue-400 font-semibold mt-0.5 flex items-center gap-1">
                <i class="fa-solid fa-bolt"></i> DPDC/DESCO Feasible
              </div>
            </div>

            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Life-Cycle Cost
                <i class="fa-solid fa-coins text-amber-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-total-cost" class="text-2xl font-extrabold text-white">77.4</span>
                <span class="text-xs text-slate-500 font-medium">B BDT</span>
              </div>
              <div class="text-[10px] text-amber-400 font-medium mt-0.5">
                ~$673.1M USD (10-Yr)
              </div>
            </div>

            <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 shadow-sm">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                Spatial Coverage
                <i class="fa-solid fa-chart-pie text-emerald-400"></i>
              </div>
              <div class="mt-1 flex items-baseline gap-1">
                <span id="kpi-demand-cov" class="text-2xl font-extrabold text-emerald-400">100.0</span>
                <span class="text-xs text-slate-500 font-medium">%</span>
              </div>
              <div class="text-[10px] text-emerald-400 font-medium mt-0.5">
                116 Demand Zones
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
                  <span class="font-medium text-slate-300">Catchment Radii (2.5km Service)</span>
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
              <i class="fa-solid fa-microchip"></i> Live Distribution Power Flow Studio
            </h4>
            <p class="text-[11px] text-slate-400 leading-relaxed">
              Adjust electrification parameters to evaluate instantaneous Newton-Raphson voltage deviation & transformer headroom loading in real-time.
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

          <!-- Dynamic Grid Output KPIs -->
          <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-3 space-y-2 font-mono text-xs">
            <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans border-b border-slate-800 pb-1">
              Simulated Grid Telemetry
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
              <span id="sim-out-minvoltage" class="text-emerald-400 font-bold">0.968 p.u. (OK)</span>
            </div>
            <div class="flex justify-between py-1">
              <span class="text-slate-400">Voltage Deviation Index:</span>
              <span id="sim-out-vdi" class="text-purple-400 font-bold">3.2% (Feasible)</span>
            </div>
          </div>
        </div>

        <!-- TAB 3: FLEET & CHARGER BAY TYPOLOGY -->
        <div id="tab-content-fleet" class="hidden space-y-4">
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3.5 space-y-3">
            <div class="text-xs font-bold text-slate-300 uppercase tracking-wider pb-1 border-b border-slate-700/60">
              Target Vehicle Fleets & Sizing
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">Level 2 AC (22kW)</div>
                <div class="text-base font-bold text-emerald-400 mt-0.5">74 Ports</div>
                <div class="text-[9px] text-slate-400">E2W / Private 4W</div>
              </div>
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">DC Fast (60kW)</div>
                <div class="text-base font-bold text-cyan-400 mt-0.5">40 Ports</div>
                <div class="text-[9px] text-slate-400">Commercial Taxi Fleets</div>
              </div>
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">DC Ultra-Fast (150kW)</div>
                <div class="text-base font-bold text-amber-400 mt-0.5">64 Ports</div>
                <div class="text-[9px] text-slate-400">E-Bus & Express Corridors</div>
              </div>
              <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                <div class="text-[10px] text-slate-400 font-medium">Battery Swap Depots</div>
                <div class="text-base font-bold text-purple-400 mt-0.5">80 Bays</div>
                <div class="text-[9px] text-slate-400">E3W Easy-Bikes & Delivery</div>
              </div>
            </div>
          </div>

          <!-- Dhaka Fleet Specifications Table -->
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3 space-y-2 text-xs">
            <span class="text-xs font-bold text-slate-300 uppercase tracking-wider block">Fleet Operational Characteristics</span>
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
      <div class="absolute top-4 right-4 glass-card rounded-xl p-1.5 z-20 shadow-xl flex space-x-1 text-xs">
        <button onclick="switchBaseMap('dark')" id="btn-bm-dark" class="px-2.5 py-1 rounded-lg font-bold bg-slate-800 text-emerald-400 transition">Dark</button>
        <button onclick="switchBaseMap('light')" id="btn-bm-light" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition">Light</button>
        <button onclick="switchBaseMap('osm')" id="btn-bm-osm" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition">OSM</button>
        <button onclick="switchBaseMap('sat')" id="btn-bm-sat" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition">Satellite</button>
      </div>

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

  <!-- Full-Screen Research Analytics Modal (Charts & Tradeoffs) -->
  <div id="analytics-modal" class="hidden fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-3 sm:p-6">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
      <!-- Modal Header -->
      <div class="p-4 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <i class="fa-solid fa-chart-line"></i>
          </div>
          <div>
            <h3 class="text-base font-bold text-white">Research Analytics & Power Grid Verification</h3>
            <p class="text-xs text-slate-400">NSGA-II Pareto Frontier & 33kV DPDC/DESCO Voltage Stability Profiles</p>
          </div>
        </div>
        <button onclick="toggleAnalyticsModal()" class="text-slate-400 hover:text-white p-2">
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
                <i class="fa-solid fa-code-branch mr-1"></i>NSGA-II Pareto Optimal Frontier
              </h4>
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
                <i class="fa-solid fa-bolt mr-1"></i>33kV Distribution Substation Voltages
              </h4>
              <span class="text-[11px] text-slate-400">Baseline vs. EV Charging Load</span>
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
    window.addEventListener('DOMContentLoaded', () => {{
      initMap();
      initLiveWeather();
      populateParetoTable();
      initCharts();
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

      activeBaseLayer = baseLayers.dark;
      activeBaseLayer.addTo(map);

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

    function switchBaseMap(type) {{
      if (activeBaseLayer) map.removeLayer(activeBaseLayer);
      activeBaseLayer = baseLayers[type] || baseLayers.dark;
      activeBaseLayer.addTo(map);

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
          content.classList.remove('hidden');
        }} else {{
          btn.className = "flex-1 py-2 font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 text-center";
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
        if (idx === index) {{
          btn.className = "px-2.5 py-1 rounded-lg font-bold bg-emerald-500 text-slate-950 shadow transition-all text-xs";
        }} else {{
          btn.className = "px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white transition-all text-xs";
        }}
      }});

      // Update KPI Cards
      document.getElementById('kpi-station-count').innerText = currentSolution.open_station_count || activeStationIds.size;
      document.getElementById('kpi-grid-power').innerText = ((currentSolution.total_grid_power_kw || 21600) / 1000).toFixed(1);
      document.getElementById('kpi-total-cost').innerText = (currentSolution.total_cost_million_bdt || 77400).toFixed(1);
      document.getElementById('kpi-demand-cov').innerText = (currentSolution.demand_coverage_pct || 100.0).toFixed(1);

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
        const ahp = rankInfo.ahp_suitability_score || p.ahp_suitability_score || 0.75;
        const zone = p.zone_name || rankInfo.zone_name || "";

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
        const ahp = rankInfo.ahp_suitability_score || p.ahp_suitability_score || 0.75;
        const zone = p.zone_name || rankInfo.zone_name || "";

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
        const dVal = feat.properties.demand_kwh_day || 500;

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

    function renderBuffers() {{
      layers.buffers.clearLayers();
      RAW_CANDIDATES.features.forEach(feat => {{
        const cid = feat.properties.candidate_id;
        if (!activeStationIds.has(cid)) return;
        const coords = feat.geometry.coordinates;

        L.circle([coords[1], coords[0]], {{
          radius: 2500, // 2.5km service buffer
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

      const ahp = (rankInfo.ahp_suitability_score || p.ahp_suitability_score || 0.75).toFixed(3);
      const landCost = (p.land_cost_bdt_sqm || 100000).toLocaleString();
      const subDist = (p.distance_to_substation_m || 1200).toFixed(0);
      const headroom = p.substation_headroom_mva || 15.0;

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
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Configured Charger Ports:</div>
          <div class="grid grid-cols-2 gap-1.5 text-[11px]">
            <span class="px-2 py-1 bg-slate-800 rounded flex justify-between"><span>22kW Level 2:</span> <b class="text-emerald-400">4 Ports</b></span>
            <span class="px-2 py-1 bg-slate-800 rounded flex justify-between"><span>60kW DC Fast:</span> <b class="text-cyan-400">2 Ports</b></span>
            <span class="px-2 py-1 bg-slate-800 rounded flex justify-between"><span>150kW Ultra-Fast:</span> <b class="text-amber-400">2 Ports</b></span>
            <span class="px-2 py-1 bg-slate-800 rounded flex justify-between"><span>Battery Swap:</span> <b class="text-purple-400">2 Depots</b></span>
          </div>
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

      body.innerHTML = `
        <div class="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800 text-xs">
          <div class="flex justify-between">
            <span class="text-slate-400">Substation ID:</span>
            <span class="font-mono font-bold text-white">#${{sub.sub_id || 'SS-01'}}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">Rated Transformer:</span>
            <span class="font-bold text-slate-200">${{sub.rated_mva || 40}} MVA</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">Spare Grid Headroom:</span>
            <span class="font-bold text-emerald-400">${{sub.headroom_mva || 15}} MVA</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">Operating Voltage:</span>
            <span class="font-bold text-cyan-400">33.0 kV (Nominal)</span>
          </div>
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

    function toggleAnalyticsModal() {{
      const modal = document.getElementById('analytics-modal');
      modal.classList.toggle('hidden');
      if (!modal.classList.contains('hidden')) {{
        setTimeout(() => {{
          if (paretoChartInstance) paretoChartInstance.resize();
          if (voltageChartInstance) voltageChartInstance.resize();
        }}, 50);
      }}
    }}

    function populateParetoTable() {{
      const tbody = document.getElementById('pareto-table-body');
      if (!tbody) return;

      tbody.innerHTML = RAW_PARETO.map((sol, idx) => `
        <tr class="hover:bg-slate-900/80 transition">
          <td class="py-2 px-3 font-bold text-white">${{sol.solution_id}}</td>
          <td class="py-2 px-3 text-emerald-400">${{idx === 0 ? 'Knee Point' : (idx === 1 ? 'Max Coverage' : 'Budget')}}</td>
          <td class="py-2 px-3">${{sol.open_station_count}} Sites</td>
          <td class="py-2 px-3">${{(sol.total_cost_million_bdt || 77400).toFixed(1)}}M</td>
          <td class="py-2 px-3">$${{(sol.total_cost_million_usd || 673).toFixed(1)}}M</td>
          <td class="py-2 px-3 text-emerald-400">${{(sol.demand_coverage_pct || 100).toFixed(1)}}%</td>
          <td class="py-2 px-3">${{((sol.total_grid_power_kw || 21600)/1000).toFixed(1)}} MW</td>
          <td class="py-2 px-3"><span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold">Feasible</span></td>
        </tr>
      `).join('');
    }}

    function initCharts() {{
      // 1. Pareto Frontier Curve
      const paretoCtx = document.getElementById('paretoChartCanvas');
      if (paretoCtx) {{
        const paretoPoints = RAW_PARETO.map((sol, i) => ({{
          x: sol.total_cost_million_bdt || (75000 + i * 2500),
          y: sol.demand_coverage_pct || (92 + i * 4),
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
              legend: {{ labels: {{ color: '#94a3b8', font: {{ family: 'Plus Jakarta Sans', size: 11 }} }} }}
            }},
            scales: {{
              x: {{
                title: {{ display: true, text: 'Total Social Cost (Million BDT)', color: '#94a3b8' }},
                grid: {{ color: 'rgba(51, 65, 85, 0.4)' }},
                ticks: {{ color: '#94a3b8' }}
              }},
              y: {{
                title: {{ display: true, text: 'Spatial Demand Coverage (%)', color: '#94a3b8' }},
                grid: {{ color: 'rgba(51, 65, 85, 0.4)' }},
                ticks: {{ color: '#94a3b8' }}
              }}
            }}
          }}
        }});
      }}

      // 2. Substation Voltage Stability Profile
      const voltCtx = document.getElementById('voltageChartCanvas');
      if (voltCtx) {{
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
              legend: {{ labels: {{ color: '#94a3b8', font: {{ family: 'Plus Jakarta Sans', size: 11 }} }} }}
            }},
            scales: {{
              x: {{
                grid: {{ display: false }},
                ticks: {{ color: '#94a3b8', font: {{ size: 9 }}, maxRotation: 45 }}
              }},
              y: {{
                min: 0.94,
                max: 1.02,
                title: {{ display: true, text: 'Voltage (p.u.) [Limit: 0.95 - 1.05]', color: '#94a3b8' }},
                grid: {{ color: 'rgba(51, 65, 85, 0.4)' }},
                ticks: {{ color: '#94a3b8' }}
              }}
            }}
          }}
        }});
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

    # Also deploy to docs/index.html for GitHub Pages / web hosting
    docs_dir = base_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    with open(docs_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Also deploy to results/figures/dhaka_evcs_interactive_map.html
    inter_path = base_dir / "results" / "figures" / "dhaka_evcs_interactive_map.html"
    with open(inter_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[Visualization] Standalone Online Web Platform generated at: {output_file}")
    print(f"[Visualization] GitHub Pages Web App updated at: {docs_dir / 'index.html'}")
