# Независимое ревью D1 — контрпример

2026-11-06, рабочее дерево на `d01cf073`. Сверены [принятый D1](world-domain-snapshot-producers-audit.md#принятый-scoped-d1--конфликт-worldplayer-cas-с-trace) и [отчёт реализации](world-domain-snapshot-cas-trace.md). Caller получает точную причину конфликта конкретной попытки. Единственное расхождение с запрошенной проверкой — видимость отката в самом trace.

## Воспроизведение

Из `backend` выполнить `python -m unittest -v tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests.test_handlers_and_sqlite_cas_share_target_and_rollback`. В subTest `mode='player_conflict'` посмотреть `error.exception.trace` после выхода из внешней транзакции. Тест зелёный и буквально проверяет следующую последовательность:

| Попытка | Участник | Назначенный snapshot | decision у caller |
|---|---|---|---|
| candidate | world w1 | candidate-world | applied |
| candidate | p1 | candidate-p1 | applied |
| candidate | p2 | candidate-p2 | mismatch |

В отдельном запуске снял эти значения при перехвате исключения у caller. `trace._fields == ('mismatch', 'steps')`, у шага есть только `operation_id`, `target`, `decision`. Ни у шага, ни у trace нет обозначения подтверждённого отката. Тип исключения и контракт внешней транзакции позволяют вывести судьбу записей. Однако при чтении самих шагов ранее успешные CAS имеют только статус `applied`. Это воспроизводит расхождение без сбоя базы. [DTO](../../backend/app/dataModel/worldSnapshot/results/publication.py#L48) · [сервис](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L124) · [проверки caller и второго соединения](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L441).

## Проверенные факты

- **World.** Сервис назначил `w1/t1/candidate-world` с новым publication ID и передал тот же target обработчикам и CAS. Для операции `candidate` полные expected/observed совпали с подготовленным ожиданием и исходным head соответственно. В обоих `world_uid=w1`, `snapshot_head=None`, `active_timeline_id=t1`, `gameplay_started=True`, `pack_hash='d' × 64`. Единственное отличие — `publication_id` из `stale-expectation` в `started`. Источник — публикация `started`, операция `start`. Единственный шаг — world mismatch. Оба игрока назначены, spy player CAS получил ноль await и список вызовов пуст. В гонке двух соединений адаптер перечислил `publication_id, pack_hash` и вернул provenance победителя. Store сравнивает все поля модели и берёт identity из строки сравнения в том же scope. Отсутствующая обязательная строка мира вызывает инфраструктурный отказ. [World store](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py) · [гонка](../../backend/tests/snapshotCore/storage/publication/test_cas.py).
- **Player.** При обратном порядке назначенных refs сервис выбирает цель по UID. После world и p1 реальный p2 CAS возвращает полное ожидание `PlayerHeadExpectation(player_uid='p2', expected_head=PlayerSnapshotRef(player_uid='p2', snapshot_id='stale'))`. Цепочка пуста, поэтому `observed=None` и `publication=None`. В отдельном сценарии ожидали пустой head, а получили существующий ref. Сверены полный ref и пара publication ID / operation ID из SQL. После следующего успешного тика через второе соединение текущий head изменился, сохранённые expected, observed и provenance совпали с исходными. [Player store](../../backend/app/db/repositories/sqlite/snapshotCore/publications/playerPublicationStore.py) · [проверка после смены head](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py#L490).
- **Rollback и отказ handler.** Peer после конфликта видит исходный world head, отсутствие обоих player head, metadata назначенного мира и игроков отсутствуют, все три marker-записи обработчиков отсутствуют. Положительный контроль видит результаты commit. В режиме refuse сохранён тот же объект `SectionRefused`, проверенный по identity; следующий handler и CAS пропущены. Владелец scope пропускает конфликт к внешнему caller после rollback, при потере подтверждения выдаёт `UnknownCommitOutcome`. [Владелец транзакции](../../backend/app/db/repositories/sqlite/snapshotCore/commitScope.py#L48).

## Повторные запуски

Адресно — 8 OK (AssignedPublicationTests целиком, гонка world CAS, metadata builder). Pyright 1.1.414: в positive единственный `reportCallIssue` в `artifactGc.py:47`, отсутствует аргумент `code`. В negative все 51 ошибки совпали с EXPECT по файлу, строке и правилу.

Полный запуск из `backend`: `python -m unittest discover -s tests/snapshotCore -v`. 170 тестов за 162,528 с. Относительно базы после исправления совпадают все восемь ERROR, один FAIL и Windows skip. В таблице ID читается как класс плюс метод.

| Класс | Метод / subTest | Результат в обоих прогонах |
|---|---|---|
| storage.artifacts.test_leases.ConcreteLeaseTests | test_cancelled_terminal_requires_released_holds_on_write_and_both_cancel_reads | ERROR cancel |
| тот же | test_corrupt_held_descriptor_is_infrastructure_failure (call='cancel') | ERROR cancel |
| тот же | test_implicit_caller_update_survives_rejected_cancel | ERROR cancel |
| тот же | test_terminal_write_refusal_rolls_back_hold_release | ERROR cancel |
| тот же | test_two_connections_cancel_while_owner_writes | ERROR cancel |
| storage.artifacts.test_staging.SqliteBlobLifecycleTests | test_cancel_drains_repeatedly_cancelled_placement_before_gc | ERROR cancel |
| тот же | test_gc_serializes_physical_delete_with_reserve_and_restart | ERROR cancel |
| storage.artifacts.test_staging.ArtifactStagingTests | test_gc_io_failure_cancellation_and_uncertainty | ERROR GC |
| contracts.test_typing.TypingGateTests | test_nominal_refs_keys_and_outcomes | FAIL positive |
| storage.artifacts.test_blob_backend.BlobBackendTests | test_symlink_escape_is_rejected | SKIP, Windows symlink privilege |

Все семь cancel дошли до `leaseStore.py:165`, GC — до `artifactGc.py:47`. Область изменений ревью ограничена этим отчётом и ссылкой из Snapshot-плана.
