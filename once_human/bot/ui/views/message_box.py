import functools
from typing import Awaitable
from typing import Callable
from typing import Optional

import discord

from once_human.bot.ui.views.base import BaseView
from once_human.bot.utils import response

type MessageBoxInteraction[T] = Callable[[T, str, discord.Interaction], Awaitable[None]]


class MessageBox(discord.ui.View):
    def __init__(
        self,
        parent_view: BaseView,
        *,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        buttons: dict[str, discord.ui.Button],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.parent_view = parent_view
        self.content = content
        self.embed = embed
        for button_id, button in buttons.items():
            button.callback = functools.partial(self.callback, button_id)
            button.disabled = False
            self.add_item(button)
        self._selected_button: Optional[str] = None

    async def callback(self, button_id: str, interaction: discord.Interaction) -> None:
        self.parent_view.interaction = interaction
        self._selected_button = button_id
        self.stop()

    async def show(self) -> str:
        await response(self.parent_view.interaction).edit_message(content=self.content, embed=self.embed, view=self)
        await self.wait()
        return self._selected_button
