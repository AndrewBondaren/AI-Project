# Pack preparation — закрытый состав diagnostics

2026-11-13, PROJECT для согласования. Runtime и ТЗ не изменены. Сверка [write-плана](pack-v2-public-write-operations.md) с `docs/tz_world_pack_storage.md`, раздел errors.py: ТЗ содержит только tuple[PackPreparationIssue, ...], а проект schema admission требует существующие JsonFieldError/WireShapeIssue. До синхронизации это расхождение, не принятый контракт.

## Предлагаемое точное изменение

В проектном `dataModel/worldPack/preparation/errors.py` объявить type alias `PackPreparationDiagnostic = JsonFieldError | WireShapeIssue | PackPreparationIssue`. Это закрытый union трёх существующих/уже проектных именованных классов, не новая модель-carrier. Поле PackPreparationError.issues получает тип `tuple[PackPreparationDiagnostic, ...]`, остаётся обязательным и непустым. Reason и оболочка PackPreparationFailure не заменяются. JsonFieldError/WireShapeIssue импортируются от владельца, поля не копируются. Широкий ImportIssue/FieldPathError[Any] в публичный контракт не попадает.

| Тип | Когда создаётся | Чего не делает |
|---|---|---|
| JsonFieldError | Schema нарушение с разрешимым путём объявленного поля | Не получает новый Pack-код для той же структурной причины |
| WireShapeIssue | Неизвестный ключ, неправильная форма или ошибка корня без допустимого field path | Не создаёт фиктивный ValidatedFieldPath |
| PackPreparationIssue | Семантический Pack predicate над структурно допустимыми данными с реальным полевым путём | Не заменяет malformed-schema или infrastructure exception |

При структурном отказе reason=INVALID_INPUT. SCHEMA_VIOLATION требует pydantic_type в обеих structural моделях; для других JsonValidationCode он отсутствует по owning validator. Семантические reason/code пары сохраняют таблицу write-плана. Одно нарушение не дублируется в двух variants. Смешанный набор с structural issues классифицируется как INVALID_INPUT; независимые доступные semantic проверки могут добавить свои полевые issues, но не исполняют зависимые эффекты. Полный freeze остальных semantic codes/operation-level identity context этим не закрывается.

## Цепочка формирования и потребления

1. Transport выполняет собственную schema admission; публичный Pack Input остаётся именованным typed POJO. Raw dict не становится альтернативным Pack API.
2. Pack повторно проверяет фактические поля экземпляра, включая model_construct/model_copy. Существующий pure pydantic_issues переводит структурные ошибки; полный resolve_model с нормализацией/reporting не вызывается ради диагностики.
3. Результат широкого ImportIssue принимается только после exact-class проверки JsonFieldError/WireShapeIssue. Неожиданный тип — дефект адаптера, не пользовательский отказ; cast не заменяет проверку.
4. Request-local ValidatorAggregationHelper допускает ровно три concrete класса. Он проверяет frozen/revalidate/immutable свойства и сохраняет порядок. Невалидный parent исключает лишь зависимую проверку; другие доступные проверки продолжаются.
5. По snapshot фабрика создаёт один PackPreparationError и затем PackPreparationFailure. Только отсутствие issues разрешает изменение state или следующий зависимый I/O этап. IssueAdmissionError, infrastructure/cancellation не превращаются в INVALID_INPUT.
6. Consumer выбирает поведение по reason и concrete diagnostic/code; message не является протоколом. start_from_base сохраняет собственный ManifestReadRefusal, activate/release — свои outcomes, этот union не поглощает их.

Canonical registration использует существующие identities JsonFieldError/WireShapeIssue и новые Pack declarations; повторно регистрировать shared class с новым ID нельзя. Cold restore должен однозначно восстанавливать concrete variant, включая CheckedPath.owner и вложенные paths. Конкретные encoding IDs и round-trip vectors ещё требуют отдельной сверки; «union написан» не означает готовность wire transport.

## Критерии проверки

Лишний ключ → WireShapeIssue без фиктивного field path; неверный тип известного поля → JsonFieldError; semantic mismatch → PackPreparationIssue; две независимые ошибки сохраняются; forged instance проверяется; неожиданный ImportIssue variant не проходит; INVALID_INPUT не начинает storage; cold round-trip сохраняет concrete class/code/path. Проверить неоднозначность union при wire restore и порядок diagnostics. Тесты не запускались.

Решение для пользователя: расширить только issues до указанного закрытого union, переиспользуя structural diagnostics, и после согласования синхронизировать owning ТЗ. До этого runtime-реализация данного контракта не начинается. Иные поля ошибок, generic expected/actual, новый public error service и изменение порядка DAG не предлагаются.
