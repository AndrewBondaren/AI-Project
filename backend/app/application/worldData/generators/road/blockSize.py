BLOCK_SIZE_BY_DENSITY: dict[str, int] = {
    "dense":  50,
    "medium": 80,
    "sparse": 120,
}
DEFAULT_BLOCK_SIZE = 80


def block_size_for_density(density: str | None) -> int:
    return BLOCK_SIZE_BY_DENSITY.get(density or "medium", DEFAULT_BLOCK_SIZE)
