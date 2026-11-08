# Pack F3 — проверка закрытия допуска

8 ноября 2026. Реализация §§15.99–15.103. DAG и Pack используют разные файлы SQLite. Тесты публикуют manifest V2, root и shard через SQLite-адаптеры и файловый BLOB backend. Точкой порядка служит commit в Pack.

## Evidence по карте §15.102

| Сценарий | Наблюдаемый результат | Проверка |
|---|---|---|
| Ответ на close потерян | После commit тест закрывает Pack-соединение и создаёт адаптер заново. Повтор возвращает исходную тройку, в таблице одна запись CLOSED, у manifest сохранился pin holder, у root и shard сохранился holder этого manifest. | [test_lost_reply](../../backend/tests/spatial_pack/test_execution_pins.py#L84) |
| Чужая identity или revision | До и после CLOSED проверены чужой UUID, отсутствующий execution и другая revision. Сохраняется прежнее удержание. Два независимых DAG store используют одно имя execution. Закрытие второго до появления pins запрещает его первый acquire и оставляет первый execution доступным. Недоступность DAG при первом close даёт typed unavailable. | [test_conflicts](../../backend/tests/spatial_pack/test_execution_pins.py#L119), [два namespace](../../backend/tests/spatial_pack/test_execution_pins.py#L98) |
| CLOSED первым | Worker уже получил ref и разрешил его через manifest и root. Барьер останавливает его перед guard целевого shard. После commit CLOSED и снятия барьера worker получает PackClosed. За этот интервал вызовов Path.open ровно 0. | [test_stale_worker](../../backend/tests/spatial_pack/test_execution_pins.py#L136) |
| Физический open первым | Барьер стоит внутри открытого файла root. На втором Pack-соединении SQLite trace фиксирует попытку BEGIN IMMEDIATE. close ждёт. В момент INSERT CLOSED stream уже закрыт. Проверены успешное завершение и отмена чтения с drain. Следующее чтение shard отклонено, holds сохранились. | [test_stream_first и вариант с отменой](../../backend/tests/spatial_pack/test_execution_pins.py#L160) |
| Crash после CLOSED, до finalized | Тест моделирует потерю состояния процесса закрытием Pack и созданием новых соединений и адаптеров после commit. До остановки pins двух invocation читают один shard через разные manifest A/B. После reopen при отключённом DAG load локальная запись возвращает прежний receipt. Оба acquire и read отклонены. Проверены точные pin holds A/B и независимые удержания общего shard обоими manifest. | [test_crash_and_shared_shard](../../backend/tests/spatial_pack/test_execution_pins.py#L215) |

## Хранение и состав проверки

[Начальная схема 0001](../../backend/app/db/migrations/0001_initial.sql) создаёт таблицы CLOSED и OPEN pins вместе с журналом держателей. Pin binding ссылается на точную пару world/publication и локальный PK manifest. Составной FK журнала связывает pin с тем же manifest. На свежей базе отдельно проверены цепочка acquire/release для operation holder, пустой pin_id у обеих записей и PRAGMA foreign_key_check. [Тест начальной схемы](../../backend/tests/spatial_pack/test_execution_pins.py#L239)

[ExecutionPins.bind](../../backend/app/db/repositories/sqlite/worldPack/executionPins.py) привязывает экземпляр к UUID доверенного ExecutionStore и зарегистрированному manifest contract, версии и бюджету из композиции Pack. При первом acquire проверяется существование execution. При первом close адаптер сверяет типизированную команду с durable stop intent и revision. Для повторного close достаточно привязанного namespace и сохранённой тройки.

При чтении shard адаптер сначала читает pinned manifest и проверяет descriptor в root. Каждый физический read получает отдельный допуск и удерживает Pack writer до возврата backend. Такая проверка closure требует повторного чтения manifest и root для каждого запроса shard. В репозитории существующие прямые вызовы raw OpenWaterBlobReader относятся к тестовым пробам. Execution-bound входы F3 — ExecutionPins.read_root и read_shard.

Команды из backend на Windows:

```text
python -m unittest -v tests.spatial_pack.test_execution_pins
python -m unittest -v tests.spatial_pack.test_execution_pins tests.spatial_pack.test_guarded_blob_read tests.spatial_pack.test_pin_worker_drain tests.spatial_pack.test_pin_binding_replay tests.spatial_pack.test_manifest_pin_retention tests.snapshotCore.contracts.test_codec
```

После переноса схемы в 0001 расширенный прогон на заново созданных временных SQLite-базах завершился успешно. Прошли 35 из 35 тестов за 119,524 с, включая все 8 тестов модуля F3.

Граница отчёта — Pack CLOSED до DAG finalized и release. Сценарий восстановления воспроизводит потерю процесса после подтверждённого SQLite commit; отдельная инъекция сбоя питания не выполнялась.
