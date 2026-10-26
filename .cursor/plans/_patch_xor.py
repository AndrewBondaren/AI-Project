from pathlib import Path

path = Path(r"e:\AI Project\docs\tz_terrain_relief.md")
text = path.read_text(encoding="utf-8")
start = text.index("#### `ReliefSlopePolicy` + bands (R32)")
end = text.index("#### Features / attachments (R28)")

new = r'''#### Conditions mode XOR (R32)

На **каждый** `ReliefConditionTerrain` — **ровно три** case (`slope_none` / `slope_down` / `slope_up`).

Пусть `dz = z_road − z_adjacent`.

**Два режима шаблона/condition — ИЛИ, не И.** Внутри одного `ReliefTerrainCondition` (и рекомендуется во всём `ReliefTemplate`) выбран **один** режим. Смешение → **reject**.

| Режим | Ключ | Когда использовать |
|---|---|---|
| **A. Policy thresholds** | у каждого case поле `delta_z` (нет `bands`) | простой порог на down/up/none |
| **B. Bands** | у `slope_down`/`slope_up` — `bands[]`; у `slope_none` — `bands: []` (нет `delta_z`) | несколько интервалов Δz → разный kind внутри одного направления |

Detect режима: если любой case имеет непустой `bands` **или** явный `"bands": []` на none при отсутствии `delta_z` у всех → **B**; если у всех трёх case есть `delta_z` и нет `bands` → **A**; иначе → **reject**.

---

##### Mode A — `delta_z` на policy

| Policy | Применяется когда |
|---|---|
| `slope_none` | `abs(dz) <= delta_z` (`delta_z >= 0`) |
| `slope_down` | `dz >= delta_z` (`delta_z >= 1`) |
| `slope_up` | `−dz >= delta_z` (`delta_z >= 1`) |

```text
1. abs(dz) <= none.delta_z → slope_none
2. dz >= down.delta_z      → slope_down (+ case weights)
3. -dz >= up.delta_z       → slope_up
4. иначе → R21
```

```json
{
  "terrain": "plains",
  "cases": [
    { "policy": "slope_down", "delta_z": 1, "slope_weight": 0.8, "sheer_weight": 0.2 },
    { "policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0 },
    { "policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0 }
  ]
}
```

---

##### Mode B — bands (`delta_z_min` / `delta_z_max?`)

| Policy | Когда |
|---|---|
| `slope_none` | `abs(dz) < 1` (жёстко; `bands: []`, без `delta_z`) |
| `slope_down` | `dz >= 1` → match **band** по `dz` |
| `slope_up` | `−dz >= 1` → match **band** по `−dz` |

```text
ReliefDeltaBand
  delta_z_min: int          # required, >= 1
  delta_z_max: int | null   # optional; нет = без верхней границы
  slope_weight / sheer_weight  # R27
  shoulder_width_cells?, earthen_canal?, structure_refs?, …
```

Match inclusive; первый match в списке; overlap → **reject**; дыра → R21.

```text
1. abs(dz) < 1 → slope_none
2. dz >= 1     → band(down)
3. -dz >= 1    → band(up)
4. иначе       → R21
```

```json
{
  "policy": "slope_down",
  "bands": [
    { "delta_z_min": 1, "delta_z_max": 2, "slope_weight": 1.0, "sheer_weight": 0.0 },
    { "delta_z_min": 3, "slope_weight": 0.0, "sheer_weight": 1.0 }
  ]
}
```

---

**Запрещено смешивать в одном condition:**

```json
{ "policy": "slope_down", "delta_z": 2, "bands": [ … ] }  // reject
```

Один template: все `conditions[]` в **одном** режиме (A или B); разные terrain в одном файле — тот же режим.

'''

path.write_text(text[:start] + new + text[end:], encoding="utf-8")
print("ok")
