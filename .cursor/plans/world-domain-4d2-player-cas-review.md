# Независимое ревью 4D2 — player CAS в той же транзакции

## Повторное ревью после исправлений

**PASS** · 2026-11-04 · HEAD `73994eae2d2f6b5039883203c1b2501d161528a6`. Все три блокера первого ревью закрыты. Регрессий в принятом пути assigned Q → handlers → world CAS не обнаружено. К моменту проверки исправления вошли в HEAD. Релевантный diff к HEAD был пуст, staged и untracked файлов не было. Единственное unstaged-изменение при итоговой проверке относилось к плану GEO-1.

| Бывший блокер | Наблюдение на проверенном HEAD | Результат подмены только в памяти |
|---|---|---|
| Состав участников | Пустой набор проходит. Для недостающего и лишнего ref, дубля ref и дубля expectation тест подтвердил отказ до dispatch, входа в блок metadata и обоих CAS. | Удаление проверки привело к запрещённому dispatch во всех четырёх случаях. |
| World MISMATCH | При устаревшем world head и двух участниках caller получил конфликт мира. Число вызовов player CAS равно нулю. | При переносе обработки world MISMATCH за цикл тест обнаружил два запрещённых вызова. |
| Исключения из player CAS | Перед инъекцией на p2 тест прочитал новый head p1 внутри writer-транзакции. За её границу вышел исходный экземпляр PublicationInfrastructureError либо CancelledError. Peer подтвердил полный откат в обоих случаях. Отмена инъецирована на границе вызова второго CAS. | Преобразование исключений в CONFLICT сломало оба сценария. |

При обратном порядке refs каждый CAS получил expected head и ref своего игрока, выданный writer scope и operation_id. При успехе второе соединение увидело Q, оба новых player heads, world/player metadata и три маркера handlers. При реальном MISMATCH на p2 после успешного CAS p1 caller получил CONFLICT с путём `("expected_players", "p2")`. Второе соединение увидело прежний world head, оба исходно пустых player heads и отсутствие новых metadata и маркеров. Handlers контролируемые, history, CAS и rollback выполняет SQLite. Позиционное сопоставление refs, пропуск последнего CAS и игнорирование второго MISMATCH по отдельности привели к падению теста.

| Свежий прогон из backend | Результат |
|---|---|
| `../.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests tests.snapshotCore.contracts.test_typing` | 3 теста, OK, 19,434 с |
| `../.venv/Scripts/python.exe -B -m unittest discover -s tests/snapshotCore -p "test_*.py"` | 165 тестов, OK, 1 пропущен, 140,015 с |

## Первое ревью

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
