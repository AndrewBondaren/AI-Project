# Artifacts — публичный staging и граница с DAG

2026-11-17. **DESIGN OPEN. Первый обязательный этап — ARCH-0: целевая архитектура и её приёмка. До закрытия ARCH-0 реализация последующих этапов запрещена.** Этот документ не является разрешением писать код и не объявляет домен принятым.

## Решения пользователя и источники

В обсуждении согласованы публичный атомарный staging, явный вызов через DAG и передача подготовленного объекта по ссылке внутри процесса. Пользователь отдельно потребовал первым пунктом реализации закрепить архитектуру. Подробные сигнатуры, классы, ноды и порядок интеграции ещё требуют архитектурной приёмки.

Нормативные источники: [правила DAG и все критерии приёмки](../rules/dag-generator-interface.mdc), [Snapshot ТЗ](../../docs/tz_world_snapshot.md), [owning-план Snapshot](./world-domain-patches-snapshots.md), [GEN-DAG](./gen-dag-1-post-geo-ws.md). Текущие формулировки ТЗ и правила DAG помещают staging внутрь materialization. Новый публичный staging меняет именно эту границу; ARCH-0 должен подготовить и согласовать точную синхронизацию источников, а не скрыто трактовать старую границу как новую. Остальные утверждённые порядки bake и публикации сохраняются.

## 1. ARCH-0 — архитектура до реализации

**Первый обязательный пункт исполнения плана.** Подготовить целевую архитектуру Artifacts и общей Publication-инфраструктуры в данном срезе, предъявить пользователю и получить явную приёмку. Наличие существующего кода, локальных PASS или принятого D2 не заменяет этот gate. До приёмки разрешены исследование и проектирование, но не создание каркасов API, перенос staging, изменение DAG или storage.

### Целевая граница

```text
DAG → Domain.prepare → типизированный объект подготовленных данных
DAG → Artifacts.stage(тот же объект) → ArtifactRef
DAG → следующий публичный потребитель / публикация Pack / Snapshot.apply
```

Названия Domain.prepare и Artifacts.stage здесь обозначают операции архитектуры, а не утверждённые имена новых классов или нод.

Artifacts остаётся общей инфраструктурой ядра патчей; Snapshot, Pack и Source используют единый механизм. DAG владеет порядком публичных операций и выбором следующей операции. Домены владеют содержимым результата. Artifacts не вызывает публичный pipeline другого домена, не выбирает следующую стадию и не запускает materialization. Регистрация кодеков и storage adapters не должна маскировать такие вызовы.

Публичная операция staging целиком выполняет подготовку descriptor/hash, reserve, запись и seal/проверку по существующим контрактам. DAG не управляет этими внутренними действиями. Атомарность означает единый внешний результат операции; это не обещание одной SQL-транзакции вокруг BLOB IO. До успеха возможны удерживаемые staged данные, но отсутствует опубликованный результат. Transaction scopes, writer drain, fences, holders и защита от GC остаются ответственностью общей инфраструктуры.

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

Владелец — Artifacts. TARGET модуль `backend/app/application/artifacts/staging/artifactStageOpenPipeline.py`: конкретный класс `ArtifactStageOpenPipeline[C: bytes | BaseModel]`; TARGET интерфейс `IArtifactStageOpenPipeline` в `application/artifacts/contracts/artifactStageOpenPipeline.py`. Метод у обоих: `async stage(self, request: ArtifactStageInput[C]) -> ArtifactRef`. Фабрика composition root `make_artifact_stage_pipeline` связывает один existing `ArtifactFormatContract[C]`, версию и backend; они не передаются DAG как executable значения.

TARGET `backend/app/dataModel/artifacts/staging/stageInput.py::ArtifactStageInput[C]`: frozen/strict/extra-forbid модель с полями `lease: OperationLeaseRef`, `content: C`. Format key/version определяются зафиксированным binding pipeline и проверяются до записи. Каждый binding использует concrete specialization (например, bytes для BLOB); открытый BaseModel/Any или необъявленная union в DAG запрещены. Request содержит ссылку на подготовленное содержимое, а не его копию; при реализации обязательна проверка identity вложенного `content` после admission/construction, в том числе с existing `revalidate_instances=always`. Если стандартное создание envelope копирует модель, это блокер реализации контракта, а не основание обходить validation через model_construct.

Для BLOB используется existing bytes-contract; произвольная доменная модель не подаётся existing BLOB backend. Доменный producer подготавливает canonical bytes и помещает их в свой named frozen output; DAG передаёт именно bytes field. Для SQL_ROWS используется конкретная frozen row-set модель owning-домена. Новый универсальный PreparedArtifact, новый ref и второй storage payload не нужны. Точные producer outputs каждого формата утверждаются у владельца, до их появления SQL_ROWS binding остаётся OPEN.

Успех — existing `dataModel/artifacts/references.py::ArtifactRef`: `kind, format_key, format_version, content_hash, nbytes, row_count`. Новый success DTO с повторением этих полей не вводится. Ref означает sealed/held результат данной подготовки; не READY всей операции и не published state.

TARGET logic error POJO `dataModel/artifacts/staging/stageFailure.py::ArtifactStageFailure`: `operation_id: EntityUid`, `code: ArtifactStageFailureCode`; enum только `LEASE_NOT_WRITABLE` для доказанного отказа admission. TARGET exception `application/artifacts/staging/stageErrors.py::ArtifactStageRefused` несёт этот POJO. Не переводить arbitrary ValueError в LEASE_NOT_WRITABLE: catalog/registry/backend ValueError может обозначать иной отказ или corruption. До реализации нужен точный typed refusal из owning lease adapter; пока mapping OPEN. Input schema/immutability errors проверяются до side effects через существующую validation infrastructure; конкретный field-error binding также OPEN, не маскируется logic code.

Existing `PublicationInfrastructureError`, `UnknownCommitOutcome` и `OperationBusyError` сохраняются как инфраструктурные исходы, а `CancelledError` распространяется после writer drain. Не изобретать второй error framework, не возвращать ложный успех/повтор при неизвестном commit. Конкретный публичный Error-контракт не принимается до закрытия field/refusal mapping.

#### Внутренняя цепочка и ответственность

Предлагаемая линейная цепочка: admission входа → existing typed staging implementation → encode/hash/row_count → reserve → backend.write → seal → ArtifactRef. `finish_preparation`, publish, cancel и collect не вызываются автоматически из stage. Domain admission/выбор формата происходит в owning preparation и composition, а не в DAG или общих кодеках.

| Класс / модуль относительно backend/app | Ответственность, допустимые зависимости и эффекты | Проверка / признак отказа |
|---|---|---|
| TARGET ArtifactStageOpenPipeline, путь выше | Только порядок одной stage-операции, typed admission adapter и внутренний stager; storage effects через зависимости | Смена hash/backend не меняет pipeline; вычисление digest, доменная классификация или retry внутри него → FAIL |
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
| ArtifactStageInput[C], TARGET staging/stageInput.py | lease + content, вход одной операции | Не второй lease/ref: композиция existing identity и payload; отдельно проверить все planned StageInput перед freeze |
| ArtifactStageFailure, TARGET staging/stageFailure.py | operation_id + code, ожидаемый отказ stage | Не GcFailure и не cancellation; field mapping OPEN |
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

TARGET disposition (уточнение по existing контракту): Pack-owned подготовка выдаёт canonical manifest bytes и members → DAG передаёт bytes в Artifacts stage → DAG передаёт ArtifactRef в Pack-owned проверку соответствия → согласованный Publication retention/READY entry → выдача PreparedPackCandidate только после подтверждённого READY. `dataModel/worldPack/activation/candidate.py` определяет candidate как результат durably finished preparation; existing finish_pack_preparation конструирует его после проверки record.phase == READY и полного binding. Конструирование candidate до READY запрещено этим смыслом, даже если POJO технически допускает создание без чтения storage. Точный владелец финальной выдачи и новые публичные signatures ожидают owning-уточнения ART-Q1; промежуточный дублирующий candidate DTO не вводится. Прямой вызов stage из Pack удаляется на согласованном cutover. Проверка соответствия manifest bytes/ref и membership остаётся Pack. Source closure/adoption и READY сохраняют owning-протокол [Pack adoption](./pack-source-adoption-publication-response-2026-11-14.md); stage сам их не доказывает.

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

**Рекомендуемый порядок операций:** Pack prepare_manifest → Artifacts stage → Pack validate_staged_manifest → согласованный внешний Publication entry (внутри atomic adoption→READY) → Pack confirm_preparation → отдельная activation. Это proposal, не утверждённые ноды. Stage не завершает operation и не выбирает следующий вызов.

**Незакрытые зависимости:** final Pack request и trusted material/fence binding; Source authority из base/capture context и scoped resolver/pins (VerifiedArtifactRef и произвольный holders lookup не дают authority); scoped finish; обязательный READY producer/version binding; durable exact candidate mapping для replay; внешний public lifecycle entry и ошибки; владелец/освобождение READY_INACTIVE manifest. OperationRecord не хранит роль manifest: recovery не может выбирать первый ref подходящего формата или пересобирать manifest. Retention holder manifest→children не удерживает сам root. Политика in-memory передачи payload не отменяет durable-инварианты записанного READY.

Ответы владельцев уточняют предмет следующего согласования; полного закрытия ART-Q1 и ARCH-0 нет.

| ID | Вопрос, требующий ответа | Владелец ответа / основание закрытия | Что блокирует |
|---|---|---|---|
| ART-Q1 — PACK-PREPARED-API | Какой конкретный публичный Pack prepare-метод выдаёт canonical manifest bytes и members без staging? Какой метод принимает полученный ArtifactRef и проверяет соответствие manifest перед подготовкой candidate? | Pack: модули, конкретные классы, полные сигнатуры, POJO полей/ошибок и порядок; согласование с owning Pack adoption/READY-контрактом | Перевод finish_pack_preparation и приёмку междоменного маршрута |
| ART-Q2 — GEN-NODE-JOINT-REVIEW | Какие согласованные ноды вызывают preparation, stage и consumer; каковы их I/O/Error, deps, условия запуска и lifecycle? Как гарантируется обычный in-memory путь без workflow JSON round-trip? | Пользователь совместно с Engine/DAG: карта маршрута и точные контракты по GEN-NODE-JOINT-REVIEW; агент не назначает NodeId самостоятельно | DAG binding, порядок операций и приёмку интеграции |
| ART-Q3 — STAGE-ERRORS | Какие existing typed field errors обслуживают вход stage? Каким конкретным typed исходом lease adapter сообщает отказ admission, чтобы не классифицировать arbitrary ValueError как LEASE_NOT_WRITABLE? | Artifacts/Publication: полный Input/Output/Error, причины, поля, mapping по конкретным call sites; reuse общей validation infrastructure | Freeze публичного stage и его реализацию |
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
