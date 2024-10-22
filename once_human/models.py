from sqlalchemy import (
    String,
    UniqueConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Table,
    Column,
)
from sqlalchemy.orm import (
    relationship,
    Mapped,
    DeclarativeBase,
    attribute_keyed_dict,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    players: Mapped[list["Player"]] = relationship(back_populates="user")


class Player(Base):
    __tablename__ = "player"
    __table_args__ = (UniqueConstraint("user_id", "is_default"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"), primary_key=True)
    user: Mapped["User"] = relationship(back_populates="players")
    name: Mapped[str] = mapped_column(primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("server.id"))
    server: Mapped["Server"] = relationship()
    is_default: Mapped[bool]
    specializations: Mapped[dict[int, "PlayerSpecialization"]] = relationship(
        collection_class=attribute_keyed_dict("level")
    )


scenario_specializations = Table(
    "scenario_specializations",
    Base.metadata,
    Column("scenario_id", ForeignKey("scenario.id")),
    Column("specialization_id", ForeignKey("specialization.id")),
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
    scenarios: Mapped[list["Scenario"]] = relationship(
        secondary=scenario_specializations, back_populates="specializations"
    )


class PlayerSpecialization(Base):
    __tablename__ = "player_specialization"
    __table_args__ = (
        UniqueConstraint("user_id", "name", "specialization_id"),
        ForeignKeyConstraint(["user_id", "name"], ["player.user_id", "player.name"]),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"), primary_key=True)
    name: Mapped[str] = mapped_column(primary_key=True)
    level: Mapped[int] = mapped_column(primary_key=True)
    specialization_id: Mapped[str] = mapped_column(ForeignKey("specialization.id"))
    specialization: Mapped["Specialization"] = relationship()


class Scenario(Base):
    __tablename__ = "scenario"
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    specializations: Mapped[list["Specialization"]] = relationship(
        secondary=scenario_specializations, back_populates="scenarios"
    )


class Server(Base):
    __tablename__ = "server"
    id: Mapped[str] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenario.id"))
    scenario: Mapped[Scenario] = relationship()
