# Lifecycle: конечный owning roster mock composition

2026-11-21. Ответ владельца Lifecycle на шаги 1–2 координатора: gen-dag-lifecycle-node-contracts.md и lifecycle-mock-result-manifest.md. Документальный контракт для mock_lifecycle_world, без кода и numeric IDs. Этот файл уточняет concrete names/closure и единый apply carrier в entity-lifecycle-binding-apply-contract.md; предметная семантика, pure outputs и принятые fingerprint/view решения не меняются. Shared coordinator файлы не редактируются.

## 1. Девять Q/P bindings — подтверждены

| NodeId = ContractId | Named input → Q | Named output → success P | Public method |
|---|---|---|---|
| engine.lifecycle.test_a.prepare_create | CreateNodeInputA → CreateRequestA | CreateNodeOutputA → CreateA | LifecycleCreatePipelineOpenPipeline.prepare_create |
| engine.lifecycle.test_b.prepare_create | CreateNodeInputB → CreateRequestB | CreateNodeOutputB → CreateB | LifecycleCreatePipelineOpenPipeline.prepare_create |
| engine.lifecycle.test_a.prepare_replacement | ReplaceNodeInputA → ReplaceRequestA | ReplaceNodeOutputA → ReplaceA | LifecycleReplacementPipelineOpenPipeline.prepare_replacement |
| engine.lifecycle.test_b.prepare_replacement | ReplaceNodeInputB → ReplaceRequestB | ReplaceNodeOutputB → ReplaceB | LifecycleReplacementPipelineOpenPipeline.prepare_replacement |
| engine.lifecycle.test_a.prepare_end | EndNodeInputA → EndRequestA | EndNodeOutputA → EndA | LifecycleEndPipelineOpenPipeline.prepare_end |
| engine.lifecycle.test_b.prepare_end | EndNodeInputB → EndRequestB | EndNodeOutputB → EndB | LifecycleEndPipelineOpenPipeline.prepare_end |
| engine.lifecycle.test_a.prepare_reactivate | ReactivateNodeInputA → ReactivateRequestA | ReactivateNodeOutputA → ReactivateA | LifecycleReactivatePipelineOpenPipeline.prepare_reactivate |
| engine.lifecycle.test_b.prepare_reactivate | ReactivateNodeInputB → ReactivateRequestB | ReactivateNodeOutputB → ReactivateB | LifecycleReactivatePipelineOpenPipeline.prepare_reactivate |
| engine.lifecycle.prepare_section | SectionNodeInputAB → PrepareLifecycleSectionAB | SectionNodeOutputAB → LifecycleSectionAB | LifecycleSectionPipelineOpenPipeline.prepare_section |

Все девять NodeContract[I,O,Never]: version=ContractVersion('1'), reads=(), calls=(), error_types=(); continuation/input_wait/retry_policy/error_policy/lifecycle/validator=None. Input только request; Output только value. Первые восемь value = exact P | LifecycleFieldError | LifecycleLogicError; последний = LifecycleSectionAB | LifecycleSectionRefused. Никакого MockSectionRefused в pure outputs. Runtime faults/cancellation — engine transport. Q/P exact class binding, единый exact contract object у executor/CallTarget, без payload dispatch и повторной сборки результата. Node wrappers находятся только в backend/tests/lifecycle/support/nodeContracts.py, bindings — nodeBindings.py. Их сериализация не требуется текущими native/terminal roots.

## 2. Единый composition carrier — owning подтверждение

Именованные composition declarations находятся только в backend/tests/lifecycle/support/resultContracts.py:

```python
MockSectionUnion = LifecycleSectionAB | TestDomainSectionA | TestDomainSectionB
MockDiagnostic = LifecycleApplyIssue | MockSubjectIssue

class MockSectionRefused(SectionRefused[MockDiagnostic]): ...
class MockSnapshotApplyResult(SnapshotApplyResult[MockDiagnostic]): ...
```

Это target H2 generic construction; actual nongeneric SectionRefused/SnapshotApplyResult не выдаются за готовую реализацию. MockSectionRefused не добавляет полей или предметных codes: category и nonempty diagnostics наследуются. Все три handler bindings в одном SectionRegistry[MockDiagnostic] имеют refusal_model is MockSectionRefused. Отдельные SectionRefused[LifecycleApplyIssue]/SectionRefused[MockSubjectIssue] как concrete runtime return classes отменены. Generic specialization без named child и subclass impostor не допускаются.

| Producer / consumer | Exact result / разрешённый subset |
|---|---|
| LifecycleSectionHandler.validate | SectionAccepted \| MockSectionRefused; diagnostics только exact LifecycleApplyIssue |
| LifecycleSectionHandler.apply | SectionApplyReceipt \| MockSectionRefused; тот же subset |
| LifecycleEvidenceValidator.validate | SectionAccepted \| MockSectionRefused; тот же subset |
| Lifecycle participant append | LifecycleAppended \| MockSectionRefused; тот же subset |
| MockSubjectHandlerA/B.validate | SectionAccepted \| MockSectionRefused; diagnostics только exact MockSubjectIssue |
| MockSubjectHandlerA/B.apply | SectionApplyReceipt \| MockSectionRefused; тот же subset |
| MockSubjectPayloadVerifierA/B.verify | SectionAccepted \| MockSectionRefused; тот же subject subset |
| MockSubjectProducerA/B.prepare | PreparedMockSubjectA/B \| MockSectionRefused; subject subset, runtime fixture result |
| MockLifecycleEvidenceBuilderA/B.build | tuple[CoverageA/B,...] \| LifecycleSectionRefused; pure helper, вне apply carrier |

Вертикальная черта в result означает union, не новый DTO. Общий registry знает закрытый MockDiagnostic; owning handlers перед возвратом проверяют свои subsets и category/code/path invariants. Wrong carrier/чужой diagnostic — execution contract fault, не новый business refusal. Lifecycle issues всегда CONFLICT. Subject INVALID_MUTATION/EFFECT_PAYLOAD_MISMATCH/INCOMPLETE_EFFECT — REJECTED; SUBJECT_BEFORE_MISMATCH — CONFLICT. Structural verifier выполняется перед subject state check; mixed-category subject refusal не создаётся. Snapshot не копирует эти predicates, использует H2 construction и переносит diagnostics без стирания concrete типов, порядка и paths.

MockSnapshotApplyResult.diagnostics = tuple[SnapshotApplyRelationIssue | LifecycleApplyIssue | MockSubjectIssue,...]. SnapshotApplyRelationIssue принадлежит общему result admission; не разрешён как diagnostic, произведённый subject/Lifecycle handler. Один PublicationResultBinding[MockSnapshotApplyResult], одна согласованная specialization OperationRecord и codec/store/claim/replay без adaptation. Concrete имя/конструкция operation record принадлежат Snapshot; Lifecycle не создаёт вторую record model. MockAssemblyInput/MockPatchSet используют MockSectionUnion; MockApplySnapshotInput — этот MockPatchSet. Эти composition wrappers не получают wire IDs без serialized root.

## 3. Полный новый owning wire roster

Ниже перечислены ВСЕ новые Lifecycle/subject concrete records, достижимые из native sections и двух owning terminal diagnostics. Сокращения A/B в описаниях обозначают пары явно перечисленных named классов, не runtime generic. Один literal kind T_A='test_entity_a', T_B='test_entity_b'; literals/aliases/tuple/NonEmpty не получают ENUM/RECORD ID. Generic parents тоже не регистрируются вместо named children.

Synthetic declarations — backend/tests/lifecycle/support/mixedContracts.py (Lifecycle named closures), domainSections.py (subject native classes). Общие негeneric LifecycleTransitionRef, LifecycleOperation и LifecycleApplyIssue/Code — owning generic-domain declarations в ранее заданных dataModel/lifecycle модулях; тестовый manifest включает их, production composition этим не расширяется. MockSubjectIssue/Code — test-support subjectMock.py. Нижние concrete field annotations явно сужаются до named children, без анонимных параметризованных Pydantic типов.

### 3.1. Native operations: 32 RECORD

| Native wrapper | prepared | transition | intent |
|---|---|---|---|
| CreatePatchA | CreateA | CreateTransitionA | CreateIntentA |
| CreatePatchB | CreateB | CreateTransitionB | CreateIntentB |
| ReplacePatchA | ReplaceA | ReplaceTransitionA | ReplaceIntentA |
| ReplacePatchB | ReplaceB | ReplaceTransitionB | ReplaceIntentB |
| EndPatchA | EndA | EndTransitionA | EndIntentA |
| EndPatchB | EndB | EndTransitionB | EndIntentB |
| ReactivatePatchA | ReactivateA | ReactivateTransitionA | ReactivateIntentA |
| ReactivatePatchB | ReactivateB | ReactivateTransitionB | ReactivateIntentB |

Каждый wrapper: header:PatchHeader, prepared:соответствующий P. Каждый prepared: base:WorldPublicationRef, transition:соответствующий transition. Transition: intent:соответствующий intent, participants:NonEmpty[ParticipantA/B]. Singleton intent: operation:соответствующий Literal[LifecycleOperation], change_uid:EntityUid, entity:RefA/B, reason:TestAReason/TestBReason. ReplaceIntent: operation/change_uid/reason и predecessors/successors:NonEmpty[RefA/B]. Все поля из owning схемы сохраняются; имена Replace, не Replacement, соответствуют карте нод.

### 3.2. Вложенные Lifecycle RECORD: ещё 18

| Exact named classes | Поля и замыкание |
|---|---|
| LifecycleSectionAB | header:SectionHeader; patches:NonEmpty[PatchAB]; domain_evidence:tuple[CoverageA \| CoverageB,...] |
| RefA, RefB | kind:соответствующий literal; entity_uid:EntityUid |
| EntityStateA, EntityStateB | entity:RefA/B; active:StrictBool; last_transition:LifecycleTransitionRef |
| AbsentA, AbsentB | status:Literal['absent']; entity:RefA/B |
| PresentA, PresentB | status:Literal['present']; state:EntityStateA/B |
| ParticipantA, ParticipantB | before:AbsentA \| PresentA либо AbsentB \| PresentB; after:EntityStateA/B |
| TestAReason, TestBReason | reason_id:'test_a_action'/'test_b_action'; action_uid:EntityUid; operation:LifecycleOperation |
| EffectA, EffectB | entity:RefA/B; effect:Literal['create','end','reactivate']; reason_action_uid:EntityUid |
| CoverageA, CoverageB | kind:Literal['prepared']; change_uid:EntityUid; effect:EffectA/B; section:PreparedSectionDependency; patch_refs:NonEmpty[PatchRef] |
| LifecycleTransitionRef | world_uid:EntityUid; origin_timeline_id:EntityUid; change_uid:EntityUid |

PatchAB — plain union восьми wrappers. CoverageA/B — единственные named children PreparedEffectBinding. Старые названия EffectBindingA/B в историческом C1 не означают второй класс: заменяются CoverageA/B, дополнительных IDs им нет. StateA/B из неформального описания означает EntityStateA/B, не альтернативные records. UnknownLifecycle/LastTransitionFact/Capture не достижимы из успешного native prepared: before допускает только Absent/Present.

### 3.3. Subject native RECORD: ещё 6

| Exact named classes | Поля и замыкание |
|---|---|
| TestDomainSectionA, TestDomainSectionB | header:SectionHeader; patches:NonEmpty[TestDomainPatchA/B] |
| TestDomainPatchA, TestDomainPatchB | header:PatchHeader; base:WorldPublicationRef; mutations:NonEmpty[MockMutationA/B]; effects:NonEmpty[EffectA/B] |
| MockMutationA, MockMutationB | entity:RefA/B; slot:Literal['primary','index']; before:StrictBool \| None; after:StrictBool; action_uid:EntityUid |

Mutation slots/effect strings не enum-классы. Ни MockBatch, ни producer admissions не вложены в subject native patch. Payload→effects проверяет subject verifier; Lifecycle потребляет те же EffectA/B через admitted view и CoverageA/B, не вводит копию effect/witness.

### 3.4. Owning terminal diagnostics: 2 RECORD и 3 ENUM во всей новой closure

| Kind | Exact type | Поля / значения |
|---|---|---|
| RECORD | LifecycleApplyIssue | code:LifecycleApplyCode; path:ValidatedFieldPath; message:StrictStr |
| RECORD | MockSubjectIssue | code:MockSubjectCode; path:ValidatedFieldPath; message:StrictStr |
| ENUM | LifecycleOperation | CREATE, REPLACEMENT, END, REACTIVATE; native intents/reasons |
| ENUM | LifecycleApplyCode | CHANGE_PAYLOAD_CONFLICT, BEFORE_STATE_MISMATCH, EVIDENCE_MISMATCH |
| ENUM | MockSubjectCode | INVALID_MUTATION, EFFECT_PAYLOAD_MISMATCH, INCOMPLETE_EFFECT, SUBJECT_BEFORE_MISMATCH |

Итого Lifecycle/subject owning delta: **58 RECORD + 3 ENUM** (32+18+6+2). Composition дополнительно добавляет **один MockSnapshotApplyResult RECORD**, то есть 59 новых RECORD вместе с result, до shared merge. MockSectionRefused не вложен в terminal и не получает wire ID. Числа являются проверкой полноты списка, не назначениями ID.

### 3.5. Shared reuse и field paths

Native edges: SectionHeader, PatchHeader, PatchRef, PreparedSectionDependency, PublishedSectionDependency, SectionDependencyKind, WorldPublicationRef, WorldSnapshotRef и полная existing shared closure их полей, включая ArtifactRef из PatchHeader.artifacts и SectionStateRef из published dependency. Пустые artifacts/depends_on в fixture не исключают объявленные типы из manifest. Existing shared declarations импортируются с исходными identities/IDs, не переобъявляются Lifecycle. EntityUid/RevisionHex/FormatVersion/SectionKey/PatchOrdinal — existing scalar aliases, не новые records.

Diagnostics.path использует ровно existing ValidatedFieldPath, ModelIdentity, FieldSegment, IndexSegment, KeySegment, VariantSegment; собственных LifecyclePath/MockPath нет. CheckedPath — runtime builder, не wire record. Root/branch allowlist для LifecycleApplyIssue: LifecycleSectionAB и реальные вложенные named types из §§3.1–3.2; для terminal MockSubjectIssue — TestDomainSectionA/B и их reachable native named types. Производные projection paths: domain_evidence[i].patch_refs[k]/effect/section либо patches[p].prepared.transition...; subject — patches[p].mutations[m].before/after, patches[p].effects или patches. Сегменты хранят exact ModelIdentity, а не строку с вымышленным индексом. Cold path restore использует manifest allowlist этих же classes.

SnapshotApplyRelationIssue и его shared closure, общие outcome/commit/publication refs — reuse Snapshot result manifest; owning список выше не назначает им новые IDs и не подменяет их классы. PatchSet сводит полный shared merge, numeric allocation/collisions, terminal format/root pair. Pair(1,20150) остаётся Time-only; Lifecycle не назначает mock pair независимо.

## 4. Runtime-only список: без автоматического расширения manifest

Не достижимы из выбранных native/terminal roots: девять named node inputs/outputs; восемь Create/Replace/End/ReactivateRequestA/B; PrepareLifecycleSectionAB; CaptureA/B, AdmissionA/B; UnknownA/B, LastTransitionFactA/B; LifecycleFieldIssue/RelationIssue, LifecycleFieldError/LogicError/SectionRefused и их enums; AcceptedChangesQuery, AcceptedChangeAbsent, AcceptedChangeFoundAB, AcceptedChangesResultAB; MockBatchA/B, PrepareMockSubjectA/B, PreparedMockSubjectA/B, MockSubjectObservationA/B, MockSubjectCaptureA/B, MockEffectLinkA/B, BuildMockEvidenceA/B; MockSectionRefused, LifecycleAppended, SectionAccepted/SectionApplyReceipt; application bindings/context/view/policies. Unknown/LastTransitionFact/Found names фиксируют test-only named specialization, не новую семантику. Snapshot record/claim wrappers runtime-only до появления отдельного serialization consumer. Если такой consumer появится, потребуется явное расширение roots, не скрытая регистрация всего набора POJO. Checkpoint OUT.

## 5. Проверяемый итог

Own roster конечен: 58 named records и 3 enums перечислены; MockSnapshotApplyResult — отдельный composition root. Q/P девяти нод совпадает с шагом 1; поля и pure refusals не изменены. Все три handlers используют exact MockSectionRefused и собственный subset. Подтверждение касается документального контракта, а не созданных Python declarations.

При реализации обязательны: reachable-closure walk native/terminal roots без missing records/enums; class/ID uniqueness после shared merge; сохранение exact classes/field paths/diagnostic order при codec+replay; negative wrong-T/wrong-carrier/foreign-subset; round-trip section.domain_evidence с types/values/order; terminal replay без handlers/section digest. Старый patch.evidence smoke не заменяет эти проверки. Numeric IDs/общую manifest-проверку сводит PatchSet; реальных producers/SQL/production wiring для этого не требуется.

## 6. Сквозная карта и доказательства локальной приёмки

Уточнение по ревью пользователя: девять строк §1 и соответствие prepared→wrapper §3.1 задают одну конечную карту, но не являются выполненным end-to-end тестом. Для каждой из восьми operation строк цепочка: точный NodeId/ContractId → тот же NodeContract[I,O,Never] version1 → named Input.request Q → pipeline с exact Q/P binding → named Output.value P либо pure отказ → exact-class map §3.1 выбирает wrapper. Нода не упаковывает wrapper сама: P передаёт DAG в PrepareLifecycleSectionAB.changes. Девятая строка принимает этот batch и возвращает LifecycleSectionAB либо LifecycleSectionRefused в Output.value.

Далее для всех восьми вариантов один SectionContract[LifecycleSectionAB]: section_model is LifecycleSectionAB, patches — plain PatchAB, domain_evidence — closed CoverageA/B. LifecycleSectionHandler и LifecycleSectionCodec используют ТОТ ЖЕ contract object; SectionRegistry.register(contract,handler,codec) связывает их. SectionFingerprint использует checked codec этого binding. Manifest содержит exact named classes §§3.1–3.4 + shared merge; mock numeric IDs/format pair сводит PatchSet. Общая приёмка не подтверждается одним roster до сверки этого merge и bindings.

| Проверка | Положительный и отрицательный критерий | Evidence сейчас |
|---|---|---|
| Девять registrations | Unique IDs/version1, exact contract object в executor/CallTarget; B request/output/intent/transition нельзя подставить в A binding, включая subclass/coercion | Документальная карта есть; static/runtime проверки не выполнены |
| Refusal transport | Все pure отказы остаются Output.value; E=Never и error_types=(); cancellation/exception обслуживает engine, фиктивного NodeError нет | Контракт зафиксирован; runtime negative не выполнен |
| Native/codec closure | Все восемь prepared превращаются в свой wrapper; section round-trip сохраняет exact concrete types и union branches; missing class/ID collision/неверная модель отвергаются | Owning roster предъявлен; full manifest/runtime evidence не подтверждено |
| Section evidence | prepare_section и codec сохраняют длину, concrete type, значения, порядок domain_evidence и patch_refs; мутация любого entry влияет на соответствующий section digest | Старый smoke patch.evidence НЕ покрывает эту проверку; актуальная проверка не выполнена |
| Effect→patch | Valid subject payload с неверной evidence relation даёт Lifecycle EVIDENCE_MISMATCH по domain_evidence[i]; valid fingerprint с ложным native effect даёт subject отказ | Сценарии §2.4 binding/apply определены; тесты не выполнены |
| Fingerprint/replay | В новой попытке подмена digest/section отвергается до validate; exact terminal replay не вычисляет section digests и не вызывает handlers | API/фаза приняты; тесты не выполнены |
| Equal Lifecycle retry | Found equal означает no-op только Lifecycle; отказ subject не подавляется, общий apply не начинается | Контракт определён; тест не выполнен |
| Atomicity | Отказ любого validate → ноль apply; ошибка после staged writes одного handler → rollback всех subject/Lifecycle history/projection; неизвестный исход не объявляется commit или подтверждённым rollback | Обязательное evidence mock atomic boundary, не выполнено |

Эти проверки принадлежат варианту А и не переносятся в production-план. Для документационной приёмки сверяются полные declarations/bindings и критерии; приёмка реализации требует фактических результатов тестов. Текущий запрос исправляет документацию и не разрешает реализацию классов/фикстуры или объявление runtime PASS. Shared node/manifest планы остаются у координатора и PatchSet; настоящая таблица — owning пакет общей сверки, не самостоятельная общая приёмка.
