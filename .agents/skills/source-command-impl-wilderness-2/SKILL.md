---
name: "source-command-impl-wilderness-2"
description: "Имплементирует шаг 2 плана wilderness-regions-mechanic: dataModel каркасы RegionSpecBase + ForestSpec/PlainSpec/FarmlandSpec, union LandcoverDeclareEntry, WorldTerrainMasks.declared_regions, RegionShape union (bbox/ellipse/polygon/anchor_radius + EdgeNoise), author-валидация форм. Вход: шаг 0 закрыт. Новый чат: /impl-wilderness-2."
---

# source-command-impl-wilderness-2

Use this skill when the user asks to run the migrated source command `impl-wilderness-2`.

## Command Template

# Имплементация: wilderness-2 — dataModel Specs + RegionShape

Это **явная просьба писать код**. Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../../../.cursor/plans/wilderness-regions-mechanic.md) — **единственный SoT этой задачи**: §4 строка **2** (цель/ТЗ/файлы/проверка); §5 #7 (shape-примитивы, валидация форм, `placement_specificity`), #9 (density, точки расширения — `flora`/`crop` не вводятся), #1 (identity: `name` обязателен при author-валидации). Раздел «Coverage region — каркас контракта» — черновик, актуальный контракт — в ТЗ. Не отклоняться.
2. [`docs/tz_map_light_bake.md`](../../../docs/tz_map_light_bake.md) — § Регионы покрытия › **Spec union** (поля/дискриминант `entry_type`), › **RegionShape** (4 формы, `edge_noise`, координаты мировые fine), › **Точки расширения** (полей `flora`/`crop` **нет** до владельца), › Identity (`name`, запрет `|`).
3. [`docs/tz_flora.md`](../../../docs/tz_flora.md) — `ForestComposition` ↔ `ForestSpec` (target): почему поля `flora` в Spec сейчас **нет** (ключ в wire = unknown key).
4. Правила (нарушение = стоп):
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок»
   - [`.cursor/rules/layer-boundaries.mdc`](../../../.cursor/rules/layer-boundaries.mdc)
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../../../.cursor/rules/dataModel-no-hardcode.mdc) — defaults только в POJO
   - [`.cursor/rules/project-context.mdc`](../../../.cursor/rules/project-context.mdc) — не DAG, не стартовать backend, не коммитить, schema только через `0001_initial.sql`
   - [`.cursor/rules/class-size-limit.mdc`](../../../.cursor/rules/class-size-limit.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Что уже есть — не переписывать

- `backend/app/dataModel/terrainMasks/mountain/` (`enums.py`, `specs.py`, `__init__.py`) — **образец пакета** Spec-union с `location_uid` optional link; повторить его структуру.
- `backend/app/dataModel/terrainMasks/worldTerrainMasks.py` — корень масок; сюда `declared_regions: list[LandcoverDeclareEntry]` (не отдельные `declared_forests`/`declared_plains`).
- `backend/app/dataModel/spatial/` — есть `facing.py`; сюда `regionShape.py`.
- `backend/app/ids/deterministicIds.py` — после шага 0 содержит `seeded_u01`/`seeded_index` (в этом шаге не используются, только контекст).
- Валидация форм: паттерн — ошибка валидации, **не** silent fix/fallback.

## Скоуп шага 2 — строго по плану §4

- `backend/app/dataModel/spatial/regionShape.py` — discriminated union `RegionShape` по `kind`: `BboxShape{x_min,y_min,x_max,y_max}`, `EllipseShape{cx,cy,rx,ry}`, `PolygonShape{vertices}` (>=3, замкнутый), `AnchorRadiusShape{anchor_uid,radius}` + общий `edge_noise: EdgeNoise | None` (`{amplitude, scale}`). Чистые методы `contains(x,y)`, `bbox()`, `area()` — **без** применения `edge_noise` (шум применяется растеризатором шага 4, не геометрией).
- `backend/app/dataModel/terrainMasks/regions/` — новый пакет по образцу `terrainMasks/mountain/`:
  - `specs.py`: `RegionSpecBase` (frozen) `{name, shape, density: float = 1.0, placement_specificity: int | None (ge=0), location_uid: str | None}` + `identity_key()`;
  - `ForestSpec` (`entry_type="forest"`), `PlainSpec` (`entry_type="plains"`), `FarmlandSpec` (`entry_type="farmland"`) — без `flora`/`crop` (там где поле появится позже — **обязательный комментарий** «точка расширения, состав — `docs/tz_flora.md`, поля нет — unknown key»);
  - `enums.py` при необходимости; `LandcoverDeclareEntry` — union с discriminant `entry_type`.
- `WorldTerrainMasks.declared_regions: list[LandcoverDeclareEntry]` — единственная плоская коллекция; существующие `default_forests`/`default_plains` и домены `FORESTS`/`PLAINS` **не трогать** (transitional, cutover — шаги 7b/10b).
- Author-валидация форм: `rx<=0`/`ry<=0`, `vertices<3`, самопересекающийся polygon, `x_max<x_min`/`y_max<y_min`, `radius<=0` — **ошибка**, не fallback; `name` обязателен для declared при validate_only (runtime fallback — шаг 3, здесь только не блокировать отсутствием на runtime-пути).
- Юнит-тест discriminated union: разбор по `entry_type`, разбор по `kind`, reject malformed wire.

- **Не в шаге 2:** precedence-функция (2b), `UidKind.REGION` и реестр (3), merge_rank cutover (3b), `RegionRasterizer` и `contains` на шуме (4), resolver/materializer (5), paint на клетках (6–7), region_states/state (9–10). Никакой оркестрации, никаких вызовов из генераторов — только dataModel-каркас и валидация.

## Жёсткие запреты

- `edge_noise` не применять в `contains`/`bbox`/`area` — шум живёт в растеризации (шаг 4); методы shape чистые и детерминистичны.
- Не добавлять поля `flora`/`crop`/`origin_x`/`origin_y`/`priority` — origin только в shape, приоритет только через `merge_rank`+`placement_specificity`.
- Не менять wire существующих масок: `FORESTS`/`PLAINS`/`default_*` — без правок.
- Не трогать DAG-ноды, schema, не стартовать backend, не коммитить.
- Pydantic = единственный контракт: defaults и нормализация в моделях, не в consumers.
- Проверки запускать из `backend/`; не чинить окружение «заодно».

## Приёмка (из плана, строка 2)

- `python -m compileall backend/app` — чисто.
- Schema/validate world JSON с `declared_regions[]` (forest/plains/farmland × 4 формы shape) — разбирается typed; юнит union-discriminant зелёный.
- `rx<=0` / `vertices<3` / самопересекающийся polygon / перевёрнутый bbox / `radius<=0` → ошибка валидации (issue), **не** silent fix.
- Поля `flora`/`crop` в wire отклоняются как unknown key (поведение текущей модели).
- Пометка «выполнен» в плане — только после приёмки и «ок» мастера.

## Старт

Прочитай план целиком, сверь строку шага 2 и статус шага 0 с кодом, покажи карту файлов (новый пакет `regions/` по образцу `mountain/`, `spatial/regionShape.py`, diff `worldTerrainMasks.py`) до первой правки.
