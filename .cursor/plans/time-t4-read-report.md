# T4 · Чтение принятого времени

На 8 ноября 2026 производственный путь доступен через `make_time_reader(commits)`, где commits — координатор Snapshot для этой БД. До среза TimeReader делегировал current и historical внедрённому источнику. Snapshot уже восстанавливал точные адреса, а Time определял типы payload. [Контракт чтения](./sn-time-read.md) · [Time §48](./time-domain.md) · [Snapshot](./world-domain-patches-snapshots.md)

Один вызов открывает read scope. Для current сначала проверяется последняя публикация мира. Для pinned проверяется полная сохранённая ссылка. Historical идёт непосредственно в историю. Когда Snapshot возвращает адрес секции, Time передаёт его в SQLite целиком и сверяет с десериализованным payload. Для начальной публикации или head родительской timeline адресом служит полная подтверждённая публикация. [SnapshotTimeReadSource](../../backend/app/application/time/reads/snapshotSource.py#L30) · [SqliteTimeStateReader](../../backend/app/db/repositories/sqlite/timeStateReader.py#L13)

```python
address = await self._accepted.resolve_publication(publication, CLOCK_SECTION, scope)
```

## Проверка

Файловая SQLite, два соединения. После чтения P исходная транзакция закрыта. Второе соединение сохраняет snapshot, секцию часов и публикацию Q в одной транзакции. Последующие обращения открывают отдельные транзакции. Проверяется полное равенство capture, включая world, timeline, ссылку и обе компоненты времени. [Интеграционный тест](../../backend/tests/time/test_snapshot_read_source.py#L25)

| Запрос | Проверенный источник | Результат |
|---|---|---|
| pinned(P) после Q | Initial binding P | P, 17 с и 8 нс |
| pinned(Q), current(Q) | Секция часов snapshot S | Q, 321 с и 123 нс |
| historical(S) | Та же секция S | S, 321 с и 123 нс |
| current(P) после Q | Последняя публикация Q | TimePublicationConflict(P,Q) |
| Следующий snapshot без изменения часов | Унаследованная ссылка на секцию S | Новая ссылка capture, 321 с и 123 нс |
| Head родительской timeline | Binding дочерней публикации, одна capability на разрешение и чтение | Timeline child, 57 с и 9 нс |

Последняя строка использует контрактную фикстуру принятой branch publication и настоящий SQLite payload reader. Отсутствие binding, секции или payload даёт SOURCE_UNRESOLVED, отсутствие исторического snapshot — SNAPSHOT_MISSING. Чужой world или timeline исторической ссылки вызывает ошибку целостности. На пути P/Q/S счётчик вызовов CalendarProjector.project равен нулю.

Из backend прошли обе команды, 50 и 9 тестов соответственно.

```powershell
../.venv/Scripts/python -B -m unittest discover -s tests/time
../.venv/Scripts/python -B -m unittest tests.snapshotCore.storage.publication.test_accepted_state_reader tests.snapshotCore.storage.publication.test_history
```

## Файлы, изменённые через apply_patch

### Повторная проверка после ревью

Исправлены четыре [находки ревью](./time-t4-read-review.md). SQLite запрещает UPDATE, DELETE и замену принятой строки в обеих таблицах часов. Чтение обычной SNAPSHOT_APPLY проверяет мир и timeline сохранённого head до возврата публикации. Регрессии проверяют все три операции изменения, ошибку целостности при current/pinned, ненулевое значение initial binding и отказ для существующего payload версии 2. В двух тестах добавлено явное сужение типов.

После исправлений Time — 51 тест, OK; полный SnapshotCore — 178 тестов, OK, один пропущен. Pyright по десяти Python-файлам из перечня ниже — 0 ошибок и предупреждений. Для запуска полного SnapshotCore из backend: `../.venv/Scripts/python -B -m unittest discover -s tests/snapshotCore -t .`.

В этой итерации через apply_patch изменены SQL-схема, worldPublicationStore.py, test_accepted_state_reader.py, test_snapshot_read_source.py и этот отчёт.

### Полный перечень среза

После повторного ревью 29b29aec обе таблицы часов в исходной схеме объявлены `WITHOUT ROWID`. Регрессия пытается заменить строку через её скрытый ключ с другим существующим внешним ключом и повторно проверяет capture P и S. При восстановлении SNAPSHOT_APPLY валидатор требует snapshot_head_id до сравнения полной ссылки. При повреждении этого поля current и pinned завершаются PublicationInfrastructureError. [Регрессии](../../backend/tests/time/test_snapshot_read_source.py#L69) · [Валидация перехода](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationValidation.py#L36)

Повторная проверка: Time 51/51, SnapshotCore 178 (один skip), Pyright по 11 Python-файлам — 0 ошибок и предупреждений. Четыре файла этой итерации изменены через apply_patch: 0001_initial.sql, worldPublicationValidation.py, test_snapshot_read_source.py и этот отчёт. Изменение исходной схемы применяется при создании БД. Для существующих БД с уже зарегистрированной версией 0001 автоматическое обновление таблиц не предусмотрено.

- `backend/app/application/time/composition/factory.py`
- `backend/app/application/time/reads/reader.py`
- `backend/app/application/time/reads/sourcePort.py`
- `backend/app/application/time/reads/snapshotSource.py`
- `backend/app/dataModel/time/storage/state.py`
- `backend/app/db/models/timeStates.py`
- `backend/app/db/migrations/0001_initial.sql` (две таблицы Time)
- `backend/app/db/repositories/sqlite/timeStateReader.py`
- `backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py`
- `backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationValidation.py`
- `backend/tests/snapshotCore/storage/publication/test_accepted_state_reader.py`
- `backend/tests/time/test_snapshot_read_source.py`
- `.cursor/plans/sn-time-read.md`
- `.cursor/plans/time-domain.md`
- `.cursor/plans/world-domain-patches-snapshots.md`
- `.cursor/plans/time-t4-read-report.md`

До первой правки просмотрены git status и diff. Исходные изменения в spatial-distribution-domain.md и world-generation-plan-dependency-graph.md, а также параллельные правки Pack, включая отдельные строки общей SQL-схемы, принадлежат другим задачам. При итоговой проверке обычный git diff --check пометил CRLF как trailing whitespace. Проверка git -c core.whitespace=cr-at-eol diff --check прошла. Следующие самостоятельные срезы — запись времени с эффектами (T5) и создание ветки.
