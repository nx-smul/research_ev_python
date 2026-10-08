"""Tests for scenario configuration and user override settings."""

import pytest

from src.config import ConfigError, load_config


def test_user_settings_deep_merge_preserves_scenario_values(base_dir):
    config = load_config(
        base_dir + "/configs/default_config.yaml",
        base_dir + "/configs/user_settings.yaml",
    )
    assert config["optimization"]["budget_cap_bdt"] == 2_500_000_000
    assert config["optimization"]["max_open_stations"] == 10
    assert config["optimization"]["service_radius_rmax_m"] == 5000.0
    assert config["optimization"]["nsga2"]["crossover_probability"] == 0.85
    assert config["optimization"]["nsga2"]["mutation_probability"] == 0.15
    assert config["optimization"]["nsga2"]["random_seed"] == 42
    assert config["economic"]["discount_rate"] == 0.08
    assert "visualization" not in config


def test_override_rejects_unknown_keys(tmp_path, base_dir):
    override = tmp_path / "override.yaml"
    override.write_text("optimization:\n  max_station_limit: 10\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown settings key"):
        load_config(base_dir + "/configs/default_config.yaml", override)


@pytest.mark.parametrize("radius", [0, -5, float("inf"), float("nan")])
def test_override_rejects_invalid_service_radius(tmp_path, base_dir, radius):
    override = tmp_path / "override.yaml"
    value = ".nan" if radius != radius else (".inf" if radius == float("inf") else str(radius))
    override.write_text(f"optimization:\n  service_radius_rmax_m: {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="service_radius_rmax_m"):
        load_config(base_dir + "/configs/default_config.yaml", override)


def test_override_validates_station_bounds(tmp_path, base_dir):
    override = tmp_path / "override.yaml"
    override.write_text(
        "optimization:\n  min_open_stations: 8\n  max_open_stations: 4\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="cannot exceed"):
        load_config(base_dir + "/configs/default_config.yaml", override)


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("optimization:\n  lambda_impedance", "-0.1", "lambda_impedance"),
        ("economic:\n  alpha_delay_weight", "1.1", "alpha_delay_weight"),
    ],
)
def test_override_validates_model_tuning_ranges(tmp_path, base_dir, setting, value, message):
    override = tmp_path / "override.yaml"
    section, key = setting.split("\n  ")
    override.write_text(f"{section}\n  {key}: {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(base_dir + "/configs/default_config.yaml", override)


def test_missing_override_reports_file_error(tmp_path, base_dir):
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(base_dir + "/configs/default_config.yaml", tmp_path / "missing.yaml")
