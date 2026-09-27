---
name: "source-command-impl-settlement-specialization"
description: "Имплементирует CITY-T-2d §1.2: специализация на шаблоне поселения, district_subtype, приоритет районов город → роли → морфология. Новый чат: /impl-settlement-specialization."
---

# source-command-impl-settlement-specialization

Use this skill when the user asks to run the migrated source command `impl-settlement-specialization`.

## Command Template

# Имплементация: специализация поселения и районы

Это **явная просьба писать код** (слои A–F плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала прочитай SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/settlement-specialization-districts.md`](../plans/settlement-specialization-districts.md) — **архитектура и порядок слоёв** (не отклоняться).
2. [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) **§1.1–§1.2**, §4.1, §9.2, §9.6.
3. CITY-T-2d в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
4. Три оси уже в коде — не откатывать A–F плана `city-three-axes-transition`.
5. Правила: `layer-boundaries.mdc`, `assembler-hierarchy.mdc`, `dataModel-no-hardcode.mdc`, `json-validation-architecture.mdc`, `project-context.mdc` (DAG / backend / commit / schema = только `0001`).

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

Шаблон **этого** поселения задаёт районы. Первичны `typical_districts` на городе, вторичны районы `settlement_specialization_registry` по `system_settlement_specializations`, морфология `city`/`village` — добивка пустых слотов.

Роль ≠ морфология: не писать `extract` в `system_location_subtype` поселения. Не класть `tavern_1` на город.

## Жёсткие запреты

- Не трогать `application/engine/nodes/`. Не чинить CITY-T-1b / CITY-T-3.
- Не стартовать backend. Не коммитить, пока мастер не скажет.
- Не `0002_*.sql`. Колонки — только правка `0001_initial.sql` + dataclass.
- Генераторы **pure sync**. Реестр ролей — POJO + `worldRow`, не литерал в assembler.
- Не ломать C22 packing. Меняется **какие слоты/типы**, не пайплайн pass1→рамка→pass2.
- Не фильтровать mine/farm по материалу/ресурсу (нет в плане).
- Не закрывать без path-2 чеклиста; агент сервер не поднимает.

## Порядок (слои целиком)

| Слой | Что | Готово когда |
|---|---|---|
| **A** | dataModel: ref, registry, `district_subtype`, канон чертежей, stub buildings, skeleton поля, `structure_type` town_hall/tavern | Unit POJO; assembler не трогать |
| **B** | WorldSlice + `settlement_specializations(world)` + BundleNamedLocation | Import не 422 |
| **C** | `0001` + `World` + `NamedLocation` + skeleton copy | validate_schema |
| **D** | `plan_district_slots` три прохода + zone agricultural + pin + union required | Unit path 3 |
| **E** | extract: NL subtype = `district_subtype` | outdoor extract тесты |
| **F** | Тесты проходов + чеклист path 2 мастеру | |

Контракты — только §2 плана. `village` size ≠ subtype.

## Стиль

Минимум файлов. Узкие unit. После слоя: что сделано / что осталось / что запустить мастеру (recreate DB после C).

## Старт

Прочитай план §1–5 и текущие `SettlementSkeleton`, `plan_district_slots`, `worldDistrictTemplateRegistry`, `settlementOutdoorExtract`, `worldSlices.py`. Затем слой A.
