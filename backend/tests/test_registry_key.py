"""RegistryKey[R] — N1-W identity branded string, not a bare str."""

from __future__ import annotations

import unittest
from typing import get_origin

from app.dataModel.annotationPolicy import (
    DefaultOnWire,
    StrictOnWire,
    WireFieldPolicy,
    field_policy,
    unwrap_wire_type,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.registryKey import RegistryKey, registry_key_target
from app.dataModel.settlement.settlement.settlementSizeEntry import SettlementSizeEntry
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    SettlementSizeKey,
    WorldSettlementSizeRegistry,
)


class TestRegistryKey(unittest.TestCase):
    def test_wire_str_coerces_to_branded_key(self) -> None:
        entry = SettlementSizeEntry(system_size="small")
        self.assertIsInstance(entry.system_size, RegistryKey)
        self.assertEqual(entry.system_size, "small")
        self.assertEqual(entry.model_dump(mode="json")["system_size"], "small")

    def test_empty_key_rejected(self) -> None:
        with self.assertRaises(Exception):
            SettlementSizeEntry(system_size="")

    def test_canonical_keys_are_branded(self) -> None:
        medium = WorldSettlementSizeRegistry.default_system_size()
        self.assertIsInstance(medium, RegistryKey)
        self.assertEqual(
            medium,
            WorldSettlementSizeRegistry.canonical_defaults().root[1].system_size,
        )

    def test_annotation_points_at_size_registry(self) -> None:
        annotation = SettlementSizeEntry.model_fields["system_size"].annotation
        self.assertEqual(field_policy(annotation), WireFieldPolicy.STRICT_ON_WIRE)
        self.assertIs(
            registry_key_target(annotation),
            WorldSettlementSizeRegistry,
        )
        inner = unwrap_wire_type(annotation)
        self.assertIs(get_origin(inner), RegistryKey)
        self.assertIs(registry_key_target(SettlementSizeKey), WorldSettlementSizeRegistry)
        self.assertIs(
            registry_key_target(DefaultOnWire[SettlementSizeKey | None]),
            WorldSettlementSizeRegistry,
        )

    def test_size_key_is_not_location_type_key(self) -> None:
        loc_ann = StrictOnWire[RegistryKey[WorldLocationTypeRegistry]]
        self.assertIs(registry_key_target(loc_ann), WorldLocationTypeRegistry)
        self.assertIsNot(
            registry_key_target(loc_ann),
            registry_key_target(SettlementSizeEntry.model_fields["system_size"].annotation),
        )


if __name__ == "__main__":
    unittest.main()
