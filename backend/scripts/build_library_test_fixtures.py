"""Build two real standalone library archives. Run from backend:

    python -m scripts.build_library_test_fixtures

Sources stay authoritative; a fixed fixture timestamp makes bytes reproducible.
No database or runtime default declarations are modified.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.application.jsonValidation.resolve import resolve_model
from app.application.worldBundle.archive import read_archive, write_archive
from app.application.templateLibrary.packs.defaults import is_default_pack_uid
from app.application.templateLibrary.packs.manifest import load_pack_manifest
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldBundle.bundleManifest import BundleKind, BundleManifest, BundleLibraryPackSource
from app.dataModel.worldBundle.libraryArchive import LIBRARY_DOMAIN_ROOTS, LibraryArchiveManifest, LibraryArchivePack
from app.ids import LibraryKind


REPO = Path(__file__).resolve().parents[2]
OUTPUT = REPO / "fixtures" / "packs"
FIXTURE_TIMESTAMP = datetime(2026, 10, 12, tzinfo=timezone.utc)
SOURCES = (
    ("user_library", LibraryKind.RELIEF_TEMPLATES, "smoke_003", False),
    ("engine_library", LibraryKind.STRUCTURE_TEMPLATES, "base", True),
)


def load_fixture_source(kind: LibraryKind, folder: str) -> LibraryArchivePack:
    root = REPO / LIBRARY_DOMAIN_ROOTS[kind]
    loaded = load_pack_manifest(root / folder, domain_root=root, library_kind=kind)
    bodies = {}
    model = StructureTemplate if kind == LibraryKind.STRUCTURE_TEMPLATES else ReliefTemplate
    for entry in loaded.members:
        raw = json.loads(entry.file.read_text(encoding="utf-8"))
        resolve_model(model, raw, label=str(entry.file))
        bodies[entry.member.template_uid] = raw
    # Preserve the original wire metadata, including future fields not yet
    # modeled by the stricter FS-author DTO.
    manifest = LibraryArchiveManifest.model_validate(
        json.loads((root / folder / "pack.manifest.json").read_text(encoding="utf-8")),
    )
    return LibraryArchivePack(manifest, bodies)


def fixture_manifest(pack: LibraryArchivePack) -> BundleManifest:
    return BundleManifest(
        kind=BundleKind.LIBRARY_PACK, format_version=1, sections={},
        source=BundleLibraryPackSource(
            kind=BundleKind.LIBRARY_PACK, pack_uid=pack.manifest.pack_uid,
            exporter="AI Project library test fixtures", exported_at=FIXTURE_TIMESTAMP,
        ),
    )


def build(output: Path = OUTPUT) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, kind, folder, expected_default in SOURCES:
        pack = load_fixture_source(kind, folder)
        if is_default_pack_uid(pack.manifest.pack_uid) != expected_default:
            raise ValueError(f"Unexpected default status: {pack.manifest.system_name}")
        path = output / f"{name}.wpack"
        write_archive({}, fixture_manifest(pack), path=path, library_packs=[pack])
        contents = read_archive(path)
        if contents.library_packs != (pack,):
            raise ValueError(f"Fixture round-trip mismatch: {path}")
        paths.append(path)
    return paths


if __name__ == "__main__":
    for path in build():
        pack = read_archive(path).library_packs[0]
        print(f"{path.name}: {pack.manifest.system_name}; {len(pack.bodies)} members; "
              f"default={is_default_pack_uid(pack.manifest.pack_uid)}; {path.stat().st_size} bytes")
