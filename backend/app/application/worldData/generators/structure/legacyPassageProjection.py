"""Temporary outward projection for legacy extract/debug; remove at F1."""

import json

from app.dataModel.locations.transitions.transition import Transition
from app.db.models.locationPassage import LocationPassage


def legacy_passages(transitions: list[Transition]) -> tuple[LocationPassage, ...]:
    return tuple(LocationPassage(
        passage_uid=item.transition_uid, world_uid=item.world_uid,
        from_level_uid=item.source.level_uid, from_x=item.source.x, from_y=item.source.y,
        to_level_uid=item.destination.level_uid, to_x=item.destination.x, to_y=item.destination.y,
        system_passage_type=item.system_transition_type, is_bidirectional=item.is_bidirectional,
        display_name=item.display_name, glossary_ref=item.glossary_ref,
        tag_refs=json.dumps(item.tag_refs) if item.tag_refs else None,
    ) for item in transitions)
