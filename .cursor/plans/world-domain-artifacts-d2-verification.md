# Artifacts D2 verification — 2026-11-07

Scope: world-domain-artifacts-cancel-gc-d1.md D2-1…D2-4; HEAD 4ed02d60. Production activation не выполнялась. Повторной реализации готовых контрактов нет; единственная кодовая правка этого прохода — дополнительный тест в backend/tests/test_logging_routes.py.

## Review D2-1 / D2-2

D2-1: OperationCancellationReason.REQUESTED, lease producer, manifest 20018, текущий StoredTerminalCodec без legacy decoder. Адресные тесты покрывают reopen/repeat, stale fence, drain, rollback terminal write и запрет чужой ambient transaction. D2-2: concrete ArtifactGcFailure, GC report/event, create_gc_failure/emit_gc_failure, manifest 20019/20020/20140. Поиск IDs в backend/app показал только owning registrations. Catch остаётся OSError/ValueError; body exception сохраняет фазу, exception guard exit получает GUARD_EXIT; инфраструктурная неопределённость распространяется. deleted/retained и GC_DELETED фиксируются после выхода guard, success emit находится вне catch. Mismatch cause/failure отклоняется до sink; ошибка sink подавляется существующим facade. Расхождений, требующих runtime-правок, не найдено.

## D2-3

Закрыт пробел прежней проверки, которая вызывала logger напрямую. Новый test_real_gc_emitter_preserves_failure_in_file_and_transcript вызывает настоящий ArtifactGarbageCollector и ArtifactLifecycleLog; контролируется только storage boundary. OSError(5) возникает в delete, следующий кандидат успешно удаляется. Реальные временные artifactLifecycle.log и generation transcript содержат ровно один GC_FAILED и один GC_DELETED каждый. В обоих проверяются operation_id, world_uid=None, весь gc_failure (включая failure_id) против возвращённого DTO, исходный кадр delete / raise cause и одинаковый traceback. Message остаётся в exception, не дублируется в structured failure. Существующий тест проверяет изоляцию world scope.

Logging: 22 tests OK, 0.729s — backend/d2-3-logging.log. Локальный EC-I0 подтверждён; production binding readiness не заявляется.

Первый запуск нового теста с asyncio.run завис на Windows socketpair в sandbox. Faulthandler evidence: backend/d2-3-probe.log. Прерванные logging/targeted прогоны не считаются результатом. Использован существующий tests.snapshotCore.support.fixtures.run_async (bounded selector polling); production loop/logging не менялись. TEMP/TMP: E:/AI Project/backend/.tmp_snapshot_core.

## D2-4 и baseline

Полный `python -m unittest discover -s tests/snapshotCore -v` из backend: **176 tests, errors=0, failures=0, skipped=1**, 166.818s. Evidence: backend/d2-4-snapshot.log. TypingGateTests прошёл: positive diagnostics=[], negative ровно 54 EXPECT с проверкой file/line/rule. Skip — test_symlink_escape_is_rejected: Windows symlink privilege unavailable.

Историческая база 170/8/1/1 → 171/8/1/1 добавила один зелёный rollback test (см. world-domain-snapshot-rollback-trace.md). Текущий результат 176/0/0/1: +5 к 171, +6 к 170. Git diff 0d86a5cb^..HEAD подтверждает пять новых методов: test_cancelled_terminal_uses_production_codec, test_cancellation_reason_is_strict_and_closed, test_cancel_reason_survives_reopen_and_repeat, test_gc_failure_contract_and_delivery, test_gc_failure_stages_and_event_admission. Семь cancel ERROR, один GC ERROR и positive typing FAIL устранены готовыми D2-1/D2-2. Новых падений нет. Новый logging test находится вне snapshotCore: logging 21 → 22, полный snapshotCore от него не растёт.

Runtime-инвариант: новых fallback/default/None условий, исходов операций и catch границ не введено. Продолжение независимого следующего GC кандидата проверено новым тестом; retained/retry/cancellation/uncertainty и cancel persistence проверены существующими тестами. Параллельные изменения physics и их routes в loggingConfig/generationLogging сохранены и не относятся к этому исправлению. Общий diff --check имеет чужие CRLF warnings; scoped check нашего теста и документов проверяется отдельно. Production composition, maintenance entrypoint, crash takeover и расширение scope остаются за пределами работы.


Итоговый адресный набор из §14 D2-4 (leases, staging, gc, atomicity, models, codec, logging routes, generation logging, typing): **143 tests OK, 117.371s**, backend/d2-4-targeted.log. Команда и cwd совпадают с планом. Scoped git diff --check для теста и документов PASS. D2-1…D2-4 локально завершены; пользовательская приёмка и production gates этим отчётом не закрываются.
