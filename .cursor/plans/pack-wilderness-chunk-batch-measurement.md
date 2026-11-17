# Pack B5: измерения batch wilderness writes

Дата: 2026-11-18. Матрица выполняется; итоговый вывод ниже будет заполнен по завершённым прогонам. Независимый PASS этим отчётом не объявляется.

## Воспроизведение

Из `backend`:

```powershell
.\.venv\Scripts\python.exe -B tests/spatial_pack/measure_wilderness_chunk_batch.py --sizes 1000 4000 16000
```

Опциональный `--output <path>` записывает JSONL. Без него результат выводится в stdout. Каждый случай запускается в отдельном дочернем процессе; `--case N MANY HEAVY REPLACEMENT` воспроизводит отдельный случай (флаги 0/1). Python 3.14.4, Windows 11 10.0.26200, AMD64; Pyright 1.1.414.

## Метод

- 24 случая: 3 размера × additions/replacements × one/many tiles × light/heavy.
- One: все N chunks в одном tile. Many: до 16 chunks на tile; T = ceil(N/16), то есть 63/250/1000 tiles. Уникальные входные адреса. Replacements заменяют artifact hash существующих chunks, сохраняя metadata values/usages.
- Light: пустые Source proof/usage. Heavy: по 2 captures с 1 object dependency каждый, как в durable payload proof, так и в каждом из двух metadata evidence slots. Planning пустой в обеих сериях. Это проверка вложенных Source данных и basis, не оценка всех возможных Planning graphs. Source DTO построены как fixture; внешняя authority/adoption не симулируется.
- Время: один непрoфилированный вызов `PackWildernessChunksInput(...)` и публичного `write_wilderness_chunks`, включая strict nested constructor validation, admission, transition и materialization результата. Fixture/база/входные items подготовлены до таймера. Построение самого публичного request НЕ исключено. GC включён, перед прогоном вызван collect.
- Память: Windows `GetProcessMemoryInfo.PeakWorkingSetSize` после timed call, до счётчиков. Это системный peak процесса, **включая imports и setup**, а не чистая allocation delta операции. Отдельно сохранены baseline working set, setup peak и retained working set после результата. Fresh process исключает влияние предыдущих случаев. Разность peak и baseline не выдаётся за точный объём allocations.
- Счётчики: отдельное исполнение того же request/service после timed call; cProfile считает owning checks/sorted. Обёртка BaseModel constructor делегирует исходному constructor без обхода validation и считает только прямые создания из transition. Она действует только во втором прогоне и снимается после него. Не используется для времени/памяти. Производственный код не инструментирован.
- Пробные calibration-прогоны с tracemalloc и line/opcode tracing исключены из основной серии: стоимость инструмента существенно меняла исполнение, а line events не равны materializations. Отдельный пробный heavy 4 captures × 4 dependencies на 1000 additions/one tile дал 15.906701 с и 378.156 MiB OS peak; он не участвует в сравнении основной heavy серии.

## Объёмы и критерий

U содержит N parts, 2N evidence slots. R содержит N parts, N chunk rows, T tile rows, N+T descriptions и суммарно N basis addresses. При additions база пуста; при replacements B имеет те же количества, что R. В heavy U содержит 6N object-dependency occurrences (payload proof и два slots); B/R содержат 6N+2T occurrences (parts, chunk groups, tile identity). Это логический объём обхода, не число уникальных Python objects или heap bytes. Basis в one tile растёт до 16000 адресов.

Static trace: локальные индексы parts, tiles, chunk membership, descriptions и stored bindings строятся до item-loop. Каждый item обновляет свой part/chunk и группы; полный basis не строится в item-loop. Финальный цикл затронутых tiles сортирует membership и создаёт basis; state собирается после него. Полные validation-проходы фиксированы относительно N, но не равны одному физическому обходу. Конструкторы и owning leaf validators включены в counters.

Sorting предъявляется отдельно: для одного tile сортируется N координат; для many — до 16 на tile. Ожидаемая стоимость O(B+U+R) плюс canonical sorting и owning leaf checks относится к фиксированной форме вложенных данных, а не к произвольной тяжести proof. Последовательность N публичных single writes остаётся другой нагрузкой и не получает эту гарантию.

## Проверки кода

115 preparation unittest прошли. Целевой Pyright production Pack, тестов B1–B4 и harness: 0 ошибок/предупреждений. Расширенный `tests/spatial_pack`: 39 файлов, **473 ошибки, 0 предупреждений**; существующий долг за пределами этого среза не исправлялся. Массовый срез не означает чистоту всех тестов проекта.

Git diff в окружении недоступен: `fatal: this operation must be run in a work tree`. Файлы среза читаются напрямую; это ограничение проверки diff, не доказательство его пустоты. Production Pack в B5 не изменялся.
