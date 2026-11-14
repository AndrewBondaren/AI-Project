# C-PIN-1: pinned-origin — редакция 1 для совместной проверки

2026-11-14. **PROPOSED FOR JOINT REVIEW. Не ACCEPTED, не IMPLEMENTED.** Owner — Snapshot (`application/publication` и Artifacts); Pack подтверждает authenticated pin/manifest boundary, Source — неизменность S1/S2. Основание разрешённого scope: `source-pack-s1-s2-implementation.md`, C-PIN-1, «разрешённый следующий срез». Эта редакция конкретизирует только pinned часть `pack-preparation-source-authority-contract.md`, не принимает весь прежний proposal.

## 1. Scope и состояние до дельты

Принятый design: S1/S2 r2 — scoped readers, verified all-provenance extraction, coverage, fresh preflight, private evidence, register/resolve trace, unchanged adopt, один outer writer, refusal после rollback, READY replay до origin reads. Реализованы только базовые pin/operation/artifact/transaction primitives. Новые scoped ports, Source base/runtime, issuer/provider/store/atomic Pack retention ещё не реализованы.

Дельта этой редакции: точный pinned issuer и доверенный caller; односкоупный runtime grant; pinned durable binding и immutable append/read; retry из повторно предъявленного исходного input после confirmed rollback. Отдельный Source operation acquisition, G4, finalizer hookup, промежуточный PREPARING commit, public Pack prepare/DAG routing и автоматическое восстановление caller input после process crash не добавляются.

R1–R3 сверены по текущему коду и `snapshot-retention-cancel-diagnostics-contract.md`: native section states/history retention относится к Snapshot metadata, не заменяет Source closure или manifest child links. `OperationBindingMismatch` относится к claim identity, `SnapshotApplyRelationIssue` — apply diagnostics, `SnapshotOperationCancelledError` — apply terminal cancellation. Не используем их как grant/Pack errors, не меняем их форматы. Старых flat receipt fields и legacy decoder этот срез не требует.

## 2. Вход первого вызова и повтор после rollback

Internal caller — `PackPreparationRetention.adopt_and_finish` в рамках той же атомарной preparation. Для каждого proof ему переданы existing `OperationLeaseRef target`, `SourceProofReadInput request`, `ManifestPinRead pin`. Нет публичного grant, нового DAG token или нового зеркального input DTO. Manifest выбирается только по persisted binding именно этого pin; pin не выбирается поиском подходящего holder. Эти аргументы сами по себе ещё не authority.

`ManifestPinRead` из `dataModel/worldPack/read/pinnedManifest.py` содержит store_id, execution_id, invocation_id, logical_read_key, pin_id, world_uid, max_bytes. `ExecutionPins._binding` сверяет первые шесть полей с authenticated namespace и persisted OPEN binding, проверяет CLOSED/live store. Результирующий manifest — ранее закреплённый `manifest_artifact_id`, не текущая публикация. max_bytes — полный повторно предъявляемый read budget; он не содержится в pin row и не удостоверяет authority. Row содержит publication_id, но эта редакция не добавляет проверку полной `WorldPublicationRef`, которой нет во входе.

**Retry после confirmed rollback:** тот же владелец повторяет internal вызов с сохранёнными исходными target/request/pin. Его сохранённые данные — только input; всё authority/evidence проверяется заново. Можно переиспользовать прежний валидный pin независимо от object identity десериализованного POJO; нельзя переиспользовать grant. Предъявление другого input не является восстановлением прежней попытки. Checked preparation binding и current lease проверяются owning target boundary; этот срез не разрешает takeover/fence replacement или смену preparation fingerprint.

**Граница crash recovery:** после потери caller input имеющиеся publication rows с fingerprints и pin row не восстанавливают exact request/target/max_bytes. Rolled-back registration отсутствует. В этой редакции нет persisted producer этих входов, поэтому автоматический restart «только по operation_id/checkpoint» остаётся OPEN dependency владельца вызывающего Pack/recovery контракта. Для restart-теста caller обязан заново предоставить исходные полные values из подтверждённого owning источника; тест сохранения/десериализации input не доказывает production recovery wiring. Новый DAG checkpoint schema, input journal или дополнительный commit здесь не проектируется. Это ограничение не скрывается под словом retry и не закрывает весь C-PIN-1 crash scenario.

Повтор ни при каких условиях не вызывает `ExecutionPins.acquire`: при missing row existing acquire прочитал бы latest head. Missing/closed/foreign binding даёт отказ. Ни caller, ни issuer не создают/переоткрывают pin и не создают child holds.

**Подтверждение Pack 2026-11-14:** `ExecutionPins.bind` связывает adapter с реальным `store.get_store_id`/persisted namespace; `_owner/_binding` подтверждают полную identity/OPEN/not CLOSED/live store. Для этого trusted internal composition дополнительный upstream token из существующего read contract не следует. Exact повторный ManifestPinRead остаётся проверяемым INPUT, не capability. Pack подтвердил допустимость узкого explicit repeat invocation, в том числе после reopen, если caller предъявляет исходный полный input; accepted durable producer для автономной реконструкции не предъявлен. Это подтверждение boundary, не общий review/PASS данной редакции.

## 3. Классы и контракты

Все code paths ниже относительно `backend/app/`. Методы — internal, не public pipeline. Public CRUD данных и настроек не меняются (C/R/U/D для обоих вне дельты); отдельная public/DAG приёмка сохраняется.

| Класс / файл | Ответственность, dependencies, effects | Критерий отказа в приёмке |
|---|---|---|
| `PreparationAuthorityIssuer`, `application/publication/service/preparationAuthorityIssuer.py` | Только `issue_pinned_manifest`; читает registry private evidence и scoped pin/catalog/holders, создаёт runtime grant | Принимает caller sources/сырой grant, собирает proof, acquires hold, открывает UOW или вызывает public pipeline |
| `PreparationAuthorityGrant`, `application/publication/contracts/preparationAuthority.py` | Непублично конструируемый opaque runtime object; authority по registry exact identity | Сериализуемый DTO/UID token, constructor доступен consumer, reuse после revoke или cross-scope |
| `PackPreparationSourceAuthority`, `application/publication/service/packPreparationSourceAuthority.py` | register/resolve, target+evidence+origin checks, store append/read | Ищет произвольные holders, вызывает collect/adopt или сам коммитит |
| `IPreparationAuthorityStore`, `application/publication/contracts/preparationAuthorityStore.py`; `SqlitePreparationAuthorityStore`, `db/repositories/sqlite/snapshotCore/operations/preparationAuthorityStore.py` | Immutable canonical origin binding в operation preparation ledger, explicit scope; не выдаёт authority | Append через public caller, own UOW, hash-only equality, изменение origin существующего binding |
| `ExecutionPins`, `db/repositories/sqlite/worldPack/executionPins.py`; `IPinnedManifestAuthority`, `application/publication/contracts/pinnedManifestAuthority.py` | Existing authenticated pin primitives; proposed `require_open_manifest` на borrowed read facet | acquire/latest/reopen, использование own `hold_open` transaction, OPEN при отключённом store |
| `PackPreparationManifestReader`, `application/worldData/pack/read/preparationManifestReader.py` | Pack-owned verified bytes/decode/all proofs, scoped pin check, bounded backend read | Unverified Cache, фильтр только changed parts, создание нового proof, own UOW |
| `SourceProofSelector`, `application/worldData/sourceVersioning/proof/selector.py`; `SourceCaptureRetentionBinding`, `application/worldData/sourceVersioning/capture/retentionBinding.py` | Принятые S1 pure coverage и S2 preflight/adopt; input/output неизменны | Authority issuance из результата collector, preflight acquire, nested lexical binding |
| `PackPreparationRetention`, `application/publication/service/packPreparationRetention.py` | Outer writer/READY replay/последовательные scoped stages/commit и rollback boundary | Catch-and-commit refusal, промежуточный commit registration, скрытая оркестрация самостоятельных public операций |

Scoped artifact/holder/operation reader interfaces и concrete SQLite adapters остаются ровно S1/S2 r2 §4. Registry принадлежит Snapshot atomic owner, связан с exact outer scope object, task/database/connection/coordinator. Нельзя выдавать issuer произвольному public reader через DI; его instance допускается только owning composition. Проверки защищают trusted application boundary, не произвольного SQL writer в том же процессе.

```python
async def issue_pinned_manifest(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput, pin: ManifestPinRead,
) -> PreparationAuthorityGrant: ...

async def register_sources(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput, grants: tuple[PreparationAuthorityGrant, ...],
) -> None: ...

async def resolve_sources(
    self, scope: CommitScope, target: OperationLeaseRef,
    request: SourceProofReadInput,
) -> tuple[VerifiedArtifactRef, ...]: ...

async def append(self, scope: CommitScope, binding: PreparationSourceBinding) -> None: ...
async def read(
    self, scope: CommitReadScope, target: OperationLeaseRef,
    request: SourceProofReadInput,
) -> PreparationSourceBinding | None: ...
```

### Private evidence и lifetime

Успешный manifest read сохраняется в private registry owner: exact scope, target, canonical request, full pin, resolved manifest и immutable available proofs. Успешные S1 и S2 дополняют ту же запись exact coverage result и immutable `SourceProofResult`. Запись создаётся только owner после возвратов настоящих dependencies, не caller-set tuple/flag. Это конкретизация private evidence S1/S2, не public `SourceProofResult` extension.

Issuer требует эту полную запись, заново проверяет current pin/manifest и actual source holds и выдаёт grant, связанный с exact issuer instance, task/DB/connection/scope object, full target/request/pin/manifest и sources. Scoped issuance не переносится между transactions. Register получает grant только этого registry, повторно проверяет holds. Repeated register с тем же valid grant и exact binding допустим как idempotent no-op; иной binding — конфликт. Grant не является consumable durable result.

Owner в `finally` отзывает все grants/private evidence на commit, rollback, cancellation и unknown, включая ошибки до первого SQL write. Отмена/исключение между issuance и registration не оставляет переносимый grant. Новый вызов даже с тем же target создаёт новый scope/evidence/grant. «Committed grant», commit acknowledgement для source operation и resurrection здесь отсутствуют.

### Durable record и отсутствие дублей

Proposed module `dataModel/publication/preparationSourceAuthority.py` содержит один roster из исходного proposal; эта редакция принимает к рассмотрению только pinned variant:

- `PreparationSourceOriginKind.PINNED_MANIFEST = "pinned_manifest"`.
- `PinnedManifestSourceOrigin`: обязательные `kind: Literal[PreparationSourceOriginKind.PINNED_MANIFEST]`, `pin: ManifestPinRead`, `manifest: ArtifactRef`.
- `PreparationSourceEntry`: обязательные `source: VerifiedArtifactRef`, `origin: PinnedManifestSourceOrigin` (operation variant не включать в реализацию этого среза).
- `PreparationSourceBinding`: обязательные `target: OperationLeaseRef`, `request: SourceProofReadInput`, `entries: tuple[PreparationSourceEntry, ...]`.

Все четыре record/enum declarations принадлежат Snapshot; records strict/frozen/extra-forbid/revalidate-always, без defaults. Existing `ArtifactRef`, `OperationLeaseRef` (`dataModel/artifacts/lifecycle/lease.py`), `VerifiedArtifactRef` и holders (`dataModel/artifacts/lifecycle/holders.py`) используются без копий. Source owns request/proof types; Pack owns pin. `source` определяет фактический holder, `origin` — проверенный pin/manifest context, они не являются двумя копиями proof. SourceProofResult/private evidence в ledger не сохраняется.

Entries в порядке `SourceProofResult.durable_refs`; каждый full ref ровно один раз. Union refs должен точно совпасть с preflight closure. Для manifest root допустим только `PinHolder(pin.pin_id)`; для любого child — только `ArtifactRetentionHolder(origin.manifest)`. Нельзя создать фиктивный PinHolder(child). Empty Source proof/closure даёт entries=(), sources=(); issuance всё равно проверяет pin/manifest и successful empty coverage/preflight. Несколько grants допустимы только для того же exact request/target; первый по порядку grants покрывающий ref задаёт его origin, duplicate entries не создаются. Эта редакция не вводит mixed operation origins.

Semantic key store: target.operation_id + target.preparation_fingerprint + canonical exact request; full target fence/value проверяется при read и append. Equality — полная canonical record equality после checksum/strict decode, не совпадение digest. Same binding — no-op; другое происхождение/значение в том же key — immutable conflict. Missing binding — None только у store; provider выдаёт AUTHORITY_NOT_REGISTERED. Corrupt bytes/chain/checksum — infrastructure.

Append выполняется в той же target transaction, что adopt и READY. Никакого отдельного commit PREPARING. Atomic commit сохраняет binding и READY/candidate/target holds вместе. Историческая фраза исходного proposal о более раннем committed registration **не применяется к этой pinned-only редакции**. SQL layout и canonical IDs ещё требуют отдельного owning storage/codec review перед реализацией; не назначаем ID поверх добавленных R1–R3 20301/20302/20306/20307 и не создаём новый schema counter или legacy decoder.

## 4. Exact nested trace и неизменность порядка

Источник порядка — S1/S2 r2 §5. Issuance занимает внутреннюю часть существующего шага register/resolve после fresh preflight; не переносится перед S1/S2 и не добавляет public стадию.

1. `PackPreparationRetention.adopt_and_finish`: одна `publication_commits.transaction(target.operation_id)`, current target/phase/fingerprint/fence checks. READY branch читает exact candidate/target holds и возвращает подтверждённый replay без pin reads/issuance/adopt. Не путать execution READY с preparation READY.
2. Для очередного proof: `require_open_manifest(scope.read_scope,pin)` → `ExecutionPins._owner/_binding/_closed` в том же scope → scoped catalog descriptor/storage SEALED → exact root PinHolder. Absent binding — typed refusal, отсутствующий descriptor при существующем binding — corruption. Ни `_checkpoint`, ни `acquire/hold_open` не вызываются. Pack reader повторно проверяет pin/full manifest equality → registered format validation → bounded `ManifestBlobBackend.read_verified` → strict decode/world/provenance admission → все parts и assembly proofs.
3. `SourceProofSelector.check_coverage(SourceProofCoverageCheckInput(request=request, available=available))`. Затем `SourceCaptureRetentionBinding.collect_for_adoption`: lexical bind → collector → finally reset. Все independent diagnostics сохраняют accepted order и typed paths. При failure зависимая issuance не выполняется.
4. Owner сохраняет successful private evidence. `issue_pinned_manifest`: scope/target/evidence guards → scoped pin current equality → scoped storage/holders каждого required ref → grant. Не читает/декодирует manifest заново, не вызывает collector: exact prior evidence содержит его проверенный результат. Ни отсутствие evidence, ни сырые durable refs не допускаются.
5. `register_sources`: scope/target → exact registry grants/evidence → повторные scoped pin/storage/holds → store.append. `resolve_sources`: scope/target → store.read → exact evidence/request/full coverage → scoped pin/storage/holds → ordered VerifiedArtifactRef tuple. Ни provider, ни store не bind-ят helper. В первом запуске resolve следует register; на retry после rollback выполняются fresh issue и register, потому что прежней записи нет.
6. Unbound helper → unchanged `adopt(scope,request,sources,OperationHolder(target))`: новый sequential bind/collect/full source and target checks/acquire/finally reset. Следующий proof проходит шаги 2–6; отказ любого откатывает прежние provisional writes.
7. Только outer owner сохраняет candidate/finish READY и COMMIT по принятому Pack lifecycle design. Ни issuer, provider, readers, Source, ни store не коммитят. Успех caller — после confirmed commit.

Catalog/holder/operation nested tree — S1/S2 r2 §4: scoped catalog `_find/_descriptor/_storage`; holders `_holders/_chain/_hydrate`, operation `_load` или history `resolve_ref(scope=...)` или catalog `_by_id`; operation `_event`/artifacts/evidence. Все SQL через `ScopedSqliteAccess` с registry checks. Physical verified read ограничен budget, scope lifetime повторно проверяется после await. Нет nested guard/UOW или ambient bind в readers. Непрерывный BEGIN IMMEDIATE общей SQLite DB сериализует pin close и compliant GC physical deletion; reset Source helper lock не снимает.

## 5. Точные ошибки и caller outcome

Переиспользуются `ManifestReadRefusal(pin_id, ref, reason)` и `ManifestReadReason` из Pack. Missing/foreign pin → INVALID_PIN; CLOSED → CLOSED_PIN; root hold missing → MISSING_HOLD; unsealed → UNSEALED; format/full ref mismatch → IDENTITY_MISMATCH; budget → BUDGET_EXCEEDED; malformed admitted manifest → INVALID_MANIFEST. Corrupt persisted descriptor/ledger не маскируется под input refusal. Pack должен подтвердить mapping scoped implementation; существующий PinnedManifestGuard — evidence текущего mapping, не callable внутри outer writer.

Глубокий issuer/provider поднимает accepted-design `PackPreparationReadAbort(refusal)` внутри scope. SourceFailure проходит `SourcePreparationAuthorityAbort(failure)` без перекодирования. Outer owner ловит carriers только после confirmed rollback/revoke и возвращает тот же SourceFailure/ManifestReadRefusal. Invalid input shapes проходят owning strict validation; не выдаются за отсутствующий origin. Scope/DB/task/lifetime violations — infrastructure до dependent IO.

Authority-only ошибки используют единственный proposed `PreparationAuthorityFault` / `PreparationAuthorityError`, без второго pinned fault DTO. Для pinned-only поставки `dataModel/publication/preparationAuthorityFault.py`:

| Code (StrEnum value) | Причина |
|---|---|
| AUTHORITY_NOT_REGISTERED (`authority_not_registered`) | store.read None при resolve |
| INVALID_GRANT (`invalid_grant`) | Неissued/revoked/cross-scope grant или grant не соответствует exact предъявленным request/target/pin/evidence |
| MISSING_SOURCE_HOLD (`missing_source_hold`) | Child closure ref не удерживается именно ArtifactRetentionHolder(manifest) |
| COVERAGE_MISMATCH (`coverage_mismatch`) | Issued source set/binding не равен exact preflight durable set; не Source logical coverage refusal |
| IMMUTABLE_BINDING_CONFLICT (`immutable_binding_conflict`) | Другой canonical origin/value в existing binding key |

`PreparationAuthorityFault` — strict/frozen/extra-forbid/revalidate-always; все поля обязательны: `operation_id: EntityUid`, `code: PreparationAuthorityCode`, `artifact: ArtifactRef | None`. artifact non-null ровно для MISSING_SOURCE_HOLD. `application/publication/errors.py::PreparationAuthorityError(fault)` strict-revalidates fault и хранит его; exception cause сохраняется. Internal error не становится terminal result и не переводится в SnapshotApplyResult.

Это явное сужение первоначального proposal §7 для pinned-only: ORIGIN_CLOSED не дублирует Pack CLOSED_PIN; STALE_ORIGIN operation branch исключён; TARGET_MISMATCH не дублирует target lifecycle BINDING_MISMATCH/STALE_LEASE. Target existence/kind/world/preparation/fence/phase errors остаются owning `PackLifecycleFault` design из `pack-storage-lifecycle-finalization-response-2026-11-14.md`. Grant mismatch — INVALID_GRANT, Source world/semantic coverage — SourceFailure. Не добавлять пересекающиеся коды при реализации без review.

Независимые проверки одного этапа агрегируются existing `ValidatorAggregationHelper` с exact admitted типами соответствующего owning этапа; field paths только typed selectors. Issuance не продолжает dependent reads после отсутствующего pin/evidence, но не меняет агрегацию Source S1/S2. Этот authority carrier описывает отказ целого dependent admission, не новый список field diagnostics.

Late refusal требует rollback всего writer. `UnknownCommitOutcome` при commit/rollback имеет приоритет над caught refusal; наружу unknown с cause, grant/evidence revoked. После unknown нельзя объявить confirmed rollback или автоматически выдать новый grant: существующий recovery сначала устанавливает durable phase. READY → exact candidate/target replay; подтверждённый неcommitted PREPARING → fresh attempt с полным входом. Неизвестный outcome остаётся неизвестным. Cancellation не создаёт terminal, не освобождает исходные pin/children и не превращается в обычный отказ.

## 6. Обязательные review/tests и границы приёмки

| Проверка | Evidence, требуемое перед runtime acceptance |
|---|---|
| First run / confirmed rollback retry | Настоящие Source finalized fixtures, Pack manifest/pin, issuer и store; повтор с исходным input создаёт новый grant; старый отозван. Второе соединение не видит rolled-back registrations/target holds |
| Missing/closed/foreign pin | Нет вызова acquire/latest; exact owning refusal; нет target writes |
| Fake/cross-task/DB/scope/grant | Отказ до effects; UID/совпадение tuples не удостоверяют grant |
| Coverage/empty/malformed | Все proofs из manifest, extra available allowed, extra requested refused; empty sources ровно (); strict nested DTO и independent Source diagnostics |
| Child/root retention | Root только PinHolder; child только manifest retention; missing child refusal, без acquisition источника issuer-ом |
| Late second-proof refusal | Первый register/adopt rolled back; exact caller refusal только после rollback; два independent SQLite connections |
| Close/GC race | Одна временная SQLite DB, два соединения, реальный guarded close/GC; protection от первого origin read до commit; no sleeps как единственное доказательство порядка |
| READY / unknown / cancel | Old pin closed не мешает valid READY replay; unknown не заменён refusal; evidence cleanup в finally |
| Restart input | Отдельно показать подтверждённого owning producer полного replay input; без него crash-recovery gate OPEN, retained-input retry не переименовывать в доказательство recovery |

Source fixtures — `backend/tests/sourceVersioning/support/finalizedFixtures.py` по G2, без fabricated rows. Pack предложил `backend/tests/worldPack/support/pinnedProvenanceFixtures.py`: новый, ещё не implemented/accepted import; strict manifest/provenance принадлежит Pack, pins/holds создаются реальными Snapshot adapters, captures — Source G2. Snapshot integration location предлагается `backend/tests/snapshotCore/storage/publication/test_pinned_origin.py`; реализация только после prerequisite/fixture/storage acceptance. Старые fixtures не конвертировать и не создавать legacy adapters.

Обязательная matrix плана: три запрета DAG соблюдаются только в этом internal atomic design scope; public междоменный маршрут не заявлен. Роли/deps/effects/отказы — §3; typed POJO/non-overlap — §3,5; порядок — §4 по S1/S2; public/data/settings CRUD границы — §1,3; unresolved external input producer — §2. Поэтому **полная приёмка C-PIN-1 и execution-ready пока невозможны**. Review этой редакции может отдельно принять first-call/retained-input retry contract; это не молчаливое закрытие crash/DDL/codec/runtime gates.

Изменение прохода — этот owning документ. Source implementation-план и runtime-код не изменены. Проверены текущие ExecutionPins/PinnedManifestGuard/ManifestPinRead, publication operation rows, R1–R3 report/types, S1/S2 r2 и исходный authority proposal. Runtime tests не запускались. Новые ноды, restart-протокол, operation-origin G4 и finalizer hookup не проектировались.

## 7. Результаты совместной проверки

2026-11-14, Pack (чат `01a1cfce-ff7d-7e30-b738-f075bf490f13`): **PASS в узком consumer/design scope: first call + explicit retained-input retry после confirmed rollback.** Прочитана вся редакция 1, повторно сверены actual ManifestReadReason/ManifestReadRefusal и PinnedManifestGuard.manifest_guard. Actionable findings по запрошенным Pack границам нет. Подтверждены no acquire/latest, full available proofs/evidence binding, root/child holders, fresh grants, READY-before-origin и unknown precedence.

Nullable refusal context сохраняется как в existing guard: missing/foreign/closed без найденного ref, missing hold/unsealed с exact ref. Редакционное замечание о форме check_coverage учтено в §4.3: явно показан SourceProofCoverageCheckInput, контракт метода не менялся.

Pack PASS не закрывает autonomous input reconstruction, SQL/codec/runtime, G4 или fixture implementation. Pack тесты не запускал.

2026-11-14, Source: [отдельный отчёт](source-review-pinned-origin-r1.md), **PASS по совместимости first-call/explicit retained-input repeat с accepted S1/S2**. Подтверждены issuance после fresh preflight внутри register-stage, отсутствие collector/bind внутри provider, неизменный adopt с полными повторными проверками, exact refs/holds, rollback/unknown/revoke и разделение SourceFailure/authority codes. Новых блокирующих замечаний по Source semantics/order нет. Source runtime tests не запускал. Указанная в отчёте сокращённая запись check_coverage уже уточнена в §4.3 до accepted named input; семантика не менялась.

Актуальный helper для будущей реализации — `backend/app/dataModel/validation/diagnostics/validatorAggregationHelper.py`, как отмечено Source. Исторический `app.core.validatorAggregationHelper` не является основанием создавать compatibility module.

Итог: получены два адресных consumer/design PASS в указанной узкой границе. Это не пользовательская приёмка всей редакции и не закрытие C-PIN-1: полный crash input producer, storage/codec и runtime gates остаются открыты. Статус документа остаётся PROPOSED FOR JOINT REVIEW; код этим итогом не разрешается.
