# Climate water bodies — климатический трек hydrology

Источник: продолжение hydrology-работ (2026-10-19). Трек «вода появляется через
климат» — отдельный от событий (morph→lake = `region_uid`, T-1).

## Решения мастера (приняты)

| Вопрос | Решение |
|---|---|
| Место | `HydrologyScope` на surface-planning — полный carve-пайплайн (z, shore, `coarse_hydro`, persist, L0→L2) |
| v1 scope | озёра + реки + моря |
| Identity | `climate-{role}-{anchor}` — non-durable позиционный, как `auto-*`; persist/`region_states` не опираются |
| Policy | новый блок `world.hydrology.climate_water` |

## Контракт

**POJO** — `app/dataModel/hydrology/climateWater.py` (новый):

```python
class ClimateWaterPolicy(BaseModel):
    enabled:            DefaultWhenMissing[bool] = False
    min_rainfall:       DefaultWhenMissing[int]  = 60   # effective_rainfall 0..100 gate
    lakes:              DefaultWhenMissing[bool] = True
    rivers:             DefaultWhenMissing[bool] = True
    seas:               DefaultWhenMissing[bool] = True
    seas_min_area_cells: DefaultWhenMissing[int] = 25   # basin area ≥ → INLAND_SEA, иначе LAKE
```

`WorldHydrology += climate_water: DefaultWhenMissing[ClimateWaterPolicy | None] = None`.
По умолчанию выключено — ноль изменений поведения.

**Гейт** — `generators/hydrology/climate/climateWaterGate.py`:

```python
def climate_rainfall_at(world, pole_field, gx, gy) -> int:
    sample = pole_field.sample(world, gx, gy)
    prof   = profile_for(world, sample.system_climate_zone)
    temp   = sample.base_temperature_override or prof.base_temperature
    return effective_rainfall(prof.base_rainfall, temp, world)  # mult=0 фаза уже внутри
```

Carve iff `rainfall >= policy.min_rainfall`. Пустой `pole_field` → default zone —
работает и без полюсов.

**UID** — `waterBodyIdentity.py += climate_water_body_uid(role, anchor)` →
`climate-lake-{x}x{y}` / `climate-sea-{min}` / `climate-river-{src}`.
Тот же `AutoWaterBodyRole` enum, другой префикс.

**Приоритет**: declared > autoresolve > climate — единый `occupied`/`claimed`;
climate стампует только свободные клетки. Scope-порядок: после RIVERS,
перед LANDFORMS.

## Шаги

### Шаг 1 — контракт + POJO + TZ

Цель: wire/политика/scope-enum/uid-хелпер — без carve-логики.
ТЗ: `docs/tz_terrain_hydrology.md` — новый § «Климатические водоёмы» после § C2
`water_body_uid`: блок `climate_water`, формула гейта, uid-префикс, приоритет,
сплит LAKE/INLAND_SEA по `seas_min_area_cells`.
Файлы: `dataModel/hydrology/climateWater.py` (new), `worldHydrology.py`,
`generators/hydrology/types.py` (`CLIMATE_WATER` + `HYDROLOGY_BOOTSTRAP_SCOPES`),
`load/climateWaterPolicy.py` (new), `waterBodyIdentity.py`.
Проверка: `python -m unittest tests.test_hydrology_declared_wire` +
wire round-trip `climate_water` в новом тесте; compileall.

### Шаг 2 — basin carve (lakes + inland seas)

Цель: климатические бассейны — lake/sea в зависимости от площади.
Файлы: `climate/climateWaterGate.py` (new), `climate/climateBasinCarver.py` (new).
Контракт: `climate_basins(world, heightmap, master, occupied, policy, pole_field)
-> (entries, dirty)`; reuse `detect_terrain_features` + `flood_basin_interior` +
`carve_lake_interior(..., water_body_uid, open_role=LAKE|INLAND_SEA)`.
Проверка: unit-тесты wet/dry/no-poles/disabled.

### Шаг 3 — river sources из влажных зон

Цель: wet local maxima → climate rivers.
Файлы: `climate/climateRiverCarver.py` (new), `riverBedCarver.py`
(+= опциональный `water_body_uid` param — паттерн `carve_lake_interior`/
`carve_deepening_bands`).
Контракт: `climate_river_segments(world, heightmap, master, occupied, policy,
pole_field) -> (entries, segments, dirty)`; `find_river_sources` → фильтр
rainfall → `plan_descent_path` → cap `MAX_RIVERS_PER_BBOX`.
Проверка: unit-тесты wet source carve, dry → пусто, cap.

### Шаг 4 — оркестратор + wiring

Цель: scope в сервисе + `pole_field` в `apply()`.
Файлы: `climate/climateWaterFill.py` (new, merged entries+dirty),
`hydrologyGeneratorService.py` (`apply(..., pole_field=None)`; блок после RIVERS:
`policy.enabled and pole_field is not None`), `surfaceTerrainContext.py`
(`pole_field=pole_field`).
Проверка: end-to-end `svc.apply` с pole_field; полный hydrology-прогон.

### Шаг 5 — тесты `test_hydrology_climate_water.py`

Файлы: новый тест + `hydrology_fixtures.py` (`pole_field` helper —
single pole uniform zone: TROPICAL=80 wet, DESERT=5 dry).
Кейсы: policy off→пусто; dry→пусто; wet+depression→LAKE+`climate-lake-*`;
area≥seas_min→INLAND_SEA+`climate-sea-*`; min_rainfall граница; river source→
`climate-river-*`; declared occupied не трогается; `apply` end-to-end;
детерминизм ×2.

## Приёмка

- Все 5 шагов зелёные; полный hydrology-набор + compileall.
- `climate_water.enabled=False` → ноль водоёмов независимо от климата.
- uid `climate-*` только внутри policy-enabled ветки; declared/autoresolve
  клетки никогда не перетираются.
