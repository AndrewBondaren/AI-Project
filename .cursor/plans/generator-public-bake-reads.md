# GEN-BAKE-READ — публичное чтение результатов bake

**Статус:** REQUIREMENTS / OPEN, 2026-11-02. Поручение пользователя: отдельное требование к генератору вне scope GEN-DAG с mapping нода → публичный метод → техдолг. Только документы; код и cutover не разрешены.

**Owner:** генераторный домен / Pack read и владельцы topology. GEN-DAG задаёт требования потребителей и реализует bindings после приёмки публичных контрактов. DAG не собирает результаты из файлов, manifest и SQL самостоятельно.

## 1. Обязательная карта

Названия ниже — **предлагаемые target public operation names**, которых пока нет в коде. Класс/factory/порты и exact files определяются генераторным доменом на contract freeze; новый центральный gameplay facade не требуется.

| Consumer node | Target public method | Техдолг |
|---|---|---|
| `check_light_bake` | `read_light_bake` | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) |
| `check_full_bake` | `read_full_bake` | [GEN-READ-2](../../docs/tz_generator_technical_debt.md#gen-read-2) |
| `check_location_l2` | `read_location_l2` | [GEN-READ-3](../../docs/tz_generator_technical_debt.md#gen-read-3) |

Дубликат карты: [generator_public_method](./generator_public_method.md). Consumer requirements: [GEN-DAG-NODE-DEPENDENCY §§8–9](./gen-dag-node-dependency.md#8-отдельные-ноды-проверки-состояния-мира-перед-загрузкой). Owning orchestration: [GEN-DAG-1](./gen-dag-1-post-geo-ws.md).

## 2. Требования к контрактам

Пока это смысловые сигнатуры, не новые Python POJO/порты с неподтверждёнными типами:

1. `read_light_bake(world identity, publication expectation, required L0 scope)` → полученные L0 данные/immutable domain refs либо факт отсутствия/неполноты требуемого scope.
2. `read_full_bake(world identity, publication expectation, required full scope)` → полный согласованный результат L0 и требуемой topology либо факт отсутствия/неполноты. Точный состав topology и граница owning read operation требуют совместной приёмки Pack/topology owners; отсутствие settlement делает topology неприменимой, а не missing.
3. `read_location_l2(world identity, publication expectation, location identity, required L2 scope/LOD)` → terrain L2 данные/immutable domain refs либо факт отсутствия/неполноты. Домен разрешает owning terrain scope для district/building/room, не требует файл по любому leaf UID.

Общий успешный результат: discriminated found/missing. found содержит non-null data или проверенные разрешимые refs на полный required scope; missing — подтверждённое отсутствие с конкретным missing scope, reason absent/incomplete. Не только ready bool или проценты прогресса.

Ошибка чтения/decode, manifest-declared но пропавший artifact, corruption, несовместимые world/revisions/hashes и unsupported format — отдельный Error. Нельзя ловить всё и возвращать missing. Допустимая доменная пустота не равна отсутствию bake.

Publication=None допускается только как подтверждённое отсутствие принятой публикации, не fallback после ошибки. Exact missing/admission/read evidence и pinning contract согласовать с publication owner. Методы read-only: не запускают bake/planning/materialization/repair, не публикуют мир и не меняют refs.

Bulk остаётся в immutable artifacts с domain-owned refs. Нода не получает пути файлов, storage reader, assembler/planner internals. Возвращённые refs должны поддерживать lifecycle/resume validation. World Snapshot не выбирает Input ноды; RepairPatchApplier относится к execution results и не заменяется этими reads.

## 3. AS-IS evidence и места реализации требований

| Target | Существующие места | Почему нельзя просто подключить их к ноде |
|---|---|---|
| read_light_bake | [WorldPackReader.read_world_map_tile](../../backend/app/application/worldData/pack/io/worldPackReader.py), [parentLightLoad](../../backend/app/application/worldData/pack/read/parentLightLoad.py), [ParentLightTile](../../backend/app/dataModel/worldPack/wire/parentLightTile.py) | Reader — storage internals; load_parent_light сводит FileNotFound/OSError/ValueError к None; нет public scoped found/missing/error с pinned refs |
| read_full_bake | [PackLoadingProgressFacade.get_loading_progress](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py), [PackCompletenessClassifier.classify](../../backend/app/application/worldData/pack/bake/finalize/packCompletenessClassifier.py), [settlementOutdoorOrchestrator](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py) | Progress/classifier возвращают счётчики/manifest classification, не данные; full_complete не проверяет topology; plan_topology — write/compute, не read |
| read_location_l2 | [WorldPackReader.read_location_terrain](../../backend/app/application/worldData/pack/io/worldPackReader.py), [PackFineTerrainReadFacade.read_location_terrain](../../backend/app/application/worldData/pack/read/packFineTerrainReadFacade.py), [FineTerrainChunkWire](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py) | Facade — debug dict с sample columns, не полный typed результат; wire содержит mutable lists; нет принятого public immutable scoped read |

Общие integration места: [PackReadContext](../../backend/app/application/worldData/pack/read/packReadContext.py), [PackReadServices](../../backend/app/application/worldData/pack/read/packReadServices.py), [WorldPackManifest](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py). Это audit/navigation, не предписание импортировать их internals в DAG.

Нормативные источники: [Pack storage](../../docs/tz_world_pack_storage.md), [locations](../../docs/tz_locations.md), [settlement outdoor](../../docs/tz_settlement_outdoor.md), [Snapshot](../../docs/tz_world_snapshot.md), [Domain Patches](./world-domain-patches-snapshots.md), [generator interface rule](../rules/dag-generator-interface.mdc).

## 4. План исполнения вне GEN-DAG

- [ ] Генераторный owner принимает имена и scope трёх публичных операций, ownership full/topology read.
- [ ] Провести inventory существующих POJO/refs/errors и согласовать точные Input/Output/Error, required scope, publication/source consistency, absence и partial semantics. Не создавать недостающий порт/тип при обнаруженном пробеле без приёмки.
- [ ] Предъявить exact class/factory/read binding/file/import map, direct folder counts, retained nested calls и доказательство read-only atomic boundaries. Общий механизм DAG не дублировать.
- [ ] После отдельного разрешения реализовать публичные операции за стабильным контрактом; storage internals, проверка completeness/refs и decode остаются внутри доменных reads.
- [ ] Проверить found, absent, incomplete, valid empty, missing published artifact, corruption, stale publication, wrong world, cancel/ref lifecycle. Не использовать debug/progress output как доказательство полученных данных.
- [ ] Генераторный owner принимает операции и закрывает GEN-READ-1/2/3 отдельно по фактическому evidence.
- [ ] Передать принятые контракты в GEN-DAG для concrete bindings трёх нод. Это не включает activation/cutover, не принимает SP-R2 и не снимает прочие gates.

**Блокировка:** до приёмки соответствующего public метода concrete read binding соответствующей ноды GEN-DAG остаётся OPEN. Документальные Input/Output и обсуждение графа доступны независимо.
