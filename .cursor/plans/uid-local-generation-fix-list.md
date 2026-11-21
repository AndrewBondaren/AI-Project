Локальные UID вне общего helper — список для фикса

## План исправления: три скоупа (2026-11-19)

Этот раздел — актуальная структура работ по запросу пользователя. Ревью ниже
сохраняется как доказательная база; старые исключения не действуют.
Здесь планируется изменение кода, но сама текущая правка меняет только документ.
Реализация согласованного UID-среза выполнена 2026-11-19: общие helpers,
переключение consumers, удаление локальных формул и усиление source-gate.
Проверка: 51 тест (test_local_uid_identity, test_deterministic_ids,
test_c24_district_packing) прошли. Полный live bake не запускался.
Дополнительно проверен реальный build_tokens: replay, изоляция поселений,
число/порядок/параметры токенов и отсутствие вызова UID helper при count=0.
Последний интеграционный пункт §3 закрыт тестом
test_transition_pack_roundtrip.test_generated_uid_sql_pack_export_and_fresh_import.
На временном мире: штатное создание → генерация здания с UID из app.ids →
SQL и pack publication/read → skeleton export → import в другую временную БД.
Проверены UID SQL/pack, наличие здания/комнат в экспорте, число локаций,
родительские ссылки после импорта и число connection nodes.
Граница проверки: skeleton import, не перенос pack blobs в целевой мир
и не полный terrain bake. Старые пользовательские данные не затрагивались.
Итог: 58 тестов UID/packing/SQL-pack roundtrip прошли; отдельно прошёл
импорт/экспорт восьми fixture-миров. Реализация согласованного UID-среза завершена.
Дополнительный test_perimeter_barrier_sides: 4 падения на сравнении
ValidatedFieldPath с tuple в неизменённом контракте валидации; в UID-срез не входит.
Старые данные не изменялись. Исторические отметки ниже не расширяют скоуп:
перестройка debug/DAG и аудит всех моделей потребителей не входят в эту реализацию.

### Открытые вопросы ревью реализации (2026-11-19)

Статус: CLOSED, 2026-11-19. UID-RV-1 и UID-RV-2 исправлены.
Проверка: 50 тестов test_local_uid_identity, test_deterministic_ids,
test_c24_district_packing прошли; добавлена проверка реального caller
и регрессионные примеры обходов. Gate анализирует локальные выражения
в закрытом скоупе, не является полным межпроцедурным анализатором Python.

- [x] **UID-RV-1 — передача владельца PackingToken.**
  В backend/app/application/worldData/generators/assemblers/districtAssembler/districtAssembler.py:138
  вызов build_tokens не передаёт доступный settlement_uid, поэтому
  packing_token_uid получает None. Предусмотренная планом изоляция по поселению
  теряется (остаются world/координаты/slot/template/copy).
  Требуемое исправление: передать settlement_uid через существующий именованный
  аргумент build_tokens. Регрессионная проверка должна пройти через caller:
  при одинаковых остальных компонентах разные поселения дают разные UID,
  повторный вызов для того же поселения даёт прежние UID.

- [x] **UID-RV-2 — неполное обнаружение локальных формул source-gate.**
  backend/tests/identity/test_local_uid_identity.py:14, local_uid_expressions:
  воспроизведены четыре обхода, для которых проверка возвращает пустой список:
  присваивание item.location_uid = f"...", location_uid = "...".format(...),
  передача через промежуточную переменную и возврат f-строки из локального
  генератора UID. Требуемое исправление: расширить проверку закрытого скоупа
  и добавить отрицательные регрессионные примеры всех четырёх обходов.
  Положительные примеры: обычное форматирование диагностик и получение UID
  через app.ids остаются допустимыми; глобальный запрет f-строк недопустим.



Скоуп: backend UID и backend source-gate. Доставка UID во frontend,
клиентские request/mock ID и новый API выдачи — отдельная задача, не блокер
этого плана. Требование единого генератора проекта этим не отменяется.
Окончательное решение пользователя: обновление старых данных не требуется.
Миграция, удаление, пересоздание существующих SQL/pack/refs и совместимость
со старыми UID не входят в план. Проверки выполняются на новых тестовых данных.
Это уточнение отменяет прежние требования об обслуживании старых данных
во всех исторических разделах ревью ниже.

Вне скоупа по уточнению пользователя: ConnectionEdge, гидрология (water body и
river segment), bootstrap world_uid, pack job UID. Их контракты root/keys и
сигнатуры проектируются отдельно; здесь не добавлять для них API, не заменять
callers и не удалять генераторы. R1/R3/R5 и pack-часть R8 ниже — отложенный
диагностический реестр, не работа и не блокер приёмки этого плана.
Ранее записанные замечания о frontend также не являются блокерами.
Обязательное требование общего генератора сохраняется для отложенных задач.

### 1. Локальные генераторы, которые легко заменить готовым API

Критерий включения: общий API уже обеспечивает требуемую семантику и тип результата;
не требуется новый вид UID, новая формула или новый путь доставки.

| Места (пути относительно backend/app) | Замена | Проверка |
|---|---|---|
| application/chat/chatService.py; application/session/playerService.py; application/session/gameSessionService.py | str(uuid4()) → runtime_uid() из app.ids | Сохранены строковый UUID, уникальность и ссылки message/turn/character/session. |
| application/engine/runtime/dag/dagExecutor.py; invocations/interaction/executionInteraction.py и invocations/recovery/executionRecovery.py внутри application/engine/runtime | str(uuid4()) → runtime_uid() | Owner/claim остаются строками; lease/recovery не меняются. |
| db/repositories/sqlite/bakeOperations/operationStore.py | Все три выдачи operation/owner → runtime_uid() | Создание операции и смена owner сохраняют контракт. |
| db/repositories/sqlite/dagExecutions/executionStore.py | Сохраняемый str(uuid4()) → runtime_uid() | store_id сохраняется между открытиями БД. |
| application/engine/runtime/invocations/memoryExecutionStore.py | uuid4() → UUID(runtime_uid()) | get_store_id() сохраняет UUID; преобразование готового UID не является генерацией. |
| dataModel/perks/perkTemplateOutline.py; dataModel/races/raceTemplateOutline.py | Fallback str(uuid4()) → runtime_uid() | Явно переданный template_uid не меняется; fallback остаётся случайным. |

- [x] Выполнить замены и убрать неиспользуемые импорты uuid4.
- [x] Оставить существующие классы владельцами прежних операций; app.ids отвечает
  только за выдачу UID. Не менять persistence, порядок вызовов и DAG-маршруты.
- [x] Проверить типы результатов и существующие тесты затронутых контрактов.
  Смена источника случайного UUID не требует пересоздания ранее выданных UID.

### 2. Локальные обходы общего генератора — удалить

Это скоуп удаления старой реализации, а не удаления бизнес-операций.
Для каждого потребителя сначала подключается готовая замена из §1 или §3,
после этого в том же завершённом срезе удаляется локальная формула.
Оставлять её как fallback запрещено.

| Что удалить | Где | Предусловие удаления |
|---|---|---|
| Прямые uuid4 и импорты | Все места §1; memoryExecutionStore.py; core/logMiddleware.py | Подключён общий API с нужным типом/форматом. |
| Синтетические location_uid, area_uid и room_uid | areaBarriers.py; structureAreaAssembler.py; cascade/locationScope.py; structure/room/roomFactory.py; api/routes/debug.py | Передан UID настоящего владельца либо подключена принятая централизованная выдача. Не создавать фиктивного владельца только ради UUID. |
| Выдачу PackingToken.uid строковой склейкой | districtAssembler/planner/tokens.py:125/131 | Подключён общий API идентичности экземпляра токена. |
| Разрешения обходов в _EXEMPT и устаревшие комментарии | tests/identity/test_deterministic_ids.py; deterministic-ids.mdc | Gate проверяет новые пути и не разрешает локальные UID. |

- [x] Удалить перечисленные обходы после подключения замен.
- [x] Удалить пустые/неиспользуемые генераторы и импорты; полезные доменные
  обёртки оставить только с делегированием app.ids.
- [x] Проверить отсутствие оставшихся callers старых методов и скрытых fallback.
- [x] Не удалять content fingerprints, парсеры UID и форматирование координат,
  если они не создают идентичность. Это не разрешение маскировать UID под ключ.
- [x] Расширить backend source-gate на строковые формулы; запретить
  исключения для локальной выдачи UID.

Gate этого среза проверяет закрываемые места. Известные нарушения вне скоупа
учитываются точечно как незакрытый долг, а не как допустимые генераторы;
не добавлять широкие исключения файлов. Закрытие всего проектного UID-долга
не является условием завершения этого ограниченного плана.

### 3. Недостающие операции — реализовать в общем механизме, затем заменить

Порядок каждого пункта обязателен: контракт → реализация в app.ids → проверка
общего API → подключение всех потребителей → удаление обхода по §2.

| Операция общего механизма | Потребители / требуемая работа |
|---|---|
| Технический request ID | Прямая замена на runtime_uid(), полный UUID; относится к готовому API §1, расширение не требуется. |
| Контракты location/context identity | standalone/debug BUILDING, отдельные AREA_SCOPE/ROOM_SCOPE; точные сигнатуры ниже. Барьер без владельца получает None, а не новый UID. |
| Packing token UID | Новый PACKING_TOKEN; точные owner/root/keys и обработка n<=0 зафиксированы ниже. |

- [x] Для каждой операции зафиксировать сигнатуру, root/keys, тип результата,
  ошибки, владельца контракта и полный список callers.
- [x] Реализовать недостающие операции и экспорт через app.ids.
- [x] Проверить replay/изоляцию владельцев/уникальность и типы.
- [x] Переключить потребителей и выполнить соответствующее удаление из §2.
- [x] На новых тестовых данных проверить повторяемость генерации, импорт
  и ссылочную целостность. Существующие пользовательские данные не изменять.


### Конкретизация оставшегося скоупа после ревью

Этот раздел заменяет неопределённые формулировки таблицы §3. Он не возвращает
за скоуп рёбра, воду, bootstrap, pack jobs или frontend.

#### Публичный контракт общего механизма

Единственный владелец формулы — app.ids; экспорт через app.ids.__init__.
Новые функции размещаются в app.ids.localIdentity, используют существующие
entity_uid/runtime_uid, не содержат второго UUID/hash-генератора.
Функции принимают только скалярные компоненты, не World, NamedLocation, шаблоны,
контекст, репозитории или pipeline. Результат str, без IO, SQL, логов и вызовов
доменов. Пустая обязательная строка/отрицательный copy_index → ValueError до выдачи.
Не вводить новые POJO ошибок: это внутренние предусловия helper, не HTTP-валидация.

| Сигнатура | Root / закрытый kind / keys и семантика |
|---|---|
| runtime_uid() → str (существующий API) | Канонический UUID целиком, без обрезания. Middleware хранит строку в request_id_var, lifecycle reset остаётся прежним. |
| standalone_building_uid(world_uid: str, template_uid: str, map_x: int, map_y: int) → str | entity_uid(world_uid, BUILDING, channel="standalone", template=template_uid, x=map_x, y=map_y). В существующей ветке с area_uid оставить принятый building helper. Аргумент template_uid здесь получает существующий identity=template_uid or system_name; менять выбор шаблона не входит в срез. |
| debug_building_uid(world_uid: str) → str | entity_uid(world_uid, BUILDING, channel="debug"). Оба debug места получают одинаковый UID при том же мире, как и до замены. |
| area_scope_uid(world_uid: str, building_uid: str) → str | Новый UidKind.AREA_SCOPE; keys building=building_uid. Только контекст/RNG, не ссылка на NamedLocation. Оба места с #area используют один helper. |
| room_scope_uid(world_uid: str, building_uid: str, room_id: str) → str | Новый UidKind.ROOM_SCOPE; keys building=building_uid, room=room_id. Вычисление остаётся перед циклом экземпляров; не добавлять instance_idx/z, не подменять настоящий UID комнаты. |
| packing_token_uid(world_uid: str, settlement_uid: str \| None, origin_x: int, origin_y: int, ground_z: int, slot_index: int, template_uid: str, copy_index: int) → str | Новый UidKind.PACKING_TOKEN; keys x/y/z/slot/template/copy. При settlement_uid != None добавить settlement; None не передавать в entity_uid. Отсутствие settlement допустимо для существующего standalone вызова, root и координаты задают область. |

Имена каналов фиксируются внутри app.ids, caller не собирает строки и не выбирает
канал. Новые kind обозначают три разные идентичности: area scope, room scope и
экземпляр токена; существующие AREA/ROOM остаются идентичностями реальных сущностей.
Уже выданные и явно переданные UID не регенерировать.

#### Точные изменения потребителей

- RequestLoggingMiddleware: runtime_uid() вместо uuid4().hex[:8]. Не добавлять
  транспортный header или API. Формат лог-корреляции теперь полный UUID.
- StructureAreaAssembler: standalone building helper вместо склейки в fallback;
  area_scope_uid вместо #area. Основная district/area цепочка сохраняется.
- debug_building_context: тот же area_scope_uid; area_context/room_context
  принимают готовую строку как прежде. Они не создают сущность и не пишут SQL.
- roomFactory: room_scope_uid до цикла count; выбор count, геометрия и порядок
  RNG-вызовов остаются прежними, кроме значения seed соответствующего scope.
- build_tokens: компоненты owner взять из world.world_uid, settlement_uid и
  slot.origin_x/origin_y/ground_z/slot_index. Для каждого i выдать token UID.
  При n<=0 токена нет: убрать фиктивный uid из сообщения, template уже отражён
  в диагностике; не создавать token UID для отсутствующего экземпляра.
- plan_area_barrier_cells: при building != None использовать готовый location_uid;
  при building == None передать None. MapCell.location_uid уже str | None.
  Синхронизировать аннотацию emit_barrier_cells.location_uid с str | None.
  Не создавать NamedLocation и не выдавать UID несуществующей area.
- debug.py: только заменить две выдачи building UID; изменение маршрута
  генерации этим контрактом не разрешено.

#### Ответственность и признаки отказа

| Класс / модуль | Ответственность, допустимые зависимости и эффекты | Приёмка / отказ |
|---|---|---|
| app.ids.localIdentity, UidKind | Формулы над скалярами, только общий ids; runtime использует энтропию общего helper | Отказ при доменном импорте, IO, второй формуле UUID или свободном kind. |
| ChatService, PlayerService, GameSessionService | Существующие chat/session операции и записи; импорт runtime_uid для выдачи | Типы и число выдач сохранены; отказ при изменении порядка записей/операций. |
| DAGExecutor, ExecutionInteraction, ExecutionRecovery | Существующие execution/claim/lease операции | Только источник owner меняется; отказ при новых нодах, deps или lease-поведении. |
| MemoryExecutionStore, SQLiteExecutionStore, SQLiteBakeOperations | Хранение store/operation/owner; прежние UUID/str границы | Отказ при смене типа, regeneration сохранённого store_id или новых SQL writes. |
| PerkTemplateOutline, RaceTemplateOutline | Fallback template_uid при отсутствии значения | Явный UID сохранён; отказ при повторной выдаче на чтении заданного UID. |
| RequestLoggingMiddleware | Установить/reset correlation context и логировать прежние события | Полный UUID; отказ при изменении request lifecycle или введении API. |
| StructureAreaAssembler и модули locationScope/roomFactory/areaBarriers | Вычисление прежних результатов, получение UID через ids; без нового persist | Отказ при фиктивном owner, новой scope-сущности или переносе room RNG внутрь count. |
| PackingToken и build_tokens | Токен размещения; формирование списка с прежним count/order | Отказ при изменении count, priority, размещения либо UID для n<=0. |
| MapCell и emit_barrier_cells | Результат геометрии с optional owner | Отказ при несуществующей ссылке; геометрия/материал/количество клеток неизменны. |

Новые классы pipeline, CRUD API и POJO не создаются. PackingToken сохраняет поля
uid/template_uid/w/h/priority/required/position/copy_index/n_from; MapCell уже
разрешает None. World, DistrictSlot и RoomDef остаются входными моделями и не
передаются в ids. AREA_SCOPE/ROOM_SCOPE не дублируют AREA/ROOM: они не сохраняются
как NamedLocation. Ошибки доменных операций не заменяются ValueError helper.

#### Порядок реализации и проверки

1. Зафиксировать новые UidKind и реализовать скалярные helpers в общем модуле.
2. Проверить repeatability и изоляцию world/building/room/slot/template/copy,
   полный UUID runtime и отклонение некорректных аргументов.
3. Выполнить §1 и подключить новые helpers; удалить соответствующие формулы
   и импорты в том же срезе. Для барьера убрать UID без владельца.
4. Проверить room scope: одинаковый room_id одного building делит scope;
   разные building/world не делят. Проверить PackingToken count/order и n=0.
5. Создать новые изолированные тестовые данные; проверить повторный bake/import
   и ссылочную целостность без обновления существующих миров.
6. Проверить source-gate:
   source-gate отвергает новые обходы в закрытом скоупе и учитывает отложенный
   долг отдельно. Тесты обязательны при реализации; здесь они не запускались.

#### Результат обязательной приёмки

- Порядок общего механизма → потребители → удаление сохранён по указанию пользователя.
- Для ids CRUD данных и настроек (read/create/update/delete) неприменим:
  helper ничего не хранит и не читает настройки. CRUD потребителей не меняется.
  Междоменные данные передаются скалярами; ids не запрашивает чужой CRUD.
- Новые public pipeline отсутствуют. Это не доказывает законность старых callers.
  Проверен реальный путь api/routes/debug.py:174 →
  StructureGeneratorService.generate_from_template без engine DAG.
  Он нарушает обязательную прямую DAG-границу; сохранить маршрут и одновременно
  объявить весь план принятым нельзя.
- Полный аудит существующих POJO полей/ошибок и вложенных цепочек всех перечисленных
  потребителей ещё не завершён. Таблица ответственности закрывает проектируемый
  UID-срез, но не заменяет этот аудит.
- **Приёмка всего плана остаётся НЕ ПРОЙДЕНА** по обязательному правилу
  dag-generator-interface.mdc: подтверждённый debug обход и недостающая проверка
  вложенных цепочек/POJO. Новые DAG-ноды агент не назначает. Доведение UID-контрактов
  завершено; исправление маршрута требует предусмотренной правилами совместной
  приёмки DAG, а не скрытого расширения этого плана.


### Порядок и готовность

Три скоупа — классификация работ, не команда удалить всё до появления замены.
Источник порядка: запрос пользователя от 2026-11-19 — для недостающих операций
сначала имплементировать общий механизм, затем заменить локальные генераторы.
§1 использует готовый API; §2 закрывается вместе с соответствующим переключением;
для §3 зависимость «реализовать → заменить → удалить обход» обязательна.

План пока OPEN: таблицы выше задают скоуп, но не подменяют обязательную приёмку
контрактов, каждого класса/POJO, CRUD и фактических DAG-маршрутов, указанную в ревью.
Новые ноды и порядок доменных операций этим документом не утверждаются.
Frontend и обновление старых данных не входят в этот план.
Полнота backend-инвентаря проверяется отдельно, а не выводится
из одного regex-поиска.



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
- [ ] Проверить новые формулы на новых тестовых SQL/pack/refs;
  обновление старых данных исключено окончательным решением пользователя.
- [ ] Проверить повторяемость, изоляцию владельцев и ссылочную целостность.
- [ ] Source-gate должен отвергать новый локальный UID, включая строковую формулу,
  и пропускать доказанный content fingerprint без широкого исключения файла.
- [ ] Прогнать соответствующие тесты после реализации. В этом ревью выполнены
  чтение и статический поиск; тесты не запускались, исправления не объявлены закрытыми.


Статус: OPEN, диагностический fix-list (не новый архитектурный план).

Срез: master, 16098c1a2e6c6fa32d89631abd941cb6f91c097c, 2026-11-17 (после актуализации ветки; новые UID-генераторы в добавленных файлах не найдены).
Объём: обнаруженные формулы, проверка границ их применения и source-gate. Реализация не менялась.
Где находится общий механизм UID
- Реализация: [`backend/app/ids/deterministicIds.py`](../backend/app/ids/deterministicIds.py).
- Публичный импорт: [`backend/app/ids/__init__.py`](../backend/app/ids/__init__.py) (app.ids).
- Закрытые типы: [`backend/app/ids/uidKind.py`](../backend/app/ids/uidKind.py): UidKind, LibraryKind.
- Тест и source-gate: [`backend/tests/identity/test_deterministic_ids.py`](../backend/tests/identity/test_deterministic_ids.py), SourceGateTests.
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
