# Независимое ревью 4D2 — передача assigned Q в handlers и world CAS

## Повторное независимое ревью после исправлений

**PASS** на 2026-11-04 для среза assigned Q / handlers / world CAS. Все четыре блокера первого ревью закрыты. Повторно проверен HEAD `8de6092f6db35f75240fcc0e7d36fcaae26b738a` вместе с рабочим деревом. Из относящегося к срезу изменены план и test_atomicity.py, оба файла пакета service и этот отчёт остаются untracked, индекс пуст.

Сервис один раз создаёт Q, контекст связывает её с expected P, назначенным snapshot, миром, активным timeline и pack. Каждый вызванный handler видит ту же Q. Реальный compare_append получает её после записи metadata. Транзакцией от begin до commit либо rollback владеет внешний commits.transaction(op). Контролируемые handlers сверяют ctx.scope по identity и вставляют отдельные marker rows через ScopedSqliteAccess.insert(ctx.scope, ...), который проверяет writer capability и получает соединение из реестра. History, CAS и rollback выполняет SQLite. Peer видит Q, metadata и все три маркера при успехе. При отказе секции, конфликте, ошибке или отмене peer видит прежний head и отсутствие новых metadata и маркеров. Исключения metadata инъецированы сразу после реального append внутри тела контекстного менеджера. Caller получает исходный объект исключения, CAS не вызывается.

| Подмена только в памяти | Наблюдаемый результат повторного ревью |
|---|---|
| Посторонний объект вместо выданного ctx.scope | Все пять сценариев упали на проверке identity scope |
| Вызов остальных handlers после отказа второй секции | Сценарий refuse упал на числе вызванных handlers |
| Потеря диагностики исходного SectionRefused | Сценарий refuse упал на сравнении полного отказа |
| Изменение сообщения CONFLICT | Сценарий conflict упал на сравнении полного отказа |
| Перенос CAS в finally вокруг yield | metadata_error и metadata_cancel упали на проверке отсутствия CAS |
| Равная по значению копия Q перед CAS | success и conflict упали на assertIs аргумента реального CAS |

Свежие прогоны из backend по командам ниже: AssignedPublicationTests + contracts.test_typing — **2 теста, OK**, 10,797 с. Полный snapshotCore discover — **164 теста, OK, 1 пропущен**, 125,545 с.

## Первое ревью до исправлений

**CHANGES REQUIRED** на 2026-11-04. Блокеры относятся к достоверности AssignedPublicationTests. В проверенной реализации WorldSnapshotService._apply_to_target нарушений контракта среза не обнаружено.

Проверен HEAD `8de6092f6db35f75240fcc0e7d36fcaae26b738a` вместе с рабочим деревом. На момент ревью в области среза изменены [план](world-domain-patches-snapshots.md) и [test_atomicity.py](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py). Просмотрены оба untracked-файла пакета service — пустой __init__.py и worldSnapshotService.py. Staged diff был пуст.

## Блокеры и критерии закрытия

Все четыре контрпримера воспроизведены независимыми подменами сервиса в памяти. Исходные файлы при экспериментах не менялись.

1. **Handler пишет в обход выданного scope.** При замене `scope=scope` на `scope=object()` в SnapshotApplyContext все три сценария прошли. Handler пишет через захваченный db.conn. History и CAS получают настоящий scope отдельно. Тест подтверждает rollback на общем соединении, но пропускает передачу негодной capability. Для закрытия каждый handler должен проверить `ctx.scope is scope` относительно scope внешней транзакции и выполнить проверяемую запись через адаптер, требующий именно ctx.scope. [test_atomicity.py, строки 362–364](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L362)

2. **После отказавшего handler нет следующей секции.** Подмена, вызывающая все оставшиеся handlers перед выбросом исходного отказа, прошла тест. Отказывает вторая из двух секций. Для закрытия оставить хотя бы одну секцию после отказавшей и проверить, что её handler не вызывался. Сохранить проверки отсутствия CAS и отката со второго соединения. [test_atomicity.py, строки 365–377](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L365)

3. **Проверяется только категория отказа.** Замена сообщения CAS-конфликта `world publication changed` на `wrong reason` прошла тест. При SectionRefused диагностика также не сравнивается. Для закрытия проверить исходный отказ секции либо его категорию и полную diagnostics. Для MISMATCH проверить CONFLICT и ожидаемые путь и сообщение FieldPathError. [test_atomicity.py, строки 391–394](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L391)

4. **Исключительный выход из записи metadata не покрыт.** Перенос CAS в finally вокруг yield прошёл тест, хотя при ошибке metadata такая версия вызовет CAS. Конечный rollback способен скрыть лишний вызов. Для закрытия после реального history.append отдельно инъецировать PublicationInfrastructureError и CancelledError. Проверить выход соответствующего исключения к caller, отсутствие вызова CAS, прежний head и имя мира, отсутствие assigned metadata со второго соединения. [test_atomicity.py, строки 379–392](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L379)

## Что подтверждено

Сервис один раз создаёт типизированную WorldPublicationRef с новым publication_id и назначенным snapshot_head. Мир, pack, active timeline и gameplay_started берутся из expected P. Модель проверяет принадлежность head миру. Контекст проверяет отличие ID от P, соответствие назначенному snapshot и сохранение активных pack и timeline. Один контекст с Q передаётся каждому handler. После metadata сервис передаёт ту же Q третьим аргументом SQLite CAS. Замена на равную по значению target.model_copy() уронила success и conflict на assertIs в строке 399. Проверка удостоверяет идентичность на входе адаптера. Внутри SQLite CAS перевалидирует аргументы, сравнивает сохранённую публикацию с P и при совпадении вставляет Q. [Сервис](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L38) · [Контекст](../../backend/app/application/worldSnapshot/contracts/context.py#L29) · [SQLite CAS](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py#L112)

Внешний execute входит в commits.transaction(op) до вызова сервиса. Координатор открывает транзакцию и выдаёт writer scope. Handlers выполняются до yield, caller пишет metadata в теле async with, сервис выполняет CAS после нормального возврата из yield. Commit и rollback принадлежат внешнему координатору. При SectionRefused сервис сразу поднимает _ApplyRefused с исходным отказом. При реальном MISMATCH наружу выходит _ApplyRefused категории CONFLICT с диагностикой world publication changed. Для обоих путей peer подтвердил прежний head и имя мира и отсутствие assigned metadata. Registry и handlers контролируемые. SQLite history, CAS, rollback и второе соединение реальные. [Координатор](../../backend/app/db/repositories/sqlite/snapshotCore/commitScope.py#L46) · [Проверки peer](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L395)

На исходной реализации отдельные инъекции PublicationInfrastructureError и asyncio.CancelledError сразу после успешного SQL append metadata исключили последующий CAS. В обоих случаях наружу вышло исключение исходного типа с контрольным сообщением, peer прочитал исходное имя мира w1.

## Прогоны из backend

| Команда | Результат ревью |
|---|---|
| `../.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests tests.snapshotCore.contracts.test_typing` | 2 теста, OK, 7,096 с |
| `../.venv/Scripts/python.exe -B -m unittest discover -s tests/snapshotCore -p "test_*.py"` | 164 теста, OK, 1 пропущен, 118,102 с |

Вердикт ограничен передачей assigned Q, world CAS и границей внешней транзакции. Публичный apply(), полный validation, player CAS, terminal/retry и production wiring относятся к последующим срезам.
