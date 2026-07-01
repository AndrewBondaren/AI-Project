"""Root POJO for `worlds.road_settings` JSON array."""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry

_CANONICAL_ENTRIES: tuple[RoadSettingsEntry, ...] = (
    RoadSettingsEntry(
        system_connection_type="trail",
        curve_radius_factor=1,
        max_segment_length_m=30,
        min_segment_length_m=3,
        base_travel_modifier=1.4,
        condition_degradation=0.2,
    ),
    RoadSettingsEntry(
        system_connection_type="dirt_road",
        curve_radius_factor=2,
        max_segment_length_m=60,
        min_segment_length_m=5,
        base_travel_modifier=1.2,
        condition_degradation=0.4,
    ),
    RoadSettingsEntry(
        system_connection_type="alley",
        curve_radius_factor=2,
        max_segment_length_m=30,
        min_segment_length_m=3,
        base_travel_modifier=1.1,
        condition_degradation=0.3,
    ),
    RoadSettingsEntry(
        system_connection_type="road",
        curve_radius_factor=4,
        max_segment_length_m=100,
        min_segment_length_m=10,
        default_lanes_per_side=1,
        auto_sidewalk=True,
        base_travel_modifier=0.9,
        condition_degradation=0.6,
    ),
    RoadSettingsEntry(
        system_connection_type="highway",
        curve_radius_factor=8,
        max_segment_length_m=200,
        min_segment_length_m=20,
        default_lanes_per_side=2,
        auto_sidewalk=True,
        base_travel_modifier=0.7,
        condition_degradation=0.8,
    ),
    RoadSettingsEntry(
        system_connection_type="yard_path",
        curve_radius_factor=1,
        max_segment_length_m=20,
        min_segment_length_m=2,
        base_travel_modifier=1.3,
        condition_degradation=0.2,
    ),
)


class WorldRoadSettings(RootModel[list[RoadSettingsEntry]]):
    """Root POJO for `worlds.road_settings`. Wire shape: JSON array."""

    root: list[RoadSettingsEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldRoadSettings:
        """Full explicit array after normalize (equivalent to missing `[]`)."""
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_connection_type: str) -> RoadSettingsEntry | None:
        for entry in self.root:
            if entry.system_connection_type == system_connection_type:
                return entry
        return None
