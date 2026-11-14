# Source → Pack: адресная сверка принятой границы

S1/S2 сведены в [единую редакцию 2](source-pack-s1-s2-contract.md), ACCEPTED DESIGN в ограниченном S1/S2 scope после совместного review 2026-11-14. Разделы proposal ниже сохраняются как история и evidence; они не являются параллельной принимаемой редакцией. Proof specification синхронизирована в §6/11.3/13; runtime не реализован. Implementation-план дельты содержит незакрытые prerequisite gates.

Актуальная фиксация scope/статусов — [контрольная точка](source-contract-baseline-2026-11-14.md), §4. Пользователь разрешил отдельный design-срез PACK-S1/S2 после обсуждения участвующих Source/Pack/Snapshot/Artifacts. Предложение ниже требует совместного review; принятая proof-спецификация не изменена.

2026-11-14. Основание: source-proof-v2-contract-spec.md §6, §11.1–11.4, §12.1–12.3 и независимая приёмка 2026-11-13. Ниже принятый design, не утверждение наличия runtime API. Terrain execution не меняет этот контракт.

## Capture и proof

Для поля PackPreparationBody.capture подходит существующий Source-owned `app.dataModel.sourceVersioning.sourceCaptureRef.SourceCaptureRef(world_uid: EntityUid, artifact: ArtifactRef)`. Artifact указывает **на finalized witness**, формат `source.capture-witness` v1, SQL_ROWS, row_count=1; не на body. Witness ссылается на `source.capture` v1 BLOB. Ref сам по себе не удостоверяет committed finalization или удержание; это проверяет Source.

Публичные модели под `app.dataModel.sourceVersioning` frozen/strict/extra-forbid/revalidate-always, tuple collections:

* `sourceCaptureUsage.SourceCaptureUsage(capture, dependencies)`.
* `sourceDurableProof.SourceDurableProof(schema_version: Literal[1], world_uid, uses)`.
* `sourceProofInput.SourceProofInput(world_uid, uses)` и `SourceProofReadInput(world_uid, proof)`.
* `sourceProofResult.SourceProofResult(proof, durable_refs)` — проверка и полный closure, не authority token.

Единственный доменный failure — SourceFailure(operation, field_issues, logic_issues), §11.3; SourceProofFailure не вводится. Groups/select контракты остаются по принятому §6, их замены этим ответом нет.

## Canonical binding

`app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1.SOURCE_PROOF_SCHEMA_V1`, existing CanonicalCodec/content_digest. Pack переиспользует Source bindings при композиции собственного manifest, без копий типов, перенумерации и выбора current global registry. Capture ref ID **71129** (world_uid, artifact); proof **71131** (schema_version, world_uid, uses); usage **71130**; selection **71138**. Transitive dependencies: 71001 descriptor category; 71110–71114 identities; 71120 revision; 71121–71122 version refs; 71123 dependency set. Capture body **71127**, witness **71128**, mappings **71124–71126**. Existing ArtifactKind **20003**, ArtifactRef **20107**. Точный порядок всех полей — таблица §11.4; requests/results/errors в persisted manifest не входят. Pack fingerprint кодирует вложенные Source values штатно; схема Source не определяет outer Pack fingerprint recipe.

## Retention и незакрытая граница

Принят internal `app.application.worldData.sourceVersioning.capture.retentionBinding.SourceCaptureRetentionBinding`:

```python
async def adopt(self, scope: CommitScope, request: SourceProofReadInput,
                sources: tuple[VerifiedArtifactRef, ...],
                target: ArtifactHolderRef) -> SourceProofResult | SourceFailure: ...
```

VerifiedArtifactRef — existing `app.dataModel.artifacts.lifecycle.holders`, пара ref+holder. Source заново вычисляет полный closure внутри borrowed write scope, сравнивает полный набор sources, проверяет каждый реальный hold и target, затем приобретает target holds. Sources не ищутся автоматически; нет latest fallback, release или собственного commit. Успех наружу — после caller commit. Empty proof требует sources=().

§11.1 определяет lifecycle: preparation OperationHolder удерживает каждый ref; published Pack closure получает ArtifactRetentionHolder(sealed_manifest_ref) при наличии внешнего root manifest. Несколько historical captures допускают разные source holders. Но **конкретный owning capture retention context/authority resolver с Input/Output ещё OPEN**: принятая спецификация не объявляет такой POJO/API. Ref/proof/READ result не позволяют восстановить законный holder автоматически. Нельзя подставить фиктивный OperationHolder или считать capture ref authority.

Для Pack остаётся внешний integration gate: какой preparation/publication owner сохраняет и предоставляет точные per-ref holder identities после restart, как binding получает sources и доказывает их lifecycle, как обеспечивается root lifetime manifest в общей transaction. Resolver нельзя объявить готовым, выбрать за Source/Artifacts его сигнатуру или заменить зеркальным DTO. Public capture/DAG entry и runtime реализация finalizer/collector/adopt также не закрыты приёмкой design proof. Этот ответ не разрешает новый DAG маршрут.

## PACK-S1/S2: Source-owned proposal для совместной проверки

2026-11-14. **PROPOSED, НЕ ACCEPTED/IMPLEMENTED.** Разрешён только этот design-срез; authored writer/bootstrap, Terrain/Regions, public API, DAG nodes и код не входят. Общая Snapshot authority-схема автоматически не принимается.

### S1. Pure logical coverage

Владелец — existing proposed `app.application.worldData.sourceVersioning.proof.selector.SourceProofSelector`. После Pack review двухаргументная форма заменена явным internal input record: это изменение **proposal**, не принятой спецификации.

`app.application.worldData.sourceVersioning.proof.coverageCheckInput.SourceProofCoverageCheckInput` — named concrete BaseModel, frozen/strict/extra-forbid/revalidate-always, два обязательных поля `request: SourceProofReadInput`, `available: tuple[SourceDurableProof, ...]`. Это контекст отношения requested↔coverage и owning root диагностики, не копия proof/hold/receipt. Поля существующих Source POJO не дублируются; public pipeline/endpoint не добавляется. Ни group-input admission, ни SourceProofReadInput не представляют это отношение, поэтому не переиспользуются с изменённым смыслом.

Дополнительный internal метод:

```python
def check_coverage(
    self, input: SourceProofCoverageCheckInput,
) -> None | SourceFailure: ...
```

None означает только доказанное логическое включение, не finalized/held/authenticated origin. Новый public DTO/result/token не нужен. В описании ниже request и available — поля input. Зависимости — существующие Source validators/canonical atom enumeration, immutable descriptor bindings и SOURCE_PROOF_SCHEMA_V1; никаких DB/Pack DTO/holders/public pipelines. Предлагается добавить **одно** значение `SourceOperation.CHECK_COVERAGE` (wire check_coverage) в existing enum; это proposal roster extension, не уже принятая операция. Новые field/logic code enums не создаются.

Порядок и semantics:

1. Strict revalidation request и каждого available proof; все persisted proofs должны быть canonical уже на входе. Не нормализовать/ремонтировать их. Expected world — request.world_uid; сверяется с request.proof.world_uid и каждым available world, в том числе для пустых proofs. Все независимые field/logic defects агрегируются в стабильном порядке request → available index → use index; зависимые сравнения пропускаются при невалидной форме.
2. Atom — `(full SourceCaptureRef, variant object|collection, exact SourceVersionRef|SourceCollectionVersionRef)`. Full capture identity включает world и witness ArtifactRef; совпадение dependency без того же capture не покрывает запрос. Порядок available не влияет на результат включения. Повторы одного валидного proof между available допустимы; внутренние canonical duplicates — отказ. Union существует только локально для сравнения, не возвращается как новый provenance.
3. Несколько historical captures и разные revisions одной object identity в разных captures допустимы. Для одной full capture identity конфликтующие revisions одной dependency identity в available отклоняются REVISION_CONFLICT, а не объединяются как допустимые альтернативы. Сопоставление requested с coverage — exact atoms; другая revision не покрывает requested.
4. Каждый requested atom должен быть в union available. Дополнительные atoms в available допустимы; дополнительный atom в requested — отказ даже при абсолютно одинаковом durable closure. Нельзя сравнивать только ArtifactRef sets/content hashes.
5. Валидный пустой requested покрывается пустым или непустым available того же world. Непустой requested и available=() — отказ. Пустые available proofs чужого world всё равно отказ. Pure проверка не подтверждает truth/finalization available: перед ней Snapshot/Pack удостоверяют origin и exact manifest; Source collector/adopt проверяет requested captures/closure по принятому контракту.

Ошибки через existing SourceFailure(operation=CHECK_COVERAGE): INVALID_SHAPE/INVALID_IDENTITY/NON_CANONICAL_PROOF — existing field rules; WRONG_WORLD — world mismatch; REVISION_CONFLICT — указанное противоречие одного capture; PROOF_MISMATCH — каждый непокрытый requested atom. Для requested issue group_index=None, use_index — исходный requested use, source — exact atom ref, artifact — capture witness. Для available issue group_index — available index, use_index — его use. Остальные nullable context поля задаются явно. Применение PROOF_MISMATCH и group_index к этому internal методу — **явное расширение таблицы применимости** existing codes, не молчаливое изменение §11.3. Все field paths имеют единый root SourceProofCoverageCheckInput; request/available — его поля, выбираемые через typed FieldRef, далее используются typed selectors вложенных POJO. Произвольные строковые lookup имён полей запрещены. При invalid proof shape не читать его atoms.

Отказ в приёмке: method принимает Pack manifest/pin; совершает IO; считает closure равенство coverage; считает чужой empty world допустимым; silently нормализует proof; возвращает authority token; делает union разных revisions в одном capture без отказа.

**Exact diagnostic root после review:** `ModelIdentity.of(SourceProofCoverageCheckInput)`; module `app.application.worldData.sourceVersioning.proof.coverageCheckInput`, qualname `SourceProofCoverageCheckInput`. Старое предложение synthetic argument root без POJO отозвано: текущий ModelIdentity требует named concrete BaseModel, ValidatedFieldPath начинается field segment этого root.

Повторный Pack review 2026-11-14: замечание synthetic diagnostic root снято для этой формы. Это локальный consumer verdict, не общая приёмка S1/S2.

Путь к available[i]: `CheckedPath.root(SourceProofCoverageCheckInput).field(FieldRef(lambda: SourceProofCoverageCheckInput, lambda x: x.available)).item(i).freeze()`. Далее при необходимости `.field(FieldRef(lambda: SourceDurableProof, lambda p: p.uses))` и индексы/typed nested selectors. Request root строится через FieldRef x.request, затем SourceProofReadInput.proof/world_uid. Неверная форма всего available адресуется его root field; неизвестный child — содержащему известному полю. Не конструировать FieldSegment со строками вручную. Runtime transport/cold diagnostics restore обязан включить этот exact diagnostic owner в allowlist, если такие failures восстанавливаются; не добавлять его в persisted SOURCE_PROOF_SCHEMA_V1 и не назначать proof type ID. Для malformed input aggregate validation сохраняет исходные Pydantic loc через existing CheckedPath.from_pydantic_loc и existing SourceFailure, не выпускает невалидный unchecked record.

**Pack consumer evidence:** Pack подтвердил извлечение всех `manifest.parts[*].provenance.source_proof` и `manifest.assembly_provenance[*].provenance.source_proof` (header/tile/chunk/location/settlement/region). Duplicate proofs между строками можно оставить; union/normalization не задача reader. Missing/duplicate/orphan metadata provenance — отказ owning Pack manifest admission, не available=(). Эти пути — ответ Pack, Source не импортирует manifest DTO. Общая приёмка ещё не выполнена.

### S2. Scoped preflight с сохранением existing adopt

Владелец — existing proposed `SourceCaptureRetentionBinding`, тот же модуль `capture/retentionBinding.py`. Дополнительный internal метод:

```python
async def collect_for_adoption(
    self, scope: CommitScope, request: SourceProofReadInput,
) -> SourceProofResult | SourceFailure: ...
```

Использует existing operation=ADOPT_CLOSURE; это фаза той же adoption-проверки, не новая public READ. Требует valid task/database/write scope и **unbound** ArtifactScope. Делает один lexical bind(scope), вызывает existing collector.collect(scope.read_scope, request, operation=ADOPT_CLOSURE), выходит из bind и возвращает результат. Не acquire/release/append/commit, не выдаёт origin authority. Read facet действует только в этом outer transaction и не сохраняется в result/cache/ledger. Чужой/expired/read-only/already-bound scope — existing infrastructure refusal до IO, не Source business error.

**Проверенное основание:** `db/repositories/sqlite/artifacts/access/artifactScope.py::bind` проверяет registry/write capability и _require_unbound, затем ContextVar.set/reset в finally. Запрещён reentrant bind; после выхода token сбрасывается. Это даёт статическую feasibility последовательных lexical binds, но само по себе не является Source contract acceptance. Предлагается явно разрешить **preflight bind→unbind, затем existing adopt bind→unbind** на одном живом outer writer scope. Adopt сохраняет всю принятую сигнатуру и сам повторно вычисляет closure/проверяет holds перед acquire. Запрет nested/foreign/already-bound bind остаётся.

Предлагаемый caller trace (Snapshot владеет outer transaction и проверяет свой proposal):

1. `PackPreparationRetention.adopt_and_finish` открывает одну target writer transaction; target/phase/fingerprint и replay проверяются owning Snapshot. READY replay не реконструирует старые grants.
2. Snapshot explicit scoped pin/origin checks и Pack-owned verified manifest reader используют read facet **той же transaction**, без своего UOW/ArtifactScope.bind. Source получает только extracted proofs. Source.check_coverage проверяет logical coverage. Pin/authentication failure не переводится в Source proof error.
3. Source.collect_for_adoption выполняет ограниченный preflight выше. Snapshot получает full required refs как данные, не authority. Snapshot issuer выбирает origins только из trusted acquisition context; совпадение refs не даёт права изобретать holder. Grants и сохранённый provenance — ответственность Snapshot.
4. register_sources/resolve_sources проверяют full set и origins внутри той же outer scope explicit scoped reads, не вызывают private collector и не bind-ят helper. Для использования результата preflight Snapshot должен хранить scope-local evidence, привязанный к exact request/target/task/database/живой transaction; raw caller tuple таким evidence не является. Нужный private механизм Snapshot ещё должен подтвердить в своём proposal, Source не вводит его DTO.
5. При unbound helper вызвать existing adopt(scope, request, sources, OperationHolder(target)). Он повторяет collect/full set/actual holds/target checks, затем acquire. Source не освобождает source holds. При нескольких proofs каждый failure отменяет всю outer transaction, включая earlier acquisitions и provisional provenance registration.
6. Только owning Snapshot завершает READY/commit. SourceFailure из S1/preflight/adopt прекращает путь через согласованный rollback carrier; не проглатывается для commit. Business refusal наружу только после подтверждённого rollback, infrastructure/unknown остаются своим исходом. Cleanup bind происходит в finally. Нет release источников или fabricated terminal при unknown.

Register может append provisional provenance до adopt; это не acquire и не durable успех до commit. Все Source checks и Snapshot origin checks должны завершиться до соответствующего target acquire; late failure откатывает предыдущие effects. Если required origin/hold изменён собственными действиями outer transaction после preflight, adopt обязан обнаружить это повторно. Concurrent release/GC исключается owning transaction/guard контрактом, который подтверждает Snapshot; Source не выводит защиту из одной аннотации CommitReadScope.

### Finalizer context и restart — ограничения предложения

Issue_operation нельзя авторизовать одним SourceCaptureRef или terminal replay finalizer: replay не обещает новый acquisition/hold. Успешная ветка SourceCaptureFinalizer действительно имеет computed closure и проверенную lease в scoped acquisition, но публичного/готового context provider из этого не следует. Snapshot обязан конкретизировать trusted issuer admission/commit acknowledgement, а Source — отдельно согласовать точное подключение, если потребуется изменить finalizer. Автоматический callback или новый вызов issuer внутрь принятого finalizer этим proposal не добавлен.

После restart используется подтверждённый Snapshot provenance, не восстановленный runtime grant. Requested proof и full closure пересчитываются; actual origin/holder checks повторяются; разные refs могут иметь разные origins/captures. Отсутствие регистрации/закрытый origin в PREPARING не ремонтируются поиском других holders. READY/replay lifecycle подтверждает Snapshot.

### Обязательная проверка перед приёмкой среза

### Полученные межвладельческие заключения (2026-11-14)

Pack подтвердил S1 semantics и exact diagnostic root; Snapshot подтвердил совместимость S1 input и статическую feasibility S2. Snapshot evidence — `pack-preparation-source-authority-contract.md` §10. Это завершённая адресная сверка предложения, **не совместная приёмка реализации и не автоматическое изменение accepted Source spec**.

Условия Snapshot, обязательные для S2: одна непрерывная BEGIN IMMEDIATE transaction в общей SQLite DB от origin reads до commit; все physical deleters соблюдают тот же GC writer guard; lexical bind/reset не освобождает transaction lock. Explicit scoped readers не используют unbound helpers, открывающие own UOW, и не выполняют скрытый bind. Scope-local evidence приватен Snapshot, keyed по exact outer scope object + full target lease + canonical request; проверяются task/registry/database/connection, operation/target/world. Evidence очищается в finally при любом исходе и не переиспользуется после revoke/restart. Эти private adapters/evidence пока proposed, не готовые методы CommitScope.

При late failure откатываются provenance registration и все предыдущие target acquisitions; unknown остаётся unknown. PREPARING restart повторяет checks/preflight; READY replay не требует живого прежнего origin. Эти условия не добавляют authority SourceProofResult и не отменяют повторные checks внутри accepted adopt.

**Отдельный незакрытый участок:** подключение trusted issuer к acquisition/commit acknowledgement finalizer. S1/S2 его не реализуют и не разрешают; replay finalizer не даёт acquisition authority. Полный operation-origin path нельзя объявлять готовым по результатам этого review. Authored writer/bootstrap остаётся вне данного среза. Перед freeze повторно сверить §10 и текущую Source proposal редакцию; two-connection/rollback/restart runtime evidence пока отсутствует.

Source: canonical/world/empty/conflict/subset cases; одинаковый closure с extra logical atom; original refs неизменны. Snapshot/Artifacts: последовательный bind на том же scope, nested/cross-task/foreign/stale scope refusals, rollback/cancellation cleanup, same transaction guard на чтении, provenance identity и restart, no acquire до checks. Pack: полнота извлечения всех provenance proofs из exact verified manifest. Все три владельца подтверждают роли/эффекты/границы; затем общая проектная приёмка. Runtime tests/SQL/код сейчас не выполнялись. Этот документ не переносит ACCEPTED verdict proof на расширения.
