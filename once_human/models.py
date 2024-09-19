from sqlalchemy import (
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, DeclarativeBase, attribute_keyed_dict
from sqlalchemy.testing.schema import mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    discord_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    username: Mapped[str]
    display_name: Mapped[str]
    players: Mapped[list["Player"]] = relationship(back_populates="user")


class Player(Base):
    __tablenname__ = "player"
    __table_args__ = (UniqueConstraint("user_id", "is_default"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(foreign_key="user.id")
    user: Mapped["User"] = relationship(back_populates="players")
    name: Mapped[str]
    is_default: Mapped[bool]
    specializations: Mapped[dict[int, "PlayerSpecialization"]] = relationship(
        collection_class=attribute_keyed_dict("level")
    )


class Specialization(Base):
    __tablename__ = "specialization"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    levels: Mapped[str]
    type: Mapped[str]
    affected: Mapped[str]
    category: Mapped[str]
    identity: Mapped[str]
    description: Mapped[str]
    icon_url: Mapped[str]


class PlayerSpecialization(Base):
    __tablename__ = "player_specialization"
    __table_args__ = (
        UniqueConstraint("player_id", "level"),
        UniqueConstraint("player_id", "specialization_id"),
    )

    player_id: Mapped[int] = mapped_column(foreign_key="player.id")
    level: Mapped[int]
    specialization_id: Mapped[int] = mapped_column(foreign_key="specialization.id")
    specialization: Mapped["Specialization"] = relationship()
