# Ребро assemble_patch_set → apply_snapshot

**Public Error payload evidence — 2026-11-25:** Snapshot подтвердил consumer PASS BUG-ENUM-01 после независимого от producer повторения 26 targeted admission/tagged-path tests на shared Pydantic 2.13.4/core2.46.4 и isolated pinned 2.14.2/core2.50.2 с проверенными paths/versions. Подтверждены все четыре direct-reuse compatibility facts, owning enum identity, JSON const/discriminator, operands/indices/mixed order, None identities и ADMISSION_REFUSED. Foreign enum/forged fact и malformed supported_versions отвергаются; Python lists не принимаются, корректные JSON arrays проходят. Production Snapshot payload contract не менялся; новых node wrappers/Error carriers эта дельта не требует. Это consumer evidence публичной ошибки, не PASS full apply, node реализации, NodeId или регистрации. Owning подробности — snapshot-public-methods-contract.md.

**Единственный источник node package:** [dag-write-node-pojo-contracts.md §2–5](dag-write-node-pojo-contracts.md). Этот файл сверяет ребро, не вводит другие wrappers/IDs. Concrete mock Input/Output, SnapshotPublicNodeError и SnapshotOperationCancelledNodeError существуют. Локальные IDs: engine.patch.mock_lifecycle.assemble_patch_set и engine.snapshot.mock_lifecycle.apply_snapshot. Готовность полного public apply, независимая приёмка маршрута и parent refusal slot учитываются отдельно.

2026-11-24. Единица сверки — node Input/Output/Error и orchestration. Пользователь разрешил реализацию нод и последующее сведение оставшихся контрактов в коде. Это не production activation и не приёмка всего маршрута. Генератор/gameplay и верхнее получение inputs OUT. Domain internals не являются предметом этого плана или новыми DAG gates.

## Согласуемый concrete payload

Owning imports из tests.lifecycle.support.snapshotContracts: MockAssemblyInput, MockPatchSet, MockSectionUnion, MockSnapshotApplyResult. Это synthetic binding, не универсальный production union. S = LifecycleSectionAB | TestDomainSectionA | TestDomainSectionB. Payload assembler success — exact MockPatchSet; consumer получает тот же typed объект без cast/reconstruction/sorting.

| Нода | Input / public target | Output / следующий consumer | Статус |
|---|---|---|---|
| assemble_patch_set | MockAssemblePatchSetInput.request: MockAssemblyInput → IPatchSetAssembly[MockAssemblyInput, MockPatchSet].assemble(request) | MockAssemblePatchSetOutput.value: MockPatchSet либо PatchSetAssemblyRefused | Method и concrete mock node/NodeContract/локальная регистрация существуют; независимая приёмка отдельно |
| apply_snapshot | MockApplySnapshotInput.patch_set:MockPatchSet → IWorldSnapshotApply[MockSectionUnion,MockSnapshotApplyResult].apply(input.patch_set) | MockApplySnapshotOutput.value:MockSnapshotApplyResult → caller без изменения | Concrete mock node/локальная регистрация существуют; готовность full public method и независимая приёмка отдельно |

Все 9 полей PatchSetData сохраняются: format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Snapshot/receipt/claim/holds не добавляются в node Input. Public assembler IPatchSetAssembly[Q,P] возвращает P | PatchSetAssemblyRefused; mock Q=MockAssemblyInput, P=MockPatchSet. Cast/reconstruction не нужны. Передача сохраняет exact тип и значение; Python object identity не требуется при штатной revalidation.

## Все ветви ребра

| Исход | Mapping / orchestration |
|---|---|
| Assembly success | MockAssemblePatchSetOutput.value:MockPatchSet → MockApplySnapshotInput.patch_set |
| PatchSetAssemblyRefused | Refusal/diagnostics без изменения → parent refusal branch (exact slot OPEN); apply не вызывать |
| Assembly structural/runtime exception | Engine failure; не подменять owning refusal; apply не вызывать |
| Apply T COMMITTED/CONFLICT/REJECTED | Целиком → output.value; node success не означает COMMITTED |
| SnapshotPublicError | PythonNodeError(SnapshotPublicNodeError(fault=exc.fault)); owning payload целиком |
| Durable SnapshotOperationCancelledError | PythonNodeError(SnapshotOperationCancelledNodeError(outcome=exc.outcome)); отдельно от T и invocation cancellation |
| asyncio.CancelledError | Runtime cancellation; no successful output/следующий CALL |
| Unknown при APPLY | По public контракту OUTCOME_UNKNOWN fault с checked binding и cause; не T, не rollback/refusal, без automatic retry |

## Deliverable владельца DAG

Проверить единственный предъявленный node package из dag-write-node-pojo-contracts.md §2–5: exact typing, public target mapping, lossless durable cancellation, NodeContract/registration requirements. При несовместимости дать минимальную дельту к этому пакету, не создавать альтернативный SoT. Parent refusal slot — следующий шаг основного координатора. Владельцы доменов отвечают только за public contract/guarantees/readiness; внутренние алгоритмы не проектируются в DAG.

## Evidence и границы

PatchSet/Snapshot подтвердили payload compatibility. Concrete mock wrappers/leaf/локальные регистрации существуют; актуальное и целевое размещение разделены в реестре нод. Наличие файлов не заменяет независимую приёмку и evidence тестов маршрута; domain tests не выдаются за node evidence. Method/node/registration/verification отслеживаются отдельно. Внутренние handoff/transaction/codec отчёты — история owning работ, не новые требования нод. Источник приоритета: [план нод](dag-write-nodes-implementation.md).
