# Source 2: encoding SourceProofReadInput для Snapshot ledger

2026-11-14. **Registration-срез реализован и самостоятельно проверен; независимая приёмка остаётся отдельной.** Разрешение ID71201/composition и реализации передано Snapshot после пользовательских «Делай»/«далее»; owning G1 §7/§9 разрешает отдельную registration после foundation. Актуальная поставка — §6. Ниже сохранена история proposal/readiness; прежние NOT READY/ожидание согласования заменены §6. Source spec/G1 и durable runtime этим срезом не изменяются. Общий UUID encoding ManifestPinRead вне scope.

## 1. Baseline и граница решения

### Повторная проверка после появления foundation, 2026-11-14

**Imports доступны, но подтверждённая поставка G1.1/G1.2 пока не предъявлена; registration не начинать.** Этот verdict заменяет предыдущий NOT READY по отсутствующим imports. G1-BIND согласно актуальному owning G1-плану §7 больше не prerequisite request encoding; его закрытия здесь не требуем.

Прочитаны настоящие sourceProofInput.py и application/worldData/sourceVersioning/encoding/sourceProofSchemaV1.py. SourceProofReadInput теперь объявлен по authoritative path с обязательными world_uid/proof, наследует SourceValue и проверяет совпадение миров. Manifest содержит полный roster из 21 entry: 20003/20107, 71001, 71110–71114, 71120–71131, 71138; ID/owner/kind по декларациям соответствуют §11.4. Request/results/errors туда не включены. Это снимает прежние два import blocker, но само по себе не является приёмкой.

Read-only запуск `.venv/Scripts/python.exe -B -m unittest discover -s tests/sourceVersioning -p 'test_*.py'` из backend: **27 tests OK** (test_values.py и test_foundation.py). Foundation проверяет read request/world/required fields, capture graph, diagnostics и nested revalidation; JSON round-trip в этих tests не заменяет canonical round-trip. Отдельный smoke на реальных imports: 21 entries; V0 160 bytes, digest 753fac72650941d0eb1708e8ae777e2de3bd59c0b8e4278d50dd75cd040267a3; canonical decode равен proof; request fields ровно world_uid/proof.

На момент чтения test_canonical.py отсутствует в tests/sourceVersioning; literal V0/V1 hashes найдены в spec, а не в Source tests. Полный canonical round-trip roster, V1, collision/owner/field-order/noncanonical negatives и regression evidence G1.2 пока не предъявлены. Typing valid.py уже импортирует новые types/manifest, но наличие imports не доказывает успешный positive/expected-negative Pyright прогон. Owning G1 §8 пока описывает историческую поставку 20 tests и старые отсутствующие request/schema, а не завершение новой foundation; нового акта поставки G1.1/G1.2 в прочитанном плане нет.

Остаток: владелец завершает G1.2 canonical tests и фиксирует V0/V1/full-roster round-trip/negative/collision/regression результаты, актуальные positive/negative typing и статус поставки G1.1/G1.2. После этого проверить evidence и актуальные identities, затем отдельный 71201 registration/composition/tests. Не требовать G1.3 или production G1-BIND для этого шага и не считать чужое меняющееся дерево стабильной принятой поставкой. Этот проход не заменяет независимую приёмку foundation. Source код/spec/G1 и прежний чат не изменены; обновлён только данный proposal.

### Актуальный readiness после поручения «Делай», 2026-11-14

**NOT READY для отдельного registration module + tests: две обязательные runtime dependencies отсутствуют.** Исторические сведения ниже об отсутствии всех Source directories относятся к первому чтению. Разрешение следующего шага не позволяет создавать отсутствующие G1 модели или менять чужой Source код.

Read-only rg по backend и чтение реальных файлов установили:

| Dependency / authoritative import | Фактическое состояние |
|---|---|
| app.dataModel.sourceVersioning.sourceProofInput.SourceProofReadInput | Путь подтверждён spec §6.A/§10.3 и G1 §3. Файл существует, но объявляет только SourceProofInput(world_uid, uses). SourceProofReadInput и альтернативное объявление/экспорт в backend не найдены. SourceProofInput не заменяет read request. |
| app.dataModel.sourceVersioning.sourceDurableProof.SourceDurableProof | Реальный класс существует: schema_version: Literal[1], world_uid: EntityUid, uses: tuple[SourceCaptureUsage, ...], exact-int version check. Это не доказательство готовности полного G1. |
| app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1.SOURCE_PROOF_SCHEMA_V1 | Authoritative path подтверждён spec §11.4 и G1 §4. Application directory отсутствует (Test-Path=False); export не найден rg в backend. |
| app.dataModel.worldPack.encoding.pinBindings.PACK_PIN_SCHEMA | Реальный manifest существует: ManifestPinRead RECORD 20205. |
| Shared canonical UUID | В canonicalCodec.py найдены native UUID encoder и tag10 decoder. Это наличие кода, не повторная приёмка тестов Snapshot. |

Точное условие возобновления: owning Source поставляет настоящий SourceProofReadInput по указанному пути с полями world_uid/proof и настоящий immutable SOURCE_PROOF_SCHEMA_V1 с полным accepted transitive roster. Нужны подтверждённые imports, прежние V0/V1 bytes/round-trip и готовность owning prerequisites по утверждённому порядку. Existing SourceValue/SourceDurableProof/sourceProofInput содержат OPEN TODO SOURCE-TYPED-ERRORS; их закрытие и G1-BIND не входят в эту задачу. Чужие незавершённые edits не исправлять и не считать принятыми.

После появления dependencies узкий результат — только новый sourceProofRequestSchemaV1.py (§2) и адресные registration/composition tests (§4), с повторной проверкой ID71201 и реальных owner identities. Сейчас модуль имел бы неразрешимые imports; fake classes, lazy fallback, локальная копия proof manifest и новый request class запрещены. Поиск 71201 в backend/app совпадений не дал. Runtime registration/tests не создавались. Причина — отсутствующие dependencies, не filesystem permissions и не необходимость повторного разрешения пользователя.

UUID и Pack registration больше не являются открытыми prerequisite этой Source-задачи; прежний список ниже исторический. Snapshot binding/ledger и весь G1 этим readiness не принимаются. Source spec/G1/runtime/прежний чат не изменены; актуализирован только этот proposal.

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

## 6. Поставка отдельной registration, 2026-11-14

Предыдущий §5 — исторический verdict. Foundation prerequisites повторно проверены: owning G1 §9 фиксирует declarations/encoding evidence, до правки повторён Source discover — 34 tests OK. Полный 21-entry proof roster и настоящие request/proof types доступны. Повторный поиск 71201 в backend/docs/plans перед правкой нашёл только согласованные proposals/ссылки, не существующую code registration. G1-BIND не prerequisite по актуальному §7 G1; semantic layer остаётся открытым.

Добавлены только:

- `backend/app/application/worldData/sourceVersioning/encoding/sourceProofRequestSchemaV1.py`: immutable SOURCE_PROOF_REQUEST_SCHEMA_V1, ровно RECORD 71201 → существующий SourceProofReadInput; SOURCE_PROOF_REQUEST_ENCODING_V1 = merge_manifests(SOURCE_PROOF_SCHEMA_V1, SOURCE_PROOF_REQUEST_SCHEMA_V1). Никаких новых моделей/codec/IO/authority.
- `backend/tests/sourceVersioning/test_request_canonical.py`: 6 адресных tests, реальные values; owning foundation tests переиспользуются только как fixtures, без правок.

Literal request V0: 269 bytes, SHA-256 `7c1637a9909f400dbfa18c6d364ae232ac277705a56854997e17fdf7615dcfec`. Golden построен независимой ручной TLV assembly (длины, tag7, ID71201, пары world_uid/proof) и literal accepted proof V0, без вызова production encoder; literal prefix + V0_HEX закреплён в тесте. Verified empty/nonempty/historical round-trip, exact owner/field order, unchanged V0/V1 proof bytes/fingerprints, enclosing Artifact/Snapshot/Pack merge и manifest-order independence. Проверены missing fragment dependencies, proof-only request refusal, unknown ID/field, wrong root/order/version, truncation/trailing bytes, forged world/missing proof/bool version и ID/owner/kind collisions. Decode не доказывает admission; descriptor-aware semantics здесь не добавляются.

Выполнено после правки:

1. Из backend `.venv/Scripts/python.exe -B -m unittest discover -s tests/sourceVersioning -p 'test_*.py'` — **40 tests OK**.
2. Из backend `.venv/Scripts/python.exe -B -m unittest tests.planning.encoding.test_canonical_codec tests.planning.encoding.test_uuid_codec` — **13 tests OK**.
3. Из корня `node node_modules/pyright/index.js -p backend/tests/typing/sourceVersioning/pyrightconfig.valid.json` — **0 errors**; existing include охватывает новый production encoding module.
4. Corresponding pyrightconfig.invalid.json — **ровно 5 ожидаемых diagnostics**, exit1: object/collection refs, collection вне object union, foreign RegistryKey brand, list вместо tuple, frozen seq assignment.

Изменён также только этот proposal для evidence. Foundation/spec/G1, Pack, shared codec, Snapshot ledger/SQL и прежний Source чат не менялись. Ответственности/CRUD/DAG границы §3 сохранены, утверждённый порядок foundation → registration соблюдён. Это самостоятельная проверка narrow encoding delivery, не приёмка всего G1, semantic admission, Snapshot binding/ledger или durable runtime; следующая граница — независимый review и Snapshot integration по его плану.
