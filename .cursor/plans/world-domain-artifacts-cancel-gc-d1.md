# Scoped D1 — Artifacts cancel F06 и GC failure F05

2026-11-06. **Предложение для согласования; D2 не разрешён.** Owner: Snapshot / artifact lifecycle. Основание: [трейс](world-domain-snapshot-rollback-trace.md#владелец-и-граница-следующего-исправления), [ERROR-CONTRACTS](error-contracts-1.md) A0-F5 и классификация F05/F06. Исследованы текущий код, traceback 171 теста и история Git; новых runtime-прогонов в D1 нет.

## 1. Причина и reuse

Старые конструкторы cancel (`9557f0e8a`) и GC (`ab835faf5`) предшествуют `9b1f845d`: общий FieldPathError стал generic carrier с обязательным code и проверенным path. Сообщение этого коммита прямо откладывает миграцию доменных consumers. Семь cancel ERROR возникают до транзакции; GC ERROR — внутри обработки OSError; positive typing FAIL указывает на тот же GC constructor.

Reuse сохраняется для OperationCancelled, OperationRecord, GcReport, ArtifactRef, OperationPhase, ArtifactLogRecord, ArtifactLogActivity, существующих ledger/store/codec и инфраструктурных исключений. Новый универсальный Error, второй ledger или codec не нужны.

Проверены `dataModel/engine/dag/diagnostics.py`: CancellationReason / CancellationRequest описывают DAG request с source, deadline и node/parent context. Их импорт в artifact lifecycle создаёт зависимость от чужого owner и обещает причины, которых текущий cancel API не получает. Не переиспользуем. FieldPathError и тестовый target_issue не подходят по природе события. PublicationInfrastructureError / UnknownCommitOutcome остаются транспортом инфраструктурного отказа, не становятся причиной успешной отмены. В dataModel/artifacts подходящего concrete cancel reason или GC failure сейчас нет.

## 2. Cancel — F06

### Контракт

В существующем `dataModel/artifacts/lifecycle/operation/record.py` добавить `OperationCancellationReason(StrEnum)` с единственным членом `REQUESTED = "requested"`. Поле `OperationCancelled.reason: OperationCancellationReason`; operation_id остаётся EntityUid. Это конкретный enum, не field issue. Без message, path, времени, источника user и исключения: текущий API сообщает лишь явный запрос caller. Не выводить USER или deadline из факта вызова. Другие причины требуют отдельного подтверждённого producer.

Owner причины — artifact lifecycle. Runtime producer — SqliteArtifactLeases.cancel. Сигнатура cancel(operation_id, fence) сохраняется. asyncio.CancelledError не превращается в OperationCancelled: отмена coroutine и durable отмена операции — разные факты.

### Цепочка и транзакции

ArtifactStagingService.cancel → OperationLedger.cancel (валидация identity/fence) → SqliteArtifactLeases.cancel → первая локальная транзакция: read/fence/existing terminal/evidence/close admission → drain writers → вторая локальная транзакция: повтор read/fence/terminal, проверка writers, release точных operation holds → operationStore.record_terminal → _save → codec.encode + publication_outcomes и terminal phase event → commit → OperationRecord → ledger → staging → caller.

Причину создавать после входной валидации; повтор с тем же fence возвращает уже сохранённый terminal, а не перезаписывает его. Stale fence остаётся отказом даже при terminal. Существующий иной terminal возвращается по текущему контракту без подмены на cancelled. _load проверяет отсутствие active holds при cancelled как при первом, так и при втором чтении. Отказ terminal write откатывает release и terminal вместе; ранее закрытый admission остаётся закрытым. Не присоединяться к ambient transaction и не откатывать чужие изменения.

### Codec, запись, reopen

Термин «OperationTerminalCodec» из задания обозначает существующий `StoredTerminalCodec` в `db/repositories/sqlite/snapshotCore/operations/terminalCodec.py`. Нового класса и переименования нет.

Предложение wire-политики для согласования: **новый cancelled outcome пишет format_version=2**; остальные виды terminal сохраняют version=1. Зарегистрировать новый enum и новый wire type_id OperationCancelled в ARTIFACT_CORE_SCHEMA; прежний ID 20127 не переиспользовать для изменённого shape. Числовые ID выделить из свободного диапазона при D2 с проверкой коллизий, особенно с F3. ID 20137 базового FieldPathError не переопределять и не удалять в этом срезе: другие users вне scope. Canonical TLV и checksum остаются существующими.

decode выбирает допустимую версию по outcome_kind, проверяет checksum, canonical shape, enum, operation_id и category. Старый cancelled v1 отклоняется явным PublicationInfrastructureError «unsupported legacy cancelled outcome» до попытки decode изменённой модели. Это сознательное несовместимое решение, требующее согласования: **не утверждается, что старых строк нет**. Если требуется чтение старых БД, нужен отдельно согласованный legacy decoder/migration с подтверждёнными historical bytes; эвристика по тексту "cancelled" запрещена. Прочие terminal v1 должны читаться без изменений.

После закрытия и reopen БД: OperationLedger.recover → operationStore.read → _load → codec.decode → evidence и проверка holds → OperationRecord с тем же enum reason. Recover не запускает cancel заново. Повтор cancel с тем же fence возвращает ту же запись и не добавляет release/terminal/phase rows. Lost commit acknowledgement остаётся UnknownCommitOutcome; новое соединение устанавливает факт из durable terminal, а не из локальной причины запроса.

### Logging

Сохранить существующий LEASE_RELEASED (INFO) после подтверждённого возврата cancelled record из staging. Повтор запроса может повторно логировать наблюдение существующего результата; это не exactly-once событие и не доказательство новой записи release. При отказе/неопределённости события успеха нет. Прямой lease store не начинает сам логировать сервисное событие. Нового persisted log не вводить.

## 3. GC — F05

### Контракт

В существующем `dataModel/artifacts/lifecycle/gc.py` определить frozen/strict/extra-forbid DTO:

| Тип / поле | Предложение |
|---|---|
| GcFailureCode | enum IO_ERROR, INVALID_CANDIDATE; назначается по типу исключения, не тексту |
| GcFailureStage | enum VALIDATE, GUARD, CATALOG_READ, HOLDERS_READ, DELETE, MARK_DELETED |
| ArtifactGcFailure.ref | ArtifactRef — точный кандидат |
| ArtifactGcFailure.stage | GcFailureStage — реально достигнутая фаза |
| ArtifactGcFailure.code | GcFailureCode |
| ArtifactGcFailure.exception_type | StrictStr: module + qualname исходного исключения, только диагностическое значение |
| ArtifactGcFailure.message | StrictStr: str исходного исключения, не управляющий discriminator |
| ArtifactGcFailure.errno | StrictInt или None, из OSError.errno |
| ArtifactGcFailure.winerror | StrictInt или None, из OSError при наличии |
| GcReport.failed | tuple[ArtifactGcFailure, ...] |

Owner — artifacts. DTO сохраняет снимок исходного отказа, не сам Exception/traceback и не FieldPathError. Исходный exception не восстанавливается через import по exception_type. Existing deleted/retained остаются; валидация запрещает повтор ref в failed и пересечение всех трёх списков. Один кандидат даёт один итог. Нет выдуманного rollback физического удаления: failure на MARK_DELETED допускает уже удалённый файл.

### Цепочка, caller, повтор

ArtifactStagingService.collect → ArtifactGarbageCollector.collect → validate ref → catalog.guard → read identity → holders → registry.delete → catalog.mark_deleted → deleted → GC_DELETED. При OSError/ValueError в существующей области catch: сохранить фазу и оригинальные exception fields → append ArtifactGcFailure → emit GC_FAILED → продолжить следующие candidates → вернуть GcReport caller. Не расширять catch до BaseException/Exception; CancelledError и UnknownCommitOutcome/PublicationInfrastructureError распространяются, не попадают в failed. Ошибка выхода guard не должна заменяться ошибкой delete: если она делает исход неизвестным, инфраструктурное исключение имеет приоритет.

В контрольном OSError от delete: failed[0] содержит точный ref, stage=DELETE, code=IO_ERROR, оригинальные type/message/errno; deleted пуст, GC_FAILED достигнут. Ошибка логгера не заменяет результат (существующий logging facade подавляет ошибку sink).

GC report сейчас не пишется в operation terminal, и D2 этого не добавляет. Durable факты — catalog/storage events после успешного mark_deleted; report — результат текущего вызова. Canonical serialization GcReport поддержать через существующий artifact manifest: новые IDs для failure/enums и изменённого GcReport (старый 20129 не переиспользовать), round-trip проверить. Автоматическое восстановление прежнего failed report после reopen не обещать. Повтор того же operation_id/candidates — новая явная попытка GC; после снятия fault удаление завершается, GC_DELETED достигается. Повтор после успешного удаления проверяет существующую идемпотентность backend/catalog без дополнительного physical delete эффекта и без противоречивых storage events; автоматический retry/scheduler не вводится.

### Logging

Сохранить текущий GC_FAILED (ERROR) с operation_id и artifact_hash через ArtifactLogRecord; подробности отказа получает caller в failed DTO. Не менять shape ArtifactLogRecord и не добавлять второй logging API. D2 проверяет один GC_FAILED на failed candidate и отсутствие GC_DELETED для него. Нет обещания exactly-once логов между явными повторами.

## 4. Точный перечень файлов D2

Все пути ниже относительно backend/. Новых production-файлов не требуется.

| Файл | Изменение |
|---|---|
| app/dataModel/artifacts/lifecycle/operation/record.py | enum reason и точная аннотация OperationCancelled |
| app/dataModel/artifacts/lifecycle/gc.py | failure DTO/enums, failed annotation, disjoint invariant |
| app/db/repositories/sqlite/artifacts/leaseStore.py | producer reason, убрать старый FPE constructor/import |
| app/application/artifacts/lifecycle/artifactGc.py | сбор исходного failure по фазам, достижение GC_FAILED |
| app/application/artifacts/encoding/coreManifest.py | новые IDs и регистрации изменённых contracts; согласовать с F3 |
| app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py | version policy cancelled v2 / legacy rejection, остальные v1 |
| tests/snapshotCore/contracts/test_models.py | новые shape/invariants, отказаться от target_issue для этих DTO |
| tests/snapshotCore/contracts/test_codec.py | canonical enum/GC round-trip, некорректные значения |
| tests/snapshotCore/storage/artifacts/test_leases.py | пять исходных cancel test methods и повтор/reopen |
| tests/snapshotCore/storage/artifacts/test_staging.py | два cancel, один GC сценарий, fake producer и caller logging |
| tests/snapshotCore/storage/publication/test_atomicity.py | terminal codec versions, reopen и неопределённый commit |
| tests/typing/snapshotCore/valid.py | положительные concrete cancel/GC contracts |
| tests/typing/snapshotCore/invalid.py | запрет FieldPathError, чужих enum и неверного failed DTO; обновить EXPECT |

Fake cancel найден в tests/snapshotCore/storage/artifacts/test_staging.py:127; support/artifactFixtures.py не содержит producer этих DTO и не входит в diff. SQL publication_outcomes допускает format_version >= 1, поэтому предложенный v2 не требует изменения CHECK.

Не менять operationStore.py, operationLedger.py, artifactStaging.py, events.py, artifactLog.py, SQL migration и holderStore.py ради этого D1: их существующие переходы/логирование переиспользуются и проверяются тестами. Если D2 обнаружит необходимость их менять по иной причине — отдельное уточнение D1, не расширение по ходу. Test codec fixtures должны использовать production manifest для новых типов, а не маскировать отсутствие регистрации TEST_ISSUE_SCHEMA. Документы D2: этот файл (evidence) и Snapshot owning-план (статус/ссылка).

## 5. Критерии D2

| Исходный тест | Обязательное evidence после исправления |
|---|---|
| ConcreteLeaseTests.test_cancelled_terminal_requires_released_holds_on_write_and_both_cancel_reads | Запись cancelled с live holds отклонена; оба чтения cancel и recover отвергают повреждённый persisted terminal; raw holds не теряются |
| ConcreteLeaseTests.test_corrupt_held_descriptor_is_infrastructure_failure, call=cancel | PublicationInfrastructureError, не TypeError; повреждение не превращается в успешный cancel; bool fence отвергнут |
| ConcreteLeaseTests.test_implicit_caller_update_survives_rejected_cancel | Отказ ambient scope; пользовательская транзакция остаётся активной, commit виден peer |
| ConcreteLeaseTests.test_terminal_write_refusal_rolls_back_hold_release | Peer видит исходный hold, нет terminal; admission закрыт; повтор после снятия fault успешно отменяет |
| ConcreteLeaseTests.test_two_connections_cancel_while_owner_writes | Stale fence отвергнут; актуальная отмена ждёт writer; peer подтверждает terminal и отсутствие holds; повтор без дублирования journal |
| SqliteBlobLifecycleTests.test_cancel_drains_repeatedly_cancelled_placement_before_gc | Drain переживает повторную отмену writer; только после завершения доступны release и GC; типизированный terminal читается после reopen |
| SqliteBlobLifecycleTests.test_gc_serializes_physical_delete_with_reserve_and_restart | Cancel позволяет дойти до GC; guard сериализует delete/reserve; restart не теряет durable facts и не удаляет held artifact |
| ArtifactStagingTests.test_gc_io_failure_cancellation_and_uncertainty | OSError сохраняется в DTO + GC_FAILED; CancelledError и UnknownCommitOutcome распространяются; повтор без fault успешен; duplicate candidates отвергнуты |

Дополнительно: fresh production codec round-trip cancelled v2, same operation/fence повтор до и после reopen (равный terminal, неизменное количество terminal/release/phase rows), другой fence/identity не получает ложного успеха, legacy cancelled v1 даёт явный инфраструктурный исход, прочие terminal v1 работают. GC DTO round-trip и отрицательные strict typing кейсы; GC после удачного удаления не создаёт противоречивых событий. Unknown commit проверять через fresh connection, не ловить как cancelled.

Повторить адресные leases/staging/GC/codec/models/atomicity и typing positive/negative; затем snapshotCore. База последнего прогона: 171 тест, 8 errors, 1 failure, 1 skip. Цель D2 — устранить перечисленные 8 errors и positive typing failure, без новых падений; Windows symlink skip допустим. Количество новых тестов и EXPECT указать явно; не обещать прежние 51 negative после расширения fixtures.

## 6. Фактическое пересечение с Pack F3

На момент исследования [отчёт F3](spatial-f3-implementation-report.md) фиксирует только get_store_id; production receipt/binding/holder/admission ещё не реализованы. По поиску backend/app нет executionPins.py или production worldPack adapter из карты F3 и нет Pack caller ArtifactStagingService.cancel/collect. Найденные worldData pack materializer.collect — другой контракт, не artifact GC. Это снимок текущего рабочего дерева, а не обещание состояния параллельной реализации.

Карта Spatial §15.102 требует pin holder, общий holder journal и live-set, immutable close receipt; release отложен за F3. Поэтому **функциональная зависимость F3 от исправления этих cancel/GC producers не установлена**. Общий физический файл есть: `app/application/artifacts/encoding/coreManifest.py` (F3 регистрирует holder, D2 — outcome types). Нужна координация type_id и сохранение обеих регистраций. F3 также работает с holder schema/SQL, которых этот D2 не касается. GC использует общий holders(ref): любые F3 live pin holds должны по-прежнему удерживать artifact; менять это поведение здесь нельзя. Если до D2 появится F3 caller cancel/collect, повторить поиск и оформить отдельную зависимость с конкретным call site. F4 finalized, F5 release и execution retry вне scope.

## 7. Решения пользователя перед D2

1. Принять F06: reason как artifact-owned OperationCancellationReason.REQUESTED без field error и без выдуманного источника.
2. Принять F05: ArtifactGcFailure с ref, stage и снимком исходного исключения; существующий GC_FAILED, без persisted GC terminal.
3. Выбрать wire-политику: предложенные cancelled v2 / новые type IDs / явный отказ legacy v1, либо потребовать отдельную совместимую миграцию старых terminal до D2. Автоматического согласия на потерю совместимости нет.
4. Принять ограниченный D2 по карте файлов и критериям; координировать manifest с F3 без объявления недоказанной блокирующей зависимости.

**Стоп на согласовании D1.** Код, SQL, тесты и retry-поведение в этом чате не изменяются.
