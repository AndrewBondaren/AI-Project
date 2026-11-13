# Source — pregame revision staging и root lifetime

Дата: 2026-11-13. **DESIGN OPEN / не принят для реализации.** Отдельный следующий проектный срез; не изменение принятого SourceDurableProof. Основание — OPEN pregame staging из [акта независимой приёмки](source-durable-proof-contract-acceptance-2026-11-13.md) и §5 основной Source proof спецификации.

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
| SourceRegistryMutationInput | operation_id: EntityUid, world_uid: EntityUid, changes: tuple[SourceRegistryChange, ...], membership: SourceCollectionMutation |

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
| 72105 | SourceRegistryMutationInput | operation_id, world_uid, changes, membership |
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
