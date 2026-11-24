from pydantic import BaseModel, Field


class BonusBalance(BaseModel):
    balance_kzt: int = Field(description="1 bonus = 1 KZT.")
    earn_percent: int = Field(description="Share of the money paid for a completed ride.")
    max_share_percent: int = Field(description="Bonuses pay at most this share of a ride.")
