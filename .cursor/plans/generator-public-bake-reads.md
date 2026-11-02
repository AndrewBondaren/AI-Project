# GEN-BAKE-READ — публичное чтение результатов bake

**Статус:** EXACT CONTRACT PROPOSAL / НА ПРИЁМКЕ, 2026-11-02. Локальные решения и внешние OPEN contracts — §§5–12; freeze пользователем не принят. Поручение пользователя: отдельное требование к генератору вне scope GEN-DAG с mapping нода → публичный метод → техдолг. Только документы; код и cutover не разрешены.

**Owner:** генераторный домен / Pack read и владельцы topology. GEN-DAG задаёт требования потребителей и реализует bindings после приёмки публичных контрактов. DAG не собирает результаты из файлов, manifest и SQL самостоятельно.

## 1. Обязательная карта

Названия ниже — **предлагаемые target public operation names**, которых пока нет в коде. Класс/factory/POJO/file map предложены в §10, внешние ports OPEN в §11; новый центральный gameplay facade не требуется.

| Consumer node | Target public method | Техдолг |
|---|---|---|
| `read_world_light_bake` | `read_light_bake` с полным world light coverage; exact proposal §§6–8, acceptance OPEN | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) |
| `read_scoped_light_bake` | `read_light_bake` с required request scope; exact proposal §§6–8, acceptance OPEN | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) |
| `check_full_bake` | `read_full_bake` | [GEN-READ-2](../../docs/tz_generator_technical_debt.md#gen-read-2) |
| `check_detailed_bake` | `read_location_l2` | [GEN-READ-3](../../docs/tz_generator_technical_debt.md#gen-read-3) |

Дубликат карты: [generator_public_method](./generator_public_method.md). Consumer requirements: [GEN-DAG-NODE-DEPENDENCY §§8–9](./gen-dag-node-dependency.md#8-родитель-и-отдельные-ноды-проверки-инициализации-мира). Owning orchestration: [GEN-DAG-1](./gen-dag-1-post-geo-ws.md).

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

- [ ] Генераторный owner принимает имена и scope публичных операций, ownership full/topology read.
- [ ] Провести inventory существующих POJO/refs/errors и согласовать точные Input/Output/Error, required scope, publication/source consistency, absence и partial semantics. Не создавать недостающий порт/тип при обнаруженном пробеле без приёмки.
- [ ] Предъявить exact class/factory/read binding/file/import map, direct folder counts, retained nested calls и доказательство read-only atomic boundaries. Общий механизм DAG не дублировать.
- [ ] После отдельного разрешения реализовать публичные операции за стабильным контрактом; storage internals, проверка completeness/refs и decode остаются внутри доменных reads.
- [ ] Проверить found, absent, incomplete, valid empty, missing published artifact, corruption, stale publication, wrong world, cancel/ref lifecycle. Не использовать debug/progress output как доказательство полученных данных.
- [ ] Генераторный owner принимает операции и закрывает GEN-READ-1/2/3 отдельно по фактическому evidence.
- [ ] Передать принятые контракты в GEN-DAG для concrete bindings согласованных нод. Это не включает activation/cutover, не принимает SP-R2 и не снимает прочие gates.

**Блокировка:** до приёмки соответствующего public метода concrete read binding соответствующей ноды GEN-DAG остаётся OPEN. Документальные Input/Output и обсуждение графа доступны независимо.

**Light readers:** группа light_bake_readers содержит read_world_light_bake и read_scoped_light_bake; смысловые I/O/Error/DoD — [§9.5 реестра нод](./gen-dag-node-dependency.md#95-light_bake_readers--выходные-контракты-и-definition-of-done). Обе читают L0 и обязательные связанные index/climate/metadata для своего coverage. Общий domain reader допустим. check_light_bake сохраняет прежнее родство; replacement bindings новых нод OPEN, нового parent NodeId нет. NamedLocation entry использует scoped reader; world complete не его prerequisite.

## 5. Exact contract freeze proposal GBR-1 (2026-11-02)

**НА ПРИЁМКЕ, не принят.** §§5–12 заменяют прежние «определить на freeze»
для локальных проектных решений. Внешние ports перечислены в §11 как OPEN;
это реальные blockers реализации, а не разрешение выбрать контракт в коде.
Исследование статическое; production/race evidence не получено. GEN-DAG draft
не downstream authority: использованы только consumer requirements §§8–9, 9.5, 16.

### 5.1. Проверенный reuse и legacy ledger

Пути ниже относительно `backend/app/`; ссылки ведут на существующие файлы.

| Реализация и caller | Наблюдение | Disposition |
|---|---|---|
| [WorldPackReader](../../backend/app/application/worldData/pack/io/worldPackReader.py): load_manifest, read_world_map_tile, read_climate_coarse, read_location_terrain, read_wilderness_chunk | decode с kind check; manifest перечитывается по mtime/size; fine cache keyed UID/coordinates, не publication | Retain storage decoder; новый read использует только pinned namespace и отдельный cache на publication. Существующий reader не pin port |
| [parentLightLoad](../../backend/app/application/worldData/pack/read/parentLightLoad.py): load/require_parent_light → [gridNeighborHalo](../../backend/app/application/worldData/pack/refine/gridNeighborHalo.py), [climatePackBakeOrchestrator](../../backend/app/application/worldData/pack/climate/climatePackBakeOrchestrator.py), [detailedBakeRefine](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py) | None при FileNotFound/OSError/ValueError; require превращает всё это в MissingParentLightError | Retain для legacy preparation; запрет reuse error mapping/public cache. Никакого blanket удаления |
| [PackLoadingProgressFacade.get_loading_progress](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py) → [routes/map.py](../../backend/app/api/routes/map.py): get_loading_progress и detail status | locations→SurfacePlanningEntry.probe_extent; счётчики путей/статусов, не validated data | Retain progress API; исключить целиком из read call graph, включая probe_extent |
| [PackCompletenessClassifier.classify](../../backend/app/application/worldData/pack/bake/finalize/packCompletenessClassifier.py) ← progress | PackTilePlanner.plan(light/full), ограниченный missing list, full не проверяет C23 | Retain diagnostic classifier; не использовать его completeness enum как public verdict |
| [PackFineTerrainReadFacade](../../backend/app/application/worldData/pack/read/packFineTerrainReadFacade.py) ← routes/map.py: pack_fine_terrain_read | sample dict; отсутствующий declared blob даёт column_count=0; merged path идёт в gameplay | Retain debug route; новый read не вызывает facade/get_cell и не возвращает sample |
| [PackReadContext](../../backend/app/application/worldData/pack/read/packReadContext.py) ← [PackReadServices factory](../../backend/app/application/worldData/pack/read/packReadServices.py), mapCellQuery/render/debug/climate | path/cache lifetime не равен publication lifetime; has_pack проверяет presence | Retain legacy; не расширять до publication manager и не считать presence evidence |
| [locationsIndexRead](../../backend/app/application/worldData/pack/read/locationsIndexRead.py) | отсутствующий index→None; pins не полный ownership census | Reuse decode только после проверки обязательного artifact; не использовать pins для parent resolution |
| [settlementOutdoorTopology](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorTopology.py): topology_census, should_skip_topology, load_topology_slots ← [settlementOutdoorPackingJob](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py) | SQL district payloads, skeleton/context, восстановление DistrictSlot; skip authored children не readiness proof | Retain packing helpers; не public immutable topology reader |
| [settlementOutdoorOrchestrator](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py): plan_topology/materialize | compute/persist, invalidate; не read | Исключить из reads; отдельный topology owner read ниже |
| WorldPackReader.read_settlement_structure → [PackRenderReadFacade](../../backend/app/application/worldData/pack/read/packRenderReadFacade.py), [settlementStructureRaster](../../backend/app/application/worldData/pack/read/settlementStructureRaster.py), [transitionReadService](../../backend/app/application/worldData/transitions/transitionReadService.py) | C24 structure/interior transitions не C23 topology receipt | Retain; не выводить C23 или C11 completeness из наличия settlement.zst |
| [packTileCollect](../../backend/app/application/worldData/pack/bake/plan/packTileCollect.py): location_anchor_tiles, declared_hydro_tiles, light_l0_tiles, world_bounds_l0_tiles | light anchor-only и endpoints-only hydro; full world_bounds; debug cap не coverage | Legacy planning policy; target coverage ниже требует отдельного producer handoff, read не вызывает collector |
| [detailedBakeScope](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py) | territory_volume_for_location и wilderness rect selection; нет общего leaf→owner published resolver | Reuse coordinate conventions; не вызывать preparation и не считать готовым ownership port |

Готовые узкие contracts: kind-checked blob decode, wire schemas
[manifest](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py),
[index](../../backend/app/dataModel/worldPack/wire/locationsIndexWire.py),
[ParentLightTile](../../backend/app/dataModel/worldPack/wire/parentLightTile.py).
Их mutable вложения/неполный provenance не позволяют экспортировать их как immutable output.
Отсутствуют: pinned publication read lease, authoritative coverage receipt,
immutable topology closure, leaf→terrain owner census и public complete result.

### 5.2. Варианты композиции и решение

1. Подключить progress/classifier/debug: отклонено из-за planning probe, swallowed
   errors, sample output и отсутствия pinning/topology.
2. Собрать manifest/SQL/files в DAG: отклонено; дублирует доменную completeness и
   заставляет ноду знать storage internals.
3. Добавить central gameplay facade/registry: отклонено; lookup по трём статическим
   операциям не требует registry, gameplay overlays не входят в baked read.
4. **Выбрано:** отдельные Pack light/L2 readers и небольшой full composition service
   внутри Pack read. Topology owner предоставляет immutable C23 read. Full собирает
   L0 и C23 под одним publication lease; не вызывает другую DAG-ноду. Общий light
   reader обслуживает world/request coverage. Factory существующих PackReadServices
   остаётся composition root, без world/planning capture внутри read.

Full ownership: Pack owns агрегат и missing union, settlementOutdoor owns C23
payload/admission. Нельзя поручить C23 WorldPackReader.read_settlement_structure:
это другой artifact. При невозможности pin SQL topology к публикации full read
блокируется внешним контрактом; live SQL fallback запрещён.

## 6. Точная семантика scope и ownership (proposal)

Все координаты integer world-fine; XY boxes half-open. Seam split выполняет
домен до tile expansion с WorldTopology той же revision; caller не нормализует
ошибочные координаты молча. Z terrain wire остаётся inclusive; преобразование
request [z0,z1) в wire явно проверяется. Scope nonempty и bounded; пустой запрос
INVALID_SCOPE, но пустые данные внутри корректного scope допустимы.

**WorldLightCoverage:** не world_bounds и не то, что уже listed в manifest.
Нормативный expected set = macro tiles, пересекающие published authoritative
NamedLocation anchor/territory union и declared hydrology geometry union.
Anchor включает свой tile; при наличии territory берётся вся territory, не один
anchor. Для authored water берутся все пересечённые tiles сегментов/полигонов,
включая interior declared basin/lake, не только endpoints/shore vertices.
Auto oceans/auto rivers не расширяют light scope. Geometry здесь coverage demand,
не water occupancy и не повторный fill. Seam geometry использует accepted topology
frame. Producer сохраняет canonical sorted unique tile set и source fingerprint
в coverage receipt; reader только проверяет receipt. Изменение anchor-only policy
явно предъявляется на приёмку; старый collector не объявляется эквивалентным.

**RequestLightCoverage:** обязательный explicit union boxes + target identity
если NamedLocation. Домен проверяет соответствие required request territory
выбранному target; отсутствие complete world не prerequisite. Нельзя молча
сужать запрос до пересечения с WorldLightCoverage: request tiles вне world-light
тоже обязательны и могут дать missing. Halo только если явно входит в request,
не скрытое расширение. Обязательный комплект: каждый L0 tile, полный согласованный
locations_index (включая корректный empty), coarse climate, format/grid/topology
metadata. Климат может быть глобальным artifact; scoped read всё равно проверяет
его согласованность, но не world tile completeness.

**FullScope:** explicit bounded boxes либо WorldBounds, required L0 tiles для
всего scope + C23 closures всех settlement territories, пересекающих scope.
C23 читается целиком для каждого такого settlement, даже при частичном overlap.
Ноль применимых settlements → topology NOT_APPLICABLE с проверенным census.
Full не требует L2/C24/interiors и не доказывает water availability.

**Named L2:** target UID проверяется в published hierarchy census, не в pins.
Target location с собственным terrain ownership mapping использует его; district,
building, room проходят цепочку parents до ближайшего declared terrain owner.
Одна leaf может требовать несколько owner volumes: возвращается весь tuple mapping,
если explicit published split; ambiguous overlap без mapping → OWNERSHIP_UNRESOLVED.
Не угадывать owner по ближайшему anchor, пути или типу UID. Проверяются world,
acyclic ancestry, containment required volume и source revision; выход за mapped
coverage → INVALID_SCOPE. Отсутствие terrain artifact у корректно resolved owner
есть missing; отсутствие/противоречие самого обязательного ownership census — Error.

**Координаты/wilderness:** отдельное требование, не overload read_location_l2.
Предлагается отдельный `read_wilderness_l2(WildernessL2ReadRequest)` за тем же
PackTerrainBakeReader; target = canonical bounded XYZ boxes, chunk coverage из
published layout, никакой fake NamedLocation. Имя/добавление операции требует
отдельной приёмки §11; три запрошенные операции его молча не реализуют.

## 7. Input/Output/Error schema (проект exact freeze)

Все records ниже immutable: frozen dataclass, tuple/frozenset вместо lists/dicts.
Это документальная схема, не новые production symbols. UID использует existing
EntityUid (`app.dataModel.identity.uid`); hash — nonempty canonical content digest, opaque revision — nonempty
owner-issued token, не timestamp. Поля обязательны, если явно не optional.

```text
BakeIdentity = {world_uid: EntityUid, source_revision: str, frame_revision: str}
PublicationExpectation = PinnedPublication | ConfirmedNoPublication
PinnedPublication = {world_uid, publication_id: str, root_digest: str}
ConfirmedNoPublication = {world_uid, observed_head_revision: str, absence_receipt: str}
ReadControl = {cancel: cancellation token}
LightReadRequest = {identity, publication, coverage: WorldLight | RequestLight, control}
WorldLight = {kind: WORLD}
RequestLight = {kind: REQUEST, boxes: tuple[FineBox2D,...], target_uid: EntityUid|None}
FullReadRequest = {identity, publication, scope: WorldBounds | tuple[FineBox2D,...], control}
LocationL2ReadRequest = {identity, publication, target_uid: EntityUid,
                       volumes: tuple[FineBox3D,...], lod: TERRAIN_L2, control}
ResolvedBakeScope = {frame_revision, tiles: tuple[TileKey,...],
                    terrain_owners: tuple[OwnerVolume,...], settlements: tuple[EntityUid,...]}
OwnerVolume = {owner_uid, requested_volume: FineBox3D, ancestry_digest: str}
BakeReadFound[T] = {kind: FOUND, identity, publication: PinnedPublication,
                   resolved_scope, data: T, evidence: BakeReadEvidence}
BakeReadMissing = {kind: MISSING, identity, publication: PublicationExpectation,
                  resolved_scope, reason: ABSENT|INCOMPLETE,
                  missing_scope: tuple[MissingBakePart,...]}
MissingBakePart = {part: L0_TILE|LOCATIONS_INDEX|COARSE_CLIMATE|METADATA|C23|L2_VOLUME,
                   tile: TileKey|None, owner_uid: EntityUid|None,
                   volume: FineBox3D|None}
LightBakeData = {tiles: tuple[VerifiedBakeRef,...], locations_index: VerifiedBakeRef,
                 coarse_climate: VerifiedBakeRef, metadata: VerifiedBakeRef}
FullBakeData = {light: LightBakeData, topology: tuple[VerifiedBakeRef,...],
                topology_applicability: REQUIRED|NOT_APPLICABLE}
LocationL2BakeData = {target_uid, owners: tuple[OwnerVolume,...], terrain: tuple[VerifiedBakeRef,...]}
VerifiedBakeRef = {identity, publication_id, artifact_id: str, digest: str,
                   format_id: str, scope: ResolvedBakeScope}
BakeReadEvidence = {coverage_digest: str, verified_artifact_digests: tuple[str,...],
                    lease_receipt: str, applicability_digest: str}
BakeReadError = {code: BakeReadErrorCode, identity, publication, part: MissingBakePart|None,
                 diagnostic_id: str}
```

Optional fields в MissingBakePart не свободная комбинация: L0_TILE требует tile,
C23 требует owner_uid, L2_VOLUME требует owner_uid+volume; остальные singleton.
Missing scope nonempty, canonical sorted/deduplicated, без diagnostic cap; missing
не несёт частичный usable payload. ABSENT — ни одна требуемая bake часть не
опубликована; INCOMPLETE — proper subset. Для no-publication resolved scope идёт
из authoritative request/source receipt, не из отсутствующего manifest.

`async read_light_bake(request) -> BakeReadFound[LightBakeData] | BakeReadMissing`
и аналогично full/location. Ошибки поднимаются как typed BakeReadError exception;
cancellation распространяется стандартным cancellation exception, не missing/error
payload. Public operations не имеют дефолтного scope/LOD/publication.

BakeReadErrorCode (закрытый proposed enum): INVALID_SCOPE, WORLD_MISMATCH,
SOURCE_MISMATCH, PUBLICATION_STALE, REF_STALE, OWNERSHIP_UNRESOLVED,
DECLARED_ARTIFACT_MISSING, CORRUPT_ARTIFACT, UNSUPPORTED_FORMAT, READ_FAILURE,
PUBLICATION_UNAVAILABLE. Неподдержанный LOD → INVALID_SCOPE. Нет catch-all→missing.
Несколько обнаруженных errors сохраняются в typed tuple причин; code — первая
по стабильному порядку validation→publication→metadata→scope→artifact key.
Cancellation имеет приоритет после очередного cancellation checkpoint.

## 8. Read transaction, refs, valid emptiness

1. Validate request/identity/frame/LOD. Publication owner подтверждает explicit
   pin либо отсутствие head. None не сырой filesystem fact. Для confirmed absence
   повторно проверить observed head: изменившийся head → PUBLICATION_STALE, не
   переключаться на latest. Пока внешнего receipt port нет — PUBLICATION_UNAVAILABLE.
2. Acquire read lease точной publication с namespace identity; проверить source,
   metadata и expected coverage receipts. No-publication возвращает absent только
   после достоверного admission. Read не создаёт directory/manifest/cache file.
3. Domain resolves scope, сравнивает required vs published coverage. Невключённые
   в публикацию scope parts → missing. Listed reference, файл которого пропал,
   всегда DECLARED_ARTIFACT_MISSING, даже если другой scope incomplete.
4. Проверить все declared artifacts requested scope, hashes, format, coordinates,
   decoded coverage. Ошибки имеют приоритет перед missing; не ранний missing,
   скрывающий corruption соседней requested части. Не сканировать чужие world tiles.
5. Выдать only verified refs: каждый artifact реально открыт/hash/decode checked
   под lease, не просто manifest path. Bulk не копировать в DAG output. Consumer
   получает resolver read через domain method/lease, не WorldPackReader/filesystem.

Ref lifetime: operation lease закрывается при завершении/отмене, durable retention
receipt результата удерживает closure до release владельцем результата. Resume
сохраняет identity/publication/digests/receipt, повторно acquires pin и validates
retention перед использованием. Истёкший receipt → REF_STALE; нельзя автоматически
читать latest или готовить bake. Cancel до выдачи результата освобождает lease,
не создаёт transferable receipt; после выдачи retention принадлежит consumer.
GC обязан уважать retention. Это требование к external owner, не готовая возможность
PackReadContext/Snapshot. Cache keys включают publication+digest+artifact identity.

Valid empty: index.locations=() при опубликованном empty census корректен;
нулевой expected world-light tile set требует metadata/index/climate и coverage
receipt; world без settlements имеет full topology=() NOT_APPLICABLE. Пустые
terrain columns/runs допустимы только если decoded artifact явно покрывает весь
запрошенный объём и формат допускает sparse empty (не делать вывод по len=0).
Отсутствие run не является Spatial dry. Невалидный zero world extent — INVALID_SCOPE,
не empty found. Поля manifest с пустым path без declared ref — отсутствие части;
nonempty declared ref с потерянным blob — Error.

## 9. Spatial / GEO / C11 compatibility

Приняты SP-1 §14.12/14.14, GEO EF-1.12/14 и joint compatibility; SP-P0 целиком и
SP-M не приняты. Bake coverage — наличие опубликованных artifact частей; Spatial
coverage — wet/dry/unknown query facts. Ни world light/full, ни L2 found не дают
Spatial known/dry и не делают L0 canonical water source. Required water evidence
для consumer надо получать по принятому SP-1 read contract/EF-1 source revision;
здесь water facts в payload не добавлены. Unknown не terrain missing.

C23 применяется по published settlement census, C11 — отдельно по structure
applicability/readiness contract. L2 output вообще не содержит ready_detailed=true.
Для building/room accepted terrain found может сопровождаться внешним C11 missing;
consumer обязан проверить применимый C11 до placement. Interior transitions и
structure_status/packed_district_uids не заменяют C11 evidence. SP-M projection
не становится implicit шагом read. Full topology не физическая hydrology topology.

SP-P0 §15.17: поддержать полный namespace lifetime exclusion всех mutation sinks,
resolved path identity и single-supervisor/drain requirements; mtime cache и
process-local lock не pinning. Не активировать V2 reader поверх продолжающих
legacy writers. Diagnostic admission учитывает producer-backed concrete enum
closure, неизвестный enum — отказ, не coercion/удаление. Caps одновременно:
shard 4 MiB/262144 TLV, root 16 MiB/524288, depth64/container65536/field4096.
Exceeded cap → явный error/admission refusal без truncation facts; numeric IO SLA
и весь codec freeze этим документом не принимаются. Snapshot draft adapters не
implementation pin/read ports.

## 10. Exact target file/import map и direct counts

Предлагаемые файлы существуют **только в этой карте**. Prefix A =
`backend/app/application/worldData/`, D = `backend/app/dataModel/`.

| Target file | Symbols / responsibility / allowed imports |
|---|---|
| D/worldPack/read/bakeReadRequest.py | BakeIdentity, PublicationExpectation variants, LightReadRequest/WorldLight/RequestLight, FullReadRequest, LocationL2ReadRequest, ReadControl; imports app.dataModel.identity.uid.EntityUid; локальные FineBox2D(x0,y0,x1,y1), FineBox3D(x0,y0,z0,x1,y1,z1), TileKey(gx,gy), WorldBounds(kind=WORLD_BOUNDS) в этом же файле с integer half-open границами §6; это request scopes, не копия terrain wire |
| D/worldPack/read/bakeReadResult.py | ResolvedBakeScope, OwnerVolume, Found/Missing, MissingBakePart, Light/Full/LocationL2BakeData, VerifiedBakeRef, BakeReadEvidence; imports request, enums, error; никаких storage paths/SQL models |
| D/worldPack/read/bakeReadEnums.py | BakeReadKind(FOUND/MISSING), MissingReason, MissingPartKind, LightCoverageKind, BakeLod(TERRAIN_L2), TopologyApplicability, BakeReadErrorCode с values §7 |
| D/worldPack/read/bakeReadError.py | BakeReadError + typed causes; imports enums/request; не HTTP exception |
| A/pack/read/packLightBakeReader.py | PackLightBakeReader.read_light_bake; request/result/errors + pinned storage decode; не planner/progress |
| A/pack/read/packTerrainBakeReader.py | PackTerrainBakeReader.read_location_l2; hierarchy receipt resolution и L2 decode, не materializer |
| A/pack/read/packFullBakeReader.py | PackFullBakeReader.read_full_bake; imports light reader, topology port, result. Один lease; union missing; не registry |
| A/settlementOutdoor/settlementTopologyRead.py | SettlementTopologyRead.read_published_topology; owns C23 admission/output refs; imports accepted publication port + bake result; не DistrictSlot/assembler |
| A/pack/read/packReadServices.py (existing) | build_pack_read_services добавляет light_bake, full_bake, terrain_bake поля после приёмки external ports. Явные constructor dependencies publication_access, coverage_access, topology_read; не передавать planning/capture новым readers |

Factory call target: existing `core/container/packs.py:pack_read_services` создаёт
readers после разрешения external ports; DAG импортирует только named readers и
D/worldPack/read contracts. Никаких imports io/worldPackReader, db, assembler из
ноды. Externals §11 пока не имеют утверждённых import paths: выдуманный Snapshot
adapter здесь не импортируется. Internal nested calls ограничены lease→receipt→
decode/validate; full→light+topology (не public reacquire и не DAG call).

Direct file counts (Get-ChildItem -File, без descendants, baseline 2026-11-02):
A/pack/read **22→25**, A/pack/io **11→11**, A/settlementOutdoor **15→16**,
D/worldPack **1→1**, D/worldPack/meta **7→7**, wire **18→18**, bake **14→14**,
A/pack/bake/plan **4→4**. Новый D/worldPack/read **0→4** без __init__.py;
если package policy требует __init__, отдельно **+1**, не скрывать в counts.
Всего proposal **8 новых файлов**, существующий factory/container изменяются
позже; реальное изменение сейчас **0 production files**. Отдельный registry,
центральный facade и копия wire payload schemas не нужны.

## 11. Точные внешние OPEN contracts / межплановые предложения

Это список предложений владельцам; другие планы/граф не изменены. Каждая строка
блокирует соответствующую реализацию до совместной приёмки, не «решить в коде».

| Owner / OPEN | Требуемая внешняя поверхность / критерий закрытия |
|---|---|
| Publication / Snapshot + Pack lifecycle | acquire_exact(world_uid, publication_id, root_digest) → read lease immutable namespace+closure; observe_absence(world_uid, head_revision, receipt) → verified absence; retain/reacquire/release(receipt), cancellation-safe lease.close. Exact accepted type/import/retention duration/GC authority пока отсутствуют. Требуется concurrency proof со всеми writers §15.17; Snapshot draft не заменяет его |
| Pack coverage producer | Published receipt: identity, grid/frame, canonical expected world-light tile set, full bounds, hierarchy/terrain-owner census, source digest, artifact completeness coverage. Producer обязан покрывать territory/segments/interiors §6, не endpoint-only collector; требуется schema/version и producer evidence до public read implementation |
| Settlement topology owner | read_published_topology(lease, settlement_uids tuple, source_revision) → verified immutable C23 closure refs либо exact missing settlement IDs; отказ stale/corrupt отдельно. Closure включает district census/slots, CITY nodes+edges/gates и применимость; empty authored layout требует явного authored closure receipt, не should_skip_topology=true. Exact transport/version/publication join ещё не принят |
| C11 / structure owner | Отдельный applicability + readiness read evidence по target/required scope/source/publication, причины missing и valid no-interior. Ни L2 read, ни full не владеют этим решением. До приёмки нельзя объявлять ready detailed по одному terrain found |
| GEN consumer / coordinate requirement | Принять отдельный read_wilderness_l2 с request identity/publication/XYZ union/TERRAIN_L2; output как L2 coverage refs с target=coordinates без owner NamedLocation. Отдельно согласовать preparation, trusted provenance и caller; здесь не добавлены новые nodes/CALLs |
| SP-3 / Pack errors | Согласовать mapping typed Spatial/storage failures в bake error без превращения wet/dry/unknown в missing. Water evidence остаётся separate typed read; numeric bounded-read budgets owner SP-P0/SP-3, не обещание этого трека |

## 12. Сквозные сценарные трассы и предмет приёмки

| Сценарий | Трасса / проверяемый outcome |
|---|---|
| Found light | exact pin→source/coverage receipt→scope tiles+index+climate+metadata decode/hash→retained refs; downstream использует тот же publication |
| World partial, NamedLocation complete | world-light required A+B, published A; world missing B. Request A→found без world reader/full call; unknown world tiles не проверяются |
| Scoped partial | request A+B, published только A→INCOMPLETE с B; node передаёт missing отдельно в preparation. Read ничего не дописывает |
| Full found/valid empty topology | required L0 complete + census settlements=()→full found NOT_APPLICABLE; при settlements S нужны C23 closures S, один missing→INCOMPLETE C23(S) |
| Empty data | explicit covered empty index/terrain artifact→found refs; отсутствие columns без coverage evidence→CORRUPT_ARTIFACT, не empty success |
| Absent | подтверждённый no-head receipt + authoritative source scope→ABSENT всего required scope; нет receipt→PUBLICATION_UNAVAILABLE |
| Missing declared artifact | listed tile/ref исчез после publication→DECLARED_ARTIFACT_MISSING, даже при другом legitimately absent tile |
| Corrupt / unsupported | hash/decode/coordinate mismatch→CORRUPT_ARTIFACT; unknown schema/codec→UNSUPPORTED_FORMAT; OS read failure→READ_FAILURE |
| Stale / wrong world | request world W, root W2→WORLD_MISMATCH; wrong source→SOURCE_MISMATCH; pinned head/root mismatch→PUBLICATION_STALE; никогда missing/None |
| Room target | published room→building→district→terrain owner mapping→L2 scope refs; room UID blob не ищется; ambiguous/missing census→OWNERSHIP_UNRESOLVED |
| Terrain found, C11 absent | L2 found остаётся terrain verdict; placement ждёт внешнего применимого C11. Наличие settlement blob не закрывает gate |
| Coordinates | consumer требует full bounded scope, затем отдельный wilderness L2 контракт; read_location_l2 отказывает coordinate input, fake NamedLocation нет |
| Cancellation | checkpoint во время decode→cancel exception, закрыть lease; нет preparation/publication/partial success; restart exact pin |
| Resume / GC | durable result receipt→reacquire exact closure→validate digest; retained refs доступны. Expired/GC violation→REF_STALE/DECLARED_ARTIFACT_MISSING, не latest fallback |
| Concurrent write | target namespace writer/drain exclusion не доказан→activation blocked; mtime повторное чтение не обеспечивает atomic publication |

Пользовательская приёмка требуется по конкретным решениям: (1) владельцы и
композиция §5.2; (2) расширенное world-light territory+geometry coverage и scoped
правило §6; (3) explicit publication/absence и immutable ref lifetime §§7–8;
(4) full=C23 closure, L2 leaf ownership и отдельный coordinate requirement;
(5) errors/valid empty и §9 boundaries; (6) target map/counts и external OPEN §11.
Приёмка этих документов не закрывает external ports, implementation debt,
SP-P0/SP-M, GEN bindings, публикацию или cutover. Следующий шаг после приёмки —
совместное закрытие названных внешних контрактов, а не выбор неизвестных решений
во время реализации. GEN-READ-1/2/3 остаются OPEN до реализации и evidence.
