# ТЗ: Типизированные контракты нод engine DAG (Input / Output)

**Статус (2026-10-30):** архитектура исполнения согласована в DAG-TYPING-1; настоящие §§6–12 фиксируют общий контракт. Конкретные контракты всех рабочих нод, их зависимости по данным и миграция принадлежат GEN-DAG-1. DAG-TYPING-1 реализует только общую инфраструктуру и тестовые ноды. Документ **не разрешает менять engine DAG** без отдельного согласования с мастером.

**Связанные документы:** `.cursor/plans/dag-typing-1.md` (план типизации), `.cursor/plans/gen-dag-1-post-geo-ws.md` (интеграция и конкретные контракты нод), `.cursor/plans/world-domain-patches-snapshots.md`, `docs/tz_world_generation_dag.md`, `docs/tz_engine_flow.md`.

## 1. Исходное состояние

- `BaseNode.deps: list[str]` уже декларирует зависимости по порядку исполнения; `GraphCompiler` строит уровни DAG и обнаруживает циклы. Повторный механизм `REQUIRES` для этого не нужен.
- `NodeResult.data: Any`, `ExecutionState.node_results: dict[str, object]` и `shared_context: dict` не задают типы данных между нодами.
- Python-ноды могут читать результаты других нод по строковым ключам; контракт потребляемых полей не проверяется типами.
- LLM-ноды уже имеют отдельные `contract_json` и валидаторы, но единая модель типизированных Input/Output для всех нод ещё не реализована.

## 2. Принятые архитектурные решения

1. **Каждая нода объявляет Input и Output строго как типизированные POJO**, подобно типизированной сигнатуре метода. Контракты известны до исполнения, а не создаются динамически при вызове. Допускается непосредственно использовать существующий доменный POJO, составить POJO ноды из нескольких доменных POJO или объявить собственный POJO ноды, если этого требует её семантика. Отдельный класс для каждой ноды не обязателен.
2. **Нода самостоятельно формирует экземпляр своего Input** перед исполнением. Концептуальный жизненный цикл: `prepare_input(read_view) -> I`, затем `execute(input: I) -> O`. Точные общие сигнатуры и binding приведены в §6; доменные зависимости внедряются в ноду явно через её factory.
3. Для подготовки Input нода может получать доступ к **согласованному исходному состоянию** через публичные доменные read-контракты и к **типизированным результатам завершённых зависимостей**. DAG выбирает и упорядочивает операции, но не подбирает за домен поля и не формирует его данные. Snapshot не решает, что передавать ноде; чтение, missing и fallback принадлежат соответствующему домену.
4. Существующее **`deps` остаётся механизмом зависимостей исполнения**. Оно не тождественно контракту данных: нода может зависеть от другой по порядку без потребления её Output. Типобезопасный доступ и явные требования контрактов определены в §6; второго графа исполнения нет.
5. **Output возвращается непосредственно как типизированное значение `O`.** Текущий `NodeResult`, содержащий только `data: Any`, при такой модели является избыточной обёрткой и подлежит устранению при миграции после проверки фактических usages. Заранее не вводить `NodeResult[T]` только ради сохранения обёртки.
6. Инфраструктура исполнения валидирует фактические Input и Output на границах вызова. Статусы, ошибки, replan и трассировка остаются отдельной ответственностью runtime, а не обязательными полями каждого Output. Нужно сохранить семантику существующих Python- и агрегированных LLM-исполнителей.
7. **Output не обязан быть Patch или PatchSet.** Нода возвращает результат своей операции; DAG отвечает за выбор следующих операций и сборку PatchSet по согласованным контрактам, Snapshot — за применение и историю. `prepare_input` не вправе скрыто запускать самостоятельные DAG-операции или междоменный pipeline.

### 2.1. DAGContext как каталог типизированных Output (решение 2026-10-30)

- **Повторно использовать контракты нод:** логический контекст DAG содержит опубликованные экземпляры `Output` нод, адресуемые по идентификатору/контракту производителя. Не создавать вторую иерархию `TerrainContext`/`SceneContext` с копиями тех же данных.
- **Не создавать гигантский POJO общего состояния:** физическая реализация может использовать закрытое гетерогенное хранилище по `node_id`, но предоставлять наружу только типизированные операции публикации и чтения с проверкой контракта. Внутренний `object` не должен превращаться во внешний `Any`-API. Сигнатуры интерфейса приведены в §6.
- **Input короткоживущий по умолчанию:** нода формирует типизированный Input и использует его при исполнении. Не хранить все Input постоянно в DAGContext без конкретного требования replay/diagnostics; формат аудита входов решается отдельно.
- **Малые Output допускается хранить непосредственно.** Для крупных результатов Output может содержать типизированные ссылки на доменное хранилище/кеш/pack (использовать существующие механизмы, где они подходят). Представление "значение или ссылка" определяет контракт самой ноды/домена, а не автоматическая эвристика DAGContext по размеру. Универсальную новую систему ссылок без конкретного обоснования не вводить.
- **Не копировать данные между стадиями:** опубликованные результаты должны иметь подтверждённую неизменяемость, в том числе вложенных структур; зависимые ноды могут разделять один объект или ссылку. Диагностические снимки уровней DAG не должны создавать полные копии доменных payload.
- **DAG runtime владеет временем жизни опубликованных результатов** по §9: активное исполнение и resume-снимок удерживают нужные результаты; trace не удерживает payload. Автоматическое освобождение только по последнему потребителю не применяется.
- **DAGContext не является копией состояния мира.** Согласованное исходное состояние читается через публичные доменные read-контракты; Snapshot не выбирает и не формирует содержимое Input. DAGContext не принимает на себя доменные read/missing/fallback, CRUD или сборку PatchSet.

**Следствие для памяти:** число нод влияет прежде всего на число записей каталога, а размер тяжёлых доменных данных определяется жизненным циклом самих доменных результатов и их ссылок. Объём памяти не должен расти из-за копирования payload каждым уровнем DAG.

### 2.2. POJO нод и вызовы доменов (решение 2026-10-30)

- **Input и Output всегда POJO:** применять действующие требования `dataModel`/Pydantic к строгой типизации, полям, defaults, ограничениям и вложенным объектам. Не вводить для DAG параллельные схемы/полевые валидаторы. Перед созданием нового типа обязательна инвентаризация существующих POJO, `RegistryKey` и enum по `.cursor/rules/contract-creation.mdc`; `dataModel` остаётся SoT доменных данных.
- **Композиция, а не копирование контрактов:** если доменная read/CRUD-операция уже возвращает POJO, подходящий по смыслу, нода может использовать его напрямую как Input или Output. Когда нужно несколько результатов, POJO ноды объявляет типизированные поля существующих доменных POJO. Собственный контракт ноды допустим, когда прямой доменный POJO не выражает требуемый результат. Не изменять доменные POJO исключительно ради формата DAG и не дублировать в ноде их поля/defaults.
- **Формирование Input:** нода объявляет потребность в данных через поля Input и самостоятельно получает доменные POJO из публичных read-операций и/или типизированных Output завершённых зависимостей. Объявление типа поля **не запускает автоматически** поиск/чтение/создание объекта: выбор публичного доменного API и параметров запроса остаётся явным в реализации ноды. Домен владеет read, missing и fallback. Подготовка Input не является поводом запускать скрытый межоперационный pipeline.
- **Выполнение операции:** по решению DAG нода вызывает нужную публичную доменную CRUD-операцию, а не реализует её алгоритм. Одна нода не должна скрывать несколько самостоятельных операций мира с отдельным выбором порядка, условий и жизненного цикла; такие операции декомпозируются на DAG-ноды. Внутренние вычисления одной доменной операции остаются у домена.
- **Запись и публикация:** read не меняет состояние мира; операции изменения подчиняются действующим контрактам доменных Patch, сборки PatchSet в DAG и применения через Snapshot. Прямой persist из ноды в обход этого пути не разрешается. Публикуемый результат ноды — экземпляр её Output POJO, не raw `dict`/`Any`; JSON от LLM должен быть приведён к валидированному POJO до публикации.
- **Граница инфраструктур:** `NodeRegistry` должен связывать ноду с объявленными классами Input/Output, но не дублировать их Pydantic-схемы. Проверять экземпляры и ограничения через существующую POJO-инфраструктуру; специализированные wire-policy, import/runtime resolver и cascade применять только при наличии соответствующей семантики. Общий API регистрации и доступа определён в §6; реализации принадлежат DAG-TYPING-1, конкретные binding нод — GEN-DAG-1.

### 2.2.1. Собственные композиционные POJO ноды и их размещение

Если ноде для работы нужны несколько POJO, в том числе разных доменов, её Input объявляется собственным композиционным POJO с типизированными полями **существующих классов этих POJO**. Нода работает с вложенными объектами через их typed API. Аналогично Output может объединять несколько доменных результатов. Это композиция контрактов, а не разворачивание их полей в новую схему и не новый общий контекст мира.

- Существующий подходящий доменный POJO переиспользуется напрямую из своего домена `backend/app/dataModel/<домен>/`; отдельная обёртка для одного значения не обязательна.
- Новый контракт с самостоятельным доменным смыслом принадлежит соответствующему домену dataModel. Нельзя переносить его в engine только потому, что первым потребителем стала DAG-нода.
- Специальный Input/Output, объединяющий данные для конкретной ноды, размещается в **`backend/app/dataModel/engine/nodes/<группа>/<контракт>.py`**. Группа определяется ответственностью нод, а не случайной нумерацией. Общие runtime-контракты остаются в `backend/app/dataModel/engine/dag/`.
- Композиционный POJO импортирует публичные POJO доменов. Обратных импортов из доменных POJO в engine/nodes, а также импортов application/репозиториев в этот POJO быть не должно. В нём нет read/CRUD, алгоритмов доменов или выбора producer.
- Нода явно объявляет, от каких producers какие контракты требуются; `prepare_input` получает соответствующие результаты или явно вызывает публичные доменные read API и собирает композиционный Input. Тип вложенного поля сам по себе не запускает lookup/read/CRUD.
- Поля, defaults, normalization и validators вложенных доменных объектов не дублируются. Подтверждённо неизменяемые вложенные объекты разделяются без копирования тяжёлых payload; неизменяемость проверяется на всём графе вложений, не только на внешней модели.
- **GEN-DAG-1 обязан для каждой такой ноды записать в её ТЗ** точные классы Input/Output, имена и типы вложенных полей, источники данных, обязательность требований, гарантии неизменяемости и точные пути файлов. До реализации проверить переиспользование существующих POJO и количество файлов в целевых папках. DAG-TYPING-1 задаёт это общее правило, но не создаёт конкретные рабочие композиции.

### 2.3. Сохранение параллельного исполнения DAG (требование 2026-10-30)

- **Существующий механизм не должен деградировать:** `GraphCompiler` формирует топологические уровни; `DAGExecutor._run_level()` запускает независимые Python-ноды одного уровня через `asyncio.gather` и ждёт завершения уровня. LLM-ноды проходят через агрегированные группы по temperature; это не тождественно отдельному параллельному вызову каждой LLM-ноды.
- **Типизированный DAGContext должен работать при одновременном исполнении:** чтение завершённых зависимостей и публикация результатов нескольких нод не должны обнаруживать частично сформированный Output или общую изменяемую вложенную структуру. Не заменять параллелизм глобальной блокировкой/последовательным исполнением ради упрощения контекста. Применяется барьерная публикация с единственным writer-координатором по §§7–8; это согласованное решение.
- Приёмка типизации включает проверку фактического одновременного исполнения независимых Python-нод, успехов/ошибок/отмены на одном уровне, неизменности Output и сохранения LLM aggregation/repair.

## 3. Границы ответственности

| Составляющая | Владелец |
|---|---|
| Объявление Input/Output, подготовка конкретного Input | Нода |
| Выбор, зависимости, порядок и условия исполнения | DAG |
| Доменные read/missing/fallback и реализация CRUD | Домен |
| Валидация границ исполнения и учёт статусов/ошибок | Engine execution runtime |
| Хранение результатов завершённых нод | DAG runtime |
| Сбор PatchSet | DAG |
| Применение и история состояния | Snapshot с доменными storage-контрактами |

## 4. Граница общего контракта и конкретных нод

DAG-TYPING-1 владеет общими API и инфраструктурой §§6–12. GEN-DAG-1 определяет конкретные Input/Output **всех** рабочих нод (Python и LLM), явные producer/contract requirements, доменные read/operation bindings, business validators и пользовательские выходы. Конкретные поля рабочих нод этим ТЗ не задаются. Удаление legacy-нод также выполняется в GEN-DAG-1. Runtime-каналы удаляются в DAG-TYPING-1 после миграции всех их потребителей; adapters и смешанный режим не вводятся.

## 5. Статус старого предложения о доменных контекстах

Ранее предлагались общие поля `ExecutionState.terrain_context`, `scene_context`, `combat_context`, `structure_context` и отдельный `REQUIRES`. **Это не утверждённый целевой канал обмена между нодами.** Принятое направление — собственные типизированные Input/Output каждой ноды и существующие `deps`. Не создавать глобальный набор доменных контекстов или второй механизм зависимостей без отдельного доказанного требования.

Миграция рабочего кода не начата. Текущие `shared_context` и `NodeResult` остаются до согласованного шага реализации.

## 6. Общий typed-call и регистрация

### 6.1. Типы, идентичность и декларации

`I` и `O` — Pydantic POJO (`BaseModel`), неизменяемые вместе с вложениями. Доменные классы принадлежат dataModel своего домена, специальные композиции нод — dataModel/engine/nodes по §2.2.1; application не копирует поля и схемы. Выбор доменного класса, композиции и factory конкретной ноды — GEN-DAG-1.

- `ExecutionPhase(StrEnum)` в `dataModel/engine/dag/executionPhase.py` — единый контракт фаз: PRE_LLM = pre_llm, LLM = llm, POST_LLM = post_llm. `PythonExecutionPhase = Literal[ExecutionPhase.PRE_LLM, ExecutionPhase.POST_LLM]`; PythonNode использует его с default ExecutionPhase.PRE_LLM. Конструктор ноды вызывает `validate_python_phase`: Python API принимает только экземпляр enum из Python-подмножества, строки и LLM отклоняются. Общая admission-функция переиспользует Pydantic TypeAdapter по alias, без отдельной схемы в application. ExecutionDiagnostic.phase использует полный ExecutionPhase; его strict Python API отклоняет строки, JSON-граница принимает только перечисленные wire-значения. Прежние production-ноды переключаются по GEN handoff.
- `NodeId`, `ExecutionId`, `ContractId`, `ContractVersion`, `PlanRevision`, `DomainRevision` — различимые типы идентификаторов/версий. Строковое представление здесь допустимо как открытый технический идентификатор, а не закрытый enum или ключ world-registry. `attempt` — положительное целое, монотонное для `(execution_id, node_id)`; resume не сбрасывает счётчик. ExecutionId создаётся один раз на новый запуск; это runtime ID, не deterministic world UID.
- `ExecutionIdentity(execution_id, node_id, attempt, plan_revision)` — адрес попытки. Ревизия плана — метаданные, ключ результата: execution/node/attempt.
- `OutputRef[O](producer: NodeId, output_type: type[O])` связывает производителя с классом результата. `RequiredOutput[O]` и `OptionalOutput[O]` содержат такую ссылку и задают обязательность; это объявления данных на рёбрах `deps`, не второй граф.
- `NodeContract[I,O](input_type: type[I], output_type: type[O], contract_id: ContractId, version: ContractVersion, reads: tuple[RequiredOutput|OptionalOutput,...])`. Гетерогенность reads допустима только внутри binding; `require`/`optional` сохраняют конкретный `O` для вызывающего.
- `NodeRegistration[I,O]` связывает node/factory/executor с этим контрактом. Схема получается из POJO. Нельзя регистрировать два несовместимых binding одного NodeId. Общий registry не импортирует конкретные ноды и dataModel доменов.
- До исполнения GraphCompiler проверяет объявленные producers, соответствие `deps`, классов Output, порядок фаз и групп. Требование прочитать результат внутри того же LLM-запроса недопустимо; зависимость только по порядку сохраняется. Условно исключённый producer допустим в описании графа, но required чтение без доступного актуального Output завершается ошибкой подготовки Input; optional возвращает отсутствие. Runtime повторно проверяет тип/доступность/актуальность.

### 6.2. Сигнатуры и владельцы

Сигнатуры ниже — общий обязательный API, не пример реализации. `ReadView` привязан к потребителю и его объявлениям; публичного произвольного `dict.get(node_id)` нет.

| API | Контракт |
|---|---|
| `NodeRegistry.register_python[I,O](node_cls, executor_cls, contract: NodeContract[I,O]) -> type` | binding, существующие decorator wrappers делегируют сюда; создание конкретной ноды — typed factory интеграции |
| `NodeRegistry.register_llm[I,O](node_cls, contract: NodeContract[I,O]) -> type` | один Output POJO является источником схемы и публикации |
| `BaseNode[I,O].prepare_input(view: DAGReadView) -> Awaitable[I]` | нода явно читает объявленные Output и внедрённые доменные read-сервисы; request/session данные нода получает через typed factory, не общий services dict |
| `PythonNode[I,O].execute(input: I) -> Awaitable[O]` | прямой Output; управляющий gate через существующий объявленный `PythonNodeError`, который runner переводит в runtime-исход |
| `PythonExecutor.execute(node: PythonNode[I,O], input: I) -> Awaitable[O]` | Protocol A1.2; target PythonNodeExecutor реализует его в A2.3, тонкая делегация без подготовки Input/доменных алгоритмов |
| `DAGReadView.require(req: RequiredOutput[O]) -> O` | проверяет объявление и доступность, фиксирует точную прочитанную версию |
| `DAGReadView.optional(req: OptionalOutput[O]) -> O | None` | отсутствие тоже записывается в provenance; несовпадение типа не превращается в None |
| `DAGReadView.record_domain_read(domain: str, revision: DomainRevision | None) -> None` | фиксирует подтверждение согласованного чтения со стороны доменного read-контракта; None означает отсутствие доказательства reuse между запусками, но не разрешение несогласованного чтения |
| `DAGContext.begin_attempt(node_id: NodeId, plan_revision: PlanRevision) -> ExecutionIdentity` | только координатор; инвалидирует прежний Output и потребителей до создания read view |
| `DAGContext.read_view(consumer: NodeId) -> DAGReadView` | снимок актуальных записей до запуска уровня, ссылки на неизменяемые payload |
| `DAGContext.publish_level(outcomes: tuple[NodeOutcome,...]) -> LevelDecision` | только координатор, без await внутри изменения каталога; проверяет открытые attempts и фиксирует все исходы барьера |
| `NodeRunner.run(node, view, identity) -> Awaitable[NodeOutcome[O]]` | prepare → boundary validation → execute → boundary validation, локальный outcome, никаких общих записей |

`domain` в record_domain_read — явный технический namespace публичного read-контракта, допустимый открытый str; это не автоматический поиск сервиса. Контекст хранит только evidence, не выбирает доменные поля. Доменные зависимости/ревизии конкретной ноды определяются GEN-DAG-1.

`NodeRegistration` хранит декларацию, а экземпляр ноды создаёт typed factory интеграции перед исполнением. В `ExecutionBindings` передаётся request-local binding `make_node[I,O](registration: NodeRegistration[I,O]) -> BaseNode[I,O]`; конкретная factory сохраняет точный I/O и внедряет доменные readers/request POJO. Закрытый runtime lookup проверяет соответствие экземпляра зарегистрированному контракту. Request-local bindings не мутируют глобальную регистрацию и не передают session через свободный dict. Generic registry не вызывает доменные readers и не пытается сконструировать конкретную ноду по типам её полей.

`ResolveResult[O]` — общий POJO ответа: `ok: bool`, `data: O | None`, `error: str | None`; `error` — свободный пользовательский текст, не код ветвления. Он объявляется в `application/engine/contracts/executionBindings.py`, а ResponseResolver импортирует его, не наоборот. `ResponseBinding.resolve(view) -> ResolveResult[O]`, `TransitionBinding.transition(view) -> TaskType | None`. `SnapshotExtension[E: BaseModel]` объявляет ContractId/version и `capture() -> E`, `restore(value: E) -> Awaitable[None]`; runtime хранит typed E без интерпретации полей. Конкретный E и фабрики принадлежат GEN-DAG-1.

`NodeOutcome[O]` — внутренний исход runner, а не возвращаемая нодой обёртка: identity, типизированный NodeStatus, Output только для success, прочитанные версии, диагностика, timestamps и необязательный управляющий сигнал. `NodeStatus` переиспользуется и дополняется `CANCELLED`, `GATED`; существующие IDLE/READY/RUNNING/SUCCESS/FAILED/BLOCKED сохраняют смысл. `LevelDecision` — закрытый enum CONTINUE/CANCEL/FAIL/REPLAN. Диагностика имеет enum code/severity; свободный текст message/reason допускается как пояснение, не управляющий discriminator. Gate-сигнал содержит существующий TaskType и причину, поэтому остаётся в application; pure dataModel не импортирует TaskType из application.

Внутреннее закрытое гетерогенное хранилище допускает object; наружу типизированное чтение возвращает O после проверки класса. `Any` и непроверенные cast у потребителей запрещены. Валидация структуры выполняется существующей Pydantic/ContractValidator инфраструктурой, business validation остаётся у зарегистрированного валидатора; не строить вторую схему.

### 6.3. Метаданные A1.1: представление и admission

Технические идентификаторы §6.1 представлены отдельными NewType над str; Pydantic aliases запрещают пустые строки, крайние пробелы и неявный coerce из чисел. ExecutionIdentity.result_key — `(execution_id, node_id, attempt)`, plan_revision в ключ не входит. attempt — strict int >0, bool недопустим. Все метаданные frozen/extra-forbid/strict с revalidation экземпляров; неизменяемость вложений проверяется существующим `app.dataModel.validation.immutableValue.validate_immutable`, отдельный механизм DAG не создаётся.

- `DependencyRead`: producer, contract_id, contract_version, required, result: ExecutionIdentity | None. None фиксирует отсутствие; при result producer совпадает с result.node_id.
- `DomainReadEvidence`: domain (открытый непустой namespace read-контракта), revision: DomainRevision | None. Это evidence актуальности для reuse, не разрешение несогласованного чтения.
- `OutputRecord[O]`: identity, contract_id, contract_version, output: O, reads: tuple[DependencyRead,...], domain_reads: tuple[DomainReadEvidence,...]. Пустые tuple означают отсутствие фактических чтений. Output принимается только как готовый экземпляр объявленного POJO; raw dict и другой класс отклоняются. Сохраняется идентичность payload, включая классы с revalidate_instances=always. Проверка схемы/семантики самого Output выполняется на границе ноды, record не копирует и не повторяет её. Глубокая неизменяемость проверяется общим валидатором. У успешного Output нет отсутствующего required чтения или ссылки на результат другого execution. Это memory record, не универсальный JSON-десериализатор доменных Output.
- `SnapshotMetadata`: format_version (strict int >0), execution_id, plan_revision, pass_number (strict int >=0), contract_versions: tuple[(ContractId, ContractVersion),...], attempt_counters: tuple[(NodeId, attempt),...]. Tuple сохраняет неизменяемость; повторяющиеся contract/node keys запрещены. Текущую поддерживаемую версию формата задаст snapshot service A3.1, метаданные не подменяют проверку совместимости restore.
- `ExecutionDiagnostic`: identity, pass_number, phase: ExecutionPhase, level, timestamp, code, severity, status, message; requirements: tuple[(NodeId, ContractId, ContractVersion, required),...], reads, saved_outputs, sibling_statuses, cancel_source: CancellationSource | None, cancel_reason: CancellationReason | None, cancel_message: str | None, cancel_requested_at/observed_at/completed_at, causes: tuple[ExecutionDiagnostic,...]. Требования и фактические чтения разделены. Unix timestamps — конечные неотрицательные seconds; None для необязательных моментов означает неизвестность. message и cancel_message — свободные пояснения, не управляющие discriminator. cancel_source и cancel_reason — только enum; для cancellation они обязательны, неизвестность задаётся явно значением UNKNOWN, не None. Пояснение cancel_message необязательно. Связанные ошибки/gates/save outcomes передаются causes без payload. status итогового события уровня отражает решение (success/cancelled/failed/gated); application LevelDecision остаётся отдельным runtime-контрактом.
- Закрытые ExecutionEventCode A1.1: node_started, node_finished, cancel_requested, cancel_observed, level_finished, replan_requested, snapshot_saved, snapshot_failed, restore_failed. ExecutionSeverity: debug/info/warning/error. Новые события при дальнейших шагах добавляются в этот SoT и enum совместно; свободные event-коды недопустимы.

Классификация отмены в `dataModel/engine/dag/diagnostics.py`:

| Enum | Значение | Смысл |
|---|---|---|
| CancellationSource | USER | явный запрос пользователя |
| CancellationSource | PARENT | отмена родительского запуска/задачи |
| CancellationSource | NODE | отмена инициирована самой нодой |
| CancellationSource | TIMEOUT | отмена инициирована контролем срока/таймаута |
| CancellationSource | UNKNOWN | источник не установлен |
| CancellationReason | REQUESTED | явный запрос остановки |
| CancellationReason | PARENT_CANCELLED | распространение отмены родителя |
| CancellationReason | NODE_CANCELLED | самостоятельная отмена ноды |
| CancellationReason | DEADLINE_EXCEEDED | истёк срок ожидания/исполнения |
| CancellationReason | UNKNOWN | причина не установлена |

Wire-значения enum — lowercase snake_case имён. Python API принимает экземпляры enum, не строки; Pydantic JSON-граница принимает только перечисленные wire-значения. Не выводить источник/причину из текста сообщения или самого факта CancelledError: при отсутствии подтверждённых метаданных producer выставляет UNKNOWN. Таблица классифицирует события и не вводит новые таймауты/политику отмены. Независимые оси source/reason не требуют искусственного взаимно-однозначного соответствия.

### 6.4. Декларации до реализации и безопасные импорты (preflight A1.2)

- `DAGReadView` — Protocol в `backend/app/application/engine/contracts/dagReadView.py`, создаётся в A1.2. Методы require/optional/record_domain_read определены §6.2. Модуль зависит от OutputRef/RequiredOutput/OptionalOutput и dataModel ID, но не от каталога, NodeRegistry или конкретных нод. `PublishedDAGReadView` в `backend/app/application/engine/runtime/dag/context/dagReadView.py` реализует этот интерфейс в A2.1. Объявление Protocol — законченный контракт, не временная stub-реализация.
- `PythonExecutor` — Protocol в `backend/app/application/engine/contracts/pythonExecutor.py`, создаётся в A1.2. Метод execute generic по I/O и сохраняет связь типов PythonNode[I,O], input I и результата O. Модуль зависит от нейтрального nodeTypes, но не импортирует реализацию runner/executor. `PythonNodeExecutor` в `backend/app/application/engine/runtime/execution/pythonNodeExecutor.py` реализует его в A2.3. Прежний production executor `(node,state,context)->NodeResult` не используется целевым API.
- OutputRef/NodeContract/ExecutionBindings находятся соответственно в `engine/contracts/outputRef.py`, `nodeContract.py`, `executionBindings.py`; registry/registration — в `engine/registration/nodeRegistry.py`, `nodeRegistration.py`; BaseNode/PythonNode/LLMNode/CompiledNode — в `engine/nodeTypes/baseNode.py`, `pythonNode.py`, `llmNode.py`, `compiledNode.py` (все пути относительно `backend/app/application/`). Их импорты не запускают `engine/nodes/__init__.py`.
- NodeKind/NodeCost/PythonNodeError переиспользуются через перенос существующих определений в `engine/nodeTypes/support/nodeKind.py`, `nodeCost.py`, `pythonNodeError.py`. В A1.2 одновременно обновляются все старые и новые consumers; поведение/значения этих деклараций не меняются, копий/re-export не остаётся. Это import-only перенос, не миграция конкретных контрактов нод.
- Целевая NodeRegistration хранит тип executor через PythonExecutor Protocol; NodeContract обязателен для каждой новой регистрации. В A1.2 target registry существует как явно создаваемый isolated instance. Никаких auto-import concrete модулей, optional contract, sys.modules-подмен или adapter старого execute в новый нет.
- TYPE A1.2 включает declarations и fake реализации портов. Реализации runtime ещё отсутствуют и не импортируются даже для аннотаций. Проверяются связи типов required/optional чтения, prepare_input, execute и response; отсутствие body каталога/executor не компенсируется Any.

## 7. Уровень, барьер и актуальность

Координатор определяет исполняемые ноды уровня, вызывает begin_attempt для каждой, выполняет инвалидацию, затем формирует read views и одновременно запускает задачи через gather(return_exceptions=True). Вызовы доменных API и LLM не удерживают общую блокировку. Задачи видят только результаты, опубликованные до уровня; завершившийся сосед недоступен.

Координатор собирает outcomes, сверяет attempts и публикует успешные Output/статусы/метаданные на барьере. Output заморожен вместе с вложениями; frozen=True на внешней модели недостаточно. Не менять доменный POJO только ради DAG: несовместимый mutable контракт должен быть исправлен владельцем или представлен допустимой доменной ссылкой в GEN-DAG-1. Отсутствие такой возможности блокирует конкретную интеграцию.

Закрытие записи attempt выполняется при commit координатора, а не при локальном завершении задачи. После commit повторная/поздняя публикация запрещена. Trace хранит ссылки-идентификаторы, не payload. Следующий уровень допускается только при CONTINUE.

При begin_attempt прежний Output немедленно перестаёт быть актуальным. Инвалидируются фактические потребители старой версии и транзитивные потребители их Output. Учёт фактических чтений дополняет декларации из §6, но не создаёт второй граф scheduling. Отсутствие optional результата — также наблюдение, изменение которого инвалидирует потребителя. Ошибка повторного запуска не оживляет старый Output. Зависимость только по порядку не инвалидирует данные. Reuse доменных чтений требует подтверждённой актуальности ревизии; без неё нода исполняется заново.

## 8. Ошибки, отмена, gate и LLM

Обычная ошибка Python-задачи не отменяет соседей: координатор ждёт всех, сохраняет успехи и завершает уровень FAIL. При отмене одной задачи остальные завершаются, успехи сохраняются, решение CANCEL; сопутствующие ошибки и gate-сигналы остаются в диагностике. При отмене всего запуска координатор отменяет незавершённые задачи, ожидает их очистки, фиксирует уже завершённые валидные outcomes и сохраняет resume-снимок. CancelledError не считается success и не теряется в обработке Exception.

Gate разрешён в pre_llm согласно engine-nodes: на барьере один gate означает REPLAN, несколько — FAIL конфликт. Gate не маскирует ошибку/отмену. После решения REPLAN следующий уровень и LLM не запускаются; это согласованное изменение остановки после всей pre_llm-фазы. Приоритет остановки: отмена → ошибка (включая конфликт gate) → один gate → продолжение. Все причины сохраняются независимо от итогового приоритета.

LLM temperature-группа — один исходный запрос и существующий repair в той же conversation. `LLMGroupPayloadBuilder` получает заранее подготовленные POJO Input по binding; wire JSON формируется только на границе клиента. `contract_json` заменяется ссылкой на output_type в общем binding; генерация strict schema переиспользует существующий schemaBuilder. Семантические валидаторы конкретных нод и их миграция принадлежат GEN-DAG-1.

После repair все секции повторно проходят структурную/семантическую проверку; публикация группы целиком как одного batch происходит только после успеха всех. При неуспехе/отмене частичные секции не становятся доступными Output. Полностью актуальная группа при resume не вызывает LLM; незавершённая или инвалидированная группа выполняется целиком. Repair-вызовы допустимы, скрытое дробление на запросы отдельных нод запрещено. LLM-нода не получает Output соседа этой же группы для подготовки Input.

## 9. Resume, ссылки и retention

SnapshotStore сейчас in-memory; DAG-TYPING-1 сохраняет этот класс хранения. Гарантируется resume после штатной отмены и успешного save, не после падения процесса. Snapshot включает format_version, версии контрактов, execution_id, счётчики попыток, ревизию плана/pass, актуальные immutable Output с provenance, runtime-статусы/управление и ссылки на ещё не применённые эффекты. Конкретные payload эффектов и их дедупликация — контракт GEN-DAG-1/PatchSet/Snapshot, не новое поле Any.

`ExecutionSnapshotService.capture(state) -> SessionSnapshot` и `restore(snapshot, registry) -> Awaitable[ExecutionState]`: проверить format/contract versions и доменные ссылки до допуска к исполнению. Несовместимость версии или отсутствующий/недействительный объект ссылки — явная ошибка с producer/attempt/ref/reason; без автоматической миграции, пустых подстановок и скрытой генерации. Исходный snapshot сохраняется. Поддержка старых свободных snapshots не вводится.

Для Output с доменными ссылками registry binding получает typed lifecycle callback `validate_restored(output: O) -> Awaitable[None]`, реализованный доменом/интеграцией. Для value-only Output — стандартная проверка класса/неизменяемости. Runtime не декодирует доменную ссылку по типу поля и не выбирает API автоматически.

Активное исполнение и сохранённый снимок удерживают нужные payload/ссылки; snapshot ссылается на те же immutable данные без копирования между уровнями. Завершение запуска освобождает его владение, удаление/замена snapshot — владение снимка; trace не удерживает payload. Доменные lease/pin/release, если требуются ссылке, выполняются её существующим storage-контрактом через lifecycle binding. Новая универсальная система хранения ссылок не вводится. Exactly-once внешнего LLM-запроса при потере ответа и дедупликация применения эффектов здесь не гарантируются.

## 10. Диагностика и логирование

Единственный emitter `dagLog.emit(event: ExecutionDiagnostic) -> None` в application/engine/diagnostics. Logger `app.engine.dag` через существующий loggingConfig направляется в server sink `backend/logs/engine/dagExecution.log` (domain engine, service dagExecution). Новый router/handler/форматтер не создавать. Схема маршрута — docs/tz_logging.md; событие и payload — настоящее ТЗ.

Обязательные поля: execution_id, plan_revision, pass, phase, level, node_id, attempt, timestamp, status/outcome, typed event code/severity. Для отмены — requested/observed/completed time, типизированные source/reason (явные CancellationSource.UNKNOWN/CancellationReason.UNKNOWN при отсутствии), необязательный cancel_message, объявленные producer/contract/required, реально прочитанные версии/absence, исходы соседей, идентификаторы сохранённых Output, ошибки и gates, решение остановки, save snapshot success/failure. INPUT/OUTPUT payload не логируются целиком; корреляция по ID, а не порядку строк.

ERROR: fail/конфликт/невалидный snapshot; WARNING: cancel; INFO: lifecycle/pass/level/replan и итог сохранения; DEBUG: детали требований и read evidence. Для диагноза отмены обязательные сведения сохраняются в событии отмены/барьера независимо от включённости DEBUG. Trace фиксирует те же идентификаторы; один факт не эмитится повторно задачей и координатором. Задачи сообщают локальные факты, координатор владеет итоговыми состояниями.

## 11. Подключение и разделение планов

Целевые runtime-компоненты создаются по постоянным путям `backend/app/application/engine/runtime/` (карта DAG-TYPING-1); typed SessionSnapshot/SnapshotStore — в `backend/app/application/cancellation/typed/`. Старые реализации не подмешиваются в target и остаются подключены к production Container до handoff. До этого target исполняется только в изолированных тестах с typed registry/ports. Временное сосуществование predecessor и target исходников не означает поддержку двух production runtime: нет межрежимных вызовов/адаптеров, одновременно в запросе используется только один граф исполнения.

GEN-DAG-1 задаёт все конкретные контракты/factories и создаёт явный bootstrap `backend/app/application/engine/registration/productionNodes.py`: `register_production_nodes(registry: NodeRegistry) -> None`. В одном шаге подключает его и target runtime в `backend/app/core/container/engine.py`, обновляет caller imports на runtime/cancellation/typed, убирает прежнюю side-effect регистрацию из `engine/nodes/__init__.py` и переводит concrete-ноды на нейтральные nodeTypes. До этого шага старый bootstrap и его decorators работают по прежнему API; target NodeRegistry при этом никогда не принимает legacy-декларации. После handoff B2 DAG-TYPING-1 удаляет predecessor общие файлы по карте, а GEN-DAG-1 — конкретные legacy-ноды. Не создавать второй постоянный путь исполнения.

При полном переключении сохраняются один runtime/registry и один источник результатов. Общесистемные free node_results/shared_context/NodeResult удаляются только после проверки всех usages. Concrete response mapping и извлечение полей вроде intents не входят в generic engine; GEN-DAG-1 предоставляет typed callback `resolve(view) -> ResolveResult` и `transition(view) -> TaskType | None` по общему интерфейсу. Это механизм применения уже существующего решения, не новый бизнес-gate в runtime.

PatchApplier сейчас лишь повторно пишет node_results и не доказывает транзакционное применение доменных эффектов. Его замена/конкретный effect binding относятся к GEN-DAG-1. DAG-TYPING-1 не маскирует этот путь универсальным dict-адаптером. SQL, crash recovery, новый persistent store, HTTP, world materialization и конкретные схемы нод — вне общего плана.

## 12. Приёмка общего механизма

Обязательны тестовые producers/consumers с required/optional и order-only deps, статические positive/negative проверки API, overlap через управляемый asyncio.Event барьер, разные порядки завершения, fail/cancel/gate, invalidation chain/diamond и optional absence, immutable вложения, LLM group+repair без реального клиента, snapshot version/ref errors и retention без копий payload. Негативные typing fixtures должны проверять точные ожидаемые ошибки, а не любой ненулевой exit code.

Оркестраторы отвечают только за порядок, зависимости, lifecycle и передачу typed результатов. Внутренние callbacks/dispatch/helpers проверяются так же; смена доменного алгоритма не требует изменения runtime. Каждый шаг плана фиксирует эту проверку и baseline delta кратко, без копирования кода. Конкретные пользовательские сценарии и доменная приёмка — GEN-DAG-1.
