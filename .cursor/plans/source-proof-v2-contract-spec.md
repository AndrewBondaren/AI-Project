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

### Проверка POJO для SourceDurableProof — 2026-11-13

Актуальная проработка — §6.0.A–H этого документа; старый отдельный single-capture проект `source-durable-proof-contract.md` не является основой реализации. Следующий inventory identity/descriptor dependencies приведён в §3.1. Приведённый ниже аудит отражает исходные пробелы, а не отменяет последующие конкретизации.

По поручению пользователя проверены проект ниже, §6, требования `docs/tz_world_pack_storage.md` к freeze входа и существующие `dataModel/artifacts/references.py`, `dataModel/planning/contracts/planDependency.py`, `dataModel/validation/diagnostics/fieldPathError.py`. Результат: **NOT ACCEPTED / OPEN**. Фиксируется результат проверки, не утверждение схемы и не разрешение реализации. Объявлений SourceDurableProof, SourceCapture, SourceDependencySet и SourceVersionRef в `backend/app/dataModel` при проверке не обнаружено.

| Тип, владелец и предлагаемый модуль | Проверка полей, ответственности и границ | Результат |
|---|---|---|
| SourceRevision — Source, sourceObjectRevision.py | `seq` и `content_hash` описывают историю и semantic identity. Не заменять StateViewRevision или hash полных artifact bytes. Positive strict int исключает bool. A→B→A требует новой seq при возможном прежнем hash. | Форма определена; codec и semantic projection требуют принятия |
| SourceObjectId — Source, sourceObjectId.py | Нужны конкретные варианты и owning typed keys для registry member, library member, entity, settings projection и collection. Общая строка либо dict не закрывают union. | OPEN: roster и полный состав полей отсутствуют |
| SourceVersionRef — Source, sourceVersionRef.py | `object_id`, `revision`; не хранит body, resolver или storage capability. | OPEN вследствие SourceObjectId |
| SourceBodyVersion / SourceTombstoneVersion — Source, sourceBodyVersion.py | Live связывает `source` с существующим ArtifactRef; tombstone не имеет live body. Необходимо точно объявить discriminator обоих вариантов и допустимые body formats. | OPEN: union/codec не завершены |
| SourceCollectionBody — Source, sourceCollection.py | `members: tuple[SourceObjectId, ...]`; уникальность до нормализации. Порядок должен определять owning collection contract: ordered sequence нельзя сортировать как set. | OPEN: типизированная identity коллекции и semantics порядка |
| SourceCapture — Source, sourceCapture.py | `world_uid`, `objects`, `collections`; общий SourceBodyVersion пока не исключает object ref в collections. Нужны точная capture identity, правила глобальных library identities и согласованная read boundary. | OPEN: canonical capture identity не объявлена полем конкретного типа |
| SourceDependencySet — Source, sourceDependencies.py | `objects`, `collections` фиксируют прочитанные revisions, включая состав кандидатов. Не дублирует capture: capture фиксирует доступный набор, dependencies — фактически использованный набор. Проверяется принадлежность captured set. | OPEN: distinction object/collection и identity |
| SourceDurableProof — Source, sourceDurableProof.py | Проект публичного импорта: `app.dataModel.sourceVersioning.sourceDurableProof.SourceDurableProof`. Полная схема не определена; не заменять произвольным ArtifactRef, пустым record или копией полей Pack. | OPEN; публичного runtime импорта ещё нет |
| SourceFieldIssue / Source logic issue / failure — Source, модуль требует определения | Field issue должен быть именованным concrete subclass существующего FieldPathError с `code`, `path`, `message`. Logic issue требует отдельного точного состава полей и кодов, failure — operation и immutable issues. Нельзя считать список кодов из §4 полноценным error contract. | OPEN: модули, discriminators, логические варианты и полная схема failure отсутствуют |
| ArtifactRef — Artifacts, artifacts/references.py | Переиспользовать `kind`, `format_key`, `format_version`, `content_hash`, `nbytes`, `row_count`. Existing frozen/strict/extra-forbid/revalidate-always; SQL_ROWS требует row_count, BLOB запрещает его. Ref удостоверяет content identity, не seal/hold/source semantic revision. | Собственная схема подтверждена; Source format binding OPEN |
| PlanDependency — Planning, planning/contracts/planDependency.py | Переиспользовать `slot`, `ref`; unique slots и canonical UTF-8 order проверяет существующий require_canonical_dependencies. Planning dependencies остаются в PackStoredProvenance.planning. | Не копировать в Source proof; existing helper должен применяться owning validator |
| PackStoredProvenance — Pack, проект worldPack/preparation/provenance.py | `source_proof: SourceDurableProof`, `planning: tuple[PlanDependency, ...]`. Pack хранит внешний proof без раскрытия Source body/dependency полей; new/inherited относятся к admission wrappers. | Структурная совместимость подтверждена, точный внешний binding OPEN |

Все новые Source records требуют strict/frozen/extra-forbid/revalidate-always и глубоко immutable вложений. Независимые field errors агрегируются с исходными путями в стабильном порядке существующим ValidatorAggregationHelper. Дублирование Source revision, Artifacts identity, Planning dependency или общего FieldPathError не разрешено. Отсутствие полного union и error roster не позволяет доказать отсутствие всех пересечений POJO; общий POJO gate не закрыт.

**Проверка proof и closure.** Структурная валидация не доказывает происхождение. Нужны отдельно: проверка точного finalized capture и dependency membership без latest-read; проверка доступности исторических bodies/collection bodies и их owning codecs; полное перечисление durable ArtifactRef владельцем Source; scoped-проверка удержаний и их передача при общем commit, защищённая от concurrent release. Сигнатуры и concrete публичные классы этих операций пока не предъявлены — это требования к контракту, не существующие методы. Пустой closure при неизвестном binding запрещён. Предварительная проверка через DAG не заменяет scoped adoption. Persisted proof не требует живой engine session или временного lease.

**Сверка Pack.** Полный source_proof и planning наследуются неизменно относительно pinned base. Новая версия должна удерживать весь необходимый closure после release старой версии и restart. Дедупликация storage refs не удаляет отдельные provenance uses одного BLOB по разным адресам. Связь output artifact/metadata projection с capture подтверждает producer binding; Source revision set не доказывает исполнение producer. Pack не создаёт proof и не вызывает публичный Source pipeline напрямую; результаты междоменных операций передаются через DAG. Внутренний scoped storage binding требует отдельной конкретной приёмки и не разрешает обход этого запрета.

**Зависимости и предлагаемый порядок для согласования:** (1) owning identities/projections/codecs для выбранных входов Pack; (2) durable capture и authoritative revision/publication mapping; (3) Source retention owner, независимые holds и scoped adoption/release; (4) точные proof/validation/closure POJO, ошибки, concrete публичные методы и codec; (5) producer mapping и согласованный DAG binding. Это порядок зависимостей, не новый утверждённый execution DAG. Не расширяет задачу до всей миграции Source; полноту writers проверять для выбранного captured scope. Полную миграцию и новые ноды этим документом не назначать.

**Обязательная приёмка:** три запрета DAG сохраняются (нет выбора маршрута pipeline, скрытого запуска или прямых междоменных публичных вызовов); фактический маршрут пока отсутствует. Ответственность POJO указана выше, но concrete классы операций, вложенные вызовы, Input/Output/field-error/logic-error и CRUD данных/настроек не предъявлены. Утверждённый порядок исполнения не изменяется; предложенный порядок поставки ещё требует согласования. Поэтому ни весь домен Source, ни рабочий SourceDurableProof срез не приняты. Реализация — только через implement-plan после принятия конкретного среза. Этот аудит изменяет только документацию.

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

### 3.1. Результат инвентаризации identity и entry contracts — 2026-11-13

Это продолжение **шага 1** основного плана, не перескок к установке `__source_contract__` (шаг 2). Проверены actual `WORLD_SLICES`, их root annotations и declared overlay/merge identity. Read-only Python introspection выполнена с `-B`; доменные поля и runtime не изменены. Поиск SourceObjectContract/SourceRevision/SourceObjectId/__source_contract__ в backend/app не обнаружил реализации.

Источник: `application/jsonValidation/worldSlices.py::WORLD_SLICES`, всего **36**: 6 multi_column, 25 registry_list, 4 json_blob, 1 registry_dict. Из registry_list 24 содержат entry POJO, один — строки. Это полный roster текущего WORLD_SLICES, но не всех source inputs мира: library members, entities, raw SQL writers и selection dependencies проверяются отдельно. Наличие в WORLD_SLICES не означает автоматическое INCLUDE в Source.

| World key | Entry POJO | Кандидат owning identity field, подтверждённый объявлением поля |
|---|---|---|
| economic_tier_registry | EconomyTierEntry | system_tier |
| material_registry | MaterialRegistryEntry | system_material |
| resource_type_registry | ResourceTypeEntry | system_resource |
| crops_registry | CropsTypeEntry | system_crop |
| livestock_registry | LivestockTypeEntry | system_livestock |
| terrain_registry | TerrainRegistryEntry | system_terrain |
| climate_zone_registry | ClimateZoneEntry | system_climate |
| barrier_template_registry | BarrierTemplateEntry | system_type |
| city_size_registry | SettlementSizeEntry | system_size |
| settlement_specialization_registry | SettlementSpecializationEntry | system_specialization |
| district_template_registry | DistrictTemplateEntry | system_name |
| district_zone_preference | DistrictZonePreferenceEntry | zone |
| road_settings | RoadSettingsEntry | system_connection_type |
| connection_type_registry | ConnectionTypeEntry | system_connection_type |
| transition_type_registry | TransitionTypeEntry | system_type |
| location_type_registry | LocationTypeEntry | system_type |
| weather_type_registry | WeatherTypeEntry | system_weather |
| terrain_category_registry | TerrainCategoryEntry | system_category |
| room_type_registry | RoomTypeEntry | system_room |
| location_mood_registry | LocationMoodEntry | system_mood |
| race_template_registry | RaceTemplateRegistryEntry | system_template_uid |
| perk_template_registry | PerkTemplateRegistryEntry | system_template_uid |
| purpose_pack_registry | PurposePackEntry | system_pack |
| canal_template_registry | CanalTemplateEntry | system_type |

Колонка identity — inventory, не автоматическая декларация Source. Полноту uniqueness/rename/ref-integrity для каждого кандидата надо доказать от owning contract и writer. Overlay/merge fields не заменяют эту проверку. DistrictZonePreferenceEntry.zone — enum CellZone, многие registry fields — RegistryKey[OwningRegistry], часть остаётся StrictOnWire[str]; единый permissive str key стёр бы эти различия. PurposePackEntry.system_pack дополнительно имеет owning BeforeValidator: применение нормализации не должно менять identity при exact historical resolve.

**Оставшиеся 12 slices:**

- Multi-column: WorldPackMetadata, WorldMapResolutionSettings, WorldGridSettings, WorldClimateScalars, WorldTerrainScalars, WorldReliefGradeObstacleScalars. У них нет entry key_field; identity settings projection должна задаваться отдельным accepted descriptor. WorldPackMetadata содержит terrain_pack_path/hash — publication output, его нельзя без consumer trace включить в source hash и получить зависимость результата от самого себя. Climate/Terrain scalars содержат parallel_workers: исключение execution policy из Planning fingerprint не автоматически означает такое же исключение из Source revision.
- JSON blob: WorldEnvironmentSettings, WorldHydrology, WorldTerrainMasks, WorldReliefPickPolicy. Нужны owning semantic projection и правила вложенных объектов/коллекций; один world_key не доказывает, что весь blob — одна source identity.
- WorldLoreRegistry — RootModel[dict[str, LoreRegistryEntry]]: identity расположена в ключе map, а не в поле entry. Нельзя добавлять фиктивный key_field внутрь LoreRegistryEntry. Должен быть принят container-key adapter либо обоснованное EXCLUDE для выбранного captured scope.
- WorldPurposePacks — RootModel[list[str]] с owning coerce_purpose_packs: это membership enabled ids, а не entry objects. Нужны collection identity, semantics порядка/duplicates и stable canonical membership; не создавать wrapper entry ради единого projector.

**Library/entity boundary:** existing TemplateEntry[T] (`application/templateLibrary/templateContracts.py`) содержит template_uid/pack_uid/body и проверяет canonical UUID; body key может отличаться от catalog identity. SourceObjectContract на body не должен заменить template_uid значением system_name. WorldTemplateSnapshot запрещает пересечение UID между поддержанными доменами, но не является историческим revision/hold witness. Entity identifiers остаются owning EntityUid/declared keys; identity схемы authored/derived locations ещё требуют classification из §1, не считаются закрытыми данным registry inventory.

#### Декларация SourceObjectContract: конкретный кандидат шага 2

Сохранить выбранный основным планом `dataModel/sourceVersioning/sourceObjectContract.py::SourceObjectContract`: frozen typed dataclass с `key_field: str`, `exclude_fields: tuple[str, ...] = ()`, размещаемая как ClassVar `__source_contract__` entry POJO. Никаких body/schema/holder/codec/Pack imports в этой декларации. В ней нет Runtime CRUD и allocation revisions.

До регистрации projector проверяет: имена непустые и существуют среди owning model_fields; key_field один, не excluded, соответствует допустимой immutable scalar identity; exclude_fields уникальны, не содержат неизвестных полей. Нельзя угадывать display/lore исключения по похожему имени: каждой записи нужен owning consumer trace. Default «все поля semantic, кроме явно объявленных» сохраняется. Изменение значения identity означает новую identity/tombstone по основному плану, а не очередную revision прежнего ключа.

Проверка наличия полей не выполняется самим dataclass без owning модели. Proposed internal `SourceContractInspector`, `application/worldData/sourceVersioning/contracts/sourceContractInspector.py`, выполняет pure registration check над owning model + declaration и выдаёт existing Source field diagnostics, не читает DB и не создаёт типизированные версии. Полная Input/Output/Error сигнатура inspector принимается вместе с registry descriptor; только это описание не разрешает его код.

**Authored presence:** TerrainRegistryEntry.has_authored_hills использует model_fields_set. Канонизация полного model_dump с defaults не сохраняет отсутствие против explicit default. В roster будущего projector для каждого семантически чувствительного поля обязательно указать preservation path и round-trip check. Показать хотя бы hills отсутствует / явно None / explicit policy; semantic equality определяет owning codec, не общий Source сериализатор.

#### Конфликт импортов, который требуется решить до identity POJO

Основной план запрещает dataModel/sourceVersioning импортировать domain entry/registry POJO, потому что те импортируют SourceObjectContract. Прямое объявление RegistryMemberId с полями RegistryKey[WorldTerrainRegistry] и аналогами внутри Source namespace нарушило бы это направление. Предыдущая фраза «взять owning typed keys» без места binding была недостаточной.

Кандидат решения для design review: базовая декларация SourceObjectContract остаётся dependency-free от доменов; descriptor→owning key adapter и codec связываются в application composition поверх WORLD_SLICES. Публичная identity должна ссылаться на зарегистрированную Source-owned descriptor identity, а значение ключа проверяется owning adapter. Однако конкретный carrier значения ключа (типизированный union категорий, без универсальной str/Any дырки), registry identity/версии и его canonical representation **ещё нужно предъявить**. Не выдавать application registry по имени за разрешение untyped публичного ID. Альтернатива с переносом всех ключевых типов/реестров в neutral namespace потребовала бы отдельного междоменного scope и этим планом не назначается.

**Выход шага:** получен проверенный roster 36 slices, 24 entry identity кандидата и четыре разных формы источников, локализованы import-cycle и key_field gaps. Не закрыты общий source descriptor union, включение/исключение каждого input по consumer evidence, semantic field policies, membership ordering и body codecs. Следующее действие шага 1 — concrete descriptor/key carrier и его application binding, затем consumer trace выбранного captured набора; не установка одинакового __source_contract__ на все 36 моделей. Это Source работа, Pack files/POJO не меняются. Полная приёмка шага 1 пока не пройдена.

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

### 6.0. Ядро Source для proof — уточнение 2026-11-13

Статус: конкретный проект для приёмки, не runtime и не утверждённое изменение основного дизайна. Главный план — `world-source-versioning.md`; этот документ владеет технической детализацией интеграции. Source — вспомогательный механизм: не универсальный CRUD мира, не Pack assembler и не владелец artifact GC. Application размещение следует основному плану: `app.application.worldData.sourceVersioning`; POJO — `app.dataModel.sourceVersioning`.

**Снятое предложение:** индексы objects/collections внутри одного capture из `source-durable-proof-contract.md` не принимаются как основа реализации. В основном дизайне dependencies — точные SourceVersionRef, а при частичном обновлении исторические основания не переписываются. Ни однократный capture новой операции, ни его полный closure не заменяют provenance всех использованных результатов. Удержание всего capture как обязательная политика также не принято. Отдельные Source документы являются вспомогательными материалами, не вторым основным планом.

#### A. Состав и смысл POJO

Публичный импорт кандидата: `app.dataModel.sourceVersioning.sourceDurableProof.SourceDurableProof`. Все модели frozen/strict/extra-forbid/revalidate-always, коллекции tuple, обязательные поля без неявных defaults. Поля ниже — полный состав новых records; существующие проектные SourceRevision/SourceVersionRef/SourceDependencySet из §3 не копируются.

| Модуль в dataModel/sourceVersioning | Тип / поля | Ответственность |
|---|---|---|
| sourceCaptureRef.py | SourceCaptureRef(`world_uid: EntityUid`, `artifact: ArtifactRef`) | Exact ref immutable finalized capture; owning format и финализация должны проверяться. Это не hold и не произвольный BLOB |
| sourceCaptureUsage.py | SourceCaptureUsage(`capture: SourceCaptureRef`, `dependencies: SourceDependencySet`) | Заявленные использованные object/collection revisions одного capture. Не список всех доступных inputs |
| sourceDurableProof.py | SourceDurableProof(`uses: tuple[SourceCaptureUsage, ...]`) | Канонический набор исторических source dependencies одного результата; без Pack address, output artifact, Planning dependencies и capabilities |
| sourceProofInput.py | SourceProofInput(`world_uid: EntityUid`, `uses: tuple[SourceCaptureUsage, ...]`) | Заявка admission/нормализации: world ожидание и реально сообщённые producer зависимости; не готовое удостоверение |
| sourceProofInput.py | SourceProofReadInput(`world_uid: EntityUid`, `proof: SourceDurableProof`) | Проверка уже сохранённого proof без его переписывания |
| sourceProofResult.py | SourceProofResult(`proof: SourceDurableProof`, `durable_refs: tuple[ArtifactRef, ...]`) | Полностью проверенные source зависимости и вычисленный closure на момент чтения; не retention token |

SourceProofInput и SourceDurableProof имеют разную семантику: input допускает неканонический порядок/повторные usage одного capture для объединения, output — единственное каноническое представление. Отличие должно быть отражено validators, а не только именами. SourceProofReadInput не вызывает нормализацию сохранённого proof: повреждённая persisted canonical форма отклоняется.

SourceDependencySet остаётся `objects: tuple[SourceVersionRef, ...]`, `collections: tuple[SourceVersionRef, ...]`. Его identity discriminators обязаны отличать объекты и коллекции; точный roster §3 остаётся необходимым до кода. Нельзя заполнить отсутствующий identity contract универсальными строками или Python type от caller. SourceCaptureRef предполагает отдельное registered capture representation; concrete codec/index остаётся dependency C ниже, не готовым существующим форматом.

#### B. Нормализация и конфликтные revisions

1. Проверить форму всех доступных полей, world ожидание каждого usage и полную identity capture. Bool не принимается за seq; seq положительная; semantic hash не приравнивается hash body bytes.
2. Повтор exact source ref в группе объединяется как set. Повтор одного capture объединяется только по full SourceCaptureRef. Одна identity с двумя revisions внутри **одного capture** — отказ; несовпадающие body mappings одной exact revision — corruption. Canonical ordering задаёт existing CanonicalCodec после регистрации типов, не repr/stringification.
3. **Разные captures могут содержать разные revisions одной identity.** Их нельзя ни глобально склеить по object_id, ни произвольно выбрать latest. Группы сохраняют принадлежность capture. Source доказывает каждую группу отдельно; совместимость комбинации inputs относится к producer/consumer. Это необходимо, например, для metadata, часть полей которой сохранена из базы, а часть получена из новых inputs.
4. Для каждого dependency проверить membership именно в указанном finalized capture, revision equality и live/tombstone смысл owning read. Если потребитель зависел от состава кандидатов, collection dependency обязательна по producer declaration; Source не угадывает отсутствие таких чтений по списку объектов.
5. Source не выбирает допустимые captures за producer и не считает произвольный valid capture достаточным основанием результата. Producer/Pack сообщает и проверяет связь результата с реальными inputs; DAG переносит owning output без вычисления dependencies. Это две разные проверки.
6. Пустой uses допустим только как явное заявление об отсутствии source dependencies. Source возвращает пустой source closure, не утверждая полноту producer read-set; consumer обязан иметь основание для source-independent результата. Пустая группа без dependencies исключается при admission, но запрещена в persisted canonical proof. Отсутствующий/неизвестный proof никогда не заменяется пустым.
7. Label stamp не участвует в semantic SourceRevision equality; его отдельная audit схема остаётся детализацией основного плана. Повтор label не меняет seq и не создаёт новый semantic dependency. Source proof не вводит новый hash engine.

#### C. Durable refs: что именно удерживать

Для каждого употреблённого capture вернуть artifact, необходимый для проверки его durable identity/membership, исторические body artifacts выбранных объектов, collection body artifacts использованных коллекций и транзитивные Source artifacts, необходимые owning resolver/codec для проверки и exact resolve. Тела неиспользованных кандидатов не включаются автоматически только из-за перечисления их identity в collection membership.

**Обязательная оговорка:** минимальный выбор closure возможен только если accepted capture format отделяет membership witness от storage dependencies остальных тел. Если owning формат требует все referenced bodies, traversal обязан включить их все. Source не может выборочно пропустить ребро формата. Поэтому экономия subset — не утверждённое свойство схемы, а критерий проектирования capture codec. До принятия этого codec перечень refs нельзя объявить полным. Проект не добавляет holder/self-hold capture root.

Storage refs дедуплицируются по полному ArtifactRef; logical usage остаётся по capture и revision. Unknown format, missing/corrupt/unsealed required body, неразрешимый witness дают отказ, а не partial success. Cycle в исходном semantic graph не запрещается автоматически; traversal использует visited по exact identity, а admissibility retention graph определяет owning storage contract. Latest не читается. PlanRef/PlanDependency не преобразуются в ArtifactRef.

#### D. Минимальный публичный API

Concrete класс `SourceProofPipelineOpenPipeline`, модуль `app.application.worldData.sourceVersioning.sourceProofPipelineOpenPipeline`. Интерфейс `ISourceProofPipelineOpenPipeline` в `app.application.worldData.sourceVersioning.interfaces.sourceProofPipelineOpenPipeline` объявляет те же сигнатуры:

```python
async def admit(self, request: SourceProofInput) -> SourceProofResult | SourceProofFailure: ...
async def read(self, request: SourceProofReadInput) -> SourceProofResult | SourceProofFailure: ...
```

ADMIT: принимает реальный declared usage, проверяет exact captured dependencies, нормализует и возвращает proof + полный durable refs набор. READ: проверяет persisted proof и возвращает тот же proof + refs; не меняет historical identity. Отдельные create/verify/collect_refs, повторяющие один и тот же IO и возвращающие не связанные по времени ответы, не вводятся. Получение refs — обязательная часть обеих операций, не optional flag. Операции read-only; capture-finalize, запись revision и acquiring/releasing holds в них не спрятаны.

Вызов — прямо из согласованной DAG-ноды; следующие операции и retry выбирает DAG. Одна публичная Source операция не вызывает другую. Их общий внутренний алгоритм — exact read/validation/traversal одной операции, не orchestration соседних публичных pipelines. Durable refs результат не защищает окно после возврата: атомарная проверка исходного live holder и приобретение target hold относятся к принятому scoped Artifacts/publication binding. Приобретение target hold само по себе не снимает source hold; release/handoff выполняется только по owning lifecycle, после остановки соответствующих writers.

#### E. Ошибки и ответственность реализации

Предлагаемый `sourceProofErrors.py`:

- SourceProofOperation: ADMIT, READ.
- SourceProofFieldCode: INVALID_SHAPE, INVALID_IDENTITY, NON_CANONICAL_PROOF. SourceProofFieldIssue — concrete FieldPathError[SourceProofFieldCode] с inherited code/path/message; общий carrier не клонируется.
- SourceProofLogicCode: WRONG_WORLD, CAPTURE_NOT_FINALIZED, DEPENDENCY_NOT_CAPTURED, REVISION_CONFLICT, BODY_MAPPING_CONFLICT, UNSUPPORTED_FORMAT, MISSING_BODY, CORRUPT_BODY, UNSEALED_BODY, INCOMPLETE_CLOSURE.
- SourceProofLogicIssue: `code: SourceProofLogicCode`, `use_index: StrictInt` (ge=0), `source: SourceVersionRef | None`, `artifact: ArtifactRef | None`. None означает ошибку группы/capture без конкретного source/body. Индекс в ADMIT относится к исходному request, не отсортированному output.
- SourceProofFailure: `operation: SourceProofOperation`, `field_issues: tuple[SourceProofFieldIssue, ...]`, `logic_issues: tuple[SourceProofLogicIssue, ...]`; хотя бы одна issue. Независимые дефекты агрегируются; недоступная зависимая проверка пропускается, но не остальные группы. Infra exceptions не превращаются в MISSING_BODY; hold errors не клонируются из Artifacts.

Эти proof-specific ошибки не разрешают второй совпадающий SourceFieldIssue из §4: до реализации сверить общий Source diagnostics roster и выбрать одну декларацию каждого semantic кода. Exact schema error translation/typed field selectors ещё требует реализации на existing validation infrastructure; список кодов не считается завершённой приёмкой ошибок.

| Класс / модуль в application/worldData/sourceVersioning | Ответственность, зависимости, эффекты | Отказ |
|---|---|---|
| SourceProofPipelineOpenPipeline / sourceProofPipelineOpenPipeline.py | Один ADMIT либо READ; зависимости — internal validator/normalizer/read binding/closure collector; read-only | Публичный nested call, retry workflow, Source write или запуск producer |
| SourceProofValidator / proof/validator.py | Проверяет формы и соответствие decoded capture/dependencies; только готовые POJO | IO, latest-read либо утверждение producer completeness |
| SourceProofNormalizer / proof/normalizer.py | Pure grouping exact captures, set dedup и canonical ordering | Слияние разных revisions из разных captures по object_id, изменение read proof |
| SourceProofClosureCollector / proof/closure.py | Traversal owning decoded dependencies через internal exact reader, полный refs tuple | Partial success, синтез ref по fingerprint или интерпретация чужого произвольного JSON |
| SourceProofReadBinding / proof/readBinding.py | Exact immutable body/capture read+decode в принятой read boundary | Новый blob store, public foreign pipeline, fallback на latest |

Все POJO из A/E только представляют и структурно валидируют свои данные, не проверяют holds. Existing ArtifactRef — content identity, SourceVersionRef — semantic version, PlanDependency — Planning dependency; ни один из них не заменяет другой. Concrete storage adapter, schema registration и полный error roster должны быть предъявлены до code acceptance; именование ролей не заменяет их проверку.

#### F. Поставка и повторная приёмка

Дополнение к A–E: **контракт групп usage, корреляции и выборок определён в §6.0.G ниже**. Его API дополняет admit/read; прежние отдельные предложения Pack о SourceDependencyAdmission/SourceDependencySelection не являются уже существующими Source типами.

1. Принять identity/descriptor roster §3 и точные existing field selectors SourceObjectContract, не расширяя автоматически список всех writers. Проверить запрет import cycles из основного плана: декларативный SourceObjectContract не должен тянуть доменные POJO, holder/usage или Pack.
2. Принять capture record/codec/finalization witness и revision→body mapping. Это определит полноту closure C и допустимые durable refs. Порядок mutation/capture-finalize/prune основного плана сохраняется; max-three capture attempts не превращаются в скрытый retry proof pipeline.
3. Проверить A–E по всем обязательным критериям; после принятия конкретного среза реализовать его через implement-plan. Нет placeholder SourceCapture, зеркала Pack и новых DAG-нод.
4. Предъявить actual result поля `proof` и `durable_refs` потребителю: proof → PackStoredProvenance.source_proof; refs → согласованный transient/scoped admission binding. Точное поле Pack входа принимает Pack-владелец; этот Source документ не меняет Pack POJO. Planning остаётся отдельным tuple.
5. Подключить accepted retention/adoption и проверить restart, latest change, concurrent release/GC, inherited A + new B, разные revisions одной identity в разных captures, противоречие внутри одного capture, missing collection/body и несколько независимых errors. Source read result не заменяет atomic удержание.

**Результат уточнения:** устранены single-capture ограничение и дублирование CREATE/VERIFY в предложении ядра; заданы смысл мульти-capture, граница closure и две операции. Это не закрывает identity roster, capture codec/finalization, error carrier/schema, concrete storage/retention bindings и producer mapping. До их приёмки код proof не пишется. Принятие полного Source домена или Pack интеграции этим разделом не объявляется.

#### G. Ответ Source на требования потребителя: группы, соответствие и выборки

Статус: PROPOSED, для согласования с владельцем потребителя. Source знает только ordered groups заявленного usage, exact captures и dependencies. Group может соответствовать полю, нескольким полям или иному результату; имён полей, PackMetadataSubject, DTO metadata и алгоритма Pack в Source нет. Выбор модели «один proof строки + selections» остаётся решением потребителя. Для неё Source предоставляет следующие универсальные операции.

**Уточнение SourceDurableProof:** добавить обязательное `world_uid: EntityUid` перед `uses`. Оно необходимо для world identity пустого proof; мир всех непустых captures обязан совпадать. World ожидание входа сравнивается с proof.world_uid даже при пустом uses. Это не новое snapshot/publication поле и не копия всего capture. A описывает первоначальную форму; действующая кандидатная форма после этого уточнения — `SourceDurableProof(world_uid, uses)`.

| Модуль под app.dataModel.sourceVersioning | Тип и полный состав | Смысл |
|---|---|---|
| sourceProofGroups.py | SourceProofGroupsInput(`groups: tuple[SourceProofInput, ...]`) | Непустой упорядоченный набор заявок одного мира; исходная позиция — transient correlation |
| sourceProofSelection.py | SourceProofSelection(`proof_fingerprint: RevisionHex`, `dependency_indices: tuple[StrictInt, ...]`) | Выборка exact dependency atoms **конкретного общего proof**, не capture/body indices |
| sourceProofGroups.py | SourceProofGroupsResult(`admission: SourceProofResult`, `selections: tuple[SourceProofSelection, ...]`) | Один общий proof/closure и ровно одна selection на каждую входную группу в исходном порядке |
| sourceProofGroups.py | SourceProofGroupsVerifyInput(`expected: SourceProofGroupsInput`, `result: SourceProofGroupsResult`) | Проверка предъявленного результата относительно точного исходного usage всех групп |
| sourceProofSelection.py | SourceProofSelectInput(`world_uid: EntityUid`, `proof: SourceDurableProof`, `selection: SourceProofSelection`) | Чтение subset общего proof; без знания поля потребителя |

Настройки immutable/strict и обязательность полей — как в A. Selections могут повторяться для разных групп с одинаковыми dependencies: это не duplicate group. Порядок groups/selections не сортировать. Empty groups tuple запрещён, но каждая SourceProofInput может явно содержать пустой usage; тогда corresponding indices пусты. Наличие хотя бы одной группы задаёт world. Смешанные worlds отклоняются до dependent IO.

**Адресация внутри proof.** Сначала canonical ordered uses по full capture identity. В каждом use — canonical objects, затем canonical collections. Каждый элемент порождает один atom `(capture, category, exact SourceVersionRef)`; глобальный zero-based ordinal этого потока — dependency index. Одинаковый SourceVersionRef в разных captures остаётся разными atoms; object/collection categories не сливаются. Indices strict int, ge=0, уникальны и возрастают; bounds проверяются относительно конкретного proof. Это selection над уже предъявленным proof; снятое предложение BLOB-body indices внутри capture не возвращается.

Fingerprint selection — existing canonical content digest **полного SourceDurableProof**, включая world и все capture/dependency identities, по зарегистрированной Source schema. Не hash output metadata, не hash тела объекта и не новый hash algorithm. Canonical IDs/version binding должны быть приняты до реализации. Fingerprint отсутствует как второе поле самого proof: он вычисляется owning codec. Перестановка исходных групп не меняет общий canonical proof, но меняет порядок selections. Любое изменение semantic состава общего proof инвалидирует прежние selections, даже если некоторые indices остались в пределах bounds; перенос выполняется через Source операцию, не поправкой indices в DAG.

**Новые методы того же SourceProofPipelineOpenPipeline / ISourceProofPipelineOpenPipeline:**

```python
async def admit_groups(self, request: SourceProofGroupsInput) -> SourceProofGroupsResult | SourceProofFailure: ...
async def verify_groups(self, request: SourceProofGroupsVerifyInput) -> SourceProofGroupsResult | SourceProofFailure: ...
async def select(self, request: SourceProofSelectInput) -> SourceProofResult | SourceProofFailure: ...
```

ADMIT_GROUPS — одна операция read admission: проверить каждую заявленную группу, собрать canonical union exact atoms без потери capture provenance, построить общий SourceDurableProof, получить полный closure общего proof, выдать selections в исходном порядке. Source не вызывает публичный admit в цикле: shared validator/normalizer/reader выполняют внутренний алгоритм этой операции. Успех всего запроса атомарен как результат: при одной ошибке частичный result не возвращается. Это не storage transaction и не приобретение holds.

VERIFY_GROUPS заново проверяет owning данные и canonical expected usage, затем требует одновременно:

1. World результата совпадает с world всех expected groups.
2. Общий proof равен exact canonical union ожидаемых groups: запрещены missing и extra dependencies, capture/revision подмена.
3. Число selections равно числу groups. Selection i разрешается **ровно** в normalized expected.groups[i], не в superset. Совпадение общего union не заменяет эту проверку: обмен selectors двух разных групп отклоняется.
4. Fingerprint и bounds каждой selection корректны, every atom общего proof покрыт хотя бы одной selection. Явно пустая группа соответствует только empty indices.
5. durable_refs предъявленного admission равны заново вычисленному полному canonical closure. Missing/extra refs и несовпадающая полная ArtifactRef identity отклоняются; refs нельзя считать истинными потому, что result POJO валиден.

Success возвращает проверенный результат с тем же semantic proof/selections; не исправляет неверный result молча. Эта операция отличается от ADMIT_GROUPS: она проверяет чужой предъявленный result, а не создаёт его из request. READ без expected usage подтверждает только внутреннюю Source корректность proof, не соответствие конкретному заявленному набору.

SELECT проверяет world, fingerprint/bounds/canonical selection и exact dependencies в owning capture. Возвращает самостоятельный canonical SourceDurableProof выбранного subset и его полный **собственный** closure. Общий proof не мутируется. Для extract не требуется читать body невыбранных dependencies только ради subset, если они не входят в owning capture/format closure; обязательные witness dependencies сохраняются по C. Empty selection возвращает proof данного мира с uses=() и пустой Source closure. Это не доказывает, что конкретное поле действительно source-independent. Source не генерирует новую selection относительно subset автоматически: прежняя selection привязана к исходному proof.

**Граница проверки:** ни VERIFY_GROUPS, ни SELECT не доказывают, что producer честно сообщил все чтения или правильно вычислил metadata. Expected usage берётся из owning producer output; DAG не собирает его из value hash. Результат проверки не является подписанным token: на недоверенной границе он проверяется по описанному owning API/binding. Совпадение usage и proof не заменяет действующее удержание перед publication.

**Дополнение diagnostics.** SourceProofOperation получает ADMIT_GROUPS, VERIFY_GROUPS, SELECT. SourceProofLogicCode получает USAGE_MISMATCH, PROOF_MISMATCH, SELECTION_PROOF_MISMATCH, SELECTION_OUT_OF_RANGE, SELECTION_USAGE_MISMATCH, CLOSURE_MISMATCH. SourceProofFieldCode получает INVALID_SELECTION и GROUP_COUNT_MISMATCH. Существующий SourceProofLogicIssue уточняется: `group_index: StrictInt | None`, `use_index: StrictInt | None`, `source: SourceVersionRef | None`, `artifact: ArtifactRef | None`, `code`; все поля обязательны, индексы при наличии ge=0. None допускается для ошибки всего result/proof, а не подставляется fictitious use_index=0. Обе позиции ссылаются на исходный request. FieldPathError использует полный typed путь: например result.selections[i].dependency_indices[j]; descriptors следует зарегистрировать при реализации. Exact error-code roster остаётся единым с E; новые exception mirrors не вводятся.

**Ответственность дополнительного internal класса:** `SourceProofSelector`, модуль `application/worldData/sourceVersioning/proof/selector.py`, pure алгоритм canonical atom enumeration, построения selections и exact subset comparison по Source POJO/CanonicalCodec. Не читает storage, не знает Pack fields, не делает normalize captured body и не принимает retention решения. Он не вызывает публичные методы; pipeline передаёт готовые проверенные данные. Признаки отказа в приёмке: зависимости от Pack DTO, body IO, создание другого hash engine или изменение requested groups ради совпадения результата.

**Публичные импорты для потребителя:** SourceProofInput из `sourceProofInput`; SourceProofGroupsInput/SourceProofGroupsResult/SourceProofGroupsVerifyInput из `sourceProofGroups`; SourceProofSelection/SourceProofSelectInput из `sourceProofSelection`; SourceDurableProof из `sourceDurableProof`; SourceProofResult из `sourceProofResult`. Все префиксы — `app.dataModel.sourceVersioning`. Пока это объявленные проектные пути, не runtime импорты. Не создавать aliases SourceDependencyAdmission/SourceDependencySelection по именам чужого черновика.

**Mapping через DAG:** owning ordered groups → SourceProofGroupsInput.groups → ADMIT_GROUPS → result.admission.proof сохраняется потребителем один раз; result.selections[i] соответствует ровно исходной группе i. DAG переносит элементы по позиции, не вычисляет union/indices/fingerprint. Групповые ключи потребителя остаются у него и не передаются Source. Для исторического поля pure extraction usage из материализованного proof задаётся §H; SELECT нужен, когда требуется owning IO-проверка и closure subset. Он не вставляется между каждым Pack write. Full durable closure строки/артефакта получают через READ общего proof; набор selections не разрешает исключить необходимые refs общего proof.

**Приёмочные сценарии:** historical capture A + current B; одна identity с разными revisions в A/B; одинаковый union при переставленных различных selections; две разные группы с одинаковыми subsets; empty declared usage; extra atom без группы; foreign world пустого proof; selection с чужим fingerprint при валидных bounds; invalid bool/negative/out-of-range index; subset с обязательным collection witness; missing/extra closure ref; restart и released source hold между verification и publication. Минимум два независимых дефекта разных groups должны вернуться вместе с исходными индексами, без частичного результата.

**Состояние передачи:** требования потребителя сопоставлены с concrete кандидатными POJO/API, включая optional модель общего proof с выборками. Они готовы к design review владельцами Source и потребителя, но ещё не к runtime freeze: SourceVersionRef identity roster, capture codec/finalization witness, canonical schema IDs, exact read/retention ports и единый error roster остаются обязательными dependencies F. Это работа Source, а не повод расширять Pack; Pack файлы данным уточнением не меняются.

#### H. Pure binding над материализованными Source значениями

Основание: ответ потребителя Pack на §G. Статус: PROPOSED, не runtime и не принятое исключение из архитектурных правил. Устраняет потребность вызывать async SELECT при каждом сохранении поля и async VERIFY_GROUPS внутри pure bind. Сам pipeline G остаётся отдельной операцией DAG.

**Concrete библиотечный класс:** `SourceProofValues`, публичный импорт `app.application.worldData.sourceVersioning.contracts.sourceProofValues.SourceProofValues`. Методы синхронные, stateless, без storage/DI ports, callback, resolver, lease, cache и глобального mutable registry. CanonicalCodec/schema binding фиксируется Source composition; consumer не передаёт собственный codec или type IDs. Класс не OpenPipeline и не фасад над IO-операциями.

```python
def extract_usage(self, request: SourceProofSelectInput) -> SourceProofInput | SourceProofFailure: ...
def match_groups(self, request: SourceProofGroupsMatchInput) -> SourceProofGroupsInput | SourceProofFailure: ...
```

**Один новый входной POJO:** `SourceProofGroupsMatchInput` в `app.dataModel.sourceVersioning.sourceProofGroups`, поля `expected: SourceProofGroupsInput`, `proof: SourceDurableProof`, `selections: tuple[SourceProofSelection, ...]`. Frozen/strict/extra-forbid/revalidate-always, все поля обязательны. В отличие от SourceProofGroupsVerifyInput он намеренно не принимает admission/durable_refs: чистая операция не способна проверить storage closure. Это не зеркальный proof/result, а request другой проверки с меньшим составом проверяемых данных. Остальные Input/Output/Error переиспользуются из A/G; новый ExtractedUsage/MatchReceipt/VerifiedProof DTO не создаётся.

**EXTRACT_USAGE:** повторно валидировать фактические вложенные POJO → проверить expected world, canonical proof и selection → вычислить fingerprint существующим Source canonical binding → проверить fingerprint и indices → материализовать выбранные atoms как canonical SourceProofInput(world_uid, uses). Сохранить exact captures/categories/revisions, не объединять разные исторические revisions. Не читать capture artifact или bodies, не нормализовать повреждённый persisted proof. Empty selection даёт явный пустой usage правильного мира. Возвращённое значение — структурно извлечённая заявка, а не доказательство финализации capture или availability его зависимостей.

**MATCH_GROUPS:** повторно валидировать input; нормализовать только expected declared groups по B; проверить один world и canonical предъявленный proof; проверить exact union proof и expected; проверить count/order и fingerprint/bounds всех selections; проверить, что selection i выбирает ровно canonical expected.groups[i]. Superset/subset/перестановка различных групп и непокрытые atoms отвергаются. Успех возвращает SourceProofGroupsInput с canonical groups в исходном порядке, без изменения proof или selectors. Это полезный typed output для дальнейшей обработки usage, не token и не новое persisted состояние. Одинаковые groups и одинаковые selections разрешены. Expected пустой usage не заменяет неизвестное происхождение.

**Предел гарантии:** pure методы подтверждают только логическую согласованность предъявленных значений. Поддельный, но внутренне согласованный proof может пройти pure matching. Не подтверждаются capture-finalize, подлинность revisions/body, producer read-set, вычисление metadata, closure полнота/доступность, действующие holds или факт предшествующего Source IO admission. Поля с такими гарантиями не добавляются в выход. READ/VERIFY_GROUPS/SELECT выполняют owning IO-проверки через DAG; проверка и приобретение удержаний перед READY остаются отдельным согласованным scoped binding. Доверие к producer/Pack basis не выводится из совпадения expected и result.

**Недиублирование алгоритмов и ответственность:** SourceProofValues использует existing proposed SourceProofValidator/SourceProofNormalizer/SourceProofSelector, но только их pure части. Эти internals не экспортируются потребителю. IO pipeline использует те же internal algorithms; он не вызывает публичный метод SourceProofValues как следующую операцию. Selector не знает Pack subjects/field enums. Ни Pack, ни DAG не реализуют собственный enumeration/union/hash/subset алгоритм. Отказ в приёмке: hidden IO, вызов публичного Source pipeline, mutable cache, передача callback/codec от consumer или утверждение полноты closure результатом pure проверки.

**Ошибки:** SourceProofOperation дополняется EXTRACT_USAGE и MATCH_GROUPS. SourceProofFailure/SourceProofFieldIssue/SourceProofLogicIssue и коды G переиспользуются, отдельный домен ошибок pure методов не вводится. Pure методы могут выдавать INVALID_SHAPE/INVALID_IDENTITY/NON_CANONICAL_PROOF/INVALID_SELECTION/GROUP_COUNT_MISMATCH, WRONG_WORLD/REVISION_CONFLICT/PROOF_MISMATCH/SELECTION_PROOF_MISMATCH/SELECTION_OUT_OF_RANGE/SELECTION_USAGE_MISMATCH. Они не выдают BODY_MISSING/CORRUPT_BODY/UNSEALED_BODY/CAPTURE_NOT_FINALIZED/INCOMPLETE_CLOSURE/CLOSURE_MISMATCH как будто проверили storage. Несколько независимых field/group ошибок агрегируются в исходном порядке; fingerprint/bounds/subset проверки пропускаются только для зависимых повреждённых ветвей.

**Вход потребителя:** materialized proof+selection → extract_usage → existing SourceProofInput, пригодный для следующего grouped admission через DAG. При pure bind consumer передаёт expected usage, предъявленные общий proof/selections в match_groups; durable_refs сюда не передаются. В consumer остаются проверки subject, собственной базы и computation basis. Source группы сопоставляются по заранее определённому порядку, consumer keys не становятся Source полями. Это карта предложенного library binding, а не изменение Pack DTO или его порядка операций.

**Архитектурная приёмка:** требуется явно подтвердить классификацию SourceProofValues как общей pure библиотеки value-контракта, а не самостоятельной междоменной публичной операции. Один суффикс/название helper не даёт исключения из запрета прямых междоменных вызовов `.cursor/rules/dag-generator-interface.mdc`. До принятия этой границы direct consumer use остаётся OPEN. У библиотеки отсутствуют lifecycle, IO и выбор стадий; Source pipeline по-прежнему вызывается прямо из DAG. Порядок write/describe/bind не меняется; новые ноды/receipts/signatures хранения не вводятся. Класс, зависимости, effects, конкретные POJO и предел ошибки описаны выше для совместной проверки; код до принятия не писать.

**DoD pure среза:** match exact groups и extract совпадают с canonical atom model; разные captures не схлопываются; forged instances и лишние поля revalidate; mismatch world пустого proof отвергается; несколько независимых errors сохраняют group/field paths; round-trip selectors не меняет subset; повтор/перестановка различных groups не теряет корреляцию; storage port может быть вообще отсутствующим, вызовов IO нет. Отдельный негативный тест показывает, что structurally coherent invented capture не отвергается за отсутствие storage в pure методе, но отвергается owning IO admission: это проверка честного предела гарантии, не разрешение фиктивного proof в production.

**Оставшийся gate:** identity roster, Source canonical codec/schema и diagnostics infrastructure из F нужны даже pure implementation. Capture/body storage adapter не нужен для самой pure библиотеки, но обязателен для IO admission и полного integrated маршрута. Поэтому этот срез можно принимать отдельно после подтверждения library boundary; не требовать готовности всей миграции Source и не выдавать локальный результат за READY.

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
