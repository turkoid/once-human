import abc
import asyncio
import functools
import inspect
from abc import abstractmethod
from operator import attrgetter
from typing import Optional, Awaitable, Self, Callable, Any
import discord

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from once_human.bot.ui.button import BaseButton
from once_human.bot.ui.embed import Error, TimedEmbed
from once_human.bot.ui.modal import BaseModal
from once_human.bot.ui.select import (
    SingleSelect,
    SingleSelected,
    SingleSelectGroup,
    BaseSelect,
    DISCORD_SELECT_MAX,
)
from once_human.bot.utils import response, InteractionCallback, ZERO_WIDTH_SPACE
from once_human.models import Player, Server, User, Specialization

type Layout = list[list[discord.ui.Item]]
type DecoratedCallback[**P] = Callable[[P], Awaitable[None]]

MIN_LEVEL = 5
MAX_LEVEL = 50
LEVEL_INCREMENT = 5


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


class UserView(BaseView):
    def __init__(
        self,
        interaction: discord.Interaction,
        session: AsyncSession,
        discord_user: discord.User,
        timeout: float = 100.0,
    ) -> None:
        super().__init__(interaction, session, timeout=timeout)

        self.discord_user = discord_user
        self.user: Optional[User] = None
        self.servers: Optional[list[Server]] = None
        self.new_player_button: Optional[BaseButton] = None
        self.modify_player_button: Optional[BaseButton] = None
        self.reset_player_button: Optional[BaseButton] = None
        self.delete_player_button: Optional[BaseButton] = None
        self.player_select: Optional[SingleSelect[Player]] = None
        self.server_select: Optional[SingleSelect[Server]] = None
        self.modify_specs_button: Optional[BaseButton] = None
        self.save_button: Optional[BaseButton] = None
        self.cancel_button: Optional[BaseButton] = None

    async def load_database_objects(self) -> None:
        stmt = (
            select(User)
            .options(selectinload(User.players).selectinload(Player.player_specializations))
            .where(User.id == self.discord_user.id)
        )
        user = (await self.session.scalars(stmt)).first()
        if not user:
            user = User(
                id=self.discord_user.id,
                username=self.discord_user.name,
                display_name=self.discord_user.display_name,
            )
            self.session.add(user)
        self.user = user
        stmt = select(Server).order_by(Server.name).options(selectinload(Server.scenario))
        self.servers = (await self.session.scalars(stmt)).all()

    def build_ui(self) -> None:
        user: User = self.user
        self.new_player_button = BaseButton(label="New", style=discord.ButtonStyle.primary, callback=self.new_player)
        self.modify_player_button = BaseButton(
            label="Modify", style=discord.ButtonStyle.secondary, callback=self.modify_player
        )
        self.reset_player_button = BaseButton(
            label="Reset", style=discord.ButtonStyle.secondary, callback=self.reset_player
        )
        self.delete_player_button = BaseButton(
            label="Delete", style=discord.ButtonStyle.danger, callback=self.delete_player
        )
        self.player_select = SingleSelect[Player](
            placeholder="Select a player",
            option_label=attrgetter("name"),
            option_value=attrgetter("lower_name"),
            option_description=lambda player: f"{len(player.specializations)} specs selected",
            callback=self.player_selected,
        )
        self.player_select.refresh(user.players)
        self.server_select = SingleSelect[Server](
            placeholder="Select server",
            option_label=attrgetter("name"),
            option_value=attrgetter("lower_name"),
            option_description=lambda server: server.scenario.name,
            callback=self.server_selected,
        )
        self.server_select.refresh(self.servers)
        if user.players:
            self._select_player(user.players[0])
        self.modify_specs_button = BaseButton(
            label="Specializations", style=discord.ButtonStyle.primary, callback=self.modify_specs
        )
        self.save_button = BaseButton(label="Save", style=discord.ButtonStyle.success, callback=self.save)
        self.cancel_button = BaseButton(label="Cancel", style=discord.ButtonStyle.danger, callback=self.cancel)

        # add items to view
        layout: Layout = [
            [self.new_player_button, self.modify_player_button, self.reset_player_button, self.delete_player_button],
            [self.player_select],
            [self.server_select],
            [],
            [self.modify_specs_button, self.save_button, self.cancel_button],
        ]
        self.add_layout(layout)

    def _select_player(self, player: Optional[SingleSelected[Player]]) -> Optional[Player]:
        user: User = self.user
        self.player_select.selected = player
        selected_player = self.player_select.selected_object(user.players)
        self._select_server(selected_player.server if selected_player else None)
        return selected_player

    def _select_server(self, server: Optional[SingleSelected[Server]]) -> Optional[Server]:
        self.server_select.selected = server
        selected_server = self.server_select.selected_object(self.servers)
        return selected_server

    @staticmethod
    def _create_player_input(
        *, label: str = "Player name", placeholder: str = "Please enter a name", default: Optional[str] = None
    ) -> discord.ui.TextInput:
        input = discord.ui.TextInput(
            label=label,
            style=discord.TextStyle.short,
            placeholder=placeholder,
            default=default,
            min_length=1,
            max_length=Player.__table__.columns["name"].type.length,
            required=True,
        )
        return input

    def _create_player_input_modal(
        self, title: str, input: discord.ui.TextInput, on_submit: InteractionCallback
    ) -> BaseModal:
        input_modal = BaseModal(title=title, on_submit=functools.partial(on_submit, self))
        input_modal.add_item(input)
        return input_modal

    @classmethod
    def _create_player_embed(cls, player: Player) -> discord.Embed:
        specs: list[str] = []
        for level in range(5, 51, 5):
            player_spec = player.specializations.get(level, None)
            player_spec_str = player_spec.name if player_spec else ""
            spec = f"* **Level {level}** - {player_spec_str}"
            specs.append(spec)
        embed = discord.Embed(description="\n".join(specs))
        return embed

    @intercept_interaction
    async def new_player(self) -> None:
        user: User = self.user
        if len(user.players) >= 25:
            await self.send_error("You are limited to 25 players")
            return

        input = UserView._create_player_input()

        @intercept_interaction
        async def submit() -> None:
            value = input.value
            for player in user.players:
                if player.lower_name != value.lower():
                    continue
                await self.send_error(f"**{player.name}** already exists")
                return

            player = Player(name=value)
            self.session.add(player)
            user.players.append(player)
            user.players.sort(key=attrgetter("lower_name"))
            self.player_select.refresh(user.players, selected=player)
            self.server_select.selected = None
            self.update_view()

            await self.interact(embeds=[self._create_player_embed(player)])

        input_modal = self._create_player_input_modal("New Player", input, on_submit=submit)
        await self.show_and_wait(input_modal)

    @intercept_interaction
    async def reset_player(self) -> None:
        await self.interact(content="reset player")

    @intercept_interaction
    async def modify_player(self) -> None:
        user: User = self.user
        selected_player: Player = self.player_select.selected_object(user.players)
        input = UserView._create_player_input(default=selected_player.name)

        @intercept_interaction
        async def submit():
            if selected_player.name == input.value:
                await self.send_error("Player name not modified")
                return

            if any(
                player.lower_name == input.value.lower()
                for player in user.players
                if player.lower_name != selected_player.lower_name
            ):
                await self.send_error("Player name already exists")
                return

            selected_player.name = input.value
            self.session.add(selected_player)
            user.players.sort(key=attrgetter("lower_name"))
            self.player_select.refresh(user.players, selected=selected_player)
            self.update_view()
            await self.interact(content="Player name changed")

        input_modal = self._create_player_input_modal("Modify Player", input, on_submit=submit)
        await self.show_and_wait(input_modal)

    @intercept_interaction
    async def delete_player(self) -> None:
        user: User = self.user
        selected_value = self.player_select.selected
        for i, player in enumerate(user.players):
            if player.lower_name == selected_value:
                del user.players[i]
                await self.session.flush()
                self.session.expunge(player)
                break
        self.session.add(user)
        self.player_select.refresh(user.players, selected=None)
        self.server_select.selected = None
        self.update_view()
        await self.interact(content="Removed player", embeds=[])

    @intercept_interaction
    async def player_selected(self) -> None:
        selected_player = self._select_player(self.player_select.value)
        self.update_view()
        await self.interact(embeds=[self._create_player_embed(selected_player)])

    @intercept_interaction
    async def server_selected(self) -> None:
        selected_server = self._select_server(self.server_select.value)
        user: User = self.user
        selected_player = self.player_select.selected_object(user.players)
        if selected_player.server != selected_server:
            selected_player.server = selected_server
            self.session.add(selected_player)
        self.update_view()
        await self.interact()

    @intercept_interaction
    async def modify_specs(self) -> None:
        user: User = self.user
        spec_view = await SpecializationView.create(
            self.interaction, self.session, self.player_select.selected_object(user.players)
        )
        await self.interact(view=spec_view, embeds=[])

    @intercept_interaction
    async def save(self) -> None:
        await self.session.commit()
        await self.finish(content="Saved")

    @intercept_interaction
    async def cancel(self) -> None:
        await self.session.rollback()
        await self.finish(content="Changes Canceled")

    def update_view(self) -> None:
        self.player_select.show()
        self.server_select.show()
        self.server_select.disabled = self.player_select.disabled
        player_is_selected = self.player_select.has_selected
        self.modify_player_button.disabled = not player_is_selected
        self.reset_player_button.disabled = not player_is_selected
        self.delete_player_button.disabled = not player_is_selected
        server_is_selected = self.server_select.has_selected
        self.modify_specs_button.disabled = not player_is_selected and not server_is_selected


class SpecializationView(BaseView):
    def __init__(
        self, interaction: discord.Interaction, session: AsyncSession, player: Player, timeout: Optional[float] = 180.0
    ) -> None:
        super().__init__(interaction, session, timeout=timeout)
        self.player: Player = player
        self.specs: list[Specialization] = []
        self.server_players: Optional[list[Player]] = None
        self.specs_by_level: dict[int, list[Specialization]] = {}
        self.current_level: int = 5

        self.clear_spec_button: Optional[BaseButton] = None
        self.first_spec_button: Optional[BaseButton] = None
        self.prev_spec_button: Optional[BaseButton] = None
        self.next_spec_button: Optional[BaseButton] = None
        self.last_spec_button: Optional[BaseButton] = None
        self.specs_select: Optional[SingleSelectGroup[Specialization]] = None
        self.players_view_button: Optional[BaseButton] = None
        self.save_button: Optional[BaseButton] = None
        self.cancel_button: Optional[BaseButton] = None

    async def load_database_objects(self) -> None:
        await self.session.refresh(self.player.server.scenario, ["specializations"])
        self.specs = self.player.server.scenario.specializations
        for spec in self.specs:
            for level in spec.levels:
                self.specs_by_level.setdefault(level, []).append(spec)
        stmt = (
            select(Player)
            .where(and_(Player.server == self.player.server, Player.id != self.player.id))
            .order_by(Player.lower_name)
            .options(selectinload(Player.player_specializations))
        )
        self.server_players = (await self.session.scalars(stmt)).all()

    def build_ui(self) -> None:
        self.clear_spec_button = BaseButton(label="Clear", style=discord.ButtonStyle.primary, callback=self.clear_spec)
        emoji_first = "⏮️"
        emoji_prev = "⏪"
        emoji_next = "⏩"
        emoji_last = "⏭️"
        self.first_spec_button = BaseButton(emoji=emoji_first, callback=self.first_spec)
        self.prev_spec_button = BaseButton(emoji=emoji_prev, callback=self.prev_spec)
        self.next_spec_button = BaseButton(emoji=emoji_next, callback=self.next_spec)
        self.last_spec_button = BaseButton(emoji=emoji_last, callback=self.last_spec)

        def placeholder_gen(item: BaseSelect):
            if item.options:
                placeholder = f"{item.options[0].label[:2].title()} - {item.options[-1].label[:2].title()}"
            else:
                placeholder = ZERO_WIDTH_SPACE
            return placeholder

        size = int((max(len(specs) for specs in self.specs_by_level.values()) - 1) / DISCORD_SELECT_MAX) + 1
        self.specs_select = SingleSelectGroup[Specialization](
            size,
            min_values=0,
            placeholder=placeholder_gen,
            option_label=attrgetter("name"),
            option_value=attrgetter("lower_name"),
            callback=self.select_spec,
        )
        self._refresh_specs()
        self.players_view_button = BaseButton(
            label="Select Player", style=discord.ButtonStyle.primary, callback=self.players_view
        )
        self.save_button = BaseButton(label="Save", style=discord.ButtonStyle.success, callback=self.save)
        self.cancel_button = BaseButton(label="Cancel", style=discord.ButtonStyle.danger, callback=self.cancel)

        layout: Layout = [
            [
                self.clear_spec_button,
                self.first_spec_button,
                self.prev_spec_button,
                self.next_spec_button,
                self.last_spec_button,
            ],
            *[[select_item] for select_item in self.specs_select.items],
            [self.players_view_button, self.save_button, self.cancel_button],
        ]
        self.add_layout(layout)

    def _refresh_specs(self) -> None:
        level_specs = self.specs_by_level.get(self.current_level, [])
        player_spec = self.player.specializations.get(self.current_level, None)
        player_specs = [spec for level, spec in self.player.specializations.items() if level != self.current_level]
        level_specs = [spec for spec in level_specs if spec not in player_specs]
        self.specs_select.refresh(level_specs, selected=player_spec)

    def _select_spec(self, spec: Optional[SingleSelected[Specialization]]) -> Optional[Specialization]:
        self.specs_select.selected = spec
        level_specs = self.specs_by_level[self.current_level]
        selected_spec = self.specs_select.selected_object(level_specs)
        player_spec = self.player.specializations.get(self.current_level, None)
        if selected_spec is None and player_spec:
            del self.player.specializations[self.current_level]
            self.session.add(self.player)
        elif player_spec != selected_spec:
            self.player.specializations[self.current_level] = selected_spec
            self.session.add(self.player)
        return selected_spec

    @intercept_interaction
    async def clear_spec(self) -> None:
        self._select_spec(None)
        self.update_view()
        await self.interact(content="clear_spec")

    @intercept_interaction
    async def first_spec(self) -> None:
        self.current_level = MIN_LEVEL
        self._refresh_specs()
        self.update_view()
        await self.interact(content="first_spec")

    @intercept_interaction
    async def prev_spec(self) -> None:
        self.current_level -= LEVEL_INCREMENT
        self._refresh_specs()
        self.update_view()
        await self.interact(content="prev_spec")

    @intercept_interaction
    async def next_spec(self) -> None:
        self.current_level += LEVEL_INCREMENT
        self._refresh_specs()
        self.update_view()
        await self.interact(content="next_spec")

    @intercept_interaction
    async def last_spec(self) -> None:
        self.current_level = MAX_LEVEL
        self._refresh_specs()
        self.update_view()
        await self.interact(content="last_spec")

    @intercept_interaction
    async def select_spec(self, item: SingleSelect[Specialization]) -> None:
        self._select_spec(item.value)
        self.update_view()
        await self.interact(content="selected spec")

    @intercept_interaction
    async def players_view(self) -> None:
        await self.interact(content="players_view")

    @intercept_interaction
    async def save(self) -> None:
        await self.session.commit()
        await self.finish(content="Saved")

    @intercept_interaction
    async def cancel(self) -> None:
        await self.session.rollback()
        await self.finish(content="Changes Canceled")

    def update_view(self) -> None:
        self.specs_select.show()
        self.clear_spec_button.disabled = not self.specs_select.has_selected
        self.first_spec_button.disabled = self.current_level == MIN_LEVEL
        self.prev_spec_button.disabled = self.current_level == MIN_LEVEL
        self.next_spec_button.disabled = self.current_level == MAX_LEVEL
        self.last_spec_button.disabled = self.current_level == MAX_LEVEL
