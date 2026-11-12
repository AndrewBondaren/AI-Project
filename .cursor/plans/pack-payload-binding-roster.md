# Pack — единая карта payload bindings

Проект конкретизации P2: 10 публичных address roles → 7 payload bindings. Основание — существующие payload traces и [контракт лимитов](pack-budget-enforcement.md). Runtime не изменяется. Новые descriptor IDs ниже относятся к проекту Pack, а не объявляются уже зарегистрированными. Existing climate/hydrology IDs и версии сохраняются; версия manifest не назначается версиям payload.

## Форматы и типизированное чтение

Все storage bindings — ArtifactFormatContract[bytes], BLOB. Typed T возвращает внутренний PackPartPayloadDecoder, не BLOB backend. Для новых storage/read descriptors предлагается первая версия 1; значение принадлежит соответствующей декларации constants, не повторяется literal в DAG. Для existing форматов используются owning version constants.

| Address roles | Storage key / источник | Typed read ID / T | Decoder и статус |
|---|---|---|---|
| map_tile | Проект world_pack.map_tile.zstd; meta/worldMapTileStorageFormat.py | Проект world_pack.map_tile; проект WorldMapTileWire | encoding/worldMapTileFormat.py; envelope TileCodec kind WORLD_MAP, bounded JSON; shared WorldMapCellWire без копии |
| wilderness_chunk, location_terrain | Проект world_pack.fine_terrain.zstd; meta/fineTerrainStorageFormat.py | Проект world_pack.fine_terrain; existing FineTerrainChunkWire | encoding/fineTerrainFormat.py; один bounded decoder, разные address/territory проверки |
| settlement | Проект world_pack.settlement_structure.framed; meta/settlementStructureStorageFormat.py | Проект world_pack.settlement_structure; existing SettlementStructureWire | encoding/settlementStructureFormat.py; согласованный framed format и historical transition binding; без legacy fallback по догадке |
| climate_coarse, climate_fine | Existing world_pack.climate_field.zstd / CLIMATE_FIELD_FORMAT_VERSION | Проект world_pack.climate_field; existing ClimateFieldWire | Existing encoding/climateFieldFormat.py::decode_climate_field с требуемой bounded/strict адаптацией; один формат для обеих ролей |
| locations_index | Проект world_pack.locations_index.json; meta/locationsIndexStorageFormat.py | Проект world_pack.locations_index; existing LocationsIndexWire | Проект encoding/locationsIndexFormat.py; bounded strict JSON; порядок pins сохраняется |
| spatial_root(HYDROLOGY_OPEN_WATER) | Existing ROOT_V1.key / FORMAT_VERSION из hydrology/pack/profile.py | Проект world_pack.spatial.hydrology_open_water; existing HydrologyPackRoot | Owning decode_root и bounded profile; Pack adapter без повторной реализации codec; shards — transitive closure, не новые top-level parts |
| tile_grade_slots, location_grade_slots | Уже предложенный world_pack.grade_slots.json; meta/gradeSlotsStorageFormat.py | Уже предложенный world_pack.grade_slots; existing GradeSlotSidecar | encoding/gradeSlotsFormat.py::decode_grade_slots; один JSON binding, без merge внутри decoder |

Все meta paths относительны `backend/app/dataModel/worldPack/`, encoding — `backend/app/application/worldData/pack/`. Read descriptors размещаются в `dataModel/worldPack/read/`: worldMapTileContract.py, fineTerrainContract.py, settlementStructureContract.py, climateFieldContract.py, locationsIndexContract.py, spatialRootContract.py, gradeSlotsContract.py соответственно. Эти модули объявляют immutable contract identity; executable decoder/backend туда не попадают. Spatial descriptor явно относится к существующему supported domain, а не обещает generic поддержку всех будущих SpatialDatasetKind.

Четыре новых storage keys — map_tile, fine_terrain, settlement_structure, locations_index — выделяют уже описанные bytes formats; они не меняют алгоритмы producer. Shared payload POJO требуют ранее выявленной strict/immutable адаптации, поэтому наличие имени T не означает готовность read binding. Для settlement target framing и migration прежних bytes проверяются отдельно; новая версия descriptor не легализует молчаливое чтение всех legacy вариантов.

## Composition и разрешение

Переиспользуются existing ArtifactFormatRegistryBinding и проектные PackPartReadBindingRegistry/PackPartReadBinding. Storage регистрируется один раз на format key с явным набором supported versions; existing register отклоняет повтор ключа и несовпадение экземпляра backend.contract. Нельзя регистрировать coarse/fine или tile/location дважды как разные backend под одним key.

Typed read registry связывает (read id, read version) с конкретными address_types, storage key/versions, payload_type, pure decoder и fixed profile. Неверная роль отвергается до payload read: например, fineTerrain binding не принимает settlement address, даже если caller подставил подходящий generic T. Идентичность read descriptor не определяется по имени Python-класса от caller. Для final prepare та же immutable registration предоставляет однозначное соответствие (address variant/domain, storage key/version) → binding. Составление этого внутреннего индекса — composition, не второй независимый реестр правил и не публичный каталог схем.

Если две регистрации дают разные payload types/decoders для одной address+storage пары, composition отклоняется как неоднозначная. Пустые address_types/versions, отсутствующий decoder/profile и неконкретный payload type также отклоняются до приёма запросов. Read version и storage version независимы; добавление версии требует явной регистрации, не fallback по похожему key. Новые schema identities регистрируются вместе с конкретными named моделями; raw generic specialization не подменяет ModelIdentity для диагностики.

**Read chain:** pinned manifest → part по logical address → проверка read contract/role/descriptor → bounded guarded read bytes → тот же registered semantic decoder/profile → address/metadata проверки → immutable typed result. Отсутствие part в проверенном manifest даёт ABSENT; отсутствующий codec, неподходящая версия или роль — CONTRACT_MISMATCH, а не ABSENT. Missing blob/hold и malformed payload сохраняют отдельные existing read reasons.

**Prepare chain:** конечные parts → тот же address/format binding → verified bounded bytes → тот же semantic decoder/profile → связь с assembly/coverage и closure → READY. Prepare не вызывает публичный read_part и не читает latest manifest; входная база и удержания определяются его lifecycle. Различие read/prepare в admission контексте не создаёт двух реализаций payload schema.

## Состав дочерних refs

Map tile, fine terrain, climate, locations index и grade payload не получают дочерних ArtifactRef из строковых UID/registry keys. Source/provenance closure учитывается отдельно. Spatial root использует owning shard entries; каждый shard дополнительно проверяется своим descriptor/decoder и identity относительно root. Settlement исторический transition registry не заменяется current singleton; нужный historical binding фиксируется в его отдельном контракте. Регистрация bytes backend сама по себе не доказывает полноту closure.

В production сейчас подтверждена регистрация manifest и climate через PacksWiring. Наличие ROOT_FORMAT/SHARD_FORMAT или fixture registry не означает production wiring spatial. Новые строки карты также требуют реального подключения; describe/write операции не выполняют ленивую регистрацию и не загружают codecs через пользовательские строки.

Приёмка: все 10 ролей разрешаются ровно своим binding; wrong T/role/version отклоняется; две роли общего формата имеют один semantic decoder/profile; prepare и read одинаково отклоняют malformed bytes; duplicate/ambiguous registry не запускается; missing binding не превращается в absent; root-only registration не проходит full spatial closure; callers не получают codec/backend. Эта карта — проект, не отчёт о выполненных тестах или готовом runtime.
