from datetime import datetime

from pydantic import BaseModel, Field


class Achievement(BaseModel):
    code: str
    current: float
    target: float
    unlocked: bool
    xp: int = Field(description="Experience the achievement adds once unlocked.")
    sample_count: int | None = None
    minimum_samples: int | None = None


class Level(BaseModel):
    number: int
    level_start_xp: int
    next_level_xp: int | None = Field(description="Null on the top level.")


class Streak(BaseModel):
    """Weeks in a row (Asia/Almaty, Monday first) with at least one completed ride."""

    current_weeks: int
    best_weeks: int
    active_this_week: bool


class WeeklyQuest(BaseModel):
    code: str
    current: int
    target: int
    completed: bool
    reward_xp: int = Field(description="Added for every week the target was reached.")
    ends_at: datetime


class Progress(BaseModel):
    completed_rides: int
    xp: int
    level: Level
    streak: Streak
    weekly_quest: WeeklyQuest
    achievements: list[Achievement]
