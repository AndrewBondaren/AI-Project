# Time — технический долг независимого ревью

Дата: 2026-11-02. Статус: OPEN, статическое исследование; не разрешение на implementation. Owning proposal: [time-domain.md](./time-domain.md), включая последние уточнения §22. Этот реестр фиксирует находки, prerequisites и границы evidence; не заменяет owning контракты соседних доменов.

Исходное ревью не изменяло код, планы и ТЗ. При его начале и завершении рабочее дерево содержало чужие изменения `time-domain.md` и `world-generation-plan-dependency-graph.md`; они сохранены. Настоящий файл и ссылки добавлены по последующему прямому запросу пользователя. Runtime proofs не выполнялись; общий PASS Time design не выставлен.

## Принятые границы

Время принадлежит миру и без действий игрока не продвигается. Actions/actionCore определяет положительную длительность игрового действия; technical zero interval допустим. ActionCore deferred (§22 proposal), не blocker core design. Time owns значения, арифметику, validation и preparation; DAG — межоперационный порядок; Snapshot — атомарное принятие времени и effects, restore/branch. Representation: int64 seconds + nanos; час = 3600 секунд. World owns hours_per_day (default 24), календари, эпохи и versioned start. Default Gregorian start — once-captured UTC+0; custom calendar требует явный старт. World.calendar:dict подлежит удалению. Turn UID/ordinal, snapshot sequence, simulation time и wall-clock не взаимозаменяемы.

## Actionable findings

### TIME-DEBT-01 — P1: generic World writers обходят clock acceptance

Статус: **legacy migration obligation**; возможность записи подтверждена на уровне service/repository, HTTP payload и реальная БД не проверены.

Evidence: [worldService.py:102](../../backend/app/application/worldData/registries/worldService.py#L102), [import:161](../../backend/app/application/worldData/registries/worldService.py#L161), [base.py:29](../../backend/app/db/repositories/sqlite/base.py#L29), [bundle sections.py:31](../../backend/app/application/worldBundle/entity/sections.py#L31).

- Trigger: update/import существующего мира с current_tick; bundle переносит World через asdict.
- Фактически: immutable guard защищает world_uid/created_at; import вызывает upsert, repository пишет поля модели. Clock не отделён от definition CRUD и не связан с атомарным принятием gameplay effects.
- Требуется: runtime clock меняется через Snapshot вместе с effects; definition import не заменяет время активного мира.
- Источник: принятые границы, Time §14.3, Snapshot/Patch acceptance.
- Owner: World/import + Snapshot.
- Disposition: **replace** generic clock writes; **retain** settings CRUD. Prerequisite: definition versus snapshot/history import modes, versioned migration поля, initial-state binding. Удаление одного increment_tick не закрывает косвенные writers.
- Закрытие: trace всех mutation/import/copy paths и проверки запрета runtime overwrite, atomic acceptance и provenance round-trip.

### TIME-DEBT-02 — P2: Regions history принимает wall-clock marker

Статус: **legacy migration obligation**; достижимая исходная цепочка подтверждена.

Evidence: [declaredRegionEdit.py:65](../../backend/app/application/worldData/regions/declaredRegionEdit.py#L65), [consumer.py:72](../../backend/app/application/worldData/regions/stateChange/consumer.py#L72), [history.py:8](../../backend/app/application/worldData/regions/stateChange/history.py#L8), [regionState.py:27](../../backend/app/dataModel/regions/regionState.py#L27).

- Trigger: изменение entry_type существующего declared region через reconcile.
- Фактически: datetime.now(UTC) передаётся как updated_at и at; at сохраняется в domain history. str|int не различает дату и произвольный счётчик, не несёт timeline/provenance.
- Требуется: отделить технический аудит от времени доменного события, обеспечить однозначную historical binding.
- Источник: принятые границы; явные TODO model/history; Time §14.3.
- Owner: Regions и World/DAG lifecycle caller.
- Disposition: **replace** at типизированным event/time evidence; **retain** audit updated_at. Prerequisite: semantics pregame edit/runtime event, включая отсутствие simulation timeline до gameplay start.
- Закрытие: typed history round-trip и проверка branch/event provenance. Использование wall-clock для скорости роста этим trace не установлено.

### TIME-DEBT-03 — P2: last_eval_tick является локальным накопителем

Статус: **legacy migration obligation**; повторное применение elapsed **требует проверки caller contract**.

Evidence: [progress.py:28](../../backend/app/application/worldData/regions/stateChange/progress.py#L28), [consumer.py:55](../../backend/app/application/worldData/regions/stateChange/consumer.py#L55), [consumer.py:125](../../backend/app/application/worldData/regions/stateChange/consumer.py#L125), [regionState.py:37](../../backend/app/dataModel/regions/regionState.py#L37).

- Trigger: первая оценка region в ненулевой момент мира либо повторная подача одного ненулевого elapsed.
- Фактически: initial 0, затем last_eval_tick += elapsed_ticks; request не удостоверяет границы интервала/timeline. Повтор снова прибавляет elapsed.
- Требуется: checkpoint однозначно обозначает уже обработанное время; world_time − last_eval_tick нельзя использовать без такого контракта.
- Источник: [lazy simulation](../../docs/tz_lazy_simulation.md), last_tick/batch catch-up; требования provenance.
- Owner: Regions; доставка/scheduling — DAG/lazy owner.
- Disposition: **replace** integer elapsed/checkpoint согласованными interval/evaluation facts. Prerequisite: replay policy и atomic checkpoint/effects acceptance.
- Закрытие: late-created region, replay и branch tests. Найденный production declared-edit caller передаёт zero; ненулевые вызовы найдены в tests, production scheduler не установлен. Это ограниченное negative evidence.

### TIME-DEBT-04 — P2: batch transition теряет превышение порога

Статус: **design gap**, не доказанный gameplay defect.

Evidence: [progress.py:34](../../backend/app/application/worldData/regions/stateChange/progress.py#L34), [history.py:12](../../backend/app/application/worldData/regions/stateChange/history.py#L12).

- Trigger: strength × elapsed / (inertia + weight) превышает оставшуюся дистанцию до threshold.
- Фактически: одна transition, progress сбрасывается в 0; остаток интервала не возвращается/не сохраняется.
- Требуется: явно определить допустимость одного перехода за evaluation либо обработку оставшегося интервала. Большой batch и малые partitions потенциально дают разную историю.
- Источник: [tz_lazy_simulation.md:190](../../docs/tz_lazy_simulation.md#L190), согласованность состояния с прошедшим временем.
- Owner: Regions.
- Disposition: **retain** формулу до принятия модели; **replace** batch handling, если нужна partition equivalence. Prerequisite: owner-defined transition/residual semantics; затем соответствующий test. Не переносить hysteresis/residual gameplay rules в Time.

### TIME-DEBT-05 — P2: legacy требования подменяют время счётчиками

Статус: **legacy migration obligation**, документальный конфликт.

Evidence: [storage TZ:2008](../../docs/project_data_storage_tz.md#L2008) — session ownership; [:2010](../../docs/project_data_storage_tz.md#L2010) — current_tick=turn_id/«Ход N»; [snapshot TZ:1045](../../docs/tz_world_snapshot.md#L1045) — elapsed turns как основание batch unfold; [storage TZ:2555](../../docs/project_data_storage_tz.md#L2555) — бесплатные interior-переходы.

- Trigger: реализация consumers по этим формулировкам при действиях различной длительности.
- Фактически по тексту: ordinal delta заменяет duration; игровой переход может не продвигать время.
- Требуется: отдельные simulation interval/turn ordinal и положительная длительность игрового действия.
- Источник: принятые границы, Time §1/§22.
- Owners: Actions, lazy simulation, Snapshot consumers, UI.
- Disposition: **replace** конфликтующие требования. Prerequisite: versioned units mapping и разграничение logical link/игрового перехода. Production реализация этих формул поиском не подтверждена.

### TIME-DEBT-06 — P2: initial/branch Time storage не замкнут

Статус: **design gap**, явно признанный proposal.

Evidence: [Time §§20–22](./time-domain.md#20-lifecycle-payload-proposal-и-границы-реализации).

- Trigger: gameplay start без snapshot head либо branch до первой новой Time section.
- Фактически: StoredTimeState/PublicationTimeState различены, но SectionStateRef не даёт готового headless binding; retention и атомарный lifecycle protocol остаются внешним prerequisite. Pure bind_initial/rebind не обеспечивают durable state.
- Требуется: один authoritative clock с согласованным read/retention/branch protocol.
- Источник: Snapshot owns commit/restore/branch, Time §§20–22.
- Owner: Snapshot/World integration.
- Disposition: **retain** разделение coordinate/timeline; **replace** OPEN seam конкретным согласованным protocol перед integration. Не создавать fictitious snapshot или второй publisher.
- Закрытие: headless read, first snapshot, inherited refs, branch rebind, retention и atomicity proofs.

Последние уточнения §22.1 уже различают calendar version publication и capture source; §22.2 задаёт initial zero как Literal. Не предъявлять устранённые варианты как действующие дефекты. ActionCore deferred не переоткрывать. P3 findings с достаточным evidence в этом ревью не выделены.

## Корректные использования / false positives

- elapsed_ticks=0 при declared edit — technical evaluation, не доказательство бесплатного действия.
- Regions progress:float — gameplay progress, не authoritative float clock.
- monotonic для LLM latency, cancellation deadlines и profiling — техническое время.
- created_at/export timestamps — audit metadata; now() сам по себе не simulation advance.
- Combat round_seconds=6 и копия настройки при старте боя — допустимый owner contract.
- 3600 секунд/час — принятая единица; default 24 допустим в owning World POJO.
- Snapshot sequence и chat UUID допустимы в собственной роли; fixtures не доказывают подмену simulation time.
- at=42/updated_at="now" в tests — fixtures, не production literals.
- Исключение current_tick из definition fingerprint корректно само по себе; записи clock это не защищает.

## Coverage ledger и незакрытые границы

| Область | Evidence | Ограничение |
|---|---|---|
| Working tree | git status --short, git diff --stat, diff двух изменённых планов | План менялся параллельно; учтён увиденный §22 |
| Time proposal | Последовательно прочитанные разделы и последние calendar/lifecycle уточнения | Общий PASS не выставлен |
| World | Model/DDL, increment, service update/import, save/upsert, bundle section | HTTP, все copy variants и внешние клиенты не исполнены |
| Regions | Types → request → consumer → progress/history → mapping/upsert | Ненулевой production scheduler не установлен; replay/partition tests не запускались |
| Wall-clock | Поиск now/utcnow/time/monotonic, назначения найденных групп | Не полный аудит aliases/dynamic imports |
| Frontend/tests | Tick/turn/round/duration поиск; fixtures отделены | Полный UI/calendar flow не проверен |
| Physics/GEN/Snapshot | Релевантные требования и foreign gaps | Большие owning-планы не прочитаны построчно целиком; solver/restore runtime не проверены |
| Needs/rest/travel/weather/resources | Hourly rates, remaining ticks, batch requirements | Сквозной production flow не установлен; отсутствие реализации не доказано |
| Правила | POJO row/wire, validation architecture, defaults/ownership требования | Не все общие rule-файлы прочитаны отдельно |

Основные команды поиска:

```text
git status --short
git diff --stat
git diff -- .cursor/plans/time-domain.md .cursor/plans/world-generation-plan-dependency-graph.md
rg -n 'current_tick|elapsed_ticks|last_eval_tick|last_tick|remaining_ticks|round_seconds|increment_tick' backend/app frontend
rg -n 'datetime.now|datetime.utcnow|time.time\(|time.monotonic\(' backend/app
```

Дополнительно искались turn_id, «Ход», ticks, 3600, TODO Time/LOD по backend/frontend/tests и перечисленным источникам. Точечные чтения выполнены через Get-Content. Ошибочный glob backend/app/api/routes/world* в одном поиске не дал evidence; последующий поиск routes не установил нужный HTTP binding.

Источники: [storage TZ](../../docs/project_data_storage_tz.md), [lazy simulation](../../docs/tz_lazy_simulation.md), [Snapshot](../../docs/tz_world_snapshot.md), [Patch](../../docs/tz_patch_system.md), [World plan](./world-domain-patches-snapshots.md), [Physics](./physics-spatial-dynamics.md), [GEN](./gen-dag-node-dependency.md), POJO/validation rules.

Не выполнены runtime проверки коротких интервалов/округления, concurrency, restore/branch, import round-trip и repeated elapsed. Negative search не доказывает недостижимость. Для закрытия каждого пункта требуется собственное evidence; наличие нового Time API не закрывает consumer/writer migration автоматически.
