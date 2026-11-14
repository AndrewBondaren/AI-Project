# Pinned origin: storage и canonical encoding

**UUID-срез принят пользователем 2026-11-14:** ответ «Ок» на конкретную дельту tag10 / 16 bytes / оба decoder / синхронизация SoT разрешил только этот независимый implementation scope. Нижние proposed/blocked статусы сохраняются для registration/storage, не блокируют принятый UUID primitive. Реализация и evidence — §8.

2026-11-14. **PROPOSED / BLOCKED ON OWNER ENCODING DECISIONS**, не разрешение runtime-кода. Следующий design-срез после принятого single-origin/historical persistence и независимого PASS [pinned r2](snapshot-pinned-origin-contract-r1.md). Scope: конкретизировать existing operation ledger extension и canonical представление уже согласованного binding. Source S1/S2/adopt, G4/finalizer, DAG и crash input не расширяются.

**Текущая конкретизация:** Source 2 и Pack предъявили отдельные registration proposals; сводная таблица и следующий ограниченный implementation scope находятся в §7. Статус их приёмки не подменяется наличием предложений. Прежний Source не изменяется и не опрашивается.

## 1. Фактический baseline и найденные пробелы

HEAD проверки `b1ecaea67e6f1e63f7b3ca70aa9b7e7af04ce52a`, рабочие документальные изменения сохранены. `backend/app/db/models/snapshotCore/operationRows.py` и `backend/app/db/migrations/0001_initial.sql` содержат immutable operation identity, event chain, publication request fingerprint и terminal outcome. Поля для нескольких Source request/origin bindings в одной preparation отсутствуют. Existing terminal outcome нельзя использовать для промежуточной registration: он имеет иной lifecycle и один outcome на operation.

Согласованный `PreparationSourceBinding(target, request, origin, sources)` ещё не реализован. Его transitive values: existing OperationLeaseRef/VerifiedArtifactRef/ArtifactRef/holders, SourceProofReadInput/SourceDurableProof, ManifestPinRead и proposed pinned origin enum/record.

**ENC-UUID:** `ManifestPinRead.store_id` — настоящий UUID (`backend/app/dataModel/worldPack/read/pinnedManifest.py`). Общий `backend/app/encoding/canonicalCodec.py` поддерживает TLV tags 0–9, UUID отсутствует. Воспроизводимый read-only запуск из backend:

```powershell
.venv/Scripts/python.exe -c "from uuid import UUID; from app.encoding.canonicalCodec import encode; from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest; print(encode(UUID('00000000-0000-0000-0000-000000000001'), CanonicalSchemaManifest(entries=())))"
```

Результат: exit 1, `CanonicalEncodingError: unsupported canonical value`. Это конкретный transitive counterexample: добавление только ID для pin/binding не сделает их сериализуемыми. Existing ArtifactRef encoding менять не требуется.

**ENC-SOURCE-REQUEST:** Source spec §11.4 имеет owning `SOURCE_PROOF_SCHEMA_V1`, в том числе SourceDurableProof=71131, но явно исключает requests/results. SourceProofReadInput — обязательный nested record binding, его canonical ID и owning manifest пока не предъявлены. Нельзя самовольно назначить Source record ID в Snapshot или записывать его как произвольный dict.

**ENC-PIN:** canonical registration существующего ManifestPinRead не найдена в просмотренных Snapshot/Artifact/Patch manifests. Её owning declaration/ID должен подтвердить Pack. Shared UUID scalar support не заменяет registration самого record.

До решения этих конкретных encoding зависимостей зависимую реализацию не начинать. Запросы Source и Pack отправлены в рамках согласованной координации; это не новые внешние домены.

## 2. Предложенное физическое представление

Новая immutable detail-таблица `publication_preparation_sources` **в составе existing operation ledger**, не отдельный receipt service/store/database. Это явное proposed DDL-дополнение; текущая схема его не содержит. Будущие изменения только `0001_initial.sql` и синхронный row model, без migration/legacy backfill. Public API не добавляется.

| Column | Тип / constraint | Назначение |
|---|---|---|
| operation_id | TEXT NOT NULL, FK publication_operations(operation_id) | Owning immutable operation |
| request_data | BLOB NOT NULL, typeof=blob, length>0 | Exact canonical SourceProofReadInput bytes, часть ключа |
| binding_data | BLOB NOT NULL, typeof=blob, length>0 | Полный canonical PreparationSourceBinding |
| binding_checksum | TEXT NOT NULL, 64 lowercase hex | Existing content_digest(binding_data).hex() |

PRIMARY KEY `(operation_id, request_data)`. Preparation fingerprint функционально определён immutable publication_operations.operation_id; в payload target он также обязателен и сверяется с owning operation. Fence намеренно **не входит** в ключ: другой fence не создаёт вторую authority row и не обходит immutable conflict. Исторический origin и sources только внутри binding_data; per-ref SQL rows/отдельные IDs не требуются.

Append-only no-update/no-delete и duplicate-identity insert guards следуют existing ledger pattern; `INSERT OR REPLACE/IGNORE` запрещены. Все writes — обычный INSERT после scoped проверки существующей записи, без собственного commit. Никакого independent format counter/receipt ID/secondary journal. Единственная поддержанная canonical schema задаётся immutable merged manifest; другая форма отклоняется, legacy decoder отсутствует.

Request bytes — SQL projection nested поля binding для адресации, не второй доменный POJO. Codec обязан проверять `encode(decoded.request) == row.request_data` и `decoded.target.operation_id == row.operation_id`; несоответствие — infrastructure. Digest не является ключом и не заменяет full equality. Поэтому совпавшие hashes разных canonical requests не объединяют records. Дополнительный digest-index пока не нужен.

SQL FK не удостоверяет current lease, PREPARING или успешный Source admission: это scoped adapter/provider responsibility. Таблица сама по себе не доказывает READY. Только trusted atomic owner коммитит registration вместе с READY/candidate/holds; никакой новый public writer этого разрешения не получает. Atomic integration test обязан доказать rollback и отсутствие standalone PREPARING commit. Не обещать невозможного «DDL сам проверяет весь Source proof».

## 3. Классы, методы и nested effects

Пути относительно backend/app; всё ниже proposed, не implemented.

| Класс / файл | Обязанность и зависимости | Отказ в приёмке |
|---|---|---|
| PublicationPreparationSourceRow, `db/models/snapshotCore/operationRows.py` | Frozen row с четырьмя полями §2, никаких IO/семантических методов | Mirror доменного proof/origin или собственные defaults |
| PreparationSourceBindingCodec, `application/publication/encoding/preparationSourceBindingCodec.py` | Pure strict encode/decode accepted binding и request на explicit immutable manifest; ошибки canonical shape, никакого IO | Coercion UUID в string, auto registration, fallback/legacy decoder |
| SqlitePreparationAuthorityStore, `db/repositories/sqlite/snapshotCore/operations/preparationAuthorityStore.py` | Принятые append(scope,binding)/read(scope,target,request), registry+scoped operation checks, row projection/checksum/integrity, SQL | Own UOW/bind/GC/hold acquisition; row admission из public caller |
| PackPreparationSourceAuthority, `application/publication/service/packPreparationSourceAuthority.py` | Exact issued grant/evidence, current origin/holds, immutable register/resolve через store | Raw refs/rows вместо grant; aggregate partial origins |

Public/internal и Source/Pack readers unchanged по pinned r2. Store получает тот же scope/coordinator/access, что atomic owner. `append`: strict target/request/binding → registry write/operation check → existing scoped operation/current lease/PREPARING guard → existing row integrity checks → exact equality no-op или immutable conflict → INSERT. `read`: strict input → registry read/operation identity → scoped operation/current lease → checked rows → exact request lookup → decoded binding или None. Store не выполняет Source collect/adopt и не проверяет pin через nested public UOW; эти checks остаются provider.

До оптимизации store читает строки этой operation и проверяет checksum, canonical decode и row/body equality перед сопоставлением request. Это не позволяет повреждению request_data скрыть существующую запись под видом missing registration. Для каждого decoded target проверяются world/kind/preparation identity по immutable operation. Отличающийся caller lease → owning STALE_LEASE; валидный current target против исторического binding fence → IMMUTABLE_BINDING_CONFLICT, без mutation. Corrupt identity/body/bytes → PublicationInfrastructureError, не lifecycle refusal. `read(None)` только когда целевого canonical request действительно нет среди проверенных rows.

При exact row no-op store не возвращает успех минуя current guards. На INSERT race единый BEGIN IMMEDIATE сериализует writers; unexpected SQL constraint failure не превращается по тексту exception в no-op. Provider/outer rollback сохраняют typed authority errors и unknown precedence r2. Источники не release-ятся.

## 4. Encoding proposal и конкретные owner decisions

**Предпочитаемое предложение ENC-UUID:** native UUID scalar в existing canonical TLV codec: tag 10 (0x0a), length ровно 16, payload `UUID.bytes`; decode возвращает UUID(bytes=payload), другие lengths отвергаются. Полный вектор UUID(int=1): `0a000000000000001000000000000000000000000000000001`. Existing tags/record IDs/field orders и bytes всех ранее поддержанных values не меняются. Это shared codec contract delta, требующая отдельной приёмки; её ещё нет в коде. UUID не подменяется string/bytes field в Pack DTO. Новый mirror pin record не вводится.

**ENC-PIN:** Pack должен назначить или предъявить owning ManifestPinRead canonical ID/manifest с exact field order store_id, execution_id, invocation_id, logical_read_key, pin_id, world_uid, max_bytes. Existing opaque execution/invocation string identities сохраняются, дополнительные форматы из DAG не изобретаются.

Ответ Pack 2026-11-14: owner DTO/UUID подтверждён; в проверенных declarations и планах existing registration/ID и принятого UUID encoding нет. Pack не утверждает общий scalar tag и подтверждает сохранение полей DTO без coercion/mirror. Это зависимость данного Snapshot integration path, не общий блокер завершения Pack contract-плана. Snapshot владеет подготовкой storage/codec delta; Pack review ограничивается его DTO/reader boundary, не переносом внешнего storage design в Pack.

Последующее конкретное [предложение Pack](pack-pin-canonical-registration-proposal.md) прочитано: `dataModel/worldPack/encoding/pinBindings.py::PACK_PIN_SCHEMA`, один RECORD ID **20205** для existing ManifestPinRead, exact семь полей в существующем порядке. ArtifactRef не является nested полем pin и не добавляется в этот manifest по одному наличию import. Opaque execution/invocation остаются strings, world_uid остаётся existing str; UUID primitive отдельный. Статус ID/manifest — PROPOSED, не reservation/accepted/runtime. Перед общей приёмкой повторить collision/exact-owner check с Source 2 и Snapshot roster. Прямой registration existing DTO подходит потребителю Snapshot; merge всего Pack surface и mirror не нужны. UUID и fixed vectors этим предложением не закрыты.

**ENC-SOURCE-REQUEST:** Source должен назначить отдельную owning canonical registration existing SourceProofReadInput(world_uid, proof), не меняя SourceDurableProof/его persisted schema и контрольные векторы. Возможен отдельный immutable Source request manifest для merge; Snapshot не выпускает новую версию Source proof и не назначает его ID.

Ответ Source 2026-11-14: отдельное owning encoding решение ещё не принято, gate OPEN. `source-g1-values-canonical-implementation.md` сохраняет accepted proof IDs/bytes и исключение requests/results/errors; наличие SourceProofReadInput POJO в G1 не обещает registration для этого ledger. Запрещено самостоятельно назначать Source ID или включать request в SOURCE_PROOF_SCHEMA_V1. Данный запрос не расширяет scope G1 автоматически. Выявленный Source gate exact pure/key-adapter API принадлежит его implementation-плану и не закрывается Snapshot заглушкой. UUID pin не относится к Source proof schema.

Snapshot owns registrations PreparationSourceOriginKind, PinnedManifestSourceOrigin(kind,pin,manifest), PreparationSourceBinding(target,request,origin,sources). Exact numeric IDs пока не закреплены: после ответов владельцев проверить весь merged roster и назначить свободные IDs одним документированным набором. R1–R3 IDs 20301/20302/20306/20307 не переиспользовать. Authority errors и runtime grant/evidence не входят в persisted binding manifest, «заодно» их не регистрировать.

Merge нового Snapshot binding manifest с owner Artifact/Source request+proof/Pack pin manifests выполняется existing merge_manifests, с exact owner/type/kind collision checks. Ни Snapshot metadata codec, ни terminal codec не должны неявно стать decoder всего Source/Pack graph: новый codec получает только необходимый transitive roster. Отсутствующая registration — composition/configuration error до writes, не business missing origin.

## 5. Проверки перед реализационной приёмкой

- Shared UUID: точный вектор выше; native type round-trip; invalid length 0/15/17, unknown tag, truncation; существующие Snapshot/Pack/Source canonical vectors и cache keys неизменны. Не считать нативный round-trip равным storage admission.
- Binding: full/empty sources, complete pin+target+request+origin round-trip; strict unknown fields, wrong enum/type ID, wrong field order и noncanonical payload отвергаются; UUID остаётся UUID. Fixed golden bytes вычислить только с принятыми numeric IDs и реальными Source types, не fabricated mirrors.
- Ledger: identical append no-op; same key/different origin conflict, включая empty proof; разные canonical requests с одинаковым тестовым digest не дают false equality; повреждение body, checksum и request projection → infrastructure; другой fence → отказ/no mutation.
- Atomicity: independent connections одной временной SQLite DB, late second proof refusal, commit visibility binding+READY+target holds, rollback absence, close/GC serialization, cancel/revoke, unknown dominance. READY replay не читает historical origin binding и допускает closed old pin.
- Typing и полный snapshotCore плюс профильные Source/Pack tests после реализации; fixture prerequisites G1/G2/G3 остаются обязательны. Ни один из этих tests не объявляется выполненным этим документом.

## 6. Приёмка и evidence этого прохода

### Координация после указания пользователя «Source 2»

Пользователь запретил трогать прежний Source и поручил создать новый чат для уточнений. Создан `Source 2`, thread `01a1db24-b734-7420-992c-e5867e7a1cfa`; ему передан только отдельный request-encoding proposal, без правок прежних Source spec/G1/implementation-планов. Дальнейшие уточнения идут туда. Существующий Pack чат `01a1cfce-ff7d-7e30-b738-f075bf490f13` продолжает pin-registration review с явного разрешения пользователя. Это не общий перенос владения Source или его текущих работ.

### Уточнённая общая UUID delta для review

SoT действующего TLV — `docs/tz_terrain_generation.md`, описание canonical codec v1 около строки 3307. Оно перечисляет только tags 0–9. Поэтому tag 10 требует явного согласования и синхронизации этого пункта SoT до реализации, а не только локального изменения Snapshot codec. В текущем проходе SoT не изменён.

Точный состав будущей общей правки после приёмки: `backend/app/encoding/canonicalCodec.py` — exact native UUID branch encoder, `_decode_scalar` UUID длиной 16, `_decode_one` dispatch tag10; `backend/app/application/encoding/boundedCanonicalDecode.py` — тот же scalar dispatch через existing `_decode_scalar` с сохранением budget/depth/items checks и strict expected-type match. Изменение только одного decoder недостаточно. Existing `decode` выполняет re-encode canonical check; UUID branch обязан работать в обоих направлениях.

`UUID.bytes`, не `bytes_le`, строка или int; wire не требует определённого UUID version/variant: такие ограничения отсутствуют в ManifestPinRead и не добавляются общим codec. Нулевой/all-ones UUID являются валидными scalar values, а право namespace проверяет pin owner. Tag10 primitive не получает RegisteredTypeEntry и не занимает record ID. Unknown tags кроме явно поддержанного 10 остаются ошибкой. UUID не должен приниматься вместо str/bytes поля, а str/bytes с тем же содержимым — вместо UUID. Compatibility означает неизменность bytes всех ранее поддержанных values; старый decoder не читает новый tag, dual decoder/legacy fallback не вводится.

Адресные будущие проверки: существующий `tests.planning.encoding.test_canonical_codec` плюс bounded-decode tests по фактическому roster; UUID root/nested/tuple/frozenset, exact vector, оба decoder, неверные lengths/trailing bytes, wrong expected type, budget limit. Затем Snapshot canonical regressions и имеющиеся Pack cache vectors. Эти проверки пока не запускались: production UUID delta не написана. Новые Source/Pack record goldens остаются зависимыми от отдельных согласованных registrations.

Три запрета DAG: новые public операции/ветвление/обходы не добавляются. Роли/deps/effects/refusals §3; public data/settings C/R/U/D не расширяются; internal persistence согласованного historical binding — §2. Порядок r2/S1/S2 не меняется. Новые POJO не дублируют чужие records, SQL projection не public DTO; конкретные transitive encoding пробелы открыты в §4. Поэтому весь storage/codec design пока **не готов к приёмке**, до owner решений dependent code остановлен.

Прочитаны actual operation DDL/rows, canonical codec/manifest, Snapshot/Artifact manifests и codecs, ManifestPinRead, Source spec §11.4 и pinned r2. Выполнены git status/HEAD, rg/Get-Content, один UUID repro с ожидаемым failure. Поиск UUID/tag10 в просмотренных owning encoding/Snapshot/Geo1 документах не дал готового принятого решения; это ограниченный поиск, не доказательство отсутствия любого документа в репозитории. Runtime код, DDL, Source/Pack plans не изменены; новый артефакт этого шага — данный proposal и ссылка на него в owning документе.

## 7. Сводная encoding-таблица для совместного review

По следующему указанию пользователя «далее по плану» прочитан [Source 2 proposal](source-2-snapshot-request-encoding-proposal.md). Предложены отдельный request fragment и Source-owned полный request manifest; proof schema/IDs/bytes не меняются. В новом чтении дерева Source values уже появились и имеют чужие незавершённые изменения, но `SourceProofReadInput` и `application/worldData/sourceVersioning/encoding/sourceProofSchemaV1.py` ещё не найдены. Историческая строка Source 2 об отсутствии всех папок относится к его baseline. Ничего из Source runtime/spec/G1 не менялось в этом проходе, готовность G1 не объявлена.

| Owner | Record / enum / primitive | Proposed registration | Exact порядок |
|---|---|---|---|
| Shared codec | UUID scalar | TLV tag **10**, не record ID | 16 bytes UUID.bytes |
| Pack | ManifestPinRead | RECORD **20205**, `dataModel/worldPack/encoding/pinBindings.py::PACK_PIN_SCHEMA` | store_id, execution_id, invocation_id, logical_read_key, pin_id, world_uid, max_bytes |
| Source 2 / Source | SourceProofReadInput | RECORD **71201**, `application/worldData/sourceVersioning/encoding/sourceProofRequestSchemaV1.py::SOURCE_PROOF_REQUEST_SCHEMA_V1` | world_uid, proof |
| Snapshot | PreparationSourceOriginKind | ENUM **20308**, `application/publication/encoding/preparationSourceManifest.py::PREPARATION_SOURCE_SCHEMA` | wire value pinned_manifest |
| Snapshot | PinnedManifestSourceOrigin | RECORD **20309**, тот же manifest | kind, pin, manifest |
| Snapshot | PreparationSourceBinding | RECORD **20310**, тот же manifest | target, request, origin, sources |

Snapshot types принадлежат `dataModel/publication/preparationSourceAuthority.py` по r2; Source/Pack types остаются в owning модулях. Все новые числовые IDs здесь PROPOSED. Повторный `rg` по backend/docs/.cursor/plans обнаружил 20205/71201 только в соответствующих proposals/ссылках; 20308–20310 до этой записи не найдены. Это локальная проверка, не глобальное reservation и не runtime merge test.

Source 2 exports `SOURCE_PROOF_REQUEST_ENCODING_V1 = merge_manifests(SOURCE_PROOF_SCHEMA_V1, SOURCE_PROOF_REQUEST_SCHEMA_V1)` в том же новом request module. Snapshot получает именно owning полный export, не копирует Source roster. SOURCE_PROOF_SCHEMA_V1 отдельно по-прежнему не умеет root request; nested proof bytes неизменны.

`PREPARATION_SOURCE_SCHEMA` содержит только три Snapshot entries. Полная composition для PreparationSourceBindingCodec: этот fragment + PACK_PIN_SCHEMA + SOURCE_PROOF_REQUEST_ENCODING_V1 + existing Artifact type entries, необходимые полному annotation tree binding. Exact shared entries повторно используют owners/IDs из ARTIFACT_CORE_SCHEMA, не переобъявляют POJO: SnapshotChainKind=20001, ArtifactKind=20003, OperationKind=20004, ArtifactHolderKind=20006; WorldSnapshotRef=20101, PlayerSnapshotRef=20102, ArtifactRef=20107, OperationLeaseRef=20108, OperationHolder=20110, ArtifactRetentionHolder=20111, SnapshotHolder=20112, VerifiedArtifactRef=20113, PinHolder=20141. Snapshot refs нужны потому, что existing VerifiedArtifactRef.holder аннотирован полным ArtifactHolderRef union; binding validator всё равно отвергает operation/snapshot holder для pinned origins. Это transitive schema completeness, не разрешение нового origin kind.

Не включать entire terminal/error/metadata manifests или Pack surface ради этих entries. Shared entries брать из existing owning manifest по exact python_type с проверкой одного соответствия; все данные manifest immutable. Missing owner/ID/kind conflict — configuration error до writes. Итоговый merge и strict typed round-trip должны быть доказаны на реальных Source types; пока их нет, fake classes запрещены.

### Следующий ограниченный срез после приёмки UUID delta

Первым независимо реализуемым куском может быть native UUID scalar: изменения общего encoder и обоих decoder, синхронизация точного SoT TLV-пункта, адресные canonical/bounded tests и existing bytes regressions. Он не требует Source request/models, SQL или pin registration для primitive tests. Это **предложенный implementation scope**, не уже разрешённая правка SoT: shared tag10 ещё требует адресного review/приёмки. После него — отдельно Pack pin registration с fixed vector; Source request registration только когда Source 2 contract принят и owning real values готовы. Snapshot binding/ledger — после всей composition и storage review, не skeleton с placeholders.

Таким порядком можно двигаться независимо от незавершённого Source, не расширяя его G1 и не выдавая отсутствие Source зависимости за запрет всей дальнейшей работы. Код/SQL в этом документальном проходе не менялись. Следующий review должен отдельно оценить UUID tag/compatibility и эту таблицу, а не повторять уже принятый single-origin выбор.

### Адресный Pack consumer review §4/6/7

2026-11-14: **PASS совместимости предложения с Pack DTO**, новых actionable Pack-boundary findings нет. Подтверждены перенос RECORD20205/PACK_PIN_SCHEMA/exact семи полей, UUID.bytes (не bytes_le/string), длина 16, оба decoder, strict expected type, отсутствие новых version/variant ограничений. Nil/all-ones допустимы как values; namespace authority остаётся pin checks. Primitive tag не занимает record ID.

Неизменность existing ArtifactRef/cache/proof bytes — обязательное regression требование, runtime evidence пока отсутствует. Этот verdict не принимает за пользователя shared tag10/SoT или Snapshot storage composition и не резервирует ID20205. Код/основной Pack план не менялись; прежний Source не затронут.

## 8. Реализация принятого UUID-среза

2026-11-14. Применён implement-plan; прочитаны owning scope, actual codecs и SoT canonical TLV. Новой функциональности в baseline не было: прежний UUID repro завершался unsupported canonical value. Ответ пользователя разрешил tag10 и точную синхронизацию SoT; registration/SQL/Source не входят.

Изменённые файлы:

- `backend/app/encoding/canonicalCodec.py`: native exact UUID → tag10/UUID.bytes, scalar decode ровно 16 bytes → native UUID, ordinary decoder dispatch.
- `backend/app/application/encoding/boundedCanonicalDecode.py`: tag10 проходит existing scalar/type/budget path и общий scalar decoder. Никакого отдельного parser/coercion/legacy fallback.
- `docs/tz_terrain_generation.md`: owning canonical TLV paragraph синхронизирован с принятым tag10, обоими decoder, native type и сохранением old bytes.
- `backend/tests/planning/encoding/test_uuid_codec.py`: пять regression tests — literal endian/vector, nil/all-ones, nested typed UUID tuple/frozenset, malformed widths/truncation/trailing/unknown tag, no coercion, bounded bytes/nodes/depth/items.

Роли/приёмка: CanonicalCodec остаётся pure encoder, scalar decoder проверяет одно dependent wire value, bounded Reader сохраняет preflight/build и лимиты. Ошибки — existing CanonicalEncodingError; новый diagnostic DTO/агрегатор не нужен для одного недекодируемого TLV. Pipeline/CRUD/DAG/междоменный вызов не добавлен. Новые Source/Pack records или IDs не реализованы; чужие dirty изменения сохранены.

Команды из backend (`.venv/Scripts/python.exe`):

1. `-m unittest tests.planning.encoding.test_uuid_codec tests.planning.encoding.test_canonical_codec tests.planning.encoding.comparison.test_wire_compatibility tests.planning.encoding.comparison.test_manifest_assembly tests.snapshotCore.contracts.test_codec` — **29 tests OK**.
2. `-m unittest discover -s tests/planning/encoding -t .` — **19 tests OK** (пересекается с адресным прогоном, не складывать counts).
3. `-c "import tempfile, unittest; from pathlib import Path; tempfile.tempdir=str(Path('tests/.tmp_snapshot_core').resolve()); unittest.main(module=None, argv=['unittest','tests.cache.test_container_v2'])"` — **7 tests OK**; временные файлы направлены в existing tests scratch, не корень проекта.
4. `-m unittest discover -s tests/snapshotCore -t .` — **182 tests, 0 failures, 0 errors, 1 skip**, 158.895s. Skip — symlink privilege unavailable на Windows (`test_blob_backend.py`). Штатный Pyright gate прошёл: positive без diagnostics, negative совпал с 58 EXPECT.

`git diff --check` по изменённым production/SoT файлам — PASS. Diff кода/SoT и полное содержимое нового test файла показаны через tools до отчёта. Literal UUID(int=1) vector совпал с предложением §4. Source proof vectors/runtime не проверяются до owning readiness; Pack cache и существующие wire fixtures дают ограниченное regression evidence, не полную приёмку будущего authority ledger. Коммит не создавался.

Независимое review реализации 2026-11-14: **PASS**, actionable findings нет — [отдельный отчёт](snapshot-uuid-codec-review.md). Агент `/root/uuid_review` проверил diff, SoT, обязательные критерии и независимо повторил адресные **29 tests OK** (1.565s), diff check PASS. Полный snapshotCore/Pack cache/typing не повторял; это evidence implementation-прогона выше. PASS ограничен UUID primitive и обоими decoder, не registrations/ledger/pinned runtime.

## 9. Следующий срез: Pack pin registration

2026-11-14, пользователь поручил «Далее» после UUID implementation PASS. Реализована предъявленная Pack-owned registration `20205`, без изменения DTO, accepted field order, core/Source manifests или SQL. Применён implement-plan; сверены Pack proposal, actual model, owning read contract в tz_world_pack_storage и ID collisions. Shared UUID prerequisite закрыт §8. Полная future ledger composition не объявлена реализованной.

Новые файлы: `backend/app/dataModel/worldPack/encoding/pinBindings.py` — ровно один immutable RegisteredTypeEntry для existing ManifestPinRead; `backend/tests/spatial_pack/test_pin_canonical_registration.py` — четыре tests literal wire/both decoders/field sensitivity/malformed wire/ID-owner collisions. Registration не создаёт authority и не вызывается public pipeline. Публичные CRUD/settings/DAG/порядок S1/S2 не меняются. Codec/DTO copies и legacy adapters отсутствуют; запись type identity — единственная production ответственность файла.

Golden input: store_id=UUID(int=1), execution_id="exec", invocation_id="inv", logical_read_key="base", pin_id="pin", world_uid="world", max_bytes=1024. **339 bytes**, SHA256 `aba1c78650c352504b3af0484341179769e2d82d091d495c2c09b273e96f0b32`. Полные literal bytes находятся в test GOLDEN; вектор предварительно собран отдельным read-only TLV script через byte lengths/int/UTF8/UUID.bytes без production encoder, затем проверен обоими production decoder. Это wire fixture, не authenticated pin fixture.

Адресные команды из backend:

- `.venv/Scripts/python.exe -m unittest tests.spatial_pack.test_pin_canonical_registration tests.planning.encoding.test_uuid_codec tests.snapshotCore.contracts.test_codec` — **22 tests OK**.
- Cache/wire/typing: Python unittest runner для `tests.cache.test_container_v2`, `tests.planning.encoding.comparison.test_wire_compatibility`, `tests.snapshotCore.contracts.test_typing` с `tempfile.tempdir=Path('tests/.tmp_snapshot_core').resolve()` — **10 tests OK**, positive/negative typing прошёл.
- Обычный запуск pin registration + pinned_manifest_reader + pin_binding_replay остановлен после четырёх sync tests без дальнейшего прогресса; успешным не считается. Polling-loop повтор сначала выявил недоступный sandbox TEMP (unable to open database / cleanup PermissionError; 7 tests, 5 errors включая cleanup). Повтор с tests scratch и polling loop также остановлен без результата async tests. Причина оставшегося отсутствия прогресса не установлена; нельзя объявлять его доказанно только environment issue. Production код ради этого не менялся. Async reader/replay regression остаётся **не подтверждённым** в этом проходе.
- После уточнения collision test повторён `.venv/Scripts/python.exe -m unittest tests.spatial_pack.test_pin_canonical_registration` — **4 tests OK**.

Pack owning read-only review двух новых файлов: **PASS статической registration/consumer границы**, actionable defects не найдены. Pack самостоятельно tests не перезапускал; результат исполнителя не выдаётся за независимый прогон. No broad ledger/Source acceptance. Полное содержимое новых файлов показано инструментом; чужие Source/Pack изменения сохранены. Full snapshotCore из §8 после isolated registration повторно не запускался: global manifests/codecs не изменены; новый merge/round-trip проверен адресно.

### Закрытие незавершённого reader/replay regression

2026-11-14, по следующему «Далее»: **3 tests OK, 134.269s** — оба `tests.spatial_pack.test_pinned_manifest_reader` и `tests.spatial_pack.test_pin_binding_replay.test_commit_and_rollback_are_distinguishable_after_reopen`. Предыдущее «не подтверждён» выше сохраняет историю остановленных попыток, актуальный результат этого regression — PASS.

Диагностика `faulthandler.dump_traceback_later(30, repeat=True)` установила существенную задержку в `ExecutionPinFixture.asyncSetUp`, строка 63: синхронный `db.executescript(schema)` для отдельной DAG-базы. Два setup заняли 39.970s и 40.426s; оба reader tests затем прошли, replay/reopen также завершился. Это наблюдение не доказывает конкретную причину медленного дискового IO и не требует изменения production lifecycle/codec. Durability/SQL/schema/test source не менялись. Прежние попытки были остановлены до итогового результата.

Воспроизводимый runner: из backend передать следующий script в `.venv/Scripts/python.exe -` (на PowerShell — here-string). Патч loop только process-local и соответствует existing `tests.snapshotCore.support.fixtures.run_async` polling approach; реальные tasks, aiosqlite worker threads и SQLite сохраняются. TEMP размещён в tests scratch. Это evidence этих сценариев на ограниченном host, не проверка стандартного Windows network event-loop backend.

```python
import asyncio, selectors, time, unittest, tempfile, faulthandler
from pathlib import Path
from unittest.mock import patch
from tests.spatial_pack.test_execution_pins import ExecutionPinFixture
from tests.spatial_pack.test_pin_binding_replay import PinBindingReplayTests

tempfile.tempdir = str(Path('tests/.tmp_snapshot_core').resolve())
def no_pipe(loop):
    loop._ssock = loop._csock = None
def factory():
    selector = selectors.SelectSelector()
    selector.select = lambda timeout=None: (
        time.sleep(min(.002, timeout) if timeout is not None else .002), []
    )[1]
    return asyncio.SelectorEventLoop(selector)
ExecutionPinFixture.loop_factory = staticmethod(factory)
PinBindingReplayTests.loop_factory = staticmethod(factory)
faulthandler.dump_traceback_later(30, repeat=True)
try:
    with patch.object(asyncio.SelectorEventLoop, '_make_self_pipe', no_pipe), patch.object(
        asyncio.SelectorEventLoop, '_close_self_pipe', lambda loop: None
    ):
        unittest.main(module=None, argv=['unittest', '-v',
            'tests.spatial_pack.test_pinned_manifest_reader',
            'tests.spatial_pack.test_pin_binding_replay'])
finally:
    faulthandler.cancel_dump_traceback_later()
```

Изменение этого прохода — только evidence в owning-плане; production/test source, Source/Pack чужие изменения и следующий ledger scope не затронуты. Следующая зависимость — отдельная Source request registration/composition, без возврата к уже закрытому UUID вопросу.

## 10. Readiness Source request registration после pin regression

2026-11-14, пользователь поручил «Делай» следующий срез через Source 2. Проверка actual tree: `sourceProofInput.py` содержит только SourceProofInput(world_uid, uses); `rg` по backend/app не нашёл class SourceProofReadInput. `Test-Path backend/app/application/worldData/sourceVersioning/encoding/sourceProofSchemaV1.py` вернул False; directory application/worldData/sourceVersioning отсутствует. Source values существуют частично и имеют чужие незавершённые изменения.

Нельзя реализовать `SOURCE_PROOF_REQUEST_SCHEMA_V1` с exact owner SourceProofReadInput и `SOURCE_PROOF_REQUEST_ENCODING_V1 = merge_manifests(SOURCE_PROOF_SCHEMA_V1, ...)`, пока оба imports отсутствуют. Замена на SourceProofInput неверна: uses вместо proof и другая семантика normalization/read. Lazy import, string type name, placeholder и копия proof roster не закрывают контракт.

Owning Source G1 §7 разрешает текущий узкий POJO-срез для Pack 3a, но явно исключает отдельные read requests и encoding. Его не расширять из Snapshot. Source 2 получил адресный запрос актуального readiness/точных imports и обновления собственного отдельного proposal, без обращения к прежнему Source и без правок его кода/spec/G1. Дальнейшая зависимая реализация registration и binding ledger приостановлена до поставки настоящего request и proof manifest владельцем. UUID/Pack registration уже реализованы и этим gate не отменяются.

Source 2 независимо подтвердил **NOT READY** и актуализировал [свой proposal, §1](source-2-snapshot-request-encoding-proposal.md): exact imports отсутствуют, альтернативных exports нет. Для продолжения нужны реальные SourceProofReadInput(world_uid, proof) и полный SOURCE_PROOF_SCHEMA_V1 с подтверждёнными V0/V1 bytes/round-trip. Это dependency gate, не нехватка прав на запись и не запрос повторного разрешения registration. Новый модуль и tests сейчас не создавались, чтобы не поставлять неразрешимые imports. После поставки зависимостей сохраняется узкий scope: request manifest + composition tests, без G1/legacy/Source IO расширений.
