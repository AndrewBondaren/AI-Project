from dataclasses import dataclass


@dataclass
class CitySkeleton:
    """
    Поля скелета поселения. Создаётся CityAssembler из NamedLocation поселения
    и передаётся вниз по иерархии без изменений.

    Все поля nullable — поселение может существовать без части атрибутов.
    """
    economic_tier:        str | None   # ref → worlds.economic_tier_registry
    architectural_style:  str | None   # ref → worlds.architectural_style_registry
    dominant_material:    str | None   # ref → worlds.material_registry
    settlement_density:   str | None   # "sparse" | "medium" | "dense"
    system_city_size:     str | None   # ref → worlds.city_size_registry
    system_location_mood: str | None   # ref → worlds.location_mood_registry
