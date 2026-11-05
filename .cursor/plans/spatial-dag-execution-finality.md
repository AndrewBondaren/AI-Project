# SP-P2W — когда Pack может освободить pins execution

Исследование от 2026-11-05 к [§15.95 о времени жизни pins](./spatial-distribution-domain.md#1595-принятое-решение--lifetime-pin-до-конца-execution-и-защита-одного-blob) и [§15.96 о границе SQLite guard](./spatial-distribution-domain.md#1596-sp-p2w--terminal-при-открытом-blob-и-граница-sqlite-guard).

**Вывод.** Сейчас DAG не предоставляет Pack достаточного наблюдаемого события для release всех pins execution. Ближайшее событие — commit checkpoint с сохранённым ответом и статусом `COMPLETED`. Обычный resume после него не запускает следующий pass, но вызывает lifecycle восстановленных outputs до проверки ответа. Статус строки `FAILED` ещё слабее: он может отражать только статус root текущего прохода. [Выбор статуса](../../backend/app/dataModel/engine/dag/invocations/record.py#L99) · [Порядок restore](../../backend/app/application/engine/runtime/dagEngine.py#L228) · [Вызов validate_restored](../../backend/app/application/engine/runtime/invocations/checkpointCodec.py#L23)

| Событие | Кто ещё может работать | Отзыв права и reopen | Решение Pack |
|---|---|---|---|
| Движок сохраняет response всего execution, затем возвращает результат. | Scheduler дождался своих активных задач. Обычный resume получает новый claim, восстанавливает outputs и возвращает ответ без нового прохода. Отдельный вход run_invocation тоже берёт claim и вызывает restore. | SQLite сохраняет ответ и ревизию. Claim не проверяет terminal-статус. Сохранение ответа не закрывает старому reader допуск к новому BLOB. | До подтверждения запрета новых открытий pins остаются. [Запись ответа](../../backend/app/application/engine/runtime/dagEngine.py#L353) · [run_invocation и scheduler](../../backend/app/application/engine/runtime/dag/dagExecutor.py#L65) · [SQLite claim](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L44) |
| Child A завершается ошибкой, child B читает shard. | При разрешённом retry coordinator возвращает A в READY до save. При исчерпанном retry отказ A входит в результат вызова. B продолжает читать. После join родитель может запросить новых children. После transition возможен next_pass. | Checkpoint хранит записи invocation. При восстановлении coordinator переводит RUNNING в READY, поэтому B может стартовать снова. Отказ A не отзывает эти права. | Сохраняются все pins, включая pin A. Закрытие файла B или завершение root текущего pass тоже недостаточно. [FIRST_COMPLETED и save](../../backend/app/application/engine/runtime/dag/dagExecutor.py#L93) · [Retry, child и join](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L174) · [RUNNING при восстановлении](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L37) · [Caller next_pass](../../backend/app/application/engine/runtime/dagEngine.py#L329) |
| Сохранён graph.failure всего execution при работающем или восстанавливаемом worker. | На путях отказа прохода или ответа с interaction_owner движок сохраняет failure. При отказе прохода без него движок бросает исключение. После reopen сохранённый failure блокирует новый drive, но restore callbacks выполняются раньше. У старого worker мог остаться ref. | SQLite проверяет owner, fence и revision при checkpoint. Новый claim лишает старого владельца права записи. Даже явный cancel с повышением fence не удостоверяет закрытие stream или запрет физического open. | Сохранённый failure позволяет начать остановку. Cleanup ждёт подтверждения отзыва прав на дальнейшую работу. Уже открытый файл должен закрыться до release. [Ветка FAIL](../../backend/app/application/engine/runtime/dagEngine.py#L315) · [OwnedExecution.save](../../backend/app/application/engine/runtime/invocations/ownedExecution.py#L17) · [Checkpoint и cancel](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L57) |

## Предложение для решения пользователя, DAG и Pack

**DAG** публикует один монотонный durable-факт окончательности execution, условно `finalized(execution_id, revision, outcome)`. Предусловие публикации — действующий и прежние владельцы больше не могут начать child, retry или pass. Уже работающие потребители завершены либо лишены полномочий начать следующую операцию. Все точки входа соблюдают эту границу. После reopen результат доступен без callback, которому требуются pins. Сбой между публикацией и cleanup не теряет факт.

**Pack и artifact storage** упорядочивают с публикацией этого факта допуск каждого физического открытия, включая открытие по ранее выданному ref. Увидев finalized, Pack перечисляет все OPEN pins execution и идемпотентно освобождает их. Для уже допущенного IO guard удерживает файл до закрытия, и только затем снимается hold. Между root и shard reader возвращает отказ без частичного окна. При отдельных БД требуется доказать порядок admission и fence через границу хранилищ.

## Контрпример и граница проверки

1. Остановить B после успешной предварительной проверки статуса следующего shard, до входа в guard. Завершить A ошибкой и проверить, что pins остались.
2. Довести весь execution до отказа, опубликовать finalized, переоткрыть store и отпустить B. Новый физический open опровергает контракт, даже если следующий checkpoint B отклонён по fence.
3. Отдельно выполнить resume terminal execution с наблюдаемым validate_restored. Попытка callback обратиться к освобождённым данным также опровергает контракт.
4. Для IO, допущенного до финализации, проверить обратный порядок: закрытие stream предшествует release. Повтор cleanup после reopen должен сохранить общий shard, удерживаемый версией B.

Существующая проба формирует FAILED вручную. При одной SQLite-базе открытый reader под BEGIN IMMEDIATE задерживает запись FAILED. При отдельных БД cleanup ждёт guard, но предварительная проверка статуса оставляет окно до admission. В §15.96 зафиксирован результат 2/2 для этой пробы. Итог повторного запуска во время исследования не подтверждён. [Барьер, checkpoint и release в пробе](../../backend/tests/spatial_pack/test_pin_worker_drain.py#L66)
## Проверка terminal resume через DAGEngine (2026-11-05)

Focused-тест завершает Pipeline через штатный `DAGEngine.run`, получает ответ `count=5`, проверяет сохранённый `COMPLETED` и закрывает соединение SQLite. Для каждой попытки `resume` тест создаёт новое соединение, store и engine. Lifecycle существующего тестового root использует восстановленное значение `Text.text` как ключ внешнего файла. Удаление файла моделирует потерю доступности данных после release. Pack в тесте не участвует. [Исполняемый тест](../../backend/tests/dag_typing/invocations/test_world_calls.py#L307)

| Состояние файла при reopen | Наблюдение на штатном resume |
|---|---|
| Доступен | Restore вызывает `validate_restored(Text(text="count=5"))`. Callback открывает файл и читает `held data`. Только затем caller получает ответ, равный исходному. |
| Удалён | Тот же callback пытается открыть тот же файл. `FileNotFoundError` оборачивается в `RestoreFailure` кодеком и затем движком. Caller получает исключение, хотя ответ по-прежнему сохранён. |

В обоих случаях checkpoint после вызова равен исходному, включая статус, ревизию и blob. Причина порядка — вызов `CheckpointCodec.restore` внутри `_restore_durable` до ветки `graph.response`. [Caller в DAGEngine](../../backend/app/application/engine/runtime/dagEngine.py#L242) · [Callback в кодеке](../../backend/app/application/engine/runtime/invocations/checkpointCodec.py#L23)

**Уточнение для согласования.** После публикации `finalized` для завершённого execution штатный `resume` обязан вернуть сохранённый ответ после reopen, даже если Pack уже освободил все его pins и связанные данные недоступны. До возврата нельзя запускать восстановление outputs, требующее доступа к этим данным. Проверяемая граница — тот же результат и ноль попыток открыть освобождённые данные. Сегодня второй случай таблицы воспроизводит нарушение предложенной гарантии.

Воспроизведение из `backend`:

```powershell
../.venv/Scripts/python -B -m unittest -v tests.dag_typing.invocations.test_world_calls.RecoveryTests.test_terminal_resume_requires_data_read_by_output_lifecycle
```

Результат на Windows — один тест, оба случая прошли (`OK`).
