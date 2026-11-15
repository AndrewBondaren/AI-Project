# Ревью реализации Pack preparation — 2026-11-15

## Вердикт и границы

Предъявленный локальный срез пока не принят: обнаружены два воспроизводимых дефекта. Это ревью реализации, не повторная приёмка плана, полного Pack или всего шага 3a.

Полный заявленный аудит всех связанных контрактов, deep revalidation и негативных сценариев не завершён; отсутствие других дефектов не утверждается. Нереализованные start/bind/prepare и внешние execution bindings не включены в findings как ошибки пяти реализованных методов. Структурная допустимость Source proof не считалась доказательством исполнения Source. Storage/READY и полная проверка конечного состава не возлагались на текущие pure-методы.

## Findings

### P1 — При записи теряется различие new/inherited; inherited принимается без базы

Места: `backend/app/application/worldData/pack/preparation/packPreparationService.py:115`, аналогично строка 82.

Воспроизведение: взять fixture `PreparationClimateWriteTests`, где `base_publication.pack_hash=None`, и вызвать `write_coarse_climate` сначала с `PackNewPartProvenance`, затем отдельно с `PackInheritedPartProvenance` и одинаковым вложенным provenance. Оба вызова успешны; результаты равны. Унаследовать часть из отсутствующей Pack-базы невозможно, но метод принимает это заявление и стирает его discriminator. `replace_locations_index` использует тот же механизм.

Последствие: следующий этап по возвращённому state уже не различит эти два заявления о происхождении. Это недостающая проверка реализованной записи и потеря admission-семантики, а не требование подключить Source или выполнять storage admission внутри pure-метода.

Нарушенное требование: сохранение значимых различий происхождения и раздельный admission новых и унаследованных частей.

### P2 — Структурная ошибка одного поля подавляет независимые смысловые проверки всего запроса

Место: `backend/app/application/worldData/pack/preparation/packPreparationService.py:96`; тот же шаблон используется на строках 37 и 63.

Воспроизведение: в корректном state продублировать `parts` по адресу; независимо подменить `part.artifact.nbytes` строкой через `model_copy`; запрос передать через `PackCoarseClimateInput.model_construct`. Получен только `SCHEMA_VIOLATION` по `part.artifact.nbytes`. Ошибка `DUPLICATE_ADDRESS` в структурно корректном `state.parts` отсутствует.

Причина: после общей неуспешной schema validation `checked=None`, поэтому все semantic checks пропускаются.

Последствие: отказ неполный, caller вынужден исправлять независимые нарушения последовательно.

Нарушенное требование: `.cursor/plans/pack-v2-public-write-operations.md:455` — invalid parent исключает зависимые проверки, но независимые поля продолжают проверяться.

## Выполненные проверки

- Прочитаны фактические файлы рабочего дерева, включая файлы вне HEAD; анализ не ограничивался diff. `git status` завершился ошибкой `this operation must be run in a work tree`, поэтому статус tracked/untracked не подтверждён.
- Из `backend` выполнено `.venv/Scripts/python.exe -B -m unittest discover -s tests/spatial_pack -p 'test_preparation*.py'`: 51 тест, все успешны.
- Pyright выполнен через установленный в проекте `node_modules/.bin/pyright.cmd`, с Python из backend `.venv`: 0 ошибок, 0 предупреждений для preparation-пакетов и четырёх указанных meta-модулей. Модуль Pyright в самой `.venv` отсутствует.
- Оба сценария findings проверены отдельными исполнениями без изменения файлов. Существующие зелёные тесты эти дефекты не выявляют.
- В просмотренных цепочках пяти сервисных методов не обнаружены IO, запуск генераторов или междоменная оркестрация. Их локальные вызовы валидатора сами по себе три запрета DAG не нарушают.

Команда Pyright из `backend`:

```text
../node_modules/.bin/pyright.cmd --pythonpath .venv/Scripts/python.exe app/dataModel/worldPack/preparation app/application/worldData/pack/preparation app/dataModel/worldPack/meta/parts.py app/dataModel/worldPack/meta/metadataAttribution.py app/dataModel/worldPack/meta/packCompositionFields.py app/dataModel/worldPack/meta/locationsIndexStorageFormat.py
```

Код, планы и тесты при ревью не изменялись; backend не запускался, коммиты не создавались. Этот файл сохраняет ранее выданный отчёт и не означает завершения оставшейся части аудита.
