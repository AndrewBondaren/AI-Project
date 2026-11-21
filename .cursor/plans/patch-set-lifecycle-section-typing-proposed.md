# PatchSet: Lifecycle mixed section и closed node bindings

2026-11-21. PROPOSED owning ответ на задание №2 [локального node-плана](gen-dag-lifecycle-node-contracts.md). Дизайн, без кода/миграций/назначения IDs. Ядро PatchSet не меняется. Scope: два synthetic entity вида, четыре перехода, одна native section, пять logical leaf операций, готовые inputs; real producers/storage/checkpoint/bulk/вариант Б вне scope и не blockers.

## 1. Рекомендация: восемь concrete native вариантов, одна секция

T — вид ссылки/участника, не полный предметный payload. TestEntityA/TestEntityB и closed request/prepared specializations размещать только в backend/tests/lifecycle/support/mixedContracts.py. Их owning generic bases остаются Lifecycle. Полные schemas/evidence/field/logic refusals предъявляет Lifecycle по node-плану: данное предложение фиксирует composition, не выдумывает поля этих POJO.

Предлагаемый owning generic wrapper в backend/app/dataModel/lifecycle/changes/transitionPatch.py:

```python
class LifecycleTransitionPatch[P: BaseModel](PatchData):
    transition: P
```

Header объявлен только в PatchData. P на runtime binding обязан быть конкретным prepared record; BaseModel/unbound не допускаются. Prepared records не наследуют PatchData: это предложение node-плана, требующее синхронизации Lifecycle ТЗ, где ещё встречается «prepared = native patch». Поля prepared не копируются в wrapper, header не появляется у каждого участника Replacement.

Exact proposed synthetic declarations в tests/lifecycle/support/mixedContracts.py (generic imports из owning Lifecycle модулей):

```python
class CreateA(PreparedLifecycleCreate[TestEntityA]): pass
class CreateB(PreparedLifecycleCreate[TestEntityB]): pass
class ReplaceA(PreparedLifecycleReplacement[TestEntityA]): pass
class ReplaceB(PreparedLifecycleReplacement[TestEntityB]): pass
class EndA(PreparedLifecycleEnd[TestEntityA]): pass
class EndB(PreparedLifecycleEnd[TestEntityB]): pass
class ReactivateA(PreparedLifecycleReactivate[TestEntityA]): pass
class ReactivateB(PreparedLifecycleReactivate[TestEntityB]): pass

type PreparedAB = CreateA | CreateB | ReplaceA | ReplaceB | EndA | EndB | ReactivateA | ReactivateB

class CreatePatchA(LifecycleTransitionPatch[CreateA]): pass
class CreatePatchB(LifecycleTransitionPatch[CreateB]): pass
class ReplacePatchA(LifecycleTransitionPatch[ReplaceA]): pass
class ReplacePatchB(LifecycleTransitionPatch[ReplaceB]): pass
class EndPatchA(LifecycleTransitionPatch[EndA]): pass
class EndPatchB(LifecycleTransitionPatch[EndB]): pass
class ReactivatePatchA(LifecycleTransitionPatch[ReactivateA]): pass
class ReactivatePatchB(LifecycleTransitionPatch[ReactivateB]): pass

type PatchAB = CreatePatchA | CreatePatchB | ReplacePatchA | ReplacePatchB | EndPatchA | EndPatchB | ReactivatePatchA | ReactivatePatchB

class LifecycleSectionAB(DomainSection[PatchAB]): pass
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

PASS feasibility closed native union без изменения PatchSet; PROPOSED выбор canonical model discrimination и named wrappers. OPEN внутри IN: полные owning prepared/evidence/refusal schemas и разрешение prepared-vs-native противоречия; exact Lifecycle closed producer/section construction mapping; решение coordinator по concrete NodeIds либо раздельным registry; synthetic manifest IDs/closure. Это конечный список необходимых локальных контрактов, а не запрос реальных доменов/storage. H2 runtime diagnostic transport и atomic handler boundary согласуются отдельно с владельцами, generic ядро не переоткрываются. Code-go/полная приёмка не объявлены.
