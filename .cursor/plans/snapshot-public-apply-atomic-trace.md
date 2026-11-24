# Snapshot public apply — S3 atomic trace и contract gates

## Актуальный срез 2026-11-24: public apply после повторного ревью

Зафиксирована обратная связь второго междоменного координатора (`Between domain operations (2)`, `01a1f529-898c-7342-82f4-1e68983b3a9c`). Это ограниченная сверка, не общая архитектурная/runtime-приёмка. Три прежних локальных замечания независимого ревью закрыты; локальный C2 и проверенное внутреннее service wiring получили PASS (56 независимо выполненных тестов). Public apply, конкретная Lifecycle integration и ARCH-0 остаются OPEN. Synthetic caller частных методов не доказывает публичный маршрут.

Разделы 1–7 ниже сохранены как исторический trace от 2026-11-14: их preliminary R1–R3, сообщения об отсутствии cancellation carrier и старых mismatch carriers не являются текущими OPEN и не отменяют последующие C2/H2/H3 решения. Текущие owning уточнения: [C2 facts/diagnostics](snapshot-receipt-facts-diagnostics.md), [atomic boundary](snapshot-lifecycle-atomic-boundary.md), [H2](snapshot-refusal-transport-h2.md). Новые междоменные предложения требуют общей сверки назначенным DAG-координатором и решения пользователя; эта запись не объявляет их принятыми.

### Пять стыков для последовательного разбора

| № | Стык / статус | Что требуется зафиксировать до зависимой реализации | Ответственность и критерий проверки |
|---|---|---|---|
| 1 | Admission → claim — OPEN | Exact admission Input/Output/Error, источник concrete request model/registry, producer request fingerprint и соединение с `_claim_publication` | PatchSet владеет invariants и canonical encoding; Snapshot адаптирует admission к своему публичному контракту. Нет копии predicates/serializer, нет предположения «caller уже вызвал assemble». Invalid input не доходит до claim; exact replay не запускает новую попытку. |
| 2 | Owner → transaction — OPEN | Constructor dependency transaction owner, exact вызов и привязка scope к полученному claim | Publication владеет transaction/acknowledgement; Snapshot собирает вызовы. Чужой claim/scope отклоняется; unknown rollback/commit не превращается в business refusal. |
| 3 | Expected/source bindings — OPEN | Exact guards/resolver calls, исходные данные и outputs в attempt context | Snapshot проверяет общую publication/source boundary; доменные predicates остаются владельцам. Caller POJO не доказательство authority. Все bindings pinned к исходной publication; все validations раньше любого apply. |
| 4 | Assigned refs / metadata — OPEN | Кто назначает world/player refs, откуда turn_id/created_at, dependency holders и точный transferred set | Snapshot назначает refs и собирает metadata; Artifacts владеет handoff. Нет угадывания destinations/retention. Metadata, handoff, CAS и terminal атомарны; пустой synthetic route не доказывает маршрут с artifact refs. |
| 5 | Public Error boundary — OPEN | Полный exact mapping public ошибок и существующих carriers, включая отказ при сохранении refusal | Infrastructure не становится business diagnostic. Refusal сохраняется после подтверждённого rollback; COMMITTED возвращается после commit acknowledgement. Durable OperationCancelled сохраняет operation_id и отличается от invocation CancelledError; engine mapping остаётся отдельным OPEN. |

### Неизменный порядок публичной попытки

Request admission + request fingerprint → claim / exact terminal replay → outer transaction → expected-context checks → H3 source metadata binding → dependency binding + actual section fingerprints → все handler.validate → remaining pinned bases с reuse source → каждый handler.apply с немедленной receipt validation → metadata / handoff → world CAS → player CAS → terminal в той же transaction → confirmed commit → concrete T.

Replay не означает «без любых hashes»: request fingerprint нужен для claim; проверки целостности persistence сохраняются. Exact terminal replay пропускает новую попытку, dependency/section fingerprint checks, handlers и source reads для повторного исполнения. Actual section fingerprint остаётся после claim/replay и до первого validate, через PatchSet-owned `SectionFingerprint`.

Validation/apply/CAS refusal должен выйти за outer transaction. Сохранение refusal допустимо только после confirmed rollback; возвращать durable refusal можно только после подтверждения его записи. Unknown исход имеет приоритет. Ни private helper, ни новый public caller не вправе менять этот порядок.

### Пункт 1: факты к обсуждению и минимальное направление

**Сведение 2026-11-24:** подробное предложение, owning feedback и делегирование реализации пункта 1 вынесены в [Snapshot apply admission → claim](snapshot-apply-admission-claim.md). Пользователь поручил фиксацию и делегирование ограниченного среза; общая сверка основным координатором остаётся обязательной. Нижний текст фиксирует исходные факты, а не отменяет уточнённый mixed diagnostic transport/owning admission API. Публичный apply и остальные четыре стыка этой делегацией не разрешены.

В actual коде уже существуют:

- `PatchSet.coherent_request()` → `PatchSetInvariants.check_core(self)`: constructor invariants; prepared-order прямо исключён из constructor guarantee.
- `PatchSetInvariants.check_prepared_order(data)` → tuple violations: существующий чистый predicate владельца PatchSet; его не копировать в Snapshot и не заменять повторным assemble.
- `PatchSetCodec[S](registry, request_model).fingerprint(request: PatchSet[S]) -> RevisionHex`: existing canonical producer через `encode` и `content_digest`. Encode проверяет exact concrete model, strict validation, supported format и checked section codecs. Это request fingerprint, не проверка declared section fingerprint.
- `WorldSnapshotService._claim_publication(operation_id, world_uid, preparation_fingerprint, request_fingerprint) -> PublicationOwner | T`: существующий seam, отдельно передающий persisted cancellation. Публичный `apply` пока не соединяет эти части.

Предлагаемое направление для согласования: Snapshot admission использует существующие PatchSet predicates и codec; его собственная ответственность — порядок вызовов и перевод результатов/ошибок в accepted Snapshot boundary. Доменные validate и actual dependency fingerprint checks остаются внутри новой попытки. Не вводить второй serializer, второй набор invariants или Snapshot-owned доменное доказательство. `snapshotRequestValidator.py` в actual validation package отсутствует: такое имя нельзя выдавать за реализованный контракт.

Остаток пункта 1: назвать exact adapter method/signature и источник его зависимостей, roster admission checks и mapping каждого отказа (включая prepared-order и ошибки encoding/registry), проверить выход в claim без повторного assembly. Пока это не предъявлено и не согласовано, пункт 1 остаётся OPEN; выбор направления не равен готовности контракта.

### Следующий delivery и граница scope

Сначала последовательно закрыть пять строк exact контрактами в owning документах и общей координаторской сверкой. Затем реализовать public assembly и synthetic/SQLite tests, вызывающие публичный `apply`; после этого — конкретную Time/Lifecycle integration. Проверки должны покрыть replay, validation refusal, immediate receipt fault, rollback предыдущих writes, CAS, unknown, scope expiry и acknowledgement, а не только private helpers.

IN: Snapshot / Publication transaction-persistence / PatchSet registry, доступные synthetic participants; artifacts handoff для маршрута с refs. OUT: реальные producers, write_changes, завершение Pack, production rollout. OUT не блокирует независимую работу. Новых DAG nodes/IDs/порядка не вводить; C2/H2/H3/D1–D7 не переоткрывать. Эта фиксация документальная: новые тесты в данном проходе не запускались, код не менялся.

## Исторический срез 2026-11-14 (статусы на дату записи)

Concrete предложения R1–R3 на дату этого среза: [snapshot-retention-cancel-diagnostics-contract.md](snapshot-retention-cancel-diagnostics-contract.md). R1 заменяет preliminary artifact→destinations запись на state/history-bound retention, поскольку иначе наследование остаётся неоднозначным. Подробные proposals ниже читаются с этим уточнением; утверждение о ещё не изменённых DTO/code относится только к исторической дате.

2026-11-14. Документальный этап плана snapshot-public-contracts-dag-integration.md. Публичные три метода описаны в snapshot-public-methods-contract.md. Этот документ проверяет именно apply; код/DDL/DAG, Source authored writer, Pack authority и Time T5 не меняются.

## 1. Existing owner/transaction trace

1. WorldSnapshotService revalidates PatchSet и registry/model/version/dependencies, вычисляет canonical request fingerprint через existing PatchSetCodec. DAG собирает PatchSet; Snapshot не строит чужие patches.
2. IOperationStore.claim_publication(SNAPSHOT_APPLY, operation_id, world_uid, preparation_fingerprint, request_fingerprint) — отдельная короткая transaction. Existing реализация либо возвращает PublicationOwner, либо PublicationTerminal, либо PublicationBusy; immutable identity mismatch сейчас ValueError. На terminal не запускаются handlers и повторные target checks.
3. PublicationOwner разрешает service продолжить одну попытку согласно existing claim; source-mutation grant/recovery proposal не переносится сюда автоматически. Artifact refs должны оставаться held от проверки до commit.
4. Владелец publication transaction — SqlitePublicationCommitStore.transaction(operation_id). Service читает expected world/player heads, gameplay/base/timeline/turn и validates все sections в принятом порядке. Конфликт до apply не вызывает handlers.apply.
5. Existing _apply_to_target выдаёт assigned context и последовательно вызывает handlers.apply. Внутри его yield service пишет metadata/handoff. После выхода yield выполняются world CAS, затем player CAS в expected order. Любой отказ/ошибка выходит за outer transaction и откатывает domain writes, metadata, handoff и все CAS вместе.
6. Только после успешного выхода _apply_to_target, но ещё внутри outer transaction, service формирует SnapshotCommitRefs и вызывает record_terminal(scope, COMMITTED). Затем coordinator подтверждает COMMIT; только после этого возвращается COMMITTED и эмитируется success.
7. Existing record_refusal(claim, outcome) открывает **отдельную** короткую transaction после подтверждённого rollback основного apply. Это accepted Snapshot port, не Source proposal с savepoint. При unknown rollback/commit refusal не записывается.

Public refusal возвращается лишь после confirmed record_refusal commit. Если отказ уже вычислен, но запись refusal не удалась, caller получает infrastructure/unknown, а не ложный durable REJECTED. Между rollback и refusal commit crash оставляет unresolved APPLYING; existing claim/recover не является автоматическим takeover. Это explicit runtime recovery limitation, не повод повторить handler из service.

## 2. Caller outcomes и holds — что уже следует из кода

| Состояние | Caller / durable результат |
|---|---|
| Exact stored SnapshotApplyResult | Возврат сохранённого исхода до target refs/handlers; immutable binding сначала |
| PublicationBusy | Public BUSY transport; никакого hidden retry/domain work |
| Body/CAS refusal + confirmed rollback + confirmed refusal commit | Existing CONFLICT/REJECTED, committed=None, исходные diagnostics |
| Refusal commit lost acknowledgement | OUTCOME_UNKNOWN; свежий coordinator читает ledger, не перезапускает body |
| Body commit lost acknowledgement | OUTCOME_UNKNOWN, не CONFLICT и не record_refusal |
| Cancelled invocation | CancelledError после owning cleanup; нельзя объявлять operation cancelled или не committed без acknowledgement |
| Success | Metadata/heads/handoff/terminal видимы вместе на втором connection |

Existing record_refusal **не освобождает operation holds**. Поэтому нельзя обещать cleanup по одному REJECTED/CONFLICT или считать terminal эквивалентом cancel. Если нужен release refused-operation holds, требуется отдельное принятое lifecycle решение; этот trace его не изобретает. Untransferred holds в успешном partial handoff остаются operation-owned по принятому 4D2 evidence.

## 3. Gate R1: отсутствует ownership artifact destinations

**Контрпример:** один SectionApplyReceipt содержит world и player state refs и retained_artifacts=(a,). Возможны три корректных намерения: a принадлежит world, player либо обоим. Existing receipt одинаков во всех случаях. Поэтому flat refs не определяют вход retained: Mapping[SnapshotRef, tuple[ArtifactRef,...]] для metadata builder. Публичный PatchSet также этого не определяет, а DAG не должен знать assigned snapshot IDs. Нельзя автоматически отдать ref всем, выбрать world или вывести назначение по format.

**Предложенное минимальное изменение до зависимого кода:** оставить публичный apply signature, уточнить internal receipt contract владельца Patch/Snapshot. Добавить explicit typed retention assignments на выходе handler, использующие assigned SnapshotRef из SnapshotApplyContext. Предлагаемый record `SnapshotArtifactAssignment` в dataModel/patch/results/artifactAssignment.py: `artifact: ArtifactRef`, `destinations: tuple[SnapshotRef,...]`, nonempty/unique; strict/frozen/extra-forbid/revalidate-always. В SectionApplyReceipt заменить flat retained_artifacts на `artifact_assignments: tuple[SnapshotArtifactAssignment,...]`; unique artifact entries, full union используется для transfer selection. Это **breaking proposal**, не принятый DTO и не разрешение мигрировать код.

Каждая destination должна входить в assigned context и принадлежать section owner согласно contract; foreign world/player отклоняется до metadata append. Много получателей разрешено явно. Inherited state требует полного retention closure текущей секции/назначения, включая no-op; новый receipt contract должен определить, как handler сообщает inherited artifacts без чтения чужих sections. Existing metadata содержит flat per-snapshot retained set, поэтому полное наследование нельзя восстановить автоматически при замене одной из нескольких секций. Этот связанный storage/read вопрос входит в R1 review; простая замена поля сама по себе его не закрывает.

Вариант «передать map из DAG» отвергается: раскрывает assigned internal refs и заставляет caller управлять storage ownership. Variant «оставить плоский receipt, resolver угадает» отвергается контрпримером. До принятия R1 existing проверенные helper/tests остаются как есть; production public apply readiness не заявляется.

## 4. Gate R2: terminal cancellation не имеет public apply representation

**Контрпример:** operation SNAPSHOT_APPLY отменена в PREPARING/READY; claim_publication того же preparation возвращает PublicationTerminal(OperationCancelled). SnapshotApplyResult допускает только COMMITTED/CONFLICT/REJECTED и требует непустые business diagnostics для последних. Преобразовать cancel в REJECTED означает выдумать business reason; CancelledError означает отмену invocation и также неверен.

**Предложение:** не менять SnapshotApplyResult/OperationCancelled enums. В application/worldSnapshot/errors.py добавить `SnapshotOperationCancelledError`, переносящий **existing OperationCancelled** как `outcome`, без нового cancel DTO. Это отдельный declared public control carrier, не SnapshotPublicFault.Kind и не asyncio.CancelledError. DAG mapping различает три факта: business refusal, durable cancelled operation, cancelled invocation.

Replay cancellation проверяет доступное immutable binding: world/kind/preparation и existing publication fingerprint, если он уже установлен. Если отмена раньше claim и publication fingerprint отсутствует, caller получает cancellation **preparation operation**, а не утверждение, что конкретный request fingerprint применялся. Никакой request fingerprint не дописывается в cancelled ledger для replay. Другой preparation binding отклоняется. Это уточнение public error contract требует принятия до реализации; operation terminal roster не расширяется.

## 5. Gate R3: типизация immutable mismatch и core refusal diagnostics

Existing operation store сообщает immutable mismatch через ValueError. Public method не должен классифицировать его по тексту или ловить все ValueError как mismatch: тот же тип может означать повреждённый invariant. До реализации нужно выделить owning typed mismatch carrier со checked operation/request facts либо checked result branch и отдельно определить concrete core FieldPathError codes для accepted REJECTED outcome. Existing generic FieldPathError не инстанцируется; raw строка не typed reason.

Конкретные diagnostics для registry/version, gameplay/timeline/turn, world/player CAS также должны быть сверены с already accepted error contracts before additions. Этот S3 trace не объявляет голые NamedTuple CAS traces готовыми public diagnostics. Scoped D1 metadata остаётся без изменений. При missing persisted parent corruption остаётся infrastructure, не бизнес missing-base refusal.

## 6. Read methods и пределы первого среза

Read_snapshot/read_publication из public-methods-contract.md не зависят от R1–R3: их proposal Input/Output/Error и existing read_scope mechanism можно принимать/реализовывать отдельным разрешённым срезом. Public apply signature accepted freeze сохраняется, но законченный implementation plan обязан закрыть R1–R3 и recovery limitations прежде чем обещать end-to-end readiness.

Внешние Source/Pack/Cache public операции не запускаются из apply. Генераторы/другие домены v1 не перепроектируются и не адаптируются. Не надо менять их producers для документальной проверки этих общих gates. Новые internal receipt/error changes сначала предъявляются пользователю, затем freeze/implementation.

## 7. Evidence и следующий шаг

Прочитаны IOperationStore и SqliteOperationStore claim/record_terminal/record_refusal, OperationRecord/OperationClaim, WorldSnapshotService и builder, owning 4D2 evidence. Выявленные gaps — статический анализ, не новые воспроизведённые runtime баги. Тесты не запускались, код не менялся. git diff --check — документационная проверка.

S3 trace подготовлен; приёмка public apply implementation **не закрыта**. Следующий контрактный результат Snapshot: R1 explicit destination+inherited retention contract и R2 control carrier на пользовательскую приёмку; R3 scoped diagnostics freeze. Не обходить эти изменения с помощью legacy adapters и не переносить их в DAG payload assembly.
