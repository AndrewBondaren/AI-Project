# Lifecycle: точные локальные контракты варианта А — предложение владельца

2026-11-21. Ответ на задание №1 [координатора](gen-dag-lifecycle-node-contracts.md). Статус всего нового дизайна ниже — **PROPOSED**, не согласован и не реализован. Основной [план](entity-lifecycle.md); owning [ТЗ](../../docs/tz_entity_lifecycle.md). Этот документ не редактирует общий node-план.

## Scope и решения для пользователя

IN: пять pure операций, точные локальные данные/ошибки, синтетические два вида, native wrapper, декларация atomic boundary. OUT: реальные домены и producers, SQL adapters, production wiring, read_world, Delete/settings, bulk, вариант Б, overlapping chains, checkpoint/restart. OUT не блокирует локальную приёмку.

Предлагаемые решения D1–D5 (не выдавать за принятые):

1. D1: Prepared — чистая запись с base и каноническим transition, без PatchHeader. Native wrapper создаётся только prepare_section. История сохраняет transition, не prepare request/capture целиком.
2. D2: Create/End/Reactivate обрабатывают по одной сущности на вызов; Replacement — непустые predecessor/successor tuples. 100 Create — 100 вызовов, не новый bulk API. Возможность множественных участников в Create/End/Reactivate потребовала бы другого input, это конкретный выбор, не внешний блокер.
3. D3: локальный coverage допускает несколько patches на один эффект и несколько эффектов на patch. Каждое отношение перечислено явно и связано с fingerprint prepared section. Это синтетическое предложение many-to-many, не доказанная миграция legacy.
4. D4: по умолчанию каждый эффект требует предметного patch; NoDomainMutation разрешается только отдельной декларацией synthetic policy для операции/вида, с typed evidence существующего предметного состояния. Отдельный сценарий без domain patch не выводится из пустого tuple. Можно выбрать запрет NoDomainMutation для локальной v1; ниже обе ветви определены точно.
5. D5: synthetic policy допускает Reactivate после End; после Replacement — явный отказ REACTIVATION_RULE_UNSUPPORTED. Это ограничение синтетических специализаций, не глобальный запрет Reactivate и не переоткрытие принятой семантики. Для допуска after-Replacement нужен другой объявленный policy/evidence, не bool allow.

## Общие правила моделей и reuse

Все новые records: strict=True, frozen=True, extra=forbid, revalidate_instances=always. Tuple не превращается в list. NonEmpty[X] означает tuple[X, ...] с min_length=1; Unique означает semantic validator, а не новый контейнер. Индекс — Annotated[StrictInt, ge=0]. None используется только там, где указан смысл; неизвестность имеет отдельный вариант. Не вводятся Any/dict/BaseModel payload.

Переиспользуются без копирования: EntityUid (identity/uid.py), WorldPublicationRef (worldSnapshot/identity/publication.py), RevisionHex (validation/diagnostics/runtimeIssueContext.py), PatchData/PatchHeader/PatchRef (patch/changes), SectionHeader/DomainSection, PreparedSectionDependency/PublishedSectionDependency, SectionStateRef, FormatVersion, ArtifactRef, FieldPathError, ValidatedFieldPath и ValidatorAggregationHelper. Пути далее относительно backend/app/dataModel/lifecycle, если не указано иное. Новые численные representation IDs этим документом не назначаются.

T — тип предметного kind token, не домен и не entity payload. Для локальной проверки T_A=Literal['test_entity_a'], T_B=Literal['test_entity_b']; именованные concrete subclasses всех generic records объявляются в synthetic composition module тестов. Literal здесь только тестовые wire discriminators. В production эти имена не регистрируются. Общий алгоритм не ветвится по A/B.

## Identity, состояния и capture

| Тип / модуль | Полный состав полей | Инварианты |
|---|---|---|
| LifecycleEntityRef[T], identity.py | kind:T; entity_uid:EntityUid | Typed identity; сравнение (kind, uid), scope берётся из base |
| LifecycleTransitionRef, identity.py | world_uid:EntityUid; origin_timeline_id:EntityUid; change_uid:EntityUid | Ссылка на переход, не PatchRef и не publication receipt |
| EntityLifecycle[T], entityLifecycle.py | entity:LifecycleEntityRef[T]; active:StrictBool; last_transition:LifecycleTransitionRef | Единственная модель текущего состояния; ref принадлежит миру base |
| AbsentLifecycle[T], reads/facts.py | status:Literal['absent']; entity:LifecycleEntityRef[T] | Подтверждённое отсутствие на base, не отсутствие результата |
| PresentLifecycle[T], reads/facts.py | status:Literal['present']; state:EntityLifecycle[T] | Не копирует поля проекции |
| UnknownLifecycle[T], reads/facts.py | status:Literal['unknown']; entity:LifecycleEntityRef[T]; cause:UnknownFactCause | cause ∈ NOT_CAPTURED, INCOMPLETE_HISTORY; не допускает prepare success |
| LifecycleObservation[T], reads/facts.py | alias discriminated union Absent/Present/Unknown по status | В каждом concrete subclass T замкнут |
| LastTransitionFact[T], reads/facts.py | ref:LifecycleTransitionRef; operation:LifecycleOperation; entity:LifecycleEntityRef[T] | Свидетельство вида последнего перехода; exact ref совпадает с проекцией, не вложенная история |
| LifecycleCapture[T], reads/capture.py | publication:WorldPublicationRef; entities:tuple[LifecycleObservation[T],...]; last_transitions:tuple[LastTransitionFact[T],...] | Unique entity refs; все ref принадлежат миру publication. Нужные записи перечислены явно, отсутствие элемента — INCOMPLETE_CAPTURE |

LifecycleOperation — enum CREATE/REPLACEMENT/END/REACTIVATE (operations/kind.py). Capture не обещает полную историю или защиту чтения: это готовые факты конкретной базы. Freshness проверяется Snapshot при apply, не чистым validator. В локальной v1 для Reactivate требуется last fact; остальные операции не требуют полного history scan. Absence successor запрещает повторное использование уже существующего UID; ancestry graph не создаётся из неизвестности.

## Основание и предметное подтверждение

Reason types принадлежат synthetic owning module, не новому универсальному Lifecycle payload. TestAReason: reason_id:Literal['test_a_action']; action_uid:EntityUid; operation:LifecycleOperation. TestBReason аналогично с Literal['test_b_action']. Это именованные zero-history-ref причины со ссылкой на synthetic намерение. Их каталожные декларации связывают reason_id, concrete model и owning kind; immutable composition binding, без factories/validators/callbacks. A input допускает только TestAReason, B — только TestBReason. Это конкретная association, а не union всех причин во всех видах.

Для сохранения одного generic T вводится именованный synthetic subject contract в composition: Ref[T], Reason[T], Admission[T] связываются при создании concrete request/prepared классов. В Python generic public signature T обозначает пакет этой специализации; concrete поля остаются перечисленными ниже (никакого runtime поиска типа по kind). Если используемая система generics не поддерживает associated types, техническая форма модели имеет параметры [T,R], а concrete public A/B-классы закрывают оба. Внешний DAG не получает открытые [T,R]. Выбор Python declaration сверяется владельцем PatchSet, не меняет payload.

DomainEffect[T], evidence/effects.py: entity:LifecycleEntityRef[T]; effect:Literal['create','end','reactivate']; reason_action_uid:EntityUid. Replacement разворачивается только в список ожидаемых эффектов end для predecessors/create для successors, но остаётся одной lifecycle-operation.

DomainAdmission[T], evidence/admission.py: publication:WorldPublicationRef; action_uid:EntityUid; effects:NonEmpty[DomainEffect[T]]. Это данные результата owning mock, не authority token и не trusted=True. Validator сравнивает всю relation с intent: exact participants/roles, base, action UID. Наличие POJO само по себе не доказывает внешний business validation; доверие ограничено принятой typed boundary synthetic producer. При apply обязательства проверки привязок сохраняются.

## Канонические intents и четыре requests

Intents в operations/intents.py (Replacement переиспользует lifecycleReplacement.py, поля не дублируются):

| Тип | Поля |
|---|---|
| LifecycleCreate[T] | operation:Literal[CREATE]; change_uid:EntityUid; entity:LifecycleEntityRef[T]; reason:Reason[T] |
| LifecycleReplacement[T] | operation:Literal[REPLACEMENT]; change_uid:EntityUid; predecessors:NonEmpty[LifecycleEntityRef[T]]; successors:NonEmpty[LifecycleEntityRef[T]]; reason:Reason[T] |
| LifecycleEnd[T] | operation:Literal[END]; change_uid:EntityUid; entity:LifecycleEntityRef[T]; reason:Reason[T] |
| LifecycleReactivate[T] | operation:Literal[REACTIVATE]; change_uid:EntityUid; entity:LifecycleEntityRef[T]; reason:Reason[T] |

В replacement обе стороны unique и непересекающиеся. Порядок участников значим для представления и semantic retry v1: автоматическая сортировка не выполняется. Все виды соответствуют T. reason.operation соответствует intent.operation. World/timeline не копируются в intent: scope берётся из capture.publication, где gameplay_started=true и active_timeline_id не None для этого runtime synthetic контракта. Pregame вне этой локальной формы.

Requests operations/{create,replacement,end,reactivate}.py имеют ровно три поля: intent соответствующего конкретного типа; capture:LifecycleCapture[T]; admission:DomainAdmission[T]. operation_id в этих pure requests не нужен: logical identity — intent.change_uid, публикационная identity поступает только prepare_section. Это предлагаемая коррекция раннего поля operation_id в PrepareLifecycleReplacement, не создание синонима change_uid.

Create требует absent; End — present active; Reactivate — present inactive и last fact operation END; Replacement — active predecessors и absent successors. Unknown/missing дают refusal. Все capture/admission/base relations проверяются; лишние capture entities разрешены как неизменённый контекст, лишние admission effects запрещены. Подтверждение опубликованного duplicate change_uid не имитируется в pure input: authoritative retry admission — обязанность atomic boundary ниже.

## Prepared outputs — не native patches

ParticipantTransition[T], changes/participant.py: before:AbsentLifecycle[T] | PresentLifecycle[T]; after:EntityLifecycle[T]. Unknown отсутствует в успешном результате. Entity identity before/after совпадает. after.last_transition — ref текущего intent.change_uid и scope capture.publication. before сохраняется без изменения.

LifecycleTransition[T,I], changes/transition.py: intent:I; participants:NonEmpty[ParticipantTransition[T]]. I — соответствующий concrete intent, не новый union с непроверенным kind. Create/End/Reactivate имеют одного участника; Replacement — predecessors, затем successors в исходном порядке. after.active: true для create/reactivate/successors, false для end/predecessors.

Каждый PreparedLifecycleCreate/Replacement/End/Reactivate[T] (changes/prepared*.py) имеет ровно base:WorldPublicationRef; transition:соответствующий LifecycleTransition[T,I]. Ни PatchHeader, ни operation_id, ни полного capture/admission, ни чужих payload здесь нет. Reason сохраняется единожды внутри transition.intent. Native wrapper впоследствии содержит prepared целиком; history operation — transition, publication metadata принадлежит Snapshot.

Semantic retry v1 сравнивает scope, intent (включая порядок и reason) и participants.before/after; исключает base.publication_id, publication operation_id и patch ordinal. Scope содержит мир и исходный timeline. Смена base без изменения исходного смыслового состояния не делает новое намерение, но не отменяет apply freshness. Новый change_uid — новое намерение. Политика наследования веток остаётся отдельно от локальной v1, которая проверяется на одном timeline.

## Coverage в prepare_section

PrepareLifecycleSection имеет operation_id:EntityUid; expected_world:WorldPublicationRef; changes:NonEmpty[SyntheticPreparedUnion]; domain_evidence:tuple[SyntheticCoverageUnion,...]. SyntheticPreparedUnion — ровно восемь named concrete records (4 операции × A/B). Ни один generic не остаётся открытым. Domain evidence не перезаписывает prepared reason/state.

| Тип / evidence/coverage.py | Поля |
|---|---|
| PreparedEffectBinding[T] | kind:Literal['prepared']; change_uid:EntityUid; effect:DomainEffect[T]; section:PreparedSectionDependency; patch_refs:NonEmpty[PatchRef] |
| PublishedNoMutationBinding[T] | kind:Literal['no_domain_mutation']; change_uid:EntityUid; effect:DomainEffect[T]; section:PublishedSectionDependency; observed_action_uid:EntityUid |

SyntheticCoverageUnion — A/B concrete subclasses обеих ветвей. Ключ coverage = (change_uid, typed entity ref, effect). Ровно один entry на ожидаемый эффект; extra/duplicate/missing запрещены. Patch refs в entry unique, принадлежат request.operation_id и section.section_key. Несколько effects могут ссылаться на один patch; один effect — на несколько refs. Для одного prepared section key fingerprint должен совпадать во всём наборе. Подмена actual payload при сохранённом fingerprint не выявляется чистым producer без тела: owning payload verification и Snapshot acceptance обязаны отклонить это на atomic boundary, synthetic fake моделирует такой отказ.

Матрица обязательного покрытия: Create — create каждого участника; End — end; Reactivate — reactivate; Replacement — end каждого predecessor и create каждого successor. Evidence base берётся из prepared.base/request.expected_world; published ref обязан принадлежать тому же миру, применимость published section к exact base доказывается boundary fixture. Один только ref не доказывает существование.

NoDomainMutation (D4) в рекомендуемой synthetic policy допустим только для End вида B: предметный immutable descriptor уже существует, активность хранится только Lifecycle. observed_action_uid совпадает с reason.action_uid; опубликованный descriptor witness и policy определяют отсутствие предметной записи. Для A, Create, Replacement и Reactivate ветвь отвергается NO_DOMAIN_MUTATION_NOT_ALLOWED. Это сконструированный тестовый случай, не утверждение о регионах. Если пользователь выбирает запрет, ветвь исключается из v1 union; отсутствие patch тогда всегда coverage refusal. NoMutation не означает отсутствие lifecycle state/history write.

LifecycleSectionPipelineOpenPipeline получает immutable SectionContract и policy при composition (не через DAG input). Key/version берутся из этого binding, не назначаются здесь числом. Для каждого changes[i] создаётся PatchHeader(ref=PatchRef(request.operation_id, own_key, i), format_version=bound_version, depends_on=(), artifacts=()). В этом локальном варианте coverage patch refs являются свидетельствами совместных данных, а не приказом apply ordering; section dependencies объединяются в порядке первого появления evidence. Конфликт fingerprint не разрешается дедупликацией. Published и prepared dependencies используют existing типы. Самозависимость на Lifecycle section запрещена. Чужие codecs не вызываются. Если atomic owner требует patch-level ordering, это отдельное решение D3, а не вывод из ordinal.

Native типы publication/patch.py: восемь concrete subclasses LifecycleTransitionPatch[P](PatchData) с единственным собственным полем prepared:P. P закрыт соответствующим Prepared. Никакого второго header в prepared. LifecycleSection(DomainSection[SyntheticNativePatchUnion]) сохраняет existing header и patches tuple; union ровно этих восьми типов. Concrete discrimination проверяется по nested intent.operation + entity kind (для Replacement по predecessor kind), без нового зеркала полей. Exact codec manifest и совместимость такого union проверяет PatchSet; numeric IDs здесь не назначены.

## Refusals и точные result unions

Форма/типы Python input проверяются existing model admission: неправильный concrete class → TypeError, структурно malformed объект → ValidationError до semantic helper. Node не ловит их blanket-catch и не превращает в domain success. Доменные отказы возвращаются значениями.

results/issues.py:

- LifecycleFieldIssue(FieldPathError[LifecycleFieldCode]): унаследованные code, path:ValidatedFieldPath, message:StrictStr; дополнительные поля отсутствуют. Codes: UNKNOWN_FACT, REQUIRED_FACT_MISSING, UNSUPPORTED_REASON, INVALID_STATE, REACTIVATION_RULE_UNSUPPORTED, NO_DOMAIN_MUTATION_NOT_ALLOWED.
- LifecycleRelationIssue: code:LifecycleRelationCode; path:ValidatedFieldPath; related_path:ValidatedFieldPath | None; message:StrictStr. Codes: BASE_MISMATCH, IDENTITY_MISMATCH, REASON_OPERATION_MISMATCH, ADMISSION_MISMATCH, DUPLICATE_PARTICIPANT, PARTICIPANT_OVERLAP, DUPLICATE_CHANGE_UID, COVERAGE_MISSING, COVERAGE_EXTRA, COVERAGE_DUPLICATE, PATCH_OPERATION_MISMATCH, PATCH_SECTION_MISMATCH, FINGERPRINT_CONFLICT, SELF_DEPENDENCY.
- LifecycleIssue — закрытый union двух concrete issue records. Path всегда относится к реальному полю concrete request: capture/entities, intent, admission/effects, changes или domain_evidence. Для отсутствующего элемента адресуется существующий tuple field, не вымышленный индекс. related_path — второе поле того же request, если отношение имеет обе стороны во входе; иначе None. Нет фиктивного root path для wrong Python class.

results/errors.py:

- LifecycleFieldError: kind:Literal['field_refusal']; issues:NonEmpty[LifecycleIssue], минимум один LifecycleFieldIssue.
- LifecycleLogicError: kind:Literal['logic_refusal']; issues:NonEmpty[LifecycleRelationIssue].
- LifecycleSectionRefused: kind:Literal['section_refusal']; issues:NonEmpty[LifecycleIssue].

Mixed prepare issues возвращаются LifecycleFieldError без потери relation issues; только relation — LifecycleLogicError. Section всегда возвращает один LifecycleSectionRefused, с теми же issue типами без копирования. CHANGE_PAYLOAD_CONFLICT относится к authoritative published retry, не выдумывается из отсутствующего локального ledger; его carrier в apply принадлежит atomic boundary согласованию Snapshot, не расширяет pure node union.

Exact prepare return types: соответствующий PreparedLifecycleX[A] | LifecycleFieldError | LifecycleLogicError для A, аналогично B. Section return: LifecycleSection | LifecycleSectionRefused. Это точные domain value unions для node Output.value, без новой LifecycleNodeError. Cancellation/runtime faults — existing engine transport, не эти бизнес-отказы. Snapshot SectionRefused не заполняется произвольным LifecycleLogicError: отдельный apply mapping согласуется владельцем boundary.

## Pure helpers, классы и порядок

Все application-пути внутри application/lifecycle. Public методы четырёх changes/*PipelineOpenPipeline.py: prepare_x(self, request:PrepareLifecycleX[T]) → PreparedLifecycleX[T] | LifecycleFieldError | LifecycleLogicError. Public publication/sectionPipelineOpenPipeline.py: prepare_section(self, request:PrepareLifecycleSection) → LifecycleSection | LifecycleSectionRefused. Concrete A/B input/output binding обязателен; runtime foreign dispatch отсутствует.

| Класс | Методы / результат | Ответственность и критерий нарушения |
|---|---|---|
| LifecycleTransitionValidator, validation/transitionValidator.py | validate_create/replacement/end/reactivate(request) → tuple[LifecycleIssue,...] | Проверка готовых фактов; без IO, UID allocation, изменения input. Нарушение: latest read, foreign callback или принятие unknown |
| LifecycleChangeBuilder, changes/changeBuilder.py | build_create/replacement/end/reactivate(request) → соответствующий Prepared | Вызывается только после пустого issues; строит before/after/ref. Нарушение: самостоятельное изменение семантики, публикация или второй payload |
| LifecycleSectionValidator, validation/sectionValidator.py | validate(request:PrepareLifecycleSection) → tuple[LifecycleIssue,...] | Проверяет весь набор и coverage. Нарушение: скрытый вызов prepare, сортировка входа, пропуск независимых ошибок |
| LifecycleSectionBuilder, publication/sectionBuilder.py | build(request:PrepareLifecycleSection) → LifecycleSection | Строит wrappers и headers по immutable composition binding; без IO. Нарушение: копия полей перехода, mutable accumulator, частичная секция |
| Четыре public pipeline | Методы выше | Admission → validator → refusal либо builder; DAG не получает internals |
| LifecycleSectionPipelineOpenPipeline | Метод выше | Admission → section validator → refusal либо section builder; без вызова четырёх public prepare |

Порядок prepare: structural admission → scope/base → identity/uniqueness → required capture и исходные состояния → reason/admission relations → собрать issues → build при отсутствии issues. Порядок section: structural admission → base/operation relations → duplicate change_uid/participant overlap по входным индексам → coverage в порядке transitions/participants → evidence extras по индексам → dependency conflicts → build. Независимые ошибки собираются ValidatorAggregationHelper, зависимые проверки пропускаются после нарушенного предусловия; builder при refusal не вызывается. Это внутренняя последовательность атомарных операций, не новые стадии DAG. Sort/reorder участника или перехода запрещён.

## Atomic boundary и проверки

Локальный pure успех подтверждает согласованность переданных данных, не актуальность хранилища и не авторизацию записи. Synthetic transaction participant должен проверить exact base/существование referenced data, payload fingerprint, исходные lifecycle states и published change_uid uniqueness, затем атомарно дописать transitions и обновить проекции вместе с остальным набором. Его receipt должен ссылаться на исходные PatchRefs; receipt не commit. Snapshot назначает publication refs и обеспечивает общий commit/rollback/unknown protocol. Lifecycle не вызывает самостоятельный commit и не выбирает новый operation_id при unknown. Exact allowed capability/participant signature и apply error carrier предъявляет Snapshot в своей части задания; SQL adapter не требуется.

Synthetic acceptance: восемь concrete prepare успехов; отсутствующий capture vs absent vs inactive; wrong kind/reason/action/base; дубли/пересечение; 100 Create → 100 patches и один Replacement со 100 участниками → один; A+B round-trip сохраняет типы; coverage missing/extra/duplicate/fingerprint mismatch; NoMutation только по D4; no partial section/no IO; changed reason при прежнем UID конфликтует в fake atomic acceptance; отказ CAS не публикует историю/проекцию. Фикстуры неподтверждённого evidence должны отвергаться, а не заменяться trusted=True.

## Остаток только IN

На решение пользователя: D1–D5. На сверку координатора/PatchSet: конкретная Python форма associated type specialization и nested union discrimination/manifest без новых численных IDs. На Snapshot: typed atomic participant и refusal mapping, без production adapters. Это конкретные решения внутри нового задания, не возврат OUT в gate и не утверждение реализации. После выбора D4 закрытый union содержит выбранные ветви; оба варианта нельзя молча считать принятыми одновременно.
