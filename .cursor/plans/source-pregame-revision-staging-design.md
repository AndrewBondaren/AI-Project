# Source — pregame revision staging и root lifetime

Дата: 2026-11-13. **DESIGN OPEN / не принят для реализации.** Отдельный следующий проектный срез; не изменение принятого SourceDurableProof. Основание — OPEN pregame staging из [акта независимой приёмки](source-durable-proof-contract-acceptance-2026-11-13.md) и §5 основной Source proof спецификации.

Актуальный сводный остаток и критерии завершения записаны в основном плане: [четыре шага подготовки первого среза](world-source-versioning.md#ближайшие-четыре-шага-подготовки-первого-среза-2026-11-14). Дополнения ниже служат деталями и evidence; сами по себе они не заменяют итоговую приёмку единого контракта.

## Ограничение среза и порядок

Разобрать одну атомарную persisted source mutation до появления Pack/Snapshot: подготовка immutable тела → staging → запись exact revision/membership → root retention → terminal outcome. Требуется инфраструктура уже для выбранных источников, но не автоматическая миграция всех WorldService/library/entity writers. Proof/schema v1, R1/R2 и порядок основного плана не переоткрываются.

Это детализация зависимости шага 3 основного плана. Шаги 1–2 (конкретный inventory выбранного источника и projector) остаются prerequisites реализации, не пропускаются. Код, SQL, Artifacts public enums/holders, Pack DTO и DAG в этом проектном проходе не меняются. Будущий код — отдельный принятый implement-plan срез.

## Подтверждённые препятствия по текущему коду

| Точка | Evidence | Следствие |
|---|---|---|
| Staging entry | `backend/app/application/artifacts/contracts/stagingPort.py::IArtifactStaging.open_operation(operation_id, world_uid, kind, preparation_fingerprint)` | Нужна реальная операция/lease, одной legacy SQL UOW недостаточно |
| Kinds | `backend/app/dataModel/artifacts/lifecycle/operation/kinds.py::OperationKind` | Только SNAPSHOT_APPLY/PACK_ACTIVATION/GAMEPLAY_START; source edit не является ни одним из них |
| Persisted kind | `backend/app/db/migrations/0001_initial.sql`, publication_operations.kind CHECK | Одного расширения Python enum недостаточно |
| Terminal value | `backend/app/dataModel/artifacts/lifecycle/operation/record.py::OperationRecord.terminal` и coherent_record | Union/валидация поддерживают только Snapshot/Pack/gameplay/cancel, source-success отсутствует |
| Terminal codec | `backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py::StoredTerminalCodec.encode/decode` | Hard allowlist классов/discriminators и canonical manifest; нельзя выдать Source успех за PackActivationResult |
| Persisted outcome | `0001_initial.sql`, publication_outcomes.outcome_kind CHECK | Source terminal требует согласованного изменения owning storage contract, не только нового DTO |
| Latest root | `backend/app/db/repositories/sqlite/artifacts/holderStore.py::acquire`, `dataModel/artifacts/lifecycle/holders.py` | SQL revision row не допустимый ArtifactHolderRef; ArtifactRetentionHolder требует sealed owner artifact; PinHolder нельзя использовать как освобождаемый фиктивный root |
| Release | holderStore.release и existing cancellation/drain | Source mutation success не эквивалентен cancel; cancel не может служить успешным terminal receipt |

## Предлагаемое направление — расширение существующего lifecycle

Source предлагает добавить отдельную семантику **source mutation** в существующий operation lifecycle; не создавать параллельные lease/fence/receipt/GC механизмы. Это предложение к owning Artifacts/publication контракту, не уже доступный OperationKind и не разрешение редактировать чужую реализацию. Внешнее публичное доменное CRUD остаётся у владельца данных, orchestration — у DAG; Source обеспечивает internal revision binding в общей transaction.

Source-owned результат применения должен содержать operation identity, world, request fingerprint и exact назначенные object/collection revisions; он не должен имитировать WorldPublicationRef или PackActivationResult. Конкретный outcome POJO, его отличие от Source mutation receipt и интеграцию в existing terminal store нужно принять **как одно представление результата**, без второго совпадающего журнала. Отдельный новый canonical manifest outcome не изменяет SOURCE_PROOF_SCHEMA_V1 и не перенумеровывает её IDs.

### P1: concrete кандидат успешного outcome

Публичный модуль кандидата — `app.dataModel.sourceVersioning.sourceMutationOutcome`, владелец Source. Единственный immutable record:

`SourceMutationApplied(operation_id: EntityUid, world_uid: EntityUid, request_fingerprint: RevisionHex, object_revisions: tuple[SourceVersionRef, ...], collection_revisions: tuple[SourceCollectionVersionRef, ...])`.

Все поля обязательны; frozen/strict/extra-forbid/revalidate-always. Это результат успешно committed Source mutation, не proof и не holder. `request_fingerprint` должен совпасть с binding применённой mutation в существующем operation ledger; preparation fingerprint не подставляется без проверки, что он описывает тот же запрос. Lists — exact revisions затронутых identities после commit; duplicate identity и conflicting revision запрещены, порядок canonical по Source ref bytes. Хотя бы один список непуст. Label-only изменение может возвращать прежнюю semantic revision; это не новый seq. Delete возвращает ref tombstone state в Source revision history, но не превращает его в live proof dependency.

Первая предлагаемая граница этого lifecycle — один world-scoped registry mutation batch плюс его membership; object_revisions содержит только RegistryMemberId того же мира и явно зарегистрированного descriptor. Global library/entity/settings mutations этим срезом не объявляются поддержанными. Это ограничение предполагаемой implementation поставки, не сужение принятого общего SourceObjectId. Concrete descriptor, typed mutation input и projector обязаны пройти отдельную приёмку перед кодом.

Record используется один раз как terminal outcome existing operation store. Source index сохраняет ссылку на operation identity и assigned revisions, а не вторую копию outcome с новым receipt DTO. Транзакция domain rows + Source revisions/membership + root holds + terminal outcome общая. До commit нельзя вернуть SourceMutationApplied. Отказ до записи — existing SourceFailure; unknown outcome — existing infrastructure recovery. Полная terminal union/codec/SQL registration остаётся P2, record пока PROPOSED.

До принятия Source-facing результата подготовить единый mapping: request fingerprint → operation identity → outcome → revision rows → retained bodies. Повтор operation id с другим fingerprint — конфликт; с тем же — прежний exact outcome, без повторного seq. Unknown commit разрешается по existing receipt/recovery, а не повторным применением mutation к latest.

### P1.1. Типизированный вход registry mutation

Владелец — Source, публичный модуль кандидата `app.dataModel.sourceVersioning.sourceRegistryMutation`. Все новые records frozen/strict/extra-forbid/revalidate-always; обязательные поля, tuple вместо mutable коллекций. Ни executor/callback, ни DB/scope/lease в payload нет. Это запрос на новую mutation, а не persisted proof или receipt.

`SourceRegistryMutationKind` — enum с wire values create/update/delete. Поле kind каждого варианта — обязательный Literal соответствующего enum member, без default.

| Тип | Полный состав |
|---|---|
| SourceRegistryCreate | kind, identity: RegistryMemberId, body: ArtifactRef |
| SourceRegistryUpdate | kind, expected: SourceVersionRef, body: ArtifactRef |
| SourceRegistryDelete | kind, expected: SourceVersionRef |
| SourceCollectionMutation | collection_id: SourceCollectionId, expected_revision: SourceRevision \| None, body: ArtifactRef |
| SourceRegistryMutationInput | operation_id: EntityUid, world_uid: EntityUid, execution_version: Annotated[StrictInt, Field(ge=1)], changes: tuple[SourceRegistryChange, ...], membership: SourceCollectionMutation; version binding — P2.13 |

`SourceRegistryChange` — discriminated union трёх вариантов по kind. В update/delete expected.object_id должен быть RegistryMemberId; другие принятые SourceObjectId варианты не разрешаются в этом частном mutation срезе. Не создавать отдельный RegistryVersionRef, зеркалирующий SourceVersionRef. SourceCollectionMutation отличается от version ref: expected_revision — **предусловие**, None означает отсутствие зарегистрированной collection identity; body — предлагаемое после-значение, не тело уже назначенной revision. Промежуточная новая seq в запросе запрещена.

Changes непусты, уникальны по full registry member identity и идут в canonical identity order. Все identities принадлежат request.world_uid и одному registered registry-member descriptor. Membership descriptor — зарегистрированный world-scoped counterpart этого registry; в этом срезе он допускает именно данный member descriptor. Input не содержит второй header descriptor, дублирующий identities. Collection body должен декодироваться как SourceCollectionBody с тем же collection_id. Body CREATE/UPDATE должен иметь owning format/identity соответствующего member; проверить key adapter без нормализации.

Каждый request описывает итоговую атомарную мутацию. Два изменения одной identity внутри одного batch запрещены; caller формирует одно итоговое изменение. Rename — DELETE старого + CREATE нового ключа с проверкой итогового ref-integrity графа. CREATE не переиспользует tombstoned identity: recreate требует отдельного принятого restore-контракта, не скрытого сброса seq. Переход значений A→B→A существующего объекта остаётся обычными UPDATE.

### P1.2. До lease, staging и optimistic apply

ArtifactRef кандидата вычисляется owning codec **до** reserve/stage по точным подготовленным bytes. Наличие ref в SourceRegistryMutationInput не означает, что artifact существует или sealed. Это разрешает порядок: подготовить bytes/refs → canonical request fingerprint → open_operation → stage exact bytes → apply. Не вычислять request fingerprint по результату stage, требующему ещё не открытой lease. При stage descriptor должен точно совпасть с заранее заявленным ref; изменение bytes требует нового request fingerprint, не silent замены input.

Request fingerprint включает operation_id, world_uid, action kinds, identities/expected refs и full body refs, в объявленном порядке полей и changes. Исключённых из request произвольных callback/config values нет. Кандидат canonical mutation manifest и IDs определён в P2.1; до review этот input не объявляется принятым wire-контрактом. Source semantic content_hash вычисляется owning projector, **не** копируется из ArtifactRef.content_hash.

При apply сначала проверить operation identity/fingerprint по existing terminal ledger. Committed same request возвращает прежний SourceMutationApplied без повторной проверки latest и seq. Same operation id/different request — конфликт, а не retry. Только новая mutation проверяет expected object/membership revisions, sealed/held bodies и итоговый ref-integrity graph под общим write scope.

| Действие / состояние | Правило применения |
|---|---|
| CREATE | Identity никогда не существовала; назначается seq=1. Occupied либо tombstoned identity — отказ |
| UPDATE | Expected full SourceVersionRef совпадает с текущей live revision. Identity не меняется |
| UPDATE, иной semantic hash | Следующая монотонная seq; новый retained body mapping; A→B→A даёт новую seq при прежнем hash |
| UPDATE, тот же semantic hash | Возвращается прежний SourceVersionRef. Существующий immutable body mapping не заменяется кандидатом |
| DELETE | Expected совпадает с текущей live revision; создаётся следующая tombstone revision, membership удаляет identity. Старые held live mappings неизменны |
| Collection expected_revision=None | Допустимо только отсутствие versioned collection identity, а не произвольный overwrite. Должен быть завершён owning bootstrap/read-set учёт существующих persisted entries |
| Collection expected_revision задана | Сравнить точную revision; другой состав/ревизия — конфликт. Не брать latest после stage без проверки expected |

Присланный membership body сравнивается с **полным** итоговым составом: прежний exact membership минус DELETE плюс CREATE. UPDATE состава не меняет. Для SET — canonical set order; для SEQUENCE порядок задаёт owning contract, произвольная перестановка не считается no-op. Missing/extra members отклоняются, даже если все присланные object bodies существуют. Первая поставка не добавляет отдельную операцию reorder; SEQUENCE registry, требующий такого поведения, не включается без её явного контракта.

Если состав и его семантический порядок не изменились, сохраняются прежние collection revision и body mapping. В SourceMutationApplied коллекция всё равно указана как проверенная затронутая identity. Source mutation outcome может содержать прежние object/collection refs при no-op или audit-only изменении; это committed результат запроса, а не обещание bump каждой seq.

### P1.3. Excluded metadata и label-only без body mapping conflict

Owning live row и audit metadata могут измениться без изменения Source semantic hash. В таком случае Source сохраняет прежний exact revision→body mapping. Новый label фиксируется owning audit stamp, связанный с operation_id и прежней SourceVersionRef; второй SourceBodyVersion с той же revision и другим ArtifactRef не создаётся. Source exact read возвращает тело зафиксированной версии; его excluded display/audit поля не являются API актуальных labels. Актуальные labels читает owning domain/audit contract.

Staged candidate body audit-only mutation может отличаться полными bytes от прежнего body. Он используется для owning row/audit apply, но не становится новым semantic revision body или частью proof. После commit/drain его operation hold снимается по existing lifecycle, если artifact не нужен другой owning retention policy. Capture/publication holds старого body не трогаются.

Такое разделение допустимо только для полей, доказанно исключённых owning semantic projector. Ни glossary/lore/display поля, ни hills authored-presence нельзя исключать по имени. Реальный TerrainRegistryEntry содержит mutable list eligibility при frozen model и различает hills через model_fields_set: напрямую выдавать его за готовый durable canonical body нельзя. Его owning body codec/semantic projector и audit exclusions остаются prerequisite шага 2, а не автоматически закрытым результатом этого mutation-input проекта.

### P1.4. Ошибки и проверяемые сценарии

Переиспользовать SourceFailure с operation PREPARE_MUTATION/APPLY_MUTATION; не создавать SourceMutationFailure с копией diagnostics. Structural/identity/duplicate ошибки — existing SourceFieldIssue с typed paths changes[i].identity/expected/body либо membership.*. Existing SourceLogicCode используются для WRONG_WORLD, UNKNOWN_DESCRIPTOR, DESCRIPTOR_MISMATCH, REVISION_CONFLICT, BODY_MAPPING_CONFLICT, MISSING_BODY, CORRUPT_BODY, UNSEALED_BODY, MISSING_HOLD. SourceLogicIssue.source — offending expected/actual ref при наличии, artifact — offending body; proof group/use индексы не переименовываются в change_index.

Для двух новых semantic условий предложить **добавление в общий SourceLogicCode**, а не новый enum: MUTATION_ID_CONFLICT (тот же operation id с другим request fingerprint) и MEMBERSHIP_MISMATCH (предъявленный after-body не равен вычисленному итоговому составу). CAPTURE_ID_CONFLICT/PROOF_MISMATCH для них не переиспользовать. Эти дополнения пока только в данном OPEN mutation-проекте: принятый error roster спецификации не редактируется, их совместимость и typed diagnostics проходят review P1/P2 отдельно.

Критические сценарии: body refs известны до lease; stage вернул иной descriptor; stale membership при неизменном chosen member; CREATE существующего/удалённого ключа; два actions одного ключа; ошибочный after-membership; UPDATE A→B→A; label-only с другими bytes и прежним mapping; failure после domain row write; same operation id/different fingerprint; replay после изменения latest. Проверка body mapping: для каждой принятой exact SourceVersionRef существует не более одного semantic body mapping независимо от числа audit-only операций.

### P2.1. Кандидат canonical mutation schema v1

Владелец — Source. Предлагаемый внутренний модуль `app.application.worldData.sourceVersioning.encoding.sourceMutationSchemaV1`, константа `SOURCE_MUTATION_SCHEMA_V1`. Кодек — существующий CanonicalCodec, digest — существующий content_digest. Это фиксированный manifest; вызывающий не передаёт произвольную schema. Публичные POJO остаются в указанных P1/P1.1 модулях dataModel.

| ID | Тип | Порядок record fields / enum values |
|---|---|---|
| 72001 | SourceRegistryMutationKind | create, update, delete |
| 72101 | SourceRegistryCreate | kind, identity, body |
| 72102 | SourceRegistryUpdate | kind, expected, body |
| 72103 | SourceRegistryDelete | kind, expected |
| 72104 | SourceCollectionMutation | collection_id, expected_revision, body |
| 72105 | SourceRegistryMutationInput | operation_id, world_uid, execution_version, changes, membership |
| 72106 | SourceMutationApplied | operation_id, world_uid, request_fingerprint, object_revisions, collection_revisions |

Диапазон 72000–72999 проверен поиском по backend/app и .cursor/plans 2026-11-13: до этого предложения совпадений не найдено. Это локальная проверка отсутствия конфликта, не принятие регистрации владельцем общего terminal manifest. Перед реализацией повторить collision check по совокупному manifest.

Зависимости — принятые Source identity/revision/ref bindings из SOURCE_PROOF_SCHEMA_V1 и ArtifactKind/ArtifactRef с существующими IDs 20003/20107. Их не регистрировать под новыми IDs и не создавать mutation-копии. Merge проверяет совпадение ID, Python owner и kind. Discriminated union не отдельный record и не получает type ID. SourceFailure и registry descriptor definitions в persisted mutation manifest не входят.

Request fingerprint = lowercase hex content_digest(CanonicalCodec(SOURCE_MUTATION_SCHEMA_V1).encode(request)). Никаких JSON/repr, исключений operation_id или повторного хеширования fingerprint. Preparation binding использует этот digest; successful terminal обязан связываться с тем же exact request digest. Допустимость использования существующего publication_fingerprint для этой связи подтверждает owning lifecycle контракт P2.2.

Версия задаётся manifest v1 и версией persisted terminal envelope; дополнительное поле schema_version в P1 POJO этим проектом не добавляется. Изменение набора/порядка полей или их семантики требует отдельной версии и review совместимости, не переопределения этих IDs. Для outcome предлагается существующий envelope format_version=1 с новым discriminator; это ещё требует подтверждения владельца terminal codec.

CanonicalCodec не сортирует tuple за caller. Input обязан уже иметь unique changes в порядке encoded full RegistryMemberId; UPDATE/DELETE берут identity из expected.object_id. Outcome tuples сортируются по encoded full refs согласно P1. Неканонический порядок отклоняется до open_operation; не исправляется при retry. expected_revision=None кодируется как None, не как отсутствующее поле. Значения enum кодируются зарегистрированным enum, не голой строкой. Все свойства strict/frozen и проверки P1 остаются обязательны после decode.

Приёмка сериализации: fixed byte/hash vectors для CREATE, UPDATE, DELETE и terminal; encode/decode round-trip реальных POJO; отказ на неизвестный type ID, иной порядок/форму, duplicate identity, неверный enum; изменение expected/body/operation_id меняет request digest. Векторы реальных POJO и runtime-тесты пока отсутствуют: сериализация остаётся DESIGN OPEN, не доказанной runtime поставкой.

### P2.2. Запрос владельцу Artifacts/publication — ответ получен, решения OPEN

Source просит конкретный контракт для атомарной pregame registry mutation без Pack/Snapshot. Source владеет input, semantic revisions, membership, outcome POJO и решением о Source root eligibility. Artifacts/publication владеет lease/fence/terminal ledger, общими holders и storage bindings. Ответ должен содержать точные модули, типы, сигнатуры, ошибки и порядок, а не только согласие с направлением.

1. **Lifecycle kind и terminal.** Подтвердить либо заменить предложение `OperationKind.SOURCE_MUTATION = "source_mutation"`, terminal discriminator `source_mutation`, outcome SourceMutationApplied из P1. Указать регистрацию в OperationRecord, StoredTerminalCodec, общем manifest и SQL CHECK. Проверки должны связывать kind, operation_id, world_uid и request_fingerprint. Текущая generic ветвь coherent_record читает result.publication.world_uid: для Source нужен явный путь проверки result.world_uid, без фиктивной publication.
2. **Binding apply и commit.** Указать supported entry/signature перехода READY→APPLYING и записи terminal под caller-owned CommitScope: как request digest связывается с preparation_fingerprint/publication_fingerprint; как сохраняется единая transaction domain rows + revisions + membership + holds + outcome. Нужны exact replay, конфликт operation_id, unknown commit/recovery и правила drain. Не создавать второй Source receipt store и не считать cancel успешной mutation.
3. **Pregame root.** Предоставить допустимое typed представление holder до первого Pack/Snapshot, его identity/codec, scope-bound acquire/release и проверку владельцем Source. Подтвердить GC-защиту каждого retained ref, atomic latest handoff и сохранение чужих historical holders. Если выбран root artifact, указать кто удерживает сам root и когда снимает hold; self-hold и фиктивный Pin не подходят.
4. **Зависимости и поставка.** Указать owning implementation slice и его порядок до Source apply. Подтвердить, что это internal storage binding, а не прямой Source→чужой public pipeline вызов. Внешние доменные операции запускает DAG; новый маршрут/ноды этим запросом не назначаются.

Source может независимо уточнять собственные POJO/validation/encoding, но не объявляет чужие enums, union, storage checks или signatures принятыми. По команде пользователя 2026-11-13 запрос передан в чат «SNAPSHOT» (01a1a0c5-931c-77a0-96a5-cb5b6ca6766f), ранее реализовывавший Artifacts leases и holder handoff. Получен read-only ответ владельца, отражённый ниже; это предложение, не приёмка P2/P3.

### P2.3. Ответ Artifacts/publication и оставшиеся зависимости

Источник — переданный ответ чата «SNAPSHOT», 2026-11-13. Его сообщения о текущем коде являются evidence владельца; новые signatures/holders ниже остаются предложениями, а не существующим API.

- Владелец предлагает SOURCE_MUTATION/source_mutation и SourceMutationApplied с terminal category=None. Дополнительные точки регистрации: application/publication/contracts/operationStore.py, service/operationLedger.py, publicationEvidence.py, terminal-kind SQL trigger. StoredTerminalCodec может объединить Source manifest с SNAPSHOT_CORE_SCHEMA, но exact-class allowlist и binding checks всё равно требуют изменения. Existing schema migration для уже созданных БД — отдельный вопрос владельцу; это не разрешение создавать 0002_*.sql вопреки implement-plan.
- По trace владельца existing claim_publication(kind, operation_id, world_uid, preparation_fingerprint, request_fingerprint) возвращает OperationClaim и владеет короткой bookkeeping transaction; record_terminal(scope, outcome) заимствует CommitScope. Для Source нужно запретить создание APPLYING при отсутствующей операции: допуск только из READY после закрытия admission и drain writers. Busy сохраняет OperationBusyError; binding mismatch переводится в Source MUTATION_ID_CONFLICT.
- Предлагаемый порядок: подготовить bytes/refs/fingerprint → open/stage/seal → finish_preparation → claim → одна domain transaction с expected checks, rows, revisions/membership, holds и terminal → подтверждённый commit → outcome. Claim отдельно не подтверждает успешный apply. Replay проверяет все bindings до возврата terminal; unknown commit не разрешает повторное применение к latest.
- Кандидат владельца: SourceRootHolder(kind=ArtifactHolderKind.SOURCE_ROOT, source: SourceVersionRef | SourceCollectionVersionRef), модуль app.dataModel.artifacts.lifecycle.sourceRootHolder. Representation/codec принадлежат Artifacts, eligibility/lifetime — Source. Предлагаемый internal sourceRootPort имеет acquire(scope: CommitScope, holder: SourceRootHolder) -> None и release(scope: CommitScope, holder: SourceRootHolder) -> None. Scoped Source index определяет полный набор refs; caller не передаёт сокращённый список. Adapter sourceRootStore заимствует scope, проверяет eligibility и записывает каждый hold. SQL/hydration/GC bindings и ошибки ещё не определены полностью.

Обязательные незакрытые условия:

| Условие | Владелец решения | Почему P2/P3 пока не принимаются |
|---|---|---|
| Source refusal после claim и подтверждённого rollback | Artifacts/publication + Source error contract | record_refusal принимает только SnapshotApplyResult; Source отказ оставляет APPLYING. Нужен согласованный terminal отказа либо fenced recovery transition с доказанным rollback/quiescence. Успешный outcome и cancel не подменяют отказ |
| Scoped mapping/eligibility | Source, затем binding Artifacts | Нужны exact signatures, typed errors, tombstone representation и атомарные проверки acquire/release; один holder DTO их не заменяет |
| Historical root lifetime | Source | Смена latest сама по себе не доказывает допустимость release A. Сначала определить, какие historical exact reads Source гарантирует независимо от capture/publication holds и как разрешается prune |

Предложенный владельцем acquire B → switch latest → release root A допустим только после Source-authorized lifetime/prune проверки A. Он не принимается как безусловная политика удаления исторических тел. Capture/publication holders независимы и сохраняются.

Порядок зависимостей: inventory выбранного registry → owning projector/body codec → приёмка mutation input/outcome/errors → lifecycle/terminal/refusal contract → Source scoped index/eligibility/lifetime → root storage binding → atomic apply и rollback/replay/recovery проверки. Контрактный дизайн этих зависимостей можно уточнять до кода; implementation порядок основного плана не меняется. Следующий Source-owned результат — scoped eligibility и historical retention policy; внешний незакрытый вопрос — refusal/recovery contract.

## Root retention — требования Source к owning holder binding

Нужен root, который существует **до** Pack/Snapshot и удерживает immutable body каждой требуемой live source revision. Предпочтительное направление для review — typed source revision owner в existing holder системе с проверкой существования/статуса через scope-bound Source index. Альтернатива root artifact допустима только с отдельно доказанным удержанием самого root и release lifecycle; self-hold не является решением.

Обязательные свойства независимо от выбранного representation:

1. Source row и initial root hold становятся видимы в одном commit. При rollback нет успешной revision без тела или успешного terminal outcome без root.
2. Переход latest A→B сначала защищает B, затем изменяет latest index. A сохраняет capture/publication/accepted-set holds; снятие latest ownership не освобождает чужие holders.
3. Object deletion создаёт tombstone и меняет membership в той же transaction. Старые held live bodies остаются доступными. Никакой latest fallback при exact read.
4. Release latest root не выполняется произвольным API Artifacts без owning Source проверки. Порядок ref-integrity/referenced/usage и revision prune остаётся основным планом; holder binding не выбирает policy вместо Source/пользователя.
5. Root eligibility, identity/codec, guarded deletion, restart и unknown-outcome recovery должны быть конкретизированы до SQL. Нового PinHolder/self-hold «до последующей миграции» нет.

Это ещё не выбор нового ArtifactHolderRef варианта и не его runtime регистрация. Source формулирует необходимые данные/проверки; точный shared holder contract принимается отдельно с владельцем Artifacts/publication. Отсутствие такого binding — зависимость runtime шага 3, а не дефект уже принятого proof.

### P2.4. Source-owned historical lifetime — предложение по explicit prune

Основание: основной план, «GC ревизий (решение 2026-10-24)»: latest всегда held, sourceUsage учитывает внешних держателей, revisionPrune удаляет только free; v1 предусматривает явный preview/confirm, не background sweeper. Поэтому предлагается **SourceRootHolder на каждую сохранённую body-bearing revision до explicit prune**, а не только на latest. Это уточнение lifetime для совместной приёмки; основной план и его порядок не переписываются.

При A→B acquire root B и публикация новой latest выполняются атомарно; root A сохраняется. Object DELETE создаёт tombstone и новое membership, но не снимает roots исторических live revisions. Label-only не создаёт дополнительного root: прежний exact ref и mapping остаются теми же. Collection revisions имеют такую же политику; retained collection body сам по себе не является capture и не закрепляет автоматически body каждого member — полный capture closure удерживается отдельно принятым proof-контрактом.

До успешного explicit prune exact live revision read должен находить прежнее тело после restart даже без Pack/Snapshot/capture. После prune чтение той же exact revision не переходит к latest. Сохраняются identity/seq/hash и отметка удаления body mapping, достаточные для запрета повторного seq/identity и отличения намеренного prune от corrupt/missing artifact. Tombstone — отрицательное состояние owning revision index, не пустой live ArtifactRef; live body read возвращает TOMBSTONE. Его canonical content_hash и точная storage форма остаются prerequisite deletion-контракта, их нельзя выдумать в holder adapter.

Чтобы собственный archival root не делал prune невозможным, sourceUsage должен различать **защиту от физического GC** и **причину запрета explicit prune**. Собственный SourceRootHolder exact revision обеспечивает первое. Latest и внешние capture/publication/accepted-set holders обеспечивают второе. Нельзя просто игнорировать все Source holders одного artifact: если bytes разделяют несколько revisions, roots других revisions сохраняются. Удаляется только holder выбранного exact ref.

Prune confirm обязан повторить latest и external usage проверки в сериализованной с mutation/capture-finalize границе, затем в той же transaction снять выбранный root и отметить mapping pruned. Preview не является разрешением и не несёт capability. На отказе никаких частичных release; на rollback body mapping/root восстанавливаются вместе. Физическое удаление bytes остаётся у existing Artifacts GC после commit, с проверкой полного live-set. Точный sourceUsage scoped read контракт должен быть принят отдельно; публичный междоменный вызов из root adapter не допускается.

### P2.5. Конкретный кандидат внутреннего Source root read binding

Модуль `app.application.worldData.sourceVersioning.retention.rootReadBinding`, класс `SourceRootReadBinding`, владелец Source. Это внутренний scope-bound адаптер, не публичный OpenPipeline, не новый dataModel POJO и не holder implementation. Предлагаемый метод:

```python
async def retained_refs(
    self,
    scope: CommitScope,
    source: SourceVersionRef | SourceCollectionVersionRef,
    *,
    operation: SourceOperation,
) -> tuple[ArtifactRef, ...] | SourceFailure: ...
```

Назначение — прочитать **точный** revision mapping из общей transaction и вычислить полный storage closure его body через existing owning format bindings. Результат canonical/unique, включает primary body и все format dependencies; не proof, не lease, не capability и не обещание hold после выхода из scope. Поиск latest и обход всех members collection вместо storage closure запрещены. CommitScope/SourceOperation остаются internal, в публичный mutation input не попадают.

Проверки: exact identity/revision/world/descriptor; body-bearing, не pruned/tombstone; единственный immutable mapping; поддерживаемый формат; полнота closure; sealed/integrity каждого ref. Binding не назначает seq, не изменяет SQL, не добавляет holds, не открывает transaction и не вызывает public pipeline другого домена. Использует scoped revision-index read и внутренние Artifacts format/catalog readers той же DB/composition. Все независимые diagnostics агрегируются до effects.

Ошибки переиспользуют SourceFailure с operation вызывающей операции, SourceLogicIssue.source=запрошенный exact ref и artifact при наличии. Existing TOMBSTONE, REVISION_CONFLICT, BODY_MAPPING_CONFLICT, UNSUPPORTED_FORMAT, MISSING_BODY, CORRUPT_BODY, UNSEALED_BODY, INCOMPLETE_CLOSURE сохраняют свои значения. Для намеренно pruned mapping предлагается общий SourceLogicCode.REVISION_PRUNED, для неизвестной exact revision — REVISION_NOT_FOUND: это разные условия от missing bytes при существующем mapping. Новые codes остаются предложением в этом OPEN документе; принятый sourceErrors roster не изменяется. Infrastructure errors не превращаются в отрицательный результат.

Artifacts root acquire использует этот binding внутри собственного internal adapter и записывает полный набор holds только после успешных проверок; fresh revision mapping уже записан, но ещё не committed в общей transaction. Должны быть дополнительно проверены operation/fence и полномочия mutation caller, а не только существование ref. Повтор acquire идентичен; mapping иной для того же exact ref — отказ. Как caller передаёт operation/fence контекст при предложенной двухаргументной acquire(scope, holder), владелец Artifacts ещё должен конкретизировать.

**Release не использует retained_refs как разрешение.** Для первого mutation среза release исторических roots не вызывается вообще: explicit prune — отдельная операция основного плана. Общий unrestricted release(scope, holder) пока нельзя открыть. Перед его поставкой нужны concrete Source prune authorization, scoped sourceUsage evidence и атомарная связь проверки с записью pruned; токен, bool от caller и повторный read после выхода из scope не подходят. Это зависимость полноценного retention lifecycle, а не разрешение отложить её приёмку незаметно.

Критерии проверки binding/lifetime: historical A читается после B и restart без внешнего holder; GC не удаляет A до prune; latest prune запрещён; внешний hold блокирует prune; общий artifact двух revisions не теряет root второй; label-only не меняет mapping; rollback acquire/prune не оставляет частичный live-set; tombstone не превращается в live body; pruned и отсутствующие bytes различимы; не вызывается latest fallback. До runtime evidence и joint review P2/P3 остаются OPEN.

### P2.6. Повторный ответ владельца: отказ и полномочия acquire

Получен [ответ Artifacts/publication от 2026-11-13](source-mutation-artifacts-publication-response-2026-11-13.md). Он подтверждает как согласованное направление обсуждения сохранение historical roots до explicit prune и уточняет acquire до `acquire(scope: CommitScope, claim: PublicationOwner, holder: SourceRootHolder) -> None | SourceFailure`. Это заменяет первоначальное двухаргументное предложение P2.3; runtime API пока отсутствует и не принят.

Владелец рекомендует Source-owned terminal envelope `SourceMutationRefused(operation_id, world_uid, request_fingerprint, failure: SourceFailure)` с failure.operation=APPLY_MUTATION. Envelope фиксирует identity запроса и исходный отказ в едином ledger, не дублирует diagnostics новым failure DTO. Exact replay возвращает сохранённый failure; исправленный запрос требует нового operation_id. Canonical ID и включение SourceFailure с его nested diagnostics в terminal manifest требуют отдельного roster/round-trip review; P2.1 пока описывает только success/input и не является полным terminal manifest.

**Найденный блокер:** runtime ConfirmedRollback capability не переживает crash между rollback и записью refusal. После рестарта отсутствие terminal не доказывает исходный отказ и не разрешает проверить изменившийся latest вместо прежнего результата. Поэтому предложенные transaction_for_claim и record_source_refusal остаются неполными до durable recovery/единственной apply attempt. Source не объявляет этот протокол готовым на основании одного terminal POJO.

Для acquire дополнительно требуется Source-owned `validate_acquisition(scope: CommitScope, source: SourceVersionRef | SourceCollectionVersionRef, *, operation_id: EntityUid, operation: SourceOperation) -> None | SourceFailure` в retention/rootEligibilityBinding.py. Проверка должна связывать текущую mutation с exact revision, включая no-op/audit-only, где created_by_operation принадлежит прежней операции. Это internal eligibility, не public CRUD и не разрешение caller передать произвольный ref.

Оставшиеся конкретные результаты: Source проектирует scoped operation→revision linkage без копии terminal outcome, diagnostics MUTATION_BINDING_MISMATCH и правила no-op; Artifacts/publication завершает durable refusal recovery, исключение конкурирующих apply attempts и typed acquire infrastructure errors. Допустимые исходные durable holders для reused closure согласуются совместно. Explicit prune/release требует собственного scoped usage-контракта. До этих результатов P2/P3 остаются OPEN.

### P2.7. Operation → exact revision linkage (Source, 2026-11-14)

Кандидат internal класса `SourceMutationLinkStore`, модуль `app.application.worldData.sourceVersioning.mutation.linkStore`. Владелец Source; SQLite implementation располагается в owning Source storage adapter, не в Pack или publication ledger. Это индекс участия revision в mutation, **не receipt/terminal store**. Public dataModel record для link не вводится.

Логическая persisted запись имеет только `operation_id: EntityUid` и `source: SourceVersionRef | SourceCollectionVersionRef`. Для одного operation и full identity допускается ровно одна exact revision; object и collection identities различаются своим типом. Operation identity ссылается на существующий ledger, source — на exact revision index; canonical identity использует принятые Source bindings, не новый digest. Fingerprint/world/terminal/failure/body refs не копируются в link rows. DDL и физическое разложение полей здесь не принимаются.

Предлагаемые internal signatures:

```python
async def append_application(
    self, scope: CommitScope,
    request: SourceRegistryMutationInput,
    outcome: SourceMutationApplied,
) -> None | SourceFailure: ...

async def contains(
    self, scope: CommitReadScope,
    operation_id: EntityUid,
    source: SourceVersionRef | SourceCollectionVersionRef,
) -> bool: ...
```

Source apply implementation формирует outcome как **provisional value** после назначения revisions; это не внешний success до commit. append_application проверяет request/outcome operation/world/fingerprint, exact набор затронутых identities и существование назначенных revision rows в том же scope. Object identities должны точно совпасть с changes, collection identity — с membership; ни пропуск, ни дополнительный touched ref не разрешён. Семантический projector/назначение seq принадлежат apply implementation; store не пересчитывает чужие тела и не принимает произвольный caller outcome через публичный API. Metadata/audit rows, revisions и полный link set входят в одну domain transaction.

Для CREATE/изменяющего UPDATE link указывает новую revision. Для no-op/label-only link указывает прежнюю exact revision, независимо от её created_by_operation. Для DELETE link указывает назначенную tombstone revision: участие в результате не делает её eligible для body root. Link на проверенную collection записывается и при неизменном membership. Поэтому наличие link само по себе не означает необходимость нового root или допустимость acquire.

Перед первым append проверяется весь batch и все existing links operation. Пустой набор допускает запись полного набора; существующий **точно полный** набор идентичен и не меняется; partial/extra/conflicting набор отклоняется, не дополняется для сокрытия нарушения atomicity. Store не открывает transaction, не пишет terminal и не восстанавливает успех из links. Replay committed операции выполняется через ledger до повторного apply; отсутствие terminal при найденных уже committed links — recovery/infrastructure inconsistency, а не разрешение вернуть успех. Собственные uncommitted links до записи terminal в той же transaction являются нормальным промежуточным состоянием.

### P2.8. Eligibility и no-op roots (Source, 2026-11-14)

`SourceRootEligibilityBinding` в `app.application.worldData.sourceVersioning.retention.rootEligibilityBinding` предоставляет validate_acquisition из P2.6. Внутренние зависимости: SourceMutationLinkStore.contains, scoped exact revision index и descriptor registry. Он проверяет operation→exact ref link, world/descriptor, существующее body-bearing состояние и отсутствие prune/tombstone. Для этого acquire adapter сначала проверяет PublicationOwner, SOURCE_MUTATION/APPLYING, fence, world, scope/task/database и единственность apply attempt, затем передаёт operation_id из **проверенного claim**, не из отдельного caller поля. Класс eligibility не проверяет lease вместо Artifacts и не читает latest для подмены запрошенной revision.

Отсутствующий либо неверный link даёт предлагаемый общий SourceLogicCode.MUTATION_BINDING_MISMATCH с source=offending ref, group_index/use_index=None. Не создаётся новый failure carrier. Missing revision, pruned, tombstone, world/descriptor/mapping defects используют P2.5. Infrastructure corruption и невалидный scope не становятся Source logic failure. Independent checks агрегируются, зависимая проверка exact mapping пропускается только если её input неизвестен.

No-op требует сохранённого **полного прежнего Source root**; он не маскирует потерю holds приобретением заново на основании одной live mapping row. Результат повторного acquire уже существующего root идемпотентен только после full closure/hold проверки. Недостающий старый hold — MISSING_HOLD или infrastructure inconsistency согласно owning проверке, repair в mutation не добавляется. Staged audit-only candidate не подменяет retained body и его closure.

Для новой revision Source не предлагает искать произвольного держателя по artifact hash. Свежие тела должны быть защищены OperationHolder проверенного claim. Reused refs требуют explicit доказанного source hold в общем scope; допустимые holders и передача такого evidence остаются совместным вопросом Artifacts/publication. retained_refs доказывает состав storage closure, но не наличие удержания.

**Важная transaction граница:** даже SourceFailure, возвращённый acquire до его первого holder append, может возникнуть **после** записи domain rows/revisions/links. Apply owner обязан откатить всю domain transaction при таком результате. «До первого write» внутри одного adapter не означает, что caller может commit-ить ранее сделанные изменения. Failure при частичной storage записи пересекает boundary exception; success/outcome наружу — только после confirmed commit.

### P2.9. Ответственности и проверка нового среза

| Класс | Допустимая ответственность / effects | Критерий отказа |
|---|---|---|
| SourceMutationLinkStore | Scoped полный append exact links и read membership; FK/uniqueness; без own commit | Второй receipt, частичное дополнение повреждённого batch, принятие caller refs без request/outcome checks |
| SourceRootEligibilityBinding | Read-only проверка участия exact revision в mutation и body-bearing status | Created-by вместо no-op linkage, управление leases/holders, latest fallback |
| SourceRootReadBinding | Read-only exact body→full storage closure, P2.5 | Принятие неполного caller closure или выдача разрешения release |
| Source apply implementation | Expected/ref-integrity/semantic revisions → rows и links → root binding → terminal в общей transaction | Commit после SourceFailure любого adapter; внешняя выдача provisional outcome |
| Artifacts root adapter | Claim/scope authority, eligibility, closure protection, полный append holds | Поиск случайного holder, repair no-op без контракта, partial commit |

Последние два implementation owner должны получить точные классы/порты при P3 после infrastructure ответа; таблица не закрывает этот пробел общей ролью. Публичный mutation Input/Outcome/Error и DAG маршрут от этих internal signatures не меняются. Source dataModel не импортирует holders/sourceUsage.

Обязательные сценарии для будущей реализации: новый revision link; no-op с чужим created_by и своим valid link; подмена operation/identity/seq; missing/extra/partial link batch; tombstone link без root; full unchanged collection link; чужой world; missing старый root; failure после links до holds; failure после части holds; rollback без сохранённых links; restart/replay по terminal без назначения seq. Это проверяемый проект, не выполненные тесты. Приёмка всего P2/P3 по-прежнему OPEN.

### P2.10. Уточнение владельца и решение по crash guarantee (2026-11-14)

В [ответе Artifacts/publication](source-mutation-artifacts-publication-response-2026-11-13.md) предложен outer transaction + domain savepoint: Source failure откатывает весь domain scope (rows/revisions/links/holds), затем refusal и operation-hold cleanup фиксируются одним outer commit. Это новое предложение infrastructure контракта, не уже реализованный coordinator API. Историческое предложение отдельной ConfirmedRollback capability и второго refusal commit заменено этим вариантом для дальнейшего review.

После crash до outer commit durable attempt-start остаётся без terminal; исходный in-memory failure восстановить нельзя. Владелец предложил fail-closed unresolved и отдельный будущий fenced abandon. **Решение пользователя 2026-11-14: «Сначала полный протокол восстановления».** Unresolved допустим как промежуточное безопасное состояние, но не как конечное ограничение принятой первой поставки. До реализации требуется конкретный recovery protocol с доказанными fencing/quiescence, судьбой незавершённой attempt, holds и точным результатом для caller. Нельзя автоматически запускать новую identity, фабриковать исходный отказ или повторять mutation по изменившемуся latest под видом exact replay. Точная семантика восстановленной незавершённой attempt должна быть предъявлена отдельно; это решение не обещает восстановить недолговечные данные из памяти.

Владелец также уточнил eligibility: требуется internal SourceRootAcquisitionMode CREATE | REQUIRE_EXISTING вместо None при успехе. CREATE разрешает первый root только для revision текущей активной attempt; REQUIRE_EXISTING проверяет полный own root без append/repair. contains(operation_id, source) доказывает участие, но не fresh creation. Source должен дополнить exact revision provenance и её связь с единственной domain attempt; enum/изменение signature пока PROPOSED, не принято.

Для CREATE первая поставка предложена с current OperationHolder либо SourceRootHolder другой exact revision, где проверены mapping и membership artifact в полном closure. Произвольный holder lookup не разрешён. Предложенные infrastructure codes и Source MISSING_HOLD mapping описаны владельцем в разделе «Согласование linkage и no-op». Они требуют совместной проверки, не дублирования в Source failure family. P2.7–P2.9 сочтены владельцем совместимыми с domain savepoint; приёмка P2/P3 остаётся OPEN.

### P2.11. Fresh revision provenance и выбор acquisition mode (2026-11-14)

Участие revision в operation (P2.7) и создание revision — разные факты. Предложение Source: immutable revision-index запись получает `created_attempt_id: EntityUid`, ссылающийся на единственный owning publication attempt-start. Идентичность attempt не добавляется в SourceRevision, SourceVersionRef, SourceDurableProof или public mutation input; semantic hash от неё не зависит. Полные operation/fence/request данные остаются в ledger и не копируются в revision row.

created_attempt_id назначает только Source revision writer из **проверенного активного domain scope**, а не caller, не owning body и не provisional outcome. Связь scope→attempt проверяет infrastructure owner по registry/task/database/phase/fence и persisted attempt-start. Current CommitScope имеет только assert_active/read_scope; метода получения attempt identity в нём сейчас нет. Поэтому Source запрашивает отдельный internal infrastructure binding вместо неявного расширения CommitScope:

```python
# Предложение владельцу publication; не существующий port.
def require_domain_attempt(
    self, scope: CommitScope, *, operation_id: EntityUid,
) -> EntityUid: ...
```

Возвращённый EntityUid — identity проверенной attempt, не самостоятельная capability. Вся работа продолжается в том же scope; перед каждым доступом действуют guards. Возвращённый uid нельзя сохранить и предъявить позже вместо scope. Owning module/class и необходимость async проверки persisted fence определяет publication; без точного ответа этот dependency не считается принятым. Source writer и root eligibility должны использовать один и тот же binding, не две независимые трактовки свежести.

`SourceRootEligibilityBinding.validate_acquisition` в текущем проектном кандидате возвращает `SourceRootAcquisitionMode | SourceFailure`; enum internal, рядом с binding, wire values CREATE="create", REQUIRE_EXISTING="require_existing". Он не persisted и не получает canonical schema ID. Это уточняет прежнюю None-success signature P2.6; до совместной приёмки все варианты остаются проектными.

| Условие после exact linkage/status checks | Результат |
|---|---|
| Revision создана текущей active domain attempt, provenance совпадает с проверенным scope | CREATE |
| Revision создана ранее, её создание подтверждено committed successful terminal исходной operation; текущая operation имеет touched link | REQUIRE_EXISTING |
| Revision помечена другой незавершённой/отозванной attempt либо provenance отсутствует/противоречива | Отказ; не fallback в CREATE или REQUIRE_EXISTING |
| Tombstone либо pruned mapping | Existing P2.5 отказ до выбора mode |

Новая revision, её provenance, body mapping и touched links записываются в domain savepoint и откатываются вместе. No-op не меняет created_attempt_id. CREATE/semantic UPDATE/изменение membership назначают provenance новой revision; DELETE создаёт provenance tombstone, но не body root. Повторный acquire в одной attempt не меняет provenance; adapter проверяет existing full root/idempotency согласно owning контракту. Проверка «создана раньше» не подменяется сравнением seq, hash, времени или operation_id.

При recovery новая attempt не наследует право объявить CREATE для записей старой attempt. Terminal replay не запускает acquisition. Если owning recovery доказывает отсутствие committed domain результата и откат старой попытки, её revision/link rows должны отсутствовать; найденные committed rows без corresponding success terminal — infrastructure consistency failure. Допустимость новой attempt под той же operation identity определяется ещё проектируемым recovery, не Source. Source не создаёт вторую attempt автоматически.

Bootstrap существующих registry rows требует принятого способа provenance/initial root registration до включения writer: nullable created_attempt_id с трактовкой «наверное старое» запрещён. Этот prerequisite относится к inventory/projector/revision storage шагам основного плана; данный проект не мигрирует legacy данные автоматически.

Проверки: no-op сохраняет прежнюю creation attempt; подмена uid caller отвергается; wrong task/DB/phase/fence не выдаёт active attempt; child/stale scope после rollback не действует; rollback удаляет fresh provenance вместе с mapping; восстановление не переименовывает old attempt в current; одинаковый content hash разных seq не смешивает creation; tombstone никогда не даёт CREATE body root. До согласования infrastructure binding, bootstrap и recovery это test obligations, не runtime evidence.

### P2.12. Решение по recovery и обязательное логирование (2026-11-14)

Пользователь согласовал explicit recovery незавершённого transactional body с тем же operation_id, исходным immutable request/expected и новой fenced attempt, с условием: **«такое поведение требует логирования -> от причины и operation_id до результата»**. Durable terminal всегда replay-ится точно без domain body. Recovery незавершённой attempt — новое исполнение исходного запроса, а не восстановление утраченного in-memory refusal; provisional результат может отличаться. Это решение заменяет запрет повторного body для той же operation identity в раннем кандидате. Автоматическая замена operation_id и silent retry не разрешены. Весь P2/P3 этим решением ещё не принят.

Обязательное условие приёмки — единая прослеживаемая цепочка recovery по existing logging facade/JsonLogFormatter/router, согласно docs/tz_logging.md. Owning publication emitter должен получить concrete typed event/error mapping и route в implementation map до кода; новый локальный logger/handler или отдельный журнал состояний не вводится. Source передаёт свои typed diagnostics, не дублирует lifecycle emit.

| Факт | Обязательные данные и момент фиксации |
|---|---|
| Recovery запрошен | Типизированная причина восстановления и наблюдаемое durable состояние; operation_id, world_uid, request_id общего фасада, request_fingerprint, ожидаемая attempt identity. Не выдавать отсутствие terminal за доказанный crash: unknown acknowledgement/незавершённая attempt отражаются как наблюдения |
| Решение после inspect/claim | Terminal replay / busy / binding или CAS mismatch / takeover; прежние и новые attempt_id/fence при наличии. Takeover и перенос operation holds отмечаются подтверждёнными только после их commit |
| Повторный domain apply | Связь новой attempt со старой и тем же request fingerprint; исходные expected не заменяются latest. Ни body, ни весь request, ни raw SQL в лог не копируются |
| Domain refusal/rollback | Коды Source diagnostics и типизированные пути/контекст по owning error mapping; подтверждённый rollback отличается от unknown. Промежуточный refusal не объявляется durable terminal |
| Итог recovery | Applied / Refused / terminal replay либо busy/stale/infrastructure failure/unknown outcome; operation_id, attempt/fence, correlation и typed причина. Success/refusal как durable итог — только после confirmed outer commit; replay не выдаётся за новый APPLY_COMMITTED |

При exception сохраняется исходный exception/trace через существующий formatter и существующая failure correlation, где она определена owning error contract; новый случайный failure_id вместо отсутствующего owning ID не вводится. Типизированный recovery reason не является вторым SourceFailure/outcome enum. Точный roster причин, event POJO, severity и producer methods конкретизирует Artifacts/publication совместно с Source error mapping. Необходимые причина и итог должны быть наблюдаемы при штатном production уровне; цепочка не может целиком исчезнуть при отключённом DEBUG. Если это требует уточнить принятый STARTED/BUSY severity, владелец предъявляет изменение отдельно.

Crash может оборвать лог до итоговой записи; следующая recovery коррелируется по durable operation/attempt и отражает установленный результат. Логи не используются как ledger или доказательство commit, не обещают exactly-once и не восстанавливают утраченные diagnostics. Отказ sink после commit не меняет outcome и не инициирует повторный apply.

Проверки приёмки: terminal replay без повторного apply/commit event; recover до domain start и после rollback-before-terminal; crash после commit до acknowledgement; stale/CAS mismatch; busy и unknown; две последовательные recovery attempts различимы по attempt/fence; исходная причина и конечный результат соединяются по operation_id; реальные emitter→configured sink проверки и failure correlation; ошибка sink не меняет committed outcome. Runtime логирование пока не реализовано. Требование передаётся владельцу publication как обязательная часть полного recovery, не follow-up после поставки.

### P2.13. Immutable execution binding — REC-1 (2026-11-14)

Проверенный concrete кандидат первого registry — WorldTerrainRegistry (`SCH-WORLD-TERRAIN`, ключ system_terrain). Это выбор для проектного анализа, не объявление полного writer inventory завершённым. TerrainRegistryEntry содержит mutable eligibility list при frozen модели и semantic authored-presence hills через model_fields_set. Registered durable owning body codec и semantic Source projector для него ещё не предъявлены. WorldService._save/reconcile — существующая запись owning rows, не реализация Source revision boundary.

Для recovery недостаточно SourceRegistryMutationInput bytes и ArtifactRef.format_version. Последняя определяет формат body, но не версию projector/ref-integrity/membership правил. Предлагается добавить в **ещё не принятый** SourceRegistryMutationInput обязательное поле `execution_version: Annotated[StrictInt, Field(ge=1)]` после world_uid. Bool/строки отвергаются, default отсутствует. Отдельного version DTO, зеркального descriptor/header или SourceProof schema change не требуется.

Execution binding key — `(registered member descriptor из request.changes, execution_version)`. P1 уже требует один member descriptor на batch; membership counterpart проверяется тем же exact binding. Номер фиксирует неизменяемый пакет семантических правил **для этого descriptor**, а не build number процесса. Registration включает owning body codec/format version, semantic projector и authored-presence, key adapter, membership SET/SEQUENCE semantics, ref-integrity interpretation, tombstone encoding и audit exclusions. Смена любого влияющего правила требует новой execution_version и отдельной совместимости; переопределять старую регистрацию новым алгоритмом запрещено.

Registry и его entries — internal application composition, не request-supplied callback/config. Runtime mutation не выбирает «последнюю поддержанную» версию вместо заявленной. Existing durable terminal replay не требует запуска прежнего projector: проверяет immutable request binding и возвращает сохранённый outcome. Только незавершённая recovery требует наличия точного исполнителя версии. Если его нет, body не запускается, исходные request/holds сохраняются, caller получает явный отказ исполнения; не фабрикуется SourceMutationRefused с business diagnostics и не снимаются holds как после завершённой mutation. Typed infrastructure error для unsupported execution version должен быть согласован с publication recovery owner.

Для candidate версии 1 предлагается **запрет ambient настроек**, влияющих на преобразование body/назначение semantic hash. Versioned execution определяется request bodies и фиксированной регистрацией правил. Если owning trace выявит изменяемый параметр, его exact immutable input обязан войти в request/dependency binding до приёмки версии 1; этот запрет не является доказательством отсутствия параметров. Проверки expected/latest/ref-integrity в transaction могут видеть изменившееся состояние и законно дать новый отказ: это согласованная recovery semantics, а не silent смена projector. Исходные expected refs не заменяются.

Для terrain body необходимо сохранить hills absent / explicit None / explicit policy и порядок/состав eligibility; нельзя вводить label/glossary exclusions по названию. Default правила SourceObjectContract остаются «всё semantic, кроме доказанно excluded». Конкретное дерево owning immutable body, format binding и тестовые векторы входят в обязательный projector prerequisite. Принятые Source identity/proof refs и их canonical IDs от execution version не меняются.

Это уточнение **supersedes только кандидат** P1.1/P2.1: полный порядок SourceRegistryMutationInput теперь operation_id, world_uid, execution_version, changes, membership. Кандидат ID 72105 ещё не принят/реализован/использован для сохранённых bytes; изменение его проекта не является runtime wire migration. Перед freeze нужны реальные fixed vectors, collision checks и nested round-trip. Если обнаружится persisted use предыдущей формы, её нельзя переопределить: потребуется отдельная schema version. request fingerprint включает execution_version; SourceMutationApplied.request_fingerprint и immutable request record связываются с обновлённым canonical request.

REC-1 пока **PARTIAL, не закрыт**: конкретизирован способ binding, но owning terrain projector/body/tombstone и влияющие inputs ещё не приняты. Для его закрытия нужен execution registration dossier с точными owner classes/modules, immutable fields и consumer traces; scalar version без такого dossier не подтверждает воспроизводимость. Полноценная migration всех Source writers не входит в этот шаг.

### P2.14. Terrain owning contract: установленная граница и запрос (2026-11-14)

Проверены terrainRegistryEntry.py, eligibilityRule.py, hillPolicy.py, hillShape.py, surfaceCoating/surfaceSupportInput.py и landcover/planning/capturedSources.py. Findings до выбора body representation:

| Evidence | Следствие для body/projector |
|---|---|
| TerrainRegistryEntry.eligibility — list[EligibilityRule] при frozen outer model | Нужна owning immutable representation либо согласованная правка модели; frozen alone не обеспечивает deep immutability |
| has_authored_hills читает model_fields_set | Body должен сохранять absent / explicit None / policy; обычный полный dump с defaults не обеспечивает round-trip |
| TerrainSupportEntry содержит только key/category/default_material/merge_rank/eligibility/hills/hills_authored | Это частичная consumer projection; нет основания использовать как полный Source terrain body или добавлять в неё все Source поля |
| capture_landcover_policy переносит captured.hills_authored отдельно | Authored bit уже нужен реальному consumer, это не придуманная Source metadata |
| HillPolicy.resolved_shapes при пустом shapes вызывает HillShape.catalog() | Каталог/его порядок входят в influencing execution semantics; неизменность body bytes не фиксирует изменение каталога автоматически |
| EligibilityRule имеет ordered tuple/list употребление и numeric bounds validators | Сохранить owning validation и порядок; не сортировать rules как set без consumer доказательства |

По разрешению пользователя создан отдельный owning clarification чат «Terrain registry: контракт body и projector для Source», id 01a1d6e7-7dc4-71c0-a570-5abda0bffe62. Запрошен только новый terrain-source-execution-contract-dossier.md: complete immutable body/nested types, reuse inventory, consumers/semantic fields, canonical format/projector/ambient inputs/ref-integrity/tombstone/bootstrap. Код/Pack/DAG/чужие планы не поручались. Ответ и joint review ожидаются. До них новый Source mirror terrain DTO не создаётся, REC-1 остаётся PARTIAL.

### P2.15. Полученный Terrain dossier: проверка реализуемости (2026-11-14)

Получен [terrain-source-execution-contract-dossier.md](terrain-source-execution-contract-dossier.md). Владелец рекомендует укрепление existing TerrainRegistryEntry/WorldTerrainRegistry, все 18 полей semantic, immutable nested tuples и SEQUENCE membership; эти рекомендации требуют joint review, не приняты автоматически. Mirror DTO и partial TerrainSupportEntry как полный body исключены. Полный caller/writer inventory и owning ref-integrity остаются OPEN.

Проверкой текущего app.encoding.canonicalCodec.CanonicalCodec установлено: BaseModel кодируется ровно по model_fields. RegisteredTypeEntry содержит только type_id/python_type/kind; hooks для добавочной authored-presence metadata нет. Поэтому предложение dossier «после 18 полей» добавить hills presence тем же codec пока не реализуемо через existing manifest. Нужен конкретный owning representation/presence контракт и compatibility trace; расширение generic codec либо зеркало terrain body не разрешены этим замечанием. Уточнение отправлено владельцу Terrain.

Предложенный terrain value adapter также должен быть оформлен как internal registered format/value binding в composition. Название «публичный pure adapter» не разрешает Source→Terrain public helper в обход DAG. Окончательная import/call boundary запрошена вместе с representation. Source tombstone/provenance остаются Source-owned, не передаются Terrain. REC-1 не закрыт до устранения этих пробелов и остальных prerequisites dossier.

### P2.16. Terrain presence: устранение codec blocker (2026-11-14)

Владелец уточнил dossier: вместо невидимой metadata предлагается обычное 19-е поле hills_authored: StrictBool в существующем TerrainRegistryEntry. Public helper отозван в пользу internal registered composition binding. Это устраняет конкретное противоречие P2.15 с возможностями canonical manifest, но ещё не означает принятия изменения owning POJO/callers.

Source проверил _decode_one в app.encoding.canonicalCodec: полный ordered field roster сверяется с owner.model_fields **до** model_validate. Следовательно, после регистрации 19-field модели canonical payload без hills_authored должен отклоняться до legacy before-validator; он не может восстановить marker догадкой. Полный canonical decode с hills=None/hills_authored=False сохраняет false. Encode читает поля непосредственно и не вызывает proposed legacy serializer. Расширение generic codec для этого representation не требуется.

Условия joint acceptance остаются явными: strict/deep immutable модели; preserving legacy export flags/schema; capture_landcover_policy передаёт marker; with_hills/with_eligibility сохраняют принятую семантику; generic model_copy/model_construct/replace и persisted canonical registrations проверены. Legacy JSON, canonical field dict и typed durable reader — разные входы; последний не проходит через legacy authored_hills_key_from_wire. Manifest IDs/format и full round-trip tests ещё отсутствуют. REC-1 остаётся PARTIAL до полного owning dossier acceptance, Source tombstone и остальных recovery gates.

### P2.17. Source tombstone и pruned revision (2026-11-14)

Основание — основной план: tombstone является revision с deleted flag, не отдельной сущностью. Этот срез проектирует registry-member DELETE; удаление самой collection и restore/recreate не добавляются. Новый публичный SourceTombstone DTO, фиктивный пустой ArtifactRef либо body Terrain с null-полями не создаются. Принятый live SourceBodyVersion/proof manifest не меняется.

Предлагаемый storage invariant exact object revision index (не новый публичный POJO): immutable identity + seq + semantic_hash + deleted: strict bool + created_attempt_id. Live revision имеет immutable body ArtifactRef mapping; deleted revision его не имеет. Prune — отдельный факт прекращения доступности ранее live mapping, не изменение deleted/seq/hash и не новая semantic revision. Identity, assigned seq/hash, original body ref и creation provenance не стираются при prune: это позволяет отличить sanctioned prune от storage corruption и не переиспользовать identity/seq. Точные storage rows/events/SQL guards остаются revision-storage implementation slice.

| Exact состояние | Live body read | Root eligibility |
|---|---|---|
| Live, mapping retained | Прежнее проверенное body | P2.11 CREATE либо REQUIRE_EXISTING |
| Deleted revision | SourceFailure/TOMBSTONE, body отсутствует по контракту | Отказ TOMBSTONE, body root не создаётся |
| Live revision после explicit prune | SourceFailure/REVISION_PRUNED, без latest fallback | Отказ REVISION_PRUNED |
| Live retained mapping, bytes пропали | MISSING_BODY либо CORRUPT_BODY по реальной проверке | Не трактовать как tombstone/prune, repair не выполняется |

DELETE проверяет expected exact **live** ref в той же transaction, где проверяется итоговый ref-integrity graph. Назначает next seq этой identity и deleted=true, связывает creation attempt и operation→revision link, удаляет identity из нового collection body и сохраняет старые live roots. Outcome содержит tombstone SourceVersionRef и проверенную collection revision. Tombstone ref не включается в live capture dependencies. Replay committed operation возвращает прежний outcome; новый DELETE уже deleted identity — TOMBSTONE, не новая seq. No-op DELETE missing entry не вводится.

**Кандидат semantic hash tombstone v1:** existing CanonicalCodec над `("source.registry-member.tombstone", 1, registry_member_id)`, затем existing content_digest(bytes).hex(). Source-owned internal модуль `application/worldData/sourceVersioning/encoding/tombstoneEncodingV1.py`; identity кодируется принятым RegistryMemberId binding из SOURCE_PROOF_SCHEMA_V1, без нового record/type ID. Первый tuple string — фиксированный доменный tag, не пользовательский *_kind carrier. Root tuple отличает encoding от live body record. Версия 1 — фиксированная версия encoding, не seq. Seq, operation/attempt, время, execution_version и прежние bytes в hash не входят; deleted смысл для одной identity стабилен, а history различается seq. Это кандидат только для registry member, не произвольных SourceObjectId.

Owning execution registration ссылается на этот точный tombstone encoder. Его изменение требует нового согласованного encoding/semantic contract; нельзя переопределить v1. Не вводится второе hash-ядро. Root tuple/identity binding и domain tag должны получить golden bytes/hash vectors с реальными Source identity POJO до freeze. Пока это проект формулы, не вычисленный или проверенный runtime vector. Историческое общее упоминание SourceTombstoneVersion не используется как разрешение зеркального public record.

Условия проверки: DELETE сохраняет historical body/root; TOMBSTONE отличается от REVISION_PRUNED и отсутствующих bytes; digest не зависит от attempt/seq; identity/world/descriptor/key различаются canonical bytes; recovery/rollback не оставляют deleted latest без согласованного membership/terminal; repeated terminal replay не назначает seq; orphan/tombstone body mapping запрещён; prune не меняет revision semantics. Exact inbound ref policy и Terrain SEQUENCE membership всё ещё требуют owning acceptance. P2.17 закрывает предложенную форму Source tombstone, но не объявляет REC-1 или DELETE runtime принятыми.

### P3.1. Конкретная внутренняя карта Source mutation/recovery (2026-11-14)

Следующая карта заменяет абстрактную роль «Source apply implementation» для **internal** проектного среза. Она не объявляет новый public CRUD, не назначает DAG-ноды и не разрешает Source самостоятельно оркестрировать чужие public pipelines. Прежний основной gate pregame publication/append-only writes сохраняется. Public entry, staging caller и первоначальный claim остаются отдельной согласуемой границей P3.3.

Все пути ниже начинаются с app.application.worldData.sourceVersioning. Классы предлагаемые, runtime отсутствует.

| Класс / модуль | Ответственность и зависимости | Effects и критерий отказа |
|---|---|---|
| SourceMutationExecutionRegistry / mutation/executionRegistry.py | Exact descriptor+execution_version → неизменяемый на lifetime attempt экземпляр SourceRegistryMutationApplier; registration задаётся composition | Lookup без IO; отказ при fallback на latest version или runtime замене регистрации |
| SourceRegistryMutationApplier / mutation/registryMutationApplier.py | Одна registry transaction body: validation/expected/ref-integrity → назначение revisions → owning rows/membership → links → full roots; использует фиксированные owning format/value bindings | Borrowed domain scope; отказ при own commit, вызове owning public CRUD или выдаче durable success до commit |
| SourceMutationAttemptRunner / mutation/attemptRunner.py | Привязывает exact executor к одному PublicationExecutionGrant, вызывает domain body, переводит SourceFailure в rollback-carrier, передаёт Applied/Refused в existing terminal owner | Не stage/claim/takeover и не retry; отказ при повторе domain(), catch-and-commit после SourceFailure или смене request |
| SourceMutationLinkStore / mutation/linkStore.py | Полный touched set P2.7 | Scoped append/read, без duplicate terminal |
| SourceRootEligibilityBinding / retention/rootEligibilityBinding.py | Link+status+checked attempt provenance → acquisition mode P2.11 | Read-only; не вычисляет полномочия из caller uid |
| SourceRootReadBinding / retention/rootReadBinding.py | Exact body mapping → owning storage closure P2.5 | Read-only; не acquire/release, не latest fallback |
| SourceDiagnosticLogProjector / logging/diagnosticProjection.py | SourceFailure → safe typed log entries | Pure; не дублирует publication emitter |

Source revision-index storage остаётся отдельным конкретизируемым контрактом шага revisions/history: в нём нужно принять append-only rows/events и latest read. Нельзя скрыть этот незакрытый порт внутри applier или использовать WorldService._save как его готовую реализацию. Owning terrain row writer также не назначается Source вместо Terrain.

### P3.2. Execution lookup, body и terminal boundary

Предлагаемые internal signatures (не public payload):

```python
def resolve(
    self, descriptor: SourceDescriptorKey, execution_version: StrictInt,
) -> SourceRegistryMutationApplier | None: ...

# SourceRegistryMutationApplier; immutable configured execution binding
async def required_refs(
    self, scope: CommitReadScope, request: SourceRegistryMutationInput,
) -> tuple[ArtifactRef, ...] | SourceFailure: ...

async def apply_in_scope(
    self, scope: CommitScope, request: SourceRegistryMutationInput,
) -> SourceMutationApplied | SourceFailure: ...

# SourceMutationAttemptRunner
async def run(
    self, grant: PublicationExecutionGrant,
    request: SourceRegistryMutationInput,
    execution: SourceRegistryMutationApplier,
) -> SourceMutationApplied | SourceFailure: ...
```

resolve валидирует exact positive version и registered descriptor, возвращает None только при отсутствии поддержанного exact исполнителя. Предъявленный request уже checked immutable ledger value; resolve не декодирует тела, не читает latest и не запускает projector. Ссылка на executor — обычная internal dependency с фиксированной registration, не сериализуемый token. Caller не конструирует executor и не подменяет его callbacks. Publication преобразует None в согласованный EXECUTION_UNAVAILABLE с descriptor/version, сохраняя request/holds. При terminal replay lookup не выполняется.

required_refs вычисляет полный canonical unique closure **candidate request artifacts**: CREATE/UPDATE bodies, after-membership body и format-required dependencies. Не принимает список refs как доказательство полноты и не включает произвольные latest bodies. DELETE не имеет candidate member body. Execution semantics/code версия фиксируется registry, а не фиктивным ArtifactRef. Expected historical revisions читаются под Source root protection в domain scope; их нельзя объявить staged кандидатами. Если owning registration требует внешние immutable execution inputs, они должны быть явно добавлены в request binding до его приёмки (REC-1), а не обнаружены из ambient configuration в required_refs.

run использует owning transaction_for_attempt(grant), открывает domain() один раз и проверяет request operation/world/fingerprint против grant-bound scope через принятые internal guards. execution должен совпасть с registered descriptor/version этого request. Вызов apply_in_scope выполняет локальную атомарную Source операцию; source checks агрегируются до зависимых effects. Предыдущие domain writes всегда откатываются при SourceFailure, независимо от того, успел ли текущий adapter сделать write.

Порядок успешного body: проверить original expected object/membership и итоговый ref-integrity → вычислить owning semantic hashes/назначенные seq → записать owning rows и exact revision/membership/provenance → полный operation linkage → root eligibility/closure/acquire. Эти действия используют один domain scope. На выходе получается provisional SourceMutationApplied. Runner передаёт его attempt.succeed; подтверждённый outer commit precedes наружный Applied. Ни applier, ни stores не пишут terminal отдельно.

На SourceFailure runner поднимает SourceMutationRollback с тем же failure из domain(), дожидается confirmed rollback и только затем формирует SourceMutationRefused с operation/world/request fingerprint и исходным failure. attempt.refuse фиксирует refusal+operation-hold cleanup общим outer commit; после commit run возвращает исходный SourceFailure. Unknown rollback/commit и infrastructure exceptions не превращаются в Refused и не приводят к повторному body. Cancelled invocation сохраняет отдельную owning cancellation/unknown semantics. Терминальный OperationCancelled обрабатывается внешним replay до run; новый Source cancelled DTO не создаётся.

required_refs и apply_in_scope — internal стадии одного принятого execution binding, не самостоятельные DAG операции. SourceMutationRecovery остаётся owning internal infrastructure inspect/takeover service; он не получает право вызывать Terrain public CRUD. Exact разрешённый caller runner и transport ошибок фиксируются в P3.3, не выводятся автоматически из этой карты.

### P3.3. Что ещё требуется для implementation-ready slice

1. Source revision-index append/read port, scoped owning terrain writer и их typed errors; полный storage schema/order без legacy UPDATE bypass.
2. Конкретная композиция public owning mutation/recovery входа: typed data/result/errors, прямой согласованный DAG caller, путь bytes→staging→READY→claim→grant→runner, логирование; без выставления lease/scope/executor в public DTO. Новую ноду определяет пользователь после контракта, не этот документ.
3. Terrain immutable representation/caller compatibility, manifest/format/ref-integrity и accepted execution registration dossier; initial bootstrap и full writer inventory в утверждённом порядке.
4. Public typed representation infrastructure refusals/unknown для caller и cancellation replay; внутренние exception classes сами по себе public error map не закрывают.

REC-5 продвинут до named Source classes и nested trace, но остаётся OPEN по перечисленным точкам. Это не permission реализовать каркасы в обход полного среза. REC-1, mutation/refusal canonical vectors и обязательная совместная приёмка также остаются prerequisites.

### P3.4. Closure preflight до takeover: порядок и отказ (2026-11-14)

Получена сверка publication «Ответ на Source P3.1–P3.3: runner и required closure». required_refs вызывается через read facet **той же CONTROL BEGIN IMMEDIATE**, после повторных terminal/binding/phase/expected-attempt checks и до первого transfer/fence append. Внешнее preflight-чтение не является доказательством: concurrent cancel мог завершить operation и снять holds. require_domain_attempt здесь не применяется, поскольку DOMAIN attempt ещё не выдана.

Candidate closure не равен полному transfer set: IOperationHoldTransfer перечисляет все live operation holds, включая leftover. Проверка защиты candidates и полного переносимого набора выполняется в той же serialized границе. Replay existing terminal возвращается до required_refs и executor lookup. Runner вызывается только после confirmed takeover и durable start CAS/grant. claim_recovery не запускает body скрыто.

Source предлагает единственный internal exception carrier `SourceMutationPreflightRejected` в `app.application.worldData.sourceVersioning.mutation.sourceMutationErrors`, поле `failure: SourceFailure`, без нового diagnostic DTO/enum. Он отличается от SourceMutationRollback областью применения: отказ до domain attempt, а не откат частично выполненного body. Конструктор сохраняет исходный strict SourceFailure без смены operation/code/path/context; для required_refs recovery operation=APPLY_MUTATION. Carrier не serialized/persisted и не является terminal outcome.

Когда required_refs вернул SourceFailure, recovery adapter поднимает этот carrier **внутри CONTROL transaction**, до append. Он пересекает transaction boundary; только после confirmed rollback внешний caller получает исходную проверочную причину через этот typed exception. claim_recovery сохраняет успешный union OWNER|TERMINAL. Ни attempt.refuse, ни новый terminal, ни release holds, ни смена fence не выполняются. Unknown rollback остаётся UnknownCommitOutcome, а не подтверждённым preflight rejection. Arbitrary infrastructure exceptions не преобразуются в SourceFailure.

На public boundary этот случай нельзя свести к тому же неразличимому SourceFailure result, который runner возвращает после committed refusal. До принятия public error map P3.3 carrier остаётся internal: consuming boundary обязан сохранить различие «проверка не прошла, durable исход не записан» / «terminal отказ committed» / «исход неизвестен». Дополнительный public envelope автоматически не вводится. Логирование должно сохранять исходный Source diagnostic context и факт preflight, без объявления durable REFUSED; owning event mapping требует подтверждения publication.

Проверки: failure required_refs не вызывает transfer/start/runner/terminal; old operation/attempt/fence/holds идентичны до и после confirmed rollback; cancel между ранним preflight и CONTROL transaction возвращается как terminal без нового closure traversal; missing candidate hold не чинится; failure rollback acknowledgement не маскируется preflight error. Этот transport — Source proposal для owning review; P3.3 public entry и общая приёмка остаются OPEN.

### P3.5. Owning ответ по preflight diagnostics (2026-11-14)

Publication подтвердил P3.4 internal transport в разделе «Ответ на Source P3.4: preflight carrier и logging» owning response. Согласованное направление проектирования: claim_recovery OWNER|TERMINAL не меняется; SourceMutationPreflightRejected выходит после confirmed CONTROL rollback, без grant/domain/terminal/fence/cleanup. Публичный error mapping и полный implementation slice ещё не приняты.

Для recovery после successful phase/CAS checks предлагаются два WARNING PROVISIONAL_REFUSAL наблюдения одного recovery_id: до rollback с durability=PROVISIONAL и после подтверждения с durability=OUTER_ROLLED_BACK/exception_type=SourceMutationPreflightRejected. Второе означает окончание проверки без durable business terminal. Оба сохраняют исходную Source projection и старую реально прочитанную attempt pair; source_operation=APPLY_MUTATION, terminal_kind/cancellation_reason/new pair/hold_count/fault=None. Для OUTER_ROLLED_BACK это явное расширение текущего event invariant; его должен включить единый owning roster до implementation, не только appendix.

Если rollback acknowledgement неизвестен, вместо второго refusal идёт OUTCOME_UNKNOWN/ERROR с diagnostics=(), реальным uncertainty exception и последним подтверждённым context. Caller получает UnknownCommitOutcome. DOMAIN_ROLLED_BACK здесь запрещён: domain savepoint не открывался. FAILED не подменяет ожидаемую Source проверку; durable REFUSED не заявляется.

Source статически не нашёл противоречия P3.4 с этим mapping. Initial preflight без существующей attempt не покрывается данной ветвью, synthetic old pair не допускается. Pending: синхронизация единого logging invariant у владельца, P3.3 public boundary и реальные rollback/sink проверки. Logging ТЗ severity не меняется: оба события WARNING согласно P2.12.

## Следующие проверяемые проектные результаты

| Порядок | Результат | Владелец и граница |
|---|---|---|
| P1 | Concrete Source mutation outcome, input/prepared batch и error mapping; отсутствие дублирования receipt | Source; не расширять proof POJO и не вводить универсальный CRUD мира |
| P2 | Предложение exact lifecycle kind/outcome registration и root holder binding с nested signatures | Source requirements + owning Artifacts/publication acceptance; existing store/codec/checks перечислены выше |
| P3 | Одна concrete apply boundary: body/membership/revision/root/outcome в общем CommitScope, idempotency/recovery | Source internal binding + owning domain writer; без nested BEGIN/COMMIT |
| P4 | Приёмка по всем критериям проекта и принятие отдельного implementation slice | Сохранить inventory→projector→revision storage порядок; только затем implement-plan |

Необходимые сценарии: A→B→A; label-only; unknown outcome после commit; rollback после записи body/membership; same operation/different fingerprint; source delete при held historical body; GC между staging и apply; смена latest при действующем capture; restart до/после terminal. До этих контрактов и проверки runtime durable API остаётся NOT ACCEPTED.

## Статус текущего прохода

Выполнен read-only trace pregame staging; предъявлены concrete SourceMutationApplied и SourceRegistryMutationInput/варианты, optimistic membership rules и label-only mapping policy (P1.1–P1.4). Устранена циклическая зависимость request fingerprint от stage: refs вычисляются до lease. В P2.1 определён кандидат mutation manifest/IDs/field order; в P2.2 подготовлен точный запрос владельцу Artifacts/publication. Owning projector/codec, golden vectors реальных POJO, новые diagnostic conditions, terminal registration и root binding ещё требуют проработки и review. P1–P4 не объявлены завершёнными; принятая схема SourceDurableProof и закрытые R1/R2 от этого не меняются.
