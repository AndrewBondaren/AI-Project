"""RAM cache contract for exact manifest bytes. Pack owns artifact admission."""


class ManifestBytesCodec:
    def validate(self, value: object) -> bytes:
        if type(value) is not bytes:
            raise ValueError("manifest cache requires bytes")
        return value

    def encode(self, value: bytes) -> bytes:
        return self.validate(value)

    def decode(self, encoded: bytes) -> bytes:
        return self.validate(encoded)

    def retained_bytes(self, value: bytes) -> int:
        return len(value)
