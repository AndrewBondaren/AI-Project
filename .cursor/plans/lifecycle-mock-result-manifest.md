# Lifecycle mock: closed apply result и manifest — шаг 2

2026-11-21. Выполняется после конкретизации девяти регистраций в gen-dag-lifecycle-node-contracts.md. Документальное предложение к общей сверке, без кода или назначения production IDs. Scope mock_lifecycle_world, synthetic A/B, ready inputs; реальные домены/SQL/checkpoint OUT.

## Предлагаемая единая composition

MockSectionUnion = LifecycleSectionAB | TestDomainSectionA | TestDomainSectionB (plain closed union). Одни named MockAssemblyInput и MockPatchSet используют этот union. Только LifecycleSectionAB недостаточно: D4 требует предметных patches. MockApplySnapshotInput содержит именно MockPatchSet; output.value — MockSnapshotApplyResult, без новых полей результата и без нового apply NodeId.

MockDiagnostic = LifecycleApplyIssue | MockSubjectIssue. Proposed MockSnapshotApplyResult — named closed specialization целевого SnapshotApplyResult[MockDiagnostic], diagnostics = tuple[SnapshotApplyRelationIssue | LifecycleApplyIssue | MockSubjectIssue,...]. Common category/operation_id/request_fingerprint/committed invariants переиспользуются. Production TimeSnapshotApplyResult/root20150 не расширяется. Actual SnapshotApplyResult ещё nongeneric: target generic H2 и actual implementation не смешивать.

Один mock PublicationResultBinding[MockSnapshotApplyResult] и соответствующий exact OperationRecord specialization проходят codec/store/claim/replay/node без adaptation. Runtime record/claim модели не получают wire IDs без serialization consumer. Общая SectionRegistry[MockDiagnostic] использует MockSectionRefused(SectionRefused[MockDiagnostic]). Lifecycle handler/append/validator возвращают exact local MockLifecycleSectionRefused(SectionRefused[LifecycleApplyIssue]); subject A/B handler/verifier — MockSubjectSectionRefused(SectionRefused[MockSubjectIssue]). Registry проверяет exact local carrier и diagnostic subset, затем переносит category и diagnostics в общий carrier без потери concrete типов, paths и порядка. Требование одного exact carrier от всех handlers отменено как противоречащее H2. Pure LifecycleSectionRefused и девять node outputs не меняются; runtime-only carriers не требуют wire IDs.

### Координаторская сверка 2026-11-21

PASS узкой поправки local → composition carrier по существующему H2; это не runtime PASS и не разрешение новой реализации. Для синхронизации proposed manifest выбран один путь composition declarations: backend/tests/lifecycle/support/snapshotContracts.py (вместо resultContracts.py); MockSubjectIssue/Code — backend/tests/lifecycle/support/domainSections.py (вместо subjectMock.py). subjectMock.py содержит поведение producer/verifier, а не вторые объявления этих классов. Owning документы должны ссылаться на эти exact classes.

PatchSet предъявил test-only allocation 94001–94062, 94090–94091 и pair (1,94001). 59 owning/result RECORD + 2 shared path RECORD + 3 ENUM = 64 declarations; численного противоречия нет. Статус allocation/pair — предложены к решению пользователя, не объявлены утверждёнными. Локальный source collision audit не заменяет runtime manifest merge/closure/round-trip проверки на этапе реализации. Time pair (1,20150) не меняется.

## Manifest: что действительно сериализуется

1. Native sections: LifecycleSectionAB, восемь Lifecycle wrappers, named prepared/transition/intent/participant/state/ref/reason classes, CoverageA/B и их вложенные effects/refs; subject TestDomainSectionA/B, их patches/mutations/effects/base.
2. Terminal: MockSnapshotApplyResult, LifecycleApplyIssue/Code, MockSubjectIssue/Code, SnapshotApplyRelationIssue и его existing closure, commit refs, field-path models и enums.
3. Existing shared identities/header/dependency/publication/snapshot records и enums переиспользуются с исходными IDs через merge, без копирования declarations.
4. Node Input/Output, pure requests/refusals, captures и accepted lookup добавляются лишь если reachable из реально выбранного serialized root. Engine checkpoint вне scope: не расширять wire roster автоматически всеми POJO.

IDs: полный proposed class→RECORD/ENUM→ID roster предъявлен в patch-set-lifecycle-mock-manifest-roster.md; статус утверждения указан выше. Test-only manifest не регистрирует synthetic types в production. Проверяются collision с merged shared declarations, distinct roots и полная reachable closure; plain aliases/generic parents не получают IDs вместо concrete classes. Pair(1,20150) остаётся Time-only.

## Узкая owning сверка и результат

PatchSet: предъявить полный finite named schema roster и план test-only IDs без collisions; явно отделить shared reuse от new records/enums и wire от runtime-only. Указать missing named nested declarations, не скрывать их за «closure позже».

Snapshot: подтвердить MockSectionUnion/MockDiagnostic/result/record/carrier binding по существующему H2, включая общий exact refusal_model и subset checks, write/replay/unknown-root semantics. Никакой новой orchestration или изменения Time IDs.

Lifecycle: подтвердить exact own diagnostic/code/field-path и prepared/native roster, согласовать единый registry carrier без изменения предметной семантики или pure node outputs.

После owning ответа координатор сведёт единую таблицу и выполнит проверку declarations/collisions. Runtime round-trip и error/replay tests — этап реализации. Этот план не выдаёт runtime PASS и не делает OUT prerequisites.
