from contextlib import contextmanager
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker

from once_human.config import (
    config,
    GoogleSheetsDatabaseSettings,
    GenericDatabaseSettings,
)
from once_human.models import Base


def create_generic_database():
    db_settings: GenericDatabaseSettings = config.db
    dialect = db_settings.dialect
    if db_settings.driver != "default":
        dialect = f"{dialect}+{db_settings.driver}"
    connection_string = f"{dialect}://{db_settings.user}:{db_settings.password}@{db_settings.host}/{db_settings.name}"
    engine = create_engine(connection_string, echo=True)
    Base.metadata.create_all(bind=engine)
    session_local_class = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local_class()
    return db


def create_gsheets_database():
    db_settings: GoogleSheetsDatabaseSettings = config.db
    engine = create_engine(
        "gsheets://",
        service_account_info=db_settings.service_account,
        catalog=db_settings.catalog(),
    )
    session_local_class = sessionmaker(bind=engine)
    db = session_local_class()
    return db


@contextmanager
def get_db():
    if config.db.dialect == "gsheets":
        db = create_gsheets_database()
    else:
        db = create_generic_database()

    try:
        yield db
    finally:
        db.close()
