# Pinned origin: storage и canonical encoding

2026-11-14. **PROPOSED / BLOCKED ON OWNER ENCODING DECISIONS**, не разрешение runtime-кода. Следующий design-срез после принятого single-origin/historical persistence и независимого PASS [pinned r2](snapshot-pinned-origin-contract-r1.md). Scope: конкретизировать existing operation ledger extension и canonical представление уже согласованного binding. Source S1/S2/adopt, G4/finalizer, DAG и crash input не расширяются.

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
