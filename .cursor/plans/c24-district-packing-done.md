# C24: packing по району ✅ DONE

SoT: [`docs/tz_settlement_outdoor.md`](../../docs/tz_settlement_outdoor.md) §5 C24. Команда: [`/impl-c24`](../commands/impl-c24.md).

Код сейчас пакует весь uid одним JSON-кадром и skip’ает по «файл + SQL-дети».

## Контракт вызова (не новый оркестратор)

`SettlementOutdoorOrchestrator.materialize`: `district_uid`, `at_x`, `at_y` optional.

- Канон шага — `district_uid` = `named_locations.location_uid` района (C5).
- `at_*` только резолвер: rect `district_topology`. Fine/world, не `gx/gy`.
- Оба якоря → 422. `at` вне слотов → 422. Нет C23 → **409**, не inline `plan_topology`.
- Без якоря: цикл очереди до `structure_status=complete` (`detailed_bake` не менять).

Резолвер — функции в `settlementOutdoorTopology.py`. HTTP — тот же `generate-settlement`. `SettlementOutdoorConflictError` рядом с NotFound → 409.

## Очередь и C14

`SettlementStructureEntry`: `structure_status` (`absent` \| `partial` \| `complete`), `packed_district_uids`.

Перепись = дети с `district_topology`. Очередь = census − packed. Пустой packed район всё равно в списке.

Skip района iff uid в packed и файл+manifest. Skip поселения (без якоря) iff `complete`. C23-дети без packed — не skip. Authored не-район дети — skip как сейчас.

## Generate одного слота

`generate_layout(district_slots=[one], city_graph=C23)`. `slot_index` с freeze на `DistrictSlot`. Extract не `enumerate` с 0. SQL persist — upsert шага; city-рёбра C23 не rng заново.

## Кадры

Не `TileCodec`. Функции в `packBlobWire.py`; Writer — `.tmp` / replace / manifest.

После 2-байтного header `PAYLOAD_KIND_SETTLEMENT_STRUCTURE`: magic + length-prefixed zstd (`header` + district records). Append = copy + новый record. Read merge в `SettlementStructureWire`. Legacy один-zstd читается.

## Границы классов

Расширяем существующие швы. Не заводим: `settlementOutdoorDistrictAnchor.py`, второй оркестратор, queue dataclass, sidecar index, `SettlementFrameReader`, новый HTTP resource, метод assembler «pack tile».

Не делать: клип по `gx/gy`; skip по «есть дети»; `slot_index=0` на одном слоте.

## Вне среза

SceneInit/DAG; `refine_from_entry`; интерьеры; C16 parallel; алгоритм C22.
