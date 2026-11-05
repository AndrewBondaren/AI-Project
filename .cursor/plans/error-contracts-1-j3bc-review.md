# ERROR-CONTRACTS-1 — независимое ревью J3b и J3c

**J3b — FAIL. J3c — FAIL.** Ревью от 2026-11-05 выполнено на `cb6effadb5c13a6367f850cd537efb7545466cd7`. Рабочая копия кода и тестов J3 на момент проверки совпадала с HEAD. Основание — [§6.1 owning-плана](error-contracts-1.md#L939).

## Дефекты, воспроизведённые на исходной ревизии

1. **P2 · R-J3b-5.** Вызвать `_index_issue` с `model=WorldClimateScalars` и `path=('wrong_column',)`. Колонка отсутствует в зарегистрированных `world_keys`, поэтому по контракту ожидается `RuntimeError`. Фактически возвращается `WireShapeIssue` с адресом `('wrong_column',)`. Для `multi_column` значение `offset` равно нулю, и проверка принадлежности колонки пропускается. Воспроизведено прямым вызовом helper. [index/validate.py:36–46](../../backend/app/application/jsonValidation/index/validate.py#L36)
2. **P2 · J3c, общий mapper.** Передать в `preflight.validate_rows` строку модели с полем `values: dict[str, int]` и значением `{"function-main": "bad", "is-instance[custom]": "bad"}`. Pydantic выдаёт две ошибки `int_parsing`. Ожидаются адреса `('rows', 0, 'values', 'function-main')` и `('rows', 0, 'values', 'is-instance[custom]')`. Mapper фильтрует оба ключа по префиксу. В итоговом отчёте остаётся одна ошибка по `('rows', 0, 'values')`. [resolve.py:390–400](../../backend/app/application/jsonValidation/resolve.py#L390)

## Вердикты по реестру §6.1

Таблица фиксирует состояние на момент независимого ревью; повторная проверка исправлений приведена в конце.

| ID | Вердикт | Реализация | Проверка |
|---|---|---|---|
| R-J3b-1 | Исправлено | [resolve.py:370, 403](../../backend/app/application/jsonValidation/resolve.py#L370) | Общие mapper-функции используются callers. Прошли сценарии POJO, raw loc, alias и root model. Отдельный дефект wire loc приведён выше. |
| R-J3b-2 | Исправлено в J3b | [connectionGraph.py:1, 24, 45](../../backend/app/application/jsonValidation/bundle/connectionGraph.py#L1), [index/validate.py:1](../../backend/app/application/jsonValidation/index/validate.py#L1) | Проверены все четыре docstring. Исходники содержат символ `—`. |
| R-J3b-3 | Принятое поведение подтверждено | [connectionGraph.py:99](../../backend/app/application/jsonValidation/bundle/connectionGraph.py#L99) | Для nodes и edges отсутствие секции и пустой список допустимы. Для `null` и `{}` получен `EXPECTED_LIST` с точным адресом секции. |
| R-J3b-4 | Исправлено | [preflight.py:42](../../backend/app/application/jsonValidation/bundle/preflight.py#L42) | Принудительный `ReliefValidationError` в строке 0 дал `VALIDATION_ERROR` по `('bundle', 'rows', 0)`. |
| R-J3b-5 | Частично исправлено | [index/validate.py:36](../../backend/app/application/jsonValidation/index/validate.py#L36) | Для штатных путей сверены адрес и schema_id. Незарегистрированный POJO и чужая колонка вложенного slice отклонены. Открыт случай `multi_column` из дефекта 1. |
| R-J3c-1 | Исправлено | [regionIdentity.py:41](../../backend/app/application/worldData/masks/regionIdentity.py#L41), [types.py:80](../../backend/app/application/jsonValidation/types.py#L80) | Проверены доменный тип, wire-префикс и schema_id. Прошли 14 тестов региона. |
| R-J3c-2 | Передано в J4 | [worldBundleService.py:104, 127](../../backend/app/application/worldBundle/worldBundleService.py#L104) | По §6.1 владелец bundle pipeline — J4. Проверка сервиса входит в его приёмку. |
| R-J3c-3 | Исправлено | [worldBundleService.py:173](../../backend/app/application/worldBundle/worldBundleService.py#L173) | Принудительный Pydantic ValidationError из prepare_import преобразован в ImportValidationError с кодом `int_parsing` и адресом `['bundle', 'world', 'n']`. |
| R-J3c-4 | Исправлено для Relief | [worldBundleService.py:190, 205](../../backend/app/application/worldBundle/worldBundleService.py#L190) | Section handler дал `VALIDATION_ERROR` по `('bundle', 'states')`. Ветка архива использует `LIBRARY_INVALID`. |
| R-J3c-5 | Условие завершения открыто | [§6.1, R-J3c-5](error-contracts-1.md#L1009) | Для закрытия требуются проверка чужой колонки в J3b и сохранение обеих причин с полными wire loc в J3c. |

## Запущенные проверки и границы

Прошли **70 тестов**: 39 в `tests/errorContracts`, 14 в `tests.test_region_identity` и 17 в `tests.test_import_validation_policy`. Проверены carrier admission, отклонение изменяемого состояния опубликованного отчёта, одноразовый iterable и полный loc удалённого wire-поля. Адресные пробы в таблице дополняли эти тесты. Полный backend-suite и отдельный аудит безопасности за рамками этого прогона.

## Оставшиеся проверки J4

1. После исправления повторить обе минимальные пробы. Для ошибочных ключей словаря дополнительно сверить две причины и оба полных адреса в preview и HTTP 422.
2. При итоговом вердикте J4 учесть результаты `test_import_validation_policy` на проверенной ревизии. Пройдены preview без записи и резервирования, повторная проверка после remap, rollback при ошибке записи и отмене, отдельный исход инфраструктурного отказа и HTTP-флаг. [Тесты импорта](../../backend/tests/test_import_validation_policy.py#L94)
3. На целевой ревизии отдельно подтвердить атомарность continuation с устаревшим source и HTTP-коллизию региона с rollback. Эти два сценария в данный прогон не входили. EC-11 принят, R-J4-1 имеет статус DONE. [Тест continuation](../../backend/tests/test_library_packs_4d.py#L121) · [Тест коллизии](../../backend/tests/test_declared_region_edit.py#L172)

## Повторная проверка после исправлений

- **J3b · R-J3b-5 — исправлено.** Принадлежность первого компонента пути проверяется по `world_keys` для всех видов slice. Регрессионный тест подтвердил `RuntimeError` для чужой колонки и прежние `loc` и `schema_id` для `precipitation_liquid`.
- **J3c · wire mapper — исправлено.** Resolver и preflight передают фактический вход проверки. Ключи словаря сохраняются даже при совпадении с формой служебной метки; добавлен также тест на реальные метки ветвей union. На HTTP-импорте проверено поле `weather_type_registry[0].need_modifiers`: preview вернул две причины `int_parsing`, HTTP 422 — тот же список с двумя полными адресами.
- До исправлений оба адресных теста упали по ожидаемым причинам. После исправлений прошли 42 теста errorContracts и 79 адресных тестов, включая rollback при HTTP-коллизии региона и атомарность continuation с устаревшим source. Оба замечания закрыты; итоговая приёмка J4 остаётся отдельным шагом.
