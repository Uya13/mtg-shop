from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Deck(Base):
    __tablename__ = "decks"
    __table_args__ = (
        CheckConstraint("stock >= 0"),
        CheckConstraint("price_rub >= 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    format: Mapped[str] = mapped_column(String(30))
    price_rub: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    cards: Mapped[list["DeckCard"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="DeckCard.id"
    )


class DeckCard(Base):
    __tablename__ = "deck_cards"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[int]
    section: Mapped[str] = mapped_column(String(20))


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int]
    unit_price_rub: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
