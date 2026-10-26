# Library instantiate — общий механизм двух входов ✅ DONE

Дата: 2026-10-13. Статус: **done**, реализовано и проверено 2026-10-13.

Основание: архитектурное ревью `ea09865f` и согласованный итог обсуждения.
Нормативный контракт: [ТЗ](../../docs/tz_template_library_packs.md), §0.3/§2,
уточнение «Единый механизм инстанцирования» от 2026-10-13.
Контекст: [архитектура L-4](library-write-l4-architecture.md).
Завершённый [план исправлений L-4](library-write-l4-review-debt-done.md)
остаётся завершённым; эта работа — отдельное устранение повтора.

## Проблема и граница

В `backend/app/application/worldData/libraryPacks/writeFacade.py`
`LibraryWriteFacade.instantiate_negotiated()` и `instantiate()` повторяют
проверку non-default engine-источника и цепочку
`pack_request → writer.execute → require_result`. Изменение общего правила
потребует синхронной правки двух реализаций.

Два публичных входа оправданы: compatibility-вход переводит `confirm` в
selection и возвращает lifecycle preview; negotiated-вход принимает явные
decisions и возвращает policy outcome. Объединяется только общий механизм.
`LibraryPackService` сохраняет роль фасада. Wire-идентичность доменов
соответствует ТЗ; `authoringWrite` подключает POJO-валидацию через pipeline.
Изменение его зависимостей, адаптеров, batch API, field policies, transport
и `copy_pack` в эту работу не входит.

## Шаг 1 — выделить общую проверку и выполнение

- [x] В `LibraryWriteFacade` выделить приватную проверку допустимости
  источника: world-owned и default-паки отклоняются прежним
  `LibraryPackValidationError` с прежним сообщением.
- [x] Выделить общий приватный запуск `pack_request`, `writer.execute` и
  `require_result`, возвращающий `WriteResult | PolicyRequired` до адаптации
  результата. Не вызывать один публичный вход из другого: negotiated-вход
  уже преобразует `WriteResult` в `PackRemapResult` и теряет нужный legacy план.
- [x] Подключить оба входа к общим функциям. Сохранить порядок: проверка
  источника до `find_instance` в compatibility-входе; затем подготовка
  decisions и выполнение. Не переносить policy в фасад и не создавать
  альтернативную транзакционную границу.

## Шаг 2 — сохранить различия контрактов

- [x] Compatibility-вход сохраняет поиск существующего инстанса,
  построение REPLACE selection при `existing and confirm`, выбор preview
  с планом, `stale`, `applied` и fallback на `PolicyRequired`, когда плана нет.
- [x] Negotiated-вход передаёт decisions/token без изменений и возвращает
  `PolicyRequired` либо `PackRemapResult` через существующий `remap_result`.
- [x] Сигнатуры `instantiate_pack` / `instantiate_pack_negotiated`, UID,
  provenance, remap ссылок и форматы HTTP-ответов сохраняются.

## Шаг 3 — проверить поведение

- [x] Запустить существующие suites `test_library_packs_4b`,
  `test_library_packs_4c`, `test_library_write_api` из каталога `backend`:
  `$env:PYTHONPATH='.;tests'; & '../.venv/Scripts/python.exe' -m unittest test_library_packs_4b test_library_packs_4c test_library_write_api`.
- [x] Проверить покрытие обоих входов: первый import; повторный preview
  без записи; подтверждение с актуальным token; stale без записи; отказ
  для default/world-owned источника. В частности, переиспользовать
  `test_instantiate_gates`, `test_preview_diff_confirm_and_no_write_without_token`,
  `test_stale_source_and_pin_tokens_do_not_write` и
  `test_world_pack_instantiation_can_negotiate`.
- [x] При пробеле дополнить существующие сценарии проверкой результата и
  состояния хранилища. Не писать тесты на число вызовов приватных helpers.

## Приёмка

Общие проверка источника и запуск запроса имеют по одной реализации.
Оба публичных входа сохраняют прежние результаты, ошибки и отсутствие
записей при preview/stale/reject. Существующий inspector/policy/planner/
executor и доменные POJO остаются единственным pipeline операции.
После реализации отметить шаги и записать фактические результаты проверок.

## Результат реализации — 2026-10-13

В `LibraryWriteFacade` выделены `_require_instantiable_source` и
`_execute_instantiation`; оба входа используют их, сохраняя порядок
проверок, подготовку selections и прежнюю адаптацию результатов.

`test_instantiate_gates` дополнен проверками negotiated-входа для
world-owned/default источника и отсутствующего мира.
`test_world_pack_instantiation_can_negotiate` дополнен stale-сценарием:
изменение тела источника после preview возвращает 409 со `stale=true`,
членство и тела существующего инстанса сохраняются.

Проверка: три запланированных suites — **56 tests, OK**, 38.818 s.
Использовано корневое `.venv` с `PYTHONPATH=.;tests`: системный Python
не содержит зависимостей, а imports тестовых fixtures требуют `tests`
в пути поиска модулей. `git diff --check` — без ошибок.
