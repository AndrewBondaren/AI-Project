---
name: tz-terrain-relief-g9s-technical-debt
description: "Независимый аудит GEO-1 G9-S: производительность и границы authored presence."
metadata:
  node_type: memory
  type: project
---

# GEO-1 G9-S — технический долг

**Тип:** living registry замечаний к коду, не generate SoT. **Срез:** master, 2026-10-29; статическое ревью, без запуска тестов и профилирования.  
**Основной реестр:** [tz_terrain_relief_technical_debt.md](./tz_terrain_relief_technical_debt.md) (TD-1–TD-9).  
**Активация:** проверить перед G10-A; не объявлять текущей production-регрессией.

| ID | Приоритет | Статус |
|---|---|---|
| RELIEF-TD-10 | P2 | Подтверждённый кодом избыточный обход, без замеров |
| RELIEF-TD-11 | P2 candidate | Гипотеза, требует профилирования |
| RELIEF-TD-12 | P3 | Архитектурный долг, не доказанный баг |

## RELIEF-TD-10 — G9-S: повторная полная растеризация declared region на каждом тайле

**Severity:** medium. **Status:** open. **P:** P2. **Обнаружено:** 2026-10-29, независимое статическое ревью master.

**Доказательство:** `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py:102-133`: `SupportSources.terrain_at()` кэширует `_tiles[tile]`, но при промахе по кэшу для каждого `ResolvedRegion` вызывает `rasterize_fine(region.spec.shape, self.world, context)` без scope, а затем отбрасывает координаты за пределами bbox тайла. `backend/app/application/worldData/masks/regionRasterizer.py`: `rasterize_fine()` проходит `shape.bbox()` целиком; в отличие от `rasterize_claim_fine(..., scope=bbox)`, ограничения выборки нет. Для региона, пересекающего N тайлов, возможны N полных обходов bbox. Это **подтверждённый кодом избыточный обход**, но величина замедления не измерена.

**Влияние:** масштабирование G9-S support при больших регионах и множестве shore-клеток; G9-S пока изолирован до G10-A, поэтому это долг **до production-активации**, а не доказанная текущая регрессия.

**Целевое решение:** дать общему rasterizer контракт ограниченной выборки по bbox тайла с сохранением исходной семантики membership/density/topology, включая wrapped/reflected координаты. Не дублировать растеризацию в `SupportSources`. Альтернатива — существующий эквивалентный пространственный индекс, если он обеспечивает ту же семантику. Сравнить результаты с текущим полным проходом.

**Критерии закрытия:** тесты эквивалентности полной и ограниченной выборки для planar/wrapped и граничных регионов; тест на отсутствие повторного полного обхода при нескольких тайлах; замер на крупном регионе с множеством тайлов; отсутствие изменений в terrain selection.

---

## RELIEF-TD-11 — G9-S: стоимость перебора mountain layout для каждой shore-клетки

**Severity:** medium (предварительно). **Status:** open, требует профилирования. **P:** P2 candidate. **Обнаружено:** 2026-10-29, независимое статическое ревью master.

**Доказательство:** `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py:132-139` вызывает `observe_sides(layout, cell, ...)` для каждой shore-клетки в surface extent. `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/geometry.py`: `observe_sides()` перебирает все `layout.entries` и топологические образы, затем вызывает геометрические kernels. Прямой пространственный prefilter в просмотренном пути не найден. Это **гипотеза о существенном runtime cost**, не измеренный дефект.

**Влияние:** рост затрат на G9-S при большом mountain layout и числе shore-клеток; до G10-A не считать production-регрессией.

**Целевое решение:** сначала профиль на репрезентативных размерах; при подтверждении — spatial candidate selection/footprint в общем владельце геометрии с сохранением топологии и правил winner/fraction. Не создавать новый слой кэша, пока не проверен существующий planning/cache.

**Критерии закрытия:** измерение количества проверок и времени на сетках с разным числом гор и shore-клеток; эквивалентность выбранного `SideObservation` до/после оптимизации; решение о необходимости оптимизации по результатам профиля.

---

## RELIEF-TD-12 — G9-S: реконструкция Pydantic authored presence в application-layer

**Severity:** low. **Status:** open (architecture). **P:** P3. **Обнаружено:** 2026-10-29, независимое статическое ревью master.

**Доказательство:** `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py:51-64` создаёт `LandcoverTerrainPolicy` через `model_construct(_fields_set=fields, ...)`, добавляя `hills` по `landcover.terrain_policy_hills_authored`, затем вызывает `apply_to()`. `LandcoverTerrainPolicy.apply_to()` использует `self.has_authored_hills` (`model_fields_set`) при том, что `registry_hills_authored` передаётся явно. Слой реализации вынужден восстанавливать внутреннее состояние POJO ради применения политики. **Функциональный дефект не доказан**.

**Влияние:** неочевидный контракт и риск расхождения семантики authored presence при эволюции модели/codec; смежно с RELIEF-TD-9, но относится к потреблению уже captured facts.

**Целевое решение:** передавать явно оба authored-факта в операцию применения политики (или использовать типизированный captured contract), без `model_construct(_fields_set=...)`. Не создавать отдельный адаптер/домен без необходимости; сохранить существующий приоритет registry hills vs landcover override.

**Критерии закрытия:** отсутствие ручного восстановления `model_fields_set` в `SupportSources`; тесты случаев hills absent / explicit null / concrete policy и приоритета registry; неизменность результатов после canonical encode/decode.

---
