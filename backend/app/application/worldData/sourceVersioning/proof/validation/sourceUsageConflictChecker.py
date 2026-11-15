"""Revision conflicts among usable leaf facts from original request positions."""

from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceErrors import SourceLogicCode, SourceLogicIssue
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class SourceUsageConflictChecker:
    def check(self, *,
              captures: tuple[tuple[int | None, int, SourceCaptureRef], ...],
              dependencies: tuple[tuple[int | None, int, int, SourceCaptureRef,
                                        SourceVersionRef | SourceCollectionVersionRef], ...],
              ) -> tuple[SourceLogicIssue, ...]:
        if type(captures) is not tuple or type(dependencies) is not tuple:
            raise TypeError("facts must be tuples")
        positions: dict[tuple[int | None, int], SourceCaptureRef] = {}
        ranks: dict[tuple[int | None, int], int] = {}
        previous_position: tuple[int, int] | None = None
        grouped = captures[0][0] is not None if captures else False
        for group, use, capture in captures:
            self._indices(group, use)
            if (group is not None) != grouped:
                raise ValueError("single and grouped capture positions cannot be mixed")
            original_order = (group if group is not None else 0, use)
            if previous_position is not None and original_order <= previous_position:
                raise ValueError("capture facts must preserve unique original positions")
            previous_position = original_order
            SourceCaptureRef.model_validate(capture, strict=True)
            position = (group, use)
            if position in positions:
                raise ValueError("duplicate capture position")
            positions[position] = capture
            ranks[position] = len(ranks)

        errors = ValidatorAggregationHelper[SourceLogicIssue]((SourceLogicIssue,))
        seen: dict[tuple[SourceCaptureRef, object], SourceVersionRef | SourceCollectionVersionRef] = {}
        previous_order: tuple[int, int, int] | None = None
        for group, use, index, capture, source in dependencies:
            self._indices(group, use)
            if type(index) is not int or index < 0:
                raise ValueError("dependency index must be a non-negative integer")
            position = (group, use)
            if position not in positions or positions[position] != capture:
                raise ValueError("dependency fact differs from its capture position")
            if type(source) is SourceVersionRef:
                SourceVersionRef.model_validate(source, strict=True)
                identity, category = source.object_id, 0
            elif type(source) is SourceCollectionVersionRef:
                SourceCollectionVersionRef.model_validate(source, strict=True)
                identity, category = source.collection_id, 1
            else:
                raise TypeError("expected an exact Source version ref")
            order = (ranks[position], category, index)
            if previous_order is not None and order <= previous_order:
                raise ValueError("dependency facts must preserve unique original positions")
            previous_order = order
            key = (capture, identity)
            previous = seen.get(key)
            if previous is not None and previous.revision != source.revision:
                errors.add(SourceLogicIssue(code=SourceLogicCode.REVISION_CONFLICT,
                    group_index=group, use_index=use, source=source, artifact=capture.artifact))
            else:
                seen[key] = source
        return errors.snapshot()

    @staticmethod
    def _indices(group: int | None, use: int) -> None:
        if group is not None and (type(group) is not int or group < 0):
            raise ValueError("group index must be a non-negative integer")
        if type(use) is not int or use < 0:
            raise ValueError("use index must be a non-negative integer")
