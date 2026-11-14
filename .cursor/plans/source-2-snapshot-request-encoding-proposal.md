# Source 2: encoding SourceProofReadInput для Snapshot ledger

2026-11-14. **PROPOSED, NOT ACCEPTED, NOT IMPLEMENTED.** Отдельное Source-owned предложение; не изменение Source spec, G1 или разрешение runtime. Scope пользователя — только encoding уже согласованного request в historical pinned-origin binding. Общий UUID encoding ManifestPinRead вне scope.

## 1. Baseline и граница решения

Проверен HEAD `b1ecaea67e6f1e63f7b3ca70aa9b7e7af04ce52a`. Прочитаны AGENTS.md, implement-plan (код не запрошен), обязательные критерии dag-generator-interface.mdc, source-proof-v2-contract-spec.md §11.4, source-g1-values-canonical-implementation.md, snapshot-pinned-origin-contract-r1.md (r2), snapshot-pinned-origin-storage-codec-proposal.md.

Accepted: SourceDurableProof ID 71131, поля schema_version/world_uid/uses, версия 1 и proof vectors; SOURCE_PROOF_SCHEMA_V1 исключает requests/results/errors. Accepted Snapshot decision — single full origin и historical-only durable binding. Независимый PASS ограничен first-call и explicit retained-input repeat; он не принимает storage encoding или crash recovery.

Фактические `backend/app/dataModel/sourceVersioning` и `backend/app/application/worldData/sourceVersioning` отсутствуют. SourceProofReadInput пока контракт, не доступный runtime import. Existing `backend/app/dataModel/encoding/schemaManifest.py` содержит RegisteredTypeEntry(type_id, python_type, kind) и CanonicalSchemaManifest(entries). Existing `backend/app/encoding/canonicalCodec.py` предоставляет encode(value, manifest), decode(encoded, expected, manifest), merge_manifests и CanonicalEncodingError. Manifest не содержит отдельной таблицы полей: порядок берётся из owning model declaration.

До создания этого файла поиск `71201` в backend, .cursor, .agents, docs не дал совпадений. Это проверка текущего дерева, не глобальное резервирование. ID должен быть повторно проверен перед принятием/реализацией вместе со всеми merged manifests. Accepted Source roster 71001, 71110–71114, 71120–71131, 71138 и shared 20003/20107 не затрагивается.

## 2. Exact предложенная registration

Предлагаемый файл: `backend/app/application/worldData/sourceVersioning/encoding/sourceProofRequestSchemaV1.py`.

Публичный импортируемый immutable constant `SOURCE_PROOF_REQUEST_SCHEMA_V1: CanonicalSchemaManifest` содержит **ровно одну** RegisteredTypeEntry:

| type_id | kind | python_type | Порядок обязательных полей |
|---|---|---|---|
| 71201 (proposed) | CanonicalTypeKind.RECORD | app.dataModel.sourceVersioning.sourceProofInput.SourceProofReadInput | world_uid: EntityUid; proof: SourceDurableProof |

Owner — Source. Используется единственная модель из G1, frozen/strict/extra-forbid/revalidate-always, без defaults. EntityUid — existing `app.dataModel.identity.uid.EntityUid`, scalar string, не UUID. Proof — `app.dataModel.sourceVersioning.sourceDurableProof.SourceDurableProof`. Новый request DTO, dict mirror, schema_version поле request и новый SourceDurableProof version не вводятся. Суффикс V1 относится к immutable registration request, не к новой версии proof.

Manifest намеренно является registration fragment: standalone request encode требует объединения с transitive proof manifest. Source-owned композиция в том же новом файле экспортирует `SOURCE_PROOF_REQUEST_ENCODING_V1 = merge_manifests(SOURCE_PROOF_SCHEMA_V1, SOURCE_PROOF_REQUEST_SCHEMA_V1)`. Это полный immutable encoding manifest для request, не изменение SOURCE_PROOF_SCHEMA_V1. Snapshot использует этот экспорт при merge своего binding manifest с Artifact и Pack registrations. Consumer не назначает ID, не собирает альтернативный Source roster и не подменяет owner type.

Exact request bytes: existing encode(request, SOURCE_PROOF_REQUEST_ENCODING_V1). Record TLV tag 7, payload — existing encoding tuple `(71201, (("world_uid", request.world_uid), ("proof", request.proof)))`. Эта запись описывает wire layout, не разрешает runtime tuple/dict вместо реального POJO. Nested proof кодируется теми же 71131/полями/версией; encode(proof, SOURCE_PROOF_REQUEST_ENCODING_V1) должен быть byte-for-byte равен encode(proof, SOURCE_PROOF_SCHEMA_V1).

Альтернатива «сохранять только proof, world восстановить» отвергнута: меняет exact input representation и скрывает самостоятельное поле request. Tuple wrapper без registration потребовал бы нового custom decoder и отдельного неявного контракта. Одна registration существующего record сохраняет единый typed decoder и проверку owner.

## 3. Ответственность, ошибки и границы

| Участник | Допустимая ответственность / зависимости | Основание отказа |
|---|---|---|
| SourceProofReadInput, Source-owned sourceProofInput.py | Existing world_uid/proof, structural validation; read не нормализует persisted proof | Mirror, defaults, новый authority смысл или silent normalization |
| SourceDurableProof и transitive roster §11.4 | Existing immutable values/IDs; семантические проверки остаются Source pure layer | Изменение accepted bytes/полей/версии ради request |
| RegisteredTypeEntry, CanonicalSchemaManifest | Existing immutable type identity; uniqueness ID/owner | Dynamic discovery или consumer-assigned Source ID |
| CanonicalCodec и existing encode/decode/merge | Pure typed serialization и collision/noncanonical checks, без IO | Новый codec engine, fallback или legacy decoder |
| Snapshot PreparationSourceBindingCodec, proposed application/publication/encoding/preparationSourceBindingCodec.py | Enclosing encode/decode на merged manifest; exact request projection; dependencies только owning values/manifests | Выдача authority по decode, обход Source semantic admission |

Не вводится новый error POJO или SourceOperation. Invalid registration/collision/unknown type/noncanonical bytes/structurally invalid decoded request — existing CanonicalEncodingError на shared module-level encode/decode/merge boundary. Ошибка композиции обнаруживается до writes. Corrupt persisted row Snapshot переводит в existing PublicationInfrastructureError по своему storage proposal, не в missing-origin и не в SourceFailure. Domain proof/world/descriptor semantics проверяются существующим Source validation/admission контрактом; успешный decode не заменяет эти проверки и не доказывает holds, coverage или finalization. G1-BIND остаётся OPEN: здесь не изобретается его API/adapter и не утверждается его завершение.

Новый публичный pipeline/CRUD/настройки отсутствуют. Constant — публичный encoding binding, не самостоятельная доменная операция. Snapshot получает bytes своего existing request через pure codec; публичный Source READ/ADMIT не вызывается для сериализации. Data/settings C/R/U/D не добавляются и этим предложением не принимаются. Три запрета DAG сохранены: нет pipeline routing, скрытого запуска через callback/worker и прямого вызова публичной операции другого домена. G4/finalizer/public DAG/crash-input producer вне scope. Порядок pinned r2/S1/S2 и основной Source delivery sequence неизменен.

## 4. Проверки и зависимости до принятия реализации

1. Повторно проверить 71201 во всём актуальном roster; merge с Artifact/Pack/Snapshot и exact owner/kind collisions. Совпадающие shared declarations допускаются existing merge, конфликтующие ID либо owner отклоняются.
2. На реальных G1 моделях проверить exact root type, round-trip request с empty/nonempty/historical proof, immutable mandatory fields, wrong world/type/unknown fields и отсутствие normalization. Semantic invalid cases должны отклоняться owning validator; одного codec round-trip недостаточно.
3. Зафиксировать literal golden request bytes после принятия ID и появления реальных моделей; не вычислять expected тем же тестируемым encoder. Existing §11.4 V0/V1 bytes/fingerprints неизменны в обоих manifests; request bytes отличаются от proof bytes и не подменяют selection fingerprint.
4. Unknown request ID, wrong field order, trailing/truncated bytes, wrong root, bool proof version, malformed nested proof — отказ; decode/re-encode должен воспроизводить exact canonical bytes. SOURCE_PROOF_SCHEMA_V1 отдельно по-прежнему отвергает request как unregistered.
5. Snapshot проверяет encode(decoded_binding.request) == row.request_data на том же immutable composition. Hash не заменяет full equality. Повреждение projection не трактуется как отсутствие registration. Ledger atomicity и grant lifecycle проверяются Snapshot отдельно.

Source dependencies: принятие этой отдельной registration; наличие настоящих G1 values/proof manifest и закрытие их собственных gates в утверждённом порядке. Нельзя автоматически включать новый модуль или tests в G1: нужен отдельно разрешённый implementation slice после принятия proposal. Snapshot dependencies: Pack ManifestPinRead registration, shared UUID решение и enclosing roster/codec/ledger остаются открыты независимо от Source request registration. Этот документ не выбирает UUID tag/байты.

## 5. Статус приёмки

Роли и признаки нарушения — §3; public/internal граница и все три запрета DAG — §3; неизменный порядок и открытые prerequisites — §4; POJO не дублируются — §2–3; новых междоменных CRUD маршрутов нет. Это адресный proposal encoding, не приёмка домена Source или всего Snapshot storage плана. При отсутствии evidence для любого обязательного критерия зависимая реализация не принимается.

Нужно отдельное owning/joint review и явное принятие 71201/composition. Runtime tests не запускались, golden request vector пока не предъявлен; это не PASS реализации. Изменён только этот документ. Source spec, G1/implementation планы, runtime, SQL, Pack UUID и прежний Source чат не затронуты.
