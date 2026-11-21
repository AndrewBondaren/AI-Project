"""W-1 policy contract: explicit decisions, access and atomic batch negotiation."""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase

from pydantic import ValidationError

from app.application.templateLibrary.packs.write.writeContracts import (
    LibraryWriteItem, LibraryWriteRequest, LibraryWriteSelection, WriteAction,
    WriteItemSnapshot, WriteObjectKind, WritePolicy, WriteSnapshot, WriteSource,
    WriteSourceKind, WriteStatus, WriteTarget,
)
from app.application.templateLibrary.packs.write.writePolicy import LibraryWritePolicy
from app.ids import LibraryKind


def item(key="a", kind=WriteObjectKind.MEMBER, owner="world"):
    return LibraryWriteItem(item_key=key, object_kind=kind,
                            source=WriteSource(kind=WriteSourceKind.CATALOG, key="source"),
                            owner_world_uid=owner,
                            target_pack_uid="destination" if kind is WriteObjectKind.MEMBER else None,
                            library_kind=LibraryKind.STRUCTURE_TEMPLATES
                            if kind is WriteObjectKind.MEMBER else None)


def facts(entry=None, matches=True):
    entry = entry or item()
    return WriteItemSnapshot(entry, WriteTarget("destination", entry.owner_world_uid),
                             (WriteTarget("existing", entry.owner_world_uid),) if matches else (),
                             source_owner_world_uid=entry.owner_world_uid)


def selection(key="a", policy=WritePolicy.COPY, target=None, name=None):
    return LibraryWriteSelection(item_key=key, policy=policy,
                                 target_uid=target, copy_system_name=name)


class LibraryWritePolicyTests(TestCase):
    def decide(self, entries, decisions=(), token=None, current="current"):
        snapshot = WriteSnapshot(tuple(entries), current)
        request = LibraryWriteRequest(items=tuple(f.item for f in entries),
                                      decisions=tuple(decisions), preview_token=token)
        before = deepcopy((snapshot, request))
        with self.assertNoLogs(level="WARNING"):
            result = LibraryWritePolicy().decide(snapshot, request)
        self.assertEqual((snapshot, request), before)
        return result

    def test_no_match_creates_for_both_kinds_and_scopes(self):
        for kind in WriteObjectKind:
            for owner in (None, "world"):
                with self.subTest(kind=kind, owner=owner):
                    result = self.decide([facts(item(kind=kind, owner=owner), False)])
                    self.assertEqual(result.status, WriteStatus.READY)
                    self.assertEqual(result.actions[0].action, WriteAction.CREATE)

    def test_matches_require_policy_for_both_kinds_and_scopes(self):
        for kind in WriteObjectKind:
            for owner in (None, "world"):
                result = self.decide([facts(item(kind=kind, owner=owner))])
                self.assertEqual(result.status, WriteStatus.POLICY_REQUIRED)
                self.assertFalse(result.actions)
                self.assertEqual(result.preview_token, "current")

    def test_every_match_returned_and_replace_requires_exact_uid(self):
        f = replace(facts(), matches=(WriteTarget("one", "world"), WriteTarget("two", "world")))
        preview = self.decide([f])
        self.assertEqual([t.uid for t in preview.choices[0].matches], ["one", "two"])
        result = self.decide([f], [selection(policy=WritePolicy.REPLACE, target="two")], "current")
        self.assertEqual(result.actions[0].target_uid, "two")
        bad = self.decide([f], [selection(policy=WritePolicy.REPLACE, target="other")], "current")
        self.assertEqual(bad.status, WriteStatus.REJECTED)
        self.assertFalse(bad.actions)

    def test_member_copy_does_not_target_existing_identity(self):
        result = self.decide([facts()], [selection()], "current")
        self.assertEqual(result.actions[0].action, WriteAction.COPY)
        self.assertIsNone(result.actions[0].target_uid)

    def test_pack_copy_requires_inspected_free_new_identity(self):
        base = facts(item(kind=WriteObjectKind.PACK))
        cases = ((None, None, False, "copy_system_name_required"),
                 ("new.pack", None, False, "copy_identity_not_inspected"),
                 ("new.pack", "new.pack", False, "copy_identity_occupied"))
        for requested, inspected, available, error in cases:
            f = replace(base, copy_system_name=inspected, copy_identity_available=available)
            result = self.decide([f], [selection(name=requested)], "current")
            self.assertEqual(result.status, WriteStatus.REJECTED)
            self.assertIn("a:" + error, result.issues)
        f = replace(base, copy_system_name="new.pack", copy_identity_available=True)
        result = self.decide([f], [selection(name="new.pack")], "current")
        self.assertEqual(result.actions[0].copy_system_name, "new.pack")

    def test_member_cannot_receive_pack_identity(self):
        result = self.decide([facts()], [selection(name="new.pack")], "current")
        self.assertEqual(result.status, WriteStatus.REJECTED)

    def test_missing_and_stale_tokens_never_apply(self):
        for token in (None, "old"):
            result = self.decide([facts()], [selection()], token)
            self.assertEqual(result.status, WriteStatus.POLICY_REQUIRED)
            self.assertEqual(result.stale, token is not None)
            self.assertFalse(result.actions)

    def test_disappeared_matches_do_not_bypass_stale_check(self):
        result = self.decide([facts(matches=False)], [selection()], "old")
        self.assertTrue(result.stale)
        self.assertFalse(result.actions)
        # Also protect a repeated preview request without decisions.
        self.assertTrue(self.decide([facts(matches=False)], token="old").stale)

    def test_partial_batch_never_returns_executable_actions(self):
        result = self.decide([facts(), facts(item("b")), facts(item("c"), False)],
                             [selection()], "current")
        self.assertEqual(result.status, WriteStatus.POLICY_REQUIRED)
        self.assertFalse(result.actions)
        self.assertEqual(len(result.choices), 3)

    def test_default_target_can_be_copied_but_not_replaced(self):
        f = replace(facts(), matches=(WriteTarget("existing", "world", is_default=True),))
        preview = self.decide([f])
        self.assertTrue(preview.choices[0].options[0].allowed)
        self.assertFalse(preview.choices[0].options[1].allowed)
        result = self.decide([f], [selection(policy=WritePolicy.REPLACE, target="existing")], "current")
        self.assertEqual(result.status, WriteStatus.REJECTED)
        self.assertEqual(self.decide([f], [selection()], "current").status, WriteStatus.READY)

    def test_foreign_and_read_only_replace_targets_rejected(self):
        for target in (WriteTarget("existing", "other"), WriteTarget("existing", "world", writable=False)):
            f = replace(facts(), matches=(target,))
            result = self.decide([f], [selection(policy=WritePolicy.REPLACE, target="existing")], "current")
            self.assertEqual(result.status, WriteStatus.REJECTED)

    def test_destination_access_and_domain_errors_block_all_writes(self):
        for target, errors in ((WriteTarget("destination", "other"), ()),
                               (WriteTarget("destination", "world", is_default=True), ()),
                               (WriteTarget("destination", "world", writable=False), ()),
                               (WriteTarget("wrong-pack", "world"), ()),
                               (WriteTarget("destination", "world"), ("invalid_body",))):
            f = replace(facts(), destination=target, issues=errors)
            result = self.decide([f], [selection()], "current")
            self.assertEqual(result.status, WriteStatus.REJECTED)
            self.assertFalse(result.actions)

    def test_catalog_member_cross_scope_blocked_but_import_can_enter_world(self):
        f = replace(facts(matches=False), source_owner_world_uid=None)
        self.assertEqual(self.decide([f]).status, WriteStatus.REJECTED)
        imported = f.item.model_copy(update={"source": WriteSource(kind=WriteSourceKind.IMPORT, key="entry")})
        self.assertEqual(self.decide([replace(f, item=imported)]).status, WriteStatus.READY)

    def test_two_replacements_cannot_write_same_target(self):
        result = self.decide([facts(), facts(item("b"))],
                             [selection(policy=WritePolicy.REPLACE, target="existing"),
                              selection("b", WritePolicy.REPLACE, "existing")], "current")
        self.assertEqual(result.status, WriteStatus.REJECTED)
        self.assertFalse(result.actions)

    def test_pack_replace_keeps_explicit_target_for_both_scopes(self):
        for owner in (None, "world"):
            f = facts(item(kind=WriteObjectKind.PACK, owner=owner))
            result = self.decide([f], [selection(policy=WritePolicy.REPLACE, target="existing")], "current")
            self.assertEqual(result.status, WriteStatus.READY)
            self.assertEqual(result.actions[0].action, WriteAction.REPLACE)
            self.assertEqual(result.actions[0].target_uid, "existing")

    def test_two_pack_copies_cannot_claim_one_new_identity(self):
        entries = [replace(facts(item(key, WriteObjectKind.PACK)),
                           copy_system_name="new.pack", copy_identity_available=True)
                   for key in ("a", "b")]
        result = self.decide(entries, [selection(key, name="new.pack") for key in ("a", "b")], "current")
        self.assertEqual(result.status, WriteStatus.REJECTED)
        self.assertFalse(result.actions)

    def test_invalid_item_aborts_other_ready_actions(self):
        result = self.decide([facts(matches=False), replace(facts(item("b")), issues=("invalid_body",))])
        self.assertEqual(result.status, WriteStatus.REJECTED)
        self.assertFalse(result.actions)

    def test_request_and_snapshot_must_correspond(self):
        request = LibraryWriteRequest(items=(item("different"),))
        result = LibraryWritePolicy().decide(WriteSnapshot((facts(),), "token"), request)
        self.assertEqual(result.status, WriteStatus.REJECTED)

    def test_wire_round_trip_and_invalid_requests(self):
        request = LibraryWriteRequest(items=(item(),), decisions=(selection(),), preview_token="current")
        self.assertEqual(LibraryWriteRequest.model_validate_json(request.model_dump_json()), request)
        invalid = [dict(items=(item(), item())),
                   dict(items=(item(),), decisions=(selection(), selection())),
                   dict(items=(item(),), decisions=(selection("unknown"),))]
        for raw in invalid:
            with self.assertRaises(ValidationError):
                LibraryWriteRequest(**raw)
        for raw in (dict(item_key="a", policy="unknown"),
                    dict(item_key="a", policy="replace"),
                    dict(item_key="a", policy="copy", target_uid="existing"),
                    dict(item_key="a", policy="copy", copy_system_name="bad|name")):
            with self.assertRaises(ValidationError):
                LibraryWriteSelection(**raw)

    def test_request_validates_member_and_pack_destinations(self):
        for raw in (dict(item_key="a", object_kind="member", source=item().source),
                    dict(item_key="a", object_kind="pack", source=item().source, target_pack_uid="pack")):
            with self.assertRaises(ValidationError):
                LibraryWriteItem(**raw)
