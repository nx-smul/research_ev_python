"""Smoke tests for generated dashboard settings and API-key handling."""

from pathlib import Path

from src.config import load_config
from src.visualization.generate_responsive_map import build_responsive_map_html


def test_dashboard_displays_run_settings_without_embedding_map_key(tmp_path, base_dir):
    config = load_config(
        Path(base_dir) / "configs" / "default_config.yaml",
        Path(base_dir) / "configs" / "user_settings.yaml",
    )
    output = tmp_path / "dashboard.html"
    build_responsive_map_html(Path(base_dir), output, config=config)

    html = output.read_text(encoding="utf-8")
    assert "RUN_SETTINGS" in html
    assert '"budget_cap_bdt": 2500000000' in html
    assert '"service_radius_rmax_m": 5000.0' in html
    assert '"data_mode": "demo"' in html
    assert 'prefers-color-scheme: dark' in html
    assert 'setThemePreference' in html
    assert 'network-distance optimization' in html
    assert 'id="catchment-radius"' in html
    assert 'Illustrative Scenario Estimates (not utility telemetry)' in html
    assert "maptiler-key" in html
    assert "dhaka-evcs-maptiler-key" in html
    assert "MapTiler does not require" not in html
    assert "localStorage.setItem('dhaka-evcs-maptiler-key', key)" in html
    assert "API_KEY_PLACEHOLDER" not in html
