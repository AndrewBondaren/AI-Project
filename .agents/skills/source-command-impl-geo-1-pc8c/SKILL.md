---
name: "source-command-impl-geo-1-pc8c"
description: "Имплементирует PC-8C плана geo-1-designed-water.md: ClimateLocalPlanProvider — local climate anchors от final hydrology surface, deps climate_base + hydrology. Входы закрыты: PC-0…PC-8 (включая R-разделение ответственностей PC-8). Новый чат: /impl-geo-1-pc8c."
---

# source-command-impl-geo-1-pc8c

Use this skill when the user asks to run the migrated source command `impl-geo-1-pc8c`.

## Command Template

# Имплементация: GEO-1 PC-8C — local climate provider после hydrology

Это **явная просьба писать код** (шаг PC-8C плана). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/geo-1-designed-water.md`](../plans/geo-1-designed-water.md) — **единственный SoT**. Обязательные разделы: §5.4 (карта модулей), §6.26 stage 6 (climate_local stage), §6.31-E (порядок assembler calls), §6.33 (`SurfacePlanSlot`, member `CLIMATE_LOCAL="climate_local"`), §7 PC-8C (тело шага) и DONE-блоки PC-5/PC-6S/PC-8 (готовые входы и паттерны).
2. [`docs/tz_climate.md`](../../docs/tz_climate.md) — §local field: существующая семантика anchors от final surface.
3. [`docs/tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) — §PC-D1: граница provider↔domain owners, принятая для PC-8 (действует и здесь).
4. [`.cursor/plans/geo-1-pc8-responsibility-refactor-done.md`](../plans/geo-1-pc8-responsibility-refactor-done.md) — принятый паттерн разделения: provider = только lifecycle-обвязка.
5. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc) — один шаг за заход, шесть полей шага
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc) — § Boundary-адаптеры: provider не содержит доменных операций
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc) — инвентаризация → строгий тип
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc) — монстр не только про строки
   - [`.cursor/rules/folder-composition.mdc`](../rules/folder-composition.mdc) — счёт файлов до добавления

План важнее догадок. Противоречие план↔ТЗ↔код — остановиться и спросить мастера.

## Scope этой команды

**Только PC-8C.** PC-9A (assembler/bundle) и далее — вне scope: они стартуют по следующей команде. GEO-1 algorithms не активируются.

Цель шага (§7): сохранить существующую зависимость anchors от final surface — `ClimateLocalPlanProvider` выдаёт `ClimateLocalPlan` из `climate_base` + `hydrology` (final) envelopes через `SurfacePlanSlot`.

## Что уже есть — не переписывать

- `dataModel/climate/planning/climatePlan.py::ClimateLocalPlan` и `inputs/climateLocalInput.py::ClimateLocalInput` — frozen typed contracts из PC-1C, поля не менять без правки плана.
- `dataModel/surfacePlanning/surfacePlanSlot.py::SurfacePlanSlot` — slot names только через enum (`.value` → `PlanSlot`), никаких string literals (PC-6S).
- `application/worldData/generators/climate/planning/climatePlanProvider.py` — существующий base provider (PC-5); `ClimateLocalPlanProvider` добавляется в тот же файл по карте §7.
- `climate/localFieldFromCoarse.py`, `assemblers/climateAssembler/passes/anchorCollectPass.py` — existing kernels, pure input adapter seam; не дублировать логику.
- PC-8 паттерн (`hydrology/planning/`): provider = require deps → exact ref checks → делегирование; если domain work не помещается в pure seam — сначала карта владельцев, не методы в provider.
- `application/planning/` — generic engine; domain код в него не вносить.

## Жёсткие запреты

- Не изменять `ClimateBasePlan` и не вызывать повторный base pole planning: climate_base приходит готовым envelope.
- Не создавать цикл `climate_base → hydrology → climate_base`: deps только `CLIMATE_BASE` + `HYDROLOGY` (final), не routes/relief напрямую.
- Нет live `World`/registry/SQL/pack reads в provider/owner; только frozen inputs + typed envelopes.
- Нет `Any`, raw dict, cast, string slot literals, synthetic defaults.
- Provider не содержит доменных операций (layer-boundaries § Boundary-адаптеры); anchor/local-field логика — в existing kernels или выделенном owner по карте, не в `build`.
- Не DAG-ноды, не backend-старт, не коммит, не SQL.
- Production registration/caller activation — PC-9A/PC-9, не этот шаг.

## Приёмка (Done по §7)

- `build` выдаёт `ClimateLocalPlan`; slots `climate_base`/`hydrology` через `SurfacePlanSlot`; exact upstream ref проверяется.
- Providers suite §6.27 зелёный; anchor baseline равен legacy; отсутствие цикла climate_base → hydrology → climate_base проверено.
- Final z edit инвалидирует local anchors (новый key → rebuild); неизменный climate base сохраняет свой cache key.
- Pyright valid0 / negative exact code+location по существующим configs; folder counts соблюдены.
- DONE-запись в плане: файлы, классы, размеры, проверки, счётчики тестов — по формату предыдущих PC-шагов.

## Старт

Прочитай §7 PC-8C + §6.26 stage 6 + §6.33, сверь `climatePlanProvider.py` и `climatePlan.py` с текущим кодом (могло уехать после PC-1C/PC-6S), инвентаризируй anchor/local-field kernels, затем реализуй provider и adapter seam по карте. Отчёт: сделано/файлы/проверки → ждать «ок».
