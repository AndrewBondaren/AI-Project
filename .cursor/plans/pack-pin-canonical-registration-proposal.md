# Pack: canonical registration ManifestPinRead

2026-11-14. PROPOSED для совместного review, не accepted/runtime registration. Только существующий Pack record для Snapshot pinned-origin storage. Основной план, POJO, код и SQL не меняются. UUID primitive — отдельная shared-codec дельта Snapshot.

## Точная декларация

- Existing owner: `app.dataModel.worldPack.read.pinnedManifest.ManifestPinRead`.
- Proposed declaration module: `app.dataModel.worldPack.encoding.pinBindings` (`backend/app/dataModel/worldPack/encoding/pinBindings.py`). Только schema data, без encoder/IO.
- Proposed manifest: `PACK_PIN_SCHEMA`, один `RegisteredTypeEntry(type_id=20205, python_type=ManifestPinRead, kind=CanonicalTypeKind.RECORD)` внутри `CanonicalSchemaManifest`.
- ID 20205 предложен после поиска `rg -n '20205' backend docs .cursor/plans`: до создания этого документа совпадений нет. Это локальная проверка дерева, не глобальный allocator/reservation. Соседние 20201–20204 уже предложены в pack-canonical-registration-audit.md для activation; не переиспользовать их. Перед принятием повторить collision/owner check итоговой Snapshot composition.

## Поля в существующем порядке

| № | Поле | Owning тип / canonical value |
|---|---|---|
| 1 | store_id | uuid.UUID; требуется native UUID scalar encoding/strict decode |
| 2 | execution_id | ExecutionIdValue из app.dataModel.engine.dag.identity; runtime str, существующие constraints |
| 3 | invocation_id | InvocationIdValue из того же модуля; runtime str, существующие constraints |
| 4 | logical_read_key | Annotated[str, Field(min_length=1)] |
| 5 | pin_id | Annotated[str, Field(min_length=1)] |
| 6 | world_uid | Annotated[str, Field(min_length=1)], не менять на EntityUid этой регистрацией |
| 7 | max_bytes | PositiveInt под strict model validation; не bool, положительное целое |

Existing model frozen/strict/extra-forbid/revalidate-always. NewType ExecutionId/InvocationId не отдельные canonical records; отдельные IDs для них, UUID или базы _Record не назначаются. ArtifactRef не поле этого record, его import в исходном модуле не означает transitive schema dependency. Python annotations/validators не сериализуются. Nested domain records отсутствуют.

CanonicalCodec уже берёт порядок из exact model_fields, strict-revalidates values и отклоняет missing/duplicate/extra/reordered fields при decode. Не дублировать DTO и не создавать вручную альтернативную projection. Ни pin identity, ни successful decode не дают authority: persisted OPEN binding/live holds проверяются прежним owning путём.

## Composition и UUID prerequisite

Snapshot включает PACK_PIN_SCHEMA в конкретную authority-storage composition через existing merge_manifests, не добавляет весь Pack surface manifest. Exact owner не должен иметь второй ID в этой composition. PACK_PIN_SCHEMA не меняет ARTIFACT_CORE_SCHEMA, SOURCE_PROOF_SCHEMA_V1, manifest bytes codec или manifest cache contract. Добавление неиспользуемой декларации само по себе не меняет bytes других owners; не перенумеровывать существующие shared declarations.

Сейчас canonicalCodec не поддерживает UUID. Поэтому регистрация record сама по себе не обеспечивает round-trip. Предложение Snapshot native UUID TLV tag 10 / 16 bytes НЕ принимается этим документом: требуется отдельный shared-codec review, включая strict type/length, deterministic bytes, decode UUID без string coercion и неизменность encoding прежних values. Не обходить отсутствие primitive через str(store_id), mirror record или legacy decoder. Конкретной причины запрещать прямую registration existing ManifestPinRead не найдено; единственная выявленная scalar prerequisite — UUID.

## Проверки перед реализацией и её приёмкой

1. Проверить proposed ID/exact owner в полном composed manifest, duplicate owner/ID conflicts; импорт declaration не добавляет executable behavior.
2. После принятия UUID encoding: strict round-trip исходного ManifestPinRead и stable encode после decode, exact UUID type, оба execution identifiers сохраняют opaque strings. Unknown tag/неверная длина UUID, неверный field order, extra/missing поля, invalid identifiers и max_bytes=bool/0 отвергаются.
3. Утвердить pinned record vectors только после scalar решения; сейчас bytes/hash не выдумываются. Повторное создание из тех же validated values даёт те же bytes; изменение каждого поля меняет canonical record.
4. Регрессия старых ArtifactRef/cache key и Source proof vectors: новые declarations/native scalar support не меняют их bytes при неизменных исходных данных и declarations.

Статически прочитаны pinnedManifest.py, engine/dag/identity.py, canonicalCodec.py record encode/decode, Pack registration audit и Snapshot storage proposal. Runtime tests не запускались. Это предложение Pack-owned declaration, не приёмка Snapshot storage и не общий gate завершения контрактного плана Pack.
