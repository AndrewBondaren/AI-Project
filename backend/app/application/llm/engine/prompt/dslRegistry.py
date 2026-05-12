import os

class DSLRegistry:

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._cache = {}

    def get(self, key: str) -> str:

        if key in self._cache:
            return self._cache[key]

        path = os.path.join(self.base_path, f"{key}.txt")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self._cache[key] = content
        return content