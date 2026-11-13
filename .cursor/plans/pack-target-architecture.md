# Pack — целевая архитектура и публичная граница DAG

Зафиксировано по поручению пользователя 2026-11-13. Это консолидация согласованных решений, не изменение контрактов, новая приёмка или объявление runtime готовым. Источники: [ТЗ Pack](../../docs/tz_world_pack_storage.md), [write-контракт](pack-v2-public-write-operations.md), [реестр ответственности](pack-class-responsibility-roster.md), [порядок поставки](world-pack-v2-single-manifest-contract.md#единая-таблица-зависимостей-и-завершения-шагов). Детальные predicates, поля входов и error codes остаются в этих owning документах; этот документ фиксирует карту реализации и подключения.

## 1. Граница домена и данные

Pack владеет составом версии, metadata, адресацией, проверками, manifest, подготовкой кандидата, закреплённым чтением и публичными activate/release. DAG выбирает следующий вызов, передаёт результаты и обрабатывает исходы. Pack не запускает Source, Planning или producers, не выбирает workflow и не вызывает один публичный метод из другого.

Единственный сохраняемый агрегат — WorldPackManifestV2. Одна внутренняя декларация `_PackCompositionFields` содержит parts, assembly, assembly_provenance; state и manifest наследуют её без отдельного contents DTO/artifact:

- parts: tuple[PackStoredPart, ...]; каждый record содержит address, ArtifactRef и полный PackStoredProvenance;
- assembly: PackAssemblyInput; metadata без копий payload refs/paths/hashes;
- assembly_provenance: tuple[PackStoredAssemblyProvenance, ...]; происхождение адресованных metadata projections.

PackPreparationState добавляет base_publication: WorldPublicationRef; world определяется через неё. State допускает промежуточную неполноту связей, но не повреждённые вложенные записи. Это материализованный immutable POJO, не session store, не pin capability и не гарантия удержания refs. Полный manifest требует final admission. Производные counters вычисляются из состава, не становятся независимо задаваемыми входами.

Все новые публичные records — strict/frozen/extra-forbid/revalidate-always, коллекции immutable. Existing owning POJO переиспользуются с проверкой фактической строгости вложенных значений. State не наследует готовый manifest и не отключает его validators. Wire pack_version="3.0.0", storage format_version=2, key=world_pack.manifest.json; codec_version/payload_format сохраняются. Legacy удаляется только после cutover и migration gates.

## 2. Компоненты и ответственность

Пути ниже относительно backend/app/application/worldData/pack/; объявления данных — backend/app/dataModel/worldPack/.

| Компонент / путь | Ответственность и эффекты |
|---|---|
| PackPreparationService — preparation/packPreparationService.py | Один конкретный start/write/delete/recalculate/describe/bind. Pure, кроме bounded pinned read в start_from_base. Не хранит mutable state между вызовами |
| PackPreparationValidator — preparation/validator.py | Pure local и final проверки предоставленных данных; request-local агрегация независимых диагностик. Не выполняет storage reads/holds |
| PackManifestAssembler — preparation/assembler.py | Проверенный конечный state → полный manifest и derived counters. Не повторяет writes, не читает базу |
| PackPreparationPipelineOpenPipeline — packPreparationPipelineOpenPipeline.py | Один вызов → одна делегация PackPreparationOperation.prepare |
| PackPreparationOperation — preparation/operation.py | Final admission, verified base/artifacts, adoption/holds, assembly/encoding, stage/seal/READY через внутренние ports. Не публикует head |
| PackPartReadPipelineOpenPipeline — read/packPartReadPipelineOpenPipeline.py | Один вызов → PackPartReadOperation.read_part |
| PackPartReadOperation — read/packPartReadOperation.py | Guarded bounded read точной версии и роли; полностью материализованный typed result, absent либо refusal |
| PackPartReadBindingRegistry — read/partReadBindings.py | Exact descriptor → roles/version/T/pure decoder. Регистрация при composition, без генерации и consumer-specific dispatch |
| PackActivationPipelineOpenPipeline — packActivationPipelineOpenPipeline.py | Публичный activate → внутренний scoped atomic binding. Конкретная внутренняя реализация зависит от owning Publication/Artifacts port; новое имя не придумывается |
| PackCandidateReleasePipelineOpenPipeline — release/packCandidateReleasePipelineOpenPipeline.py | Один вызов → PackCandidateReleaseOperation.release |
| PackCandidateReleaseOperation — release/operation.py | Full candidate identity, durable READY_INACTIVE, атомарное освобождение и replay. Не меняет head и не выполняет цикл отдельных child release |
| Codecs / identity codecs | Pure format/schema/canonical encoding; детали и READY recovery — в отдельном serialization/deserialization плане |
| PacksWiring — core/container/packs.py (относительно backend/app/) | Composition ports, registries, budgets и отдельного manifest Cache instance; не workflow |

Нарушения границ: dispatcher очереди write-команд, callback/lease/backend/CommitScope в public DTO, прямой публичный междоменный вызов, latest lookup вместо pinned read, второй holder/session store. Любое из них означает отказ в приёмке соответствующего кода.

## 3. Публичные методы PackPreparationService для DAG

Каждая строка — отдельный метод с единственным request указанного именованного типа. Все изменяющие методы возвращают новый PackPreparationState, сохраняют base expectation и не мутируют вход. Поля inputs и локальные эффекты определены write-контрактом.

| Метод | Тип request | Результат / особенности |
|---|---|---|
| start_empty | PackPreparationEmptyInput | PackPreparationState; pure, base без Pack |
| async start_from_base | PackPreparationBaseInput | PackPreparationState или ManifestReadRefusal; exact bounded pinned read |
| sync_grid_metadata | PackGridMetadataInput | PackPreparationState |
| set_last_l0_mode | PackLastL0ModeInput | PackPreparationState |
| write_map_tile | PackMapTileInput | PackPreparationState |
| write_wilderness_chunk | PackWildernessChunkInput | PackPreparationState; включая provisional status |
| write_location_terrain | PackLocationTerrainInput | PackPreparationState |
| write_settlement_structure | PackSettlementStructureInput | PackPreparationState; без SQL/publish head |
| write_coarse_climate | PackCoarseClimateInput | PackPreparationState |
| write_fine_climate | PackFineClimateInput | PackPreparationState |
| replace_locations_index | PackLocationsIndexInput | PackPreparationState |
| replace_region_index | PackRegionIndexInput | PackPreparationState |
| write_tile_grade_slots | PackTileGradeSlotsInput | PackPreparationState; полный результат producer, без merge |
| write_location_grade_slots | PackLocationGradeSlotsInput | PackPreparationState; полный результат producer, без merge |
| write_spatial_root | PackSpatialRootInput | PackPreparationState; без генерации/merge shards |
| delete_part | PackDeletePartInput | PackPreparationState; один part, без metadata cascade/GC |
| delete_wilderness_chunk | PackDeleteWildernessChunkInput | PackPreparationState; согласованные metadata/provisional effects |
| delete_fine_climate | PackDeleteFineClimateInput | PackPreparationState |
| delete_location_terrain | PackDeleteLocationTerrainInput | PackPreparationState |
| delete_settlement_structure | PackDeleteSettlementStructureInput | PackPreparationState |
| recalculate_wilderness_status | PackWildernessStatusInput | PackPreparationState; отдельный expected/provisional пересчёт |
| describe_metadata | PackMetadataSubjectsInput | tuple[PackMetadataSubject, ...]; identity текущих projections, не proof |
| bind_metadata_provenance | PackMetadataProvenanceInput | PackPreparationState; entries: tuple[PackMetadataProofBinding, ...]; значения metadata/parts не меняет |

Write/bind failures: PackPreparationFailure с PackPreparationError; diagnostics — закрытый JsonFieldError | WireShapeIssue | PackPreparationIssue. Infrastructure/cancellation не превращаются в INVALID_INPUT. Изменение выполняется после всех доступных независимых проверок; invalid parent исключает только зависимую ветвь.

## 4. Остальные публичные операции для DAG

| Класс | Метод и контракт |
|---|---|
| PackPreparationPipelineOpenPipeline | async prepare(request: PackPreparationInput) -> PreparedPackCandidate; failure — PackPreparationFailure |
| PackPartReadPipelineOpenPipeline | async read_part[T](request: PackPartReadInput[T]) -> PackPartReadResult[T] \| PackPartAbsent \| PackPartReadRefusal |
| PackActivationPipelineOpenPipeline | async activate(request: PackActivationInput) -> PackActivationResult \| PackActivationRefusal \| OperationCancelled |
| PackCandidateReleasePipelineOpenPipeline | async release(request: PreparedPackCandidate) -> PackCandidateReleaseResult \| PackCandidateReleaseRefusal |

В строках результата символ `|` обозначает union типов, не отдельную операцию. Activate переиспользует existing publication result, не вводит его копию. Release разрешён для durable READY_INACTIVE; READY до активации, ACTIVE/history, REJECTED и CANCELLED этим методом не освобождаются. Повтор определяется durable evidence, не отсутствием файла/hold. Infrastructure/busy сохраняют owning исходы.

## 5. Точки интеграции

| Владелец | Точка подключения и граница Pack |
|---|---|
| DAG | Выбирает start и порядок writes, передаёт результаты внешних операций, отдельно вызывает prepare/activate/release/read. Новые ноды и перенос callers — отдельный трек |
| Source | Concrete immutable capture и SourceDurableProof, exact revisions/membership/body closure. Тип импортируется от владельца; Pack не создаёт placeholder, Any или копию Source |
| Producers Terrain/Settlement/Climate/Grade/Hydrology | Их собственные готовые result POJO, exact refs, coverage/evidence → согласованный mapping через DAG → Pack inputs. Producer не обязан возвращать PackPartInput |
| Planning | Existing PlanDependency. PACK-METADATA-PLANNING отложен; не вводит общий запрет независимой работы Pack |
| Artifacts | Verified bytes, stage/seal, preparing adoption, holds/retention/release. Exact atomic ports/typed outcomes принимаются владельцем; Pack не копирует storage |
| Publication | Scoped CAS/handoff/terminal/replay. Resource failure после OWNER требует owning lifecycle/recovery, не самодельного terminal/retry |
| Serialization/deserialization | Canonical schemas/encoding, fingerprints и exact READY recovery по отдельному плану; текущий Pack подключает принятый binding |
| Payload format owners | Pure decoders, semantic validation, format budgets и transitive closure. Pack не назначает произвольные defaults лимитов |
| Transition | Pinned historical context для settlement custom transitions; latest/canonical fallback не допускается |
| Cache | Exact bytes через принятую границу. Hit не отменяет Pack pin/digest/seal/schema checks; публичный Cache workflow внутрь Pack не переносится |

## 6. Порядок и статус реализации

Порядок вызовов: DAG start → отдельные writes в прежнем утверждённом порядке → describe_metadata → evidence владельца через DAG → bind_metadata_provenance → final prepare → отдельно activate. Read и release — самостоятельные маршруты. Final prepare не вызывает bind/writes; assembler не оркестрирует.

Порядок интеграционной поставки сохраняется: sources → evidence → manifest → codec/readers → cutover → удаление legacy → отдельный аудит версий. Независимая локальная работа 3a разрешена до готовности внешних интеграций.

На момент фиксации в текущей работе добавлены [адреса](../../backend/app/dataModel/worldPack/preparation/addresses.py) и [структурные chunk outcomes](../../backend/app/dataModel/worldPack/preparation/coverage.py). Восемь адресных/coverage unit-тестов прошли в предыдущем шаге; это не проверка public service, canonical transport или полного runtime.

По явному решению пользователя: продолжать независимые согласованные типы, алгоритмы и проверки Pack. SourceDurableProof — отложенная внешняя интеграция, не основание остановить весь 3a. Объявления PackStoredProvenance, parts/state и публичные методы, которые невозможно закончить без concrete Source-типа, остаются незавершёнными. Общий state ради обхода зависимости не меняется. Полные producer coverage records также не создаются без их обязательного proof.

Assembly и остальные независимые проверки ещё требуют реализации. Публичные методы таблиц — целевая граница, не список реализованных вызовов. Массовый write-путь требует реальных измерений 1000/4000/16000: admission/update, копирование, describe/bind, фактический DAG transport, время и peak memory. Измерения не выполнены; оценка квадратичной стоимости не заменяет эксперимент, validation не ослабляется без согласованного решения.
