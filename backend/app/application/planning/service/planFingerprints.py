"""The three planning fingerprint formulas; bindings supply only their manifest."""

from app.application.encoding.canonicalCodec import digest
from app.dataModel.cache.identity.cacheKey import CacheItemKey
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency, require_canonical_dependencies
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.planKey import InputFingerprint, OutputFingerprint, PlanKey, PlanScope


def input_fingerprint(metadata: PlanContractMetadata, world_uid: EntityUid, scope: PlanScope,
                      inputs: object, dependencies: tuple[PlanDependency, ...],
                      manifest: CanonicalSchemaManifest) -> InputFingerprint:
    require_canonical_dependencies(dependencies)
    return InputFingerprint(digest((metadata.id, metadata.schema_version, metadata.algorithm_version,
        world_uid, scope, inputs, dependencies), manifest))


def output_fingerprint(payload: object, dependencies: tuple[PlanDependency, ...],
                       diagnostics: tuple[PlanDiagnostic, ...], manifest: CanonicalSchemaManifest) -> OutputFingerprint:
    require_canonical_dependencies(dependencies)
    return OutputFingerprint(digest((payload, dependencies, diagnostics), manifest))


def cache_item_key(key: PlanKey, manifest: CanonicalSchemaManifest) -> CacheItemKey:
    return CacheItemKey(digest(key, manifest))
