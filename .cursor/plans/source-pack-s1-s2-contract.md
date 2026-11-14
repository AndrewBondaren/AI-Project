# Source / Pack S1–S2: единая редакция для приёмки

Редакция 2, 2026-11-14. Статус: ACCEPTED DESIGN в ограниченном S1/S2 scope, не IMPLEMENTED. Совместная статическая приёмка Source, Pack и Snapshot/Artifacts завершена; S2-TRACE-1 и S12-PACK-ERR-1 закрыты. Принятый Source proof design остаётся в source-proof-v2-contract-spec.md; этот документ добавляет две явно указанные internal операции. Public Source/Pack CRUD, DAG bindings, trusted acquisition admission/finalizer hookup, authored writer/bootstrap, Terrain/Regions и миграция старых форм не входят. Код до отдельного принятого implementation-плана через implement-plan не начинается.

Этот документ сводит предложения source-pack-boundary-response-2026-11-14.md (PACK-S1/S2) и pack-preparation-source-authority-contract.md §9–11. Предыдущие обсуждения сохраняются как evidence, не как параллельные варианты S1/S2. При обнаружении расхождения с ними либо принятым proof контрактом остановить зависимую работу и исправить конкретное расхождение; выбирать удобную редакцию автоматически нельзя. Акт статической проверки — source-pack-s1-s2-acceptance-2026-11-14.md; S2-TRACE-1 закрыт. Совместные verdicts записываются отдельно по этой редакции.

## 1. Дельта и ownership

| Изменение | Владелец, граница и совместимость |
|---|---|
| SourceProofSelector.check_coverage(input) | Source, новый pure internal метод; прежняя общая роль selector не считалась готовой сигнатурой |
| SourceProofCoverageCheckInput | Source, новый internal named BaseModel для отношения request/available и diagnostic root; не mirror proof, не public/persisted DTO |
| SourceOperation.CHECK_COVERAGE | Source, новое значение check_coverage в существующем enum; расширяется применимость существующих errors/context, не создаются дубль failure или codes |
| SourceCaptureRetentionBinding.collect_for_adoption(scope, request) | Source, новый internal read-only preflight; operation=ADOPT_CLOSURE |
| Последовательные preflight bind/reset → adopt bind/reset | Source и Snapshot; один живой outer writer scope, accepted adopt/signature/checks не меняются |
| Scoped read dependencies | Snapshot/Artifacts, новые internal ports в §4; не существующие public helpers и не готовая runtime реализация |
| Verified manifest extraction | Pack; возвращает исходные Source proofs из всех provenance rows, не создаёт proof |

Публичные Source POJO и canonical IDs не меняются: SourceCaptureRef(world_uid, artifact) указывает на finalized witness; SourceDurableProof(schema_version=1, world_uid, uses); SourceProofReadInput(world_uid, proof); SourceProofResult(proof, durable_refs). Их целевые импорты — app.dataModel.sourceVersioning.* по принятой спецификации. SOURCE_PROOF_SCHEMA_V1 и full closure semantics остаются прежними. Runtime наличие этих импортов этим документом не утверждается.

## 2. S1: pure coverage

Класс: app.application.worldData.sourceVersioning.proof.selector.SourceProofSelector.

Input: app.application.worldData.sourceVersioning.proof.coverageCheckInput.SourceProofCoverageCheckInput, concrete named BaseModel, frozen=True, strict=True, extra=forbid, revalidate_instances=always. Ровно два обязательных поля:

```python
request: SourceProofReadInput
available: tuple[SourceDurableProof, ...]

def check_coverage(self, input: SourceProofCoverageCheckInput) -> None | SourceFailure: ...
```

None означает только логическое покрытие. Ни вход, ни результат не удостоверяют finalization, origin или holds. Зависимости selector — Source validators, canonical atom enumeration и immutable descriptor/schema bindings. IO, Pack DTO, pins, holder lookup и public pipelines запрещены.

Порядок проверки фиксирован:

1. Strict revalidation request и всех available. Canonical form обязательна на входе, без normalization/repair. Expected world=request.world_uid; сверить request.proof.world_uid и каждый available, включая empty. Независимые дефекты агрегировать в стабильном порядке request → available index → use index; невалидная форма блокирует только зависимые comparisons.
2. Atom=(full SourceCaptureRef, object|collection variant, exact SourceVersionRef|SourceCollectionVersionRef). Full capture включает world и witness ArtifactRef. Dependency без того же capture не покрывает запрос. Повтор валидного proof между available допустим; canonical duplicates внутри proof — отказ.
3. Разные revisions одной identity в разных captures допустимы. Конфликт revisions одной dependency identity в одной full capture внутри available — REVISION_CONFLICT. Другая revision не покрывает requested atom.
4. Requested atoms должны быть подмножеством union available. Extra available допустимы; extra requested отвергаются даже при том же durable closure. Union существует только для сравнения, не выпускается как новый proof/provenance.
5. Empty requested допускает empty либо valid same-world available. Nonempty requested с available=() отвергается. Foreign-world empty available отвергается. Truth available проверяет verified origin/manifest path, truth requested — collector/adopt.

Результат отказа — существующий SourceFailure(operation=CHECK_COVERAGE, field_issues, logic_issues). Existing field codes: INVALID_SHAPE, INVALID_IDENTITY, NON_CANONICAL_PROOF. Logic: WRONG_WORLD, REVISION_CONFLICT, PROOF_MISMATCH для каждого missing requested atom. Requested context: group_index=None, use_index исходного use, source exact dependency ref, artifact capture witness. Available context: group_index исходного available index, use_index его use. Все nullable context поля задаются явно. Расширение group_index и применимости PROOF_MISMATCH относится только к этому методу.

Diagnostic root — ModelIdentity.of(SourceProofCoverageCheckInput), module app.application.worldData.sourceVersioning.proof.coverageCheckInput, qualname SourceProofCoverageCheckInput. Field paths строятся через CheckedPath/typed FieldRef к request/available, затем к полям существующих nested POJO; item(i) сохраняет исходный индекс. Для invalid whole available — путь его поля; неизвестный child адресуется содержащему известному полю. Existing CheckedPath.from_pydantic_loc сохраняет исходные validation locations. Synthetic argument root и handwritten string FieldSegment запрещены. Если failures восстанавливаются cold transport, exact root должен быть в его allowlist; persisted proof schema/type IDs не расширять.

## 3. S2: preflight и неизменный adopt

Класс: app.application.worldData.sourceVersioning.capture.retentionBinding.SourceCaptureRetentionBinding.

```python
async def collect_for_adoption(
    self, scope: CommitScope, request: SourceProofReadInput,
) -> SourceProofResult | SourceFailure: ...

# Ранее принятый контракт, без изменения:
async def adopt(
    self, scope: CommitScope, request: SourceProofReadInput,
    sources: tuple[VerifiedArtifactRef, ...], target: ArtifactHolderRef,
) -> SourceProofResult | SourceFailure: ...
```

Preflight требует valid task/database/write scope и unbound artifact helper. Один lexical bind(scope) → collector.collect(scope.read_scope, request, operation=ADOPT_CLOSURE) → reset в finally → result. Нет acquire/release/append/commit, origin authority или сохранения read facet в результате/cache/ledger. Invalid/foreign/revoked/read-only/already-bound scope отвергается infrastructure boundary до IO.

Допустимы sequential preflight bind/reset и adopt bind/reset на том же живом outer writer scope; nested binding остаётся запрещённым. Adopt повторно collect/check exact source set, actual holds и target перед acquire; preflight не заменяет эти проверки. Source не ищет отсутствующие origins, не освобождает источники и не коммитит. Empty proof требует sources=().

## 4. Точные internal зависимости

Все пути ниже относительно backend/app. Owning подробности guards/None/errors — Snapshot proposal §11; ниже единая обязательная декларация зависимости, не разрешение cross-class private calls новым callers.

| Port / модуль | Сигнатура | Concrete adapter / ответственность / отказ |
|---|---|---|
| IScopedArtifactRead, application/artifacts/contracts/scopedArtifactRead.py | read_scoped(scope: CommitReadScope, ref: ArtifactRef) → ArtifactRef или None; descriptor_scoped(scope, artifact_id: EntityUid) → ArtifactRef или None; storage_state_scoped(scope, ref) → ArtifactStorageEventKind или None | SqliteArtifactCatalog, db/repositories/sqlite/artifacts/catalogStore.py; descriptor/storage reads. None=отсутствующий факт, не sealed; DELETED явный. Corrupt descriptor/chain и full descriptor mismatch — PublicationInfrastructureError |
| IScopedArtifactHolderRead, application/artifacts/contracts/scopedArtifactHolderRead.py | holders_scoped(scope: CommitReadScope, ref: ArtifactRef) → tuple[ArtifactHolderRef, ...] | SqliteArtifactHolders, db/repositories/sqlite/artifacts/holderStore.py; actual hold identities; absent catalog → (); corrupt chain/owner → infrastructure |
| IScopedOperationRead, application/publication/contracts/scopedOperationRead.py | read_scoped(scope: CommitReadScope, operation_id: EntityUid) → OperationRecord или None | SqliteOperationStore, db/repositories/sqlite/snapshotCore/operations/operationStore.py; immutable operation/lifecycle evidence; absent → None, damaged state → infrastructure |
| IPinnedManifestAuthority, application/publication/contracts/pinnedManifestAuthority.py | require_open_manifest(scope: CommitReadScope, pin: ManifestPinRead) → ArtifactRef или ManifestReadRefusal | ExecutionPins; authenticated namespace/identity/OPEN/holder/world, без byte read; owning pin refusal сохраняется |
| PackPreparationManifestReader, application/worldData/pack/read/preparationManifestReader.py | read_source_proofs(scope: CommitReadScope, pin: ManifestPinRead, manifest: ArtifactRef) → tuple[SourceDurableProof, ...] или ManifestReadRefusal | Pack; exact verified manifest decode/admission/all proofs; owning manifest refusal, corruption/IO infrastructure |

Каждый scoped adapter strict-validates input и проверяет registry/task/database/lifetime до SQL. Единый coordinator/access identity обязателен. Не открывать read_scope/transaction/guard, не bind/acquire. Public holders/is_held/read не подставлять вместо scoped methods. Новые ports явно proposed; existing private primitives не становятся публичными.

Nested reads: catalog → _find/_descriptor/_storage → ScopedSqliteAccess; holders → own _holders → _chain/_hydrate → operation _load либо history.resolve_ref(scope=...) либо catalog._by_id; operation _load → _event/SqliteOperationArtifacts.read/terminal decode/SqlitePublicationEvidence.check → world._by_id/player._for_operation → ScopedSqliteAccess. Existing _find mismatch ValueError требует явной реализации promised infrastructure boundary, не catch по тексту исключения.

Pin path: require_open_manifest → existing _owner/_binding/_closed с тем же scope → descriptor_scoped → storage_state_scoped(SEALED) → holders_scoped(exact PinHolder). Absent binding отказывается; absent descriptor при persisted pin — corruption. Не вызывать hold_open/_checkpoint/acquire и не читать новый execution-store checkpoint внутри writer transaction.

Manifest path: require_open_manifest → exact ref equality → ArtifactFormatRegistryBinding.validate → bounded ReadableBlobBackend.read_verified → strict Pack decoder/admission → все manifest.parts[*].provenance.source_proof и manifest.assembly_provenance[*].provenance.source_proof (header/tile/chunk/location/settlement/region). Не фильтровать current/changed и не нормализовать. Missing/duplicate/orphan provenance rows — Pack refusal, не available=(). Duplicate proofs между валидными rows допускаются. Existing допустимый physical backend: ManifestBlobBackend → ContentAddressedBlobBackend → read_verified_file, без own guard/UOW; configured budget и pin.max_bytes ограничивают read. Registry lifetime проверить до и после awaited IO. Другой backend требует новой проверки composition.

Snapshot PackPreparationSourceAuthority, application/publication/service/packPreparationSourceAuthority.py, владеет register_sources(scope,target,request,grants) и resolve_sources(scope,target,request) → tuple[VerifiedArtifactRef, ...]. Register: scope/write/operation_id → scoped target operation/current lease → private preflight evidence → issued grants → scoped origin state/holds → IPreparationAuthorityStore.append(scope,binding). Resolve: те же guards → store.read(scope.read_scope,target,request) → exact preflight completeness → scoped origins/state/holds → VerifiedArtifactRef tuple. Store — contracts/preparationAuthorityStore.py и SqlitePreparationAuthorityStore в db/repositories/sqlite/snapshotCore/operations/preparationAuthorityStore.py, без own UOW. Missing registration/origin — PreparationAuthorityError; damaged ledger — infrastructure. Ни provider, ни store не вызывают collector/adopt и не приобретают holds.

Private evidence принадлежит Snapshot: exact outer scope object identity + full target lease + canonical request; immutable successful SourceProofResult, task/registry/database/connection identity. Проверять operation/world/target/lifetime перед register/resolve. Очистить в finally на commit/rollback/cancel/unknown; revoke/restart запрещают reuse. Raw tuple, persisted row и восстановленный grant не заменяют evidence.

## 5. Неизменный порядок composition

Outer owner — Snapshot PackPreparationRetention.adopt_and_finish, application/publication/service/packPreparationRetention.py. Это internal atomic storage operation внутри Pack prepare; новая public operation или DAG-нода не добавляется.

1. Открыть одну target writer transaction; target/fingerprint/phase и READY replay проверить owning Snapshot. Helper unbound. READY replay проверяет exact candidate и target holds, не требует старого живого origin.
2. Проверить заранее допущенные origins/pin и exact manifest scoped reads; извлечь proofs. Выполнить Source S1 coverage.
3. Выполнить Source S2 preflight bind/collect/reset. Required refs — данные; выбирать holder только из trusted acquisition context, не поиском любого holder по совпавшему ref.
4. Register/resolve provenance через scoped readers и private evidence. Operation origin требует exact source lease/fence/OperationHolder; pinned origin — exact manifest pin, root PinHolder либо child ArtifactRetentionHolder(manifest).
5. При unbound helper выполнить accepted adopt с OperationHolder(target): bind/collect/full checks/acquire/reset. Для нескольких proofs повторять шаги 2–5 последовательно. Late failure откатывает все прежние provisional registrations/acquisitions этой outer transaction.
6. Только outer owner завершает candidate/READY и COMMIT. Источники не release-ятся. Успех наружу — после commit.

Один непрерывный BEGIN IMMEDIATE общей SQLite DB удерживается от origin reads до COMMIT. Все GC physical deleters обязаны использовать тот же writer guard; bind/reset lock не снимает. Другой DB/backend либо удаление вне этого протокола не покрыты гарантией.

SourceFailure проходит SourcePreparationAuthorityAbort (application/publication/service/preparationAuthorityErrors.py) через outer rollback без перекодирования. Authority refusal — PreparationAuthorityError. Infrastructure/unknown commit или rollback остаются infrastructure/UnknownCommitOutcome; cancellation не создаёт terminal/release. PREPARING restart создаёт fresh evidence/preflight и повторно проверяет persisted origins; grants не возрождаются.

**Точный read refusal boundary (дельта редакции 2, S12-PACK-ERR-1):** оба read ports возвращают success | existing app.dataModel.worldPack.read.pinnedManifest.ManifestReadRefusal. Pack reader возвращает refusal от pin port без byte read/decode. Union не ловит infrastructure/invalid scope/unknown. Единственный Snapshot-owned internal carrier для этого refusal — app.application.publication.service.preparationAuthorityErrors.PackPreparationReadAbort(Exception), обязательное поле refusal: ManifestReadRefusal, __init__(self, refusal: ManifestReadRefusal) -> None. Constructor strict-revalidates existing refusal и сохраняет pin_id/ref/reason без перекодирования. Новый DTO/enum/public exception не вводится.

PackPreparationRetention.adopt_and_finish при ManifestReadRefusal от reader поднимает PackPreparationReadAbort внутри writer transaction. Глубокие pin consumers PackPreparationSourceAuthority/PreparationAuthorityIssuer явно проверяют union и поднимают тот же carrier в этой же transaction; другие уровни пропускают его. Catch выполняет только PackPreparationRetention снаружи async with publication_commits.transaction(target.operation_id), после confirmed rollback и revoke. Internal output adopt_and_finish явно расширяется с OperationRecord | SourceFailure до OperationRecord | SourceFailure | ManifestReadRefusal; он возвращает error.refusal. Это proposed изменение Snapshot internal boundary, не новая Source/public операция. Pack public error mapping остаётся за пределами принимаемого internal среза.

Если rollback выдаёт UnknownCommitOutcome, наружу выходит он с cause, а не ManifestReadRefusal. Refusal второго proof откатывает регистрации/acquisitions первого. Catch-and-commit внутри scope запрещён; тот же boundary обязателен и при отсутствии writes. Тест этого сценария обязателен при реализации.

Trusted acquisition admission и finalizer hookup не поставляются этим срезом. Указанный operation-origin branch нельзя объявлять production-ready до отдельного принятого контракта. Terminal replay Source finalizer не выдаёт authority. Это явная граница применимости, не разрешение placeholder/fabricated origin.

## 6. Приёмка и дальнейшая поставка

Срез не добавляет публичные C/R/U/D данных или настроек; добавляет internal read/check и разрешает конкретную scoped composition. Public READ не меняется; schema/descriptor settings immutable. DAG orchestration, маршруты HTTP и существующий порядок основного плана не меняются. Критерии трёх запретов DAG, ответственности классов, typed errors, границ и nested calls проверяются по акту dag-generator-interface.mdc; matrix статической проверки находится в акте S1/S2. Public prepare/DAG всей системы этим не принимаются.

Обязательные проверки реализации: canonical/world/empty/duplicates/historical/conflict/subset и extra atom при том же closure; несколько независимых diagnostics с typed paths; отсутствие IO у S1; unbound/sequential/nested/foreign/task/revoked scope; отсутствие acquire до checks; rollback после последнего acquire; cleanup cancel/unknown; two-connection GC/pin-close serialization; fresh PREPARING restart и READY replay; полнота Pack provenance extraction. Реализация новых scoped ports должна доказать весь read tree, а не только совпадение сигнатур.

Порядок поставки после совместного review: зафиксировать verdicts по редакции → синхронизировать accepted Source specification с явно перечисленной дельтой → подготовить отдельный implementation-план с prerequisites, файлами и проверками → принять его по всем правилам → код через implement-plan. Принятие S1/S2 не отменяет prerequisites основного world-source-versioning.md. Нельзя под видом этого среза реализовать весь authority protocol, authored writer или миграцию Source.

Редакция 1 получила одно замечание Pack S12-PACK-ERR-1: success-only read signatures и неназванный carrier. Первоначальный Snapshot PASS отозван после этого finding. Редакция 2 включает точное owning исправление из Snapshot proposal §12; оба владельца повторно проверили дельту и закрыли finding 2026-11-14. Остальные рассмотренные S1/S2 semantics не менялись. Статус/таблица verdicts внесены после review без изменения проверенных signatures/semantics.

| Владелец | Verdict по редакции 2 |
|---|---|
| Source | PASS статической проверки ограниченного design; matrix и evidence в source-pack-s1-s2-acceptance-2026-11-14.md |
| Pack | PASS редакции 2, сообщение owning чата 01a1cfce-ff7d-7e30-b738-f075bf490f13 от 2026-11-14; S12-PACK-ERR-1 CLOSED |
| Snapshot/Artifacts | PASS редакции 2; snapshot-review-source-pack-s1-s2-r2.md; S12-PACK-ERR-1 CLOSED |
