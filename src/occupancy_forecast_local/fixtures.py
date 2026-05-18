from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from occupancy_forecast_local.models import OccupancyPoint, PortfolioFixture, Space, SpaceKind, project_root


def fixtures_dir() -> Path:
    path = project_root() / "fixtures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def fixture_path() -> Path:
    return fixtures_dir() / "portfolio.json"


def _timestamp(start: datetime, bin_index: int) -> str:
    return (start + timedelta(minutes=30 * bin_index)).isoformat(timespec="minutes")


def generate_fixture(days: int = 98) -> PortfolioFixture:
    rng = np.random.default_rng(424242)
    spaces = [
        Space(id="floor-1", name="Building A Floor 1", kind=SpaceKind.FLOOR, capacity=180, monthly_cost=42000),
        Space(id="floor-2", name="Building A Floor 2", kind=SpaceKind.FLOOR, capacity=160, monthly_cost=39000),
        Space(id="floor-3", name="Building A Floor 3", kind=SpaceKind.FLOOR, capacity=150, monthly_cost=37000),
        Space(id="floor-4", name="Building A Floor 4", kind=SpaceKind.FLOOR, capacity=140, monthly_cost=31000),
        Space(id="booth-bank", name="Phone Booth Bank", kind=SpaceKind.ROOM_BANK, capacity=24, monthly_cost=7000),
        Space(id="entry-east", name="East Doorway", kind=SpaceKind.DOORWAY, capacity=220, monthly_cost=9000),
    ]
    start = datetime(2026, 1, 5, 0, 0)
    points: list[OccupancyPoint] = []
    event_day = 60
    sensor_drift_start = 74
    for day in range(days):
        dow = day % 7
        weekly = {0: 0.72, 1: 0.86, 2: 0.82, 3: 0.68, 4: 0.34, 5: 0.08, 6: 0.05}[dow]
        yearly = 1.0 + 0.12 * math.sin(day / days * math.tau)
        for half_hour in range(48):
            hour = half_hour / 2.0
            workday_curve = math.exp(-((hour - 11.0) ** 2) / 18.0) + 0.72 * math.exp(-((hour - 15.0) ** 2) / 12.0)
            workday_curve = min(workday_curve, 1.0)
            for space in spaces:
                if space.kind == SpaceKind.DOORWAY:
                    kind_factor = 0.48
                elif space.kind == SpaceKind.ROOM_BANK:
                    kind_factor = 0.36
                else:
                    kind_factor = 1.0
                floor_factor = 0.45 if space.id == "floor-4" and dow == 4 else 1.0
                expected = space.capacity * weekly * yearly * workday_curve * kind_factor * floor_factor
                count = max(0, int(rng.normal(expected, max(2.0, expected * 0.10))))
                event = None
                health = 0.99
                if day == event_day and 9 <= hour <= 17:
                    count = int(count * 0.18)
                    event = "snow-day"
                if space.id == "entry-east" and day >= sensor_drift_start and 8 <= hour <= 18:
                    count = int(count * 0.58)
                    health = 0.62
                    event = "sensor-drift"
                points.append(
                    OccupancyPoint(
                        timestamp=_timestamp(start, day * 48 + half_hour),
                        space_id=space.id,
                        count=count,
                        sensor_health=health,
                        injected_event=event,
                    )
                )
    return PortfolioFixture(spaces=spaces, points=points)


def write_demo_fixture(force: bool = False) -> Path:
    path = fixture_path()
    if force or not path.exists():
        fixture = generate_fixture()
        path.write_text(fixture.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_fixture() -> PortfolioFixture:
    if not fixture_path().exists():
        write_demo_fixture()
    return PortfolioFixture.model_validate_json(fixture_path().read_text(encoding="utf-8"))


def export_csv() -> Path:
    fixture = load_fixture()
    path = project_root() / "data" / "occupancy_points.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["timestamp,space_id,count,sensor_health,injected_event"]
    for point in fixture.points:
        rows.append(
            f"{point.timestamp},{point.space_id},{point.count},{point.sensor_health},{point.injected_event or ''}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path
