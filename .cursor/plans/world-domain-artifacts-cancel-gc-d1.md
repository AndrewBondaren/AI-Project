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

**Уточнение пользователя: прямой переход внутреннего контракта.** Пункт 20 ТЗ Snapshot — задел на будущую совместимость изменяемых форматов мира, а не требование поддерживать прежний внутренний контракт OperationCancelled. По legacy-folder.mdc потребители и fixtures переводятся на новый контракт одним срезом. Legacy decoder, миграция старых terminal и отдельная ветка cancelled v2 не вводятся. Существующий format_version=1 сохраняется для текущего целевого terminal-контракта; это не обещание чтения исторических bytes с прежним reason.

В ARTIFACT_CORE_SCHEMA зарегистрировать новый enum причины и concrete GC DTO/enums; существующие identities OperationCancelled (20127) и GcReport (20129) сохраняются при прямом обновлении внутренних shapes. Свободные IDs новых типов проверить и согласовать с F3. ID 20137 базового FieldPathError не переопределять. Наличие аннотации SnapshotApplyResult.diagnostics: tuple[FieldPathError, ...] не доказывает необходимость регистрации самого carrier: canonical codec выбирает конкретный type(value). Эта регистрация не служит compatibility reader для cancel/GC; её общий аудит относится к Snapshot diagnostics, не к этому переходу. Canonical TLV, checksum и проверки operation_id/category сохраняются. Codec проверяет текущую модель и отклоняет неподдерживаемые/невалидные данные без fallback. Новые записи должны восстанавливаться после reopen; исторические cancelled payload не входят в контракт совместимости этого D2. Тестовые данные обновляются или создаются заново. Удаление пользовательской БД этим решением не разрешается.

После закрытия и reopen БД: OperationLedger.recover → operationStore.read → _load → codec.decode → evidence и проверка holds → OperationRecord с тем же enum reason. Recover не запускает cancel заново. Повтор cancel с тем же fence возвращает ту же запись и не добавляет release/terminal/phase rows. Lost commit acknowledgement остаётся UnknownCommitOutcome; новое соединение устанавливает факт из durable terminal, а не из локальной причины запроса.

### Logging

Сохранить существующий LEASE_RELEASED (INFO) после подтверждённого возврата cancelled record из staging. Повтор запроса может повторно логировать наблюдение существующего результата; это не exactly-once событие и не доказательство новой записи release. При отказе/неопределённости события успеха нет. Прямой lease store не начинает сам логировать сервисное событие. Нового persisted log не вводить.

## 3. GC — F05

### Контракт

В существующем `dataModel/artifacts/lifecycle/gc.py` определить frozen/strict/extra-forbid DTO:

| Тип / поле | Предложение |
|---|---|
| GcFailureCode | enum IO_ERROR, VALUE_ERROR; OSError → IO_ERROR, ValueError → VALUE_ERROR в существующей области catch. VALUE_ERROR не утверждает, что виноват кандидат: конкретная фаза хранится отдельно |
| GcFailureStage | enum VALIDATE, GUARD_ENTER, CATALOG_READ, HOLDERS_READ, DELETE, MARK_DELETED, GUARD_EXIT |
| ArtifactGcFailure.failure_id | EntityUid, runtime_uid один раз при формировании отказа; общий ключ DTO и log event |
| ArtifactGcFailure.ref | ArtifactRef — точный кандидат |
| ArtifactGcFailure.stage | GcFailureStage — реально достигнутая фаза |
| ArtifactGcFailure.code | GcFailureCode |
| ArtifactGcFailure.exception_type | StrictStr: module + qualname исходного исключения, только диагностическое значение |
| ArtifactGcFailure.message | StrictStr: str исходного исключения, не управляющий discriminator |
| ArtifactGcFailure.errno | StrictInt или None, из OSError.errno |
| ArtifactGcFailure.winerror | StrictInt или None, из OSError при наличии |
| GcReport.failed | tuple[ArtifactGcFailure, ...] |

Owner — artifacts. DTO сохраняет снимок исходного отказа, не сам Exception/traceback и не FieldPathError. Исходный exception не восстанавливается через import по exception_type. Existing deleted/retained остаются; валидация запрещает повтор ref в failed и пересечение всех трёх списков. Каждый обработанный кандидат получает один итог в возвращённом GcReport. При out-of-band исключении метод не возвращает частичный GcReport; ранее подтверждённые эффекты других кандидатов не отменяются этим фактом. Нет выдуманного rollback физического удаления: failure на MARK_DELETED допускает уже удалённый файл.

### Цепочка, caller, повтор

ArtifactStagingService.collect → ArtifactGarbageCollector.collect → validate ref → catalog.guard → read identity → holders → registry.delete → catalog.mark_deleted → deleted → GC_DELETED. Входные ошибки operation_id/типов candidates/дубликатов, проверяемые до цикла, остаются отказом вызова и не получают GC_FAILED. При OSError/ValueError в существующей области catch внутри цикла: сохранить фазу и оригинальные exception fields → append ArtifactGcFailure → emit GC_FAILED → продолжить следующие candidates → вернуть GcReport caller. Не расширять catch до BaseException/Exception; CancelledError и UnknownCommitOutcome/PublicationInfrastructureError распространяются, не попадают в failed. Фаза обозначает источник исключения, а не последнюю присвоенную переменную. Перед входом — GUARD_ENTER; операции тела получают собственные фазы; GUARD_EXIT используется только для исключения выхода. При исключении тела сохранить его фазу до unwind. Если выход guard успешно подтвердил откат, обработать исходное исключение с исходной фазой. Если выход вместо него поднял UnknownCommitOutcome/PublicationInfrastructureError, распространять это исключение с его cause chain; не возвращать ранний failure как известный итог.

Добавлять ref в deleted/retained и эмитировать GC_DELETED только после успешного выхода из guard. Текущий код добавляет ref внутри scope — D2 переносит фиксацию локального итога за границу. Это исключает одновременное попадание ref в deleted и failed при сбое выхода. Физическое удаление файла не откатывается вместе с SQLite. GC_FAILED подтверждает наблюдённый технический отказ, а не восстановление файла. Для generic guard, выбросившего OSError/ValueError при выходе, failure.stage=GUARD_EXIT; если owner обозначил исход неопределённым, действует инфраструктурная ветка выше.

В контрольном OSError от delete: failed[0] содержит точный ref, stage=DELETE, code=IO_ERROR, оригинальные type/message/errno; deleted пуст, GC_FAILED достигнут. Ошибка логгера не заменяет результат (существующий logging facade подавляет ошибку sink).

GC report сейчас не пишется в operation terminal, и D2 этого не добавляет. Durable факты — catalog/storage events после успешного mark_deleted; report — результат текущего вызова. Canonical serialization GcReport поддержать через существующий artifact manifest: новые IDs для failure/enums, текущая регистрация GcReport с обновлённым shape, round-trip проверить. Автоматическое восстановление прежнего failed report после reopen не обещать. Повтор того же operation_id/candidates — новая явная попытка GC; после снятия fault удаление завершается, GC_DELETED достигается. Повтор после успешного удаления проверяет существующую идемпотентность backend/catalog без требования нулевого повторного вызова backend: blobBackend.delete использует unlink(missing_ok=True), catalog.mark_deleted не добавляет повторный GC_DELETED storage event. Проверяются отсутствие содержимого и неизменность числа storage events; автоматический retry/scheduler не вводится.

### Logging

GC_FAILED (ERROR) принадлежит ArtifactGarbageCollector: один emit на пойманный отказ кандидата. Передать тот же ArtifactGcFailure, который включён в GcReport.failed, в расширенный ArtifactLogRecord.gc_failure: ArtifactGcFailure | None = None. Инвариант: GC_FAILED требует gc_failure, artifact_hash совпадает с gc_failure.ref.content_hash; для других activities gc_failure отсутствует. Новый failure_id создаётся один раз через runtime_uid. Caller и лог связываются по failure_id; operation_id связывает вызов с maintenance operation, ref — с кандидатом. При повторе GC новый отказ имеет новый failure_id даже при том же operation_id/ref. Это диагностическая identity, не новый persisted state и не ключ дедупликации удаления.

Расширить существующий ArtifactLifecycleLog.emit(record, *, cause: Exception | None = None). Для GC_FAILED producer передаёт исходный пойманный exception непосредственно из except; для остальных событий cause отсутствует. Facade проверяет согласованность activity/cause до отправки: GC_FAILED требует cause, остальные activities его не принимают. Ошибки построения event — ошибки контракта, не ошибки sink; они не подавляются. Facade использует существующий logger app.artifacts и `_LOGGER.log(..., exc_info=(type(cause), cause, cause.__traceback__))`. Exception и traceback живут только на границе logging, не входят в DTO/manifest/terminal. Связанный typed gc_failure, напротив, входит в ArtifactLogRecord и должен проходить его canonical round-trip через существующий ID 20136; ID события не меняется. JsonLogFormatter уже сериализует exc_info в JSON-поле exc: сохраняются traceback и цепочка причин. Не восстанавливать exception из exception_type и не выдавать новый stack в emitter за исходное место отказа.

Безопасная structured projection: failure_id, полный ArtifactRef (только его объявленные metadata fields), enum code/stage, exception_type, errno/winerror. Сырой message остаётся в caller DTO; не дублировать его в structured extra. В поле exc разрешена стандартная техническая traceback-диагностика исходного исключения: frames и exception text, без дампа locals, Exception.__dict__, args, domain payload или SQL parameters. Это не обещание автоматической очистки произвольного exception text: producer/backend не должен включать секреты или raw payload в свои exception messages. Не вводить сериализацию произвольных объектов. Existing model_dump(mode="json") подходит для metadata, но projection gc_failure должна явно исключать message. Ошибка sink не меняет возвращаемый GcReport и не запускает повтор удаления.

Маршрут по docs/tz_logging.md: app.artifacts → artifacts/artifactLifecycle, backend/logs/artifacts/artifactLifecycle.log; использовать существующие _PREFIX_ROUTES и SERVER_SINKS. В текущем коде маршрута нет. В generationLogging добавить app.artifacts в существующий allowlist: внутри активного generation_world_log запись копируется в transcript тем же emit; вне generation scope transcript не создаётся. GC world_uid остаётся None, если artifact межмировой; scope transcript не подменяет ownership artifact. request_id берётся из общего facade, фиктивные correlation IDs не создаются.

Cancel F06 не имеет ошибочного поля или stack trace ошибки: LEASE_RELEASED коррелируется по operation_id и существующему context; причина REQUESTED восстанавливается из terminal. Ошибки исполнения cancel не превращаются в успешный LEASE_RELEASED. Реальная полевая ошибка по-прежнему несёт CheckedPath/ValidatedFieldPath; переход F06/F05 не отменяет EC-02 и не добавляет синтетический path.

## 4. Точный перечень файлов D2

Все пути ниже относительно backend/. Новых production-файлов не требуется.

| Файл | Изменение |
|---|---|
| app/dataModel/artifacts/lifecycle/operation/record.py | enum reason и точная аннотация OperationCancelled |
| app/dataModel/artifacts/lifecycle/gc.py | failure DTO/enums, failed annotation, disjoint invariant |
| app/db/repositories/sqlite/artifacts/leaseStore.py | producer reason, убрать старый FPE constructor/import |
| app/application/artifacts/lifecycle/artifactGc.py | failure_id/фаза/причина, тот же failure в report и log, исходный exception в emitter |
| app/dataModel/artifacts/events.py | gc_failure и инварианты activity/hash |
| app/application/artifacts/logging/artifactLog.py | safe projection и cause → exc_info через прежний logger |
| app/core/loggingConfig.py | только app.artifacts route и SERVER_SINKS; formatter переиспользовать |
| app/core/generationLogging.py | app.artifacts в существующем transcript allowlist |
| tests/test_logging_routes.py | artifact route/server sink, JSON traceback и failure correlation |
| tests/test_generation_logging.py | один emit → domain file и transcript, изоляция generation scope |
| app/application/artifacts/encoding/coreManifest.py | новые IDs только новых enum/failure типов; обновить существующие contracts без параллельных old/new регистраций; согласовать с F3 |
| tests/snapshotCore/contracts/test_models.py | новые shape/invariants; перевести все GC_FAILED fixtures на gc_failure и cause, проверки уровней/sink failure; отказаться от target_issue для cancel/GC |
| tests/snapshotCore/contracts/test_codec.py | canonical enum/GC/ArtifactLogRecord с gc_failure round-trip, некорректные значения |
| tests/snapshotCore/storage/artifacts/test_leases.py | пять исходных cancel test methods и повтор/reopen |
| tests/snapshotCore/storage/artifacts/test_staging.py | два cancel, один GC сценарий, fake producer и caller logging |
| tests/snapshotCore/storage/publication/test_atomicity.py | текущий terminal codec round-trip, reopen и неопределённый commit |
| tests/typing/snapshotCore/valid.py | положительные concrete cancel/GC contracts |
| tests/typing/snapshotCore/invalid.py | запрет FieldPathError, чужих enum и неверного failed DTO; обновить EXPECT |

Fake cancel найден в tests/snapshotCore/storage/artifacts/test_staging.py:127; support/artifactFixtures.py не содержит producer этих DTO и не входит в diff. SQL schema и format_version остаются прежними: переход reason не требует изменения CHECK или миграции SQL.

StoredTerminalCodec уже вызывает model_validate и canonical encode/decode с manifest; новая аннотация reason проверяется через эту цепочку. Изменение terminalCodec.py не требуется только ради смены типа: файл входит в проверку round-trip, а не в обязательный production diff.

Не менять operationStore.py, operationLedger.py, artifactStaging.py, SQL migration и holderStore.py ради этого D1: их существующие переходы/логирование переиспользуются и проверяются тестами. Если D2 обнаружит необходимость их менять по иной причине — отдельное уточнение D1, не расширение по ходу. Test codec fixtures должны использовать production manifest для новых типов, а не маскировать отсутствие регистрации TEST_ISSUE_SCHEMA. Документы D2: этот файл (evidence), Snapshot owning-план (статус/ссылка), docs/tz_logging.md (статус фактически реализованного artifact route; snapshot route не объявлять реализованным заодно).

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

Дополнительно: fresh production codec round-trip нового cancelled контракта, same operation/fence повтор до и после reopen (равный terminal, неизменное количество terminal/release/phase rows), другой fence/identity не получает ложного успеха, невалидный payload отвергается без fallback, остальные текущие terminal contracts работают. GC DTO round-trip и отрицательные strict typing кейсы; GC после удачного удаления не создаёт противоречивых событий. Unknown commit проверять через fresh connection, не ловить как cancelled.

Повторить адресные leases/staging/GC/codec/models/atomicity, tests.test_logging_routes и tests.test_generation_logging, затем typing positive/negative; затем snapshotCore. База последнего прогона: 171 тест, 8 errors, 1 failure, 1 skip. Цель D2 — устранить перечисленные 8 errors и positive typing failure, без новых падений; Windows symlink skip допустим. Количество новых тестов и EXPECT указать явно; не обещать прежние 51 negative после расширения fixtures.

## 6. Фактическое пересечение с Pack F3

На момент исследования [отчёт F3](spatial-f3-implementation-report.md) фиксирует только get_store_id; production receipt/binding/holder/admission ещё не реализованы. По поиску backend/app нет executionPins.py или production worldPack adapter из карты F3 и нет Pack caller ArtifactStagingService.cancel/collect. Найденные worldData pack materializer.collect — другой контракт, не artifact GC. Это снимок текущего рабочего дерева, а не обещание состояния параллельной реализации.

Карта Spatial §15.102 требует pin holder, общий holder journal и live-set, immutable close receipt; release отложен за F3. Поэтому **функциональная зависимость F3 от исправления этих cancel/GC producers не установлена**. Общий физический файл есть: `app/application/artifacts/encoding/coreManifest.py` (F3 регистрирует holder, D2 — outcome types). Нужна координация type_id и сохранение обеих регистраций. F3 также работает с holder schema/SQL, которых этот D2 не касается. GC использует общий holders(ref): любые F3 live pin holds должны по-прежнему удерживать artifact; менять это поведение здесь нельзя. Если до D2 появится F3 caller cancel/collect, повторить поиск и оформить отдельную зависимость с конкретным call site. F4 finalized, F5 release и execution retry вне scope.

## 7. Решения пользователя перед D2

1. **Принято пользователем.** F06: reason как artifact-owned OperationCancellationReason.REQUESTED без field error и без выдуманного источника.
2. **Предложение, требует согласования итоговой формы.** F05: ArtifactGcFailure с failure_id/ref/stage и снимком исходного исключения; GC_FAILED с тем же failure и исходным traceback, реальный sink/transcript; без persisted GC terminal. Пользователь поручил включить tracing в D1, но это не разрешение D2.
3. **Уточнено пользователем:** прямой переход внутреннего контракта; без legacy decoder, миграции старых terminal и cancelled v2. Совместимость будущих форматов мира не распространяется на этот переход.
4. **D2 не разрешён.** После согласования итогового D1 отдельно разрешить реализацию по карте файлов, включая logging route/transcript; координировать manifest с F3 без недоказанной блокирующей зависимости.

**Стоп на согласовании D1.** Код, SQL, тесты и retry-поведение в этом чате не изменяются.


### Текущий статус согласования

Приняты reason REQUESTED и прямой переход внутреннего контракта. Tracing включён по поручению пользователя; окончательная GC-карта, расширенная logging-часть и критерии предъявляются в настоящем D1. Вопрос о поддержке старых terminal закрыт и не выносится повторно. Реализация D2 не начиналась. Пункт 20 ТЗ Snapshot о будущих форматах мира не менялся.

## 8. Проверка аналогичных переходов в D1

Проверены разделы codec, GC serialization, карта файлов, критерии D2 и решения пользователя. Общая политика этого среза: один текущий внутренний контракт и одновременный перевод его producers/consumers/fixtures, без параллельных веток исторических форматов.

| Переход | AS-IS → TARGET/OPEN | Решение |
|---|---|---|
| [OperationCancelled.reason](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py), producer [SqliteArtifactLeases.cancel](../../backend/app/db/repositories/sqlite/artifacts/leaseStore.py) | FieldPathError → OperationCancellationReason.REQUESTED в том же record.py | Прямой cutover producer, DTO и fake/test constructors. Не принимать оба типа через union и не преобразовывать по message. Target ещё не реализован. |
| [GcReport.failed](../../backend/app/dataModel/artifacts/lifecycle/gc.py), producer [ArtifactGarbageCollector.collect](../../backend/app/application/artifacts/lifecycle/artifactGc.py) | tuple[FieldPathError, ...] → tuple[ArtifactGcFailure, ...] в том же gc.py | Такой же прямой cutover. Без старого reader, GC report v2 и fallback. Target ещё не реализован. |
| [ARTIFACT_CORE_SCHEMA](../../backend/app/application/artifacts/encoding/coreManifest.py) | Существующие OperationCancelled/GcReport получают текущие shapes; добавляются новые enum/failure types | IDs 20127/20129 сохраняются; новые IDs нужны только новым типам. Нельзя интерпретировать эту регистрацию как сохранение исторических shapes. |
| [StoredTerminalCodec.encode/decode](../../backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py), caller [SqliteOperationStore._save/_load](../../backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py) | Тот же codec с обновлённой моделью и manifest | Не вводить отдельный codec, ветку версии или ручной converter. Проверить production round-trip и reopen нового результата; это сохранность текущего результата, а не legacy compatibility. |
| [test_models](../../backend/tests/snapshotCore/contracts/test_models.py), [test_leases](../../backend/tests/snapshotCore/storage/artifacts/test_leases.py), [test_staging](../../backend/tests/snapshotCore/storage/artifacts/test_staging.py) | target_issue в cancel/GC fixtures → соответствующие целевые значения | Обновить fixtures. Тест противоречивого terminal с active holds сохранить на новом типе: он проверяет целостность, а не исторический формат. |

Проверка 2026-11-06: rg по OperationCancelled/GcReport constructors, FieldPathError и type IDs, чтение StoredTerminalCodec и canonicalCodec. Целевые enum/DTO отсутствуют; production activation остаётся D2. Общие Snapshot diagnostics и регистрация carrier 20137 не объявлены очищенными этим исследованием. Они не должны использоваться как оправдание legacy поддержки cancel/GC. Перед закрытием D2 повторить поиск старых constructors в обозначенном scope; вне scope carrier не удалять заодно. Код и runtime-тесты при этой проверке не изменялись.


## 9. Trace и доставка причины — уточнение D1

По запросу пользователя в проект контракта добавлено устранение недоработки: одной записи operation_id/hash недостаточно для объяснения GC failure. Требования EC-09/EC-10 выполняются совместно: typed failure для caller, тот же failure_id в event, исходный traceback в существующем formatter, реальная доставка в owning sink. Проверены ArtifactLifecycleLog.emit, ArtifactLogRecord, JsonLogFormatter.format и _GENERATION_PREFIXES; это исследование, не реализованные гарантии.

Дополнительные критерии D2:

1. Вызвать delete из именованного тестового helper, выбросить OSError с errno и chained cause. Caller получает точные ref/stage/code/type/message/errno; JSON sink содержит совпадающий failure_id, operation_id и ref, а exc — исходный helper и цепочку причин. Не проверять лишь mock emit.
2. Один пойманный отказ → один owning emit. Transcript получает копию того же события без второго вызова logger. При следующей явной попытке failure_id новый. Ошибка sink не меняет failure и не вызывает повтор delete.
3. Успешный GC и cancel не получают gc_failure или exc_info. CancelledError и UnknownCommitOutcome не конвертируются в GC_FAILED. Отказ при выходе guard с неопределённым исходом не маскируется более ранним failure.
4. Проверить JSON-safe projection без locals, domain payload и SQL parameters; raw failure.message не копируется в structured extra. Стандартное exc содержит технический exception text и проверяется на тестовых данных без секретов. Не заявлять sanitization чужих произвольных exceptions.
5. Проверить server profile, правильный domain file, копирование только в активный generation scope и отсутствие фиктивного world_uid. Scope request_id — существующий facade; для caller ↔ sink обязательны failure_id/operation_id/ref, не зависимость от наличия HTTP request.

Это точечное расширение карты D2 на существующий logging путь, а не новая logging подсистема. Для этого среза реальная sink/transcript проверка включена в приёмку D2; оставлять её неопределённым последующим I0 нельзя. Реализация по-прежнему остановлена на согласовании D1.


## 10. Ревизия согласованности — 2026-11-06

Исправлены устаревшие/неоднозначные положения:

- VALUE_ERROR вместо INVALID_CANDIDATE: исключение ValueError из backend или mark_deleted не доказывает ошибочность входного кандидата. Семейство F05 и наблюдённая стадия сохраняются; семантика не угадывается по тексту.
- Разделены GUARD_ENTER/GUARD_EXIT, исходная стадия тела и ошибка unwind. Инфраструктурная неопределённость не превращается в обычный failed; ref попадает в deleted/retained только после подтверждённого выхода scope.
- Уточнён предел «один кандидат — один итог»: это инвариант возвращённого отчёта, не обещание частичного отчёта при исключении или атомарности всего batch.
- Повтор GC проверяет идемпотентный эффект, а не ноль вызовов delete. Сверены ContentAddressedBlobBackend.delete и SqliteArtifactCatalog.mark_deleted.
- Изменение ArtifactLogRecord включено в codec/fixture tests. Для всех старых GC_FAILED fixtures требуется cause и gc_failure. Event admission и ошибки sink разделены.
- Статусы решений сведены к текущему состоянию; отменённый вопрос legacy не переоткрывается. D2 остаётся отдельным разрешением.

Историческое evidence 171/8/1/1 относится к предыдущему полному прогону; это не результат проверки текущего параллельно меняющегося checkout. Перед D2 сверить базу, перед приёмкой повторить указанные наборы. По повторному чтению spatial-f3-implementation-report.md и поиску executionPins production F3 по-прежнему не найден на момент этой ревизии; перед кодом повторить проверку общего manifest.

### Композиция карты файлов

Новых production/test файлов D2 не добавляет. Текущие → планируемые количества непосредственных файлов: dataModel/artifacts/lifecycle/operation 4→4; dataModel/artifacts/lifecycle 4→4; dataModel/artifacts 3→3; application/artifacts/lifecycle 2→2; application/artifacts/logging 2→2; application/artifacts/encoding 2→2; db/repositories/sqlite/artifacts 5→5; core 13→13; tests 280→280; tests/snapshotCore/contracts 5→5; tests/snapshotCore/storage/artifacts 5→5; tests/snapshotCore/storage/publication 4→4; tests/typing/snapshotCore 4→4. Каталог документов .cursor/plans 228→228 в этой ревизии. По folder-composition.mdc WARN для переполненных каталогов сообщён в чат; дополнительных файлов туда не планируется, реорганизация вне scope. Пути существующих модулей и импортов сохраняются; новые зависимости только events → lifecycle.gc и emitter → concrete DTO, без обратного импорта gc → events.

Проверка выполнена чтением D1 и production definitions, поиском consumers/fixtures и git diff --check документов. Runtime-тесты не запускались, код не менялся. Эта ревизия не является приёмкой реализации или общего Snapshot diagnostics scope.
