from __future__ import annotations

import fcntl
import json
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from statistics import mean

import duckdb

from occupancy_forecast_local.engine import forecast, recommend, top_anomalies
from occupancy_forecast_local.fixtures import export_csv, load_fixture, write_demo_fixture
from occupancy_forecast_local.models import ActionName, ForecastReport, SuiteSummary, project_root


def runs_dir() -> Path:
    path = project_root() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_dir() -> Path:
    path = project_root() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return runs_dir() / "occupancy_forecast.duckdb"


@contextmanager
def store_lock() -> Iterator[None]:
    lock_path = project_root() / ".occupancy-forecast.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path()))
    con.execute(
        """
        create table if not exists suite_runs (
          run_id varchar,
          forecast_improvement double,
          anomaly_precision double,
          capacity_calibrated boolean,
          report_count integer,
          pass_gates boolean
        )
        """
    )
    return con


def run_suite() -> SuiteSummary:
    write_demo_fixture()
    export_csv()
    run_id = f"run-{time.time_ns():x}"[-18:]
    fixture = load_fixture()
    floor_spaces = [space.id for space in fixture.spaces if space.kind == "floor"]
    forecasts = [forecast(space_id) for space_id in floor_spaces]
    anomaly_rows = top_anomalies(limit=40)
    injected_detected = [
        row for row in anomaly_rows if row.reason in {"joint-occupancy-shift", "sensor-health-regression"}
    ]
    precision = round(len(injected_detected) / max(len(anomaly_rows), 1), 4)
    capacity = recommend("floor-4", ActionName.CLOSE_FRIDAYS)
    summary = SuiteSummary(
        run_id=run_id,
        forecast_improvement=round(float(mean(report.improvement for report in forecasts)), 4),
        anomaly_precision=precision,
        capacity_calibrated=capacity.calibrated,
        report_count=len(forecasts) + len(anomaly_rows) + 1,
        pass_gates=all(report.pass_forecast for report in forecasts)
        and precision >= 0.85
        and capacity.calibrated,
    )
    write_outputs(forecasts, anomaly_rows, capacity, summary)
    with store_lock():
        con = _connect()
        try:
            con.execute(
                "insert into suite_runs values (?, ?, ?, ?, ?, ?)",
                [
                    summary.run_id,
                    summary.forecast_improvement,
                    summary.anomaly_precision,
                    summary.capacity_calibrated,
                    summary.report_count,
                    summary.pass_gates,
                ],
            )
        finally:
            con.close()
    return summary


def write_outputs(forecasts: list[ForecastReport], anomalies: list, capacity, summary: SuiteSummary) -> None:
    out = outputs_dir()
    (out / "forecasts.json").write_text(
        json.dumps([report.model_dump(mode="json") for report in forecasts], indent=2),
        encoding="utf-8",
    )
    (out / "anomalies.json").write_text(
        json.dumps([row.model_dump(mode="json") for row in anomalies], indent=2),
        encoding="utf-8",
    )
    (out / "recommendation.json").write_text(capacity.model_dump_json(indent=2), encoding="utf-8")
    (out / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    (out / "report.md").write_text(render_report(forecasts, anomalies, capacity, summary), encoding="utf-8")


def render_report(forecasts: list[ForecastReport], anomalies: list, capacity, summary: SuiteSummary) -> str:
    lines = [
        "# Occupancy Forecast Report",
        "",
        f"- Run: `{summary.run_id}`",
        f"- Forecast improvement: {summary.forecast_improvement:.0%}",
        f"- Anomaly precision: {summary.anomaly_precision:.0%}",
        f"- Capacity calibrated: {summary.capacity_calibrated}",
        "",
        "| Space | Improvement | 95% Coverage | Status |",
        "| --- | ---: | ---: | --- |",
    ]
    for report in forecasts:
        lines.append(
            f"| {report.space_id} | {report.improvement:.0%} | "
            f"{report.interval_coverage_95:.0%} | {'PASS' if report.pass_forecast else 'FAIL'} |"
        )
    lines.extend(["", "## Top Anomalies", ""])
    for row in anomalies[:8]:
        lines.append(f"- `{row.timestamp}` `{row.space_id}` {row.reason}: z={row.z_score}, joint={row.joint_score}")
    lines.extend(["", "## Capacity Recommendation", "", capacity.recommendation])
    return "\n".join(lines) + "\n"


def verify_outputs() -> tuple[bool, dict[str, bool]]:
    summary_path = outputs_dir() / "summary.json"
    checks: dict[str, bool] = {
        "summary_exists": summary_path.exists(),
        "forecasts_exists": (outputs_dir() / "forecasts.json").exists(),
        "anomalies_exists": (outputs_dir() / "anomalies.json").exists(),
        "recommendation_exists": (outputs_dir() / "recommendation.json").exists(),
        "dashboard_exists": (outputs_dir() / "dashboard.html").exists(),
        "report_exists": (outputs_dir() / "report.md").exists(),
        "store_exists": db_path().exists(),
    }
    if not summary_path.exists():
        return False, checks
    summary = SuiteSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    forecasts = json.loads((outputs_dir() / "forecasts.json").read_text(encoding="utf-8"))
    anomalies = json.loads((outputs_dir() / "anomalies.json").read_text(encoding="utf-8"))
    rec = json.loads((outputs_dir() / "recommendation.json").read_text(encoding="utf-8"))
    checks.update(
        {
            "pass_gates": summary.pass_gates,
            "forecast_improvement": summary.forecast_improvement >= 0.25,
            "forecast_count": len(forecasts) >= 4,
            "anomaly_precision": summary.anomaly_precision >= 0.85,
            "snow_day_detected": any(row["reason"] == "joint-occupancy-shift" for row in anomalies),
            "sensor_health_detected": any(row["reason"] == "sensor-health-regression" for row in anomalies),
            "capacity_calibrated": bool(rec["calibrated"]),
            "privacy_fixture_only": (project_root() / "data" / "occupancy_points.csv").exists(),
        }
    )
    with store_lock():
        con = _connect()
        try:
            rows = con.execute("select count(*) from suite_runs where run_id = ?", [summary.run_id]).fetchone()[0]
        finally:
            con.close()
    checks["store_row_present"] = rows == 1
    return all(checks.values()), checks


def benchmark(iterations: int = 100) -> SuiteSummary:
    last = run_suite()
    for _ in range(iterations - 1):
        last = run_suite()
    return last


def export_demo_pack() -> Path:
    if not (outputs_dir() / "summary.json").exists():
        run_suite()
    pack = outputs_dir() / "demo_pack"
    if pack.exists():
        shutil.rmtree(pack)
    pack.mkdir(parents=True)
    for name in ["summary.json", "forecasts.json", "anomalies.json", "recommendation.json", "report.md"]:
        shutil.copy2(outputs_dir() / name, pack / name)
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "name": "occupancy-forecast-local-demo-pack",
                "files": sorted(str(path.relative_to(pack)) for path in pack.rglob("*") if path.is_file()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return pack
