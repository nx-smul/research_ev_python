"""Tests for AC power flow simulation, voltage stability, and grid reinforcement."""

import os
import pytest
import numpy as np
import pandas as pd
import pandapower as pp

from src.grid.voltage_stability import (
    evaluate_voltage_stability,
    calculate_voltage_deviation_index,
    evaluate_thermal_loading,
    estimate_thd_harmonics
)
from src.grid.grid_reinforcement import (
    calculate_substation_upgrade_cost,
    calculate_bess_peak_shaving
)
from src.grid.power_flow import GridPowerFlowSimulator


def test_voltage_stability_assessment():
    # Normal bus voltages within 0.95 - 1.05 p.u.
    bus_df_normal = pd.DataFrame({
        "vm_pu": [1.02, 1.00, 0.98, 0.96]
    })
    res_normal = evaluate_voltage_stability(bus_df_normal, v_min_pu=0.95, v_max_pu=1.05)
    assert res_normal["is_compliant"] is True
    assert res_normal["undervoltage_count"] == 0
    assert res_normal["overvoltage_count"] == 0
    assert res_normal["min_v_pu"] == 0.96

    # Violating bus voltages (under and over)
    bus_df_violation = pd.DataFrame({
        "vm_pu": [1.08, 1.00, 0.92, 0.94]
    })
    res_violation = evaluate_voltage_stability(bus_df_violation, v_min_pu=0.95, v_max_pu=1.05)
    assert res_violation["is_compliant"] is False
    assert res_violation["undervoltage_count"] == 2
    assert res_violation["overvoltage_count"] == 1


def test_voltage_deviation_index():
    # Identical to nominal 1.0 p.u. -> VDI = 0
    vm_nominal = np.array([1.0, 1.0, 1.0])
    assert calculate_voltage_deviation_index(vm_nominal) == 0.0

    # Deviations
    vm_deviated = np.array([0.95, 1.05])
    # Deviations are -0.05 and +0.05 -> mean sq = 0.0025 -> sqrt = 0.05
    assert np.isclose(calculate_voltage_deviation_index(vm_deviated), 0.05)


def test_thermal_loading_assessment():
    line_df = pd.DataFrame({"loading_percent": [45.0, 85.0, 105.0]})
    trafo_df = pd.DataFrame({"loading_percent": [60.0, 95.0]})

    res = evaluate_thermal_loading(line_df, trafo_df, max_loading_pct=100.0)
    assert res["is_thermal_compliant"] is False
    assert res["overloaded_line_count"] == 1
    assert res["max_line_loading_pct"] == 105.0
    assert res["max_trafo_loading_pct"] == 95.0


def test_voltage_thd_estimation():
    thd_pct = estimate_thd_harmonics(ev_power_kw=2000.0, baseline_power_kw=100000.0, short_circuit_mva=500.0)
    assert thd_pct >= 0.0
    assert thd_pct <= 5.0, "Expected THD <= 5.0% IEEE 519 limit"


def test_substation_upgrade_cost():
    # Within headroom -> 0 cost
    cost, excess = calculate_substation_upgrade_cost(
        station_power_kw=2000.0,
        available_headroom_mva=5.0,
        upgrade_cost_per_mva=3500000.0,
        power_factor=0.95
    )
    assert cost == 0.0
    assert excess == 0.0

    # Exceeding headroom
    cost_over, excess_over = calculate_substation_upgrade_cost(
        station_power_kw=8000.0,
        available_headroom_mva=5.0,
        upgrade_cost_per_mva=3500000.0,
        power_factor=0.95
    )
    assert excess_over > 0.0
    assert cost_over > 0.0


def test_bess_sizing():
    # No overload -> No BESS needed
    bess_none = calculate_bess_peak_shaving(station_power_kw=2000.0, available_headroom_mva=5.0)
    assert bess_none["needs_bess"] is False
    assert bess_none["bess_power_kw"] == 0.0

    # Overload -> BESS sized
    bess_req = calculate_bess_peak_shaving(station_power_kw=8000.0, available_headroom_mva=5.0)
    assert bess_req["needs_bess"] is True
    assert bess_req["bess_power_kw"] > 0
    assert bess_req["bess_energy_kwh"] > 0
    assert bess_req["bess_capex_bdt"] > 0


def test_pandapower_simulator_baseline(mock_pandapower_network):
    # Save mock network to temp json or run power flow directly
    pp.runpp(mock_pandapower_network, numba=False)
    bus_res = mock_pandapower_network.res_bus
    assert len(bus_res) == 3
    assert np.all(bus_res["vm_pu"] > 0.90) and np.all(bus_res["vm_pu"] < 1.10)
