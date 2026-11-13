# Source review — recovery logging contract

2026-11-14. Проверены logging-разделы source-mutation-artifacts-publication-response-2026-11-13.md, docs/tz_logging.md, existing ArtifactLogRecord и FieldPathError. Статическая проверка проекта, не runtime evidence. **NOT ACCEPTED для implementation: ниже остаются конкретные пробелы event/error контракта.** Согласие пользователя с recovery и обязательностью logging сохраняется.

## RLOG-1 — неполное представление infrastructure причины

OperationRecoveryEvent.fault_code допускает только RecoveryContractCode. Но owning проект вводит также DomainAttemptBindingError/коды INVALID_SCOPE, OPERATION_MISMATCH, WRONG_PHASE, STALE_ATTEMPT и SourceRootAcquireError/коды INVALID_ATTEMPT, ADMISSION_OPEN и другие. RECOVERY_FAILED должен сохранить причину и семейство этих ошибок, а не потерять их в общем exception text или переименовать в RecoveryContractCode. Нужен точный typed projection всех ожидаемых infrastructure failure families и правило для непредвиденного exception через existing exc_info. Не создавать зеркальный enum кодов.

Критерий: root INVALID_ATTEMPT, binding STALE_ATTEMPT и recovery STALE_OWNER дают различимые typed причины в реальном sink; original exception остаётся причиной. Unknown outcome не маскируется общим FAILED.

## RLOG-2 — Source logic diagnostics теряют предмет отказа

Пары source_codes/source_paths сохраняют field diagnostics code/path, но logic issues имеют path=None и могут отличаться только source/artifact/group_index/use_index. Два MISSING_HOLD разных refs становятся неразличимы. P2.12 требует typed пути/контекст, а не только список кодов. Нужна конкретная проекция SourceLogicIssue с допустимым exact ref/artifact identity и correlation, без message/raw body и без новой копии SourceFailure. Указать порядок field_issues затем logic_issues либо другое точно определённое отображение двух исходных tuples; исходного общего interleaved порядка в SourceFailure нет.

Критерий: несколько независимых ошибок с одинаковым code сохраняют различимый owning context, stable order и соответствие полей. Нельзя создавать SourceProofFailure либо заменять typed paths строками.

## RLOG-3 — нет единого полного roster полей и activity invariants

observed_request_fingerprint и RECOVERY_CANCELLED добавлены в последующем тексте, но отсутствуют в исходном полном поле roster/activity table. Нужна одна актуальная таблица всех обязательных полей, типов, nullability и закрытых enum wire values. В ней зафиксировать пары attempt_id/fence, required/forbidden поля каждой activity, SourceFieldCode→non-null path и SourceLogicCode→соответствующий context. RecoveryReason причины invocation и observed durable state не смешивать. request_fingerprint заявленного typed input всегда известен; неизвестным до read может быть observed fingerprint, не сам request value.

Критерий: REQUESTED не может утверждать confirmed takeover, UNKNOWN не содержит durable terminal kind, REPLAYED не означает новый commit, CANCELLED не обещает rollback без acknowledgement. Numeric fields strict: bool/строки не принимаются. Event defaults не скрывают отсутствие обязательного контекста.

## Границы и согласованное направление

Existing app.artifacts route и единый OperationRecoveryLog соответствуют направлению проекта. INFO для REQUESTED/INSPECTED и WARNING для recovery BUSY удовлетворяют требованию пользователя; это узкое уточнение logging ТЗ, не изменение existing Snapshot STARTED/BUSY. До записи amendment владелец должен предъявить окончательный event/error roster и точный текст изменения. Наличие source-owned log projection не даёт Source право дублировать publication lifecycle emit.

Причина→operation_id→attempt/fence→результат должна пройти actual emitter/router/formatter/sink при production INFO. Проверки postcommit sink failure, crash без последней строки, exact replay и второго SQLite соединения в owning проекте предусмотрены; они ещё не выполнялись. Logging schema не заменяет recovery state machine и не доказывает корректность immutable request replay.

Следующий шаг: владелец Artifacts/publication исправляет свой проект по RLOG-1–3; Source сверяет диагностическую проекцию. Код, Source proof schema и DAG не менялись.

## Повторная проверка 2026-11-14

Владелец заменил прежние logging-разделы единым актуальным roster. RLOG-1 исправлен по содержанию: family/owning code/context не теряются; RLOG-2 исправлен через field projection и повторное использование SourceLogicIssue; RLOG-3 исправлен единым roster, strict numeric, activity invariants и closed wire values. Исторический verdict выше относится к прежней версии.

Source уточняет единственное размещение diagnostic projection: app.dataModel.sourceVersioning.sourceLogProjection. SourceDiagnosticLogKind — FIELD="field", LOGIC="logic". SourceFieldLogEntry(code: SourceFieldCode, path: ValidatedFieldPath) не повторяет SourceFieldIssue: это logging projection без message. SourceFieldDiagnosticLogEntry(kind: Literal[SourceDiagnosticLogKind.FIELD], issue: SourceFieldLogEntry) и SourceLogicDiagnosticLogEntry(kind: Literal[SourceDiagnosticLogKind.LOGIC], issue: SourceLogicIssue) составляют discriminated SourceDiagnosticLogEntry по kind. Все поля обязательны, strict/frozen/extra-forbid/revalidate-always; нового логического error DTO нет. Pure SourceDiagnosticLogProjector.project(failure: SourceFailure) -> tuple[SourceDiagnosticLogEntry, ...] в application/worldData/sourceVersioning/logging/diagnosticProjection.py сохраняет field-then-logic порядок. Нет IO, emit, изменения failure или нового operation outcome. Caller отдельно переносит failure.operation в event.source_operation без переименования.

Узкое нормативное уточнение INFO/WARNING для recovery и existing route внесено в docs/tz_logging.md по поручению пользователя «Исправляй». Runtime acceptance этим не заявлена.

**RLOG-4, OPEN:** dataModel/artifacts/recoveryEvents.py должен использовать owning codes/fault POJO из dataModel, но ранние разделы response размещают некоторые из них в application/errors. Нужны точные единственные dataModel-модули; application exceptions несут эти POJO, обратный импорт запрещён. Поскольку существующие proposed fault records уже содержат только safe code/identity context, лог должен оборачивать их discriminator без зеркального fault DTO. Требование передано владельцу. До фиксации import graph и повторной проверки полный logging срез NOT ACCEPTED для реализации.

Новые production POJO/classes здесь только специфицированы. Код и тесты не создавались; runtime проверки отсутствуют. Полная приёмка recovery также требует closure остальных owning infrastructure gates независимо от закрытия logging findings.

## Итог повторной проверки RLOG-1–4

Владелец уточнил единственные определения: dataModel/publication/recoveryFault.py, dataModel/publication/domainAttemptFault.py, dataModel/artifacts/lifecycle/sourceRootAcquireFault.py. Application exceptions переносят соответствующие fault POJO; recoveryEvents импортирует dataModel, не application. Три discriminated log wrappers содержат исходный fault целиком, без копии полей/code enum. RLOG-4 закрыт на уровне проекта.

**RLOG-1–4 исправлены и проверены статически.** Это закрытие четырёх конкретных замечаний, не приёмка реализации или полного recovery плана. Для Source diagnostic wrapper используются точные имена и Literal-типы из раздела повторной проверки выше; сокращения FieldEntry/LogicEntry в owning response обозначают эти же типы и не разрешают дополнительные классы.

Нормативное logging amendment записано в docs/tz_logging.md. Фактический emitter→sink, crash/replay, fault injection и типизация runtime ещё не проверялись: новых Python/SQL файлов в этом исправлении нет. Перед реализацией остаётся полная приёмка recovery с scope/attempt/hold-transfer/immutable-request контрактами по обязательным правилам проекта.
