# Независимое ревью T4 на 8d6e6785

Проверены [две находки по 29b29aec](./time-t4-read-review.md#повторное-ревью-коммита-29b29aec) и [исправление bda52ad2](./time-t4-read-report.md). Между исправлением и HEAD изменились только настройки Codex, скрипт проверки и план зависимостей генерации. До ревью в рабочем дереве были изменения dagEngine.py и новый каталог invocations/interaction/. Индекс был чист.

## P1 — исправлено для базы из актуальной 0001

На новом файле SQLite штатная миграция создала обе таблицы часов. Начальный current(P) при пустом head вернул 17 с 8 нс. Второе соединение приняло SNAPSHOT_APPLY Q с head S и временем 321 с 123 нс. Первое соединение прочло current(Q) и historical(S) с этим временем, а current(P) вернул конфликт с observed=Q.

Для P целевым существующим ключом служил Q, для S — следующий принятый snapshot. В обоих случаях передан валидный payload с новым адресом. При включённых триггерах выполнена исходная команда, где key обозначает publication_id или snapshot_id.

```sql
INSERT OR REPLACE INTO tab(rowid,key,payload)
SELECT rowid,?,? FROM tab WHERE key=?
```

Обе попытки дали sqlite3.OperationalError с текстом `table … has no column named rowid`. После закрытия обоих соединений файл открыт заново. Через make_time_reader нового координатора read_pinned(P) вернул исходный TimeCapture (17 с 8 нс), read_historical(S) — исходный HistoricalTimeCapture (321 с 123 нс). Сравнивались полные модели. Граница проверки — новые БД из [0001_initial.sql](../../backend/app/db/migrations/0001_initial.sql#L1461).

## P2 — исправлено

В отдельной файловой fixture принята Q с head S. После удаления триггера world_publications_no_update обновлена ровно одна строка Q, snapshot_head_id установлен в NULL. Вызовы read_current с исходной Q и read_pinned(Q) оба дали точный тип PublicationInfrastructureError и текст `invalid runtime publication transition`. Проверка обязательного head выполняется при восстановлении перехода. Легальная начальная P с head=None прошла контроль current и pinned с ненулевым временем в первом сценарии. [Валидация перехода](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationValidation.py#L36)
## Регрессии

Адресные test_values_after_commit_and_inherited_section и test_corrupt_snapshot_apply_head прошли (2/2). Через unittest discover из backend прошли Time (51/51) и SnapshotCore (178 запущено, один skip). Pyright с pyrightconfig.cascade.json по 11 Python-файлам из отчёта владельца вернул 0 ошибок, предупреждений и информационных сообщений.
