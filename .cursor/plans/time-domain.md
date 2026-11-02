# Time — owning architectural proposal

Статус: RESEARCH / USER DECISIONS IN PROGRESS. Не CODE-READY, не пользовательская приёмка всего proposal. Только документы; production POJO, DDL, DAG nodes, publication и cutover запрещены текущим scope.

## Базовая политика runtime/worldEdit

SoT: [tz_runtime_world_edit_policy.md](../../docs/tz_runtime_world_edit_policy.md), [tz_json_validation.md](../../docs/tz_json_validation.md). Все применяемые настройки задаются owning POJO: поля, типы, defaults, missing/null/empty policies, ограничения и model invariants — единственный источник истины. Общий `jsonValidation.resolve` использует эти контракты; Time не вводит собственный policy engine. `facade`/`worldRow` и consumers — тонкие bindings без повторных defaults.

Проверено по `dataModel/annotationPolicy.py`: `DefaultWhenMissing` применяет schema default только при отсутствии, supplied invalid остаётся unresolved. Отсутствие настройки, explicit null, пустой объект и invalid value нельзя объединять `value or default`. Patch сначала сохраняет missing/null semantics и выполняет merge, затем валидирует полное состояние. Runtime unresolved идёт в существующий diagnostic/log sink как WarningError и блокирует зависимую операцию без ложного успеха; worldEdit получает ту же диагностику. Exact Time consumer binding общего result/log API ещё OPEN.

Import preview — существующий `validate_only=true` того же pipeline без writes, version allocation и изменяющих задач; отдельный Time validate endpoint не проектировать. Обычный apply повторно проверяет актуальный source. Штатный default календаря/часов — не error fallback и не runtime публикация. Порядок CRUD/принятия изменений по-прежнему у DAG/Snapshot.

## 1. Зафиксированные решения пользователя (2026-11-02)

- Owner текущего времени — мир. Пока игрок не ходит, время стоит. Ход служит причинным основанием продвижения, но соответствие одного хода длительности ещё требует exact contract.
- Мир и персонаж уже архитектурно разделены. Не пересматривать это решение. Течение времени отражается на возрасте/истории через соответствующих owners; Time не применяет gameplay effects.
- Нужен запас на большие диапазоны и будущие перемотки.
- Принято представление: signed int64 секунды + наносекундный остаток 0..999999999. Точный wire/storage contract и overflow validation ещё требуют детализации.
- Пользователь разрешил заменить старое правило «1 тик = 1 час» более подходящей моделью настраиваемого мира. Число часов в сутках — настройка мира; новая формулировка единиц и миграция legacy per-tick consumers ещё OPEN. Старое ТЗ остаётся историческим baseline, не доказательством выполненного cutover.
- Каждое игровое действие тратит положительное время; действия различаются интервалами. Actions/actionCore — отдельный домен: Time не классифицирует действия, не определяет их стоимость и не содержит action rules. DAG получает длительность от соответствующего владельца и передаёт Time типизированные временные факты. Exact actionCore foreign contract OPEN. Zero interval остаётся допустимым математическим/техническим случаем (например, Physics zero path), но не бесплатным игровым действием.
- История версий календаря сохраняется через существующий механизм версионирования; отдельный calendar version store не вводится. Exact World/Snapshot reference binding ещё OPEN.
- Интерфейс обязан отображать точное время МИРА и отдельно номер хода. «Ход N» не заменяет время даже при отсутствии пользовательского календаря. Time не владеет интерфейсом, номером хода или его продвижением. Согласованную передачу этих данных потребителю организует DAG по public contracts владельцев. Настройки возвращения/отображения времени требуют exact consumer contract; они не изменяют authoritative clock и не допускают потери его точности. Выбор календаря и размещение presentation settings ещё OPEN.
- Если пользовательский календарь мира не задан, мир использует обычный календарь (решение пользователя). Это штатное world-owned значение по умолчанию, а не отсутствие календарной проекции или показ elapsed seconds вместо даты. Time получает разрешённое определение календаря от владельца мира, не выбирает fallback самостоятельно. Обычный календарь — григорианский; при отсутствии стартовой даты/времени используются текущие дата и время (принято пользователем). Некорректный заданный календарь нельзя молча заменять обычным.
- Календари, стартовая дата и календарные эпохи принадлежат миру. Календари любого вида задаются настройками и описанием, расширяемость N+1 по правилу движка. Длительность суток — настройка мира.
- Если количество часов в сутках отсутствует, применяется 24. Default объявляется один раз в world-owned settings POJO через общую field policy. Пользователь требует POJO-first для всех применяемых настроек, не только этого поля. Time получает разрешённые typed settings, не читает raw World.calendar и не подставляет локально 24.
- Основной путь: пользователь задаёт настройки календаря; точные преобразования выполняются по валидированным настройкам. Отдельный маршрут через LLM — только архитектурная возможность вне текущего scope. Его результат также обязан проходить ту же валидацию настроек; он не обходит доменные проверки и не является частью Time. Проектирование и реализация этого маршрута сейчас не требуются.
- Поддержать и заранее заданные эпохи, и эпохи, добавляемые во время игры вследствие событий (например, новое летоисчисление после падения короля). Time не наблюдает события и не объявляет эпохи. DAG организует явную операцию владельца мира; Time получает принятые факты для преобразований.
- Все межоперационные/междоменные выборы и причинный порядок — DAG. Time owns временную семантику, validation и чистые преобразования. Snapshot сохраняет commit/restore/branch. Physics получает time facts и не пишет clock.

### Уточнение единиц, старта и исторического отображения

- Принято: час = 60 минут, минута = 60 секунд; эти величины не настраиваются. Мир настраивает только количество часов в сутках (default 24). Физическая секунда не меняется при смене календаря.
- Принято: исторические события по умолчанию отображаются по версии календаря, действовавшей в соответствующий момент. Не пересчитывать автоматически исторические подписи по текущим settings; источником версии служит существующее версионирование, не новый Time store.
- Предлагаемый initialization binding: внешний caller захватывает wall-clock один раз и передаёт typed факт в подготовку world settings. Для стандартного календаря owning POJO объявляет policy отсутствующего start_date; общий resolver/binding применяет её по переданному факту, без скрытого now() в default_factory. Явно заданный старт сохраняется. Повтор принятия той же операции использует тот же captured input; read/restore не вычисляет старт заново. Это детализация для freeze, не готовый production port.
- Принято пользователем: текущие начальные дата/время берутся по Гринвичу +0 (UTC+00:00), независимо от timezone пользователя или сервера. Текущие реальные дата/время используются только для начального значения, не означают дальнейшего течения simulation clock без действий игрока. Принято пользователем: для пользовательского календаря стартовая дата обязательна и задаётся явно. Её отсутствие — ошибка валидации owning POJO через общий resolver, без подстановки текущей григорианской даты. Invalid date не исправляется молча.

## 2. Решения, ещё НЕ принятые

- Representation принята в §1; wire encoding больших integers, допустимые operation bounds и exact errors остаются OPEN.
- Замена hourly tick baseline разрешена в §1. Exact новая семантика legacy current_tick и per-tick rates, migration mapping требуют отдельной спецификации; нельзя молча переинтерпретировать сохранённые значения.
- Несколько календарей N+1 и сохранение истории версий приняты. Точная привязка эпохи к моменту, revision binding и API выбора отображения — предложения детализации, а не принятые public POJO.
- No-calendar означает отсутствие пользовательской настройки: используется обычный календарь (§1). Григорианский default и текущий старт приняты; OPEN: exact initialization/capture contract; отсутствие даты и elapsed-only UI больше не предлагаются.
- Поддержка календаря любого вида не доказывается перечнем обычных месяцев/сезонов. Требуется исследовать выразительность настроек, роль описания и поведение при недостаточных правилах. Нельзя молча вычислять точную дату из неоднозначного prose.

## 3. Первичный source / implementation ledger

Исследован HEAD 4a5f29b7 и рабочая копия. Чужое незавершённое изменение `.cursor/plans/gen-dag-node-dependency.md` §18 прочитано и сохранено: world-wide exclusivity изменяющих bake, эквивалентные запросы join, неэквивалентные BakeConflict без очереди. Оно не разрешает автоматически применять тот же lifecycle к Time.

Поиск owning-плана по filenames и упоминаниям Time/time-domain в `.cursor/plans` отдельного плана не обнаружил; создан этот файл. Отрицательные результаты поиска ограничены просмотренными путями/терминами.

| Источник | Факт / текущее evidence | Статус |
|---|---|---|
| `docs/project_data_storage_tz.md:910` | 1 мировой тик = час; бой в секундах | Исторический baseline; пользователь разрешил replacement (§1), exact migration OPEN, выполнение не заявлено |
| Тот же файл :427–432 | round_seconds 4..12, default 6; копируется в combat_state | Требование; runtime conversion не установлена |
| Тот же файл :1032 против :2008–2010 | World owner против session owner; no-calendar связывает current_tick с turn_id | Owner уточнён пользователем; время и номер хода раздельны, «Ход N» не замена времени (§1); legacy migration OPEN |
| Тот же файл :1960–2026 | start_date, months/seasons/epochs/time_of_day; формула часа не включает start_date | Сохранённое ТЗ; требуется точная offset-семантика |
| `backend/app/db/models/world.py` | current_tick:int=0; calendar и combat_settings — dict | Legacy storage, не typed Time API |
| `backend/app/db/migrations/0001_initial.sql` | worlds.current_tick INTEGER DEFAULT 0; calendar TEXT; combat round_seconds INTEGER | Legacy DDL, дробного clock здесь не установлено |
| `backend/app/db/repositories/iWorldRepository.py` и `sqlite/worldRepository.py` | increment_tick(world_uid:str)->int; UPDATE + отдельный commit + SELECT | Прямой writer вне предполагаемого acceptance boundary; application caller поиском не найден, не доказано отсутствие всех callers |
| `sqlite/base.py` | save всех полей, insert/upsert; commit вне ambient transaction | Косвенные writers, нельзя ограничиться increment_tick |
| `application/worldData/registries/worldService.py` | update защищает только world_uid/created_at; create/import/upsert используют World; _save пишет repository | Generic mutation surface требует отдельного migration gate |
| `application/worldBundle/entity/sections.py` | WorldSectionHandler export asdict(World), import через WorldService | Clock/calendar входят в generic bundle surface |
| `application/worldBundle/deriveWorldUid.py` | current_tick исключён из fingerprint определения мира, calendar не исключён | Это не защита записи clock; import/copy требует отдельного gate |
| `application/patch/contracts/sectionHandler.py` | typed validate/apply/encode/decode; apply не commit | Reuse seam, не готовый Time handler |
| `application/worldSnapshot/contracts/applyPort.py` | IWorldSnapshotApply.apply(PatchSet)->SnapshotApplyResult | Единственный proposed runtime publication route; готовность Time acceptance не доказана |
| `dataModel/worldSnapshot/identity/publication.py`, `refs.py` | WorldPublicationRef содержит head/active timeline; WorldSnapshotRef содержит world/timeline/snapshot IDs | Реальные foreign types; не следует смешивать identity с elapsed time |
| Поиск calendar/round_seconds/conversions в backend Python | Calendar/combat duration converter не установлен; UTC envelope parsing относится к wall-clock metadata | Ограниченное negative evidence, не глобальное доказательство |
| `docs/tz_lazy_simulation.md` | elapsed batches, last_tick, frozen far, потребности/ресурсы/weather | Требования сохранены; scheduling вне Time; runtime выполнение не доказано |
| `docs/tz_world_snapshot.md`, `docs/tz_patch_system.md`, owning World plan | active timeline, immutable history, atomic acceptance, restore/branch | Внешний owning contract; legacy blob-текст не заменяет target pack+overlay |
| `physics-spatial-dynamics.md` последние P2/F решения | Time external; capture=start для resume; DAG выбирает public pipeline; numerical substeps принадлежат Physics | Сохранить, exact foreign specialization OPEN |
| `gen-dag-node-dependency.md` | invocation/CALL/RETURN не тождественны родству; public typed operations; актуальные read/preparation requirements | Concrete Time caller bindings OPEN; новые рёбра этим планом не вводятся |

## 4. Внешние наработки календарей

- Fantasy Calendar: настраиваемые месяцы, вставные дни/месяцы вне недельного цикла — https://helpdocs.fantasy-calendar.com/topic/months/ и https://helpdocs.fantasy-calendar.com/topic/leap_days/ . Предметный reference, не доказательство произвольности и достаточного численного диапазона.
- ICU: Calendar abstraction и реализации незападных календарей — https://unicode-org.github.io/icu/userguide/datetime/calendar/ . Reference разделения преобразований, не выбранная dependency.
- Noda Time: разделение instant/duration/calendar полезно, но custom calendars не поддерживаются — https://staging.nodatime.org/3.3.x/userguide/design . Не предлагать как готовый пользовательский calendar engine.

## 5. Проверка согласованности (2026-11-02)

Проверены весь текущий Time-план, правила `layer-boundaries`, `folder-composition`, `contract-creation`, `pojo-world-row-wire`, `dataModel-no-hardcode`, `documentation-layout` и существующие identity/publication POJO. Это document review, не runtime proof.

| Находка | Вердикт / действие |
|---|---|
| N+1 уже принят, но несколько отображений перечислены как целиком OPEN | Исправлен статус в §2; exact API остаётся OPEN |
| Нет этапов и зависимостей | Добавлен §8; нельзя трактовать source ledger как implementation sequence |
| Нет карты классов, файлов, фабрик и imports | Добавлен proposal §6; новые production файлы не создаются |
| Нет exact POJO / public API | §7 определяет размещение и проверки, но не выдаёт названия за законченные контракты; BLOCKER до отдельной детализации |
| Calendar ownership можно ошибочно перенести в Time | World owns definitions/CRUD; Time owns pure projection. Зависимости разложены без импорта application из dataModel |
| `SeasonKey` содержит только winter/spring/summer/autumn | Нельзя использовать его как закрытый enum произвольных сезонов N+1. Foreign World calendar keys и Climate mapping OPEN; существующий enum не менять этим планом |
| Историческое «сессия/current_tick=turn_id» конфликтует с решениями | World owner, раздельные время/номер хода и обычный календарь при отсутствии настройки приняты; точная миграция legacy поля и initialization binding ещё OPEN |
| «Любой календарь» не обеспечен схемой старого ТЗ | Expressiveness gate: неодинаковые месяцы, вставные дни, собственные сутки и эпохи; недостаточные настройки возвращают unresolved, а не выдуманную дату |

## 6. Предлагаемое размещение архитектуры, классов и POJO

Все пути ниже — **проект**, не существующие реализации и не разрешение на код. Архитектура и execution map пока хранятся только в этом owning-плане. Будущее доменное ТЗ `docs/tz_time.md` — отдельное предложение после приёмки; сейчас его не создавать. Не создавать документы в папках production.

Корень путей — `backend/app/`. `dataModel/time`, `dataModel/world`, `application/time` на момент проверки отсутствуют. World calendar paths ниже требуют согласования владельца World; отсутствие папки не даёт Time ownership календаря.

| Путь | Классы / ответственность | Imports |
|---|---|---|
| `dataModel/time/values/point.py` | TimePoint: шкала world/timeline + точная координата; не календарная дата | identity/uid; собственные scalar types |
| `dataModel/time/values/duration.py` | TimeDuration: неотрицательная длительность; единицы/границы после representation gate | Только validation primitives |
| `dataModel/time/values/interval.py` | TimeInterval: start/end одной шкалы, end>=start | point, duration |
| `dataModel/time/reads/capture.py` | TimeCapture/HistoricalTimeCapture: согласованные clock facts + provenance; не набор независимых latest reads | values, существующие WorldPublicationRef/WorldSnapshotRef |
| `dataModel/time/reads/request.py` | CurrentTimeRead, HistoricalTimeRead — отдельные requests | EntityUid, WorldSnapshotRef |
| `dataModel/time/changes/advance.py` | PrepareAdvance, TimeAdvanceProposal: candidate, не accepted clock | values, reads/capture, EntityUid |
| `dataModel/time/results/errors.py` | Конкретные refusal POJO; exact закрытый перечень ещё OPEN | Только dataModel; не exceptions из application |
| `dataModel/world/calendar/definition.py` | WorldCalendarDefinition: настройки/описание, не Time entity | World keys/rules; не application/time |
| `dataModel/world/calendar/epoch.py` | WorldCalendarEpoch: world-owned именованная эпоха, anchor | calendar keys, TimePoint; semantics anchor OPEN |
| `dataModel/world/calendar/registry.py` | WorldCalendarRegistry: N+1 definitions | definition; existing RegistryKey mechanism |
| `dataModel/world/calendar/projection.py` | CalendarProjectionRequest/CalendarProjection: перенос определений и результата без повторной схемы календаря в Time | definition, epoch, TimePoint; exact result OPEN |
| `dataModel/world/settings/timeSettings.py` | WorldTimeSettings: world-owned часы в сутках; proposed hours_per_day — DefaultWhenMissing positive strict integer, default 24. Единственный источник поля; calendar definitions не дублируют настройку | annotationPolicy, constrained primitives; точный SCHEMA_ID/wire binding OPEN |
| `application/time/pure/arithmetic.py` | TimeArithmetic: add/difference/comparison, без clock read | dataModel/time/values |
| `application/time/pure/conversions.py` | TimeConversions: seconds/hours; стоимость и число раундов вычисляет actionCore/Combat, не Time | dataModel/time; никаких Combat imports |
| `application/time/pure/calendarProjection.py` | CalendarProjector: чистый алгоритм по валидированному world definition | dataModel/world/calendar + time/values |
| `application/time/reads/reader.py` | TimeReader: отдельные current/historical reads согласованного источника | capture/request, внедрённый read port |
| `application/time/reads/sourcePort.py` | ITimeReadSource: coherent source seam, без собственного store/publication | exact request/capture; source consistency contract OPEN |
| `application/time/changes/prepareAdvance.py` | TimeAdvancePreparer: фиксированный pipeline validation → proposal, без чужого CRUD/commit | time POJO, pure arithmetic |
| `application/time/integration/snapshotHandler.py` | TimeSectionHandler: Time validation/append в чужом commit scope (§10 TimeAdvanceSection) | DomainSectionHandler + будущий concrete Time section OPEN |
| `application/time/composition/factory.py` | make_time_reader(source), make_time_advance_preparer(); явный DI, не service locator/dispatcher | Только указанные классы/ports |

Число непосредственных файлов (с планируемым `__init__.py`): time/values 4; reads POJO 3; changes POJO 2; results 2; world/calendar 5; world/settings 2; application/time/pure 4; reads 3; changes 2; integration 2; composition 2. Новые промежуточные package folders — по одному `__init__.py`. Ни одна предложенная папка не превышает 5; при уточнении errors/rules/section schemas пересчитать до добавления, не наполнять эти папки без проверки.

Направление: `DAG → public application operations → dataModel`; `Physics → dataModel/time` только через подготовленный Input. `dataModel/world/calendar → dataModel/time/values` допустимо для anchors; обратного импорта из time/values в World calendar нет. Calendar projection request размещён у World именно для предотвращения цикла. TimeCapture не содержит calendar settings/ref: DAG получает их отдельным World read на той же публикации. Это исключает обратный импорт Time → World из capture. `Snapshot → TimeSectionHandler` через binding, handler не вызывает Snapshot.apply. World CRUD вызывает чистую validation явно через согласованный binding, без Time-вызова World CRUD. DAG composition POJO живут в `dataModel/engine/nodes/<group>/`, переиспользуют вложенные domain POJO и не дублируют поля.

DB rows остаются в `db/models/`, DDL в `db/migrations/0001_initial.sql`; это storage representation, не публичный POJO. Новая persistence схема сейчас не выбрана. Mapping/normalization не дублируются в DAG, routes и repositories. Runtime authoritative time должен читаться из принятого Snapshot состояния, а не независимо из stale World row.

### POJO settings integration gate

Evidence: `WorldClimateScalars` показывает SCHEMA_ID/field policies/POJO wire helpers; `WorldEnvironmentSettings` — world-owned typed nested settings; `application/jsonValidation/worldSlices.py` — существующий WorldSlice registry. В поиске calendar/hours_per_day в dataModel и этом registry готовый settings contract не найден; legacy dict не признан достаточным. Это references механизма, не разрешение копировать legacy Any, error fallbacks или закрытый набор сезонов.

До реализации World owner должен принять exact WorldSlice binding calendar/settings, policy каждого поля и migration старого `calendar.hours_per_day` в единственный source. Single JSON slice использует штатный registry mapping; если выбраны несколько SQL-колонок — wire keys выводятся из POJO и проверяются startup column assertion. Не заводить второй список wire keys в Time/facade/DAG. SCHEMA_ID, RegistryKey для N+1 refs и typed diagnostics используют существующие механизмы.

Default 24 применяется при missing hours_per_day; 0/negative/неверный тип не заменяются 24. Предложенный strict positive integer ещё требует freeze exact schema; null не трактуется как missing без явной принятой policy. Обычный calendar default также определяется owning POJO/canonical factory, не literals в проекторе. Только для стандартного григорианского календаря отсутствующий start_date заполняется из однократно захваченных текущих даты/времени UTC+00:00 на initialization boundary; пользовательский календарь требует явной стартовой даты; pure POJO/Time не вызывают now(). Настройки presentation, если вводятся, тоже должны иметь свой owning POJO, а не kwargs/dict в Time.

Каскад настроек автоматически не вводится. Если World owner объявит наследование, использовать существующие Cascade/FieldRef/extend и проверки по `cascade-pojo.mdc`; локальные or-цепочки запрещены. Проверки перед будущим cutover: missing→24, invalid→unresolved, patch omission сохраняет предыдущее значение, import/runtime используют одинаковые ограничения, preview без writes, source revision согласована с capture. Это будущие proofs, не выполненные тесты.

## 7. Результат проверки POJO и applicability

Production Time POJO по поиску class Time/Duration/Calendar/Epoch в `dataModel`/`ids` не установлены. Проверены reuse candidates: `EntityUid`, `WorldPublicationRef`, `WorldSnapshotRef`; calendar/combat storage остаётся нетипизированным legacy. Это ограниченное evidence, не доказательство отсутствия всех возможных aliases.

Карта §6 уточнена предложенными схемами §10. Для закрытия API freeze по каждому контракту проверяются: поля/strict constraints; конкретные success/error POJO и полностью перечисленные unions; caller requirement; publication/source/timeline consistency; idempotency; legacy disposition. Все foreign types OPEN сохраняются blockers, не заменяются Any/object/dict/BaseModel. Свободное описание — текст, но calendar IDs/keys/rule kinds не свободные строки. Структурная validation находится у POJO, чистая временная семантика — Time; IO/current revision checks — application read/acceptance boundary.

| Сущность | Применимость операций |
|---|---|
| TimePoint/Duration/Interval | Создание/validation immutable values, conversions; persistence CRUD не применим. Update/delete methods ради симметрии запрещены |
| World clock | Read; prepare positive advance. Create только при initial world/timeline binding, exact owner seam OPEN. Arbitrary update/delete clock запрещены; rollback только Snapshot restore/branch |
| TimeCapture | Read immutable coherent facts; нет update/delete или самостоятельной публикации |
| TimeAdvanceProposal | Prepare immutable candidate; не accepted state. Нет Time accept/commit. Retry acceptance/operation status у Snapshot, не дополнительный Time operation store |
| Calendar/epoch | World-owned public CRUD/preparation. Нужны отдельные create/read/update/delete applicability и retention rules от World; Time CRUD этих сущностей запрещён |
| Timeline / snapshot | Snapshot ownership; Time не создаёт и не удаляет ветки |

## 8. Последовательность и зависимости

Это атомарные **документальные** этапы; каждый завершается проверяемым дополнением owning-плана. Никакой шаг не разрешает implementation.

| Этап | Prerequisites | Результат / gate |
|---|---|---|
| T0 Baseline audit | Исходные источники и working-tree evidence | Закрыть ledger всех consumers/writers; отдельно факты, конфликты, negative evidence |
| T1 Representation decision | T0; ответы пользователя | Принятые units/range/precision, hourly baseline, turn separation и no-calendar policy |
| T2 World calendar contract proposal | T0; принятые N+1/ownership | Exact World foreign keys/definition/revision/projection, эпохи, update semantics; без чужих правок |
| T3 Time values и pure API | T1; T2 только для calendar projection части | Exact point/duration/interval/conversions/errors и file/import map |
| T4 Coherent reads и preparation | T3; Snapshot publication/ref contracts | Capture, current/historical reads, proposal/base expectations; запрет mixed-source facts |
| T5 Acceptance/handoff | T4; совместный Snapshot contract proposal | Atomic time+effects, operation identity, unknown outcome/retry/concurrent advances/cancellation/restore/branch |
| T6 Сквозное review | T2–T5 | Все walkthrough исходного запроса, exact public API inventory, закрытые unions, counts/import cycles, legacy gates |
| T7 Пользовательская приёмка | T6; явный список оставшихся OPEN | Архитектурный verdict. Даже PASS не разрешает код автоматически |

T0 и уточнение внешних seam можно исследовать независимо. После T1 arithmetic часть T3 независима от calendar T2; чтение Snapshot contracts и consumer requirements Physics/GEN можно вести параллельно документально. Полный Physics/GEN/Snapshot DONE не prerequisites дизайна. Недостающий конкретный контракт блокирует только соответствующий freeze/integration, не всё исследование. Production integration позднее потребует готовности нужного acceptance seam и явного разрешения на implementation.

Обязательный T6 набор: zero/positive, бой меньше часа, несколько действий внутри часа, Physics resume capture=start, смена календаря/no-calendar, concurrent advances, retry unknown commit, restore/branch, inactive timeline, cancellation. Для каждого нужны input/base → chosen DAG operations → proposal → acceptance/refusal → повторное чтение. Документальные walkthrough приведены в §12; runtime proofs ещё не выполнены.

## 9. Остаток исследования / stop boundary

Исходный checklist: полный ledger требований/consumers и writers; exact public Input/Output/Error и CRUD applicability; files/classes/factories/import directions; coherent capture и Snapshot acceptance; retries/concurrency/unknown outcome/cancellation; restore/branch/inactive timeline; walkthrough; этапы и внешние contracts. Core proposal и walkthrough добавлены в §§10–12; актуальные незакрытые пункты и verdict — §13.

До этого verdict: PARTIAL RESEARCH, NOT READY FOR ARCHITECTURAL ACCEPTANCE. Отсутствие реализации не означает отмену старого ТЗ. Незакрытые foreign types отмечать OPEN, не заменять Any/object/dict. Review PASS не заменяет приёмку пользователя. Меняется только этот owning-план; внешние документы и graph edges — лишь предложения с evidence.

## 10. Explicit proposed Time POJO (актуальная детализация карты §6)

Все контракты этого раздела — proposal для приёмки, не production declarations. POJO strict/frozen/extra-forbid, вложенные коллекции immutable tuples, bool не принимается вместо int. Structural validation использует существующий механизм проекта; expected temporal refusals перечислены ниже. Не добавлять generic payload или универсальный request dispatcher.

Scalar notation: I64 = strict integer [-2^63,2^63−1]; U63 = strict integer [0,2^63−1]; Nano = strict integer [0,999999999]; PositiveCount = strict integer >=1. EntityUid и RevisionHex — существующие типы, не новые aliases строк. Единицы секунды/минуты/часа фиксированы: 1/60/3600 секунд. В wire большие integers требуют согласованного codec; до этого запрет транзита через JS Number. Математика выполняется с проверкой конечного результата; overflow — явный refusal, не wrap/clamp.

Пути таблицы относительно `backend/app/dataModel/time/`.

| Файл / POJO | Exact proposed fields / invariant |
|---|---|
| `values/point.py`: TimePoint | world_uid:EntityUid; timeline_id:EntityUid; seconds:I64; nanoseconds:Nano. Координата от origin simulation шкалы, не Unix timestamp. Для отрицательных координат нормализованная пара: −0.5s = seconds −1, nanos 500000000 |
| `values/duration.py`: TimeDuration | seconds:U63; nanoseconds:Nano. Zero допустим как математическое значение. Максимальная разность крайних TimePoint может не поместиться — explicit overflow |
| `values/interval.py`: TimeInterval | start:TimePoint; end:TimePoint. Одинаковые world/timeline, end>=start; интервал [start,end), zero пустой. Длительность выводится, не хранится вторым независимо изменяемым полем |
| `reads/capture.py`: TimeCapture | publication:WorldPublicationRef; point:TimePoint. Только current active capture: world совпадает, gameplay_started=True, active_timeline_id=point.timeline_id; snapshot_head может быть закреплённым parent другой ветки, ancestry проверяет source port |
| `reads/capture.py`: HistoricalTimeCapture | snapshot:WorldSnapshotRef; point:TimePoint. World/timeline совпадают; подтверждённый immutable snapshot state. Нельзя передать вместо TimeCapture для продвижения |
| `reads/request.py`: CurrentTimeRead | expected:WorldPublicationRef. Чтение ровно этой publication с проверкой актуальности; не скрытый latest lookup. DAG получает expectation через public Snapshot/World read |
| `reads/request.py`: HistoricalTimeRead | snapshot:WorldSnapshotRef. Не переключает active timeline |
| `changes/advance.py`: PrepareAdvance | operation_id:EntityUid; base:TimeCapture; duration:TimeDuration. Duration>0; нет action kind, combat settings, turn_id, foreign effects |
| `changes/advance.py`: TimeAdvanceProposal | operation_id:EntityUid; base:TimeCapture; interval:TimeInterval. interval.start=base.point, end>start; end вычислен из duration. Не receipt, не proof текущей актуальности base |
| `changes/section.py`: TimeAdvanceSection | Конкретная специализация DomainSection[TimeAdvanceProposal]: header:SectionHeader; patches:tuple[TimeAdvanceProposal,...], ровно один proposal на acceptance группу. SectionKey/format version registration OPEN. Никакого union с чужими domain sections в Time |
| `operations/arithmetic.py`: AddDurationInput | point:TimePoint; duration:TimeDuration |
| `operations/arithmetic.py`: ComparePointsInput | left:TimePoint; right:TimePoint |
| `operations/arithmetic.py`: MakeIntervalInput | start:TimePoint; end:TimePoint |
| `operations/arithmetic.py`: PointResult / IntervalResult / DurationResult | соответственно point:TimePoint / interval:TimeInterval / duration:TimeDuration |
| `operations/arithmetic.py`: ComparisonResult | order:TimeOrder; TimeOrder — закрытый enum BEFORE/EQUAL/AFTER в том же файле. Cross-world/timeline comparison возвращает отказ, не ordering |
| `operations/conversion.py`: SecondsInput / HoursInput | соответственно seconds:U63,nanoseconds:Nano / hours:U63. Exact целые часы; дробные значения передаются seconds+nanos, не float |

Ошибки — конкретные POJO в `results/errors.py`:

- TimeScopeMismatch(left:TimePoint, right:TimePoint).
- TimeRangeOverflow(operation:TimeArithmeticKind), где enum ADD/DIFFERENCE/HOURS_TO_DURATION.
- TimeIntervalReversed(start:TimePoint, end:TimePoint).
- TimeAdvanceMustBePositive(duration:TimeDuration).
- TimePublicationConflict(expected:WorldPublicationRef, observed:WorldPublicationRef).
- TimeInactiveTimeline(requested:EntityUid, active:EntityUid | None).
- TimeStateUnavailable(world_uid:EntityUid, reason:TimeUnavailableReason); enum WORLD_MISSING/CLOCK_UNINITIALIZED/SNAPSHOT_MISSING/SOURCE_UNRESOLVED.

Все поля errors перечислены; user-facing сообщения строятся из typed диагностики внешним consumer. Malformed POJO — стандартный structural admission отказ проекта, не экземпляр доменного success. Cancellation распространяется как cancellation, не TimeStateUnavailable. Нарушение storage guarantee — infrastructure fault, не fabricated domain refusal. Exact mapping в общую диагностику проекта OPEN; не создавать второй log/policy engine.

**Дополнение file map:** operations/arithmetic.py и operations/conversion.py — два новых модуля + init = 3; changes/section.py доводит changes до 3 файлов с init. В values/point.py располагаются только point/его scalar constraints, в duration.py — duration constraints. Число файлов остальных папок §6 не меняется; число классов внутри файла не означает отдельный файл на каждый wrapper. Перед кодом проверить лимиты размера классов и модулей по exact реализации.

## 11. Публичные операции, вызываемые DAG

Каждая строка — отдельная typed операция. Обозначение `→ A | B` перечисляет конкретные допустимые POJO, а не generic Result. Время не читает actionCore, не зовёт World CRUD и не вызывает Snapshot.apply. Pure операции могут также вызываться доменным caller для арифметики, но не выбирают следующий шаг.

| Public method / exact I→O или E | Caller requirement | Boundary / consistency / idempotency |
|---|---|---|
| TimeArithmetic.add(AddDurationInput) → PointResult \| TimeRangeOverflow | DAG: конец заданной длительности; Physics: time facts | Pure, никаких reads/writes; сохраняет scope; одинаковый input даёт одинаковый output |
| TimeArithmetic.compare(ComparePointsInput) → ComparisonResult \| TimeScopeMismatch | DAG/consumers: порядок моментов | Pure, сравнение только внутри одной ветки; calendar epoch не timeline identity |
| TimeArithmetic.interval(MakeIntervalInput) → IntervalResult \| TimeScopeMismatch \| TimeIntervalReversed | DAG: coherent start/end для Physics/lazy consumers | Pure, [start,end); zero допускается |
| TimeArithmetic.elapsed(TimeInterval) → DurationResult \| TimeRangeOverflow | Physics, путешествие, отдых, needs/resources/weather через DAG | Pure, не считает эффекты и не выбирает cadence |
| TimeConversions.from_seconds(SecondsInput) → DurationResult | DAG получает уже рассчитанные секунды от owner действия/боя | Pure exact conversion, constraints на admission; без round_seconds default/проверок Combat |
| TimeConversions.from_hours(HoursInput) → DurationResult \| TimeRangeOverflow | Legacy world-hour consumers при миграции | Pure, 3600 seconds/hour; не reinterpret turn_id |
| async TimeReader.read_current(CurrentTimeRead) → TimeCapture \| TimePublicationConflict \| TimeInactiveTimeline \| TimeStateUnavailable | DAG: старт advance, Physics resume, интерфейс | Один coherent read под expected publication; активная ветка; repeat при том же base стабилен, после публикации conflict |
| async TimeReader.read_historical(HistoricalTimeRead) → HistoricalTimeCapture \| TimeStateUnavailable | DAG: история/restore preparation/lazy evidence | Immutable snapshot read; inactive history разрешена; не делает restore; идентичный retained snapshot даёт те же facts |
| TimeAdvancePreparer.prepare(PrepareAdvance) → TimeAdvanceProposal \| TimeAdvanceMustBePositive \| TimeRangeOverflow | DAG после получения положительной длительности от actionCore | Pure preparation на supplied capture; никаких writes. Одинаковый input → тот же candidate. Актуальность base повторно проверяет acceptance boundary |

Owner всех операций таблицы — Time. Files/imports: классы и factory §6; request/result imports — §10; arithmetic/conversions не импортируют repositories/World/Physics/engine. `make_time_reader(source:ITimeReadSource)->TimeReader`; `make_time_advance_preparer()->TimeAdvancePreparer` — composition-only, не DAG business operation. ITimeReadSource имеет те же две отдельные read signatures, гарантирует provenance и coherent state; реализация поверх Snapshot read OPEN, не SQL latest fallback. Публичного TimeService.execute(kind,request) нет.

Legacy/gates для каждой группы: arithmetic/conversions — новые публичные операции, legacy formulas retain до миграции callers; gate T3. Reads — replace чтение raw World.current_tick, retain legacy до coherent Snapshot source; gate T4. Prepare — replace прямой increment_tick только после T5 и блокировки косвенных generic writers; до этого ни один writer не удаляется этим документом. Generic import/export retain до World-approved migration/fingerprint policy. Нельзя считать отсутствие найденного increment_tick caller основанием убрать generic writes.

### Foreign public contracts — отдельно от Time API

| Owner / обязательный seam | POJO / exact status | DAG применение / gate |
|---|---|---|
| World settings/calendar read | WorldTimeSettings и WorldCalendarDefinition/Registry/Epoch, пути §6; exact calendar rules/keys/revision reference OPEN | Читать по той же publication/snapshot что clock; default Gregorian/24 и explicit custom start применяются через owning POJO. Нельзя подставить dict для закрытия Time API |
| Time pure calendar projection | CalendarProjector.project(CalendarProjectionRequest) → CalendarProjection; exact поля и concrete refusal union OPEN до World calendar schema | Request/result placement `dataModel/world/calendar/projection.py`; чистое преобразование, без lookup/default/CRUD. Это явный незакрытый публичный контракт, а не реализуемый порт |
| World create/update calendar/epoch | Immutable prepared World change, foreign exact Input/Output/Error OPEN | DAG вызывает World. Create/read допустимы; update создаёт новую version; delete ранее использованной версии запрещён retention. Удаление текущего назначения/неиспользованного definition требует World policy, не Time метода |
| World/Snapshot initial clock | Initialization prepared change + timeline binding OPEN | Create clock при инициализации; once-captured UTC start передаётся явно. Не добавлять arbitrary Time.create/set_clock до принятия foreign seam |
| Snapshot apply | Existing IWorldSnapshotApply.apply(PatchSet[S]) → SnapshotApplyResult | TimeAdvanceSection concrete; общий heterogeneous S с другими effects закрывает owning caller, не Time. Точный aggregate union OPEN до перечня effect owners |
| actionCore | Длительность действия и causal execution evidence — foreign exact POJO OPEN | DAG передаёт Time только Duration, не action inputs. Проверка «все effects действия включены» не у Time |
| Turn/UI owner | Номер хода и display configuration — foreign exact POJO OPEN | DAG собирает отдельную композицию Time capture + turn data + календарная проекция; все согласованы по принятой публикации. Time не генерирует turn counter |

### Snapshot acceptance boundary

DAG подготавливает Time proposal и эффекты других owners от одного captured base, собирает общий PatchSet. Time handler проверяет start/base/end, operation_id и active timeline в supplied acceptance context; append выполняется только в общем commit scope без собственного commit. Snapshot выполняет CAS publication/head и принимает всю группу или ничего. Связанные effects и continuation должны принадлежать тому же интервалу/base; сбор и полнота причинной группы — DAG/соответствующие owners, не Time dispatcher.

Snapshot сохраняет operation identity + fingerprint и outcome атомарно с принятой публикацией. Это required foreign guarantee, не доказанная готовность backend: совпадающий retry возвращает accepted refs без второго advance; тот же ID с другим payload отвергается. Unknown commit требует узнать durable outcome либо повторить тот же запрос по existing idempotent contract; новый operation ID до разрешения outcome запрещён. Exact status/recovery public port OPEN у Snapshot. Candidate hash/Time proposal не acceptance receipt.

Два advance от одного base: только один проходит CAS; второй получает conflict и требует нового capture/явного DAG пересчёта effects, не автоматического прибавления к новому clock. Cancellation до commit оставляет world неизменным; во время/после commit caller разрешает outcome через Snapshot. Time не откатывает принятые данные. Restore/branch принадлежат Snapshot: clock и версии settings восстанавливаются согласованно, новая ветка получает новую timeline identity. Inactive timeline нельзя advance. Restore в прошлое не отрицательный duration и не update существующей истории. Same-timeline historical compare — арифметика; cross-timeline сравнение отказывает даже при равной координате, ancestry обрабатывается внешним owner.

## 12. Документальные walkthrough / proof obligations

| Сценарий | Предлагаемый сквозной результат |
|---|---|
| Zero interval | DAG строит start=end для технического Physics zero path; Time.elapsed=0; prepare advance с zero отвергается. Бесплатного игрового действия не возникает |
| Positive interval | actionCore выдаёт duration; DAG capture→add/interval→domain effects→prepare→Snapshot apply. Clock/end видимы только после acceptance |
| Бой 6 секунд | Combat использует скопированный round_seconds, DAG получает 6s. Time не проверяет боевые настройки. End=start+6s; округления до часа нет |
| Несколько действий внутри часа | Последовательные accepted intervals 6s,12s,30s дают 48s; каждый следующий capture от предыдущего acceptance. Turn sequence не выражает 48s |
| Physics resume | DAG передаёт capture.point=interval.start, compatible accepted continuation от того же base; Physics checks остаются Physics. Для исторического continuation нельзя подменить start текущим latest clock |
| Смена календаря | World prepared settings version принимается Snapshot; simulation seconds не меняются только из-за смены отображения. История читает соответствующую snapshot/version, не latest settings |
| Без настройки календаря | World resolver создаёт обычный Gregorian definition; hours missing→24; initial start missing→once captured UTC+0. UI получает дату/точное время и отдельный turn. Ошибочный custom calendar не заменяется default |
| Два concurrent advance | Одинаковый base, разные IDs: первый accepted, второй conflict, без частичных domain effects |
| Retry unknown commit | Тот же ID/fingerprint; Snapshot outcome accepted возвращает прежние refs. Если outcome ещё неизвестен, не создавать новый advance и не утверждать failure |
| Restore в прошлое / branch | Snapshot читает clock/settings на выбранной точке; новая ветка получает отдельный timeline ID; history сохраняется. DAG передаёт новый capture; старая continuation проходит отдельную owner validation |
| Inactive timeline | Историческое чтение допускается; current read/acceptance advance для inactive отказывает; Time не переключает active timeline |
| Cancellation | До acceptance — только локальные proposals; при неизвестном commit — recovery тем же ID. После accepted clock не вычитается обратно |

Будущие runtime proofs: exact nanosecond roundtrip и signed range boundaries; coherent capture при конкуренции; replay dedup после crash; clock/effects/continuation atomicity при сбое; pinned branch ancestry; restore calendar revision; отсутствие hidden writers; cancellation before/during/after commit. Таблица — design walkthrough, не свидетельство пройденных tests.

## 13. Повторный verdict

Исправлены: открытый статус уже принятых defaults, смешение calendar settings с TimeCapture, потенциальное присвоение Time боевых conversions/rules, отсутствие public operation inventory. Добавлены явные local POJO fields, закрытые result/error alternatives для core API, файлы и consumer boundaries. Результат: **CORE API PROPOSAL PRESENT; FOREIGN CONTRACT FREEZE OPEN; NOT CODE-READY**.

Блокеры полной архитектурной приёмки: выразительная World calendar schema и projection I/O/E; coherent Snapshot source implementation contract; initialization и heterogeneous acceptance/status/recovery bindings; actionCore/turn consumer contracts; complete legacy migration ledger. Эти блокеры не требуют полного Physics/GEN/Snapshot DONE. Следующая работа документальная по T2/T4/T5, затем T6/T7; review не заменяет приёмку пользователя. Никакие POJO, ports, DDL или DAG nodes этим обновлением не реализованы.
