# F3 — проверка входного identity-среза

2026-11-06. Проверен рабочий diff get_store_id в ExecutionStore,
MemoryExecutionStore и SQLiteExecutionStore. SQLite использует тот же
_ensure_identity для get_store_id и record_stop_intent; возврат из with
происходит после commit контекстного менеджера.

Из backend выполнено:

```text
python -m unittest discover -s tests/dag_typing/invocations -p test_execution_stop_intent.py -v
Ran 3 tests in 3.327s
OK
```

Успешны test_identity_before_stop, test_memory, test_sqlite_reopen.
Проверены persistent UUID после reopen, равенство на двух соединениях
одной БД, различие разных БД, отсутствие незавершённой транзакции после
get_store_id и совпадение с последующим stop intent.

Первый запуск в sandbox завис до выполнения тела теста. faulthandler
через 20 секунд показал unittest._callSetUp → asyncio.Runner._lazy_init →
windows_events.ProactorEventLoop → _make_self_pipe →
socket._fallback_socketpair → socket.accept (Python 3.14, socket.py:298).
Это ожидание создания служебного socket pair, не SQLite lock и не вызов
get_store_id. Повтор вне sandbox завершился успешно; production identity
код не менялся.

Оставшийся F3 в этом проходе не реализован. Close receipt, binding,
отдельный holder с миграцией journal, trusted adapter и admission каждого
physical open ещё требуют реализации и пяти сценариев карты §15.102.
Этот отчёт не подтверждает готовность F3. F4/finalized и release не менялись.
