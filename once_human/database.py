from contextlib import contextmanager

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker

from once_human.config import config, GoogleSheetsDatabaseSettings


def get_mysql_engine():
    raise NotImplementedError


def get_google_sheets_engine():
    db_settings: GoogleSheetsDatabaseSettings = config.db
    engine = create_engine(
        "gsheets://",
        service_account_info=db_settings.service_account,
        catalog=db_settings.catalog(),
    )
    return engine


@contextmanager
def get_db():
    if config.db.dialect == "gsheets":
        engine = get_google_sheets_engine()
    elif config.db.dialect == "mysql":
        engine = get_mysql_engine()
    else:
        raise ValueError(f"unknown db dialect: {config.db.dialect}")

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
