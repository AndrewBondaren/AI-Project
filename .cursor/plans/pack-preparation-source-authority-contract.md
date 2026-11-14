# Pack preparation: Source-holder authority — полный contract proposal

Уточнение S12-PACK-ERR-1: §12 задаёт result unions pin/manifest readers и exact Snapshot rollback carrier. Он заменяет прежние success-only signatures и неназванный «owning carrier» в §4/9/11 для этих двух readers. Единая S1/S2 редакция должна включить это уточнение до окончательного verdict.

Operation-origin acquisition/ack/restart уточнён отдельно: [snapshot-source-acquisition-admission.md](snapshot-source-acquisition-admission.md). Это proposed owner-local register до finalize + checked confirm/resume после него; finalizer signature остаётся прежней, Pack target/request появляется позже. Explicit source handle в уточнённом issue_operation заменяет прежнюю неявную origin authority из scope. Совместная приёмка этого отдельного участка ещё требуется.

2026-11-14. **PROPOSED FOR ACCEPTANCE**, не runtime PASS. Владелец — Snapshot; application/publication — его внутренний слой. Документ заменяет прежний PARTIAL и закрывает проектный пробел write-side конкретным предложением. Принятие пользователем READY candidate в existing ledger не означает автоматического принятия новых declarations ниже.

Scope: запись происхождения Source holds, restart resolution и atomic adoption для Pack. Нет новых holder kinds, независимых version counters, receipt stores, DAG-нод, генераторных bindings, миграций или legacy adapters.

## 1. Проверенные основания и принятое решение

Existing SourceCaptureFinalizer по source-proof-v2-contract-spec.md §12.3 после успешного finalize имеет OperationHolder на witness + capture body + computed closure. Replay finalized capture не гарантирует текущего holder. SourceCaptureRetentionBinding.adopt принимает SourceProofReadInput + tuple[VerifiedArtifactRef,...], вычисляет полный closure, проверяет источники и приобретает target holds в borrowed scope.

Existing ExecutionPins удостоверяет pin identity/OPEN lifetime и manifest hold. Pin удерживает manifest, **не каждый child**. Для child источник — existing ArtifactRetentionHolder(manifest) при доказанной Source coverage этого manifest. Нельзя заменить этот источник фиктивным PinHolder(child).

Решение proposal: сохранять provenance в existing target preparation ledger; запись допускает только opaque runtime grant от trusted acquisition owner. Grant — не public DTO, не serializable evidence и не новый holder. После commit durable binding заменяет grant для restart; все actual holds/lifetimes проверяются заново.

## 2. Классы, файлы, ответственность

Пути относительно backend/app/:

| Класс | Файл | Ответственность / запрет |
|---|---|---|
| PreparationAuthorityIssuer | application/publication/service/preparationAuthorityIssuer.py | Выдаёт grant только из проверенного acquisition context. Не принимает произвольные sources, не создаёт holds, не вызывает public Source/Pack |
| PackPreparationSourceAuthority | application/publication/service/packPreparationSourceAuthority.py | register_sources/resolve_sources, проверка target и immutable provenance. Не вычисляет Source semantics и не владеет COMMIT |
| IPreparationAuthorityStore | application/publication/contracts/preparationAuthorityStore.py | Append/read provenance в existing operation ledger, без собственного UOW |
| SqlitePreparationAuthorityStore | db/repositories/sqlite/snapshotCore/operations/preparationAuthorityStore.py | Ledger binding/constraint/codec checks. Не авторизует исходный holder по наличию UID |
| IPinnedManifestAuthority | application/publication/contracts/pinnedManifestAuthority.py | Scoped проверка существующего pin/manifest context, без acquire/reopen |
| ExecutionPins | db/repositories/sqlite/worldPack/executionPins.py | Реализует scoped pin authority extension; сохраняет namespace/execution/OPEN semantics |
| SourceCaptureRetentionBinding | application/worldData/sourceVersioning/capture/retentionBinding.py | Existing exact Source closure/adopt checks; новых public методов этим proposal не требуется |

Композиция разрешает issuer только владельцам acquisition: Source capture/preparation owner для operation path и authenticated ExecutionPins binding для pinned path. Ни Pack public input, ни generic storage reader не получают issuer. Exact instance/task/database binding проверяется runtime registry; один лишь protocol class не доказывает происхождение.

## 3. Новые records и reuse

Proposed dataModel/publication/preparationSourceAuthority.py. Все records strict/frozen/extra-forbid/revalidate-always, tuple collections, обязательные поля без defaults. Existing refs, leases, proof и VerifiedArtifactRef переиспользуются.

- PreparationSourceBinding: target: OperationLeaseRef; request: SourceProofReadInput; entries: tuple[PreparationSourceEntry,...].
- PreparationSourceEntry: source: VerifiedArtifactRef; origin: PreparationSourceOrigin.
- PreparationSourceOrigin — discriminated union:
  - OperationSourceOrigin(kind: Literal[OPERATION], lease: OperationLeaseRef).
  - PinnedManifestSourceOrigin(kind: Literal[PINNED_MANIFEST], pin: ManifestPinRead, manifest: ArtifactRef).
- PreparationSourceOriginKind(StrEnum): OPERATION, PINNED_MANIFEST.

Origin не зеркалирует VerifiedArtifactRef: source сообщает, **какой holder фактически удерживает ref**, origin — **какой acquisition context разрешил его использование**. Operation source holder обязан быть OperationHolder с точно равным origin.lease. Pinned origin source holder: для самого manifest — PinHolder(pin.pin_id); для child — ArtifactRetentionHolder(origin.manifest). Другие holder kinds в этой версии origin contract запрещены. Это не wire version counter.

ManifestPinRead используется целиком из dataModel/worldPack/read/pinnedManifest.py; нового PinIntent DTO нет. max_bytes остаётся проверенным read budget исходного pin read, не даёт новых прав. Все worlds target/request/origin должны совпадать; ArtifactRef сам world не содержит.

Entry refs уникальны внутри одного proof. Несколько origins могут покрыть разные refs одного proof; один ref выбирается ровно один раз по переданному порядку grants, без произвольного поиска holder. Empty proof требует entries=(). Same ref может повторяться в bindings разных proof.

Запись не является Source proof/receipt и не сохраняет SourceProofResult. Истинность Source proof/closure по-прежнему удостоверяет Source. Provenance record не объявляет terminal и не добавляет holder.

## 4. Runtime grant и точные signatures

PreparationAuthorityGrant в application/publication/contracts/preparationAuthority.py — opaque runtime class с закрытым constructor. Registry хранит exact object identity, issuer, task/database, target lease, exact proof request, checked origin и covered refs. Grant нельзя сериализовать, собрать из UID, принять из public API или восстановить после crash.

Issuer:

```python
async def issue_operation(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput,
) -> PreparationAuthorityGrant: ...

async def issue_pinned_manifest(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput, pin: ManifestPinRead,
) -> PreparationAuthorityGrant: ...
```

issue_operation вызывается trusted source acquisition owner в **его** active scoped acquisition context. Source lease берётся из checked scope binding владельца; не является параметром caller и не выводится из target. Origin world/kind/lease/fence/seals/holder chains проверены; разрешённая coverage — refs, которые этот owner реально приобрёл/удерживает в данной операции, а не holders(ref) произвольных владельцев. Scope должен быть owner write context; read scope и вручную указанный чужой operation_id не заменяют admission issuer.

Grant может быть provisional до исходного commit, но использовать его вне source scope можно лишь после confirmed source commit; registry отмечает это через acknowledgement transaction owner. Rollback/unknown аннулируют grant. Если source=target и scope тот же, register допускается в этом scope до commit. Никакого автоматического reissue после lost grant: trusted owner заново открывает проверенный acquisition context либо используется уже committed provenance registration.

issue_pinned_manifest проверяет pin через новый internal scoped port:

```python
async def require_open_manifest(
    self, scope: CommitReadScope, pin: ManifestPinRead,
) -> ArtifactRef: ...
```

Это extension ExecutionPins к уже существующим _owner/_binding/held_manifest invariants: exact namespace/execution/invocation/read-key/pin/world, не CLOSED, pin OPEN, actual manifest PinHolder, sealed descriptor и bounded verified bytes. Проверка выполняется в переданном transaction, не hold_open с nested writer UOW; pin не создаётся. Отключённый execution store не объявляется открытым по stale pin row.

Далее Pack-owned typed manifest decoder извлекает stored proofs. Проверка requested proof против stored proofs и предварительный scoped Source collector требуют **явных proposed extensions §9**; existing durable_refs не доказывают logical coverage. До их согласования этот путь не считается готовым. Grant не выдаётся по одному pin_id или совпадению bytes. Для каждого child проверяется actual ArtifactRetentionHolder(manifest). Отсутствующие child holds не создаются issuer. Публичные pipelines не вызываются.

Provider:

```python
async def register_sources(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput,
    grants: tuple[PreparationAuthorityGrant, ...],
) -> None: ...

async def resolve_sources(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput,
) -> tuple[VerifiedArtifactRef, ...]: ...
```

register не принимает caller sources. Он получает pairs/origins из exact registry grants и повторно проверяет durable origin evidence в target writer scope. Grants проверяются до effects; exact target/request совпадают. Из нескольких grants берётся детерминированная полная coverage request, не union чужих refs; extra/duplicate source coverage не скрывается. Source-owned collector определяет полный required set. После validation сохраняется один PreparationSourceBinding; grant consumption не является durable outcome.

Store:

```python
async def append(
    self, scope: CommitScope, binding: PreparationSourceBinding,
) -> None: ...

async def read(
    self, scope: CommitReadScope, target: OperationLeaseRef,
    request: SourceProofReadInput,
) -> PreparationSourceBinding | None: ...
```

Store доступен provider, не public caller. Same exact binding — no-op; different entries/origins при том же target preparation + exact proof — immutable conflict. Новый target fence не переиспользует authority прежнего без явного accepted takeover protocol. Store.read None означает отсутствие регистрации; provider.resolve_sources переводит его в AUTHORITY_NOT_REGISTERED, а не ().

## 5. Persisted schema и trusted acquisition identity

Данные хранятся как immutable provenance binding **в existing preparation ledger**. Semantic key: target operation_id + preparation_fingerprint + canonical exact SourceProofReadInput; target fence хранится и проверяется. Payload содержит PreparationSourceBinding и checksum existing canonical storage механизма. При digest lookup обязательно сравнение full canonical proof, не доверие одному hash. New records требуют owning canonical IDs/codec registration review; независимый version counter и отдельный receipt store запрещены.

Source operation authority доказывается checked issuance из acquisition owner + persisted exact holder event chains. Pinned authority доказывается checked issuance из authenticated pin context + persisted pin identity и actual retention chains. Store не принимает произвольную запись минуя provider; constructor доступа/DI и runtime registry проверяются negative tests. Это граница доверенного application кода, не утверждение криптографической защиты против произвольного SQL writer.

Важно: существующий generic transaction(operation_id) сам по себе не удостоверяет acquisition context. Для issue_operation необходима owner-issued runtime admission в том же scope registry при реальном reserve/acquire/finalize. Это **предлагаемое изменение internal composition/registry**, которым владеет Snapshot. Его нельзя считать уже реализованной возможностью CommitScope. No external public method/новый DAG token не вводится. Поля runtime admission: owner instance identity, database/task/scope generation, exact source lease, checked acquired ref set. Она создаётся trusted acquisition owner после проверенного acquisition, а не caller произвольного transaction.

При restart resolve читает durable registration, полные source identities и origin context; оригинальный runtime grant не восстанавливается. Источник не переизбирается. Если pin закрыт, lease superseded либо hold исчез — явный отказ. Missing acquisition registration не чинится поиском чужого live holder. Persisted candidate/READY history не используется для fabrication provenance.

## 6. Atomicity и lifetime

Рекомендуемый production порядок: source finalize/acquire подтвердил holds → issue grant из checked origin → target writer scope → register_sources → resolve_sources → scoped Source adopt всех proofs → exact candidate binding → scoped finish → outer COMMIT. Source world/proof failures выходят после confirmed rollback. READY не наблюдается отдельно от adopted target holds и candidate.

Если registration сохраняется ранее в PREPARING, она не продлевает pin/holds. Последующий resolve обязан снова проверить origins. Такое сохранение допускается как durable preparation input, но не как READY/evidence живой защиты. Смена origins той же registration не разрешена; при утрате источника нужна новая preparation identity по owning Pack правилам, не скрытая перезапись.

Source commit и target commit могут быть разными: это безопасно, поскольку source hold защищает bytes, а gap закрывается повторной проверкой под общим target write/GC guard. Source release, pin close и GC обязаны сериализоваться с проверкой+adopt. После успешного target adoption дальнейший release исходного pin не разрушает target protection.

READY replay использует committed candidate + target holds и не требует живого старого pin. Нельзя повторно resolve_sources и отвергать уже READY только потому, что исходный acquisition завершился. PREPARING resume требует живых origin либо уже атомарно завершённого accepted adoption evidence; данный proposal не объявляет отдельного частичного adoption shortcut. Поэтому не продвигать partially adopted PREPARING как READY.

## 7. Ошибки и результаты

Proposed dataModel/publication/preparationAuthorityFault.py:
- PreparationAuthorityCode(StrEnum): AUTHORITY_NOT_REGISTERED, INVALID_GRANT, TARGET_MISMATCH, ORIGIN_CLOSED, STALE_ORIGIN, MISSING_SOURCE_HOLD, COVERAGE_MISMATCH, IMMUTABLE_BINDING_CONFLICT.
- PreparationAuthorityFault: operation_id: EntityUid; code: PreparationAuthorityCode; artifact: ArtifactRef | None.
- strict/frozen/extra-forbid/revalidate-always; artifact non-null только MISSING_SOURCE_HOLD, остальные None.
- application/publication/errors.py::PreparationAuthorityError(fault: PreparationAuthorityFault), cause сохраняется. Этот internal carrier не добавляет business terminal category.

Exact grant identity/lifetime/scope mismatch → INVALID_GRANT. Target lease/request/world mismatch → TARGET_MISMATCH. Pin/execution closed → ORIGIN_CLOSED; superseded operation fence → STALE_ORIGIN; отсутствующий actual hold → MISSING_SOURCE_HOLD. Несоответствие acquired origin coverage → COVERAGE_MISMATCH. Different registered origin/value → IMMUTABLE_BINDING_CONFLICT.

Source semantic rejection при collection/proof verification сохраняется **SourceFailure**, не переводится в authority code. Для issuer/register, где объявлен success-only return, internal SourcePreparationAuthorityAbort(failure: SourceFailure) в application/publication/service/preparationAuthorityErrors.py переносит его за borrowed scope; orchestration возвращает исходный failure только после confirmed rollback. Это application exception, без нового error DTO/enum. Ошибка на одном proof откатывает предыдущие acquisitions того же outer scope.

Corrupt checksum/ledger/holder chain → PublicationInfrastructureError. Busy → existing OperationBusyError. Unknown source/target commit → UnknownCommitOutcome, никакого grant/READY success. Cancellation — existing transaction acknowledgement semantics. Store.read None единственный nullable outcome; resolve никогда не возвращает None.

## 8. Приёмка и границы готовности

Предъявлены write/read signatures, fields, issuer trust boundary, two origin paths, storage binding, transaction/lifetime/error semantics. Предложение готово к **контрактному review**, не считается принятым или реализованным. Нужны review canonical registration/SQL layout в existing ledger и доказательство реализации internal acquisition admission; это конкретные задачи Snapshot, не ожидание другого владельца Publication.

Обязательные negative traces: fake grant или grant другого issuer/task/database; generic transaction с чужим UID без admission; pin manifest без child retention; proof не покрытый manifest; mixed source operations; stale fence; same identity/different origins; missing registration; empty proof; source commit unknown; pin close/GC между issuance и adoption; rollback после последнего acquire; restart PREPARING и READY с уже закрытым origin. Two SQLite connections проверяют atomic visibility и exact holds. Все Source internal calls проходят accepted source semantics, без public cross-domain pipeline.

Код не менялся, runtime/typing/tests не запускались. Статически прочитаны operationRows, ExecutionPins, ManifestPinRead, Source finalizer/adopt contracts. git diff --check — только документационная проверка. Старый PARTIAL с предложением искать внешнего владельца заменён этим proposal.

## 9. Уточнение после Source review: sequential scoped trace

Приоритет этого раздела выше общих формулировок issuer/collector. **Accepted:** Source adopt §12.1 получает unbound artifact helper, сам делает один bind(scope), collect/check/acquire и освобождает binding на выходе; scope/outer transaction принадлежит caller. **Не accepted:** логический subset requested proof относительно набора stored proofs; отдельный предварительный collect, затем adopt с новым последовательным bind той же outer transaction. Эти расширения нельзя вывести из существующей signature adopt.

### Concrete caller и источник pin/manifest

Владелец единственной outer transaction — Snapshot-owned `PackPreparationRetention.adopt_and_finish`, backend/app/application/publication/service/packPreparationRetention.py (proposed internal entry из owning retention response). Его вызывает Pack internal implementation одной публичной prepare, не отдельный публичный pipeline. Это локальная атомарная storage операция; никакого решения, какую доменную операцию запустить дальше, внутри нет.

Origin pin берётся из checked persisted acquisition context или issuer admission предыдущего реального pin acquisition. Caller-provided ManifestPinRead без persisted equality недостаточен. `ExecutionPins.require_open_manifest(scope.read_scope, pin)` — proposed extension, проверяющий existing authenticated namespace/intent/OPEN/holder/world в этом же scope, **без** _scopes.bind, hold_open или своего UOW. Для этого backend использует explicit scoped catalog/holder reads; вызов существующего helper, который требует ambient bind, нельзя замаскировать тем же именем метода.

Pack-owned `PackPreparationManifestReader` в backend/app/application/worldData/pack/read/preparationManifestReader.py — proposed internal read binding:

```python
async def read_source_proofs(
    self, scope: CommitReadScope, pin: ManifestPinRead,
    manifest: ArtifactRef,
) -> tuple[SourceDurableProof, ...]: ...
```

Он требует exact authenticated pin→manifest equality, sealed descriptor, bounded verified bytes и owning strict manifest decode. Извлекает **все** provenance proofs из конечного manifest по Pack-owned fields; не вычисляет Source coverage и не выбирает proof по artifact overlap. Данные не берутся из unverified Cache. Output — existing SourceDurableProof tuple; Pack DTO/manifest не передаётся в Source. Reader не открывает UOW/не bind-ит artifact helper/не acquires holds. Source не читает Pack payload. Точная Pack field enumeration должна быть проверена владельцем Pack при review этого internal reader, не придумана в Source.

### Две конкретные Source dependencies — пока proposal

Минимальная форма запроса владельцу Source (окончательные имена/файлы назначает Source, это не утверждение existing API):

```python
# Pure Source-only proof semantics, без scope/IO/Pack DTO.
def check_coverage(
    input: SourceProofCoverageCheckInput,
) -> None | SourceFailure: ...

# Internal read-only preflight, не public READ pipeline.
async def collect_for_adoption(
    scope: CommitScope, request: SourceProofReadInput,
) -> SourceProofResult | SourceFailure: ...
```

check_coverage должен проверить logical selection/capture/dependency coverage, world и допустимое объединение proofs, а не set(durable_refs). Точный набор Source logic codes выбирает Source без зеркального Snapshot enum. collect_for_adoption получает unbound helper, делает ровно один собственный bind, использует Source collector и закрывает bind до возврата; не acquire/release и не commit. Отдельное согласование Source должно разрешить **последовательный** preflight bind→unbind→existing adopt bind→unbind на одной writer transaction. Пока его нет, trace ниже **не implementation-ready**. Snapshot не обходит запрет, не использует private collector и не передаёт уже bound helper в adopt. Если Source выберет иной single-bind seam, сначала совместно заменить эту зависимость/trace, а не добавлять скрытый callback.

Синхронизация S1 после Source/Pack review: exact internal named BaseModel `app.application.worldData.sourceVersioning.proof.coverageCheckInput.SourceProofCoverageCheckInput(request: SourceProofReadInput, available: tuple[SourceDurableProof, ...])`, frozen/strict/extra-forbid/revalidate-always. Он является реальным ModelIdentity root typed diagnostics, не public DTO, receipt или persisted proof. Двухаргументная signature выше по истории отозвана; никакого synthetic argument root. Snapshot создаёт этот проверенный input, не копирует поля Source proof. Proposed SourceOperation.CHECK_COVERAGE остаётся Source-owned roster change, не принят автоматически.

Подтверждённое Pack consumer mapping: reader извлекает ВСЕ manifest.parts[*].provenance.source_proof и manifest.assembly_provenance[*].provenance.source_proof, включая header/tile/chunk/location/settlement/region. Missing/duplicate/orphan provenance row — owning Pack admission refusal; не available=(). Повтор одного proof между валидными строками допустим. Не фильтровать по changed/current capture, не извлекать только B из mixed A/B, не строить proof из planning/capture/ref. Reader возвращает original proofs без union/normalization. Это уточнение предложения reader, не runtime evidence.

### Один полный порядок checks → adopt → READY

1. PackPreparationRetention открывает writer UOW для target; artifact helper unbound. Проверяет exact target/fingerprint/phase, immutable registration и исходные grants. READY replay выполняется отдельно до origin checks; закрытый старый pin не отменяет уже READY.
2. Explicit scoped ExecutionPins проверяет pin/context; PackPreparationManifestReader читает verified exact manifest и возвращает Source proof tuple. **Ни один не bind-ит artifact helper.** Общий writer/GC guard защищает прочитанные удержания от конкурентного close/release.
3. Source pure check_coverage проверяет логическое покрытие. Refused → rollback outer scope, без registration/adopt/READY.
4. Proposed Source collect_for_adoption делает preflight bind/collect/unbind. Возвращённые full durable_refs используются issuer для выбора **заранее допущенных origins**: root manifest PinHolder либо child ArtifactRetentionHolder(manifest), либо operation origin checked acquisition. Missing/extra origins не ремонтируются поиском чужого holder. Sequential rebind требует вышеуказанной Source приёмки.
5. register_sources валидирует exact grants/coverage и append provenance; resolve_sources проверяет persisted identities и actual holds explicit scoped reads. Оба helper **не bind-ят**; source collector повторно не вызывают. Full required refs уже получены шагом 4; provider использует checked scope-local evidence, не caller arbitrary tuple. При restart PREPARING шаг 4 выполняется снова и сверяется с persisted entries; signature resolve(scope,target,request) не выдаёт неподтверждённую полноту по одному mapping.
6. Только с helper unbound вызывается existing Source adopt(scope, request, sources, OperationHolder(target)). **Source единственный bind owner этого вызова.** Он заново collect/check/acquire по принятому контракту; повторная проверка не заменяется preflight evidence. После возврата helper снова unbound. Для нескольких proofs шаги 2–6 идут последовательно; failure любого отменяет предыдущие target acquisitions.
7. После всех adopts registry pending candidate → finish READY вместе с candidate bytes/checksum → outer COMMIT. Ни collector, reader, provider, store, ни Source adopt не завершает transaction. READY schema не меняется.

Внешние SourceFailure проходят SourcePreparationAuthorityAbort с исходным failure через outer rollback; только затем caller видит SourceFailure. Pin refusal сохраняет owning ManifestReadRefusal в internal carrier, не перекодируется в Source coverage failure. Authority errors — existing proposed PreparationAuthorityError; corrupt persisted state/IO — PublicationInfrastructureError; unknown rollback/commit — UnknownCommitOutcome. Cancelled invocation не означает release/terminal cancel. Grant validity и bind cleanup проверяются на любом выходе; ошибка последнего bind/acquire не оставляет частичных holds.

Этот trace — конкретный proposal, а не доказательство, что Source/Pack extensions приняты. Остались точные межвладельческие review decisions: Source pure coverage + sequential preflight seam; Pack verified reader field enumeration; Snapshot internal explicit-scope pin/provider implementation. Ответственность за доведение общего trace остаётся у Snapshot. Runtime tests не запускались.

## 10. Snapshot review PACK-S1/S2 — 2026-11-14

**Статический вывод:** S1 с named input совместим с Snapshot consumer; S2 sequential lexical binds технически совместим с SqliteArtifactScope.bind/reset. Это не joint acceptance. Изменения accepted Source spec или finalizer не выполнены.

**Private scope-local evidence:** владелец PackPreparationSourceAuthority сохраняет успешный preflight в private request-local map на время одного adopt_and_finish. Ключ: exact registered outer CommitScope object identity, target OperationLeaseRef целиком, exact canonical request value. Record хранит immutable SourceProofResult, task identity и общий registry/database/connection identity. Перед register/resolve registry.check(scope, write=True) и operation_id(scope)==target.operation_id обязательны; target/request/world проверяются заново. Scope object не переиспользуется для новой transaction; после revoke запись непригодна даже при том же operation_id. Map очищается в finally при commit/rollback/cancel/unknown. Никакой public token, cache entry, persisted result или raw tuple не принимается вместо этой записи. Это proposed private механизм, не уже имеющееся поле CommitScope.

**Explicit readers:** proposed require_open_manifest и PackPreparationManifestReader используют переданный scope.read_scope, ScopedSqliteAccess/registry checks и verified immutable blob backend. Не вызывают SqliteArtifactScope.read_scope/transaction/guard, ExecutionPins.hold_open либо public holders()/is_held(), если те открывают own UOW при unbound helper. Нужные scoped adapter reads должны быть явными в реализации; существующие public helpers не объявлены подходящими по совпадению назначения. Rebinding Source остаётся только у двух Source вызовов S2/adopt; outer coordinator не держит ambient artifact binding.

**Guard:** SqlitePublicationCommitStore.transaction использует BEGIN IMMEDIATE через SqliteTransactionDriver; эта writer transaction удерживается непрерывно от origin checks/verified manifest IO до всех adopts/READY/COMMIT. Existing artifact guard тоже сериализуется через writer coordinator, однако отдельный guard внутри этого scope запрещён. При same SQLite DB WAL другой writer/GC/pin-close должен дождаться или получить busy; все удаления physical blobs обязаны оставаться под existing shared GC guard. Для другого backend/database или удаления вне этого протокола гарантия не заявляется. Bind/reset не освобождает SQLite transaction lock. Это статическое основание, two-connection runtime evidence пока отсутствует.

**Rollback/restart:** register append и все earlier target acquisitions остаются provisional в outer transaction, late Source/Pack/authority failure выходит за transaction через owning carrier. Refusal после confirmed rollback; unknown не превращается в отказ. Cleanup Source bind — finally; cleanup private evidence — caller finally. При PREPARING restart создаётся новый read/preflight evidence, persisted origins revalidated; grants не возрождаются. При READY сначала exact candidate replay+target holds, без требования живого старого origin. Собственное изменение holds после preflight не скрывается: accepted adopt проверяет их повторно.

**Незакрытое отдельно:** S1/S2 не создают trusted acquisition admission и не подключают issuer к SourceCaptureFinalizer. Terminal replay finalizer не выдаёт такого права. Proposed admission/commit acknowledgement должны пройти отдельный Source review при изменении finalizer hookup; это ответственность Snapshot, а не свойство принятого collector. До этого operation-origin grant path не считается реализованным/принятым. Для scoped seam review findings выше конкретны и не требуют authored Terrain writer/bootstrap, которые остаются отдельной задачей.

## 11. S2-TRACE-1: exact scoped read declarations и nested calls

2026-11-14. Адресное закрытие конкретности proposal; не accepted API и не код. Scope только S2 read dependencies. Origin issuer/finalizer hookup, authored writer, public CRUD/DAG не расширяются. Все пути относительно backend/app/.

### Internal adapter ports

Предлагаемый `IScopedArtifactRead` в application/artifacts/contracts/scopedArtifactRead.py:

```python
async def read_scoped(
    self, scope: CommitReadScope, ref: ArtifactRef,
) -> ArtifactRef | None: ...

async def descriptor_scoped(
    self, scope: CommitReadScope, artifact_id: EntityUid,
) -> ArtifactRef | None: ...

async def storage_state_scoped(
    self, scope: CommitReadScope, ref: ArtifactRef,
) -> ArtifactStorageEventKind | None: ...
```

Concrete adapter — existing SqliteArtifactCatalog в db/repositories/sqlite/artifacts/catalogStore.py, с этими **новыми internal methods**. read_scoped: strict ref → registry.check(scope) → _find(scope,ref) → _descriptor(row), без public read(). descriptor_scoped: strict artifact_id → registry.check → ScopedSqliteAccess.one_row(ArtifactCatalogRow by id) → _descriptor; None только absent row. storage_state_scoped: registry.check → _find → _storage → existing enum kind. None означает отсутствующий catalog/storage факт, не sealed; DELETED остаётся явным existing enum. Corrupt descriptor/storage chain → PublicationInfrastructureError. Для уже validated descriptor при совпадающем identity key и несовпадении полного descriptor proposed read_scoped явно выдаёт PublicationInfrastructureError из проверки equality; не ловить любой ValueError по тексту. Public catalog methods остаются вне этого пути.

Предлагаемый `IScopedArtifactHolderRead` в application/artifacts/contracts/scopedArtifactHolderRead.py:

```python
async def holders_scoped(
    self, scope: CommitReadScope, ref: ArtifactRef,
) -> tuple[ArtifactHolderRef, ...]: ...
```

Concrete — existing SqliteArtifactHolders в db/repositories/sqlite/artifacts/holderStore.py, новый internal method. Strict ref → registry.check(scope) → own _holders(scope,ref). Private _holders остаётся implementation detail владельца, не cross-class port. _holders → catalog._find → holder _chain → _hydrate; operation hydration читает operation через same explicit scope, snapshot hydration — history.resolve_ref(scope=scope), artifact hydration — catalog._by_id(scope,...). Все обращения through ScopedSqliteAccess, без public holders/is_held/read и без `_scopes.read_scope()`. Absent catalog → (); invalid persisted holder chain/owner → PublicationInfrastructureError. () не доказывает права и означает missing hold для вызывающего issuer/provider. Отдельный scoped is_held не нужен: equality проверяется над этим tuple.

Предлагаемый `IScopedOperationRead` в application/publication/contracts/scopedOperationRead.py:

```python
async def read_scoped(
    self, scope: CommitReadScope, operation_id: EntityUid,
) -> OperationRecord | None: ...
```

Concrete — SqliteOperationStore в db/repositories/sqlite/snapshotCore/operations/operationStore.py. Strict UID → registry.check → own _load(operation_id,scope). _load/event/outcome/evidence/artifact-reader используют тот же scope, не public read(). None — отсутствующая operation; damaged row/event/terminal evidence — PublicationInfrastructureError. Проверка current lease/fence/kind/phase выполняется provider над прочитанным existing OperationRecord, не посредством catalog._lease с private чужим доступом. Нового lifecycle state POJO нет.

Указанные methods read-only, не bind/guard/UOW и не acquisition. Invalid/foreign/cross-task/revoked scope отвергается registry до SQL. Registered coordinator/access identity одна для всех adapters. Backend SQL busy/IO обрабатывается существующей infrastructure boundary, не преобразуется в successful None. Strict malformed argument не записывает diagnostics/terminal. Ни один caller не получает raw row/connection.

### Exact pin read nested trace

IPinnedManifestAuthority.require_open_manifest(scope: CommitReadScope, pin: ManifestPinRead) -> ArtifactRef (proposed §4) реализует ExecutionPins:

1. strict pin, registry.check(scope), authenticated binding `_owner` и existing `_binding` identity/OPEN checks, передавая **этот scope**; `_binding` читает `_closed(scope,owner)` и pack_execution_pins через ScopedSqliteAccess. Никаких acquire/held_manifest/hold_open/_checkpoint или нового execution-store read внутри transaction. Existing отсутствие authenticated store binding остаётся refusal, не offline fabrication.
2. IScopedArtifactRead.descriptor_scoped(scope,row.manifest_artifact_id); None при existing pin reference — corrupt persisted pin (infrastructure).
3. storage_state_scoped(scope,ref) требует SEALED; holders_scoped(scope,ref) требует exact PinHolder(pin_id). Missing live hold/unsealed/closed pin — existing owning Pack pin refusal, не Source failure. Valid ref возвращается без bytes read; повторные шаги reader ниже не создают guard.

Physical byte verification принадлежит PackPreparationManifestReader, не require_open_manifest: эта более точная граница заменяет прежнюю общую формулировку §4 про bytes в pin port.

### Exact manifest-reader nested trace

PackPreparationManifestReader.read_source_proofs(scope,pin,manifest): require_open_manifest(scope,pin) → full ref equality manifest → registered ArtifactFormatRegistryBinding.validate(manifest) → registered ReadableBlobBackend.read_verified(manifest,max_bytes=pin.max_bytes) → owning strict Pack decoder/admission → извлечение всех parts/assembly proofs §9. Backend read_verified — immutable physical read/digest check, не catalog.guard; composition должна подтвердить именно такой backend. Если existing backend требует own guard, его нельзя подключить этому scoped reader без отдельной правки контракта.

Reader не вызывает Source, Cache public API, public Pack read pipeline или bind. Pin/manifest refusal переносится owning internal carrier с исходным ManifestReadRefusal; corruption/IO сохраняет infrastructure. Missing/duplicate/orphan provenance — Pack admission refusal, не tuple(). Lifetime bytes read защищён outer writer/GC lock; registry проверяется до и после awaited physical IO. Canonical proofs возвращаются без union/normalization.

### Register/resolve exact nested trace

PackPreparationSourceAuthority.register_sources(scope,target,request,grants): registry.check(scope,write=True)/operation_id equality → IScopedOperationRead.read_scoped(scope.read_scope,target.operation_id) → exact target check → private preflight evidence check §10 → validate exact issued grants → проверить recorded origins следующими **scoped** reads → IPreparationAuthorityStore.append(scope,binding). Для operation origin: IScopedOperationRead.read_scoped(source operation) и exact lease/fence → IScopedArtifactRead.storage_state_scoped каждого required ref → IScopedArtifactHolderRead.holders_scoped и equality OperationHolder(source lease). Для pinned origin: require_open_manifest(scope.read_scope,pin), exact manifest equality → state/holders_scoped каждого required ref, root PinHolder либо child ArtifactRetentionHolder(manifest). Никакого Source collector/manifest reread внутри register: logical coverage и complete refs уже в exact checked preflight evidence. Immutable append — existing proposed ledger port, без own UOW.

resolve_sources(scope,target,request): тот же scope/target guard → IPreparationAuthorityStore.read(scope.read_scope,target,request) → missing registration fault → check private preflight evidence exact proof/full required refs → тот же scoped origin/state/holder path → existing VerifiedArtifactRef tuple. Store.read не использует public operation.read и не открывает scope. After restart preflight выполняется заново до resolve; persisted row не подменяет current origin checks. Neither method calls Source adopt, bind/guard, holders()/is_held() или holder acquire. Source adopt вызывается outer owner только после успешного возврата, с unbound helper.

### Feasibility, errors и evidence

Existing private primitives _find/_storage/_holders/_load уже принимают explicit scope, но **новые ports выше предложены явно**, а не объявлены существующими. При реализации нужно проверить всё дерево _hydrate/_evidence и storage backend на отсутствие ambient transaction; описание не заменяет этот тест. S2 preflight и adopt остаются единственными lexical artifact bind owners в соответствующих шагах; caller writer transaction BEGIN IMMEDIATE непрерывна через readers/register/resolve/physical IO. Scope reset не снимает lock; другого guard не открывается.

Недействительный scope/повреждённый ledger — infrastructure; missing/expired origin — PreparationAuthorityError по §7; Pack manifest/pin refusal сохраняет свой typed reason; SourceFailure только из S1/S2/adopt. Любой failure после register/предыдущего acquire проходит outer rollback; unknown/cancel согласно §9–10. Explicit read ports не создают новый recovery outcome.

Проверены исходники artifactScope, catalogStore, holderStore, operationStore и scopeRegistry. Runtime/typing/tests не запускались, код не менялся. S2-TRACE-1 предъявлен на повторный совместный review; этот документ не объявляет ACCEPTED и не закрывает acquisition admission/finalizer hookup.

## 12. S12-PACK-ERR-1: exact read refusal transport

Принимается как совместный **proposal** уточнение Pack: existing ManifestReadRefusal из dataModel/worldPack/read/pinnedManifest.py не оборачивается новым dataModel reason/code. Актуальные signatures:

```python
# IPinnedManifestAuthority / ExecutionPins internal extension
async def require_open_manifest(
    self, scope: CommitReadScope, pin: ManifestPinRead,
) -> ArtifactRef | ManifestReadRefusal: ...

# PackPreparationManifestReader
async def read_source_proofs(
    self, scope: CommitReadScope, pin: ManifestPinRead, manifest: ArtifactRef,
) -> tuple[SourceDurableProof, ...] | ManifestReadRefusal: ...
```

Pack reader при refusal от require_open_manifest возвращает **тот же** immutable ManifestReadRefusal немедленно, без byte read/decode и без собственного rollback. Provider/issuer helper, который вызывает require_open_manifest глубже outer caller, обязан явно проверить union и поднять нижеуказанный carrier, а не принять refusal за ArtifactRef. Infrastructure/invalid scope/unknown продолжают выходить своим исключением; union не является catch-all для storage faults.

Один Snapshot-owned internal exception в backend/app/application/publication/service/preparationAuthorityErrors.py (рядом с existing proposed SourcePreparationAuthorityAbort):

```python
class PackPreparationReadAbort(Exception):
    refusal: ManifestReadRefusal
    def __init__(self, refusal: ManifestReadRefusal) -> None: ...
```

Constructor принимает strict-revalidated existing ManifestReadRefusal, сохраняет его в refusal без перекодирования pin_id/ref/reason. Никакого нового DTO/enum или public exception API. Только ошибки чтения pin/manifest этого scoped пути, не SourceFailure и не unknown. SourcePreparationAuthorityAbort остаётся отдельным carrier для existing SourceFailure.

**Raise boundary:** PackPreparationRetention.adopt_and_finish проверяет результат read_source_proofs внутри target writer scope; ManifestReadRefusal → raise PackPreparationReadAbort(result) немедленно. При глубоком вызове pin port из origin checks тот же carrier поднимает PackPreparationSourceAuthority/PreparationAuthorityIssuer в этой же transaction; все остальные уровни его только пропускают.

**Catch boundary:** тот же PackPreparationRetention ловит PackPreparationReadAbort **снаружи** async with publication_commits.transaction(target.operation_id), после подтверждённого rollback и revoke. Никакого catch-and-commit внутри scope. Его internal результат для preparation consumer расширяется до `OperationRecord | SourceFailure | ManifestReadRefusal`: возвращает error.refusal, а не READY. Pack public operation дальше использует собственный принятый public error mapping; этот union не становится новым public DTO.

Если rollback выдаёт UnknownCommitOutcome, carrier не ловится как подтверждённый отказ: наружу выходит UnknownCommitOutcome с cause, не ManifestReadRefusal. Cancellation/cleanup неопределённость сохраняет owning semantics. Это особенно необходимо для нескольких proofs: pin refusal второго proof откатывает provisional provenance и target acquisitions первого. На пути без writes требуется тот же boundary, чтобы caller не различал ложные «частично успешно» варианты.

Внешний contract signature adopt_and_finish из прежнего retention response (`OperationRecord | SourceFailure`) требует этой явной proposed корректировки; принимать новый read union без неё нельзя. Source S1/S2/adopt signatures, order и ошибки не меняются. После синхронизации единой редакции повторно проверить этот finding; runtime evidence отсутствует.
