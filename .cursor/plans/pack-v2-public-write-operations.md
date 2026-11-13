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
| `start_empty(self, request: PackPreparationEmptyInput) -> PackPreparationState` | `base_publication: WorldPublicationRef`, `initial_assembly: PackAssemblyInput` | Pure. Требует base_publication.pack_hash=None; создаёт пустые parts/assembly_provenance и начальную metadata из явных значений. Начальные коллекции assembly пусты; header задаётся по прежним owning правилам без новых defaults. Если publication уже содержит Pack — BASE_PUBLICATION_MISMATCH, без автоматического перехода в другой метод |
| `async start_from_base(self, request: PackPreparationBaseInput) -> PackPreparationState \| ManifestReadRefusal` | `pin: PackPinnedReadIdentity`, `max_manifest_bytes: strict positive int` | Только verified bounded pinned read через внутренний Pack binding. Требует pin.publication.pack_hash не None; проверяет соответствие точных manifest bytes/ref, world, schema и pin. Копирует состав/provenance базы без latest lookup. Нет Pack в publication — BASE_PUBLICATION_MISMATCH, не fallback на start_empty |

PackPinnedReadIdentity — существующий проект Pack read-контракта из ТЗ, не новый набор скопированных store/execution/invocation полей. Его extraction/mapping с existing ManifestPinRead всё ещё требует приёмки. Тип initial_assembly общий с остальным Pack проектом. Новая версия не получает готовность только из наличия такого input: source proof и header initialization остаются соответствующими gates.

**Уточнённые поля PackPreparationState:** `base_publication: WorldPublicationRef`, `parts: tuple[PackStoredPart, ...]`, `assembly: PackAssemblyInput`, `assembly_provenance: tuple[PackStoredAssemblyProvenance, ...]`. world_uid берётся из base_publication; не повторяется отдельным полем. Состав metadata/parts переиспользует общие типы stored manifest, но полный request state имеет иную ответственность: содержит base expectation и допускает незавершённую межчастную сборку. Не выдавать его как WorldPackManifestV2 и не ослаблять валидаторы готового manifest ради промежуточного состояния. Codec_version/payload_format принадлежат manifest binding, а не этому публичному state.

Каждый write Input содержит обязательный `state: PackPreparationState` и только описанные поля своей операции. Return — новое состояние с неизменным base_publication. Значение request.state валидируется повторно; ошибки не меняют исходный объект. Две записи одного адреса являются двумя вызовами с передачей результата, не двумя entries одного списка. Operation ID/fingerprint финального prepare не назначают новые revisions и не являются версией mutable session.

Все промежуточные значения обязаны оставаться обычными материализованными POJO без lazy readers. Состояние не хранит pin как capability, не продлевает его и не обещает сохранность artifacts. При finish нужен действующий принятый retention/adoption binding; после закрытия pin нельзя повторить storage read по старому удостоверению. Отдельный state holder или новый storage этим уточнением не вводится.

Проверки: start_empty отклоняет непустую Pack-базу; start_from_base отклоняет отсутствие Pack, closed/foreign pin и несовпадение publication/ref; начало от A после активации B читает закреплённую A; в state один world source; write сохраняет base expectation; S0 не меняется при успехе или отказе; start не открывает staging и не запускает prepare/activate.

Начальная assembly из explicit данных сохраняет принятое требование без скрытого resolver. Это ещё не доказательство паритета V1 defaults: нужно завершить таблицу начального header и семантику первой операции. Конкретные false/empty значения не придумываются по именам полей.

Предлагаемый `dataModel/worldPack/preparation/state.py::PackPreparationState` имеет уточнённые выше поля base_publication, parts, assembly, assembly_provenance. Base_publication использует существующий WorldPublicationRef; parts — tuple существующих проектных PackStoredPart; assembly и provenance используют общие Pack-owned metadata records. Поля состава должны иметь единственную декларацию, общую с manifest: копия дерева моделей и validators не допускается. Способ общего объявления конкретизирован в пункте 1 ниже; его реализация и nested admission ещё не проверены. Source proof не определяется этим документом, его разрабатывает другой агент.

State — глубоко immutable значение промежуточной подготовки. Оно не является опубликованной версией, manifest ArtifactRef, receipt удержания или новым сохраняемым contents object. Допускаются промежуточные состояния, ещё не прошедшие полную межчастную проверку; окончательные полнота/coverage/ref/proof проверки обязательны в prepare. Это не разрешает выдавать повреждённые вложенные POJO или игнорировать локальные инварианты операции.

У публичных входов нет writer/backend/CommitScope/lease/callback. Передача S0 → S1 → S2 через DAG сохраняет причинный порядок. Внутренний scope/adoption final prepare остаётся отдельным незакрытым binding. Существование state не доказывает удержание его refs. Отдельные session store, mutable singleton draft, журнал команд и новый OperationKind не вводятся.

Операции изменения состояния pure относительно внешних эффектов; base получает отдельный read/start контракт. Они не пишут blobs или active head. Сериализация/размер промежуточного state, restart и срок удержания входных refs должны быть проверены до реализации; при доказанном превышении transport budget решение пересматривается отдельно, не скрывается неутверждённым state store.

## Публичные методы и точные обязанности

### Единый lifecycle metadata provenance в промежуточном state

Текущий контракт после консолидации: start_empty создаёт assembly из explicit input и пустой assembly_provenance; start_from_base переносит полный состав proofs закреплённой базы. Вычисляющие write-методы не принимают proof ещё не вычисленной metadata. Существующие proofs незатронутых projections сохраняются; proof изменённой/удалённой projection удаляется. При создании новой строки proof отсутствует до bind. Присутствующий record всегда должен соответствовать своей текущей projection; «stale, но пока не проверен» в state не допускается.

Для явной полной замены location/settlement/region row proof заменяемой строки снимается консервативно, даже при равном значении: равенство значения не подтверждает одинаковое происхождение нового результата. При region replacement records удалённых rows также снимаются. Чужие строки сохраняют свои proofs. Для присваиваний header и tile status при неизменном значении допустимо сохранить прежний proof только как свидетельство прежнего значения; это не evidence нового materialization. При изменении скаляра снимается proof всей соответствующей header/tile projection. Chunk replacement снимает proof этого chunk; tile proof снимается отдельно при создании tile или изменении его собственного status. Actual early return прежней status policy сохраняется. Полнота исполнения проверяется отдельным coverage, не фактом сохранённого metadata proof.

Методы без metadata-эффекта (coarse climate, locations index payload, grade sidecars, spatial root) не снимают assembly proofs. Ролевое удаление использует своё явно описанное metadata-изменение и те же правила инвалидирования. Не удалять proofs всех metadata при любой записи part.

describe_metadata остаётся pure-чтением subject; bind_metadata_provenance отдельно добавляет проверенные records и не меняет значения assembly/parts. Вход bind и правила exact subject/base описаны в разделе локальной идентификации. Final prepare требует полный комплект proofs и не вызывает bind самостоятельно. Это изменение контракта промежуточного state, а не ослабление finished manifest. Внешние evidence/Planning mappings остаются выделенными интеграционными вопросами, а не новыми параметрами write. Runtime не реализован.

Все методы ниже принадлежат PackPreparationService. Входы размещаются в `dataModel/worldPack/preparation/operations.py`; fields state/address/part используют общие типы, не повторяют их содержимое. Результат операций изменения — PackPreparationState из state.py. Они выбрасывают PackPreparationFailure с PackPreparationError из существующего проекта preparation/errors; infrastructure errors сохраняют owning тип. Передача failure через DAG не разрешает retry внутри метода.

| Сигнатура метода | Поля Input сверх state | Источник поведения / локальный результат |
|---|---|---|
| `sync_grid_metadata(self, request: PackGridMetadataInput) -> PackPreparationState` | captured fine_cells_per_map_cell и world_map_cells_per_tile; owning constraints без новых defaults | Pack-owned эффект sync_world_metadata до записи L0 tiles. Не меняет last_l0_mode, не читает World, не выбирает resolver. Codec-поля остаются внутренним binding |
| `set_last_l0_mode(self, request: PackLastL0ModeInput) -> PackPreparationState` | mode: PackBakeMode | Присваивание bake_mode в WorldMapBakeOrchestrator после цикла L0 tiles, включая пустой цикл. Не запускает bake и не обновляет сетку |
| `write_map_tile(self, request: PackMapTileInput) -> PackPreparationState` | part: PackMapTilePartInput; effective side | write_world_map_tile: заменить только адресованную часть, сохранить chunks/climate тайла; side соответствует payload. Обновление parent-light cache не переносится в pure операцию |
| `write_wilderness_chunk(self, request: PackWildernessChunkInput) -> PackPreparationState` | part: PackWildernessChunkPartInput; refine_role: ChunkRefineRole либо None | write_wilderness_chunk → commit_chunk: заменить chunk по адресу, затем provisional status по existing policy без expected. None роли записывается как значение |
| `write_location_terrain(self, request: PackLocationTerrainInput) -> PackPreparationState` | part: PackLocationTerrainPartInput; territory_volume: TerritoryVolume | write_location_terrain: заменить запись одной локации; прежний coarse default новой metadata row сохраняется |
| `write_settlement_structure(self, request: PackSettlementStructureInput) -> PackPreparationState` | part: PackSettlementStructurePartInput; territory_volume; packed_district_uids: tuple UID либо None; structure_status: SettlementStructureStatus либо None | publish_settlement_structure: None сохраняет прежнее поле, явно пустой packed set очищает. Без базы owning defaults. Здесь нет tmp rename/SQL/публикации head |
| `write_coarse_climate(self, request: PackCoarseClimateInput) -> PackPreparationState` | part: PackCoarseClimatePartInput | write_climate_coarse: заменить singleton, не сбрасывать fine статусы тайлов |
| `write_fine_climate(self, request: PackFineClimateInput) -> PackPreparationState` | part: PackFineClimatePartInput | write_climate_tile: заменить адресованную часть и установить fine у данного тайла; прочие поля сохранить |
| `replace_locations_index(self, request: PackLocationsIndexInput) -> PackPreparationState` | part: PackLocationsIndexPartInput | write_locations_index: полная замена payload индекса. Пустой индекс — реальный готовый payload, не отсутствие ref |
| `replace_region_index(self, request: PackRegionIndexInput) -> PackPreparationState` | entries: tuple[WildernessRegionEntry, ...] | replace_region_index: валидировать весь индекс existing require_region_index, заменить целиком; пустой tuple очищает |
| `write_tile_grade_slots(self, request: PackTileGradeSlotsInput) -> PackPreparationState` | part: PackTileGradeSlotsPartInput | Принять полный готовый результат существующего incoming-first merge. Не выполнять merge, не запускать grade producer |
| `write_location_grade_slots(self, request: PackLocationGradeSlotsInput) -> PackPreparationState` | part: PackLocationGradeSlotsPartInput | То же для location address. Пустой incoming у producer сохраняет прежние slots; Pack получает уже полный результат |
| `write_spatial_root(self, request: PackSpatialRootInput) -> PackPreparationState` | part: PackSpatialRootPartInput | [Проект контракта](pack-spatial-root-write-contract.md): добавить/заменить только root-part данного domain вместе с provenance, сохранить assembly и остальные parts; без Hydrology/IO/merge shards |
| `delete_part(self, request: PackDeletePartInput) -> PackPreparationState` | address: PackPartAddress | [Проект удаления](pack-delete-part-contract.md): удалить один part вместе с его provenance, сохранить assembly и остальные адреса; absent предлагается как no-op. Без cascade/GC. Допустимость итогового удаления проверяет final admission; ролевые metadata-сценарии ещё OPEN |
| `delete_wilderness_chunk(self, request: PackDeleteWildernessChunkInput) -> PackPreparationState` | address: PackChunkAddress | [Проект согласованного удаления](pack-delete-wilderness-chunk-contract.md): удалить chunk part/metadata и их proofs; существующий tile сохранить, status пересчитать pure provisional policy. Обновление tile provenance следует общему metadata-output контракту; expected-пересчёт остаётся отдельным вызовом DAG |
| `delete_fine_climate(self, request: PackDeleteFineClimateInput) -> PackPreparationState` | address: PackFineClimateAddress | [Проект удаления fine](pack-delete-fine-climate-contract.md): удалить fine part/provenance, существующий tile fine→coarse; без генерации coarse, изменения других полей и вложенного публичного вызова. Обновлённый tile proof — по общему metadata-output контракту |
| `delete_location_terrain(self, request: PackDeleteLocationTerrainInput) -> PackPreparationState` | address: PackLocationTerrainAddress | [Проект удаления представлений](pack-delete-location-representations.md): удалить terrain part, location metadata и их proofs; сохранить settlement, pins, sidecars и source entities. Final scope/dependencies обязательны |
| `delete_settlement_structure(self, request: PackDeleteSettlementStructureInput) -> PackPreparationState` | address: PackSettlementAddress | [Тот же trace](pack-delete-location-representations.md): удалить settlement part, settlement metadata и их proofs; сохранить terrain/pins/source entities; без каскада |
| `recalculate_wilderness_status(self, request: PackWildernessStatusInput) -> PackPreparationState` | address: PackTileMetadataAddress; expected_chunks: strict int либо None | recalc_wilderness_status: None явно запускает provisional пересчёт, int — existing count policy. Отсутствие вызова сохраняет статус. Bounds должны соответствовать старой policy, новый произвольный запрет negative/zero не вводить |

Restriction part.address.kind является конкретной типизированной границей каждого Input; передача несовместимого адреса — ошибка до изменения. Способ объявления без зеркальных PackPartInput выбран ниже. Таблица не разрешает Any/dict/строковые универсальные kinds. TerritoryVolume и status/role values переиспользуются. UID остаётся отдельной проверкой соответствия existing str и proposed EntityUid.

Для удаления только L0 используется delete_part с PackMapTileAddress: [trace map_tile](pack-delete-map-tile-trace.md) не выявил отдельного metadata-эффекта, поэтому delete_map_tile/зеркальный input не добавляются. Tile/chunks/climate/proofs и grid scalars сохраняются; допустимость отсутствия проверяет final admission.

[Итоговый roster удаления](pack-delete-remaining-roles.md) покрывает все 10 payload-ролей: delete_part достаточен для map_tile, climate_coarse, locations_index, spatial_root и двух grade sidecars; четыре ролевых метода выше выполняют дополнительные metadata-эффекты. Наличие roster не закрывает общий metadata-output/errors/scope freeze. Дополнительные delete_coarse/delete_index/delete_root/delete_grade методы без отдельного эффекта не вводятся.

Write-входы таблицы не содержат metadata provenance: они вычисляют metadata, а привязка выполняется отдельным bind_metadata_provenance. Полный provenance payload сохраняется в part и не становится optional. Header, новые/изменённые строки могут временно не иметь assembly_provenance; правила инвалидирования и final admission приведены ниже. Это единая текущая форма контракта вместо прежнего требования proof результата до вычисляющей операции.

### Пункт 1 рабочего списка: типизация входов и общие модели

**Исправление общей приёмки:** публичные поля используют именованные concrete подклассы специализаций, как требует existing ModelIdentity/CheckedPath. Generic база объявляет поля один раз; concrete классы не переобъявляют их. Ни type alias на параметризованный класс, ни прямой _PackPartInput[Address] в public field не заменяют именованный класс. Это исправление проекта; runtime диагностики ещё проверяются при реализации.

Проектное решение по поручению «делаем по списку». Это конкретизация деклараций; завершённая приёмка зависит от полей provenance (пункт 2) и финального coverage/lifecycle (пункты 3–4). Новые типы пока не реализованы.

**Ограничение адреса без копий part.** В `preparation/parts.py` внутренняя generic база `_PackPartInput[AddressT]` единожды объявляет `address: AddressT`, `artifact: ArtifactRef`, `provenance: PackPartProvenance`. AddressT ограничен PackPartAddress. Публичный общий `PackPartInput` — именованный concrete подкласс `_PackPartInput[PackPartAddress]`; специализированные классы перечислены ниже. Каждый объявляется отдельным `class ...(_PackPartInput[...])` без новых/повторных полей, а не alias. Это одно определение состава с разными ограничениями адреса, не зеркальные DTO. Canonical schema registry регистрирует конкретные named classes со стабильной identity; внутреннюю generic базу не регистрировать как публичный record. Stored part сохраняет прежний отдельный контракт с абсолютным provenance без new/inherited wrappers.

| Input в preparation/operations.py | Именованный тип поля part, preparation/parts.py | База специализации (не публичная аннотация поля) |
|---|---|---|
| PackMapTileInput | PackMapTilePartInput | _PackPartInput[PackMapTileAddress] |
| PackWildernessChunkInput | PackWildernessChunkPartInput | _PackPartInput[PackChunkAddress] |
| PackLocationTerrainInput | PackLocationTerrainPartInput | _PackPartInput[PackLocationTerrainAddress] |
| PackSettlementStructureInput | PackSettlementStructurePartInput | _PackPartInput[PackSettlementAddress] |
| PackCoarseClimateInput | PackCoarseClimatePartInput | _PackPartInput[PackCoarseClimateAddress] |
| PackFineClimateInput | PackFineClimatePartInput | _PackPartInput[PackFineClimateAddress] |
| PackLocationsIndexInput | PackLocationsIndexPartInput | _PackPartInput[PackLocationsIndexAddress] |
| PackTileGradeSlotsInput | PackTileGradeSlotsPartInput | _PackPartInput[PackTileGradeSlotsAddress] |
| PackLocationGradeSlotsInput | PackLocationGradeSlotsPartInput | _PackPartInput[PackLocationGradeSlotsAddress] |
| PackSpatialRootInput | PackSpatialRootPartInput | _PackPartInput[PackSpatialRootAddress] |

Остальные операции part не принимают. В inputs не повторяются gx/gy/location_uid, уже содержащиеся в part.address. Дополнительные territory/status/role относятся к metadata, а не дублируют адрес. У recalculate_wilderness_status отдельный PackTileMetadataAddress нужен, поскольку payload part в этой операции отсутствует. Format/version проверяются по owning descriptor, не второй таблицей строковых format keys. Конкретные классы адресов и их Literal-дискриминаторы берутся из roster §6.5 контракта Pack.

**Единая декларация состава.** Предлагаемый `dataModel/worldPack/meta/packCompositionFields.py::_PackCompositionFields` — внутренняя база моделей, объявляющая ровно `parts: tuple[PackStoredPart, ...]`, `assembly: PackAssemblyInput`, `assembly_provenance: tuple[PackStoredAssemblyProvenance, ...]`. Она не является новым публичным contents DTO, не вкладывается отдельным объектом в wire и не используется как тип аргумента/результата. PackPreparationState наследует эти поля и добавляет base_publication; итоговый WorldPackManifestV2 наследует те же поля и добавляет существующий manifest envelope, world_uid и вычисляемые показатели. При удалении legacy действует уже принятый rename единственного manifest, а не второй alias. Публичный сервис по-прежнему возвращает PackPreparationState, assembler — готовый manifest.

Локальные проверки общих полей принадлежат этой базе/вложенным owning POJO. Проверки полноты размещаются только на конечном manifest и в final admission, поэтому state не наследует завершённый manifest и не отключает его validators. Существующая `_ManifestFields` из `meta/worldPackManifest.py` содержит legacy-состав; её нельзя механически использовать для нового state или объявить готовой реализацией нового общего состава. Никаких DraftAssembly/DraftPart, второго contents artifact или копии metadata records.

**Оставшиеся поля входов.** `state` обязателен у каждой операции. `refine_role: ChunkRefineRole | None`, `structure_status: SettlementStructureStatus | None` и `packed_district_uids: tuple[EntityUid, ...] | None` сохраняют описанную выше семантику None; это не универсальный признак отсутствия изменения. `expected_chunks` остаётся strict int | None без нового нижнего bound. `entries` — tuple[WildernessRegionEntry, ...], не tuple dict. Effective side/grid constraints берутся из owning моделей, не объявляются произвольными positive int по названию. Metadata provenance отсутствует в этих write-входах и поступает в отдельный bind. Nullable поля payload proof вместо этого не вводятся.

**Nested admission: подтверждённый пробел существующих типов.** Проверены `wire/territoryVolume.py` и `meta/wildernessRegionEntry.py`. TerritoryVolume имеет extra=ignore, выполняет int(...) и упорядочивает пары bounds; STRICT_BOUNDS контролирует целочисленные значения только при передаче специального context. WildernessRegionEntry/RegionIndexBounds frozen и extra=forbid, но не объявляют strict/revalidate_instances=always. Поэтому frozen и strict на внешнем Input не доказывают требуемый deep admission; доверять model_construct/model_copy нельзя.

На Pack boundary перед owning нормализацией требуется проверять реальные типы всех шести координат TerritoryVolume и отсутствие extra; затем сохранять существующее упорядочивание min/max. Проверка чисел не должна превращать обратный порядок границ в новый отказ: раньше owning тип его нормализовал. RegionIndexBounds, напротив, уже отклоняет обратный порядок, и это правило сохраняется. Для повторной проверки экземпляра должны быть проверены его фактические поля/extra и вложенные значения, а не только isinstance или model_validate экземпляра без revalidation. Новая зеркальная StrictTerritoryVolume/StrictWildernessRegionEntry не вводится. Способ общей boundary-проверки должен использовать объявления owning полей; копировать списки полей/validators в каждый Input запрещено. Изменение общего поведения legacy моделей для всех callers не является автоматическим следствием этого решения.

**Ошибки входов.** Состав закрытого union diagnostics согласован и синхронизирован с ТЗ 2026-11-13: PackPreparationDiagnostic = JsonFieldError | WireShapeIssue | PackPreparationIssue; [цепочка admission](pack-preparation-issue-union.md). Неподходящий address discriminator отвергается schema admission конкретной специализации, а семантическое несовпадение допустимого адреса с данными — ADDRESS_MISMATCH; двойной диагностики нет. Поля generic expected/actual не добавляются без конкретного потребителя. При наличии structural issues reason=INVALID_INPUT; runtime, canonical registration и полная semantic матрица не объявляются принятыми одним согласованием union.

Приёмка пункта 1: каждый перечисленный Input отвергает все чужие address variants; правильный part не теряет artifact/provenance; ни один публичный input не использует bare generic; поля состава объявлены один раз; внешняя модель не пропускает forged вложенный instance, bool/float/string вместо strict координаты и extra; прежний min/max TerritoryVolume сохранён; обратный bbox региона по-прежнему отклоняется; nullable settlement поля сохраняют различие None/empty. До выполнения этих проверок и завершения provenance полей пункт не отмечается реализованным или полностью принятым.

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

### Пункт 2 рабочего списка: header и metadata provenance

Актуальное уточнение 2026-11-13: [metadata dependency usage](pack-metadata-dependency-usage.md). Пользователь согласовал детализацию по независимо обновляемым полям, необходимые изменения Pack POJO и отказ partial update старой строки при неизвестных зависимостях сохранённых полей; read/unchanged inheritance разрешены. [Конкретный проект POJO](pack-metadata-dependency-pojo.md) предъявляет transient usage, describe/bind и durable attribution. Предыдущие сигнатуры ниже — исходная схема до этого дополнения; точные новые carriers/bindings ещё требуют проверки, не реализуются по одному факту согласования направления.

Проверка старых операций `worldPackWriter.py`: sync_world_metadata, _upsert_tile, write_world_map_tile, commit_chunk, recalc_wilderness_status, write_climate_tile, publish_settlement_structure. Единица свидетельства — сохранённая semantic projection из owning контракта, а не имя операции или её частичный input. Header содержит только скаляры PackAssemblyInput; codec/envelope в него не добавляются. Tile projection исключает chunks; chunk имеет отдельный адрес. При сравнении используются значения owning POJO и canonical codec, а не repr и не количество payload.

| Операция | Потенциально изменяемые metadata projections | Что сохраняется |
|---|---|---|
| start_empty | Header из explicit initial assembly | Parts и metadata collections пусты; новый header не получает inherited proof |
| start_from_base | Нет новых projections | Все значения и proofs закреплённой версии переносятся без изменений |
| sync_grid_metadata | Header: fine_cells_per_map_cell, world_map_cells_per_tile | Другие скаляры, включая last_l0_mode |
| set_last_l0_mode | Header: last_l0_mode | Остальной header; вызов остаётся после L0 tile writes |
| write_map_tile | Header: фактический side; tile projection при создании тайла | У существующего tile собственные statuses и все chunks; замена ref сама по себе не меняет tile projection |
| write_wilderness_chunk | Адресованный chunk; tile projection при создании или изменении provisional status | Все другие chunks и их proofs; climate_status существующего tile |
| delete_wilderness_chunk | Адресованные part/chunk metadata и их proofs исключаются; tile status получает provisional значение, его evidence повторно связывается с изменёнными входами расчёта | Остальные chunks/parts, tile и climate; absent address без part/metadata — no-op. [Точная граница](pack-delete-wilderness-chunk-contract.md); равенство status не доказывает применимость прежнего proof |
| delete_fine_climate | Fine part/provenance исключается; tile climate_status fine→coarse требует подходящего нового metadata evidence | Coarse part, map_tile, chunks, wilderness status и другие tiles сохраняются; coarse не генерируется. [Контракт](pack-delete-fine-climate-contract.md) |
| delete_location_terrain / delete_settlement_structure | Исключается только owning metadata row и её proof вместе с адресованным part/provenance | Второе представление того же UID, pins и прочие projections сохраняются; [точные эффекты и final gates](pack-delete-location-representations.md) |
| recalculate_wilderness_status | Tile projection при создании или изменении status | Все chunks; даже пустой вызов может создать tile через старый _upsert_tile |
| write_fine_climate | Tile projection при создании или переходе climate_status в fine | Chunks и wilderness status существующего tile |
| write_location_terrain | Адресованная location projection с прежним coarse default | Остальные location rows |
| write_settlement_structure | Адресованная settlement projection после разрешения None по базе/defaults | Прежние packed/status при None; чужие settlements |
| replace_region_index | Итоговые region rows; удалённые rows теряют свои proof records | Proof неизменной строки может сохраняться, если строка и её provenance действительно наследуются из базы |
| write_coarse_climate, replace_locations_index, write_tile_grade_slots, write_location_grade_slots, write_spatial_root | Не изменяют assembly projections | Вся assembly и её provenance; изменяется соответствующий payload part |

Наличие записи и равенство значения проверяются раздельно: newly created tile со значениями defaults требует происхождения новой строки. Для прежней неизменной projection не требуется искусственно выпускать новый proof только из-за вызова write. Payload part при этом имеет собственный provenance admission. Если значение projection изменилось, старое свидетельство не переносится. Если оно позже вернулось к прежнему значению, автоматически объявлять новое вычисление inherited нельзя: это отдельная проверка связи с базой, а не сравнение одного hash.

**Незакрытая причинная зависимость в прежнем предложении.** Вход каждой write-операции требовал proof готовой metadata, но саму готовую metadata вычисляет эта операция Pack. Settlement partial input не равен результату; chunk input не содержит итогового tile status; header после tile write включает сохранённые скаляры базы. Ни DAG, ни внешний producer не должны повторять Pack merge/status/header правила для изготовления свидетельства. Исходный proof payload также не удостоверяет эти новые projections. Один общий proof от capture не закрывает эту связь.

**Предложение для согласования: отдельная открытая привязка metadata proofs после вычисления Pack.** Сохранить последовательность старых write-операций и их результат. Промежуточный state допускает отсутствие provenance для новых/изменённых metadata projections; при изменении прежний record удаляется, а не оставляется под видом действительного proof. Все присутствующие records по-прежнему строго валидны. Неполное state не является опубликованным manifest и не проходит final prepare. Parts сохраняют уже принятый полный provenance — это предложение относится только к metadata.

После выбранной последовательности write-вызовов DAG передаёт описанные Pack subjects в согласованную операцию получения evidence владельца, затем вызывает PackPreparationService.bind_metadata_provenance(request: PackMetadataProvenanceInput) -> PackPreparationState. Актуальный input в preparation/operations.py: state: PackPreparationState, entries: tuple[PackMetadataProofBinding, ...]; binding содержит subject: PackMetadataSubject и provenance: PackPartProvenance, как определено ниже в разделе локальной идентификации. Прежний вариант entries из PackAssemblyProvenanceEntry заменён, alias-вход не сохраняется. Метод не изменяет assembly/parts, не вычисляет geometry/status, не вызывает Source и не запускает prepare. Он проверяет уникальность адресов subjects, базу и fingerprint текущей projection, затем provenance admission. Только успешная проверка всего вызова возвращает state с привязанными records; неполный набор не даёт READY. Это отдельная pure операция, не dispatcher write-команд.

После выбора направления и консолидации start_empty не принимает initial_provenance, вычисляющие write-операции не принимают metadata provenance; основные таблицы синхронизированы. start_from_base сохраняет полный provenance базы. Привязка результата выполняется отдельным bind по контракту ниже; внешний evidence mapping не подменяется свободным dict или одним fingerprint.

Альтернатива — отдельные публичные Pack preview-операции перед каждой записью: Pack вычисляет точную projection, DAG получает evidence и вызывает write с ним. Это сохраняет требование полного provenance в каждом state, но добавляет предварительный вызов для каждой операции и проверку, что evidence рассчитан для того же входного state. Не выбирать такой маршрут молча и не переносить preview-расчёт в DAG.

Предложение с последующей привязкой сохраняет старый порядок изменений и устраняет необходимость повторять доменную логику вне Pack. Оно меняет только контракт промежуточной подготовки, поэтому должно быть явно согласовано перед изменением основных сигнатур. До решения пункт 2 не закрыт, runtime отсутствует. Проверки после согласования: settlement None наследует прежние поля до evidence; chunk обновляет только свой proof и при необходимости tile proof; новый default tile требует evidence; повторная смена header аннулирует старый proof; незатронутые proofs неизменны; missing/stale metadata proof блокирует READY.

### Ревью цепочки отложенной привязки metadata proof

**Вердикт: НЕ ПРИНЯТО.** Проверено по поручению пользователя «проверь цепочку». Предложение пункта 2 выше остаётся рассмотренным вариантом, а не выбранной архитектурой. Само разрешение неполного промежуточного state не противоречит запрету публикации без proof, но представленная цепочка не доказывает происхождение вычисленной metadata. Основные start/write сигнатуры не переключаются на этот вариант.

| Переход | Проверяемые данные и владелец | Результат ревью |
|---|---|---|
| Pinned base → start_from_base | Pack читает закреплённый manifest и переносит значения/proofs | Направление корректно; действующий pin/retention на весь нужный период остаётся отдельной незакрытой связью lifecycle |
| State + input → write → новый state | Pack исполняет свой старый локальный алгоритм | Удаление stale proof допустимо только как предложение изменения intermediate invariant. Однако результат не содержит подтверждённой связи вычисленной projection с использованными входами |
| Новый state → typed subjects для подтверждения | Subject должен выделять Pack, DAG только передаёт результат | Публичный метод, полный output POJO и errors не предъявлены. DAG не должен сам вычислять header/tile projection и её зависимости |
| Subjects → evidence | Pack — producer собственной metadata; Source подтверждает исходные версии/тела/удержания | Нельзя приписывать Source подтверждение Pack merge/status алгоритма. Конкретный контракт переноса producer evidence и source dependencies отсутствует |
| Evidence + state → bind_metadata_provenance | Проверка exact subject и допустимого происхождения | Проектный input содержит entries(address, provenance), но не предъявлена связь этих данных с фактическим результатом Pack. Обещанная проверка ownership evidence не обеспечена конкретным контрактом |
| Bound state → final prepare → READY | Полный metadata coverage, база/scope, provenance, bytes/holds/closure | Наличие одного proof на адрес необходимо, но не устраняет предыдущий пробел. Existing finish_pack_preparation удостоверяет staging/READY/live-set, а не происхождение metadata |
| READY → activate | Отдельный вызов DAG с принятым candidate | Отложенный bind не должен вводить auto-activate или менять publication CAS. До полноценного prepare эта стадия недостижима |

**F1 — потеря основания вычисления.** Пример: settlement получает новый territory, но packed_district_uids и status наследует из базы. После удаления прежнего metadata proof итоговые значения не показывают, какие поля наследованы и какие зависимости участвовали в расчёте. Header объединяет сохранённые поля, grid input и последний effective side; tile status зависит от текущих chunks и expected_chunks конкретного вызова. Конечное значение не восстанавливает эти зависимости. База отдельно помогает проверить inheritance, но не заменяет evidence новых и смешанных результатов. Pack обязан передать подтверждаемую связь результата со своими реально использованными typed inputs; одного последующего вычисления hash недостаточно. Не добавлять для этого command log, не сохранять все промежуточные payload и не расширять Source proof за владельца.

**F2 — неподтверждённая роль Source.** В source-proof-v2-contract-spec §6 уже указано: producer сообщает реальные зависимости, Source подтверждает версии/тела/удержания. Для Pack-derived metadata producer — Pack. Поэтому формулировка «передать metadata для подтверждения происхождения владельцу» недостаточна: сначала требуется Pack-owned результат вычисления с точным dependency mapping, затем согласованный контракт Source evidence. Source не должен повторять settlement preserve, wilderness status или header merge и не может восстановить их по одному subject hash. Это проблема междоменной связи, не просьба заново спроектировать concrete source_proof.

**F3 — bind проверяет больше, чем позволяет его объявленный вход.** В `entries` есть address и PackPartProvenance; принадлежность proof точному subject и связь с producer outcome пока только обещаны. Схема source_proof может дать subject binding, но считать это уже существующим полем нельзя. Внешний transient evidence также не определён. Нужны конкретные owner method → output fields → bind input и проверка независимого смешения двух результатов. Требование не означает криптографическую подпись или новый receipt store: достаточно принятого проверяемого контракта, но сейчас его нет. Preview-альтернатива из пункта 2 сама по себе F1–F3 также не закрывает.

**F4 — чрезмерное обещание отказа запоздалому proof.** При A → B старый proof A отвергается по несовпадению subject. При A → B → A равенство final value само по себе не отличает две подготовки. Если evidence относится к exact базе/зависимостям и они совпадают, его повторное применение может быть допустимым; если зависимости различаются, одинаковое значение не разрешает reuse. Следовательно, слова выше «повторно изменённая projection отклоняет запоздалое свидетельство» не являются доказанной гарантией. Требуется проверка принятой semantic identity (subject, база и релевантные dependencies), а не только значения и не новый счётчик session. Время получения proof само по себе не определяет валидность.

**F5 — незакрытое удержание между стадиями.** Immutable state не удерживает base/source refs. Дополнительный цикл получения evidence увеличивает интервал, в котором должны действовать принятые pin/holds. Отказ при потерянном удержании должен происходить до READY; успешный bind не гарантирует доступность при prepare. Existing staging finish не закрывает atomic adoption. Этот пробел уже принадлежит пункту 4 списка и не устраняется добавлением поля pin/backend в DTO.

Что выдерживает проверку: DAG остаётся единственным оркестратором; Pack не вызывает Source; последовательность старых write-эффектов не переставляется; untouched rows/proofs сохраняются; изменённое значение не несёт старый proof; incomplete state не публикуется. Эти свойства необходимы, но недостаточны для приёмки цепочки по обязательным критериям проекта.

Перед повторной приёмкой требуется одна сквозная конкретизация: публичный Pack write/output сохраняет необходимую связь результата с входами → Pack выдаёт typed metadata subject и зависимости → существующий/согласованный owner contract формирует evidence → Pack bind проверяет точный subject/dependencies → final prepare проверяет базу, completeness и lifecycle. Нельзя закрыть этап просто пользовательским согласием на incomplete state. До предъявления этой связи вопрос о выборе bind против preview преждевременен; ранее предложенное согласование варианта снимается.

Минимальные контрпримеры для проверки будущего контракта: одинаковая settlement row из разных source revisions; None против explicit equal packed tuple; chunk write с неизменным tile status; header side A → B → A; stale proof другой базы при совпадающих полях; удаление/повторное создание region; закрытие pin между вычислением и bind; GC/release перед prepare. Для каждого должно быть определено reuse либо refusal с основанием, а не общий запрет всех повторов. Проверка этого среза статическая; runtime тесты не проводились и код не менялся.

### Принятое направление metadata provenance после ревью

**Решение пользователя: «Зафиксируй это направление».** Выбрано направление дальнейшей конкретизации, исправляющее разрывы F1–F5:

1. Pack выполняет публичные write-операции в прежнем порядке и сохраняет проверяемую связь вычисленной metadata с реально использованными typed inputs, включая наследование из закреплённой базы и релевантные зависимости. DAG не повторяет merge/status/header расчёты.
2. Pack предоставляет typed metadata subject и необходимые зависимости как результат своего публичного контракта. DAG передаёт этот результат в согласованный контракт получения evidence. Source подтверждает исходные версии/тела/удержания в своей ответственности; правильность вычислений Pack не делегируется Source.
3. DAG передаёт evidence в отдельную публичную операцию Pack привязки provenance. Pack проверяет точный subject, базу и релевантные dependencies; одно совпадение значения или hash не доказывает происхождение. Вложенных вызовов публичных Source/Pack операций и скрытого orchestration pipeline нет.
4. Финальный prepare проверяет полноту provenance, согласованность состава/coverage, базу, доступность и удержание всего необходимого closure, затем завершает storage lifecycle до READY. Activate остаётся отдельным вызовом DAG.

Неизменные metadata и их proofs сохраняются; изменённая projection не получает старое свидетельство. Неполная промежуточная подготовка не публикуется. Случай A → B → A решается по semantic identity и зависимостям, не времени получения proof. Старая логика записей, settlement preserve, grade merge и status policy остаётся обязательной.

Это решение заменяет неопределённость выбора направления в предыдущем ревью, но **не отменяет отказ в приёмке прежнего неполного варианта**. Объявления write/output/subject/evidence/bind, representation связи результата с входами, lifetime удержаний и проверки F1–F5 ещё должны быть конкретизированы. Ранее предложенный PackMetadataProvenanceInput с одними entries не объявляется достаточным. Предварительные preview-вызовы перед каждой записью не выбраны как основной маршрут. Concrete source_proof остаётся задачей его владельца; новый command log, receipt store или зеркальный proof POJO этим решением не разрешаются. Runtime и ТЗ не изменены.

### Связь результата с входами: последовательные изменения одной projection

Продолжение принятого направления. Источники проверки: `worldPackWriter.publish_settlement_structure` читает prev из текущего manifest; `commit_chunk` заменяет адресованный chunk и пересчитывает status; `recalc_wilderness_status` возвращает прежний status без замены строки при равенстве; `planning/contracts/planDependency.py::require_canonical_dependencies` запрещает повтор slot.

**Уточнение preserve:** слова «сохраняется из базы» в описании settlement означают предыдущее состояние входа операции. Только у первого изменения оно совпадает с pinned base. При S0 → S1 → S2 операция над S1 не имеет права снова читать поля S0. Это уточнение прежнего writer, не изменение алгоритма.

Контрольный пример: S0 имеет packed=(A), status=partial. W1 записывает territory=T1, packed=(B), status=complete и возвращает S1. W2 записывает territory=T2, packed=None, status=None. Результат S2 обязан содержать T2, (B), complete. Metadata S2 зависит от нового territory W2 и сохранённых полей S1. Proof только W2 или только pinned S0 недостаточен. Даже если W2 заменил payload W1 по тому же адресу, итоговая metadata всё ещё может зависеть от результата W1. Это не основание удерживать заменённый payload автоматически: необходимый source/proof closure определяется конкретным provenance-контрактом.

| Часть результата | Обновление значения | Требуемая связь с входами |
|---|---|---|
| Settlement territory | Всегда значение текущего write | Основание territory текущего вызова; прежнее territory не считается использованным автоматически |
| Settlement packed/status при None | Из предыдущего state; при отсутствии записи — existing default | Связь сохранённого поля с его происхождением; не подмена текущим capture и не повторное чтение pinned базы |
| Settlement packed/status при explicit значении | Explicit значение, включая empty tuple/absent | Основание explicit input; равенство числа/строки прежнему значению само по себе не доказывает inheritance |
| Header grid/side/mode | Каждая операция меняет только свои поля | Основания незатронутых полей сохраняются. Последняя запись side заменяет основание side, а не происхождение всего header |
| Tile wilderness status | Existing policy по текущему chunk set и expected текущего вызова | При изменении status — связь с проверенными входами этого расчёта. Не подменять доказательство состава одним count. При existing early return неизменное значение не получает фиктивный новый расчёт/proof |
| Tile climate status / chunk refine_role | Existing fine update / значение роли, включая None | Раздельные tile/chunk projections; изменение chunk не переписывает происхождение остальных chunks или climate |

Из примера следует требование к будущему output/state: сохранять достаточную связь **используемых полей** с их основаниями до выпуска evidence. Одна метка «последний write», один общий current capture и один final value hash этого не обеспечивают. Полная история команд и копии всех промежуточных state не требуются. Это требование к данным, а не утверждение нового generic lineage POJO; конкретное представление должно пройти проверку отсутствия дублей с source/producer evidence.

**Ограничение типа Planning, а не установленная проблема Pack:** `PlanDependency(slot, ref)` и `require_canonical_dependencies` требуют уникальных slots в одном tuple и канонического UTF-8 порядка. Случай slot=X/ref=R1 и slot=X/ref=R2 для retained/new полей metadata рассматривался гипотетически. Реальные producer inputs, требующие такого сочетания в этой цепочке, не предъявлены. Поэтому этот пример не обосновывает новый составной provenance, переименование slots или изменение Planning-контракта.

### Отложенный вопрос PACK-METADATA-PLANNING — разрешённая заглушка проекта

**Решение пользователя: оставить заглушку на текущий момент и разрешить вопрос отдельно.** Заглушка обозначает только незавершённый mapping metadata → реальные Planning dependencies. Она не заменяет весь metadata provenance или concrete source_proof и не утверждает, что такие зависимости обязательно нужны каждому полю. Существующее проектное поле `PackStoredProvenance.planning: tuple[PlanDependency, ...]` этим решением не меняется.

**Последующее уточнение пользователя: это не блокировка текущего Pack.** PACK-METADATA-PLANNING является отложенным вопросом интеграции, а не обязательной предпосылкой разработки или приёмки текущего объёма Pack. Не возвращать его как причину остановки, не требовать полного разрешения связанного контракта до продолжения Pack и не расширять текущий объём всеми возникающими внешними вопросами. Это уточнение имеет приоритет над прежними формулировками о блокирующем gate именно этой зависимости. Отложенный вопрос не объявляется решённым.

До отдельной проверки не проектировать composition/lineage POJO ради гипотетического конфликта slots. Заглушка обозначена в проекте; фиктивный PlanRef и всегда успешная проверка не требуются. Конкретизация интеграции и её сквозные проверки выполняются отдельно, без повторного согласования отсрочки на каждом шаге текущего Pack.

Условие снятия заглушки: для settlement/header/tile status предъявить фактический producer output и используемые поля → определить, нужна ли прямая ссылка на доменный план или достаточно provenance готового результата → указать existing PlanDependency и mapping только там, где зависимость доказана. Если прямой зависимости нет, зафиксировать это с трассировкой входов. Проверку одинаковых slots с разными refs включать только при обнаружении реального такого маршрута. Concrete source_proof остаётся у другого агента, Planning и другие домены здесь не меняются.

Проверки будущего output: W1 explicit → W2 None сохраняет поля и основания W1; W1 → W2 explicit заменяет соответствующие поля без потери оснований остальных; equal explicit input не объявляется inherited только по value; header side A → B → A различает релевантные dependencies; одинаковый planning slot с разными refs не теряет ни одно нужное основание и не выдаёт незаконный tuple. Текущий return PackPreparationState без представления этих данных нельзя объявлять окончательным write-output. F1 конкретизирован примером и правилами переноса, но ещё не закрыт DTO/сквозной проверкой. Runtime не менялся.

### Текущий Pack: локальная идентификация metadata для привязки

PACK-METADATA-PLANNING остаётся неблокирующей заглушкой. Этот срез задаёт собственную ответственность Pack: выделить exact metadata subject и проверить соответствие предъявленного subject текущему состоянию. Он не выдаёт локальный fingerprint за proof происхождения и не закрывает внешнюю интеграцию фиктивными данными.

**Write-output:** публичные write-методы продолжают возвращать PackPreparationState. Отдельный PackWriteResult с копией state/metadata не добавляется. Промежуточные состояния и сам порядок записей остаются прежними; DAG не извлекает header поля и не вычисляет projection fingerprints.

**Публичное описание metadata:** предлагаемый метод того же `application/worldData/pack/preparation/packPreparationService.py::PackPreparationService.describe_metadata(self, request: PackMetadataSubjectsInput) -> tuple[PackMetadataSubject, ...]`. Input в `dataModel/worldPack/preparation/metadataSubject.py` содержит `state: PackPreparationState`, `addresses: tuple[PackAssemblyAddress, ...]`. Output record в том же модуле: `PackMetadataSubject(base_publication: WorldPublicationRef, address: PackAssemblyAddress, value_fingerprint: RevisionHex)`. Все records strict/frozen/extra-forbid/revalidate-always. Subject — идентичность значения для последующей привязки, не второе объявление metadata row, не durable proof, не receipt хранения и не capability.

Адреса выбирает caller из принятого маршрута; Pack выбирает значения и вычисляет их fingerprint. Метод pure: не меняет state, не читает latest/Source/storage, не вызывает другие публичные методы и не решает, запускать ли evidence/prepare. Дубликаты request.addresses дают DEPENDENCY_MISMATCH/DUPLICATE_ADDRESS с исходным индексом; отсутствующая projection — DEPENDENCY_MISMATCH/ADDRESS_MISMATCH. Независимые ошибки агрегируются существующим PackPreparationFailure/PackPreparationError. Пустой набор даёт пустой tuple; успешный результат соответствует порядку входных адресов. Это адреса для чтения, не список write-команд.

Один внутренний selector используется describe_metadata и проверкой bind. Он следует уже описанным projections в `rev-02-r1-public-pipelines.md`: header — last_l0_mode и пять effective scalars в зафиксированном порядке; tile — собственные gx/gy/status поля без chunks; chunk — cx/cy/refine_role адресованного chunk; location/settlement/region — полная owning row. Значения не переписываются в новые DTO. Fingerprint строится existing canonical codec/content digest по типизированному адресу и projection в зарегистрированном Pack schema binding; Python repr, JSON key order и новый hash engine не используются. Schema binding должен оставаться тем же между describe и bind; его регистрация — часть Pack реализации, не настройка DAG.

**Вход привязки уточняется локально:** `PackMetadataProofBinding(subject: PackMetadataSubject, provenance: PackPartProvenance)` в `preparation/metadataSubject.py`; `PackMetadataProvenanceInput(state: PackPreparationState, entries: tuple[PackMetadataProofBinding, ...])` в `preparation/operations.py`. Прежнее предложение entries из одного PackAssemblyProvenanceEntry заменяется этим record для привязки: address расположен только в subject, provenance — только в binding. Stored schema сохраняет existing PackStoredAssemblyProvenance; subject не записывается в manifest как второй provenance.

Локальная проверка bind: повторно проверить input → проверить уникальность subject.address → сопоставить subject.base_publication с state.base_publication → найти текущую projection → пересчитать fingerprint тем же selector/codec → проверить равенство. Чужая база даёт BASE_PUBLICATION_MISMATCH, отсутствующий адрес — ADDRESS_MISMATCH, несовпадающее значение — SOURCE_PROOF_MISMATCH. Затем выполняется согласованный admission самого provenance; локальная проверка subject его не заменяет. Только после успешной проверки всего вызова возвращается новое immutable state; assembly и parts не меняются. Недостающий внешний evidence не подменяется successful subject comparison. Вопрос Planning не возвращается в качестве блокировки текущей локальной работы.

**Предел гарантии:** S1.subject, применённый к S2 с другой metadata или базой, отклоняется. При A → B → A с той же базой локальная проверка может пройти; допустимость proof определяется provenance admission, а не счётчиком состояния или временем вызова. Изменение unrelated row само по себе не делает subject устаревшим. Subject не доказывает, что поле было вычислено из конкретного source/plan: это сохранённая граница отложенной интеграции, а не дополнительное обещание данного метода.

Приёмка локального среза: describe не мутирует state; header/tile projections не захватывают соседние коллекции; изменение адресованного значения меняет fingerprint; другой адрес с теми же скалярами не смешивается; несовпадение базы выявляется независимо от fingerprint; missing/duplicate адреса агрегируются; bind не меняет payload/metadata и не применяет часть entries после отказа; совпадающий subject не принимается за достаточный durable proof. Это проект конкретных сигнатур и проверок, runtime ещё не реализован.

### Текущий Pack: локальная проверка coverage

Следующий срез рабочего списка. Переиспользуются проектные PackWildernessCoverage, PackChunkCoverageEntry, PackChunkMaterialized, PackChunkWithoutPayload и PackSettlementCoverage из `preparation/coverage.py`; второй CoverageSnapshot и новый универсальный result не вводятся. Формат producer evidence уточняется отдельно. Этот раздел конкретизирует собственные проверки Pack, не расширяя scope до реализации producers или Planning.

**Ответственность:** внутренний `PackPreparationValidator.validate_coverage(self, body: PackPreparationBody) -> None` выполняет pure проверки уже переданных значений. Отказ — existing проект PackPreparationFailure с PackPreparationError/PackPreparationIssue. Метод не читает bytes/storage, не вызывает producer, не рассчитывает expected геометрию/census, не пишет metadata и не выбирает следующий публичный вызов. Проверка фактических payload остаётся у принятого внутреннего format binding, проверка происхождения — у evidence admission. Успешный возврат этого метода означает локальную согласованность coverage, не READY и не доказательство выполнения producer.

| Проверка | Правило и отказ |
|---|---|
| Expected wilderness | Уникальные полные PackChunkAddress внутри одного coverage record; DUPLICATE_ADDRESS на повторном элементе. Expected не строится из completed |
| Completed wilderness | Уникальные addresses внутри record; каждый принадлежит expected. Вне expected — ADDRESS_MISMATCH. Равные counts при разных адресах не означают равенство множеств |
| Materialized outputs | Непустой tuple, без повторов внутри одной записи; каждый адрес разрешается в конечном state.parts. Missing — MISSING_PART, повтор — DUPLICATE_ADDRESS. Связь именно с конечными ref/provenance отдельно проверяет evidence admission |
| Общий output у нескольких областей | Допустим: один location terrain artifact может объединять несколько областей. Нельзя применять global uniqueness к outputs всех completed entries |
| Without payload | Completed факт без искусственного ArtifactRef. Не удаляет part базы и не требует отсутствия part по этому адресу в итоговом state |
| Неполная обработка | completed ⊂ expected не превращается автоматически в ошибку или complete. Допуск результата определяется существующим scope/принятым режимом полноты; не вводить общее требование completed=expected для всех операций |
| Settlement | Уникальные expected_districts и packed_districts, packed ⊆ expected; неверный UID — ADDRESS_MISMATCH. Полный census не восстанавливается из числа районов |
| Settlement и итоговая запись | Сопоставлять coverage с конкретной location и итоговым результатом, который оно удостоверяет. None update не обнуляет packed/status; несовпадение не исправляется изменением metadata или расширением census |
| L0 | expected_tiles берётся из PackL0PreparationScope, без второго списка expected. Наличие inherited tile не удостоверяет новый bake |
| Изменения вне scope | Проверяются по итоговому составу относительно базы; OUT_OF_SCOPE_CHANGE. Наличие coverage произвольного адреса само по себе не расширяет scope |

Проверки уникальности выполняются до преобразования tuple в set и canonical сортировки. Ошибки сохраняют исходные индексы входа. Сначала проверяются независимые shape/address/set relations; проверки, требующие отсутствующего part, пропускаются только для этого part. В конце этапа выбрасывается один агрегированный отказ, без изменения state. Неизвестный/недоступный external proof не обозначается успешным локальным результатом проверки происхождения.

**Сохранение status policy.** Existing `wildernessRefineStatus.py` использует число сохранённых chunks: при нуле — absent; без expected при положительном числе — partial; с expected>0 и baked>=expected — complete, иначе partial. Это не формула completed/expected из coverage. После chunk write действует прежний provisional пересчёт; отдельный final пересчёт выполняется только при соответствующем вызове DAG. `validate_coverage` не пересчитывает status и не вставляет такой вызов. Не вводится новый запрет expected_chunks<=0: old policy эти значения обрабатывает.

**Повторные записи:** локальные проверки выполняются для каждого переданного record; несколько последовательных результатов одной области нельзя автоматически объединять по union или выбирать по времени. Evidence R1 с logical output A не подтверждает конечный A/ref_R2. При этом ref_R1 не возвращается в manifest ради прохождения проверки. Связь нескольких результатов с окончательным составом относится к конкретной интеграции, а не новому алгоритму merge в валидаторе.

Локальные контрольные случаи: expected={A,B}, completed={A,C} — отказ несмотря на равные counts; два completed используют один location output — допустимо; without_payload при retained базовом chunk — допустимо; все expected обработаны без нового payload при пустой базе — coverage может быть полным, wilderness status остаётся absent; положительное baked при отсутствии final пересчёта остаётся partial; subset completed не отклоняется без требования полноты данного scope; missing output даёт отказ без частичной правки state. Для этих случаев не требуется расширять контракт Planning. Это требования к локальной реализации, не отчёт о выполненных runtime тестах.

### Текущий Pack: подготовка, удержания и повторный вызов

Сверены existing `IArtifactStaging`, `SqliteArtifactLeases` в leaseStore.py, `SqliteArtifactCatalog._lease`, `OperationRecord`, `finish_pack_preparation`. Переиспользуются OperationKind.PACK_ACTIVATION, OperationLeaseRef, OperationRecord и PreparedPackCandidate. Новые Pack holder store, operation ledger и state machine не вводятся. Это конкретизация Pack-owned использования lifecycle, не изменение Artifacts.

**Подтверждённые механизмы:** open_operation связывает operation_id/world/kind/preparation_fingerprint и проверяет lease identity; finish_preparation требует открытого writer admission, отсутствия активных writers, sealed refs и точного равенства refs всем operation holds. Затем он закрывает admission и фиксирует READY. recover читает record, но при APPLYING/RECOVERY_REQUIRED возвращает OperationBusyError: это не универсальная команда устранить неизвестный исход. Existing finish_pack_preparation проверяет digest/nbytes manifest и возвращённые phase/identity/fence/live-set; он не реализует полный повтор prepare или весь новый metadata/source admission.

**Порядок внутренней реализации PackPreparationOperation:** strict input/локальные проверки и fingerprint полного semantic body → admission durable operation identity и текущей phase → для новой/продолжаемой подготовки verified base/refs и нужные удержания → полная проверка состава, payload и provenance → assembler конечного manifest → canonical encode и byte budget → stage/seal manifest → exact finish_preparation → PreparedPackCandidate. Эти действия принадлежат одной операции подготовки, не являются вызовами публичных write/Source/activate. Повтор READY имеет отдельный локальный путь восстановления результата без staging, описанный ниже.

Fingerprint вычисляется по содержимому запроса, не доверяется caller-строке. Operation_id не входит в собственный digest. При том же ID с другим body/world/kind — identity conflict до нового staging. Нельзя на каждый retry выдавать новый ID, перезапускать write-операции или читать latest World. Внутренние lease/fence не выходят в публичный input.

| Durable состояние | Допустимое поведение Pack |
|---|---|
| Операции ещё нет | После локального admission открыть existing operation и продолжить подготовку; active head не меняется |
| PREPARING с той же identity | Продолжение только по existing admission/fence и проверенному содержимому; активный writer/конкурентное владение не обходится. Отсутствие public retry loop сохраняется |
| READY с той же identity | Проверить и восстановить тот же candidate без reserve/stage/finish_preparation: writer admission уже закрыт. Повторная запись через existing finish helper ошибочна |
| APPLYING или RECOVERY_REQUIRED | Сохранить owning busy/unknown-outcome поведение. Не reopen, не создавать второй candidate, не запускать recovery/publication самостоятельно |
| TERMINAL | Не возвращать PREPARING и не восстанавливать holds автоматически. Исторический activation replay относится к activate; cancel и release — отдельные операции. Терминальный исход не считать свидетельством доступности candidate |

Для READY replay одного record.phase недостаточно. Проверяются identity и точный manifest ref, его descriptor/digest, доступность под соответствующим hold и полный ожидаемый live-set. В OperationRecord нет отдельного поля manifest ref; нельзя выбирать первый artifact подходящего format из leased_artifacts. Связь с candidate должна быть однозначно восстановлена через принятый manifest encoding/identity binding и проверенные данные подготовки. Не вводить отдельный candidate store лишь ради этого пробела. Утверждение о готовом replay до реализации этой проверки запрещено; успешный replay не продлевает владение неявно.

**Единственный retention set Pack:** manifest ref + refs всех итоговых parts + transitive refs зарегистрированных payload formats + необходимые durable source/provenance refs всех parts и metadata. На storage-уровне одинаковые refs дедуплицируются; разные logical addresses/provenance остаются разными записями manifest. Весь набор передаётся finish_preparation и используется при publication handoff/read reachability. Extra operation hold тоже нарушает exact equality: его нельзя игнорировать или удалять вручную в Pack ради прохождения проверки.

**База и adoption:** start_from_base удостоверяет чтение в момент start, но не удержание на весь последующий prepare. До чтения/передачи inherited refs требуется действующее принятое удержание. Проверка source holder, seal и получение владения target operation должны использовать согласованный внутренний atomic binding владельца Artifacts, без незащищённого промежутка «проверили — source release/GC — приобрели». `holders.acquire` сам по себе не доказывает producer provenance и не объявляется готовым atomic adoption. Pack вычисляет требуемый набор и проверяет результат binding; не копирует чужие SQL/GC правила. Это интеграционная обязанность, отдельная от текущего Pack-контракта; её неизвестные детали не заполняются заглушкой, всегда возвращающей успех.

**Отказ и cleanup:** local invalid input не начинает staging. После начала IO ошибка не выдаёт candidate и не разрешает опубликовать частичный состав. Нельзя обещать отсутствие ранее записанных staged bytes: их cleanup принадлежит existing lifecycle. Cancel/error не освобождают чужие base/source holds. Если READY мог быть зафиксирован, но ответ потерян, результат выясняется по durable identity; слепой cancel/повтор finish запрещён. Infrastructure failure и cancellation не маскируются как INVALID_INPUT.

READY_INACTIVE retention и release не проектируются заново: [existing trace](pack-inactive-retention-trace.md) и [публичный проект release](pack-candidate-release-contract.md) уже отделяют root OperationHolder от общих child retention links. Terminal не означает автоматическое освобождение manifest; cancel не является release неактивного кандидата. Новая подготовка не получает права снять удержание другого кандидата того же manifest.

Приёмка Pack-части: same ID/different body не создаёт новый staging; lost READY response возвращает тот же candidate без finish повторно; READY replay не принимает посторонний manifest того же format; missing/extra ref отклоняются до candidate; активный writer препятствует finish; закрытие base pin не подменяется чтением latest; missing transitive child не скрывается root hold; при late failure head неизменен; повтор после release не восстанавливает владение. Existing lifecycle source проверен статически, эти сценарии здесь не запускались. Planning остаётся неблокирующей отложенной темой.

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
| Spatial root | В V1 writer самостоятельного метода нет. [Проект write_spatial_root](pack-spatial-root-write-contract.md) задаёт один pure add/replace готового root-part по domain; это конкретизация целевого parts-контракта, не заявление legacy parity. Hydrology не запускается; semantic decode/closure — final admission |

Завершающий `PackPreparationPipelineOpenPipeline.prepare(request: PackPreparationInput) -> PreparedPackCandidate` принимает конечный state и identity/fingerprint/capture/scope по объявленной выше форме; не список команд. Схема оболочки согласована с ТЗ. Открыты concrete внешние capture/proof/coverage bindings; их отсутствие не означает альтернативную старую форму body. Encoding/identity/recovery принимаются отдельным планом. Сигнатура release уже консолидирована; existing candidate/activation POJO переиспользуются.

## Повторные адреса и порядок

[Трассировка старых маршрутов и условий](pack-write-order-trace.md) конкретизирует этот раздел: batch/single L0 различаются; detailed имеет общий parent-light barrier и per-tile final status; параллельный legacy callback сериализует записи по готовности, а не по возвращаемому ordered списку. Согласованный DAG binding обязан учитывать эти факты без неявной сортировки и перестановки стадий.

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
| Manifest превышает budget | MANIFEST_OVERSIZE; issues=() допустим по решению 2026-11-13 | Производный результат без фиктивного пути поля; явный отказ независимо от пустого collector, без staging/READY на этапе предварительного byte-budget контроля |

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

**Условия начала конкретного implementation-среза.** Использовать [единую последовательность поставки](world-pack-v2-single-manifest-contract.md#единая-таблица-зависимостей-и-завершения-шагов). Header initialization, spatial update, preparation error union, metadata describe/bind и release уже конкретизированы в профильных разделах; settings исключения для CachePolicy/manifest_max_bytes приняты. Их нельзя повторно объявлять отсутствующими по старому общему списку OPEN. До реализации выбранного среза проверить его конкретные Input/Output/Error, owning данные и все обязательные критерии; отсутствие внешнего binding блокирует зависимый маршрут, а не остальные операции. State/start transport bound не заменяется manifest byte cap. Scoped lifecycle остаётся интеграционной зависимостью; encoding/recovery — отдельный план. Production callers/DAG cutover и доказательства runtime выполняются после соответствующей реализации, не выдаются за уже пройденную приёмку проекта. Кодовые правки требуют implement-plan.

## Проверка внутренней согласованности проекта (2026-11-12)

### Стоимость последовательных writes — отдельная проверка масштабирования

Замечание P2 подтверждено на уровне алгоритмического риска, не runtime benchmark. Каждый вызов принимает/возвращает полный immutable state и повторно проверяет вложения/уникальность. Для N добавлений полный обход растущего состава даёт суммарно Θ(N²) посещений элементов. Для N=16384 сумма размеров 1…N равна 134225920; повторные посещения ранее добавленных элементов — N(N−1)/2 = 134209536. Это оценка одного полного прохода по parts; admission входа/выхода, metadata/proofs, копирование tuple, describe/bind и транспорт могут добавить работу. Оптимизация только поиска адреса не устраняет эту стоимость.

До приёмки реализации **массовой последовательной записи** выполнить масштабный эксперимент на 1000 / 4000 / 16000 частей с настоящими owning POJO и тем же маршрутом validation/update, который будет поставляться. Это подготовительная проверка реализации выбранного среза, не разрешение реализовать неподтверждённые внешние контракты или подменить их успешными mocks. Пока конкретные типы/путь не готовы, измерение отмечается невыполненным; проверка одной формулы или упрощённого dict не закрывает его.

| Сценарий | Что измерять |
|---|---|
| N последовательных добавлений разных адресов | Полное время цепочки; отдельно input/output admission, uniqueness, изменение коллекций и metadata. Считать посещения ранее существующих записей и объём копирования |
| N замен в уже заполненном state размера N | Те же показатели при постоянном размере, чтобы не спрятать полный обход в replacement |
| Actual DAG transport | Serialized bytes/время транспорта, если сериализация действительно есть; при in-memory передаче — ссылки и удержание старых states. Не добавлять искусственную сериализацию для benchmark |
| Используемые describe/bind/final admission | Стоимость по реальному числу и порядку вызовов, не только изолированный lookup/write. Отдельно peak memory и количество одновременно живых states |

Данные воспроизводимы: одинаковая форма и ограниченная сопоставимая сложность одной части/proof на всех размерах, адреса различаются; указать runtime/hardware, состав данных, warm-up и несколько повторов с медианой/разбросом. Payload bytes не добавлять в state. Дополнительно проверить представительный тяжёлый provenance, когда owning тип доступен. Не сохранять всю историю states в harness, если production её не удерживает; если удерживает — измерить этот режим отдельно.

При росте N в 4 раза линейная работа растёт примерно в 4 раза, квадратичная — в 16. Вывод делать по счётчикам операций и времени вместе, с учётом шума/GC; фиксированного секундного порога без продуктового бюджета не назначать. Отчёт должен показывать total и стоимость на один update, а не только время последнего вызова. При подтверждённом квадратичном росте массовый путь не принимается без отдельно согласованного решения о приемлемости стоимости либо изменении механизма.

Возможные направления для согласования после измерений — пакетная передача или инкрементальная проверка/структурное разделение данных. Ни одно здесь не выбрано. Batch не разрешает внутренний dispatcher произвольных writes или перестановку DAG-порядка; incremental admission не разрешает доверять forged/mutable вложениям, выключить revalidation или принять полный state без доказанной границы доверия. Immutable tuple copying тоже должно попасть в оценку, даже если validation оптимизирована.

До изменения механизма действуют текущие strict/immutable/uniqueness требования каждого вызова. Альтернативный API, session store, скрытый mutable builder и публичный callback не вводятся этим замечанием. [Transport/size checks](pack-budget-enforcement.md#промежуточный-state) остаются отдельными: приемлемый размер state не доказывает приемлемую суммарную стоимость updates. Результат benchmark — обязательное свидетельство соответствующего массового implementation-среза; measurements в этой документационной правке не выполнялись.

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
