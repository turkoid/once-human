from sqlalchemy import (
    String,
    UniqueConstraint,
    ForeignKey,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import relationship, Mapped, DeclarativeBase, attribute_keyed_dict
from sqlalchemy.testing.schema import mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    username: Mapped[str]
    display_name: Mapped[str]
    players: Mapped[list["Player"]] = relationship(back_populates="user")


class Player(Base):
    __tablename__ = "player"
    __table_args__ = (UniqueConstraint("user_id", "is_default"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"), primary_key=True)
    user: Mapped["User"] = relationship(back_populates="players")
    name: Mapped[str] = mapped_column(primary_key=True)
    is_default: Mapped[bool]
    specializations: Mapped[dict[int, "PlayerSpecialization"]] = relationship(
        collection_class=attribute_keyed_dict("level")
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
    is_active: Mapped[bool]


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
