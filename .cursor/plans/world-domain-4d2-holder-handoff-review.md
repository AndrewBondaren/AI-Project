# Независимое ревью 4D2 — holder handoff

**CHANGES REQUIRED**, 2026-11-05. Проверен HEAD `b958c3086e0c8562255a2c0a7e86a98dcc8f3f4f` вместе с unstaged-изменениями сервиса, теста и плана. Единственный блокер относится к регрессионному тесту. На контрпримере текущая реализация сохранила все ожидаемые holds.

## Блокер — частичная передача operation holds

В успешном сценарии `a` назначен миру, `b` — игроку, а в `transferred` входят оба артефакта. Третий артефакт `leftover` отсутствует и в metadata, и в списке передачи. Поэтому тест допускает ошибочное расширение `transferred` всеми назначениями из metadata. [test_atomicity.py, строка 603](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L603)

Подмена только в памяти, которая добавляла в `transferred` все артефакты из metadata, прошла штатный тест. В дополнительном сценарии назначения остались прежними, а caller передал только `transferred=(a,)`. После commit второе соединение увидело у `b` и `SnapshotHolder(player)`, и исходный `OperationHolder(lease)`. На подменённом сервисе второй держатель исчез, и проверка упала.

**Критерий закрытия.** Закрепить частичную передачу в успешном сценарии. После commit со второго соединения проверить точные наборы держателей:

| Артефакт | Ожидаемые держатели |
|---|---|
| `a` | Только `SnapshotHolder(world)` |
| `b` | `SnapshotHolder(player)` и `OperationHolder(lease)` |
| `leftover` | Только `OperationHolder(lease)` |

## Проверенный путь

Сервис записывает все envelopes, затем передаёт порту holders исходный writer scope, fenced lease, назначенные world/player refs и явный список передачи. При отказе handoff либо отмене в player CAS второе SQLite-соединение видит прежние heads, отсутствие обеих новых metadata и сохранение трёх operation holds. В точке отмены внутри writer scope тест видит уже записанный world head и оба snapshot holds. Наружу выходит исходный экземпляр `CancelledError`. Артефакты подготовлены SQL-фикстурами, назначения переданы явно. [Сервис](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L43) · [Интеграционный тест](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L540)

| Проверка на момент ревью | Результат |
|---|---|
| `AssignedPublicationTests` + `test_registry` + `test_typing` | 17 тестов, OK, 29,399 с |
| Полный `snapshotCore` discover | 169 тестов, OK, 1 пропущен, 135,299 с |
| Адресный Pyright по сервису | 0 ошибок, 0 предупреждений |
| `git diff --check` по файлам среза | Прошёл |
