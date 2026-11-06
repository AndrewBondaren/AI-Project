# Physics I0 — подготовительный срез, 2026-11-07

Сверка §P3.21–22 и кода обнаружила уже подготовленные незакоммиченные I0
изменения. Они проверены и дополнены regression test и документацией.
Готовые D2/P2 не повторялись; поиск обеих input operations в backend/app
показывает только определения, production caller отсутствует.

Physics settings input → settings/reporting.py → logging facade →
physics/physicsLog.log; внутри generation_world_log та же запись поступает
в transcript своего world scope. Adapter не создаёт handlers, второй collector
или глобальную dedup policy. Concrete F01 сохраняется в ResolveReport,
selected default берётся из typed F07. Validation/collect_only не emit-ят.
DAG lifecycle принадлежит прежнему владельцу; execution IDs не выдумываются.

## Проверки

- 79 tests PASS: tests.physics.test_settings_policy, test_settings_logging,
  test_settings_core, test_settings_typing, test_codec_compatibility;
  tests.test_generation_logging; tests.planning.encoding.test_canonical_codec;
  tests.snapshotCore.contracts.test_codec.CanonicalRequestCodecTests.test_raw_digest_is_shared_with_canonical_and_tile_hashing;
  tests.errorContracts.test_import_issues, test_resolve_issues, test_typing, test_core.
- tests.test_logging_routes: 16 PASS, исключён существовавший до работы
  test_real_gc_emitter_preserves_failure_in_file_and_transcript (Artifacts GC).
  Общие запуски зависали именно на нём, остановлены. Чужой тест сохранён.
- Первый запуск с системным TEMP получил PermissionError sandbox при записи
  файлов. Успешные проверки выполнены с TEMP/ TMP = backend/.test-tmp.
- Настоящие handlers во временных каталогах проверяют содержимое Physics файла
  и transcript, request_id/reset, вложенную world isolation, отсутствие Physics
  событий в jsonValidation, request-local continuation dedup и повторные отказы.
- Emit/collect_only дают равные values/outcomes/typed reports. Missing, zero,
  custom, invalid gravity/default, None root, malformed int key, mixed refusal
  и последующая независимая обработка сохранены. D2 tests покрывают технические
  исключения/cancellation и P2. Runtime ветвления не изменены.

## Граница результата

Подготовительный I0 завершён. Полный общий test suite не объявляется зелёным
из-за указанного чужого зависания. Production activation, реальный DAG caller
и execution correlation, World/Snapshot/storage integration не выполнялись.
Пользовательская приёмка D2 остаётся открытой.

## Совместная проверка Artifacts / Physics — 2026-11-07

После объединения изменений выполнена команда из `backend`:
` .\.venv\Scripts\python.exe -m unittest tests.physics.test_settings_policy tests.physics.test_settings_logging tests.test_logging_routes tests.test_generation_logging`.
TEMP/TMP установлены в `E:/AI Project/backend/.tmp_snapshot_core`.
Результат: **40 tests OK**, 1.582s, без исключения GC-теста.
Оговорка выше о зависании общего logging-набора снята для этой команды:
настоящий GC emitter и Physics logging проверены в одном процессе.
Это не повтор полного snapshotCore и не production activation.
