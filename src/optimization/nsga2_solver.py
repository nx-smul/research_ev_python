"""Fast elitist Multi-Objective Genetic Algorithm (NSGA-II) for EVCS placement and capacity sizing."""

import argparse
import os
import sys
import copy
import json
import yaml
import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm

from .cost_functions import calculate_grid_connection_cost, calculate_station_capex, evaluate_objectives


class SolutionCandidate:
    """Represents a single candidate EVCS placement & sizing solution."""

    def __init__(self, x, Y):
        self.x = np.array(x, dtype=int)  # 1D binary array of length M
        self.Y = np.array(Y, dtype=int)  # 2D integer array M x K
        self.objectives = []  # [F1_cost, -F2_coverage] (minimization formulation)
        self.F1_cost = 0.0
        self.F2_coverage = 0.0
        self.rank = 0
        self.crowding_distance = 0.0
        self.z_assignment = None
        self.penalties = 0.0
        self.demand_values = None


class NSGA2Solver:
    """Multi-Objective Genetic Algorithm Solver implementing NSGA-II."""

    def __init__(self, dist_matrix, time_matrix, demand_values, candidate_metadata, config):
        self.dist_matrix = np.array(dist_matrix, dtype=np.float64)
        self.time_matrix = np.array(time_matrix, dtype=np.float64)
        self.demand_values = np.array(demand_values, dtype=np.float64)
        self.candidate_metadata = candidate_metadata
        self.config = config

        self.N = len(demand_values)
        self.M = len(candidate_metadata)
        self.charger_specs = config["chargers"]
        self.K = len(self.charger_specs)

        opt = config["optimization"]
        self.y_min = opt.get("min_chargers_per_station", 2)
        self.y_max = opt.get("max_chargers_per_station", 12)
        self.min_open_stations = opt.get("min_open_stations", 3)
        self.max_open_stations = min(opt.get("max_open_stations", self.M), self.M)
        if self.min_open_stations > self.max_open_stations:
            raise ValueError("Station-count limits exceed the number of available candidate sites.")
        if self.min_open_stations * self.y_min > self.max_open_stations * self.y_max:
            raise ValueError("Station and charger-count limits are infeasible.")
        self.budget_cap_bdt = opt.get("budget_cap_bdt")
        self.r_max = opt.get("service_radius_rmax_m", 5000.0)

        nsga_cfg = opt.get("nsga2", {})
        self.pop_size = nsga_cfg.get("population_size", 100)
        self.generations = nsga_cfg.get("generations", 250)
        self.cx_prob = nsga_cfg.get("crossover_probability", 0.85)
        self.mut_prob = nsga_cfg.get("mutation_probability", 0.15)
        self.seed = nsga_cfg.get("random_seed", 42)

        self.rng = np.random.default_rng(self.seed)

    def initialize_population(self):
        """Create initial random population of valid solutions."""
        pop = []
        for _ in range(self.pop_size):
            # Sample a valid number of open sites from configured limits.
            num_open = self.rng.integers(self.min_open_stations, self.max_open_stations + 1)
            open_indices = self.rng.choice(self.M, size=num_open, replace=False)
            x = np.zeros(self.M, dtype=int)
            x[open_indices] = 1

            Y = np.zeros((self.M, self.K), dtype=int)
            for j in open_indices:
                total_chargers = self.rng.integers(self.y_min, self.y_max + 1)
                # Distribute chargers among K types
                probs = self.rng.dirichlet(np.ones(self.K))
                counts = self.rng.multinomial(total_chargers, probs)
                Y[j, :] = counts

            cand = SolutionCandidate(x, Y)
            self.evaluate_individual(cand)
            pop.append(cand)

        return pop

    def evaluate_individual(self, ind):
        """Evaluate objectives F1 (Cost) and F2 (Coverage)."""
        F1, F2, z_mat, pen = evaluate_objectives(
            ind.x, ind.Y, self.dist_matrix, self.time_matrix,
            self.demand_values, self.candidate_metadata, self.config
        )
        ind.F1_cost = F1
        ind.F2_coverage = F2
        ind.demand_values = self.demand_values.copy()
        ind.z_assignment = z_mat
        ind.penalties = pen
        ind.capex_bdt = self.calculate_capex(ind.x, ind.Y)
        ind.budget_feasible = self.budget_cap_bdt is None or ind.capex_bdt <= self.budget_cap_bdt
        # Penalize over-budget solutions while retaining a gradient toward the cap.
        if ind.budget_feasible:
            ind.objectives = [F1, -F2]
        else:
            overrun = ind.capex_bdt - self.budget_cap_bdt
            ind.objectives = [1e30 + overrun, 1e30 + overrun]

    def calculate_capex(self, x, Y):
        """Calculate upfront station CAPEX, including land, equipment, installation and grid connection."""
        econ = self.config["economic"]
        total = 0.0
        for j in np.flatnonzero(x):
            meta = self.candidate_metadata[j]
            land_cost = meta.get("land_cost_bdt_sqm")
            substation_distance = meta.get("distance_to_substation_m")
            if land_cost is None or pd.isna(land_cost):
                raise ValueError(
                    f"Candidate '{meta.get('candidate_id', j)}' has no sourced land cost."
                )
            if substation_distance is None or pd.isna(substation_distance):
                raise ValueError(
                    f"Candidate '{meta.get('candidate_id', j)}' has no sourced substation distance."
                )
            capex, _, _, _ = calculate_station_capex(
                Y[j], land_cost, self.charger_specs,
                econ.get("land_acquisition_base_sqm", 120.0),
                econ.get("land_sqm_per_charger", 25.0),
            )
            power_kw = sum(Y[j, k] * spec["power_kw"] for k, spec in enumerate(self.charger_specs.values()))
            grid_cost = calculate_grid_connection_cost(
                power_kw, substation_distance,
                econ.get("grid_connection_cost_per_kw", 4500.0),
                econ.get("grid_distance_penalty_bdt_per_m", 1200.0),
            )
            total += capex + grid_cost
        return total

    def fast_non_dominated_sort(self, population):
        """Partition population into non-dominated Pareto fronts F_1, F_2, ..."""
        fronts = [[]]
        for p in population:
            p.domination_count = 0
            p.dominated_solutions = []
            for q in population:
                if self.dominates(p, q):
                    p.dominated_solutions.append(q)
                elif self.dominates(q, p):
                    p.domination_count += 1

            if p.domination_count == 0:
                p.rank = 0
                fronts[0].append(p)

        i = 0
        while len(fronts[i]) > 0:
            next_front = []
            for p in fronts[i]:
                for q in p.dominated_solutions:
                    q.domination_count -= 1
                    if q.domination_count == 0:
                        q.rank = i + 1
                        next_front.append(q)
            i += 1
            fronts.append(next_front)

        if len(fronts[-1]) == 0:
            fronts.pop()

        return fronts

    def dominates(self, ind1, ind2):
        """Returns True if ind1 dominates ind2 (strictly better in at least one and no worse in any)."""
        better_in_any = False
        for obj1, obj2 in zip(ind1.objectives, ind2.objectives):
            if obj1 > obj2:
                return False
            elif obj1 < obj2:
                better_in_any = True
        return better_in_any

    def calculate_crowding_distance(self, front):
        """Assign crowding distance to solutions within a Pareto front."""
        l = len(front)
        if l == 0:
            return
        for ind in front:
            ind.crowding_distance = 0.0

        num_objectives = len(front[0].objectives)

        for m in range(num_objectives):
            front.sort(key=lambda ind: ind.objectives[m])
            front[0].crowding_distance = float("inf")
            front[-1].crowding_distance = float("inf")

            f_min = front[0].objectives[m]
            f_max = front[-1].objectives[m]
            denom = f_max - f_min
            if denom == 0:
                continue

            for i in range(1, l - 1):
                front[i].crowding_distance += (front[i + 1].objectives[m] - front[i - 1].objectives[m]) / denom

    def binary_tournament_selection(self, population):
        """Select best candidate using crowded comparison operator (rank first, crowding distance second)."""
        idx1, idx2 = self.rng.choice(len(population), size=2, replace=False)
        ind1, ind2 = population[idx1], population[idx2]

        if ind1.rank < ind2.rank:
            return ind1
        elif ind2.rank < ind1.rank:
            return ind2
        else:
            return ind1 if ind1.crowding_distance >= ind2.crowding_distance else ind2

    def crossover(self, parent1, parent2):
        """Uniform / SBX crossover on station selection and charger allocations."""
        if self.rng.random() > self.cx_prob:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        # Crossover on selection vector x
        mask = self.rng.random(self.M) < 0.5
        child1_x = np.where(mask, parent1.x, parent2.x)
        child2_x = np.where(mask, parent2.x, parent1.x)

        # Crossover on charger matrix Y
        mask_Y = self.rng.random((self.M, self.K)) < 0.5
        child1_Y = np.where(mask_Y, parent1.Y, parent2.Y)
        child2_Y = np.where(mask_Y, parent2.Y, parent1.Y)

        self.repair_individual(child1_x, child1_Y)
        self.repair_individual(child2_x, child2_Y)

        c1 = SolutionCandidate(child1_x, child1_Y)
        c2 = SolutionCandidate(child2_x, child2_Y)
        self.evaluate_individual(c1)
        self.evaluate_individual(c2)

        return c1, c2

    def mutate(self, ind):
        """Polynomial / uniform mutation on station locations and charger sizing."""
        if self.rng.random() < self.mut_prob:
            # Mutate station toggle x
            mutate_sites = self.rng.choice(self.M, size=max(1, int(0.10 * self.M)), replace=False)
            ind.x[mutate_sites] = 1 - ind.x[mutate_sites]

        if self.rng.random() < self.mut_prob:
            # Mutate charger counts
            for j in range(self.M):
                if ind.x[j] == 1 and self.rng.random() < 0.30:
                    k = self.rng.integers(self.K)
                    delta = self.rng.choice([-2, -1, 1, 2])
                    ind.Y[j, k] = max(0, ind.Y[j, k] + delta)

        self.repair_individual(ind.x, ind.Y)
        self.evaluate_individual(ind)

    def repair_individual(self, x, Y):
        """Enforce bounds: y_min * x_j <= sum_t y_jt <= y_max * x_j."""
        # Bound the number of open stations first; randomly drop/add sites as needed.
        open_indices = np.flatnonzero(x)
        if len(open_indices) > self.max_open_stations:
            drop = self.rng.choice(open_indices, len(open_indices) - self.max_open_stations, replace=False)
            x[drop] = 0
        elif len(open_indices) < self.min_open_stations:
            closed_indices = np.flatnonzero(x == 0)
            add = self.rng.choice(closed_indices, self.min_open_stations - len(open_indices), replace=False)
            x[add] = 1

        for j in range(self.M):
            if x[j] == 0:
                Y[j, :] = 0
            else:
                total = np.sum(Y[j, :])
                if total < self.y_min:
                    Y[j, 0] += self.y_min - total
                elif total > self.y_max:
                    scale = self.y_max / total
                    Y[j, :] = np.floor(Y[j, :] * scale).astype(int)
                    while np.sum(Y[j, :]) < self.y_min:
                        Y[j, 0] += 1

    def solve(self, generations=None, show_progress=True):
        """Execute NSGA-II optimization loop."""
        gens = generations or self.generations
        population = self.initialize_population()
        fronts = self.fast_non_dominated_sort(population)
        for front in fronts:
            self.calculate_crowding_distance(front)

        pbar = tqdm(range(gens), desc="NSGA-II Optimizing", disable=not show_progress)
        for gen in pbar:
            offspring = []
            while len(offspring) < self.pop_size:
                p1 = self.binary_tournament_selection(population)
                p2 = self.binary_tournament_selection(population)
                c1, c2 = self.crossover(p1, p2)
                self.mutate(c1)
                self.mutate(c2)
                offspring.extend([c1, c2])

            # Merge Parent and Offspring (2N -> N elitist reduction)
            combined_pop = population + offspring[:self.pop_size]
            fronts = self.fast_non_dominated_sort(combined_pop)

            new_pop = []
            front_idx = 0
            while front_idx < len(fronts) and len(new_pop) + len(fronts[front_idx]) <= self.pop_size:
                self.calculate_crowding_distance(fronts[front_idx])
                new_pop.extend(fronts[front_idx])
                front_idx += 1

            if len(new_pop) < self.pop_size and front_idx < len(fronts):
                last_front = fronts[front_idx]
                self.calculate_crowding_distance(last_front)
                last_front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                needed = self.pop_size - len(new_pop)
                new_pop.extend(last_front[:needed])

            population = new_pop

            if gen % 10 == 0 or gen == gens - 1:
                best_cost = min(ind.F1_cost for ind in population)
                max_cov = max(ind.F2_coverage for ind in population)
                pbar.set_postfix({"Min Cost (M BDT)": f"{best_cost/1e6:.1f}", "Max Coverage": f"{max_cov:.0f}"})

        # Extract Pareto Front (Rank 0 solutions)
        final_fronts = self.fast_non_dominated_sort(population)
        pareto_front = [ind for ind in final_fronts[0] if ind.budget_feasible]
        if not pareto_front:
            raise ValueError(
                "No budget-feasible EVCS solution was found. Increase optimization.budget_cap_bdt "
                "or relax station/charger limits."
            )
        # Sort Pareto front by Cost ascending
        pareto_front.sort(key=lambda ind: ind.F1_cost)

        return pareto_front, population


def self_budget(config):
    """Return configured upfront CAPEX limit, or None when no cap is set."""
    return config["optimization"].get("budget_cap_bdt")


def canonicalize_pareto_front(pareto_front):
    """Sort and deduplicate a Pareto front for stable labels and exports."""
    unique = {}
    for solution in pareto_front:
        key = (round(float(solution.F1_cost), 10), round(float(solution.F2_coverage), 10))
        previous = unique.get(key)
        signature = (tuple(solution.x.tolist()), tuple(solution.Y.ravel().tolist()))
        if previous is None:
            unique[key] = (signature, solution)
        else:
            old_signature, _ = previous
            if signature < old_signature:
                unique[key] = (signature, solution)
    return [entry[1] for _, entry in sorted(
        unique.items(), key=lambda item: (item[0][0], -item[0][1], item[1][0])
    )]


def export_pareto_solutions(pareto_front, candidate_metadata, config, output_csv_path):
    """Export a canonical, cost-sorted Pareto table with stable solution identifiers."""
    pareto_front = canonicalize_pareto_front(pareto_front)
    if not pareto_front:
        raise ValueError("Cannot export an empty Pareto front.")
    charger_keys = list(config["chargers"].keys())
    usd_rate = config["economic"].get("currency_usd_to_bdt", 115.0)
    total_potential_demand = float(np.sum(pareto_front[0].demand_values)) if pareto_front else 0.0
    if not np.isfinite(total_potential_demand) or total_potential_demand <= 0:
        raise ValueError("Cannot export demand coverage without positive, finite input demand values.")

    rows = []
    for sol_idx, sol in enumerate(pareto_front):
        open_site_indices = np.where(sol.x == 1)[0]
        open_site_ids = [candidate_metadata[j]["candidate_id"] for j in open_site_indices]

        # Sizing summary by charger type
        total_chargers = {k: int(np.sum(sol.Y[:, idx])) for idx, k in enumerate(charger_keys)}
        total_kw = sum(
            total_chargers[k] * config["chargers"][k]["power_kw"] for k in charger_keys
        )

        coverage_pct = round(min(100.0, (sol.F2_coverage / total_potential_demand) * 100.0), 2)

        rows.append({
            "solution_id": f"SOL-{sol_idx + 1:03d}",
            "total_cost_bdt": round(sol.F1_cost, 2),
            "total_cost_million_bdt": round(sol.F1_cost / 1e6, 3),
            "total_cost_usd": round(sol.F1_cost / usd_rate, 2),
            "total_cost_million_usd": round((sol.F1_cost / usd_rate) / 1e6, 3),
            "demand_coverage_score": round(sol.F2_coverage, 2),
            "demand_coverage_denominator_kwh": round(total_potential_demand, 6),
            "demand_coverage_pct": coverage_pct,
            "open_station_count": len(open_site_ids),
            "total_grid_power_kw": round(total_kw, 1),
            "selected_station_ids": ";".join(open_site_ids),
            "charger_allocations_json": json.dumps(total_chargers),
            "penalties_bdt": round(sol.penalties, 2),
            "upfront_capex_bdt": round(sol.capex_bdt, 2),
            "budget_cap_bdt": self_budget(config),
            "budget_feasible": bool(sol.budget_feasible)
        })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    print(f"[NSGA-II] Exported {len(rows)} Pareto-optimal solutions to {output_csv_path}")
    return df


def main():
    parser = argparse.ArgumentParser(description="Multi-objective NSGA-II optimization solver for EVCS placement.")
    parser.add_argument("--config", type=str, default="configs/dhaka_scenario_2030.yaml", help="Path to config YAML.")
    parser.add_argument("--generations", type=int, default=250, help="Number of GA generations.")
    parser.add_argument("--population", type=int, default=100, help="Population size.")
    parser.add_argument("--output", type=str, default="results/tables/optimal_solutions_pareto.csv", help="Output path for Pareto solutions CSV.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, args.config) if not os.path.isabs(args.config) else args.config

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Load OD matrix and candidate metadata
    npz_path = os.path.join(base_dir, "data", "processed", "od_travel_time_matrix.npz")
    candidate_geojson_path = os.path.join(base_dir, "data", "processed", "candidate_sites_filtered.geojson")

    if not (os.path.exists(npz_path) and os.path.exists(candidate_geojson_path)):
        parser.error("OD matrix and candidate inputs are required. Obtain source data or run `python main.py --mode data` for synthetic demo data; no data was generated automatically.")

    data = np.load(npz_path)
    dist_matrix = data["distances"]
    time_matrix = data["travel_times"]
    demand_values = data["demand_values"]

    candidate_gdf = gpd.read_file(candidate_geojson_path)
    candidate_metadata = candidate_gdf.to_dict(orient="records")

    solver = NSGA2Solver(dist_matrix, time_matrix, demand_values, candidate_metadata, config)
    solver.pop_size = args.population
    solver.generations = args.generations

    print(f"[NSGA-II] Starting multi-objective optimization ({args.population} population, {args.generations} generations)...")
    pareto_front, _ = solver.solve(generations=args.generations)

    output_csv = os.path.join(base_dir, args.output) if not os.path.isabs(args.output) else args.output
    export_pareto_solutions(pareto_front, candidate_metadata, config, output_csv)


if __name__ == "__main__":
    main()
