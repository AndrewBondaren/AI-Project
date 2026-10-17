---
name: "source-command-impl-topology-1"
description: "Имплементирует шаг 1 плана surface-topology: ТЗ sync — world_topology_mode, координатная карта трёх режимов, NeighborResult, canonicalize в tz_terrain_generation § Форма мира; seam-контракт (sphere-пары, pull-строчка, pack invalidation) в tz_world_pack_storage § L0. Только документы, без кода. Новый чат: /impl-topology-1."
---

# source-command-impl-topology-1

Use this skill when the user asks to run the migrated source command `impl-topology-1`.

## Command Template

# Имплементация: topology-1 — ТЗ sync формы мира и шва

Это **явная просьба править документы** (ТЗ). Кода в этом шаге нет — любая правка `*.py` = выход за скоуп.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом правки.

## Прочитать до первой правки

1. [`.cursor/plans/surface-topology.md`](../../../.cursor/plans/surface-topology.md) — **единственный SoT этой задачи**: §0 контракт (три режима, `NeighborResult`, canonical owner, pull-строчка), «Целевая реализация», «Решения (2026-10-17)» (все 5 — planar void, флаги в результате, порядок миграции, default `wrapped`, mode-change → full re-bake), «Порядок дальнейшей подготовки» п.1. Не отклоняться.
2. [`docs/tz_terrain_generation.md`](../../../docs/tz_terrain_generation.md) — § Форма мира / § шов мира — точки вставки, текущие формулировки шва.
3. [`docs/tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) — § L0 — seam-контракт тайлов.
4. Правила:
   - [`.cursor/rules/documentation-layout.mdc`](../../../.cursor/rules/documentation-layout.mdc) — ТЗ в `docs/`, планы в `.cursor/plans/`, не смешивать.
   - [`.cursor/rules/code-gates.mdc`](../../../.cursor/rules/code-gates.mdc) — один шаг за заход, отчёт → «ок».

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Скоуп шага 1 — строго по плану

**В `tz_terrain_generation.md` § Форма мира:**

- `world_topology_mode` — скаляр мира (`planar` | `wrapped` | `sphere`), wire-контракт, default `wrapped` (обратная совместимость: миров без поля = текущее тор-поведение).
- Координатная карта трёх режимов: torus (`wrapped`), сфера-проекция (`sphere`, пары кромок NORTH↔NORTH / SOUTH↔SOUTH с инверсией dy, **чётность x** для sphere), плоскость (`planar` — край = impassable void, `neighbor → None`).
- `NeighborResult{coord, edge_crossing: bool, invert_dy: bool}` — typed-результат lookup; intent transform — флаги, не метод (потребитель применяет сам).
- `canonicalize` — local-mod нормализация координат (идиома `wrap_owner_and_other`/`antipode_xy` переиспользуется, нового механизма нет).

**В `tz_world_pack_storage.md` § L0:**

- Seam-пары режимов: `wrapped` — как сейчас (`opposite(facing)`); `sphere` y-кромки — NORTH↔NORTH / SOUTH↔SOUTH (не `opposite`); `planar` — шва нет, no-op.
- Pull-строчка частичного bake: baked tile = `other` → читает owner-rim из пака и применяет `WorldSeamCopy` к себе; baked tile = `owner` → не строчит; pack-write за пределы bake-scope не вводится.
- Pack invalidation при смене `world_topology_mode`: меняется карта соседей → seam/halo всех испечённых тайлов инвалидны → обязательный full re-bake; warning при worldEdit.

- **Не в шаге 1:** `WorldTopology` код, `worlds` SQL-поле, любые `.py`, потребители. Только два документа.

## Жёсткие запреты

- Никакого кода. Правки только в двух файлах ТЗ.
- Терминология плана не переписывается (canonical owner/antagonist, pull-строчка, seam-pairs) — ТЗ вводит её как норму, не изобретает свою.
- Не добавлять механики вне решений (нет «виртуального края», нет edge-сущности).
- Не коммитить без явной просьбы.

## Приёмка

- Оба раздела содержат все пункты выше; ссылка `tz_map_light_bake.md` § Регионы покрытия › RegionShape на раздел «Форма мира» — валидна (агент сверяет anchor).
- Пометка «выполнен» в плане — только после «ок» мастера.

## Старт

Прочитай план целиком, покажи diff-план по двум документам (куда какие подразделы лягут, какие строки заменяются) до первой правки.
