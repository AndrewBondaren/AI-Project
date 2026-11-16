# Pack: инвентарь canonical graph prepare/manifest

2026-11-16. Статическая сверка текущего кода и контрактов. Runtime/IDs не менялись; полной собранной схемы пока нет, поэтому отсутствие коллизий всей будущей composition не заявляется. Это следующий контрактный вопрос после принятого batch, не повтор его приёмки.

## Корни и границы

Проект `PackPreparationInput(operation_id, preparation_fingerprint, body)` содержит `PackPreparationBody(state: PackPreparationState, capture: SourceCaptureRef, scope: PackPreparationScope)`. Operation identity находится вне semantic body. World определяется state.base_publication. Не вводить зеркальные поля состава наверху body.

State в коде наследует `_PackCompositionFields(parts, assembly, assembly_provenance)` и добавляет base_publication и metadata_dependencies. Manifest должен использовать единственную декларацию состава, но не автоматически сериализовать transient descriptions или всю оболочку state. Точное включение pending dependencies в semantic fingerprint после bind требует явного правила: присутствие поля в state не доказывает его принадлежность durable manifest.

Current `WorldPackManifestV2` в `meta/worldPackManifest.py` ещё объявляет pack_version literal 2.0.0 и старые manifest fields. Это не готовая модель принятого single-manifest target wire 3.0.0/storage 2. JSON codec и canonical TLV registration — разные границы; работоспособный JSON codec не доказывает регистрацию prepare graph.

## Проверенные declarations

Пути относительно `backend/app/`. «Не найдена» означает результат статического поиска регистраций, не назначение нового ID.

| Тип / группа | Владелец | Схема / ID в коде | Действие Pack |
|---|---|---|---|
| ArtifactKind / ArtifactRef | Artifacts | `application/artifacts/encoding/coreManifest.py`: 20003 / 20107; те же owners/IDs в SOURCE_PROOF_SCHEMA_V1 | Переиспользовать, не перенумеровывать |
| WorldPublicationRef | Snapshot/publication | ARTIFACT_CORE_SCHEMA: 20103 | Переиспользовать для state.base_publication |
| SourceCaptureRef | Source | `application/worldData/sourceVersioning/encoding/sourceProofSchemaV1.py`: 71129 | Existing body.capture type, без surrogate |
| SourceCaptureUsage / SourceDurableProof / SourceProofSelection | Source | Та же схема: 71130 / 71131 / 71138 | Existing usage/proof/attribution leaf graph |
| SourceRevision / SourceVersionRef / SourceCollectionVersionRef / SourceDependencySet | Source | Та же схема: 71120 / 71121 / 71122 / 71123 | Транзитивные owning declarations |
| SourceBodyVersion / SourceCollectionVersion / SourceCollectionBody / SourceCapture / SourceCaptureWitness | Source | Та же схема: 71124–71128 | Не копировать объявления и не менять proof composition |
| SourceDescriptorCategory; RegistryMemberId / LibraryMemberId / EntityObjectId / SourceSettingsId / SourceCollectionId | Source | Та же схема: 71001; 71110–71114 | Existing discriminated leaf graph |
| SourceProofReadInput | Source | `sourceProofRequestSchemaV1.py`: 71201; merged SOURCE_PROOF_REQUEST_ENCODING_V1 | Это READ request, не замена SourceProofInput |
| SourceProofInput | Source | POJO существует; в просмотренных proof/request схемах регистрация не найдена | Нужен точный owning binding, если этот тип включается в fingerprint/transport pending descriptions; не назначать Source ID внутри Pack |
| PlanRef / PlanDependency | Planning | `application/worldData/planning/encoding/surfaceBindings.py`: 94 / 101 | Переиспользовать owning declarations и их транзитивные зависимости; отсутствие DAG integration Planning не запрещает owning POJO |
| ValidatedFieldPath / ModelIdentity / FieldSegment / VariantSegment / IndexSegment / KeySegment | Fields | `dataModel/fields/encoding/surfaceBindings.py`: 303–308 | Нужны диагностике/typed paths, не добавлять автоматически в semantic body без достижимости |
| ManifestPinRead | Pack | `dataModel/worldPack/encoding/pinBindings.py`, PACK_PIN_SCHEMA: 20205 | Existing pin boundary; не считать регистрацией body/manifest |
| ParentLightRefinePolicy | Pack | `dataModel/worldPack/encoding/surfaceBindings.py`: 198 | Existing отдельное объявление; не полный Pack graph |
| PackPreparationBody / PackPreparationScope | Pack | Body заявлен проектом; exact runtime class/root registration не найдены | Завершить concrete shape и затем декларации Pack |
| PackPreparationState / PackStoredPart / PackStoredProvenance | Pack | POJO существуют, canonical registrations не найдены | Pack-owned records будущей composition |
| PackAssemblyInput / PackTileAssembly / PackChunkAssembly и остальные assembly records | Pack | POJO существуют, полной canonical composition не найдено | Поимённо перечислить достижимые leaf types, включая чужие territory/region values |
| PackStoredAssemblyProvenance / PackMetadataAttribution / PackMetadataGroupAdmission / PackWildernessStatusBasis / PackMetadataGroup | Pack | POJO существуют, canonical registrations не найдены | Durable metadata graph, отличать records от enum |
| PackMetadataSubject / PackMetadataDescription / PackMetadataDependencyUse | Pack | POJO существуют, registrations не найдены | Отдельный transient/metadata fingerprint graph; решить включение в prepare digest |
| Конкретные part/metadata addresses | Pack | POJO существуют, registrations не найдены | Каждый concrete record отдельно; union aliases без собственного ID |
| Целевой single manifest | Pack | Current JSON models не являются целевой canonical registration | Предъявить точную целевую root declaration и reachable graph |
| PreparedPackCandidate / PackActivationInput | Pack | POJO существуют; production canonical registrations статическим поиском не найдены | Отдельный lifecycle/activation graph; предложенные ранее IDs не объявлять runtime-регистрацией |

## Коллизии и что уже нельзя делать

По [раннему audit](pack-canonical-registration-audit.md), полный SURFACE_MANIFEST и SNAPSHOT_CORE_SCHEMA нельзя слепо объединять: shared validation owners имеют разные IDs в независимых storage схемах (например FieldPathError 106 и 20137). В этой сверке подтверждены существующие Artifacts/Source shared ArtifactRef IDs и Fields declarations; полный новый merge не выполнялся.

Проверка будущей composition должна отвергать: один ID для разных owners, один owner с разными IDs, enum/record kind mismatch, отсутствие concrete subtype, недостижимую ModelIdentity при восстановлении diagnostics. Совпадение чисел лишь в рассмотренных строках таблицы не является PASS всего графа. Не вводить глобальный allocator и не перенумеровывать чужие сохранённые схемы.

## Точный остаток этого вопроса

1. **Pack:** завершить semantic-body inclusion policy для state.metadata_dependencies и coverage. Write-план прямо отмечает wilderness/settlement coverage additions как ещё не утверждённые: нельзя молча добавить их или поставить пустые defaults ради encoding. Отделить собственную shape-конкретизацию от будущих producer bindings.
2. **Pack:** предъявить полный reachable roster target body/manifest и минимального metadata fingerprint graph, назначить только Pack-owned IDs после проверки существующих диапазонов/предложений. Не назначать IDs `_PackCompositionFields` и union aliases вместо concrete values.
3. **Source:** если transient usage входит в сериализуемый graph, уточнить owning регистрацию SourceProofInput; подтверждённая SourceProofReadInput=71201 не решает этот вопрос. Запрос должен указывать назначение: pending descriptions/metadata fingerprints, не новая Source операция.
4. **Pack:** проверить реальную composition на collisions и составить контрактные vector cases. Вычисление runtime vectors следует отдельной реализации, не требует временных моделей/успешных заглушек сейчас.

Итог: имеющиеся регистрации отделены от проектных. Полный canonical graph ещё не принят; новые номера не выбраны автоматически. Это локальный serialization-срез, не общий блокер независимого Pack. Настройки Cache, wire/storage версии, exact READY candidate replay и последний порядок DAG integration не пересматриваются.
