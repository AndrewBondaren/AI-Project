# Общая запись DAG: последовательные уточнения владельцев

2026-11-18. Ответы владельцев для [карты K1–K10](dag-multidomain-patch-publication-draft.md). Это evidence сверки, не приёмка новых контрактов или разрешение кода. Порядок опроса не задаёт runtime-порядок нод.

## 1. Snapshot — ответ получен

Источник: чат `snapshot`, thread `01a1eeb1-392b-7a02-8aa3-c3fa11482b02`, ответ на запрос 2026-11-18. Проверены owning public methods, atomic trace, R1–R3 и проект Snapshot node contracts.

- K4: `IWorldSnapshotApply.apply[S: DomainSection](patch_set: PatchSet[S]) -> SnapshotApplyResult`. Целевой concrete owner — WorldSnapshotService. Порт существует; полный public apply lifecycle не готов. Node mapping: ApplySnapshotInput.patch_set → apply → ApplySnapshotOutput.value без пересборки.
- Result: COMMITTED/CONFLICT/REJECTED, operation_id, request_fingerprint, committed refs и diagnostics. Public SnapshotPublicError/SnapshotPublicFault transport ещё proposed; engine mapping сохранённой SnapshotOperationCancelledError остаётся OPEN, она не равна обычной invocation cancellation.
- K3: публичной owning операции сборки не найдено. Простая композиция возможна только из уже готовых native sections, их порядка/зависимостей и полного контекста. Превращение входных patches в sections, merge, предметная группировка, вычисление dependencies/fingerprint не разрешены внутри DAG.
- PatchSet требует format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Producer общей operation identity/preparation fingerprint и закрытый section roster для нашего процесса OPEN. `request_fingerprint` вычисляет Snapshot; не смешивать его с входным preparation_fingerprint.
- Lease, hold map, assigned SnapshotRef, registry и transaction scope не входят в public apply. Artifact protection должна сохраняться до commit. Leftover holds не освобождаются автоматически; producer lease, readiness и cleanup требуют уточнения Artifacts/Publication.
- Snapshot владеет admission, canonical request fingerprint, immutable operation binding/replay, claim, transactional checks, apply, metadata/history, handoff, CAS, terminal/commit. Эти алгоритмы не переносятся в prepare_changes, assemble_patch_set или apply_snapshot.
- Универсальная очередь Source → Lifecycle → Time → Artifacts → Pack из apply не следует. Cache не prerequisite корректности apply; Pack activation перед apply не требуется. Уже готовые Time/Lifecycle patches не требуют повторной предметной подготовки.
- Ограничение: current apply — runtime контракт с существующими pack, gameplay/timeline/turn prerequisites. Их создание не добавляется в наш scope. Нельзя объявить этот маршрут универсальной записью до появления такого контекста.

Owning источники: [public methods](snapshot-public-methods-contract.md), [node contracts](gen-dag-snapshot-node-contracts.md), [atomic trace](snapshot-public-apply-atomic-trace.md), [R1–R3](snapshot-retention-cancel-diagnostics-contract.md). Исторические proposals читаются с учётом последних owning решений.

Итог: K3/K4 OPEN для полной приёмки; уже принятые apply signature/result/R1–R3 не переоткрываются. Следующий запрос Artifacts: lease, operation binding/fingerprint, readiness/protection/cleanup и exact prepare/stage contracts.

## 2. Artifacts — ответ получен

Источник: чат `Artifacts`, thread `01a1ea09-2ab4-7f71-9d96-7a29d70269d7`, 2026-11-18. Owning источник: [public staging](artifacts-public-staging-dag.md).

- K8 target concrete ArtifactPrepareStageOpenPipeline[C].prepare_stage(ArtifactPrepareStageInput[C](content)) → PreparedArtifact[C](content, descriptor). K9 ArtifactStageOpenPipeline[C].stage(ArtifactStageInput[C](lease, prepared)) → ArtifactRef. Разделение операций принято; exact API/POJO — TARGET proposal, не runtime/full acceptance.
- Content производит owning домен: canonical bytes для BLOB или concrete frozen row-set для SQL_ROWS. Trusted composition связывает format/version/backend. DAG не выбирает codec и не сериализует все входные патчи автоматически. PreparedArtifact — temporary envelope; durable/checkpoint transport OPEN.
- Expected input faults: ArtifactInputRejected(ArtifactInputError); stage также ArtifactLeaseRefused(ArtifactLeaseFailure). Codec/infrastructure/busy/unknown/cancellation не покрываются одним node error POJO. Полный fault transport OPEN.
- Stage обеспечивает operation hold в точке confirmed seal commit, но concurrent cancel может снять hold до доставки ответа. ArtifactRef не read authority и не гарантия protection до apply; cache-hit также этого не доказывает.
- Target open/complete preparation принадлежит Publication. Existing open_operation/finish_preparation не становятся автоматически публичными целями нового DAG-процесса. Producer общей operation identity/preparation fingerprint, public completion/READY, непрерывная protection, retention и cleanup остаются OPEN.
- Finish существующего примитива проверяет holds/seals, отсутствие writers и закрытие admission, но не доказывает полноту доменных изменений/Source closure. Collect не снимает live holds. Unknown нельзя трактовать как rollback; cancellation не означает подтверждённую отмену публикации.

## 3. Publication — ответ получен

Источник: чат `Publication: контракт adoption и READY` (`01a1ea8d-2bdb-7152-bb40-925c86c041d8`), 2026-11-18; [Snapshot ARCH-0.3–0.4](world-domain-patches-snapshots.md).

- Принятого public preparation/completion lifecycle общей SNAPSHOT_APPLY нет. Existing IArtifactLeases.open_operation/finish_preparation/recover/cancel и IArtifactHolders.handoff — внутренние порты, не готовые цели нод.
- Producer operation_id/preparation_fingerprint и semantic body общей подготовки OPEN. Existing open может вернуть lease закрытой операции, поэтому не обещает публичный writable/replay-aware success.
- READY подтверждает exact holds/seals/no writers/closed admission, но не полноту секций и соответствие будущему PatchSet. Completion/replay и protection при concurrent cancel OPEN.
- Cancel terminal-операции возвращает terminal; это не гарантированная очистка leftover holds. Exact cleanup OPEN. Unknown не разрешает release или автоматический takeover.
- Малая запись без staged artifacts допускает claim без предварительного staging record. Нельзя назначать lease/stage/READY обязательными для любой записи.
- Pack-specific retention/adoption/manifest/candidate и initial registration не являются общим preparation-контрактом. Их перенос на SNAPSHOT_APPLY без owning решения запрещён.

Итог: добавить в карту внешнюю потребность Publication (producer K9 и связь с K4), не придумывая публичную ноду.

## 4. Pack — ответ получен

Источник: чат `PACK (2)`, thread `01a1db1a-600b-74b3-a38d-aed8b42317d0`, 2026-11-18.

- При готовых native sections вызов Pack не обоснован без отдельной owning зависимости. expected_world.pack_hash — закреплённая база, не команда подготовить/активировать новый Pack.
- Реализованные PackPreparationService.write_wilderness_chunks(PackWildernessChunksInput) и start_empty(PackPreparationEmptyInput) возвращают PackPreparationState, отказывают через PackPreparationFailure(PackPreparationError). Они не являются подготовкой runtime PatchSet.
- PackPreparationState и PreparedPackCandidate не DomainSection. Принятого преобразования в section не предъявлено. Candidate fingerprint не заменяет общий preparation fingerprint. Final Pack preparation/activation/release остаются отдельными контрактами, не стадиями общей native patch записи.
- Pack владеет admission адресов, состава, descriptor formats, metadata transitions/provenance. Pure state writes не требуют обязательного Source/Artifacts/Cache CALL: нужные evidence/refs должны уже входить в owning input. Descriptor не доказывает seal/hold.
- K7 остаётся необязательной неподключённой ветвью до указания конкретного изменения persistent Pack, input producer, public operation и consumer результата. Нельзя переносить PACK_ACTIVATION lifecycle на SNAPSHOT_APPLY.

Источники ответа: [state service](../../backend/app/application/worldData/pack/preparation/packPreparationService.py), [owning inputs](../../backend/app/dataModel/worldPack/preparation/operations.py), [public write plan](pack-v2-public-write-operations.md).

## 5. Source — ответ получен

Источник: чат `Source`, thread `01a1d566-656d-7f83-b460-bef97bb4a2e7`, 2026-11-18. Owning источники: [spec §9](source-proof-v2-contract-spec.md), [public boundaries](source-core-public-boundaries.md), [mutation](source-core-mutation-contract.md), [technical debt](source-technical-debt.md).

- Source call не обязателен для готовой section или по одному наличию Source refs. Нужен конкретный producer/consumer provenance; для общей записи такой roster не установлен.
- Async admit/read/select возвращают SourceProofResult или SourceFailure; admit_groups/verify_groups — SourceProofGroupsResult или SourceFailure. Infrastructure не semantic refusal. Полные owning Input перечислены в K6.
- Baseline spec — единый SourceProofPipelineOpenPipeline; пять отдельных owners под operations согласованы как направление. Полный layout/constructors/IO binding ещё не принят вместо baseline, публичной IO-реализации нет. DAG не выбирает layout самостоятельно.
- Producer обеспечивает полноту usage своего вычисления. Source проверяет предъявленные зависимости, не доказывает, что producer ничего не забыл. DAG не вычисляет proof union/subset/fingerprint/closure.
- Все пять операций read-only; finalized captures проверяются, но не создаются. durable_refs — closure, не receipt удержания. Proof не выполняет adoption/publication. Известный mapping proof → PackStoredProvenance не задаёт consumer общей Snapshot записи.
- Направление DAG → Source preparation → DAG → publication с атомарным target retention сохраняется. Прямой Snapshot → Source.check_coverage/collect_for_adoption/adopt недопустим; исторические S1/S2 scoped traces не разрешают этот обход. Отдельная adopt-нода без доказанной атомарности также не решение.
- Source mutation apply/recover — отдельные proposals. Proof admission не write API; runtime preparation/native-section binding Source OPEN.

K6 OPEN: конкретная необходимость, owner layout/IO, output→input mapping и protection/retention; при mutation — отдельный owning контракт.

## 6. Entity Lifecycle — ответ получен

Источник: чат `Lifecycle`, thread `01a1e936-4dfc-7d73-aede-dbfd4d988d81`, 2026-11-18; [ТЗ и LC-C06/09/13](../../docs/tz_entity_lifecycle.md).

- При готовой принятой native LifecycleSection дополнительный CALL не нужен. Предметное намерение и proposed PreparedLifecycle… не равны готовой section.
- Четыре public prepare-операции и read_current/read_history описаны проектно; exact POJO/errors и native patch representation OPEN. Публичного метода, уже возвращающего готовую native section, нет; application/dataModel lifecycle отсутствуют.
- LC-C06/09 должны определить представление результата и section binding; если нужна отдельная операция, её публичный контракт принимает владелец. DAG не строит before/after, основания или секцию сам.
- Reads не обязательны для каждой записи. Нужны достаточные captured facts/evidence; нельзя заменять неизвестность отсутствием или читать latest для обновления условий уже готового перехода. Публикационные stale/precondition checks сохраняются.
- change_uid — логический переход, operation_id — общая публикация. Runtime change_uid создаётся при намерении через общий app.ids.runtime_uid и сохраняется при retry. operation_id не входит в смысловое сравнение перехода. Lifecycle не производит общий preparation/request fingerprint. Exact PatchRef mapping и concurrent retry binding OPEN.
- Атомарность перехода/основания/проекции/предметных изменений требуется, но concrete persistence, разрешённая nested chain, registration/errors/retention OPEN. Snapshot handler infrastructure не разрешает прямой Lifecycle writer/validator.

K10-Lifecycle OPEN: необходим точный public result → native section mapping, а не дополнительный универсальный converter DAG.

## 7. Time — ответ получен

Источник: чат `TIME IMPL`, thread `01a1a0ba-1bcf-7870-b23c-b0c27d874eca`, 2026-11-18; [Time plan](time-domain.md), application/time/changes/advancePipelineOpenPipeline.py и dataModel/time/changes/advance.py.

- Реализован prepare_advance(PrepareAdvance(operation_id, base: TimeCapture, duration)) → TimeAdvanceProposal(operation_id, base, interval) либо TimeAdvanceMustBePositive/TimeRangeOverflow. Это pure proposal, не принятая запись и не native section.
- Proposed TimeAdvanceSection(DomainSection[TimeAdvanceProposal]) содержит header/patches, один proposal на acceptance group. Public producer section/Input/Output/Error и header binding OPEN, section/codec/handler readiness не доказана (T5).
- Готовая native section не требует повторного advance/read. Proposal нельзя превратить в section алгоритмом DAG. Если есть только намерение, нужен owning prepare с достаточным capture; нельзя автоматически заменить supplied base текущим временем. Нет изменения времени — нет фиктивного advance(0).
- TimeCapture.publication — база, не target. Общая operation identity передаётся Time; future refs назначает Snapshot; принятие clock подтверждается только commit. Общий preparation fingerprint не принадлежит Time.
- Историческое §18.4 «DAG собирает TimeAdvanceSection» не разрешает предметную сборку/валидацию по новому правилу. Нужен owning public контракт. Existing Time read adapter с прямой Snapshot-зависимостью не является автоматически допустимым target read path.

K10-Time закрыт только на уровне pure advance API; native section producer и integration OPEN. Initial/start в scope не добавляются.

## 8. Cache — ответ получен

Источник: адресная сверка Cache в чате `DAG`, thread `01a1d598-f2e7-7fc1-8c3a-f4386cbfa6a6`, 2026-11-18. Остальные семейства этим запросом не перепроектировались. Источники: [Cache contracts](cache-public-contracts.md), [node plan §6.5–6.6](gen-dag-cache-pack-source-families.md), engine/nodes/cache и dataModel/engine/nodes/cache.

- Четыре leaf реализованы: get(CacheKey[T]) → CacheLookup[T]; create/update(CacheEntry[T]) → CacheCreateResult/CacheUpdateResult; evict(CacheKey[T]) → CacheEvictResult. CacheFailure(CacheError) сохраняется в CacheNodeError. Concrete manifest T=bytes, namespace world_pack.manifest_bytes/schema 1, named manifest node DTO и registrations существуют.
- read_cache One/All и write_cache Create/Update/Evict — PROJECT; upper binding/continuation/all scope остаются OPEN. All — явно заданный tuple запросов, не scan всего cache.
- Cache не обязателен для готовых patches. Нужны конкретные producer, T, key/value и hit/miss semantics. Manifest key по полному ArtifactRef и verified bytes не являются готовым контрактом кэширования patches.
- Owning producer формирует данные ключа/значения; DAG не считает доменные hashes. Hit не доказывает publication/pin/protection; miss штатный outcome, не ошибка. Update NOT_FOUND не создаёт запись, UNCHANGED не меняет значение, другое значение конфликтует.
- Cache не разрешает publication unknown. Evict удаляет RAM-копию, не holders/pin и не публикацию. Cleanup coupling общей записи OPEN; Cache не закрывает assembler/native-section/Publication gaps.

## Сводка после первого последовательного круга

Все запрошенные ответы получены по очереди: Snapshot → Artifacts → Publication → Pack → Source → Lifecycle → Time → Cache. Этот порядок является только порядком уточнения.

1. Публичный apply принимает готовые native sections. Вход «готовые патчи» ещё не доказан эквивалентным; нельзя молча изменить вход или реализовать converter в DAG.
2. K3: либо доказать простую композицию всех готовых данных, либо получить owning публичную операцию формирования недостающего результата. Такого assembler-контракта сейчас не предъявлено.
3. Time/Lifecycle не имеют завершённого публичного producer native section; pure proposals не закрывают эту границу. Их повторный вызов для уже готовой section не нужен.
4. K9 consumer lease известен, public producer и общая preparation/completion/protection/cleanup boundary Publication OPEN. Это отдельная зависимость карты, не новый назначенный NodeId.
5. Pack/Source/Cache и staging не являются обязательными стадиями любой записи. Нужна конкретная owning потребность input→operation→output; текущие стрелки — возможности семейства, а не установленный runtime маршрут.
6. Контракты ошибок/cancellation сохраняют owning различия; exact transport местами OPEN. Реализованные внутренние примитивы не закрывают публичный contract gate.

Полная приёмка нод/маршрута не выполнена. Следующее совместное решение — точная форма входа общей записи и владелец её преобразования в native sections, затем внешний public lifecycle подготовки для ветви с артефактами. Код и owning ТЗ этим опросом не менялись.
