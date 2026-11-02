# Time — owning architectural proposal

Статус: RESEARCHED PROPOSAL / USER ACCEPTANCE PENDING; foreign schema freeze OPEN (§21). Не CODE-READY, не пользовательская приёмка всего proposal. Только документы; production POJO, DDL, DAG nodes, publication и cutover запрещены текущим scope.

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
- Последующее указание пользователя: actionCore прорабатывается позже; его foreign contracts намеренно остаются OPEN. Не проектировать их внутри текущего Time scope. Это prerequisite будущей gameplay integration, не блокер приёмки core Time POJO/арифметики/подготовки. Time API принимает готовую TimeDuration без зависимости от класса actionCore.
- Последующее решение пользователя: реализация техдолга допускается после core. Исследование legacy и фиксация disposition нужны для проектирования, но удаление/переключение legacy consumers не являются prerequisite изолированного core. Core contract freeze и безопасные границы обязательны; runtime cutover требует закрытия связанных обходных путей (§26). Текущий scope по-прежнему только документы, не разрешение писать core сейчас.
- История версий календаря сохраняется через существующий механизм версионирования; отдельный calendar version store не вводится. Exact World/Snapshot reference binding ещё OPEN.
- Явное решение пользователя: `World.calendar: dict` и связанный legacy путь хранения/обработки подлежат удалению при реализации перехода. Это не контракт и не поддерживаемый параллельный API. Цель — World-owned POJO, общий resolver и согласованный versioned storage binding. Текущий документ не удаляет production поле/DDL, поскольку implementation вне scope.
- Интерфейс обязан отображать точное время МИРА и отдельно номер хода. «Ход N» не заменяет время даже при отсутствии пользовательского календаря. Time не владеет интерфейсом, номером хода или его продвижением. Согласованную передачу этих данных потребителю организует DAG по public contracts владельцев. Настройки возвращения/отображения времени требуют exact consumer contract; они не изменяют authoritative clock и не допускают потери его точности. Выбор календаря и размещение presentation settings ещё OPEN.
- Если пользовательский календарь мира не задан, мир использует обычный календарь (решение пользователя). Это штатное world-owned значение по умолчанию, а не отсутствие календарной проекции или показ elapsed seconds вместо даты. Time получает разрешённое определение календаря от владельца мира, не выбирает fallback самостоятельно. Обычный календарь — григорианский; при отсутствии стартовой даты/времени используются текущие дата и время (принято пользователем). Некорректный заданный календарь нельзя молча заменять обычным.
- Календари, стартовая дата и календарные эпохи принадлежат миру. Календари любого вида задаются настройками и описанием, расширяемость N+1 по правилу движка. Длительность суток — настройка мира.
- Уточнение пользователя: N+1 — произвольные данные мира, ссылающиеся на закрытые типы enum движка. Не создавать enum на каждый авторский календарь/месяц/эпоху; закрыты семантические виды правил, а не пользовательские записи. Периодический календарь не принимается как ограничение всей архитектуры (§23).
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
| `backend/app/db/models/world.py` | current_tick:int=0; calendar и combat_settings — dict | Legacy evidence, не typed Time API; calendar dict — REMOVE по решению пользователя, не retain target |
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

Calendar legacy removal gate: заменить `World.calendar: dict`, его raw consumers и generic import/export/update bypass на owning POJO + validated boundary; согласовать replacement SQL/wire representation и удалить старое поле/колонку либо заменить их типизированной проекцией в едином cutover. Старый произвольный JSON blob не сохраняется как второй authoritative источник. Физический JSON encoding нового POJO, если выбран World owner, не означает сохранение legacy dict-контракта. Проверить callers, WorldSlice, bundle roundtrip и version history до удаления; не добавлять dual-read/error fallback на старый dict. Это обязательный будущий этап, не выполненная миграция.

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
| T2-TZ Calendar specification freeze | T2; решение N+1 §23 | Обязательное полное закрытие календарных enum/POJO/API по §24, без deferred calendar schema |
| T3 Time values и pure API | T1; T2-TZ обязательно для calendar projection части | Exact point/duration/interval/conversions/errors и file/import map |
| T4 Coherent reads и preparation | T3; Snapshot publication/ref contracts | Capture, current/historical reads, proposal/base expectations; запрет mixed-source facts |
| T5 Acceptance/handoff | T4; совместный Snapshot contract proposal | Atomic time+effects, operation identity, unknown outcome/retry/concurrent advances/cancellation/restore/branch |
| T6 Сквозное review | T2–T5 | Все walkthrough исходного запроса, exact public API inventory, закрытые unions, counts/import cycles, legacy gates |
| T-RULE Agent-rule audit | T6; T2-TZ; актуальная consolidated map | Проверка всего плана по §25, findings устранены или явно блокируют затронутый scope |
| T7 Пользовательская приёмка | T-RULE; явный список внешних deferred contracts | Архитектурный verdict. Даже PASS не разрешает код автоматически |

T0 и уточнение внешних seam можно исследовать независимо. После T1 arithmetic часть T3 независима от calendar T2; чтение Snapshot contracts и consumer requirements Physics/GEN можно вести параллельно документально. Полный Physics/GEN/Snapshot DONE не prerequisites дизайна. Недостающий конкретный контракт блокирует только соответствующий freeze/integration, не всё исследование. Production integration позднее потребует готовности нужного acceptance seam и явного разрешения на implementation.

Обязательный T6 набор: zero/positive, бой меньше часа, несколько действий внутри часа, Physics resume capture=start, смена календаря/no-calendar, concurrent advances, retry unknown commit, restore/branch, inactive timeline, cancellation. Для каждого нужны input/base → chosen DAG operations → proposal → acceptance/refusal → повторное чтение. Документальные walkthrough приведены в §12; runtime proofs ещё не выполнены.

## 9. Остаток исследования / stop boundary

Исходный checklist: полный ledger требований/consumers и writers; exact public Input/Output/Error и CRUD applicability; files/classes/factories/import directions; coherent capture и Snapshot acceptance; retries/concurrency/unknown outcome/cancellation; restore/branch/inactive timeline; walkthrough; этапы и внешние contracts. Core proposal и walkthrough добавлены в §§10–12; актуальные незакрытые пункты и verdict — §§14–17 (уточняют промежуточный §13).

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

Snapshot сохраняет operation identity + fingerprint и outcome атомарно с принятой публикацией. Это required foreign guarantee, не доказанная готовность backend: совпадающий retry возвращает accepted refs без второго advance; тот же ID с другим payload отвергается. Unknown commit требует узнать durable outcome либо повторить тот же запрос по existing idempotent contract; новый operation ID до разрешения outcome запрещён. Существующие status/recovery APIs Publication уточнены в §14.1; Time integration/error mapping остаются OPEN. Candidate hash/Time proposal не acceptance receipt.

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

Блокеры полной архитектурной приёмки: выразительная World calendar schema и projection I/O/E; coherent Snapshot source implementation contract; initialization и heterogeneous acceptance/status/recovery bindings; actionCore/turn consumer contracts; complete legacy migration ledger. Эти блокеры не требуют полного Physics/GEN/Snapshot DONE. Следующая работа документальная по T2/T4/T5, затем T6/T7; review не заменяет приёмку пользователя. Никакие POJO, ports, DDL или DAG nodes этим обновлением не реализованы. Последующая детализация и актуальный остаток — §§19–21.

## 14. Дополнительное исследование внешних seams и migration ledger

Этот раздел уточняет статусы §§3/11/13 по повторному чтению исходников, не объявляет внешние owners DONE.

### 14.1. Publication/recovery — существующие точные контракты

`application/publication/service/operationLedger.py` уже предоставляет:

- `read(operation_id:EntityUid) -> OperationRecord | None`;
- `recover(operation_id:EntityUid) -> OperationRecord`;
- `cancel(operation_id:EntityUid, fence:int) -> OperationRecord` (positive fence).

Это application seam Publication, а не предлагаемые методы Time. `IOperationStore.record_terminal(scope:CommitScope, outcome)` документирует запись в той же transaction; `record_refusal` допускается после подтверждённого rollback и запрещён при unknown COMMIT. В `SqliteOperationStore` проверяются единый coordinator/access, phases/fence и terminal evidence. Конкретный operation kind для Time-containing runtime PatchSet — существующий SNAPSHOT_APPLY, отдельный TIME_ADVANCE не нужен.

`OperationRecord.terminal` — существующий закрытый union `SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled | None`. Для runtime advance ожидается SNAPSHOT_APPLY и SnapshotApplyResult либо cancellation; несовпадение kind/fingerprint — contract fault, не новый advance. None/нет записи не доказывает rollback: сначала разрешается судьба отправленного запроса. Recovery caller использует тот же ID и существующий ledger, не вызывает storage напрямую. Exact public error translation ledger → DAG ещё OPEN; внутренние exceptions не скрывать как Time refusal.

`ISnapshotHistoryStore.read(ref, scope)` читает metadata, а не готовое Time state. `IWorldPublicationStore.read(world_uid, scope)` и CommitReadScope дают building blocks согласованного чтения. **Исправление статуса:** read/recover application API существует; отсутствует проверенный Time state binding к нему, а не весь механизм recovery.

### 14.2. Coherent source proposal

Current read: TimeReader делегирует ITimeReadSource; Snapshot integration открывает один read scope, проверяет expected publication, разрешает accepted Time state из pinned head/base и ancestry, выдаёт TimeCapture. Domain state adapter не делает дополнительный latest SQL query вне scope. Historical read фиксирует snapshot ref, читает immutable metadata + Time state; current active check не применяется. Domain state serialization/retention binding остаётся внешним OPEN: нельзя восстановить clock только по metadata.turn_id.

Для calendar read World получает тот же expected publication или historical snapshot ref. Отдельные read calls допустимы при immutable pinned version: если current publication ушла, явно conflict; не возвращать смешанный набор. DAG связывает clock/settings/turn data по publication/snapshot identity. При branch parent другого timeline Time point в новом active capture должен быть явно rebound к новой timeline без изменения coordinate; это Snapshot-owned branch transition, не Time.compare cross-branch.

Initial state: World creation фиксирует accepted settings/start anchor один раз; gameplay-start binding сохраняет Time coordinate zero для новой root timeline атомарно с GameplayStarted. Исходный `GameplayStarted` допускает head=None и не создаёт snapshot tick — нельзя обходить его искусственным turn 1. Требуется extension к initial domain state binding у World/Snapshot; конкретный порт не найден и остаётся OPEN. Branch initialization использует координату branch point, не zero и не новый wall-clock старт.

### 14.3. Writers / consumers / disposition

| Evidence | Retain / replace / gate |
|---|---|
| World.current_tick; increment_tick interface/SQLite UPDATE+commit | Retain до cutover; заменить authoritative clock на accepted Time state. Legacy import значение N интерпретировать как N×3600s **только при подтверждённой версии legacy schema**, не для произвольного нового wire |
| WorldService.create/update/import/_save, BaseRepository.save/upsert; WorldSectionHandler asdict/import | Закрыть обход runtime Time через generic world writes; settings CRUD остаётся World. Snapshot/history import должен сохранять clock provenance, definition import не вправе незаметно заменить live clock. Exact mode/field restrictions принимает World owner |
| deriveWorldUid исключает current_tick | Новое runtime clock также не включать в definition identity. Не копировать список исключений без согласованного wire contract |
| Regions `stateChange/progress.py`, `consumer.py`, `contracts.py`, RegionState.last_eval_tick | Реальная elapsed-time цепочка: progress использует target.strength×elapsed_ticks/(inertia+weight); consumer обновляет last_eval_tick и child state. Явный TODO о Time/LOD. Replace integer elapsed contract на согласованные duration/evaluation facts; formula/inertia/residual ownership остаётся Regions |
| Regions `declaredRegionEdit.py` передаёт elapsed_ticks=0 | Это edit/evaluation, не бесплатное игровое действие; сохранить zero technical semantics. Не запрещать все zero consumers из-за action rule |
| storage TZ needs increment_per_tick, rest/sleep_requirement_ticks | Legacy rates/durations retain до consumer migration. Предложение: сохранить численное значение как rate per 3600s либо duration×3600s по owning schema version; дробные интервалы и остатки обрабатывает Needs/Rest, не Time |
| storage TZ travel_ticks, craft/regeneration | Длительность задаёт actionCore/соответствующий gameplay owner; Time только conversion. Нельзя floor короткое путешествие до нуля |
| storage TZ :2555 interior transitions без временной стоимости | Конфликт с принятым «все действия тратят время». Предложить владельцу Actions различить logical link и игровое действие перехода; Time не назначает произвольную цену |
| storage TZ remaining_ticks/weather_duration; lazy near/medium/far | Weather и lazy owners принимают elapsed interval, рассчитывают overdue events/cadence/residual. Time не запускает N/M scheduling и не обновляет ресурсы |
| Combat round_seconds 4..12/default6/copy at start | Retain нормативный контракт Combat; snapshot copied setting определяет длительность, не latest World settings. Time seconds converter не знает раундов |
| Physics latest capture=start, SI, zero/resume | Передавать TimeInterval/TimeCapture напрямую, без Physics clock aliases. Solver substeps могут быть float numerical internals, но accepted end точный и не округляется из последнего substep |
| SQL turns.turn_id TEXT против world_snapshots.turn_id INTEGER | Разные реальные сущности! Chat turn UID нельзя показывать/передавать как snapshot ordinal автоматически. Public UI turn-number contract требует владельца chat/GEN; Time не выбирает один из счётчиков |

Поиск current_tick/increment_tick/calendar conversions и elapsed_ticks выполнялся по backend/app Python, generic writers прочитаны отдельно. Не охвачены любые динамические SQL/внешние клиенты: перед cutover обязателен write audit на runtime boundary; negative evidence не равняется отсутствию writers. Runtime потребители needs/travel/weather по этому исследованию не признаны реализованными только по наличию ТЗ.

## 15. Calendar proposal для World owner (не перенос ответственности в Time)

### 15.1. Выразительность и граница обещаний

Фиксированная схема «одинаковое число дней в каждом месяце» недостаточна. Предлагается data-driven календарь с именованными единицами, упорядоченными периодами, условными вставками и epoch anchors. Prose хранит описание, но не исполняется как код/LLM. Невозможно честно объявить любую мыслимую систему покрытой конечным непроверенным списком rules: неизвестное правило должно давать UnsupportedCalendarRule, не fallback Gregorian. Пользовательская цель «любой вид через настройки» сохраняется; exact grammar и доказательство выразительности — предмет World contract acceptance.

Для review предлагаются две конкретные формы: GregorianCalendarDefinition и RuleCalendarDefinition. Это union конкретных POJO, не `CustomCalendar(payload:dict)` и не произвольный исполняемый script. Gregorian — встроенный алгоритм с proleptic правилами; conventions year zero/до нашей эры требуют отдельной фиксации, не заимствуются молча из datetime (диапазон Python datetime недостаточен).

### 15.2. Exact outer POJO и явно незакрытый rules contract

Предлагаемая композиция папок World calendar (заменяет плоскую карту §6, пока только документ): `identity/refs.py`, `definitions/gregorian.py`, `definitions/ruleCalendar.py`, `definitions/registry.py`, `epochs/epoch.py`, `projection/request.py`, `projection/result.py`, `projection/errors.py`; в каждой leaf папке вместе с init соответственно 2/4/2/4 файла. В корне calendar только init. Settings/timeSettings.py остаётся отдельно. Импорты definitions→identity, epochs→identity+TimePoint, projection→definitions+epochs+Time values; обратных импортов в Time values нет.

| Proposed World-owned POJO | Поля / OPEN seam |
|---|---|
| CalendarVersionRef (`identity/refs.py`) | calendar_key:RegistryKey[WorldCalendarRegistry]; publication:WorldPublicationRef. Предложение использовать уже принятую world publication как version witness, не вводить счётчик версий. Historical resolution через snapshot metadata; точный existing source-revision binding требует World approval |
| GregorianCalendarDefinition | calendar_key:RegistryKey[WorldCalendarRegistry]; description:str; формат имени/описания — разрешённый prose, не идентификатор. Gregorian algorithm fixed; start anchor и world hours передаются отдельно |
| RuleCalendarDefinition | calendar_key:RegistryKey[WorldCalendarRegistry]; description:str; rules:CalendarRuleSet. **CalendarRuleSet OPEN foreign World type**, ни dict/Any, ни непроверенный union не подставлять. Эта форма пока не freeze-ready |
| WorldCalendarRegistry | entries:tuple[GregorianCalendarDefinition \| RuleCalendarDefinition,...], непустая N+1 коллекция, уникальные keys; selected:RegistryKey[WorldCalendarRegistry]. RegistryKey self-reference использует существующий registry механизм, не custom lookup |
| WorldCalendarEpoch | epoch_key:RegistryKey[WorldCalendarEpochRegistry]; calendar_key:RegistryKey[WorldCalendarRegistry]; anchor:TimePoint; label:str; description:str. Epoch numbering rules OPEN у World, не timeline identity. WorldCalendarEpochRegistry — отдельный foreign registry contract OPEN; proposed файл epochs/registry.py (leaf epochs с init итого 3 файла) |
| CalendarProjectionRequest | point:TimePoint; capture:TimeCapture \| HistoricalTimeCapture; settings:WorldTimeSettings; calendar:GregorianCalendarDefinition \| RuleCalendarDefinition; version:CalendarVersionRef; anchor:CalendarStartAnchor. **CalendarStartAnchor OPEN**: точная start-date форма зависит от rules; request equality point/capture и provenance обязательна |
| CalendarProjection | point:TimePoint; version:CalendarVersionRef; date:CalendarDate; time_of_day:CalendarTimeOfDay. **CalendarDate/CalendarTimeOfDay OPEN foreign World POJO**, должны покрывать intercalary/epoch/custom periods; нельзя выдавать year/month/day тройку за универсальный тип |

Prose str в предлагаемых World fields разрешается только как текст описания/подписи; при переносе в доменное ТЗ перечислить эти исключения политики contract-creation. Exact calendar error POJO proposal: CalendarSourceMismatch(expected:WorldPublicationRef, actual:WorldPublicationRef), CalendarPointMismatch(expected:TimePoint, actual:TimePoint), CalendarProjectionOutOfRange(point:TimePoint), UnsupportedCalendarRule(calendar_key:RegistryKey[WorldCalendarRegistry]). Structural rule/start errors используют owning field/model diagnostics общего resolver.

Предлагаемая публичная signature: `CalendarProjector.project(CalendarProjectionRequest) -> CalendarProjection | CalendarSourceMismatch | CalendarPointMismatch | CalendarProjectionOutOfRange | UnsupportedCalendarRule`. Чистый Time algorithm, World-owned definitions. Все alternatives перечислены, но поля foreign types выше OPEN: **не готово к production typing**. Полная schema без World design не выдумывается. DAG явно читает настройки нужной версии, затем вызывает выбранное преобразование; projector не читает World и не выбирает новые public операции.

### 15.3. Calendar CRUD requirements к World

Create definition/epoch — prepared World change; read current/historical — обязательно pinned revision; update — новая immutable version. Delete используемой исторической версии запрещён; removal текущего назначения допустим лишь с выбранной заменой и сохранением истории. Для единственного календаря «удалить и остаться без разрешённого календаря» запрещено: требуется явная World operation переключения на canonical Gregorian. Time не имеет этих методов. Exact World preparation I/O/E остаются OPEN foreign contracts; текущий generic dict WorldService не считать их реализацией.

Принято пользователем: изменение hours_per_day создаёт новую версию календарных настроек с anchor в момент изменения. Текущая отображаемая дата и время сохраняются, если допустимы по новым настройкам; иначе требуется явно заданная валидная календарная привязка. Например, 24→30 часов допускает сохранение 18:00; 24→12 при 18:00 требует явной новой привязки, без modulo/clamp. SI-момент мира и прошедшая длительность не меняются. Дальнейшая проекция использует новую версию/anchor, исторические события — действовавшую тогда версию. Проверка и подготовка изменения принадлежат World с чистыми Time conversions; принятие — Snapshot. Не пересчитывать историю от origin по новым hours/day.

## 16. Конкретные внешние изменения на согласование

Другие файлы **не изменены**. Предлагаются:

1. `project_data_storage_tz.md` «Система времени» / «Два масштаба»: заменить session ownership и равенство current_tick=turn_id; описать seconds+nanos, fixed 3600s/hour, configurable hours/day default24; Gregorian current UTC start/custom explicit start. Evidence: принятые решения §1 и World storage.
2. Там же rest/needs/travel/weather: явно версионировать migration tick-based quantities; не менять formula units скрытно. Interior travel zero wording отправить actionCore owner (§14.3).
3. `tz_world_snapshot.md` / owning World plan: initial Time state при gameplay start без snapshot tick, domain state read по scope, atomic Time+effects и branch rebinding; reuse existing OperationLedger. Не добавлять второй Time publisher.
4. Physics owning plan: заменить placeholders TPoint/TInterval/TCapture конкретными Time POJO после их приёмки; сохранить capture=start и accepted continuation provenance. До acceptance только requirement, без импортов.
5. GEN owning plan: требования данных `public publication read → Time current capture`, `actionCore duration → Time prepare`, `same-base domain effects + Time section → Snapshot apply`, `accepted refs → current UI reads`. Это логические зависимости proposal, **не новые NodeIds, child edges или CALL/RETURN bindings**. Exact invocation lifetime/operation ID reuse согласовать у GEN, существующее родство не менять.
6. World calendar owner: N+1 rules/schema/provenance и POJO-policy registration по §15; конкретные files — предложение, не молчаливое создание нового owning-плана.

## 17. Итог исследования и пользовательская приёмка

**Verdict: архитектурный proposal исследован и предъявлен; implementation запрещена текущим scope.** Core Time API/file map и responsibilities конкретизированы. Нет основания объявить весь design frozen или старые ТЗ выполненными: foreign calendar rules/start/date schemas, World CRUD preparation и initial/domain-state bindings остаются явно OPEN с владельцами и требуемыми входами/выходами. Runtime proofs остаются будущими тестами, даже при принятии proposal.

На приёмку:

- A1: core POJO/API §§10–11, интервалы [start,end), cross-timeline comparison refusal, без Action/Calendar CRUD в Time.
- A2: pinned captures и atomic Snapshot acceptance, reuse OperationLedger, initialization без искусственного snapshot turn (§14).
- A3: direction/files §6/§15 и bounded calendar proposal; grammar полнота не заявлена, World foreign types остаются blockers соответствующих calendar operations.
- A4 **ПРИНЯТО пользователем:** изменение hours/day через новую version/anchor; допустимые текущие дата и время сохраняются, иначе требуется явная привязка; история и физический момент сохраняются (§15.3). Это принятие поведения, не всех production bindings.
- A5: migration policy и внешние contract requests §§14/16; exact chat turn display binding не приравнивается автоматически к snapshot turn ordinal.

Последовательность будущих документальных работ: принять core решения независимо от calendar grammar; World schema freeze и Snapshot Time binding разрабатываются независимо; затем закрыть exact calendar projection и initialization contracts; интеграционные GEN/Physics bindings только после принятия используемых APIs. Полного DONE соседних проектов ждать не требуется. Ни принятие отдельных пунктов, ни review PASS не разрешает код/cutover без отдельного задания пользователя.

## 18. Уточнение write contract: подготовка, append, принятие

Проверены existing `DomainSectionHandler`, `SnapshotApplyContext`, `IDomainCommitBinding`, `IPublicationCommitStore`, `SectionApplyReceipt`, `SectionStateRef`, `SectionHistoryRef`. Transaction owner port прямо запрещено внедрять domain handlers. Receipt содержит refs, но не свидетельствует о durable commit. Ниже конкретизируется proposal storage seam; DDL/код не создаются.

### 18.1. State и storage POJO

Файлы относительно `backend/app/`:

- `dataModel/time/storage/state.py`: **TimeClockState(point:TimePoint)** — authoritative значение, без календаря, action, turn number или wall-clock. **StoredTimeState(ref:SectionStateRef, state:TimeClockState)** — immutable accepted-state reference; ref.snapshot только WorldSnapshotRef и его world/timeline совпадают с point. Ограничение проверяется моделью, не вводит новый SnapshotRef union.
- `dataModel/time/storage/append.py`: **TimeStateAppend(operation_id:EntityUid, snapshot:WorldSnapshotRef, proposal:TimeAdvanceProposal)**. ID равен proposal.operation_id; snapshot world/timeline равны end scope; proposal.base — expected base, snapshot — назначенный Snapshot новый ref. **TimeStateAppended(state_ref:SectionStateRef, history_ref:SectionHistoryRef)** — transaction-local acknowledgement, не public accepted receipt.
- **TimeAppendConflict(expected:TimePoint, observed:TimePoint)** в том же append.py. Дублирование ref с другим payload — infrastructure integrity fault, не «успешный retry».

Time storage directory: state.py, append.py, init = 3 файла. Domain state encoding содержит оба integer компонента без float, schema version задаётся existing FormatVersion. Конкретный canonical manifest ID/SectionKey резервирует существующий registry при implementation freeze; не использовать случайный строковый key.

### 18.2. Внутренний порт Time, не публичный DAG API

`application/time/storage/statePort.py`:

- **ITimeStateReader.read(ref:SectionStateRef, scope:CommitReadScope) → StoredTimeState | None**. Читает ровно ref, не latest. Неподходящий section/world-kind отвергается структурной проверкой; отсутствие required state преобразуется read boundary в TimeStateUnavailable, не zero default.
- **IBoundTimeStateWriter.append(request:TimeStateAppend) → TimeStateAppended | TimeAppendConflict**. Writer уже связан с CommitScope. Не имеет commit/rollback/transaction методов и не пишет текущий World row. Проверяет accepted start в supplied base и сохраняет immutable state/history в той же transaction.
- **ITimeCommitBinding.bind(scope:CommitScope) → IBoundTimeStateWriter** — конкретизация существующего IDomainCommitBinding, не новый transaction coordinator.

Storage application folder: statePort.py + init = 2. Concrete backend adapter path предлагается `db/repositories/sqlite/time/stateStore.py` (+init = 2); exact SQL layout и append/history read implementation OPEN. При выборе другого утверждённого domain storage путь пересматривается, scope guarantees сохраняются. Mapping слой импортирует Time POJO, Time pure не импортирует db.

### 18.3. Section handler — exact existing interface specialization

**TimeSectionHandler(DomainSectionHandler[TimeAdvanceSection])**, файл §6:

- `validate(section:TimeAdvanceSection, context:SnapshotValidationContext) → SectionAccepted | SectionRefused`;
- `apply(section:TimeAdvanceSection, context:SnapshotApplyContext) → SectionApplyReceipt | SectionRefused`;
- `encode(section:TimeAdvanceSection) → bytes`;
- `decode(payload:bytes, version:FormatVersion) → TimeAdvanceSection`.

Validate проверяет operation_id, expected_world, active timeline, captured start и положительный interval; читает через context.read_scope. Apply получает writer через bind(context.scope), повторяет необходимые актуальные preconditions и append под назначенным context.world_snapshot. На конфликт — SectionRefused(category=CONFLICT, typed FieldPathError diagnostics). На успешный append — SectionApplyReceipt с state/history refs для Time section. Construction changed:PatchRef зависит от принятого Patch identity binding, **OPEN**, не заполнять фиктивными ссылками. Сопоставление Time errors с FieldPathError — в handler boundary, через общий механизм, не по message parsing.

Snapshot записывает receipt/history и operation terminal вместе с остальными effects и публикацией. Только committed SnapshotApplyResult позволяет DAG объявить новое время принятым. Storage append не выдаётся пользователю как successful advance. CAS failure/отказ любого другого handler отменяет append общей transaction. Storage не retry-loop и не scheduler.

### 18.4. Публичная boundary DAG остаётся прежней

`prepare(PrepareAdvance) → TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow` — единственный runtime Time advance preparation contract. DAG собирает TimeAdvanceSection в typed PatchSet и вызывает Snapshot.apply. DAG не получает IBoundTimeStateWriter/CommitScope и не вызывает handler.apply напрямую. Domain-local validation и арифметика допустимы внутри prepare; чужие CRUD/сбор action effects запрещены.

Initialization и branch **не маскировать** runtime append с выдуманным snapshot. Headless gameplay-start state и branch rebind требуют собственных existing World/Snapshot lifecycle bindings; shape их storage source refs пока OPEN. Restore выбирает existing immutable state, а не вызывает Time.set_clock. Этот пункт остаётся отдельным integration gate, а не неявным дополнительным writer.

### 18.5. Принятое правило смены часов в сутках

Пользователь принял правило §15.3: сохранить текущие отображаемые дату/время при допустимости; иначе запросить явную новую календарную привязку. Owning POJO/общая validation проверяют candidate в новых настройках; невалидное изменение не публикуется. Технические transaction/ref bindings продолжают прорабатываться по правилам проекта. Данное решение не означает приёмку всего плана или разрешение implementation.

## 19. Техническая детализация календарного ядра — proposal, не скрытый scope cut

Повторно проверены `dataModel/registryKey.py` (RegistryKey[R], REF-W membership), `WorldSnapshotMetadata` (state refs могут ссылаться на прошлые snapshots), owning Snapshot map (`GameplayStart` — целевой pregame CAS service, отдельного production файла в проверенной выборке не найдено). Нельзя путать карту плана с существующей реализацией. В working tree обнаружено внешнее изменение `world-generation-plan-dependency-graph.md`; оно не редактируется.

### 19.1. Конкретная базовая grammar

Для замены неопределённого CalendarRuleSet предлагается **PeriodicCalendarRules**: конечный повторяемый цикл лет, каждый год состоит из упорядоченных именованных spans. Такой формат описывает произвольные длины месяцев, недели, дополнительные дни вне недели, високосные месяцы/годы. Gregorian остаётся отдельным built-in алгоритмом, не таблицей 400×365 дней. Это конкретный первый grammar proposal, **не доказательство выполнения требования любого календаря**: нерегулярные бесконечные правила/астрономические наблюдения требуют расширения typed grammar после review, не prose execution.

Типы World-owned, frozen/strict, поля коллекций tuple. `Count` — strict int>=1, `Index` — strict int>=0, `Year` — strict integer (не ограничивать диапазоном datetime). Ссылки на именованные записи — RegistryKey соответствующего ниже реестра; labels/description — явно разрешённый prose str.

| POJO | Exact proposed fields |
|---|---|
| CalendarSpanEntry | system_span:RegistryKey[CalendarSpanRegistry]; label:str; description:str |
| CalendarWeekdayEntry | system_weekday:RegistryKey[CalendarWeekdayRegistry]; label:str |
| CalendarSeasonEntry | system_season:RegistryKey[CalendarSeasonRegistry]; label:str |
| CalendarPeriodEntry | system_period:RegistryKey[CalendarPeriodRegistry]; label:str; from_hour:Index |
| CalendarSpanRegistry / CalendarWeekdayRegistry / CalendarSeasonRegistry / CalendarPeriodRegistry | Каждый содержит entries:tuple своего Entry,…; keys уникальны. Span registry непустой, weekday/season registry могут быть пусты; periods непусты и содержат from_hour=0 |
| CalendarSpanOccurrence | span:RegistryKey[CalendarSpanRegistry]; days:Count; participates_in_week:bool; season:RegistryKey[CalendarSeasonRegistry] \| None |
| CalendarYearPattern | spans:tuple[CalendarSpanOccurrence,...], непустой; одинаковый span key в одном year pattern не повторяется |
| PeriodicCalendarRules | cycle_start_year:Year; cycle:tuple[CalendarYearPattern,...], непустой; spans:CalendarSpanRegistry; weekdays:CalendarWeekdayRegistry; seasons:CalendarSeasonRegistry; periods:CalendarPeriodRegistry; week_anchor_day:strict int; week_anchor_weekday:RegistryKey[CalendarWeekdayRegistry] \| None |

Year pattern выбирается Euclidean modulo `(year-cycle_start_year) mod len(cycle)`, включая отрицательные годы. Число дней в полном цикле положительно. Отсутствие weekdays требует week_anchor_weekday=None; непустая неделя требует валидный anchor key. Week count пропускает spans с participates_in_week=False, такие даты имеют weekday=None. Membership, periods < hours_per_day, unique starts и season references проверяются общим resolver по полному resolved World input, не новым policy engine. Epoch — подпись/система нумерации поверх координаты; не меняет длину секунд и не переключает timeline.

`RuleCalendarDefinition.rules` в этом конкретном proposal имеет тип **PeriodicCalendarRules**, а не общий CalendarRuleSet. Union определений остаётся ровно `GregorianCalendarDefinition | RuleCalendarDefinition`. Unsupported grammar не передаётся в runtime как opaque payload. Добавление новых видов требует явного concrete POJO + алгоритма/validation + расширения union, а N+1 entries внутри существующей grammar не требует добавления enum/кода на каждый календарь.

### 19.2. Date, anchor и projection

Предлагается заменить открытые CalendarDate/CalendarTimeOfDay из §15 следующими конкретными типами:

- **GregorianDate(year:Year, month:strict int[1,12], day:strict int[1,31])**, model validator Gregorian day/month/leap validity. Proposal использует astronomical year numbering (year 0 существует) для вычисления; display era convention остаётся World formatting. Это proposed convention для приёмки, не ранее принятое решение пользователя.
- **RuleCalendarDate(year:Year, span:RegistryKey[CalendarSpanRegistry], day:Count)**; validity зависит от selected year pattern, проверяет pure projection validator.
- **CalendarClockTime(hour:Index, minute:strict int[0,59], second:strict int[0,59], nanoseconds:Nano)**; hour<hours_per_day.
- **CalendarStartAnchor(point:TimePoint, date:GregorianDate | RuleCalendarDate, time:CalendarClockTime)**. Date variant обязан соответствовать definition; не silent conversion. Branch anchor rebinding меняет только timeline identity point через согласованный lifecycle, не date/coordinate.
- **CalendarTimeOfDay(period:RegistryKey[CalendarPeriodRegistry] | None)**. Gregorian builtin periods должны быть объявлены canonical World POJO, а не hardcoded в projector; если эти подписи не настроены для Gregorian, None не означает отсутствие точного clock time.
- **CalendarProjection(point:TimePoint, version:CalendarVersionRef, date:GregorianDate | RuleCalendarDate, time:CalendarClockTime, time_of_day:CalendarTimeOfDay, weekday:RegistryKey[CalendarWeekdayRegistry] | None, season:RegistryKey[CalendarSeasonRegistry] | None)**. Gregorian weekday/season mapping в World canonical definitions требует отдельного binding, не использования Climate SeasonKey как универсального реестра.

CalendarProjectionRequest сохраняет поля §15.2, с конкретными anchor/date/rules выше. Epoch formatting не прячется в projector: отдельный pure **project_epoch(EpochProjectionRequest) → EpochProjection | CalendarPointMismatch | CalendarProjectionOutOfRange**. `EpochProjectionRequest(projection:CalendarProjection, epoch:WorldCalendarEpoch, epoch_anchor_date:GregorianDate | RuleCalendarDate)`; `EpochProjection(epoch_key:RegistryKey[WorldCalendarEpochRegistry], elapsed_calendar_years:strict int)`. Разность календарных лет — только координатное значение; никакого автоматического «нулевой год = первый» в Time. Exact alternate numbering/epoch display rules остаются World proposal, API не считает label арифметикой.

Offset алгоритм: перевести anchor date в integer day ordinal выбранной системы; добавить `(point−anchor.point)` к time-of-day в наносекундах; Euclidean divmod на `hours_per_day×3600×10^9`; прибавить day delta к ordinal; выполнить обратную календарную проекцию. Period берётся из уже resolved periods по resulting hour. Start hour участвует в вычислении — исправляет пробел старой формулы current_tick % hours/day. Циклический календарь использует division по длине цикла и prefix sums внутри bounded pattern; не перебирать миллиарды лет. Gregorian — integer civil-date arithmetic, без datetime range limit. Arithmetic budgets/maximum authored collection sizes требуют policy World, не молчаливого truncation.

### 19.3. Карта дополнительных файлов

World calendar root по-прежнему только init. Новые leaf folders:

- `rules/periodic.py`: PeriodicCalendarRules, CalendarYearPattern, CalendarSpanOccurrence; init → 2 файла.
- `catalogs/spans.py`, `catalogs/weekdays.py`, `catalogs/seasons.py`, `catalogs/periods.py`: соответствующие Entry+Registry; init → 5.
- `dates/date.py`, `dates/clock.py`, `dates/anchor.py`: date union, clock time, start anchor; init → 4.
- В existing proposed `epochs/epoch.py` добавить epoch request/result; epochs/registry.py содержит WorldCalendarEpochRegistry(entries:tuple[WorldCalendarEpoch,...]) с unique key. Итого epochs с init = 3.
- projection/result.py содержит CalendarProjection/CalendarTimeOfDay; число файлов projection остаётся 4. Definitions/ruleCalendar.py импортирует rules/periodic, references и не application.

Public CalendarProjector использует эти данные; calendar pure algorithms при необходимости выделяются в `application/time/calendar/gregorian.py`, `periodic.py`, `projection.py`, `epochs.py` + init = 5. Это **заменяет** прежний `pure/calendarProjection.py`, а не создаёт второй projector. Arithmetic/conversions остаются в pure (2 модуля+init=3). Factory связывает выбранные fixed pure operations, не выбирает DAG workflow. Dispatch по конкретному календарному представлению внутри чистого преобразования — интерпретация данных одной операции, не вызов чужого CRUD/межоперационная orchestration.

## 20. Lifecycle payload proposal и границы реализации

### 20.1. Отделить координату от timeline binding

Runtime TimePoint сохраняет world/timeline. Initial world start ещё может не иметь active timeline: поэтому settings anchor до gameplay-start не должен требовать фиктивного timeline ID. Предлагаемый **CalendarOrigin(date:GregorianDate | RuleCalendarDate, time:CalendarClockTime)** хранится у World как определение даты при simulation coordinate zero. Gameplay start связывает origin с настоящим timeline; CalendarStartAnchor создаётся из origin + bound TimePoint. Таким образом §19 CalendarStartAnchor — runtime/resolved binding, а не обязательный authored field при создании мира. Файл dates/anchor.py содержит оба POJO, новых файлов не требуется.

**InitialTimeFacts(world_uid:EntityUid, seconds:I64, nanoseconds:Nano)** — proposed Time POJO в storage/initial.py; только seconds=0,nanoseconds=0 для новой root timeline. **BindInitialTime(world_uid:EntityUid, timeline_id:EntityUid, initial:InitialTimeFacts)** → **TimeClockState** — pure fixed operation `TimeLifecycle.bind_initial`, проверяет world equality; не создаёт timeline. **RebindBranchTime(source:StoredTimeState, target_timeline_id:EntityUid)** → **TimeClockState** — pure fixed operation того же класса; сохраняет world/coordinate, назначает timeline, не доказывает ancestry/разрешение branch. DAG/Snapshot supplies validated branch context. Ошибки world/same-target misuse — shared structural validation; authorization/provenance нельзя подменить pure type check.

Файлы: dataModel/time/storage/initial.py (storage теперь 4 с init), dataModel/time/operations/lifecycle.py (operations теперь 4 с init), application/time/changes/lifecycle.py (changes теперь 3 с init). Authoritative headless state должен храниться в domain storage под publication binding существующего GameplayStart, а не под выдуманным SectionStateRef. **PublicationTimeState(publication:WorldPublicationRef, state:TimeClockState)** — proposed read value в storage/state.py; only started publication, совпадение world/active timeline. Предлагаемый read-source state union закрыт: `StoredTimeState | PublicationTimeState`. Foreign lifecycle storage write capability к GameplayStart/branch остаётся integration proposal, не дополнение SnapshotApplyContext без согласования owner.

### 20.2. Почему не утверждается готовый restore/branch writer

Existing SectionStateRef привязан к SnapshotRef, тогда как GameplayStarted имеет snapshot_head=None; это реальная несовместимость, найденная по POJO. Initial storage нельзя реализовать простым переиспользованием TimeStateAppend. Owner Snapshot должен принять publication-bound domain state retention и atomic binding с GameplayStart/branch. Это точный prerequisite, а не причина заводить Time.commit или отдельный journal.

Restore existing timeline читает StoredTimeState и versioned World settings; новая ветка использует pure rebind и сохраняет publication-bound состояние в общем branch transaction. First accepted snapshot переносит ссылку на новый Time state обычным section writer. Прежние refs удерживаются existing holder/retention механизмом. Time не выбирает target snapshot, не авторизует путешествие во времени и не вычисляет последствия для персонажа.

## 21. Итог дополнительной детализации

§§19–20 заменяют placeholders только для явно предложенного periodic/Gregorian scope и конкретизируют root/branch data flow. Закрыты названия и поля date/clock/anchor/basic rules, folder/import direction и pure lifecycle inputs. **Не закрыты и не замаскированы**: универсальная выразительность календаря любого вида, World acceptance grammar/epoch conventions, publication-bound state lifecycle binding и actual chat turn-number API. Core Time реализовать сейчас всё ещё нельзя в рамках этого задания.

Предлагаемый порядок приёмки: core arithmetic/read/advance отдельно; затем calendar grammar и astronomical-year convention как явные design decisions; Snapshot owner принимает headless/branch state binding; затем согласовываются exact callers и migration. Проработка не требует полного DONE соседних доменов. Runtime tests/DDL/production ports отсутствуют намеренно; документальная конкретизация не равняется implementation или принятию пользователем.

## 22. Финальная consistency-проверка: зависимости и исправления proposal

ActionCore отложен пользователем: все ранние записи «actionCore OPEN» читаются как deferred integration requirement, а не незавершённая обязанность текущего Time design. Новые action request/result классы не вводятся. Повторный поиск action/turn contracts в backend/app не установил готового actionCore API; этот negative result не переоткрывает отложенную задачу.

### 22.1. Версия календаря — не текущая публикация

В §§15/19 предложенный CalendarVersionRef содержит publication, в которой принято определение. Эта публикация может быть старше capture; требование равенства этих refs было бы ошибочным. Исправленная семантика: **WorldCalendarRead** доказывает, что выбранная definition version действовала на запрошенном snapshot/publication. Proposed World-owned **ResolvedCalendarAt(source:WorldPublicationRef, version:CalendarVersionRef, settings:WorldTimeSettings, definition:GregorianCalendarDefinition | RuleCalendarDefinition, anchor:CalendarStartAnchor)**; source совпадает с current capture.publication. Для истории нужен отдельный **ResolvedHistoricalCalendarAt(source:WorldSnapshotRef, version:CalendarVersionRef, settings:WorldTimeSettings, definition:GregorianCalendarDefinition | RuleCalendarDefinition, anchor:CalendarStartAnchor)**. Version publication не обязана равняться source. World reader проверяет lineage/version validity, Time pure projection проверяет соответствие supplied source/capture и definition/anchor.

Эти POJO предлагаются в `dataModel/world/calendar/projection/request.py`. CalendarProjectionRequest заменяет расплющенные settings/calendar/version/anchor на `resolved:ResolvedCalendarAt | ResolvedHistoricalCalendarAt`, сохраняя point и capture. Current/historical variants обязаны совпадать; конкретный union перечислен. CalendarSourceMismatch из §15 требует расширения source полей на **WorldPublicationRef | WorldSnapshotRef** (ровно эти два POJO), не object. CalendarPointMismatch остаётся без изменения. Immutable version reuse не требует новой календарной версии на каждом advance.

### 22.2. Проверка схемы lifecycle

§20 fixed lifecycle operations — **pure binding helpers для внешнего lifecycle**, не дополнительные CRUD Time. StoredTimeState/PublicationTimeState — два способа ссылаться на состояние одного clock, не два независимых clocks. Snapshot metadata может наследовать state ref прошлой публикации; reader не требует ref.snapshot=current head. Он проверяет, что ref разрешён metadata/ancestry, а не извлекает latest напрямую.

InitialTimeFacts.seconds/nanoseconds в §20 фактически константны для root: exact schema заменить на **Literal[0] / Literal[0]**, не I64/Nano с неявным условием. Публичный clock reset из этих полей не следует. Branch rebind изменяет timeline identity только при утверждённом внешнем transition. Calendar epoch key не используется вместо timeline_id.

### 22.3. Номер хода: evidence и отделение от Time

В `0001_initial.sql` turns — «один ход игрока, создаётся только при успехе»; поля turn_id TEXT PK, session_id, player_input, game_tick INTEGER nullable, created_at. WorldSnapshotMetadata.turn_id — strict int>=1 и порядок цепочки. Ни TEXT UID, ни nullable game_tick не являются готовым public UI ordinal contract. Предложение владельцу chat/GEN: **DisplayedTurn(number:strict int>=0, source:WorldPublicationRef)**, получение из accepted game-turn semantics; не назначать самостоятельно count SQL rows или snapshot ordinal. Exact owner API остаётся integration OPEN; Time UI facts доступны независимо, но UI «время + номер хода» нельзя объявить интегрированным до принятия этого binding.

### 22.4. Принятые решения против непринимаемых автоматически proposals

Принято пользователем: time units/representation; World ownership; Gregorian+UTC default start/custom explicit start; hours/day default24; immutable history; положительная цена действий; versioned hours/day change с сохранением допустимой даты; actionCore deferred. Не принято автоматически: periodic-only grammar как предел календарей, astronomical year zero, конкретные file/API names, publication-bound initial storage protocol. Эти предложения требуют итоговой приёмки, но не реализации до неё.

Заявка «любой календарь через настройки» сохраняется целевой. Предложенная periodic grammar — конкретная проверяемая архитектурная основа, не повод объявить все календари покрытыми. Расширение grammar принадлежит World-defined POJO + pure Time algorithms и требует concrete typed alternatives; plugin registry/исполняемый пользовательский код/LLM fallback не добавляются. Неизвестный authored rule отвергается schema admission; UnsupportedCalendarRule применяется к известной version/capability, которую данный projector не поддерживает, не переносит неизвестный raw payload через строгий POJO.

### 22.5. Итоговые gates

| Gate | Статус / зависимость |
|---|---|
| Core Time proposal | Предъявлен: values, arithmetic, capture, preparation, section/storage boundaries; требуется пользовательская приёмка |
| Calendar proposal | Предъявлены concrete базовые POJO/проекция и ограничения; arbitrary grammar coverage и year convention требуют отдельного согласования |
| Snapshot integration | Contract proposal предъявлен; headless/branch state retention binding — внешний freeze prerequisite, не новый Time publisher |
| ActionCore | DEFERRED / OPEN по прямому указанию пользователя; не блокирует core proposal |
| UI turn contract | OPEN у chat/GEN; существующий TEXT UID не подменяет номер |
| Legacy audit | Независимое статическое ревью получено: [техдолг TIME-DEBT-01…06](./time-domain-review-debt.md). Generic writers, Regions и legacy требования требуют адресной миграции; lifecycle integration остаётся OPEN. Coverage limitations сохранены; runtime proofs не выполнялись |
| Production/runtime proofs | NOT STARTED, вне текущего scope |

Следующий допустимый шаг — пользовательская приёмка core proposal и адресные решения по calendar conventions/внешним lifecycle seams. Не создавать новые POJO, DDL, граф или runtime activation на основании этого документа. Повторные технические проверки не должны переоткрывать принятые решения или превращать отложенный actionCore в требование текущего scope.

## 23. N+1 календарей по существующему паттерну движка

**Нормативное уточнение пользователя; имеет приоритет над ограничивающими формулировками §§19/21/22.** Пользователь не принял periodic-only первую версию. PeriodicCalendarRules остаётся примером конкретного правила, а не единственным видом custom calendar и не новым owning фундаментом, который затем придётся заменять.

### Проверенные эталоны

- `dataModel/terrain/terrainRegistryEntry.py`: `system_terrain:RegistryKey[WorldTerrainRegistry]` задаёт world-authored identity; `fill_roles` ссылается на закрытый `TerrainFillRole`; `eligibility` содержит typed EligibilityRule. Пользовательские имена terrain не превращаются в enum members.
- `dataModel/terrain/eligibilityRule.py` + `enums/eligibilityOp.py`: данные rules задаются миром, `op:StrictEnumOnWire[EligibilityOp]` выбирает закрытую семантику GTE/LTE/IN_RANGE/FLAG; model validator проверяет применимость lo/hi. Это прямой пример «настраиваемые данные → engine enum → проверяемая семантика».
- `dataModel/registryKey.py` и `WorldTerrainRegistry`: nominal key + membership в owning registry + canonical entries. Нельзя копировать существующие legacy str/Any из соседних полей эталона; переиспользуется механизм, а не его технический долг.

### Применение к календарям

1. WorldCalendarRegistry — N+1 записи с `RegistryKey[WorldCalendarRegistry]`, произвольными названиями, описаниями и typed настройками. Gregorian — canonical запись/настройка, а не основание делить весь мир на Gregorian и единственный periodic custom.
2. Календарь содержит композицию concrete rule POJO. Каждое rule имеет discriminator `Literal[CalendarRuleKind.<member>]`, где CalendarRuleKind — закрытый enum движка. Payload каждого вида имеет собственные поля/constraints, а общий union перечисляет все поддерживаемые POJO. Ни `kind:str`, ни arbitrary payload, ни открытый runtime plugin/LLM interpretation не допускаются.
3. Месяцы, сезоны, периоды, эпохи — world entries/RegistryKey refs. Их тип/роль, где нужна алгоритмическая семантика, указывает на соответствующий закрытый enum. Enum не содержит month_1/«эльфийский календарь»/имена эпох.
4. Engine описывает конечные виды правил (их полный состав ещё предстоит freeze): структура счёта, повторение, условные вставки/исключения, реформа/anchor, нумерация эпох. Конкретные условия и величины задаются типизированными данными мира. Эти названия — категории для инвентаризации, **не принятый enum или готовый union**.
5. Time интерпретирует принятые rule POJO одной чистой операции projection/validation. World owns authored данные, registry membership/defaults/versioning. DAG явно предоставляет необходимые внешние факты; календарное правило не вызывает scheduler, Events, World CRUD или LLM.
6. Новая авторская запись, использующая существующие enum semantics, проходит import/roundtrip без изменений кода. Новая вычислительная семантика требует engine enum member + concrete POJO/validator/algorithm и явного version/capability gate. Нельзя обещать новую семантику только новым названием записи.

### Disposition прежнего calendar proposal

`GregorianCalendarDefinition | RuleCalendarDefinition(PeriodicCalendarRules)` как **полный публичный union — REDESIGN REQUIRED**, не целевой freeze. Periodic/Gregorian algorithms и date arithmetic сохраняются reuse candidates. Закрытие CalendarProjectionRequest/CalendarProjection зависит от полноценной композиционной схемы правил, а не выдаётся за выполненное §19. Core TimePoint/Duration/Interval/advance и Snapshot boundaries от этой смены не зависят.

Следующий calendar design gate: инвентаризировать существующие engine enums на применимость; предъявить полный closed CalendarRuleKind, concrete POJO union, правила совместимости/порядка и неоднозначности; проверить Gregorian, неравные месяцы, вставные дни/месяцы, непериодические исключения и реформы, эпоху от принятого события. Документировать каждый неподдержанный случай, не скрывая его behind unsupported payload. Этот gate — текущая документальная работа, не разрешение реализовывать периодическое ограничение раньше остальных.

## 24. T2-TZ — обязательный шаг полного календарного ТЗ

**Добавлен по прямому запросу пользователя. Статус TODO; calendar-dependent freeze BLOCKED.** Это не optional follow-up и не задача «уточнить при реализации». Полное ТЗ подготавливается разделом этого owning-плана: текущее ограничение «менять только Time-план» сохраняется. После отдельного разрешения нормативный текст можно перенести в `docs/tz_time.md`/World owning ТЗ без дублирования SoT; сейчас новые документы не создаются.

Цель: полностью закрыть вопрос N+1 календарей как world-authored данных поверх закрытых engine enums. Periodic-only MVP вместо этого результата запрещён. Предварительные §§15/19 не являются утверждённой схемой.

### Атомарные документальные подшаги

| ID | Prerequisites | Один проверяемый результат |
|---|---|---|
| TZ-1 | T0, §23 | Инвентарь требований и существующих registry/enum механизмов: reuse/new/deprecate с путями и evidence; перечень календарных сценариев и неопределённостей |
| TZ-2 | TZ-1 | Нормативная семантика календаря: composition/order правил, ordinal/anchor, эпохи/нумерация, реформы/исключения, неоднозначность и допустимые зависимости от явных фактов |
| TZ-3 | TZ-2 | Полный closed engine enum catalog: конкретные members, смысл, файл/owner, неизвестные значения/version compatibility; ни одного «категории уточним позже» |
| TZ-4 | TZ-3 | Exact World-owned N+1 POJO catalog: каждое поле/тип/required/null/default/constraints/refs, concrete discriminated unions, SCHEMA_ID/wire/serialization/version; explicit Gregorian canonical data |
| TZ-5 | TZ-4 | Exact публичный projection/validation API: Input/Output/Error, producer/consumer, coherent source/version, pure semantics, обратное преобразование и ambiguity policy; CRUD requirements World без присвоения их Time |
| TZ-6 | TZ-5 | Единая актуальная class/factory/file/import map с counts; старые альтернативные карты помечены SUPERSEDED у места использования, без второго active определения |
| TZ-7 | TZ-6 | Документальная verification matrix и соответствие правилам; zero unresolved calendar-local contracts; пакет пользовательской приёмки |

### Обязательные критерии завершения

- Любые новые имена/записи, использующие поддержанные engine semantics, задаются данными мира и проходят общий POJO/REF-W механизм; новый авторский календарь не требует нового enum member.
- Все вычислительные виды правил — закрытые enum + concrete POJO; нет raw payload, Any/object/dict, произвольных имён callbacks, пользовательского executable code или скрытого LLM fallback.
- Схема покрывает согласованные виды календарных правил, включая периодические и непериодические конструкции. Граница выразительности описана явно; непокрытый пользовательский requirement блокирует DONE до решения пользователя, а не автоматически переносится «на потом».
- Exact positive/negative примеры: Gregorian вековые leap exceptions; 10/30-часовые сутки; неодинаковые месяцы; вставные дни вне недели; вставной месяц; непериодическая датированная реформа; эпоха от принятого события; большие/отрицательные координаты; неизвестный enum/registry ref; конфликт правил; отсутствующая custom start; hours/day change с недопустимым текущим часом.
- Каждому примеру предъявить input settings, ожидаемую дату/ошибку, правила validation и основания детерминизма; отдельно roundtrip и неоднозначные даты. Это документальные доказательства; runtime tests только после разрешения кода.
- Нельзя скрыто ограничить range datetime или пересчитывать годы циклом до заданного момента; описать алгоритмы, overflow и complexity/budgets без изменения точности.
- World owns settings/versions, Time — pure semantics, DAG — передача фактов/операций, Snapshot — acceptance. Events/Actions/Physics не импортируются внутрь calendar projector ради lookup.
- Полностью закрыты calendar-local enum/POJO/API/files; внешние deferred actionCore контракты не мешают этому DoD. Snapshot integration может оставаться отдельным gate, но требуемый от него exact seam обязан быть сформулирован.

DONE только после документального review и явной пользовательской приёмки ТЗ. До этого никакие calendar POJO/tests/fixtures/DDL не реализуются. Даже DONE не разрешает production cutover.

## 25. T-RULE — аудит соответствия плана правилам агента

### Проверенные источники и текущий результат

Проверены применимые правила; ссылки ниже — нормативные источники, а не декларация PASS будущего кода. Root AGENTS.md ранее не найден; это не отменяет `.cursor/rules`. При следующем freeze повторить discovery вложенных инструкций для фактически выбранных paths.

| Правило | Проверка плана / verdict |
|---|---|
| [code-gates](../rules/code-gates.mdc) | Документальный scope соблюдён. **BLOCKED для реализации:** календарные enum/POJO/API не frozen; новый T2-TZ закрывает обязательный gate. Нельзя считать весь план compliant для исполнения |
| [contract-creation](../rules/contract-creation.mdc), [type-kind-str-fields](../rules/type-kind-str-fields.mdc) | RegistryKey/closed enum pattern принят; **OPEN** exact calendar enum и unions. В TZ-3/4 обязательна инвентаризация reuse и всех prose-str исключений |
| [dataModel-no-hardcode](../rules/dataModel-no-hardcode.mdc), [pojo-world-row-wire](../rules/pojo-world-row-wire.mdc), [json-validation-architecture](../rules/json-validation-architecture.mdc) | World POJO defaults, общий resolver/WorldSlice закреплены. **OPEN** exact replacement wire/schema для удаляемого calendar dict, не выбирать при кодировании |
| [runtime-world-edit-policy](../rules/runtime-world-edit-policy.mdc) | Есть начальный раздел, missing ≠ invalid, preview без writes, общий diagnostic path. Exact reason/action/log binding ещё integration gate, не готовый runtime proof |
| [layer-boundaries](../rules/layer-boundaries.mdc), [class-size-limit](../rules/class-size-limit.mdc) | Ownership и запрет скрытого CRUD соблюдены на уровне намерения. Требуется финальная проверка каждого pipeline/helper/error path по consolidated map. Размеры production classes пока неприменимы: код не создавался |
| [folder-composition](../rules/folder-composition.mdc) | Предложенные leaf folders имеют до 5 файлов с init. **OPEN** единая пересчитанная карта после §23 redesign; исторические counts не доказывают final compliance |
| [documentation-layout](../rules/documentation-layout.mdc) | PASS текущей правки: изменён только owning plan; ТЗ-шаг пока пишет сюда по прямому ограничению пользователя |
| [legacy-folder](../rules/legacy-folder.mdc), [refactor-safety](../rules/refactor-safety.mdc) | **PARTIAL:** исследованные writers/callers есть, но не все строки ledger имеют clickable definition/caller links и complete disposition. До T7 это обязательно исправить; global negative search не substitute |
| [dag-generator-interface](../rules/dag-generator-interface.mdc), [frozen-node-contracts](../rules/frozen-node-contracts.mdc) | Конкретные ноды/родство не менялись. Добавляется явный target HTTP path ниже; без принятых GEN bindings runtime activation BLOCKED |
| [project-context](../rules/project-context.mdc), [database-migrations](../rules/database-migrations.mdc) | Код/DDL/server/commits не затронуты. Future DDL только 0001_initial.sql + model sync; новые migration files не предлагать |

### Исправления, внесённые этим аудитом

1. T2-TZ стал обязательным predecessor календарной части T3 и T-RULE; больше нельзя перейти от списка идей к POJO реализации.
2. Обязательный target внешнего API: **app/api → engine DAG → согласованная нода → public Time operation**. HTTP route не вызывает writer/prepare+commit самостоятельно. DAG не делает HTTP self-call. API route paths/NodeIds не вводятся до совместной GEN-приёмки. После cutover прежний обход удаляется, а не сохраняется debug fallback.
3. Подготовка advance описана как fixed pipeline. Для соответствия принятому именованию public pipelines предлагается freeze rename: **ITimeAdvancePipeline / TimeAdvancePipeline.prepare_advance(PrepareAdvance)**, файл `application/time/changes/advancePipeline.py`; прежний `TimeAdvancePreparer.prepare` и prepareAdvance.py — **SUPERSEDED proposal names**, не production rename. Factory `make_time_advance_pipeline()->ITimeAdvancePipeline`. Pure arithmetic/reads не переименовывать Pipeline ради симметрии. Остальные I/O/E сохраняются.
4. Все карты §§6/15/19 читаются как история proposal до TZ-6: никакой код не должен выбирать между ними. TZ-6 обязан заменить их одной active map и снабдить point-of-use supersession, иначе T-RULE FAIL.

### DoD окончательной проверки всего плана

Reviewer читает весь план, не только последний appendix. Для каждого шага: prerequisite graph без циклов; один атомарный результат; exact ownership/file/signature; POJO/enum freeze; legacy definition+caller links+disposition+cutover gate; folder counts; отсутствие hidden orchestration; evidence/status. Отдельно проверяет сохранение принятых решений пользователя и отсутствие их повторного OPEN. По каждому правилу — PASS/FAIL/NOT APPLICABLE с обоснованием; для каждой FAIL — исправление и повторная проверка. Внешний deferred actionCore обозначается DEFERRED, не FAIL core Time.

**Текущий честный verdict: документальный scope соблюдён, полное соответствие плана execution-gates пока НЕ достигнуто.** Добавление этого checklist не исправляет автоматически findings. Calendar freeze, consolidated map и полный linked legacy inventory блокируют T7/implementation соответствующего scope. Нельзя объявить «план полностью соответствует правилам» до их фактического закрытия. Review PASS не заменяет пользовательскую приёмку.

## 26. Core сначала, реализация техдолга после core

**Принято пользователем.** Этот раздел уточняет зависимости предыдущих gates; не отменяет исследование legacy и не объявляет production cutover выполненным.

| Этап | Обязательный prerequisite | Что не обязано быть реализовано заранее |
|---|---|---|
| Core design / приёмка | Exact используемые Time POJO/enum/API, ownership/file map, известные legacy seams/disposition; T2-TZ для календарной части | Перевод legacy consumers, удаление World.calendar dict/increment_tick, обновление старых per-tick правил |
| Изолированная реализация core — только после отдельного разрешения | Принятый core plan и contracts; тестовые bindings не выдают фиктивную готовность production | ActionCore и полная миграция существующих callers; полного DONE Physics/GEN/Snapshot не требуется |
| Реализация migration/debt | Готовый проверенный core + принятые replacement bindings | Не требует повторно реализовывать core; каждый consumer мигрируется отдельным атомарным срезом |
| Runtime integration / cutover | Нужные Snapshot/GEN contracts, атомарность, миграция writers и consumers затронутого flow, удаление обходов, tests | Несвязанный техдолг других flows не блокирует автоматически |

**Что относится к отложенному техдолгу:** удаление raw World.calendar и его import/update/export bypass; замена increment_tick; migration Regions elapsed_ticks/last_eval_tick; перевод legacy needs/rest/travel/weather rates; отключение прежних routes/callers после готовности согласованной замены. До их среза legacy остаётся существующим поведением и явно помечается unmigrated, но новый core не зависит от raw dict или прямого commit.

**Что не переносится под видом техдолга:** неизвестные поля/enum/API core; смешение ответственности; отсутствующая валидация настроек; неподтверждённая точность; скрытый writer/dispatcher в новом core; fake Snapshot refs; неутверждённая календарная grammar, которую использует реализуемый календарный модуль. Эти gaps закрываются до соответствующего core кода.

Linked legacy inventory — документальная обязанность до приёмки плана, а не требование предварительно переписать legacy. T-RULE проверяет core и migration readiness раздельно: допустим verdict **CORE READY / MIGRATION PENDING**, когда core contract gates действительно закрыты. Сейчас такого verdict ещё нет из-за T2-TZ/consolidated-map gaps. Нельзя запрещать core только потому, что migration ещё не выполнена; нельзя включать production flow с оставшимся обходом только потому, что core готов.
