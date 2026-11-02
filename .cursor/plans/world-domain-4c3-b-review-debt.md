# Техдолг архитектурного ревью 4C3-B

Дата: 2026-11-02. Статус: **4C3-B-REV-1 CLOSED / RE-REVIEW PASS; B НА ПОВТОРНОЙ ПРИЁМКЕ ПОЛЬЗОВАТЕЛЯ**. Окончательная приёмка B и завершение debt-плана ожидают решения пользователя.

Источник: [owning-план, ревью актуальной 4C3-B](world-domain-patches-snapshots.md#архитектурное-ревью-актуальной-4c3-b--2026-11-02)
и принятый там handoff amendment. Исходная находка относится к `11891e1c`;
проверенная текущая версия исправления идентифицирована в повторном ревью ниже.
Фиксация техдолга не означает приёмку B или разрешение C/D, 4D2, production wiring.

## 4C3-B-REV-1 — P2: неполная проверка destinations до holder append

Место: [SqliteArtifactHolders.handoff](../../backend/app/db/repositories/sqlite/artifacts/holderStore.py),
проверки `planned`/`retained_refs` и последующий цикл acquire.

В исходной версии для всех metadata destinations (`planned`) заранее проверяется только sealed state.
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

При исходной фиксации исправление не выполнялось; последующее исправление и
evidence закрытия finding приведены ниже. Public ports/DTO/DDL, C/D, 4D2 и
production wiring не меняются.

### Закрытие 4C3-B-REV-1 — 2026-11-02

Перед изменениями сверены current holderStore и working diff: исполняемого
исправления не было, только TODO REV-1; чужие текущие изменения не затронуты.
Новый regression на исходном коде **FAIL**: после пойманного отказа и успешного
выхода caller UOW обнаружен лишний snapshot acquire для первого destination.

Исправление: handoff сначала проверяет sealed state и вызывает `_holders`
(валидация chains и owner hydration) для объединения **всех metadata refs и
retained_refs**, сохраняя checked projections в локальном typed dict. Затем
проверяет условия передачи retained_refs. Только после завершения обеих фаз
валидации начинается existing acquire loop, затем release loop. Mapping по
metadata, exact lease/fence и explicit retention owner сохранены. Никаких
новых UOW/savepoint/commit/rollback, public signatures или изменений scope
helper; caller остаётся владельцем borrowed transaction. TODO удалён.

Regression:
`SqliteArtifactBehaviorTests.test_corrupt_metadata_only_destination_refuses_without_appends_even_when_caller_commits`
в [test_gc.py](../../backend/tests/snapshotCore/storage/artifacts/test_gc.py).
Поздний B присутствует в metadata=(A,B), но отсутствует в retained_refs=(A,);
его root holder event_seq повреждён до 2. Caller ловит отказ, собирает facts
внутри UOW и успешно коммитит. Сравнение facts внутри и после commit с baseline
подтверждает **0 новых snapshot holds и отсутствие operation releases**;
оба исходных operation acquire events сохраняются. Отдельно проверяется,
что snapshot metadata действительно закоммичена: исправление не скрывает rollback.

Проверки на исправленной версии из backend: targeted `test_gc`, `test_leases`
и `contracts.test_typing` — **25 tests OK**; полный
`../.venv/Scripts/python.exe -m unittest discover -s tests/snapshotCore -p 'test_*.py'`
— **149 tests OK (1 skipped), 73.407s**, baseline 148 → +1.
Existing Pyright gate в этих запусках: **positive 0 / negative 50 EXPECT**.
Scoped diff --check — PASS. Ошибки IO/cancellation после начала записи всё ещё
требуют rollback внешним owner; prevalidation не является общей IO-atomicity.
**Finding закрыт исправлением и regression evidence; B предъявлен на повторную
приёмку, автоматически ПРИНЯТ/DONE не объявляется. C/D, 4D2 и production
wiring НЕ НАЧАТЫ.**

### Повторное ревью исправления REV-1 — 2026-11-02

**VERDICT: PASS, REV-1 CLOSED подтверждён актуальным кодом и новым запуском;
новых findings в исправлении не обнаружено. B НЕ ПРИНЯТ пользователем.**
Проверен working tree, включая существующий незакоммиченный fix/test diff,
а не только HEAD или прежнее evidence. SHA256 до/после нового прогона совпали:
holderStore.py `F7EFE924C9D36B280E4879F5FEA69B88C3C861AC0880E619D4DB4ECE52CF7362`;
test_gc.py `EE8806F32C961BC2BED4A23F9C1FAB0605B91F971CE816CA934BD8365AADF9D6`.

Трейс: handoff:245–248 проходит union(metadata refs, retained_refs), проверяет
sealed state и `_holders` для каждого ref. `_holders` → `_chain` проверяет
все события/ветки/sequence/predecessor, затем `_hydrate` разрешает owners
до фильтрации acquire facts. Этот путь read-only. Затем выполняются условия
передачи retained_refs; первый `acquire` расположен только на строке 266,
`release` — после завершения всего acquire loop. Mapping по metadata сохранён.
Все проверки/записи идут в том же bound caller scope; BEGIN IMMEDIATE внешнего
UOW исключает конкурирующее изменение chains между prevalidation и append.
В bind остаётся только set/reset binding; нового commit/rollback/savepoint нет.

Regression :311–347 действительно ставит валидный A перед повреждённым B в
metadata=(A,B), retained_refs=(A,), меняет B.root.event_seq на 2 и ловит именно
`PublicationInfrastructureError("invalid artifact holder chain")` внутри UOW.
Он сохраняет facts внутри scope, выходит из transaction нормально, затем читает
facts новым read scope. Обе выборки сравниваются с baseline; явно проверены
отсутствие snapshot events и сохранение обоих operation acquire facts без release.
Чтение snapshot metadata после commit подтверждает успешное сохранение caller
работы, а не скрытый rollback или подавление ошибки transaction.

**Новое evidence этого ревью:** из backend
`../.venv/Scripts/python.exe -m unittest tests.snapshotCore.storage.artifacts.test_gc tests.snapshotCore.storage.artifacts.test_leases tests.snapshotCore.contracts.test_typing`
— **25 tests OK, 35.821s**, включая regression, mapping/parent rollback,
retention и lease/chain cases; typing gate **positive 0 / negative 50 EXPECT**.
Прежние 149 tests не используются как доказательство текущей версии; полный
suite в этом повторном ревью не перезапускался. Scoped diff --check PASS.
Код/тесты в этом ревью не менялись; изменены только owning/review-debt документы.
Сохранена оговорка: IO/cancellation после начала записи требуют rollback внешним
owner. **B предъявлен на повторную приёмку; C/D, 4D2 и production wiring не начаты.**
