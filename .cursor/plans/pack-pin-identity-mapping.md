# Pack — pin identity и exact publication admission

2026-11-12. Статический trace, PROJECT адаптации существующих механизмов; только документация, тесты не запускались. Связь: [POJO audit](pack-pojo-error-acceptance.md), [CRUD roster](pack-data-crud-roster.md), [write-план](pack-v2-public-write-operations.md). Код/SQL/DAG не меняются.

## Что уже есть

[ExecutionPins._binding](../../backend/app/db/repositories/sqlite/worldPack/executionPins.py) проверяет authenticated store namespace, execution closure и exact store/execution/invocation/logical_read_key/world/pin/state=OPEN. acquire при новом pin читает текущую публикацию в транзакции, проверяет manifest и записывает **publication_id** вместе с manifest_artifact_id; повтор существующего pin возвращает закреплённый ref, а не переключает его на новый head.

[pack_execution_pins](../../backend/app/db/migrations/0001_initial.sql) уже имеет FK(world_uid, publication_id) к append-only world_publications. held_manifest проверяет binding и PinHolder; hold_open удерживает read scope и проверяет seal. Новой таблицы pin-publication, нового journal или копии всей publication в pin row не требуется.

[PinnedManifestGuard](../../backend/app/db/repositories/sqlite/worldPack/pinnedManifestGuard.py) строит PinIntent из ManifestPinRead, вызывает hold_open и проверяет descriptor/budget. [PinnedManifestReader](../../backend/app/application/worldData/pack/read/pinnedManifestReader.py) дополнительно проверяет address/cache key, digest/schema/world. **Полная expected WorldPublicationRef в этом input отсутствует.** _binding не сравнивает caller publication_id, snapshot_head, timeline или gameplay_started. Existing VerifiedManifestBytes не доказывает эти соответствия.

Существующий [SqliteWorldPublicationStore.read_exact](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py) имеет сигнатуру `async read_exact(world_uid: EntityUid, publication_id: EntityUid, *, scope: CommitReadScope) -> WorldPublicationRef | None`. Он использует заданный scope и читает историю по точному ID. Новый latest lookup или публичный междоменный CRUD-вызов для Pack read не нужен.

## Единая декларация identity — предложение без второго POJO состава

В `dataModel/worldPack/read/pinnedManifest.py` предлагается внутренняя база `_PackPinIdentityFields` с единственной декларацией существующих пяти полей и constraints: store_id: UUID, execution_id: ExecutionIdValue, invocation_id: InvocationIdValue, logical_read_key: непустая strict str, pin_id: непустая strict str. Она strict/frozen/extra=forbid/revalidate_instances=always и не является публичным record или отдельным contents объектом.

- EXISTING ManifestPinRead наследует эти поля и сохраняет world_uid/max_bytes. Его текущая структура caller-visible полей не меняется этим проектом.
- PROJECT PackPinnedReadIdentity в read/part.py наследует те же поля и добавляет publication: WorldPublicationRef. World берётся только из publication; budgets остаются в вызывающем request.
- Оба public класса — named concrete records, с собственным ModelIdentity по разным обязанностям. Повторно объявлять пять полей/validators в каждом нельзя. Реальные CheckedPath/canonical registration/serialization проверки ещё нужны.
- Internal PinIntent остаётся адаптерным входом, не третий public DTO. При реализации его общие identity constraints также должны переиспользовать эту декларацию/единый проверенный mapping; текущий dataclass не объявляется уже адаптированным. Если требуется смена его представления, это отдельная внутренняя правка с trace callers, без вечного parallel alias.

Таким образом ManifestPinRead и PackPinnedReadIdentity различаются context/budget/publication обязанностями, а общая identity не объявляется дважды. Это проект устранения отмеченного пересечения, не разрешённое исключение из запрета дублей и не утверждение, что адаптация уже реализована.

## Exact pin admission — внутреннее расширение

Предлагаемый метод существующего concrete адаптера `ExecutionPins` в db/repositories/sqlite/worldPack/executionPins.py:

`hold_exact(self, request: PackPinnedReadIdentity) -> AbstractAsyncContextManager[ArtifactRef]`

Реализация — async context manager; это внутренний storage binding, не публичная операция DAG и не capability в dataModel. Он переиспользует _binding/catalog/holders, не создаёт второй pin lifecycle. Возвращённый ref действителен для physical open только пока guard открыт.

В той же защищённой области, что и pin lifetime/open:

1. Strict revalidation request; internal world_uid = request.publication.world_uid. Проверить existing namespace/execution/invocation/key/pin identity и OPEN binding.
2. Сопоставить row.publication_id с request.publication.publication_id. При несовпадении не принимать совпавший manifest hash как альтернативное доказательство.
3. В том же scope вызвать existing read_exact(row.world_uid, row.publication_id, scope=...). Сравнить **всю** восстановленную WorldPublicationRef с request.publication: world_uid/publication_id/pack_hash/snapshot_head/active_timeline_id/gameplay_started. Поддельная expectation с тем же ID должна быть отклонена.
4. Разрешить manifest_artifact_id; проверить точный descriptor, publication.pack_hash == ref.content_hash, PinHolder и seal. Бюджеты/profile проверяются соответствующим read guard до открытия bytes. Не искать другой artifact по совпадению hash, не переустанавливать pin.
5. Оставить pin/GC protection действующей до завершения verified physical read. Проверка publication вне guard с последующим незащищённым open недостаточна. Scope read_exact обязан принадлежать тому же принятому registry; несовместимость подключённых scope — composition refusal, не новый вложенный COMMIT.

Existing pin errors и infrastructure/cancellation сохраняются. Exact publication mismatch должен отображаться в PackPartReadRefusal.PUBLICATION_MISMATCH, а в existing manifest bytes boundary — ManifestReadRefusal.IDENTITY_MISMATCH. Закрытый/чужой pin остаётся CLOSED_PIN/INVALID_PIN; пропавший исторический row при существующем FK-bound pin не трактуется как обычный PackPartAbsent. Точный внутренний carrier для различения publication mismatch и прочих PackIdentityConflict ещё требует error mapping; нельзя произвольно переводить любой conflict в PUBLICATION_MISMATCH или создавать новый универсальный error DTO.

## Mapping к потребителям

| Потребитель | Поля и проверки | Запрещённая подмена |
|---|---|---|
| start_from_base(PackPreparationBaseInput) | request.pin передаётся exact admission; max_manifest_bytes ограничивает verified manifest read. state.base_publication берётся из успешно подтверждённой publication, состав/provenance — из этих bytes | Принять caller publication после проверки одного world/hash; считать previous VerifiedManifestBytes живым pin |
| read_part(PackPartReadInput) | Тот же exact pin admission; four budgets остаются в input, role/contract/reachability — в read operation. Returned publication равна проверенной historical publication | Вернуть latest publication рядом с pinned bytes или прочитать child после закрытия pin |
| Existing ManifestPinRead adapter | Пять identity fields копируются через общий typed mapping; world_uid=publication.world_uid, max_bytes=caller budget | Такой mapping сам по себе не выполняет exact admission: existing bytes reader не знает полной publication |
| Cached manifest read | Каждый hit снова проходит exact pin/publication и existing key/digest/schema checks | Использовать cache как замену pin validation |

Нельзя выполнить hold_exact, закрыть его и затем вызвать bytes read, заявив, что чтение защищено предыдущей проверкой. Конкретная проводка PinnedManifestGuard/Reader должна сохранить весь physical open внутри действующей exact защиты либо выполнять эту проверку заново внутри своего guard. Это часть реализации binding, не дополнительная стадия DAG.

Initial pin acquisition и чтение уже созданного pin — разные операции: current acquire выбирает head в момент первой фиксации. Оно не реализует request-pin-at-arbitrary-historical-publication. Если DAG хочет именно исторический pin, такой acquire-контракт должен быть предъявлен отдельно; read adaptation не получает право перезаписать existing pin.

Start_from_base не гарантирует, что база останется доступной до final prepare. State содержит publication и данные, а не lease. Final preparation проверяет существующий внутренний pin/retention/adoption binding заново; добавление public backend/lease или скрытого reacquire latest запрещено. Это сохранённый lifecycle gate, не новый Source механизм.

## Приёмочные случаи и статус

- Публикации A и B имеют один pack_hash, но разные IDs: pin A + expected B отклоняется.
- Тот же ID/hash, подменены snapshot/timeline/gameplay_started: полный expected mismatch отклоняется.
- Head сменился A→B: действующий pin A + точная A читается без latest lookup.
- Другой store/execution/invocation/key/world, CLOSED pin, missing hold/unsealed — соответствующие typed отказы.
- Закрытие pin между логической проверкой и physical open не даёт незащищённого чтения; cold/cache hit соблюдают ту же границу.
- Shared identity поля объявлены один раз; named concrete CheckedPath/canonical round-trip работает; бюджеты не становятся identity полями publication.
- State создан из A, pin закрыт до prepare: нет автоматического fallback на B и нет READY без принятого retention binding.

Статус: конкретный пробел и способ reuse существующего storage/history подтверждены trace; shared identity и hold_exact — PROJECT. Error carrier, concrete guard wiring, PinIntent migration и race/restart tests ещё OPEN. Полная POJO/lifecycle приёмка не объявляется завершённой. Порядок источники → evidence → manifest → codec/readers и три запрета DAG сохраняются.
