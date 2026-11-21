# Lifecycle mock manifest: finite PatchSet owning roster

## Синхронизация координаторской сверки — 2026-11-21

Источник — [mock result manifest, координаторская сверка](lifecycle-mock-result-manifest.md#координаторская-сверка-2026-11-21). Local -> composition carrier получил PASS совместимости с H2, не runtime PASS. Единый модуль composition — tests/lifecycle/support/snapshotContracts.py; прежний resultContracts.py заменён, дубли классов не создаются. MockSubjectIssue/Code остаются в domainSections.py; subjectMock.py — только behavior.

Allocation 94001–94062,94090–94091 и mock pair(1,94001) остаются PROPOSED, явного принятия пользователем нет. Time pair(1,20150) неизменна. 59 owning/result RECORD + 2 shared path RECORD + 3 ENUM =64. Runtime merge/round-trip/static tests — evidence реализации, не дополнительный prerequisite архитектурного решения. Эта документальная синхронизация не отменяет уже выданное пользователем разрешение независимой реализации; зависимое назначение wire IDs согласуется отдельно. Историческое «не code-go» ниже означает только, что сам этот roster не выдаёт нового разрешения.

2026-11-21. Ответ на шаг 2 [координатора](lifecycle-mock-result-manifest.md). PROPOSED test-only allocations, не production reservation/code-go. Проверены actual ARTIFACT_CORE_SCHEMA/PATCH_CORE_SCHEMA/SNAPSHOT_CORE_SCHEMA, snapshotCore support diagnostics, planning test path declarations и owning entity-lifecycle-binding-apply-contract.md. Общий coordinator файл не менялся.

## Roots / consumers

- LifecycleSectionAB, TestDomainSectionA, TestDomainSectionB — owning SectionCodec encode/decode и SectionFingerprint; весь immutable native payload включён.
- MockPatchSet — PatchSetCodec projection encode/decode/fingerprint; собственной RECORD registration MockPatchSet НЕ требуется: actual codec кодирует ordered tuple projection, не record root. MockAssemblyInput не сериализуется.
- MockSnapshotApplyResult — единственный Snapshot terminal root этого test binding; consumer StoredTerminalCodec/mock Publication binding, затем exact replay. Предлагаемая test pair (snapshot_format_version=1, root=94001), подтверждает Snapshot/координатор. Time root20150 не расширяется. Existing Pack/Gameplay/Cancelled сохраняют свои отдельные актуальные roots.
- MockSectionRefused, локальные handler refusal models, OperationRecord specialization/claim, node I/O, captures, requests, accepted lookup, producer batches/admissions, runtime bindings/contexts — без ID: выбранные consumers их не сериализуют. Если появится отдельный consumer, расширение roster требует отдельной явной заявки, не автоматической регистрации.

## Allocation / evidence

До создания этого файла выполнен `rg -n --hidden '\b94[0-9]{3}\b' backend .cursor docs .agents`: exit1, совпадений нет. Проверены actual shared manifest literals: диапазон 94000–94999 ими не занят. Это локальный source audit с обычными ignore rules, не глобальный allocator и не исследование БД/веток. Предлагаются test-owned explicit IDs 94001–94062 и 94090–94091, НЕ вычисляемые из enumerate/model order. Пробелы не резервируются. Размещение registration fragment — backend/tests/lifecycle/support/manifest.py, без production imports этого test модуля.

Предыдущие snapshotCore synthetic IDs 90001–90014 не переиспользуются для новых owners. Ни один существующий owner не копируется в новый record. Actual общие path records имеют локальные test assignments в разных независимых manifests: snapshotCore 90012/90013/90014 и planning 12/13/14 для тех же owners. Нельзя merge эти два manifests целиком. Для данного snapshot-compatible test manifest выбираются существующие snapshotCore identities; IndexSegment reuse existing test identity15. KeySegment/VariantSegment source registrations в просмотренных schema declarations не найдены, ниже предложены новые test IDs. Это явный выбор одного composition manifest, не глобальная перенумерация.

## Полный новый roster

Module legend (полный путь, не новые package roots):

- M = backend/tests/lifecycle/support/mixedContracts.py
- S = backend/tests/lifecycle/support/domainSections.py
- C = backend/tests/lifecycle/support/snapshotContracts.py (named composition result и runtime carriers)
- K = backend/app/dataModel/lifecycle/operations/kind.py (owning target)
- I = backend/app/dataModel/lifecycle/identity.py (owning target)
- E = backend/app/dataModel/lifecycle/results/applyIssue.py (owning target из local contracts C3)

RECORD/ENUM — CanonicalTypeKind. Все номера только test-only declarations; owning production types из K/I/E не получают production registration этим файлом. Named synthetic модели не создают новых domain fields.

| Test ID | Exact class | Module | Kind |
|---|---|---|---|
| 94001 | MockSnapshotApplyResult | C | RECORD |
| 94002 | LifecycleSectionAB | M | RECORD |
| 94003 | TestDomainSectionA | S | RECORD |
| 94004 | TestDomainSectionB | S | RECORD |
| 94005 | LifecycleOperation | K | ENUM |
| 94006 | LifecycleTransitionRef | I | RECORD |
| 94007 | LifecycleApplyCode | E | ENUM |
| 94008 | LifecycleApplyIssue | E | RECORD |
| 94009 | MockSubjectCode | S | ENUM |
| 94010 | MockSubjectIssue | S | RECORD |
| 94011 | RefA | M | RECORD |
| 94012 | RefB | M | RECORD |
| 94013 | EntityStateA | M | RECORD |
| 94014 | EntityStateB | M | RECORD |
| 94015 | AbsentA | M | RECORD |
| 94016 | AbsentB | M | RECORD |
| 94017 | PresentA | M | RECORD |
| 94018 | PresentB | M | RECORD |
| 94019 | ParticipantA | M | RECORD |
| 94020 | ParticipantB | M | RECORD |
| 94021 | TestAReason | M | RECORD |
| 94022 | TestBReason | M | RECORD |
| 94023 | EffectA | M | RECORD |
| 94024 | EffectB | M | RECORD |
| 94025 | CoverageA | M | RECORD |
| 94026 | CoverageB | M | RECORD |
| 94027 | CreateIntentA | M | RECORD |
| 94028 | CreateIntentB | M | RECORD |
| 94029 | ReplaceIntentA | M | RECORD |
| 94030 | ReplaceIntentB | M | RECORD |
| 94031 | EndIntentA | M | RECORD |
| 94032 | EndIntentB | M | RECORD |
| 94033 | ReactivateIntentA | M | RECORD |
| 94034 | ReactivateIntentB | M | RECORD |
| 94035 | CreateTransitionA | M | RECORD |
| 94036 | CreateTransitionB | M | RECORD |
| 94037 | ReplaceTransitionA | M | RECORD |
| 94038 | ReplaceTransitionB | M | RECORD |
| 94039 | EndTransitionA | M | RECORD |
| 94040 | EndTransitionB | M | RECORD |
| 94041 | ReactivateTransitionA | M | RECORD |
| 94042 | ReactivateTransitionB | M | RECORD |
| 94043 | CreateA | M | RECORD |
| 94044 | CreateB | M | RECORD |
| 94045 | ReplaceA | M | RECORD |
| 94046 | ReplaceB | M | RECORD |
| 94047 | EndA | M | RECORD |
| 94048 | EndB | M | RECORD |
| 94049 | ReactivateA | M | RECORD |
| 94050 | ReactivateB | M | RECORD |
| 94051 | CreatePatchA | M | RECORD |
| 94052 | CreatePatchB | M | RECORD |
| 94053 | ReplacePatchA | M | RECORD |
| 94054 | ReplacePatchB | M | RECORD |
| 94055 | EndPatchA | M | RECORD |
| 94056 | EndPatchB | M | RECORD |
| 94057 | ReactivatePatchA | M | RECORD |
| 94058 | ReactivatePatchB | M | RECORD |
| 94059 | MockMutationA | S | RECORD |
| 94060 | MockMutationB | S | RECORD |
| 94061 | TestDomainPatchA | S | RECORD |
| 94062 | TestDomainPatchB | S | RECORD |
| 94090 | KeySegment | backend/app/dataModel/fields/validatedFieldPath.py | RECORD |
| 94091 | VariantSegment | backend/app/dataModel/fields/validatedFieldPath.py | RECORD |

Итого 64 новых test declarations: 61 RECORD, 3 ENUM. Диапазон таблицы 94001–94062 плюс94090/94091 — итоговая exact allocation; все проверены указанным поиском полного94xxx. Поля и ordering берутся из owning schemas, таблица не добавляет их заново. LifecycleApplyCode содержит только три принятых apply codes; MockSubjectCode четыре owning subject codes; не заменять отдельными test enum copies.

## Shared reuse / полная reachability

База composition — existing SNAPSHOT_CORE_SCHEMA (включает PATCH_CORE_SCHEMA и ARTIFACT_CORE_SCHEMA). Не менять owners/kinds/IDs существующих entries, даже если конкретная ветвь сейчас не достигается. Required reachable shared subset:

| IDs | Existing types / модуль |
|---|---|
| 20001 | SnapshotChainKind — dataModel/worldSnapshot/identity/refs.py |
| 20002 | SnapshotApplyOutcomeKind — dataModel/worldSnapshot/results/outcomeKind.py |
| 20003 | ArtifactKind — owning artifacts refs closure, actual ARTIFACT_CORE_SCHEMA |
| 20007 | SectionDependencyKind — dataModel/patch/sections/dependency.py |
| 20101/20102 | WorldSnapshotRef / PlayerSnapshotRef — dataModel/worldSnapshot/identity/refs.py |
| 20103/20104 | WorldPublicationRef / PlayerHeadExpectation — dataModel/worldSnapshot/identity/publication.py |
| 20105/20106 | SectionStateRef / SectionHistoryRef — dataModel/worldSnapshot/sections/refs.py |
| 20107 | ArtifactRef — dataModel/artifacts/references.py |
| 20114/20115 | PatchRef / PatchHeader — dataModel/patch/changes/header.py |
| 20116/20117 | PreparedSectionDependency / PublishedSectionDependency — dataModel/patch/sections/dependency.py |
| 20118 | SectionHeader — dataModel/patch/sections/section.py |
| 20123 | SnapshotCommitRefs — dataModel/worldSnapshot/results/apply.py |
| 20306/20307 | SnapshotApplyCode / SnapshotApplyRelationIssue — dataModel/worldSnapshot/results/applyIssues.py |
| 90012/90013/90014 | ValidatedFieldPath / ModelIdentity / FieldSegment — dataModel/fields/validatedFieldPath.py; existing tests/snapshotCore/support/diagnostics.py declarations |
| 15 | IndexSegment — тот же owning path module; existing tests/planning/providers/test_domain_providers.py declaration |

Merge именно отдельного path fragment с согласованными entries, не всего planning или FakeSection manifests. SnapshotApplyResult20124/SectionRefused20131/OperationRecord20128 остаются existing entries базы, но НЕ current mock root, НЕ registration новых specialized classes и НЕ разрешение legacy readers. Scalar aliases EntityUid/RevisionHex/FormatVersion и Literal kind/effect/slot/status, tuple/None/bool/str/int не требуют RECORD ID.

Native closure: section -> headers + 8 patches -> prepared(base,transition) -> 8 transitions(intent,participants) -> 8 intents(refs,reason,operation enum) + ParticipantA/B(before Absent/Present,after EntityState) -> typed Ref + LifecycleTransitionRef. Coverage -> change_uid + EffectA/B(ref,effect,reason_action_uid) + PreparedSectionDependency + patch_refs. Subject section -> patch(base,mutations,effects) -> MockMutationA/B(ref,slot,before/after,action_uid) + EffectA/B. Domain payload не импортируется в Lifecycle prepared.

Terminal closure: MockSnapshotApplyResult -> shared category/identity/commit refs либо закрытые SnapshotApplyRelationIssue/LifecycleApplyIssue/MockSubjectIssue -> соответствующие enums + ValidatedFieldPath -> ModelIdentity и ВСЕ четыре segment alternatives. ModelIdentity owner allowlist для terminal paths ограничен native section/patch/prepared/transition/intent/participant/ref/effect/mutation и shared headers уже в manifest. Producer-only paths batches/captures не выдаются в terminal: producer refusal не apply output. Если owning handler начнёт выдавать такой path, это явное расширение root reachability, а не повод зарегистрировать весь runtime.

Не reachable: UnknownA/B/UnknownFactCause (успешный Participant.before их не допускает), CaptureA/B, LastFactA/B, AdmissionA/B, MockBatchA/B, MockSubjectCapture/Observation, PrepareMockSubject/PreparedMockSubject, accepted lookup и history wrappers. Они могут существовать runtime для подготовки/проверки, но не вложены в выбранные roots. Сам LifecycleTransition сохраняется nested native record; отдельный history storage consumer не проектируется здесь. Generic parents PatchData/DomainSection/FieldPathError и aliases не подменяют concrete descendants.

## Node cards и конкретность schema

Подтверждены девять строк начала gen-dag-lifecycle-node-contracts.md: create/replacement/end/reactivate × test_a/test_b и prepare_section AB. IDs уникальны внутри списка; version1, E=Never, error_types/reads/calls пустые; named request/success mapping Q/P совпадает с roster выше. I/O классы в tests/lifecycle/support/nodeContracts.py, регистрация в nodeBindings.py; domain synthetic models только mixedContracts.py/domainSections.py. Никаких numeric wire IDs для NodeContract/Input/Output/NodeError. Source admission допускает empty errors; static/runtime тесты ещё не выполнены.

Composition result — MockSnapshotApplyResult в snapshotContracts.py, D=LifecycleApplyIssue|MockSubjectIssue. В том же модуле три runtime-only carrier: MockLifecycleSectionRefused(SectionRefused[LifecycleApplyIssue]), MockSubjectSectionRefused(SectionRefused[MockSubjectIssue]), MockSectionRefused(SectionRefused[MockDiagnostic]). Lifecycle handler/append/validator используют первый; оба subject handler/verifier — второй; SectionRegistry[MockDiagnostic](MockSectionRefused) выдаёт третий после exact local carrier/subset проверки. Category/concrete diagnostic types/paths/order сохраняются. Общий carrier не требуется от всех handlers, None/чужой local class не coerced. Pure LifecycleSectionRefused и девять node outputs неизменны. Ни одному из этих трёх runtime carriers wire ID не назначается.

Missing named declarations перечислены исчерпывающе таблицей, а не «closure позже»: TypeAdapters/annotations каждого existing generic child должны указывать на named nested модели (например CreateA.transition=CreateTransitionA, ParticipantA.before=AbsentA|PresentA, after=EntityStateA, CoverageA.effect=EffectA). Автоматические parameterized generic classes не заменяют эти owners и не получают fallback IDs. Все новые модели ещё TARGET; runtime merge нельзя доказать fake stand-ins. Source absence 94xxx — evidence отсутствия найденных collisions, не выполненный merge/round-trip.

## Итог

Finite proposed roster предъявлен: 64 новых entries плюс exact shared reuse; native/terminal consumers отделены от runtime/checkpoint. Остаток решения координатора — принять test allocation и test pair(1,94001), подтвердить closed nested declaration identities с Lifecycle/Snapshot. Owning E module уточнён по local contracts C3: results/applyIssue.py. Это конкретные строки, не новые предметные OPEN. Implementation evidence: merge ID/owner/kind conflicts, all reachable branches, exact A/B + evidence round-trip, terminal issue paths/index/variant preservation, foreign subtype/root rejection, no legacy/fallback/repeated apply. Runtime проверок/кода/production registration в этом проходе нет.
