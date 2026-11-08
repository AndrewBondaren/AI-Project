# LOD-A0. Продолжение смены покрытия региона

Первый проверяемый потребитель — `StateChangeConsumer.evaluate`. Регион может оставаться лесом с уже накопленным прогрессом перехода в степь. Здесь можно различить доменный результат, незавершённый процесс и то, что наблюдатель видит на карте. В production метод вызывается при изменении декларации с `elapsed_ticks=0` и календарной меткой аудита. Положительный интервал сейчас передаёт тестовый caller. Автоматический выбор FAR/NEAR для региона отсутствует. [Caller деклараций](../../backend/app/application/worldData/regions/declaredRegionEdit.py#L57) · [Caller с длительностью](../../backend/tests/test_region_state_change.py#L146)

## Кто кому передаёт данные

| Producer | Передаваемое значение | Consumer и статус |
|---|---|---|
| Мир и редактор деклараций | terrain registry, default_landcover, spec, fingerprint, previous_entry_type | [Reconcile](../../backend/app/application/worldData/regions/declaredRegionEdit.py#L57) создаёт writer. Inertia, eligibility и threshold управляют переходом покрытия. Радиус наблюдения и частота LOD в этих параметрах не заданы. |
| Наблюдатели и настройки мира → предложенная общая LOD policy | Scope, требуемая проекция, точность расчёта и частота | По [плану §2–3](./lod-simulation-handoff.md) DAG принимает решение об активации и назначает вычисление. Сейчас caller прямо выбирает объём запроса и elapsed. |
| Time T4 | read_current с ожидаемой публикацией, read_pinned для конкретной публикации, read_historical для snapshot | [TimeReader](../../backend/app/application/time/reads/reader.py#L8) возвращает coherent capture либо типизированный исход. Устаревшее ожидание current требует перепланирования. На файловой БД после reopen проверены pinned P = 17 с + 8 нс и historical S = 321 с + 123 нс. Это отдельная [проверка T4](./time-t4-read-verification.md). Привязки RegionEvaluation к capture и конверсии в ticks пока нет. |
| Caller вычисления и сборщики фактов | UID, входные факты, elapsed_ticks, at, spec revision | [Evaluate](../../backend/app/application/worldData/regions/stateChange/consumer.py#L48) читает предыдущую строку, разрешает цель, передаёт strength и elapsed в [advance](../../backend/app/application/worldData/regions/stateChange/progress.py). |
| Домен регионов | current_type, pending_target, progress, last_eval_tick, history, fingerprint, overrides и tombstone | [Mapping](../../backend/app/application/worldData/regions/regionStateMapping.py) и [SQLite repository](../../backend/app/db/repositories/sqlite/regionStateRepository.py) сохраняют RegionState по миру и UID. Строка принадлежит домену и содержит continuation. MaterializeSignal возвращается caller при смене типа. |
| World Pack и region_states | Baked membership/UID плюс текущее покрытие | [MapCellQueryFacade](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py#L66) вызывает [overlay](../../backend/app/application/worldData/pack/read/regionStateOverlay.py#L37) под patch-слоем. L0 [light grid](../../backend/app/application/worldData/pack/bake/lightGrid/bakeContext.py) и [detailed refine](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py) готовят представления. Read не расходует интервал. |
| Snapshot и доменный writer, целевая граница T5 | Принятые изменения мира, continuation, точное время на одной publication | Snapshot владеет принятием ревизии над immutable Pack. Сегодня region_states читается по UID без publication pin. T4 позволяет читать принятое время, но не связывает upsert региона, последствия и advance часов одной транзакцией. Атомарная запись и восстановление на общей границе требуют T5 и согласования участия writer региона. |

## Выполненный сценарий

На временном файле SQLite применена штатная миграция. Использованы [registry, policy, request и климатический test provider](../../backend/tests/test_region_state_change.py#L34), реальный scorer, writer и новый экземпляр Database после закрытия. Вход постоянен — осадки 0, цель steppe, inertia леса 4, strength 1, общий маркер at=42. Единица опыта — входной tick региона.

1. Контрольный UID обработан одним батчем elapsed=4. Опытный UID в том же мире получил elapsed=2. В БД текущий тип forest, pending_target=steppe, progress=0,5.
2. На границе детализации тот же UID четыре раза спроецирован через overlay_terrain для чтения покрытия. Все четыре результата — forest. Выбран более частый расчёт с шагом 1. При самом переключении writer не вызывается.
3. Соединение закрыто. Через новую Database и новый repository прочитана строка и проверено полное равенство восстановленного RegionState промежуточному. Новый consumer выполнил два вызова elapsed=1.
4. Проверено равенство всех полей итоговых моделей за исключением заведомо разных UID. Итог — steppe, last_eval_tick=4, одна запись перехода и один materialize signal на последнем шаге. Это проверка смены cadence при одинаковых фактах, с чистой функцией проекции. Запуск DAG, фактический L2 read и доставка сигнала не входили в опыт.

Граница обобщения важна для выбора первого примера. Ветка spatial создаёт child UID по seed и начинает нового ребёнка с current_type родителя, без переноса накопленного pending/progress. Родитель при этом только увеличивает last_eval_tick. Если при progress=0,5 передать spatial и два тика, новый ребёнок накопит только 0,5, тогда как whole-region контроль уже перейдёт в степь. Это вывод из [ветвления evaluate](../../backend/app/application/worldData/regions/stateChange/consumer.py#L84). Такой split нельзя считать эквивалентным повышением точности.

## Два наблюдателя

Пусть A и B видят один UID на перекрывающихся участках, A запрашивает частый расчёт, B — редкий. Оба могут читать одну принятую версию. Текущий overlay делает собственный batch read на запрос, поэтому между запросами writer может изменить видимый тип. Два последовательных evaluate с elapsed=2 за один и тот же интервал дадут четыре тика вместо двух. Параллельный read-modify-upsert также допускает потерю прогресса при отсутствии внешней сериализации. Контракт [consumer](../../backend/app/application/worldData/regions/stateChange/consumer.py#L1) возлагает сериализацию на caller. Одна блокировка не распознаёт последовательный повтор интервала.

Критерий C1 для примера — одно вычисление для общего UID, исходной ревизии и интервала, два независимых чтения результата. Уход A может снизить частоту следующих вычислений. Удаление continuation и повтор последнего интервала изменили бы мир. Для stale/retry нужен проверяемый исход до применения effects.

## Вопросы на решение LOD-C1

- **DAG/settings.** Где объединяются требования двух observers и кто владеет правом обработать конкретный интервал? Как читатель получает принятую ревизию? Для [LS-T1–T9](../../docs/tz_lazy_simulation.md) остаются открыты EventBus, радиусы, cadence, NPC batch/unfold, дальние события, freeze клеток, overlap NPC и wiring климата. Значения этих политик из примера региона не следуют.
- **Time.** Какая длительность соответствует одному tick региона, кто хранит остаток при дробном интервале и какую конечную метку получает history при пересечении порога внутри батча?
- **Регионы.** Допустима ли смена только cadence при неизменных фактах? При пространственном split/merge кто переносит progress, историю, fingerprint и границы дочерних scope, и когда возвращать unsupported?
- **Snapshot/T5.** Как enlist region_states и доставку materialize effect в acceptance одной publication с Time, где проверять предыдущий pin и как отличать retry уже принятого интервала после reopen?
- **Spatial/Physics.** Каким публичным bounded read подтверждать покрытие на общей ревизии? Для водного потребителя нужны отдельные PH-LOD/PH-HANDOFF transform, баланс и допустимая погрешность. Проверка региона не устанавливает эквивалентность AGG/LOCAL воды. [Spatial](./spatial-distribution-domain.md) · [Physics](./physics-spatial-dynamics.md)
