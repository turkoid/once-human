from __future__ import annotations

from typing import Annotated
from typing import Optional

from sqlalchemy import ARRAY
from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import ColumnElement
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import attribute_keyed_dict
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import registry
from sqlalchemy.orm import relationship


str_100 = Annotated[str, 100]


class Base(DeclarativeBase):
    registry = registry(type_annotation_map={str_100: String(100)})


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str_100] = mapped_column(unique=True)
    display_name: Mapped[str_100]
    players: Mapped[list[Player]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, order_by="Player.lower_name"
    )


class Player(Base):
    __tablename__ = "player"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"))
    user: Mapped[User] = relationship(back_populates="players")
    name: Mapped[str_100] = mapped_column()
    server_id: Mapped[Optional[int]] = mapped_column(ForeignKey("server.id"))
    server: Mapped[Server] = relationship()
    player_specializations: Mapped[dict[int, PlayerSpecialization]] = relationship(
        back_populates="player",
        collection_class=attribute_keyed_dict("level"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlayerSpecialization.level",
    )
    specializations: AssociationProxy[dict[int, Specialization]] = association_proxy(
        "player_specializations",
        "specialization",
    )

    @hybrid_property
    def lower_name(self) -> str:
        return self.name.lower()

    @lower_name.inplace.expression
    @classmethod
    def _lower_name(cls) -> ColumnElement[str]:
        return func.lower(cls.name)

    __table_args__ = (Index(f"{__tablename__}_user_id_lower_name_key", "user_id", func.lower(name), unique=True),)


scenario_specializations = Table(
    "scenario_specializations",
    Base.metadata,
    Column("scenario_id", ForeignKey("scenario.id", ondelete="CASCADE")),
    Column("specialization_id", ForeignKey("specialization.id", ondelete="CASCADE")),
)


class Specialization(Base):
    __tablename__ = "specialization"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str_100] = mapped_column()
    levels: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    type: Mapped[str_100]
    affected: Mapped[str_100]
    category: Mapped[str_100]
    identity: Mapped[str_100]
    description: Mapped[str]
    icon_url: Mapped[Optional[str]]
    scenarios: Mapped[list[Scenario]] = relationship(
        secondary=scenario_specializations,
        back_populates="specializations",
    )

    @hybrid_property
    def lower_name(self) -> str:
        return self.name.lower()

    @lower_name.inplace.expression
    @classmethod
    def _lower_name(cls) -> ColumnElement[str]:
        return func.lower(cls.name)

    __table_args__ = (Index(f"{__tablename__}_lower_name_key", func.lower(name), unique=True),)


class PlayerSpecialization(Base):
    __tablename__ = "player_specialization"
    __table_args__ = (
        UniqueConstraint("player_id", "level"),
        UniqueConstraint("player_id", "specialization_id"),
    )

    player_id: Mapped[int] = mapped_column(ForeignKey("player.id", ondelete="CASCADE"), primary_key=True)
    player: Mapped[Player] = relationship(back_populates="player_specializations")
    level: Mapped[int] = mapped_column(primary_key=True)
    specialization_id: Mapped[int] = mapped_column(ForeignKey("specialization.id"))
    specialization: Mapped[Specialization] = relationship()

    def __init__(self, level: int, specialization: Specialization):
        self.level = level
        self.specialization = specialization


class Scenario(Base):
    __tablename__ = "scenario"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str_100] = mapped_column()
    specializations: Mapped[list[Specialization]] = relationship(
        secondary=scenario_specializations,
        back_populates="scenarios",
        cascade="all, delete",
        passive_deletes=True,
        order_by="Specialization.levels, Specialization.lower_name",
    )
    servers: Mapped[list[Server]] = relationship(back_populates="scenario", order_by="Server.lower_name")

    @hybrid_property
    def lower_name(self) -> str:
        return self.name.lower()

    @lower_name.inplace.expression
    @classmethod
    def _lower_name(cls) -> ColumnElement[str]:
        return func.lower(cls.name)

    __table_args__ = (Index(f"{__tablename__}_lower_name_key", func.lower(name), unique=True),)


class Server(Base):
    __tablename__ = "server"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str_100] = mapped_column()
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id"))
    scenario: Mapped[Scenario] = relationship()

    @hybrid_property
    def lower_name(self) -> str:
        return self.name.lower()

    @lower_name.inplace.expression
    @classmethod
    def _lower_name(cls) -> ColumnElement[str]:
        return func.lower(cls.name)

    __table_args__ = (Index(f"{__tablename__}_lower_name_key", func.lower(name), unique=True),)
