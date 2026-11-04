import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Final, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from taxi_service.modules.ratings.models import (
    ALLOWED_TAGS,
    COMMENT_MAX_LENGTH,
    RaterRole,
    RatingTag,
    RideRating,
)
from taxi_service.modules.ratings.records import RatingSummary

# Line breaks and tabs are kept in a comment; other control characters are refused.
_ALLOWED_CONTROLS: Final = frozenset("\n\t")


def _comment(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if any(unicodedata.category(char) == "Cc" and char not in _ALLOWED_CONTROLS for char in text):
        raise ValueError("Comment must not contain control characters")
    if len(text) > COMMENT_MAX_LENGTH:
        raise ValueError(f"Comment must have at most {COMMENT_MAX_LENGTH} characters")
    return text or None


Comment = Annotated[
    str | None,
    AfterValidator(_comment),
    Field(
        description=f"Up to {COMMENT_MAX_LENGTH} characters after trimming; blank is null.",
        examples=["Thank you!"],
    ),
]


class RatingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stars: int = Field(strict=True, ge=1, le=5, examples=[5])
    tags: list[RatingTag] = Field(
        default_factory=list,
        description="The passenger about the driver: "
        f"{', '.join(ALLOWED_TAGS[RaterRole.PASSENGER])}; the driver about the passenger: "
        f"{', '.join(ALLOWED_TAGS[RaterRole.DRIVER])}. Repeats are dropped.",
    )
    comment: Comment = None


class MyRating(BaseModel):
    stars: int
    tags: list[RatingTag]
    comment: str | None

    @classmethod
    def build(cls, rating: RideRating) -> Self:
        return cls(stars=rating.stars, tags=rating.tags, comment=rating.comment)


class RatingResponse(MyRating):
    ride_id: uuid.UUID
    rater_role: RaterRole
    created_at: datetime

    @classmethod
    def build(cls, rating: RideRating) -> Self:
        return cls(
            ride_id=rating.ride_id,
            rater_role=rating.rater_role,
            stars=rating.stars,
            tags=rating.tags,
            comment=rating.comment,
            created_at=rating.created_at,
        )


class RatingSummaryResponse(BaseModel):
    """Average stars received (two decimals), null without ratings."""

    average: float | None
    count: int

    @classmethod
    def build(cls, summary: RatingSummary) -> Self:
        return cls(average=summary.average, count=summary.count)
