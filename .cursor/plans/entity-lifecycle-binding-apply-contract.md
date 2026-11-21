# Lifecycle: единый owning контракт construction / lookup / apply

2026-11-21. Ответ на повторную сверку трёх IN-стыков координатором. Заменяет технические варианты C1–C3 в entity-lifecycle-local-contracts.md. D1–D7 приняты и не пересматриваются. Документальное техническое предложение для общего freeze; утверждение согласия всех владельцев не делается. Код/SQL/реальные producers/production wiring OUT. Общий node-план не редактируется.

Точный finite roster и единый carrier mock composition: [entity-lifecycle-mock-roster.md](entity-lifecycle-mock-roster.md). Девять Q/P bindings подтверждены; все apply participants используют exact MockSectionRefused с owning diagnostic subsets. Numeric IDs сводит PatchSet.

## Подтверждённые решения пользователя — 2026-11-21

Источник: gen-dag-lifecycle-node-contracts.md, «Подтверждённое решение пользователя — fingerprint и admitted view», передано координатором по поручению «верни обратную связь доменам как подтвержденное решение». Эти решения имеют приоритет над историческим отчётом §7 и противоположными предложениями владельцев:

1. Actual section fingerprint проверяется только в новой попытке, после claim/exact terminal replay, в общей dependency-binding фазе до первого handler.validate. Terminal replay не вычисляет section digests и не вызывает handlers. Expected-context/source bindings/H3, all-validate-before-apply и остальные стадии сохраняют утверждённый порядок.
2. Единственный API: PatchSet-owned application/patch/encoding/sectionFingerprint.py::SectionFingerprint(registry).fingerprint(section:DomainSection) -> RevisionHex. Формула — content_digest(registry.resolve_codec(section).encode(section)).hex(), existing checked codec и exact bytes. BoundSectionCodec.fingerprint отменён; Lifecycle не вызывает чужой codec/helper. Declared fingerprint готовит synthetic preparation/composition через этот же helper; Snapshot проверяет actual. Mismatch — owning Snapshot dependency refusal, codec/contract failure — existing fault transport.
3. Snapshot-owned AdmittedSectionView создаётся SnapshotAttemptContextBuilder из admitted request внутри attempt. Один immutable view через validation context используется validate/apply с exact request/scope/lifetime binding. Внешний LifecycleMockPreparedEvidenceBinding.from_request и mock context subclasses отменены. Это закрытые архитектурные решения, не code-go и не runtime-приёмка.

## 1. Один construction binding

Принимаю рекомендацию PatchSet как owning технический вариант: application/lifecycle/contracts/preparationBinding.py, frozen LifecyclePreparationBinding[Q,P] содержит только request_model:type[Q], prepared_model:type[P]. Это application configuration, не request POJO. Runtime Q/P — exact named closed models из roster 4 операций × A/B; generic BaseModel bounds не разрешают открытые runtime модели.

```python
class LifecycleCreatePipelineOpenPipeline[Q, P]:
    def __init__(self, *, binding: LifecyclePreparationBinding[Q,P],
                 policy: LifecyclePreparationPolicy) -> None: ...
    def prepare_create(self, request: Q) -> P | LifecycleFieldError | LifecycleLogicError: ...
```

Для Replacement/End/Reactivate — собственный метод prepare_replacement/end/reactivate и тот же двухполевой binding. LifecyclePreparationPolicy — уже описанная immutable owning policy/catalog, не внешний validator callback. Validator/builder — собственная внутренняя реализация, не независимо поставляемые несовместимые model factories.

При construction один раз через public model_fields извлекается цепочка prepared.transition → transition.participants element → participant.after, а из request — intent/capture/admission. Проверяются named concrete классы, закрытые T/R, strict/frozen/extra-forbid/revalidate, соответствие operation, exact identity request.intent и transition.intent, typed refs и before/after. Производные классы хранятся как private immutable construction result. Пяти независимо передаваемых model fields больше нет. Нет reflection по данным запроса или повторного parsing A→B при runtime.

Roster test-support неизменен: CreateRequestA/B → CreateA/B; ReplaceRequestA/B → ReplaceA/B; EndRequestA/B → EndA/B; ReactivateRequestA/B → ReactivateA/B. Concrete named intent/transition/participant/state/ref/capture/reason children находятся в backend/tests/lifecycle/support/mixedContracts.py. Q/P из разных T/R или wrong operation дают construction error. type(request) is binding.request_model обязательно; результат строится непосредственно binding.prepared_model(base=...,transition=named_transition(...)). Проверяется type(result) is prepared_model. Bare generic/subclass impostor не допускается.

Section binding, application/lifecycle/contracts/sectionBinding.py:

```python
class LifecycleSectionBinding[Q,S]:
    request_model: type[Q]
    section_contract: SectionContract[S]
    patch_bindings: tuple[LifecyclePatchModelBinding, ...]

class LifecyclePatchModelBinding[P,N]:
    prepared_model: type[P]
    patch_model: type[N]
```

Отдельного section_model нет: используется section_contract.section_model. Closed map type(prepared)→patch_model создаётся один раз из tuple, read-only. Keys ровно совпадают с request.changes union, values — section_contract.section_model.patches union; patch.prepared annotation exact identity. Section-level domain_evidence annotation проверяется согласно §2. Никаких дублирующих keys, fallback/issubclass dispatch или произвольных callbacks. Public prepare_section(Q) → S | LifecycleSectionRefused. Wrapper выбирается exact class, codec выбирает RECORD ID. Nested kind/operation только coherence.

## 2. Native representation и semantic coverage — актуальный owning ответ

2026-11-21. Принимаю section-level representation из актуальных PatchSet/Snapshot предложений как единый owning вариант для общей сверки. Ранее предложенный patch.evidence отменён. Это документальный контракт; общей приёмки и реализации не объявляет.

```python
class LifecycleTransitionPatch[P](PatchData):
    prepared: P

class LifecycleSection[P, C](DomainSection[P]):
    domain_evidence: tuple[C, ...]
```

Closed test roster: PatchAB = CreatePatchA | ReplacePatchA | EndPatchA | ReactivatePatchA | CreatePatchB | ReplacePatchB | EndPatchB | ReactivatePatchB; CoverageAB = CoverageA | CoverageB (existing named PreparedEffectBinding children). Оба — plain union values, не TypeAliasType. LifecycleSectionAB и PrepareLifecycleSectionAB используют один CoverageAB. Construction проверяет exact identity аннотаций request.domain_evidence/section.domain_evidence. Existing Q/P binding, immutable exact-class patch map и section_model только из SectionContract остаются.

prepare_section сохраняет каждый request.domain_evidence[i] в section.domain_evidence[i]: exact concrete type, поля, число и порядок; patch_refs также не переставляются. Object identity после revalidation не требуется. Ни группировки, ни копии evidence внутри patches нет. Связь с переходом — existing change_uid, с эффектом — typed entity/effect/action. Header dependencies — stable unique projection по порядку первого появления section dependencies в domain_evidence; конфликт fingerprints для одного key отвергается. PatchHeader.depends_on не превращает coverage в apply-order edges.

### 2.1. Synthetic предметные данные: что именно является payload

Все нижние новые классы — PROPOSED test-support declarations в backend/tests/lifecycle/support/domainSections.py, producer/verifier в subjectMock.py, binding в evidenceBinding.py. Они принадлежат mock предметному участнику, не production dataModel Lifecycle. A/B — named closed варианты для уже принятого T_A/T_B. Strict/frozen/extra-forbid; вложенные tuples immutable. Existing DomainEffect, DomainAdmission, PreparedEffectBinding, SectionHeader/PatchHeader, WorldPublicationRef и H2 transport переиспользуются без копий.

Предмет mock — две записи существования одной typed сущности: slot Literal['primary','index']. Это явная искусственная семантика mock_lifecycle_world, не требования реальному домену. Чтобы реализовать один effect, предметный batch обязан изменить обе записи; поэтому один effect может требовать несколько patches. Один patch может содержать изменения нескольких сущностей.

| Named family / поля | Ответственность и invariants |
|---|---|
| MockMutationA/B: entity:RefA/B; slot:Literal['primary','index']; before:bool\|None; after:bool; action_uid:EntityUid | Actual native subject payload. None означает отсутствие записи. Допустимые пары только (None,True)=create, (True,False)=end, (False,True)=reactivate. Это изменение предметной записи, а не копия заявленного effect |
| MockBatchA/B: mutations:NonEmpty[MockMutationA/B] | Группа payload mutations, из которой строится один native patch; duplicate (entity,slot) запрещены во всей секции |
| TestDomainPatchA/B(PatchData): base:WorldPublicationRef; mutations:NonEmpty[MockMutationA/B]; effects:NonEmpty[EffectA/B] | Сохраняет actual payload и проверяемое заявление effects. effects — stable unique projection mutations через указанную таблицу, typed entity + action; эффект встречается в patch один раз, даже если обе записи внутри него |
| TestDomainSectionA/B(DomainSection): patches:NonEmpty[TestDomainPatchA/B] | Для каждого (entity,action,effect) во всей секции должны присутствовать ровно primary и index с одинаковой парой before/after. Одна entity не участвует в двух actions данного batch |
| MockSubjectObservationA/B: entity:RefA/B; slot:Literal['primary','index']; value:bool\|None | Authoritative accepted значение собственной mock записи, None только подтверждённое отсутствие |
| MockSubjectCaptureA/B: publication:WorldPublicationRef; observations:tuple[MockSubjectObservationA/B,...] | Exact requested entity/slot coverage без missing/extra/duplicates; неполный источник не означает отсутствие |
| MockSubjectIssue(FieldPathError[MockSubjectCode]) | Единственный test-owned typed diagnostic; поля existing code/path/message. Codes INVALID_MUTATION, EFFECT_PAYLOAD_MISMATCH, INCOMPLETE_EFFECT, SUBJECT_BEFORE_MISMATCH. Не дублирует Lifecycle relation diagnostic |

Этот payload достаточен для конкретного synthetic доказательства: effect вычисляется из изменения двух предметных записей. Поле effects само по себе доказательством не является. Реальная subject семантика и новые producers OUT.

### 2.2. Exact producer/verifier contracts и границы вызовов

A signatures ниже повторяются для B с exact named B types; открытый generic/Any не является runtime output. Все helpers — test fixture или внутренний алгоритм своего handler, не новые публичные DAG pipelines и не новые ноды.

1. MockSubjectProducerA.prepare(request:PrepareMockSubjectA) -> PreparedMockSubjectA | MockSectionRefused.
   PrepareMockSubjectA имеет publication:WorldPublicationRef, operation_id:EntityUid (тот же existing UID type, что PatchRef.operation_id), batches:NonEmpty[MockBatchA]. PreparedMockSubjectA имеет section:TestDomainSectionA, admissions:NonEmpty[AdmissionA].
   Producer проверяет допустимые mutations, уникальность entity/slot и полноту пары slots, назначает headers из operation_id, test-owned fixed section key/version и batch ordinals. Формирует effects из payload, admissions группирует по action_uid в порядке первого появления: publication=request.publication, action_uid и stable unique effects из batch. Не читает accepted storage, не объявляет commit и не назначает change_uid. Refused producer diagnostics адресуют batches[i].mutations[j].before/after либо batches; category REJECTED. Никаких чужих prepare/codec calls.

2. MockSubjectPayloadVerifierA.verify(section:TestDomainSectionA) -> SectionAccepted | MockSectionRefused.
   Собственный pure алгоритм verifier повторно выводит effects из mutations, сверяет их точный набор/порядок и полноту двух slots по секции. Неверная пара before/after → INVALID_MUTATION, path patches[p].mutations[m].after; ложные effects → EFFECT_PAYLOAD_MISMATCH, path patches[p].effects; missing slot → INCOMPLETE_EFFECT, path patches (существующая коллекция). Category REJECTED: это внутренне ложное subject предложение, а не конфликт Lifecycle с admitted view. Verifier не вызывает Lifecycle и не зависит от результата другого validate. Producer и handler используют один этот алгоритм проверки, без двух реализаций semantic правила.

3. MockSubjectHandlerA.validate(section:TestDomainSectionA, context:SnapshotValidationContext) -> SectionAccepted | MockSectionRefused, async.
   Внутренне вызывает свой MockSubjectPayloadVerifierA.verify; затем свой IMockSubjectReaderA.read_for_section(section, *, publication:WorldPublicationRef, scope:CommitReadScope) -> MockSubjectCaptureA, async. Reader возвращает exact observations для всех mutations при context.expected_world. Handler проверяет base/context equality и current value == mutation.before для каждой записи. Known mismatch → SUBJECT_BEFORE_MISMATCH/CONFLICT, path patches[p].mutations[m].before. Missing/unknown/malformed capture или scope mismatch → existing infrastructure contract fault, не SectionAccepted.
   Для локального mock намеренно строгий before-state: повтор mutation после уже изменённой записи отказывает. Lifecycle equal retry не обещает subject idempotence. Повтор той же уже принятой publication может завершаться общим publication retry до нового attempt по existing протоколу; новый attempt с equal lifecycle change всё равно проверяет subject before.
   Его apply сохраняет mutations только в собственном bound mock storage после успеха всех validates; commit не выполняет. H2 closure synthetic результата включает этот diagnostic, без новых production IDs/carriers.

4. MockLifecycleEvidenceBuilderA.build(request:BuildMockEvidenceA) -> tuple[CoverageA,...] | LifecycleSectionRefused.
   BuildMockEvidenceA имеет section:TestDomainSectionA, dependency:PreparedSectionDependency, links:NonEmpty[MockEffectLinkA]; MockEffectLinkA имеет change_uid:EntityUid, effect:EffectA. Links поступают из подготовленных Lifecycle transitions через test fixture, не через вызов Lifecycle из subject producer.
   Builder связывает каждый link с ВСЕМИ patches этой section, содержащими такой exact effect; patch_refs сохраняют section patch order. Проверяет key/ref operation coherence, unique links и ненулевое coverage. Формирует existing CoverageA(kind='prepared',change_uid,effect,section=dependency,patch_refs). Не вычисляет fingerprint: dependency — готовый выход принятой representation границы (synthetic composition вычисляет его через SectionFingerprint для окончательной subject section); здесь только structural check. Refusal переиспользует LifecycleRelationIssue: COVERAGE_MISSING на links[i].effect при отсутствии соответствующих patches; COVERAGE_DUPLICATE на links[i] при повторе ключа; PATCH_SECTION_MISMATCH на dependency.section_key при чужом key; PATCH_OPERATION_MISMATCH на section.patches[p].header.ref.operation_id при неоднородных operation IDs. related_path=None, кроме сравнения двух существующих полей данного BuildMockEvidenceA. Эти реальные request paths дополняют path binding именно test-helper, не меняют paths публичного PrepareLifecycleSection. Его успех не заменяет subject validate или admission hash verification.

Подготовка fixture подаёт admissions в соответствующие pure Lifecycle requests и готовые CoverageA/B в prepare_section. Это описание fixture data assembly, не разрешение перестроить DAG или добавить pipeline orchestration. Own subject handler запускает Snapshot в уже принятой общей participant фазе; Lifecycle не вызывает subject producer/verifier/reader/codec.

### 2.3. Exact operands и consumers после упаковки

Обозначения: N = LifecycleSectionAB; P = локальная immutable typed projection TestDomainSectionA/B из общего AdmittedSectionView; C = validation context с принятым полем admitted_sections; L = собственный AcceptedChangesResultAB; V = собственные CaptureA/B. Способ доставки принят, но ещё не объявляется реализованным. Projection не хранит request, не создаёт context и не является отдельным proof/capability.

| Predicate / проверяющий | Typed operands и источник | Native сохранение / mapping | Outcome |
|---|---|---|---|
| Actual payload реализует заявленный effect — MockSubjectPayloadVerifierA/B.verify | TestDomainPatch.mutations (entity,slot,before,after,action_uid), TestDomainPatch.effects | Оба поля внутри subject native section проходят codec. Сравнение с вычисленной проекцией и полнотой primary/index | Subject REJECTED по §2.2, не Lifecycle успех |
| Subject before соответствует Q — MockSubjectHandlerA/B.validate | patch.base; C.expected_world; capture.publication/observations собственного reader | base в каждом subject patch; observations только собственный scoped read | SUBJECT_BEFORE_MISMATCH/CONFLICT либо infrastructure fault |
| Lifecycle base и publication operation — Lifecycle relational validator | N.patches[p].prepared.base; C.expected_world; N/subject patch.header.ref.operation_id; C.operation_id | Existing headers/base, operation_id не равен change_uid/action_uid по назначению | Context/admission incoherence → contract fault; stale head — общий Snapshot outcome |
| Полнота ожидаемых effects — Lifecycle relational validator | transition intent/participants/reason.action_uid; N.domain_evidence[i].change_uid/effect | Ровно один entry на (change_uid,entity,effect); Replacement даёт end predecessors/create successors | Pure coverage refusal до build; malformed bypass → contract fault |
| Native subject claim связан с evidence — Lifecycle relational validator | N.domain_evidence[i].effect/section/patch_refs; P.patch.effects/base/header | Для entry найти exact section, затем ВСЕ patches с exact typed effect; предъявленный refs tuple обязан совпасть с ними в native patch order. Entity/action/effect/base должны совпасть. Many-to-many сохранён | Complete P contradicts claim → EVIDENCE_MISMATCH/CONFLICT на domain_evidence[i].effect, .patch_refs или .patch_refs[k] |
| Section content binding — Snapshot dependency binding, потребитель Lifecycle | evidence.section.section_key/section_fingerprint; N.header.depends_on; фактическая admitted section из P; C.resolved_dependencies | Snapshot проверяет через SectionFingerprint в новой попытке после replay до первого validate; Lifecycle сверяет evidence с объявленной/разрешённой dependency, не пересчитывает hash | Snapshot dependency refusal на hash mismatch; codec failure или отсутствующий promised binding/view → existing fault |
| Retry/current lifecycle — own lookup и reader | L по change refs; V при Absent; N.prepared.transition | Found equal по D7 → no-op только Lifecycle; unequal → conflict; Absent сверяется с own before/last transition | Existing CHANGE_PAYLOAD_CONFLICT/BEFORE_STATE_MISMATCH; coverage всё равно проверяется |
| Все semantic predicates истинны перед writes — Snapshot aggregate phase | Existing outcomes всех registered subject и Lifecycle handlers | Не POJO witness success, не mutable proof-cache: неизменные исходные operands + общий барьер всех validate | Любой отказ запрещает все apply/commit; порядок validates не влияет на истинность |

Lifecycle relational validator: application/lifecycle/validation/evidenceValidator.py::LifecycleEvidenceValidator.validate(section:LifecycleSectionAB, *, prepared_domain_sections:tuple[TestDomainSectionA|TestDomainSectionB,...], expected_world:WorldPublicationRef, operation_id:EntityUid) -> SectionAccepted | MockSectionRefused в test binding. Production algorithm не импортирует test classes: этот exact closed binding находится в tests/lifecycle/support/evidenceBinding.py; production generic definition замыкается composition. Validator — внутренняя часть Lifecycle handler, не public DAG leaf. Его задача — relations по публичным effects, а не вывод effects из чужого payload. Отдельного witness DTO не нужно: публичный native effects — immutable claim, а его истинность проверяется subject validate до любого apply.

Принятый producer: SnapshotAttemptContextBuilder.build(request, *, scope, resolved_dependencies) -> SnapshotValidationContext; перед dispatch Snapshot вызывает assert_bound(context, *, request, scope). Context и view создаёт только Snapshot из admitted request. Его request identity после admission/decode, active read scope и зарегистрированный roster — общие invariants; равного operation_id недостаточно. Revalidation handler section может создать равный экземпляр, поэтому его object identity с исходной section не требуется.

Exact consumer mapping: LifecycleSectionHandler.validate(N, context) читает context.admitted_sections; apply(N, context) — context.validation.admitted_sections. Для каждого N.domain_evidence[i] собственный closed immutable map CoverageA→TestDomainSectionA, CoverageB→TestDomainSectionB выбирает модель, затем view.require(entry.section.section_key, model=TestDomainSectionA/B) возвращает exact named section. Общий require[S:DomainSection](key:SectionKey, *, model:type[S])->S проверяет active scope/key/exact registered model; missing key, wrong model или expired scope — contract fault, не пустая секция. Handler передаёт найденные immutable sections собственному LifecycleEvidenceValidator как typed projection P; один key извлекается один раз в порядке первого появления evidence. Никакого foreign verifier/codec callback, создания второго context, сохранения request или mutable proof-cache. Apply потребляет тот же view, а не latest или результаты промежуточных writes. Внешний LifecycleMockPreparedEvidenceBinding.from_request отменён.

### 2.4. Обязательные synthetic acceptance cases

- Valid fingerprint, false native effect: mutations (True,False) при заявленном create. Common hash может пройти; MockSubjectPayloadVerifier выдаёт EFFECT_PAYLOAD_MISMATCH/REJECTED. Даже если Lifecycle relations согласны с ложным claim, общий barrier запрещает apply.
- Valid subject payload/effects=end, но N.domain_evidence.effect=create: subject validate может пройти; Lifecycle выдаёт EVIDENCE_MISMATCH/CONFLICT. Это другой predicate и другой владелец ошибки.
- Equal Lifecycle retry + отказ subject: L содержит equal transition; текущая subject запись уже after, предложение повторяет старый before. Subject handler возвращает SUBJECT_BEFORE_MISMATCH; Lifecycle no-op не подавляет отказ, ни один apply не запускается.
- Many-to-many: patch0 содержит primary(entity1) и primary(entity2), patch1 — index(entity1) и index(entity2). Для effect1 и effect2 coverage содержит refs=(patch0,patch1). Два эффекта ссылаются на два общих patches; удаление любого ref не проходит exact coverage.
- Порядок validates переставлен (Lifecycle раньше subject и наоборот): результат одинаков, отсутствуют proof-cache/foreign calls/writes до общего успеха.
- Forged ordinal/action/entity/base, missing promised view и другой admitted request различаются как доказанный relation conflict либо infrastructure fault; отсутствие данных никогда не выдаётся за semantic success.

### 2.5. Статус и ответственность

Закрыто в owning предложении: representation disagreement (section-level exact copy); source actual payload→effect; exact producer/verifier/reader inputs/results/errors; subject vs Lifecycle predicates; many-to-many и equal-retry негативные критерии. Это документальная полнота предложения, не пройденные runtime tests и не общая приёмка.

Delivery/lifetime capability, единственный section fingerprint API и фаза его проверки закрыты подтверждённым решением пользователя. Остаётся общая проверка согласованности H2 closure/manifest и Output→Input, а при разрешённой реализации — обязательные тесты этих контрактов; три принятых выбора больше не OPEN. OUT: реальные предметные domains/producers/SQL, production wiring, parent Б, checkpoint. Принятый DAG порядок и D1–D7 неизменны.

## 3. Accepted-change lookup — один вариант

Сохраняется owning dataModel/lifecycle/storage/acceptedChanges.py:

- AcceptedChangesQuery(publication:WorldPublicationRef, refs:NonEmpty[LifecycleTransitionRef]); refs unique.
- AcceptedChangeAbsent(kind:Literal['absent'], ref:LifecycleTransitionRef).
- AcceptedChangeFound[C](kind:Literal['found'], ref:LifecycleTransitionRef, transition:C).
- AcceptedChangesResult[E](publication:WorldPublicationRef, entries:tuple[E,...]); exact request order/coverage, без missing/extra/duplicate.

C — closed union восьми named transitions, E — named FoundAB | Absent. application/lifecycle/storage/participantPort.py::ILifecycleAcceptedChangesReader[Result].lookup_accepted_changes(request:AcceptedChangesQuery, *, scope:CommitReadScope) → Result (async), Result=AcceptedChangesResultAB в mock. Не AcceptedChangesRequest, не ILifecycleAcceptedChanges.read. Current read_for_section(section:L, *, publication:WorldPublicationRef, scope:CommitReadScope) → tuple[CaptureA | CaptureB,...] отдельно; captures не являются историей. Один capture на представленный вид, exact requested publication, полный набор requested entity observations. Все чтения собственного accepted view, без foreign read.

Unknown/incomplete/unavailable lookup — infrastructure fault; отсутствие индекса не Absent. Found+equal по D7 → no-op без проверки старого before против изменившейся current projection. Found+different → CHANGE_PAYLOAD_CONFLICT. Absent → current before-state check. Обязательное coverage сохраняется и для equal retry; другой synthetic participant обязан выполнить собственную идемпотентность. No-op Lifecycle не разрешает повторную предметную мутацию.

## 4. Одна apply-диагностика и carrier

Owning выбор: LifecycleApplyIssue(FieldPathError[LifecycleApplyCode]) с existing code/path/message; без proposed/accepted payload copies. Carrier — единый named MockSectionRefused(SectionRefused[MockDiagnostic]), MockDiagnostic = LifecycleApplyIssue | MockSubjectIssue. Все три registry handler bindings используют exact refusal_model is MockSectionRefused; Lifecycle возвращает только свой subset, subject — свой. Отдельные concrete domain carriers отменены, общий H2 transport переиспользуется. Отдельные три relation DTO и LifecycleApplyRefused не вводятся: у каждого отказа есть реальный native operand. Pure LifecycleSectionRefused не используется в apply. Paths принадлежат concrete LifecycleSectionAB, не prepare request.

| Code | Category | Реальный operand path | Почему |
|---|---|---|---|
| CHANGE_PAYLOAD_CONFLICT | CONFLICT | patches[i].prepared.transition.intent.change_uid | UID в текущем предложении уже занят другим accepted transition; stored payload не нужно копировать в диагностику |
| BEFORE_STATE_MISMATCH | CONFLICT | patches[i].prepared.transition.participants[j].before | Новый переход предъявляет состояние, несовместимое с authoritative exact base |
| EVIDENCE_MISMATCH | CONFLICT | domain_evidence[i].patch_refs[k], .effect или .section — по нарушенному отношению | Well-typed binding противоречит фактически admitted совместным данным; конфликт двух проверяемых значений, не ошибка синтаксиса |

Все три — CONFLICT. Прежний выбор REJECTED для EVIDENCE_MISMATCH отозван: в apply здесь диагностируется расхождение с authoritative/admitted view. Malformed input, неизвестная schema, неполный promised view — structural/infrastructure failure existing transport; категория CONFLICT не маскирует отсутствие данных. Неверный coverage до prepare success остаётся pure LifecycleSectionRefused. Если future semantics потребует отдельного REJECTED, нужен отдельный определённый owning predicate, а не переиспользование этого кода.

evidence_index отдельно не хранится: i/k адресуются existing CheckedPath к реальному section.domain_evidence. Relation к одному patch и его эффекту указывает соответствующее поле; отсутствующий referenced ref адресует предъявленный patch_refs[k], не несуществующий чужой элемент. Порядок evidence issues — section evidence/ref index; transition issues — patch/participant index. Multiple independent conflicts собираются до записи. No invented path и нет второго класса для той же ошибки.

LifecycleApplyCode/Issue и closure model identities регистрируются в test-only H2 D/result/manifest. Не меняются production TimeSnapshotApplyResult/root20150 или existing numeric IDs. FieldPathError subclass совместим и с actual SectionRefused.diagnostics; H2 generic specialization не требует нового transport. No legacy adapters.

## 5. Append и no-op

LifecycleAppended(state:SectionStateRetention | None, history:SectionHistoryRetention | None, changed:tuple[PatchRef,...]) сохраняется. LifecycleAppendResult = LifecycleAppended | MockSectionRefused в H2 (target composition carrier; actual nongeneric SectionRefused не объявляется готовой H2 реализацией). Handler.validate → SectionAccepted | MockSectionRefused; apply → SectionApplyReceipt | MockSectionRefused. Writer bound scope, append(section,expected,target) без commit/rollback.

All-equal batch: state=None/history=None/changed=(); receipt states=()/history=()/changed=(). Snapshot наследует pinned state по C2, новая state/history ссылка не создаётся. Mixed batch пишет только новые transitions; changed — исходные PatchRefs новых переходов в порядке section. Новые refs относятся к assigned target; inherited history не возвращается. Один конфликт запрещает весь append. Writer повторяет authoritative проверки в том же scope перед writes. Snapshot C2/CAS/terminal/confirmed commit остаются обязательными. Domain equality D7 не нормализует Publication immutable request fingerprint.

## 6. Точные remaining differences и тестовые обязательства

Owning выбор един: двухполевой preparation binding; section binding без section_model; AcceptedChangesQuery/lookup_accepted_changes; LifecycleApplyIssue + SectionRefused, все три codes CONFLICT; прежний no-op mapping. Это предложение заменить несовместимые варианты Snapshot/PatchSet, не заявление, что их документы уже синхронизированы.

Статус двух дельт после подтверждённого решения:

1. PatchSet: section-level domain_evidence по §2, wrapper header+prepared, восемь concrete bindings и manifest closure. Representation disagreement устранён в owning предложении; numeric IDs отдельно, не назначаются здесь.
2. Snapshot: приняты AdmittedSectionView/SnapshotAttemptContextBuilder и SectionFingerprint по начальному разделу. Mock context extension и внешний producer binding отменены. Lifecycle читает context.admitted_sections.require; apply — context.validation.admitted_sections. Выбор API/фазы/доставки закрыт; реализация и проверка общего flow не объявляются готовыми.

Synthetic tests для реализации: exact named output/map; неправильный T/R при construction; immutable binding; lossless request evidence→section evidence; decode с типами; forged ordinal/effect/action/base/fingerprint; well-typed contradiction даёт реальный EVIDENCE_MISMATCH path/CONFLICT; отсутствие promised view даёт contract fault; equivalent accepted retry без отката current projection; mixed/no-op receipts; atomic rollback всех participants. D1–D7, production OUT и порядок DAG не переоткрываются. Реализация не выполнялась; ограниченная проверка codec описана ниже и не заменяет эти тесты.

## 7. Результат технической проверки — 2026-11-21

По поручению пользователя «Проведи» проверены две границы. Это проверка осуществимости предложения и наличия возможностей в текущем коде, не приёмка общей цепочки и не разрешение реализации.

Уточнение после проверки: рекомендация DAG-координатора хранить exact request.domain_evidence на уровне section.domain_evidence (types/values/order), оставив wrapper header+prepared, теперь отражена в активных §§1–2,4. Описанный ниже smoke относится к прежнему предложению patch.evidence и не выдаётся за проверку новой section-level схемы. Прежние wrapper [P,E] и paths patches[i].evidence[j] отменены. Вывод о недостаточности текущего prepared view/fingerprint остаётся в силе при обоих размещениях evidence.

### Native evidence и canonical codec — ограниченный PASS

Existing `backend/app/application/patch/contracts/sectionHandler.py::SectionContract` допускает concrete PatchData с дополнительными типизированными полями. `backend/app/encoding/canonicalCodec.py` кодирует declared model_fields и восстанавливает concrete RECORD types по manifest. Поэтому предложенное поле patch.evidence не требует изменения общего формата codec.

Выполнен одноразовый in-memory smoke через backend/.venv/Scripts/python.exe -B, без создания файлов: восемь named native вариантов (A/B × четыре операции), prepared и nonempty typed evidence, closed union секции и временный manifest. Проверены construction SectionContract, canonical round-trip с сохранением точных классов native patches/evidence, отказ на evidence другого вида и изменение content digest при изменении evidence patch ordinal. Все проверки прошли. Временные RECORD IDs не регистрировались в проекте.

Граница доказательства: это минимальная форма восьми вариантов, не полные Lifecycle schemas. Не проверены полная closure будущего manifest, назначение постоянных IDs, полный request→native mapping и интеграция atomic apply. Дополнительные поля совместимы с механизмом кодирования; принятие самой native-дельты остаётся предметом общей сверки.

### Prepared view и fingerprint — историческая проверка runtime, до принятия архитектурного решения

`backend/app/application/worldSnapshot/contracts/context.py::SnapshotValidationContext` не содержит предметных native sections. `resolved_dependencies` содержит заявления о зависимостях, но не даёт операндов для проверки ordinal/effect. `backend/app/application/patch/encoding/patchSetCodec.py::fingerprint` вычисляет digest всего request; это не доказательство равенства section_fingerprint содержимому конкретной секции. `backend/app/application/patch/registry/boundSectionCodec.py` обеспечивает привязку модели/key/version и encode/decode, но сам не сверяет dependency fingerprint. В просмотренном application-коде вычисление и сравнение section_fingerprint с фактическим содержимым секции не обнаружено.

Архитектурный выбор, отсутствовавший на момент этой проверки, теперь закрыт начальным разделом: SectionFingerprint и Snapshot-owned AdmittedSectionView, dependency binding после replay и до validate. Результат чтения runtime выше не отменяет принятие дизайна. Hash доказывает привязку к содержимому; смысл effects по-прежнему проверяет предметный participant.

Обязательные проверки реализации в mock_lifecycle_world: (1) view связан с тем же admitted immutable request/scope; (2) fingerprint проверяется по exact section bytes после replay только в новой попытке; (3) подмена request/секции/fingerprint не проходит; (4) ложный native effect отвергает subject verifier, неверную relation evidence→effect — Lifecycle с реальным domain_evidence[i] path; (5) отсутствие view/expired scope даёт contract fault; (6) terminal replay не вызывает section fingerprint helper/handlers; (7) актуальная section.domain_evidence проходит round-trip с exact types/values/order и отрицательные проверки. Старый patch.evidence smoke не заменяет эти тесты. Это локальная synthetic проверка, без production wiring, SQL и новых DAG nodes; архитектурные решения приняты, runtime PASS не объявляется.
