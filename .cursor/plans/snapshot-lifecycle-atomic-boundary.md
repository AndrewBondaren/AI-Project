# Snapshot / Lifecycle: ограниченная atomic boundary

2026-11-21, PROPOSED для Lifecycle и координатора. Задание №4 [node-плана](gen-dag-lifecycle-node-contracts.md). Документальный контракт, не code-go. C1/C2/H2, H3 Time, порядок write_changes не пересматриваются. IN — готовая typed LifecycleSection, synthetic TestEntityA/TestEntityB, fake participant и общая atomic boundary. OUT — реальные producers/объекты, SQL/DDL/adapters, production wiring, read_world, bulk, вариант Б, overlapping chains, checkpoint/restart. OUT не blockers этого среза.

## 1. Владельцы проверок и порядок

| Проверка | До transaction | В общей transaction |
|---|---|---|
| Shape/native schema/версии | Owning модели и C1 registry/codec; Snapshot request admission | BoundSectionHandler проверяет output shape по C1/H2; не дублирует semantics |
| operation_id, expected_world, PatchRef/dependencies | Lifecycle prepare_section формирует headers и проверяет supplied evidence; PatchSet проверяет общие invariants | Snapshot сравнивает actual expected heads/context, immutable binding; Lifecycle сверяет свои supplied operands с context |
| Lifecycle source/before-state | Pure prepare использует supplied typed capture, не latest и не IO | Lifecycle handler читает собственное accepted состояние exact Q в borrowed read facet и проверяет preconditions; Snapshot не вычисляет lifecycle status |
| Предметное основание/evidence | Owning synthetic producer проверяет свои факты/typed payload; Lifecycle проверяет structural relation/coverage, не предметную логику | Lifecycle проверяет Q/operation/entity/patch bindings supplied evidence; Snapshot гарантирует общий Q и admitted dependency refs. Нельзя превратить произвольный POJO/trusted=True в proof принятого состояния |
| Duplicate change_uid в batch | Lifecycle prepare_section отклоняет весь batch, даже если повтор равен | Lifecycle handler повторно применяет тот же owning pure invariant для unchecked/direct/decode path, не копирует алгоритм |
| change_uid уже в accepted history | Capture обязан описывать полноту проверки, отсутствие записи без полноты не доказательство | Lifecycle owning store даёт exact lookup/completeness в том же scope; same semantic content → no second history operation, different → typed Lifecycle conflict. Operation replay Snapshot не заменяет эту проверку между разными operation_id |
| Участники пересекаются между переходами | Lifecycle section invariant запрещает; independent transitions сохраняют входной порядок | Owning revalidation того же инварианта; Snapshot не сортирует и не пытается разрешить цепочку |
| Receipt membership/assigned refs/inheritance | Не проверяется по выдуманному будущему snapshot | Snapshot C2 сразу после successful apply до accumulator/следующего handler; PatchSet проверяет лишь output contract |

Trace новой попытки: admission → fingerprint → claim/replay → общая transaction → expected-context checks → предусмотренные принятым порядком source bindings → все handler.validate → дочитывание C2 bases с reuse → последовательные handler.apply и immediate C2 check → metadata/handoff/CAS/terminal → confirmed commit. Lifecycle не получает Time source binding по аналогии. Если ему нужна Snapshot metadata source resolution, предъявляется собственный binding; fake собственного Lifecycle persistence может читать accepted view по exact Q без foreign lookup.

Replay текущей operation выходит до Lifecycle reads/handler. Validation refusal запрещает все apply. Apply refusal/contract fault/CAS conflict откатывает все уже выполненные writes; разделение business/infrastructure/unknown остаётся owning H2. Отказ не выдаёт частичную секцию/успех.

## 2. Точные application port obligations — предложение Lifecycle owner

Сигнатуры используют closed `L` конкретной LifecycleSection и её native patch union, определяемый Lifecycle/PatchSet. Не подставлять DomainSection/BaseModel как runtime L. Existing planned LifecycleCapture должен быть завершён владельцем (§5); Snapshot не создаёт второй capture/evidence POJO.

Предлагаемый `application/lifecycle/storage/participantPort.py`:

```python
class ILifecycleParticipantReader[L](Protocol):
    async def read_for_section(
        self, section: L, *, publication: WorldPublicationRef,
        scope: CommitReadScope,
    ) -> LifecycleCapture: ...

class ILifecycleCommitBinding[L](Protocol):
    def bind(self, scope: CommitScope) -> IBoundLifecycleWriter[L]: ...

class IBoundLifecycleWriter[L](Protocol):
    async def append(
        self, section: L, *, expected: WorldPublicationRef,
        target: WorldSnapshotRef,
    ) -> LifecycleAppendResult: ...
```

Это узкие ports собственного Lifecycle persistence, не public domain pipelines. Payload read request не содержит чужого store/handler. Writer связывается только с существующим scope и не commit/rollback/retry. `append` повторно проверяет owning preconditions/idempotence в том же exact accepted Q до первого write, затем атомарно добавляет Lifecycle operations и соответствующие projections. LifecycleAppendResult — proposed alias `LifecycleAppended | LifecycleSectionRefused`; точный concrete refusal определяется владельцем по H2, Snapshot его не изобретает.

Предлагаемый `dataModel/lifecycle/publication/appendResult.py::LifecycleAppended`: state:SectionStateRetention | None; history:SectionHistoryRetention | None; changed:tuple[PatchRef,...]. Все поля обязательны, strict/frozen/extra-forbid/revalidate-always. Это storage postcondition, не вторая history-operation запись. Новый state и любой возвращённый history ref относятся к assigned target и Lifecycle section key, versions принадлежат Lifecycle. Для local row-like fake artifacts=(). Коррекция 2026-11-21 по actual receiptProvenance: наследуется только state; history из receipt не может ссылаться на старый snapshot. При доказанном exact повторе без новых переходов changed=(), history=None, state=None либо exact inherited state retention; builder сам наследует неперезаписанное base state. Прежнее предложение inherited history отозвано. Если у владельца есть equivalent typed append outcome, переиспользовать его; отсутствие duplication подтверждает Lifecycle до приёмки. Null history на no-op — local Lifecycle contract, не новое общее правило cardinality Snapshot.

LifecycleSectionHandler.validate(section:L,context:SnapshotValidationContext) → SectionValidation[LifecycleDiagnostic] вызывает только reader и pure owning checks. apply(section:L,context:SnapshotApplyContext) → SectionApplyReceipt | LifecycleSectionRefused использует binding.bind(context.scope).append(section, expected=context.validation.expected_world, target=context.world_snapshot). Handler строит receipt из результата и owning section key: states=() при state=None, иначе (state,); history=() при history=None, иначе (history,); changed передаётся точно. Refs не переназначает. Shape admission — BoundSectionHandler, provenance — Snapshot C2. Snapshot назначает world_snapshot, next_publication, operation_id; Lifecycle не выделяет snapshot/publication/operation identity и не пишет publication heads.

Ошибки ports: malformed request — owning strict admission; semantic stale/precondition/change_uid conflict — concrete Lifecycle refusal; missing required source/completeness, corruption, scope/IO/output inconsistency — infrastructure failure с cause. None не означает автоматически отсутствие entity/истории. Истинный empty initial Lifecycle view должен быть явно отражён validated complete capture, не fallback. Unknown transaction outcome принадлежит coordinator, не writer. Cancellation не разрешает detached writes; fake/adapter drain обязан завершиться до возврата scope owner.

## 3. Разрешённая capability chain и Output→Input

Разрешённый маршрут: apply_snapshot → Snapshot public apply → registry BoundSectionHandler → LifecycleSectionHandler → Lifecycle-owned reader/pure validators/bound writer → собственное transactional fake state. Fake SQL не симулирует: нет foreign tables/public pipelines. Scope лишь разрешает участие в transaction, **не даёт право писать данные чужого домена**. Writer Lifecycle меняет только Lifecycle history/projections.

При synthetic предметном изменении его fake owning participant регистрируется отдельно через тот же C1 механизм и получает свой ограниченный writer, в той же outer transaction. Lifecycle handler не вызывает его, не получает его mutable state и не пишет его history. Fixed declared order/dependencies задаются готовым PatchSet, не выбираются Lifecycle алгоритмом. Если evidence требует предметный patch, он присутствует и admitted по exact PatchRef; если declared no-domain-patch proof разрешён, concrete owning evidence обязан объяснять достаточность without writes. Boolean bypass не допускается. Exact coverage schema — обязанность Lifecycle внутри IN.

| Output | Input / обязательное равенство |
|---|---|
| Prepared records + domain_evidence | PrepareLifecycleSection: operation/Q/typed participant scope согласованы, один transition → один patch |
| LifecycleSection | PatchSet.sections: тот же concrete object/value, порядок/headers/dependencies сохраняются; повторной подготовки нет |
| SnapshotValidationContext | reader publication=expected_world, scope=read_scope; capture.publication полным равенством Q |
| SnapshotApplyContext | writer expected=validation.expected_world, target=world_snapshot, capability=scope; без новой transaction |
| LifecycleAppended | Receipt: exact retention entries/changed refs передаются без реконструкции identity |
| Receipt | C2→metadata→CAS: successful receipt ещё не commit; history ref может адресовать bundle многих transitions |
| Confirmed terminal | apply output: только после confirmed commit/refusal persistence; unknown не normal result |

History cardinality: 100 independent Creates → 100 patches/100 новых Lifecycle history operations при первом успешном применении; один Replacement со 100 участниками → один patch/одна operation, число projections по участникам. Число SectionHistoryRef в receipt не равно числу операций: один ref может адресовать section history bundle. Для семантического повторения change_uid новых history operations нет; exact правила changed/no-op retention требуют owner mapping, не автоматического равенства changed всем входным refs.

## 4. Synthetic fake и критерии приёмки

FakeTransactionOwner — test-only реализация существующей commit capability semantics: один workspace транзакции, отдельные namespaced stores Lifecycle/DomainA/DomainB, accepted immutable baseline Q, commit публикует все namespaces вместе, rollback отбрасывает весь workspace. Он не shared production service и не новый DAG scope. Reader возвращает actual accepted Q view, не заранее заданный ответ на любой запрос. Bound writer проверяет active scope/свой namespace; после завершения owner доступ отклоняется. Baseline не меняется предыдущими staged writes, поэтому validate/apply expected-Q checks сравниваются с той же базой.

Проверки local IN:

1. Closed A/B native decode сохраняет вид; Snapshot не ветвится по A/B. Переданные source/evidence имеют typed identities и полноценные required поля.
2. 100 Creates и 100-participant Replacement дают указанную cardinality, один общий commit, input order сохраняется.
3. Неверный Q/operation/source revision/coverage ref и duplicate change_uid внутри batch отвергаются owning проверками; отсутствующий required evidence не заменяется mock default.
4. Same change_uid в другой operation: equal semantic transition без второй history operation; different content — typed conflict. Разные publication metadata не должны сами превращать один transition в different content; exact comparison задаёт Lifecycle.
5. Ошибка второго participant после writes первого, malformed receipt и CAS conflict оставляют все accepted namespaces неизменными. Нет следующего handler после отказа; detached writes отсутствуют.
6. Wrong target/foreign changed ref/сфабрикованный inherited retention обнаруживаются C2; writer не может писать чужой namespace или commit напрямую.
7. Commit acknowledgement lost → unknown; тест различает физически совершившийся и не совершившийся commit, не объявляет rollback по исключению. Exact terminal replay не вызывает writers/reader повторно.
8. Cancellation/drain/expired scope, missing/corrupt source, current output type/diagnostic preservation проходят без business маскировки infrastructure faults. Не проверяется deferred durable-cancellation node mapping.

Fake evidence проверяет протокольные обязанности, но не доказывает production storage durability/SQL isolation/cleanup. Для локального дизайна эти OUT не требуются.

## 5. Статус и оставшиеся решения строго внутри IN

Snapshot предъявил владельцев checks, fixed phase order, assigned refs, permitted nested calls, typed port proposal и synthetic assertions. Whole local binding пока **OPEN** до ответов Lifecycle/PatchSet:

- Exact closed L/diagnostic union и codec declarations (задание Lifecycle/PatchSet), без новых numeric IDs здесь.
- Полный LifecycleCapture: typed entity/transition lookup result, доказательство полноты exact Q, historical change_uid lookup. Reader signature выше не позволяет вернуть неполный capture с «не найдено значит отсутствует».
- Scope уникальности change_uid и точные semantic comparison fields; accepted duplicate-in-batch/retry semantics не переоткрываются, требуется их executable contract.
- Concrete evidence/coverage и declared no-domain-patch proof для двух synthetic видов; источник достоверности, не один hash/trusted=True.
- Owning подтверждение/переиспользование LifecycleAppended/refusal и no-op inherited retention mapping; actor только собственного persistence, без foreign writer.

Это необходимые local схемы/обязанности, не запрос реального producer, SQL adapter, production entity или checkpoint. Lifecycle source binding не считается закрытым Time H3. После owning ответов координатор сверяет ограниченный IN и пользователь принимает; код/общий node-план этим документом не изменены.
