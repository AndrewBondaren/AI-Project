---
name: "source-command-plan-detailed-bake"
description: "Планировщик (не код): целевая архитектура хука C11 в detailed_bake (L2 затем materialize поверх). Новый чат: /plan-detailed-bake."
---

# source-command-plan-detailed-bake

Use this skill when the user asks to run the migrated source command `plan-detailed-bake`.

## Command Template

# План: detailed_bake как консьюмер L2 + C11

Это **план**, не имплементация. Код не писать. `no-code-until-asked` действует. Если режим не Plan — запросить switch в **Plan**.

Ты новый агент: **не** опирайся на чужую память сессии.

## Прочитать до плана

1. Контракт bake — [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) § **Контракт `full_bake` / `detailed_bake`** (locked 2026-09-06).
2. C11 / C23 — [`docs/tz_settlement_outdoor.md`](../../docs/tz_settlement_outdoor.md) (**C11**, **C14**, **C23**).
3. City фазы — [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) §5 фаза 1b–2, §8, §11.2–11.3.
4. Правило [`.cursor/rules/dag-generator-interface.mdc`](../rules/dag-generator-interface.mdc).
5. Правило [`.cursor/rules/architecture-first.mdc`](../rules/architecture-first.mdc) — в плане: целевое состояние, контракты, data flow, порядок слоёв.
6. Код как есть: `WorldSurfaceMaterializationOrchestrator` (`materialize_pack_full` → `plan_topology`; `materialize_pack_detailed` → только `_detailed.bake`), `PackDetailedBakeOrchestrator._bake_location_scope`, `SettlementOutdoorOrchestrator.materialize`, Container (`outdoor=` уже на surface orch).

Противоречие план↔ТЗ — остановиться и спросить мастера. Продуктовый контракт **не** переписывать «заодно».

## Цель плана

Сейчас два caller’а: `mode=detailed` = только L2; HTTP `generate-settlement` = C11. Город после detailed неиграбелен.

Target: `detailed_bake` `scope=location` **один job**:

1. Генерация terrain L2 (уже есть: refine / `FineChunkRunner`).
2. Если uid settlement-like — **тот же** `materialize` (C11) **поверх** этой земли. Не копипаст C22 в pack bake.

`scope=wilderness` — только шаг 1. `full_bake` не трогать (L0 → C23 уже в коде). HTTP generate-settlement остаётся другим caller того же C11.

## Жёсткие запреты (и в будущем impl)

- Не `application/engine/nodes/`. Не CITY-T-5b / lazy `generate_map_cells`. Не интерьеры.
- Не стартовать backend. Не коммитить из этого чата.
- Не класть `plan_district_slots` / assembler в `PackDetailedBakeOrchestrator`.
- Не менять алгоритм C22 и не reopen C23.
- Не 4-й bake mode. Не C11 на wilderness.
- Не `0002_*.sql`, пока план явно не потребует `0001` (хук скорее без schema).

Риски skip (не раздувать в этот план, но **назвать**): CITY-T-5a / **5g** — ложный skip packing после C23 без zst. Если хук зовёт `materialize(skip_if_initialized=True)`, 5g может noop’нуть шаг 2.

## Что сдать мастеру

Файл [`.cursor/plans/detailed-bake-c11.md`](../plans/detailed-bake-c11.md) (создать). Структура:

1. **Целевое состояние** — кто caller, кто интерфейс (`materialize`, refine), инварианты (порядок L2→C11; bake не знает `DistrictSlot`).
2. **Контракты** — сигнатура хука (где: `materialize_pack_detailed` vs конец `_bake_location_scope`); нужен ли outdoor на `PackDetailedBakeOrchestrator` или только surface facade; как прокинуть `world_uid`; skip_if_initialized; settlement-like = `named_location_uses_settlement_fine_footprint`.
3. **Data flow** — mermaid: HTTP bake → L2 persist → materialize → zst+SQL; ошибка C11 vs уже записанный L2.
4. **Порядок impl** — слои (wiring Container → один вызов → отчёт bake / 5m → тесты/smoke), не «сначала полгорода».
5. **Вне scope** — DAG, lazy, mill, world routes, C16 batch из detailed.
6. **Чеклист мастера** — что запустить после impl (HTTP detailed на city uid; zst+дети; wilderness без C11).

План важнее догадок. После файла — коротко в чат: где хук, какие риски 5g/ошибка после L2, готово ли согласовать impl.

## Старт

Прочитай контракт pack + `materialize_pack_detailed` + `materialize` (C11) + `named_location_uses_settlement_fine_footprint`. Затем пиши только план.
