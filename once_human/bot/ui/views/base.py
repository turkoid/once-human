import abc
import asyncio
import functools
import inspect
from abc import abstractmethod
from typing import Optional, Awaitable, Self, Callable, Any
import discord

from sqlalchemy.ext.asyncio import AsyncSession

from once_human.bot.ui.embed import Error, TimedEmbed
from once_human.bot.utils import response, InteractionCallback

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
    def __init__(self, interaction: discord.Interaction, session: AsyncSession, *args: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.interaction = interaction
        self.session = session
        self.static_embeds: list[discord.Embed] = []
        self.timed_embeds: list[discord.Embed] = []

    @property
    def embeds(self) -> list[discord.Embed]:
        return self.static_embeds + self.timed_embeds

    @classmethod
    async def create(
        cls, interaction: discord.Interaction, session: AsyncSession, *args: Any, timeout: Optional[float] = None
    ) -> Self:
        view = cls(interaction, session, *args, timeout=timeout)
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

    async def show_and_wait(self, modal: discord.ui.Modal) -> None:
        await response(self.interaction).send_modal(modal)
        await modal.wait()

    async def _send_timed_embeds(self, embeds: list[discord.Embed], duration: float) -> None:
        await asyncio.sleep(duration)
        updated_embeds = []
        for embed in self.timed_embeds:
            if any(em for em in embeds if em is embed):
                continue
            updated_embeds.append(embed)
        if len(self.timed_embeds) != len(updated_embeds):
            self.timed_embeds = updated_embeds
            await self.refresh()

    async def interact(
        self,
        *,
        view: Optional[discord.ui.View] = None,
        content: Optional[str] = None,
        embeds: Optional[list[discord.Embed | TimedEmbed]] = None,
        suppress_static: bool = False,
    ) -> None:
        if self.is_finished():
            return
        timed_embeds: dict[float, list[discord.Embed]] = {}
        if view and view is not self:
            self.static_embeds = []
            self.timed_embeds = []
        elif embeds is not None and len(embeds) == 0:
            self.static_embeds = []
        elif embeds:
            static_embeds = []
            for embed in embeds:
                if isinstance(embed, discord.Embed):
                    static_embeds.append(embed)
                else:
                    embed: TimedEmbed = embed
                    timed_embeds.setdefault(embed.duration, []).append(embed.embed)
                    self.timed_embeds.append(embed.embed)
            if static_embeds:
                self.static_embeds = static_embeds
        await response(self.interaction).edit_message(content=content, embeds=self.embeds, view=view or self)
        tasks: list[Awaitable[None]] = [
            self._send_timed_embeds(embeds, duration) for duration, embeds in timed_embeds.items()
        ]
        await asyncio.gather(*tasks)

    async def refresh(self, content: Optional[str] = None) -> None:
        if self.is_finished():
            return
        await self.interaction.edit_original_response(content=content, embeds=self.embeds, view=self)

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
        self.static_embeds = []
        self.timed_embeds = []
        await response(self.interaction).edit_message(
            content=content, embeds=embeds or [], view=self, delete_after=delete_after
        )
        self.stop()
