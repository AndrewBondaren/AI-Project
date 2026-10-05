"""Pure POJO↔row projection. No SQL writer, reference queries or remint."""

from dataclasses import dataclass, fields
from collections.abc import Sequence

from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionSide import TransitionSide, TransitionSideId
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.models.transition import TransitionRow
from app.db.models.transitionSide import TransitionSideRow


@dataclass(frozen=True)
class TransitionRows:
    transition: TransitionRow
    sides: tuple[TransitionSideRow, TransitionSideRow]


def validate_transition_row_projection() -> None:
    """A new POJO field must be projected, never silently dropped by intersection."""
    endpoint_names = {side.value for side in TransitionSideId}
    side_names = {f"side_{side}" for side in TransitionSideId}
    scalar_names = Transition.model_fields.keys() - endpoint_names - side_names
    endpoint_columns = {f"{side}_{name}" for side in TransitionSideId
                        for name in TransitionEndpoint.model_fields}
    expected = scalar_names | endpoint_columns
    actual = {field.name for field in fields(TransitionRow)}
    if actual != expected:
        raise RuntimeError(f"TransitionRow/POJO projection mismatch: {sorted(actual ^ expected)}")


validate_transition_row_projection()


def to_transition_rows(transition: Transition) -> TransitionRows:
    wire = transition.model_dump(mode="json")
    scalar_fields = {field.name for field in fields(TransitionRow)} & Transition.model_fields.keys()
    projected = {name: wire[name] for name in scalar_fields}
    for side, endpoint in ((TransitionSideId.A, transition.a), (TransitionSideId.B, transition.b)):
        projected.update({f"{side}_{name}": value
                          for name, value in endpoint.model_dump(mode="json").items()})
    row = TransitionRow(**projected)
    sides = tuple(
        TransitionSideRow(transition_uid=transition.transition_uid, side=side.value,
                          **state.model_dump(mode="json"))
        for side, state in ((TransitionSideId.A, transition.side_a),
                            (TransitionSideId.B, transition.side_b))
    )
    return TransitionRows(row, sides)


def from_transition_rows(
    row: TransitionRow,
    sides: Sequence[TransitionSideRow],
    *,
    registry: WorldTransitionTypeRegistry,
) -> Transition:
    if len(sides) != len(TransitionSideId):
        raise ValueError("transition aggregate requires exactly two sides")
    by_side = {TransitionSideId(side.side): side for side in sides}
    if set(by_side) != set(TransitionSideId):
        raise ValueError("transition aggregate requires sides a and b")
    if any(side.transition_uid != row.transition_uid for side in sides):
        raise ValueError("side belongs to another transition")
    scalar_fields = {field.name for field in fields(TransitionRow)} & Transition.model_fields.keys()
    wire = {name: getattr(row, name) for name in scalar_fields}
    for side in TransitionSideId:
        wire[side.value] = {name: getattr(row, f"{side}_{name}")
                            for name in TransitionEndpoint.model_fields}
        wire[f"side_{side}"] = {name: getattr(by_side[side], name)
                                for name in TransitionSide.model_fields}
    return Transition.model_validate(wire, context={"transition_type_registry": registry})
