# Snapshot / Time: зависимость данных, не граф

2026-11-16. Уточнение пользователя: «Это не граф, просто скорее зависимость которую нужно помнить. Реальные ноды будут иначе спроектированы».

Для будущего проектирования DAG учитывать:

- Time BindInitialTime требует timeline_id для подготовки initial clock.
- Snapshot start требует подготовленный clock. Publication identity нужна атомарной записи, а не pure подготовке Time.
- Snapshot закрепляет контракт стабильной timeline identity, связанной с operation_id: повтор возвращает тот же ID; выдача identity сама по себе не активирует timeline. Актуальные статусы и требования START-ID/START-ERRORS-B приведены ниже; весь start API этим не объявляется готовым.

Это только зависимости входных данных. Запись «Snapshot identity → Time preparation → Snapshot start» не задаёт граф, состав или имена нод, их родство, гранулярность, отдельные CALL либо утверждённый порядок публичных вызовов. Не переносить её механически в node contracts/continuation/registration. Реальные ноды будут спроектированы отдельно вместе с пользователем; legacy-ноды для этого не используются.

Snapshot отвечает за свои публичные контракты и эффекты, Time — за семантику clock, DAG — за будущую согласованную оркестрацию. Прямой вызов публичного Time API из Snapshot не следует из этой зависимости.

Источник доменного обсуждения: world-domain-patches-snapshots.md, ARCH-0.1 / ARCH-START-POJO. Atomic storage binding и календарный anchor остаются на согласовании владельцев. Данный документ не изменяет Snapshot-план, не утверждает новые POJO и не разрешает реализацию.

## Snapshot contract requirements — переданы владельцем 2026-11-16

Источник: [owning Snapshot-план](world-domain-patches-snapshots.md), START-ID / START-ERRORS-B. Здесь фиксируются обязательства публичных контрактов, не ноды или последовательность CALL. Принятые у Snapshot identity/storage/error решения не означают реализацию runtime; старые success-only signatures ниже в owning-плане читать с приоритетом accepted START-ERRORS-B.

### IGameplayStartPreparation.prepare_timeline_identity

Планируемый публичный порт: `backend/app/application/publication/contracts/gameplayStartPreparationPort.py`. Контракт: `prepare_timeline_identity(request: GameplayStartPreparationInput) -> GameplayStartPreparationResult`. Нормативные semantics — [Snapshot START-ID / START-ERRORS-B](world-domain-patches-snapshots.md). Статус: дизайн identity/storage принят владельцем, метод planned, не runtime-ready. Result union из START-ERRORS-B заменяет историческую success-only подпись.

Public error path — proposed SnapshotPublicError/SnapshotPublicFault, operation=PREPARE_GAMEPLAY_START_IDENTITY; kinds INVALID_INPUT / INFRASTRUCTURE_FAILURE / OUTCOME_UNKNOWN. Cancellation отдельно. Эта транспортная часть не объявляется принятой вместе с identity/storage; ошибки не подменяют owning preparation refusal.

prepare_timeline_identity(GameplayStartPreparationInput(operation_id, world_uid)) → GameplayStartPreparationResult: GameplayStartIdentity(operation_id, world_uid, timeline_id) либо GameplayStartPreparationRefused(request, reason). Reason — owning union SnapshotWorldMissing | PreparationBindingConflict | PreparationIdentityUnavailable, без копирования ошибок в DAG.

Snapshot сохраняет стабильную identity; повтор совместимой операции возвращает тот же timeline_id. Единственный эффект подготовки — durable operation/identity binding. Она не создаёт активную timeline, не меняет publication/gameplay_started и не записывает clock. Storage-дизайн принят у Snapshot, runtime ещё не реализован.

### IGameplayStart.start

Планируемый публичный порт: `backend/app/application/publication/contracts/gameplayStartPort.py`. Контракт: `start(request: GameplayStartInput) -> GameplayStartResult`. Input: identity / expected_publication / initial_clock и proposed initial_settings: PreparedInitialSettings. Источник: [Snapshot START-ID / START-ERRORS-B и календарное дополнение](world-domain-patches-snapshots.md). Статус: planned; календарная приёмка и atomic World/Time binding OPEN, полной готовности реализации нет.

Public error path — proposed SnapshotPublicError/SnapshotPublicFault, operation=START_GAMEPLAY; kinds INVALID_INPUT / BUSY / INFRASTRUCTURE_FAILURE / OUTCOME_UNKNOWN. Cancellation отдельно от result union. Сохранённые отказ/успех не заменяются public transport fault. Требования первого старта и повторов ниже относятся именно к этому методу.

GameplayStartIdentity требуется первому gameplay start и повтору этой операции, а не каждому действию идущей игры. Exact same operation/request после успешного commit возвращает сохранённый GameplayStarted без второй timeline/publication. Изменение полного запроса под прежним operation_id даёт binding conflict без изменения исходного terminal.

Повторное начало другой операцией: stale expected publication → StartPublicationChanged; актуальная expected publication с gameplay_started=True → StartAlreadyStarted. Сохранённый результат своего exact запроса проверяется раньше повторной бизнес-проверки already-started. Это внутренние обязательства Snapshot operation/replay, не назначенный DAG порядок вызовов.

GameplayStartResult = GameplayStarted | GameplayStartNotAdmitted | GameplayStartRefused. NotAdmitted не пишет terminal; Refused владельцу claim сохраняется только после confirmed rollback. Busy и unknown — отдельные исходы, не автоматическая команда retry. DAG не перекодирует их в успешный start или SnapshotApplyResult и не теряет исходную identity/диагностику.

### IWorldSnapshotApply.apply

Existing публичный порт: [applyPort.py](../../backend/app/application/worldSnapshot/contracts/applyPort.py). Exact existing declaration: `async def apply[S: DomainSection](self, patch_set: PatchSet[S]) -> SnapshotApplyResult`. Вход содержит native timeline_id, expected_world и expected_players; GameplayStartIdentity не входит. Result — owning SnapshotApplyResult, без start outcome variants. Error mapping: [snapshot-public-methods-contract.md §3](snapshot-public-methods-contract.md#3-error-contract-existing-baseline-и-точное-предложение) и accepted apply semantics, включая отдельную cancellation boundary. Статус: порт существует; это не подтверждение готовности concrete public lifecycle, его implementation gates сохраняются.

IWorldSnapshotApply.apply(PatchSet) принимает native PatchSet с timeline_id и expected publication. GameplayStartIdentity в этот контракт не входит. WorldPublicationRef.active_timeline_id адресует активную timeline, но не разрешает implicit latest вместо expected CAS. Наличие start не означает необходимость prepare_timeline_identity/start перед каждым runtime apply.

### Session resume вне этого контракта

Возобновление сессии не входит в Snapshot gameplay-start контракт. Snapshot не определяет его оркестрацию и контракт другого владельца. Нельзя считать наличие start реализацией session resume либо использовать start как его неявный заменитель.

Публичного Snapshot resume/continue метода из этого сценария не вводится: такого согласованного метода нет. Для planned prepare_timeline_identity/start точные async declarations/type parameters при реализации брать из owning ports/freeze; приведённая карта не назначает HTTP endpoint или ноду.

### Граница готовности

Полный GameplayStartInput пока proposed: identity, expected_publication, initial_clock, initial_settings: PreparedInitialSettings. Reuse owning PreparedInitialSettings; новые calendar DTO не вводятся. Календарная приёмка и внутренний atomic World/Time binding ещё не завершены; весь start API не implementation-ready.

Публичные Source/World/Time операции — только через DAG, без прямого вызова из Snapshot. Требования не назначают ноды, родство, гранулярность и маршрут. Их определение остаётся отдельной работой с пользователем. Четыре ранее согласованные Snapshot-ноды этим сообщением не расширяются и не перепроектируются. Код не меняется.
