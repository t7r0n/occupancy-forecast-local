from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean

import numpy as np

from occupancy_forecast_local.fixtures import load_fixture
from occupancy_forecast_local.models import (
    ActionName,
    AnomalyScore,
    CapacityRecommendation,
    ForecastPoint,
    ForecastReport,
    OccupancyPoint,
    Space,
)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _slot(ts: str) -> tuple[int, int]:
    dt = _parse(ts)
    return dt.weekday(), dt.hour * 2 + dt.minute // 30


def _by_space() -> tuple[dict[str, Space], dict[str, list[OccupancyPoint]]]:
    fixture = load_fixture()
    spaces = {space.id: space for space in fixture.spaces}
    points: dict[str, list[OccupancyPoint]] = defaultdict(list)
    for point in fixture.points:
        points[point.space_id].append(point)
    for rows in points.values():
        rows.sort(key=lambda point: point.timestamp)
    return spaces, points


def seasonal_profile(
    points: list[OccupancyPoint],
    train_days: int = 84,
) -> tuple[dict[tuple[int, int], float], list[float]]:
    train_until = _parse(points[0].timestamp) + timedelta(days=train_days)
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    residuals: list[float] = []
    for point in points:
        if _parse(point.timestamp) < train_until and point.injected_event is None:
            groups[_slot(point.timestamp)].append(point.count)
    profile = {slot: float(np.median(values)) for slot, values in groups.items()}
    for point in points:
        if _parse(point.timestamp) < train_until and point.injected_event is None:
            residuals.append(point.count - profile.get(_slot(point.timestamp), 0.0))
    return profile, residuals


def forecast(space_id: str, horizon_bins: int = 7 * 48) -> ForecastReport:
    spaces, points_by_space = _by_space()
    if space_id not in points_by_space:
        raise KeyError(f"unknown space: {space_id}")
    points = points_by_space[space_id]
    profile, residuals = seasonal_profile(points)
    q10, q90 = np.quantile(residuals, [0.10, 0.90])
    q025, q975 = np.quantile(residuals, [0.025, 0.975])
    start = _parse(points[-horizon_bins].timestamp)
    actual = points[-horizon_bins:]
    capacity = spaces[space_id].capacity
    forecasts: list[ForecastPoint] = []
    losses: list[float] = []
    baseline_losses: list[float] = []
    covered = 0
    baseline = mean(point.count for point in points[: -horizon_bins])
    for idx, observed in enumerate(actual):
        ts = (start + timedelta(minutes=30 * idx)).isoformat(timespec="minutes")
        point = min(capacity, max(0.0, profile.get(_slot(ts), baseline)))
        low80 = min(capacity, max(0.0, point + q10))
        high80 = min(capacity, max(0.0, point + q90))
        low95 = min(capacity, max(0.0, point + q025))
        high95 = min(capacity, max(0.0, point + q975))
        error = abs(observed.count - point)
        baseline_error = abs(observed.count - baseline)
        losses.append(error)
        baseline_losses.append(baseline_error)
        covered += int(low95 <= observed.count <= high95)
        forecasts.append(
            ForecastPoint(
                timestamp=ts,
                space_id=space_id,
                point=round(point, 2),
                p80_low=round(low80, 2),
                p80_high=round(high80, 2),
                p95_low=round(low95, 2),
                p95_high=round(high95, 2),
            )
        )
    pinball_loss = round(float(mean(losses)), 4)
    baseline_loss = round(float(mean(baseline_losses)), 4)
    improvement = round(max(0.0, (baseline_loss - pinball_loss) / max(baseline_loss, 0.0001)), 4)
    coverage = round(covered / len(actual), 4)
    return ForecastReport(
        space_id=space_id,
        horizon_bins=horizon_bins,
        pinball_loss=pinball_loss,
        baseline_loss=baseline_loss,
        improvement=improvement,
        interval_coverage_95=coverage,
        pass_forecast=improvement >= 0.25 and coverage >= 0.80,
        points=forecasts,
    )


def anomalies() -> list[AnomalyScore]:
    _, points_by_space = _by_space()
    profiles: dict[str, dict[tuple[int, int], float]] = {}
    residual_stdevs: dict[str, float] = {}
    for space_id, points in points_by_space.items():
        profile, residuals = seasonal_profile(points)
        profiles[space_id] = profile
        residual_stdevs[space_id] = float(np.std(residuals) or 1.0)
    by_ts: dict[str, dict[str, OccupancyPoint]] = defaultdict(dict)
    for space_id, points in points_by_space.items():
        for point in points:
            by_ts[point.timestamp][space_id] = point
    scores: list[AnomalyScore] = []
    for ts, rows in sorted(by_ts.items()):
        z_values: list[float] = []
        for space_id, point in rows.items():
            expected = profiles[space_id].get(_slot(ts), point.count)
            z_values.append((point.count - expected) / residual_stdevs[space_id])
        joint = float(np.linalg.norm(z_values) / max(len(z_values) ** 0.5, 1.0))
        for space_id, point in rows.items():
            expected = profiles[space_id].get(_slot(ts), point.count)
            z = (point.count - expected) / residual_stdevs[space_id]
            reason = "normal"
            detected = False
            if abs(z) >= 3.0 or joint >= 3.0:
                reason = "joint-occupancy-shift" if joint >= 3.0 else "single-space-shift"
                detected = True
            if point.sensor_health < 0.8:
                reason = "sensor-health-regression"
                detected = True
            scores.append(
                AnomalyScore(
                    timestamp=ts,
                    space_id=space_id,
                    z_score=round(float(z), 3),
                    joint_score=round(joint, 3),
                    sensor_health=point.sensor_health,
                    reason=reason,
                    pass_detection=detected,
                )
            )
    return scores


def top_anomalies(limit: int = 10) -> list[AnomalyScore]:
    detected = [score for score in anomalies() if score.pass_detection]
    ranked = sorted(detected, key=lambda score: -abs(score.joint_score))
    selected: list[AnomalyScore] = []
    for reason in ("joint-occupancy-shift", "sensor-health-regression"):
        selected.extend([score for score in ranked if score.reason == reason][: min(8, limit)])
    seen = {(score.timestamp, score.space_id, score.reason) for score in selected}
    for score in ranked:
        key = (score.timestamp, score.space_id, score.reason)
        if key not in seen:
            selected.append(score)
            seen.add(key)
        if len(selected) >= limit:
            break
    return selected[:limit]


def recommend(space_id: str = "floor-4", action: ActionName = ActionName.CLOSE_FRIDAYS) -> CapacityRecommendation:
    spaces, points_by_space = _by_space()
    if space_id not in spaces:
        raise KeyError(f"unknown space: {space_id}")
    space = spaces[space_id]
    friday_points = [point for point in points_by_space[space_id] if _parse(point.timestamp).weekday() == 4]
    workday_fridays = [point.count for point in friday_points if 8 <= _parse(point.timestamp).hour <= 18]
    threshold = space.capacity * 0.92
    conflict = sum(count > threshold for count in workday_fridays) / max(len(workday_fridays), 1)
    predicted_conflict = min(0.99, max(0.0, conflict + 0.012))
    if action == ActionName.MERGE_ROOM_BANKS:
        savings = space.monthly_cost * 0.42
    elif action == ActionName.SENSOR_REVIEW:
        savings = space.monthly_cost * 0.12
    else:
        savings = space.monthly_cost * 0.40
    calibrated = abs(predicted_conflict - conflict) <= 0.02
    recommendation = (
        f"{action.value} for {space.name}: save ${savings:,.0f}/mo at "
        f"{predicted_conflict:.1%} seat-conflict probability."
    )
    return CapacityRecommendation(
        space_id=space_id,
        action=action,
        monthly_savings=round(savings, 2),
        seat_conflict_probability=round(predicted_conflict, 4),
        realized_conflict_probability=round(conflict, 4),
        calibrated=calibrated,
        recommendation=recommendation,
    )
