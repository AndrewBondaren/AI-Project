# Lifecycle: локальные ноды варианта А и пакет согласования

2026-11-21. Поручение пользователя: завершить POJO, предложить типизацию секции, точно определить node contracts и выдать владельцам ограниченные задания. Это проектирование до реализации, не code-go. Основной план — entity-lifecycle.md; развитие Б — lifecicle-todo.md.

## Фиксированный scope

IN: готовые typed inputs; четыре pure prepare-операции и pure prepare_section; пять operation leaf; exact generic POJO/evidence/refusal; native секция; Output→Input до существующего PatchSet/apply; декларация atomic boundary и синтетические проверки. OUT: реальные NPC/прочие предметные объекты, их producers/read pipelines/SQL adapters, миграция legacy, production wiring, read_world, физический Delete, settings, bulk API, родитель Б, overlapping chains, engine checkpoint/restart. Отсутствие OUT не блокирует локальную приёмку. Необходимая внутри IN типовая схема не переносится в TODO под видом внешнего producer.

## Node cards — предложение к freeze

Семейство Lifecycle; все пять — самостоятельные operation leaf без Lifecycle parent. Вызывает существующая prepare_changes; hidden CALL между leaf нет. T означает конкретный вид сущности; замкнутая специализация задаётся composition, а не строковым dispatch в ноде.

| Node / proposed NodeId | Input.request | Output.value | Public target |
|---|---|---|---|
| PrepareLifecycleCreateNode / engine.lifecycle.prepare_create | PrepareLifecycleCreate[T] | PreparedLifecycleCreate[T] или LifecycleFieldError или LifecycleLogicError | LifecycleCreatePipelineOpenPipeline.prepare_create |
| PrepareLifecycleReplacementNode / engine.lifecycle.prepare_replacement | PrepareLifecycleReplacement[T] | PreparedLifecycleReplacement[T] или LifecycleFieldError или LifecycleLogicError | LifecycleReplacementPipelineOpenPipeline.prepare_replacement |
| PrepareLifecycleEndNode / engine.lifecycle.prepare_end | PrepareLifecycleEnd[T] | PreparedLifecycleEnd[T] или LifecycleFieldError или LifecycleLogicError | LifecycleEndPipelineOpenPipeline.prepare_end |
| PrepareLifecycleReactivateNode / engine.lifecycle.prepare_reactivate | PrepareLifecycleReactivate[T] | PreparedLifecycleReactivate[T] или LifecycleFieldError или LifecycleLogicError | LifecycleReactivatePipelineOpenPipeline.prepare_reactivate |
| PrepareLifecycleSectionNode / engine.lifecycle.prepare_section | PrepareLifecycleSection | LifecycleSection или concrete owning section refusal | LifecycleSectionPipelineOpenPipeline.prepare_section |

Wrappers: PrepareLifecycleCreateInput/Output[T], PrepareLifecycleReplacementInput/Output[T], PrepareLifecycleEndInput/Output[T], PrepareLifecycleReactivateInput/Output[T], PrepareLifecycleSectionInput/Output. Только request/value соответственно; strict/frozen/extra-forbid/revalidate semantics согласно общему POJO-контракту. Нет второй копии domain fields. Пути proposed: dataModel/engine/nodes/lifecycle/contracts.py и application/engine/nodes/lifecycle/. Exact layout и NodeId collision/specialization registration проверяются до freeze.

Mapping: input.request передаётся публичному методу; returned value помещается в output.value неизменным. Domain refusal — value, не успешный prepared object. Engine input admission выполняется до вызова. Cancellation/runtime exception не превращаются в business refusal; blanket catch нет. Новая LifecycleNodeError не вводится без owning public fault. Нужно сверить достаточность existing runtime failure transport, а если обязателен declared error — предъявить конкретный owning fault и mapping, не пустую заглушку.

## Типизация коллекции — рекомендация координатора

Раздельные типизированные prepare-вызовы возвращают конкретные prepared records. Общий prepare_section принимает закрытый union разрешённых специализаций и операций. Для проверки использовать два синтетических вида TestEntityA/TestEntityB, не production NPC. Конкретные имена и representation типов выбирает Lifecycle после проверки reuse; не добавлять fictional production entities.

Предлагаемый принцип: каждая native patch-оболочка сохраняет конкретный prepared record и inherited PatchData.header. Конкретная LifecycleSection содержит tuple закрытого union этих patches; один общий owning section key, не по секции на вид. Exact Python declaration/дискриминация/manifest предъявляются PatchSet и Lifecycle: записи должны сохранять вид после decode, не использовать Any, BaseModel, голый UID или открытый generic. Общий алгоритм не ветвится по TestEntityA/TestEntityB. Изменение разрешённого состава — composition/schema review, не модификация DAG-алгоритма. Это рекомендация, не утверждённый mixed-type wire contract.

100 независимых Create одного вида дают 100 prepared records и 100 patches в одной секции. Один Replacement со 100 участниками даёт один patch. При mixed наборе эти правила не меняются; участник не пересекается между переходами. Коллекция сохраняет входной порядок; ordinal — адрес, не зависимость состояний. Отказ не выдаёт частичную секцию. Bulk API не требуется для доказательства этих контрактов.

## Задания владельцам и условия ответа

Lifecycle: предъявить полные схемы четырёх requests/prepared outputs, typed refs/capture/reason/evidence, field/logic/section refusals и invariants; mapping всех полей и reuse existing types. Устранить конфликт «prepared уже native patch» против «native wrapper появляется в prepare_section». Предлагаемая граница: pure prepared record переиспользуется wrapper без копирования payload; один источник header. Дать pure helper ответственность и порядок checks/build, без IO. Proof от предметного mock должен иметь определённый контракт, а не trusted=True или фиктивное отсутствие required данных. Coverage/no-domain-patch конкретизировать на синтетике, не ждать реальных доменов.

PatchSet: проверить exact closed union двух видов, native wrapper/section types и registry/codec compatibility; как одна logical node registration получает closed POJO specialization без dynamic kind dispatch. Выдать точные declarations и synthetic admission/round-trip критерии. Не менять принятое ядро PatchSet, не требовать реальных domain adapters. Новые numeric IDs не назначать без общей сверки.

Snapshot: предъявить ограниченную atomic boundary для готовой Lifecycle section: какие проверки до transaction и внутри, кто проверяет source/base/evidence/duplicate change_uid, где assigned refs, validate/apply/receipt/CAS/commit/unknown. Отличить semantic predicates Lifecycle от Snapshot provenance и PatchSet output admission. Если handler является transaction participant, явно описать разрешённые capability/вложенные вызовы, без автоматического разрешения foreign writer по DI. Нужны typed протокольные обязанности и synthetic fake participant, не production SQL adapter, не перенос H3 Time на Lifecycle. Не переоткрывать принятый C1/C2 или порядок write flow.

Координатор: после owning ответов свести полную node Input/Output/Error карту, exact registration, рекомендации union и общий PASS/OPEN/FAIL только для IN. Ответ каждого владельца обязан назвать: что завершено; точные оставшиеся решения IN; зависимости OUT отдельно. Не выдавать runtime readiness за contract PASS и не возвращать OUT в blockers. Общие решения предъявляются пользователю; код не меняется в этом задании.
