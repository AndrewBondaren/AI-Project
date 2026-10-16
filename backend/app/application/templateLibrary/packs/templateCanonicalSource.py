"""Declared typed canonical graph; no SQL and no discovery of user packs."""
import json
from dataclasses import dataclass
from pathlib import Path

from app.application.canonicalLibrary import CanonicalEntry, CanonicalSourceError
from app.application.templateLibrary.packs.defaults import (
    BUILDINGS_BASE_SYSTEM_NAME, PLOTS_BASE_SYSTEM_NAME, STRUCTURES_BASE_SYSTEM_NAME,
)
from app.application.templateLibrary.packs.domainAdapters.building import BuildingBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.plot import PlotBodyPreparation
from app.application.templateLibrary.packs.domainAdapters.structure import StructureBodyPreparation
from app.application.templateLibrary.packs.lifecycleContracts import CatalogSnapshot
from app.application.templateLibrary.packs.manifest import load_pack_manifest, source_file_label
from app.application.templateLibrary.packs.packCatalog import member_rows_for
from app.application.templateLibrary.packs.templateGraphValidation import template_graph_issues
from app.application.templateLibrary.structureTemplateLibraryService import resolve_structures_domain_root
from app.dataModel.libraryPacks.packManifest import LibraryPackManifest, LibraryPackManifestMember
from app.dataModel.locations.structure.building.worldBuildingLayoutDefaults import (
    CANONICAL_PLOT_NAMES, canonical_defaults,
)
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.models.plotTemplate import PlotTemplateRow
from app.db.models.structureTemplate import StructureTemplateRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, library_uid

SOURCE_ROOT = Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class CanonicalTemplateRecord:
    member: LibraryPackMemberRow
    row: PlotTemplateRow | BuildingTemplateRow | StructureTemplateRow


@dataclass(frozen=True)
class CanonicalTemplatePack:
    kind: LibraryKind
    manifest: LibraryPackManifest
    entries: tuple[CanonicalEntry, ...]


def _generated_pack(kind, system_name, bodies, dependencies):
    pack_uid = library_uid(LibraryKind.LIBRARY_PACKS, system_name)
    entries, declarations = [], []
    for body in bodies:
        name = str(body.system_name)
        uid = library_uid(kind, name, pack_uid=pack_uid)
        prepared = (PlotBodyPreparation() if kind == LibraryKind.PLOT_TEMPLATES
                    else BuildingBodyPreparation()).prepare_body(
                        body.model_dump(mode="json"), local_uid=name, template_uid=uid)
        source = f"fixtures/templates/{name}.json"
        if kind == LibraryKind.BUILDING_TEMPLATES:
            source += "#main_building"
        member = LibraryPackMemberRow(uid, pack_uid, kind.value, name)
        row_cls = PlotTemplateRow if kind == LibraryKind.PLOT_TEMPLATES else BuildingTemplateRow
        row = row_cls(template_uid=uid, system_name=name, display_name=body.display_name,
            data=prepared.model_dump(mode="json"), source_file=source)
        entries.append(CanonicalEntry(uid, CanonicalTemplateRecord(member, row)))
        declarations.append(LibraryPackManifestMember(library_kind=kind.value, local_uid=name,
            template_uid=uid, source_file=f"base/{name}.json"))
    manifest = LibraryPackManifest(pack_uid=pack_uid, system_name=system_name,
        pack_name="base", display_name=system_name, dependencies=list(dependencies), members=declarations)
    return CanonicalTemplatePack(kind, manifest, tuple(entries))


def load_canonical_template_graph(root: Path | None = None) -> tuple[CanonicalTemplatePack, ...]:
    """Every source is checked before the caller opens its attach transaction."""
    # Explicit roots isolate authored-source tests; production uses the same
    # env/repo-relative domain root as explicit FS imports.
    structure_root = root / "structures_templates" if root is not None else resolve_structures_domain_root()
    root = root if root is not None else SOURCE_ROOT
    loaded = load_pack_manifest(structure_root / "base", domain_root=structure_root,
                                library_kind=LibraryKind.STRUCTURE_TEMPLATES)
    if loaded.manifest.system_name != STRUCTURES_BASE_SYSTEM_NAME:
        raise CanonicalSourceError("structure default manifest does not match trusted declaration")
    entries = []
    members = {m.template_uid: m for m in member_rows_for(loaded.manifest)}
    for source in loaded.members:
        member = members[source.member.template_uid]
        body = StructureBodyPreparation().prepare_body(json.loads(source.file.read_text(encoding="utf-8")),
            local_uid=member.local_uid, template_uid=member.template_uid)
        row = StructureTemplateRow(template_uid=member.template_uid, display_name=body.display_name,
            version=body.version, data=body.model_dump(mode="json"),
            source_file=source_file_label(source.file, domain_root=structure_root, root_label="structures_templates"))
        entries.append(CanonicalEntry(member.template_uid, CanonicalTemplateRecord(member, row)))
    structures = CanonicalTemplatePack(LibraryKind.STRUCTURE_TEMPLATES, loaded.manifest, tuple(entries))
    plots = canonical_defaults(source_root=root / "fixtures" / "templates")
    # Explicit shipped building identities share their declared plot's main body.
    # This does not extract arbitrary inline buildings from user templates.
    from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
    buildings = []
    for name, plot in zip(CANONICAL_PLOT_NAMES, plots, strict=True):
        if str(plot.system_name) != name or plot.main_building is None:
            raise CanonicalSourceError(f"canonical plot {name} must declare its named main building")
        buildings.append(BuildingTemplate(system_name=name, display_name=plot.display_name,
                                         **plot.main_building.model_dump(mode="json")))
    building_pack = _generated_pack(LibraryKind.BUILDING_TEMPLATES, BUILDINGS_BASE_SYSTEM_NAME,
                                    buildings, (structures.manifest.pack_uid,))
    plot_pack = _generated_pack(LibraryKind.PLOT_TEMPLATES, PLOTS_BASE_SYSTEM_NAME, plots,
                               (structures.manifest.pack_uid,))
    graph = (structures, building_pack, plot_pack)
    declared_packs = {pack.manifest.pack_uid for pack in graph}
    for pack in graph:
        if set(pack.manifest.dependencies) - declared_packs:
            raise CanonicalSourceError(f"canonical pack {pack.manifest.system_name} has undeclared dependencies")
    records = [entry.body for pack in graph for entry in pack.entries]
    if len({record.member.template_uid for record in records}) != len(records):
        raise CanonicalSourceError("duplicate canonical template identity in declared graph")
    catalog = CatalogSnapshot({r.member.template_uid: r.member for r in records},
                              {r.member.template_uid: r.row.data for r in records}, {})
    issues = template_graph_issues(catalog)
    if issues:
        raise CanonicalSourceError("; ".join(f"{i.path}: {i.message}" for i in issues))
    return graph
