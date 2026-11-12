# READY_INACTIVE — существующие удержания и остаток release

Статическая сверка 2026-11-12, без runtime/SQL правок и без запуска тестов. Связь: [Pack activation](pack-activation-refusal-trace.md), [ТЗ Pack](../../docs/tz_world_pack_storage.md), абзац «Удержания одинакового manifest — предложение владельцам Pack и Artifacts».

## Найденное переиспользование

`dataModel/artifacts/lifecycle/holders.py::OperationHolder` уже содержит OperationLeaseRef с operation_id/world_uid/kind/preparation_fingerprint/fence. В `SqliteArtifactHolders._key` identity operation hold включает operation_id и fence; identity ArtifactRetentionHolder — retained_artifact_id. Поэтому одинаковый manifest может иметь два разных operation hold, а его связь с одним ребёнком через ArtifactRetentionHolder общая. Эти две обязанности нельзя смешивать.

Existing tests подтверждают предусмотренную модель (здесь не перезапускались):

- `tests/snapshotCore/storage/artifacts/test_gc.py::test_two_connection_reserve_race_shares_one_identity_and_both_holds` — два reserve одного descriptor дают общий artifact_id и два OperationHolder.
- `test_ready_inactive_handoff_requires_explicit_existing_retention` в том же файле — payload передаётся ArtifactRetentionHolder(manifest), manifest сохраняет OperationHolder. Тест использует SNAPSHOT_APPLY claim, поэтому сам по себе не доказывает публичный Pack lifecycle.
- `tests/snapshotCore/storage/artifacts/test_staging.py::test_ready_inactive_handoff_obeys_outer_rollback_and_retention` — после Pack staging и claim выполняет handoff только payload и сохраняет terminal PackActivationResult(READY_INACTIVE); проверяет rollback, recovery через второе соединение и удержание payload при collect. Manifest не входит в передаваемый retained_refs и его operation hold не снимается.

`SqliteArtifactHolders._holders` не исключает operation holds по terminal phase. `SqliteArtifactCatalog.mark_deleted` запрещает GC при любом действующем acquire или живом writer. Следовательно, terminal сам по себе не освобождает manifest. `SqliteArtifactHolders.release` требует точный lease, закрытый admission и drained writers; `_lease(writable=False)` не требует PREPARING. Однако это низкоуровневый механизм, не публичная policy освобождения кандидата Pack.

## Что этим не доказано

`handoff` требует APPLYING, проверяет уже имеющихся владельцев назначения и снимает только перечисленные operation holds. Он не создаёт отдельного candidate owner. `leaseStore.cancel` при existing terminal возвращает record, не освобождая удержания; cancel не является готовым release READY_INACTIVE.

Снятие OperationHolder с manifest и снятие общих ArtifactRetentionHolder(manifest) с детей — разные действия. Освобождение кандидата A не даёт права снять общие дочерние связи, пока manifest нужен кандидату B, публикации, pin или history. Простой последовательный вызов release по refs не доказывает атомарность проверки последнего владельца относительно нового acquire/GC. Наличие двух operation holds в тесте reserve не заменяет проверку двух terminal READY_INACTIVE и их независимого release после restart.

## Вывод для Pack и внешняя граница

Необходимость нового holder kind/store не доказана: сначала проверить использование existing OperationHolder как удержания root manifest завершённого кандидата. Предложенный в ТЗ ключ (world_uid, activation_operation_id) не считать уже реализованным отдельным типом и не вводить его автоматически. Это результат трассировки, не принятие изменения owning Artifacts policy.

Pack-owned требование к будущему публичному release: адресовать конкретного кандидата/операцию и полный manifest ref, сверять durable identity/outcome, освобождать только его владение; повтор не затрагивает другого владельца и не переписывает terminal activation. Replay activation возвращает исторический исход и не создаёт удержания заново. Публичные Input/Output/Error release ещё требуют конкретизации по существующим типам; lease/fence не выдаются caller как способ управления storage.

Artifacts/publication должны предъявить принятый внутренний scoped binding: допустимость terminal operation hold как durable candidate root, проверка и снятие конкретного владения, правила освобождения общих дочерних связей, атомарность относительно acquire/release/GC, restart/replay. Pack не реализует второй holder ledger или собственный GC. До этого полная приёмка release остаётся OPEN, а найденные existing механизмы учитываются как база, а не заменяются новой системой.

Приёмочные сценарии: A/B с одинаковым manifest; release A сохраняет B и closure; повтор release A ничего не снимает у B; release B при наличии pin/history не разрушает версию; restart между terminal и release; race последнего release с новым acquire; rollback без частичной потери closure; replay activation после release не восстанавливает доступ. Runtime-гарантии этими требованиями не объявлены проверенными.
