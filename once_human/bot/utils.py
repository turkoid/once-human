from collections.abc import Awaitable
from collections.abc import Callable

import discord
from discord import InteractionResponse

from once_human.models import Base


type InteractionCallback[T] = Callable[[T, discord.Interaction], Awaitable[None]]
type DatabaseModel[T: Base, R] = Callable[[T], R]

ZERO_WIDTH_SPACE = "\u200b"


def response(interaction: discord.Interaction) -> InteractionResponse:
    # just a way to avoid that bad type hinting of discord.py
    return interaction.response
