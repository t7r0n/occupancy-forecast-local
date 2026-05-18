# Occupancy Forecast Local

Occupancy Forecast Local is an offline, privacy-first analytics toolkit for aggregated workplace occupancy counts. It forecasts half-hour occupancy, detects building-wide anomalies, and recommends capacity actions without using raw identity data, cameras, external APIs, or hosted model services.

## Capabilities

- Deterministic synthetic portfolio with floor, room-bank, doorway, sensor-health, and closure-planning fixtures.
- Dual-seasonality baseline using day-of-week and half-hour-of-day profiles.
- Quantile residual intervals for bounded, heavy-tailed occupancy.
- Joint multi-space anomaly detection that catches portfolio-wide events and sensor-health regressions.
- Capacity recommendation with seat-conflict risk and monthly savings estimate.
- DuckDB run store with a local file lock, JSONL tool loop, static light/dark dashboard, Markdown report cards, and demo pack export.

## Quickstart

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

## Release Gate

```bash
uv run ruff check .
uv run pytest -q
uv run occupancy-forecast verify
uv run occupancy-forecast benchmark --iterations 100
```

Generated data, outputs, local databases, caches, and virtual environments are ignored by git.

