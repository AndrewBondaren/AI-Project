---
name: "source-command-impl-wilderness-10b"
description: "Имплементирует шаг 10b плана wilderness-regions-mechanic: landcover domain cutover — удалить MaskDomainId.FORESTS/PLAINS (contributor-map → LANDCOVER), resolve_forest_plains/profile_for_zone_key/*_from_zone (потребители terrainZ → CoverageResolver или fallback-ключ policy), ForestsCategoryPolicy/PlainsCategoryPolicy → LandcoverRegionsCategoryPolicy, default_forests/default_plains — wire-алиасы на чтение. Входы закрыты: 5b–7b. Новый чат: /impl-wilderness-10b."
---

# source-command-impl-wilderness-10b

Use this skill when the user asks to run the migrated source command `impl-wilderness-10b`.

## Command Template

# Имплементация: wilderness-10b — landcover domain cutover

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

**Блокер-условия (все):** шаги 5b, 6, 7, 7b сданы — `LANDCOVER` paint работает end-to-end (L0+L2, hills по ключу); `CoverageResolver` существует. Чего-то нет → стоп, доклад мастеру (cutover не делается до живой замены).

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **10b** (цель/ТЗ/файлы/проверка); §5 #5 (per-cell fallback роль `default_*`), #9 (hills-политика transitional — после 7b её источник — реестр). Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § **Домены terrain_masks** (LANDCOVER единственный; FORESTS/PLAINS transitional), § Plugin map (`MASK_DOMAIN_CONTRIBUTOR`), § Корни JSON (`default_forests`/`default_plains` → wire-алиасы).
3. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § L2 open-land hills (источник hills после 7b).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — fallback-ключ из policy-POJO
   - [`.cursor/rules/contract-creation.mdc`](../../../.cursor/rules/contract-creation.mdc)
   - [`.cursor/rules/type-kind-str-fields.mdc`](../../../.cursor/rules/type-kind-str-fields.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/dataModel/masks/enums/maskDomainId.py` — `FORESTS`/`PLAINS` (строки 18–19), contributor-map (~42–43) → `LANDCOVER`.
- `backend/app/application/worldData/masks/resolveForestPlains.py` — удаляемый climate-resolver (interim-правила уже в `eligibility` реестра — 5a).
- `backend/app/application/worldData/generators/terrain/terrainZ.py` + `generators/climate/terrainZ.py` — потребители `resolve_forest_plains`/`profile_for_zone_key`/`*_from_zone`; перепайка → `CoverageResolver` или fallback-ключ policy.
- `backend/app/dataModel/terrainMasks/worldTerrainMasks.py` — `default_forests`/`default_plains`, `ForestsCategoryPolicy`/`PlainsCategoryPolicy`.
- `wd/generators/terrain/landcover/` + `contributors/landcover*.py` + `pack/read/regionStateOverlay.py` — новые пути (шаги 5b–9c уже реализованы).
- `dataModel/terrain/hillPolicy.py` — `HillPolicy` (источник после 7b — `TerrainRegistryEntry.hills`).
- Существующие тесты/smoke — приёмка.

## Скоуп шага 10b — строго по плану §4

- Удалить `MaskDomainId.FORESTS`/`PLAINS`; `MASK_DOMAIN_CONTRIBUTOR` → единственный `LANDCOVER`.
- Удалить `resolve_forest_plains`, `profile_for_zone_key`, `*_from_zone`; потребители `terrainZ` (terrain + climate) → `CoverageResolver` (там где решение нужно по контексту) или фоновый fallback-ключ policy (для фона вне регионов).
- `ForestsCategoryPolicy`/`PlainsCategoryPolicy` → `LandcoverRegionsCategoryPolicy` — policy с fallback-ключом (per-cell фон вне регионов) + `transition_threshold` (из 10a — если policy уже введён там, консолидировать, не дублировать).
- `default_forests`/`default_plains` в `WorldTerrainMasks` — **wire-алиасы на чтение** (старые JSON импортируются без правок): на parse мапятся в `LandcoverRegionsCategoryPolicy`-источник (hills/fallback/…), записываются обратно или deprecate — по ТЗ § Корни JSON; не дублировать значения в двух моделях.
- Юнит/smoke по приёмке ниже.

- **Не в шаге 10b:** state-machine consumer (10a — уже есть), worldEdit (10c), удаление `HillPolicy`-wire полей из `default_*` (alias продолжает их читать), region merge/renames.

## Жёсткие запреты

- Wire-совместимость: `world_test_002` импортируется **без правок JSON** — `default_forests`/`default_plains` читаются как alias.
- Один источник значений: alias читает из нового policy-поля, не хранит копию.
- Никаких ссылок на `FORESTS`/`PLAINS` после удаления (grep до нуля, включая тесты/fixtures комментарии где семантика устарела).
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 10b)

- `python -m compileall backend/app` — чисто; `grep` `FORESTS`/`PLAINS`/`resolve_forest_plains`/`profile_for_zone_key`/`*_from_zone` — ноль в коде.
- Import `world_test_002` без правок JSON — проходит (alias-чтение).
- Light bake smoke идентичен шагу 6 (та же карта покрытия).
- `LandcoverRegionsCategoryPolicy` — единственный источник fallback-ключа/threshold; `default_*` — alias.
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, проверь все блокеры, покажи полный grep-лист удаляемых символов с планом замены каждого потребителя (`terrainZ` ×2 и др.) до первой правки.
