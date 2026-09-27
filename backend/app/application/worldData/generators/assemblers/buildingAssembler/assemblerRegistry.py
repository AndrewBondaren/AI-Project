from typing import Type

from app.application.worldData.generators.assemblers.buildingAssembler.baseBuildingAssembler import BaseBuildingAssembler


class AssemblerRegistry:
    """Assemble *kind* → class: ``building`` / ``ruins`` / ``resourceExtraction`` / ``vastHull``.

    Not catalog ``structure_type`` (tavern, mine, town_hall) and not ``system_name``.
    """

    def __init__(self) -> None:
        self._assemblers: dict[str, Type[BaseBuildingAssembler]] = {}

    def register(self, kind: str):
        def decorator(cls: Type[BaseBuildingAssembler]) -> Type[BaseBuildingAssembler]:
            if kind in self._assemblers:
                raise ValueError(f"Assembler for kind={kind!r} already registered")
            if not issubclass(cls, BaseBuildingAssembler):
                raise TypeError(f"{cls.__name__} must subclass BaseBuildingAssembler")
            self._assemblers[kind] = cls
            return cls
        return decorator

    def get(self, kind: str) -> BaseBuildingAssembler:
        if kind not in self._assemblers:
            raise KeyError(
                f"No assembler registered for kind={kind!r}. "
                f"Registered kinds: {list(self._assemblers)}"
            )
        return self._assemblers[kind]()

    def all(self) -> dict[str, Type[BaseBuildingAssembler]]:
        return dict(self._assemblers)


BUILDING_ASSEMBLER_REGISTRY = AssemblerRegistry()
