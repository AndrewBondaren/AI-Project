# Artifacts — публичный staging и граница с DAG

Редакция 2026-11-18. **DESIGN OPEN. Первый обязательный этап — ARCH-0: целевая архитектура и её приёмка. До закрытия ARCH-0 реализация последующих этапов запрещена.** Этот документ не является разрешением писать код и не объявляет домен принятым.

## Решения пользователя и источники

### H2-SIG: propagation W/R через Artifacts — 2026-11-20, PROPOSED

Owning дельта для координатора Between domain operations по [H2-SIG](interdomain-refusal-transport-h2.md). Не code-go и не приёмка H2. Заменяет прежнее однопараметрическое предложение store/ledger/конкретных adapters[R]. W — concrete текущий Snapshot write result; R — закрытый набор читаемых Snapshot roots, включающий W. Reader policy legacy root20124 | W остаётся предложением Publication до пользовательской приёмки. D принадлежит result composition и отдельно в leases не передаётся. H3, reuse TimeSectionRefused, Time-owned validator, lease/retention порядок не меняются.

**Actual evidence:** IArtifactLeases.finish_preparation/recover/cancel возвращают bare OperationRecord; SqliteArtifactLeases._record возвращает SqliteOperationStore._load. OperationLedger.recover имеет terminal fast path через store.read и fallback leases.recover. cancel может вернуть ранее сохранённый terminal, а не только OperationCancelled. ArtifactStagingService.cancel повторно валидирует bare OperationRecord. Store создаёт bare OperationRecord, terminal codec фиксирует SnapshotApplyResult. Одних annotations недостаточно для H2.

**Владение:** Publication определяет terminal write/read models, root dispatch, manifest, compatibility и единый construction binding store/ledger/codec[W,R]. Artifacts сохраняет R в operation observations, не выбирает roots и не создаёт второй terminal codec. OperationRecord[R] в existing dataModel/artifacts/lifecycle/operation/record.py сохраняет все поля и общие инварианты; terminal имеет R | PackActivationResult | GameplayStarted | OperationCancelled | None. R — Snapshot roots, а не повторный union всех terminal kinds. Time imports в общем Artifacts/Publication ядре запрещены.

#### Exact signatures — proposed delta существующих модулей

```python
# app.application.artifacts.storage.artifactLeases
class IArtifactLeases[R](Protocol):
    async def finish_preparation(
        self, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]
    ) -> OperationRecord[R]: ...
    async def recover(self, operation_id: EntityUid) -> OperationRecord[R]: ...
    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord[R]: ...

# app.db.repositories.sqlite.artifacts.leaseStore
class SqliteArtifactLeases[W, R]:
    def __init__(
        self, scopes: SqliteArtifactScope,
        operations: SqliteOperationStore[W, R],
        artifacts: SqliteOperationArtifacts,
    ) -> None: ...
    async def _record(
        self, scope: CommitReadScope | CommitScope, operation_id: EntityUid
    ) -> OperationRecord[R]: ...
    # finish_preparation/recover/cancel: signatures идентичны IArtifactLeases[R].

# app.application.artifacts.staging.artifactStaging
class ArtifactStagingService[W, R]:
    def __init__(
        self, registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog,
        leases: IArtifactLeases[R], holders: IArtifactHolders,
        gc: ArtifactGarbageCollector, ledger: OperationLedger[W, R],
        log: ArtifactLifecycleLog, *, record_model: type[OperationRecord[R]],
    ) -> None: ...
    # finish_preparation/recover/cancel: signatures идентичны IArtifactLeases[R].
```

IArtifactStaging[R] в existing application/artifacts/contracts/stagingPort.py имеет те же три result signatures. Остальные методы IArtifactLeases/IArtifactStaging сохраняют existing inputs/outputs. Термин «reader-only leases[R]» означает отсутствие W в surface, а не read-only эффекты: finish/cancel по-прежнему изменяют lifecycle. Concrete SqliteArtifactLeases[W,R] зависит от write/read store и потому сохраняет оба параметра; запись OperationCancelled не превращается в W.

Publication counterpart, согласуемый prerequisite (не самостоятельное переопределение foreign API): OperationLedger[W,R].__init__(operations: IOperationStore[W,R], leases: IArtifactLeases[R]); read(operation_id:EntityUid)->OperationRecord[R]|None; recover(operation_id:EntityUid)->OperationRecord[R]; cancel(operation_id:EntityUid,fence:int)->OperationRecord[R]. Store/codec record_refusal принимает W; read/decode возвращает R с отдельными Pack/Gameplay/Cancelled branches по Publication контракту.

#### Construction, validation и nested calls

- record_model — одна closed concrete specialization, предоставляемая той же Publication composition, что store/codec. Это proposed явная constructor dependency вместо bare OperationRecord.model_validate в staging wrapper; не новый DTO/token/registry. Полные неизменные поля валидируются через record_model, terminal concrete class/operands/category/order сохраняются. _record в lease adapter возвращает уже проверенный store result, не выполняет dict round-trip или old→new adaptation.
- Composition должна проверить W входит в R, закрытость R, совпадение record_model и root/manifest policy у store/ledger/leases/staging adapter. Неподставленные generics и runtime Any/BaseModel не допускаются. Exact механизм проверки shared construction binding должен предоставить Publication; type annotations сами по себе это не обеспечивают. Это внешний OPEN H2-SIG, не обещание готового constructor guard.
- Допустимая к согласованию lifecycle цепочка: OperationLedger[W,R] → IArtifactLeases[R] → SqliteArtifactLeases[W,R] → тот же SqliteOperationStore[W,R]. Ledger не вызывает публичный Artifacts OpenPipeline/ArtifactStagingService; lease adapter не вызывает ledger, Time, Source или Pack. Store/evidence/codec являются узкими infrastructure dependencies; их полная вложенная цепочка требует приёмки координатора.
- Normal apply использует согласуемый узкий IOperationStore[W,R] port. recover/cancel/finish не добавляются в apply ради H2. Internal terminal read/replay не переносится в read_world или предыдущие ноды.

#### Ошибки, проверки и статус переходов

Входы остаются existing OperationLeaseRef, tuple[ArtifactRef,...], EntityUid и положительный fence; новых зеркальных request POJO нет. Existing validation/lease refusals, OperationBusyError, PublicationInfrastructureError, UnknownCommitOutcome и cancellation сохраняют разделение. H2 не объявляет proposed ArtifactLeaseFailure реализованным. Несовместимость composition отклоняется при construction; foreign persisted root/manifest и искажение terminal — Publication-owned infrastructure/contract fault, не Snapshot business refusal. Exact codec compatibility errors принадлежат Publication.

| Переход | Вердикт | Условие закрытия |
|---|---|---|
| Store[W,R] → leases[W,R] → IArtifactLeases[R] | PROPOSED / OPEN | Один Publication binding, record R без пересборки diagnostics |
| Ledger terminal fast path / leases fallback → OperationRecord[R] | PROPOSED / OPEN | Одинаковый R обеих ветвей, включая supported legacy root |
| cancel existing terminal / OperationCancelled → OperationRecord[R] | PROPOSED / OPEN | Нет сужения до cancelled; existing release semantics сохранены |
| Staging adapter[W,R] → IArtifactStaging[R] | PROPOSED / OPEN | Explicit concrete record_model, отсутствие bare model_validate |
| Bare current codec/store → новый W | FAIL для H2 расширения | Дельта Publication codec/store необходима; это не оценка legacy поведения |

Критерии будущей проверки: exact terminal concrete type, operands/category/order после store load, обеих recover ветвей и cancel уже terminal операции; foreign root rejection; constructor binding mismatch rejection; отсутствие повторного handler и old→new adaptation. finish exact holds/seals/READY, cancel fence/drain/release, rollback/unknown semantics неизменны. Новых tests/runtime PASS этим документом не заявляется.

**Остаток:** H2-SIG — подтверждение Publication constructor binding и record_model dependency; H2-DISPATCH/REP/IDS — root dispatch, supported representations/manifest closure и IDs отдельно у владельцев. OperationRecord persistence reachability проверяется до назначения canonical ID; существование runtime model не доказывает сериализацию. Общий H2-документ этой правкой не меняется.

### Уточнение поручения: вернуть контракт Source — 2026-11-18

Ответ «полного публичного контракта нет» является результатом аудита, но не результатом поручения. Artifacts обязан подготовить и вернуть конкретный owning proposal: exact public methods/Input/Result/Error, непрерывную retention guarantee, caller trace, recovery/cleanup и проверяемые критерии. Наличие gaps не перекладывает проектирование Artifacts на Source. Реализованное, принятые решения и новые proposals обозначаются раздельно; предложение не объявляется реализованным или принятым.

**Приоритет над историческими trace ниже:** выбран маршрут DAG → Source preparation → DAG → publication. Любые старые записи про Source check_coverage/collect_for_adoption/adopt внутри Snapshot/Publication UOW отозваны как целевой маршрут. Финальное закрепление target retention и публикация остаются атомарными; отмена старого trace не ослабляет эту гарантию. Source не вызывается из Artifacts/Publication, включая DI/callback. Новые ноды здесь не назначаются.

Обязательный объём возвращаемого контракта:

1. **Protected read.** Artifacts задаёт конкретный публичный read с authority admission, exact descriptor/catalog/seal checks и непрерывной защитой до окончания physical IO. Existing `ReadableBlobBackend.read_verified` и `IArtifactStaging.verify` — примитивы, не готовый публичный контракт. `ArtifactReadInput(ref,holder,max_bytes)` выше не замораживается как достаточный вход: holder identity не является caller authority. Source использует не только BLOB: existing `SourceCaptureRef.artifact` — SQL_ROWS `source.capture-witness`, `SourceCaptureWitness.capture_body` — BLOB `source.capture`. Поэтому отдельно специфицировать typed SQL_ROWS read через existing format binding и BLOB read; не возвращать SQL_ROWS как непроверенный dict и не подменять owning Source POJO новым DTO.
2. **Начальная защита.** Указать, какой authoritative retained set покрывает roots и ещё не раскрытые зависимости до первого Source read; кто и когда фиксирует его lifetime. Root-only hold и последовательность read → acquire обнаруженного ref не принимаются. Artifacts защищает физический retained set; Source вычисляет семантический closure. Доступность зависимостей нельзя предполагать из существования root.
3. **Межфазное удержание.** Описать атомарное закрепление полного переданного Source набора под existing durable holder до освобождения исходной защиты. Переиспользовать operation/holder machinery. Назвать вход/результат/отказы, повтор и recovery, отмену, writers/readers drain, release после подтверждённого исхода. Не обещать вечный hold после cancel или из-за одного факта доставки DTO.
4. **Admission точного кандидата.** Сопоставить existing SourceProofResult(proof,durable_refs), SourceCaptureWitness(capture_uid,world_uid,capture_body), SourceCaptureRef и OperationRecord с требуемой связью exact publication candidate ↔ verified proof/closure ↔ durable удержание ↔ operation/fence. Эти существующие значения по отдельности не доказывают такую связь. Source отвечает за семантическую проверку; Publication — authoritative admission точного кандидата/replay; Artifacts — exact retained refs. Нельзя вводить зеркальный ArtifactsSourceProof, verified flag или выдавать fingerprint за всю гарантию.
5. **Финальная атомарность.** Artifacts предоставляет конкретную внутреннюю scoped retention operation для существующего Publication UOW без собственного commit и без вызовов Source. Publication владеет commit/rollback/unknown outcome и atomic записью publication. Existing IArtifactHolders.handoff ограничен Snapshot-сценарием и не объявляется универсальным готовым контрактом. Требуемые изменения этого binding должны быть точными, а не новым transaction engine.
6. **Concurrency и отказоустойчивость.** Различить independent DAG invocations/connections и внутренние thread workers. Existing scope task/connection/lifetime checks сохраняются. Worker получает immutable данные; живые scope/connection автоматически не передаются. Точный публичный bound/unbound отказ входит в proposal; existing private _require_unbound не считается публичным API.

**Форма возвращаемого результата:** для каждой операции — владелец, concrete class/module, signature, existing/new POJO с полями и отсутствием семантического дубля, ошибки, preconditions, точка фиксации гарантии, effects, replay/cancellation/cleanup, вложенная цепочка. Новые типы в документе помечаются TARGET и не создаются в коде в рамках этого поручения. Чужие недостающие контракты формулируются как точные требования к публичному входу/результату владельца, а не как поручение реализовать storage internals Artifacts.

**Граница возврата:** Source должен получить законченное предложение собственной части Artifacts и явно выделенные адресные вопросы Publication/Source по их публичным контрактам. Нельзя объявлять весь маршрут принятым до ответов владельцев; нельзя вместо предложения собственной части повторно вернуть только список gaps. Критерии проверки: GC на границах catalog/body/read/transfer; исходный release при раскрытии; независимые connections; stale fence и подмена candidate/closure; exact replay; rollback обоих финальных effects; unknown outcome через fresh confirmed connection; cancellation с drain; идемпотентный cleanup без снятия чужих и опубликованных holds. Статический аудит не заменяет runtime evidence.

### Вопросы, блокирующие полный ответ Source — 2026-11-18

Контрактные пункты ниже остаются **OPEN**, кроме явно принятых проектных решений в следующем подразделе. Это вопросы для завершения контракта, а не новое поручение реализации. Внешние ответы требуются только в пределах публичных контрактов владельцев. Собственные вопросы Artifacts агент прорабатывает сам; их нельзя переадресовать Source или пользователю как просьбу спроектировать наш домен. Реестр дополняет ART-Q1…ART-Q8, но выделяет конкретные зависимости ответа Source.

#### Решения по Q1 и Q2 — 2026-11-18

**Q1: чтение в контексте конкретной подготовки — принято пользователем.** Основание доступа отделено от технической защиты чтения. Первый срез ограничен конкретной подготовкой, связанной с operation/world; универсальное чтение от имени произвольного holder не обещается. Основание допуска исходных данных приходит через DAG из публичного результата владельца. Artifacts проверяет его актуальность и соответствие exact ref, затем непрерывно защищает catalog/body до окончания IO. Самостоятельно сконструированные ArtifactHolderRef/OperationLeaseRef не считаются достаточным допуском. После restart требуется новая проверка durable состояния. Отзыв запрещает новые чтения; начатое physical IO должно завершиться либо быть прервано с drain до освобождения защиты. Живые connection/scope/guard через DAG не передаются. Новый универсальный token этим решением не вводится.

Проектное направление Q1 принято; exact публичный контракт допуска, отзыва и восстановления остаётся предметом адресного вопроса Lifecycle. Artifacts самостоятельно проектирует reader, проверки и ошибки на основании owning ответа. Пользователь явно поручил после фиксации отправить вопрос в существующий чат Lifecycle.

**Запрос отправлен 2026-11-18** в существующий чат **Lifecycle** (`01a1e936-4dfc-7d73-aede-dbfd4d988d81`). Запрошены: предварительная сверка собственных контрактов, exact public method/Input/Result/Error допуска, authoritative binding и stale/revoked checks, cancellation/restart/unknown outcome, границы Lifecycle/Publication/Artifacts и caller trace без скрытых междоменных вызовов. При отсутствии existing API требуется минимальный owning proposal. Ответ ожидается; отправка не означает согласование. Изменения кода и чужих доменов не поручались.

**Q2: удерживать исходный набор целиком — выбранное направление, поддержано Source по сообщению пользователя.** До первого чтения защищается весь допущенный исходный набор, покрывающий roots и допустимые зависимости. Source вычисляет точный семантический closure; Artifacts не извлекает его из Source payload. Защита исходного набора непрерывно сохраняется до подтверждённого durable закрепления итогового closure под удержанием подготовки. Затем допускается освобождение только временной защиты данного выполнения, а не чужих исходных holds. При отмене cleanup следует подтверждённому lifecycle outcome; при unknown outcome сначала reconciliation.

Ref вне допущенного исходного набора не читается молча и не удерживается постфактум как исправление окна GC: требуется явный отказ либо отдельно согласованное расширение покрытия через DAG. Такое расширение пока не принято. Выбор Q2 закрывает альтернативу стратегии защиты, но не exact публичную операцию получения набора, доказательство его покрытия, binding и lifecycle lifetime. Эти детали Q2/A2 остаются OPEN.

#### Междоменные согласования

| ID | Точный вопрос | Владелец ответа | Что требуется для закрытия / что блокируется |
|---|---|---|---|
| SRC-ART-Q1 — read authority | Какая публичная операция выдаёт контекст, позволяющий данному вызову читать exact refs, и как её результат связывает world, operation/fence и исходный retention owner? Каковы отзыв, срок действия и проверка после restart? | Publication/Lifecycle — operation authority; Source — требуемые исходные roots и owning provenance. Artifacts задаёт собственный admission на основании этих фактов | Exact method/Input/Result/Error и соответствие полей входу read. Одного ArtifactHolderRef/OperationLeaseRef как самостоятельно сконструированного значения недостаточно. Блокирует authority-поля public read и классификацию NOT_AUTHORIZED/stale |
| SRC-ART-Q2 — исходное покрытие | Какой гарантированно удерживаемый набор содержит roots и все зависимости, которые Source может обнаружить? Какая публичная операция предоставляет этот набор или гарантирует его покрытие, и до какого события запрещено его освобождение? | Source — семантика исходного покрытия и допустимых зависимостей; владелец исходной публикации/подготовки — публичная гарантия lifetime. Artifacts — механизм защиты | Подтверждённые preconditions до первого чтения и отказ при отсутствующем покрытии. Root-only hold не закрывает вопрос. Блокирует безопасное раскрытие неизвестного closure, но не разрешает Artifacts вычислять Source closure |
| SRC-ART-Q3 — read/preparation boundary | Какой exact публичный вход Source preparation принимает защищённые прочитанные данные? Если следующий ref становится известен лишь после decode, какой публичный результат Source возвращает DAG для следующего чтения, сохраняя выбранный порядок и защиту? | Source — Input/Result/Error preparation и семантика запроса дополнительных данных; DAG — согласование порядка публичных вызовов, без назначения нод Artifacts | Caller trace для BLOB и SQL_ROWS, включая многошаговое раскрытие, либо подтверждение достаточного единовременного входа. Блокирует окончательный стык Artifacts read → Source; прямой Source → Artifacts callback не считается ответом |
| SRC-ART-Q4 — exact candidate evidence | Какой публичный результат Source связывает проверенные proof/closure с точным публикуемым candidate, и какой публичный вход Publication принимает и авторитетно проверяет эту связь без повторного вызова Source? Какие части existing SourceProofResult/SourceCaptureWitness/SourceCaptureRef используются и где хранится подтверждённая связь? | Source — семантическое evidence; Publication — admission/replay; Artifacts — exact refs и удержание | Exact POJO/imports, persisted binding, правила stale/подмены/точного replay. Bool, hash или DTO construction не заменяют admission. Блокирует безопасное использование closure для конкретной публикации |
| SRC-ART-Q5 — final transaction boundary | Какая публичная publication-операция атомарно принимает подготовленный candidate и закрепляет target retention? Какой существующий scoped infrastructure contract она предоставляет Artifacts, какой target owner фиксируется и кто подтверждает результат commit? | Publication/Snapshot — публичная операция и UOW/capability; Artifacts — предложение scoped retention binding | Exact public Input/Result/Error и согласованный внутренний scoped port без самостоятельного commit/Source calls. Разделить confirmed rollback и UnknownCommitOutcome. Блокирует окончательную сигнатуру transfer и гарантию atomic retention + publication |
| SRC-ART-Q6 — lifecycle/recovery | Какими публичными операциями caller восстанавливает exact candidate/retention после restart или неизвестного исхода, отменяет подготовку и получает подтверждение допустимости cleanup? Как concurrent cancel упорядочен с публикацией? | Publication/Lifecycle; Artifacts описывает условия release своего retained set | Existing или owning-proposed method/Input/Result/Error, terminal состояния, fence/replay, правило сохранения holds до reconciliation. Блокирует обещание межфазного lifetime и безопасное освобождение |
| SRC-ART-Q7 — invocation scope | Допускают ли публичные entry Source/Artifacts borrowed scope или требуют unbound entry? Какой публичный отказ соответствует несовместимому scope и как выдаются независимые connections конкурентным invocations? | Publication infrastructure — capability/connection policy; Source и Artifacts — публичные entry; DAG — invocation/cancellation context | Явная policy с task/connection/lifetime, отменой и запретом автоматической передачи scope в workers. Блокирует final preconditions/errors; существование private guard/bind не является согласованием |

#### Вопросы, которые обязан закрыть сам Artifacts

| ID | Собственный вопрос | Требуемый результат |
|---|---|---|
| SRC-ART-A1 — read API | Как оформить protected BLOB read и typed SQL_ROWS read без зеркал owning моделей, с exact authority input после Q1 и ограничениями bytes/rows? | Concrete public classes/modules/methods, полные Input/Result/Error; таблица повторного использования existing POJO; physical integrity/SQL_ROWS consistency guarantee, budget и disposition настроек. Не объявлять один BLOB reader достаточным для Source |
| SRC-ART-A2 — непрерывная защита | Какая операция Artifacts фиксирует начальную защиту из Q2 и атомарно переносит полный переданный Source набор под existing durable holder до release? | Конкретный public retention API и scoped internals, exact набор refs, acquire-before-release в одном подтверждённом UOW, rollback/replay; никакого нового holder engine и семантического traversal Source |
| SRC-ART-A3 — evidence boundary | Что именно Artifacts проверяет при принятии evidence Q4 и чего не проверяет? | Проверка exact catalog/seal/refs/holder/operation/fence, отличие от Source semantics и Publication admission; никакого универсального verified flag или зеркального proof DTO |
| SRC-ART-A4 — errors и binding | Какие существующие ошибки переиспользуются, какие TARGET leaf POJO действительно нужны, и какие внутренние классы обеспечивают admission/read/transfer? | Полный field/logic error mapping без перекрытия с existing ArtifactLeaseFailure/read errors; ответственность/dependencies/effects каждого класса. Fault/unknown outcome/cancellation не маскируются expected refusal |
| SRC-ART-A5 — проверяемость | Как доказать гарантии на независимых connections, при GC, cancellation и restart, а не только в одной task? | Сценарии с точками остановки до/после catalog read, body IO, retention commit и publication commit; stale/replay/rollback/unknown outcome/cleanup; критерии результата для каждого. До реализации это test design, не утверждение о пройденных тестах |

**Порядок закрытия:** параллельно проработать A1/A4 на existing типах и получить Q1–Q3; затем завершить A2 по Q2/Q6 и admission boundary A3 по Q4/Q5; Q7 применить ко всем entry; завершить A5 и единый caller trace. Это порядок уточнения документа, не изменение утверждённого runtime-порядка действий. До внешних ответов можно вернуть конкретный proposal собственной части с обозначенными зависимостями; полный согласованный контракт нельзя объявлять готовым. Статус отправки адресных запросов фиксируется отдельно; согласие владельцев не подразумевается из отправки.

### Согласование с Pack — 2026-11-18

По переданному пользователем результату Pack считает публичные `prepare_stage` и `stage` достаточными для подготовки descriptor и staging готовых BLOB bytes. **Согласован только этот срез потребности Pack**, не весь API Artifacts, ARCH-0 или реализация. Эта запись уточняет последующие исторические OPEN-пометки: достаточность двух операций для данного BLOB-сценария больше не открытый вопрос; полный маршрут ART-Q1 остаётся открытым.

Pack выдаёт готовые bytes через DAG и получает ArtifactRef. Семантика payload, metadata и manifest остаётся Pack-owned. Прямых вызовов публичного Artifacts API из Pack нет. Stage не подтверждает Source closure, READY или наличие hold в момент доставки ответа; эти гарантии устанавливают соответствующие публичные операции владельцев.

Оставшиеся требования полного маршрута фиксируются отдельно:

| ID | Требуемый публичный контракт | Граница согласования |
|---|---|---|
| PACK-ART-READ | Bounded verified read: concrete Input/Output/Error, exact ref/bytes, гарантированная защита артефакта на время чтения | Artifacts проектирует публичный read; Pack подтверждает достаточность результата. Existing storage read port сам по себе не закрывает требование |
| PACK-ART-ADOPT | Adoption унаследованных refs: проверка полномочий и удержание полного closure | Совместный публичный контракт соответствующих владельцев; не добавлять эту гарантию stage и не выводить полномочия из одного ArtifactRef |
| PACK-ART-COMPLETE | Завершение подготовки, подтверждённый READY и точный replay кандидата | Совместно с Publication/Lifecycle и Pack; отдельный от stage контракт, без повторной сборки candidate по предположению |
| PACK-VERSION-OWNER | Соответствие wire/storage версий Pack правилу владения версиями DAG | Отдельное уточнение Pack/DAG. Записанные в ТЗ Pack значения не являются новым требованием к Artifacts и здесь не переутверждаются |

Эта фиксация не назначает новые ноды, версии, DTO соседних доменов или внутренние storage-механизмы. Следующий собственный публичный контракт Artifacts для проработки — PACK-ART-READ.

**Приоритет редакций:** раздел «Предложение Artifacts: публичный срез V1.1» ниже заменяет предварительные stage-specific failures и запросы другим доменам проектировать `_lease`, storage classification и logging. Эти вопросы решаются внутри Artifacts. Исторические записи исследования ниже не являются действующими внешними требованиями. Завершённость предложения среза не означает пользовательскую приёмку ARCH-0 всего домена, реализацию или закрытие CRUD.

## Предложение Artifacts: публичный срез V1.1

### PACK-ART-READ — публичное bounded verified чтение (проект 2026-11-18)

**Статус: CONTRACT PROPOSAL, не принят.** Физическое bounded read и GC exclusion существуют; generic публичная authority admission не существует в проверенном контуре. Ниже конкретная форма операции и guarantees, а не обещание готовой универсальной авторизации. Новые public ноды не назначаются.

**Existing evidence:** `application/artifacts/contracts/blobRead.py::ReadableBlobBackend.read_verified(ref, *, max_bytes) -> bytes`; `storage/artifacts/blobBackend.py::ContentAddressedBlobBackend`; `storage/artifacts/blobRead.py::read_verified_file` проверяет точный размер/SHA-256 и читает не более descriptor.nbytes плюс один контрольный байт. `db/repositories/sqlite/artifacts/access/artifactScope.py::SqliteArtifactScope.guard` удерживает database writer coordinator на время IO, не reentrant. `SqliteArtifactHolders.is_held` проверяет membership, не caller authority. Pack `PinnedManifestGuard` отдельно проверяет PinIntent через ExecutionPins.hold_open: store/execution/invocation/logical_read_key/pin/world. Замена этого протокола одним PinHolder была бы ослаблением.

#### Public API и POJO

TARGET concrete `application/artifacts/read/artifactReadOpenPipeline.py::ArtifactReadOpenPipeline`; интерфейс `application/artifacts/contracts/artifactReadOpenPipeline.py::IArtifactReadOpenPipeline`:

```python
async def read_verified(self, request: ArtifactReadInput) -> ArtifactReadOutput: ...
```

TARGET `dataModel/artifacts/read/read.py`, strict/frozen/extra-forbid:

- `ArtifactReadInput`: `ref: ArtifactRef`, `holder: ArtifactHolderRef`, `max_bytes: Annotated[StrictInt, Field(gt=0)]`.
- `ArtifactReadOutput`: `request: ArtifactReadInput`, `payload: bytes`.

Input задаёт exact artifact и предъявленный holder, а не право доступа. Output связывает verified bytes с полным прочитанным запросом; `result.request.ref == request.ref`, `len(payload) == ref.nbytes`, digest совпадает. Это immutable bytes, не путь/stream/backend/callback. Нет domain decode, latest lookup, rebake, auto acquisition, нового durable read receipt или token.

Output не дублирует semantic Pack result: existing `VerifiedManifestBytes(ref,payload)` сейчас дополнительно следует за Pack decode/manifest admission в PinnedManifestReader. Новый output описывает только protected physical read и request/budget, не корректность manifest. Existing VerifiedArtifactRef(ref,holder) не содержит bytes и не является авторизацией. Полное сравнение с planned read DTO обязательно до freeze; создавать универсальные aliases на Pack types нельзя.

#### Admission и гарантированная защита

Trusted composition задаёт доступный набор BLOB formats/versions и положительный верхний лимит bytes. Эффективный limit = min(request.max_bytes, composition limit); ref.nbytes проверяется до allocation/physical IO. Caller не может увеличить trusted limit. Численное значение не назначается; configuration/CRUD disposition остаётся ART-Q6. SQL_ROWS этой операцией не читается.

Порядок одной операции: structural admission → kind/format/version/budget → authoritative admission предъявленного holder в контексте текущего разрешённого вызова → в единой непрерывной защите exact catalog descriptor/seal/hold → bounded physical read/hash/size → сформировать output → освободить guard. Ни предварительная проверка ref, ни presence любого holder не заменяют authority admission. Пока backend выполняет IO, guard не отпускается; при cancellation сначала drain physical read, затем release. Защита гарантируется до завершения physical read, не после доставки output. Возвращённые bytes остаются usable после release, но повторное обращение к storage требует новой admission.

Текущий SQLite guard — writer transaction across IO, а не бесплатный per-ref lock. Он блокирует конкурирующие writer operations; latency/throughput не обещаются. Внешние изменения файлов вне managed storage этим протоколом не предотвращаются, corruption обнаруживается hash/size. Уже удерживаемый внешний guard нельзя оборачивать вторым guard: existing bind/guard не reentrant.

**Authority blocker:** Input из ref/holder/limit не переносит existing PinIntent identity. Поэтому эта signature ещё недостаточна для полной замены Pack pinned read. До freeze нужно определить конкретный публичный authority input/result с владельцем существующих execution pins, обеспечивающий exact store/execution/invocation/logical read/world/pin binding, проверку closed/revoked и lifetime на всё чтение. Не передавать внутренний PinIntent, CommitScope или guard callback через DAG; не вводить самодельный proof/token. Нельзя просто объявить typed holder capability. Для operation/snapshot/publication/retention holders нужны собственные exact public admissibility guarantees; предложенный generic union не означает поддержку всех вариантов. До принятия конкретного authority mapping соответствующая specialization не регистрируется. Artifacts сохраняет ответственность за собственный admission; чужой публичный контракт предоставляет необходимые owning facts/guarantees, не проект storage internals.

#### Ошибки

TARGET `dataModel/artifacts/read/readErrors.py::ArtifactReadRefusal` с полями `request: ArtifactReadInput`, `reason: ArtifactReadReason`; enum `UNSUPPORTED_FORMAT`, `BUDGET_EXCEEDED`, `NOT_FOUND`, `UNSEALED`, `HOLD_MISSING`, `NOT_AUTHORIZED`. TARGET carrier `application/artifacts/read/readErrors.py::ArtifactReadRejected(refusal)`; не ValueError и не второй result union. Неподдерживаемый kind относится к UNSUPPORTED_FORMAT. Budget refusal сравнивает nbytes с effective limit до IO; для диагностик limit добавляется отдельным обязательным полем только budget leaf при финальном POJO freeze, не nullable универсальной корзиной. Эта детализация и exact authority refusal mapping остаются частью review, не runtime реализацией.

Malformed input использует existing validation structural issues через ArtifactInputRejected без копирования field schema. Expected отсутствующий catalog/hold при допустимом запросе — refusal. Если owning accepted binding гарантирует наличие, его consumer обязан трактовать такой отказ по своему публичному контракту как нарушение гарантии, не fallback на latest. Descriptor collision → ArtifactDescriptorConflictError; physical size/hash mismatch → existing CorruptBlobError; отсутствующий physical blob при catalog sealed, IO failure, broken chains → PublicationInfrastructureError. Не превращать fault в NOT_FOUND/NOT_AUTHORIZED. UnknownCommitOutcome/CancelledError сохраняются. Read не вызывает repair, retry, cancel или lease release.

#### Ответственность и интеграция

ArtifactReadOpenPipeline выполняет только порядок вызовов admission/protected reader и перенос результата. Existing ReadableBlobBackend владеет bounded physical bytes/hash, catalog/holders — фактами хранения; authority admission проверяет owning binding. Запуск чужого public pipeline из admission/DI/callback запрещён. Exact внутренний admission класс и полный authority dependency closure должны быть предъявлены до реализации — их отсутствие сейчас блокер, не разрешение скрытого междоменного вызова.

Public маршрут: owning Pack/Publication read context → DAG → ArtifactReadOpenPipeline → DAG → owning Pack/Time decode. Producer контекста и exact matching signatures ещё должны быть согласованы. Pack semantic decode остаётся у Pack. Existing PinnedManifestReader нельзя механически заменить: он совмещает pin admission, physical read и semantic decode, а его cache admission — отдельная ответственность, не дополнительная ветвь нового reader.

Проверки: oversize до physical IO; unknown format; wrong owner/execution/world; closed pin; точный ref против подставленного descriptor; concurrent release/cancel/GC до и во время read; independent DB connections; read cancellation с drain; truncated/extra/hash mismatch; IO fault отдельно от expected absence; отсутствие domain decode и повторного log. Public read не объявляется готовым до authority freeze и этих проверок.

**Вывод:** требования по bounded IO и protection определены, конкретная public форма предъявлена, но PACK-ART-READ остаётся OPEN из-за authority input/lifetime и final refusal POJO. Это выявленная контрактная зависимость, а не право ослабить existing Pack admission.

### Предоставляемые операции

Пути относительно `backend/app`. Все новые классы/типы — TARGET. Public interfaces содержат те же signatures, что concrete classes; executable dependencies задаются composition, не передаются через DAG.

| Concrete public class / модуль | Метод | Input → success | Declared errors |
|---|---|---|---|
| ArtifactPrepareStageOpenPipeline[C], application/artifacts/staging/artifactPrepareStageOpenPipeline.py | `def prepare_stage(self, request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]` | content → тот же content + ожидаемый ArtifactRef descriptor | ArtifactInputRejected; ArtifactCodecError |
| ArtifactStageOpenPipeline[C], application/artifacts/staging/artifactStageOpenPipeline.py | `async stage(self, request: ArtifactStageInput[C]) -> ArtifactRef` | lease + prepared → sealed ref, равный descriptor | ArtifactInputRejected; ArtifactLeaseRefused; existing OperationBusyError, PublicationInfrastructureError (включая специализированные codec/storage faults), UnknownCommitOutcome; CancelledError |

Интерфейсы IArtifactPrepareStageOpenPipeline/IArtifactStageOpenPipeline находятся в одноимённых модулях `application/artifacts/contracts/`. Existing immutable ArtifactFormatContract[C] и поддерживаемая version связываются в composition; prepare и stage обязаны иметь одинаковый binding. BLOB specialization — bytes, SQL_ROWS — concrete owning frozen model. Generic BaseModel не допускается как фактический registered payload. Binding errors отклоняются при composition, не исправляются выбором другого формата.

POJO в `dataModel/artifacts/staging/preparedArtifact.py`: ArtifactPrepareStageInput[C](content:C), PreparedArtifact[C](content:C, descriptor:ArtifactRef). В `staging/stageInput.py`: ArtifactStageInput[C](lease:OperationLeaseRef, prepared:PreparedArtifact[C]). Все strict/frozen/extra-forbid; content deep immutable по existing validate_immutable. PreparedArtifact — временный runtime envelope, не persisted payload и не capability.

**Identity admission:** новый input/envelope не сериализует content и не заменяет существующий concrete instance. Валидация nested content выполняется проверкой его concrete schema/immutability с сохранением исходного admitted экземпляра, по существующему принципу Engine ContractValidator. Для новых wrapper-моделей instance-preserving validator явно возвращает проверенный исходный объект; model_construct и безусловное доверие экземпляру запрещены. Диагностическая validation может создавать временные объекты, но возвращаемый content остаётся исходным. Для bytes identity также проверяется. Это ответственность Artifacts, не требование к соседу изменить revalidate_instances его модели.

**Pure prepare:** без IO, lease, holds, registry mutations и domain calls. Внутренняя реализация применяет fixed pure codec/row_count и existing content digest, возвращает descriptor. **Stage:** сначала проверяет input и пересчитывает полный descriptor тем же внутренним алгоритмом, затем reserve → backend.write → seal. Не вызывает public prepare. При несовпадении descriptor до IO — input refusal. Точка гарантии — confirmed commit seal при live writer claim и operation hold. Existing service освобождает claim до return, поэтому concurrent cancel может снять hold ещё до доставки результата caller. Ref подтверждает состоявшийся seal, но не наличие hold в момент return; publication обязана выполнить собственный authoritative admission.

Повтор stage допустим только пока lease writable: reused content identity не заменяет проверки. READY/closed не позволяет повторный stage; replay completed preparation принадлежит публичному lifecycle-владельцу. При partial write могут остаться удерживаемые данные. CancelledError распространяется после drain; unknown outcome не становится refusal или success.

### Единые ошибки Artifacts: внутреннее решение

InputRejected и field roster из раздела ошибок ниже сохраняются. Никаких ArtifactStageFailure/ArtifactStageRefused/stageFailure.py не создавать: предварительное предложение отозвано.

Единственный TARGET logic POJO `dataModel/artifacts/lifecycle/leaseFailure.py::ArtifactLeaseFailure`:

- `lease: OperationLeaseRef`;
- `requirement: ArtifactLeaseRequirement` со значениями WRITABLE/CLOSED;
- `code: ArtifactLeaseFailureCode`: OPERATION_MISSING, BINDING_MISMATCH, FENCE_MISMATCH, LEASE_ABSENT, PHASE_NOT_WRITABLE, ADMISSION_CLOSED, ADMISSION_OPEN.

Strict/frozen/extra-forbid, без повторения identity-полей lease. Валидатор совместимости: PHASE_NOT_WRITABLE/ADMISSION_CLOSED допустимы только для WRITABLE, ADMISSION_OPEN — только для CLOSED. TARGET carrier `application/artifacts/lifecycle/leaseErrors.py::ArtifactLeaseRefused(failure: ArtifactLeaseFailure)` валидирует POJO, наследуется от Exception, не ValueError, не логирует и не пишет terminal. Stage и другие Artifacts consumers передают его без stage-wrapper.

Authoritative порядок внутри Artifacts: load/validate operation → missing → сравнение world/kind/fingerprint → сравнение fence → проверка полной persisted admission chain → требуемый режим. Corrupt chain/invalid persisted values дают infrastructure fault, а не ожидаемый refusal. Полное отсутствие chain даёт LEASE_ABSENT: существуют direct-publication операции без staging. Если конкретный persisted workflow обещает обязательную chain, нарушение его гарантии трактуется этим workflow как infrastructure inconsistency. Последний event fence, несовместимый с current operation fence при корректном requested lease, — corruption. WRITABLE требует PREPARING/open; CLOSED требует closed, но сам не утверждает READY/APPLYING или drain.

Это единый внутренний протокол для reserve/seal, leases open/assert/writer/read/finish, holders release/handoff и climate retention. Их изменение выполняется одним согласованным implementation-срезом, включая fixtures/catches; внешним доменам не поручается проектировать `_lease`.

**Категории fault уточнены:** широкий ArtifactIntegrityError отозван. Existing CorruptBlobError сохраняет исходное наследование PublicationInfrastructureError и смысл verified bytes mismatch. TARGET `application/artifacts/errors.py::ArtifactDescriptorConflictError(PublicationInfrastructureError)` — одна content-address identity с противоречивым catalog descriptor; `ArtifactStorageInvariantError(PublicationInfrastructureError)` — потеря внутренних reservation/hold/claim при действующем lease; `ArtifactCodecError(PublicationInfrastructureError)` — ошибка codec/binding, включая повторный backend encoding mismatch после admission. Ни storage invariant, ни codec fault нельзя автоматически отображать в SOURCE_CORRUPT. Соседям предъявляются публичные категории, не правила устройства их reader.

Перед классификацией отсутствующих reservation/hold/claim проверяется lease в том же scope: доказанный cancel/fencing → ArtifactLeaseRefused, действующий lease → ArtifactStorageInvariantError. Storage OSError нормализуется в PublicationInfrastructureError с cause. UnknownCommitOutcome и CancelledError не маскируются. GC сохраняет собственный GcReport.

**Codec boundary:** BLOB в новом пути — уже canonical bytes owning producer, identity encoding без semantic decode соседнего домена. Existing Pack manifest_format вызывает decode_manifest внутри encode и не считается автоматически совместимым binding: semantic admission должен быть гарантирован публичным producer до передачи в Artifacts. SQL_ROWS codec принимает конкретный уже admitted payload и детерминированно возвращает bytes; row_count — strict int >=0. Builder ограничивает try/except именно callback encode/row_count: каждый обычный Exception нормализуется в ArtifactCodecError с cause; неверный output type также ArtifactCodecError. BaseException не перехватывается. Input/schema checks находятся вне этого блока; callback ValueError не превращается в input refusal. Если codec имеет ожидаемые semantic/budget отказы, его нельзя подключить до согласования отдельного owning admission: универсальная совместимость existing callbacks не заявляется. Состав concrete bindings и их приемлемость — собственный незакрытый FORMATS gate Artifacts.

**Logging:** pure prepare не имеет IO и не пишет лог. Field refusal переносится существующей validation/diagnostics политикой; новый повторный emit не вводится. Storage adapters не логируют rethrow. Stage boundary единожды сообщает lease refusal через existing ArtifactLifecycleLog: TARGET LEASE_REFUSED, optional lease_failure:ArtifactLeaseFailure в existing ArtifactLogRecord (обязателен ровно для этой activity), emit_lease_refusal(failure), WARNING без traceback. Requested operation/world/fingerprint берутся из lease, отсутствующие publication/artifact facts не выдумываются. Infrastructure/unknown логируются owning fault boundary как ERROR с исходным exception; не превращаются в LEASE_REFUSED. Carrier не логирует; повторный emit того же исхода выше по стеку запрещён. Sink failure не меняет outcome, existing UnknownLogConsumerError fail-fast сохраняется. Дельта logging ТЗ входит в реализацию, а не поручается другому домену.

### Ответственность новых внутренних компонентов

TARGET `application/artifacts/staging/artifactDescriptor.py::ArtifactDescriptorBuilder[C]` содержит pure алгоритм encode/digest/row_count, использует fixed contract и existing canonical primitive. Public pipelines зависят от этого внутреннего job, но не реализуют hash/codec. Нарушение — IO, выбор доменной стратегии либо запуск соседней операции. TARGET `application/artifacts/staging/artifactAdmission.py::ArtifactInputAdmission[C]` проверяет input/schema/immutability/binding, агрегирует field diagnostics через существующие helpers, сохраняет instance identity; не открывает lease и не выбирает retry. Нарушение — side effect или копирование payload ради транспорта.

Оба публичных pipeline владеют только линейным порядком одной операции и передачей typed результата/ошибки. Existing registry/backend/catalog/lease/holder/GC роли из реестра ниже сохраняются. DTO/enums имеют только validation; exceptions только carrier/category. Замена hash/backend при неизменном контракте не требует изменения DAG. Нет второго публичного TypedArtifactStager: existing алгоритм переиспользуется/переносится во внутреннюю реализацию на cutover, не остаётся обходным entry доменных callers.

### Требования к другим доменам — только публичные контракты

| Владелец | Что Artifacts получает/предоставляет через DAG | Требуемая публичная гарантия |
|---|---|---|
| Time и другие producers | Получаем конкретный immutable content; для Time это encoded bytes | Successful owning preparation/encode; согласованный формат, никакого lease/hash/storage writer от Time. Одна и та же content-ссылка передаётся prepare_stage и stage |
| Publication initial opening | Получает наш descriptor плюс собственную start identity; возвращает writable OperationLeaseRef либо existing completed-result/refusal | Lease соответствует preparation/world/kind/fingerprint; READY не выдаётся как разрешение stage; concrete result позволяет DAG выбрать дальнейшую операцию |
| Publication initial registration | Получает тот же lease, stage ref и start identity | Success означает проверенную exact registration и завершённую подготовку; no partial success; replay/refusal/unknown outcomes явно различимы; stage ref сам по себе не доказывает semantic identity |
| Publication Pack completion | Получает agreed prepared refs/lease и собственный публичный input | Success READY подтверждает полный принятый retained set, включая необходимые Source dependencies; failure не оставляет частично завершённую подготовку. Внутренние transaction/scoped методы в требования не входят |
| Pack | Передаёт canonical manifest content, получает наш descriptor/ref | Pack проверяет свой состав и соответствие manifest, candidate выдаётся после подтверждённого completion; content/descriptor corruption сохраняет отличие от codec/storage invariant faults |
| Source | Прямого публичного вызова из Artifacts нет | Его публичные данные/результаты и гарантии удержания согласуются с потребителем completion через DAG; Artifacts не требует конкретного resolver/SQL/UOW устройства Source |
| Engine DAG | Получает конкретные input/output/error types двух операций | Согласованный in-memory маршрут сохраняет content identity; выбирает open/replay/stop/retry по public result, не вызывает reserve/seal/скрытые storage APIs |

Требования к соседям не назначают им SQL, helper classes, scopes, carriers чужого домена и алгоритм хранения. Все ранее отправленные просьбы спроектировать Artifacts lease errors/descriptor/integrity/logging отозваны как внешние требования; полученное исследование использовано в собственном решении выше. Для согласования теперь предъявляется эта редакция публичного среза.

### Что завершено и что не объявлено принятым

Основные решения descriptor до lease, ответственности и shared lease-carrier предложены; полнота codec/consumer/logging/class/POJO inventory ещё не доказана. Предложение не является завершённой архитектурой. Не требуется повторно спрашивать соседей, как устроить эти механизмы Artifacts. Проверки реализации: instance identity включая revalidation, no IO prepare, descriptor mismatch до reserve, stale/closed modes во всех callers, cancel/drain, integrity отдельно от unavailable, no duplicate logging, retry только по writable lease.

Пользовательская приёмка V1, exact foreign public signatures и совместная DAG-карта остаются отдельными gates. Полные CRUD/read/settings и общий class/POJO closure домена остаются в ART-Q4…Q6: этот срез их не закрывает. Нельзя объявлять весь Artifacts ARCH-0 принятым на основании двух публичных методов. Код не изменён, runtime checks не выполнялись.

**Вариант 1 принят пользователем 2026-11-17 («Давай 1»).** Artifacts предоставляет две самостоятельные публичные операции для DAG: pure `prepare_stage` вычисляет descriptor и возвращает prepared объект с той же ссылкой на content; `stage` принимает lease и этот prepared объект, выполняет reserve/write/seal. Publication открывает и завершает preparation. Это решение заменяет прежнее предложение единственного stage(lease, content); не означает приёмку всех типов ошибок, foreign-контрактов или реализацию. Далее действует редакция двух операций.

**Дополнение решения пользователя, 2026-11-17:** INITIAL-REGISTER переводится на сохранённый ref после отдельного публичного staging через DAG; прежняя bytes-входная форма registrar подлежит нормативному пересмотру. Это принятие границы, не exact нового Input/Output/Error. Требуется согласовать открытие INITIAL_STATE_PREPARATION/lease, identity и format admission, защиту staged ref, атомарную регистрацию/завершение подготовки, replay и cleanup. Time остаётся владельцем pure preparation/encode/decode, registrar не вызывает Time/World. До согласования конкретного протокола прежний accepted bytes-input в Snapshot читается как исходный контракт под замену, а не как разрешение сохранить два публичных пути.

По поручению пользователя начато междоменное согласование с Pack, Publication/Artifacts/Snapshot и Time в существующих чатах владельцев. Каждый сначала сверяет собственные актуальные контракты, затем предъявляет точную дельту и возражения. Ответы по новой границе ожидаются. Направление согласовано пользователем; полная междоменная архитектура ещё не принята.

В обсуждении согласованы публичный атомарный staging, явный вызов через DAG и передача подготовленного объекта по ссылке внутри процесса. Пользователь отдельно потребовал первым пунктом реализации закрепить архитектуру. Подробные сигнатуры, классы, ноды и порядок интеграции ещё требуют архитектурной приёмки.

Нормативные источники: [правила DAG и все критерии приёмки](../rules/dag-generator-interface.mdc), [Snapshot ТЗ](../../docs/tz_world_snapshot.md), [owning-план Snapshot](./world-domain-patches-snapshots.md), [GEN-DAG](./gen-dag-1-post-geo-ws.md). Текущие формулировки ТЗ и правила DAG помещают staging внутрь materialization. Новый публичный staging меняет именно эту границу; ARCH-0 должен подготовить и согласовать точную синхронизацию источников, а не скрыто трактовать старую границу как новую. Остальные утверждённые порядки bake и публикации сохраняются.

## 1. ARCH-0 — архитектура до реализации

**Первый обязательный пункт исполнения плана.** Подготовить целевую архитектуру Artifacts и общей Publication-инфраструктуры в данном срезе, предъявить пользователю и получить явную приёмку. Наличие существующего кода, локальных PASS или принятого D2 не заменяет этот gate. До приёмки разрешены исследование и проектирование, но не создание каркасов API, перенос staging, изменение DAG или storage.

### Целевая граница

```text
DAG → Domain.prepare/owning encode → типизированное immutable content
DAG → Artifacts.prepare_stage(content) → PreparedArtifact(content, descriptor)
DAG → Publication.open_preparation(owning input, descriptor) → lease
DAG → Artifacts.stage(lease, prepared) → ArtifactRef
DAG → следующий публичный потребитель / публикация Pack / Snapshot.apply
```

Названия Domain.prepare и Artifacts.stage здесь обозначают операции архитектуры, а не утверждённые имена новых классов или нод.

Artifacts остаётся общей инфраструктурой ядра патчей; Snapshot, Pack и Source используют единый механизм. DAG владеет порядком публичных операций и выбором следующей операции. Домены владеют содержимым результата. Artifacts не вызывает публичный pipeline другого домена, не выбирает следующую стадию и не запускает materialization. Регистрация кодеков и storage adapters не должна маскировать такие вызовы.

Pure prepare_stage выполняет format admission, encode/hash/размер/row_count и выдаёт descriptor без IO и lease. Stage проверяет соответствие prepared содержимого descriptor и своему binding, затем целиком выполняет reserve, запись и seal/проверку по существующим контрактам. DAG не управляет этими внутренними действиями. Атомарность stage означает единый внешний результат операции; это не обещание одной SQL-транзакции вокруг BLOB IO. До успеха возможны удерживаемые staged данные, но отсутствует опубликованный результат. Transaction scopes, writer drain, fences, holders и защита от GC остаются ответственностью общей инфраструктуры. Строка open_preparation в схеме — зависимость специализированного initial-пути, не разрешение переоткрывать Pack lease для каждого артефакта; Pack сохраняет свой owning preparation binding.

### Передача данных

Передавать между preparation и staging ссылку на тот же типизированный объект в одном процессе. Не копировать и не сериализовать payload лишь ради перехода между нодами. Сериализация для canonical hash и хранения допустима внутри storage-пути; обещание полного отсутствия выделений памяти не даётся.

После передачи содержимое не изменяется, включая вложенные коллекции и буферы. ARCH-0 определяет конкретный способ обеспечения этого условия и владельца времени жизни. Ссылка удерживается до завершения/отмены staging; cleanup не освобождает данные, пока ими пользуется writer. Не вводить универсальный Any/dict payload либо callback, повторно запускающий доменный расчёт.

Ссылка на объект — временная память процесса, ArtifactRef — идентичность сохранённого артефакта. После потери процесса восстанавливаются durable facts; если пригодного результата нет, DAG решает о повторной подготовке. Нельзя сохранять адрес объекта как durable checkpoint. Проверить реальную модель исполнения DAG: сериализацию outputs, worker/process boundaries и checkpoints. Если она не допускает передачу объекта по ссылке, предъявить конкретное противоречие до реализации; не вводить скрытую копию или отдельный registry объектов.

### Обязательные deliverables ARCH-0

1. Полный inventory текущих callers, вложенных вызовов, registries, composition roots, debug/worker путей и storage adapters. Для каждого — existing/target, замена и удаление прежнего маршрута. Особо проверить вызовы TypedArtifactStager.stage из materialization и их перенос.
2. Для каждого задействованного класса: модуль, роль, ответственность, допустимые зависимости/эффекты, проверяемый критерий приёмки и конкретный признак отказа. Включить существующие классы из стартового inventory ниже и весь обнаруженный closure. Общая характеристика подсистемы не заменяет реестр классов.
3. Для каждой операции: конкретный публичный класс и полная сигнатура, модули POJO входа/результата/ошибок, владелец интерфейса, caller, открытый pipeline и внутренняя реализация. Проследить вложенные вызовы; проверить заменяемость реализации без изменения DAG. Не переносить backend, SQL scope или алгоритм в публичный контракт.
4. Полный анализ POJO и типизированных field/logic errors: поля, владельцы, назначение, сравнение с existing/planned типами и отсутствие дублирования. Согласовать конкретный prepared payload и различие временной ссылки и ArtifactRef; не создавать параллельные lease/holder/operation модели.
5. Матрица CRUD данных и настроек: каждая операция отдельно, конкретные методы и POJO по обязательному правилу. Не считать immutable content автоматическим исключением для update и не придумывать настройки ради таблицы. Неизвестный контракт или необходимое исключение остаётся открытым до решения пользователя.
6. Для каждой чужой зависимости выполнить протокол междоменного CRUD из правила: owning-контракты, согласованные маршруты и POJO. Привязку к конкретным DAG-нодам согласовать с пользователем; вымышленные ноды не закрывают gate. Не заменять маршрут прямым вызовом чужого pipeline через DI.
7. Сопоставить существующий утверждённый порядок и целевой порядок каждого маршрута, включая условия запуска, cancel/recovery/GC и вложенные атомарные действия. Сохранить full_bake L0 → C23 и detailed location L2 → C11 при settlement-like. Указать точное место staging относительно каждого результата. Новый порядок остаётся открытым до согласования.
8. Согласовать текст изменения ТЗ/правила о staging внутри materialization и границу с ARCH-0 Snapshot. Не обходить остановку реализации в owning-плане Snapshot.

**Приёмка ARCH-0:** отчёт по каждому обязательному критерию правила DAG с местом в архитектуре и доказательством. Pipeline, выбирающий следующую операцию; скрытый запуск; прямой междоменный публичный вызов — каждый даёт отказ. Неполный реестр классов, неполные контракты/POJO/CRUD, неизвестные маршруты или несогласованный порядок также означают отказ. Сейчас эти deliverables не закрыты: план не готов к приёмке реализации.

## Исходный inventory для ARCH-0

| Existing | Роль, которую нужно сохранить и проверить |
|---|---|
| application/artifacts/staging/artifactStaging.py::TypedArtifactStager | Уже имеет stage(lease, content) → ArtifactRef: encode/hash → reserve → backend.write → seal. Кандидат переиспользования, не доказательство готового DAG-facing API. |
| Там же ::ArtifactStagingService | Делегирует lifecycle/storage операции через существующие порты; не должен становиться междоменным оркестратором. |
| application/artifacts/registry/artifactRegistry.py::ArtifactFormatRegistryBinding | Регистрация и разрешение форматов/backends; без запуска доменных pipelines. |
| application/artifacts/lifecycle/artifactGc.py::ArtifactGarbageCollector | Безопасное удаление кандидатов с учётом удержаний; момент запуска определяет DAG. |
| application/artifacts/contracts/ и storage/ | Existing staging/holder/backend/catalog/lease contracts; проверить публичную и внутреннюю границы по каждому методу. |
| application/publication/service/operationLedger.py и db/repositories/sqlite/artifacts/ | Operation lifecycle и durable adapters; проверить scope, fences, cancel и handoff без переноса SQL в DAG. |

Пути в таблице относительно backend/app. Таблица — старт исследования, не полный реестр для приёмки.

## Последующие этапы — только после ARCH-0

### ARCH-0 — проработка по коду от 2026-11-17

Следующие положения конкретизируют архитектуру выше. Все новые имена ниже — TARGET proposal, не existing и не принятая реализация. Пользователь подтвердил границу первой поставки: prepare → stage в памяти одного процесса; durable/checkpoint-интеграция Engine остаётся открытой. Это не разрешение отключить durable execution существующих маршрутов.

#### Фактическая передача результата в Engine

- `application/engine/runtime/validation/contractValidator.py::ContractValidator.validate` проверяет declared instance, `validate_immutable` и вложенные модели, затем возвращает исходный output. Проверка моделей может создавать временные validation instances; обещается сохранение identity передаваемого результата, а не отсутствие любых allocations.
- `application/engine/runtime/dag/context/dagReadView.py::DagReadView.require` через `_read` возвращает `record.output`, проверив declaration, contract и execution identity. Это подтверждённый механизм передачи ссылки. Новый object registry, handle table или deepcopy не нужны.
- `application/engine/contracts/outputRef.py::OutputRef` — декларация producer/output_type, а не ссылка хранения payload. Не создавать второй аналог OutputRef в Artifacts.
- `application/engine/runtime/dag/dagExecutor.py::DAGExecutor._run_workflow_phase` восстанавливает output через `contract.output_type.model_validate_json(record.terminal_payload())`; non-durable argument в этой workflow-ветке также проходит store/CheckpointCodec. Поэтому одного `durable=None` недостаточно для гарантии identity. Конкретный graph binding должен доказать, что выбран обычный in-memory путь; workflow branch не входит в принятую первую границу.
- `dataModel/validation/immutableValue.py::validate_immutable` допускает bytes, frozen модели, tuple/frozenset и рекурсивно проверяет вложения; list/dict, mutable buffer, opaque handle и циклы отклоняются. Повторно реализовывать deep immutability в Artifacts нельзя.

Владение: producer возвращает frozen prepared POJO; catalog удерживает output до принятой Engine invalidation, stage удерживает аргумент до завершения awaited write/seal. Backend обязан завершить/drain writer до возврата/распространения отмены. Удаление одной catalog-ссылки не освобождает объект, пока stage им пользуется. Нельзя дополнительно обнулять или мутировать содержимое. Restart не сохраняет Python identity; повторное вычисление выбирает DAG по durable facts.

#### Публичная операция staging: конкретный предлагаемый контракт

**Дополнение двухоперационной редакции.** TARGET `application/artifacts/staging/artifactPrepareStageOpenPipeline.py`: concrete `ArtifactPrepareStageOpenPipeline[C: bytes | BaseModel]`; интерфейс `IArtifactPrepareStageOpenPipeline` в `application/artifacts/contracts/artifactPrepareStageOpenPipeline.py`. Публичная сигнатура: `def prepare_stage(self, request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]`. TARGET модели в `dataModel/artifacts/staging/preparedArtifact.py`: `ArtifactPrepareStageInput[C](content: C)` и `PreparedArtifact[C](content: C, descriptor: ArtifactRef)`, frozen/strict/extra-forbid. Format/version задаёт trusted binding с existing ArtifactFormatContract[C], согласованный для соответствующего producer; DAG не получает codec callback/backend. Формат не выбирается по содержимому и не подменяется producer. Подготовленный descriptor — ожидаемая identity, не доказательство записи, seal или удержания. PreparedArtifact не является capability; stage не доверяет вручную собранному descriptor. Публичные ошибки admission/mismatch требуют точного общего error mapping в ART-Q3; завершённый Error freeze этим именованием не объявляется.

Гарантия identity: `prepared.content is request.content`, затем stage использует тот же content. Prepared envelope может быть новым малым объектом; копирование содержимого ради границы запрещено. Pure prepare не открывает operation, не читает SQL и не создаёт holds. Concrete specialized модели и их validation проверяются без обхода model_construct.

Владелец — Artifacts. TARGET модуль `backend/app/application/artifacts/staging/artifactStageOpenPipeline.py`: конкретный класс `ArtifactStageOpenPipeline[C: bytes | BaseModel]`; TARGET интерфейс `IArtifactStageOpenPipeline` в `application/artifacts/contracts/artifactStageOpenPipeline.py`. Метод у обоих: `async stage(self, request: ArtifactStageInput[C]) -> ArtifactRef`. Фабрика composition root `make_artifact_stage_pipeline` связывает один existing `ArtifactFormatContract[C]`, версию и backend; они не передаются DAG как executable значения.

TARGET `backend/app/dataModel/artifacts/staging/stageInput.py::ArtifactStageInput[C]`: frozen/strict/extra-forbid модель с полями `lease: OperationLeaseRef`, `prepared: PreparedArtifact[C]`. Это замена прежнего content-поля, не дополнительная overload. Format key/version определяются зафиксированным binding pipeline и проверяются до записи. Каждый binding использует concrete specialization (например, bytes для BLOB); открытый BaseModel/Any или необъявленная union в DAG запрещены. Request содержит ссылку на prepared и его содержимое, а не копию; при реализации обязательна проверка identity вложенного content после admission/construction, в том числе с existing revalidate_instances=always. Если стандартное создание envelope копирует модель, это блокер реализации контракта, а не основание обходить validation через model_construct.

Для BLOB используется existing bytes-contract; произвольная доменная модель не подаётся existing BLOB backend. Доменный producer подготавливает canonical bytes и помещает их в свой named frozen output; DAG передаёт именно bytes field. Для SQL_ROWS используется конкретная frozen row-set модель owning-домена. PreparedArtifact[C] из принятого варианта 1 — только runtime envelope content+descriptor, не второй semantic/storage payload и не новый ref. Точные producer outputs каждого формата утверждаются у владельца, до их появления SQL_ROWS binding остаётся OPEN.

Успех — existing `dataModel/artifacts/references.py::ArtifactRef`: `kind, format_key, format_version, content_hash, nbytes, row_count`. Новый success DTO с повторением этих полей не вводится. Ref означает sealed/held результат данной подготовки; не READY всей операции и не published state.

#### Контракт ошибок двух операций — редакция для приёмки

2026-11-17. Конкретное предложение Artifacts; заменяет предварительный одноэлементный LEASE_NOT_WRITABLE roster. Типы ниже TARGET, не существующая реализация. Требует приёмки и согласования с владельцем shared lifecycle; не объявляет ART-Q3 закрытым.

Обе операции возвращают только success-тип из signatures выше; ожидаемые отказы передаются именованными application exceptions с concrete dataModel POJO. Не вводить одновременно альтернативный result union с теми же ошибками. Pure prepare_stage не имеет operation_id и не возвращает lease-ошибки.

**Field/input errors.** TARGET `dataModel/artifacts/staging/inputErrors.py`:

- `ArtifactInputIssueCode(StrEnum)`: `CONTENT_NOT_IMMUTABLE`, `CONTENT_TYPE_MISMATCH`, `FORMAT_BINDING_MISMATCH`, `DESCRIPTOR_MISMATCH`.
- `ArtifactInputIssue(FieldPathError[ArtifactInputIssueCode])`: existing обязательные code/path/message без дополнительных копий этих полей.
- `ArtifactInputError`: `issues: tuple[JsonFieldError | WireShapeIssue | ArtifactInputIssue, ...]`, непустой tuple, strict/frozen/extra-forbid; existing JsonFieldError/WireShapeIssue импортируются из validation/importIssues, не копируются.
- TARGET carrier `application/artifacts/staging/stageErrors.py::ArtifactInputRejected(error: ArtifactInputError)`. Это узкий доменный exception carrier, не новый общий error framework.

Structural errors переводятся существующим pydantic_issues механизмом; independent checks собираются existing ValidatorAggregationHelper. FieldRef/bind_field задают канонические пути относительно конкретной специализации input. Если невозможно проверить зависимое поле из-за malformed root, downstream check пропускается, но другие независимые ошибки собираются. Новый валидатор immutable payload не создаётся: reuse validate_immutable с размещением ошибки на content-пути. Backend/codec exception нельзя ловить общим except ValueError и объявлять input issue.

**Lifecycle и storage errors:** единственная актуальная редакция — § «Единые ошибки Artifacts: внутреннее решение» выше. Предварительные ArtifactStageFailure/ArtifactStageRefused и запрос Publication спроектировать ошибки Artifacts отозваны; параллельные типы не создаются.

Статический аудит обнаружил общие callers _lease: catalog reserve/seal; leases open/assert/writer/read/finish; holders release/handoff; worldPack climate retention. Все затронутые публичные error contracts и тестовые ValueError catches переводятся в согласованном implementation-срезе. Полный consumer inventory и отсутствие дублирования POJO ещё требуется проверить самим Artifacts. Owning исследования в чатах — evidence, не пользовательская приёмка.

#### Внутренняя цепочка и ответственность

Принятая граница двух операций: prepare_stage admission → внутренний pure descriptor builder → PreparedArtifact; stage admission → внутренняя проверка descriptor/content/binding → reserve → backend.write → seal → ArtifactRef. Переиспользовать descriptor-алгоритм TypedArtifactStager через внутреннюю реализацию; stage не вызывает публичный prepare_stage, и prepare_stage не запускает stage. Повторная проверка hash при stage допустима и не означает копирования/повторного доменного вычисления. `finish_preparation`, publish, cancel и collect не вызываются автоматически из stage. Domain admission/выбор формата происходит в owning preparation и composition, а не в DAG или общих кодеках.

| Класс / модуль относительно backend/app | Ответственность, допустимые зависимости и эффекты | Проверка / признак отказа |
|---|---|---|
| TARGET ArtifactStageOpenPipeline, путь выше | Только порядок одной stage-операции, typed admission adapter и внутренний stager; storage effects через зависимости | Смена hash/backend не меняет pipeline; вычисление digest, доменная классификация или retry внутри него → FAIL |
| TARGET ArtifactPrepareStageOpenPipeline, путь выше | Одна pure операция подготовки через внутренний descriptor builder, без IO/lease | Открывает operation/пишет данные/запускает stage либо другой домен → FAIL |
| TARGET IArtifactStageOpenPipeline, путь выше | Только публичный контракт | Backend/CommitScope/SQL в signature → FAIL |
| Existing TypedArtifactStager, application/artifacts/staging/artifactStaging.py | Внутренний алгоритм descriptor и staging через registry/IArtifactStaging; сохраняется как implementation, не второй публичный entry | Не вызывает Pack/Source/Snapshot и не выбирает следующую операцию; foreign pipeline → FAIL |
| Existing ArtifactStagingService, тот же модуль | Storage lifecycle facade через catalog/lease/holder/ledger/GC/log; reserve/seal остаются internal для DAG | DAG вызывает reserve/seal по отдельности или сервис запускает domain preparation → FAIL |
| ArtifactFormatContract, contracts/formatBackend.py | Связывает content type, kind, versions и pure codecs/row_count | Callable производит IO/доменные вызовы → FAIL |
| ArtifactBackend, тот же модуль; ReadableBlobBackend, contracts/blobRead.py | Write/verify/delete и verified read за storage-контрактом, writer claim принадлежит write | Удержание writer перенесено в DAG либо write публикует мир → FAIL |
| ArtifactFormatRegistryBinding, registry/artifactRegistry.py | Проверка регистрации, codec/backend dispatch; не межоперационный routing | Подмена key/version либо callback запускает pipeline → FAIL |
| IArtifactCatalog / SqliteArtifactCatalog, storage/artifactCatalog.py / db/repositories/sqlite/artifacts/catalogStore.py | Guard, reservation, seal и catalog facts | Seal без согласованного descriptor; SQL в caller → FAIL |
| IArtifactLeases / SqliteArtifactLeases, storage/artifactLeases.py / db/repositories/sqlite/artifacts/leaseStore.py | Fences, admission, writer drain, READY и cancel; локальные транзакции | Принят stale fence, release до drain или own domain computation → FAIL |
| IArtifactHolders / SqliteArtifactHolders, contracts/holderPort.py / db/repositories/sqlite/artifacts/holderStore.py | Acquire/release/query/handoff в утверждённом scope | Разрыв atomic handoff на ноды или release чужого holder → FAIL |
| SqliteArtifactScope, db/repositories/sqlite/artifacts/access/artifactScope.py | Проверка borrowed scope и доступ к artifact tables | Самостоятельный внешний pipeline/UOW вместо borrowed scope → FAIL |
| SqliteOperationArtifacts, db/repositories/sqlite/artifacts/operationArtifacts.py | Read-only operation-holder projection | Writer/GC внутри read → FAIL |
| OperationLedger, application/publication/service/operationLedger.py | Bookkeeping через IOperationStore/leases, не оркестрация повторной подготовки | Recover запускает producer → FAIL |
| ContentAddressedBlobBackend, storage/artifacts/blobBackend.py | Физическое хранение bytes под DI root, writer lifecycle, verify/read/delete | Изменение published bytes, утечка пути в ArtifactRef или новая state machine → FAIL |
| ArtifactGarbageCollector, artifacts/lifecycle/artifactGc.py | Обработка переданных кандидатов под guards и проверка holders | Сам планирует следующий запуск/игнорирует holder → FAIL |
| ArtifactLifecycleLog, artifacts/logging/artifactLog.py | Типизированная диагностика через общий logging | Delivery меняет outcome либо логгер принимает business-решения → FAIL |
| ContractValidator / DagReadView / DAGExecutor, пути выше | Existing Engine admission/read/execution, не знают artifact codec и SQL | Передача копии, скрытая запись payload или storage алгоритм в Engine → FAIL |

Это реестр непосредственно прослеженного stage/lifecycle контура. Транзитивный publication/store/codec closure для новых lifecycle API и все SQL_ROWS adapters не объявляются проверенными. Эти API не расширяются данным предложением stage; полная приёмка домена остаётся OPEN до их отдельного анализа. Все orchestration-классы проверяются по class-size-limit.mdc независимо от размера: публичный pipeline не собирает descriptor, не выбирает recipe и не классифицирует чужие ошибки; эта работа остаётся в implementation/admission owner.

#### POJO: reuse и отсутствие дублирования

| Тип / dataModel/artifacts | Поля и ответственность | Disposition |
|---|---|---|
| ArtifactPrepareStageInput[C] / PreparedArtifact[C], TARGET staging/preparedArtifact.py | content; content + descriptor соответственно | Временная подготовка без storage guarantees, не второй canonical payload/ref; новый POJO требует проверки общего inventory |
| ArtifactStageInput[C], TARGET staging/stageInput.py | lease + prepared, вход сохранения | Не второй lease/ref: композиция existing identity и prepared; отдельно проверить все planned StageInput перед freeze |
| ArtifactLeaseFailure, TARGET artifacts/lifecycle/leaseFailure.py | lease/requirement/code, полный roster выше | Единственный shared lease refusal; не terminal/cancellation/field error |
| ArtifactInputIssue / ArtifactInputError, TARGET staging/inputErrors.py | code/path/message; nonempty issues из existing structural и owning field diagnostics | Не копировать JsonFieldError/WireShapeIssue; классификация/агрегация в admission, не DTO |
| OperationLeaseRef, lifecycle/lease.py | operation_id/world_uid/kind/preparation_fingerprint/fence | Reuse; public capability, не CommitScope |
| StagingReservation, тот же файл | artifact_id/lease/ref | Internal; не выдавать DAG для управления фазами |
| ArtifactRef, references.py | kind/format_key/format_version/content_hash/nbytes/row_count | Единственная identity результата хранения |
| ArtifactFormatMetadata / ArtifactFormatRegistry, references.py | key/supported_versions; entries | Метаданные форматов, не runtime executable registry |
| OperationHolder / ArtifactRetentionHolder / SnapshotHolder / PinHolder, lifecycle/holders.py | tagged lease / artifact / snapshot / pin соответственно | Existing retention identities; не копировать в StageInput |
| VerifiedArtifactRef, тот же файл | ref/holder | Existing результат проверки удержания; stage не выдаёт его вместо ArtifactRef |
| OperationRecord, lifecycle/operation/record.py | operation/world/kind, preparation/publication fingerprints, phase/fence, leased_artifacts/terminal | Existing наблюдение lifecycle; не output каждой записи bytes |
| OperationCancelled, тот же файл | operation_id/reason REQUESTED | Durable cancellation, не coroutine cancellation |
| ArtifactGcFailure / GcReport, lifecycle/gc.py | failure_id/ref/stage/code/exception_type/message/errno/winerror; deleted/retained/failed | Existing GC results, не общий stage error carrier |

Перечисление не даёт разрешения менять эти формы, canonical IDs и codec manifests. Полная проверка foreign terminal POJO, логовых DTO и planned errors остаётся отдельным незакрытым пунктом общей приёмки, не скрытым PASS.

#### Конкретный existing consumer и междоменный маршрут

Поиск `TypedArtifactStager` в backend/app нашёл definition и Pack `application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation`. Функция сейчас кодирует manifest, собирает members, вызывает `StagedClimateFields.validate`, затем stager.stage, проверяет descriptor, вызывает finish_preparation и собирает PreparedPackCandidate. Это конкретная смешанная цепочка, которую нельзя просто переименовать в OpenPipeline.

TARGET disposition (уточнение по existing контракту): Pack-owned подготовка выдаёт canonical manifest bytes и members → DAG передаёт bytes в Artifacts.prepare_stage и его PreparedArtifact в Artifacts.stage с согласованным Pack lease → DAG передаёт ArtifactRef в Pack-owned проверку соответствия → согласованный Publication retention/READY entry → выдача PreparedPackCandidate только после подтверждённого READY. `dataModel/worldPack/activation/candidate.py` определяет candidate как результат durably finished preparation; existing finish_pack_preparation конструирует его после проверки record.phase == READY и полного binding. Конструирование candidate до READY запрещено этим смыслом, даже если POJO технически допускает создание без чтения storage. Точный владелец финальной выдачи и новые публичные signatures ожидают owning-уточнения ART-Q1; промежуточный дублирующий candidate DTO не вводится. Прямой вызов stage из Pack удаляется на согласованном cutover. Проверка соответствия manifest bytes/ref и membership остаётся Pack. Source closure/adoption и READY сохраняют owning-протокол [Pack adoption](./pack-source-adoption-publication-response-2026-11-14.md); stage сам их не доказывает.

Протокол междоменного CRUD: потребитель Artifacts.stage требует подготовленный content от Pack; existing функция не предоставляет отдельного публичного prepare-контракта. Обратный потребитель Pack требует ArtifactRef, формат/версию/hash/nbytes и membership evidence; exact public Pack consumer также ещё не определён. Поэтому PACK-PREPARED-API — OPEN: нужен owning Pack контракт с конкретными POJO/ошибками. Не назначать эти методы Pack из Artifacts. Другие доменные producer contracts нельзя вывести из наличия registry.

Согласованных NodeId для этой новой границы нет. Маршрут выше — proposal операций, не утверждённый граф. По GEN-NODE-JOINT-REVIEW привязка остаётся OPEN до совместной карты и согласования; никаких invented NodeId и прямого Pack→Artifacts pipeline как обхода.

#### CRUD disposition и остаточные blockers

| Объект | Create | Read | Update | Delete |
|---|---|---|---|---|
| Immutable artifact data | TARGET ArtifactStageOpenPipeline.stage; Error mapping OPEN | Existing ReadableBlobBackend.read_verified — storage API, не готовый concrete domain CRUD | Нет принятого публичного метода; replacement по тому же hash запрещён, но это не исключение из правила CRUD | Existing collect → GcReport — guarded GC, не универсальное разрешение удалить held content |
| Artifacts settings | Не определён owning settings POJO/API | Нет публичного контракта | Нет публичного контракта | Нет публичного контракта |

Root/backend registration — existing composition configuration, а не основание самовольно распространять исключения Cache/Pack на Artifacts. Для полной приёмки необходимо либо разработать полный owning CRUD с конкретными моделями, либо получить явное узкое исключение и синхронизировать правило/ТЗ. Это решение не подменяется созданием фиктивных методов и вымышленных настроек.

#### Матрица архитектурной приёмки этой редакции

| Обязательный критерий | Вывод / основание |
|---|---|
| Нет выбора следующих операций в pipeline | TARGET соблюдает: stage не finish/publish/retry; existing Pack chain требует cutover |
| Нет скрытого запуска | TARGET только DAG; фактический новый binding отсутствует, статус OPEN |
| Нет прямых междоменных pipeline calls | TARGET соблюдает; existing Pack→stager под замену, точный Pack API OPEN |
| Каждый класс и ответственность | Stage contour описан; полный foreign/lifecycle closure OPEN |
| Public/Input/Output/Error и implementation | Stage proposal конкретизирован; typed admission/refusal mapping OPEN |
| Неизменность согласованного порядка | Выбор публичного stage и in-memory границы подтверждён; per-route/node порядок OPEN |
| CRUD данных и настроек | FAIL для приёмки всего домена: матрица содержит незакрытые операции |
| Междоменный CRUD-протокол | Pack inputs/consumers выявлены, owning public contracts отсутствуют — OPEN |
| POJO/field/logic errors без дублей | Reuse установлен для основного контура; полный анализ planned/foreign errors OPEN |
| Именование | TARGET класс, интерфейс и модули имеют OpenPipeline |
| Замена implementation без правки orchestration | Целевой контракт изолирует backend/codec; доказательство substitution остаётся проверкой реализации |

**Вердикт: ARCH-0 ещё не принят.** Конкретные blockers: PACK-PREPARED-API, GEN-NODE-JOINT-REVIEW, stage field/refusal contract, complete POJO/class closure и CRUD disposition. In-memory граница подтверждена пользователем; durable интеграция сознательно остаётся вне первой поставки. Это проработанное предложение с выявленными зависимостями, не декларация полного соответствия.

2. **Контракты и нормативная синхронизация.** По принятой архитектуре синхронизировать ТЗ/правила и точные публичные контракты, ошибки, prepared payload и гарантии владения. Проверить reuse TypedArtifactStager; не создавать второй staging. Сохранять порядок согласованных contract groups, переводить producers/consumers согласованно.
3. **Реализация публичного staging.** Реализовать принятый конкретный API поверх единой инфраструктуры; закрыть успешное сохранение, отказ, отмену, конкурентную запись и идемпотентность. Не публиковать Pack/Snapshot из stage.
4. **Перевод preparation и DAG binding.** По согласованному inventory домен возвращает объект без staging; DAG передаёт именно этот объект публичной операции. Перевести composition/debug/worker callers и убрать прежний путь в том же согласованном срезе. Изменение DAG требует явного разрешения на реализацию; этот план его не выдаёт.
5. **Lifecycle и межплановая интеграция.** Подключить согласованные cancel/recover/GC и публикацию без разрыва атомарного holder handoff. Не выводить из успешного stage доказательство Source completeness либо разрешение на публикацию. Не реализовывать открытые соседние контракты по предположению.
6. **Техническая приёмка.** Проверить весь согласованный маршрут, заменяемость реализации, отсутствие старой скрытой оркестрации и сохранение существующих storage-инвариантов. Зафиксировать revision, команды и результаты; отсутствие production binding не маскировать локальными тестами.

Детальное разбиение этапов 2–6 и их классы/методы фиксируются в ARCH-0; сейчас это последовательность подготовки поставки, не готовый список кодовых изменений.

## Проверки целевого поведения

### Реестр открытых вопросов ARCH-0 — 2026-11-17

Все вопросы ниже имеют статус **OPEN**. Закрытие фиксируется здесь ссылкой на точный owning-контракт/решение и проверкой его переноса в архитектуру. Список не означает, что все ответы должен подготовить пользователь: исследование и контрактные предложения выполняются в ARCH-0, пользователь принимает решения и совместный DAG-дизайн.

По ART-Q1 2026-11-17 получены ответы отдельных чатов: Pack `01a1ea8d-1751-70d3-970e-df20d38779f4` и Publication/Artifacts `01a1ea8d-2bdb-7152-bb40-925c86c041d8`. Каждый сначала сверил собственные доменные источники и код. Результат уточнения ниже не означает приёмку предложенного API; ART-Q1 остаётся OPEN.

#### ART-Q1 — результат уточнения владельцев

**Existing, подтверждено обоими:** `finish_preparation(lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord` проверяет writable lease, отсутствие writers, уникальный набор refs, его точное равенство operation holds и seals; закрывает admission и записывает READY в собственной транзакции. Это не доказательство Source closure или корректности Pack manifest. `SqliteArtifactLeases._transaction` требует unbound connection: bind(scope) вокруг existing finish не присоединяет его к внешнему UOW, а отвергается.

`PreparedPackCandidate(operation_id, manifest, preparation_fingerprint)` выдаётся только после confirmed READY и exact Pack checks. Его POJO validator проверяет descriptor, не durability. Existing finish_pack_preparation — внутренний helper; Pack-проверка нашла callers в тестах spatial_pack, production caller не подтверждён. Поэтому не считать его уже включённым публичным pipeline. Часть Pack write-классов уже реализована, несмотря на исторические PROJECT-пометки: статусы проверять по declarations, а не переносить целиком из старого плана.

**Pack proposal, ещё не принят:** `PackManifestPreparationOpenPipeline` / `IPackManifestPreparationOpenPipeline` в `application/worldData/pack/preparation/packManifestPreparationOpenPipeline.py` предлагает prepare_manifest, validate_staged_manifest и confirm_preparation. Первый возвращает материал для stage; второй проверяет descriptor/hash/nbytes/members; третий выдаёт existing candidate после доверенного чтения READY и проверки world/kind/operation/fence/fingerprint/полного набора holds. Произвольный OperationRecord от caller не является доказательством durability. Распределение этих методов по concrete public classes и интерфейсам требует проверки ответственности перед freeze.

Предлагаемый `dataModel/worldPack/preparation/manifestStageMaterial.py::PackManifestStageMaterial` содержит operation_id, world_uid, preparation_fingerprint, content: bytes, members: tuple[ArtifactRef, ...] (полный closure без самого manifest). Он не утверждает READY и не является вторым candidate. Его точный binding с lease/current fence и принятым final request остаётся OPEN; DTO пока не утверждать. Existing PackPreparationInput здесь нельзя считать окончательно зафиксированным новым prepare request только по имени из предложения.

Pack рекомендует reuse `PackPreparationFailure` / `PackPreparationError(reason, issues)` из `dataModel/worldPack/preparation/errors.py`, включая existing field/artifact/budget issues, вместо новых зеркальных CandidateError. Mapping manifest mismatch, READY mismatch и lifecycle refusal остаётся OPEN; infrastructure/cancel/unknown outcome не превращать в validation failure.

**Publication proposal, ещё не принят:** internal `IPackPreparationRetention.adopt_and_finish(request: PackPreparationRetentionInput) -> OperationRecord | SourceFailure`. Input: lease, closures: tuple[SourceClosureAdoption, ...], operation_members: tuple[ArtifactRef, ...]; SourceClosureAdoption: request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef, ...]. Fingerprint брать из lease, отдельное поле не дублировать; PackPreparationBody/recomputation остаются Pack-owned.

Для единого UOW требуется proposed `SqliteArtifactLeases.finish_preparation_scoped(scope: CommitScope, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord`: borrowed scope без собственного commit, общий алгоритм проверки с standalone finish. Порядок: validation/binding → writer UOW → повторная проверка admission/drain → все internal Source adopts → scoped members/seals/READY → confirmed commit → результат. SourceFailure требует rollback всех новых target holds перед возвратом; source holds не снимаются. Unknown commit/rollback остаётся UnknownCommitOutcome.

Internal retention port **не является готовым публичным DAG entry**. Требуются явная внешняя lifecycle boundary, её Input/Output/Error и trusted binding. Нельзя закрыть этот пробел прямым Pack→public Publication pipeline, callback или передачей internal scoped API в ноду. Proposed PackPreparationRetentionError roster и Pack mapping не приняты.

**Рекомендуемый порядок операций:** Pack prepare_manifest → Artifacts.prepare_stage → Artifacts.stage с существующим Pack lease → Pack validate_staged_manifest → согласованный внешний Publication entry (внутри atomic adoption→READY) → Pack confirm_preparation → отдельная activation. Это proposal, не утверждённые ноды. Stage не завершает operation и не выбирает следующий вызов.

**Незакрытые зависимости:** final Pack request и trusted material/fence binding; Source authority из base/capture context и scoped resolver/pins (VerifiedArtifactRef и произвольный holders lookup не дают authority); scoped finish; обязательный READY producer/version binding; durable exact candidate mapping для replay; внешний public lifecycle entry и ошибки; владелец/освобождение READY_INACTIVE manifest. OperationRecord не хранит роль manifest: recovery не может выбирать первый ref подходящего формата или пересобирать manifest. Retention holder manifest→children не удерживает сам root. Политика in-memory передачи payload не отменяет durable-инварианты записанного READY.

Ответы владельцев уточняют предмет следующего согласования; полного закрытия ART-Q1 и ARCH-0 нет.

| ID | Вопрос, требующий ответа | Владелец ответа / основание закрытия | Что блокирует |
|---|---|---|---|
| ART-Q1 — PACK-PREPARED-API | Какой конкретный публичный Pack prepare-метод выдаёт canonical manifest bytes и members без staging? Какой метод принимает полученный ArtifactRef и проверяет соответствие manifest перед подготовкой candidate? | Pack: модули, конкретные классы, полные сигнатуры, POJO полей/ошибок и порядок; согласование с owning Pack adoption/READY-контрактом | Перевод finish_pack_preparation и приёмку междоменного маршрута |
| ART-Q2 — GEN-NODE-JOINT-REVIEW | Какие согласованные ноды вызывают preparation, stage и consumer; каковы их I/O/Error, deps, условия запуска и lifecycle? Как гарантируется обычный in-memory путь без workflow JSON round-trip? | Пользователь совместно с Engine/DAG: карта маршрута и точные контракты по GEN-NODE-JOINT-REVIEW; агент не назначает NodeId самостоятельно | DAG binding, порядок операций и приёмку интеграции |
| ART-Q3 — STAGE-ERRORS | Какие existing typed field errors обслуживают вход stage? Проверены ли все concrete codecs/consumers и propagation нового shared ArtifactLeaseRefused без маскировки codec/storage faults? | Artifacts/Publication: полный Input/Output/Error, причины, поля, mapping по конкретным call sites; reuse общей validation infrastructure | Freeze публичного stage и его реализацию |
| ART-Q4 — CLASS-POJO-CLOSURE | Каков полный closure затронутых классов и POJO, включая publication store/codec, foreign terminal types, SQL_ROWS adapters и planned errors? Где доказано отсутствие повторяющихся ответственностей и DTO? | Исследование ARCH-0: полный реестр модулей/полей, dependencies/effects, критерии отказа каждого класса, сопоставление existing/planned типов | Полную архитектурную приёмку; не заменяется начальным inventory |
| ART-Q5 — DATA-CRUD | Какие конкретные публичные read/update/delete методы Artifacts дополняют stage? Каковы допустимые update/delete для immutable и held artifacts? Требуется ли узкое исключение из общего CRUD-правила? | Artifacts готовит контрактное предложение; пользователь принимает семантику либо явное исключение с нормативной фиксацией | Приёмку CRUD и домена целиком; immutable само по себе не освобождает от правила |
| ART-Q6 — SETTINGS-CRUD | Есть ли у Artifacts доменные изменяемые настройки, каков их named POJO и полный CRUD? Если root/registration являются только composition configuration, какое точное исключение требуется? | Artifacts инвентаризирует configuration; пользователь принимает границу и при необходимости исключение. Исключения Cache/Pack автоматически не применяются | Приёмку настроек и домена целиком |
| ART-Q7 — PAYLOAD-IDENTITY | Сохраняет ли создание/admission конкретного ArtifactStageInput[C] identity вложенного content при existing revalidate_instances=always? Какие concrete frozen producer outputs используются для каждого формата? | Artifacts и owning producers: точные POJO и воспроизводимая проверка identity/immutability; без model_construct, Any и скрытого копирования | Freeze input-контракта и утверждение передачи того же объекта |
| ART-Q8 — NORMATIVE-SYNC | Какие точные положения Snapshot ТЗ и DAG-правила заменяют старое staging-inside-materialization, не меняя прочих утверждённых порядков? Как новый срез согласован с ARCH-0 Snapshot? | Artifacts/Snapshot: конкретная нормативная редакция по уже принятому пользователем решению о публичном staging | Согласованность источников и переход к реализации |

**Уже решено, повторно не спрашивать:** staging — публичная атомарная операция; управление вызовами — DAG; передаётся тот же объект по ссылке; первая поставка ограничена одним процессом; архитектура и её приёмка идут первыми. Durable/checkpoint-путь остаётся отложенной интеграцией Engine, не условием для расширения текущего scope. ART-Q2/ART-Q7 проверяют реализацию принятой границы, а не пересматривают эти решения.

### Сценарии проверки

- Preparation и stage получают один объект по identity; между нодами нет encode/decode ради транспорта. Storage encode проверяется отдельно.
- Недопустима мутация payload между hash и записью; контракт обеспечивает стабильность bytes и descriptor.
- Stage возвращает ref только после принятого seal; частичная запись не становится опубликованной.
- Cancel во время записи, повтор cancel, повтор staging, restart и unknown commit сохраняют утверждённые lifecycle гарантии.
- GC не удаляет held/writing результаты; публикация и handoff не имеют окна без удержания.
- Ошибка stage не запускает последующего потребителя; retry выбирает DAG по типизированному исходу.
- Существующие snapshotCore artifact/atomicity/typing и logging проверки остаются регрессионной базой; точные команды определяются по изменённым маршрутам после ARCH-0. Новых runtime-прогонов при составлении этого плана не было.

## Зависимости и границы

[D2](./world-domain-artifacts-cancel-gc-d1.md) и [его проверка](./artifacts-d2-physics-i0-joint-verification.md) — существующая база, не основание переписывать cancel/GC заново. [Pack adoption](./pack-source-adoption-publication-response-2026-11-14.md), [Source mutation](./source-mutation-artifacts-publication-response-2026-11-13.md) и INITIAL-REGISTER в Snapshot сохраняют собственных владельцев и статусы. Новый план не объявляет их закрытыми и не переопределяет их протоколы.

Вне текущего поручения: код, SQL-миграции, перенос папок ради нового названия домена, новые storage/ledger/holder механизмы, коммит и запуск backend. Сейчас создаётся только план; следующий содержательный шаг — ARCH-0.

## Исправления ревью 2026-11-18 и обязательная повторная приёмка

1. Все Pack-маршруты включают prepare_stage перед stage; существующий Pack lease не переоткрывается на каждый artifact.
2. Широкая integrity-категория заменена различимыми content/descriptor, codec и storage-invariant faults.
3. Hold-гарантия привязана к confirmed seal commit, не к моменту доставки return.
4. Callback errors имеют явную границу нормализации; несовместимые existing format bindings остаются заблокированными до owning admission.
5. Удалены прежние stage-specific failure declarations и противоречащие инструкции ждать их проектирования от Publication.
6. Замечание о полноте class/POJO closure **не закрыто**: по каждому затронутому concrete codec/registration/composition, storage caller, logging validator и public consumer нужен отдельный модуль, роль, dependencies/effects и критерий отказа. Новые ArtifactCodecError, ArtifactDescriptorConflictError, ArtifactStorageInvariantError — только application fault categories без IO/dispatch/logging; DTO/schema validators не исполняют операции. Требуется сравнение всех existing/planned errors и обновление общего реестра. Это собственная работа Artifacts, не требование к соседям.

Статус ARCH-0 остаётся NOT ACCEPTED. CRUD данных/настроек, exact foreign public contracts и совместная DAG-карта остаются открытыми. Наличие исправлений документа не означает runtime evidence или разрешение кода.

