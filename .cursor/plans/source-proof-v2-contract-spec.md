# Source proof для Pack V2 — техническая спецификация

Дата: 2026-11-12. Основание: поручение завершить техническую проработку REV-02, [основной план](world-pack-v2-single-manifest-contract.md), [Source-design](world-source-versioning.md). Статус: PROJECT / NOT ACCEPTED. Ниже отделены проверенная реализация и проект изменений. Это не отчёт о выполненной реализации и не разрешение обходить обязательную приёмку DAG/CRUD/POJO.

## 1. Подтверждённые границы записи

| Writer / исходник | Подготовка и изменение | Транзакция / место адаптации |
|---|---|---|
| [WorldService](../../backend/app/application/worldData/registries/worldService.py) create/update/import/edit_region | normalize, merge, prepare_import, before/after; `_save` вызывает create/update/upsert и reconcile | В штатном DI scope через DeclaredRegionEditor; standalone без editor scope пустой. Добавление revision должно быть обязательным для persisted source change, а не зависеть от наличия region editor |
| [NamedLocationService](../../backend/app/application/worldData/locations/namedLocationService.py) CRUD/import | typed location, occupancy, create/update/delete/upsert | Самостоятельный repository writer. Изменение body и membership locations должно учитываться совместно |
| [LibraryWriteService](../../backend/app/application/templateLibrary/packs/write/writeService.py), [executor](../../backend/app/application/templateLibrary/packs/write/writeExecutor.py) | Существующие prepare/apply, plan с members/world changes, конфликты identity | Executor требует caller main UOW; сюда передаётся подготовленное source изменение вместе с доменным write plan, без второго planner |
| [persist_body_row](../../backend/app/application/templateLibrary/packs/write/preparedPersistence.py), [LibraryBodyMixin](../../backend/app/application/templateLibrary/packs/domainAdapters/mixins.py) | insert/save/delete body через owning domain library | Не самостоятельный publication owner. Старое тело сегодня заменяется; adapter должен исполнять prepared change в scope владельца |
| [_MemberOps.delete/teardown](../../backend/app/application/templateLibrary/packs/memberOps.py) | usage check, policy allow_used, удаление body и membership | scope.atomic; allow_used не разрешает удалить историческое held-тело. Source tombstone и membership должны фиксироваться вместе |
| [_PackOps](../../backend/app/application/templateLibrary/packs/packOps.py) | create/delete/set_dependencies/update_metadata | create/delete/dependencies через atomic, metadata напрямую. Нужна классификация semantic/label полей; version label не становится SourceRevision |
| [WorldCopyImport](../../backend/app/application/worldBundle/worldCopyImport.py) | World → prepared libraries → remapped entities | Одна внешняя Database.transaction. Source revision batch должен rollback-иться вместе с импортом, а не иметь отдельный успешный commit |
| [repairWorldDefaults](../../backend/app/application/worldData/registries/repairWorldDefaults.py) | normalize и repo.update, если changed и repo передан | Обходит WorldService._save; persisted repair является записью, in-memory repair без repo — нет |
| [RaceService](../../backend/app/application/worldData/registries/raceService.py), [WorldPerkService](../../backend/app/application/worldData/registries/worldPerkService.py) | body CRUD/import плюс `_ensure_registry`/`_unbind_registry` → worlds.update | Дополнительные source writers. Изменение тела и world membership должно стать одним prepared atomic batch; сейчас единый scope этих последовательных вызовов сервисом не гарантируется |
| [SettlementOutdoorSqlPersist](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorSqlPersist.py) | districts/buildings, levels, graph, transitions; persist_topology изменяет district payload | Собственная Database.transaction, location upsert_bulk. Это derived output; нельзя автоматически считать каждую запись authored source mutation и получать feedback loop. Нужна явная роль данных при capture следующей операции |
| [SqliteWorldRepository.increment_tick](../../backend/app/db/repositories/sqlite/worldRepository.py) | Прямой UPDATE current_tick и commit | Не автоматически Pack semantic input. Классифицировать по consuming projection; не назначать source revision любому UPDATE worlds |

**Предел полноты:** таблица покрывает выявленные writers перечисленных доменов; не доказано отсутствие иных generic repository aliases, raw SQL, cascade-delete и import/bootstrap путей. Полноту проверять от таблиц World/location/member/body назад к callers, а не только поиском имени сервиса. Для каждого writer обязателен исход INCLUDE (влияет на captured semantic input), EXCLUDE с consumer-доказательством либо DERIVED с правилом повторного использования. Без классификации всех строк нельзя объявить общий source mutation interception завершённым.

## 2. Транзакционные механизмы: точное различие V1/V2

[Database.transaction_if_needed](../../backend/app/db/database.py) поддерживает внешнюю UOW и task-owned `_in_transaction`. BaseRepository использует этот flag для подавления локального commit. LibraryWriteExecutor также проверяет flag и owns_unit_of_work.

[SqlitePublicationCommitStore._transaction](../../backend/app/db/repositories/sqlite/snapshotCore/commitScope.py) отказывает при уже существующей ambient UOW/transaction, сам выдаёт CommitScope и обрабатывает unknown commit outcome/quarantine. Он не эквивалентен Database.transaction_if_needed и не устанавливает V1 flag как контракт для legacy repositories.

[SqliteArtifactScope.bind](../../backend/app/db/repositories/sqlite/artifacts/access/artifactScope.py) **уже позволяет** присоединить artifact операции к выданному CommitScope. При bind последующий transaction использует текущий scope. [SqliteArtifactHolders.acquire](../../backend/app/db/repositories/sqlite/artifacts/holderStore.py) проверяет catalog/seal/holder и добавляет hold в этом scope. Следовательно, scoped hold механизм есть; второй holder store не нужен.

**Недопустимое соединение:** войти в Database.transaction, затем вызвать обычный unbound holders.acquire и ожидать общую атомарность. Он попробует открыть publication transaction, которая запрещает ambient transaction. Обратное соединение (publication scope + старый BaseRepository writer) также нельзя объявить безопасным без адаптации commit suppression и проверки ownership.

**Проект адаптации:** сохранить доменные prepare и алгоритм apply, перевести физические writers на scope-bound repositories через существующие CommitScope/IDomainCommitBinding/ScopedSqliteAccess. Внешний owner операции владеет одной transaction; artifacts получают bind этого же scope. Legacy executor больше не проверяет только boolean flag вместо capability. После gameplay owner — Snapshot. До gameplay сохраняется ответственность существующего mutation entry, внутренний adapter использует общий commit infrastructure; новый публичный Source orchestrator из этого не следует.

Приёмка: zero nested BEGIN/COMMIT, одинаковый scope у domain rows/revision index/holds, отказ на foreign DB/task/expired/read-only scope до SQL, rollback всех трёх групп, проверка unknown commit outcome существующим recovery-протоколом.

## 3. Предлагаемые данные Source: владельцы и поля

Все новые records — `dataModel/sourceVersioning/`, strict/frozen/extra-forbid/revalidate-always, tuple вместо list/dict. EntityUid, RevisionHex, ArtifactRef и Planning refs переиспользуются. Ниже **проект**, не существующие классы. SQL spelling и class naming не заменяют согласование семантики.

| Тип / модуль | Поля / ответственность | Отказ |
|---|---|---|
| SourceRevision, sourceObjectRevision.py | `seq: strict int > 0`, `content_hash: RevisionHex`; только semantic identity | bool/int coercion, nonpositive seq; label не включать в semantic equality |
| SourceObjectId, sourceObjectId.py | Discriminated union identity категорий из Source-design: registry member `(world_uid, registry, member_key)`, library member `(template_uid)`, entity `(entity_uid)`; отдельные варианты settings projection и collection | Универсальная строка kind/container; смешение body identity и collection identity |
| SourceVersionRef, sourceVersionRef.py | `object_id: SourceObjectId`, `revision: SourceRevision` | Ref не содержит mutable body, storage backend или latest-resolver |
| SourceBodyVersion, sourceBodyVersion.py | `source: SourceVersionRef`, `body: ArtifactRef` | Artifact format должен соответствовать owning source contract; hash semantic projection не приравнивается автоматически hash полных body bytes |
| SourceTombstoneVersion, sourceBodyVersion.py | `source: SourceVersionRef`; отдельный discriminator tombstone | Отсутствие body не трактуется как storage miss живой записи; старые версии не перезаписываются |
| SourceCollectionBody, sourceCollection.py | Полный канонический `members: tuple[SourceObjectId, ...]` для конкретной collection identity | Duplicate members; неизвестный порядок: semantically ordered коллекции нельзя сортировать как множества |
| SourceCapture, sourceCapture.py | `world_uid: EntityUid`, `objects: tuple[SourceBodyVersion, ...]`, `collections: tuple[SourceBodyVersion, ...]`, canonical capture identity | Смешанные worlds, две revisions одной identity, incomplete required collection; capture не выдаёт сам себе удержание |
| SourceDependencySet, sourceDependencies.py | `objects: tuple[SourceVersionRef, ...]`, `collections: tuple[SourceVersionRef, ...]` | Нельзя перечислить лишь выбранные bodies, если алгоритм зависел от состава кандидатов |

**Незакрытый точный параметр identity:** тип registry/settings/collection key должен происходить из owning registry, не enum с произвольно скопированными именами SQL колонок. WorldSlice содержит несколько world_keys для scalar-проекций; его Python class нельзя передавать по публичному контракту. До кода нужен полный roster source descriptors → owning typed key → поля проекции → codec. Эта таблица не выдаётся за уже выполненную.

**Authored-presence:** owning body codec обязан восстановить различие отсутствующего поля и явно заданного default, где оно семантическое. Hash считается существующим canonical механизмом над owning semantic projection + необходимой authored-presence. `model_dump` со всеми defaults сам по себе не является доказанным решением. При semantic equality label-only update не увеличивает seq; label хранится отдельным audit stamp, как требует Source-design.

## 4. Контракт чтения и изменения: проект для приёмки

Публичный CRUD остаётся у владельцев данных. Source не становится центральным фасадом, вызывающим все домены. Механизм revision storage — внутренний scope-bound collaborator существующих apply/read adapters. DTO read не содержит CommitScope/lease/backend; runtime capability передаётся только внутренним binding.

- **Create:** owning prepared change с отсутствующей expected revision. Внутренний apply проверяет отсутствие identity, sealed body и корректность projection, создаёт первую revision и membership change. Occupied identity — конфликт, не overwrite.
- **Update:** owning prepared change с `expected: SourceVersionRef` и новым sealed body. Atomic compare текущей revision; semantic change → следующий seq; semantic equality → прежняя revision. Label-only audit не меняет semantic identity. Конкурентное изменение → типизированный конфликт.
- **Delete:** expected ref → новая tombstone revision + изменение membership; historical held bodies не удаляются. Повтор того же operation подтверждается сохранённым receipt, не новой tombstone каждый раз.
- **Read exact:** `SourceReadRequest[T](source: SourceVersionRef, contract: SourceReadContract[T])` → `SourceReadResult[T](source, body: ArtifactRef, value: T)` либо `SourceReadRefusal`. Contract — зарегистрированный typed descriptor, не Python type/codec от caller. Historical read не fallback-ится на latest; выход полностью материализован/immutable.
- **Capture:** owning read получает явную согласованную publication/read boundary и требуемые descriptors; возвращает готовый SourceCapture и typed values. Выбор следующих producers делает DAG. Capture не создаёт revisions и не запускает генерацию.
- **Настройки:** semantic settings читаются/изменяются owning domain CRUD с тем же revision механизмом. Технические бюджеты storage не превращаются в mutable settings API Source. Их source/config и admission фиксируются composition отдельно.

**Проект ошибок:** `SourceIssueCode` с INVALID_IDENTITY, DUPLICATE_IDENTITY, WRONG_WORLD, REVISION_CONFLICT, UNKNOWN_CONTRACT, UNSUPPORTED_FORMAT, MISSING_BODY, UNSEALED_BODY, MISSING_HOLD, INCOMPLETE_COLLECTION, TOMBSTONE; конкретный `SourceFieldIssue(FieldPathError[SourceIssueCode])`, отдельный logic issue с expected/actual source refs. Публичный failure содержит operation + immutable tuple issues, infrastructure exceptions не превращаются в not-found. Агрегировать независимые field issues существующим [ValidatorAggregationHelper](../../backend/app/dataModel/validation/diagnostics/validatorAggregationHelper.py); путь в skill `app.core.validatorAggregationHelper` устарел, новый helper не создавать.

## 5. Проект хранения и атомарности

Изменения SQL только в `0001_initial.sql` и синхронных db/models после приёмки. Предлагаются логические relations (ещё не DDL):

1. **source_object_revisions:** typed identity columns, seq, semantic_hash, live/tombstone discriminator, nullable body artifact catalog identity, mutation operation identity. Unique `(typed identity, seq)`; live требует body, tombstone запрещает live body. Semantic hash не unique: возврат A→B→A даёт новый seq при прежнем hash.
2. **source_mutation_receipts:** operation identity, canonical prepared input fingerprint, immutable результаты назначенных revisions. Повтор идентичного запроса возвращает прежний результат; другой fingerprint под тем же ID — конфликт. При наличии подходящего existing operation receipt его адаптировать, не дублировать автоматически.
3. **source publication membership/index:** соответствие атомарного опубликованного source set точным SourceVersionRef. Latest может быть только восстанавливаемой projection; authoritative history append-only. Concrete связь с existing publication IDs остаётся отдельным schema gate, не подразумевается наличием UUID.

Collection body хранится через тот же Artifacts, как и body объекта; не заводить второй blob store. SQL index не выдаёт blob за held автоматически. Перед publication body должен быть sealed и защищён staging hold; внутри commit acquired published/dependency holds и revision mapping становятся видимы совместно. Cancel/rollback не снимают удержания уже опубликованных revisions. GC eligibility проверяется владельцем Artifacts по реальным holds.

**Подтверждённый незакрытый шов staging:** IArtifactStaging.open_operation требует OperationKind; сегодня enum содержит только SNAPSHOT_APPLY/PACK_ACTIVATION/GAMEPLAY_START. Existing V1 writers не получают OperationLeaseRef. Поэтому существующая SQL UOW решает атомарность SQL, но сама не даёт stage lease для нового source body. Нельзя выдавать source edit за PACK_ACTIVATION. Для pregame записи нужен принятый внутренний lifecycle staging (расширение существующего либо иной owning port), без предположения о новом публичном доменном входе. Это конкретный gap по коду, а не вывод только из названия enum.

**Другой незакрытый шов:** долговременный owner latest/source revisions до появления Pack/Snapshot. ArtifactRetentionHolder требует sealed owner artifact; SQL revision row не является допустимым holder. Выбор: source-owned root artifact с доказанным удержанием самого root либо расширение общего holder-контракта typed source revision owner. Ни фиктивный PinHolder, ни self-hold без release lifecycle не принимаются. Решение необходимо до DDL/GC реализации; нельзя скрыть его в bare acquire(ref).

## 6. Связь результата и proof: проект

Конкретная граница Pack вынесена в [pack-v2-domain-contract-spec.md](pack-v2-domain-contract-spec.md). Ниже — предложение структуры evidence, не изменение утверждённого Pack ТЗ и не назначение Source CRUD домену Pack. В частности, public activate остаётся у Pack, внутренний transaction mechanism — у publication.

Producer сообщает реальные зависимости, а не Source угадывает их из выходного hash. Source подтверждает версии/тела/удержания. Pack проверяет соответствие адресу и payload. Передача междоменных результатов — через DAG.

Актуальная структура persisted proof после согласования границ Source/producer/Pack:

- `PackStoredProvenance`: `source_proof: SourceDurableProof`, `planning: tuple[PlanDependency, ...]`. Название SourceDurableProof обозначает внешний разрабатываемый контракт владельца Source, а не готовое объявление runtime. Прежнее предложение раскрывать dependencies/source_bodies непосредственно в Pack отозвано: owning Source proof определяет exact revisions, membership и body closure; Pack не копирует его поля. Planning dependencies переиспользуются из существующего dataModel/planning, не дублируются внутри source_proof.
- `PackStoredPart`: уже предложенные address, artifact, provenance. Producer evidence при admission должно связывать **все три**. Нельзя считать произвольно собранный POJO доказательством, что именно этот producer создал artifact; нужен подтверждаемый producer outcome/receipt из подготовительной цепочки.
- `PackStoredAssemblyProvenance`: address + provenance, evidence связывает точную semantic metadata projection. Её fingerprint считается существующим codec по owning схеме, не repr/dict order.

Это уточнение распределения ответственности, а не молчаливое переименование `<proof Source>` из ТЗ. Перед freeze синхронизировать owning Source/producer/Pack contracts: какой тип является durable proof, какой — transient admission evidence. Operation leases, capture holder и receipts не сохраняются как необходимая runtime-зависимость читателя manifest. При inherited ref/адрес/proof сверяются с pinned base и переносятся неизменно.

### 6.1. Адаптация найденных механизмов к целевому Pack — без доменной оркестрации

По поручению пользователя 2026-11-12 адаптируется **передача данных и проверок**, а не legacy call graph. При этом применяются уже действующие границы из `.cursor/rules/dag-generator-interface.mdc` («Обязательная приёмка плана любого домена»); напоминание пользователя не является новым архитектурным решением. Source proof реализуется владельцем Source отдельно; эта карта не назначает его разработку Pack и не меняет параллельно уточняемую схему внешнего типа.

| Existing механизм | Использование в целевом контракте | Что запрещено переносить |
|---|---|---|
| SurfacePlanningCapture и immutable SurfacePlanningView/GeoSurfacePlanningView | Переиспользовать owning typed projections и canonical encoding при проектировании captured входов. StateViewRevision остаётся fingerprint projection, не SourceRevision и не свидетельство удержания | Capture не выбирает следующие домены, не вызывает их публичные read/compute pipelines. Если вход требует чужой публичной операции, её отдельно вызывает DAG и передаёт результат |
| SourcePublicationGuard.require_fresh → require_current_source | Legacy гарантия сохраняется до cutover; целевой вход использует уже закреплённые object/collection revisions и подтверждение удержаний | Не включать повторный latest-read/capture в Pack prepare/activate. Согласно принятому freeze in-flight изменение latest не отменяет готовящийся результат |
| PlanEnvelope(ref, dependencies, payload, diagnostics), PlanRef, PlanDependency | Producer получает готовые typed inputs и необходимые envelopes через DAG; проверяет exact expected refs, scope/world и fingerprints в границах своей операции. Pack сохраняет необходимые существующие PlanDependency в provenance | Не клонировать Planning POJO/codec и не вызывать соседний planner/provider из producer для получения недостающей зависимости |
| NativeRiverReliefPublicationJob.publish | Найденные сравнения input/output fingerprints, source mapping и expected refs служат инвентарём необходимых проверок | Его nested calls в FineWaterPublicationJob/соседние домены не принимаются как target DAG-путь. Перенос проверок требует owning pure contract либо передачи уже проверенного результата; Pack не копирует чужой алгоритм |
| OutputRecord/DependencyRead и PublishedDAGReadView | Engine связывает результат с вызовом и переносит доменный output на вход следующей согласованной операции | Не передавать engine record/сервис в Pack DTO; не считать факт чтения доказательством правильного mapping каждого поля |
| finish_pack_preparation / PreparedPackCandidate | Pack завершает собственную подготовку manifest/closure и возвращает подтверждённый candidate после READY | Не вызывать из prepare Source capture, producer materialize, Cache или activate; existing helper не объявлять полным proof admission |

**Конкретное соответствие полей:** domain producer output содержит его собственные адресуемые результаты, точные ArtifactRef, source proof и Planning dependencies по owning контракту. Согласованный DAG binding переносит их без вычисления доменной семантики в `PackPartInput(address, artifact, provenance)`. Для new используется `PackNewPartProvenance(kind="new", provenance=PackStoredProvenance(source_proof, planning))`, для inherited — `PackInheritedPartProvenance(kind="inherited", provenance=исходный полный provenance базы)`. Отдельный PackProducedPartEvidence не создаётся. Pack проверяет соответствие своему scope/assembly/coverage и закреплённой базе; producer не импортирует обязательный Pack result DTO. Stored part сохраняет address/artifact/полный provenance, без new/inherited и зависимости от временной engine session.

Metadata передаётся таким же способом как готовая typed projection; Pack сохраняет адрес metadata и полный provenance. SourceDurableProof/schema/codec остаётся внешним точным входом, не заменяется StateViewRevision, PlanRef, dict или ArtifactRef без owning контракта. Нужные source refs входят в closure по этому контракту; при read готового payload Source CRUD не вызывается.

**Оркестрация только в DAG:** выбор операций, условий запуска, retry после conflict/miss, получение отсутствующих dependencies, порядок L0 → topology и L2 → settlement materialization. Нельзя скрыть эту ответственность в SourceCaptureOperation, materialization facade, PackPreparationOperation, callback или worker. Локальный алгоритм одной атомарной операции не даёт права запускать самостоятельные публичные операции даже того же домена. Внутренние storage/scoped ports допустимы только в уже принятой ответственности одной операции, не как лазейка для вызова чужого pipeline.

**Приёмка адаптации:** предъявить concrete owner method → output POJO → поля consumer input → согласованный DAG binding; проследить вложенные вызовы. Отдельно проверить смешение refs/proofs разных outputs, отсутствие требуемого source body, membership change, inherited B при новом A и restart с закрытой session. Пока внешний Source type и bindings не предъявлены, весь маршрут OPEN. Это не новая система хранения proof, не новый OperationKind и не перенос реализации внешних доменов в Pack. Runtime не изменён.

## 7. Приёмка классов и зависимостей

| Компонент | Роль / эффекты | Отказ в приёмке |
|---|---|---|
| Existing domain planners/validators | Локальные pure правила и подготовка изменений | SQL/commit или запуск другого domain pipeline |
| Scope-bound domain writer | Применение уже подготовленного body/membership в переданном scope | Собственный commit, latest read вместо expected revision, derived output без классификации |
| SourceRevisionStore (проект) | Append/read revision mapping и receipts; не body codec | Выбор producer, семантическая проекция чужой модели, отдельный commit |
| Owning source codec/projector | Typed body + semantic/authored-presence representation | Второе hash-ядро, неполный round-trip, IO при pure validation |
| Source capture adapter | Согласованный read и materialized immutable result | Назначение seq, lazy service в POJO, смешанные snapshots |
| Artifact ports | Seal, holds, GC, bounded read | Удержания SQL row выдаются за artifact holder без контракта |
| Pack assembler/codec | Единственный полный manifest, проверка evidence/address/schema | Запуск source read/producer, перезапись proof inherited части |
| Existing publication/Snapshot owner | Scope, atomic apply, outcome/recovery | Materialization внутри apply или самостоятельный commit домена после gameplay |

Эта таблица — обязанности ролей; окончательный список конкретных классов, точные signatures ошибок и source descriptors ещё должен заменить роли перед приёмкой. DAG-ноды здесь не назначаются. Доменная поставка не зависит от миграции внешних consumers, но публичный маршрут нельзя объявлять проверенным без конкретного binding.

## 8. Обязательные проверки и оставшиеся решения

1. Create/update/delete/replay: expected revision, same-ID different fingerprint, A→B→A, label-only, tombstone + historical read.
2. Capture во время membership/body изменения видит один snapshot; добавленный candidate меняет relevant collection dependency даже при прежнем выбранном member.
3. World bundle failure откатывает domain rows, revision index, receipts и published holds. Foreign/expired/read-only scope даёт отказ до записи.
4. Restart восстанавливает captured bodies и authored-presence; missing/corrupt/unsealed body не становится default или not-found.
5. Refine A сохраняет B/ref/proof; release исходной версии не освобождает тела новой версии; GC и concurrent release не выигрывают race с adoption.
6. Одновременная порча двух независимых полей даёт обе typed diagnostics в стабильном порядке; зависимый writer не вызван.
7. Для каждого writer из roster тест доказывает INCLUDE accounting либо EXCLUDE/DERIVED policy; общая зелёная проверка WorldService не покрывает repair/bulk/library paths.

**Состояние приёмки: НЕ ПРОЙДЕНА.** Конкретизированы контрактные формы, операции, схема relations, точки adaptation и тесты; остаются owning descriptor roster и classification writers, pregame staging lease/retention root, exact publication index mapping и producer outcome binding. Это не четыре повторных запроса разрешения: уже выбранное хранение и переиспользование V1 остаются принятыми. Следующий design review должен решить именно эти технические варианты и проверить их против Source/Artifacts/Snapshot SoT. Runtime, SQL и DAG этой спецификацией не изменяются.
