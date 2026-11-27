import os

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    if os.environ.get("POSTGRES_HOST"):
        DATABASE_URL = URL.create(
            "postgresql+psycopg",
            username=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["POSTGRES_HOST"],
            database=os.environ["POSTGRES_DB"],
        )
    else:
        DATABASE_URL = "sqlite:///./mtg-shop.db"
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if str(DATABASE_URL).startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session():
    with SessionLocal() as session:
        yield session
