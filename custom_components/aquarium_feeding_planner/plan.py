"""Default food catalogue, feeding presets and calendar logic."""
from datetime import date
from hashlib import sha256
import json
from typing import TypedDict
from uuid import uuid4

DOMAIN = "aquarium_feeding_planner"
DEFAULT_WEEK_A = "2026-11-09"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class Food(TypedDict):
    name: str
    url: str


class DayPortion(TypedDict):
    recipient: str
    food_id: str
    grams: float
    note: str


class Portion(DayPortion):
    id: str
    weekly_days: list[str]
    alternate_days: list[str]
    alternate_week: str


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


def rotation_week(day: date, week_a: date) -> str:
    """Return the rotation week of a local calendar date."""
    return "a" if (day - week_a).days // 7 % 2 == 0 else "b"


def _applies(portion: Portion, week: str, weekday: str) -> bool:
    return weekday in portion["weekly_days"] or (
        week == portion["alternate_week"] and weekday in portion["alternate_days"]
    )


def portions_for(day: date, week_a: date, portions: list[Portion]) -> list[Portion]:
    """Return the unpaused portions due on a local calendar date."""
    week = rotation_week(day, week_a)
    return [
        portion
        for portion in portions
        if portion["grams"] > 0 and _applies(portion, week, str(day.weekday()))
    ]


def schedule_by_day(portions: list[Portion]) -> dict[str, list[list[DayPortion]]]:
    """Expose both weeks for the editor, including paused portions."""
    return {
        week: [
            [
                DayPortion(food_id=p["food_id"], recipient=p["recipient"], grams=p["grams"], note=p["note"])
                for p in portions
                if _applies(p, week, str(weekday))
            ]
            for weekday in range(len(WEEKDAYS))
        ]
        for week in ("a", "b")
    }


def schedule_revision(portions: list[Portion]) -> str:
    """Identify the plan a dashboard editor has opened."""
    return sha256(json.dumps(portions, sort_keys=True).encode()).hexdigest()


def replace_day(
    portions: list[Portion], week: str, weekday: int, meals: list[DayPortion]
) -> list[Portion]:
    """Replace one day in one rotation week, preserving every other day."""
    day = str(weekday)
    result = []
    for portion in portions:
        if not _applies(portion, week, day):
            result.append(portion)
            continue

        days = {
            key: {str(i) for i in range(len(WEEKDAYS)) if _applies(portion, key, str(i))}
            for key in ("a", "b")
        }
        days[week].discard(day)
        if not days["a"] and not days["b"]:
            continue
        weekly = days["a"] & days["b"]
        alternating = [(key, sorted(days[key] - weekly)) for key in ("a", "b") if days[key] - weekly]
        for index, (alternate_week, extra_days) in enumerate(alternating or [("a", [])]):
            result.append({
                **portion,
                "id": uuid4().hex if index else portion["id"],
                "weekly_days": [] if index else sorted(weekly),
                "alternate_days": extra_days,
                "alternate_week": alternate_week,
            })

    for meal in meals:
        result.append({
            **meal,
            "id": uuid4().hex,
            "weekly_days": [],
            "alternate_days": [day],
            "alternate_week": week,
        })
    return result


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
