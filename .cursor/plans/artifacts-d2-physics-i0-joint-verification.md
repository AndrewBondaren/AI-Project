# Совместная техническая приёмка Artifacts D2 и подготовительного Physics I0

8 ноября 2026 года. Checkout `c1e7408bd9008519650837a1c789b2314a60fd2b`, Windows, cwd `backend`, проектный Python из `.venv`. Предмет приёмки ограничен локальными контрактами D2, подготовительным I0 и общей маршрутизацией. Production activation, DAG execution correlation и World/Snapshot binding находятся за его пределами.

## Исходные свидетельства

[Отчёт Artifacts D2](./world-domain-artifacts-d2-verification.md) указывает HEAD `4ed02d60` и результаты 143 адресных, 22 logging, snapshotCore 176/0/0/1, positive 0, negative 54 EXPECT. Сам отчёт и новый GC-тест вошли в следующий коммит `371e8044`. [Отчёт Physics I0](./physics-i0-report.md) первоначально фиксировал 79 профильных и 16 route-тестов с исключением GC. Та же оговорка сохранилась в [P3.22](./physics-spatial-dynamics.md#p322--результат-подготовительного-i0-2026-11-07). Позднее в `a2afe469` в отчёт I0 добавлен результат совместного прогона 40/40 за 1.582 с, включая GC. SHA исполнявшегося рабочего дерева там не указан. Эта запись подтверждала четыре перечисленных модуля.

## Итог после исправления архитектурного теста

**Artifacts D2 — ACCEPT. Подготовительный Physics I0 — ACCEPT. Совместная маршрутизация — ACCEPT.** На рабочем дереве `c1e7408b` уточнены разрешённые импорты публичного logging API для двух emitter в тесте архитектурных границ. Изолированный тест прошёл. Контрольные подстановки в памяти подтвердили отклонение лишнего имени, wildcard, импорта модуля целиком и зависимости вне разрешённого emitter.

Повтор команд `snapshot` и `logging` из раздела воспроизведения дал **176 тестов / 0 errors / 0 failures / 1 skip** за 148.380 с и **28/28** за 1.239 с. Единственный skip — Windows возвратила WinError 1314 при создании симлинка в `test_symlink_escape_is_rejected`. Локальные логи — `backend/.tmp_snapshot_core/followup-0.log` (snapshotCore), `followup-1.log` (logging), `followup-2.log` (изолированный тест). Для Physics и общего прогона ниже приведены результаты до изменения теста.

## Исходы до исправления архитектурного теста

| Предмет | Решение | Результат |
|---|---|---|
| Artifacts D2 | **REVISE** | Адресный набор 149/149, logging 28/28. Positive Pyright 0 diagnostics (exit 0), negative 54 ошибки (ожидаемый exit 1), TypingGateTests подтвердил все EXPECT по файлу, строке и rule. Обязательный snapshotCore дал 176 тестов / 0 errors / 1 failure / 1 skip. |
| Physics I0, подготовительный | **ACCEPT** | Полный профиль из owning-отчёта 80/80 (исторически 79). Профиль logging/policy/typing/generation 24/24, второй набор P3.22 29/29, объединённый P3.21 72/72. Policy отдельно 15/15, file/generation 8/8, file/policy/typing 19/19. |
| Совместная маршрутизация | **ACCEPT** | Команда исторического совместного прогона 46/46. Проверка с единственным комплектом handlers и общим transcript прошла. |

По сравнению с 143/22/40 адресный, logging и совместный наборы выросли на шесть методов в tests.test_logging_routes (formatter, log root/request context, console queue, reconfigure/transcript, два Time route). Старый фильтр Physics с исключением GC также воспроизведён, 22/22. Решение опирается на полный прогон без этого фильтра.

**Воспроизводимое отклонение D2.** Команда `.\.venv\Scripts\python.exe -m unittest discover -s tests/snapshotCore -v`. Test ID `contracts.test_registry.SectionRegistryTests.test_application_ports_have_no_concrete_storage_or_service_imports`. Ожидался PASS и итог 176/0/0/1. Фактически FAIL на [assertFalse](../../backend/tests/snapshotCore/contracts/test_registry.py#L264) и итог 176/0/1/1 за 148.182 с. Тот же отказ воспроизведён изолированно командой `.\.venv\Scripts\python.exe -m unittest -v tests.snapshotCore.contracts.test_registry.SectionRegistryTests.test_application_ports_have_no_concrete_storage_or_service_imports`. Тест разрешает двум emitter импортировать logging и app.core.logLevel. В [snapshotLog.py](../../backend/app/application/worldSnapshot/logging/snapshotLog.py#L4) появился импорт UnknownLogConsumerError из app.core.logging.contracts (`e32b331b`). Тот же модуль импортирует [artifactLog.py](../../backend/app/application/artifacts/logging/artifactLog.py#L3). Проверка останавливается на Snapshot. Единственный skip — test_symlink_escape_is_rejected, на Windows недоступна привилегия symlink.

## Проверенные контракты

**Artifacts.** В адресном логе прошли все семь исходных сценариев из [таблицы D2](./world-domain-artifacts-cancel-gc-d1.md). В `ConcreteLeaseTests` это `test_cancelled_terminal_requires_released_holds_on_write_and_both_cancel_reads`, `test_corrupt_held_descriptor_is_infrastructure_failure` (ветка cancel), `test_implicit_caller_update_survives_rejected_cancel`, `test_terminal_write_refusal_rolls_back_hold_release` и `test_two_connections_cancel_while_owner_writes`. В `SqliteBlobLifecycleTests` прошли `test_cancel_drains_repeatedly_cancelled_placement_before_gc` и `test_gc_serializes_physical_delete_with_reserve_and_restart`.

`ConcreteLeaseTests.test_cancel_reason_survives_reopen_and_repeat` закрывает SQLite, открывает тот же файл без seed и сверяет recover с исходным terminal (reason REQUESTED). Повтор cancel с тем же fence возвращает равный результат без роста total_changes, неверный fence отклоняется. `tests.test_logging_routes.ServerRouteFileTests.test_real_gc_emitter_preserves_failure_in_file_and_transcript` прошёл отдельно (1/1 за 0.231 с) и в полных маршрутах. В artifactLifecycle.log и transcript ровно по одному GC_FAILED и GC_DELETED. Проверены исходный OSError(5) и кадр delete в одинаковых traceback, stage, operation_id и совпадение structured failure с DTO. После отказа удалён следующий кандидат.

**Physics.** Три метода `tests.physics.test_settings_logging.SettingsLoggingTests` проверили реальные physicsLog.log и world transcript, установку и reset request_id, вложенный world scope, отсутствие Physics в jsonValidation, единственную запись continuation при повторе в том же ResolveContext и повторную запись в новом контексте. Сравнены результаты и typed reports обычного вызова и collect_only для missing, zero, custom, invalid gravity, malformed и mixed input. В collect_only число записей не растёт, выбранный fallback сохраняется, следующий независимый вызов с нулевой гравитацией успешен.

**Совместная маршрутизация.** Дополнительно в одном процессе однократно установлен `setup_logging(profile="server")` с временным logs_dir. Под `request_id=joint-request` внутри одного `generation_world_log("joint-world")` вызваны настоящий ArtifactGarbageCollector с ArtifactLifecycleLog и дважды публичная Physics runtime operation с invalid gravity и общим ResolveContext. На границе delete первый ref получил OSError(5), второй успешно удалён. В artifactLifecycle.log прочитаны только две строки app.artifacts, в physicsLog.log одна строка Physics с выбранным 9.80665. Проверено полное равенство трёх JSON-записей доменных файлов соответствующим строкам одного transcript в порядке GC_FAILED, GC_DELETED, Physics fallback. Все три содержат joint-request. Первый вывод результата в консоль встретил ошибку кодировки cp1251 на символе ² после проверок. Повтор с UTF-8 завершился с кодом 0.

## Воспроизведение

Основная последовательность из `backend`, TEMP и TMP указывают на `backend/.tmp_snapshot_core`. Локальные логи имеют имена `joint-<метка>.log` в этом каталоге. Дополнительные профили Physics выполнялись с `backend/.test-tmp`.

```powershell
# target
.\.venv\Scripts\python.exe -m unittest -v tests.snapshotCore.storage.artifacts.test_leases tests.snapshotCore.storage.artifacts.test_staging tests.snapshotCore.storage.artifacts.test_gc tests.snapshotCore.storage.publication.test_atomicity tests.snapshotCore.contracts.test_models tests.snapshotCore.contracts.test_codec tests.test_logging_routes tests.test_generation_logging tests.snapshotCore.contracts.test_typing

# logging
.\.venv\Scripts\python.exe -m unittest -v tests.test_logging_routes tests.test_generation_logging

# snapshot
.\.venv\Scripts\python.exe -m unittest discover -s tests/snapshotCore -v

# physics
.\.venv\Scripts\python.exe -m unittest tests.physics.test_settings_policy tests.physics.test_settings_logging tests.physics.test_settings_core tests.physics.test_settings_typing tests.physics.test_codec_compatibility tests.test_generation_logging tests.planning.encoding.test_canonical_codec tests.snapshotCore.contracts.test_codec.CanonicalRequestCodecTests.test_raw_digest_is_shared_with_canonical_and_tile_hashing tests.errorContracts.test_import_issues tests.errorContracts.test_resolve_issues tests.errorContracts.test_typing tests.errorContracts.test_core

# joint
.\.venv\Scripts\python.exe -m unittest tests.physics.test_settings_policy tests.physics.test_settings_logging tests.test_logging_routes tests.test_generation_logging

# profile
.\.venv\Scripts\python.exe -m unittest tests.physics.test_settings_logging tests.physics.test_settings_policy tests.physics.test_settings_typing tests.test_generation_logging

# valid
node ../node_modules/pyright/index.js -p tests/typing/snapshotCore/pyrightconfig.valid.json --outputjson

# invalid
node ../node_modules/pyright/index.js -p tests/typing/snapshotCore/pyrightconfig.invalid.json --outputjson
```
