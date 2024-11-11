from operator import attrgetter
from typing import Optional

import discord
from sqlalchemy import and_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from once_human.bot.ui.button import BaseButton
from once_human.bot.ui.select import BaseSelect
from once_human.bot.ui.select import DISCORD_SELECT_MAX
from once_human.bot.ui.select import SingleSelect
from once_human.bot.ui.select import SingleSelected
from once_human.bot.ui.select import SingleSelectGroup
from once_human.bot.ui.views.base import BaseView
from once_human.bot.ui.views.base import intercept_interaction
from once_human.bot.ui.views.base import Layout
from once_human.bot.utils import ZERO_WIDTH_SPACE
from once_human.models import Player
from once_human.models import Specialization

MIN_LEVEL = 5
MAX_LEVEL = 50
LEVEL_INCREMENT = 5


class PlayerSpecializationView(BaseView):
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
        # description = 5, 10, 15 | 2 players | 0/3 expert
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
