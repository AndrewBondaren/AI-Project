# Настройки времени: оркестрация и привязка контрактов к методам

Размещение каждой описанной ноды, её POJO, регистрации и родительских связей: [единый реестр](dag-node-layout-register.md). Реестр различает существующие файлы и целевые пути; размещение не закрывает OPEN контрактов и не означает production wiring.

Решение пользователя 2026-11-21: зафиксировать оркестрацию настроек и закрепить контракты за конкретными методами. Последующее поручение пользователя разрешило реализацию нод; восемь single leaf уже реализованы с локальной регистрацией. Приёмка полного маршрута и production activation учитываются отдельно.

## Структура

Приоритетное уточнение 2026-11-21: пользователь выбрал последовательную Time-owned batch preparation; прежний OPEN выбора batch-семантики ниже исторический. Для одной команды orchestrator вызывает соответствующий single leaf, для нескольких — один batch leaf → TimeSettingsBatchPipelineOpenPipeline.prepare_batch. NodeId/wrappers/error mapping parent и batch ещё OPEN; восемь single leaf уже имеют локальную регистрацию. Orchestrator возвращает PreparedTimeSettingsChange либо полный owning отказ в prepare_changes; prepare_changes вызывает section producer через отдельный leaf. В orchestrator нет сравнения base, вычисления command indices/budget, промежуточных settings, no-op/retention checks. Эти алгоритмы остаются Time-owned. Границы CALL и transport — dag-write-nodes-implementation.md, «Обязательная граница оркестрации».

`prepare_world_time_settings_changes` — проектируемая orchestration node. Получает типизированные команды, вызывает соответствующие operation leaf и передаёт результаты следующему согласованному этапу подготовки. Методы, callbacks и pipelines не передаются как данные команды. Название сохраняет ранее предложенную форму; семейство timeSettings включает родителя и его single/batch children; owning настройки принадлежат Time.

Каждая из восьми дочерних нод отвечает за одну операцию и вызывает один закреплённый публичный метод. Внутренние календарные алгоритмы не переносятся в DAG. Четыре ранее принятые самостоятельные Time leaf остаются без родительской ноды: этот orchestrator к ним родство не добавляет.

## Закреплённая карта методов и существующих POJO

### Реализация operation leaf (2026-11-24)

Восемь single-operation leaf имеют NodeId, равные именам методов в таблице
(`prepare_hours_change`, `prepare_calendar_create`, `prepare_calendar_update`,
`prepare_calendar_select`, `prepare_calendar_remove`, `prepare_epoch_create`,
`prepare_epoch_update`, `prepare_epoch_remove`). Для каждой операции
`Prepare<Operation>Input.request` имеет точный owning request из таблицы;
`Prepare<Operation>Output.value` имеет полный union соответствующей строки.
Конкретные POJO — `backend/app/dataModel/engine/nodes/timeSettingsContracts.py`,
реализации — восемь отдельных классов в
`backend/app/application/engine/nodes/timeSettings/prepare*Node.py`,
NodeContract и явная регистрация — `timeSettings/registration.py`.
Проектируемая родительская нода принадлежит отдельному классу и файлу в
той же папке; её реализация не входит в этот срез.
ContractId каждого leaf: `engine.time.settings.<NodeId>`, версия `1`,
`reads=()`, `calls=()`, `error_types=(TimeSettingsNodeError,)`.
Owning refusals передаются через Output.value; исключения исполнения не
преобразуются. Регистрация локальная через `register_time_settings_nodes`;
production wiring вне этого среза. Согласование будущего orchestrator,
batch и section producer остаётся OPEN.

Полные имена классов публичных целей:

- H = `WorldHoursSettingsPipelineOpenPipeline`, `application/worldData/timeSettings/preparation/hoursPipelineOpenPipeline.py`.
- C = `WorldCalendarSettingsPipelineOpenPipeline`, `application/worldData/timeSettings/preparation/calendarPipelineOpenPipeline.py`.
- E = `WorldEpochSettingsPipelineOpenPipeline`, `application/worldData/timeSettings/preparation/epochPipelineOpenPipeline.py`.

Пути относятся к `backend/app/`. Для восьми single leaf ниже реализация и локальная регистрация уже существуют, как указано в разделе от 2026-11-24 выше. Parent/batch/section остаются отдельными целевыми нодами; их файлы закреплены в реестре размещения. Сигнатуры методов не означают приёмку внутренней реализации доменов.

| Operation leaf | Публичный метод | Input POJO | Полный возвращаемый union |
|---|---|---|---|
| prepare_hours_change | H.prepare_hours_change | HoursChange | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded / SettingsAnchorRequired |
| prepare_calendar_create | C.prepare_calendar_create | CalendarCreate | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded |
| prepare_calendar_update | C.prepare_calendar_update | CalendarUpdate | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded / SettingsAnchorRequired |
| prepare_calendar_select | C.prepare_calendar_select | CalendarSelect | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded |
| prepare_calendar_remove | C.prepare_calendar_remove | CalendarRemove | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded / SettingsInUse |
| prepare_epoch_create | E.prepare_epoch_create | EpochCreate | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded |
| prepare_epoch_update | E.prepare_epoch_update | EpochUpdate | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded |
| prepare_epoch_remove | E.prepare_epoch_remove | EpochRemove | PreparedTimeSettingsChange / SettingsInvalid / CalendarBudgetExceeded |

Каждая связь leaf → method означает PUBLIC CALL с указанным request без преобразования доменной семантики; обратная связь — полный возвращаемый union. Отказ не превращается в успешный prepared result. Это граница доменных POJO; отдельные engine Input/Output/Error wrappers пока OPEN, новые дублирующие доменные модели не вводятся.

## Поля запросов и результата

Запросы определены в `dataModel/world/settings/timeOperations/changes.py`.

Общий `SettingsPreparationBase`: `operation_id: EntityUid`, `capture: TimeSettingsCapture`, `clock: TimeCapture`, `budget: CalendarBudget`. Существующий validator требует `clock.publication == capture.source`. Это контракт согласованности входа, а не поручение DAG вычислять время или нормализовать календарь.

| Request | Поля помимо base: SettingsPreparationBase |
|---|---|
| HoursChange | hours_per_day: Pos; anchors: tuple[CalendarAnchorReplacement, ...] |
| CalendarCreate / CalendarUpdate | entry: CalendarEntry |
| CalendarSelect | calendar: Key[WorldCalendarRegistry] |
| CalendarRemove | calendar: Key[WorldCalendarRegistry]; replacement: Key[WorldCalendarRegistry] |
| EpochCreate / EpochUpdate | epoch: WorldCalendarEpoch |
| EpochRemove | epoch: Key[WorldCalendarEpochRegistry] |

`CalendarAnchorReplacement`: `calendar: Key[WorldCalendarRegistry]`, `origin: CalendarOrigin`. Update календаря передаёт полный CalendarEntry, а не произвольный partial dict.

`PreparedTimeSettingsChange` из `dataModel/world/settings/timeOperations/results.py`: `operation_id: EntityUid`, `expected: WorldPublicationRef`, `before: WorldTimeSettings`, `after: WorldTimeSettings`, `effective_at: TimePoint`. Это подготовленный кандидат, не receipt записи и не подтверждение принятия мира.

SettingsInvalid несёт непустой tuple CalendarFieldIssue; SettingsAnchorRequired — calendar и current: CalendarClockTime; SettingsInUse — calendar. CalendarBudgetExceeded принадлежит календарной проекции (`dataModel/world/calendar/projection/errors.py`). Конфигурация budget передаётся явно через base; настройки мира передаются в capture. DAG не получает право интерпретировать бюджет или изменять настройки самостоятельно.

## Порядок и границы

1. На вход поступают готовые типизированные запросы с закреплёнными capture/clock; получение этих данных не добавляется скрыто внутрь leaf.
2. Orchestrator выбирает leaf по конкретному типу команды. Leaf вызывает закреплённый метод и возвращает его результат.
3. Успех подготовки ещё требует согласованного producer native settings section. Затем секция участвует в общей сборке PatchSet и единственном вызове Snapshot.apply по write flow. PreparedTimeSettingsChange не выдаётся за готовую секцию.
4. Prepare-методы не вызывают Snapshot.apply. Remove означает подготовку изменения настроек; фактическое сохранение проходит общий маршрут.

Несколько команд нельзя автоматически выполнить независимо на одном capture и затем выбрать последний after: это теряет изменения. Нельзя и самостоятельно подменять capture промежуточным кандидатом. Последовательная batch preparation принята и выполняется публичным методом Time. DAG выбирает single/batch, не вычисляет промежуточные состояния. Остаются concrete node wrappers/CALL/error transport, а не повторный выбор batch-семантики.

## Сверка и открытые границы

- PASS, инвентарь: восемь конкретных методов, существующие Input и возвращаемые POJO закреплены таблицей; generic execute отсутствует.
- RESOLVED, ownership: owning update Time в SETTINGS-CONTRACT-2026-11-21 подтвердил пользовательское решение — runtime настройки мира принадлежат Time. World* в именах и путях не обозначает другого владельца. Противоречивый REVIEW-FIX отозван владельцем. Отдельный initial маршрут сохраняется.
- RESOLVED, граница вложенных вычислений: CalendarValidator и CalendarProjector внутри H/C/E — Time-owned алгоритмы, их не требуется выносить в DAG. Это не разрешает вложенный Snapshot.apply и не закрывает остальные runtime-проверки.
- OPEN: producer native WorldTimeSettingsSection, его exact Input/Output/Error и consumer mapping до assemble_patch_set.
- OPEN: concrete batch node Input/Output/Error wrappers и CALL binding к owning prepare_batch; engine retry/cancellation mapping. Последовательный порядок и owning batch-семантика не переоткрываются.
- OPEN: NodeId/registration parent, batch и section leaf; их контрактная приёмка. Восемь single leaf имеют NodeId и локальную регистрацию; это не приёмка всего маршрута.

Initial settings и чтение мира не добавлены в этот срез. Связанный план локальных Time-нод: [gen-dag-time-local-node-contracts.md](gen-dag-time-local-node-contracts.md).

## Координаторская сверка owning update Time, 2026-11-21

Источник: time-domain.md, SETTINGS-CONTRACT-2026-11-21 и S2–S4. Новые API остаются PROPOSED до решения пользователя.

1. S2 исправляет реальный representation gap: existing DomainSection требует P: PatchData, поэтому PreparedTimeSettingsChange нельзя передать как patch напрямую. Предложение WorldTimeSettingsPatch(PatchData){change} совместимо с общей формой header+payload; cardinality, ключи и версии требуют concrete validation и регистрации.
2. Предложенный маршрут: single prepare_* либо prepare_batch → PreparedTimeSettingsChange → TimeSettingsSectionPipelineOpenPipeline.prepare_section(PrepareTimeSettingsSection(change, operation_id, expected_world)) → WorldTimeSettingsSection → PatchSetAssemblyInput.sections → Snapshot.apply. На producer refusal сборка с отсутствующей обязательной секцией не продолжается. Engine wrappers и общий typed отказ подготовки остаются OPEN.
3. Time-owned ordered batch сохраняет доменную обработку в Time и не требует fake capture или слияния кандидатов в DAG. Это рекомендуемое изменение первоначального предложения: несколько команд вызывают одну batch operation leaf, а не последовательность публичных single leaf. Пока не пользовательская приёмка нового порядка.
4. Блокер совместной clock/settings записи: S2 одновременно задаёт invariant пустых dependencies и оставляет policy совместного применения OPEN. До выбора policy это только ограниченный proposal. Нужны exact проверки общего base, effective_at, связь с исходной/целевой clock point, порядок handler validation/apply и решение, нужны ли dependencies. Нельзя объявлять arbitrary совместный PatchSet допустимым.
5. No-op before==after: подготовленный результат допустим в proposal, но запись/receipt ещё OPEN. Нужен один выбор владельцев Time и Snapshot: принимается ли такая секция, какие states/history и changed выдаются и какие проверки подтверждают результат. DAG не отбрасывает её самостоятельно.
6. Native manifest closure, новый patch ID, settings section codec и handler validate/apply/receipt/storage остаются integration gates. Форма wrapper не доказывает сквозную поддержку.

Итог: ownership и граница локальных вычислений сведены; mapping кандидата в native оболочку проверен по базовым типам. Полная приёмка нового settings write flow — OPEN.
