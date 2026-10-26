"""Pure target graph facts — supplied catalog is already membership-scoped.

TZ domain libraries §5–7; no lookup outside membership, implicit attach,
fallback, runtime logging or persistence. Caller decides how to report issues.
"""

from collections.abc import Mapping

from app.application.jsonValidation.types import (
    FieldPathError, ReferenceIssueContext, ReferenceIssueReason,
)
from app.application.templateLibrary.packs.domainAdapters.bodyPreparation import TemplatePreparationError
from app.application.templateLibrary.packs.domainAdapters.building import BuildingBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.plot import PlotBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.relief import ReliefBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.structure import StructureBodyPreparation
from app.application.templateLibrary.packs.lifecycleContracts import (
    CatalogSnapshot,
    PreparedTemplateGraph,
)
from app.application.templateLibrary.packs.referenceResolver import (
    contextualize_reference_issues, reference_index,
)
from app.db.models.libraryPackMember import LibraryPackMemberRow


_PREPARATIONS = {p.library_kind.value: p() for p in (
    PlotBodyPreparation, BuildingBodyPreparation, ReliefBodyPreparation,
    StructureBodyPreparation,
)}


def prepare_template_graph(
    catalog: CatalogSnapshot, *, world=None,
    known_members: Mapping[str, LibraryPackMemberRow] | None = None,
) -> PreparedTemplateGraph:
    """Single pass: validate bodies once, collect declared refs and issues.

    ``bodies`` holds only members that passed preparation — callers needing
    the typed bodies (the B3 snapshot loader) reuse them instead of running
    a second ``prepare_body`` round through the domain adapters.
    """
    issues, refs = [], []
    bodies: dict = {}
    world_uid = world.world_uid if world is not None else None
    for uid, member in sorted(catalog.members.items()):
        if member.template_uid != uid:
            issues.append(FieldPathError((uid,), 'catalog key does not match member identity',
                                         code='TEMPLATE_IDENTITY'))
            continue
        preparation = _PREPARATIONS.get(member.library_kind)
        if preparation is None:
            continue  # Other domains retain their own validators.
        if uid not in catalog.bodies:
            issues.append(_missing_body(member, uid, 'body', world_uid))
            continue
        try:
            body = preparation.prepare_body(catalog.bodies[uid], local_uid=member.local_uid,
                                            template_uid=uid, world=world)
        except TemplatePreparationError as exc:
            issues.extend(exc.issues)
            continue
        bodies[uid] = body
        refs.extend(preparation.body_refs(body, uid))
    _, ref_issues = reference_index(refs, catalog.members)
    issues.extend(contextualize_reference_issues(ref_issues, known_members or {}, world_uid))
    # Missing targets were diagnosed at their member row; retain the consumer
    # path as well so callers can identify which operation depends on the body.
    for ref in refs:
        member = catalog.members.get(ref.template_uid)
        if (member is not None and member.library_kind == ref.library_kind
                and member.template_uid not in catalog.bodies):
            issues.append(_missing_body(member, ref.consumer, ref.path, world_uid))
    return PreparedTemplateGraph(bodies=bodies, refs=tuple(refs),
                                 issues=tuple(dict.fromkeys(issues)))


def template_graph_issues(
    catalog: CatalogSnapshot, *, world=None,
    known_members: Mapping[str, LibraryPackMemberRow] | None = None,
) -> tuple[FieldPathError, ...]:
    """Validate all target bodies and declared refs, preserving every issue path."""
    return prepare_template_graph(
        catalog, world=world, known_members=known_members,
    ).issues


def _missing_body(member, consumer, path, world_uid):
    return FieldPathError((consumer, path), 'member body is missing', code='LIBRARY_REFERENCE',
        reference=ReferenceIssueContext(ReferenceIssueReason.BODY_MISSING,
            member.library_kind, world_uid=world_uid, requested_template_uid=member.template_uid,
            owner_pack_uid=member.pack_uid, consumer=consumer))
