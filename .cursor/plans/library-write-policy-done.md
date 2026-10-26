# План: единая политика записи библиотек

Статус: целевая архитектура зафиксирована 2026-10-11 по обсуждению с мастером;
L-1…L-5 выполнены (L-4/L-5 — 2026-10-13). Дополнение L к
`library-packs-model-done.md`, отдельное от 5a.
SoT: `docs/tz_template_library_packs.md` §0.3; владение/identity — §1–3,
импорт — §4, canonical attach — §6. Один подшаг за заход с отчётом.

Архитектура L-4: [компоненты, контракты и UOW](library-write-l4-architecture.md).
Фактический разбор: [анализ L-4](library-write-l4-analysis-done.md).
Архитектура и результаты реализации L-4 зафиксированы в этих документах.

Уточнение ответа API согласовано 2026-10-12: первый `policy_required`
содержит item_key, UID совпавших целей, допустимые copy/replace и причины,
preview последствий и preview_token в одном ответе. Полные тела фронт при
необходимости читает по UID; чтение не заменяет preview. Отдельный обязательный
preview-запрос не вводится. Повторный запрос передаёт decisions/token;
при stale — обновлённый preview/token без writes. Назначение и проверка
новых UID остаются на бэкенде. Подробности — §5 архитектуры L-4.

## Исходное состояние и проблема до L-4

- `memberCopyOps.copy_member` всегда копирует; `_MemberOps.create` отклоняет
  существующий вычисленный UID, `update_body` отдельно заменяет тело.
- `_PackScope.new_pack_identity` смешивает подготовку identity и отклонение
  существующей записи; `_RemapOps` отдельно выбирает повторное инстанцирование.
- `reinstantiateOps` имеет собственный confirm/token-протокол; его pure
  diff/retention/remap уже пригодны для переиспользования.
- FS-import structures/relief вызывает domain upsert до общего решения;
  membership attach при этом insert-missing. HTTP может обращаться прямо
  к доменным library services. Добавления фасада недостаточно: обходы закрыть.
- `find_by_local_uid` ожидает максимум одну строку, хотя ключ может повторяться.

## Целевые компоненты и контракты

Имена ниже — целевые, существующие файлы не переименовываются ради косметики.
Каждый класс имеет одну ответственность; методы подготовки не записывают,
методы применения не принимают решений о политике.

- `LibraryWriteInspector.inspect(request) -> WriteSnapshot`: только чтение
  состояния и сбор фактов. Список совпадений, источники/цели, доступ,
  provenance, references/pins, сведения для проверки актуальности.
- `LibraryWritePolicy.decide(snapshot, request) -> WriteDecision`: чистый
  единственный выбор действия. Результаты: need-policy, create/copy/replace,
  rejected/stale. Правила выбора и допустимости не повторяются в routes,
  импортёрах и исполнителях. Доменная валидность предоставляется фактами.
- `LibraryWritePlanner.prepare(snapshot, decision) -> LibraryWritePlan`:
  координация специализированных `PackWritePlanner`/`MemberWritePlanner`.
  Они готовят concrete actions, UID-map, тела, membership, dependencies,
  provenance и retention, не выбирая политику. Источник идентичности —
  только `app.ids`; полученные новые UID фиксируются в плане один раз.
- `LibraryWriteExecutor.apply(plan) -> WriteResult`: только выполнение
  подготовленных действий в caller UOW; не нормализует вход и не выбирает
  поведение при совпадениях. SQL-конфликт не превращается в silent upsert.
- `LibraryWriteService.execute(request) -> WriteResult | PolicyRequired`:
  application orchestration стадий и транзакционной границы. Не содержит
  самостоятельных правил `copy`/`replace`.

DTO: `LibraryWriteRequest` содержит object kind (pack/member), источник,
целевую область/пак, optional decisions и token. Решение по совпадению:
`policy: copy | replace`, UID выбранной цели для replace, ключ элемента
исходного запроса. `PolicyRequired`: статус, полный список совпадений,
допустимые действия/причины, preview и token. Никаких дефолтных replace.
`LibraryWritePlan` — typed actions, без произвольных callbacks/сырого SQL.
Доменные тела остаются typed по контракту адаптера, общий слой не знает полей.

## Поток и инварианты

Все стадии последовательны: read/validate → decide → prepare → apply.
Первый запрос с совпадениями завершается до apply. При повторном запросе
источник и цель перечитываются; stale/неполный выбор возвращает preview без
записи. Финальная проверка и apply защищены одной UOW/контрактом конкурентности.
Для batch сначала решения и проверка всех объектов, затем одна запись всего
набора; ошибка не оставляет частичного результата. Token связан с содержимым
источника, scope, целями и предложенными вариантами, а не только временем/UID.
Выбор клиента проверяется против этих фактов; ещё неизвестный выбор пользователя
не включается в токен первого preview.

Пак сопоставляется по UID/занятой вычисленной identity. Member: UID либо
target pack + kind + local_uid, всегда список совпадений. `display_name` не
участвует; одинаковый local_uid других паков не влияет. Re-instantiate
сохраняет provenance-сопоставление. Pack replace не делает delete/recreate
и сохраняет используемых исчезнувших членов согласно §2; независимые
member-копии не получают ложное управление через pack provenance.

Независимая copy пака требует новой центральной identity даже при занятом
system_name инстанса; точная wire-форма запроса новой identity фиксируется
L-1, без локального uuid/hash. Replace не меняет владельца цели. Изменения
provenance планируются явно; неоднозначные члены не сливаются по local_uid.
Canonical insert-missing — отдельный служебный режим §6, недоступный как
обход политики пользовательского импорта. Чтение 5a не входит в write-path.

## L-1 — типы запроса и чистая политика — выполнен 2026-10-11

**Выполнен 2026-10-11.** `writeContracts.py`: валидируемый frozen request,
selection и source reference (catalog UID/import entry key), immutable DTO
фактов и результатов. `writePolicy.py`: чистый `LibraryWritePolicy.decide`,
без I/O/UID-generation. 20 unittest-тестов: оба object kinds/scopes,
неполный batch, точная цель, stale, доступ, domain errors, wire validation,
занятость новой identity и повторные цели batch. `copy_system_name` задаётся
клиентом для pack copy; inspector L-2 проверит свободную центральную identity.
Replace сохраняет lineage цели; правила уточнены в ТЗ §0.3.
Готовых write-routes пока нет: application wiring — L-4, HTTP — L-5.

- Цель: единый проверяемый контракт выбора для pack/member и world/engine.
- ТЗ: §0.3, §1.1, §2–3.
- Файлы: `libraryPacks/writeContracts.py`, `writePolicy.py`, policy tests.
- Контракт: DTO выше, чистый `decide`; фиксировать wire-форму новой pack
  identity, provenance замены и результат blocked/stale. Сначала эти типы,
  затем остальные компоненты; не вводить пустых внутренних заглушек.
- Проверка: `python -m unittest discover -s tests -p test_library_write_policy.py`
  из backend; матрица отсутствующего/явного выбора, нескольких совпадений,
  default/чужого owner, невалидного входа, stale и обоих object kinds.
- Done: policy не имеет repository/HTTP/logging I/O; все переходы явны.

## L-2 — чтение состояния и инспекция совпадений — выполнен 2026-10-11

**Выполнен 2026-10-11.** `LibraryWriteInspector` собирает read-only snapshot;
`LibraryWriteSourceReader` читает SQL либо нормализованный parsed import и
валидирует тела штатными domain adapters; `LibraryWriteStateReader` читает
явный owner/default набор, refs и pins через существующие scanners.
`WriteInspectionState` сохраняет тела/typed outlines, metadata, provenance,
зависимости и внешнее владение для L-3. Обход dependencies — visited-set.
Preview token через `app.ids.state_fingerprint` меняется при значимых
изменениях source/target/usage. Новый copy_system_name проверяется независимо
от токена первого preview: выбор пользователя ещё отсутствовал при его выдаче.
Добавлен списковый `list_by_local_uid`, одиночный lookup совместим и по-прежнему
отклоняет неоднозначность. Конвенции instance/publish system_name вынесены в
`packIdentity.py` и переиспользованы старым remap без изменения поведения.
Read-snapshot не выбирает policy, не делает SQL writes/BEGIN/COMMIT и не
использует global list_all. Парсинг контейнеров FS/архива остаётся за их
readers, вход inspector — `Mapping[entry_key, WriteImportSource]`; подключение
пользовательских import entry points к этому шву — L-4/L-5.
Проверка: 18 SQLite inspector tests + 20 policy tests; также 69 прежних
schema/4b/4c tests. Все прошли. SQL trace проверяет отсутствие mutations.

- Цель: предоставить политике полный snapshot без записи.
- ТЗ: §0.3, §1.1–1.2, §3.
- Файлы: `libraryPacks/writeInspector.py`, repository interface/sqlite
  member queries, существующие reference/provenance scanners, tests.
- Контракт: списковый запрос members по target pack/kind/local_uid;
  existing single-result accessor не использовать для выбора первой цели.
  Snapshot включает все данные token/retention, не общий global list_all.
- Проверка: `python -m unittest discover -s tests -p test_library_write_inspector.py`;
  несколько members с ключом, изоляция scopes, ссылки/pins, отсутствие writes.
- Done: источники FS/архив/SQL приводятся к проверенному входу до apply;
  inspector не выбирает copy/replace.

## L-3 — подготовка планов pack/member — выполнен 2026-10-11

**Выполнен 2026-10-11.** `LibraryWritePlanner` координирует выделенные
`MemberWritePlanner`, `PackWritePlanner` и `WriteRetentionPlanner`:
сначала назначаются identity всего batch, затем готовятся typed тела,
membership, dependencies и world before/after patches. План содержит
typed actions/diff/remap/preserved/removed/held/diagnostics без SQL,
repository reads, часов или изменения входного snapshot. Единственная
policy остаётся `LibraryWritePolicy`; неготовое/stale решение не планируется.

Member-copy использует `app.ids.runtime_uid`, сохраняет исходные refs;
member-replace сохраняет UID, local key и provenance точной цели.
Полный pack remap сохраняет разные исходные UID при повторных local keys,
ремапит внутренние/cross-pack ссылки и dependencies всего переносимого
batch; внешние refs без переноса остаются. Pack replace использует
UID/provenance matching, сохраняет lineage цели, независимые extras,
а unrelated replace не назначает ложную `pack_copy` provenance.
Retention переиспользует least-reachable `hold_candidates` по итоговому
каталогу/world: удаляемые consumers не удерживают друг друга без корня,
новые consumers и pins удерживают кандидатов; dependencies extras сохраняются.

Адаптеры получили pure `prepare_world_refs` и совместимый optional
`local_uid` у `remap_body`; legacy write wrappers сохраняют прежние
timestamps/логи. Shared reference/dependency diagnostics не эмитятся;
проверяются world refs и транзитивные missing dependencies. Невалидный
import consumer отклоняется, прежняя диагностика catalog/world сохраняется
для будущей apply-границы и сама по себе не блокирует валидный import.

Уточнение read-state: `existing_member_uids` отделяет реально занятые
SQL UID от imported source UID в `known_members`; импорт не получает
ложный occupancy и не захватывает известную чужую строку. Pure planner
не читает БД для проверки ещё не назначенных UID. SQL uniqueness всех
новых UID, включая случайные и детерминированные UID вне прочитанного
набора, и повторная проверка состояния обязательны в UOW executor L-4;
конфликт не должен превращаться в upsert. Сервис/routes ещё не подключены.

Проверка: 29 L-3 unittest-тестов; общий набор write_plan/write_policy/
write_inspector/schema/4b/4c/pack_refs — 143 tests, OK. `git diff --check`
без ошибок. Backend не запускался, commits отсутствуют. L-4/L-5 не начаты.

- Цель: единая подготовка явных действий с отдельной логикой объектов.
- ТЗ: §0.3, §0.1, §2, §4.
- Файлы: `libraryPacks/writePlanner.py`, `packWritePlanner.py`,
  `memberWritePlanner.py`, `reinstantiatePlan/Members/Policy`, UID adapters,
  domainAdapters (pure prepare/remap), tests.
- Контракт: reuse diff/retention/provenance; подготовка ничего не сохраняет.
  Copy/replace выдаёт полный план, включая UID-map, зависимости и source_*;
  выполняющие доменные операции не переопределяют решение L-1.
- Проверка: `python -m unittest discover -s tests -p test_library_write_plan.py`;
  identity/ref preservation, copy remap, pack replacement состав,
  удержание used members, независимые копии, отсутствие side effects.
- Done: каждый поддержанный результат политики имеет валидный полный план.

## L-4 — application orchestration и атомарное применение — выполнен 2026-10-13

**Выполнен 2026-10-13.** `LibraryWriteService` соединяет inspect → policy →
prepare → strict executor в одной main-connection UOW. `PolicyRequired`
возвращает choices, replace projections, copy consequences, token/stale;
перечитывание и проверка актуальности предшествуют любым writes. Executor
проверяет все new pack/member/body identities, не использует upsert и не
открывает/коммитит собственную транзакцию. Ошибки выходят к владельцу UOW.

Pack/member create/copy/replace, instantiate/publish, legacy confirm adapter,
доменные SQL entry points, FS-import и manifest-less legacy bodies подключены
к общей границе. Старые `remapOps`, `reinstantiateOps`, `memberCopyOps` и
дублирующие body writers удалены. Exact edit/copy по UID сохраняют существующие
явные операции §0.2–0.3 через ту же policy/planning, без нового wire-протокола.
Дубли при обычном domain upsert требуют выбора, а не считаются edit.

FS сначала читает выбранные тела, затем пишет общим сервисом. Single-file
import заменяет только member; доверенный canonical attach отдельно сохраняет
insert-missing. World-колонки resolve при prepare, накладываются на свежий World
через prepared apply. SQL-сервис без подключённого общего writer отказывает;
старый in-memory seam не используется runtime DI. У remapped legacy members
с source UID зафиксирован `member_copy`, согласованный с provenance §3.

Проверка: 260 `test_library*.py` — OK; после уточнения mixed batch preview
повторно 18 L-4 integration tests (включая новый copy-only + replace сценарий) — OK.
18 world-column + 20 canonical + 20 bundle tests — OK; compileall и
`git diff --check` — OK. Дополнительный `test_database_bootstrap_conn.py`:
3/4 OK, прежний несвязанный сбой fixture — отсутствует `system_grade_uid` в
локальной тестовой таблице при наличии поля в HEAD-модели. Эти test/DDL и
map-cell writers не изменялись. Backend не запускался; commits/push отсутствуют.
Общий DAG и SQL schema не менялись. HTTP/frontend остаются L-5, world bundle
4d использует готовый caller-UOW seam и реализуется своим шагом.

- Цель: все пользовательские pack/member операции проводят запись через
  единый сервис; повторный запрос безопасен при изменившемся состоянии.
- ТЗ: §0.3, §2–4, §6–7.
- Файлы: `libraryPacks/writeService.py`, `writeExecutor.py`, `packService`,
  `memberOps/memberCopyOps/packOps/remapOps/reinstantiateOps`, domain library
  services/FS readers, `core/container.py`, интеграционные tests.
- Контракт: split parse/validate от FS writes; служебный persistence только
  применяет plan. Старые entry points делегируют сервису без второй policy.
  Canonical attach сохраняет insert-missing и свои атомарные гарантии.
- Обязательный контракт для bundle 4d (согласовано 2026-10-12): executor
  применяет подготовленный библиотечный plan в caller UOW импорта мира
  без собственного commit; финальная проверка актуальности защищена этой
  же UOW. Ошибка entity/library-секции откатывает весь импорт.
- Проверка: `python -m unittest discover -s tests -p test_library_write_service.py`;
  rollback, batch, stale source/target, гонка, запрет обходного upsert,
  неизменность оригинала, canonical attach; существующие pack/lifecycle tests.
- Done: одинаковые решения для всех входов, без дублирующего confirm-протокола.

## L-5 — общий HTTP-контракт и фронт — **выполнен 2026-10-13**

- Решение пользователя 2026-10-13: fallback из manifest пака отложен
  в `docs/tz_library_contextual_fallback.md`. SQL-хранение defaults и
  resolver world/pack override не являются зависимостью L-5/4d.

- Уточнение пользователя 2026-10-13: импорт целого мира по умолчанию делает
  независимую копию с remap; обновление существующего мира строится через
  библиотеки и политику патчей. Обязательный выбор
  world mode update/copy при коллизии снят. Full-world
  update пока не считать обязательным согласованным маршрутом. Это решение
  не вводит default copy/replace для конфликтов библиотек: их проверяет
  общий decisions/token pipeline.

- Регрессии ревью `c5d5b2c3` исправлены отдельной работой:
  [самостоятельный план LIBWRITE-TD-1…3](library-write-l4-review-debt-done.md)
  (done 2026-10-13), без ожидания L-5/4d. L-5 переиспользует созданные там
  transport DTO/serializer/error mapper; эти исправления уже выполнены.
- Цель: единый двухэтапный обмен вместо независимых import/copy обработчиков.
- ТЗ: §0.3, §4; frontend contract при необходимости уточняется до правок UI.
- Файлы: pack/template/import routes, request/response models, errorMapping,
  bundle import entry points; существующие frontend library API/UI после
  инвентаризации (не создавать редактор библиотек вне отдельного запроса).
- Контракт: HTTP 409 + `status=policy_required`, preview/token; повторный
  запрос передаёт decisions/token. Транспорт только сериализует результат
  L-4. Source-grep прямых write обходов входит в приёмку. Готовые внешние
  маршруты архивов координируются с 4d/C-4, их работу не перезаписывать.
  Допустимый запрос без конфликтов может применяться сразу. Если требуется
  выбор или token stale, весь запрос откатывается до ответа, включая
  временно созданный мир при world import. Caller UOW сохраняется.
- Bundle 4d обязан переиспользовать общий preview/decisions/token контракт;
  отдельные library confirm/policy правила в bundle запрещены. Default
  world copy не подменяет библиотечные решения. Решение об отложенных
  defaults и техническая задача стабильности повторного copy ведутся в
  [актуальном анализе 4d/L-5](library-packs-4d-l5-analysis-done.md#актуальные-открытые-вопросы-после-согласований).
- Проверка: `python -m unittest discover -s tests -p test_library_write_api.py`;
  policy-required запрос без сохранённых изменений, copy/replace, forbidden,
  stale и batch; успешный импорт без конфликтов с первого запроса;
  применимые frontend checks если существует соответствующий UI.
- Done: доступные пользовательские записи паков/members используют общий
  контракт; отсутствие library UI явно отмечено, backend контракт завершён.
- **Итог 2026-10-13:** `routes/libraryPacks.py` + `libraryArchives.py` и
  импорт мира в `routes/worlds.py` работают через `WriteNegotiation`/
  `parse_negotiation` + `policy_response` (409 `policy_required`,
  preview/token, stale); `LibraryPackPolicyRequiredError` покрыт
  глобальным `errorMapping`. `frontend/src/api/worldApi.js#importWorld`
  передаёт decisions/preview_token и сохраняет structured outcome.
  Library-редактор UI отсутствует — в scope не входил. Source-grep:
  обходных write-путей нет (SQL-записи relief/structure — только через
  общий write service; без provider при наличии db — RuntimeError).
  Приёмочные suites зелёные.

## Зависимости и границы

L-1 → L-2 → L-3 → L-4 → L-5. 4d обязательно зависит от L-4 и переиспользует
его pipeline в общей UOW мира; HTTP-интеграция 4d согласуется с L-5.
Основа: сделанные 4a–4c; L-5 синхронизируется
с routes/import из 4d и C-4. 5a может разрабатываться независимо, 5b
координирует те же writer/adapter файлы с L-4. Не менять DAG, SQL schema
без необходимости, не стартовать backend и не коммитить без просьбы.
