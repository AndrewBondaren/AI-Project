# Terrain dependency для Source G1-BIND — owning предложение

2026-11-15. **PROPOSED, NOT ACCEPTED.** Источник — ответ owning чата `01a1d6e7-7dc4-71c0-a570-5abda0bffe62`, turn `01a1dc0d-cfbe-77e3-af90-00b1907af532`. Source фиксирует предложение, не принимает его вместо владельца/пользователя. Код Terrain, Artifacts и Source этим документом не разрешается. Связанные документы: terrain-source-execution-contract-dossier.md; source-proof-v2-contract-spec.md §10.1; source-g1-pure-api-sheet.md §3.1.

## 1. Exact key

2026-11-15: пользователь ответил «Ок» на рекомендацию принять exact-key контракт отдельно от остального пакета. Согласованы signatures и правила этого раздела; реализация и её приёмка ещё не выполнены. Для semantic representation принято направление: явная версия и existing canonical codec без ambient reads, но не весь набор предложенных body semantics.

Предлагаемый owning модуль `app.application.worldData.generators.terrain.source.terrainKeyValidator`:

```python
class TerrainKeyValidator:
    def validate_exact(self, token: str) -> TerrainKey: ...
    def encode_exact(self, key: TerrainKey) -> str: ...
```

TerrainKey — existing RegistryKey[WorldTerrainRegistry]. Отказ — existing pydantic.ValidationError. Повторно проверяется базовое строковое содержимое, strict/min_length=1, без доверия instance-ветви RegistryKey. String carriers допустимы, bytes/числа/coercion — нет. Никаких strip/casefold/Unicode normalization/нового regex. encode_exact повторяет проверку; exact token equality обязательна. Проверка наличия member в registry сюда не входит. Source owning adapter переводит отрицательный validation outcome в INVALID_IDENTITY с исходными operation/path, не анализируя message. Terrain не принимает SourceObjectId и не создаёт SourceFailure.

Для SCH-WORLD-TERRAIN/membership key_kind=NONE; key adapter не регистрируется. Ключи членов проверяются через /member.

## 2. Исходный вариант body encoding и semantic projection

История предложения: all19/вложенный body/ID17 ниже не являются текущим принятым решением. Уточнения и альтернативы владельца — §5; актуальный остаток проверки — §6. SEQUENCE отозван, exact-key отдельно согласован в §1.

Предлагаемые модули под `app.application.worldData.generators.terrain.source.encoding`:

```python
# terrainBodyCodecV1.py
class TerrainBodyCodecV1:
    def encode(self, body: TerrainRegistryEntry) -> bytes: ...
    def decode(self, payload: bytes, version: FormatVersion) -> TerrainRegistryEntry: ...

# terrainSemanticProjectorV1.py
class TerrainSemanticProjectorV1:
    def project(self, body: TerrainRegistryEntry) -> bytes: ...
```

Конструкторы без caller manifest/callback/settings; отказы — existing CanonicalEncodingError с validation cause. Используется целевая строгая форма existing TerrainRegistryEntry с 19 обязательными полями и immutable nested values, явным hills_authored. Encode проверяет exact class/roster/nested values/key; decode — bytes, version=1, полный roster, exact re-encode equality. Нет defaults repair/legacy conversion/model_construct trust. TLV — только existing CanonicalCodec.

Предложение semantic bytes: canonical tuple `("terrain.source-entry.semantic", 1, body)`. Все 19 полей semantic, exclusions отсутствуют; rules/shapes/fill_roles сохраняют порядок. Projector не разыменовывает refs, не читает latest/defaults/catalog и не вызывает resolved_shapes; empty shapes сохраняется. Source считает existing digest semantic bytes; artifact hash считается от body bytes, это разные представления.

Предложен `terrainSourceSchemaV1.TERRAIN_SOURCE_SCHEMA_V1` с existing IDs 17 TerrainRegistryEntry, 18–19 EligibilityRule/EligibilityOp, 20–21 HillPolicy/HillShape, 22–23 TerrainFillRole/HydrologyCellRole. Registry ID16 не включается. **Reuse ID17 пока не принят:** изменение layout existing record требует доказанной совместимости поддерживаемых enclosing schemas/исторических bytes. Отсутствие legacy adaptation не является разрешением молча изменить старую wire-схему. Решение не выводится Source из списка IDs.

## 3. Artifact format boundary

Owning ответ указывает: existing BLOB ArtifactFormatContract требует content_model=bytes, поэтому ArtifactFormatContract[TerrainRegistryEntry] не подходит. Предложен `terrainSourceFormatV1.TERRAIN_SOURCE_ENTRY_FORMAT`: ArtifactFormatContract[bytes], key terrain.source-entry, kind BLOB, supported_versions frozenset({1}), content_model bytes, row_count None. Format encode/decode проверяют bytes через TerrainBodyCodecV1.decode и возвращают exact bytes.

Это предложение format/value binding. Реальная регистрация ArtifactFormatRegistryBinding требует подтверждения Artifacts и подходящего existing backend; константа сама по себе gate не закрывает. Новый backend/lifecycle/SQL здесь не проектируется. Source не принимает чужой format contract самостоятельно.

## 4. Решения и evidence до приёмки

Уже согласованы hills_authored, запрет legacy adaptation и bootstrap из явно подготовленных authored-записей нового strict контракта. Повторного выбора не требуется.

| Остаток | Владелец | Требуемый результат |
|---|---|---|
| Exact key API §1 | Terrain, Source для boundary mapping | Design согласован отдельно; реализация и negative/round-trip проверки ещё не выполнены |
| Strict full19/nested body | Terrain | Полный exact roster/validation/callers compatibility, три hills presence состояния, no repair |
| All19 semantic/tuple/tag/version | Terrain; принятие пользователем | Зафиксировать semantic policy и literal vectors; показать изменение bytes для каждого влияющего поля/presence |
| SET membership / duplicate refusal — новое предложение §5 | Terrain semantics, Source collection contract | Принять после evidence; прежняя рекомендация SEQUENCE отозвана владельцем |
| Reuse manifest IDs/layout | Terrain, владельцы enclosing encodings | Проверить совместимость ID17 и остальных записей; не переназначать старый layout автоматически |
| BLOB bytes format registration | Artifacts совместно с Terrain | Подтвердить exact existing binding/backend, unsupported-version/collision/vector checks |
| Concrete Source composition | Source после owning подтверждений | Связать принятые contracts без permissive adapters и fake registration |

До этих подтверждений G1-BIND OPEN. G1.1/G1.2 PASS сохраняется. Writer/storage/recovery/DAG, миграция реестров и код Pack вне этого согласования. Следующий шаг — разрешить перечисленные design/compatibility пункты с владельцами; принятие только общего названия adapter не является приёмкой concrete composition.

После согласия пользователя отправлены два адресных уточнения: Terrain — consumer evidence всех 19 semantic fields, доказательство SET/SEQUENCE и совместимости ID17; Snapshot — проверка existing Artifacts BLOB contract/binding либо указание актуального владельца, если это вне его ответственности. Ответ Terrain записан в §5. В проверенных последних десяти turns Snapshot подтверждение BLOB binding не найдено; его последний результат по publication diagnostics не отвечает на этот запрос и не закрывает Artifacts gate. SET рекомендован только при доказанной независимости порядка, SEQUENCE не принят по одному list root. All19/reuse ID17/Artifacts registration остаются OPEN. Код и чужие планы не изменялись.

## 5. Уточнение Terrain по consumer trace — 2026-11-15

Owning ответ получен; он уточняет и частично заменяет рекомендации §2/4, но не является общей приёмкой. Прежняя рекомендация SEQUENCE отозвана. Blanket утверждение, что все 19 полей доказанно влияют на исполнение, также отозвано. Exact-key остаётся отдельно согласованным.

| Поле | Evidence / предлагаемый статус |
|---|---|
| system_terrain | Identity: entry_for/coverageResolver/refs; смена identity, не update прежнего объекта |
| glossary_ref | Пока semantic: ТЗ связывает display_terrain с lore; исключение требует принятой границы display/audit |
| terrain_category | Semantic: keys_for_category, SurfaceSupportCapture |
| travel_modifier | Semantic по ТЗ travel/None непроходимость; runtime entry trace не доказан |
| danger_level | Semantic по ТЗ effective danger/priority; отдельная разработка registry не разрешается |
| has_state, default_state | Semantic по ТЗ creation/fallback state; cell-state разработка остаётся вне scope |
| default_material | Semantic: support MaterialKey conversion, material fallback по ТЗ |
| gap_width | Semantic по ТЗ cell override fallback |
| merge_rank | Semantic: terrainMerge/capturedSources candidate order |
| eligibility | Semantic: coverageResolver bounds/required/weighted score |
| inertia | Semantic: regions/stateChange/progress.advance |
| hills | Semantic: preWaterHillHosts/HillPolicy/landcover projection |
| fill_roles, fill_priority | Semantic: column_terrain_key filter и min(-priority,key) |
| morph_hydrology_role | Кандидат исключения, НЕ исключён: найдены declaration/LAKE-or-None validator, вычислительный consumer не найден |
| supports_open_land_grade | Semantic: openLandTerrains/relief terrainMap |
| open_land_profile | Semantic: terrainMap→ReliefConditionTerrain |
| hills_authored | Semantic, ранее согласовано: LandcoverTerrainPolicy.apply_to различает absent/null |

Предложен SET с unique identities: проверенные entry_for, column_terrain_key и coverageResolver order-independent; category/open-land/validation используют множества, SurfaceSupportCapture/preWaterHillHosts явно сортируют keys. Найденный root[0] относится к BUILTIN canonical_defaults, не authored registry. Полнота всех динамических consumers не заявлена. Приёмочные проверки: перестановки unique entries сохраняют результаты этих consumers и canonical membership bytes. Порядок nested rules/shapes/fill_roles этим не меняется. SET ещё требует принятия, не автоматически установлен Source.

ID17 используется через terrain surfaceBindings → SURFACE_MANIFEST → planProviders.declared_binding → SurfaceEnvelopeCodec и planning fingerprints. Old18/new19 decoding несовместим до validators. Но binding не доказывает существование валидных старых full-body bytes: текущий eligibility=list не поддерживается encoder, persisted full-entry writer в проверенном маршруте не найден. Отсутствие найденного writer не является разрешением молча менять layout.

Новая owning альтернатива reuse17: existing CanonicalCodec кодирует `("terrain.source-entry.body", 1, (19 значений в фиксированном порядке))`; owning decoder проверяет tag/version/arity/slot types, создаёт строгий existing entry и проверяет exact re-encode. Top-level ID17 не используется; nested18–23 переиспользуются только при неизменных layouts. Semantic projection также кодирует выбранные slots под отдельным fixed tag/version, а не body model с ID17. Это предложение нового versioned layout, не новый DTO/TLV engine и не адаптация старых bytes. Оно заменяет рекомендацию вложить body model в semantic tuple, если пользователь выберет этот вариант. Изменение shared POJO в SURFACE_MANIFEST всё равно требует отдельной compatibility проверки.

Остаток решений: SET; политика glossary/morph (консервативное включение либо обоснованное исключение); выбор tuple-based layout без17 либо доказанное reuse; фиксированные body/semantic vectors и format registration. До этого Source composition и G1-BIND не принимаются.

## 6. Проверка решений и схем — 2026-11-15

Результат: CHANGES REQUIRED для приёмки G1-BIND. Это проверка документов и существующего кода, не независимая приёмка реализации. Пользователь разрешил свести документы и предъявить точную схему/composition; это не принятие SET, all19 или нового layout. Source API sheet и G1-план синхронизированы; Terrain dossier остаётся owning документом и требует обновления владельцем: прежние SEQUENCE/all19/ID17 рекомендации нельзя использовать как актуальное согласование.

### 6.1. Таблица для проверки tuple-варианта владельцем

Ниже явная раскладка по предложенному Terrain constructor roster (dossier §5b). Это кандидат для подтверждения Terrain, не самостоятельно введённая Source wire-схема. Индексы с нуля, внешний tuple — `(body_tag, body_version, slots)`. Предложенные tag/version — `"terrain.source-entry.body"` / integer `1`; slots — exact tuple длины 19. Semantic slots и их tag/version фиксируются отдельно после выбора semantic policy, не выводятся из этого body roster автоматически.

| Индекс | Поле | Целевой Python тип |
|---|---|---|
| 0 | system_terrain | TerrainKey |
| 1 | glossary_ref | str или None |
| 2 | terrain_category | str |
| 3 | travel_modifier | float или None |
| 4 | danger_level | str |
| 5 | has_state | bool |
| 6 | default_state | str или None |
| 7 | default_material | str или None |
| 8 | gap_width | int или None |
| 9 | merge_rank | int |
| 10 | eligibility | tuple[EligibilityRule, ...] |
| 11 | inertia | float |
| 12 | hills | HillPolicy или None |
| 13 | fill_roles | tuple[TerrainFillRole, ...] |
| 14 | fill_priority | int |
| 15 | morph_hydrology_role | HydrologyCellRole или None |
| 16 | supports_open_land_grade | bool |
| 17 | open_land_profile | Literal["plains", "forest"] или None |
| 18 | hills_authored | bool |

Nested manifest-кандидат: ID18 EligibilityRule RECORD `(fact, op, lo, hi, weight, required)`; ID19 EligibilityOp ENUM; ID20 HillPolicy RECORD `(min_spacing, radius, height, shapes)`; ID21 HillShape ENUM; ID22 TerrainFillRole ENUM; ID23 HydrologyCellRole ENUM. IDs16/17 не входят в этот вариант. Владельцу подтвердить точные enum tokens, неизменность nested layouts и совместимость strengthening validation. Existing CanonicalCodec остаётся единственным TLV engine.

До принятия нужны literal body/semantic vectors; exact tag/version/arity/slot checks; отказ bool вместо integer version и неверных числовых типов; finite floats; bounds/open-land/presence инварианты; missing/extra/reordered slots; malformed nested values; exact encode-decode-reencode; неизвестная версия; non-ASCII key round-trip. Required nullable поля не восстанавливаются из defaults. Generic codec проверяет имена полей RECORD, но не знает имён внешних tuple slots: их соответствие проверяет owning Terrain codec. Смена shared TerrainRegistryEntry по-прежнему требует отдельной surface compatibility проверки даже без ID17 в новом body manifest.

### 6.2. Подтверждённая Artifacts граница и остаток composition

Чтением `backend/app/application/artifacts/contracts/formatBackend.py` подтверждено: BLOB требует `content_model=bytes`, `row_count=None`. Existing `backend/app/storage/artifacts/blobBackend.py::ContentAddressedBlobBackend` принимает такой contract; новый backend из этого требования не следует. Existing `backend/app/application/artifacts/registry/artifactRegistry.py::ArtifactFormatRegistryBinding.register` требует тот же экземпляр contract у backend и запрещает повторный format key. Это evidence существующей реализации, не согласие владельца на конкретную Terrain registration.

`verify` и `read_verified` BLOB backend проверяют hash/size/descriptor и возвращают bytes, но не вызывают Terrain decoder. Поэтому будущая цепочка чтения должна явно показать decode/strict semantic validation; успешная integrity-проверка не доказывает корректность Terrain body. Runtime read/storage здесь не реализуется.

Для закрытия Source composition предъявить одной таблицей:

| Элемент | Владелец / необходимая конкретизация |
|---|---|
| member descriptor | Source: SCH-WORLD-TERRAIN/member, WORLD, REGISTRY_MEMBER, TEXT; concrete immutable definition и registration |
| membership descriptor | Source: SCH-WORLD-TERRAIN/membership, WORLD, COLLECTION, NONE; member_descriptors и принятый SET/SEQUENCE; для SET canonical bytes order по spec §10.2, duplicate identities reject |
| key binding | Source concrete adapter к согласованному TerrainKeyValidator; exact round-trip и INVALID_IDENTITY с исходным operation/path; без latest lookup |
| body binding | Terrain codec/manifest/format выбранной схемы; Source связывает descriptor с допустимыми format/version и проверкой identity↔system_terrain |
| semantic binding | Terrain projector с принятыми slots/exclusions/version; Source digest не подменяет ArtifactRef.content_hash |
| artifact binding | Concrete contract instance + existing backend + registry registration; неподдерживаемая версия/коллизия/чужой descriptor отвергаются |
| исторические bindings | Source: удерживаемые версии не переназначаются на latest; смена format не меняет object identity |

Эта таблица задаёт остаток design, а не готовые signatures отсутствующего полного binding. Key-only registry из API sheet не закрывает body/projector composition. Source proof validator не вызывает projector/IO. Pack, DAG, CRUD, writer/storage/finalizer и миграция Terrain не добавляются в scope; их реализация не нужна для исправления этих документов. Порядок остаётся G1.1/G1.2 (поставлены) → принятие G1-BIND/API → G1.3 → независимая приёмка G1.
