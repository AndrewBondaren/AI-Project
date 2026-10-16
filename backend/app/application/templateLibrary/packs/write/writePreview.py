"""Read-only previews through the same policy and batch planner as apply."""
from dataclasses import replace
from itertools import product

from app.application.worldData.libraryPacks.errors import LibraryPackError
from app.application.worldData.libraryPacks.writeContracts import (
    LibraryWriteSelection, WriteItemDecision, WriteAction, WriteObjectKind, WritePolicy, WriteStatus,
)
from app.application.worldData.libraryPacks.writeResults import CopyPreview, WritePreview


def prepare_preview(snapshot, request, decision, policy, planner):
    variants, choices = [], []
    facts = {f.item.item_key: f for f in snapshot.items}
    sources = dict(snapshot.inspection.sources)
    for choice in decision.choices:
        replacements = tuple(LibraryWriteSelection(item_key=choice.item_key,
            policy=o.policy, target_uid=o.target_uid) for o in choice.options
            if o.allowed and o.policy is WritePolicy.REPLACE)
        if choice.matches:
            choices.append(replacements)
        # Unknown copy identity cannot be minted or advertised as committed.
        if any(o.allowed and o.policy is WritePolicy.COPY for o in choice.options):
            item, source = facts[choice.item_key].item, sources[choice.item_key]
            pack_copy = item.object_kind is WriteObjectKind.PACK
            variants.append(WritePreview((WriteItemDecision(choice.item_key, WriteAction.COPY),),
                copy=CopyPreview(tuple(m.member.template_uid for m in source.members), item.owner_world_uid,
                    item.target_pack_uid, pack_copy, pack_copy)))
    for selections in product(*choices):
        candidate = request.model_copy(update={"decisions": tuple(selections),
                                                "preview_token": snapshot.preview_token})
        approved = policy.decide(snapshot, candidate)
        if approved.status is not WriteStatus.READY:
            continue
        try:
            variants.append(WritePreview(approved.actions, planner.prepare(snapshot, approved)))
        except (LibraryPackError, ValueError) as exc:
            variants.append(WritePreview(approved.actions, issues=(str(exc),)))
    # A copy-only match elsewhere must not hide another item's replace diff.
    # These alternatives explicitly describe just one item; other inputs are
    # unchanged in this conditional projection, not silently assigned a policy.
    covered = {action.item_key for variant in variants for action in variant.actions
               if action.action is WriteAction.REPLACE}
    for choice in decision.choices:
        if choice.item_key in covered:
            continue
        item = facts[choice.item_key].item
        for option in choice.options:
            if not option.allowed or option.policy is not WritePolicy.REPLACE:
                continue
            candidate = request.model_copy(update={"items": (item,), "decisions": (
                LibraryWriteSelection(item_key=item.item_key, policy="replace", target_uid=option.target_uid),),
                "preview_token": snapshot.preview_token})
            alternative = replace(snapshot, items=(facts[choice.item_key],))
            approved = policy.decide(alternative, candidate)
            if approved.status is WriteStatus.READY:
                try:
                    variants.append(WritePreview(approved.actions, planner.prepare(alternative, approved)))
                except (LibraryPackError, ValueError) as exc:
                    variants.append(WritePreview(approved.actions, issues=(str(exc),)))
    return tuple(variants)
