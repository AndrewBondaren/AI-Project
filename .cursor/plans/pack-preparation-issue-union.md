# Pack preparation — закрытый состав diagnostics

2026-11-13. Состав union согласован, ТЗ и [write-план](pack-v2-public-write-operations.md) синхронизированы. Устранено расхождение: прежнее ТЗ допускало только tuple[PackPreparationIssue, ...], хотя schema admission требовал JsonFieldError/WireShapeIssue. Runtime не изменён; реализация и canonical transport остаются PROJECT.

## Предлагаемое точное изменение

В проектном `dataModel/worldPack/preparation/errors.py` объявить type alias `PackPreparationDiagnostic = JsonFieldError | WireShapeIssue | PackPreparationIssue`. Это закрытый union трёх существующих/уже проектных именованных классов, не новая модель-carrier. Поле PackPreparationError.issues получает тип `tuple[PackPreparationDiagnostic, ...]`, остаётся обязательным; пустой tuple допускается только при reason=MANIFEST_OVERSIZE, для остальных причин нужен непустой tuple. Reason и оболочка PackPreparationFailure не заменяются. JsonFieldError/WireShapeIssue импортируются от владельца, поля не копируются. Широкий ImportIssue/FieldPathError[Any] в публичный контракт не попадает.

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

## Проверка семантических путей (2026-11-13)

Корень путей final prepare — проектный PackPreparationInput, а не несуществующий persisted manifest. У pure write корень — конкретный named Input этого метода; префикс body нельзя автоматически добавлять к его путям. Ниже запись пути — читаемая проекция будущего CheckedPath, не строковый способ создания ValidatedFieldPath.

| Установленное нарушение | Reason / code | Реальный объект диагностики |
|---|---|---|
| Заявленный fingerprint не совпадает с вычисленным body | IDENTITY_CONFLICT / IDENTITY_MISMATCH | preparation_fingerprint |
| Тот же operation_id уже связан с другим запросом | IDENTITY_CONFLICT / IDENTITY_MISMATCH | operation_id; не обвинять корректный fingerprint нового body в повреждении |
| Lifecycle подтвердил закрытую операцию | OPERATION_CLOSED / OPERATION_CLOSED | operation_id; busy/unknown outcome не считаются закрытием |
| Неподходящая pinned base | DEPENDENCY_MISMATCH / BASE_PUBLICATION_MISMATCH | body.state.base_publication |
| У заявленного part отсутствует удержание либо seal | ARTIFACT_UNAVAILABLE / HOLD_MISSING либо ARTIFACT_UNSEALED | body.state.parts[i].artifact, после подтверждения соответствующей причины storage port |
| Неверные format/address | DEPENDENCY_MISMATCH / FORMAT_MISMATCH либо ADDRESS_MISMATCH | artifact/address конкретного part, а не произвольный корень |
| Duplicate addresses | DEPENDENCY_MISMATCH / DUPLICATE_ADDRESS | address повторной части по исходному индексу; без предварительной сортировки |
| Отсутствует обязательная часть | DEPENDENCY_MISMATCH / MISSING_PART | body.state.parts как реально существующая коллекция; не путь к выдуманному отсутствующему элементу |
| Не хватает записи metadata provenance | DEPENDENCY_MISMATCH / METADATA_PROOF_MISSING | body.state.assembly_provenance как существующая коллекция; не синтетический индекс |

Это уточняет уже проектные причины, не вводит четвёртый variant diagnostic. Когда отказ относится к идентификатору операции, реальный operation_id допустим как объект диагностики; пути operation.status нет во входе и его создавать нельзя. Source-specific paths и причины не выводятся из неизвестного concrete source_proof; их точный mapping остаётся у интеграционного контракта. Одной общей SOURCE_UNAVAILABLE недостаточно для вывода missing hold или infrastructure failure.

**MANIFEST_OVERSIZE — согласовано пользователем 2026-11-13.** Сериализованный manifest — производный результат, не поле PackPreparationInput. Для этого отказа разрешён PackPreparationError(reason=MANIFEST_OVERSIZE, issues=()). Поле issues остаётся обязательным; для остальных причин пустой tuple отклоняется. Новый non-field carrier не создаётся; размер не приписывается одному part, preparation_fingerprint, фиктивному body.manifest или WireShapeIssue. Непустая диагностика при MANIFEST_OVERSIZE допустима только при наличии реально обоснованного пути, не ради заполнения tuple.

Отказ oversized manifest создаётся явно по результату byte-budget проверки, независимо от ValidatorAggregationHelper.raise_if_any: пустой collector не должен превратить такой отказ в успех. Код MANIFEST_LIMIT_EXCEEDED не обязывает создавать field issue без пути. Приёмка: MANIFEST_OVERSIZE с () проходит model/canonical round-trip, остальные reasons с () отклоняются; issues нельзя опустить; oversized manifest не достигает staging/READY даже при отсутствии полевых ошибок.

Проверки: cold restore пути operation_id; missing part указывает существующую коллекцию; invalid nested input не запускает storage; unknown outcome не становится OPERATION_CLOSED; infrastructure не становится HOLD_MISSING; oversized manifest не получает фиктивный field path. Эти сценарии ещё не выполнялись.

## Критерии проверки

Лишний ключ → WireShapeIssue без фиктивного field path; неверный тип известного поля → JsonFieldError; semantic mismatch → PackPreparationIssue; две независимые ошибки сохраняются; forged instance проверяется; неожиданный ImportIssue variant не проходит; INVALID_INPUT не начинает storage; cold round-trip сохраняет concrete class/code/path. Проверить неоднозначность union при wire restore и порядок diagnostics. Тесты не запускались.

Согласованное решение: расширить только issues до указанного закрытого union, переиспользуя structural diagnostics; owning ТЗ синхронизировано. Иные поля ошибок, generic expected/actual, новый public error service и изменение порядка DAG не добавляются. Общая приёмка плана и проверки реализации сохраняются отдельными требованиями.
