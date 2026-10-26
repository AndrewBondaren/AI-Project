# Инструкция для анализа: идентичность шаблонов в глобальных библиотеках (`system_name` / `display_name` / uid) ✅ DONE

**Статус:** анализ выполнен, решение **принято разработчиком 2026-09-26** — см. §7 «Решение»: модель **А** (`system_name` = uuid шаблона, `display_name` — человеческое имя; одно глобальное множество, мир — подмножество через pointers). Промежуточная рекомендация V2 (scope по миру) **отозвана** — см. §7.3. §4.1 плана [`city-t-5n-5o-structure-split.md`](city-t-5n-5o-structure-split.md) синхронизирован. Блокер шагов 1/8/DDL снят. Кода не писать.

> **Роли.** «Мастер» в проекте — автор/консьюмер мира (грузит JSON, не разрабатывает). Решения по архитектуре принимает **разработчик**. Формулировка §1 «отклонена мастером» — историческая, см. §7.0.

## 1. Проблема

Глобальные библиотеки шаблонов (`building_templates`, `relief_templates`, будущая `structure_templates`) сегодня идентифицируют запись **именем**: `system_name TEXT UNIQUE`, `template_uid = uuid5(f"{table}|{system_name}")` — uid производный от имени и ничего не добавляет.

Следствие: два мира не могут иметь **разные** шаблоны с одним именем (`tavern_1` мира A ≠ `tavern_1` мира B). При импорте второй перезаписывает первый (later-wins) или падает на UNIQUE.

Первая идея — «`system_name` = uuid, `display_name` = человеческое имя» — **отклонена мастером**: в проекте `system_name`/`display_name` — единая пара по всем системам (`docs/tz_json_validation.md` §0 RegistryKey, `data-storage-pattern.mdc`). `system_name` — **читаемый** машинный ключ, по которому мастер ориентируется в JSON **без UI**: `main_building.structure: "tavern_1"` должно читаться человеком; `"3f9a2c…"` — нет.

## 2. Инварианты (не нарушать)

1. `system_name` остаётся человекочитаемым slug во **всех** библиотеках и registries; тип на wire — `RegistryKey[R]` (`backend/app/dataModel/registryKey.py`), JSON-строка.
2. Пара `system_name`/`display_name` — единая конвенция для каждой системы; не вводить третье поле «настоящий ключ», которое обесценит первые два, без явного обоснования.
3. Правило `template-pack-layout.mdc`: свой domain root на библиотеку, `stem файла == system_name`, имя папки == `pack_name`.
4. Schema-правки — только `0001_initial.sql` + sync `db/models/` (`project-context.mdc`); отдельные миграции запрещены.
5. Ничего не хардкодить параллельно POJO (`dataModel-no-hardcode.mdc`).

## 3. Что изучить (факты, а не догадки — с путями и строками)

### 3.1 Как ключ устроен сегодня

- `backend/app/dataModel/registryKey.py` — `RegistryKey[R]`; `docs/tz_json_validation.md` §0 — контракт N1-W ключа.
- `backend/app/db/migrations/0001_initial.sql` — все таблицы с `system_name UNIQUE` (стр. ~150, ~414, ~631, ~644 и др.): какие из них **глобальные библиотеки**, а какие world-scoped (есть `world_uid`).
- `*TemplateLibraryService` (buildings, relief): где вычисляется `template_uid` (`uuid5(...)`), что делает `upsert` при совпадении имени.
- `*FsImport` (relief-образец `reliefTemplateFsImport.py`): как `pack_name` (папка) участвует в идентичности — или **не участвует** (только `source_file`).
- `worlds.building_template_registry` / `worlds.relief_template_registry`: pointer — это `system_name` или `template_uid`? Что происходит при импорте bundle мира, чей шаблон по имени уже есть в библиотеке с другим телом (`bundle/*Section.py`).
- `fixtures/templates/*.json`, `fixtures/world_*.json`: как ссылаются друг на друга (участок → структура, район → `required_structures`, pin `plot_template`) — везде по `system_name`.

### 3.2 Кто и когда сталкивается с коллизией

Расписать сценарии и для каждого — что должно произойти:

| Сценарий | Сегодня | Ожидание |
|---|---|---|
| Мир A и мир B оба импортируют свою `tavern_1` с разными телами | ? | оба живут |
| Мир ссылается на `tavern_1`, а в библиотеке их две | ? | однозначный резолв |
| Engine stdlib `tavern_1` и world-pack `tavern_1` | ? | ? (override или две сущности) |
| Export bundle мира A → import в другую инсталляцию, где `tavern_1` уже есть | ? | без порчи чужого |
| Мастер правит JSON участка руками | — | видит понятное имя структуры |

### 3.3 Прецеденты в проекте

- Как решена та же задача для **world-scoped** registries (`WorldMaterialRegistry`, `WorldTerrainRegistry`, `WorldDistrictTemplateRegistry`): ключ уникален **в пределах мира**, глобальной таблицы нет. Применимо ли «уникальность в scope, а не глобально» к библиотекам.
- `template-pack-layout.mdc`: пакет (`pack_name`) как естественный namespace — `{pack}/{system_name}.json` уже уникален на FS. Почему в SQL этот namespace теряется.
- `docs/project_data_storage_tz.md`, `docs/tz_world_pack_storage*.md` — что сказано об идентичности глобальных библиотек и портируемости.

## 4. Варианты для оценки (минимум эти; можно добавить)

Для каждого: изменения в DDL / POJO / `RegistryKey` / FS-layout / refs в JSON / bundle / routes; что видит мастер в JSON; риск коллизии; миграция существующих строк.

| # | Вариант | Суть |
|---|---|---|
| V1 | **Scope по пакету** | Уникальность `(pack_name, system_name)`. Ref в JSON — `system_name`; резолв в контексте пакетов, подключённых к миру (`worlds.*_template_registry` хранит `pack/name` или пакеты целиком). Квалифицированная форма `pack/name` — только при неоднозначности |
| V2 | **Scope по миру** | Библиотека остаётся глобальной, но строка получает `owner_world_uid NULL` (NULL = engine stdlib). Уникальность `(owner_world_uid, system_name)`. Мир видит stdlib ⊕ своё; refs по `system_name`; коллизия только внутри одного мира |
| V3 | **Отдельный технический uid + читаемый `system_name` без UNIQUE** | `template_uid` = случайный uuid, `system_name` читаемый, не уникальный. Refs в JSON — по `system_name`, но резолв неоднозначен → нужен scope (сводится к V1/V2) либо refs по uid (нарушает инвариант 2) |
| V4 | **Оставить как есть** | Глобальная уникальность имени; коллизия — ошибка импорта с понятным сообщением; мастер переименовывает. Оценить честно: возможно, достаточно для текущей стадии продукта |

Для каждого варианта ответить: где живёт **scope** при резолве ссылки `main_building.structure` в `StructureCatalog` во время `generate-settlement` (есть `world_uid` → легко; нет → проблема).

## 5. Критерии решения

1. Мастер читает и правит JSON без UI — ссылки по понятным именам.
2. Два мира с одноимёнными разными шаблонами сосуществуют **или** осознанно принято V4 с обоснованием.
3. Одно правило идентичности для **всех** библиотек (buildings, relief, structures), не особый случай для структур.
4. Минимальный blast radius для среза 5n/5o: структуры делаются сразу по выбранному правилу; participки/relief — миграция отдельным пунктом §7 плана.
5. Bundle export/import не портит чужие шаблоны.

## 6. Deliverable

- Раздел **«Решение»** в этом файле: выбранный вариант, DDL `structure_templates` (поля, уникальные ключи), форма ref в JSON участка, правило резолва в `StructureCatalog`, что с `template_uid`, миграционный пункт для `building_templates`/`relief_templates`.
- Правка §4.1 плана `city-t-5n-5o-structure-split.md` («ключ структуры») и §1 (аннотации `system_name`/`structure`) под решение; §7 п.8 — синхронизировать.
- Вопросы мастеру — списком, только те, что нельзя закрыть из ТЗ/кода.

**Не делать:** код, миграции, правки fixtures; не менять `RegistryKey`; не предлагать uuid в `system_name`.

---

## 7. Решение

### 7.0 Принятая модель (решение разработчика, 2026-09-26)

Требование продукта, которое определило выбор: **мастер загружает свои шаблоны один раз и подключает их в несколько миров.** Значит библиотека — **одно глобальное множество**, библиотека мира — **подмножество** через pointers (`worlds.*_template_registry`), как в `tz_world_bundle.md:82-84`. Коллизии исключаются не scope'ом, а ключом:

- `system_name` = **уникальный uid шаблона** (uuid, строка). Дубль `system_name` с другим телом — критично → ошибка, не later-wins.
- `display_name` = человеческое имя. Дубли допустимы.

Инвариант §2 п.1 («`system_name` — читаемый slug») для **глобальных библиотек шаблонов** разработчиком **снят**; для world-scoped registries (`material_registry`, `district_template_registry`, …) остаётся. Инвариант п.2 (пара `system_name`/`display_name`, без третьего поля-ключа) — соблюдён: отдельного `template_uid` в POJO нет, `system_name` **и есть** uid.

### 7.1 Факты (проверено по коду)

| # | Факт | Где |
|---|---|---|
| F1 | Глобальные библиотеки с `system_name UNIQUE` **без** `world_uid`: `race_templates` (стр. 148), `perk_templates` (412), `building_templates` (629), `relief_templates` (642). Прочие `system_*`-ключи — JSON-колонки внутри `worlds` (world-scoped) | `0001_initial.sql` |
| F2 | `template_uid = uuid5(NAMESPACE_URL, "{table}\|{system_name}")` — производный от имени, PK | `buildingTemplateLibraryService.py:28`, `reliefTemplateLibraryService.py:28` |
| F3 | `upsert` = `INSERT OR REPLACE` по PK → одноимённое тело **молча затирается**, UNIQUE-ошибки нет | `db/repositories/sqlite/base.py:38-42` |
| F4 | `pack_name` (папка) в идентичности **не участвует** — только `source_file` label | `reliefTemplateFsImport.py:63-97, 100-112` |
| F5 | Pointer-реестры миров и `relief_pick_policy.default_template_uid` **уже** хранят uuid → world JSON уже оперирует uuid; модель А делает это консистентным (один uid везде вместо uuid5-от-имени) | `reliefTemplateRegistryEntry.py:16`, `buildingTemplateRegistryEntry.py:15`, `fixtures/world_test_gen_003.json:378-394` |
| F6 | Bundle import = `upsert_outline(source_file="bundle")` + pointer → перезапись чужого одноимённого тела | `reliefWorldImportService.py:61`, `buildingTemplateLibraryService.py:138` |
| F7 | Refs между шаблонами — по `system_name`: `RequiredStructure.plot_template: DrawingKey`, `plot_counts/plot_priority: dict[DrawingKey, int]`, `BuildingCatalog.by_system_name`; при модели А эти значения становятся uuid после миграции участков (§7.6) | `requiredStructure.py:31`, `districtTemplateEntry.py:54-60`, `buildingCatalog.py:24-41` |
| F8 | Прецедент «engine ⊕ world, later wins по имени»: `assemble_building_catalog`, `resolve_registry_list_world` | `planner/buildingDefaults.py:14-23`, `worldRow.py:258-266` |
| F9 | `world` доступен во всех точках сборки каталога → pointer-подмножество мира резолвится без доп. контекста | grep `assemble_building_catalog(` |
| F10 | `PRAGMA foreign_keys=ON` | `db/database.py:31,36` |
| F11 | `named_locations.system_template_uid` FK → `building_templates(template_uid)`, но area пишет туда `template.system_name` — при модели А (после §7.6) `system_name == template_uid`, расхождение исчезает само | `0001_initial.sql:704`, `structureAreaAssembler.py:385-396` |
| F12 | ТЗ `tz_building_generator.md` §5.1/§6.1: `uuid5(system_name)`, «замена = загрузить тот же `system_name`» → update in-place. `tz_world_bundle.md:82-84`: «один раз библиотека, в мире pointers» — модель А ей соответствует | docs |

### 7.2 Сценарии коллизии (§3.2)

| Сценарий | Сегодня | При модели А |
|---|---|---|
| Мир A и B загружают свою «таверну» с разными телами | B затирает A по имени (F3) | разные uuid → две сущности, обе живут; `display_name` может совпадать |
| Мир ссылается на «таверну», а их две | невозможно (UNIQUE по имени) | ref — uuid → однозначно |
| Engine stdlib и шаблон мастера с одним `display_name` | shadows по имени | две сущности; выбор — pointer мира |
| Export bundle A → import в другую инсталляцию, где uid уже есть | затирает (F6) | тот же uid = тот же шаблон (uuid глобально уникален по построению); тело совпало → no-op; тело **отличается** → конфликт, см. §7.4 «bundle» |
| Повторная загрузка того же файла (тот же uuid) | update in-place | update in-place (ТЗ §5.1) + WARNING, если тело изменилось |
| Мастер правит JSON участка руками | имена читаемы | ref — uuid; читаемость через `display_name`/`description` в файле, имя папки пака, `list` route (uid + display_name) — осознанная цена модели А |

### 7.3 Почему не V1/V2/V4

| Вариант | Причина отказа |
|---|---|
| **V2 scope по миру** (промежуточная рекомендация, отозвана) | Библиотека мира = «stdlib ⊕ своё», своё других миров не видно → мастер **не может** загрузить один раз и подключить в N миров. Противоречит требованию продукта |
| **V1 scope по пакету** | Даёт подмножество через паки, но две формы ключа в JSON (`name` / `pack/name`), binding паков в `worlds`, коллизии имён паков между инсталляциями. Больше сущностей ради того же результата |
| **V4 глобально уникальный читаемый slug + ошибка дубля** | Работает, но коллизии между авторами возможны и лечатся переименованием чужого контента при импорте bundle. Разработчик выбрал исключить их полностью — uuid |
| **V3** | = А. `template_uid` как отдельное поле не нужно — `system_name` и есть uid |

### 7.4 Решение — модель А для `structure_templates`

**POJO `StructureTemplate`:**
- `system_name: StrictOnWire[RegistryKey[StructureTemplate]]` — uuid-строка (canonical `8-4-4-4-12`, lower-case). Валидация формата — `field_validator` на POJO (`uuid.UUID(value)`), **не** в `RegistryKey`. Omit → 422: автор обязан задать uid до загрузки (файл должен знать свой stem).
- `display_name: StrictOnWire[str]` — человеческое имя, не уникально.
- `description: DefaultOnWire[str | None]` — рекомендуется автору заполнять (читаемость файла без UI).

**DDL:**

```sql
CREATE TABLE IF NOT EXISTS structure_templates (
    template_uid   TEXT PRIMARY KEY,          -- == StructureTemplate.system_name (uuid); НЕ uuid5 от имени
    display_name   TEXT NOT NULL,             -- не UNIQUE
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,             -- StructureTemplate.model_dump(mode="json") — полное тело
    source_file    TEXT                       -- "structures_templates/{pack}/{uid}.json" | "bundle" | NULL
);
```

- Отдельной колонки `system_name` нет: `template_uid` = `system_name` POJO. Имя колонки `template_uid` сохранено для единообразия с FK-холдерами (`named_locations.system_template_uid`, relief `template_uid`) и с будущей миграцией §7.6.
- Без `structure_type`, без `owner_world_uid`, без `pack_name`.
- `StructureTemplateRow`: `template_uid`, `display_name`, `version`, `data: dict`, `source_file`.

**Ref в JSON участка:** `main_building.structure: "<uuid>"` — `StrictOnWire[RegistryKey[StructureTemplate]]`.

**FS stdlib (`structures_templates/{pack}/{uid}.json`):** `stem == system_name` (uuid) — правило `template-pack-layout` соблюдено буквально; читаемость — имя папки пака + `display_name` внутри. Два файла с одним uuid в разных паках stdlib — **ошибка FS-импорта** второго файла с обоими путями (не может быть намеренным).

**Library service:**
- `StructureTemplateLibraryService.upsert(outline, *, source_file)`: `template_uid = outline.system_name`; **никакого** `uuid5`. Существующая строка с тем же uid → update in-place (ТЗ §5.1); если `data` отличается — `logger.warning` (замена тела). 
- `upsert_from_dict(raw, source_file, expected_stem)`: stem == system_name (как relief).
- `get_by_uid`, `list_all` (uid + display_name + structure_types для выбора), `delete` (RESTRICT, если на uid ссылается участок какого-либо мира — §7 п.6 плана, можно отложить).

**World pointer для структур — не нужен (вариант C сохраняется).** Структура достижима только через `PlotLayoutTemplate.main_building.structure`; подмножество мира задаётся pointers на **участки** (`building_template_registry`). Импорт участка в мир (bundle / world-route) валидирует, что `structure`-uid резолвится в глобальной библиотеке → иначе `ImportError` (паттерн материалов ТЗ §6.2).

**Правило резолва `StructureCatalog`** (sync snapshot, гидрирует caller — pattern `BuildingCatalog`):

```
StructureCatalog.build(fs_stdlib: list[StructureTemplate], rows: list[StructureTemplateRow])
    by_uid = {t.system_name: t for t in fs_stdlib}
    by_uid |= {r.template_uid: StructureTemplate(**r.data) for r in rows}   # SQL wins: FS-import пишет туда же; upload мог обновить
resolve(uid) -> StructureTemplate | None      # None → GenerationError 422 с display_name участка + uid структуры
```

Scope при резолве не нужен: ключ глобально уникален. `world` не участвует.

**Routes среза:** `GET /structure-templates` (list: uid, display_name, structure_types, version), `GET /structure-templates/{uid}`, `POST /structure-templates` (upsert тела — загрузка мастером в глобальную библиотеку), `POST /structure-templates/import` (FS path под domain root), `DELETE /structure-templates/{uid}` (RESTRICT — можно §7 п.6). World-route для структур **нет** (C). Уточнение к прежнему ответу Q2: при модели А глобальный `POST` **нужен** — это и есть «мастер загружает один раз»; заменить его нечем.

**Debug API `POST /worlds/{uid}/generate-structure`:** принимает JSON `StructureTemplate` **или** uid из каталога (как в плане §5).

**Bundle (§7 п.6 плана):** export — замыкание refs участков мира → тела структур по uid (все, включая stdlib: bundle самодостаточен, uid гарантирует отсутствие путаницы). Import — для каждого тела: uid отсутствует → insert; uid есть и `data` совпадает → no-op; uid есть и `data` отличается → **`ImportError` по умолчанию** (не портить шаблон, на который могут ссылаться другие миры инсталляции), `?replace=true` — update in-place + WARNING. Никакого later-wins.

### 7.5 `template_uid` — итог

Для структур: **одно поле**. В POJO — `system_name` (uuid), в SQL — колонка `template_uid` с тем же значением. Производного uuid5 нет. `RegistryKey[StructureTemplate]` остаётся типом ключа; формат uuid проверяет POJO.

### 7.6 Миграция `building_templates` / `relief_templates` (§7 п.8 плана)

Цель — то же правило: `system_name` = uuid = `template_uid`.

1. `0001_initial.sql`: обеим таблицам убрать колонку `system_name` (или оставить и держать `== template_uid` — **убрать**, чтобы не было двух источников); `template_uid` = uid из JSON. Sync `BuildingTemplateRow`/`ReliefTemplateRow`. Recreate БД.
2. `*LibraryService.upsert_outline`: удалить `building_template_uid()`/`relief_template_uid()` (uuid5); uid = `outline.system_name`; валидатор формата на `BuildingTemplateOutline`/`PlotLayoutTemplate`/`ReliefTemplate`.
3. Pointer-реестры `worlds.*_template_registry` — **без изменений по форме** (`system_template_uid` уже uuid); меняется только источник значения (uid автора, не uuid5). `relief_pick_policy.default_template_uid` — без изменений по форме.
4. Fixtures: `fixtures/templates/*.json` — `system_name` → uuid (сгенерировать один раз, зафиксировать); `_PACKING_STEMS` → uid-stems или, лучше, загрузчик по domain root (шаг 8 плана). `fixtures/world_test_gen_003.json`: uuid5-значения в `relief_template_registry`/`relief_pick_policy` → uid из файлов `relief_templates/smoke_003/*.json` (те же файлы получают uuid-stem).
5. Refs на участки в чертежах районов (`plot_template`, `plot_counts`, `plot_priority`, `DrawingKey`) → uuid; `WorldDistrictTemplateRegistry.canonical_defaults()` (`plot_template="town_hall"`, стр. 64) → uid town_hall из stdlib.
6. F11: `named_locations.system_template_uid` = `template.system_name` становится корректным FK автоматически.
7. Race/perk templates — то же правило при их миграции (`tz_world_bundle` WB-14).
8. Docs sync: `tz_building_generator.md` §5.1/§6.1 (убрать `uuid5(system_name)`), `tz_terrain_relief.md` R11, `tz_json_validation.md` §0 — оговорка: для глобальных библиотек `RegistryKey` несёт uuid.

### 7.7 Правки в `city-t-5n-5o-structure-split.md` (выполнено)

- §1 аннотации: `system_name` — uuid шаблона (`RegistryKey[StructureTemplate]`, формат проверяет POJO), `display_name` — человеческое, не уникально; `structure` — ref по uid.
- §4.1: блок «Решение» → модель А; таблица «ключ структуры» — из истории обратно в **принятое**; DDL из §7.4; routes включают глобальный `POST`.
- §7 п.8 → формулировка §7.6.

### 7.8 Закрытые вопросы

| # | Вопрос | Ответ разработчика |
|---|---|---|
| Q1 | Единое правило для всех `*_templates` | да |
| Q2 | Глобальный `POST /structure-templates` | при модели А — **нужен** (загрузка мастером в общую библиотеку); FS-import — для stdlib разработчика |
| Q3 | Pointer-реестры миров | остаются — это и есть «подмножество мира»; для структур реестр не нужен (достижимы через участки) |
| Q4 | Дубль uid внутри stdlib-паков | ошибка FS-импорта в движок (второй файл), не в мир |
| Q5 | Bundle | тела по uid, самодостаточный; конфликт тела при том же uid → `ImportError`, `replace=true` — явно |
| — | Модель ключа | **А**: `system_name` = uuid, `display_name` — имя |
