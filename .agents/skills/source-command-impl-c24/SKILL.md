---
name: "source-command-impl-c24"
description: "Имплементирует outdoor C24: packing одного района через materialize, очередь в manifest, кадры в том же settlement.zst. Новый чат: /impl-c24."
---

# source-command-impl-c24

Use this skill when the user asks to run the migrated source command `impl-c24`.

## Command Template

# Имплементация: C24 packing по району

Это **явная просьба писать код** (слои плана C24). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/c24-district-packing.md`](../plans/c24-district-packing.md) — **архитектура, границы классов, порядок**; не отклоняться.
2. [`docs/tz_settlement_outdoor.md`](../../docs/tz_settlement_outdoor.md) §5 **C24** (якорь, очередь, кадры) + таблица **C14 / C15 / C19 / C11**.
3. [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) фаза 2 / §11.3 (без якоря = очередь; spawn = район ног).
4. [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) `SettlementStructureEntry` (`packed_district_uids`, `structure_status`).
5. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/architecture-first.mdc`](../rules/architecture-first.mdc)
   - [`.cursor/rules/dag-generator-interface.mdc`](../rules/dag-generator-interface.mdc)
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — DAG / backend / commit / schema = только `0001`

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

После C23 районы уже в SQL. `materialize` пакует **один район** (или очередь без якоря) в тот же `l.{uid}.settlement.zst`. Игрок не ждёт весь город и не ждёт L2 AABB. Очередь — manifest, не decompress zst.

## Жёсткие запреты

- Не клип layout / packing по `tile_gx/gy`. Не файл на район. Не sidecar `*.index.json`.
- Не новый оркестратор, не `settlementOutdoorDistrictAnchor.py`, не `DistrictPackQueue`, не `SettlementFrameReader`, не ветки district в `TileCodec`.
- Не inline `plan_topology` внутри packing: нет C23 → **409**.
- Не skip C14 по «файл есть + SQL-дети» (после C23 дети уже есть).
- Не `enumerate` одного слота как `slot_index=0` (uid района разъедется с C23).
- Не DAG `application/engine/nodes/`. Не WP-13 / `refine_from_entry`. Не стартовать backend. Не коммитить, пока мастер не скажет.
- Не `0002_*.sql`. Интерьеры, parallel C16, правка алгоритма C22 — вне среза.

```python
# ❌ BAD
materialize(..., tile_gx=0, tile_gy=1)
if writer.has_published_settlement(uid) and children: return skip
for i, slot in enumerate(one_slot_list):  # i==0 → чужой uuid5
    uid = district_location_uid(settlement, slot.template, i)

# ✅ GOOD
district_uid = resolve_district_uid(census, district_uid=..., at_x=..., at_y=...)
if district_uid in packed: return skip
layout = generate_layout(..., district_slots=[one], city_graph=frozen)
# slot.slot_index с freeze → тот же district_location_uid, что C23
```

## Якорь

Канон — `district_uid` = `named_locations.location_uid` района (C5). Тот же ключ в `packed_district_uids`, C14, `parent_location_uid` зданий.

`at_x`/`at_y` — **только резолвер** в этот uid (rect `district_topology`, world fine). Оба якоря → 422. Вне слотов → 422. Функции — в `settlementOutdoorTopology.py`, не в route.

HTTP: существующий `POST …/generate-settlement` + query. `SettlementOutdoorConflictError` рядом с `NotFound` / `PackMissing` → 409.

Без якоря: цикл очереди до `complete` (`detailed_bake` не менять — он уже зовёт `materialize()`).

## Порядок (слои целиком)

| Слой | Что | Готово когда |
|---|---|---|
| **A** POJO | `SettlementStructureEntry.structure_status` (`absent`\|`partial`\|`complete`), `packed_district_uids`; `extra=ignore` | Unit defaults; старый manifest без полей читается |
| **B** якорь + C14 | `resolve_district_uid` в topology; `should_skip_materialize` по packed/complete; 409 без census | Unit: uid; at в rect; оба/miss; C23 дети без packed → не skip; authored tavern → skip |
| **C** один слот | `slot_index` на `DistrictSlot`; `generate_layout([one], city_graph)`; extract uid = C23; SQL upsert только шага | Unit: `slot_index=2` → тот же `district_location_uid` |
| **D** кадры | encode/append/parse в `packBlobWire`; Writer `.tmp`+replace+manifest packed list; legacy один-zstd читается; `TileCodec` без district-веток | Unit: два append без recompress первого payload; legacy read |
| **E** оркестратор + HTTP | `_materialize_one` + цикл без якоря; query `district_uid` / `at_x`+`at_y`; 409/422 | `detailed_bake` без правок вызывает очередь |

После слоя: что сделано / что осталось. Не рефакторить assembler C22 «заодно». Тесты — `backend/tests/`, не `debug_settlement.py`.

## Старт

Прочитай план целиком и текущие `settlementOutdoorOrchestrator.materialize`, `settlementOutdoorSkip.py`, `settlementOutdoorTopology.py`, `settlementOutdoorExtract.py`, `worldPackManifest.SettlementStructureEntry`, `packBlobWire.py`, `worldPackWriter.encode_settlement_structure_tmp`, `api/routes/locations.py` `generate-settlement`. Затем слой A.
