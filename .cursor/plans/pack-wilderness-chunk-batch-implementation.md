# Pack: реализация single и batch wilderness chunk writes

2026-11-16. Статус: **PASS независимой приёмки implementation-плана B1–B5, включая технические решения §3.1–3.2; код по нему не изменён**. Результат зафиксирован по прямому поручению пользователя после независимого ревью в текущем чате. Это отдельный вердикт, не автоматическое распространение прежнего PASS контрактного дополнения из чата `01a1e4f2-bf85-73c3-81dd-7a1137ac6e27`. B6 остаётся отдельной последней интеграцией; реализация, весь Pack и production end-to-end этим вердиктом не приняты. Формулировки ниже о предстоящей приёмке плана сохраняют историю подготовки и заменены настоящим статусом.

## 1. Источники и предел работы

Нормативные источники:

- [Batch contract](pack-wilderness-chunk-batch-contract.md), включая «Применение и порядок», «Диагностика дополнения» и «Поимённое уточнение контрактного inventory».
- [Точные transitions](pack-chunk-metadata-transition-contract.md): актуальные правила перекрывают исторические OPEN в предыдущих документах.
- [Owner requirements](pack-batch-owner-contract-requirements.md) и [bulk principles](pack-bulk-write-principles.md).
- [Write contract](pack-v2-public-write-operations.md): state admission, write_wilderness_chunk, metadata projection и error aggregation.
- [Metadata POJO](pack-metadata-dependency-pojo.md), [status basis](pack-wilderness-status-dependencies.md), [Source exchange](pack-source-exchange-contract.md).
- [ТЗ Pack](../../docs/tz_world_pack_storage.md) и [domain contract](pack-v2-domain-contract-spec.md).
- [Payload binding roster](pack-payload-binding-roster.md#форматы-и-типизированное-чтение), [минимальный metadata encoding до зависимых операций](pack-serialization-deserialization.md#зависимость-metadata-операций-3a), [canonical inventory](pack-prepare-canonical-inventory.md).

Результат этого плана — две pure операции Pack над одним immutable state с общим внутренним переходом, typed diagnostics и измеренным массовым путём. Не финальный prepare/READY, не storage writer, не migration всего Pack.

Не входят: генераторы, producer bindings, Source SELECT/admit/adoption, Snapshot pinning, Cache операции, describe/import/bind как новые публичные методы, SQL, HTTP, новые DAG-ноды, запуск backend, commit/push. При отсутствии импортированных historical usages операция обязана отказать по принятому контракту; не реализовывать внутри неё импорт. Интеграция с DAG — последний отдельный шаг после принятия доменного кода, выполняемый по согласованным нодам пользователя.

## 2. Сверка с кодом и зависимости

Пути далее относительно `backend/`.

| Что уже существует | Что делать |
|---|---|
| `app/dataModel/worldPack/preparation/parts.py::PackWildernessChunkPartInput` | Переиспользовать address/artifact/provenance; не создавать копию payload input |
| State, assembly, metadata subjects/dependencies/attribution, SourceProofInput/SourceDurableProof/SourceProofSelection | Переиспользовать owning declarations из принятого inventory |
| `operations.py` содержит другие pure writes, но нет chunk single/item/batch | Добавить только согласованные объявления |
| `PackPreparationService` содержит start_empty, climate/index/spatial/grade writes и deletes; chunk методов нет | Single и batch поставлять вместе на одном transition, не ссылаться на несуществующий single как доказательство |
| `PackPreparationValidator` проверяет state identities/groups; errors.py умеет leaf admission и missing sentinel | Расширить нужными predicates, сохранить независимую диагностику; не считать существующие checks полной проверкой актуальности subject/basis |
| `errors.py` создаёт TypeAdapter при leaf checks | Добавить reuse annotations при подтверждённом exact cache key; не кешировать результат валидации values |
| `app/encoding/canonicalCodec.py` содержит CanonicalCodec, encode/content_digest | Использовать существующее ядро; конкретный проект Pack binding предъявлен в §3.1 и принимается вместе с этим планом |
| Legacy `worldPackWriter.commit_chunk`, status policy | Источник уже принятой семантики; не вызывать legacy writer из pure service и не переносить его replacement-order |

Порядок зависимостей: owning schema/evidence и fingerprint binding → admission → локальный переход → single/batch methods → функциональная приёмка → измерения → отдельная DAG-интеграция. Source/Snapshot/Cache не являются обязательными runtime вызовами внутри этого среза.

## 3. Публичная граница и ответственность

Владелец — Pack. Публичный класс `app/application/worldData/pack/preparation/packPreparationService.py::PackPreparationService`:

```python
def write_wilderness_chunk(self, request: PackWildernessChunkInput) -> PackPreparationState: ...
def write_wilderness_chunks(self, request: PackWildernessChunksInput) -> PackPreparationState: ...
```

Input объявления — `app/dataModel/worldPack/preparation/operations.py`: item `PackWildernessChunkWrite(part, refine_role, metadata_inputs)`, single наследует item и добавляет state; batch содержит state и entries. Output — существующий `preparation/state.py::PackPreparationState`. Ошибка — `application/worldData/pack/preparation/errors.py::PackPreparationFailure`, несущая `dataModel/worldPack/preparation/errors.py::PackPreparationError`. Нового result/receipt/error union нет.

Прямой production caller — DAG. DAG выбирает публичные операции и границы пакета, передаёт данные и результаты. Ни service, ни helpers не выбирают следующую публичную стадию и не вызывают чужой API. Batch не вызывает single в цикле; single не конструирует batch request для повторного admission.

Принятый [поимённый inventory](pack-wilderness-chunk-batch-contract.md#поимённое-уточнение-контрактного-inventory) включён в этот план ссылкой целиком: owning declarations, поля, dependencies/effects, DoD и признаки отказа для существующих типов не переносятся на последующую работу. Ниже — конкретное размещение реализации и дополнительных используемых типов.

| Класс / модуль | Ответственность и зависимости | DoD / отказ в приёмке |
|---|---|---|
| PackPreparationService, существующий | Две публичные atomic операции: admission → локальное применение → один результат | Нет IO, public-method chaining, скрытого workflow или service-held состояния |
| PackPreparationValidator, существующий | State/item predicates и точные diagnostics; только данные и общие validation helpers | Ошибка соседнего поля не скрывает независимую проверку; ошибки не исправляют input |
| PackWildernessChunkWrite / PackWildernessChunkInput / PackWildernessChunksInput, новые | Data-only declarations из принятого контракта | Strict/frozen/extra-forbid/revalidate-always; exact item admission; single со state внутри entries отклоняется |
| PackMetadataInputEvidence, PackMetadataValueInputSelector, PackMetadataRegionInputSelector, согласованные, ещё отсутствуют в runtime | Единственные объявления в `dataModel/worldPack/preparation/metadataDependencies.py` по metadata POJO §2–3; selector/value_fingerprint/source_usage | Полная owning форма selector union, без урезанного batch-зеркала; chunk допускает только VALUE ADDRESS/REFINE_ROLE |
| PackMetadataInputField / PackRegionMetadataInputField и discriminator selectors, согласованные | Closed enum roster metadata POJO §3 в том же owning модуле | Не создавать OTHER, строковые field paths или новые значения; объявления не реализуют остальные write-методы |
| CanonicalCodec — `app/encoding/canonicalCodec.py`; поле manifest: CanonicalSchemaManifest | Existing generic encoding primitive; Pack использует encode/content_digest, не чужую доменную операцию | Один Pack binding для записи/проверки; repr, новый hash engine и скрытая normalization запрещены |
| CanonicalSchemaManifest — `app/dataModel/encoding/schemaManifest.py`; entries: tuple[RegisteredTypeEntry, ...] | Immutable schema data; проверяет уникальность ID и owner | Дубли ID/owner отвергаются; schema не выполняет доменный workflow |
| RegisteredTypeEntry — тот же модуль; type_id: StrictInt > 0, python_type: type, kind: CanonicalTypeKind | Одна регистрация concrete owning типа | ID и kind соответствуют точному owner; нет aliases/generic bases вместо concrete type |
| CanonicalTypeKind — тот же модуль; RECORD/ENUM | Категория регистрации, без effects | Только owning варианты; ChunkRefineRole/ClimateBakeStatus — Literal aliases, не Enum и не отдельные entries |
| CanonicalEncodingError — `app/encoding/canonicalCodec.py`, existing exception без дополнительных полей | Сбой canonical primitive | Невалидный пользовательский input отклоняется typed Pack admission до encoding; ошибка регистрации не маскируется как METADATA_INPUT_MISMATCH |

Внутренние новые модули — функции, не новые публичные классы:

- `app/application/worldData/pack/preparation/metadataProjection.py`: выбор owning projection, проверка subject, canonical fingerprint input evidence/projection. Один общий механизм, пригодный для последующих describe/bind; сами публичные методы сюда не добавляются.
- `app/application/worldData/pack/preparation/wildernessChunkWrite.py`: локальные индексы, membership, применение одного item и итоговая материализация. Локальные typed dict/list/set не выходят из вызова, не сохраняются в service/cache, не являются публичным builder или вторым state POJO.

CRUD: create и update реализованы обеими write-операциями (новый адрес / replacement); read/describe и delete сохраняют свои отдельные контракты. Batch не добавляет публичные read/delete и не объявляет их реализацию завершённой. CRUD настроек: C/R/U/D не меняются, новых настроек/лимитов/defaults нет. Полная приёмка CRUD всего Pack — другой скоуп.

### 3.1. Конкретный минимальный metadata binding для приёмки плана

**Новая техническая конкретизация этого implementation-плана, не ранее выданный PASS.** В runtime отсутствует. Принимается до B1; при несогласии reviewer корректируется этот раздел, а не выбирается иная схема во время кода. Полный body/manifest codec, Source usage transport и READY recovery здесь не проектируются.

Единственное объявление `PACK_METADATA_SCHEMA` — новый `app/dataModel/worldPack/encoding/metadataBindings.py`, использующий existing CanonicalSchemaManifest/RegisteredTypeEntry. Таблица — полный reachable record/enum graph для формул ниже. Номера предложены только для Pack-owned классов; статическим поиском регистрации этих owners и назначение этих ID в просмотренных production declarations не найдены. Это не глобальная резервация: collision check фактической composition обязателен до поставки. Чужие ID не назначаются и не перенумеровываются.

| type_id | Concrete owner (относительно app/dataModel/worldPack/) | kind / поля в owning declaration order |
|---|---|---|
| 20401 | preparation/addresses.py::PackChunkAddress | RECORD: kind, gx, gy, cx, cy |
| 20402 | preparation/addresses.py::PackAssemblyHeaderAddress | RECORD: kind |
| 20403 | preparation/addresses.py::PackTileMetadataAddress | RECORD: kind, gx, gy |
| 20404 | preparation/addresses.py::PackChunkMetadataAddress | RECORD: kind, gx, gy, cx, cy |
| 20405 | preparation/addresses.py::PackLocationMetadataAddress | RECORD: kind, location_uid |
| 20406 | preparation/addresses.py::PackSettlementMetadataAddress | RECORD: kind, location_uid |
| 20407 | preparation/addresses.py::PackRegionMetadataAddress | RECORD: kind, region_uid |
| 20408 | preparation/metadataDependencies.py::PackMetadataValueInputSelector | RECORD: kind, field |
| 20409 | preparation/metadataDependencies.py::PackMetadataInputField | ENUM: полный roster metadata POJO §3, wire values — lower_snake_case имён slots |
| 20410 | preparation/assembly.py::PackLocationAssembly | RECORD: location_uid, territory_volume, climate_status |
| 20411 | preparation/assembly.py::PackSettlementAssembly | RECORD: location_uid, territory_volume, structure_status, packed_district_uids |
| 20412 | wire/territoryVolume.py::TerritoryVolume | RECORD: x0, y0, z0, x1, y1, z1 |
| 20413 | meta/wildernessRegionEntry.py::WildernessRegionEntry | RECORD: region_uid, entry_type, current_type, bbox, status, parent_region_uid, spec_fingerprint |
| 20414 | meta/wildernessRegionEntry.py::RegionIndexBounds | RECORD: x_min, y_min, x_max, y_max |
| 20415 | meta/wildernessRegionEntry.py::WildernessRegionStatus | ENUM: existing owning values |

Selector discriminator для новых declarations: Literal `"value"` / `"region_entry"`; поля и roster остаются из metadata POJO. Region selector/region input enum объявляются в общей owning форме, но chunk input их отвергает до fingerprint; они не reachable в этом минимальном encoding binding. Полная generic evidence transport schema этим не объявляется.

`encode` и `content_digest` — существующие функции `app.encoding.canonicalCodec`. Fingerprint — `content_digest(encode(value, PACK_METADATA_SCHEMA)).hex()`, то есть RevisionHex; не новый hash engine. Два точных входных value:

- Evidence: tuple `("pack.metadata.input", selector, selected_value)`. Для ADDRESS selected_value — полный PackChunkAddress; для REFINE_ROLE — owning string literal либо None. Source usage не входит в fingerprint значения input.
- Subject: tuple `("pack.metadata.value", metadata_address, projection)`. base_publication остаётся отдельным обязательным полем subject и сравнивается целиком; fingerprint идентифицирует значение projection по адресу, не proof/базу/историю.

Projection selector поддерживает все существующие metadata address variants, поскольку admission исходного state не ограничен изменяемыми строками:

| Address | Projection, точный порядок |
|---|---|
| header | tuple(last_l0_mode, fine_cells_per_map_cell, world_map_cells_per_tile, fine_cell_size, map_subsurface_depth, terrain_chunk_columns) |
| tile | tuple(gx, gy, climate_status, wilderness_refine_status), без chunks |
| chunk | tuple(cx, cy, refine_role) адресованного chunk; tile identity уже в address |
| location | Полный PackLocationAssembly |
| settlement | Полный PackSettlementAssembly; packed_district_uids сохраняет tuple-order |
| region | Полный WildernessRegionEntry |

Порядок полей берётся из owning declarations, typed значения проверяются до encoding; ручные dict зеркала, repr и JSON key ordering запрещены. EntityUid/RevisionHex/RegistryKey и Literal поля используют scalar encoding existing kernel, не новые registrations. Basis/usages/proofs не включаются в value_fingerprint и проверяются отдельно: одинаковый fingerprint не разрешает stale bind или preserve. SourceProofInput поэтому не требует нового Source type_id для этого среза; serialization полного state остаётся отдельным owning graph.

Canonical order basis в пределах одного tile: после duplicate admission сортировать адреса по `(gx, gy, cx, cy)` численно; kind у всех один. Это предложение конкретизирует ранее требуемый детерминированный порядок; parts/assembly tuple-order не сортируется вслед за basis. Сверить и принять этот порядок в рамках приёмки плана до B1, не считать новым порядком DAG.

Матрица vectors при поставке: ADDRESS с отрицательным gx и положительными cx/cy; REFINE_ROLE=None и каждый owning literal; header; tile coarse/partial и fine/complete; chunk nullable role; location/settlement с TerritoryVolume; region с bbox/status/nullable fields. Для каждого — фиксированные bytes/hash, повтор в отдельном процессе, изменение каждого смыслового поля; изменение только chunks при неизменной tile projection не меняет tile fingerprint, но меняет basis. Различные selectors/domain tags обязаны различать одинаковые scalar значения. Runtime hex-векторы следуют B1, не требуются как уже выполненный тест документа.

### 3.2. Точный descriptor admission wilderness payload

Источник выбора — [payload roster, строка wilderness_chunk/location_terrain](pack-payload-binding-roster.md#форматы-и-типизированное-чтение): BLOB, `world_pack.fine_terrain.zstd`, первая storage version 1, existing FineTerrainChunkWire. Это **проект owning Pack binding**, не найденная production-регистрация и не версия manifest/TileCodec envelope.

В B1 создать только owning constants в `app/dataModel/worldPack/meta/fineTerrainStorageFormat.py`: `FINE_TERRAIN_FORMAT_KEY: ArtifactFormatKey` со значением указанного ключа и `FINE_TERRAIN_STORAGE_VERSION: FormatVersion` со значением 1. Использовать существующий ArtifactFormatKey из `app/dataModel/artifacts/references.py` и owning FormatVersion из `app/dataModel/patch/values.py`; новых классов или enum не требуется. Pure predicate после structural ArtifactRef admission: kind is ArtifactKind.BLOB, format_key равен owning constant, format_version равен owning constant. Несовпадение — FORMAT_MISMATCH на part.artifact (с исходным batch префиксом).

Не объявлять этот predicate декодированием/проверкой bytes, seal или удержанием. Decoder/profile/storage registration относятся к отдельному read/prepare срезу. Здесь нет чтения payload, выбора byte cap или требования интегрировать генератор. Непустота/shape descriptor проверяется owning ArtifactRef, дополнительные произвольные ограничения не добавляются. Если owning roster изменён параллельно, разрешить конкретное противоречие до правки constants, не поддерживать оба формата fallback-веткой.

## 4. Шаги реализации и проверяемые выходы

### B1. Общие DTO и локальная identity

- Добавить перечисленные evidence/selectors и item/single/batch declarations в owning модули; проверить отсутствие уже появившихся объявлений перед правкой.
- Реализовать `metadataProjection.py` на existing canonical kernel. Для tile fingerprint брать собственные координаты/status без chunks; для chunk — координаты/роль адресованного chunk. Input fingerprint включает identity selector и typed выбранное значение. Точный Pack binding должен быть один для формирования и проверки, без повторного DTO значений.
- Реализовать принятый после проверки плана binding §3.1, проверить exact reachable graph/collisions и зафиксировать vectors. Не выбирать IDs, формулу или порядок заново в B1.
- Реализовать descriptor constants/predicate §3.2. Этот шаг не включает decoder/storage binding и не объявляет pure admission доказательством payload integrity.

Выход: строгие declarations, воспроизводимые fingerprints, один binding и format predicate. Тесты `tests/spatial_pack/test_preparation_chunk_contracts.py`: missing/None, extra keys, enums, union selectors, forged dictionaries/models, exact item vs single subclass, canonical vectors. B2–B4 не закрываются при неподтверждённых identity/format predicates.

### B2. Полный admission и независимые ошибки

- В validator добавить проверки evidence slots/fingerprint/world, актуальности pending subject и basis, уникальности batch addresses, доступности сохраняемых tile usages. Base/state проверять до применения, entries независимо от ошибок соседних полей.
- Сохранять валидированные значения после успешного schema admission; не продолжать semantic checks на исходном dict вместо полученного POJO. После частичного отказа допускать отдельные необходимые поля с исходными индексами, не целые записи как условие независимых checks.
- Уникальность address не зависит от artifact/provenance; format не зависит от address; proof.world не зависит от planning; missing basis отличается от explicit None.
- Следовать code/path таблице принятого batch-контракта без нового набора ошибок. Причина: structural → INVALID_INPUT; иначе любой non-address semantic mismatch → DEPENDENCY_MISMATCH; иначе address duplicates → IDENTITY_CONFLICT. Missing/duplicate metadata slot остаётся METADATA_INPUT_MISMATCH, не IDENTITY_CONFLICT.
- Inherited input без предусмотренного verified admission отклонять SOURCE_PROOF_MISMATCH; не выдавать ordinary DTO за pinned origin. При наличии нового принятого owning admission переиспользовать его, не вводить batch-specific доверие.
- Reuse TypeAdapter только по exact owner/field/specialization и типу элемента; никаких caches values/identity/«уже проверено» и обхода revalidation.

Выход: typed aggregation с путями single/batch и отсутствием двойной диагностики одного missing поля. Новые negative tests в `test_preparation_chunk_contracts.py`; действующие preparation regressions обязательны при изменении общих helpers.

### B3. Один последовательный внутренний переход

В `wildernessChunkWrite.py` реализовать принятую последовательность, без промежуточной сборки полного state:

1. После admission один раз построить новые локальные индексы parts, tile/chunk membership, provenance и текущих descriptions. Immutable usages хранить ссылками; не копировать их на каждом item.
2. Применять entries в tuple-order. Replacement сохраняет позицию part; новые parts/rows добавляются по первому появлению. Duplicate input addresses уже отклонены; совпадение с базой — replacement.
3. Новый tile: identity получает целиком ADDRESS usage первого item; coarse climate — Pack-derived empty usage. Existing tile сохраняет IDENTITY/CLIMATE_STATUS из актуального pending/imported description; отсутствие оснований — отказ, без Source SELECT внутри Pack.
4. Каждый chunk получает ADDRESS и REFINE_ROLE текущего item, включая explicit None; equal values не сохраняют старые usages автоматически.
5. На каждом item выполнять provisional transition над membership с expected=None. Для затронутого tile — partial и empty status usage; canonical basis материализовать один раз в конце. Complete при replacement не сохранять.
6. При изменении value/basis/usage инвалидировать старый row binding, сохранив независимые группы в pending карте. Следующий item видит эту карту. На зависимом отказе не выполнять переходы, которым нужен отсутствующий результат; независимые проверки входов уже выполнены, частичного output нет.
7. Один раз собрать descriptions/subjects и итоговые assembly/parts tuples; незатронутые records сохранить. Полный basis отдельно отсортировать по owning canonical order. Собрать один итоговый state и проверить допустимость промежуточного состава, без final completeness/READY.

Выход: внутренний pure алгоритм с отсутствием обхода всего state/tile на каждом item. Empty entries выполняет admission и возвращает эквивалентный state без перерасчёта/invalidation. Условие успеха не зависит от object identity.

### B4. Публичные single и batch, функциональная приёмка

Подключить оба service-метода к B2/B3. Single получает один item из валидированного собственного request без создания второго публичного request. Batch проходит тот же transition в цикле локального применения.

Добавить `tests/spatial_pack/test_preparation_wilderness_chunks.py`:

- Unique additions/replacements: single-chain vs batch по parts, assembly, pending descriptions и пригодности bindings; отдельные проверки порядка.
- Один/несколько tiles, mixed existing/new, два captures в evidence; tile identity от первого ADDRESS, каждый chunk со своими usages, climate/status empty usage с nonempty basis.
- Existing fine/complete replacement → fine/partial; partial→partial membership change; nullable role и equal value/different usage.
- Missing retained usage и whole-row attribution отказ; pending после предыдущего item не заменяется исходным state. Полный исходный state неизменен при успехе и отказе.
- Forged nested inputs и несколько независимых ошибок: duplicate+format+foreign world+bad planning; malformed sibling не скрывает адрес/UID/group/basis checks; missing nullable поле не создаёт вторую semantic ошибку.
- Empty batch, single request внутри entries, extra selectors/duplicate slots, неверный fingerprint, stale subject/basis. Проверка всех codes/paths/reason, не только факта exception.
- Независимые ожидаемые значения из transition table: одного совпадения single и batch недостаточно, общий helper может ошибаться одинаково.

Stale provenance проверяется по output invalidation и изменённым descriptions/basis. Реальный Source exchange/последующий bind-тест не подменять mock-«успехом» и не объявлять выполненным до owning публичного binding-среза.

Выход: обе операции реализованы полностью в данном pure скоупе; новые/изменённые tests и production modules типизируются без suppressions, Any или model_construct в production для обхода checks. Forged construction допустим только в negative fixtures.

### B5. Масштабирование и финальная проверка реализации

Добавить воспроизводимый harness `tests/spatial_pack/measure_wilderness_chunk_batch.py`, отчёт `.cursor/plans/pack-wilderness-chunk-batch-measurement.md` создавать только по фактическим замерам.

Матрица: 1000/4000/16000 additions и replacements; один большой tile и много tiles; лёгкий и тяжёлый nested provenance/usage/basis. Измерять построение публичного request вместе с admission/применением/результатом, время и peak memory. Отдельно фиксировать B/U/R (объёмы базы/входа/результата), canonical sorting и owning leaf checks. Fixture setup отделить от измеряемого маршрута; constructor validation не исключать.

Критерии: ограниченное, не растущее с K число полных проходов по базе/результату; отсутствие K materializations basis/state и повторного full tile scan; локальный индекс строится один раз; стоимость сопоставляется с B+U+R и отдельно sorting. Предъявить counters наряду со временем, условия запуска и исходные результаты. Квадратичный рост при сопоставимых B/U/R или повторные полные обходы означают FAIL массового среза, а не повод отключить strict admission. Числовой предел entries не вводить.

После функциональных тестов — targeted Pyright новых/изменённых tests, затем production Pack scope и полный `tests/spatial_pack` для честного учёта baseline. Существующий долг не скрывать за узким «0 ошибок», не исправлять посторонние тесты в этом срезе. Runtime suites выбирать по изменённым helpers и зависимым модулям; runtime benchmark не заменяет функциональную приёмку.

Выход: отчёт с доказательствами, остаточными ограничениями и diff всех изменённых файлов; отдельная независимая приёмка кода. PASS этого шага не означает приёмки остального Pack.

### B6. Отдельная интеграция через DAG — последняя

После принятия B1–B5: согласованный DAG передаёт imported usages в state, вызывает single/batch напрямую, передаёт descriptions в Source и результаты обратно в Pack. Execution binding, Source adoption и closure перед READY проверяются в своих owning срезах. Здесь не создавать ноды или генераторные контракты. Отсутствие B6 не мешает принять pure методы B1–B5, но запрещает объявлять production end-to-end готовым.

## 5. Проверка последовательности и критерии отказа плана

| Критерий | Где предъявлен / условие отказа |
|---|---|
| Три запрета DAG | §1/§3/B6: прямой caller, нет выбора публичных стадий и междоменных вызовов; нарушение любого — FAIL |
| Class/POJO inventory | Принятый поимённый roster включён ссылкой, реализационные зависимости в §3; дополнительный класс без owning полей/DoD требует дополнения до кода |
| Public/internal boundary | Два named request/state/error контракта; локальные индексы не выходят наружу |
| Утверждённый порядок | B3 повторяет порядок batch-контракта; B1/B2 prerequisites, B4 после общего перехода, B5 после функциональных checks, B6 последний |
| CRUD/settings | §3: scope create/update, остальные операции не заменяются; settings без изменений |
| Междоменные contracts | §1/B2/B3/B6: Source owning данные через DAG, отсутствие готового usage — typed refusal; Snapshot identity не capability; Cache не вызывается |
| Errors/отсутствие дублей | §3/B2 и ссылка на accepted inventory; один field/logic error carrier, semantic/structural разделены |

План не заявляет выполненными B1–B6. До кода пройти независимую приёмку implementation-плана, включая конкретные технические предложения §3.1–3.2; они больше не отложены на выбор во время реализации. При реальном противоречии owning контракту остановить только зависимую часть и предъявить точный predicate/type вопрос; не добавлять placeholder, новый внешний API или генераторную интеграцию.

### Сверка с ТЗ и связанными планами — 2026-11-16

| Источник | Сопоставление / результат статической сверки |
|---|---|
| ТЗ Pack § «Проект POJO подготовки Pack», адреса/parts/state | B1 использует единственные owning records; world из base_publication. Source proof/Planning не дублируются в item |
| ТЗ Pack: final prepare получает уже конечный state | B3 создаёт промежуточный state; не запускает prepare, assembler, stage, READY или activation |
| Write contract: публичные metadata операции и один projection selector | §3.1 даёт общий механизм для будущих describe/bind, но не вводит эти операции в chunk workflow |
| Write contract: state admission и агрегация | B2 сохраняет nested strict checks, missing/None и field-granularity independence; приоритет reason из принятого batch дополнения |
| Metadata POJO / status dependencies / принятые transitions | B3 сохраняет группы существующего tile, обоснованные empty usages и non-null status basis; Source indices не интерпретируются Pack |
| Serialization plan § «Зависимость metadata-операций 3a» | Минимальный binding §3.1 принимается до кода B1; полный 4a/READY не перенесён перед pure 3a. Вопрос SourceProofInput registration полного transport graph не подменён Pack ID |
| Payload roster | §3.2 конкретизирует ровно предложенный shared fine-terrain descriptor; не создаёт отдельный wilderness codec/формат |
| Bulk principles | B3 — последовательные transitions, итоговая материализация один раз; B5 учитывает constructor/nested стоимость, sorting и retained data |

Статическая сверка не обнаружила необходимости менять согласованную семантику batch или порядок DAG. IDs, domain-separated fingerprint формулы, точный basis order и descriptor admission §3.1–3.2 приняты отдельным независимым ревью настоящего implementation-плана. Независимый PASS контракта на них автоматически не распространялся. Код, runtime composition и benchmark в этом документальном проходе не проверялись исполнением.

### Независимая приёмка implementation-плана — 2026-11-16

**Вердикт: PASS B1–B5. Блокирующих findings не выявлено.**

| Обязательный критерий | Основание приёмки |
|---|---|
| Три запрета DAG | §1/§3/B3/B6: DAG выбирает операции и границы пакета; Pack выполняет локальный переход без междоменных вызовов, callbacks или скрытого запуска публичных стадий |
| Ответственность классов и inventory | §3 включает принятый roster нормативной ссылкой и дополняет canonical-классами, полями, dependencies/effects и DoD; обязательный inventory не отложен до реализации |
| Public/internal boundary | Два named request, existing state/error; индексы и функции применения внутренние; single не создаёт batch request, batch не вызывает публичный single |
| Утверждённый порядок | B1 identity/schema → B2 admission → B3 общий переход → B4 функциональная приёмка → B5 измерения; B6 последним. B3 сохраняет tuple-order, промежуточные отказы и принятые transitions |
| CRUD данных и настроек | Create/update конкретизированы; read/describe/delete сохраняют отдельные контракты. C/R/U/D настроек не меняются; новых defaults/лимитов нет |
| Междоменные контракты | Owning POJO без вызовов сервисов владельцев; historical usage поступает заранее через DAG; отсутствие evidence вызывает отказ; Snapshot identity не capability |
| POJO и типизированные ошибки | Общие declarations без зеркальных carriers; existing field/semantic diagnostics, исходные индексы и согласованный reason priority; ошибки регистрации не маскируются пользовательским metadata mismatch |

Отдельно проверены §3.1–3.2: конфликтующих назначений IDs 20401–20415 в проверенных production declarations и планах не найдено; reachable graph заявленных fingerprint-формул покрыт. Nullable REFINE_ROLE и Literal aliases используют scalar encoding; SourceProofInput не входит в value fingerprint, usage/basis проверяются отдельно. Projection fields/order соответствуют owning declarations и write-контракту; tile исключает chunks. Численный basis order `(gx, gy, cx, cy)` соответствует status-dependencies и не переставляет writes/parts. BLOB / `world_pack.fine_terrain.zstd` / storage version 1 соответствует проекту payload roster; descriptor check отделён от decoder/storage/seal/hold/READY.

B2 явно требует дополнить текущий validator subject/basis и независимыми checks, не объявляя существующий admission полным. B4 требует независимых ожидаемых результатов помимо single/batch equality. B5 задаёт counters, B/U/R, constructor validation, sorting, peak memory и условия отказа при повторных полных обходах.

Фактически выполнены: чтение плана, сверка обязательного правила и принятого batch/transitions, связанных metadata/write/serialization/payload контрактов; проверка canonical kernel/schema manifest, registrations, address/assembly/metadata/provenance/error declarations и текущего validator; поиск IDs по production-коду и планам. Runtime vectors, tests, Pyright и benchmarks не выполнялись: они остаются свидетельствами поставки B1–B5. Реализация и коммиты в рамках ревью не выполнялись.
