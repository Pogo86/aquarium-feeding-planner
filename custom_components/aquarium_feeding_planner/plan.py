"""Default food catalogue, feeding presets and calendar logic."""
from datetime import date
from typing import TypedDict

DOMAIN = "aquarium_feeding_planner"
DEFAULT_WEEK_A = "2026-11-09"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class Food(TypedDict):
    name: str
    url: str


class Portion(TypedDict):
    id: str
    recipient: str
    food_id: str
    grams: float
    weekly_days: list[str]
    alternate_days: list[str]
    alternate_week: str
    note: str


DEFAULT_FOODS: dict[str, Food] = {
    "insect": {"name": "Insect Granules", "url": "https://heronspetworld.co.uk/products/insect-granules"},
    "daphnia": {"name": "Dried Daphnia", "url": "https://heronspetworld.co.uk/products/dried-daphnia"},
    "tropical": {"name": "Ultra Tropical Flakes", "url": "https://heronspetworld.co.uk/products/ultra-tropical-flakes"},
    "spirulina": {"name": "Spirulina Forte Flakes", "url": "https://heronspetworld.co.uk/products/spirulina-forte-flakes"},
    "catfish": {"name": "2 mm Catfish Pellets", "url": "https://heronspetworld.co.uk/products/catfish-pellets-2mm"},
    "bloodworms": {"name": "Freeze-dried bloodworms", "url": "https://heronspetworld.co.uk/products/freeze-dried-bloodworm-larvae"},
    "wafer": {"name": "Spirulina Algae Wafer", "url": "https://heronspetworld.co.uk/products/spirulina-algae-wafers"},
    "shrimp": {"name": "Nano Caridina Sticks", "url": "https://heronspetworld.co.uk/products/nano-caridina-sticks"},
    "multi": {"name": "Multi Pellets", "url": "https://heronspetworld.co.uk/products/multi-pellets"},
}


def _portion(
    key: str,
    recipient: str,
    food_id: str,
    grams: float,
    weekly: str = "",
    alternate: str = "",
    week: str = "a",
    note: str = "",
) -> Portion:
    return {
        "id": key,
        "recipient": recipient,
        "food_id": food_id,
        "grams": grams,
        "weekly_days": list(weekly),
        "alternate_days": list(alternate),
        "alternate_week": week,
        "note": note,
    }


PRESETS: dict[str, list[Portion]] = {
    "main": [
        _portion("tetra_regular", "Tetras", "insect", 0.40, "03", "5", "b"),
        _portion("tetra_mixed", "Tetras", "insect", 0.25, "1", "5"),
        _portion("daphnia", "Tetras", "daphnia", 0.10, "1"),
        _portion("flakes", "Tetras", "tropical", 0.40, "26"),
        _portion("spirulina", "Tetras", "spirulina", 0.40, "4"),
        _portion("cory_regular", "Corys", "catfish", 0.20, "012346", "5", "b"),
        _portion("cory_reduced", "Corys", "catfish", 0.15, alternate="5"),
        _portion("bloodworms", "Tetras and corys", "bloodworms", 0.05,
                 alternate="5", note="share this amount"),
        _portion("oto_wafer", "Otos", "wafer", 0.03, "0123456",
                 note="offer a broken fragment"),
    ],
    "shrimp": [
        _portion("shrimp_sticks", "Cherry shrimp", "shrimp", 0.01, "04",
                 note="per roughly 10 adult shrimp"),
    ],
}


def portions_for(day: date, week_a: date, portions: list[Portion]) -> list[Portion]:
    """Return the portions due on a local calendar date."""
    weekday = str(day.weekday())
    week = "a" if (day - week_a).days // 7 % 2 == 0 else "b"
    return [
        portion
        for portion in portions
        if portion["grams"] > 0
        and (
            weekday in portion["weekly_days"]
            or (portion["alternate_week"] == week and weekday in portion["alternate_days"])
        )
    ]


def portion_label(portion: Portion, foods: dict[str, Food]) -> str:
    """Show the current catalogue name and the optional recipient."""
    food = foods.get(portion["food_id"])
    name = food["name"] if food else "Food entry unavailable"
    recipient = portion["recipient"]
    return f"{recipient}: {name}" if recipient else name


def format_meal(portions: list[Portion], foods: dict[str, Food]) -> str:
    """Format one line per portion for dashboards and notifications."""
    lines = []
    for portion in portions:
        line = f'{portion_label(portion, foods)} · {portion["grams"]:.2f} g'
        if portion["note"]:
            line += f' ({portion["note"]})'
        lines.append(line)
    return "\n".join(lines)

