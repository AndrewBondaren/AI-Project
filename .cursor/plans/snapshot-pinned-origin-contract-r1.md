# C-PIN-1: pinned-origin — исправленная редакция 2 для совместной проверки

**Итог независимого review, 2026-11-14: PASS узкого design first-call/explicit retained-input repeat после confirmed rollback.** [Акт проверки](source-pinned-origin-final-review-2026-11-14.md) и границы — §10. Три findings закрыты на уровне design; SQL/codec, prerequisites, runtime и полный crash recovery остаются открытыми. Исторические статусы ниже не отменяют этот ограниченный verdict.

**Актуальное решение пользователя, 2026-11-14:** ответом «Ок» после предъявления двух открытых решений согласованы (1) один origin, полностью покрывающий request, без partial union и (2) сохранение durable binding как immutable history admission без post-commit runtime consumer. Точный объём и оставшиеся gates — §9. Формулировки PROPOSED/ожидания решения ниже сохраняют историю review; по этим двум решениям ожидание снято. Это не приёмка runtime или всего C-PIN-1.

2026-11-14. **PROPOSED FOR JOINT REVIEW. Не ACCEPTED, не IMPLEMENTED.** Owner — Snapshot (`application/publication` и Artifacts); Pack подтверждает authenticated pin/manifest boundary, Source — неизменность S1/S2. Основание разрешённого scope: `source-pack-s1-s2-implementation.md`, C-PIN-1, «разрешённый следующий срез». Эта редакция конкретизирует только pinned часть `pack-preparation-source-authority-contract.md`, не принимает весь прежний proposal.

Файл сохраняет прежнее имя для существующих ссылок; актуальный текст — редакция 2. Итог review редакции 1: **CHANGES REQUIRED**, PIN-GRANTS-1 / PIN-BINDING-PURPOSE-1 / PIN-LEDGER-TESTS-1. Ни прежние адресные PASS, ни приведённые ниже исправления не означают принятия новых решений. Дельта для повторного review перечислена в §8.

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
- `PreparationSourceBinding`: обязательные `target: OperationLeaseRef`, `request: SourceProofReadInput`, `origin: PinnedManifestSourceOrigin`, `sources: tuple[VerifiedArtifactRef, ...]`.

Этот roster (enum и два records) принадлежит Snapshot; records strict/frozen/extra-forbid/revalidate-always, без defaults. Existing `ArtifactRef`, `OperationLeaseRef` (`dataModel/artifacts/lifecycle/lease.py`), `VerifiedArtifactRef` и holders (`dataModel/artifacts/lifecycle/holders.py`) используются без копий. Source owns request/proof types; Pack owns pin. `sources` определяет фактические holders, единственный `origin` — проверенный pin/manifest context. SourceProofResult/private evidence в ledger не сохраняется. Прежний proposed PreparationSourceEntry удалён из pinned roster до реализации: общий origin не нужно повторять для каждого ref. Operation variant не вводится.

**Предлагаемое owning правило PIN-GRANTS-1: только полные альтернативные origins.** Один grant удостоверяет весь exact requested proof и весь preflight closure одного manifest. Sources идут в порядке `SourceProofResult.durable_refs`, каждый full ref ровно один раз. Для manifest root допустим только `PinHolder(pin.pin_id)`; для любого child — только `ArtifactRetentionHolder(origin.manifest)`. Нельзя создать фиктивный PinHolder(child). Empty proof даёт sources=(), но origin остаётся обязательным и issuance проверяет pin/manifest и successful empty coverage/preflight. Поэтому смена origin обнаруживается даже для empty proof.

Signature register_sources с tuple grants сохраняется из S1/S2, но этот pinned-only срез допускает **ровно один** полный grant; ноль или более одного → INVALID_GRANT до append. Origin задаётся переданным internal input pin до checks; issuer/provider не перебирают альтернативы и не делают fallback. Если X и Y каждый независимо покрывают полный request, вызывающая сторона может предъявить один из них для первой попытки, но Snapshot не объединяет grants и не выбирает маршрут. Если X держит A,B, Y держит C, а request требует A,B,C, этот сценарий данным контрактом не поддерживается: full checks X или Y откажут. Нельзя сначала получить partial grants и затем union. Это предложенный более узкий выбор, а не уже принятая рекомендация reviewer.

Повтор одного canonical request в разных provenance rows не создаёт новый registration key. Повтор register с тем же target/request/origin/sources — no-op после fresh guards. Последовательный register того же request с другим manifest/pin (даже если оба полностью покрывают request) → IMMUTABLE_BINDING_CONFLICT, без overwrite/second row; outer transaction откатывается целиком, включая первый register/adopt. Автоматической смены origin, объединения или выбора «первого по ref» нет. После confirmed rollback retry по-прежнему предъявляет исходный input (§2), а не заменяет его другим origin.

Semantic key store: target.operation_id + target.preparation_fingerprint + canonical exact request; full target fence/value проверяется при read и append. Equality — полная canonical record equality после checksum/strict decode, не совпадение digest. Same binding — no-op; другое происхождение/значение в том же key — immutable conflict. Missing binding — None только у store; provider выдаёт AUTHORITY_NOT_REGISTERED. Corrupt bytes/chain/checksum — infrastructure.

Digest служит только ускорителем поиска canonical request. При совпавшем digest и разных canonical requests это разные semantic keys: append не является no-op и read не возвращает чужую запись; storage layout должен уметь различать их. При одинаковом canonical request и разных canonical binding values это IMMUTABLE_BINDING_CONFLICT независимо от digest. Caller target fence, отличный от current persisted lease, отвергается owning STALE_LEASE до mutation; existing binding с другим fence при уже проверенном current target также не переиспользуется — IMMUTABLE_BINDING_CONFLICT. Takeover/remapping записи запрещён.

Append выполняется в той же target transaction, что adopt и READY. Никакого отдельного commit PREPARING. Atomic commit сохраняет binding и READY/candidate/target holds вместе. Историческая фраза исходного proposal о более раннем committed registration **не применяется к этой pinned-only редакции**. SQL layout и canonical IDs ещё требуют отдельного owning storage/codec review перед реализацией; не назначаем ID поверх добавленных R1–R3 20301/20302/20306/20307 и не создаём новый schema counter или legacy decoder.

**Назначение записи, PIN-BINDING-PURPOSE-1.** Во время transaction provider.resolve_sources читает регистрацию и получает exact checked pairs; immutable key запрещает противоречивую регистрацию одного request в разных последовательных стадиях. После commit **runtime consumer этой записи в данном срезе отсутствует**: READY replay проверяет candidate/target holds и не читает origin binding. Сохранение предлагается только как immutable provenance в existing operation ledger: зафиксировать, какой exact pin/manifest и какие source-holder identities были проверены для committed preparation, чтобы запись не терялась вместе с runtime registry. Это историческое объяснение принятого admission, не доказательство нынешней доступности refs, не новый audit API, не восстановление input/grant и не recovery mechanism. Дополнительный production reader не выдумывается. Цена — codec/schema/storage без post-commit operational consumer; сохранение этой истории требует явного owning согласия при review. Если такое назначение не принимается, нужно отдельно пересмотреть принятую register/resolve/storage границу до кода, а не незаметно заменить её transient map.

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
| Coverage/empty/malformed | Все proofs из manifest, extra available allowed, extra requested refused; empty sources ровно (), origin обязателен; strict nested DTO и independent Source diagnostics |
| Child/root retention | Root только PinHolder; child только manifest retention; missing child refusal, без acquisition источника issuer-ом |
| Late second-proof refusal | Первый register/adopt rolled back; exact caller refusal только после rollback; два independent SQLite connections |
| Close/GC race | Одна временная SQLite DB, два соединения, реальный guarded close/GC; protection от первого origin read до commit; no sleeps как единственное доказательство порядка |
| READY / unknown / cancel | Old pin closed не мешает valid READY replay; unknown не заменён refusal; evidence cleanup в finally |
| Restart input | Отдельно показать подтверждённого owning producer полного replay input; без него crash-recovery gate OPEN, retained-input retry не переименовывать в доказательство recovery |
| Полные альтернативы / partial запрещён | X={A,B}, Y={C}, request={A,B,C}: ни одного successful grant; X и Y каждый full: один выбранный input разрешён, tuple из двух grants → INVALID_GRANT без append; пустой tuple также отвергнут |
| Identical ledger append | Дважды exact target/request/origin/sources → no-op второго append после guards; bytes/количество records неизменны, после commit второе соединение видит одну запись |
| Same key / different origin | Последовательные registrations одного request с разными full origins → IMMUTABLE_BINDING_CONFLICT; исходные bytes не изменены, caller получает отказ после rollback всех provisional effects. То же для empty request с разными origins |
| Same digest / different canonical | Контролируемая коллизия lookup digest для двух разных canonical requests не возвращает чужой binding и не даёт ложного no-op; distinct semantic keys различимы. Одинаковый request, другой canonical payload → конфликт; реальный hash взламывать не требуется |
| Corrupt bytes / checksum | Отдельно invalid payload при проверяемом checksum и checksum mismatch → PublicationInfrastructureError; никаких None/no-op/refusal вместо corruption, запись не переписывается. Fault injection только в storage corruption test, не способ создания lawful fixture |
| Same request / different target fence | Stale caller lease → STALE_LEASE до writes; checked current target против прежнего binding fence → IMMUTABLE_BINDING_CONFLICT. Исходный binding не меняется, новый не вставляется, second connection подтверждает отсутствие mutation |

Source fixtures — `backend/tests/sourceVersioning/support/finalizedFixtures.py` по G2, без fabricated rows. Pack предложил `backend/tests/worldPack/support/pinnedProvenanceFixtures.py`: новый, ещё не implemented/accepted import; strict manifest/provenance принадлежит Pack, pins/holds создаются реальными Snapshot adapters, captures — Source G2. Snapshot integration location предлагается `backend/tests/snapshotCore/storage/publication/test_pinned_origin.py`; реализация только после prerequisite/fixture/storage acceptance. Старые fixtures не конвертировать и не создавать legacy adapters.

Обязательная matrix плана: три запрета DAG соблюдаются только в этом internal atomic design scope; public междоменный маршрут не заявлен. Роли/deps/effects/отказы — §3; typed POJO/non-overlap — §3,5; порядок — §4 по S1/S2; public/data/settings CRUD границы — §1,3; unresolved external input producer — §2. Поэтому **полная приёмка C-PIN-1 и execution-ready пока невозможны**. Review этой редакции может отдельно принять first-call/retained-input retry contract; это не молчаливое закрытие crash/DDL/codec/runtime gates.

Изменение прохода — этот owning документ. Source implementation-план и runtime-код не изменены. Проверены текущие ExecutionPins/PinnedManifestGuard/ManifestPinRead, publication operation rows, R1–R3 report/types, S1/S2 r2 и исходный authority proposal. Runtime tests не запускались. Новые ноды, restart-протокол, operation-origin G4 и finalizer hookup не проектировались.

## 7. Результаты совместной проверки

**Актуальный итог редакции 1 — CHANGES REQUIRED.** Последующее пользовательское review, записанное в [Source report](source-review-pinned-origin-r1.md), выявило P1 PIN-GRANTS-1 (несогласованность full issuance и per-ref union), P2 PIN-BINDING-PURPOSE-1 (нет заявленного post-commit consumer), P2 PIN-LEDGER-TESTS-1 (неполная ledger matrix). Ни один исторический адресный PASS ниже не закрывает эти findings. Редакция 2 предъявляет исправления для повторной проверки; общий PASS отсутствует.

2026-11-14, Pack (чат `01a1cfce-ff7d-7e30-b738-f075bf490f13`): **PASS в узком consumer/design scope: first call + explicit retained-input retry после confirmed rollback.** Прочитана вся редакция 1, повторно сверены actual ManifestReadReason/ManifestReadRefusal и PinnedManifestGuard.manifest_guard. Actionable findings по запрошенным Pack границам нет. Подтверждены no acquire/latest, full available proofs/evidence binding, root/child holders, fresh grants, READY-before-origin и unknown precedence.

Nullable refusal context сохраняется как в existing guard: missing/foreign/closed без найденного ref, missing hold/unsealed с exact ref. Редакционное замечание о форме check_coverage учтено в §4.3: явно показан SourceProofCoverageCheckInput, контракт метода не менялся.

Pack PASS не закрывает autonomous input reconstruction, SQL/codec/runtime, G4 или fixture implementation. Pack тесты не запускал.

2026-11-14, Source: [отдельный отчёт](source-review-pinned-origin-r1.md), **PASS по совместимости first-call/explicit retained-input repeat с accepted S1/S2**. Подтверждены issuance после fresh preflight внутри register-stage, отсутствие collector/bind внутри provider, неизменный adopt с полными повторными проверками, exact refs/holds, rollback/unknown/revoke и разделение SourceFailure/authority codes. Новых блокирующих замечаний по Source semantics/order нет. Source runtime tests не запускал. Указанная в отчёте сокращённая запись check_coverage уже уточнена в §4.3 до accepted named input; семантика не менялась.

Актуальный helper для будущей реализации — `backend/app/dataModel/validation/diagnostics/validatorAggregationHelper.py`, как отмечено Source. Исторический `app.core.validatorAggregationHelper` не является основанием создавать compatibility module.

Исторически получены два адресных consumer/design PASS в указанной узкой границе; последующее итоговое review выше требует изменений. Полный crash input producer, storage/codec и runtime gates остаются открыты. Статус исправленной редакции 2 — PROPOSED FOR JOINT REVIEW; код этим итогом не разрешается.

## 8. Решения редакции 2 для повторного review

1. PIN-GRANTS-1: предлагаются full alternative origins и ровно один grant на registration. Partial union исключён. Binding хранит один origin и ordered sources; это заодно сохраняет origin empty proof. Same request с другим origin конфликтует, включая последовательные обращения в одном outer writer. Нужна проверка Source/Pack и принятие owning выбора пользователем.
2. PIN-BINDING-PURPOSE-1: durable запись предлагается сохранять как immutable admission provenance; post-commit runtime consumer отсутствует и не заявляется. READY/recovery её не используют. Согласовать ценность сохранения истории до storage реализации; промежуточный commit не добавлен.
3. PIN-LEDGER-TESTS-1: добавлены exact no-op/conflict/collision/corruption/fence cases с no-mutation и caller/second-connection outcomes. Это test requirements, не выполненные tests. DDL/codec layout остаётся отдельным gate.

Правки прохода только документальные. Code/SQL/runtime/Source implementation-план не менялись. G4/finalizer/DAG/crash input scope не расширялся. Findings считаются предъявленными к повторному review, а не закрытыми самим автором.

### Повторный Pack review редакции 2

2026-11-14: Pack подтвердил устранение противоречия full grant/per-ref union, сохранение origin для empty proof и полноту design matrix PIN-LEDGER-TESTS-1. Новых Pack-boundary findings нет; **общий PASS не выдан** до решения пользователя по §8.

Последствие предлагаемого правила одного origin: одинаковый proof в валидных provenance rows разных manifests приводит к отказу всей preparation, если caller предъявляет для одного request разные pins. Автоматического dedup/выбора origin нет. Это новое ограничение допустимых входов, не только техническое исправление. Requested proof A+B поддержан этим срезом лишь при полном logical coverage и storage closure одного pinned manifest; общий mixed-origin Pack остаётся вне scope.

Pack также подтвердил: durable history не нужна технически для retry/READY и не является его обязательным recovery требованием. Historical-only назначение названо честно, но ценность и стоимость её сохранения требуют пользовательского решения. Ни Pack, ни Snapshot не заменяют запись на transient вариант без пересмотра контракта. Статус остаётся PROPOSED; новый общий PASS и разрешение реализации отсутствуют.

### Повторный Source review редакции 2

2026-11-14, [Source report](source-review-pinned-origin-r1.md): full alternatives/exactly one grant совместимы с Source semantics при принятии этого ограничения. Подтверждены binding-level origin для empty proof и same request/different pin conflict. Документальный пробел пяти ledger test requirements закрыт; runtime не проверен. Назначение historical admission provenance раскрыто без выдуманного post-commit consumer; Source не принимает за пользователя решение о сохранении и стоимости. Оба повторных consumer review получены, но общий ACCEPTED отсутствует до решения по §8. Новый scope и код не разрешены.

## 9. Пользовательское решение после повторных reviews

2026-11-14 пользователь согласовал оба предъявленных выбора редакции 2:

1. **Single-origin принято:** один полный grant на registration; один pinned manifest покрывает весь logical request и storage closure. Partial union/fallback отсутствуют. Same request/different origin конфликтует; ограничение распространяется и на одинаковый proof в разных manifests при предъявлении разных pins. Origin сохраняется и при empty proof.
2. **Historical persistence принято:** durable binding сохраняется как immutable admission provenance в existing preparation ledger. После commit runtime consumer в этом срезе отсутствует; для retry/READY запись технически не нужна и recovery mechanism не является. Новый audit API, промежуточный commit и автономное восстановление input не вводятся.

PIN-GRANTS-1 и PIN-BINDING-PURPOSE-1 получили owning пользовательское решение после повторных Source/Pack checks. Документальный PIN-LEDGER-TESTS-1 закрыт добавленной matrix и повторными reviews; выполнение этих тестов ещё предстоит. Не объявляется новый независимый общий review PASS.

Остаются открытыми: concrete SQL layout/canonical registrations и их review, implementation prerequisites G1/G2/G3, реализация и runtime/typing/race tests, producer полного input для автономного crash recovery. Scope остаётся first-call/explicit retained-input retry. G4/finalizer/DAG не расширяются. Этот ответ пользователя фиксирует решения design; runtime-код в данном проходе не меняется, готовность implementation-плана должна быть проверена отдельно.

## 10. Итоговое независимое review редакции 2

2026-11-14 прочитан [акт независимой проверки](source-pinned-origin-final-review-2026-11-14.md), выполненной отдельным read-only агентом `pinned_final_review`. **PASS только first-call и explicit repeat полного исходного input после confirmed rollback**, новых actionable findings нет. Проверены обязательные критерии DAG/ownership/public-internal/порядок/CRUD/dependencies/POJO-errors и пользовательское решение §9.

PIN-GRANTS-1 и PIN-BINDING-PURPOSE-1 закрыты на уровне design с учётом пользовательского принятия. PIN-LEDGER-TESTS-1 закрыт на уровне требований к tests; сами tests не выполнены. Ограничение single-origin относится к pinned issuer, generic Source adopt не сужается.

PASS не закрывает SQL layout/canonical registrations, implementation prerequisites G1/G2/G3, runtime/typing/race tests, autonomous crash input producer или весь C-PIN-1. G4/finalizer/public DAG wiring не входят. Код этим актом не разрешён. В этом проходе изменён только owning документ; runtime tests не запускались.

## 11. Следующий storage/codec design-срез

По указанию пользователя «Далее», 2026-11-14: [конкретный storage/codec proposal](snapshot-pinned-origin-storage-codec-proposal.md). Предъявлены immutable detail-таблица existing operation ledger, exact canonical request key без hash-only equality, codec/store responsibilities и matrix проверок. Найдены два transitive contract gaps: UUID в ManifestPinRead не поддержан canonicalCodec (реальный repro: CanonicalEncodingError), SourceProofReadInput исключён из Source persisted manifest и не имеет предъявленной registration. Pack pin record registration также требует owning подтверждения. Native UUID tag 10 и отдельные owner registrations только предложены; Source/Pack запрошены, dependent code/DDL не меняются до решения. Принятый single-origin/historical design и его PASS этим не расширяются.
