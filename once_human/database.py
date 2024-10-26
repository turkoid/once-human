from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)

from once_human.config import config
from once_human.models import Base

engine = create_async_engine(config.db.url, echo=False)
AsyncSessionFactory = async_sessionmaker(
    engine,
    autoflush=False,
    expire_on_commit=False,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
