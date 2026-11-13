# Pack ↔ DAG ↔ Source: проект конкретных входов и результатов

Дата: 2026-11-13. Статус: PROPOSED для совместной приёмки. Поручение пользователя — подготовить контракт и уточнить внешнюю границу у Source. Runtime код, NodeId и новый порядок исполнения не разрешены. Основания: [DAG §6.7](gen-dag-cache-pack-source-families.md#67-source--dag--pack-сопоставление-данных-после-уточнения-contracts), [Pack metadata POJO](pack-metadata-dependency-pojo.md), [Source §6.0.A–G](source-proof-v2-contract-spec.md). Прямые Pack → Source вызовы, включая pure helper, запрещены.

## 1. Historical extraction до зависимого partial write

**Результат сверки Source:** [ответ владельца 2026-11-13](source-pack-exchange-response-2026-11-13.md) подтверждает четыре формы обмена по принятому Source API (§§6.0, 11–12). Это не приёмка новых Pack signatures или DAG execution binding. Ниже учтены ограничения SELECT, единый SourceFailure и уже принятый внутренний adoption Source.

**Уточнение текущего проекта 2026-11-14:** `fields=()` у describe_metadata_usage_requests и `entries=()` у import_metadata_usage отклоняются: PackPreparationFailure с reason=DEPENDENCY_MISMATCH, issue METADATA_GROUP_MISMATCH и путём fields либо entries относительно named input. Эти операции описывают/импортируют полный набор групп хотя бы одной строки; пустой вызов не является подтверждением готовности строки. Это semantic проверка после structural admission и проверки state, без min_length, дублирующего ту же причину в schema errors. Если state структурно невалиден, действует согласованная агрегация и reason=INVALID_INPUT. Empty Source selection допустим: группа всё равно представлена request/result с пустым usage. Closure без Source proofs — отдельный случай и этим правилом не запрещается.

Предлагаемые Pack records в `dataModel/worldPack/preparation/sourceExchange.py`; strict/frozen/extra-forbid/revalidate-always, обязательные поля, immutable вложения. Это новые кандидаты, не runtime imports.

| POJO | Все поля | Назначение |
|---|---|---|
| PackMetadataUsageKey | subject: PackMetadataSubject; group: PackMetadataGroup | Корреляция запроса с текущим значением и полем Pack; Source её не получает |
| PackMetadataUsageRequestsInput | state: PackPreparationState; fields: tuple[PackMetadataUsageKey, ...] | Явный перечень требуемых сохранённых групп, без выбора workflow внутри Pack |
| PackMetadataUsageRequest | key: PackMetadataUsageKey; request: SourceProofSelectInput | Pack копирует общий proof и selection своей durable attribution в owning запрос; Source indices не интерпретирует |
| PackMetadataUsageResolution | requested: PackMetadataUsageRequest; result: SourceProofResult | Исходный запрос плюс результат Source select. Корреляция не является удостоверением выполнения |
| PackMetadataUsageImportInput | state: PackPreparationState; entries: tuple[PackMetadataUsageResolution, ...] | Вход отдельного импорта готовых зависимостей в transient карту |

Кандидаты открытых методов того же PackPreparationService:

- `describe_metadata_usage_requests(request: PackMetadataUsageRequestsInput) -> tuple[PackMetadataUsageRequest, ...]` — pure чтение. Проверяет subject/group и наличие detailed attribution; копирует base world, общий proof и selection. Не вызывает Source и не пытается вычислить subset.
- `import_metadata_usage(request: PackMetadataUsageImportInput) -> PackPreparationState` — pure перенос готового результата, не write metadata. Проверяет unique keys, актуальные subject/base/group, точное совпадение requested proof/selection с attribution текущего state, world результата и owning structural форму. Не проверяет subset алгоритмом Source.

После подтверждённого Source execution binding importer переносит result.proof.world_uid/uses в owning SourceProofInput и сохраняет usage в существующей transient карте. basis группы берётся из текущей Pack attribution, а не из Source. Durable provenance/assembly/parts не меняются. Неполный набор resolved groups нельзя выдавать как полный PackMetadataDescription: до write, требующего всех групп строки, должен быть импортирован полный необходимый набор; формат transient partial map требует отдельного уточнения либо importer принимает только полный набор групп выбранной строки. **Для данного кандидата выбран полный набор групп строки**, без изменения текущего полного Description carrier. fields input обязан перечислить этот набор; для old whole-row без attribution — согласованный отказ.

Сама пара requested/result недостаточна для semantic admission: caller способен подменить обе. До принятия trusted DAG execution/result binding importer не объявляется пригодным к production. Source подтвердил: отдельного verify_select(request,result) нет; READ subset proof и VERIFY_GROUPS не заменяют exact select correspondence. Для недоверенного предъявленного результата требуется исполнение SELECT через DAG над сверенным Pack запросом и непосредственная передача успешного результата. Pack не вычисляет atom subset. Новый receipt/token/store этим документом не вводится.

Source подтвердил механическое копирование result.proof.world_uid/uses в SourceProofInput. Исходная selection остаётся привязанной к исходному общему proof, не переносится на subset proof. Empty selection возвращает пустой usage правильного мира, но не доказывает source-independence metadata поля.

## 2. Групповой admission и bind

SourceProofGroupsInput формируется механически из ordered `PackMetadataDescription.dependencies[].source_usage`. Pack keys/basis остаются в DAG-корреляции. Source admit_groups возвращает общий proof и selections; verify_groups применяется при необходимости проверки предъявленного результата, а не автоматически вторым вызовом всегда.

Кандидат уточнения **существующего** PackMetadataProofBinding, без второго Binding класса:

Единственный owning модуль проекта — `app.dataModel.worldPack.preparation.metadataDependencies`. Он объявляет PackMetadataProofBinding; metadataSubject.py сохраняет PackMetadataSubject и не объявляет второй binding, alias или re-export. PackMetadataProvenanceInput из operations.py импортирует этот binding. Binding содержит данные subject/provenance/Source request/result/groups, не PackPreparationState, сервис или оркестрацию. Это разрешает прежнюю неоднозначность размещения, не создаёт новый тип или runtime import.

| Поле | Тип / источник |
|---|---|
| subject | PackMetadataSubject из исходного description |
| provenance | PackPartProvenance; общий proof равен source_result.admission.proof; Planning — по отдельному согласованному binding |
| source_request | SourceProofGroupsInput — точный исходный ordered usage |
| source_result | SourceProofGroupsResult — результат admit_groups либо verify_groups |
| groups | tuple[PackMetadataGroupAdmission, ...] — Pack group keys/basis, selections из source_result по исходной позиции |

Это заменяет кандидат source_admission: SourceProofResult в предыдущем черновике: полный grouped result нужен, чтобы не потерять корреляцию и дать DAG передать owning output целиком. Второй persisted proof не создаётся; transient equality proof и selectors проверяется, в manifest остаются общий provenance и attribution.

Bind сравнивает source_request.groups с ожидаемыми usages текущего state в том же порядке, result proof с provenance, число/позиции selections с groups и все subject/basis по Pack правилам. Проверка canonical union/selection semantics принадлежит Source. Равенство двух caller-копий не доказывает, что admit_groups/verify_groups исполнился: необходим тот же trusted result binding, что в §1. При изменении expected state требуется новый owning результат для изменённого запроса; Pack не исправляет чужой результат.

## 3. Полный closure перед prepare

Предлагается общий transient exchange для всех proofs конечного state, включая inherited payload и metadata. Это не только результат последнего bind.

| POJO | Все поля |
|---|---|
| PackSourceClosureRequestsInput | state: PackPreparationState |
| PackSourceClosureResolution | request: SourceProofReadInput; result: SourceProofResult |

Кандидат метода `describe_source_closure_requests(request: PackSourceClosureRequestsInput) -> tuple[SourceProofReadInput, ...]`: Pack перечисляет proofs конечного state и world, не раскрывает их Source internals. Один запрос на exact одинаковое materialized proof допустим при сохранении проверки покрытия всех logical uses; новая proof hash схема не вводится. Полнота списка принадлежит Pack, DAG не обходит manifest.

Кандидат дополнения PackPreparationBody — `source_closures: tuple[PackSourceClosureResolution, ...]` рядом со state/capture/scope. Это **предложение изменения публичного input**, не уже принятое поле. Prepare сверяет точный набор requested proofs с конечным state, request/result world/proof equality; missing, extra, duplicate/conflicting записи отклоняются. Source result durable_refs включаются в общий semantic closure только через принятый owning admission/execution binding. Required refs capture-формата не отбрасываются по selections. Полнота и подлинность Source traversal не выводятся из equality с operation holds.

В Source §12.1 уже принят internal `SourceCaptureRetentionBinding.adopt(scope: CommitScope, request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef, ...], target: ArtifactHolderRef) -> SourceProofResult | SourceFailure` (async). Он повторно вычисляет closure в borrowed write scope, проверяет exact source holds и приобретает target holds, не освобождая sources. Это owning алгоритм, не новый публичный Source pipeline.

OPEN — внешний Pack/Artifacts publication entry, передача scope/sources/target и lifetime target holder. Наличие internal adopt не разрешает прямой междоменный вызов из Pack без принятого инфраструктурного binding. Existing finish_preparation проверяет уже удержанный набор, но не заменяет adoption. Ошибка после acquire требует rollback общей transaction; unknown commit outcome остаётся у owning recovery. Данный документ не назначает внешний caller.

## 4. Порядок, ошибки и граница согласования

Уточнение 2026-11-14: operation-specific Pack diagnostics и связь с уже принятым preparation_fingerprint вынесены в [A3 / identity](pack-source-error-identity-contract.md). Это проект mapping, не самостоятельная приёмка. Внешний adoption конкретизирован владельцем в [publication response](pack-source-adoption-publication-response-2026-11-14.md), статус DESIGN OPEN.

По следующему поручению пользователя подготовлен [проект engine execution binding](pack-source-dag-execution-binding.md): exact continuation state, request/key/target и successful child result на существующем CALL. Он конкретизирует доверенный маршрут, но требует приёмки coordinating caller/leaf contracts и restore. Новый Source helper/token не требуется.

Таблицы задают data dependencies, не новую последовательность нод. Historical extraction/import должен предшествовать write, которому нужен historical usage; grouped admission относится к вычисленной projection; closure read — к конечным proofs перед prepare. Точное включение новых Pack публичных методов в утверждённые read/write семейства, число вызовов и deps принимает пользователь по DAG-плану. Изменять runtime порядок или вводить повтор describe/write без этой приёмки нельзя.

Pack переиспользует PackPreparationFailure и согласованный diagnostic union: stale base/subject, неизвестная attribution, missing/duplicate groups по metadata-проекту. Единый SourceFailure из app.dataModel.sourceVersioning.sourceErrors сохраняется на Source-операции; отдельный SourceProofFailure не вводится. Failure не импортируется как successful SourceProofResult. Точный error mapping новых методов должен пройти отдельную проверку. Independent errors агрегируются; никакой частичной mutation/READY при отказе.

Review владельца Source по четырём формам обмена получен: несовместимых request/result форм не установлено. При доверенном execution path ADMIT_GROUPS достаточен; для недоверенного grouped result нужен успешный output VERIFY_GROUPS, не исходный carrier. Одинаковые selections разных групп допустимы, исходный порядок сохраняется. READ не нормализует persisted proof; coverage всего конечного state остаётся Pack, полный closure включает обязательные невыбранные тела формата и не даёт live holds.

Перед реализацией остаются: приёмка новых Pack signatures/полей/error mapping, trusted DAG execution и неизменность соответствующего state между запросом/результатом, согласованный порядок/leaf bindings, а для READY — внешний publication entry и target lifetime над принятым internal Source adoption. Scope независимой Pack работы не расширяется автоматически и не объявляется заблокированным целиком.
