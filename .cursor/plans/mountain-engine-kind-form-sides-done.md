# Plan slice: Mountain engine (Kind / Form / Sides / Range) ✅ DONE

> **SoT:** [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) § **Mountain (engine)** + § **Surface mask domains**  
> **Принцип:** целевая архитектура целиком (M8); гора — **поддомен** `terrain_masks` (M0), не отдельный bake.

## Домен (общий) — declare подход A

```text
world.terrain_masks.default_mountains       # policy + defaults
world.terrain_masks.declared_mountains[]    # полные MountainSpec | MountainRangeSpec
→ category_enabled → Specs → engine → общий merge/paint
```

То же A для `declared_forests|plains|ravines[]` (свои `*Spec`).  
`NamedLocation` — поверх (храм на горе…), не declare-path.  
Убрать interim: geographic.mountain/peak → disk paint.

**Autoresolve A+D:** ridge field → `MountainRangeSpec` → peaks along spine → `MountainSpec[]` → engine.  
Placement knobs ≠ paint; Spec assemble из policy defaults.

Engine (Kind/Form/Sides/Range) = materialize **внутри** этого домена.

## Целевой pipeline

```text
FormGeometry → FormRaster → SideFill(per side) → KindElevation
```
| Слой | Выход |
|---|---|
| FormGeometry | vertices + `SideSector[]` |
| FormRaster | footprint light cells (Pineda / winding) |
| SideFill | `side_fraction` через `fill_sheer` \| `fill_slope` |
| KindElevation | `z = base + rise * fraction` + terrain/summit |

L0 и L2 — потребители **одного** контракта (M9).

## Form — два контракта (sum type)

```text
MountainForm =
  | MountainFormBySides { side_count: int >= 3 }
  | StarForm { rays: int >= 3; inner_ratio: float }      # POJO default
  | PeakForm { side_count: int >= 3 }                    # default часто 3
  | PlateauForm { side_count: int >= 3; hat_fraction: float }  # (0,1]
```

Утверждено: **A** — все variants с полными knobs с первого PR (не stub).
| OK | Forbidden |
|---|---|
| `StarForm(rays=5)` | `{ side_count: 5, geometry: STAR }` |
| `MountainFormBySides(side_count=6)` | внешний `side_count` рядом с Star |

Construct: N-gon / isotoxal star / peak / plateau knobs.  
Raster: Pineda (convex) / winding (star).

## Sides — отдельный fill на сторону

```text
side_index = argmin dist(p, edge_i)     # ownership B; tie → min i
t = dist_along_outward / sector_width   # только у выбранной стороны
SHEER → step(1 - ε)
SLOPE → 1 - smoothstep(t) | (1-t)^k
z = base + rise(kind) * profile(t)
```

Мягкость ≠ параметр form. Max-fraction / blend — запрещены.

## Defaults (утверждены)

| | Default |
|---|---|
| kind / form | ROCKY / BySides(6) |
| sides | all SLOPE |
| radius_m | 500 |
| Star | rays=5, inner_ratio=0.45 |
| Peak / Plateau | n=3 / n=6, hat=0.45 |
| SHEER ε | 1 light cell |
| SLOPE | smoothstep |
| Range sides | left+right (SLOPE); optional start/end |

## Range

Тот же pipeline: spine corridor + SideFill left/right (+ optional caps); peaks = полный `MountainSpec`.

## Порядок имплементации (по слоям архитектуры)

1. Types/POJO: Kind, Form sum-type, SideSpec, RangeSpec, FormGeometry, SideSector  
2. FormGeometry construct + FormRaster  
3. SideFill sheer/slope  
4. KindElevation + `apply_mountain_cell`  
5. Contributor thin wiring + tests  
6. Range corridor (тот же SideFill)

Stub только на границе caller (policy defaults), не внутри pipeline.
