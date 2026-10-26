# DONE: location-transitions — генератор, хранение, чтение и CRUD физических переходов

**Дата:** 2026-10-05; начало исполнения — 2026-10-06; завершение — 2026-10-07. **Статус:** DONE в согласованном generator/storage/read/CRUD scope. S0–A1 выполнены; после отчёта о проверках A1 мастер разрешил продолжение («Делай дальше»), итоговая приёмка зафиксирована. Отложенные темы §7 не реализованы; wallOpening сохраняется в конце плана (§9).
**SoT:** [tz_location_transitions.md](../../docs/tz_location_transitions.md), особенно §1–§5, §7, §8.1 и статусы §10.
**Правила:** [code-gates.mdc](../rules/code-gates.mdc), [layer-boundaries.mdc](../rules/layer-boundaries.mdc), [database-migrations.mdc](../rules/database-migrations.mdc), [deterministic-ids.mdc](../rules/deterministic-ids.mdc), [bulk-sql.mdc](../rules/bulk-sql.mdc).

## 1. Результат и границы текущей работы

Согласованный результат: структурный генератор и outdoor assembly возвращают единый Transition; наружные материальные проходы хранятся в SQL, интерьер одного здания — в pack; SQL-переходом с обеими сторонами управляют CRUD-операции application/persist. Сам переход не зависит от parent/child.

ТЗ описывает конечную архитектуру всего движка. Этот план поставляет её генеративный и storage-контракт в согласованном текущем scope. Завершение плана не означает завершение отложенных порталов, navigation, discovery или игровых действий.

### В текущем scope

- Закрытый TransitionType и N+1 transition_type_registry с behaves_as; одна классификация входов/проходов.
- Единый POJO, ровно две стороны, отдельная SQL-таблица transition_sides.
- Surface как явное семантическое пространство по умолчанию; level как конкретный уровень. Nullable host/owner при отсутствии NL.
- Генерация существующих наружных входов, дверей, проёмов, лестниц и прочих уже реализованных структурных проходов.
- SQL-схема, repository, application CRUD; outdoor extract/persist; interior pack wire/write/read.
- Settlement gates и калитки существующих барьеров; связь с графовым узлом только при фактической привязке.
- Чтение данных переходов из SQL/pack без решения о проходимости, маршруте или выборе сцены.
- Удаление заменённых location_passages/location_entry_points после переключения их действующих consumers.

### Вне текущего scope

- Создание нового портального producer, перенос portal_* из connection_nodes, destination wire и исполнение обеих реализаций портала. Их целевая архитектура сохраняется в §2 и ТЗ §3.4; текущая реализация назначения зависит от отложенных вопросов.
- Поиск ближайшего выхода в surface и сборка комбинации лестница/тоннель/прочие решения — SURFACE-T-1.
- Несколько назначений портала и выбор между ними, обратный проход в локацию, UID перенаправляемого портала, уточнение проверки is_accessible сторон — неприоритетные темы из ТЗ §10.
- Персональное discovery и player-state.
- Navigation/pathfinding/traversal, действие graph-барьера во время прохода, стоимость движения.
- WP-13 выбор якоря сцены и ранжирование входов.
- DAG wiring, LLM context, game actions breach/fall/portal и их pending_patches.
- Новый JSON bundle формат переходов, конвертация старых bundle и миграция портального импорта. Подключение нового реестра к существующему WorldSlice входит; новый import pipeline — нет.
- Lazy-комплексы, новый BridgeAssembler, новые producer-алгоритмы и manifest-индекс переходов по уровням.
- Автоматическая политика regenerate/reset игровых изменений. В текущем scope — явные CRUD-операции и повторная запись одинаковых генеративных данных; скрытый сброс состояния не добавляется.

После обсуждения прежние G1/G2 (портальная генерация), P4 (bundle handlers/remap), R2 (WP-13), traversal-часть R1 и D1–D3 (DAG/actions) исключены из обязательной последовательности. Ни один из них не является условием приёмки текущего генератора.

## 2. Принятая целевая архитектура

### 2.1 Домен

Transition — единая абстракция перехода с двумя сторонами source/destination. Физический проход имеет геометрию, назначение surface может быть семантическим. Объявление surface не требует от автора фиксированных координат. Генератор сохраняет уже известную геометрию результата; неизвестную не заменяет фиктивной клеткой.

Endpoint хранит пространство surface/level и optional явные ссылки. Surface не является NamedLocation, родителем или z=0. Ссылка на существующий host допустима, но не обязательна для внешнего пространства. Level требует level_uid. Координаты материализованного endpoint — глобальные, с учётом окончательного placement/rotation/z adjustment. Семантическое назначение surface без выбранного выхода остаётся отличимым от конкретной клетки.

Side хранит optional owner_location_uid, исходные is_discovered/is_accessible, overrides 0–100 и display_name. Эти поля сохраняются как данные. Генератор не решает персональное discovery и не определяет, какую сторону проверять при движении.

Main/service входы — builtin-типы; destination_side.owner_location_uid указывает входимую локацию. Это семантика входа, а не parent/child. C20 требует хотя бы один MAIN_ENTRANCE, а не любой тип с entry=true. Directional-флаг имеет смысл только для соответствующих builtin; дверь не маркируется is_bidirectional=False.

Portal остаётся одним builtin TransitionType.PORTAL с реализациями graph/coordinate. Graph учитывает граф и блокирующий его специальный барьер; coordinate буквально телепортирует без графа. Назначение может быть локацией. Конечная модель не ограничивается обязательным статическим endpoint destination или node UID. В текущей работе фиксируются enum/реестр и требования, но новая operational portal-модель/producer не реализуется до возврата к отложенным контрактам.

### 2.2 Слои и single writer

- dataModel/locations/transitions/: engine enum/metadata, реестр, Endpoint, Side, Origin, Transition и params поддержанных физических типов. Это SoT полей, defaults и wire policies.
- application/worldData/transitions/: typed identity wrapper, cross-reference validation, storage partition, CRUD service, объединённое чтение данных.
- generators/: чистая генерация Transition из собственного layout. Нет SQL, выбора сцены и игровых действий.
- db/models/: только SQL-проекции POJO, без второго набора поведения.
- ITransitionRepository / sqlite implementation: один writer transitions и двух sides; атомарный aggregate CRUD, bulk через app.db.bulkSql.
- SettlementOutdoorSqlPersist: caller transaction для NL/levels/graph nodes+edges/SQL transitions/sides; существующий graph writer не разделяется.
- pack/: тот же Transition POJO в building wire, действующие tmp/publish/recovery; read-only после публикации.

Pack eligibility определяется явным building layout scope и level принадлежностью. Родство сторон, equality owner и координатный overlap не доказывают принадлежность одному interior. Runtime/directional и любые будущие portal — SQL. Для калитки area NL не создаётся ради FK.

### 2.3 Публичные контракты

Точные аннотации оформляются в шаге соответствующего слоя; семантика фиксирована:

    validate_transitions(world_uid, transitions, *, levels, locations, nodes, registry) -> None
    partition_transitions(transitions, *, building_scopes, registry) -> TransitionPartition
    ITransitionRepository.get(uid) -> Transition | None
    ITransitionRepository.create(transition) -> Transition
    ITransitionRepository.update(uid, patch) -> Transition
    ITransitionRepository.delete(uid) -> bool
    ITransitionRepository.upsert_bulk(transitions) -> int
    ITransitionRepository.owned_by_destination(world_uid, location_uid) -> list[Transition]
    TransitionService.entries_of(world_uid, location_uid) -> list[Transition]
    ITransitionRepository.touching_level(world_uid, level_uid) -> list[Transition]
    ITransitionRepository.touching_node(world_uid, node_uid) -> list[Transition]
    TransitionReadService.for_level(world_uid, level_uid) -> list[Transition]

Create/update/delete — только SQL-ярус; обе sides изменяются атомарно. Update проверяет весь итоговый агрегат, а не только отдельный patch. Get/delete missing имеют явный результат; произвольное переназначение UID не является update. Pack не редактируется CRUD «на месте».

Repository выбирает по destination_side.owner_location_uid; application entries_of фильтрует builtin entry через behaves_as. Typed registry для hydration передаёт caller; repository не делает скрытых повторных чтений WorldSlice. Эта выборка не выбирает лучший вход и не вводит discovery policy. Read service возвращает данные, не вычисляет traversability.

### 2.4 Data flow

    Typed world registry + caller location/placement context
      → pure geometry/layout → final Transition + deterministic UID
      → extract → validate refs → SQL/pack partition
      → encode pack tmp
      → SQL transaction: NL → levels → graph nodes/edges → transitions → sides
      → SQL commit → publish pack → manifest
      → repository / pack reader → TransitionReadService

CRUD читает и изменяет SQL-агрегат через тот же validator. Generation/extract/partition без I/O. SQL запись последовательна в caller transaction; существующий C24 publish/recovery сохраняется. Новый parallel pipeline не создаётся.

## 3. Актуальная сверка и технические зависимости

Сверено 2026-10-05. В workspace идёт независимая работа над UID; перед своим шагом перечитать его файлы и diff, чужие изменения не переписывать.

- worldData/ids/ уже существует: entity_uid, runtime_uid и UidKind.TRANSITION доступны. Создание второго helper и общий перенос UID не входят в этот план.
- settlementOutdoorUids.py уже использует общий helper; level_uid имеет z_offset. Extract уже сохраняет level UID вместо переминтинга. Это не повторять.
- LocationPassage и LocationEntryPoint ещё используются; entry.py пишет False как маркер входа.
- Layout translation уже смещает passage xy; migration не должна добавить origin дважды. Для нового endpoint требуется также корректный z.
- ExtractedSettlement пока содержит entry_points; outdoor SQL writer пишет прежний entry repository.
- BuildingShellWire пока не хранит interior transitions. Фактический encode/decode путь — packBlobWire.py, worldPackWriter/Reader, а не новая самостоятельная библиотека codec.
- Portal-поля остаются в ConnectionNode и ConnectionNodeImportRow; существующий bundle использует их. Их удаление без согласованного нового portal-контракта сейчас ломало бы отдельную подсистему.
- Area UID в pack не равен существующему NamedLocation FK. Surface устраняет необходимость создавать area NL ради прохода.
- WP-13 reader пока принимает готовые anchor coordinates; его изменение не требуется для generator/storage приёмки.

Обычный UID материализованного перехода следует ТЗ §2 инв. 10 и общему helper. Временная локальная формула запрещена. Identity изменяемого портала отложена и не блокирует генерацию физических проходов. Изменение scope при новом факте оформляется явно в плане, не молча.

## 4. Правила исполнения

**Уточнение контракта мастером 2026-10-06:** стороны переименованы из a/b в
source/destination во всём новом Transition API. Endpoint поля — source/destination,
state поля — source_side/destination_side; SQL-колонки и UID identity prefixes —
source_*/destination_*, enum TransitionSideId — SOURCE/DESTINATION со значениями
source/destination. Состав шагов и семантика переходов прежние. Исправлены C2/C3/P1,
ТЗ и действующие consumers нового контракта. 59 тестов transition suites + DET-1
прошли на временной SQLite; рабочая БД и legacy producer API не менялись.

- План согласован; команда мастера «Делай» от 2026-10-06 разрешает исполнение. Выполнять шаги по порядку, соблюдая правило одного шага за заход.
- Один шаг за заход → проверка → короткий отчёт → ожидание «ок».
- DDL только 0001_initial.sql вместе с соответствующими dataclass models. Проверки на временной SQLite; рабочую БД не удалять автоматически.
- Backend агент не запускает; коммиты только по просьбе. DAG/engine nodes не менять.
- Перед сменой API/удалением — полный usage audit включая side-effect imports, re-exports, tests, fixtures и scripts. Изменённые действующие callers мигрируются вместе с контрактом.
- Все новые классы разделять по ответственности; bulk только через app.db.bulkSql.
- Каждый шаг ниже имеет явные зависимости, цель, ссылку на раздел SoT, файлы, контракт, проверку, Done и состояние callers. Шаги выполняются строго в порядке §5; переход к следующему возможен только после Done предыдущего. Зависимость означает готовый и проверенный результат, а не обещание реализовать его позднее.
- Подготовительные шаги добавляют новый путь рядом с действующим. Production переключается только в указанном шаге; временные проекции не становятся второй изменяемой моделью и удаляются в F1.
- Пути к коду ниже относительно backend/. Команды python запускать из backend/ через & '..\.venv\Scripts\python.exe'; новые test-модули создаются в своём шаге, сейчас они не существуют.
- Проверки не расширять после успешной целевой приёмки без новых изменений или сбоев.

## 5. Последовательность атомарных шагов

### S0 — синхронизировать ссылки и текущий scope документации

- **Вход / зависит от:** утверждённое ТЗ, решения мастера и правила репозитория; code prerequisites нет.

- **Цель:** убрать противоречащие текущему scope ссылки, не переоткрывая отложенные вопросы.
- **ТЗ:** transitions §1–§5, §8.1, §9–§11; locations passages/entry points; outdoor C20; storage DET-1.
- **Файлы:** связанные docs/tz_*.md только в разделах текущей миграции; этот план.
- **Контракт:** surface и отдельные sides приняты; parent не prerequisite; portal/surface algorithms deferred; discovery/WP-13/import compatibility вне generator. Устаревшие схемы помечены как прежние и ссылаются на Transition. Отложенные вопросы не превращаются в S0 approval gate.
- **Проверка:** rg по legacy table/registry названиям в соответствующих разделах docs; проверить ссылки и статусы. Никакой правки кода.
- **Done:** актуальные доменные документы и этот план не требуют от генератора решений по исключённым темам.
- **Состояние callers после шага:** код не меняется; актуальные docs задают scope следующих шагов.
- **Выполнено 2026-10-06:** синхронизированы transitions §11/К4, locations legacy схемы/реестр/world_uid, outdoor C20/O3/P9 и граница pack WP-13; перенос node portal_* явно отложен. Проверены legacy mentions, локальные ссылки и зависимости плана; backend не менялся.

### C1 — engine enum и единый реестр типов

- **Вход / зависит от:** S0 — их Done и проверки завершены.

- **Цель:** дать структуре один typed словарь проходов и входов.
- **ТЗ:** transitions §1, §3.1, §6 К1/К8; tz_json_validation.md POJO-first/N1-W.
- **Файлы:** новые dataModel/locations/transitions/transitionType.py, transitionTypeEntry.py, worldTransitionTypeRegistry.py; tests/test_transition_registry.py.
- **Контракт:** закрытый TransitionType с metadata entry/directional/vertical; обязательный behaves_as, RegistryKey, SCHEMA_ID/canonical_engine. Portal присутствует как абстракция; graph/coordinate не новые transition types. Реестр не исполняет portal algorithms.
- **Проверка:** python -m unittest tests.test_transition_registry: builtin metadata, main/service/hidden, custom behaves_as и ошибки неизвестного builtin.
- **Done:** один реестр поведения, без нового portal producer. Прежний PassageType удаляется только после generator caller migration.
- **Состояние callers после шага:** новый реестр доступен; старые generator enums/callers ещё действуют.
- **Выполнено 2026-10-06:** добавлены TransitionType (17 builtin) с единой metadata entry/directional/vertical и WorldTransitionTypeRegistry с RegistryKey, SCHEMA_ID, canonical_engine/defaults и обязательным behaves_as. Вертикаль сохраняет четыре значения ТЗ (нет/да/любая/вниз); custom display-типы читают поведение builtin, builtin-ключи не переназначаются. Portal — один тип. `python -m unittest tests.test_transition_registry`: 11 тестов, OK (metadata, custom main/service/hidden/portal, wire policies, неизвестный builtin, round-trip, legacy PassageType). Генераторы и их callers не менялись; следующий шаг — C2.

### C2 — единый контракт Transition, Endpoint, Side и params

- **Вход / зависит от:** C1 — их Done и проверки завершены.

- **Цель:** создать один POJO для generator, SQL projection и pack.
- **ТЗ:** transitions §1–§2, §3.2, §7; surface §10.11; levels access_mechanic.
- **Файлы:** новые dataModel/locations/transitions/transition.py, transitionEndpoint.py, transitionSide.py, transitionOrigin.py, transitionParams.py; общий mechanics enum по сверке существующего entryAccessType.py; tests/test_transition_contract.py.
- **Контракт:** ровно две sides; space surface(default)/level; owner/host optional; level_uid обязателен для level. Geometry конкретного endpoint — global; geometry либо полная, либо отсутствует, без частично заданных координат/нулевых заглушек. Surface declaration без выбранной geometry отличимо от конкретной клетки. Зафиксировать каноническое представление endpoint для C3: space, заданные refs и concrete geometry либо явный symbolic marker; порядок source/destination сохраняет семантику POJO. Overrides/defaults/flags из SoT, params для текущих физических producers. Новая portal destination/projection не придумывается; оперативная поддержка portal отложена.
- **Проверка:** python -m unittest tests.test_transition_contract: round-trip, nullable surface ownership, symbolic surface, materialized geometry, ranges, params, исходные side flags. Не тестировать actor discovery/traversal.
- **Done:** одна доменная модель поддержанных producers; surface не требует ручной точки или фиктивной NL.
- **Состояние callers после шага:** POJO доступен для schema/fixtures; producer API пока прежний.
- **Выполнено 2026-10-06:** добавлены Transition, Endpoint, Side, Origin и typed physical params (gate width_cells, staircase_type, strict empty params остальных физических типов). Aggregate содержит source/destination endpoints и source_side/destination_side; surface symbolic отличается от конкретных xyz, level требует level_uid и полную geometry. Endpoint.identity_keys фиксирует space, только заданные refs и concrete tuple либо marker symbolic без None, сохраняя порядок сторон для C3. Hidden destination discovery default=false с сохранением явных флагов; fall bidirectional=false, остальные physical types=true. Custom type проверяется с caller typed registry в validation context; operational portal явно отклоняется до PORTAL-T-1. EntryAccessType оказался enum подхода (auto/none/steps/porch); добавлен общий locations/enums/AccessMechanic, к нему подключён LevelDef.access_mechanic с прежним [] default. Проверки: tests.test_transition_contract + tests.test_transition_registry — 25 тестов OK; затронутые tests.test_room_def + tests.test_structure_template + tests.test_pojo_policies — 34 теста OK. Backend не запускался; generator producer API прежний. Следующий шаг — C3.

- **Исправление C2 2026-10-06 по замечанию мастера:** identity_keys больше не повторяет имена полей Endpoint. Проекция строится через model_dump(mode="json", exclude_none=True); concrete geometry теперь представлена собственными x/y/z полями POJO, а marker geometry=concrete|symbolic объявлен отдельным typed EndpointIdentityGeometry. Это уточняет описанное выше tuple-представление до начала C3; UID ещё не mintятся. Повторная проверка transition_contract + transition_registry: 25 тестов OK.

### C3 — identity wrapper материализованных переходов

- **Вход / зависит от:** C2 — их Done и проверки завершены. Дополнительно: существующий entity_uid/UidKind.TRANSITION после повторной сверки текущего diff.

- **Цель:** выдавать один UID конечному физическому проходу до SQL/pack projection.
- **ТЗ:** transitions §2 инв. 10; storage DET-1.
- **Файлы:** новый application/worldData/transitions/transitionIdentity.py; tests/test_transition_identity.py; существующие worldData/ids/ только импортируются.
- **Контракт:** typed transition_uid(world_uid, system_type, source, destination) использует entity_uid с UidKind.TRANSITION и каноническую identity C2; имена/порядок ключей фиксируются в wrapper и тестах до producer migration. В helper не передавать None: symbolic surface имеет явный marker, optional refs включаются только при наличии. Порядок source/destination соответствует POJO, не сортируется независимо от side semantics. Runtime create использует runtime_uid. Mint после конечного placement/rotation/z adjustment; projections не переминтируют. Identity перенаправляемого portal и поиск точки symbolic surface не входят.
- **Проверка:** python -m unittest tests.test_transition_identity tests.test_deterministic_ids: повтор входных данных, различение текущих concrete endpoints/types, SQL/pack same UID, отсутствие ad-hoc uuid5.
- **Done:** wrapper использует имеющийся helper; независимая UID миграция не повторена.
- **Состояние callers после шага:** identity wrapper готов до генерации новых Transition; existing UID callers не переписываются.
- **Выполнено 2026-10-06:** добавлена typed transition_uid(world_uid, system_type: TransitionTypeKey, source, destination). Wrapper передаёт type и source_/destination_ prefixed Endpoint.identity_keys в существующий entity_uid с UidKind.TRANSITION; имена полей Endpoint не дублируются, None не передаются, стороны не сортируются. Runtime creation использует существующий runtime_uid без новой формулы. Проверка tests.test_transition_identity + tests.test_deterministic_ids: 23 теста OK — фиксированные ключи helper, repeat, world/type/xyz/refs/space differences, symbolic surface, source/destination order, custom key, сохранение UID aggregate при dict/JSON projection, runtime uuid4 и DET-1 source gate. Реальная SQL/pack projection ещё не существует и проверяется в storage шагах; C3 фиксирует исходный UID и запрет remint при сериализации. Helper и действующие generator callers не менялись. Следующий шаг — P1.

### P1 — аддитивная SQL-схема и POJO↔row projection

- **Вход / зависит от:** C1, C2 — их Done и проверки завершены.

- **Цель:** добавить SQL-ярус текущих переходов и отдельные sides.
- **ТЗ:** transitions §2, §4, §8.1; schema-policy.
- **Файлы:** db/migrations/0001_initial.sql; новые db/models/transition.py, transitionSide.py и projection module; db/models/world.py; core/app.py registration; tests/test_transition_schema.py.
- **Контракт:** transitions + transition_sides, composite side PK, bool/origin/range checks, nullable surface refs и согласованное представление concrete/symbolic geometry; FKs и индексы level/node/destination_side.owner_location_uid; worlds.transition_type_registry. Две sides обеспечиваются aggregate writer. Legacy passage/entry schema пока сохраняется. Node portal_* не трогать.
- **Проверка:** временная SQLite из 0001, validate_schema и FK check; python -m unittest tests.test_transition_schema: projection round-trip, symbolic surface не получает фиктивную geometry.
- **Done:** новый schema/model контракт согласован; старые consumers ещё работоспособны.
- **Состояние callers после шага:** новые таблицы аддитивны; старые repositories/pipeline работают.
- **Выполнено 2026-10-06:** в 0001 добавлены transitions/transition_sides, composite side PK, checks origin/bools/JSON/ranges/space/полной integer geometry, nullable surface refs, FK world/levels/hosts/nodes/owners и индексы world/level/node/destination owner. World получил transition_type_registry; TransitionRow/TransitionSideRow зарегистрированы в validate_schema startup. SQL row-модели не вводят defaults поведения; pure transitionProjection выводит имена из POJO/dataclass fields, сохраняет UID, typed params и требует обе согласованные sides. Projection gate выявляет новое непроецируемое поле POJO. tests.test_transition_schema — 11 тестов OK на TemporaryDirectory SQLite: validate_schema + точное совпадение колонок, full/custom/symbolic round-trip через mapper и реальные SQL rows, empty JSON, FK/check/PK/cascade, invalid aggregates, legacy schema и portal node fields. Рабочая БД не менялась, backend не запускался, production writers прежние; гарантия наличия двух rows при записи — будущий aggregate writer P2. Следующий шаг — P3.

### P3 — подключить WorldSlice нового реестра

- **Вход / зависит от:** P1, C1 — их Done и проверки завершены.

- **Цель:** читать и валидировать единый реестр штатным POJO-first механизмом.
- **ТЗ:** transitions §3.1/§6 К8; tz_json_validation.md WorldSlice/REF-W.
- **Файлы:** application/jsonValidation/worldSlices.py, worldRow.py; tests/test_transition_registry_wire.py; facade только штатная registration, если требуется. По результатам целевых тестов 2026-10-06 добавлен общий resolve.py: исправления обязательности полей registry rows при partial world write, runtime row rejection и model-validator error routing.
- **Контракт:** один WorldSlice для transition_type_registry; import strict/runtime policy существующего resolve; behaves_as обязателен. Новый JSON bundle переходов и legacy payload conversion не добавляются; существующие node portal поля сохраняются.
- **Проверка:** python -m unittest tests.test_transition_registry_wire: canonical/custom registry и корректный path ошибок.
- **Done:** generator читает typed registry; новый import pipeline не создан.
- **Состояние callers после шага:** typed registry доступен validator/repository/generator; legacy import остаётся рабочим.
- **Выполнено 2026-10-06:** один registry_list WorldSlice с POJO SCHEMA_ID/canonical_defaults, без legacy wire adapter; добавлен worldRow.transition_types(world). Facade использует штатный merge без новых defaults/converter/import pipeline. Целевые проверки выявили существующие дефекты resolve: ctx.partial ошибочно применялся к отдельным строкам заменяемого registry, runtime StrictFieldError не приводил к warn+skip строки, model-validator ошибка уходила в unchecked field-wise construct и затем наружный ValidationError. Исправлено один раз в общем resolver: registry rows полные; invalid runtime row пропускается с warning; cross-field model errors сохраняют import path либо отклоняют runtime row. tests.test_transition_registry_wire — 11 тестов OK (canonical/custom, empty/absent, required behaves_as/UNKNOWN_ENUM paths, builtin remap rejection, runtime valid rows retained, legacy fields untouched). Затронутые world_row_t28/pojo_policies/resource_type_registry/crop_registry/livestock_registry/registry_key/relief_template_pojo — 77 тестов OK. Следующий шаг — V1.

### V1 — cross-reference validation и SQL/pack partition

- **Вход / зависит от:** C2, C3, P3 — их Done и проверки завершены.

- **Цель:** проверять данные перехода и выбирать его writer без parent/child требований.
- **ТЗ:** transitions §2, §3.3, §4, §5 gate; §10.8–§10.9.
- **Файлы:** новые application/worldData/transitions/transitionValidation.py, transitionStoragePolicy.py; tests/test_transition_storage_policy.py.
- **Контракт:** проверяются только заданные location/level/node refs и world, space/level/geometry consistency; node соответствует concrete endpoint. Building scope передаёт caller layout. Materialized interior → pack; outer/runtime/directional → SQL. Surface ownership optional, area NL не требуется. Ни pathfinding, ни проверка обеих accessible sides не реализуются.
- **Проверка:** python -m unittest tests.test_transition_storage_policy: interior, соседние здания, cross-branch concrete проход, surface без NL, runtime SQL, invalid refs; разные parent не блокируют проход.
- **Done:** pure validate/partition; никакого поиска wilderness выхода.
- **Состояние callers после шага:** validate/partition готовы для repository/extract, production pipeline прежний.
- **Выполнено 2026-10-06:** pure validate_transitions принимает typed registry и caller snapshots Mapping uid→LocationLevel/NamedLocation/ConnectionNode, перевалидирует полный POJO, проверяет world, заданные owner/host/level/node refs, host уровня, z в интервале уровня, concrete совпадение node xyz и вертикаль по builtin metadata. Parent и accessible/discovered/is_active/access_mechanic не используются для разрешения движения. BuildingTransitionScope содержит building_uid + явно заявленные level_uids/transition_uids из layout; partition после validate требует concrete level endpoints в одном scope, runtime/directional/outer сохраняет в SQL. Output TransitionPartition: sql_transitions и pack_by_building, порядок и исходные POJO сохранены; неоднозначный scope отклоняется. Точные сигнатуры §2.3 уточнены registry-аргументом: defaults поведения читаются из C1, не копируются. tests.test_transition_storage_policy — 13 тестов OK (door/staircase interior, no implicit owner/overlap scope, neighboring buildings/cross-branch hatch, nullable concrete/symbolic surface без area NL, runtime/fall/custom, bad refs/world/host/z/node, full aggregate revalidation, unchanged parents/state, ambiguous scope). Production callers прежние; следующий шаг — P2.

### P2 — repository полного агрегата

- **Вход / зависит от:** P1, P3, V1 — их Done и проверки завершены.

- **Цель:** обеспечить атомарные SQL CRUD и bulk без второго writer.
- **ТЗ:** transitions §2 инв. 1/6, §4, §8.1.
- **Файлы:** новые db/repositories/iTransitionRepository.py, sqlite/transitionRepository.py; tests/test_transition_repository.py.
- **Контракт:** get/create/update/delete/upsert_bulk и выборки §2.3; обе sides в одной transaction; bulk через executemany_rows. Hydration использует typed registry P3, переданный caller; validation применяет готовый V1. Repository выбирает destination_side.owner_location_uid, а entry-фильтр по behaves_as выполняет application P4. Update не delete-cascade replacement. Delete обрабатывает sides и существующие refs. Missing get/delete возвращают явный результат.
- **Проверка:** python -m unittest tests.test_transition_repository: CRUD, rollback, повтор одинаковых rows, FK, atomic delete, отсутствие half-aggregate.
- **Done:** один SQL writer Transition+sides; pack и game actions не затронуты.
- **Состояние callers после шага:** новый writer готов; production outdoor ещё пишет старые entries.
- **Выполнено 2026-10-06:** добавлены ITransitionRepository, явный TransitionRepositoryContext(world_uid, registry, levels, locations, nodes) и scoped SqliteTransitionRepository(db, context). Create/update/bulk канонизируют полный POJO и применяют V1; create строгий INSERT, update UPDATE + side ON CONFLICT (без REPLACE/delete), bulk только executemany_rows. Собственная transaction либо caller transaction с aggregate savepoint: ошибка любой стороны откатывает весь aggregate, даже если caller ловит её. Get/выборки читают root+обе sides одним SELECT snapshot; неполный aggregate отклоняется. Missing get=None/delete=False/update=KeyError; UID/world нельзя переназначить, bulk collision с другим world отклоняется. Destination owner query не фильтрует entry типы, level/node выборки объединяют обе стороны; delete cascade sides и уважает FK зависимых refs. tests.test_transition_repository — 15 тестов OK на временной SQLite: CRUD/patch/ranges/refs, второй side failure create/update/bulk, caller catch/rollback, shared bulk/idempotence, отсутствие REPLACE с restrictive dependent FK, stale snapshot FK rollback, delete/restrict, queries/custom hydration/half aggregate, world UID collision. Registry не читается скрыто из WorldSlice; production callers и pack не менялись. Следующий шаг — P4.

### P4 — application CRUD service и DI

- **Выполнено 2026-10-06:** TransitionService делегирует SQL create/read/update/delete и выборки уровня/узла P2 (полная validation V1 и атомарность остаются в едином repository write path). entries_of фильтрует destination-owner выборку по registry behaves_as.entry без фильтрации state flags. Container.transition_service(world, levels=..., locations=..., nodes=...) создаёт свежий world scope с реестром P3 и явными reference snapshots. `python -m unittest tests.test_transition_crud tests.test_transition_repository` — 20 тестов OK; `git diff --check` — OK. Следующий шаг — K1.

- **Вход / зависит от:** P2, P3, V1 — их Done и проверки завершены.

- **Цель:** дать callers явное управление сохранённым переходом через принятый контракт.
- **ТЗ:** transitions §8.1; слой application/persist.
- **Файлы:** новый application/worldData/transitions/transitionService.py; core/container.py; tests/test_transition_crud.py.
- **Контракт:** create/read/update/delete делегируют P2, validate полный aggregate через V1, registry через P3. entries_of получает выборку по destination_side.owner_location_uid из P2 и фильтрует builtin entry через registry. Только поддержанные текущим контрактом physical transitions; operational portal не объявляется готовым. Нет hidden regenerate/reset, HTTP route, персональных прав или game action semantics.
- **Проверка:** python -m unittest tests.test_transition_crud: create/read, valid/invalid patches, ranges/refs, rollback, delete, side state сохраняется как данные.
- **Done:** CRUD доступен application callers; вопросы игровой доступности не решены внутри service.
- **Состояние callers после шага:** новый CRUD/entry query доступен; generation cutover ещё не выполнен.

### K1 — interior-переходы: pack wire и codec

- **Выполнено 2026-10-06:** BuildingShellWire дополнен optional interior_transitions: BuildingInteriorTransitionsWire с обязательными format=building-interior-transitions-v1, world_uid, level_uids и transitions (единый Transition POJO, owner/node/host refs внутри него). Wire проверяет явный level scope, UID/world, исключает runtime/directional/exterior; полная проверка reference snapshots остаётся V1 перед packing. Payload/framed decode и legacy unframed rewrite принимают typed registry для custom behaves_as. parse_building_interior_transitions_blob возвращает целое здание; shell-only блок вызывает InteriorTransitionsRebuildRequired, существующий shell reader работает. `python -m unittest tests.test_transition_pack_wire tests.test_world_pack_wire tests.test_c24_district_packing tests.test_pack_render_read_facade` — 46 тестов OK; `git diff --check` — OK. Production cutover не выполнен. Следующий шаг — G2.

- **Вход / зависит от:** C2, V1 — их Done и проверки завершены.

- **Цель:** реально добавить внутренние переходы в building layout pack.
- **ТЗ:** transitions §4/§5 structure/§10.2; outdoor C20/C24; pack storage layout.
- **Файлы:** dataModel/worldPack/settlementStructureWire.py; application/worldData/pack/io/packBlobWire.py; tests/test_transition_pack_wire.py, test_world_pack_wire.py.
- **Контракт:** аддитивный interior wire с явным format marker несёт Transition и необходимые level/owner refs; один POJO и UID. Действующая shell-only ветка encode/decode остаётся рабочей до production cutover G3. Новый interior consumer различает legacy blob и явно требует rebuild, не silently empty transitions. Exterior/runtime/будущий portal не попадают в interior wire. Читать building целиком без нового manifest level index; оба пути тестируются до удаления legacy в F1.
- **Проверка:** python -m unittest tests.test_transition_pack_wire tests.test_world_pack_wire: round-trip fields/UID/refs, invalid/old blob, exterior exclusion.
- **Done:** interior codec не теряет поля; shell-only wire не выдаётся за полную interior поддержку.
- **Состояние callers после шага:** новый interior codec готов; production shell codec остаётся активным.

### G2 — outdoor extract и current storage projection

- **Выполнено 2026-10-06:** новый pure project_settlement_transitions принимает готовые Transition, typed registry, reference snapshots и BuildingTransitionScope; применяет V1, проверяет scope refs/UID и C20 MAIN_ENTRANCE по behaves_as + destination owner, делегирует partition V1 и создаёт K1 BuildingInteriorTransitionsWire. UID/level refs/state/None и 0 overrides сохраняются; parent/area не prerequisite. ExtractedSettlement и ExtractedTopology дополнены sql_transitions и pack_by_building с независимыми пустыми defaults; действующий extract остаётся legacy. `python -m unittest tests.test_settlement_outdoor_extract tests.test_transition_pack_wire tests.test_transition_storage_policy tests.test_c24_district_packing` — 58 тестов OK; `git diff --check` — OK. Дополнительный test_settlement_topology: 5 OK, 2 errors (Plot farm: structure 6f2d3a4b-5c6d-4e7f-9a8b-0c1d2e3f4a5b not found); те же errors воспроизведены с extraction-модулем из HEAD, вне изменений G2. Следующий шаг — G1.

- **Вход / зависит от:** K1, V1, C3, P3 — их Done и проверки завершены.

- **Цель:** подготовить чистое извлечение и SQL/pack projection до переключения structural producer.
- **ТЗ:** transitions §2 инв. 7/10, §4, §5 structure; outdoor C6/C20.
- **Файлы:** settlementOutdoor/settlementOutdoorExtract.py, ExtractedSettlement и ExtractedTopology; отдельный pure projection helper при необходимости; tests/test_settlement_outdoor_extract.py.
- **Контракт:** аддитивно ввести sql_transitions и pack_by_building в DTO обоих writers, включая sql_transitions у ExtractedTopology. Pure helper принимает явный list[Transition], reference snapshots, registry и building scopes, применяет V1 и строит K1 wire; тестовые данные — готовые C2 POJO, без зависимости от будущего StructureLayout.transitions. destination_side.owner_location_uid building; C20 считает behaves_as MAIN_ENTRANCE. None override наследует owner, 0 остаётся явным. Существующий level UID сохраняется. Surface host optional, area/parent не требуется. Действующий extract_settlement пока сохраняет прежние entry_points и shell wire; _role_for_passage/legacy ветка удаляются только после G3 в F1.
- **Проверка:** python -m unittest tests.test_settlement_outdoor_extract: pure Transition fixtures, ≥1 main, service/hidden не заменяют main, custom behaves_as main, refs/UID, parent unchanged, no area NL prerequisite; существующий extraction smoke продолжает проходить.
- **Done:** новая pure projection готова для typed producer и обоих writers; production extraction пока использует прежний путь.
- **Состояние callers после шага:** новый extract helper/DTO готовы; active extract ещё legacy, будущий producer не требуется для тестов.

### G1 — мигрировать structural generator API на Transition

- **Выполнено 2026-10-06:** StructureLayout.transitions — единственная изменяемая коллекция; build_transitions и builders entry/doorway/archway/staircase/corridor создают Transition с level/surface endpoints, явным z, owner и C3 identity. Main/service bidirectional берётся из POJO; наружный anchor известного входа сохраняется без SURFACE-T-1 поиска. EntryPoint/RoomConnection/RoomDef используют TransitionType при прежнем wire field passage_type. Rotation/xyz translation и cache rebind обновляют endpoints/owner и C3 UID, level UID сохраняется. Новые shared physicalTransition и legacyPassageProjection helpers; .passages — свежая tuple-проекция, passage_uid=transition_uid, без отдельного списка/mint. Internal cache/assembler/debug rotation consumers мигрированы. Audit временных outward callers: settlementOutdoorExtract.extract_settlement, api/routes/debug.py и debugStructureRotations.py (render/payload); удалить/перевести в F1. 260 affected tests OK, compileall structure и git diff --check OK. Дополнительные 37 проверок после делегирования side defaults POJO — OK. WallOpening создаёт прежнюю геометрию; вопрос мастера о дополнительных Transition вынесен отдельно, текущая runtime-only breach семантика не изменена. Следующий шаг — K2.

- **Вход / зависит от:** G2, C2, C3, P3 — их Done и проверки завершены.

- **Цель:** заменить LocationPassage единым POJO во всех действующих structure producers.
- **ТЗ:** transitions §2, §3.1, §5 structure, §6 К1/К2/К6; building §3.6 и связи/лестницы.
- **Файлы:** generators/structure/passages/{builder,entry,doorway,archway,staircaseTunnelOrchestrator}.py; staircase/{builder,surfaceCorridor}.py; structureGeneratorService.py, structureOrientation.py, layoutTranslate.py, layoutEntry.py; dataModel/locations/structure/room/entryPoint.py и enum consumers; settlementAssembler/layoutCells.py и buildingCache.py; areaAssembler/structureAreaAssembler.py; затронутые structure tests.
- **Контракт:** StructureLayout.transitions — единственная изменяемая коллекция проходов. Все внутренние constructors/cache/orientation/translation consumers мигрируются вместе с API. Final physical Transition после geometry transforms получает C3 UID. Entry outer side обозначает surface; producer сохраняет известную geometry, неизвестную оставляет декларацией без нового поиска. Main/service default bidirectional true; concrete endpoints корректно translate/rotate, включая z. На внешней границе старого active extract до G3 допускается только вычисляемая read-only .passages projection из transitions: без отдельного mutable списка и нового mint, passage_uid = transition_uid. Полный usage audit фиксирует callers этой временной проекции и её удаление F1.
- **Проверка:** python -m unittest tests.test_entry_point tests.test_entry_layout tests.test_entry_point_runtime tests.test_structure_orientation tests.test_room_connection; добавить nonzero placement/dz и повтор geometry→UID проверки.
- **Done:** structural producers и внутренние callers используют Transition; старый production extract продолжает работать через явную временную проекцию. SURFACE-T-1 algorithm не запускается.
- **Состояние callers после шага:** канонический generator API новый; внешние legacy callers работают через read-only projection до G3.

### K2 — publish/recovery и pack reader

- **Выполнено 2026-10-06:** writer.encode_settlement_structure_tmp и reader.read_settlement_structure принимают optional typed registry; read_building_interior_transitions возвращает целое здание с явным rebuild для legacy shell, transitions_for_level фильтрует прочитанные данные без manifest index. K1 codec-reader делегирует общий building lookup settlementStructureIndex. Явный integration caller проводит G1 layout → G2 projection → encode tmp → transaction (NL/levels/graph перед P2 transitions) → publish → fresh reader; проверены custom types, UID/state/refs, SQL failure rollback без публикации, append preservation и retry сохранившегося tmp без генерации/SQL. Новый факт: os.replace удаляет tmp до save_manifest; publish теперь допускает retry с сохранённым committed TmpRef при совпадении hash/size опубликованного blob, отказывает при mismatch и не добавляет кадры повторно. TmpRef удерживается caller до успешного manifest publish; автоматическое сохранение этого receipt между процессами не добавлено. `python -m unittest tests.test_transition_pack_roundtrip tests.test_transition_pack_wire tests.test_c24_district_packing tests.test_world_pack_wire tests.test_pack_render_read_facade` — 52 теста OK; git diff --check OK. Production extraction/persist пока legacy, переключение в G3.

- **Вход / зависит от:** K1, G2, G1, P2 — их Done и проверки завершены.

- **Цель:** провести interior через действующий C24 write/read cycle.
- **ТЗ:** transitions §4/§8 pack reader; outdoor C24; pack commit/recovery.
- **Файлы:** pack/io/worldPackWriter.py, worldPackReader.py, settlementStructureTmp.py; pack/read/settlementStructureIndex.py; tests/test_transition_pack_roundtrip.py, test_c24_district_packing.py; production packing job меняется только при необходимости аддитивного read/helper API, переключение — G3.
- **Контракт:** готовые G1 layout → pure G2 helper → K1 encode tmp → P2 SQL transaction → publish → manifest → fresh reader проверяются явным integration caller. SQL nodes/edges сохраняются до transitions/sides в caller transaction. Production materialize ещё использует старую extraction ветку. Building read целиком, filter by level только над данными. SQL failure не публикует blob; interrupted publish использует текущий recovery. Не требовать будущий G3 для выполнения этого шага.
- **Проверка:** python -m unittest tests.test_transition_pack_roundtrip tests.test_c24_district_packing: temp DB+pack, fresh reader, UID agreement и recovery.
- **Done:** новый interior write/read/recovery путь проверен end-to-end и готов для production cutover G3; прежний pipeline работоспособен.
- **Состояние callers после шага:** новый путь проверен integration caller; production cutover выполняется только G3.

### G3 — outdoor SQL writer на transitions

- **Вход / зависит от:** G1, G2, K2, P2, P4, V1 — их Done и проверки завершены.

- **Цель:** одновременно переключить production extraction и SQL/pack callers на уже готовые contracts.
- **ТЗ:** transitions §4/§5 structure/§8.1; outdoor C20/C24 persist cycle.
- **Файлы:** settlementOutdoor/settlementOutdoorExtract.py, settlementOutdoorSqlPersist.py, settlementOutdoorPackingJob.py, settlementOutdoorTopologyJob.py; core/container.py; db/bulkSql.py и sqlite namedLocationRepository/locationLevelRepository/connectionNodeRepository; tests/test_transition_outdoor_persist.py, test_settlement_outdoor_extract.py, test_transition_pack_roundtrip.py; scripts/debug_settlement_persist.py только затронутый smoke-контракт.
- **Уточнение G3 2026-10-06:** новые FK обнаружили DELETE-семантику INSERT OR REPLACE в bulk-записи NL/levels/nodes. Эти caller-записи переведены на общий bulkSql.upsert_rows (ON CONFLICT DO UPDATE), чтобы повторная generation сохраняла references и обе sides существующих Transition. Состав шагов и regenerate scope не меняются.
- **Контракт:** active extract_settlement передаёт G1 transitions в готовый G2 helper с reference snapshots/registry/scopes; materialize_district публикует готовый K1/K2 wire. Одна caller transaction: NL→levels→ConnectionPersistService.persist_graph(nodes, edges, [])→P2 transitions/sides; graph writer не разделять и обратный node→transition FK не добавлять. persist_topology уже принимает sql_transitions DTO G2 и пишет их после graph, пока список пуст до G4. Legacy entry write выключить без dual-write. Публичный счётчик MaterializeResult.entry_points/run_queue временно сохранить по имени, но вычислять количество entry-type SQL Transition через registry, без обращения к legacy DTO entry_points. Repeat identical generation без дубликатов; никакого replace-all/reset/delete при изменившейся generation.
- **Проверка:** python -m unittest tests.test_transition_outdoor_persist tests.test_settlement_outdoor_extract tests.test_transition_pack_roundtrip tests.test_c24_district_packing: реальный materialize caller, свежий pack reader, counters, пустые topology transitions, rollback/FK/recovery. In-process debug_settlement_persist после проверки CLI на временной DB.
- **Done:** production generation→extract→SQL commit→pack publish→read работает новым путём; legacy entry write выключен, backend не запускался.
- **Состояние callers после шага:** оба production writer яруса используют новые данные; topology writer заранее готов к G4.
- **Выполнено 2026-10-06:** active extract сохраняет producer UID, валидирует transitions/reference context через G2 и заполняет interior_transitions; materialize передаёт world registry в extract/codec, считает entry-type SQL Transition. Persist пишет NL→levels→graph→transitions/sides одной транзакцией, без legacy entry dual-write. При повторе existing UID не перезаписывается; CRUD-состояние сохраняется, изменённая geometry добавляет новый UID без удаления прежнего. FK-sensitive bulk обновляет существующие NL/levels/nodes через ON CONFLICT DO UPDATE. 80 тестов (outdoor/extract/pack/C24/repository/CRUD/schema) прошли. Обновлённый in-process debug_settlement_persist с реальным генератором/stdlib, временными DB/pack, повторной записью и свежим reader прошёл; backend не запускался. Следующий шаг — G4.

### G4 — settlement gates C23

- **Вход / зависит от:** G3, G2, C3 — их Done и проверки завершены.

- **Цель:** представить существующие городские ворота как entry Transition и graph node.
- **ТЗ:** transitions §3.1/§5 settlement_gate/§6 К7; outdoor C23; connections city graph.
- **Файлы:** generators/assemblers/settlementAssembler/planner/topologyPlan.py и typed output; все callers plan_slots_and_city_graph, включая settlementOutdoorTopology.py; settlementOutdoorExtract.py extract_topology; tests/test_settlement_topology.py, test_transition_settlement_gates.py.
- **Контракт:** typed topology output несёт nodes/edges/transitions; все tuple-unpacking callers меняются вместе с producer API. extract_topology заполняет готовый sql_transitions DTO G2, persist_topology G3 уже умеет его писать. City settlement_gate node остаётся; main/service Transition с destination_side.owner_location_uid settlement и surface сторонами, C3 UID после final geometry. Territory host optional, parent не prerequisite. Endpoint node_uid ссылается на уже сохраняемый graph node; обратный FK/portal-множественность не добавлять.
- **Проверка:** python -m unittest tests.test_transition_settlement_gates tests.test_settlement_topology: node/geometry refs, entry types, no parent requirement, unchanged road graph.
- **Done:** current topology writer G3 сохраняет gate aggregate; нового wilderness выхода не ищет.
- **Состояние callers после шага:** topology producer, caller, extract и persist согласованы в этом шаге.
- **Выполнено 2026-10-06:** SettlementTopologyPlan(slots, nodes, edges, transitions) заменил tuple API, все callers обновлены. Каждый существующий CITY settlement_gate создаёт MAIN_ENTRANCE с symbolic source surface и concrete destination на node ворот (host/owner=settlement), UID C3 после final geometry. Роли service у нынешнего producer нет; SERVICE_ENTRANCE проверен как допустимый aggregate, автоматическое назначение не добавлено. extract_topology применяет G2/V1 и передаёт SQL transitions в готовый G3 writer. Road graph сохранён; отсутствие settlement_gate nodes не создаёт фиктивных переходов. 39 тестов gates/topology/outdoor persist/C24 прошли, включая production plan_one, nonzero placement/z, обе sides/FK, repeat/skip, сохранение CRUD и rollback; compileall прошёл. Topology fixtures используют явный stdlib catalog, независимо от cwd. Следующий шаг — G5.

### G5 — калитки барьеров area

**Уточнение по просьбе мастера после G4 (2026-10-06):** в topologyPlan и physicalTransition словари side owner заменены прямым созданием TransitionSide. Default hidden_entrance в Transition POJO применяется также к typed side с незаданным is_discovered; явно заданные True/False сохраняются. 37 затронутых contract/structure/gates/entry runtime/outdoor persist тестов прошли. G5 этим исправлением не начат.

**Дополнительное исправление C2 по просьбе мастера «без raw wire» (2026-10-06):** Transition defaults/type_params validation перенесены из before/raw-dict обработки в after-валидатор typed aggregate. Pydantic разбирает type_params как union строгих POJO, после чего проверяется соответствие builtin. Hidden/fall defaults используют typed поля и fields_set, сохраняя явные значения. Файлы: dataModel/locations/transitions/transition.py, tests/test_transition_contract.py. 75 тестов contract/pack wire/repository/CRUD/structure/gates/outdoor/pack roundtrip/registry wire и diff-check прошли; проверено прямое typed создание и JSON roundtrip. Scope и порядок G5–A1 не меняются.

- **Вход / зависит от:** G3, G1, G2 — их Done и проверки завершены.

- **Цель:** создать gate у фактической калитки и сохранить yard_path привязку.
- **ТЗ:** transitions §3.1 gate/§5 perimeter_barrier/§6 К7; assembler hierarchy perimeter; city perimeter_barrier.
- **Файлы:** generators/assemblers/areaAssembler/structureAreaAssembler.py, planner/{areaBarriers,areaPaths,resolveThreshold}.py, areaLayout.py; settlementOutdoorExtract.py area transition collector; tests/test_structure_area_assembler.py, test_transition_area_gates.py.
- **Контракт:** AreaLayout.transitions и его collector подключаются в одном шаге: готовая G2 partition и G3 persist получают gates, а не только новое DTO поле. Только существующий barrier/threshold producer; gate соединяет фактические surface стороны, C3 UID после final placement, host refs optional. Нет барьера — нет gate; дверь/yard_path независимы. Area NL не создаётся. Алгоритм лестницы/тоннеля для достижения surface не добавлять.
- **Проверка:** python -m unittest tests.test_transition_area_gates tests.test_structure_area_assembler: fenced/unfenced, без здания, путь через существующую калитку, no area NL, optional refs.
- **Done:** текущие gates присутствуют в output/persist, искусственных gate на открытом участке нет.
- **Состояние callers после шага:** area producer и collector согласованы; gates достигают действующего writer.
- **Уточнение G5 2026-10-06:** прежний producer дважды выбирал вероятность барьера (до threshold и при emit), что позволяло GATE threshold без созданного барьера. Threshold теперь опирается на фактически созданные cells и координаты opening, решение о probability принимается один раз. После существующего approach z-clamp opening согласуется с final threshold/graph elevation. Новый алгоритм выхода или подъёма не добавлен.
- **Выполнено 2026-10-06:** AreaLayout.transitions хранит typed Transition. Фактическая одиночная клетка opening создаёт GATE с GateTransitionParams(width_cells=1) между соседними surface клетками снаружи/внутри барьера; без host/owner и обязательной area NL, C3 UID после final placement/z. Collector сохраняет area transitions также в buildingless ветке через G2→G3 SQL writer. Door и yard_path независимы; threshold/yard_path проходит через существующее opening. 78 тестов area gates/assembler/outdoor persist/extract/C24/settlement gates/C21 прошли: cardinal geometry, probability/open/missing barrier, buildingless SQL/две sides/pack roundtrip/no area NL, repeat CRUD preservation и z-clamp. Следующий шаг — R1.

### R1 — объединённое чтение данных SQL/pack

- **Вход / зависит от:** K2, G3, G4, G5, P4 — их Done и проверки завершены.

- **Цель:** вернуть единый Transition набор без сцены и movement semantics.
- **ТЗ:** transitions §4 и §8 storage readers; исключения §9.
- **Файлы:** новый application/worldData/transitions/transitionReadService.py; core/container.py; tests/test_transition_read.py.
- **Контракт:** for_level и entries_of объединяют соответствующий building pack и SQL, dedupe UID. State/overrides возвращаются как данные; символическая surface не становится выдуманным navigation edge. Нет traversal.py, barrier evaluation, nearest entry/exit, discovery filtering или WP-13 wiring.
- **Проверка:** python -m unittest tests.test_transition_read: SQL outer, pack interior, runtime SQL rows, refs/custom type и отсутствие дублирования.
- **Done:** consumers могут читать текущие данные без legacy entry repository; будущие алгоритмы не реализованы.
- **Состояние callers после шага:** новый объединённый reader готов; удаление legacy стало допустимым.
- **Выполнено 2026-10-06:** TransitionReadService и Container.transition_read_service создают fresh world-scoped reader с SQL сервисом/registry/reference context и явными BuildingTransitionPackBinding(settlement_uid, building_uid, level_uids, owner_location_uids). for_level и entries_of объединяют SQL + соответствующие interior blocks, применяют V1 к pack refs/world и dedupe UID. При collision SQL aggregate имеет приоритет, включая случай CRUD-изменения типа/owner/endpoints, после которого старый pack больше не должен попадать в выборку. State/overrides и symbolic surface возвращаются без discovery/traversal фильтрации; parent-chain routing не вводится. Empty bindings дают SQL-only чтение; shell-only/missing/foreign/invalid-ref pack дают явную ошибку, не пустой interior. 18 тестов read/CRUD/pack roundtrip прошли (реальные временные SQL/pack и DI), включая custom entry type, runtime, state/0, duplicate bindings, edited collisions, no parent и ошибки pack. Следующий шаг — F1.

### F1 — удалить только заменённые legacy passages/entries

- **Вход / зависит от:** R1, G1, G2, G3, G4, G5, K2, P3 — их Done и проверки завершены.

- **Цель:** завершить переключение текущего generator/storage API.
- **ТЗ:** transitions §4/§6 К1/К5; schema-policy.
- **Файлы:** 0001_initial.sql; убрать locationPassage.py/locationEntryPoint.py и entry repositories; core/app.py/container.py; obsolete EntryRole/PassageType только по полному usage audit; tests/scripts/fixtures текущего contract.
- **Контракт:** после полного caller audit удалить location_passages/location_entry_points, прежние writer/readers, _role_for_passage, legacy extraction ветку и вычисляемую .passages projection G1; sync schema/models. Удалить заменённую shell compatibility ветку только после K2/G3/R1 checks, не ломая актуальный shell-only сценарий вне interior consumer. ConnectionNode.portal_* и import wire сохраняются: миграция отложена. Enum aliases/re-export удалить после callers. Новый converter старых JSON/pack не создаётся; schema проверяется на recreate temp DB/новом pack.
- **Проверка:** rg по legacy class/table/enum symbols во всём backend и fixtures; python -m compileall -q app; временная validate_schema/FK; affected import checks.
- **Done:** текущий scope не использует старые passages/entries; сохранённый legacy portal явно указан как вне scope, не называется завершённой полной унификацией.
- **Состояние callers после шага:** все действующие callers свободны от удалённых passages/entries; legacy portal сохраняется.
- **Выполнено 2026-10-06:** удалены LocationPassage/LocationEntryPoint, entry repository/DI/schema registration, таблицы/индексы location_passages/location_entry_points, неиспользуемые EntryRole/PassageType/exports и passage_type_registry (World + initial schema). Удалены legacy extract helpers/entry_uid, пустой DTO entry_points и computed .passages/legacyPassageProjection. Debug API/rotation payload и debug_structure/debug_ladder используют transitions с общей POJO-сериализацией и typed разбором на внешней границе. Счётчик MaterializeResult.entry_points сохранён по согласованному контракту G3. Caller audit по старым class/table/enum/property/wire symbols чистый; старые SQL имена остались только в негативных schema assertions. 116 tests schema/registry/wire/read/outdoor/pack/structure/orientation/gates/C24 прошли, временная validate_schema/FK, in-process persist smoke и import core.app/debug/registry exports прошли. Shell-only остаётся допустимым для shell consumer и даёт rebuild-required для interior reader; прежнего passage adapter там больше нет. ConnectionNode.portal_* и portal import не изменены. Backend не запускался, рабочая БД не изменялась. Следующий шаг — A1.

### A1 — приёмка и закрытие текущего scope

- **Вход / зависит от:** F1, R1, P4 — их Done и проверки завершены.

- **Цель:** доказать generation→SQL/pack→read/CRUD и завершить этот план.
- **ТЗ:** transitions §1–§5/§8.1/§9–§10; outdoor C6/C20/C23/C24; текущий scope §1 плана.
- **Файлы:** tests/test_transition_materialization.py; соответствующие in-process smoke scripts; только status/links этого плана.
- **Контракт:** nonzero placement и несколько z, main/service door, interior staircase, gates, symbolic surface без NL, concrete cross-branch fixture и runtime SQL CRUD fixture. Без портальных traversal, action success/fail, actor discovery, WP-13 ranking и surface exit search.
- **Проверка:** python -m unittest tests.test_transition_materialization и затронутые suites после F1: geometry/UID, обе sides, C20, refs/FK, interior pack/outer SQL, atomic CRUD, publish recovery, unchanged parent, no area NL requirement. Повтор одинаковой generation; не тестировать ещё не принятую reset policy.
- **Done:** мастер принял текущий generator/storage/CRUD scope. Приёмка перечисляет оставшиеся долги. План можно пометить DONE и переименовать в location-transitions-done.md без ожидания исключённых DAG/actions/portal алгоритмов; в H1 и отчёте явно указать завершённый scope.
- **Состояние callers после шага:** scope принят; отложенные вопросы остаются открытыми.
- **Приёмка A1 2026-10-07:** после отчёта о 210 прошедших тестах и готовности текущего scope к приёмке мастер дал команду «Делай дальше». Текущий scope принят, план закрыт и переименован в location-transitions-done.md; ссылки обновлены. Следующих обязательных шагов в этом плане нет. Отложенные темы §7 и wallOpening §9 требуют отдельного возврата к работе.
- **Проверки A1 2026-10-06:** добавлен tests/test_transition_materialization.py с полным in-process циклом StructureAreaAssembler → extract → SQL/pack publish → fresh read. Проверены nonzero xy, z=7/13, main/service entrances, interior staircase, area gate, детерминированные UID и повторная генерация, сохранение CRUD-состояния при повторном persist, обе стороны, FK и неизменный parent. Отдельный runtime сценарий проверяет symbolic surface и concrete cross-branch переходы с create/read/update/delete. Общий прогон transition suites и затронутых geometry/outdoor/topology/packing suites: 210 тестов, OK. In-process debug_settlement_persist smoke, compileall и diff-check прошли; аудит заменённых legacy usages чист, кроме отрицательных schema assertions. Техническая часть A1 завершена; Done/переименование плана остаются после приёмки мастером. Отложенные темы §7 и wallOpening §9 сохраняются.

## 6. Порядок и критерий готовности

Порядок: S0 → C1 → C2 → C3 → P1 → P3 → V1 → P2 → P4 → K1 → G2 → G1 → K2 → G3 → G4 → G5 → R1 → F1 → A1.

### 6.1 Явные точки переключения

- P1–P4 готовят schema/registry/validation/CRUD; production writer пока прежний.
- K1 и G2 готовят wire и чистую projection до изменения structural output. G1 переводит внутренние generator callers и оставляет только вычисляемую внешнюю совместимость.
- K2 проверяет новый SQL/pack cycle без зависимости от production cutover.
- G3 переключает active extraction, SQL persist и pack materialize одновременно. Нельзя включать новый SQL writer с неподготовленным wire или удалять entry_points до обновления counters.
- G4 меняет topology output вместе со всеми callers; его writer/DTO уже готовы после G2/G3. G5 меняет area output вместе с collector и использует готовый persist.
- R1 завершает новый read path. Только после него F1 удаляет legacy модели, adapters и таблицы. A1 проверяет окончательный pipeline после удаления.

Каждый шаг имеет готовые входы в предшествующих шагах; обратных зависимостей нет. Упоминание будущего шага в состоянии callers обозначает границу переключения, а не требование к текущей проверке.

Это 19 атомарных шагов с проверяемым результатом. S0 — документация, не новый опрос по отложенным темам. Согласование и команда на исполнение получены 2026-10-06. Техническую сверку UID/helper выполнять локально, не повторять уже сделанные изменения другого плана.

Не возвращать portal-first operational migration из исходного каркаса T1 в обязательную последовательность: мастер отложил определяющие её контракты. Сначала контракт общего Transition; будущая миграция обеих portal реализаций использует его после отдельного согласования.

## 7. Отложенные темы и возврат к ним

- [PORTAL-T-1](../../docs/tz_generator_technical_debt.md#portal-t-1--задание-назначения-портала-в-генераторе-и-прибытие-в-локацию): generator portal destination и прибытие в локацию, P3.
- [SURFACE-T-1](../../docs/tz_generator_technical_debt.md#surface-t-1--поиск-выхода-в-surface-среди-комбинаций-генератора): ближайший допустимый выход и комбинации генератора, P3.
- Transitions §10.5–§10.7: несколько portal назначений, обратный проход, identity изменяемого portal, сторона доступности — не приоритет.
- Discovery, WP-13, navigation и DAG/actions: отдельные domain планы; они потребители данных, не обязательная приёмка генератора.
- Portal SQL projection/node-field cleanup и новый bundle transition import/remap: отдельная миграция после согласования portal destination/storage. Не стирать существующие данные и не придумывать legacy converter.
- Pack level index — при необходимости после измерения; lazy complex storage — вместе с complex ТЗ.
- Regenerate reconciliation — отдельный контракт поверх CRUD; текущий producer не решает судьбу пользовательских изменений.

Возврат к этим темам только по отдельной просьбе мастера. Их статус не становится Done при закрытии текущего плана. До возврата не создавать внутренние заглушки алгоритмов, mandatory arrival markers или фиктивные координаты.

## 8. Риски текущей работы

- Двойное xy смещение, несмещённый z, UID до конечного placement или второй mint в extract.
- Surface интерпретируется как нулевая клетка/фиктивная NL либо требует координат от автора.
- C20 засчитывает service/hidden вместо MAIN_ENTRANCE; door False остаётся маркером входа.
- Validator требует parent/child или materialize area NL ради host FK.
- Aggregate write неатомарен, update использует delete/replace, cascade теряет связанные данные.
- Pack теряет interior поля при extra-ignore или recovery публикует несогласованный результат.
- Legacy portal поля удаляются вместе с passages без готовой миграции его producer/import.
- Read/CRUD добавляют traversal, discovery, WP-13 или implicit regenerate policy вне scope.

Новый факт отражается явной правкой плана с сообщением мастеру. Этот документ не даёт разрешения менять код заодно с уточнением архитектуры.

## 9. Отложенное дополнение: wallOpening → Transition

**Решение мастера 2026-10-06:** пока оставить wallOpening на потом и продолжить основной план. Это дополнение не блокирует K2–A1 и не считается реализованным при закрытии текущего scope.

При возврате уточнить, какие окна/бойницы/иллюминаторы/вентиляционные отверстия образуют Transition, их builtin/behaves_as тип и начальное состояние. Действующее ТЗ §3.1/§5 Ad-hoc предусматривает breach после успешного runtime-действия; заранее создаваемые переходы требуют отдельного согласования. До этого wallOpening сохраняет существующую геометрию, без автоматического создания Transition.
