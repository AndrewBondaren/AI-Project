"""Engine-locked building / plot purposes — NPC and economy bind to these keys.

Not N+1 world overlay. Drawings (``system_name``) stay many-per-purpose.
Plot types = union of buildings on the plot. Match: ``like`` vs ``strict``.

Not plot purposes (unless master reopens): ``lamp_post``, ``portal``, ``air_dock``.
``dungeon`` is settlement morphology, not a house purpose. Fallback omit → ``house``.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class BuildingPurpose(StrEnum):
    """Purpose tag on a building drawing. Fallback / omit → ``house``."""

    HOUSE = "house"
    INN = "inn"
    BARRACKS = "barracks"

    TOWN_HALL = "town_hall"
    PLAZA = "plaza"
    TEMPLE = "temple"
    SHRINE = "shrine"
    THEATER = "theater"
    LIBRARY = "library"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    BATHHOUSE = "bathhouse"
    PRISON = "prison"
    COURTHOUSE = "courthouse"

    TAVERN = "tavern"
    SHOP = "shop"
    BAKERY = "bakery"
    BUTCHER = "butcher"
    FISHMONGER = "fishmonger"
    GREENGROCER = "greengrocer"
    APOTHECARY = "apothecary"
    TAILOR = "tailor"
    COBBLER = "cobbler"
    JEWELER = "jeweler"
    BOOKSELLER = "bookseller"
    MARKET = "market"
    GUILD = "guild"
    WAREHOUSE = "warehouse"
    GRANARY = "granary"

    WORKSHOP = "workshop"
    SMITHY = "smithy"
    CARPENTER = "carpenter"
    TANNERY = "tannery"
    WEAVER = "weaver"
    POTTER = "potter"
    GLASSBLOWER = "glassblower"
    BREWERY = "brewery"
    WINERY = "winery"
    CHANDLER = "chandler"

    MINE = "mine"
    QUARRY = "quarry"
    LUMBER_CAMP = "lumber_camp"
    MILL = "mill"
    SMELTER = "smelter"
    SAWMILL = "sawmill"
    SHIPYARD = "shipyard"
    KILN = "kiln"

    FARM = "farm"
    ORCHARD = "orchard"
    VINEYARD = "vineyard"
    LIVESTOCK = "livestock"
    STABLE = "stable"
    APIARY = "apiary"
    FISHERY = "fishery"

    GATEHOUSE = "gatehouse"
    WATCHTOWER = "watchtower"
    DOCK = "dock"

    @classmethod
    def from_wire(cls, key: object) -> BuildingPurpose | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        if not norm:
            return None
        for member in cls:
            if member.value == norm:
                return member
        return None


class BuildingPurposeMatch(StrEnum):
    """How a plot purpose array is tested against a filter (district allowed / need)."""

    LIKE = "like"
    STRICT = "strict"

    @classmethod
    def from_wire(cls, key: object) -> BuildingPurposeMatch | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        if not norm:
            return None
        for member in cls:
            if member.value == norm:
                return member
        return None


HOUSE = BuildingPurpose.HOUSE
DEFAULT_BUILDING_PURPOSES: tuple[BuildingPurpose, ...] = (HOUSE,)
DEFAULT_PURPOSE_MATCH = BuildingPurposeMatch.LIKE

PURPOSE_DISPLAY: dict[BuildingPurpose, str] = {
    BuildingPurpose.HOUSE: "Жилой дом",
    BuildingPurpose.INN: "Постоялый двор",
    BuildingPurpose.BARRACKS: "Казарма",
    BuildingPurpose.TOWN_HALL: "Ратуша",
    BuildingPurpose.PLAZA: "Площадь",
    BuildingPurpose.TEMPLE: "Храм",
    BuildingPurpose.SHRINE: "Святилище",
    BuildingPurpose.THEATER: "Театр",
    BuildingPurpose.LIBRARY: "Библиотека",
    BuildingPurpose.SCHOOL: "Школа",
    BuildingPurpose.HOSPITAL: "Лазарет",
    BuildingPurpose.BATHHOUSE: "Баня",
    BuildingPurpose.PRISON: "Тюрьма",
    BuildingPurpose.COURTHOUSE: "Суд",
    BuildingPurpose.TAVERN: "Таверна",
    BuildingPurpose.SHOP: "Лавка",
    BuildingPurpose.BAKERY: "Пекарня",
    BuildingPurpose.BUTCHER: "Мясная",
    BuildingPurpose.FISHMONGER: "Рыбная",
    BuildingPurpose.GREENGROCER: "Овощная",
    BuildingPurpose.APOTHECARY: "Аптека",
    BuildingPurpose.TAILOR: "Портной",
    BuildingPurpose.COBBLER: "Сапожник",
    BuildingPurpose.JEWELER: "Ювелир",
    BuildingPurpose.BOOKSELLER: "Книжная",
    BuildingPurpose.MARKET: "Рынок",
    BuildingPurpose.GUILD: "Гильдия",
    BuildingPurpose.WAREHOUSE: "Склад",
    BuildingPurpose.GRANARY: "Амбар",
    BuildingPurpose.WORKSHOP: "Мастерская",
    BuildingPurpose.SMITHY: "Кузница",
    BuildingPurpose.CARPENTER: "Плотницкая",
    BuildingPurpose.TANNERY: "Кожевня",
    BuildingPurpose.WEAVER: "Ткацкая",
    BuildingPurpose.POTTER: "Гончарная",
    BuildingPurpose.GLASSBLOWER: "Стекольная",
    BuildingPurpose.BREWERY: "Пивоварня",
    BuildingPurpose.WINERY: "Винодельня",
    BuildingPurpose.CHANDLER: "Свечная",
    BuildingPurpose.MINE: "Шахта",
    BuildingPurpose.QUARRY: "Каменоломня",
    BuildingPurpose.LUMBER_CAMP: "Лесозаготовка",
    BuildingPurpose.MILL: "Мельница",
    BuildingPurpose.SMELTER: "Плавильня",
    BuildingPurpose.SAWMILL: "Лесопилка",
    BuildingPurpose.SHIPYARD: "Верфь",
    BuildingPurpose.KILN: "Обжиг",
    BuildingPurpose.FARM: "Ферма",
    BuildingPurpose.ORCHARD: "Сад",
    BuildingPurpose.VINEYARD: "Виноградник",
    BuildingPurpose.LIVESTOCK: "Скот",
    BuildingPurpose.STABLE: "Конюшня",
    BuildingPurpose.APIARY: "Пасека",
    BuildingPurpose.FISHERY: "Рыбный промысел",
    BuildingPurpose.GATEHOUSE: "Надвратная",
    BuildingPurpose.WATCHTOWER: "Сторожка",
    BuildingPurpose.DOCK: "Причал",
}


def coerce_purpose_list(
    raw: object,
    *,
    empty_as_house: bool = True,
) -> list[BuildingPurpose]:
    """Wire string / list → unique purposes. Unknown keys dropped.

    Building drawings: empty → ``[house]``. District ``allowed``: empty stays empty.
    """
    if raw is None:
        return list(DEFAULT_BUILDING_PURPOSES) if empty_as_house else []
    if isinstance(raw, BuildingPurpose):
        return [raw]
    items: list[object]
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return list(DEFAULT_BUILDING_PURPOSES) if empty_as_house else []
    out: list[BuildingPurpose] = []
    seen: set[BuildingPurpose] = set()
    for item in items:
        purpose = BuildingPurpose.from_wire(item)
        if purpose is None or purpose in seen:
            continue
        seen.add(purpose)
        out.append(purpose)
    if not out and empty_as_house:
        return list(DEFAULT_BUILDING_PURPOSES)
    return out


def coerce_purpose_match(raw: object) -> BuildingPurposeMatch:
    parsed = BuildingPurposeMatch.from_wire(raw)
    return parsed if parsed is not None else DEFAULT_PURPOSE_MATCH


def union_plot_purposes(
    buildings: Iterable[object],
) -> tuple[BuildingPurpose, ...]:
    """Union of ``structure_types`` on every building of a plot."""
    out: list[BuildingPurpose] = []
    seen: set[BuildingPurpose] = set()
    for building in buildings:
        types = getattr(building, "structure_types", None)
        if not types:
            raw = getattr(building, "structure_type", None)
            types = coerce_purpose_list(raw, empty_as_house=True)
        for purpose in types:
            parsed = purpose if isinstance(purpose, BuildingPurpose) else BuildingPurpose.from_wire(purpose)
            if parsed is None or parsed in seen:
                continue
            seen.add(parsed)
            out.append(parsed)
    return tuple(out) if out else DEFAULT_BUILDING_PURPOSES


def purposes_match(
    plot: Iterable[BuildingPurpose],
    filt: Iterable[BuildingPurpose],
    mode: BuildingPurposeMatch,
) -> bool:
    """``like`` = nonempty intersection. ``strict`` = plot ⊆ filter (extras reject)."""
    plot_set = set(plot)
    filter_set = set(filt)
    if not filter_set:
        return False
    if mode is BuildingPurposeMatch.STRICT:
        return bool(plot_set) and plot_set <= filter_set
    return bool(plot_set & filter_set)


def primary_purpose(types: Iterable[BuildingPurpose]) -> BuildingPurpose:
    for purpose in types:
        return purpose
    return HOUSE
