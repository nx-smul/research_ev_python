"""Mixed-Integer Linear Programming (MILP) formulation for CMO-EVCSLSP and MCLP / P-Median."""

import numpy as np
import pyomo.environ as pyo
from scipy.optimize import milp, LinearConstraint, Bounds


class CMO_EVCS_MILP:
    """Capacitated Multi-Objective EVCS Location & Sizing MILP Model."""

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

    def build_pyomo_model(self, budget_cap=None, p_stations=None, coverage_weight=0.5):
        """Build Pyomo ConcreteModel for CMO-EVCSLSP.

        Args:
            budget_cap (float, optional): Maximum capital expenditure budget.
            p_stations (int, optional): Fixed number of stations for P-Median / MCLP.
            coverage_weight (float): Multi-objective trade-off weight in [0, 1].

        Returns:
            pyo.ConcreteModel
        """
        model = pyo.ConcreteModel(name="Dhaka_EVCS_Placement_MILP")

        # Sets
        model.I = pyo.RangeSet(0, self.N - 1)  # Demand zones
        model.J = pyo.RangeSet(0, self.M - 1)  # Candidate sites
        model.T = pyo.RangeSet(0, self.K - 1)  # Charger types

        # Parameters
        r_max = self.config["optimization"].get("service_radius_rmax_m", 5000.0)
        y_min = self.config["optimization"].get("min_chargers_per_station", 2)
        y_max = self.config["optimization"].get("max_chargers_per_station", 12)
        charger_list = list(self.charger_specs.values())

        # Decision Variables
        model.x = pyo.Var(model.J, within=pyo.Binary)  # 1 if station j is open
        model.y = pyo.Var(model.J, model.T, within=pyo.NonNegativeIntegers)  # chargers of type t at station j
        model.z = pyo.Var(model.I, model.J, within=pyo.NonNegativeReals, bounds=(0.0, 1.0))  # Fraction served

        # 1. Demand Satisfaction / Assignment Constraints
        def demand_assignment_rule(m, i):
            return sum(m.z[i, j] for j in m.J if self.dist_matrix[i, j] <= r_max) <= 1.0
        model.demand_assignment = pyo.Constraint(model.I, rule=demand_assignment_rule)

        def linking_rule(m, i, j):
            if self.dist_matrix[i, j] > r_max:
                return m.z[i, j] == 0.0
            return m.z[i, j] <= m.x[j]
        model.linking = pyo.Constraint(model.I, model.J, rule=linking_rule)

        # 2. Station Capacity Constraint: sum_i D_i * z_ij <= sum_t eta_t * C_t * y_jt
        def capacity_rule(m, j):
            daily_capacity = sum(
                charger_list[t]["daily_energy_kwh"] * charger_list[t]["efficiency"] * m.y[j, t]
                for t in m.T
            )
            return sum(self.demand_values[i] * m.z[i, j] for i in m.I) <= daily_capacity
        model.station_capacity = pyo.Constraint(model.J, rule=capacity_rule)

        # 3. Charger Sizing Bounds: y_min * x_j <= sum_t y_jt <= y_max * x_j
        def min_sizing_rule(m, j):
            return sum(m.y[j, t] for t in m.T) >= y_min * m.x[j]
        model.min_sizing = pyo.Constraint(model.J, rule=min_sizing_rule)

        def max_sizing_rule(m, j):
            return sum(m.y[j, t] for t in m.T) <= y_max * m.x[j]
        model.max_sizing = pyo.Constraint(model.J, rule=max_sizing_rule)

        # 4. Optional Station Count Constraint (P-Median / MCLP)
        if p_stations is not None:
            def p_median_rule(m):
                return sum(m.x[j] for j in m.J) == p_stations
            model.p_stations_con = pyo.Constraint(rule=p_median_rule)

        # Objective Function: Weighted Normalized Formulation
        # Min Cost + Max Coverage
        def objective_rule(m):
            # Cost approximation
            equip_cost = sum(
                (charger_list[t]["cap_cost_bdt"] + charger_list[t]["inst_cost_bdt"]) * m.y[j, t]
                for j in m.J for t in m.T
            )
            land_cost = sum(
                self.candidate_metadata[j].get("land_cost_bdt_sqm", 100000.0) * (120.0 * m.x[j] + sum(25.0 * m.y[j, t] for t in m.T))
                for j in m.J
            )
            # Coverage (sum of served demand with distance decay)
            decay = np.exp(-self.config["optimization"].get("lambda_impedance", 0.00035) * self.dist_matrix)
            coverage = sum(
                self.demand_values[i] * m.z[i, j] * float(decay[i, j])
                for i in m.I for j in m.J
            )
            # Combine
            return (1.0 - coverage_weight) * (equip_cost + land_cost) * 1e-6 - coverage_weight * coverage

        model.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize)
        return model

    def solve_scipy_milp_fallback(self, p_stations=15):
        """Pure SciPy MILP fallback solver for MCLP / P-Median station selection.

        Returns:
            dict: Optimal binary selection vector x and summary stats.
        """
        # Formulate classic P-Median / MCLP problem with SciPy
        # Variables: x_j in {0, 1} for j in 0..M-1
        # Objective: Maximize coverage = sum_i D_i * max_j(x_j * exp(-lambda * d_ij))
        # Approximation: Linearized station utility score
        decay = np.exp(-0.00035 * self.dist_matrix)
        potential_coverage = np.dot(self.demand_values, decay)  # shape (M,)

        land_costs = np.array([m.get("land_cost_bdt_sqm", 100000.0) for m in self.candidate_metadata])

        # Benefit - Cost vector for each station j
        c_obj = -(potential_coverage / np.max(potential_coverage)) + 0.35 * (land_costs / np.max(land_costs))

        # Constraint: sum(x_j) <= p_stations
        A_eq = np.ones((1, self.M))
        constraints = LinearConstraint(A_eq, lb=1, ub=p_stations)
        integrality = np.ones(self.M)  # All integer/binary
        bounds = Bounds(lb=0, ub=1)

        res = milp(c=c_obj, constraints=constraints, integrality=integrality, bounds=bounds)
        if res.success:
            x_opt = np.round(res.x).astype(int)
        else:
            # Fallback heuristic: top p stations by potential coverage
            top_indices = np.argsort(-potential_coverage)[:p_stations]
            x_opt = np.zeros(self.M, dtype=int)
            x_opt[top_indices] = 1

        return {
            "x": x_opt,
            "selected_station_count": int(np.sum(x_opt)),
            "selected_indices": np.where(x_opt == 1)[0].tolist(),
            "status": "Optimal" if res.success else "Heuristic"
        }
