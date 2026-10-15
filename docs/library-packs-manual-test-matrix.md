# Матрица ручной приёмки library packs — шаги 6–7 и регрессия

Дата: 2026-10-16. Статус: подготовлена; ручной прогон не выполнялся.

Источник требований: `.cursor/plans/library-packs-model.md`, шаги 6–7;
`tz_template_library_packs.md` §0.3/1/2/4/5/6;
`tz_domain_template_libraries.md`; `tz_terrain_relief.md` R21/R29;
`tz_json_validation.md` — global canonical defaults.

У каждого кейса фиксировать: PASS / FAIL / BLOCKED, фактический результат,
HTTP request/response, относящийся к кейсу фрагмент лога и SQL before/after.
BLOCKED не считать успешным прогоном. Все кейсы ниже пока NOT RUN.

## Подготовка и контрольные состояния

Прогон выполняет мастер на отдельной тестовой БД. Сервер запускает мастер.
Заранее записать commit/diff, путь тестовой БД, cwd процесса, env roots и seed.
Для восстановления checkpoint остановить сервер; checkpoint SQLite включает
согласованное состояние WAL, а не копию одного файла работающей БД.

- **C0** — новая схема, template bodies и pack catalog пусты; сервер запущен,
  библиотечных HTTP-чтений ещё не было. Проверить SQL: startup сам по себе
  не считается доказательством пустоты. Для кейсов «первое чтение» каждый раз C0.
- **C1** — после canonical attach: 13 structure, 11 building, 11 plot,
  три engine default-пака и 35 memberships; relief bodies отсутствуют.
  Это числа текущего shipped graph, не универсальная константа контракта.
- **W0** — импортирован `fixtures/world_test_002.json`, подготовлены L0/topology
  штатным full bake; район выбран, outdoor этого района ещё не materialized.
  Ручного импорта structure/building/plot-паков не было.
- **A/B** — два тестовых мира. A можно использовать `world-test-002`, B —
  отдельную копию через штатный world copy/import. После copy использовать UID
  из ответа и экспорта: старые location/template UID могут быть remapped.
- **R0** — `relief_templates/smoke_003` явно импортирован только в engine library,
  но не инстанцирован ни в A, ни в B.

Запросы ниже используют base `http://localhost:8000/api`.
Swagger: `http://localhost:8000/docs`. Не путать JSON body и multipart form.
`find_by_uid` — сервисный метод, отдельного HTTP find endpoint нет.

Для W0: импортировать fixture через `POST /worlds/import` (multipart `path`
или `file`), затем `POST /worlds/world-test-002/map/pack/bake?mode=full`.
Settlement fixture: `loc-city-ironhold-002` или `loc-city-amberport-002`.
Актуальные district UID получить через
`GET /worlds/world-test-002/locations/{settlement_uid}/children` и тип `district`.
Если подготовка world/map падает раньше библиотечного сценария — BLOCKED,
сохранить ошибку подготовки отдельно.

## Обязательная приёмка: canonical structures

### S01 · P0 · Первое list-чтение заполняет пустую БД

- **До:** C0.
- **Действия:** `GET /structure-templates`; SQL bodies/catalog/deps before/after.
- **Ожидание:** 200, 13 structure summaries; SQL соответствует C1. Есть
  membership каждого canonical UID и dependencies building/plot → structures.
  User-паки не созданы. Relief остаётся пустым.

### S02 · P0 · Первое get-чтение тоже выполняет attach

- **До:** отдельный C0; UID взять из `structures_templates/base/pack.manifest.json`,
  не из предварительного HTTP list, который уже заполнил бы БД.
- **Действия:** `GET /structure-templates/{canonical_uid}`.
- **Ожидание:** 200, тело найдено, весь canonical graph доступен в SQL;
  `data.system_name == template_uid`. `source_file` — диагностика под
  `structures_templates/base/`, не абсолютный env-root.

### S03 · P0 · Повтор attach идемпотентен

- **До:** C1, сохранить UID, bodies, source_file, memberships/deps.
- **Действия:** трижды list/get, перезапуск сервера, ещё один list/get.
- **Ожидание:** состав и тела неизменны, UID стабильны, дубликатов нет.
  Непустая таблица не используется вместо проверки полноты.

### S04 · P0 · Частичная библиотека восстанавливается

- **До:** отдельная копия C1. При остановленном сервере подготовить три
  независимых варианта: отсутствует canonical body; отсутствует membership;
  отсутствует dependency row. Остальные строки сохранить как baseline.
- **Действия:** запуск и `GET /structure-templates` в каждом варианте.
- **Ожидание:** пропуск восстановлен; сохранённые тела/source_file не заменены;
  нет переезда UID в другой пак. API delete default-member для подготовки
  не использовать: это запрещённая пользовательская операция.

### S05 · P0 · Existing override canonical UID сохраняется

- **До:** отдельная копия C1. Служебно при остановленном сервере задать
  существующему canonical UID валидное изменённое тело с заметным display_name
  и `source_file=user/override.json`; согласовать денормализованную строку.
- **Действия:** get/list несколько раз и после restart; сравнить SQL.
- **Ожидание:** пользовательское тело и source_file сохранены побайтно по
  содержимому данных; canonical source не перетирает запись.
  Обычный CRUD default-пака для подготовки не подходит: он read-only.

### S06 · P1 · Конкурентный attach на холодной БД

- **До:** C0.
- **Действия:** одновременно из двух клиентов get/list structures.
- **Ожидание:** оба запроса успешны, один полный graph, по одной строке на UID,
  нет duplicate PK, database locked, частично опубликованного graph.

### S07 · P0 · cwd не влияет на fallback root

- **До:** env `STRUCTURES_TEMPLATES_ROOT` отсутствует; C0 в двух отдельных
  прогонах. Junction `backend/structures_templates` отсутствует.
- **Действия:** мастер запускает backend сначала из repo root с корректным
  import path, затем из `backend/`; в каждом прогоне S01/S02.
- **Ожидание:** одинаковые UID, bodies и source_file; root — repo
  `structures_templates/`, не `backend/structures_templates/`.
  Ошибка Python import path при запуске — ошибка подготовки, не root resolver.

### S08 · P0 · Явный env-root действительно используется

- **До:** C0; отдельная полная копия `structures_templates/base` с manifest.
  В одном теле изменить display_name, не UID/refs; env задаёт абсолютный
  domain root, содержащий папку `base`, а не путь самой папки `base`.
- **Действия:** restart с `STRUCTURES_TEMPLATES_ROOT`, get соответствующего UID.
- **Ожидание:** marker из внешнего источника; все refs graph разрешаются;
  source_file остаётся domain-relative. После очистки env вернуть штатный root.

### S09 · P1 · Необъявленный FS-контент не auto-default

- **До:** C0, внешний structures root с валидным base; дополнительно
  `user/pack.manifest.json` с повреждённым JSON и lone `orphan.json` вне base.
- **Действия:** list/get structures, проверить catalog.
- **Ожидание:** чтение успешно, только canonical graph; посторонние файлы
  не прочитаны как canonical source, user-пак не импортирован.

### S10 · P1 · Ошибка canonical source атомарна

- **До:** C0, внешний structures root с повреждённым manifest/body внутри base.
- **Действия:** первое get/list; записать response и лог; проверить SQL.
  Исправить источник и повторить чтение.
- **Ожидание:** первый запрос явно завершается ошибкой источника, без частичных
  bodies/catalog/deps и без молчаливого fallback к штатной папке; повтор после
  исправления успешен. Точный HTTP-код ошибки canonical source не закреплён
  этим шагом; записать фактический код, отсутствие записи — обязательный oracle.

## Обязательная приёмка: генерация и persist

### G01 · P0 · Свежий мир генерирует район без ручного импорта

- **До:** W0, выбрать один settlement/district; сохранить snapshot SQL.
- **Действия:** `POST /worlds/world-test-002/locations/{settlement_uid}/generate-settlement?district_uid={district_uid}`.
- **Ожидание:** успешная реальная materialization, а не skipped; canonical
  graph появляется без `/structure-templates/import`; здания/комнаты/persist
  создаются штатно. Применённые structure refs указывают на реальные доступные
  member UID, а не local name или выдуманный selector.

### G02 · P0 · Повтор не маскирует проверку runtime

- **До:** результат G01 и отдельный checkpoint W0.
- **Действия:** (a) повторить запрос G01 с default skip; (b) восстановить W0
  и повторить реальную генерацию с тем же seed/настройками.
- **Ожидание:** (a) нет дублей, штатный skip допустим; (b) выполняется packing,
  те же применённые template refs при тех же входах, без ручного импорта.
  Один skipped-запрос не доказывает повторный runtime resolve.

### G03 · P0 · Недоступная явная structure-ссылка

- **До:** отдельный W0; authored world plot/building с явным structure UID
  из чужого/неинстанцированного user-пака либо отсутствующим UID. Зафиксировать
  сохранённый ref до запуска. При необходимости служебно подготовить legacy
  неконсистентное состояние: современный writer может отклонить его раньше.
- **Действия:** реальная генерация района, сравнить лог, исходное тело и NL refs.
- **Ожидание:** доменная диагностика и предусмотренный POJO fallback; нет
  global SQL/FS bypass. Сохранённая авторская ссылка не переписана; persist
  применённого structure соответствует фактическому результату, а не запросу.
  Отдельно зафиксировать, исключён ли invalid candidate на snapshot boundary;
  не требовать выбора недоступного кандидата.

## Обязательная приёмка: relief

### R01 · P0 · Пустые defaults не импортируют smoke_003

- **До:** C0; на диске штатный `relief_templates/smoke_003`.
- **Действия:** `GET /relief-templates`, затем get отсутствующего UID;
  проверить relief bodies/catalog before/after.
- **Ожидание:** 200 + `[]`, get — 404; нет relief pack/member/body записей.
  Чтение relief само по себе не должно заполнять structure graph.
  Наличие FS-пака не делает его default.

### R02 · P0 · Явный импорт использует env-root

- **До:** C0; копия smoke_003 во внешнем domain root,
  env `RELIEF_TEMPLATES_ROOT` указывает на него; restart.
- **Действия:** сначала R01; затем `POST /relief-templates/import`, multipart
  `path=smoke_003`; get/list импортированных UID.
- **Ожидание:** до import пусто; import возвращает 4 тела; после — SQL bodies
  с source_file под `relief_templates/smoke_003/`, engine user-пак, не default.
  Повторить fallback-root проверку из repo/backend без env, на независимых C0.

### R03 · P0 · Частичная SQL-библиотека не чинится FS-сканированием

- **До:** R0; служебно изменить одно body/source_file, удалить другое body,
  сохранив его membership. Использовать отдельную тестовую копию.
- **Действия:** несколько get/list, в том числе параллельных, затем restart.
- **Ожидание:** override/source_file сохранены; отсутствующее user body не
  восстановлено автоматически, get его UID — 404; пустой relief spec ничего
  не записывает. Наличие повреждённого постороннего FS-пака не мешает чтению.

### R04 · P0 · Engine library не даёт world availability

- **До:** R0, A/B без инстансов; административный get engine relief UID успешен.
- **Действия:** inspect memberships/owner и world exports A/B. Для реального
  resolve запустить штатный relief consumer на одном тестовом scope с fixed
  engine UID, зафиксировав policy; для snapshot-only проверки использовать
  сервисный seam `load_relief_templates_for_world`, отдельного HTTP snapshot нет.
  HTTP consumer: `POST /worlds/{world_uid}/map/pack/bake?mode=detailed&scope=location&location_uid={settlement_uid}&grade_mill=true&grade_paint=true`.
  Выбрать scope, в котором реально есть grade нужного context, и свежий
  checkpoint без готового materialized результата. В world `relief_pick_policy`
  установить fixed UID именно для этого context; отсутствие pick-события
  означает BLOCKED/неподходящие входы, а не PASS.
- **Ожидание:** engine UID не становится кандидатом A/B. Relief применяет R21:
  warning + отказ, а не structure-style fallback и не выбор произвольного тела.
  Исходный policy ref не переписывается. Пустой пул → `DOMAIN_NO_CANDIDATE`;
  пул непуст, fixed UID недоступен → `REF_W_UNKNOWN`.

### R05 · P0 · Инстанс только в A, затем явно в B

- **До:** R0 и A/B.
- **Действия:** `POST /worlds/{A}/library-packs/instantiate` с JSON
  `{"source_pack_uid":"<engine_pack_uid>"}`. Проверить members/owner/UID map;
  fixed policy A задавать UID инстанса, не engine UID. Выполнить resolve A/B;
  затем явно инстанцировать исходный пак в B и повторить с B UID.
- **Ожидание:** A получает все 4 members, B до instantiate — ни одного;
  B после — свои members. UID A/B/engine различаются, provenance сохранён;
  разрешаются только refs своего доступного каталога. Два мира не делят
  изменяемое тело одного user member.

### R06 · P1 · Pick-policy и диагностика не изменились

- **До:** A с двумя доступными relief members одного context.
- **Действия:** fixed на свой UID; random с тем же seed/site;
  round_robin с последовательными occurrence_seq; затем fixed на чужой UID.
- **Ожидание:** fixed выбирает свой member; random воспроизводим; round_robin
  идёт по сортированным member UID. Чужой fixed → одна warning-запись на
  событие и R21, исходный ref неизменен. Pin не требуется каждому кандидату.
  HTTP bake должен реально выполнять relief pick; skipped/cache hit недостаточен.
  Точное управление site_id/occurrence_seq — сервисный debug-прогон: публичный
  HTTP route не принимает их как query. Если доступен только HTTP, отдельно
  записать покрытие этого фрагмента `test_library_packs_5b_relief.py`, не
  выдавать обычный bake за проверку всей последовательности round_robin.

## Регрессия общего pack lifecycle

### L01 · P0 · Default-пак read-only для пользователя

- **До:** C1; canonical pack/member UID известны.
- **Действия:** PATCH/DELETE `/library-packs/{default_pack_uid}`;
  PUT/DELETE `/library-members/{canonical_uid}` с валидным телом.
- **Ожидание:** 403, тела/membership/deps не изменены. Canonical attach S04
  остаётся единственным разрешённым additive восстановлением defaults.

### L02 · P1 · Same local_uid в разных паках

- **До:** два разных editable user engine-пака.
- **Действия:** создать в каждом однотипный member с одинаковым local_uid;
  получить обоих по `/library-members/{template_uid}`.
- **Ожидание:** разные UID, оба тела сохранены; нет глобальной name-коллизии.
  Повтор в том же паке не создаёт второй member с той же локальной identity:
  применяется явная negotiation/ошибка, без скрытого replace.

### L03 · P0 · Preview и stale не пишут

- **До:** импортируемый/инстанцируемый user-пак конфликтует с существующим;
  сохранить bodies/catalog/world refs.
- **Действия:** повторить write без decisions; сохранить 409 preview_token;
  изменить target другим клиентом; подтвердить старый preview.
- **Ожидание:** первый 409 `policy_required` и повторный stale-preview не
  меняют SQL. Decisions брать из реально разрешённых choices, а не выдумывать
  target UID. Новый актуальный preview нужен перед применением.

### L04 · P1 · Явные copy/replace и повтор instantiate

- **До:** конфликтующий user-пак, актуальный preview.
- **Действия:** на независимых checkpoint подтвердить разрешённые copy и
  replace; затем повторить instantiate того же source в тот же мир.
- **Ожидание:** copy выдаёт новые identities/remap и сохраняет source;
  replace меняет только разрешённый target, сохраняет его ownership;
  повтор instantiate не плодит случайные инстансы. Если требуется policy,
  возвращается preview, а не применяется скрытое решение.

### L05 · P1 · Re-instantiate удерживает используемые members

- **До:** A с инстансом user-пака; один member pinned, другой реально referenced
  в location/template. Исходный engine-пак изменён: эти members удалены,
  появился новый. Зафиксировать source/instance и все refs.
- **Действия:** повтор instantiate, изучить preview held/preserved, подтвердить
  разрешённую актуальную операцию.
- **Ожидание:** pinned ∪ referenced members удержаны; unused можно убрать;
  новые добавлены; refs не dangling. Не принимать результат, если источник
  молча меняет сохранённые applied structure refs уже materialized зданий.

### L06 · P0 · World/library archive round-trip и remap refs

- **До:** A с пользовательскими instance-паками, internal structure refs,
  policy refs и persisted `system_structure_template_uid`.
- **Действия:** `GET /worlds/{A}/export?download=true&level=skeleton`;
  импорт в отдельную БД/мир через штатную negotiation copy. Дополнительно
  export/import engine library через `/library-packs/{pack_uid}/export`
  и multipart `POST /library-packs/import`.
- **Ожидание:** bodies/members/ownership/deps/provenance не теряются;
  world copy remaps все world-local refs, включая persisted structure UID;
  canonical defaults остаются shared defaults. Engine archive импортирует
  library, не подключает user-пак к произвольному миру.

### L07 · P1 · Missing dependency не auto-instantiated

- **До:** пользовательский building/plot-пак зависит от другого user structure
  пака; в мире присутствует только consumer, dependency недоступна.
- **Действия:** проверить diagnostics и реальную генерацию; затем явно
  подключить требуемую dependency в тот же мир согласованным импортом/remap.
- **Ожидание:** до подключения — диагностируемый gap/доменный fallback, без
  global lookup; после — graph замкнут по доступным UID. Одного presence
  dependency body в общей SQL library недостаточно.

### L08 · P1 · Невалидный import откатывается целиком

- **До:** валидный архив с несколькими members, один body испорчен; baseline SQL.
- **Действия:** импортировать архив и world bundle на независимых checkpoint.
- **Ожидание:** ошибка валидации/rolled_back, нет частично применённых новых
  bodies/packs/deps/world refs. Ошибку транспорта и application failure отличать;
  world bundle может отвечать 207 + `rolled_back=true`, а не обязательно 422.

## Аудит opt-out и условия приёмки

### A01 · P1 · Остальные домены сохраняют свой источник и policy

- **До:** world с barrier/district/purpose overrides, canal entries, lore map,
  явно импортированными race/perk pointers.
- **Действия:** экспорт before; выполнить canonical/relief list/get и restart;
  экспорт after; просмотреть domain audit в `tz_json_validation.md`.
- **Ожидание:** world inline/pointer данные не меняются от global reads.
  Barrier/district/purpose — прежний T-29 по своим ключам; canal — world list;
  lore — world map; race/perk — явный import/create и world pointers.
  Новых auto-default записей/паков для opt-out доменов нет.

P0 — обязательный gate приёмки шагов 6–7 и основных интеграционных гарантий.
P1 — расширенный ручной прогон краевых случаев/регрессии. Для каждого P1,
который не прогоняется вручную, явно записать основание покрытия автотестом
или согласованный перенос; не отмечать PASS без запуска.

Минимальный первый проход: S01, S02, S03, S05, S07, S08, G01, G02,
R01, R02, R04, R05, L01. Он проверяет основной сценарий и окружение;
не заменяет полный P0 gate. План не закрывать только по числу HTTP 200.

## Команды для первых проверок

```powershell
$api = 'http://localhost:8000/api'
curl.exe "$api/relief-templates"
curl.exe "$api/structure-templates"
curl.exe -X POST "$api/relief-templates/import" -F 'path=smoke_003'
curl.exe "$api/worlds/world-test-002/locations/loc-city-ironhold-002/children"
```

Эти команды запускать в порядке нужного кейса: GET structures заполняет C0,
а POST relief import нарушает предусловие R01. Для JSON-запросов в PowerShell
удобнее Swagger или `Invoke-RestMethod -ContentType 'application/json' -Body …`.

Read-only SQL для сверки (подставить фактические UID через параметры клиента):

```sql
SELECT 'structure' AS kind, COUNT(*) AS n FROM structure_templates
UNION ALL SELECT 'building', COUNT(*) FROM building_templates
UNION ALL SELECT 'plot', COUNT(*) FROM plot_templates
UNION ALL SELECT 'relief', COUNT(*) FROM relief_templates;

SELECT pack_uid, system_name, owner_world_uid, source_pack_uid FROM library_packs;
SELECT pack_uid, library_kind, local_uid, template_uid, source_template_uid
FROM library_pack_members ORDER BY pack_uid, library_kind, local_uid;
SELECT * FROM library_pack_dependencies;

SELECT template_uid, display_name, source_file, data
FROM structure_templates WHERE template_uid = :structure_uid;
SELECT template_uid, display_name, source_file, data
FROM relief_templates WHERE template_uid = :relief_uid;
SELECT location_uid, system_template_uid, system_structure_template_uid
FROM named_locations WHERE world_uid = :world_uid;
```

Для каждого прогона сохранить отдельную запись вида:
`S01 | NOT RUN/PASS/FAIL/BLOCKED | checkpoint | request | response/log/SQL | заметка`.
Служебные corrupt/override сценарии описаны как подготовка тестовой копии;
никаких SQL/FS изменений эта матрица сама не выполняет.
