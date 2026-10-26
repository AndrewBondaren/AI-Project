---
name: "source-command-impl-wilderness-8"
description: "Имплементирует шаг 8 плана wilderness-regions-mechanic: wilderness_region_entries[] в manifest при bake (WildernessRegionEntry: region_uid/entry_type/current_type/bbox/status/parent/state_fingerprint — индекс, не SoT), render outline, region-селектор (тонкий route). Входы закрыты: 0–7. Новый чат: /impl-wilderness-8."
---

# source-command-impl-wilderness-8

Use this skill when the user asks to run the migrated source command `impl-wilderness-8`.

## Command Template

# Имплементация: wilderness-8 — manifest region entries + debug

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):** шаги 0–7 сданы — регионы реально формируются при bake (declared/anchor/autoresolve + саблокации), `region_uid`/paint работают. Чего-то нет → стоп, доклад мастеру.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **8** (цель/ТЗ/файлы/проверка); §5 #8 (manifest entries — **индекс/debug/status**, не источник истины; resolved Specs derive-on-read из world data). Не отклоняться.
2. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § **`WildernessRegionEntry`** (поля, статусы), таблица manifest-полей (`wilderness_region_entries[]`), § Region state store (snapshot `current_type` — актуальное в `region_states`).
3. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc) — route только HTTP, логика в сервисах
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/dataModel/worldPack/meta/worldPackManifest.py` — manifest с `location_terrain_entries[]` / `settlement_structure_entries[]` и образцом `SettlementStructureEntry` (строка 43); сюда `wilderness_region_entries[]` + модель (или sibling `wildernessRegionEntry.py` по образцу).
- Pack writer — место, где manifest собирается при bake (region entries пишутся там же, где settlement/location entries).
- `backend/app/api/routes/map.py` — debug/read routes (`list_map_cells`, `export_map`…) — регион-селектор как тонкий route.
- `RegionShape.bbox()` (шаг 2) + `topology.canonicalize` — bbox seam-aware (канонизированные координаты).
- `state_fingerprint` — из collect/spec (шаг 3/5b), snapshot-поле.
- Статусы: `declared` | `anchor` | `autoresolved` | `sublocation` (+`parent_region_uid` для sublocation).

## Скоуп шага 8 — строго по плану §4

- `dm/worldPack/meta/wildernessRegionEntry.py` — `WildernessRegionEntry{region_uid, entry_type, current_type, bbox, status, parent_region_uid?, state_fingerprint?}` (поля/типы по ТЗ; `current_type` — snapshot на момент bake, актуальное — `region_states`).
- `worldPackManifest.py` += `wilderness_region_entries: list[WildernessRegionEntry]` (+ accessor по образцу `settlement_structure_entry()`).
- Pack writer: при bake — запись entries всех регионов (declared/anchor/autoresolve/sublocation + hydro-индекс из #6 если уже доступен — иначе без него, не изобретать); записи переписываются каждым bake, derive-on-read сохраняется SoT.
- Debug: render outline региона (существующий debug-render слой карты — где outlines уже рисуются, тонко) + регион-селектор endpoint в `map.py` (GET по uid → запись/статус/bbox; делегация в сервис, не логика в route).
- Юнит/smoke по приёмке ниже.

- **Не в шаге 8:** `region_states` (9a–c), overlay read (9c), `StateChangeConsumer` (10a), полный render-пайплайн регионов — только outline/селектор как debug-минимум.

## Жёсткие запреты

- Entries — **индекс/debug/status**, не SoT: ничто не читает resolved Specs из manifest; читатель entries не может восстановить «истинное» состояние (snapshot помечен).
- Никаких файлов-per-region в паке (ломает WP-12/13 — отвергнуто).
- Route — thin: validate → service/repo → DTO.
- Не трогать DAG-ноды, schema manifest только через модели (manifest — JSON в паке, не SQL), не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 8)

- `python -m compileall backend/app` — чисто.
- Bake world-test-002: manifest содержит `wilderness_region_entries[]` со всеми статусами; `region_uid` стабилен при повторном bake; саблокация несёт `parent_region_uid`.
- Region-селектор route отдаёт запись по uid (через сервис); render outline показывает контур.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь блокеры, найди точку pack writer'а, где пишутся `settlement_structure_entries` (туда же region entries), покажи карту файлов и endpoint-сигнатуру до первой правки.
