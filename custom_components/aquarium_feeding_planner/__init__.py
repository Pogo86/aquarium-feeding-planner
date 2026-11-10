"""Standalone, local aquarium feeding schedules."""
from asyncio import Lock
from datetime import date, datetime
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .catalogue import FoodCatalogue, async_get_catalogue
from .plan import DEFAULT_WEEK_A, DOMAIN, PRESETS
from .schedule_api import websocket_save_day

PLATFORMS = (Platform.SENSOR, Platform.BUTTON)


class TankPlan:
    """Own the schedule and persisted feeding status for one tank."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, catalogue: FoodCatalogue) -> None:
        self.hass = hass
        self.catalogue = catalogue
        self.portions = entry.options.get("portions", PRESETS[entry.data["preset"]])
        self.week_a = date.fromisoformat(entry.options.get("week_a", DEFAULT_WEEK_A))
        self.store = _feeding_store(hass, entry)
        self.last_fed: datetime | None = None
        self.signal = f"{DOMAIN}_{entry.entry_id}_updated"
        self.device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)
        self._lock = Lock()

    async def async_load(self) -> None:
        """Restore the last confirmed feeding."""
        saved = await self.store.async_load()
        if saved and saved.get("last_fed"):
            self.last_fed = dt_util.parse_datetime(saved["last_fed"])

    async def async_mark_fed(self) -> None:
        """Record one confirmed feeding per tank per local date."""
        async with self._lock:
            now = dt_util.now()
            if self.last_fed and dt_util.as_local(self.last_fed).date() == now.date():
                return
            await self.store.async_save({"last_fed": now.isoformat()})
            self.last_fed = now
            async_dispatcher_send(self.hass, self.signal)


def _feeding_store(hass: HomeAssistant, entry: ConfigEntry) -> Store:
    return Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the local dashboard resource and schedule editor."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            f"/{DOMAIN}/card.js",
            str(Path(__file__).parent / "www" / "card.js"),
            False,
        )
    ])
    websocket_api.async_register_command(hass, websocket_save_day)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry[TankPlan]) -> bool:
    """Set up a feeding plan from the UI."""
    catalogue = await async_get_catalogue(hass)
    plan = TankPlan(hass, entry, catalogue)
    await plan.async_load()
    entry.runtime_data = plan
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry[TankPlan]) -> bool:
    """Unload both entities when the tank is reconfigured or disabled."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry[TankPlan]) -> None:
    """Remove the tank's feeding record when the entry is deleted."""
    await _feeding_store(hass, entry).async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry[TankPlan]) -> bool:
    """Convert v0.1 schedule rows to catalogue references."""
    if entry.version != 1:
        return False
    if entry.minor_version >= 2:
        return True
    options = dict(entry.options)
    if "portions" in options:
        catalogue = await async_get_catalogue(hass)
        options["portions"] = await catalogue.async_link_legacy_portions(options["portions"])
    hass.config_entries.async_update_entry(entry, minor_version=2, options=options)
    return True
