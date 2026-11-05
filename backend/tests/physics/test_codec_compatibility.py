"""Legacy imports preserve shared objects and canonical wire semantics."""
from hashlib import sha256
import unittest
from unittest.mock import patch

from app.application.encoding import canonicalCodec as legacy
from app.encoding import canonicalCodec as shared
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest


class CodecCompatibilityTests(unittest.TestCase):
    def test_shared_classes_private_decoder_and_legacy_patch_contract(self):
        for name in ("CanonicalCodec", "CanonicalEncodingError", "encode", "decode",
                     "content_digest", "merge_manifests", "_decode_scalar", "_decode_one", "_tuple"):
            self.assertIs(getattr(legacy, name), getattr(shared, name))
        manifest = CanonicalSchemaManifest(entries=())
        value = (None, True, 123, -1.5, "physics", b"bytes", frozenset({1, 2}))
        wire = shared.encode(value, manifest)
        self.assertEqual(legacy.decode(wire, tuple, manifest), value)
        self.assertEqual(legacy.digest(value, manifest), sha256(wire).digest())
        with patch.object(legacy, "content_digest", return_value=b"patched") as raw:
            self.assertEqual(legacy.digest(value, manifest), b"patched")
            raw.assert_called_once_with(wire)
        with self.assertRaises(legacy.CanonicalEncodingError):
            shared.decode(wire + b"trailing", tuple, manifest)
