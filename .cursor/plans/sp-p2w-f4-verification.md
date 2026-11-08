# SP-P2W F4 — фиксация finalized и повторная выдача результата

Проверено рабочее дерево поверх `aecef2af` с незакоммиченными исправлениями Pack F3. Входы описаны в [проверке F2](./sp-p2w-f2-verification.md) и в [приёмке Pack F3](./spatial-f3-pack-evidence.md).

## Что фиксирует DAG

При подключённом `pack_closer` владелец читает CLOSED по namespace, execution и stop revision. Если записи ещё нет, он вызывает close и запрашивает сохранённый receipt. При потере ответа на close используется тот же запрос. Пока выполняется операция Pack, DAG продолжает heartbeat. Проверка receipt и условный UPDATE проходят в одной SQLite-транзакции. UPDATE требует остановленного execution, текущих owner, fence, revision и действующей lease. Исходный blob со stop intent и outcome сохраняется. Версия checkpoint становится 4, revision увеличивается ровно на один. [Оркестрация](../../backend/app/application/engine/runtime/dagEngine.py) · [SQLite CAS](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py)

## Проверенные сценарии

- На обоих store проверены чужие store/execution/revision, потеря lease, старый fence и повторный finalize. Проигравшие попытки оставляют прежний checkpoint. [Тесты store](../../backend/tests/dag_typing/invocations/test_execution_stop_intent.py)
- После потери ответа на close владелец перечитывает receipt. При пустом повторном чтении даже успешный ответ close оставляет intent. Инъекция сбоя перед finalize сохраняет исходный outcome. Инъекция сразу после SQLite commit оставляет действующую lease. После reopen повторные run и resume возвращают исходный ResolveResult или Failed, в том числе после удаления внешнего файла. Проверены нулевые вызовы claim, compile, CheckpointCodec.restore, validate_restored и Path.open. Отдельно проверены чужой task, interaction owner, тип ответа и повреждённая контрольная сумма. [Тесты replay](../../backend/tests/dag_typing/invocations/test_world_calls.py)
- На настоящем Pack после reopen прочитан CLOSED и передан SQLite DAG store. После finalize в Pack одна запись CLOSED, у manifest остаётся pin, у root и shard остаются удержания manifest. [Тест Pack](../../backend/tests/spatial_pack/test_execution_pins.py)

Новые графы сохраняют исходный task для проверки повторного run после смены pass. Старый checkpoint первого pass позволяет определить task по cursor. Для старого многопроходного checkpoint без исходного task доступен resume, а повторный run отклоняется, поскольку его identity нельзя подтвердить.

## Команды

Из `backend` в PowerShell:

```powershell
python -m unittest -v tests.dag_typing.invocations.test_world_calls tests.dag_typing.invocations.test_execution_stop_intent tests.dag_typing.invocations.test_input_wait tests.spatial_pack.test_execution_pins
$mods = rg --files tests/dag_typing -g 'test_*.py' | ForEach-Object { ($_ -replace '\.py$','') -replace '[\\/]','.' }
python -B -m unittest $mods
..\node_modules\.bin\pyright.cmd -p tests/dag_typing/typing/pyrightconfig.json --pythonpath (Get-Command python).Source
..\node_modules\.bin\pyright.cmd --pythonpath (Get-Command python).Source app/db/repositories/sqlite/dagExecutions/executionStore.py app/db/repositories/sqlite/worldPack/executionPins.py app/application/engine/runtime/dagEngine.py app/application/engine/runtime/invocations/memoryExecutionStore.py app/application/engine/contracts/invocation/executionStore.py app/dataModel/engine/dag/invocations/record.py app/application/engine/runtime/invocations/ownedExecution.py
python -m unittest -v tests.dag_typing.invocations.test_world_calls.RecoveryTests.test_slow_effect_retains_lease tests.dag_typing.invocations.test_world_calls.RecoveryTests.test_slow_effect_retains_one_second_lease
```

## Результаты и вход для F5

Полный DAG-набор прошёл **403/403 за 300,292 с**. Обе команды Pyright дали 0 ошибок и 0 предупреждений. В первом совмещённом прогоне DAG и Pack прошли 47/48 за 251,493 с. При записи checkpoint короткая lease истекла и store вернул OwnershipConflict. В полном DAG-наборе и в последующем изолированном повторе оба теста с lease 1 и 2 секунды прошли (2/2 за 15,664 с). Отдельный повтор тестов store, включая истёкшую lease и takeover, и проверки доступа, типа и checksum прошёл 4/4 за 12,047 с.

**Вход для F5 готов.** По ключу execution следующий потребитель может перечитать finalized, получить исходный stop intent и проверить `final_revision == stop_revision + 1`. Между закрытием допуска Pack и обращением F5 к этому факту pins продолжают удерживать данные. Освобождение pins относится к F5.

## Независимая приёмка, 2026-11-08

**ACCEPT по коду F4.** Ревью выявило два окна гонки. В обоих store выдача claim теперь проверяет finalized атомарно. При потере ownership в ходе recovery движок перечитывает победивший checkpoint и проверяет заголовок перед возвратом результата. Независимая проба на memory и SQLite после finalize и release получила OwnershipConflict при новом claim и сохранила final_revision = 2. Отдельный прогон test_execution_stop_intent прошёл 3/3 за 19,127 с.

При общем прогоне проявилась регрессия обычного execution с секундной lease. Для рабочего checkpoint восстановлена прежняя семантика renew при совпадающих owner и fence. После stop intent renew требует ещё действующей lease. Ревьюер проверил обе фазы на обоих store, включая отказ в finalize с истёкшей lease и успех нового recovery owner.

Штатный положительный профиль Pyright и отдельный запуск по семи production-файлам дали по 0 ошибок и предупреждений. При прямом запуске на всех десяти изменённых Python-файлах, включая три тестовых модуля, база с исправлениями F3 содержит 120 диагностик, итог — 114. Сравнение по файлу и тексту ошибки без позиции строки не выявило новых диагностик. Windows asyncio в песочнице зависал на создании socketpair, поэтому тесты выполнялись вне неё.

В контрольном прогоне профильные invocation-тесты прошли 57/57 за 238,912 с. В полном наборе отдельно воспроизведено истечение секундной рабочей lease между commit renew и следующим checkpoint (402/403). В OwnedExecution добавлен один повтор на той же revision при отсутствии stop intent. Повтор заново проходит renew и checkpoint CAS. Независимый ревьюер проверил смену owner/fence и появление intent между чтением и записью, вердикт **ACCEPT**. Прогон двух сценариев terminal replay, обоих store и модуля Pack дал 15/15 за 138,884 с.
После последней правки OwnedExecution полный DAG-набор по §9 прошёл **403/403 за 177,761 с**, в том числе test_world_calls и тесты секундной и двухсекундной lease.
