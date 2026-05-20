from app.application.cancellation.cancellationToken import CancellationToken


class CancellationRegistry:

    def __init__(self):
        self._tokens: dict[str, CancellationToken] = {}

    def register(self, token: CancellationToken) -> None:
        self._tokens[token.request_id] = token

    def cancel(self, request_id: str) -> bool:
        token = self._tokens.get(request_id)
        if token:
            token.cancel()
            return True
        return False

    def remove(self, request_id: str) -> None:
        self._tokens.pop(request_id, None)


cancellation_registry = CancellationRegistry()
