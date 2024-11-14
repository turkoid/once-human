import abc
import asyncio
import functools
import inspect
from abc import abstractmethod
from typing import Awaitable
from typing import Callable
from typing import Optional
from typing import Self

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from once_human.bot.ui.embed import Error
from once_human.bot.ui.embed import TimedEmbed
from once_human.bot.utils import InteractionCallback
from once_human.bot.utils import response

type Layout = list[list[discord.ui.Item]]
type DecoratedCallback[**P] = Callable[[P], Awaitable[None]]


def intercept_interaction(orig_func: DecoratedCallback) -> InteractionCallback:
    is_inner_func = len(inspect.signature(orig_func).parameters) == 0

    @functools.wraps(orig_func)
    async def set_interaction(*args) -> None:
        func = orig_func
        if inspect.isclass(args[0]):
            func = functools.partial(func, args[0])
            args = args[1:]
        view: BaseView = args[0]
        interaction = args[-1]
        view.interaction = interaction
        if is_inner_func:
            result = await func()
        else:
            args = args[:-1]
            result = await func(*args)
        return result

    return set_interaction


class BaseView(discord.ui.View, abc.ABC):
    def __init__(self, interaction: discord.Interaction, session: AsyncSession, **kwargs) -> None:
        super().__init__(**kwargs)
        self.interaction = interaction
        self.session = session
        self._static_embeds: list[discord.Embed] = []
        self._timed_embeds: list[discord.Embed] = []

    @property
    def _embeds(self) -> list[discord.Embed]:
        return self._static_embeds + self._timed_embeds

    @classmethod
    async def create(
        cls, interaction: discord.Interaction, session: AsyncSession, *, timeout: Optional[float] = None, **kwargs
    ) -> Self:
        view = cls(interaction, session, timeout=timeout, **kwargs)
        await view.load_database_objects()
        view.build_ui()
        view.update_view()
        return view

    async def load_database_objects(self) -> None:
        pass

    @abstractmethod
    def build_ui(self) -> None:
        pass

    def add_layout(self, layout: Layout) -> None:
        for row, items in enumerate(layout):
            for item in items:
                item.row = row
                self.add_item(item)

    @abstractmethod
    def update_view(self) -> None:
        pass

    async def _send_timed_embeds(self, embeds: list[discord.Embed], duration: float) -> None:
        await asyncio.sleep(duration)
        updated_embeds = []
        for embed in self._timed_embeds:
            if any(em for em in embeds if em is embed):
                continue
            updated_embeds.append(embed)
        if len(self._timed_embeds) != len(updated_embeds):
            self._timed_embeds = updated_embeds
            await self.refresh()

    async def interact(
        self,
        *,
        view: Optional[discord.ui.View] = None,
        content: Optional[str] = None,
        embeds: Optional[list[discord.Embed | TimedEmbed]] = None,
    ) -> None:
        if self.is_finished():
            return
        timed_embeds: dict[float, list[discord.Embed]] = {}
        if view and view is not self:
            self._static_embeds = []
            self._timed_embeds = []
        elif embeds is not None and len(embeds) == 0:
            self._static_embeds = []
        elif embeds:
            static_embeds = []
            for embed in embeds:
                if isinstance(embed, discord.Embed):
                    static_embeds.append(embed)
                else:
                    embed: TimedEmbed = embed
                    timed_embeds.setdefault(embed.duration, []).append(embed.embed)
                    self._timed_embeds.append(embed.embed)
            if static_embeds:
                self._static_embeds = static_embeds
        await response(self.interaction).edit_message(content=content, embeds=self._embeds, view=view or self)
        tasks: list[Awaitable[None]] = [
            self._send_timed_embeds(embeds, duration) for duration, embeds in timed_embeds.items()
        ]
        await asyncio.gather(*tasks)

    async def refresh(self, content: Optional[str] = None) -> None:
        if self.is_finished():
            return
        await self.interaction.edit_original_response(content=content, embeds=self._embeds, view=self)

    async def send_error(self, description: str, duration: float = 5) -> None:
        await self.interact(embeds=[TimedEmbed(Error(description), duration)])

    async def finish(
        self,
        *,
        content: Optional[str] = None,
        embeds: Optional[list[discord.Embed]] = None,
        delete_after: Optional[float] = 5,
    ) -> None:
        if self.is_finished():
            return
        self.clear_items()
        self._static_embeds = []
        self._timed_embeds = []
        await response(self.interaction).edit_message(
            content=content, embeds=embeds or [], view=self, delete_after=delete_after
        )
        self.stop()
