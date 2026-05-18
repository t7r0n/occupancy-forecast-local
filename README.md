# Occupancy Forecast Local

Occupancy Forecast Local is an offline, privacy-first analytics toolkit for aggregated workplace occupancy counts. It forecasts half-hour occupancy, detects building-wide anomalies, and recommends capacity actions without using raw identity data, cameras, external APIs, or hosted model services.

`occupancy-forecast-local` favors explicit fixtures, deterministic checks, and reviewable artifacts over hidden services or live data.

## Use case

Offline privacy-first occupancy forecasting, anomaly detection, and capacity recommendation.

## Signal design

- Deterministic synthetic portfolio with floor, room-bank, doorway, sensor-health, and closure-planning fixtures.
- Dual-seasonality baseline using day-of-week and half-hour-of-day profiles.
- Quantile residual intervals for bounded, heavy-tailed occupancy.
- Joint multi-space anomaly detection that catches portfolio-wide events and sensor-health regressions.
- Capacity recommendation with seat-conflict risk and monthly savings estimate.
- DuckDB run store with a local file lock, JSONL tool loop, static light/dark dashboard, Markdown report cards, and demo pack export.

## Demo path

```bash
uv sync
uv run occupancy-forecast init-demo
uv run occupancy-forecast forecast --space-id floor-2
uv run occupancy-forecast anomaly
uv run occupancy-forecast recommend --space-id floor-4 --action close-fridays
uv run occupancy-forecast verify
uv run occupancy-forecast dashboard
uv run occupancy-forecast benchmark --iterations 100
```

## Files worth opening

- `outputs/summary.json` for headline metrics and gate status
- `outputs/reports.json` for per-case results
- `outputs/dashboard.html` for visual inspection
- `outputs/demo-pack.zip` or `outputs/demo_pack/` for portable review

## Build checks

```bash
uv run ruff check .
uv run pytest -q
uv run occupancy-forecast verify
uv run occupancy-forecast benchmark --iterations 100
```

## Data policy

The `occupancy-forecast-local` public surface is source, tests, lockfile, and docs. It does not need credentials, browser state, customer records, or hosted services.
