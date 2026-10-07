"""Pareto optimal trade-off visualization, hypervolume indicator, and knee-point solution selector."""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def find_knee_point_solution(pareto_df):
    """Find the compromise / knee-point solution on the 2D Pareto frontier using maximum distance to secant line."""
    if len(pareto_df) <= 2:
        return 0, pareto_df.iloc[0]

    costs = pareto_df["total_cost_bdt"].to_numpy()
    coverages = pareto_df["demand_coverage_score"].to_numpy()

    # Min-max normalization
    c_norm = (costs - np.min(costs)) / (np.max(costs) - np.min(costs) + 1e-9)
    cov_norm = (coverages - np.min(coverages)) / (np.max(coverages) - np.min(coverages) + 1e-9)

    # Inverted cost so that both are 'higher is better' in normalized space: (1 - c_norm, cov_norm)
    # Secant line between first and last point
    p1 = np.array([1 - c_norm[0], cov_norm[0]])
    p2 = np.array([1 - c_norm[-1], cov_norm[-1]])

    # Distance of each point to secant line
    distances = []
    line_vec = p2 - p1
    line_len = np.linalg.norm(line_vec)
    if line_len == 0:
        return 0, pareto_df.iloc[0]

    for i in range(len(pareto_df)):
        p = np.array([1 - c_norm[i], cov_norm[i]])
        cross_2d = line_vec[0] * (p1[1] - p[1]) - line_vec[1] * (p1[0] - p[0])
        d = np.abs(cross_2d) / line_len
        distances.append(d)

    knee_idx = int(np.argmax(distances))
    return knee_idx, pareto_df.iloc[knee_idx]


def calculate_hypervolume_indicator(costs, coverages, ref_cost=None, ref_coverage=0.0):
    """Calculate 2D Hypervolume indicator for the Pareto frontier."""
    if len(costs) == 0:
        return 0.0

    r_cost = ref_cost or np.max(costs) * 1.15
    sorted_indices = np.argsort(costs)
    s_costs = costs[sorted_indices]
    s_covs = coverages[sorted_indices]

    hv = 0.0
    cur_cov = ref_coverage
    for i in range(len(s_costs) - 1, -1, -1):
        if s_covs[i] > cur_cov:
            width = r_cost - s_costs[i]
            height = s_covs[i] - cur_cov
            hv += width * height
            cur_cov = s_covs[i]

    return float(hv)


def plot_pareto_front_2d(pareto_df, output_fig_path):
    """Generate publication-ready 2D Pareto Front trade-off curve ($F_1$ Cost vs $F_2$ Coverage)."""
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 6.5))

    costs_m_bdt = pareto_df["total_cost_bdt"].to_numpy() / 1e6
    coverage_pct = pareto_df["demand_coverage_pct"].to_numpy()
    station_counts = pareto_df["open_station_count"].to_numpy()

    # Plot Pareto curve line
    ax.plot(costs_m_bdt, coverage_pct, color="#2b5c8f", linestyle="-", linewidth=2.0, alpha=0.8, zorder=3)

    # Scatter points colored by number of open stations
    scatter = ax.scatter(
        costs_m_bdt, coverage_pct,
        c=station_counts, cmap="plasma", s=130, edgecolors="black", linewidths=1.0, zorder=5
    )

    cbar = plt.colorbar(scatter, ax=ax, pad=0.03)
    cbar.set_label("Number of Deployed EVCS Sites", fontsize=11, fontweight="bold")

    # Highlight Knee-point / Compromise Solution
    knee_idx, knee_row = find_knee_point_solution(pareto_df)
    knee_cost = knee_row["total_cost_bdt"] / 1e6
    knee_cov = knee_row["demand_coverage_pct"]

    ax.scatter(
        knee_cost, knee_cov,
        color="#e41a1c", s=280, marker="*", edgecolors="black", linewidths=1.5, zorder=7,
        label=f"Knee-Point Compromise ({knee_row['solution_id']}: {knee_cov:.1f}% @ BDT {knee_cost:.1f}M)"
    )

    ax.set_title("Pareto-Optimal Trade-off: Life-Cycle System Cost vs. Spatial Demand Coverage", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Total System & User Social Cost ($F_1$, Million BDT)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Spatial & Demand Catchment Coverage ($F_2$, %)", fontsize=11, fontweight="bold")
    ax.legend(loc="lower right", frameon=True, fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_fig_path), exist_ok=True)
    plt.savefig(output_fig_path, dpi=300)
    plt.close()
    print(f"[Visualization] Pareto trade-off figure saved to: {output_fig_path}")
