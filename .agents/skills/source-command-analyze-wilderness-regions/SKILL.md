---
name: "source-command-analyze-wilderness-regions"
description: "Анализирует план wilderness-regions-mechanic и связанные ТЗ на консистентность, полноту и противоречия с кодом. Не пишет код. Новый чат: /analyze-wilderness-regions."
---

# source-command-analyze-wilderness-regions

Use this skill when the user asks to run the migrated source command `analyze-wilderness-regions`.

## Command Template

# Анализ: план wilderness regions + ТЗ

Это **аналитическая задача — код не писать и не править**. Только чтение,
сверка, отчёт. Правило no-code-until-asked действует полностью.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT,
потом код, потом выводы.

## Прочитать до первого вывода

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../plans/wilderness-regions-mechanic.md) —
   **главный объект анализа**: §0 (топология — контракт-зависимость),
   §1 диагноз, целевая архитектура (домены/классы/консьюмеры/логирование),
   §4 delivery plan (10 шагов), §5 решённые вопросы #1–#11.
2. [`.cursor/plans/surface-topology.md`](../plans/surface-topology.md) —
   смежный план: контракт `WorldTopology`, 5 решений, порядок подготовки.
3. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) —
   § «Регионы покрытия (wilderness regions)» (новый раздел, целевой
   контракт), § MaskDomain materialize, § Plugin map, § Домены
   terrain_masks, § Placement priority.
4. [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) —
   § `WildernessRegionEntry`, § «Region state — patch-слой», § Patch
   Store (WP-20), § manifest.
5. [`docs/tz_runtime_world_edit_policy.md`](../../docs/tz_runtime_world_edit_policy.md) —
   обязательная основа: один resolver, два режима, WarningError без
   defaults.
6. Правила (нарушение планом = находка):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — гейты, атомарность
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)
   - [`.cursor/rules/bulk-sql.mdc`](../rules/bulk-sql.mdc)

## Что проверить (checklist)

### A. План ↔ ТЗ консистентность

- Каждое решение §5 (#1–#11) отражено в разделе «Регионы покрытия»
  tz_map_light_bake или в region-секциях tz_world_pack_storage. Потерянные
  решения = находка.
- Каждый шаг §4 ссылается на раздел ТЗ, который **реально существует**
  после ТЗ sync (⛔-маркеры должны быть сняты фактом, а не обещанием).
- Имена идентичны везде: `declared_regions`, `entry_type`,
  `current_type`, `RegionShape`, `edge_noise`, `wilderness_region_entries`,
  `RegionState`, `state_fingerprint`, `merge_rank`, `eligibility`,
  `inertia`, `LANDCOVER`, `elevation_plain`. Расхождение имён
  wire/план/ТЗ = находка.

### B. План ↔ код (верификация точек интеграции)

Проверить существование и сигнатуры — план опирается на них:

- `app/ids`: `entity_uid`, `seed_root`, `seed_rng`, `seeded_u01`,
  `seeded_index`, `bake_seed`, `UidKind` (REGION ещё нет — новый член).
- `masks/`: `run_mask_domain`, `MaskDomainMaterializer` protocol,
  `apply_terrain_footprint`, `may_paint_terrain`, `terrain_merge_rank`,
  `masks.merge_rank_order`, `PRESERVE_HYDROLOGY_ROLES`.
- `terrainBatchOrchestrator.build_tile_surface_state`: порядок
  upsample → place_hills → merge_hydro_hard_corridor (точка правки L2).
- `jsonValidation/resolve.py`: `ResolveContext.validate_only`,
  `log_issues`/`report_issues`/`reject_unresolved`, `FieldPathError`.
- Гидрология: `HydrologyGeneratorService.apply` порядок скоупов,
  `generate_lakes` (shoreline→interior), `HydrologyCellRole`.
- `worldPackManifest` — место для `wilderness_region_entries`;
  patch-слой (WP-20) — механизм для `RegionState`.

### C. Внутренняя непротиворечивость плана

- Один `CoverageResolver` на autoresolve и state-change — не два.
- Тип (`entry_type`/`current_type`)/геометрия не в uid — проверить, что
  нигде в плане/ТЗ не просочилось обратное.
- `plains` = только покрытие; `elevation_plain` = факт elevation —
  нигде не смешано.
- Автор = «мастер» (world data), архитектурные решения = «разработчик»
  — терминология не перепутана.
- Seed/claim/stab-поля не зависят от набора baked-тайлов.

### D. Дыры и риски

- Что в §4 не покрыто шагами (например: миграция `FORESTS`/`PLAINS` →
  `LANDCOVER`, cutover `default_*` полей, `resolveForestPlains`).
- Заглушки без комментария-обязательства (`flora`, `elapsed_ticks`).
- Зависимости вне плана (surface-topology, LOD/время) — честно ли
  план деградирует без них (planar-режим, tick-параметр).
- Классы >300 строк по `class-size-limit` при предполагаемой
  декомпозиции — где границы разбиения.

### E. Гейты и процесс

- Каждый шаг §4 атомарен (один слой/контракт), имеет проверку и Done.
- Никакой шаг не требует кода до разрешения мастера.

## Формат отчёта

```markdown
# Анализ wilderness-regions-mechanic — {дата}

## Вердикт
{готов к имплементации / есть блокеры / частично}

## Находки
| # | Категория (A–E) | Сeverity (blocker/major/minor) | Что | Где |
|---|---|---|---|---|

## Подтверждённые факты
{что проверено и сошлось — точки в коде, решения, имена}

## Вопросы разработчику
{что нельзя решить без уточнения}
```

## Границы

- Код не править, ТЗ не править, план не править — **только отчёт**.
- Противоречие план↔ТЗ — зафиксировать находкой, не чинить.
- Не коммитить, не запускать backend.
- Если находка требует правки плана — предложить формулировку, решение
  принимает разработчик.
