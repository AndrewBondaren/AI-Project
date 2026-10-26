# Policy: schema migrations (мастер)

> **Статус:** active · **Действует пока** мастер **явно** не снимет правило  
> **Audience:** планировщик, агент, любые имплементационные планы

## Правило

1. **Все изменения SQL-schema** — только правка [`backend/app/db/migrations/0001_initial.sql`](../../backend/app/db/migrations/0001_initial.sql).
2. **Sync** dataclass-моделей в `backend/app/db/models/` в **том же изменении**.
3. **Запрещено** создавать отдельные файлы `0002_*.sql`, `0003_*.sql`, … и `ALTER TABLE` migration scripts.
4. После правки 0001: локальная БД — **recreate** (drop + restart / fresh apply 0001), не incremental migration.

## Почему

Pre-production: один canonical initial schema; без цепочки версий, пока продукт не в проде.

## Исключения

Только **явная** команда мастера: «можно 0002» / «снимаем правило single migration».

## Связанные планы

- [hydrology-pre-dag.md](./hydrology-pre-dag.md) — D HY-0a `MapCell.hydrology`
- [implementation-roadmap.md](./implementation-roadmap.md)

## TODO для agent mode

Продублировать в [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) § «Schema / migrations» (blocked in plan-only edits to `.mdc`).
