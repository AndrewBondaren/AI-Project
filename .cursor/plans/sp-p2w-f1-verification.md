# SP-P2W F1 — проверка durable stop intent

**Вход для F2 готов.** Проверен HEAD `d01cf073967683fe22d0ec8554b837f1c0bf18b4`. В пределах контракта F1 дефектов не обнаружено. Изменения ограничены отчётом и ссылкой из плана.

## Свидетельства

Из каталога `backend` выполнена команда `.\.venv\Scripts\python.exe -m unittest discover -s tests/dag_typing/invocations -p test_execution_stop_intent.py -v`. Оба теста завершились с `OK`. Они выполняют один сценарий для каждой пары хранилища и outcome — COMPLETED с JSON результата и FAILED с диагностикой. [Тесты и общий сценарий exercise](../../backend/tests/dag_typing/invocations/test_execution_stop_intent.py)

| Проверка | Наблюдение |
|---|---|
| Право первой записи | Истёкшая lease, предыдущий claim после смены владельца, отдельно неверные owner и fence, а также неверная revision дают OwnershipConflict. До успешного CAS checkpoint совпадает с исходным. |
| Идемпотентность | CAS по revision 0 создаёт intent с execution_id и stop_revision 1. Повтор с исходной revision и тем же outcome возвращает равный intent. Повтор с revision 1, другим outcome или прежним claim отклонён. |
| Необратимость записи | Checkpoint по актуальной revision отклонён, cancel и cancel_child вернули False. Последующее чтение подтвердило исходные blob и status, revision 1 и первоначальный intent. |
| Долговечность | После закрытия обоих SQLite-соединений новое соединение прочитало целиком равные checkpoints, включая store_id, execution_id, stop_revision и outcome. Две записи в одной базе имеют один store_id. |

В memory store проверка owner/fence, времени lease, revision и замена snapshot идут без точки приостановки. В SQLite первая запись выполняется внутри BEGIN IMMEDIATE. Итоговый UPDATE ещё раз проверяет owner/fence, срок lease и revision. Обычные writers обновляют только строки версии 2, тогда как запись intent переводит строку в версию 3. [MemoryExecutionStore](../../backend/app/application/engine/runtime/invocations/memoryExecutionStore.py) · [SQLiteExecutionStore](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py) · [Сравнение при повторе](../../backend/app/application/engine/contracts/invocation/executionStore.py)

Отдельная проверка на временной базе обошла текущий create: прямым INSERT записана строка v2 с execution_id `legacy`, revision 7, fence 3, статусом RUNNING, blob из байтов 0…255 и его SHA-256. После закрытия базы load вернул те же байты, revision и статус с пустым intent. Действующий owner записал FAILED на ожидаемой revision 7. После второго открытия повтор с тем же claim, revision 7 и outcome вернул первоначальный intent. Следующий load подтвердил revision 8, исходный blob и тот же intent.

Приёмка заканчивается на storage API. Остановка dispatch и восстановление runtime относятся к F2, взаимодействие с Pack — к последующим шагам.
