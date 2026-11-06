# PS-ERROR-1: подготовительный I0, 2026-11-07

Реализован scope §P3.22. Не production I0 и не пользовательская приёмка D2.

## Изменение

`application/physics/settings/reporting.py` — единственный emitter input facts через logger `app.application.physics.settings`. Input operations сохраняют исходные ветви и результаты; adapter пишет в existing ResolveReport и использует его continuation dedup. Общие JSON reporting/core не изменены. Logging facade маршрутизирует Physics в `logs/physics/physicsLog.log`; generation allowlist захватывает те же события внутри world scope. Собственных handlers, второго collector и production caller не добавлено.

Без raw input: code/type/location, применимый checked path, gravity arguments и selected default проецируются явно. Validation/collect_only тихие; missing/zero/valid тихие; fallback продолжает обработку с тем же default, mixed/structural input отказывает без fallback. Admission/fault/cancellation policy не менялась. Отказ не управляет сессией.

## Evidence

- До переключения: `tests.physics.test_settings_policy` — 15/15 PASS.
- Полный baseline §P3.21 (оба списка объединены) после переключения — 71/71 PASS, включая P2, typing, codec и propagation exceptions/cancellation.
- `tests.physics.test_settings_logging tests.test_generation_logging` — 7/7 PASS. Настоящие facade/file handlers: собственный sink, отсутствие событий в jsonValidation sink, совпадение события в transcript, request_id/reset, nested world isolation, continuation dedup. Проверены runtime/collect_only equality, validation silence, None/missing/zero/custom/mixed/P2 и независимый успешный вызов после отказов.
- После последнего изменения projection: `tests.physics.test_settings_logging tests.physics.test_settings_policy tests.physics.test_settings_typing` — 19/19 PASS.
- Existing route suite без постороннего `test_real_gc_emitter_preserves_failure_in_file_and_transcript` — 16/16 PASS. Этот параллельно добавленный Artifact GC тест зависал и в общем, и в отдельном verbose запуске; прогоны прерваны. Его код не менялся. Полный route suite PASS не заявляется.

Первый файловый запуск столкнулся с PermissionError системного sandbox temp; повтор выполнен с TEMP/TMP внутри workspace. Воспроизведение из backend:

```powershell
$env:TEMP = 'E:\AI Project\backend\.test-tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
.\.venv\Scripts\python.exe -m unittest tests.physics.test_settings_logging tests.physics.test_settings_policy tests.physics.test_settings_typing tests.test_generation_logging
```

Изолированное воспроизведение route regression, исключающее только зависающий чужой case:

```python
import unittest
suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_logging_routes')
selected = unittest.TestSuite(t for group in suite for t in group
    if 'test_real_gc_emitter_preserves_failure_in_file_and_transcript' not in t.id())
result = unittest.TextTestRunner().run(selected)
raise SystemExit(not result.wasSuccessful())
```

Production search вновь обнаружил только определения двух input operations. Execution correlation, activation, World JSON/storage cutover, Snapshot/CAS и пользовательская приёмка D2 остаются открытыми. Подготовительная цепочка доказана; общая route-проверка имеет указанное внешнее ограничение. Одна эмиссия в два sink не обещает exactly-once file delivery.


## Уточнение типизации event projection (2026-11-07)

Убран dict[str, object] из Physics adapter. Закрытые application projections для shape/field/gravity и fallback используют конкретные enum, ValidatedFieldPath, PhysicsGravityArguments и WirePart; fallback требует selected_default. В emitter передаётся сам typed PhysicsGravityDefaultApplied, а не optional float. Только logging boundary вызывает model_dump(mode="json"). Формат события и runtime ветви сохранены; file assertions проверяют path/arguments/code/default и отсутствие fallback полей у shape refusal. Policy/file/typing профиль после исправления: 19/19 PASS.
