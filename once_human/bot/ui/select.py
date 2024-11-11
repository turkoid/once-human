from itertools import zip_longest
from typing import Optional, Any, Callable

import discord

from once_human.models import Base
from once_human.bot.utils import DatabaseModel, InteractionCallback

type Selected[S: Base] = str | list[str] | S | list[S]
type SingleSelected[S: Base] = str | S


class NullSelectOption(discord.SelectOption):
    def __init__(self) -> None:
        super().__init__(label="...")

    @property
    def label(self) -> str:
        return "..."

    @label.setter
    def label(self, value: Any) -> None:
        pass

    @property
    def value(self) -> str:
        return self.label

    @value.setter
    def value(self, value: Any) -> None:
        pass

    @property
    def description(self) -> None:
        return None

    @description.setter
    def description(self, value: Any) -> None:
        pass

    @property
    def emoji(self) -> None:
        return None

    @emoji.setter
    def emoji(self, value: Any) -> None:
        pass

    @property
    def default(self) -> bool:
        return False

    @default.setter
    def default(self, value: bool) -> None:
        pass

    def __repr__(self):
        return self.label


NULL_SELECT_OPTION = NullSelectOption()
DISCORD_SELECT_MAX = 25


class BaseSelect[T: Base](discord.ui.Select):
    def __init__(
        self,
        *,
        option_label: DatabaseModel[T, str],
        option_value: Optional[DatabaseModel[T, Optional[str]]] = None,
        option_description: Optional[DatabaseModel[T, Optional[str]]] = None,
        callback: InteractionCallback,
        min_values: int = 1,
        max_values: Optional[int] = 1,
        **kwargs,
    ) -> None:
        self._underlying_select: Optional[discord.SelectMenu] = None
        if max_values is None:
            max_values = DISCORD_SELECT_MAX
        if min_values < 0 or min_values > max_values:
            raise ValueError(f"min_values must beast at least 0 and no greater than {max_values}")
        if max_values < min_values or max_values > DISCORD_SELECT_MAX:
            raise ValueError(f"max_values must beast at least {min_values} and no greater than {DISCORD_SELECT_MAX}")
        super().__init__(min_values=min_values, max_values=max_values, **kwargs)
        self.option_label = option_label
        self.option_value = option_value
        self.option_description = option_description
        self.callback = callback

    def _normalize_selected(self, selected: Optional[Selected[T]]) -> list[str]:
        if not selected:
            values = []
        elif isinstance(selected, str):
            values = [selected]
        elif isinstance(selected, Base):
            values = [self.option_value(selected)]
        elif isinstance(selected, list):
            values = []
            for entry in selected:
                if isinstance(entry, str):
                    values.append(entry)
                elif isinstance(entry, Base):
                    values.append(self.option_value(entry))
                else:
                    raise ValueError("Invalid selected value type")
        else:
            raise ValueError("Invalid selected value type")
        #
        # if len(values) < self.min_values or len(values) > self.max_values:
        #     f"The number of selected must be at least {self.min_values} and no greater than {self.max_values}"
        return values

    def _refresh(self, objects: list[T], *, values: list[str]) -> None:
        self.options.clear()
        for obj in objects:
            kwargs: dict[str, str] = {}
            for param in ["label", "value", "description"]:
                func = getattr(self, f"option_{param}")
                if func:
                    kwargs[param] = func(obj)
            opt = discord.SelectOption(**kwargs)
            opt.default = opt.value in values
            self.options.append(opt)

    def refresh(self, objects: list[T], *, selected: Optional[Selected[T]] = None) -> None:
        values = self._normalize_selected(selected)
        self._refresh(objects, values=values)

    def _select(self, values: list[str]) -> None:
        for opt in self.options:
            if opt.value in values:
                opt.default = True

    def select(self, selected: Selected[T]) -> None:
        values = self._normalize_selected(selected)
        self._select(values)

    @property
    def selected(self) -> list[str]:
        return [opt.value for opt in self.options if opt.default]

    def _selected(self, values: list[str]) -> None:
        for opt in self.options:
            opt.default = opt.value in values

    @selected.setter
    def selected(self, selected: Optional[Selected[T]]) -> None:
        values = self._normalize_selected(selected)
        self._selected(values)

    def _selected_objects(self, obj_values: dict[str, T]) -> list[T]:
        selected: list[T] = []
        for opt in self.options:
            if opt.default:
                obj = obj_values.get(opt.value, None)
                if obj is None:
                    raise ValueError(f"{opt.value} does not exist in objects")
                selected.append(obj)
        return selected

    def selected_objects(self, objects: list[T]) -> list[T]:
        obj_values = {self.option_value(obj): obj for obj in objects}
        return self._selected_objects(obj_values)

    @property
    def has_selected(self) -> bool:
        return any(opt.default for opt in self.options)

    def show(self) -> None:
        if not self.options:
            self.options.append(NULL_SELECT_OPTION)
        self.disabled = self.options[0] is NULL_SELECT_OPTION

    @property
    def _underlying(self) -> discord.SelectMenu:
        return self._underlying_select

    @_underlying.setter
    def _underlying(self, value: discord.SelectMenu) -> None:
        previous_underlying = self._underlying_select
        self._underlying_select = value
        if not previous_underlying or len(previous_underlying.options) != len(value.options):
            return
        for i, (opt, underlying_opt) in enumerate(zip_longest(previous_underlying.options, value.options)):
            if opt.value == underlying_opt.value and opt is NULL_SELECT_OPTION:
                self._underlying_select.options[i] = NULL_SELECT_OPTION
                break


class SingleSelect[T: Base](BaseSelect[T]):
    def __init__(self, **kwargs) -> None:
        kwargs["max_values"] = 1
        super().__init__(**kwargs)

    def _normalize_selected(self, selected: Optional[SingleSelected[T]]) -> list[str]:
        if isinstance(selected, list):
            raise ValueError("Multiple selected not allowed for single select")
        return super()._normalize_selected(selected)

    def refresh(self, objects: list[T], *, selected: Optional[SingleSelected[T]] = None) -> None:
        super().refresh(objects, selected=selected)

    def select(self, selected: SingleSelected[T]) -> None:
        super().select(selected)

    @property
    def selected(self) -> Optional[str]:
        selected = super().selected
        return selected[0] if selected else None

    @selected.setter
    def selected(self, selected: Optional[SingleSelected[T]]) -> None:
        super(SingleSelect, self.__class__).selected.fset(self, selected)

    def selected_objects(self, *args, **kwargs) -> None:
        raise TypeError("Operation not supported for a single select")

    def selected_object(self, objects: list[T]) -> Optional[T]:
        selected_objs = super().selected_objects(objects)
        return selected_objs[0] if selected_objs else None

    @property
    def value(self) -> Optional[str]:
        return self.values[0] if self.values else None


class SelectGroup[T: Base]:
    def __init__(
        self,
        size: int,
        *,
        placeholder: Optional[str | Callable[[BaseSelect[T]], str]] = None,
        min_values: int = 1,
        max_values: Optional[int] = None,
        option_label: DatabaseModel[T, str],
        option_value: Optional[DatabaseModel[T, Optional[str]]] = None,
        option_description: Optional[DatabaseModel[T, Optional[str]]] = None,
        callback: InteractionCallback,
    ):
        if size < 2 or size > 5:
            raise ValueError("Size must be at least 2 and no greater than 5")
        select_max = size * DISCORD_SELECT_MAX
        if max_values is None:
            max_values = select_max
        if min_values < 0 or min_values > max_values:
            raise ValueError(f"min_values must beast at least 0 and no greater than {max_values}")
        if max_values < min_values or max_values > select_max:
            raise ValueError(f"max_values must beast at least {min_values} and no greater than {select_max}")

        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.items: list[BaseSelect[T]] = []
        for _ in range(size):
            item = BaseSelect(
                min_values=min_values,
                max_values=min(DISCORD_SELECT_MAX, self.max_values),
                option_label=option_label,
                option_value=option_value,
                option_description=option_description,
                callback=callback,
            )
            self.items.append(item)

    @property
    def values(self) -> list[str]:
        values: list[str] = []
        for item in self.items:
            values.extend(item.values)
        return values

    def _normalize_selected(self, selected: Optional[Selected[T]]) -> list[str]:
        values = self.items[0]._normalize_selected(selected)
        # if len(values) < self.min_values or len(values) > self.max_values:
        #     raise ValueError(
        #         f"The number of selected must be at least {self.min_values} and no greater than {self.max_values}"
        #     )
        return values

    def refresh(self, objects: list[T], *, selected: Optional[Selected[T]] = None) -> None:
        values = self._normalize_selected(selected)
        for i, item in enumerate(self.items):
            lower_bound = i * DISCORD_SELECT_MAX
            upper_bound = lower_bound + DISCORD_SELECT_MAX
            item_objects = objects[lower_bound:upper_bound]
            item._refresh(item_objects, values=values)
            item.placeholder = self.placeholder(item)

    def select(self, selected: Selected[T]) -> None:
        values = self._normalize_selected(selected)
        for item in self.items:
            item._select(values)

    @property
    def selected(self) -> list[str]:
        values: list[str] = []
        for item in self.items:
            values.extend(item.selected)
        return values

    @selected.setter
    def selected(self, selected: Optional[Selected[T]]) -> None:
        values = self._normalize_selected(selected)
        for item in self.items:
            item._selected(values)

    def selected_objects(self, objects: list[T]) -> list[T]:
        obj_values = {self.items[0].option_value(obj): obj for obj in objects}
        selected: list[T] = []
        for item in self.items:
            item_selected = item._selected_objects(obj_values)
            selected.extend(item_selected)
        return selected

    @property
    def has_selected(self) -> bool:
        for item in self.items:
            if any(opt.default for opt in item.options):
                return True
        return False

    def show(self) -> None:
        for item in self.items:
            item.show()


class SingleSelectGroup[T: Base](SelectGroup[T]):
    def __init__(self, **kwargs) -> None:
        kwargs["max_values"] = 1
        super().__init__(**kwargs)

    def _normalize_selected(self, selected: Optional[SingleSelected[T]]) -> list[str]:
        if isinstance(selected, list):
            raise ValueError("Multiple selected not allowed for single selected")
        return super()._normalize_selected(selected)

    def refresh(self, objects: list[T], *, selected: Optional[SingleSelected[T]] = None) -> None:
        super().refresh(objects, selected=selected)

    def select(self, selected: SingleSelected[T]) -> None:
        super().select(selected)

    @property
    def selected(self) -> Optional[str]:
        selected = super().selected
        return selected[0] if selected else None

    @selected.setter
    def selected(self, selected: Optional[SingleSelected[T]]) -> None:
        super(SingleSelectGroup, self.__class__).selected.fset(self, selected)

    def selected_objects(self, *args, **kwargs) -> None:
        raise TypeError("Operation not supported for a single select")

    def selected_object(self, objects: list[T]) -> Optional[T]:
        selected_objs = super().selected_objects(objects)
        return selected_objs[0] if selected_objs else None

    @property
    def value(self) -> Optional[str]:
        values = self.values
        return values[0] if values else None
