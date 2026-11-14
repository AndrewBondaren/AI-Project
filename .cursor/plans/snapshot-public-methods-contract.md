# Snapshot public methods — предложение для согласования перед DAG

Contract changes R1–R3 предъявлены отдельно: [snapshot-retention-cancel-diagnostics-contract.md](snapshot-retention-cancel-diagnostics-contract.md). В частности, предложены SectionStateRetention/SectionHistoryRetention, existing OperationCancelled carrier и расширение core diagnostic union. Это требует приёмки до изменения accepted DTO/codec; готовность полного apply пока не объявляется.

Дополнительная S3 сверка: [snapshot-public-apply-atomic-trace.md](snapshot-public-apply-atomic-trace.md). Для public apply обнаружены конкретные contract gates retention destinations/inheritance, cancellation replay и typed core refusals. Read proposals от них независимы. Поэтому readiness signatures к review не означает завершённого public apply implementation contract. Предложенный отдельный cancellation carrier в S3 дополняет error roster этого документа только после принятия.

2026-11-14. CONTRACT PROPOSAL READY FOR REVIEW для трёх методов. Связан с [планом интеграции](snapshot-public-contracts-dag-integration.md). Код/ноды не реализованы. Apply signature/outcome — existing freeze; новые read signatures, error transport и узкий read-UOW port ниже предъявлены для пользовательской приёмки. Read-UOW механизм найден в существующем коде, не является отсутствующей реализацией. Контракты остальных доменов сохраняются v1 без адаптеров. Полный CRUD и runtime readiness этим статусом не объявляются.

## 1. Concrete owner и три метода текущего среза

Единственный public class — WorldSnapshotService, backend/app/application/worldSnapshot/service/worldSnapshotService.py. Public caller каждого метода — непосредственно согласуемая нода DAG. API/debug/worker не вызывает сервис напрямую. Разделение read/write нод и их имена определяются позднее чатом DAG.

```python
class WorldSnapshotService:
    async def apply[S: DomainSection](
        self, patch_set: PatchSet[S],
    ) -> SnapshotApplyResult: ...

    async def read_snapshot(
        self, snapshot: SnapshotRef,
    ) -> SnapshotReadResult: ...

    async def read_publication(
        self, request: SnapshotPublicationReadInput,
    ) -> SnapshotPublicationReadResult: ...
```

read_publication здесь **exact historical publication**, не неявный current/latest read. Предварительное намерение добавить current read заменено exact вариантом после проверки ports: existing IWorldPublicationStore.read возвращает nonoptional ref, а публичный контракт отсутствующего мира ещё не определён. Не объявлять такой lookup готовым посредством придуманных NOT_FOUND exceptions. Получение current expected heads для нового сценария — отдельный будущий контракт; данные ожидаемых heads уже входят в existing apply input.

Не вводятся generic CRUD(operation=...), второй фасад, методы prepare/apply internal stages для DAG или дублирующий SnapshotWriteInput. Runtime create/update состояния проходит только apply; это не разрешение изменять immutable snapshot row.

## 2. Input/Output: точные поля и модули

Все новые records: Pydantic BaseModel, strict=True, frozen=True, extra=forbid, revalidate_instances=always; обязательные поля, включая nullable, без молчаливых defaults. Типы identity/metadata только existing, не зеркала.

| Тип | Модуль backend/app/dataModel/ | Поля / инварианты |
|---|---|---|
| PatchSet[S], existing | patch/request/patchSet.py | Existing format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Состав не меняется |
| SnapshotApplyResult, existing | worldSnapshot/results/apply.py | category, operation_id, request_fingerprint, committed, diagnostics. Existing invariant COMMITTED vs CONFLICT/REJECTED сохраняется |
| SnapshotRef, existing | worldSnapshot/identity/refs.py | WorldSnapshotRef или PlayerSnapshotRef с existing discriminator. Прямой named input read_snapshot, без обёртки с тем же ref |
| SnapshotReadResult, proposed | worldSnapshot/results/read.py | snapshot: SnapshotRef; metadata: SnapshotEnvelope \| None. Non-null metadata.ref строго равен snapshot; None означает отсутствие exact записи, не corruption |
| SnapshotPublicationReadInput, proposed | worldSnapshot/requests/publicationRead.py | world_uid: EntityUid; publication_id: EntityUid. Оба обязательны; target exact |
| SnapshotPublicationReadResult, proposed | worldSnapshot/results/read.py | request: SnapshotPublicationReadInput; publication: WorldPublicationRef \| None. Non-null совпадает по world_uid/publication_id; None — отсутствие exact записи |

Read result связывает ответ с запросом, а не дублирует поля metadata/publication. Null — нормальный результат существования, не строковый diagnostic. Read не заявляет доступность всех retained artifacts, чужого payload или capture authority; найденная metadata и verified body — разные гарантии. Missing persisted parent при apply остаётся corruption, не преобразуется в этот null result.

Новые records не заменяют SnapshotEnvelope, WorldPublicationRef, SectionStateRef, AcceptedStateReader или Source capture/proof. Последний возвращает иной semantic result и не является Snapshot read API.

## 3. Error contract: existing baseline и точное предложение

Existing apply business result остаётся SnapshotApplyResult с CONFLICT/REJECTED и исходными concrete FieldPathError subclasses. Никаких infrastructure категорий в SnapshotApplyOutcomeKind. Независимые diagnostics сохраняют порядок фаз/секций/producer; общий FieldPathError нельзя инстанцировать вместо конкретного owning класса.

Existing infrastructure carriers в application/publication/errors.py: OperationBusyError, PublicationInfrastructureError, UnknownCommitOutcome. Они сейчас не имеют публичного dataModel fault. Поэтому одно перечисление этих исключений не закрывает критерий typed public errors. Предлагается **один Snapshot boundary carrier**, не изменение глобальных publication exceptions:

`SnapshotPublicError` в backend/app/application/worldSnapshot/errors.py содержит `fault: SnapshotPublicFault`, исходное исключение сохраняет через cause. Новый fault в backend/app/dataModel/worldSnapshot/errors/publicFault.py:

- SnapshotPublicOperation(StrEnum): APPLY, READ_SNAPSHOT, READ_PUBLICATION.
- SnapshotPublicFailureKind(StrEnum): INVALID_INPUT, BUSY, INFRASTRUCTURE_FAILURE, OUTCOME_UNKNOWN. Это категории transport, не новые копии domain reason codes и не operation terminal.
- SnapshotPublicFault: operation: SnapshotPublicOperation; kind: SnapshotPublicFailureKind; operation_id: EntityUid | None; request_fingerprint: RevisionHex | None; input_issues: tuple[JsonFieldError | WireShapeIssue, ...]. Все поля обязательны. Значения operation enum: apply/read_snapshot/read_publication; kind: invalid_input/busy/infrastructure_failure/outcome_unknown.
- JsonFieldError и WireShapeIssue — existing конкретные POJO из dataModel/validation/importIssues/jsonFieldError.py и wireShapeIssue.py, с existing JsonValidationCode и typed WireLocation. Новый SnapshotInputFieldCode/SnapshotInputFieldIssue **отозван как дубль**. FieldPathError применяется только к существующему объявленному полю; root/wrong model/extra unknown key описывается WireShapeIssue, не выдуманным FieldRef. Pydantic ErrorType сохраняется в pydantic_type для SCHEMA_VIOLATION по existing invariant.

INVALID_INPUT требует непустые input_issues и null binding до успешной строгой валидации; нельзя извлекать trusted operation_id из malformed dict. Остальные kinds требуют пустые input_issues. Для reads operation_id/fingerprint всегда None. Для apply после успешной проверки immutable request binding оба non-null; до неё оба None. OUTCOME_UNKNOWN допустим только для APPLY и требует binding; причина остаётся UnknownCommitOutcome. BUSY сообщает отказ текущего вызова из-за занятости, не обещает auto-retry и не утверждает отсутствие effects другой попытки. Infrastructure fault не включает raw payload/SQL/exception message.

Admission input fields агрегируется стандартным field-path/collector механизмом проекта, с типизированными путями. Proposed mapper application/worldSnapshot/validation/publicInputValidation.py::SnapshotPublicInputValidation отвечает только за revalidation трёх named входов и перенос structural ValidationError в existing F09 POJO; не вызывает общий world/import pipeline. Exact admitted collector tuple — (JsonFieldError, WireShapeIssue). Порядок — declaration fields, вложенные tuple индексы, затем независимые root/unknown-key issues в исходном decoder order. Не сортировать по сообщениям, не переносить raw input в message. Domain semantic/model invariants после structural admission сохраняют existing owning коды и фазы apply, не превращаются в generic schema errors. Unexpected programmer errors не маскировать под INVALID_INPUT. Обычный CancelledError распространяется как отмена invocation; подтверждённый/неизвестный storage outcome логируется по transaction acknowledgement, отмена не означает durable cancel operation. Если uncertainty установлена владельцем transaction, не заменять её обычным business result.

SnapshotPublicError — только граница F09/F05/F06 transport для этих методов. Existing F03 business SnapshotApplyResult и scoped D1 reasons не оборачиваются им как новые domain issues. Исходные PublicationInfrastructureError/OperationBusyError/UnknownCommitOutcome остаются cause. Это не общий errors framework и не замена exception классов storage. Публичные ошибки никогда не импортируют engine NodeError; их mapping принадлежит будущему DAG binding.

Это предложение затрагивает публичную границу, поэтому требует пользовательского решения до кода. Scoped D1 collector и existing business codes не мигрируются этим предложением. Duplicate enums ошибки owning доменов не вводятся. Полный доказанный roster errors конкретных registered sections остаётся prerequisite их admission, а не повод конструировать новые mirror issues.

## 4. Вложенные вызовы и transaction ownership

### apply

Порядок existing freeze docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок» неизменен:

1. Strict input/registry/formats/dependencies/fingerprint validation.
2. Immutable operation binding; exact terminal replay до повторного чтения refs. Same ID/different request не меняет original record.
3. Один apply claim; artifact protection/verification.
4. Общая publication transaction: expected world/player, gameplay/base/timeline/turn checks до handlers.
5. Все handler.validate на одной базе в declared order; aggregation исходных diagnostics.
6. Handler.apply только после успешных validations; отказ прерывает последующие handlers и откатывает набор.
7. Metadata → holder handoff → world/player publication CAS → terminal в одной transaction по owning freeze. COMMITTED наружу и success log только после confirmed COMMIT.

WorldSnapshotService не собирает PatchSet: его собирает DAG из native typed результатов доменных операций. Внутренний handler не вызывает чужой public pipeline и не пишет snapshot metadata/heads. Владелец transaction — publication commit store; сервис/handler/DAG не выполняют независимый nested commit. Exact terminal/refusal persistence и retry implementation ещё не закрыты 4D2; публичная подпись не выдаётся за реализованный lifecycle.

### read_snapshot

Strict SnapshotRef → service-owned read_scope → Snapshot history.read(ref, scope=scope) → strict validation identity/envelope → закрытие read scope → SnapshotReadResult. Нет writes, staging, generation, repairs, latest fallback или acquisition ownership. Read возвращает metadata по world/player union. Некорректная persisted metadata — infrastructure fault, не None. Точная existing semantics: history lookup по snapshot_id в выбранной chain table; отсутствующий ID даёт metadata=None. Если ID найден, но owner/timeline/decoded ref не равен request, existing adapter сообщает PublicationInfrastructureError. Public read сохраняет этот fail-closed исход, не делает второй lookup и не обещает скрыть mismatch как отсутствие. Это явное отличие от composite lookup read_publication, а не изменение принятого history port.

### read_publication

Strict input → service-owned read_scope → IExactWorldPublicationReader.read_exact(world_uid, publication_id, scope=read_scope) → проверка identity → закрытие read scope → result. Composite lookup world_uid+publication_id возвращает None, если такой пары нет; найденная inconsistent row/parent/head — infrastructure error. Caller не передаёт scope. Никакого current/latest lookup при отсутствии exact publication.

### Конкретный read-UOW port — reuse existing реализации

Предлагается узкий Protocol `ISnapshotReadScopeFactory` в backend/app/application/worldSnapshot/storage/readScopeFactory.py:

```python
def read_scope(self) -> AbstractAsyncContextManager[CommitReadScope]: ...
```

Concrete implementation уже существует: backend/app/db/repositories/sqlite/snapshotCore/commitScope.py::SqlitePublicationCommitStore.read_scope(existing_scope=None). Более широкий optional argument concrete метода не раскрывается через новый узкий protocol. Не создавать второй coordinator, adapter, wrapper или read connection factory. DI сервиса получает тот же объект как ISnapshotReadScopeFactory; history/exact-publication adapters используют его же database/SqliteScopeRegistry.

Текущий механизм _transaction(None, False): BEGIN через SqliteTransactionDriver с write=False, task/database-bound issued scope, read-only facet; success завершает read transaction через ROLLBACK, revoke всегда в finally. Нет synthetic operation_id и writer admission. Ambient/nested transaction отвергается; service открывает один scope на public read, stores получают его explicit и не открывают competing UOW. Scope не возвращается DAG, результат содержит только immutable data.

Важная existing особенность: failed read ROLLBACK тоже может поднять UnknownCommitOutcome из общего coordinator и quarantine соединение. Public read переводит это в SnapshotPublicError(kind=INFRASTRUCTURE_FAILURE, operation_id=None, request_fingerprint=None) с исходным cause: **не было write operation, требующей recovery**. Результат read не возвращается до успешного выхода scope. APPLY UnknownCommitOutcome сохраняет OUTCOME_UNKNOWN и checked binding. Этот mapping не меняет механизм coordinator и не ловит CancelledError как обычный fault.

Оба reads не возвращают право на дальнейшее чтение blobs: lifetime/pin относится к владельцу payload. Они не обязаны открывать Source capture или Pack pin и не удерживают их скрыто.

## 5. Source / Pack / Cache — проверенный минимальный mapping

| Владелец | Нужен ли прямой вызов этим трём Snapshot методам | Передача через DAG / граница |
|---|---|---|
| Source | Нет. Snapshot metadata read не читает authored bodies; apply принимает native prepared sections | Source capture/proof остаются owning DTO. Если нужны producer, DAG вызывает Source отдельно и передаёт результат его потребителю. Snapshot не создаёт зеркальный proof/authority resolver |
| Pack | Нет public Pack call внутри Snapshot. Apply использует existing WorldPublicationRef.pack_hash, который уже входит в expected_world | PackActivationResult.publication может быть передан DAG как publication expectation, но одного activation недостаточно для runtime: apply требует gameplay_started=True. Не конструировать готовый PatchSet из candidate и не запускать activation в apply |
| Cache | Не требуется для корректности metadata/publication read/apply | Cache key/namespace/retention для Snapshot не согласованы и не вводятся «на всякий случай». CacheService публично вызывает DAG только при отдельном принятом binding. Cache hit не доказывает актуальность head/holds |

Основания сверки: source-pack-boundary-response-2026-11-14.md, pack-contract-final-scope.md и cache-public-contracts.md. Принятое exact candidate READY ledger хранение относится к Pack preparation, не является новым Snapshot public методом и не блокирует эти read signatures. Source authority provider для Pack остаётся самостоятельной задачей; Snapshot не присваивает его через общий read facade.

Отложенные генераторы/остальные домены сохраняют v1. Их native compatibility не утверждается; конвертация output→section внутри Snapshot запрещена. Фактические v1 места требуют локальных комментариев по интеграционному плану. Пустой core tick и contract fixtures не доказывают production registration таких доменов.

## 6. Что передавать DAG после согласования

Три exact methods §1, dataModel fields §2, error proposal §3, trace §4. DAG владеет вызовом, ветвлением по result/error, сборкой PatchSet и дальнейшим вызовом владельца payload; Snapshot не возвращает команды запуска. read_snapshot.metadata и read_publication.publication — только metadata/identity результаты. Apply COMMITTED передаёт existing SnapshotCommitRefs; CONFLICT/REJECTED не содержит committed refs. Ни один результат не содержит scope/lease/grant/backend.

Для приёмки node binding отдельно зафиксировать происхождение operation_id/preparation_fingerprint/expected heads, native section producers и порядок, а также путь read missing/refusal/unknown/cancellation. Ноды сейчас не назначены, сообщение в DAG не отправлялось. Реализацию нод согласуют после пользовательской приёмки контрактов; public readiness не равна runtime readiness.

## 7. Статусы и проверяемые gates

- Apply signature/result: reuse accepted freeze; concrete method implementation и terminal/retry остаются OPEN.
- Два exact read methods и POJO: конкретное предложение готово к review; public errors также предъявлены явно, не считаются принятыми.
- Read transaction issuer: existing SqlitePublicationCommitStore.read_scope; узкий ISnapshotReadScopeFactory предъявлен выше для принятия, отсутствующего storage механизма нет.
- Current publication/player head reads, restore, branch, delete/prune, settings CRUD: отдельная следующая спецификация. Ни удаление immutable history, ни settings exception не изобретены. Полный Snapshot CRUD пока не принят.
- Source/Pack/Cache: для текущих трёх методов новые public dependencies не требуются; будущая необходимость оформляется отдельно exact mapping.

Проверки будущей реализации: strict malformed inputs и concrete error types; exact missing без writes; wrong world/player/ref/version; corrupted metadata; no latest fallback; no payload reads; два SQLite connections для partial apply rollback, stale CAS, partial holder handoff, cancellation, replay/unknown; отсутствие domain→Snapshot и route bypass; typing + профильные regression + snapshotCore. Для комментариев/документального прохода эти tests не запускались.

Evidence этого прохода: прочитаны Snapshot freeze, существующие DTO/ports/service/reader/errors и Source/Pack/Cache boundaries. Выполнен git diff --check документов. Код, ТЗ, чужие изменения и DAG не изменялись. Документ не закрывает открытые gates обещанием будущего wiring.

## 8. Scoped D0/D1 и критерии решения по первому пункту

| Семейство / ответственность | Решение | Проверяемый критерий |
|---|---|---|
| F01/F09 input shape | Reuse JsonFieldError/WireShapeIssue, без Snapshot mirror codes | Missing/type/extra/wrong union root дают exact concrete тип, typed path/location и pydantic_type; нет фиктивного пути к undeclared field |
| F02/F03 apply contract/business | Reuse accepted PatchSet/registry/SectionRefused/SnapshotApplyResult | Semantic codes/producer order не меняются; rejected не создаёт fake committed refs |
| F05 infrastructure | SnapshotPublicFault transport, исходный cause; details только safe log projection | Corrupt row/IO не становятся None/REJECTED; read cleanup uncertainty не становится write recovery |
| F06 busy/cancel/unknown | Busy и unknown отдельные kinds; cancellation исходное исключение | Нет automatic retry, fake cancellation terminal или success до acknowledgement |
| F08 aggregation | Existing exact-admitted collector, scoped D1 metadata unchanged | Несколько structural errors до IO; malformed field не скрывает независимую причину |
| F04/F07 | Не добавляются этим срезом | Нет domain→NodeError; read не выдумывает warnings о generation |

Concrete public implementation owner — WorldSnapshotService; существующие SnapshotMetadataBuilder/AcceptedStateReader/SectionRegistry/storage/codec/log responsibilities остаются в integration plan. Новый SnapshotPublicInputValidation не владеет read/commit или domain semantics. Новый read protocol не владеет connection. Новые read-result POJO отличаются от metadata: описывают exact lookup existence/correlation, не копируют payload. SnapshotPublicFault не persisted outcome/receipt. Нового settings CRUD или exception к нему этот срез не утверждает.

### Матрица caller outcomes для трёх методов

| Сценарий | Caller видит |
|---|---|
| Malformed input любого метода до IO | SnapshotPublicError INVALID_INPUT, непустые existing shape issues, binding None |
| Missing snapshot ID / missing exact publication pair | Successful read-result с None соответствующего payload |
| Stored identity/parent/chain inconsistency | SnapshotPublicError INFRASTRUCTURE_FAILURE, исходный cause; не None |
| Concurrent publication после read | Read возвращает pinned historical result; он не обещает current head после scope |
| Valid apply semantic refusal / stale expected CAS | Existing SnapshotApplyResult REJECTED/CONFLICT согласно accepted phase order; no committed refs |
| Successful apply / same-request durable replay | Existing COMMITTED c сохранёнными refs; replay до повторной проверки target refs |
| Same operation_id, другой fingerprint | Existing rejected policy, без overwrite/повторного body исходной операции |
| Apply busy / uncertain commit | SnapshotPublicError BUSY / OUTCOME_UNKNOWN; unknown только с checked binding |
| Read cleanup uncertainty | INFRASTRUCTURE_FAILURE, cause UnknownCommitOutcome, quarantine сохраняется |
| Cancelled invocation | CancelledError после owning cleanup semantics; durable исход не выводится из отмены |

**Предмет приёмки пользователем сейчас:** три signatures; два read-result POJO и publication read-input; reuse shape errors и public transport fault; exact lookup/mismatch semantics; узкий read-UOW protocol поверх existing implementation. Поля и владельцы определены, больше нет отложенного решения «кто выдаёт read scope». После принятия можно передавать этот контракт DAG для node design; implementation public apply/terminal/retry остаётся отдельным разрешённым срезом, не обещанием готового исполнения. Restore/branch/settings/delete и новый authored Source writer не входят в первый пункт.

Повторная статическая сверка: commitScope.py read lifecycle/driver, historyStore read и worldPublicationStore.read_exact, FieldPathError/JsonFieldError/WireShapeIssue и error-contracts-1 F01–F09. Runtime/typing/regression не запускались: код не менялся. Новые поля/error mapping требуют tests при реализации, не считаются проверенными этим документом.
