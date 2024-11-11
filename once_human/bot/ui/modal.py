import discord.ui

from once_human.bot.utils import InteractionCallback


class BaseModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        on_submit: InteractionCallback,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_submit = on_submit
