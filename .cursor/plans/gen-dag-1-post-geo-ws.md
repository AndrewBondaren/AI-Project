# GEN-DAG-1 — Передача оркестрации генерации в engine DAG (после GEO-1 и принятия новой архитектуры patches/snapshots)

**Статус:** DRAFT / DEFERRED. Только фиксация архитектурного намерения; не разрешение на имплементацию.
**Входные gates:** завершён и принят GEO-1; принята архитектура `.cursor/plans/world-domain-patches-snapshots.md` и согласованы необходимые для DAG интеграции Patch/PatchSet/Snapshot контракты; архивный WS не является gate; отдельное согласование с мастером перед изменениями DAG.
**Типизация engine DAG:** самостоятельный план `.cursor/plans/dag-typing-1.md`; настоящая задача включает генераторную интеграцию и конкретные контракты всех рабочих DAG-нод; общая типизированная инфраструктура остаётся в DAG-TYPING-1.
**Preflight 2026-10-31:** аудит готовности выполнен ниже. A1–A3 DAG-TYPING-1 завершены; production migration GEN-DAG-1 остаётся закрыта внешними gates и конкретными contract gaps. Это результат анализа, не приёмка GEO-1/Patch/Snapshot и не разрешение на production cutover.
**Связанные SoT:** `geo-1-designed-water.md`, `docs/tz_world_generation_dag.md`, `docs/tz_engine_flow.md`, `.cursor/rules/dag-generator-interface.mdc`, `.cursor/plans/world-domain-patches-snapshots.md`, `docs/tz_world_snapshot.md` и доменные контракты (архивный `world-state-crud-transition.md` не является SoT). При конфликте со старыми правилами persist/bake — сначала сверить и согласовать SoT, не молча менять их.

## Стык с DAG-TYPING-1 и удаление legacy (согласовано 2026-10-30)

- GEN-DAG-1 владеет заменой и удалением legacy-нод генератора, включая выявленные `check_terrain`, `eager_terrain`, `lazy_terrain`, `lazy_settlement`, `generate_climate`: перед удалением каждого старого пути перенести нужное поведение в ноды публичных доменных операций, обновить регистрации, `deps` и потребителей. Точный состав удаления подтвердить аудитом вызовов.
- DAG-TYPING-1 реализует общие типизированные Input/Output, DAGContext, NodeRegistry и runtime. Не мигрировать подлежащие удалению генераторные ноды только ради типизации; новые ноды GEN-DAG-1 сразу используют согласованные общие контракты. Адаптеры legacy/typed и смешанный режим не вводить.
- Инфраструктурную фазу A DAG-TYPING-1 можно готовить и проверять на типизированных тестовых нодах до завершения GEN-DAG-1. Полное переключение рабочего DAG требует готовности нужных частей обоих планов и отсутствия legacy-потребителей. Удаление общесистемных старых каналов и `NodeResult` выполняет DAG-TYPING-1 после проверки всех usages.
- Приёмка удаления: старые реализации и регистрации генераторных нод удалены, нет обходных вызовов репозиториев и ссылок на удалённые ноды; нужные сценарии покрыты новыми нодами, параллелизм независимых операций и согласованные правила публикации сохранены. Удаление пользовательских данных/snapshots этим шагом не предусмотрено.

### Последовательность переключения после preflight A1.2

1. DAG-TYPING-1 готовит target declarations в `backend/app/application/engine/contracts/`, `registration/`, `nodeTypes/` и реализации в `engine/runtime/`, `application/cancellation/typed/`. Они проверяются isolated registry и тестовыми нодами, без импорта production side effects. Общие NodeKind/NodeCost/PythonNodeError переносятся в `engine/nodeTypes/support/` с обновлением imports; это не переписывание конкретных контрактов.
2. GEN-DAG-1 готовит конкретные bindings и явный `backend/app/application/engine/registration/productionNodes.py` с `register_production_nodes(registry: NodeRegistry) -> None`. Production до переключения использует только старые decorators/registry, target не принимает старый API.
3. Одним интеграционным шагом GEN-DAG-1 переключает `backend/app/core/container/engine.py`, concrete-ноды и caller imports на target runtime/typed snapshots, вызывает явную регистрацию, убирает side-effect bootstrap из `backend/app/application/engine/nodes/__init__.py`. Предварительно проверить полноту списка ID и concrete контрактов. Переключение не выполняется частично по нодам и не вводит fallback на старый runtime.
4. Передать handoff в B1 DAG-TYPING-1. Удаление predecessor общих файлов — B2 по карте; конкретных legacy-нод — данный план. Временное наличие старых и target исходников до handoff не является разрешением на два production runtime или adapter legacy/typed.

## Конкретные контракты нод — обязательный scope GEN-DAG-1 (уточнение 2026-10-30)

GEN-DAG-1 владеет **всеми конкретными** Input/Output рабочих Python- и LLM-нод, а не только генераторными результатами. Для каждой ноды до кода: выбрать доменные POJO либо композицию; явно задать producer/Output/required-or-optional требования поверх deps; определить typed factory и доменные read/operation bindings, валидаторы, восстановление ссылок и response/task/effect bindings. Общие сигнатуры/механизмы брать из `docs/tz_engine_node_context.md` §§6–12 и карты M01–33 DAG-TYPING-1. Generic infrastructure не реализовывать повторно. Если ноде нужны несколько POJO, её собственный Input/Output составляется из типизированных вложенных полей существующих доменных POJO. Специальные композиции размещать в `backend/app/dataModel/engine/nodes/<группа>/<контракт>.py`; самостоятельные доменные контракты оставлять в своих доменах. Обязательно закрепить в ТЗ каждой ноды классы композиции, имена/типы вложенных полей, producers/read-источники, обязательность, неизменяемость и точные файлы. Не дублировать доменные поля/defaults/validators. Нормативный источник: `docs/tz_engine_node_context.md` §2.2.1. Состав файлов и folder counts входят в карту GEN-DAG-1 до реализации.

Инвентарь для конкретизации: зарегистрированные ноды через `backend/app/application/engine/nodes/__init__.py`; `nodes/pojo/python/scene/`, `terrain/`, `climate/`; `nodes/pojo/llm/intentDetection/`; старые `python/sceneInitNode.py`, `python/pythonFilterNode.py`, `python/prepareAnalysisContextNode.py` проверить по фактическим imports/usages. Для каждого файла зафиксировать сохранить/заменить/удалить. Общий engine не должен задавать за эти ноды поля, read API или семантику отсутствующих данных.

Владение также включает конкретные схемы `backend/app/application/contracts/contracts.py`, `intentItem.py`, concrete validators в `engine/validation/validators/`, `_OUTPUT_NODE`/response mapping, извлечение `intents`/task transition, старый `engine/repair/patchApplier.py`, production wiring в `backend/app/core/container/` и чтение результатов в chat/cancellation callers. Общие классы runtime остаются в DAG-TYPING-1; GEN поставляет typed callback/binding и мигрирует конкретные call sites.

Перед передачей на B1 DAG-TYPING-1 предъявить: карту всех node IDs с точными файлами POJO/factory/validator, явными requirements, подтверждёнными read-consistency гарантиями, lifecycle callbacks ссылок, отсутствием legacy usages и критериями доменной приёмки. Эти конкретные карты составляются и согласуются в данном плане, а не в общем плане типизации. Если требуемого доменного read-контракта нет, соответствующая интеграция не принимается. Номенклатура новых нод не считается утверждённой одним упоминанием инвентаря.

## Аудит готовности к интеграции — 2026-10-31

### Вывод и границы проверки

Общая инфраструктура готова к подключению concrete bindings: target `DAGEngine[O,S]` находится в `backend/app/application/engine/runtime/dagEngine.py`; node contracts/registry, phased execution, grouped LLM+repair, atomic group publication, cursor/pass/resume и ограниченные hooks реализованы в DAG-TYPING-1 A1–A3. Это не готовность production: `core/container/engine.py` по-прежнему создаёт legacy LLMExecutionEngine, загружает side-effect bootstrap и legacy snapshot singleton. `registration/productionNodes.py` отсутствует. B1 сейчас принимать нечего.

Проверка включает планы/ТЗ, AST closure текущего bootstrap, contracts/validators/DSL, конкретные read/write call sites, наличие core implementations и callers. Это readiness audit, а не полная per-node приёмка всех вложенных доменных алгоритмов. Новые node IDs/DTO/enum/CRUD операции не утверждены. Код, регистрации, migrations и чужие текущие GEO-изменения не менялись.

### Внешние gates: что действительно готово

- **DAG-TYPING-1 A1–A3 — implemented/verified.** Evidence находится в его плане; rename M27 до DAGEngine учтён. Generic runtime повторно реализовывать не требуется; далее нужны concrete factories, readers, error/validator/lifecycle и response/transition/effects bindings.
- **GEO-1 — OPEN, production gate не закрыт.** Последние записи G10-A в `geo-1-designed-water.md` различают isolated native fine routing и canonical production source join. Остались fine→coarse projection semantics, exact source dependencies routes→river-relief→final, coverage/intent reconciliation, G8-B legacy contract removal и G10-A/G10/G10-R/G11 acceptance. В текущем `generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py::_routes` GEO всё ещё проходит coarse `.plan` → legacy fine `.plan`; наличие native fine operation само по себе не переключило caller. `planning/composition/surfacePlanningAssembler.py::prepare_geo` сохраняет общий inter-stage порядок. Green isolated tests не являются gate acceptance всего GEO-1.
- **Patch/Snapshot — core частично реализован.** Принят architecture baseline; есть DTO, typed ports/registries/encoding, DDL/models, publication/operation/history adapters. 4C2-R материализован; 4C2-H реализован и ожидает приёмки. Последний статус §8.14: 4C2-O НЕ НАЧАТ, 4C3 запрещён до приёмки H и завершения/приёмки O. В коде отсутствуют запланированные `snapshotCore/operations/terminalCodec.py`, `publicationEvidence.py`, `sqlite/artifacts/operationArtifacts.py`; operationStore пока содержит соответствующие реализации вместе.
- **Runtime publication ещё нет.** `application/worldSnapshot/contracts/applyPort.py::IWorldSnapshotApply` — Protocol. Отсутствуют `application/worldSnapshot/service`, artifact staging/lifecycle implementations, `application/publication/service`, `core/container/snapshots` и SQLite artifact adapters. Следовательно, 4C3/4C4/4D1–3/4E2 и concrete domain handler/source-version binding не подтверждены как ready. Точные prerequisites и порядок — `world-domain-patches-snapshots.md` §8.3.8/§8.14; не заменять их shortcut-реализацией в GEN.
- **Два разных Snapshot.** `cancellation/typed/SessionSnapshot[S]` удерживает исполнение для memory resume. Он не реализует world/player publication, PatchSet commit или историю gameplay Snapshot. Готовность save/resume A3.6 не закрывает отсутствие Snapshot.apply.

### Фактический инвентарь: 15 активных node IDs

Ниже пути относительно `backend/app/application/engine/nodes/pojo/`. Статусы означают направление контрактной проработки, а не одобрение нынешней реализации или будущих имён replacement-нод.

1. `check_scene` — `python/scene/checkSceneNode.py`. Сохранить роль проверки сцены/gate; заменить direct scene/location repo reads и shared_context на публичный coherent domain read, immutable POJO и typed E/error policy. Подходящий read-контракт/revision сначала предъявляет владелец сцены.
2. `scene_init` — `python/scene/sceneInitNode.py`. Подготовка выбора стартовой сцены и её effect разделяются по Patch/Snapshot контракту; существующий `scene_repo.upsert` в PRE_LLM нельзя сохранить в typed node.
3. `scene_location_children` — `python/scene/sceneLocationSelectNode.py`, класс SceneLocationChildrenNode. Сохранить смысл получения доступных children; access/faction/occupancy решения и coherent location/player/NPC reads принадлежат домену, не переносить helpers как алгоритмы в новый node.
4. `scene_start_location_select` — тот же файл, класс SceneStartLocationSelectNode. Existing leaf branch вызывает `scene_repo.upsert`; заменить на prepared domain effect/section и Snapshot-owned применение, сохранить отдельно ветку возврата children.
5. `check_terrain` — `python/terrain/checkTerrainNode.py`. Заменить map_cells existence/location lookup на согласованный публичный read-контракт; coordinate/missing semantics и authoritative source определяет домен.
6. `eager_terrain` — `python/terrain/eagerTerrainNode.py`. Legacy direct MapCell load/asdict; заменить public read/materialized refs, не принимать SQL map_cells как целевую SoT pack path по умолчанию.
7. `lazy_terrain` — `python/terrain/lazyTerrainNode.py`. Legacy generate_minimal + insert_bulk_ignore; заменить отдельными согласованными domain preparation/staging/publication операциями. Запрет direct write нельзя обходить callback в новой ноде.
8. `lazy_settlement` — `python/terrain/lazySettlementNode.py`. Legacy generate_map_cells + insert_bulk_ignore и local settlement-type dispatch; scope/тип/needs_geometry принадлежат соответствующему доменному контракту. Граница одной публичной операции определяется её жизненным циклом, не внутренними helpers.
9. `terrain_context` — `python/terrain/terrainContextNode.py`. Сейчас выбирает eager/lazy raw results и пишет shared_context. Пересмотреть композицию typed read/prepared refs после замены producers; не переносить legacy dict merge как новый общий context.
10. `terrain_summary` — `python/terrain/terrainSummaryNode.py`. Агрегация raw cells/settings/conversion выполняется в node; выделить owning domain projection и immutable result с inventory существующих типов/defaults.
11. `generate_climate` — `python/climate/generateClimateNode.py`. Legacy apply_climate_pass + upsert_climate_fields; заменить approved preparation/effect/publication contract.
12. `recalculate_climate` — `python/climate/recalculateClimateNode.py`. Аналогичный прямой climate writer; не считать отдельным законным apply entry после типизации.
13. `resolve_weather` — `python/climate/resolveWeatherNode.py`. Сохранить роль runtime weather read/projection через доменный API; убрать shared_context/raw cells и node-local temperature/rainfall fallbacks.
14. `context_snap_gatherer` — `llm/intentDetection/contextSnapGathererNode.py`. Concrete typed Input/Output, semantic validator и DSL/patch resources требуют freeze; same-group dependency conflict описан ниже.
15. `intent_detection` — `llm/intentDetection/intentDetectionNode.py`. Concrete typed Input/Output/validator/transition требуют freeze; не переносить dynamic enum/ignore/raw-dict validation в новый runtime.

Отдельный ledger неактивных файлов:

- `python/prepareAnalysisContextNode.py` импортирован bootstrap, но класс `prepare_context` не декорирован и не входит в actual registration baseline. Решить удалить или заново обосновать его необходимость; не добавлять автоматически в productionNodes.
- `python/pythonFilterNode.py` содержит decorator, но не входит в bootstrap import closure. Сам факт decorator в исходниках не делает его production-нодой.
- `python/sceneInitNode.py` — неактивный дубликат `scene_init`; активный путь — `python/scene/sceneInitNode.py`. Удаление только после полной usage проверки в implementation step.

### Контрактные находки, блокирующие механический перенос

- **C1 — same-temperature LLM dependency.** Оба LLM node имеют temperature=0.2; `intent_detection.deps=[context_snap_gatherer]`, DSL `app/dsl/intent_detection/intent_detection.txt` прямо требует `scene_context: ContextSnap FROM context_snap_gatherer`. Typed GraphCompiler запрещает required/optional Output read из той же LLM group. Order-only deps не предоставляют этот Output в заранее подготовленный Input. Нельзя скрыто разрезать группу или вернуть raw node_results. До кода выбрать и согласовать семантику: общий запрос с независимыми Input из authoritative scene и соответствующей joint-output DSL либо явно утверждённый другой request/group контракт. Выбор этим аудитом не сделан.
- **C2 — immutable schemas и enum owner.** `application/contracts/contracts.py` хранит mutable List-based ContextSnapContract/IntentDetectionContract; `db/models/sessionScene.py` — mutable SQL dataclass с actors:list. Они не являются готовыми immutable DAG POJO. `application/contracts/intentItem.py` строит LLMTaskType из application TaskType и содержит ignore. До размещения concrete моделей в dataModel необходимо определить нейтрального владельца task identity/ограничения или явное application mapping; запрет dataModel→application и одного SoT для enum сохраняется. Не создавать parallel task enum или str-флаг ради обхода.
- **C3 — mutable authoritative writes до Snapshot.** Конкретные примеры: `lazyTerrainNode.py`/`lazySettlementNode.py` вызывают insert_bulk_ignore; generate/recalculateClimateNode — upsert_climate_fields; sceneInitNode/SceneStartLocationSelectNode — scene_repo.upsert в PRE_LLM. `repair/patchApplier.py` лишь переписывает node_results/status и очищает pending list. Его docstring о транзакции не означает атомарного применения мира; использовать его как реализацию LifecycleBinding.apply_effects нельзя.
- **C4 — response map шире реального графа.** Legacy `_OUTPUT_NODE` в `application/engine/responseResolver.py` содержит 7 targets; отсутствуют среди 15 registered IDs: scene_narration, scene_combat, scene_change_location, local_scene_analysis, local_region_analysis. Зарегистрированы лишь scene_init/scene_start_location_select из этой карты. Для каждого missing target определить реализовать/удалить mapping/явный unsupported response; это бизнес-решение, не generic fallback DAGEngine и не основание молча зарегистрировать новые ноды.
- **C5 — repair resources неполны.** Из 7 node.dsl_patches значений существуют только intent_detection/repair_confidence.txt; отсутствуют четыре context_snap_gatherer/repair_{location,situation,player_state,actors}.txt и intent_detection/repair_{tone,missing_intent}.txt. DSLRegistry.get открывает эти paths непосредственно. Freeze должен связать реальные validation codes и существующие DSL resources; отсутствие ресурса не подменять пустым patch. Новое содержание DSL этим аудитом не сочинялось.
- **C6 — callers всё ещё legacy.** `core/container/engine.py` создаёт old engine/side-effect registry/global store; `application/chat/chatService.py` зовёт run(task_type,message,session,cancel_token,snapshot), ожидает dict/string и сериализует asdict snapshot; `api/routes/chat.py` делает session_id-based load/delete и допускает fresh run при missing resume snapshot. Новый DAGEngine использует ExecutionId/run-resume/ResolveResult и typed memory snapshot. Нужен explicit session→execution mapping, LifecycleBinding/SnapshotExtension/LLMRequest binding и транспортная проекция результата. Не добавлять legacy JSON codec, fallback или runtime adapter вместо миграции callers.
- **C7 — нормативный sync.** `docs/tz_engine_flow.md`/project context и legacy-раздел правила dag-generator-interface по-прежнему описывают pending_patches→PatchApplier и старую публикацию. Перед implementation freeze отразить принятое разделение staging, pregame CAS и runtime Snapshot; не использовать старый абзац как разрешение обойти новый baseline.

### Следующая исполнимая работа и первый интеграционный срез

**Сейчас доступен GEN-P0 — contract freeze, только документы.** Этот аудит закрывает его discovery/inventory часть. Остаток P0 — конкретная карта для всех 15 IDs плюс ledger неактивных файлов и missing response targets. Для каждой роли должны быть предъявлены: существующий публичный read/operation owner и consistency/revision contract; выбранный POJO или композиция с точными полями/типами/путём; requirements поверх deps; factory/validator/typed E и lifecycle refs; effects handler/staging/publication owner; retry/cancel/idempotency; файл/пакет counts и per-node acceptance. Пока отсутствующий порт/тип остаётся gap, его не записывать как утверждённый новый API.

В P0 в первую очередь закрыть C1/C2, authoritative scene read и применение scene effects (C3), затем C4/C5/C6. Существующий Scene/Location SQL repository не считается автоматически согласованным read API; raw mutable DTO нельзя просто переименовать в Output. Обновляемые артефакты P0 — этот план и профильные ТЗ, без production source changes. Согласованная карта и закрытые внешние gates являются входом к коду.

**Ближайший уже спроектированный кодовый prerequisite — Patch/Snapshot 4C2-O**, после требуемой повторной приёмки 4C2-R/4C2-H. Его точная map уже находится в world-domain-patches-snapshots §8.14: StoredTerminalCodec, SqlitePublicationEvidence, SqliteOperationArtifacts и DI-композиция SqliteOperationStore; затем 4C3/4C4/4D1–3/4E2 по исходной последовательности. Не включать эти реализации в GEN/DAGEngine. Параллельный GEO prerequisite — текущий source-join contract review → G10-A production activation → итоговая приёмка; native fine stage не заменяет этот gate.

**Первый bounded GEN integration после prerequisites — scene read → typed check_scene.** Сначала владелец сцены реализует согласованный immutable coherent read и его version/ref semantics; затем отдельный thin-node шаг связывает reader, concrete Input/Output/E, factory и gate policy с существующим target registry. Проверки: found/missing/draft scene, missing location, согласованность reads, error policy, no direct writes и restore refs. Имена новых DTO/ports/файлов замораживаются в P0 до реализации. Это изолированный concrete binding, не production switch и не B1. LLM context/intent добавляются следующим срезом только после решения C1/C2/C5.

**Единственная точка production cutover остаётся прежней:** полный concrete registration/bootstrap, LifecycleBinding + Snapshot-owned effects + request/response/session/cancellation callers переключаются одним интеграционным шагом. До него target bindings проверяются изолированно, без mixed runtime и без partial routing реальных запросов. После per-node и сценарной приёмки — handoff B1, затем удаление legacy B2 и общая приёмка B3.

### Evidence аудита

- AST traversal explicit bootstrap imports: 24 node-namespace modules, 15 unique decorated registered IDs; состав совпадает с existing production baseline в `tests/dag_typing/registry/test_binding.py`. Простое сканирование всех decorators не использовалось как registration inventory. Отдельно AST-сверка response map: 7 targets / 5 отсутствуют в bootstrap.
- Проверены фактические callers/writers/DSL/POJO и наличие core paths. IWorldSnapshotApply остаётся Protocol, planned application services/4C2-O modules/productionNodes отсутствуют; source join использует прежний маршрут. Эти выводы не основаны только на заголовках DRAFT или числах прежних tests.
- Изменён только этот план. Unit/typing/backend в этом read-only аудите не запускались; чужие текущие rename/GEO изменения сохранены. Per-node архитектурная приёмка и согласование решений C1/C2/C4 остаются открытыми, успешный inventory их не заменяет.

## Исторический контекст (не новый scope)

Генерация **изначально** проектировалась не только для первоначального создания мира. В существующем engine DAG уже есть gameplay-ноды `check_terrain`, `eager_terrain`, `lazy_terrain`, `lazy_settlement`, которые используются при работе со сценой и смене локации. Это не новая возможность, вводимая GEN-DAG-1. План исправляет границы ответственности и согласованность существующего подхода, а не расширяет назначение генератора с bootstrap на runtime.

**Обнаруженный legacy-разрыв:** `backend/app/application/engine/nodes/pojo/python/terrain/checkTerrainNode.py`, `eagerTerrainNode.py`, `lazyTerrainNode.py`, `lazySettlementNode.py` напрямую обращаются к `location_repo`, `world_repo`, `map_cell_repo`; `lazyTerrainNode.py` и `lazySettlementNode.py` самостоятельно вызывают `map_cell_repo.insert_bulk_ignore`. `backend/app/application/engine/nodes/pojo/python/climate/generateClimateNode.py` также напрямую читает/пишет через репозитории. Это предмет аудита и последующего перевода на публичные CRUD-контракты генератора, а не основание переносить CRUD в DAG. Не считать старый путь эталонной архитектурой только потому, что он работает.

## Цель

Устранить скрытую **межоперационную оркестрацию уровня мира** внутри генератора: выбор самостоятельных публичных операций, их внешних зависимостей, условий запуска, порядка и scope принадлежит существующему engine DAG. Внутренняя композиция вычислений одной доменной операции остаётся у генератора. Это **не изменение роли DAG**, а подключение генераторных операций к уже принадлежащей DAG оркестрации.

Генератор отвечает на вопрос **как вычислить/построить результат конкретной доменной операции**. Он не владеет глобальной очередью стадий, не принимает решения о запуске соседних доменов и предоставляет и реализует доменный CRUD. DAG непосредственно вызывает публичные CRUD-операции генератора по их контрактам, но не реализует CRUD, не забирает его у генератора и не знает деталей хранения; правила фиксации изменений в production определяются контрактами нового плана доменных patches/snapshots.

Одинаковая архитектурная граница применяется к:
- первоначальному сотворению мира (bootstrap/bake);
- lazy-планированию и материализации;
- локальному изменению (пример: ведро воды → лужа);
- региональному/глобальному изменению (пример: потоп);
- другим действиям игрока и фоновой симуляции, затрагивающим мир.

Масштаб сам по себе не диктует обязательный набор доменов: DAG выбирает необходимые операции по контрактным зависимостям и последствиям, не по захардкоженному сценарию «лужа/потоп».

## Разделение ответственности

- **Engine DAG:** выбор операций и стадий (включая planning vs materialization), их порядка/зависимостей, scope, условий запуска, повторного исполнения и сборки PatchSet из результатов по принятым контрактам Patch/PatchSet. DAG решает **что/когда/как организовать исполнение**, но не реализует доменные алгоритмы.
- **Генераторы и домены:** владеют собственным CRUD и его реализацией, доменными расчётами, алгоритмами и локальной композицией внутри атомарной операции. Предоставляют явные CRUD-контракты, которые вызывает DAG; не владеют общей последовательностью чужих стадий. Владение CRUD не тождественно самостоятельному решению о моменте запуска операции или фиксации транзакции в обход Snapshot.
- **Snapshot и доменные Patch:** DAG собирает PatchSet из подготовленных доменных patches; только Snapshot инициирует применение и сохранение состояния/истории, делегируя доменную запись владельцу данных. Самостоятельный общий patcher как вход применения исключён. Генератор не формирует patches и не сохраняет состояние. DAG вызывает публичные доменные CRUD-контракты подготовки, не реализует CRUD и не обращается к внутренним репозиториям/алгоритмам. Snapshot не запускает planning/materialization; подготовка и применение — разные фазы.

**Граница ноды:** не превращать каждый helper, цикл, chunk или внутренний шаг алгоритма в DAG node. Выносить самостоятельные публичные операции с внешними зависимостями и управляемым жизненным циклом; сохранять внутреннюю алгоритмическую композицию в домене. Размер класса сам по себе не критерий границы.

### Нормативная граница: самостоятельная операция vs внутренняя композиция

- **DAG управляет самостоятельными операциями мира**, а не внутренним устройством их алгоритмов. Публичные `create/update/delete` города, локации или area являются возможными точками вызова DAG; это не требование заводить отдельную ноду для каждой разновидности объекта.
- **Генератор вправе организовывать любое количество внутренних вычислительных шагов** одной публичной доменной операции: например, `create_house` может последовательно рассчитывать фундамент, этажи, комнаты, лестницы, окна и крышу. Эти шаги не требуют отдельных DAG-нод только из-за порядка или зависимостей между ними.
- **Самостоятельность определяется контрактом и внешним управлением**, а не числом методов: операция имеет отдельный публичный результат и жизненный цикл, её запуск/повтор/условия/зависимости должны определяться внешним сценарием, либо она участвует в межоперационных зависимостях. Наличие нескольких внутренних стадий, циклов, ветвлений и helpers само по себе не доказывает самостоятельности.
- **Недопустим скрытый запуск самостоятельных операций других доменов** или скрытая смена planning/materialization и управление межоперационным графом вместо DAG. Внутренний вызов чужого чистого вычислительного контракта как части реализации сам по себе не запрещён: решающим является, кто выбирает самостоятельные операции мира и их жизненный цикл.
- **Атомарность здесь архитектурная, не обязательно транзакционная**: внутренняя композиция может быть сложной, но наружу предоставляется одна согласованная доменная операция. Применение и сохранение состояния по-прежнему подчинены PatchSet/Snapshot-контрактам.
- **Инвариант независимости:** при сохранении публичного контракта можно заменить всю внутреннюю последовательность построения дома без изменения DAG; изменение внешнего сценария создания/изменения областей не требует изменения генератора.

## План работ (после gates)

1. **Аудит текущих контрактов и исполнения.** Прочитать актуальный код DAG, включая legacy `check_terrain` / `eager_terrain` / `lazy_terrain` / `lazy_settlement` / `generate_climate`, GEO-1 planning/materialization, bake callers, debug HTTP и новый план доменных patches/snapshots. Составить таблицу существующих оркестраторов: какие вызовы — межстадийная оркестрация, какие — внутренняя доменная работа; зафиксировать несовместимые legacy-контракты. Никаких догадок о нодах по названиям.
2. **Контрактная карта DAG ↔ операции.** Для каждой переносимой операции зафиксировать входы, результаты, deps, scope, planning/materialization, idempotency/retry/cancel и жизненный цикл кеша; определить границу атомарности. Утвердить с мастером до кода.

   **Типизация DAG — отдельный план:** общесистемная POJO-типизация Input/Output, `DAGContext`, `NodeRegistry`, `ExecutionState`, LLM/Python и replan/resume вынесены в `.cursor/plans/dag-typing-1.md` (подробное ТЗ — `docs/tz_engine_node_context.md`). GEN-DAG-1 не проектирует и не реализует эту инфраструктуру «заодно». Конкретные Input/Output всех рабочих нод определить здесь, применяя общие контракты DAG-TYPING-1; применять согласованную выше границу ответственности и зависимость точки переключения; это не gate на начало инфраструктурной фазы A DAG-TYPING-1.

3. **Вынести межстадийное управление и убрать обход CRUD.** DAG выбирает и вызывает отдельные публичные CRUD-операции генератора; прямые обращения legacy-нод к репозиториям генераторных данных заменить вызовами его CRUD-контрактов. generator APIs остаются стабильными и не получают знаний о DAG/ExecutionState. Не переносить доменные алгоритмы в DAG. Не создавать второй глобальный pipeline в bake или generator.
4. **Интегрировать доменные patches/Snapshot.** DAG вызывает публичный domain CRUD для write-free подготовки → получает typed prepared result → вызывает доменный Patch → собирает PatchSet → передаёт Snapshot, который единолично инициирует применение и сохранение через доменные storage-контракты. Planning/materialization вызываются только DAG и не запускаются Snapshot. Сверить bootstrap/bulk bake и runtime paths с новым архитектурным планом; никаких прямых writes или отдельного patcher apply entry.
5. **Сохранить debug/test paths.** Debug API обязан повторять вызовы DAG через те же публичные CRUD-контракты генератора, с той же семантикой входов/результатов; никаких альтернативных debug-алгоритмов, debug-pipeline или дублирования orchestration policy. Размещение транспортных точек входа регулируется отдельным планом `.cursor/plans/api-1-transport-boundary.md`. Debug harness остаётся инструментом диагностики, а не альтернативным production-входом.
6. **Приёмка.** Проверить как минимум bootstrap мира, lazy materialization, локальную лужу и региональный потоп (последние — сценарии проверки маршрутизации, не требование реализовать физику воды в этом плане); корректность deps/scope, отсутствие лишнего глобального bake, детерминизм, повторные вызовы, failure/retry и PatchSet/Snapshot consistency. Тесты должны различать выбор операций DAG и правильность доменных вычислений.


## Жёсткие запреты / out of scope

- Не менять engine DAG до отдельного разрешения мастера и прохождения GEO-1 и согласованных gates нового плана patches/snapshots.
- Не создавать новый DAG/оркестратор внутри генератора вместо использования существующего.
- Не дублировать вычисления в DAG, не смешивать planning/materialization, не писать в состояние мира мимо согласованного пути через Snapshot.
- Не переписывать GEO-1, новый план patches/snapshots или алгоритмы гидрологии «заодно»; при обнаружении пробела контракта — отдельное решение.
- Этот документ не утверждает готовность или конкретную номенклатуру будущих DAG-нод.


## Обязательный архитектурный gate: двусторонняя независимость

**Категорически запрещено:**

1. Межстадийный / междоменный production-pipeline внутри генератора: генератор не определяет последовательность planning → materialization → соседние домены, условия запуска и граф зависимостей. Всё это принадлежит DAG.
2. Просачивание деталей реализации генератора в DAG: DAG не знает внутренних assembler/planner, хранилищ, алгоритмов, вспомогательных шагов и структуры внутренних данных. Он вызывает только публичные CRUD-контракты генератора.
3. Параллельные реализации одной и той же orchestration policy в DAG и генераторе.
4. Debug-маршрут, реализующий собственный pipeline вместо повторения DAG-вызовов публичного CRUD генератора.

**Правило приёмки функциональных тестов:** функциональные тесты, **не написанные разработчиком**, **не являются критерием приёмки**. Их успешное прохождение не может использоваться как доказательство выполнения Definition of Done. Происхождение тестов должно быть установлено до использования их результатов для приёмки. Это правило не отменяет обязательное архитектурное ревью и проверку контрактных границ.

**Критерии приёмки (обязательные проверяемые сценарии):**

- **DAG изменён → генератор неизменен.** Перестройка графа, условий, порядка, scope и композиции операций не требует изменения исходного кода генератора или его CRUD-реализации.
- **Генератор изменён → DAG неизменен при сохранении контракта.** Замена алгоритма, внутреннего состава классов, способа хранения или реализации CRUD не требует изменений DAG. Если публичный контракт меняется намеренно, в DAG допустима **только контрактная адаптация**; перенос логики реализации в DAG запрещён.
- **Проверка границ:** code review и проверка контрактных границ подтверждают обе независимости; результаты функциональных тестов учитываются как критерий приёмки только при соблюдении правила об их авторстве; любые обнаруженные скрытые цепочки самостоятельных операций мира внутри генератора и знания DAG о внутренностях генератора блокируют приёмку; внутренние вычислительные стадии одной публичной операции допустимы.

Внутренние циклы и вспомогательные вычисления **одной атомарной доменной CRUD-операции** — не межстадийный pipeline и остаются в генераторе. Граница определяется контрактом операции и ответственностью, не количеством строк.

## Обязательная приёмка **каждой отдельной DAG-ноды**

Это **per-node gate**, а не разовая проверка всей интеграции и не выборочный аудит. Для **каждой** DAG-ноды до её индивидуальной приёмки проследить фактическую цепочку вызовов, включая вложенные сервисы и методы. Если любой вызываемый метод самостоятельно выбирает, запускает или координирует **несколько самостоятельных публичных операций мира** (их внешние зависимости, условия, scope, planning/materialization и жизненный цикл) вместо DAG, **именно эта нода не принимается**. Несколько внутренних вычислительных стадий одной публичной операции, даже последовательных и взаимозависимых, не являются основанием для отказа. Метод подлежит декомпозиции на отдельные публичные операции, вызываемые самостоятельными DAG-нодами; межстадийное управление остаётся только в DAG. Обёртка над скрытым pipeline не считается атомарной операцией. Внутренние циклы, helpers и вычислительные шаги одной доменной операции допустимы. Проверять фактическую ответственность, а не только сигнатуру или тесты. Нельзя принять общий GEN-DAG-1 при наличии хотя бы одной непрошедшей ноды.

## Definition of Done

- Единственный production-владелец межстадийной оркестрации генерации/изменений — engine DAG.
- Генераторные домены отвечают за «как» и владеют собственным CRUD; DAG вызывает их CRUD по публичным контрактам и отвечает за выбор и порядок операций; Snapshot — за применение/историю состояния по контракту.
- Первичная генерация, локальные и региональные изменения используют один принцип оркестрации без отдельного generator-DAG.
- Контракты и архитектурные границы приняты мастером; функциональные тесты учитываются как критерий приёмки только если они написаны разработчиком.
