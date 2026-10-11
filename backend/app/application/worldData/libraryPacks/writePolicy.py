"""Single pure copy/replace decision boundary — packs TZ §0.3.

The inspector supplies facts; the planner allocates identities and prepares
content; the executor writes. This class does none of those jobs.
"""
from app.application.worldData.libraryPacks.writeContracts import (
    LibraryWriteRequest, LibraryWriteSelection, WriteAction, WriteChoice,
    WriteDecision, WriteItemDecision, WriteItemSnapshot, WriteObjectKind,
    WriteOption, WritePolicy, WriteSnapshot, WriteSourceKind, WriteStatus, WriteTarget,
)


class LibraryWritePolicy:
    """Decide the complete batch or return no executable actions."""

    def decide(self, snapshot: WriteSnapshot, request: LibraryWriteRequest) -> WriteDecision:
        if tuple(f.item for f in snapshot.items) != request.items or not snapshot.preview_token:
            return self._result(snapshot, WriteStatus.REJECTED, issues=("snapshot_request_mismatch",))
        choices = tuple(self._choice(f) for f in snapshot.items)
        blocked = tuple(f"{f.item.item_key}:{reason}"
                        for f in snapshot.items for reason in self._destination_issues(f))
        if blocked:
            return self._result(snapshot, WriteStatus.REJECTED, choices=choices, issues=blocked)
        # A returned token remains mandatory even when all former matches disappeared.
        needs_token = request.preview_token is not None or (
            bool(request.decisions) and any(f.matches for f in snapshot.items))
        if needs_token and request.preview_token != snapshot.preview_token:
            return self._result(snapshot, WriteStatus.POLICY_REQUIRED, choices=choices,
                                stale=request.preview_token is not None)
        selections = {s.item_key: s for s in request.decisions}
        actions, issues, pending = [], [], False
        for facts, choice in zip(snapshot.items, choices):
            selected = selections.get(facts.item.item_key)
            if selected is None:
                if facts.matches:
                    pending = True
                else:
                    actions.append(WriteItemDecision(facts.item.item_key, WriteAction.CREATE))
                continue
            errors = self._selection_issues(facts, choice, selected)
            if errors:
                issues.extend(f"{facts.item.item_key}:{error}" for error in errors)
            else:
                actions.append(WriteItemDecision(facts.item.item_key, WriteAction(selected.policy.value),
                                                 selected.target_uid, selected.copy_system_name))
        if issues:
            return self._result(snapshot, WriteStatus.REJECTED, choices=choices, issues=tuple(issues))
        if pending:
            return self._result(snapshot, WriteStatus.POLICY_REQUIRED, choices=choices)
        # Multiple inputs must not overwrite one target in the same transaction.
        replaced = [a.target_uid for a in actions if a.action is WriteAction.REPLACE]
        copied_keys = [a.copy_system_name for a in actions if a.copy_system_name is not None]
        if len(set(replaced)) != len(replaced) or len(set(copied_keys)) != len(copied_keys):
            return self._result(snapshot, WriteStatus.REJECTED, choices=choices,
                                issues=("duplicate_batch_destination",))
        return self._result(snapshot, WriteStatus.READY, actions=tuple(actions))

    @staticmethod
    def _destination_issues(facts: WriteItemSnapshot) -> tuple[str, ...]:
        reasons = list(facts.issues)
        target, item = facts.destination, facts.item
        if target.owner_world_uid != item.owner_world_uid:
            reasons.append("destination_owner_unavailable")
        if target.is_default:
            reasons.append("destination_default_read_only")
        if not target.writable:
            reasons.append("destination_not_writable")
        if item.object_kind is WriteObjectKind.MEMBER and target.uid != item.target_pack_uid:
            reasons.append("destination_pack_mismatch")
        if (item.object_kind is WriteObjectKind.MEMBER
                and item.source.kind is WriteSourceKind.CATALOG
                and facts.source_owner_world_uid != item.owner_world_uid):
            reasons.append("member_copy_cannot_cross_scope")
        return tuple(reasons)

    @staticmethod
    def _replacement_issues(target: WriteTarget, facts: WriteItemSnapshot) -> tuple[str, ...]:
        reasons = []
        if target.owner_world_uid != facts.item.owner_world_uid:
            reasons.append("target_owner_unavailable")
        if target.is_default:
            reasons.append("target_default_read_only")
        if not target.writable:
            reasons.append("target_not_writable")
        return tuple(reasons)

    def _choice(self, facts: WriteItemSnapshot) -> WriteChoice:
        blocked = self._destination_issues(facts)
        options = (WriteOption(WritePolicy.COPY, reasons=blocked),) + tuple(
            WriteOption(WritePolicy.REPLACE, target.uid,
                        blocked + self._replacement_issues(target, facts))
            for target in facts.matches)
        return WriteChoice(facts.item.item_key, facts.matches, options)

    @staticmethod
    def _selection_issues(facts: WriteItemSnapshot, choice: WriteChoice,
                          selected: LibraryWriteSelection) -> tuple[str, ...]:
        option = next((o for o in choice.options
                       if o.policy is selected.policy and o.target_uid == selected.target_uid), None)
        if option is None:
            return ("target_not_in_matches",)
        if not option.allowed:
            return option.reasons
        if selected.policy is WritePolicy.COPY:
            if facts.item.object_kind is WriteObjectKind.PACK:
                if not selected.copy_system_name:
                    return ("copy_system_name_required",)
                if selected.copy_system_name != facts.copy_system_name:
                    return ("copy_identity_not_inspected",)
                if not facts.copy_identity_available:
                    return ("copy_identity_occupied",)
            elif selected.copy_system_name is not None:
                return ("member_copy_forbids_copy_system_name",)
        return ()

    @staticmethod
    def _result(snapshot: WriteSnapshot, status: WriteStatus, **kwargs) -> WriteDecision:
        return WriteDecision(status=status, preview_token=snapshot.preview_token, **kwargs)
