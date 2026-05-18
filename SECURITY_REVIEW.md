# Security Review

## Scope

Local CLI, deterministic synthetic aggregated-count fixtures, forecast engine, anomaly detector, capacity recommender, DuckDB run store, JSONL tool loop, static dashboard, and demo-pack export.

## Assessment

The application is offline and synthetic-only. It does not contact sensor APIs, workplace systems, identity systems, messaging systems, cloud services, or shell commands at runtime.

## Controls

- Inputs are aggregated counts only; there are no person-level identifiers.
- Fixtures and tool-loop inputs are parsed through Pydantic models.
- Space IDs, action names, and gates are closed local enumerations.
- DuckDB writes use parameterized inserts and a local file lock.
- Dashboard rendering uses Jinja autoescaping.
- Generated runtime state, outputs, caches, and virtual environments are ignored by git.

## Focused Scan Status

Completed for the public release.

## Results

- Static public-release hygiene scan: clean for non-public context, personal account strings, cloud credential markers, and common secret prefixes.
- Runtime surface scan: no network clients, dynamic code execution, unsafe deserialization, or shell execution in application code.
- Test-only process launch is limited to CLI regression coverage.
- Validation suite: `ruff`, `pytest`, `occupancy-forecast verify`, `occupancy-forecast benchmark --iterations 100`, and dashboard HTML/browser checks passed.
- DuckDB access is guarded by a local file lock to avoid parallel-run store contention.

## Residual Risk

This is a deterministic offline benchmark over synthetic aggregated-count data. It is not a production workplace operations system, financial calculator, or substitute for facilities review. Real deployments should add customer authorization, sensor data validation, cost-model review, and explicit privacy governance.
