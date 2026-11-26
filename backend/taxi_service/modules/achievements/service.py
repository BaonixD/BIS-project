"""Progress computed from completed rides and ratings: nothing is stored, so it never drifts."""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Final

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.database.session import read_transaction
from taxi_service.modules.achievements.schemas import (
    Achievement,
    Level,
    Progress,
    Streak,
    WeeklyQuest,
)
from taxi_service.modules.payments.models import Payment, PaymentMethod
from taxi_service.modules.ratings.models import RideRating
from taxi_service.modules.rides.models import Ride
from taxi_service.modules.rides.states import RideStatus
from taxi_service.modules.rides.tariffs import Tariff
from taxi_service.modules.users.models import UserRole

ALMATY: Final = timezone(timedelta(hours=5))
WEEK: Final = timedelta(days=7)
LEVEL_THRESHOLDS: Final = (0, 300, 800, 1500, 2500, 4000, 6000, 9000)
RIDE_XP: Final = 100
KM_XP: Final = 2
RATING_XP: Final = 20
ACHIEVEMENT_XP: Final = 50
QUEST_XP: Final = 150
WEEKLY_TARGET: Final = {UserRole.PASSENGER: 3, UserRole.DRIVER: 10}
PREMIUM_TARIFFS: Final = frozenset({Tariff.COMFORT_PLUS, Tariff.BUSINESS})


@dataclass(frozen=True)
class Trip:
    at: datetime
    distance_m: int
    tariff: Tariff
    kaspi: bool
    bonus: bool

    @property
    def at_night(self) -> bool:
        hour = self.at.astimezone(ALMATY).hour
        return hour >= 22 or hour < 5


@dataclass(frozen=True)
class Ratings:
    """Given by a passenger; received by a driver (``five_stars`` and the average)."""

    count: int
    total: int
    five_stars: int


@dataclass(frozen=True)
class Stats:
    trips: list[Trip]
    ratings: Ratings
    streak: Streak

    @property
    def rides(self) -> int:
        return len(self.trips)

    @property
    def km(self) -> float:
        return round(sum(trip.distance_m for trip in self.trips) / 1000, 1)

    def count(self, predicate: str) -> int:
        return sum(bool(getattr(trip, predicate)) for trip in self.trips)


async def progress(db: AsyncSession, user_id: uuid.UUID, role: UserRole, now: datetime) -> Progress:
    async with read_transaction(db):
        trips = [] if role is UserRole.ADMIN else await _trips(db, user_id, role)
        ratings = await _ratings(db, user_id, role)
    this_week = week_start(now)
    weeks = Counter(week_start(trip.at) for trip in trips)
    stats = Stats(trips, ratings, streak(set(weeks), this_week))
    goals = _goals(stats, role)
    quest = _weekly_quest(role, weeks[this_week], this_week)
    quest_weeks = sum(count >= quest.target for count in weeks.values())
    xp = (
        stats.rides * RIDE_XP
        + int(stats.km) * KM_XP
        + _rating_points(ratings, role) * RATING_XP
        + sum(goal.xp for goal in goals if goal.unlocked)
        + quest_weeks * QUEST_XP
    )
    return Progress(
        completed_rides=stats.rides,
        xp=xp,
        level=level_for(xp),
        streak=stats.streak,
        weekly_quest=quest,
        achievements=goals,
    )


def week_start(moment: datetime) -> date:
    local = moment.astimezone(ALMATY).date()
    return local - timedelta(days=local.weekday())


def streak(weeks: set[date], this_week: date) -> Streak:
    current, cursor = 0, this_week if this_week in weeks else this_week - WEEK
    while cursor in weeks:
        current, cursor = current + 1, cursor - WEEK
    best = 0
    for week in weeks:
        if week - WEEK not in weeks:
            length = 1
            while week + WEEK * length in weeks:
                length += 1
            best = max(best, length)
    return Streak(current_weeks=current, best_weeks=best, active_this_week=this_week in weeks)


def level_for(xp: int) -> Level:
    number = sum(xp >= threshold for threshold in LEVEL_THRESHOLDS)
    upcoming = LEVEL_THRESHOLDS[number] if number < len(LEVEL_THRESHOLDS) else None
    return Level(number=number, level_start_xp=LEVEL_THRESHOLDS[number - 1], next_level_xp=upcoming)


async def _trips(db: AsyncSession, user_id: uuid.UUID, role: UserRole) -> list[Trip]:
    owner = Ride.driver_id if role is UserRole.DRIVER else Ride.passenger_id
    rows = await db.execute(
        select(
            func.coalesce(Ride.completed_at, Ride.created_at),
            Ride.distance_m,
            Ride.tariff,
            Payment.method,
            Ride.bonus_kzt,
        )
        .outerjoin(Payment, Payment.ride_id == Ride.id)
        .where(owner == user_id, Ride.status == RideStatus.COMPLETED)
    )
    return [
        Trip(
            at=at if at.tzinfo else at.replace(tzinfo=UTC),
            distance_m=distance,
            tariff=tariff,
            kaspi=method is PaymentMethod.KASPI_LINK,
            bonus=bonus > 0,
        )
        for at, distance, tariff, method, bonus in rows
    ]


async def _ratings(db: AsyncSession, user_id: uuid.UUID, role: UserRole) -> Ratings:
    if role is UserRole.ADMIN:
        return Ratings(0, 0, 0)
    side = RideRating.rater_id if role is UserRole.PASSENGER else RideRating.ratee_id
    count, total, five = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(RideRating.stars), 0),
                func.coalesce(func.sum(case((RideRating.stars == 5, 1), else_=0)), 0),
            )
            .join(Ride, Ride.id == RideRating.ride_id)
            .where(side == user_id, Ride.status == RideStatus.COMPLETED)
        )
    ).one()
    return Ratings(count, total, five)


def _rating_points(ratings: Ratings, role: UserRole) -> int:
    return ratings.count if role is UserRole.PASSENGER else ratings.five_stars


def _weekly_quest(role: UserRole, rides: int, this_week: date) -> WeeklyQuest:
    target = WEEKLY_TARGET.get(role, WEEKLY_TARGET[UserRole.PASSENGER])
    ends = datetime.combine(this_week + WEEK, time(), ALMATY).astimezone(UTC)
    return WeeklyQuest(
        code="weekly_rides",
        current=rides,
        target=target,
        completed=rides >= target,
        reward_xp=QUEST_XP,
        ends_at=ends,
    )


def _goal(code: str, current: float, target: float, **extra: int) -> Achievement:
    unlocked = current >= target
    return Achievement(
        code=code, current=current, target=target, unlocked=unlocked, xp=ACHIEVEMENT_XP, **extra
    )


def _goals(stats: Stats, role: UserRole) -> list[Achievement]:
    if role is UserRole.PASSENGER:
        return _passenger_goals(stats)
    if role is UserRole.DRIVER:
        return _driver_goals(stats)
    return []


def _passenger_goals(stats: Stats) -> list[Achievement]:
    premium = sum(trip.tariff in PREMIUM_TARIFFS for trip in stats.trips)
    return [
        _goal("first_ride", stats.rides, 1),
        _goal("regular_passenger", stats.rides, 5),
        _goal("loyal_passenger", stats.rides, 25),
        _goal("feedback", stats.ratings.count, 3),
        _goal("explorer", stats.km, 50),
        _goal("night_owl", stats.count("at_night"), 1),
        _goal("premium", premium, 1),
        _goal("kaspi_fan", stats.count("kaspi"), 3),
        _goal("bonus_saver", stats.count("bonus"), 1),
        _goal("streak_keeper", stats.streak.best_weeks, 4),
    ]


def _driver_goals(stats: Stats) -> list[Achievement]:
    ratings = stats.ratings
    average = ratings.total / ratings.count if ratings.count else 0
    high_rating = _goal("high_rating", average, 4.8, sample_count=ratings.count, minimum_samples=5)
    high_rating.unlocked = ratings.count >= 5 and ratings.total * 10 >= ratings.count * 48
    return [
        _goal("first_order", stats.rides, 1),
        _goal("experienced_driver", stats.rides, 10),
        _goal("road_master", stats.rides, 50),
        high_rating,
        _goal("marathon", stats.km, 300),
        _goal("night_shift", stats.count("at_night"), 5),
        _goal("five_stars", ratings.five_stars, 10),
        _goal("streak_keeper", stats.streak.best_weeks, 4),
    ]
