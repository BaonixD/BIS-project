"""One rating per side of a completed ride (ADR 0013); tags are rows of their own table."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Final

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from taxi_service.database.base import Base, UtcDateTime

COMMENT_MAX_LENGTH: Final = 500
VALUE_MAX_LENGTH: Final = 16
RATEE_INDEX: Final = "ix_ride_ratings_ratee_id_stars"


class RaterRole(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"


class RatingTag(StrEnum):
    POLITE = "polite"
    CLEAN_CAR = "clean_car"
    SMOOTH_DRIVING = "smooth_driving"
    KNOWS_ROUTE = "knows_route"
    ON_TIME = "on_time"
    CLEAN = "clean"


# What each side may say about the other, in the order responses list them.
ALLOWED_TAGS: Final = {
    RaterRole.PASSENGER: (
        RatingTag.POLITE,
        RatingTag.CLEAN_CAR,
        RatingTag.SMOOTH_DRIVING,
        RatingTag.KNOWS_ROUTE,
    ),
    RaterRole.DRIVER: (RatingTag.ON_TIME, RatingTag.POLITE, RatingTag.CLEAN),
}


def _values_in(column: str, enum: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(f"'{member.value}'" for member in sorted(enum))})"


def _string_enum(enum: type[StrEnum]) -> Enum:
    """Stored as its value in a VARCHAR; the CHECK constraint is declared by the table."""
    return Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        length=VALUE_MAX_LENGTH,
        values_callable=lambda members: [member.value for member in members],
    )


class RideRating(Base):
    __tablename__ = "ride_ratings"
    __table_args__ = (
        CheckConstraint("stars BETWEEN 1 AND 5", name="stars_range"),
        CheckConstraint(_values_in("rater_role", RaterRole), name="rater_role"),
        CheckConstraint(
            f"comment IS NULL OR length(comment) BETWEEN 1 AND {COMMENT_MAX_LENGTH}",
            name="comment_length",
        ),
        CheckConstraint("rater_id <> ratee_id", name="not_self"),
        UniqueConstraint("ride_id", "rater_role"),
        # Averages of a user: GROUP BY ratee_id.
        Index(RATEE_INDEX, "ratee_id", "stars"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id"))
    rater_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    rater_role: Mapped[RaterRole] = mapped_column(_string_enum(RaterRole))
    ratee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    stars: Mapped[int]
    comment: Mapped[str | None] = mapped_column(String(COMMENT_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())

    tag_rows: Mapped[list["RideRatingTag"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def tags(self) -> list[RatingTag]:
        """In the fixed order of ``ALLOWED_TAGS`` for the rater's side."""
        chosen = {row.tag for row in self.tag_rows}
        return [tag for tag in ALLOWED_TAGS[self.rater_role] if tag in chosen]


class RideRatingTag(Base):
    __tablename__ = "ride_rating_tags"
    __table_args__ = (CheckConstraint(_values_in("tag", RatingTag), name="tag"),)

    rating_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ride_ratings.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[RatingTag] = mapped_column(_string_enum(RatingTag), primary_key=True)
