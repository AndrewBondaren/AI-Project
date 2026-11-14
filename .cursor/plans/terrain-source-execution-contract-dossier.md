# Terrain registry: owning execution contract для Source

2026-11-14. **PROPOSED / NOT ACCEPTED / NOT runtime-ready.** Ограниченная контрактная проработка по Source P2.13 и REC-1. Ни SourceDurableProof/R1/R2, ни Pack, ни DAG не меняются. Документ не закрывает REC-1 самостоятельно. Все ниже предложенные модули и методы отсутствуют до отдельной принятой реализации; это не утверждение наличия API.

## Согласованное решение пользователя

2026-11-14: **cell_state_registry — оставить как есть, разобраться отдельно, вне скоупа данного плана.** Владение, правила и реализация реестра здесь не проектируются. Прежние вопросы о назначении владельца state сняты с текущего этапа. Terrain.default_state сохраняется как существующее nullable поле и внешняя ссылка; её наличие не означает приёмки исполнения state-механики.

**Граница шага 1, уточнённая с пользователем 2026-11-14:** результат этого этапа — POJO/валидация, codec/manifest, семантика ссылок и требования целостности, inventory callers. Новые междоменные API, scoped bindings, Input/Outcome/Error внешних зависимостей и DAG routes здесь не проектируются. Отсутствие таких будущих API не блокирует завершение семантического dossier. Их совместное проектирование с DAG относится к шагу 3; приведённые ниже прежние требования получить scoped APIs как prerequisite шага 1 отозваны. Existing read paths не подтверждают целевой контракт. Общая приёмка реализации по всем правилам остаётся обязательной; данный этап не объявляет runtime готовым.

**Уточнение пользователя 2026-11-14: «адаптация старой формы под строгим запретом».** Это решение отменяет предложения ниже о legacy before-validator, выводе hills_authored из наличия hills, compatibility serializer и автоматическом преобразовании старых inputs. Целевой вход должен явно соответствовать новому строгому контракту; отсутствующий обязательный hills_authored и старая форма отклоняются. Затронутые constructors/callers переводятся на целевую форму непосредственно, без adapter, fallback, dual-read или угадывания authored state. Семантика согласованного hills_authored сохраняется. JSON как формат сам по себе не запрещён: запрещено принимать старую форму через преобразование в новую. Bootstrap не получает исключения из запрета; неполные старые данные не нормализуются автоматически. Исторические bytes не переписываются и не удаляются этим решением. Compatibility-предложения в §2–5a считаются отозванными; ниже документ сведён к единому целевому контракту; полнота caller cutover требует приёмки.

2026-11-14, в owning terrain чате: после объяснения необходимости сохранять absent / explicit None / policy пользователь ответил «Окей». Согласовано явное поле `hills_authored` в существующем TerrainRegistryEntry для сохранения authored-presence через canonical round-trip. Это согласование выбора representation, а не приёмка всех деталей validation/serialization, caller migration, execution contract или разрешение реализации. Соответствующий выбор в §2 больше не является несогласованной альтернативой; остальные OPEN и общий статус NOT ACCEPTED сохраняются.

## 1. Рекомендация и границы

Выбран `WorldTerrainRegistry`, `SCH-WORLD-TERRAIN`, world slice `terrain_registry`, identity `system_terrain`. Terrain владеет полным body, validation, authored-presence и semantic projection. Source владеет descriptor, identity carrier, revision, proof, collection refs и tombstone. Нельзя превращать terrain body в Source-owned mirror или считать `TerrainSupportEntry` полной записью.

Рекомендуется согласованно укрепить **существующие** `backend/app/dataModel/terrain/terrainRegistryEntry.py::TerrainRegistryEntry` и `worldTerrainRegistry.py::WorldTerrainRegistry`, переиспользовать `EligibilityRule`, `HillPolicy`, `HillShape`. Это затрагивает callers и требует project acceptance до кода. Отдельная семантика нового зеркального DTO не доказана — создание такого DTO не предлагается. До укрепления нынешний frozen entry не является immutable durable body: eligibility — изменяемый list, root registry — list; extra ignore теряет неизвестные поля, default/wire coercion не равны strict canonical decode.

`SurfaceSupportInput/TerrainSupportEntry` из `dataModel/terrain/relief/surfaceCoating/surfaceSupportInput.py` имеют отдельную доказанную consumer semantics: subset и сортированную проекцию. `application/worldData/planning/composition/support/surfaceSupportCapture.py::SurfaceSupportCapture.capture` сортирует entries, берёт только key/category/default_material/merge_rank/eligibility/hills/hills_authored. `application/worldData/generators/terrain/landcover/planning/capturedSources.py::capture_landcover_policy` восстанавливает только этот subset и передаёт captured.hills_authored в override. Нельзя использовать результат как full body, добавлять в support Source поля или переносить его сортировку на Source collection.

## 2. Полный рекомендуемый body

Порядок ниже — кандидат фиксированного canonical field roster, не уже зарегистрированный manifest. Все поля semantic, exclusions = пусто. Отдельного label поля у entry нет. `glossary_ref` не исключается по имени. Для полей без доказанного вычислительного consumer это консервативное включение, а не выдуманное доказательство использования.

| Поле | Тип и смысл / evidence |
|---|---|
| system_terrain | `RegistryKey[WorldTerrainRegistry]`, точная owning identity; entry_for, coverageResolver, terrainMerge |
| glossary_ref | `str | None`, ссылка на glossary, default None; concrete resolution/invalidation consumer OPEN, сохранить полностью |
| terrain_category | `str`, категория; keys_for_category и SurfaceSupportCapture category conversion; ref-integrity к WorldTerrainCategoryRegistry отдельно |
| travel_modifier | finite `float | None`, default None, travel характеристика; defaults в canonical entries, прямой entry consumer в этом trace не доказан, OPEN |
| danger_level | `str`, default "none", danger характеристика; canonical entries; runtime resolution OPEN |
| has_state | strict `bool`, default False, поддержка состояния; door/gate/window defaults; полный consumer trace OPEN |
| default_state | `str | None`, default None, начальное состояние; door/gate/window = closed; registry/ref rule OPEN |
| default_material | `str | None`, default None; SurfaceSupportCapture переводит в MaterialKey; это ссылка, не embedded material |
| gap_width | strict `int >= 1 | None`, default None; crevice default 2; override/entry resolution OPEN |
| merge_rank | strict `int`, default 0; application/worldData/masks/terrainMerge.py и capturedSources candidate ordering |
| eligibility | **tuple[EligibilityRule, ...]**, default (); coverageResolver ordered evaluation, required rejection и weighted scoring; не set |
| inertia | finite `float > 0`, default 1.0; application/worldData/regions/stateChange/progress.py: strength * ticks / (inertia + weight) |
| hills | `HillPolicy | None`, default None; authored tri-state ниже |
| fill_roles | `tuple[TerrainFillRole, ...]`, default (); WorldTerrainRegistry.column_terrain_key фильтрует suppliers, enum fallback_role |
| fill_priority | strict `int`, default 0; column_terrain_key: maximum priority, lexical key tie-break |
| morph_hydrology_role | `HydrologyCellRole | None`, default None; existing validator допускает только LAKE/None; downstream morph consumer audit OPEN |
| supports_open_land_grade | strict `bool`, default False; generators/terrain/relief/sample/openLandTerrains.py и terrainMap.py |
| open_land_profile | Literal["plains", "forest"] | None, default None; terrainMap.py возвращает ReliefConditionTerrain(profile) |

Последний тип в таблице читается как nullable literal. Existing invariant: supports_open_land_grade iff profile is not None. Не добавлять без отдельного решения новые связи has_state/default_state или диапазоны travel_modifier/merge_rank. Запрет nonfinite travel_modifier — рекомендуемое усиление canonical boundary, старые rows автоматически не исправляются.

### Authored-presence и nested values

**Исправление feasibility после Source review:** `CanonicalCodec._encode` читает ровно `type(value).model_fields`, проверяет значения через strict model_validate и кодирует каждое поле. `RegisteredTypeEntry` не предоставляет field adapters. Предыдущее предложение невидимой canonical metadata отозвано. Generic codec не расширяется.

Рекомендуемый конкретный вариант: добавить **19-е обычное поле** `hills_authored: StrictBool` в существующий TerrainRegistryEntry после open_land_profile. Поле frozen вместе с моделью, без exclude=True, private attribute или computed_field; default на объявлении отсутствует. Existing has_authored_hills возвращает hills_authored, а не model_fields_set. Это owning semantic fact существующей записи, не зеркальный DTO. Canonical manifest регистрирует эту же модель; codec видит 19 полей штатно. До реализации обязательны project acceptance изменения модели и проверка отсутствия прежней persisted canonical регистрации этого класса; обнаруженный старый format нельзя переопределить.

Правила construction/validation целевого контракта:

* hills_authored — обязательный strict bool без default; missing отвергается. hills=None и false означает отсутствие authored override; None/true — explicit null; policy/true — explicit policy. False+policy запрещено. Presence не выводится из наличия ключа, значения, fields_set или старых bytes.
* Python callers непосредственно создают целевые immutable values: eligibility/root/shapes/fill_roles — tuple, без приёма list через conversion validator. JSON может представлять целевые последовательности массивами через штатный строгий JSON decoder; это транспорт нового контракта, а не восстановление старой формы. Обязательный hills_authored должен присутствовать в JSON.
* Export/import и schema описывают одну целевую форму с hills_authored; serializer не скрывает marker и не удаляет explicit null. Full-body export не использует exclude_unset/exclude_none для удаления обязательного semantic содержания. Старый input отклоняется без repair/continuation, dual-read и fallback.
* with_hills(value) валидированно заменяет hills=value и hills_authored=True; with_eligibility сохраняет оба значения. model_copy/replace не обходят validation. model_construct не является публичной input boundary: только полные trusted значения с последующей строгой проверкой; _fields_set не источник semantics.
* Default значения остальных полей в таблице описывают имеющиеся owning значения, а не разрешение достраивать старый body. Целевая required-политика зафиксирована в §5b: все 19 полей и полные nested rosters обязательны. Bootstrap исключений не имеет.

Для остальных полей semantic presence не доказана; audit fields_set/exclude_unset проверяет отсутствие скрытых зависимостей. Legacy before-validator и compatibility serializer не проектируются.

`EligibilityRule` (existing eligibilityRule.py): fact nonempty str; op EligibilityOp; lo/hi finite float nullable; weight finite >= 0 default 1; required bool default False. GTE/IN_RANGE требуют lo, LTE/IN_RANGE требуют hi, при обоих lo <= hi. Сохранять также неиспользуемую данным op границу; не «упрощать» её. Рекомендуемый canonical boundary strict, forbid extra, revalidate instances; bool не int/float. Existing validators переиспользуются, целевой strict boundary не допускает legacy coercion. Порядок, повторы и нулевые weights сохраняются. Catalog допустимых fact names/ref rules OPEN.

`HillPolicy` (existing hillPolicy.py): min_spacing int >=1 default 500; radius int >=1 default 40; height int >=1 default 2; shapes tuple[HillShape,...] default (). `HillShape`: circle, oval, double_circle, double_oval. Пустой shapes **не** отсутствие hills и не отсутствие холмов: resolved_shapes вызывает catalog в enum order. Не разворачивать empty в explicit tuple при encode: это изменяет authored body. Execution v1 фиксирует каталог именно `(circle, oval, double_circle, double_oval)` и его порядок; изменение каталога/толкования empty требует execution version. Existing shape duplicates/order сохраняются. Случайность/world uid принадлежит consumer generation inputs, не semantic projector.

Deep immutability требует tuple eligibility и tuple registry root, immutable nested values, отсутствия alias на входные lists и строгой повторной проверки экземпляров. Frozen outer model недостаточно. `fill_roles`, `shapes`, rules и registry members не сортируются и не deduplicate silently. Дубликаты registry identity отвергаются явно. Registry membership рекомендуется **SEQUENCE**: сохраняется authored order; независимость отдельных consumers от order не доказывает общую SET semantics. Перестановка members меняет collection semantic identity, но не body отдельных entries.

## 3. Reuse inventory и цена изменения

Проверенные callers, которые должны войти в будущий migration inventory (это не полный writer inventory):

* `dataModel/terrain/worldTerrainRegistry.py`: canonical_defaults/canonical_engine создают list из constants; все entry literals eligibility lists переводятся в tuple; entry_for/keys_for_category/column_terrain_key читают sequence и сохраняют поведение.
* `dataModel/terrain/terrainRegistryEntry.py::with_eligibility`: сейчас принимает list и копирует list; перейти на immutable tuple result, отдельно принять допустимый input тип. with_hills обязан сохранять explicit presence, включая None.
* `dataModel/terrainMasks/landcoverRegionsCategoryPolicy.py`: apply_to вызывает with_eligibility(source.eligibility), строит `[*rules, rainfall]`; обновить boundary без изменения precedence.
* `application/jsonValidation/terrainHillRegistry.py`, `application/worldData/generators/terrain/terrainZ.py`, `application/worldData/regions/coverageBackground.py`, `application/worldData/generators/terrain/landcover/collect.py`: создают WorldTerrainRegistry из list; адаптировать construction, сохранить order.
* `application/worldData/generators/terrain/landcover/planning/capturedSources.py`: list construction и eligibility=list; оставить partial consumer semantics и отдельный authored bit, не делать durable reader.
* `application/worldData/planning/composition/support/surfaceSupportCapture.py`: tuple(row.eligibility) совместим, sorted projection остаётся локальной.

OPEN: все generic World JSON hydration/export/import, WORLD_SLICES, fixtures, tests, repository writes, model_copy/model_construct/replace, root append/index mutations и exclude_unset serialization. WorldService._save/reconcile, repairWorldDefaults, import/copy и прямые SQL writers должны получить Source-owned полный inventory; этот список не доказывает его завершение. До audit и принятия caller changes recommended POJO strengthening не разрешено внедрять.

### Минимальный дополнительный impact явной presence

`SurfaceSupportCapture.capture` продолжает читать has_authored_hills без смены semantics. В `capture_landcover_policy` construction entry должен передавать `hills_authored=e.hills_authored`, иначе новый обязательный marker отсутствует и validation должна отказать. Находящийся рядом model_construct относится к **LandcoverTerrainPolicy**, не TerrainRegistryEntry: его _fields_set восстановление сохраняется, модель policy этим решением не мигрируется. `LandcoverTerrainPolicy.apply_to` использует strengthened with_hills и сохраняет прежнюю precedence; registry_hills_authored остаётся отдельным параметром consumer projection.

Existing TerrainRegistryEntry.authored_hills_key_from_wire и WorldTerrainRegistry.authored_hill_keys_from_wire определяют presence по наличию hills и потому не подходят целевому контракту. В принятом cutover их callers должны читать валидированное hills_authored; старое inferred чтение не сохраняется как fallback. application/jsonValidation/terrainHillRegistry.py перестаёт определять terrain presence через raw keys. canonical entry literals непосредственно задают hills_authored=True для authored policy/null и False для отсутствия override: runtime inference отсутствует. LandcoverTerrainPolicy имеет собственную semantics и не объявляется автоматически мигрированной этим изменением.

Acceptance требует: missing hills_authored rejected в Python/JSON/canonical; None/false round-trip не становится true; with_hills(None) даёт true; with_eligibility не меняет presence; full export сохраняет marker/null; list на strict Python tuple boundary rejected; старые input/bytes не исправляются; capture_landcover_policy передаёт captured marker явно. SEQUENCE/all semantic остаются recommendations. Source tombstone разрабатывает Source.

## 4. Codec и граница дальнейшей интеграции

Шаг 1 задаёт требования к преобразованию полного строгого TerrainRegistryEntry в canonical bytes и обратно, semantic projection и извлечению exact system_terrain. Это чистые преобразования без DB, latest, stage, lease, commit или public domain calls. Предложения TerrainSourceAdapter, нового TerrainSourceError и composition signatures сняты с этого этапа. Классы междоменной интеграции, mapping ошибок и nested call trace определяются на шаге 3 совместно с DAG; здесь для них не создаются временные API.

Предлагаемый `.../terrain/source/encoding/terrainSourceSchemaV1.py::TERRAIN_SOURCE_SCHEMA_V1` — terrain-owned manifest для existing entry с 19 обычными полями и nested types; fixed IDs/enum registrations и collision checks **OPEN**, не назначены произвольно. Field adapters отсутствуют и не требуются рекомендуемому варианту. Использовать existing `backend/app/encoding/canonicalCodec.py` и application binding `backend/app/application/encoding/canonicalCodec.py`, existing content_digest, без второго JSON codec/hash. Proposed format `terrain.source-entry`, format_version=1: terrain владеет semantic format, Artifacts владеет регистрацией/verified storage; exact ArtifactKind и registration module требуется согласовать, **OPEN**. Эти пути — предлагаемые, не существующие реализации.

Semantic bytes включают весь roster и hills presence под отдельным semantic domain/manifest binding; Artifact content hash и Source semantic hash не приравниваются. Source key adapter обязан проверить exact owning key round-trip, world/descriptor и соответствие system_terrain object identity. Никакой latest lookup для decode historical body.

Source execution registration key = `(registered terrain member descriptor, execution_version=1)`; numeric descriptor ID остаётся Source-owned. Immutable registration связывает codec/format, manifest, projection без exclusions, key adapter, SEQUENCE membership, hills presence/catalog, ref rules и Source tombstone semantics. Version не build number. Любая перемена влияющих правил — новая версия; format_version не заменяет execution_version. При отсутствии exact old executor незавершённая recovery не запускается, не переходит на latest, сохраняет request/holds; typed infrastructure error согласуется с publication. Terminal replay возвращает сохранённый outcome по immutable fingerprint без повторного projector.

## 5. Зависимости, replay и bootstrap

Рекомендуемый projector не читает ambient world/settings/fixtures/catalog latest: только полное body и frozen registration. Empty hills catalog закреплён выше; default material/category/glossary не разыменовываются при hashing body. Их содержимое при потреблении — отдельные explicit dependencies, не скрытое расширение body. Изменяемые landcover overrides, климат, world uid/seed, grid, material registry и relief policies относятся к consumer input/capture; запрет ambient projector не означает отсутствие этих runtime dependencies.

Ref-integrity checks в общей transaction читают текущее согласованное состояние: category, default_material, glossary_ref, default_state, danger_level и eligibility fact namespaces требуют точного owning ref roster/nullable policy. Сейчас это **OPEN**, нельзя объявлять строки нессылочными по отсутствию typed key. Нужно определить create/update/delete проверки, inbound usage, missing/foreign refs и scope. Они могут дать новый конфликт при recovery; original expected refs и candidate bodies не заменяются. Не замораживать всю БД для воспроизведения прежнего in-memory outcome.

Delete: по Source P2.17 tombstone — новая revision с index deleted flag без live body mapping, не новая сущность/public DTO, не TerrainRegistryEntry с null полями и не отсутствующий artifact. Terrain определяет допустимость удаления/inbound usage; Source владеет tombstone encoding/hash и seq. Source-owned candidate `application/worldData/sourceVersioning/encoding/tombstoneEncodingV1.py`: existing CanonicalCodec над `("source.registry-member.tombstone", 1, registry_member_id)`, затем existing content_digest(bytes).hex(); RegistryMemberId использует принятый SOURCE_PROOF_SCHEMA_V1 binding, нового type ID нет. Seq, operation/attempt, время, execution_version и прежние bytes в hash не входят. Execution registration ссылается на этот encoder; terrain не создаёт собственного tombstone codec. Это кандидат до vectors/joint acceptance, не принятый DELETE runtime. Исторические body/holds не удаляются по удалению latest member. Pruned live revision — отдельный факт недоступности, не tombstone и не новая semantic revision; исчезнувшие retained bytes также не превращаются в tombstone/prune. Rename key — не скрытая body update: identity change должен быть согласованным remove/add membership batch.

**Статическая feasibility presence, Source P2.16:** повторно проверен `backend/app/encoding/canonicalCodec.py::_decode_one`: exact field names/order сравниваются с model_fields до model_validate. Поэтому canonical payload без 19-го hills_authored отвергается, а никакой validator не достраивает отсутствующее canonical поле. Конкретное ограничение generic codec для предложенного обычного поля закрыто статически без расширения codec. Это не закрывает caller/schema/serializer compatibility, golden vectors или весь REC-1.

Initial bootstrap: до v1 activation инвентаризировать persisted registries, unknown fields, duplicates, nonfinite/coerced values и hills presence. Нельзя восстанавливать потерянную presence догадкой или текущим canonical_engine defaults. First revisions требуют отдельно принятого Source batch с уже целевыми полными bodies, coherent membership, ref checks и retention root. Legacy normalization/repair запрещены; defaults не восстанавливают неполные исходники. Если исходная presence уже потеряна, bootstrap policy/authoritative source OPEN. Restart не выполняет bootstrap повторно поверх имеющейся истории. Порядок inventory → projector → revisions → capture сохраняется.

## 5a. Конечное owning предложение после дополнительного trace

Это завершение ограниченной проработки, не снятие gates. Пользователь согласовал **выбор hills_authored**, но не общий контракт. Следующие сведения уточняют предыдущие OPEN, не разрешают runtime migration.

### Compatibility schema/export/import

Обнаружена существующая регистрация: `backend/app/dataModel/terrain/encoding/surfaceBindings.py::BINDINGS`: WorldTerrainRegistry=16, TerrainRegistryEntry=17, EligibilityRule=18, EligibilityOp=19, HillPolicy=20, HillShape=21, TerrainFillRole=22; `dataModel/hydrology/encoding/surfaceBindings.py` регистрирует HydrologyCellRole=23. Поэтому гипотеза «entry ещё не зарегистрирован» неверна. Изменение model_fields меняет canonical layout ID 17, tuple/frozen root меняет допустимость ID 16. Назначение нового ID тому же Python owner конфликтует с merge_manifests. Generic codec не меняется, mirror не вводится.

**Gate сужен по Source audit** [source-terrain-execution-audit-2026-11-14.md](source-terrain-execution-audit-2026-11-14.md), раздел «Проверка потребителей ID 17 и старых bytes»: SURFACE_MANIFEST → declared_binding → SurfaceEnvelopeCodec использует cache contract version; old18→new19 decoder отвергает до validators. Но текущий encoder не поддерживает list, валидный entry содержит eligibility=list, а registry не frozen/list root. Поэтому текущие валидные full-entry/root не дают таких canonical bytes. Planning route использует MemoryCache/LegacyMemoryCache; persisted SurfaceEnvelope writer в проверенном маршруте не найден. Это не скан исторических artifacts/БД, но и не основание назначать широкую миграцию.

Перед freeze требуется **ограниченное доказательство**: зафиксировать отсутствие поддерживаемого old full-entry writer/format либо предъявить конкретный writer/format и согласовать переход только для него. Прежнее требование всеобщего persisted migration audit по одному ID отозвано. TerrainSupportEntry и TerrainMergeEntry — самостоятельные projections, добавление поля в full entry не меняет их roster автоматически. Их golden bytes/fingerprints и общие nested EligibilityRule/HillPolicy validation всё равно проверяются отдельно. Новый Source format/execution_version не меняет existing cache version автоматически; invalid cache payload нельзя предполагать обычным miss.

| Generic caller / boundary | Прямой cutover в будущем принятом срезе |
|---|---|
| jsonValidation/resolve.py::resolve_model и _resolve_defaultable_wire | Terrain input проходит строгую проверку целевого контракта; missing marker/invalid types не направляются в default repair/continuation |
| jsonValidation/worldSlices.py::canonical_registry_wire, resolve_registry_list_world, _apply_runtime_canonical_merge | Все производимые entries непосредственно целевые; Python constructors получают tuples и явный marker. Исторический overlay/list conversion не служит адаптацией старого Source input |
| jsonValidation/worldRow.py::terrain → apply_landcover_policies | Чтение не достраивает старую запись. Effective consumer projection не становится bootstrap body |
| jsonValidation/facade.py::normalize_world | Не выполняет repair старой формы перед Source acceptance. Export сохраняет явный marker; политика не переписывает authored presence исходного body |
| jsonValidation/terrainHillRegistry.py | Читает hills_authored валидированного entry, не presence raw hills key |
| application/templateLibrary/reliefTerrainSync.py::missing_terrain_entries | Сохраняет различие stored/resolved; не скрывает неполную старую запись defaults |
| application/templateLibrary/packs/domainAdapters/relief.py | Создаваемые новые canonical entries сразу соответствуют целевому контракту. Старые stored rows не обновляются автоматически |
| engine prompt/schema callers (llmGroupPayloadBuilder, llmPayload, graphCompiler) | Новая schema включает обязательный hills_authored. Никакого скрытия marker или старой схемы по fallback |
| SurfaceSupportCapture / capture_landcover_policy | Первый читает explicit presence; второй прямо передаёт e.hills_authored и tuple eligibility. Partial projection не объявляется full durable body |

Полнота generic caller inventory сверяется с отдельным Source audit, включая export/import/copy, fixtures и schemas. Эта таблица задаёт необходимое поведение будущего cutover, не разрешает сейчас менять код. Новый strict contract отвергает unknown fields, bool-as-int и coercion строк в числа; nested EligibilityRule/HillPolicy validation и projection vectors проверяются отдельно. Старые DefaultWhenMissing/import continuation не используются для восстановления старой формы. JSON decoder допустим только как декодирование явно целевой формы; новый legacy preprocessing запрещён.

Раздельный legacy/canonical validation context больше не нужен для совместимости: marker является частью целевого внешнего и внутреннего контракта. Его семантическая проверка обязательна, «marker injection» не повод скрывать поле. Старые records остаются нетронутыми и отклоняются целевым reader; неизвестная historical provenance требует явного решения вне этого dossier, без переписывания/удаления.

### Ref-integrity roster: evidence и recommendation

Уточнение по завершённому POJO trace: `EligibilityRule.fact` остаётся точной nonempty string; Source не вводит vocabulary enum/whitelist или alias normalization. У текущего consumer unknown/missing дают None, но это не новая гарантия исполнимости правила. В RegionState current_type/pending_target — live state, history.from_type/to_type — история; оба представлены TerrainKey, история не является Source pin. Подробное evidence — [обзор ссылок](terrain-source-ref-integrity-contract-proposal.md), раздел «Дополнительная проверка двух оставшихся пунктов». Новая политика Regions admission и история as-of этим dossier не проектируются.

Общий принцип не является новым предложением: основной план, раздел «Ref-integrity latest и pinned-графов (решение 2026-10-24)» и п.15, уже требует разрешения исходящих ссылок в итоговом атомарном графе и запрещает неявный fallback. Таблица ниже уточняет адресацию/nullable и observed usages; её старые OPEN по blanket dangling-policy не переоткрывают это решение. Исторические pinned refs проверяются отдельно от latest, без переписывания/потери held bodies. State registry исключён из scope по решению пользователя.

| Поле / inbound | Владелец смысла и доказательство | Nullable / missing / delete |
|---|---|---|
| system_terrain | Terrain identity, WorldTerrainRegistry.entry_for | Non-null; duplicate/mismatch reject. Это identity, не outbound ref |
| terrain_category | Terrain, WorldTerrainCategoryRegistry; keys_for_category и support typed conversion | Non-null. Рекомендован exact target check; unknown reject, без canonical latest fallback в Source apply |
| default_material | Materials, WorldMaterialRegistry; docs/tz_locations.md effective_material, support MaterialKey conversion | None допустим. Non-null missing target рекомендуется reject; удаление material при live terrain usage рекомендуется restrict |
| glossary_ref | Lore, dataModel/lore/loreRegistry/worldLoreRegistry.py; tz_locations.md: display_terrain из lore_registry по glossary_ref | None допустим. Точный key namespace/world scope и missing target policy требует Lore owner; рекомендован restrict для declared live ref, но это не принятая политика |
| danger_level | World danger_level_registry, tz_locations.md § danger_level_registry и effective_danger_level через priority | Non-null, default "none" — обычный ключ, не отсутствие ссылки. Exact owner API/registry model и missing/delete policy OPEN; рекомендован reject unknown/restrict |
| default_state | World cell_state_registry, tz_locations.md: has_state создаёт cell_states с default_state; missing state fallback WARNING | Nullable по POJO. has_state=true + None сейчас не запрещено validator; запрещать это без acceptance нельзя. Target validation и delete restriction требуют owning state contract |
| eligibility.fact | Regions fact vocabulary, coverageResolver → region_facts.value_for(fact) | Nonempty str, не ArtifactRef/registry membership. Допустимый namespace, unknown-fact policy и расширения требуют Regions owner; нельзя принимать произвольный fact как доказанно исполнимый |
| eligibility.op, hills.shapes, fill_roles, morph_hydrology_role, open_land_profile | Owning enums/literal, не внешние object refs | Enum membership/nullable и existing invariants; изменение enum catalog — execution compatibility, не delete другого registry |
| map_cells.system_terrain | Locations/cell storage; tz_locations.md nullable terrain ref | Inbound live usage; recommended restrict terrain delete до явного remove/reassign в согласованном batch |
| terrain_masks.default_landcover.fallback_terrain / terrain_policies.*.system_terrain | Landcover; jsonValidation/index/validate.py::_landcover_checks | Inbound; import validation есть, transaction delete guard не доказан |
| hydrology shore.system_terrain | Hydrology; index/validate.py::_shore_ref_checks | Inbound; тот же gap между import validation и scoped delete |
| RegionState.current_type / declared region entry_type | Regions; capturedSources проверяет current_type в captured registry | Inbound candidates; полный authoritative storage usage inventory OPEN |

Остальные поля — значения, не обнаруженные object references: travel_modifier, has_state, gap_width, merge_rank, inertia, fill_priority, supports_open_land_grade, hills_authored, eligibility numeric bounds/weight/required, HillPolicy numeric knobs. Их semantic включение сохраняется. ТЗ дополнительно объясняет travel_modifier=None как непроходимость, gap_width как cell fallback, has_state/default_state как создание/чтение состояния — прежний пробел по назначению этих полей сужен, runtime trace всё ещё не доказан полностью.

`index/validate.py::_check_ref` пропускает None/empty string и unavailable registry, применяется к normalized import. Эти skips не являются принятой семантикой целостности Source. Требование к будущему исполнению: проверки должны видеть согласованное состояние и учитывать inbound usage; historical held versions сохраняются независимо от live delete. На шаге 1 фиксируются смысл ссылок и inventory, а механизм consistency и API — на шаге 3. Автоматический cascade delete/remap не предполагается; reject/restrict до owning семантического решения остаются рекомендациями.

### Manifest/format/membership: итоговое предложение

`terrain.source-entry` v1 кодирует existing TerrainRegistryEntry с 19 полями в объявленном порядке. Минимальный manifest closure: ID 17 entry RECORD, 18 EligibilityRule RECORD (fact, op, lo, hi, weight, required), 19 EligibilityOp ENUM, 20 HillPolicy RECORD (min_spacing, radius, height, shapes), 21 HillShape ENUM, 22 TerrainFillRole ENUM, 23 HydrologyCellRole ENUM. Это **reuse existing bindings**, не новые IDs. RegistryKey кодируется как существующий str subtype, bool/float/int/nullable/tuple — built-in codec, отдельные type IDs не нужны. WorldTerrainRegistry ID 16 не нужен entry-body manifest: collection уже Source-owned и содержит ordered identities, не вторую копию terrain entries. Его immutable strengthening всё равно затрагивает existing surface consumers.

Manifest owner и format path остаются §4; минимальный closure надо сверить merge_manifests и golden vectors с действующими surface registrations. Включение изменённого ID 17 разрешается только после compatibility gate выше, не путём тихого переопределения. ArtifactKind/format registry port — Artifacts acceptance, не terrain self-registration. Source descriptor/key/proof и tombstone binding остаются Source-owned.

Окончательная **рекомендация** membership — SEQUENCE, сохраняющая порядок уже целевого полного registry из принятого authoritative bootstrap source; duplicate keys reject. Не считать canonical overlay [] пустой коллекцией. Source не сортирует rows по образцу SurfaceSupportCapture. Все 19 полей semantic, exclusions пусты; это консервативная recommendation, не согласованная пользователем policy. Необходимы явное совместное принятие этого выбора и подтверждение authoritative источника целевого bootstrap body без нормализации старой формы.

### Конкретные неразрешимые по текущему trace вопросы

1. Есть ли поддерживаемый old full-entry writer/format ID 16/17 за пределами проверенного Source маршрута? Зафиксировать его отсутствие либо назвать конкретный writer/format и принять локальный переход. Широкая миграция по факту регистрации ID не требуется; nested validation/projection vectors остаются отдельной проверкой.
2. Полон ли прямой caller cutover на единый строгий контракт без repair/continuation? Legacy/canonical context для адаптации не требуется и не проектируется.
3. Bootstrap representation CLOSED решением пользователя: явно подготовленные authored-записи нового строгого контракта, defaults/landcover отдельно. Storage/bootstrap mechanics — шаг 2; отсутствие целевого input означает отказ без нормализации.
4. Семантический inventory собран в [обзоре ссылок](terrain-source-ref-integrity-contract-proposal.md). Общая ref-integrity политика уже принята основным планом; danger закреплён за Locations, cell_state_registry исключён из scope. Source не добавляет whitelist fact или новые правила Regions. Scoped guards и API относятся к шагу 3.
5. Совместное принятие SEQUENCE/all-fields-semantic, строгого caller cutover и Artifacts format registration. Presence уже согласована пользователем и повторного решения о необходимости hills_authored не требует.

## 5b. Строгие POJO и оставшиеся семантические вопросы

Предложение окончательных owning signatures (не существующая реализация):

* `TerrainRegistryEntry.with_eligibility(self, rules: tuple[EligibilityRule, ...]) -> Self`: только tuple; strict revalidation каждого rule; новый immutable entry, без list conversion, сохранение hills/hills_authored.
* `TerrainRegistryEntry.with_hills(self, hills: HillPolicy | None) -> Self`: strict nested validation; новый entry с явным hills_authored=True. Это authored действие, не inference старого input.
* `WorldTerrainRegistry(root: tuple[TerrainRegistryEntry, ...])`: frozen root, только целевые entry, unique system_terrain, сохранение order; Python list отвергается. `canonical_defaults() -> WorldTerrainRegistry` и `canonical_engine() -> WorldTerrainRegistry` строят новые целевые literals с явной presence, а не адаптируют старые rows.
* `TerrainRegistryEntry(*, system_terrain: RegistryKey[WorldTerrainRegistry], glossary_ref: str | None, terrain_category: str, travel_modifier: float | None, danger_level: str, has_state: bool, default_state: str | None, default_material: str | None, gap_width: int | None, merge_rank: int, eligibility: tuple[EligibilityRule, ...], inertia: float, hills: HillPolicy | None, fill_roles: tuple[TerrainFillRole, ...], fill_priority: int, morph_hydrology_role: HydrologyCellRole | None, supports_open_land_grade: bool, open_land_profile: Literal["plains", "forest"] | None, hills_authored: bool)`: рекомендуемый полный constructor roster, все аргументы обязательны, nullable не означает optional/missing. Указанные в §2 defaults — исторические значения для явных новых literals, не constructor fallback.

Для canonical body и целевого full-body wire предлагается полный обязательный roster, включая nested records. `EligibilityRule(*, fact: str, op: EligibilityOp, lo: float | None, hi: float | None, weight: float, required: bool)`; `HillPolicy(*, min_spacing: int, radius: int, height: int, shapes: tuple[HillShape, ...])`. Все модели frozen, extra=forbid, revalidate_instances=always; никакого fallback при missing. Bool не принимается как число; Python numeric fields проверяются на заявленный тип, float значения конечны; canonical boundary не coerces строки или list. Existing limits/invariants из §2 сохраняются: weight>=0, inertia>0, положительные hill knobs/gap_width, bounds и open-land consistency. Никаких новых диапазонов travel_modifier/merge_rank либо has_state/default_state отношений без owning решения. Strict enum members для Python, объявленные enum tokens при штатном JSON decode. JSON schema обязана иметь hills_authored и полный required roster, export сохраняет явный false/null/empty sequence. Serializer не скрывает marker и не формирует старую форму.

Shared nested models уже используются projections: изменение обязательности/defaults/strict validation требует прямого перевода их producers в согласованном срезе и projection vectors. Это остаётся проверкой caller cutover, не разрешением держать dual input или адаптацию старого payload. Отдельный canonical codec/зеркальные nested DTO не предлагаются.

**Итоговая owning recommendation:** SEQUENCE membership; все 19 полей semantic; exclusions пусты; rules/shapes/fill_roles order и повторы сохраняются, duplicate registry identity reject. Presence повторно согласовывать не требуется. Эти рекомендации не объявляются общей приёмкой пользователем.

**Незакрытые семантические вопросы:** допустимые namespaces, смысл missing/nullable и ограничения удаления при inbound usage уточняются только в границах таблицы основного плана. WorldTerrainCategoryRegistry/WorldMaterialRegistry/WorldLoreRegistry подтверждают представления данных. `db/models/world.py:73–74` хранит cell_state_registry/danger_level_registry как raw dict, но это не устанавливает владельца: при необходимости решения по ним требуется остановка и вопрос пользователю. `RegionFacts.value_for` смешивает unknown name и missing observation; его поведение не определяет само по себе целевую политику валидации fact. Наличие или отсутствие scoped APIs не является критерием завершения этого семантического этапа; их проектирование относится к шагу 3.

**Bootstrap — принятое решение пользователя:** явно подготовленные authored-записи нового строгого контракта; defaults и landcover — отдельные зависимости. Effective/normalized registry не является bootstrap body. Storage/bootstrap mechanics относятся к шагу 2, не к normalizer. Исторические данные не переписываются и не удаляются. Завершение семантического этапа не означает приёмки runtime; междоменные ref contracts не требуются на этом этапе.

Дополнительные обязательные callers по Source audit: repairWorldDefaults.apply_import_normalize_to_world выполняет world_wire_from_row → normalize_world → in-place world; использовать его для Source bootstrap запрещено. WorldCopyImport проходит world_handler.import_section и должен входить в generic cutover inventory: только целевые authored inputs без repair старой формы.

## 5c. Owning durable writer: ограниченная сверка шага 2

2026-11-14. В проверенном маршруте **существующий Terrain append-only scoped durable writer не найден**. `application/worldData/registries/worldService.py::_save` вызывает переданный repository method в _write_scope, затем optional region reconciliation; без region editor scope пуст. `db/repositories/sqlite/worldRepository.py::update` вызывает inherited save текущего World. Это legacy row writer, не доказанный append-only writer полного authored terrain и его membership. Наличие transaction вокруг update не делает историю immutable. Поиск terrain_registry в store/writer модулях проверенных repository/worldData путей дополнительного такого writer не предъявил; это scoped вывод, не доказательство отсутствия любых внешних реализаций.

Минимальные owning требования к будущему storage binding: принимать уже проверенный полный authored registry целевого строгого контракта; сохранять exact entry bodies/presence и полный ordered membership без overlay/defaults/landcover/repair; записывать новые immutable версии/переходы без UPDATE прежних bodies и без независимого latest pointer. Заимствовать одну разрешённую domain transaction у утверждённого apply owner; не открывать/commit-ить собственную transaction. Terrain data, Source-owned revision/body/tombstone/membership mapping и требуемые publication/retention facts должны иметь общий atomic outcome; partial failure откатывает целый write, неизвестный commit outcome не объявляется успехом. Source seq/history и Artifacts holds не реализуются второй раз в terrain writer. Исторические bodies остаются читаемыми согласно retention; bootstrap получает только явно подготовленные authored records нового контракта.

**Точная внешняя зависимость:** основной world-source-versioning.md, уточнение 2026-10-27, требует append-only и исключительное применение sets через Snapshot; протокол append-only head/commit и представление draft history там ещё не выбраны. Без принятого Snapshot apply/set→borrowed domain transaction binding и представления owning terrain append-only transition нельзя назначить concrete writer/class/storage layout или выдать WorldService._save за такой writer. Нужен принятый binding от Snapshot/apply owner, в котором Terrain storage исполняет только запись своих данных, а Source revision store — своей истории. Этот раздел не создаёт public API/signatures/DAG, не назначает новый apply owner и не разрешает pregame обход. На этой зависимости конкретизация writer остановлена; runtime и старый JSON не меняются.

## 6. Приёмка и проверки

Нужны golden vectors всех 19 полей и nested enums, absent/null/policy, empty/nonempty/reordered/duplicate shapes и rules; decode→encode byte equality и exact authored round-trip; mutation исходных lists после подготовки не меняет body/hash. Проверить bool/string coercion, NaN/inf, missing bounds, malformed enum, extra fields, inconsistent open-land profile/presence, duplicate identity. Проверить порядок collection, key mismatch, non-ASCII keys, glossary-only изменение (semantic до доказанного exclusion), unchanged body equality, A→B→A Source seq, old execution unavailable, catalog changed with unchanged bytes, current ref conflict после restart, tombstone/live distinction и bootstrap повтор. Реальных vectors/runtime tests этим документом не выполнено.

| Обязательный критерий проекта | Статус |
|---|---|
| Нет pipeline с ветвлением между самостоятельными операциями | На шаге 1 новые pipeline не проектируются; production nested trace проверяется на шаге 3 |
| Нет скрытой orchestration; DAG напрямую вызывает public operations | Новый DAG/NodeId не назначается; public CRUD caller binding OPEN |
| Нет прямых междоменных public вызовов | Новые bindings сняты с шага 1; целевой маршрут проверяется совместно с DAG на шаге 3 |
| Роль/effects/deps/refusal каждого класса | Existing POJO validation, codec serialization, adapter pure projection определены выше; Source apply/Artifacts lifecycle вне этого owner, exact registration/errors OPEN |
| Public contract / implementation boundary | Временные adapter signatures отозваны; здесь только данные/encoding requirements, public операции проектируются на шаге 3 |
| Неизменность утверждённого порядка | inventory→projector→revisions→capture; без новых нод, migration и cutover |
| CRUD данных отдельно C/R/U/D | Codec read не заменяет CRUD read; owning CRUD classes/Input/Output/Error/scope/effects и DAG paths OPEN |
| CRUD настроек отдельно C/R/U/D | Запрет ambient projector не освобождает terrain settings от полного CRUD; именованный settings POJO/API inventory OPEN |
| Междоменный CRUD/dependency protocol | Terrain body recommendation передаётся Source; ref owners/Artifacts format/Source tombstone требуют review, прямое чтение чужих внутренних stores не разрешено |
| Typed POJO/errors, отсутствие дубликатов | Reuse выбран; strict/deep immutable strengthening и errors нуждаются в принятии, mirror не вводится |

**Вердикт:** конкретная recommended representation и semantic policy предъявлены, но приёмка реализации/полного домена отклонена до закрытия OPEN. REC-1 не закрывается scalar version или этим dossier без совместной проверки manifest, callbacks/settings absence, ref integrity, tombstone и bootstrap. Код/ТЗ/чужие планы не изменены.

## 7. Сводный результат ограниченного шага 1

**Статус: семантический dossier подготовлен; не приёмка implementation-плана.** Этот раздел определяет актуальное распределение работ; прежние runtime OPEN не превращаются в новые задания шага 1.

| Результат | Зафиксировано | Evidence |
|---|---|---|
| POJO | Existing TerrainRegistryEntry, все 19 полей обязательны; frozen/strict/extra-forbid/revalidate-always; nullable не означает missing; tuple nested collections. Отдельного Source terrain DTO нет | §2, §5b |
| Authored semantics | Явный hills_authored; отсутствие обязательных полей — отказ; legacy adaptation/dual-read/inference запрещены | Решения пользователя, §5b |
| Encoding | Existing CanonicalCodec; manifest closure IDs 17–23, без registry 16 в entry body; BLOB bytes format. Нет нового codec или неявного latest lookup | §4, §5a, Source audit |
| Projection/membership | Конкретное owning предложение: все 19 полей semantic, exclusions пусты; SEQUENCE с сохранением порядка, duplicate identity reject. Это предъявленный проект, не автоматически принятая пользователем политика | §5b |
| Dependencies | Namespace/nullable и известные inbound usages описаны; итоговый latest-граф и pinned-графы различаются; fact сохраняется точной строкой; RegionState history не считается proof/pin | Semantic evidence, основной план |
| Bootstrap source | Только явно подготовленные authored-записи нового строгого контракта; defaults/landcover отдельно | Принятое решение пользователя |
| Caller inventory | Прямые constructors, projections, normalizer, repair, import, fixture и generic schema paths выявлены. Динамические/все исторические writers не объявлены полностью проверенными | §3, §5a–5b, Source audit |

**Следующие работы распределены явно:** шаг 2 — Source revision storage/owning writer/bootstrap mechanics; шаг 3 — целевые междоменные contracts, errors, consistency и DAG; шаг 4 — полная обязательная приёмка и точный перечень файлов реализации. Полнота caller cutover, real canonical vectors и projection regression требуют проверки на конкретном implementation-срезе до его принятия/поставки; здесь tests не выполнялись. Cell-state разработка вне плана. Данные истории не удаляются/не адаптируются.

Этим результатом можно пользоваться для проектирования Source storage, не считая междоменные API существующими. Укреплять shared POJO в коде до общей приёмки нельзя. Полный домен и REC-1 остаются непринятыми; подмена этой приёмки завершением анализа запрещена.
