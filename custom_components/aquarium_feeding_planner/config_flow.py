"""Set up tanks and edit their feeding plans in the Home Assistant UI."""
from datetime import date
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .catalogue import DuplicateFoodError, async_get_catalogue, valid_purchase_url
from .plan import DEFAULT_WEEK_A, DOMAIN, PRESETS, WEEKDAYS, Food, Portion, portion_label

DAY_OPTIONS = [{"value": str(i), "label": name} for i, name in enumerate(WEEKDAYS)]


def _select(options: list[dict[str, str]], multiple: bool = False) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, multiple=multiple, mode=selector.SelectSelectorMode.DROPDOWN)
    )


def _food_choices(foods: dict[str, Food]) -> list[dict[str, str]]:
    return [
        {"value": key, "label": food["name"]}
        for key, food in sorted(foods.items(), key=lambda item: item[1]["name"].casefold())
    ]


class FeedingPlannerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one plan per tank."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            name = user_input["name"].strip()
            if name and (slug := slugify(name)):
                await self.async_set_unique_id(f"tank_{slug}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=name, data={"preset": user_input["preset"]})
            errors["name"] = "invalid_name"

        schema = vol.Schema({
            vol.Required("name"): selector.TextSelector(),
            vol.Required("preset", default="main"): _select([
                {"value": "main", "label": "Main tank"},
                {"value": "shrimp", "label": "Cherry shrimp"},
            ]),
        })
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        return FeedingOptionsFlow()


class FeedingOptionsFlow(OptionsFlowWithReload):
    """Manage individual portions and the fortnightly rotation."""

    _portion_id: str | None = None
    _food_id: str | None = None

    def _portions(self) -> list[Portion]:
        return self.config_entry.options.get("portions", PRESETS[self.config_entry.data["preset"]])

    def _save(self, **updates) -> ConfigFlowResult:
        return self.async_create_entry(title="", data={**self.config_entry.options, **updates})

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        menu = ["edit_portion", "add_portion", "remove_portion"] if self._portions() else ["add_portion"]
        return self.async_show_menu(step_id="init", menu_options=[*menu, "manage_foods", "set_week_a"])

    async def async_step_edit_portion(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is None:
            return await self._async_select_portion("edit_portion")
        self._portion_id = user_input["portion"]
        return await self.async_step_portion()

    async def async_step_add_portion(self, user_input: dict | None = None) -> ConfigFlowResult:
        self._portion_id = None
        return await self.async_step_portion()

    async def async_step_remove_portion(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is None:
            return await self._async_select_portion("remove_portion")
        return self._save(portions=[p for p in self._portions() if p["id"] != user_input["portion"]])

    async def _async_select_portion(self, step_id: str) -> ConfigFlowResult:
        catalogue = await async_get_catalogue(self.hass)
        choices = []
        for portion in self._portions():
            weekly = ", ".join(WEEKDAYS[int(i)][:3] for i in portion["weekly_days"])
            alternate = ", ".join(WEEKDAYS[int(i)][:3] for i in portion["alternate_days"])
            days = [weekly] if weekly else []
            if alternate:
                days.append(f"{alternate} week {portion['alternate_week'].upper()}")
            choices.append({
                "value": portion["id"],
                "label": f"{portion_label(portion, catalogue.foods)} ({portion['grams']:.2f} g; {' + '.join(days)})",
            })
        if not choices:
            return self.async_abort(reason="portion_missing")
        return self.async_show_form(
            step_id=step_id, data_schema=vol.Schema({vol.Required("portion"): _select(choices)})
        )

    async def async_step_portion(self, user_input: dict | None = None) -> ConfigFlowResult:
        catalogue = await async_get_catalogue(self.hass)
        portions = self._portions()
        current = next((p for p in portions if p["id"] == self._portion_id), None)
        if self._portion_id is not None and current is None:
            return self.async_abort(reason="portion_missing")

        errors = {}
        if user_input is not None:
            food_id = user_input["food_id"]
            weekly_days = user_input.get("weekly_days", [])
            alternate_days = user_input.get("alternate_days", [])
            if food_id not in catalogue.foods:
                errors["food_id"] = "food_missing"
            if not weekly_days and not alternate_days:
                errors["base"] = "missing_days"
            if set(weekly_days) & set(alternate_days):
                errors["alternate_days"] = "overlapping_days"
            if not errors:
                updated: Portion = {
                    "id": self._portion_id or uuid4().hex,
                    "recipient": user_input.get("recipient", "").strip(),
                    "food_id": food_id,
                    "grams": float(user_input["grams"]),
                    "weekly_days": weekly_days,
                    "alternate_days": alternate_days,
                    "alternate_week": user_input["alternate_week"],
                    "note": user_input.get("note", "").strip(),
                }
                if current is None:
                    return self._save(portions=[*portions, updated])
                return self._save(portions=[updated if p["id"] == updated["id"] else p for p in portions])

        schema = vol.Schema({
            vol.Required("food_id"): _select(_food_choices(catalogue.foods)),
            vol.Optional("recipient"): selector.TextSelector(),
            vol.Required("grams"): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=10, step=0.01, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="g"
            )),
            vol.Optional("weekly_days"): _select(DAY_OPTIONS, multiple=True),
            vol.Optional("alternate_days"): _select(DAY_OPTIONS, multiple=True),
            vol.Required("alternate_week", default="a"): _select([
                {"value": "a", "label": "Week A"},
                {"value": "b", "label": "Week B"},
            ]),
            vol.Optional("note"): selector.TextSelector(),
        })
        return self.async_show_form(
            step_id="portion",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or current),
            errors=errors,
        )

    async def async_step_manage_foods(self, user_input: dict | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="manage_foods", menu_options=["add_food", "edit_food"]
        )

    async def async_step_add_food(self, user_input: dict | None = None) -> ConfigFlowResult:
        self._food_id = None
        return await self.async_step_food()

    async def async_step_edit_food(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._food_id = user_input["food_id"]
            return await self.async_step_food()
        catalogue = await async_get_catalogue(self.hass)
        return self.async_show_form(
            step_id="edit_food",
            data_schema=vol.Schema({vol.Required("food_id"): _select(_food_choices(catalogue.foods))}),
        )

    async def async_step_food(self, user_input: dict | None = None) -> ConfigFlowResult:
        catalogue = await async_get_catalogue(self.hass)
        current = catalogue.foods.get(self._food_id) if self._food_id is not None else None
        if self._food_id is not None and current is None:
            return self.async_abort(reason="food_missing")
        errors = {}
        if user_input is not None:
            name = user_input["name"].strip()
            url = user_input.get("url", "").strip()
            if not name:
                errors["name"] = "invalid_food_name"
            if not valid_purchase_url(url):
                errors["url"] = "invalid_url"
            if not errors:
                try:
                    await catalogue.async_save_food(self._food_id, name, url)
                except DuplicateFoodError:
                    errors["name"] = "duplicate_food"
                else:
                    return self._save()

        schema = vol.Schema({
            vol.Required("name"): selector.TextSelector(),
            vol.Optional("url"): selector.TextSelector(),
        })
        return self.async_show_form(
            step_id="food",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or current),
            errors=errors,
        )

    async def async_step_set_week_a(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            week_a = date.fromisoformat(user_input["week_a"])
            if week_a.weekday() == 0:
                return self._save(week_a=week_a.isoformat())
            errors["week_a"] = "not_monday"
        schema = vol.Schema({vol.Required("week_a"): selector.DateSelector()})
        suggested = user_input or {"week_a": self.config_entry.options.get("week_a", DEFAULT_WEEK_A)}
        return self.async_show_form(
            step_id="set_week_a",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

