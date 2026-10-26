# NL as typed host — вынос type-specific данных в payload — DONE

**Статус:** завершён 2026-10-07. Все шаги P0–P6 и S1/S1b/S1c/S1d/S2 реализованы и проверены.
Каскад — linked list полей POJO; verifier и runtime не используют вложенность
локаций или enum-rank для порядка. Terminal defaults читаются из POJO через
FieldRef. Повторяемые каналы материалов разворачиваются по declared scope-пути
остальных linked lists; экономика сохраняет явную цепочку. Payload — единственное
хранилище type-полей; is_inhabited гейтит специализации и planner.
Проверки S2: 187 focused tests OK; npm run typecheck:cascade OK;
full suite 1574 tests — те же 21 ошибки baseline и 1 expected failure, новых нет.
Parent-цепочка, DAG wiring, economy gate и TEST-DB-1 остаются отдельными задачами.
S1d заменил публичные строковые source-ссылки на FieldRef; runtime-verifier
сохранён, статические проверки выполняются через `npm run typecheck:cascade`.

### P5 — выполнено 2026-10-07

- `SettlementSkeleton` остаётся единственным assembler POJO; plain type-поля
  наследуются от SettlementPayloadFields, economic_tier-channel не меняется.
- `settlementSkeletonAccess.settlement_skeleton_pojo(location)` строит authored
  view из typed payload и двух generic полей NL (system_economic_tier/mood).
  `resolved_settlement_skeleton(location, *, economic_tier, settlement_density)`
  валидирует resolved view; явный None сохраняется. dominant_material остаётся
  None в assembler view, как раньше: итоговый материал берётся из каскада/fold.
- Удаляются CitySkeleton dataclass, mirror/copy/alias helpers, старый модуль
  citySkeleton.py и все его импорты. Consumers используют SettlementSkeleton.
- Bundle содержит только generic поля и typed location_payload. before-validator
  продолжает читать flat type wire keys/aliases по payload-модели; serializer
  больше не исключает несуществующие flat-поля. Удаляется лишний фильтр type-полей
  из DB→generic POJO conversion после P2b.
- Это один шаг контракта представления, без изменения planner rules, живости,
  parent-иерархии, materialization, generic tier fallback или RNG.

Результат P5:

- Overlay/alias literals и startup maps удалены из SettlementSkeleton;
  generic economic-tier channel сохранён. Shared payload fields не дублируются.
- Bundle содержит generic поля и location_payload, без плоских type-полей
  и _skeleton_default. Wire aliases проходят прежний payload-validator;
  to_db_fields сериализует модель без таблицы исключений.
- CitySkeleton dataclass/module и все старые импорты удалены. Assemblers,
  road/layout/planner consumers и fixtures используют SettlementSkeleton.
  Новый application adapter settlementSkeletonAccess строит source/resolved
  POJO, сохраняя authored данные, branding, None и независимые nested values.
  DB→generic POJO conversion больше не фильтрует удалённые type-колонки.
- 257 focused tests OK + 5 wire tests OK; полный набор 1560 tests,
  21 прежняя ошибка (IDs совпадают с P2b), 1 expected failure; новых FAIL нет.
  `npm run typecheck:cascade`, compile debug-скриптов и `git diff --check` — OK.
  Grep старых overlay/shim API по backend Python пуст.
  Логи: `.local/nl-payload-p5-focused.log`, `.local/nl-payload-p5-wire.log`,
  `.local/nl-payload-p5-tests.log`.

### P2b — выполнено 2026-10-07

- Из основной SQL-схемы и DB dataclass удалены 11 type-колонок:
  10 settlement-полей и district_topology. Generic stamped channels сохранены.
- Удалены legacy read fallback и legacy-перенос в CRUD update. SQL NULL
  даёт дефолты payload-модели, без чтения плоских runtime-атрибутов.
  Плоский wire import/update и aliases продолжают работать через validator.
- Constructor/update fixtures и два debug-скрипта переведены на payload.
  Fixture world-типа city явно объявляет payload_kind; C11 fixture с **dict
  также обновлён. Debug-скрипты проверены compileall, не запуском HTTP/backend.
- Основная схема на temp DB: validate_schema, точное совпадение колонок
  с NamedLocation, отсутствие type-колонок по payload-контрактам,
  NULL/empty/nested repository roundtrip, CRUD, import и cascade binding.
  Рабочая dev-БД не удалялась и не пересоздавалась.
- 303 focused tests OK + 12 C11 tests OK. Полный набор: 1559 tests,
  21 прежняя ошибка (error IDs совпадают с S1d), 1 expected failure;
  новых FAIL нет. `npm run typecheck:cascade` и `git diff --check` — OK.
  Логи: `.local/nl-payload-p2b-focused.log`, `.local/nl-payload-p2b-c11.log`,
  `.local/nl-payload-p2b-tests.log`.

### S1d — выполнено 2026-10-07: типизированные ссылки на поля

Уточнение реализации 2026-10-07: Pyright не анализирует выражения metadata
внутри `Annotated` (проверено отрицательным примером). Поэтому `FieldRef`
объявляется отдельной константой вне `Annotated`, а metadata использует
готовую ссылку. Это обязательно для статической проверки атрибутов;
self-ссылки могут объявляться перед классом благодаря model supplier.
Pyright 1.1.414 добавлен в корневые npm devDependencies по запросу мастера;
команда проверки и положительные/отрицательные fixtures входят в S1d.


- `FieldRef[M, T]` содержит `model: Callable[[], type[M]]` и
  `select: Callable[[M], T]`, где `M` — source-POJO. Пример:
  `FieldRef(lambda: DistrictTemplateEntry, lambda pojo: pojo.density)`.
  Типизатор должен выводить тип аргумента селектора из model supplier;
  это проверяется отдельным статическим примером до миграции объявлений.
- `CascadeLink(ref: FieldRef[M, T], level: ScopeAxis)` и
  `CascadeDefault(ref: FieldRef[M, T])` заменяют публичные пары model/str.
  Для self-ссылки используется тот же API с `lambda: OwnModel`:
  supplier вызывается после создания классов, не при исполнении тела класса.
- Разрешён только непосредственный выбор одного атрибута POJO.
  Generic binding определяет имя через probe, проверяет его в
  `model_fields` / computed fields и создаёт нормализованный ключ
  `(model, field_name, level)`. Вложенные пути, вычисления, неизвестные поля
  и иные результаты селектора отвергаются; AST/bytecode не разбираются.
  Для link требуются обычное поле и channel metadata; computed-поля
  разрешены только для terminal default.
- Внутренние строковые имена остаются результатом introspection для ключей,
  чтения и provenance, но пользователь не объявляет их вторым источником
  истины. Равенство узлов определяется нормализованным ключом, не identity
  lambda. Нет списка моделей/полей, enum имён или доменных веток в движке.
- Статическая проверка выявляет неизвестный атрибут и несовместимую
  сигнатуру селектора. Совместимость разных каналов, kind-aware типы,
  ось и целостность linked list по-прежнему проверяет verifier.
  Имена параметров `Cascade.field` и обработчиков fold/materialize
  не являются ссылками на source-поля и в этот шаг не входят.
- Миграция деклараций и потребителей выполняется одним изменением
  контракта, без постоянного legacy API. Семантика наследования, порядок,
  дефолты, RNG и provenance сохраняются. DAG не участвует.

Результат S1d:

- Все production links и terminal defaults переведены на FieldRef; старые
  сигнатуры и self-маркер удалены. Движок использует BoundField/CascadeNode
  с нормализованным ключом; лишние owner-таблицы убраны.
- Селекторы links вынесены из Annotated, поскольку Pyright игнорирует
  metadata-выражения. AST-тест защищает это обязательное размещение.
- Pyright 1.1.414 закреплён в npm devDependencies/package-lock. Команда
  `npm run typecheck:cascade` проверяет production-декларации и positive
  fixtures (0 ошибок), затем четыре exact negative diagnostics.
- Для static gate в BundleNamedLocation явно проверены str-ключи типа/
  subtype и наличие entry перед обращением к реестру; валидный wire-путь
  сохранён, нет подавлений diagnostics.
- 123 focused tests OK. Полный набор: 1559 tests, 21 прежняя ошибка и
  1 expected failure; error IDs совпадают с P4, новых FAIL нет.
  Логи: `.local/nl-payload-s1d-focused.log`, `.local/nl-payload-s1d-tests.log`.
- Runtime проверяет форму селектора, POJO-поле, channel/param/scope,
  kind-aware типы, циклы/разрывы/ветвления; computed defaults не вычисляются
  при binding. Static gate ограничен декларациями каскада, не всем backend.

### P4 — выполнено 2026-10-07

- `SettlementPayload` объявляет каналы размера, density и dominant material
  на SETTLEMENT. Размер и dominant — по одному узлу; density сохраняет
  связь `DistrictTemplateEntry.density → SettlementPayload.settlement_density`.
- Три NL-поля/канала и их рёбра к skeleton удалены. Соответствующие поля
  skeleton остаются plain assembler inputs, без cascade metadata.
  Generic economic tier (включая skeleton fallback) и parent materials
  не менялись; fold/default и границы наследования сохраняются.
- Settlement caller передаёт payload отдельным Link; `source_wire` удалён.
  Generic NL conversion не проецирует type-значения в NL. Resolver изменений
  не потребовал: новые source-узлы обнаруживаются тем же metadata walker.
- Authored provenance type-параметров теперь `SettlementPayload.field`.
  Обновлены runtime/contract assertions, добавлены проверки точного состава
  сокращённых цепочек и production binding на settlement/location_complex
  с конфликтующими legacy-значениями. **115 focused tests OK**.
- Полный прогон — **1551 tests**, **21 прежняя ошибка**, **1 expected failure**;
  error IDs совпадают с P3. Логи — `.local/nl-payload-p4-focused.log`
  и `.local/nl-payload-p4-tests.log`. `git diff --check` — OK.

### P3 — выполнено 2026-10-06

- Все группы (a–e) перенесены в `location_payload`: flat wire и aliases
  сохраняются, `BundleNamedLocation` валидирует поля выбранной payload-моделью,
  `to_db_fields` исключает type-поля из плоского persist-словаря. Реестр world
  передаётся через validation context; custom types работают без списка имён.
- Import/create/update используют один контракт; CRUD сливает текущий payload
  и переданные поля, сохраняет неизменённые значения, допускает явный `None`.
  При обновлении legacy-строки её данные сначала переносятся в payload.
  Recipe default `is_inhabited` применяется при импорте; явное значение выше.
- `locationPayloadAccess` валидирует persisted JSON на чтении. Payload имеет
  приоритет над legacy-колонками; только `location_payload=None` включает
  временный fallback, который удаляется в P2b. Skeleton, footprint/occupancy,
  index/render и district topology переведены на этот typed API.
- District freeze создаётся в `DistrictPayload`; SQL persist выполняет
  read–validate–merge type-stamped поля внутри транзакции перед upsert.
- До P4 flat source-поля/metadata на Bundle сохранены: `source_wire` проецирует
  payload в старые NL cascade-узлы только в памяти. Новое хранение не дублирует
  type-колонки; приоритеты и provenance действующего каскада не изменены.
  Мост удаляется/пересматривается вместе с переносом каналов в P4.
- Добавлены семь проверок на основной SQL-схеме: все группы wire→payload,
  CRUD сохранение/очистка, recipe default/override, payload priority и invalid
  JSON, district typed storage, legacy partial update, custom world import
  и каскад. Обновлены прежние wire/extract assertions.
- **267 focused tests OK**, `compileall` / `git diff --check` — OK.
  Полный прогон — **1549 tests**, **21 прежняя ошибка**, **1 expected failure**;
  error IDs совпадают с P2a. Логи — `.local/nl-payload-p3-focused.log`
  и `.local/nl-payload-p3-tests.log`.

### P2a — выполнено 2026-10-06

- `named_locations.location_payload TEXT` и `NamedLocation.location_payload`
  (`dict | None`, `json_nullable_col`) добавлены синхронно. Legacy поля
  сохранены до P3/P4; импортер и runtime-потребители пока не мигрировали.
- Три новых теста используют основную `0001_initial.sql` на временной БД:
  validate_schema + точное соответствие колонок; nullable TEXT; repository
  roundtrip NULL / empty / nested JSON; обновление payload сохраняет generic
  поля и допускает очистку до NULL. Dev SQLite не удалялась/не пересоздавалась.
- Focused набор — **131 tests OK**, `compileall` / `git diff --check` — OK.
  Полный набор — **1542 tests**, **21 прежняя ошибка**, **1 expected failure**;
  error IDs совпадают с P1b. Логи — `.local/nl-payload-p2a-focused.log`
  и `.local/nl-payload-p2a-tests.log`.

### Уточнение зависимости P2/P3 — 2026-10-06

P3 не может сохранять `location_payload` до появления колонки и поля
DB-модели. Исходный порядок P3→P2 также не позволяет удалить legacy
колонки до миграции их потребителей и каскадных аннотаций P4.
P2 разделён: P2a добавляет nullable JSON-хранилище без удаления старых
полей; P3 переносит чтение/запись; P4 переносит каскадные каналы;
P2b удаляет legacy SQL/model поля после этих зависимостей. Целевая схема
не меняется. Один проверяемый шаг за заход сохраняется.

### P1b — выполнено 2026-10-06

- `locationFootprintPolicy` выбирает root pipeline по `PayloadKind.SETTLEMENT`,
  fine footprint — по settlement/district контракту. Удалены legacy список
  типов и subtype fallback; неизвестный/generic type не проходит gate.
- Policy принимает world registry. C6, packing targets, occupancy, territory
  volumes, layout geometry, detailed bake и L0 contributor передают его;
  renderer учитывает переданный registry при выборе marks и легенды.
  Это необходимые callers одного изменённого policy-контракта; они включены
  в состав P1b. DAG-ноды и живость не менялись.
- `settlementOutdoorTypes.is_district_location` проверяет district payload
  контракта; builtin district/building factories сохраняют своё назначение.
- Subtype `settlement/dungeon` удалён; `underground_city` сохранён.
  Complex recipes используют нейтральное имя footprint-набора.
- Добавлены четыре регрессионных теста: выбор по контракту, false-positive
  geographic subtype / legacy city, custom world types, C6/packing,
  district fine-геометрия, явное отключение builtin payload и render marks.
  Обновлены recipe/legend tests. Focused набор — **168 tests OK**.
  Полный набор — **1539 tests**, **21 прежняя ошибка**, **1 expected failure**;
  error IDs совпадают с P1. Логи — `.local/nl-payload-p1b-focused.log`
  и `.local/nl-payload-p1b-tests.log`. `git diff --check` — OK.

### P1 — выполнено 2026-10-06

- `PayloadKind` + `LocationPayload.models/model_for/validate` задают builtin
  dispatch по контракту (`settlement` / `district`), независимо от имени
  типа. Неизвестный kind и payload у generic-типа отвергаются.
- `SettlementPayload` содержит type-поля + `is_inhabited=True`;
  `DistrictPayload` — typed `DistrictTopologySlot | None`. Общая база
  `SettlementPayloadFields` сохраняет определения/aliases skeleton без
  дублирования; generic tier/mood и текущие CascadeChannel остаются
  только на skeleton до P4. `is_inhabited` не добавлен в legacy skeleton:
  его assembler ещё читает поля с плоской NamedLocation.
- `LocationTypeEntry.payload_kind` валидируется; fixture_identity и
  engine/world merge сохраняют его. Отсутствующее поле наследует engine,
  явное значение/null имеет приоритет.
- Новый `location_complex` с пятью рецептами `crypt/mine/ruins/fortress/lair`:
  district types, footprint по рангам и `is_inhabited=False` на subtype.
  District/building hierarchy допускает комплекс как родителя. Применение
  recipe default к экземпляру — при миграции import; сейчас только контракт.
- Добавлены 10 тестов dispatch/validation, aliases, typed topology,
  default/frozen semantics, generic-поля/каналы, builtin seed и world overlay,
  hierarchy и живость рецептов. Focused наборы: **75 + 103 tests OK**.
  `compileall` и `git diff --check` — OK. Полный набор — **1535 tests**,
  **21 прежняя ошибка**, **1 expected failure**; error IDs совпадают с S1c.
  Лог — `.local/nl-payload-p1-tests.log`. SQL/schema не менялись.

### S1c — выполнено 2026-10-06

- `CascadeDefault(model, field)` заменяет `default_value/default_registry`.
  Verifier проверяет тип POJO, обычное/computed-поле и совместимость
  его типа с полем контекста; `NONE_IS_ERROR` запрещает fallback-ссылку.
- `LocationCascadeDefaults` хранит канонические дефолты в полях модели;
  медиана тира — ленивое computed-поле, вызывающее политику реестра.
  Значения nullable authored-полей не менялись: `None` наследует.
- `LocationContext.root(world, default_sources=(pojo, ...))` сохраняет
  источники без вычисления полей. Location-caller `root_context(world)`
  передаёт POJO с world-реестром. Resolver читает ссылку только после
  исчерпания authored-цепочки и наследия; таблица `_REGISTRIES` удалена.
- Нет источника, неоднозначный экземпляр или `None` terminal default —
  явная ошибка. Provisional default сохраняет provenance, не служит
  materialize-якорем, не перевычисляет медиану и не повторяет WARNING.
- Добавлены 12 тестов: ordinary/computed поля, неверные декларации,
  supplied value, missing/ambiguous/None runtime source, authored без
  fallback, ленивое и однократное чтение медианы.
- Focused набор — **103 tests OK**. Полный прогон — **1525 tests**,
  **21 errors**, **1 expected failure**; список ошибочных тестов полностью
  совпадает с baseline S1b (новых ошибок нет). Лог —
  `.local/nl-payload-s1c-tests.log`. `git diff --check` — OK.

### S1b — выполнено 2026-10-06

- `runtimeChain.bind_chain` привязывает declared links к накопленным POJO
  и отдаёт один итератор на параметр, сохраняя порядок и пустые узлы.
  Несколько подходящих объектов одного канала — явная ошибка.
- `ordered_scopes` выводит последовательность границ из связей полей
  всех параметров. Движок не использует порядок enum или ручной список
  доменов. Неоднозначные/противоречивые ограничения отвергаются.
- Параметры берутся из метаданных модели входного контекста; новый
  параметр и source-модель не требуют правок resolver.
- `_node_results` сохраняет вычисленные значения/provenance узлов.
  Предки не перечитываются и не перебрасывают RNG; дочерние контексты
  получают отдельное состояние. Fold/default наследуются как раньше;
  перенос default-источников остаётся отдельным S1c.
- `empty_location_chain` использует тот же выведенный путь, включая
  явные пустые границы; запрос root возвращает невычисленный root.
- Добавлены 10 runtime-тестов: иной порядок enum, новый параметр,
  полный bound iterator, пустые границы, POJO default/None, снимки
  предков, независимые sibling-контексты, неоднозначная привязка/порядок,
  root и однократный materialize.
- Focused каскадный набор — **91 tests OK**. Полный набор — **1511 tests**,
  **21 errors**, **1 expected failure**. Те же 21 errors в шести модулях
  воспроизведены с прежними runtime-модулями из HEAD, загруженными только
  в память; рабочие файлы и остальные изменения не откатывались.
  Причины: устаревшие DDL fixtures, невалидные StructureTemplate fixtures,
  старый вызов location renderer. Логи — `.local/nl-payload-s1b-tests.log`
  и `.local/nl-payload-s1b-baseline.log`.

### S1 — выполнено 2026-10-06

- Из verifier удалена проверка вложенности scope; порядок каналов
  определяется объявленными связями `above/below`.
- После поиска всех usages удалены неиспользуемые helpers
  `containment_parents`, `scope_adjacent`, `scope_descendant_of`
  из `ScopeAxis` и override из `ScopeLevel`. `rank` сохранён для
  существующих runtime-caller'ов до S1b.
- `ordered_chain` теперь отвергает ветвления и требует единственные
  верхний и нижний концы; неоднозначные соседи больше не перезаписываются
  молча при сборке списка.
- Добавлены 12 регрессионных тестов: порядок по links независимо от
  порядка enum/полей, разные source-модели, циклы, оторванный цикл,
  разрывы, оба вида ветвления, отсутствующее поле, типы, ось и покрытие.
- `python -m unittest tests.test_location_context_contract tests.test_context_extend
  tests.test_cascade_context_baseline tests.test_cascade_migration_m2`
  из `backend` — **81 tests OK**. `git diff --check` — OK.

### Перепроверка исходного состояния до S1 — 2026-10-06

- В текущем коде verifier дополнительно проверяет вложенность scope.
  Эта зависимость не относится к linked list полей и подлежит удалению
  в S1. Проверка покрытия `param.levels` остаётся декларативной.
- `python -m unittest tests.test_location_context_contract tests.test_context_extend`
  из `backend` — **55 tests OK**. Они не содержат отдельных кейсов на
  новый контракт generic linked-list walker, поэтому зелёный съют
  не закрывает переработанный S1 целиком.
- Runtime `settlement → building` отклонён
  с `level building skips a level after settlement`. Это **не доказательство
  бага**: связанный каскад не должен перепрыгивать промежуточные домены.
  Предыдущее требование разрешить такой переход отменено.
- В текущем `building_context` нет `EmptyLink(AREA)`-заплатки. Пустой
  AREA есть в `debug_building_context`; реальный plot и намеренно пустые
  debug-scopes не удаляются автоматически. S1b теперь про разворачивание
  linked list движком, а не про разрешение коротких scope-путей.
- `hills` нет в DDL `named_locations` и DB-модели. В P0 поле убрано
  из списка NL-колонок; отдельное ТЗ overlay hills сохранено как целевое.
- В рабочем дереве до начала этого плана уже есть изменения структуры,
  переходов, settlement persist и тестов. P0 меняет только ТЗ и этот план.

## Мотивация

`named_locations` — generic-строка для всех типов локаций, но на неё приплюснуты
settlement-специфичные authored-поля (`dominant_material`, `settlement_density`,
`architectural_style`, `frontage_type_order`, `plot_counts`, `plot_priority`,
`perimeter_barrier`, `typical_districts`, `system_settlement_specializations`,
`district_topology`, `system_city_size`). Симптом — «дубль»: одно поле на
`BundleNamedLocation` + то же поле на `SettlementSkeleton`, два узла одной
каскадной цепочки (`NL → skeleton` через `CascadeLink`).

Целевая модель: **NL = абстрактный хост** (место на карте: uid, type, footprint,
occupancy, generic stamped-поля), а type-семантика живёт в **payload по
`payload_kind`**. Один payload-контракт может обслуживать несколько типов:
живой город и мёртвый комплекс (крипта, шахта, руины, крепость) строятся
**одним pipeline** (footprint → district topology → plot packing), но
отличаются семантикой «живости».

Уже имплементированная половина: LOC-T-3 — `locations[]` occupancy на plot
(NL-экземпляры занимают клетки). Недостающая — вынести type-семантику с NL.

## Целевое состояние

### Разделение полей

**Остаётся на NL (generic, есть у локации любого типа):**

- identity/hierarchy: `location_uid`, `display_name`, `system_location_type`,
  `system_location_subtype`, `parent_location_uid`
- discovery/access/state: `is_discovered`, `is_accessible`, `entry_difficulty`,
  `guard_level`, `is_public`, `is_forbidden`, `is_selectable`, `is_mobile`,
  `owner_uid`, `state_uid`, `system_climate_zone`, `system_location_mood`,
  `display_*`, `glossary_ref`, `tag_refs`, `created_at`
- geometry/occupancy: `map_x/y/z`, `system_template_uid`, `is_outdoor`,
  `is_sheltered`, `is_transit`
- **generic stamped cascade-каналы**: `system_economic_tier`,
  `parent_wall_material`, `parent_floor_material` — stamped-узлы на всех
  scope'ах; у room-локации комплекса тоже есть tier и материалы стен. Это
  легитимные NL-поля, не leak.

**Уезжает в `location_payload` (type-specific; authored + type-stamped):**

- `SettlementPayload` (`payload_kind:"settlement"`):
  `system_city_size`, `settlement_density`, `dominant_material`,
  `architectural_style`, `frontage_type_order`, `plot_counts`, `plot_priority`,
  `perimeter_barrier`, `typical_districts`, `system_settlement_specializations`,
  **`is_inhabited: bool = True`** (решено: флаг живости — поле payload,
  authored per-локация; руины-город можно пометить живыми)
- `DistrictPayload` (`payload_kind:"district"`, тип `district`):
  `district_topology` — C23 **type-stamped** freeze на district-строках;
  второй реальный payload-тип.

**Граница payload (решено, = `tz_locations` §Payload per type):** payload =
authored (import) **+ type-stamped** (результат генерации домена типа:
`district_topology`, `system_city_size`). На NL-колонках остаются только
**generic** stamped-каналы каскада. Префикс `system_` **не** означает
«колонка NL» — `system_city_size` живёт в payload.

Полная классификация — `tz_locations.md` §«Payload per type» (обновить:
`dungeon` → `location_complex`, `is_inhabited`, убрать `hills` из списка
NL-колонок — такой колонки нет в DDL).

### Контракт payload — решено: `payload_kind`

```text
named_locations                      # generic host-строка (DB + wire)
  system_location_type ──► location_type_registry[].payload_kind
                             ──► builtin payload-модель
    "settlement"       → SettlementPayload  (≈ сегодняшний SettlementSkeleton)
    "district"         → DistrictPayload    (district_topology)
    null               → без payload (geographic, climate_pole, declare-only)
```

| `system_type` | `payload_kind` | Комментарий |
|---|---|---|
| `settlement` | `settlement` | живое поселение; subtypes `city` / `village` = рецепт морфологии |
| `location_complex` | `settlement` | **не живое**: `is_inhabited=false` по умолчанию в рецепте; subtypes `crypt` / `mine` / `ruins` / `fortress` / `lair` … — свой рецепт (`typical_district_types`, `footprint_by_size`, `required_structure_types`) на `LocationTypeSubtypeEntry`, как у `city`/`village` |
| `district` | `district` | |
| `building`, `room`, `region`, `territory`, `geographic`, `climate_pole` | `null` | |

- **Привязка — `payload_kind`** (новое поле на `LocationTypeEntry`,
  `null` = generic без payload): type-ключи — данные мастера (N+1 реестр),
  payload-контракты — код. Мастер может объявить `elven_city` с
  `payload_kind:"settlement"`.
- `subtype` остаётся рецептом морфологии внутри типа.
- **`location_complex` — отдельный `system_type`**, не subtype поселения.
  Имя нейтральное: «данж» подразумевает подземелье, а положение
  (поверхность / под землёй / в воздухе) — **не семантика типа, а `map_z`**,
  как у города. Следствие: subtype `dungeon` у `settlement` в
  `worldLocationTypeRegistry._ENGINE_ENTRIES` **удаляется** (→ тип
  `location_complex`). `underground_city` **остаётся** subtype'ом
  `settlement` (решено): это семантика живого города — свой рецепт,
  удобнее собирать данные и давать описания; `map_z` рецепт не заменяет.
- **Живость** (`is_inhabited`) гейтит: `system_settlement_specializations`
  (торговля/экономика), economy planner, lazy-settlement DAG-ноду
  (`lazySettlementNode._SETTLEMENT_TYPES` — хардкод имён типов, DAG не
  трогаем, фиксируем как leftover для gate DAG). Pipeline застройки
  (`is_settlement_map_site`, C23 topology, C24 packing) гейтится по
  `payload_kind == "settlement"`, **не** по строке типа/subtype
  (`locationFootprintPolicy._LEGACY_FOOTPRINT_SYSTEM_TYPES`,
  `_settlement_subtypes()` → через реестр `payload_kind`).
- Payload — pydantic-модель per kind, живёт в `dataModel/locations/<kind>/`.
- Импорт `locations[]`: `payload_kind` типа строки выбирает payload-модель,
  authored type-поля валидируются ей, а не плоской NL-моделью. Wire-ключи
  `locations[]` не меняются.
- `architectural_style` — пограничное: сейчас settlement-authored, в payload;
  если станет generic для зданий — промоут на NL отдельным решением.

### Хранение — решено: вариант A (`location_payload` JSON-колонка)

**Размер не заменяется контейнером.** `system_settlement_size` — целевое
доменное имя ранга из LOC-T-2; существующий wire/POJO/DDL ключ —
`system_city_size`. `location_payload` — контейнер type-specific полей,
внутри которого остаётся поле ранга. Этот план переносит место хранения,
но сохраняет wire-ключ `system_city_size`; rename в
`system_settlement_size` — отдельное изменение контракта, не делается
неявно вместе с переносом. В ТЗ оба имени и место хранения показаны явно.

`named_locations` получает одну колонку `location_payload TEXT` (JSON);
settlement overlay-колонки и `district_topology` удаляются. Payload
валидируется pydantic-моделью per kind на импорте и на load — sqlite хранил
эти поля и раньше как JSON-текст в отдельных колонках, на уровне SQL ничего
не теряется (проверено: `WHERE` по overlay-полям в коде нет; индексы только
на `world_uid`, `parent_location_uid`, `type`, `is_public`).

**Type-stamped запись** (`district_topology`, `system_city_size`): persist
делает read-modify-write `location_payload` через payload-модель
(`model_copy(update=…)` → dump), одна запись на NL-строку в рамках
persist-сервиса; генератор payload не пишет (`layer-boundaries`).

Отвергнутый вариант B (per-type таблицы): join на каждое чтение и
репозиторий на каждый type за возможность SQL-запросов, которых нет.
Если позже появится SQL-консьюмер конкретного payload-поля —
`json_extract` или проекционная колонка точечно.

### Каскад после переезда

- Settlement-параметры (`CITY_SIZE`, `SETTLEMENT_DENSITY`, `DOMINANT_MATERIAL`)
  теряют NL-узел верха цепочки — authored живёт только на payload
  (=`SettlementSkeleton`). Значения и дефолты принадлежат payload/доменным
  POJO; движок читает их через объявленные каналы. Дубль исчезает.
  Для `location_complex` те же каналы — payload тот же.
- Generic stamped-каналы (`ECONOMIC_TIER`, `WALL_MATERIAL`, `FLOOR_MATERIAL`)
  остаются на NL — они и есть «stamped beats authored» слой.
- **Linked list полей — контракт каскада (уточнение мастера).** Порядок
  и приоритет задаются `CascadeChannel` + `CascadeLink.above/below` на
  полях POJO. Движок сам находит концы и разворачивает связанный граф
  в один упорядоченный проход **для каждого параметра**. Ручной список
  доменов, моделей, полей или дефолтов в движке не допускается.
- **Домены не перепрыгиваются.** Текущие границы — world → settlement →
  district → area → building → room. Это описание текущего контракта,
  не таблица обхода в resolver. Узлы сохраняют объявленные связи;
  отсутствие runtime-объекта / `None` не создаёт shortcut между доменами.
  `EmptyLink` сохраняет пустую границу. `param.levels` описывает покрытие
  параметра; параметр, объявленный только на settlement, наследуется
  ниже без искусственных каналов.
- **Иерархия NL отдельно от каскада.** `parent_location_uid` и
  `parent_types` задают семантическую вложенность локаций, а не порядок
  полей cascade linked list. Порядок определяется только `above/below`.
  Generic parent-обход и parenting остаются отдельной задачей.
- **Одна scope-ось (решено, правка ТЗ):** `location_complex` **не** вводит
  отдельную ось `DUNGEON→LEVEL→ROOM`. Комплекс = тег `SETTLEMENT` на той же
  локационной оси (районы — `DISTRICT`, здания — `BUILDING`, помещения — `ROOM`);
  уровни комплекса — `map_z` + `parent_location_uid`, не scope-тег.
  `tz_locations` стр. «своя scope-ось» и `tz_cascade_context` §2 — привести
  к этому.
- **Level-agnostic каналы — ограниченно.** Контракт `cascadeSpec` —
  двусвязный список с единственным top/bottom; узел «NL на любом scope»
  в него не ложится там, где между NL-узлами стоят чужие
  (`ECONOMIC_TIER`: `DistrictTemplateEntry` / `PlotLayoutTemplate`).
  Решение: `WALL_MATERIAL` / `FLOOR_MATERIAL` (только NL-узлы) — одна
  декларация с маркером «repeat on every tag»; `ECONOMIC_TIER` остаётся
  явной ×4 цепочкой. S2 ввёл `RepeatScope.EVERY_TAG` и разворачивание
  по scope-пути остальных declared linked lists; verifier запрещает mixed/links
  и неоднозначный порядок. Контракт закреплён в `tz_cascade_context` §2.

### Контракт runtime-движка — уточнение мастера

- Вход — контекст и экземпляры source-POJO на очередной границе;
  caller делает преобразование DB/runtime → POJO, но не собирает ручной
  порядок каналов. Generic walker принадлежит движку каскада
  `application/worldData/context/`.
- Сборка и вычисление разделены: верифицированные `above/below` →
  привязка к source-объектам → единый runtime-проход. Материализованный
  список не обязателен: допустим iterator, порядок тот же.
- Направление наследования — от верхнего домена к нижнему; приоритет
  полей внутри параметра сохраняется по declared links. Нельзя просто
  обратить first-non-null порядок и поменять победителя канала.
- Значение шаблона и дефолт модели находятся **в самом POJO**.
  `None` означает продолжение наследования; ненулевой дефолт экземпляра
  участвует как значение узла. Движок не подставляет литералы и не
  хранит таблицу «параметр/домен → default».
- Дефолты, зависящие от мира (например медиана тира), и доменные fold /
  materialize правила вычисляет доменный POJO/его объявленный обработчик;
  их вход/результат доступны движку через контракт, без веток по имени
  параметра. Безусловный дефолт на каждом дочернем поле не добавляется:
  он затёр бы наследование; terminal default-источник объявляется в
  той же цепочке отдельно, когда нужен.
- Узлы materialize вычисляются однократно на экземпляр/границу;
  расширение runtime-цепочки не перебрасывает RNG предков. Сохраняются
  provenance и границы ответственности persist / generators.
- Verifier проверяет поля, типы, identity параметра, ось, концы,
  согласованность связей, циклы, разрывы и ветвления. Обход не зависит
  от enum-rank или правил вложенности локаций.

### Data flow

```text
import locations[]  → BundleNamedLocation (generic) + payload per payload_kind
persist           → named_locations row + location_payload JSON
runtime           → assembler читает payload (skeleton), stamped generic — с NL
source POJO       → metadata linked list → generic runtime iterator → resolved context
stamping generic  → NL-колонки (system_economic_tier, parent_*_material)
stamping typed    → payload через persist-сервис (district_topology, system_city_size)
```

## Шаги

Порядок: P0 → перепроверка контракта S1 → runtime S1b → источники
дефолтов S1c; payload-миграция P1 → P1b → P2a → P3 → P4 → S1d → P2b → P5 → P6 остаётся отдельной последовательностью
этого плана. Parent-цепочка не входит в runtime-шаги.

| # | Цель | ТЗ | Файлы | Проверка | Done |
|---|---|---|---|---|---|
| P0 ✅ | Sync ТЗ: `dungeon` → `location_complex` (свой тип, `payload_kind:"settlement"`, `is_inhabited`, z — не семантика), одна scope-ось, payload = authored + type-stamped, убрать `hills` из NL-колонок | `tz_locations.md` §Payload per type / §Scope, `tz_cascade_context.md` §2 | `docs/tz_locations.md`, `docs/tz_cascade_context.md` | ревью ТЗ; `git diff --check` | Согласовано после уточнения linked-list контракта |
| S1 ✅ | Проверить контракт linked list; убрать из verifier зависимость от вложенности scope; generic разворачивание по above/below без порядка enum и ручного списка моделей; проверить usages перед удалением прежних helpers | tz_cascade §2 | `cascadeSpec.py`, `cascadeGraph.py`, `cascadeVerify.py`, `scopeLevel.py`, `tests/test_location_context_contract.py` | Новый параметр на иных POJO/порядке enum работает без правки walker; цикл, разрыв, неоднозначные концы/ветвление и несовместимый тип отвергаются | Выполнено 2026-10-06: 12 новых тестов; 81 tests OK; verifier не проверяет иерархию NL |
| S1b ✅ | Движок сам привязывает linked list к source-POJO и разворачивает в единый runtime-проход на параметр; убрать зависимость порядка обхода от rank и ручных списков, сохранить промежуточные домены и EmptyLink | tz_cascade §2, §4 | `contextResolver.py`, `runtimeChain.py`, `cascadeGraph.py`, `locationContext.py`, `locationScope.py`, `tests/test_context_extend.py` | Полная цепочка и пустые промежуточные объекты; приоритет declared links; None-наследование; однократный materialize и стабильный RNG; новый канал без правки resolver | Выполнено 2026-10-06; 91 tests OK; полный набор: 21 прежняя ошибка подтверждена сравнением runtime |
| S1c ✅ | Дефолты и шаблонные значения — на source-POJO; `CascadeDefault(model, field)` вместо default_value/default_registry, без таблицы дефолтов движка | tz_cascade §3–§4, целевой контракт POJO | `cascadeSpec.py`, `cascadeParams.py`, `locationCascadeDefaults.py`, `cascadeGraph.py`, `cascadeVerify.py`, `locationContext.py`, `locationScope.py`, `contextResolver.py`, contract/context tests | `root(world, default_sources=...)`; location-caller `root_context(world)`; обычные/computed поля проверяются по типу; None наследует; terminal default из POJO; median/fold сохраняют provenance, WARNING и RNG | Движок читает POJO и объявленные связи/операции; не назначает доменные значения сам; 103 tests OK |
| P1 ✅ | `LocationPayload` реестр `payload_kind`→model; `SettlementPayload` (type-поля skeleton + `is_inhabited`) + `DistrictPayload` (`district_topology`); поле `payload_kind` на `LocationTypeEntry` + seed реестра; `location_complex` с пятью рецептами | tz_locations §Payload per type | `locationPayload.py`, `payloadKind.py`, `settlementPayload.py`, `districtPayload.py`, `locationType/*`, skeleton, `tests/test_location_payload.py` | `compileall`; 75 + 103 focused tests OK; полный набор = baseline ошибок; schema не меняется | Выполнено 2026-10-06: реестр + 2 payload; shared field base без новых cascade-узлов; recipe is_inhabited объявлен на subtype |
| P1b ✅ | Удалить subtype `dungeon` у `settlement`; pipeline gate по payload_kind вместо строк типа/subtype; district сохраняет fine-геометрию | tz_locations §Payload per type, §Размер поселения | `worldLocationTypeRegistry.py`, `locationFootprintPolicy.py`, `settlementOutdoorTypes/Skip/Orchestrator.py`, callers occupancy/territory/layout/detailed bake/L0/render, contract/recipe/render tests | 168 focused tests OK; полный набор = baseline ошибок | Выполнено 2026-10-06; world-контракт передаётся caller'ами, legacy список удалён |
| P2a ✅ | Добавить nullable location_payload JSON-хранилище; сохранить legacy поля до миграции потребителей | tz_locations §Payload per type | 0001_initial.sql, db/models/namedLocation.py, tests/test_location_payload_schema.py | 131 focused tests OK; основная схема на temp DB; validate_schema; exact columns; repository roundtrip None/empty/nested JSON | Выполнено 2026-10-06; SQL/model синхронны, nullable JSON читается и пишется |
| P3 ✅ | Миграция групп (a–e): size/density, material/style, plotting, district refs/specializations, district topology → typed payload; wire-ключи сохранены | tz_locations §Payload per type | `bundleNamedLocation`, `locationPayloadAccess`, skeleton, locationScope, импорт/CRUD, footprint/index consumers, `settlementOutdoorExtract/Topology/SqlPersist`, wire/schema/extract tests | 267 focused tests OK; полный набор = baseline ошибок | Выполнено 2026-10-06; хранение в payload, typed reads, CRUD/RMW; временный source bridge до P4 и legacy read fallback до P2b |
| S1d ✅ | Заменить строки source-полей типизированными FieldRef в links и defaults | tz_cascade_context §2.1 | `cascadeSpec.py`, `cascadeGraph.py`, `cascadeVerify.py`, `cascadeParams.py`, POJO с links, `runtimeChain.py`, `contextResolver.py`, contract/context tests, статические fixtures, `pyrightconfig.cascade.json`, `scripts/check-cascade-types.cjs`, npm manifest/lock | Статический checker: корректные external/self/computed ссылки проходят, неизвестный атрибут и неверная сигнатура дают ошибку; runtime отвергает nested/computed selectors для links, сохраняет нормализованное равенство узлов; focused contract/context/payload tests; полный набор = baseline ошибок; `git diff --check` | Выполнено 2026-10-07: 123 focused OK; Pyright positive 0 ошибок + 4 ожидаемых negative; полный набор = baseline; legacy API удалён, self/default и provenance сохранены |
| P2b ✅ | После P3/P4/S1d удалить type-колонки и legacy read/update fallback | tz_locations §Payload per type, schema-policy | `0001_initial.sql`, `db/models/namedLocation.py`, `locationPayloadAccess.py`, `namedLocationService.py`, schema/consumer fixtures и debug-скрипты | Новая temp DB из основной схемы, `validate_schema`, exact columns и repository roundtrip; focused/full suite = baseline; `npm run typecheck:cascade`; compile debug-скриптов; dev БД не пересоздаётся | Выполнено 2026-10-07: SQL/model sync на temp DB; 303 + 12 focused OK; full = baseline; Pyright OK; payload — единственный type storage/read |
| P4 ✅ | Каскад-каналы: settlement-параметры на payload-класс (тег SETTLEMENT); удалить NL-узлы и рёбра к skeleton | tz_cascade_context §2 | cascadeParams, bundleNamedLocation, settlementPayload/Skeleton, locationScope, locationPayloadAccess, contract/runtime/schema tests | 115 focused tests OK; полный набор = baseline ошибок | Выполнено 2026-10-07: цепочки сокращены, source bridge удалён, generic channels/fold/default сохранены |
| P5 ✅ | Удалить overlay-таблицы, плоские type-поля Bundle и дублирующий CitySkeleton dataclass/shim; потребители используют SettlementSkeleton POJO | tz_locations §Payload per type (P5), tz_city_generation §3, tz_assembler_hierarchy §7.1 | skeleton, Bundle, новый `settlementSkeletonAccess.py`, `locationScope.py`, удалить `citySkeleton.py`, импорты/type hints consumers, fixtures, Pyright config | Нет прежних overlay/shim API; wire aliases и payload storage сохранены; generic cascade priority и resolved None; focused/full suite = baseline; `npm run typecheck:cascade`; compile debug scripts | Выполнено 2026-10-07: один POJO вместо зеркального dataclass; 257 + 5 focused OK; full = baseline; Pyright OK; старых overlay/shim API нет |
| P6 ✅ | Гейт живости: payload validator отвергает непустые specializations при false на импорте/CRUD/runtime; planner сохраняет authored районы, морфологию и required рецепта, отключает специализации и подбор без рецепта; lookup рецепта по фактическому типу/subtype | tz_locations §Payload per type, tz_city §1.2 | `settlementPayload.py`, `planner/districts.py`, `planner/placement.py`, payload/schema/planner tests | false + specializations отвергается без записи; complex/custom recipe и explicit районы работают при false; true разрешает специализации и fallback; `npm run typecheck:cascade`; full suite = baseline | Выполнено 2026-10-07: 82 focused OK (7 новых); Pyright OK; full 1567 tests = те же 21 ошибки + 1 expected failure, новых нет; живость — поле, не имя типа; economy/DAG вне шага |
| S2 ✅ | Level-agnostic NL-каналы материалов: `RepeatScope.EVERY_TAG`, единственное поле без links/смешивания с обычными каналами; `ordered_chain(param, scope_path=...)` разворачивает по scope-пути остальных linked lists, без enum-rank/ручного порядка; runtime сохраняет snapshots/EmptyLink/provenance; ECONOMIC_TIER без изменений | tz_cascade §2–§4 | `cascadeSpec.py`, `cascadeGraph.py`, `cascadeVerify.py`, `bundleNamedLocation.py`, `cascadeParams.py` (комментарий), `runtimeChain.py`, `contextResolver.py`, contract/context tests | новый параметр на иной оси с несовпадающим порядком enum; ошибочные mixed/links/duplicate/missing path отвергаются; inheritance/override/None/default/ambiguity/snapshots/provenance; `npm run typecheck:cascade`; full suite = baseline | Выполнено 2026-10-07: ×5 → 1 для материалов; 187 focused OK (7 новых); Pyright OK; full 1574 tests = baseline 21 ошибок + 1 expected failure; snapshots/EmptyLink/provenance и явные цепочки сохранены |

## Вынесено в отдельный план (`nl-parent-chain.md`, не создан)

Уточнение 2026-10-07: S3 ниже — вероятный техдолг, не обязательный следующий
шаг. Необходимость и caller-контракт проверить при реализации patch/rollback
и типизации DAG: [CASCADE-TD-1](../../docs/tz_cascade_technical_debt.md).
S4 про parenting/маски остаётся самостоятельной задачей.

- S3: scope-helpers → generic `ancestor_chain_context(world, leaf)` по
  `parent_location_uid`, link-объекты по `payload_kind`; per-уровневые
  фабрики могут быть пересмотрены. Зависит от P1; отдельный дизайн:
  parent-путь не подменяет linked list каскада, промежуточные домены
  и необходимость `EmptyLink` нельзя удалять по наличию/отсутствию NL.
- S4: parenting при placement, lazy synthetic NL из маски (emit от
  генератора, пишет persist), релакс правила «generators не пишут NL»,
  связка NL↔mask. Требует тегов `GEOGRAPHIC`/`TERRITORY` на `ScopeLevel`
  (сейчас оси нет) — тест «POI в unnamed forest» без них непроходим.

## Leftovers (не в этом плане)

- TEST-DB-1: удалить ручные копии DDL из трёх persist-тестовых модулей,
  создавать тестовые БД из основной SQL-схемы. Отдельная задача:
  [`docs/testing_technical_debt.md`](../../docs/testing_technical_debt.md).

- Входы/переходы — отдельный домен, единый шаблон `Transition`:
  [`docs/tz_location_transitions.md`](../../docs/tz_location_transitions.md).
  Parent-цепочка и payload их не трогают; `location_complex` связывается с
  хостом через `Transition(hatch|tunnel)`, не через `parent_location_uid`.

- `lazySettlementNode._SETTLEMENT_TYPES` (хардкод `city/town/village/…`) →
  `payload_kind`/`is_inhabited` — DAG-нода, только с мастером после gate.
- `planner/economic.py` — гейт по `is_inhabited`; не трогаем.
- `DungeonPayload`/wilderness-типы как отдельные `payload_kind` — не нужны:
  комплекс = `settlement`-payload; появятся только при реально другом
  контракте данных.

## Связи

- Предшественники: `cascade-migration-done.md` (M1–M10), `loc-t-3-settlement-volume-separation-done.md` (occupancy), `datamodel-locations-merge-done.md`.
- ТЗ: `docs/tz_locations.md` §NamedLocation/§Иерархия локаций, `docs/tz_cascade_context.md`, `docs/tz_city_generation.md` §3.
