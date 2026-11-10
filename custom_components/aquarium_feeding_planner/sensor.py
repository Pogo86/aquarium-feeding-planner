"""Today's meal and feeding status."""
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import TankPlan
from .catalogue import FOODS_CHANGED
from .plan import format_meal, portions_for, rotation_week, schedule_by_day, schedule_revision


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[TankPlan], async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([FeedingPlanSensor(entry)])


class FeedingPlanSensor(SensorEntity):
    """Expose today's food, quantities and status for a tank."""

    _attr_has_entity_name = True
    _attr_name = "Feeding plan"
    _attr_icon = "mdi:fish"
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({
        "food_catalogue", "week_schedule", "schedule_revision", "plan_entry_id", "tank_name"
    })

    def __init__(self, entry: ConfigEntry[TankPlan]) -> None:
        super().__init__()
        self._plan = entry.runtime_data
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_feeding_plan"
        self._attr_device_info = self._plan.device_info
        self._refresh()

    async def async_added_to_hass(self) -> None:
        """Refresh after marking a feed and at local midnight."""
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, self._plan.signal, self._update))
        self.async_on_remove(async_dispatcher_connect(self.hass, FOODS_CHANGED, self._update))
        self.async_on_remove(
            async_track_time_change(self.hass, self._update, hour=0, minute=0, second=0)
        )
        self._refresh()

    @callback
    def _update(self, _now: datetime | None = None) -> None:
        self._refresh()
        self.async_write_ha_state()

    def _refresh(self) -> None:
        today = dt_util.now().date()
        portions = portions_for(today, self._plan.week_a, self._plan.portions)
        last_fed = self._plan.last_fed
        fed_today = last_fed is not None and dt_util.as_local(last_fed).date() == today
        self._attr_native_value = "fed" if fed_today else ("due" if portions else "rest_day")
        foods = self._plan.catalogue.foods
        self._attr_extra_state_attributes = {
            "meal": format_meal(portions, foods),
            "food_catalogue": [
                {"id": key, **food}
                for key, food in sorted(foods.items(), key=lambda item: item[1]["name"].casefold())
            ],
            "week_schedule": schedule_by_day(self._plan.portions),
            "schedule_revision": schedule_revision(self._plan.portions),
            "plan_entry_id": self._entry.entry_id,
            "tank_name": self._entry.title,
            "current_week": rotation_week(today, self._plan.week_a),
            "current_weekday": today.weekday(),
            "last_fed": last_fed.isoformat() if last_fed else None,
        }
