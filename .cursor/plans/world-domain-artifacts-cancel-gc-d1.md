# Scoped D1 — Artifacts cancel F06 и GC failure F05

2026-11-06. **Архитектурная основа и направление D1 приняты пользователем; новая общая инфраструктура отклонена. D2 не начат.** Owner: Snapshot / artifact lifecycle. Основание: [трейс](world-domain-snapshot-rollback-trace.md#владелец-и-граница-следующего-исправления), [ERROR-CONTRACTS](error-contracts-1.md) A0-F5 и классификация F05/F06. Исследованы текущий код, traceback 171 теста и история Git; новых runtime-прогонов в D1 нет.

## Граница изменений и порядок D2

| Проблема / существующий механизм | Решение |
|---|---|
| Разные домены вручную реализуют правила доставки | Унифицировать применение принятой политики постепенно в owning-срезах, через существующие reporting/logging механизмы. Не вводить новый общий механизм доставки. |
| Дублируется сборка диагностических событий | Убирать повторяемую сборку через доменные адаптеры ошибок и диагностики; сначала расширять существующие. |
| ArtifactLifecycleLog требует ручной сборки ArtifactLogRecord | Добавить семантические методы; service вызывает create_gc_failure и emit_gc_failure, а event/activity/severity собирает существующий адаптер. |
| Общий ResolveContext и накопление | Переиспользовать без параллельного context/report/collector. |
| Доменные POJO и типизированные ошибки | Сохранять; расширять по доказанной необходимости конкретного домена. В Artifacts меняются только согласованные reason/failed/event contracts. |
| Новый универсальный error/logging framework | Не создавать. |
| Перенос решений об исходе операции в адаптер | Не выполнять: решения о допустимости значения, fallback, отказе, продолжении, commit/rollback принадлежат доменному сервису/валидатору и transaction owner. Адаптер применяет объявленную политику формирования/доставки, не выбирает её. |

Унификация не означает одинаковую форму всех доменных причин или обязательный адаптер для каждой ошибки. В POJO/import цепочках report_issues/report_continuation уже выполняют доставку с учётом контекста; их не обходят новым emit. В Artifacts GC применяется объявленная семантика collect без навязывания ResolveContext.

После отдельной команды на D2 следовать атомарным шагам §14. Один шаг — одна проверяемая контрактная группа, краткий отчёт и ожидание подтверждения по code-gates.mdc. Связанные producer/consumer/fixtures переводятся внутри своей группы одновременно. Общий framework и массовая миграция не входят в шаги.

## 1. Причина и reuse

Старые конструкторы cancel (`9557f0e8a`) и GC (`ab835faf5`) предшествуют `9b1f845d`: общий FieldPathError стал generic carrier с обязательным code и проверенным path. Сообщение этого коммита прямо откладывает миграцию доменных consumers. Семь cancel ERROR возникают до транзакции; GC ERROR — внутри обработки OSError; positive typing FAIL указывает на тот же GC constructor.

Reuse сохраняется для OperationCancelled, OperationRecord, GcReport, ArtifactRef, OperationPhase, ArtifactLogRecord, ArtifactLogActivity, существующих ledger/store/codec и инфраструктурных исключений. Новый универсальный Error, второй ledger или codec не нужны.

Проверены `dataModel/engine/dag/diagnostics.py`: CancellationReason / CancellationRequest описывают DAG request с source, deadline и node/parent context. Их импорт в artifact lifecycle создаёт зависимость от чужого owner и обещает причины, которых текущий вызов cancel не получает. Не переиспользуем. FieldPathError и тестовый target_issue не подходят по природе события. PublicationInfrastructureError / UnknownCommitOutcome остаются транспортом инфраструктурного отказа, не становятся причиной успешной отмены. В dataModel/artifacts подходящего concrete cancel reason или GC failure сейчас нет.

## 2. Cancel — F06

### Контракт

В существующем `dataModel/artifacts/lifecycle/operation/record.py` добавить `OperationCancellationReason(StrEnum)` с единственным членом `REQUESTED = "requested"`. Поле `OperationCancelled.reason: OperationCancellationReason`; operation_id остаётся EntityUid. Это конкретный enum, не field issue. Без message, path, времени, источника user и исключения: текущий вызов cancel сообщает лишь явный запрос caller. Не выводить USER или deadline из факта вызова. Другие причины требуют отдельного подтверждённого producer.

Owner причины — artifact lifecycle. Runtime producer — SqliteArtifactLeases.cancel. Сигнатура cancel(operation_id, fence) сохраняется. asyncio.CancelledError не превращается в OperationCancelled: отмена coroutine и durable отмена операции — разные факты.

### Цепочка и транзакции

ArtifactStagingService.cancel → OperationLedger.cancel (валидация identity/fence) → SqliteArtifactLeases.cancel → первая локальная транзакция: read/fence/existing terminal/evidence/close admission → drain writers → вторая локальная транзакция: повтор read/fence/terminal, проверка writers, release точных operation holds → operationStore.record_terminal → _save → codec.encode + publication_outcomes и terminal phase event → commit → OperationRecord → ledger → staging → caller.

Причину создавать после входной валидации; повтор с тем же fence возвращает уже сохранённый terminal, а не перезаписывает его. Stale fence остаётся отказом даже при terminal. Существующий иной terminal возвращается по текущему контракту без подмены на cancelled. _load проверяет отсутствие active holds при cancelled как при первом, так и при втором чтении. Отказ terminal write откатывает release и terminal вместе; ранее закрытый admission остаётся закрытым. Не присоединяться к ambient transaction и не откатывать чужие изменения.

### Codec, запись, reopen

Термин «OperationTerminalCodec» из задания обозначает существующий `StoredTerminalCodec` в `db/repositories/sqlite/snapshotCore/operations/terminalCodec.py`. Нового класса и переименования нет.

**Уточнение пользователя: прямой переход внутреннего контракта.** Пункт 20 ТЗ Snapshot — задел на будущую совместимость изменяемых форматов мира, а не требование поддерживать прежний внутренний контракт OperationCancelled. По legacy-folder.mdc потребители и fixtures переводятся на новый контракт одним срезом. Legacy decoder, миграция старых terminal и отдельная ветка cancelled v2 не вводятся. Существующий format_version=1 сохраняется для текущего целевого terminal-контракта; это не обещание чтения исторических bytes с прежним reason.

В ARTIFACT_CORE_SCHEMA зарегистрировать новый enum причины и concrete GC DTO/enums; существующие identities OperationCancelled (20127) и GcReport (20129) сохраняются при прямом обновлении внутренних shapes. Новые IDs зафиксированы в §14; перед кодом повторить collision check с изменениями F3, без автоматического переназначения. ID 20137 базового FieldPathError не переопределять. Наличие аннотации SnapshotApplyResult.diagnostics: tuple[FieldPathError, ...] не доказывает необходимость регистрации самого carrier: canonical codec выбирает конкретный type(value). Эта регистрация не служит compatibility reader для cancel/GC; её общий аудит относится к Snapshot diagnostics, не к этому переходу. Canonical TLV, checksum и проверки operation_id/category сохраняются. Codec проверяет текущую модель и отклоняет неподдерживаемые/невалидные данные без fallback. Новые записи должны восстанавливаться после reopen; исторические cancelled payload не входят в контракт совместимости этого D2. Тестовые данные обновляются или создаются заново. Удаление пользовательской БД этим решением не разрешается.

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

По терминологии ТЗ logging producer уровня/структуры события — доменный emitter ArtifactLifecycleLog: он фиксирует GC_FAILED → ERROR. ArtifactGarbageCollector владеет обнаружением исхода и моментом вызова; LogLevel вручную не выбирает. GC_FAILED (ERROR) принадлежит ArtifactGarbageCollector как владельцу момента эмиссии: один явный emit_gc_failure на пойманный отказ кандидата после create_gc_failure и добавления результата в report (§11). Передать тот же ArtifactGcFailure, который включён в GcReport.failed, в расширенный ArtifactLogRecord.gc_failure: ArtifactGcFailure | None = None. Инвариант: GC_FAILED требует gc_failure, artifact_hash совпадает с gc_failure.ref.content_hash; для других activities gc_failure отсутствует. Новый failure_id создаётся один раз через runtime_uid. Caller и лог связываются по failure_id; operation_id связывает вызов с maintenance operation, ref — с кандидатом. При повторе GC новый отказ имеет новый failure_id даже при том же operation_id/ref. Это диагностическая identity, не новый persisted state и не ключ дедупликации удаления.

Расширить существующий ArtifactLifecycleLog.emit(record, *, cause: Exception | None = None) как механизм отправки. Producer вызывает семантический emit_gc_failure; тот сам собирает ArtifactLogRecord и вызывает emit. Producer не собирает event вручную. Для GC_FAILED producer передаёт исходный пойманный exception непосредственно из except; для остальных событий cause отсутствует. Facade проверяет согласованность activity/cause до отправки: GC_FAILED требует cause, остальные activities его не принимают. Ошибки построения event — ошибки контракта, не ошибки sink; они не подавляются. Facade использует существующий logger app.artifacts и `_LOGGER.log(..., exc_info=(type(cause), cause, cause.__traceback__))`. Exception и traceback живут только на границе logging, не входят в DTO/manifest/terminal. Связанный typed gc_failure, напротив, входит в ArtifactLogRecord и должен проходить его canonical round-trip через существующий ID 20136; ID события не меняется. JsonLogFormatter уже сериализует exc_info в JSON-поле exc: сохраняются traceback и цепочка причин. Не восстанавливать exception из exception_type и не выдавать новый stack в emitter за исходное место отказа.

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
| app/application/artifacts/lifecycle/artifactGc.py | объявленные catch/фазы, create_gc_failure → report → явный emit_gc_failure; фиксация результата после guard |
| app/dataModel/artifacts/events.py | gc_failure и инварианты activity/hash |
| app/application/artifacts/logging/artifactLog.py | pure create_gc_failure и явный emit_gc_failure поверх существующего emit; contract validation отдельно от sink failure; safe projection/cause → exc_info |
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

Не менять operationStore.py, operationLedger.py, artifactStaging.py, SQL migration и holderStore.py ради этого D1: их существующие переходы/логирование переиспользуются и проверяются тестами. Если D2 обнаружит необходимость их менять по иной причине — отдельное уточнение D1, не расширение по ходу. Test codec fixtures должны использовать production manifest для новых типов, а не маскировать отсутствие регистрации TEST_ISSUE_SCHEMA. Документы D2: этот файл (evidence), Snapshot owning-план (статус/ссылка), docs/tz_world_snapshot.md (синхронизация целевых contracts до моделей), docs/tz_logging.md (статус фактически реализованного artifact route; snapshot route не объявлять реализованным заодно).

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

## 7. Принятые решения и граница реализации

1. **Принято пользователем.** F06: reason как artifact-owned OperationCancellationReason.REQUESTED без field error и без выдуманного источника.
2. **Направление D1 принято пользователем.** F05: ArtifactGcFailure с failure_id/ref/stage и снимком исходного исключения; GC_FAILED с тем же failure и исходным traceback, реальный sink/transcript; без persisted GC terminal. Tracing входит в принятое направление; реализация D2 отдельно не запускалась.
3. **Уточнено пользователем:** прямой переход внутреннего контракта; без legacy decoder, миграции старых terminal и cancelled v2. Совместимость будущих форматов мира не распространяется на этот переход.
4. **D2 не разрешён.** Архитектурное направление принято; реализация начинается по отдельной команде по карте файлов, включая logging route/transcript; координировать manifest с F3 без недоказанной блокирующей зависимости.

**Архитектурное направление D1 принято; D2 не начат.** Текущая работа ограничена документами; код, SQL, тесты и retry-поведение не изменяются.


### Текущий статус согласования

Пользователь принял существующую архитектурную основу и предложенное направление D1, включая раздельные create/emit и reuse ResolveContext/ResolveReport/collect_only с blocking issues / continuations. Создание новой общей инфраструктуры отклонено. Унификация доменных адаптеров выполняется постепенно при работе с конкретными доменами, без массовой миграции или общего предварительного инфраструктурного этапа. Ранее принятые reason REQUESTED и прямой переход внутреннего контракта сохраняются. Реализация D2 не начиналась; принятие архитектуры не является командой писать код.

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

### Разделение D2 и EC-I0

D2 реализует конкретные DTO/producers, методы существующего адаптера и нужные регистрации logging. Проверки настоящего artifact sink, formatter, failure correlation и transcript из этого раздела выполняются в том же рабочем срезе, но фиксируются в отчёте отдельно как **локальный EC-I0 artifact logging**, включённый в приёмку D2. Это не отмена этапа I0 и не перенос его критериев в unit tests.

Приёмка D2 требует evidence обоих блоков: (а) typed contracts/runtime/typing; (б) локальный EC-I0 с существующим router и реальным временным файлом/transcript, без mock emit. В графе зависимостей отражено то же включение. Моки допустимы для отдельных fault-injection тестов, но не доказывают доставку в sink.

Локальный EC-I0 подтверждает только artifact logging route и проверенный calling scope. Он не закрывает общий EC-I0, production composition, DAG binding или эксплуатационный gate будущего maintenance entrypoint. Для фактической эксплуатации конкретной операции дополнительно подтвердить её реальный entrypoint, назначение root-cause owner, корреляцию и отсутствие дублей на всей границе. Если такая binding ещё отсутствует, статус этой интеграции остаётся OPEN; это не скрытый prerequisite исправления producers. Новая logging подсистема не создаётся. D2 не начат.


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


### Терминология

Внутренняя доменная обвязка именуется «доменный адаптер ошибок и диагностики». Общая инфраструктура предоставляет механизмы, доменный адаптер ошибок и диагностики задаёт применение для конкретного семейства и сценария владельца. Это название ответственности, а не требование нового класса. В данном D2 расширяется существующий ArtifactLifecycleLog; новая общая инфраструктура исключена.


## 11. Принятое направление: reuse инфраструктуры и доменные адаптеры ошибок и диагностики

**Статус: архитектурная основа и направление приняты пользователем. Новая общая инфраструктура отклонена; унификация адаптеров — постепенно в конкретных доменных срезах. Это не запуск D2.** Поручение пользователя — закрепить архитектурное направление отдельно от исправления двух constructors artifacts. Владельцем общих механизмов остаётся ERROR-CONTRACTS вместе с существующей инфраструктурой logging; Artifacts D1 предъявляет конкретный сценарий применения.

### Разделение ответственности

Практическое правило унификации: домен объявляет допустимые факты, исходы и политику их доставки; существующий доменный адаптер ошибок и диагностики устраняет повторяющуюся сборку контекста, проекции и события. Он не принимает решения «продолжить/отказать», «подставить default/None», «повторить операцию» или «подтвердить commit». Для resolve-сценариев доставка выполняется существующими reporting helpers, для GC — явным emit_gc_failure; единообразие принципов не требует одинаковой реализации для разных семейств.

| Действие | Владелец в Artifacts D2 |
|---|---|
| Поймать предусмотренный отказ и определить достигнутую фазу | ArtifactGarbageCollector.collect |
| Создать один immutable failure по утверждённому отображению типов | ArtifactLifecycleLog.create_gc_failure, без logging |
| Накопить failure и решить, продолжать ли обработку | ArtifactGarbageCollector.collect |
| Собрать ArtifactLogRecord, activity, severity и projection | ArtifactLifecycleLog.emit_gc_failure |
| Проверить контракт события и передать исходный traceback | Существующий ArtifactLifecycleLog.emit |
| Доставить JSON в файл / transcript | Существующие loggingConfig и generationLogging |
| Подтвердить транзакционный исход | Существующий transaction owner, не адаптер |


1. **Общая инфраструктура** предоставляет существующие проверенные механизмы: typed field paths, admission immutable diagnostics, переиспользование существующих механизмов накопления и reporting, корреляцию и logging transport/formatter/sinks. Новый универсальный collector не вводится. Общий слой не импортирует конкретные причины Artifacts, Snapshot или DAG и не выбирает за них исход операции.
2. **Доменный адаптер ошибок и диагностики** связывает эти механизмы для конкретного владельца и семейства. Он предоставляет короткие типизированные методы, собирает повторяющийся контекст, формирует конкретные причины/события только по утверждённому контракту операции (не угадывает бизнес-смысл произвольного exception) и передаёт исходное исключение в logging там, где это предусмотрено политикой. Сначала reuse/extend существующего адаптера; новый класс или файл требует доказательства недостаточности существующего.
3. **Сервис или валидатор** сообщает факты и остаётся владельцем решения: накопить диагностику, вернуть исход, прервать выполнение, дождаться commit/rollback. Момент подтверждения durable результата не переносится в logging. Модели причин не эмитируют события при конструировании.

DAG, Snapshot и Artifacts — владельцы, а не взаимоисключающие семейства ошибок. У одного владельца могут быть F01 field validation, F02 model invariant, F03 conflict, F05 technical fault, F06 control outcome. Поэтому единого универсального «создать/залогировать/выбросить всё» механизма не предлагается. Удобство проектируется для конкретного семейства и сценария, а общие механизмы переиспользуются.

### Обязательное переиспользование ResolveContext / ResolveReport в POJO/import-цепочках

Уточнение пользователя: архитектура §11 явно переиспользует существующие принципы resolve, не создаёт параллельные mode/context/report/disposition-механизмы. Нормативная политика: [ERROR-CONTRACTS-1, EC-10/EC-11 и «Применение EC-11 к полям POJO»](error-contracts-1.md#L679). Доменный адаптер сохраняет различие между политикой исхода операции и политикой доставки диагностики. Переключение collect_only не изменяет типизированную причину, результат операции или право на запись. Проверены [ResolveContext и reporting functions](../../backend/app/application/jsonValidation/resolution/diagnostics.py), [ResolveReport](../../backend/app/application/jsonValidation/types.py) и ERROR-CONTRACTS EC-11.

- `ResolveContext` уже несёт `validate_only`, `collect_only`, `mode`, `partial`, `location` и общий request-local `report`. `child()` наследует флаги, расширяет location и разделяет тот же report. В существующих POJO/import цепочках передавать этот контекст, а не создавать новый независимый отчёт внутри доменного адаптера.
- `ResolveReport.issues` и `ctx.errors` — **blocking issues**. `ResolveReport.diagnostics` — отдельная immutable проекция зарегистрированных **continuations**: фактов, для которых producer разрешил продолжение и вернул пригодное значение. Нельзя добавлять continuation в blocking issues или вычислять отказ по наличию любого диагностического факта.
- `collect_only` управляет только доставкой: сохраняются те же значение/UID, blocking или continuation, исключение либо возврат, допуск записи. Флаг отключает диагностическую эмиссию, но не разрешает невалидный POJO, не превращает отказ в success и не включает preview. Отсутствие эмиссии не означает отсутствие факта в report.
- `validate_only` — отдельная политика проверки/preview. Запись, резервирование и выдача версии запрещаются владельцем входной операции; этого нельзя обеспечить одним отключением логирования. `ResolveMode.IMPORT` не является синонимом preview: preview/apply различаются явным validate_only.
- Существующие `report_issues` / `reject_unresolved` доставляют blocking facts; `report_continuation` регистрирует разрешённое продолжение и выполняет предусмотренную дедупликацию. `report_unreported_issues` предотвращает повторную доставку уже полученных дочерних facts. Reuse этих функций важнее буквального введения пары create/emit в каждом методе.

**Согласование с create/emit:** создание конкретной причины остаётся чистым. В resolve-цепочке после создания причина передаётся в соответствующий существующий reporting helper, который уже учитывает validate_only/collect_only и политику эмиссии. Не вызывать дополнительно emit_* для того же факта после report_issues/report_continuation — это удвоит лог. Прямой emit_* предназначен для owning boundary без такого reporting helper, например текущего GC. Не добавлять безусловный emit в доменный адаптер, обходящий collect_only.

| Кейс одного POJO resolver | Канал и реакция |
|---|---|
| Validate: нарушение | Concrete issue → report.issues; для отсутствующего валидного POJO существующий reject_unresolved/UnresolvedModelError; без runtime warning и без записи |
| Runtime: объявленный default при допустимом пропуске | Штатное значение; не создавать искусственную ошибку или continuation |
| Runtime: явно разрешённая замена после нарушения | Пригодное значение + report_continuation с исходной причиной; не добавлять в ctx.errors; при collect_only тот же результат без эмиссии |
| Runtime: допустимый None | Штатное значение; не подменять им unresolved POJO |
| Runtime: недопустимый None / другая явная ошибка POJO | Blocking issue и отказ либо отдельно разрешённое continuation по политике поля/операции; collect_only не меняет решение |
| Отказ операции вне поля | Существующий family-specific outcome/exception. Не упаковывать F05/F06 в ImportIssue ради reuse report; переносить принципы разделения факта, исхода и доставки |

Граница reuse: ResolveContext/ResolveReport — текущий владелец POJO/import resolution, не универсальный контекст DAG, Snapshot или GC. В этих подсистемах сохраняются собственные outcomes и transaction/execution semantics; новый импорт ResolveContext в GC или DAG этой архитектурой не требуется. Продолжение цикла GC после failure кандидата не является resolve continuation: удаление этого кандидата не стало успешным и остаётся в GcReport.failed. Аналогично OperationCancelled — F06, не blocking field issue и не continuation. Добавление collect_only в GC здесь не предлагается: его публичный контракт пока не имеет этого режима.

Критерии сохранения reuse: один context через child и общий report; одинаковые blocking facts/continuations/UID/исход при collect_only=False/True; различается только эмиссия; mixed-case (разрешённое continuation + независимая blocking ошибка) не теряет ни один факт и остаётся отказом из-за blocking причины; preview не пишет. Проверки должны использовать существующие resolve characterization-тесты и helpers, а не второй collector. Рефакторинг jsonValidation не входит в D2 Artifacts: конкретные изменения такого owner требуют собственной карты, если reuse выявит недостаточность существующего контракта.

### Применение по семействам при работе с доменом

| Семейство / сценарий | Ответственность доменного адаптера ошибок и диагностики | Что остаётся у caller |
|---|---|---|
| F01, проверка поля | Concrete причина с проверенным selector/path и typed arguments; возможность чистого накопления без emit | Продолжение независимых проверок, решение о возврате/отказе |
| F02, правило модели | Concrete причина с предметными аргументами, без выдуманного field path | Применение правила и итог операции |
| F03, Snapshot CAS | Сохранение expected/observed, порядка достигнутых сравнений и корреляции | Transaction owner подтверждает rollback/commit; адаптер не делает это по факту исключения |
| F05, обработанный GC fault | Один typed failure для caller и log, исходный traceback, согласованные ref/stage/failure_id | Решение продолжить batch; инфраструктурная неопределённость остаётся out-of-band |
| F05, распространяемое исключение | Причинное событие на объявленной owning boundary, без потери exception chain | raise/re-raise и управление транзакцией |
| F06, cancel/busy | Представление управляющего исхода и предусмотренного lifecycle event | Fence/drain/commit и выбор фактически подтверждённого исхода |
| DAG execution | Существующий доменный адаптер ошибок и диагностики DAG сообщает факт исполнения и связывает его с доменной причиной | Execution policy, retry/replan и lifecycle DAG; без повторной эмиссии той же domain root cause |

### Владение событием при распространении исключения

Нормативная граница EC-10: слои propagation не логируют одну причину на каждом уровне. `raise` / `raise ... from exc` сохраняют исключение и chain; запись traceback принадлежит назначенному terminal runtime/infra owner конкретного entrypoint. GC, staging, ledger и storage не становятся такими owners только потому, что исключение проходит через них.

| Ситуация | Владелец и действие |
|---|---|
| GC обработал OSError/ValueError по контракту и продолжил batch | ArtifactGarbageCollector вызывает emit_gc_failure ровно один раз с тем же failure, который вернётся caller. Root cause принадлежит GC. |
| GC получил UnknownCommitOutcome / PublicationInfrastructureError | Распространяет исключение без GcReport.failed и без GC_FAILED. Staging/ledger/storage не добавляют дублирующий root-cause emit. Transaction owner определяет неопределённость, но это не назначает его владельцем logging. |
| Исключение дошло до DAG | Существующий DAG owner фиксирует собственный execution/lifecycle outcome по объявленному binding. Это отдельный факт; он не повторяет уже эмитированную доменную причину и её payload/traceback. Если нижний слой не обработал fault, единственный root-cause owner должен быть явно назначен binding до эксплуатации. |
| Неожиданное исключение дошло до HTTP entrypoint | Если оно выходит через текущий RequestLoggingMiddleware.dispatch, существующий logger.exception сохраняет traceback, затем исключение распространяется дальше. Не добавлять аналогичный emit в каждый промежуточный сервис. |
| Фоновый/maintenance entrypoint без HTTP | Его terminal runtime/infra boundary должна назначить единственного владельца traceback. Конкретная production binding для такого caller не реализуется и не объявляется закрытой в этом Artifacts D2; отсутствие назначения блокирует EC-I0 этой production boundary, а не требует нового универсального error framework. |

Не вводить mutable «already_logged» в исключения или глобальный dedup registry. Отсутствие дублей определяется контрактом владения и проверкой сценария. Для обработанного GC failure policy закрыта здесь. Для будущего production entrypoint I0 обязан проверить ровно один root-cause emit плюс, при наличии, отдельное lifecycle-событие DAG. HTTP middleware — доказанный существующий путь, не гарантия того, что любое исключение из любого runtime обязательно попадёт в него.

### Принятое направление: два явно названных действия

Пользователь выбрал основным раздельное формирование факта и отправку события. Имена обязаны показывать побочный эффект:

```python
failure = diagnostics.create_gc_failure(
    ref=ref,
    stage=stage,
    cause=exc,
)
failed.append(failure)

# Отдельное явное действие; можно не вызывать при чистом накоплении.
diagnostics.emit_gc_failure(
    operation_id=operation_id,
    failure=failure,
    cause=exc,
)
```

`create_gc_failure` возвращает ArtifactGcFailure, назначает failure_id и снимает разрешённые технические факты; не обращается к logger/sink и не меняет состояние операции. `emit_gc_failure` принимает уже созданный failure, определяет GC_FAILED/ERROR, строит ArtifactLogRecord и использует существующую передачу события. Он не создаёт второй failure и не возвращает новый исход операции. Названия `gc_failure`/`gc_failed` заменяются на явные `create_`/`emit_`; скрытого create-and-log и переключателя log=True в этом срезе нет.

Reuse для Artifacts: расширить существующий ArtifactLifecycleLog в application/artifacts/logging/artifactLog.py этими методами (create — staticmethod без состояния, emit — метод экземпляра поверх существующего emit(record, cause=...)). `diagnostics` в примере — ссылка на этот существующий объект, не новый класс или wrapper. Production producer может сохранить имя self._log и вызывать self._log.create_gc_failure / self._log.emit_gc_failure. Чистый метод можно использовать без настройки logging. Название класса и пути не переименовываются ради терминологии.

Классификация разрешена только в рамках утверждённого контракта collect: OSError/ValueError в обозначенных фазах цикла → согласованные IO_ERROR/VALUE_ERROR. Сам адаптер не определяет бизнес-смысл произвольного исключения. Неподдерживаемый cause, невалидные enum и несовпадение code с cause — ошибка контракта; CancelledError и PublicationInfrastructureError не допускаются в эту фабрику. Исходы, caught boundary и разрешение продолжить batch определяет сервис, не классификатор исключений общего назначения.

Дополнительный адаптер не обязателен для каждой причины. Для F01 достаточно concrete DomainTypeError и существующего collector, если повторяемой сборки контекста/события/проекции нет. Создавать отдельный класс для каждого семейства или каждой ошибки запрещено без обоснования reuse/extend/new.

В emit_gc_failure обязательно проверить соответствие failure переданному cause: exception_type равен module + qualname фактического типа; code соответствует утверждённому отображению OSError/ValueError; message, errno и winerror совпадают со снимком того же cause (для ValueError технические errno/winerror — None). Проверка не создаёт новый failure_id. Несовпадение — явный ValueError контракта до logging, а не best-effort ошибка sink. Сравниваются объявленные технические факты; ref/stage задаёт домен, из исключения их не восстанавливают. Исходный exception object и traceback не хранятся в immutable DTO: равенство технических фактов не доказывает identity двух разных exception objects. Producer обязан передавать тот же пойманный cause; универсальный registry exceptions для доказательства identity не вводится.

Оба семантических метода валидируют свой контракт. В emit_gc_failure построение и проверка event выполняются до best-effort границы. Неверный тип DTO, отсутствие cause, несовпадение ref/hash и недопустимая activity не проглатываются как сбой логгера. Подавляются только исключения отправки уже валидного события через logging sink, как в существующем ArtifactLifecycleLog.emit. Ошибка sink не меняет failure, не повторяет delete и не превращает исход в успех.

### Критерии соответствия принятому направлению

- Показать конкретный код вызова для ошибки поля, накопленного GC failure, raise/re-raise технического исключения и подтверждённого cancel. Для каждого указать существующие типы/модули reuse и только необходимые изменения.
- Один причинный факт не пересобирается отдельно для caller и лога; идентичность, typed arguments и исходная причина совпадают. Проверенный путь обязателен для F01, но не синтезируется для F05/F06.
- Неприменимые поля, activity и severity не приходится повторять в каждом producer; машинные решения не принимаются по тексту сообщения.
- Чистое создание/агрегация не логируют автоматически. В resolve-цепочках эмиссия остаётся у существующих reporting helpers с учётом collect_only/validate_only; её не дублирует новый emit. Эмиссия выполняется отдельным emit_gc_failure на согласованной owning boundary; collector и вышестоящий caller не эмитируют ту же причину повторно.
- Traceback сохраняется без сериализации Exception в доменный DTO; sink failure не меняет результат, не запускает повтор эффекта и не выдаёт rollback/commit за подтверждённый.
- Нет нового общего logger/router, дубля collector, универсального outcome wrapper или зависимости shared слоя от доменных enum. Новые файлы/классы не считаются необходимыми только из-за появления термина «адаптер».
- Проверить соответствие EC-09/EC-10/EC-11 и существующим domain emitters. Предъявить обновлённую exact file map, минимальные meaningful tests и logging policy для каждого затронутого исхода.

**Принятый результат:** сохранены общие механизмы и определена ответственность доменных адаптеров; для Artifacts выбраны раздельные create/emit и карта §4. Принятие направления не означает глобальную миграцию DAG/Snapshot и не расширяет D2 без обновления его карты. Раздельные create/emit и явный нейминг выбраны пользователем; перечисленные критерии проверяются при реализации конкретного доменного среза. Код в данном чате не начинается.


### Проверки принятого create/emit

- create_gc_failure возвращает валидный immutable failure; logger и sink не вызываются, один объект можно передать collector и другим consumers.
- emit_gc_failure передаёт тот же failure_id/ref/code/stage; activity и severity выбираются адаптером, не собираются сервисом.
- Недопустимый cause, некорректный failure/event или рассогласованный контракт вызывают явный отказ до logging; отрицательные тесты не смешиваются с тестом недоступного sink.
- Отдельный отрицательный тест в tests/snapshotCore/contracts/test_models.py: создать failure из первого OSError и передать в emit_gc_failure второй OSError с отличающимся errno/message. Ожидать ValueError до вызова logger/sink, без изменения failure и без повторного delete. Параметризовать независимые расхождения exception_type (другой подкласс), code (подмена IO_ERROR/VALUE_ERROR), message, errno и winerror (для платформенной независимости — контролируемое исключение с этим атрибутом). Каждый subcase должен отличаться проверяемым фактом и не проходить за счёт другого несовпадения. Положительный контроль: исходный cause принят, тот же failure_id в event и report. Тест не утверждает различимость двух отдельных исключений с полностью одинаковыми объявленными фактами.
- Исключение sink подавлено после успешной contract validation; failure остаётся прежним, число вызовов delete не растёт.
- Чистые F01 constructors/collectors не требуют дополнительного адаптера и не получают автоматического emit.

Эти проверки входят в существующие test_models/test_staging и logging-тесты карты §4; новых файлов/классов ради двух методов не добавляется. Изменение документов не разрешает D2.


## 12. Решение пользователя — 2026-11-06

1. **Текущая архитектурная основа принята и сохраняется.** Переиспользуются ERROR-CONTRACTS, существующие resolve context/report/reporting helpers, разделение blocking issues / continuations, collect_only и действующая инфраструктура logging.
2. **Предложенное направление D1 принято.** Чистое создание типизированного факта и явная эмиссия разделены; адаптер выполняет утверждённую доменную политику, не угадывает смысл произвольных исключений. Ошибки контракта не подавляются как сбой sink.
3. **Создание новой общей инфраструктуры отклонено.** Не вводить новый общий context/report/collector, универсальный error/outcome wrapper, router/logger или обязательный базовый класс адаптеров. Слова «общая инфраструктура» в §11 обозначают reuse существующих механизмов, а не проект нового слоя. Точечные регистрации существующего logging route и методы существующего ArtifactLifecycleLog не являются новой инфраструктурой.
4. **Унификация доменных адаптеров — постепенно.** При работе с конкретным доменом сначала исследовать его existing types/emitters/helpers, затем применить принятое направление в owning scope. Нет отдельной массовой миграции DAG/Snapshot/Artifacts и требования переделать соседние домены до Artifacts D2. Для F01 существующих concrete error и collector может быть достаточно без дополнительного адаптера.

Это решение определяет итоговый архитектурный статус; разделы исследования описывают evidence, а не отдельные повторные согласования. Карта Artifacts D2 остаётся локальной: contracts/producers/fixtures и согласованные расширения существующего logging пути. Общая архитектура не переоткрывается при каждом доменном срезе; конкретные изменения за пределами карты требуют отдельного обоснования. D2 не начат, код в этом чате не менялся.


## 13. Обработка внешнего ревью 7217ad92

Ревью проверяло committed D1, где ещё был выбор двух вариантов; локальные последующие уточнения в него не входили. Сверены git show 7217ad92, текущий §11, ResolveContext/ResolveReport и граф §12.2–12.3.

| Замечание | Изменение в текущем документе |
|---|---|
| P1 validate/runtime | §11 прямо ссылается на EC-10/EC-11; определены ResolveMode, validate_only, collect_only, blocking issues и continuations. Конкретный JSON context не переносится в Artifacts. |
| P1 форма доменного вызова | Выбран раздельный create_gc_failure / emit_gc_failure в существующем ArtifactLifecycleLog. Совмещённого альтернативного варианта нет. |
| P2 owner распространяемых исключений | §11 содержит таблицу владельцев root-cause/lifecycle событий и границу будущих entrypoints; propagation без logging на каждом уровне. |
| P2 D2/I0 | §9 и граф зависимостей явно включают локальный EC-I0 artifact logging в рабочий срез/приёмку D2; общая эксплуатационная готовность не объявляется. |

Это документальная коррекция по ревью, не независимый PASS, не отчёт реализации и не начало D2. Принятые пользователем архитектурные решения сохраняются.


## 14. Freeze и атомарные шаги после ревью

### Точные контракты до кода

Owner всех следующих DTO — dataModel/artifacts. OperationCancellationReason в lifecycle/operation/record.py: StrEnum REQUESTED="requested". OperationCancelled.operation_id: EntityUid и reason: OperationCancellationReason — обязательные, без defaults; существующий frozen/strict/extra-forbid/revalidate_instances="always" сохраняется.

В lifecycle/gc.py: GcFailureCode(StrEnum): IO_ERROR="io_error", VALUE_ERROR="value_error". GcFailureStage(StrEnum): VALIDATE="validate", GUARD_ENTER="guard_enter", CATALOG_READ="catalog_read", HOLDERS_READ="holders_read", DELETE="delete", MARK_DELETED="mark_deleted", GUARD_EXIT="guard_exit". ArtifactGcFailure — frozen/strict/extra-forbid/revalidate_instances="always"; все поля из §3 обязательные, **включая nullable errno: StrictInt | None и winerror: StrictInt | None, без default=None**. failure_id/ref/stage/code/exception_type/message также без defaults. Значение None явно передаёт фабрика. Для VALUE_ERROR errno/winerror обязаны быть None. GcReport сохраняет конфигурацию; deleted/retained/failed обязательные tuples без defaults. ArtifactLogRecord сохраняет конфигурацию; только новое gc_failure: ArtifactGcFailure | None имеет default=None; для GC_FAILED валидатор требует ненулевое значение, для остальных activities — None.

Сигнатуры в существующем application/artifacts/logging/artifactLog.py:

```python
@staticmethod
def create_gc_failure(*, ref: ArtifactRef, stage: GcFailureStage,
                      cause: OSError | ValueError) -> ArtifactGcFailure: ...

def emit_gc_failure(self, *, operation_id: EntityUid,
                    failure: ArtifactGcFailure,
                    cause: OSError | ValueError) -> None: ...

def emit(self, record: ArtifactLogRecord, *,
         cause: Exception | None = None) -> None: ...
```

Runtime admission проверяет типы независимо от аннотаций. Ошибочный аргумент/DTO отклоняется до sink (TypeError для неподдерживаемого cause, ValueError для рассогласованных фактов; ошибки Pydantic валидации сохраняются как ValidationError). Неизвестные stage/code и строки вместо enum не приводятся автоматически. Stage и code независимы: разрешено полное декартово произведение объявленных GcFailureStage × GcFailureCode. Code проверяется по фактическому cause, stage — по реально достигнутой producer фазе. Дополнительной таблицы запрещённых пар нет. Эти методы не являются универсальным exception mapper.

Регистрация в ARTIFACT_CORE_SCHEMA: OperationCancellationReason — ENUM 20018; GcFailureCode — ENUM 20019; GcFailureStage — ENUM 20020; ArtifactGcFailure — RECORD 20140. Существующие 20127/20129/20136 сохраняются. На checkout cb1a945f поиск этих четырёх чисел в backend не выявил регистраций; test_codec содержит только прежний ожидаемый диапазон IDs, который обновляется вместе с manifest. Новые IDs закреплены этим документом, а не оставлены на произвольный выбор D2. Если F3 успеет занять номер, остановить конфликтующий шаг и явно скорректировать карту, не переиспользовать чужой identity.

### Точная граница catch GC

Операционный try охватывает только registry/catalog/holders/delete/mark_deleted и вход/выход guard. Создание failure, проверка event, emit_gc_failure и **успешный emit GC_DELETED находятся вне этого try**. Success event строится только после успешного выхода guard. Contract ValueError при создании/проверке события не может попасть обратно в catch операций GC и стать ArtifactGcFailure. Ошибка sink остаётся внутри best-effort участка emitter. Тест: после успешного delete/mark_deleted инъекция contract ValueError при GC_DELETED должна распространиться, без GC_FAILED и без повторного delete; peer подтверждает уже committed storage event. Для failure event аналогично: отказ admission не создаёт второй failure и не маскируется sink error.

### Шаги — цель → ТЗ → файлы → контракт → проверка → Done

Пути ниже относительно backend/, кроме явно указанных docs/. Общая карта §4 задаёт предел scope; следующие группы задают порядок и контрольные точки.

| Шаг / цель | ТЗ | Файлы | Контракт | Проверка | Done |
|---|---|---|---|---|---|
| D2-0, синхронизировать owning SoT до моделей | [Snapshot: Artifact diagnostics](../../docs/tz_world_snapshot.md#artifact-diagnostics--уточнение-контракта-2026-11-06); [logging: Artifact emitter](../../docs/tz_logging.md#artifact-emitter--уточнение-ответственности-2026-11-06) | docs/tz_world_snapshot.md, docs/tz_logging.md, `.cursor/plans/world-domain-artifacts-cancel-gc-d1.md`, `.cursor/plans/world-domain-patches-snapshots.md` | Новые reason/failed, emitter владеет severity; no legacy; §14 exact freeze | Из корня: `git diff --check -- docs/tz_world_snapshot.md docs/tz_logging.md .cursor/plans/world-domain-artifacts-cancel-gc-d1.md .cursor/plans/world-domain-patches-snapshots.md`; `rg -n -e OperationCancellationReason -e ArtifactGcFailure -e StrictStr docs/tz_world_snapshot.md`. Сверка символов/значений/ссылок с D1, diff --check | Только документы; целевые contracts согласованы, реализация не объявлена |
| D2-1, прямой переход cancel F06 | [Snapshot: Operation storage, CAS и capability ports](../../docs/tz_world_snapshot.md#operation-storage-cas-и-capability-ports); [целевой reason](../../docs/tz_world_snapshot.md#artifact-diagnostics--уточнение-контракта-2026-11-06) | app/dataModel/artifacts/lifecycle/operation/record.py; app/db/repositories/sqlite/artifacts/leaseStore.py; app/application/artifacts/encoding/coreManifest.py; tests/snapshotCore/contracts/test_models.py, test_codec.py; tests/snapshotCore/storage/artifacts/test_leases.py, test_staging.py; tests/snapshotCore/storage/publication/test_atomicity.py; tests/typing/snapshotCore/valid.py, invalid.py | Enum reason, producer, регистрация и fixtures переключаются вместе; codec reuse | Из backend: `python -m unittest -v tests.snapshotCore.storage.artifacts.test_leases tests.snapshotCore.storage.artifacts.test_staging tests.snapshotCore.storage.publication.test_atomicity tests.snapshotCore.contracts.test_models tests.snapshotCore.contracts.test_codec`; `python -m unittest -v tests.snapshotCore.contracts.test_typing`. Семь cancel scenarios, production codec round-trip/reopen/повтор, соответствующие typing cases | Cancel больше не строит FieldPathError; нет сломанного промежуточного consumer; оставшийся GC baseline отдельно указан |
| D2-2, целостный контракт GC failure и его события | [Snapshot: Artifact diagnostics](../../docs/tz_world_snapshot.md#artifact-diagnostics--уточнение-контракта-2026-11-06); [logging: Artifact emitter](../../docs/tz_logging.md#artifact-emitter--уточнение-ответственности-2026-11-06) | app/dataModel/artifacts/lifecycle/gc.py; app/dataModel/artifacts/events.py; app/application/artifacts/encoding/coreManifest.py; app/application/artifacts/logging/artifactLog.py; app/application/artifacts/lifecycle/artifactGc.py; tests/snapshotCore/contracts/test_models.py, test_codec.py; tests/snapshotCore/storage/artifacts/test_staging.py; tests/typing/snapshotCore/valid.py, invalid.py | Одна связанная группа producer→failure→report/event, create/emit и ограниченный catch; не отделять новый failed DTO от его consumer | Из backend: `python -m unittest -v tests.snapshotCore.storage.artifacts.test_staging tests.snapshotCore.storage.artifacts.test_gc tests.snapshotCore.contracts.test_models tests.snapshotCore.contracts.test_codec tests.snapshotCore.contracts.test_typing`. GC исходный сценарий, повтор, mismatched cause/failure, sink vs admission, GC_DELETED ValueError вне catch, canonical round-trip, typing | GC возвращает конкретную причину и исходный trace без fake path; unit/fault tests зелёные |
| D2-3, маршрутизация существующего artifact logger | [logging: Artifact emitter](../../docs/tz_logging.md#artifact-emitter--уточнение-ответственности-2026-11-06); [logging: Два слоя](../../docs/tz_logging.md#два-слоя) | app/core/loggingConfig.py; app/core/generationLogging.py; tests/test_logging_routes.py; tests/test_generation_logging.py; docs/tz_logging.md | Только route/server allowlist/transcript registration, без нового formatter/handler | Из backend: `python -m unittest -v tests.test_logging_routes tests.test_generation_logging`. Настоящий временный JSON sink и transcript, correlation/traceback, изоляция scope, один owning emit | Локальный EC-I0 artifact logging подтверждён отдельно; production binding readiness не заявлена |
| D2-4, итоговая регрессия и фиксация evidence | [Snapshot: Artifact diagnostics](../../docs/tz_world_snapshot.md#artifact-diagnostics--уточнение-контракта-2026-11-06); [logging: Artifact emitter](../../docs/tz_logging.md#artifact-emitter--уточнение-ответственности-2026-11-06) | `.cursor/plans/world-domain-artifacts-cancel-gc-d1.md`, `.cursor/plans/world-domain-patches-snapshots.md`; код без новых изменений | Проверка объединённого среза, не новая реализация | Из backend: `python -m unittest -v tests.snapshotCore.storage.artifacts.test_leases tests.snapshotCore.storage.artifacts.test_staging tests.snapshotCore.storage.artifacts.test_gc tests.snapshotCore.storage.publication.test_atomicity tests.snapshotCore.contracts.test_models tests.snapshotCore.contracts.test_codec tests.test_logging_routes tests.test_generation_logging tests.snapshotCore.contracts.test_typing`; `python -m unittest discover -s tests/snapshotCore -v`. Адресные leases/staging/GC/codec/models/atomicity, logging routes/transcript, typing positive/negative, snapshotCore; сравнение с историческими 171/8/1/1 и фактической базой | Краткий итог по каждому набору, локальный I0 отдельно, оставшиеся внешние defects/production gates перечислены |

Все команды unittest запускаются с cwd backend; команды D2-0 — с cwd корня проекта. В ячейках команды, разделённые точкой с запятой, перечислены для отдельных запусков, а не как shell pipeline. D2-0: diff --check без ошибок, rg подтверждает целевые определения (не заменяет чтение ТЗ). D2-1: семь cancel scenarios и новые cancel tests зелёные; GC-падение и positive typing defect в artifactGc до D2-2 могут оставаться только как точно перечисленный baseline, без новых ошибок. D2-2: адресный набор и typing gate зелёные; D2-3: оба logging-модуля зелёные; D2-4: все согласованные проверки без новых падений, baseline delta явно указан. Новые отрицательные тесты в перечисленных test_models/test_staging проверяют неизвестные значения enum, несоответствие code исходному cause и неверное указание фактически достигнутой фазы. Фазу проверяют fault-injection тесты producer: отказ в конкретной операции должен дать её stage; адаптер не восстанавливает фазу из exception. Запрещённые сочетания объявленных stage/code не вводятся. Команды выше обнаруживают эти тесты и проверки согласованности cause/failure.

Если D2-1 positive typing останавливает gate раньше negative, дополнительно из backend запустить отдельно `node ../node_modules/pyright/index.js -p tests/typing/snapshotCore/pyrightconfig.valid.json --outputjson` и `node ../node_modules/pyright/index.js -p tests/typing/snapshotCore/pyrightconfig.invalid.json --outputjson`: positive допускает только известный GC defect до D2-2, negative должен содержать все ожидаемые EXPECT с совпадающими файлом/строкой/rule (return code 1 для negative ожидаем). После D2-2 штатный TypingGateTests обязан пройти и сам проверяет точное совпадение negative EXPECT.

Каждый шаг — отдельная контрольная точка: отчёт и ожидание подтверждения согласно code-gates.mdc. D2-1 и D2-2 — отдельные согласованные контрактные группы; DTO, producer и их fixtures не разделяются на неработающие версии. Эта таблица заменяет прежний укрупнённый шаг «все DTO/producers/адаптеры сразу». D2-0 документально подготовлен настоящей правкой; кодовые шаги не начаты.

### Дополнение legacy inventory: реальные callers и cutover

| Определение / AS-IS | Callers / регистрация | TARGET и точка переключения |
|---|---|---|
| [SqliteArtifactLeases.cancel](../../backend/app/db/repositories/sqlite/artifacts/leaseStore.py) создаёт прежний reason | [ArtifactStagingService.cancel](../../backend/app/application/artifacts/staging/artifactStaging.py) → [OperationLedger.cancel](../../backend/app/application/publication/service/operationLedger.py) → lease port; concrete test composition [SqliteBlobFixture.__init__](../../backend/tests/snapshotCore/storage/artifacts/test_staging.py#L353) собирает SqliteArtifactLeases → OperationLedger → ArtifactStagingService. [live_database](../../backend/tests/snapshotCore/support/fixtures.py) предоставляет базовые SQL-компоненты, [adapters](../../backend/tests/snapshotCore/support/artifactFixtures.py) — catalog/holders; сами по себе они не собирают эту цепочку | TARGET OperationCancellationReason в [record.py](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py); D2-1 меняет constructor и все cancel fixtures; alias/reader не оставлять |
| [OperationCancelled](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py) переносится как terminal | [SqliteOperationStore.record_terminal/_save/_load](../../backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py), [StoredTerminalCodec.encode/decode](../../backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py), [ARTIFACT_CORE_SCHEMA](../../backend/app/application/artifacts/encoding/coreManifest.py) | Те же consumers читают новый reason через model/manifest в D2-1; old wire compatibility не вводится |
| [ArtifactGarbageCollector.collect/_emit](../../backend/app/application/artifacts/lifecycle/artifactGc.py) строит FPE и ручной event | [ArtifactStagingService.collect](../../backend/app/application/artifacts/staging/artifactStaging.py), [GcReport](../../backend/app/dataModel/artifacts/lifecycle/gc.py), [ArtifactLifecycleLog.emit](../../backend/app/application/artifacts/logging/artifactLog.py), [ArtifactLogRecord](../../backend/app/dataModel/artifacts/events.py) | TARGET create_gc_failure/emit_gc_failure в том же artifactLog.py; D2-2 заменяет старый producer и failed carrier; `_emit` не используется для failed, success helper переиспользуется вне catch |
| Fake cancel и старые DTO/event constructors | [test_staging.py](../../backend/tests/snapshotCore/storage/artifacts/test_staging.py), [test_leases.py](../../backend/tests/snapshotCore/storage/artifacts/test_leases.py), [test_models.py](../../backend/tests/snapshotCore/contracts/test_models.py), [test_codec.py](../../backend/tests/snapshotCore/contracts/test_codec.py) | Переводятся вместе со своим контрактом D2-1/D2-2; исторические test worlds обновляются, compatibility слой отсутствует |

Evidence на cb1a945f, 2026-11-06: определения прочитаны; область backend/app и backend/tests/snapshotCore + tests/typing/snapshotCore. Воспроизводимые команды из корня:

```powershell
rg -n 'OperationCancelled|GcReport|FieldPathError' backend/app/dataModel/artifacts backend/app/application/artifacts backend/app/db/repositories/sqlite/artifacts backend/tests/snapshotCore backend/tests/typing/snapshotCore
rg -n 'async def cancel|async def collect|_leases.cancel|_ledger.cancel|_gc.collect' backend/app/application/artifacts backend/app/application/publication backend/app/db/repositories/sqlite/artifacts
rg -n 'StoredTerminalCodec|record_terminal|_codec.encode|_codec.decode' backend/app/db/repositories/sqlite/snapshotCore backend/tests/snapshotCore
rg -n '20018|20019|20020|20140' backend .cursor/plans/spatial-f3-implementation-report.md
```

Последняя команда не нашла production registrations этих IDs. Constructor usages остаются AS-IS: target типы/методы не реализованы. Перед Done каждого шага повторить поиск в той же области и отдельно подтвердить отсутствие old constructor в его producer/fixtures. Реестр не разрешает очистку общего FieldPathError ID 20137 вне scope. Production bindings не подменять test binding: D2 не объявляет подключённым отсутствующий maintenance entrypoint.


### Дополнение по формальным замечаниям ревью

В таблице D2-0…D2-4 теперь указаны запускаемые команды, cwd/ожидаемые результаты и ссылки на конкретные разделы ТЗ. Evidence binding исправлен на SqliteBlobFixture.__init__; вспомогательные SQL/catalog fixtures не названы полной композицией. Stage/code объявлены независимыми, проверяется code/cause и фактическая фаза, а не выдуманная допустимость пар. Обоснование StrictStr и граница преобразования перенесены в owning ТЗ Snapshot. Это документальная корректировка; команды тестов здесь не запускались и D2 не объявляется выполненным.
