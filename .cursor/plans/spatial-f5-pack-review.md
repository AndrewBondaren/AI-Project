# Независимое ревью Pack F5

**Вердикт — ACCEPT для входа в F6.** Ревью рабочего дерева и проверка Bugbot не выявили дефектов в объёме [§§15.100–15.101](./spatial-distribution-domain.md#15100-sp-p2w--шаги-pack-для-раздельных-хранилищ). Вердикт относится к отдельным SQLite-базам DAG и Pack, созданным по текущей редакции `0001_initial.sql`. Миграция существующей БД F3 не проверялась. В общей схеме рассмотрены изменения execution pins и журнала holder events.

## Наблюдения

1. **Допуск к release.** [ExecutionPins.cleanup](../../backend/app/db/repositories/sqlite/worldPack/executionPins.py#L155) загружает checkpoint из привязанного DAG store, сверяет stop intent, final_revision и текущую revision. В каждой Pack-транзакции проверяет CLOSED по store_id, execution_id и stop_revision. При недоступном DAG, отсутствии finalized и поочерёдной подмене каждой части ключа оба проверяемых pin сохранили состояние OPEN и точные holds. Отдельный тест подтвердил сохранение hold при отсутствии CLOSED и при другой stop_revision в CLOSED.
2. **Сбой между двумя pins.** После commit первого pin внесено исключение сразу после записи release-события второго, до обновления его состояния. После отката у pin-a наблюдались RELEASED и отсутствие hold, у pin-b — OPEN и действующий hold. В [тесте восстановления](../../backend/tests/spatial_pack/test_pin_terminal_recovery.py#L42) обе БД закрыты и открыты заново. После каждого из двух вызовов cleanup у execution осталось 0 OPEN pins, read_closed вернул исходный receipt, pin другого execution сохранил hold на том же manifest.
3. **Общий shard A и B.** В [fixture §15.101](../../backend/tests/spatial_pack/test_manifest_pin_retention.py#L186) production cleanup снял последний PinHolder с manifest A. После снятия дочерних holds A сборщик удалил только manifest A. После reopen на root и shard остались точные holds B. Чтение с holder B вернуло все 1913 байтов исходной fixture, SHA-256 `efc45c2be06b296c3190f3128aa657abda3858d978b2de5448d9eae0f68bb308`.
4. **Запоздалый acquire и replay.** После release повтор исходного PinIntent и запрос с новым pin_id для закрытого execution завершились PackClosed. Прямой повтор holders.acquire для снятого PinHolder завершился IntegrityError с сообщением `pin event conflicts with admission`. Обе строки сохранили состояние RELEASED, оба holds отсутствовали.

## Воспроизведение

Команды и состав модулей приведены в [исходном evidence](./spatial-f5-pack-evidence.md). В независимом прогоне прошли 17 из 17 тестов за 80,902 с. Pyright выдал 0 ошибок и 0 предупреждений. Дополнительная проверка промежуточного состояния и запоздалого acquire на временных базах прошла.

Для общего рабочего дерева `git diff --check` вернул код 2 (в evidence указан 1). Команда `git -c core.whitespace=cr-at-eol diff --check` завершилась с кодом 0.
