# F3 — решение и минимальный срез

2026-11-06 пользователь принял карту §15.102 spatial-distribution-domain.md: immutable close receipt, pin binding с указанными FK и ключами поиска, отдельный pin holder общего журнала, trusted store_id до первого acquire. Один исполнитель координирует DAG, Pack и Artifact schema. Граница — F3, до finalized и release.

Реализован отдельный вход: ExecutionStore.get_store_id() возвращает существующий persistent UUID. SQLite выдаёт его под BEGIN IMMEDIATE и фиксирует до возврата. record_stop_intent использует тот же helper внутри собственной транзакции. Memory store возвращает UUID экземпляра.

В test_execution_stop_intent.py добавлены reopen, два соединения, разные БД и совпадение с последующим stop intent. Успешное выполнение тестов пока не подтверждено; pytest отсутствует в окружении.

Production F3 пока не реализован: receipt, binding schema, holder journal, trusted adapter, admission под guard и проверки гонок остаются открытыми. F4 и release не изменены.

Правки предыдущего прохода отменены и заново внесены через apply_patch.
