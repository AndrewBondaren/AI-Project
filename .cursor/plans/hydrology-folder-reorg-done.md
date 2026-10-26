# План: реорганизация hydrology layout ✅ DONE

## Решение по корню

**`generators/hydrology/`** — peer [`generators/climate/`](backend/app/application/worldData/generators/climate/), не подпапка terrain. Hydrology — отдельный pure-generator домен (carve heightmap + cell roles), как climate; вложенность под `terrain/` размывала границы.

`dataModel/hydrology/` **не трогаем** (уже нормально).

## Целевое дерево

```
generators/hydrology/
  __init__.py
  hydrologyGeneratorService.py    # facade only
  types.py
  load/
    loadHydrologyFromWorld.py
    loadDeclaredHydrology.py
    loadConnectionGraph.py
    buildHydrologyMasterInput.py
    hydrologyLocations.py
    declaredEdges.py
    resolveHydrologyBands.py
    resolveRiverTypeClassify.py
    hydrologyAutoresolvePolicy.py
  basins/
    seaLevelPolicy.py
    seaBasinGenerator.py
    oceanBasinGenerator.py
    lakeBasinGenerator.py
    lakeSpecs.py
    basinKindResolver.py
    coastalLandformClassifier.py
  rivers/
    riverNetworkPlanner.py
    riverBedCarver.py
    riverSpecs.py
    classifyRiverSegments.py
    resolveDeclaredRiverPath.py
    riverConnectionEmit.py
  shore/
    shoreProfile.py
    deepeningBandCarver.py
    meterHydrologyIndex.py
    heightmapSurfaceCells.py
  geom/
    polylineRasterize.py
    polygonInterior.py
    smoothRiverPolyline.py
  autoresolve/
    proceduralSeaAutoresolve.py
    proceduralLakeAutoresolve.py
    proceduralRiverAutoresolve.py
```

**Rename при переносе (только имена файлов, публичные символы те же):**
- `classifyRiverSegments.py` остаётся; слияние с `resolveRiverTypeClassify` — **не в этом PR**.
- TZ упоминал `riverTypeClassifier.py` / `applyHydrologyMetadata.py` — в коде других имён; в ТЗ синхронизировать фактические пути.

## Инварианты

- Поведение generators **байт-в-байт** (только path/import).
- Внешние call sites: те же символы, новый package path.
- Compatibility shims: **не** оставлять пустые re-export в `terrain/hydrology/` (чистый cutover); один PR, все imports обновлены.

## Порядок работ

1. Создать дерево `generators/hydrology/{load,basins,rivers,shore,geom,autoresolve}/` + корневые файлы.
2. `git mv` файлов по таблице выше.
3. Rewrite imports внутри hydrology.
4. Rewrite внешних imports (~40 файлов): pack/materialization, terrain passes, `map.py`, tests, smoke.
5. Удалить пустой `generators/terrain/hydrology/`.
6. Обновить `docs/tz_terrain_hydrology.md` § «Расположение кода (target)».
7. Проверка: `python -m unittest` hydrology tests; импорт facade из нового пути.

## Не в scope

- Логика carve / scopes / autoresolve
- Слияние дублирующих classify-модулей
- Перестройка `dataModel/hydrology/`
- Climate pack smoke

## Todos

- [x] git mv: flat terrain/hydrology → generators/hydrology/{load,basins,rivers,shore,geom,autoresolve}
- [x] Rewrite internal + external imports to new package paths
- [x] Remove empty terrain/hydrology; update tz_terrain_hydrology § layout
- [x] Run hydrology unit tests + import smoke
