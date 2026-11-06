# GEN-BAKE-READ — публичное чтение результатов bake

**Памятка агента:** перед продолжением прочитать [шпаргалку границ и исправлений](./gen-bake-read-agent-cheatsheet.md). Актуальные решения пользователя — §§13–15; текущая проверка и поправки proposal — §17; исходные proposals не являются принятым freeze.

**Статус:** EXACT CONTRACT PROPOSAL / НА ПРИЁМКЕ, 2026-11-02. Локальные решения и внешние OPEN contracts — §§5–12; freeze пользователем не принят. Поручение пользователя: отдельное требование к генератору вне scope GEN-DAG с mapping нода → публичный метод → техдолг. Только документы; код и cutover не разрешены.

**Owner:** генераторный домен / Pack read и владельцы topology. GEN-DAG задаёт требования потребителей и реализует bindings после приёмки публичных контрактов. DAG не собирает результаты из файлов, manifest и SQL самостоятельно.

**Актуальный независимый review:** §17.10 имеет приоритет над противоречащими формулировками proposal ниже. D1–D7 не приняты; R0 document review выполнен с замечаниями, acceptance не закрыта.

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
2. `read_full_bake(world identity, publication expectation, required full scope)` → proposed full L0 результат. Consumer full требует отдельной видимой композиции с C23; D1 и её совместный контракт ещё на согласовании (§17.10).
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

## 5. Первоначальный exact proposal GBR-1 (2026-11-02)

**Историческая редакция: отмены §§13–15 и поправки §17 имеют приоритет, особенно full composition, refs, lifetime и file map.**

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
| [packTileCollect](../../backend/app/application/worldData/pack/bake/plan/packTileCollect.py): location_anchor_tiles, declared_hydro_tiles, light_l0_tiles, world_bounds_l0_tiles | light anchor-only и endpoints-only hydro; full world_bounds; debug cap не coverage | Действующая семантика light/full; сохраняется без расширения coverage. Read не запускает preparation |
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

**World light coverage (параметр чтения существующего light_bake):** expected set
сохраняет семантику `packTileCollect.light_l0_tiles`: tiles static location anchors
∪ tiles endpoints declared coastline/lake shoreline/river segments, при включённой
hydrology. Territories, intermediate segment tiles и polygon interiors автоматически
не добавляются. Это намеренная оптимизация light_bake, не incomplete full_bake.
Положительный max_tiles — debug cap; product default uncapped. World read проверяет
полный product light set, не объявляет capped debug output complete.
Expected set должен быть связан с source revision; read не запускает preparation.
Опубликованный coverage receipt — proposed consistency mechanism, не новый bake mode.
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

Приняты SP-1 §14.12/14.14, GEO EF-1.12/14 и joint compatibility. Актуальные отдельные документальные приёмки Spatial — §15.19 (P0 design) и §16.16 (M); executable storage/read/materialization не приняты. §15.17 сам по себе не полный freeze. Bake coverage — наличие опубликованных artifact частей; Spatial
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
| Pack coverage producer | Published receipt: identity, grid/frame, canonical expected world-light tile set, full bounds, hierarchy/terrain-owner census, source digest, artifact completeness coverage. Producer сохраняет существующий light anchor/endpoint set и отдельно full bounds; требуется schema/version и producer evidence до public read implementation |
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
композиция §5.2; (2) существующее world-light anchor/endpoint coverage и scoped
правило §6; (3) explicit publication/absence и immutable ref lifetime §§7–8;
(4) full=C23 closure, L2 leaf ownership и отдельный coordinate requirement;
(5) errors/valid empty и §9 boundaries; (6) target map/counts и external OPEN §11.
Приёмка этих документов не закрывает external ports, implementation debt,
SP-P0/SP-M, GEN bindings, публикацию или cutover. Следующий шаг после приёмки —
совместное закрытие названных внешних контрактов, а не выбор неизвестных решений
во время реализации. GEN-READ-1/2/3 остаются OPEN до реализации и evidence.

## 13. Решение пользователя: публичные read-ноды и видимая композиция (2026-11-02)

**Принят только архитектурный принцип этого раздела.** Пользователь подтвердил:
публичные методы находятся в доменах, публичные read-ноды вызываются другими
нодами; места и порядок вызовов должны быть видны в большом DAG. Это не приёмка
всего GBR-1, новых NodeIds, CALL bindings или production реализации.

Этот раздел заменяет предложение §5.2 о скрытой full-композиции внутри Pack.
`PackFullBakeReader` и factory field `full_bake` **отозваны** из target map §10.
Упоминания этого класса и full→light+topology nested calls в §§5–12 являются
историей первоначального варианта, а не действующим implementation target.

### 13.1. Два уровня

- Доменный публичный метод владеет конкретной read operation: разрешение scope,
  проверка completeness, чтение/декодирование artifacts, typed data/refs/errors.
  SQL/filesystem/manifest остаются внутри домена.
- Публичная read-нода — переиспользуемая единица DAG с явными Input/Output;
  другая нода вызывает её через engine CALL/RETURN. Чужой execute() напрямую
  не вызывается. Cancellation/resume/результаты проходят штатный lifecycle.
- Композиция самостоятельных public reads видна как вызовы read-нод. Не прятать
  её в facade/helper, чтобы затем воспроизводить или обходить в разных consumers.
  Внутренний decode отдельных blobs не обязан становиться отдельной нодой:
  storage implementation и самостоятельная domain operation — разные границы.

### 13.2. Full: действующая схема, требующая concrete binding freeze

```text
full-read composition node (existing consumer role check_full_bake)
  → CALL public light-read node для required full L0 scope
  → CALL public C23 topology-read node для required settlement closures
  → typed aggregation light + C23
```

Обе read-ноды получают одну explicit pinned publication identity/source/frame и
совместимый retention context. Identity сама не является живым lease: каждый
домен обязан acquire/validate её по принятому publication port, а composition
lifecycle должен удерживать общую closure до завершения обоих reads. Между CALLs
нельзя выбирать latest. Exact shared retention/lease handoff остаётся external
OPEN §11; process-local объект lease не становится сериализуемым node Input.

Full-агрегация использует только typed outputs read-нод, без storage introspection.
Проверяет совпадение identity/publication/scope, объединяет exact missing parts;
ошибки не понижает до missing. Missing одного child не повод пропустить другой
required read и скрыть его ошибку. Ноль settlements требует authoritative
applicability evidence; только тогда topology NOT_APPLICABLE без C23 read.

`read_full_bake` сохраняется в реестре как требование full-result, но больше не
считается согласованным именем агрегирующего Pack domain method. Его уровень и
имя (public node operation либо иной accepted domain contract) требуют отдельной
приёмки. Сохранение прежней строки карты не разрешает скрытый Pack composite.

Необходимые новые read-node roles, их NodeIds/parents/CALLs не назначены этим
решением. Межплановое предложение GEN: предъявить explicit light/C23 composition
и reusable water/terrain read roles на отдельную приёмку. Общий граф и GEN-DAG
не изменяются в этом треке.

### 13.3. Другие consumers и корректировка map

Физический consumer может CALL terrain-read и water-read ноды с согласованными
publication/source inputs. Water reader вызывает публичный SP-1/EF-1 domain read;
full не становится prerequisite для каждого самостоятельного чтения. Это пример
применения принципа, не добавление physics nodes/edges или готового binding.

Сохраняются PackLightBakeReader/read_light_bake, PackTerrainBakeReader/read_location_l2,
SettlementTopologyRead/read_published_topology как proposed domain targets.
Удаление одного PackFullBakeReader из первоначальной карты меняет direct target
count A/pack/read **22→24** и число новых domain files **8→7** (без __init__).
Existing factory получает только light_bake/terrain_bake; topology binding принадлежит
его owner. Exact node class/factory/POJO/import map композиции требует отдельного
GEN contract freeze: в owning GEN документы здесь изменения не вносятся.

Все остальные external OPEN §11, coverage proposals и I/O/error сценарии остаются
на приёмке. Принятие видимой композиции не закрывает publication ports и не
разрешает реализацию. Новый acceptance scenario: execution trace обязан показывать
самостоятельные light/C23 CALLs, их inputs/publication, outputs и cancellation/resume;
дублирующей скрытой full-композиции в Pack нет.

## 14. Уточнение семантики по генератору; без новых bake-сущностей

**Решение пользователя:** сохранить существующие light_bake, full_bake,
detailed_bake. World/request coverage — параметры чтения, не новые виды bake.
Предложение расширить light до territories/full hydro geometry отозвано.
Этот раздел имеет приоритет над несовместимыми первоначальными предложениями.

| Существующая операция | Подтверждённое поведение | Source |
|---|---|---|
| light_bake | L0 на tiles static anchors ∪ declared hydro endpoints; cap только debug. Общий pipeline также пишет coarse climate/index, fine climate зависит от policy | [packTileCollect](../../backend/app/application/worldData/pack/bake/plan/packTileCollect.py), [PackTilePlanner](../../backend/app/application/worldData/pack/bake/plan/packTilePlanner.py), [PackMaterializationOrchestrator](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py) |
| full_bake | Тот же L0 pipeline, все macro tiles world_bounds/resolved AABB, без light cap; full path применяет world seam. Не автоматический весь L2 | [PackMaterializationOrchestrator.materialize_full_pack](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py), [WorldMapBakeOrchestrator](../../backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py) |
| detailed_bake | Existing scope=location либо wilderness. Location: territory volume индексированной location, только пересекающие rects. Wilderness: explicit tile либо незавершённые L0 tiles с optional cap, whole-tile rects. Parent L0 обязателен | [DetailedBakeRequest](../../backend/app/dataModel/worldPack/bake/detailedBakeScope.py), [detailedBakeScope](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py), [detailedBakeRefine](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py) |

Detailed scope resolver пропускает location, отсутствующую в pack index; это
legacy job skip, не доказательство successful public read. Leaf→owner разрешение
остаётся OPEN и не приписывается этому resolver. Detailed location по default
дополняет fine climate; grade stages optional. Manifest bake_mode хранит light/full,
detailed не становится третьим значением этого поля (PackBakeApiMode допускает
light/full/detailed). Это техническое различие representation, не новая сущность.

Требование consumer full-check получить L0 + C23 не означает, что сам
materialize_full_pack строит C23: исследованный body строит L0. C23 остаётся
самостоятельной read operation с видимой композицией §13. Аналогично terrain L2
не доказывает C11: контракт DetailedBakeRequest описывает L2 then applicable C11,
но наличие terrain artifacts не является evidence завершения этой цепочки.

Request scope не меняет производственную семантику light: он определяет, какую
часть существующих L0 результатов требует consumer. Full world bounds и proposed
bounded consumer full requirement различаются явно; bounded read не переименовывает
и не превращает full_bake producer в новую scoped bake operation.

Предложение отдельного имени read_wilderness_l2 **отозвано как выбранное решение**.
Wilderness — уже existing scope detailed_bake; нужно согласовать чтение его
результатов с coordinate input, не новый bake kind и не фиктивная NamedLocation.
Точный public read signature (расширение existing detailed-result read или отдельный
узкий read port) остаётся предметом приёмки; автоматически API не расширяется.
Названия новых классов/POJO в §10 — только первоначальные proposals: они не
разрешают ввод новых сущностей без проверки reuse existing generator contracts.

## 15. Принятая архитектура domain readers (2026-11-02)

Пользователь принял архитектурное предложение: у каждого домена публичный
reader, возвращающий принадлежащий этому домену типизированный контракт.
Чтение поддерживает уровни от целой сущности через её часть/окно до минимальной
доменной единицы. Минимальная единица определяется смыслом домена, а не единым
универсальным cell DTO. Это принятие архитектуры, не concrete class/API freeze.

1. Явные операции reader соответствуют семантике домена; один универсальный
   метод или одинаковый набор CRUD/read методов всем доменам не навязывается.
2. Контракт сообщает identity, revision/publication/provenance, фактический scope,
   данные либо проверенные immutable refs, valid empty/absence/errors.
3. Целая сущность может возвращаться metadata+refs, без eager загрузки всего bulk.
   Части/минимальные элементы читаются тем же domain reader в согласованной версии.
4. Публичные read-ноды вызывают domain readers; consumers вызывают read-ноды через
   engine CALL/RETURN. Композиция самостоятельных domain reads видна в DAG.
   Один внутренний метод reader не требует автоматически отдельной ноды.
5. SQL/filesystem/decode принадлежат domain infrastructure. Read не выполняет
   preparation/generation/repair/write. Существующий метод со словом read/get
   не считается подходящим без проверки фактических nested calls.
6. Сначала сущности/уровни/существующий reuse, затем exact contracts/methods и
   только затем class/file/node map. Предложенная ранее карта §10 не является
   разрешением создать новые классы в обход этого порядка.
7. Архитектура не вводит новый bake kind, central reader/router/registry, общий
   WS CRUD и не меняет принятые Patch/Snapshot responsibilities.

CRUD исследован отдельно: [инвентаризация генераторов и domain storage](./generator-domain-crud-inventory.md).
Это статическое исследование, не новый owning implementation plan. Изменения
[Patch/Snapshot owning](./world-domain-patches-snapshots.md), графа и GEN-DAG не внесены.

## 16. Перепроверка read reuse

Явные методовые метки, nested call evidence и исправление прежнего обобщения —
[CRUD inventory §8](./generator-domain-crud-inventory.md#8-повторная-проверка-read-candidates--явный-exclusion-ledger-2026-11-02).
Confirmed preparation: WildernessRegionReadService.outline→require_plan_inputs→
prepare→PlanningService.get_or_build (cache miss может build). Progress probe_extent
**не** вызывает preparation: только capture/report/probe, затем classifier tile plan.
Read/decode errors conflated с absence: load/require_parent_light,
PackReadContext.climate_tile_field. Render/gameplay/debug file-absence fallback
отмечены отдельно; arbitrary errors им без evidence не приписываются.

## 17. GBR-2 — продолжение исследования и согласованный предмет review (2026-11-02)

**Verdict: READY FOR DOCUMENT REVIEW; NOT ACCEPTED / NOT CODE-READY.** Это новая редакция существующего проекта, не параллельный план. Предложения ниже требуют решения пользователя и владельцев внешних contracts. Архитектурные решения §§13–15 сохраняются; прежние противоречащие signatures/композиция/file map §§5–12 заменяются этим разделом, не являются альтернативами реализации.

### 17.1. Baseline, повторная проверка и dispositions

Прочитаны отчёты §§5–16, agent cheatsheet, consumer §§8–9/9.5/16, последние Spatial/Snapshot записи и отдельный LIGHT-HYDRO-ROUTE report. Git history owning: 6336c2a7, e468119d, e2835a91, ab53ad2c. На входе два разрешённых файла чисты; чужие изменения physics-spatial-dynamics, общего графа и untracked generator-light-hydrology-route-trace сохранены. Шпаргалка устарела в части P0/M приёмки; нормативны последние owning-записи. Статическая проверка не означает независимый runtime PASS.

Повторно прочитаны реальные тела methods из ledger §5.1, wire types и factory. Уточнения:

- WorldPackReader._decode_file → TileCodec.decode → kind-specific parse; read_location_terrain/read_wilderness_chunk используют cache UID/coordinates. Manifest reread по mtime/size не обеспечивает snapshot. Файлы читаются целиком; bounded verified stream не доказан. Retain codec/parser algorithms после отдельного format/limit audit; **replace binding/cache/error admission** для публичного пути, не reuse reader instance из legacy context.
- parentLightLoad.load_parent_light ловит FileNotFoundError/OSError/ValueError → None; require переводит None в MissingParentLightError. Cache (world,gx,gy) не pin. Retain preparation callers из §5.1; replace только public binding. Remove helper запрещён до отдельного closure всех preparation/halo/climate callers.
- PackLoadingProgressFacade → probe_extent → classifier; classifier вызывает PackTilePlanner.plan дважды и сравнивает manifest paths, обрезает missing list до 64, при empty index использует anchored SQL locations. **Это не bake**, но также не authoritative published read. Retain progress routes [map.py](../../backend/app/api/routes/map.py); исключить из public read graph.
- PackFineTerrainReadFacade.read_location_terrain при entry absent возвращает debug status, при пропавшем blob — column_count=0; read_merged_cell вызывает gameplay.get_cell. Retain debug/gameplay callers; не переносить их semantics в новый контракт. Никакое значение ok/100%/column_count не completeness proof.
- [FineTerrainChunkWire](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py) frozen только сверху; columns/runs — lists, z-runs inclusive. Manifest hashes optional, lists mutable, paths не refs. Retain decode schemas; public immutable projection/verified refs обязательны. Conversion run z1→exclusive z1+1 проводится на domain boundary, не в DAG; отсутствие колонки не доказывает covered empty.
- [settlementOutdoorTopology](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorTopology.py): topology_census пропускает district без frozen slot; should_skip_topology может вернуть true для authored children; load_topology_slots использует templates/context и возвращает assembler DistrictSlot. Caller [settlementOutdoorPackingJob](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py) — packing, не public read. Retain helpers; replace их роль readiness proof immutable topology reader. Remove только после отдельной C23 caller migration. C24 settlement.zst не C23 receipt.
- Existing [WorldPublicationRef](../../backend/app/dataModel/worldSnapshot/identity/publication.py) уже имеет world_uid/publication_id/pack_hash/snapshot_head/active_timeline_id/gameplay_started. Existing [ArtifactRef](../../backend/app/dataModel/artifacts/references.py) уже имеет kind/format_key/format_version/content_hash/nbytes/row_count. **Reuse этих identities**, не новые строковые publication_id/artifact_id/digest DTO из §7. Наличие типов не доказывает namespace pinning или доступность bytes.

Все legacy entries §5.1 получают общий transition gate: accepted method + independent parity/negative/caller evidence → explicit consumer migration → usage closure → возможное remove. В этом проекте ни одного безусловного remove production helper нет. Direct API→generator route из нового trace относится к GEN cutover owner, не удаляется в read-треке.

### 17.2. Ownership и устранение full-composition конфликта — решение на согласование

Предлагается сохранить три запрошенных имени с точным разделением:

1. **read_light_bake** — Pack-owned L0 reader: WorldLight использует опубликованный product anchor∪hydro-endpoint set; RequestLight требует все explicit boxes независимо от world-light set. Index/coarse climate/metadata обязательны в обоих случаях.
2. **read_full_bake** — второй метод того же Pack L0 reader, читает **L0 full producer result** для WorldBounds либо bounded boxes, возвращает FullL0BakeData. Не вызывает light reader/C23 reader и не обещает consumer full readiness. Общий private decode/coverage алгоритм допустим.
3. **read_location_l2** — terrain reader с NamedLocation identity, explicit volumes и published owner mapping. Terrain-only; applicable C11 отдельно.

Consumer `check_full_bake` требует результат **FullL0 + C23**. Его композиция остаётся видимой в DAG через public read operations; полное соответствие input publication/source/frame обязательно. Pack reader не принимает готовый C23 result ради скрытого агрегирования. `FullBakeData(light,topology)` §7 больше не output public Pack method; это требование будущей совместной GEN composition, exact node contract OPEN. Предложение именования устраняет противоречие, но пользователь должен явно согласовать семантику read_full_bake; автоматически менять consumer bindings нельзя.

Topology domain reader выдаёт whole settlement closure либо его domain-owned parts (district slot/node/edge) по одной revision; whole может быть refs. Empty census даёт NOT_APPLICABLE, incomplete authored topology — missing, contradictory published census — error. Pack не определяет C23 numerical/topology correctness и не читает live SQL вместо versioned closure.

Coordinate/wilderness: существующий detailed scope подтверждён, но три операции не покрывают вход без UID. Предлагаемый **следующий контрактный выбор**, не новое имя API: тот же terrain reader должен иметь отдельную explicit coordinate operation с common L2 result без target UID, по canonical XYZ union и published chunk layout. Не overload read_location_l2 и не возвращать отозванное имя read_wilderness_l2 как принятое. Приёмка названия/сигнатуры с GEN owner — design blocker coordinate ветви, не blocker NamedLocation implementation.

### 17.3. Required coverage: источник истины и допустимая пустота

Published coverage receipt предлагается как immutable Pack artifact, связанный с pack_hash, source/frame revision, format/grid/topology и producer operation identity. Содержит product light set, world bounds, declared artifact mapping и produced coverage; hierarchy/ownership и settlement applicability — refs на отдельно принадлежащие доменам versioned census. Receipt не запускает planner. Expected request boxes приходят от caller; domain проверяет их принадлежность target по pinned census и рассчитывает tile intersection чистой арифметикой. Нельзя вычислять expected только из фактически записанных tiles: capped debug bake иначе станет complete.

Для L2 receipt содержит exact covered XY×Z unions и empty-coverage declarations, terrain-owner identity, parent L0/source dependencies и required sidecars по versioned terrain format. Parent coverage dependency относится только к requested terrain; whole-world L0 не нужен. Grade-dependent sidecars, если format объявляет их required, проверяются как closure; fine climate отдельно от terrain readiness, C11 отдельно. No runs может означать air/empty лишь по explicit coverage/format semantics, не по размеру списка.

No publication не требует несуществующего manifest: request должен иметь source-bound expected-scope evidence от capture owner; для WorldLight это product expected-set receipt, для named leaf — hierarchy/scope receipt. Отсутствие этих evidence → PUBLICATION_UNAVAILABLE/OWNERSHIP_UNRESOLVED, не fabricated empty missing_scope. Их выпуск относится к preparation/capture, read лишь проверяет. Не опубликованное required artifact → missing; declared reference, отсутствующий в storage, → error.

Seams: canonical split boxes по принятому topology/frame, отрицательные координаты floor division; не соединять split в гигантский AABB. Никакого скрытого halo. Full C23 applicability пересечение settlement territory с requested scope, затем whole closure settlement. Unrequested world tiles не сканируются. Shared обязательные index/climate проверяются даже для scoped read.

### 17.4. Exact semantic Input/Output/Error delta (всё PROPOSED)

Reuse EntityUid/RevisionHex, WorldPublicationRef/ArtifactRef по ссылкам §17.1. Existing types не расширяются этим документом. Boxes/TileKey из §10 сохраняют half-open integer semantics; strict bool rejection, nonempty normalized disjoint union, frame/topology обязательны. Domain normalization выдаёт canonical representation либо INVALID_SCOPE, не сужает scope.

```text
BakeIdentity(world_uid: EntityUid, source_revision: RevisionHex, frame_revision: RevisionHex)
PinnedBake(publication: WorldPublicationRef, coverage_ref: ArtifactRef,
           retention: ExternalRetentionEvidence)
NoBake(expected_scope: ExpectedScopeEvidence, absence: ExternalAbsenceEvidence)
PublicationExpectation = PinnedBake | NoBake
LightReadRequest(identity, publication, coverage: WorldLight | RequestLight)
FullReadRequest(identity, publication, scope: WorldBounds | tuple[FineBox2D,...])
LocationL2ReadRequest(identity, publication, target_uid: EntityUid,
                      volumes: tuple[FineBox3D,...], lod: Literal[TERRAIN_L2])
VerifiedBakeRef(artifact: ArtifactRef, identity: BakeIdentity,
                publication: WorldPublicationRef, part: BakePartScope)
FullL0BakeData(tiles: tuple[VerifiedBakeRef,...], locations_index: VerifiedBakeRef,
               coarse_climate: VerifiedBakeRef, metadata: VerifiedBakeRef)
LightBakeData = та же форма данных L0, semantics различаются request/evidence
LocationL2BakeData(target_uid: EntityUid, owners: tuple[OwnerVolume,...],
                   terrain: tuple[VerifiedBakeRef,...], dependencies: tuple[VerifiedBakeRef,...])
BakeReadEvidence(request_scope_digest: RevisionHex, coverage_ref: ArtifactRef,
                 verified_refs: tuple[ArtifactRef,...], retention: ExternalRetentionEvidence)
Found[T](identity, publication: WorldPublicationRef, resolved_scope, data:T, evidence)
Missing(identity, publication: PublicationExpectation, requested_scope,
        reason: ABSENT|INCOMPLETE, missing_scope: tuple[MissingBakePart,...])
```

ExternalRetentionEvidence/ExternalAbsenceEvidence/ExpectedScopeEvidence — **незакрытые external type slots**, не предлагаемые production classes или произвольные str. Их semantic obligations ниже точны, import/format принимает owner. NoBake missing не содержит фиктивный resolved_scope из manifest. Existing `WorldPublicationRef.pack_hash=None` требует отдельного подтверждения absence; сам None не proof. Snapshot head не добавляет runtime overlay к baked data.

Public signatures: `async read_light_bake(request, *, control)` / `read_full_bake(request, *, control)` / `read_location_l2(request, *, control)` → соответствующий Found|Missing. Control — invocation-only cooperative cancellation, не сериализуемый request field; concrete existing cancellation binding проверяется на implementation preflight. Exceptions: BakeReadError с code + immutable tuple[Cause(part, code, diagnostic_id)], identity и expectation; никакого payload/storage path. Используется enum §7 плюс **RESOURCE_LIMIT** для явного refusal из-за лимита; unsupported format отдельно от corrupt. MissingBakePart — tagged variants вместо свободных nullable combinations: Tile(gx,gy), Singleton(INDEX|CLIMATE|METADATA), Terrain(owner_uid,box), Dependency(ArtifactRef). C23 missing принадлежит topology result, не Pack full method.

Поправка review D5 (§17.10), на согласовании: ABSENT означает отсутствие всех required data components; proper subset комплекта, включая index/climate/required sidecars, означает INCOMPLETE. Receipt/retention не data components. Правило «no primary→ABSENT» отозвано как противоречащее GEN §9.1. Valid zero expected set с полными shared artifacts и empty evidence→found. Error проверенных requested declarations имеет приоритет над missing; error collection не обещает исчерпывающий IO после fatal access/limit failure. Стабильный порядок diagnostic causes, cancellation отдельно от result.

Immutable refs разрешаются **тем же domain reader** по exact publication + ArtifactRef + requested sub-scope. Исправленный proposed resolution contract D6: `resolve(ref, scope, access_evidence, *, control)` проверяет subset verified part и действующую fenced retention, возвращает immutable domain projection либо typed error, никогда missing для уже verified declared ref. Минимальные формы L0 cell и L2 column/run сохраняют domain fields/registry identities и covered-empty evidence; storage wire lists напрямую не экспортируются. Exact per-domain leaf projections — R2, field preservation obligations — §17.10. До него whole-ref output нельзя объявлять готовым публичным resolvable API.

### 17.5. Pinning, cancellation и resume — исправление read-only lifetime

Варианты: (a) удерживать coroutine lease после return — отвергнут, не переживает restart; (b) read создаёт durable hold — отвергнут, скрытая запись; (c) **external lifecycle заранее удерживает publication closure**, read только заимствует validated access — предложено. Retention evidence обязано связывать owner operation, world, exact publication/closure, validity/release authority. Выпуск/renew/release — отдельные публичные lifecycle операции owner, видимые orchestration; не внутренний side effect read. Existing artifact holders являются строительными блоками, не принятым read-retention port.

Внутри read: request admission → validate borrowed retention/absence → namespace guard → receipts/census → requested declarations decode/hash/coverage → result → release только transient resources. Cache только memory, key publication+ArtifactRef+decode version. Вся closure уже защищена на входе, поэтому cancellation между final check и delivery не создаёт orphan durable hold. При отмене worker IO должен завершиться/drain до освобождения namespace guard; не считать Task.cancel остановкой file worker. Lifecycle caller владеет eventual release при успехе/отмене/краше, read не делает скрытый rollback или release чужого hold.

Resume: persist request/ref/evidence, external owner подтверждает retention, read повторно проверяет exact pin. **Head advanced не равен stale:** retained old publication допустима при exact-pin policy. Требование current head проверяет внешний consumer/publication admission отдельно; mismatch→PUBLICATION_STALE. Истёкший hold→REF_STALE; storage loss под действующим hold→DECLARED_ARTIFACT_MISSING. Нельзя автоматически перейти на latest. Read не обещает атомарного «current forever» после return; перед placement нужен собственный accepted publication/UOW gate.

Подготовка missing создаёт новую publication: downstream повторно читает нужные части на новой compatible pin; нельзя compose старый L0 и новый C23 без owner-certified compatibility. Full pair проверяется по одному publication/source/frame; несовпадение→SOURCE_MISMATCH/PUBLICATION_STALE, не missing.

### 17.6. Пересмотренная class/factory/file/import map

Это **proposal**, не freeze. Prefixes A/D как §10; legacy files не удаляются. Retain PackReadServices как composition root, но не прокидывать его legacy context/planning/gameplay новым readers. Factory принимает конкретные accepted external dependencies позже; никакого getattr/optional fallback.

| Proposed file | Symbols / imports / counts |
|---|---|
| D/worldPack/read/bakeReadRequest.py | Requests/scopes/identity; imports existing identity, snapshot publication, artifacts; no application control token |
| D/worldPack/read/bakeReadResult.py | Found/Missing, domain refs, evidence; imports request + artifacts; no db/wire lists |
| D/worldPack/read/bakeReadEnums.py | discriminators/error codes; без registry/router |
| D/worldPack/read/bakeReadError.py | Exception + typed Cause; imports enums/request, no result→error reverse dependency |
| A/pack/read/bake/l0Reader.py | PackL0BakeReader.read_light_bake/read_full_bake/resolve; injected pinned artifact access + coverage/census validation; no public domain read nesting |
| A/pack/read/bake/terrainReader.py | PackTerrainBakeReader.read_location_l2/resolve; explicit owner mapping + terrain closure; no preparation |
| A/pack/read/bake/coverage.py | pure required-vs-produced operations, canonical boxes, admission; no planner/SQL/IO |
| A/settlementOutdoor/read/topologyReader.py | SettlementTopologyRead owned C23 payload/projections; own domain contracts, не import Pack FullBakeData; external versioned topology storage binding OPEN |
| existing A/pack/read/packReadServices.py + core/container/packs.py | explicit l0_bake/terrain_bake composition after external contract acceptance; full_bake facade field НЕ добавляется; topology factory belongs topology composition, не hidden Pack nested read |

Current direct counts: A/pack/read 22→22; new bake 0→3; A/settlementOutdoor 15→15, new read 0→1; D/worldPack/read 0→4. Empty package markers при требовании repo policy добавляют по одному в каждый новый каталог (итого +3), до code preflight проверить policy. §10 old 22→25 и PackFullBakeReader отменены. Topology public type file/leaf projections и concrete external adapters **ещё не заморожены**; counts здесь честно относятся к локальному предложению, не всему production footprint. New folders не освобождают от проверки ответственности/размера файлов.

### 17.7. Сквозная проверка proposal (walkthrough, не тесты)

| Сценарий | Проверенная логическая цепочка / stop |
|---|---|
| NamedLocation A ready, world B missing | Published target territory→RequestLight(A)→shared metadata/index/climate + A artifacts→found. B не читается; world-complete не вход |
| NamedLocation light missing | Missing exact A→consumer world_creation готовит full вне read→новая accepted pin→FullL0 и C23 reads→detail. Старый missing не превращается в found по job counter |
| Coordinates/wilderness | Trusted canonical box→FullL0+C23→coordinate terrain operation→C11 applicability→placement. Пока coordinate API не принят, ветвь BLOCKED; NamedLocation API не обход |
| Empty world-light / no settlements | Receipt expected tiles=(), shared artifacts valid→found; topology census empty→NOT_APPLICABLE. Empty manifest без receipt не found |
| L2 sparse empty | Explicit coverage+format empty semantics→found; пустые lists без coverage→error. Water dry/wet не используется |
| Mixed missing + corrupted declared tile | Validate all accessible requested declarations→typed corruption; отсутствующий другой undeclared tile не скрывает error |
| Hash/format/world/source mismatch | Declared missing→DECLARED_ARTIFACT_MISSING; wrong hash/coordinates→CORRUPT_ARTIFACT; unknown format→UNSUPPORTED_FORMAT; foreign world→WORLD_MISMATCH; stale scope/source→SOURCE_MISMATCH |
| Leaf room + ambiguous owner | Traverse pinned census, cycle/overlap without explicit split→OWNERSHIP_UNRESOLVED; не nearest anchor и не файл по room UID |
| Terrain ready / C11 missing | Terrain found сохраняется, detail placement не разрешён; C11 read отдельный owner gate |
| Cancel mid-read / after final validation | Drain transient IO, close borrowed access; external retained closure остаётся caller-owned до его cleanup, no new durable hold/read result |
| Restart + head moved | Reacquire existing retained exact pin→resolve old refs допустим; consumer current policy отдельно. Истёкший hold→REF_STALE |
| Full results разных publications | Composition отказывает до downstream; no latest merge. Re-read на compatible accepted pin |
| Limits / unsupported seam | RESOURCE_LIMIT/INVALID_SCOPE/format refusal, без truncation facts и giant AABB; actual numeric budgets должны быть приняты до runtime |

### 17.8. Атомарные этапы и предложение интеграции в общий граф

Gate IDs ниже локальные proposals GEN-BAKE-READ, не новые GEN nodes. Общий граф не изменяется этим заданием.

| Этап / статус | Prerequisites | Scope / критерий приёмки / stop |
|---|---|---|
| GBR-R0 — исследование, REVIEW READY | existing consumers §§8–9/16 | Evidence §§17.1–7; снять локальные противоречия, принять решения §17.9. Не code |
| GBR-R1 — external semantic agreements, OPEN | R0 review, named owners | Publication/retention/absence, coverage/hierarchy receipt и topology join; exact existing/new types/imports. Не ждать весь Snapshot DONE |
| GBR-R2 — exact method/leaf/file freeze, OPEN | принятые R0 решения + relevant R1 contracts | Три methods, immutable cell/column projections/resolve, closed errors и complete files/counts. Coordinate отдельный slice. Не bindings |
| GBR-R3L — L0 read implementation, NOT STARTED | R2-L, accepted pinned access/coverage producer + отдельная команда | light world/scoped + full L0, negative/empty/hash/limit/no-write tests; остановка на приёмке domain methods |
| GBR-R3T — named terrain implementation, NOT STARTED | R2-T, pinned ownership/terrain coverage, команда | Named leaf/volume closure; отдельные tests; не C11/coordinate/cutover |
| GBR-R3C — topology read, NOT STARTED | topology-owner exact contract, accepted versioned storage/retention, команда | C23 closure/applicability; никакого live SQL fallback; owner acceptance |
| GBR-R4 — lifecycle/cold integration, OPEN | соответствующие R3 + concrete lifecycle ports | restart/resume/drain/GC/race, declared-loss, mixed-publication negatives, actual resolver; не выводить PASS из unit mocks |
| GBR-R5 — consumer handoff, OPEN | accepted relevant R4 + совместный GEN contract | Передать verified public operations; GEN independently implements bindings. Не production switch |

Parallel: R1 publication и topology/coverage исследования независимы; R3L/R3T/R3C могут выполняться после своих gates с раздельными файлами, shared DTO/factory меняет один writer. Whole world readiness не prerequisite scoped slice; topology не prerequisite light/L2; C11 не prerequisite terrain read, но prerequisite applicable placement. Coordinate extension не блокирует три named операции. SP-M не prerequisite L0 design; implementation canonical L2 source compatibility предъявляется только там, где consumer использует canonical SP-4 output.

**Предложение координатору графа:** добавить отдельную ветвь R0→R1→R2→{R3L,R3T,R3C applicable}→R4→R5, с пооперационными gates вместо общего «GEN-BAKE-READ DONE». Рёбра external accepted pin/retention→R3 соответствующей ветви; published scope/ownership→R3T; versioned C23→R3C; R5-L→concrete light binding, R5-L+R5-C→full composition binding, R5-T→named L2 binding. C11→detail consumer readiness, не R3T. GEN совместный design параллелен; GEN cutover не prerequisite R0–R4. Нужные publication ports могут опираться на Snapshot stages, но B PASS не accepted port; B-2 E2E не вход GBR (иначе ложный цикл). Эти межплановые рёбра предъявлены, не применены и не приняты.

External status: Spatial §15.17 requirements, §15.18 diagnostic closure/§15.19 design acceptance и §16.16 materialization acceptance учтены **только в их документальных scopes**. Численные Hydrology TLV caps не распространяются автоматически на L0/terrain formats; их budgets отдельно. GEO-I1 independent PASS не producer/Pack acceptance. Snapshot B повторный PASS не пользовательская приёмка и не lifetime integration. Ни один из этих статусов не закрывает GBR-R1/R4.

### 17.9. Решения на предметное согласование и следующий шаг

**Локальные design decisions:** D1 read_full_bake означает full L0 producer result, consumer full=C23+L0 видимо в DAG; D2 reuse WorldPublicationRef/ArtifactRef вместо строковых дублей; D3 caller-owned pre-acquired retention, reads без durable writes; D4 exact pin отдельно от current-head policy; D5 source-bound coverage/ownership receipts и primary-data absent/incomplete; D6 общий domain resolver и immutable leaf projections; D7 coordinate operation отдельно без fake UID/самовольного имени.

**External contracts:** exact receipt/retention/absence types и lifecycle authority, versioned topology join, published leaf ownership/coverage producer. Это блокеры executable contract freeze, а не повод отложить исследованные D1–D7. **Runtime proofs:** bounded IO, cancellation drain, crash/GC/retention, decoder/format parity, cold scope completeness — будущие проверки, не нерешённые варианты дизайна.

Следующий разрешённый шаг: предметное согласование D1–D7 и cross-owner semantic R1 review, затем заполнение точных external type/import slots и immutable leaf projections R2. Не создавать production POJO/ports/code, не включать bindings и не публиковать мир. Пользовательская приёмка отдельно от этого verdict. Координатору предъявить §17.8 как готовое предложение графа; данный трек не правит чужие owning-планы.

### 17.10. Независимое adversarial review D1–D7 (2026-11-02)

**Verdict: REVISE BEFORE ACCEPTANCE; NOT ACCEPTED / NOT CODE-READY.** Статический review actual types/callers/storage flow выполнен заново, без принятия выводов §17.7 за доказательство. D1–D7 сохраняются решениями на согласование **с поправками ниже**. R0 review выполнен, но R0 acceptance и R1/R2 не закрыты. Ни runtime PASS, ни принятие пользователем из этого не следуют. Изменены только этот документ и реестр методов; межплановые изменения ниже — предложения владельцам.

#### 17.10.1. Проверяемое evidence и границы вывода

Пути в таблице относительно `backend/app/`; symbols позволяют воспроизвести поиск независимо от смещения строк.

| Evidence | Проверенный факт / следствие |
|---|---|
| `dataModel/worldSnapshot/identity/publication.py::WorldPublicationRef.coherent_refs` | Проверяет world/head и started constraints, допускает pinned branch point; не делает IO, CAS, ancestry или retention. `pack_hash=None` возможен до started, не доказательство отсутствия bake |
| `dataModel/artifacts/references.py::ArtifactRef` | Content identity, format/version, bytes и row count; ни locator, ни world/publication membership. `SQL_ROWS` тоже допустим: нельзя проектировать resolver только как filesystem blob lookup |
| `dataModel/artifacts/lifecycle/holders.py::VerifiedArtifactRef`, `application/artifacts/staging/artifactStaging.py::verify` | Уже есть ref+holder и проверка sealed/held под catalog guard. Reuse candidate, но verified object не гарантирует будущую retention или publication closure |
| `application/artifacts/storage/artifactCatalog.py::IArtifactCatalog.guard`, `contracts/holderPort.py`, `contracts/formatBackend.py::ArtifactBackend` | Guard общий для holders/writers/GC; есть verify/delete/write, но этот backend contract не даёт public typed domain read. Наличие artifact staging не означает готовый resolver |
| `application/worldData/pack/io/worldPackWriter.py::_atomic_write`, `write_locations_index`, `save_manifest` | Replace blob по текущему path, index пишет JSON, manifest hash вычисляется отдельно. Это не immutable namespace на publication и не атомарная публикация всех artifacts. Hash manifest не locator и не proof bytes retention |
| `pack/io/worldPackReader.py::read_location_terrain/read_wilderness_chunk/_decode_file` | Lookup по UID/coordinate path, cache без publication, decode всего файла. `pack/read/packFineTerrainReadFacade.py` и `packRenderReadFacade.py` реально вызывают эти методы; их caller migration обязательна отдельно, не автоматический reuse instance |
| `dataModel/worldPack/meta/worldPackManifest.py::TileManifestEntry/LocationTerrainEntry/ChunkRef` | Hash optional, mutable lists, territory_volume и z_band не exact produced XYZ coverage; нет leaf ownership census или versioned C23 closure |
| `dataModel/worldPack/wire/fineTerrainChunkWire.py` | Column/run типы находятся здесь (не в отдельном fineTerrainColumnWire.py); chunk и runs содержат lists. z-runs inclusive; `cells()` использует min/max, поэтому сам helper не доказывает валидность упорядоченных runs |
| `pack/bake/plan/packTileCollect.py::light_l0_tiles/world_bounds_l0_tiles`, `pack/bake/detailed/detailedBakeScope.py::_wilderness_plan/wilderness_tiles` | Light anchor∪endpoint; full world bounds. Wilderness preparation пропускает complete tiles и ограничивает max_tiles; список оставшейся работы нельзя использовать как expected read scope |
| `settlementOutdoor/settlementOutdoorTopology.py::topology_census/has_frozen_c23_districts` | Census отбрасывает district без frozen slot; пустой результат не доказывает отсутствие settlements. SQL rows и DistrictSlot не immutable published C23 read |

Consumer cross-check: GEN-DAG §§8–9 требуют requested stage, data/разрешимые refs, nonempty missing scope и отдельный Error; §9.3 требует L0+C23, §9.4 — leaf→owner и coordinate target; §9.5 — partial world/scoped independence и shared index/climate/metadata; §16 — Named light→при missing full, coordinates full→detail, terrain не C11 readiness. §9.5 ещё содержит OPEN anchor/territory rule: **предложить владельцу** синхронизировать его с принятыми уточнениями §§14–15 и product anchor∪endpoint; reader сам правило не расширяет. GEN документ здесь не изменён.

#### 17.10.2. Контрпримеры, варианты и сквозные поправки

**D1 — поддержать направление, исправить composition contract.** Контрпример: L0 missing, C23 declared blob потерян; early return missing запускает подготовку вместо остановки на storage error. Другой: light anchor tiles complete, но full scope содержит ещё tile — вызов light не доказывает full. Hidden Pack aggregate отвергнут архитектурой §§13–15; заменить full на world-light нельзя. Предложение: `read_full_bake` проверяет full L0 **required bounded scope**, не требует исторического запуска full job или `bake_mode=full`; совместимые ранее опубликованные tiles переиспользуются. WorldBounds — лишь один вариант scope, не глобальный prerequisite. Full consumer видимо получает L0 и applicable C23 с одной pin/source/frame, возвращает found только при обоих complete, union missing при отсутствии ошибок. Не short-circuit по L0 missing до проверки применимого C23; fatal Error допускает остановку IO, но не missing. Empty applicability требует authoritative census, не filtered topology_census. C23 applicability/whole closure решает topology domain, не арифметика в DAG. Предложить GEN owner exact composite result/error policy и CALL/RETURN bindings, не новые NodeIds здесь. Cancel ждёт drain обоих reads; resume сохраняет обе части и pin, повторно валидирует их, не смешивает старую часть с новым head.

**D2 — reuse принять только как identity reuse.** Контрпример: два мира используют одинаковые bytes ArtifactRef; ref валиден по hash, но чужой для requested publication. Или manifest старой pin сохранён, а `world_map.zst` заменён новым bake. String DTO дублирует identity; raw path привязывает DAG к storage; одного ArtifactRef недостаточно. Предложение: domain envelope связывает existing ArtifactRef с exact publication, source/frame, semantic part и receipt membership. Owning storage обеспечивает immutable locator/namespace mapping и registry format binding для BLOB/SQL_ROWS, без live rows fallback. Нельзя предполагать, что pack_hash равен content_hash конкретного blob или canonical manifest без принятого mapping/hash contract. Coverage receipt не должен включать собственный hash через pack_hash циклически: предложить двухуровневый immutable receipt content + publication root, который связывает receipt ref и pack identity; exact encoding принимает owner. Retention покрывает root, receipts/census, locators и всю closure, не только tiles. На resume descriptor/membership проверяются вновь; существующий VerifiedArtifactRef переиспользовать, если accepted holder semantics подходят, не создавать параллельный holder DTO по умолчанию.

**D3 — externally owned retention требует fencing до конца чтения.** Контрпример: is_held=true при admission, caller release/expiry сразу после него, GC удаляет bytes во время decode либо до resolve после RETURN. Durable acquire внутри read нарушает read-only, удержание coroutine не переживает crash. Предложение: lifecycle owner заранее создаёт/передаёт hold на closure; borrowed access атомарно проверяет membership/hold и блокирует deletion/release либо гарантирует drain до их действия. Конкретная техника (catalog guard или owner-fenced read guard) требует acceptance и bounded lifetime; одной финальной проверки недостаточно. Read не renew/release durable hold. Caller release только после всех consumers и drain; при передаче результата новому owner сначала durable handoff с acknowledgement, затем release прежнего owner. Crash cleanup отличает незавершённый handoff от завершённого, eventual GC не зависит от завершения coroutine. Borrow/close и memory cache допустимы без durable writes. Expiry до borrow→REF_STALE; утрата declared bytes под действующей защитой→Error. Нужен отдельный read-only access contract, staging verify не подставляется как готовый порт.

**D4 — exact pin и current policy надо передавать раздельно.** Контрпример: head P→Q во время долгого read; повторная проверка current на каждом blob случайно отвергает coherent P или смешивает Q. Альтернатива «всегда latest» ломает resume; «current при старте навсегда current» не защищает placement. Предложение: read и resolve всегда exact P; отдельное admission evidence фиксирует policy, comparison point, expected source и P. Current-head admission только наблюдение в определённой точке, terminal placement требует собственного CAS/UOW. Если нужна гарантия до RETURN, owner обязан дать fence, иначе такая гарантия не заявляется. Head moved сам по себе не stale для retained exact pin. Историческая pin не доказывает актуальность mobile target/source: explicit source requirement может отказать независимо от head. Policy refusal и source mismatch не missing, cancel не меняет policy, resume не повышает pin до latest автоматически.

**D5 — изменить primary-only reason и ownership/absence proof.** Контрпример: tiles отсутствуют, index/climate опубликованы; §17.4 называет это ABSENT, хотя GEN §9.1 определяет часть комплекта как INCOMPLETE. Другой: комната удалена/не существует в pinned hierarchy — это не missing terrain с просьбой rebake. Третий: territory_volume присутствует, но половина Z никогда не produced; нельзя found по bounding box. Предложение заменить правило §17.4: ABSENT — ни одного required data component не опубликовано, INCOMPLETE — proper subset комплекта (включая required sidecars); receipts/retention сами не считаются data. Пустое primary set даёт found только при доказанной допустимой пустоте и всех shared components. Любая повреждённая requested declaration→Error до missing; scope unknown/недоказанная absence→Error, не пустой missing_scope. Удалённый/foreign target→invalid target/world/source error, неизвестный mapping→OWNERSHIP_UNRESOLVED, валидный target с неопубликованным owner terrain→missing. Owner census задаёт exhaustive partition requested XYZ, explicit overlaps precedence/splits и no-owner empty semantics; nearest anchor/filtered pins запрещены. NoBake evidence фиксирует world/source/frame/scope и точку отсутствия; concurrent publication делает его историческим наблюдением, подготовка использует отдельный CAS и recheck. Evidence нельзя бесконечно replay как current absence после resume. Exact отсутствие артефакта в authoritative publication отличается от потери declared bytes. Это предложение совместной синхронизации semantics с GEN owner, не самостоятельное изменение GEN.

**D6 — resolver пока не executable contract; поправить lifetime и проекции.** Контрпример: `resolve(ref, scope)` §17.4 не принимает retention, хотя hold мог закончиться; либо scope расширен за verified part и прочитаны чужие данные; shallow-frozen columns позволяют mutate cached runs следующему consumer. Вариант eager whole-world decode не нужен; manifest-only refs не удовлетворяют GEN §9.1. Предложение signature semantics: `resolve(ref, requested_subscope, access_evidence, *, control)` на том же domain reader, subset verified part, exact publication/format/membership/hold admission; никакого durable token в ref. Результат — immutable projection + exact coverage/provenance, Error при loss/stale/out-of-scope, не missing. Immutable materialized data можно хранить после release, но повторное IO требует нового accepted access на ту же pin; валидность ref не бесконечна.

Leaf freeze R2 должен включать field preservation table, а не только название DTO: L0 cell — tx/ty, surface_z, terrain/region/dominant identity, hydrology role/width, climate id, location pin, facing/grade; L2 column — world/local coordinate binding, facing/grade/region, tuple runs terrain/material и explicit covered Z; run half-open conversion inclusive z1→z1+1 с проверкой ranges/overlap/limits. Registry/index refs pinned к тому же source. Отсутствующая колонка не air без coverage rule; несовместимый wire version не заполняется defaults. Whole/part/cell projections должны совпадать по значениям, coverage и пустоте, mutable wire lists не выдаются наружу. Проверка пригодности refs до Found включает accessible verified content/accepted immutable sealed verification, не только catalog entry; bounded IO refusal→RESOURCE_LIMIT, без ложного Found. Cancel во время resolve drain-ит access, resume заново проверяет его.

**D7 — отдельный coordinate контракт обоснован, но XYZ не равен готовому existing reader.** Контрпример: wilderness_tiles для complete tile возвращает []; read принимает это за пустой required set и found. Или coordinate volume пересекает location terrain и wilderness chunks, оба заявлены, но с разными parent source. Overload с fake UID отвергнут; новый bake kind не нужен. Предложение отдельной explicit coordinate operation terrain reader оставить на приёмке, общий L2 payload без обязательного target UID, с trusted anchor/frame/topology, canonical half-open XYZ union и authoritative layout/ownership. Layout выбирает named/wilderness backing и precedence, не исключает location volumes молча; incompatible dependencies→Error, непроизведённые volumes→missing. Scope берётся из запроса, не remaining-work planner/max_tiles. Seam split, negative floor division, requested Z и parent L0 dependencies одинаковы с named read. Coordinate API/preparation binding — отдельный delivery slice, block только координатного entry; terrain found не доказывает applicable C11/позицию. Resume сохраняет coordinate provenance, scope digest и exact pin; chunk re-layout на новом head не переинтерпретирует старый ref.

#### 17.10.3. Исправленный порядок gates и межплановые предложения

§17.8 не означает одну линейную очередь всего трека. Предлагается индексировать R1/R2/R4/R5 по L (L0), T (named terrain), C (C23), X (coordinates). R0 documentary review evidence готов; принятие D1–D7 отдельно. Для каждого среза: relevant R1 owner semantic/type agreement → R2 exact method/result/errors/leaf/import/limits freeze → отдельно разрешённый R3 → R4 actual cold resolver/lifecycle proof → R5 совместная GEN карточка/handoff. C23 также требует R2-C, coordinate — R2-X/R3X/R4-X, а не неявное расширение R3T. Ни один R3 не начат этим review. Старые folder counts §17.6 — provisional footprint, не complete freeze (projection/storage/type reuse ещё могут их изменить).

| Proposed edge / gate | Почему ровно это, а не целый план |
|---|---|
| Accepted immutable publication membership+locator/hash+borrow/hold contract → соответствующий R2/R3 | Snapshot B PASS или весь Snapshot DONE не эквивалент нужному порту; R1 discussion не ждёт implementation |
| Producer expected/produced coverage artifacts и source/frame agreement → R3L/T/X по scope | Read не выпускает receipt. Producer contract можно проектировать параллельно R1; нужны реальные publishable artifacts к R4, не bootstrap всех миров |
| Published hierarchy/owner partition → R3T; coordinate layout → R3X | Whole-world completeness не prerequisite. Parent L0 closure только для requested terrain |
| Versioned C23 applicability+closure+publication join → R2-C/R3C | C23 не блокирует R3L/T/X terrain; C24 settlement blob не замена C23 |
| R5-L(light) → respective light binding; R5-L(full)+R5-C → full composite binding | Нет edge «весь GBR DONE→весь GEN». Full missing/error aggregation и CALL bindings принимает GEN, не helper reader |
| R5-T → named terrain binding; R5-X → coordinate terrain binding | Coordinate не блокирует NamedLocation. Согласованные bounded full/C23/base contracts отдельно нужны coordinate entry |
| Applicable C11 evidence → detail readiness/placement integration | Не C11→terrain read. Spatial compatibility только для реально требуемого downstream canonical source, не весь Spatial→L0 |

Предъявить координатору как **замену** общего R0→R1→R2 fan-out и уточнение пооперационных §17.8 edges; общие gate IDs не вводят whole-plan dependency. GEN §§8–9/9.5/16 consumer design идёт параллельно; concrete binding ждёт только своего accepted handoff, cutover — внешняя отдельная приёмка. Нет обратного GEN cutover→read ports или Snapshot E2E→GBR цикла.

R4 minimum evidence для каждого применимого среза: complete scoped/partial world; optional/required empty; zero-primary с shared components; missing+declared-loss; foreign membership при одинаковом hash; retained P после Q; expired hold; release/GC race в borrow и после RETURN; crash до/после handoff ACK; cancel обоих full reads/resolve и drain; restart с тем же scope/pin; whole/part/leaf parity; sparse Z hole и overlapping owners; coordinate seam/negative tiles. Это будущие integration acceptance cases, **не выполненные тесты**. Unit mocks не доказывают storage lifetime.

#### 17.10.4. Конкретный пакет решений на согласование

Предлагается согласовать D1 с full-L0 scoped semantics и отдельной C23 error/missing composition; D2 с existing identities плюс owner membership/locator и ацикличным receipt root; D3 с fenced borrowed access, external durable handoff и drain; D4 с отдельным current admission/CAS и retained exact reads; D5 с component-based absent/incomplete, exhaustive ownership и point-in-time absence; D6 с access-aware resolver и field-preserving immutable leaf projections; D7 с отдельной coordinate operation/layout без имени, fake UID или нового bake kind. Альтернативы и причины отказа приведены выше, а не оставлены одним OPEN ledger.

До приёмки нельзя объявлять эти решения freeze. После принятия следующий документальный результат — R1 owner agreements и R2 exact slots/projections по отдельным срезам. Код, production POJO/ports, новые bindings, publication и cutover остаются за stop boundary. Review не принимает ни D1–D7, ни межплановые рёбра от имени пользователя.


## Инвариант миграции диагностики: runtime не меняется (2026-11-06)

**Прямое требование пользователя, обязательное для error/logging треков этого домена:** новые типы ошибок, доменные адаптеры, collectors, события и logging integrations не должны переписывать текущую логику runtime. Условия fallback и продолжения обработки не меняются.

- Сохраняются существующие условия допустимости default/None, fallback и выбора альтернативного результата, продолжения batch/независимых проверок, отказа и распространения исключения. Нельзя ужесточать или ослаблять их из-за нового типа диагностики, severity, наличия лога или удобства нового адаптера.
- Сохраняются вычисленные значения/UID, порядок и условия доменных действий, права на запись, commit/rollback, cancellation и retry. Диагностика отражает фактический исход; не становится новой причиной выбора исхода.
- В POJO/import-цепочках переиспользуются ResolveContext/ResolveReport: blocking issues и continuations не смешиваются; collect_only меняет только эмиссию, а validate_only сохраняет принятую политику соответствующего режима. Разрешённое runtime-продолжение не превращается в blocking error после миграции.
- До переключения producer закрепить characterization текущих сценариев: обычный успех, штатный default/None, разрешённый fallback/continuation, blocking отказ и независимая последующая обработка. После переключения сопоставить значения, эффекты и outcome; допустимы только согласованные изменения формы/доставки диагностики. Изменение диагностики в fingerprint проверяется отдельно и не оправдывает изменение доменного payload/маршрута.
- Исправление сломанного конструктора диагностики должно восстановить уже предусмотренную ветвь, а не сохранять случайный TypeError как доменную политику. Где текущая поломка мешает получить результат, evidence берётся из утверждённого доменного контракта, фактов до сбоя и адресных тестов; новый fallback не придумывается.
- Если для реализации требуется изменить runtime-условие, это **отдельный явно согласуемый поведенческий срез**: зафиксировать расхождение и остановить зависимую правку. Не вносить его попутно под названием error migration или logging. Отрицательная проверка нового диагностического контракта не расширяет область перехвата операционных ошибок.

Приёмка каждого затронутого шага включает evidence сохранения runtime-семантики. Это ограничение миграции ошибок и логов, а не запрет ранее согласованной самостоятельной функциональной разработки домена. Статус реализации и пользовательская приёмка этим пунктом не изменяются.
