from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class SpaceKind(StrEnum):
    FLOOR = "floor"
    ROOM_BANK = "room_bank"
    DOORWAY = "doorway"


class ActionName(StrEnum):
    CLOSE_FRIDAYS = "close-fridays"
    MERGE_ROOM_BANKS = "merge-room-banks"
    SENSOR_REVIEW = "sensor-review"


class Space(BaseModel):
    id: str
    name: str
    kind: SpaceKind
    capacity: int = Field(gt=0)
    monthly_cost: float = Field(gt=0)


class OccupancyPoint(BaseModel):
    timestamp: str
    space_id: str
    count: int = Field(ge=0)
    sensor_health: float = Field(ge=0.0, le=1.0)
    injected_event: str | None = None


class PortfolioFixture(BaseModel):
    spaces: list[Space]
    points: list[OccupancyPoint]


class ForecastPoint(BaseModel):
    timestamp: str
    space_id: str
    point: float
    p80_low: float
    p80_high: float
    p95_low: float
    p95_high: float


class ForecastReport(BaseModel):
    space_id: str
    horizon_bins: int
    pinball_loss: float
    baseline_loss: float
    improvement: float
    interval_coverage_95: float
    pass_forecast: bool
    points: list[ForecastPoint]


class AnomalyScore(BaseModel):
    timestamp: str
    space_id: str
    z_score: float
    joint_score: float
    sensor_health: float
    reason: str
    pass_detection: bool


class CapacityRecommendation(BaseModel):
    space_id: str
    action: ActionName
    monthly_savings: float
    seat_conflict_probability: float
    realized_conflict_probability: float
    calibrated: bool
    recommendation: str


class SuiteSummary(BaseModel):
    run_id: str
    forecast_improvement: float
    anomaly_precision: float
    capacity_calibrated: bool
    report_count: int
    pass_gates: bool


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

