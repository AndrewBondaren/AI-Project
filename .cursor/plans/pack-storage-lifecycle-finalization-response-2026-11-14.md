# Pack storage/lifecycle — актуальный internal contract

2026-11-14. Механизм READY storage/replay ACCEPTED пользователем: см. pack-serialization-deserialization.md и pack-contract-final-scope.md. Ниже точные **предлагаемые declarations**, ещё не реализованные и не автоматически принятые вместе с механизмом. Документ заменяет прежние варианты целиком.

## 1. Принято без повторного выбора

Exact existing PreparedPackCandidate(operation_id, manifest: ArtifactRef, preparation_fingerprint) сохраняется в existing operation ledger атомарно с READY после полного admission/adoption. READY replay читает candidate, проверяет identity/bytes/holds; не пересобирает manifest, не вызывает stage/finish.

Нет отдельного candidate store, нового holder, independent version counter или release marker. Manifest сохраняет existing OperationHolder точного lease; children удерживаются ArtifactRetentionHolder(manifest). Source proof/adopt не является provider сохранённых source-holder identities. Этот provider — обязанность preparation/publication.

## 2. Точные internal ports

Пути относительно backend/app/. Все async методы заимствуют scope; ни один не открывает и не завершает UOW. Scope проверяется по task/database/lifetime/capability. Для write scope дополнительно operation identity должна совпасть с lease/candidate.operation_id.

В application/publication/contracts/packPreparationBindingStore.py:

```python
class IPackPreparationBindingStore(Protocol):
    async def append_ready_binding(
        self, scope: CommitScope, lease: OperationLeaseRef,
        candidate: PreparedPackCandidate,
    ) -> None: ...

    async def read_ready_binding(
        self, scope: CommitReadScope, operation_id: EntityUid,
    ) -> PreparedPackCandidate | None: ...
```

SQLite adapter: db/repositories/sqlite/snapshotCore/operations/packPreparationBindingStore.py::SqlitePackPreparationBindingStore. Это порт к existing operation ledger, не отдельное хранилище кандидатов. Нужное schema declaration — один immutable candidate payload, связанный с operation_id уникально, в owning ledger; конкретное SQL представление должно пройти review с existing rows/codec. Новый schema counter не вводится.

В application/artifacts/contracts/scopedPreparationFinish.py:

```python
class IScopedPreparationFinish(Protocol):
    async def finish_preparation_scoped(
        self, scope: CommitScope, lease: OperationLeaseRef,
        refs: tuple[ArtifactRef, ...],
    ) -> OperationRecord: ...
```

Реализация — existing db/repositories/sqlite/artifacts/leaseStore.py::SqliteArtifactLeases. Для PACK_ACTIVATION finish требует сохранённый в том же scope candidate binding и включённый в refs candidate.manifest. Public generic finish не должен создавать PACK READY без такого binding. Это явное изменение внутренней проверки, не утверждение о текущем коде.

В application/artifacts/contracts/packCandidateRetention.py:

```python
class IPackCandidateRetention(Protocol):
    async def release_scoped(
        self, scope: CommitScope, candidate: PreparedPackCandidate,
    ) -> None: ...
```

Adapter: db/repositories/sqlite/artifacts/packCandidateRetention.py::SqlitePackCandidateRetention. Отдельного retain метода не требуется: root уже удерживается operation. Сервис получает действительный lease из ledger, не реконструирует fence по caller данным. Public Pack release не раскрывает этот scope или lease.

## 3. Binding, None и атомарность READY

Перед первым append: strict DTO, scope operation_id, kind=PACK_ACTIVATION; lease полностью равен persisted operation lease по operation_id/world_uid/kind/preparation_fingerprint/fence. Candidate.operation_id и preparation_fingerprint совпадают с lease. Manifest descriptor проверяется existing PreparedPackCandidate validator; owning verified manifest decode проверяет world_uid=lease.world_uid до append. ArtifactRef не содержит world_uid: нельзя утверждать world equality по одному ref.

Append допустим в PREPARING после admission/adoption, до finish; binding provisional до outer COMMIT. Existing identical candidate в текущей transaction — no-op; different candidate того же operation_id — BINDING_MISMATCH без overwrite. Для первого binding phase не PREPARING — WRONG_PHASE. Missing operation — OPERATION_NOT_FOUND. READY replay не вызывает append.

read_ready_binding — metadata read без blob IO/проверки живых holds. None означает unknown operation либо PREPARING без binding; различие caller при необходимости получает existing operation read в том же scope. Ранняя отмена до READY также может не иметь binding. READY/APPLYING/RECOVERY_REQUIRED либо activation terminal без обязательного candidate — PublicationInfrastructureError, не None. Corrupt/несогласованный persisted candidate/world/kind/fingerprint — infrastructure error. PREPARING с provisional binding видим внутри текущей transaction; confirmed PREPARING с binding недопустим: coordinator обязан не commit-ить незавершённый append/finish.

READY/replay owner отдельно проверяет exact operation identity/current fence, phase READY, полный live-set, seals, bytes/digest и accepted preparation input binding. Сам read не обещает пригодность candidate к activation. Историческое чтение binding после release не требует bytes.

Единый порядок: writer scope → identity/phase/admission checks → trusted source authority + scoped Source adopt всех closures → append_ready_binding → finish_preparation_scoped → confirmed outer COMMIT → наружный candidate. Любой отказ откатывает весь scope, включая предыдущие adopts. Finish проверяет exact unique refs == all operation holds, sealed members, отсутствие writers; закрывает admission и пишет READY. Нельзя подтверждать append отдельным commit. При unknown COMMIT caller получает UnknownCommitOutcome, fresh coordinator читает ledger; нельзя повторять stage/finish вслепую.

## 4. Existing-holder release и replay после GC

Первое release под общим writer lock:
1. Проверить scope/candidate и exact persisted candidate binding.
2. Загрузить operation и exact terminal PackActivationResult; kind/world/preparation identity и terminal.manifest согласованы. Для данного среза разрешён READY_INACTIVE terminal; ACTIVE terminal — ACTIVE_CANDIDATE, другие terminal/phase — WRONG_PHASE. Расширение на когда-то ACTIVE candidate не подразумевается.
3. Проверить exact persisted lease, закрытый admission/drained writers и root event chain. Другие holders того же manifest не запрещают release **своего** root.
4. Append release существующего OperationHolder(manifest) в этом scope. Не переписывать activation terminal, не создавать marker и не освобождать общие children links.
5. Наружный успех только после confirmed COMMIT владельцем UOW.

Replay сначала проверяет immutable binding/terminal и existing event chain по exact artifact identity + operation_id/fence. Полная валидная acquire→release цепочка без последующего acquire — evidence прежнего release; вернуть None, не читать физический blob, не seal/acquire/repair. Chain отсутствует или повреждена — PublicationInfrastructureError, не успешная идемпотентность. Если root ещё live, выполняется первое release. Existing terminal после release запрещает повторный acquire operation hold; попытка resurrection — corruption/нарушение lifecycle.

После GC должны сохраняться descriptor→artifact identity, candidate binding и holder events; physical deletion не удаляет replay evidence. Это требование к existing catalog/event ledger и обязательная проверка, не предложение отдельного marker store. Release одного A не снимает root B при одинаковом manifest. Children остаются защищёнными общей retention связью до owning GC самого manifest; release candidate не запускает GC и не делает cascade сам. Atomicity относительно нового holder/GC обеспечивается общим writer/GC guard, не последовательными публичными release вызовами.

Возврат None из release_scoped — provisional успешное действие/подтверждённый в scope replay, не самостоятельный commit. Rollback отменяет новый event. Lost acknowledgement даёт UnknownCommitOutcome на outer boundary, последующий replay использует ledger.

## 5. DTO и errors

Новых request/result DTO эти internal ports не вводят. Используются existing PreparedPackCandidate, OperationLeaseRef, ArtifactRef, OperationRecord, EntityUid, CommitScope/CommitReadScope. Candidate не содержит world/fence; их источник только checked operation record.

Один proposed typed fault вместо прежних двух пересекающихся ошибок:
- dataModel/artifacts/lifecycle/packLifecycleFault.py::PackLifecycleCode(StrEnum): OPERATION_NOT_FOUND, BINDING_MISMATCH, STALE_LEASE, WRONG_PHASE, MEMBERS_MISMATCH, UNSEALED_MEMBER, ACTIVE_CANDIDATE.
- PackLifecycleFault: operation_id: EntityUid; code: PackLifecycleCode; artifact: ArtifactRef | None. Strict/frozen/extra-forbid/revalidate-always, все поля обязательны. artifact non-null только для UNSEALED_MEMBER, для остальных None.
- application/artifacts/errors/packLifecycleError.py::PackLifecycleError(fault: PackLifecycleFault), exception carrier. Старые предложенные PackPreparationRetentionError/PackCandidateRetentionFault в этом срезе заменяются этим roster до реализации; это не rename существующего принятого кода.

Mapping: unknown operation mutation → OPERATION_NOT_FOUND; caller candidate/input differs → BINDING_MISMATCH; checked lease differs → STALE_LEASE; недопустимая phase/admission → WRONG_PHASE; missing/extra/duplicate requested refs → MEMBERS_MISMATCH; unsealed member → UNSEALED_MEMBER; release ACTIVE → ACTIVE_CANDIDATE. Wrong kind/world/preparation binding из caller — BINDING_MISMATCH. Не преобразовывать corrupt persisted binding/chain в эти коды.

Live writers/storage busy → existing OperationBusyError. Foreign/expired scope, corruption/IO → PublicationInfrastructureError. Commit/rollback uncertainty → UnknownCommitOutcome. Structural malformed input → strict validation до IO; это не durable refusal. Source adopt semantic failure сохраняет exact SourceFailure и исходный operation/code/path; outer rollback подтверждается до его возврата. Отмена invocation сохраняет coordinator semantics, не создаёт cancel terminal.

Pack public error mapping принадлежит Pack; приведённые internal outcomes не являются новым публичным CRUD и не должны попадать в public DTO как scope/lease.

## 6. Последний authority gap — точно чего не хватает

Owner этой незавершённой части — Snapshot в текущем чате; application/publication является его внутренним слоем. Это не внешняя зависимость от отдельного домена Publication. Следующий результат владельца — законченный acquisition/write/resolve contract, а не запрос пользователю найти другого исполнителя.

Актуальный полный proposal: [pack-preparation-source-authority-contract.md](pack-preparation-source-authority-contract.md). Предъявлены issuer, register_sources/resolve_sources, exact binding/origin/fault records, scoped pin port и owner-issued acquisition admission, запись в existing preparation ledger и restart/READY semantics. Это законченный предмет контрактного review, не accepted/runtime API. Исторические формулировки ниже об отсутствии proposal заменены указанным документом; canonical/SQL declarations и реализация требуют отдельной приёмки.

Source не предоставляет готовый authority resolver. Нужен **принятый durable preparation provenance contract** владельца preparation/publication: связь target operation/preparation fingerprint + exact SourceProofReadInput с per-ref existing VerifiedArtifactRef (ref + exact source holder), сохранёнными исходным trusted owner при получении authority. Для OperationHolder сохраняется полный lease/fence; для PinHolder — exact pin identity и lifetime/coverage authority. Source proof/digest и manifest-only pin не заменяют этот набор.

Эти identities появляются при настоящем acquisition/capture/pin admission и подтверждённом provenance исходного preparation context, а не при поиске произвольного живого holder во время restart. После restart читается тот же persisted binding; под общим write scope проверяются target/world/fingerprint, полный Source closure, seals, каждый source holder chain и действующая pin/operation authority. Затем existing scoped Source adopt получает VerifiedArtifactRef tuple и target OperationHolder; чужие источники не освобождаются.

Ни существующий PreparedPackCandidate, ни один operation fingerprint не хранят эту provenance mapping. Concrete accepted record/schema/port для её записи и чтения пока не предъявлен. Поэтому **не объявляется готовый provider signature/новый POJO**. Минимальный следующий owning результат: exact durable mapping declaration с источником каждого holder, timing записи и restart lookup; reuse existing ledger/context без отдельного receipt store. До него authority-dependent prepare остаётся OPEN. Append/read candidate и release signatures выше от выбора mapping не меняются.

## 7. Evidence и статус

## 7A. Конкретизация ledger schema — предложение владельца Snapshot

Следующее — exact schema proposal, а не уже принятый DDL. Приняты storage/replay semantics; код и SQL в этом проходе не меняются. Используется owning operation ledger в той же SQLite БД, без отдельного candidate/receipt store и без миграционного compatibility path.

**Candidate:** расширить existing PublicationOperationEventRow/publication_operation_events nullable полями `pack_candidate_data: bytes | None`, `pack_candidate_checksum: str | None`. Они заполнены только на READY event операции PACK_ACTIVATION и содержат canonical exact PreparedPackCandidate. Для остальных kind/phase оба NULL; никаких candidate/version/holder mirror fields. Unique READY event per operation обеспечивается проверкой phase-chain и дополнительной partial uniqueness по operation_id для phase=ready. FK operation_id остаётся существующим. Checksum — existing content_digest bytes, не новый identity hash. World/preparation/fence читаются из existing operation row/event и проверяются против decoded candidate; world manifest проверяется owning reader до append.

Уточнение реализации append_ready_binding из §2: **он регистрирует pending candidate в task/database/scope-bound coordinator state**, не commit-ит отдельную запись. finish_preparation_scoped потребляет pending candidate и вставляет один READY event вместе с candidate_data/checksum. Exit/rollback очищает pending registration; завершение scope с неиспользованным pending candidate запрещает commit. Два разных pending candidates дают BINDING_MISMATCH. После READY read_ready_binding читает данные event. Это предотвращает durable PREPARING с candidate и не требует отдельного candidate table. Signature append остаётся прежней; название обозначает логический append в текущей UOW. До finish candidate доступен только registry этого scope, не другому connection. Read-ready port не выдаёт pending candidate: PREPARING без READY всегда None. Эти положения заменяют прежнюю формулировку §3 о чтении provisional binding через read_ready_binding.

Persisted READY PACK event без этих полей — PublicationInfrastructureError; старый формат не адаптируется/не пересобирается. Terminal/release не удаляют READY event. Exact replay после GC читает binding из event без blob read, а READY usability check по-прежнему проверяет bytes/holds отдельно. Canonical registration PreparedPackCandidate должна переиспользовать его owning model; fixed IDs назначаются в review существующего schema roster, не копируются наугад.

**Authority:** предложить append-only extension existing operation ledger `publication_preparation_authorities`, row `PublicationPreparationAuthorityRow` в backend/app/db/models/snapshotCore/operationRows.py. Поля:

- `operation_id: str` — FK publication_operations.operation_id;
- `preparation_fingerprint: str` — exact copy проверенного existing binding;
- `request_data: bytes` — canonical exact SourceProofReadInput, не новый Source DTO;
- `request_checksum: str` — existing content_digest для bounded lookup/check;
- `target_fence: int` — positive checked lease fence;
- `authority_data: bytes` — canonical PreparationSourceBinding из authority proposal;
- `authority_checksum: str` — checksum payload.

Ключ `(operation_id, request_checksum)`; при совпадении checksum обязателен byte-for-byte compare canonical request_data. Collision/mismatched bytes не объединяются и не выдаются за same proof. request_data/key/preparation не изменяются; authority_data содержит exact target/request/entries и декодированное значение должно совпасть с projected columns. Unique key намеренно не включает fence: новый fence не создаёт обход immutable origin mapping прежней preparation. CHECK положительного fence/непустых blobs/checksum shape; FK operation_id; no UPDATE/DELETE. Insert guard требует kind PACK_ACTIVATION, phase PREPARING, current fence и preparation equality. Закрытие admission/terminal запрещает новые registrations, но разрешает чтение исторической записи. Никакого authority outcome/terminal/release marker в этой таблице нет.

Это новая **внутренняя таблица того же ledger**, не отдельный service/store результатов. Её принятие — явное schema решение, не скрытое следствие принятия candidate storage. Если пользователь не принимает расширение ledger, authority registration нельзя объявлять durable через один fingerprint; требуется другое явное storage решение. SQL layout/row validation идут вместе в будущем implementation slice, не через 0002 migration.

Точный порт authority — IPreparationAuthorityStore.append(scope, binding) -> None и read(scope, target, request) -> PreparationSourceBinding | None из pack-preparation-source-authority-contract.md. Persisted row авторизован только PackPreparationSourceAuthority.register_sources: он принимает opaque grants, проверяет issuing acquisition owner, full coverage и actual holds, затем вызывает append. Generic SQL writer/случайный tuple[VerifiedArtifactRef] не public admission. После restart resolve_sources читает exact binding и заново проверяет recorded origins; после READY старый origin lifetime уже не нужен для candidate replay, защищает target OperationHolder.

**Trusted writer/source:** runtime grant issuer и acquisition admission проектирует Snapshot owner. Operation path принимает checked Source finalizer/preparation owner scope с реальным source lease/holds; pinned path использует authenticated ExecutionPins scope, root PinHolder и child ArtifactRetentionHolder(manifest). Grant выдаётся в момент проверенного acquisition либо его checked resume, не восстанавливается по одному UID. Persisted registration не продлевает исходные holds; исчезновение источника до adoption даёт typed refusal. Register→resolve→Source adopt→candidate pending→finish READY происходит под общим writer/GC guard; release/close сериализуются им. Source semantic failures остаются SourceFailure, internal authority failures — PreparationAuthorityError; exact roster в authority document, busy/corruption/unknown сохраняют existing carriers.

**Точный вопрос Source на совместное review**, без нового public вызова: подтвердить, что accepted internal collector/subset rules позволяют issuer проверить request.proof против proof coverage decoded exact pinned manifest и получить full required closure в borrowed read facet, без acquisition и повторного finalize. Нужна ссылка на concrete internal method/signature в accepted Source binding; если его нет, предъявить только scoped read extension. Это проверка конкретного внутреннего Source seam, не передача Source обязанности хранить authority и не повод выдумать уже готовый provider. Подтверждение требуется перед зависимой реализацией pinned-origin path, не меняет operation-origin storage declaration.

Статически сверены holderStore.py (_current/acquire/release/handoff), leaseStore.py finish/recover, scope contracts, Source boundary и Pack accepted запись. Existing release сам по себе не закрывает proposed scoped policy/replay; actual scoped methods и typed fault пока отсутствуют. SQL declaration и authority mapping требуют review; механизм exact candidate existing ledger не переоткрывается.

Обязательные tests при реализации: два SQLite connections; candidate/READY atomic rollback; wrong world/fence/fingerprint; different candidate same ID; busy writers; cancel/adopt race; two terminal candidates same manifest; release/replay after physical GC; corruption chain; rollback release; unknown commit/readback; отсутствие extra holder/version/marker. Runtime/typing/tests в этом документальном проходе не запускались. git diff --check — только whitespace evidence. Код, DAG, генераторы и общие Pack планы не менялись.
