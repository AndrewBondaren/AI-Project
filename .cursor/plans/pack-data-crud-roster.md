# Pack — concrete CRUD данных и границы приёмки

2026-11-12. Сводка по [write-плану](pack-v2-public-write-operations.md), [ТЗ Pack](../../docs/tz_world_pack_storage.md) и существующему коду. Только документация; тесты не запускались. PROJECT означает предложенный контракт, EXISTING — объявление найдено в коде, но не автоматически завершённую приёмку целевой версии. Поля shared POJO не переобъявляются этой таблицей.

## Модули общих контрактов

Все пути ниже относительно backend/app. `PackPreparationService` — PROJECT в `application/worldData/pack/preparation/packPreparationService.py`. Его state — `dataModel/worldPack/preparation/state.py::PackPreparationState(base_publication, parts, assembly, assembly_provenance)`. Start inputs — `dataModel/worldPack/preparation/start.py`, остальные inputs таблицы изменений — `dataModel/worldPack/preparation/operations.py`. Shared addresses/parts/assembly — соответствующие модули preparation/addresses.py, parts.py, assembly.py по общему проекту.

Общий semantic failure start/write/prepare: `application/worldData/pack/preparation/errors.py::PackPreparationFailure`, несущий `dataModel/worldPack/preparation/errors.py::PackPreparationError(reason, issues)` и PackPreparationIssue(code, path, message). Согласованный closed union: `PackPreparationDiagnostic = JsonFieldError | WireShapeIssue | PackPreparationIssue`; issues — обязательный tuple, пустой допускается только для MANIFEST_OVERSIZE. Structural issues дают INVALID_INPUT без дублирования semantic кодами. [Точный контракт и admission](pack-preparation-issue-union.md) описаны; реализация и полная semantic матрица этим не принимаются. Infrastructure/cancellation сохраняют owning типы и не превращаются в success/absent.

## C/U: начало и явные изменения нового состава

Все методы этой таблицы принадлежат PackPreparationService, имеют статус PROJECT. Sync означает pure обработку immutable state; только start_from_base выполняет I/O через внутренний pinned read binding. Ошибки — общие выше, плюс явно указанный ManifestReadRefusal.

| CRUD | Полная сигнатура | Смысл и конкретность |
|---|---|---|
| C | `def start_empty(self, request: PackPreparationEmptyInput) -> PackPreparationState` | Начальная версия при base_publication.pack_hash=None; initial assembly/provenance объявлены в write-плане |
| U | `async def start_from_base(self, request: PackPreparationBaseInput) -> PackPreparationState \| ManifestReadRefusal` | Pin + max_manifest_bytes → проверенный состав базы; без fallback в start_empty |
| U | `def sync_grid_metadata(self, request: PackGridMetadataInput) -> PackPreparationState` | Captured grid; не меняет last_l0_mode |
| U | `def set_last_l0_mode(self, request: PackLastL0ModeInput) -> PackPreparationState` | Отдельный эффект после L0 writes по принятому порядку |
| C/U | `def write_map_tile(self, request: PackMapTileInput) -> PackPreparationState` | Адресованный L0 payload и его обязательные локальные эффекты |
| C/U | `def write_wilderness_chunk(self, request: PackWildernessChunkInput) -> PackPreparationState` | Chunk, metadata, provisional status |
| C/U | `def write_location_terrain(self, request: PackLocationTerrainInput) -> PackPreparationState` | Terrain part и owning metadata |
| C/U | `def write_settlement_structure(self, request: PackSettlementStructureInput) -> PackPreparationState` | Settlement part; preserve/empty metadata semantics |
| C/U | `def write_coarse_climate(self, request: PackCoarseClimateInput) -> PackPreparationState` | Singleton coarse part |
| C/U | `def write_fine_climate(self, request: PackFineClimateInput) -> PackPreparationState` | Fine part и tile climate status |
| C/U | `def replace_locations_index(self, request: PackLocationsIndexInput) -> PackPreparationState` | Полный готовый payload индекса; порядок pins сохраняет смысл |
| U | `def replace_region_index(self, request: PackRegionIndexInput) -> PackPreparationState` | Полная замена metadata index с existing require_region_index |
| C/U | `def write_tile_grade_slots(self, request: PackTileGradeSlotsInput) -> PackPreparationState` | Готовый полный merge producer, не merge внутри Pack |
| C/U | `def write_location_grade_slots(self, request: PackLocationGradeSlotsInput) -> PackPreparationState` | Тот же payload для location address |
| C/U | `def write_spatial_root(self, request: PackSpatialRootInput) -> PackPreparationState` | Готовый root одного domain, без Hydrology |
| U | `def recalculate_wilderness_status(self, request: PackWildernessStatusInput) -> PackPreparationState` | Явный expected/provisional пересчёт по старой policy |

Точные поля inputs и специализации PackPartInput приведены в write-плане; каждый input именованный и содержит общий state, а не его копию. Запись U означает новое immutable значение и впоследствии новую версию, а не in-place изменение опубликованного manifest.

### Metadata: описание и привязка evidence

Оба метода — PROJECT того же PackPreparationService, общий Failure выше; pure, без Source I/O, запуска prepare и выбора workflow.

| CRUD | Полная сигнатура | Конкретные POJO и эффект |
|---|---|---|
| R | `def describe_metadata(self, request: PackMetadataSubjectsInput) -> tuple[PackMetadataSubject, ...]` | `dataModel/worldPack/preparation/metadataSubject.py`: input(state, addresses); output subject(base_publication, address, value_fingerprint). Описывает identity текущих значений, не создаёт proof |
| U | `def bind_metadata_provenance(self, request: PackMetadataProvenanceInput) -> PackPreparationState` | Input в preparation/operations.py: state, entries: tuple[PackMetadataProofBinding, ...]; binding(subject, provenance) в preparation/metadataSubject.py. Проверяет уникальность адресов, base/current fingerprint и provenance admission; возвращает state без изменения parts/assembly |

Порядок: DAG вызывает describe после выбранных writes, получает evidence у владельца и передаёт bindings в Pack. Прежний вход из PackAssemblyProvenanceEntry не сохраняется как alias. Точные проверки — в write-плане; внешнее evidence mapping не объявляется реализованным.

## D: новый состав и отдельное освобождение кандидата

Первые пять методов — тот же PackPreparationService, input-модуль operations.py, результат state.py, общий failure. Их эффекты и final gates сведены в [delete roster](pack-delete-remaining-roles.md).

| Полная сигнатура | Область |
|---|---|
| `def delete_part(self, request: PackDeletePartInput) -> PackPreparationState` | Один logical address и его payload provenance; для шести ролей дополнительных metadata-эффектов нет |
| `def delete_wilderness_chunk(self, request: PackDeleteWildernessChunkInput) -> PackPreparationState` | Chunk part/metadata/proof и provisional tile status |
| `def delete_fine_climate(self, request: PackDeleteFineClimateInput) -> PackPreparationState` | Fine part и согласованный tile status |
| `def delete_location_terrain(self, request: PackDeleteLocationTerrainInput) -> PackPreparationState` | Только terrain представление и owning metadata/proof |
| `def delete_settlement_structure(self, request: PackDeleteSettlementStructureInput) -> PackPreparationState` | Только settlement представление и owning metadata/proof |

Отдельный PROJECT-класс `PackCandidateReleasePipelineOpenPipeline`, `application/worldData/pack/release/packCandidateReleasePipelineOpenPipeline.py`:

`async def release(self, request: PreparedPackCandidate) -> PackCandidateReleaseResult | PackCandidateReleaseRefusal`

Input EXISTING — `dataModel/worldPack/activation/candidate.py`; result/refusal/reason PROJECT — `dataModel/worldPack/release/result.py`. One delegate — PackCandidateReleaseOperation в release/operation.py. Только durable READY_INACTIVE; не release ACTIVE/history, не cancel READY, не физическое удаление blobs. OperationBusyError/infrastructure/unknown commit не превращаются в domain success. [Atomic release/repeat gate](pack-candidate-release-contract.md) открыт. Удаление logical part, release и GC не взаимозаменяемы.

## C/U: завершение подготовки и activation

| PROJECT публичный класс и модуль application/worldData/pack/ | Полная сигнатура | Типы и эффекты |
|---|---|---|
| PackPreparationPipelineOpenPipeline, packPreparationPipelineOpenPipeline.py | `async def prepare(self, request: PackPreparationInput) -> PreparedPackCandidate` | Input/body: dataModel/worldPack/preparation/input.py; body(state, capture, scope), без списка write-команд. Candidate EXISTING в activation/candidate.py. Failure общий; один delegate PackPreparationOperation.prepare, admission/seal/READY без изменения head |
| PackActivationPipelineOpenPipeline, packActivationPipelineOpenPipeline.py | `async def activate(self, request: PackActivationInput) -> PackActivationResult \| PackActivationRefusal \| OperationCancelled` | Input EXISTING activation/input.py; result EXISTING dataModel/worldSnapshot/results/publication.py; cancellation EXISTING dataModel/artifacts/lifecycle/operation/record.py; refusal PROJECT worldPack/activation/refusal.py. Pack admission и принятый внутренний atomic commit/CAS/handoff/terminal |

Activation Input содержит operation_id, полный manifest ref, preparation_fingerprint и полный expected: WorldPublicationRef. Result содержит operation_id/request_fingerprint/manifest/disposition/publication. Новые копии этих типов не создаются. Concrete activation internal binding, canonical registration refusal/issues и identity vectors остаются [открытыми](pack-activation-refusal-trace.md); строка публичной сигнатуры их не закрывает.

## R: части и существующее чтение manifest

PROJECT `PackPartReadPipelineOpenPipeline` в `application/worldData/pack/read/packPartReadPipelineOpenPipeline.py`:

`async def read_part[T: BaseModel](self, request: PackPartReadInput[T]) -> PackPartReadResult[T] | PackPartAbsent | PackPartReadRefusal`

Все перечисленные input/result/absent/refusal/reason, PackPinnedReadIdentity, PackPartReadContract и PackPartReadBudget — проект `dataModel/worldPack/read/part.py`. Input: pin/address/contract/budget. Result: publication/manifest/address/contract/artifact/value/provenance. T — конкретный registered deep immutable payload POJO. Отсутствие адреса и refusal различаются; malformed input и infrastructure не становятся absent. Одна делегация PackPartReadOperation.read_part в read/packPartReadOperation.py; guard/verified read/bounded decode, без latest source или генерации. Реализация и composition всех bindings ещё OPEN.

EXISTING `PinnedManifestReader` в [read/pinnedManifestReader.py](../../backend/app/application/worldData/pack/read/pinnedManifestReader.py) имеет следующие реальные методы. Все named POJO находятся в [dataModel/worldPack/read/pinnedManifest.py](../../backend/app/dataModel/worldPack/read/pinnedManifest.py):

| Полная сигнатура | Input/result и смысл |
|---|---|
| `async def resolve(self, request: ManifestPinRead) -> ManifestAddress \| ManifestReadRefusal` | Pin identity + max_bytes → exact ref/cache key под guard |
| `async def read_verified(self, request: ManifestStorageRead) -> VerifiedManifestBytes \| ManifestReadRefusal` | pin/address → проверенные ref/payload, без выбора Cache hit/miss |
| `async def admit_cached(self, request: ManifestCachedRead) -> VerifiedManifestBytes \| ManifestReadRefusal` | pin/address/CacheEntry[bytes] → повторный pin/identity/digest/schema admission |

Это отдельный существующий bytes-read контракт, не готовый typed read_part и не доказательство поддержки новой полной схемы manifest. Ветки hit/miss и Cache операции принадлежат DAG. Для start_from_base mapping нового PackPinnedReadIdentity к этому boundary ещё требует проверки; VerifiedManifestBytes от caller не доказывает живой pin.

## Открытые строки, которые нельзя скрыть таблицей

1. **Metadata output/bind:** concrete DTO и обе публичные операции описаны выше и в write-плане. Проверке подлежат реализация и внешний evidence mapping; утверждение об отсутствии subject/bind DTO устарело. PACK-METADATA-PLANNING сохраняет разрешённую отсрочку и не переоткрывается как блокер текущего объёма.
2. **Errors:** состав closed structural/semantic union согласован; остаются проверка полной semantic матрицы, field paths и реализации mapping. Это не разрешение Any/строкового ValueError. Canonical registration/identity/recovery ведутся в [отдельном плане](pack-serialization-deserialization.md), не блокируют независимый текущий scope, но обязательны для соответствующего runtime-пути.
3. **Final admission/lifecycle:** exact scope/coverage, inherited proofs, полный closure, atomic adoption/activation/release и restart/replay остаются соответствующими gates. Внешние типы/ports не реализуются Pack по догадке; отсутствие миграции callers не запрещает самостоятельную Pack-owned работу.
4. **Payload bindings:** descriptors и strict bounded decoder/composition проверяются по каждому owning контракту. Для grade descriptors уже предложены в ТЗ: storage world_pack.grade_slots.json/version 1 и read world_pack.grade_slots/version 1; это не открытый выбор имени. Реализация, budget и registration не подтверждены одним текстом ТЗ.
5. **Настройки:** эта таблица намеренно о данных. Отдельную обязательную C/R/U/D сверку настроек выполнять по [уже принятым решениям](pack-v2-domain-contract-spec.md#5-crud-и-настройки-не-подменять-семантику), без повторного выбора manifest_cache/CachePolicy и без выдуманного hot settings service.

Полный CRUD данных пока **не принят**: остаются проверки Error/binding/lifecycle и реализации по обязательным критериям. Отсутствие metadata DTO больше не является основанием отказа. Классы/POJO и их ответственность не заменяются одной таблицей; детальные traces остаются нормативными для проекта. DAG вызывает публичные методы напрямую, выбирает порядок и ветви; операции не оркестрируют друг друга. Порядок источники → evidence → manifest → codec/readers, перенос callers до удаления legacy и отдельный последующий аудит версионных имён/комментариев сохраняются.
