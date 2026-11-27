from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DeckFormat = Literal["Commander", "Standard", "Modern", "Pioneer", "Pauper", "Legacy", "Other"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CardInput(InputModel):
    name: str = Field(min_length=1, max_length=150)
    quantity: int = Field(gt=0, le=1000, strict=True)
    section: Literal["main", "sideboard", "commander"] = "main"


class DeckInput(InputModel):
    sku: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=150)
    format: DeckFormat
    price_rub: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    cards: list[CardInput] = Field(default_factory=list, max_length=300)

    @model_validator(mode="after")
    def unique_cards(self):
        keys = [(card.name.casefold(), card.section) for card in self.cards]
        if len(keys) != len(set(keys)):
            raise ValueError("Карта в одной секции должна быть указана одной строкой")
        return self


class DeckOutput(DeckInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stock: int


class MovementInput(InputModel):
    kind: Literal["receipt", "sale"]
    quantity: int = Field(gt=0, le=100000, strict=True)


class MovementOutput(MovementInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deck_id: int
    unit_price_rub: Decimal
    created_at: datetime


class Summary(BaseModel):
    deck_types: int
    decks_in_stock: int
    stock_value_rub: Decimal
    sold_quantity: int
    revenue_rub: Decimal
