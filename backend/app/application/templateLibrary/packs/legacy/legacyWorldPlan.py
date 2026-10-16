"""B1 pure pointer-set migration planner. No hydrate, writer or runtime cutover."""
from copy import deepcopy
from dataclasses import replace

from app.application.jsonValidation.types import FieldPathError, ImportValidationError, ReferenceIssueContext, ReferenceIssueReason
from app.application.templateLibrary.packs.domainAdapters.building import BuildingBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.plot import PlotBodyPreparation
from app.application.templateLibrary.packs.write.bodyDiff import body_diff
from app.application.templateLibrary.packs.defaults import is_default_pack_uid
from app.application.templateLibrary.packs.domainAdapters.refFields import DirectRefField, RELIEF_POLICY_REF_FIELDS, template_body_refs
from app.application.templateLibrary.packs.legacy.legacyDomainRefs import is_canonical_uid
from app.application.templateLibrary.packs.legacy.legacyDomainContracts import LegacyDomainShape
from app.application.templateLibrary.packs.legacy.legacyPack import legacy_member_row, legacy_pack_row, legacy_source_member_row
from app.application.templateLibrary.packs.legacy.legacyWorldBodies import LegacyWorldBodyTools, target_kind
from app.application.templateLibrary.packs.legacy.legacyWorldContracts import (
    LegacyBodyComparison, LegacyPackProjection, LegacyPackRoute, LegacyPointerDecision,
    LegacyWorldMigrationPlan, LegacyWorldFacts,
)
from app.application.templateLibrary.packs.legacy.legacyWorldProjection import existing_instance, project_pack
from app.application.templateLibrary.packs.legacy.legacyWorldRefs import project_world_refs
from app.application.templateLibrary.packs.lifecycleContracts import (
    CatalogSnapshot,
    RELIEF_POLICY_FIELD,
    world_consumer,
)
from app.application.templateLibrary.packs.referenceResolver import contextualize_reference_issues, dependency_issues, reference_index
from app.application.templateLibrary.packs.uidMap import compose_template_uid_maps
from app.application.templateLibrary.packs.write.writeInspectionContracts import WriteImportMember
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.ids import LibraryKind, UID_PART_SEPARATOR


def _fail(path, message, code="LEGACY_IDENTITY"):
    raise ImportValidationError([FieldPathError(path, message, code=code)])


def _accepts(pointer, member):
    return member.library_kind == pointer.source_kind.value or (
        pointer.source_kind == LibraryKind.BUILDING_TEMPLATES and member.library_kind == LibraryKind.PLOT_TEMPLATES)


def plan_legacy_world_migration(legacy, facts: LegacyWorldFacts) -> LegacyWorldMigrationPlan:
    original, facts = deepcopy(legacy), deepcopy(facts)
    diagnostics, decisions, comparisons = [], [], []
    try:
        if original.issues:
            raise ImportValidationError(list(original.issues))
        return _plan(original, facts, diagnostics, decisions, comparisons)
    except ImportValidationError as exc:
        return LegacyWorldMigrationPlan(original, facts, deepcopy(original.raw_world), (), (),
            tuple(decisions), tuple(comparisons), (), CatalogSnapshot({}, {}, {}),
            tuple(diagnostics), tuple(exc.errors))
    except ValueError as exc:
        return LegacyWorldMigrationPlan(original, facts, deepcopy(original.raw_world), (), (),
            tuple(decisions), tuple(comparisons), (), CatalogSnapshot({}, {}, {}), tuple(diagnostics),
            (FieldPathError(("uid_map",), str(exc), code="LEGACY_UID_MAP"),))


def _plan(original, facts, diagnostics, decisions, comparisons):
    world_uid = original.raw_world["world_uid"]
    if any(not is_canonical_uid(a) or not is_canonical_uid(b) for a, b in facts.uid_aliases):
        _fail(("uid_map",), "UID aliases must contain canonical UUID identities", "LEGACY_UID_MAP")
    aliases = compose_template_uid_maps(*({a: b} for a, b in facts.uid_aliases))
    tools = LegacyWorldBodyTools(facts, aliases)
    packs, entries = {}, {}
    for source in facts.packs:
        uid = source.pack.pack_uid
        if not is_canonical_uid(uid):
            _fail(("library_packs", uid), "pack identity must be a canonical UUID", "TEMPLATE_UID")
        if uid in packs:
            _fail(("library_packs", uid), "duplicate pack snapshot")
        packs[uid] = source
        if is_default_pack_uid(uid) and source.pack.owner_world_uid is not None:
            _fail(("library_packs", uid), "declared default pack must be engine-owned")
        for entry in source.members:
            m = entry.member
            if (not is_canonical_uid(m.template_uid) or
                m.source_template_uid is not None and not is_canonical_uid(m.source_template_uid)):
                _fail(("library_packs", uid, m.template_uid), "member identity must be a canonical UUID", "TEMPLATE_UID")
            if (m.library_kind not in {k.value for k in (LibraryKind.PLOT_TEMPLATES, LibraryKind.BUILDING_TEMPLATES,
                                                       LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.RELIEF_TEMPLATES)} or
                not isinstance(m.local_uid, str) or not m.local_uid or m.local_uid != m.local_uid.strip() or UID_PART_SEPARATOR in m.local_uid):
                _fail(("library_packs", uid, m.template_uid), "invalid declared domain/local key")
            if (m.creation_kind not in ("authored", "pack_copy", "member_copy") or
                (m.creation_kind == "authored") != (m.source_template_uid is None)):
                _fail(("library_packs", uid, m.template_uid), "invalid declared provenance", "LEGACY_PROVENANCE")
            if m.pack_uid != uid or m.template_uid in entries:
                _fail(("library_packs", uid, m.template_uid), "invalid or duplicate membership")
            entries[m.template_uid] = entry
    resolved, selected = {}, set()
    for pointer in original.pointers:
        uid = aliases.get(pointer.template_uid, pointer.template_uid)
        entry = entries.get(uid)
        member = tools.members.get(uid)
        if entry is not None and _accepts(pointer, member) and packs[entry.member.pack_uid].pack.owner_world_uid in (None, world_uid):
            resolved[pointer.path] = uid
            selected.add(entry.member.pack_uid)
    associated, authors = [], []
    for body in original.bodies:
        kind = target_kind(body.source_kind, body.shape)
        uid = aliases.get(body.source_uid, body.source_uid)
        entry = entries.get(uid)
        if entry is not None and packs[entry.member.pack_uid].pack.owner_world_uid not in (None, world_uid):
            entry = None  # Explicit raw content may be copied; a foreign pack is never expanded.
        if entry is None and body.source_uid is None:
            candidates = {value for value in resolved.values() if tools.members[value].library_kind == kind.value
                          and tools.members[value].local_uid == body.local_uid}
            if len(candidates) > 1:
                _fail(body.path, f"ambiguous legacy body name; candidates={sorted(candidates)}", "LEGACY_REF_AMBIGUOUS")
            if candidates:
                uid = next(iter(candidates))
                entry = entries[uid]
            elif body.local_uid is not None:
                known = legacy_member_row(kind, body.local_uid, world_uid=world_uid).template_uid
                candidate = entries.get(known)
                if candidate is not None and candidate.member.pack_uid == legacy_pack_row(world_uid).pack_uid:
                    uid, entry = known, candidate
        if entry is not None:
            if tools.members[uid].library_kind != kind.value:
                _fail(body.path, "body source identity belongs to a different domain", "LEGACY_DOMAIN_KIND")
            selected.add(entry.member.pack_uid)
            associated.append((body, uid))
        else:
            if not body.local_uid:
                _fail(body.path, "authored structure body requires declared local_uid", "STRICT_REQUIRED")
            row = (legacy_source_member_row(kind, body.local_uid, world_uid=world_uid, source_template_uid=uid)
                   if uid else legacy_member_row(kind, body.local_uid, world_uid=world_uid))
            authors.append((body, row, uid))
    # Raw authored bodies can refer to each other before destination remap.
    tools.members.update((uid or row.template_uid, replace(row, template_uid=uid or row.template_uid))
                         for _, row, uid in authors)
    relevant = selected | {uid for uid, p in packs.items() if p.pack.owner_world_uid == world_uid or is_default_pack_uid(uid)}
    normalized = {uid: replace(packs[uid], members=tuple(tools.normalize(e) for e in packs[uid].members)) for uid in sorted(relevant)}
    routes, targets, rows, instances = {}, {}, {}, {}
    split_uids = {uid for uid, entry in entries.items() if tools.members[uid].library_kind != entry.member.library_kind}
    for uid in sorted(selected):
        source = normalized[uid]
        if source.pack.owner_world_uid == world_uid or is_default_pack_uid(uid):
            if any(e.member.template_uid in split_uids for e in source.members):
                routes[uid] = LegacyPackRoute.LEGACY
            continue
        instance = existing_instance(facts, source, world_uid)
        route = LegacyPackRoute.REUSE if instance else LegacyPackRoute.INSTANCE
        routes[uid], instances[uid] = route, instance
        targets[uid], rows[uid] = project_pack(source, route, world_uid, instance=instance)
    provisional = compose_template_uid_maps(aliases,
        {old: row.template_uid for managed in rows.values() for old, row in managed.items()})
    overrides = {}
    initial_routes = dict(routes)
    for body, uid in associated:
        src = next(e for e in normalized[entries[uid].member.pack_uid].members if e.member.template_uid == uid)
        override = tools.prepare(src.member, body.body, source_kind=body.source_kind, shape=body.shape,
            path=body.path, source_uid=body.source_uid or uid, source_file=body.source_file)
        previous = overrides.get(uid)
        if previous is not None and previous.body != override.body:
            _fail(body.path, "conflicting bodies for one source UID", "LEGACY_BODY_CONFLICT")
        overrides[uid] = override
    tools.members.update((row.template_uid, row) for managed in rows.values() for row in managed.values())
    for body, uid in associated:
        src = next(e for e in normalized[entries[uid].member.pack_uid].members if e.member.template_uid == uid)
        override = overrides[uid]
        pack_uid = entries[uid].member.pack_uid
        row = rows.get(pack_uid, {}).get(uid, src.member)
        baseline = src
        if initial_routes.get(pack_uid) == LegacyPackRoute.REUSE and uid in rows[pack_uid]:
            baseline = tools.normalize(entries[row.template_uid])
        left = tools.remap(baseline, row, provisional, path=body.path).body
        right = tools.remap(override, row, provisional, path=body.path).body
        changes = body_diff(left, right)
        comparisons.append(LegacyBodyComparison(body.path, uid, changes))
        if changes:
            routes[pack_uid] = LegacyPackRoute.LEGACY
    for uid, route in sorted(routes.items()):
        targets[uid], rows[uid] = project_pack(normalized[uid], route, world_uid,
            instance=instances.get(uid), split_uids=split_uids)
        existing = packs.get(targets[uid].pack_uid)
        if existing is not None and route == LegacyPackRoute.INSTANCE:
            _fail(("library_packs", targets[uid].pack_uid), "instance destination identity is occupied")
    mapping = compose_template_uid_maps(aliases,
        {old: row.template_uid for managed in rows.values() for old, row in managed.items()},
        {old_row.template_uid: rows[uid][old].template_uid
         for uid, instance in instances.items() if instance and routes[uid] == LegacyPackRoute.LEGACY
         for old, old_row in project_pack(normalized[uid], LegacyPackRoute.REUSE, world_uid, instance=instance)[1].items()},
        {uid: row.template_uid for _, row, uid in authors if uid is not None})
    tools.members.update((row.template_uid, row) for managed in rows.values() for row in managed.values())
    tools.members.update((row.template_uid, row) for _, row, _ in authors)
    actions, final_members, final_bodies, files = {}, {}, {}, {}
    for uid, source in sorted(normalized.items()):
        if source.pack.owner_world_uid != world_uid and not is_default_pack_uid(uid):
            continue
        if routes.get(uid) == LegacyPackRoute.LEGACY:
            # A compatibility kind split has no valid modern source catalog row.
            # Otherwise cloning an override does not delete an owned library.
            if any(e.member.template_uid in split_uids for e in source.members):
                continue
        for entry in source.members:
            final_members[entry.member.template_uid], final_bodies[entry.member.template_uid] = entry.member, entry.body
            files[entry.member.template_uid] = entry.source_file
        if source.pack.owner_world_uid == world_uid:
            actions[uid] = LegacyPackProjection(uid, source.pack, LegacyPackRoute.REUSE,
                source.members, source.dependencies, source, (uid,))
    pool, origins, pool_dependencies = {}, [], set()
    pack_map = {uid: target.pack_uid for uid, target in targets.items()}
    for uid, route in sorted(routes.items()):
        source, target = normalized[uid], targets[uid]
        if route == LegacyPackRoute.REUSE:
            instance = normalized[target.pack_uid]
            actions[target.pack_uid] = LegacyPackProjection(uid, instance.pack, route, instance.members,
                instance.dependencies, packs[uid], (uid,))
            continue
        effective = {e.member.template_uid: e for e in source.members}
        if initial_routes.get(uid) == LegacyPackRoute.REUSE:
            for old, owned_row in project_pack(source, LegacyPackRoute.REUSE, world_uid, instance=instances[uid])[1].items():
                effective[old] = tools.normalize(entries[owned_row.template_uid])
        projected = tuple(tools.remap(overrides.get(e.member.template_uid, effective[e.member.template_uid]), rows[uid][e.member.template_uid],
            mapping, path=("library_packs", uid, e.member.template_uid)) for e in source.members)
        deps = {pack_map.get(dep, dep) for dep in source.dependencies} - {target.pack_uid}
        if route == LegacyPackRoute.LEGACY:
            pool.update((e.member.template_uid, e) for e in projected)
            origins.append(uid)
            pool_dependencies.update(deps)
        else:
            actions[target.pack_uid] = LegacyPackProjection(uid, target, route, projected, tuple(sorted(deps)), source, (uid,))
        pointed = {value for value in resolved.values() if entries[value].member.pack_uid == uid}
        extra = sorted(e.member.template_uid for e in source.members if e.member.template_uid not in pointed)
        if extra:
            diagnostics.append(FieldPathError(("library_packs", uid),
                f"full {route.value} expands pointer set; extra members={extra}", code="LIBRARY_EXPANSION"))
    for body, row, uid in authors:
        if row.template_uid in pool:
            _fail(body.path, "duplicate authored destination identity", "LEGACY_BODY_CONFLICT")
        pool[row.template_uid] = tools.prepare(row, body.body, source_kind=body.source_kind, shape=body.shape,
            path=body.path, source_uid=body.source_uid, source_file=body.source_file, mapping=mapping)
    if pool:
        target = legacy_pack_row(world_uid)
        current = packs.get(target.pack_uid)
        if current is not None:
            if current.pack.owner_world_uid != world_uid or current.pack.source_pack_uid is not None:
                _fail(("library_packs", target.pack_uid), "legacy destination ownership/provenance conflict")
            target = current.pack
            untouched = normalized[target.pack_uid]
            for entry in untouched.members:
                if entry.member.template_uid not in mapping or mapping[entry.member.template_uid] == entry.member.template_uid:
                    pool.setdefault(entry.member.template_uid, entry)
            pool_dependencies.update(current.dependencies)
        actions[target.pack_uid] = LegacyPackProjection(None, target, LegacyPackRoute.LEGACY,
            tuple(pool[k] for k in sorted(pool)), tuple(sorted(pool_dependencies - {target.pack_uid})), None, tuple(origins))
    for action in actions.values():
        for entry in action.members:
            known = entries.get(entry.member.template_uid)
            if known is not None and known.member != entry.member:
                _fail(("library_packs", action.target_pack.pack_uid, entry.member.template_uid), "destination member identity is occupied")
            final_members[entry.member.template_uid], final_bodies[entry.member.template_uid] = entry.member, entry.body
            files[entry.member.template_uid] = entry.source_file
    pins = []
    for pointer in original.pointers:
        source_uid = aliases.get(pointer.template_uid, pointer.template_uid)
        uid = mapping.get(source_uid, source_uid)
        member = final_members.get(uid)
        if member is not None and _accepts(pointer, member):
            source = entries.get(source_uid)
            route = routes.get(source.member.pack_uid) if source else LegacyPackRoute.LEGACY
            label = route.value if route else "default" if is_default_pack_uid(member.pack_uid) else "owned"
            pins.append(LibraryPinEntry(library_kind=member.library_kind, template_uid=uid))
            decisions.append(LegacyPointerDecision(pointer.path, pointer.template_uid, uid, member.library_kind, label))
        else:
            known = entries.get(source_uid)
            owner = packs[known.member.pack_uid].pack.owner_world_uid if known else None
            reason = (ReferenceIssueReason.UNKNOWN_TEMPLATE if known is None else
                ReferenceIssueReason.KIND_MISMATCH if not _accepts(pointer, tools.members[source_uid]) else
                ReferenceIssueReason.OWNER_UNAVAILABLE if owner not in (None, world_uid) else
                ReferenceIssueReason.BODY_MISSING)
            diagnostics.append(FieldPathError(pointer.path + ("system_template_uid",),
                f"unavailable or wrong-kind pointer {pointer.template_uid}; no pin created", code="LIBRARY_REFERENCE",
                reference=ReferenceIssueContext(reason, pointer.source_kind.value, world_uid,
                    pointer.template_uid, known.member.pack_uid if known else None, consumer=world_consumer(world_uid))))
            decisions.append(LegacyPointerDecision(pointer.path, pointer.template_uid, None, None, "unavailable"))
    projected_world, pins, pin_issues = project_world_refs(original.raw_world, mapping, final_members, pins)
    diagnostics.extend(pin_issues)
    refs = []
    for uid, member in final_members.items():
        if LibraryKind(member.library_kind) != LibraryKind.RELIEF_TEMPLATES:
            model = {LibraryKind.PLOT_TEMPLATES: PlotBodyPreparation.model,
                     LibraryKind.BUILDING_TEMPLATES: BuildingBodyPreparation.model}.get(LibraryKind(member.library_kind))
            if model:
                refs.extend(template_body_refs(LibraryKind(member.library_kind), model.model_validate(final_bodies[uid]), uid))
    for field in RELIEF_POLICY_REF_FIELDS:
        raw = (projected_world.get("relief_pick_policy") or {}).get(field.parent_field)
        if raw is not None:
            refs.extend(DirectRefField(field.uid_field, field.library_kind).references(
                ReliefContextPickPolicy.model_validate(raw), world_consumer(world_uid),
                f"{RELIEF_POLICY_FIELD}.{field.parent_field}."))
    _, ref_issues = reference_index(refs, final_members)
    diagnostics.extend(contextualize_reference_issues(ref_issues, {u: e.member for u, e in entries.items()}, world_uid))
    # Legacy manifests did not declare dependencies. Derive only from known
    # declared refs; this never makes an unavailable pack part of the catalog.
    for uid, action in tuple(actions.items()):
        if action.route != LegacyPackRoute.LEGACY:
            continue
        dependencies = set(action.dependencies)
        consumers = {e.member.template_uid for e in action.members}
        for ref in refs:
            member = final_members.get(ref.template_uid)
            if ref.consumer in consumers and member is not None and member.pack_uid != uid:
                dependencies.add(member.pack_uid)
        actions[uid] = replace(action, dependencies=tuple(sorted(dependencies)))
    available_packs = {m.pack_uid for m in final_members.values()} | set(actions) | {
        uid for uid, source in normalized.items() if source.pack.owner_world_uid == world_uid or is_default_pack_uid(uid)}
    for action in actions.values():
        diagnostics.extend(dependency_issues(action.target_pack.pack_uid,
            set(action.dependencies) - available_packs, world_uid))
    return LegacyWorldMigrationPlan(original, facts, projected_world, pins, tuple(actions[k] for k in sorted(actions)),
        tuple(decisions), tuple(comparisons), tuple(sorted(mapping.items())),
        CatalogSnapshot(final_members, final_bodies, files), tuple(diagnostics), ())
