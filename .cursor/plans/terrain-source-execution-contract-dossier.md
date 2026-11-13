# Terrain registry: owning execution contract для Source

2026-11-14. **PROPOSED / NOT ACCEPTED / NOT runtime-ready.** Ограниченная контрактная проработка по Source P2.13 и REC-1. Ни SourceDurableProof/R1/R2, ни Pack, ни DAG не меняются. Документ не закрывает REC-1 самостоятельно. Все ниже предложенные модули и методы отсутствуют до отдельной принятой реализации; это не утверждение наличия API.

## Согласованное решение пользователя

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

Последний тип в таблице читается как nullable literal. Existing invariant: supports_open_land_grade iff profile is not None. Не добавлять без отдельного решения новые связи has_state/default_state или диапазоны travel_modifier/merge_rank. Запрет nonfinite travel_modifier — рекомендуемое усиление canonical boundary, совместимость существующих rows OPEN.

### Authored-presence и nested values

**Исправление feasibility после Source review:** `CanonicalCodec._encode` читает ровно `type(value).model_fields`, проверяет значения через strict model_validate и кодирует каждое поле. `RegisteredTypeEntry` не предоставляет field adapters. Предыдущее предложение невидимой canonical metadata отозвано. Generic codec не расширяется.

Рекомендуемый конкретный вариант: добавить **19-е обычное поле** `hills_authored: StrictBool` в существующий TerrainRegistryEntry после open_land_profile. Поле frozen вместе с моделью, без exclude=True, private attribute или computed_field; default на объявлении отсутствует. Existing has_authored_hills возвращает hills_authored, а не model_fields_set. Это owning semantic fact существующей записи, не зеркальный DTO. Canonical manifest регистрирует эту же модель; codec видит 19 полей штатно. До реализации обязательны project acceptance изменения модели и проверка отсутствия прежней persisted canonical регистрации этого класса; обнаруженный старый format нельзя переопределить.

Правила construction/validation:

* Валидируемый legacy input без hills_authored: owning before-validator копирует mapping и устанавливает presence по наличию ключа hills **до defaults**. Так сохраняются существующие constructors и JSON: absent → None/false, explicit null → None/true, policy → policy/true. Нельзя мутировать caller mapping или брать bool(hills).
* Input с явным hills_authored: strict bool обязателен, его значение авторитетно; false допускает только hills=None, true требует явно присутствующего ключа hills (None либо policy). Canonical decode передаёт все поля, включая явный false, и не выводит presence заново из присутствия hills. Existing instance повторно валидируется по полным значениям; его fields_set больше не semantic authority.
* Legacy JSON serialization существующего entry: owning wrap serializer удаляет hills_authored из внешней legacy формы; при false удаляет также hills, при true сохраняет hills **даже None**, включая используемые export flags. Full internal canonical encode сериализатор не вызывает: читает поля непосредственно. Поэтому generic model_dump для legacy interchange и canonical field roster сознательно различаются; любые callers, ожидающие полный internal dump, инвентаризируются. Режимы exclude_none/exclude_unset/include/exclude и alias поведение требуют явных compatibility tests; нельзя считать стандартные флаги доказательством корректности.
* with_hills(value) валидированно заменяет одновременно hills=value и hills_authored=True; with_eligibility сохраняет оба поля hills неизменными. Direct replace/model_copy(update={hills: ...}) не считается допустимой mutation boundary без одновременного обновления presence и повторной validation. Отдельный метод «снять authored override» этим срезом не вводится.
* model_construct обходит validators: разрешён только trusted construction с **обоими явными полями**, followed by boundary revalidation. Выводить presence из _fields_set запрещено. Missing hills_authored, invalid false+policy и counterfeit instances должны отвергаться до encode/consumer use. CanonicalCodec уже отвергает неполный vars roster; это не заменяет проверки перед обычным consumer. Canonical decode не обязан восстанавливать fields_set: semantic authority теперь явное поле.

Для остальных полей semantic presence не доказана: defaults материализуются; audit fields_set/exclude_unset остаётся OPEN. Serializer и before-validator выше — proposal алгоритма изменения owning POJO, не второй canonical codec и не реализация. Полная совместимость generic wire ingestion/serialization остаётся acceptance gate.

`EligibilityRule` (existing eligibilityRule.py): fact nonempty str; op EligibilityOp; lo/hi finite float nullable; weight finite >= 0 default 1; required bool default False. GTE/IN_RANGE требуют lo, LTE/IN_RANGE требуют hi, при обоих lo <= hi. Сохранять также неиспользуемую данным op границу; не «упрощать» её. Рекомендуемый canonical boundary strict, forbid extra, revalidate instances; bool не int/float. Existing validators переиспользуются, coercion policy требует compatibility review. Порядок, повторы и нулевые weights сохраняются. Catalog допустимых fact names/ref rules OPEN.

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

`SurfaceSupportCapture.capture` продолжает читать has_authored_hills без смены semantics. В `capture_landcover_policy` construction entry должен передавать `hills_authored=e.hills_authored`, поскольку явное hills=e.hills иначе ошибочно сделает absent authored. Находящийся рядом model_construct относится к **LandcoverTerrainPolicy**, не TerrainRegistryEntry: его _fields_set восстановление сохраняется, модель policy этим решением не мигрируется. `LandcoverTerrainPolicy.apply_to` использует strengthened with_hills и сохраняет прежнюю precedence; registry_hills_authored остаётся отдельным параметром consumer projection.

`TerrainRegistryEntry.authored_hills_key_from_wire` и `WorldTerrainRegistry.authored_hill_keys_from_wire` продолжают анализировать именно legacy wire, где explicit marker не публикуется; `application/jsonValidation/terrainHillRegistry.py` должен получать эту форму, а не canonical decoded field dict. Canonical body входит через owning typed binding, не через legacy helper. Existing literals canonical_plains/forest с hills получают true через validator, literals без hills — false. Generic World round-trip не должен добавлять absent hills=None. Перед внедрением нужны поиск и trace всех entry model_construct/model_copy/replace, generic serializers/JSON schema consumers и проверка, что новый internal marker не объявился внешним редактируемым полем через автоматически публикуемую schema. Точный schema/export compatibility mechanism OPEN до project acceptance; отсутствие найденных прямых callers не закрывает generic paths.

Acceptance новой формы дополнительно требует: canonical decode с hills=None/false сохраняет false несмотря на полный fields_set; legacy export→import сохраняет все три состояния; with_hills(None) даёт true; with_eligibility не меняет presence; unsupported raw construct отвергается; capture→landcover сохраняет false; override policy model_construct не сломан; declared 19-field manifest round-trip и golden bytes проходят без изменений generic codec. SEQUENCE и включение всех полей в semantic projection остаются **recommendations**, не accepted policy. Source tombstone разрабатывается Source отдельно.

## 4. Codec, adapters и execution registration

Предлагаемый terrain owner: `backend/app/application/worldData/generators/terrain/source/terrainSourceAdapter.py::TerrainSourceAdapter`, **internal registered format/value binding**, не публичный междоменный helper, CRUD service или OpenPipeline. Предыдущее обозначение «публичный owning value adapter» отозвано. Предлагаемые internal методы (после strengthening existing types):

* `encode_body(body: TerrainRegistryEntry) -> bytes`;
* `decode_body(payload: bytes) -> TerrainRegistryEntry`;
* `semantic_bytes(body: TerrainRegistryEntry) -> bytes`;
* `key(body: TerrainRegistryEntry) -> RegistryKey[WorldTerrainRegistry]`.

Все pure, без DB, latest, settings, stage, leases, commit и calls к public Source. Typed rejection нужен в proposed `backend/app/dataModel/terrain/source/terrainSourceError.py::TerrainSourceError` (operation, field path, code: INVALID_BODY/INVALID_PRESENCE/UNSUPPORTED_FORMAT/KEY_MISMATCH). Точная error base/field-path POJO и mapping в existing SourceFailure **OPEN**; не выдавать нынешний ValueError за принятый public error contract. bytes — canonical transport, не свободный dict/Any body. Adapter не заявляется полным public CRUD API; его boundary и signatures требуют owner review.

Composition root связывает terrain-owned instance с exact Source execution registration и Artifacts format registration при создании приложения; Source получает проверенный immutable internal binding, а не импортирует/вызывает public Terrain API и не выбирает request-supplied callback. Nested trace: Source internal execution registry → bound pure encode/decode/projection/key implementation → existing CanonicalCodec → existing POJO validators; возврат значения без IO/lifecycle. Concrete composition module/interface registration остаётся OPEN у Source/Artifacts. Этот вариант не легализует Source→Terrain public helper или чтение terrain stores. Если для операции требуется terrain CRUD, нужен отдельный согласованный публичный контракт и DAG route, этот binding его не заменяет.

Предлагаемый `.../terrain/source/encoding/terrainSourceSchemaV1.py::TERRAIN_SOURCE_SCHEMA_V1` — terrain-owned manifest для existing entry с 19 обычными полями и nested types; fixed IDs/enum registrations и collision checks **OPEN**, не назначены произвольно. Field adapters отсутствуют и не требуются рекомендуемому варианту. Использовать existing `backend/app/encoding/canonicalCodec.py` и application binding `backend/app/application/encoding/canonicalCodec.py`, existing content_digest, без второго JSON codec/hash. Proposed format `terrain.source-entry`, format_version=1: terrain владеет semantic format, Artifacts владеет регистрацией/verified storage; exact ArtifactKind и registration module требуется согласовать, **OPEN**. Эти пути — предлагаемые, не существующие реализации.

Semantic bytes включают весь roster и hills presence под отдельным semantic domain/manifest binding; Artifact content hash и Source semantic hash не приравниваются. Source key adapter обязан проверить exact owning key round-trip, world/descriptor и соответствие system_terrain object identity. Никакой latest lookup для decode historical body.

Source execution registration key = `(registered terrain member descriptor, execution_version=1)`; numeric descriptor ID остаётся Source-owned. Immutable registration связывает codec/format, manifest, projection без exclusions, key adapter, SEQUENCE membership, hills presence/catalog, ref rules и Source tombstone semantics. Version не build number. Любая перемена влияющих правил — новая версия; format_version не заменяет execution_version. При отсутствии exact old executor незавершённая recovery не запускается, не переходит на latest, сохраняет request/holds; typed infrastructure error согласуется с publication. Terminal replay возвращает сохранённый outcome по immutable fingerprint без повторного projector.

## 5. Зависимости, replay и bootstrap

Рекомендуемый projector не читает ambient world/settings/fixtures/catalog latest: только полное body и frozen registration. Empty hills catalog закреплён выше; default material/category/glossary не разыменовываются при hashing body. Их содержимое при потреблении — отдельные explicit dependencies, не скрытое расширение body. Изменяемые landcover overrides, климат, world uid/seed, grid, material registry и relief policies относятся к consumer input/capture; запрет ambient projector не означает отсутствие этих runtime dependencies.

Ref-integrity checks в общей transaction читают текущее согласованное состояние: category, default_material, glossary_ref, default_state, danger_level и eligibility fact namespaces требуют точного owning ref roster/nullable policy. Сейчас это **OPEN**, нельзя объявлять строки нессылочными по отсутствию typed key. Нужно определить create/update/delete проверки, inbound usage, missing/foreign refs и scope. Они могут дать новый конфликт при recovery; original expected refs и candidate bodies не заменяются. Не замораживать всю БД для воспроизведения прежнего in-memory outcome.

Delete: по Source P2.17 tombstone — новая revision с index deleted flag без live body mapping, не новая сущность/public DTO, не TerrainRegistryEntry с null полями и не отсутствующий artifact. Terrain определяет допустимость удаления/inbound usage; Source владеет tombstone encoding/hash и seq. Source-owned candidate `application/worldData/sourceVersioning/encoding/tombstoneEncodingV1.py`: existing CanonicalCodec над `("source.registry-member.tombstone", 1, registry_member_id)`, затем existing content_digest(bytes).hex(); RegistryMemberId использует принятый SOURCE_PROOF_SCHEMA_V1 binding, нового type ID нет. Seq, operation/attempt, время, execution_version и прежние bytes в hash не входят. Execution registration ссылается на этот encoder; terrain не создаёт собственного tombstone codec. Это кандидат до vectors/joint acceptance, не принятый DELETE runtime. Исторические body/holds не удаляются по удалению latest member. Pruned live revision — отдельный факт недоступности, не tombstone и не новая semantic revision; исчезнувшие retained bytes также не превращаются в tombstone/prune. Rename key — не скрытая body update: identity change должен быть согласованным remove/add membership batch.

**Статическая feasibility presence, Source P2.16:** повторно проверен `backend/app/encoding/canonicalCodec.py::_decode_one`: exact field names/order сравниваются с model_fields до model_validate. Поэтому canonical payload без 19-го hills_authored отвергается, а legacy before-validator не может угадать отсутствующее canonical поле. Конкретное ограничение generic codec для предложенного обычного поля закрыто статически без расширения codec. Это не закрывает caller/schema/serializer compatibility, golden vectors или весь REC-1.

Initial bootstrap: до v1 activation инвентаризировать persisted registries, unknown fields, duplicates, nonfinite/coerced values и hills presence. Нельзя восстанавливать потерянную presence догадкой или текущим canonical_engine defaults. Legacy normalization/repair и first revisions — отдельный принятый Source batch с coherent membership, full bodies, ref checks и retention root; defaults/catalog version фиксируются до fingerprint. Если исходная presence уже потеряна, bootstrap policy/authoritative source OPEN. Restart не выполняет bootstrap повторно поверх имеющейся истории. Порядок inventory → projector → revisions → capture сохраняется.

## 5a. Конечное owning предложение после дополнительного trace

Это завершение ограниченной проработки, не снятие gates. Пользователь согласовал **выбор hills_authored**, но не общий контракт. Следующие сведения уточняют предыдущие OPEN, не разрешают runtime migration.

### Compatibility schema/export/import

Обнаружена существующая регистрация: `backend/app/dataModel/terrain/encoding/surfaceBindings.py::BINDINGS`: WorldTerrainRegistry=16, TerrainRegistryEntry=17, EligibilityRule=18, EligibilityOp=19, HillPolicy=20, HillShape=21, TerrainFillRole=22; `dataModel/hydrology/encoding/surfaceBindings.py` регистрирует HydrologyCellRole=23. Поэтому гипотеза «entry ещё не зарегистрирован» неверна. Наличие регистраций не доказывает persisted use: нынешняя mutable eligibility не кодируется CanonicalCodec, но исключать старые успешные/альтернативные consumers без проверки нельзя. Изменение model_fields меняет canonical layout ID 17, tuple/frozen root меняет допустимость ID 16. **До кода нужен audit всех manifests/formats/cache keys, включающих эти bindings, и persisted compatibility decision владельцев.** Новый Source format сам по себе не решает совместимость прежнего surface format; назначение нового ID тому же Python owner также конфликтует с merge_manifests. Generic codec не меняется, mirror не вводится.

| Generic caller / boundary | Нужное сохранение поведения |
|---|---|
| jsonValidation/resolve.py::resolve_model и _resolve_defaultable_wire | Валидируют whole raw object, используют model_validate/model_validate_json и context validate_only. Legacy lists должны приниматься и копироваться в tuples owning before-boundary, canonical tuples — проверяться строго. Нельзя глобальным strict=True без адаптации сломать JSON arrays и constructors |
| jsonValidation/worldSlices.py::canonical_registry_wire, resolve_registry_list_world, _apply_runtime_canonical_merge | Defaults dump в JSON, overlay по key и list(by_id.values()); сохранить порядок и list wire, получить tuple внутри POJO. Не добавлять hills=None отсутствующим override. [] означает подключение канона, не пустую Source membership |
| jsonValidation/worldRow.py::terrain → apply_landcover_policies | Это resolved read с defaults/policy, не чтение authored durable entry. Не подменять им Source bootstrap input |
| jsonValidation/facade.py::normalize_world, строки 85–94 | После merge/ref checks повторно применяет landcover policies, затем model_dump(json). Нужен тест raw→normalize→persist→read на три presence состояния; policy-derived value не должен незаметно стать исходным authored значением |
| jsonValidation/terrainHillRegistry.py | raw authored keys проверяются отдельно от resolved entries; не передавать canonical field dict в legacy helper |
| application/templateLibrary/reliefTerrainSync.py::missing_terrain_entries | По Source audit намеренно читает stored rows: resolved read скрывает отсутствующие canonical keys. Сохранить различие stored/resolved при bootstrap |
| application/templateLibrary/packs/domainAdapters/relief.py, участок добавления canonical entries | По Source audit дописывает в raw registry canonical entries; это writer/inventory boundary, не просто read. Presence должна соответствовать исходному literal, новый revision не назначается этим dossier |
| generic schema consumers: engine/prompt/llmGroupPayloadBuilder.py, engine/runtime/prompt/pojo/llmPayload.py, engine/runtime/graphs/graphCompiler.py | Используют model_json_schema; условное включение TerrainRegistryEntry требует dependency trace. Legacy schema не должна требовать internal marker или предлагать его как пользовательский override |

Рекомендуемый schema/wire контракт: legacy shape остаётся массивом entry, без hills_authored; validation schema скрывает marker и не включает его в required, serialization schema описывает optional hills. Owning JSON schema hook должен отражать это, canonical codec JSON schema не использует. Legacy ingestion отвергает явный marker на внешней boundary, а internal canonical decode принимает полный roster. Конкретный механизм разграничения внешнего input и canonical validation context **не принят**: общий model_validate без контекста не может сам определить происхождение dict. Нельзя утверждать, что один before-validator уже решает external injection. Необходим review generic import callers до выбора контекста/explicit wire validation; запрет прятать это в Source decoder.

Для tuple/strict: нормализация legacy arrays→tuple должна происходить перед внутренней immutable validation с копированием; bool-as-int, строки вместо чисел и неизвестные поля не должны молча исправляться canonical boundary. Legacy DefaultWhenMissing/StrictOnWire и import continuation policy нельзя заменить массовым extra=forbid/strict=True без separate compatibility decision. CanonicalCodec проверяет exact roster, но не делает все существующие nested annotations строгими автоматически. Требуется принять по каждому existing nested POJO strengthening либо owning pre-encode validation без изменения его legacy semantics. Этот dossier не объявляет всех generic callers перечисленными: полноту устанавливает отдельный Source audit, включая world export/import/copy и schemas.

### Ref-integrity roster: evidence и recommendation

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

`index/validate.py::_check_ref` пропускает None/empty string и unavailable registry, применяется к normalized import, не выполняет Source transactional referential integrity. Эти skips нельзя переносить в execution v1 автоматически. Рекомендовано проверять live targets в coherent post-batch view общей transaction, допускающей согласованные dependency changes; historical held versions сохранять независимо от live delete. Нужны конкретные owner-provided scoped contracts и полный inbound inventory: без них reject/restrict выше остаются proposal, не executable contract. Автоматического cascade delete или remap не предлагается.

### Manifest/format/membership: итоговое предложение

`terrain.source-entry` v1 кодирует existing TerrainRegistryEntry с 19 полями в объявленном порядке. Минимальный manifest closure: ID 17 entry RECORD, 18 EligibilityRule RECORD (fact, op, lo, hi, weight, required), 19 EligibilityOp ENUM, 20 HillPolicy RECORD (min_spacing, radius, height, shapes), 21 HillShape ENUM, 22 TerrainFillRole ENUM, 23 HydrologyCellRole ENUM. Это **reuse existing bindings**, не новые IDs. RegistryKey кодируется как существующий str subtype, bool/float/int/nullable/tuple — built-in codec, отдельные type IDs не нужны. WorldTerrainRegistry ID 16 не нужен entry-body manifest: collection уже Source-owned и содержит ordered identities, не вторую копию terrain entries. Его immutable strengthening всё равно затрагивает existing surface consumers.

Manifest owner и format path остаются §4; минимальный closure надо сверить merge_manifests и golden vectors с действующими surface registrations. Включение изменённого ID 17 разрешается только после compatibility gate выше, не путём тихого переопределения. ArtifactKind/format registry port — Artifacts acceptance, не terrain self-registration. Source descriptor/key/proof и tombstone binding остаются Source-owned.

Окончательная **рекомендация** membership — SEQUENCE, сохраняющая порядок prepared authored/resolved registry, который выберет принятый bootstrap contract; duplicate keys reject. Не считать canonical overlay [] пустой коллекцией. Source не сортирует rows по образцу SurfaceSupportCapture. Все 19 полей semantic, exclusions пусты; это консервативная recommendation, не согласованная пользователем policy. Необходимы явное совместное принятие этого выбора и отдельный выбор authoritative authored vs normalized bootstrap body.

### Конкретные неразрешимые по текущему trace вопросы

1. Какие persisted/cache форматы реально используют ID 16/17, и какой совместимый cutover разрешён их владельцами? Код регистрации сам не доказывает отсутствие старых bytes.
2. Какой внешний import/schema context гарантирован всеми generic callers для запрета marker injection при разрешённом internal canonical decode? Простой serializer этого не решает.
3. Bootstrap фиксирует stored authored registry или normalised effective registry после canonical overlay и landcover policy? Текущие callers предоставляют оба представления; выбрать за пользователя семантику истории нельзя.
4. Lore/danger/state/fact owners: точные identity namespace, null/empty/missing правила и scoped live read/delete guards; полный inbound usage inventory. ТЗ даёт назначение, но не атомарные Source contracts.
5. Совместное принятие SEQUENCE/all-fields-semantic, strict legacy compatibility и Artifacts format registration. Presence уже согласована пользователем и повторного решения о необходимости hills_authored не требует.

## 6. Приёмка и проверки

Нужны golden vectors всех 18 полей и nested enums, absent/null/policy, empty/nonempty/reordered/duplicate shapes и rules; decode→encode byte equality и exact authored round-trip; mutation исходных lists после подготовки не меняет body/hash. Проверить bool/string coercion, NaN/inf, missing bounds, malformed enum, extra fields, inconsistent open-land profile/presence, duplicate identity. Проверить порядок collection, key mismatch, non-ASCII keys, glossary-only изменение (semantic до доказанного exclusion), unchanged body equality, A→B→A Source seq, old execution unavailable, catalog changed with unchanged bytes, current ref conflict после restart, tombstone/live distinction и bootstrap повтор. Реальных vectors/runtime tests этим документом не выполнено.

| Обязательный критерий проекта | Статус |
|---|---|
| Нет pipeline с ветвлением между самостоятельными операциями | Proposed adapter pure; production nested trace OPEN |
| Нет скрытой orchestration; DAG напрямую вызывает public operations | Новый DAG/NodeId не назначается; public CRUD caller binding OPEN |
| Нет прямых междоменных public вызовов | Предложен value binding, не Source→terrain CRUD; окончательный Source composition trace OPEN |
| Роль/effects/deps/refusal каждого класса | Existing POJO validation, codec serialization, adapter pure projection определены выше; Source apply/Artifacts lifecycle вне этого owner, exact registration/errors OPEN |
| Public contract / implementation boundary | Adapter signatures предложены; canonical implementation/manifest registration и full CRUD не приняты |
| Неизменность утверждённого порядка | inventory→projector→revisions→capture; без новых нод, migration и cutover |
| CRUD данных отдельно C/R/U/D | Codec read не заменяет CRUD read; owning CRUD classes/Input/Output/Error/scope/effects и DAG paths OPEN |
| CRUD настроек отдельно C/R/U/D | Запрет ambient projector не освобождает terrain settings от полного CRUD; именованный settings POJO/API inventory OPEN |
| Междоменный CRUD/dependency protocol | Terrain body recommendation передаётся Source; ref owners/Artifacts format/Source tombstone требуют review, прямое чтение чужих внутренних stores не разрешено |
| Typed POJO/errors, отсутствие дубликатов | Reuse выбран; strict/deep immutable strengthening и errors нуждаются в принятии, mirror не вводится |

**Вердикт:** конкретная recommended representation и semantic policy предъявлены, но приёмка реализации/полного домена отклонена до закрытия OPEN. REC-1 не закрывается scalar version или этим dossier без совместной проверки manifest, callbacks/settings absence, ref integrity, tombstone и bootstrap. Код/ТЗ/чужие планы не изменены.
