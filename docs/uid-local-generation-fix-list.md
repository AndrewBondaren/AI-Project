# Локальные UID вне общего helper — список для фикса

## Повторное ревью 2026-11-18 — обязательный общий генератор

**Вердикт: НЕ ПРИНЯТ к реализации; нарушения централизации подтверждены.**
Это дополнение имеет приоритет над прежними исключениями и вопросами ниже.
Проверен текущий код рабочего каталога; HEAD сообщает
`84d66dd30441e3bf34bc0e9df9d665d339675355`. Старый срез 2026-11-17 — исторический.
Git status недоступен (ошибка work tree/доступа), поэтому чистота дерева не подтверждена.

**Решение пользователя:** каждый UID проекта создаётся общим генератором
`app.ids`. Локальная формула недопустима независимо от persist, debug,
autoresolve, runtime или authored fallback. Обёртка может передавать типизированные
компоненты в общий API, но не собирать собственный UID. Чтение готового UID
не является генерацией. Content fingerprint сам по себе не UID; использование
его для создания идентичности уже входит в запрет.

### Подтверждённые нарушения и обязательные исправления

- [ ] **R1 / P1 — ConnectionEdge:** все пять формул §1 подтверждены текущим кодом
  (gridLayout:116, areaPaths:70, streets:294/359, alleys:131).
  Перевести на общий генератор; вопрос «подпадают ли под DET-1» закрыт решением
  пользователя. В UidKind пока нет CONN_EDGE. Зафиксировать компоненты идентичности,
  направление ребра и различение параллельных рёбер; проверить SQL/pack/refs.
- [ ] **R2 / P1 — location/context:** устранить локальную выдачу location_uid
  в areaBarriers:111 и structureAreaAssembler:453–459; суррогат area_uid
  в structureAreaAssembler:279 и cascade/locationScope:171.
  Дополнительно найдены debug location_uid в backend/app/api/routes/debug.py:99/159.
  Debug/standalone не исключение. Для roomFactory:172 проследить scope_rng:
  составной ключ не считать автоматически сущностью, но он не может подменять
  UID комнаты или обходить централизованный контракт RNG.
- [ ] **R3 / P1 — hydrology:** auto-* в waterBodyIdentity:14 и речные edge_uid
  в proceduralRiverAutoresolve:46, loadDeclaredHydrology:105,
  resolveDeclaredRiverPath:211 подтверждены. Перевести выдачу UID в app.ids.
  Non-durable статус больше не разрешает локальную формулу. Согласовать старое
  положение tz_terrain_hydrology с новым требованием, проверить ссылки потребителей.
- [ ] **R4 / P1 — runtime:** восемь uuid4-вызовов в шести файлах §4 подтверждены.
  Использовать общий API, сохраняя требуемые типы UUID/str на границах.
  Дополнительно убрать обходы в application/chat/chatService.py:53/63,
  application/session/playerService.py:27/38,
  application/session/gameSessionService.py:54,
  core/logMiddleware.py:16 и dataModel/{perks/perkTemplateOutline.py:36,
  races/raceTemplateOutline.py:30}. Runtime и authored fallback не исключения.
- [ ] **R5 / P1 — bootstrap world_uid:** application/worldBundle/deriveWorldUid.py:19–29
  самостоятельно хэширует JSON и выдаёт world-{digest}. Это генерация UID,
  прежнее bootstrap-исключение отменено. Домен может готовить исходные данные;
  формулой идентичности должен владеть общий модуль. Определить совместимость
  повторного импорта и существующих world_uid.
- [ ] **R6 / P2 — frontend:** crypto.randomUUID обнаружен в
  frontend/src/features/send-message/model/useChatStream.ts:96 и
  frontend/src/shared/api/mock/adapter.ts:104/120/133/137.
  Прежнее исключение request/mock отменено. Определить общий путь выдачи UID
  для frontend, включая mock; отдельная копия формулы в TypeScript не удовлетворяет
  требованию единого генератора. Контракт этого пути пока OPEN.
- [ ] **R7 / P1 — source-gate:** текущий SourceGateTests сканирует только
  backend/app/*.py рекурсивно; regex не ловит строковые формулы UID и frontend.
  _EXEMPT явно пропускает bootstrap/chat/session/logging/perk/race.
  Удалить разрешения на локальную генерацию UID, добавить контроль строковых
  обходов и frontend. Исключения для настоящих content hashes должны быть узкими
  и не скрывать UID в том же файле. Старый комментарий о невозможности импорта
  из application/worldData/ids устарел: публичный модуль теперь app.ids.
- [ ] **R8 / P2 — оставшиеся прежние исключения:** PackJobUid и PackingToken
  больше не имеют автоматического разрешения. Проследить их производителей и
  потребителей: если значение служит UID, выдавать его через общий генератор;
  если это только адрес/алгоритмический ключ — доказать это контрактом и использованием.
  Проверка этих цепочек в данном ревью не завершена; полного покрытия проекта
  этим поиском не заявляется.
- [ ] **R9 / P2 — документация:** синхронизировать deterministic-ids.mdc,
  DET-1, C23 и гидрологический контракт с обязательным общим генератором.
  Старые разрешения ниже сохранены только как история предыдущего ревью,
  а не как допустимые варианты реализации.

### Приёмка плана по dag-generator-interface.mdc

Основание отказа — недостаточность сведений; изменение кода не выполнялось.

| Обязательный критерий | Место / результат |
|---|---|
| Три запрета DAG: ветвящий pipeline, скрытая оркестрация, междоменные вызовы | §1–4 перечисляют места формул, но не маршруты DAG и nested calls. Не проверено; приёмка не пройдена. |
| Ответственность каждого класса, зависимости, эффекты, критерий отказа | §1–4 не содержат полного реестра задействованных классов. OPEN. |
| Публичный контракт / pipeline / внутренняя реализация, Input/Output/Error | Описание helper в начале не определяет границы всех затронутых операций; frontend-путь R6 отсутствует. OPEN. |
| Неизменность утверждённого порядка действий | Нумерация диагностических групп не является согласованным порядком поставки. Источник утверждённой последовательности отсутствует. OPEN. |
| CRUD данных и настроек: read/write/delete/update отдельно | Контракты и обоснование применимости по операциям отсутствуют. OPEN. |
| Протокол зависимостей от чужих данных/настроек | SQL/pack/refs упомянуты без полной трассировки владельцев и контрактов. OPEN. |
| POJO, ошибки полей/логики, отсутствие дублирования | Нет инвентаря типов и сравнения ответственности; UUID/str отмечены, но этого недостаточно. OPEN. |

### Условия закрытия

- [ ] Составить полный инвентарь выдачи UID, включая ранее исключённые участки,
  с цепочкой до общего API и проверкой оставшихся R8.
- [ ] Принять контракты и последовательность исправления, закрыв критерии таблицы.
- [ ] Для каждой смены сохраняемой формулы определить судьбу SQL/pack/refs;
  сохранить replay там, где он обязателен, либо явно принять пересоздание данных.
- [ ] Проверить повторяемость, изоляцию владельцев и ссылочную целостность.
- [ ] Source-gate должен отвергать новый локальный UID, включая строковую формулу,
  и пропускать доказанный content fingerprint без широкого исключения файла.
- [ ] Прогнать соответствующие тесты после реализации. В этом ревью выполнены
  чтение и статический поиск; тесты не запускались, исправления не объявлены закрытыми.



**Статус:** OPEN, диагностический fix-list (не новый архитектурный план).

**Срез:** `master`, `16098c1a2e6c6fa32d89631abd941cb6f91c097c`, 2026-11-17 (после актуализации ветки; новые UID-генераторы в добавленных файлах не найдены).
**Объём:** обнаруженные формулы, проверка границ их применения и source-gate. Реализация не менялась.

## Где находится общий механизм UID

- **Реализация:** [`backend/app/ids/deterministicIds.py`](../backend/app/ids/deterministicIds.py).
- **Публичный импорт:** [`backend/app/ids/__init__.py`](../backend/app/ids/__init__.py) (`app.ids`).
- **Закрытые типы:** [`backend/app/ids/uidKind.py`](../backend/app/ids/uidKind.py): `UidKind`, `LibraryKind`.
- **Тест и source-gate:** [`backend/tests/test_deterministic_ids.py`](../backend/tests/test_deterministic_ids.py), `SourceGateTests`.
- **Действующий контракт:** [`docs/project_data_storage_tz.md`](project_data_storage_tz.md), § DET-1, уточнение **A0 от 2026-10-14**.

Основные операции: `entity_uid(world_uid, UidKind, **keys)` для идентичности сущностей мира; `seed_uid(world_seed, UidKind, **keys)` для bake; `library_uid(LibraryKind, system_name, pack_uid=...)` для библиотек; `runtime_uid()` для назначаемого случайного UID; `entity_rng`/`seed_rng` для детерминированных потоков. Тонкие доменные обёртки допустимы, если не вводят собственную формулу.

**Документационный дрейф:** [`.cursor/rules/deterministic-ids.mdc`](../.cursor/rules/deterministic-ids.mdc) всё ещё называет `app.application.worldData.ids` актуальным модулем, хотя реальный и объявленный в DET-1 A0 путь — `app.ids`. Исправлять ссылку, а не переносить рабочую реализацию обратно.

## 1. Рёбра `ConnectionEdge` — локальные формулы для сохраняемого PK

`ConnectionEdge.edge_uid` — первичный ключ `connection_edges`. Узлы уже получают UID через `connection_node_uid()` → `entity_uid()`, но рёбра используют строковую склейку:

| Место | Формула |
|---|---|
| [`road/layouts/gridLayout.py:116`](../backend/app/application/worldData/generators/road/layouts/gridLayout.py#L116) | `e_{from_node_uid}_{to_node_uid}` |
| [`areaAssembler/planner/areaPaths.py:70`](../backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaPaths.py#L70) | `a_{from_node_uid}_{to_node_uid}` |
| [`settlementAssembler/planner/streets.py:294`](../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py#L294) | `city_{from_node_uid}_{to_node_uid}` |
| [`settlementAssembler/planner/streets.py:359`](../backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py#L359) | `city_link_{entry_node_uid}_{nearest_node_uid}` |
| [`districtAssembler/planner/alleys.py:131`](../backend/app/application/worldData/generators/assemblers/districtAssembler/planner/alleys.py#L131) | `e_alley_{edge_key}_{from_node_uid}` |

- [ ] Определить, подпадают ли все сохраняемые `ConnectionEdge` под DET-1 (он называет `connection_nodes/edges`), или для части действует отдельный явно принятый контракт.
- [ ] Учесть, что [`docs/tz_city_generation_technical_debt.md`](tz_city_generation_technical_debt.md) фиксирует `city_` / `city_link_` как стабильную пару узлов по C23. Это нужно согласовать с требованием единой формулы; не переписывать UID без решения о существующих ссылках.
- [ ] При выборе DET-1 добавить необходимый закрытый `UidKind` (сейчас `CONN_EDGE` отсутствует), тонкую обёртку и тесты повторяемости/уникальности/SQL+pack ссылок.

## 2. Синтетические UID в генерации локаций и контекстов

| Место | Локальное значение | Влияние / проверка |
|---|---|---|
| [`areaBarriers.py:111`](../backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaBarriers.py#L111) | `{world_uid}-area-{min_x}-{min_y}` | При отсутствии здания передаётся в `MapCell.location_uid`. Проверить существование владельца и сохранение ссылки. |
| [`structureAreaAssembler.py:453–459`](../backend/app/application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py#L453) | `{world_uid}-{template_identity}-{map_x}-{map_y}` | Fallback `NamedLocation.location_uid` без `area_uid`; в комментарии назван standalone/debug. Проверить, не выходит ли в production persist. |
| [`structureAreaAssembler.py:279`](../backend/app/application/worldData/generators/assemblers/areaAssembler/structureAreaAssembler.py#L279) и [`cascade/locationScope.py:171`](../backend/app/application/cascade/locationScope.py#L171) | `{building.location_uid}#area` | Суррогатный ключ area scope для контекста/RNG, не подтверждённый UID реальной area-сущности. |
| [`roomFactory.py:172`](../backend/app/application/worldData/generators/structure/room/roomFactory.py#L172) | `{building_uid}|{room_id}` | Ключ `room_context()`/`scope_rng()`, отличается от реального UID комнаты, который `structureGeneratorService.py` создаёт через `entity_uid(..., UidKind.ROOM, ...)`. Проверить, намеренно ли RNG общий для экземпляров `room_id`. |

- [ ] Разделить настоящую идентичность сохраняемого объекта и локальный ключ для контекста/алгоритма; для последних не требовать механически нового UUID.
- [ ] Не менять fallback для debug/standalone без проверки допустимых вызывающих путей.

## 3. Гидрология — собственные строковые UID

| Место | Формула / назначение |
|---|---|
| [`waterBodyIdentity.py:12`](../backend/app/application/worldData/generators/hydrology/waterBodyIdentity.py#L12) | `auto-{lake|sea|river}-{x}x{y}` — процедурное тело воды |
| [`proceduralRiverAutoresolve.py:46`](../backend/app/application/worldData/generators/hydrology/autoresolve/proceduralRiverAutoresolve.py#L46) | `ar-river-{world_uid}-{x}-{y}-{index}` |
| [`loadDeclaredHydrology.py:105`](../backend/app/application/worldData/generators/hydrology/load/loadDeclaredHydrology.py#L105) | `dr-{river.location_uid}-{index}` |
| [`resolveDeclaredRiverPath.py:211`](../backend/app/application/worldData/generators/hydrology/rivers/resolveDeclaredRiverPath.py#L211) | `dr-{river.location_uid}` |

- [ ] **Не считать `auto-*` автоматически дефектом:** [`docs/tz_terrain_hydrology.md`](tz_terrain_hydrology.md), § `water_body_uid`, прямо допускает позиционные **non-durable** UID при autoresolve/re-bake. Проверить, что не появляются долговечные ссылки на них.
- [ ] Для речных `edge_uid` установить границу: это локальные сегментные ключи / opaque reference или долговечная идентичность связи? Не переводить их на DET-1 без проверки реальных потребителей `connection_edge_uid`.

## 4. Технические UUID DAG / SQLite вне `runtime_uid()`

Прямые вызовы `uuid4()` — **8 мест в 6 файлах**:

| Файл | Строки | Назначение |
|---|---|---|
| [`dagExecutor.py`](../backend/app/application/engine/runtime/dag/dagExecutor.py#L262) | 262 | owner выполнения |
| [`executionInteraction.py`](../backend/app/application/engine/runtime/invocations/interaction/executionInteraction.py#L62) | 62 | owner claim |
| [`executionRecovery.py`](../backend/app/application/engine/runtime/invocations/recovery/executionRecovery.py#L44) | 44 | owner recovery |
| [`memoryExecutionStore.py`](../backend/app/application/engine/runtime/invocations/memoryExecutionStore.py#L20) | 20 | нативный `UUID` store_id |
| [`dagExecutions/executionStore.py`](../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L34) | 34 | долговечный `UUID` store_id |
| [`bakeOperations/operationStore.py`](../backend/app/db/repositories/sqlite/bakeOperations/operationStore.py#L43) | 43, 44, 81 | operation_id / owner_id |

- [ ] Решить, распространяется ли `app.ids.runtime_uid()` на технические execution/store/lease ID. Они **не** являются детерминированными сущностями мира; не менять тип `UUID` на `str` в контрактах ради формальной замены.
- [ ] Либо перенаправить через общий API подходящего типа, либо документировать узкие исключения в source-gate.

## 5. Source-gate и исключения

Повторение регулярных выражений `SourceGateTests` статически выявило **10 непокрытых `_EXEMPT` файлов**: 6 файлов с `uuid4()` из §4 и 4 с `hashlib`:

- `storage/artifacts/blobBackend.py`, `storage/artifacts/blobRead.py` — content/path/temp fingerprints;
- `dataModel/world/bakeOperation/request.py` — request fingerprint;
- `worldData/generators/hydrology/encoding/sourceShape.py` — shape fingerprint.

Последние четыре не генерируют world UID. Полный `unittest` в проверочном окружении не дошёл до теста из-за зависимостей; результат здесь — **статический прогон логики gate**, а не отчёт о прохождении тестов.

- [ ] Убрать ложные срабатывания на content hashes, сохранив запрет **hash для UID/seed**.
- [ ] Дополнить проверку локальных формул `edge_uid`, `location_uid` и аналогичных полей: нынешний regex не ловит `f"..."` и конкатенации. Не запрещать все f-строки глобально — учитывать назначение поля и принятые исключения.
- [ ] Обновить устаревший путь helper в `.cursor/rules/deterministic-ids.mdc` с учётом DET-1 A0.

**Не включать в фиксы без нового основания:** `derive_world_uid()` (bootstrap-хэш, заявленное исключение); `uuid4()` в chat/player/session/logging и authored fallback perk/race (явные `_EXEMPT`); `PackingToken.uid` вида `{template_uid}#{index}` (внутренний алгоритмический токен); frontend `crypto.randomUUID()` для request/mock; `PackJobUid` (принятый форматный wire-композитор, а не независимый UUID-хэш).

## Минимальная проверка после адресных фиксов

- [ ] Одинаковые входные данные + world UID дают прежнюю идентичность там, где контракт требует replay; разные владельцы не сталкиваются по UID.
- [ ] Проверить ссылки `connection_edges`, `MapCell.location_uid`, `connection_edge_uid`, pack/SQL после повторной генерации.
- [ ] `SourceGateTests` проходит без маскирования новых генераторов широкими исключениями; тесты продемонстрировали и запрет нового обхода, и допустимые локальные идентификаторы.
- [ ] Если меняется **формула долговечного UID**, отдельно определить судьбу существующих SQL/pack/refs (DET-1 предупреждает о пересоздании), не применять изменение незаметно.
