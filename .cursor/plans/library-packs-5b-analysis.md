# 5b — анализ исполнения после сверки доменных контрактов

Дата: 2026-10-13. Статус: анализ пересмотрен; код не изменён.
**A0 выполнен 2026-10-14:** нормативный
[контракт доменных библиотек](../../docs/tz_domain_template_libraries.md)
и существующие ТЗ синхронизированы. Исторические предложения анализа
не имеют приоритета над этим ТЗ/актуальным планом. Следующий шаг — A1;
кодовые A1–B7 не начаты.
Уточнения 2026-10-14 имеют приоритет над предложениями ниже: plot имеет
собственный шаблон с building templates внутри; обязательная замена вложенных
building bodies голыми UID-ссылками не согласована. Стандартные plot/building
templates согласованы как canonical members объявленных дефолтных библиотек
с обычными UID. Defaults параметров остаются в POJO. Старое правило ТЗ
о builtin plots вне SQL изменяется в A0 плана, без повторного выбора решения.
Дополнительно согласовано: template refs всегда записываются по UID реального
library member, никогда по system_name/local_uid. Существующая цепочка
plot → building body → structure UID сохраняется. Последующим решением
пользователь согласовал сохранение UID фактически применённой structure
у созданного здания: system_structure_template_uid с SQL/DTO/remap/usage
поддержкой добавляется в B4 плана. Это не snapshot редакции тела. Требуется
провести member identity до persist и проверять uniqueness/kind/owner/body/
world availability. Упоминания выбора новой семантики location refs ниже
не означают необходимость нового механизма ссылок.
План исполнения подготовлен 2026-10-14:
[domain-template-libraries-5b-implementation-done.md](domain-template-libraries-5b-implementation-done.md).
План — проект на согласование; архитектурные конкретизации перечислены
в его §8, первый шаг A0 меняет только доменные документы.
Этот текст заменяет предыдущую редакцию анализа, включая предложения
специального объекта default, default_plot_counts/priority и новых SQL-полей
происхождения. Эти предложения не входят в согласованный контракт.

## 1. Основание и результат

Приоритет имеет уточнение пользователя: каждый домен имеет свою библиотеку;
параметры используют POJO-defaults либо согласованные переопределения,
разрешение и проверка которых принадлежат доменной библиотеке.
Цепочка рассматривается полностью: plot → building → structure.

Источники: docs/tz_template_library_packs.md §0–7;
docs/tz_building_generator.md §3/5/6; docs/tz_city_generation.md §3/9;
docs/tz_structure_connections.md §5.1.3; docs/tz_cascade_context.md §2/4;
docs/tz_library_contextual_fallback.md; library-packs-model-done.md §5a/5b/6;
фактические POJO, libraries, adapters, readers и import pipeline.

Входы 5a и 4d/L-5 реализованы. Технические зависимости 5b закрыты.
Однако нынешняя доменная раскладка plot/building не соответствует полностью
уточнённой целевой архитектуре. Готовность инфраструктуры не означает,
что runtime cutover можно выполнять по прежнему анализу.

Нужно сначала зафиксировать отображение трёх доменов на библиотеки и их
взаимные refs, затем переключать читателей и удалять старые реестры.
Новый универсальный default-marker для этого не требуется автоматически.

## 2. Четыре независимых контракта

### 2.1 Идентичность и доступность библиотечного шаблона

Template member адресуется template_uid. Default-пак доступен по декларации
движка; user-пак движка — через явный world-owned instance; авторский member
мира — через world-owned пак. Чужие миры и engine user-паки без instance
в каталог генерации не входят. Pins маркируют использование, не доступность.
Имена могут повторяться и не создают override/слияние.

### 2.2 Defaults параметров внутри шаблона

POJO определяет тип, обязательность и значение при отсутствии параметра.
Библиотечная запись задаёт явные значения, переопределяющие допускаемые
политикой defaults. Библиотека применяет доменную нормализацию и проверяет
весь полученный объект, включая взаимозависимые поля и ссылки.

Это не universal dict merge. StrictOnWire требует значение; DefaultWhenMissing
допускает schema default только при отсутствии. Явный null, пустой список,
0 и false имеют собственную семантику поля и не заменяются через `or`.
Невалидное явное значение не исправляется молча дефолтом.
Template bodies после подготовки полные и валидные; runtime не объединяет
одноимённые members полями. Правка по UID проходит общий writer/replace.

### 2.3 Наследование контекста между уровнями

Для объявленных cascade-параметров действует LocationContext/extend:
источники и terminal default объявлены POJO, None продолжает наследование.
Доменная библиотека сохраняет такую семантику nullable полей. Она не должна
заранее подставлять concrete default вместо None и тем самым обрывать cascade.
Библиотека готовит source models; существующий cascade engine разрешает
контекст по объявленным связям. Второй resolver наследования не создаётся.

### 2.4 Неразрешимая ссылка и fallback

Неизвестный UID, недоступный owner, missing body/dependency — отдельный
контракт runtime resolve: диагностика + существующее доменное решение.
Исходный ref не переписывается, другой случайный member не выбирается.
У relief подстановка тела запрещена. Structures POJO fallback описан
отдельным срезом 5c-1, но фактически ещё не реализован.

Явный выбор доменного default упомянут в packs §5, однако конкретная wire-форма
определяется доменом. Из defaults параметров не следует требование вводить
объект {kind: default, drawing_key: ...}. Contextual manifest fallback
world → pack → POJO остаётся отложенным расширением.

## 3. Домены: цель и фактическая реализация

### Plot — шаблон участка

Ответственность: параметры участка, размещение main/secondary buildings,
барьер, footprint и доменные ограничения.
Текущий POJO: PlotLayoutTemplate. main_building и secondary_buildings —
вложенные BuildingBodyTemplate, не ссылки на самостоятельную building-запись.
Builtin plots загружаются worldBuildingLayoutDefaults.canonical_defaults()
из fixtures/templates; authored plots также лежат в world registry или SQL.

Библиотечное хранение называется building_templates, хотя в нём принимаются
plots. Отдельного LibraryKind для plots сейчас нет. Это несовпадение имён
и границ нужно явно устранить в целевом контракте; не переименовывать SQL
или вводить новый kind по догадке в середине 5b.

### Building — шаблон здания внутри участка

Ответственность: параметры здания, foundation/roof/porch, ссылка structure,
согласование этих параметров с участком и структурой.
Текущий BuildingBodyTemplate: structure обязателен; foundation_type=slab,
roof_type=gable, foundation_depth=1; материалы допускают None;
porch_has_roof=false. Это примеры фактических POJO-defaults параметров,
а не готовое default-тело здания без обязательной structure-ссылки.

Самостоятельного библиотечного member identity/service/adapter для этого
POJO сейчас нет. BuildingTemplateOutline, принимаемый building library,
не равен BuildingBodyTemplate: это другая модель с levels-диапазоном,
room slots и собственными полями. Использовать её как готовую библиотеку
building body без проверки нельзя.

Наличие вложенного body сегодня не отменяет требование библиотеки домена.
Но уточнение пользователя само по себе не определяет SQL-layout,
LibraryKind и точную форму plot → building ref. Эти технические контракты
нужно описать в подготовительном срезе, а не выдавать за уже реализованные.

### Structure — шаблон внутренней геометрии

Ответственность: уровни, комнаты, connections, staircases, entry points,
геометрические ограничения и defaults этих параметров.
Текущий StructureTemplateLibraryService/StructurePackAdapter работает с
structure_templates. Wire model A: StructureTemplate.system_name == member UID.
BuildingBodyTemplate.structure — обязательная UID-ссылка на этот домен.
Defaults отдельных полей уже есть; полноценного canonical_defaults()
валидного тела StructureTemplate и override resolve_fallback пока нет.
Default-пак structures/base и POJO-default тела — разные источники.

### Relief — параллельный домен, также затронутый 5b

Собственная library/adapter и ReliefTemplate POJO существуют. Default-паков
тел нет; smoke_003 остаётся engine user-паком. Context кандидатов берётся
из тела; выбор/условия и default скаляров не дают права подставить другое
тело при неразрешимой обязательной ссылке.

## 4. Проверенные разрывы кода

### Рекомендуемое целевое отображение для 5b-0a

Это конкретное архитектурное предложение для сверки, а не описание кода
или автоматически согласованное изменение SQL:

- Plot library хранит PlotTemplate, отдельный kind `plot_templates`.
  PlotTemplate задаёт параметры участка и building refs главного/
  дополнительных зданий. Существующие PlotLayoutTemplate тела переходят
  сюда по явной migration map, а не по переименованию UID на лету.
- Building library хранит BuildingTemplate, kind `building_templates`.
  BuildingTemplate содержит параметры building body и structure UID ref.
  Вложенные BuildingBodyTemplate из старых plots извлекаются в members
  с явной mapping старого plot UID + пути вложенного body → новый member UID.
  Формулу identity определять только в app.ids; одинаковые тела не сливать
  по совпадению имени/контента без объявленного правила идентичности.
- Structure library сохраняет StructureTemplate и `structure_templates`.
  BuildingTemplate.structure адресует member UID, model A сохраняется.
- Каждый домен переиспользует общую pack/member инфраструктуру,
  inspector/policy/writer и свой adapter. Три библиотеки не означают
  три независимо написанных CRUD/policy движка.
- Параметры POJO-defaults не превращаются автоматически в новые members.
  Canonical библиотечные записи и применение defaults полей различаются;
  текущие builtin источники проходят доменную подготовку без дублирования
  источника истины и без выдуманного пользовательского default selector.
- Локальные overrides на ref-поле не вводятся неявно. Начальная однозначная
  семантика: ссылка выбирает полную подготовленную запись; для её изменения
  редактируется/копируется member по общей policy. Наличие запроса на
  parameter overrides не разрешает sparse merge одноимённых template members.
- Старый BuildingTemplateOutline требует отдельного маршрута: он не содержит
  того же building body/обязательной structure refs. Конвертировать только
  когда исходник даёт достаточно данных, иначе явная validation diagnostic;
  не назначать случайную structure и не терять outline при silent skip.

Выделение этих library identities/ref-полей — самостоятельный подготовительный
architecture split. Его надо выполнить до runtime cutover, если принимается
именно такое хранение. Включение всего split в одну правку 5b нарушит
атомарность. 5b migration затем использует его типы, UID map и archive DTO.
Назначение NamedLocation template refs определяется для каждого домена;
существующее system_template_uid нельзя молча переосмыслить с plot на building.

1. BuildingTemplateLibraryService.parse_body выбирает PlotLayoutTemplate
   либо BuildingTemplateOutline по наличию plot-полей. Один storage-kind
   сейчас обслуживает разные формы, BuildingBodyTemplate отдельно не обслужен.
2. BuildingCatalog индексирует по system_name и silently later-wins.
   Требуется сохранять разные member UID, а не только исправить lookup.
3. BuildingLayoutCache и PackingToken также используют имена; UID должен
   пройти через candidates, cache, tokens, reservations, slots и placements.
4. StructureAreaAssembler._create_building записывает plot.system_name в
   NamedLocation.system_template_uid. При трёх доменах надо определить,
   UID какого шаблона означает это поле: plot, building или structure.
   Предыдущий вывод «просто записать plot UID» недостаточно обоснован.
5. derive_structure_context сейчас переносит BuildingBodyTemplate поля
   в StructureContext и читает model_fields defaults при отсутствии body.
   Новый библиотечный контракт не должен дублировать эти defaults литералами
   или превращать plot без main_building в автоматически созданное здание.
6. SettlementOutdoorPackingJob читает structure_library.list_all(). Это
   global bypass membership; scoped snapshot обязателен.
7. assemble_structure_catalog использует FS defaults; полный canonical
   attach и снятие этого пути остаются шагу 6, если scope явно не изменён.
8. Relief loaders/pickers читают WorldReliefTemplateRegistry и context
   pointer entry; нужны typed candidates из доступных bodies.
9. Registry mixin и domain adapters делают pointer dual-write, одновременно
   выполняя полезный remap pins/body refs/relief policies. Удаляется только
   pointer surface, а не весь lifecycle remap.
10. building registry хранит pointers и полные embedded plots. Удаление
    колонки до миграции этих тел потеряет данные.

## 5. Полный набор значимых случаев

- Библиотечный UID default-пака: resolve конкретного member, без instance.
- UID world-owned instance/authored member: resolve конкретного member мира.
- Engine user member без instance/чужой мир: недоступен, ссылка не attach.
- Автоматический pick: фильтры домена поверх всех доступных members,
  UID-порядок, pins не фильтр.
- Не задан необязательный параметр: его POJO default либо наследование,
  согласно field policy. Не создавать отсутствующее здание/структуру
  лишь потому, что у их отдельных параметров есть defaults.
- Явный override параметра: сохранить значение и валидировать итоговую
  модель; отличать отсутствующее значение от null/0/false/пустой коллекции.
- Не задан обязательный ref: импорт отвергает его, если домен не объявил
  допустимый default. Не изобретать глобальную подстановку.
- Broken ref runtime: один library diagnostic и доменный fallback/отказ;
  stored ref сохраняется. Broken body import: ошибка, без fallback.
- Missing pack dependency: допустимая диагностируемая неполнота согласно
  packs §3/4; runtime может отказать в использовании. Не автоинстанцировать.
- Нужно изменить default member: собственная копия и её UID, default pack
  read-only; одинаковое имя не означает замещение.
- Старый world file: явная compatibility-миграция pointers, bodies и refs.
- Встроенный POJO plot сейчас: обслуживается доменной библиотечной границей;
  его наличие не обосновывает отдельный публичный selector/synthetic member.
  Конкретный переход описывается после разделения plot/building контрактов.

## 6. Миграция 5b: что сохраняется

Raw legacy input извлекается до normalize_world. Обычное SQL чтение/hydrate
не запускает скрытую запись. WorldCopyImport остаётся общей UOW
world → libraries → entities с token continuation/rollback.
Используются uidMap/legacyPack и общий inspector/policy/planner/executor.

Pointers классифицируются по member owner/default status, не по имени
или source_file. Default/уже доступный owned member даёт pin без instance;
engine user source — полный instance и согласованный remap; существующий
instance сопоставляется по source_pack_uid/provenance, без re-instantiate.

Embedded authored plots и manifest-less bodies сохраняются как world-owned
данные по зафиксированному доменному mapping. Изменённые тела не затираются
instantiate исходника; равенство проверяется после нормализации/remap,
а конфликты существующей identity идут через общий writer.
Одинаковые local_uid допустимы: старое обоснование конфликта именами неверно.

Полная UID-карта строится до remap и валидации batch; переносит pins,
world refs и member body refs. Pins — пары (library_kind, template_uid).
Одинаковые UID pins дедуплицируются; context/imported_at не становятся
настройками доступности. Повтор не дублирует instances и тела.

Modern bundle по-прежнему переносит world-owned libraries целиком;
нельзя экспортировать fallback как будто это выбранный авторский member.
После cutover новые writes не создают pointers или автоматический pin
для каждого member.

## 7. Исполнимый порядок

### 5b-0a — согласованный доменный mapping

Цель: описать библиотеки plot/building/structure и refs между ними.
ТЗ: packs §0.2/1/2/5/6; building §3/5/6; уточнение пользователя.
Файлы: доменные ТЗ и library-packs-model; отдельный architecture plan,
если требуется выделение библиотеки building body из существующего хранения.
Контракт: какой POJO представляет member каждого домена, что вложено,
что адресуется UID, где применяются defaults/override validation;
назначение persisted template refs; перенос текущих builtins и authored data.
Проверка: схема цепочки и примеры проходят случаи §5 без потери одного домена.
Done: никакая текущая форма тела не выдаётся за библиотеку другого домена.
Не добавлять новую таблицу/kind/refs как неявную часть удаления registry.

### 5b-0b — синхронизация recipe refs и параметров

Цель: провести принятый UID-контракт через существующие selectors.
ТЗ: packs §1.1/1.2/5; city §3/9.4; connections §5.1.3; cascade §2/4.
Файлы: ТЗ, RequiredStructure/DistrictTemplateEntry/SettlementPayload,
описание snapshot и reference declarations.
Контракт: библиотечные plot_template и keys counts/priority — UID;
legacy name → UID только при однозначности. Сохранить required.count
→ district count → settlement count → 1, priority district → settlement
→ 0, explicit 0/false и domain-specific null/inheritance.
Проверка: коллизии имён, aliases, remap ключей и referenced retention.
Done: точная wire-модель следует доменному mapping, нет нового общего
объекта default, введённого только ради старых name-keyed consumers.

### 5b-1 — legacy input и pure migration plan

Цель: классификация без записи по полному доменному mapping.
ТЗ: packs §0/1.1/2/4 legacy.
Файлы: новые legacyWorldInput/Plan; uidMap/legacyPack/bodyDiff; tests.
Контракт: input/facts/plan раздельны, source/final UID не смешиваются.
Проверка: pointers default/user/owned/dangling, edited/identical bodies,
embedded plots/building data, provenance idempotency, immutable input.
Done: нет потери вложенных building параметров или structure refs.

### 5b-2 — интеграция import UOW

Цель: общий migration/writer без отдельного policy protocol.
ТЗ: packs §0.3/4.1–4.2.
Файлы: legacyWorldMigration, bundle/worldCopyImport/worldLibraries,
WorldService entry points, container wiring.
Контракт: extraction до normalize; atomic libraries + refs + entities;
современный bundle без legacy keys идёт существующим 4d путём.
Проверка: preview/stale/error без записей; повтор не дублирует; file/archive
и fixture path используют одну подготовку.
Done: registry keys не нужны для сохранения восстановленного мира.

### 5b-3 — snapshots и runtime consumers

Цель: scoped библиотеки всех участвующих доменов готовят typed source models.
ТЗ: packs §1/3/5/7; building/city; cascade §2/4; relief R19/R21/R31.
Файлы: library loaders, BuildingCatalog/StructureCatalog, settlement job,
cache/tokens/area slots/structure assembler, relief loaders/pickers.
Контракт: async scoped hydration → sync generation; UID identity сохраняется
до persist; defaults применяет владелец домена, cascade не дублируется.
Проверка: два мира, name duplicates, deterministic picks, body overrides,
null inheritance, отдельные 0/false, cross-domain validation и diagnostics.
Done: runtime не читает registries и global SQL list_all; missing defaults
нового домена не маскируются произвольными чужими шаблонами.
Если 5b-0 выявит отдельный architecture prerequisite, сначала выполнить
его по своему плану; не разрабатывать новую библиотеку незаметно в этом срезе.

### 5b-4 — снятие pointer writes

Цель: доступность только через membership, remap сохраняется.
ТЗ: packs §0.2/0.3/1.2/2.
Файлы: adapter contract/mixins/building/relief/structure/refFields/remapRefs,
memberOps/writeRetentionPlanner и старые service bind helpers.
Контракт: удалить ensure/drop/swap pointer; сохранить pins/policies/body refs,
расширить ref declarations по доменному mapping, retention pinned ∪ referenced.
Проверка: instantiate/copy/replace/delete/re-instantiate и token regressions.
Done: writer не обращается к старым двум колонкам.

### 5b-5 — schema cleanup и приёмка

Цель: убрать transitional хранение после миграции и cutover.
ТЗ: packs §3/4/5; schema-policy; JSON validation contracts.
Файлы: World + 0001_initial.sql, worldSlices/worldRow/re-exports,
registry/entry POJO, service exports, relief repository name lookup,
fixtures/tests и документация.
Контракт: modern wire без registry keys; compatibility boundary явно
allowlisted. LibraryPackRepository.get_by_system_name остаётся — это
уникальная identity пака, а не неоднозначный member name lookup.
Проверка: свежая test DB/schema, current/legacy round-trip, source audit,
fixture import, JSON validation, scoped writes и generation regressions.
Done: нет registry/dual-write в runtime, тела и refs сохранены.

## 8. Приёмка и ограничения

Обязательные сценарии: все случаи §5; разные имена/UID/owners не сливаются;
одинаковые имена не ломают cache/token/persist; defaults и явные overrides
согласованы на всём plot → building → structure пути; None не обрывает
cascade; explicit refs/default selection/runtime fallback не смешаны;
world copy переносит refs/keys/pins; lifecycle retention учитывает refs;
preview/stale/entity error откатывают мир и библиотеки целиком.

Регрессии из backend через рабочий Python runtime:

```powershell
python -m unittest tests.test_library_packs_5a tests.test_library_packs_4d
python -m unittest discover -s tests -p "test_library_packs_*.py"
python -m unittest discover -s tests -p "test_library_write_*.py"
python -m unittest tests.test_fixture_bundle_import tests.test_world_column_write
```

Новые migration/snapshot и доменные cases добавляются в соответствующих
срезах. Повторно тесты при этой сверке не запускались: код не изменялся.
Предыдущая попытка baseline не дала результата после предупреждения
Python launcher о c:\python314\python.exe; процесс был остановлен,
причина отсутствия последующего вывода не установлена.

Backend не запускать, не коммитить. SQL правится только в 0001 + модели;
новые incremental migrations не создаются, локальную БД пересоздаёт пользователь.
DAG wiring не трогать. Canonical attach 6/7, contextual fallback и N+1
pack-миграция не включаются автоматически.

## 9. Итог готовности

Согласованы: доменные библиотеки, defaults параметров в POJO, согласованные
библиотечные overrides, UID template refs, scoped availability, общий writer.
Отменено как необоснованное предложение: специальный builtin selector и
новые поля counts/provenance исключительно ради этого selector.

Реальный недостающий контракт: отображение plot/building/structure на
библиотечные записи и связи, включая судьбу смешанного building_templates
и вложенного BuildingBodyTemplate. Это архитектурная работа 5b-0a,
а не выбор пользователем между синтаксисами default.

Не объявлять весь 5b готовым к кодированию до этого mapping. Анализ сохраняет
проверенные migration/runtime задачи, но больше не закрепляет текущую
неполную реализацию как целевую архитектуру и не скрывает новый доменный
library-split под удалением двух полей.
