# Source 2: полученный Terrain owning contract и оставшиеся зависимости

2026-11-15. Документальная сверка по прямому указанию пользователя «Делай» после предъявления ответа Terrain. **Ответ получен; повторно запрашивать отсутствующие signatures нельзя.** Это фиксация и review предложения, не автоматическая приёмка G1-BIND или разрешение runtime. Прежний Source чат, его spec/G1/API sheet и Terrain код не изменяются.

Источник: приложенный пользователем «Вставленный текст.txt» (attachment 6e038190-b0c9-4a7d-9388-45d212b75bff), начинающийся «Ниже новое owning предложение для принятия». В source-g1-pure-api-sheet.md §3.1 строка «ответ ещё не получен» устарела относительно этого evidence. Настоящий документ фиксирует актуальный ответ без правки чужого плана и без восстановления отозванного TerrainSourceAdapter.

## 1. Предъявленные owning signatures

Все пути ниже под backend/app/application/worldData/generators/terrain/source. Это предложенные пути, не существующие imports.

| Компонент | Exact контракт | Ответственность / отказ |
|---|---|---|
| terrainKeyValidator.py::TerrainKeyValidator | validate_exact(self, token: str) -> TerrainKey; encode_exact(self, key: TerrainKey) -> str | TerrainKey = RegistryKey[WorldTerrainRegistry]. Проверить базовое строковое содержимое strict/min_length=1, включая nominal string carriers, минуя доверие instance-ветви RegistryKey. Без strip/casefold/Unicode normalization/regex, lookup или coercion bytes/numbers. Повторная проверка encode, exact round-trip. Отказ pydantic.ValidationError; принятие пустого forged RegistryKey либо normalization нарушает контракт. |
| encoding/terrainBodyCodecV1.py::TerrainBodyCodecV1 | encode(self, body: TerrainRegistryEntry) -> bytes; decode(self, payload: bytes, version: FormatVersion) -> TerrainRegistryEntry | Exact class, полный strict immutable full19/nested roster, key validation; version только 1, exact bytes, encode(decoded)==payload. Единственный encoder — existing canonicalCodec. Defaults repair/legacy adaptation запрещены. |
| encoding/terrainSemanticProjectorV1.py::TerrainSemanticProjectorV1 | project(self, body: TerrainRegistryEntry) -> bytes | Canonical tuple ("terrain.source-entry.semantic", 1, body), все 19 полей semantic, exclusions пусты. Сохранять rules/shapes/fill_roles order, empty shapes; не вызывать resolved_shapes, latest/catalog или reference IO. |

Body codec/projector constructors не принимают caller manifest, callbacks или settings. Ошибка — existing app.encoding.canonicalCodec.CanonicalEncodingError, validation cause сохраняется. Semantic bytes хеширует Source существующим digest; Artifact bytes — encoding самого body, не semantic tuple. Новых errors/POJO/mirror нет.

`encoding/terrainSourceSchemaV1.py::TERRAIN_SOURCE_SCHEMA_V1`: reuse ID17 TerrainRegistryEntry; 18 EligibilityRule; 19 EligibilityOp; 20 HillPolicy; 21 HillShape; 22 TerrainFillRole; 23 HydrologyCellRole. ID16 WorldTerrainRegistry исключён: registry не child entry body. Изменение layout17 требует ограниченного compatibility review существующего full-entry format; назначать новый ID тому же owner или адаптировать старые bytes нельзя.

`encoding/terrainSourceFormatV1.py::TERRAIN_SOURCE_ENTRY_FORMAT`: ArtifactFormatContract[bytes], key terrain.source-entry, kind BLOB, supported_versions=frozenset({1}), content_model=bytes, row_count=None. Encode/decode format binding проверяют payload через TerrainBodyCodecV1.decode и возвращают exact исходные bytes. Это value/format contract; backend/lifecycle не возникает из объявления константы.

## 2. Сверка с актуальным кодом и Source boundary

- dataModel/registryKey.py действительно имеет is_instance_schema перед строковой ветвью min_length=1. Требование проверять содержимое заново обосновано. docs/tz_json_validation.md §RegistryKey задаёт nominal TerrainKey; новая whitelist/нормализация не следует из SoT.
- application/artifacts/contracts/formatBackend.py::ArtifactFormatContract.__post_init__ требует для BLOB model is bytes и row_count is None. Предложенный bytes binding соответствует; ArtifactFormatContract[TerrainRegistryEntry] для BLOB был бы отвергнут.
- dataModel/terrain/encoding/surfaceBindings.py уже владеет IDs17–22; dataModel/hydrology/encoding/surfaceBindings.py — ID23. Повторное использование должно сохранять точный owner/kind и проходить merge collision checks, а не копировать declarations с другими IDs.
- dataModel/terrain/terrainRegistryEntry.py пока имеет 18 полей, extra=ignore, defaults, eligibility:list и has_authored_hills через model_fields_set. Явного hills_authored нет. Каталог application/worldData/generators/terrain/source отсутствует. Следовательно owning предложение нельзя выдавать за реализованный strict full19 контракт.
- Source API sheet §3 предлагает SourceIdentityKeyAdapter.validate_exact(identity: SourceObjectId) -> SourceFieldCode | None, тогда как Terrain принимает token и возвращает key/ValidationError. Это разные ответственности, не interchangeable signatures. Нужен конкретный Source adapter: после Source category/descriptor checks извлечь member_key, вызвать owning exact validator/encoder, подтвердить round-trip, преобразовать только ожидаемый ValidationError в INVALID_IDENTITY. Operation/path создаёт Source validator; ошибки программирования/композиции не маскируются как INVALID_IDENTITY. Terrain не принимает SourceObjectId и не выпускает SourceFailure.
- Для SCH-WORLD-TERRAIN/membership key_kind=NONE, adapter не нужен; member keys проверяются через /member. SEQUENCE сохраняет порядок членов; duplicate identities reject. Наличие членства проверяется по captured membership, не latest.

## 3. Что осталось, с владельцами и evidence

| Gate | Владелец / необходимый результат |
|---|---|
| Принятие owning design | Совместно принять предложенные exact-key methods/errors, strict full19/nested body, all19-semantic tuple/tag/version, SEQUENCE policy и minimal manifest/format. Пользователь поручил сверить и зафиксировать предложение; это не объявляется его молчаливой приёмкой всех решений. Presence hills_authored, no legacy adaptation и authored bootstrap уже согласованы и повторного выбора не требуют. |
| Source concrete composition | Source должен предъявить exact concrete adapter/module/constructor и полный descriptor registration, связывающий key, body codec/format, semantic projector; запрет Any/dict/passthrough и неполной key-only подмены сохраняется. Здесь новый adapter API не выдумывается. |
| Terrain contract delivery | Owning full19/nested strengthening и caller cutover, ограниченный ID17 compatibility check; затем реальные key/body/projector golden/negative/round-trip tests. Не применять codec к старому permissive body через repair. |
| Artifacts registration | Подтвердить подходящий existing backend и реальную регистрацию terrain.source-entry v1 в ArtifactFormatRegistryBinding (application/artifacts/registry/artifactRegistry.py). Константа bytes-contract сама этого не доказывает. Storage/lifecycle design в это уточнение не добавлять. |

Проверки до implementation acceptance: пустой вручную созданный RegistryKey, bytes/numbers, nominal string carriers, Unicode/пробелы/регистр без изменения; full19 missing/extra/coercion/nested mutability; три hills-state; изменение каждого semantic поля; empty/nonempty/reordered shapes/rules/membership и duplicate identities; exact literal vectors/round-trip/unsupported versions; ID/owner/kind collisions и ограниченная compatibility17. Эти runtime проверки этим документальным проходом не выполнялись.

## 4. Граница приёмки

G1-BIND остаётся OPEN **по принятию/композиции/регистрации и evidence, а не по отсутствию ответа Terrain**. Request encoding71201 уже поставлен отдельным срезом и этим gate не блокируется. G1.3/полный G1 не объявляются завершёнными.

Роли/deps/effects/refusals — §1–2; публичный Source/Terrain CRUD не расширяется; новых data/settings C/R/U/D нет. Pure внутренние контракты не являются public pipelines и не вводят ветвление DAG, скрытую оркестрацию или прямые вызовы публичных операций чужого домена. Утверждённый порядок owning contract → concrete composition → соответствующая реализация/проверки сохраняется. Writer/storage/recovery/finalizer/DAG и другие реестры вне scope. При отсутствии evidence любого обязательного критерия приёмка зависимой реализации не проходит.

Изменён только этот документ через apply_patch. Следующий содержательный шаг — review предъявленного design и конкретизация Source composition по нему, не повторный запрос Terrain придумать уже предъявленные signatures.
