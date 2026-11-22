# Source: фактические values и методы, 2026-11-22

Статическая инвентаризация для АР-6; не независимая приёмка и не разрешение обхода АР-1…АР-5. Источник — фактические файлы `backend/app/dataModel/sourceVersioning`. Ниже module означает `app.dataModel.sourceVersioning.<module>`. Наследуемые Pydantic construction/validation/serialization методы сохраняют общую границу SourceValue; отдельного бизнес-метода у записи нет, если указан «только construction».

Для всех записей: строгие immutable поля, без IO/application imports/union/closure/commit. Проверять невозможность изменения вложенного значения, отказ extra fields и отсутствие coercion. Результат construction не удостоверяет finalize/retention/availability. Нарушение любого из этих запретов — отказ по ответственности. Manual ValueError/неполная агрегация остаются существующим долгом G1 §3, не объявлены исправленными этой инвентаризацией.

| Module / класс | Поля / ответственность | Собственные методы и проверка |
|---|---|---|
| _value / SourceValue | Общая frozen/strict/extra-forbid/revalidate-always конфигурация | immutable_value → Self: shared validate_immutable; не выполняет semantic admission |
| sourceObjectId / _SourceIdentity | Общая строгость identity | exact_kind: exact enum в Python; nonempty_descriptor: непустой ключ; не lookup registry |
| sourceObjectId / RegistryMemberId | kind/world_uid/descriptor/member_key: identity registry member | Только construction; не подтверждает существование member |
| sourceObjectId / LibraryMemberId | kind/descriptor/template_uid: global library identity | canonical_uuid: canonical UUID; не world-scoped identity |
| sourceObjectId / EntityObjectId | kind/world_uid/descriptor/entity_uid: entity identity | Только construction; не читает entity |
| sourceObjectId / SourceSettingsId | kind/world_uid/descriptor: settings identity | Только construction; не хранит настройки |
| sourceObjectId / SourceCollectionId | kind/world_uid/descriptor: collection identity | Только construction; не перечисляет members |
| sourceObjectRevision / SourceRevision | seq/content_hash: semantic revision | Только construction; positive strict seq/RevisionHex; не allocation/hash calculation |
| sourceVersionRef / SourceVersionRef | object_id/revision: exact object version | Только construction; не body mapping |
| sourceVersionRef / SourceCollectionVersionRef | collection_id/revision: exact membership version | Только construction; не object ref mirror |
| sourceBodyVersion / SourceBodyVersion | source/body: object version-to-artifact mapping | Только construction; не читает body/не вычисляет hash |
| sourceBodyVersion / SourceCollectionVersion | source/body: collection version-to-artifact mapping | Только construction; отдельный вид ref, не generic untyped mapping |
| sourceCollection / SourceCollectionBody | collection/members: membership value | membership_shape: unique identities/same world кроме global library; descriptor ordering — application |
| sourceCapture / SourceCapture | world_uid/objects/collections: exact mappings | mapping_shape: одна revision на identity/same world; не finalization |
| sourceCaptureWitness / SourceCaptureWitness | capture_uid/world_uid/capture_body: finalize candidate | capture_body_shape: source.capture v1 BLOB; не committed evidence по одному constructor |
| sourceCaptureRef / SourceCaptureRef | world_uid/artifact: witness ref | witness_shape: source.capture-witness v1 SQL_ROWS, row_count=1; не проверяет наличие witness |
| sourceDependencies / SourceDependencySet | objects/collections: declared dependencies | Только construction; repetitions не нормализуются |
| sourceCaptureUsage / SourceCaptureUsage | capture/dependencies: declared usage одного capture | dependency_worlds: same world; не producer completeness |
| sourceDurableProof / SourceDurableProof | schema_version/world_uid/uses: persisted proof value | exact_version_type: exact int; persisted_shape: world/unique capture/nonempty usage/unique dependency identities; без repair/authority |
| sourceProofInput / SourceProofInput | world_uid/uses: declared usage request | capture_worlds: same world; сохраняет порядок/повторы |
| sourceProofInput / SourceProofReadInput | world_uid/proof: persisted read request | proof_world: same world; не normalization |
| sourceProofSelection / SourceProofSelection | proof_fingerprint/dependency_indices: selection ordinals | increasing_indices: shared strict ordering; bounds и fingerprint matching — checker |
| sourceProofSelection / SourceProofSelectInput | world_uid/proof/selection: select request | proof_world: same world; subset не вычисляется |
| sourceProofResult / SourceProofResult | proof/durable_refs: result value | refs_shape: unique refs/empty correlation; полнота closure и protection не выводятся из формы |
| sourceProofGroups / SourceProofGroupsInput | groups: nonempty ordered requests | same_world: единый world; union не вычисляется |
| sourceProofGroups / SourceProofGroupsResult | admission/selections: grouped result | Только construction, nonempty selections; не matching |
| sourceProofGroups / SourceProofGroupsVerifyInput | expected/result: verification request | correlation_shape: число selections/world; не exact union/closure verification |
| sourceDescriptor / SourceMemberKey | Непустой exact string token | __get_pydantic_core_schema__: strict string schema; не registry membership certificate |
| sourceDescriptor / SourceDescriptorRegistry | entries: immutable definitions | valid_roster: unique keys/member descriptors; не mutable registration |
| sourceDescriptor / SourceDescriptorDefinition | key/category/scope/key_kind/collection_order/member_descriptors | valid_shape: category-related configuration constraints; не owning projection |
| sourceErrors / SourceFieldIssue | Existing FieldPathError[SourceFieldCode] | Нет собственных методов; owning specialization, не второе поле path |
| sourceErrors / SourceLogicIssue | code/group_index/use_index/source/artifact | Только construction, nullable context/strict nonnegative indices; не field diagnostic mirror |
| sourceErrors / SourceFailure | operation/field_issues/logic_issues | nonempty_failure: непустой failure; не aggregation/transport infrastructure errors |

## Enum и aliases

sourceDescriptor: SourceDescriptorCategory, SourceDescriptorScope, SourceMemberKeyKind, SourceCollectionOrder — закрытые словари значений, без dispatch/IO; SourceDescriptorKey переиспользует RegistryKey[SourceDescriptorRegistry]. sourceObjectId.SourceObjectId — discriminated union существующих четырёх object identities, не новый класс. sourceErrors: SourceOperation, SourceFieldCode, SourceLogicCode — контекст/коды, не переключатели исполнения. Наличие исторического ADOPT_CLOSURE enum не разрешает отозванный adoption маршрут; изменение wire roster требует отдельной нормативной дельты, здесь код не удаляется.

## Фактическая application-поставка

В `application/worldData/sourceVersioning` обнаружены encoding/sourceProofSchemaV1.py и sourceProofRequestSchemaV1.py, proof/atomIndex.py, validation/sourceWorldChecker.py, sourceUsageConflictChecker.py, sourceProofCanonicalChecker.py, sourceSelectionChecker.py. Их ранее принятый A0→D/G1 evidence сохраняется. Пять public owners, request checkers, closure collector, mutation/recovery/finalizer в этой директории отсутствуют; предложенные signatures не являются runtime imports.

## Остаток инвентаризации

### Проектируемые Source POJO: размещение отдельно от actual

Актуализация 2026-11-22: concrete local methods `registry_identity`, `batch_shape`, `revision_shape`, `refusal_shape` и общие predicates описаны в source-core-mutation-contract.md §3 «Собственные local POJO methods». Эта детализация заменяет прежние отметки ниже «имена validators не зафиксированы» для перечисленных моделей; runtime и приёмка не заявлены. SourceRevisionChanges остаётся отдельным internal value, не public POJO.

Все пути ниже относительно `backend/app/dataModel/sourceVersioning/`; эти классы не объявляются существующими imports. Единственный источник exact полей и инвариантов — source-core-mutation-contract.md §§1, 4. Новые mirrors не создаются.

| Файл / класс | Ответственность и поля | Методы / проверка границы |
|---|---|---|
| sourceRegistryMutation.py / SourceRegistryCreate | CREATE operand: kind, identity, body | Construction/локальная validation; не создаёт revision и не пишет body |
| sourceRegistryMutation.py / SourceRegistryUpdate | UPDATE operand: kind, expected, body | Construction/локальная validation; expected остаётся precondition, не назначением seq |
| sourceRegistryMutation.py / SourceRegistryDelete | DELETE operand: kind, expected | Construction/локальная validation; не physical prune и не снятие holds |
| sourceRegistryMutation.py / SourceCollectionMutation | Membership operand: collection_id, expected_revision, body | Construction/локальная validation; None означает ожидаемое отсутствие revision, не missing artifact |
| sourceRegistryMutation.py / SourceRegistryMutationInput | operation_id, world_uid, execution_version, changes, membership | Локальная validation immutable batch §1; нет storage/phase/commit; concrete имена validators ещё не зафиксированы |
| sourceMutationOutcome.py / SourceMutationApplied | operation_id, world_uid, request_fingerprint, object_revisions, collection_revisions | Construction/shape validation; constructor не подтверждает commit; evidence обязан предъявить owning producer |
| sourceMutationOutcome.py / SourceMutationRefused | operation_id, world_uid, request_fingerprint, failure | Construction/shape validation; terminal refusal не смешивается с preflight failure |

SourceRegistryMutationKind — enum create/update/delete в sourceRegistryMutation.py; SourceRegistryChange — discriminated union существующих вариантов, не отдельный DTO-класс. Типы полей, strict/frozen правила и nullable обязательность см. owning §1/4; таблица не задаёт альтернативной schema.

`SourceRevisionChanges` отдельно находится в проекте `backend/app/application/worldData/sourceVersioning/mutation/revisionChanges.py`: internal frozen value с object_revisions/collection_revisions, без public/persisted/terminal роли. Его placement нельзя незаметно переносить в dataModel или выдавать как SourceMutationApplied. Собственные validator methods и единые predicate owners будущих моделей ещё требуют детализации; названия методов не выдумываются как уже принятые.

Это concrete список Source values, не завершение всей АР-6. Требуется отдельно сопоставить shared collaborators (ArtifactRef, FieldPathError, FieldRef/CheckedPath, aggregation, codec) с их owning контрактами и перечислить методы будущих исполнителей после АР-1…АР-5. Новые типы не созданы. Предлагаемые mutation outcomes/prepared values отсутствуют в фактическом inventory и не объявляются поставленными.
