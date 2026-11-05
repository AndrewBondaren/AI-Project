# Snapshot 4D2. Producers после metadata/handoff

2026-11-05, HEAD `60f41b2f3b6f3c3859267fd6a188d45f294751d8`. В Snapshot изменены только тесты и их support. Решение владельца в [плане 4D2](world-domain-patches-snapshots.md) охватывает сбор причин metadata до append. Из оставшихся production-отказов ни один не попадает в этот D1.

## Воспроизведение

Из `backend`:

```powershell
../.venv/Scripts/python.exe -B -m unittest discover -s tests/snapshotCore -p "test_*.py"
../.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.contracts.test_typing
```

До правок — 169 тестов за 142,100 с, 36 записей ERROR, 1 failure typing, 1 skipped. Числа прошлой базы воспроизведены. ERROR включает subTest. В одном асинхронном тесте внешний traceback оканчивался timeout/ошибкой очистки временной БД, пока отдельная задача cancel уже упала. После явного ожидания завершившегося cancel и освобождения worker адресный тест показывает тот же конструктор в leaseStore.py:165.

После перевода fixtures полный discover — 169 тестов за 132,414 с, 10 TypeError, 1 failure typing и 1 skipped (symlink на Windows). Все десять TypeError дошли до production-конструктора: 7 cancel, 1 GC, 1 world CAS и 1 player CAS.

## Разбор исходных 36 ERROR

Число относится к первому caller в исходном запуске, даже если после починки fixture тот же тест обнаружил другую ошибку. Пути тестов ниже относительно `backend/tests/snapshotCore`. Все fixture-группы вне metadata D1. У тестового домена теперь свой конкретный `FakeTargetIssue` с enum и путём `FakeTarget.name`, построенным через CheckedPath. Его тип и владелец поля зарегистрированы в тестовом manifest. Это синтетические данные для проверки carrier/storage, без объявления production-семантики причины cancel или CAS.

| Первый caller и число ERROR | Ожидаемый исход, существующие типы | Минимальная проверка |
|---|---|---|
| [contracts/test_models.py](../../backend/tests/snapshotCore/contracts/test_models.py), `CoreModelTests._snapshot_dto_fixtures` ×7 | Общая fixture создаёт `SnapshotApplyResult(CONFLICT)` рядом с committed result. Падает до проверок DTO, даже в pregame/holder тестах. | `test_apply_result_category_commit_and_diagnostic_invariants`, матрица category/committed/diagnostics. |
| Там же, `test_section_refusal_is_typed_and_does_not_publish` ×1 и `test_patch_records_are_frozen_and_revalidate_nested_instances` ×1 | `SectionRefused` принимает конкретный field issue. Сохранены проверки категории, непустого tuple, frozen и strict revalidation. | Оба названных теста, восстановление конкретного типа по manifest. |
| [contracts/test_codec.py](../../backend/tests/snapshotCore/contracts/test_codec.py), `test_shared_diagnostics_roundtrip_and_runtime_enum_requires_explicit_owner` ×1 | `SnapshotApplyResult(REJECTED)` с конкретным issue восстанавливается с registered type ID. `ReferenceIssueContext` и `RuntimeIssueContext` проверяются отдельно, включая запрет незарегистрированного enum. | Названный тест, equality до и после decode. |
| [storage/artifacts/test_staging.py](../../backend/tests/snapshotCore/storage/artifacts/test_staging.py), `LifecycleFixture.cancel` ×6 | Fake возвращает `OperationCancelled` после drain. Устаревшая fixture блокировала release logging, recovery и вход в GC. | `test_stage_finish_and_ready_inactive_retention` и `test_gc_io_failure_cancellation_and_uncertainty` разделяют fake cancel и реальный GC. |
| [storage/artifacts/test_leases.py](../../backend/tests/snapshotCore/storage/artifacts/test_leases.py), `test_cancelled_terminal_requires_released_holds_on_write_and_both_cancel_reads` ×1 | Подготовка `OperationCancelled` для проверки запрета terminal с активными holds. После миграции тест проходит подготовку и доходит до production cancel. | Тот же тест с двумя соединениями. |
| [storage/publication/test_atomicity.py](../../backend/tests/snapshotCore/storage/publication/test_atomicity.py), `AssignedPublicationTests.test_handlers_and_sqlite_cas_share_target_and_rollback` ×9 | Один заранее созданный `SectionRefused(REJECTED)` останавливал все режимы до handler, metadata и CAS. Теперь 7 режимов доходят до ожидаемого исхода, 2 доходят до настоящего MISMATCH. | `success`, `refuse`, `conflict`, `player_conflict` в этом методе. |
| Там же, `test_adapter_world_player_history_and_outcome_commit_or_rollback_as_one` и `test_adapter_lost_commit_ack_quarantines_connection_and_recovers_terminal` ×1 каждый | Тестовые `SnapshotApplyResult(CONFLICT)` для проверки хранения и запрета перезаписи неизвестного исхода. | Оба названных метода с реальным codec и test manifest. |
| [storage/publication/test_cas.py](../../backend/tests/snapshotCore/storage/publication/test_cas.py), `test_adapter_two_connection_cas_has_one_winner_and_durable_refusal` и `test_adapter_preparing_is_busy_and_ready_claim_binds_request_once` ×1 каждый | Тест сам создаёт отказ записи. SQLite возвращает `CasDecision`, в первом тесте побеждает ровно один writer. | Оба метода, включая чтение terminal после гонки. |
| [leaseStore.py](../../backend/app/db/repositories/sqlite/artifacts/leaseStore.py), `SqliteArtifactLeases.cancel` ×6 | Реальный producer заранее конструирует `OperationCancelled` перед чтением fence, проверкой terminal и drain. Штатная отмена должна вернуть fenced record, stale fence дать ValueError, повреждённые данные — PublicationInfrastructureError. Тип `OperationCancelled` существует, его поле reason требует field issue, подходящей конкретной причины отмены в этом домене нет. | `test_two_connections_cancel_while_owner_writes` достигает конструктора даже при stale fence. `test_cancel_drains_repeatedly_cancelled_placement_before_gc` отдельно подтвердил ту же причину за ошибкой cleanup. |

Итого 30 исходных ошибок в тестовых данных и 6 из production cancel. После миграции fixtures остаются следующие четыре места в production.

| Файл и символ | Реальный доменный исход и минимум проверки | Отношение к D1 |
|---|---|---|
| [worldSnapshotService.py:117](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L117), `WorldSnapshotService._apply_to_target` | [SqliteWorldPublicationStore.compare_append](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py#L112) сравнивает полную `WorldPublicationRef` и возвращает `CasDecision.MISMATCH`. После выхода из yield сервис пытается создать `_ApplyRefused(SectionRefused(CONFLICT))`, но создание базового FieldPathError падает. Минимум — режим `conflict`, без player CAS, peer видит прежнюю публикацию. | После metadata, отдельное решение о публикации. Конкретного типа причины world conflict нет. |
| [worldSnapshotService.py:123](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L123), тот же метод | [SqlitePlayerPublicationStore.compare_append](../../backend/app/db/repositories/sqlite/snapshotCore/publications/playerPublicationStore.py#L62) сравнивает head с `PlayerHeadExpectation.expected_head`. В режиме `player_conflict` world и p1 уже записаны в текущем scope, p2 даёт MISMATCH. Ожидается CONFLICT с идентичностью p2 и откат world/p1, metadata и markers для peer. | После metadata. Конкретного типа причины player conflict нет. |
| [artifactGc.py:47](../../backend/app/application/artifacts/lifecycle/artifactGc.py#L47), `ArtifactGarbageCollector.collect` | После успешного fake cancel ошибка delete/OSError должна дать элемент `GcReport.failed`, пустой deleted и GC_FAILED. Неопределённость и отмена должны распространяться. `test_gc_io_failure_cancellation_and_uncertainty` теперь достигает настоящего producer. | Artifact lifecycle, вне metadata D1. `ArtifactRef` и `GcReport` существуют, отдельной конкретной причины failed candidate нет. |
| `SqliteArtifactLeases.cancel` выше | После миграции 7 ERROR в пяти тестах test_leases и двух test_staging. Дополнительный caller — тест с заранее подготовленным cancelled terminal. | Artifact lifecycle. Согласование причины отмены затрагивает сохраняемый outcome, отложено у границы terminal. |

## Typing и контроль handoff

Положительный профиль Pyright 1.1.414 — три `reportCallIssue` (GC:47 и service:117,123), все про обязательный code. Добавление одного code не исправит runtime: carrier запрещает прямой конструктор, а пустой или строковый tuple не является ValidatedFieldPath. Неинициализированная world publication в адаптере даёт инфраструктурный отказ ещё до CAS decision. У player пустой head допустим. Подмена этих исходов missing persisted metadata или ошибкой поля receipt потеряла бы причину. Gate останавливается после positive; отдельно запущенный invalid-профиль дал 51 ожидаемую диагностику, совпали строки и правила с EXPECT.

Отдельно повторены три теста из строки metadata/handoff owning-плана: builder, составной missing-parent/receipt отказ и `test_metadata_handoff_and_heads_share_outer_transaction` — 3 OK, 6,596 с. После commit peer видит у a world snapshot, у b player snapshot плюс operation hold, у leftover только operation hold.

## Предложение ближайшего scoped D1 — конфликт публикации в writer scope

Согласовать только две ветки MISMATCH в `WorldSnapshotService._apply_to_target`. Использовать локальный typed conflict с категорией CONFLICT и причиной одного из двух видов: world хранит уже переданную `WorldPublicationRef`, player — точную `PlayerHeadExpectation`. Вынести перенос такого отказа через rollback в отдельное внутреннее исключение Snapshot. Оставить `_ApplyRefused(SectionRefused)` для отказа domain handler. Сервис уже знает ожидаемые значения; повторное чтение актуального head или расширение SQL CAS для этого решения не нужны.

Приёмка в `test_atomicity.py::AssignedPublicationTests.test_handlers_and_sqlite_cas_share_target_and_rollback`: для `conflict` сверить полный world expectation и ноль вызовов player store; для `player_conflict` сверить p2 вместе с expected head, последовательность world → p1 → p2 и состояние до транзакции на втором соединении. Для `refuse` подтвердить прежний объект отказа handler. Повторить `test_metadata_handoff_and_heads_share_outer_transaction`, `test_missing_persisted_bases_preserve_independent_receipt_diagnostics`, `contracts.test_typing` и полный discover. Ожидаемая дельта этого D1 — минус два runtime ERROR и обе диагностики CAS; останутся GC и cancel. Это предложение для согласования. Реализация CAS, выбор формата persisted terminal, retry и интеграция Time в этом проходе не выполнялись.
