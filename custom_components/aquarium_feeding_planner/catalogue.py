"""Persist the food list shared by every tank."""
from asyncio import Lock
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .plan import DEFAULT_FOODS, DOMAIN, Food, Portion

FOODS_CHANGED = f"{DOMAIN}_foods_changed"


class DuplicateFoodError(ValueError):
    """A food with this name already exists."""


def valid_purchase_url(url: str) -> bool:
    """Accept a web link, or no link."""
    if not url:
        return True
    if any(char.isspace() or char in '<>\\' or ord(char) < 32 for char in url):
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.username is None
    except ValueError:
        return False


class FoodCatalogue:
    """Maintain a shared, persisted mapping from food IDs to names and links."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.foods: dict[str, Food] = {}
        self._store = Store(hass, 1, f"{DOMAIN}.foods")
        self._loaded = False
        self._lock = Lock()

    async def async_load(self) -> None:
        async with self._lock:
            if not self._loaded:
                data = await self._store.async_load()
                self.foods = data["foods"] if data and "foods" in data else dict(DEFAULT_FOODS)
                self._loaded = True

    async def _async_save(self, foods: dict[str, Food]) -> None:
        await self._store.async_save({"foods": foods})
        self.foods = foods
        async_dispatcher_send(self.hass, FOODS_CHANGED)

    async def async_save_food(self, key: str | None, name: str, url: str) -> None:
        async with self._lock:
            if any(other != key and food["name"].casefold() == name.casefold()
                   for other, food in self.foods.items()):
                raise DuplicateFoodError(name)
            foods = {**self.foods, (key or uuid4().hex): {"name": name, "url": url}}
            await self._async_save(foods)

    async def async_link_legacy_portions(self, rows: list[dict[str, Any]]) -> list[Portion]:
        """Link v0.1 portions to foods while preserving their schedule and wording."""
        async with self._lock:
            foods = dict(self.foods)
            food_ids = {food["name"].casefold(): key for key, food in foods.items()}
            portions = []
            for row in rows:
                if "food_id" in row:
                    portions.append(row)
                    continue
                old = dict(row)
                label = old.pop("label")
                recipient, separator, name = label.partition(": ")
                if not separator or not name.strip():
                    recipient, name = "", label
                food_id = food_ids.get(name.casefold())
                if food_id is None:
                    food_id = uuid4().hex
                    food_ids[name.casefold()] = food_id
                    foods[food_id] = {"name": name, "url": ""}
                portions.append({**old, "recipient": recipient, "food_id": food_id})
            if foods != self.foods:
                await self._async_save(foods)
            return portions


async def async_get_catalogue(hass: HomeAssistant) -> FoodCatalogue:
    """Return the catalogue after it has been loaded."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = FoodCatalogue(hass)
    catalogue = hass.data[DOMAIN]
    await catalogue.async_load()
    return catalogue

