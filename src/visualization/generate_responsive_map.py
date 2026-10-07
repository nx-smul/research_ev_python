"""Generate standalone responsive GIS web application for Dhaka EVCS optimization visualization."""

import json
import os
import pandas as pd
from pathlib import Path


def build_responsive_map_html(base_dir: Path, output_file: Path):
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    tables_dir = base_dir / "results" / "tables"

    # Read data
    with open(processed_dir / "candidate_sites_filtered.geojson", "r") as f:
        candidates_geo = json.load(f)

    with open(processed_dir / "demand_grid_100m.geojson", "r") as f:
        demand_geo = json.load(f)

    with open(raw_dir / "osm_dhaka_roads.geojson", "r") as f:
        roads_geo = json.load(f)

    with open(raw_dir / "rajuk_dap_landuse.geojson", "r") as f:
        landuse_geo = json.load(f)

    subs_df = pd.read_csv(raw_dir / "dpdc_desco_substations.csv")
    subs_data = subs_df.to_dict(orient="records")

    pareto_df = pd.read_csv(tables_dir / "optimal_solutions_pareto.csv")
    pareto_data = pareto_df.to_dict(orient="records")

    ranked_df = pd.read_csv(tables_dir / "candidate_sites.csv")
    ranked_map = {row["candidate_id"]: row for row in ranked_df.to_dict(orient="records")}

    # HTML template with embedded data
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dhaka EVCS Optimization Map</title>

  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Leaflet CSS & JS -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
  <!-- Leaflet Heat plugin -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.heat/0.2.0/leaflet-heat.js"></script>
  <!-- Font Awesome -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" />
  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">

  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          fontFamily: {{
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
          }},
          colors: {{
            brand: {{
              50: '#ecfdf5',
              100: '#d1fae5',
              500: '#10b981',
              600: '#059669',
              700: '#047857',
            }},
            grid: {{
              dpdc: '#2563eb',
              desco: '#7c3aed',
              evcs: '#ef4444',
            }}
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
      z-index: 10;
    }}
    .custom-scrollbar::-webkit-scrollbar {{
      width: 5px;
    }}
    .custom-scrollbar::-webkit-scrollbar-track {{
      background: rgba(0, 0, 0, 0.05);
    }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{
      background: rgba(100, 116, 139, 0.3);
      border-radius: 9999px;
    }}
    .pulse-marker {{
      animation: pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
    }}
    @keyframes pulse-ring {{
      0% {{ transform: scale(0.95); opacity: 0.9; }}
      50% {{ transform: scale(1.15); opacity: 0.5; }}
      100% {{ transform: scale(0.95); opacity: 0.9; }}
    }}
    .leaflet-popup-content-wrapper {{
      border-radius: 12px;
      padding: 0;
      overflow: hidden;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
    }}
    .leaflet-popup-content {{
      margin: 0;
      line-height: 1.5;
    }}
  </style>
</head>
<body class="bg-slate-900 text-slate-100 h-screen w-screen overflow-hidden flex flex-col antialiased select-none">

  <!-- Top Navigation Bar -->
  <header class="h-16 bg-slate-900/95 backdrop-blur border-b border-slate-800 flex items-center justify-between px-4 sm:px-6 z-30 shrink-0">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
        <i class="fa-solid fa-bolt text-slate-950 text-xl"></i>
      </div>
      <div>
        <h1 class="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
          Dhaka EVCS Optimization
          <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GIS & NSGA-II</span>
        </h1>
        <p class="text-xs text-slate-400 hidden sm:block">Spatial MCDM & Distribution Grid Co-Optimization (DPDC & DESCO)</p>
      </div>
    </div>

    <!-- Quick Controls -->
    <div class="flex items-center space-x-3">
      <!-- Solution Selector -->
      <div class="flex items-center bg-slate-800 border border-slate-700 rounded-lg p-1 text-xs">
        <span class="text-slate-400 px-2 font-medium hidden md:inline"><i class="fa-solid fa-code-branch mr-1 text-emerald-400"></i>Solution:</span>
        <button id="btn-sol-1" onclick="switchSolution('SOL-001')" class="px-2.5 py-1 rounded font-semibold bg-emerald-500 text-slate-950 shadow transition-all">
          Knee (SOL-001)
        </button>
        <button id="btn-sol-2" onclick="switchSolution('SOL-002')" class="px-2.5 py-1 rounded font-medium text-slate-300 hover:text-white transition-all">
          Max Cov (SOL-002)
        </button>
      </div>

      <!-- Mobile Sidebar Toggle -->
      <button onclick="toggleSidebar()" class="lg:hidden p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white">
        <i class="fa-solid fa-bars text-base"></i>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <div class="flex-1 flex relative overflow-hidden">

    <!-- Sidebar Controls -->
    <aside id="sidebar" class="w-80 sm:w-96 bg-slate-900/90 backdrop-blur border-r border-slate-800 flex flex-col shrink-0 z-20 transition-all duration-300 absolute lg:relative h-full -translate-x-full lg:translate-x-0 shadow-2xl lg:shadow-none">

      <!-- Scrollable Content -->
      <div class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">

        <!-- Live KPI Overview -->
        <div class="grid grid-cols-2 gap-2.5">
          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              Active EVCS
              <i class="fa-solid fa-charging-station text-red-400"></i>
            </div>
            <div class="mt-1 flex items-baseline gap-1">
              <span id="kpi-stations" class="text-2xl font-extrabold text-white">33</span>
              <span class="text-xs text-slate-500 font-medium">/ 58 sites</span>
            </div>
            <div class="text-[10px] text-emerald-400 font-medium mt-0.5">Optimal Knee Selection</div>
          </div>

          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              Grid Load
              <i class="fa-solid fa-plug-circle-bolt text-blue-400"></i>
            </div>
            <div class="mt-1 flex items-baseline gap-1">
              <span id="kpi-power" class="text-2xl font-extrabold text-white">21.6</span>
              <span class="text-xs text-slate-500 font-medium">MW</span>
            </div>
            <div class="text-[10px] text-blue-400 font-medium mt-0.5">AC Power Flow Feasible</div>
          </div>

          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              Total Capex/Opex
              <i class="fa-solid fa-coins text-amber-400"></i>
            </div>
            <div class="mt-1 flex items-baseline gap-1">
              <span id="kpi-cost" class="text-2xl font-extrabold text-white">77.4B</span>
              <span class="text-xs text-slate-500 font-medium">BDT</span>
            </div>
            <div class="text-[10px] text-amber-400 font-medium mt-0.5">~$673.1M USD (10 Yr)</div>
          </div>

          <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              Demand Cov.
              <i class="fa-solid fa-chart-pie text-emerald-400"></i>
            </div>
            <div class="mt-1 flex items-baseline gap-1">
              <span id="kpi-coverage" class="text-2xl font-extrabold text-emerald-400">100</span>
              <span class="text-xs text-slate-500 font-medium">%</span>
            </div>
            <div class="text-[10px] text-emerald-400 font-medium mt-0.5">116 Demand Zones</div>
          </div>
        </div>

        <!-- Layer Toggles -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3.5 space-y-2.5">
          <div class="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between pb-1 border-b border-slate-700/60">
            <span>Spatial Layers</span>
            <span class="text-[10px] text-slate-500 lowercase font-normal">toggle visibility</span>
          </div>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-red-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-plug text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">Optimal EVCS Stations</span>
            </div>
            <input type="checkbox" id="layer-optimal" checked onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-blue-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-bolt text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">33/11kV Substations (18)</span>
            </div>
            <input type="checkbox" id="layer-subs" checked onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-slate-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-location-dot text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">All Candidate Sites (58)</span>
            </div>
            <input type="checkbox" id="layer-all-candidates" onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-amber-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-fire text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">AHP Suitability Heatmap</span>
            </div>
            <input type="checkbox" id="layer-heatmap" onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-indigo-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-road text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">Major Road Corridors</span>
            </div>
            <input type="checkbox" id="layer-roads" checked onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-cyan-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-cubes text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">100m Demand Grid (116)</span>
            </div>
            <input type="checkbox" id="layer-demand" onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>

          <label class="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-slate-800 cursor-pointer transition">
            <div class="flex items-center space-x-2.5">
              <span class="w-3.5 h-3.5 rounded-full bg-pink-500 flex items-center justify-center text-[9px] text-white font-bold"><i class="fa-solid fa-city text-[8px]"></i></span>
              <span class="text-xs font-semibold text-slate-200">RAJUK Land-Use & Flood Zones</span>
            </div>
            <input type="checkbox" id="layer-landuse" onchange="updateLayers()" class="w-4 h-4 rounded text-emerald-500 focus:ring-0 bg-slate-800 border-slate-700 cursor-pointer" />
          </label>
        </div>

        <!-- Filter & Search -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3.5 space-y-3">
          <div class="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between pb-1 border-b border-slate-700/60">
            <span>Filter Stations</span>
            <i class="fa-solid fa-filter text-slate-500 text-xs"></i>
          </div>

          <!-- Search Input -->
          <div class="relative">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-slate-400"></i>
            <input type="text" id="search-input" onkeyup="applyFilters()" placeholder="Search zone, station, corridor..." class="w-full bg-slate-900/70 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500" />
          </div>

          <!-- Zone Select -->
          <div>
            <label class="text-[11px] font-medium text-slate-400 mb-1 block">City Zone</label>
            <select id="zone-select" onchange="applyFilters()" class="w-full bg-slate-900/70 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500">
              <option value="ALL">All Zones (Whole Dhaka)</option>
              <option value="Gulshan_Banani">Gulshan & Banani</option>
              <option value="Uttara">Uttara</option>
              <option value="Mirpur">Mirpur</option>
              <option value="Motijheel_Dilkusha">Motijheel & Kamalapur</option>
              <option value="Dhanmondi">Dhanmondi & Mohammadpur</option>
              <option value="Kawran_Bazar_Tejgaon">Tejgaon & Kawran Bazar</option>
              <option value="Badda_Mohakhali">Mohakhali & Badda</option>
              <option value="Old_Dhaka">Old Dhaka (Lalbagh/Sadarghat)</option>
              <option value="Jatrabari_Sayedabad">Jatrabari & Sayedabad</option>
              <option value="Purbachal_Suburbs">Purbachal 300ft Corridor</option>
            </select>
          </div>

          <!-- AHP Suitability Slider -->
          <div>
            <div class="flex justify-between text-[11px] font-medium text-slate-400 mb-1">
              <span>Min AHP Suitability</span>
              <span id="ahp-val-label" class="text-emerald-400 font-bold">0.00</span>
            </div>
            <input type="range" id="ahp-slider" min="0" max="1" step="0.05" value="0.0" oninput="updateAHPFilter(this.value)" class="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500">
          </div>
        </div>

        <!-- Charger Bay Configuration Breakdown -->
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-3.5 space-y-2.5">
          <div class="text-xs font-bold text-slate-300 uppercase tracking-wider pb-1 border-b border-slate-700/60">
            Knee Charger Allocation
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400 font-medium">Level 2 AC (22kW)</div>
              <div class="text-base font-bold text-emerald-400 mt-0.5">74 Bays</div>
              <div class="text-[9px] text-slate-500">E2W / Private 4W</div>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400 font-medium">DC Fast (60kW)</div>
              <div class="text-base font-bold text-cyan-400 mt-0.5">40 Bays</div>
              <div class="text-[9px] text-slate-500">Fleet Taxi / 4W</div>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400 font-medium">DC Ultra-Fast (150kW)</div>
              <div class="text-base font-bold text-amber-400 mt-0.5">64 Bays</div>
              <div class="text-[9px] text-slate-500">E-Bus / Highway Hubs</div>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400 font-medium">Battery Swap Depots</div>
              <div class="text-base font-bold text-purple-400 mt-0.5">80 Depots</div>
              <div class="text-[9px] text-slate-500">E3W EasyBike / E2W</div>
            </div>
          </div>
        </div>

      </div>

      <!-- Footer Info -->
      <div class="p-3 bg-slate-950/60 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between shrink-0">
        <span>CRS: WGS84 (EPSG:4326)</span>
        <span class="text-emerald-400 font-medium"><i class="fa-solid fa-check-double mr-1"></i>Optimized</span>
      </div>
    </aside>

    <!-- Map View -->
    <main class="flex-1 relative h-full">
      <div id="map"></div>

      <!-- Detail Inspector Card (Bottom-Right floating overlay) -->
      <div id="inspector-card" class="hidden absolute bottom-5 right-5 w-80 sm:w-96 bg-slate-900/95 backdrop-blur border border-slate-700/80 rounded-2xl shadow-2xl p-4 z-20 space-y-3 transition-all transform duration-200">
        <div class="flex items-start justify-between">
          <div class="flex items-center space-x-2.5">
            <div id="insp-icon" class="w-8 h-8 rounded-lg bg-red-500/20 text-red-400 flex items-center justify-center font-bold text-sm">
              <i class="fa-solid fa-plug"></i>
            </div>
            <div>
              <h4 id="insp-title" class="text-sm font-bold text-white leading-tight">Station Details</h4>
              <p id="insp-subtitle" class="text-[11px] text-slate-400">Zone Name</p>
            </div>
          </div>
          <button onclick="closeInspector()" class="text-slate-400 hover:text-white p-1">
            <i class="fa-solid fa-xmark text-sm"></i>
          </button>
        </div>

        <div id="insp-body" class="space-y-2 text-xs">
          <!-- Dynamic details injected here -->
        </div>
      </div>

      <!-- Map Base Toggle Floating Control -->
      <div class="absolute top-4 right-4 bg-slate-900/90 backdrop-blur border border-slate-700/80 rounded-xl p-1.5 z-20 shadow-lg flex space-x-1 text-xs">
        <button onclick="setBaseLayer('dark')" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">Dark</button>
        <button onclick="setBaseLayer('light')" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">Light</button>
        <button onclick="setBaseLayer('osm')" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">OSM</button>
        <button onclick="setBaseLayer('sat')" class="px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">Satellite</button>
      </div>

      <!-- Quick Reset View Button -->
      <button onclick="resetMapView()" class="absolute bottom-5 left-5 bg-slate-900/90 backdrop-blur border border-slate-700/80 rounded-xl px-3 py-2 z-20 shadow-lg text-xs font-semibold text-slate-200 hover:text-white hover:bg-slate-800 transition flex items-center gap-2">
        <i class="fa-solid fa-crosshairs text-emerald-400"></i>
        <span>Center Dhaka</span>
      </button>

    </main>
  </div>

  <!-- Injected Dataset Payload -->
  <script>
    const RAW_CANDIDATES = {json.dumps(candidates_geo)};
    const RAW_DEMAND = {json.dumps(demand_geo)};
    const RAW_ROADS = {json.dumps(roads_geo)};
    const RAW_LANDUSE = {json.dumps(landuse_geo)};
    const RAW_SUBSTATIONS = {json.dumps(subs_data)};
    const RAW_PARETO = {json.dumps(pareto_data)};
    const RANKED_CANDIDATES = {json.dumps(ranked_map)};

    // Current State
    let currentSolutionId = "SOL-001";
    let currentMinAHP = 0.0;
    let selectedZone = "ALL";
    let searchQuery = "";

    // Solution Sets
    const sol1Set = new Set(RAW_PARETO[0].selected_station_ids.split(";"));
    const sol2Set = RAW_PARETO.length > 1 ? new Set(RAW_PARETO[1].selected_station_ids.split(";")) : sol1Set;
    let activeStationIds = sol1Set;

    // Map & Layer Groups
    let map;
    let baseLayers = {{}};
    let currentBaseLayer;
    let optimalLayerGroup;
    let subsLayerGroup;
    let allCandidatesLayerGroup;
    let heatmapLayerGroup;
    let roadsLayerGroup;
    let demandLayerGroup;
    let landuseLayerGroup;

    // Initialize Map
    function initMap() {{
      map = L.map('map', {{
        center: [23.7800, 90.4000],
        zoom: 12,
        zoomControl: false,
        attributionControl: false
      }});

      L.control.zoom({{ position: 'topleft' }}).add_to(map);

      // Base Tile Providers
      baseLayers.dark = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        subdomains: 'abcd',
        maxZoom: 19
      }});
      baseLayers.light = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        subdomains: 'abcd',
        maxZoom: 19
      }});
      baseLayers.osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19
      }});
      baseLayers.sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        maxZoom: 18
      }});

      // Default Base: Dark Matter
      currentBaseLayer = baseLayers.dark;
      currentBaseLayer.addTo(map);

      // Layer Groups
      optimalLayerGroup = L.layerGroup().addTo(map);
      subsLayerGroup = L.layerGroup().addTo(map);
      roadsLayerGroup = L.layerGroup().addTo(map);
      allCandidatesLayerGroup = L.layerGroup();
      heatmapLayerGroup = L.layerGroup();
      demandLayerGroup = L.layerGroup();
      landuseLayerGroup = L.layerGroup();

      renderAllLayers();
    }}

    function setBaseLayer(type) {{
      if (currentBaseLayer) map.removeLayer(currentBaseLayer);
      currentBaseLayer = baseLayers[type] || baseLayers.dark;
      currentBaseLayer.addTo(map);
    }}

    function resetMapView() {{
      map.flyTo([23.7800, 90.4000], 12, {{ duration: 1.2 }});
    }}

    function toggleSidebar() {{
      const sb = document.getElementById('sidebar');
      sb.classList.toggle('-translate-x-full');
    }}

    function switchSolution(solId) {{
      currentSolutionId = solId;
      const b1 = document.getElementById('btn-sol-1');
      const b2 = document.getElementById('btn-sol-2');

      if (solId === "SOL-001") {{
        activeStationIds = sol1Set;
        b1.className = "px-2.5 py-1 rounded font-semibold bg-emerald-500 text-slate-950 shadow transition-all";
        b2.className = "px-2.5 py-1 rounded font-medium text-slate-300 hover:text-white transition-all";
        document.getElementById('kpi-stations').innerText = "33";
        document.getElementById('kpi-power').innerText = "21.6";
        document.getElementById('kpi-cost').innerText = "77.4B";
      }} else {{
        activeStationIds = sol2Set;
        b2.className = "px-2.5 py-1 rounded font-semibold bg-emerald-500 text-slate-950 shadow transition-all";
        b1.className = "px-2.5 py-1 rounded font-medium text-slate-300 hover:text-white transition-all";
        document.getElementById('kpi-stations').innerText = "34";
        document.getElementById('kpi-power').innerText = "21.7";
        document.getElementById('kpi-cost').innerText = "77.4B";
      }}

      renderOptimalStations();
      renderAllCandidates();
    }}

    function renderAllLayers() {{
      renderSubstations();
      renderOptimalStations();
      renderAllCandidates();
      renderHeatmap();
      renderRoads();
      renderDemandGrid();
      renderLanduse();
    }}

    function renderSubstations() {{
      subsLayerGroup.clearLayers();
      RAW_SUBSTATIONS.forEach(sub => {{
        const isDPDC = sub.utility === 'DPDC';
        const color = isDPDC ? '#3b82f6' : '#8b5cf6';

        const customIcon = L.divIcon({{
          className: 'custom-sub-icon',
          html: `
            <div style="background-color: ${{color}};" class="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs shadow-lg border-2 border-slate-900 transform -translate-x-1/2 -translate-y-1/2">
              <i class="fa-solid fa-bolt"></i>
            </div>
          `,
          iconSize: [28, 28]
        }});

        const marker = L.marker([sub.lat, sub.lon], {{ icon: customIcon }});

        marker.on('click', () => {{
          showSubstationInspector(sub);
        }});

        marker.bindTooltip(`<b>${{sub.name}}</b><br><span style="color:${{color}}">${{sub.utility}}</span> · Headroom: ${{sub.headroom_mva}} MVA`, {{
          direction: 'top',
          className: 'bg-slate-900 text-white text-xs border border-slate-700 rounded-lg px-2 py-1'
        }});

        marker.addTo(subsLayerGroup);
      }});
    }}

    function renderOptimalStations() {{
      optimalLayerGroup.clearLayers();
      RAW_CANDIDATES.features.forEach(feat => {{
        const cid = feat.properties.candidate_id;
        if (!activeStationIds.has(cid)) return;

        // Apply filters
        const p = feat.properties;
        const rankInfo = RANKED_CANDIDATES[cid] || {{}};
        const ahp = rankInfo.ahp_suitability_score || p.ahp_suitability_score || 0.75;
        const zone = p.zone_name || rankInfo.zone_name || "";

        if (ahp < currentMinAHP) return;
        if (selectedZone !== "ALL" && zone !== selectedZone) return;
        if (searchQuery && !p.site_name.toLowerCase().includes(searchQuery) && !zone.toLowerCase().includes(searchQuery)) return;

        const coords = feat.geometry.coordinates; // [lon, lat]

        const customIcon = L.divIcon({{
          className: 'custom-cs-icon',
          html: `
            <div class="relative flex items-center justify-center transform -translate-x-1/2 -translate-y-1/2">
              <div class="absolute w-8 h-8 rounded-full bg-red-500/30 pulse-marker"></div>
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
        marker.addTo(optimalLayerGroup);
      }});
    }}

    function renderAllCandidates() {{
      allCandidatesLayerGroup.clearLayers();
      RAW_CANDIDATES.features.forEach(feat => {{
        const cid = feat.properties.candidate_id;
        const isOptimal = activeStationIds.has(cid);
        const p = feat.properties;
        const rankInfo = RANKED_CANDIDATES[cid] || {{}};
        const ahp = rankInfo.ahp_suitability_score || p.ahp_suitability_score || 0.75;
        const zone = p.zone_name || rankInfo.zone_name || "";

        if (ahp < currentMinAHP) return;
        if (selectedZone !== "ALL" && zone !== selectedZone) return;
        if (searchQuery && !p.site_name.toLowerCase().includes(searchQuery) && !zone.toLowerCase().includes(searchQuery)) return;

        const coords = feat.geometry.coordinates;
        const marker = L.circleMarker([coords[1], coords[0]], {{
          radius: isOptimal ? 6 : 5,
          fillColor: isOptimal ? '#ef4444' : '#64748b',
          color: '#ffffff',
          weight: 1.5,
          opacity: 0.9,
          fillOpacity: 0.8
        }});

        marker.on('click', () => showStationInspector(p, rankInfo, isOptimal));
        marker.bindTooltip(`<b>${{p.site_name}}</b> (CID: ${{cid}})<br>AHP Score: ${{ahp.toFixed(3)}}`, {{
          direction: 'top',
          className: 'bg-slate-900 text-white text-xs border border-slate-700 rounded-lg px-2 py-1'
        }});
        marker.addTo(allCandidatesLayerGroup);
      }});
    }}

    function renderHeatmap() {{
      heatmapLayerGroup.clearLayers();
      const heatPoints = RAW_CANDIDATES.features.map(f => {{
        const c = f.geometry.coordinates;
        const p = f.properties;
        const ahp = p.ahp_suitability_score || 0.75;
        return [c[1], c[0], ahp];
      }});

      const heat = L.heatLayer(heatPoints, {{
        radius: 35,
        blur: 20,
        maxZoom: 13,
        gradient: {{ 0.2: '#3b82f6', 0.5: '#10b981', 0.8: '#f59e0b', 1.0: '#ef4444' }}
      }});
      heat.addTo(heatmapLayerGroup);
    }}

    function renderRoads() {{
      roadsLayerGroup.clearLayers();
      L.geoJSON(RAW_ROADS, {{
        style: function(feat) {{
          const pcu = feat.properties.pcu_per_hr || 3000;
          const color = pcu > 4500 ? '#ef4444' : pcu > 3500 ? '#f59e0b' : '#3b82f6';
          return {{
            color: color,
            weight: 3.5,
            opacity: 0.75,
            dashArray: feat.properties.highway === 'motorway' ? null : '6, 6'
          }};
        }},
        onEachFeature: function(feat, layer) {{
          const p = feat.properties;
          layer.bindTooltip(`<b>${{p.u}} to ${{p.v}}</b><br>Speed: ${{p.maxspeed}} km/h · PCU: ${{p.pcu_per_hr}}/hr`, {{
            sticky: true,
            className: 'bg-slate-900 text-white text-xs border border-slate-700 rounded-lg px-2 py-1'
          }});
          layer.on('click', () => showRoadInspector(p));
        }}
      }}).addTo(roadsLayerGroup);
    }}

    function renderDemandGrid() {{
      demandLayerGroup.clearLayers();
      RAW_DEMAND.features.forEach(f => {{
        const c = f.geometry.coordinates;
        const p = f.properties;
        const kwh = p.daily_demand_kwh;
        const radius = Math.max(3, Math.min(8, kwh / 300));

        const cm = L.circleMarker([c[1], c[0]], {{
          radius: radius,
          fillColor: '#06b6d4',
          color: '#0891b2',
          weight: 1,
          opacity: 0.7,
          fillOpacity: 0.5
        }});

        cm.bindTooltip(`<b>${{p.demand_id}}</b> (${{p.zone_name}})<br>Demand: <b>${{kwh}} kWh/day</b>`, {{
          direction: 'top',
          className: 'bg-slate-900 text-white text-xs border border-slate-700 rounded-lg px-2 py-1'
        }});

        cm.addTo(demandLayerGroup);
      }});
    }}

    function renderLanduse() {{
      landuseLayerGroup.clearLayers();
      L.geoJSON(RAW_LANDUSE, {{
        style: function(feat) {{
          const z = feat.properties.zone_type;
          let color = '#94a3b8';
          let fillOp = 0.15;
          if (z === 'Waterbody') {{ color = '#0284c7'; fillOp = 0.4; }}
          else if (z === 'Flood_Hazard') {{ color = '#f43f5e'; fillOp = 0.3; }}
          else if (z === 'Commercial') {{ color = '#eab308'; fillOp = 0.2; }}
          else if (z === 'Industrial') {{ color = '#8b5cf6'; fillOp = 0.2; }}
          else if (z === 'Residential') {{ color = '#10b981'; fillOp = 0.2; }}

          return {{
            color: color,
            fillColor: color,
            weight: 1.5,
            fillOpacity: fillOp
          }};
        }},
        onEachFeature: function(feat, layer) {{
          const p = feat.properties;
          layer.bindTooltip(`<b>RAJUK Zone: ${{p.zone_type}}</b><br>Land Price: BDT ${{Number(p.land_price_bdt_sqm).toLocaleString()}}/m²`, {{
            sticky: true,
            className: 'bg-slate-900 text-white text-xs border border-slate-700 rounded-lg px-2 py-1'
          }});
        }}
      }}).addTo(landuseLayerGroup);
    }}

    // Layer Toggle Handlers
    function updateLayers() {{
      document.getElementById('layer-optimal').checked ? map.addLayer(optimalLayerGroup) : map.removeLayer(optimalLayerGroup);
      document.getElementById('layer-subs').checked ? map.addLayer(subsLayerGroup) : map.removeLayer(subsLayerGroup);
      document.getElementById('layer-all-candidates').checked ? map.addLayer(allCandidatesLayerGroup) : map.removeLayer(allCandidatesLayerGroup);
      document.getElementById('layer-heatmap').checked ? map.addLayer(heatmapLayerGroup) : map.removeLayer(heatmapLayerGroup);
      document.getElementById('layer-roads').checked ? map.addLayer(roadsLayerGroup) : map.removeLayer(roadsLayerGroup);
      document.getElementById('layer-demand').checked ? map.addLayer(demandLayerGroup) : map.removeLayer(demandLayerGroup);
      document.getElementById('layer-landuse').checked ? map.addLayer(landuseLayerGroup) : map.removeLayer(landuseLayerGroup);
    }}

    function updateAHPFilter(val) {{
      currentMinAHP = parseFloat(val);
      document.getElementById('ahp-val-label').innerText = currentMinAHP.toFixed(2);
      renderOptimalStations();
      renderAllCandidates();
    }}

    function applyFilters() {{
      selectedZone = document.getElementById('zone-select').value;
      searchQuery = document.getElementById('search-input').value.toLowerCase().trim();
      renderOptimalStations();
      renderAllCandidates();
    }}

    // Inspector Overlay
    function closeInspector() {{
      document.getElementById('inspector-card').classList.add('hidden');
    }}

    function showStationInspector(p, rankInfo, isOptimal) {{
      const card = document.getElementById('inspector-card');
      const icon = document.getElementById('insp-icon');
      const title = document.getElementById('insp-title');
      const sub = document.getElementById('insp-subtitle');
      const body = document.getElementById('insp-body');

      icon.className = isOptimal
        ? "w-8 h-8 rounded-lg bg-red-500/20 text-red-400 flex items-center justify-center font-bold text-sm"
        : "w-8 h-8 rounded-lg bg-slate-700 text-slate-300 flex items-center justify-center font-bold text-sm";
      icon.innerHTML = '<i class="fa-solid fa-charging-station"></i>';

      title.innerText = p.site_name || "EV Charging Station";
      sub.innerText = `Candidate ID: ${{p.candidate_id}} · Zone: ${{p.zone_name || rankInfo.zone_name || 'Dhaka'}}`;

      const ahp = (rankInfo.ahp_suitability_score || p.ahp_suitability_score || 0.75).toFixed(3);
      const rank = rankInfo.topsis_rank || 'N/A';
      const landCost = Number(p.land_cost_bdt_sqm || rankInfo.land_cost_bdt_sqm || 0).toLocaleString();
      const subDist = Number(p.distance_to_substation_m || rankInfo.distance_to_substation_m || 0).toFixed(0);
      const headroom = p.substation_headroom_mva || rankInfo.substation_headroom_mva || 10.0;

      body.innerHTML = `
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/80 border border-slate-700">
          <span class="text-slate-400">Optimization Status:</span>
          <span class="font-bold ${{isOptimal ? 'text-red-400' : 'text-slate-400'}}">
            ${{isOptimal ? '★ SELECTED (NSGA-II Knee)' : 'Candidate (Unselected)'}}
          </span>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">AHP Score / TOPSIS</span>
            <div class="text-sm font-bold text-emerald-400">${{ahp}} <span class="text-[10px] text-slate-400">(Rank #${{rank}})</span></div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Land Valuation</span>
            <div class="text-sm font-bold text-white">BDT ${{landCost}} <span class="text-[10px] text-slate-400">/m²</span></div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Substation Distance</span>
            <div class="text-sm font-bold text-blue-400">${{subDist}} m</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Available Headroom</span>
            <div class="text-sm font-bold text-teal-400">${{headroom}} MVA</div>
          </div>
        </div>
        <div class="p-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-[11px] space-y-1">
          <div class="text-slate-400 font-semibold">Configured Fleet Services:</div>
          <div class="flex flex-wrap gap-1 text-[10px]">
            <span class="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Level 2 AC 22kW</span>
            <span class="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">DC Fast 60kW</span>
            <span class="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">Ultra 150kW</span>
            <span class="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Swap Depot</span>
          </div>
        </div>
      `;

      card.classList.remove('hidden');
    }}

    function showSubstationInspector(sub) {{
      const card = document.getElementById('inspector-card');
      const icon = document.getElementById('insp-icon');
      const title = document.getElementById('insp-title');
      const subtitle = document.getElementById('insp-subtitle');
      const body = document.getElementById('insp-body');

      const isDPDC = sub.utility === 'DPDC';
      const color = isDPDC ? 'text-blue-400' : 'text-purple-400';
      const bg = isDPDC ? 'bg-blue-500/20' : 'bg-purple-500/20';

      icon.className = `w-8 h-8 rounded-lg ${{bg}} ${{color}} flex items-center justify-center font-bold text-sm`;
      icon.innerHTML = '<i class="fa-solid fa-bolt"></i>';

      title.innerText = sub.name;
      subtitle.innerText = `Substation ID: ${{sub.sub_id}} · Utility: ${{sub.utility}}`;

      body.innerHTML = `
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Rated Capacity</span>
            <div class="text-sm font-bold text-white">${{sub.rated_mva}} MVA</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Base Grid Load</span>
            <div class="text-sm font-bold text-slate-300">${{sub.base_load_mva}} MVA</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Available Headroom</span>
            <div class="text-sm font-bold text-emerald-400">${{sub.headroom_mva}} MVA</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Spare Capacity %</span>
            <div class="text-sm font-bold text-teal-400">${{sub.headroom_pct}}%</div>
          </div>
        </div>
        <div class="p-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-[11px] text-slate-400">
          <b>Voltage Level:</b> ${{sub.voltage_kv}} kV / 11 kV<br>
          <b>Location:</b> Lon ${{sub.lon.toFixed(4)}}°, Lat ${{sub.lat.toFixed(4)}}°<br>
          <b>Zone:</b> ${{sub.zone}}
        </div>
      `;

      card.classList.remove('hidden');
    }}

    function showRoadInspector(p) {{
      const card = document.getElementById('inspector-card');
      const icon = document.getElementById('insp-icon');
      const title = document.getElementById('insp-title');
      const subtitle = document.getElementById('insp-subtitle');
      const body = document.getElementById('insp-body');

      icon.className = "w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-sm";
      icon.innerHTML = '<i class="fa-solid fa-road"></i>';

      title.innerText = `${{p.u}} ➔ ${{p.v}}`;
      subtitle.innerText = `Corridor Type: ${{p.highway}} (${{p.lanes}} Lanes)`;

      body.innerHTML = `
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Length</span>
            <div class="text-sm font-bold text-white">${{(p.length_m / 1000).toFixed(2)}} km</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Speed Limit</span>
            <div class="text-sm font-bold text-slate-300">${{p.maxspeed}} km/h</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">Peak Traffic Volume</span>
            <div class="text-sm font-bold text-amber-400">${{p.pcu_per_hr}} PCU/hr</div>
          </div>
          <div class="bg-slate-800/60 p-2 rounded-lg border border-slate-700/60">
            <span class="text-[10px] text-slate-400">BPR Congestion Factor</span>
            <div class="text-sm font-bold text-red-400">${{p.congestion_factor}}x</div>
          </div>
        </div>
      `;

      card.classList.remove('hidden');
    }}

    window.onload = initMap;
  </script>
</body>
</html>
"""

    os.makedirs(output_file.parent, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Responsive map successfully written to: {output_file}")


if __name__ == "__main__":
    base_dir = Path("/home/simp/research")
    output_path = base_dir / "results" / "figures" / "dhaka_evcs_responsive_map.html"
    build_responsive_map_html(base_dir, output_path)
