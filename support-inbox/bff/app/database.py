from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_session_factory(database_url: str):
    engine = create_engine(database_url, future=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
