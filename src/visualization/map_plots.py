"""Spatial visualization: Matplotlib publication figures and interactive Folium GIS maps."""

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import folium
from folium.plugins import MarkerCluster, HeatMap


def plot_ahp_suitability_map(candidate_gdf, landuse_gdf, output_fig_path):
    """Plot publication-quality AHP Spatial Suitability Heatmap across Dhaka."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 12))

    # Plot Landuse Base Polygons
    if landuse_gdf is not None and not landuse_gdf.empty:
        # Background zones
        landuse_gdf[landuse_gdf["zone_type"] != "Waterbody"].plot(
            ax=ax, color="#f5f5f2", edgecolor="#d0d0d0", linewidth=0.8, alpha=0.9
        )
        # Waterbodies / Wetlands
        water = landuse_gdf[landuse_gdf["zone_type"] == "Waterbody"]
        if not water.empty:
            water.plot(ax=ax, color="#b3cde3", edgecolor="#88a8c4", linewidth=1.0, label="Waterbodies (Buriganga/Hatirjheel)")
        # Flood prone areas
        flood = landuse_gdf[landuse_gdf["zone_type"] == "Flood_Hazard"]
        if not flood.empty:
            flood.plot(ax=ax, color="#fbb4ae", edgecolor="#e78ac3", alpha=0.4, linewidth=1.0, label="Flood Inundation Hazard")

    # Plot candidate points colored by AHP score
    scores = candidate_gdf["ahp_suitability_score"].to_numpy()
    scatter = ax.scatter(
        candidate_gdf.geometry.x,
        candidate_gdf.geometry.y,
        c=scores,
        cmap="viridis",
        s=120,
        edgecolors="black",
        linewidths=0.8,
        zorder=5,
        alpha=0.9
    )

    cbar = plt.colorbar(scatter, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("AHP Spatial Suitability Index S(x, y)", fontsize=11, fontweight="bold")

    ax.set_title("Dhaka Metropolitan Area: EVCS Spatial Suitability Map (GIS-AHP)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Longitude (°E)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Latitude (°N)", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)

    # Annotate top anchor zones
    anchors_to_label = ["Gulshan_1", "Motijheel_CBD", "Uttara_Sec3", "Mirpur_10_Circle", "Mohakhali_Terminal"]
    for idx, row in candidate_gdf.iterrows():
        sname = str(row.get("site_name", ""))
        for a in anchors_to_label:
            if a in sname and "Site_1" in sname:
                ax.annotate(
                    a.replace("_", " "),
                    xy=(row.geometry.x, row.geometry.y),
                    xytext=(6, 6),
                    textcoords="offset points",
                    fontsize=8.5,
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.6, ec="none")
                )

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_fig_path), exist_ok=True)
    plt.savefig(output_fig_path, dpi=300)
    plt.close()
    print(f"[Visualization] AHP Suitability map saved to: {output_fig_path}")


def plot_optimal_cs_locations(candidate_gdf, selected_station_ids, substations_df, output_fig_path):
    """Plot optimal placed EV Charging Stations vs. Substations."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 12))

    # All candidate sites (unselected)
    unselected = candidate_gdf[~candidate_gdf["candidate_id"].isin(selected_station_ids)]
    ax.scatter(
        unselected.geometry.x, unselected.geometry.y,
        color="#b0b0b0", s=60, alpha=0.6, edgecolors="gray", label="Candidate Sites (Unselected)", zorder=3
    )

    # Selected optimal stations
    selected = candidate_gdf[candidate_gdf["candidate_id"].isin(selected_station_ids)]
    ax.scatter(
        selected.geometry.x, selected.geometry.y,
        color="#e41a1c", s=160, marker="^", edgecolors="black", linewidths=1.2, label=f"Selected EVCS ({len(selected)} Sites)", zorder=6
    )

    # Substations
    if substations_df is not None and not substations_df.empty:
        ax.scatter(
            substations_df["lon"], substations_df["lat"],
            color="#377eb8", s=110, marker="s", edgecolors="black", linewidths=1.0, label="33/11kV Substations (DPDC & DESCO)", zorder=4
        )

    ax.set_title("Optimal Spatial Placement of EV Charging Stations in Dhaka", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Longitude (°E)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Latitude (°N)", fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", frameon=True, fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_fig_path), exist_ok=True)
    plt.savefig(output_fig_path, dpi=300)
    plt.close()
    print(f"[Visualization] Optimal EVCS locations map saved to: {output_fig_path}")


def generate_interactive_folium_map(candidate_gdf, selected_station_ids, substations_df, output_html_path):
    """Generate an interactive Folium web map with layer controls, popups, and clusters."""
    # Center map on Dhaka City (23.78°N, 90.40°E)
    m = folium.Map(location=[23.7800, 90.4000], zoom_start=12, tiles="OpenStreetMap")

    # Layer 1: Substations
    sub_fg = folium.FeatureGroup(name="DPDC & DESCO 33/11kV Substations")
    if substations_df is not None and not substations_df.empty:
        for _, row in substations_df.iterrows():
            sub_id = row.get("sub_id", "")
            s_name = row.get("name", "")
            utility = row.get("utility", "")
            rated_mva = row.get("rated_mva", 40.0)
            headroom_mva = row.get("headroom_mva", 10.0)

            popup_html = f"""
            <div style='font-family: sans-serif; min-width: 180px;'>
                <h4 style='margin-bottom: 4px; color: #1f77b4;'>⚡ {s_name}</h4>
                <b>Utility:</b> {utility}<br>
                <b>Rated Capacity:</b> {rated_mva} MVA<br>
                <b>Available Headroom:</b> <span style='color: green; font-weight: bold;'>{headroom_mva} MVA</span><br>
            </div>
            """
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"Substation: {s_name}",
                icon=folium.Icon(color="blue", icon="bolt", prefix="fa")
            ).add_to(sub_fg)
    sub_fg.add_to(m)

    # Layer 2: Selected EV Charging Stations
    selected_fg = folium.FeatureGroup(name="Optimal EV Charging Stations (EVCS)")
    selected_set = set(selected_station_ids)

    for _, row in candidate_gdf.iterrows():
        cid = row.get("candidate_id", "")
        is_selected = cid in selected_set
        if not is_selected:
            continue

        sname = row.get("site_name", cid)
        zname = row.get("zone_name", "")
        ahp_score = row.get("ahp_suitability_score", 0.75)
        land_cost = row.get("land_cost_bdt_sqm", 100000.0)
        sub_dist = row.get("distance_to_substation_m", 1200.0)

        popup_html = f"""
        <div style='font-family: sans-serif; min-width: 220px;'>
            <h4 style='margin-bottom: 4px; color: #d9534f;'>🔋 EVCS: {sname}</h4>
            <b>Candidate ID:</b> {cid}<br>
            <b>Zone:</b> {zname}<br>
            <b>AHP Suitability Score:</b> {ahp_score:.3f}<br>
            <b>Land Valuation:</b> BDT {land_cost:,.0f}/m²<br>
            <b>Nearest Substation Dist:</b> {sub_dist:.0f} m<br>
            <b>Configured Bays:</b> Level 2 AC, DC Fast 60kW, Ultra-Fast 150kW, Battery Swap<br>
        </div>
        """
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"Selected EVCS: {sname}",
            icon=folium.Icon(color="red", icon="plug", prefix="fa")
        ).add_to(selected_fg)

    selected_fg.add_to(m)

    # Layer 3: AHP Candidate HeatMap
    heat_data = [[row.geometry.y, row.geometry.x, float(row.get("ahp_suitability_score", 0.5))] for _, row in candidate_gdf.iterrows()]
    heat_fg = folium.FeatureGroup(name="AHP Suitability Intensity Heatmap")
    HeatMap(heat_data, radius=25, blur=15, max_zoom=13).add_to(heat_fg)
    heat_fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
    m.save(output_html_path)
    print(f"[Visualization] Interactive Folium map saved to: {output_html_path}")
