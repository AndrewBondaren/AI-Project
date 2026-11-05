# Time — owning architectural proposal

Исторический статус документальной итерации до разрешения разработки: SPECIFICATION CANDIDATE / USER REVIEW PENDING (§§29–35); accepted freeze и внешние integration gates не закрыты. Не CODE-READY, не пользовательская приёмка всего proposal. Только документы; production POJO, DDL, DAG nodes, publication и cutover запрещены текущим scope.

## Выполнение изолированного core (2026-11-03)

### Ревью политики данных Time / World settings (2026-11-05)

Основание — [error-contracts-1, O05 и EC-11](error-contracts-1.md), [общая политика данных](../../docs/tz_runtime_world_edit_policy.md) и уточнение мастера о двух режимах. Это ревью текущего поведения; миграция диагностики и подключение runtime resolver предстоят.

| Вход | validate | runtime — целевой контракт |
|---|---|---|
| Допустимое значение или отсутствующее поле со штатным default | Принять по POJO | То же значение. Например, отсутствующие hours_per_day → 24 и from_minute → 0 без WarningError. |
| Явное недопустимое значение | Вернуть типизированную диагностику с кодом и путём | Общая граница пишет WarningError и применяет объявленный для этого случая fallback. Например, для ошибочной минуты нужно явно разрешить fallback 0; один DefaultWhenMissing такого разрешения не даёт. |
| У обязательного поля или ссылки нет допустимого fallback | Вернуть точную причину | Записать WarningError и оставить зависимую операцию unresolved. Для авторского календаря требуется явный origin. |

**Реализовано после ревью.** Для полного WorldTimeSettings публичная граница resolve_world_time_settings использует ResolveContext, общий resolver и CalendarValidator. Явные ошибки hours_per_day/from_minute в runtime разрешены в POJO defaults (24/0), с WarningError; validate возвращает структурированные ошибки. Остальные поля требуют валидного значения. После замены выполняется полная семантическая проверка. CalendarFieldIssue содержит enum-код и ValidatedFieldPath; независимые календарные проверки используют ValidatorAggregationHelper. Проверены парные входы и число событий. Подключение к production binding остаётся отдельным этапом.

Проверка 2026-11-05: 29 тестов Time и 14 адресных тестов jsonValidation resolve прошли; Pyright по Time, World settings и изменённому общему resolver — 0 ошибок и предупреждений.

**Исходные находки ревью до исправления.**

1. Подтверждён сбой validate при неизвестном selected: CalendarValidator конструирует базовый FieldPathError и выбрасывает TypeError вместо CalendarInvalid. Та же конструкция есть в WorldCalendarResolver и preparation/shared/candidate. Потребитель prepare_calendar_update индексирует path как tuple, хотя теперь это ValidatedFieldPath. Нужны конкретная доменная ошибка с enum-кодом и проверяемым путём по контракту общего carrier.
2. CalendarValidator прекращает проверку на первом InvalidCalendar. Для validate требуется накопить независимые ошибки, например в двух календарях. Производные проверки следует пропускать, если для них не разрешены исходные поля.
3. Для настроек Time найден общий sink WarningError в jsonValidation, но не подтверждена связка resolver → зарегистрированная причина → fallback → итоговый WorldTimeSettings. В текущих POJO defaults описывают отсутствие поля. До реализации нужна полевая матрица допустимых замен для явных ошибок. Проверять парой входов в обоих режимах: код/путь, фактическое значение и ровно одно runtime-событие. Чистая арифметика и prepare_advance продолжают возвращать свои доменные исходы.

**Актуальный итог ревью.** Изолированные T3-A, T3-C, подготовка T4 и операции World settings проверены по §§10–11, 29–33, 36 и 38. Все 25 тестов Time прошли. Pyright по dataModel/time, dataModel/world, application/time и application/worldData/timeSettings — 0 ошибок и предупреждений.

Time предоставляет арифметику, календарную валидацию, project/resolve и чистый prepare_advance с типизированными результатами и отказами. World владеет настройками и их подготовкой. Чтение делегируется закреплённым source ports. Проверка импортов не выявила прямых зависимостей этих пакетов от DAG engine, БД, логгера, Physics или actionCore.

Для §32 обе операции project/resolve сверены с независимым посуточным перечислением в годах −25…25 при сочетании YEAR_RANGE, модулей 3 и 5 и RESET_AT_YEAR. Проверены оба лимита бюджета, неизвестный дискриминатор правила на JSON-входе и CalendarTimeOverflow при выходе на 1 нс за каждую границу TimePoint.

Политика STANDARD для суток в 1–3 часа согласована и реализована согласно таблице в ТЗ Time. PeriodEntry.from_minute задаёт минуту начала с default 0 при отсутствии. Открыты внешние контракты §§45–47. Приёмка изолированного core не закрывает T5: production read, атомарное принятие Time и effects, retry/restore/branch, emitter и cutover требуют отдельных интеграционных проверок.

**Уточнение T5 от 2026-11-05.** DAG собирает Time proposal и последствия того же действия от общей исходной публикации в один `PatchSet` и вызывает публичный `IWorldSnapshotApply.apply`. Snapshot владеет общей транзакцией, записью секций и CAS. Отказ секции или конфликт головы откатывает всю группу. Для обычного продвижения передача назначенной публикации через `SnapshotApplyContext.next_publication` уже реализована в Snapshot. По Time остаются интеграция секции и проверка атомарности на доменных таблицах (§44). Порядок записи и проверки внешних ключей относится к реализации этой транзакции.

**Решение о частях суток, 2026-11-05.** Части суток принадлежат календарю World и настраиваются как N+1 записи существующего CalendarPeriodRegistry. Для обычного 24-часового мира принят земной набор по умолчанию. Сезонное изменение соотношения дня и ночи по дню внутри сезона выделено в будущее расширение. Действующий projector использует фиксированные from_hour. [ТЗ Time](../../docs/tz_time.md#части-суток)

Отложенный шаг: реализовать настраиваемую мастером мира зависимость границ периодов от дня внутри сезона. Приёмка — два мира могут задать разное поведение на одной календарной дате; историческая проекция использует настройку своей версии. До реализации согласовать типизированный контракт World и правила вычисления Time.

<details><summary>История проверок отдельных срезов</summary>

По запросу мастера реализованы T3-A, pure T3-C и подготовка T4. Действующее ТЗ — [tz_time.md](../../docs/tz_time.md). Ранние запреты кода относятся к документальной итерации. T2-TZ синхронизирован для шкалы, авторских календарей, владения World и публичных операций. Ordinal 0 — первый день астрономического года 0, modulo использует year − offset. Для STANDARD приняты четверти суток при H ≥ 4; прежний единственный Day в §33 заменён.
Прямые API (§§10–11, 20, 29–30, 36, 38) проверены для арифметики, advance, bind/rebind, календарной валидации, project/resolve, World resolver и восьми операций подготовки настроек. Time/World readers делегируют закреплённым source ports. Фабрики соединяют зависимости; Time готовит только proposal, World проверяет candidate, выбор операций остаётся у DAG.
Проверки: 14 unittest ядра, compileall, Pyright по четырём пакетам (0 ошибок). Отдельно 7 существующих тестов canonical encoding. Чтение проверено с тестовыми источниками. T5/интеграция ожидают контрактов §45; registration и emitter §47 остаются интеграционными. prepare_initial проверен для AUTHORED и STANDARD: русские подписи, понедельник, обычные сезоны по месяцам и четыре периода. Перевод по языку пользователя вне Time. Для STANDARD с 1–3 часами политика отдельно OPEN (SettingsInvalid).

T4, дополнение §§20/34: реализован `PublicationTimeState(publication, state)`. Headless publication и унаследованный head покрыты тестом, как и отказы для другого мира, неактивной ветки и незапущенного gameplay. 15 тестов Time прошли, Pyright на dataModel/time и application/time без ошибок. Production-чтение под CommitReadScope остаётся открытым.

T5, состояние на 2026-11-03 до реализации assigned publication: передача publication обработчику была открыта. Актуальный статус обычного продвижения приведён выше в уточнении от 2026-11-05. Контракт ветвления рассматривается отдельно в §34.

T3-C, §29.3: календарный индекс рассчитывает период отдельно в каждой области YEAR_RANGE. Проверена проекция разовой вставки с modulus 10^30 при бюджете в три класса годов; при двух классах возвращается CalendarBudgetExceeded. Прогон Time: 16 тестов, Pyright для application/time и dataModel/time без ошибок.

T3-C, матрица §32: проверена повторяющаяся дата при реформе календаря. На двух заданных версиях World resolver и Time projector возвращают разные точные координаты для одной даты и времени; исторический capture с текущей версией даёт CalendarSourceMismatch. Проверка изолирована от записи Snapshot. Все 17 тестов Time прошли.

T3-C, матрица §32: проверены обе границы для нестандартной длины суток с ненулевым начальным часом. Через prepare_initial → resolve_at → project → resolve прибавление одной секунды даёт следующий день 00:00:00 при H=10 и тот же день 24:00:00 при H=30. Обратное преобразование в обоих случаях возвращает точную координату +1 s. Все 18 тестов Time прошли.

T3-C, §32: конфликт REMOVE_SPAN/REPLACE_SPAN после удаления цели проверен через CalendarValidator и World prepare_calendar_update. Исправлен пропущенный сегмент definition в диагностике. Оба отказа указывают на конфликтующее правило, исходные настройки сохранены. Прошли 19 тестов Time, Pyright по application/time и worldData/timeSettings без ошибок.

T3-C / World preparation, §32: сокращение авторских суток с 24 до 12 часов проверено при 18:00:00.123456789. Без замены возвращён SettingsAnchorRequired; повтор с явным origin подготовил изменение на той же физической координате с сохранением наносекунд. Исходная версия календаря сохранена. Прошли 20 тестов Time.

T2-TZ / §32: на входе PrepareInitialSettings проверены отсутствующая и явно null дата авторского календаря при переданном captured_utc. Обе формы отклонены с диагностикой поля anchor.origin.date. После восстановления явной даты тот же запрос проходит prepare_initial и сохраняет авторские настройки. Прошёл 21 тест Time.

T3-C, §32: REPLACE_SPAN с YEAR_RANGE [17,17] удлиняет 30-дневный месяц на один день. Через resolve/project проверены точная координата 31-го дня, переход на первый день года 18 и CalendarInvalid для 31-го дня в годах 16 и 18. Прошли 22 теста Time.

</details>

<details><summary>Изменённые файлы ядра</summary>

Документы: `docs/tz_time.md`, `docs/project_data_storage_tz.md`, `.cursor/plans/time-domain.md`. В перечисленных пакетах добавлены также файлы `__init__.py`.

- `backend/app/dataModel/time/` — `changes/advance.py`, `operations/arithmetic.py`, `operations/conversion.py`, `operations/lifecycle.py`, `reads/capture.py`, `reads/request.py`, `results/errors.py`, `storage/initial.py`, `storage/state.py`, `values/duration.py`, `values/interval.py`, `values/point.py`.
- `backend/app/application/time/` — `calendar/ordinal.py`, `calendar/projection.py`, `calendar/rules.py`, `calendar/validation.py`, `changes/advancePipelineOpenPipeline.py`, `changes/lifecycle.py`, `composition/factory.py`, `pure/arithmetic.py`, `pure/conversions.py`, `reads/reader.py`, `reads/sourcePort.py`.
- `backend/app/dataModel/world/` — `calendar/catalogs/periods.py`, `calendar/catalogs/seasons.py`, `calendar/catalogs/spans.py`, `calendar/catalogs/weekdays.py`, `calendar/dates/anchor.py`, `calendar/dates/clock.py`, `calendar/dates/date.py`, `calendar/definitions/definition.py`, `calendar/definitions/registry.py`, `calendar/enums/rules.py`, `calendar/epochs/epoch.py`, `calendar/epochs/registry.py`, `calendar/projection/errors.py`, `calendar/projection/request.py`, `calendar/projection/result.py`, `calendar/rules/edits.py`, `calendar/rules/predicates.py`, `calendar/scalars.py`, `settings/standard/gregorian.py`, `settings/timeOperations/changes.py`, `settings/timeOperations/initial.py`, `settings/timeOperations/read.py`, `settings/timeOperations/results.py`, `settings/timeSettings.py`.
- `backend/app/application/worldData/timeSettings/` — `factory.py`, `preparation/calendarPipelineOpenPipeline.py`, `preparation/epochPipelineOpenPipeline.py`, `preparation/hoursPipelineOpenPipeline.py`, `preparation/initialPipelineOpenPipeline.py`, `preparation/shared/candidate.py`, `reader.py`, `sourcePort.py`.
- `backend/tests/time/` — `test_time_core.py`.

</details>

## Актуальность разделов и границы готовности

Принятые решения — §1 и §26. Календарная архитектура — N+1 данные мира над закрытыми engine enums (§23); обязательный шаг ТЗ — T2-TZ (§24), его кандидат предъявлен в §§29–33; статус приёмки — §35. §§15 и 19 — исторические варианты календарной схемы, **SUPERSEDED как целевой enum/POJO/API freeze**; их алгоритмические идеи можно переиспользовать после T2-TZ. Нельзя реализовывать старый Gregorian/Periodic union по этим разделам.

Core value/read/advance contracts — §§10–11; write/lifecycle детализация — §§18/20/22 с указанными OPEN. Обязательное logging-integration требование к future runtime — §47 (TIME-LOG); пользователь согласовал контракт событий и маршрут в §47.1–2. Публичная подготовка: **ITimeAdvancePipelineOpenPipeline / TimeAdvancePipelineOpenPipeline.prepare_advance**. Единая candidate file map — §31 с дополнением storage §34; исторические counts не являются разрешением реализации.

Порядок: core design/freeze → отдельно разрешённая изолированная реализация core → migration/debt → production cutover. ActionCore DEFERRED. Реализация техдолга не блокирует core; документальная инвентаризация обязательна. Текущий verdict: **SPECIFICATION CANDIDATE, NOT CODE-READY** до пользовательской приёмки и закрытия требуемых integration gates; не из-за неисполненного техдолга. Runtime proofs не выполнялись. Итоговый rule audit — §25; его наличие не означает PASS.

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
- Явное требование пользователя: настройки времени и календарей имеют публичные типизированные контракты и используются через DAG. Owner этих операций — World; Time не присваивает settings CRUD. Цепочка внешнего доступа: app/api → engine DAG → согласованная нода → публичная операция World. Это обязательная часть settings contract freeze, не только Time projection API (§28).
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
| Нет exact POJO / public API | Core proposal добавлен в §§10–11/18; календарные contracts остаются BLOCKED до T2-TZ |
| Calendar ownership можно ошибочно перенести в Time | World owns definitions/CRUD; Time owns pure projection. Зависимости разложены без импорта application из dataModel |
| `SeasonKey` содержит только winter/spring/summer/autumn | Нельзя использовать его как закрытый enum произвольных сезонов N+1. Foreign World calendar keys и Climate mapping OPEN; существующий enum не менять этим планом |
| Историческое «сессия/current_tick=turn_id» конфликтует с решениями | World owner, раздельные время/номер хода и обычный календарь при отсутствии настройки приняты; точная миграция legacy поля и initialization binding ещё OPEN |
| «Любой календарь» не обеспечен схемой старого ТЗ | Expressiveness gate: неодинаковые месяцы, вставные дни, собственные сутки и эпохи; недостаточные настройки возвращают unresolved, а не выдуманную дату |

## 6. Предлагаемое размещение архитектуры, классов и POJO

Все пути ниже — **проект**, не существующие реализации и не разрешение на код. Архитектура и execution map пока хранятся только в этом owning-плане. Будущее доменное ТЗ `docs/tz_time.md` — отдельное предложение после приёмки; сейчас его не создавать. Не создавать документы в папках production.

**Статус карты:** core строки актуализированы по §§10/18/20; календарные строки ниже — SUPERSEDED навигация, целевые пути уточняет T2-TZ/TZ-6. Не использовать её как единый final file freeze.

Корень путей — `backend/app/`. `dataModel/time`, `dataModel/world`, `application/time` на момент проверки отсутствуют. World calendar paths ниже требуют согласования владельца World; отсутствие папки не даёт Time ownership календаря.

| Путь | Классы / ответственность | Imports |
|---|---|---|
| `dataModel/time/values/point.py` | TimePoint: шкала world/timeline + точная координата; не календарная дата | identity/uid; собственные scalar types |
| `dataModel/time/values/duration.py` | TimeDuration: неотрицательная длительность; принятые seconds+nanos, proposed bounds §10 | Только validation primitives |
| `dataModel/time/values/interval.py` | TimeInterval: start/end одной шкалы, end>=start | point, duration |
| `dataModel/time/reads/capture.py` | TimeCapture/HistoricalTimeCapture: согласованные clock facts + provenance; не набор независимых latest reads | values, существующие WorldPublicationRef/WorldSnapshotRef |
| `dataModel/time/reads/request.py` | CurrentTimeRead, HistoricalTimeRead — отдельные requests | WorldPublicationRef, WorldSnapshotRef |
| `dataModel/time/changes/advance.py` | PrepareAdvance, TimeAdvanceProposal: candidate, не accepted clock | values, reads/capture, EntityUid |
| `dataModel/time/results/errors.py` | Конкретные core refusal POJO перечислены в §10; mapping общей диагностики OPEN | Только dataModel; не exceptions из application |
| `dataModel/world/calendar/definition.py` | WorldCalendarDefinition: настройки/описание, не Time entity | World keys/rules; не application/time |
| `dataModel/world/calendar/epoch.py` | WorldCalendarEpoch: world-owned именованная эпоха, anchor | calendar keys, TimePoint; semantics anchor OPEN |
| `dataModel/world/calendar/registry.py` | WorldCalendarRegistry: N+1 definitions | definition; existing RegistryKey mechanism |
| `dataModel/world/calendar/projection.py` | CalendarProjectionRequest/CalendarProjection: перенос определений и результата без повторной схемы календаря в Time | definition, epoch, TimePoint; exact result OPEN |
| `dataModel/world/settings/timeSettings.py` | WorldTimeSettings: world-owned часы в сутках; proposed hours_per_day — DefaultWhenMissing positive strict integer, default 24. Единственный источник поля; calendar definitions не дублируют настройку | annotationPolicy, constrained primitives; точный SCHEMA_ID/wire binding OPEN |
| `application/time/pure/arithmetic.py` | TimeArithmetic: add/elapsed/compare/interval, без clock read | dataModel/time/values |
| `application/time/pure/conversions.py` | TimeConversions: seconds/hours; стоимость и число раундов вычисляет actionCore/Combat, не Time | dataModel/time; никаких Combat imports |
| `application/time/pure/calendarProjection.py` | CalendarProjector: чистый алгоритм по валидированному world definition | dataModel/world/calendar + time/values |
| `application/time/reads/reader.py` | TimeReader: отдельные current/historical reads согласованного источника | capture/request, внедрённый read port |
| `application/time/reads/sourcePort.py` | ITimeReadSource: coherent source seam, без собственного store/publication | exact request/capture; source consistency contract OPEN |
| `application/time/changes/advancePipelineOpenPipeline.py` | ITimeAdvancePipelineOpenPipeline / TimeAdvancePipelineOpenPipeline: фиксированный pipeline validation → proposal, без чужого CRUD/commit | time POJO, pure arithmetic |
| `application/time/integration/snapshotHandler.py` | TimeSectionHandler: Time validation/append в чужом commit scope (§10 TimeAdvanceSection) | DomainSectionHandler + TimeAdvanceSection (§10); registry/receipt binding OPEN (§18) |
| `application/time/composition/factory.py` | make_time_reader(source), make_time_advance_pipeline(); явный DI, не service locator/dispatcher | Только указанные классы/ports |

**Исторический count первоначальной карты, не итоговый freeze:** число непосредственных файлов (с планируемым `__init__.py`): time/values 4; reads POJO 3; changes POJO 2; results 2; world/calendar 5; world/settings 2; application/time/pure 4; reads 3; changes 2; integration 2; composition 2. Новые промежуточные package folders — по одному `__init__.py`. Ни одна предложенная папка не превышает 5; при уточнении errors/rules/section schemas пересчитать до добавления, не наполнять эти папки без проверки.

Направление: `DAG → public application operations → dataModel`; `Physics → dataModel/time` только через подготовленный Input. `dataModel/world/calendar → dataModel/time/values` допустимо для anchors; обратного импорта из time/values в World calendar нет. Calendar projection request размещён у World именно для предотвращения цикла. TimeCapture не содержит calendar settings/ref: DAG получает их отдельным World read на той же публикации. Это исключает обратный импорт Time → World из capture. `Snapshot → TimeSectionHandler` через binding, handler не вызывает Snapshot.apply. World CRUD вызывает чистую validation явно через согласованный binding, без Time-вызова World CRUD. DAG composition POJO живут в `dataModel/engine/nodes/<group>/`, переиспользуют вложенные domain POJO и не дублируют поля.

DB rows остаются в `db/models/`, DDL в `db/migrations/0001_initial.sql`; это storage representation, не публичный POJO. Новая persistence схема сейчас не выбрана. Mapping/normalization не дублируются в DAG, routes и repositories. Runtime authoritative time должен читаться из принятого publication-bound или snapshot-bound состояния (§20), а не независимо из stale World row.

Calendar legacy removal gate: заменить `World.calendar: dict`, его raw consumers и generic import/export/update bypass на owning POJO + validated boundary; согласовать replacement SQL/wire representation и удалить старое поле/колонку либо заменить их типизированной проекцией в едином cutover. Старый произвольный JSON blob не сохраняется как второй authoritative источник. Физический JSON encoding нового POJO, если выбран World owner, не означает сохранение legacy dict-контракта. Проверить callers, WorldSlice, bundle roundtrip и version history до удаления; не добавлять dual-read/error fallback на старый dict. Это обязательный будущий этап, не выполненная миграция.

### POJO settings integration gate

Evidence: `WorldClimateScalars` показывает SCHEMA_ID/field policies/POJO wire helpers; `WorldEnvironmentSettings` — world-owned typed nested settings; `application/jsonValidation/worldSlices.py` — существующий WorldSlice registry. В поиске calendar/hours_per_day в dataModel и этом registry готовый settings contract не найден; legacy dict не признан достаточным. Это references механизма, не разрешение копировать legacy Any, error fallbacks или закрытый набор сезонов.

До реализации World owner должен принять exact WorldSlice binding calendar/settings, policy каждого поля и migration старого `calendar.hours_per_day` в единственный source. Single JSON slice использует штатный registry mapping; если выбраны несколько SQL-колонок — wire keys выводятся из POJO и проверяются startup column assertion. Не заводить второй список wire keys в Time/facade/DAG. SCHEMA_ID, RegistryKey для N+1 refs и typed diagnostics используют существующие механизмы.

Default 24 применяется при missing hours_per_day; 0/negative/неверный тип не заменяются 24. Предложенный strict positive integer ещё требует freeze exact schema; null не трактуется как missing без явной принятой policy. Обычный calendar default также определяется owning POJO/canonical factory, не literals в проекторе. Только для стандартного григорианского календаря отсутствующий start_date заполняется из однократно захваченных текущих даты/времени UTC+00:00 на initialization boundary; пользовательский календарь требует явной стартовой даты; pure POJO/Time не вызывают now(). Настройки presentation, если вводятся, тоже должны иметь свой owning POJO, а не kwargs/dict в Time.

Каскад настроек автоматически не вводится. Если World owner объявит наследование, использовать существующие Cascade/FieldRef/extend и проверки по `cascade-pojo.mdc`; локальные or-цепочки запрещены. Проверки перед будущим cutover: missing→24, invalid→unresolved, patch omission сохраняет предыдущее значение, import/runtime используют одинаковые ограничения, preview без writes, source revision согласована с capture. Это будущие proofs, не выполненные тесты.

## 7. Результат проверки POJO и applicability

Production Time POJO по поиску class Time/Duration/Calendar/Epoch в `dataModel`/`ids` не установлены. Проверены reuse candidates: `EntityUid`, `WorldPublicationRef`, `WorldSnapshotRef`; calendar/combat storage остаётся нетипизированным legacy. Это ограниченное evidence, не доказательство отсутствия всех возможных aliases.

Карта §6 уточнена предложенными схемами §10. Для закрытия API freeze по каждому контракту проверяются: поля/strict constraints; конкретные success/error POJO и полностью перечисленные unions; caller requirement; publication/source/timeline consistency; idempotency; legacy disposition. Foreign types OPEN блокируют только зависимые операции/integration; actionCore DEFERRED не блокирует core. Заглушки Any/object/dict/BaseModel запрещены. Свободное описание — текст, но calendar IDs/keys/rule kinds не свободные строки. Структурная validation находится у POJO, чистая временная семантика — Time; IO/current revision checks — application read/acceptance boundary.

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
| T3-A Core values и arithmetic API | T1 | Exact point/duration/interval/conversions/errors и core file/import map; независимо от календарной grammar |
| T3-C Calendar projection API | T2-TZ; T3-A | Exact projection/validation I/O/E и calendar file/import map |
| T4 Coherent reads и preparation | T3-A; Snapshot publication/ref contracts | Capture, current/historical reads, proposal/base expectations; запрет mixed-source facts |
| T5 Acceptance/handoff | T4; совместный Snapshot contract proposal | Atomic time+effects, operation identity, unknown outcome/retry/concurrent advances/cancellation/restore/branch |
| T6 Сквозное review всего proposal | T3-C; T4; T5 | Все walkthrough исходного запроса, exact public API inventory, закрытые unions, counts/import cycles, legacy gates |
| T-RULE Agent-rule audit | T6; T2-TZ; актуальная consolidated map | Проверка всего плана по §25, findings устранены или явно блокируют затронутый scope |
| T7 Пользовательская приёмка | T-RULE; явный список внешних deferred contracts | Архитектурный verdict. Даже PASS не разрешает код автоматически |

T0 и уточнение внешних seam можно исследовать независимо. После T1 T3-A независим от T2/T2-TZ; чтение Snapshot contracts и consumer requirements Physics/GEN можно вести параллельно документально. Полный Physics/GEN/Snapshot DONE не prerequisites дизайна. Недостающий конкретный контракт блокирует только соответствующий freeze/integration, не всё исследование. Production integration позднее потребует готовности нужного acceptance seam и явного разрешения на implementation.

Обязательный T6 набор: zero/positive, бой меньше часа, несколько действий внутри часа, Physics resume capture=start, смена календаря/no-calendar, concurrent advances, retry unknown commit, restore/branch, inactive timeline, cancellation. Для каждого нужны input/base → chosen DAG operations → proposal → acceptance/refusal → повторное чтение. Документальные walkthrough приведены в §12; runtime proofs ещё не выполнены.

## 9. Остаток исследования / stop boundary

Исходный checklist: полный ledger требований/consumers и writers; exact public Input/Output/Error и CRUD applicability; files/classes/factories/import directions; coherent capture и Snapshot acceptance; retries/concurrency/unknown outcome/cancellation; restore/branch/inactive timeline; walkthrough; этапы и внешние contracts. Core proposal и walkthrough добавлены в §§10–12; актуальные gates — §§24–26; ранние verdict ниже являются промежуточной историей.

Промежуточный verdict этого checklist: PARTIAL RESEARCH; актуальный статус см. в начале плана и §§24–26. Отсутствие реализации не означает отмену старого ТЗ. Незакрытые foreign types отмечать OPEN, не заменять Any/object/dict. Review PASS не заменяет приёмку пользователя. Меняется только этот owning-план; внешние документы и graph edges — лишь предложения с evidence.

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
| TimeAdvancePipelineOpenPipeline.prepare_advance(PrepareAdvance) → TimeAdvanceProposal \| TimeAdvanceMustBePositive \| TimeRangeOverflow | DAG с готовой положительной TimeDuration; actionCore producer binding DEFERRED | Pure preparation на supplied capture; никаких writes. Одинаковый input → тот же candidate. Актуальность base повторно проверяет acceptance boundary |

Owner всех операций таблицы — Time. Files/imports: классы и factory §6; request/result imports — §10; arithmetic/conversions не импортируют repositories/World/Physics/engine. `make_time_reader(source:ITimeReadSource)->TimeReader`; `make_time_advance_pipeline()->ITimeAdvancePipelineOpenPipeline` — composition-only, не DAG business operation. ITimeReadSource имеет те же две отдельные read signatures, гарантирует provenance и coherent state; реализация поверх Snapshot read OPEN, не SQL latest fallback. Публичного TimeService.execute(kind,request) нет.

Legacy/gates для каждой группы: arithmetic/conversions — новые публичные операции, legacy formulas retain до миграции callers; gate T3-A. Reads — replace чтение raw World.current_tick, retain legacy до coherent Snapshot source; gate T4. Prepare — replace прямой increment_tick только после T5 и блокировки косвенных generic writers; до этого ни один writer не удаляется этим документом. Generic import/export retain до World-approved migration/fingerprint policy. Нельзя считать отсутствие найденного increment_tick caller основанием убрать generic writes.

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

## 13. Промежуточный verdict (история; актуальные gates §§24–26)

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

## 15. Исторический Calendar proposal — SUPERSEDED для freeze (§23/T2-TZ)

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

**Историческая signature; требует замены в T2-TZ, не active freeze:** `CalendarProjector.project(CalendarProjectionRequest) -> CalendarProjection | CalendarSourceMismatch | CalendarPointMismatch | CalendarProjectionOutOfRange | UnsupportedCalendarRule`. Чистый Time algorithm, World-owned definitions. Все alternatives перечислены, но поля foreign types выше OPEN: **не готово к production typing**. Полная schema без World design не выдумывается. DAG явно читает настройки нужной версии, затем вызывает выбранное преобразование; projector не читает World и не выбирает новые public операции.

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

## 17. Промежуточный пакет приёмки (уточнён §§23–26)

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

Validate проверяет operation_id, expected_world, active timeline, captured start и положительный interval; читает через context.read_scope. Apply получает writer через bind(context.scope), повторяет необходимые актуальные preconditions и append под назначенным context.world_snapshot. На конфликт — SectionRefused(category=CONFLICT, typed FieldPathError diagnostics). На успешный append — SectionApplyReceipt с state/history refs для Time section. Construction changed:PatchRef конкретизирована в §34.3 через existing PatchOrdinal=0; receipt не является acceptance proof. Сопоставление Time errors с FieldPathError — в handler boundary, через общий механизм, не по message parsing.

Snapshot записывает receipt/history и operation terminal вместе с остальными effects и публикацией. Только committed SnapshotApplyResult позволяет DAG объявить новое время принятым. Storage append не выдаётся пользователю как successful advance. CAS failure/отказ любого другого handler отменяет append общей transaction. Storage не retry-loop и не scheduler.

### 18.4. Публичная boundary DAG остаётся прежней

`prepare_advance(PrepareAdvance) → TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow` — единственный runtime Time advance preparation contract. DAG собирает TimeAdvanceSection в typed PatchSet и вызывает Snapshot.apply. DAG не получает IBoundTimeStateWriter/CommitScope и не вызывает handler.apply напрямую. Domain-local validation и арифметика допустимы внутри prepare; чужие CRUD/сбор action effects запрещены.

Initialization и branch **не маскировать** runtime append с выдуманным snapshot. Headless gameplay-start state и branch rebind требуют собственных existing World/Snapshot lifecycle bindings; shape их storage source refs пока OPEN. Restore выбирает existing immutable state, а не вызывает Time.set_clock. Этот пункт остаётся отдельным integration gate, а не неявным дополнительным writer.

### 18.5. Принятое правило смены часов в сутках

Пользователь принял правило §15.3: сохранить текущие отображаемые дату/время при допустимости; иначе запросить явную новую календарную привязку. Owning POJO/общая validation проверяют candidate в новых настройках; невалидное изменение не публикуется. Технические transaction/ref bindings продолжают прорабатываться по правилам проекта. Данное решение не означает приёмку всего плана или разрешение implementation.

## 19. Исторический periodic/Gregorian вариант — SUPERSEDED для freeze (§23/T2-TZ)

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

**InitialTimeFacts(world_uid:EntityUid, seconds:Literal[0], nanoseconds:Literal[0])** — proposed Time POJO в storage/initial.py; только seconds=0,nanoseconds=0 для новой root timeline. **BindInitialTime(world_uid:EntityUid, timeline_id:EntityUid, initial:InitialTimeFacts)** → **TimeClockState** — pure fixed operation `TimeLifecycle.bind_initial`, проверяет world equality; не создаёт timeline. **RebindBranchTime(source:StoredTimeState, target_timeline_id:EntityUid)** → **TimeClockState** — pure fixed operation того же класса; сохраняет world/coordinate, назначает timeline, не доказывает ancestry/разрешение branch. DAG/Snapshot supplies validated branch context. Ошибки world/same-target misuse — shared structural validation; authorization/provenance нельзя подменить pure type check.

Файлы: dataModel/time/storage/initial.py (storage теперь 4 с init), dataModel/time/operations/lifecycle.py (operations теперь 4 с init), application/time/changes/lifecycle.py (changes теперь 3 с init). Authoritative headless state должен храниться в domain storage под publication binding существующего GameplayStart, а не под выдуманным SectionStateRef. **PublicationTimeState(publication:WorldPublicationRef, state:TimeClockState)** — proposed read value в storage/state.py; only started publication, совпадение world/active timeline. Предлагаемый read-source state union закрыт: `StoredTimeState | PublicationTimeState`. Foreign lifecycle storage write capability к GameplayStart/branch остаётся integration proposal, не дополнение SnapshotApplyContext без согласования owner.

### 20.2. Почему не утверждается готовый restore/branch writer

Existing SectionStateRef привязан к SnapshotRef, тогда как GameplayStarted имеет snapshot_head=None; это реальная несовместимость, найденная по POJO. Initial storage нельзя реализовать простым переиспользованием TimeStateAppend. Owner Snapshot должен принять publication-bound domain state retention и atomic binding с GameplayStart/branch. Это точный prerequisite, а не причина заводить Time.commit или отдельный journal.

Restore existing timeline читает StoredTimeState и versioned World settings; новая ветка использует pure rebind и сохраняет publication-bound состояние в общем branch transaction. First accepted snapshot переносит ссылку на новый Time state обычным section writer. Прежние refs удерживаются existing holder/retention механизмом. Time не выбирает target snapshot, не авторизует путешествие во времени и не вычисляет последствия для персонажа.

## 21. Промежуточный итог детализации (calendar выводы заменены §23/T2-TZ)

§19 исторически предлагал заполнение placeholders для periodic/Gregorian scope, но после §23 не закрывает target schemas. §20 конкретизирует root/branch data flow. Названия и поля date/clock/anchor/basic rules из §19 сохраняются только как исторические candidates; их target freeze выполняет T2-TZ. Pure lifecycle inputs остаются proposal §20. **Не закрыты и не замаскированы**: World calendar grammar/epoch conventions, publication-bound state lifecycle binding и actual chat turn-number API. Core Time реализовать сейчас нельзя в рамках документального задания; календарные gaps блокируют только зависимый scope, а не автоматически всю арифметику.

Предлагаемый порядок приёмки: core arithmetic/read/advance отдельно; calendar grammar и numbering conventions обязательно закрыть в T2-TZ; Snapshot owner принимает headless/branch state binding; затем согласовываются exact callers и migration. Проработка не требует полного DONE соседних доменов. Runtime tests/DDL/production ports отсутствуют намеренно; документальная конкретизация не равняется implementation или принятию пользователем.

## 22. Финальная consistency-проверка: зависимости и исправления proposal

ActionCore отложен пользователем: все ранние записи «actionCore OPEN» читаются как deferred integration requirement, а не незавершённая обязанность текущего Time design. Новые action request/result классы не вводятся. Повторный поиск action/turn contracts в backend/app не установил готового actionCore API; этот negative result не переоткрывает отложенную задачу.

### 22.1. Версия календаря — не текущая публикация

В §§15/19 предложенный CalendarVersionRef содержит publication, в которой принято определение. Эта публикация может быть старше capture; требование равенства этих refs было бы ошибочным. Исправленная семантика: **WorldCalendarRead** доказывает, что выбранная definition version действовала на запрошенном snapshot/publication. Proposed World-owned **ResolvedCalendarAt(source:WorldPublicationRef, version:CalendarVersionRef, settings:WorldTimeSettings, definition:GregorianCalendarDefinition | RuleCalendarDefinition, anchor:CalendarStartAnchor)**; source совпадает с current capture.publication. Для истории нужен отдельный **ResolvedHistoricalCalendarAt(source:WorldSnapshotRef, version:CalendarVersionRef, settings:WorldTimeSettings, definition:GregorianCalendarDefinition | RuleCalendarDefinition, anchor:CalendarStartAnchor)**. Version publication не обязана равняться source. World reader проверяет lineage/version validity, Time pure projection проверяет соответствие supplied source/capture и definition/anchor.

Эти POJO предлагаются в `dataModel/world/calendar/projection/request.py`. CalendarProjectionRequest заменяет расплющенные settings/calendar/version/anchor на `resolved:ResolvedCalendarAt | ResolvedHistoricalCalendarAt`, сохраняя point и capture. Current/historical variants обязаны совпадать; конкретный union перечислен. CalendarSourceMismatch из §15 требует расширения source полей на **WorldPublicationRef | WorldSnapshotRef** (ровно эти два POJO), не object. CalendarPointMismatch остаётся без изменения. Immutable version reuse не требует новой календарной версии на каждом advance.

### 22.2. Проверка схемы lifecycle

§20 fixed lifecycle operations — **pure binding helpers для внешнего lifecycle**, не дополнительные CRUD Time. StoredTimeState/PublicationTimeState — два способа ссылаться на состояние одного clock, не два независимых clocks. Snapshot metadata может наследовать state ref прошлой публикации; reader не требует ref.snapshot=current head. Он проверяет, что ref разрешён metadata/ancestry, а не извлекает latest напрямую.

InitialTimeFacts.seconds/nanoseconds в §20 заданы **Literal[0] / Literal[0]** для root; это не произвольный clock setter. Публичный clock reset из этих полей не следует. Branch rebind изменяет timeline identity только при утверждённом внешнем transition. Calendar epoch key не используется вместо timeline_id.

### 22.3. Номер хода: evidence и отделение от Time

В `0001_initial.sql` turns — «один ход игрока, создаётся только при успехе»; поля turn_id TEXT PK, session_id, player_input, game_tick INTEGER nullable, created_at. WorldSnapshotMetadata.turn_id — strict int>=1 и порядок цепочки. Ни TEXT UID, ни nullable game_tick не являются готовым public UI ordinal contract. Предложение владельцу chat/GEN: **DisplayedTurn(number:strict int>=0, source:WorldPublicationRef)**, получение из accepted game-turn semantics; не назначать самостоятельно count SQL rows или snapshot ordinal. Exact owner API остаётся integration OPEN; Time UI facts доступны независимо, но UI «время + номер хода» нельзя объявить интегрированным до принятия этого binding.

### 22.4. Принятые решения против непринимаемых автоматически proposals

Принято пользователем: time units/representation; World ownership; Gregorian+UTC default start/custom explicit start; hours/day default24; immutable history; положительная цена действий; versioned hours/day change с сохранением допустимой даты; actionCore deferred. Periodic-only grammar как предел календарей отвергнута пользователем (§23). Не принято автоматически: astronomical year zero, конкретные file/API names, publication-bound initial storage protocol. Эти предложения требуют итоговой приёмки, но не реализации до неё.

Заявка «любой календарь через настройки» сохраняется целевой. Историческая periodic grammar — reuse candidate одного вида правила, не целевая архитектурная основа и не закрытие schema (§23). Расширение grammar принадлежит World-defined POJO + pure Time algorithms и требует concrete typed alternatives; plugin registry/исполняемый пользовательский код/LLM fallback не добавляются. Неизвестный authored rule отвергается schema admission; UnsupportedCalendarRule применяется к известной version/capability, которую данный projector не поддерживает, не переносит неизвестный raw payload через строгий POJO.

### 22.5. Итоговые gates

| Gate | Статус / зависимость |
|---|---|
| Core Time proposal | Предъявлен: values, arithmetic, capture, preparation, section/storage boundaries; требуется пользовательская приёмка |
| Calendar proposal | N+1/closed-enum архитектура принята; старый periodic union SUPERSEDED; полный enum/POJO/API freeze выполняется T2-TZ |
| Snapshot integration | Contract proposal предъявлен; headless/branch state retention binding — внешний freeze prerequisite, не новый Time publisher |
| ActionCore | DEFERRED / OPEN по прямому указанию пользователя; не блокирует core proposal |
| UI turn contract | OPEN у chat/GEN; существующий TEXT UID не подменяет номер |
| Legacy audit | Независимое статическое ревью получено: [техдолг TIME-DEBT-01…06](./time-domain-review-debt.md). Generic writers, Regions и legacy требования требуют адресной миграции; lifecycle integration остаётся OPEN. Coverage limitations сохранены; runtime proofs не выполнялись |
| TIME-LOG / общий logging facade | Обязателен для будущей production-интеграции (§47); контракт событий и маршрут согласованы. Регистрация и runtime-проверки предстоят на интеграции. Изолированное ядро разрабатывается независимо |
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

**Добавлен по прямому запросу пользователя. Статус SPECIFICATION PROPOSAL предъявлен в §§29–33; accepted calendar freeze BLOCKED до приёмки и закрытия integration prerequisites.** Это не optional follow-up и не задача «уточнить при реализации». Полное ТЗ подготавливается разделом этого owning-плана: текущее ограничение «менять только Time-план» сохраняется. После отдельного разрешения нормативный текст можно перенести в `docs/tz_time.md`/World owning ТЗ без дублирования SoT; сейчас новые документы не создаются.

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
3. Подготовка advance описана как fixed pipeline. Для соответствия принятому именованию public pipelines предлагается freeze rename: **ITimeAdvancePipelineOpenPipeline / TimeAdvancePipelineOpenPipeline.prepare_advance(PrepareAdvance)**, файл `application/time/changes/advancePipelineOpenPipeline.py`; прежние имя preparer и метод prepare — **SUPERSEDED proposal names**, не production rename; активное имя в §§6/11 приведено к Pipeline. Factory `make_time_advance_pipeline()->ITimeAdvancePipelineOpenPipeline`. Pure arithmetic/reads не переименовывать Pipeline ради симметрии. Остальные I/O/E сохраняются.
4. Все карты §§6/15/19 читаются как история proposal до TZ-6: никакой код не должен выбирать между ними. TZ-6 обязан заменить их одной active map и снабдить point-of-use supersession, иначе T-RULE FAIL.

### DoD окончательной проверки всего плана

Reviewer читает весь план, не только последний appendix. Для каждого шага: prerequisite graph без циклов; один атомарный результат; exact ownership/file/signature; POJO/enum freeze; legacy definition+caller links+disposition+cutover gate; folder counts; отсутствие hidden orchestration; evidence/status. Отдельно проверяет сохранение принятых решений пользователя и отсутствие их повторного OPEN. По каждому правилу — PASS/FAIL/NOT APPLICABLE с обоснованием; для каждой FAIL — исправление и повторная проверка. Внешний deferred actionCore обозначается DEFERRED, не FAIL core Time.

**Текущий честный verdict: документальный scope соблюдён, полное соответствие плана execution-gates пока НЕ достигнуто.** Добавление этого checklist не исправляет автоматически findings. Calendar freeze блокирует календарный core; core file-map/contract gaps и документальный linked legacy inventory блокируют приёмку соответствующего core slice. Реализация самой legacy migration не является prerequisite core (§26). Нельзя объявить «план полностью соответствует правилам» до их фактического закрытия. Review PASS не заменяет пользовательскую приёмку.

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

Linked legacy inventory — документальная обязанность до приёмки плана, а не требование предварительно переписать legacy. T-RULE проверяет core и migration readiness раздельно: допустим verdict **CORE READY / MIGRATION PENDING**, когда core contract gates действительно закрыты. Сейчас такого verdict для всего core ещё нет из-за T2-TZ и core consolidated-map gaps; проверенные независимые части могут предъявляться отдельно. Нельзя запрещать core только потому, что migration ещё не выполнена; нельзя включать production flow с оставшимся обходом только потому, что core готов.


## 27. Финальная редакционная проверка противоречий

Проверен план целиком с учётом уточнений пользователя и внесённых внешним ревью ссылок на `time-domain-review-debt.md`. Чужие findings и файлы сохранены. Исправления внесены в исходные формулировки, а не только новым приоритетным appendix:

- Единое активное имя подготовки: ITimeAdvancePipelineOpenPipeline / TimeAdvancePipelineOpenPipeline.prepare_advance, advancePipelineOpenPipeline.py, make_time_advance_pipeline; старые имена не используются в текущем API inventory.
- Gregorian/Periodic полный union и его file maps помечены SUPERSEDED у места описания. N+1/closed-enum composition и обязательный T2-TZ остаются единственным целевым направлением. Частные algorithms — candidates, не второе активное ТЗ.
- T3 разделён на T3-A и T3-C: reads/advance зависят от core arithmetic, а не от календарной grammar. Общее review всего proposal ждёт обе части; отдельный core slice может пройти свой T-RULE/приёмку независимо.
- ActionCore DEFERRED; миграция legacy выполняется после core. Нужные собственные core contracts/документальный inventory не названы техдолгом, который можно отложить за код.
- Initial root coordinate — Literal[0] seconds/nanos. При отсутствии snapshot используется publication-bound accepted state, не фиктивный snapshot ID.
- Ошибки core перечислены в §10; строка первоначальной карты больше не объявляет весь error catalog отсутствующим. Calendar errors остаются частью T2-TZ.
- Ранние verdict и folder counts обозначены промежуточными; общий актуальный статус вынесен в начало. Не заявлены полный freeze, T-RULE PASS или runtime readiness.

Оставшиеся OPEN — реальные задачи, а не конкурирующие решения: T2-TZ, окончательная core file/import map, initial/branch acceptance binding, UI turn binding. ActionCore — отдельно отложен. Техдолг — отдельный последующий migration scope. Проверка формулировок не закрывает эти задачи и не разрешает implementation.

## 28. Публичные settings contracts через DAG — обязательное требование

Уточнено пользователем: публичные контракты нужны **для самих настроек**, не только для арифметики, calendar projection и advance clock. Владение остаётся World. Существующий WorldService с dict payload не выполняет требование.

Обязательный inventory для T2-TZ/TZ-5:

| World-owned public operation | Применимость / смысл |
|---|---|
| Read current time settings | Получить WorldTimeSettings и применимые calendar bindings на expected publication; без независимого latest/fallback |
| Read historical time settings | Получить настройки и версии, действовавшие на заданном snapshot; не менять active timeline |
| Prepare initial time settings | Создать настройки при инициализации мира: owning POJO defaults, explicit custom start, supplied once-captured UTC для standard start |
| Prepare update time settings | Изменить разрешённые поля, включая hours_per_day; сохранить допустимую дату/время либо потребовать explicit anchor; новая version без изменения physical clock |
| Read calendar registry / definition / epoch | Typed N+1 записи и refs на согласованной версии, не raw JSON |
| Prepare create/update calendar и epoch | Создание world entries; update создаёт новую версию; события/выбор момента передаёт DAG, World не наблюдает их самостоятельно |
| Prepare select calendar | Изменение выбранного календаря через owning World operation, без изменения clock |
| Prepare remove calendar assignment/entry | Только допустимые World policy удаления с сохранением retained history и разрешённого выбранного календаря; exact applicability/отказы freeze в ТЗ |

Standalone delete WorldTimeSettings, удаление удерживаемой исторической версии, generic set arbitrary field и прямой commit настроек запрещены. Restore/branch не заменяются CRUD настроек. Сброс на default, если нужен, должен быть явной typed update operation, а не невалидным/пустым payload с молчаливым исправлением.

Для **каждой** строки TZ-5 обязан предъявить exact public interface/method/file, Input/Output/Error POJO и полный union, source/publication/version guards, idempotency, validation/default policy, preparation/acceptance boundary, DAG caller requirement, legacy disposition и gate. Этот inventory пока не exact API и не закрывает freeze одним перечислением названий. Placement: owning World application operations и World dataModel; конкретные пути закрываются TZ-6, не выбираются при реализации.

Внешний API, включая будущий editor/debug, направляет выполнение через DAG; DAG вызывает World public operations непосредственно, без HTTP self-call. DAG явно связывает World settings result с Time input. Ни TimeReader, ни CalendarProjector не вызывают World settings CRUD скрытно. Изменения принимаются согласованным World/Publication lifecycle; runtime changes — через общий Snapshot acceptance. Route не реализует собственный validate→write→publish pipeline. Preview использует тот же согласованный DAG-путь и общую POJO validation без writes.

**Gate:** calendar/settings core contract freeze неполон без этого public settings inventory с exact signatures. Отложенная реализация legacy migration не отменяет требования сначала описать новую public boundary. Конкретные NodeIds, CALL/RETURN и HTTP routes по этому разделу не создаются и требуют отдельной GEN-приёмки.

## 29. T2-TZ — цельный кандидат нормативного контракта

**Статус: SPECIFICATION PROPOSAL, требуется пользовательская приёмка.** Этот раздел заменяет календарные варианты §§15/19/22, не меняет core Time values. Вводит закрытую композиционную grammar, а не enum имён календарей. Не утверждается математическая возможность описать произвольную неизвестную вычислительную семантику: новые engine operations требуют нового concrete enum/POJO; произвольные данные мира в рамках operations не требуют изменения кода. Это применение принятого N+1, не periodic-only ограничение.

### 29.1. Типы и enums

Общие constraints: Int — strict integer arbitrary precision для календарных индексов; Nat>=0; Pos>=1; Text — str только display/description. Runtime seconds/nanos сохраняют bounds §10. N+1 keys — RegistryKey owning registry, snake_case, membership через общий REF-W. Все models frozen/extra-forbid; payload defaults только из owning POJO; tuples immutable. Schema identity — `SCH-WORLD-TIME-SETTINGS-V1`; format version=1 (предложение namespace, проверка collision при общей registry registration до кода).

Закрытые enums (новые, engine-owned, `dataModel/world/calendar/enums/rules.py`):

- CalendarPredicateKind: ALWAYS, YEAR_MODULO, YEAR_RANGE.
- CalendarEditKind: INSERT_SPAN, REPLACE_SPAN, REMOVE_SPAN.
- CalendarWeekMode: CONTINUOUS, RESET_AT_YEAR.
- CalendarNumbering: ASTRONOMICAL, NO_YEAR_ZERO.
- CalendarSpanRole: MONTH, INTERCALARY.

Каждый tagged POJO имеет `kind:Literal[соответствующий enum member]`. Unknown member — structural rejection, не fallback. Имена календарей/месяцев/сезонов не входят в эти enums. Canonical Gregorian — данные правил ниже, а не второй public definition class.

### 29.2. POJO grammar и однозначный порядок

В этой таблице каждое поле обязательно, если default/nullable явно не указан. Own registry keys помечены сокращением Key[R]=RegistryKey[R]. Реестры содержат `entries:tuple[Entry,...]`, unique system keys; CalendarRegistry непустой, остальные могут быть пусты только при отсутствии соответствующих refs. Реестры: WorldCalendarRegistry, CalendarSpanRegistry, CalendarWeekdayRegistry, CalendarSeasonRegistry, CalendarPeriodRegistry, WorldCalendarEpochRegistry.

| POJO | Поля |
|---|---|
| SpanEntry | system_span:Key[CalendarSpanRegistry]; display_span:Text; role:CalendarSpanRole |
| WeekdayEntry / SeasonEntry | system_weekday:Key[CalendarWeekdayRegistry], display_weekday:Text / system_season:Key[CalendarSeasonRegistry], display_season:Text |
| PeriodEntry | system_period:Key[CalendarPeriodRegistry]; display_period:Text; from_hour:Nat; from_minute:DefaultWhenMissing[int 0..59]=0 |
| CalendarSpan | span:Key[CalendarSpanRegistry]; days:Pos; counts_in_week:bool; season:Key[CalendarSeasonRegistry] \| None |
| AlwaysPredicate | kind=ALWAYS |
| YearModuloPredicate | kind=YEAR_MODULO; modulus:Pos; residue:Nat (<modulus); offset:Int |
| YearRangePredicate | kind=YEAR_RANGE; first:Int; last:Int; first<=last |
| CalendarCondition | all_of:tuple[AlwaysPredicate \| YearModuloPredicate \| YearRangePredicate,...]; none_of:tuple[AlwaysPredicate \| YearModuloPredicate \| YearRangePredicate,...]. all_of empty=True, none_of empty=True; no opaque expressions |
| InsertSpanRule | kind=INSERT_SPAN; condition:CalendarCondition; after:Key[CalendarSpanRegistry] \| None; value:CalendarSpan. after=None означает начало года |
| ReplaceSpanRule | kind=REPLACE_SPAN; condition:CalendarCondition; value:CalendarSpan. Заменяется occurrence с value.span |
| RemoveSpanRule | kind=REMOVE_SPAN; condition:CalendarCondition; span:Key[CalendarSpanRegistry] |
| CalendarDefinition | system_calendar:Key[WorldCalendarRegistry]; display_calendar:Text; description:Text; numbering:CalendarNumbering; spans:CalendarSpanRegistry; weekdays:CalendarWeekdayRegistry; seasons:CalendarSeasonRegistry; periods:CalendarPeriodRegistry; base_year:tuple[CalendarSpan,...]; rules:tuple[InsertSpanRule \| ReplaceSpanRule \| RemoveSpanRule,...]; week_mode:CalendarWeekMode; week_anchor_ordinal:Int; week_anchor_index:Nat |
| CalendarDate | year:Int; span:Key[CalendarSpanRegistry]; day:Pos |
| CalendarClockTime | hour:Nat; minute:strict int[0,59]; second:strict int[0,59]; nanoseconds:Nano |
| CalendarOrigin | date:CalendarDate; time:CalendarClockTime |
| CalendarAnchor | coordinate_seconds:I64; coordinate_nanoseconds:Nano; origin:CalendarOrigin. Не требует timeline до gameplay; scope задаётся versioned World binding |
| CalendarEntry | definition:CalendarDefinition; anchor:CalendarAnchor |
| WorldTimeSettings | hours_per_day:DefaultWhenMissing[Pos]=24; calendars:WorldCalendarRegistry; selected:Key[WorldCalendarRegistry]; epochs:WorldCalendarEpochRegistry |
| WorldCalendarEpoch | system_epoch:Key[WorldCalendarEpochRegistry]; display_epoch:Text; description:Text; calendar:Key[WorldCalendarRegistry]; start_seconds:I64; start_nanoseconds:Nano; start_year_label:Int |

WorldCalendarRegistry entries — CalendarEntry, identity projection — entry.definition.system_calendar. Поля description/display разрешены prose, никакой код из них не исполняется. CalendarDefinition — единственный public definition type. GregorianDate/RuleCalendarDate/PeriodicCalendarRules и их union не используются целевым API.

Порядок: взять base_year, применить подходящие rules в порядке tuple. У replace/remove цель обязана существовать, у insert — отсутствовать; after обязан существовать. Повторный ключ occurrence запрещён, длина итогового года положительна. Не исправлять конфликт приоритетом из имени/key. Order tuple — authored часть семантики и fingerprint. Modulo применяется к внутреннему astronomical year после конверсии numbering; для NO_YEAR_ZERO внешнее 0 invalid, отрицательное y преобразуется в y+1. Изменять numbering допустимо только новой версией/anchor.

Calendar spans и годы не обязаны быть периодическими: YEAR_RANGE разрешает разовые и ограниченные исторические exceptions, сочетание range+modulo — временные правила. Реформа даты — новая версия с anchor, не разрушительная перепись старого алгоритма. Эпоха от события задаётся явно принятым моментом World operation; Time не читает Events. Future неизвестная дата события не становится исполняемым calendar rule.

### 29.3. Validation, defaults, bounds

World resolver проверяет registry membership, уникальность periods/from_hour, from_hour<hours/day и наличие периода 0, clock hour<hours/day, day<=resulting span.days, validity selected/epoch refs. Empty weekdays: все weekday outputs=None, anchor index=0. Nonempty weekdays: anchor index<len. INTERCALARY не навязывает counts_in_week: автор задаёт явно.

Проверка rules охватывает все классы годов: boundaries YEAR_RANGE разделяют шкалу на конечные области; внутри области истинность modulo периодична с LCM модулей. Анализ/расчёт должны иметь явный execution budget, передаваемый caller, а не обрезать правила. **CalendarBudget(max_rule_checks:Pos, max_year_patterns:Pos)** — application request data, не world setting. Недостаток budget → CalendarBudgetExceeded; не принятие непроверенного объекта. Большой LCM может потребовать больше budget или улучшения алгоритма; это прозрачный отказ по ресурсу, не изменение календаря. Количество прошедших лет не перебирается: prefix sums + циклы/области; signed arithmetic и floor division поддерживают отрицательные годы.

Gregorian canonical settings: 12 span entries с conventional lengths, February replace 29 при year%4=0 AND NOT year%100=0, затем February replace29 при year%400=0; numbering NO_YEAR_ZERO, weekdays Monday…Sunday, continuous week. Canonical epoch/season/period display entries — World data; их точные подписи и canonical anchor weekday подлежат fixture-spec freeze, не literals алгоритма. **Это оставшийся конкретный gap canonical data**, не разрешение агенту выбрать значения в коде.

Отсутствующие standard settings готовятся fixed World initializer из supplied UTC instant и canonical POJO. Custom creation требует explicit origin. JSON null не missing. JSON codec I64 components — decimal strings на внешней transport boundary, strict ints внутри application/canonical codec; единственное место conversion — согласованный transport codec, не domain coerce. Wire choice — proposal для приёмки API owner, не изменение текущих routes.

### 29.4. Pure projection API

CalendarVersionRef(calendar_key:Key[WorldCalendarRegistry], publication:WorldPublicationRef) сохраняется. **ResolvedCalendarAt(source:WorldPublicationRef | WorldSnapshotRef, version:CalendarVersionRef, settings:WorldTimeSettings)** — World reader гарантирует applicability version и выбранного calendar. Union source ровно два названных POJO; World-owned version evidence, не календарный latest lookup.

**CalendarProjectionInput(point:TimePoint, capture:TimeCapture | HistoricalTimeCapture, calendar:Key[WorldCalendarRegistry], resolved:ResolvedCalendarAt, budget:CalendarBudget)**.
**CalendarProjection(point:TimePoint, version:CalendarVersionRef, date:CalendarDate, time:CalendarClockTime, weekday:Key[CalendarWeekdayRegistry] | None, season:Key[CalendarSeasonRegistry] | None, period:Key[CalendarPeriodRegistry], epoch:Key[WorldCalendarEpochRegistry] | None, epoch_year:Int | None)**. Epoch selection — последняя applicable start этого calendar в supplied version, равные starts запрещены; до первого epoch обе nullable fields=None. Epoch year = date year − projected epoch-start year + start_year_label с numbering conversion, label convention не меняет физический год.

Ошибки, конкретные POJO: **CalendarSourceMismatch(expected:WorldPublicationRef | WorldSnapshotRef, actual:WorldPublicationRef | WorldSnapshotRef)**; **CalendarScopeMismatch(expected:TimeScope, actual:TimeScope)**; **CalendarBudgetExceeded(budget:CalendarBudget)**; **CalendarInvalid(issues:tuple[FieldPathError,...])** непустой; **CalendarTimeOverflow(operation:CalendarConversionKind)**, где закрытый enum CalendarConversionKind=PROJECT/RESOLVE (enums/rules.py).

`CalendarProjector.project(CalendarProjectionInput) → CalendarProjection | CalendarSourceMismatch | CalendarScopeMismatch | CalendarBudgetExceeded | CalendarInvalid | CalendarTimeOverflow`.

Обратная операция: **CalendarResolveInput(resolved:ResolvedCalendarAt, calendar:Key[WorldCalendarRegistry], date:CalendarDate, time:CalendarClockTime, scope:TimeScope, budget:CalendarBudget)**; **TimeScope(world_uid:EntityUid,timeline_id:EntityUid)** — отдельный value POJO в dataModel/time/values/point.py, не фиктивный TimePoint с игнорируемой координатой. `CalendarProjector.resolve(CalendarResolveInput) → PointResult | CalendarSourceMismatch | CalendarInvalid | CalendarBudgetExceeded | CalendarTimeOverflow`. Scope обязан совпадать с world и выбранной timeline source; при несовпадении CalendarInvalid с field-path диагностикой. Вход закреплён на **одной версии**, поэтому ambiguous dates разных реформ не угадываются: caller выбирает version. Выбор применимой исторической версии — World read, не reverse projector.

## 30. Публичные settings contracts — exact proposal

Все операции World-owned, зовутся DAG. Scope read/apply не открывается в HTTP. Value outputs reusable в DAG без копии схемы. Preconditions повторно проверяются при acceptance; preparation не пишет. Исходный WorldTimeSettings приходит только из coherent World reader, не caller-authored proof.

Общие POJO:

- **TimeSettingsRead(expected:WorldPublicationRef)**; **HistoricalTimeSettingsRead(snapshot:WorldSnapshotRef)**.
- **TimeSettingsCapture(source:WorldPublicationRef, settings:WorldTimeSettings, versions:tuple[CalendarVersionRef,...])**; **HistoricalTimeSettingsCapture(source:WorldSnapshotRef, settings:WorldTimeSettings, versions:tuple[CalendarVersionRef,...])**. Ровно одна version на каждый calendar key; world совпадает, применимость подтверждает World reader. Без versions нельзя построить ResolvedCalendarAt достоверно.
- **SettingsPreparationBase(operation_id:EntityUid, capture:TimeSettingsCapture, clock:TimeCapture, budget:CalendarBudget)**; publication equality обязательно, clock scope active.
- **PreparedTimeSettingsChange(operation_id:EntityUid, expected:WorldPublicationRef, before:WorldTimeSettings, after:WorldTimeSettings, effective_at:TimePoint)**. Proposal полного typed settings state, не arbitrary world replacement; fingerprint включает все поля.
- **SettingsConflict(expected:WorldPublicationRef, observed:WorldPublicationRef)**; **SettingsNotFound(world_uid:EntityUid)**; **SettingsInvalid(issues:tuple[FieldPathError,...])** nonempty; **SettingsAnchorRequired(calendar:Key[WorldCalendarRegistry], current:CalendarClockTime)**; **SettingsInUse(calendar:Key[WorldCalendarRegistry])**.

| Operation / request POJO fields | Exact result alternatives |
|---|---|
| read_current(TimeSettingsRead) | TimeSettingsCapture \| SettingsConflict \| SettingsNotFound |
| read_historical(HistoricalTimeSettingsRead) | HistoricalTimeSettingsCapture \| SettingsNotFound \| SettingsSnapshotNotFound |
| prepare_hours_change(HoursChange(base:SettingsPreparationBase,hours_per_day:Pos,anchors:tuple[CalendarAnchorReplacement,...])) | PreparedTimeSettingsChange \| SettingsInvalid \| SettingsAnchorRequired \| CalendarBudgetExceeded |
| prepare_calendar_create(CalendarCreate(base:SettingsPreparationBase,entry:CalendarEntry)) | PreparedTimeSettingsChange \| SettingsInvalid \| CalendarBudgetExceeded |
| prepare_calendar_update(CalendarUpdate(base:SettingsPreparationBase,entry:CalendarEntry)) | PreparedTimeSettingsChange \| SettingsInvalid \| SettingsAnchorRequired \| CalendarBudgetExceeded |
| prepare_calendar_select(CalendarSelect(base:SettingsPreparationBase,calendar:Key[WorldCalendarRegistry])) | PreparedTimeSettingsChange \| SettingsInvalid \| CalendarBudgetExceeded |
| prepare_calendar_remove(CalendarRemove(base:SettingsPreparationBase,calendar:Key[WorldCalendarRegistry],replacement:Key[WorldCalendarRegistry])) | PreparedTimeSettingsChange \| SettingsInvalid \| SettingsInUse \| CalendarBudgetExceeded |
| prepare_epoch_create(EpochCreate(base:SettingsPreparationBase,epoch:WorldCalendarEpoch)) | PreparedTimeSettingsChange \| SettingsInvalid \| CalendarBudgetExceeded |
| prepare_epoch_update(EpochUpdate(base:SettingsPreparationBase,epoch:WorldCalendarEpoch)) | PreparedTimeSettingsChange \| SettingsInvalid \| CalendarBudgetExceeded |
| prepare_epoch_remove(EpochRemove(base:SettingsPreparationBase,epoch:Key[WorldCalendarEpochRegistry])) | PreparedTimeSettingsChange \| SettingsInvalid \| CalendarBudgetExceeded |

**CalendarAnchorReplacement(calendar:Key[WorldCalendarRegistry], origin:CalendarOrigin)** — anchor coordinate берётся из base.clock; duplicates forbidden. hours change затрагивает все calendars: valid projected origins сохраняются, invalid требуют explicit replacement. Calendar update проверяет origin по новым rules. Selected calendar removal требует отличную существующую replacement; last entry не удаляется, сначала явно создать canonical replacement. Delete означает removal из **новой версии**, не deletion retained history. Epoch removal тоже не удаляет старые версии. SettingsInUse — current remaining refs в candidate, а не запрет самого versioned removal из-за истории.

Create/update различны: create при существующем key — SettingsInvalid, update при отсутствующем — SettingsInvalid. Reads отдельных entries выполняются pure registry accessor на capture, не hidden DB query. Default reset — явное update/create canonical POJO, нет общего reset kwargs. Нет delete всего WorldTimeSettings.

Initialization определяется только §33: PrepareInitialSettings содержит tagged authored input и budget. Прежняя resolved-only сигнатура удалена из активной таблицы; её нельзя использовать как альтернативный API.

Owner World public interface **IWorldTimeSettings**: методы таблицы; реализации fixed preparation pipelines не выбирают другие операции. Прежняя aggregate factory **SUPERSEDED**: активные отдельные factories и dependencies перечислены в §38; persistence читатель использует Snapshot scopes. Preparation methods synchronous/pure; reads async. Classes/paths в §31. Initial/root publication и acceptance World settings change используют World/Snapshot handler, не Time.advance. Exact heterogeneous section union принадлежит caller; этот API не вводит его произвольно.


## 31. Единая candidate file map и порядок freeze

Корень `backend/app`. Эта карта заменяет competing calendar maps. Каждый leaf включает init; counts в скобках. Новые имена пока proposal, не пользовательская приёмка.

- `dataModel/time/values`: point.py, duration.py, interval.py (4); `reads`: capture.py, request.py (3); `operations`: arithmetic.py, conversion.py, lifecycle.py (4); `changes`: advance.py, section.py (3); `results`: errors.py (2); `storage`: state.py, append.py, initial.py (4). Ответственности core — §§10/18/20.
- `dataModel/world/calendar/enums/rules.py` (2): все enums §29.1.
- `dataModel/world/calendar/catalogs`: spans.py, weekdays.py, seasons.py, periods.py (5): Entry+Registry из §29.2.
- `dataModel/world/calendar/rules`: predicates.py, edits.py (3): concrete tagged POJO; condition в predicates.py.
- `dataModel/world/calendar/definitions`: definition.py, registry.py (3): CalendarDefinition/CalendarEntry и WorldCalendarRegistry.
- `dataModel/world/calendar/dates`: date.py, clock.py, anchor.py (4): CalendarDate, CalendarClockTime, CalendarOrigin/CalendarAnchor/CalendarAnchorReplacement.
- `dataModel/world/calendar/epochs`: epoch.py, registry.py (3): WorldCalendarEpoch/Registry.
- `dataModel/world/calendar/projection`: request.py, result.py, errors.py (4): все §29.4, CalendarBudget в request.py. ResolvedCalendarAt/version ref в request.py; values не импортируют projection.
- `dataModel/world/settings/timeSettings.py` (2): WorldTimeSettings + SCHEMA_ID/policies.
- `dataModel/world/settings/timeOperations`: read.py, changes.py, results.py, initial.py (5): §30 requests/captures/results; SettingsPreparationBase в changes.py. Не создавать registry schemas здесь повторно.
- `application/time/pure`: arithmetic.py, conversions.py (3); `calendar`: projection.py, ordinal.py, rules.py, validation.py (5); `reads`: reader.py, sourcePort.py (3); `changes`: advancePipelineOpenPipeline.py, lifecycle.py (3); `integration`: snapshotHandler.py (2); `storage`: statePort.py (2); `composition`: factory.py (2).
- `application/worldData/timeSettings`: interface.py, reader.py, sourcePort.py, factory.py (5); `preparation`: calendarPipelineOpenPipeline.py, epochPipelineOpenPipeline.py, hoursPipelineOpenPipeline.py, initialPipelineOpenPipeline.py (5). Методы объединены по одному владельцу данных, каждый public pipeline фиксирует одну операцию, не универсальный dispatcher.
- `db/repositories/sqlite/time/stateStore.py` (2): future Time state adapter; фактический SQL layout/World settings adapter freeze — prerequisite storage implementation, не выбор во время кодирования.

Imports: dataModel только dataModel/primitives; World calendar → Time values допустимо для capture/projection, Time values → World запрещено. Time pure calendar imports World POJO; World preparation использует pure Time checks через явный binding, не Time CRUD. Registry TYPE_CHECKING разрывает entry↔registry цикл по existing pattern. Snapshot binds domain handlers, handlers не импортируют transaction owner. API/GEN конкретные файлы не вводятся до принятия node/transport contract.

Все leaf counts <=5. Parent package folders — один init, вложенные папки не считаются непосредственными файлами. Производственные line counts неприменимы до кода; декомпозиция по ответственности обязательна при достижении лимита, не новый giant CalendarService.

## 32. Verification matrix и T-RULE результат этой итерации

### Документальные примеры

| Input | Expected |
|---|---|
| Gregorian 1900, year modulo rules | February=28: делимость на 100 исключает leap; на 400 не делится |
| Gregorian 2000 | February=29: правило 400 применимо |
| Base month 30 дней + YEAR_RANGE [17,17] replace days31 | Только year17 получает 31 день, period-only предположения нет |
| INSERT_SPAN intercalary days1/counts_in_week=False | День существует в ordinal/date, weekday=None, следующая недельная дата не сдвинута этим днём |
| 10h/day, anchor day1 09:59:59, +1s | day2 00:00:00 |
| 30h/day, anchor day1 23:59:59, +1s | day1 24:00:00 |
| remove отсутствующего span / replace неверной цели | CalendarInvalid, без частично применённых rules |
| Unknown enum / отсутствующий selected key | Общая schema/REF-W диагностика, без Gregorian fallback |
| Custom calendar missing start | Initial admission отказ, не server now |
| hours24→12 at18:00 без anchor | SettingsAnchorRequired, clock/settings не публикуются |
| Historical reform labels повторяются | Resolve требует конкретную version; latest не выбирается молча |
| Action/epoch event | DAG supplies accepted anchor facts; Time не вызывает action/event owner |

Большие диапазоны, ordinal roundtrip, сложные LCM и все отрицательные годы требуют runtime property/boundary tests после разрешения реализации; сейчас это proof obligations, не PASS.

### Rule audit — честная граница закрытия

N+1/enum semantics, конкретная базовая grammar, settings API inventory и candidate file map теперь предъявлены с typed fields/unions. Документальное требование не использовать Any/dict placeholders соблюдено в новых schemas. Code/server/DDL/nodes не менялись; actionCore deferred; техдолг не перенесён в prerequisites реализации независимого core.

**Обнаруженные остаточные FAIL, не скрывать статусом DONE:**

1. Exact authored initial-input schema (missing Gregorian/custom explicit origin), canonical display/period/weekday fixture specification и full initial operation errors требуют завершения; текущий resolved-only PrepareInitialSettings не выражает default policy полностью.
2. Snapshot headless/branch state storage acceptance и World settings handler/receipt bindings остаются внешними exact-contract prerequisites integration; existing ports недостаточны для объявления ready implementation.
3. Proposed closed grammar требует пользовательской приёмки expressiveness; отрицательные годы/era numbering не были ранее приняты. Без этого нельзя объявить T2-TZ DONE.
4. CalendarRange/epochs projection tests отсутствуют по scope; это будущий runtime gate, не причина писать тестовый код сейчас.

T2-TZ: **SPEC DRAFT PRODUCED, NOT ACCEPTED**. T-RULE: **REVIEWED WITH OPEN FINDINGS**, не PASS всему плану. Нельзя заменить эти findings обещанием «агент разберётся при кодировании». Остаточные пункты конкретны и не относятся к отложенному actionCore или legacy техдолгу.

## 33. Закрытие initial-input specification (уточняет §30 и finding 32.1)

Дополнительный закрытый enum **CalendarInitializationKind: STANDARD, AUTHORED**, в enums/rules.py. Две concrete формы initial input:

- **StandardTimeSettingsInput(kind:Literal[STANDARD], hours_per_day:DefaultWhenMissing[Pos]=24, origin:DefaultWhenMissing[CalendarOrigin | None]=None)**. None — явно допустимый sentinel capture-current-UTC для стандартного календаря, не invalid-value fallback.
- **AuthoredTimeSettingsInput(kind:Literal[AUTHORED], settings:WorldTimeSettings)**. Все CalendarEntry.anchor/origin обязательны; ошибки/null не заменяются стандартными значениями.
- **PrepareInitialSettings(operation_id:EntityUid, world_uid:EntityUid, input:StandardTimeSettingsInput | AuthoredTimeSettingsInput, captured_utc:CreatedAtUtc, budget:CalendarBudget)**. CreatedAtUtc — existing metadata type, ограничивает только реальный wall-clock input; вычисляемая calendar date не ограничена datetime.
- **PreparedInitialSettings(operation_id:EntityUid, world_uid:EntityUid, settings:WorldTimeSettings, captured_utc:CreatedAtUtc)**, как §30.
- **InitialAnchorRequired(hours_per_day:Pos, captured_hour:Nat)** — отдельный World refusal: при стандартном calendar с сокращёнными сутками UTC hour может оказаться недопустимым. Не применять modulo к текущему часу; caller задаёт явный origin.

`WorldInitialTimeSettingsPipelineOpenPipeline.prepare_initial(PrepareInitialSettings) → PreparedInitialSettings | SettingsInvalid | InitialAnchorRequired | CalendarBudgetExceeded`. Fixed pipeline разрешает только штатный missing/default через объявленную owning policy, затем общий validation; не создаёт мир/timeline и не читает wall-clock. Runtime raw wire admission — общий resolver, не самописный parse внутри pipeline. Optional origin касается только STANDARD; не ослабляет обязательный custom start. Records в timeOperations/initial.py, implementation в preparation/initialPipelineOpenPipeline.py, counts не меняются.

Историческое предложение: defaults подписей, сезонов и периодов заменены решениями раздела выполнения и docs/tz_time.md. Canonical data proposal для freeze: system_calendar=`gregorian`; spans january…december с display January…December, role MONTH и lengths 31/28/31/30/31/30/31/31/30/31/30/31; counts_in_week=True; seasons registry пустой и span.season=None (нет незаказанного hemisphere/climate решения); periods registry содержит одну запись system_period=`day`, display_period=`Day`, from_hour=0; weekdays monday…sunday с English display names; numbering NO_YEAR_ZERO; week anchor — Gregorian 1970-01-01 ordinal, index3 (Thursday при Monday index0). Display names — canonical World data, локализация может заменить их; пользовательский календарь не наследует эти names автоматически. Epoch registry по умолчанию пустой; исторические эпохи автор задаёт N+1. Эти конкретные defaults являются **предложением к приёмке**, не ранее принятым продуктовым решением. Они не вводятся в code/fixtures этим заданием.

Нормализованный settings fingerprint строится existing canonical codec, не JSON repr/hash внутри Time. Повтор initial operation использует тот же captured UTC и input; изменение данных под тем же operation ID — отказ external publication ledger. Transport-generated новые IDs/захват now на retry запрещены контрактом orchestration, но не проверяются pure initializer как durable state.

Finding 32.1 закрыт **на уровне schema proposal** этим разделом; accepted freeze требует пользовательской приёмки. Остаточные findings 32.2/32.3 сохранены: это external integration и решения по предлагаемой grammar/defaults, а не недописанные полевые заглушки initial-input.

## 34. Exact proposal: publication-bound Time lifecycle storage

Повторно проверены `IWorldPublicationStore.compare_append`, `IWorldPublicationInitializer.initialize`, `CommitScope/CommitReadScope` и `WorldPublicationRef`. Existing initializer создаёт публикацию, не Time state; доступен только lifecycle owner. Новые внутренние binding contracts ниже расширяют его domain-state integration, но не дают Time право открывать transaction или менять publication head.

### 34.1. Конкретные POJO и внутренние методы

В `dataModel/time/storage/lifecycle.py` (storage leaf: state/append/initial/lifecycle + init = 5):

- **InitialClockBinding(operation_id:EntityUid, expected:WorldPublicationRef, target:WorldPublicationRef, state:TimeClockState)**. expected.gameplay_started=False; target.gameplay_started=True, head=None; world одинаков; target.active_timeline_id=state.point.timeline_id; state coordinate=0. Target publication ID отличается от expected.
- **BranchClockBinding(operation_id:EntityUid, expected:WorldPublicationRef, target:WorldPublicationRef, source:StoredTimeState, state:TimeClockState)**. target.gameplay_started=True, target.snapshot_head не None, expected/target/source/state принадлежат одному world; target.publication_id!=expected.publication_id. Target active timeline отличается от source.ref.snapshot.timeline_id; target.head — выбранный Snapshot branch point; совпадение world; state coordinate=source.state.point coordinate, timeline=target active. Source state ref может быть унаследованным предшественником branch point, поэтому equality source snapshot=target.head **не требуется**; ancestry/effective state проверяет Snapshot reader.
- **ClockBindingStored(publication:WorldPublicationRef)** — acknowledgement записи в scope, не accepted result.
- **ClockBindingConflict(expected:WorldPublicationRef, observed:WorldPublicationRef)** — actual precondition conflict; durable outcome не утверждает.

В `application/time/storage/lifecyclePort.py` (statePort/lifecyclePort + init = 3):

**IBoundTimeLifecycleWriter**:

- `append_initial(InitialClockBinding) → ClockBindingStored | ClockBindingConflict`;
- `append_branch(BranchClockBinding) → ClockBindingStored | ClockBindingConflict`.

**ITimeLifecycleBinding.bind(scope:CommitScope) → IBoundTimeLifecycleWriter** — синхронная конкретизация existing IDomainCommitBinding. Только append/read методы async; внешнее scope остаётся единственным transaction owner. Writer append-only; target publication ref + world уникально адресуют domain clock binding. Повтор в одной transaction с тем же payload не создаёт вторую запись; несовпадающий payload под тем же target — integrity fault. Cross-request idempotency выполняет Publication ledger, не Time writer.

**ITimePublicationStateReader.read(publication:WorldPublicationRef, scope:CommitReadScope) → PublicationTimeState | None**, в том же lifecyclePort.py. Читает именно domain binding указанной публикации, не current/latest и не fallback к World.current_tick. Кандидат, не прошедший общий commit, не доступен внешнему read scope. SQL encoding/таблицы остаются задачей отдельного storage implementation slice по 0001+model sync, но внешний контракт не зависит от их имён.

### 34.2. Fixed внешние lifecycle flows

**Initial:** DAG передаёт PreparedInitialSettings и operation identity внешнему World/gameplay-start API. Snapshot/Publication owner открывает commit scope, повторно проверяет expected, назначает target publication/timeline, применяет World settings binding, вызывает Time append_initial, CAS compare_append и record_terminal(GameplayStarted) в том же scope. Отказ любого участника отменяет всё. Time не вызывает World writer или compare_append. Core Time tests используют contract adapter, не имитацию принятия всей игры.

**Branch:** Snapshot выбирает retained branch point и его effective state/settings, проверяет ancestry/authorization, назначает новую timeline/target publication, вызывает pure rebind и Time append_branch в общей transaction; World settings branch projection связывается с сохранённой версией. CAS head и terminal branch outcome принадлежат Snapshot. **Existing OperationKind не содержит branch**: branch public request/result/ledger-kind extension должен быть утверждён Snapshot owner; этот Time binding не добавляет его молча и не выдаёт GameplayStarted за branch receipt. Это конкретный внешний dependency, не недописанная Time storage signature.

**Restore существующей ветки:** Snapshot переключает active publication на retained выбранную точку, read разрешает effective Time state через metadata. Если target head timeline совпадает с state timeline, rebind не нужен. Если нужно продолжить альтернативную историю — branch flow. Time.set_clock отсутствует.

**Advance после initial/branch:** TimeReader сначала получает expected publication под pinned scope. При head=None читает publication-bound state. При head другого timeline (закреплённая branch point) читает принятый branch binding, не возвращает точку с чужой timeline. При обычном head читает Time state ref из snapshot metadata. Все три случая — fixed read resolution по принятому storage layout, не выбор gameplay operation. First accepted advance пишет snapshot-bound Time state; old initial/branch binding удерживается общим retention, не удаляется при первом read.

### 34.3. Receipt и ошибки runtime advance

В §18 ранее OPEN changed PatchRef конкретизируется: один TimeAdvanceSection содержит один proposal, поэтому `PatchRef(operation_id=proposal.operation_id, section_key=handler.contract.key, ordinal=0)`; ordinal использует existing PatchOrdinal (>=0). SectionApplyReceipt.changed содержит ровно этот ref, state_refs/history_refs — назначенные refs нового snapshot, retained_artifacts=() при row-only storage. Если backend выберет artifact storage, exact artifact refs должны быть добавлены в отдельном согласованном slice, не скрыты empty tuple. Receipt по-прежнему не commit proof.

Contract/fault boundary: malformed binding → structural admission; stale expected → ClockBindingConflict; отсутствующий required retained state/битая ancestry → infrastructure integrity failure; отсутствие optional initial record до gameplay → TimeStateUnavailable(CLOCK_UNINITIALIZED). Cancel/unknown commit не переводить в domain refusal. Snapshot recovery выполняет существующий OperationLedger; Time не создаёт recovery coroutine/retry loop.

## 35. Итог проверки документа и пакет приёмки

T2-TZ: exact schema/API candidate §§29–33 предъявлен; T-RULE проверен повторно с §34. Оставшиеся вопросы теперь разделены:

| Категория | Итог |
|---|---|
| Core values/advance | Typed contracts, errors, scope, idempotency boundary и storage seams предъявлены; нужны приёмка и отдельное разрешение реализации |
| Calendar/settings | Конкретный закрытый enum/POJO/API candidate предъявлен; требуется пользовательская приёмка grammar и canonical defaults. Это не принятие «любых неизвестных алгоритмов» |
| Initial/branch Time binding | Точные внутренние Input/Output/ports §34; Snapshot branch public lifecycle/ledger-kind extension — явно внешний integration prerequisite |
| ActionCore | DEFERRED по указанию пользователя |
| UI номер хода | External chat/GEN contract, без присвоения Time; сохраняется requirement отображения вместе с точным world time |
| Legacy | [TIME-DEBT-01…06](./time-domain-review-debt.md), реализация после core; документальный evidence не превращён в требование сначала мигрировать код |
| Неприменимые сейчас проверки | Runtime concurrency/durability/typing/fixtures/SQL tests не запускались, поскольку код не создаётся |

Для rule audit exact storage binding отдельно от production SQL layout: последний не выбирается внутри core implementation и требует собственного согласованного storage slice. Ссылки на существующие interfaces: [publicationStore](../../backend/app/application/worldSnapshot/storage/publicationStore.py), [commitScope](../../backend/app/application/worldSnapshot/contracts/commitScope.py), [OperationLedger](../../backend/app/application/publication/service/operationLedger.py), [SectionApplyReceipt](../../backend/app/dataModel/patch/results/sectionResult.py), [PatchRef](../../backend/app/dataModel/patch/changes/header.py). Legacy audit с определениями/callers/disposition — linked debt ledger; coverage limits сохранены.

**Verdict: specification candidate ready for user review, NOT implementation approval.** Полный blanket PASS не выставляется: календарные новые решения ещё не приняты, внешние Snapshot branch/UI contracts не закрыты. Отложенные внешние contracts не блокируют review независимого Time core. Предложенный порядок: принять core; принять/скорректировать calendar settings candidate; отдельно согласовать Snapshot integration; реализовывать только явно разрешённые slices; migration после core.

На пользовательскую приёмку, без повторного открытия уже принятых решений: (1) закрытый набор календарных operators §29 и модель версий/anchors; (2) canonical numbering/display/period defaults §33; (3) exact public settings API §30/33; (4) Time lifecycle/storage contract §34. Согласие на продолжение исследования не считается принятием этих конкретных choices.

## 36. Аудит точности POJO и явности contract bindings

### 36.1. Исправленные неточности

| Находка | Исправление / влияние |
|---|---|
| Reverse API использовал scope:TimePoint с игнорируемой координатой | В §29.4 введён TimeScope(world_uid,timeline_id); value-only identity в том же point.py. Не передавать фиктивный нулевой момент |
| CalendarTimeOverflow требовал point, которого при overflow результата ещё нет | Поле заменено operation:CalendarConversionKind(PROJECT/RESOLVE), enum и файл указаны; input остаётся известен caller |
| SettingsCapture не содержал calendar version provenance, хотя следующий Input его требовал | Оба capture в §30 содержат versions:tuple[CalendarVersionRef,...]; world/coverage/unique invariants обязательны |
| Старый PrepareInitialSettings конкурировал с tagged Input §33 | Удалена прежняя signature из активного §30; один Input с STANDARD/AUTHORED |
| Все lifecycle методы были названы async, включая bind | bind синхронный как existing IDomainCommitBinding; IO read/append async |
| BranchClockBinding не фиксировал started/head/world coherence | Дополнены обязательные target/expected/state invariants в §34.1 |

### 36.2. Явные producers, consumers и source guards

**ITimeReadSource** — producer TimeCapture/HistoricalTimeCapture; возвращает read outcomes §11. **IWorldTimeSettingsSource** — ранее лишь имя: теперь фиксируются два async метода `read_current(TimeSettingsRead) → TimeSettingsCapture | SettingsConflict | SettingsNotFound` и `read_historical(HistoricalTimeSettingsRead) → HistoricalTimeSettingsCapture | SettingsNotFound | SettingsSnapshotNotFound`. Port в application/worldData/timeSettings/sourcePort.py. Domain public reader делегирует ему pinned IO; не создаёт default settings при missing stored state. SettingsNotFound относится к отсутствующему world/settings; отсутствующий retained snapshot требует отдельного **SettingsSnapshotNotFound(snapshot:WorldSnapshotRef)** в results.py и добавляется только в historical result union (как порта, так и public API).

**WorldCalendarResolver.resolve_at** — pure boundary, явный producer ResolvedCalendarAt вместо неописанного преобразования DAG. Input **ResolveCalendarAt(capture:TimeSettingsCapture | HistoricalTimeSettingsCapture, calendar:Key[WorldCalendarRegistry])**; output **ResolvedCalendarAt | SettingsInvalid**. Проверяет membership, выбирает соответствующий version из capture. Ни independent latest read, ни конструирование версии по current publication. Класс в application/worldData/timeSettings/reader.py, Input в timeOperations/read.py; число файлов не меняется. Внешний DAG вызывает его явно либо переиспользует опубликованный результат; Time projector не вызывает resolver скрытно.

Current source проверяется по capture.publication, historical — по capture.snapshot, типы source/capture должны соответствовать. ResolvedCalendarAt.version.calendar_key=input.calendar, version publication принадлежит тому же world; применимость версии на source гарантирует World reader, не модель с произвольным publication ref. Pure projection проверяет согласованность supplied values, **не доказывает подлинность refs**. Application acceptance повторно читает trusted base под CommitReadScope; от клиента не принимается POJO как доказательство принятого состояния.

Projection Input.point не обязан равняться capture.point: можно чисто проектировать конец ещё не принятого интервала. Обязательны одинаковые world/timeline и явно переданная версия; output не сообщает, что future point принят. Capture=start остаётся требованием соответствующего Physics Input, не универсальным правилом календарной проекции. Для исторического отображения по действовавшей версии DAG получает historical capture на нужном snapshot, а не выбирает current settings по одной numeric coordinate. В этой операции CalendarPointMismatch означает **scope mismatch**; во избежание ложного equality переименовать в **CalendarScopeMismatch(expected:TimeScope, actual:TimeScope)** в active §29.4.

### 36.3. Явная validation операция вместо скрытой зависимости

CalendarBudget уже присутствует в preparation, но standalone typed validation не был описан. Proposed public pure **CalendarValidator.validate(ValidateCalendarInput) → CalendarValidated | CalendarInvalid | CalendarBudgetExceeded**. Input **ValidateCalendarInput(settings:WorldTimeSettings,budget:CalendarBudget)**, success **CalendarValidated(settings:WorldTimeSettings)**; models в calendar/projection/request.py/result.py, class в application/time/calendar/validation.py. Это deep calendar semantic validation, не новый field-policy resolver. World owning resolver выполняет structural/REF-W policies; fixed preparation pipeline явно вызывает pure calendar validation как внутренний алгоритм своей операции. Не маршрутизировать весь World CRUD через validator и не добавлять retry/fallback.

Этот вызов может исчерпать budget у любой settings preparation, если она валидирует полный candidate. Поэтому **CalendarBudgetExceeded входит в result union всех prepare_* settings операций §30**, включая select/remove/epoch. Structural errors → SettingsInvalid через явное преобразование CalendarInvalid.issues; не по тексту exception. Scope/provenance mismatch у SettingsPreparationBase — structural/coherence admission, stale durable publication — external acceptance conflict. Snapshot refused не маскируется successful PreparedTimeSettingsChange.

### 36.4. Неполноты, которые нельзя объявить исправленными именованием

- CalendarVersionRef привязан к publication; readonly POJO не делает version действительной. Source ports должны получить actual implementation proof при integration; нужны rejection tests forged/stale refs.
- World settings acceptance ещё не имеет здесь concrete World section/handler/storage transaction contract. PreparedTimeSettingsChange — подготовка, не применённая настройка. World section/storage binding предложен в §37, с явным внешним prerequisite next_publication; не Time writer и не доказанная production integration. Public preparation API можно принимать отдельно; production settings mutation нельзя.
- InitialClockBinding/BranchClockBinding требуют внешнего gameplay/branch authorization и assigned refs. Их поля не заменяют Snapshot guard; branch external ledger/result contract остаётся OPEN.
- Generic IWorldTimeSettings из §30 — интерфейс операций, не описанная универсальная dispatcher implementation. Фабрика требует явных bindings каждой фиксированной операции; конструирование всех pipelines по одному reader без dependencies не считать достаточной DI map. Pure/domain factory signatures уточнены в §38; handler encoding integration остаётся отдельным prerequisite.
- Default/nullable policies пока указаны полностью только у settings initial boundary; перед accepted freeze каждого authored leaf §29 требуется полевая policy matrix (StrictOnWire/DefaultWhenMissing и missing/null/empty), без догадок из Python optional. Отсутствие default означает required, но это должно быть отражено в owning annotations. Полевая matrix добавлена в §39; это не разрешение defaults в consumers.

Verdict данного review: конкретные data-flow ошибки исправлены, неявные source/validation bindings раскрыты; **полный POJO/contract freeze ещё не PASS** из-за перечисленных точных gaps. Review не подменяет пользовательскую приёмку и не даёт права закрывать World/Snapshot foreign contracts вымышленными типами.

## 37. World settings acceptance — точный предложенный binding

Этот раздел — proposal внешнему World owner внутри разрешённого документа. Не означает наличия production handler. Использует existing DomainSectionHandler, SectionApplyReceipt, CommitScope и IDomainCommitBinding; не вводит отдельный commit.

### 37.1. Runtime section/state

`dataModel/world/settings/timePublication/section.py`: **WorldTimeSettingsSection(DomainSection[PreparedTimeSettingsChange])**, ровно один patch. Existing SectionHeader, section key регистрируется в PatchSectionRegistry; proposed key=`world_time_settings`, format_version=1. Time clock section отдельно, proposed key=`time_clock`, format_version=1. Оба keys — SectionKey, не свободные строки в consumers; collision проверяется при composition. Canonical numeric manifest IDs не назначаются здесь произвольно: reservation отдельным encoding integration gate, а не выбор в коде доменной модели.

`timePublication/state.py`: **StoredWorldTimeSettings(ref:SectionStateRef, settings:WorldTimeSettings, versions:tuple[CalendarVersionRef,...])**. Ref только WorldSnapshotRef; section key соответствует handler; versions покрывают все calendar keys ровно один раз. Version witness включает часы/epoch/anchor, влияющие на projection; изменение часов обновляет версии всех calendars. Для неизменённых calendars при частичном update version сохраняется. Принятую version publication назначает Snapshot acceptance, не preparation.

`timePublication/append.py`: **WorldSettingsAppend(operation_id:EntityUid, snapshot:WorldSnapshotRef, target:WorldPublicationRef, proposal:PreparedTimeSettingsChange)**; **WorldSettingsAppended(state_ref:SectionStateRef, history_ref:SectionHistoryRef)**; **WorldSettingsAppendConflict(expected:WorldPublicationRef, observed:WorldPublicationRef)**. Target snapshot_head=snapshot, same world, operation IDs совпадают. PreparedTimeSettingsChange.before сравнивается с фактическим pinned accepted settings; поддельный before не является CAS evidence.

`application/worldData/timeSettings/storage/statePort.py`:

- async **IWorldSettingsStateReader.read(ref:SectionStateRef, scope:CommitReadScope) → StoredWorldTimeSettings | None**;
- async **IBoundWorldSettingsWriter.append(WorldSettingsAppend) → WorldSettingsAppended | WorldSettingsAppendConflict**;
- sync **IWorldSettingsCommitBinding.bind(scope:CommitScope) → IBoundWorldSettingsWriter**.

`application/worldData/timeSettings/integration/sectionHandler.py`: **WorldTimeSettingsSectionHandler** specializes DomainSectionHandler[WorldTimeSettingsSection]. Exact validate/apply/encode/decode signatures — existing interface с этим concrete S. Validate читает accepted settings и Time state через explicit scoped ports, проверяет expected/base/effective_at и candidate. Apply использует assigned snapshot/target publication context и bound writer; receipt.changed содержит PatchRef(operation_id,contract.key,0), state/history refs, artifacts=() только для row-only backend. Writer не коммитит; Snapshot атомарно принимает World settings и прочие effects.

**Внешний context prerequisite:** existing SnapshotApplyContext не содержит target WorldPublicationRef. Нужно либо передать его явно в typed World handler binding, либо расширить общий context владельцем Snapshot. Предлагается конкретное расширение **SnapshotApplyContext.next_publication:WorldPublicationRef**, согласованное с assigned world_snapshot и expected_world. Это requirement к owner, не объявление уже существующего поля. До его принятия этот handler integration BLOCKED; нельзя reconstruct target publication ID внутри домена.

### 37.2. Headless settings binding

`timePublication/lifecycle.py`: **InitialSettingsBinding(operation_id:EntityUid, expected:WorldPublicationRef, target:WorldPublicationRef, prepared:PreparedInitialSettings)** и **BranchSettingsBinding(operation_id:EntityUid, expected:WorldPublicationRef, target:WorldPublicationRef, source:HistoricalTimeSettingsCapture)**. Same-world/operation checks; target started; initial head=None; branch target.head=source.source и target.active_timeline_id новая ветка. Snapshot подтверждает ancestry. **PublicationWorldSettings(publication:WorldPublicationRef, settings:WorldTimeSettings, versions:tuple[CalendarVersionRef,...])** — read state для headless/pinned-parent publication.

`storage/lifecyclePort.py`: **IBoundWorldSettingsLifecycleWriter.append_initial(InitialSettingsBinding)** и **append_branch(BranchSettingsBinding)**, оба async → **WorldSettingsBindingStored(publication:WorldPublicationRef) | WorldSettingsAppendConflict**; **IWorldSettingsLifecycleBinding.bind(CommitScope) → IBoundWorldSettingsLifecycleWriter** sync; **IWorldSettingsPublicationReader.read(WorldPublicationRef,CommitReadScope) → PublicationWorldSettings | None** async. WorldSettingsBindingStored объявлен в timePublication/lifecycle.py. Source settings immutable, branch не пересчитывает origin/now. Контракт target.ref назначает lifecycle owner. Root facts/settings clock пишутся вместе в общем scope (§34).

Отказ validation → existing SectionRefused с typed FieldPathError; budget exhaustion → явный отказ до append, не частичная запись. **Acceptance budget** — обязательный CalendarBudget, внедрённый в handler factory, не persisted setting и не неограниченный default. Claimed operation outcome/retry остаётся Publication ledger. Calendar clock не сдвигается при settings-only change.

File counts: timePublication section/state/append/lifecycle + init = 5; application storage statePort/lifecyclePort + init = 3; integration sectionHandler + init = 2. Все paths World-owned. Concrete SQL schema/adapter freeze отдельно до storage реализации; runtime state не хранится в legacy calendar dict.

## 38. Явная DI-композиция без универсального dispatcher

Фабрика `make_world_time_settings(reader)->IWorldTimeSettings` из §30 **SUPERSEDED**: скрывала необходимые pure dependencies. IWorldTimeSettings остаётся инвентарём typed методов, не обязательной mega-facade. DAG composition получает отдельные конкретные операции:

| Factory (sync) | Результат / методы |
|---|---|
| make_time_reader(source:ITimeReadSource) | TimeReader; read_current/read_historical §11 |
| make_time_advance_pipeline() | ITimeAdvancePipelineOpenPipeline; prepare_advance §11, pure |
| make_calendar_projector() | CalendarProjector; project/resolve §29.4, pure |
| make_calendar_validator() | CalendarValidator; validate §36.3, pure |
| make_world_settings_reader(source:IWorldTimeSettingsSource) | WorldTimeSettingsReader; две read signatures §36.2 |
| make_calendar_settings_pipeline(validator:CalendarValidator,projector:CalendarProjector) | WorldCalendarSettingsPipelineOpenPipeline; prepare_calendar_create/update/select/remove, exact requests/results §30 |
| make_epoch_settings_pipeline(validator:CalendarValidator) | WorldEpochSettingsPipelineOpenPipeline; prepare_epoch_create/update/remove §30 |
| make_hours_settings_pipeline(validator:CalendarValidator,projector:CalendarProjector) | WorldHoursSettingsPipelineOpenPipeline; prepare_hours_change §30 |
| make_initial_settings_pipeline(validator:CalendarValidator) | WorldInitialTimeSettingsPipelineOpenPipeline; prepare_initial §33 |

Каждый метод — фиксированная public operation; несколько методов одного typed класса не разрешают execute(kind,payload) и взаимные вызовы чужих CRUD. Общие pure validation/calculation helpers допустимы. Канонические defaults — owning POJO factory, не factory DI defaults. WorldCalendarResolver.resolve_at — pure static operation reader.py, не требует service lookup. Factories находятся в существующих proposed composition/factory.py (Time) и timeSettings/factory.py (World), counts не меняются.

Handler DI — отдельная integration factory, не DAG operation. **make_time_section_handler(contract:SectionContract[TimeAdvanceSection], reader:ITimeStateReader, publication_reader:ITimePublicationStateReader, binding:ITimeCommitBinding) → TimeSectionHandler**; publication reader обязателен для состояния до первого snapshot. **make_world_settings_section_handler(contract:SectionContract[WorldTimeSettingsSection], reader:IWorldSettingsStateReader, publication_reader:IWorldSettingsPublicationReader, clock_reader:ITimeStateReader, clock_publication_reader:ITimePublicationStateReader, binding:IWorldSettingsCommitBinding, validator:CalendarValidator, projector:CalendarProjector, budget:CalendarBudget) → WorldTimeSettingsSectionHandler**. Все зависимости типизированы; reader'ы работают только под supplied scope. Кодирование использует existing canonical codec через явный encoding binding, **его точная сигнатура остаётся encoding integration prerequisite**, не скрытый global import. Handler contract manifest/version обязан быть зарегистрирован до активации; class existence не доказывает codec readiness.

## 39. Полевая policy matrix календарного authored input

Матрица относится к **всем** полям §29.2/§33, не оставляет неявных defaults. Поля runtime request/result/capture/receipt не являются authored settings: они strict required, extra-forbid; nullable только там, где явно указан None. Wire enum operations tagged concrete Literal, enum constraints сохраняются.

| Группа полей | Missing / null / empty / policy |
|---|---|
| WorldTimeSettings.hours_per_day; StandardTimeSettingsInput.hours_per_day | Missing→24, null invalid, strict positive int; DefaultWhenMissing |
| StandardTimeSettingsInput.origin | Missing/explicit null→штатный capture-current sentinel; DefaultWhenMissing[CalendarOrigin|None]=None. Только STANDARD |
| Все остальные поля settings/definitions/entries/rules/origins/epochs и AuthoredTimeSettingsInput.settings | StrictOnWire; missing invalid. Никаких defaults из предполагаемого «обычного» календаря |
| CalendarSpan.season; InsertSpanRule.after | Required nullable: missing invalid, null означает нет сезона / вставку в начало. Non-null RegistryKey membership обязательно |
| Enum поля numbering/week_mode/role; initialization.kind и rule/predicate.kind | Required, strict closed value; null/unknown invalid; Literal-discriminator с enum member, не arbitrary str |
| description | Required Text; пустая строка допустима как отсутствие описания, null invalid |
| display_* | Required Text непустой после проверки whitespace; null/empty invalid; не использовать label как key |
| system_* и refs | Required typed RegistryKey, непустой snake_case; null только у двух явно nullable полей выше; actual membership REF-W |
| calendars.entries / definition.base_year / spans.entries / periods.entries | Required nonempty tuples; null invalid; unique IDs/occurrences |
| weekdays.entries / seasons.entries / epochs.entries / rules / condition.all_of / condition.none_of | Required tuples; empty допустимо по §29 semantics, null invalid |
| Integer/boolean fields | Required strict type/range, null invalid; bool не int; никакого numeric-string coerce в domain |

Registry wrappers имеют единственное required entries, не root-list с неявным преобразованием. CalendarEntry.definition/anchor required, origin.date/time required; `AuthoredTimeSettingsInput` не принимает missing custom start. WorldTimeSettings.selected обязан существовать. Registry tuple ordering сохраняется для правил/месяцев/недели; no sort по именам во время normalize. Unknown extra fields отвергаются; N+1 означает новые **entries**, не непредусмотренные поля payload.

Для patch preparation omission не означает reset/default: runtime Update requests содержат полный typed entry или конкретный scalar change (§30). Generic JSON patch должен быть разрешён World boundary в полный validated candidate до этих операций. Нет скрытого partial dict в Time API. Serialized I64 transport policy §29.3 не распространяется автоматически на calendar arbitrary Int — **для всех целочисленных transport fields** требуется единый lossless codec policy; предлагается decimal-string wire для integer quantities, JSON numbers для bounded enum-independent small fields только по explicit schema. До transport freeze нельзя считать HTTP контракт закрытым этим Python POJO.

## 40. Результат уточнения трёх блоков

На уровне proposal закрыты: World settings section/state/lifecycle schemas и scoped acceptance ports (§37), pure/domain DI map (§38), authored missing/null/empty/default matrix (§39). Матрица не выдаёт новые defaults за принятые пользователем. Поддельные capture/refs не становятся trusted через constructor; acceptance readers подтверждают их под scope.

Оставшиеся **явные integration prerequisites**, а не неявное применение POJO: SnapshotApplyContext.next_publication owner approval; branch public outcome/operation kind; canonical codec binding/schema IDs; lossless transport encoding; concrete SQL storage slice. Их нельзя изобрести внутри core реализации. ActionCore по-прежнему deferred, legacy migration после core. **Blanket CODE-READY/PASS не выставляется**, но эти зависимости теперь названы на уровне конкретных полей/портов и не скрыты в DI/defaults.

## 41. Encoding bindings без отдельного механизма Time

Evidence: [canonicalCodec.py](../../backend/app/application/encoding/canonicalCodec.py) уже кодирует integer как sign+magnitude произвольной длины, проверяет frozen models и registered concrete types; [schemaManifest.py](../../backend/app/dataModel/encoding/schemaManifest.py) задаёт explicit type identities; [SnapshotEnvelopeCodec](../../backend/app/application/worldSnapshot/encoding/snapshotCodec.py) показывает reuse canonical encode/decode и проверку version/type. SnapshotEnvelopeCodec кодирует metadata, не Time payload: его нельзя использовать как domain state codec.

### 41.1. Exact proposed domain codecs

Новые concrete wrappers используют existing canonical functions; новый сериализатор не создаётся. Ошибки всех wrappers — existing CanonicalEncodingError для invalid/noncanonical bytes, unsupported version/root type; cancellation не перехватывается. Никаких object/Any в public domain signatures.

| Класс / файл относительно backend/app | Методы |
|---|---|
| TimeSectionCodec / application/time/encoding/sectionCodec.py | encode(TimeAdvanceSection)→bytes; decode(payload:bytes,version:FormatVersion)→TimeAdvanceSection |
| TimeStateCodec / application/time/encoding/stateCodec.py | encode(TimeClockState)→bytes; decode(payload:bytes,version:FormatVersion)→TimeClockState |
| WorldTimeSettingsSectionCodec / application/worldData/timeSettings/encoding/sectionCodec.py | encode(WorldTimeSettingsSection)→bytes; decode(payload:bytes,version:FormatVersion)→WorldTimeSettingsSection |
| WorldTimeSettingsStateCodec / application/worldData/timeSettings/encoding/stateCodec.py | encode(WorldTimeSettings)→bytes; decode(payload:bytes,version:FormatVersion)→WorldTimeSettings |

Each constructor `(manifest:CanonicalSchemaManifest)`; supported version ровно 1, не default coercion. После decode — exact root type и owning POJO structural validation, затем semantic validation на соответствующей boundary с typed dependencies/budget. Byte equality re-encode проверяется existing canonical mechanism/owner wrapper; не доверять произвольному pickle/import-by-name.

Manifest files: application/time/encoding/manifest.py и application/worldData/timeSettings/encoding/manifest.py. Обе encoding leaf папки sectionCodec/stateCodec/manifest/init = 4 файла. Time manifest включает transitive Time values/capture/proposal/section + существующие shared identity/publication records. World manifest включает World settings/rules/enums и transitive Time/shared records. Merge через existing merge_manifests, не копировать shared entries с новыми IDs. Manifest должен закрыть все reachable serialized types, включая enum discriminators. Schema IDs и numeric type IDs — разные сущности.

**Handler factory уточнение §38:** make_time_section_handler получает обязательный `codec:TimeSectionCodec`; make_world_settings_section_handler — `codec:WorldTimeSettingsSectionCodec`. Handler.encode/decode делегируют только этому codec. State codecs внедряются в concrete storage adapters при их freeze. SectionContract.manifest обязан совпадать с merged codec manifest по identities; mismatch останавливает composition до запуска DAG.

Numeric type-id reservation не закрывается подстановкой диапазона наугад. Отдельный атомарный encoding registry шаг должен предъявить полный список type→ID и проверить collisions по всем manifests до codec implementation. Изолированная pure arithmetic не зависит от этой registration; persisted/public serialized operations зависят. Это точная граница readiness, а не скрытый TODO в codec constructor.

### 41.2. Transport contract, отдельный от canonical storage

Все application/calendar integers остаются strict int. Для **новых** Time/settings JSON DTO предлагается единая однозначная policy: все integer quantity/index/year/budget fields — canonical decimal strings; enums — строковые enum values; bool — JSON bool; tuple — JSON array; refs — структурированные DTO existing owners. Negative zero, leading plus, leading zeros кроме `0`, exponent/fraction и whitespace отвергаются. Bounds проверяет owning POJO после lossless parse. Existing shared refs не переопределяются целиком этим правилом: их transport schema переиспользуется владельцем API.

Это **новый DTO proposal**, не молчаливое изменение existing world import number encoding. Existing endpoints/URLs требуют API-1 compatibility review; старый импорт сначала проходит явно версионированный adapter/migration contract. Новый codec не обходит общий settings resolver и не создаёт raw dict public API. Конкретные endpoint DTO и adapters принадлежат app/api, фиксируются после GEN invocation binding; Time/domain signatures не получают FastAPI/HTTP dependencies.

Проверки будущего encoding slice: min/max I64; arbitrary календарный year больше JS safe integer; nanosecond roundtrip; strict zero/negative-zero; unknown enum/version; manifest collision/missing type; capture/proposal fingerprint stability; decoded payload не trusted acceptance evidence. Это ещё не выполненные runtime tests.

## 42. Актуальные gates после encoding review

На уровне документа определены точные codec classes, signatures, injection и reuse shared serialization. Техдолг остаётся после core. Следующие внешние/регистрационные задачи не превращаются в новый Time механизм:

1. Encoding IDs: отдельный проверенный manifest reservation до serialized core implementation.
2. Snapshot: owner принимает next_publication context и branch outcome/operation-kind contract; внутренние Time/World payloads уже описаны.
3. API/GEN: lossless DTO compatibility и exact node invocation принимаются совместно; никаких concrete nodes/routes в этом задании.
4. Storage: отдельный DDL/model/adapter freeze по текущим правилам до storage реализации.

User acceptance остаётся отдельным gate для предложенных calendar grammar/defaults/API. Текущий документ — reviewable specification, а не доказательство полной production готовности. Новые enum/POJO definitions и runtime registration не создавались.

## 43. Encoding reservation proposal

Поиск числовых литералов 31000–31199 в backend/app, plans и docs не дал совпадений на момент проверки. Это ограниченное collision evidence, не глобальное резервирование registry. Предлагаются следующие **стабильные** IDs для persisted roots и их transitive dependencies; номера не вычислять из позиции класса в списке при реализации.

| ID | Concrete type |
|---|---|
| 31000–31006 | По порядку: CalendarPredicateKind=31000, CalendarEditKind=31001, CalendarWeekMode=31002, CalendarNumbering=31003, CalendarSpanRole=31004, CalendarInitializationKind=31005, CalendarConversionKind=31006 |
| 31100–31106 | TimePoint=31100, TimeDuration=31101, TimeInterval=31102, TimeCapture=31103, TimeAdvanceProposal=31104, TimeAdvanceSection=31105, TimeClockState=31106 |
| 31110–31117 | SpanEntry=31110, CalendarSpanRegistry=31111, WeekdayEntry=31112, CalendarWeekdayRegistry=31113, SeasonEntry=31114, CalendarSeasonRegistry=31115, PeriodEntry=31116, CalendarPeriodRegistry=31117 |
| 31118–31125 | CalendarSpan=31118, AlwaysPredicate=31119, YearModuloPredicate=31120, YearRangePredicate=31121, CalendarCondition=31122, InsertSpanRule=31123, ReplaceSpanRule=31124, RemoveSpanRule=31125 |
| 31126–31135 | CalendarDefinition=31126, CalendarEntry=31127, WorldCalendarRegistry=31128, CalendarDate=31129, CalendarClockTime=31130, CalendarOrigin=31131, CalendarAnchor=31132, WorldCalendarEpoch=31133, WorldCalendarEpochRegistry=31134, WorldTimeSettings=31135 |
| 31136–31138 | PreparedTimeSettingsChange=31136, WorldTimeSettingsSection=31137, CalendarVersionRef=31138 |

Existing shared WorldPublicationRef/WorldSnapshotRef/SectionHeader and their dependencies retain existing IDs; no re-registration under 31xxx. IDs 31000–31006 ENUM, listed 311xx RECORD. Admission-only requests/results без durable encoding не требуют ID только потому, что являются POJO; при persist в DAG runtime owning registry отдельно должен перечислить их, не сериализовать незарегистрированное значение. State rows versions tuple сериализуется с manifest, содержащим CalendarVersionRef и shared refs. Merge-manifest collision и missing reachable type проверки обязательны до codec implementation. Зарезервированные номера считаются предложенными до принятия common registry owner.

## 44. Storage design candidate — без DDL реализации

Проверены existing WorldPublicationRow/WorldSnapshotRow и composite owner FKs в 0001_initial.sql. Domain storage использует immutable записи и ссылки, а не UPDATE worlds.calendar/current_tick. Ниже **предлагаемые таблицы**, код SQL не создаётся.

Общий layout для четырёх snapshot row families (`time_snapshot_states`, `time_snapshot_history`, `world_time_settings_snapshot_states`, `world_time_settings_snapshot_history`): ключ snapshot_id TEXT PK; world_uid TEXT; operation_id TEXT; format_version INTEGER>0; payload BLOB canonical; checksum TEXT 64 lowercase hex. Composite FK (world_uid,snapshot_id)→world_snapshots, (world_uid,operation_id)→publication_operations; NOT NULL везде. State payload — TimeClockState/WorldTimeSettings; history payload — соответствующая concrete section. Settings state дополнительно versions BLOB (canonical tuple[CalendarVersionRef,...]), а не ещё одна копия WorldTimeSettings. Snapshot+operation ownership сверяется с metadata row; append в едином CommitScope.

Headless/branch bindings: `time_publication_states` и `world_time_settings_publication_states`, аналогичные колонки, но publication_id вместо snapshot_id и composite FK (world_uid,publication_id)→world_publications. Payload types те же; settings versions BLOB. Привязка timeline выводится из typed state/target publication и проверяется на write/read; column shadow clock не вводится. Все records immutable; UPDATE/REPLACE запрещены. Delete только в существующем retained-history cleanup lifecycle после проверки refs; Time не предоставляет публичный delete.

Порядок ссылок в transaction: coordinator сохраняет assigned parent metadata/publication row до domain binding либо использует согласованные deferred FK; нельзя делать преждевременный отдельный commit ради FK. Конкретный вариант должен быть принят Snapshot storage owner, поскольку compare_append ранее выполнялся после append; этот план не утверждает текущий порядок совместимым без изменения. Atomicity proof включает rollback обеих записей и unknown commit outcome. Это integration constraint, не скрытая операция домена.

Row classes: `db/models/time/stateRows.py` — TimeSnapshotStateRow/TimePublicationStateRow; `db/models/time/historyRows.py` — TimeSnapshotHistoryRow (folder + init=3). `db/models/worldTimeSettings/stateRows.py` — WorldTimeSettingsSnapshotStateRow/WorldTimeSettingsPublicationStateRow; `historyRows.py` — WorldTimeSettingsSnapshotHistoryRow (+init=3). Fields соответствуют колонкам выше, db wire types str/int/bytes допустимы только здесь. Adapter: `db/repositories/sqlite/time/stateStore.py` и `db/repositories/sqlite/worldTimeSettings/stateStore.py`, по init+module=2. Existing scoped access/commit coordinator внедряются, не используются отдельные connections.

Этот layout — полный reviewable candidate, не production proof. До реализации storage slice требует согласованных FK ordering/retention hooks и DDL/model sync в 0001_initial.sql. Нет отдельной 0002 migration; legacy migration отдельным этапом после core.

## 45. Межвладельческий handoff без новых DAG nodes

Snapshot owner получает конкретный change request: next_publication в SnapshotApplyContext (§37), target validation и durable branch result/OperationKind extension (§34), FK ordering (§44). Time не определяет весь branch action protocol: player transfer/authorization/holders принадлежат внешним владельцам, и эти поля нельзя заменить пустым tuple ради закрытого union. До принятия external extension branch integration остаётся BLOCKED; pure rebind/core не блокируются.

API/GEN owner получает inventory §11/30/33, lossless transport policy §41 и обязательные source refs. Нужны concrete invocation mapping и DTOs для выбранных операций; существующие NodeIds/родство/CALL не назначаются автоматически. Пользователь явно запретил concrete nodes в этом scope, поэтому их отсутствие — stop boundary, не забытая часть реализации. Production API нельзя объявить готовым только по наличию Python interface.

**Пакет для пользовательского review теперь включает:** календарное ТЗ, public settings API, Time/World acceptance proposals, DI, полевые политики, codec type-ID proposal и storage row layout. Remaining gates — пользовательская приёмка и принятие конкретных изменений внешними owners; runtime implementation/verification не выполнялись. Прежние формулировки «type IDs/storage layout ещё не предъявлены» уточняются §§43–44: теперь они предложены, но не утверждены.

## 46. Приёмка архитектурных пунктов и граница core / integration

**Явная приёмка пользователя:**

1. Time не публикует изменения самостоятельно; DAG собирает Time proposal и domain effects, Snapshot принимает атомарно.
2. Публичные операции World time/calendar settings выполняются через DAG; typed POJO, версии, миграция удаляемого World.calendar dict.
3. Предложенная календарная модель N+1 над закрытыми engine enums: ALWAYS/YEAR_MODULO/YEAR_RANGE, INSERT/REPLACE/REMOVE_SPAN, CONTINUOUS/RESET_AT_YEAR, ASTRONOMICAL/NO_YEAR_ZERO, MONTH/INTERCALARY; версии/anchors для реформ. Принятие относится к предъявленной модели, не обещанию любой неизвестной вычислительной семантики.
4. Immutable snapshot-bound и publication-bound Time/settings state/history, общая transaction boundary без отдельного Time publisher/journal.

**Уточнение пользователя:** зависимости других доменов не блокируют разработку ядра. Они блокируют только использующий их integration/cutover slice. Ранние blanket формулировки «нужна приёмка календарной модели/архитектуры 1–4» заменены этой записью. Приёмка этих пунктов не означает автоматического утверждения всех числовых type IDs, DTO деталей или SQL constraints и не является просьбой начать код в текущем документальном scope.

| Область | Допустимая readiness boundary |
|---|---|
| Core Time values/arithmetic/intervals/conversions | Можно готовить к изолированной реализации по принятым собственным контрактам; не ждать Snapshot/GEN/actionCore DONE |
| Calendar rules/validation/projection и World settings pure preparation | Принята архитектурная модель; разработка независима от production storage и concrete DAG nodes. Собственные точные I/O/E и policies обязательны |
| Domain public interfaces и contract adapters | Разрабатываются против явных ports; test doubles не выдают себя за готовую external integration |
| Snapshot next_publication/branch lifecycle/FK ordering | Внешние prerequisites соответствующих persistence/integration операций, не blanket blocker core |
| API/GEN DTO/invocation/node bindings | Внешние integration prerequisites; не блокируют pure core/domain operations |
| Numeric codec IDs и concrete storage layout | Отдельный encoding/storage slice; его freeze нужен до реализации именно этого slice |
| Legacy debt и actionCore | Debt после core; actionCore DEFERRED, как уже принято |

Итог: **архитектурные пункты 1–4 приняты; core и external integration имеют раздельные gates**. Возможные собственные противоречия схем core надо исправлять до затронутого кода, но нельзя использовать внешнюю незавершённость как причину откладывать независимое ядро. Production готовность и runtime proofs этим решением не объявляются.

## 47. TIME-LOG — обязательное логирование через общий фасад проекта (2026-11-03)

**Пользователь согласовал архитектурный контракт §47.1–2. Реализация и интеграционные проверки предстоят.** Источник политики sinks/маршрутов — [tz_logging.md](../../docs/tz_logging.md) L1–L8 и существующий [loggingConfig.py](../../backend/app/core/loggingConfig.py). Этот пункт не объявляет TIME CODE-READY и не разрешает менять production.

1. **Один механизм.** Application-owned Time operations эмитят события исключительно через общий `loggingConfig` (штатный JSON formatter/router, профиль server). Целевой домен лога — `time`, сервис — согласованный application producer, а не отдельный файл на каждый арифметический helper/класс/календарь. Перед runtime-включением зарегистрировать согласованный в §47.1 маршрут в существующих `_PREFIX_ROUTES`/`SERVER_SINKS` и каталог консьюмеров `tz_logging.md`. Попадание в fallback `core/runtime` не является выполненным Time sink contract. Запрещены собственные handlers/formatters, второй logging framework, `print`, `app.log` и обход общего фасада.
2. **Границы событий.** Отдельный Time application producer логирует существенные этапы/результаты подготовки advance и отказы по Time-owned причинам (несогласованная timeline/source/revision, invalid interval, overflow, недопустимая календарная операция), cancellation и непредвиденные faults — с разным typed status/severity. Чистые value/arithmetic/projector операции возвращают typed result/error и не становятся побочными лог-писателями. Успешная `prepare_advance` означает только candidate, а не принятый ход/clock; факт Snapshot COMMIT эмитит Snapshot owner, DAG execution — DAG owner. Штатный default календаря/часов не превращается в warning.
3. **Данные и недублирование.** Типы событий, поля, уровни и место эмиссии согласованы в §47.1–2. Корреляция — общий `request_id` и доступные `world_uid`, `timeline_id`, `operation_id`, source/ref/revision, границы интервала и machine-readable refusal code; отсутствующие ID не выдумываются. Не копировать raw calendar definition, приватные данные, целые Time POJO/patch payload и high-cardinality numerical state. Уже зарегистрированные `jsonValidation/resolve` WarningError, DAG и Snapshot события не логировать повторно от имени Time.
4. **Нагрузка и отказоустойчивость.** Никакого per-tick/per-value/per-cell storm в stdout; частые подробности только на согласованном DEBUG/bounded уровне по L7–L8. Сбой доставки лога не изменяет typed outcome, не подменяет cancellation/refusal и не запускает повторную запись/advance.
5. **До runtime cutover** зарегистрировать согласованный маршрут в общем фасаде и каталоге sinks. Выполнить проверки §47.3.

### 47.1. Согласованный маршрут и владелец записи

В профиле server единственный emitter `TimeOperationLog.emit(TimeLogRecord) → None` пишет в logger `app.time.operations`. Согласованная запись в `_PREFIX_ROUTES` — `("app.time.operations","time","operations")`, в `SERVER_SINKS` — `("time","operations")`. Файл — `backend/logs/time/operations.log`. Нужны обе регистрации: по текущему `_DomainFileRouter._keys_for` неизвестный префикс попадает в runtime, известная пара вне allowlist отбрасывается. Образцы единственного emitter и typed admission — `application/worldSnapshot/logging/snapshotLog.py` и `application/engine/diagnostics/dagLog.py`.

Дополнение §31 (корень `backend/app`): `dataModel/time/diagnostics/events.py` — закрытые enums и frozen strict POJO ниже; `application/time/logging/timeOperationLog.py` — emitter, отображение activity → общий LogLevel и явная проекция разрешённых полей в JSON. Обе папки с `__init__.py`. При runtime wiring вызывающая application-граница конкретной DAG binding передаёт исход наблюдаемого вызова в Time emitter ровно один раз. Факт выбирается по фактическому результату или исключению. Binding не вызывает дополнительные доменные операции. Импорты идут от binding к emitter и typed outcomes, от emitter к diagnostics и общему logging. Ядро и DAG engine не импортируют logging Time. Без binding чистый прямой вызов не эмитит. Публичного DAG CRUD для логов и изменения сигнатур §11/§29 нет.

### 47.2. Матрица событий и форма POJO

`TimeLogRecord = TimeCandidateLog | TimeRefusalLog | TimeCancelledLog | TimeFaultLog`. Поле `activity` каждого варианта фиксировано соответствующим значением закрытого enum из таблицы. `operation:TimeLogOperation` принимает PREPARE_ADVANCE, READ_CURRENT, READ_HISTORICAL, PROJECT, RESOLVE. Граница наблюдения ограничена этими bindings. Настройки пишет World через собственные контракты.

| POJO / activity | Уровень | Момент эмиссии и дополнительные поля |
|---|---|---|
| TimeCandidateLog / ADVANCE_PREPARED | DEBUG | Только PREPARE_ADVANCE вернул TimeAdvanceProposal. Обязательные start_seconds:I64, start_nanoseconds:Nano, end_seconds:I64, end_nanoseconds:Nano из interval. |
| TimeRefusalLog / OPERATION_REFUSED | WARNING | Операция вернула один из перечисленных ниже typed отказов. Единственное дополнительное поле code:TimeRefusalCode. |
| TimeCancelledLog / OPERATION_CANCELLED | DEBUG | Binding получил cancellation в ходе вызова до результата. Распространяет исходную cancellation. Дополнительных полей нет. |
| TimeFaultLog / OPERATION_FAILED | ERROR | При исполнении возник непредвиденный fault. Binding сохраняет исходное исключение. Дополнительных полей нет. |

Общие поля четырёх POJO помимо activity/operation: world_uid:EntityUid, timeline_id:EntityUid | None, operation_id:EntityUid | None, publication_id:EntityUid | None, snapshot:WorldSnapshotRef | None. Источник для prepare — base.publication/base.point и обязательный input.operation_id; для current read — expected; для historical — запрошенный snapshot; для project — capture; для resolve — закреплённый source из resolved и переданный scope. Для current source сохраняются publication_id и snapshot_head (если есть); timeline берётся от активной ветки, поскольку head может быть унаследован. Для historical source сохраняется snapshot без publication_id. operation_id присутствует только у prepare. Общий formatter добавляет request_id из context и ts wall-clock; эти поля не входят в Time POJO. Полный capture, календарь, текст исключения и пользовательские payload не сериализуются.

`TimeRefusalCode` — закрытый enum. В таблице позиционное соответствие доменного типа и значения; ни одна строка не расширяет error union операции.

| Операция | Типы отказа | Значения code в том же порядке |
|---|---|---|
| PREPARE_ADVANCE | TimeAdvanceMustBePositive, TimeRangeOverflow | ADVANCE_NONPOSITIVE, RANGE_OVERFLOW |
| READ_CURRENT | TimePublicationConflict, TimeInactiveTimeline, TimeStateUnavailable | PUBLICATION_CONFLICT, INACTIVE_TIMELINE, STATE_UNAVAILABLE |
| READ_HISTORICAL | TimeStateUnavailable | STATE_UNAVAILABLE |
| PROJECT | CalendarSourceMismatch, CalendarScopeMismatch, CalendarBudgetExceeded, CalendarInvalid, CalendarTimeOverflow | CALENDAR_SOURCE_MISMATCH, CALENDAR_SCOPE_MISMATCH, CALENDAR_BUDGET, CALENDAR_INVALID, CALENDAR_OVERFLOW |
| RESOLVE | CalendarSourceMismatch, CalendarInvalid, CalendarBudgetExceeded, CalendarTimeOverflow | CALENDAR_SOURCE_MISMATCH, CALENDAR_INVALID, CALENDAR_BUDGET, CALENDAR_OVERFLOW |

При обычном чтении, успешной проекции и штатном выборе default записей нет. Структурный отказ до вызова принадлежит admission. Если тот же отказ уже эмитирован общим resolver, binding не эмитит вторую запись. После возврата candidate отмена DAG и unknown commit принадлежат соответствующим owners. Повторная подготовка может дать новую диагностическую запись той же operation_id; лог не используется для дедупликации или восстановления.

### 47.3. Порядок приёмки и будущих проверок

1. Архитектурная приёмка §47.1–2 завершена пользователем. Изолированный core можно разрабатывать независимо. Изменение общего каталога sinks — отдельная предложенная правка владельцу `docs/tz_logging.md`.
2. После появления конкретных bindings проверить регистрационные пары и server routing на фактическом JSON-файле, строгую схему каждого варианта, correlation и уровень. Проверить каждую пару operation/code, чтение унаследованного head и исторического snapshot. Проверить отсутствие payload и лишней записи для default и pure вызова.
3. На интеграции проверить две конкурентные подготовки и повтор после неизвестного commit: число candidate-записей соответствует наблюдаемым завершившимся подготовкам при включённом DEBUG и исправном sink, число публикаций определяется только Snapshot. При cancellation, исключении или сбое emitter результат либо исключение исходной операции сохраняется. Нагрузочная проверка подтверждает отсутствие per-tick эмиссии и DEBUG storm в stdout. Это будущие runtime proofs; маршрут и emitter согласованы на уровне архитектуры.

## 48. Внешние зависимости production-интеграции T4/T5 (2026-11-03)

Владелец внешних контрактов и критерии их проверки указаны в [Snapshot, «Контракты Snapshot для интеграции Time»](./world-domain-patches-snapshots.md). Статус всех трёх gates — OPEN.

- **T4, current/historical read.** Требуется SN-TIME-READ и реализация Time state reader. Чтение привязано к уже принятому состоянию. Целевая публикация будущей записи и операция создания ветки этому пути не требуются.
- **T5, runtime apply.** Требуется SN-TIME-APPLY и применимый Time/World handler в общем CommitScope. Target publication назначает Snapshot. Принятие подтверждается общим результатом commit. Pure prepare_advance доступен независимо.
- **Restore/branch.** SN-TIME-BRANCH требуется именно для создания и восстановления результата новой ветки. Чтение существующей исторической точки использует SN-TIME-READ.

Зависимости относятся к соответствующим production-путям. У изолированного core и чистой арифметики остаются собственные условия приёмки §46.
