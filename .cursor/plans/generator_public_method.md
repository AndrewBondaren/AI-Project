# generator_public_method — реестр требований к публичным методам генератора

**Статус:** EXACT CONTRACT PROPOSAL / НА ПРИЁМКЕ, 2026-11-02. Freeze не принят; implementation OPEN. Создан по поручению пользователя; существующего плана с этим именем при поиске не найдено. Не является реализацией новых API или разрешением production cutover.

Публичные reads реализует генераторный/Pack домен; GEN-DAG потребляет принятые контракты. Имена методов ниже — target proposal, не существующие символы кода. Предлагаемые владельцы, POJO и exact files описаны в GEN-BAKE-READ §§5–10; внешние OPEN contracts — §11. Они ещё требуют приёмки.

| Имя ноды | Имя публичного метода | Требуемый результат | Техдолг | Отдельный план |
|---|---|---|---|---|
| `read_world_light_bake` | `read_light_bake` (world coverage, LightReadRequest, proposal GBR-1) | Полный light-комплект мира: data/refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `read_scoped_light_bake` | `read_light_bake` (request scope, LightReadRequest, proposal GBR-1) | Полный light-комплект запроса: data/refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_full_bake` | `read_full_bake` | Full L0 + требуемая topology: data/refs либо missing | [GEN-READ-2](../../docs/tz_generator_technical_debt.md#gen-read-2) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_detailed_bake` | `read_location_l2` | L2 owning scope выбранной location: data/refs либо missing | [GEN-READ-3](../../docs/tz_generator_technical_debt.md#gen-read-3) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |

Для всех методов: явные world/scope/publication inputs, отдельный Error для corruption/read failure/stale refs; нет генерации, writes, fallback, SQL/filesystem знания в ноде. Это domain reads, не HTTP endpoints и не новый central gameplay facade.

Полные требования, AS-IS evidence, ссылки на readers/classifier/facades и порядок реализации принадлежат [GEN-BAKE-READ](./generator-public-bake-reads.md). Потребители и форма found/missing: [GEN-DAG-NODE-DEPENDENCY §§8–9](./gen-dag-node-dependency.md#9-input--output-трёх-bake-read-нод--уточнение-пользователя).

Изменение названий/контрактов синхронизируется в обеих картах и техдолге; самостоятельно копировать readers в DAG или считать метод принятым по наличию строки здесь запрещено.

**Light readers:** группа light_bake_readers содержит read_world_light_bake и read_scoped_light_bake; смысловые I/O/Error/DoD — [§9.5 реестра нод](./gen-dag-node-dependency.md#95-light_bake_readers--выходные-контракты-и-definition-of-done). Обе читают L0 и обязательные связанные index/climate/metadata для своего coverage. Общий domain reader допустим. check_light_bake сохраняет прежнее родство; replacement bindings новых нод OPEN, нового parent NodeId нет. NamedLocation entry использует scoped reader; world complete не его prerequisite.

## Публичные preparation pipelines — отдельные domain-owned интерфейсы

Эта секция не является read-картой выше. Имена target interface/method фиксируются как требования реализации; наличие строки не означает готовый API или изменение зафиксированных нод.

| Потребляющая операция | Owning domain | Интерфейс / метод | Выход / DoD | Отдельное требование |
|---|---|---|---|---|
| L0 light/full preparation и L2 detailed preparation, когда нужен surface plan; exact node binding OPEN | surface planning | `ISurfacePlanningPipeline.prepare_surface_plan` | Согласованный immutable surface-plan bundle для captured inputs, exact dependency/source evidence и diagnostics; без world publication | [GEN-SURFACE-PLAN](./generator-public-surface-planning.md), [GEN-PLAN-1](../../docs/tz_generator_technical_debt.md#gen-plan-1) |

Capture boundary, exact types/files и baseline/GEO choice требуют domain freeze. Readers не получают обязанности подготовки или передачи настроек. Имена остальных ещё не разобранных pipeline interfaces не назначаются автоматически.

## Climate и Weather — публичные операции для DAG

[Пример оркестрации погоды сцены через DAG](./api-1-climate-c1-d1.md#пример-оркестрации-погоды-сцены-через-dag) показывает вызовы доменных методов из нод и передачу результатов между нодами.

**Повторная проверка по общему правилу доменов:** целевые маршруты соответствуют трём запретам. [Разбор 13 методов и исправления](./api-1-climate-c1-d1.md#приёмка-маршрутов-по-трём-запретам). Реализация и bindings требуют отдельной приёмки.

Предлагаемая публичная поверхность для DAG. **C1** — первый срез настроек; **расчёт** — методы генерации и сцены; **реестры** — последующий срез редактирования. Имена целевые. R — точная публикация выбранного мира. База изменения включает исходное состояние владельца и версии прочитанных зависимостей. Каждый prepare возвращает результат с этой базой; окончательную проверку свежести и commit выполняет владелец приёмки.

| Домен | Метод | Функционал | Контракт |
|---|---|---|---|
| Climate | `read_settings` | C1 · Прочитать настройки климата | (world_uid, R) → R, WorldClimateScalars и WorldClimateZoneRegistry. WorldNotFound / PublicationUnavailable / InvalidStoredSettings. Без записи. |
| Weather | `read_weather_rules` | C1 · Прочитать правила погоды | (world_uid, R) → WeatherRulesView с WorldWeatherTypeRegistry на R. Те же ошибки чтения. DAG объединяет оба результата только для одной пары (world_uid, R). |
| Climate | `prepare_change` | C1 · Подготовить частичную правку девяти скаляров | (база, PatchClimateScalars, MaterialRegistryView от DAG) → полный кандидат Climate, версии зависимостей, consequences. Пропуск сохраняет значение; явный null проверяется типом. InvalidPatch / InvalidSettings / InvalidReference / UnsupportedField. Preview и save используют одну подготовку. |
| Climate | `prepare_materialization` | Расчёт · Подготовить климатическое поле запрошенной области | (закреплённый план, область, LOD, входы Climate) → покрытие, происхождение данных и refs подготовленных артефактов. Проверить полноту и совместимость входов; возможен staging. Публикацией управляет DAG через Pack/Snapshot. |
| Climate | `prepare_recalculation` | Расчёт · Пересчитать затронутую часть поля | (закреплённый план, существующая база поля, ClimateFieldRecalcInput с областью без флагов стадий) → refs изменённых частей с их базой либо успешный пустой результат. Несовместимая база — ошибка. Форматы refs и ошибок обеих операций материализации OPEN. |
| Climate | `sample_scene_climate` | Расчёт · Вычислить климат сцены с учётом сезона | (SampleRef, temperature_base:int или null, rainfall:int или null, season:SeasonKey или null из привязки DAG к выходу Time, SeasonTempOffsets той же базы) → SceneClimateSample с исходной и эффективной температурой, осадками и ref либо IncompleteSceneClimate с ref, доступными значениями и именами отсутствующих полей. Измеренный 0 сохраняется. Без сезона effective = base. SourceMismatch при несовместимых входах. |
| Weather | `resolve_weather` | Расчёт · Выбрать погоду сцены одним линейным OpenPipeline | (полный SceneClimateSample, WeatherRulesView) → WeatherSnapshot с system_weather. Проверить мир и R, применить пороги по priority и fallback clear по ТЗ. SourceMismatch при расхождении. Без записи карты. |
| Climate | `prepare_upsert_zone` | Реестры · Добавить или заменить одну зону | (база, ClimateZoneEntry) → кандидат реестра с полной записью по system_climate. InvalidSettings / InvalidReference по итоговому состоянию. |
| Climate | `prepare_remove_zone` | Реестры · Удалить зону | (база, ключ system_climate, RegistryUsageView[] от DAG) → кандидат без записи; EntryNotFound либо InvalidReference, если сохраняется ссылка на зону. |
| Climate | `prepare_replace_zones` | Реестры · Заменить весь авторский список зон | (база, WorldClimateZoneRegistry, RegistryUsageView[] для затронутых ключей) → кандидат после проверки уникальности ключей и ссылок. InvalidSettings / InvalidReference. |
| Weather | `prepare_upsert_weather_type` | Реестры · Добавить или заменить один тип погоды | (база, WeatherTypeEntry, снимки Need/Glossary от DAG) → кандидат с полной записью по system_weather. InvalidSettings / InvalidReference по итоговому состоянию. |
| Weather | `prepare_remove_weather_type` | Реестры · Удалить тип погоды | (база, ключ system_weather, RegistryUsageView[] от DAG) → кандидат без записи; EntryNotFound / InvalidReference. |
| Weather | `prepare_replace_weather_rules` | Реестры · Заменить весь авторский список правил | (база, WorldWeatherTypeRegistry, RegistryUsageView[] и снимки Need/Glossary от DAG) → кандидат после проверки записей и уникальности system_weather. InvalidSettings / InvalidReference. |

Для этих строк действует [разделение публичных read/write/delete/settings, линейного OpenPipeline и оркестрации материализации](./api-1-climate-c1-d1.md#поверхность-доменов-и-ответственность-dag). DAG явно компонует Climate и Weather reads одной R. Генератор готовит результат своей операции; staging, сборка и принятие публикации следуют контрактам DAG/Pack/Snapshot. Для prepared удаления объектом является конкретная авторская запись соответствующего домена.

Для prepare_materialization и prepare_recalculation уточнён [контракт результата coarse/fine](./api-1-climate-c1-d1.md#результат-материализации-и-пересчёта-climate): адрес и покрытие каждой части, ArtifactRef в staging, полное покрытие или изменение относительно базы, ошибки и граница публикации.

I/O, ошибки, effects и пример — [API-1-C1/D1](./api-1-climate-c1-d1.md#публичные-контракты-climate-и-weather-для-dag). [Legacy inventory и результат проверки по правилам](./api-1-climate-c1-d1.md#проверка-плана-и-legacy-inventory). Статус — предложение, exact freeze и DAG bindings OPEN. Старые имена нод служат для трассировки. Прикладные операции Climate/Weather ведутся в C1; опубликованные bake reads и подготовка surface plan сохраняют своих владельцев.

## GBR-1 — историческая карта exact proposal

**Заменена поправками GBR-2 ниже; старые classes/fields не действующий freeze.**

Нормативный проект, включая поля/enum/errors/lifetime и сценарии:
[GEN-BAKE-READ §§5–12](./generator-public-bake-reads.md#5-exact-contract-freeze-proposal-gbr-1-2026-11-02).
Это документальная спецификация на приёмку, не existing production symbols.

| Операция | Proposed owner / factory | Exact Input → Output |
|---|---|---|
| read_light_bake | PackLightBakeReader; build_pack_read_services.light_bake | LightReadRequest(identity, publication, WorldLight либо RequestLight, control) → BakeReadFound[LightBakeData] либо BakeReadMissing |
| read_full_bake | PackFullBakeReader; build_pack_read_services.full_bake; C23 — SettlementTopologyRead | FullReadRequest(identity, publication, required scope, control) → BakeReadFound[FullBakeData] либо BakeReadMissing |
| read_location_l2 | PackTerrainBakeReader; build_pack_read_services.terrain_bake | LocationL2ReadRequest(identity, publication, target_uid, volumes, TERRAIN_L2, control) → BakeReadFound[LocationL2BakeData] либо BakeReadMissing |

Все методы async; typed BakeReadError exception и cancellation отдельно от
found/missing. Полные schemas и закрытый proposed error enum — owning §7.
Found содержит проверенные разрешимые immutable refs, pinned одной publication;
missing содержит nonempty exact absent/incomplete scope. Valid empty — found.
Declared artifact loss, stale/wrong-world/corruption/unsupported/read failure — Error.

World light сохраняет existing light_bake: static location anchor tiles ∪ declared hydro endpoint tiles; не world_bounds и без расширения на territories/interiors. Request
light проверяет весь request scope плюс обязательные index/climate/metadata;
world completeness не блокирует NamedLocation. Full = required L0 + применимые
целые C23 settlement closures; нет settlements → NOT_APPLICABLE, не missing.
L2 разрешает published leaf→terrain owner mapping, не файл на каждый leaf UID.
L2 found не доказывает C11 или Spatial wet/dry/known; L0 не canonical water source.

Отдельный coordinate/wilderness consumer requirement: предлагается
read_wilderness_l2 за PackTerrainBakeReader, но операция **не добавлена** к трём
принятым именам и требует отдельной приёмки. Fake NamedLocation запрещена.
Pin/absence/retention/GC, coverage producer receipt, immutable C23 publication join,
C11 evidence и coordinate API — конкретные внешние OPEN §11. Snapshot draft adapters
не готовые ports. SP-1/GEO EF-1 и частные SP-P0 §15.17 учтены; P0/M имеют отдельные документальные приёмки Spatial §§15.19/16.16; executable ports не приняты. Ни код, ни bindings, ни публикация/cutover не разрешены этой картой.

## Актуализация: принятое решение о видимой композиции

[GEN-BAKE-READ §13](./generator-public-bake-reads.md#13-решение-пользователя-публичные-read-ноды-и-видимая-композиция-2026-11-02)
имеет приоритет над первоначальной GBR-1 картой выше.

Публичные domain methods читаются через переиспользуемые публичные read-ноды;
другие ноды вызывают их через engine CALL/RETURN. Композиция самостоятельных reads
видна в DAG, а SQL/filesystem остаются внутри domains. Новые NodeIds/связи не приняты.

`PackFullBakeReader` и `build_pack_read_services.full_bake` отозваны. Full-result
предлагается собирать явной композицией light-read и C23-read нод с общей pinned
publication/retention. Строка read_full_bake сохраняет требование результата;
уровень/имя aggregate API и concrete binding OPEN, скрытый Pack composite запрещён.
PackLightBakeReader/PackTerrainBakeReader и topology-owner domain read остаются
proposed targets. Это принятие архитектурного принципа, не всего contract freeze.

**Актуальное уточнение пользователя:** сохраняются light_bake/full_bake/detailed_bake;
новые bake kinds не вводятся. Source-backed semantics и отменённые расширения —
[GEN-BAKE-READ §14](./generator-public-bake-reads.md#14-уточнение-семантики-по-генератору-без-новых-bake-сущностей).
Предложение read_wilderness_l2 отозвано как выбранное решение: wilderness уже
existing detailed scope, exact coordinate read API OPEN. Full consumer L0+C23
композиция не приписывается body L0 full producer. Class/POJO map пока proposal,
не разрешение создания новых production сущностей.

## Принятая архитектура readers

[GEN-BAKE-READ §15](./generator-public-bake-reads.md#15-принятая-архитектура-domain-readers-2026-11-02):
у каждого домена публичный reader с domain-owned typed contracts от целой сущности
через часть до минимальной доменной единицы. Whole entity допускает metadata+refs;
все уровни согласованы по revision. Consumers CALL публичные read-ноды; внутри них
вызов domain reader, без SQL/storage в нодах. Не каждому методу нужна отдельная нода.
Сначала reuse и контракт, затем concrete map. Это принятая архитектура, не freeze
предыдущих proposed классов. CRUD evidence: [инвентаризация](./generator-domain-crud-inventory.md).

## GBR-2 — актуальный proposal и gates (2026-11-02)

**Независимый review: REVISE BEFORE ACCEPTANCE; D1–D7 НЕ ПРИНЯТЫ.** Приоритетные поправки, контрпримеры, actual evidence и решения на согласование — [GEN-BAKE-READ §17.10](./generator-public-bake-reads.md#1710-независимое-adversarial-review-d1d7-2026-11-02). R0 review выполнен с замечаниями; acceptance и executable freeze не закрыты. Старые строки реестра о full как одном L0+topology API — историческое требование consumer, не разрешение скрытой композиции.

[Owning §17](./generator-public-bake-reads.md#17-gbr-2--продолжение-исследования-и-согласованный-предмет-review-2026-11-02) заменяет противоречащие строки GBR-1. **READY FOR DOCUMENT REVIEW, NOT ACCEPTED / NOT CODE-READY.** Архитектура domain readers и видимой композиции принята ранее, следующие exact решения ещё на согласовании.

| Consumer requirement (не accepted binding) | Proposed public operation | Output / gate |
|---|---|---|
| read_world_light_bake | PackL0BakeReader.read_light_bake(WorldLight) | Found[LightBakeData] / Missing + typed error; product anchor/endpoint set, shared artifacts; GBR-R5-L |
| read_scoped_light_bake | тот же метод, RequestLight explicit boxes/target | Requested tiles не сужаются до world-light; whole world readiness не вход; GBR-R5-L |
| check_full_bake | PackL0BakeReader.read_full_bake + separate topology-domain read | **Предложено:** method возвращает FullL0BakeData; consumer full=L0+C23 в видимой DAG composition на одной pin. Не hidden PackFullBakeReader. GBR-R5-L+R5-C |
| check_detailed_bake, NamedLocation | PackTerrainBakeReader.read_location_l2 | Owner-resolved terrain refs/dependencies; не C11 readiness. GBR-R5-T |
| coordinate/wilderness requirement | Отдельная explicit operation того же terrain domain reader; имя OPEN | Scope XYZ без fake UID; отдельная приёмка, не blocker NamedLocation |

Reuse existing WorldPublicationRef/ArtifactRef; explicit source/frame/scope и typed Found/Missing/Error. Ref resolution тем же domain reader возвращает immutable domain data, не file paths/reader/SQL. Caller заранее обеспечивает durable retention; read валидирует и заимствует transient access, durable holds не пишет. Exact pin остаётся пригодной при смене head, если retention/source requirements соблюдены; current-head admission отдельно.

Новая file/factory map — owning §17.6; первоначальные PackFullBakeReader/full_bake field и inline Pack→topology composition отозваны. packReadServices остаётся composition root для L0/terrain; topology factory/domain contracts отдельны. Exact external receipt types/imports и leaf projections ещё R1/R2, не скрытые готовые ports.

Этапы: GBR-R0 документальный review → R1 external semantic contracts → R2 exact freeze → независимые R3L/R3T/R3C по своим prerequisites → R4 cold/lifecycle evidence → R5 совместный GEN handoff. Код каждого этапа требует отдельной команды; no cutover. Межплановые proposed edges/parallelism, сценарии и решения D1–D7 — owning §§17.7–17.9. Общий граф не изменён.

Поправки review к этой краткой карте (всё на согласовании):

- `read_full_bake` проверяет full L0 required scope, включая bounded scope, переиспользует совместимые published tiles без требования последнего `bake_mode=full`. Consumer full видимо соединяет L0+C23; missing одной части не скрывает Error другой, no-settlements требует authoritative applicability census. Exact GEN composition/CALL bindings ещё не приняты.
- Existing WorldPublicationRef/ArtifactRef и VerifiedArtifactRef/holders — reuse candidates, не готовые pin/read ports. Нужны accepted publication membership, immutable locator/format mapping и retention всей closure. Manifest hash и mutable current paths этого не обеспечивают.
- External lifecycle удерживает closure до всех consumers и drain; read/resolve только borrow validated fenced access. Durable handoff новому owner подтверждается до release старого. Resolve принимает access evidence, exact pin и subset scope; stale/loss/out-of-scope — Error, не missing. Current-head admission отдельно от exact read и terminal placement CAS.
- Предложено исправить primary-only reason: required index/climate/sidecars также data components; ноль primary при существующей части комплекта — incomplete. Absent означает отсутствие всего required data; допустимая пустота требует proof. Unknown owner/invalid target не missing terrain; authoritative XYZ partition и absence observation обязательны.
- Immutable whole/part/leaf projections сохраняют L0 cell fields, L2 column facing/grade/region и terrain/material runs с coverage и coordinate binding; mutable wire lists не output. Пропущенная колонка не air без format evidence. Exact types и field parity ещё R2.
- Coordinate operation terrain reader — отдельный slice X без выбранного имени API, fake NamedLocation или нового bake kind. Required XYZ не берётся из remaining-work wilderness planner; named/wilderness backing precedence и parent dependencies определяет published layout.

Уточнённый порядок: R1/R2/R4/R5 по relevant L/T/C/X slice; C23 тоже требует R2-C, coordinate — R2-X/R3X/R4-X. Конкретные edges — owning §17.10.3, только предложение координатору. R5-L(light)→light binding; R5-L(full)+R5-C→full composition; R5-T→named terrain; R5-X→coordinate terrain. Нет whole-plan gates, world completeness→scoped или C11→terrain read. Applicable C11 остаётся detail readiness/placement gate. Runtime cold/GC/cancel/resume/ref-resolution evidence не получено. Изменены только документы; production POJO/ports, bindings, публикация и cutover не начаты.
