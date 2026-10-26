# Coastline forms — органичный берег вместо дословной прямой (HY-9)

**Долг:** HY-9 в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
**ТЗ:** [`docs/tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) § SeaBasinGenerator (U15/U21), § declare/autoresolve; прецеденты — `tz_map_light_bake.md` § RegionShape `edge_noise`, U14 (≤45°).
**Зависимость:** HY-6 ✅ (водная сторона `(C−K)·n > 0` для произвольной ориентации — закрыт). **HY-11/TOPO-1** — спайн через шов мира идёт через домен-метрику; для coastline у края в `wrapped`-мире зависит от домен-сервисов.
**Evidence:** `world_test_004` — declared прямая x=−1500 даёт бритвенный `s`-столбец через всю карту.

## Актуализация зависимостей 2026-10-20

Целевой контракт изменён [HY-12](hy-12-sea-elevation-contract-done.md): вода следует из relief carve и level-fill; procedural размещение designed water выделено в GEO-1 и использует [общий placement](generator-placement.md). Поэтому описанные ниже procedural spine по bbox edge, bbox-edge fallback и безусловный lagoon lake-carve — прежний проект, требующий пересмотра до реализации шагов 2–3 HY-9. Формы должны порождать intent/spec для общего placement и relief, а не обходить их своей генерацией воды. HY-6/HY-11 остаются прецедентами геометрии через шов. Dynamic membership — [водные системы](hydrology-water-systems.md), история замещения — [общий lifecycle](entity-lifecycle.md); они не реализуются в coastlineForms.

## Проблема

1. `DeclaredCoastline.path` растеризуется дословно → абсолютно прямая береговая линия (единственная доступная форма).
2. Autoresolve без declare — `_autoresolve_from_map_boundary`: flood от края bbox → прямые края воды по границе мира.
3. Бухты/лагуны невозможны без ручной геометрии (`declared_lakes` по точкам).

## Целевой контракт

### `CoastlineForm` (StrEnum, `dataModel/hydrology/enums/`)

| Form | Семантика |
|---|---|
| `straight` | path как есть — авторская воля (default declared) |
| `sine_noise` | спайн + перпендикулярный offset `A·sin(2πs/λ + φ) + (n(s)−0.5)·2·N` |
| `sine_lagoons` | `sine_noise` + бухты (landward-бугоры) + лагуны (эмиссия `LakeSpec`) |

- `DeclaredCoastline += form: CoastlineForm = STRAIGHT`, `form_knobs: CoastlineFormKnobs | None` (`amplitude`, `wavelength`, `noise_scale`, `bay_density`, `lagoon_density`, `lagoon_radius_min/max` — fine-клетки; defaults — POJO, не литералы).
- `HydrologySeasPolicy += coastline_form_policy` — форма/диапазоны knobs для autoresolve; выбор seeded (`seeded_u01(seed_root, UidKind.*, channel="coast_form", location_uid)`).
- **Трансформация до rasterize**: `expand_coastline_spine(path, form, knobs, uid) → (effective_path, emitted_lake_specs)` в `loadDeclaredHydrology` — master input видит уже кривую; lagoon-спеки вливаются в `loaded.lake_specs` с `location_uid` берега → по единому механизму HY-12 это `BasinSpec(kind=lake)` — тот же pipeline `spec → carve → fill → classify`, отдельного lake-carve нет.
- **Изгибы:** offset в обе стороны от спайна (к суше и к воде); бухта = landward-дуга amplitude×2..3 на seeded-участке; лагуна — замкнутый N-gon полигон на стороне суши вблизи линии.
- **Ограничения:** U14 — deflection ≤45° между сегментами после трансформации (ресемпл при нарушении); clip effective path в bounds (клетки вне heightmap отсекаются); amplitude ≤ расстояние до края bounds на land-стороне и до других coastline (v1: половина минимального зазора); детерминизм — только `seeded_u01`/`seed_rng` каналы `coast_form`/`coast_noise`/`bay`/`lagoon` по `location_uid`.
- **Autoresolve без declare:** процедурный спайн внутри bounds вдоль `_ocean_axis` (perpendicular ось, inset 1–2 map-клетки от края) → form → тот же declared-пайплайн. Bbox-edge flood остаётся только как degenerate fallback при пустом спайне.
- **HY-6 не трогается:** water-side считается по финальной (трансформированной) линии — контракт ортогонален форме.

## Шаги

### Шаг 1 — ТЗ: «Форма береговой линии»

| Поле | Содержание |
|---|---|
| Цель | зафиксировать union форм, knobs, autoresolve-политику и emission-семантику лагун до кода |
| ТЗ | `tz_terrain_hydrology.md` § SeaBasinGenerator — новый пункт «Форма береговой линии»: `CoastlineForm`, knobs таблица, `default_seas.coastline_form_policy`, лагуны = emitted `LakeSpec` (U20), U14-ограничение, clip bounds, детерминизм каналов; обновить U21 (declare: path = спайн при `form ≠ straight`) |
| Файлы | `docs/tz_terrain_hydrology.md` |
| Проверка | согласовано с мастером |
| Done | раздел обновлён |

### Шаг 2 — POJO + spine transform (declared path)

| Поле | Содержание |
|---|---|
| Цель | `form`/`form_knobs` на declare + `expand_coastline_spine` + lagoon emission |
| ТЗ | § «Форма береговой линии» (шаг 1) |
| Файлы | `dataModel/hydrology/enums/coastlineForm.py` (new), `declaredCoastline.py` (+поля), `shore/coastlineForms.py` (new: resample→offset→bays→lagoons, pure, seeded), `loadDeclaredHydrology.py` (transform до `_path_to_segments`; lagoon → `lake_specs`) |
| Контракт | `expand_coastline_spine(path: list[HydrologyWaypoint], form, knobs, uid) -> tuple[list[HydrologyWaypoint], list[LakeSpec]]`; `straight` — identity, ноль lagoon; seeded-каналы из `app.ids` |
| Проверка | `python -m unittest backend.tests.test_hydrology_hy9`: determinism (2 вызова — тот же path), `straight` identity, U14 после transform, clip у края, lagoon count по `lagoon_density`, offsets в ±amplitude |
| Done | форма влияет на effective path; лагуны попадают в `lake_specs`; тесты зелёные |

### Шаг 3 — autoresolve спайн

| Поле | Содержание |
|---|---|
| Цель | autoresolve без declare — процедурная кривая вместо прямого bbox-edge flood |
| ТЗ | § «Форма береговой линии» + § declare/autoresolve |
| Файлы | `proceduralSeaAutoresolve.py` (`_autoresolve_from_map_boundary` → генерация спайна по `_ocean_axis` + form policy → declared-пайплайн; bbox-edge flood — fallback при вырожденном спайне), `hydrologyAutoresolvePolicy.py` (`coastline_form_policy` resolve) |
| Контракт | без изменений `autoresolve_sea_basins` сигнатуры |
| Проверка | тесты hy5a + новые: спайн сгенерирован при пустом declare, форма применена, fallback на вырожденном миру |
| Done | procedural ocean край — кривая, не бритва |

### Шаг 4 — фикстура + smoke

| Поле | Содержание |
|---|---|
| Цель | органичный берег и лагуны на реальном мире |
| ТЗ | § «Форма береговой линии»; smoke из HY-5 |
| Файлы | `fixtures/world_test_004.json`: coastline `form: "sine_lagoons"` + knobs (после HY-6 шаг 4: линия x=−500) |
| Проверка | rebake → `render-world-grid` + `render_maps.py`: `s`-линия кривая (синус + бухты), лагуны — `s`-кольца с водой, U14 не нарушен; до HY-6 smoke только E-W-ориентация |
| Done | берег не прямой, лагуны видны, determinism по re-bake |

## Не входит

- HY-6 flood fix (отдельный план, prerequisite).
- HY-7 shoreline × mountain; HY-8 вода-уровень; HY-BATH-1 rim-профиль.
- Concave/branching спайны, tide/erosion динамика, mangrove/delta классы.
- LLM naming для сгенерированных бухт/лагун (HY-3).
