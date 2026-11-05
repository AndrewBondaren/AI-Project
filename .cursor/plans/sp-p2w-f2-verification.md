# SP-P2W F2 — остановка DAG и восстановление intent

Проверен рабочий diff поверх `d01cf073967683fe22d0ec8554b837f1c0bf18b4`. На входе HEAD совпадал с отчётом F1, а рабочие изменения относились к планам и отчётам. Вход для F3 со стороны DAG готов.

## Контракт на границе F2

При явном включении `DAGEngine(enable_stop_intent=True)` владелец записывает через F1 точный JSON ответа либо диагностику окончательного отказа. Начало и восстановление остановки дают `ExecutionStopping` с неизменяемым intent. Он содержит ключ для F3 — store_id, execution_id и stop_revision — и сохранённый outcome. После reopen recovery owner проверяет execution и доступ, затем повторяет CAS с исходной revision и outcome до compile и восстановления outputs. Включение для production остаётся за F6. [DAGEngine](../../backend/app/application/engine/runtime/dagEngine.py) · [OwnedExecution](../../backend/app/application/engine/runtime/invocations/ownedExecution.py)

Каждый старт выбранной invocation требует checkpoint CAS **внутри worker**. Тот же store упорядочивает его с записью intent по owner, fence и revision. CAS допускает ровно одну попытку. Следующая попытка, продолжение и новый pass запрашивают допуск заново. Прямой запуск и принятие input проверяют intent до рабочего claim и повторно под claim. У прежнего владельца отозвано право записи, scheduler отменяет оставшиеся локальные задачи и дожидается их выхода. [DAGExecutor](../../backend/app/application/engine/runtime/dag/dagExecutor.py)

## Воспроизведение

| Сценарий | Наблюдение |
|---|---|
| Два соединения SQLite, выбранный child, retry и join | Worker остановлен на барьере после выбора. Второй владелец получил новый fence, записал FAILED и освободил lease. После снятия барьера новых вызовов node — 0. Запись checkpoint прежним владельцем отклонена. Прямой run_invocation отклонён до обращения за рабочим claim. [Тест](../../backend/tests/dag_typing/invocations/test_world_calls.py#L311) |
| Одна задача уже вошла в обработчик, sibling выбран | После смены владельца sibling отклонён, cleanup активной задачи завершён до выхода scheduler. Сохранён исходный intent. [Тест](../../backend/tests/dag_typing/invocations/test_world_calls.py#L365) |
| Выбран следующий pass | После выбора перехода новый владелец записал intent. Прежний владелец получил OwnershipConflict до compile следующего pass. [Тест](../../backend/tests/dag_typing/invocations/test_world_calls.py#L412) |
| Input уже принят, продолжение выбрано | После отзыва повторный input отклонён, вызовов resume у child — 0. Новое SQLite-соединение восстановило тот же FAILED до compile. [Тест](../../backend/tests/dag_typing/invocations/test_input_wait.py#L92) |
| Child завершился ошибкой, родитель обработал join | Родитель вернул `joined`, владелец сохранил COMPLETED. После закрытия SQLite повторные run и resume вернули управление на границе F2 с тем же intent. Вызовов compile и CheckpointCodec.restore — 0. [Тест](../../backend/tests/dag_typing/invocations/test_world_calls.py#L450) |
| Отмена всего execution | Владелец сохранил FAILED с диагностикой `execution cancelled`. После reopen получен тот же intent. [Тест](../../backend/tests/dag_typing/invocations/test_input_wait.py#L78) |

## Проверки

Профильные модули `test_world_calls`, `test_input_wait` и `test_execution_stop_intent` — 37/37. Штатный положительный Pyright — 0 ошибок и предупреждений. Windows asyncio в sandbox зависал при создании локальной socketpair до тестов, поэтому DAG-прогоны выполнены вне sandbox.

В первом полном прогоне 398 из 399 тестов прошли. В `test_slow_effect_retains_lease` запись checkpoint получила OwnershipConflict при двухсекундной lease. Кодирование графа перенесено перед renew. Итоговый полный DAG-набор по команде §9, включая две добавленные проверки активного sibling и отмены всего execution, прошёл **401/401 за 159,135 с**. Проверка `git diff --check` по файлам F2 и проверка ссылок отчёта прошли.

Граница поставки — сохранённый stop intent. Pack CLOSED, DAG finalized и release относятся к следующим срезам.
