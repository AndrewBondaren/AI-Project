# POJO `EntryPoint` — убрать raw-dict wire и хардкоды — **DONE 2026-10-01**

**Источник:** правило `dataModel-no-hardcode.mdc` — `entry_point`/`back_entry_point` на комнате сейчас проходят как `dict` от `room_def` до билдера; каждый потребитель читает ключи строками и дублирует defaults. ТЗ-контракт: [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §3.6 (поля), §286–297 (perimeter-правило), §3.10/§493 (проём), §1536–1555 (направленное размещение).

**Статус: все шаги и срезы сданы 2026-10-01** (working tree, uncommitted).
E1–E3, 6.1–6.11 имплементированы; **E4 закрыт фактом**: docs sync выполнен
посрезово (ТЗ §495–532 door_height/формула, §186–188 ratio/max, §282/§3.10–3.11
wall_openings, §673–675 + staircase §2 embed, §1667+ attach_wall any,
§286 perimeter-форсинг), validator sweep — идентичные A/B и стабильные 8 ERROR
на всех срезах 6.6–6.11. Тот же working tree содержит WIP шага 3c основного плана
(`structureOrientation.py`, `debugStructureRotations.py`, `test_structure_orientation.py`,
baseline-тесты лестниц, `debug.py`) — с этим планом пересекается только чтением
`entry.*` (уже типизировано). Незакрытые находки вынесены в
`.cursor/plans/structure-technical-debt.md`.

## 1. Инвентарь raw-чтений и хардкодов (факт 2026-09-29)

| Место | Что читает | Хардкод / проблема |
|---|---|---|
| `roomFactory.py:176-177` | `room_def.get("entry_point")` / `.get("back_entry_point")` → `_RoomInstance` | passthrough raw dict |
| `roomInstance.py:47-48` | `entry_point: dict \| None`, `back_entry_point: dict \| None` | тип `dict` вместо POJO |
| `layoutEngine.py:132` | `if r.entry_point:` (BFS start) | только truthiness — ок |
| `passages/builder.py:275-288` | truthiness → `_build_entry_point(room, room.entry_point, …)` | сигнатура `ep: dict` |
| `passages/entry.py:31` | `ep.get("wall")` → `parse_facing_or_default(default=SOUTH)` | дефолт SOUTH — не из ТЗ |
| `passages/entry.py:40` | `ep.get("width", 1)` | литерал default 1 |
| `passages/entry.py:41` | `ep.get("frame_material") or room.wall_material` | fallback в коде (ок — runtime), ключ строкой |
| `passages/entry.py:44` | `ep.get("height", passage_height)` | **ключ `height` — в ТЗ поле `door_height`; wire-ключ несуществующий → явная `door_height` шаблона игнорируется (латентный баг)** |
| `passages/entry.py:60` | `ep.get("passage_type")` → `from_wire(default=MAIN_ENTRANCE)` | дефолт MAIN_ENTRANCE — для `back_entry_point` семантически неверен |
| `structureOrientation.py:84-95` (untracked, WIP шага 3c) | `entry.get("passage_type")` + `entry.get("wall")` | **копия тех же двух хардкодов** — обязательно обновить |

Не читаются нигде (`grep` пустой): `access_type`, `panel_material`, `door_height`, `door_height_ratio`, `door_height_max`. Переносятся в POJO по ТЗ §3.6 как wire-контракт; потребление (`access_type` авто-резолв ассемблером, `panel_material` = открытый проём) — отдельные задачи, не этот план.

## 2. Целевая модель

```python
# dataModel/structure/enums/entryAccessType.py — НОВЫЙ
class EntryAccessType(StrEnum):
    AUTO = "auto"; NONE = "none"; STEPS = "steps"; PORCH = "porch"

# dataModel/structure/room/entryPoint.py — НОВЫЙ (рядом с roomTypeEntry.py)
class EntryPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    wall:           StrictOnWire[Facing]                      # ТЗ §3.6: только cardinals — field_validator через CARDINAL_FACINGS
    passage_type:   StrictEnumOnWire[PassageType]             # validator: только MAIN_ENTRANCE | SERVICE_ENTRANCE
    width:          DefaultOnWire[int] = 1                    # ge=1 (constrained_field); 2 = двустворчатая, 3+ = ворота
    door_height:    DefaultOnWire[int | None] = None          # wire-ключ door_height; авто-резолв — runtime (нужны z_height, world.default_passage_height)
    frame_material: DefaultOnWire[str | None] = None          # fallback wall_material комнаты — остаётся в consumer
    panel_material: DefaultOnWire[str | None] = None          # null = открытый проём (контракт есть, потребителя нет)
    access_type:    DefaultEnumOnWire[EntryAccessType] = EntryAccessType.AUTO
```

**Решения по контракту (требуют ок мастера):**

- `wall` — **StrictOnWire** (обязателен): ТЗ §3.6 не помечает optional; все 13 stdlib-фикстур задают явно. Убирает оба `default=Facing.SOUTH`. Альтернатива — DefaultOnWire SOUTH, если мастер хочет tolerant-вход.
- `passage_type` — **StrictEnumOnWire**, валидатор ограничивает {`main_entrance`, `service_entrance`}: дефолт невозможен корректно для обоих полей (entry→front, back→service); фикстуры задают всегда. Убирает оба `default=MAIN_ENTRANCE`.
- `door_height` — wire-ключ по ТЗ; чтение `ep.get("height")` заменяется на `ep.door_height` (фикс бага, §1). Авто-резолв формулы (`ratio`/`max` — §4.2) в POJO не входит: нужны runtime-величины.
- `levels[].rooms[]` остаются `list[dict]` (POJO-D-16) — POJO парсится **на границе**: `StructureTemplate` model_validator (import-strict, как purpose-валидация шага 5a) + повторный `model_validate` в `roomFactory` (ValidationError → `GenerationError`).

## 3. Шаги

### Шаг E1 — dataModel: enum + POJO + import-валидация

| | |
|---|---|
| Цель | Контракт `EntryPoint` существует; `StructureTemplate` реджектит битый wire на загрузке |
| ТЗ | `tz_building_generator.md` §3.6 (поля и defaults), §280–281 (entry/front ↔ service) |
| Файлы | новые `dataModel/structure/room/entryPoint.py`, `dataModel/structure/enums/entryAccessType.py`; `structureTemplate.py` — model_validator: пройти `levels[].rooms[]`, `EntryPoint.model_validate` на `entry_point`/`back_entry_point` (ошибка → ValidationError с `room_id`); `dataModel/structure/room/__init__.py` — экспорт |
| Контракт | как §2; `entry_point` и `back_entry_point` — один и тот же POJO; `perimeter_required`-форсинг (ТЗ §286) — **не** в POJO комнаты (room остаётся dict), переносится в E2 на фабрику |
| Проверка | `python -m unittest tests.test_structure_template` + новый `tests/test_entry_point.py` (cardinal-only `wall`, `width=0` → ошибка, `passage_type=doorway` → ошибка, omit `wall`/`passage_type` → ошибка, `access_type` default `auto`, unknown ключ при `extra="forbid"` → ошибка); все 13 stdlib-структур валидируются |
| Done | **Сделано 2026-09-29** (working tree, uncommitted): `entryPoint.py` — `wall` StrictOnWire + cardinal-валидатор, `passage_type` StrictEnumOnWire + валидатор {main_entrance, service_entrance}, `width` ge=1, `access_type` AUTO; `entryAccessType.py`; `StructureTemplate._validate_entry_points` (model_validator, ошибка с `room_id`); экспорт в `room/__init__.py`; `tests/test_entry_point.py` зелёный; 13 stdlib-структур проходят |

### Шаг E2 — runtime: типизация `_RoomInstance` + потребители

| | |
|---|---|
| Цель | `_RoomInstance.entry_point/back_entry_point: EntryPoint \| None`; ни одного `ep.get(...)`/строкового ключа в потребителях |
| ТЗ | `tz_building_generator.md` §3.6, §286–297 (форсинг perimeter), §493 (центрирование — не меняется) |
| Файлы | `room/roomInstance.py` (типы полей), `room/roomFactory.py` (`EntryPoint.model_validate` обоих полей; `perimeter_required` = `room_def.get("perimeter_required", False) or (entry_point or back_entry_point)` — ТЗ §289), `passages/entry.py` (`ep.wall`, `ep.width`, `ep.frame_material`, `ep.door_height`, `ep.passage_type`; убрать `parse_facing_or_default(...,SOUTH)`, `get("width",1)`, `from_wire(default=MAIN_ENTRANCE)`, ключ `height`→`door_height`), `passages/builder.py` (`ep: EntryPoint`), `structureOrientation.py` (`entry.passage_type`, `entry.wall` — **координация: файл untracked WIP шага 3c**, править совместно с его автором или после его коммита), `layoutEngine.py` — без правок (truthiness) |
| Контракт | `_build_entry_point(room, ep: EntryPoint, …)`; `entry_orientation` читает typed-поля; ValidationError из factory → `GenerationError` (шаблон прошёл import-валидацию, runtime-дубль — защита) |
| Проверка | `python -m unittest tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes`; grep `ep\.get\|entry\.get\|\.get("wall")\|\.get("passage_type")` по `generators/` — пусто; generate×2 детерминизм не сломан |
| Done | **Сделано 2026-09-29** (working tree, uncommitted): `_RoomInstance` типизирован; `roomFactory` — `EntryPoint.model_validate` → `GenerationError` + perimeter-форсинг `or entry/back declared`; `entry.py` читает `ep.wall/width/frame_material/door_height/passage_type` без `.get` и без SOUTH/MAIN_ENTRANCE-дефолтов; `builder.py` прокидывает `template`; `structureOrientation.py` (WIP 3c) обновлён на `entry.passage_type`/`entry.wall`; `tests/test_entry_point_runtime.py`; grep `ep.get`/`entry.get` по entry_point-потребителям чист (остатки `.get` — словари `conn`/`sc_entry` лестниц/connections, другой домен POJO-D-16) |

### Шаг E3 — авто-резолв `door_height` по ТЗ-формуле (решение мастера 2026-09-29)

| | |
|---|---|
| Цель | Полный контракт §3.6: `door_height_ratio`/`door_height_max` — поля шаблона; авто-резолв высоты проёма по формуле ТЗ; нижний предел `world.default_passage_height` |
| ТЗ | `tz_building_generator.md` §3.6 «Авто-резолв `door_height`» (формула + примеры), валидация `door_height >= default_passage_height` и `< z_height` |
| Файлы | `dataModel/structure/building/structureTemplate.py` — `door_height_ratio: DefaultOnWire[float] = 0.75` (gt=0, le=1), `door_height_max: DefaultOnWire[int] = 5` (ge=1); `passages/entry.py` — резолв: explicit `ep.door_height` → `max(door_height, world.default_passage_height)`; иначе `z_height <= 3` → `z_height - 1`, иначе `min(floor(z_height * ratio), max)` → `max(., passage_height)`; `passages/builder.py` — прокинуть `ratio`/`max` (или `template`) в `_build_entry_point`; `builder.py:52` — литерал `else 2` → дефолт из POJO мира (смежный хардкод, тот же резолв-путь) |
| Контракт | `z_height` — высота уровня/комнаты проёма (`room.z_height`); нарушение `door_height < z_height` / `< default_passage_height` → `GenerationError` с `room_id` и uid структуры (runtime — нужен world); импорт-тайм частичная проверка возможна, если `z_height` уровня в шаблоне — решать при имплементации |
| Проверка | `python -m unittest tests.test_entry_point tests.test_building_assembler` + новые кейсы: явный `door_height` выше/ниже предела, `z=2/3/4/6/7/10` против таблицы примеров ТЗ (ratio=0.75, max=5, passage=2 → 2/2/3/4/5/5), `door_height >= z_height` → ошибка |
| Done | **Сделано 2026-09-29** (working tree, uncommitted): `StructureTemplate` + `door_height_ratio`/`door_height_max` с constraints и `DEFAULT_*` константами; `_resolve_entry_height` в `entry.py` — формула ТЗ + `GenerationError` при `height ∉ [passage_height, z_height)` с uid и room_id; `builder.py:52` — `else World.default_passage_height` вместо литерала `2`; 110 тестов зелёные |

### Шаг E4 — docs sync + регрессия валидаторов

| | |
|---|---|
| Цель | ТЗ фиксирует `door_height` (ключ `height` признан багом, удалён); прогон валидаторов чист по entry-части |
| ТЗ | `tz_building_generator.md` §3.6 — пометка: wire-ключ `door_height`, поля `door_height_ratio`/`door_height_max` на шаблоне (E3); §286 — форсинг реализован в roomFactory |
| Файлы | `docs/tz_building_generator.md`; при необходимости заметка в `tz_city_generation_technical_debt.md` |
| Проверка | sweep generate по 13 stdlib-структурам с capture `logger.error` — entry/door-проверки не добавились к §7 п.11 основного плана |
| Done | docs sync; sweep не хуже baseline 36 ERROR (те, что в §7 п.11) |

## 4. Найденные расхождения и открытые вопросы

1. **Баг wire-ключа (E2 чинит):** код читает `ep.get("height")`, ТЗ и смысл — `door_height`. Фикстуры ключа не задают → регрессии нет, фикс безопасен.
2. **Авто-резолв `door_height` не реализован:** ТЗ-формула требует `template.door_height_ratio` (default 0.75) и `door_height_max` (default 5) — полей на `StructureTemplate` нет. **Решено мастером 2026-09-29:** отдельным шагом E3 (поля POJO + формула + валидация).
3. **`perimeter_required` форсинг (ТЗ §286–297) в коде не найден** — `roomFactory:174` читает только явное поле. В E2 добавлено `or entry/back declared` по букве ТЗ; если поведение уже достигается иначе — убрать из шага.
4. **Направленное размещение по `entry_point.wall` (ТЗ §1536–1555) в `layoutEngine` не найдено** — комната не ставится так, чтобы указанная стена оказалась периметральной; вход режется там, где комната встала. Это объясняет часть критерия «дверь не на стороне улицы». Вне scope этого плана (layout engine, не wire-контракт) — кандидат в техдолг `tz_building_generator.md`.
5. **`structureOrientation.py` — untracked WIP шага 3c** основного плана: его `entry.get(...)` уже повторяют хардкоды. Порядок: либо E2 правит его вместе с автором 3c, либо E2 ждёт коммита 3c — решить при старте.
6. **`builder.py:52` `passage_height = world.default_passage_height if world is not None else 2`** — литерал `2` вместо fallback POJO мира (смежный хардкод `dataModel-no-hardcode`); **входит в E3** (тот же резолв-путь высоты).

## 5. Blast radius

`dataModel/structure/room/` (+2 файла), `structureTemplate.py` (validator), `room/roomInstance.py`, `room/roomFactory.py`, `passages/entry.py`, `passages/builder.py`, `structureOrientation.py`. Тесты: `test_structure_template`, новый `test_entry_point`, регресс — building/area/deterministic-ids/three-axes. API/SQL/Fixtures не трогаются.

## 6. Следующие срезы POJO (инвентарь sweep 2026-09-29)

`entry_point` закрыт; тот же паттерн raw-dict + литералы остаётся в трёх соседних доменах `StructureTemplate` (`list[dict]` по POJO-D-16) и в изолированных дефолтах. Каждая строка — отдельный шаг при планировании; ниже — только фиксация фактов, не очередь.

### 6.1 `connections[]` → POJO `RoomConnection`

**Статус:** имплементирован 2026-09-29 (working tree, uncommitted). `RoomConnection` в `dataModel/structure/building/` (frozen, extra=forbid; `passage_type` — fallback `doorway` на любое значение вне {doorway, archway} (вкл. staircase; решение мастера 2026-09-29, не reject); ERROR-лог — на границе `_resolve_connections` (logger `generators.structure.*` → generation-транскрипт + core/runtime; POJO не логирует — `app.dataModel.*` вне всех sink-route'ов); `width` per-kind default 1/2 в POJO; `required`, `panel_material`, `railing_material` — wire-контракт ТЗ); `StructureTemplate._validate_connections` import-strict; `StructureGeneratorService._resolve_connections` → `GenerationError`; typed flow в layout/cells/passages; synth conns (shaft↔room) строятся как `RoomConnection`. Баги §6.5: `door_height` ключ починен; archway frame ← `wall_material`; old-schema staircase-branch удалён (staircase-conn теперь коерсится в doorway на границе — ветка мёртвая). 128 тестов + `test_room_connection` зелёные; sweep 13 stdlib = 8 ERROR (baseline E4); детерминизм ×2 ок. Открыто мастеру: auto-резолв `door_height` (ratio/max) для connections не введён — TZ §3.7 требует «тот же резолв, что entry_point», но это меняет геометрию высоких комнат (см. отчёт).

Поля по ТЗ §3.7 (таблица ~§594–600): `from_room`, `to_room`, `passage_type` (doorway/archway; `staircase` **запрещён** — reject, не default), `door_height`, `frame_material` (fallback `wall_material` from_room), `step_material` (fallback `floor_material`), `width`.

| Место | Хардкод / проблема |
|---|---|
| `doorway.py:41` | `conn.get("height", passage_height)` — **тот же баг wire-ключа, что чинил E2**: ТЗ-поле `door_height` молча игнорируется |
| `doorway.py:34` | `conn.get("width", 1)` — литерал default 1 |
| `archway.py:59` | `conn.get("width", 2)` — литерал default 2 (другой по типу — в POJO per-kind) |
| `builder.py:77`, `doorway.py:58` | `from_wire(default=DOORWAY)` — дубль дефолта; `staircase` в wire глотается вместо reject (ТЗ §587) |
| `archway.py:64` | `or fr.floor_material` — **подозрение на баг**: ТЗ §606 `frame_material ?? wall_material`, у арки fallback на floor |
| `builder.py:245` | `conn.get("step_material") or floor_material` — семантика по ТЗ §608 верна, чтение raw |
| `builder.py:231-232` | `room_z_offsets.get(room, 0)` — silent `0` для неизвестного room_id (legacy-ветка staircase-conns; далее :241 `KeyError` — защита частичная) |
| `archway.py:73`, `corridorTrimmer.py:166`, `staircase/builder.py:51,86`, `service:519` | `get("…", "?")`/`"staircase"` — placeholder-дефолты в лог-лейблах |
| `layoutEngine.py:122,136-137` | `conn.get("passage_type")`, `conn.get("to_room")`/`from_room` |

### 6.2 `staircases[]` → POJO `StaircaseSpec` (+ vertical-ladder spec)

**Статус:** имплементирован 2026-09-30 (working tree, uncommitted). `StaircaseSpec` + `ShaftSize` в `dataModel/structure/building/staircaseSpec.py` (frozen, extra=forbid; `staircase_type` — `parse_template` с `trapdoor`-алиасом; `facing` — только cardinal; `embed_at` — intercardinal/`center`; auto-id `staircase_{from}_{to}` по `stops` — один резолв вместо 6 местных дефолтов `"staircase"`/`"?"`/`conn_label`; `_flag_compat`: `outside` требует `has_walls`, `in_a_room` ⊥ `outside`; `embed_in`/`embed_at` — accept+carry, позиционная семантика зафиксирована в staircase §2 с TODO, `EmbeddedShaftPlacer` по-прежнему stub). `has_walls` default — `False` = status quo кода (ТЗ декларирует `true`; решение мастера — не менять поведение). `StructureTemplate.staircases` остаётся `list[dict]`; `_validate_staircases` import-strict, wire не мутирует. `StructureGeneratorService._resolve_staircases` → `GenerationError` на runtime-границе. Typed flow: `_instantiate_rooms`/`_layout_rooms`/`_run_passages`/`_build_synth_conns`/`_place_level_shafts`/`_propagate_trapdoor_starts`/`_staircase_layout_order`, `instantiate_shaft_rooms`, `make_shaft_placer`, `trim_corridor_rooms`, `build_passages`, `build_staircase` (dual-schema path удалён — staircase-conn в `connections[]` коерсится в doorway на границе 6.1, ветка мёртвая), `StaircaseBuilder.sc_entry` типизирован, `uShape`/`verticalLadder` читают поля spec. Баг §6.5 п.3 починен: `verticalLadderValidator` берёт `World.default_passage_height` вместо литерала `2`. Новый `tests/test_staircase_spec` (12 тестов: defaults/auto-id, type parse, size-формы, flag-compat, roundtrip+immutability, import/runtime boundary, sweep всех 13 stdlib). 145 тестов зелёные; A/B-fingerprint всех 13 stdlib HEAD vs slice — **бит-в-бит идентичны** (cells+passages hash); детерминизм ×2 ок.

Поля по ТЗ §3.7b и `tz_staircase_generation.md`: `staircase_id`, `staircase_type` (`StaircaseType.parse_template`), `stops`, `step_material`, `on_the_edge`, `in_a_room`, `outside`, `size`, `facing`; ladder: `is_movable`, `has_trapdoor`, `near_wall`, `has_walls`, `open_wall_shaft`, `closed_exit`.

| Место | Хардкод / проблема |
|---|---|
| `builder.py:126`, `shaftFactory.py:67`, `corridorTrimmer.py:166`, `service:446,476,519`, `uShape.py:462` | `staircase_id` → `"staircase"`/`"?"`/`or conn_label` — 6 разных дефолтов одного поля |
| `verticalLadder.py:81-88` | 7 bool/enum-полей `.get(..., False/None)` |
| `verticalLadderValidator.py:132` | `kwargs.get("passage_height", 2)` — **литерал `2`, дубль `default_passage_height` мира** (как `builder.py:52` до E3) |
| `shaftFactory.py:35-43` | `size` sub-dict: `size_type`, `depth_range` fallback `size["width_range"]` |
| `shaftPlacer.py:139-140` | `in_a_room`/`outside` → False |
| `builder.py:206`, `service:444,474,517` | `sc.get("staircase_type")`, `sc.get("stops", [])`, `sc.get("on_the_edge", False)` |

### 6.3 `rooms[]` / `levels[]` → `RoomDef` / `LevelDef` / `SizeSpec` / `ShapeParams`

**Статус 2026-09-30:** реализован в working tree. На `StructureTemplate` сохранён
raw wire (`list[dict]`); import-валидация и повторная runtime-валидация дают typed
уровни/комнаты. Фабрика, size/shape resolver и сервис читают поля POJO;
`layoutEngine` больше не содержит `attach_wall or "both"`.
`attach_wall` — `StrictEnumOnWire[AttachWall]`, отсутствующее/битое → BOTH
(решение мастера в чате, заменяет прежний import-required); подмена заданного
значения и отсутствие у комнаты с `attach_to` → централизованный ERROR на
границе генератора. POJO сохраняет отметку, не логирует. Битые runtime-ссылки
`attach_to` → skip + ERROR (включая зависимые прикрепления); import — reject.
Диапазоны размеров валидируются; L/T params обязательны для любого элемента
массива shapes; stem max < width min. EntryPoint и purpose-потребитель переиспользованы.
`count=1` и вывод формы при omitted shape_type сохранены; z_height=0/битое →
наследование template default + ERROR, None/omit — тихо. Шаблоны не мутируются.

**Оставлено вне среза:** `attach_wall=any` — исправлен отдельным срезом §6.6;
host-not-placed пишет WARNING; смешанный массив shapes с L/T всё ещё
не резолвит shape_params выбранной формы (изменение RNG/геометрии — отдельный фикс).
Связность `stops`/`embed_in` остаётся доменом сданного staircase-среза.
Изолированные facing defaults §6.4 не менялись.

**Проверки:** 161 тест — OK (1 существующий expected failure), включая 16 новых
проверок среза и запись fallback в настоящий generation-транскрипт; compileall
и diff --check чистые. A/B sha256(cells+passages) всех 13 stdlib совпадают,
generate×2 детерминирован, те же 8 ERROR с теми же сообщениями. Sweep raw-get
по room/level-полям в generators/structure пуст. Результаты:
`.local/rooms_pojo_before.json`, `.local/rooms_pojo_after.json`,
`.local/rooms_pojo_final_tests.log`. Backend не запускался, коммит не создавался.

Больший scope: `room_def` целиком (`room_id`, `display_name`, `room_type`, `is_public`, `is_forbidden`, `required`, `count`, `economic_tier`, `attach_to`, `attach_wall`, `perimeter_required`, `underground_fallback`, `staircase_type`, `facing`, `size`, `shape_params`, `entry_point`, `back_entry_point`, `purpose`) и `level_def` (`z_offset`, `z_height`, `isolated`, `access_mechanic`, `rooms`, `purpose`).

| Место | Хардкод / проблема |
|---|---|
| `roomFactory.py:71,74` | `depth_range`/`z_range` → `[3,3]` литералы |
| `roomFactory.py:95-107` | `arm_*_range`/`stem_width_range` → `[2,3]`, `arm_corner`/`stem_wall` → `"any"` |
| `shapeResolver.py:18` | `width_range` → `[1,1]` |
| `roomFactory.py:150` | `count` → `1` |
| `service:101,110` | `level_def.get("z_height") or default` — `or` проглатывает falsy (`0` легален?) |
| `service:132-133` | `isolated` → False, `access_mechanic` → `[]` |
| `layoutEngine.py:384` | `attach_wall or "both"` — строковый литерал режима |

### 6.4 Изолированные facing-дефолты (не dict-домены)

**Статус 2026-09-30: реализован, решение мастера — продолжать генерацию с ERROR.**
`shared._exterior_cells_on_wall` принимает `Facing` из валидированного EntryPoint,
мёртвый SOUTH удалён. NORTH в `passages/builder.py` сохранён как внутренняя
конвенция N/S-оси для расчёта arch width при optional shaft facing; обоснование
добавлено в код и `tz_staircase_generation.md`. Двойной silent SOUTH в shapes
заменён на `ResolvedStemWall` (StrictEnumOnWire[Facing], cardinal, SOUTH fallback,
пометка подмены без лога в dataModel). Генератор пишет ERROR; фабрика разрешает
его один раз до повторных footprint-запросов. Прямые вызовы геометрии тоже защищены.
Смешанные L/T-массивы не исправлялись; RNG не добавлялся.
Проверки: 166 тестов OK (1 существующий expected failure), compileall и diff --check
чистые; A/B всех 13 stdlib идентичен, те же 8 ERROR, generate×2 детерминирован.
В grep остался только обоснованный NORTH для оси арки шахты. Новые 5 тестов
проверяют кардиналы, деградацию, прямой dispatch и централизованный транскрипт.
Артефакты: `.local/facing_defaults_{before,after}.json`, `.local/facing_defaults_tests.log`.

| Место | Дефолт | Контекст |
|---|---|---|
| `builder.py:154` | `parse_facing_or_default(_shaft_ref.facing, NORTH)` | shaft reference |
| `shared.py:50` | `parse_facing_or_default(direction, SOUTH)` | passage direction |
| `shapes.py:108`, `shapes.py:168` | `stem_wall` → SOUTH | T-shape stem |

Три молчаливых дефолта направления — проверить по ТЗ, обязательно ли поле на wire (тогда StrictOnWire) или дефолт легитимен (тогда в POJO-поле).

### 6.5 Подтверждённые баги из sweep (чинить в срезах 6.1–6.2)

1. **`doorway.py:41`** — `conn.get("height")` вместо `door_height`: явная высота проёма связи игнорируется (тот же класс бага, что `entry.py` до E2).
2. **`archway.py:64`** — frame ← `fr.floor_material`; ТЗ §606 — `wall_material`. Подтвердить/чинить в 6.1.
3. **`verticalLadderValidator.py:132`** — `passage_height` default литерал `2` вместо дефолта мира. Чинить в 6.2.
4. `room_z_offsets.get(…, 0)` в legacy-ветке `builder.py:231` — silent-ноль; в 6.1 решить reject vs keep (ветка уходит при удалении старой схемы).

### 6.6 `attach_wall: "any"` — резолв по позиции лестницы (дизайн согласован 2026-09-30)

**Статус 2026-10-01: реализован в working tree.** `_layout_mode_b` выбирает одну
сторону для `ANY` на corridor по A1–A5; staircases и building_uid передаются из
сервиса через `layout_level`. Учитываются stops и наличие шахты того же staircase_id
на z_offset коридора (не требуется placed, шахты ставятся позже). Occupied — union;
проекция на ось через `GRID_OUTWARD_DELTA`; единственная свободная сторона выбирается
без RNG, иначе используется отдельный `scoped_rng`. BOTH, явные стороны и ANY
некоридорного хоста сохранены. StaircaseSpec/shaftPlacer не менялись.

**Баг:** ТЗ `tz_building_generator.md` §3.4-модал-B (стр. ~1667) + решённый вопрос §15
требуют: «any» = комнаты на стороне, **противоположной лестнице** в коридоре.
Код (`layoutEngine._layout_mode_b`): `"any"` падает в ту же ветку `except ValueError`,
что `"both"` → чередование обеих сторон, лестница не участвует. `"any"` ≡ `"both"`.

**Нюансы миграции:** ТЗ-правило ссылается на `staircase.position` — поле старой
connection-схемы (§3.9 «position применяется к to_room»); в `StaircaseSpec` его нет.
Шахты ставятся **после** mode-B (`_place_level_shafts`), а `EmbeddedShaftPlacer` —
stub; «лестница в коридоре» сегодня = shaft смежен коридору со стороны `sc.facing`.

**Решения мастера:**

| # | Решение |
|---|---|
| A1 | Сторона шахты ← `sc.facing` (preferred-направление `AdjacentShaftPlacer` от fr_room-стопа коридора) |
| A2 | Несколько лестниц на коридоре легальны: `occupied = {стороны всех shaft-лестниц на этом z_offset}`; комнаты идут на свободную противоположную сторону. Конфликт — только fit-проблема плейсера, не правила |
| A3 | Неоднозначность (нет свободной стороны / нет лестницы / side вне оси) → `scoped_rng(building_uid, corridor_id, str(z_offset), AttachWall.ANY.value).choice(sides)` — тот же keyed-random паттерн, что `scoped_rng(..., "fr_anchor")` у u_shape; **общий rng-поток не трогаем** (layout-фаза его не имеет). Соль — из enum `AttachWall`, не литерал |
| A4 | `"any"` на некоридорном хосте — ТЗ-правило коридор-специфично → сохранить текущее чередование |
| A5 | Ось сторон — по фактической ориентации хоста (N/S для вертикального коридора, E/W для горизонтального), не фиксированный n/s как в тексте ТЗ |

**Безопасность:** ни одна stdlib-фикстура не использует `"any"` (grep `attach_wall` →
все `"both"`) → A/B fingerprint и RNG-поток существующих шаблонов не сдвигаются.

**TZ:** `tz_building_generator.md` ~§1667; реализация — `layoutEngine._layout_mode_b`
+ источник staircases/levels из `_layout_rooms` (сигнатура mode_b расширяется
staircases + scoped_rng из `app.utils.deterministicIds`).

**Не в срезе:** `EmbeddedShaftPlacer` (stub — embed_in/embed_at carry-only);
host-not-placed WARNING→ERROR (отдельный leftover).

### 6.7 `wall_openings` → `WallOpeningSpec` POJO + потребление

**Статус 2026-10-01: реализован в working tree, uncommitted.**
`WallOpeningSpec` — frozen, extra=forbid; `opening_type` ограничен
`WALL_OPENING_ELEMENTS`, материалы optional, `window_z` — целое >=0.
Невалидные параметры сохраняют substitution без лога в dataModel;
roomFactory пишет ERROR в централизованный generation-транскрипт и передаёт
typed-спеки в `_RoomInstance`. Исходный wire шаблона не мутируется.
`place_wall_openings` потребляет element/frame/glass/window_z; высота проёма
сохраняется из стратегии элемента (пропорция 0.4), явный нижний z от `level.z`.
Выход за высоту комнаты или невмещающийся проём → ERROR + автоматический z.

**Семантика v1:** `spec[0]` применяется ко всем алгоритмическим проёмам комнаты;
каждая запись сверх первой игнорируется, количество таких записей отмечается ERROR.
Пустой массив/спека, omitted/None-параметры — тихий auto-resolve (no-op).
XY/количество/фильтры сохранены. OQ-17 остаётся OPEN, baseline — WINDOW;
template/level `window_z_ratio`/`window_z_offset`, shaft-автоокна,
placement и OQ-13–16 вне среза.

**Проверки:** 177 тестов OK (1 существующий expected failure), 9 новых;
compileall и diff --check чистые. A/B cells+passages всех 13 stdlib идентичен,
те же 8 ERROR, generate×2 детерминирован. Артефакты:
`.local/wall_openings_{before,after}.json`, `.local/wall_openings_tests.log`.

### 6.8 host-not-placed: WARNING → ERROR

**Статус 2026-10-01: реализован в working tree, uncommitted.**
В `_layout_mode_b` одна точка host-not-placed переведена с WARNING на ERROR;
текст сообщения и логика пропуска attached-комнат сохранены. Генерация продолжается.
Проверены обе ветви: хост отсутствует в all_placed / хост найден, но не размещён.
Близнецов в layoutEngine/structureGeneratorService нет: invalid attach_to уже
пишет ERROR, общие NOT PLACED и сводка пропущенных комнат остаются WARNING.

**Scope:** только строка host-not-placed в `_layout_mode_b`. «no space»
варнинги mode_a/mode_b (комната не влезла на сторону) — отдельный вопрос
(геометрический fit, не authored-ссылка) — вне среза. Upstream-фильтр невалидных
`attach_to` (fixed-point в `_layout_rooms`) не трогать.

**Проверки:** suite + compileall + `git diff --check`; A/B 13 stdlib идентичен
(фикстуры не триггерят кейс), те же 8 ERROR. Новый тест: attach_to на
неразмещённый хост → ERROR в транскрипте, комната пропущена, генерация живёт.
179 тестов OK (1 существующий expected failure), включая 2 новых теста;
compileall и diff --check чистые, generate×2 детерминирован.
Артефакты: `.local/host_not_placed_{before,after}.json`,
`.local/host_not_placed_tests.log`. Backend не запускался, коммит не создавался.

### 6.9 `door_height` auto-resolve: убрать clamp, привести к ТЗ

**Статус 2026-10-01: реализован в working tree, uncommitted.**
Общий `passages/doorHeight.py:resolve_door_height` вызывается из entry/doorway;
`build_passages` передаёт template в doorway. По контракту ТЗ
(`tz_building_generator.md` §505–543 entry, §627 connections — решение мастера 2026-09-30) явное
`door_height` **ниже** `world.default_passage_height` — не валидно и **заменяется
авто-резолвом** (не поднимается clamp'ом до предела); для `connections[]`
формула берёт `z_height = min(from_room.z_height, to_room.z_height)`.

**Поведение:** явное `< passage_height` → ERROR на runtime-границе + авто-формула;
`max(height, passage_height)` применяется только к автоматическому результату.
Валидная явная высота сохраняется без cap. Для входа используется room.z_height,
для doorway — min(fr.z_height, to.z_height). Невмещающаяся высота → GenerationError
с uid шаблона и room/connection контекстом. Логи идут в generation-транскрипт.

**Контракт:** общий резолвер — одна функция (например `resolve_door_height(z_height,
explicit, passage_height, ratio, cap)` в `passages/`), оба потребителя вызывают её —
не копия формулы. `template` для `doorway` — прокинуть (функция его сейчас не
получает — через `_build_doorway` из `build_passages`). Runtime-валидация
`passage_height <= door_height < z_height` → `GenerationError` сохраняется и для
connections (применять к `min(fr,to).z_height`).

**A/B: обнаружено неверное исходное предположение.** stdlib-фикстуры не содержат
явного `door_height` (grep → 0), однако новая connection-формула меняет авто-двери
высоких комнат. 12/13 fingerprints совпадают; «Манор тип 1»
(`7c3a4d5e-6f7a-4b8c-8d9e-1f2a3b4c5d6e`, default_z_height=15) изменился.
Это требуемое изменение геометрии по ТЗ, а не побочная регрессия: временная подмена
только doorway-резолвера старой минимальной высотой возвращает все 13 baseline
fingerprints бит-в-бит. ERROR-сообщения всех шаблонов идентичны (8 суммарно),
generate×2 детерминирован. Полная A/B-идентичность несовместима с новой формулой.

**Границы среза:** только `entry.py` + `doorway.py` + plumbing `template` +
тесты. Не трогать `archway` (нет `door_height` на wire), `corridorConnector`
(свой `min(z_height-1, passage_height)` — другая семантика), `heightChecker`.

**Проверки:** 183 теста OK (1 существующий expected failure), включая 4 новых;
старый тест entry ниже предела обновлён с clamp=2 на auto=5.
compileall и diff --check чистые; тесты покрывают fallback+ERROR входа/связи,
valid explicit без cap, min двух высот, template ratio/cap plumbing,
GenerationError у потолка, централизованный транскрипт, детерминизм и immutability.
Артефакты: `.local/door_height_{before,after}.json`, `.local/door_height_tests.log`,
`.local/door_height_ab_check.py`, `.local/door_height_legacy_connection.json`.
Backend не запускался, коммит не создавался.

### 6.10 Смешанный `shape_type`-массив: `shape_params` по **выбранной** форме

**Статус 2026-10-01: реализован в working tree, uncommitted.**
`roomFactory._resolve_shape_params` получает выбранный `ShapeType` и резолвит
arm_* для L / stem_* для T независимо от скаляра или массива на wire.
Остальные формы возвращают `{}` без RNG-draws. Неполные L/T params при обходе
валидатора → ERROR + `{}` для существующих защитных footprint-дефолтов.
Постпроход `resolve_stem_wall` сохранён только при наличии ключа `stem_wall`.

**Фикс:** `_resolve_shape_params(room_def, chosen_shape, rng)` — ветка по
**выбранному** `ShapeType`, не по wire-массиву.
**Уточнение исходного описания:** фактический порядок до среза —
`_resolve_shape → _resolve_shape_params → resolve_stem_wall → _resolve_size`,
а не size перед params. Этот порядок сохранён ради бит-в-бит совместимости
скаляров и одноэлементных массивов; состояние RNG проверено по старой
последовательности draws. Новые draws (arm/stem) возникают только при выбранной
L/T из ранее сломанного многоэлементного массива.

**Безопасность:** stdlib содержит массивы только `["square","rectangle"]`
(kitchen в `5a1f2b3c`, `6b2f3c4d`) — обе формы без params → **поток не меняется,
A/B идентичен обязан быть**. Валидатор `RoomDef` уже требует `shape_params` при
наличии l/t в массиве — доп. импорт-валидации не нужно.

**Проверки:** suite + compileall + `git diff --check`; A/B 13 stdlib идентичен;
тесты: смешанный массив → выбран l_shape → arm_* из спеки (не дефолты), выбран
rectangle → params пусты без draws, скаляр `l_shape`/`t_shape` неизменён,
generate×2 детерминизм.

194 теста OK (1 существующий expected failure), включая 6 новых;
обновлён старый characterization-тест facing defaults, который фиксировал
сломанную mixed-T ветку: теперь он проверяет настоящий обход wire-валидатора
с невалидным stem_wall и однократный ERROR при нормализации.
A/B fingerprints и ERROR-сообщения всех 13 stdlib идентичны baseline этого среза
(8 ERROR суммарно), generate×2 детерминирован. compileall и diff --check чистые.
Артефакты: `.local/mixed_shape_{before,after}.json`, `.local/mixed_shape_tests.log`.
Вне среза: shapes.py, RoomDef-валидатор, SizeShapeResolver, ResolvedStemWall,
EmbeddedShaftPlacer. Backend не запускался, коммит не создавался.

### 6.11 `EmbeddedShaftPlacer` — embed_in/embed_at

**Статус 2026-10-01: реализован в working tree, uncommitted.**
`EmbeddedShaftPlacer` потребляет StaircaseSpec через factory; building_uid
прокинут из сервиса для scoped_rng. Missing/unplaced/wrong-level host → ERROR
+ largest placed non-shaft room на z_lo (равные площади — uid_key).
Угол совмещает две стороны с периметром host; center полностью внутри interior
с минимум одной клеткой host-interior вокруг footprint перед внешними стенами.
Невместимость или overlap с другими комнатами → ERROR + прежний AdjacentShaftPlacer.
CellBuilder, adjacent/edge стратегии и upper host-семантика не менялись.

**Контракт ТЗ:** шахта внутри `embed_in` (fallback: самая большая комната на
z_lo + ERROR); `embed_at` = intercardinal-угол (две стороны шахты сливаются
со стенами хоста, не дублируются) или `center` (столб-атриум, стены на всех 4);
шахта вырезает footprint из interior хоста; хост обязан вместить; проём в шахту
на z_lo — archway со стороны входа.

**Механика уже работает без правок:** `pass2_floors` пропускает `is_shaft` (пол
хоста под шахтой сохраняется → stair-builder перезаписывает ступенями),
`pass3_interior_walls` красит периметр любого footprint → угловая шахта внутри
хоста автоматически даёт стены; слияние со стенами хоста — естественное
(общие ячейки → одна стена). Срез = только `EmbeddedShaftPlacer.place` +
разрешение host/embed_at + synth-conn входа + тесты.

**Решения v1 (если мастер не уточнит иное):**

| Вопрос | Рекомендация |
|---|---|
| `embed_at` отсутствует | `scoped_rng(building_uid, staircase_id, "embed_at").choice(4 угла)` — паттерн §6.6 |
| Хост не вмещает footprint | `logger.error` + fallback на `AdjacentShaftPlacer` (доктрина играбельности; альтернатива — GenerationError) |
| `embed_in` — не room_id на этом z | `logger.error` + fallback: самая большая комната на z_lo (ТЗ) |
| Сторона входа (archway на z_lo) | сторона, обращённая к центру interior хоста; `center` → deterministic по `scoped_rng(..., "embed_entry")` |
| Upper-level pass-through | вне v1 (ТЗ §2 помечает TODO — семантика хоста верхних этажей) |

**Безопасность:** ни одна stdlib-фикстура не использует `in_a_room` (проверить
grep'ом) → A/B идентичен; новые scoped_rng-ключи не пересекаются с существующими.

**Вход/метаданные:** runtime `embedded_host_key`/`embedded_entry` на shaft;
нижняя арка идёт к фактическому host, включая embed_in != stops[0] и fallback.
Для вложенной шахты пересечение footprints — вся площадь шахты, поэтому
archway получил optional shared_cells: embedded передаёт только одну entry-стену
без углов, остальные вызовы сохраняют прежний shared-wall путь.
Center-entry — scoped_rng(..., "embed_entry"), угол — внутренняя сторона с
предпочтением opposite authored facing, иначе внутренняя N/S-сторона.
Runtime-facing = opposite(entry), наследуется верхними шахтами вместе с origin,
чтобы staircase-builder использовал тот же вход. Spec/wire не мутируются.
Сортировка наборов cardinal/intercardinal делает RNG-выбор независимым от hash seed.

**Проверки:** 202 теста OK (1 существующий expected failure), включая 8 новых:
четыре угла и слияние стен, center с четырьмя стенами, deterministic auto-угол,
fallback-host, fit/overlap fallback (включая реальный adjacent), перенос origin,
z_lo arch к host, generate×2 и immutability. A/B всех 13 stdlib идентичен,
те же 8 ERROR, детерминизм ×2; compileall и diff --check чистые.
Артефакты: `.local/embedded_shaft_{before,after}.json`, `.local/embedded_shaft_tests.log`.
TODO функционала снят из staircase §2; старое противоречивое описание §11
согласовано с v1. Верхние embedded pass-through комнаты остаются TODO.
Backend не запускался, коммит не создавался.

## 7. Верификация среза

- `python -m unittest tests.test_entry_point tests.test_structure_template tests.test_building_assembler tests.test_structure_area_assembler tests.test_deterministic_ids tests.test_city_three_axes` — зелёные
- `python -m compileall -q app tests`
- grep: `entry\.get\(|ep\.get\(` в `generators/` — пусто; `entry_point: dict` — нет
- Sweep валидаторов (как §7 п.11): не хуже baseline
