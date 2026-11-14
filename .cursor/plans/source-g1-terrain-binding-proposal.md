# Terrain dependency для Source G1-BIND — owning предложение

2026-11-15. **PROPOSED, NOT ACCEPTED.** Источник — ответ owning чата `01a1d6e7-7dc4-71c0-a570-5abda0bffe62`, turn `01a1dc0d-cfbe-77e3-af90-00b1907af532`. Source фиксирует предложение, не принимает его вместо владельца/пользователя. Код Terrain, Artifacts и Source этим документом не разрешается. Связанные документы: terrain-source-execution-contract-dossier.md; source-proof-v2-contract-spec.md §10.1; source-g1-pure-api-sheet.md §3.1.

## 1. Exact key

Предлагаемый owning модуль `app.application.worldData.generators.terrain.source.terrainKeyValidator`:

```python
class TerrainKeyValidator:
    def validate_exact(self, token: str) -> TerrainKey: ...
    def encode_exact(self, key: TerrainKey) -> str: ...
```

TerrainKey — existing RegistryKey[WorldTerrainRegistry]. Отказ — existing pydantic.ValidationError. Повторно проверяется базовое строковое содержимое, strict/min_length=1, без доверия instance-ветви RegistryKey. String carriers допустимы, bytes/числа/coercion — нет. Никаких strip/casefold/Unicode normalization/нового regex. encode_exact повторяет проверку; exact token equality обязательна. Проверка наличия member в registry сюда не входит. Source owning adapter переводит отрицательный validation outcome в INVALID_IDENTITY с исходными operation/path, не анализируя message. Terrain не принимает SourceObjectId и не создаёт SourceFailure.

Для SCH-WORLD-TERRAIN/membership key_kind=NONE; key adapter не регистрируется. Ключи членов проверяются через /member.

## 2. Body encoding и semantic projection

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
| Exact key API §1 | Terrain, Source для boundary mapping | Принять concrete signature; negative пустой nominal key/bytes/numbers, exact case/whitespace/Unicode round-trip |
| Strict full19/nested body | Terrain | Полный exact roster/validation/callers compatibility, три hills presence состояния, no repair |
| All19 semantic/tuple/tag/version | Terrain; принятие пользователем | Зафиксировать semantic policy и literal vectors; показать изменение bytes для каждого влияющего поля/presence |
| SEQUENCE membership / duplicate refusal | Terrain semantics, Source collection contract | Принять рекомендацию, проверить значимость перестановки; не выводить из текущего list root |
| Reuse manifest IDs/layout | Terrain, владельцы enclosing encodings | Проверить совместимость ID17 и остальных записей; не переназначать старый layout автоматически |
| BLOB bytes format registration | Artifacts совместно с Terrain | Подтвердить exact existing binding/backend, unsupported-version/collision/vector checks |
| Concrete Source composition | Source после owning подтверждений | Связать принятые contracts без permissive adapters и fake registration |

До этих подтверждений G1-BIND OPEN. G1.1/G1.2 PASS сохраняется. Writer/storage/recovery/DAG, миграция реестров и код Pack вне этого согласования. Следующий шаг — разрешить перечисленные design/compatibility пункты с владельцами; принятие только общего названия adapter не является приёмкой concrete composition.
