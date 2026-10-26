---
name: "source-command-impl-type-kind-str-fields"
description: "Имплементирует план type-kind-str-fields-debt: миграция *_type/*_kind полей контрактов с голого str на существующие enum/RegistryKey-алиасы (шаги 0–8) + отложенные дизайн-пункты (шаг 9 roof, dependent-key). Верифицированная карта типов — в плане. Новый чат: /impl-type-kind-str-fields."
---

# source-command-impl-type-kind-str-fields

Use this skill when the user asks to run the migrated source command `impl-type-kind-str-fields`.

## Command Template

# Имплементация: type-kind-str-fields — типизация `*_type`/`*_kind` контрактов

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код.

**Один шаг за заход** — спроси мастера, какой шаг выполняем (или следующий по «Порядку»), выполни, отчёт → «ок» → следующий. Не пакетировать несколько шагов.

## Прочитать до первой правки

1. [`.cursor/plans/type-kind-str-fields-debt.md`](../../../.cursor/plans/type-kind-str-fields-debt.md) — **единственный SoT**: карта «поле → целевой тип» верифицирована по коду (не гадай домены — они уже проверены); шаги 0–9 с Цель/ТЗ/Файлы/Контракт/Проверка/Done; секции «Scaffold-контексты» и «Dependent-key поля» — это части плана, не факультатив.
2. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc) и [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc) — если есть: доменные правила типизации
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — ключи из реестра/enum, не литералы
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔код — остановиться и спросить мастера.

## Инварианты трека (из плана)

- **Wire/DB не меняется** — только runtime-тип поля. SQL-модели (`db/models/*`) не трогаем; lookup-параметры функций (`entry_for`, `subtype_for`, `require`) не трогаем.
- Новый `XKey = RegistryKey[XRegistry]` — по образцу `TerrainKey`/`ConnectionTypeKey`/`TransitionTypeKey`; новый enum — только если верифицированного нет.
- Boundary-адаптер `str | Enum` с `.value`/`.wire_value` coerce — существующая конвенция (`chatService`, `_pole_kind_wire`, `streets.graph_level`).
- Historical wire/DB при чтении — snapshot-семантика (без live-membership), как WR-TD-1; unknown → reject только на write/parse.
- Тесты — `python -m unittest tests.<…>` из `backend/` + `compileall app`. Тесты на новое поведение — обязательны; на механическую правку типа — минимум round-trip существующих.

## Карта шагов → верифицированные типы

| Шаг | Что | Целевой тип |
|---|---|---|
| 0 | `test_contract_hygiene.py` — AST-скан `*_type`/`*_kind` на str + allowlist | gate роста карты; делать первым |
| 1 | `library_kind` | `LibraryKind` (enum есть) |
| 2 | `connection_type` контракт-поля | `ConnectionTypeKey` (alias есть) |
| 3 | `shape_type`/`staircase_type`/`room_type`/`default_shaft_size_type` | `ShapeType`/`StaircaseType`/`RoomTypeKey` (новый alias)/union size-enum |
| 4 | `foundation_type`/`resource_type` | новый `FoundationType` StrEnum + `ResourceTypeKey` (новый alias) |
| 5 | `pole_kind` | `PoleKind` (enum есть) |
| 6 | `locationsIndexWire.system_location_type` + литерал `"room"` в `structureGeneratorService.py:230` | `LocationTypeKey` (новый alias) |
| 7 | `node_type`/`graph_level` в `ResolvedConnectionNode` | `ConnectionNodeType`/`GraphLevel` (оба есть) |
| 8 | `task_type` | `TaskType` (enum есть; убрать дубль-coerce в `chatService`) |
| 9 | `roof_type` | **дизайн-диалог до кода**: форма контракта (`list[RoofType]` / union / разделить на type+fallbacks) — варианты в плане; блокер закрытия плана |

## Вне скоупа шагов 0–8 — не делать «заодно»

- **Scaffold-контексты** (`VastHullContext`, `ResourceExtractionContext`, `RuinsContext`): enum НЕ вводить до producer. При появлении кода, создающего контексты: `hull_type`/`extraction_type`/`ruin_style` → enum по литералам docstring; `orientation` → `Facing`; `base_structure_type` → str с валидацией `in BUILDING_ASSEMBLER_REGISTRY.all()` (engine-registry, не N+1; helper рядом с `AssemblerRegistry`, литеральных списков ключей — нет).
- **Dependent-key** (`system_location_subtype`, частично `default_shaft_size_type`): отдельный дизайн-пункт parent→namespace; поля остаются `str` до дизайна. Карта subtype-пространств — в плане.
- `grid_kind` — defer до второго producer (сейчас только `world_map_light`).
- `db/models`, `params` lookup-границ, `MaskDomainId`.

## Жёсткие запреты

- Не менять wire/DB-представление ни в одном шаге (round-trip тест обязан это доказать).
- Не вводить enum с выдуманными членами — значения только из кода/ТЗ.
- Не типизировать scaffold-поля enum до появления producer.
- Не трогать DAG-ноды, не стартовать backend, не коммитить.
- Не «починить заодно» другие находки из инвентаризации — каждая = свой шаг.
- Allowlist hygiene-теста (шаг 0) — только уменьшается; легитимный str → allowlist со ссылкой на ТЗ, не молчаливый обход.

## Приёмка (на шаг)

- `python -m compileall backend/app` чисто; профильные unittest шага — зелёные.
- Поле typed по карте; unknown value на write/parse → reject; чтение исторических данных — snapshot-семантика.
- Шаг 0 дополнительно: скан без runtime-import, allowlist = карта плана, stale-запись → fail.
- Отчёт: что изменено, чем проверено, allowlist-тронут ли. Пометка выполнения в плане — после «ок» мастера.

## Старт

Прочитай план целиком + `test_contract_hygiene` (если есть — статус шага 0), уточни у мастера шаг (дефолт — следующий по «Порядку»: 0 → 6 → 1 → 2 → 3 → 5 → 7 → 8 → 4 → 9), покажи целевые файлы и контракт до первой правки.
