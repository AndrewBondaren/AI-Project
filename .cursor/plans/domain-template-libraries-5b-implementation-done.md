# План имплементации: доменные библиотеки plot/building/structure и шаг 5b ✅ DONE

## Актуальные ТЗ и правила — основание плана

Ссылки проверены по текущим файлам 2026-10-14. Нормативные источники:

- [Библиотеки plot/building/structure — A0](../../docs/tz_domain_template_libraries.md):
  §1 — композиция; §2 — defaults/overrides; §3–4 — storage/default packs;
  §5 — runtime/persist refs; §6 — selectors/legacy; §7 — ошибки и границы.
  Имеет приоритет над прежними POJO-only plot/name-based формулировками.

- [Паки библиотек шаблонов](../../docs/tz_template_library_packs.md):
  §0.2–0.3 — общий CRUD/writer; §1–1.2 — доступность, pins и usage;
  §2–3 — UID/владение/SQL; §4–4.2 — manifest/bundle/archive;
  §5–5.1 — resolve и доменный fallback; §6–8 — canonical attach, логи, инварианты.
- [Генератор зданий](../../docs/tz_building_generator.md): §2–3.1 — термины
  и plot wire; §3.2–3.9 — structure geometry; §5–6 — библиотеки/импорт;
  §7 — результат и template refs; §10 — валидация; §11.1/11.6 — building context.
- [Генератор города](../../docs/tz_city_generation.md): §3 — settlement
  selectors; §9.2/9.4 — district selectors и required plots; §11.3/11.5 — materialize/persist.
- [Соединения и packing](../../docs/tz_structure_connections.md): §5.1.3,
  подразделы «Число токенов», «Приоритет посадки», «Два прохода посадки».
- [Cascade / LocationContext](../../docs/tz_cascade_context.md): §2–4 —
  source-POJO, inheritance и terminal defaults; §8 — приёмочные случаи.
- [JSON validation](../../docs/tz_json_validation.md): «Field policy»,
  «WorldSlice» (внутри — единый движок canonical defaults), «Import path»,
  «Scoped column write», «Runtime path», «Bundle row DTO».
- [World bundle](../../docs/tz_world_bundle.md): «Критерий: library vs entity»,
  «Целевые домены», «Два рода handlers», «Порядок секций», «Domain errors».
- [JSON import](../../docs/tz_json_import.md): §10 — API, §11 — форматы.
  Для library policy/архивов более поздний pack-контракт §0.3/4.1/4.2 имеет приоритет.
- [Хранение данных](../../docs/project_data_storage_tz.md):
  «Детерминированные uid и rng (DET-1)», «Локации и карта мира» / named_locations.
- [Terrain relief](../../docs/tz_terrain_relief.md): «Библиотека и мир»,
  «Pick: мир → локация / объект», «Conditions» — действующие pick/ref контракты.
- [Логирование](../../docs/tz_logging.md): «Инварианты», «Каталог консьюмеров», «Маршрут».
- [Отложенный contextual fallback](../../docs/tz_library_contextual_fallback.md):
  «Базовый действующий контракт», «Идея расширения» и «Что определить до реализации».

Правила агента: [code-gates](../rules/code-gates.mdc),
[границы слоёв](../rules/layer-boundaries.mdc),
[безопасный рефакторинг](../rules/refactor-safety.mdc),
[размер классов](../rules/class-size-limit.mdc),
[размещение документов](../rules/documentation-layout.mdc),
[schema-policy](schema-migrations-policy.md).

Планы зависимостей не заменяют ТЗ:
[pack-модель, §5b/6](library-packs-model-done.md),
[dependency graph](plan-dependency-graph.md),
[анализ 5b](library-packs-5b-analysis.md).

**Граница актуальности:** A0 выполнен 2026-10-14: packs §6, city §9.4,
connections §5.1.3 и другие перечисленные ТЗ синхронизированы с новым доменным
контрактом. Это завершение документационного шага, не реализация библиотек
или новых SQL/DTO полей. Исторические snippets помечены legacy; A1–B7
реализуют уже описанное целевое состояние.

Дата: 2026-10-14. Статус: A0–A7 и B1–B7 выполнены (B7 — 2026-10-15); план закрыт.
Основание: уточнения пользователя и [анализ](library-packs-5b-analysis.md).
Порядок исполнения обязателен после согласования. План не разрешает писать
код автоматически: текущий запрос — подготовка плана.

## 1. Цель и границы

Обеспечить отдельные библиотеки plot, building, structure с defaults параметров
в их POJO, согласованной доменной подготовкой и UID-ссылками; затем выполнить
5b: legacy world migration, effective catalog readers, снятие pointer-реестров.
Relief сохраняет свою библиотеку и входит в reader/registry cutover 5b.

Это два трека: A — необходимое разделение доменных библиотек; B — сам 5b.
A не считать скрытым подшагом удаления двух колонок. Новая архитектура должна
быть описана в доменных ТЗ до кода; текущие product docs содержат старые
предписания, которые нельзя молча проигнорировать.

Не входят: N+1 pack migration, новый cascade engine, manifest-defined
contextual fallback, full-world replace, DAG wiring, запуск backend, коммит.
POJO defaults полей не означают автоматический fallback любой битой ссылки.
Полноценный StructureTemplate.canonical_defaults() из 5c-1 — отдельный срез,
не вводится как побочный эффект разделения библиотек.

## 2. Целевая архитектура

### 2.1 Доменные записи и ссылки

Основание: [packs §0.2/1.1/2/3](../../docs/tz_template_library_packs.md),
[building §2/3.1/5](../../docs/tz_building_generator.md),
[city §3/9.2/9.4](../../docs/tz_city_generation.md).
Разделение plot/building и переход recipe keys оформляются в A0 как изменения ТЗ.

Предлагаемые окончательные контракты для утверждения этим планом:

- PlotTemplate — собственный библиотечный шаблон участка, kind plot_templates.
  Сохраняет параметры участка и содержит building templates главного и
  остальных зданий. Отдельная библиотека building не означает обязательную
  замену вложенных шаблонов голыми UID-ссылками — это предложение снято
  после уточнения пользователя. None главного здания означает участок без
  главного здания, а не запрос создать default building. Точная wire-форма
  использования библиотечного building внутри plot закреплена A0 §1: композиция тела сохраняется, ссылки адресуют members;
  само по себе уточнение не утверждает новый формат ссылки/override.
- BuildingTemplate — отдельный библиотечный шаблон здания,
  kind building_templates. Имеет system_name/local key, display_name,
  structure: UID и параметры BuildingBodyTemplate. Обязательная structure
  не заменяется выдуманной default-ссылкой. Defaults foundation/roof/porch
  принадлежат building POJO и проверяются библиотекой.
- StructureTemplate — kind structure_templates, существующая model A:
  system_name == template_uid; уровни/комнаты/связи/лестницы, их defaults
  и валидаторы остаются у structure-домена.
- Имена не identity. Ссылки на библиотечные записи адресуются template_uid;
  принадлежность паку и доступность вычисляет общая инфраструктура.
  Вложенный building template не объявляется ссылкой только из-за вложенности.
- Recipe plot_template и keys plot_counts/plot_priority — plot member UID.
  Сохраняются aliases, порядок required и приоритеты N/priority.
- Existing PlotLayoutTemplate/BuildingBodyTemplate сверяются с целевыми
  доменными моделями; их вложенность сама по себе не является legacy-ошибкой.
  BuildingTemplateOutline не приравнивается к BuildingBodyTemplate.
  Устаревшие формы/identity mapping описаны A0 §6; код converter проверяется в A6.

Новые POJO вводятся рядом со старыми, чтобы не ломать всех callers одним
изменением поля. Переход consumers выполняется отдельными шагами B3/B4.

### 2.2 Defaults и overrides

Основание: [JSON validation — Field policy](../../docs/tz_json_validation.md#field-policy-annotationpolicy),
[cascade §2/4](../../docs/tz_cascade_context.md),
[packs §0/0.3/5](../../docs/tz_template_library_packs.md).

Один доменный prepare_body выполняет wire policy, POJO defaults и валидацию.
StrictOnWire остаётся обязательным; missing DefaultWhenMissing получает
schema default; supplied invalid value не исправляется молча.
Null/0/false/[] различаются согласно политике поля. Для cascade-полей None
сохраняется как наследование; terminal default разрешает существующий extend.

Template member хранит подготовленное полное тело. Изменения конкретной
записи проходят copy/replace по общей policy. Не вводится field merge
одноимённых template members или overrides, встроенных в UID ref.
Cross-domain validation проверяет graph plot → building → structure,
доменные subject-поля и объявленные ограничения; не размазывается по routes.

Общий ref resolver отвечает за membership, body/dependency availability и
одну library diagnostic. Домен отвечает за пригодность и разрешённый fallback.
Не вводится специальный объект выбора builtin plot, default_plot_counts,
default_plot_priority или default-origin SQL columns.

### 2.3 Canonical records: согласованное решение

Действующий контракт: [packs §6](../../docs/tz_template_library_packs.md#6-canonical-attach-и-жизненный-цикл),
[JSON validation — WorldSlice/canonical engine](../../docs/tz_json_validation.md#worldslice-целевой-реестр).
Изменение правила builtin plots зафиксировано A0 §4; декларации паков реализуются в A5.

Пользователь согласовал 2026-10-14: стандартные plot/building templates —
члены объявленных дефолтных библиотек с обычными UID; defaults параметров
остаются в POJO. Объявить canonical plot/building records через доменные CanonicalLibrarySpec
и существующий global_fill_missing, с явными default pack declarations.
Источник канонических тел один: typed domain providers, использующие
мигрированные canonical templates и POJO-defaults. SQL — их библиотечное
хранение, а не независимый изменяемый набор дефолтов.

Это согласованно меняет старое правило packs §6 «builtin plots без
membership/SQL». A0 переносит принятое решение в ТЗ; повторного выбора
этой архитектуры не требуется. Не заменять её специальным default selector
или name lookup. Имена конкретных паков и UID declarations фиксируются
по центральному контракту, а не выводятся из FS autodiscovery.

Провайдеры описывают только объявленный canonical набор. FS user-паки не
становятся defaults. Default-паки read-only, attach только insert-missing;
правка — копия в mutable pack. Defaults полей POJO при этом не превращаются
в members сами по себе. Structure base spec/attach подключается штатным
контрактом; эту часть прежнего шага 6 план переносит в A5, что явно отражается
в dependency graph. Остальной scope шага 6 не объявляется выполненным.

### 2.4 Хранение и persist refs

Основание: [packs §3](../../docs/tz_template_library_packs.md#3-каталог-и-sql),
[building §7](../../docs/tz_building_generator.md#7-buildinglayout-возвращаемый-результат),
[storage — named_locations и DET-1](../../docs/project_data_storage_tz.md).
Согласовано пользователем: ссылки на шаблоны всегда записываются по UID.
Исправление существующего persist-пути описывается в этих разделах в A0.

Добавляется plot_templates body table. building_templates после cutover
хранит только BuildingTemplate; прежние plot/outline bodies читаются legacy
normalizer'ом и переводятся явной картой. Временно старые денормализованные
колонки building row сохраняются до финального cleanup, чтобы модель и
0001 оставались согласованы; их значения не используются как identity.
Domain rows не имеют owner_world_uid — owner только в pack catalog.

NamedLocation.system_template_uid, когда ссылка задана, всегда содержит UID
реального применённого библиотечного шаблона. system_name/local_uid/display_name
не записываются вместо UID. Отсутствие ссылки допускается только существующим
доменным контрактом; произвольный UID вместо отсутствующей ссылки не создаётся.
Уникальность обеспечивает PK template_uid общего member-каталога; разрешение
дополнительно проверяет kind, единственного owner, доступность миру и body.
Домен применённого шаблона определяется существующим caller-контрактом,
а не угадывается по имени или только system_location_type. Сохраняется цепочка
plot → building body → structure UID. Пользователь отдельно согласовал:
у созданного здания сохраняется UID фактически применённой structure.
Добавляется system_structure_template_uid: UID | None в NamedLocation,
SQL и bundle DTO. При генерации со structure поле заполняется её member UID;
None допустим для локаций без структуры либо legacy-записей, где источник
не удаётся восстановить по явной карте. Не вычислять его заново из
текущей редакции building template при обычном чтении. Это identity
применённого шаблона, не снимок/версия его тела. Bundle/remap переносят
обе UID-ссылки; другие типы локаций не переосмысливаются blanket-правилом.
Новая ссылка входит в объявленный usage/ref-контракт, чтобы проверки
использования structure учитывали созданные здания.

Старый building.system_template_uid, содержащий имя plot, конвертируется
только при однозначном соответствии с old plot/body map. Неоднозначность
на импорте — явная ошибка с path, не угадывание и не silent data loss.

### 2.5 Shared infrastructure и публичные швы

Основание: [packs §0.2/0.3/1.2/7](../../docs/tz_template_library_packs.md),
[JSON validation — архитектура/Scoped column write](../../docs/tz_json_validation.md),
[world bundle — Слои/handlers](../../docs/tz_world_bundle.md).

Повторно используются PackCatalogRepos, EffectiveCatalogLoader, RefResolver,
PackDomainAdapter, общий inspector/policy/planner/executor, archive codec,
scoped world writes и caller UOW. Новый домен добавляет adapter, не CRUD engine.

Предлагаемые typed application contracts (точные имена фиксируются в A1):

- TemplateEntry[T]: template_uid, pack_uid, body: T.
- WorldTemplateSnapshot: world_uid, plots/buildings/structures по UID;
  ordered candidates по UID; отдельный relief snapshot.
- Domain preparation: prepare_body(raw, local_uid, template_uid, world=None)
  → typed full body; refs объявлены один раз для validation/remap/usage.
- SnapshotLoader.load(world, ctx) → WorldTemplateSnapshot; async I/O здесь,
  sync generators получают готовые immutable source models.
- LegacyWorldInput → LegacyMigrationFacts → LegacyMigrationPlan:
  pack requests, source/final UID maps, migrated pins/refs, diagnostics,
  consumed legacy keys. Planning pure, чтение фактов и apply отдельны.

Classes application слоя ≤300 строк; деление по ответственности. Референсы
на модели типизированы, поля не определяются произвольным UUID grep в JSON.

## 3. Data flow и зависимости

Подготовка canonical source → общий ensure_canonical → load scoped membership
→ resolve refs → domain graph validation → typed snapshot → cascade context
→ sync planning/materialize → existing persist services.

Legacy import: raw parse/extract до normalize → facts → pure split/migration
plan → общий writer в world UOW → общий composed remap → entities → commit.
Нормализация world pure; обычное SQL hydrate не пишет паки. Никаких скрытых
commit, SQL I/O из POJO, library calls из generators или второго confirm.

Порядок serial: A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 →
B1 → B2 → B3 → B4 → B5 → B6 → B7.
Нет нового parallel execution/pool: текущий task этого не требует.
Промежуточные новые API не подключать production callers до готовности
их adapter/source/migration. Частичная схема допустима только как этап
разработки, не как законченный продуктовый контракт.

## 4. Правила исполнения и проверок

Каждый шаг — отдельный заход: выполнить → отчёт с diff/проверками → ожидать
«ок» перед следующим, согласно .cursor/rules/code-gates.mdc. Новый факт,
изменяющий состав шагов, сначала отражается в плане и сообщается пользователю.

Перед заменой API искать usages во всём репозитории, re-exports, fixtures,
frontend и engine nodes; ноды не менять. Если обнаружен обязательный node
consumer удаляемого API, cutover обозначить зависимостью Gate: DAG, не оставить
скрытый compatibility bypass и не объявлять B7 закрытым.

Команды ниже выполняются из backend/ рабочим Python interpreter. Базовая
проверка — python -m unittest; новые имена suites здесь являются обязательными
артефактами соответствующего шага. Failing baseline отделяется от новых ошибок.
Ранее .venv launcher сообщил ошибку пути и baseline не был подтверждён;
перед первым кодовым шагом проверить interpreter, не менять среду заодно.
SQL изменения только 0001_initial.sql + dataclass models вместе; отдельные
0002+ запрещены. Тесты используют temporary DB, рабочая БД не удаляется.

## 5. Трек A — библиотеки доменов

### A0 — синхронизировать доменные ТЗ

**Статус:** выполнен 2026-10-14. Новый нормативный
[контракт доменов](../../docs/tz_domain_template_libraries.md), существующие
ТЗ и граф зависимостей синхронизированы; код, SQL и fixtures не изменены.

**Цель:** закрепить целевой graph и снять противоречащие ему старые правила.
**ТЗ:** [packs §0.2/1.1/1.2/2–6](../../docs/tz_template_library_packs.md),
[building §2/3.1/5–7/11.1/11.6](../../docs/tz_building_generator.md),
[city §3/9.2/9.4/11.5](../../docs/tz_city_generation.md),
[connections §5.1.3](../../docs/tz_structure_connections.md),
[cascade §2/4](../../docs/tz_cascade_context.md),
[world bundle — Library-template секции/Порядок секций](../../docs/tz_world_bundle.md),
[storage — named_locations/DET-1](../../docs/project_data_storage_tz.md).
**Файлы:** перечисленные ТЗ; [JSON validation](../../docs/tz_json_validation.md)
для registry/wire projection изменений; [relief](../../docs/tz_terrain_relief.md)
для снятия pointer-пути; [library-packs-model](library-packs-model-done.md),
[plan-dependency-graph](plan-dependency-graph.md); этот план при выявленном уточнении.
**Контракт:** §2 этого плана; перенести согласованное решение canonical
plot/building в ТЗ, сохранить уточнение о собственном plot template с
building templates внутри и требование всегда записывать UID в template refs.
Перенос части шага 6 остаётся техническим предложением до фиксации. Зафиксировать examples
с UID и отсутствие специального default selector; другие location types
не переосмысливаются. Не реализовывать SQL/POJO в этом шаге.
**Проверка:** rg по default/builtin/plot_template/system_template_uid в ТЗ;
ручная сверка всех случаев §7 и отсутствие противоречащих обязательных норм.
**Done:** согласованный доменный текст покрывает каждый следующий шаг;
непринятые архитектурные предложения не маскируются отметкой «готово».

### A1 — target POJO и typed graph contracts

**Статус:** выполнен 2026-10-14. BuildingTemplate наследует defaults
BuildingBodyTemplate, PlotTemplate переиспользует PlotLayoutTemplate
без регистрации второго набора cascade channels. Добавлены typed
TemplateEntry/WorldTemplateSnapshot/ReliefTemplateSnapshot с read-only
UID indexes; public re-exports обновлены. StructureTemplate уже валидировал
model A/geometry, менять его defaults не потребовалось. 34 теста A1 +
structure/cascade baseline прошли; SQL, runtime readers и DAG не изменены.

**Цель:** ввести модели трёх доменов без переключения старых consumers.
**ТЗ:** [building §3.1/11.1/11.6](../../docs/tz_building_generator.md) и
[packs §0.2/2/5](../../docs/tz_template_library_packs.md) в редакции A0;
[JSON validation — Field policy](../../docs/tz_json_validation.md#field-policy-annotationpolicy),
[cascade §2/4](../../docs/tz_cascade_context.md).
**Файлы:** dataModel/locations/structure/building/{plotTemplate,buildingTemplate}.py
(новые), structureTemplate.py, re-exports; application templateContracts.py
(новый); tests/test_template_domain_models.py (новый).
**Контракт:** UID refs, TemplateEntry и snapshot types §2.1/2.5;
full validation, defaults из POJO, None inheritance. Legacy классы пока живы.
**Проверка:** python -m unittest tests.test_template_domain_models
 tests.test_structure_template tests.test_cascade_context_baseline.
Ожидается: missing defaults применены, invalid overrides отвергнуты,
null/0/false не потеряны, plot без здания не создаёт building.
**Done:** target models не импортируют DB/services, fixtures legacy ещё читаются.

### A2 — identity и SQL/repository primitives

**Статус:** выполнен 2026-10-14. Добавлены PLOT_TEMPLATES, plot_templates
в 0001, PlotTemplateRow и UID repository; schema startup включает модель.
UID/migration используют существующие library_uid/remapped_library_uid,
отдельной split/hash функции нет. TemplateRepositoryProviders вынесен
из Container с сохранением old methods/cache names. 33 storage/schema
теста и 43 теста A1/building registry/5a прошли; git diff --check прошёл.
Рабочая БД не изменена, SQL миграции 0002+ не создавались. Library adapters,
default declarations и runtime consumers — последующие шаги.

**Цель:** дать plot-домену storage и использовать центральный UID-контракт миграции.
**ТЗ:** [packs §2/3](../../docs/tz_template_library_packs.md) в редакции A0;
[storage — DET-1](../../docs/project_data_storage_tz.md),
[schema-policy](schema-migrations-policy.md),
[доменные библиотеки §1/6](../../docs/tz_domain_template_libraries.md).
Вложенность building не создаёт отдельный member или новый split UID.
**Файлы:** app/ids; db/migrations/0001_initial.sql; db/models/plotTemplate.py
(новый), buildingTemplate.py; iPlotTemplateRepository.py и sqlite implementation
(новые); repositories registration (core/templateRepositories.py, Container
и startup schema model list); tests/test_template_domain_storage.py.
При регистрации вынести провайдеры plot/building/structure в одну небольшую
зону, сохранив текущие Container methods и private cache names.
**Контракт:** LibraryKind.PLOT_TEMPLATES; member UID единственная identity;
plot row uid/name/display/data/source; name не UNIQUE. Mapping смены domain
kind использует центральный library/remap UID-контракт из DET-1; назначенный
UID не пересчитывается. Не вводить helper по пути вложенного body только
ради создания member. Старую table data
не UPDATE-мигрировать: локальная БД recreate, входы файлов конвертируются.
**Проверка:** python -m unittest tests.test_template_domain_storage
 tests.test_library_packs_schema. Свежая temp DB, mapper/schema соответствие,
одноимённые members, стабильность UID mapping и сохранность вложенных bodies.
**Done:** нет local uuid/hash; существующие SQL модели/0001 согласованы.

### A3 — pure preparation и ref declarations доменов

**Статус:** выполнен 2026-10-14. Добавлены target body preparation для
plot/building/structure и отдельный template_graph_issues над supplied scoped
catalog. Direct/nested refs используют одну декларацию structure field для
usage/remap. Shared sourceValidation выделяет проверку уже подготовленного
POJO без повторной реконструкции defaults; существующий validate_source
сохраняет прежний revalidation path. Inline bodies не создают members.
122 теста прошли (52 domain/model/structure/cascade, 7 refs, 29 write plan,
34 pack-remap/cascade/resource). Старые imports некоторых suites требуют
unittest discover; изменения тестовых imports не потребовались.
Writer factory и runtime consumers не переключены — это A4/B3.

**Цель:** библиотечная подготовка применяет defaults и проверяет graph.
**ТЗ:** [packs §0/0.2/1.2/5](../../docs/tz_template_library_packs.md) и
[building §3.1/10/11.6](../../docs/tz_building_generator.md) в редакции A0;
[JSON validation — Field policy/Normalize vs reject](../../docs/tz_json_validation.md),
[cascade §2/4](../../docs/tz_cascade_context.md).
**Файлы:** domainAdapters/{plot,building,structure,refFields}.py;
новые domain preparation/graphValidation helpers; sourceValidation.py
(переиспользование channel checks для подготовленных POJO);
tests/test_template_domain_preparation.py.
**Контракт:** plot содержит building bodies; явные библиотечные refs — UID,
building.structure → structure; новый plot→building UID wire не вводится.
полная typed preparation; local field validation и cross-domain graph
validation раздельны; usage/remap используют одну декларацию refs.
Structure model A сохранена. Доменные material/cascade constraints не
заменяются глобальным merger. Supplied invalid value остаётся ошибкой.
**Проверка:** python -m unittest tests.test_template_domain_preparation;
python -m unittest discover -s tests -p test_library_pack_refs.py.
Проверить valid graph, wrong kind, unavailable
ref, duplicate local names, None inheritance и cross-field invalid override.
**Done:** генераторы/routes не становятся владельцами этой подготовки.

### A4 — подключить домены к общему writer

**Статус:** выполнен 2026-10-14. PlotTemplateLibraryService и target building
body path делегируют общему writer; factory содержит по одному typed adapter
на plot/building/structure. Structure использует preparation A3; source reader
сохраняет полное подготовленное тело. Direct/nested structure refs участвуют
в общем remap/usage/retention, legacy world embedded refs временно сканирует
structure adapter. Новый modern member не создаёт legacy pointer.
Проверено 327 тестов: 49 domain model/preparation/storage/writer,
97 write suites, 181 pack/lifecycle/resolve/archive/schema. compileall и
git diff --check прошли. Реальная БД не менялась. Legacy outline conversion
и canonical plot/building attach остаются A6/A5 соответственно.

**Цель:** один write protocol обслуживает plot/building/structure members.
**ТЗ:** [packs §0.2/0.3/2/3](../../docs/tz_template_library_packs.md),
domain kinds/body contracts — в редакции A0;
[JSON validation — Scoped column write](../../docs/tz_json_validation.md#scoped-column-write-internal).
**Файлы:** PlotTemplateLibraryService (новый), building library typed body path,
domainAdapters/factory, write source/state reader wiring, core/container;
tests/test_template_domain_writer.py.
**Контракт:** один adapter на kind, body persistence в caller UOW; общий
inspector/planner/executor, copy/replace/token, immutable lineage. Legacy
body shape не принимается modern adapter как BuildingTemplate по эвристике.
**Проверка:** python -m unittest discover -s tests -p test_template_domain_writer.py;
 python -m unittest discover -s tests -p test_library_write_service.py;
 python -m unittest discover -s tests -p test_library_write_plan.py.
Ожидается полный graph remap, policy/stale без записи, rollback всей batch,
retention referenced plot/building/structure, одинаковые имена не сливаются.
**Done:** нет отдельного CRUD/policy движка для plot.

Уточнение A4 (2026-10-14): `building_templates.structure_type` становится
nullable в 0001 и dataclass. Target BuildingTemplate не имеет этого legacy
метаполя; writer сохраняет NULL, не выводит тип из structure UID. Удаление
колонки остаётся в B7. Writer fixtures участков переводятся на plot_templates.
Modern plot/building adapters не создают указателей в legacy registry и не
подставляют builtin plots при ошибке building ref. Lifecycle/resolve fixtures
обновляются под это разделение. Старый manifest-less building outline import
отклоняется без записи до явного converter A6; его тест пока проверяет отказ.

### A5 — canonical source/spec для стандартного graph

**Статус:** выполнен 2026-10-14. Объявлены три default-пака; typed source
проверяет 13 structure + 11 building + 11 plot и полный graph до SQL.
Три CanonicalLibrarySpec/global_fill_missing используют общий
SqlCanonicalPersistence и catalog insert-missing в одной attach UOW.
Public get/list и container effective catalog обеспечивают attach; internal
find и write preview не выполняют hydrate-write. Восстанавливаются тела,
membership, паки и dependency rows; существующие тела/source_file сохраняются,
конфликт ownership/membership не исправляется переездом записи.
Проверено 359 тестов: 61 template domain (включая 12 canonical), 181 pack,
97 write, 20 canonical engine. compileall и git diff --check прошли.
Реальная БД не менялась; legacy runtime consumers переходят на snapshot в B3.

**Цель:** стандартные записи доступны библиотекам по UID без runtime FS bypass.
**ТЗ:** [packs §6](../../docs/tz_template_library_packs.md#6-canonical-attach-и-жизненный-цикл)
и [building §6.1](../../docs/tz_building_generator.md#61-загрузка-в-глобальную-библиотеку)
в редакции A0; [JSON validation — WorldSlice, абзац «Единый движок canonical defaults»](../../docs/tz_json_validation.md#worldslice-целевой-реестр).
Явно заменяет часть [прежнего шага 6](library-packs-model-done.md).
**Файлы:** доменные source/spec modules, libraryPacks/defaults.py;
canonicalLibrary adapters/wiring по публичному contract;
fixtures/templates и structures_templates manifests по migration map;
tests/test_template_domain_canonical.py.
**Контракт:** единый typed источник каждого canonical набора, объявленные
pack identities и связи; insert-missing, no positive fullness cache,
повтор не заменяет body/source_file. Нет autodiscovery user FS как defaults.
Уточнение источников A5: актуальные fixture structure refs уже мигрированы;
повторная перезапись JSON/manifests не нужна. Явный список имён plot fixtures
задаёт source; standard building members получают main_building именно этих
объявленных plot identities. Plot сохраняет inline bodies, без выдуманной
plot→building UID ссылки. Паки engine.plots.base и engine.buildings.base
зависят от engine.structures.base. Три доменных CanonicalLibrarySpec работают
в общей main-connection UOW attach facade; body fill использует существующий
SqlCanonicalPersistence. Public catalog/get/list вызывают attach; внутренний
find writer остаётся read-only. Legacy runtime cutover остаётся B3.
**Проверка:** python -m unittest discover -s tests -p test_template_domain_canonical.py;
 python -m unittest discover -s tests -p test_library_packs_b3.py. Empty/partial DB, restore missing, existing
row неизменна, concurrent attach/rollback, user pack не импортирован.
**Done:** стандартный plot → building → structure разрешается по UID на
свежей temp DB без ручного импорта и без специального default объекта.

### A6 — split legacy shapes: pure converter

**Статус:** выполнен 2026-10-14. Добавлены LegacyDomainRecord/SplitResult,
pure split_legacy_domains и scoped resolver legacy refs. Plot остаётся
владельцем inline main/secondary bodies; новые building identities для них
не создаются. Destination/provenance заданы caller, исходные raw records
сохраняются отдельно от converted. Composed UID maps принимают сходящиеся
old/intermediate/final edges и отвергают циклы/конфликты. Name ambiguity
возвращает кандидатов и path; modern refs не проходят name compatibility.
Unrepresentable legacy поля и outline без structure дают явный отказ;
при ошибке batch не выдаёт частичный converted результат.
Проверено 145 тестов: 22 split (включая реальную SQLite trace без SQL),
61 остальных domain, 44 B3, 18 deterministic IDs. compileall и
git diff --check прошли. Converter не подключает старый importer автоматически:
transport и world migration используют его в следующих шагах A7/B1/B2.

**Цель:** сохранить старые plots/вложенные bodies без смешения доменов.
**ТЗ:** [packs §2/4 — Legacy fixtures/bundle](../../docs/tz_template_library_packs.md),
[building §3.1/5–6](../../docs/tz_building_generator.md) в редакции A0;
[storage — DET-1](../../docs/project_data_storage_tz.md).
**Файлы:** libraryPacks/legacyDomainSplit.py и contracts (новые);
uidMap.py/legacyPack.py; tests/test_template_domain_split.py.
**Контракт:** сохранять собственный plot template и содержащиеся building
templates. Обязательное извлечение каждого inline body в отдельный member
с заменой на UID не согласовано и не является целью converter. Конкретное
отображение legacy shapes определяется A0. Для изменяемых identities — полная composed
old/final UID map, path каждой embedded записи, provenance. Main/secondary
параметры сохранены. Outline без достаточной structure информации даёт
явную validation diagnostic; исходник не пропадает и не заменяется случайным.
Уточнение A6: caller явно задаёт source shape/kind, destination member и
scoped membership. Используется существующий pure legacy_member_row; новый
UID allocator/legacy CRUD не вводится. Unknown/unrepresentable legacy fields
дают path diagnostic; modern raw extensions сохраняются. Результат содержит
исходники, provenance, embedded paths без synthetic UID и resolution audit;
ошибка не выдаёт частичный runnable batch. HTTP/archive wiring — A7, world
migration extraction — B1/B2; старый importer не подключается в A6.
**Проверка:** python -m unittest discover -s tests -p test_template_domain_split.py.
Проверить main/secondary, одинаковые bodies под разными identities,
null/false/0, edited bodies, неоднозначность старых имён, повтор converter.
**Done:** pure conversion не пишет SQL и не выполняет instantiate.

### A7 — modern transport для всех доменов

**Статус:** выполнен 2026-10-14. UID archive root поддерживает plot_templates;
manifest/member HTTP DTO используют typed LibraryKind. Общие archiveSources,
archiveService и writer обслуживают все три target домена без второго CRUD.
Flat world compatibility проходит A6 до старых section handlers, сохраняет
inline main/secondary, объявляет dependencies на incoming structure packs,
композирует flat/packed части одного legacy pack с сохранением metadata.
Modern manifest kind остаётся authoritative; ошибочный building body с plot
shape не перенаправляется в другой домен. Validate-only не читает SQL и не
пишет; empty plot section возвращает succeeded=0. Проверены engine import
в пустую библиотеку без мира, world-owned graph round-trip, duplicate names,
cross-pack remap/deps/pins, 409 stale без записи и rollback после entity error.
Проверено 456 тестов: 100 template domain (17 новых archive/API), 181 pack,
97 write, 73 bundle, 5 fixture import. compileall и git diff --check прошли.
Реальная БД не менялась; legacy world registry/pointer migration — B1/B2.

**Цель:** archive/HTTP умеют переносить типизированный graph библиотек.
**ТЗ:** [packs §0.3/4.1/4.2](../../docs/tz_template_library_packs.md),
[world bundle — Library-template секции/handlers/Порядок секций](../../docs/tz_world_bundle.md),
[JSON import §10/11](../../docs/tz_json_import.md),
[JSON validation — Bundle row DTO](../../docs/tz_json_validation.md#bundle-row-dto-вариант-a-для-секций-вне-worlds).
Новые domain kinds/тела — по редакции A0; policy/409 остаётся packs §0.3.
**Файлы:** worldBundle library DTO/section allowlists; bundle/archive/libraryLayout;
libraryPacks/archiveSources/archiveService; api routes/DTO;
frontend существующий libraryWrite client только при изменении kind typing;
tests/test_template_domain_archive.py, test_template_domain_api.py.
**Контракт:** UID paths, typed kind, transport хранит одинаковые имена;
legacy формы идут только converter A6; routes тонкие, 409 decisions/token
общий. Engine import не требует мира, world import не публикует engine packs.
Уточнение A7: generic archiveSources/archiveService уже покрывают modern kinds
через adapter map; новый parallel transport не создаётся. Добавлены plot root
и section mapping, typed kind в DTO/member API. Flat compatibility преобразует
raw bodies A6 до section validation; target dependencies следуют объявленным
refs, modern manifests не используют shape inference. Self-contained legacy
вход получает membership структур из incoming packs; extraction старых world
pointers/registry и composed world refs остаётся B1/B2. В frontend kind union
не обнаружен, изменение JS client не требуется.
**Проверка:** python -m unittest discover -s tests -p test_template_domain_archive.py;
 python -m unittest discover -s tests -p test_template_domain_api.py;
 python -m unittest discover -s tests -p test_bundle_library_archive.py;
 python -m unittest discover -s tests -p test_library_write_api.py.
**Done:** round-trip полного graph и cross-domain remap сохраняет refs;
новый формат не попадает в старый ambiguous parse_body.

## 6. Трек B — собственно 5b

### B1 — pointer-set migration planner

**Статус:** выполнен 2026-10-14. Pure extraction сохраняет raw world/sections
до normalize. Planner получает detached полные pack/member/body snapshots,
явные UID aliases и legacy shapes; SQL, instantiate, writer и runtime callers
не вызывает. Default/owned pointers дают pins, engine user — полный instance,
существующий instance находится по provenance и сохраняет собственные bodies
без refresh, включая случай неполного instance. Unknown/foreign/wrong-kind
pointers диагностируются общим ReferenceIssueContext и не создают pin.
Нормализованный raw body сравнивается после composed remap. При различии
сохраняется полный legacy graph затронутого пака: overrides и остальные
существующие instance edits, без перезаписи исходных owned/default библиотек.
Source UID определяет identity legacy copy, поэтому duplicate local names
не сливаются. Authored bodies сохраняют inline main/secondary, null/false/0;
modern extensions сохраняются, unrepresentable legacy fields блокируют план
с исходниками. План содержит projections, pins, comparisons, composed UID map,
catalog и expansion/reference/dependency diagnostics; dependencies legacy
manifest выводятся из объявленных refs без подключения недоступных паков.
Повторные instance/legacy планы сохраняют identities. Legacy registry поля
сохранены; применение и удаление compatibility-данных остаются B2/B7.
Проверено 128 тестов: 36 B1, 22 A6 split, 8 A7 archive, 44 packs B3,
18 deterministic IDs. compileall и git diff --check прошли. Реальная БД
не менялась.

**Цель:** построить план legacy world migration до изменения runtime.
**ТЗ:** [packs §1.1/2/4 — Legacy fixtures/bundle / §5](../../docs/tz_template_library_packs.md)
в редакции A0. План работ: [library-packs-model, шаг 5b](library-packs-model-done.md);
это зависимость, не замена доменному ТЗ.
**Файлы:** legacyWorldInput.py/legacyWorldPlan.py, legacyWorldContracts.py,
legacyWorldBodies.py/legacyWorldProjection.py/legacyWorldRefs.py (новые);
legacyDomainContracts.py и bundle/legacyTemplateBodies.py — общий discriminator;
uidMap/legacyPack/bodyDiff; tests/test_library_packs_5b_migration.py.
**Контракт:** default/owned → pins; engine user → полный instance;
already-instance → provenance reuse без re-instantiate; authored/edited
body → legacy route, без silent loss. Нормализованные bodies сравниваются
после identity remap; совпадение local_uid не является запретом/слиянием.
**Проверка:** python -m unittest discover -s tests -p test_library_packs_5b_migration.py.
Все ветки классификации + split A6 + repeat + dangling pointer diagnosis.
**Done:** plan содержит все bodies/refs/pins и expansion diagnostics,
ни одна legacy колонка не удаляется до extraction.

### B2 — migration в world import UOW

**Статус:** выполнен 2026-10-14. Добавлен `legacyWorldMigration.py` —
применение `LegacyWorldMigrationPlan` через существующий 4d writer в
общей UOW world copy import; врезка в `worldCopyImport`/`worldLibraries`/
`worldBundleService` и container. Raw extraction до normalize, composed
split/world-copy remap и token continuation сохранены; SQL hydrate
не мигрирует, modern input идёт прежним 4d путём.
Проверено: `tests.test_library_packs_5b_import tests.test_library_packs_4d
tests.test_fixture_bundle_import` — 23 теста, OK.

**Цель:** применить план через существующий 4d writer атомарно.
**ТЗ:** [packs §0.3/4.1/4.2](../../docs/tz_template_library_packs.md),
[world bundle — Порядок секций/Domain errors](../../docs/tz_world_bundle.md),
[JSON validation — Import path/Normalize vs reject](../../docs/tz_json_validation.md).
Legacy split и его refs — по обновлённым в A0 domain contracts.
**Файлы:** legacyWorldMigration.py (новый), bundle/worldCopyImport/worldLibraries;
worldService/import entry points; tests/test_library_packs_5b_import.py.
**Контракт:** raw extraction до normalize, composed split/world-copy remap,
общая UOW и token continuation; SQL hydrate не мигрирует скрыто.
Fixture/world-row path использует application pipeline, pure prepare_import
не получает SQL I/O. Modern input проходит существующий 4d путь.
**Проверка:** python -m unittest tests.test_library_packs_5b_import
 tests.test_library_packs_4d tests.test_fixture_bundle_import.
Preview/stale/entity error rollback; immutable originals; repeat без duplicates.
**Done:** imported мир не зависит от registry для восстановления graph.

### B3 — world snapshot и packing identity

**Статус:** выполнен 2026-10-14. Добавлен
`application/worldData/templateSnapshotLoader.py`; выбор plots/buildings
переведён на scoped UID catalog: packing и placement идут через catalog
`template_uid`, legacy `system_name` lookups сняты из district/settlement
consumers (tokens/areaSlots/types, buildingCache/buildingDefaults,
requiredStructureResolve/structurePlacement). Для соблюдения class-size
tokens разделён на layoutPicks/subjects. StructureCatalog без global
list_all/FS source.
Проверено: `tests.test_library_packs_5b_snapshot
tests.test_required_structure_position tests.test_building_assembler
tests.test_settlement_topology` — 29 тестов, OK.

**Цель:** переключить выбор plots/buildings на scoped UID catalog.
**ТЗ:** [packs §1/1.1/3/5](../../docs/tz_template_library_packs.md),
[city §3/9.2/9.4](../../docs/tz_city_generation.md),
[connections §5.1.3 — Число токенов/Приоритет посадки](../../docs/tz_structure_connections.md)
в редакции A0; [JSON validation — Runtime path](../../docs/tz_json_validation.md#runtime-path-read).
**Файлы:** templateSnapshotLoader.py (новый); BuildingCatalog и target catalogs;
settlementOutdoorPackingJob; settlementAssembler buildingCache/buildingDefaults;
district planner tokens/areaSlots/requiredStructureResolve и typed token/slot DTO;
RequiredStructure/DistrictTemplateEntry/SettlementPayload/structurePlacement.
**Контракт:** loader → immutable snapshot, UID кандидаты/кэш/token/placement;
UID recipe refs/keys; legacy names только converter; N/priority порядок
сохранён; StructureCatalog не получает global list_all или прямой FS source.
**Проверка:** python -m unittest tests.test_library_packs_5b_snapshot
 tests.test_required_structure_position tests.test_building_assembler
 tests.test_settlement_topology. Новый snapshot suite обязателен.
**Done:** одноимённые plots не сливаются, pins не фильтр, чужой owner невидим;
ни один packing consumer не восстанавливает identity по имени.

### B4 — building materialize и persist template refs

**Цель:** провести разрешённый graph до генерации и сохранения локаций.
**ТЗ:** [building §3.1/7/11.1/11.6](../../docs/tz_building_generator.md),
[city §11.3/11.5](../../docs/tz_city_generation.md),
[storage — named_locations/DET-1](../../docs/project_data_storage_tz.md)
в редакции A0; [cascade §2/4/8.4](../../docs/tz_cascade_context.md),
[JSON validation — Bundle row DTO](../../docs/tz_json_validation.md#bundle-row-dto-вариант-a-для-секций-вне-worlds).
**Файлы:** areaAssembler/structureAreaAssembler и context helpers;
db/models/namedLocation.py + db/migrations/0001_initial.sql;
bundleNamedLocation DTO; доменные ref declarations/usage queries;
persist/remap services; tests/test_template_location_refs.py.
**Контракт:** system_template_uid хранит UID реально выбранного member;
assembler получает identity отдельно от читаемого имени тела. Существующие
structure refs остаются UID. Проверяются PK uniqueness, kind/owner/body и
world availability; одинаковые имена не влияют на разрешение.
Добавляется system_structure_template_uid — UID фактически применённого
StructureTemplate. SQL/model/DTO меняются вместе; import/export/world copy
и ref usage поддерживают новое поле. При повторной генерации поле отражает
вновь применённую structure; обычное чтение его не пересчитывает.
Прочие location types сохраняют семантику своих ссылок. Legacy ref
восстанавливается только по явному однозначному mapping, без догадок.
Context берёт подготовленные building параметры, None сохраняет cascade;
plot без building не создаёт NL. Central det-id использует принятую identity.
**Проверка:** python -m unittest tests.test_template_location_refs
 tests.test_structure_area_assembler tests.test_structure_orientation
 tests.test_bundle_named_location_wire tests.test_bundle_remap
 tests.test_cascade_context_baseline.
**Done:** persist и round-trip содержат реальные member UID, не имена;
две одноимённые копии различимы; проверка wrong-kind/unknown UID не обходится;
применённый structure UID переживает смену structure ref исходного building
template, export/import и remap; usage видит ссылку созданного здания;
default-параметры не дублируются в generators.

### B5 — relief reader/pick cutover

**Цель:** снять relief registry из загрузки тел и выбора кандидатов.
**ТЗ:** [packs §1/5/7](../../docs/tz_template_library_packs.md),
[relief — Библиотека и мир / Pick: мир → локация / объект / Conditions](../../docs/tz_terrain_relief.md)
(R19/R21/R31; pointer-формулировки снимаются в A0),
[logging — Инварианты/Маршрут](../../docs/tz_logging.md).
**Файлы:** loadReliefTemplatesForWorld; relief pick/templatePick/ribbonGrade;
mountains/reliefSidesStamp; detailedGradeDiscover/detailedGradeFrontPick;
pack bake/refine callers; tests/test_library_packs_5b_relief.py.
**Контракт:** entries_for_context над typed bodies, UID-order; pure pick;
explicit ref availability проверяет общий resolver, no-candidate/context
mismatch остаются самостоятельными domain errors. Не дублировать diagnostic.
**Проверка:** python -m unittest tests.test_library_packs_5b_relief
 tests.test_relief_mountain_stamp tests.test_relief_road_shoulder
 tests.test_relief_grade_system_t3c.
**Done:** random/round_robin/fixed сохраняют policy, expected order diff
документирован, другой шаблон вместо missing relief не подставляется.

### B6 — удалить pointer dual-write

**Цель:** membership становится единственным availability source.
**ТЗ:** [packs §0.2/0.3/1.2/2](../../docs/tz_template_library_packs.md)
в редакции A0 (полный graph refs и отсутствие pointer availability);
[JSON validation — Scoped column write](../../docs/tz_json_validation.md#scoped-column-write-internal).
**Файлы:** domainAdapters contract/mixins/building/relief/structure
(`_RegistryPointerMixin` целиком: `pointer_entry`/`_pointer_entry`,
`ensure_pointer`/`drop_pointer`/`_swap_pointer`, `_registry_with_entries`,
`_rebuild_registry_field`, мёртвый `remap_world_refs`; ensure/drop уходят
и из `PackDomainAdapter`); `memberOps.delete`/`teardown`;
`writeRetentionPlanner._world`; старые `_ensure_registry*` bind helpers
(`buildingTemplateLibraryService`, `reliefWorldImportService`); export/read
paths (`reliefSection.export_relief_template_bodies`,
`export_bodies_for_world`, `layouts_for_world`); `refFields`/`remapRefs`;
lifecycle regressions.
**Контракт:** удалить ensure/drop/swap pointer и entry builders; сохранить
remap pins/policies и refs всех трёх доменов, usage и retention.
Не pin-ить автоматически все записанные members.
Согласовано 2026-10-15:

- Export-пути flat bundle-секций читают membership: тела members паков
  с `owner_world_uid == world` (не world ∪ pins).
- `layouts_for_world` удаляется в этом шаге — pointer-reader без
  продакшен-callers (только тесты test_city_three_axes/test_e6_consumers).
- Stale pointer rows существующих миров не чистятся: колонка и её данные
  умирают в B7, промежуточной перезаписи при write нет (локальная БД
  recreate по schema-policy).
- `prepare_world_refs` сохраняет `remap_pins`, remap `relief_pick_policy`,
  sync `terrain_registry` и `_remap_structure_refs` — это
  pins/policies/refs, не pointer-write. `world_refs` structure-адаптера
  продолжает скан embedded layout строк до B7.
- Race/perk `_ensure_registry` вне scope — не pack-домены.

**Проверка:** python -m unittest discover -s tests -p "test_library_packs_4*.py";
python -m unittest discover -s tests -p "test_library_write_*.py".
Проверки старых suites обновить по поведению, не просто удалить assertions.
**Done:** copy/replace/delete/re-instantiate работают без registry writes;
export отдаёт тела world-owned members; ни один write-путь не трогает
registry колонки.
**Статус:** выполнен 2026-10-15. `_RegistryPointerMixin` и pointer-API
(`ensure_pointer`/`drop_pointer`/`remap_world_refs`/`_swap_pointer`,
entry builders) удалены из mixins/contract/relief; factory не берёт
`world_repository`; `memberOps`/`packOps` больше не читают мир для
teardown; `_ensure_registry`/`_ensure_registry_pointer` сняты с
import-путей; flat export обеих секций читает `members.list_for_world`;
`layouts_for_world` удалён. Тесты переведены на membership-assertions.

### B7 — schema/legacy API cleanup и итоговая приёмка — выполнен 2026-10-15

**Цель:** удалить старые registry columns и mixed domain body APIs.
**ТЗ:** [packs §3/4/5](../../docs/tz_template_library_packs.md),
[building §5–6](../../docs/tz_building_generator.md) в редакции A0;
[JSON validation — Wire projection/WorldSlice/Runtime path](../../docs/tz_json_validation.md),
[schema-policy](schema-migrations-policy.md).
**Файлы:** World + 0001; worldSlices/worldRow/re-exports;
registry/entry POJO; ambiguous building parse_body; legacy denorm columns;
domain repository member name lookup; bundle sections; fixtures/tests;
ТЗ и dependency graph. Compatibility parser остаётся отдельным модулем.
Export-пути flat секций уже читают membership после B6 — здесь решается
судьба самих section handlers (flat `relief_templates`/`building_templates`),
не переключение чтения.
**Контракт:** modern wire/schema только новые доменные тела и UID refs;
registry names разрешены лишь legacy input parser/tests/history.
Pack-level get_by_system_name остаётся для глобально уникальной pack identity.
**Проверка:** python -m unittest discover -s tests -p "test_library_packs_*.py";
python -m unittest discover -s tests -p "test_library_write_*.py";
python -m unittest tests.test_fixture_bundle_import tests.test_world_column_write
 tests.test_bundle_archive tests.test_bundle_library_archive
 tests.test_template_location_refs.
Source audit rg registry names / mixed POJO / by_system_name / global list_all
по backend/frontend/fixtures/scripts с явным compatibility allowlist.
**Done:** fresh schema и modern/legacy round-trip прошли; нет silent drops,
modern runtime не читает registries; обнаруженные node dependencies закрыты
по Gate: DAG. План помечен -done только после всех обязательных проверок.

## 7. Обязательная приёмочная матрица

- Пустая temp DB → canonical typed graph доступен по UID; повтор insert-missing
  не заменяет существующие тела; arbitrary FS user content не auto-default.
- POJO missing defaults, valid overrides, invalid overrides, null/0/false/[];
  cross-domain validation и None cascade; отдельный mandatory structure ref.
- Default member, authored world member, instance user pack, чужой owner;
  same local_uid в одном/разных packs; no-pin member участвует в candidates.
- Graph refs и recipe map keys remapped при world copy; pins по final UID.
- Legacy embedded plots/buildings, edited bodies, flat sections/manifests;
  исходные тела не теряются при split; idempotency по provenance.
- Missing dependency остаётся диагностируемой неполнотой, без auto-instance;
  invalid body import — ошибка; runtime ref failure — domain decision + одна запись.
- UID identity в cache/token/placement/persist; plot/building/structure refs
  не перепутаны и переживают export/import.
- Сохранённый structure UID — фактически применённый при генерации; изменение
  building template не переписывает его задним числом. World copy remap и
  проверка использования учитывают эту ссылку. Версионирование тела не вводится.
- Common policy preview/stale без записи; entity/body failure rollback всей UOW;
  pinned ∪ referenced удержание на всём graph, engine import без мира.

## 8. Что требуется утвердить и что уже определено

Уже определено пользователем: отдельные доменные библиотеки, POJO-defaults
параметров и согласованные overrides, UID библиотечных и persisted template refs, собственный
шаблон plot с building templates внутри. Стандартные plots/buildings —
canonical members объявленных default-библиотек с UID (принято 2026-10-14).
У созданного здания сохраняется фактически применённый structure UID;
поле system_structure_template_uid и его SQL/DTO/remap/usage входят в B4.
Специальный объект default и обязательная замена вложенного building
на голую UID-ссылку не являются согласованными требованиями.

A0 закрепил композицию plot/building/structure, domain kinds/storage mapping, canonical default members и persist refs. Canonical attach из прежнего шага 6 перенесён в A5 с явной записью в графе зависимостей. Конкретные typed model имена/pack declarations — реализация этого контракта, не новый выбор default архитектуры.

A0–A7 и B1–B7 выполнены; план закрыт. Не начинать A1 автоматически
по факту принятия одного архитектурного пункта. Если review изменит архитектурную часть, сначала обновить этот план
и ссылки, не подменять решение по ходу реализации.

