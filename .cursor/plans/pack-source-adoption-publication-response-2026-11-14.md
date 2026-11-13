# Pack Source closure — ответ Artifacts/publication

2026-11-14. DESIGN OPEN. Статическая проверка текущих staging/lease/holder/commit adapters и принятых Source §12.1, pack-source-exchange-contract.md §3, source-pack-exchange-response-2026-11-13.md. Код и Source/Pack документы не изменены.

## Доступный контракт и пробел

Принятый SourceCaptureRetentionBinding.adopt(scope, request, sources, target) вычисляет полный closure в borrowed write scope, проверяет exact source pairs и приобретает target holds. Он сам выполняет один SqliteArtifactScope.bind(scope), получает unbound helper и не освобождает source holds.

SqlitePublicationCommitStore.transaction(operation_id) выдаёт task/database/lifetime-bound write scope. SqliteArtifactLeases.finish_preparation(lease, refs) проверяет writable lease, отсутствие writers, точное равенство refs всем operation holds, seals, затем закрывает admission и пишет READY. ArtifactStagingService делегирует этому методу.

По просмотренным контрактам готового принятого внешнего entry, объединяющего все proofs конечного Pack state, adoption и READY, нет. finish_preparation не доказывает Source completeness. Ниже конкретное предложение инфраструктурного entry для согласования.

## Рекомендуемая boundary

Владелец — publication infrastructure. Новый internal порт backend/app/application/publication/contracts/packPreparationRetention.py::IPackPreparationRetention. Реализация backend/app/application/publication/service/packPreparationRetention.py::PackPreparationRetention. Этот класс координирует transaction и принятые internal bindings. Public Source pipeline в зависимостях отсутствует.

Предлагаемый вызов:

```python
async def adopt_and_finish(
    self, request: PackPreparationRetentionInput,
) -> OperationRecord | SourceFailure: ...
```

Предлагаемые frozen strict records в backend/app/application/publication/contracts/packPreparationRetention.py:

- SourceClosureAdoption(request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef, ...]).
- PackPreparationRetentionInput(lease: OperationLeaseRef, preparation_fingerprint: RevisionHex, closures: tuple[SourceClosureAdoption, ...], operation_members: tuple[ArtifactRef, ...]).

Input internal, содержит capability lease. Output OperationRecord подтверждает READY только после commit; SourceFailure сохраняет ADOPT_CLOSURE и исходные diagnostics. Другие lifecycle phases обрабатываются как typed refusals/recovery, не возвращаются как успешный READY.

Target всегда вычисляется как OperationHolder(lease=request.lease), caller не передаёт произвольный target. Предлагаемый kind первой поставки PACK_ACTIVATION должен быть отдельно подтверждён владельцем Pack prepare lifecycle: без этой приёмки конкретное kind ограничение остаётся OPEN. Не заводить другой operation id только ради Source adoption.

## Полномочия input и nested calls

Полнота closures принадлежит Pack. До вызова entry Pack-owned internal preparation binding проверяет точное покрытие proofs конечного immutable preparation state, включая inherited payload/metadata, и соответствие preparation fingerprint. Entry сам не обходит Pack state и не выбирает proofs. Concrete caller и механизм trusted execution binding из pack-source-dag-execution-binding.md пока требуют приёмки; этот документ не разрешает новый public Pack→Source вызов.

sources приходят из owning preparation/execution binding как exact пары ref+holder, по одной на каждый computed ref каждого proof. Это заявления, которые Source adopt проверяет заново. Ref одинаковый в двух proofs допускает повтор между closure requests, но дубли внутри sources одного proof запрещены. Произвольный выбор любого найденного holder по is_held не доказывает права использования.

Для v1 предлагается разрешать source holders из явно предъявленного owned capture/retention context данного prepare и текущего target operation. Проверка доступности holder, world и lifecycle выполняется принятыми Source/Artifacts bindings. Конкретный источник source-holder authority в Pack execution contract остаётся OPEN. VerifiedArtifactRef сам по себе не capability, и successful READ SourceProofResult не выдаёт live hold.

operation_members — полный ожидаемый набор этой operation: Pack artifacts, inherited adopted artifacts и union всех computed Source durable_refs. Его вычисляет owning preparation binding. Общие refs дедуплицируются по полному ArtifactRef, конфликтующие descriptors отвергаются. Наличие unrelated operation holds вызывает mismatch полного набора; их нельзя молча освобождать или скрывать. Для завершения вызывающий должен предъявить согласованный полный набор.

## Единственная transaction до READY

1. Entry строго проверяет DTO, world/fingerprint, kind и точный lease/fence.
2. Открывает существующий общий writer transaction по lease.operation_id. Повторно проверяет operation PREPARING, admitted и отсутствие writers. Current binding/fingerprint проверяется внутри writer scope.
3. Для каждого closure вызывает принятый internal SourceCaptureRetentionBinding.adopt с вычисленным OperationHolder. Перед каждым вызовом artifact helper unbound; bind принадлежит Source adopt и заканчивается до следующего вызова.
4. SourceFailure даже от последнего closure переводится во внутреннее rollback exception. Все новые target holds предыдущих closures откатываются. Наружу возвращается исходный SourceFailure только после подтверждённого rollback.
5. В том же scope выполняет scoped finish_preparation по полному operation_members. Он повторно сверяет exact active operation holds, seals и drain, закрывает admission и записывает READY.
6. После подтверждённого outer COMMIT возвращает READY OperationRecord.

Нужное infrastructure изменение — явный internal scoped finish:

```python
async def finish_preparation_scoped(
    self, scope: CommitScope, lease: OperationLeaseRef,
    refs: tuple[ArtifactRef, ...],
) -> OperationRecord: ...
```

Предлагаемое размещение — backend/app/db/repositories/sqlite/artifacts/leaseStore.py. Public finish_preparation делегирует той же проверке внутри собственного UOW. Scoped метод проверяет registry operation identity и lease, заимствует scope и не завершает transaction. Он доступен coordinator через internal port, не через public Pack API. Это явное расширение infrastructure контракта на согласование.

Альтернатива через helper.bind и нынешний finish_preparation возможна только после доказательства общего helper/registry и joined-UOW semantics. Рекомендуется явный scoped метод, чтобы transaction ownership проверялся по сигнатуре и избежать nested UOW. Source adopt остаётся единственным bind owner во время своего вызова.

## Lifetime, cancel и replay

До READY target OperationHolder защищает каждый adopted ref. В предложенном entry acquisition и READY видимы атомарно. Source holders не снимаются. При cancel existing lifecycle закрывает admission, drain-ит writers и освобождает operation holds target; другие holders сохраняются. Concurrent cancel сериализуется writer transaction: если cancel победил, entry отвергает terminal/stale phase до writes; если READY победил, дальнейший cancel применяет обычный lifecycle.

После READY держатели остаются operation-owned до последующего согласованного Pack retention/publication handoff или cancel. Этот entry не объявляет Pack artifact-retention root достаточным без доказанного удержания самого root. Финальный Pack retention mapping/lifetime — отдельная внешняя зависимость.

READY replay должен сначала сверять полный binding, current fence, exact полный набор holds и seals. Он возвращает существующий READY только при доверенном неизменном preparation identity/input binding. Отсутствие persisted доказательства соответствия final state/closures данному fingerprint делает такой replay OPEN. Нельзя считать одни operation holds доказательством предыдущего Source traversal.

Unknown COMMIT outcome не превращается в SourceFailure. Caller получает UnknownCommitOutcome и обращается к existing operation recovery через свежий coordinator. READY подтверждает атомарно закрытую подготовку только при принятом immutable input binding выше. PREPARING допускает новую adoption attempt лишь после подтверждённого отсутствия прежней transaction и повторной проверки источников; APPLYING/RECOVERY_REQUIRED сохраняют existing busy/recovery ограничения. Terminal cancel возвращается lifecycle result наружной recovery границы, а не успешным adopt_and_finish.

## Ошибки

Предлагаемый PackPreparationRetentionError в backend/app/application/publication/errors.py переносит frozen fault с code, operation_id и optional offending ArtifactRef. Enum-коды WRONG_KIND, WORLD_MISMATCH, FINGERPRINT_MISMATCH, STALE_LEASE, WRONG_PHASE, MEMBERS_MISMATCH, UNSEALED_MEMBER. Structural malformed input отвергается validation до IO. Foreign/expired/task-invalid scope — инфраструктурная ошибка issued capability, до storage writes.

Source semantic/closure отказ сохраняет SourceFailure. Live writers — OperationBusyError. Corrupt persisted chain/catalog — PublicationInfrastructureError. Unknown COMMIT/ROLLBACK — UnknownCommitOutcome с quarantine текущего coordinator. Mapping в PackPreparationFailure должен отдельно принять владелец Pack; копия SourceFailure roster не вводится.

## Ответственности и приёмка

Pack preparation binding отвечает за final-state proof coverage и immutable input fingerprint. Нарушение — omitted inherited proof, произвольная замена state между describe/read/prepare.

PackPreparationRetention владеет одним UOW, ordering adopt→finish и целевым OperationHolder. Нарушение — READY до завершения всех adopts, own source traversal или public Source pipeline call.

Source retention binding владеет closure/seals/source-pair validation и scoped acquisition. Нарушение — trusted caller refs вместо collect или release sources.

Lease store владеет admission/drain/full members/READY. Нарушение — nested COMMIT или разрешение неполного members set.

Holder store и GC сохраняют общий live-set. Нарушение — физическое удаление ref при действующем target hold.

Обязательные проверки: несколько proofs с общими refs и обязательными невыбранными bodies; stale source holder; ошибка последнего adopt; members missing/extra; active writer; concurrent cancel; rollback после последнего acquire и перед READY; lost COMMIT acknowledgement; restart/replay с тем же и другим fingerprint; второе SQLite-соединение видит все holds+READY либо исходное состояние.

Приёмка отклонена до закрытия OPEN: concrete trusted caller/полномочия sources, immutable preparation fingerprint coverage и replay evidence, Pack kind, scoped finish port, Pack error mapping, post-READY Pack holder lifetime. Новый DAG порядок этим документом не назначается. Runtime-тесты в этом контрактном проходе не запускались.
