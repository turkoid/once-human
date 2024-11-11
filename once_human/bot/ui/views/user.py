import functools
from operator import attrgetter
from typing import Optional

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from once_human.bot.ui.button import BaseButton
from once_human.bot.ui.modal import BaseModal
from once_human.bot.ui.select import SingleSelect
from once_human.bot.ui.select import SingleSelected
from once_human.bot.ui.views.base import BaseView
from once_human.bot.ui.views.base import intercept_interaction
from once_human.bot.ui.views.base import Layout
from once_human.bot.ui.views.player_specialization import PlayerSpecializationView
from once_human.bot.utils import InteractionCallback
from once_human.models import Player
from once_human.models import Server
from once_human.models import User


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
        spec_view = await PlayerSpecializationView.create(
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
