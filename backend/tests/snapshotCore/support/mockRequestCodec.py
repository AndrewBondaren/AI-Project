"""Explicit mock for tests of post-admission private stages, never admission evidence."""
from unittest.mock import Mock
from app.application.patch.encoding.patchSetCodec import PatchSetCodec


def mock_request_codec(registry):
    codec = Mock(spec=PatchSetCodec)
    codec.registry = registry
    codec.validate_request.side_effect = AssertionError("post-admission fixture must not admit requests")
    codec.fingerprint.side_effect = AssertionError("post-admission fixture must not fingerprint requests")
    return codec
