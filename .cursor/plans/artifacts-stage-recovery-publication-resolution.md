# SR-03 — Publication boundary for full stage claims

2026-11-26. Документальный owning PROPOSAL, вариант A. Код/SQL не менялись. Основной пакет: [artifacts-stage-recovery-contract.md](artifacts-stage-recovery-contract.md), SR-03. Artifacts owns stage-attempt authority; Publication остаётся инфраструктурой Snapshot и owns operation lifecycle/transaction acknowledgement. Publication StageAttemptService не вводится.

## Вердикт

### Review P2: identity drain adapter и отдельный crash-recovery этап

2026-11-26. Проверено требование одного object instance SqliteStageExecutionDrain. Этот adapter пока PROPOSED; runtime реализации для проверки statefulness нет. В предъявленном constructor единственная зависимость — ScopedSqliteAccess; собственные cache/locks/claims/epoch/policy не объявлены. Existing ScopedSqliteAccess проверяет scope через свой registry перед/после IO; authority хранится в registry/transaction и authoritative Artifacts state, не в identity read-only drain wrapper.

**Результат:** для двух stateless экземпляров exact одного owning adapter с одним и тем же access и единым predicate нарушения invariant не выявлено. Они могут наблюдать разные состояния при разных scopes/времени, но один экземпляр наблюдал бы их точно так же. Atomicity обеспечивается scoped повторной проверкой в transition transaction, а не singleton adapter. Исходное требование одного экземпляра было избыточным усилением composition.

**Принятая P2 поправка плана, 2026-11-26 («Правим»):** требование `drain_a is drain_b` снято. Сохранены required dependency без default; exact owning implementation; `drain.access is consumer.access`; общий registry/coordinator graph; отсутствие mutable per-instance state и hot-rebind; единый authoritative predicate и переданный scope. Разные adapter objects с этими свойствами допустимы. Если Artifacts добавит stateful claim authority, cache или policy, потребуется заново предъявить её ownership/identity гарантию; такое состояние не считается частью нынешнего read-only wrapper по умолчанию. Это принятие поправки документа, не runtime/code-go.

Будущий тест принятой поправки: два независимо созданных stateless drain adapters на одном access дают одинаковое решение для одного stable scope/state; чужой access/registry отклоняется; scoped transition recheck ловит изменение authority независимо от числа adapters. Не ослабляются identity требования к самим scopes/access/coordinator, backend write admission и runtime StageWriteClaim. Constructor/composition требования ниже синхронизированы; singleton restriction больше не действует.

**Приоритетная граница пользователя:** automatic crash recovery выделен в отдельный этап. Отсутствие доказанного restart quiescence не блокирует независимую штатную authorized запись с настоящими acquisition/full-claim/worker-drain/atomic seal/evidence checks. В штатной поставке process loss либо непроверенная остановка оставляют stage Unresolved; safe retry, выпуск successor и release защищённых holds без proof запрещены. Lost ACK с уже доказанным completion может дать historical Confirmed, но отсутствие completion не доказывает отсутствие effects. Требования ниже к crash-proof относятся к acceptance automatic recovery, не к blanket gate штатного stage. Live cancel/READY/drain guards остаются обязательными для штатной записи.

Приоритет уточнения inventory/retention ниже: конкретные existing callers/factories перечислены; circular ownership quiescence снят в пользу Artifacts; cleanup не разрешает deletion stage evidence. После этого остаток SR-03 — согласование Artifacts реализации единого predicate/representation и предложенных required constructor/scoped seal дельт. Упоминания «inventory ещё требуется» в первоначальном тексте ниже означают необходимость проверки будущего cutover, а не отсутствие текущего списка.

**SR-03: OPEN общей приёмки; конкретная Publication TARGET-граница предъявлена ниже.** AS-IS несовместим с обещанием полного stage drain. Закрытие требует сверки этих портов с параллельным Artifacts resolution и consumer inventory переходов, не просто общего coordinator. Runtime PASS не заявляется. Реализация generator/gameplay, новый DAG route и полный Source/Pack completion OUT.

## Источники / AS-IS

- `backend/app/application/artifacts/staging/artifactStageWriter.py`: write последовательно reserve → backend.write → локальный writer → verify/seal; full-stage claim отсутствует.
- `backend/app/db/repositories/sqlite/artifacts/leaseStore.py`: SqliteArtifactLeases.finish_preparation проверяет catalog._writers, exact holds/sealed, закрывает admission и пишет READY. cancel закрывает admission, ждёт _writers вне write transaction, затем повторно проверяет fence/terminal/writers и снимает holds/пишет terminal. Этого недостаточно для промежутка между backend write и seal.
- `backend/app/db/repositories/sqlite/artifacts/catalogStore.py`: reserve и seal используют SqliteArtifactScope.transaction; seal требует локальный reservation writer и operation hold. Новая generation/completion ими не проверяются.
- `backend/app/db/repositories/sqlite/artifacts/access/artifactScope.py`: bind позволяет scoped storage access; не является разрешением публиковать промежуточный результат.
- `backend/app/db/repositories/sqlite/snapshotCore/commitScope.py`: SqlitePublicationCommitStore.transaction(operation_id: EntityUid) -> AbstractAsyncContextManager[CommitScope], confirmed commit/rollback, quarantine/UnknownCommitOutcome, scope revoke.
- `backend/app/db/repositories/sqlite/shared/capabilities/scopeRegistry.py`: check/operation_id проверяют issued scope, task, connection, lifetime/write authority.
- `backend/app/application/publication/service/operationLedger.py`: operation observation/recover/cancel, не stage-retry decision.
- [Обязательные критерии](../rules/dag-generator-interface.mdc), [правило координации](../rules/interdomain-contract-coordination.mdc), AGENTS.md; [Snapshot ТЗ](../../docs/tz_world_snapshot.md) — transaction/terminal/unknown semantics. Ни факт чтения этих источников, ни эта записка не являются приёмкой всего домена.

## Конкретные TARGET порты

Все нижеследующие additions PROPOSED. Existing OperationLeaseRef, StagingReservation, ArtifactRef, CommitScope/CommitReadScope переиспользуются; public permit/generation/error roster принадлежит Artifacts и здесь не дублируется.

`application/artifacts/storage/stageAttemptStore.py::IStageAttemptStore`:

```python
def claim_stage(self, permit: StageAttemptPermit) -> AbstractAsyncContextManager[StageWriteClaim]: ...
async def seal_stage(self, claim: StageWriteClaim, reservation: StagingReservation) -> ArtifactRef: ...
```

`StageWriteClaim` — issued runtime capability Artifacts; не DTO/node payload, не второй durable token. Exact representation определяет Artifacts. Его lifetime покрывает reserve/write/verify/seal и drain workers до release. Не разрешает bypass operation fence/closed admission.

Дополнительный узкий внутренний lifecycle порт в том же модуле:

```python
class IStageExecutionDrain(Protocol):
    async def is_drained(self, scope: CommitReadScope, operation_id: EntityUid) -> bool: ...
    async def assert_drained(self, scope: CommitScope, operation_id: EntityUid) -> None: ...
```

Owner — Artifacts. Concrete `db/repositories/sqlite/artifacts/stageAttemptStore.py::SqliteStageAttemptStore[R]` реализует оба порта. is_drained возвращает True только после подтверждения отсутствия способности всех stage generations операции продолжать effects; проверяет authoritative full-stage state, не только старые локальные claims. Unknown/corruption не возвращают False/True, а распространяются. assert_drained проверяет тот же predicate в указанном write scope: при подтверждённом busy — existing OperationBusyError; invalid scope/corruption — PublicationInfrastructureError; unknown/cancel без изменения категории. Новый refusal POJO для внутреннего drain не нужен.

TARGET storage primitive `SqliteArtifactCatalog.seal_in_scope(scope: CommitScope, reservation: StagingReservation) -> ArtifactRef` (async) сохраняет existing seal predicates и effects, но НЕ открывает/закрывает transaction и НЕ выдаёт confirmed outcome: возвращённый ref provisional. Existing seal может делегировать ему из собственной transaction; authorized stage вызывает его только из seal_stage. Это не новый public pipeline и не перенос holder SQL в Publication.

Durable completion write остаётся внутри SqliteStageAttemptStore за его seal_stage, в том же scope. Отдельный public completion writer или сериализуемое evidence из Artifacts в Publication не вводится. Method/class владельца evidence назван; внутренний SQL/таблица и отдельный repository не назначаются.

## Constructor graph и authority

Предлагаемый exact concrete constructor:

```python
SqliteStageAttemptStore[R](
    scopes: SqliteArtifactScope,
    operations: SqliteOperationStore[R],
    catalog: SqliteArtifactCatalog,
)
```

Объект использует scopes.commits/access и catalog operationArtifacts; не принимает второй coordinator, callback или independently committing evidence service. При необходимости отдельного persistence collaborator Artifacts обязан предъявить его exact constructor и same-scope binding до принятия, а не добавить молча.

TARGET SqliteArtifactLeases[R] constructor сохраняет scopes/operations/artifacts и получает required keyword `stage_drain: IStageExecutionDrain`; actual SQLite composition допускает только проверенный SqliteStageAttemptStore того же graph. Optional/no-op default запрещён. Не создавать dependency cycle: stage store не зависит от leases/public lifecycle service; owning stage admission использует internal scoped catalog/operation checks.

Fail-fast identities внутри SQLite adapter layer:

- stage_store.scopes is leases.scopes is catalog.scopes;
- общий operations, общий access; operations._commits is scopes.commits; operations._access is scopes.access;
- catalog._operations is operations; catalog._access is scopes.access; catalog._artifacts is operations._artifacts; artifact reader._access is scopes.access;
- access.registry is commits.registry; internal leases catalog имеет тот же scopes/operations/access/artifact reader;
- leases.record_model is operations.record_model is operations.result_binding.record_model; existing codec/store/ledger identity checks сохраняются;
- stage writer, backend admission и lease adapter имеют существующую проверенную identity graph; full-stage store связывается с этой же graph, не с отдельным lease adapter.

Имена private links выше — проверка concrete adapter composition, не public properties нового protocol. Generic writer/Engine/Source их не читает. Same database path/equal DTO недостаточны. Проверять подмену каждого элемента до IO. Scoped methods дополнительно используют registry.check(scope, True) и registry.operation_id(scope); authority не следует из constructor identity одной лишь.

## Порядок и совместимость lifecycle

1. claim_stage consumption: в короткой owning transaction проверить operation/admission integrity, binding/fence/PREPARING/open и актуальный permit, затем зарегистрировать полный execution claim до первого reserve/physical effect. Выдать handle только после confirmed acquisition. Lost ACK acquisition не означает отсутствие claim.
2. Writer выполняет reserve/write/verify/seal в lifetime этого claim. Existing локальные backend/seal claims не удаляются этим предложением; full-stage и локальные claims различаются по роли. Не считать собственный full-stage claim конкурентом при seal; не ослаблять existing reservation-writer predicate.
3. finish_preparation: внутри одной transaction перед READY проверяет И existing локальные writers, И stage_drain.assert_drained(scope, oid), затем exact holds/sealed, close admission/READY. Блокирующего ожидания drain внутри transaction нет. Если stage ещё active — OperationBusyError, не READY. Issued, но ещё не consumed permit сам по себе не active writer: READY может закрыть admission, после чего consumption обязан отказать.
4. cancel: подтвердить close admission в existing первой transaction; ждать оба множества claims вне write transaction. stage_drain.is_drained использует текущий read scope. В финальной transaction повторить terminal/fence, closed admission, локальный drain и full-stage assert_drained ДО release holds/cancel terminal. Новая generation после close не выдаётся/не потребляется. Не добавлять второй background owner: это расширение existing cancel drain loop.
5. Любое разрешённое изменение operation fence и любой путь в READY/terminal, освобождающий stage-protected holds, обязаны использовать тот же scoped drain predicate до перехода. Stale fence сам по себе не доказывает остановку physical worker. Конкретный inventory всех transition callers должен быть сверен перед cutover; существующему recover не добавляется takeover по отсутствию локальных claims.
6. Закрытие admission во время stage запрещает дальнейший seal, но не прерывает cleanup/drain. Full claim выпускается только когда workers остановлены и нет отложенного эффекта. Unknown release сохраняет uncertainty; ни cancel, ни recovery не объявляют quiescence по timeout/отсутствию старых writers.

## Один commit seal / hold / exact completion

seal_stage открывает existing scopes.commits.transaction(binding.lease.operation_id). Внутри: issued claim и exact generation/binding; current operation/admission/fence; reservation/ref; existing live local writer/hold predicates; scoped seal; обеспечение требуемого operation hold; durable exact completion evidence stage/generation/ref в ЭТОМ scope. Completion evidence не является operation terminal и не расширяет PublicationResultBinding[R].

Physical write/verify уже завершены под full claim; SQL transaction не держится на всём IO. После выхода с confirmed commit возвращается ref; затем full-stage context выполняет cleanup. При ошибке до commit rollback отменяет seal/evidence изменения вместе (предшествующая reservation/hold могла существовать и не объявляется отсутствующей). При unknown никакой success/absence/компенсационный release не выводится. Lost ACK после commit восстанавливается по exact Artifacts completion evidence, даже если последующий cancel снял current hold. Post-seal logging fault не отменяет completion.

Запрещено: standalone catalog.seal с последующей записью evidence; две transactions; прямой вызов Publication public recover/stage service из adapter; выдача provisional ref как confirmed; восстановление completion по одному sealed descriptor.

## Inventory затронутых ролей и критерии отказа

| Класс/семейство | Ответственность / допустимая дельта | Отказ при приёмке |
|---|---|---|
| StageAttemptService, StageAttemptPermit и outcomes (Artifacts proposal) | begin/recover decisions, typed binding/generation; roster у Artifacts | Publication-копия POJO/service или evidence boolean без authority |
| IStageAttemptStore / SqliteStageAttemptStore[R] | Full execution authority и atomic seal/evidence, shared transaction infrastructure | Независимый commit evidence, claim gap, callback в другой public pipeline |
| IStageExecutionDrain | Scoped full-stage quiescence | True по отсутствию только локальных claims; скрытый wait/commit |
| StageWriteClaim | Issued runtime lifetime, не durable wire | Forgeable DTO принят как authority; release до worker drain |
| ArtifactStageOpenPipeline / ArtifactStageWriter | Existing linear admission/descriptor/write; full claim вокруг всего stage | Orchestration recovery loop, optional permit bypass |
| ArtifactInputAdmission / ArtifactDescriptorBuilder | Existing pure checks | Новые storage/recovery обязанности |
| ArtifactFormatRegistryBinding / ArtifactFormatContract / ArtifactBackend | Binding/physical IO, existing worker claims/drain | Hot rebind, другой admission graph, скрытая запись completion |
| SqliteArtifactLeases[R] / IArtifactLeases[R] | Operation lifecycle, расширение drain consumer; public signatures finish/cancel не меняются | READY/cancel release при active full-stage claim |
| SqliteArtifactCatalog | Scoped reserve/seal predicates/storage facts | Новый lifecycle decision или собственный commit в seal_in_scope |
| SqliteArtifactHolders / SqliteOperationArtifacts | Existing hold chain/active refs primitives | Fork holder representation либо current refs как completion proof |
| SqliteOperationStore[R] / SqlitePublicationEvidence[R] / StoredTerminalCodec[R] / PublicationResultBinding[R] | Existing operation binding/terminal integrity | Stage evidence как новый terminal R, ослабление existing checks |
| OperationLedger[R] / ArtifactStagingService | Existing operation observation/delegation | Operation recover выдан как stage retry permission |
| SqliteArtifactScope / ScopedSqliteAccess | Same-scope access, scoped binding | Nested owning transaction/foreign scope accepted |
| SqlitePublicationCommitStore / SqliteScopeRegistry / SqliteTransactionDriver / GuardedConnection | Existing transaction/ack/lifetime/quarantine | Второй transaction engine, false confirmation, wait drain под write lock |
| Composition factories и lifecycle callers | Передать единственный graph и required drain | Неучтённый caller/default обход; конкретный caller inventory ещё требуется |

Не все эти классы требуют изменения кода: таблица включает reachable неизменные зависимости и зоны проверки. Конкретные backend specializations и factory consumers перечисляет Artifacts owning resolution; эта записка не выдаёт generic PASS любой регистрации.

## Обязательная приёмка / остаток

### Уточнение owner inventory и retention — 2026-11-26

Сверен [Artifacts owning resolution](artifacts-stage-recovery-owning-resolution.md), §§4–8. **Quiescence после process loss принадлежит Artifacts**: Publication не выдаёт proof по времени, operation phase или отсутствию local claims. Publication предъявляет обязательных consumers этого predicate ниже. Формулировка §8 Artifacts о получении quiescence от Publication не соответствует варианту A; её изменение выполняет владелец того документа.

Все пути ниже относительно `backend/`. Runtime поиск выполнен по `backend/app`, отдельно проверены composition fixtures; строки SQL, допускающие переход, не считаются реализованным caller.

| Concrete caller | Required TARGET full-stage check и последствия |
|---|---|
| `app/db/repositories/sqlite/artifacts/leaseStore.py::SqliteArtifactLeases.finish_preparation` | assert_drained(scope, lease.operation_id) вместе с local writers ДО close/READY в одной transaction. Busy → OperationBusyError, READY не пишется; unknown → propagate, не утверждать отсутствие transition |
| Тот же файл, `cancel` | После confirmed close ждать is_drained и local writers вне write UOW; в финальном UOW assert_drained до hold release и terminal. Busy при recheck → OperationBusyError, без release; unknown → propagate, не compensation |
| Тот же файл, `open_operation` | Новая операция fence=1; existing branch не увеличивает fence и не reopened admission. Не превращать его в stage resume; full claim не снимается. Existing closed replay не означает writable grant |
| Тот же файл, `recover` | Observation; APPLYING/RECOVERY_REQUIRED → existing busy. Не выдаёт новую generation/fence и не освобождает stage claim. Quiescence не выводится из возвращённого record |
| Тот же файл, `_release` / `_cleanup` / `writer` | Это release ЛОКАЛЬНОГО writer claim, не operation hold/full-stage claim. Нельзя требовать full drain перед этим release: возник бы self-deadlock. После local drain full-stage owner продолжает/завершает свой lifetime; unknown local cleanup запрещает объявить full quiescence |
| `app/db/repositories/sqlite/artifacts/holderStore.py::SqliteArtifactHolders.release` — только OperationHolder branch | В borrowed/owning write scope assert_drained(operation_id) после closed/fence check и до append release; сохранить local writer check. Busy → отказ без release; unknown → propagate. ArtifactRetentionHolder release не становится operation cancellation; non-operation ветви не получают фиктивный operation ID |
| Тот же файл, `handoff` | После APPLYING/closed/lease validation и до первого destination append проверить full drain наряду с local writers. Busy → без handoff effects; unknown → propagate outer owner. Existing subset/retention semantics не расширяются |
| Тот же файл, `_release_pin` | Не operation hold; вызов из owning GC/pin cleanup сохраняет собственную authority. Не применяет operation drain по guessed ID; stage evidence не удаляет |
| `app/db/repositories/sqlite/snapshotCore/operations/operationStore.py::SqliteOperationStore.claim_publication` | Перед переходом READY→APPLYING scoped assert_drained. Нельзя полагаться лишь на старую проверку READY producer. Existing terminal/busy replay не меняет claims; для этих ветвей новый drain не prerequisite исторического replay. Busy перед переходом → OperationBusyError; unknown сохраняется |
| Тот же файл, `_save` через `record_terminal` и `record_refusal` | Для НОВОГО terminal assert_drained в том же write scope до terminal/event insert; exact existing terminal replay не требует нынешнего drain. Busy → новый terminal не пишется; unknown → propagate. Это не разрешает record_refusal при unknown rollback |
| `app/application/publication/service/operationLedger.py::claim_publication/record_terminal/record_refusal/cancel/recover` | Delegation к указанным owning stores; второй drain/latest read здесь не добавляется |
| `app/application/artifacts/staging/artifactStaging.py::finish_preparation/recover` | Existing delegation сохраняется; operation observation не заменяет stage recover. Вызов через legacy фасад не обходит новые guards storage layer |
| `app/db/repositories/sqlite/artifacts/catalogStore.py::seal` и proposed `seal_in_scope` | НЕ assert full drained: seal исполняется под собственным active full claim. Authorized путь вместо этого проверяет exact live claim/generation; generic standalone seal не должен стать обходом authorized evidence commit |
| Тот же файл, `mark_deleted` | Existing holds/local writers guards сохраняются; physical artifact GC не удаляет stage binding/predecessor/completion. Full-stage authority должна защищать effects до их reserve/hold; механизм конкретного Artifacts claim остаётся owning contract |

**Fence inventory:** actual `_event` в operationStore.py и trigger `publication_operation_events` в `app/db/migrations/0001_initial.sql` допускают recovery READY с fence+1, но runtime producer такого перехода в проверенном `backend/app` не найден. Нельзя назвать `_event` writer: это validator. Если producer добавляется, обязательны closed admission + full/local drain в том же transaction до bump; busy/unknown запрещают выдачу нового fence. Existing finish_preparation READY сохраняет fence, claim_publication APPLYING также его не меняет.

### Construction без dependency cycle

Для новых guards operationStore/holders требуется отделить read-only drain adapter от stage store, который уже зависит от operationStore. Предыдущее предложение передавать сам stage store всем consumers заменяется этим exact TARGET:

```python
# proposed module db/repositories/sqlite/artifacts/stageExecutionDrain.py
SqliteStageExecutionDrain(access: ScopedSqliteAccess)
# implements IStageExecutionDrain; no operations/leases/service dependency
```

Он проверяет authoritative full-stage state Artifacts через тот же access/scope. Отдельного registry/state machine или второго quiescence policy не вводит: predicate единственный, reused stage store и lifecycle consumers. Artifacts подтверждает его совместимость со своей durable representation; Publication не определяет query/SQL.

Required keyword `stage_drain: IStageExecutionDrain` получают concrete SqliteOperationStore[R], SqliteArtifactLeases[R], SqliteArtifactHolders и SqliteStageAttemptStore[R]; optional/no-op default запрещён. Concrete SQLite checks требуют exact stateless SqliteStageExecutionDrain с тем же access/registry/coordinator graph и единым authoritative predicate; отдельные экземпляры допустимы, mutable state и hot-rebind запрещены. Это явная constructor дельта, не public method signature change. Порядок assembly: scopes/access → drain adapters → operations/catalog → stage store → leases/holders → backend/writer. Так operations не зависит от stage store и цикл не образуется. Поля/методы самого IStageExecutionDrain выше неизменны.

Concrete composition sites:

- `app/core/container/packs.py::PacksWiring.initialize_pack_storage`: existing единственная найденная production сборка operations/leases; создать named scopes и stateless drain adapter(s) на общем access до stores, передать required dependency. Сейчас также содержит старый `StoredTerminalCodec()` без binding — existing отдельная проблема, не разрешение подставить mock production binding. Эта фабрика не доказывает регистрацию authorized stage.
- `tests/snapshotCore/support/fixtures.py::live_database`: общий operations graph — создать drain рядом с access и передать store; fixtures не должны получать fake True drain.
- `tests/snapshotCore/support/artifactFixtures.py::adapters`: holders/catalog используют общий access из test composition; отдельный stateless drain instance допустим при exact implementation и том же predicate/authority graph.
- `tests/typing/snapshotCore/valid.py::sqlite_composition` и constructor expressions SqliteArtifactCatalog/SqliteArtifactHolders/SqliteArtifactLeases в этом файле: отразить required typed dependency, без Any/cast/default.
- Direct test constructors SqliteArtifactLeases в storage/lifecycle tests должны получать тот же реальный drain из test graph. Это миграция тестовых consumers, не ещё одна production factory; обнаружение всех call sites повторить после параллельных изменений перед кодом.

Критерий отказа каждого перечисленного factory: иной access/registry/coordinator, не exact owning drain implementation, mutable drain state/hot-rebind, другой predicate, default bypass или цикл constructors. Различие drain object identity само по себе не является отказом. Backend registration/format factories, не создающие operation stores, лишь reuse готовые leases и не становятся владельцами drain.

### Cleanup и retention: конкретный запрет удаления в этом срезе

В проверенном `backend/app` public operation purge/prune метода не найдено. `0001_initial.sql` содержит no-delete triggers для publication_operations/publication_operation_events. `SqliteArtifactLeases.cancel` снимает holds/добавляет terminal, НЕ удаляет operation history. `_cleanup` завершает execution claim, НЕ удаляет recovery evidence. Physical artifact GC — отдельная lifetime, не основание удалить stage history.

**TARGET обязательство Artifacts:** immutable StageBinding, generation predecessor links и exact completion evidence сохраняются после claim release, cancel, READY, operation terminal и physical artifact GC. Для всех поддерживаемых checkpoint replay этого достаточно для historical Confirmed; нынешний body/hold не обещается. Unknown и absence не смешиваются; отсутствие обязательных сохранённых facts — infrastructure/integrity fault либо owning untracked policy только для действительно никогда не зарегистрированного stage, не «безопасный новый begin» после очистки.

**Кто разрешает deletion сейчас: никто. Контракта deletion authority в этом срезе нет, удаление этих facts запрещено.** Это конкретная disposition, не TTL и не скрытый новый storage. Operation cancellation/terminal/cleanup не являются разрешением. Существующий append-only lifecycle не требует invent purge ради closure SR-03.

Если позднее потребуется удаление, это отдельная принятая cross-owner boundary: checkpoint/replay owner должен необратимо исключить все поддерживаемые ссылки и future resume к stage; Artifacts проверяет отсутствие активной authority/неразрешённого outcome и владеет удалением своих facts; Publication отдельно разрешает удаление operation history только по собственному будущему контракту. Ни одному owner нельзя самостоятельно вывести чужую replay retirement из terminal/возраста. Exact future deletion API здесь намеренно не назначается и не является prerequisite сохранения evidence в текущем срезе.

Следовательно retention compatibility этого среза закрывается правилом **retain, no deletion API**, а не ссылкой на неопределённый operation cleanup. Срок не ограничен новым TTL; изменение этой политики требует отдельного принятого контракта.

Три запрета DAG: новые ноды/порядок не назначаются; решения begin/recover передаются только явным будущим DAG public CALL, Engine не читает storage; внутренние scoped storage методы не выбирают следующую публичную операцию. Public stage input остаётся Artifacts-owned, scope/claim не входят в node POJO. Нет foreign public service calls через adapter.

CRUD: дельта не создаёт настройки/доменное хранилище общего назначения; scoped authority и seal используют owning storage. Новые public begin/recover и ошибки принимаются в Artifacts resolution, не заменяются этим документом. POJO reuse перечислен выше, новый mirror holder/ref/lease/terminal не вводится. Общая доменная CRUD приёмка здесь не заявляется.

Порядок existing stage/cancel/READY сохраняется с обязательным full-stage guard и единой seal/evidence boundary; изменение shared lifecycle consumer semantics требует сверки non-stage consumers. Неустранимые из Publication-части вопросы: (а) Artifacts exact full-stage quiescence proof/claim invalidation при crash и отмене acquisition; (б) совместимость proposed required drain/scoped seal с его конкретным constructor/store design; (в) полный перечень fence/READY/terminal/release callers и отсутствие обхода; (г) persistence representation completion, обеспечивающая тот же scope. Не назначать SQL/новый журнал вместо ответа владельца.

Acceptance evidence будущей реализации: race cancel/READY vs consumption; cancel во время physical IO; active full claim в промежутке без local claims; unknown acquisition/release; lost ACK seal; fault между scoped seal и completion; concurrent recover; foreign graph/scope/claim; old generation worker после fencing; unchanged non-stage lifecycle; ни одного committed seal без exact completion для authorized stage. Это тестовые требования, не замена архитектурной приёмки. До сведения Artifacts resolution и подтверждения всех callers SR-03 целиком OPEN.
