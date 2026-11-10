"""A button to confirm a feeding."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TankPlan


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[TankPlan], async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([MarkFedButton(entry)])


class MarkFedButton(ButtonEntity):
    """Confirm that today's feeding is complete."""

    _attr_has_entity_name = True
    _attr_name = "Mark as fed"
    _attr_icon = "mdi:check"

    def __init__(self, entry: ConfigEntry[TankPlan]) -> None:
        super().__init__()
        self._plan = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_mark_as_fed"
        self._attr_device_info = self._plan.device_info

    async def async_press(self) -> None:
        await self._plan.async_mark_fed()

