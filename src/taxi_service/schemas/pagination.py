"""List pages (MVP_SPEC section 3): items, limit, offset, total."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class Page[ItemT](BaseModel):
    items: list[ItemT]
    limit: int
    offset: int
    total: int


@dataclass(frozen=True, slots=True)
class PageParams:
    limit: int = DEFAULT_LIMIT
    offset: int = 0


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Page size.")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


PageParamsDep = Annotated[PageParams, Depends(page_params)]
