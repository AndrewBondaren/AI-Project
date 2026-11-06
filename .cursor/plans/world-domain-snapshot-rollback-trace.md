# D1: подтверждение rollback в CAS trace

2026-11-06. Исправление [замечания ревью](world-domain-snapshot-cas-trace-review.md).

## Контракт

[DTO](../../backend/app/dataModel/worldSnapshot/results/publication.py) сохраняет неизменные факты сравнений: world applied, p1 applied, p2 mismatch. Поле `transaction_outcome: CasTransactionOutcome` отдельно определяет судьбу всей попытки. `PENDING` не подтверждает откат; `ROLLED_BACK` подтверждает откат всех записей попытки, включая ранее applied CAS.

[WorldSnapshotService](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py) создаёт trace с PENDING. [Владелец транзакции](../../backend/app/db/repositories/sqlite/snapshotCore/commitScope.py) заменяет trace на ROLLED_BACK только после успешного acknowledgement rollback и проверки отсутствия активной транзакции. Исключение rollback, оставшаяся активной транзакция или отсутствие транзакции до команды rollback дают UnknownCommitOutcome и quarantine. Отсутствие транзакции само по себе не доказывает откат. Отмена сохраняет прежнюю семантику CancelledError.

## Проверки

[AssignedPublicationTests](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py): 7 OK. Реальный сервис проверен для world conflict и конфликта второго игрока: полные expected/observed, provenance, порядок достигнутых CAS, ROLLED_BACK у caller. Второе SQLite-соединение подтверждает прежние heads, отсутствие metadata попытки и marker-записей handlers. Отказ handler сохраняет исходный SectionRefused; успешная публикация подтверждается peer. Новый тест проверяет три инфраструктурных сценария: исключение после физического rollback, незавершённый rollback, неизвестное завершение транзакции до rollback. Исходный trace остаётся PENDING.

18 тестов PublicationCasTests прошли; 11 тестов registry (включая metadata builder) прошли. Адресный набор с typing: 25 тестов, единственный failure — базовая positive typing ошибка `artifactGc.py:47` (нет аргумента code). Negative typing: все 51 диагностики совпали с EXPECT по строке и правилу.

Первый полный snapshotCore: 170 тестов за 206.681 с, errors=8, failures=1, skipped=1, как в базе ревью.

Scope ограничен DTO, сервисом, границей rollback и профильными тестами. Cancel/GC, persisted terminal и retry не изменялись.

Финальный полный snapshotCore: **171 тест за 186.979 с; 8 errors, 1 failure, 1 skip**. Прирост к базе — один зелёный тест rollback. Все восемь ERROR, typing FAIL и Windows symlink SKIP совпадают по ID с таблицей [базы ревью](world-domain-snapshot-cas-trace-review.md#повторные-запуски): семь cancel ошибок в leaseStore.py:165 и GC ошибка в artifactGc.py:47. Новых падений нет. Команда: `python -m unittest discover -s tests/snapshotCore -v` из backend. `git diff --check` по файлам этого исправления пройден.


## Трейс оставшихся ошибок artifacts

Исследование 2026-11-06: чтение production-кода, traceback полного прогона и истории Git. Это диагностика, не реализация cancel/GC или persisted terminal. Новые тесты в рамках исследования не запускались.

**Вывод:** домен artifacts не завершил переход на изменённый общий контракт ошибок. Общий validation намеренно запретил создание базового FieldPathError; старые producers, аннотации DTO и wire-регистрация artifacts остались на прежней модели. Это отдельная причина базовых падений, не регрессия исправления CAS trace.

### Cancel: семь ERROR с одной ранней причиной

Цепочка: [ArtifactStagingService.cancel](../../backend/app/application/artifacts/staging/artifactStaging.py) → [OperationLedger.cancel](../../backend/app/application/publication/service/operationLedger.py) → [SqliteArtifactLeases.cancel](../../backend/app/db/repositories/sqlite/artifacts/leaseStore.py#L163) → создание `OperationCancelled(reason=FieldPathError(path=(), message="cancelled"))` → [FieldPathError.__new__](../../backend/app/dataModel/validation/diagnostics/fieldPathError.py#L50) → `TypeError: FieldPathError requires a named concrete domain subclass`.

Ledger проверяет operation_id и положительность fence. Lease store падает на построении reason **до входа в транзакцию отмены**. Не достигаются чтение операции, проверка актуальности fence, возврат существующего terminal, закрытие admission, ожидание writers, освобождение holds и сохранение terminal. Поэтому семь сценариев падают на одной строке; в частности, TypeError перекрывает ожидаемый отказ stale fence. Эти падения не доказывают неисправность последующих механизмов: выполнение до них не дошло.

### GC: один ERROR и typing failure

Цепочка: `ArtifactStagingService.collect` → [ArtifactGarbageCollector.collect](../../backend/app/application/artifacts/lifecycle/artifactGc.py) → guard → чтение catalog → проверка holders → `registry.delete` → тестовый `OSError("IO")` → обработчик `(OSError, ValueError)` → создание `FieldPathError(path=(), message=str(exc))` → тот же TypeError.

В проверенном сценарии ошибка возникает при формировании диагностики исходного отказа удаления. Caller получает TypeError вместо GcReport с failed candidate; событие GC_FAILED и возврат отчёта не достигаются. Pyright на той же строке 47 дополнительно сообщает `Argument missing for parameter "code"`. Добавление code само по себе не исправит запрет прямого создания carrier и не определит подходящий доменный исход. Windows symlink skip связан с отсутствием привилегии окружения, а не с этой миграцией.

### История разрыва

| Коммит | Наблюдение |
|---|---|
| `ab835faf5` | По git blame старый конструктор FieldPathError в GC происходит из этого коммита. |
| `9557f0e8a` | По git blame старый конструктор причины cancel происходит из этого коммита. |
| `9b1f845d` | FieldPathError переведён из dataclass в generic Pydantic-модель с обязательным enum code, ValidatedFieldPath и запретом прямого создания carrier. Сообщение коммита явно говорит: «Domain consumers of the old FieldPathError are not migrated yet (D2 per A0 register)». |

Текущий запрет реализован в __new__; последующие изменения общего carrier не мигрировали два указанных producer.

### Владелец и граница следующего исправления

Владелец — artifact lifecycle: причина отмены операции и описание отказа GC. [Error-contracts, A0-F5 и реестр Artifacts](error-contracts-1.md#L166) уже выделяют cancel как управляющий исход F06, а GC failure как технический отказ F05. Это не ошибки проверки поля. Прежняя рекомендация механически заменить базовый FieldPathError конкретным подклассом уточняется: сначала нужен соответствующий природе события доменный контракт, без искусственного field path и без ослабления общего validation.

Сейчас [OperationCancelled.reason](../../backend/app/dataModel/artifacts/lifecycle/operation/record.py) имеет тип FieldPathError, а [GcReport.failed](../../backend/app/dataModel/artifacts/lifecycle/gc.py) — tuple[FieldPathError, ...]. Для cancel имеется дополнительная граница: результат передаётся в operationStore.record_terminal и [StoredTerminalCodec.encode/decode](../../backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py); [ARTIFACT_CORE_SCHEMA](../../backend/app/application/artifacts/encoding/coreManifest.py) регистрирует базовый FieldPathError как record с type_id 20137.

Следовательно, будущая смена причины cancel требует согласования DTO и persisted wire-контракта с проверкой round-trip. Это выявленная зависимость следующего среза, а не воспроизведённая ошибка codec: текущие семь падений до сохранения terminal не доходят. Cancel/GC, persisted terminal и retry в этом исследовании не изменялись.
