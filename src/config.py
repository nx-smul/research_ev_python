"""Load and validate scenario configuration plus user overrides."""

from copy import deepcopy
from math import isfinite
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """Raised when a scenario or override configuration is invalid."""


def _deep_merge(base, overrides):
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _read_yaml(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration file '{path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file '{path}' must contain a YAML mapping.")
    return data


def _validate_keys(overrides, base, prefix=""):
    for key, value in overrides.items():
        full_key = f"{prefix}.{key}" if prefix else key
        allowed_additions = {
            "optimization": {"min_open_stations", "max_open_stations", "service_radius_rmax_m"},
        }
        if key not in base and key not in allowed_additions.get(prefix, set()):
            raise ConfigError(f"Unknown settings key '{full_key}'.")
        if isinstance(value, dict):
            if key not in base:
                if full_key != "optimization":
                    raise ConfigError(f"Settings section '{full_key}' must be a mapping already defined in the scenario.")
                _validate_keys(value, {}, full_key)
                continue
            if not isinstance(base[key], dict):
                raise ConfigError(f"Settings section '{full_key}' must be a scalar value.")
            _validate_keys(value, base[key], full_key)


def validate_config(config):
    """Validate user-facing optimization controls and applicable value ranges."""
    opt = config.get("optimization")
    if not isinstance(opt, dict):
        raise ConfigError("'optimization' must be a mapping.")

    def integer(key, default):
        value = opt.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ConfigError(f"'optimization.{key}' must be a positive integer.")
        return value

    min_open = integer("min_open_stations", 3)
    max_open = integer("max_open_stations", int(opt.get("max_candidate_sites", 50)))
    min_chargers = integer("min_chargers_per_station", 2)
    max_chargers = integer("max_chargers_per_station", 12)
    if min_open > max_open:
        raise ConfigError("'optimization.min_open_stations' cannot exceed 'optimization.max_open_stations'.")
    if min_chargers > max_chargers:
        raise ConfigError("'optimization.min_chargers_per_station' cannot exceed 'optimization.max_chargers_per_station'.")
    candidate_count = config.get("spatial", {}).get("candidate_site_generation", {}).get("max_candidate_sites")
    if candidate_count is not None and max_open > candidate_count:
        raise ConfigError("'optimization.max_open_stations' cannot exceed spatial.candidate_site_generation.max_candidate_sites.")

    budget = opt.get("budget_cap_bdt")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float)) or not isfinite(budget) or budget <= 0):
        raise ConfigError("'optimization.budget_cap_bdt' must be a positive number.")

    service_radius = opt.get("service_radius_rmax_m", 5000.0)
    if isinstance(service_radius, bool) or not isinstance(service_radius, (int, float)) or not isfinite(service_radius) or service_radius <= 0:
        raise ConfigError("'optimization.service_radius_rmax_m' must be a finite positive number.")
    impedance = opt.get("lambda_impedance", 0.00035)
    if isinstance(impedance, bool) or not isinstance(impedance, (int, float)) or not isfinite(impedance) or impedance < 0:
        raise ConfigError("'optimization.lambda_impedance' must be a finite non-negative number.")

    nsga = opt.setdefault("nsga2", {})
    if not isinstance(nsga, dict):
        raise ConfigError("'optimization.nsga2' must be a mapping.")
    for key in ("population_size", "generations"):
        value = nsga.get(key, 100 if key == "population_size" else 250)
        if isinstance(value, bool) or not isinstance(value, int) or value < 2:
            raise ConfigError(f"'optimization.nsga2.{key}' must be an integer of at least 2.")
    for key in ("crossover_probability", "mutation_probability"):
        value = nsga.get(key, 0.85 if key == "crossover_probability" else 0.15)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
            raise ConfigError(f"'optimization.nsga2.{key}' must be finite and within [0, 1].")
    seed = nsga.get("random_seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ConfigError("'optimization.nsga2.random_seed' must be a non-negative integer.")

    def validate_positive_numbers(section_name, keys, allow_zero=False):
        section = config.get(section_name, {})
        if not isinstance(section, dict):
            raise ConfigError(f"'{section_name}' must be a mapping.")
        for key in keys:
            value = section.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ConfigError(f"'{section_name}.{key}' must be finite numeric.")
            if value < 0 or (value == 0 and not allow_zero):
                qualifier = "non-negative" if allow_zero else "positive"
                raise ConfigError(f"'{section_name}.{key}' must be {qualifier}.")

    validate_positive_numbers("economic", (
        "discount_rate", "project_lifetime_years", "vot_bdt_per_hour", "currency_usd_to_bdt",
        "land_acquisition_base_sqm", "land_sqm_per_charger", "grid_connection_cost_per_kw",
        "grid_distance_penalty_bdt_per_m",
    ), allow_zero=True)
    if config.get("economic", {}).get("discount_rate", 0) >= 1:
        raise ConfigError("'economic.discount_rate' must be less than 1.")
    alpha = config.get("economic", {}).get("alpha_delay_weight")
    if alpha is not None and (isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not isfinite(alpha) or not 0 <= alpha <= 1):
        raise ConfigError("'economic.alpha_delay_weight' must be finite and within [0, 1].")

    grid = config.get("grid", {})
    if not isinstance(grid, dict):
        raise ConfigError("'grid' must be a mapping.")
    for key in ("v_min_pu", "v_max_pu", "max_line_loading_pct", "max_transformer_loading_pct", "power_factor", "thd_v_limit_pct"):
        value = grid.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)):
            raise ConfigError(f"'grid.{key}' must be finite numeric.")
    if "v_min_pu" in grid and "v_max_pu" in grid and grid["v_min_pu"] >= grid["v_max_pu"]:
        raise ConfigError("'grid.v_min_pu' must be less than 'grid.v_max_pu'.")
    if "power_factor" in grid and not 0 < grid["power_factor"] <= 1:
        raise ConfigError("'grid.power_factor' must be within (0, 1].")

    chargers = config.get("chargers", {})
    if not isinstance(chargers, dict) or not chargers:
        raise ConfigError("'chargers' must be a non-empty mapping.")
    for name, charger in chargers.items():
        if not isinstance(charger, dict):
            raise ConfigError(f"'chargers.{name}' must be a mapping.")
        for key in ("power_kw", "cap_cost_bdt", "inst_cost_bdt", "daily_energy_kwh"):
            value = charger.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
                raise ConfigError(f"'chargers.{name}.{key}' must be finite and positive.")
        efficiency = charger.get("efficiency")
        if efficiency is not None and (not isinstance(efficiency, (int, float)) or not isfinite(efficiency) or not 0 < efficiency <= 1):
            raise ConfigError(f"'chargers.{name}.efficiency' must be within (0, 1].")

    return config


def load_config(config_path, settings_path=None):
    """Load a complete scenario, optionally applying a validated partial override YAML."""
    config = _read_yaml(config_path)
    if settings_path:
        overrides = _read_yaml(settings_path)
        _validate_keys(overrides, config)
        config = _deep_merge(config, overrides)
    return validate_config(config)
