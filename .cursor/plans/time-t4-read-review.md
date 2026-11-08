# Ревью интеграционного чтения Time T4

8 ноября 2026. Проверено рабочее дерево по [списку файлов отчёта](time-t4-read-report.md), включая четыре untracked-файла Python. Основания проверки — [SN-TIME-READ](sn-time-read.md) и [§48 плана Time](time-domain.md). В общей SQL-схеме проверены две таблицы Time.

## Находки по убыванию серьёзности

1. **P1. Значение часов по закреплённой ссылке можно изменить.** На SQLite в памяти первое чтение через `make_time_reader(commits).read_pinned(P)` вернуло 0 секунд. В отдельной транзакции `UPDATE time_publication_states SET payload=?` записал валидную точку той же timeline с той же полной ссылкой P. Повторное чтение вернуло 11 секунд. Обе таблицы Time допускают обновление и удаление адресуемой строки. Для snapshot это также затрагивает все последующие snapshots, унаследовавшие ссылку на секцию. [0001_initial.sql:1461](../../backend/app/db/migrations/0001_initial.sql#L1461) · [требование неизменяемости](time-domain.md#L1211)

2. **P2. Повреждённая timeline head обычной публикации скрывается за штатным результатом.** В БД в памяти после принятия Q с head S отключён триггер защиты от обновления snapshot и изменена только сохранённая timeline S на другую timeline того же мира. С исходной Q вызов `read_current` вернул `TimePublicationConflict`, хотя новой публикации не было. С реконструированной ссылкой `read_pinned` вернул `SOURCE_UNRESOLVED`. Восстановление head сверяет operation ID, а resolver трактует отличие timeline как основание для чтения дочернего binding. Для обычного `SNAPSHOT_APPLY` нарушенная связь должна дать ошибку целостности. [worldPublicationStore.py:66](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py#L66) · [acceptedStateReader.py:49](../../backend/app/application/worldSnapshot/service/acceptedStateReader.py#L49)

3. **P2. Две проверки проходят и при неверной реализации чтения.** После проверки существования initial binding реализация могла бы вернуть константный ноль для headless P. В тесте P ожидает ровно ноль, поэтому такая подмена значения пройдёт. Для неподдерживаемой версии v2 фикстура не записывает payload. Удаление проверки версии также оставит ожидаемый отказ из-за отсутствия строки. Отличить эти причины позволят ненулевая точка для headless P и существующий payload для v2. [test_snapshot_read_source.py:33](../../backend/tests/time/test_snapshot_read_source.py#L33) · [тот же файл:105](../../backend/tests/time/test_snapshot_read_source.py#L105)

4. **P3. В двух тестах пропущено сужение типа.** После `assertEqual` обращение к `first.publication` даёт три диагностики Pyright по вариантам отказа. В Snapshot-тесте результат `read_exact` типа `WorldPublicationRef | None` передаётся в `resolve_publication`. Если запись отсутствует, тест упадёт при обращении к полю внутри resolver. [test_snapshot_read_source.py:40](../../backend/tests/time/test_snapshot_read_source.py#L40) · [test_accepted_state_reader.py:65](../../backend/tests/snapshotCore/storage/publication/test_accepted_state_reader.py#L65)

## Проверенные пути и границы покрытия

Обе ветки фабрики возвращают `TimeReader`. Production-конструкция передаёт `SnapshotTimeReadSource` в параметр типа `ITimeReadSource`, что проверяет структурную совместимость выведенных типов результатов трёх методов. На каждый вызов источник открывает один read scope. От чтения публикации до payload передаётся одна `CommitReadScope`, включая заимствование capability в history. После resolver проверка `isinstance` сужает union до типа полного адреса для соответствующего payload reader. [factory.py:15](../../backend/app/application/time/composition/factory.py#L15) · [snapshotSource.py:38](../../backend/app/application/time/reads/snapshotSource.py#L38)

`read_current` различает отсутствующий мир и существующий мир без обязательной публикации. `read_pinned` сверяет полную публикацию до обращения по head. `read_historical` идёт прямо в историю. При наследовании загрузка использует исходный `SectionStateRef`, а capture содержит запрошенную ссылку. SQLite сверяет ссылку десериализованного payload с адресом, модели проверяют world и timeline точки. [snapshotSource.py:53](../../backend/app/application/time/reads/snapshotSource.py#L53) · [timeStateReader.py:17](../../backend/app/db/repositories/sqlite/timeStateReader.py#L17)

В тесте P/Q/S исходная транзакция чтения завершается до commit Q вторым соединением. Новые вызовы различают точки P (0 с, 0 нс) и Q/S (321 с, 123 нс), полные ссылки и конфликт current(P). Тест наследования обращается к дочернему snapshot при единственной строке payload у исходного S. Дочерний binding при head родительской timeline проверен с реальным SQLite payload reader и подставленной принятой публикацией. Spy проверяет общую capability и отсутствие чтения родительской секции. У helper `publish` параметры и callback не аннотированы, а `AsyncMock` без spec принимает произвольные сигнатуры. Эти фикстуры сами по себе не доказывают статическую совместимость портов. [test_snapshot_read_source.py:38](../../backend/tests/time/test_snapshot_read_source.py#L38) · [тот же файл:86](../../backend/tests/time/test_snapshot_read_source.py#L86) · [test_accepted_state_reader.py:15](../../backend/tests/snapshotCore/storage/publication/test_accepted_state_reader.py#L15)

## Команды и результаты

Тесты запущены из `backend` с доступом к временным файловым SQLite-базам.

| Команда | Результат |
|---|---|
| `../.venv/Scripts/python -B -m unittest discover -s tests/time -t .` | 50 тестов, OK |
| `../.venv/Scripts/python -B -m unittest discover -s tests/snapshotCore -t .` | 178 тестов, OK, один пропущен |

Pyright 1.1.414 запущен из корня репозитория с конфигурацией проекта.

```powershell
$files = Select-String -Path .cursor/plans/time-t4-read-report.md -Pattern '^- `(backend/.+\.py)`' |
    ForEach-Object { $_.Matches[0].Groups[1].Value }
node node_modules/pyright/index.js -p pyrightconfig.cascade.json @files
```

По всем десяти Python-файлам — 4 ошибки в тестах, 0 предупреждений. По восьми production-файлам из того же списка — 0 ошибок, 0 предупреждений.
