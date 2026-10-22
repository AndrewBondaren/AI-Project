---
name: "source-command-impl-geo-1-pc"
description: "Имплементирует подготовительный PC-блок плана geo-1-designed-water.md: PC-0…PC-12 — общий planning/cache/placement lifecycle до GEO-1 алгоритмов. Входы закрыты: план DESIGN_CLOSED. Новый чат: /impl-geo-1-pc."
---

# source-command-impl-geo-1-pc

Use this skill when the user asks to run the migrated source command `impl-geo-1-pc`.

## Command Template

# Имплементация: GEO-1 PC-блок — общий planning/cache до designed water

Это **явная просьба писать код** (шаги PC-0…PC-12 плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/geo-1-designed-water.md`](../plans/geo-1-designed-water.md) — **единственный SoT этой задачи**. Обязательные разделы: §5.4 (карта модулей), §6.15–6.22 (snapshot/lifecycle/planning/cache), §6.23 (A01–A08 аудит), §6.25–6.28 (typed contracts: envelopes/keys/fingerprints/revision/inputs), §6.29-M (финальные схемы GEO), §7 PC-блок (тела шагов). Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) — §Placement P1/P2/P3, §compose; L0/L2 consumer contracts.
3. [`docs/tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) — §generate-surface, persist cycle.
4. [`docs/tz_patch_system.md`](../../docs/tz_patch_system.md) и [`docs/tz_world_snapshot.md`](../../docs/tz_world_snapshot.md) — граница будущего cutover (G0-S), реализуется только caller-boundary seam, не platform service.
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход, шесть полей шага
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc) — cross-domain сборка вне generators
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc) — POJO единственный SoT
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc) — инвентаризация → строгий тип, RegistryKey/StrEnum
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema только `0001_initial.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)
   - [`.cursor/rules/bulk-sql.mdc`](../rules/bulk-sql.mdc) — массовые записи только через `db/bulkSql.py`

План важнее догадок. Противоречие план↔ТЗ↔код — остановиться и спросить мастера.

## Scope этой команды

**Только PC-0…PC-12.** GEO-1 code steps (G0-PT/G0-PE/G0-P и далее) — вне scope: они стартуют по **отдельной явной команде мастера** после приёмки PC-12. Нормативные G0/G0-A/G0-S — design-шаги; PC-0 замораживает относящиеся к PC contracts, GEO-часть может идти параллельно, но не является задачей этого чата.

Исполняемый порядок (§7, обязателен):
`PC-0 → PC-0U → PC-0G1 → PC-0G2 → PC-0I → PC-1 → PC-1C/PC-1T/PC-1R/PC-1H → PC-2…PC-6 → PC-6W → PC-7 → PC-8 → PC-8C → PC-9A → PC-9…PC-12`

Один PC-step = один атомарный срез: отчёт (сделано/файлы/проверки/остаток) → ждать «ок». **Правило мастера:** каждое сообщение после отчёта = следующий шаг, если нет фидбека.

## Что уже есть — не переписывать

- `application/cascade/contextResolver.extend(ctx, Link(...))`, `LocationContext` — общий каскад; водоспецифичный resolver не создавать.
- `application/worldData/generators/coordinates/{types,space}.py` — `GridX…FineDelta`, `Surface/FineGridCoord/Rect`, `CoordinateSpace` (переносятся PC-0G2).
- `climatePoleField.py::GridBBox` — переносится PC-0G1; `terrain/types.py` lazy re-export, `hydrology/types.py` type-check import — обновить на новый путь с сохранением symbol identity.
- `waterPlacementPass.py::run_water_placement_pass`, `PlacementBatch/Outcome` в `dataModel/placement/`, `resolved_water_placements` — baseline placement, расширяется по G-контрактам позже.
- `surfaceTerrainContext.py::prepare_surface_terrain_context` — после PC-9 становится compatibility-делегацией к `SurfacePlanningAssembler.prepare`; второй implementation запрещён.
- `packReadContext.py::FineTerrainDecodeCache` — pack/read cache, отдельный домен; planning cache его не заменяет.
- `app.ids.state_fingerprint` — reusable hash primitive; canonical payload/algorithm version фиксируются PC-0.

## Жёсткие запреты

- Нет water-specific placement resolver и нет `resolve_water_fraction()` — общий PolicyResolver/cascade.
- Нет локального WorldSnapshot/Patch-заменителя; generators не читают БД/Patch Store самостоятельно — только captured view/inputs.
- Cache не определяет currency мира; cached payloads — immutable domain plans dataModel, не live objects.
- `Any`, raw dict, unsafe cast, synthetic defaults, order-dependent foreign keys на cross-contract границах.
- Samplers/алгоритмы не получают live `World` — только frozen payloads (A03).
- Planning ≠ materialization: materializers не повторяют placement/policy/strategy/winner selection.
- Старые пути после переносов — только re-export/delegation, без второй реализации; wire values/symbol identity/half-open семантика сохраняются.
- `WorldBounds` не заменять на `GridBBox`; города/локационные caches не мигрировать.
- Не DAG-ноды, не backend-старт, не коммит, не `0002_*.sql`.
- Не активировать GEO-1 strategies/autoresolve — PC-8/PC-6W проверяют только baseline-equivalence.

## Приёмка (PC-12)

- Production wiring через composition root; все cases §6.22, generic type-negative checks (pyright valid/invalid configs).
- Coherent refs: один capture на compute run; mismatch revision/phase/space не merge'ится.
- Cache clear/restart/TTL/worker-count не меняют layout/identity/seed/geometry; HIT/MISS одинаковая диагностика.
- Edit → replan только затронутого набора; L0/L2 consumers читают planning results, не планируют заново.
- Single-flight/error propagation; baseline доменные регрессии зелёные; городские caches нетронуты.
- Done PC-12 = разрешение просить у мастера команду на основную GEO-1 реализацию.

## Старт

Прочитай план §6.25–6.29 и §7 PC-блок целиком, сверь §6.16/§6.17 facts с текущим кодом (могло уехать), затем PC-0: заморозь exact contracts, provider bindings, file map, revision sources, test suites/commands — в точные разделы ТЗ/плана по code-gates.
