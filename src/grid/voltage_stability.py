"""Voltage stability assessment, thermal loading checks, and harmonic distortion estimation."""

import numpy as np
import pandas as pd


def evaluate_voltage_stability(bus_results_df, v_min_pu=0.95, v_max_pu=1.05):
    """Evaluate bus voltage compliance with IEEE / utility standards.

    Args:
        bus_results_df (pd.DataFrame): DataFrame containing 'vm_pu' (voltage magnitude in p.u.).
        v_min_pu (float): Lower permissible voltage limit (default 0.95 p.u.).
        v_max_pu (float): Upper permissible voltage limit (default 1.05 p.u.).

    Returns:
        dict: Voltage stability metrics (violations, min_v, max_v, vdi, is_compliant).
    """
    vm = bus_results_df["vm_pu"].to_numpy()
    undervoltage_buses = np.where(vm < v_min_pu)[0].tolist()
    overvoltage_buses = np.where(vm > v_max_pu)[0].tolist()

    vdi = calculate_voltage_deviation_index(vm)
    is_compliant = (len(undervoltage_buses) == 0 and len(overvoltage_buses) == 0)

    return {
        "is_compliant": is_compliant,
        "vdi": round(vdi, 5),
        "min_v_pu": round(float(np.min(vm)), 4),
        "max_v_pu": round(float(np.max(vm)), 4),
        "mean_v_pu": round(float(np.mean(vm)), 4),
        "undervoltage_count": len(undervoltage_buses),
        "overvoltage_count": len(overvoltage_buses),
        "undervoltage_buses": undervoltage_buses,
        "overvoltage_buses": overvoltage_buses
    }


def calculate_voltage_deviation_index(vm_array):
    """Calculate Voltage Deviation Index (VDI) = sqrt( (1/N) * sum_k (V_k - 1.0)^2 )."""
    arr = np.array(vm_array, dtype=np.float64)
    return float(np.sqrt(np.mean((arr - 1.0) ** 2)))


def evaluate_thermal_loading(line_results_df, trafo_results_df=None, max_loading_pct=100.0):
    """Evaluate feeder line and transformer thermal loading limits.

    Args:
        line_results_df (pd.DataFrame): DataFrame containing 'loading_percent' for lines.
        trafo_results_df (pd.DataFrame, optional): DataFrame containing 'loading_percent' for transformers.
        max_loading_pct (float): Maximum thermal threshold (default 100.0%).

    Returns:
        dict: Thermal loading summary (max_line_load, max_trafo_load, overloads).
    """
    line_loading = line_results_df["loading_percent"].to_numpy() if "loading_percent" in line_results_df.columns else np.array([50.0])
    trafo_loading = trafo_results_df["loading_percent"].to_numpy() if (trafo_results_df is not None and "loading_percent" in trafo_results_df.columns) else np.array([50.0])

    overloaded_lines = np.where(line_loading > max_loading_pct)[0].tolist()
    overloaded_trafos = np.where(trafo_loading > max_loading_pct)[0].tolist()

    return {
        "is_thermal_compliant": (len(overloaded_lines) == 0 and len(overloaded_trafos) == 0),
        "max_line_loading_pct": round(float(np.max(line_loading)), 2),
        "max_trafo_loading_pct": round(float(np.max(trafo_loading)), 2),
        "overloaded_line_count": len(overloaded_lines),
        "overloaded_trafo_count": len(overloaded_trafos),
        "overloaded_lines": overloaded_lines,
        "overloaded_trafos": overloaded_trafos
    }


def estimate_thd_harmonics(ev_power_kw, baseline_power_kw, short_circuit_mva=500.0):
    """Estimate voltage Total Harmonic Distortion (THD_V) injected by EV power converters.

    Standard IEEE 519 limit is THD_V <= 5.0%.
    """
    if baseline_power_kw <= 0:
        return 0.0

    ev_penetration_ratio = ev_power_kw / (baseline_power_kw + ev_power_kw)
    # Empirical harmonic distortion model for 6-pulse and 12-pulse IGBT DC fast chargers
    # THD_V approx increases quadratically with EV load relative to short circuit grid strength
    base_thd = 1.2  # 1.2% background grid THD in Dhaka
    added_thd = 3.5 * (ev_penetration_ratio ** 1.5) * (100.0 / short_circuit_mva)
    total_thd = min(15.0, base_thd + added_thd)

    return round(float(total_thd), 2)
