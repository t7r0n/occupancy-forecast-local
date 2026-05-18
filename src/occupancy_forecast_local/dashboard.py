# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, select_autoescape

from occupancy_forecast_local.models import SuiteSummary, project_root
from occupancy_forecast_local.runner import outputs_dir, run_suite

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Occupancy Forecast Local</title>
  <style>
    :root { color-scheme: light; --bg:#f8faf8; --panel:#fff; --text:#17201b; --muted:#617068; --line:#dce8e1; --blue:#3b6fd8; --green:#209668; --amber:#be7c22; --red:#ce4f4f; --track:#edf3ef; }
    html[data-theme="dark"] { color-scheme: dark; --bg:#101512; --panel:#18201c; --text:#edf7f1; --muted:#a8b6af; --line:#2c3933; --track:#26302c; }
    * { box-sizing:border-box; }
    body { margin:0; overflow-x:hidden; background:var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width:1200px; margin:0 auto; padding:32px 20px 48px; }
    header { display:flex; justify-content:space-between; gap:18px; align-items:end; margin-bottom:24px; }
    h1 { margin:0 0 8px; font-size:32px; line-height:1.08; letter-spacing:0; }
    h2 { margin:0 0 14px; font-size:21px; letter-spacing:0; }
    p { margin:0; color:var(--muted); }
    .actions { display:flex; gap:10px; align-items:center; }
    .pill,.toggle { border:1px solid var(--line); border-radius:999px; padding:8px 12px; background:var(--panel); color:var(--text); font:inherit; font-size:13px; white-space:nowrap; }
    .toggle { cursor:pointer; }
    .grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; }
    .metric span { color:var(--muted); font-size:13px; }
    .metric strong { display:block; margin-top:8px; font-size:28px; }
    .wide { grid-column:span 2; }
    .full { grid-column:1/-1; }
    .bar { display:grid; grid-template-columns:120px 1fr 72px; gap:12px; align-items:center; margin:12px 0; }
    .track { height:13px; border-radius:999px; background:var(--track); overflow:hidden; }
    .fill { height:100%; border-radius:999px; background:var(--blue); }
    .fill.good { background:var(--green); }
    .ok { color:var(--green); font-weight:700; }
    .table-wrap { width:100%; overflow-x:auto; }
    table { width:100%; border-collapse:collapse; margin-top:8px; font-size:14px; }
    th,td { text-align:left; border-bottom:1px solid var(--line); padding:11px 8px; vertical-align:top; }
    th { color:var(--muted); font-weight:600; }
    td, th, p, h1, h2, .bar span { overflow-wrap:anywhere; }
    @media (max-width:860px) { header { display:block; } .actions { margin-top:16px; } .grid { grid-template-columns:1fr; } .wide { grid-column:auto; } }
  </style>
  <script>
    const savedTheme = localStorage.getItem("occupancy-forecast-theme") || "light";
    document.documentElement.dataset.theme = savedTheme;
    function toggleTheme() {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("occupancy-forecast-theme", next);
      document.querySelector("#themeToggle").textContent = next === "dark" ? "Light" : "Dark";
    }
    window.addEventListener("DOMContentLoaded", () => {
      document.querySelector("#themeToggle").textContent =
        document.documentElement.dataset.theme === "dark" ? "Light" : "Dark";
    });
  </script>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Occupancy Forecast Local</h1>
      <p>Privacy-first forecasting, joint anomaly detection, and capacity recommendations on aggregated counts.</p>
    </div>
    <div class="actions"><button class="toggle" id="themeToggle" onclick="toggleTheme()" type="button">Dark</button><div class="pill">Run {{ summary.run_id }}</div></div>
  </header>
  <section class="grid">
    <div class="panel metric"><span>Forecast lift</span><strong>{{ "%.0f"|format(summary.forecast_improvement * 100) }}%</strong></div>
    <div class="panel metric"><span>Anomaly precision</span><strong>{{ "%.0f"|format(summary.anomaly_precision * 100) }}%</strong></div>
    <div class="panel metric"><span>Capacity</span><strong>{{ "OK" if summary.capacity_calibrated else "FAIL" }}</strong></div>
    <div class="panel metric"><span>Reports</span><strong>{{ summary.report_count }}</strong></div>
    <div class="panel wide forecast-bars">
      <h2>Forecast Improvement</h2>
      {% for report in forecasts %}
      <div class="bar"><span>{{ report.space_id }}</span><div class="track"><div class="fill good" style="width: {{ report.improvement * 100 }}%"></div></div><strong>{{ "%.0f"|format(report.improvement * 100) }}%</strong></div>
      {% endfor %}
    </div>
    <div class="panel wide">
      <h2>Capacity Recommendation</h2>
      <p>{{ recommendation.recommendation }}</p>
      <table><tbody>
        <tr><td>Monthly savings</td><td class="ok">${{ "%.0f"|format(recommendation.monthly_savings) }}</td></tr>
        <tr><td>Seat conflict risk</td><td class="ok">{{ "%.1f"|format(recommendation.seat_conflict_probability * 100) }}%</td></tr>
        <tr><td>Calibration</td><td class="ok">{{ "PASS" if recommendation.calibrated else "FAIL" }}</td></tr>
      </tbody></table>
    </div>
    <div class="panel full">
      <h2>Top Anomalies</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Timestamp</th><th>Space</th><th>Reason</th><th>Z</th><th>Joint</th><th>Health</th></tr></thead>
          <tbody>
          {% for row in anomalies[:12] %}
            <tr><td>{{ row.timestamp }}</td><td>{{ row.space_id }}</td><td>{{ row.reason }}</td><td>{{ row.z_score }}</td><td>{{ row.joint_score }}</td><td>{{ row.sensor_health }}</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </section>
</main>
</body>
</html>
"""


def build_dashboard() -> Path:
    if not (outputs_dir() / "summary.json").exists():
        run_suite()
    summary = SuiteSummary.model_validate_json((outputs_dir() / "summary.json").read_text(encoding="utf-8"))
    forecasts = json.loads((outputs_dir() / "forecasts.json").read_text(encoding="utf-8"))
    anomalies = json.loads((outputs_dir() / "anomalies.json").read_text(encoding="utf-8"))
    recommendation = json.loads((outputs_dir() / "recommendation.json").read_text(encoding="utf-8"))
    env = Environment(autoescape=select_autoescape(enabled_extensions=("html", "xml")), trim_blocks=True, lstrip_blocks=True)
    path = project_root() / "outputs" / "dashboard.html"
    path.write_text(
        env.from_string(TEMPLATE).render(
            summary=summary,
            forecasts=forecasts,
            anomalies=anomalies,
            recommendation=recommendation,
        ),
        encoding="utf-8",
    )
    return path
