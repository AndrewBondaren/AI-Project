from typing import Type

from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler


class AssemblerRegistry:

    def __init__(self) -> None:
        self._assemblers: dict[str, Type[BaseStructureAssembler]] = {}

    def register(self, structure_type: str):
        def decorator(cls: Type[BaseStructureAssembler]) -> Type[BaseStructureAssembler]:
            if structure_type in self._assemblers:
                raise ValueError(f"Assembler for '{structure_type}' already registered")
            if not issubclass(cls, BaseStructureAssembler):
                raise TypeError(f"{cls.__name__} must subclass BaseStructureAssembler")
            self._assemblers[structure_type] = cls
            return cls
        return decorator

    def get(self, structure_type: str) -> BaseStructureAssembler:
        if structure_type not in self._assemblers:
            raise KeyError(
                f"No assembler registered for structure_type='{structure_type}'. "
                f"Registered types: {list(self._assemblers)}"
            )
        return self._assemblers[structure_type]()

    def all(self) -> dict[str, Type[BaseStructureAssembler]]:
        return dict(self._assemblers)


ASSEMBLER_REGISTRY = AssemblerRegistry()
