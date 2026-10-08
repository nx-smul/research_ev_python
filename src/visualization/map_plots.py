"""Static publication figures for spatial analysis results."""

import os
import numpy as np
import matplotlib.pyplot as plt


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
