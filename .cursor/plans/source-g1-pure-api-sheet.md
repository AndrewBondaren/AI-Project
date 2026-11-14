# Source G1.3 — внутренние pure API для приёмки

2026-11-14. DRAFT конкретных сигнатур, требуемых §5/7 source-g1-values-canonical-implementation.md. Это продолжение Source после поставки POJO для Pack 3a, не переоткрытие принятого proof/error контракта. Код этих компонентов данным документом не разрешён. Нормативная семантика — source-proof-v2-contract-spec.md §6.H, 9.2, 10.1–3, 11.3–4; S1 check_coverage остаётся отдельным следующим слоем.

## 1. Что уже определено, а что требует приёмки

Закрыто спецификацией: внешний roster POJO, identity categories, semantics descriptor/key, правила canonical ordering, historical revisions, empty proof/usage, selection atoms, единый error roster и порядок diagnostics. Новые коды, варианты proof и методы публичного pipeline здесь не предлагаются.

Предъявляется на приёмку: конкретные внутренние signatures и constructor dependencies. Не закрывается автоматически: регистрация реальных owning bindings с подтверждёнными body codec/projector/key contracts. Наличие текущего TerrainRegistryEntry.system_terrain — evidence существующего кода, не принятие будущего owning execution или DAG контракта.

Все пути application ниже под `app.application.worldData.sourceVersioning`. Ни один класс не является открытым pipeline, не запускает другую публичную операцию и не вызывается напрямую Pack. Будущий Source pipeline передаёт уже предъявленные значения своим internal collaborators; DAG передаёт публичные inputs/results между доменами.

## 2. Ошибки — применение принятого контракта

Единственный public carrier — `app.dataModel.sourceVersioning.sourceErrors` по §11.3: SourceFieldCode/Issue, SourceLogicCode/Issue, SourceOperation/Failure. SourceFailure — значение результата, не новый Exception subclass. Helpers собирают concrete issues через existing ValidatorAggregationHelper и формируют SourceFailure с исходной operation; инфраструктурные исключения не перехватываются как domain absence.

Структурный Pydantic отказ на невалидном корне request допускается §11.3. Нельзя фабриковать пустой field path. Это не освобождает owning pure boundary от Source diagnostics для доступных nested fields и семантических проверок. Перед реализацией каждого check применяется существующая таблица condition→code из §11.3; строки ValueError не используются как ключи классификации. Typed selectors FieldRef/bind_field и CheckedPath привязаны к конкретному исходному request; group/use indices сохраняются до normalization.

Порядок: независимые field failures в порядке полей/исходных индексов; logic world → descriptor → capture → dependency → selection → closure. Зависимую ветвь пропустить при нарушении prerequisites, остальные groups продолжить. Pure компоненты не выполняют closure IO. Исключения shape самого SourceFailure/issue POJO остаются ошибками построения values, не рекурсивным SourceFailure.

## 3. Descriptor/key boundary

Модуль `contracts/descriptorBindings.py`:

```python
class SourceDescriptorBindingRegistry:
    def __init__(self, definitions: SourceDescriptorRegistry,
                 key_bindings: tuple[SourceDescriptorKeyBinding, ...]) -> None: ...
    def definition(self, key: SourceDescriptorKey) -> SourceDescriptorDefinition | None: ...
    def key_binding(self, key: SourceDescriptorKey) -> SourceDescriptorKeyBinding | None: ...
```

`SourceDescriptorKeyBinding` — internal immutable runtime binding, не dataModel/wire record: `descriptor: SourceDescriptorKey`, `adapter: SourceIdentityKeyAdapter`. `SourceIdentityKeyAdapter` — internal abstract base в том же модуле, `validate_exact(self, identity: SourceObjectId) -> SourceFieldCode | None`; допустимый отрицательный результат только INVALID_IDENTITY. Lookup category/scope/world/unknown descriptor выполняет validator, adapter не выпускает SourceFailure и не меняет operation/path. Adapter не проверяет captured membership и не читает latest. Definition и binding roster immutable после создания; duplicate/unknown binding key, отсутствующий обязательный adapter и несовместимая category — отказ registration до использования registry.

Для concrete owning adapters необходимо предъявить точный тип owning key и реализацию strict validation + exact wire round-trip. Enum wire token проверяется owning enum, RegistryKey — owning annotation/constraints; произвольный TEXT passthrough запрещён. Для library UUID обязательна canonical lowercase hyphenated форма и owning validation. SourceMemberKey не становится owning RegistryKey. Application может зависеть от подтверждённых owning value contracts; sourceVersioning dataModel — нет.

**Незакрытая часть G1-BIND:** этот key-facing API является проекцией полной композиции §10.1, которая также содержит body codec/format и semantic projector. Их concrete registration нельзя заменить этой проекцией или пустым adapter. Полная композиция и точные concrete adapters должны быть предъявлены до снятия G1-BIND. Здесь не утверждаются guessed Terrain adapter, universal Any/dict validator или новая версия owning контракта. Точный нерешённый вопрос: какие подтверждённые owning key/body/projector bindings входят в первую production composition. Он принадлежит Source composition с согласованием выбранного owning домена; не Pack.

### 3.1. Ответ владельца Terrain — 2026-11-14

Получен ответ из owning чата `01a1d6e7-7dc4-71c0-a570-5abda0bffe62` на явно разрешённую пользователем ограниченную сверку. **G1-BIND остаётся OPEN по конкретным зависимостям ниже.** Это фиксация ответа, не приёмка нового Terrain/DAG контракта.

- Подтверждён тип `RegistryKey[WorldTerrainRegistry]` (alias TerrainKey), поле `TerrainRegistryEntry.system_terrain: StrictOnWire[RegistryKey[WorldTerrainRegistry]]`, shared `RegistryKey.__get_pydantic_core_schema__`. Основание — docs/tz_json_validation.md, RegistryKey. Это не concrete owning exact-validator: StrictOnWire является annotation policy, а Python instance branch RegistryKey не доказывает повторную проверку всех ограничений. Принятой exact-validator signature пока нет.
- `/membership` имеет Source key_kind=NONE: отдельный terrain member key adapter для него не нужен. Member keys проверяются через `/member`; наличие подтверждается captured membership, не latest.
- Приняты hills_authored, запрет legacy adaptation и bootstrap из явно подготовленных authored-записей нового strict контракта. Полные body codec/projector не приняты. `terrain.source-entry v1`, `TERRAIN_SOURCE_SCHEMA_V1`, full19 body — proposals; all19 semantic/exclusions empty/SEQUENCE — recommendations. Existing CanonicalCodec и registrations17–23 — evidence, не приёмка этих предложений. Открыты concrete codec/format registration, exact semantic projector encoding/composition и real vectors.
- Актуальный §4 Terrain dossier снял прежние TerrainSourceAdapter/TerrainSourceError/integration signatures. Их нельзя использовать как согласованные API. Нынешние mutable eligibility, extra ignore, model_fields_set presence и list root реестра — свойства текущего кода, не готового durable контракта. Предложенный выше SourceIdentityKeyAdapter остаётся Source DRAFT и не подтверждённым Terrain API.

Следующий необходимый внешний результат: принятые owning exact key validation и body codec/projector contracts выбранного Terrain scope. Source затем фиксирует concrete composition/registration; текущий код не адаптируется как legacy. Реализация Terrain, writer/storage/DAG и миграция реестра этим уточнением не разрешены. Поставленные Pack POJO imports от этой зависимости не зависят.

## 4. SourceProofValidator

Модуль `proof/validator.py`, constructor `SourceProofValidator(bindings: SourceDescriptorBindingRegistry)`. Canonical codec создаётся внутри по единственному SOURCE_PROOF_SCHEMA_V1; caller не подаёт manifest/codec. Предлагаемые методы:

```python
def validate_input(self, request: SourceProofInput,
                   operation: SourceOperation) -> None | SourceFailure: ...
def validate_groups_input(self, request: SourceProofGroupsInput,
                          operation: SourceOperation) -> None | SourceFailure: ...
def validate_read(self, request: SourceProofReadInput,
                  operation: SourceOperation) -> None | SourceFailure: ...
def validate_select(self, request: SourceProofSelectInput,
                    operation: SourceOperation) -> None | SourceFailure: ...
def validate_groups_result(self, request: SourceProofGroupsVerifyInput,
                           operation: SourceOperation) -> None | SourceFailure: ...
```

Typed request root сохранён каждым методом. Общие private checks переиспользуются, публичные Source операции не вызываются. validate_input/groups_input допускают declared repetitions и empty usages; проверяют world/descriptor/key и конфликт revisions в одном capture без исправления input. validate_read требует persisted canonical proof. validate_select дополнительно проверяет fingerprint/index shape/bounds. validate_groups_result проверяет shape/world/canonical формы, число selections и их связь с proof; exact union/group matching выполняет selector после этих checks. Нельзя объявлять validate_groups_result проверкой computed durable closure.

Decoded-capture checks сохраняют точный исходный request. Предлагаются отдельные entry methods для declared single/groups и persisted read; они переиспользуют один private алгоритм проверки готового capture:

```python
def validate_input_capture(self, request: SourceProofInput,
                           use_index: int, witness: SourceCaptureWitness,
                           capture: SourceCapture,
                           collection_bodies: tuple[SourceCollectionBody, ...],
                           operation: SourceOperation) -> None | SourceFailure: ...
def validate_group_capture(self, request: SourceProofGroupsInput,
                           group_index: int, use_index: int,
                           witness: SourceCaptureWitness, capture: SourceCapture,
                           collection_bodies: tuple[SourceCollectionBody, ...],
                           operation: SourceOperation) -> None | SourceFailure: ...
def validate_read_capture(self, request: SourceProofReadInput,
                          use_index: int, witness: SourceCaptureWitness,
                          capture: SourceCapture,
                          collection_bodies: tuple[SourceCollectionBody, ...],
                          operation: SourceOperation) -> None | SourceFailure: ...
```

Индексы относятся соответственно к request.uses, request.groups[group_index].uses и request.proof.uses. Недопустимый internal index является programming error, не fabricated source issue. Private алгоритм получает usage, typed path к нему и исходные group/use indices от entry method; не выводит их из normalized proof. Ready decoded values поставляет будущая owning IO stage. Проверяются world, exact mapping и membership по предъявленным значениям; committed finalization, seal и доступность bytes не доказываются. Mapping artifact→decoded value и доверенный источник witness доказывает read binding.

Эти методы возвращают issues для одного use; вызывающая внутренняя стадия обязана собрать отказы остальных доступных uses/groups до возврата общего SourceFailure. Она не делает ранний return на первом отказе. IO порядок и bindings SELECT/VERIFY_GROUPS не вводятся этим pure sheet: их diagnostic root остаётся исходный SourceProofSelectInput/SourceProofGroupsVerifyInput; подмена его синтетическим SourceProofReadInput запрещена. Полные decoded entry signatures для этих двух roots необходимо предъявить в соответствующем IO-срезе до его кода, а не считать покрытыми validate_read_capture.

## 5. SourceProofNormalizer

Модуль `proof/normalizer.py`, constructor `SourceProofNormalizer(validator: SourceProofValidator)`. Предлагаемая сигнатура:

```python
def normalize(self, request: SourceProofInput,
              operation: SourceOperation) -> SourceDurableProof | SourceFailure: ...
```

Вызов внутреннего validator перед normalization обязателен; return failure до зависимого вычисления. Canonical grouping/dedup/order по §9.2, разные revisions между captures сохраняются. Не создаёт SourceProofResult и не синтезирует durable_refs. Не нормализует предъявленный persisted proof. Private group normalization переиспользуется selector после проверки всех исходных groups; не теряет original diagnostic indices.

## 6. SourceProofSelector

Модуль `proof/selector.py`, constructor `SourceProofSelector(validator: SourceProofValidator, normalizer: SourceProofNormalizer)`. Canonical schema фиксирована внутренней композицией. Предлагаемые методы:

```python
def union_groups(self, request: SourceProofGroupsInput,
                 operation: SourceOperation) -> SourceProofGroupProjection | SourceFailure: ...
def select(self, request: SourceProofSelectInput,
           operation: SourceOperation) -> SourceDurableProof | SourceFailure: ...
def match_groups(self, request: SourceProofGroupsVerifyInput,
                 operation: SourceOperation) -> None | SourceFailure: ...
```

`SourceProofGroupProjection` — единственный новый internal pure result в `proof/groupProjection.py`, frozen runtime dataclass: `proof: SourceDurableProof`, `selections: tuple[SourceProofSelection, ...]`. Это результат вычисления без closure, не зеркало SourceProofGroupsResult: нет admission или durable_refs и не может быть передан вместо публичного результата. В dataModel/canonical manifest/Pack не экспортируется. IO stage позднее использует proof для durable checks, после чего формирует existing SourceProofGroupsResult. Отказ при review: использование этой projection как admitted evidence либо добавление фиктивного SourceProofResult с пустыми refs.

union_groups сначала проверяет все groups с исходными индексами, затем вычисляет exact union и selections в исходном порядке. select проверяет предъявленный proof/selection и возвращает самостоятельный persisted proof, не durable result. match_groups сравнивает normalized expected union и каждую selection с соответствующей группой; не подтверждает равенство computed closure. Pure атомы и fingerprint не экспортируются Pack, не появляются новые публичные EXTRACT_USAGE/MATCH_GROUPS.

## 7. Приёмка API sheet и порядок реализации

| Класс / shared зависимость | Ответственность / эффекты | Основание отказа |
|---|---|---|
| SourceDescriptorBindingRegistry / SourceDescriptorKeyBinding | Immutable Source composition lookup; no IO | Подмена полного owning binding пустым key adapter; mutable registration; unknown descriptor принят |
| SourceIdentityKeyAdapter и будущие concrete adapters | Exact owning key validation/round-trip | Permissive TEXT, normalization, latest lookup, отсутствие concrete owning evidence |
| SourceProofValidator | Проверки предъявленных values + Source diagnostics | IO, fake finalization, ранний отказ с потерей независимых issues |
| SourceProofNormalizer | Нормализация declared input | Переписывание READ proof, смешение historical revisions, fake closure |
| SourceProofSelector / SourceProofGroupProjection | Union/subset/group matching без IO | Подмена public durable result, потеря group correlation, зависимость от Pack |
| CanonicalCodec / SOURCE_PROOF_SCHEMA_V1 | Existing encoding/digest по owning manifest | Другой hash engine, caller-supplied schema, отсутствие vectors |
| FieldRef/bind_field, CheckedPath, FieldPathError, ValidatorAggregationHelper | Existing typed paths/issue collection | raw string paths, mirror diagnostics, пустой фиктивный path |

Три запрета DAG соблюдаются отсутствием orchestration/public domain calls/IO в этом срезе. Public/internal граница описана в §1/4–6. Data/settings CRUD не вводятся и не считаются принятыми. Междоменные зависимости ограничены shared values и ещё подлежащими подтверждению owning bindings; новые ноды не проектируются. Source error roster переиспользуется целиком, не клонируется по helper.

После приёмки этого sheet и снятия G1-BIND: завершить G1.1 (оставшиеся values, requests, errors) → G1.2 manifest/vectors → G1.3 pure checks/normalization/selection → независимая приёмка G1. До этого разрешённая поставка POJO Pack сохраняется, но весь G1 не закрыт.

Матрица проверки следующей реализации: strict nested revalidation; несколько независимых field/logic issues с точными paths/order; отсутствие dependent computation после failure; unknown/mismatched descriptor; key normalization refusal; full capture equality и historical revisions; declared vs persisted ordering; empty worlds; bounds/fingerprint/group-count; exact union и каждый subset; подмена/перестановка selections; pure test doubles не считаются production owning bindings. Canonical tests берут буквальные vectors из §11.4. IO/holds/finalize не проверяются и не обещаются pure тестами.

## 8. Локальная проверка последовательности — 2026-11-14

Это собственная проверка проекта API, не независимая приёмка. Исправлена потеря diagnostic root: первоначальный единственный validate_capture(SourceProofReadInput, ...) не мог обслужить ADMIT_GROUPS с исходными индексами без неявной подмены request. Теперь declared single/groups имеют отдельные typed entry methods; общий private алгоритм не создаёт публичных операций.

Разделение фактических зависимостей:

| Работа | Нужен принятый Terrain body/projector? | Основание |
|---|---|---|
| Source error roster §11.3 | Нет | Именованные Source diagnostics используют уже существующие shared paths и Source refs |
| Оставшиеся Source body/capture/witness value declarations и read/select/verify requests | Нет | Body представлен ArtifactRef, owning Terrain body не копируется и не декодируется |
| SOURCE_PROOF_SCHEMA_V1 и literal vectors | Нет | Manifest регистрирует Source values и shared ArtifactRef, не Terrain body codec |
| Production descriptor admission и полная binding composition | Да | Нужны утверждённые owning exact-key/body/projector contracts; пустой adapter не замена |
| Durable read/finalize/closure | Да, и отдельные storage/format/retention зависимости | Не входит в текущую поставку pure foundation |

Следовательно, Terrain не является техническим prerequisite declarations и Source canonical manifest. Однако §7 текущего G1-плана требует принять полный API/G1-BIND до кода вне отдельно разрешённых Pack POJO. Это процессное ограничение нельзя молча отменить выводом этой таблицы.

Предлагаемый следующий ограниченный срез на утверждение: завершить G1.1 declarations (включая единый sourceErrors) и G1.2 Source manifest/vectors до закрытия production G1-BIND. Scope и критерии уже заданы §3/4/6 G1-плана; добавить только явное исключение порядка для этих пунктов. G1.3 semantic diagnostics, owning adapters, union/subset/closure, storage/finalizer/DAG и код Pack не входят. TODO перехода к typed semantic diagnostics не снимаются одним созданием sourceErrors.py. Приёмка этого среза не закрывает G1 целиком.

### 8.1. Точные prerequisites потребителя Snapshot

Получен readiness Source 2; повторная локальная проверка 2026-11-14 подтверждает **NOT READY для request encoding registration**. Основание — [proposal §1](source-2-snapshot-request-encoding-proposal.md#1-baseline-и-граница-решения). Это отдельная готовность от уже поставленных Pack 3a POJO.

1. В `app.dataModel.sourceVersioning.sourceProofInput` отсутствует `SourceProofReadInput(world_uid: EntityUid, proof: SourceDurableProof)`. Его поставляет оставшийся G1.1; SourceProofInput не является заменой.
2. Отсутствует `app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1.SOURCE_PROOF_SCHEMA_V1` и application directory. Его поставляет G1.2 после полного transitive Source value roster; обязательны accepted IDs/field order, V0/V1 bytes и round-trip. Одно объявление пустого manifest не закрывает prerequisite.

По readiness владельца UUID и PACK_PIN_SCHEMA присутствуют; их не переоткрывать как Source blocker. После поставки и проверки двух указанных imports Source 2 повторяет readiness и выполняет свой отдельно разрешённый registration/composition срез. Его proposed request ID 71201 и request manifest не включаются автоматически в SOURCE_PROOF_SCHEMA_V1 или текущую Source поставку. Здесь не меняются Source 2 proposal, Snapshot ledger или Pack code. Отсутствие этих dependencies не устраняется mirrors/lazy imports/fallback.
