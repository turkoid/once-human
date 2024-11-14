import discord.ui
from discord import Interaction

from once_human.bot.ui.views.base import BaseView
from once_human.bot.utils import response


class BaseModal(discord.ui.Modal):
    def __init__(self, parent_view: BaseView, *, title: str, text_inputs: list[discord.ui.TextInput]):
        super().__init__(title=title)
        self.parent_view = parent_view
        for item in text_inputs:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction) -> None:
        self.parent_view.interaction = interaction
        self.stop()

    async def show(self) -> None:
        await response(self.parent_view.interaction).send_modal(self)
        await self.wait()
