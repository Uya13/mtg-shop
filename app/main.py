from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_session
from app.models import Deck, DeckCard, Movement
from app.schemas import (
    DeckFormat,
    DeckInput,
    DeckOutput,
    MovementInput,
    MovementOutput,
    Summary,
)


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="MTG Shop — учёт колод",
    description="Каталог готовых колод, поступления, продажи и остатки. Цены в рублях.",
    version="1.0.0",
    lifespan=lifespan,
)
Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app).expose(app)


def find_deck(session: Session, deck_id: int, lock: bool = False) -> Deck:
    query = select(Deck).where(Deck.id == deck_id)
    if lock:
        query = query.with_for_update()
    deck = session.scalar(query)
    if deck is None:
        raise HTTPException(404, "Колода не найдена")
    return deck


def save_deck(session: Session, deck: Deck):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Колода с таким артикулом уже существует") from None
    session.refresh(deck)
    return deck


@app.get("/health", tags=["Система"])
def health(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "База данных недоступна") from None
    return {"status": "ok", "database": "ok"}


@app.post("/decks", response_model=DeckOutput, status_code=201, tags=["Колоды"])
def create_deck(data: DeckInput, session: Session = Depends(get_session)):
    deck = Deck(**data.model_dump(exclude={"cards"}))
    deck.cards = [DeckCard(**card.model_dump()) for card in data.cards]
    session.add(deck)
    return save_deck(session, deck)


@app.get("/decks", response_model=list[DeckOutput], tags=["Колоды"])
def list_decks(
    format: DeckFormat | None = None,
    in_stock: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    query = select(Deck).order_by(Deck.id).limit(limit).offset(offset)
    if format:
        query = query.where(Deck.format == format)
    if in_stock:
        query = query.where(Deck.stock > 0)
    return session.scalars(query).all()


@app.get("/decks/{deck_id}", response_model=DeckOutput, tags=["Колоды"])
def get_deck(deck_id: int, session: Session = Depends(get_session)):
    return find_deck(session, deck_id)


@app.put("/decks/{deck_id}", response_model=DeckOutput, tags=["Колоды"])
def replace_deck(deck_id: int, data: DeckInput, session: Session = Depends(get_session)):
    deck = find_deck(session, deck_id, lock=True)
    for name, value in data.model_dump(exclude={"cards"}).items():
        setattr(deck, name, value)
    deck.cards = [DeckCard(**card.model_dump()) for card in data.cards]
    return save_deck(session, deck)


@app.delete("/decks/{deck_id}", status_code=204, tags=["Колоды"])
def delete_deck(deck_id: int, session: Session = Depends(get_session)):
    deck = find_deck(session, deck_id, lock=True)
    has_history = session.scalar(select(Movement.id).where(Movement.deck_id == deck_id).limit(1))
    if has_history:
        raise HTTPException(409, "Колоду с историей операций удалять нельзя")
    session.delete(deck)
    session.commit()
    return Response(status_code=204)


@app.post(
    "/decks/{deck_id}/movements",
    response_model=MovementOutput,
    status_code=201,
    tags=["Склад"],
)
def add_movement(deck_id: int, data: MovementInput, session: Session = Depends(get_session)):
    deck = find_deck(session, deck_id, lock=True)
    if data.kind == "sale":
        if deck.stock < data.quantity:
            raise HTTPException(409, "Недостаточно колод на складе")
        deck.stock -= data.quantity
    else:
        if deck.stock + data.quantity > 1000000:
            raise HTTPException(409, "Превышен допустимый остаток: 1000000")
        deck.stock += data.quantity
    movement = Movement(
        deck_id=deck_id, kind=data.kind, quantity=data.quantity, unit_price_rub=deck.price_rub
    )
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return movement


@app.get("/decks/{deck_id}/movements", response_model=list[MovementOutput], tags=["Склад"])
def list_movements(
    deck_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    find_deck(session, deck_id)
    return session.scalars(
        select(Movement)
        .where(Movement.deck_id == deck_id)
        .order_by(Movement.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@app.get("/summary", response_model=Summary, tags=["Склад"])
def summary(session: Session = Depends(get_session)):
    deck_types, quantity, value = session.execute(
        select(func.count(Deck.id), func.sum(Deck.stock), func.sum(Deck.stock * Deck.price_rub))
    ).one()
    sold, revenue = session.execute(
        select(
            func.sum(Movement.quantity), func.sum(Movement.quantity * Movement.unit_price_rub)
        ).where(Movement.kind == "sale")
    ).one()
    return Summary(
        deck_types=deck_types,
        decks_in_stock=quantity or 0,
        stock_value_rub=value or 0,
        sold_quantity=sold or 0,
        revenue_rub=revenue or 0,
    )
