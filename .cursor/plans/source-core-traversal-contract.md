# Source — structural traversal и допуск leaves

2026-11-16. Архитектурный proposal АР-1, детализация решения пользователя: immutable facts + diagnostics; traversal не вызывает semantic checkers; request checker не повторяет обход. Не runtime API и не разрешение реализации. Публичные POJO и импорты Pack не меняются. Применяется вместе с source-core-request-composition.md; перечисленные ниже дельты существующих внутренних checker API требуют проверки при приёмке всей архитектуры.

## 1. Общие гарантии

Все inspect-функции — private pure функции модуля `proof/validation/requests/traversal.py`. У каждой один входной record/container и его `CheckedPath[RootT, T]`, где RootT: BaseModel, T — точный входной тип. Результаты — вычисленные immutable tuples. В таблицах ниже запись `inspect_x(value: T) → R` означает полную сигнатуру `inspect_x[RootT: BaseModel](value: T, *, path: CheckedPath[RootT, T]) -> R`. Это соглашение записи, не новый type alias или runtime DTO.

Каждый result заканчивается `tuple[SourceFieldIssue, ...]`. Optional slot означает непригодное/отсутствующее обязательное поле и сопровождается issue. Для nullable полей отдельно сохраняется наличие, чтобы валидный None не смешивался с отказом. Функции не чинят исходный объект, не создают модель из его пригодных частей, не вызывают model_construct. Strict scalar constraints читаются из existing FieldRef/bind_field и FieldInfo (включая metadata), а не переписываются литералами. Валидатор всего Source record не является structural extractor.

Record envelope проверяет конкретный ожидаемый тип, отсутствие неизвестных полей и допустимость чтения известных полей. Для union используется конкретная объявленная ветвь; discriminator проверяется отдельно и не исправляется по имени класса. Ошибка поля не отменяет чтение соседних полей. Ошибка envelope неизвестного типа отменяет только обход этого record. Изменяемые контейнеры не превращаются в tuples. Копия контейнера не делает повреждённый вход immutable.

RootT/path не восстанавливаются по строкам. FieldRef продолжает путь через field; item сохраняет исходную позицию; variant применяется только к объявленной union-ветви. Неизвестное вложенное поле адресуется containing path. У root нет freeze-пути: неизвестный root или неизвестное extra корня дают structural Pydantic отказ до semantic стадии, без выдуманного поля. Это отдельная граница допуска корня, а не model_validate всего дерева. Несогласованные path/type arguments — programming error.

## 2. Leaves: точные входы и результаты

| Функция и вход T | Результат R до последнего tuple issues |
|---|---|
| inspect_capture(SourceCaptureRef) | `tuple[EntityUid | None, ArtifactRef | None, tuple[SourceFieldIssue, ...]]` |
| inspect_object_ref(SourceVersionRef) | `tuple[SourceObjectId | None, SourceRevision | None, tuple[SourceFieldIssue, ...]]` |
| inspect_collection_ref(SourceCollectionVersionRef) | `tuple[SourceCollectionId | None, SourceRevision | None, tuple[SourceFieldIssue, ...]]` |
| inspect_revision(SourceRevision) | `tuple[int | None, RevisionHex | None, tuple[SourceFieldIssue, ...]]` |
| inspect_registry_identity(RegistryMemberId) | `tuple[SourceDescriptorCategory | None, EntityUid | None, SourceDescriptorKey | None, SourceMemberKey | None, tuple[SourceFieldIssue, ...]]` |
| inspect_library_identity(LibraryMemberId) | `tuple[SourceDescriptorCategory | None, SourceDescriptorKey | None, EntityUid | None, tuple[SourceFieldIssue, ...]]` |
| inspect_entity_identity(EntityObjectId) | `tuple[SourceDescriptorCategory | None, EntityUid | None, SourceDescriptorKey | None, EntityUid | None, tuple[SourceFieldIssue, ...]]` |
| inspect_settings_identity(SourceSettingsId) | `tuple[SourceDescriptorCategory | None, EntityUid | None, SourceDescriptorKey | None, tuple[SourceFieldIssue, ...]]` |
| inspect_collection_identity(SourceCollectionId) | `tuple[SourceDescriptorCategory | None, EntityUid | None, SourceDescriptorKey | None, tuple[SourceFieldIssue, ...]]` |

Порядок scalar slots соответствует порядку полей actual POJO: kind, world_uid при наличии, descriptor, конкретный key при наличии. `inspect_revision` проверяет seq/hash по их существующим annotations; sequence allocation/hash calculation отсутствуют. Модельные slots в capture/ref проходят только envelope: ArtifactRef и identity ещё не считаются семантически допущенными. Дочерние inspect-функции вызываются общей механикой обхода ровно один раз на occurrence, не повторно внутри semantic checker. Родительские paths сохраняются рядом с результатами в локальных immutable tuples request invocation.

Source не копирует поля/семантику ArtifactRef в свою модель. Его полная value-validation выполняется **после traversal** существующим `TypeAdapter(ArtifactRef).validate_python(value, strict=True)` на исходном ArtifactRef. Это проверка общего value-типа, не вызов операции другого домена. Только ValidationError этой конкретной границы преобразуется в INVALID_SHAPE по исходному artifact path; один отказ на ArtifactRef, без разбора ValueError text. Никакие storage/registry/existence проверки сюда не входят. Успешный результат адаптера используется как доказательство валидности исходного value; repaired capture не создаётся.

### Единственность локальных semantic rules

| Правило | Единственная будущая реализация и signature | Использование результата |
|---|---|---|
| Непустой descriptor | `dataModel/sourceVersioning/_identityValueRules.py::is_nonempty_descriptor(value: SourceDescriptorKey) -> bool` | POJO validator и request semantic стадия используют один predicate; INVALID_IDENTITY на descriptor |
| Canonical UUID library key | тот же модуль, `is_canonical_library_uid(value: EntityUid) -> bool` | POJO validator и semantic стадия; INVALID_IDENTITY на template_uid |
| Witness shape capture | `dataModel/sourceVersioning/_captureValueRules.py::is_witness_artifact(value: ArtifactRef) -> bool` | После успешной ArtifactRef validation; POJO и semantic стадия используют один predicate; INVALID_SHAPE на capture.artifact |
| Exact enum discriminator и scalar/container constraints | Existing annotation/FieldInfo; для Python discriminator additionally exact SourceDescriptorCategory type | Structural стадия; INVALID_SHAPE. Не превращать string в enum |

Это адресный перенос existing правил `nonempty_descriptor`, `canonical_uuid`, `witness_shape`, не новые варианты контракта. При реализации wrappers POJO сохраняют отказ и strict/frozen guarantees; helper не импортирует application/errors. Request semantic stage только назначает existing code/path, не повторяет predicate. ArtifactRef.representation_fields остаётся у владельца общего типа; Source его не реализует.

World facts допускаются независимо от descriptor/key/revision. Неизвестный descriptor не скрывает WRONG_WORLD. Невалидная revision не скрывает ошибки доступной identity. Бит допуска leaf — локальный результат проверок, не публичный DTO/сертификат. В conflict batch попадает **исходный** ref только при полном локальном допуске его identity/revision; required capture должен быть допущен отдельно. Неуспех owning descriptor/key checks также исключает зависимые вычисления. Проверка world сохраняет source=None, если целый ref ещё непригоден для SourceLogicIssue.source.

## 3. Root/group/result wrappers

Соглашение сигнатур §1 действует и здесь. Все результаты содержат envelope-пригодные исходные records, не валидированные заново trees.

| Функция и вход T | Полный результат R |
|---|---|
| inspect_admission(SourceProofInput) | `tuple[EntityUid | None, tuple[SourceCaptureUsage, ...] | None, tuple[SourceFieldIssue, ...]]` |
| inspect_read(SourceProofReadInput) | `tuple[EntityUid | None, SourceDurableProof | None, tuple[SourceFieldIssue, ...]]` |
| inspect_groups(SourceProofGroupsInput) | `tuple[tuple[tuple[int, SourceProofInput, CheckedPath[RootT, SourceProofInput]], ...], tuple[SourceFieldIssue, ...]]` |
| inspect_verify(SourceProofGroupsVerifyInput) | `tuple[SourceProofGroupsInput | None, SourceProofGroupsResult | None, tuple[SourceFieldIssue, ...]]` |
| inspect_select(SourceProofSelectInput) | `tuple[EntityUid | None, SourceDurableProof | None, SourceProofSelection | None, tuple[SourceFieldIssue, ...]]` |
| inspect_groups_result(SourceProofGroupsResult) | `tuple[SourceProofResult | None, tuple[SourceProofSelection, ...] | None, tuple[SourceFieldIssue, ...]]` |
| inspect_result(SourceProofResult) | `tuple[SourceDurableProof | None, tuple[ArtifactRef, ...] | None, tuple[SourceFieldIssue, ...]]` |
| inspect_selections(tuple[SourceProofSelection, ...]) | `tuple[tuple[tuple[int, SourceProofSelection, CheckedPath[RootT, SourceProofSelection]], ...], tuple[SourceFieldIssue, ...]]` |
| inspect_durable_refs(tuple[ArtifactRef, ...]) | `tuple[tuple[tuple[int, ArtifactRef, CheckedPath[RootT, ArtifactRef]], ...], tuple[SourceFieldIssue, ...]]` |

Непустота groups/selections проверяется на поле-владельце по existing FieldInfo. Непригодный элемент не вычитает единицу из исходной длины контейнера. GROUP_COUNT_MISMATCH сравнивает исходные длины пригодных контейнеров, а не количество сохранённых facts. Если контейнер недоступен, count-check пропускается; доступные элементы другой стороны проверяются.

Для ADMIT_GROUPS authoritative expected world берётся только из structurally пригодного groups[0].world_uid. Если он повреждён/отсутствует, соседняя группа не назначается новой authoritative: cross-group equality пропускается, но собственные relations каждого пригодного group/use проверяются. VERIFY использует тот же expected.groups[0]; presented proof world не становится expected world.

## 4. Обязательные дельты внутренних checker API

Нынешние signatures нельзя одновременно оставить нормативными и заявить отсутствие повторного обхода. Следующие дельты являются proposal вместо соответствующих подписей в source-core-checker-signatures.md; код A0→D этим документом не изменён и его прежний PASS не переносится на будущую дельту.

### Identity

`SourceIdentityChecker` сохраняет constructor `(descriptors: SourceDescriptorLookup, keys: SourceIdentityKeyAdapter)`. Его check принимает identity независимо от revision:

```python
def check[RootT: BaseModel, IdentityT: (
    RegistryMemberId, LibraryMemberId, EntityObjectId,
    SourceSettingsId, SourceCollectionId,
)](
    self, identity: IdentityT, *, path: CheckedPath[RootT, IdentityT],
    group_index: int | None, use_index: int | None,
    source: SourceVersionRef | SourceCollectionVersionRef | None,
) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]: ...
```

Prerequisite: конкретная identity прошла structural и локальные value rules §2; revision для этого не требуется. source=None при повреждённой revision. Checker проверяет descriptor/category/scope/key_kind и owning key, не обходит исходный request и не повторяет local rules. Путь указывает непосредственно на identity; variant выполнен traversal. SourceIdentityKeyAdapter остаётся key-only, world/collection semantics не добавляются.

### Selection

`SourceSelectionChecker` сохраняет constructor `(atoms: SourceProofAtomIndex)`. Вместо повторного обхода SourceProofSelection получает scalar facts:

```python
def check[RootT: BaseModel](
    self, *,
    fingerprint: RevisionHex | None,
    indices: tuple[tuple[int, int, CheckedPath[RootT, int]], ...],
    proof: SourceDurableProof | None,
    selection_index: int | None,
) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]: ...
```

indices — исходная позиция, пригодный non-negative int, исходный path; уникальные возрастающие позиции фактов проверяются как programming prerequisite. Structural INVALID_SELECTION по повреждённым scalar indices уже возвращает inspect_selection и больше никто. Порядок/duplicates значений проверяет единственный `invalid_selection_order_positions`; checker отображает его позиции обратно в исходные paths. fingerprint=None означает уже диагностированное повреждение. proof=None означает отсутствие пригодного canonical proof: только proof-relative fingerprint/bounds пропускаются, порядок пригодных indices всё равно проверяется. Нет нового bool режима. При наличии proof: один SELECTION_OUT_OF_RANGE на selection, отдельный SELECTION_PROOF_MISMATCH. Fingerprint hashing и atom enumeration — existing implementations. Canonical checker вызывается только после полного leaf/structural допуска persisted proof; canonical отказ не запрещает независимые selection order checks.

## 5. Trace пяти request checkers

Во всех строках общая последовательность: root boundary → structural traversal → независимые local/owning semantic checks → conflict batch своей стороны → canonical checks persisted стороны → selection checks → aggregation. Request checker вызывает общие inspect-функции и управляет порядком semantic checks; не пишет второй field/index traversal. Это локальный алгоритм одной проверки, без public/domain/IO calls, выбора DAG-маршрута и transformation.

| Owner | Structural ветви | Semantic дополнительные relations / дальнейшая стадия |
|---|---|---|
| Admission | inspect_admission → inspect_usages → inspect_usage → inspect_capture/inspect_dependencies → leaf functions | world request/captures/identities; declared repetitions разрешены; normalizer только после отсутствия issues |
| Read | inspect_read → inspect_proof → та же usage/leaf ветвь | world request/proof/captures/identities; canonical persisted proof; без normalize |
| GroupAdmission | inspect_groups → inspect_admission по original group positions → общая usage/leaf ветвь | world groups относительно группы 0; один conflict batch всех групп; union после успеха |
| GroupVerification | inspect_verify → inspect_groups(expected); inspect_groups_result(result) → inspect_result → inspect_proof, inspect_durable_refs; отдельно inspect_selections → inspect_selection | expected/presented conflict batches раздельно; count по исходным контейнерам; presented canonical proof; selection checks; matcher только после успеха |
| Selection | inspect_select → inspect_proof → общая usage/leaf ветвь; отдельно inspect_selection | world; canonical proof; selection order всегда для пригодных indices, bounds/fingerprint по prerequisites; extractor после успеха |

Result durable refs проходят общую ArtifactRef validation §2; повтор refs и связь empty proof/closure проверяются по §5.1. Сверка с **вычисленным** closure принадлежит позднему result verification, не traversal.

### 5.1. Единственный владелец result value relations

Proposal переноса существующего `SourceProofResult.refs_shape`, без новых инвариантов и публичных DTO:

- `dataModel/sourceVersioning/_proofResultValueRules.py::duplicate_ref_positions(refs: tuple[ArtifactRef, ...]) -> tuple[int, ...]` возвращает позиции повторных occurrences после первого. Preconditions: все переданные refs валидны.
- Тот же модуль: `has_matching_emptiness(proof_use_count: int, durable_ref_count: int) -> bool`; counts — non-negative int. Проверяет только согласованность пустоты, не равенство количества uses и refs и не полноту closure.
- POJO validator делегирует этим функциям, сохраняя strict/frozen отказ. Application не копирует их алгоритмы.

Concrete `proof/validation/sourceProofResultValueChecker.py::SourceProofResultValueChecker` имеет единственную ответственность — diagnostics этих двух relations, без IO, canonical proof или вычисления closure. Constructor `__init__(self) -> None`. Метод:

```python
def check[RootT: BaseModel](
    self, *,
    refs: tuple[tuple[int, ArtifactRef, CheckedPath[RootT, ArtifactRef]], ...],
    proof_use_count: int | None, durable_ref_count: int | None,
    refs_path: CheckedPath[RootT, tuple[ArtifactRef, ...]],
) -> tuple[SourceFieldIssue, ...]: ...
```

Counts относятся к исходным structurally пригодным контейнерам, не к отфильтрованным facts. None значит контейнер уже диагностирован и недоступен; emptiness проверяется только при обоих counts. Duplicate predicate получает пригодные refs, затем его позиции отображаются на original indices/paths; непригодный ref не скрывает дубликат соседних пригодных refs. Отрицательные counts, повторные/неупорядоченные позиции facts — programming error. Request GroupVerification checker получает этот checker отдельным обязательным constructor dependency `result_values` и вызывает после допуска ArtifactRef, до matcher/IO. Другие четыре request checkers его не получают.

**Явное дополнение error mapping для приёмки:** duplicate durable ref → INVALID_SHAPE на повторном durable_refs[i]; несовместимая пустота proof/refs → INVALID_SHAPE на durable_refs. Это local value refusal по существующему carrier, а не DUPLICATE_IDENTITY (у него иная семантика) и не CLOSURE_MISMATCH до вычисления closure. §11.3 spec не перечисляет эти две relations отдельными строками: данное уточнение нужно принять и синхронизировать при консолидации, оно не объявляется уже принятым изменением spec. После IO CLOSURE_MISMATCH сохраняет только установленный смысл missing/extra относительно computed refs.

Критерий отказа: checker повторяет set/empty алгоритмы вместо общих predicates, принимает filtered length за original count, вычисляет closure или дублирует уже выданный structural diagnostic. Матрица: (A, invalid, A) сохраняет duplicate на позиции 2 и отдельный structural отказ позиции 1; empty proof + nonempty refs; nonempty proof + empty refs; malformed proof uses не мешает duplicate check; failure не допускает matcher/IO.

## 6. Проверки и предел завершения

Обязательные design/implementation cases: повреждённая revision + invalid descriptor в одной dependency; malformed capture.artifact + WRONG_WORLD в соседней identity; неверный UUID + invalid revision; повреждённая группа 0 без выбора replacement world; неверные selection scalar/order при непригодном proof; два out-of-range индекса → одна logic issue; исходные count при skipped элементах; root extra без fake path; ArtifactRef после отказа не попадает в SourceLogicIssue.artifact; никакого model_construct/semantic checker из traversal и ноль transform/IO при failure.

Документ закрывает детализацию входов/результатов leaf/root/group обхода как **проект**, но не приёмку SRC-AR-04. Identity/Selection signatures синхронизированы с source-core-checker-signatures.md; result value owner задан в §5.1. До закрытия нужны приёмка дельт и синхронизация diagnostic mapping с основным proof spec. Актуализация 2026-11-22: разделение request/persisted validation уже принято, выбор не OPEN; original-request maps описаны в source-core-occurrence-mapping.md и возвращаются request checker. Старый Source read lifetime отозван; внешний остаток — X-READ materialized data/protection/producer binding по source-closure-operands-2026-11-22.md. Общая архитектура и код не объявляются принятыми; локальный implementation-срез не создаётся.
