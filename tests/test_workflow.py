from __future__ import annotations

import json
import subprocess

from occupancy_forecast_local.dashboard import build_dashboard
from occupancy_forecast_local.engine import forecast, recommend, top_anomalies
from occupancy_forecast_local.fixtures import write_demo_fixture
from occupancy_forecast_local.models import ActionName
from occupancy_forecast_local.runner import export_demo_pack, run_suite, verify_outputs


def test_forecast_beats_naive_baseline() -> None:
    write_demo_fixture(force=True)
    report = forecast("floor-2")
    assert report.pass_forecast
    assert report.improvement >= 0.25
    assert report.interval_coverage_95 >= 0.80


def test_anomaly_detector_finds_snow_day_and_sensor_health() -> None:
    write_demo_fixture(force=True)
    rows = top_anomalies(limit=40)
    reasons = {row.reason for row in rows}
    assert "joint-occupancy-shift" in reasons
    assert "sensor-health-regression" in reasons


def test_capacity_recommendation_is_calibrated() -> None:
    write_demo_fixture(force=True)
    rec = recommend("floor-4", ActionName.CLOSE_FRIDAYS)
    assert rec.calibrated
    assert rec.monthly_savings > 10000
    assert rec.seat_conflict_probability <= 0.05


def test_suite_verifies() -> None:
    summary = run_suite()
    assert summary.pass_gates
    build_dashboard()
    ok, checks = verify_outputs()
    assert ok, checks


def test_dashboard_and_demo_pack() -> None:
    run_suite()
    dashboard = build_dashboard()
    html = dashboard.read_text(encoding="utf-8")
    assert "Occupancy Forecast Local" in html
    assert "Top Anomalies" in html
    assert "themeToggle" in html
    pack = export_demo_pack()
    assert (pack / "manifest.json").exists()


def test_jsonl_tool_loop() -> None:
    payload = {"tool": "forecast", "arguments": {"space_id": "floor-2"}}
    completed = subprocess.run(
        ["uv", "run", "--project", "elite_projects/occupancy-forecast-local", "occupancy-forecast", "tool-loop"],
        input=json.dumps(payload) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    assert report["space_id"] == "floor-2"
    assert report["pass_forecast"]

