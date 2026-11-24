# Конкретные POJO нод записи и связи

Сверочная таблица ребра и owning evidence: [assemble → apply](dag-assemble-apply-edge.md). Конкретные wrappers/предложенные регистрации задаёт этот документ; сверочная таблица не вводит второй набор. Изменения после engine/public-boundary проверки вносятся сюда адресной дельтой. Отсутствие cast/reconstruction при передаче base-typed результата требует доказательства exact typing binding до реализации, не компенсируется обещанием runtime subtype.

2026-11-24. Проработка по поручению пользователя. PROPOSED node wrappers/registration/errors; существующие owning POJO не меняются. Это контрактная работа, не code-go незакрытого маршрута. Domain internals OUT. Первый concrete scenario — mock_lifecycle_world; generator/gameplay OUT, входы уже подготовлены. Следующие карточки не объявляют full write_changes реализованным.

## 1. Concrete owning типы

Все пути ниже относительно backend/.

| Тип | Существующий источник | Назначение |
|---|---|---|
| MockAssemblyInput | tests/lifecycle/support/snapshotContracts.py | Closed PatchSetAssemblyInput[LifecycleSectionAB \| TestDomainSectionA \| TestDomainSectionB] |
| MockPatchSet | тот же | Closed successful assembled request |
| MockSnapshotApplyResult | тот же | Closed result Snapshot с Lifecycle/subject diagnostics |
| PatchSetAssemblyRefused | app/dataModel/patch/results/assembly.py | Owning отказ сборки; не NodeError |
| SnapshotPublicFault | app/dataModel/worldSnapshot/errors/publicFault.py | Owning неперсистентный public fault |
| OperationCancelled | app/dataModel/artifacts/lifecycle/operation/record.py | Owning durable cancellation outcome |

MockAssemblyInput содержит existing поля: format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Все приходят готовыми от предыдущей согласованной границы; ни одна из двух нод их не вычисляет. Concrete fixture задаёт тестовые значения, не изображает generator/gameplay. sections содержит только названные owning классы.

## 2. assemble_patch_set — concrete карточка

| Параметр | Предлагаемый контракт |
|---|---|
| Logical name / family / role | assemble_patch_set / запись / operation leaf; caller write_changes |
| Concrete NodeId = ContractId | engine.patch.mock_lifecycle.assemble_patch_set; test registration, не production ID |
| Version | ContractVersion('1'), не wire format |
| Input | MockAssemblePatchSetInput(request: MockAssemblyInput) |
| Output | MockAssemblePatchSetOutput(value: MockPatchSet \| PatchSetAssemblyRefused) |
| Declared Error | Never; business отказ в value, unexpected failure через engine infrastructure transport |
| Public target | IPatchSetAssembly[MockAssemblyInput, MockPatchSet].assemble(input.request); exact Q/P owning дельта от 2026-11-24 |
| Public success mapping | returned MockPatchSet → output.value, без повторного создания PatchSet |
| Public refusal mapping | returned PatchSetAssemblyRefused → output.value неизменным |
| reads / calls | (), (); owning method — public call, не child node CALL |

Нода не проверяет domain rules, не переставляет sections, не вычисляет fingerprints и не вызывает apply. Транспортная exact-class проверка не заменяет admission владельца. Непредусмотренный result class — engine output contract failure, не превращение в PatchSetAssemblyRefused.

**Exact Q/P binding, 2026-11-24:** owning port IPatchSetAssembly[Q:PatchSetAssemblyInput, P:PatchSet].assemble(request:Q) → P | PatchSetAssemblyRefused; implementation PatchSetAssembler[Q,P](request_model:type[Q], result_model:type[P]). Mock Q=MockAssemblyInput, P=MockPatchSet. Статика сохраняет concrete типы входа/результата; согласованность section union между Q/P проверяет owning constructor по exact annotations до исполнения. Это runtime guarantee, не dependent static typing. Node cast/reconstruction/shadow protocol не нужны. Owning реализация/typing evidence ожидаются отдельно.

## 3. apply_snapshot — concrete карточка

**Готовность assembly public target, 2026-11-24:** PatchSet сообщил реализацию exact Q/P в application/patch/contracts/assembly.py и assembly/patchSetAssembler.py. Owning evidence: 9 assembly tests PASS; positive assert_type 0 ошибок; negative fixture — три ожидаемые ошибки foreign input/result/port; несовместимый sections binding отвергается constructor. Node implementation/registration и проверка ребра отдельно; отчёт владельца не подменяет node-level evidence.

| Параметр | Предлагаемый контракт |
|---|---|
| Logical name / family / role | apply_snapshot / Snapshot / operation leaf; caller write_changes |
| Concrete NodeId = ContractId | engine.snapshot.mock_lifecycle.apply_snapshot; test registration |
| Version | ContractVersion('1') |
| Input | MockApplySnapshotInput(patch_set: MockPatchSet) |
| Output | MockApplySnapshotOutput(value: MockSnapshotApplyResult) |
| Declared Error | SnapshotPublicNodeError \| SnapshotOperationCancelledNodeError |
| Public target | await IWorldSnapshotApply[MockSectionUnion, MockSnapshotApplyResult].apply(input.patch_set) |
| Result mapping | exact returned MockSnapshotApplyResult → output.value для COMMITTED/CONFLICT/REJECTED |
| reads / calls | (), (); scope/transaction/handlers не поля контракта ноды |

Предлагаемые engine-only carriers, subclass existing NodeError:

- SnapshotPublicNodeError(fault: SnapshotPublicFault). Catch только SnapshotPublicError; payload exc.fault переносится целиком в PythonNodeError этого carrier. Категории/identity/diagnostics не пересчитываются.
- SnapshotOperationCancelledNodeError(outcome: OperationCancelled). Catch только SnapshotOperationCancelledError; payload exc.outcome переносится целиком. Это durable outcome, не invocation cancellation.

asyncio.CancelledError сохраняет существующий engine cancellation path; новый error POJO для него не вводится. Unexpected/raw infrastructure исключения не преобразуются leaf в domain/public fault. Если public method по принятому контракту выдаёт SnapshotPublicFault OUTCOME_UNKNOWN, нода передаёт его как есть, без retry/rollback/record_refusal. Полный перечень публичных exceptions подтверждает Snapshot на границе метода, внутренние источники ошибок DAG не проектирует.

Нода не достаёт committed refs отдельно, не превращает CONFLICT/REJECTED в NodeError и не объявляет durable cancellation обычным cancelled invocation. Возврат результата не зависит от рассуждений ноды о commit.

## 4. Exact ребро assemble → apply

**Owning Snapshot подтверждение 2026-11-24:** публичная граница §3–4 PASS как target obligation. Исчерпывающие declared exceptions: SnapshotPublicError (INVALID_INPUT/ADMISSION_REFUSED/BUSY/INFRASTRUCTURE_FAILURE/OUTCOME_UNKNOWN), SnapshotOperationCancelledError и asyncio.CancelledError. Ожидаемый unknown передаётся SnapshotPublicFault.OUTCOME_UNKNOWN с сохранённым cause у исключения, не raw UnknownCommitOutcome в node union. Два предложенных NodeError carrier достаточны по owning payload; окончательная engine-приёмка отдельно. POJO/порт существуют, полный public apply пока не реализован/не принят. Этот ответ не принимает NodeId/wrappers/registration и не даёт code-go.

| Producer outcome | Mapping caller write_changes | Consumer |
|---|---|---|
| MockAssemblePatchSetOutput.value: MockPatchSet | MockApplySnapshotInput(patch_set=assembled.value) | apply_snapshot |
| MockAssemblePatchSetOutput.value: PatchSetAssemblyRefused | Сохранить owning отказ в результате caller; apply не вызывается | caller output branch, exact wrapper в следующей карточке |
| Engine failure/cancellation assembly | Передать existing engine outcome; не создавать apply input | Нет зависимого CALL |
| MockApplySnapshotOutput.value: MockSnapshotApplyResult | Сохранить exact результат в caller result | caller output branch |
| Declared apply NodeError / cancellation | Передать engine outcome и correlation без нового domain отказа | caller error/control branch |

Field mapping только один: assembled.value → apply.input.patch_set. Identity поля operation_id/world/timeline/expected/context берутся внутри того же MockPatchSet, не копируются вторым набором на ребре. Engine invocation correlation принадлежит CALL, operation_id — owning payload; они не подменяют друг друга. Node invocation correlation не добавляется в доменный POJO.

Все node wrappers strict/frozen/extra-forbid/revalidate-always; named concrete классы, без open generic registration. Не вводить новые domain defaults, identities, wire IDs или Python classes/callbacks в payload. Политика object identity для локального envelope transport должна соответствовать engine-контракту; не переносить специальную content-is гарантию Artifacts на все POJO без основания. Тип/значения и порядок должны сохраняться.

**Уточнение wrapper identity, 2026-11-24:** для assembly/apply входов, выходов и error carriers Python `is` не является гарантией. Nested Pydantic validation с owning revalidate_instances='always' вправе создавать новый экземпляр exact того же concrete класса. Требование «без пересборки» запрещает ноде вручную извлекать/копировать поля, пересоздавать доменный результат или приводить базовый тип к concrete; оно не запрещает штатную framework revalidation. На ребре сохраняются exact тип, все значения, enum members, порядок tuple/diagnostics, operation identity и корреляция. Constructor/CALL передаёт owning объект непосредственно в предусмотренное поле, без model_construct/cast/отключения validation. Проверки Python `is` для этой пары нод заменить проверками exact type + полного payload/порядка; object identity публичных service dependencies/NodeContract остаётся прежней отдельной гарантией. Специальные content/prepared identity-контракты Artifacts этим не меняются.

## 5. Размещение и границы приёмки

Concrete mock Input/Output — proposed tests/lifecycle/support/writeNodeContracts.py; concrete test bindings — tests/lifecycle/support/writeNodeBindings.py. Engine-only reusable error carriers — proposed app/dataModel/engine/nodes/snapshot/contracts.py. Никаких production registrations для synthetic типов. Existing Lifecycle 9 registrations не переименовываются.

Перед кодом проверить отсутствие существующих wrappers/carriers с той же ролью и exact target protocol path; reuse при наличии. Результат owning метода, готовность реализации ноды и регистрация — отдельные статусы.

| Граница | Сейчас | Следующий конкретный результат |
|---|---|---|
| Assembly owning POJO/API | Существуют | PatchSet подтверждает exact named result binding и exception boundary, без внутреннего trace |
| Apply owning POJO/API | POJO/порт существуют, full public implementation не готова по последней проверке | Snapshot подтверждает публичный IO/Error roster и статус готовности target |
| Node wrappers/IDs/Error | PROPOSED в этой карте | Совместная приёмка новых node-контрактов; не выдавать за уже зарегистрированные |
| assemble → apply edge | Mapping полностью предъявлен | Type test exact classes/values; refusal/fault не вызывает apply |
| write_changes / prepare_changes | Остаток конкретизации | Отдельные concrete Input/Output/CALL cards; не закрываются этой парой leaf |

Проверки нод: один public вызов, неизменные payload/types/diagnostics/indices; все outcome branches; unknown/foreign model rejection; contract identity/duplicate registration; no dependent CALL после refusal/error/cancel. Проверка API может использовать явный spy и не доказывает domain commit. Domain algorithms/tests остаются у владельцев.
