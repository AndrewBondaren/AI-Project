# Pack activate — сохранение отказа и replay

Статическая сверка 2026-11-12. Область — Pack activation, отдельно от [публичных write-операций](pack-v2-public-write-operations.md), которые прорабатываются в другом чате. Runtime/SQL не менялись; тесты не запускались.

## Уже описанное решение, не новый выбор

[ТЗ Pack](../../docs/tz_world_pack_storage.md), таблица публичных исходов, строка «Доменный отказ после получения OWNER», уже предлагает PackActivationRefusal(operation_id, request_fingerprint, diagnostics: tuple[PackActivationIssue, ...]) и durable mapping в SnapshotApplyResult(category=REJECTED, committed=None, diagnostics=...). При replay Pack восстанавливает публичный отказ из terminal. Не предлагать новый lifecycle или второй terminal store из-за имени SnapshotApplyResult. Это существующий проект ТЗ; полный binding ещё не принят как реализованный.

## Подтверждённая цепочка

- `application/publication/service/operationLedger.py::OperationLedger.record_refusal(claim: PublicationOwner, outcome: SnapshotApplyResult)` делегирует existing IOperationStore.
- `db/repositories/sqlite/snapshotCore/operations/operationStore.py::SqliteOperationStore.record_refusal` повторно валидирует claim/outcome, запрещает COMMITTED, открывает bookkeeping transaction и проверяет lease/fence/phase перед сохранением. `_save` проверяет identity и неизменность уже записанного terminal.
- `db/repositories/sqlite/snapshotCore/operations/terminalCodec.py::StoredTerminalCodec` кодирует SnapshotApplyResult и восстанавливает его с checksum/row consistency checks. Его storage discriminator snapshot_apply обозначает форму результата; сам по себе он не доказывает запуск Snapshot apply.
- Existing `tests/snapshotCore/storage/publication/test_cas.py` содержит race двух PACK_ACTIVATION claims; проигравший записывает SnapshotApplyResult(CONFLICT) через record_refusal. Это evidence использования общего механизма, не приёмка целевого Pack activate: CAS-конфликт по Pack policy может требовать READY_INACTIVE, а не этот тестовый CONFLICT.
- `encoding/canonicalCodec.py` выбирает регистрацию по точному type(value). `application/artifacts/encoding/coreManifest.py` регистрирует FieldPathError, но это не регистрация всех его будущих подклассов. StoredTerminalCodec принимает расширенный CanonicalSchemaManifest и объединяет его с базовой схемой — готовая точка composition, новый codec не требуется.

## Остаток в ответственности Pack

1. Конкретизировать PackActivationIssue/refusal в предусмотренных ТЗ модулях без копирования FieldPathError и существующих diagnostics; PackActivationRefusal в проверенном backend/app пока не найден.
2. Зарегистрировать точный issue class и используемые им enum/context types через существующий canonical manifest extension; передать этот manifest в composition terminal codec. Проверить отсутствие конфликтующих IDs. Не стирать subtype до FieldPathError ради прохождения codec.
3. Pure mapping публичного отказа → REJECTED terminal сохраняет operation_id, request_fingerprint и diagnostics. Обратное преобразование проверяет kind операции PACK_ACTIVATION, category и concrete diagnostics; не превращает любой SnapshotApplyResult в Pack refusal. Владелец проверки — внутренняя реализация Pack activate, не DAG.
4. Проверить durable round-trip с конкретным issue subtype, рестарт и повтор после изменения head: исходные типы/поля/diagnostics возвращаются без нового CAS. Неподдерживаемый terminal или несовпадение identity отклоняется, не выдаёт выдуманный отказ.

Сохраняется порядок owning ТЗ: refusal под OWNER до доменных записей либо после подтверждённого rollback; при неизвестном commit сначала recovery. Infrastructure/cancellation не становятся REJECTED. READY_INACTIVE — отдельный PackActivationResult со своим удержанием, не разновидность domain refusal. Сохранение отказа не доказывает готовность scoped activation/handoff или release: эти проверки остаются отдельными.

Вывод: новый архитектурный выбор для durable refusal не нужен. Есть existing механизм и уже описанный mapping; незавершены конкретные Pack-типы, их registration/composition и проверка replay. Публичный activate этим trace не объявлен реализованным или принятым.

## Fingerprint активации и admission claim — следующая конкретизация

ТЗ Pack уже задаёт состав: версия контракта активации, kind, operation_id, полный expected, полный manifest, preparation_fingerprint. Это не новый выбор и не fingerprint подготовки. Existing `PackActivationInput` наследует PreparedPackCandidate и добавляет expected; он уже содержит все переменные поля. Отдельный PackActivationIdentity POJO с их копиями не нужен.

Предлагаемый внутренний pure `PackActivationIdentityCodec` в `application/worldData/pack/encoding/activationIdentityCodec.py` предоставляет `fingerprint(self, request: PackActivationInput) -> RevisionHex`. Он повторно валидирует request и использует existing `encoding.canonicalCodec.digest` над tuple `(activation_contract_revision, OperationKind.PACK_ACTIVATION, request)` с зарегистрированным concrete PackActivationInput и existing shared types из ARTIFACT_CORE_SCHEMA. Activation contract revision — закреплённая identity encoding-контракта, не pack_version, storage version или caller option. Её конкретное значение, canonical type ID и контрольный вектор остаются encoding gate; произвольные числа не назначаются. Никакой новой hash-функции, JSON-проекции вручную или второго списка полей.

Existing canonical codec кодирует model_fields в порядке объявления и включает exact registered type ID; `digest` вычисляет SHA-256 encoded bytes. Для текущего наследования порядок полей PackActivationInput: operation_id, manifest, preparation_fingerprint, expected. Контрольный вектор должен закрепить именно эту декларацию и всю вложенную схему. Изменение декларации требует явной проверки fingerprint-контракта; молчаливое сохранение старой identity после смыслового изменения запрещено. ARTIFACT_CORE_SCHEMA уже регистрирует OperationKind, ArtifactRef, WorldPublicationRef и snapshot refs; exact registration PackActivationInput в просмотренных Pack encoding/core registrations не найдена. Base PreparedPackCandidate не заменяет регистрацию наследника.

Полный expected включает world_uid, publication_id, pack_hash, snapshot_head, active_timeline_id и gameplay_started, включая null. Полный ArtifactRef включает формат/версию, kind, digest, nbytes/row_count по его owning модели. В fingerprint не входят вычисленный request_fingerprint, текущий latest head, timestamp, lease/fence и состояние holders. Изменение expected/manifest при том же operation_id — identity conflict, не retry с новой базой; новый запрос с новым expected требует новой подтверждённой подготовки/владения согласно ТЗ. Возобновление после release не синтезирует hold.

### Что уже обеспечивает ledger и чего он не обеспечивает

`SqliteOperationStore.claim_publication` сравнивает world_uid/kind/preparation_fingerprint и уже связанный publication_fingerprint до возврата terminal. Он проверяет только переданный digest, не вычисляет fingerprint Pack input. При record=None общий порт создаёт новую APPLYING operation; это допустимая возможность общего ledger, но не доказательство READY-кандидата Pack. При существующем не-READY record без terminal он возвращает BUSY.

Pack-owned admission обязан различать:

- тот же полный запрос с terminal — восстановить исходный результат по подтверждённой identity до проверки текущих holds/bytes; replay после release не требует повторного seal и не делает CAS;
- первая активация — существующая операция PACK_ACTIVATION в READY с точной preparation identity и подтверждённым candidate manifest, а не произвольный ref от caller;
- отсутствующая подготовка — отказ до создания publication claim, без автоматического запуска prepare;
- другой fingerprint при том же ID — identity conflict без нового эффекта; APPLYING/RECOVERY_REQUIRED — existing busy/recovery semantics, без выбора retry workflow внутри Pack.

Повторный scoped admission в atomic activation binding должен защищать владение/фазу от release и GC; предварительный read сам эту гарантию не даёт. Нельзя объявить raw claim_publication готовым Pack activate или менять общий ledger ради обхода этого требования. Конкретный typed mapping identity conflict до OWNER остаётся с existing Pack activation error contract; ValueError storage не превращать произвольно в durable REJECTED.

Ответственность PackActivationIdentityCodec — только strict canonical identity без IO/claim; критерий отказа — чтение latest, ручной сокращённый список expected/ref или использование preparation_fingerprint вместо fingerprint активации. Вызов выполняет внутренняя реализация Pack activate, DAG передаёт PackActivationInput без вычисления digest. Existing codec/schema classes остаются у Encoding и не копируются. Конкретные encoding IDs/vector и scoped activation binding всё ещё OPEN; здесь не объявлена полная архитектурная приёмка.

Проверки реализации: одинаковый request после restart даёт тот же digest; изменения каждого значимого поля expected/ref/preparation identity меняют digest (на валидных согласованных входах); один ID с другим request не возвращает старый success; replay после продвижения head и после release возвращает исходный terminal без CAS/hold; неизвестный ID не создаёт publication operation; malformed constructed/copied request отклоняется до effects. Эти тесты в рамках документальной сверки не запускались.

## Atomic activate: существующие механизмы и точный остаток

Статическая сверка 2026-11-12. Новый CAS/transaction manager не требуется по найденным данным:

| Механизм | Подтверждённый existing контракт | Предел гарантии |
|---|---|---|
| Полный CAS | `SqliteWorldPublicationStore.compare_append(scope, expected, next_publication) -> WorldCasResult` сравнивает observed != expected как полный WorldPublicationRef; differing_fields строится по всем model_fields. MISMATCH возвращает observed без вставки; APPLIED добавляет publication с predecessor и следующим seq | Не проверяет Pack payload/closure и не приобретает удержания |
| Физический commit | `SqlitePublicationCommitStore.transaction(operation_id)` выдаёт scope в одной UOW, запрещает nested/ambient transaction, подтверждает rollback/commit; неизвестный исход quarantines coordinator и даёт UnknownCommitOutcome | Не выбирает доменный исход Pack; не является готовым Pack activation service |
| Заимствование scope Artifacts | `SqliteArtifactScope.bind(scope)` и его transaction/read_scope переиспользуют переданный scope; constructors проверяют общий coordinator/registry/access | Нельзя заменить согласованную композицию двумя экземплярами coordinator или самостоятельным commit holder adapter |
| Handoff | `SqliteArtifactHolders.handoff` требует APPLYING, closed admission/drained writers, sealed refs и существующих destination holders; проверяет назначения до изменений, затем снимает только переданные operation holds | Не устанавливает новый root owner кандидата автоматически; не обнаруживает пропущенный caller ref как полный manifest closure |
| Terminal | `SqliteOperationStore.record_terminal` и `SqlitePublicationEvidence.check` сверяют operation binding и историческую publication. ACTIVE требует публикацию данной операции; READY_INACTIVE — observed publication без публикации данной операции | Это не проверка полного удержания manifest/payload/source closure. Успешная запись terminal не заменяет Pack/Artifacts admission |

Evidence существующего теста: `tests/spatial_pack/test_manifest_activation_rollback.py::test_refused_handoff_rolls_back_applied_cas` выполняет APPLIED, затем получает отказ handoff; второе соединение видит старый head, отсутствие terminal новой операции и сохранённый operation hold. Тест использует fixture BLOB, ручную композицию и прежний manifest, а не публичный Pack activate. Здесь тест не запускался; его наличие не закрывает production gate.

### Сохраняемый порядок, без нового workflow

Existing ТЗ Pack «Последовательность исполнения активации» и Snapshot-план 4D3 задают внутреннюю атомарную реализацию одной публичной операции. После admission/claim и защищённой проверки bytes до короткого commit внутри scope должны повторно проверяться изменяемые условия: точная identity/фаза кандидата и действующее владение необходимыми refs. Затем один полный compare_append; APPLIED сохраняет ACTIVE и владение опубликованной версии, MISMATCH — READY_INACTIVE с исходным manifest и observed publication. Установка destination ownership предшествует снятию передаваемых holds; terminal и все изменения атомарны. Возврат успеха только после подтверждённого commit.

MISMATCH не запускает новый bake/prepare, не меняет expected и не выбирает следующий pipeline. Это результат локального CAS внутри одной атомарной операции; выбор дальнейшего workflow принадлежит DAG. Внешние Source/producer public API внутри activate не вызываются. Unknown commit не становится доменным REJECTED; сначала восстанавливается исход по существующему publication recovery contract.

**Что ещё требуется предъявить для binding:** (1) concrete внутренний entry 4D3, объединяющий перечисленные existing ports и error mapping; (2) точное отображение полного Pack retention set в source/destination ownership, включая root manifest для ACTIVE/READY_INACTIVE; (3) scoped проверка необходимых source holds и защита от release/GC; (4) composition с одним coordinator/registry/access; (5) тест через публичный Pack activate, включая race со стартом gameplay и потерю commit-ответа. Source latest freshness не вводится заново вместо принятой проверки captured данных/удержаний.

Эти требования относятся к сборке принятого binding, а не к созданию новой транзакционной системы. Владелец транзакционного механизма — publication; holds — Artifacts; смысл и полный состав кандидата — Pack. Пока binding не предъявлен, полный activate OPEN. Части полного CAS/rollback уже имеют existing реализацию и не должны повторно фигурировать как отсутствующие механизмы.
