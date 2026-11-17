Локальные UID вне общего helper — список для фикса
Статус: OPEN, диагностический fix-list (не новый архитектурный план).

Срез: master, 16098c1a2e6c6fa32d89631abd941cb6f91c097c, 2026-11-17 (после актуализации ветки; новые UID-генераторы в добавленных файлах не найдены).
Объём: обнаруженные формулы, проверка границ их применения и source-gate. Реализация не менялась.
Где находится общий механизм UID
- Реализация: [`backend/app/ids/deterministicIds.py`](../backend/app/ids/deterministicIds.py).
- Публичный импорт: [`backend/app/ids/__init__.py`](../backend/app/ids/__init__.py) (app.ids).
- Закрытые типы: [`backend/app/ids/uidKind.py`](../backend/app/ids/uidKind.py): UidKind, LibraryKind.
- Тест и source-gate: [`backend/tests/test_deterministic_ids.py`](../backend/tests/test_deterministic_ids.py), SourceGateTests.
- Действующий контракт: [`docs/project_data_storage_tz.md`](project_data_storage_tz.md), § DET-1, уточнение A0 от 2026-10-14.
Основные операции: entity_uid(world_uid, UidKind, **keys) для идентичности сущностей мира; seed_uid(world_seed, UidKind, **keys) для bake; library_uid(LibraryKind, system_name, pack_uid=...) для библиотек; runtime_uid() для назначаемого случайного UID; entity_rng/`seed_rng` для детерминированных потоков. Тонкие доменные обёртки допустимы, если не вводят собственную формулу.

Документационный дрейф: [`.cursor/rules/deterministic-ids.mdc`](../.cursor/rules/deterministic-ids.mdc) всё ещё называет app.application.worldData.ids актуальным модулем, хотя реальный и объявленный в DET-1 A0 путь — app.ids. Исправлять ссылку, а не переносить рабочую реализацию обратно.
1. Рёбра ConnectionEdge — локальные формулы для сохраняемого PK
ConnectionEdge.edge_uid — первичный ключ connection_edges. Узлы уже получают UID через connection_node_uid() → entity_uid(), но рёбра используют строковую склейку:
Место	Формула
[road/layouts/gridLayout.py (line 116)](../backend/app/application/worldData/generators/road/layouts/gridLayout.py#L116)	e_{from_node_uid}_{to_node_uid}
[areaAssembler/planner/areaPaths.py (line 70)](../backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaPaths.py#L70)	a_{from_node_uid}_{to_node_uid}
[settlementAssembler/planner/streets.py (line 294)](../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py#L294)	city_{from_node_uid}_{to_node_uid}
[settlementAssembler/planner/streets.py (line 359)](../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py#L359)	city_link_{entry_node_uid}_{nearest_node_uid}
[districtAssembler/planner/alleys.py (line 131)](../backend/app/application/worldData/generators/assemblers/districtAssembler/planner/alleys.py#L131)	e_alley_{edge_key}_{from_node_uid}


- [ ] Определить, подпадают ли все сохраняемые ConnectionEdge под DET-1 (он называет connection_nodes/edges), или для части действует отдельный явно принятый контракт.
- [ ] Учесть, что [`docs/tz_city_generation_technical_debt.md`](tz_city_generation_technical_debt.md) фиксирует city_ / city_link_ как стабильную пару узлов по C23. Это нужно согласовать с требованием единой формулы; не переписывать UID без решения о существующих ссылках.
- [ ] При выборе DET-1 добавить необходимый закрытый UidKind (сейчас CONN_EDGE отсутствует), тонкую обёртку и тесты повторяемости/уникальности/SQL+pack ссылок.
2. Синтетические UID в генерации локаций и контекстов
Место	Локальное значение	Влияние / проверка
[areaBarriers.py (line 111)](../backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaBarriers.py#L111)	{world_uid}-area-{min_x}-{min_y}	При отсутствии здания передаётся в MapCell.location_uid. Проверить существование владельца и сохранение ссылки.
[structureAreaAssembler.py (line 453)](../backend/app/application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py#L453)	{world_uid}-{template_identity}-{map_x}-{map_y}	Fallback NamedLocation.location_uid без area_uid; в комментарии назван standalone/debug. Проверить, не выходит ли в production persist.
[structureAreaAssembler.py (line 279)](../backend/app/application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py#L279) и [cascade/locationScope.py (line 171)](../backend/app/application/cascade/locationScope.py#L171)	{building.location_uid}#area	Суррогатный ключ area scope для контекста/RNG, не подтверждённый UID реальной area-сущности.
[roomFactory.py (line 172)](../backend/app/application/worldData/generators/structure/room/roomFactory.py#L172)	`{building_uid}	{room_id}`


- [ ] Разделить настоящую идентичность сохраняемого объекта и локальный ключ для контекста/алгоритма; для последних не требовать механически нового UUID.
- [ ] Не менять fallback для debug/standalone без проверки допустимых вызывающих путей.
3. Гидрология — собственные строковые UID
Место	Формула / назначение
[waterBodyIdentity.py (line 12)](../backend/app/application/worldData/generators/hydrology/waterBodyIdentity.py#L12)	`auto-{lake
[proceduralRiverAutoresolve.py (line 46)](../backend/app/application/worldData/generators/hydrology/autoresolve/proceduralRiverAutoresolve.py#L46)	ar-river-{world_uid}-{x}-{y}-{index}
[loadDeclaredHydrology.py (line 105)](../backend/app/application/worldData/generators/hydrology/load/loadDeclaredHydrology.py#L105)	dr-{river.location_uid}-{index}
[resolveDeclaredRiverPath.py (line 211)](../backend/app/application/worldData/generators/hydrology/rivers/resolveDeclaredRiverPath.py#L211)	dr-{river.location_uid}


- [ ] Не считать auto-* автоматически дефектом: [`docs/tz_terrain_hydrology.md`](tz_terrain_hydrology.md), § water_body_uid, прямо допускает позиционные non-durable UID при autoresolve/re-bake. Проверить, что не появляются долговечные ссылки на них.
- [ ] Для речных edge_uid установить границу: это локальные сегментные ключи / opaque reference или долговечная идентичность связи? Не переводить их на DET-1 без проверки реальных потребителей connection_edge_uid.
4. Технические UUID DAG / SQLite вне runtime_uid()
Прямые вызовы uuid4() — 8 мест в 6 файлах:
Файл	Строки	Назначение
[dagExecutor.py (line 262)](../backend/app/application/engine/runtime/dag/dagExecutor.py#L262)	262	owner выполнения
[executionInteraction.py (line 62)](../backend/app/application/engine/runtime/invocations/interaction/executionInteraction.py#L62)	62	owner claim
[executionRecovery.py (line 44)](../backend/app/application/engine/runtime/invocations/recovery/executionRecovery.py#L44)	44	owner recovery
[memoryExecutionStore.py (line 20)](../backend/app/application/engine/runtime/invocations/memoryExecutionStore.py#L20)	20	нативный UUID store_id
[dagExecutions/executionStore.py (line 34)](../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L34)	34	долговечный UUID store_id
[bakeOperations/operationStore.py (line 43)](../backend/app/db/repositories/sqlite/bakeOperations/operationStore.py#L43)	43, 44, 81	operation_id / owner_id


- [ ] Решить, распространяется ли app.ids.runtime_uid() на технические execution/store/lease ID. Они не являются детерминированными сущностями мира; не менять тип UUID на str в контрактах ради формальной замены.
- [ ] Либо перенаправить через общий API подходящего типа, либо документировать узкие исключения в source-gate.
5. Source-gate и исключения
Повторение регулярных выражений SourceGateTests статически выявило 10 непокрытых _EXEMPT файлов: 6 файлов с uuid4() из §4 и 4 с hashlib:
- storage/artifacts/blobBackend.py, storage/artifacts/blobRead.py — content/path/temp fingerprints;
- dataModel/world/bakeOperation/request.py — request fingerprint;
- worldData/generators/hydrology/encoding/sourceShape.py — shape fingerprint.
Последние четыре не генерируют world UID. Полный unittest в проверочном окружении не дошёл до теста из-за зависимостей; результат здесь — статический прогон логики gate, а не отчёт о прохождении тестов.
- [ ] Убрать ложные срабатывания на content hashes, сохранив запрет hash для UID/seed.
- [ ] Дополнить проверку локальных формул edge_uid, location_uid и аналогичных полей: нынешний regex не ловит f"..." и конкатенации. Не запрещать все f-строки глобально — учитывать назначение поля и принятые исключения.
- [ ] Обновить устаревший путь helper в .cursor/rules/deterministic-ids.mdc с учётом DET-1 A0.
Не включать в фиксы без нового основания: derive_world_uid() (bootstrap-хэш, заявленное исключение); uuid4() в chat/player/session/logging и authored fallback perk/race (явные _EXEMPT); PackingToken.uid вида {template_uid}#{index} (внутренний алгоритмический токен); frontend crypto.randomUUID() для request/mock; PackJobUid (принятый форматный wire-композитор, а не независимый UUID-хэш).
Минимальная проверка после адресных фиксов
- [ ] Одинаковые входные данные + world UID дают прежнюю идентичность там, где контракт требует replay; разные владельцы не сталкиваются по UID.
- [ ] Проверить ссылки connection_edges, MapCell.location_uid, connection_edge_uid, pack/SQL после повторной генерации.
- [ ] SourceGateTests проходит без маскирования новых генераторов широкими исключениями; тесты продемонстрировали и запрет нового обхода, и допустимые локальные идентификаторы.
- [ ] Если меняется формула долговечного UID, отдельно определить судьбу существующих SQL/pack/refs (DET-1 предупреждает о пересоздании), не применять изменение незаметно.