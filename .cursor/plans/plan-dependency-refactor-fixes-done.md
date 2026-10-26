# Фиксы ядра canonical-defaults engine (A-2) — ревизия 2026-10-09 ✅ DONE

> Родительский план: [`canonical-defaults-engine-done.md`](canonical-defaults-engine-done.md)
> шаг 2. Файл — журнал находок ревизии кода после имплементации шага,
> не новый план имплементации.

## Контекст

После сдачи шага A-2 (`backend/app/application/canonicalLibrary/` +
`tests/test_canonical_library.py`) проведена ревизия чистоты
ответственности и дублирования. Ниже — что было найдено и как закрыто.

## Исправлено

### F1 — `INSERT OR IGNORE` молча глотает non-identity нарушения

- **Найдено:** `INSERT OR IGNORE` пропускает не только конфликт PK/UNIQUE,
  но и NOT NULL/CHECK-нарушения — битая canonical-строка терялась бы
  silently при статусе `added`.
- **Фикс:** `INSERT … ON CONFLICT (uid_col) DO NOTHING` в
  `SqlCanonicalPersistence` — игнорируется только конфликт идентичности;
  прочие нарушения целостности → ошибка → rollback всего attach.
  Требование к uid-колонке: UNIQUE/PK-индекс; доменные UNIQUE-коллизии
  вне identity — ошибка, не skip.
- **Покрытие:** `test_insert_error_rolls_back_and_retry_works`.
- **Примечание:** та же оговорка зафиксирована в плане шага 2 и в
  docstring `CanonicalPersistenceAdapter`.

### F2 — doc-drift в `engine.py`

- **Найдено:** после F1 module docstring всё ещё ссылался на
  `INSERT OR IGNORE`.
- **Фикс:** формулировка приведена к `ON CONFLICT (uid) DO NOTHING`.

### F3 — разорванная транзакция check → insert

- **Найдено:** `SELECT existing` выполнялся вне транзакции, insert —
  внутри. Чужой DELETE canonical-строки между ними давал stale
  missing-set: UID попадал в `existing`, хотя строки уже нет
  (восстановление откладывалось бы до следующего ensure).
- **Фикс:** check+insert в одной транзакции — единый `_attach` внутри
  `db.transaction_on`; при внешней транзакции caller'а — участие без
  nested BEGIN/commit (`_in_transaction`, как в репозиториях).
- **Побочный эффект:** убрана двойная ветка txn-ownership с повтором
  `executemany_rows`.

### F4 — дубль вычисления uid-колонки

- **Найдено:** `uid_column or pk_col(model)` вычислялся в двух методах —
  потенциальный третий источник истины.
- **Фикс:** резолв один раз в `__post_init__` → `self._uid_col`
  (derived attr вне dataclass-полей; объявленное поле `uid_column`
  остаётся `str | None`).

### F5 — дыра в когерентности spec

- **Найдено:** global-spec молча принимал `identity_field` — поле для
  global-пути не используется (identity живёт на `CanonicalEntry.uid`),
  silent-ignore недекларативен.
- **Фикс:** `__post_init__` отвергает `identity_field` при `scope=global`.

### F6 — тестовая гигиена

- `assertRaises(Exception)` → `sqlite3.IntegrityError` в rollback-тесте.
- `CanonicalAttachResult` поднят в top-level импорты теста.

## Проверено и признано не нарушением

- Gate `scope`+`attach_policy` в `canonical_merge`/`ensure_canonical` —
  dispatch по полной паре, не дубль `__post_init__` (план допускает новые
  политики в рамках scope).
- `_check_snapshot` — контрактная проверка идентичности набора движком,
  не дубль доменной валидации адаптера.
- `dict(row)` копия canonical-строк — изоляция от мутации провайдера.
- Дубль `canonical_merge` ↔ `canonical_registry_wire` — временный,
  снимается делегацией в шаге A-3.
- `_attach_locks.setdefault` — throwaway `Lock` на вызов, косметика.
- `row[spec.identity_field]` на битой canonical-строке — голый
  `KeyError`; fail-fast на ошибке декларации домена, не user-input.

## Проверка

`python -m unittest tests.test_canonical_library` (cwd=backend) —
20/20 OK после всех правок.
