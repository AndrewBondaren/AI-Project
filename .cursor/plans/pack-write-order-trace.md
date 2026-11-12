# Pack — порядок существующих записей и требования к переносу

Статическая сверка по поручению продолжить список Pack. Только Pack callers и используемый ими механизм очередности callback; реализации других доменов и DAG-ноды не меняются. Цель — сохранить старую логику. Это трассировка существующего порядка, не утверждение новых NodeId/deps и не отчёт о runtime тестах.

## Пакетный L0 light/full

Источники: `backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py::_materialize_l0_pack`, `worldMapBakeOrchestrator.py::bake_tiles`.

| Порядок | Существующее действие | Требование к передаче в публичный Pack |
|---|---|---|
| 1 | drain_persisted только при has_job_repo и background_drain_per_request > 0 | Предшествует coarse climate; не переносить скрытый drain внутрь prepare/write. Отдельный маршрут DAG сохраняет условие и результаты |
| 2 | bake_coarse | Готовый результат передаётся write_coarse_climate до замены locations index |
| 3 | write_locations_index | replace_locations_index до L0 tile writes |
| 4 | compose_light_grid, затем replace_region_index | Готовый полный region index заменяет предыдущий до sync grid. Full-only seam применяется producer до tile payload; Pack не вычисляет seam |
| 5 | sync_world_metadata | sync_grid_metadata до цикла tiles; last_l0_mode ещё не меняется |
| 6 | write_world_map_tile в порядке входного tiles | Каждый write получает результат предыдущего state; не сортировать tiles заново ради удобства DAG |
| 7 | manifest.bake_mode = bake_mode | set_last_l0_mode после цикла, включая пустой цикл |
| 8 | persist bake relief grades, затем fine climate по L0 policy | Сохранить эту границу. Не требовать fine для каждого tile и не переносить fine перед L0 writes |
| 9 | publisher.publish при наличии publisher | Финальная публикационная граница; новые prepare/activate не вкладывать в write-методы |

Light/full используют общий путь; различия production/policy не разрешают Pack выбирать алгоритм по mode. Исходный условный publisher не является доказательством готовой целевой activation-проводки.

## Один L0 tile

Источник: `worldMapBakeOrchestrator.py::bake_tile`. После готового compose выполняются replace_region_index → write_world_map_tile. В этом методе **нет** sync_world_metadata и присваивания bake_mode. Нельзя переносить сюда весь batch-маршрут или незаметно обновлять last_l0_mode. Необходимые исходные grid значения предоставляет прежний контекст вызова; их отсутствие не исправляется скрытым fallback внутри Pack.

## Detailed L2

Источники: `bake/detailed/detailedBakeRefine.py::refine_detailed_tiles`, `packDetailedBakeOrchestrator.py::_run`, `refine/fine/chunk/fineChunkRunner.py::refine_rects`, `fineChunkPersist.py`.

1. require_parent_light выполняется для **всех** plan.tiles до начала второго цикла refine. Это существующий предварительный барьер: отсутствие parent у позднего tile сейчас обнаруживается до первых L2 writes. Перенос проверки внутрь цикла меняет поведение частичного выполнения.
2. Во втором цикле tiles с пустыми rects пропускаются. Для них не вызывается ни runner, ни final recalc_wilderness_status. Нельзя вставлять пересчёт только потому, что tile присутствует в scope.
3. Внутри одного runner каждый непустой wilderness результат записывается через write_wilderness_chunk; старый commit_chunk включает provisional status. Отсутствие wilderness payload не создаёт пустой chunk и не удаляет базовый.
4. После завершения всех rect callbacks вызывается persist.finish: непустые накопленные location payload записываются через write_location_terrain; затем grade sidecars (tile, затем location по существующему порядку накопления); затем recalc counters. Grade merge остаётся producer-owned, Pack принимает полный результат. Нового промежуточного public save здесь не появляется.
5. Только после возврата runner вызывается final recalc_wilderness_status, если plan.expected_chunks_for_status не None. Это пересчёт **для текущего tile**, до перехода к следующему tile, не один общий пересчёт после всей работы.
6. После всех tiles fine climate выполняется только для location scope при detailed_include_climate_fine; затем persist_detailed_grades. Wilderness scope этого location-only fine прохода не получает.

Счётчики в целевом проекте вычисляются при завершении состава; этот внутренний расчёт не разрешает менять относительный порядок payload/status writes. Внешние границы full L0 → topology и detailed L2 → settlement materialize остаются ранее установленными требованиями; локальная трассировка перечисленных методов сама по себе не доказывает полную миграцию внешних callers.

## Параллельное вычисление не означает исходный порядок записи

Источник: `backend/app/application/worldData/materialize/shared/chunkComputePool.py::map_sync_with_callback`. При одном worker callbacks идут по исходному indexed_rects. При нескольких worker каждый run_indexed ждёт свой compute, затем захватывает callback_lock и вызывает on_result. Lock сериализует эффекты, но не сортирует их по idx. Только **возвращаемый список** ordered строится в исходном порядке; FineChunkRunner применяет persist внутри callback, до получения списка.

Следовательно, утверждение «старые параллельные writes всегда шли по исходному списку» неверно. Замена callback-пути на обход ordered results может поменять порядок накопления location cells/grades и последнее обновление при пересекающихся адресах. При миграции нужно сохранить существующее поведение либо доказать независимость конкретных эффектов; новый детерминированный порядок требует отдельно обоснованного изменения, а не считается технической деталью.

Принятое требование последовательного S0 → S1 → S2 сохраняется: Pack не объединяет два state, полученных от S0, и не выбирает результат по времени завершения своих вызовов. Источник порядка готовых producer results должен быть явно отражён в caller binding. Сериализация старых callback-эффектов и последовательная передача state — совместимые требования; универсальную сортировку между ними добавлять нельзя.

## Проверки переноса

- Batch empty tiles: region/grid/mode эффекты сохраняются в прежних местах; single-tile вызов не получает batch-only grid/mode writes.
- Отсутствующий parent у последнего detailed tile не допускает ранних L2 writes, если раньше срабатывал общий parent barrier.
- Empty rects не вызывают final status recalc; nonempty tile завершает location/grade writes до своего final recalc.
- Два результата одного адреса применяются последовательно; delayed callback не превращается без решения в ordered-list write.
- Fine climate соблюдает прежние scope/policy условия; coarse write не сбрасывает fine status.
- Ошибка промежуточного вызова не разрешает продолжить цепочку с частичным state или автоматически запустить prepare/activate.

Итог: карта обязательных порядков и условий предъявлена. Конкретные DAG bindings ещё проверяются при подключении; они не изобретаются здесь. Planning-интеграция остаётся отложенной и не блокирует этот Pack-срез. Runtime и SQL не менялись, тесты не запускались.
