from dataclasses import asdict
from unittest.mock import patch

from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.worldPack.read.pinnedManifest import (
    ManifestCachedRead, ManifestPinRead, ManifestReadReason, ManifestStorageRead,
)
from tests.spatial_pack.test_execution_pins import ExecutionPinFixture


class PinnedManifestTests(ExecutionPinFixture):
    async def test_cold_and_cached_reads_follow_pin_after_head_change(self):
        reader = self.manifest_reader
        pin = ManifestPinRead(**asdict(self.intent), max_bytes=self.manifest.nbytes)
        address = await reader.resolve(pin)
        self.assertEqual(address.ref, self.manifest)
        request = ManifestStorageRead(pin=pin, address=address)
        cold = await reader.read_verified(request)
        hit = ManifestCachedRead(pin=pin, address=address, entry=CacheEntry(key=address.key, value=cold.payload))
        await self.publish("b", 2)
        self.assertEqual(await reader.resolve(pin), address)
        with patch.object(self.fixture.backend, "read_verified", side_effect=AssertionError("unexpected IO")):
            self.assertEqual(await reader.admit_cached(hit), cold)
            damaged = hit.entry.model_copy(update={"value": b"x" * self.manifest.nbytes})
            self.assertEqual((await reader.admit_cached(hit.model_copy(update={"entry": damaged}))).reason,
                             ManifestReadReason.INVALID_MANIFEST)
            await self.pins.close(await self.stop())
            self.assertEqual((await reader.admit_cached(hit)).reason, ManifestReadReason.CLOSED_PIN)
            self.assertEqual((await reader.read_verified(request)).reason, ManifestReadReason.CLOSED_PIN)

    async def test_budget_identity_and_cache_key(self):
        reader = self.manifest_reader
        pin = ManifestPinRead(**asdict(self.intent), max_bytes=self.manifest.nbytes)
        address = await reader.resolve(pin)
        small = pin.model_copy(update={"max_bytes": self.manifest.nbytes - 1})
        foreign = pin.model_copy(update={"world_uid": "other"})
        bad_key = address.key.model_copy(update={"item_key": bytes(32)})
        wrong = address.model_copy(update={"key": bad_key})
        with patch.object(self.fixture.backend, "read_verified", side_effect=AssertionError("unexpected IO")):
            self.assertEqual((await reader.resolve(small)).reason, ManifestReadReason.BUDGET_EXCEEDED)
            self.assertEqual((await reader.resolve(foreign)).reason, ManifestReadReason.INVALID_PIN)
            self.assertEqual((await reader.read_verified(ManifestStorageRead(pin=pin, address=wrong))).reason,
                             ManifestReadReason.IDENTITY_MISMATCH)
            cached = ManifestCachedRead(pin=pin, address=address, entry=CacheEntry(key=bad_key, value=b""))
            self.assertEqual((await reader.admit_cached(cached)).reason, ManifestReadReason.IDENTITY_MISMATCH)
