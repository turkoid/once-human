from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Table,
    Column,
    ForeignKeyConstraint,
)
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import (
    relationship,
    Mapped,
    DeclarativeBase,
    mapped_column,
    attribute_keyed_dict,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    players: Mapped[list[Player]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Player(Base):
    __tablename__ = "player"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    user: Mapped[User] = relationship(back_populates="players")
    name: Mapped[str] = mapped_column(primary_key=True)
    server_id: Mapped[Optional[str]] = mapped_column(ForeignKey("server.id"))
    server: Mapped[Server] = relationship()
    player_specializations: Mapped[dict[int, PlayerSpecialization]] = relationship(
        back_populates="player",
        collection_class=attribute_keyed_dict("level"),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    specializations: AssociationProxy[dict[int, Specialization]] = association_proxy(
        "player_specializations",
        "specialization",
        creator=lambda k, v: PlayerSpecialization(level=k, specialization=v),
    )


scenario_specializations = Table(
    "scenario_specializations",
    Base.metadata,
    Column("scenario_id", ForeignKey("scenario.id", ondelete="CASCADE")),
    Column("specialization_id", ForeignKey("specialization.id", ondelete="CASCADE")),
)


class Specialization(Base):
    __tablename__ = "specialization"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    levels: Mapped[str]
    type: Mapped[str]
    affected: Mapped[str]
    category: Mapped[str]
    identity: Mapped[str]
    description: Mapped[str]
    icon_url: Mapped[str]
    scenarios: Mapped[list[Scenario]] = relationship(
        secondary=scenario_specializations, back_populates="specializations"
    )


class PlayerSpecialization(Base):
    __tablename__ = "player_specialization"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "player_name"],
            ["player.user_id", "player.name"],
            ondelete="CASCADE",
        ),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True)
    player_name: Mapped[str] = mapped_column(primary_key=True)
    player: Mapped[Player] = relationship(back_populates="player_specializations")
    level: Mapped[int]
    specialization_id: Mapped[str] = mapped_column(ForeignKey("specialization.id"))
    specialization: Mapped[Specialization] = relationship()

    def __init__(self, level: int, specialization: Specialization):
        self.level = level
        self.specialization = specialization


class Scenario(Base):
    __tablename__ = "scenario"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    specializations: Mapped[list[Specialization]] = relationship(
        secondary=scenario_specializations,
        back_populates="scenarios",
        cascade="all, delete",
        passive_deletes=True,
    )
    servers: Mapped[list[Server]] = relationship(back_populates="scenario")


class Server(Base):
    __tablename__ = "server"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenario.id"))
    scenario: Mapped[Scenario] = relationship()
