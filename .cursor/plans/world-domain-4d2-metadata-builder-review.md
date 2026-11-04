# Независимое ревью 4D2 — metadata builder и scoped append

**Итог повторного ревью от 2026-11-05 — PASS.** Ревьюер проверил рабочее дерево с исправлениями поверх `ca159fc6`. Оба замечания повторного ревью закрыты. [Контрпримеры, результаты прогонов и границы проверки в разделе 4D2](world-domain-patches-snapshots.md#L2991).

## Исходное ревью

**CHANGES REQUIRED** · 2026-11-04 · HEAD `d031508ee225727be6a0f03231712c81c20df4c6`. Обычный путь второго тика прошёл проверку. Сервис теряет независимые ошибки секций при отсутствии persisted parent. Часть ошибок входа обходит доменную диагностику.

На момент ревью индекс и рабочее дерево были чистыми, untracked-файлов не было. Относительно принятого player CAS (`73994eae`) изменились builder, сервис, два тестовых файла и план. Проверен также вызываемый `receiptProvenance.py`, который не менялся в этом diff.

## Блокеры и критерии закрытия

1. **Сервис прекращает независимые проверки после чтения родителей.** При отсутствующей world-строке, чужом history в первой секции и artifact без назначения во второй caller получает только `PublicationInfrastructureError` с одной диагностикой. Полный протокол ниже. Закрытие требует сохранить инфраструктурную классификацию отсутствующей строки, собрать обе независимые ошибки секций и проверить отсутствие append в одном сервисном тесте. Для чтения POJO и получения имени поля в пути использовать общий типизированный селектор. [worldSnapshotService.py, строки 48–59](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py#L48)
2. **Часть типизированных ошибок обнаруживается после агрегации.** При `retained={world:(A,A), player:(A,A)}` caller получает Pydantic `ValidationError` только по world с сообщением `duplicate retained artifact`. При совпадении assigned world ref и pinned parent — `ValidationError` с сообщением `parent must be a different snapshot of this world`. Если receipt одной секции содержит достижимый прежний state другого timeline и новый state текущего timeline того же мира, merge замещает прежний state и provenance выдаёт голый `ValueError("receipt state is missing from the resulting metadata")`. Закрытие требует `SnapshotMetadataFailure` с доменными кодами и путями к назначениям, родителю или элементу state_refs. Независимые дубли обоих участников должны попадать в один отказ до первого append. [snapshotMetadataBuilder.py, строки 123–143](../../backend/app/application/worldSnapshot/service/snapshotMetadataBuilder.py#L123) · [receiptProvenance.py, строки 44–50](../../backend/app/application/worldSnapshot/validation/receiptProvenance.py#L44)
3. **Прямой builder не проверяет состав игроков.** При ожидании `p1` и assigned ref игрока `guest` caller получает `KeyError('guest')`. При ожидании `p1` с пустым head и пустых assigned players builder успешно возвращает только world envelope. Оба контекста создаются обычным конструктором. На пути через `_apply_to_target` состав проверяется. Закрытие требует обеспечить взаимно однозначное соответствие до построения parents либо при создании контекста и проверить предсказуемый отказ для обоих прямых входов. [snapshotMetadataBuilder.py, строки 52–57](../../backend/app/application/worldSnapshot/service/snapshotMetadataBuilder.py#L52)
4. **Ошибка одного поля receipt скрывает независимую ошибку соседнего поля.** В намеренно повреждённом POJO секции переданы невалидный `retained_artifacts[0]` и корректно типизированный history ref чужого snapshot. Caller получил `invalid_receipt` для artifact, но пропустил `foreign_history` того же receipt. Следующая секция была проверена. Закрытие требует пропускать зависимую ветвь, продолжать проверку доступных соседних полей и подтвердить обе диагностики с индексами. [snapshotMetadataBuilder.py, строки 76–84](../../backend/app/application/worldSnapshot/service/snapshotMetadataBuilder.py#L76)

## Составной отказ

Временное SQLite-хранилище и настоящая writer-транзакция. World parent `old` отсутствует, history секции `a` ссылается на чужой snapshot, artifact секции `b` не имеет назначения. Ниже полные списки в порядке выдачи. Ко всем кодам в таблице применяется префикс `snapshot.metadata.`.

| Вызов | Код | Путь | Сообщение |
|---|---|---|---|
| Сервис, единственный элемент `PublicationInfrastructureError.args[0]` | `missing_persisted_base` | `validation.expected_world.snapshot_head` | `missing pinned snapshot old` |
| Прямой builder с пустой картой bases, `SnapshotMetadataFailure.diagnostics[0]` | `missing_base` | `bases.old` | `missing pinned snapshot` |
| Тот же builder, элемент 1 | `foreign_history` | `receipts[0].history_refs[0].snapshot` | `history must target an assigned snapshot` |
| Тот же builder, элемент 2 | `unassigned_artifact` | `receipts[1].retained_artifacts[0]` | `receipt artifact has no metadata destination` |

При двух отсутствующих persisted refs SQLite-read вернул None для каждого. Один `PublicationInfrastructureError` содержал две диагностики `snapshot.metadata.missing_persisted_base` в порядке world → player:

1. `validation.expected_world.snapshot_head` — `missing pinned snapshot old`.
2. `validation.expected_players[0].expected_head` — `missing pinned snapshot old-p`.

В обоих сервисных отказах счётчик `history.append` был **0**. С двумя существующими persisted parents сервис на тех же плохих receipts вернул `SnapshotMetadataFailure` с `foreign_history` и `unassigned_artifact` в указанном порядке. Вызовов append также **0**.

Без валидной базы нельзя проверить достижимость прежнего state данного владельца, унаследовать его секции и завершить envelope. Назначение history, operation ID, no-op с новым state, retention destination и независимые секции можно проверить.

## Обычный путь и границы проверки

- Сервис читает точные refs из expected heads через `context.scope.read_scope`, строит весь кортеж envelopes и передаёт каждый в `history.append` с исходным writer scope. Интеграция второго тика использует реальные SQLite history и CAS. Со второго соединения проверены world/player heads и точные родители. Receipts в этой интеграции пусты. Merge с содержательными receipts проверен контрактным тестом builder.
- Для каждого участника builder сохраняет неизменённые state refs базы, заменяет state по section_key для назначенного ref и включает history только своего текущего snapshot. Пустой тик наследует state. Новый state у no-op, недостижимый прежний state и чужой history отвергаются. Неверный envelope под правильным ключом базы дал `base_identity` на `bases.old.ref` вместе с обеими независимыми ошибками секций.
- Builder проверяет scalar-поля, базы, destinations, receipts по индексу и pack. Затем на строке 123 вызывает `raise_if_any`. Вложенные поля receipt, patch, state и history читаются через `FieldRef` и `bind_field`. Порядок обхода bases и retained задаёт входной mapping. Сервис проходит world и затем expectations игроков, формирует пути к полям POJO строковыми литералами и вызывает `raise_if_any` на строке 58. Отдельная проба вне аннотации — `None` вместо кортежа в `retained[world]` — дала `TypeError: 'NoneType' object is not iterable` на строке 71 builder.
- Receipt с world и player state refs и одним artifact A проверен с четырьмя картами. При назначении только world либо только player artifact получил ровно указанный участник. Пустая карта дала `unassigned_artifact`. Карта с одним чужим snapshot дала сначала `foreign_destination` на `retained.old-p`, затем `unassigned_artifact` на `receipts[0].retained_artifacts[0]`. Выбор владельца, полнота inherited artifacts и фактический handoff принадлежат внешнему caller.
- Публичный apply(), terminal/retry и production wiring вне проверенного среза.

## Сила регрессий и прогоны

Подмены выполнены в отдельном процессе только в памяти. При замене индекса `i` на `i+1` тест `test_metadata_builder_merges_pinned_state_and_partitions_tick_receipts` упал на сравнении полного списка пар (код, путь). При ограничении обхода до `receipts[:1]` тот же тест остался зелёным. Минимальный контрпример — две секции из составного отказа выше, где artifact без назначения есть только во второй. [test_registry.py, строка 331](../../backend/tests/snapshotCore/contracts/test_registry.py#L331)

| Команда из backend на проверенном HEAD | Результат |
|---|---|
| `../.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.contracts.test_registry tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests tests.snapshotCore.contracts.test_typing` | 15 тестов, OK, 24,192 с |
| `../.venv/Scripts/python.exe -B -m unittest discover -s tests/snapshotCore -p "test_*.py"` | 167 тестов, OK, 1 пропущен, 130,369 с |
