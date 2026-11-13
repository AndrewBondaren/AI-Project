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
| SourceObjectId, sourceObjectId.py | Точные discriminated variants и SourceCollectionId определены в §10.2; registered descriptor + owning key adapter — §10.1 | Неизвестный descriptor, чужой world, нормализация historical key либо object/collection подмена |
| SourceVersionRef, sourceVersionRef.py | `object_id: SourceObjectId`, `revision: SourceRevision` | Ref не содержит mutable body, storage backend или latest-resolver |
| SourceBodyVersion, sourceBodyVersion.py | `source: SourceVersionRef`, `body: ArtifactRef` | Artifact format должен соответствовать owning source contract; hash semantic projection не приравнивается автоматически hash полных body bytes |
| SourceTombstoneVersion, sourceBodyVersion.py | `source: SourceVersionRef`; отдельный discriminator tombstone | Отсутствие body не трактуется как storage miss живой записи; старые версии не перезаписываются |
| SourceCollectionBody, sourceCollection.py | `collection: SourceCollectionId`, `members: tuple[SourceObjectId, ...]`; правила §10.2 | Duplicate members, foreign world/descriptor, сортировка SEQUENCE как SET |
| SourceCapture, sourceCapture.py | `world_uid: EntityUid`, `objects: tuple[SourceBodyVersion, ...]`, `collections: tuple[SourceCollectionVersion, ...]`; отдельный SourceCaptureWitness §10.3 | Смешанные worlds, conflicting revisions, incomplete membership; body сам не доказывает finalize |
| SourceDependencySet, sourceDependencies.py | `objects: tuple[SourceVersionRef, ...]`, `collections: tuple[SourceCollectionVersionRef, ...]` (§10.2) | Пропущенные collection dependencies либо ref другой категории |

**Конкретизация identity:** §10.1–2 определяет Source-owned descriptor/key carrier и отдельные object/collection refs. Owning typed key проверяется application adapter с exact round-trip; compile-time generic owning RegistryKey[R] не переносится в Source ID. Полная регистрация поддерживаемых descriptors/projectors/codecs и её приёмка ещё требуются; WorldSlice Python class в публичный ID не входит.

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

### 3.2. Consumer trace terrain и граница identity — 2026-11-13

Продолжение inventory шага 1; не разрешение реализации шага 2. Проверены следующие реальные пути:

| Источник evidence | Наблюдение | Следствие для Source |
|---|---|---|
| `backend/app/application/worldData/planning/composition/support/surfaceSupportCapture.py::SurfaceSupportCapture.capture` | Передаёт весь terrain registry, сортируя по system_terrain; читает category, default_material, merge_rank, eligibility, hills и has_authored_hills | Эти поля входят в зависимости данного потребителя. Нельзя объявить остальные поля globally excluded по одной проекции. Authored presence уже имеет явный носитель hills_authored в Planning, повторный POJO этой проекции не нужен |
| `backend/app/application/worldData/regions/coverageBackground.py::coverage_registry`, `coverageResolver.py::resolve` | Фильтрация по policy и eligibility, оценка всех кандидатов, tie-break по ключу | Proof победителя недостаточен: нужны membership и revisions просмотренных entries, включая отклонённых при оценке. Изменение eligibility проигравшего способно изменить результат. Порядок реестра не влияет на tie-break этого scorer; это не доказательство unordered semantics всех потребителей |
| `backend/app/dataModel/terrain/worldTerrainRegistry.py::column_terrain_key` | Отбор по fill_roles и available, выбор по fill_priority и ключу | fill_roles/fill_priority нельзя исключать из общего semantic body только потому, что SurfaceSupportCapture их не копирует |
| `backend/app/application/templateLibrary/reliefTerrainSync.py::missing_terrain_entries` | Сравнивает сохранённые строки; комментарий и реализация различают их от resolved registry, дополненного canonical entries | Stored membership и effective membership различаются. Capture только persisted rows не доказывает полный effective input |

**Обязательная зависимость capture:** прежде чем назначать revisions эффективным входам, определить носитель canonical defaults и overlay policy. Нельзя скрыто читать актуальные встроенные значения при historical restore. Допустимая реализация должна либо удерживать точное effective body вместе с проверяемой версией его source/projection inputs, либо включать immutable versioned canonical inputs и policy в closure. Выбор и формат ещё OPEN; нельзя объявлять default entry persisted mutation на каждом capture. Это уточнение текущего шага inventory, а не добавление стадии в утверждённый порядок.

**Уточнение риска ключей:** `RegistryKey[R]` в `backend/app/dataModel/registryKey.py` различается по R для статической типизации, но runtime schema использует общий origin RegistryKey и принимает строку. Проверку пары descriptor/key и membership он сам не выполняет. `TYPE_CHECKING` импорт в TerrainRegistryEntry позволяет текущую forward annotation; это не доказывает безопасное публичное восстановление heterogeneous SourceObjectId без owning registration. Поэтому предыдущий import-cycle finding — ограничение предлагаемой новой зависимости Source→domain, а не утверждение о существующем сломанном импорте.

**Конкретный выбор для приёмки identity, ещё не принятый:**

1. Сохранить запрещённое основным планом направление Source→domain неизменным. В Source ввести закрытые варианты identity по категориям и Source-owned descriptor identity; ключ registry member — отдельный nominal immutable carrier с обязательным descriptor binding. Application composition проверяет его owning key adapter, category и canonical round-trip. Такой carrier не является owning RegistryKey[R]; потребуется явно принять, что типизация пары descriptor/key обеспечивается регистрацией и проверкой, а не generic R публичного поля. Нельзя выдать wrapper над str за выполнение прежнего требования owning typed key.
2. Сохранить owning RegistryKey[R] непосредственно в публичной identity. Тогда до Source POJO нужен согласованный способ независимого размещения registry brands/descriptor types с owning domains; прямой импорт их registry POJO в Source нарушает основной план. Перенос типов — отдельная зависимость и отдельный scope, автоматически не выполняется.

Рекомендуется вариант 1 для небольшого модуля Source, но он требует явного согласования границы публичной типизации. До выбора точный carrier/descriptor roster не считается принятым. Общий str/Any, Python type в wire, копия SQL-column enum и фиктивные DTO не являются третьим вариантом.

**Приёмка этого этапа:** evidence для terrain зафиксирован; SourceObjectId и реализация не приняты. Не закрыты точный carrier, descriptor registration diagnostics, canonical-default witness и trace остальных источников. Публичные CRUD, proof pipeline, pure value API и DAG bindings этим inventory не принимаются. Порядок остаётся inventory → contracts/projector → revisions/history → capture; Pack не получает нового runtime контракта до приёмки соответствующего среза.

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
| sourceDurableProof.py | SourceDurableProof(`world_uid: EntityUid`, `uses: tuple[SourceCaptureUsage, ...]`) | Канонический набор исторических source dependencies одного результата; без Pack address, output artifact, Planning dependencies и capabilities |
| sourceProofInput.py | SourceProofInput(`world_uid: EntityUid`, `uses: tuple[SourceCaptureUsage, ...]`) | Заявка admission/нормализации: world ожидание и реально сообщённые producer зависимости; не готовое удостоверение |
| sourceProofInput.py | SourceProofReadInput(`world_uid: EntityUid`, `proof: SourceDurableProof`) | Проверка уже сохранённого proof без его переписывания |
| sourceProofResult.py | SourceProofResult(`proof: SourceDurableProof`, `durable_refs: tuple[ArtifactRef, ...]`) | Полностью проверенные source зависимости и вычисленный closure на момент чтения; не retention token |

SourceProofInput и SourceDurableProof имеют разную семантику: input допускает неканонический порядок/повторные usage одного capture для объединения, output — единственное каноническое представление. Отличие должно быть отражено validators, а не только именами. SourceProofReadInput не вызывает нормализацию сохранённого proof: повреждённая persisted canonical форма отклоняется.

SourceDependencySet определён в §10.2: objects содержит SourceVersionRef, collections — SourceCollectionVersionRef. SourceCaptureRef.artifact указывает на finalized SourceCaptureWitness, который ссылается на SourceCapture body (§10.3). Owning codecs и trusted committed reader требуют реализации; произвольный BLOB не считается witness.

#### B. Нормализация и конфликтные revisions

1. Проверить форму всех доступных полей, world ожидание каждого usage и полную identity capture. Bool не принимается за seq; seq положительная; semantic hash не приравнивается hash body bytes.
2. Повтор exact source ref в группе объединяется как set. Повтор одного capture объединяется только по full SourceCaptureRef. Одна identity с двумя revisions внутри **одного capture** — отказ; несовпадающие body mappings одной exact revision — corruption. Source normalizer сортирует по canonical encoded bytes согласно §9.2; existing CanonicalCodec сам не сортирует tuple. Не использовать repr/stringification.
3. **Разные captures могут содержать разные revisions одной identity.** Их нельзя ни глобально склеить по object_id, ни произвольно выбрать latest. Группы сохраняют принадлежность capture. Source доказывает каждую группу отдельно; совместимость комбинации inputs относится к producer/consumer. Это необходимо, например, для metadata, часть полей которой сохранена из базы, а часть получена из новых inputs.
4. Для каждого dependency проверить membership именно в указанном finalized capture, revision equality и live/tombstone смысл owning read. Если потребитель зависел от состава кандидатов, collection dependency обязательна по producer declaration; Source не угадывает отсутствие таких чтений по списку объектов.
5. Source не выбирает допустимые captures за producer и не считает произвольный valid capture достаточным основанием результата. Producer/Pack сообщает и проверяет связь результата с реальными inputs; DAG переносит owning output без вычисления dependencies. Это две разные проверки.
6. Пустой uses допустим только как явное заявление об отсутствии source dependencies. Source возвращает пустой source closure, не утверждая полноту producer read-set; consumer обязан иметь основание для source-independent результата. Пустая группа без dependencies исключается при admission, но запрещена в persisted canonical proof. Отсутствующий/неизвестный proof никогда не заменяется пустым.
7. Label stamp не участвует в semantic SourceRevision equality; его отдельная audit схема остаётся детализацией основного плана. Повтор label не меняет seq и не создаёт новый semantic dependency. Source proof не вводит новый hash engine.

#### C. Durable refs: что именно удерживать

Для каждого употреблённого capture вернуть witness artifact, capture_body, все body artifacts mappings полного capture v1 и их обязательные owning format dependencies (§10.3–4). Полный storage closure включает невыбранные тела этого capture; они не становятся logical usage результата. Source не добавляет произвольные refs вне owning format graph.

**Выбранный проект формата v1 (§10.3–4):** witness → полный capture → все body mappings и обязательные format dependencies. SELECT не уменьшает storage closure внутри одного capture; уменьшается только logical usage. Минимальный storage subset возможен лишь в отдельном будущем формате с самостоятельным membership witness, не обещается текущим контрактом.

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

- SourceProofOperation: ADMIT, READ, ADMIT_GROUPS, VERIFY_GROUPS, SELECT. Внутренние стадии не добавляют публичные операции.
- SourceProofFieldCode: INVALID_SHAPE, INVALID_IDENTITY, NON_CANONICAL_PROOF, INVALID_SELECTION, GROUP_COUNT_MISMATCH. SourceProofFieldIssue — concrete FieldPathError[SourceProofFieldCode] с inherited code/path/message; общий carrier не клонируется.
- SourceProofLogicCode: WRONG_WORLD, CAPTURE_NOT_FINALIZED, DEPENDENCY_NOT_CAPTURED, REVISION_CONFLICT, BODY_MAPPING_CONFLICT, UNSUPPORTED_FORMAT, MISSING_BODY, CORRUPT_BODY, UNSEALED_BODY, INCOMPLETE_CLOSURE, PROOF_MISMATCH, SELECTION_PROOF_MISMATCH, SELECTION_OUT_OF_RANGE, SELECTION_USAGE_MISMATCH, CLOSURE_MISMATCH. Общий USAGE_MISMATCH не вводится: нарушение exact union — PROOF_MISMATCH, отдельной selection — SELECTION_USAGE_MISMATCH.
- SourceProofLogicIssue: `code: SourceProofLogicCode`, `group_index: StrictInt | None`, `use_index: StrictInt | None`, `source: SourceVersionRef | SourceCollectionVersionRef | None`, `artifact: ArtifactRef | None`; все поля обязательны. Индексы при наличии ge=0, относятся к исходному request. Для ошибки proof/result целиком оба индекса None; для одиночной операции group_index=None. Fictitious use_index=0 запрещён. Вложенные refs имеют разные обязательные поля object_id/collection_id и extra-forbid, поэтому union не допускает смешанную запись.
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

**SourceDurableProof:** единая кандидатная форма A/G/§9 — `SourceDurableProof(world_uid: EntityUid, uses: tuple[SourceCaptureUsage, ...])`. World обязателен даже при пустом uses, сравнивается с request world и мирами всех captures. Отсутствующий proof не заменяется пустым.

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

**Diagnostics групповых операций:** единый roster §E. Для ошибки selection group_index — её исходная позиция, use_index=None; для expected.groups[i].uses[j] задаются оба индекса. FieldPathError содержит полный typed путь от корня request, например result.selections[i].dependency_indices[j]. Независимые diagnostics исходных groups не теряются после union. Exact typed field descriptors обязательны до реализации.

**Ответственность дополнительного internal класса:** `SourceProofSelector`, модуль `application/worldData/sourceVersioning/proof/selector.py`, pure алгоритм canonical atom enumeration, построения selections и exact subset comparison по Source POJO/CanonicalCodec. Не читает storage, не знает Pack fields, не делает normalize captured body и не принимает retention решения. Он не вызывает публичные методы; pipeline передаёт готовые проверенные данные. Признаки отказа в приёмке: зависимости от Pack DTO, body IO, создание другого hash engine или изменение requested groups ради совпадения результата.

**Публичные импорты для потребителя:** SourceProofInput из `sourceProofInput`; SourceProofGroupsInput/SourceProofGroupsResult/SourceProofGroupsVerifyInput из `sourceProofGroups`; SourceProofSelection/SourceProofSelectInput из `sourceProofSelection`; SourceDurableProof из `sourceDurableProof`; SourceProofResult из `sourceProofResult`. Все префиксы — `app.dataModel.sourceVersioning`. Пока это объявленные проектные пути, не runtime импорты. Не создавать aliases SourceDependencyAdmission/SourceDependencySelection по именам чужого черновика.

**Mapping через DAG:** ordered usages → SourceProofGroupsInput.groups → ADMIT_GROUPS → result.admission.proof и result.selections. Selection i соответствует исходной группе i; consumer group keys остаются у потребителя. DAG переносит данные, не вычисляет union/indices/fingerprint. Historical subset проверяет SELECT через DAG; точное место в Pack-порядке остаётся OPEN (§9.5). READ общего proof возвращает полный closure; selections не разрешают исключить обязательные refs.

**Приёмочные сценарии:** historical capture A + current B; одна identity с разными revisions в A/B; одинаковый union при переставленных различных selections; две разные группы с одинаковыми subsets; empty declared usage; extra atom без группы; foreign world пустого proof; selection с чужим fingerprint при валидных bounds; invalid bool/negative/out-of-range index; subset с обязательным collection witness; missing/extra closure ref; restart и released source hold между verification и publication. Минимум два независимых дефекта разных groups должны вернуться вместе с исходными индексами, без частичного результата.

**Состояние передачи:** требования потребителя сопоставлены с concrete кандидатными POJO/API, включая optional модель общего proof с выборками. Они готовы к design review владельцами Source и потребителя, но ещё не к runtime freeze: SourceVersionRef identity roster, capture codec/finalization witness, canonical schema IDs, exact read/retention ports и единый error roster остаются обязательными dependencies F. Это работа Source, а не повод расширять Pack; Pack файлы данным уточнением не меняются.

#### H. Внутренние pure алгоритмы Source

Прямой Pack→SourceProofValues/extract_usage/match_groups исключён решением пользователя из `gen-dag-cache-pack-source-families.md` §6.7. Предложение публичной библиотеки `contracts.sourceProofValues.SourceProofValues` отозвано. Не создавать этот класс, его публичный импорт или отдельный pure delivery slice.

SourceProofValidator, SourceProofNormalizer и SourceProofSelector из E/G — внутренние pure компоненты: revalidation, canonical atom enumeration, нормализация declared usage, exact union и matching selections. Они не читают storage, не запускают публичные операции и не принимают callback/codec от потребителя. Pack и DAG не воспроизводят эти алгоритмы.

SourceProofGroupsMatchInput не вводится: pure matching является внутренней стадией VERIFY_GROUPS над его входом. Публичные EXTRACT_USAGE/MATCH_GROUPS и соответствующие значения SourceProofOperation также не вводятся. Исторический subset проверяет SELECT, возвращающий SourceProofResult. Сопоставление proof.world_uid/proof.uses с конкретным Pack usage input предъявляет owning binding; второй usage record в result не добавляется.

Pure стадия подтверждает лишь структурную согласованность значений. Finalized capture, exact mappings и полный closure проверяются IO стадиями одной owning операции. Поддельный внутренне согласованный proof может пройти pure проверку, но не должен получить успешный IO result. Живые holds проверяет Artifacts/publication scoped owner.

Приёмка internals входит в приёмку публичной операции: canonical round-trip, разные revisions в разных captures, forged nested instances, world пустого proof, переставленные selections и независимые diagnostics. В pure стадиях IO запрещён. Этот раздел не назначает DAG-ноды и порядок Pack write/describe/bind; открытые точки — §9.5.

Конкретная граница Pack вынесена в [pack-v2-domain-contract-spec.md](pack-v2-domain-contract-spec.md). Ниже — предложение структуры evidence, не изменение утверждённого Pack ТЗ и не назначение Source CRUD домену Pack. В частности, public activate остаётся у Pack, внутренний transaction mechanism — у publication.

Producer сообщает реальные зависимости. Source проверяет exact captured revisions, тела и closure; живые holds подтверждает Artifacts/publication scoped owner. Pack проверяет адрес, payload и computation basis. Междоменные результаты передаются через DAG.

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

**Уточнение границы текущего среза:** для приёмки схемы proof не требуется завершить миграцию всех writers. Но все identity категории, разрешённые этой схемой, должны иметь точные типы и правила; ограничение поддерживаемого roster задаётся явно, не permissive fallback. Для работающего durable API обязательны retained mappings и finalized captures именно поддерживаемых источников. Это не разрешение перескочить шаги основного плана.

## 9. Сводный кандидат контракта для приёмки — 2026-11-13

Этот раздел сводит публичную поверхность A–H и уточняет canonical ordering. Статус **PROJECT / NOT ACCEPTED**: описание точных верхнеуровневых records не закрывает зависимости §9.4. Нельзя объявить runtime import готовым. §3 и §6 сохраняют обоснование и детали; при расхождении будущая приёмка должна исправить обе записи, не выбирать версию по усмотрению implementer.

### 9.1. Публичные значения и операции

Все новые модели принадлежат Source: frozen, strict, extra-forbid, revalidate_instances=always; все поля обязательны, коллекции tuple. Для индексов StrictInt с ge=0; bool запрещён. Вложенные Source типы должны иметь те же гарантии. Existing ArtifactRef, EntityUid, RevisionHex и PlanDependency не переобъявляются.

Префикс модулей таблицы — `app.dataModel.sourceVersioning`.

| Модуль | Record: полный состав полей |
|---|---|
| sourceCaptureRef | SourceCaptureRef(world_uid: EntityUid, artifact: ArtifactRef) |
| sourceCaptureUsage | SourceCaptureUsage(capture: SourceCaptureRef, dependencies: SourceDependencySet) |
| sourceDurableProof | SourceDurableProof(world_uid: EntityUid, uses: tuple[SourceCaptureUsage, ...]) |
| sourceProofInput | SourceProofInput(world_uid: EntityUid, uses: tuple[SourceCaptureUsage, ...]); SourceProofReadInput(world_uid: EntityUid, proof: SourceDurableProof) |
| sourceProofResult | SourceProofResult(proof: SourceDurableProof, durable_refs: tuple[ArtifactRef, ...]) |
| sourceProofGroups | SourceProofGroupsInput(groups: tuple[SourceProofInput, ...]); SourceProofGroupsResult(admission: SourceProofResult, selections: tuple[SourceProofSelection, ...]) |
| sourceProofGroups | SourceProofGroupsVerifyInput(expected: SourceProofGroupsInput, result: SourceProofGroupsResult) |
| sourceProofSelection | SourceProofSelection(proof_fingerprint: RevisionHex, dependency_indices: tuple[StrictInt, ...]); SourceProofSelectInput(world_uid: EntityUid, proof: SourceDurableProof, selection: SourceProofSelection) |

Внешний import proof: `app.dataModel.sourceVersioning.sourceDurableProof.SourceDurableProof`.

Concrete публичный IO класс: `app.application.worldData.sourceVersioning.sourceProofPipelineOpenPipeline.SourceProofPipelineOpenPipeline`; интерфейс с префиксом I в `interfaces.sourceProofPipelineOpenPipeline`. Методы async, возвращают указанный result либо единый SourceProofFailure из `sourceProofErrors`:

| Метод | Request | Success | Проверяемая гарантия |
|---|---|---|---|
| admit | SourceProofInput | SourceProofResult | Declared usage нормализован, exact dependencies проверены по finalized captures, полный closure вычислен |
| read | SourceProofReadInput | SourceProofResult | Предъявленный canonical proof проверен без переписывания, полный closure вычислен |
| admit_groups | SourceProofGroupsInput | SourceProofGroupsResult | Exact union groups, selections в исходном порядке, полный closure |
| verify_groups | SourceProofGroupsVerifyInput | SourceProofGroupsResult | Exact union, каждая selection соответствует именно своей группе, предъявленные refs равны вычисленному closure |
| select | SourceProofSelectInput | SourceProofResult | Выбранные exact dependencies проверены, возвращены самостоятельный proof и его полный closure |

Все пять методов read-only. Не создают captures/revisions/holds, не запускают producer и не вызывают друг друга публично. Pure алгоритмы §H — внутренние стадии Source, публичной pure библиотеки для Pack нет. Точные extraction/matching bindings и место SELECT/VERIFY_GROUPS в последовательности Pack остаются OPEN.

### 9.2. Единые правила значения, порядка и сравнения

1. `E(value)` — bytes существующего `CanonicalCodec.encode` при фиксированном Source canonical manifest. Source normalizer сортирует лексикографически по bytes: uses по E(full SourceCaptureRef), objects и collections внутри use отдельно по E(full SourceVersionRef), durable_refs по E(full ArtifactRef). Не сортировать по hash вместо полного значения, по repr, Python module name или порядку обнаружения. Type IDs/версия manifest остаются обязательной dependency до реализации; они фиксируются в Source composition и недоступны для подмены caller.
2. Admission объединяет одинаковые full capture refs, удаляет exact дубликаты dependencies; затем сортирует. Разные revisions одной identity внутри capture отклоняются, а в разных captures сохраняются. Пустые usages удаляются только при admission. READ/SELECT/VERIFY предъявленного persisted proof требуют уже canonical порядка, уникальности и отсутствия пустых usages; не исправляют его.
3. World proof обязателен даже при uses=(). Capture worlds совпадают с ним; request world проверяется отдельно. Проверки мира и применимости каждой identity не заменяются одним сравнением capture.world_uid: world-scoped dependency не может принадлежать чужому миру, global library dependency требует owning membership witness.
4. Groups непусты, одного мира, порядок сохраняется. Каждая группа может явно заявить пустой usage. Неизвестное происхождение не превращается в пустую группу. Atom stream = ordered uses, затем objects, затем collections; atom identity включает capture, category и exact revision. Selection indices строго возрастают, уникальны, в границах этого потока. Одинаковые selections разных groups разрешены.
5. Fingerprint = существующий canonical content digest всего proof по фиксированной схеме; формат digest соответствует RevisionHex. Нужна одна named Source schema binding с закреплёнными IDs и версией, не implicit current global registry. Fingerprint не удостоверяет capture-finalize или producer completeness.
6. VERIFY_GROUPS требует точного равенства normalized expected union предъявленному proof и точного равенства каждого subset соответствующей группе. Проверка union без покомпонентного matching недостаточна. durable_refs обязаны быть canonical tuple exact полного closure; missing, extra, duplicate или неверно упорядоченные refs не исправляются. READ возвращает неизменный proof, не пересобранную semantic approximation.
7. Все независимые доступные ошибки собираются до отказа; dependent IO не выполняется после нарушения предусловия. Никакого partial success. Ошибки инфраструктуры не превращаются в отсутствие body. Привязка typed field paths и единый error roster требуют §9.4; список правил не заменяет error POJO.

### 9.3. Closure, восстановление и передача потребителю

Полный closure включает capture witness, необходимые исторические object/collection bodies и все обязательные рёбра owning форматов. **Минимальность subset не гарантируется.** Если capture-формат удерживает невыбранные bodies, они входят в closure SELECT тоже. Это не разрешает произвольно добавлять unrelated refs: состав определяется registered format dependency traversal. Пустой proof без captures даёт пустой source closure.

Sealed artifact доказывает content integrity в границах Artifacts, но не сам факт согласованной Source capture-finalize. До реализации нужен конкретный immutable witness/его trusted binding: какие данные подтверждают согласованность capture, какие exact revision→body mappings проверяются после restart и как отвергается корректно sealed, но не finalized capture. Флаг caller `finalized=true` или наличие самого SourceCaptureRef этого не доказывают.

Возвращённые refs не являются lease или receipt живого удержания. До публикации нужен existing scoped owner, атомарно проверяющий доступность/исходное удержание и acquiring target holds; source release выполняется owning lifecycle отдельно. Source read не вызывает Pack и не производит скрытый handoff. Точный Pack input и scope binding согласуются с владельцем Pack; результат обсуждения фиксируется отдельно.

Mapping: SourceProofResult.proof → PackStoredProvenance.source_proof; Planning dependencies остаются отдельным existing tuple[PlanDependency, ...]. Source не знает адрес metadata и не подтверждает computation Pack. При хранении inherited части её исходный proof не переписывается; построение нового общего proof для новой строки не является правкой provenance исходной строки. DAG передаёт declared groups и результаты, не вычисляет union, fingerprint, subset или closure.

### 9.4. Зависимости и порядок закрытия

| Gate | Что предъявить до реализации | Почему нельзя заменить заглушкой |
|---|---|---|
| Identity | §10.1–2 задаёт варианты, descriptor/key carrier и owning validation; принять schema и полный roster поддерживаемых bindings | Без регистрации и проверки adapters identity не считается admitted |
| Semantic body | SourceRevision, live/tombstone representation, label audit, authored-presence, canonical defaults/overlay witness; устранить расхождения с основным планом | Исторический body не восстанавливается из текущих defaults |
| Capture | §10.3–4 задаёт SourceCaptureWitness, committed SQL_ROWS authority и полный v1 closure; принять format/store bindings | ArtifactRef и seal без committed Source witness недостаточны |
| Encoding | Named schema binding, stable type IDs/версия и совместимость сохранённых proofs/selections | Смена encoding меняет fingerprint и индексы |
| Errors | Единый proof roster §E, schema error translation и typed field paths; устранение пересечения с проектируемыми CRUD diagnostics §4 | Список кодов не закрывает field descriptors и недублирование ошибок всего Source |
| Storage | Concrete exact-read и closure adapter, read boundary, existing scoped holder binding с testable failure contract | Полный refs список не устраняет race с GC |
| Consumer | Проверка Pack-порядка, места usage extraction/matching и transient refs input; решение по pure binding | Запрет прямых междоменных операций не снимается названием helper |

Основной порядок не меняется: inventory → contracts/projector → revisions/history/retained bodies → capture-finalize. На стадии design можно согласовать внешний proof-контракт отдельно; работающий durable proof зависит от этих механизмов. Нельзя требовать всю миграцию producers для принятия схемы, но нельзя объявить durable API реализуемым одним POJO-файлом. Следующий runtime срез допускается только после приёмки его конкретных классов, CRUD зависимостей, ошибок и маршрутов по обязательным критериям проекта.

**Приёмочные условия для незавершённых identity/witness:**

- Identity descriptor должен однозначно определять категорию, scope, owning key validation и версию семантического body-контракта. Runtime проверка пары descriptor/key обязательна; nominal carrier без зарегистрированного adapter недостаточен. Unknown descriptor и чужой world отклоняются, global library identity не объявляется world-owned искусственно. Точные поля и roster ещё не приняты — перечисленные ограничения не являются заменой POJO.
- Capture witness должен однозначно связывать world, exact object/collection revisions и immutable body mappings с успешно завершённой capture-finalize. Источник доверия не может быть caller boolean или текущий latest registry. После restart доступны те же сведения; допустимая форма свидетельства и его конкретный reader ещё требуют проекта.
- Negative cases для witness: sealed, но не finalized capture; подмена body при прежнем exact revision; чужой world; отсутствующее membership evidence; потеря required body после release. Первые четыре дают owning отказ, а GC race закрывается scoped acquisition, не повторной pure validation.
- Отдельно сверить SourceRevision/label и tombstone representation с черновыми сигнатурами основного плана: там label находится в SourceRevision и tombstone описан флагом, здесь label вынесен в audit и предложен union. Пока расхождение не устранено согласованной правкой, реализации этих типов нет.

### 9.5. Проверка требований с владельцем Pack — 2026-11-13

По разрешению пользователя получен review агента Pack в чате `01a1cfce-ff7d-7e30-b738-f075bf490f13`. Сверено с `gen-dag-cache-pack-source-families.md` §6.7, `pack-metadata-dependency-pojo.md` и `pack-preparation-closure-trace.md`. Это подтверждение потребностей и открытых bindings, не приёмка реализации и не изменение Pack-плана.

- **Extraction:** нужен до partial write, сохраняющего поля detailed metadata базы; также describe, если usage ещё отсутствует. Неизменное наследование целой строки extraction не требует. Прямые Pack→extract_usage/match_groups запрещены. Source.select→DAG→Pack допустим как принцип передачи, но точные input/output bindings и место в согласованном порядке ещё не заданы. Source.select возвращает SourceProofResult, поэтому соответствие этому результату конкретного Pack usage input должно быть предъявлено явно; название SELECT не закрывает mapping.
- **Matching:** нужен после формирования metadata и получения Source result, до успешного bind. Проверяет expected usage и предъявленные proof/selections; не подтверждает алгоритм вычисления metadata. Exact result→bind boundary остаётся OPEN.
- **Closure:** Pack допускает полный closure с невыбранными телами, если они обязательны owning capture-формату. Минимальность subset не требуется. Storage dependencies не добавляются в declared usage; лишние произвольные refs запрещены.
- **Holds:** `source_admission: SourceProofResult` — кандидат входа bind одной projection. Это не закрывает closure всех proofs конечного state в final prepare. Точный scoped adoption метод Artifacts/publication не закреплён. Existing finish_preparation проверяет уже удержанное множество, но не приобретает недостающие holds и не доказывает полноту Source closure.
- **Inherited:** один proof строки плюс selections соответствует требованиям потребителя. Неизменная строка переносит прежние proof/selections/basis/Planning без переписывания. Для изменённой строки сохраняются exact historical dependencies полей, но selections строятся относительно нового общего proof. Старые indices не переносятся механически. Partial update с неизвестным происхождением сохраняемых полей отклоняется; неизменное наследование старой строки без детализации допускается по owning Pack правилам.

Вывод: full closure и multi-capture модель совместимы с потребителем. Pure direct binding исключён, а точные DAG/Pack inputs и atomic adoption — внешние открытые зависимости. Source продолжает собственные identity/codec/error contracts; не вводит Pack DTO, не меняет порядок операций и не реализует чужой adoption owner.

## 10. Identity и finalized witness: конкретный проект Source

Владелец всех новых типов ниже — Source. Это проект для приёмки, а не просьба Pack определить Source POJO и не отчёт о runtime. Этот раздел заменяет неопределённые варианты identity/witness в §3 и §9 конкретным предлагаемым решением. До кода остаются приёмка решения и привязка реализации к существующим storage ports. Все новые POJO frozen/strict/extra-forbid/revalidate-always; поля обязательны, включая nullable; коллекции tuple. Discriminator поля обязательны и не заполняются скрытым default.

### 10.1. Descriptor и носитель ключа

Публичный модуль `app.dataModel.sourceVersioning.sourceDescriptor`:

- `SourceDescriptorCategory`: REGISTRY_MEMBER, LIBRARY_MEMBER, ENTITY, SETTINGS, COLLECTION.
- `SourceDescriptorScope`: WORLD, GLOBAL.
- `SourceMemberKeyKind`: NONE, TEXT, UUID. Это категории wire-ключа, не перечень значений owning реестров. Enum-key owning домена использует TEXT с проверкой допустимых enum values адаптером.
- `SourceCollectionOrder`: SET, SEQUENCE.
- `SourceDescriptorKey = RegistryKey[SourceDescriptorRegistry]` — existing nominal RegistryKey, не новый generic механизм.
- `SourceDescriptorDefinition(key: SourceDescriptorKey, category: SourceDescriptorCategory, scope: SourceDescriptorScope, key_kind: SourceMemberKeyKind, collection_order: SourceCollectionOrder | None, member_descriptors: tuple[SourceDescriptorKey, ...])`.
- `SourceDescriptorRegistry(entries: tuple[SourceDescriptorDefinition, ...])` — immutable configuration Source composition, не mutable service в proof.
- `SourceMemberKey` — Source-owned nominal str subtype; strict Python/JSON string, min_length=1, без strip/casefold/coercion. В публичной identity он допустим только вместе с descriptor. Это не RegistryKey[R] owning домена и не утверждение compile-time проверки пары.

Registry validation: unique keys; registry member требует WORLD и TEXT/UUID; library member требует GLOBAL и UUID; entity требует WORLD и NONE (его uid — отдельное поле); settings требует WORLD и NONE. Collection требует WORLD, NONE, явный collection_order и непустой уникальный список зарегистрированных non-collection member_descriptors. У non-collection collection_order=None и member_descriptors=(). Циклов коллекций здесь нет: member — object, не другая collection. Definition не содержит Python type, callbacks, codec, DB или holds.

Descriptor key стабилен для логического вида источника и не содержит revision тела или текущую codec version. Смена body format сама по себе не создаёт новую object identity. Application binding каждой definition содержит exact owning key adapter, body codec/format bindings и semantic projector; их типы не передаются в proof. Неизвестный descriptor и несовпадающая category/scope/key_kind — отказ. Historic descriptor bindings нельзя удалять, пока существуют удерживаемые proofs соответствующего формата.

Для WorldSlice binding key берётся из owning `pojo_cls.SCHEMA_ID`; registry-member и collection descriptor имеют разные Source keys: `SCHEMA_ID + "/member"` и `SCHEMA_ID + "/membership"`. Это явная регистрация по owning schema, не автоматическое перечисление SQL колонок и не public Python class. Пример подтверждённого кандидата: `SCH-WORLD-TERRAIN/member` ↔ WorldTerrainRegistry / TerrainRegistryEntry.system_terrain, TEXT; `SCH-WORLD-TERRAIN/membership` ↔ соответствующий состав. Сам факт SCHEMA_ID не разрешает регистрацию: uniqueness, семантика порядка и writer coverage проверяются отдельно. §3.1 остаётся roster кандидатов, а не объявлением всех 36 slices поддержанными.

Owning key adapter выполняет strict validate и exact encode обратно: результат должен совпасть с исходным токеном. Нормализация на историческом read запрещена. Для UUID требуется canonical lowercase hyphenated UUID, как в TemplateEntry; EntityUid сам по себе этого не гарантирует. Для TEXT применяются реальные ограничения owning поля, включая enum и RegistryKey. Проверка наличия ключа выполняется по captured membership, не latest registry. Синтаксически допустимый токен ещё не доказывает существование источника.

### 10.2. Точные identity и version POJO

Публичный модуль `app.dataModel.sourceVersioning.sourceObjectId`; каждый kind — Literal соответствующего значения SourceDescriptorCategory:

| Тип | Полный состав полей |
|---|---|
| RegistryMemberId | kind, world_uid: EntityUid, descriptor: SourceDescriptorKey, member_key: SourceMemberKey |
| LibraryMemberId | kind, descriptor: SourceDescriptorKey, template_uid: EntityUid |
| EntityObjectId | kind, world_uid: EntityUid, descriptor: SourceDescriptorKey, entity_uid: EntityUid |
| SourceSettingsId | kind, world_uid: EntityUid, descriptor: SourceDescriptorKey |
| SourceCollectionId | kind, world_uid: EntityUid, descriptor: SourceDescriptorKey |

`SourceObjectId = Annotated[RegistryMemberId | LibraryMemberId | EntityObjectId | SourceSettingsId, Field(discriminator="kind")]`. Collection намеренно не входит в object union. Entity включает world: одинаковый uid не должен скрыто связывать источники разных миров; переходный mapping существующих globally unique uid выполняет owning adapter без изменения uid. Library остаётся global, а её принадлежность конкретному миру доказывает world-scoped membership. Имя шаблона не заменяет template_uid, pack_uid не добавляется в identity template.

`sourceObjectRevision.SourceRevision(seq: Annotated[StrictInt, Field(gt=0)], content_hash: RevisionHex)` — semantic revision. `sourceVersionRef.SourceVersionRef(object_id: SourceObjectId, revision: SourceRevision)` и `sourceVersionRef.SourceCollectionVersionRef(collection_id: SourceCollectionId, revision: SourceRevision)` — разные ссылки на object и membership, не два представления одного вида. `sourceDependencies.SourceDependencySet(objects: tuple[SourceVersionRef, ...], collections: tuple[SourceCollectionVersionRef, ...])`. Это исправляет прежнюю дыру одинакового SourceVersionRef в обоих полях. Все usages, atoms и canonical ordering §6/9 используют этот distinction.

`sourceBodyVersion.SourceBodyVersion(source: SourceVersionRef, body: ArtifactRef)` — mapping live object; `sourceBodyVersion.SourceCollectionVersion(source: SourceCollectionVersionRef, body: ArtifactRef)` — mapping состава. Body format должен быть зарегистрирован для descriptor и версии; semantic hash не равен автоматически content_hash ArtifactRef. `sourceCollection.SourceCollectionBody(collection: SourceCollectionId, members: tuple[SourceObjectId, ...])`: members unique по full identity; WORLD members того же мира, GLOBAL library members допустимы только если их descriptor включён в member_descriptors. SET сортируется по canonical bytes; SEQUENCE сохраняет owning порядок. Порядок значим и входит в semantic hash. Несовпадение body.collection с mapping.source.collection_id — отказ.

Proof не доказывает absence через ссылку на tombstone: отсутствие/состав устанавливается exact collection revision. Live SourceCapture не содержит tombstone body. Удерживаемая старая live revision остаётся валидной после удаления текущего объекта. Проект исторического tombstone storage и label audit не включается в proof POJO: это отдельные revision storage contracts шага 3. Label не влияет на SourceRevision equality и canonical proof. Эти два уточнения требуют синхронизации черновых сигнатур основного плана при приёмке, не молчаливого изменения runtime.

### 10.3. Один capture body и один finalize witness

`app.dataModel.sourceVersioning.sourceCapture.SourceCapture(world_uid: EntityUid, objects: tuple[SourceBodyVersion, ...], collections: tuple[SourceCollectionVersion, ...])` — единственный capture body. Отдельного дублирующего Snapshot/CaptureEvidence с теми же mappings нет. Objects/collections canonical по encoded full source ref; unique identity, одна revision на identity. Все WORLD identities совпадают с world_uid. Capture содержит все bodies перечисленных members используемых коллекций; неразрешённый member — INCOMPLETE_CLOSURE. Это выбранная полная форма первой версии, не обещание минимального subset storage.

`app.dataModel.sourceVersioning.sourceCaptureWitness.SourceCaptureWitness(capture_uid: EntityUid, world_uid: EntityUid, capture_body: ArtifactRef)` — единственная immutable finalize запись. Capture uid выдаётся Source до finalize для идемпотентности; не выводится из Pack publication и не является holder/lease. Повтор uid с тем же full body ref возвращает существующий committed witness, с другим body/world — конфликт. У witness нет finalized bool, времени expiry, списка holds и копии mappings.

`SourceCaptureRef(world_uid, artifact)` сохраняет форму: **artifact указывает на SourceCaptureWitness, а не на SourceCapture body**. Оба public world_uid должны совпадать с decoded witness и capture. Предлагаемые owning formats: `source.capture` v1, BLOB (canonical bytes SourceCapture); `source.capture-witness` v1, SQL_ROWS (SourceCaptureWitness, row_count=1). Имена/версия являются частью этого проекта, должны регистрироваться через existing ArtifactFormatContract, не через второй codec/store. Hash/size относятся к exact owning encoding. Изменение формата в будущем требует новой supported version и сохранения decoder старой версии.

Источником доверия является committed запись owning Source finalization store, читаемая exact witness backend. Наличие скопированных canonical bytes/валидного SQL_ROWS ref или seal в общем каталоге недостаточно. Arbitrary artifact staging не может создать committed finalize запись. Отдельная mutable фаза staging не входит в witness bytes: owning backend отличает staged content от committed finalization по транзакционному состоянию Source. Public proof читает только committed записи.

Finalization store не является вторым body store: тела размещает Artifacts. Он сохраняет Source факт финализации и предоставляет SQL_ROWS owning view witness. Это не публикация мира, не Snapshot revision и не замена существующего publication outcome ledger. Конкретные SQL таблицы/indices и scope-bound adapter реализуются только в шаге capture-finalize после revisions/holders; этот проект не создаёт миграцию.

### 10.4. Finalize, exact read и closure

До finalize подготовлены sealed body artifacts и полный capture body под действующим staging hold. Source не вычисляет seq во время capture. Effective inputs, включая canonical defaults, должны уже иметь exact revision→effective-body mappings: storage содержит материализованный semantic body с authored-presence. Историческое чтение не накладывает текущие defaults. Смена defaults/overlay policy, меняющая effective body, должна учитываться owning revision preparation до capture; отсутствие такой версии — отказ, не synthetic seq в finalize.

В одной короткой транзакции existing commit scope, сериализованной с mutation/prune: проверить ожидаемые object/membership revisions и exact body mappings; проверить seals; приобрести source capture holds на body, witness и все обязательные dependencies; записать committed witness. Только после успешного commit выдаётся SourceCaptureRef. При конфликте повтор захвата выбирает owning DAG в пределах трёх попыток основного плана; proof pipeline retry не выполняет. Unknown commit outcome восстанавливается existing transaction recovery и exact lookup capture_uid, не повтором с новым uid. Acquire и witness commit должны rollback-иться вместе; техническое связывание source finalize с existing artifact scope — обязательный тест реализации.

READ/ADMIT/SELECT: exact-read committed witness по full ArtifactRef → проверить uid/world/format/hash/row_count → exact-read capture_body → проверить canonical capture и world → проверить membership каждой заявленной dependency и equality exact revision → проверить required body formats/bytes и собрать closure. Source proof не перепроверяет latest revisions после finalize и не запускает mutation. После restart witness и capture доступны по тем же refs. Если сохранённого witness нет, sealed capture body не превращается в finalized capture.

**V1 closure одного непустого use:** witness artifact + capture_body + все body refs mappings в этом capture + их обязательные owning format dependencies. Exact dedup/sort по §9.2. SELECT любого непустого subset того же capture сохраняет весь этот storage closure; его logical usage остаётся только выбранным subset. Несколько captures дают union closure. Пустой proof — пустой closure. Это сознательно полный, проверяемый формат, согласующийся с ответом Pack §9.5.

Witness нельзя удалить отдельно, пока удерживается его ArtifactRef; удаление owning SQL_ROWS через existing GC guard. Holding witness обязан защищать обязательные closure dependencies по accepted artifact dependency/holder binding. SourceProofResult сам hold не приобретает: publication приобретает весь returned closure атомарно до освобождения исходного holder. Backup/import не может восстановить доверие одним пользовательским JSON: требуется доверенное восстановление finalized Source rows и artifact catalog либо новая owning capture-finalize.

### 10.5. Ответственность реализации и приёмка среза

| Concrete кандидат / модуль | Ответственность и зависимости | Критерий отказа |
|---|---|---|
| SourceDescriptorBindingRegistry / application/worldData/sourceVersioning/contracts/descriptorBindings.py | Immutable composition binding descriptor → owning key validator/projector/codec; без чтения latest и mutable runtime регистрации | Unknown descriptor принят, key изменён нормализацией, доменная модель импортирована в source identity POJO |
| SourceCaptureFinalizationStore / application/worldData/sourceVersioning/capture/finalizationStore.py | Internal scope-bound append/exact-read finalize record; использует готовые mappings и existing commit scope, не планирует capture | Свой commit, выдача ref до commit, назначение seq или retry workflow |
| SourceCaptureWitnessBackend / application/worldData/sourceVersioning/capture/witnessBackend.py | Owning SQL_ROWS format adapter поверх finalization store; exact committed read/verify и guarded deletion | Staged либо caller-supplied witness признан finalized; общая seal-проверка вместо проверки Source record |
| SourceProofReadBinding / proof/readBinding.py | Witness → capture → bodies exact read через owning bindings | latest fallback, чтение staged record, самостоятельная финализация |
| SourceProofClosureCollector / proof/closure.py | Полный v1 traversal и canonical refs, shared exact reader | Пропуск невыбранного body из capture v1 или добавление unrelated ref |

До runtime приёмки обязательны конкретные сигнатуры внутренних ports/диагностики, canonical type IDs и scope integration tests. Поля identity/witness здесь определены; это уже не dependency на неизвестный контракт другого владельца. Оставшиеся детали реализации принадлежат Source и принимаются в следующих конкретных срезах implement-plan. Ноды DAG и Pack DTO этим разделом не меняются.

Минимальные проверки: foreign descriptor/world; key canonical round-trip; object ref в collections и обратная подмена; duplicate/conflicting revisions; typed UUID mismatch; SET/SEQUENCE round-trip; sealed unfinalized capture; same capture_uid different body; rollback witness+holds; unknown commit recovery; restart после удаления latest; deletion/GC при удерживаемом witness; subset с неизменным полным closure; empty proof; несколько независимых diagnostics. Все обязательные проектные критерии по-прежнему применяются: перечень тестов не является приёмкой.

