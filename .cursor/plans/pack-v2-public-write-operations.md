# Pack V2 — публичные операции изменения состава

Дата: 2026-11-12. Основание: пользователь поручил конкретизировать открытые контракты операций вместо скрытого исполнения списка обновлений внутри prepare/assembler. Область: только Pack. Статус: PROJECT, требуется архитектурная приёмка; runtime, SQL и DAG-ноды не изменяются. Связь: [основной план](world-pack-v2-single-manifest-contract.md), [контракт домена](pack-v2-domain-contract-spec.md), [ТЗ](../../docs/tz_world_pack_storage.md).

## Принятая граница и выбранный проект реализации

Для последовательности самостоятельных изменений выбран вариант отдельных публичных методов concrete класса `PackPreparationService` в `application/worldData/pack/preparation/packPreparationService.py`. Это публичные доменные операции, не универсальный execute(kind), callback dispatcher или новый orchestration pipeline. Имена и сигнатуры ниже — предложения для приёмки, не существующая реализация.

DAG вызывает конкретный метод с его typed Input и передаёт возвращённое состояние следующему вызову. Метод не вызывает другие публичные операции. Он применяет только своё изменение с обязательными локальными последствиями старого writer. `commit_chunk` с provisional пересчётом статуса — одна операция, поскольку пересчёт является её прежним инвариантом; финальный пересчёт с expected открыт отдельно, как старый recalc_wilderness_status.

`PackManifestAssembler` больше не принимает очередь изменений: он строит полный manifest из конечного проверенного состояния. `PackPreparationOperation` выполняет только завершающую проверку/staging/seal/READY. Он не исполняет операции таблицы ниже. Публичный prepare остаётся завершением подготовки; его прежний DTO требует изменения. Activate остаётся самостоятельным вызовом DAG после candidate.

## Передача состояния — проект без нового хранилища

### Конкретизация start/state после сверки existing Pack contracts

Статическая сверка 2026-11-12: ManifestPinRead содержит pin identity и max_bytes; VerifiedManifestBytes — только ref/payload, без доказательства актуального pin при повторном использовании. WorldPublicationRef уже содержит world_uid и nullable pack_hash. Поэтому отдельное world_uid в state не требуется, а объект VerifiedManifestBytes от caller сам по себе не заменяет pinned admission.

Вместо первоначального общего start предлагаются **два отдельных метода** PackPreparationService; выбор делает DAG, сервис не выбирает следующий публичный маршрут по наличию базы:

| Метод | Concrete input, `dataModel/worldPack/preparation/start.py` | Результат / эффекты / отказ |
|---|---|---|
| `start_empty(self, request: PackPreparationEmptyInput) -> PackPreparationState` | `base_publication: WorldPublicationRef`, `initial_assembly: PackAssemblyInput`, `initial_provenance: tuple[PackStoredAssemblyProvenance, ...]` | Pure. Требует base_publication.pack_hash=None; создаёт пустой parts и начальную metadata из явных значений. Начальные коллекции assembly пусты; header задаётся по прежним owning правилам без новых defaults. Если publication уже содержит Pack — BASE_PUBLICATION_MISMATCH, без автоматического перехода в другой метод |
| `async start_from_base(self, request: PackPreparationBaseInput) -> PackPreparationState \| ManifestReadRefusal` | `pin: PackPinnedReadIdentity`, `max_manifest_bytes: strict positive int` | Только verified bounded pinned read через внутренний Pack binding. Требует pin.publication.pack_hash не None; проверяет соответствие точных manifest bytes/ref, world, schema и pin. Копирует состав/provenance базы без latest lookup. Нет Pack в publication — BASE_PUBLICATION_MISMATCH, не fallback на start_empty |

PackPinnedReadIdentity — существующий проект Pack read-контракта из ТЗ, не новый набор скопированных store/execution/invocation полей. Его extraction/mapping с existing ManifestPinRead всё ещё требует приёмки. Типы initial assembly/provenance общие с остальным Pack проектом. Новая версия не получает готовность только из наличия такого input: source proof и header initialization остаются соответствующими gates.

**Уточнённые поля PackPreparationState:** `base_publication: WorldPublicationRef`, `parts: tuple[PackStoredPart, ...]`, `assembly: PackAssemblyInput`, `assembly_provenance: tuple[PackStoredAssemblyProvenance, ...]`. world_uid берётся из base_publication; не повторяется отдельным полем. Состав metadata/parts переиспользует общие типы stored manifest, но полный request state имеет иную ответственность: содержит base expectation и допускает незавершённую межчастную сборку. Не выдавать его как WorldPackManifestV2 и не ослаблять валидаторы готового manifest ради промежуточного состояния. Codec_version/payload_format принадлежат manifest binding, а не этому публичному state.

Каждый write Input содержит обязательный `state: PackPreparationState` и только описанные поля своей операции. Return — новое состояние с неизменным base_publication. Значение request.state валидируется повторно; ошибки не меняют исходный объект. Две записи одного адреса являются двумя вызовами с передачей результата, не двумя entries одного списка. Operation ID/fingerprint финального prepare не назначают новые revisions и не являются версией mutable session.

Все промежуточные значения обязаны оставаться обычными материализованными POJO без lazy readers. Состояние не хранит pin как capability, не продлевает его и не обещает сохранность artifacts. При finish нужен действующий принятый retention/adoption binding; после закрытия pin нельзя повторить storage read по старому удостоверению. Отдельный state holder или новый storage этим уточнением не вводится.

Проверки: start_empty отклоняет непустую Pack-базу; start_from_base отклоняет отсутствие Pack, closed/foreign pin и несовпадение publication/ref; начало от A после активации B читает закреплённую A; в state один world source; write сохраняет base expectation; S0 не меняется при успехе или отказе; start не открывает staging и не запускает prepare/activate.

Начальная assembly из explicit данных сохраняет принятое требование без скрытого resolver. Это ещё не доказательство паритета V1 defaults: нужно завершить таблицу начального header и семантику первой операции. Конкретные false/empty значения не придумываются по именам полей.

Предлагаемый `dataModel/worldPack/preparation/state.py::PackPreparationState` имеет уточнённые выше поля base_publication, parts, assembly, assembly_provenance. Base_publication использует существующий WorldPublicationRef; parts — tuple существующих проектных PackStoredPart; assembly и provenance используют общие Pack-owned metadata records. Поля состава должны иметь единственную декларацию, общую с manifest: копия дерева моделей и validators не допускается. Способ общего объявления — gate реализации после проверки POJO. Source proof не определяется этим документом, его разрабатывает другой агент.

State — глубоко immutable значение промежуточной подготовки. Оно не является опубликованной версией, manifest ArtifactRef, receipt удержания или новым сохраняемым contents object. Допускаются промежуточные состояния, ещё не прошедшие полную межчастную проверку; окончательные полнота/coverage/ref/proof проверки обязательны в prepare. Это не разрешает выдавать повреждённые вложенные POJO или игнорировать локальные инварианты операции.

У публичных входов нет writer/backend/CommitScope/lease/callback. Передача S0 → S1 → S2 через DAG сохраняет причинный порядок. Внутренний scope/adoption final prepare остаётся отдельным незакрытым binding. Существование state не доказывает удержание его refs. Отдельные session store, mutable singleton draft, журнал команд и новый OperationKind не вводятся.

Операции изменения состояния pure относительно внешних эффектов; base получает отдельный read/start контракт. Они не пишут blobs или active head. Сериализация/размер промежуточного state, restart и срок удержания входных refs должны быть проверены до реализации; при доказанном превышении transport budget решение пересматривается отдельно, не скрывается неутверждённым state store.

## Публичные методы и точные обязанности

Все методы ниже принадлежат PackPreparationService. Входы размещаются в `dataModel/worldPack/preparation/operations.py`; fields state/address/part используют общие типы, не повторяют их содержимое. Результат операций изменения — PackPreparationState из state.py. Они выбрасывают PackPreparationFailure с PackPreparationError из существующего проекта preparation/errors; infrastructure errors сохраняют owning тип. Передача failure через DAG не разрешает retry внутри метода.

| Сигнатура метода | Поля Input сверх state | Источник поведения / локальный результат |
|---|---|---|
| `sync_grid_metadata(self, request: PackGridMetadataInput) -> PackPreparationState` | captured fine_cells_per_map_cell и world_map_cells_per_tile, metadata provenance; окончательная схема header binding OPEN | Pack-owned эффект sync_world_metadata до записи L0 tiles. Не меняет last_l0_mode, не читает World, не выбирает resolver. Codec-поля остаются внутренним binding |
| `set_last_l0_mode(self, request: PackLastL0ModeInput) -> PackPreparationState` | mode: PackBakeMode; metadata provenance | Присваивание bake_mode в WorldMapBakeOrchestrator после цикла L0 tiles, включая пустой цикл. Не запускает bake и не обновляет сетку |
| `write_map_tile(self, request: PackMapTileInput) -> PackPreparationState` | part: PackPartInput ограниченный map_tile; effective side | write_world_map_tile: заменить только адресованную часть, сохранить chunks/climate тайла; side соответствует payload. Обновление parent-light cache не переносится в pure операцию |
| `write_wilderness_chunk(self, request: PackWildernessChunkInput) -> PackPreparationState` | part: PackPartInput ограниченный wilderness_chunk; refine_role: ChunkRefineRole либо None; metadata provenance | write_wilderness_chunk → commit_chunk: заменить chunk по адресу, затем provisional status по existing policy без expected. None роли записывается как значение |
| `write_location_terrain(self, request: PackLocationTerrainInput) -> PackPreparationState` | part: PackPartInput ограниченный location_terrain; territory_volume: TerritoryVolume; metadata provenance | write_location_terrain: заменить запись одной локации; прежний coarse default новой metadata row сохраняется |
| `write_settlement_structure(self, request: PackSettlementStructureInput) -> PackPreparationState` | part: PackPartInput ограниченный settlement; territory_volume; packed_district_uids: tuple UID либо None; structure_status: SettlementStructureStatus либо None; metadata provenance | publish_settlement_structure: None сохраняет прежнее поле, явно пустой packed set очищает. Без базы owning defaults. Здесь нет tmp rename/SQL/публикации head |
| `write_coarse_climate(self, request: PackCoarseClimateInput) -> PackPreparationState` | part: PackPartInput ограниченный climate_coarse | write_climate_coarse: заменить singleton, не сбрасывать fine статусы тайлов |
| `write_fine_climate(self, request: PackFineClimateInput) -> PackPreparationState` | part: PackPartInput ограниченный climate_fine; metadata provenance | write_climate_tile: заменить адресованную часть и установить fine у данного тайла; прочие поля сохранить |
| `replace_locations_index(self, request: PackLocationsIndexInput) -> PackPreparationState` | part: PackPartInput ограниченный locations_index | write_locations_index: полная замена payload индекса. Пустой индекс — реальный готовый payload, не отсутствие ref |
| `replace_region_index(self, request: PackRegionIndexInput) -> PackPreparationState` | entries: tuple[WildernessRegionEntry, ...]; provenance для итоговых строк | replace_region_index: валидировать весь индекс existing require_region_index, заменить целиком; пустой tuple очищает |
| `write_tile_grade_slots(self, request: PackTileGradeSlotsInput) -> PackPreparationState` | part: PackPartInput ограниченный tile_grade_slots | Принять полный готовый результат существующего incoming-first merge. Не выполнять merge, не запускать grade producer |
| `write_location_grade_slots(self, request: PackLocationGradeSlotsInput) -> PackPreparationState` | part: PackPartInput ограниченный location_grade_slots | То же для location address. Пустой incoming у producer сохраняет прежние slots; Pack получает уже полный результат |
| `recalculate_wilderness_status(self, request: PackWildernessStatusInput) -> PackPreparationState` | address: PackTileMetadataAddress; expected_chunks: strict int либо None; metadata provenance | recalc_wilderness_status: None явно запускает provisional пересчёт, int — existing count policy. Отсутствие вызова сохраняет статус. Bounds должны соответствовать старой policy, новый произвольный запрет negative/zero не вводить |

Restriction part.kind является конкретной типизированной границей каждого Input; передача несовместимого адреса — ошибка до изменения. Как выразить ограничения без зеркальных PackPartInput, необходимо решить при POJO-приёмке. Таблица не разрешает Any/dict/строковые универсальные kinds. TerritoryVolume и status/role values переиспользуются. UID остаётся отдельной проверкой соответствия existing str и proposed EntityUid.

В таблице metadata provenance означает существующий проект PackStoredProvenance и привязку к точной итоговой metadata projection. Окончательные поля этих bindings пока OPEN: proof входного partial update не заменяет proof результата после наследования. Это конкретная незавершённость сигнатур Input, а не разрешение новому proof-классу.

## Начало, завершение и оставшиеся методы writer

### Начальный header: подтверждённые источники и предел паритета

| Поле | V1 источник при пустой базе | Последующее изменение / целевая граница |
|---|---|---|
| last_l0_mode | WorldPackManifest.bake_mode default light, existing PACK_BAKE_LIGHT | L0 caller меняет после записи tiles, detailed не меняет. Start и L0 completion нельзя считать одним событием без проверки порядка |
| fine_cells_per_map_cell | FINE_CELLS_PER_MAP_CELL_DEFAULT из wire/mapCellSize.py | sync_world_metadata передаёт значение World; в целевом входе captured effective значение, constraint WorldGridSettings |
| world_map_cells_per_tile | WORLD_MAP_CELLS_PER_TILE из wire/worldMapCellsPerTile.py | sync_world_metadata берёт cells_per_side, затем non-null authored override; write_world_map_tile ставит фактический side. Для нулевого числа tiles последней записи нет. Resolver остаётся владельцем effective side; не скрывать возможное различие raw override и resolved side |
| fine_cell_size | FINE_CELL_SIZE из core/constants.py | В проверенных Pack writers последующего setter нет; единица fine-grid, не свободный масштаб |
| map_subsurface_depth | WorldPackManifest default 0 | В проверенных Pack writers setter не найден. Effective captured depth в целевом header — уже требование проекта, но его V1 mapping нельзя объявить доказанным |
| terrain_chunk_columns | В legacy manifest поля нет | В Pack-плане §6.6 уже принято обязательное captured поле и owning constraints. Не придумывать default для start и не выводить значение из случайного первого chunk |
| codec_version / payload_format | PACK_CODEC_VERSION и manifest default json | sync_world_metadata обновляет codec_version из PackBakeDefaults и payload_format; поля сохраняются в manifest. Целевой источник — Pack binding, не публичные параметры DAG |

Для start_empty initial_assembly содержит явные значения с owning происхождением, не автоматически заполненную копию legacy manifest. Дефолты таблицы — evidence старого поведения, не разрешение новых literal defaults. Таблица не закрывает initial provenance и depth/chunk-grid mapping. При start_from_base значения копируются из pinned версии, не из текущих defaults.

**Коррекция после сверки owning ТЗ (§ «Поля, которые формирует Pack»):** прежнее предложение включить codec_version/payload_format в публичные state/start inputs отозвано как противоречащее ТЗ. Поля сохраняются в manifest и определяются зарегистрированным Pack binding; DAG не выбирает codec. Wire 3.0.0/storage 2 также определены принятой парой формата. Совместимость binding с pinned базой и replay должна быть доказана отдельно; отсутствие codec полей в public input не разрешает молча переинтерпретировать старые bytes. Это исправление ошибочного предложения, не новое изменение принятой логики.

### Конкретная оболочка завершения подготовки — проект

#### Coverage: существующие типы, передача и финальная проверка

Статическая сверка Pack 2026-11-12. Owning ТЗ уже предлагает `preparation/coverage.py::PackWildernessCoverage(expected, completed, proof)` и `PackSettlementCoverage(location_uid, expected_districts, packed_districts, proof)`. Completed использует PackChunkCoverageEntry и варианты PackChunkMaterialized(outputs)/PackChunkWithoutPayload. Повторная иерархия типов не требуется. Existing PackCompletenessSnapshot — progress/read projection с counts и ограниченными missing lists, а не полное evidence; использовать его вместо coverage нельзя.

**Предложение места данных до подтверждения producer mapping:** дополнить PackPreparationBody полями `wilderness_coverage: tuple[PackWildernessCoverage, ...]` и `settlement_coverage: tuple[PackSettlementCoverage, ...]`. Это не утверждённые новые поля: ТЗ требует сначала предъявить concrete producer output и mapping. Типы proof, L0 coverage/policy evidence и правила нескольких результатов одной области остаются OPEN. Пока эта сверка не выполнена, оболочка body ниже не объявляется полной реализационной схемой. Не заменять пробел `tuple[Any, ...]`, optional пустым значением или новым generic coverage wrapper.

| Гарантия | Доступная Pack-форма / требуемая передача | Проверка в финальном prepare |
|---|---|---|
| Wilderness expected и обработанные области | Existing проект PackWildernessCoverage из готовых результатов через DAG | Уникальные expected/completed, completed ⊆ expected, grid/scope соответствуют закреплённым значениям. Expected не восстанавливать из completed |
| Несколько областей → одна location terrain часть | PackChunkMaterialized.outputs содержит адреса частей | Каждый output существует в итоговом state и подтверждён evidence именно его ref/provenance. Не требовать one chunk = one artifact |
| Without payload | PackChunkWithoutPayload с подтверждением producer | Не создавать фиктивный ref, не удалять базовый chunk, не объявлять wilderness status complete только по completed coverage |
| Settlement census/packed | Existing проект PackSettlementCoverage | Уникальные UID, packed ⊆ census, соответствие итоговой structure metadata и payload. None update сохраняет прежние поля по writer; coverage не отменяет preserve-семантику |
| L0 | PackL0PreparationScope.expected_tiles уже существует в проекте, ready parts находятся в state | Набор адресов должен быть связан с готовыми результатами данной подготовки; наличие inherited map_tile само по себе не доказывает повторный bake. Отдельный concrete outcome/proof mapping ещё OPEN; новый второй expected_tiles не вводить |
| Fine climate по policy | Адрес fine части и captured policy/coverage результата | Не требовать fine для каждого L0 tile без такой policy; без готового evidence не разрешать новые адреса по догадке |

Coverage в body относится к проверяемым результатам подготовки; оно не является очередью операций и не запускает materialization. DAG передаёт данные, не строит expected геометрию или census. Какие готовые результаты принадлежат одному финальному prepare, задаёт согласованный маршрут; Pack не выбирает их по времени завершения worker.

**Повторные записи:** если A последовательно заменён результатами R1 и R2, конечный state содержит R2/ref/provenance. Один совпавший logical address в evidence R1 не доказывает соответствие R2. Финальный валидатор обязан проверить связь coverage с итоговыми refs/provenance; прежнее evidence нельзя молча перепривязать к новым bytes. При этом нельзя требовать, чтобы каждый перезаписанный промежуточный payload оставался в manifest: это изменило бы last-write семантику. Правила передачи/разделения coverage нескольких таких результатов нужно предъявить в конкретном binding; полный журнал команд или новый receipt store не вводятся автоматически.

Fingerprint включает оба coverage поля и их proofs после принятия их concrete mapping. Отсутствие требуемого evidence — отказ, пустой tuple не означает «проверку пропустить». Пустой scope допустим только с доказанной прежней семантикой отсутствия работы, не для сокрытия изменений. Для неподдерживаемого сочетания ещё не принятых контрактов не писать runtime обход.

Приёмочные проверки: равные counts при разных адресах; without_payload при сохранённой базе; один output для нескольких областей; R1 evidence с R2 bytes; missing evidence при изменённой части; inherited часть без новой materialization сохраняет прежнее proof; отказ не выдаёт READY. Coverage и видимый wilderness status проверяются раздельно по принятой старой policy.

Переиспользуются `dataModel/worldPack/preparation/input.py` и существующие проектные имена; второй FinishPackInput не вводится:

- `PackPreparationInput(operation_id: EntityUid, preparation_fingerprint: RevisionHex, body: PackPreparationBody)`.
- `PackPreparationBody(state: PackPreparationState, capture: <concrete owning capture>, scope: PackPreparationScope)`.

State единожды содержит base_publication, parts, assembly, assembly_provenance. World берётся из state.base_publication. Верхний body не дублирует их отдельными полями. Capture остаётся внешним типом другого агента, его форма здесь не определяется. Scope переиспользуется из owning проекта ТЗ; он не является командой запустить другие операции. Codec_version/payload_format формирует внутренний Pack binding.

Эта форма ещё не закрывает полноту coverage evidence: если owning scope/proof не содержит нужные expected/completed результаты, необходимо предъявить конкретное поле с owning типом до freeze. Нельзя потерять эти сведения при переходе от прежнего input или восстановить их из counters. Привязки покрытия остаются явно OPEN, а не Any/dict.

Fingerprint вычисляется existing canonical encoding по полному body: state (включая pinned base), capture, scope и всем добавленным при freeze semantic evidence. Operation_id и заявленный preparation_fingerprint не входят в собственный digest. Pin transport identity и последовательность уже выполненных write-вызовов не объявляются новым журналом; все значимые результаты/provenance должны присутствовать в body. Нормализация уникальных множеств происходит после проверки дублей. Same operation_id + другой body — конфликт; тот же body — existing lifecycle replay после admission. Привязка schema/binding к fingerprint/replay требует проверки принятого encoding/lifecycle контракта, не добавления скрытых публичных codec-настроек.

Один вызов PackPreparationPipelineOpenPipeline.prepare делегирует PackPreparationOperation.prepare. Внутри разрешены локальная полная валидация конечного state относительно базы/scope, проверка inherited proofs, сборка manifest, canonical encoding/budget и принятый storage lifecycle до READY. Ни одного write_* вызова, source capture или activate внутри. Unknown/closed lifecycle, инфраструктурные ошибки и cancellation сохраняют принятые исходы; invalid state не выдаёт candidate.

Переиспользование finish_pack_preparation ограничено его доказанной обязанностью: stage encoded bytes, сверка ref.nbytes/content_hash, finish_preparation и точная проверка READY record/live-set. Текущий helper не выполняет full state/coverage/source admission и не становится публичным prepare простым переименованием. Переход его other_members/spatial/climate набора на полный authoritative closure остаётся Pack-owned работой.

Приёмка дополнения: финальный manifest сохраняет codec_version/payload_format согласно binding; публичный input не содержит выбор codec; разные command sequences с одинаковым полным semantic body не требуют нового журнала; потеря coverage evidence блокирует freeze; state без source/metadata proofs не превращается в READY; prepare не запускает другую публичную операцию.

| V1 точка | Disposition |
|---|---|
| __init__ с legacy_head | Отдельные start_empty и start_from_base по таблице выше; DAG выбирает вызов, Pack не исполняет fallback. Initial header/defaults и concrete pinned binding требуют приёмки |
| manifest property | Immutable state возвращается методом; mutable доступ к manifest убирается |
| sync_world_metadata и последующее присваивание bake_mode | Два публичных вызова: sync_grid_metadata до L0 tile writes, set_last_l0_mode после них. Объединённый set_l0_metadata отозван: он не сохранял старый порядок. Concrete DAG bindings ещё требуют согласования |
| commit_chunk | Внутренняя реализация write_wilderness_chunk; дополнительный публичный обход без payload не вводится |
| recalc_manifest_counters | Внутренний pure расчёт по конечному составу перед assembler/final prepare, не самостоятельная DAG-стадия. Промежуточные counters в state не вводятся |
| save_manifest | Завершение prepare → PreparedPackCandidate; публикация отдельно через activate. Не возвращать successful public version до READY |
| encode_settlement_structure_tmp / publish rename / load_settlement_structure_tmp / settlement_structure_tmp_path | Legacy файловый механизм; не копировать в публичный Pack input. Готовый typed ref поступает на write_settlement_structure. Lifecycle замена/retention требует существующих owning bindings, не решается pure state |
| has_published_settlement | Чтение pinned версии через публичный read_part и его typed absent/refusal, без live filesystem exists как источника истины; mapping caller ещё проверяется |
| paths / _atomic_write / pack_storage_path | Внутренняя storage-инфраструктура, не публичные самостоятельные операции DAG |
| _upsert_tile / _replace_tile | Pure helpers соответствующих операций, не открытые методы |
| parent_light_cache / bake_defaults | Не содержимое state и не публичные runtime capabilities; нужные effective данные передаются типизированно |
| Spatial root | В V1 writer самостоятельного метода нет. Не придумывать его поведение по аналогии; concrete Pack registration/update для spatial остаётся OPEN |

Завершающий `PackPreparationPipelineOpenPipeline.prepare(request: PackPreparationInput) -> PreparedPackCandidate` принимает конечный state и identity/fingerprint/capture/scope по уточнённой схеме; не список команд. Этот документ не объявляет окончательные поля данного Input. Нужны согласование fingerprint конечного содержания, admission refs, candidate replay и release; existing candidate/activation POJO переиспользуются.

## Повторные адреса и порядок

В каждом state и окончательном manifest ровно одна запись на logical address. Последовательные DAG-вызовы write_* могут заменять этот адрес: S1 = write_A(S0), S2 = write_A(S1). Последний **в согласованном порядке вызовов**, не завершившийся последним worker, определяет результат. Это правило не разрешает duplicate address в одном unordered payload.

Два параллельных результата S1/S2, построенных из S0, не сливаются автоматически и не выбираются сервисом по времени. До совместного согласования DAG зависимостей запрещено считать такой fork эквивалентным последовательности. Порядок самостоятельных операций задаётся DAG; domain loop по списку разнотипных updates удаляется из проекта. Existing full L0 → topology и detailed L2 → settlement materialize не переставляются. Новые NodeId/deps не утверждены.

Grade merge и settlement preserve сохраняют собственные правила, общий last-wins к их внутренним полям не применяется. Статус сохранённых chunks и coverage выполнения — разные значения. Final expected-пересчёт вызывается DAG после соответствующих chunk updates, как в прежнем detailed caller; он не вызывается Pack по выбору режима запроса.

## Классы, ошибки и приёмка

### Mapping отказов Pack по этапам

#### Состав диагностик и проверка отсутствия дублей

Сверка 2026-11-12: общие структурные records уже существуют. Новые PackInputTypeError/PackExtraFieldError/PackMissingFieldError не предлагаются без доказанного пробела; их семантика пересеклась бы с существующими ошибками schema admission.

| Тип / модуль dataModel | Поля и текущая ответственность | Использование в Pack / граница |
|---|---|---|
| JsonFieldError, validation/importIssues/jsonFieldError.py | code: JsonValidationCode; path: ValidatedFieldPath; message; location: WireLocation; wire_path: tuple[WirePart, ...]; schema_id; pydantic_type | Existing структурная диагностика известного POJO/поля на границе декодирования. Canonical path и фактический wire_path не смешиваются. Для SCHEMA_VIOLATION обязателен pydantic_type |
| WireShapeIssue, validation/importIssues/wireShapeIssue.py | code: JsonValidationCode; location: WireLocation; message; pydantic_type | Existing структурная диагностика, когда нет объявленного поля/POJO. Не создавать фиктивный FieldRef неизвестного extra key |
| PackPreparationIssue, worldPack/preparation/errors.py (проект ТЗ) | FieldPathError[PackPreparationIssueCode]: code, path, message | Pack-owned смысловое нарушение входа/связей: address, descriptor, scope, provenance, coverage. Не дублировать schema type/extra/missing ошибки кодами этой модели |
| PackPreparationError, worldPack/preparation/errors.py (проект ТЗ) | reason: PackPreparationFailureReason; непустой issues | Итог отказа конкретного этапа; reason различает INVALID_INPUT/DEPENDENCY_MISMATCH/IDENTITY_CONFLICT и lifecycle/admission причины. Не исполняет recovery и не означает terminal REJECTED |
| ManifestReadRefusal, worldPack/read/pinnedManifest.py (existing) | pin_id, ref либо None, reason: ManifestReadReason | Самостоятельный результат pinned read; возвращается из start_from_base, не оборачивается зеркальной Pack pin-ошибкой |

**Предлагаемое уточнение ошибки подготовки для обсуждения contract freeze:** `PackPreparationError.issues` допускает tuple из existing JsonFieldError, WireShapeIssue и проектного PackPreparationIssue; в фазе INVALID_INPUT — структурные records, в фазах Pack semantics — PackPreparationIssue. Это предложение расширения прежнего tuple[PackPreparationIssue], не молчаливое изменение owning ТЗ. Статическая проверка существующего schema adapter приведена ниже; она не означает приёмку расширения публичной ошибки.

**Проверка адаптера структурных ошибок (2026-11-12).** В `application/jsonValidation/resolution/wireIssues.py` уже существует `pydantic_issues(ctx, root, exc, raw=...)`: он переводит ValidationError в диагностические records, не вызывает resolve, reporting или другую операцию домена. `ResolveContext` поддерживает `RUNTIME` и корневой `WireLocation(parts=())`; фиктивный import document не нужен. Для Pack корнем является фактический input конкретного публичного метода, `root` — его POJO-класс, `raw` — фактически проверяемое значение, `schema_id` — только объявленный идентификатор модели либо None. Имя операции не добавляется как выдуманное поле wire-пути.

| Ошибка структуры | Результат существующего переводчика |
|---|---|
| Путь разрешается в объявленное поле input | JsonFieldError с CheckedPath и wire_path относительно input |
| Путь не разрешается в поле, включая лишний ключ | WireShapeIssue с фактическим расположением в input |
| Ошибка корня без пути поля | WireShapeIssue с корневой location; пустой FieldPath не конструируется |
| Неизвестное enum-значение | UNKNOWN_ENUM; не дублировать новым Pack-кодом для той же причины |
| Стандартная ошибка Pydantic | SCHEMA_VIOLATION с конкретным pydantic_type |

Ограничение reuse: аннотация результата переводчика — широкий `list[ImportIssue]`, хотя показанные ветви создают JsonFieldError/WireShapeIssue. Нельзя переносить `ImportIssue = FieldPathError[Any] | WireShapeIssue` в публичный Pack-контракт и тем самым принимать произвольные доменные ошибки. При реализации нужен проверяемый переход к закрытому union; одного cast недостаточно. Вызов полного `resolve_model` ради перевода ошибок не предлагается: его нормализация, reporting и политика unresolved не являются ответственностью Pack admission. Допустимость зависимости на этот внутренний helper должна быть зафиксирована при freeze; наличие функции не делает её публичным междоменным контрактом.

Статически подтверждено отсутствие необходимости в новых PackInputTypeError/PackExtraFieldError и фиктивном import-контексте. До приёмки остаются: закрытый тип результата на границе, проверка путей на конкретных Pack POJO (включая nested union и повторную валидацию экземпляров), согласование расширения PackPreparationError. Runtime-проверки адаптера в рамках этого уточнения не выполнялись. Семантические Pack errors этот переводчик не заменяет.

Field/logic разделение по ответственности: структурная ошибка сообщает нарушение объявления значения; PackPreparationIssue сообщает доменное нарушение с привязкой к конкретному полю/адресу; PackPreparationError.reason классифицирует отказ операции/этапа; read refusal относится к отдельному read-контракту. Отдельный новый PackLogicError с теми же reason/code/path не вводится только ради названия. Это не завершённая приёмка logic errors: expected/actual identity и operation context нужно сопоставить с owning контрактами перед freeze, не разносить одно нарушение по двум независимым records.

Предлагаемое правило API: публичные методы принимают named typed Input; transport decoder использует собственную schema admission и не передаёт raw dict в Pack. Pack повторно проверяет переданный instance для обходов model_construct/model_copy. Representation структурного отказа этой повторной проверки должна совпасть с принятой schema diagnostics, а не выдавать наружу строковый ValueError. Программная ошибка конструктора diagnostic (IssueAdmissionError) не превращается в пользовательский Pack отказ.

Проверка агрегации: ValidatorAggregationHelper допускает конкретные классы явно; одно нарушение не выдаётся одновременно как JsonFieldError и PackPreparationIssue. Неизвестный ключ не получает вымышленный validated path; invalid parent исключает зависимые semantic проверки, независимые поля продолжают проверяться. Итоговая фабрика строит один PackPreparationError и PackPreparationFailure после завершения этапа. Нужны тесты типовой ошибки, extra key, missing field, двух независимых ошибок, semantic mismatch и forged instance; они пока не запускались.

Результат этого среза: roster и назначение error POJO описаны, потенциальные дубли исключены из предложения; существующий schema adapter и runtime root location проверены статически. OPEN остаются проверка путей на конкретных Pack POJO, union admission, согласование зависимости и полный typed logic context. Source proof и чужие domain error types здесь не переопределяются.

Проверены existing `worldPack/read/pinnedManifest.py::ManifestReadRefusal`, `validation/diagnostics/fieldPathError.py::FieldPathError` и ValidatorAggregationHelper. PackPreparationError/Issue/Failure остаются проектом ТЗ; реализации в просмотренных Pack модулях не найдены. Новый универсальный error carrier не вводится.

| Где / условие | Reason / issue code из проекта ТЗ | Поле диагностики и эффект |
|---|---|---|
| start_empty при непустой Pack-базе | DEPENDENCY_MISMATCH / BASE_PUBLICATION_MISMATCH | base_publication; state не создаётся, fallback отсутствует |
| start_from_base при отсутствии Pack в указанной publication | DEPENDENCY_MISMATCH / BASE_PUBLICATION_MISMATCH | pin.publication; storage read не запускается |
| write_* с неподходящим видом/координатами адреса | DEPENDENCY_MISMATCH / ADDRESS_MISMATCH | part.address; исходный state неизменен |
| write_* с неподходящим format/version descriptor | DEPENDENCY_MISMATCH / FORMAT_MISMATCH | part.artifact; это descriptor admission, не доказательство валидности bytes/seal |
| Несогласованный proof результата или metadata | DEPENDENCY_MISMATCH / SOURCE_PROOF_MISMATCH | конкретный provenance input; новое состояние не выдаётся |
| Отсутствует требуемый metadata proof | DEPENDENCY_MISMATCH / METADATA_PROOF_MISSING | соответствующая metadata projection; не синтезировать proof |
| Duplicate addresses в одном состоянии/индексе | DEPENDENCY_MISMATCH / DUPLICATE_ADDRESS | исходные индексы коллекции; не сортировать/дедуплицировать перед диагностикой. Последовательная замена адреса отдельными вызовами ошибкой не является |
| Финальный scope нарушен | DEPENDENCY_MISMATCH / OUT_OF_SCOPE_CHANGE | body.state и конкретный изменённый адрес; без READY. Согласованность scope проверяется конечным prepare, pure write не получает тайно scope извне |
| Нет обязательной итоговой части | DEPENDENCY_MISMATCH / MISSING_PART | соответствующий адрес/coverage; inherited часть не удаляется для устранения ошибки |
| Статус противоречит существующей policy | DEPENDENCY_MISMATCH / STATUS_MISMATCH | конкретное status поле; полное coverage само по себе не заменяет старую policy |
| Same operation ID с другим body | IDENTITY_CONFLICT / IDENTITY_MISMATCH | identity/fingerprint запроса; lifecycle выполняет принятый replay/conflict, write-методы в replay не запускаются |
| Manifest превышает budget | MANIFEST_OVERSIZE / MANIFEST_LIMIT_EXCEEDED | конечный manifest admission; без staging/READY на этапе предварительного byte-budget контроля |

Неверный тип поля, extra key и прочие структурные ошибки относятся к INVALID_INPUT; конкретный field-code mapping полного DTO ещё не принят. Нельзя выдать ADDRESS_MISMATCH за все ошибки Pydantic либо объявить field/logic POJO acceptance выполненной этой таблицей. Отдельные logic errors и их отсутствие пересечений с существующими error types остаются gate по правилам проекта.

#### Семантические отказы replace_region_index (уточнение проекта)

Источник поведения: `dataModel/worldPack/meta/wildernessRegionEntry.py`, validators `ordered`, `parent_contract` и `require_region_index`; caller `application/worldData/pack/io/wildernessRegionIndexWriter.py`. Сохраняются все существующие условия допуска. Новые ограничения глубины, геометрического включения bbox, совпадения типов parent/child или сортировки входа не добавляются.

| Условие | Диагностика / путь относительно PackRegionIndexInput |
|---|---|
| Повтор region_uid в полном входном индексе | DEPENDENCY_MISMATCH / DUPLICATE_ADDRESS, `entries[i].region_uid` для каждого повторного вхождения после первого; сообщение указывает первый индекс |
| Родитель отсутствует среди entries | DEPENDENCY_MISMATCH / предлагаемый REGION_PARENT_MISMATCH, `entries[i].parent_region_uid`; сообщение указывает отсутствующий UID |
| Родитель найден, но его status = SUBLOCATION | DEPENDENCY_MISMATCH / предлагаемый REGION_PARENT_MISMATCH, `entries[i].parent_region_uid`; сообщение указывает родителя и недопустимый status |
| SUBLOCATION без distinct parent, parent у другого status, неупорядоченный bbox | Уже отвергаются validators вложенного WildernessRegionEntry/RegionIndexBounds. Передать диагностику model validation через согласованный schema adapter; не выдавать второй Pack issue за то же нарушение |

`REGION_PARENT_MISMATCH` — предложение добавить один код в существующий PackPreparationIssueCode, а не новый error POJO. В перечне ТЗ такого кода пока нет. MISSING_PART не подходит: отсутствует строка region index, а не payload part. ADDRESS_MISMATCH не описывает запрет родителя со status SUBLOCATION. До согласования код не считается частью принятого контракта; ТЗ этой записью не изменяется.

Путь строится типизированными селекторами от PackRegionIndexInput, строки выше — отображение пути, не строковый API. При duplicate UID ссылка на этот UID неоднозначна: сообщить duplicate, не выбирать родителя правилом last-wins; независимые проверки других строк продолжаются. Сортировать и заменять индекс можно только после отсутствия ошибок. Ни частично заменённый индекс, ни новое state при отказе не возвращаются. Existing require_region_index бросает первый ValueError: нельзя разбирать текст исключения для получения UID/кода. Типизированная проверка должна сохранять эти predicates и иметь один источник правил, без второй расходящейся реализации.

Для этих отказов достаточно принятых полей `code/path/message` существующего проекта PackPreparationIssue. Обязательные generic `expected: Any`, `actual: Any` или отдельный PackLogicError не предлагаются. Правило проекта требует типизированных ошибок и разграничения ответственности, но само по себе не требует expected/actual в каждом record. Если caller действительно должен машинно читать дополнительные значения, их конкретный тип и потребитель должны быть предъявлены отдельно; message не является машинным протоколом.

Приёмочные случаи: duplicate UID; missing parent; parent со status SUBLOCATION; валидный parent позже child; пустой индекс; два независимых неверных parent. Последние три различают сохранение прежних правил, полную очистку и агрегацию. Это требования к будущей реализации, тесты этого среза не запускались.

**Pinned read сохраняет собственный refusal.** Return start_from_base: `PackPreparationState | ManifestReadRefusal`, как в основной таблице; закрытый/чужой pin, missing hold, unsealed, budget и invalid manifest сохраняют существующий ManifestReadReason, не превращаются в пустое состояние или общий invalid input. PackPreparationFailure применяется к собственным нарушениям подготовки, не заменяет этот read result. Не ловить любые exceptions как доменный отказ: IO/busy/unknown outcome/cancellation сохраняют owning семантику.

Агрегация: сначала независимые структурные поля в порядке декларации, затем локальные семантические проверки с исходными индексами. Невалидный parent исключает только зависимые проверки. Использовать именованный PackPreparationIssue, а не инстанс generic FieldPathError; paths строятся через owning FieldRef/CheckedPath. ValidatorAggregationHelper принимает конкретные admissible классы; его snapshot/raise_if_any адаптируется к существующей оболочке PackPreparationError, а не создаёт новый helper. Только после отсутствия issues формируется новое immutable state или начинается следующий IO этап.

Проверки: две независимые ошибки дают две typed diagnostics; отказ не мутирует state и не запускает storage; closed pin сохраняет CLOSED_PIN; infrastructure failure не становится INVALID_MANIFEST; same-address successive writes не дают DUPLICATE_ADDRESS; ошибка финального admission не выдаёт candidate. Тесты ещё не запускались, runtime не менялся.

| Класс | Ответственность / допустимые зависимости и эффекты | Критерий отказа |
|---|---|---|
| PackPreparationService (проект) | Concrete публичные методы; каждый валидирует собственный input и применяет одну операцию. Pure методы зависят от Pack records и существующих pure policies; только start_from_base допускает внутренний pinned read после приёмки binding | Universal dispatcher, вызов producer/Source/другого публичного метода или самостоятельный выбор следующей операции |
| PackPreparationValidator (проект) | Pure локальные и финальные проверки, aggregated Pack field/logic diagnostics | IO, назначение порядка операций, подстановка неизвестных proof |
| PackManifestAssembler (проект) | Одно конечное состояние → полный immutable manifest; без очереди updates и IO | Исполнение операций writer, branch по workflow, второй contents store |
| PackPreparationOperation (проект) | Один финальный prepare, внутренний storage/adoption lifecycle, READY candidate | Последовательность write_* внутри, публикация head или producer call |
| PackPreparationIdentityCodec (проект) | Existing canonical encoding конечного typed request | Новое hash-ядро или неучтённые semantic поля |
| Existing status functions | Pure сохранённые policies, никаких новых effects | Counts объявлены доказательством source/coverage; незаметная смена статусов |

Ошибки переиспользуют проект PackPreparationError/PackPreparationIssue/PackPreparationFailure: wrong address/role, identity/world/base mismatch, invalid input, source/metadata proof mismatch, out-of-scope. Независимые field issues агрегируются existing ValidatorAggregationHelper; зависимые изменения не применяются после отказа. Для каждого метода точный mapping reason/code/path ещё должен быть заполнен; универсальный ValueError наружу не принимается. Pure методы не способны удостоверить seal/hold без финального storage admission.

Приёмочные сценарии: A затем A сохраняет второй ref и его provenance; A затем B сохраняет оба; settlement None/empty различаются; grade получает готовый merge; fine climate не сбрасывается coarse; provisional/final status следуют порядку DAG; S0 не мутирует; final manifest не содержит duplicate addresses или команд; failed operation не создаёт state с частично применённым изменением; final prepare не выдаёт READY без полного admission. Restart и удержания не доказываются тестами чистого state.

**Обязательный gate остаётся OPEN.** Предъявлена карта публичных операций и V1 disposition, но не завершены start/state transport budget, exact Input/provenance/error fields, header initialization, spatial update, scoped lifecycle и конкретные согласованные DAG bindings. CRUD release/settings не закрываются этой таблицей записи. Runtime реализация до приёмки этих зависимостей запрещена по implement-plan; согласие на проектирование не объявляется приёмкой новых нод или всех DTO.

## Проверка внутренней согласованности проекта (2026-11-12)

### State admission и final admission — конкретизация ответственности

У промежуточного PackPreparationState ослабляется только требование **полного итогового состава**, а не типизация вложенных значений. Не вводить флаг skip_validation в WorldPackManifestV2 и не возвращать непроверенный dict вместо state. Перечисленные shared POJO остаются одной декларацией; правила связи между целыми коллекциями выполняются валидатором соответствующего этапа.

| Инвариант | Каждый вход и результат публичной write-операции | Финальный prepare / готовый manifest |
|---|---|---|
| Strict типы, обязательные поля records, отсутствие extra, immutable tree | Всегда. Revalidation экземпляров, включая model_copy/model_construct | Те же правила без ослабления |
| Уникальность parts и metadata addresses | Всегда; sequential replacement возвращает один элемент на адрес | Повторно перед canonical сортировкой/encode |
| Локальная корректность значений | Existing role/status, bounds и registry keys; разрешённая owning нормализация не меняется | Повторная проверка и связь с captured геометрией |
| World/base identity | base_publication неизменна; explicit world-bound данные согласованы с ней | Проверенная pinned база, ожидаемая publication и scope |
| Ref descriptor и роль | Для новой части проверяется known kind/format/version и address role; ref не является доказательством IO | Verified bytes, seal, holds, payload geometry и полный closure через принятые внутренние ports |
| Непосредственные эффекты write | Chunk metadata соответствует записанной части, fine climate устанавливает fine, settlement preserve/replace соблюдён | Эти связи сохраняются в полном составе; нет восстановления значений из счётчиков |
| Наличие всех независимых частей версии | Не требуется до их отдельных DAG-вызовов: новая location part может предшествовать замене общего locations index | Все обязательные связи parts ↔ assembly ↔ indexes проверены. Нельзя опубликовать незавершённую связку |
| Полнота source/metadata provenance | Существующие proof records структурно валидны; затронутая проекция не получает чужое/старое свидетельство. Конкретный binding новых projections остаётся gate | Ровно необходимые proofs для всего итогового состава; соответствие значениям, источникам, retained refs и базе |
| Полное coverage операции | Не выводится каждым write из промежуточного списка parts | Подтверждённое expected/completed и связь с final refs; статус chunks отдельно по старой policy |
| Объём и retention | In-memory state не выдаёт гарантий хранения/удержания; transport bound должен быть определён до реализации | Byte budgets, adoption, exact live-set и READY обязательны |

Отдельный случай `replace_region_index`: передаётся весь индекс, поэтому require_region_index (duplicates, parent existence/status) исполняется сразу; dangling parent нельзя оправдать будущим вызовом, поскольку операция является полной заменой. Для location index его отсутствие на промежуточной стадии не разрешает пропустить финальную сверку. Порядок этих разных операций сохраняется по согласованному DAG маршруту, а не переставляется ради валидатора.

**Распределение между классами:** shared records валидируют собственные поля; PackPreparationValidator предоставляет локальные проверки конкретных inputs и отдельную полную проверку final state; PackPreparationService применяет ровно одно изменение после local admission; PackManifestAssembler только строит полную модель после final admission. Validators не делают IO. PackPreparationOperation обеспечивает внутренний verified read/hold admission и вызывает завершающие проверки до выдачи READY. Утверждение «вызов методов валидатора» не разрешает assembler выполнять публичные write-операции.

**Недублирование state и manifest:** переиспользуются PackStoredPart, PackAssemblyInput и PackStoredAssemblyProvenance с одинаковыми полями/смыслом; новые DraftPart/DraftAssembly/DraftProvenance не вводятся. State добавляет base_publication и означает промежуточное значение, не опубликованный документ. Manifest добавляет wire/binding envelope и полный набор инвариантов завершённой версии. Общий способ объявления fields и корректность самих вложенных POJO ещё проверяются при freeze; эта таблица не объявляет общей приёмки POJO завершённой.

Проверки границы: допустимая промежуточная location part без нового общего index доходит до следующего write, но не проходит final prepare при оставшемся несоответствии; region index с missing parent отклоняется немедленно; duplicate part/extra/mutable вложение отклоняются на обоих этапах; update A сохраняет B/proof; изменённая metadata с прежним несовместимым proof не допускается под видом inheritance. После отказа исходный state остаётся прежним и новый state/READY не выдаётся. Pure тесты этих случаев не заменяют проверку реального storage lifecycle.

Этим уточнено, **какие** проверки разделяются; exact field/logic DTO, provenance binding и transport budget ещё OPEN. Не добавлять недостающий proof по default и не ослаблять завершённый manifest, чтобы формально принять state.

Исправлены в основных объявлениях: read-refusal union start_from_base; отсутствие codec-настроек в public input; разделение sync_grid_metadata и set_last_l0_mode по фактическому порядку WorldMapBakeOrchestrator (sync → tile writes → mode). Это коррекции проекта для соблюдения ранее принятой семантики, не утверждение новых DAG-нod/параллельных стадий.

Остаются конкретные Pack-owned вопросы, без подмены внешнего source_proof:

1. **Header provenance после последовательных изменений.** Grid sync, map tile side и mode меняют одну header projection в разные моменты. Нельзя требовать proof от старого header для нового значения или выдумывать его внутри write. Нужно согласовать точный binding каждого изменения к итоговой projection; полный Input этих методов пока не принят.
2. **Допуск промежуточного state.** Partial assembly и её поля обязаны быть валидными типами, даже если ещё отсутствуют обязательные parts. Разделить локальные constraints shared POJO и финальные cross-part validators, не ослабляя готовый manifest. Проверить отсутствие дублирования state/manifest по каждому полю.
3. **Основание финальной проверки базы.** State хранит publication, но не capability для нового storage read. Финальный prepare должен получить действующий внутренний pin/retention binding; immutable state и проверка в start сами по себе не доказывают доступность базы в конце. Публичный lease/backend в DTO не добавлять.
4. **Покрытие не доказывает порядок.** Конечные refs/proofs и coverage проверяют результат; порядок вызовов подтверждается конкретным согласованным DAG binding. Domain state не содержит скрытого command log. Same final body не является evidence выполнения конкретного маршрута.
5. **Structural/logic errors.** Таблица ошибок покрывает semantic cases, но полный набор concrete field и logic errors ещё не предъявлен. Его нельзя закрыть generic ValueError или именованием одного carrier.

Приёмка всего проекта остаётся НЕ ПРОЙДЕНА. Эти пункты — точные недостающие контракты для дальнейшей работы; принятие направления public write operations не считается разрешением реализовать placeholders. Проверка статическая, без runtime тестов.
