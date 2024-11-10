import discord.ui

from once_human.bot.utils import InteractionCallback


class BaseButton(discord.ui.Button):
    def __init__(self, *, callback: InteractionCallback, **kwargs) -> None:
        super().__init__(**kwargs)
        self.callback = callback
