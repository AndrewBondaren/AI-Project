# Матрица каскадных параметров

Сверочная таблица к плану [`cascade-migration-done.md`](cascade-migration-done.md)
и ТЗ [`docs/tz_cascade_context.md`](../../docs/tz_cascade_context.md)
(§2 — связный список полей, §4 — движок, §5 — параметры).

Чтение столбцов: **родитель** — узел ближе к корню (его значение
наследуется), **наследник** — узел глубже (его authored-значение
перебивает). Цепочки читаются слева направо от мелкого scope к
глубокому.

| Домен | Параметр | Класс родитель (мельче — отдаёт) | Класс наследник (глубже — перебивает) |
|---|---|---|---|
| locations | `economic_tier` (M1–M6) | `SettlementSkeleton` ← NL@SETTLEMENT ← `DistrictTemplateEntry` ← NL@DISTRICT ← `PlotLayoutTemplate` (tier→band→range) ← NL@BUILDING | NL@ROOM ← `RoomDef` (верх цепочки) |
| locations | `city_size` (M7) | `SettlementSkeleton` / NL@SETTLEMENT | — (одноуровневый: `levels=(SETTLEMENT,)`; глубже — чистое наследие контекста) |
| locations | `settlement_density` (M8) | `SettlementSkeleton`@SETTLEMENT | `DistrictTemplateEntry`@DISTRICT |
| locations | `wall_material` (M9) | NL `parent_wall_material` (settlement/building) | building NL / `RoomDef`-resolved, room NL |
| locations | `floor_material` (M9) | NL `parent_floor_material` | то же |
| locations | `dominant_material` (M10) | `SettlementSkeleton` / NL@SETTLEMENT | district-derived fallback (fold-кандидат) |
| locations | `race_mix` (отложен) | `SettlementDemographics`@SETTLEMENT (планируется) | district-уровень (multi-source) |
| locations | `climate anchor` (отложен) | world/settlement scalars | — (`levels` — подмножество) |
| factions (будущее) | loyalty/… | `FactionScope`: faction root | cell — своя ось |

## Особые строки

- **`city_size`** — наследника-класса нет сознательно: параметр
  объявлен на одном уровне, глубже — чистое наследие. Первый тест
  `Cascade.levels`.
- **`wall_material`/`floor_material`** — родитель и наследник могут
  быть одним классом (NL) на разных уровнях scope; parent/child — по
  уровню, не по типу.
- **`dominant_material`** — не pure first-non-null: fallback «из
  районов»/«по tier» — первая реальная проверка `Cascade.fold`.
- **`race_mix`** — проверит multi-source на одном уровне (не DTE).
- **`climate anchor`** — проверит `Cascade.levels` (подмножество).
