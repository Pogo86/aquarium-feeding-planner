"""WebSocket command used by the dashboard to save one feeding day."""
import math
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .plan import DOMAIN, PRESETS, DayPortion, replace_day, schedule_revision


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/save_day",
    vol.Required("entry_id"): str,
    vol.Required("revision"): vol.Match(r"^[a-f0-9]{64}$"),
    vol.Required("week"): vol.In(("a", "b")),
    vol.Required("weekday"): vol.All(int, vol.Range(min=0, max=6)),
    vol.Required("portions"): [{
        vol.Required("food_id"): str,
        vol.Required("grams"): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        vol.Optional("recipient", default=""): str,
        vol.Optional("note", default=""): str,
    }],
})
@callback
def websocket_save_day(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Validate a day edit, persist it and refresh the feeding sensor."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], "plan_unavailable", "This tank's feeding plan is unavailable.")
        return

    current = entry.options.get("portions", PRESETS[entry.data["preset"]])
    if schedule_revision(current) != msg["revision"]:
        connection.send_error(
            msg["id"], "schedule_changed", "The schedule changed. Close this editor and reopen the day."
        )
        return

    runtime = entry.runtime_data
    meals = []
    for portion in msg["portions"]:
        if portion["food_id"] not in runtime.catalogue.foods or not math.isfinite(portion["grams"]):
            connection.send_error(
                msg["id"], "invalid_portion", "Choose a catalogue food and a weight between 0 and 10 g."
            )
            return
        meals.append(DayPortion(
            food_id=portion["food_id"],
            recipient=portion["recipient"].strip(),
            grams=portion["grams"],
            note=portion["note"].strip(),
        ))

    updated = replace_day(current, msg["week"], msg["weekday"], meals)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "portions": updated})
    runtime.portions = updated
    async_dispatcher_send(hass, runtime.signal)
    connection.send_result(msg["id"])
