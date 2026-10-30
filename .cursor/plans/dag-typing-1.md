# DAG-TYPING-1 — общесистемная типизация engine DAG

**Статус:** DRAFT — самостоятельный **план реализации** общесистемной типизации DAG. Принципы Input/Output, DAGContext и решения исполнения ниже согласованы 2026-10-30 до подготовки ТЗ. **Сначала согласуются и реализуются архитектурные изменения инфраструктуры, только затем мигрируются ноды.** Документ не разрешает изменять код без отдельного согласования с мастером.
**Область:** весь существующий engine DAG — Python-ноды, LLM-ноды, NodeRegistry, DAGContext, execution runtime, replan/resume/repair и диагностика. **Не часть GEN-DAG-1:** интеграция генератора с DAG остаётся самостоятельной задачей; граница работ и зависимость точки переключения явно заданы в пункте 8 и разделе «Стык планов без совместимого слоя».
**Нормативные документы:** `docs/tz_engine_node_context.md` (подробные решения и ответственность), `.cursor/rules/engine-nodes.mdc`, `.cursor/rules/contract-creation.mdc`, `.cursor/rules/dataModel-no-hardcode.mdc`, `.cursor/rules/type-kind-str-fields.mdc`, `docs/tz_json_validation.md`. Для стыка генератора: `.cursor/plans/gen-dag-1-post-geo-ws.md`.

## Цель и граница

### Готовность и граница поставки

Архитектура согласована. Карта компонентов, точные пути, API, атомарные шаги и проверки приведены ниже; ТЗ синхронизировано с решениями. Разрешена подготовка документации; реализация кода начинается только по отдельному запросу. A0 завершён документально; A1.1 реализован и проверен; A1.2–A3 и B не выполнены. Конкретные контракты **всех** рабочих нод и их миграция принадлежат GEN-DAG-1; инфраструктура проверяется на тестовых нодах. Полная приёмка B зависит от интеграции GEN-DAG-1, но A1–A3 не ждут её завершения.

Предоставить общий механизм обязательных типизированных Input/Output для **каждой** ноды и обмена опубликованными результатами между нодами без превращения DAG в доменный resolver, новую POJO-инфраструктуру или владельца CRUD. Изменение состава/порядка DAG не должно требовать изменения реализации доменных операций при сохранении их публичных контрактов.

Граф зависимостей по исполнению уже определён через `BaseNode.deps` и `GraphCompiler`; второй механизм `REQUIRES` не вводить. Текущие `NodeResult.data: Any`, `ExecutionState.node_results: dict[str, object]` и `shared_context: dict` — legacy, а не образец целевой архитектуры.

**Существующий параллелизм — обязательный инвариант:** `GraphCompiler` строит топологические уровни; `DAGExecutor._run_level()` запускает независимые Python-ноды одного уровня одновременно через `asyncio.gather(..., return_exceptions=True)` и ожидает завершения уровня перед следующим. LLM-ноды исполняются агрегированными группами по temperature; это другая семантика, её не подменять отдельными одновременными вызовами. Типизация не вправе последовательно выполнять все ноды, вводить глобальную блокировку, ломать уровни/фазы, replan/gate или вызывать повторные LLM-запросы без отдельного согласования.

## Принятые архитектурные решения (2026-10-30)

1. **Контракты каждой ноды:** обязательные, статически объявленные **Input и Output POJO** по действующим правилам `dataModel`/Pydantic. Нода формирует конкретный Input самостоятельно; Output возвращается непосредственно как значение заявленного POJO. `NodeResult(data: Any)` не сохранять ради обёртки без дополнительной подтверждённой семантики.
2. **Семантическое переиспользование POJO:** если публичный read/CRUD домена возвращает подходящий POJO, нода может напрямую использовать его в Input/Output. Если нужно несколько объектов — объявить собственный композиционный POJO с типизированными полями доменных POJO. Отдельный контракт ноды допустим при иной семантике; не модифицировать доменный POJO лишь ради формы DAG и не дублировать его поля, defaults и нормализацию. Собственная композиция Input/Output ноды размещается в `backend/app/dataModel/engine/nodes/<группа>/<контракт>.py` и содержит вложенные объекты существующих POJO, в том числе разных доменов, без разворачивания/копирования их схем. Доменные POJO остаются в своих доменах; общие runtime-типы — в `dataModel/engine/dag/`. Нормативное правило — `docs/tz_engine_node_context.md` §2.2.1; GEN-DAG-1 обязан явно описать конкретные композиции и точные пути в ТЗ нод до кода.
3. **Получение данных:** нода явно вызывает публичные доменные read-контракты и может читать типизированные Output завершённых зависимостей. Объявление поля Input POJO **не** запускает автоматический поиск/CRUD по его типу. Домены владеют read/missing/fallback; каждая стадия читает согласованное исходное состояние. Snapshot не решает, какие поля отдать ноде.
4. **Выполнение:** DAG выбирает операции, зависимости, условия и порядок; нода делегирует вызов публичному API нужного домена. Алгоритмы и CRUD принадлежат домену. Нельзя скрывать за нодой несколько самостоятельных операций мира с собственным внешним жизненным циклом; внутренние вычислительные шаги одной доменной операции остаются у домена.
5. **Контекст результатов:** логический `DAGContext` — разреженный каталог опубликованных типизированных Output по производителям, а не копия мира и не гигантский `TerrainContext`/`SceneContext`. Input короткоживущий по умолчанию. Малый Output может храниться непосредственно; крупный — содержать типизированные доменные ссылки, если это предусмотрено самим контрактом. Не копировать подтверждённо неизменяемые, включая вложенные данные, payload между уровнями DAG. **Параллельные ноды одного уровня не должны видеть частично сформированные результаты друг друга**; применяется барьерная публикация уровня и правила идентичности/времени жизни из раздела согласованных решений ниже.
6. **Валидация:** переиспользовать POJO/Pydantic, строгие `RegistryKey`/enum и существующие ограничения. `NodeRegistry` должен связывать ноду с её типами Input/Output, не копируя Pydantic-схемы. LLM JSON — транспортная форма, в контекст публикуется только валидированный Output POJO. Не дублировать механизмы `jsonValidation` и каскада там, где их семантика не применима.
7. **Runtime и эффекты:** статусы, ошибки, replan, repair, cancellation и trace — ответственность execution runtime, не обязательные поля каждого Output. Output не обязан быть Patch/PatchSet. Сбор PatchSet — ответственность DAG в пределах отдельно согласованных контрактов, применение/история — Snapshot; прямые persist-записи из нод не вводить.

Подробное объяснение и границы ответственности — в `docs/tz_engine_node_context.md`. ТЗ §§6–12 синхронизировано с решениями плана; новые расхождения устраняются в документах до кода, без повторного выбора утверждённой архитектуры. **Принятые пункты не являются разрешением немедленно мигрировать работающий код.**

## Согласованные решения исполнения (2026-10-30)

**Статус: согласовано пользователем до подготовки ТЗ.** A0 сверяет реализацию с этими решениями и составляет карту изменений. Агент не выбирает архитектуру заново при написании ТЗ. При обнаружении несовместимости он описывает конкретное противоречие и возвращает изменение решения на согласование в этот план. Детализация сигнатур и размещения типов не должна менять приведённую семантику.

1. **Идентичность.** Результат адресуется `execution_id + node_id + attempt`; resume сохраняет `execution_id`, повторное исполнение получает новый `attempt`. Ревизия плана хранится отдельно. Каталог различает исторический результат и актуальный результат; наличия записи по `node_id` недостаточно для reuse. После фиксации координатором исхода попытки её запись закрывается; повторная или поздняя публикация запрещена. Локальное завершение задачи ещё не является закрытием записи: координатор фиксирует её исход на барьере, в том числе при штатной отмене уровня.
2. **Доступность и типы.** На начало уровня формируется read-only представление опубликованных результатов. Нода заранее явно объявляет, от какого производителя какой контракт Output ей требуется и является ли чтение обязательным. Объявления связываются с Input/Output через NodeRegistry без копирования POJO-схем; производитель должен присутствовать в `deps`. До исполнения проверяются существование производителя, совместимость объявленных контрактов и соответствие `deps`; runtime дополнительно проверяет доступность и актуальность результата. Чтение необъявленного производителя/контракта запрещено. `deps` остаётся единственным графом исполнения; объявления контрактов уточняют данные на его связях, а не создают независимый реестр порядка. Обязательное чтение при отсутствии результата завершает подготовку Input ошибкой runtime; необязательное явно возвращает отсутствие. Несовпадение типов всегда является ошибкой. Доменные missing/fallback остаются в домене. Статический API сохраняет конкретный тип POJO; динамические идентификаторы дополнительно проверяются runtime. Схемы остаются в POJO/Pydantic.
3. **Параллелизм.** Независимые Python-ноды уровня одновременно исполняются через `asyncio.gather`. Задача возвращает локальный исход исполнения; каталог, статусы и trace обновляет координатор. Output публикуются на барьере после завершения задач уровня. Соседи не читают Output друг друга даже после раннего завершения. Исполнение доменных операций, I/O и LLM не удерживает общую блокировку. Локальный runtime-исход не заменяет публичный Output обёрткой `NodeResult(data: Any)`.
4. **Ошибки, отмена, gate.** При ошибке Python-ноды соседи завершаются; успешные Output сохраняются, следующий уровень не запускается. При отмене запуска незавершённые задачи отменяются и ожидаются, завершённые валидные результаты сохраняются для resume. Отмена не является успехом. Gate обрабатывается после барьера: следующий уровень и LLM не запускаются, управление возвращается для replan. Несколько gate-сигналов уровня — ошибка конфликта независимо от порядка завершения; ошибка уровня не маскируется replan. Остановка на границе уровня при gate — согласованное изменение текущей проверки после всей pre-LLM-фазы.
5. **Инвалидация.** Runtime записывает версии Output, реально прочитанные в рамках заранее объявленных требований при подготовке Input, включая отсутствие необязательного результата. Учёт чтений дополняет явные объявления ноды и не выводит её контракты автоматически из исполнения. Это метаданные исполнения, не второй граф зависимостей. Изменение прочитанной версии инвалидирует потребителя и транзитивных потребителей его результата; зависимость только по порядку сама по себе не инвалидирует данные. Для доменных чтений reuse допускается лишь при подтверждённой актуальности исходного состояния; без гарантии домена нода исполняется заново. `_should_skip()` и `skip_on_replan` не обходят проверку актуальности.
6. **LLM-группа.** Temperature-группа остаётся единицей исполнения и публикации: один исходный запрос и существующий repair, затем публикация всех валидированных Output целиком. Output соседа внутри этого же запроса недоступен как завершённый результат при подготовке Input. Требование такого чтения — несовместимый контракт, а не повод скрыто дробить запрос. При resume полностью актуальная группа переиспользуется; незавершённая или инвалидированная исполняется целиком.
7. **Lifetime/resume.** Каталог содержит неизменяемые, включая вложения, Output либо предусмотренные доменным контрактом ссылки. Trace содержит идентификаторы результатов и диагностику без тяжёлых payload. Данные удерживаются, пока нужны активному исполнению или сохранённому resume-снимку; история попыток сама по себе не удерживает payload. Resume восстанавливает актуальность, управляющее состояние и ещё не применённые эффекты, а не только `node_results`. Прямые persist-записи из нод не вводятся; состав доменных PatchSet остаётся за соответствующей интеграцией.
8. **Конкретные контракты и удаление legacy — GEN-DAG-1.** GEN-DAG-1 определяет Input/Output, явные требования producer/contract, factories, read/operation bindings и валидаторы всех рабочих Python/LLM-нод; мигрирует конкретные consumers, task transitions, response/effect mappings и удаляет legacy-ноды. DAG-TYPING-1 реализует общую инфраструктуру без полей конкретных нод, использует только тестовые POJO для проверки generic API. Адаптеры legacy/typed и смешанный production runtime запрещены. Удаление общих NodeResult/free node_results/shared_context — финальный шаг DAG-TYPING-1 после устранения всех usages в GEN-DAG-1. Данные пользователей и сохранённые snapshots не удаляются автоматически.

**Стык планов:** A1–A3 используют isolated registry с тестовыми нодами, рабочее переключение не выполняется. GEN-DAG-1 затем подключает конкретные контракты и factories к общей инфраструктуре. B проверяет интеграцию и удаляет общие старые каналы. Это зависимость точки переключения, не gate на начало A1. Подготовка изменений по шагам не означает поддержку двух production runtime.

### Дополнительные согласованные уточнения (2026-10-30)

- **Согласованность доменных чтений.** Подготовка Input использует согласованную доменную ревизию или snapshot через публичные read-контракты. Read-only DAGContext фиксирует Output, но сам по себе не фиксирует состояние БД. Если домен не поддерживает согласованное чтение, соответствующая интеграция не принимается до появления подходящего публичного доменного read-контракта. Блокер явно указывается в карте A0 и ТЗ соответствующей интеграции; одной фиксации ограничения недостаточно для разрешения несогласованного чтения; повторное исполнение ноды не считается решением проблемы согласованности. Не вводить скрытый persist или глобальную блокировку DAG для компенсации ограничения.
- **Момент инвалидации.** При назначении новой попытки старый Output сразу исключается из актуальных; тогда же инвалидируются результаты, потребившие его, по правилам пункта 5. Ошибка или отмена новой попытки не возвращает старый Output в актуальные. Историческая запись может оставаться в диагностике без доступности через обычное чтение каталога.
- **Версии resume-снимков.** Снимок хранит версию формата и версии контрактов сохранённых данных. Перед восстановлением проверяется совместимость с текущими контрактами. Несовместимость завершается явной диагностической ошибкой без автоматической миграции и скрытого повторного запуска; исходный снимок не удаляется. Поля и представление версий определены в ТЗ §§6.1/9 и карте M01/M05; A3 реализует этот контракт.
- **Граница гарантий восстановления.** DAG-TYPING-1 гарантирует resume после штатной отмены, при которой runtime дождался задач и успешно сохранил снимок. Восстановление после падения процесса и недублирующее применение эффектов требуют отдельного согласованного контракта хранения/применения PatchSet/Snapshot. Сохранение Output не является доказательством этих гарантий. Конкретная реализация устойчивости к падению и дедупликации эффектов не входит в общую типизацию автоматически.

- **Отмена отдельной Python-ноды.** Если отменена одна задача, а весь запуск не отменён, координатор дожидается соседей, сохраняет их успешные валидные Output на барьере и останавливает выполнение перед следующим уровнем с исходом «отмена». Отменённая нода не публикует успешный Output; gate не разрешает продолжение после такой отмены. Сопутствующие ошибки и gate-сигналы сохраняются в диагностике, а не теряются из-за итогового исхода.
- **Подробная диагностика отмены.** Структурированные события и trace должны позволять восстановить причину и последствия: `execution_id`, ревизию плана/pass, фазу и уровень, `node_id` и `attempt`, время запроса/наблюдения отмены и завершения, источник и причину отмены (если неизвестны — явно «неизвестно»). Записывать объявленные требования ноды: производитель, ожидаемый контракт и обязательность; отдельно — реально прочитанные версии/отсутствие и состояние доступности. На барьере фиксировать исход каждой соседней задачи, идентификаторы сохранённых Output, ошибки/gate-сигналы, решение остановить дальнейшее исполнение и факт/ошибку сохранения resume-снимка, если оно выполнялось. Не записывать тяжёлые payload/Input целиком и не хранить их в trace ради диагностики. Владельцем итоговой записи остаётся координатор; сообщения параллельных задач коррелируются по идентификаторам, а не по порядку строк логов.
- **Недействительная доменная ссылка при resume.** Если объект по сохранённой ссылке отсутствует или недоступен для корректного восстановления, resume завершается явной ошибкой с идентификатором ссылки, производителем, попыткой и причиной. Не подставлять пустой результат, не запускать генерацию автоматически и не выдавать устаревший результат как актуальный.

Эти уточнения обязательны при детализации A0 и реализации A2/A3. Проверки включают недоступность старого Output после неуспешного перезапуска, отказ при несовместимых версиях снимка/недействительных доменных ссылках, восстановление после штатной отмены и отмену отдельной ноды с проверкой полноты коррелируемой диагностики. Отдельно проверять запрет необъявленных чтений и несовместимых контрактов зависимостей. Вопрос объединения записей legacy-нод снят: смешанный режим не вводится, замена и удаление генераторных нод принадлежат GEN-DAG-1.

### Практики, применимые к выбранной архитектуре

- **Управляемое время жизни задач:** координатор владеет задачами уровня, ожидает их завершения и очистки при отмене. `CancelledError` не подавляется как обычная ошибка. Сохраняем `gather(return_exceptions=True)`: автоматическая замена на `TaskGroup` изменила бы выбранную политику завершения соседей при ошибке. Основание: [Python asyncio](https://docs.python.org/3/library/asyncio-task.html).
- **Реальная неизменяемость опубликованных данных:** `frozen=True` не делает вложенный `dict` неизменяемым. При инвентаризации проверять весь граф вложений; не считать read-only внешнюю оболочку достаточной для безопасного разделения payload. Основание: [Pydantic — faux immutability](https://docs.pydantic.dev/latest/concepts/models/#faux-immutability).
- **Повторное использование записанного результата:** восстановление завершённой актуальной LLM-группы не выполняет новый запрос. Это применение принципа сохранения результатов недетерминированных операций, а не внедрение Temporal или полного event sourcing. Основание: [Temporal Workflows](https://docs.temporal.io/workflows).

**Согласованная граница ответственности за эффекты:** идемпотентность применения после resume требует контракта PatchSet/Snapshot. Идентификатор логического эффекта должен переживать retry; `attempt` результата не подходит в качестве единственного ключа дедупликации. Конкретный ключ и атомарность применения согласуются в соответствующей интеграции, а не выбираются этим планом за GEN-DAG-1. Основание: [Temporal — Activity definition](https://docs.temporal.io/activity-definition). Гарантия exactly-once для внешнего LLM-запроса при потере ответа здесь не заявляется.

## Точное целевое устройство

SoT API и поведения: `docs/tz_engine_node_context.md` §§6–12. Общие signatures: §6.2; отсутствие конкретных схем нод — §4/§11. Имена и пути ниже фиксированы до кода. Изменение карты требует явной правки плана и сообщения пользователю; папки нельзя выбирать во время имплементации.

### Инвентаризация и переиспользование

- `NodeStatus` уже существует: перенести, дополнить CANCELLED/GATED, обновить все imports; второй enum не создавать. `NodeKind`, `TaskType`, `PythonNodeError`, ValidationStatus/ValidationResult, NodeValidationError/NodeErrorSeverity, ContractValidator, schemaBuilder переиспользовать.
- Общих ExecutionIdentity/OutputRef/DAGContext в `dataModel`/`app/ids` не обнаружено. Новые технические ID — не RegistryKey доменных реестров; допустимость их строкового представления явно описана в ТЗ §6.1.
- Реальный ExecutionPlan импортируется из `application/engine/dag/executionPlan.py`; `graphs/executionPlan.py` содержит закомментированную старую схему и не является целевым контрактом. Не переносить его и не чистить заодно.
- `application/contracts/contracts.py` и конкретные contracts/validators нод — инвентарь GEN-DAG-1; не копировать их в generic dataModel/engine.
- SnapshotStore — in-memory. Новые SQL/codec/event-store не создаются. PatchApplier сейчас повторно пишет node_results; его конкретная замена относится к GEN-DAG-1, а не считается готовой доменной транзакцией.
- Из usages `shared_context` исключать одноимённое поле cascade по его смыслу, а не удалять механически по grep.

### Карта классов, владельцев и файлов

Обозначения путей (точные корни): **E**=`backend/app/application/engine/`, **D**=`backend/app/dataModel/engine/dag/`, **C**=`backend/app/application/cancellation/`, **T**=`backend/tests/dag_typing/`. `E/x.py` означает ровно `backend/app/application/engine/x.py`. Все классы, перечисленные в одной строке, находятся в указанном файле; `+` в файлах означает два отдельно названных файла, не диапазон.

| ID | Классы / функции | Ответственность, владелец и слой | Точный файл | Producers → consumers / зависимости |
|---|---|---|---|---|
| M01 | ExecutionIdentity; NodeId, ExecutionId, ContractId, ContractVersion, PlanRevision, DomainRevision | технические ID DAG; engine/dataModel | D/identity.py (новый) | coordinator → catalog/snapshot; stdlib/Pydantic, без application |
| M02 | DependencyRead, DomainReadEvidence, OutputRecord[O] | immutable result/provenance; engine/dataModel | D/records.py (новый) | runtime → read view/snapshot; M01 и domain POJO через generic O |
| M03 | ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity, CancellationSource, CancellationReason | typed события lifecycle; engine/dataModel | D/diagnostics.py (новый) | runner/coordinator → log/trace; M01, без доменных алгоритмов |
| M04 | NodeStatus | единый enum состояния; engine/dataModel | E/nodes/nodeStatus.py → D/nodeStatus.py | все engine imports обновить, старый файл удалить; без re-export/дубля |
| M05 | SnapshotMetadata | версии формата/контрактов, execution/pass counters; engine/dataModel | D/snapshotMetadata.py (новый) | snapshot service → restore; M01 |
| M06 | OutputRef[O], RequiredOutput[O], OptionalOutput[O] | типизированная связь producer/contract; engine/application | E/nodes/contracts/outputRef.py (новый) | декларации ноды → registry/read view; M01, type[O] |
| M07 | NodeContract[I,O], OutputLifecycle[O] Protocol | binding POJO и восстановление ссылок; engine/application | E/nodes/contracts/nodeContract.py (новый) | интеграция GEN → registry/executors; M06, Pydantic; без импорта конкретных нод |
| M08 | ExecutionBindings, ResponseBinding, TransitionBinding, SnapshotExtension Protocol; ResolveResult[O] | typed callbacks request/effects/response, без бизнес-правил; engine/application | E/nodes/contracts/executionBindings.py (новый) | GEN factories → engine/snapshot; существующий TaskType, BaseModel, M06 |
| M09 | NodeRegistration[I,O], NodeRegistry, decorators | хранение binding и поиск; engine/application | E/nodes/nodeRegistration.py + E/nodes/nodeRegistry.py | GEN/test registration → compiler/runner; M06–08, NodeKind |
| M10 | BaseNode[I,O], PythonNode[I,O], LLMNode[I,O], CompiledNode | общий typed-call интерфейс; engine/application | E/nodes/pojo/baseNode.py + E/nodes/pojo/pythonNode.py + E/nodes/pojo/llmNode.py + E/nodes/pojo/compiledNode.py | factories → runtime; M07, существующие Rule/NodeCost; без конкретных schemas |
| M11 | GraphCompiler, ExecutionPlan, LLMGroup | выбор/порядок и проверка рёбер контрактов; engine/application | E/graphs/graphCompiler.py + E/dag/executionPlan.py | registry + rule engine → DAGExecutor; не читает мир |
| M12 | ContractValidator, NodeValidator, LLMValidator, NodeValidationContext[O] | общий boundary validation и вызов доменного валидатора; engine/application | E/validation/contractValidator.py + E/validation/nodeValidator.py + E/validation/llmValidator.py + E/validation/nodeValidationContext.py | runner/aggregate → существующий ValidationResult; конкретные validators — GEN |
| M13 | DAGContext | single-writer каталог и lifecycle attempts; engine/application | E/dag/context/dagContext.py (новый) | coordinator → M14/restore; M01–07, M15; не доменный resolver |
| M14 | DAGReadView | неизменяемое представление и контроль требований; engine/application | E/dag/context/dagReadView.py (новый) | catalog → prepare_input; M06, M02; без write API |
| M15 | ResultInvalidation | вычисление invalidation по read evidence; engine/application | E/dag/context/resultInvalidation.py (новый) | begin_attempt → catalog; M02, без повторного scheduler/графа deps |
| M16 | NodeOutcome[O], GateSignal, LevelDecision | локальный результат исполнения и control metadata; engine/application | E/execution/nodeOutcome.py (новый) | runner/aggregate → coordinator; M01–04, TaskType, PythonNodeError |
| M17 | PythonNodeExecutor, NodeRunner | typed invocation + локальный исход; engine/application | E/execution/pythonNodeExecutor.py + E/execution/nodeRunner.py | M10/M12 → M16; не пишет shared runtime |
| M18 | DAGExecutor, ExecutionState | scheduling, единственный writer runtime; engine/application | E/dag/dagExecutor.py + E/dag/executionState.py | plan/outcomes → catalog/level decision; M13/M16; business gate остаётся в ноде |
| M19 | ExecutionTrace, ExecutionLevelSnapshot | только immutable IDs/status/provenance; engine/application | E/dag/executionTrace.py + E/dag/executionLevelSnapshot.py | coordinator → diagnostics; не хранит Input/Output payload |
| M20 | ExecutionSnapshotService | capture/restore/retention; engine/application | E/dag/lifecycle/executionSnapshotService.py (новый) | state ↔ SessionSnapshot; M05/M07/M08; domain refs через lifecycle callback |
| M21 | SessionSnapshot, SnapshotStore | типизированный снимок и прежнее memory-хранилище; cancellation/application | C/sessionSnapshot.py + C/snapshotStore.py | M20 ↔ cancellation; immutable Output refs, без SQL |
| M22 | emit | единый emitter событий engine; engine/application | E/diagnostics/dagLog.py (новый) | M03 → loggingConfig; без собственного handler |
| M23 | route_for, _PREFIX_ROUTES (функция/таблица; классы formatter/router не менять) | регистрация sink; logging/core | backend/app/core/loggingConfig.py | logger app.engine.dag → engine/dagExecution; без импорта engine |
| M24 | LLMGroupPayloadBuilder, NodeSection, LLMPayload | POJO Input → групповой wire payload; engine/application | E/prompt/llmGroupPayloadBuilder.py + E/prompt/pojo/nodeSection.py + E/prompt/pojo/llmPayload.py | M07/M10 → client; существующие DSLResolver и schemaBuilder без дублирования |
| M25 | RepairBuilder, LLMRepairPayload, NodeFailureContext, DSLFailureProjector | typed repair request/errors → wire; engine/application | E/repair/repairBuilder.py + E/prompt/pojo/llmRepairPayload.py + E/repair/pojo/nodeFailureContext.py + E/repair/dslFailureProjector.py | ValidationResult → repair loop; не ищет свободный node_results |
| M26 | LLMAggregateExecutor, RepairOrchestrator | групповой вызов + repair, локальные outcomes; engine/application | E/execution/llmAggregateExecutor.py + E/repair/repairOrchestrator.py | M24/M25/M12 → M16; single group publication через coordinator |
| M27 | LLMExecutionEngine | passes/cancel/resume, делегация callbacks; engine/application | E/llmExecutionEngine.py | M18/M20/M08; конкретное извлечение intents переносится в GEN binding |
| M28 | ResponseResolver | общий lookup результата через typed response binding; engine/application | E/responseResolver.py | M08/M14 → caller; ResolveResult переносится в M08 без дублирования, конкретные TaskType→node mappings — GEN |
| M29 | NodeRuntimeState | оставшийся потребитель NodeStatus; engine/application | E/nodes/nodeRuntimeState.py | обновить импорт M04, не создавать второй lifecycle store |
| M30 | NodeResult | удалить общую legacy-обёртку после handoff | E/nodes/pojo/nodeResult.py | все usages до удаления устранены GEN и общим runtime |

Допустимые направления: конкретные ноды/GEN → общий engine → dataModel; core logging не импортирует engine; dataModel не импортирует application/db/core runtime. Domain readers/lifecycle implementations приходят через typed binding, generic engine не импортирует domain internals. Pydantic schema — единственный источник полей/constraints. Новые generic ID описаны в ТЗ §6.1; не заводить RegistryKey для world-registry, которого нет.

ResolveResult переносится из E/responseResolver.py в E/nodes/contracts/executionBindings.py вместе с обновлением imports в A1.2; M08 не импортирует ResponseResolver, поэтому цикла нет. Его поля: ok: bool, data: O | None, error: str | None; текст ошибки — объяснение, не discriminator.

Обязательные детали M08: `ResponseBinding.resolve(view) -> ResolveResult[BaseModel]`, `TransitionBinding.transition(view) -> TaskType | None`; конкретный generic O уточняется binding. `SnapshotExtension[E: BaseModel]` предоставляет `capture() -> E` и `restore(value: E) -> Awaitable[None]` плюс ContractId/version и lifecycle validation. Конкретные request/session/effect POJO принадлежат GEN; JSON/Any не является допустимой заменой E. M20 хранит immutable extension вместе с версиями, не интерпретирует его поля.

### Композиция папок и imports

Подсчёт непосредственных файлов включает служебные. Новые папки — namespace packages, `__init__.py` не добавлять без пересчёта. Новые файлы только по M01–30; остальные строки — изменение существующих. Дополнительный файл требует корректировки карты и counts до кода.

| Папка | Сейчас → целевое | Действие |
|---|---:|---|
| E | 4 → 4 | менять llmExecutionEngine/responseResolver |
| E/nodes | 6 → 5 | NodeStatus переносится в D, импорт consumers обновить в A1.1 |
| E/nodes/pojo | 7 → 6 | NodeResult удаляется только B2 |
| E/nodes/contracts | 0 → 3 | M06–08 |
| E/graphs | 2 → 2 | старый закомментированный executionPlan не менять |
| E/dag | 5 → 5 | новые механизмы в подпапках по ответственности |
| E/dag/context | 0 → 3 | M13–15 |
| E/dag/lifecycle | 0 → 1 | M20 |
| E/execution | 3 → 4 | M16 |
| E/diagnostics | 0 → 1 | M22 |
| E/prompt; E/prompt/pojo | 4 → 4; 3 → 3 | существующие builders/wire DTO |
| E/repair; E/repair/pojo | 5 → 5; 1 → 1 | existing repair, без новых framework |
| E/validation | 6 → 6 | только изменяемые файлы M12 |
| C | 6 → 6 | существующий memory snapshot |
| D | 0 → 5 | M01–05, без init |
| backend/app/dataModel | 6 → 6 | только подпапка engine/dag; root не расширяется |
| backend/app/core | 13 → 13 | только routing entry; новых файлов нет, композиция всего core вне scope |
| backend/tests | 278 → 278 | только подпапка dag_typing; root не расширяется |
| T | 0 → 1 | fixtures.py; остальные файлы в подпапках |
| T/registry | 0 → 4 | test_metadata.py, test_binding.py, test_graph.py, test_validation.py |
| T/context | 0 → 3 | test_catalog.py, test_invalidation.py, test_retention.py |
| T/execution | 0 → 3 | test_runner.py, test_level.py, test_logging.py |
| T/lifecycle | 0 → 3 | test_snapshot.py, test_restore.py, test_passes.py |
| T/llm | 0 → 3 | test_payload.py, test_repair.py, test_group.py |
| T/integration | 0 → 3 | test_handoff.py, test_types.py, test_cleanup.py |
| T/typing | 0 → 4 | valid.py, invalid.py, pyrightconfig.json, pyrightconfig.invalid.json |

WARN для существующих >5: E/nodes 6→5, E/nodes/pojo 7→6, E/validation 6→6, C 6→6, dataModel root 6→6, core 13→13, tests root 278→278. Новые файлы в перегруженные core/tests root запрещены; этот план их не добавляет. Рекомендована композиция по ответственности при будущем расширении. Все imports NodeStatus и NodeResult проверить по репозиторию, включая side-effect registration, fixtures и re-exports. Новые typed механизмы не импортируют legacy/конкретные ноды через глобальный singleton; тесты создают isolated NodeRegistry. Production imports/Container wiring переводятся в GEN-DAG-1 перед B.

## Атомарный порядок реализации

Каждая строка ниже — отдельный шаг и один проверяемый слой/контракт/группа файлов. После шага короткий отчёт и ожидание «ок». Сначала весь A1 (types/binding), затем A2 (catalog/runner/coordinator), A3 (lifecycle/LLM/engine), затем handoff и B. A0 выполнен как документация; A1.1 реализован отдельно по запросу пользователя. Остальные шаги не начинались.

Для каждой строки: файлы Mxx раскрываются в точные файлы таблицы выше; дополнительно создаётся ровно названный тест. ТЗ всегда `docs/tz_engine_node_context.md` с указанным §. При новом неучтённом классе сначала дополнить карту, не выбирать место в коде.

### Команды проверок и среда

Все команды из корня репозитория, PowerShell. Один раз перед Python-проверками: `$env:PYTHONPATH = (Resolve-Path backend).Path`. Python: `.venv/Scripts/python.exe`. Backend/uvicorn не запускать. Моки доменных сервисов/LLM, memory SnapshotStore; внешние API/БД для общей приёмки не нужны.

Обозначение **U(folder,file)** — точная команда `.venv/Scripts/python.exe -m unittest discover -s backend/tests/dag_typing/<folder> -p <file> -v`; значения folder/file даны в каждой строке. Ожидается exit 0, все тесты PASS, отсутствие пропущенных обязательных сценариев. Это будущие тесты, создаваемые соответствующим шагом, а не заявление о существующих/пройденных проверках.

**TYPE**: `.venv/Scripts/python.exe -m unittest discover -s backend/tests/dag_typing/integration -p test_types.py -v`. Тест запускает установленный `node node_modules/pyright/index.js -p backend/tests/dag_typing/typing/pyrightconfig.json --outputjson`, затем аналогично pyrightconfig.invalid.json. Positive exit 0; negative exit 1 и точное совпадение rule/line для каждого `# expect:`; отсутствие/лишние ошибки — FAIL. Python 3.12, extraPaths от config до backend (`../../..`), include valid.py и точных реализованных generic модулей шага: в A1.2 M01–10, в A2.1 добавить M13–14, в A2.4 M15–18; strict для новых контрактов; negative config включает invalid.py. Известные ошибки нетронутых импортируемых модулей фиксировать baseline отдельно, не скрывать новые через Any/ignore. Модель проверки — существующий scripts/check-cascade-types.cjs, новый скрипт в scripts не нужен.

**ALL**: по очереди U для folder registry/context/execution/lifecycle/llm/integration с file `test_*.py` (каждая папка отдельно; рекурсивный discover без init не предполагать). **DIFF**: `git diff --check -- .cursor/plans/dag-typing-1.md .cursor/plans/gen-dag-1-post-geo-ws.md docs/tz_engine_node_context.md docs/tz_logging.md` для документации; при коде дополнить точными файлами шага. Архитектурная проверка владельцев Mxx обязательна дополнительно к тестам, не заменяется ими.

| Шаг / цель | ТЗ | Файлы и контракт | Проверка | Done |
|---|---|---|---|---|
| A0 — зафиксировать исполнимую документацию | §§4,6–12; tz_logging §Каталог | этот план, GEN-DAG-1, tz_engine_node_context, tz_logging; карта M01–30, шаги и sink | DIFF; сверка всех M/§/counts | DONE (документы), поведение и владельцы согласованы |
| A1.1 — общие metadata и единый status | §6.1, §6.3, §10 | M01–05, M29; обновить все импорты старого NodeStatus; T/fixtures.py, registry/test_metadata.py | U(registry,test_metadata.py) | DONE: immutable record/identity, один NodeStatus; нет dataModel→application |
| A1.2 — binding ноды и typed вызов | §6.1–6.2 | M06–10, M28 (только перенос ResolveResult и imports), T/registry/test_binding.py, T/typing/valid.py, invalid.py, pyrightconfig.json, pyrightconfig.invalid.json, T/integration/test_types.py | U(registry,test_binding.py), TYPE | обязательные I/O и producer/contract declarations, generic binding сохраняет I/O; неверный I/O отклоняется статически; проверки require добавляются A2.1 |
| A1.3 — проверка контрактов графа | §6.1, §8 | M11, T/registry/test_graph.py; compile проверяет deps/binding/phase/group | U(registry,test_graph.py) | неизвестный producer/несовместимый Output/невозможное чтение в группе отвергнуты, order-only deps сохранены |
| A1.4 — общая валидация boundary | §6.2 | M12, T/registry/test_validation.py; POJO+semantic delegation | U(registry,test_validation.py) | нет копии схемы; invalid Output не допускается к публикации |
| A2.1 — каталог и read view | §6.2, §7 | M13–14, T/context/test_catalog.py, T/typing/valid.py, invalid.py и оба pyrightconfig; identity/read_view/require/optional, transitive invalidation — A2.2 | U(context,test_catalog.py), TYPE | неподписанный producer и чужой тип недоступны; соседний незавершённый Output невидим |
| A2.2 — invalidation provenance | §7 | M15, интеграция в M13–14, T/context/test_invalidation.py | U(context,test_invalidation.py) | chain/diamond/optional absence инвалидируются до rerun; order-only не инвалидирует, failed rerun не оживляет старое |
| A2.3 — локальный outcome runner | §6.2, §8 | M16–17, T/execution/test_runner.py | U(execution,test_runner.py) | prepare/validate/execute/validate, gate/cancel/fail локальны; общих записей нет |
| A2.4 — конкурентный уровень и barrier commit | §7–8 | M18–19, T/execution/test_level.py и оба T/typing/pyrightconfig | U(execution,test_level.py) | Event-барьер доказывает overlap; разные порядки завершения дают согласованные исходы; cancel ждёт cleanup; gate останавливает до следующего уровня |
| A2.5 — подробные события и единый sink | §10; tz_logging §DAG execution | M22–23, M18 emitter calls, T/execution/test_logging.py | U(execution,test_logging.py) | все обязательные cancel/read/sibling/save поля, маршрут engine/dagExecution, без payload/дублирующего handler |
| A3.1 — typed memory snapshot | §9 | M20–21, T/lifecycle/test_snapshot.py | U(lifecycle,test_snapshot.py) | identity/counters/versions/control/provenance/typed extension сохранены без копий payload |
| A3.2 — restore и освобождение владения | §9 | M20–21, M13, T/lifecycle/test_restore.py, T/context/test_retention.py | U(lifecycle,test_restore.py), U(context,test_retention.py) | version/ref mismatch — явная ошибка; исходный snapshot сохранён; нет генерации; trace не удерживает payload |
| A3.3 — общий LLM payload из typed Input | §8 | M24, T/llm/test_payload.py | U(llm,test_payload.py) | один group schema из Output POJO; input без чтения raw node_results; transport dict не публикуется |
| A3.4 — typed repair request | §8 | M25, T/llm/test_repair.py | U(llm,test_repair.py) | errors/provenance typed, JSON только transport; существующий DSL и semantic validator hook сохранены |
| A3.5 — агрегированное исполнение и repair | §8 | M26, вызов group commit M18, T/llm/test_group.py | U(llm,test_group.py) | один initial call; repair в той же conversation; all-or-none публикация; cancelled/invalid group не публикуется частично |
| A3.6 — общий pass/resume loop и response hook | §9, §11 | M27–28, M08, T/lifecycle/test_passes.py | U(lifecycle,test_passes.py), TYPE | engine делегирует конкретные transitions/responses/effects; resume повторно не вызывает актуальную группу |
| B1 — принять handoff конкретных нод | §4, §11 | план GEN-DAG-1 (его отдельные шаги); T/integration/test_handoff.py | U(integration,test_handoff.py) | все production registrations имеют concrete binding из GEN; domain-read гарантии/refs проверены владельцами; нет смешанного runtime |
| B2 — удалить общие legacy-каналы | §11 | M30 удалить, M18/M27/M28 удалить free fields/old usages; конкретный PatchApplier/consumers уже заменены GEN; T/integration/test_cleanup.py | U(integration,test_cleanup.py), ALL | нет старых imports/side-effect refs и свободного доступа; cascade shared_context не затронут; нет aliases/adapters |
| B3 — общая архитектурная приёмка | §12 | только статус этого плана после проверки итогового кода | ALL, TYPE, DIFF по итоговым файлам | параллелизм, lifecycle, LLM и typing подтверждены; owners/imports/counts соблюдены, baseline delta записана |

### Сценарии проверок и исполнения

Тесты в T используют TestCase/IsolatedAsyncioTestCase; helpers и тестовые BaseModel помещаются в T/fixtures.py, не в production dataModel. Для overlap две ноды сигнализируют started до разрешения обеим закончить; timeout ограничен, wall-clock benchmark не является доказательством. Negative typing проверяет wrong Input, wrong Output, неверное присваивание результата require. Тесты registry — no side-effect import рабочих нод.

Тесты graph включают required producer, исключённый rules: compile не создаёт фиктивный Output, prepare падает по отсутствию; optional допускает отсутствие. Проверки LLM сохраняют один вызов для всей temperature-группы и не принимают чтение будущего Output соседа. Restore тестирует format и contract mismatch отдельно, invalid domain ref callback и отсутствие auto-generation. Snapshot extension — тестовый POJO, конкретные эффекты не выдумываются.

Подробное логирование проверять при стандартном уровне INFO/WARNING, не только DEBUG: ID attempt, declared contracts, actual read versions, cancel source/reason, sibling outcomes, сохранённые Output IDs, barrier decision, snapshot save outcome. L1–L8 tz_logging соблюдаются; server sink один на процесс, frontend/server не запускать.

### Уточнение A1.1: классификация отмены (согласовано 2026-10-30)

В M03 (`backend/app/dataModel/engine/dag/diagnostics.py`) добавить enum CancellationSource и CancellationReason вместо свободных str в cancel_source/cancel_reason; текст вынести в cancel_message. Новых файлов и runtime-поведения нет. Источник требования — `docs/tz_engine_node_context.md` §§6.3/10; значения и правила UNKNOWN определены там. Проверка: U(registry,test_metadata.py), включая отказ произвольным строкам и неверным wire-кодам, JSON round-trip enum, необязательность пояснения; Pyright M01–05. Это исправление текущего A1.1, не начало A1.2.

### Execution evidence A1.1 (2026-10-30)

- DONE: M01–05 и M29; 5 файлов dataModel, старый NodeStatus удалён, единственный импорт перенесён. Вложенная неизменяемость переиспользует `dataModel/validation/immutableValue.py`; конкретных контрактов рабочих нод нет.
- U(registry,test_metadata.py): 14 PASS (включая строгие enum отмены, неверные wire-коды и JSON round-trip). Pyright новых модулей: 0 errors/warnings. Проверены no-copy композиции, mutable-вложения, required absence, producer/execution identity, snapshot keys и cancel diagnostics.
- Владельцы/imports: только dataModel→dataModel/Pydantic/stdlib; application runtime и параллелизм не менялись. Folder counts: D 0→5, E/nodes 6→5, T 0→1, T/registry 0→1; без добавлений в переполненные root.
- Baseline: фактический интерпретатор `.venv` — Python 3.14.4, Pydantic 2.13.4; planned typecheck target Python 3.12 сохраняется. A1.2 не начат.

### Приёмка ответственности и фиксация результата

Перед реализацией и перед Done каждого шага проверить затронутые M11/M13/M17/M18/M20/M24–28: только порядок, зависимости, lifecycle и передача typed данных. Для доменного вычисления обязан быть owning callback/service из GEN; lookup рецептов, world fallback, сборка доменных metadata внутри generic runtime запрещены. Проверять вложенные helpers/dispatch, не только название класса. При >300 строках или смешении ответственностей — остановить шаг и уточнить карту, не переносить всё в FooOps. Короткая запись execution evidence: шаг/status; owner paths проверены; команда/результат; baseline delta/блокер (3–5 строк).

Правила refactor-safety: до переноса/удаления поиск usages и строковых ID по backend/tests/docs/rules, side-effect imports и re-export; перенос M04 обновляет все imports в одном шаге. B2 проверяет не только имя NodeResult, но и доступы к старым полям. Коммиты, запуск backend, DDL и чистка неучтённых legacy-файлов не входят в этот план.

## Критерии завершения и вне scope

Завершён общий typed runtime, подтверждён single-writer и параллелизм, все активные ноды используют контракты GEN-DAG-1, старые общие каналы удалены, docs согласованы. Самостоятельная приёмка A1–A3 допускается до production handoff; весь DAG-TYPING-1 не отмечается DONE до B3. После полного завершения — `dag-typing-1-done.md`, пометка DONE в H1 и обновление всех ссылок согласно code-gates.

Вне scope: concrete поля Input/Output всех нод, доменная read-consistency implementation, response/task/effect mappings и business validators, удаление конкретных legacy-нод (GEN-DAG-1); идемпотентность persist/crash recovery/SQL (PatchSet/Snapshot integration); новая схема L0/L2, материализация и HTTP. Не блокировать A1–A3 ожиданием этих интеграций, но не объявлять общий production переход готовым до их необходимых контрактов.
