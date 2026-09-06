from typing import Type

from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler


class AssemblerRegistry:
    """Assemble *kind* → class: ``building`` / ``ruins`` / ``resourceExtraction`` / ``vastHull``.

    Not catalog ``structure_type`` (tavern, mine, town_hall) and not ``system_name``.
    """

    def __init__(self) -> None:
        self._assemblers: dict[str, Type[BaseStructureAssembler]] = {}

    def register(self, kind: str):
        def decorator(cls: Type[BaseStructureAssembler]) -> Type[BaseStructureAssembler]:
            if kind in self._assemblers:
                raise ValueError(f"Assembler for kind={kind!r} already registered")
            if not issubclass(cls, BaseStructureAssembler):
                raise TypeError(f"{cls.__name__} must subclass BaseStructureAssembler")
            self._assemblers[kind] = cls
            return cls
        return decorator

    def get(self, kind: str) -> BaseStructureAssembler:
        if kind not in self._assemblers:
            raise KeyError(
                f"No assembler registered for kind={kind!r}. "
                f"Registered kinds: {list(self._assemblers)}"
            )
        return self._assemblers[kind]()

    def all(self) -> dict[str, Type[BaseStructureAssembler]]:
        return dict(self._assemblers)


ASSEMBLER_REGISTRY = AssemblerRegistry()
