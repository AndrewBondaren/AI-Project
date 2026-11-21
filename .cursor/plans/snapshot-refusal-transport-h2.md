# Snapshot owning ответ H2-3/H2-6 и требования H2-4/H2-5

## Сводный статус и открытые вопросы — 2026-11-21

Проверены актуальные решения общего H2-плана, реестра, owning Publication/PatchSet и Snapshot. Это обновление статуса, не приёмка всего H2 и не code-go.

**Закрыты решения:** одна current TimeSnapshotApplyResult без legacy; IDs31007/31139/31140/20150; pair(format1,root20150); reuse TimeSectionRefused и Time-owned semantic validator; узкий build_time_snapshot_binding с единственным owning publication_binding и локальное владение construction checks. Локальный H3 принят отдельно. Цепочка SectionHandlerContractError получила PASS координаторской сверки ответственности/порядка в ограниченном scope; runtime evidence ещё отсутствует.

**Construction signatures сведены 2026-11-21, owning proposal для общей сверки:** Snapshot получает непосредственно PublicationResultBinding[T] и registry; промежуточный SnapshotApplyBinding отменён. TimeSnapshotBinding остаётся single-field, никаких несуществующих binding.refusal_model/result_model properties не требуется. Точные signatures/mapping ниже; generic core не импортирует Time types. Архитектура узкого builder не изменена.

**На общей приёмке:** окончательная сверка current signatures/вложенных calls, bounded decode configuration API и concrete apply node binding. Принятые semantics budgets/ошибок/expected-root и no-legacy не пересматриваются. Runtime manifest closure/collision audit, registrations, rollback/round-trip/replay/unknown-root tests — задачи реализации, не новые пользовательские вопросы о выбранных IDs/representation.

**Отложено пользователем:** exact engine mapping durable OperationCancelled после основной реализации. Не блокирует ограниченный H2 transport; обязателен перед сквозной приёмкой durable-cancellation сценария. Обычные cancellation/drain/unknown semantics сохраняются сейчас.

**За пределами H2:** весь Snapshot ARCH-0 и C2 не закрыты. В отдельном C2 review остаются R4 (единые provenance predicates/extraction), R3/R5 (malformed/diagnostic aggregation/address compatibility); R1/R2 и поправка H3 к фазе source reads не переоткрываются. Не считать эти вопросы prerequisites повторного утверждения пары или локального H3.

Ни legacy roster, ни утверждение format1+20150, ни выбор места source reads больше не являются открытыми вопросами. Исторические противоположные статусы ниже не применяются. Construction signatures сведены; следующий шаг — окончательная координаторская сверка предложенного mapping с owning contracts.

**УТВЕРЖДЕНО пользователем 2026-11-21: current Snapshot pair `(format_version=1, root_id=20150)`.** Concrete модель `TimeSnapshotApplyResult` применяется для новой записи и exact replay текущего Snapshot-маршрута. Архитектурный выбор пары закрыт; прежние пометки «кандидат», «freeze OPEN» и «требуется утверждение пары» ниже заменены этим решением. Legacy fallback не вводится, прежние IDs не переназначаются, актуальные Pack/Gameplay/Cancelled не меняются. Runtime binding, полный manifest closure/collision audit, strict bounded decode, round-trip/replay и отказ на неподдерживаемые root/format без повторного apply ещё требуют реализации и проверки. Утверждение пары не означает приёмку всего H2 или разрешение на код/миграции.

## Решение пользователя 2026-11-21 — отложенный cancellation mapping

Пользователь разрешил уточнить exact передачу сохранённого OperationCancelled через engine после реализации основного H2. Этот mapping больше не блокирует принятие и реализацию ограниченного H2 transport бизнес-результатов/contract faults; прежние формулировки gate ниже заменены в этой части. Это изменение scope приёмки, не утверждение, что недоопределённая полная node boundary прошла обязательные критерии.

До отдельного решения сохраняются owning OperationCancelled/operation_id и SnapshotOperationCancelledError; запрещены преобразование в T/REJECTED/CONFLICT, потеря identity и вымышленный успешный node output. Exact engine transport этой ветки не реализуется по предположению. После основной реализации, до сквозной приёмки durable-cancellation сценария, Snapshot и engine обязаны предъявить mapping и проверить identity/replay/cancellation. Обычный CancelledError, drain, unknown приоритет и отсутствие business refusal для infrastructure faults не откладываются. Разрешение уточнить mapping позднее само по себе не является code-go всего H2; остальные решения/приёмка сохраняются.

## Owning mapping SectionHandlerContractError — 2026-11-21, PROPOSED

Источник: PatchSet H2 §2, `application/patch/errors.py::SectionHandlerContractError(RuntimeError)`. Это output-contract failure BoundSectionHandler после return, не SectionRefused и не C2 provenance issue. Snapshot принимает owning классификацию PatchSet, не повторяет exact-type/model checks и не проверяет Time semantic predicates.

**Точное место перехвата:** `application/worldSnapshot/service/worldSnapshotService.py`, внутри основной apply transaction, непосредственно вокруг каждого `await bound_handler.validate(section, validation_context)` и `await bound_handler.apply(section, apply_context)`. Узкий `except SectionHandlerContractError as error` выполняет `raise PublicationInfrastructureError("section handler output contract violated") from error`. Используется existing infrastructure carrier `application/publication/errors.py`, новая exception/diagnostic модель не нужна. Контекст stage/section_index можно включить в safe internal log; domain operands/фиктивный FieldPath в public fault не создаются. Не перехватывать здесь RuntimeError/Exception/BaseException целиком: exceptions/cancellation самого handler проходят прежним owning путём.

После такого raise немедленно прекращаются дальнейшие validations/apply, accumulation, metadata, CAS и terminal. Ошибка выходит из transaction body; transaction owner выполняет rollback/drain/revoke. Snapshot не перехватывает PublicationInfrastructureError внутри transaction ради продолжения, не вызывает record_refusal, не создаёт REJECTED/CONFLICT и не финализирует operation самостоятельно. Writes предыдущих handlers откатываются вместе; в validation фазе действует тот же путь завершения transaction, даже если domain writes ещё не было.

**Public mapping только после выхода transaction:** existing proposed Snapshot public apply boundary в `application/worldSnapshot/errors.py` выдаёт SnapshotPublicError с SnapshotPublicFault(operation=APPLY, kind=INFRASTRUCTURE_FAILURE, operation_id/request_fingerprint из уже проверенного binding, input_issues=()). `raise SnapshotPublicError(fault) from infrastructure_error` сохраняет цепочку public → PublicationInfrastructureError → SectionHandlerContractError → исходная output-validation cause (если была). Нельзя ловить первичный contract fault вне owner context и заранее утверждать rollback.

**Приоритет исхода owner:** если rollback/cleanup не подтверждён и coordinator выдаёт UnknownCommitOutcome, внешний mapping выбирает OUTCOME_UNKNOWN с checked binding, а не INFRASTRUCTURE_FAILURE первичного output fault. Cause/context исходной ошибки сохраняются для owning diagnostics, но certainty не выдумывается. Если owner после drain распространяет CancelledError, она остаётся runtime cancellation, не SnapshotPublicError; первичная ошибка может остаться в exception context. Нельзя превращать cancellation в durable OperationCancelled без отдельного owning lifecycle. Existing rollback/quarantine механизм не меняется этим proposal; actual commitScope.py подтверждает rollback на BaseException и приоритет unknown/отмены. Ошибка после успешного return handler не является новым public input fault и не mapping INVALID_INPUT.

**Выход в apply_snapshot:** SnapshotPublicError(fault) → PythonNodeError(SnapshotNodeError(error=fault)), согласно existing planned node boundary; node не перехватывает SectionHandlerContractError отдельно и не создаёт ApplySnapshotOutput[T] при fault. Unknown остаётся OUTCOME_UNKNOWN, обычная cancellation — engine cancellation. Отдельный OPEN durable OperationCancelled transport этим правилом не закрывается. Node/public fault API ещё proposed; это конкретизация owning mapping для общей приёмки, не runtime evidence.

Приёмка будущей реализации: неверный validate branch/структурно повреждённый refusal/foreign apply output → infrastructure fault с cause, нет последующих handlers и record_refusal; writes предыдущей секции rolled back; rollback failure → unknown; cancellation во время rollback → owning исход после drain; произвольная exception самого handler не заворачивается BoundSectionHandler или новым blanket catch; valid SectionRefused остаётся business путём; malformed output не подменяет C2 receipt provenance. H3/no-legacy/IDs/Time predicates не пересматриваются. Код не изменён.

**Последнее решение пользователя 2026-11-21 — БЕЗ LEGACY.** Поддержка прежних Snapshot terminal representations не требуется. Это заменяет прежнюю W/R compatibility policy: одна целевая concrete модель результата для новой записи и replay текущего маршрута, без OldSnapshotApplyResult union, legacy readers/manifests, old→new adapters, fallback и migration ради совместимости. Вводить два независимых набора W/R только ради legacy больше не нужно; точные упрощённые signatures сводят владельцы. Replay текущих операций сохраняется: те же данные/типы/identity, без повторного handler. Неподдерживаемый сохранённый root/format — явная инфраструктурная несовместимость, не отсутствие terminal и не разрешение повторить операцию. Принятые новые IDs31007/31139/31140/20150 сохраняются; прежние IDs не переназначаются. Pack/Gameplay/Cancelled — отдельные актуальные kinds, не legacy Snapshot, автоматически не удаляются. Legacy roster/corpus больше не gate H2. Новый root-dispatch API не вводится только ради выбора legacy readers: необходимость пересмотреть, сохранив strict expected root/full bounded decode и budgets. Решение не разрешает удалять данные, писать код или миграции; финальная упрощённая цепочка ещё требует сверки.

## Актуальные упрощённые signatures — 2026-11-21, PROPOSED

Одна текущая модель `T = TimeSnapshotApplyResult`, canonical root20150, с diagnostics `SnapshotApplyRelationIssue | TimeCommitRelationIssue`. T применяется к новой записи и exact replay. S=TimeAdvanceSection фиксируется экземпляром; D=TimeCommitRelationIssue остаётся только параметром registry/result semantics. **Никакого OldSnapshotApplyResult в публичном output, независимых W/R или legacy reader roster.** Дальнейшие §1–8 сохранены как история; противоположные W/R/readers/compatibility требования **SUPERSEDED**, не gates.

Точные target signatures (не код):

| Existing/planned модуль | Упрощённая декларация |
|---|---|
| application/worldSnapshot/contracts/applyPort.py | `IWorldSnapshotApply[S: DomainSection,T]`; `async apply(self, patch_set: PatchSet[S]) -> T` |
| dataModel/engine/nodes/snapshot/contracts.py | Existing planned `ApplySnapshotInput[S].patch_set: PatchSet[S]`; existing planned `ApplySnapshotOutput[T].value: T` |
| application/worldSnapshot/service/worldSnapshotService.py | `WorldSnapshotService[S,D,T]`; `__init__(self, registry:SectionRegistry[D], world:IWorldPublicationStore, players:IPlayerPublicationStore, history:ISnapshotHistoryStore, *, publication_binding:PublicationResultBinding[T], operations:IOperationStore[T]) -> None`; `async apply(self, patch_set:PatchSet[S])->T`; `_claim_publication(operation_id:EntityUid, world_uid:EntityUid, preparation_fingerprint:RevisionHex, request_fingerprint:RevisionHex)->PublicationOwner|T`, async |
| application/worldSnapshot/contracts/applyBinding.py | Прежний proposed SnapshotApplyBinding отменён; новый файл/класс в этом срезе не нужен. Служебный TypeAdapter[S] не поле composition binding; existing input/registry admission остаётся у своих owners |
| application/publication/contracts/operationStore.py — согласуемая дельта Publication | `IOperationStore[T]`: `read(operation_id)->OperationRecord[T]|None`; `claim_publication(kind,operation_id,world_uid,preparation_fingerprint,request_fingerprint)->OperationClaim[T]`; `record_refusal(claim:PublicationOwner,outcome:T)->None`; `record_terminal(scope:CommitScope,outcome:T|PackActivationResult|GameplayStarted|OperationCancelled)->None` |

Конечный mapping: **ApplySnapshotInput[S].patch_set → await IWorldSnapshotApply[S,T].apply(input.patch_set) → ApplySnapshotOutput[T](value=result)**. Прямое сохранение текущего concrete типа/всех diagnostics/identity; replay не вызывает handler. SnapshotPublicError→SnapshotNodeError сохраняет отдельный planned mapping; обычная cancellation и OPEN transport SnapshotOperationCancelledError остаются отдельно от business T. Нового NodeId/envelope нет.

Composition остаётся `backend/app/composition/snapshotTime/{contracts.py,binding.py}`: именованный T, reuse TimeSectionRefused, одна конфигурация registry/Snapshot/Publication. Constructor consistency: exact section types S, D/local subset, result_model T с закрытыми diagnostics; тот же exact T в PublicationResultBinding[T], codec, OperationRecord[T]/claim и staging/lease returns. Конфигурации предъявляются через согласованные публичные read-only properties; private introspection запрещена. Ошибка configuration до IO — TypeError/ValueError, не business refusal.

Сверенная Publication binding: `PublicationResultBinding[T]` содержит result_model:type[T], **snapshot_format_version:FormatVersion**, manifest:CanonicalSchemaManifest, record_model:type[OperationRecord[T]], limits:DecodeLimits; owning module application/publication/contracts/resultBinding.py. Store/ledger/staging/codec предъявляют один binding через read-only result_binding; store/staging/leases — record_model. Независимых read/write models/readers нет; recover/cancel в Snapshot apply не добавляются.

**Принято пользователем 2026-11-21 — узкий construction binding:** `composition/snapshotTime/binding.py::build_time_snapshot_binding(*, publication_binding: PublicationResultBinding[TimeSnapshotApplyResult]) -> TimeSnapshotBinding` создаёт только frozen application binding с единственным полем `publication_binding`. Он не принимает registry/services/store/ledger/staging/leases, не выдаёт service/node bindings и не собирает runtime. `PublicationResultBinding` при собственном construction валидирует schema/format/manifest/limits/record_model; `TimeSnapshotBinding` проверяет exact `result_model is TimeSnapshotApplyResult`, принятую declaration root20150 и совместимость Time diagnostic roster через публичные данные owning binding. Повторно запускать `PublicationResultBinding.__post_init__`, копировать его predicates или читать private attributes нельзя. Ошибки типов — TypeError, несовместимых значений/identity — ValueError, до IO.

Application composition root передаёт `time_binding.publication_binding` как `publication_binding` в Snapshot и как binding в Publication codec; operations предоставляет тот же объект через result_binding. Registry создаётся с TimeSectionRefused. Concrete IC-1 wiring проверяет `registry.refusal_model is TimeSectionRefused` и `registry.diagnostic_types == frozenset({TimeCommitRelationIssue})`; TimeSnapshotBinding уже проверил exact TimeSnapshotApplyResult/root20150. Эти concrete имена не импортируются WorldSnapshotService.

Generic Snapshot constructor проверяет `publication_binding is operations.result_binding` и `operations.record_model is publication_binding.record_model`. Кроме того, он проверяет локальную связь diagnostics результата и registry: множество exact concrete classes из публичной `publication_binding.result_model.model_fields['diagnostics'].annotation` должно равняться `{SnapshotApplyRelationIssue} | registry.diagnostic_types`; допустима только tuple[closed union,...], без Any/BaseModel/open FieldPathError и без subclass widening. Разбор annotation через публичные typing.get_origin/get_args и model_fields — только Snapshot relation check, не повторное schema/manifest/limits validation Publication. Для runtime refusal exact type/roster проверяет PatchSet; Snapshot эти проверки не копирует. S остаётся instance type parameter, concrete input/node binding задаёт composition, existing section admission принадлежит registry.

Модель создания всех новых результатов берётся только из `self._publication_binding.result_model`; отдельный result_model/refusal_model/manifest state в Snapshot не вводится. Replay возвращает проверенный T operations без adaptation. Publication/Artifacts constructors отвечают за локальные identity связей codec/store/ledger/staging/leases; builder не принимает эти сервисы и не проверяет весь граф. TypeError — неверный тип/открытая declaration, ValueError — несовпадающие identities/rosters; все construction checks до IO. Узкий builder и public apply signature не изменены. Сведение требует финальной междоменной сверки, не означает разрешения реализации.

Это принятое разделение ответственности заменяет противоречащие ему исторические описания binding ниже, включая дублирование manifest/result/refusal полей. H2 остаётся отложенной зависимой интеграцией; решение не добавляет реализацию runtime, подключение write_changes или подготовку входов в текущий скоуп. Порядок DAG и доменные проверки неизменны. См. [единый контракт composition](patch-set-refusal-transport-h2.md#3-единая-локальная-composition).

Named node bindings в composition/snapshotTime/contracts.py: TimeApplySnapshotInput(ApplySnapshotInput[TimeAdvanceSection]), TimeApplySnapshotOutput(ApplySnapshotOutput[TimeSnapshotApplyResult]), без новых полей/NodeId/envelope. Node-план и ТЗ синхронизированы как target design; финальная координаторская приёмка не подменяется этой правкой.

**Условия закрытия оставшихся замечаний:** REP — явный freeze current pair (1,20150) координатором/пользователем после owning подтверждения неизменной row/TLV оболочки и exact closure; runtime round-trip/unknown-root/budget evidence отдельно. CANCEL — Snapshot+engine предъявляют mapping SnapshotOperationCancelledError с сохранёнными OperationCancelled/operation_id, отдельно от business T и обычного CancelledError; до этого полная node boundary не PASS. Новые enum/transport по предположению не создаются. Legacy roster не является условием.

Codec encode принимает T плюс три актуальных non-Snapshot kinds; decode возвращает тот же union, а Snapshot claim принимает только T или existing cancellation path и отвергает чужой success kind. Root выбирается существующим outcome_kind с **фиксированным expected T/root20150 для snapshot_apply**, затем strict full bounded decode и owning row/body checks. Новый root extraction/legacy dispatch API только для этой цепочки не требуется. Unknown root/format → PublicationInfrastructureError с cause, без fallback, missing-terminal трактовки, записи или повторного apply. Budgets, configuration errors и full decode остаются обязательными. Pack/Gameplay/Cancelled не удаляются как «legacy».

Confirmed rollback → construction T → record_refusal(claim,T) → confirmed persistence → return T сохраняется. Unknown/cancellation не становятся business отказом. Для success прежняя main transaction/terminal/commit граница неизменна. Source/state reads отсутствуют при replay текущего terminal; инфраструктурные evidence checks Publication сохраняются.

**Остатки:** финальная сверка сведённых signatures/properties и engine output, encoding API review; exact manifest closure/runtime registration и tests относятся к реализации. Pair(1,20150) и IDs31007/31139/31140/20150 утверждены; legacy roster не gate. Cancellation mapping отложен пользователем. Код/миграции не поручены; полный H2 не объявлен принятым.

## Исторические решения до отказа от legacy — SUPERSEDED в части W/R и совместимости

Прочитано полное [решение координатора](interdomain-refusal-transport-h2.md). **ACCEPTED пользователем:** новая запись W; exact replay исходного поддерживаемого concrete члена R без old→new adaptation. Старый root20124/format1 сохраняет declaration, identity и meaning; roots20125/20126/20127 сохраняют existing representation. Generic модель не подменяет legacy root. Полный legacy diagnostic roster отдельно OPEN; неизвестные historical subclasses автоматически не поддерживаются, БД не обследованы.

**Canonical IDs ACCEPTED:** TimeCommitIssueCode ENUM31007; PrepareTimeAdvanceSection RECORD31139; TimeCommitRelationIssue RECORD31140; TimeSnapshotApplyResult RECORD20150. Альтернативы31108/31109 сняты. Прежние native IDs и20124/20128/20131 неизменны; runtime TimeSectionRefused и validator errors без новых IDs. Это назначение, не runtime registration/round-trip evidence.

**Encoding boundaries ACCEPTED:** configuration проверяется encoding до чтения, значения задаёт composition; прямой helper также проверяет configuration. DecodeLimits budgets — strict positive int без bool; bounds 0 ≤ minimum ≤ maximum; field limits соответствуют моделям, противоречивые duplicates запрещены. TypeError — неверный тип configuration, ValueError — неверное значение/отношение; CanonicalEncodingError — malformed bytes/tag/length и превышение корректного budget. Publication сохраняет cause в infrastructure failure.

Один shared parser: read_record_root_id проверяет размер и внешнюю RECORD-оболочку/границы/положительный ID и budgets прочитанной части, не валидирует nested payload. Принятый terminal trace: row/size → checksum → root extraction → exact (format_version,root_id) reader → full bounded decode → row/body identity/category → owning operation checks. Полный decode обязателен; пробные decode/fallback/SQL parser copy запрещены. API/configuration consumer review ещё OPEN.

**Publication классифицировано пользователем как инфраструктурная часть ядра Snapshot**, не отдельный предметный домен. Внутренний operation store не foreign public pipeline; exact capabilities/nested calls всё ещё проверяются. Это не разрешение произвольных междоменных вызовов.

Остатки до полного H2 freeze: signatures/configuration/node output review; encoding API review; полный supported legacy diagnostic roster; новая write representation pair. **format1+root20150 — пока кандидат**, не accepted pair; automatic bump отсутствует. Самостоятельная serialization20128/20131 требует подтверждённого consumer. H2 целиком OPEN, код/миграции не разрешены. Этот раздел заменяет исторические PROPOSED/OPEN ниже только по явно принятым пунктам.

## H2-SIG: exact output apply_snapshot — уточнение 2026-11-21, PROPOSED

Параметризуется **существующий planned ApplySnapshotOutput**, не создаётся новый envelope. Источник: [gen-dag-snapshot-node-contracts.md §1](gen-dag-snapshot-node-contracts.md), проектный модуль `backend/app/dataModel/engine/nodes/snapshot/contracts.py`. Target declaration: `class ApplySnapshotOutput[R](BaseModel): value: R`; прежняя strict/frozen/extra-forbid/revalidate-always конфигурация сохраняется. Input остаётся `ApplySnapshotInput[S].patch_set: PatchSet[S]`. Generic shape не является готовым runtime output_type: закрытая IC-1 composition подставляет R=OldSnapshotApplyResult | TimeSnapshotApplyResult, с exact-type сохранением уже декодированного value. Named registration binding согласуется в том же composition/snapshotTime; нового NodeId, дополнительной обёртки или fallback к base SnapshotApplyResult нет.

**Конечная строка:** `ApplySnapshotInput[S](patch_set: PatchSet[S]) → await IWorldSnapshotApply[S,R].apply(input.patch_set) → ApplySnapshotOutput[R](value=result)`; `SnapshotPublicError(fault) → PythonNodeError(SnapshotNodeError(error=fault))`, обычный CancelledError → existing runtime cancellation. Business CONFLICT/REJECTED остаются value, old root не адаптируется к W. SnapshotOperationCancelledError(OperationCancelled) сохраняет отдельный OPEN engine cancellation binding из §3 node-плана; H2 output уточнение не объявляет эту старую границу закрытой и не помещает OperationCancelled в R. Неизвестные infrastructure exceptions не превращаются в business output. Совместимость записи исторического node output требует того же supported R manifest/representation binding; автоматическая registration generic output не заявляется.

Общий DAG/node-план этим уточнением не редактируется параллельно координатору. Это точная предлагаемая замена его строки `ApplySnapshotOutput.value: SnapshotApplyResult` на `ApplySnapshotOutput[R].value: R`.

**Положение Publication — зафиксировано пользователем 2026-11-21.** Publication является общей инфраструктурной частью ядра Snapshot, а не самостоятельным предметным доменом. Оно обслуживает operation identity/immutable request binding, lifecycle выполнения, транзакционную фиксацию, terminal persistence и exact replay для Snapshot apply, Pack activation и gameplay start. Выражение «владелец Publication» означает владельца этой инфраструктурной части; отдельные чат и каталог application/publication не задают отдельный домен. Snapshot владеет применением готовых изменений и моделью apply result; предметные домены — семантикой своих данных/diagnostics; Artifacts — хранением artifacts и их защитой; DAG — оркестрацией. Зависимость Snapshot → внутренний Publication operation store классифицируется как инфраструктурная связь внутри ядра, но exact capability, nested calls и H2 contracts ещё проверяются. Эта классификация не разрешает произвольные foreign public pipeline calls, не передаёт Publication доменную семантику и не закрывает H2.

**Финализация H2-SIG/REP/IDS — §8 ниже:** S-bound instance, write W/read R и минимальный compatibility roster. PROPOSED для финальной приёмки; placement composition/snapshotTime согласован владельцами, runtime evidence отсутствует.

**Актуальный итог согласования 2026-11-20: §7 ниже.** Он заменяет прежнее предложение единого read/write result в §2/§5 на W/R и сохраняет принятый reuse TimeSectionRefused. Статус итогового предложения PROPOSED; H2 целиком не принят.

2026-11-20. **PROPOSED**, ответ на [общую постановку H2](interdomain-refusal-transport-h2.md), без реализации/миграций. H3 принят отдельно и не переоткрывается. Этот документ не меняет порядок C2 и не закрывает Snapshot ARCH-0. Координатор сверяет владельцев и предъявляет решение пользователю; назначения composition/Publication ниже — предложения, не самовольная передача владения.

## 1. Existing evidence и поддерживаемое направление

Проверены `backend/app/dataModel/worldSnapshot/results/apply.py`, `application/worldSnapshot/contracts/applyPort.py`, `application/worldSnapshot/service/worldSnapshotService.py`, `db/repositories/sqlite/snapshotCore/operations/{operationStore,terminalCodec}.py`, `dataModel/artifacts/lifecycle/operation/record.py`, `application/publication/contracts/operationStore.py`, `application/artifacts/encoding/coreManifest.py`.

Existing result допускает FieldPathError | SnapshotApplyRelationIssue; apply port возвращает неподставленный result; service helpers создают его напрямую. Полный public apply lifecycle не реализован этими helpers. Existing FieldPathError специально поддерживает named concrete subclasses при revalidation; проблема не в обязательной потере каждого field subclass, а в открытом runtime roster и отсутствии domain relation carrier. Time relation issue в existing result не допускается.

Поддерживается направление PatchSet из общей постановки: SectionRefused[D], SectionValidation[D], DomainSectionHandler[S,D], refusal_model, SectionRegistry[D]. Snapshot не назначает вторую registry или копию checks локального refusal. D — закрытый union конкретных immutable diagnostic records, field и relation; generic bound BaseModel только ограничивает typing, не разрешает BaseModel/Any/dict как runtime carrier. Именованный TimeSectionRefused остаётся у Time. Точный PatchSet construction contract должен быть сверён по owning ответу H2-1; общей постановки недостаточно для объявления его принятой реализацией.

## 2. H2-3: результат, admission и construction binding

TARGET existing module `dataModel/worldSnapshot/results/apply.py`: `SnapshotApplyResult[D]` с прежними полями category, operation_id, request_fingerprint, committed и `diagnostics: tuple[SnapshotAdmissionIssue | D, ...]`. Frozen/strict/extra-forbid/revalidate-always; COMMITTED требует refs и пустые diagnostics, CONFLICT/REJECTED требуют непустые diagnostics и committed=None. Неподставленный/открытый generic не допускается ни при создании, ни в decoder. Перенос persisted identity этого класса НЕ разрешён автоматически; §5.

**Закрытый admission roster для узкого H2:** `SnapshotAdmissionIssue = SnapshotApplyRelationIssue` из existing results/applyIssues.py. Его owning enum и exact optional-context invariant сохраняются. Generic FieldPathError удаляется из целевого runtime annotation; existing конкретные domain field issues включаются в D соответствующей composition. Никакие неизвестные field classes не молча отбрасываются. Если request-validator реально должен выдавать дополнительный Snapshot-owned field/relation record, его требуется явно добавить в roster с canonical closure до подключения такого producer. Не назначать универсальный «прочий issue».

JsonFieldError/WireShapeIssue из proposed public INVALID_INPUT boundary не переносятся автоматически в business diagnostics. Structural admission и existing business outcomes не переклассифицируются ради H2; exact dependency diagnostics остаются отдельным Snapshot admission design вопросом. H2 сохраняет данные поступившего typed refusal, но не объявляет недетализированный общий request-validator готовым.

TARGET `application/worldSnapshot/contracts/applyPort.py`: `IWorldSnapshotApply[S, D]`, `async apply(self, patch_set: PatchSet[S]) -> SnapshotApplyResult[D]`. S привязан composition на уровне экземпляра, а не unrestricted method generic. Все records/refs остаются owning POJO. Внешние exceptions — существующие owning admission/public/infrastructure/cancellation contracts; H2 не создаёт новый public fault enum. Для IC-1 конкретный вход — PatchSet[TimeAdvanceSection], результат — именованный TimeSnapshotApplyResult(SnapshotApplyResult[TimeCommitRelationIssue]). Если Time H2-2 добавит допустимые field records, TimeDiagnostic union должен быть явно расширен до binding; сегодня они не выдумываются.

TARGET `WorldSnapshotService[S,D]` получает дополнительно `result_model: type[SnapshotApplyResult[D]]` и registry, привязанную к тому же D. Это data/model dependency, не callback pipeline и не result factory с бизнес-логикой. Composition передаёт именованный closed class; constructor отвергает generic root, несовместимый D/registry и mismatch модели Publication binding до первого apply. Список exact admitted diagnostic classes принадлежит composition binding; несовместимость — construction error, не business refusal.

Все service paths создают result только через self._result_model: admission/business checks, operation-binding mismatch, aggregated validation refusal, apply refusal, COMMITTED. Snapshot не вызывает bare SnapshotApplyResult(...), не переносит результат через model_dump/dict и не восстанавливает Time operands. Перед construction проверяется exact `type(issue)` в закрытом roster; model revalidation не должна превращать неизвестный подкласс в разрешённую superclass. Корреляция operation_id/request_fingerprint берётся из принятого запроса/claim, а category/diagnostics — из проверенного refusal. Result tuple сохраняет порядок и значения; равенство object identity после strict revalidation не обещается, concrete type/все поля обязательны.

При ошибке construction либо неожиданном типе результата handler — execution contract fault (PublicationInfrastructureError или согласованный owning subclass), не REJECTED и не durable business refusal. Нельзя сохранить malformed output ради завершения operation. Existing operation-binding mismatch возвращает result без перезаписи terminal исходной операции; H2 это поведение сохраняет.

## 3. Refusal → rollback → terminal → replay

1. Registry проверяет handler-local refusal_model, затем поднимает в согласованный composition carrier SectionRefused[D], не преобразуя diagnostics. Snapshot получает только этот closed результат. В Snapshot нет Time-specific codes, проверки observed/request operands или повторной классификации Time conflict.
2. Все handler.validate проходят в existing declared order; независимые diagnostic tuples объединяются в порядке секций и producer. Общая категория по existing правилу: REJECTED при наличии REJECTED refusal, иначе CONFLICT. Это aggregation категорий, не толкование issue.code. Infrastructure fault прекращает зависимый путь и не агрегируется как business issue. H3 source reads/remaining C2 bases сохраняют принятый порядок.
3. При handler.apply refusal дальнейшие handlers/metadata/CAS не вызываются. `_ApplyRefused[D]` переносит проверенный refusal через outer transaction boundary. Этот internal control signal не является public domain exception; domain handler возвращает POJO.
4. Только после подтверждённого rollback Snapshot строит concrete refusal result и вызывает `operations.record_refusal(claim,result)`. При validation refusal действует тот же confirmed-rollback барьер. Нельзя поймать signal внутри transaction и продолжить terminal write в ней. Если transaction owner выдал UnknownCommitOutcome/cancellation, зависимое сохранение business refusal не выполняется; existing cancellation protocol не переписывается.
5. Publication владеет отдельной короткой transaction сохранения отказа, fence/claim checks и immutable terminal identity. Snapshot возвращает durable refusal лишь после успешного acknowledgement этой записи. Неизвестный исход её commit распространяется как unknown, не как успешно сохранённый отказ. Retry/replay — existing operation binding, без повторного domain apply для «проверки» исхода.
6. Exact terminal replay проходит после immutable binding и до source/base/state reads. Возвращаются сохранённые category/diagnostics/operation/fingerprint; handler/Time reader не запускаются. Неизвестный diagnostic/root/manifest не превращается в отсутствие terminal и не разрешает повторный apply. COMMITTED остаётся доступным наружу только после confirmed commit.

## 4. H2-6: один binding для узкой composition

**Решения пользователя 2026-11-20 — ACCEPTED в узкой части H2:** (1) TimeSectionRefused сохраняет только структуру и общие инварианты carrier; проверки общего request, отсутствия повторных codes, порядка diagnostics и соответствия category набору причин выполняет Time-owned validator перед возвратом handler. Семантические инварианты отдельного TimeCommitRelationIssue остаются в его owning модели. Registry/Snapshot эти predicates не копируют. Exact имя/метод validator предъявляет Time отдельно. (2) Локальная IC-1 composition переиспользует TimeSectionRefused; второй TimeSnapshotSectionRefused не создаётся. Это не отменяет отдельный Snapshot result model. Решение не выбирает путь/владельца composition, canonical IDs, terminal compatibility и не закрывает H2 целиком; код не разрешён.

Предлагаемый owner — application composition root, подтверждается координатором. Не Time core, не Snapshot core и не DAG-нода. Предлагаемые пути (новые, код не создан):

- `backend/app/composition/snapshotTime/contracts.py`: proposed именованный TimeSnapshotApplyResult(SnapshotApplyResult[TimeCommitRelationIssue]); refusal_model переиспользует Time-owned TimeSectionRefused, второй carrier не создаётся. Это узкая IC-1 composition, не выбор полного production union; размещение ещё согласуется.
- `backend/app/composition/snapshotTime/binding.py`: proposed pure construction build_time_snapshot_binding() → TimeSnapshotBinding. Binding содержит exact result_model/refusal_model и canonical manifest; application-only immutable configuration, не persisted/public DTO и не capability. Типы полей: type[TimeSnapshotApplyResult], type[TimeSectionRefused], CanonicalSchemaManifest. Контрактная проверка закрытого roster/manifest выполняется при construction.
- Existing owning factories получают один binding: PatchSet registry — composition refusal_model с Time handler local subset; Snapshot service — result_model; Publication store/codec — тот же result_model и manifest. Никаких независимых «похожих» classes с одинаковыми именами. Подключение generic OperationRecord/claim containers ниже — обязанность Publication composition, а не hidden cast в Snapshot.

Модель результата имеет единственное значение D=TimeCommitRelationIssue в этом proposal; SnapshotAdmissionIssue добавляется только result model, не local handler. Builder binding не вызывает encode/decode business values, database, Time validation или pipeline. Конкретный manifest требуется получить от owning codecs; функция не назначает новые canonical IDs. Constructor errors — TypeError/ValueError с причиной конфигурации; не отказы пользователя.

**Согласование с PatchSet:** registry обязан предоставить проверяемую связь D/refusal_model и exact local subset; Snapshot не извлекает её из нестабильных приватных Pydantic attributes и не копирует validator. Если PatchSet H2-1 предоставляет иной named construction binding, использовать его данные вместо второго roster; это точная зависимость до design close, не разрешение динамически принимать любой issue.

## 5. H2-4/H2-5: требования к Publication и codec

Owning proposal для подтверждения Publication: `StoredTerminalCodec[D]` остаётся в `db/repositories/sqlite/snapshotCore/operations/terminalCodec.py`, pure codec, constructor `(*, snapshot_result_model: type[SnapshotApplyResult[D]], manifest: CanonicalSchemaManifest)`. `encode(outcome: SnapshotApplyResult[D] | PackActivationResult | GameplayStarted | OperationCancelled) -> PublicationOutcomeRow`; `decode(row: PublicationOutcomeRow) ->` тот же union для текущей composition. Поддерживаемые legacy decode roots требуют явного расширения closed output union; не возвращать base carrier «для удобства». Model+manifest обязательны для generic runtime; default SNAPSHOT_CORE_SCHEMA не доказывает closure D.

Encode: exact registered root class и exact reachable diagnostic types; strict revalidation; canonical encode; existing checksum/category/kind/operation projection. Decode: supported row version/discriminator, checksum, exact canonical root, strict model invariants, row/body operation/category equality. Publication дополнительно проверяет operation record binding/fingerprint/world/fence по своим контрактам. Значение issue.code/Time operands codec не интерпретирует. Decode corruption/unsupported persisted type → PublicationInfrastructureError с cause; неверный runtime input encode/configuration → contract/configuration error, не business refusal. Неизвестный subtype не декодируется как ближайшая superclass.

**Недостаточно заменить один codec:** existing IOperationStore, OperationLedger, SqliteOperationStore.record_refusal/record_terminal, `_save/_load`, OperationRecord.terminal и OperationClaim/PublicationTerminal вложенные records сейчас содержат/валидируют старый result. Publication должен предъявить generic параметризацию либо именованные closed модели всей цепочки, привязанные к result_model, с сохранением kind/world/fingerprint/fence invariants. `SnapshotApplyResult.model_validate(outcome)` в record_refusal и точные проверки type(outcome) в record_terminal должны использовать выбранную closed модель, а не стирать D. Переход через `record.model_dump()` в `_save` требует отдельной проверки сохранения concrete nested types; dict round-trip не может служить доказательством такого сохранения. H2 не меняет pack/start outcomes и не запрещает existing shared refusal cases других operation kinds без inventory.

**Source inventory representation:** `application/artifacts/encoding/coreManifest.py` уже регистрирует SnapshotApplyResult как RECORD **20124**, SnapshotApplyRelationIssue как **20307**, FieldPathError как **20137**; SNAPSHOT_CORE_SCHEMA получает shared manifests через PATCH_CORE_SCHEMA. StoredTerminalCodec поддерживает row.format_version==1, фиксированный old root и outcome_kind snapshot_apply/pack_activation/gameplay_start/cancelled. Следовательно, переназначить ID20124 произвольной новой специализации либо заменить default merged entry нельзя: это изменение wire identity, не косметическая generic аннотация.

Предлагаемая совместимость: сохранить старые readers/identity definitions для заявленных supported persisted roots; новые named roots и reachable records регистрируются только после owning решения об identity. Не назначать numeric IDs, row version bump или migration в H2 Snapshot ответе. Старый row version не обязательно меняется из-за нового canonical root — это определяется фактическим codec format, решение принадлежит Publication/encoding owner. Не смешивать domain format versions и row envelope version.

При изменении composition все ранее поддержанные replay types должны оставаться в явном read manifest/closed result union, даже если handlers для новых writes больше не регистрируются. Нельзя выкидывать diagnostics, сводить старую category к новой или заново исполнять operation. Если composition не может прочитать existing terminal, infrastructure failure/incompatible deployment; до разрешения несовместимости нельзя объявлять replay PASS. Конкретный read compatibility roster, mapping legacy root → публичный typed output и canonical closure остаются **H2-5 OPEN** до owning inventory. Сохранённые БД не обследованы; отсутствие persisted outcomes не утверждается. Новая модель не выдаётся за безусловно совместимую с 20124.

## 6. Ответственность и итог сверки

| Компонент | Ответственность и запрещённый выход за неё |
|---|---|
| Time diagnostic/local refusal | Owning operands, category, order; Snapshot не исправляет semantics |
| PatchSet registry/bound handler | Local exact-type check и closed composition admission; без Snapshot result/persistence |
| SnapshotApplyResult[D] | Только strict immutable данные/локальные outcome invariants; без IO/Time imports |
| IWorldSnapshotApply[S,D] | Public input/output mapping; без scope/codec configuration в public request |
| WorldSnapshotService / _ApplyRefused[D] | Correlation, category aggregation, rollback barrier, result construction; без интерпретации Time code, domain pipeline вызовов или нового порядка |
| Composition binding | Closed types/subsets/manifest wiring единой конфигурации; без бизнес-алгоритмов и runtime IO |
| OperationStore/Ledger/Record/claim containers | Immutable operation identity, fence, durable outcome, сохранение concrete D; без Time validation и потери subtype |
| StoredTerminalCodec / manifests | Representation/root/closure/integrity; без domain semantics, SQL lifecycle или ID reassignment |
| Transaction owner | Confirmed commit/rollback, cancellation/unknown; codec/handler не присваивают себе этот статус |
| DAG consumer | Передать typed result и применить согласованную orchestration; без decoding/normalization Time diagnostics |

Локальный proposed trace соответствует трём запретам DAG: новых route-выбирающих pipelines нет, hidden public executions нет, Snapshot не вызывает Time public pipeline; handler — уже согласованный transaction participant. H3/C2 порядок не меняется. Это документальная сверка узкого предложения, не whole-domain PASS.

**H2-3:** предложение construction/port/admission/rollback mapping предъявлено; приёмка OPEN до согласования closed roster и общей persistence цепочки. **H2-6:** конкретные пути/типы и единый binding предложены, owner composition и PatchSet construction compatibility требуют подтверждения. **H2-4/5:** переданы точные требования Publication; generic OperationRecord/claims и supported persisted roots не считаются закрытыми без owning ответа.

Будущее evidence отдельно от design: concrete Time field/relation preservation через result/store/decode/replay; aggregation порядка нескольких refusals; rejection чужого type до записи; unknown rollback без record_refusal; durable refusal save unknown не возвращает success; replay без state reads/handlers; старые supported roots; missing manifest/foreign root; composition mismatch до первого apply. Сейчас tests не запускались и код не изменён. Общий H2-план не редактировался.
## 7. Итоговый Snapshot пакет: W/R, internal port и вердикты

Сверены общий H2-план, latest write-flow фиксация в dag-multidomain-patch-publication-draft.md и ответ владельца Publication в чате `Publication: контракт adoption и READY` (01a1ea8d-2bdb-7152-bb40-925c86c041d8): separate read/write models, без old→new adaptation. **Поддерживаю это предложение с точной Snapshot дельтой ниже.** Старые §2/§5 signatures с единственным D/result_model не являются финальным replay контрактом.

### Типы и binding

- D = TimeCommitRelationIssue для узкой IC-1 composition; TimeSectionRefused переиспользуется. Time validator проверяет семантику набора до возврата handler; Snapshot/registry этих predicates не копируют.
- W = именованный TimeSnapshotApplyResult(SnapshotApplyResult[D]); diagnostics: tuple[SnapshotApplyRelationIssue | D,...]. Новый результат всегда W, включая operation-binding mismatch и COMMITTED. Existing refs/category invariants сохраняются.
- R = OldSnapshotApplyResult | TimeSnapshotApplyResult — closed public replay union. OldSnapshotApplyResult означает сохранённую прежнюю модель canonical root20124, не адаптированную новую модель; её точный Python placement и supported diagnostic manifest ещё freeze gate encoding/Publication. Нельзя сужать старые сохранённые diagnostics до D.
- `application/worldSnapshot/contracts/applyPort.py`: `IWorldSnapshotApply[S,R]`, `async apply(self, patch_set: PatchSet[S]) -> R`. S фиксируется composition экземпляра, для IC-1 TimeAdvanceSection; proposal Publication с method-generic S уточняется так, чтобы port не обещал принимать любой незарегистрированный section type. Это не изменение структуры PatchSet.
- `application/worldSnapshot/service/worldSnapshotService.py`: `WorldSnapshotService[S,D,W,R]` с constructor dependencies `registry: SectionRegistry[D]`, `write_result_model: type[W]`, `operations: IOperationStore[W,R]` плюс existing world/players/history; closed W обязан специализировать SnapshotApplyResult[D] и входить в R. Generic notation задаёт зависимости; runtime constructor проверяет named closed types, а не доверяет BaseModel bound.
- `_claim_publication(...) -> PublicationOwner | R`; `_ApplyRefused[D]` переносит typed composition refusal; все новые результаты создаются write_result_model, replay возвращает исходный член R. На replay нет W.model_validate(old_result), dict conversion или пересборки diagnostics. DAG output apply_snapshot принимает тот же R и не декодирует/нормализует Time operands. Это необходимая публичная дельта для решения пользователя.

Единое предлагаемое размещение: `backend/app/composition/snapshotTime/contracts.py` содержит W и alias R, импортирует TimeSectionRefused из Time; `binding.py` создаёт одну immutable конфигурацию registry/service/Publication. Owner — application composition, подтверждается координатором; не Time/Snapshot core и не DAG-нода. Конфигурация содержит write_model W, закрытый набор read roots R, concrete OperationRecord[R]/claim models, registry refusal_model=TimeSectionRefused, write manifest/version и reader bindings Publication. Отдельного TimeSnapshotSectionRefused нет. Это одна локальная IC-1 composition; полный production union не выбран.

### Persistence и возврат

Совместимые signatures Publication: `IOperationStore[W,R].claim_publication(kind,operation_id,world_uid,preparation_fingerprint,request_fingerprint)->OperationClaim[R]`; `read(operation_id)->OperationRecord[R]|None`; `record_terminal(scope,outcome:W|PackActivationResult|GameplayStarted|OperationCancelled)->None`; `record_refusal(claim:PublicationOwner,outcome:W)->None`. OperationRecord/PublicationTerminal/PublicationBusy параметризованы R; writer/codec/store — W,R. Recover/cancel остаются у Ledger/lease owner, в Snapshot apply не добавляются.

Registry-checked refusal выходит из общей transaction через internal signal. Только подтверждённый rollback разрешает построить W и вызвать record_refusal; Publication сохраняет его в своей короткой transaction с claim/fence checks, codec.encode(W), terminal/event append. Snapshot возвращает W после acknowledgement сохранения. Unknown/cancellation не подменяются refusal. Claim/replay читает OperationRecord[R] до новой apply transaction; после binding checks возвращает сохранённый R без handlers/source/state reads. Publication evidence может читать исторические publication rows: запрет повторного исполнения не означает запрет проверки durable evidence.

Codec соответствует ответу Publication: `StoredTerminalCodec[W,R](write_model:type[W], write_format_version:FormatVersion, write_manifest:CanonicalSchemaManifest, readers:tuple[StoredSnapshotResultReader[R],...])`; encode принимает W (плюс unchanged non-Snapshot outcomes), decode возвращает R (плюс те же outcomes). Reader dispatch только по format+canonical root ID, не перебор моделей. Старый root20124 остаётся своим типом; IDs20128(OperationRecord)/20131(SectionRefused) также нельзя переназначать из-за runtime generic delta. Safe bounded root-tag API и closed legacy manifests/corpus пока не предъявлены как закрытый контракт; это OPEN, не разрешение SQL codec копировать canonical parser.

### Классификация internal Publication port

Предлагаю Snapshot зависеть непосредственно от **IOperationStore[W,R] как внутреннего shared infrastructure port атомарной публикации**, с явным разрешённым набором выше, а не от public Publication pipeline/универсального Ledger facade. Это proposal для точной границы, не общее исключение из запрета foreign calls.

Проверенный nested route: Snapshot service → IOperationStore → SqliteOperationStore → scoped SQL/access + commit coordinator + pure terminal codec + SqlitePublicationEvidence + SqliteOperationArtifacts. Evidence обращается к DB-internal world/player publication adapters (`_by_id`, `_for_operation`), не public Snapshot/Time pipelines. Artifact dependency обслуживает operation holds через тот же shared access; не staging/producer. Store constructor проверяет общий commit coordinator/access. Claim/record_refusal владеют отдельными bookkeeping transactions; record_terminal использует supplied main transaction. Нет nested main transaction и нет изменения sequence H3/C2.

Допустимость обоснована ограниченными инфраструктурными эффектами (operation identity/fence/evidence/terminal storage), отсутствием domain pipeline dispatch и неизменным внешним DAG write flow. Владение семантикой Time не переносится. Прямой Snapshot→Time public pipeline, вызов Publication preparation/recovery orchestration из apply, запуск producer, decoder Time или нового gameplay шага через port — **FAIL**. IOperationStore нельзя расширить таким вызовом под тем же названием. Наличие DI само по себе не доказывает допустимость; координатор принимает именно описанный nested route. Read_world не участвует.

### Итог по переходам (design, не runtime PASS)

| Переход | Вердикт / конкретный результат |
|---|---|
| Time handler → TimeSectionRefused | PASS принятой границы владения/reuse; exact Time validator и payload closure подтверждает Time, Snapshot не дублирует |
| TimeSectionRefused → registry | PASS совместимости направления D; OPEN owning H2-1 exact construction/subset/result-contract checks до общего freeze |
| registry → новый W | PASS локального Snapshot proposal: exact issue types/порядок/category, admission relation roster, construction binding без Time semantics; требует пользовательской приёмки |
| W → record_refusal | PASS согласованности с Publication W/R proposal и confirmed rollback барьером; OPEN приёмки точного internal port/nested route |
| terminal decode → claim/record[R] | OPEN safe root dispatch, legacy closure/corpus/IDs и полной carrier propagation, включая Artifacts lease/staging read returns; одного codec недостаточно |
| R → Snapshot.apply → DAG | PASS proposed mapping без old→new adaptation; OPEN пользовательского принятия public union R и DAG output binding |
| Старый root → принудительно W / неизвестный terminal → повторный apply | FAIL: стирание типа либо нарушение exact replay |

Для решения пользователя предлагается единый пакет: application composition placement выше; W для новых writes/R для reads+public replay; reuse TimeSectionRefused; конкретный infrastructure IOperationStore route. До end-to-end acceptance внешние prerequisites: PatchSet exact binding; Time validator/closure; Publication propagation всех read carriers; encoding safe root dispatch и identity/version policy; supported old diagnostic manifests/golden corpus. Наличие старых БД не отрицалось и данные не мигрировались. До этих решений H2 OPEN; локальный H3 не переоткрывается. Код/ТЗ/общий H2-план этим итогом не изменены.
## 8. H2-SIG / H2-REP / H2-IDS: финальные owning предложения

### H2-SIG: один instance contract

Выбираю **S-bound instance**, уточняя method-generic предложение Publication. Existing IWorldSnapshotApply объявляет method-generic S, но concrete registry допускает конечный набор registered SectionContract.section_model. Method-generic обещание любого DomainSection шире такой composition. Поэтому TARGET `backend/app/application/worldSnapshot/contracts/applyPort.py`:

```python
class IWorldSnapshotApply[S: DomainSection, R](Protocol):
    async def apply(self, patch_set: PatchSet[S]) -> R: ...
```

R — статический параметр closed result union, не runtime BaseModel/Any. IC-1: S=TimeAdvanceSection, D=TimeCommitRelationIssue, W=TimeSnapshotApplyResult, R=OldSnapshotApplyResult | TimeSnapshotApplyResult. Error mapping — прежние owning exceptions; открытый generic не создаётся и не сериализуется. S относится только к новым input sections, не ограничивает исторические diagnostics внутри R. Historical registry handler не нужен для replay.

TARGET `backend/app/application/worldSnapshot/service/worldSnapshotService.py` (конкретные старые dependencies сохранены):

```python
class WorldSnapshotService[S: DomainSection, D, W, R]:
    def __init__(
        self, registry: SectionRegistry[D],
        world: IWorldPublicationStore, players: IPlayerPublicationStore,
        history: ISnapshotHistoryStore, *,
        binding: SnapshotApplyBinding[S, D, W, R],
        operations: IOperationStore[W, R],
    ) -> None: ...

    async def apply(self, patch_set: PatchSet[S]) -> R: ...

    async def _claim_publication(
        self, operation_id: EntityUid, world_uid: EntityUid,
        preparation_fingerprint: RevisionHex,
        request_fingerprint: RevisionHex,
    ) -> PublicationOwner | R: ...
```

`SnapshotApplyBinding[S,D,W,R]` — proposed frozen application configuration в `application/worldSnapshot/contracts/applyBinding.py`, без IO/новой authority: `section_adapter: TypeAdapter[S]`, `refusal_model: type[SectionRefused[D]]`, `write_result_model: type[W]`, `read_result_adapter: TypeAdapter[R]`. Adapter допускает closed union; передавать `type[R]` как единственную модель для union нельзя. Это один binding вместо раздельных несогласованных constructor аргументов. Поля adapters не public request/POJO и не persisted wire. Construction проверяет их закрытые аннотации и exact classes; TypeAdapter validation не заменяет exact-type guard, который запрещает coercion/subclass slicing. Generic ограничения D/W/R проверяются binding: D только concrete diagnostic records; W — named SnapshotApplyResult[D]; R состоит из exact поддерживаемых Snapshot result roots и содержит W. Public apply возвращает созданный W или исходный decoded R, не результат coercion через adapter.

Composition `backend/app/composition/snapshotTime/contracts.py` объявляет W и R, импортирует existing owning TimeSectionRefused; `binding.py` связывает один SnapshotApplyBinding, registry и Publication write/read configuration. Placement согласован владельцами; это не production readiness. Именованный duplicate refusal carrier не создаётся. Construction consistency **до IO**:

1. Section models S точно соответствуют выбранным registered contracts этой composition; local handler diagnostics — subset D; refusal_model здесь TimeSectionRefused.
2. W diagnostics = SnapshotApplyRelationIssue | D, exact immutable fields, admission roster не содержит broad FieldPathError. Time semantic validator остаётся только у Time.
3. Publication write_model **тот же W**, codec readers имеют ровно выбранные R roots; W имеет reader. Record/claim adapters содержат тот же R; неполная propagation — ошибка construction, не cast.
4. Write/read manifests имеют полный exact reachable closure и непротиворечивые registrations. Manifest прежнего reader не заменяется manifest текущего D.

Registry construction evidence поставляет owning PatchSet binding, Publication configuration — её own factory; Snapshot core не читает private attributes этих объектов ради проверки. Общая composition factory сверяет доступные configurations перед выдачей service. Если H2-1/Publication не предоставляют проверяемый construction binding, H2-SIG остаётся OPEN именно по этому Input→Input соответствию; скрытая introspection не допускается. Signatures выше — Snapshot финальный proposal, не утверждение, что public apply уже реализован.

### H2-REP: минимальный reader roster и output ноды

Новый результат W создаётся после confirmed rollback для refusal / до terminal write в основной transaction для COMMITTED и выдаётся только после соответствующего acknowledgement. OperationClaim[R] возвращает старый либо новый persisted result. После immutable binding checks `_claim_publication` возвращает тот же decoded объект; apply и output apply_snapshot передают его как R без reconstruction, union normalization, записи новой версии или вызова handlers. Не создаётся новая DAG-нода/новый wrapper DTO. Static output binding существующей apply_snapshot должен быть расширен на R до принятия цепочки; конкретный node-класс здесь не назначается.

Минимальный **предлагаемый** roster:

| Reader | Representation и exact результат | Статус evidence |
|---|---|---|
| Legacy Snapshot | row.format_version=1, canonical root20124 → сохранённый OldSnapshotApplyResult; categories COMMITTED/CONFLICT/REJECTED, исходные refs/diagnostics | Existing registration/codec подтверждены; полный supported field-diagnostic manifest/corpus OPEN |
| Current IC-1 | (write row version ещё freeze, root20150) → TimeSnapshotApplyResult; admission SnapshotApplyRelationIssue и D | ID20150 ACCEPTED; format1+20150 кандидат, pair/closure registration ещё не подтверждены |
| Existing other terminal kinds | PackActivationResult20125, GameplayStarted20126, OperationCancelled20127 в existing format1 | Сохраняются в Publication codec; НЕ входят в Snapshot public R. Cancelled идёт existing Snapshot cancellation exception; чужой success kind — infrastructure binding fault |

Root20124 с различными diagnostic closures требует явных совместимых registrations всех **поддерживаемых** старых concrete типов. Само наличие FieldPathError20137 не является полным roster. Поэтому minimum roster таблицы не означает, что legacy reader уже замкнут. Источник evidence — existing artifacts core manifest и StoredTerminalCodec; production БД/backup corpus не обследован. Неподдерживаемый root/diagnostic — инфраструктурная несовместимость, не отсутствие terminal и не разрешение повторного apply. Неизвестные representations не добавляются в R динамически. Перенос old→W отвергнут; closed R нужен именно для сохранения старого типа.

### H2-IDS: owning identity и closure W

Новый root — **TimeSnapshotApplyResult, RECORD20150 ACCEPTED 2026-11-21** (Snapshot result semantics, named class в согласованной composition). Его identity подключает composition manifest; generic SnapshotApplyResult[D] сам по себе не wire root. **20124 не используется для W**, смысл legacy root не меняется; назначение20150 не означает bump SQL format или принятие candidate pair format1+20150. Runtime registration/closure evidence ещё требуется; numeric allocation W больше не OPEN.

Closure W: existing SnapshotApplyOutcomeKind, SnapshotCommitRefs и вложенные world/player/publication refs, EntityUid/RevisionHex representations; SnapshotApplyRelationIssue с SnapshotApplyCode/SectionKey/ArtifactRef closure; TimeCommitRelationIssue с owning enum и всем достижимым request/observed closure, включая PrepareTimeAdvanceSection, TimeAdvanceProposal и TimePoint. Exact Time declarations/manifest поставляет Time, Snapshot не создаёт mirrors. Уже принятые Time native IDs не переоткрываются. Новым relation enum/request/issue, если их нет в manifests, нужны отдельные owning registrations до freeze; номера не выводятся из соседних Time IDs.

TimeSectionRefused в этом пути runtime-only и не требует новой identity из-за одного reuse. Existing SectionRefused20131 и OperationRecord20128 сохраняют прежнее значение: runtime generic propagation не даёт права переназначить их. Если proposed concrete record/claim/refusal сериализуются целиком, Publication/encoding предъявляют отдельный representation binding; terminal path сериализует W, не весь OperationRecord.

**Итог gates после решения 2026-11-21:** H2-SIG — финальная сверка factory bindings/signatures и R output ноды OPEN; H2-REP — W/R policy ACCEPTED, legacy concrete diagnostic roster/corpus и новая write format/root pair OPEN; H2-IDS — назначения31007/31139/31140/20150 ACCEPTED, runtime registrations/closure evidence отсутствуют. H2-DISPATCH — shared parser extraction + обязательный full bounded decode и классификация ошибок ACCEPTED; exact encoding API/consumer review OPEN. H3, carrier reuse и Time validator responsibility не пересматриваются; реализации/миграций нет.
