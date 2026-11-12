# Pack — POJO, field errors и logic errors

2026-11-12. Статическая сверка [CRUD roster](pack-data-crud-roster.md), актуального [write-плана](pack-v2-public-write-operations.md), [ТЗ Pack](../../docs/tz_world_pack_storage.md) и shared моделей. Только документация; тесты не запускались. PROJECT не означает готовый runtime. Таблицы фиксируют обязанности и пересечения; общий freeze остаётся открытым по явно указанным строкам.

## Identity, state и содержимое версии

Пути в таблицах относительно backend/app/dataModel, если не указано иначе.

| Тип / модуль / владелец | Поля и назначение | Проверка отсутствия дубля / статус |
|---|---|---|
| ArtifactRef / artifacts/references.py / Artifacts | Exact kind/format_key/format_version/content_hash/nbytes и owning descriptor fields | Pack использует готовую модель, не вводит PackBlobRef с копией полей |
| PreparedPackCandidate / worldPack/activation/candidate.py / Pack, EXISTING | operation_id, manifest: ArtifactRef, preparation_fingerprint | Результат READY и вход release; ReleaseInput с копией этих полей не нужен |
| PackActivationInput / worldPack/activation/input.py / Pack, EXISTING | Наследует candidate, добавляет expected: WorldPublicationRef | Иная операция с полным expected, общие поля не повторены. Не создавать ActivationIdentity DTO для fingerprint |
| PackActivationResult / worldSnapshot/results/publication.py / publication outcome, EXISTING | operation_id, request_fingerprint, manifest, disposition, publication | Один existing результат активации, несмотря на расположение в worldSnapshot. Копия в worldPack/result.py запрещена |
| OperationCancelled / artifacts/lifecycle/operation/record.py / Artifacts, EXISTING | operation_id, reason | Существующий lifecycle outcome, не новый PackCancelled |
| PackPreparationState / worldPack/preparation/state.py / Pack, PROJECT | base_publication + shared parts/assembly/assembly_provenance | Промежуточное immutable состояние, не опубликованный manifest. Допускает незавершённые межчастные связи, не слабые nested types |
| _PackCompositionFields / worldPack/meta/packCompositionFields.py / Pack, PROJECT | Одна декларация parts, assembly, assembly_provenance | Внутренняя база state/manifest, не public contents DTO и не второй artifact |
| WorldPackManifestV2 → единственный WorldPackManifest после legacy удаления / worldPack/meta/worldPackManifest.py / Pack | Target composition + world/envelope/derived показатели | Existing V2 пока прежняя схема. Наследование общей декларации — проект, не evidence реализации. Не оставлять parallel model/alias/fallback после cutover |
| PackPreparationInput / preparation/input.py / Pack, PROJECT | operation_id, preparation_fingerprint, body | Identity операции отдельно от semantic body. Operation ID/fingerprint не дублируются внутри body |
| PackPreparationBody / тот же модуль | state, capture owning Source, scope owning Pack и согласованное evidence | Не повторяет parts/assembly/base/world из state. Concrete внешние поля/coverage ещё OPEN, не Any/dict |

## Адреса, parts и provenance — PROJECT

`worldPack/preparation/addresses.py` содержит один PackPartAddress union: PackMapTileAddress(gx,gy), PackChunkAddress(gx,gy,cx,cy), PackLocationTerrainAddress(location_uid), PackSettlementAddress(location_uid), PackCoarseClimateAddress(), PackFineClimateAddress(gx,gy), PackLocationsIndexAddress(), PackSpatialRootAddress(domain), PackTileGradeSlotsAddress(gx,gy), PackLocationGradeSlotsAddress(location_uid). Каждый имеет собственный Literal kind. Одинаковые координаты разных ролей не означают одну identity; ArtifactRef в адрес не включается.

Актуальный write-план использует `preparation/parts.py::_PackPartInput[AddressT]` с единственной декларацией address/artifact/provenance. Public PackPartInput и десять named concrete subclasses: PackMapTilePartInput, PackWildernessChunkPartInput, PackLocationTerrainPartInput, PackSettlementStructurePartInput, PackCoarseClimatePartInput, PackFineClimatePartInput, PackLocationsIndexPartInput, PackSpatialRootPartInput, PackTileGradeSlotsPartInput, PackLocationGradeSlotsPartInput. У подклассов нет повторных или новых полей; различие — разрешённый address type и concrete model identity. Это не десять независимых схем payload.

Основание именованных классов: [ModelIdentity](../../backend/app/dataModel/fields/validatedFieldPath.py) отклоняет generic origin и unresolved parameters. Публичная прямая specialization не заменяет именованный класс. До приёмки нужны actual CheckedPath/nested union/canonical registration проверки concrete inputs; одно название class не доказывает их успешность.

PackNewPartProvenance и PackInheritedPartProvenance содержат kind и общий PackStoredProvenance. Wrappers задают режим admission новой/наследованной части. PackStoredPart(address, artifact, provenance: PackStoredProvenance) хранит абсолютное происхождение без относительных wrappers. Input part и stored part имеют различный смысл; исключение wrapper при сохранении не должно терять source/planning.

PackStoredProvenance(source_proof: внешний SourceDurableProof, planning: tuple[PlanDependency, ...]) не копирует Source dependencies/body closure и не заменяет их ArtifactRef/PlanRef. PlanDependency переиспользуется из planning/contracts/planDependency.py. SourceDurableProof пока внешний разрабатываемый контракт, не реализованный Pack POJO. Отдельный PackProducedPartEvidence, повторяющий address/ref, отозван. PACK-METADATA-PLANNING сохраняет разрешённую отсрочку.

## Assembly и metadata

PackAssemblyInput в preparation/assembly.py — shared metadata: last_l0_mode, пять effective grid/terrain scalars, tiles/locations/settlements/wilderness_regions. PackTileAssembly(gx,gy,climate_status,wilderness_refine_status,chunks), PackChunkAssembly(cx,cy,refine_role), PackLocationAssembly(location_uid,territory_volume,climate_status), PackSettlementAssembly(location_uid,territory_volume,structure_status,packed_district_uids). Это metadata представления, не копии payload и не исходные World/Location entities. Existing TerritoryVolume, status/role types и WildernessRegionEntry переиспользуются.

PackAssemblyAddress содержит шесть named вариантов из ТЗ: PackAssemblyHeaderAddress, PackTileMetadataAddress, PackChunkMetadataAddress, PackLocationMetadataAddress, PackSettlementMetadataAddress, PackRegionMetadataAddress. Поля — kind плюс соответствующие координаты/UID; header singleton. Metadata addresses не обязаны повторять все десять payload-ролей.

PackAssemblyProvenanceEntry(address, provenance: PackPartProvenance) — входной admission; PackStoredAssemblyProvenance(address, provenance: PackStoredProvenance) — persisted абсолютный proof metadata. Payload proof не заменяет metadata proof. Generic input entries не доказывают связь вычисленной projection с использованными inputs: concrete metadata subject/output/bind остаётся OPEN по write-плану. Новый lineage/receipt POJO этим аудитом не вводится.

## Payload POJO — shared owners, без зеркал

| Роли | Единственные типы | Граница |
|---|---|---|
| map_tile | PROJECT worldPack/wire/worldMapTileWire.py::WorldMapTileWire(cells_per_side,cells), existing WorldMapCellWire | Именует прежнюю пару side/list. ParentLightTile — contextual producer view с иной обязанностью, не storage DTO |
| wilderness/location terrain | worldPack/wire/fineTerrainChunkWire.py::FineTerrainChunkWire и вложенные column/run модели | Один payload для двух адресов, разные role bounds/origin. Не создавать LocationTerrainWire с копией схемы |
| settlement | worldPack/wire/settlementStructureWire.py::SettlementStructureWire и вложенные owning records | Порядок и transition semantics сохраняются; не вводить PackTransition копию owning Transition |
| climate coarse/fine | worldPack/wire/climateFieldWire.py::ClimateFieldWire, ClimateSampleWire | Один role-aware payload; mutable samples/strict admission остаются binding gate |
| locations_index | worldPack/wire/locationsIndexWire.py::LocationsIndexWire, LocationsIndexPin | Позиционные pins, не PackLocationAssembly/SQL Location |
| grade обе роли | terrain/relief/gradeSlot.py::GradeSlotSidecar, GradeCellSlots | Shared Relief body; четыре existing enum смысла не объединяются в новый Pack enum |
| spatial_root/shards | hydrology/pack/root.py::HydrologyPackRoot, HydrologyShardRef; shard.py::HydrologyPackShard | Owning hydrology schema, не PackRootPayload копия; refs/dependencies не теряются |

Детальные nested ограничения и codecs находятся в [payload traces](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12). Наличие shared POJO не доказывает deep immutable/strict admission; extra=ignore, mutable коллекции и coercion проверяются отдельно. Полный nested POJO audit всех owners не объявляется завершённым этой сводкой.

## Read identity — пересечение, требующее завершения

Последующая [конкретизация pin mapping](pack-pin-identity-mapping.md) предлагает единую внутреннюю декларацию пяти identity fields и exact publication admission через существующие pin row/read_exact. Это проект устранения пересечения; implementation/error/guard tests ещё OPEN.

EXISTING `worldPack/read/pinnedManifest.py`: ManifestPinRead(store_id,execution_id,invocation_id,logical_read_key,pin_id,world_uid,max_bytes), ManifestAddress(ref,key), ManifestStorageRead(pin,address), ManifestCachedRead(+entry), VerifiedManifestBytes(ref,payload), ManifestReadRefusal(pin_id,ref,reason). Это manifest bytes boundary с Cache key и read cap; VerifiedManifestBytes не является правом нового чтения.

PROJECT `worldPack/read/part.py`: PackPinnedReadIdentity(store_id,execution_id,invocation_id,logical_read_key,pin_id,publication), PackPartReadBudget(четыре byte budgets), PackPartReadInput[T](pin,address,contract,budget), PackPartReadResult[T](publication,manifest,address,contract,artifact,value,provenance), PackPartAbsent(publication,manifest,address), PackPartReadRefusal(pin_id,publication,address,reason,artifact).

Разные read outcomes имеют разные границы, но первые пять полей двух pin identities семантически пересекаются. Полный checked mapping и единая декларация/валидация общей identity ещё не доказаны; нельзя назвать это автоматически разрешённым дублированием. Новая identity дополнительно несёт publication, старая — world/budget. Нельзя удалить одно поле без trace consumers или молча копировать проверки. Требование: предъявить reuse/адаптацию с exact publication→world, pin lifetime и owner checks, либо явно авторизованное исключение по правилам. Исключение пользователем здесь не запрашивалось и не вводится.

PackPartReadContract[T] наследует id/version от PackPartReadContractMetadata, не повторяет executable registry binding. [Последующая конкретизация read-моделей](pack-read-concrete-models.md) задаёт семь семейств named Input/Contract/Result для десяти ролей, с concrete nested contract и exact registry mapping. ModelIdentity/CheckedPath/serialization реализация и проверки ещё OPEN; одна generic аннотация их не доказывает.

## Field-error и logic-error domains

| Тип / владелец | Поля / обязанность | Недопустимое пересечение |
|---|---|---|
| FieldPathError[CodeT] / validation/diagnostics/fieldPathError.py | code/path/message, shared carrier; constructing generic запрещён | Нужен named owning subclass, а не новая копия base carrier |
| JsonFieldError / validation/importIssues/jsonFieldError.py | Наследует carrier; location, wire_path, schema_id, pydantic_type | Известное declared поле/schema failure. Не создавать PackInputTypeError/PackMissingFieldError с тем же смыслом |
| WireShapeIssue / validation/importIssues/wireShapeIssue.py | code/location/message/pydantic_type | Для root/extra/необъявленной структуры нет допустимого declared field path; не выдумывать FieldRef лишнего ключа |
| PackPreparationIssue / worldPack/preparation/errors.py, PROJECT | FieldPathError[PackPreparationIssueCode] | Смысловые связи address/descriptor/scope/proof, не вторая schema diagnostic того же нарушения |
| PackPreparationError / тот же модуль, PROJECT | reason + непустой issues | Итог операции/этапа, не ещё один независимый PackLogicError с теми же полями; не durable terminal |
| PackPreparationFailure / application/worldData/pack/preparation/errors.py, PROJECT | Exception переносит PackPreparationError | Application exception не второй dataModel error record |
| ManifestReadRefusal / worldPack/read/pinnedManifest.py, EXISTING | pin/ref/reason | Сохраняется у bytes-read, start_from_base не оборачивает его зеркальной pin-ошибкой |
| PackPartReadRefusal / worldPack/read/part.py, PROJECT | Контекст publication/address/contract read | Mapping причин от manifest/storage требует сохранения контекста. Отдельная операция обосновывает иной outcome, но не новый дубликат каждой backend ошибки |
| PackActivationRefusal и PackActivationIssue / worldPack/activation/refusal.py, PROJECT | operation_id/request_fingerprint/diagnostics; exact issue enum/registration ещё требуют freeze | Durable SnapshotApplyResult(REJECTED) — storage envelope, не второй публичный отказ. Replay обязан восстановить один Pack refusal |
| PackCandidateReleaseResult/Refusal/Reason / worldPack/release/result.py, PROJECT | candidate; для refusal reason UNKNOWN_CANDIDATE/IDENTITY_MISMATCH/NOT_READY_INACTIVE | Не копировать candidate fields; отсутствие hold не равно успешному release; busy/infrastructure не становятся domain refusal |

Existing JsonFieldError и WireShapeIssue требуют pydantic_type ровно для SCHEMA_VIOLATION; это проверяется их валидаторами. Canonical path и wire_path различаются по смыслу и не объединяются строкой. Одно нарушение не выдаётся дважды как schema и semantic issue. Окончательный closed union PackPreparationError.issues пока предложен, но не принят; нельзя экспортировать широкий ImportIssue/FieldPathError[Any] как обход.

Проверки при freeze: два независимых field failures агрегируются; invalid parent исключает только зависимые checks; неизвестный ключ использует WireShapeIssue; forged instance проходит повторную валидацию; generic concrete owner сохраняется в CheckedPath и cold restore; expected/actual identity context не теряется; terminal refusal replay сохраняет diagnostics. Эти сценарии в рамках данного документа не запускались.

## Итог

Обоснованы reuse candidate/activation outcomes, shared payload bodies, одна декларация state composition и named part subclasses. Не требуется новый универсальный error carrier или зеркальный Source proof. **Полная POJO/field/logic приёмка остаётся OPEN**: pin identity overlap/mapping, concrete generic read identity, metadata outputs, error union/activation issues, nested strict schema и внешние proof contracts ещё не закрыты. Это не разрешение новых дублей; правила об исключениях не применяются без явной авторизации и обязательных пометок.

Сверка не меняет DAG-порядок, не добавляет публичные междоменные вызовы и не переносит Source/producer ответственность в Pack. Следующий самостоятельный вопрос — pin identity и mapping manifest-read → part-read/start_from_base; concrete metadata-output работу другого агента не перехватывать.
