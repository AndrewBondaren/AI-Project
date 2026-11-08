# Pack F5. Восстановление release после finalized

Вход для F6 готов на базах, созданных по обновлённой начальной схеме. Проверка использовала отдельные SQLite-базы DAG и Pack. Обновление существующей БД со схемой F3 этим прогоном не проверялось.

До первой правки выполнены `git status --short` и `git diff HEAD` с явными `--git-dir` и `--work-tree`. Исходный diff содержал только изменения в `.cursor/plans/spatial-distribution-domain.md` и `.cursor/plans/world-generation-plan-dependency-graph.md`. При итоговом просмотре появились параллельные изменения Time, в том числе отдельный блок таблиц в общей SQL-схеме.

## Контракт и результат

В F3 уже существовали durable CLOSED, точный PinHolder и привязка к namespace DAG. F4 предоставляет final_revision. [ExecutionPins.cleanup](../../backend/app/db/repositories/sqlite/worldPack/executionPins.py#L155) перечитывает checkpoint через привязанный store, проверяет intent и обе revision. В каждой Pack-транзакции сверяет CLOSED того же store_id, execution_id и stop_revision и обрабатывает один OPEN pin. Ключевой вызов внутри этой же транзакции — `await self._holders._release_pin(scope, row["manifest_artifact_id"], holder)`, за которым следует переход в RELEASED. Обычный release по-прежнему отвергает PinHolder.

В тесте восстановления первый release закоммичен. После записи holder event для второго pin выброшено исключение до смены состояния. После закрытия и повторного открытия обоих соединений первый hold отсутствовал, второй сохранился. Два последовательных cleanup оставили ноль OPEN, исходный receipt и чужой pin на том же manifest. Отдельно проверены недоступность DAG, отсутствие finalized, отсутствие CLOSED и другая stop_revision в CLOSED.

В fixture §15.101 последний hold на manifest A снят production-вызовом cleanup. После снятия дочерних holds A и прохода GC удалён manifest A. После reopen у root и shard остались точные holds B. Чтение B вернуло 1913 исходных байтов shard, SHA-256 `efc45c2be06b296c3190f3128aa657abda3858d978b2de5448d9eae0f68bb308`.

## Команды

Из backend итоговый прогон прошёл 17/17 за 90,843 с.

```powershell
../.venv/Scripts/python -B -m unittest -v tests.spatial_pack.test_pin_terminal_recovery tests.spatial_pack.test_manifest_pin_retention tests.spatial_pack.test_execution_pins
```

Из корня Pyright выдал 0 ошибок и 0 предупреждений.

```powershell
./node_modules/.bin/pyright.cmd --pythonpath .venv/Scripts/python.exe backend/app/db/repositories/sqlite/worldPack/executionPins.py backend/app/db/repositories/sqlite/artifacts/holderStore.py
```

Перед отчётом отдельно просмотрен `git diff HEAD -- backend`. Обычный `git diff --check` вернул 1 из-за CRLF в SQL и параллельных изменениях Time. Проверка `git -c core.whitespace=cr-at-eol diff --check` завершилась с кодом 0.

## Файлы, изменённые инструментом apply_patch

- `backend/app/db/migrations/0001_initial.sql` — состояние RELEASED и ограничения переходов pin и holder.
- `backend/app/db/repositories/sqlite/worldPack/executionPins.py` — проверка finalized и цикл cleanup.
- `backend/app/db/repositories/sqlite/artifacts/holderStore.py` — точный release под переданным scope и чтение события из журнала.
- `backend/tests/spatial_pack/test_execution_pins.py` — выделение общей fixture двух хранилищ.
- `backend/tests/spatial_pack/test_pin_terminal_recovery.py` — restart, replay и отказ при несовпадении подтверждений.
- `backend/tests/spatial_pack/test_manifest_pin_retention.py` — F5 release A перед GC и холодным чтением B.
- `.cursor/plans/spatial-f5-pack-evidence.md` — этот отчёт.
