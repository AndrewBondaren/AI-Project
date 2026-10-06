# Техдолг тестов

## TEST-DB-1 — ручные копии SQL-схемы в тестах persist

**Статус:** открыт, отдельная задача. Зафиксирован 2026-10-06.

Три тестовых модуля создают `map_cell_patches` собственными функциями
`_map_cell_patches_ddl()`, вместо использования основной схемы:

- [`test_bootstrap_map_cell_writer.py`](../backend/tests/test_bootstrap_map_cell_writer.py:16)
- [`test_database_bootstrap_conn.py`](../backend/tests/test_database_bootstrap_conn.py:23)
- [`test_map_cell_persist_perf.py`](../backend/tests/test_map_cell_persist_perf.py:28)

Копии разошлись с контрактом: в них отсутствует `system_grade_uid`,
который есть в [`MapCell`](../backend/app/db/models/mapCell.py:33)
и [`0001_initial.sql`](../backend/app/db/migrations/0001_initial.sql:743).
Репозиторий формирует INSERT из полей объекта, поэтому восемь тестов
падают с `table map_cell_patches has no column named system_grade_uid`.
Подтверждение: [полный прогон P1](../.local/nl-payload-p1-tests.log).

**Решение:** создавать временные тестовые БД из основной
`backend/app/db/migrations/0001_initial.sql` через общий test helper;
удалить три ручные копии DDL. При необходимости подготовить валидные
parent/world fixtures для ограничений основной схемы. Сохранить проверки
записи, видимости между соединениями и транзакций.

**Критерий закрытия:** восемь тестов записи проходят на основной схеме;
ручных `_map_cell_patches_ddl()` в этих модулях нет. Добавление только
недостающей колонки в копии не закрывает этот техдолг.

Ошибка `test_save_pass_insert_only` про запрещённый wilderness terrain
persist — другая причина и в TEST-DB-1 не входит. Эта задача также не
входит в текущий план каскада и typed payload.
