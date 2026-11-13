# Pack metadata dependency POJO: проект конкретного обмена

Дата: 2026-11-13. Статус: POJO PROPOSAL после согласования [трёх семантических решений](pack-metadata-dependency-usage.md#согласованные-решения-пользователя). Только документация. Имена новых типов ниже — кандидаты, не runtime imports. Новые signatures и persisted schema требуют проверки по правилам проекта; готовность внешних типов не предполагается.

## 1. Единственные объявления и внешние типы

**Последующее решение пользователя: прямые междоменные вызовы запрещены без исключения для pure helper.** Ниже предложенные способы вызвать Source pure extraction/matching из Pack отозваны в части маршрута вызова. Они не разрешают реализацию Pack → SourceProofValues. Актуальное [сопоставление через DAG](gen-dag-cache-pack-source-families.md#67-source--dag--pack-сопоставление-данных-после-уточнения-contracts) указывает необходимые Source results и незавершённые входы Pack; новый порядок ещё не назначен. Формы attribution/basis этим решением не отменяются.

Существующие проектные PackAssemblyAddress, PackMetadataSubject, PackStoredProvenance, PackPartProvenance, PackStoredAssemblyProvenance переиспользуются. Значения metadata остаются в PackAssemblyInput, их второй DTO не создаётся. SourceDurableProof остаётся единственным owning proof; Planning остаётся в PackStoredProvenance.planning.

Владелец предъявил типы в [Source §6.0.A–G](source-proof-v2-contract-spec.md): SourceProofInput для usage, SourceProofResult для admission/closure и SourceProofSelection для subset. Ниже используются эти owning типы; прежние SourceDependencyUsage/SourceDependencyAdmission не создавать как aliases. SourceProofResult сам по себе не является свидетельством доверенного исполнения проверки. Selection выбирает atoms данного общего proof, а не body positions внутри capture. Внешняя schema остаётся PROJECT до owning приёмки.

## 2. Поля Pack POJO

Предлагаемые модули: `dataModel/worldPack/preparation/metadataDependencies.py` для transient records, `dataModel/worldPack/meta/metadataAttribution.py` для durable mapping. Модели strict/frozen/extra-forbid/revalidate-always; вложения immutable; обязательные поля без скрытых defaults. Нет dict/Any, reader, lease, callback, receipt store или счётчика версии state.

| Модель | Все предлагаемые поля | Ответственность |
|---|---|---|
| PackMetadataDependencyUse | group: PackMetadataGroup; source_usage: SourceProofInput; basis: PackWildernessStatusBasis либо None | Source-зависимости группы и отдельное Pack-owned основание расчёта. Нет копии значения metadata |
| PackMetadataDescription | subject: PackMetadataSubject; dependencies: tuple[PackMetadataDependencyUse, ...] | Связанный subject и полный ожидаемый usage его групп |
| PackMetadataInputEvidence | input: PackMetadataInputSelector; value_fingerprint: RevisionHex; source_usage: SourceProofInput | Связь конкретного поля текущего typed write input с producer usage; fingerprint вычисляет producer/Pack owning binding, не DAG |
| PackMetadataGroupAdmission | group: PackMetadataGroup; selection: SourceProofSelection; basis: PackWildernessStatusBasis либо None | Соответствие группы subset единственного row proof и проверенное Pack основание. Одна декларация для bind/durable attribution |
| PackMetadataProofBinding, уточнение | subject: PackMetadataSubject; provenance: PackPartProvenance; source_request: SourceProofGroupsInput; source_result: SourceProofGroupsResult; groups: tuple[PackMetadataGroupAdmission, ...] | Единственная текущая проектная форма из pack-source-exchange-contract.md. Proof в provenance равен source_result.admission.proof; source_admission как отдельное поле удалено из проекта, alias/dual-input не допускается. Execution binding требует приёмки |
| PackMetadataAttribution | groups: tuple[PackMetadataGroupAdmission, ...] | Durable выборка по группам относительно source_proof содержащего record; не самостоятельное хранилище proof |
| PackStoredAssemblyProvenance, уточнение | address: PackAssemblyAddress; provenance: PackStoredProvenance; attribution: PackMetadataAttribution либо None | Один общий row proof, одна карта subset. None допустим только для доказанно неизменного старого whole-row provenance, не для новой/пересчитанной строки |

`PackWildernessStatusBasis` объявляется единожды в `dataModel/worldPack/meta/metadataAttribution.py`: `chunk_addresses: tuple[PackChunkAddress, ...]`, `expected_chunks: StrictInt | None`. Подробные [правила размещения и bind](pack-wilderness-status-dependencies.md#точное-размещение-и-проверка-basis). Поле basis обязательно предъявлено, но nullable: для WILDERNESS_REFINE_STATUS detailed record оно non-null, для остальных текущих groups — строго None. Это конкретное дополнение текущего проекта, не универсальный payload для произвольных алгоритмов; оно пока не принято как runtime schema.

**State:** к принятым base_publication/parts/assembly/assembly_provenance предлагается добавить `metadata_dependencies: tuple[PackMetadataDescription, ...]`. Это один transient носитель; отдельный PackMetadataDependencyState с теми же записями не нужен. Subject fingerprint и value хранятся не дважды: значение только в assembly, subject лишь идентифицирует его. Для изменяемой projection карта содержит usage всех групп, включая переносимые; старый whole-row record без детализации не получает выдуманную запись.

Для unchanged rows после bind сохраняется durable attribution; соответствующая transient запись удаляется. Предложение получать dependencies subsets прямым Source helper внутри следующего Pack write отозвано. Для следующего partial write требуется переданный через DAG результат owning select; точное поле его входа ещё не принято. Поэтому текущие POJO не объявляют этот путь завершённым. Pending partial writes используют актуальную transient карту, не pinned A повторно; Pack не интерпретирует Source indices.

**Write inputs:** `metadata_inputs: tuple[PackMetadataInputEvidence, ...]` предлагается только тем конкретным inputs, которые получают влияющие на metadata значения. Он описывает исходные поля, а не proof результата. Разрешённый набор input selectors зависит от конкретного метода (§3). None-preserve не требует evidence нового значения; explicit empty требует. Для initial assembly требуются основания каждого initial scalar. Связь payload/address/membership evidence с конкретным producer output не заменяется независимым caller tuple.

## 3. Typed groups и предел точности

PackMetadataGroup — закрытый enum, допустимость значения проверяется по виду PackAssemblyAddress. Typed selectors реализации используют существующие owning field definitions; свободные строки путей запрещены.

| Address kind | Предлагаемые группы |
|---|---|
| header | LAST_L0_MODE, FINE_CELLS_PER_MAP_CELL, WORLD_MAP_CELLS_PER_TILE, FINE_CELL_SIZE, MAP_SUBSURFACE_DEPTH, TERRAIN_CHUNK_COLUMNS — каждый scalar отдельно |
| tile | IDENTITY (gx/gy), CLIMATE_STATUS, WILDERNESS_REFINE_STATUS |
| chunk | IDENTITY (cx/cy внутри адресованного tile), REFINE_ROLE |
| settlement | IDENTITY (location_uid), TERRITORY_VOLUME, PACKED_DISTRICT_UIDS, STRUCTURE_STATUS |
| location | IDENTITY (location_uid), TERRITORY_VOLUME, CLIMATE_STATUS |
| region | IDENTITY (region_uid), ENTRY_TYPE, CURRENT_TYPE, BBOX, REGION_STATUS, PARENT_REGION_UID, SPEC_FINGERPRINT |

Реестр покрывает все поля целевых assembly rows из [Pack §6.4](pack-v2-domain-contract-spec.md) и existing [WildernessRegionEntry](../../backend/app/dataModel/worldPack/meta/wildernessRegionEntry.py). TerritoryVolume и RegionIndexBounds пока являются едиными значениями: отдельные координаты внутри них write не сохраняет/изменяет частично. Если такая операция появится, её зависимости и детализацию нужно проверить отдельно. Chunks не входят в tile projection, а path/hash/bytes/z_band отсутствуют в целевых location/settlement rows и поэтому не получают metadata groups.

IDENTITY usage связывается с основанием создания/сохранения адреса; повтор координат в transient payload не добавляется. Pack constant/rule с отсутствием Source reads требует owning допустимого empty usage и проверки правила, а не отсутствующей обязательной записи. WHOLE_ROW и OTHER в предлагаемом enum отсутствуют. Даже при полной замене строки её поля получают отдельные группы; одинаковые subsets допустимы, одинаковые group keys — нет.

### Typed selectors входов и roster операций

PackMetadataInputSelector предлагается как discriminated union двух named POJO: PackMetadataValueInputSelector(kind=VALUE, field: PackMetadataInputField) и PackMetadataRegionInputSelector(kind=REGION_ENTRY, entry_index: strict nonnegative int, field: PackRegionMetadataInputField). Первое enum содержит ADDRESS, FINE_CELLS_PER_MAP_CELL, WORLD_MAP_CELLS_PER_TILE, FINE_CELL_SIZE, MAP_SUBSURFACE_DEPTH, TERRAIN_CHUNK_COLUMNS, MODE, EFFECTIVE_SIDE, REFINE_ROLE, TERRITORY_VOLUME, PACKED_DISTRICT_UIDS, STRUCTURE_STATUS, EXPECTED_CHUNKS. Второе содержит REGION_UID, ENTRY_TYPE, CURRENT_TYPE, BBOX, STATUS, PARENT_REGION_UID, SPEC_FINGERPRINT. Enum kind хранит стабильный discriminator; произвольные строки и пути не вводятся.

Selector — семантический slot в конкретном named Input, не универсальный wire-field path. Связь с фактическим FieldRef/CheckedPath фиксирует owning метод. ADDRESS выбирает уже существующий request.address либо request.part.address; он не дублирует координаты. Для region entry_index выбирает исходный entries[i] до сортировки и проверяется на bounds. Он transient: durable attribution адресуется region_uid, не позицией в tuple. Canonical fingerprint использует выбранное typed значение и зарегистрированную identity selector, а не repr. Это также исправляет неоднозначность прежнего одного input_field для нескольких region rows.

| Операция | Разрешённые новые value evidence slots | Перенос / собственный расчёт Pack |
|---|---|---|
| start_empty | Шесть initial header scalars: MODE и пять scalar slots | Начальный header; пустые collections не создают fictitious row usages |
| start_from_base | Нет новых metadata_inputs | Exact pinned values/provenance/attribution; old whole-row режим отдельно |
| sync_grid_metadata | FINE_CELLS_PER_MAP_CELL, WORLD_MAP_CELLS_PER_TILE | Остальные header groups сохраняются |
| set_last_l0_mode | MODE | Остальной header сохраняется |
| write_map_tile | ADDRESS, EFFECTIVE_SIDE | Side header; существующие tile statuses сохраняются, новая tile identity/defaults — по owning правилам |
| write_wilderness_chunk | ADDRESS, REFINE_ROLE, включая None как значение | Новый chunk и provisional status; текущий состав/его изменение учитывает Pack |
| write_location_terrain | ADDRESS, TERRITORY_VOLUME | Новая row; climate coarse по owning правилу, не inherited status |
| write_settlement_structure | ADDRESS, TERRITORY_VOLUME; PACKED_DISTRICT_UIDS/STRUCTURE_STATUS только при explicit значении | None переносит соответствующую группу текущего state; без прежней строки применяется owning default |
| write_fine_climate | ADDRESS | Fine status по принятому правилу; wilderness group сохраняется |
| replace_region_index | Все семь field slots для каждого entries[i], включая явные nullable значения | Validate/replacement; удалённые строки исчезают, новые получают отдельные groups |
| recalculate_wilderness_status | ADDRESS; EXPECTED_CHUNKS только при int | None — explicit provisional policy; membership основания берутся из Pack state, не из payload content proof |
| delete_wilderness_chunk / delete_fine_climate | ADDRESS для запрошенного изменения | Пересчёт/переход статуса и сохранение соседних groups; absent no-op не создаёт новый metadata proof |
| write_coarse_climate, replace_locations_index, обе grade writes, write_spatial_root, delete_part | Нет новых metadata_inputs | Assembly не изменяется; payload provenance проверяется отдельно |
| delete_location_terrain / delete_settlement_structure | Нет metadata_inputs для удаляемой строки | Удаляются row/proof/usage целиком, новых projection не вычисляется |

Это roster для предлагаемого metadata evidence input, а не новая семантика write. Evidence ADDRESS для existing identity может быть проверено через existing part/producer binding; не требовать независимой копии Source proof, если owning result уже предъявляет точный subset. Если input содержит slot сверх разрешённого набора или отсутствует обязательный — отказ. Fingerprint nullable значения не следует путать с отсутствием evidence.

Основание текущего chunk membership нельзя заменить usage содержимого всех payload. [Трассировка status dependencies](pack-wilderness-status-dependencies.md) разделяет Pack-owned structural basis и Source usage; предлагает PackWildernessStatusBasis как снимок inputs последнего вычисления, не receipt. Его embedding и owning usage mapping ещё требуют приёмки.

**Уточнение ADDRESS slots таблицы:** slot разрешён для evidence source-derived identity, но не требует фиктивного Source proof от каждого command address. Для delete/recalculate адрес выбирает Pack объект; операция сама по себе не означает Source read. Конкретный producer binding определяет, требуется ли Source usage для address. Scope authorization не заменяется этим evidence. SOURCE usage и Pack structural basis не смешиваются; поэтому отсутствие внешнего evidence не закрывается пустым usage по умолчанию.

## 4. Mapping и новые сигнатуры

Кандидат сигнатуры: `describe_metadata(PackMetadataSubjectsInput) -> tuple[PackMetadataDescription, ...]`. Request сохраняет state/addresses. Write по-прежнему возвращает PackPreparationState; bind по-прежнему принимает state/entries и возвращает state, но entries используют уточнённый PackMetadataProofBinding. Новый PackWriteResult не вводится.

1. Pack write проверяет typed inputs/evidence, вычисляет projection и переносит/заменяет usage групп атомарно в новом immutable state. Старый state не изменяется при отказе. Внутренняя проверка inputs не является вызовом другой публичной операции.
2. Describe возвращает текущий subject и готовые usages из transient карты. Для detailed durable projection без готового usage требуется Source extraction через DAG и ещё не принятый Pack input/output mapping; прямой pure helper не допускается. Для старой whole-row projection не выдаётся fabricated group map: unchanged inheritance использует существующий путь переноса полного provenance, запрос точной детализации отклоняется.
3. DAG передаёт usages через SourceProofGroupsInput.groups в admit_groups и получает SourceProofGroupsResult. Source §6.0.G гарантирует корреляцию selections с исходным порядком groups и exact union; Pack group enum/subject туда не передаются. DAG механически соединяет результаты с исходными group keys, не вычисляя union/subset. Owning POJO предъявлены как PROJECT; exact DAG binding и приёмка остаются отдельно.
4. DAG переносит exact SourceProofGroupsInput в source_request и полный SourceProofGroupsResult в source_result, proof из result.admission — в общий provenance; возвращает исходный subject и group selections. Planning не вычисляется из Source result; применяется ранее согласованный отдельный binding.
5. Bind проверяет exact subject, basis, полный набор groups и equality общего proof/admission. Owning проверка эквивалентности selections ожидаемому usage выполняется Source через DAG, не Pack helper; как результат проверки связывается с exact request и допускается Pack, ещё требует принятого binding. После всех подтверждённых проверок сохраняется общий provenance/attribution; промежуточные usage не пишутся вторым proof в manifest.
6. Final prepare проверяет полный состав, detailed records новых строк и разрешённое exact inheritance старых. Closure собирается по общим owning proofs; group selections не разрешают исключить refs, необходимые owning proof format. READY/holds проверяются отдельно.

## 5. Admission, ошибки и старая база

| Случай | Обязательное поведение |
|---|---|
| Missing/extra/duplicate group; group несовместима с address | Отказ с адресом/полем и индексом; без частичного bind |
| Изменены projection/base или usage при том же значении | Отказ stale/mismatched binding; одного subject hash недостаточно |
| Source result для другого usage/proof/мира; неверный subset | Owning admission failure, переведённый согласованным Pack diagnostic mapping |
| Evidence поля не соответствует typed input или отсутствует | Отказ до вычисления зависимого результата; независимые ошибки агрегируются |
| Старая строка без attribution, без изменения | Разрешены read и exact inherited перенос полного прежнего provenance |
| Partial update старой строки требует неизвестных dependencies сохранённых полей | Отказ до потери старого record. Не подставлять whole-row proof вместо subset |
| Полная замена старой строки | Разрешена при evidence всех требуемых новых inputs; результат получает detailed attribution. Новые inputs не должны скрыто зависеть от неизвестного старого значения |
| Caller подделал state или successful Source DTO | Structural consistency не является доказательством; требуется принятая producer/owning boundary. Без неё semantic acceptance не объявляется |

### Конкретизация диагностик после сверки текущего проекта

Используется согласованный [PackPreparationDiagnostic union](pack-preparation-issue-union.md), FieldPathError/typed selectors и ValidatorAggregationHelper. Runtime PackPreparationIssueCode ещё не найден; существующие ниже означают объявленные проектом коды, не готовый Python enum.

| Нарушение | Reason / code | Path относительно named request |
|---|---|---|
| Extra key / неверный тип или enum selector | INVALID_INPUT / owning WireShapeIssue либо JsonFieldError | Existing structural adapter path; не зеркальная Pack ошибка |
| Чужая база / значение subject изменилось | DEPENDENCY_MISMATCH / BASE_PUBLICATION_MISMATCH либо SOURCE_PROOF_MISMATCH | entries[i].subject.base_publication либо value_fingerprint |
| Subject address отсутствует / повторяется | DEPENDENCY_MISMATCH / ADDRESS_MISMATCH либо DUPLICATE_ADDRESS | entries[i].subject.address |
| Missing final row proof | DEPENDENCY_MISMATCH / METADATA_PROOF_MISSING | state.assembly_provenance (с body prefix только в final prepare) |
| Proof/admission или ожидаемый usage не совпадают | DEPENDENCY_MISMATCH / SOURCE_PROOF_MISMATCH | entries[i].source_request/source_result либо конкретный groups[j].selection, по установленной причине; Source semantics не перепроверяются прямым helper |
| Группа пропущена/лишняя/повторна/не подходит address | DEPENDENCY_MISMATCH / METADATA_GROUP_MISMATCH — предложенный новый код | groups для отсутствующей; groups[j].group для конкретного неверного элемента |
| Partial preserve требует отсутствующей detailed attribution | DEPENDENCY_MISMATCH / METADATA_ATTRIBUTION_UNAVAILABLE — предложенный новый код | state.assembly_provenance[k].attribution; при отсутствии record — существующая коллекция, без выдуманного k |
| Missing/extra/duplicate input evidence slot, неверный value fingerprint или region entry_index | DEPENDENCY_MISMATCH / METADATA_INPUT_MISMATCH — предложенный новый код | metadata_inputs для отсутствующего; metadata_inputs[j].input/value_fingerprint для предъявленного |
| Pack basis устарел или не соответствует вычисленному status | DEPENDENCY_MISMATCH / METADATA_BASIS_MISMATCH — предложенный новый код | entries[i].groups[j].basis; это не Source proof mismatch |

Четыре новых semantic кода предлагаются внутри существующего PackPreparationIssueCode; отдельный error class/union variant не вводится. Они различают группу, отсутствие исторической детализации, неверный вход и stale/invalid Pack basis, не маскируют их под MISSING_PART/DUPLICATE_ADDRESS. Конкретные Source validation failures переводятся в SOURCE_PROOF_MISMATCH только когда owning outcome действительно доказывает mismatch; IO/cancellation/admission infrastructure сохраняют owning failure. Source diagnostics не дублируются локальными guesses. Независимые нарушения агрегируются в исходном порядке до любого изменения state.

## 6. Статус и следующий шаг

Семантика и переход старой базы согласованы. Таблицы конкретизируют кандидат Pack data transfer и способ не дублировать row proof: одна Source proof плюс group subsets. Именно этот способ ещё требует проверки Source selection/admission binding; он не выводится из пользовательского согласия автоматически.

Field/input roster, размещение Pack basis и diagnostic mapping предъявлены выше; четыре новых кода требуют приёмки вместе со схемой. Внешние usage/admission/subset типы теперь предъявлены Source как PROJECT. До реализации зависимого маршрута остаются exact Pack inputs/outputs для extraction и verification через DAG, trusted producer/state boundary, Source usage binding для status отдельно от его Pack structural basis, canonical schema registration и owning приёмка. Прямой pure extraction из Pack исключён. Не объявлять интеграцию готовой и не блокировать ею независимые Pack операции. Проверки смешанного происхождения, restart, equal-value/different-usage, отсутствующей attribution и масштабирования заданы в исходном документе. Следующая приёмка применяет все правила проекта к этому конкретному срезу; документ не разрешает изменение кода.
