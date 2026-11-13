# R1 — конкретная карта публичных pipeline и логики

Дата: 2026-11-12. Продолжение [уточнения R1](rev-02-contract-clarification.md). Статус: проект, НЕ полный принятый implementation contract. Только документы; runtime/SQL/DAG не меняются. Все новые классы ниже proposed, даже если сигнатура записана полностью. Existing обозначено явно. Имена не доказывают наличие реализации.

## Владельцы и границы поставки — решение пользователя 2026-11-12

**Pipeline принадлежит домену выполняемой операции. DAG владеет оркестрацией, а не реализацией доменных pipeline. Перечень внешних pipeline ниже — карта зависимостей Pack, НЕ задание реализовать их в рамках домена/плана Pack.**

| Операции | Владелец публичного контракта, POJO, ошибок и реализации | Scope этого плана |
|---|---|---|
| Source capture / exact read | Source Versioning | Только требования потребителя Pack и сверка внешнего контракта; реализация — в owning плане Source |
| Fine materialization | Terrain/materialization; точная внутренняя граница требует приёмки владельца | Только ожидаемые данные результата и mapping; реализация/декомпозиция L2 вне плана Pack |
| Settlement topology / materialization | Settlement | Только требования к census, результатам и provenance; реализация/декомпозиция вне плана Pack |
| L0/climate/grade producers | Соответствующие owning домены; не назначаются Pack по месту legacy caller | Не включены автоматически в Pack scope; каждую границу сначала подтвердить |
| Pack preparation / part read / activation | World Pack | Собственные публичные контракты, POJO и внутренняя реализация Pack после закрытия gates |
| Ноды, порядок вызовов и перенос результатов | Engine DAG | Отдельная совместная приёмка с пользователем; этот план не разрешает разработку нод |

Предложенные имена и пути внешних классов в §1 — адресные предложения их владельцам, не утверждённое размещение и не разрешение создать эти файлы силами Pack. Не добавлять в Pack обёртки, скрывающие вызов Source/Terrain/Settlement, и не переносить чужие алгоритмы под Pack ради закрытия зависимости. OPEN внешнего контракта остаётся внешней зависимостью, а не новой работой Pack.

Producer возвращает **собственный доменный result POJO**. Он не обязан импортировать или возвращать PackProducedPartEvidence/PackPartInput. Mapping готового доменного результата во вход Pack выполняется на согласованной границе передачи через DAG, без доменных вычислений в adapter; Pack валидирует свой вход. Конкретный binding ещё требует приёмки. Чужие POJO не копируются в Pack и не заменяются Pack-owned универсальным producer result.

## 1. Публичные операции и вызывающая сторона

Все пути относительно `backend/app/`. Публичные классы concrete, не только Protocol. Каждый wrapper один раз делегирует одноимённому operation; не выбирает следующий домен. DAG вызывает операции и переносит готовые POJO. Ноды/их deps этим документом не назначаются.

| Concrete класс / модуль | Публичный метод | Реализация и граница |
|---|---|---|
| `SourceCapturePipelineOpenPipeline`, `application/worldData/sourceVersioning/sourceCapturePipelineOpenPipeline.py` | `async capture(self, request: SourceCaptureInput) -> SourceCapture` | `SourceCaptureOperation.capture`; согласованное закрепление источников. Не materialization, не CRUD-фасад остальных доменов. Поля input и допустимый retention binding ещё OPEN, см. §5. |
| `SourceExactReadPipelineOpenPipeline`, `application/worldData/sourceVersioning/sourceExactReadPipelineOpenPipeline.py` | `async read_exact[T: BaseModel](self, request: SourceReadRequest[T]) -> SourceReadResult[T]` | `SourceExactReadOperation.read_exact`; exact revision/registered descriptor → immutable typed value. Не fallback на latest. Source failure имеет отдельный owning тип, его окончательная field/logic схема OPEN. |
| `FineMaterializationPipelineOpenPipeline`, `application/worldData/materialize/terrain/fineMaterializationPipelineOpenPipeline.py` | `async materialize(self, request: FineMaterializationInput) -> FineMaterializationResult` | `FineMaterializationOperation.materialize`; одна L2 операция, её compute/partition/staging внутри. Нельзя просто вызвать legacy refine_rects с writer; input/error ещё OPEN по конкретным причинам §5. |
| `SettlementTopologyPipelineOpenPipeline`, `application/worldData/settlementOutdoor/settlementTopologyPipelineOpenPipeline.py` | `async plan_topology(self, request: SettlementTopologyInput) -> SettlementTopologyResult` | `SettlementTopologyOperation.plan_topology`; возвращает полный census и topology result по captured входам. Не запускает materialize. Input и payload census требуют выделения из existing plan_topology, не считаются готовыми. |
| `SettlementMaterializationPipelineOpenPipeline`, `application/worldData/settlementOutdoor/settlementMaterializationPipelineOpenPipeline.py` | `async materialize(self, request: SettlementMaterializationInput) -> SettlementMaterializationResult` | `SettlementMaterializationOperation.materialize`; получает готовые topology/L2 inputs через DAG, не вызывает их pipelines. Полный census/packed set и structure ref на выходе; input/error ещё OPEN. |
| `PackPreparationPipelineOpenPipeline`, `application/worldData/pack/packPreparationPipelineOpenPipeline.py` | `async prepare(self, request: PackPreparationInput) -> PreparedPackCandidate` | `PackPreparationOperation.prepare`, `preparation/operation.py`; concrete вход ниже. Выбрасывает `PackPreparationFailure`, не вызывает activate, Source read или producer. |
| `PackPartReadPipelineOpenPipeline`, `application/worldData/pack/read/packPartReadPipelineOpenPipeline.py` | `async read_part[T: BaseModel](self, request: PackPartReadInput[T]) -> PackPartReadResult[T] \| PackPartAbsent \| PackPartReadRefusal` | Уже предложенный контракт owning ТЗ; `PackPartReadOperation.read_part`. DAG передаёт полученную базу producer, например при merge sidecar. Не читает Source ради готового payload. |

Отдельные L0/climate/grade producer boundaries должны пройти ту же проверку входов; этот документ не выдаёт перечисленные пять предложений за полный roster всех producers Pack. Existing `PackTilePlanner.plan` и `merge_grade_cell_slots` остаются внутренними вычислениями; автоматически делать из них публичные операции не требуется.

## 2. POJO Pack и связанного результата

Все proposed records — strict, frozen, extra-forbid, revalidate-always; вложенное дерево immutable. В wire не допускаются coercion и duplicate keys. Ни callbacks, ни writer/lease/CommitScope в публичном input. Типы адресов/assembly/scope — существующий **проект** owning ТЗ, не новые параллельные декларации.

| Модуль `dataModel/` | POJO и точные поля |
|---|---|
| `worldPack/preparation/input.py` | `PackPreparationInput(operation_id: EntityUid, preparation_fingerprint: RevisionHex, body: PackPreparationBody)` |
| `worldPack/preparation/input.py` | `PackPreparationBody(world_uid: EntityUid, capture: SourceCapture, base_publication: WorldPublicationRef, scope: PackPreparationScope, parts: tuple[PackPartInput, ...], assembly: PackAssemblyInput, assembly_provenance: tuple[PackAssemblyProvenanceInput, ...])` |
| `worldPack/preparation/parts.py` | `PackPartInput(address: PackPartAddress, artifact: ArtifactRef, provenance: PackPartProvenance)`; union new/inherited из ТЗ |
| `worldPack/preparation/provenance.py` | Предлагаемый `PackStoredProvenance(source_proof: SourceDurableProof, planning: tuple[PlanDependency, ...])`. Source proof не включает второй список Planning dependencies. Concrete SourceDurableProof ещё требует §5; это не разрешение placeholder в runtime. |
| `worldPack/preparation/provenance.py` | `PackNewPartProvenance(kind: Literal["new"], provenance: PackStoredProvenance)` — полный provenance новой части |
| `worldPack/preparation/provenance.py` | `PackInheritedPartProvenance(kind: Literal["inherited"], provenance: PackStoredProvenance)` — полный исходный provenance, включая planning, сверяется с pinned base и сохраняется неизменным |
| `worldPack/meta/parts.py` | `PackStoredPart(address: PackPartAddress, artifact: ArtifactRef, provenance: PackStoredProvenance)` — record внутри единственного manifest, не отдельный aggregate |
| `worldPack/activation/candidate.py` | **Existing** `PreparedPackCandidate(operation_id: EntityUid, manifest: ArtifactRef, preparation_fingerprint: RevisionHex)` |

**ACCEPTED, решение пользователя 2026-11-12:** отдельный `PackProducedPartEvidence` исключён. Address/ref находятся только в PackPartInput; оба варианта происхождения оборачивают один PackStoredProvenance (source_proof + planning), не дублируют его поля. При записи manifest сохраняется этот полный provenance без относительного признака new/inherited. Input и stored record различаются admission-семантикой: первый задаёт способ проверки относительно текущей подготовки/базы, второй описывает долговременное происхождение. Mapping собственного результата producer через DAG проверяется отдельно; повторение адреса/ref не является доказательством происхождения. Конкретный тип source_proof разрабатывает другой агент; это решение не подменяет и не утверждает его схему.

Для metadata предмет evidence — конкретная typed assembly projection и её address. Один голый digest metadata не заменяет эту модель. Pack-owned состав metadata/provenance конкретизирован в §2.1; внешний Source proof подключается как owning тип, не реализуется через dict/универсальный JSON.

### 2.1. Pack-owned metadata и provenance — конкретизация по результатам приёмки

**Scope по поручению пользователя 2026-11-12:** завершаем собственные требования Pack; последующие новые требования на междоменной границе учитываются при миграции соответствующих доменов. Внешняя миграция не останавливает эту документальную конкретизацию и не становится реализацией Pack. Она не разрешает использовать неподтверждённый proof в runtime.

Owning модули: `dataModel/worldPack/preparation/addresses.py` и `provenance.py`. Ниже конкретные предлагаемые модели Pack (strict/frozen/extra-forbid, без defaults обязательных полей):

| Модель metadata address | Поля |
|---|---|
| PackAssemblyHeaderAddress | `kind: Literal["header"]` |
| PackTileMetadataAddress | `kind: Literal["tile"]`, `gx: int`, `gy: int` |
| PackChunkMetadataAddress | `kind: Literal["chunk"]`, `gx: int`, `gy: int`, `cx: int`, `cy: int` |
| PackLocationMetadataAddress | `kind: Literal["location"]`, `location_uid: EntityUid` |
| PackSettlementMetadataAddress | `kind: Literal["settlement"]`, `location_uid: EntityUid` |
| PackRegionMetadataAddress | `kind: Literal["region"]`, `region_uid: EntityUid` |

**Решение пользователя 2026-11-13: использовать форму owning ТЗ.** `PackAssemblyAddress` — discriminated union этих шести моделей. Координаты плоские strict int; macro gx/gy могут быть отрицательными, локальные cx/cy неотрицательны. Вложенные tile/chunk и прежние Assembly-имена отозваны; aliases и второй wire-вариант не вводятся. Discriminator metadata отличает назначение от payload address: tile metadata существует и без map_tile payload. Existing PackTileRef, payload PackChunkAddress и модели других доменов не меняются. EntityUid у нового region metadata address следует ТЗ и не меняет str в existing WildernessRegionEntry: неподходящая identity отклоняется на новой границе, не обрезается и не нормализуется автоматически. Проверка совместимости реальных region identities обязательна до cutover.

- `PackAssemblyProvenanceInput(address: PackAssemblyAddress, provenance: PackPartProvenance)` — переиспользуется тот же union new/inherited, поскольку смысл происхождения одинаков; второй набор вариантов не создаётся. Название union не означает наличие payload в metadata.
- `PackStoredAssemblyProvenance(address: PackAssemblyAddress, provenance: PackStoredProvenance)` — durable record без new/inherited.
- `PackStoredProvenance(source_proof: SourceDurableProof, planning: tuple[PlanDependency, ...])` остаётся единственным общим provenance для payload и metadata. SourceDurableProof — внешний binding, не объявление локальной Source модели.

**Projection без второго metadata DTO:** address выбирает значения из единственного PackAssemblyInput. Header — last_l0_mode и пять effective scalars: fine_cells_per_map_cell, world_map_cells_per_tile, fine_cell_size, map_subsurface_depth, terrain_chunk_columns (добавлен решением пользователя 2026-11-12); tile — gx/gy/climate_status/wilderness_refine_status, без chunks; chunk — cx/cy/refine_role из конкретного tile; location/settlement — полная соответствующая assembly row; region — existing WildernessRegionEntry. Один selector внутри Pack возвращает owning row или header scalar tuple для existing canonical encoder; публичного dict/нового класса-копии row нет. Физическая общая декларация metadata остаётся у Pack, её использует и input, и manifest.

**Exact coverage metadata:** ровно один header proof; по одному на каждую tile/chunk/location/settlement/region row; duplicate, missing и лишние адреса отклоняются до сборки. Разрешение chunk сначала проверяет tile, затем локальные координаты. Несуществующая row не читается как default. Inherited metadata сравнивается с той же projection pinned базы и полным старым provenance. Изменение tile chunks само по себе не переписывает proof неизменных tile scalars; новые/изменённые chunks требуют собственного происхождения.

**Границы ошибок:** missing metadata proof → `METADATA_PROOF_MISSING`; duplicate address → `DUPLICATE_ADDRESS`; proof на отсутствующую row → `ADDRESS_MISMATCH`; несовпадение inherited projection/base → `BASE_PUBLICATION_MISMATCH`; подмена содержимого/источника → `SOURCE_PROOF_MISMATCH`. Используются existing проект PackPreparationIssue/PackPreparationError, не новые аналогичные exception/POJO.

**Coverage materialization:** structural checks PackChunkCoverageEntry/Materialized/WithoutPayload принадлежат Pack; expected/completed множества, уникальность, outputs → parts и packed ⊆ census проверяются без IO. Проверку actual payload выполняет §3.1 на owning decoded model. Поле внешнего coverage proof не заменяется SourceDurableProof автоматически: Source identity не доказывает исполнение materialization. Его concrete binding — требование миграции producer; значения counts не используются для заполнения missing proof.

### Coverage: точные существующие предложения ТЗ, без нового выбора политики

Модуль `dataModel/worldPack/preparation/coverage.py`:

```python
class PackChunkMaterialized:
    kind: Literal["materialized"]
    outputs: tuple[PackPartAddress, ...]  # nonempty

class PackChunkWithoutPayload:
    kind: Literal["without_payload"]

PackChunkCoverageResult = PackChunkMaterialized | PackChunkWithoutPayload

class PackChunkCoverageEntry:
    address: PackChunkAddress
    result: PackChunkCoverageResult
```

Это декларации полей документа, не runtime classes без BaseModel. Expected и completed остаются разными данными; источник expected — captured scope/grid, не счётчик результата. Для `PackWildernessCoverage(expected, completed, proof)` и `PackSettlementCoverage(location_uid, expected_districts, packed_districts, proof)` concrete proof всё ещё OPEN. Нельзя устранить это поле или заменить Source proof одним PlanRef ради «полной» сигнатуры.

### Ошибки prepare

Переиспользовать проект `dataModel/worldPack/preparation/errors.py`:

- `PackPreparationError(reason: PackPreparationFailureReason, issues: tuple[PackPreparationIssue, ...])`, issues непустой.
- `PackPreparationIssue(FieldPathError[PackPreparationIssueCode])`: inherited code/path/message, не второй carrier.
- `application/worldData/pack/preparation/errors.py::PackPreparationFailure(error: PackPreparationError)`.
- Неверный ref/proof mapping → `DEPENDENCY_MISMATCH / SOURCE_PROOF_MISMATCH`; missing expected output → `DEPENDENCY_MISMATCH / MISSING_PART`; лишний адрес → `UNEXPECTED_PART`; вне scope → `OUT_OF_SCOPE_CHANGE`; неверная база → `BASE_PUBLICATION_MISMATCH`; unavailable artifact → `ARTIFACT_UNAVAILABLE`; unavailable capture → `SOURCE_UNAVAILABLE`.

Это Pack-owned diagnostics нарушения входа; не копии Source field/logic ошибок. Infrastructure/busy/unknown outcome сохраняют owning тип, не превращаются в field refusal. Независимые ошибки этапа агрегирует existing `dataModel/validation/diagnostics/validatorAggregationHelper.py`.

## 3. Внутренняя логика Pack prepare

**Приоритетное последующее уточнение 2026-11-12:** [проект открытых write-контрактов Pack](pack-v2-public-write-operations.md) переносит порядок самостоятельных write-вызовов в DAG. Ассемблер получает конечное состояние, prepare выполняет только завершение, без исполнения списка metadata updates. Нижеследующее предложение применения всех updates одним assembler отозвано в этой части. Новые concrete классы/DTO и DAG bindings ещё проходят приёмку.

**Последующее принятое уточнение 2026-11-12:** сборку из проверенной базы и обновлений выполняет сам PackManifestAssembler одним pure-вызовом; отдельный класс сборки не вводится. Чтение базы и storage остаются у PackPreparationOperation. Конкретный input обновлений остаётся OPEN; он обязан различать отсутствие обновления и явно пустую замену по [старым правилам и критериям](pack-v2-domain-contract-spec.md#принятая-граница-сборки-состава-2026-11-12). Упоминание ниже незакреплённого класса сборки устарело: принят PackManifestAssembler.

**Актуальное уточнение пользователя 2026-11-12:** полный состав получается внутри Pack из закреплённой базы и готовых результатов по прежним правилам writer, а не собирается DAG перед prepare. Отсутствие нового результата сохраняет базовую часть; незатронутый provenance не меняется. [Граница, evidence и критерии](pack-v2-domain-contract-spec.md#принятая-граница-сборки-состава-2026-11-12). Таблица входных POJO выше и последовательность ниже требуют детализации под эту границу; они не разрешают реализовать прежнюю семантику «полный состав во входе» или выдумать универсальный delta DTO. Конкретный внутренний класс сборки остаётся OPEN. Новый pipeline с выбором стадий не вводится.

**Применение действующего запрета оркестрации внутри доменов** из `.cursor/rules/dag-generator-interface.mdc`, раздел «Обязательная приёмка плана любого домена». Напоминание пользователя не вводит новое решение и не меняет прежние границы. Шаги ниже — проверки и внутренние действия одной prepare операции, не цепочка публичных pipeline. Pack не получает недостающие inputs вызовом Source/producer/Cache и не запускает activate. Source и producers также не вызывают соседние публичные операции; это относится и к нескольким самостоятельным операциям одного домена. Выбор маршрута, условий запуска и retry — только DAG. Переиспользование legacy классов допускается лишь после проверки вложенных вызовов; существование NativeRiverReliefPublicationJob или SurfacePlanningCapture само по себе не принимает их orchestration. [Карта адаптации данных и проверок](source-proof-v2-contract-spec.md#61-адаптация-найденных-механизмов-к-целевому-pack--без-доменной-оркестрации).

Порядок из owning ТЗ сохраняется: admission готовых источников/evidence → полный manifest → codec/storage, без запуска producers.

1. `PackPreparationValidator` проверяет immutable input, мир, addresses, нормализацию и fingerprint через existing canonical encoding. Pure validation до нового IO эффекта. Полный fingerprint должен включать все semantic поля body; operation_id и transport receipts в него не входят.
2. `PackPreparationOperation` через внутренние принятые ports проверяет identity/replay операции и доступность capture/base. При повторе возвращает подтверждённый прежний candidate; другой body с тем же ID — конфликт. Конкретные scoped ports зависят от R2 и не выдумываются здесь.
3. Для new частей validator проверяет согласованность единственных address/ref и полного provenance с capture и owning правилами payload; сохранность полей producer output доказывает отдельная проверка DAG mapping (§4), не сравнение двух caller-копий. Planning tuple использует existing canonical slot rules. Для inherited частей сравнивает address/ref и весь вложенный PackStoredProvenance с pinned base; текущий capture не переписывает прежний proof или planning.
4. Coverage admission: уникальные expected/completed; completed является подмножеством expected; каждый declared output разрешается в parts и соответствует producer evidence. Complete допускается только при полном expected. Один output может покрывать несколько областей. Without-payload требует подтверждённого producer outcome, не выводится из отсутствия blob. Settlement: packed ⊆ census, UID уникальны; complete требует полного census и соответствующего structure payload.
5. Проверка состава: части и metadata согласованы, удаление/изменение допускается scope, неизменённые части базы сохранены. Pack не делает повторный merge sidecar и не читает latest sources.
6. `PackManifestAssembler` строит один `WorldPackManifestV2` с parts/assembly/provenance. Durable proof остаётся в manifest; transient invocation metadata, lease и receipts не становятся условиями чтения.
7. `PackPreparationIdentityCodec`/manifest codec проверяют canonical schema и budget; операция staging/seal/retention выполняется по принятым внутренним ports. Existing `finish_pack_preparation` можно использовать только после миграции прежних spatial/climate/other_members на authoritative full manifest closure. Он не заменяет шаги 3–5.
8. Только подтверждённый READY с exact manifest/live-set возвращает PreparedPackCandidate. Head не меняется; activate — следующий самостоятельный вызов DAG. Ошибка не выдаёт READY; cleanup принадлежит Artifacts lifecycle.

Классы и отказ: validator — pure входные проверки (IO означает нарушение); assembler — сборка одного агрегата (генерация/второй contents означает нарушение); identity codec — canonical encoding (свой второй hash engine означает нарушение); operation — одна prepare операция (retry workflow/Source CRUD/producer/activate внутри означает нарушение); wrapper — одна делегация (логика маршрута означает нарушение).

### 3.1. Точная Pack-owned граница pure validation / IO

Эта детализация заменяет неоднозначность шагов 2–4 выше: pure validator **не проверяет живое удержание и не читает storage**. Он не получает context/port/provider/callback. IO исполняет внутренняя реализация одной Pack операции с принятыми storage capabilities; это не запуск нескольких публичных доменных операций.

`application/worldData/pack/preparation/validator.py::PackPreparationValidator` имеет внутренние sync методы (не отдельные открытые pipeline):

| Метод | Данные / ответственность | Эффекты и отказ |
|---|---|---|
| `validate_input(self, request: PackPreparationInput) -> None` | Strict tree, world/адреса, уникальность, scope shape, metadata exact coverage, структурная согласованность refs/provenance | Pure; PackPreparationFailure с aggregated issues. Ни storage availability, ни true-флаг caller не удостоверяют hold |
| `validate_base(self, body: PackPreparationBody, base: WorldPackManifest \| None) -> None` | Получает уже decoded и admitted точную базу; сравнивает inherited address/ref/full provenance и разрешённые изменения состава | Pure; None только для подтверждённой пустой publication, не при storage error. BASE_PUBLICATION_MISMATCH/OUT_OF_SCOPE_CHANGE |
| `validate_metadata(self, body: PackPreparationBody) -> None` | Exact metadata address → owning row projection по §2.1, согласованность assembly и parts | Pure; не computes defaults и не пересчитывает чужую геометрию |
| `validate_coverage(self, body: PackPreparationBody) -> None` | Expected/completed/census и соответствие declared outputs частям; complete по точным множествам | Pure; without_payload semantic evidence проверяется owning admission, не выводится по отсутствию bytes |

`WorldPackManifest` в сигнатуре — единственная целевая модель после удаления legacy; до завершающего rename применяется её текущее имя WorldPackManifestV2, второй public тип не вводится. Эти методы не публичный CRUD и не получают собственный lifecycle/replay.

**Что конкретно поступает из IO:** существующий `VerifiedManifestBytes(ref: ArtifactRef, payload: bytes)` из `dataModel/worldPack/read/pinnedManifest.py`, затем единственный pure manifest decoder возвращает целевой WorldPackManifest. Внутренняя operation сверяет ref с точной базой и world/publication identity **до** передачи модели в validate_base. Второй `VerifiedBase` с теми же bytes/ref не вводится. Existing `PinnedManifestReader` показывает действующий guard/read/digest/schema admission; prepare не вызывает его публичный read pipeline как самостоятельную операцию и не подделывает ManifestPinRead из одного WorldPublicationRef. Конкретный guard доступа к базе подготовки фиксируется в R2; ссылка на existing reader не выдаётся за такой готовый binding.

**Payload admission:** зарегистрированный Pack read/format binding читает verified bounded bytes через внутренний storage port и декодирует owning модель payload. Его pure валидатор сопоставляет эту модель с address/assembly/coverage до возврата управления prepare. Переиспользовать модели ClimateFieldWire/FineTerrainChunkWire/SettlementStructureWire/GradeSlotSidecar; новый универсальный payload DTO не вводить. Existing `StagedClimateFields.validate` — IO collaborator (guard/seal/hold/read), его проверки coarse/fine/origin — pure часть; его нельзя поместить внутрь PackPreparationValidator. Конкретный full roster payload bindings относится к отдельному Pack пункту 2, не скрывается в Source proof.

**Source и holds:** operation не делает latest reads, не запускает Source capture/exact-read pipeline. Pure проверки schema/equality Source proof используют только предъявленный owning type и уже переданные значения. Живое удержание/atomic adoption проверяется внутренним принятым lifecycle binding под общей защитой; pure validator не принимает caller `is_held=True`. До принятия R2 этот порт остаётся внешней зависимостью, а не заглушкой интерфейса с выдуманными гарантиями.

**Порядок одной prepare операции:** pure structural admission и canonical input fingerprint → identity/replay admission → необходимые guarded reads/admission refs/capture/base → pure base/metadata/coverage и payload relation checks → assembly → encode/budget → staging/seal/READY по принятому lifecycle. Все prerequisites одной проверки доступны до неё. Replay возвращает только durable подтверждённый результат по owning правилам; отсутствующее удержание не скрывается успешным shape check. Не создавать retry loop или запуск следующего workflow внутри operation. Независимые domain issues собираются на своём этапе; IO failure не превращается в missing part и не требует продолжать зависимую ветку.

**Аудит классов этого среза:** validator отвечает только за переданные значения; decoder — schema/bytes без IO; internal storage binding — protected read/identity/holds, не materialization; assembler — построение единственной модели; wrapper — единственная делегация; operation — lifecycle одной подготовки, не управление другими публичными операциями. Для каждого нарушение указанных эффектов — отказ. Internal storage binding ещё не принят до предъявления concrete R2 метода; это не мешает зафиксировать pure signatures и данные Pack.

**Проверки при реализации:** pure validator вызывается с immutable моделями без DI storage; duplicate/missing/foreign metadata addresses дают стабильные aggregated issues; inherited row/ref/provenance mismatch отвергается; None base при непустой publication запрещён до validator; два equal-count разных coverage множества не проходят; actual payload UID/origin mismatch отклоняется binding; при любой ошибке до assembly staging не вызывается. Restart/GC/adoption проверяются отдельно после подключения lifecycle. Эти проверки здесь описаны, не выполнены.

## 4. DAG mapping и проверка подмены

Existing `PublishedDAGReadView.require` возвращает типизированный output, `DependencyRead` фиксирует прочитанный результат; `NodeRunner` проверяет вход/выход, `DAGContext` — contract/attempt/read identity. Они не сравнивают поля нового Pack request с полями producer output автоматически.

Поэтому конкретный согласованный adapter должен передать producer evidence как immutable значение и построить parts из тех же записей; отдельно заполненные ref и proof из разных outputs запрещены. Проверка binding должна подать два разных реальных producer outcomes и показать отказ при смешении ref/address/proof, сохранение корректного output и inherited base. Synthetic fixture проверяет только локальную валидацию. Engine OutputRecord не входит в публичный Pack DTO.

Карта source → producer → Pack описывает передачу данных, а не утверждает один порядок всех операций. Full сохраняет L0 → topology; detailed location сохраняет L2 → settlement materialize; wilderness не запускает settlement. Retry/выбор scope/следующей операции только в DAG. Concrete node bindings остаются OPEN.

## 5. Что ещё нельзя честно объявить конкретной реализацией

1. Source identity: в appendix есть `SourceRevision(seq, content_hash)`, `SourceVersionRef(object_id, revision)`, `SourceBodyVersion(source, body)`, но полный discriminated union object/settings/collection identities и owning codecs не определён. Поэтому полные поля SourceCaptureInput/SourceDurableProof не фиксируются произвольным enum/string. Это блокирует окончательную Source signature/error/schema приёмку.
2. L2: existing `FineChunkRunner.refine_rects` принимает World, list NamedLocation, WorldPackWriter, MaterializationContext, SurfacePlanBundle, working maps, region state snapshot, templates и другие внутренние данные. `FineTileContext` содержит mutable DB models и рабочие карты. Ни один не годится как public FineMaterializationInput. Требуется последовательно выделить captured semantic inputs и внутреннее рабочее состояние; имя нового input этого не делает.
3. Settlement: existing TopologyResult/MaterializeResult содержат counts, но не exact census/structure ref/proof. Нужны owning topology/materialization POJO и ошибки; нельзя назначить PackPreparedCandidate их общим результатом.
4. Source pin/staging/adoption/retention ports остаются R2. До согласования запрещено подставлять bare acquire или новый OperationKind.

Итог приёмки: перечислены конкретные предлагаемые публичные классы и алгоритм Pack, точные доступные POJO и места незавершённых схем. Полностью конкретный end-to-end R1 пока НЕ предъявлен; открытые типы не маскируются Any, dict, callback или пустой wrapper. Для завершения требуется дальнейшая проработка указанных owning входов, а не подтверждение пользователем выдуманных типов. Runtime реализация этим документом не разрешена.
