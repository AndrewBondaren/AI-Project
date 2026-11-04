# Независимое ревью 4D2 — player CAS в той же транзакции

**CHANGES REQUIRED** · 2026-11-04 · HEAD `42e7f6e029656bbd5a274435ff23b59628a93542`. Реализация выполнила проверенные обязательства. Для приёмки требуются три регрессионных проверки в `AssignedPublicationTests`. Регрессий в ранее принятом срезе assigned Q → handlers → world CAS не обнаружено.

Сервис уже находился в `df4ce83c`. К проверенному HEAD расширенный тест и запись в плане также вошли в коммит. На момент окончания ревью релевантный diff к HEAD был пуст, индекс пуст, untracked-файлов не было. Четыре unstaged-файла относились к GEO-1.

## Блокеры приёмки

Все строки относятся к [test_atomicity.py в проверенном HEAD](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py). Подмены выполнялись только в памяти.

| Строки | Контрпример и наблюдение | Минимальный критерий закрытия |
|---|---|---|
| 354–363 | При world MISMATCH список игроков пуст. Перенос обработки результата world CAS за цикл player CAS дал ложный PASS. Даже ошибочный вызов player CAS мог бы исчезнуть из наблюдаемого состояния после rollback. | Задать устаревший world head и непустой набор игроков. Проверить вызов world CAS, конфликт мира и `player_cas.assert_not_awaited()`. |
| 361–372 | Полное удаление проверки состава участников дало ложный PASS. Штатные сценарии используют только согласованные наборы. | Проверить недостающий ref, лишний ref, повтор ref и повтор expectation. Каждый случай должен дать отказ до первого handler и до входа в блок metadata, с нулём вызовов обоих CAS. |
| 413–424 | Ошибка и отмена вводятся при записи metadata. Подмена, превращающая исключения из player CAS в MISMATCH и затем в CONFLICT, дала ложный PASS. | После реального CAS первого игрока ввести из CAS второго по очереди `PublicationInfrastructureError` и `CancelledError`. Проверить тот же объект исключения за границей транзакции и полный откат со второго соединения. |

## Что подтверждено

В [сервисе, строки 40–68](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L40), проверка уникальности UID с обеих сторон и равенства множеств предшествует handlers. Два пустых набора допустимы. В отдельных прогонах на исходном коде все четыре некорректных набора дали `ValueError` до вызова handler.

Внешний `commits.transaction(op)` выдаёт writer scope. Контролируемые handlers получают этот scope и один объект Q и вставляют реальные SQL-маркеры. Тело контекстного менеджера записывает world/player metadata через SQLite history store. При выходе сервис передаёт тот же Q в world CAS, затем в порядке expectations передаёт в каждый player CAS исходный scope, соответствующий expected head, ref по UID и operation_id. Обе mock-обёртки делегируют реальным SQLite CAS через `wraps`. [Player store](../../backend/app/db/repositories/sqlite/snapshotCore/publications/playerPublicationStore.py#L62) проверяет writer scope, operation_id и владельца ref. Откатом владеет [внешняя транзакция](../../backend/app/db/repositories/sqlite/snapshotCore/commitScope.py#L48).

При успехе с обратным порядком refs второе соединение увидело Q, два назначенных player heads, world/player metadata и три маркера handlers. При MISMATCH второго игрока после успешного CAS первого caller получил `_ApplyRefused` с категорией `CONFLICT` и путём `("expected_players", "p2")`. Второе соединение увидело прежний world head, оба исходно пустых player heads и отсутствие новой metadata и маркеров.

Дополнительный прогон на исходном сервисе с world MISMATCH и двумя игроками подтвердил ноль вызовов player CAS. В двух отдельных прогонах ошибка инфраструктуры и отмена из CAS второго игрока вышли за границу транзакции тем же объектом. В обоих случаях второе соединение подтвердило полный откат.

Штатный тест упал при каждой из трёх отдельных подмен. Позиционное сопоставление refs вызвало ошибку владельца в SQLite player store. Пропуск последнего CAS нарушил ожидаемый список вызовов в успешном сценарии. Игнорирование MISMATCH второго игрока оставило caller без ожидаемого отказа.

## Прогоны из backend на проверенном HEAD

| Команда | Результат |
|---|---|
| `../.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests tests.snapshotCore.contracts.test_typing` | 2 теста, OK, 15,798 с |
| `../.venv/Scripts/python.exe -B -m unittest discover -s tests/snapshotCore -p "test_*.py"` | 164 теста, OK, 1 пропущен, 158,824 с |

Граница ревью задана в [разделе плана 4D2](world-domain-patches-snapshots.md#L2943). Публичный apply(), общий metadata builder, terminal/retry и production wiring вне среза.
