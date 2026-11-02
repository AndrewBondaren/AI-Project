# Техдолг архитектурного ревью 4C3-B

Дата: 2026-11-02. Статус: **OPEN / блокер приёмки B**.

Источник: [owning-план, ревью актуальной 4C3-B](world-domain-patches-snapshots.md#архитектурное-ревью-актуальной-4c3-b--2026-11-02)
и принятый там handoff amendment. Проверенная версия: `11891e1c`.
Фиксация техдолга не означает приёмку B или разрешение C/D, 4D2, production wiring.

## 4C3-B-REV-1 — P2: неполная проверка destinations до holder append

Место: [SqliteArtifactHolders.handoff](../../backend/app/db/repositories/sqlite/artifacts/holderStore.py),
проверки `planned`/`retained_refs` и последующий цикл acquire.

Для всех metadata destinations (`planned`) заранее проверяется только sealed state.
Holder-chain и owners проверяются через `_holders` лишь для `retained_refs`.
Однако snapshot holds приобретаются для всех metadata refs. Если holder-chain
позднего destination вне retained_refs повреждена, отказ возникает после
добавления holds предыдущих destinations. Borrowed scope не откатывается
адаптером: caller может поймать ошибку и закоммитить частичный результат.
Заявленное правило «все назначения проверены до записи» не выполняется.

### Воспроизведение и evidence

Actual disposable SQLite, existing `live_database`, `run_async`,
`artifactFixtures` и `unsafe_update`; probe выполнен через stdin:

1. Подготовить и seal артефакты A и B, закрыть admission, перевести операцию
   в READY и вызвать claim_publication.
2. Через unsafe_update изменить event_seq корневого holder B с 1 на 2.
3. В caller-owned publication transaction добавить snapshot с
   `metadata.retained_artifacts=(A,B)`.
4. Вызвать `handoff(scope, lease, (snapshot,), (A,))` и поймать отказ
   внутри caller scope; завершить caller transaction успешно.

Наблюдаемый результат:

```text
handoff refused: PublicationInfrastructureError invalid artifact holder chain
snapshot hold remains after refusal: True
snapshot hold committed: True
```

Полный suite текущей версии, запущенный заново из backend:
`../.venv/Scripts/python.exe -m unittest discover -s tests/snapshotCore -p 'test_*.py'`
— 148 tests, OK, skipped=1, 71.564s. Этот negative case suite не покрывает.
Existing parent rollback test доказывает rollback внешним owner, а missing
destination test — ранний отказ для retained_refs; оба не закрывают эту находку.

### Условия закрытия

- Предварительно проверить все destinations до любых holder appends,
  включая metadata refs вне retained_refs; сохранить metadata mapping,
  acquire-before-release, exact lease/fence и explicit retention owner.
- Добавить regression по сценарию выше: после пойманного отказа нет новых
  snapshot holds ни внутри caller scope, ни после его успешного commit;
  operation holds не освобождены.
- Сохранить caller ownership: без скрытого commit/rollback чужого scope.
  Ошибки IO/cancellation после начала записи по-прежнему требуют rollback
  внешним owner; prevalidation не является гарантией против всех IO failures.
- Повторить необходимые B tests и полный snapshotCore suite на исправленной
  версии, записать новое evidence и предъявить B на приёмку.

Исправление в рамках этой фиксации не выполнялось. Public ports/DTO/DDL,
C/D, 4D2 и production wiring не меняются.
