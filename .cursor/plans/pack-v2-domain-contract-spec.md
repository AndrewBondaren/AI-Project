# Pack V2 — граница домена и реализация публичных операций

Дата: 2026-11-12. Детализация REV-02 по поручению пользователя. SoT: [World Pack storage](../../docs/tz_world_pack_storage.md), разделы prepare/activate, read_part, preparation errors и roster классов. Связь: [основной план](world-pack-v2-single-manifest-contract.md), [Source appendix](source-proof-v2-contract-spec.md). Статус: проект приёмки, не evidence реализации.

## 1. Что принадлежит Pack

Pack владеет публичными prepare, activate и read_part; логическими адресами частей; metadata/assembly и полным manifest; проверкой согласованности готовых входов; доменными отказами; manifest codec и разрешением адресов pinned версии. Он вычисляет полный необходимый retention set своего состава и проверяет подтверждение удержаний через внутренние принятые ports. Он не реализует второй holder store, source revision store или producer.

**Важная точность:** публичный activate — операция Pack по ТЗ. Publication/Snapshot предоставляет внутренний atomic commit/CAS/terminal механизм. Фраза «publication владеет публикацией» не означает перенос публичного API Pack в чужой домен. После gameplay применяется Snapshot-owned подготовленный PatchSet; самостоятельная pregame activation не становится обходом Snapshot.

| Внешний владелец | Что передаётся Pack / используется внутренне | Что Pack не делает |
|---|---|---|
| Source | Immutable capture/evidence и подтверждение source retention по принятому внутреннему scoped binding | Не читает latest source, не назначает revisions, не восстанавливает отсутствующий proof из hash |
| Producer | Точные payload refs, addresses, coverage, metadata и evidence результата | Не запускает materialization, не реконструирует адреса из счётчиков, не достраивает missing parts |
| Artifacts | Staging/seal, bounded verified reads, adoption/holds/closure contracts | Не пишет отдельный blob store и не моделирует lifecycle holders в manifest |
| Publication | Atomic expected comparison, handoff, durable terminal/recovery | Не делает собственный COMMIT вокруг части общей операции |
| DAG | Передаёт POJO, выбирает retry/следующую операцию по outcome | Не передаёт callbacks/providers/backends; открытый pipeline Pack не выбирает следующую DAG-стадию |
| Cache | Отдельная операция DAG с key/entry | Pack не запускает Cache.get/create и не владеет hit/miss маршрутом |

## 2. Публичные операции: существующие и целевые контракты

**Последующее поручение пользователя 2026-11-12:** порядок самостоятельных изменений должен быть открыт DAG через конкретные публичные операции Pack. [Проект публичных write-контрактов](pack-v2-public-write-operations.md) содержит методы, V1 disposition, передачу immutable state и gates. Он заменяет прежнюю идею исполнения списка обновлений одним assembler/prepare: assembler формирует manifest из конечного состояния, а не исполняет операции; prepare завершает подготовку. Сборка остаётся ответственностью Pack, но последовательность write-вызовов принадлежит DAG. Документ — проект для приёмки, не runtime evidence; прежние схемы inputs ниже должны читаться с этим уточнением.

### Принятая граница сборки состава (2026-11-12)

Пользователь подтвердил сохранение старого поведения и ответственности Pack: DAG передаёт закреплённую базу и готовые результаты выбранных доменных операций; полный итоговый состав собирает Pack внутри одной подготовки. Прежнее требование полного итогового состава уже на входе prepare отменено. Полнота обязательна для выходного manifest. Конкретный входной POJO требует дальнейшей детализации; прежние таблицы PackPreparationBody/parts не являются замороженной схемой обновлений.

Основание: WorldPackWriter.__init__ загружает базу; commit_chunk и write_location_terrain заменяют запись по адресу, сохраняя остальные; write_locations_index и replace_region_index заменяют соответствующий индекс целиком; recalc_manifest_counters считает по итоговому составу. Отсутствие нового результата не означает удаление базовой части. Для незатронутых частей сохраняется полный исходный provenance. Пустой grade incoming сохраняет прежние slots по существующему incoming-first алгоритму владельца payload; Pack не повторяет этот алгоритм.

PackPreparationOperation владеет одной подготовкой и внутренним доступом к pinned base. **Уточнение принято пользователем 2026-11-12:** существующий проект `PackManifestAssembler` в `preparation/assembler.py` получает проверенную базу и проверенные типизированные обновления и за один pure-вызов формирует полный immutable manifest по прежним правилам. Дополнительный класс сборки не вводится. Это обработка данных, не выбор/запуск стадий. DAG не знает правил изменения manifest; Pack не вызывает producers, не выбирает следующую операцию и не запускает activate. Конкретные Input/Output/Error ещё требуют детализации; новый публичный pipeline этим решением не вводится.

**Наличие обновления — часть принятой семантики входа.** Отсутствие результата для адреса сохраняет базовую часть; новый payload заменяет только соответствующую часть. Для region index отсутствие обновления сохраняет индекс, переданный пустой индекс заменяет его пустым (`replace_region_index`). В `publish_settlement_structure` значение `packed_district_uids=None` сохраняет прежний список, явно переданный пустой список заменяет его пустым; `structure_status=None` сохраняет прежний статус. При отсутствии прежней settlement-записи V1 использует пустой список и статус absent; в реализации использовать owning ограничения/defaults, не вводить новые литералы политики. В immutable входе списки представлены tuple, но различие отсутствующего обновления и явного пустого значения сохраняется. Эта таблица фиксирует поведение, не выбирает универсальный patch DTO или nullable-схему для всех полей.

Проверки assembler: база не мутирует; отсутствие обновления сохраняет значение и provenance; пустая замена индекса действительно очищает индекс; settlement preserve и empty replacement различаются; замена части A не изменяет B. Допустимые зависимости — проверенные Pack POJO и pure правила их обработки. IO, вызов producer, выбор следующей публичной операции, повторный merge содержимого grade payload или изменение прежней семантики означают отказ в приёмке.

Приёмка этой ответственности: обновление A сохраняет B/ref/provenance; отсутствие результата для адреса сохраняет базовую часть; переданный полный индекс заменяет соответствующий индекс; счётчики вычислены по итоговому составу. Нарушение: DAG собирает manifest, Pack запускает чужую операцию, пропуск трактуется как удаление либо универсальный merge меняет прежние правила разных видов данных. До фиксации входных типов и roster классов решение не разрешает runtime-реализацию.

**Уточнение принято пользователем 2026-11-12:** PackPartInput содержит address/artifact один раз. Его new/inherited provenance оборачивает общий полный PackStoredProvenance(source_proof, planning); отдельный PackProducedPartEvidence исключён. Inherited address/ref и полный provenance сверяются с pinned base и сохраняются неизменными. Конкретный source_proof разрабатывает другой агент. [Точные Pack-типы и граница mapping](rev-02-r1-public-pipelines.md#2-pojo-pack-и-связанного-результата). Решение закрывает выбор структуры Pack-входа, не весь R1.

### prepare

`PackPreparationPipelineOpenPipeline.prepare(request: PackPreparationInput) -> PreparedPackCandidate` — async. Публичный файл по ТЗ: `application/worldData/pack/packPreparationPipelineOpenPipeline.py`; один вызов `PackPreparationOperation.prepare` из `preparation/operation.py`. Ни циклов retry, ни вызова activate после prepare.

Input переиспользует проект ТЗ: operation_id, preparation_fingerprint и единственный body. Body содержит world_uid, capture, base_publication, scope, parts, assembly, assembly_provenance. Конкретные Source/producer-типы ещё проходят внешний gate; их нельзя заменять Any, dict, строкой или локальным зеркалом. Адреса/assembly/errors принадлежат Pack. Это не новая версия входа поверх уже описанного в ТЗ.

Success — существующий [PreparedPackCandidate](../../backend/app/dataModel/worldPack/activation/candidate.py): operation_id, manifest: ArtifactRef, preparation_fingerprint. Выдаётся только после seal и READY для точного live-set. active head не изменяется.

Failure — `PackPreparationFailure(error: PackPreparationError)` по ТЗ; code/field path принадлежат Pack, инфраструктурная ошибка сохраняет infrastructure type, cancellation не превращается в доменный отказ. Локальная ошибка до IO не создаёт reservation; поздняя ошибка не выдаёт candidate/READY. Cleanup/replay исполняется принятым lifecycle Artifacts, не ad-hoc удалением файлов.

### activate

Удержание READY_INACTIVE и release: [трассировка existing OperationHolder/retention](pack-inactive-retention-trace.md). Найдено сохранение operation hold на manifest после terminal; новый holder kind не является доказанной необходимостью. Независимый release и scoped cleanup общего closure остаются отдельным gate владельца Artifacts/publication.

Уточнение existing refusal/replay механизма: [трассировка Pack activation refusal](pack-activation-refusal-trace.md). Mapping в SnapshotApplyResult(REJECTED) уже предложен owning ТЗ; повторный выбор lifecycle не нужен. Остаток — concrete Pack issue types, canonical registration/composition и проверка восстановления публичного отказа без потери diagnostics.

`async activate(request: PackActivationInput) -> PackActivationResult | PackActivationRefusal | OperationCancelled` — уже описанная публичная операция Pack. Input — существующий [PackActivationInput](../../backend/app/dataModel/worldPack/activation/input.py), полный expected: WorldPublicationRef и три поля candidate. Результаты переиспользуют [publication.py](../../backend/app/dataModel/worldSnapshot/results/publication.py); второй PackActivationResult не вводится.

Внутри: admission operation/candidate/expected → принятый scoped atomic commit для полного expected/CAS, handoff и terminal. Это локальная реализация одной операции, не запуск следующего domain pipeline. ACTIVE и READY_INACTIVE различаются по существующей матрице ТЗ; CAS conflict не означает потери candidate hold. Повтор после потери ответа читает durable terminal, не повторяет CAS. Busy/infrastructure/unknown outcome сохраняют owning семантику.

Публичный wrapper и точный внутренний activation binding в проверенном Pack-коде не подтверждены. Наличие входного/выходного POJO и operation ledger не объявлять завершённой реализацией activate. Новую внутреннюю сигнатуру не выдумывать до сверки owning publication port.

### read_part

Переиспользовать **уже описанный в ТЗ** `PackPartReadPipelineOpenPipeline.read_part[T: BaseModel](request: PackPartReadInput[T]) -> PackPartReadResult[T] | PackPartAbsent | PackPartReadRefusal`. Публичный wrapper в `read/packPartReadPipelineOpenPipeline.py`, единственная делегация `PackPartReadOperation.read_part` в `read/packPartReadOperation.py`.

Input: pin (store/execution/invocation/logical_read_key/pin_id/publication), logical address, typed contract id/version, budget. Caller не подставляет произвольный child ref. Budget: max_manifest_bytes, max_index_bytes, max_payload_bytes, max_total_bytes; положительные strict int, повторный IO тоже расходует total.

Result: publication, manifest ref, address, contract, artifact ref, materialized immutable value T, persisted provenance. ABSENT допустим только при отсутствии адреса в успешно проверенном полном pinned manifest. Closed pin, corruption, missing hold/blob и unsupported format не превращаются в ABSENT. Чтение после закрытия guard не требует IO; повторное storage чтение требует нового действующего pin.

Read готового manifest/payload **не ждёт live Source CRUD и не перечитывает sources ради доказательства свежести**. Он проверяет сохранённое provenance по схеме и identity версии; удержания проверяются через storage lifecycle. Недостающий конкретный persisted proof type блокирует freeze схемы ответа, но не требует запуска source capture при read.

### Существующий низкоуровневый manifest read

[PinnedManifestReader](../../backend/app/application/worldData/pack/read/pinnedManifestReader.py) уже имеет отдельные resolve, read_verified и admit_cached. [ManifestPinRead/ManifestAddress/ManifestStorageRead/ManifestCachedRead](../../backend/app/dataModel/worldPack/read/pinnedManifest.py) — существующие данные. На cold и cached пути pin проверяется заново; cached admission проверяет identity и digest/nbytes. При миграции сохранять эти гарантии. Этот reader возвращает bytes и не заменяет read_part. Выбор cache hit/miss остаётся у DAG; объединение read_part с cache не вводить без отдельного согласования маршрута.

## 3. Внутренние классы Pack и предел переиспользования

| Класс / файл | Ответственность, вход → выход | Допустимые эффекты / отказ |
|---|---|---|
| PackPreparationValidator, preparation/validator.py (проект ТЗ) | Полный typed input → проверенные данные либо aggregated Pack issues | Pure. IO, producer call, latest read или acceptance только по counts — отказ |
| PackManifestAssembler, preparation/assembler.py (проект ТЗ) | Проверенная pinned база + проверенные типизированные обновления → полный WorldPackManifestV2 по прежним правилам writer | Pure, база не мутирует. IO, выбор операций, второй contents object, пересчёт producer geometry, переписывание inherited proof или потеря различия preserve/empty replacement — отказ |
| PackPreparationIdentityCodec, preparation/identityCodec.py (проект ТЗ) | Канонический PackPreparationBody → fingerprint | Existing Encoding registration; не отдельный дублирующий identity POJO. Изменение значимого поля должно менять fingerprint |
| PackPreparationOperation, preparation/operation.py (проект ТЗ) | Один prepare request → READY candidate | Только принятые внутренние ports, admission/assembly/staging этой операции. Generator/Source public CRUD/Cache callback или собственная публикация head — отказ |
| [finish_pack_preparation](../../backend/app/application/worldData/pack/encoding/preparedManifest.py) (существует) | Проверяет lease/world, кодирует manifest, stage, finish_preparation и точный READY record | Переиспользовать seal/READY/digest checks; заменить сбор spatial_roots/climate/other_members на единый authoritative manifest + registered closure. other_members не оставлять как способ скрыть неполную схему |
| [packManifestCodec](../../backend/app/application/worldData/pack/encoding/packManifestCodec.py) (существует) | V2 manifest ↔ bytes | Strict recursive admission, budgets, версии. Цель — без WorldPackManifest legacy projection; decoder не делает IO |
| [manifest_format](../../backend/app/application/worldData/pack/encoding/manifestFormat.py) (существует) | Ограниченный bytes binding | Возвращает исходные valid bytes. Schema/storage version меняются совместно, без reinterpretation старых bytes |
| PackPartReadBindingRegistry, read/partReadBindings.py (проект ТЗ) | Exact descriptor → registered address types/format versions/T/decoder | Только composition registration. Unknown/duplicate contract, type mismatch, mutable result — отказ; публичный DTO не содержит executable binding |
| PackPartReadOperation, read/packPartReadOperation.py (проект ТЗ) | Pin/address/contract/budget → read result/absent/refusal | Guard + verified bounded IO + pure decoder. Подмена pinned publication latest или возвращение lazy value — отказ |
| [StagedClimateFields](../../backend/app/application/worldData/pack/encoding/stagedClimateFields.py) (существует) | Проверки готовых coarse/fine refs и origin | Переиспользовать проверки; адреса читать из parts, не поддерживать второй независимо обновляемый climate индекс |

На каждый открытый pipeline — одна прямая делегация реализации. Validation branches внутри атомарной операции не превращаются в выбор внешнего workflow. Точный approved DAG binding — отдельная проверка интеграции, новые ноды этим документом не назначаются.

## 4. Pack-owned ошибки

Сохраняется проект ТЗ `dataModel/worldPack/preparation/errors.py`: immutable PackPreparationError(reason, непустой issues), concrete PackPreparationIssue наследует FieldPathError с PackPreparationIssueCode. Причины: INVALID_INPUT, IDENTITY_CONFLICT, SOURCE_UNAVAILABLE, DEPENDENCY_MISMATCH, ARTIFACT_UNAVAILABLE, MANIFEST_OVERSIZE, OPERATION_CLOSED.

Коды по ТЗ: DUPLICATE_ADDRESS, MISSING_PART, UNEXPECTED_PART, FORMAT_MISMATCH, ADDRESS_MISMATCH, SOURCE_PROOF_MISMATCH, BASE_PUBLICATION_MISMATCH, STATUS_MISMATCH, IDENTITY_MISMATCH, HOLD_MISSING, ARTIFACT_UNSEALED, MANIFEST_LIMIT_EXCEEDED, SOURCE_HOLD_MISSING, OPERATION_CLOSED, METADATA_PROOF_MISSING, OUT_OF_SCOPE_CHANGE. Не копировать SourceIssue в Pack под новым именем: Pack формирует свой issue только о нарушении своего входа/операции; инфраструктурная причина сохраняется.

Для read_part использовать PackPartReadReason из ТЗ: INVALID_PIN, CLOSED_PIN, PUBLICATION_MISMATCH, CONTRACT_MISMATCH, MISSING_HOLD, UNSEALED, BUDGET_EXCEEDED, INVALID_MANIFEST, INVALID_INDEX, MISSING_ARTIFACT, INVALID_PAYLOAD, INVALID_PROVENANCE. Existing ManifestReadReason остаётся владельцем низкоуровневого manifest API до явно согласованного объединения; зеркальный третий набор кодов не вводить.

Независимые ошибки одного validation этапа агрегируются existing ValidatorAggregationHelper из dataModel/validation/diagnostics. Невалидный parent исключает лишь зависимую ветку; независимые адреса продолжают проверяться в стабильном порядке. Typed paths строятся от owning моделей через FieldRef/CheckedPath, не произвольными strings.

## 5. CRUD и настройки: не подменять семантику

Проект публичного удаления владения неактивным кандидатом: [Pack candidate release](pack-candidate-release-contract.md). Вход переиспользует PreparedPackCandidate; release READY_INACTIVE отделён от cancel, удаления logical part и GC. Concrete Pack result/refusal описаны, внешний atomic release binding и полная приёмка остаются OPEN.

**Ссылки на уже принятые решения по настройкам — не открывать повторно:** [конфигурация экземпляра Cache](cache-public-contracts.md#конфигурация-экземпляра-cache) фиксирует immutable CachePolicy до пересоздания экземпляра и исключает CacheSettingsService/runtime-переопределения. Источник `[world_pack.manifest_cache]` → WorldPackCacheSettings → AppSettings.world_pack согласован в [разделе доменных контрактов Cache](cache-public-contracts.md) (абзац «Источник второй политики — согласовано пользователем 2026-11-10»). Existing `manifest_max_bytes` передаётся явно при регистрации storage binding — [ТЗ Pack, регистрация формата manifest](../../docs/tz_world_pack_storage.md) (абзац «Регистрация формата manifest V2»); конкретное deployment-значение там оставлено открытым. Эти решения не требуют повторного выбора источника конфигурации или введения горячего обновления. Формальная сверка общего CRUD-критерия Pack остаётся отдельной проверкой владения и существующих контрактов; она не отменяет решения Cache и сама по себе не разрешает новый сервис настроек.

| Операция | Pack V2 |
|---|---|
| Create версии | prepare создаёт immutable candidate; activate отдельно делает версию активной |
| Read | read_part по pinned publication; существующий manifest bytes read сохраняет отдельный контракт |
| Update | Новый полный candidate на pinned base, затем activation; in-place update manifest/payload отсутствует |
| Delete | Удаление логического part — новый состав при разрешающем scope/proof. Физический release/GC — owning Artifacts lifecycle; Pack не unlink-ает опубликованные файлы. Публичный release неактивного candidate требует отдельного конкретного контракта ТЗ и не объявляется реализованным |
| Настройки | Assembly содержит effective captured settings; Pack не читает latest World и не выбирает новые defaults. Existing WorldPackCacheSettings — configuration manifest cache/budget. Публичный mutable CRUD config этим проектом не вводится; отсутствие settings CRUD нельзя молча объявить прошедшей общей CRUD-приёмкой |

## 6. Роли payload: сверка writer → reader → retention (2026-11-12)

Источники: [WorldPackPaths](../../backend/app/application/worldData/pack/io/worldPackPaths.py), [WorldPackWriter](../../backend/app/application/worldData/pack/io/worldPackWriter.py), [WorldPackReader](../../backend/app/application/worldData/pack/io/worldPackReader.py), [PacksWiring](../../backend/app/core/container/packs.py). Таблица фиксирует готовые механизмы и конкретные недостающие Pack bindings; наличие пути/codec V1 не означает наличие зарегистрированного artifact format.

| Логический адрес V2 | Фактическая запись V1 / payload | Фактическое чтение / переиспользование | Что требуется для полного V2 |
|---|---|---|---|
| map_tile(gx, gy) | write_world_map_tile → world_map_tile_payload → TileCodec WORLD_MAP; path/hash в tile entry | read_world_map_tile → parse_world_map_tile_payload; возвращает side и list WorldMapCellWire | Owning artifact format/read binding и immutable output; проверить side/адрес/grid; заменить path/hash одним ArtifactRef |
| wilderness_chunk(gx, gy, cx, cy) | write_wilderness_chunk → FineTerrainChunkWire + TileCodec FINE_TERRAIN → commit_chunk | read_wilderness_chunk → parse_fine_terrain_chunk_payload | Binding FineTerrain, соответствие chunk coordinates/grid, ref и provenance на каждый адрес; status не выводить только из количества |
| location_terrain(location_uid) | write_location_terrain использует тот же FineTerrain payload; territory в LocationTerrainEntry | read_location_terrain → тот же parser | Переиспользовать payload schema, не дублировать только ради иной роли. Отдельная address/territory admission; location role не равна chunk role |
| settlement(location_uid) | encode_settlement_structure_tmp/publish_settlement_structure, structure_path/hash/bytes и packed_district_uids | parse_settlement_structure_blob; framed/обычный формат и registry-dependent чтение | Сохранить frame/kind/version checks; concrete immutable read contract и declared dependencies. Не переносить callback/live registry в возвращаемое value; tmp-файл не объявляется persisted частью |
| climate_coarse | write_climate_coarse; существующий CLIMATE_FIELD_FORMAT | read_climate_coarse; V2 decode_climate_field | Binding уже есть; роль обязана быть coarse. Ref перемещается из отдельного climate_coarse_ref в parts без второго authoritative поля |
| climate_fine(gx, gy) | write_climate_tile; тот же CLIMATE_FIELD_FORMAT | read_climate_tile; StagedClimateFields проверяет fine и origin | Переиспользовать format; сохранить origin из gx/gy и captured span. Ref из tile.climate_fine_ref переносится в parts |
| locations_index | write_locations_index → LocationsIndexWire JSON | locationsIndexRead и существующий wire POJO | Bounded immutable artifact binding; порядок pins значим для map_tile.location_pin. TerritoryVolume в payload отсутствует, равенство UID-набора с terrain metadata не вводится. [Trace и проверки](pack-locations-index-binding.md) |
| spatial_root(domain) | SpatialDomainRootRef уже принимает конкретный hydrology root descriptor | OpenWaterBlobReader / pinnedSpatialReader, root и shards | Переиспользовать owning hydrology format/profile; root — часть manifest, shards — transitive refs. Нельзя считать refs только корня полным live-set |
| tile_grade_slots(gx, gy) | merge_grade_slot_sidecar через merge_grade_cell_slots_tile | read_grade_cell_slots_tile | Полный результат merge от producer; зарегистрированный sidecar format и точный pinned base evidence; Pack не делает merge в prepare |
| location_grade_slots(location_uid) | тот же sidecar helper для location | read_grade_cell_slots_location | Тот же payload binding с иной address admission; не отдельный зеркальный payload POJO |

**Подключение по коду:** initialize_pack_storage в PacksWiring регистрирует manifest и climate. Spatial descriptor знает HYDROLOGY_OPEN_WATER/ROOT_V1; это не доказательство подключения всех spatial storage bindings именно этой фабрикой. Для остальных ролей в просмотренном Pack encoding/composition готовые artifact bindings не найдены. Их имена/версии нельзя придумать при замене paths на refs: owning format constants, codec и registry entry должны вводиться согласованно и проверяться на V1 fixtures.

### 6.1. Единственный источник retention set

Существующий [finish_pack_preparation](../../backend/app/application/worldData/pack/encoding/preparedManifest.py) собирает other_members, spatial roots, climate refs, затем manifest. Existing [retain_climate_members](../../backend/app/db/repositories/sqlite/worldPack/climateRetention.py) проверяет scope/operation/world, точное соответствие manifest bytes descriptor, APPLYING, seal и OperationHolder, затем выдаёт climate children ArtifactRetentionHolder(manifest). Это реальная основа: общий hold алгоритм не создаётся заново, climate-specific выбор детей расширяется на принятый полный состав.

Целевой Pack-owned расчёт: manifest ref + refs всех parts + transitive refs по owning format closure + durable source refs, требуемые provenance всех частей и assembly. Deduplication storage refs допустима; два разных logical addresses одного ref сохраняют отдельные записи/proofs. Ни отсутствие записи в other_members, ни cache hit не доказывают отсутствие dependency.

Тот же проверенный состав используется для READY, публикационного handoff и проверки read reachability. Closure discovery использует внутренние зарегистрированные format contracts над готовыми данными/verified indexes, не вызывает producers или публичный Source API. Полнота и происхождение source closure подтверждаются owning evidence. Самостоятельный обход неизвестного формата запрещён: unsupported format/ref — отказ, не пропуск.

Порядок: pure input/schema/duplicate checks → проверка готовых payload/evidence и требуемых удержаний через согласованные ports → сборка одного manifest → canonical bytes/budget → stage/seal manifest → точное finish_preparation → candidate. При activation: один scoped commit для проверки кандидата/expected, передачи полного набора holds, CAS и terminal. Новые отложенные side-effects после commit не допускаются.

Особая проверка существующего helper: retain_climate_members сравнивает descriptor с повторно encoded manifest. Для общей схемы нельзя подменить identity исходных bytes перекодированной семантически эквивалентной формой. Internal context должен сохранять exact verified/staged manifest bytes/ref; canonical encode используется при создании, а read identity — digest исходных bytes.

Тесты closure: child одного spatial root отсутствует; source body только у inherited части; одинаковый ref на двух адресах; отсутствует hold одной metadata dependency; лишний ref в finish_preparation; release старой версии при retained B в новой; rollback после частичного handoff. Ошибка не выдаёт READY и не меняет head; physical unreferenced staged blobs чистит owning lifecycle.

### 6.2. Metadata без молчаливой потери V1 семантики

| Поле | Подтверждено кодом | Решение/ограничение для спецификации |
|---|---|---|
| pack_version / codec_version / payload_format | Отдельные поля manifest, сохранены решением пользователя | Не удалять. Конкретная wire semver новой схемы ещё не выбрана; storage version 2 не выбирает её автоматически |
| registry_hash | Декларация nullable str; writer/reader в проверенном Pack-пути не найден | Не заменять capture hash и не объявлять ненужным только по этому поиску. До freeze нужна owning семантика либо явное решение сохранить opaque legacy metadata |
| location z_band | Nullable str в entry; packFineTerrainReadFacade отдаёт его в ответе | Это наблюдаемое read-поле. Нельзя удалить как якобы неиспользуемое; сохранить до owning terrain решения о typed представлении |
| wilderness_tiles_total | Декларация default 0, writer расчёта в проверенном Pack-коде не найден | Не вычислять новое значение по len(tiles) без нормативного смысла; отдельное решение о сохранении/выводе из новой схемы |
| world_map_cells | recalc_manifest_counters суммирует side² для tiles с world_map_path | В V2 считать по подтверждённым map_tile parts и effective side, не по наличию legacy path |
| wilderness_chunks_baked | Сумма длины tile.chunks | В V2 считать по уникальным подтверждённым chunk addresses; не использовать count как proof coverage |
| wilderness_refine_status | Политики counts/unknown expected в V1 | Смысл absent/partial/complete сохраняется, доказательство покрытия усиливается exact expected/completed addresses |
| last_l0_mode/grid/depth | sync_world_metadata и owning settings | Передаются effective captured values; detailed не меняет last L0 mode, Pack не добирает defaults из latest World |

**Результат этой сверки:** определены десять ролей payload, существующие codecs/readers и алгоритм полного retention set. Полноценная реализация REV-02 всё ещё требует missing bindings и конкретного proof; менять только поля manifest недостаточно. Эта таблица сужает вопросы до конкретных строк и не объявляет новый workflow или новый source домен обязанностью Pack.

### 6.3. Пункт 1 — проверка решений перед freeze схемы (2026-11-12)

**Решение пользователя 2026-11-12: все четыре решения таблицы ниже приняты (ACCEPTED).** Это актуальная целевая схема и приоритетное уточнение прежних OPEN формулировок §6.2. Runtime ещё не изменён, полный пункт 1 не закрыт. Адреса/assembly из owning ТЗ переиспользуются с исключением согласованных полей; полная provenance schema остаётся зависимой от конкретного Source proof и не подменяется локальным типом.

Повторный поиск `registry_hash|wilderness_tiles_total` по backend и frontend нашёл только объявления `worldPackManifest.py:103,114` и проверку registry_hash в `tests/spatial_pack/test_manifest_versions.py:158`. Это граница статической проверки репозитория: она не доказывает отсутствие внешних или импортированных значений. Поиск location z_band подтвердил отдачу `entry.z_band` в `packFineTerrainReadFacade.py:145`; frontend consumer не найден. Числовой `ParentLightRefinePolicy.z_band` остаётся отдельным действующим алгоритмическим параметром.

| Вопрос | Concrete предложение | Основание и предел |
|---|---|---|
| Wire version | ACCEPTED: `pack_version = "3.0.0"`, `ArtifactRef.format_version = 2`, прежний format key `world_pack.manifest.json`; Python-класс WorldPackManifestV2 сохраняется | Existing wire 2.0.0 означает прежнюю spatial-схему при storage version 1. Codec_version/payload_format сохраняются без изменения семантики. |
| registry_hash | Исключить из новой полной схемы и assembly | В коде нет вычисления или semantic read; source provenance заменой этого поля не объявляется. Не синтезировать общий registry hash из capture. Удаление только после явного решения пользователя; прежний wire до cutover сохраняется. |
| wilderness_tiles_total | Исключить из новой полной схемы | В коде нет writer/consumer; нулевой default не задаёт смысл total. Expected coverage задаёт ожидаемый состав конкретной операции, это не автоматическое определение глобального total. Existing world_map_cells/wilderness_chunks_baked сохраняют вычисляемую семантику. |
| LocationTerrainEntry.z_band | Исключить строковое поле из новой location assembly; отдельно учитывать изменение legacy read projection при cutover | В проверенном пути writer не заполняет его, но read отдаёт. Поэтому это наблюдаемое изменение интерфейса, требующее явного согласования. Не удалять и не менять числовой ParentLightRefinePolicy.z_band. |

Для трёх строк исключения полей разрешение пользователя получено; фразы об отдельном решении в обоснованиях описывают выполненное условие, а не новый запрос. Эти решения не требуют новых доменов/pipelines или изменения Cache. Owning ТЗ синхронизировать в разрешённом документальном скоупе перед реализацией. Для старых bytes не выводить отсутствующие proofs и не превращать старый manifest в новый простым изменением версии. Полный freeze остаётся OPEN до конкретизации address/assembly/provenance и обязательной приёмки.

### 6.4. Состав assembly после принятого исключения полей

Следующий результат пункта 1: состав ниже взят из проекта owning ТЗ с применением решения §6.3. Это конкретизация прежней схемы, не введение новых смысловых данных. Единственная декларация metadata используется preparation и stored manifest; не создавать два независимых набора полей/validators.

`PackAssemblyInput` содержит ровно:

- `last_l0_mode: PackBakeMode`;
- `fine_cells_per_map_cell: int`, `world_map_cells_per_tile: int`, `fine_cell_size: int`, `map_subsurface_depth: int`, `terrain_chunk_columns: int` — strict effective значения по owning constraints, без заполнения отсутствующих полей defaults; terrain_chunk_columns принят пользователем 2026-11-12 (§6.6);
- `tiles: tuple[PackTileAssembly, ...]`;
- `locations: tuple[PackLocationAssembly, ...]`;
- `settlements: tuple[PackSettlementAssembly, ...]`;
- `wilderness_regions: tuple[WildernessRegionEntry, ...]`.

Вложенные записи:

- `PackTileAssembly(gx: int, gy: int, climate_status: ClimateBakeStatus, wilderness_refine_status: WildernessRefineStatus, chunks: tuple[PackChunkAssembly, ...])`;
- `PackChunkAssembly(cx: int, cy: int, refine_role: ChunkRefineRole | None)`;
- `PackLocationAssembly(location_uid: EntityUid, territory_volume: TerritoryVolume, climate_status: ClimateBakeStatus)`;
- `PackSettlementAssembly(location_uid: EntityUid, territory_volume: TerritoryVolume, structure_status: SettlementStructureStatus, packed_district_uids: tuple[EntityUid, ...])`.

Названия status/role и TerritoryVolume переиспользуются, их семантика не меняется. WildernessRegionEntry переиспользуется из `dataModel/worldPack/meta/wildernessRegionEntry.py`; у существующих полей region_uid/spec_fingerprint строковая форма, её нельзя молча заменить EntityUid/RevisionHex без owning проверки. Строгость nested wire admission проверяется отдельно, frozen existing модели недостаточно для полной strict границы.

В assembly нет ArtifactRef/path/hash/bytes: все payload refs только в parts. Нет registry_hash, строкового location z_band и wilderness_tiles_total. World_map_cells/wilderness_chunks_baked — вычисляемые проекции состава, не второй independently authored input. Header proof покрывает scalars; tile proof исключает chunks, у каждого chunk отдельный адрес proof. Location/settlement/region получают собственные metadata proof. Полный schema freeze остаётся OPEN по concrete proof/codec и окончательной сверке общего размещения metadata POJO.

### 6.5. Адреса payload и связи с metadata

Pack-owned `PackPartAddress` — discriminated union следующих десяти вариантов из owning проекта ТЗ; поля координат strict int, UID — existing EntityUid, domain — existing SpatialDatasetKind. Unknown discriminator/extra fields запрещены. Отрицательные macro gx/gy допустимы; локальные cx/cy неотрицательны и проверяются по captured геометрии, не latest World.

| Класс / kind | Поля после kind | Связь с assembly / admission |
|---|---|---|
| PackMapTileAddress / map_tile | gx, gy | Существующая tile row; payload side соответствует effective world_map_cells_per_tile |
| PackChunkAddress / wilderness_chunk | gx, gy, cx, cy | Tile и chunk row; координаты/размер payload согласованы с геометрией области |
| PackLocationTerrainAddress / location_terrain | location_uid | Location row и её TerritoryVolume; не смешивать с settlement той же UID |
| PackSettlementAddress / settlement | location_uid | Settlement row; payload соответствует packed_district_uids/census admission |
| PackCoarseClimateAddress / climate_coarse | нет | Singleton; coarse payload; отдельной копии ref в header нет |
| PackFineClimateAddress / climate_fine | gx, gy | Tile row; fine status и origin по captured macro span |
| PackLocationsIndexAddress / locations_index | нет | Singleton; owning LocationsIndexWire и согласованность перечисленных metadata identities |
| PackSpatialRootAddress / spatial_root | domain: SpatialDatasetKind | Owning root descriptor; SpatialDomainRootRef.validate_descriptor — существующий источник правил, не новая таблица domain→format |
| PackTileGradeSlotsAddress / tile_grade_slots | gx, gy | Tile row; полный sidecar от producer, не дельта и не merge внутри Pack |
| PackLocationGradeSlotsAddress / location_grade_slots | location_uid | Location identity по принятому индексу; тот же GradeSlotSidecar payload format, иная роль |

PackPartInput хранит address/ref один раз; stored part — тот же address/ref и полный durable provenance без new/inherited. Равные ref у разных адресов разрешены, дубли адреса запрещены независимо от равенства bytes. Отсутствие optional payload не превращает metadata row в absent и не отменяет обязательный metadata proof. Указанная row без требуемого по status/scope payload — ошибка, не implicit latest lookup. Spatial shards остаются transitive closure, не отдельными top-level parts. Region index хранится inline в assembly, отдельный region payload address не добавляется.

Повторно проверены existing `WorldPackPaths` и `SpatialDomainRootRef`. Имя legacy grade_rays файла не является названием целевого payload: целевой GradeSlotSidecar выбран прежним контрактом, debug leftover rays не вводятся как одиннадцатая роль. Финальные format/read bindings и closure каждой роли относятся к пункту 2.

**Derived counters:** `world_map_cells = Σ(side²)` по существующим map_tile parts при принятом общем effective side; `wilderness_chunks_baked` — число уникальных wilderness_chunk addresses, не число обработанных областей без payload. Основание: WorldPackWriter.recalc_manifest_counters. Эти значения — read projection единственного состава, не независимо сохраняемые поля. Не считать по metadata tiles или coverage completed и не возвращать удалённый wilderness_tiles_total.

### 6.6. Найденная недостающая часть captured геометрии chunks

Статическая цепочка: `worldMapSettings.terrain_chunk_columns(world)` читает WorldTerrainScalars → `fineChunkGeom.rects_for_macro_tile/fine_chunk_rect` используют размер для разбиения и bounds cx/cy → `FineTerrainChunkWire` сохраняет cx/cy/chunk_columns/columns. В исходном проекте PackAssemblyInput этого effective размера не было; решением ниже он добавлен в §6.4. Чтение готового payload по exact address может получить его из bytes, но pure проверка ожидаемого разбиения до payload IO и разрешение world-coordinate query по одному manifest не должны обращаться к latest World.

**ACCEPTED — решение пользователя 2026-11-12:** обязательный captured `terrain_chunk_columns: int` входит в header assembly с переиспользованием owning constraint WorldTerrainScalars; header proof и canonical preparation fingerprint покрывают это значение. Поле описывает принятую сетку версии, а wilderness payload.chunk_columns проверяется на соответствие. При partial refine изменение этой сетки не позволяет молча переинтерпретировать inherited chunk addresses; несовместимый состав отклоняется либо новая подготовка даёт полный согласованный состав. Новый default Pack не вводится; missing поле в новой схеме отклоняется, значение из latest World не подставляется. В read используется значение закреплённой версии. Это утверждённое изменение состава §6.4, не отметка runtime реализации.

**Дополнительная точность:** existing iter_fine_chunks обрезает крайние rects через min, а fine_chunk_rect проверяет число chunks через целочисленное деление. Нельзя механически скопировать обе формулы как одну policy. Перед реализацией address-range проверки переиспользовать принятый owning geometry contract с явным сценарием неделимого span/chunk size; исправление алгоритма terrain не включать в Pack. До этого bounds-check для крайних chunks не объявляется доказанным. Наличие поля header само по себе эту проверку не закрывает.

### 6.7. Трейсинг крайних chunks и предел локальной проверки Pack

Подтверждено кодом: `worldTile.iter_fine_chunks` обрезает крайний прямоугольник; `FineChunkPersist.persist_rect` вычисляет tile-local cx/cy через `tile_local_chunk_indices`, origin через `wilderness_chunk_origin` и передаёт в `cells_to_fine_terrain_chunk` полный `ctx.chunk_size`. Последний сохраняет номинальный chunk_columns и локальные lx/ly фактически переданных колонок. После partition в payload попадает только wilderness; пустой wilderness не записывается. Поэтому число columns не обязано равняться площади chunk, а отсутствие payload само по себе не доказывает незавершённость producer coverage. `PackFineTerrainReadFacade.read_wilderness_chunk` читает exact адрес и отдаёт локальные координаты; этот путь не доказывает корректность world-coordinate resolution.

Pack-owned спецификация проверки wilderness payload: cx/cy равны адресу part; chunk_columns равен captured header; пары lx/ly уникальны и лежат внутри фактического пересечения chunk с тайлом. Не требовать заполнения всех колонок и не применять этот контракт механически к location terrain. Для подтверждённого положительного span S и размера C число позиций по оси равно `(S + C - 1) // C`, начало — `tile_origin + c*C`, допустимый local extent — `min(C, S - c*C)`. Это выражение уже наблюдаемого writer-разбиения, а не разрешение Pack выполнять Terrain generation. Пример при S=65, C=32: адрес c=2 допустим, local extent=1; existing `fine_chunk_rect` отвергает его из-за floor division. Исправление production пути не выполнено и требует отдельной реализации у владельца этого пути.

**Проверено 2026-11-12 — происхождение S установлено, равенство не гарантировано.** `generators/coordinates/convert.py::map_cell_fine_span` предпочитает `world.map_settings["global_cell_size_m"]`, затем `world.fine_cells_per_map_cell`. `SurfacePlanningCapture.capture` передаёт результат в `SurfaceGridSettings.fine_span` (`dataModel/spatial/grid/gridSettings.py`) и `ClimateBaseInput.fine_span`; SurfacePlanningView проверяет согласованность сетки между своими фазами. Однако `WorldPackWriter.sync_world_metadata` записывает непосредственно `world.fine_cells_per_map_cell`, без сравнения с capture. В `World` нет поля map_settings; `WorldGridSettings` содержит fine_cells_per_map_cell (strict int, >=1000, multiple_of=1000). `WorldService.prepare_import` валидирует этот slice и вызывает `prepare_import_row`, проверяющий аргументы конструктора World. Это не механизм синхронизации двух размеров: override остаётся динамическим атрибутом, отсутствующим в persisted модели. Поиск global_cell_size_m в backend обнаружил production чтение в convert.py и присваивания в тестах, но не production writer этого override.

Контрпример воспроизведён выполнением неизменённой функции map_cell_fine_span, извлечённой через AST: fine_cells_per_map_cell=1000 без override даёт 1000; при map_settings.global_cell_size_m=2000 даёт 2000, тогда как выражение writer для header остаётся 1000. Это изолированная проверка функции, не сквозной тест bake. Existing `tests/planning/consumers/test_revisions.py::test_coordinate_overrides_and_bounds_are_resolved_without_generation` также явно ожидает override=2000 в captured grid (тест здесь не запускался).

**Расхождение owning документов, OPEN для миграции producer:** `tz_city_generation.md` §9.6 и `tz_assembler_hierarchy.md` §7.5 требуют World.fine_cells_per_map_cell и называют global_cell_size_m ghost key; `tz_generator_technical_debt.md` NC-1g фиксирует отсутствие поля на World. При этом `tz_terrain_generation.md`, полевая карта Source → input, описывает resolved global_cell_size_m/fine_cells_per_map_cell. Pack не выбирает за владельца Terrain способ устранения этого противоречия и не меняет его ТЗ молча.

**Локальный контракт Pack:** S — единственное captured значение header fine_cells_per_map_cell с уже указанными owning constraints. Второе поле span/global_cell_size_m не добавляется. Геометрия входных результатов должна соответствовать ему; при доказанном несовпадении подготовка отклоняется, без подмены header, пересчёта producer результата или чтения latest World. Existing typed mapping для сверки — SurfacePlanningView.terrain_base.grid.fine_span / climate_base.fine_span → PackAssemblyInput.fine_cells_per_map_cell; это описание источника значения, не разрешение Pack вызывать capture и не новый входной wrapper. Связь с конкретным producer output/provenance через DAG остаётся OPEN до предъявления binding; сам payload chunk_columns не доказывает размер тайла. Локальные bounds вычисляются по header по формуле выше; сквозная приёмка согласованности producer/manifest отдельно остаётся OPEN. Исправление ghost override и existing fine_chunk_rect относится к миграции соответствующих путей, не блокирует документальную конкретизацию собственного Pack validator.

Приёмочные сценарии для будущей реализации: делимый span, неделимый span, C>S, отрицательные gx/gy, колонка за обрезанным краем, повтор lx/ly, несовпадение payload address/header size, sparse wilderness и область целиком внутри location. Это требования к проверкам, не отчёт о запущенных тестах. Новые публичные операции, POJO, междоменные вызовы и перестановка утверждённых этапов здесь не вводятся; полная приёмка пункта 1 не объявляется.

### 6.8. Следующий срез пункта 2: map_tile format/read binding

**Existing trace:** `WorldPackWriter.write_world_map_tile` → `packBlobWire.world_map_tile_payload` (cells_per_side, cells) → `TileCodec.encode(PAYLOAD_KIND_WORLD_MAP=0, payload)`. Обратный путь: `WorldPackReader.read_world_map_tile` → TileCodec.decode → проверка kind → `parse_world_map_tile_payload`. В bytes нет gx/gy/world_uid или ArtifactRef: привязка к адресу принадлежит manifest part/provenance, её нельзя объявлять проверенной сравнением с отсутствующим полем payload. Payload является leaf по storage refs; строки region_uid/system_grade_uid и registry ids не превращаются в ArtifactRef. Source dependencies остаются в provenance и учитываются отдельно в closure.

**Подтверждённые пробелы:** parser делает int(cells_per_side), missing cells заменяет [], возвращает mutable list; WorldMapCellWire имеет extra=ignore и нестрогие int. TileCodec.decompress не задаёт предел распакованного объёма. PacksWiring.initialize_pack_storage регистрирует manifest/climate, но не map_tile. Поэтому ни существующий parser, ни codec целиком не соответствуют strict immutable bounded read contract. Требование предела decompressed output уже есть в owning ТЗ Pack (раздел read budgets); это не новый лимит размера мира.

**Проект конкретизации в ответственности Pack:** один `WorldMapTileWire` в `dataModel/worldPack/wire/worldMapTileWire.py`, поля `cells_per_side: StrictInt` (>0, совместимый с owning side policy), `cells: tuple[WorldMapCellWire, ...]`; frozen/extra=forbid с повторной проверкой входных instances. Переиспользовать единственный WorldMapCellWire, не создавать зеркальный набор полей клетки. Его strict admission должен быть обеспечен рекурсивно; существующее extra=ignore не считается выполнением этого требования. Проверять unique (tx,ty), диапазон [0, cells_per_side), соответствие side header.world_map_cells_per_tile. Полноту side² не добавлять без отдельного trace producer/coverage. Адрес остаётся в PackPartReadResult, не дублируется внутри payload.

Проверка отсутствия дубля: existing `ParentLightTile` — contextual refine view с world_uid/gx/gy/tile_macro и индексом cells, а не POJO записанного payload. Его from_cells приводит типы, нормализует размеры через max и затирает дубликаты ключей; использовать этот factory как wire admission нельзя. Новый payload POJO заменяет текущую неименованную пару side/list, не заменяет ParentLightTile; преобразование в refine view принадлежит соответствующему потребителю.

Storage binding остаётся `ArtifactFormatContract[bytes]`, kind BLOB: existing ArtifactFormatContract запрещает BaseModel как content_model для BLOB. Typed `WorldMapTileWire` — результат pure Pack read decoder, не storage backend content_model. Предлагаемый модуль `encoding/worldMapTileFormat.py` выполняет bounded envelope/kind/JSON/schema admission; registered decoder в существующем проекте PackPartReadBindingRegistry возвращает этот POJO без IO. Artifact reads и guard остаются у PackPartReadOperation. Новый публичный pipeline, междоменный вызов или собственный cache здесь не нужны.

**OPEN для приёмки binding:** конкретные storage/read descriptors и численные budgets, bounded decompression implementation и оценка memory expansion, field/logic error mapping в уже предусмотренные Pack errors, recursive strict admission без дублирования моделей, trace допустимого состава cells и регистрация в composition. Наличие этого проекта не означает готовность runtime или приёмку всего пункта 2. Сначала закончить map_tile, затем разбирать следующую роль из §5.

### 6.9. Проверка полноты map_tile: producer и storage имеют разные гарантии

Статический trace 2026-11-12: оба production callers `WorldPackWriter.write_world_map_tile` находятся в `WorldMapBakeOrchestrator` (bulk bake и bake_tile). Оба передают `LightGridCompose.to_wire_tile(gx, gy)`. Этот метод проходит каждый ty/tx в range(side), берёт существующую клетку либо LightGridCell.from_wire_defaults и без фильтра добавляет wire. Следовательно, этот producer выдаёт ровно side² уникальных координат полного квадрата, в row-major порядке. Existing `tests/test_light_grid_compose.py` проверяет 1024 клетки для side=32; тест здесь не запускался.

Однако это не общий инвариант текущего storage: writer не проверяет полноту, parser принимает sparse cells, а `WorldMapPackReader.sample_world_map` / `world_map_contribution` возвращают None при отсутствии выбранной клетки. `tests/test_world_pack_writer_reader.py::test_world_map_roundtrip` записывает один элемент при side=32 и проверяет чтение. Поэтому нельзя объявить sparse payload уже запрещённым или автоматически дополнить его defaults при decode. `ParentLightTile.from_cells` тоже не доказывает полноту. Derived counter side² описывает площадь представленного тайла, а не проверенное число записанных строк.

**Зафиксировано по обсуждению с пользователем:** defaults материализуются на уровне producer до передачи результата Pack. Текущий LightGridCompose.to_wire_tile передаёт полный квадрат, включая клетки с default значениями; Pack их сохраняет как готовые данные. Pack не дополняет пропуски, не выбирает defaults и не запускает producer. Предложение сделать len(cells)=side² безусловным storage-инвариантом снято: гарантия текущего producer сама по себе не запрещает sparse payload в общем контракте. Общие проверки Pack — strict положительный side, согласованность с header, типы, диапазон и уникальность координат. Полнота проверяется по утверждённому coverage конкретного результата; если оно требует полный квадрат, пропуски отклоняются без заполнения. Concrete coverage binding остаётся OPEN и не выводится из одного количества клеток. Не требовать миграции sparse fixtures только на основании снятого предложения. Проверки wilderness chunk остаются отдельными и sparse допускают.

### 6.10. map_tile: строгая граница enum-полей и разделение ошибок

Дополнительный trace существующей модели: `WorldMapCellWire._parse_role` вызывает `WorldMapHydrologyRole.from_wire`; неизвестная строка, неизвестный integer и ряд ошибочных типов превращаются в NONE, а bool проходит через int. `_parse_facing` вызывает `coerce_facing_wire`, который принимает пустую строку как None и приводит произвольное значение через str. Поэтому frozen/strict только у WorldMapTileWire не доказывает strict admission вложенной клетки: before-validators могут изменить значение раньше основной проверки. Это конкретное основание отказа в приёмке binding, а не новый алгоритм Hydrology.

Требование к целевому Pack decoder: принимать канонические wire-представления существующих enum, которые выдаёт producer `model_dump(mode="json")` (hydrology_role — integer действующего WorldMapHydrologyRole, system_facing — значение существующего Facing либо null). Неизвестный role, bool вместо integer и произвольные объекты вместо facing отклонять до permissive coercion. Не превращать неизвестное значение в NONE/null и не добавлять новые enum либо зеркальный WorldMapCellWire. Значения defaults уже материализованных producer клеток остаются обычными валидными данными. Отсутствие целой клетки регулируется §6.9 и не смешивается с неправильным значением её поля. Набор допустимых отсутствующих полей самой клетки должен соответствовать утверждённой схеме; этот trace не вводит молча required для всех default-полей.

Реализация должна использовать единственную owning декларацию клетки и enum; не делать второй ручной список допустимых полей/значений в read registry. До изменения shared validators проверить их остальных callers и import semantics; не переносить permissive authoring-нормализацию на границу persisted payload. Способ такого разделения с сохранением единственной модели остаётся предметом реализации/приёмки, здесь не объявлен готовым.

Классификация в уже заданном read contract: неизвестный format/read descriptor или неподходящий тип адреса — CONTRACT_MISMATCH; неверный kind/envelope, malformed JSON, неизвестные поля, ошибочные значения/координаты и дубли клеток — INVALID_PAYLOAD; превышение encoded либо decompressed budget — BUDGET_EXCEEDED. Ничего из этого не ABSENT. Pure decoder не конструирует refusal с pin/publication: перевод диагностик в PackPartReadRefusal принадлежит PackPartReadOperation, владеющей контекстом запроса. Конкретный внутренний typed error port ещё должен быть сопоставлен с existing error types без дублирования; infrastructure/cancellation не ловить как INVALID_PAYLOAD.

Budget trace: WorldPackCacheSettings содержит manifest_max_bytes и manifest_cache, PackBakeDefaults — zstd_level/codec_version, но готового лимита decompressed map_tile там нет. Не использовать cache capacity, zstd_level либо side² как замену byte budget. Сохранить existing публичный PackPartReadBudget для encoded IO; предел распаковки задаётся явно в конфигурации конкретного decoder/binding согласно owning ТЗ. Численные значения и оценка RAM expansion остаются OPEN до измерений; произвольные defaults здесь не назначаются. Пункт map_tile не закрыт одним добавлением POJO: требуются strict nested admission, bounded decode, descriptors и composition registration.

## 7. Критерии локальной поставки и сквозной приёмки

### Принятое основание типов обновлений (2026-11-12)

#### Конкретизация metadata updates — проект по старым методам

##### Header/grid и tile status — трассировка старой семантики

**Зафиксировано по поручению пользователя 2026-11-12:** при переходе сохраняются перечисленные ниже правила старого Pack. Coverage выполнения операции и wilderness_refine_status сохранённых chunks имеют разный смысл: полное выполнение без payload не превращает legacy absent в complete. Не заменять существующую status policy равенством completed/expected. Сохраняется порядок provisional пересчёта после chunk write и возможного final detailed пересчёта. Это требование к поведению, не приёмка ещё неполных DTO и provenance bindings; формулировка ниже об открытом расхождении обозначает требующую синхронизации прежнюю проектную формулу, а не повторный вопрос о смене старой логики.

Статическая сверка Pack 2026-11-12; runtime-проверки не выполнялись. Внешние домены не исследовались. Следующие правила ограничивают проект input updates, а не вводят новые политики.

| Область | Старый путь и порядок | Требование к обновлению |
|---|---|---|
| L0 header | WorldMapBakeOrchestrator.bake_tiles разрешает side, вызывает sync_world_metadata до записи тайлов; write_world_map_tile записывает фактический cells_per_side; после цикла caller устанавливает bake_mode | Передавать готовые effective значения L0. Last L0 mode обновляется даже при пустом цикле тайлов; не выводить наличие header update только из наличия payload. Сохранить различие authored override и resolved side, не разрешать настройки заново внутри assembler |
| Detailed header | В проверенном detailed refine нет sync_world_metadata или присваивания bake_mode | При отсутствии header update сохранять базовые значения и proof; detailed не становится новым last_l0_mode |
| fine_cell_size / map_subsurface_depth | В просмотренном Pack mutation-коде присваивания этих полей не найдены; legacy manifest имеет defaults | Не объявлять уже доказанным V1 перенос captured depth в header. Целевое требование effective captured values и первая сборка без базы требуют отдельного mapping; не заполнять пробел новой policy/default в assembler |
| Tile climate | write_climate_tile меняет только climate_status на fine, сохраняя остальные поля tile; write_climate_coarse не сбрасывает статусы существующих тайлов | Наличие готового fine результата обновляет соответствующий статус; отсутствие fine результата или обновление coarse не сбрасывает fine базы |
| Chunk commit | commit_chunk заменяет один chunk, затем recalc_wilderness_status(expected_chunks=None) | После фактической записи chunk применяется existing wilderness_refine_status_without_expected к итоговому набору chunks; прежний complete может стать partial. Нельзя самовольно сохранять complete как «более высокий» статус |
| Detailed финальный status | detailedBakeRefine после refine_rects вызывает recalc_wilderness_status с expected только при наличии expected_chunks_for_status; tiles без rects пропускает | Финальный пересчёт следует за chunk updates и может происходить без нового wilderness payload. Нужна явная информация о наличии пересчёта, а не один nullable expected на весь запрос |
| Пустой wilderness результат | FineChunkPersist.persist_rect вызывает writer только при непустом wilderness | Нет нового chunk — нет замены и provisional status-пересчёта от commit_chunk. Базовый chunk сохраняется; possible final detailed status остаётся отдельным действием |

Предлагаемая форма данных final status update: `PackTileWildernessStatusUpdate(address: PackTileMetadataAddress, expected_chunks: strict int)` в `preparation/updates.py`; отсутствие record означает отсутствие **финального** пересчёта, но не отменяет provisional пересчёт при chunk write. Record содержит данные для существующей pure policy, не callback expected_chunks_for_status. Поля proof, bounds expected и общий roster ещё не заморожены. Tile climate не требует произвольного status setter: факт fine payload и owning admission уже задают изменение по старому writer. Header update пока не объявлять полной новой моделью до mapping всех его полей.

**Открытое семантическое расхождение:** legacy wilderness_refine_status_for_counts считает complete при baked_chunks >= expected_chunks > 0 и absent при отсутствии сохранённых chunks. Проект exact coverage учитывает также processed without_payload. Поэтому равенство completed/expected нельзя автоматически использовать как замену старой policy видимого wilderness_refine_status: полностью обработанная область без wilderness payload может иметь complete coverage, но legacy status absent. Сохранять раздельно доказательство выполнения операции и статус сохранённых chunks; до явного решения не менять старую policy. Exact address admission не отменяется и counts не объявляются proof. Проверить отдельно existing excess chunks, without_payload, отсутствие final status update и complete → provisional partial → final complete. Это не принятие новых смысловых изменений.

Следующая таблица конкретизирует уже принятую ответственность, но не объявляет полный input freeze. Размещение предлагаемых records: `dataModel/worldPack/preparation/updates.py`; существующие проектные metadata addresses переиспользуются из `preparation/assembly.py`, без повторения UID/координат внутри того же record. Все коллекции tuple, records глубоко immutable. Это входные значения одной операции prepare, не команды запуска доменных операций и не новые DAG-ноды.

| Предлагаемый тип | Смысловые поля обновления | Применение к базе / источник |
|---|---|---|
| PackChunkMetadataUpdate | address: PackChunkMetadataAddress; refine_role: ChunkRefineRole либо None | Заменить metadata указанного chunk, сохранить остальные. None — записываемое значение роли, не preserve. WorldPackWriter.commit_chunk; status тайла обрабатывается отдельно по существующей policy |
| PackLocationMetadataUpdate | address: PackLocationMetadataAddress; territory_volume: TerritoryVolume | Заменить metadata одной location terrain. Старый write_location_terrain создаёт LocationTerrainEntry заново, поэтому climate_status берётся из существующего coarse default, а не наследуется автоматически. Не переносить эту политику на другие виды записей |
| PackSettlementMetadataUpdate | address: PackSettlementMetadataAddress; territory_volume: TerritoryVolume; packed_district_uids: tuple существующих UID либо None; structure_status: SettlementStructureStatus либо None | Territory заменяется. None у двух последних полей сохраняет прежние значения; пустой tuple заменяет packed set пустым. Если базы нет, прежние owning defaults: пустой набор/absent. Источник publish_settlement_structure |
| PackRegionIndexUpdate | entries: tuple[WildernessRegionEntry, ...] | Полная замена индекса с require_region_index; пустой tuple очищает его. Отсутствие самого update сохраняет базовый индекс. Источник replace_region_index; каждый итоговый region имеет свой metadata provenance |

Таблица задаёт payload обновления, **не полный record с уже принятым provenance binding**. Для изменившейся metadata-проекции требуется свидетельство именно итогового значения после применения к базе. В частности, settlement update с None не является полной сохранённой проекцией и его proof нельзя автоматически принять за proof итоговой settlement row. Незатронутые строки и их proofs сохраняются. Concrete source_proof выполняет другой агент; Pack должен отдельно зафиксировать mapping metadata update → итоговая проекция → provenance без изобретения второго proof-типа.

Payload ref остаётся в PackPartInput, эти metadata updates не дублируют ArtifactRef. Pack связывает payload и metadata по соответствующим адресам и проверяет согласованность. Полный locations index остаётся готовым payload по singleton parts address, а region index — inline metadata; одинаковое слово index не делает их одним POJO.

Не завершены этим срезом: header/grid updates и граница первой сборки без базы; tile climate/status updates и воспроизведение порядка status-пересчётов; окончательный тип UID; provenance binding итоговых metadata-проекций; общий request и concrete типизированные ошибки. Не подменять эти строки универсальным dict/nullable patch или defaults нового класса. После завершения таблицы PackManifestAssembler получает проверенные данные и возвращает полный manifest; отдельная pipeline-ветка по виду update не появляется.

Пользователь подтвердил результат проверки существующих Pack POJO: входные обновления и полное сохранённое состояние имеют разные обязанности. Готового POJO обновлений в просмотренном dataModel/worldPack нет; старые manifest entries не заменяют такой контракт. Это принятие направления и перечисленной семантики, не freeze полного roster новых классов.

Переиспользуются TerritoryVolume, WildernessRegionEntry и require_region_index, PackBakeMode, ClimateBakeStatus, WildernessRefineStatus, SettlementStructureStatus, ChunkRefineRole, owning ограничения WorldGridSettings и policy разрешения map resolution. Их зеркальные типы значений не создаются. WorldPackMetadata содержит world-side path/hash, а не metadata обновлений состава; WorldMapResolutionSettings содержит authored nullable override, а не уже разрешённый effective side.

Для settlement обновлений сохраняется nullable-вход: packed_district_uids — immutable tuple идентификаторов либо None (сохранить); пустой tuple — заменить пустым. Structure_status — существующий SettlementStructureStatus либо None (сохранить). Конкретный тип UID и полная схема нового record сверяются отдельно; текущий список str нельзя автоматически объявить уже мигрировавшим на EntityUid. Полные stored records получают разрешённые значения, а не команды сохранения.

Не вводить общее правило «None означает сохранить»: ChunkRef.refine_role=None является допустимым значением записи; commit_chunk заменяет запись с переданным значением. Каждый тип обновления обязан следовать конкретному writer-методу. SettlementStructureEntry с defaults absent/пустой список не сохраняет различие preserve/replace и потому не годится непосредственно как вход обновления.

Ограничения reuse: TileManifestEntry.chunks, SettlementStructureEntry.packed_district_uids и LocationsIndexWire.locations содержат list; frozen внешней модели не обеспечивает глубокой неизменности. Extra-ignore/coercion старых моделей не доказывают strict admission. TerritoryVolume нормализует порядок bounds; переход не разрешает молча заменить эту семантику отказом. Усиление wire-проверок должно сохранять отдельно принятые правила нормализации и не менять V1 до cutover.

Перед реализацией для каждого входного record указать модуль, поля, отличие ответственности от stored assembly, обработку отсутствующего/пустого/nullable значения, owning defaults при отсутствии базы и типизированные ошибки. Приёмочные пары: settlement None/(), статус None/явный absent, chunk refine_role=None, отсутствие region update/пустой индекс; отдельная проверка глубокой неизменности. Универсальный patch DTO и копирование всех legacy entries не обоснованы. Runtime-код и конкретный source_proof этой записью не меняются.

**Обязательный отдельный завершающий шаг (пользователь, 2026-11-12):** после удаления legacy проверить и очистить комментарии/docstrings, имена классов/методов/переменных/модулей от версий контрактов и переходных обозначений, включая V2, wire 3.0.0 / storage 2. Итог — одна реализация; WorldPackManifestV2 переименовывается в единственный WorldPackManifest без alias после удаления старого класса. Реальные wire/storage поля проходят отдельный аудит назначений и совместимости, не меняются слепой заменой. Полный порядок и приёмка — раздел основного плана «Обязательный отдельный шаг после удаления legacy». Этот шаг не является частью отложенного удаления codec_version/payload_format и не считается выполненным сохранением этих полей.

Локально Pack может разработать адреса, metadata projection, errors, binding registry, budgets и проверки уже конкретных типов. Нельзя создавать пустые wrappers, неподключённые stores или placeholders ради отметки реализации. Полный manifest и read result требуют завершённой persisted provenance schema. Сквозной prepare дополнительно требует реального producer output/coverage/adoption; synthetic fixtures закрывают только локальные инварианты Pack.

Проверки: duplicate/missing/foreign address; точное соответствие artifact format и роли; unknown nested fields; metadata/proof mismatch; same operation id different body; правильный READY live-set; refine A сохраняет B/proof; budget до reservation/parse; pinned A читается после activate B; absent отличается от missing blob/hold; wrong T/registry version; lost activation response replay без нового CAS; all values доступны после guard close; infrastructure/cancel не маскируются доменным outcome.

**Оставшиеся Pack-owned решения:** конечная схема адресов/assembly, closure roster всех parts, concrete activation/release binding, config CRUD disposition. Wire/storage pair и исключение registry_hash/location z_band/wilderness_tiles_total приняты в §6.3 и больше не требуют выбора. **Внешние входы:** concrete persisted source proof, producer coverage/outcome evidence, atomic adoption и retained candidate lifecycle. Миграция чужих callers не блокирует поставку собственного Pack API; отсутствующий тип его поля нельзя скрыть этим разделением.

**Итог приёмки:** ответственность Pack и существующие/целевые границы перечислены по конкретным файлам и типам ТЗ. Полный архитектурный gate пока не закрыт перечисленными OPEN-решениями. Ни source CRUD, ни новая pregame операция не назначены Pack. Runtime-код и SQL в рамках этой конкретизации не изменены.
