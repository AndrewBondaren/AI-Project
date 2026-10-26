---
name: "source-command-impl-city-t-4"
description: "Чинит CITY-T-4: смешанные ответственности планировщика поселения и хардкоды (zone preference, size rank, cache≠tokens, silent assembler). Новый чат: /impl-city-t-4."
---

# source-command-impl-city-t-4

Use this skill when the user asks to run the migrated source command `impl-city-t-4`.

## Command Template

# Имплементация: CITY-T-4 планировщик после 2d

Это **явная просьба писать код** (слои A–G плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала прочитай SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/city-t-4-planner-debt-done.md`](../plans/city-t-4-planner-debt-done.md) — **архитектура и порядок слоёв** (не отклоняться).
2. CITY-T-4 в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) (4a–4g).
3. [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) §1.2, §9.2–§9.3, §9.6 — продукт не менять.
4. Рецепт 2d уже в коде — не откатывать [settlement-specialization-districts](../plans/settlement-specialization-districts.md).
5. Правила: `layer-boundaries.mdc`, `assembler-hierarchy.mdc`, `dataModel-no-hardcode.mdc`, `json-validation-architecture.mdc`, `project-context.mdc` (DAG / backend / commit / schema = только `0001`).

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

После 2d политика generate живёт в **POJO**. Один resolve ролей. Один список имён зданий для cache и packing. Subjects на `DistrictSlot`, не повторный walk реестра в tokens.

## Жёсткие запреты

- Не reopen §1.2 (роли, subjects N+1, три прохода). Не класть `tavern_1` на город.
- Не CITY-T-2b (SQL library uid / настоящие интерьеры шахты). Не выдумывать levels вместо `_TOWN_HALL_LEVELS`.
- Не CITY-T-1b / 1e, не DAG `application/engine/nodes/`, не CITY-T-3.
- Не откатывать 2a: omit/`null` allowed = весь каталог. Civic flood → allow-list на `civic_center`.
- Не стартовать backend. Не коммитить, пока мастер не скажет.
- Не `0002_*.sql`. Колонка zone preference — правка `0001_initial.sql` + dataclass `World`.
- Генераторы **pure sync**. Не дублировать `Field(default=…)` литералом в assembler.
- Не ломать C22 packing (pass1→рамка→pass2). Меняется состав токенов и слотов, не пайплайн.

## Порядок (слои целиком)

Контракты — только §2 плана. После каждого слоя generate не должен стать пустым.

| Слой | Sub-ID | Что | Готово когда |
|---|---|---|---|
| **A** | 4e | `CellZone` + `WorldDistrictZonePreference`; `city_sizes.rank`; `PlacementConditionType`; `SYSTEM_TYPE_SETTLEMENT` | Unit POJO; assembler ещё можно не трогать |
| **B** | 4e | WorldSlice + `district_zone_preference(world)` + `0001` + `World` | merge канон⊕мир; validate_schema |
| **C** | 4a | Один resolve bind; `place_one_ref`; проходы 1 и 2 без copy-paste | specialization unit как сейчас |
| **D** | 4b, 4f max_per | Удалить `_select_by_refs`; `template_constraint_key`; max_per type+subtype; rank/zone из POJO | civic+culture оба стоят; unknown type не score 99 |
| **E** | 4c, 4d | `DistrictSlot.subject_tags`; один `pick_layout_names` → tokens **и** cache; coerce только Bind; skeleton dump | tokens без `settlement_specializations(world)`; civic без leftover mine/farm |
| **F** | 4f, 4g | Нет silent assembler `"building"`; allowed без warehouse/plaza-дыр; rng `BUILDINGS`; street default с POJO | unknown type → skip probe |
| **G** | — | Тесты плана §5; CITY-T-4* `partial`/`resolved` в tech debt; «код сейчас» city TZ | Чеклист path 2 мастеру (recreate DB после B) |

## Стиль

Минимум файлов. Узкие unit в `tests/test_city_three_axes.py` (или рядом), не `debug_settlement.py`. После слоя: что сделано / что осталось / что запустить мастеру.

## Старт

Прочитай план §1–4 и текущие `planner/defaults.py`, `districts.py`, `placement.py`, `tokens.py`, `buildingCache.py`, `DistrictSlot`, `SettlementSpecializationBind`, `city_skeleton_from_settlement`. Затем слой A.
