# F6. Совместная приёмка DAG + Pack

**Вердикт — ACCEPT.** На рабочем дереве с HEAD `8d6e6785187c41535ec352b5cd845d064d7b82cf` обе ветви прошли общую матрицу за 21,040 с. В момент исходного просмотра уже присутствовали изменения dagEngine.py и новый каталог invocations/interaction. Вход F5 подтверждён [независимым ревью](./spatial-f5-pack-review.md).

Тест запускает DAGEngine.run с группой из трёх child и тремя workers. В ветви FAILED child A бросает типизированную ошибку, пока child B держит физический stream shard. Родитель проверяет события группы и завершает исполнение ошибкой. В ветви COMPLETED родитель обрабатывает результаты группы и возвращает Text. Между сбоями закрываются соединения с dag.db и pack.db, заново создаются SQLiteExecutionStore, ExecutionPins и DAGEngine. Сбои внесены исключениями на границах операций. [Сценарии и точки инъекции](../../backend/tests/spatial_pack/test_execution_finality_reopen.py#L28)

| Точка сбоя | Наблюдаемое состояние DAG / Pack | Результат после reopen для обоих исходов |
|---|---|---|
| Перед записью intent | Последний checkpoint доступен, stop_intent отсутствует | Загруженный checkpoint равен исходному целиком. Resume доходит до записи intent ожидаемого типа. |
| После intent, перед close | Intent записан, read_closed возвращает None | Resume вызывает настоящий close, который фиксирует CLOSED. |
| После commit CLOSED с потерей ответа | DAG ожидает finalization, Pack выдал receipt вызывающей обёртке, которая прервала выполнение | Повтор close возвращает исходный receipt. Оба точных PinHolder сохранены. Чтение прежнего ref даёт PackClosed, счётчик новых физических open равен 0. |
| Перед finalize | CLOSED доступен, final_revision отсутствует | Resume завершает остановку при установленном запрете на CheckpointCodec.restore. |
| После commit finalized | Сохранён исходный intent, revision и final_revision равны stop_revision + 1 | Resume возвращает результат из сохранённого outcome, включая исходную диагностику для FAILED. |
| Посреди release | Первая транзакция сняла hold A, вторая прервана после вызова release внутри транзакции | Hold A отсутствует, hold B сохранён. Два цикла resume и cleanup возвращают тот же outcome, снимают оставшийся hold и сохраняют receipt. |

Тест регистрирует закрытие реального stream после выхода из файлового контекста и проверяет порядок stream closed → CLOSED → finalized → release A. Перед вызовом GC у общего shard остаётся единственный ArtifactRetentionHolder версии B. GC сохраняет root и shard, после повторного открытия OpenWaterBlobReader возвращает все 1913 исходных байтов. Ключевая проверка — `self.assertEqual(await reader.read_shard(shard, owner_b), expected_bytes)`.

## Воспроизведение

Из корня рабочего дерева в PowerShell:

```powershell
git status --short --branch
git diff HEAD
git rev-parse HEAD
cd backend
..\.venv\Scripts\python -B -m unittest -v tests.spatial_pack.test_execution_finality_reopen
cd ..
git diff HEAD
git diff --no-index -- /dev/null backend/tests/spatial_pack/test_execution_finality_reopen.py
git diff --check
```

Итог unittest — 2 из 2, OK. Код 1 у diff --no-index обозначает добавление файла. Изменения ограничены тестами и приёмочными документами F6.
