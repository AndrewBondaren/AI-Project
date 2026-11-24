# Ребро assemble_patch_set → apply_snapshot

**Единственный SoT node package:** [dag-write-node-pojo-contracts.md §2–5](dag-write-node-pojo-contracts.md). Настоящий файл — evidence/проверка соответствия, не второй источник wrappers/IDs. Предъявлены MockAssemblePatchSetInput(request:MockAssemblyInput), MockAssemblePatchSetOutput(value:MockPatchSet | PatchSetAssemblyRefused), MockApplySnapshotInput(patch_set:MockPatchSet), MockApplySnapshotOutput(value:MockSnapshotApplyResult); proposed engine-only SnapshotPublicNodeError(fault), SnapshotOperationCancelledNodeError(outcome). Proposed строковые IDs: engine.patch.mock_lifecycle.assemble_patch_set, engine.snapshot.mock_lifecycle.apply_snapshot. Это проектные объявления, не implemented/registered status. Ниже прежнее «wrapper не предъявлен» относится к состоянию до этого пакета; текущий остаток — exact typing/transport сверка данного SoT и registration evidence. Parent refusal slot ведёт основной координатор, здесь параллельный вариант не создаётся.

2026-11-24. Единица сверки — node Input/Output/Error и orchestration. Contract-only: маршрут не закрыт, добра на зависимую реализацию/активацию нет. Генератор/gameplay и верхнее получение inputs OUT. Domain internals не являются предметом этого плана или новыми DAG gates.

## Согласуемый concrete payload

Owning imports из tests.lifecycle.support.snapshotContracts: MockAssemblyInput, MockPatchSet, MockSectionUnion, MockSnapshotApplyResult. Это synthetic binding, не универсальный production union. S = LifecycleSectionAB | TestDomainSectionA | TestDomainSectionB. Payload assembler success — exact MockPatchSet; consumer получает тот же typed объект без cast/reconstruction/sorting.

| Нода | Input / public target | Output / следующий consumer | Статус |
|---|---|---|---|
| assemble_patch_set | Named node Input/field ещё требуется. Owning payload MockAssemblyInput → IPatchSetAssembly[S].assemble(request) | Success MockPatchSet либо PatchSetAssemblyRefused. Named node Output/поле ещё требуется | Method implemented; node/NodeContract/registration не подтверждены |
| apply_snapshot | Проектный ApplySnapshotInput[S].patch_set:PatchSet[S], concrete named wrapper требуется. IWorldSnapshotApply[S,MockSnapshotApplyResult].apply(input.patch_set) | Проектный ApplySnapshotOutput[T].value:T → результат orchestration/caller без изменения | Protocol/admission есть; full public method не реализован по owning отчёту; node/registration не подтверждены |

Все 9 полей PatchSetData сохраняются: format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Snapshot/receipt/claim/holds не добавляются в node Input. Public assembler signature возвращает PatchSet[S], runtime binding гарантирует MockPatchSet; static exact edge требует проверки владельцев, не cast в DAG.

## Все ветви ребра

| Исход | Mapping / orchestration |
|---|---|
| Assembly success | Exact MockPatchSet → apply input.patch_set; exact producer wrapper field ещё OPEN |
| PatchSetAssemblyRefused | Refusal/diagnostics без изменения → parent refusal branch (exact slot OPEN); apply не вызывать |
| Assembly structural/runtime exception | Engine failure; не подменять owning refusal; apply не вызывать |
| Apply T COMMITTED/CONFLICT/REJECTED | Целиком → output.value; node success не означает COMMITTED |
| SnapshotPublicError | Проектный PythonNodeError(SnapshotNodeError(error=fault)); exact node error class/registration OPEN |
| Durable SnapshotOperationCancelledError | Сохранить OperationCancelled(operation_id,reason) отдельно от T и invocation cancellation; exact engine transport OPEN |
| asyncio.CancelledError | Runtime cancellation; no successful output/следующий CALL |
| Unknown при APPLY | По public контракту OUTCOME_UNKNOWN fault с checked binding и cause; не T, не rollback/refusal, без automatic retry |

## Deliverable владельца DAG

Проверить единственный предъявленный node package из dag-write-node-pojo-contracts.md §2–5: exact typing, public target mapping, lossless durable cancellation, NodeContract/registration requirements. При несовместимости дать минимальную дельту к этому пакету, не создавать альтернативный SoT. Parent refusal slot — следующий шаг основного координатора. Владельцы доменов отвечают только за public contract/guarantees/readiness; внутренние алгоритмы не проектируются в DAG.

## Evidence и границы

PatchSet/Snapshot подтвердили payload compatibility; DAG-владелец подтвердил отсутствие готовых wrappers/регистрации в проверенном коде. Node-route tests не предъявлены; domain tests не выдаются за node evidence. Method/node/registration/verification отслеживаются отдельно. Внутренние handoff/transaction/codec отчёты — история owning работ, не новые требования нод. Источник приоритета: [план нод](dag-write-nodes-implementation.md).
