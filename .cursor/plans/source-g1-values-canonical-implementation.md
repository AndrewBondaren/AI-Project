# Source G1 — базовые значения, canonical schema и pure validation

2026-11-14. **G1.1 → G1.2 разрешены пользователем до закрытия G1-BIND; полный G1 остаётся незавершённым.** Решение передано через Source 2 и зафиксировано в §7; оно расширяет прежнее исключение POJO для Pack 3a. G1.3/pure semantic composition требует собственного закрытия G1-BIND. Основной план world-source-versioning.md сохраняет порядок inventory → owning contracts/projector → revisions/history/retention → finalize → integrations. Наличие POJO/manifest не означает завершения G1 или разрешения S1/runtime.

## 1. Источники и проверенное состояние

Нормативная форма — source-proof-v2-contract-spec.md §6.A–H, §9.2, §10.1–3, §11.3–4, §13; принятая S1/S2 редакция source-pack-s1-s2-contract.md. Обязательная приёмка — dag-generator-interface.mdc. Применимые shared SoT: docs/tz_json_validation.md (strict validation/RegistryKey), docs/tz_world_snapshot.md (shared ArtifactRef/identity), docs/tz_world_pack_storage.md (consumer provenance). Перед реализацией прочитать план/skill и нормативные источники, сверить конкретные shared declarations. Алгоритмы и таблицы IDs не переопределять в этом плане.

Факты preflight: Source runtime directories отсутствуют; existing shared dependencies присутствуют. RegistryKey — backend/app/dataModel/registryKey.py, EntityUid — dataModel/identity/uid.py, RevisionHex — dataModel/validation/diagnostics/runtimeIssueContext.py, ArtifactRef/Kind — dataModel/artifacts/references.py. EntityUid не гарантирует canonical UUID. CanonicalSchemaManifest/RegisteredTypeEntry — dataModel/encoding/schemaManifest.py; encoder/digest/merge — app/encoding/canonicalCodec.py. Актуальный aggregation helper — dataModel/validation/diagnostics/validatorAggregationHelper.py, а не исторический app.core import.

Готовность owning descriptor/key-adapter application composition не доказана: §10.5 называет роль SourceDescriptorBindingRegistry, но не даёт полного concrete typed API adapters. Нельзя молча реализовать permissive TEXT/UUID stub вместо owning validation. Это отдельный завершающий gate G1-BIND ниже, а не основание расширить задачу до Terrain writer.

## 2. Scope и непересекающиеся обязанности

Внутри: Source value declarations с полной структурной валидацией; Source error roster; единственный persisted proof/capture/selection manifest; canonical round-trip/golden/negative tests; конкретизация pure validation boundary перед её реализацией. Вне: storage/SQL, reads/closure IO, finalizer/adopt, public pipelines/API/DAG, Pack metadata, Snapshot issuer/binding codec, mutation/recovery implementation, owning Terrain POJO/projectors/writers и legacy adapters. Никаких «готовых» durable результатов из pure builder.

Public здесь означает импортируемое значение, не публичную операцию. G1 не создаёт методы ADMIT/READ/SELECT с заглушками. SourceProofResult можно структурно валидировать как POJO, но его создание не доказывает computed closure. SourceCaptureWitness можно представить как кандидат; POJO не подтверждает committed finalization.

## 3. G1.1 — значения и structural validation

Все пути ниже под backend/app/dataModel/sourceVersioning. Каждый record: frozen/strict/extra-forbid/revalidate-always, обязательные nullable поля без defaults, tuple collections. Точный состав и порядок — ссылки на принятую спецификацию; одна декларация на тип, без mirrors.

| Файл | Типы / источник полей | Ответственность и отказ в приёмке |
|---|---|---|
| sourceDescriptor.py | SourceDescriptorCategory/Scope, SourceMemberKeyKind, SourceCollectionOrder, SourceDescriptorKey, SourceMemberKey, SourceDescriptorDefinition/Registry; §10.1 | Immutable descriptor config/nominal tokens. Проверять category/scope/key_kind, collection order/member roster, duplicate/unknown descriptors; нельзя размещать codec/callback/DB в POJO |
| sourceObjectId.py | RegistryMemberId, LibraryMemberId, EntityObjectId, SourceSettingsId, SourceCollectionId, SourceObjectId union; §10.2 | Exact nominal identity; collection исключена из object union. Нельзя импортировать owning registry POJO, добавлять label/pack UID либо трактовать EntityUid как UUID validator |
| sourceObjectRevision.py | SourceRevision(seq, content_hash); §10.2 | Semantic version value; bool/seq≤0 запрещены, hash не вычисляется из body автоматически |
| sourceVersionRef.py | SourceVersionRef и SourceCollectionVersionRef; §10.2 | Раздельные object/membership refs; смешанная запись отклоняется |
| sourceDependencies.py | SourceDependencySet(objects, collections); §10.2 | Typed relation data; не ищет membership/latest, не сортирует declared input молча |
| sourceBodyVersion.py | SourceBodyVersion, SourceCollectionVersion; §10.2 | Только exact mapping source→ArtifactRef; не размещает/читает bodies |
| sourceCollection.py | SourceCollectionBody(collection, members); §10.2 | Структура состава; порядок SET/SEQUENCE проверяет pure descriptor-aware слой, не generic автосортировка |
| sourceCapture.py | SourceCapture(world_uid, objects, collections); §10.3 | Value mappings; доступность decoded collection bodies проверяется позднее, не обещается POJO |
| sourceCaptureWitness.py | SourceCaptureWitness(capture_uid, world_uid, capture_body); §10.3 | Кандидат finalize, не trusted committed evidence |
| sourceCaptureRef.py | SourceCaptureRef(world_uid, artifact); §6.A/10.3 | Witness ref shape/формат, не capture-body ref и не holder |
| sourceCaptureUsage.py | SourceCaptureUsage(capture, dependencies); §6.A | Declared dependencies конкретного capture; не full read-set certificate |
| sourceDurableProof.py | SourceDurableProof(schema_version, world_uid, uses); §6.A/11.4 | Persisted shape, не authority. Literal[1] дополнен exact-int before check против bool |
| sourceProofInput.py | SourceProofInput, SourceProofReadInput; §6.A | Declared input и read request имеют разные validation rules; read не normalizes proof |
| sourceProofResult.py | SourceProofResult(proof, durable_refs); §6.A | Value результата durable операции, без IO/verification/hold при construction |
| sourceProofSelection.py | SourceProofSelection, SourceProofSelectInput; §6.G | Exact fingerprint/strict sorted unique nonnegative indices; bounds требуют конкретный proof |
| sourceProofGroups.py | SourceProofGroupsInput/Result/VerifyInput; §6.G | Correlation по original groups; nonempty groups/same world, без запуска public admission |
| sourceErrors.py | SourceFieldCode/Issue, SourceLogicCode/Issue, SourceOperation/Failure; §11.3 | Один общий Source error contract; concrete FieldPathError subclass, stable nullable context, nonempty failure |

Enum roster включает уже принятый CHECK_COVERAGE. Последующий слой A S1 переиспользует его, не добавляет второй раз. CoverageCheckInput и метод check_coverage остаются слоем A, не входят в G1. Unknown descriptor/body membership/real format availability нельзя считать пройденными из-за успешного POJO construction. Structural Pydantic refusal остаётся structural refusal; domain diagnostics строятся в pure boundary с typed paths.

Зависимости импортов: shared leaves → descriptor/identity/revision → version refs/mappings → capture/usage/proof → input/result/selection/groups/errors. DataModel не импортирует application canonical manifest ради semantic ordering: иначе manifest→POJO→manifest cycle. Canonical/descriptor-aware validation выполняется после появления schema в G1.3. Private base model допускается только как локальная реализация общей configuration, без нового public value/registry.

## 4. G1.2 — единственная proof canonical schema

Production path: backend/app/application/worldData/sourceVersioning/encoding/sourceProofSchemaV1.py; export SOURCE_PROOF_SCHEMA_V1. Точный roster §11.4: existing 20003/20107, 71001, 71110–71114, 71120–71131, 71138. Перед записью повторно проверить ID collisions и merge с актуальным ARTIFACT_CORE_SCHEMA. Owner/type/kind existing entries совпадают; full lifecycle schema в Source manifest не включать.

Никакого нового codec/hash engine. Existing CanonicalCodec encode/decode/content_digest должны воспроизводить literal V0/V1 vectors §11.4. Nominal SourceMemberKey/RegistryKey round-trip проверяется реальными типами, не scalar stand-ins; enum decode восстанавливает exact owner. Изменение shared encoding не делать «заодно» при ошибке round-trip — предъявить конкретный defect dependency.

Requests/results/errors/descriptor registry не входят в persisted proof schema, как требует §11.4. Настоящий SourceProofReadInput поставляется в G1.1 по §7, но не получает canonical ID из G1.2. После подтверждённых G1.1/G1.2 Source 2 продолжает отдельный request registration/composition/tests срез по source-2-snapshot-request-encoding-proposal.md (71201), не меняя proof bytes/IDs и не добавляя mirror. Наличие request POJO не считается готовой registration. UUID ManifestPinRead.store_id принадлежит отдельной Snapshot/Pack codec задаче и не основание менять Source proof schema.

## 5. G1.3 — pure semantics и G1-BIND

Конкретные signatures и границы предъявлены в [source-g1-pure-api-sheet.md](source-g1-pure-api-sheet.md). Статус DRAFT до приёмки. Error roster и semantics уже определены спецификацией §11.3; их повторное согласование не требуется. Оставшаяся production dependency G1-BIND — concrete owning adapters и полная key/body/projector composition, не наличие импортов для Pack.

Перед кодом слоя предъявить отдельный exact API sheet для уже названных SourceProofValidator (proof/validator.py), SourceProofNormalizer (proof/normalizer.py), canonical atom enumeration SourceProofSelector (proof/selector.py) и SourceDescriptorBindingRegistry (contracts/descriptorBindings.py). Пути под backend/app/application/worldData/sourceVersioning. Это Source-owned работа по конкретизации, не запрос Terrain придумать будущий DAG API.

В API sheet обязательны: signatures и inputs/results/errors; constructor dependencies; exact key-adapter contract/registration и strict round-trip; разделение structural validation, descriptor lookup и decoded-capture semantic checks; diagnostic root и aggregation stable order; отсутствие IO/projector calls в proof validation. Метод CHECK_COVERAGE не реализуется здесь; downstream A использует готовые helpers. Не придумывать universal dict/Any adapter, callback в public POJO или «все TEXT допустимы» fallback.

Pure responsibilities уже приняты: validator проверяет готовые Source/decoded POJO; normalizer группирует full capture, dedup declared exact refs, canonical sort, отказывает conflicting revisions внутри одного capture, сохраняет historical revisions между captures; selector enumerates canonical object/collection atoms без чтения body. Нормализация ADMIT input и отказ noncanonical persisted proof не взаимозаменяемы. Empty usage исключается из normalized input, но не принимается в persisted proof. Наличие dependency в captured membership проверяется по предъявленным decoded values, не latest/DB.

**G1-BIND OPEN:** §10.1 задаёт semantics owning key validation, но exact application adapter declarations/registration ещё нужно предъявить и принять. Ни G1.1/G1.2, ни тестовая stub registry не закрывают этот gate. После API sheet сверить актуальные owning key contracts; если нужна новая внешняя операция/изменение другого домена — остановка и конкретная зависимость пользователю. Не переносить эту дыру в реализацию S1.

Owning сверка Terrain обновлена 2026-11-15 в [API sheet §3.1](source-g1-pure-api-sheet.md#31-ответ-владельца-terrain--2026-11-14) и [binding proposal §5–6](source-g1-terrain-binding-proposal.md). Exact-key signatures/rules согласованы отдельно, реализация ещё не принята. Body layout, semantic policy, membership SET, concrete format registration и полная Source composition остаются открытыми. Старые TerrainSourceAdapter/TerrainSourceError/integration signatures отозваны; использовать их для закрытия gate запрещено. Это конкретный остаток G1-BIND, не новый блокер импортов Pack.

## 6. Проверки и outputs

Новые тесты под backend/tests/sourceVersioning:

- test_values.py: strict/frozen/extra/revalidation, обязательные nullable fields, bool/seq/version, unions, nominal keys/UUID без normalization, descriptor roster и nested malformed values. Source-owned fixture records создаются заново, не legacy conversion.
- test_canonical.py: literal V0/V1, реальный round-trip всего transitive roster, exact type IDs/field order, ID/owner collisions, перестановка manifest entries без изменения bytes, proof fingerprint меняется от exact capture/ref change; immutable shared fields reuse.
- test_pure_validation.py: после принятия G1.3 API — declared vs persisted distinction, duplicate/conflict/world/empty/historical cases, SET vs SEQUENCE, decoded membership mismatch, stable multiple independent SourceFieldIssue/SourceLogicIssue с typed paths. No storage/no authority assertions.

Fixtures — только новые in-memory values для pure tests. Они НЕ finalized fixtures G2, не создают SQL/catalog/holds и не объявляются lawful origin. Successful SourceProofResult fixture не считается выполненным durable read.

Typing files: backend/tests/typing/sourceVersioning/valid.py, invalid.py и pyrightconfig.valid.json/invalid.json. Config переиспользует project settings из существующих typing suites, включает точные новые Source paths; не меняет global typing policy. Проверить distinct object/collection refs, tagged unions, immutable tuple fields и nominal RegistryKey owner. Negative expected diagnostics фиксируются явно, не подавляются.

Команды после реализации: из backend `python -m unittest discover -s tests/sourceVersioning -p "test_*.py"`; из workspace `pyright -p backend/tests/typing/sourceVersioning/pyrightconfig.valid.json` и corresponding invalid config с проверкой ожидаемых diagnostics. Использовать настроенный project interpreter (existing configs Python 3.14); не устанавливать пакеты/менять окружение молча. Existing canonical regression: tests/planning/encoding/test_canonical_codec.py. Сервер не запускать. Текущим документальным проходом tests не выполнялись.

## 7. Порядок и приёмка

Следующий абзац — история первоначального исключения Pack 3a. Его ограничения и ссылка на прежний запрет первого кода заменены актуальным решением G1.1 → G1.2 ниже; не применять их как действующий gate read requests/encoding.

**Разрешённое пользователем исключение 2026-11-14 — POJO для Pack 3a.** До приёмки G1.3 отдельно поставляются SourceDurableProof, SourceCaptureUsage, SourceCaptureRef, SourceProofInput, SourceProofGroupsInput/Result, SourceProofResult, SourceProofSelection и их транзитивные descriptor/identity/revision/dependency типы. Для этого среза G1-BIND/API sheet не prerequisite. Ответственность классов и shared dependencies — §3; поля — спецификация §9.1/10.1–2. Проверки только структурные: strict/frozen/deep revalidation, обязательные поля, shape и локальные инварианты. Canonical ordering, owning descriptor admission, union/subset/closure и matching fingerprint остаются application ответственностью G1.3, не перемещаются в модели. Отдельные read/select/verify requests, error roster, capture body/witness, encoding, storage, finalizer, pipelines, adoption, DAG и Pack code в этот срез не входят. Порядок внутри среза: shared leaves → descriptors/identities/revisions → dependencies → proof/input/result/selection/groups → собственные runtime/typing проверки → отдельная независимая приёмка. Новых CRUD/междоменных вызовов нет, data/settings CRUD этим срезом не принимаются. Не вводятся дубли ошибок: структурный отказ — Pydantic ValidationError, domain diagnostics остаются будущей pure boundary. Этот результат не закрывает весь G1; запрет первого кода ниже сохраняется для остального полного среза.

**Актуальное решение пользователя, переданное Source 2 2026-11-14:** разрешено завершить **G1.1 → G1.2 до G1-BIND**, включая настоящий SourceProofReadInput и полный SOURCE_PROOF_SCHEMA_V1 с проверками. Пользователь отдельно потребовал закрепить изменение порядка именно в owning-плане. Это решение заменяет прежний общий запрет первого кода до приёмки G1.3; предыдущий POJO-срез и его exclusions выше описывают историю первой поставки, а не новый запрет read request/capture/schema в G1.1/G1.2.

Разрешённая последовательность:

1. G1.1 — завершить values/structural validation по §3, включая SourceProofReadInput(world_uid, proof) и настоящие transitive типы полного persisted roster. Сохранить чужие незавершённые edits; не создавать mirrors или permissive adapters. Проверить strict/frozen/revalidation/negative cases и typing. Семантический admission, descriptor-aware ordering и closure не переносить в POJO.
2. G1.2 — полный immutable SOURCE_PROOF_SCHEMA_V1 по §4 и accepted spec §11.4; exact IDs/bytes/версия неизменны. Подтвердить прежние literal V0/V1, round-trip настоящих types, negative cases и collision checks. Не ограничивать manifest заглушкой под один consumer. Обозначить результат как G1.1/G1.2 evidence, не G1 complete.
3. После подтверждённой поставки G1.1/G1.2 — отдельный Source 2 registration-срез: request ID71201, owning request manifest/composition и адресные tests по его отдельному proposal. Не включать request в SOURCE_PROOF_SCHEMA_V1 и не менять proof wire. G1-BIND не prerequisite этого pure encoding-среза; собственная contract/implementation проверка registration обязательна.
4. G1.3 — exact API sheet/owning adapters/composition принять и закрыть G1-BIND до реализации соответствующего pure/semantic слоя; затем его checks и общий review G1. Отсутствующие adapters не заменять stub.

Scope не расширяется до runtime IO, semantic admission/S1, finalizer, adoption или DAG. Прежний Source чат этим документальным изменением не затрагивается. Запись переданного решения не заявляет, что G1.1/G1.2 уже реализованы или приняты по tests.

Definition of Done G1: все exact imports доступны, проверки values/canonical/pure и typing выполнены, G1-BIND закрыт принятой конкретной dependency composition; ни public durable API, ни финализация/holds не обещаются. Только после этого слой A S1 может начинаться по source-pack-s1-s2-implementation.md. Наличие файлов без pure adapter evidence — PARTIAL, не G1 complete.

| Обязательный критерий | Проверка |
|---|---|
| Три запрета DAG | Pure library, без pipeline/IO/public domain calls; ноды/ветвление/HTTP не добавляются |
| Ответственность всех классов | G1.1 table и existing schema/codec/shared helpers достаточны для разрешённого G1.1/G1.2 среза; concrete G1.3 composition ещё OPEN и блокирует приёмку G1.3/полного G1, но не values/schema |
| Public/internal | Public value imports только; application helpers internal; не вводить public ADMIT/READ stubs |
| Утверждённый порядок | По решению §7: G1.1 values → G1.2 schema/vectors → отдельный Source 2 request encoding; G1.3 после собственного G1-BIND → общий G1 review → A. Storage/finalize/integration позже по основному плану |
| Data C/R/U/D | Новых public операций нет; construction/validation value не durable C/U; R storage отсутствует; D отсутствует |
| Settings C/R/U/D | Immutable descriptor configuration, без mutable registry CRUD и runtime discovery |
| Междоменные зависимости | Shared leaves/codecs existing; owning key adapters требуют точного принятого API. Нет импорта Terrain registry в Source identity |
| POJO/typed errors | Единственный Source roster, existing FieldPathError/CheckedPath/FieldRef/aggregation reuse; нет mirrored proof/receipt или новых generic key frameworks |

**Verdict:** G1.1/G1.2 разрешены к реализации по §7 через implement-plan; полный G1 не завершён. G1-BIND/API sheet остаётся gate соответствующего G1.3 pure/semantic слоя и общей приёмки G1, не первым шагом перед values/schema. При необходимости внешнего контракта сообщить владельца и конкретную зависимость, не расширять её заглушкой. Runtime IO/S1/finalizer этим решением не разрешены. Ручные edits apply_patch; mandatory diff перед отчётом; no commit/push/server/SQL/DAG.

## 8. Поставка POJO для Pack 3a — собственная проверка 2026-11-14

Уточнение статуса после проверки ошибок: импортный блокер Pack снят поставкой values. Обязательство Source typed diagnostics по §3/спецификации §11.3 не отменено; TODO(SOURCE-TYPED-ERRORS) в коде отмечает незавершённый переход. Исключение §7 не является отказом от error roster в G1. Структурный Pydantic boundary отказ допустим ровно в границе §11.3, а семантические diagnostics и независимая агрегация требуют реализации. Полный шаг G1 не завершён.

Реализован только разрешённый срез §7. Независимая приёмка не выполнялась; G1-BIND, canonical manifest и pure алгоритмы остаются открыты. До поставки каталога dataModel/sourceVersioning не было; shared ArtifactRef/Kind, EntityUid, RevisionHex, RegistryKey и validate_immutable переиспользованы без изменений.

Префикс всех импортов ниже — `app.dataModel.sourceVersioning.`. Исполняемый список импортов: `backend/tests/typing/sourceVersioning/valid.py`.

| Модуль | Доступные типы |
|---|---|
| sourceDescriptor | SourceDescriptorCategory, SourceDescriptorScope, SourceMemberKeyKind, SourceCollectionOrder, SourceDescriptorKey, SourceMemberKey, SourceDescriptorDefinition, SourceDescriptorRegistry |
| sourceObjectId | RegistryMemberId, LibraryMemberId, EntityObjectId, SourceSettingsId, SourceCollectionId, SourceObjectId |
| sourceObjectRevision | SourceRevision |
| sourceVersionRef | SourceVersionRef, SourceCollectionVersionRef |
| sourceDependencies | SourceDependencySet |
| sourceCaptureRef | SourceCaptureRef |
| sourceCaptureUsage | SourceCaptureUsage |
| sourceDurableProof | SourceDurableProof |
| sourceProofInput | SourceProofInput |
| sourceProofResult | SourceProofResult |
| sourceProofSelection | SourceProofSelection |
| sourceProofGroups | SourceProofGroupsInput, SourceProofGroupsResult |

Private `_value.SourceValue` задаёт общую конфигурацию и использует existing validate_immutable после структурной валидации. Private `sourceObjectId._SourceIdentity` проверяет точный Python discriminator и непустой descriptor token. Они не являются новыми публичными values или admission API; IO отсутствует. Explicit frozen=True на классах обеспечивает также static read-only/hashability. Structural Pydantic ошибки независимых полей агрегируются Pydantic; SourceFailure и application diagnostics не вводятся в этот срез.

Проверены: 20 unittest cases — strict scalars/tuples, required/extra fields, JSON round-trip, frozen nested values, forged nested instances, descriptor roster, tagged union, UUID/token validation, миры, declared repetitions vs persisted uniqueness, historical revisions, empty semantics, selections, group correlation shape. Positive Pyright: 0 errors; negative Pyright: ровно 5 ожидаемых diagnostics (object/collection refs, collection вне union, чужой registry brand, list вместо tuple, изменение frozen поля). Это собственная проверка реализации, не независимая приёмка.

Команды: из backend `.venv/Scripts/python.exe -B -m unittest discover -s tests/sourceVersioning -p test_values.py`; из корня `node node_modules/pyright/index.js -p backend/tests/typing/sourceVersioning/pyrightconfig.valid.json` и corresponding invalid config (ожидается exit 1 и пять указанных ошибок).

Граница: POJO не проверяет canonical bytes ordering/fingerprint, descriptor admission, принадлежность library captured membership, finalized witness, exact stored mappings или полноту durable closure. Bounds и соответствие selections исходным группам проверит application; в этом срезе нет atom enumeration/union/subset/closure. Успешный constructor SourceProofResult не удостоверяет durable admission. Read/select/verify requests и algorithms/storage/finalizer/pipelines/adoption/DAG/Pack не реализовывались.

## 9. G1.1 declarations и G1.2 encoding — поставка 2026-11-14

Продолжение выполнено после прямого «Делаем наш план далее»; актуальное исключение порядка — §7. §8 выше описывает предыдущую поставку. Независимая приёмка нового среза не проводилась. **Два отсутствовавших import prerequisites Source 2 теперь поставлены**, но его request registration и Snapshot ledger этим не принимаются.

Добавлены `sourceProofInput.SourceProofReadInput`, `sourceProofSelection.SourceProofSelectInput`, `sourceProofGroups.SourceProofGroupsVerifyInput`, `sourceBodyVersion.SourceBodyVersion/SourceCollectionVersion`, `sourceCollection.SourceCollectionBody`, `sourceCapture.SourceCapture`, `sourceCaptureWitness.SourceCaptureWitness`. Все под `app.dataModel.sourceVersioning`; shared ArtifactRef/EntityUid/revision types переиспользованы. Проверки — structural shape, worlds, unique identities, witness format, request correlation; canonical ordering/owning admission/closure в модели не перенесены.

Добавлен единый `sourceErrors`: SourceOperation (включая CHECK_COVERAGE), SourceFieldCode/SourceFieldIssue, SourceLogicCode/SourceLogicIssue, SourceFailure с обязательным nullable context и непустым набором issues. SourceFieldIssue — concrete specialization existing FieldPathError; новых error carriers вместо него нет. Runtime immutable configuration наследуется от shared FieldPathError. **Реализованы значения ошибок, но не G1.3 boundary translation/semantic aggregation.** Существующие TODO(SOURCE-TYPED-ERRORS) остаются открыты; создание sourceErrors.py не является завершением перехода всех validators на typed diagnostics.

Поставлен `app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1.SOURCE_PROOF_SCHEMA_V1`: immutable manifest с ровно 21 accepted entry §11.4 (2 shared Artifact + 19 Source). Requests/results/errors/descriptor configuration не зарегистрированы; request ID71201 не добавлялся. Новый codec, v2 schema или формат Terrain не создавались.

Собственные проверки: **34 tests Source PASS**, **13 shared canonical/UUID regression tests PASS**, positive Pyright **0 errors**, negative Pyright **ровно 5 ожидаемых errors**. Подтверждены V0 exact hex/160 bytes/fingerprint, V1 1400 bytes/fingerprint, SourceVersionRef fingerprint и selection 204 bytes; весь transitive roster/field order round-trip, cold process round-trip, исторические revisions, изменение witness fingerprint, стабильность bytes при порядке/расширении manifest, malformed wire/wrong root/version refusals. Merge проверен с ARTIFACT_CORE_SCHEMA, SNAPSHOT_CORE_SCHEMA и PACK_PIN_SCHEMA; ID/owner/kind conflicts отклоняются. FieldIssue paths собраны existing CheckedPath/FieldRef; shared aggregation сохраняет порядок двух issues. Это проверка carriers, не реализация operation-wide aggregation.

Команды: из backend `.venv/Scripts/python.exe -B -m unittest discover -s tests/sourceVersioning -p "test_*.py"` и `.venv/Scripts/python.exe -B -m unittest tests.planning.encoding.test_canonical_codec tests.planning.encoding.test_uuid_codec`; positive/negative Pyright configs — §8. Исполняемый полный список imports обновлён в tests/typing/sourceVersioning/valid.py. Diff просмотрен; shared production codec, Terrain, Pack, Snapshot, SQL, pipelines и DAG не изменялись.

Независимая проверка declarations/encoding завершена 2026-11-15: **PASS**, замечаний нет; [акт и границы verdict](source-g1-foundation-review-2026-11-15.md). Отдельный reviewer повторил 47 tests и positive/negative Pyright. Source 2 уже поставил request registration по своему proposal §6; его отдельный review и Snapshot integration этим PASS не покрыты.

Следующий наш этап — G1.3/API/G1-BIND и semantic typed-error transition. Source-owned API sheet остаётся DRAFT; concrete owning exact key/body/projector bindings Terrain не приняты по ответу §3.1 этого sheet. До их согласования зависимую реализацию не начинать, не подменять bindings тестовыми adapters и не распространять PASS foundation на G1 целиком. Request registration повторно не реализовывать; его текущая поставка относится к отдельному Source 2 срезу.
