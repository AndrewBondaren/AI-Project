# Snapshot public methods — предложение для согласования перед DAG

## Приоритетная дельта 2026-11-24: согласованный admission transport и owning детализация

### Реализация ограниченного admission-среза — 2026-11-24

**Consumer enum cutover, 2026-11-24:** Snapshot потребляет `PatchSetStructuralFailure.error_type: PatchSetStructuralErrorKind` из owning structuralErrorKind.py. Fixtures создают enum members; dispatch использует `is PatchSetStructuralErrorKind.ENUM`. Только `SnapshotPublicInputValidation.map_structural` переводит `.value` через existing Pydantic `TypeAdapter[ErrorType]` на presentation boundary. Второго enum/allowlist/raw-string fallback нет; несовместимость presentation сохраняет ValidationError cause как infrastructure fault. Проверены весь owning roster, raw-string bypass negatives, unknown classification, root loc и mixed JSON. `test_snapshot_admission + test_patch_admission + test_tagged_paths`: **25 tests OK** на shared 2.13.4 и отдельно на pinned 2.14.2 (import path/version подтверждены); scoped Snapshot Pyright **0 errors**. Тяжёлая full regression повторно не запускалась. Изменены только consumer mapper/tests и эта статусная запись; PatchSet owning predicates/классы не дублируются.

Приоритет над историческим статусом shared-only ниже: Snapshot fault, mapper, validator, constructor identity и внутренний claim seam реализованы. Actual PatchSet exports потребляются напрямую; public invariant facts синхронизированы владельцем в tz_patch_system.md. Это локальная реализация admission → fingerprint → existing claim, не готовность полного public apply/ARCH-0.

| Actual класс/метод | Единственная ответственность и проверка границы |
|---|---|
| SnapshotPublicInputValidation.map_structural(PatchSetStructuralFailure, *, model) | Представление уже классифицированного root-relative loc через общий field_issue/CheckedPath; не реконструирует ValidationError и не запускает model validation запроса |
| SnapshotRequestValidator.validate(request) | Owning codec.validate_request → ordered mapping → owning check_prepared_order; без hash/IO/claim и копий predicates |
| SnapshotPublicFault / SnapshotPublicError | Closed immutable transport, exact concrete diagnostics, mixed order и обе admission identities None; direct reuse четырёх PatchSet compatibility facts |
| WorldSnapshotService._admit_and_claim(request) | Validator → request_codec.fingerprint → прежний _claim_publication; narrow classification catch, отдельный fingerprint catch с cause; не создаёт partial public apply |
| WorldSnapshotService.__init__(..., request_codec=...) | Один codec и identity его registry; model/registration configuration остаётся у PatchSetCodec; прежние H2 checks сохранены |
| CheckedPath / existing wireIssues.field_issue | Единственный schema resolver сохраняет discriminator metadata/VariantSegment и original loc; unknown/ambiguous не выбирает branch, extra key остаётся wire shape |
| FieldPathError.__get_pydantic_core_schema__ | Carrier wrapping только bare/parameterized schemas; named concrete использует native JSON schema. __new__, exact CodeT/subtype admission и revalidation собственных полей сохранены |

Shared JSON reproduction: strict tuple + native concrete JSON проходит; pass-through wrap `handler(value)` на concrete даёт tuple_type при JSON validation, отдельно __new__ дефект не воспроизводит. Исправление не вводит strict=False, mirror, decoder или list→tuple preprocessor. Snapshot public roster дополнительно проверяет exact Python instances через Python-only schema guard; штатная JSON ветка сохраняет arrays→tuples semantics. Проверены direct/nested JsonFieldError, typed path/indices/wire_path, concrete enum/class, generic specialization и повторный model_rebuild; Python lists, foreign code/subclass и bare carrier dict/JSON отвергаются.

Existing post-admission private-stage fixtures используют явно названный mock_request_codec: validate_request/fingerprint немедленно падают при случайном вызове. Это не admission evidence. Новые admission tests используют настоящий зарегистрированный PatchSetCodec + named FakePatchSet; существующий claim подменён явно обозначенным boundary mock. Lifecycle fixture использует реальный codec с полным roster MockPatchSet. Полный production orchestrator не заявлен.

Проверки этого прохода: C0 + Lifecycle validation — 54 tests OK; Snapshot admission/model/C0 targeted — 67 tests OK; scoped Snapshot Pyright — 0 errors. Итоговый `python -B -m unittest discover -s tests/snapshotCore -t .` — 257 tests, OK (skipped=1), 155.976s: 256 пройдено, Windows symlink privilege test пропущен. Ранее полученный единственный failure pure validation import whitelist исправлен добавлением `pydantic_core`; запрет application/IO/storage imports сохранён. Diff кода/fixtures просмотрен; diff --check чистый.

**Pinned regression закрыта 2026-11-24:** отдельно установлены Pydantic 2.14.2 / pydantic-core 2.50.2 и их зависимости через `pip install --target` в `C:/Users/andrb/AppData/Local/Temp/snapshot-pydantic-2142-6fedf41680794304a7b2111d877148a5`. Runtime версии и пути импорта проверены в том же процессе перед unittest. Целевые C0 JSON/carrier/subtype/rebuild negatives, Snapshot fault roundtrip и Snapshot/PatchSet admission: **64 tests OK**, 0.045s. Shared backend/.venv после проверки сохранил Pydantic 2.13.4 / core 2.46.4; requirements/pins не менялись. Это изолированный dependency overlay на существующем Python, не полная пересборка requirements и не повтор всей тяжёлой регрессии.

Воспроизводимый targeted run из backend (PYTHONPATH устанавливается только для отдельного shell-процесса):

```powershell
$env:PYTHONPATH = 'C:\Users\andrb\AppData\Local\Temp\snapshot-pydantic-2142-6fedf41680794304a7b2111d877148a5'
.venv/Scripts/python.exe -B -m unittest tests.errorContracts.test_core tests.errorContracts.test_import_issues tests.errorContracts.test_model_identity tests.errorContracts.test_resolve_issues tests.errorContracts.test_tagged_paths tests.snapshotCore.contracts.test_snapshot_admission tests.snapshotCore.contracts.test_patch_admission
```

Остатки OUT: полный apply/transaction composition, production/DAG caller, общий runtime/ARCH-0. Ни IO-вход, ни DAG порядок, ни C2/H2/H3 semantics этим срезом не менялись.

**Shared C0 implementation, 2026-11-24:** назначенная Snapshot узкая поправка исполнена в checkedPath.py / jsonValidation/resolution/wireIssues.py. Перед записью список активных чатов и git status целевых файлов не показали конкурирующего C0 исполнителя/правок. Сохраняется discriminator metadata, unknown/ambiguous branch не выбирается, extra-key остаётся WireShapeIssue с rendered address без распознанных branch labels; исходный loc не меняется. Проверены nested section, два union уровня, aliases, tuple element, RootModel, extra key с именем tag, unknown/ambiguous tags и class-name ambiguity. Команда `python -B -m unittest tests.errorContracts.test_tagged_paths tests.errorContracts.test_core tests.errorContracts.test_model_identity tests.errorContracts.test_import_issues tests.errorContracts.test_resolve_issues tests.errorContracts.test_typing tests.snapshotCore.contracts.test_patch_assembly`: 54 tests OK, включая positive/negative typing. Diff просмотрен, diff --check чистый. Это локальная проверка shared зависимости, не admission/runtime/ARCH-0 PASS. PatchSet actual exports и нормативный public export появились в ходе работы владельца; Snapshot fault/mapper/validator/constructor/claim seam ещё не реализованы этим shared срезом.

Этот раздел и обновлённый §3 задают единственную текущую public fault schema для owning детализации. Решение admission→claim согласовано пользователем по уточнению второго координатора; оно не возвращается в общий PROPOSED. Предыдущий shape-only roster заменён. Конкретные Output→Input и нормативная синхронизация завершаются владельцами, без нового пользовательского выбора внутренних имён. Runtime PASS не заявляется. Основание: [admission→claim](snapshot-apply-admission-claim.md). H2/C2 и durable outcomes не меняются. Public export `PatchSetInvariantViolation` требует owning нормативной синхронизации PatchSet (прочитанное ТЗ пока говорит Internal).

### Точный roster и обязательные validators

Один carrier `application/worldSnapshot/errors.py::SnapshotPublicError(fault: SnapshotPublicFault)`. Один record `dataModel/worldSnapshot/errors/publicFault.py::SnapshotPublicFault`:

```python
operation: SnapshotPublicOperation
kind: SnapshotPublicFailureKind
operation_id: EntityUid | None
request_fingerprint: RevisionHex | None
input_issues: tuple[JsonFieldError | WireShapeIssue |
                   PatchSetInvariantViolation | PatchSetRequestVersionUnsupported |
                   PatchSetSectionKeyUnknown | PatchSetSectionModelMismatch |
                   PatchSetSectionVersionUnsupported, ...]
```

Все поля обязательны, без defaults; strict/frozen/extra-forbid/revalidate-always. Existing proposed operation values `apply`, `read_snapshot`, `read_publication` сохраняются. Failure values: `invalid_input`, **`admission_refused`**, `busy`, `infrastructure_failure`, `outcome_unknown`.

- INVALID_INPUT: непустой tuple только exact JsonFieldError/WireShapeIssue; обе identity строго None.
- ADMISSION_REFUSED: только APPLY; непустой mixed closed tuple указанного roster, минимум один exact PatchSetInvariantViolation либо один из четырёх owning compatibility facts; обе identity строго None.
- BUSY / INFRASTRUCTURE_FAILURE / OUTCOME_UNKNOWN: input_issues=(); прежняя фазовая identity policy сохраняется: оба binding-поля одновременно None либо одновременно non-null. Reads всегда без binding; BUSY/OUTCOME_UNKNOWN только APPLY с binding. Ошибка fingerprint до получения hash — INFRASTRUCTURE_FAILURE с обоими None.
- Запрет частичного binding (только operation_id либо только fingerprint), неизвестных issue subclasses и неизвестных diagnostic kinds. SnapshotApplyRelationIssue в admission roster **не входит**: он не различает registry reasons и не содержит section_index; existing business result roster не меняется.
- Mixed reasons не группируются: relative producer order и все повторные/независимые diagnostics сохраняются. Наличие relation выбирает ADMISSION_REFUSED, иначе INVALID_INPUT. Нет claim/record_refusal для обоих admission kinds.

### Compatibility diagnostics: direct reuse owning facts

Четыре предложенных ранее Snapshot details и SnapshotAdmissionCompatibilityIssue **отозваны до реализации как ненужные зеркала**. Модуль admissionCompatibility.py не создаётся. Препятствий для direct reuse четырёх immutable PatchSet facts не найдено: все operands уже сериализуемы, Python classes/exceptions отсутствуют, section_index сохраняется. В closed public roster включаются exact классы PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown, PatchSetSectionModelMismatch, PatchSetSectionVersionUnsupported из owning admissionReasons.py.

Новые Snapshot reason codes не вводятся. Последняя owning редакция PatchSet задаёт обязательные Literal codes `patch_set.admission.request_version_unsupported`, `patch_set.admission.section_key_unknown`, `patch_set.admission.section_model_mismatch`, `patch_set.admission.section_version_unsupported` и plain union PatchSetCompatibilityIssue. Snapshot включает этот union с discriminated annotation по code, без wrapper/details и без второго enum; JSON round-trip проверяет exact branches.

Existing ModelIdentity и actual_type_name переносятся напрямую. Последнее — inert diagnostic string, не dispatch/identity. По последней owning редакции supported_versions уже tuple[FormatVersion,...], nonempty/unique/ascending; producer формирует его из registry frozenset. Snapshot не сортирует и не меняет тип, не создаёт свой serializer или зеркало. JSON round-trip сохраняет owning tuple и code.

### Полная reason → public mapping (требования потребителя к PatchSet)

Owning источник прочитан полностью: [patch-set-admission-output.md](patch-set-admission-output.md). Ниже exact объявленные владельцем classes из `dataModel/patch/validation/admissionReasons.py`, плюс existing invariant facts; exception — `application/patch/errors.py::PatchSetAdmissionError`. Это подтверждение документального Output, не наличия runtime exports. Snapshot не создаёт substitutes.

| Runtime concrete reason / operands | Public diagnostic / exact mapping |
|---|---|
| PatchSetRequestModelMismatch(expected_model:ModelIdentity, actual_type_name:StrictStr) | WireShapeIssue(code=JsonValidationCode.VALIDATION_ERROR, location=WireLocation(parts=()), message="request must have the configured concrete model", pydantic_type=None). Wrong exact class не выдаётся за ошибку объявленного поля; identity/type operands не сериализуются в shape message. Их diagnostic projection здесь намеренно root-level |
| PatchSetRequestVersionUnsupported(actual_version, supported_versions) | Тот же exact immutable reason в public tuple; оба operands без изменения |
| PatchSetSectionKeyUnknown(section_index, section_key) | Тот же exact reason; исходные index/key без изменения |
| PatchSetSectionModelMismatch(section_index, section_key, expected_model:ModelIdentity, actual_type_name:StrictStr) | Тот же exact reason со всеми четырьмя operands, без ModelIdentity.of/повторной проверки exact model |
| PatchSetSectionVersionUnsupported(section_index, section_key, actual_version, supported_versions) | Тот же exact reason; исходные index/key/version/tuple и code без изменения |
| PatchSetStructuralFailure(error_type:StrictStr, loc:tuple[StrictStr|StrictInt,...], message:StrictStr) | map_structural(fact, model=codec.request_model); result вставляется на место fact, без переноса через relations. loc должен быть относительно корневого request с исходными section/patch indices; не локальный loc секции без prefix |
| PatchSetInvariantViolation(details, section_index, patch_index, dependency_index, player_index, related_index) | Тот же immutable concrete fact без обёртки/переименования/потери nullable indices; публичный export должен быть принят PatchSet |
| check_prepared_order(checked) → tuple[PatchSetInvariantViolation,...] | Каждый факт сохраняется напрямую в порядке producer; predicate вызывается только после успешного validate_request, до hash |
| Необъявленный reason / неизвестный ctx.error / mapper contract violation | Infrastructure/contract failure с cause; не частичный admission result и не классификация по тексту |

Core facts имеют девять exact details branches, сохраняемых без изменения: WorldMismatchDetails (expected_world_uid/actual_world_uid), MissingPackDetails (publication), DuplicatePlayerDetails (player_uid), DuplicateSectionDetails (section_key), MissingPreparedDependencyDetails (source_section_key/missing_section_key), PreparedDependencyOrderDetails (source_section_key/dependency_section_key), PatchOperationMismatchDetails (patch_ref/expected_operation_id), PatchSectionMismatchDetails (patch_ref/expected_section_key), DuplicatePatchOrdinalDetails (section_key/ordinal). Code Literals и поля берутся из owning invariantDetails.py, не копируются в Snapshot.

### Structural-only facts: единственный mapper и точная consumer boundary

```python
SnapshotPublicInputValidation.map_structural(
    fact: PatchSetStructuralFailure, *, model: type[BaseModel],
) -> tuple[JsonFieldError | WireShapeIssue, ...]
```

Этот контракт **заменяет**, а не дополняет прежний mapper с ValidationError/entry_indices и reconstruction. PatchSet один раз классифицирует source.errors в original order. Typed core ctx.error раскрывается в owning facts на своём месте; неизвестный ctx.error даёт PatchSetValidationClassificationError, а не partial admission refusal. Каждый confirmed structural entry даёт один immutable fact на своём месте. Snapshot не повторяет allowlist classification. Нельзя обещать after-validator facts при неуспешных structural prerequisites.

Минимальные consumer requirements подтверждены owning PatchSet: fact.error_type — подтверждённый builtin ErrorType; fact.loc — исходный root-request-relative loc в исходном порядке, с section/patch indices и union labels без потери; fact.message — безопасное owning structural message без input repr/exception payload. Единственный источник — непосредственная codec.request_model.model_validate. Prefix не добавляется НИ РАЗУ. Модель mapper — exact codec.request_model. После успешной root validation локальный ValidationError registry/section revalidation — infrastructure/contract fault с cause, не новый structural reason. Snapshot не вызывает mapper для такого исключения и не восстанавливает отсутствующий outer scope.

Reuse presentation: existing `field_issue` / CheckedPath из `application/jsonValidation/resolution/wireIssues.py`; не `pydantic_issues`, который требует полного ValidationError. Для enum сохраняется existing UNKNOWN_ENUM с pydantic_type=None; остальные confirmed builtin types дают SCHEMA_VIOLATION с exact ErrorType. Existing message policy enum prefix сохраняется. Root/unknown declared key используют WireShapeIssue, известное объявленное поле — JsonFieldError. Никакой reconstruction ValidationError, resolve_model/import facade/log sink и повторной model validation. Один fact должен дать один diagnostic; tuple API сохраняется для единого consumer контракта. Unknown code/неразрешимая служебная loc-семантика — contract fault, не фиктивный WireLocation.

Проверенный consumer defect существующего helper (read-only probe 2026-11-24): `payload: Annotated[Cat|Dog, Field(discriminator='kind')]`, Cat.kind=Literal['cat'], Cat.age:int; input payload={kind:'cat',age:'bad'} даёт loc=('payload','cat','age'). Existing pydantic_issues/CheckedPath выдаёт WireShapeIssue location=['payload','cat','age'], хотя cat — branch tag, а age — declared field. Нельзя объявлять этот output корректным public address. Для этого примера **новое поле producer не требуется**: model содержит discriminator/branch schema. Consumer должен разрешить tag через declared schema, сохранить VariantSegment и исключить tag из wire_path. Исправление должно переиспользовать/дополнить owning checked-path resolver, а не вводить второй набор path predicates в Snapshot. Unknown/ambiguous branch нельзя угадывать. Полное покрытие допустимых loc остаётся конкретным тестовым seam, не основанием менять принятое admission решение.

Cause сохраняется по цепочке SnapshotPublicError → PatchSetAdmissionError → исходный ValidationError. Для standalone prepared-order source exception отсутствует; fabricated ValidationError не создаётся. В fault нет ValidationError, Python classes, input/ctx/error objects. Structural fact + exact root model достаточны для приведённого discriminated-union case; безопасность message и остальные loc branches подтверждаются regression при реализации, не предположением о generic fallback.

### JSON и acceptance этой дельты

### Nested section + discriminated union: точный consumer example

Synthetic named schema: MockRequest.sections:tuple[MockSection,...]; MockSection.payload:Annotated[Cat|Dog,Field(discriminator='kind')]; Cat.kind:Literal['cat']; Cat.age:int. Секция имеет исходный index=2. PatchSet передаёт PatchSetStructuralFailure(error_type='int_type', loc=('sections',2,'payload','cat','age'), message='Input should be a valid integer'). Mapper получает model=MockRequest.

Ожидаемый JsonFieldError: code=SCHEMA_VIOLATION, pydantic_type='int_type', location=WireLocation(parts=()), wire_path=('sections',2,'payload','age'). Typed path.root=ModelIdentity.of(MockRequest); segments: FieldSegment(owner=MockRequest,name='sections') → IndexSegment(2) → FieldSegment(owner=MockSection,name='payload') → VariantSegment(branch=ModelIdentity.of(Cat)) → FieldSegment(owner=Cat,name='age'). Model names в этой записи означают соответствующие ModelIdentity, не Python classes внутри DTO. path.projection()=('sections',2,'payload','age'). Tag 'cat' не становится полем/ключом и не попадает в wire_path; index 2 не перенумеровывается.

Только root request revalidation создаёт этот fact; prefix не добавляется ни producer, ни consumer. Отдельная section revalidation с local loc=('payload','cat','age') после root success даёт infrastructure/contract fault, не shape fact с придуманным prefix. Внешний union sections:tuple[MockSectionA|MockSectionB,...] дополнительно сохраняет original Pydantic branch label в loc и второй VariantSegment в typed path; оба branch labels исключаются из wire_path, индекс остаётся исходным.

Negative criteria: двойной prefix; потерянный section index; branch tag в wire_path; фиктивный FieldSegment('cat'); plain WireShapeIssue вместо declared age field; неизвестный/неоднозначный tag угадывается по первому union member. Для реального extra key WireShapeIssue допустим, но его location не должен содержать служебные branch labels; это отдельная проверка boundary presentation, не основание invent field path.

### Узкая shared dependency: checked-path resolver

Owning слой — общее error-contracts ядро `dataModel/fields`, не Snapshot/PatchSet. Применимый план [error-contracts-1.md](error-contracts-1.md) §3.9 C0-4/C0-8 и VARIANT-1. Exact module/class/method: `backend/app/dataModel/fields/checkedPath.py::CheckedPath.from_pydantic_loc(root, loc) -> ValidatedFieldPath | None`, внутренний `_resolve_loc`. Presentation consumer — `backend/app/application/jsonValidation/resolution/wireIssues.py::field_issue` (уже использует resolver и исключает VariantSegment из wire_path).

Минимальное изменение shared owner: сохранить доступ к discriminator metadata из FieldInfo/Annotated при продвижении schema cursor; при union step сопоставить loc tag с единственной ветвью по объявленному string discriminator и её Literal values. Выдать existing VariantSegment(branch=ModelIdentity.of(branch)), затем продолжить исходный loc. Не сканировать любые Literal поля в поисках совпадения; не вызывать user discriminator callback и не выбирать первую из неоднозначных ветвей. Сохранить plain union class-name resolution с проверкой единственности, aliases, nullable, tuple/map checks и существующую None boundary для unsupported/ambiguous path. Public signature, VariantSegment wire schema и ручной field/item/key/variant API не меняются. Snapshot не хранит свою таблицу tag→class и не копирует `_resolve_loc`.

Для известных declared paths текущего example изменение `field_issue` не требуется: существующий zip с VariantSegment уже исключает branch label. Extra-key под tagged union требует отдельного точного результата shared boundary normalization, прежде чем обещать корректный WireShapeIssue для этого случая; `None` от resolver само по себе не разрешает сериализовать raw service labels как wire address. Callable discriminator/general path redesign вне этой минимальной поправки; если такие loc реально входят в admission schema, предъявляется конкретный additional case, а не silent fallback.

Regression consumers: `backend/tests/errorContracts/test_core.py` (existing from_pydantic_loc/plain union/aliases/tuple/map плюс nested discriminator и ambiguous tag), `test_model_identity.py` (named concrete branches), `test_import_issues.py` и `test_resolve_issues.py` (JsonFieldError/WireShapeIssue address и wire projection). Сохранить typing gates общего CheckedPath из error-contracts плана; после изменения shared core проверить PatchSet assembly paths и Snapshot mapper на том же nested fixture. В этом документальном проходе эти regression tests не запускались. Назначение исполнителя shared owner остаётся координатору; отдельный чат/новый resolver не создаётся.

`SnapshotPublicFault.model_dump(mode='json')` и `model_validate_json` должны round-trip mixed tuple с сохранением exact issue/details classes, порядка и всех индексов. Compatibility branches — exact owning records без wrappers, invariant details сохраняют owning discriminator. Никакого Any/SerializeAsAny/base-only поля, отбрасывающего concrete fields; никаких wire IDs/ledger manifests этим неперсистентным transport не назначается.

Обязательные cases: все 9 invariant details branches + 4 compatibility branches + оба shape types; relations-shape-relations; root/extra/union branch paths и section prefix; exact JSON concrete types; admission identity populated запрещён (включая оба populated); pure shape с ADMISSION_REFUSED запрещён; relation с INVALID_INPUT запрещён; пустые issues запрещены. Unknown section/model/version одного section_index различимы concrete type после JSON round-trip и сохраняют operands. Проверить отсутствие hash/claim/record_refusal после fault. Model validator с неизвестным ValueError не проходит structural mapper. Public schema изменения не считаются принятыми по одному зелёному тесту.

**2026-11-15, ARCH-0:** актуальная карта и ограничения — ARCH-0.1–ARCH-0.6 [owning-плана](world-domain-patches-snapshots.md). Read/write signatures ниже сохраняются как proposal; утверждение об одном concrete public owner ниже не является завершённым архитектурным решением. Предъявлено разделение apply lifecycle и exact read owner по одной ответственности класса. До приёмки полной карты код не продолжается; public ports/read error transport, restore/branch/settings и concrete DAG bindings требуют своих exact решений. Исторические R1–R3 proposals читать с последующими приёмками в owning-плане, не считать автоматически вновь открытыми.

Contract changes R1–R3 предъявлены отдельно: [snapshot-retention-cancel-diagnostics-contract.md](snapshot-retention-cancel-diagnostics-contract.md). В частности, предложены SectionStateRetention/SectionHistoryRetention, existing OperationCancelled carrier и расширение core diagnostic union. Это требует приёмки до изменения accepted DTO/codec; готовность полного apply пока не объявляется.

Дополнительная S3 сверка: [snapshot-public-apply-atomic-trace.md](snapshot-public-apply-atomic-trace.md). Для public apply обнаружены конкретные contract gates retention destinations/inheritance, cancellation replay и typed core refusals. Read proposals от них независимы. Поэтому readiness signatures к review не означает завершённого public apply implementation contract. Предложенный отдельный cancellation carrier в S3 дополняет error roster этого документа только после принятия.

2026-11-14. CONTRACT PROPOSAL READY FOR REVIEW для трёх методов. Связан с [планом интеграции](snapshot-public-contracts-dag-integration.md). Код/ноды не реализованы. Apply signature/outcome — existing freeze; новые read signatures, error transport и узкий read-UOW port ниже предъявлены для пользовательской приёмки. Read-UOW механизм найден в существующем коде, не является отсутствующей реализацией. Контракты остальных доменов сохраняются v1 без адаптеров. Полный CRUD и runtime readiness этим статусом не объявляются.

## 1. Concrete owner и три метода текущего среза

**Дополнение 2026-11-15:** пользователь принял отдельный current-read по ARCH-DEC-3A: read_current_publication(world_uid) → SnapshotCurrentPublicationResult через owning current-reader port. Поэтому исходный список трёх методов ниже дополнен четвёртым, а запрет implicit latest внутри exact reads сохраняется. Новый result/port определены в ARCH-DEC-3A. Базовый timeline создаётся и активируется при первом gameplay start по актуальному ARCH-0.1 owning-плана; расширения branch/attach вне scope, только TODO. Time preparation вызывается через DAG, exact initial-state/start contract ещё уточняется. Settings C/R/U/D=N/A в текущем scope; restore decomposition принята без разрешения переключения timeline.

**Разделение принято 2026-11-15 («Ок»):** ARCH-DEC-1/2 owning-плана фиксирует IWorldSnapshotApply → WorldSnapshotService и IWorldSnapshotRead → SnapshotReadService с указанными ниже exact путями и методами. Имя read owner/port больше не OPEN; прежние proposed формулировки ниже — история. Public error transport и полная архитектурная/реализационная приёмка остаются отдельными gates.

Актуальное exact предложение владельцев — ARCH-DEC-1 owning-плана: `IWorldSnapshotApply` / `WorldSnapshotService` оставляют apply; `IWorldSnapshotRead` в application/worldSnapshot/contracts/readPort.py и `SnapshotReadService` в application/worldSnapshot/service/snapshotReadService.py получают два exact reads. DTO и signatures этого документа сохраняются. Статус разделения — предложено для приёмки, не existing runtime. Исходный объединённый класс в код-блоке ниже — только историческая форма предъявления signatures.

Историческое предложение объединяло три метода в WorldSnapshotService. Текущий ARCH-0 оставляет за ним apply lifecycle и предъявляет отдельного exact-read owner; имя read port/class ещё OPEN. Код-блок ниже сохраняет исходные signatures, но не является утверждённым размещением всех методов в одном классе. Public caller каждого метода — непосредственно согласуемая нода DAG. API/debug/worker не вызывает сервис напрямую. Разделение read/write нод и их имена определяются позднее чатом DAG.

```python
class WorldSnapshotService:
    async def apply[S: DomainSection](
        self, patch_set: PatchSet[S],
    ) -> SnapshotApplyResult: ...

    async def read_snapshot(
        self, snapshot: SnapshotRef,
    ) -> SnapshotReadResult: ...

    async def read_publication(
        self, request: SnapshotPublicationReadInput,
    ) -> SnapshotPublicationReadResult: ...
```

read_publication здесь **exact historical publication**, не неявный current/latest read. Предварительное намерение добавить current read заменено exact вариантом после проверки ports: existing IWorldPublicationStore.read возвращает nonoptional ref, а публичный контракт отсутствующего мира ещё не определён. Не объявлять такой lookup готовым посредством придуманных NOT_FOUND exceptions. Получение current expected heads для нового сценария — отдельный будущий контракт; данные ожидаемых heads уже входят в existing apply input.

Не вводятся generic CRUD(operation=...), второй фасад, методы prepare/apply internal stages для DAG или дублирующий SnapshotWriteInput. Runtime create/update состояния проходит только apply; это не разрешение изменять immutable snapshot row.

## 2. Input/Output: точные поля и модули

Все новые records: Pydantic BaseModel, strict=True, frozen=True, extra=forbid, revalidate_instances=always; обязательные поля, включая nullable, без молчаливых defaults. Типы identity/metadata только existing, не зеркала.

| Тип | Модуль backend/app/dataModel/ | Поля / инварианты |
|---|---|---|
| PatchSet[S], existing | patch/request/patchSet.py | Existing format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Состав не меняется |
| SnapshotApplyResult, existing | worldSnapshot/results/apply.py | category, operation_id, request_fingerprint, committed, diagnostics. Existing invariant COMMITTED vs CONFLICT/REJECTED сохраняется |
| SnapshotRef, existing | worldSnapshot/identity/refs.py | WorldSnapshotRef или PlayerSnapshotRef с existing discriminator. Прямой named input read_snapshot, без обёртки с тем же ref |
| SnapshotReadResult, proposed | worldSnapshot/results/read.py | snapshot: SnapshotRef; metadata: SnapshotEnvelope \| None. Non-null metadata.ref строго равен snapshot; None означает отсутствие exact записи, не corruption |
| SnapshotPublicationReadInput, proposed | worldSnapshot/requests/publicationRead.py | world_uid: EntityUid; publication_id: EntityUid. Оба обязательны; target exact |
| SnapshotPublicationReadResult, proposed | worldSnapshot/results/read.py | request: SnapshotPublicationReadInput; publication: WorldPublicationRef \| None. Non-null совпадает по world_uid/publication_id; None — отсутствие exact записи |

Read result связывает ответ с запросом, а не дублирует поля metadata/publication. Null — нормальный результат существования, не строковый diagnostic. Read не заявляет доступность всех retained artifacts, чужого payload или capture authority; найденная metadata и verified body — разные гарантии. Missing persisted parent при apply остаётся corruption, не преобразуется в этот null result.

Новые records не заменяют SnapshotEnvelope, WorldPublicationRef, SectionStateRef, AcceptedStateReader или Source capture/proof. Последний возвращает иной semantic result и не является Snapshot read API.

## 3. Error contract: existing baseline и точное предложение

Existing apply business result остаётся SnapshotApplyResult с CONFLICT/REJECTED и исходными concrete FieldPathError subclasses. Никаких infrastructure категорий в SnapshotApplyOutcomeKind. Независимые diagnostics сохраняют порядок фаз/секций/producer; общий FieldPathError нельзя инстанцировать вместо конкретного owning класса.

Existing infrastructure carriers в application/publication/errors.py: OperationBusyError, PublicationInfrastructureError, UnknownCommitOutcome. Они сейчас не имеют публичного dataModel fault. Поэтому одно перечисление этих исключений не закрывает критерий typed public errors. Предлагается **один Snapshot boundary carrier**, не изменение глобальных publication exceptions:

`SnapshotPublicError` в backend/app/application/worldSnapshot/errors.py содержит `fault: SnapshotPublicFault`, исходное исключение сохраняет через cause. Новый fault в backend/app/dataModel/worldSnapshot/errors/publicFault.py:

- SnapshotPublicOperation(StrEnum): APPLY, READ_SNAPSHOT, READ_PUBLICATION.
- SnapshotPublicFailureKind(StrEnum): INVALID_INPUT, ADMISSION_REFUSED, BUSY, INFRASTRUCTURE_FAILURE, OUTCOME_UNKNOWN. Это категории transport, не operation terminal.
- SnapshotPublicFault: operation: SnapshotPublicOperation; kind: SnapshotPublicFailureKind; operation_id: EntityUid | None; request_fingerprint: RevisionHex | None; input_issues — exact семичленный closed roster приоритетной дельты 2026-11-24 (два shape, invariant fact, четыре owning compatibility facts). Все поля обязательны. Второго shape-only schema или Snapshot compatibility mirrors нет.
- JsonFieldError и WireShapeIssue — existing конкретные POJO из dataModel/validation/importIssues/jsonFieldError.py и wireShapeIssue.py, с existing JsonValidationCode и typed WireLocation. Новый SnapshotInputFieldCode/SnapshotInputFieldIssue **отозван как дубль**. FieldPathError применяется только к существующему объявленному полю; root/wrong model/extra unknown key описывается WireShapeIssue, не выдуманным FieldRef. Pydantic ErrorType сохраняется в pydantic_type для SCHEMA_VIOLATION по existing invariant.

INVALID_INPUT допускает непустые только shape diagnostics; ADMISSION_REFUSED допускает mixed closed roster с обязательной relation/compatibility причиной и только APPLY. Для обоих operation_id и request_fingerprint строго None. Остальные kinds требуют пустые input_issues. Для reads оба binding-поля всегда None. Для apply после получения checked fingerprint оба non-null; до него оба None, включая encoder fault. Частичный binding запрещён. OUTCOME_UNKNOWN/BUSY допустимы только для APPLY с binding; unknown cause остаётся UnknownCommitOutcome. BUSY не обещает auto-retry и не утверждает отсутствие effects другой попытки. Infrastructure fault не включает raw payload/SQL/exception message.

Admission diagnostics агрегируются существующим ValidatorAggregationHelper с exact closed roster выше. application/worldSnapshot/validation/publicInputValidation.py::SnapshotPublicInputValidation — только mapper одного подтверждённого PatchSetStructuralFailure, не повторная revalidation; exact Input и loc contract заданы в приоритетной дельте. Structural collector допускает только JsonFieldError/WireShapeIssue. Request validator добавляет relation/compatibility outputs на исходных местах. Порядок producer/loc/indices сохраняется без grouping, sorting и deduplication. Domain semantic/model invariants не превращаются в schema errors. Неизвестные programmer/validator errors не маскируются под INVALID_INPUT. CancelledError остаётся отменой invocation; transaction uncertainty не заменяется business result.

SnapshotPublicError переносит неперсистентные admission faults и F05/F06 transport этих методов. Existing business SnapshotApplyResult после hash/claim не оборачивается им; scoped D1 остаётся прежним. PublicationInfrastructureError/OperationBusyError/UnknownCommitOutcome остаются cause. Это не общий errors framework и не замена storage exceptions. Публичные ошибки не импортируют engine NodeError; их mapping принадлежит DAG binding.

Решение admission→claim и делегирование реализации уже согласованы; внутренняя детализация и Output→Input сводятся владельцами через координатора. Повторный общий пользовательский gate не вводится. Неизменные scoped D1 collector и business codes не мигрируются. Compatibility projection выше восполняет недостающие operands, не создаёт копии owning invariant codes. До зависимой реализации требуются exact PatchSet exports и нормативная синхронизация, а не новое разрешение всего среза.

## 4. Вложенные вызовы и transaction ownership

### apply

Порядок existing freeze docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок» неизменен:

1. Strict admission/core/prepared-order/registry/formats, затем request fingerprint. Actual dependency section fingerprint здесь не вычисляется.
2. Immutable operation binding; exact terminal replay до повторного чтения refs. Same ID/different request не меняет original record.
3. Один apply claim; artifact protection/verification.
4. Общая publication transaction: expected world/player, gameplay/base/timeline/turn checks до handlers.
5. После expected/source binding — actual dependency section fingerprints; затем все handler.validate на одной базе в declared order с aggregation исходных diagnostics.
6. Handler.apply только после успешных validations; отказ прерывает последующие handlers и откатывает набор.
7. Metadata → holder handoff → world/player publication CAS → terminal в одной transaction по owning freeze. COMMITTED наружу и success log только после confirmed COMMIT.

WorldSnapshotService не собирает PatchSet: его собирает DAG из native typed результатов доменных операций. Внутренний handler не вызывает чужой public pipeline и не пишет snapshot metadata/heads. Владелец transaction — publication commit store; сервис/handler/DAG не выполняют независимый nested commit. Exact terminal/refusal persistence и retry implementation ещё не закрыты 4D2; публичная подпись не выдаётся за реализованный lifecycle.

### read_snapshot

Strict SnapshotRef → service-owned read_scope → Snapshot history.read(ref, scope=scope) → strict validation identity/envelope → закрытие read scope → SnapshotReadResult. Нет writes, staging, generation, repairs, latest fallback или acquisition ownership. Read возвращает metadata по world/player union. Некорректная persisted metadata — infrastructure fault, не None. Точная existing semantics: history lookup по snapshot_id в выбранной chain table; отсутствующий ID даёт metadata=None. Если ID найден, но owner/timeline/decoded ref не равен request, existing adapter сообщает PublicationInfrastructureError. Public read сохраняет этот fail-closed исход, не делает второй lookup и не обещает скрыть mismatch как отсутствие. Это явное отличие от composite lookup read_publication, а не изменение принятого history port.

### read_publication

Strict input → service-owned read_scope → IExactWorldPublicationReader.read_exact(world_uid, publication_id, scope=read_scope) → проверка identity → закрытие read scope → result. Composite lookup world_uid+publication_id возвращает None, если такой пары нет; найденная inconsistent row/parent/head — infrastructure error. Caller не передаёт scope. Никакого current/latest lookup при отсутствии exact publication.

### Конкретный read-UOW port — reuse existing реализации

Предлагается узкий Protocol `ISnapshotReadScopeFactory` в backend/app/application/worldSnapshot/storage/readScopeFactory.py:

```python
def read_scope(self) -> AbstractAsyncContextManager[CommitReadScope]: ...
```

Concrete implementation уже существует: backend/app/db/repositories/sqlite/snapshotCore/commitScope.py::SqlitePublicationCommitStore.read_scope(existing_scope=None). Более широкий optional argument concrete метода не раскрывается через новый узкий protocol. Не создавать второй coordinator, adapter, wrapper или read connection factory. DI сервиса получает тот же объект как ISnapshotReadScopeFactory; history/exact-publication adapters используют его же database/SqliteScopeRegistry.

Текущий механизм _transaction(None, False): BEGIN через SqliteTransactionDriver с write=False, task/database-bound issued scope, read-only facet; success завершает read transaction через ROLLBACK, revoke всегда в finally. Нет synthetic operation_id и writer admission. Ambient/nested transaction отвергается; service открывает один scope на public read, stores получают его explicit и не открывают competing UOW. Scope не возвращается DAG, результат содержит только immutable data.

Важная existing особенность: failed read ROLLBACK тоже может поднять UnknownCommitOutcome из общего coordinator и quarantine соединение. Public read переводит это в SnapshotPublicError(kind=INFRASTRUCTURE_FAILURE, operation_id=None, request_fingerprint=None) с исходным cause: **не было write operation, требующей recovery**. Результат read не возвращается до успешного выхода scope. APPLY UnknownCommitOutcome сохраняет OUTCOME_UNKNOWN и checked binding. Этот mapping не меняет механизм coordinator и не ловит CancelledError как обычный fault.

Оба reads не возвращают право на дальнейшее чтение blobs: lifetime/pin относится к владельцу payload. Они не обязаны открывать Source capture или Pack pin и не удерживают их скрыто.

## 5. Source / Pack / Cache — проверенный минимальный mapping

| Владелец | Нужен ли прямой вызов этим трём Snapshot методам | Передача через DAG / граница |
|---|---|---|
| Source | Нет. Snapshot metadata read не читает authored bodies; apply принимает native prepared sections | Source capture/proof остаются owning DTO. Если нужны producer, DAG вызывает Source отдельно и передаёт результат его потребителю. Snapshot не создаёт зеркальный proof/authority resolver |
| Pack | Нет public Pack call внутри Snapshot. Apply использует existing WorldPublicationRef.pack_hash, который уже входит в expected_world | PackActivationResult.publication может быть передан DAG как publication expectation, но одного activation недостаточно для runtime: apply требует gameplay_started=True. Не конструировать готовый PatchSet из candidate и не запускать activation в apply |
| Cache | Не требуется для корректности metadata/publication read/apply | Cache key/namespace/retention для Snapshot не согласованы и не вводятся «на всякий случай». CacheService публично вызывает DAG только при отдельном принятом binding. Cache hit не доказывает актуальность head/holds |

Основания сверки: source-pack-boundary-response-2026-11-14.md, pack-contract-final-scope.md и cache-public-contracts.md. Принятое exact candidate READY ledger хранение относится к Pack preparation, не является новым Snapshot public методом и не блокирует эти read signatures. Source authority provider для Pack остаётся самостоятельной задачей; Snapshot не присваивает его через общий read facade.

Отложенные генераторы/остальные домены сохраняют v1. Их native compatibility не утверждается; конвертация output→section внутри Snapshot запрещена. Фактические v1 места требуют локальных комментариев по интеграционному плану. Пустой core tick и contract fixtures не доказывают production registration таких доменов.

## 6. Что передавать DAG после согласования

Три exact methods §1, dataModel fields §2, error proposal §3, trace §4. DAG владеет вызовом, ветвлением по result/error, сборкой PatchSet и дальнейшим вызовом владельца payload; Snapshot не возвращает команды запуска. read_snapshot.metadata и read_publication.publication — только metadata/identity результаты. Apply COMMITTED передаёт existing SnapshotCommitRefs; CONFLICT/REJECTED не содержит committed refs. Ни один результат не содержит scope/lease/grant/backend.

Для приёмки node binding отдельно зафиксировать происхождение operation_id/preparation_fingerprint/expected heads, native section producers и порядок, а также путь read missing/refusal/unknown/cancellation. Ноды сейчас не назначены, сообщение в DAG не отправлялось. Реализацию нод согласуют после пользовательской приёмки контрактов; public readiness не равна runtime readiness.

## 7. Статусы и проверяемые gates

- Apply signature/result: reuse accepted freeze; concrete method implementation и terminal/retry остаются OPEN.
- Два exact read methods и POJO: конкретное предложение готово к review; public errors также предъявлены явно, не считаются принятыми.
- Read transaction issuer: existing SqlitePublicationCommitStore.read_scope; узкий ISnapshotReadScopeFactory предъявлен выше для принятия, отсутствующего storage механизма нет.
- Current publication/player head reads, restore, branch, delete/prune, settings CRUD: отдельная следующая спецификация. Ни удаление immutable history, ни settings exception не изобретены. Полный Snapshot CRUD пока не принят.
- Source/Pack/Cache: для текущих трёх методов новые public dependencies не требуются; будущая необходимость оформляется отдельно exact mapping.

Проверки будущей реализации: strict malformed inputs и concrete error types; exact missing без writes; wrong world/player/ref/version; corrupted metadata; no latest fallback; no payload reads; два SQLite connections для partial apply rollback, stale CAS, partial holder handoff, cancellation, replay/unknown; отсутствие domain→Snapshot и route bypass; typing + профильные regression + snapshotCore. Для комментариев/документального прохода эти tests не запускались.

Evidence этого прохода: прочитаны Snapshot freeze, существующие DTO/ports/service/reader/errors и Source/Pack/Cache boundaries. Выполнен git diff --check документов. Код, ТЗ, чужие изменения и DAG не изменялись. Документ не закрывает открытые gates обещанием будущего wiring.

## 8. Scoped D0/D1 и критерии решения по первому пункту

| Семейство / ответственность | Решение | Проверяемый критерий |
|---|---|---|
| F01/F09 input shape | Reuse JsonFieldError/WireShapeIssue, без Snapshot mirror codes | Missing/type/extra/wrong union root дают exact concrete тип, typed path/location и pydantic_type; нет фиктивного пути к undeclared field |
| F02/F03 apply contract/business | Reuse accepted PatchSet/registry/SectionRefused/SnapshotApplyResult | Semantic codes/producer order не меняются; rejected не создаёт fake committed refs |
| F05 infrastructure | SnapshotPublicFault transport, исходный cause; details только safe log projection | Corrupt row/IO не становятся None/REJECTED; read cleanup uncertainty не становится write recovery |
| F06 busy/cancel/unknown | Busy и unknown отдельные kinds; cancellation исходное исключение | Нет automatic retry, fake cancellation terminal или success до acknowledgement |
| F08 aggregation | Existing exact-admitted collector, scoped D1 metadata unchanged | Несколько structural errors до IO; malformed field не скрывает независимую причину |
| F04/F07 | Не добавляются этим срезом | Нет domain→NodeError; read не выдумывает warnings о generation |

Concrete public implementation owner — WorldSnapshotService; существующие SnapshotMetadataBuilder/AcceptedStateReader/SectionRegistry/storage/codec/log responsibilities остаются в integration plan. Новый SnapshotPublicInputValidation не владеет read/commit или domain semantics. Новый read protocol не владеет connection. Новые read-result POJO отличаются от metadata: описывают exact lookup existence/correlation, не копируют payload. SnapshotPublicFault не persisted outcome/receipt. Нового settings CRUD или exception к нему этот срез не утверждает.

### Матрица caller outcomes для трёх методов

| Сценарий | Caller видит |
|---|---|
| Malformed input любого метода до IO | SnapshotPublicError INVALID_INPUT, непустые existing shape issues, binding None |
| Apply admission relations/compatibility, в том числе mixed со shape | SnapshotPublicError ADMISSION_REFUSED, все concrete diagnostics/indices в producer order, оба binding-поля None; нет claim/record_refusal |
| Missing snapshot ID / missing exact publication pair | Successful read-result с None соответствующего payload |
| Stored identity/parent/chain inconsistency | SnapshotPublicError INFRASTRUCTURE_FAILURE, исходный cause; не None |
| Concurrent publication после read | Read возвращает pinned historical result; он не обещает current head после scope |
| Valid apply semantic refusal / stale expected CAS | Existing SnapshotApplyResult REJECTED/CONFLICT согласно accepted phase order; no committed refs |
| Successful apply / same-request durable replay | Existing COMMITTED c сохранёнными refs; replay до повторной проверки target refs |
| Same operation_id, другой fingerprint | Existing rejected policy, без overwrite/повторного body исходной операции |
| Apply busy / uncertain commit | SnapshotPublicError BUSY / OUTCOME_UNKNOWN; unknown только с checked binding |
| Read cleanup uncertainty | INFRASTRUCTURE_FAILURE, cause UnknownCommitOutcome, quarantine сохраняется |
| Cancelled invocation | CancelledError после owning cleanup semantics; durable исход не выводится из отмены |

**Предмет приёмки пользователем сейчас:** три signatures; два read-result POJO и publication read-input; reuse shape errors и public transport fault; exact lookup/mismatch semantics; узкий read-UOW protocol поверх existing implementation. Поля и владельцы определены, больше нет отложенного решения «кто выдаёт read scope». После принятия можно передавать этот контракт DAG для node design; implementation public apply/terminal/retry остаётся отдельным разрешённым срезом, не обещанием готового исполнения. Restore/branch/settings/delete и новый authored Source writer не входят в первый пункт.

Повторная статическая сверка: commitScope.py read lifecycle/driver, historyStore read и worldPublicationStore.read_exact, FieldPathError/JsonFieldError/WireShapeIssue и error-contracts-1 F01–F09. Runtime/typing/regression не запускались: код не менялся. Новые поля/error mapping требуют tests при реализации, не считаются проверенными этим документом.
