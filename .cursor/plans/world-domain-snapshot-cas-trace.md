# Snapshot D1. Конфликт публикации world/player

2026-11-05. Основание — [принятый D1 и база аудита](world-domain-snapshot-producers-audit.md).

## Контракт и момент наблюдения

[CAS-порты](../../backend/app/application/worldSnapshot/storage/publicationStore.py) возвращают прежний singleton APPLIED при успехе. На расхождении каждый порт возвращает свой тип фактов сравнения. [World store](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py) сравнивает все поля валидированной WorldPublicationRef и перечисляет различия в порядке объявления. Отсутствие обязательной world publication вызывает PublicationInfrastructureError. [Player store](../../backend/app/db/repositories/sqlite/snapshotCore/publications/playerPublicationStore.py) сохраняет полную PlayerHeadExpectation и фактический head. При пустой цепочке observed и publication равны None. При существующей строке identity публикации и операция взяты из той же строки, что и head. Identity операции-попытки отдельно проверяется по write scope.

[Сервис](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py) прикладывает к mismatch неизменяемую последовательность достигнутых CAS. Каждый шаг содержит operation_id, назначенную WorldPublicationRef или PlayerSnapshotRef с владельцем и решение. APPLIED перед MISMATCH означает запись внутри попытки. Вызывающий код перехватывает SnapshotCasConflict с категорией CONFLICT и полем trace снаружи transaction(). [Владелец транзакции](../../backend/app/db/repositories/sqlite/snapshotCore/commitScope.py) сначала завершает rollback, а при сбое rollback выдаёт UnknownCommitOutcome. Handler, вернувший SectionRefused, проходит через отдельную ветвь с исходным объектом.

## Проверки

- В [test_handlers_and_sqlite_cas_share_target_and_rollback](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py) subTest conflict отличается только publication_id. Trace содержит единственный world MISMATCH. Spy подтверждает ноль вызовов player CAS.
- В subTest player_conflict порядок фактических вызовов и trace совпадают: world APPLIED, p1 APPLIED, p2 MISMATCH с отсутствующим head. Участники сопоставлены по uid при обратном порядке назначенных refs. Второе соединение проверяет оба player head, world head, world/player metadata и markers всех обработчиков после rollback. В режиме refuse проверяется идентичность SectionRefused.
- test_existing_player_conflict_keeps_competing_publication_after_head_moves сверяет provenance существующего player head с SQL-строкой. После нового успешного тика через второе соединение прежний trace всё ещё содержит исходные expected, observed и provenance.
- [test_adapter_two_connection_cas_has_one_winner_and_durable_refusal](../../backend/tests/snapshotCore/storage/publication/test_cas.py) сверяет оба отличия мировой публикации (publication_id, pack_hash), попытку проигравшего и публикацию победителя.
- Адресный запуск AssignedPublicationTests и metadata builder — 7 OK, включая составной missing-base/receipt и metadata/handoff. Отдельный запуск гонки world CAS — 1 OK.
- Pyright 1.1.414: positive теперь выдаёт только reportCallIssue в artifactGc.py:47 (обязательный code). Обе диагностики сервиса из базы исчезли. Negative отдельно совпал с 51 EXPECT по файлу, строке и правилу.

## Сверка полного discover

В таблице имена методов приведены относительно указанного unittest-класса. ID двух CAS относятся к subTest одного метода.

| Класс | ID метода / subTest | Итог против базы |
|---|---|---|
| storage.publication.test_atomicity.AssignedPublicationTests | test_handlers_and_sqlite_cas_share_target_and_rollback (mode='conflict') | ERROR → OK |
| тот же | test_handlers_and_sqlite_cas_share_target_and_rollback (mode='player_conflict') | ERROR → OK |
| storage.artifacts.test_leases.ConcreteLeaseTests | test_cancelled_terminal_requires_released_holds_on_write_and_both_cancel_reads | ERROR cancel |
| тот же | test_corrupt_held_descriptor_is_infrastructure_failure (call='cancel') | ERROR cancel |
| тот же | test_implicit_caller_update_survives_rejected_cancel | ERROR cancel |
| тот же | test_terminal_write_refusal_rolls_back_hold_release | ERROR cancel |
| тот же | test_two_connections_cancel_while_owner_writes | ERROR cancel |
| storage.artifacts.test_staging.SqliteBlobLifecycleTests | test_cancel_drains_repeatedly_cancelled_placement_before_gc | ERROR cancel |
| тот же | test_gc_serializes_physical_delete_with_reserve_and_restart | ERROR cancel |
| storage.artifacts.test_staging.ArtifactStagingTests | test_gc_io_failure_cancellation_and_uncertainty | ERROR GC |
| contracts.test_typing.TypingGateTests | test_nominal_refs_keys_and_outcomes | FAIL positive, остался GC |

У семи cancel traceback ведёт к leaseStore.py:165, у GC — к artifactGc.py:47. Новый ID сверх базы — AssignedPublicationTests.test_existing_player_conflict_keeps_competing_publication_after_head_moves.

Итог полного discover из backend: 170 тестов за 146,544 с, errors=8, failures=1, skipped=1. В базе было 169 тестов, errors=10, failures=1, skipped=1. После проверки допустимых зависимостей DTO trace использует NamedTuple. Финальный адресный запуск с этой проверкой, metadata builder и AssignedPublicationTests — 8 OK.
