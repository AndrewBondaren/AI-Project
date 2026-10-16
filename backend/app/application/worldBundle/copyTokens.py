"""Signed continuation of a rolled-back world copy; no persistence or policy."""
import base64
import hashlib
import hmac
import json
import secrets

from app.application.templateLibrary.packs.errors import LibraryPackValidationError


class WorldCopyTokens:
    def __init__(self):
        # Restart invalidates outstanding previews safely; no client-controlled UID map.
        self._key = secrets.token_bytes(32)

    def encode(self, context: dict, library_token: str) -> str:
        data = json.dumps({"context": context, "library_token": library_token},
                          sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self._key, data, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature + data).decode()

    def decode(self, token: str) -> dict:
        try:
            raw = base64.b64decode(token, altchars=b"-_", validate=True)
            signature, data = raw[:32], raw[32:]
            if not hmac.compare_digest(signature, hmac.new(self._key, data, hashlib.sha256).digest()):
                raise ValueError("signature mismatch")
            result = json.loads(data)
            if set(result) != {"context", "library_token"}:
                raise ValueError("invalid continuation")
            return result
        except (ValueError, TypeError) as exc:
            raise LibraryPackValidationError("invalid or expired world preview token; repeat import without token") from exc
