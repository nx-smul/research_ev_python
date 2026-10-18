"""AHP weight sensitivity analysis for site rankings."""

from pathlib import Path
import numpy as np
import pandas as pd


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def compute_site_scores(candidates, weights, config):
    """Compute AHP scores with given weights."""
    n = len(candidates)
    scores = np.zeros(n)

    for i, candidate in enumerate(candidates):
        # Normalize attributes
        land_cost = candidate.get("land_cost_bdt_sqm", 100000)
        sub_dist = candidate.get("distance_to_substation_m", 5000)
        traffic = candidate.get("traffic_density_score", 0.5)
        poi = candidate.get("poi_score", 0.5)
        parking = candidate.get("parking_score", 0.5)
        headroom = candidate.get("substation_headroom_mva", 10)

        # Normalize (min-max style within this dataset)
        land_norm = 1.0 - min(land_cost / 250000.0, 1.0)
        dist_norm = 1.0 - min(sub_dist / 5000.0, 1.0)

        # Weighted sum
        score = (
            weights["traffic"] * traffic +
            weights["poi"] * poi +
            weights["parking"] * parking +
            weights["proximity_to_substation"] * dist_norm +
            weights["grid_headroom"] * min(headroom / 20.0, 1.0) +
            weights["land_cost"] * land_norm
        )
        scores[i] = score

    return scores


def write_ahp_weight_sensitivity(path, candidates, config, settings):
    """Test how site rankings change under different AHP weight scenarios."""
    base_weights = config.get("spatial", {}).get("ahp_weights", {
        "traffic": 0.20,
        "poi": 0.15,
        "parking": 0.15,
        "proximity_to_substation": 0.20,
        "grid_headroom": 0.15,
        "land_cost": 0.15,
    })

    # Define alternative weight scenarios
    weight_scenarios = {
        "base": base_weights,
        "traffic_focused": {
            "traffic": 0.35,
            "poi": 0.10,
            "parking": 0.10,
            "proximity_to_substation": 0.15,
            "grid_headroom": 0.15,
            "land_cost": 0.15,
        },
        "cost_focused": {
            "traffic": 0.10,
            "poi": 0.10,
            "parking": 0.10,
            "proximity_to_substation": 0.20,
            "grid_headroom": 0.20,
            "land_cost": 0.30,
        },
        "grid_focused": {
            "traffic": 0.15,
            "poi": 0.10,
            "parking": 0.10,
            "proximity_to_substation": 0.25,
            "grid_headroom": 0.30,
            "land_cost": 0.10,
        },
    }

    # Compute scores for each scenario
    all_scores = {}
    for scenario_name, weights in weight_scenarios.items():
        scores = compute_site_scores(candidates, weights, config)
        all_scores[scenario_name] = scores

    # Rank sites for each scenario
    n_candidates = len(candidates)
    rankings = {}
    for scenario_name, scores in all_scores.items():
        # Get indices sorted by score descending
        ranked_indices = np.argsort(-scores)
        # Assign ranks (1 = best)
        ranks = np.zeros(n_candidates, dtype=int)
        for rank, idx in enumerate(ranked_indices):
            ranks[idx] = rank + 1
        rankings[scenario_name] = ranks

    # Create comparison table
    rows = []
    for i, candidate in enumerate(candidates):
        cid = candidate.get("candidate_id", str(i))

        # Get ranks across scenarios
        scenario_ranks = {name: rankings[name][i] for name in weight_scenarios.keys()}

        # Calculate rank stability (std of ranks across scenarios)
        rank_stability = np.std(list(scenario_ranks.values()))

        rows.append({
            "candidate_id": cid,
            "site_name": candidate.get("site_name", ""),
            "base_rank": scenario_ranks["base"],
            "traffic_focused_rank": scenario_ranks["traffic_focused"],
            "cost_focused_rank": scenario_ranks["cost_focused"],
            "grid_focused_rank": scenario_ranks["grid_focused"],
            "rank_stability_std": round(rank_stability, 2),
            "stability_category": "robust" if rank_stability < 3 else "sensitive" if rank_stability < 7 else "very_sensitive",
        })

    frame = pd.DataFrame(rows)
    write_csv(frame, path)

    # Identify robust vs sensitive sites
    robust_sites = frame[frame["stability_category"] == "robust"]["candidate_id"].tolist()
    sensitive_sites = frame[frame["stability_category"] == "sensitive"]["candidate_id"].tolist()
    very_sensitive_sites = frame[frame["stability_category"] == "very_sensitive"]["candidate_id"].tolist()

    # Top 10 comparison
    top_10_comparison = {}
    for scenario_name in weight_scenarios.keys():
        rank_col = "base_rank" if scenario_name == "base" else f"{scenario_name}_rank"
        top_10_comparison[scenario_name] = frame.nsmallest(10, rank_col)["candidate_id"].tolist()

    summary = {
        "base_scenario": "base",
        "weight_scenarios_tested": len(weight_scenarios),
        "robust_sites_count": len(robust_sites),
        "sensitive_sites_count": len(sensitive_sites),
        "very_sensitive_sites_count": len(very_sensitive_sites),
        "robust_site_ids": robust_sites,
        "very_sensitive_site_ids": very_sensitive_sites,
        "top_10_comparison": top_10_comparison,
        "classification": "AHP weight sensitivity; rankings encode stakeholder preferences",
    }

    summary_df = pd.DataFrame([summary])
    write_csv(summary_df, str(path).replace(".csv", "_summary.csv"))

    return {
        "path": str(path),
        "summary": summary,
    }
