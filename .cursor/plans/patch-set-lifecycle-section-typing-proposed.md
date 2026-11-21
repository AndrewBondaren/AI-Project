# PatchSet: Lifecycle mixed section и closed node bindings

## Шаги 1/2 — named node contracts и finite mock manifest

2026-11-21: девять exact node cards из начала gen-dag-lifecycle-node-contracts.md подтверждены на уровне source-compatible proposal (version1, Never, empty errors/reads/calls, named Q/P). Полный class/module/kind/test-ID roster и consumers/reachability опубликованы в [owning manifest roster](patch-set-lifecycle-mock-manifest-roster.md): 64 новые test declarations, exact shared reuse, отдельный MockSnapshotApplyResult/root94001 как предложение; production Time20150 не меняется. Runtime-only node/checkpoint/claim/capture/request carriers не зарегистрированы. Scope allocation — итоговая таблица 94001–94062 и94090/94091; это не production reservation/code-go. Runtime merge/round-trip/static tests ещё не выполнены.

## Section fingerprint: подтверждённые границы — 2026-11-21

ACCEPTED пользователем через [решение координатора](gen-dag-lifecycle-node-contracts.md#подтверждённое-решение-пользователя--fingerprint-и-admitted-view): actual section fingerprint проверяется после claim/exact terminal replay только в новой попытке dependency binding до первого handler.validate; единственный helper — SectionFingerprint; delivery — Snapshot-owned AdmittedSectionView от SnapshotAttemptContextBuilder. Прежние до-claim размещение, альтернативный BoundSectionCodec.fingerprint и внешний LifecycleMockPreparedEvidenceBinding.from_request SUPERSEDED. Три выбора больше не OPEN; code-go/runtime acceptance этим не выданы.

Ответ на вопрос 3 координатора; согласовать со Snapshot вопросом 2. Evidence actual: application/patch/encoding/patchSetCodec.py::fingerprint хэширует целый request и НЕ подходит. application/patch/registry/boundSectionCodec.py::encode(section:DomainSection)->bytes уже проверяет exact model, strict nested structure, key/supported version и bytes result, затем вызывает owning SectionCodec.encode. encoding/canonicalCodec.py::content_digest(data:bytes)->bytes — SHA-256 exact bytes. Actual section fingerprint comparison в Snapshot здесь не подтверждён; новый алгоритм не выдаётся за existing.

### Public pure helper, минимальная application дельта

Принятый target application/patch/encoding/sectionFingerprint.py::SectionFingerprint, владелец Patch representation (не заявление наличия реализации):

```python
class SectionFingerprint:
    def __init__(self, registry: SectionRegistry) -> None: ...
    def fingerprint(self, section: DomainSection) -> RevisionHex: ...
```

Одна точная формула: `content_digest(self.registry.resolve_codec(section).encode(section)).hex()`. Это standalone pure representation utility, не DAG pipeline, не semantic handler, не новый registry/codec формат. Registry — тот же checked C1 binding, frozen состав composition на время вызовов; никаких service/storage/callback dependencies. Public input — готовая native section, output — 64-char lower-case SHA-256 RevisionHex. Existing общий core/assembler/POJO не меняются. Единственный нормативный вычислитель — SectionFingerprint; Snapshot вызывает его, второй алгоритм/serializer или BoundSectionCodec.fingerprint не вводится.

Errors: wrong exact section model/не-bytes output — existing TypeError; неизвестный key/unsupported version — existing ValueError; malformed nested instance — Pydantic ValidationError; canonical representation failure — CanonicalEncodingError с cause. Helper не ловит их как business refusal. C1 construction wrong contract identity — configuration TypeError/ValueError до fingerprint. Snapshot отображает ошибки representation/admission своим existing transport; declared-vs-actual hash mismatch — отдельная owning dependency-admission диагностика, не exception самого fingerprint helper.

**Хэшируемые bytes:** ровно owning canonical encode полной section, включая её native SectionHeader и ordered patches; для LifecycleSection также весь domain_evidence (types/values/order). Не PatchSet envelope/projection, не отдельно payload одного patch, не JSON/model_dump, не digest самого manifest. Model RECORD identity и версии, представленные в owning bytes, участвуют через encode; Python object identity SectionContract не хэшируется. Exact contract/model/key/version проверяются отдельно admission. Для local v1 codec обязан сериализовать всю native section без read-upgrade/reprojection и без опускания header/evidence; эта codec гарантия проверяется synthetic round-trip/field-change tests. Метод не принимает произвольные bytes, которые нельзя связать с admitted section. FormatVersion секции не равен format terminal1; numeric Lifecycle/subject codec versions здесь не назначаются.

### Producer / declared / admitted comparison

1. Synthetic subject preparation получает готовую immutable subject section с окончательными header/operation refs; через свой согласованный representation binding вызывает SectionFingerprint.fingerprint(section). Из этого результата создаёт PreparedSectionDependency(section_key=section.header.key, section_fingerprint=hash) в owning PreparedEffectBinding. Section объект и эти refs передаются далее как ready inputs. Это synthetic preparation/composition обязанность, не foreign codec вызов из Lifecycle и не hash алгоритм в DAG. До вычисления section должна быть окончательной; последующая смена header/payload требует нового declared hash.
2. Lifecycle prepare_section проверяет отношения supplied evidence и переносит domain_evidence exact tuple; fingerprints не пересчитывает. Header.depends_on — stable unique projection уже проверенных declared dependencies. Lifecycle codec сериализует только собственную section; чужой codec не вызывается.
3. Snapshot request/dependency admission после exact structural/registry/key/version/core/prepared-order checks находит единственную immutable subject section в том же request по dependency.section_key. Snapshot через тот же SectionFingerprint вычисляет actual RevisionHex и сравнивает с declared section_fingerprint каждой PREPARED зависимости. Не подменяет declared actual значением. Missing/ambiguous target и mismatch не дают validated dependency view. PUBLISHED dependencies используют собственную границу, эта формула их не переопределяет.
4. Actual digest comparison выполняется после claim/exact terminal replay, только для новой попытки в общей dependency-binding фазе до первого handler.validate. На terminal replay section digests не пересчитываются и handlers не вызываются. Прежнее размещение этой проверки в до-claim SnapshotRequestValidator отменено. Expected-context/source bindings/H3 и all-validate-before-apply сохраняются; остальные стадии не переставляются. Mismatch — owning Snapshot dependency refusal; codec/contract failure не маскируется business refusal.
5. SnapshotAttemptContextBuilder создаёт Snapshot-owned AdmittedSectionView из admitted request внутри attempt. Один immutable view через validation context используется validate/apply с exact request/scope/lifetime binding и результатом проверки dependencies. Existing resolved_dependencies сам по себе такой гарантии не создаёт. Внешний LifecycleMockPreparedEvidenceBinding.from_request, повторный request/context holder и mutable proof-cache/trusted flag не вводятся. Lifecycle получает typed operands; hash equality подтверждает содержимое, не subject effect truth; predicates и достаточность evidence принадлежат Lifecycle/subject.

### Representation consumer / индексы

Consumer применяет LifecycleSectionAB.domain_evidence[i]; closed union CoverageA|CoverageB и nested refs/effects сохраняются при prepare -> native -> assembler -> codec/decode. source request index i остаётся native section index i; PatchRef ordinal — отдельный адрес, не индекс evidence. Диагностические paths должны быть domain_evidence[i].patch_refs[k]/effect/section по реальному нарушенному operand. Старые patches[i].evidence[j] в historical Lifecycle apply table несовместимы с выбранной representation и требуют owning синхронизации; PatchSet не вводит второй carrier/код ошибки. Hash mismatch общий Snapshot admission адресует исходную dependency, а ложный subject effect диагностирует owning subject/Lifecycle relation, не hash helper.

### Проверки и точный остаток

- Same PatchRef + changed subject payload: actual bytes/hash меняется, старый declared hash не принимается (кроме теоретической SHA-256 collision; это стандартное cryptographic binding, не математическая уникальность).
- Wrong section model/key/version или contract identity: отказ C1 admission до выдачи fingerprint/view.
- Well-formed неверный declared hash: dependency admission отказ; запрещены исправление declared, handler/apply до successful admission.
- Корректный hash и существующие refs, но ложный claimed effect/action/entity: hash check проходит, subject owner verification и owning relation должны отказать до commit. Никакого semantic PASS на основании hash.
- Поменять domain_evidence entry/ref/order: round-trip сохраняет новую representation, original fingerprint не переиспользуется; evidence paths адресуют реальные section поля.

Закрыты пользовательским решением положение проверки после replay, единственный helper API и Snapshot ownership/delivery view. Остаток — синхронизация exact owning declarations/diagnostics и evidence реализации: full-section codec/manifest closure, section.domain_evidence round-trip, wrong binding/version/hash, отсутствие digest/handler calls при replay, lifetime view. Старый smoke patch.evidence не проверяет текущую section.domain_evidence. Runtime готовность и code-go не объявлены; реальные producers/SQL/production wiring OUT и не gates. Ни кода, ни тестов этот документ не выполняет.

## Trace producer / evidence / witness — сверка 2026-11-21

Координатор поддержал section-level evidence, Q/P binding и plain union; это техническое сведение к owning freeze, не code-go. Принятая граница ответственности из snapshot-lifecycle-atomic-boundary.md имеет приоритет: Lifecycle задаёт predicates/достаточность evidence, synthetic предметный владелец — truth своих effects, Snapshot — общие boundary/transaction guarantees. PatchSet отвечает только за native compatibility/сохранение данных.

| Переход | Exact typed данные / что сохраняется | Чего это НЕ доказывает |
|---|---|---|
| Synthetic admission -> prepare request | DomainAdmission[T].publication/action_uid/effects; DomainEffect[T].entity/effect/reason_action_uid сверяются Lifecycle с intent/capture | Instance POJO не authority token и не доказательство actual payload |
| Prepare -> prepared | base + transition(intent, participants before/after), reason/action refs внутри owning intent | Полный admission не сохраняется и не доступен apply автоматически |
| Coverage -> section request | PreparedEffectBinding[T].change_uid/effect/section/patch_refs; section содержит key/fingerprint | Caller-supplied relation не подтверждает, что указанный patch реализует effect |
| Section request -> native | section.domain_evidence[i] сохраняет exact class и все поля request.domain_evidence[i], число/порядок entries неизменны | Header dependency extraction не заменяет evidence и не проверяет чужой payload |
| Native -> PatchSet -> codec/decode | Closed CoverageA/B roster, owning record IDs/transitive schemas, native поля сохраняются целиком | Успех assemble/round-trip не semantic admission |
| Atomic admitted refs/dependencies -> Lifecycle checks | Только объявленные context/source operands: membership PatchRef и binding секции/fingerprint/base | Наличие ref и даже подтверждённый content hash не доказывают subject effect truth |
| Synthetic subject witness -> Lifecycle relation check | Owning таблица должна предъявить точный source method/result и связь с typed entity/effect/action/base/refs | Этот последний источник не выводится автоматически из DomainAdmission либо membership |

**Exact representation invariant:** len(output.domain_evidence)==len(input.domain_evidence); для каждого i type/output fields совпадают с исходным entry; patch_refs внутри entry не переупорядочены. Duplicate/extra/missing coverage отвергает owning validator до build; перенос не исправляет ошибочный вход. revalidation может создавать новые immutable instances, object identity не обязательна. Index i относится к секции; patch_index j адресует отдельный patches tuple, подмена этих индексов запрещена. Header dependencies — только stable unique projection после проверки conflicts; field values в domain_evidence не нормализуются.

**Closed roster:** один plain union value CoverageAB = CoverageA | CoverageB на request и section; оба exact named PreparedEffectBinding children с closed T и named nested effect/ref schemas. Subclass/другой reason/kind/NoDomainMutation не допускаются вместо объявленного type. Coverage IDs и reachable records объявляет synthetic manifest после общей collision сверки. Это единый reused evidence POJO, не копия в header и не третий witness DTO.

**Точный остающийся пробел source trace:** owning DomainAdmission имеет publication/action/effects, PreparedEffectBinding — effect/change_uid/section/refs. Ни один из этих records сам по себе не является результатом authoritative проверки actual admitted domain patch payload. Пока не предъявлен exact source operation/result для synthetic subject witness и его binding к этому payload/base, полный semantic evidence check OPEN. Нельзя закрыть его одним admitted_patch_refs tuple, verified dependency fingerprint или trusted=True. Требование относится только к mock_lifecycle_world/synthetic A/B; реальные producers/storage OUT не требуются. Нужна Lifecycle owning predicate/operand/source/checker/outcome таблица, затем Snapshot сверяет допустимый capability/lifetime. PatchSet не вводит такой source API за владельца.

**Коррекция прежней формулировки:** упоминание в предыдущем разделе «Snapshot atomic proposal требует...» означает выявленную потребность общей цепочки, не право Snapshot назначать predicates/достаточность. Предлагаемое admitted_patch_refs остаётся необязательной не принятой capability; сначала owning trace и reuse, затем минимальная согласованная дельта. Representation поле domain_evidence сохраняет необходимые отношения, но не решает вопрос truth.

Дополнительный негативный synthetic критерий: тот же существующий ref и корректный fingerprint предметной секции, но payload реализует другой entity/effect/action — common admission может пройти, owning subject verification/отношение должно отказать до общего commit. Проверяющий класс/метод/результат отказа должен быть указан Lifecycle, а не реализован assembler. Для неподтверждённого/неполного source результата нельзя подставить успешный witness. Tests здесь не запускались.

## Фиксация по поручению пользователя — 2026-11-21

Пользователь поручил «Зафиксируй» после предъявления результата сверки evidence/construction. Зафиксирован следующий целевой контракт со стороны PatchSet:

1. LifecycleSection сохраняет typed domain_evidence целиком из PrepareLifecycleSection: concrete types, значения, порядок и соответствие effect -> domain PatchRef. Header dependencies не заменяют эти связи. Native patch остаётся header + prepared; evidence не копируется по patches.
2. Минимальный prepare binding содержит request_model/prepared_model; nested model constructors выводятся из публичных annotations. Section binding содержит request_model/section_contract/patch_bindings; отдельный section_model не задаётся.
3. Request и section используют одинаковый closed evidence roster; исходный индекс entry сохраняется для apply diagnostics. Semantic retry не отменяет coverage checks.
4. Для этого переноса правки общего ядра PatchSet не требуются; domain section/schema/manifest остаются ответственностью Lifecycle/composition. Наличие поля не доказывает apply semantics или runtime readiness.

Общая междоменная приёмка не объявлена: координатор сводит Lifecycle C1 declarations, representation/manifest и Snapshot typed admitted-patch/source capability. Это технические IN стыки, не новые production prerequisites. Код, тестовая fixture, миграции и новые numeric IDs не разрешены этим поручением. Подробные declarations и acceptance criteria ниже сохранены как пакет для этой сверки; общий node-план здесь не редактируется.

## Сведение evidence -> native / construction — 2026-11-21, PROPOSED

Приоритет текущего предложения над прежней header+prepared-only секцией ниже. Источники: entity-lifecycle-local-contracts.md, Coverage/C1; snapshot-lifecycle-atomic-boundary.md, evidence/coverage и evidence_index. Это owning PatchSet рекомендация координатору; изменение Lifecycle representation ещё требует согласования владельцев, не объявляется уже принятым.

### Обнаруженный разрыв и точный перенос

Если сохранить только patch.prepared и SectionHeader.depends_on, теряются change_uid/effect/patch_refs связи из request.domain_evidence. Из одного section key/fingerprint нельзя восстановить, какие refs покрывали какой эффект; разные many-to-many mappings могут иметь одинаковый header. Snapshot atomic proposal требует проверять именно эти связи, включая equal retry. Поэтому ограничение apply до проверки одних dependencies противоречило бы принятому D3/D4; такой вариант не предлагается.

Минимальная дельта — одно owning поле domain_evidence на Lifecycle section, а не на каждом patch и не в Patch core. Proposed dataModel/lifecycle/sections/section.py:

```python
class LifecycleSection[P: PatchData, C: BaseModel](DomainSection[P]):
    domain_evidence: tuple[C, ...]
```

Test-support named declarations (только tests/lifecycle/support/mixedContracts.py):

```python
class CoverageA(PreparedEffectBinding[TestEntityA]): pass
class CoverageB(PreparedEffectBinding[TestEntityB]): pass
CoverageAB = CoverageA | CoverageB

class LifecycleSectionAB(LifecycleSection[PatchAB, CoverageAB]): pass
```

CoverageA/B обязаны использовать owning closed DomainEffect[T] и refs; вложенные canonical records тоже получают named closed declarations в synthetic manifest. C runtime roster не BaseModel/unbound, а ровно CoverageA|CoverageB; NoDomainMutation отсутствует. Поля PreparedEffectBinding переиспользуются без mirror evidence POJO. Пустой tuple структурно допустим как input формы, но для непустого набора переходов нарушает mandatory coverage и даёт owning COVERAGE_MISSING; constructor не обещает semantic admission.

Exact build mapping после успешного validator:

```python
section_model(
    header=constructed_section_header,
    patches=tuple(constructed_patches),
    domain_evidence=request.domain_evidence,
)
```

Сохраняются все entries, concrete types, значения и исходный порядок. Ничего не группировать/дедуплицировать/сортировать в domain_evidence; header dependencies остаются производным ordered unique набором по прежнему алгоритму после проверки fingerprint conflicts. Это два разных представления: header нужен общим dependency checks, evidence — owning relations. Не переносить evidence в PatchHeader.depends_on: patch ordering не был принят. Wrapper остаётся header+prepared, D1 не меняется.

Atomic participant получает section.domain_evidence и сверяет через согласованный typed admitted-patch/source context: существование каждого exact PatchRef в той же операции/указанной секции, fingerprint/base binding, покрытие конкретного typed effect. Механизм actual payload verification/capability принадлежит Lifecycle/Snapshot atomic контракту; PatchSet не вычисляет semantics и не вызывает чужой codec. evidence_index в LifecycleApplyEvidenceConflict — исходный индекс section.domain_evidence, без index remap. Equal accepted-change не отменяет evidence admission и согласованную идемпотентность synthetic domain participant. Наличие поля сохраняет необходимые inputs, но само по себе не закрывает exact admitted-patch capability.

### Один минимальный construction contract к сверке

Поддерживается Q/P LifecyclePreparationBinding из следующего раздела: request_model и prepared_model — единственные задаваемые model roots. Transition/participant/state constructors выводятся при construction из публичных annotations согласованных named schemas, проверяются там и не принимаются как дополнительные независимые настройки. LifecycleSectionBinding[Q,S,M] содержит request_model, section_contract, patch_bindings; section_model получается только как section_contract.section_model. Constructors проверяют named closed models, exact Q.changes/P roster, P->patch.prepared, patch roster/S.patches, плюс exact равенство Q.domain_evidence и S.domain_evidence tuple annotations/constraints. В test AB обе evidence annotations — tuple[CoverageAB,...]. Generic bounds не заменяют exact roster checks.

Во время prepare_section выбирается только native wrapper из immutable exact-class map, затем вызывается bound section model с полями выше. Общий алгоритм не читает kind/reason для выбора класса. Два synthetic kinds × четыре операции остаются девятью concrete registrations и пятью logical операциями. E=Never/error_types=() остаётся source-compatible предложением; runtime/static tests ещё не выполнялись.

### Remaining differences, только IN

1. Lifecycle C1 пока хранит пять независимо передаваемых Models полей и section_model вместе с contract. Требуется заменить declaration минимальными Q/P и section_contract binding либо явно согласовать иной один API. Это техническая дельта, не закрытая одним подтверждением направления.
2. Lifecycle native build сейчас теряет domain_evidence; предлагается поле section.domain_evidence и exact перенос выше. После owning согласования синхронизировать codec manifest closure и Snapshot evidence_index; повторных пользовательских решений по D1–D7 не требуется.
3. Snapshot/Lifecycle уточняют exact typed admitted-patch/source capability, сохраняющий PatchRef/effect association; scope проверки не сужать до section fingerprint. Наличие реальных producers/SQL OUT не требуется, capability проверяется на mock_lifecycle_world.

Evidence совместимости без правки ядра: actual SectionContract проверяет header/patches native annotations, не запрещает дополнительные owning section fields; PatchSetAssembler переносит typed sections целиком и не проецирует их поля. Следовательно domain_evidence проходит в PatchSet неизменным; common invariants остаются прежними. Canonical record поля добавляются только новой proposed Lifecycle section, её wire identity ещё не зарегистрирована этим заданием. Manifest обязан включать CoverageA/B и их reachable records; числовые IDs здесь не назначаются. Никакой заявленной runtime совместимости нового codec без round-trip.

Acceptance additions: round-trip mixed evidence сохраняет exact types/entries/order; две разные effect->refs карты при одинаковом header остаются различимы в payload/fingerprint; подмена связи/пропуск/extra/ref неверной секции дают owning refusal; evidence_index после round-trip адресует тот же entry; assemble не теряет поле; equal semantic retry не обходит coverage; C1 constructor отвергает request/section evidence roster mismatch. Это проект проверок, не выполненные тесты.

## Уточнение construction и NodeContract.E — 2026-11-21, PROPOSED

Сверены актуальные owning schemas entity-lifecycle-local-contracts.md и actual NodeContract/NodeRegistry/SectionContract. Ниже техническое предложение внутри IN, не новая предметная операция и не code-go. Девятка registrations: create/replacement/end/reactivate × A/B + section AB; пять logical операций. Synthetic declarations/NodeIds только test-support, не production.

### Exact named request -> prepared -> patch

Owning T теперь определён как kind token: `TestEntityA = Literal['test_entity_a']`, `TestEntityB = Literal['test_entity_b']`; это aliases, не payload классы. TestAReason/TestBReason — owning synthetic records из локального Lifecycle-плана. Все refs/intents/transitions/requests/prepared на wire должны быть named closed models; specialization только верхнего prepared не заменяет проверки nested schema closure.

Минимальный предлагаемый immutable model binding в application/lifecycle/contracts/preparationBinding.py:

```python
@dataclass(frozen=True)
class LifecyclePreparationBinding[Q: BaseModel, P: BaseModel]:
    request_model: type[Q]
    prepared_model: type[P]
```

Каждый из четырёх existing proposed PipelineOpenPipeline получает `*, binding:LifecyclePreparationBinding[Q,P]` при construction, помимо owning pure policy; метод своей операции принимает Q и возвращает P | LifecycleFieldError | LifecycleLogicError. Это уточнение owning generic API, Lifecycle подтверждает его; новые facade/callback/executor не вводятся. Для CreateA:

```python
class CreateRequestA(PrepareLifecycleCreate[TestEntityA, TestAReason]): pass
# CreateA — named PreparedLifecycleCreate[TestEntityA, TestAReason] ниже
create_a_binding = LifecyclePreparationBinding(CreateRequestA, CreateA)
```

Аналогично CreateRequestB/ReplaceRequestA/B/EndRequestA/B/ReactivateRequestA/B связаны с соответствующими восемью prepared children. Constructor owning operation проверяет named strict concrete модели, свою пару request/prepared operation families и равенство closed kind/reason/transition schemas через публичные model_fields/type annotations. Согласованный каталог kind/reason подтверждает пары, не выполняет runtime lookup по payload.kind. Wrong binding — TypeError/ValueError до вызова. Метод exact-check request_model, strict revalidation, owning validation, затем build prepared_model с base и concrete transition. Concrete nested transition model определяется из prepared_model.model_fields['transition'].annotation при construction; он обязан быть named closed. Конкретный intent/participant construction аналогично берётся из owning declared schemas. Ни выбор P по type(request), ни branch по вложенному kind/operation не требуется: один экземпляр операции уже связан с одной парой Q/P. Wrong-T request и output не coerced; owning отказ остаётся output value.

Отдельный proposed binding только для native wrapping в application/lifecycle/contracts/sectionBinding.py:

```python
@dataclass(frozen=True)
class LifecyclePatchBinding[P: BaseModel, B: PatchData]:
    prepared_model: type[P]
    patch_model: type[B]

@dataclass(frozen=True)
class LifecycleSectionBinding[Q: BaseModel, S: DomainSection, M]:
    request_model: type[Q]
    section_contract: SectionContract[S]
    patch_bindings: tuple[M, ...]
```

M на локальной runtime boundary — закрытый union восьми LifecyclePatchBinding специализаций CreateA/CreatePatchA … ReactivateB/ReactivatePatchB. Это application configuration, не wire POJO и не новый core registry. Constructor section pipeline проверяет: request changes exact roster равен prepared_model roster; keys без повторов; patch_model roster равен section patches union; каждый patch_model.prepared имеет exact prepared_model annotation, header остаётся PatchHeader; модели named/closed/strict. Все восемь пар обязательны. Public constructor `LifecycleSectionPipelineOpenPipeline(*, binding:LifecycleSectionBinding[Q,S,M], policy:<owning policy>)`; `prepare_section(request:Q)->S|<owning section refusal>`. Обозначение policy/refusal ссылается на owning контракт, их типы PatchSet не переименовывает.

После exact request/changes admission section builder выбирает wrapper из заранее проверенной таблицы по exact Python class prepared record, не по вложенным kind/status/reason. Это явный representation dispatch, не выбор публичной операции. Для элемента p: bound patch_model(header=owning_header, prepared=p). Lifecycle header policy и validators не меняются. Foreign subclass — structural/admission failure, не fallback; отсутствие покрытия — owning refusal. Никаких новых classes в Patch core.

**Поправка к declarations ниже:** PEP695 `type PatchAB = ...` нельзя передавать как alias в actual SectionContract: его проверка union не unwrap TypeAliasType. Для совместимости без правки ядра использовать `PatchAB = CreatePatchA | CreatePatchB | ...` (обычный union value, при необходимости annotation TypeAlias) либо literal union в DomainSection[...]. Аналогично на shared admission boundaries не передавать скрытые TypeAliasType без поддержки. Ниже PatchAB исправлен. Plain union с concrete PatchData descendants соответствует actual SectionContract/assembler; codec сохраняет canonical record identities, numeric IDs отдельно.

### Pure leaf: точный Error parameter без фиктивного fault

Рекомендация `E = typing.Never`, `error_types=()`, `retry_policy=None`, `error_policy=None` для всех девяти pure registration contracts:

```python
CREATE_A_CONTRACT: NodeContract[CreateNodeInputA, CreateNodeOutputA, Never] = NodeContract(
    input_type=CreateNodeInputA, output_type=CreateNodeOutputA,
    contract_id=ContractId('engine.lifecycle.test_a.prepare_create'),
    version=ContractVersion('1'), reads=(), error_types=(), calls=(),
)
```

CreateNodeInputA/OutputA — named test-support children owning node wrappers, exact request CreateRequestA и value CreateA | LifecycleFieldError | LifecycleLogicError. Другие операции аналогичны; section output — LifecycleSectionAB | owning section refusal. Node class/executor/CallTarget annotation используют тот же Never. Never — bottom type, не runtime error model; его НЕ помещают в error_types и не создают NodeError заглушку. Статический TypeVar bound NodeError не требует inhabited subtype.

Evidence: application/engine/contracts/nodeContract.py::_validate_error_types проверяет элементы tuple, пустой tuple разрешён; __post_init__ отвергает error_policy при пустом наборе. NodeRegistry._check_binding не требует непустой error_types. Таким образом runtime core изменения не нужны; Pyright positive/negative binding cases обязательны при реализации, их прохождение здесь не заявлено. Указание E=Never означает отсутствие declared node operation errors, а не невозможность runtime failure. Refusals остаются output.value; обычные runtime exceptions/cancellation проходят existing nodeRunner, без blanket catch и без fabricated PythonNodeError. Если позже операция получит настоящий declared public fault — новое согласование E и mapping, не скрытая смена empty roster.

Обязательные проверки construction: reject A-request/B-prepared, правильный kind/неверный reason, неправильная operation family, unbound/nested unnamed model, повтор/пропуск pair, wrong patch.prepared type; reject output B на input A. На engine: девять distinct registrations, E=Never/error_types=() admission, отсутствие declared fault policy; runtime failure не business value. Эти проверки — план evidence, не выполненные тесты.

Итог: новых обязательных правок PatchSet/engine/encoding core по выбранной форме не выявлено. Новые binding types принадлежат Lifecycle application, named synthetic модели — tests/lifecycle/support. Exact owning policy/refusal и вложенные schema declarations сверяются с Lifecycle, atomic capability — Snapshot. Это технические IN стыки, не требование production adapters.

## Принятые D1–D7 — синхронизация 2026-11-21

Источник — начало [owning локальных контрактов Lifecycle](entity-lifecycle-local-contracts.md). D1–D7 больше не пользовательские OPEN; противоположные исторические варианты этого/owning документов не применяются к active v1.

- D1: prepared — pure record base + transition, без header; native wrapper создаётся prepare_section. Header только в PatchData. Уточняем предлагаемое поле wrapper как prepared:P (не transition:P), поскольку P уже содержит transition и base.
- D2: Create/End/Reactivate — ровно один субъект; Replacement — непустые стороны участников, один переход/patch. N независимых переходов дают N patches, число 100 только пример.
- D3: explicit many-to-many coverage. Active SyntheticCoverageUnion — только именованные A/B дети PreparedEffectBinding соответствующего T; один effect может иметь несколько refs, несколько effects — один ref. Это связь с patches предметных synthetic секций, не изменение правила «один Lifecycle patch на переход».
- D4: NoDomainMutation/PublishedNoMutationBinding не входят в active v1 union. Missing required domain patch — coverage refusal; пустой tuple не означает разрешённое отсутствие изменения.
- D5: synthetic Reactivate после End допускается, после Replacement отвергается owning policy. Это не глобальное правило всех предметных доменов.
- D6: test-support fixture mock_lifecycle_world, описание «mock-мир Lifecycle». Детерминированные typed world/publication/timeline refs и проверяемые captured facts A/B; начатый профиль/один timeline только свойства fixture. Production world/gameplay не создаются, trusted=True недопустим. Fixture-код ещё не создан; создаётся при разрешённой реализации.
- D7: перестановка участников внутри каждой стороны Replacement не меняет domain semantic retry equality; роли сторон, состав, основания и прочие semantic fields значимы. Representation order сохраняется, prepare_section/assembler не сортируют. Publication exact request fingerprint, порядок patches и ordinal не меняются: равенство domain intent не означает равенство canonical bytes/request fingerprint.

Owning proposal уточнил технический параметр основания R: prepared/request/intent имеют [T,R]. Ниже A/B children закрывают [TestEntityA,TestAReason] и [TestEntityB,TestBReason]. TestAReason/TestBReason — owning synthetic typed reason records, не дубликаты entity payload. PatchSet поддерживает полную closed specialization двух параметров: число generic parameters не меняет native contract. Exact поля оснований и runtime wrong-pair admission сверяются с Lifecycle, не объявляются принятыми по D1–D7.

Дополнения acceptance matrix (проект тестов, не выполненный evidence): на mock_lifecycle_world проверить все 8 variants; отказ нескольких субъектов Create/End/Reactivate; many-to-many coverage без дубликатов/пропусков/подмены fingerprint; rejection NoDomainMutation до section success; Reactivate после End и отказ после Replacement; permuted same-side Replacement семантически равен при сохранённом representation order, смена роли/состава/reason — не равна. Отдельно подтвердить отсутствие нормализации Publication fingerprint. Fixture не обещает production storage/readiness.

2026-11-21. PROPOSED owning ответ на задание №2 [локального node-плана](gen-dag-lifecycle-node-contracts.md). Дизайн, без кода/миграций/назначения IDs. Ядро PatchSet не меняется. Scope: два synthetic entity вида, четыре перехода, одна native section, пять logical leaf операций, готовые inputs; real producers/storage/checkpoint/bulk/вариант Б вне scope и не blockers.

## 1. Рекомендация: восемь concrete native вариантов, одна секция

T — вид ссылки/участника, не полный предметный payload. TestEntityA/TestEntityB и closed request/prepared specializations размещать только в backend/tests/lifecycle/support/mixedContracts.py. Их owning generic bases остаются Lifecycle. Полные schemas/evidence/field/logic refusals предъявляет Lifecycle по node-плану: данное предложение фиксирует composition, не выдумывает поля этих POJO.

Предлагаемый owning generic wrapper в backend/app/dataModel/lifecycle/changes/transitionPatch.py:

```python
class LifecycleTransitionPatch[P: BaseModel](PatchData):
    prepared: P
```

Header объявлен только в PatchData. P на runtime binding обязан быть конкретным prepared record; BaseModel/unbound не допускаются. Prepared records не наследуют PatchData по принятому D1; старое «prepared = native patch» заменено этим решением. Поля prepared не копируются в wrapper, header не появляется у каждого участника Replacement.

Exact proposed synthetic declarations в tests/lifecycle/support/mixedContracts.py (generic imports из owning Lifecycle модулей):

```python
class CreateA(PreparedLifecycleCreate[TestEntityA, TestAReason]): pass
class CreateB(PreparedLifecycleCreate[TestEntityB, TestBReason]): pass
class ReplaceA(PreparedLifecycleReplacement[TestEntityA, TestAReason]): pass
class ReplaceB(PreparedLifecycleReplacement[TestEntityB, TestBReason]): pass
class EndA(PreparedLifecycleEnd[TestEntityA, TestAReason]): pass
class EndB(PreparedLifecycleEnd[TestEntityB, TestBReason]): pass
class ReactivateA(PreparedLifecycleReactivate[TestEntityA, TestAReason]): pass
class ReactivateB(PreparedLifecycleReactivate[TestEntityB, TestBReason]): pass

type PreparedAB = CreateA | CreateB | ReplaceA | ReplaceB | EndA | EndB | ReactivateA | ReactivateB

class CreatePatchA(LifecycleTransitionPatch[CreateA]): pass
class CreatePatchB(LifecycleTransitionPatch[CreateB]): pass
class ReplacePatchA(LifecycleTransitionPatch[ReplaceA]): pass
class ReplacePatchB(LifecycleTransitionPatch[ReplaceB]): pass
class EndPatchA(LifecycleTransitionPatch[EndA]): pass
class EndPatchB(LifecycleTransitionPatch[EndB]): pass
class ReactivatePatchA(LifecycleTransitionPatch[ReactivateA]): pass
class ReactivatePatchB(LifecycleTransitionPatch[ReactivateB]): pass

PatchAB = CreatePatchA | CreatePatchB | ReplacePatchA | ReplacePatchB | EndPatchA | EndPatchB | ReactivatePatchA | ReactivatePatchB

class LifecycleSectionAB(LifecycleSection[PatchAB, CoverageAB]): pass
class AssemblyInputAB(PatchSetAssemblyInput[LifecycleSectionAB]): pass
class PatchSetAB(PatchSet[LifecycleSectionAB]): pass
```

Все named children наследуют owning frozen/strict/extra-forbid/revalidate-always. Exact typed source tuple changes: tuple[PreparedAB,...] поступает в concrete specialization PrepareLifecycleSection, которую Lifecycle должен предъявить, сохранив остальные owning fields. Output: LifecycleSectionAB; actual public name LifecycleSection может быть именем конкретной composition, а не открытым runtime generic. Один shared lifecycle section key; значения key/format берутся из owning принятого контракта, здесь новые значения не назначаются.

prepare_section сохраняет порядок и делает ровно один wrapper на prepared transition. Закрытое соответствие prepared model -> patch model задаётся immutable construction binding Lifecycle; оно выбирает тип оболочки, не публичную операцию/маршрут. Это явная schema mapping, не скрытый entity-kind dispatch в DAG. Никаких fallback/lookup по строке вида/Any. Generic код не содержит if TestEntityA/TestEntityB. Typed mapping и exact construction admission принадлежат Lifecycle; если выбран алгоритм без table, он обязан предъявить эквивалентное сохранение prepared type. Отсутствие этого binding — локальный IN вопрос, не внешний producer blocker.

## 2. Дискриминация и codec

Рекомендация: plain closed union exact named model classes, wire discriminator — canonical RECORD type ID. Дополнительное поле kind, повторяющее класс операции/вид, не требуется. Не использовать smart-union parsing неразмеченных dict как доказательство сохранения T. На typed входе guard exact type(value) из roster выполняется до revalidation; неверная/чужая specialization отвергается, не пересобирается в другую. На decode canonical ID выбирает exact registered class, затем owning strict validation; никаких trial decode. Runtime identity после revalidation может измениться, concrete type/поля обязаны сохраниться.

Почему без Annotated discriminator на PatchAB: actual application/patch/contracts/sectionHandler.py::SectionContract.__post_init__ проверяет прямой Union/get_args в patches и не unwrap Annotated на этом месте. Plain PEP604 union проходит предусмотренную форму, каждый child наследует PatchData и сохраняет exact PatchHeader. Добавление Annotated потребовало бы отдельной правки shared admission, которая здесь не нужна.

LifecycleSectionCodec[LifecycleSectionAB] (generic notation target, owning точную class declaration подтверждает Lifecycle) использует общий encode/decode либо bounded decoder; codec.contract is handler.contract is зарегистрированный SectionContract[LifecycleSectionAB]. Registry.register(contract,handler,codec) — одна регистрация lifecycle key, не восемь. Native admission обеспечивает model/key/version, а не semantic applicability. PatchSetAssembler(AssemblyInputAB,PatchSetAB) сохраняет tuple patches; mixed A/B не меняет check_core/ordinal/prepared-order.

Synthetic manifest должен объявить section, 8 wrapper classes, 8 concrete prepared classes и transitive refs/evidence/enums; shared dependencies merge без переназначения IDs. Generic parents/type aliases не получают IDs автоматически. Номера здесь не назначены: test-ID allocation требует collision check. Unregistered/foreign ID, missing reachable type, wrong version/root — representation failure. Реальные producers/SQL для проверки не нужны; полноценный round-trip требует concrete owning prepared schemas внутри IN.

## 3. Logical NodeId и specialization: ограничение actual engine

Evidence: backend/app/application/engine/registration/nodeRegistry.py::_register хранит один binding по NodeId и отклоняет повтор; get(node_id,contract) требует exact identity contract. Engine не dispatch-ит регистрацию по T. Поэтому восемь A/B bindings четырёх операций нельзя зарегистрировать под четырьмя одинаковыми NodeId в одном registry. Closed union Input/Output сам по себе также не доказывает корреляцию: union допускает output B на input A без дополнительного dependent check.

**Рекомендуемый вариант для одного mixed synthetic графа:** сохранить пять logical leaf операций/общих реализаций, но явно назначить concrete registration identities четырём операциям на каждый T (8 concrete registrations) и один prepare_section для AB. Например, proposed qualified NodeId engine.lifecycle.test_a.prepare_create и engine.lifecycle.test_b.prepare_create; аналогично replacement/end/reactivate; section — одна. Это не новые операции, но дельта exact NodeId карты требует решения координатора/пользователя; не вводится молча. Named node input/output children и NodeContract для каждого T задаются composition; node просто input.request -> owning bound method -> output.value. Wrong-T input/output должен быть отвергнут exact admission, а не coerced. Сам public pipeline должен поддерживать agreed closed request/prepared child binding, а не возвращать bare parameterized generic; exact construction API предъявляет Lifecycle.

**Альтернатива при строгом сохранении ровно пяти concrete NodeId:** отдельные registry/composition A и B с одинаковыми logical IDs, по одному T в каждом; section AB можно проверять отдельно на готовых typed outputs. Это доказывает локальные leaf и mixed-section contracts, но НЕ демонстрирует одновременный A/B вызов в одном engine graph. Выбор registry по payload в ноде запрещён. Изменение engine key на (NodeId,specialization) — отдельный engine design, не предложение править ядро ради этой задачи.

## 4. Ответственность и критерии

| Класс/роль | Dependencies/effects | Критерий отказа |
|---|---|---|
| LifecycleTransitionPatch и 8 детей | PatchData + owning prepared, immutable data, no IO | Duplicate header/payload, unbound P или другой prepared type |
| 8 prepared children | Owning Lifecycle bases + synthetic T, no new fields | Полный entity payload, стёртый T, invented evidence |
| LifecycleSectionAB | DomainSection[PatchAB], no extra fields | Несколько section keys по T, reorder/drop или invalid nested patch |
| AssemblyInputAB/PatchSetAB | Existing shared parent roles | Переобъявление полей/разные section unions |
| SectionContract/Registry/codec | Existing C1 construction/representation, no semantic orchestration | Разные contract identities, Annotated несовместимый bound, codec вызывает handler |
| Closed node bindings | Existing NodeContract/executor, one owning call | Duplicate NodeId, payload-based runtime route, input A -> output B accepted |

Обязательные synthetic проверки: все 8 вариантов в одной секции с сохранением exact types/order/operands после round-trip; invalid A/B refs внутри Replacement; чужой prepared subclass/patch/header operation/section mismatch; ordinal uniqueness независимо identity; один Replacement с N участниками даёт один patch; N независимых transitions дают N patches без ограничения N=100; отказ без partial section; duplicate NodeId и wrong contract identity; static wrong-T rejection; missing/foreign schema ID; shared header/native fields compatibility. Это acceptance criteria, тесты не запускались.

## Итог IN/OUT

PASS feasibility closed native union без изменения PatchSet; D1–D7 приняты, prepared-vs-native выбор закрыт. OPEN внутри IN: техническая сверка предъявленных owning schemas/refusals, exact [T,R] producer/section construction mapping, final concrete NodeId registrations и synthetic manifest IDs/closure. Поля evidence/coverage сверяются только с active D4 без NoDomainMutation. Это не запрос реальных доменов/storage и не повторная постановка D1–D7 пользователю. H2 runtime diagnostic transport и atomic handler boundary согласуются отдельно с владельцами, generic ядро не переоткрывается. Code-go/полная приёмка не объявлены.
