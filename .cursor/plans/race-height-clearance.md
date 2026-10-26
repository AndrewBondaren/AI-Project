# Race stature → минимальные высоты здания (clearance по тиру)

Статус: **рамки согласованы с мастером 2026-09-30, код не начат**.

Контекст: расы разного роста требуют разных минимумов высот — двери и потолки
здания масштабируются от статуры расы жителя и экономического тира.

## Зафиксированные решения мастера

| # | Решение |
|---|---|
| R1 | `stature_z` — **typed-поле** на `RaceTemplateOutline` (не `race_traits` dict). SoT статуры |
| R2 | Clearance — **`IgnoreOnWire[int | None]` на `EconomyTierEntry`** (`ceiling_clearance`): явное значение используется как есть; опущено → дефолт по позиции тира в реестре мира |
| R3 | Дефолт clearance — по **рангу в `sorted_by_base_value`** реестра мира (`p = rank/(N-1)`): низший → `+1`, `0<p<0.8` → `+2`, `0.8≤p<1.0` → `+3`, высший (`p=1.0`) → `+4`. `N=1` → `+2`. Миры с нестандартным набором тиров получают рабочий дефолт автоматически |
| R4 | Привязка расы — каскад **building → district → settlement → world.default_race**, тот же паттерн что `TierResolver` (`tz_economic_tier.md` §4) |
| R5 | Применение — **только минимумы**: `min_room_z = stature_z + clearance(tier)`, `passage_min = stature_z`. Верхние границы `z_range` не сдвигаются |
| R6 | `door_height` — формула §3.7 не меняется: явное `≥ passage_min` → как есть; иначе авто-резолв `min(floor(z·ratio), cap)` → пропорции сохраняются самой формулой, clearance дверям не нужен (богатый тир → выше потолок → выше дверь бесплатно) |
| R7 | `culture` на district — **заглушка** (домена нет); wire-поле допустимо, не потребляется |
| R8 | Без расы в каскаде → текущее поведение полностью сохраняется (`world.default_passage_height`, никаких clearance-полов) |

## Слои и границы

```text
race (dataModel/races)          → stature_z
tier (dataModel/economy)        → ceiling_clearance на записи + percentile-default
location hierarchy              → building→district→settlement→world  (как TierResolver §4)
structure generator (runtime)   → min_room_z/passage_min floors на resolve
```

POJO не логируют; подмены/фолбэки — `ERROR` на границе `StructureGeneratorService`
(доктрина: `entry-point-pojo-done.md` §6.1/6.3 — degrade для игрока, не падение).

## Шаги

### Шаг R-TZ — ТЗ-дополнения (до кода)

| Поле | Содержание |
|---|---|
| Цель | зафиксировать домен в SoT-документах — без раздела ТЗ код-шаги невалидны |
| ТЗ | `tz_races.md` — `stature_z` на race template (typed, ge=1); `tz_economic_tier.md` — `ceiling_clearance` на `economyTierEntry` + percentile-дефолты (новый пункт §2/§4 + таблица §9); `tz_building_generator.md` — минимумы высот (§3.5 z_height floor, §3.7 door passage_min race-aware); `tz_world_bundle.md` — `world.default_race` рядом с `default_passage_height`; `tz_city_generation.md` — `race`/`culture` на district (culture=stub) |
| Done | разделы зафиксированы; wire-ключи и дефолты утверждены мастером |

### Шаг R1 — dataModel поля

| Поле | Содержание |
|---|---|
| Цель | typed-поля на расе и тире без потребителей |
| ТЗ | `tz_races.md` (новый раздел R-TZ); `tz_economic_tier.md` §1–§2 (entry N+1) |
| Файлы | `dataModel/races/raceTemplateOutline.py` (+`stature_z`); `dataModel/economy/economyTier/economyTierEntry.py` (+`ceiling_clearance`, `_fill_omitted` по образцу `road_tier_*`); `dataModel/economy/economyTier/worldEconomyTierRegistry.py` (percentile-default + `clearance_for(system_tier)`) |
| Контракт | `stature_z: DefaultOnWire[int|None] ge=1`; `ceiling_clearance: IgnoreOnWire[int|None] ge=1`; percentile-функция на registry |
| Проверка | новые тесты на entry defaults/override/percentile; `python -m compileall` |
| Done | поля парсятся, дефолты верны, registry API отдаёт clearance |

### Шаг R2 — каскад расы + мир

| Поле | Содержание |
|---|---|
| Цель | resolve race жителя по иерархии локаций |
| ТЗ | `tz_economic_tier.md` §4 (паттерн каскада); `tz_world_bundle.md` WB-13 (registry pointer); `tz_city_generation.md` (district fields) |
| Файлы | `db/models/world.py` (+`default_race`); `dataModel/locations/settlement/district/*` (поле расы на district-шаблоне); новый `generators/utils/raceResolver.py` (аналог TierResolver) |
| Контракт | `RaceResolver.resolve(building, district, settlement, world) → RaceTemplateOutline|None` |
| Проверка | unit на каскад (each level + fallback) |
| Done | каскад резолвится; без расы → None |

### Шаг R3 — применение минимумов в генераторе структур

| Поле | Содержание |
|---|---|
| Цель | race/tier floors на resolve высот |
| ТЗ | `tz_building_generator.md` §3.5 (z_range), §3.7 (door_height авто-резолв, нижний предел мира — теперь race-aware) |
| Файлы | `structureGeneratorService` (передача race/tier); `roomFactory._resolve_size` (`z_height` floor); `passages/entry.py`, `passages/doorway.py` (`passage_height` → `max(world.default, race.stature_z)`) |
| Контракт | `effective_passage_min = race.stature_z ?? world.default_passage_height`; `min_room_z = stature + clearance` |
| Проверка | A/B fingerprint 13 stdlib — идентично (нет рас → нет изменений); тест race-6: room 5→7, door 2→5 |
| Done | fingerprint без рас совпадает; race-fixture поднимает минимумы |

## Открытые вопросы (не блокируют R-TZ)

- Кто проставляет расу на district при генерации города (CITY-T домен, отдельный владелец).
- `stature_z` также влияет на ширину коридоров/проёмов, мебель, шаг лестницы — вне scope v1.
- Смешанное население здания (таверна для всех рас) — в v1 берётся раса по каскаду, мульти-раса отложено.
- `culture` на district: пока заглушка-поле; доменное потребление — отдельный план.

## Проверки среза (итоговые)

- `python -m unittest` — полный suite зелёный
- `python -m compileall -q app tests`
- A/B `sha256(cells+passages)` по 13 `structures_templates/base/*.json`: без рас — идентично HEAD
- Детерминизм ×2; sweep ERROR не хуже baseline (8)
- Доктрина логов: POJO молчат, подмены → ERROR на границе сервиса
