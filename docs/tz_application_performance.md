---
name: tz-application-performance
description: "SoT измеренных прогонов bake/runtime. Backlog pack light — WP-PERF. Не алгоритм mill/paint."
metadata:
  node_type: memory
  type: project
---

# Производительность приложения

**Статус:** SoT **измерений** (что засекли, как читать тайминги, приёмка качества прогона). Backlog оптимизации light/orchestration — [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) § WP-PERF. Generate grade — [`tz_terrain_relief.md`](./tz_terrain_relief.md). Dump ASCII — [`tz_terrain_relief_consume.md`](./tz_terrain_relief_consume.md).

Чат / DAG / UI в этом файле **нет**, пока нет прогона.

| Документ | Роль |
|---|---|
| Этот файл | baseline прогонов, wall vs CPU-sum, что входило в HTTP vs скрипт |
| [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) § WP-PERF | IDs PERF-10…51, цели light bake |
| [`tz_map_light_bake.md`](./tz_map_light_bake.md) | контракт L0 compose |

---

## Граница

| Этот TZ | Не этот TZ |
|---|---|
| Засечённое время bake / dump | Алгоритм Q1/Q2, θ, pack-слоты |
| Как читать `l2_s` vs `paint_s` | Новый SLO без решения мастера |
| Приёмка качества этого прогона (paint) | Замена WP-PERF backlog |

**Не путать:** [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) **WP-PERF-2** («узкое место — orchestration, column fill &lt; 0.5 s») — профиль **L0 / light** 2026-07-10. На **L2 detailed** 2026-08-30 узкое место — **paint** (CPU-сумма), не INSERT wilderness.

---

## Как читать тайминги bake

Источник wire: `GradePipelineTimings` + bake-only `l2_s` / `grade_persist_s` (лог `detailed_bake` / `packBakeLog`).

| Ключ | Что это |
|---|---|
| **`l2_s`** | Календарное время (wall) prep + generate + pack persist на джобе. **Не** SQL catalog. |
| **`elapsed_s` скрипта** на клетке | Wall HTTP `POST …/pack/bake` (ждёт ответ). Обычно ≈ `l2_s`. |
| **`q1_s` / `q2_s` / `mill_s` / `paint_s` / `grade_s` / `materialize_s`** | **Сумма CPU по чанкам.** При `workers > 1` может **быть больше** `l2_s`. |
| **`grade_persist_s`** | Wall SQL catalog после чанков |
| Скрипт `detailed_bake.py` целиком | HTTP bake **плюс** dump ASCII на диск (не часть `l2_s`) |

Dump (z-срезы, `surface_grade.txt`) **не** входит в bake.

Offline `detailed_bake` mill/paint **выкл.** пока не переданы `grade_mill` / `grade_paint` (ГМ может включить и залить pack — тогда сцена читает). Entry refine mill/paint **нет** (старт = L2 column fill). Product mill на сцене — DAG, когда рельеф необходим ([`tz_terrain_relief.md`](./tz_terrain_relief.md) § Caller). APP-PERF-R1 ниже — прогон **с** явным mill+paint. Без них остаётся L2 fill от parent-light, не «пустой bake».

---

## Прогон APP-PERF-R1 — `world-test-003`

| Поле | Значение |
|---|---|
| Дата | 2026-08-29…30 (UTC dump `20260829T212358Z`) |
| Мир | `world-test-003`, fixture `fixtures/world_test_gen_003.json` |
| Bounds | `world_bounds` −2…2 (25 L0 тайлов) |
| БД | recreate → seed → skeleton import → `mode=full` → `mode=detailed` wilderness `(-2,-2)` |
| Качество L2 | мастер: **paint визуально корректен** (`surface_grade.txt`) |
| Железо | не фиксировали (L0 full: `terrain_workers=5`) |

Команды:

```text
POST /api/worlds/world-test-003/map/pack/bake?mode=full
python backend/scripts/detailed_bake.py --world-uid world-test-003 --scope wilderness --gx -2 --gy -2 --grade-mill --grade-paint
```

HTTP detailed: `POST …/pack/bake?mode=detailed&scope=wilderness&tile_gx=-2&tile_gy=-2&grade_mill=true&grade_paint=true`.
(Прогон 2026-08-29 был при тогдашнем default on; сейчас те же флаги нужно передать явно.)

Артефакт dump: `.local/map-render/world-test-003/detailed-bake/after-detailed/20260829T212358Z/wilderness/Gx-2_Gy-2/surface_grade.txt` (latest → тот же run).

### L0 `mode=full`

| | |
|---|---|
| HTTP | 200, клиент **11.06 с**, сервер `elapsed_s=10.75` |
| Тайлы | 25 / 25, `pack_completeness=full_complete` |
| Клетки | 25 600 |
| Климат | coarse, 25 сэмплов |
| L2 wilderness | не печётся этим шагом (`wilderness_pct=0`) |

### L2 `mode=detailed` wilderness `(-2,-2)`

| | |
|---|---|
| HTTP | 200, `detail=complete` |
| Чанки | 0 → **1024** (остальные 24 тайла мира `absent`) |
| Wall HTTP / `l2_s` | **823.31 с** / **819.59 с** (~13 мин 43 с) |
| SQL catalog | `grade_persist_s=1.32` с |
| Скрипт целиком | **902.06 с** (~15 мин 2 с) = bake + dump |
| Dump после bake | **~78 с** (ASCII тайла + **2800** z-файлов; `--grade-z` не включали) |

CPU-сумма по чанкам (не wall):

| Фаза | с | Смысл |
|---|---:|---|
| Q1 leftover | 368.29 | очередь mill leftover |
| Q2 | 51.43 | посадки / бока |
| mill (все части) | 438.97 | поиск фронтов (Q1+Q2+sheer+швы+setup) |
| mill_sheer / mill_seam / mill_reconcile | 9.46 / 2.59 / 0.12 | внутри mill |
| paint | **3141.42** | врезка grade в heightmap — **горячая точка** |
| grade (discover+paint+швы на чанке) | 3592.05 | включает paint |
| materialize | 212.31 | заполнение колонок |
| sidecar | 19.00 | pack `slots[8]` |
| validate | 0.00 | product bake без occupancy-validator |
| systems_emit | 1.86 | T-3c catalog emit |

Порядок внутри HTTP: upsample parent-light → пул чанков (mill → pick шаблона `smoke_003` → paint → materialize) → pack persist → sidecar → catalog emit → SQL.

---

## Выводы с прогона

1. L0 full на 25 тайлах 003 — **~11 с**, не узкое место этого сценария.
2. Один L2 wilderness-тайл (1024 чанка, grade включён) — **~14 мин wall**; почти всё — параллельный mill+paint.
3. Оптимизация L2, если понадобится: **paint**, не dump и не SQL persist. Product: mill/paint **не** звать постоянно (entry, каждый scene read). Несколько чанков, когда сцена требует grade — ок. Полный мир — только ГМ `grade_mill=true` (+ `grade_paint=true`). Тайл ~1024 чанка — APP-PERF-R1, не gameplay path.
4. Сравнивать прогоны по **`l2_s` / HTTP `elapsed_s`**, не по `paint_s` как «ещё 50 минут».
5. Качество: paint этого тайла принят; слоты/occupancy T-25 этим прогоном **не** закрывались.

SLO на L2 detailed **не** записывали. WP-A1 (light ≤ 2 min) этот прогон не отменяет.

---

## История

| Дата | Изменение |
|---|---|
| 2026-08-30 | **Бюджет:** mill не спекулятивно; несколько чанков на сцене ок; полный мир = bake ГМ. APP-PERF-R1 = тайл целиком. |
| 2026-08-30 | Product: mill/paint default **off** (bake opt-in; entry никогда). **APP-PERF-R1** = явный полный mill+paint. |
| 2026-08-30 | Файл создан. **APP-PERF-R1:** 003 full ~11 с; detailed `(-2,-2)` wall ~820 с, paint CPU-сумма ~3141 с; paint визуально ок. |
