# Lifecycle: локальные контракты варианта А

Актуальный технический контракт construction/accepted lookup/apply: [единая редакция](entity-lifecycle-binding-apply-contract.md), exact named classes/closed manifest и carrier: [конечный mock roster](entity-lifecycle-mock-roster.md). Они заменяют прежние варианты C1–C3 ниже, включая пять independently supplied model classes, duplicate section_model, старую representation evidence, category REJECTED для Lifecycle apply evidence conflict и раздельные concrete apply carriers. Единственные concrete coverage classes — CoverageA/B; исторические EffectBindingA/B не создаются вторым набором. Единый MockSectionRefused не меняет pure LifecycleSectionRefused. D1–D7 и подтверждённые fingerprint/view решения неизменны; runtime реализация не объявляется готовой.

## Решение пользователя 2026-11-21 — D1–D7 приняты

Пользователь согласился с итоговой таблицей координатора и уточнил D6: создать собственный тестовый мир-фикстуру, явно названный mock. Приняты: D1 pure prepared без header; D2 один субъект для Create/End/Reactivate, несколько участников Replacement; D3 explicit many-to-many coverage; D4 запрет NoDomainMutation в локальной v1; D5 synthetic Reactivate после End, отказ после Replacement; D6 отдельный mock-мир с начатым состоянием и одним timeline; D7 порядок участников Replacement НЕ влияет на semantic retry equality, при сохранении порядка представления. Эти решения имеют приоритет над противоположными proposal/OPEN ниже. Приёмка остальных exact schemas/регистраций/atomic boundary остаётся отдельной сверкой.

Тестовая фикстура имеет явное имя `mock_lifecycle_world`; её описание должно содержать «mock-мир Lifecycle». Только test-support, без создания production world или запуска gameplay pipeline. Фикстура предоставляет детерминированные typed world/publication/timeline refs и необходимые проверяемые captured facts для synthetic видов A/B. Профиль начатого мира/одного timeline — свойство mock, не глобальное ограничение Lifecycle. Создание fixture-кода выполняется при разрешённой реализации через implement-plan; эта фиксация не утверждает, что fixture уже существует.

Active v1 coverage union содержит только PreparedEffectBinding для A/B. NoDomainMutation отклонён для этой версии и не сохраняется как активная схема. При domain semantic retry сравниваются участники каждой стороны Replacement без учёта перестановки; роли, основания и состояния значимы. Это не нормализация raw serialization/request fingerprint или patch ordinal.

2026-11-21. Ответ на задание №1 [координатора](gen-dag-lifecycle-node-contracts.md). Семантические решения D1–D7 приняты; exact schemas, generic bindings, registration и atomic boundary проходят техническую сверку. Код не реализован. Основной [план](entity-lifecycle.md); owning [ТЗ](../../docs/tz_entity_lifecycle.md). Общий node-план здесь не редактируется.

## Scope и решения для пользователя

IN: пять pure операций, точные локальные данные/ошибки, синтетические два вида, native wrapper, декларация atomic boundary. OUT: реальные домены и producers, SQL adapters, production wiring, read_world, Delete/settings, bulk, вариант Б, overlapping chains, checkpoint/restart. OUT не блокирует локальную приёмку.

Принятые решения D1–D7:

1. D1: Prepared — чистая запись с base и каноническим transition, без PatchHeader. Native wrapper создаётся только prepare_section. История сохраняет transition, не prepare request/capture целиком.
2. D2: Create/End/Reactivate обрабатывают по одной сущности на вызов; Replacement — непустые predecessor/successor tuples. 100 Create — 100 вызовов, не новый bulk API. Возможность множественных участников в Create/End/Reactivate потребовала бы другого input, это конкретный выбор, не внешний блокер.
3. D3: explicit many-to-many coverage принят для локального контракта: один эффект может ссылаться на несколько patches, один patch покрывать несколько явно перечисленных эффектов. Связь с fingerprint проверяется отдельно. Это не доказательство миграции legacy.
4. D4: NoDomainMutation запрещён в локальной v1 для всех видов и операций. Каждый ожидаемый эффект имеет PreparedEffectBinding с непустым patch_refs. Отсутствующее coverage возвращает COVERAGE_MISSING; неизвестная no_domain_mutation ветвь отвергается structural admission.
5. D5: synthetic policy допускает Reactivate после End; после Replacement — явный отказ REACTIVATION_RULE_UNSUPPORTED. Это ограничение синтетических специализаций, не глобальный запрет Reactivate и не переоткрытие принятой семантики. Для допуска after-Replacement нужен другой объявленный policy/evidence, не bool allow.

## Общие правила моделей и reuse

Принятые условия тестового профиля и сравнения повторов:

6. D6: отдельная test-support фикстура mock_lifecycle_world, явно описанная как «mock-мир Lifecycle», с детерминированными typed refs, начатым состоянием и одним timeline. Это свойство mock, не глобальное ограничение Lifecycle. Фикстура создаётся только при разрешённой реализации; сейчас существует её спецификация, не код.
7. D7: порядок участников каждой стороны Replacement незначим для domain semantic retry equality. Состав, роли и before/after значимы. Входной порядок представления сохраняется; порядок patches/ordinal и Publication exact request fingerprint не меняются.

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
| LifecycleCapture[T], reads/capture.py | publication:WorldPublicationRef; entities:tuple[LifecycleObservation[T],...]; last_transitions:tuple[LastTransitionFact[T],...] | Unique entity refs; все ref принадлежат миру publication. Нужные записи перечислены явно, отсутствие элемента — REQUIRED_FACT_MISSING |

LifecycleOperation — enum CREATE/REPLACEMENT/END/REACTIVATE (operations/kind.py). Capture не обещает полную историю или защиту чтения: это готовые факты конкретной базы. Freshness проверяется Snapshot при apply, не чистым validator. В локальной v1 для Reactivate требуется last fact; остальные операции не требуют полного history scan. Absence successor запрещает повторное использование уже существующего UID; ancestry graph не создаётся из неизвестности.

## Основание и предметное подтверждение

Reason types принадлежат synthetic owning module, не новому универсальному Lifecycle payload. TestAReason: reason_id:Literal['test_a_action']; action_uid:EntityUid; operation:LifecycleOperation. TestBReason аналогично с Literal['test_b_action']. Это именованные zero-history-ref причины со ссылкой на synthetic намерение. Их каталожные декларации связывают reason_id, concrete model и owning kind; immutable composition binding, без factories/validators/callbacks. A input допускает только TestAReason, B — только TestBReason. Это конкретная association, а не union всех причин во всех видах.

T во всех моделях означает только предметный вид сущности. R — независимый технический параметр конкретного типа основания. Предлагаемая Python-форма intents, requests и prepared outputs — [T,R]; refs/capture/admission/participants зависят только от T. Поле reason имеет тип R, associated type Reason[T] не вводится. Concrete A-классы закрывают [T_A,TestAReason], B-классы — [T_B,TestBReason]; неправильная пара отвергается composition admission по декларации каталога. Это не меняет смысл принятого T и не вводит второй вид сущности. DAG получает только именованные замкнутые классы; никакого runtime поиска типа по kind. Запись [T] в общей карте координатора остаётся концептуальным обозначением предметной специализации, а не утверждением точного числа технических generic-параметров; форму [T,R] нужно сверить с владельцем PatchSet.

DomainEffect[T], evidence/effects.py: entity:LifecycleEntityRef[T]; effect:Literal['create','end','reactivate']; reason_action_uid:EntityUid. Replacement разворачивается только в список ожидаемых эффектов end для predecessors/create для successors, но остаётся одной lifecycle-operation.

DomainAdmission[T], evidence/admission.py: publication:WorldPublicationRef; action_uid:EntityUid; effects:NonEmpty[DomainEffect[T]]. Это данные результата owning mock, не authority token и не trusted=True. Validator сравнивает всю relation с intent: exact participants/roles, base, action UID. Наличие POJO само по себе не доказывает внешний business validation; доверие ограничено принятой typed boundary synthetic producer. При apply обязательства проверки привязок сохраняются.

## Канонические intents и четыре requests

Intents в operations/intents.py (Replacement переиспользует lifecycleReplacement.py, поля не дублируются):

| Тип | Поля |
|---|---|
| LifecycleCreate[T,R] | operation:Literal[CREATE]; change_uid:EntityUid; entity:LifecycleEntityRef[T]; reason:R |
| LifecycleReplacement[T,R] | operation:Literal[REPLACEMENT]; change_uid:EntityUid; predecessors:NonEmpty[LifecycleEntityRef[T]]; successors:NonEmpty[LifecycleEntityRef[T]]; reason:R |
| LifecycleEnd[T,R] | operation:Literal[END]; change_uid:EntityUid; entity:LifecycleEntityRef[T]; reason:R |
| LifecycleReactivate[T,R] | operation:Literal[REACTIVATE]; change_uid:EntityUid; entity:LifecycleEntityRef[T]; reason:R |

В replacement обе стороны unique и непересекающиеся. Входной порядок сохраняется в результате, но перестановка внутри стороны не влияет на semantic retry (D7). Все виды соответствуют T; reason.operation соответствует intent.operation. Scope берётся из capture.publication. gameplay_started=true и непустой active_timeline_id — свойства mock_lifecycle_world (D6), не универсальные ограничения сущностей.

Requests operations/{create,replacement,end,reactivate}.py имеют ровно три поля: intent соответствующего конкретного типа; capture:LifecycleCapture[T]; admission:DomainAdmission[T]. operation_id в этих pure requests не нужен: logical identity — intent.change_uid, публикационная identity поступает только prepare_section. Это предлагаемая коррекция раннего поля operation_id в PrepareLifecycleReplacement, не создание синонима change_uid.

Create требует absent; End — present active; Reactivate — present inactive и last fact operation END; Replacement — active predecessors и absent successors. Unknown/missing дают refusal. Все capture/admission/base relations проверяются; лишние capture entities разрешены как неизменённый контекст, лишние admission effects запрещены. Подтверждение опубликованного duplicate change_uid не имитируется в pure input: authoritative retry admission — обязанность atomic boundary ниже.

## Prepared outputs — не native patches

ParticipantTransition[T], changes/participant.py: before:AbsentLifecycle[T] | PresentLifecycle[T]; after:EntityLifecycle[T]. Unknown отсутствует в успешном результате. Entity identity before/after совпадает. after.last_transition — ref текущего intent.change_uid и scope capture.publication. before сохраняется без изменения.

LifecycleTransition[T,I], changes/transition.py: intent:I; participants:NonEmpty[ParticipantTransition[T]]. I — соответствующий concrete intent, не новый union с непроверенным kind. Create/End/Reactivate имеют одного участника; Replacement — predecessors, затем successors в исходном порядке. after.active: true для create/reactivate/successors, false для end/predecessors.

Каждый PreparedLifecycleCreate/Replacement/End/Reactivate[T,R] (changes/prepared*.py) имеет ровно base:WorldPublicationRef; transition:соответствующий LifecycleTransition[T,I]. Ни PatchHeader, ни operation_id, ни полного capture/admission, ни чужих payload здесь нет. Reason сохраняется единожды внутри transition.intent. Native wrapper впоследствии содержит prepared целиком; history operation — transition, publication metadata принадлежит Snapshot.

Принято D7: semantic retry сравнивает scope, operation/change_uid/reason, отдельно множества predecessor и successor typed refs и соответствие typed entity ref → before/after. Сначала проверяется уникальность: дубли не скрываются преобразованием в множество. При равных отношениях перестановка внутри любой стороны эквивалентна. Смена роли, состава, основания или состояния конфликтует. Сравнение не меняет входной порядок, serialized bytes, порядок patches или ordinal. base.publication_id и publication operation_id не входят в domain equality; freshness проверяется отдельно. Publication exact immutable request binding сохраняет собственные правила: эквивалентность перехода не разрешает заменить serialized request прежней операции. Мир/исходный timeline остаются scope; fixture использует один timeline без глобального запрета веток.

## Coverage в prepare_section

PrepareLifecycleSection имеет operation_id:EntityUid; expected_world:WorldPublicationRef; changes:NonEmpty[SyntheticPreparedUnion]; domain_evidence:tuple[SyntheticCoverageUnion,...]. SyntheticPreparedUnion — ровно восемь named concrete records (4 операции × A/B). Ни один generic не остаётся открытым. Domain evidence не перезаписывает prepared reason/state.

| Тип / evidence/coverage.py | Поля |
|---|---|
| PreparedEffectBinding[T] | kind:Literal['prepared']; change_uid:EntityUid; effect:DomainEffect[T]; section:PreparedSectionDependency; patch_refs:NonEmpty[PatchRef] |

SyntheticCoverageUnion — ровно два named concrete типа PreparedEffectBinding[T_A] и PreparedEffectBinding[T_B]. Ключ coverage = (change_uid, typed entity ref, effect). Ровно один entry на ожидаемый эффект; extra/duplicate/missing запрещены. patch_refs unique и непусты; каждый ref принадлежит request.operation_id и section.section_key. Несколько effects могут ссылаться на один patch, один effect — на несколько refs. Для одного section key fingerprints совпадают. Payload verification выполняется на atomic boundary; чистый producer без чужого тела не заявляет проверку его hash.

Матрица обязательного покрытия: Create — create каждого участника; End — end; Reactivate — reactivate; Replacement — end каждого predecessor и create каждого successor. Все ветви требуют prepared предметные patches, включая End вида B. Evidence сопоставляется с prepared.base/request.expected_world; согласованность source base предметной секции проверяет atomic boundary fixture. Один ref/fingerprint не является доказательством предметной допустимости.

Отклонённый вариант NoDomainMutation не имеет active POJO, codec branch или разрешающей policy в v1. Нет специального бизнес-кода для несуществующей ветви: malformed branch — structural refusal, отсутствие required coverage — COVERAGE_MISSING.

LifecycleSectionPipelineOpenPipeline получает immutable SectionContract и policy при composition (не через DAG input). Key/version берутся из этого binding, не назначаются здесь числом. Для каждого changes[i] создаётся PatchHeader(ref=PatchRef(request.operation_id, own_key, i), format_version=bound_version, depends_on=(), artifacts=()). В этом локальном варианте coverage patch refs являются свидетельствами совместных данных, а не приказом apply ordering; section dependencies объединяются в порядке первого появления evidence. Конфликт fingerprint не разрешается дедупликацией. Active coverage формирует prepared dependencies существующего типа; PublishedSectionDependency не используется как обход обязательного предметного patch. Самозависимость на Lifecycle section запрещена. Чужие codecs не вызываются. Если atomic owner требует patch-level ordering, это отдельное решение D3, а не вывод из ordinal.

Native wrapper и восемь test-only children используют exact construction map из C1 ниже. Wrapper выбирается по type(prepared) через immutable binding, canonical decode — по RECORD ID. Вложенные intent.operation/kind только проверяют coherence; не выбирают wrapper или публичную операцию. Header единственный, унаследован от PatchData; prepared не копируется. LifecycleSectionAB содержит plain closed union восьми named patches. Construction API и roster приведены в C1, numeric IDs не назначаются этим документом.

## Refusals и точные result unions

Единый код отсутствующего обязательного факта — REQUIRED_FACT_MISSING; отдельный синоним для неполного capture не вводится. Наличие UnknownLifecycle даёт UNKNOWN_FACT, подтверждённый AbsentLifecycle сам по себе ошибкой не является. Для missing last-transition fact и missing entity observation используется REQUIRED_FACT_MISSING с путём соответствующего поля capture.

Форма/типы Python input проверяются existing model admission: неправильный concrete class → TypeError, структурно malformed объект → ValidationError до semantic helper. Node не ловит их blanket-catch и не превращает в domain success. Доменные отказы возвращаются значениями.

results/issues.py:

- LifecycleFieldIssue(FieldPathError[LifecycleFieldCode]): унаследованные code, path:ValidatedFieldPath, message:StrictStr; дополнительные поля отсутствуют. Codes: UNKNOWN_FACT, REQUIRED_FACT_MISSING, UNSUPPORTED_REASON, INVALID_STATE, REACTIVATION_RULE_UNSUPPORTED.
- LifecycleRelationIssue: code:LifecycleRelationCode; path:ValidatedFieldPath; related_path:ValidatedFieldPath | None; message:StrictStr. Codes: BASE_MISMATCH, IDENTITY_MISMATCH, REASON_OPERATION_MISMATCH, ADMISSION_MISMATCH, DUPLICATE_PARTICIPANT, PARTICIPANT_OVERLAP, DUPLICATE_CHANGE_UID, COVERAGE_MISSING, COVERAGE_EXTRA, COVERAGE_DUPLICATE, PATCH_OPERATION_MISMATCH, PATCH_SECTION_MISMATCH, FINGERPRINT_CONFLICT, SELF_DEPENDENCY.
- LifecycleIssue — закрытый union двух concrete issue records. Path всегда относится к реальному полю concrete request: capture/entities, intent, admission/effects, changes или domain_evidence. Для отсутствующего элемента адресуется существующий tuple field, не вымышленный индекс. related_path — второе поле того же request, если отношение имеет обе стороны во входе; иначе None. Нет фиктивного root path для wrong Python class.

results/errors.py:

- LifecycleFieldError: kind:Literal['field_refusal']; issues:NonEmpty[LifecycleIssue], минимум один LifecycleFieldIssue.
- LifecycleLogicError: kind:Literal['logic_refusal']; issues:NonEmpty[LifecycleRelationIssue].
- LifecycleSectionRefused: kind:Literal['section_refusal']; issues:NonEmpty[LifecycleIssue].

Mixed prepare issues возвращаются LifecycleFieldError без потери relation issues; только relation — LifecycleLogicError. Section всегда возвращает один LifecycleSectionRefused, с теми же issue типами без копирования. CHANGE_PAYLOAD_CONFLICT относится к authoritative published retry, не выдумывается из отсутствующего локального ledger; его carrier в apply принадлежит atomic boundary согласованию Snapshot, не расширяет pure node union.

Exact prepare return types: соответствующий PreparedLifecycleX[T_A,TestAReason] | LifecycleFieldError | LifecycleLogicError для A, аналогично B. Section return: LifecycleSection | LifecycleSectionRefused. Это точные domain value unions для node Output.value, без новой LifecycleNodeError. Cancellation/runtime faults — existing engine transport, не эти бизнес-отказы. Snapshot SectionRefused не заполняется произвольным LifecycleLogicError: отдельный apply mapping согласуется владельцем boundary.

## Pure helpers, классы и порядок

Все application-пути внутри application/lifecycle. Public методы четырёх changes/*PipelineOpenPipeline.py: prepare_x(self, request:PrepareLifecycleX[T,R]) → PreparedLifecycleX[T,R] | LifecycleFieldError | LifecycleLogicError. Public publication/sectionPipelineOpenPipeline.py: prepare_section(self, request:PrepareLifecycleSection) → LifecycleSection | LifecycleSectionRefused. Concrete A/B input/output binding обязателен; runtime foreign dispatch отсутствует.

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

Publication — инфраструктурная часть ядра Snapshot, не самостоятельный предметный домен. Она обслуживает operation binding, транзакционную фиксацию, terminal persistence/replay; lifecycle сущностей и его предметные проверки ей не передаются. Связь Snapshot с внутренним Publication store не является вызовом чужого предметного pipeline. Это классификация границы, а не разрешение произвольных вложенных вызовов: exact capability и обязанности synthetic participant по-прежнему сверяются со Snapshot. Источник принятого положения — interdomain-contract-register.md, решение пользователя 2026-11-21.

Локальный pure успех подтверждает согласованность переданных данных, не актуальность хранилища и не авторизацию записи. Atomic participant использует отдельный accepted-change lookup (C2): равный Found — no-op, неравный — apply conflict; только Absent проходит проверки текущего before-state перед append. Generic LifecycleCapture не обещает history completeness. LifecycleApplyIssue/SectionRefused, append result и no-op receipt заданы в C3. Snapshot назначает refs и обеспечивает общий commit/rollback/unknown. Receipt не commit; Lifecycle не выбирает новый operation_id при unknown. SQL adapter не требуется.

Synthetic acceptance на mock_lifecycle_world: восемь prepare успехов; missing/unknown/absent/inactive различаются; wrong kind/reason/action/base; duplicate/overlap; 100 Create → 100 patches, один Replacement со 100 участниками → один; mixed A/B round-trip; coverage missing/extra/duplicate/fingerprint mismatch; NoDomainMutation structural rejection и End B без patch → COVERAGE_MISSING; Reactivate после End успешен, после Replacement — REACTIVATION_RULE_UNSUPPORTED. Перестановка каждой стороны Replacement даёт ту же domain equality, сохраняя входной порядок результата; смена роли/основания/before/after конфликтует. Отдельный тест подтверждает, что domain equality не обходит Publication exact request binding. Fake CAS refusal не публикует историю/проекцию; нет partial section/IO/trusted=True. Это спецификация будущих тестов, не выполненное evidence.

## Остаток только IN

### Техническая сверка трёх стыков — owning ответ, 2026-11-21

Следующие exact signatures — техническое предложение владельца для сверки координатором/PatchSet/Snapshot, не новые решения D1–D7. Они заменяют прежние описания nested-dispatch и применение pure refusal на commit boundary. Реальные SQL/producers, новые сценарии и production IDs не требуются.

#### C1. Named construction и точная discrimination

Все synthetic declarations находятся только в backend/tests/lifecycle/support/mixedContracts.py. T_A/T_B из этого документа именуются TestEntityA/TestEntityB как aliases Literal token; это не новые production entities. Owning generic bases находятся в dataModel/lifecycle. Публичный runtime pipeline всегда привязан к named request/result classes при composition.

Roster (8 строк — исчерпывающий synthetic construction map):

| Operation | Named request | Named intent/transition | Named prepared | Native patch |
|---|---|---|---|---|
| Create A | CreateRequestA | CreateIntentA / CreateTransitionA | CreateA | CreatePatchA |
| Create B | CreateRequestB | CreateIntentB / CreateTransitionB | CreateB | CreatePatchB |
| Replacement A | ReplaceRequestA | ReplaceIntentA / ReplaceTransitionA | ReplaceA | ReplacePatchA |
| Replacement B | ReplaceRequestB | ReplaceIntentB / ReplaceTransitionB | ReplaceB | ReplacePatchB |
| End A | EndRequestA | EndIntentA / EndTransitionA | EndA | EndPatchA |
| End B | EndRequestB | EndIntentB / EndTransitionB | EndB | EndPatchB |
| Reactivate A | ReactivateRequestA | ReactivateIntentA / ReactivateTransitionA | ReactivateA | ReactivatePatchA |
| Reactivate B | ReactivateRequestB | ReactivateIntentB / ReactivateTransitionB | ReactivateB | ReactivatePatchB |

Каждый intent/request/prepared — named child соответствующей owning модели [TestEntityA,TestAReason] либо [TestEntityB,TestBReason]. Request.intent явно сужен до named intent; prepared.transition — до named transition. CaptureA/B и AdmissionA/B — named children owning capture/admission, request.capture/admission используют именно их. ParticipantA/B и EntityStateA/B — named children ParticipantTransition/EntityLifecycle, transition.participants и participant.after используют их. Нужные RefA/B, AbsentA/B, PresentA/B, UnknownA/B и LastFactA/B также named и включаются в manifest closure; declaration одного generic origin не заменяет эти классы. Field specialization не создаёт второе значение поля и не меняет его смысл.

type PreparedAB = CreateA | CreateB | ReplaceA | ReplaceB | EndA | EndB | ReactivateA | ReactivateB. type PatchAB — соответствующие восемь Patch children, как в предложении PatchSet. PrepareLifecycleSectionAB — named child owning section request с changes:NonEmpty[PreparedAB] и domain_evidence:tuple[EffectBindingA | EffectBindingB,...]. LifecycleSectionAB — DomainSection[PatchAB]. Остальные input поля operation_id/expected_world не переобъявляются. Каждый Patch child наследует LifecycleTransitionPatch[соответствующий Prepared] и единственный PatchData.header.

Construction binding — frozen application records, не dataModel request, не callable через DAG. Proposed module application/lifecycle/composition/modelBindings.py:

```python
class LifecycleCreateModels[Q, P, Tr, Pt, St]:
    request_model: type[Q]
    prepared_model: type[P]
    transition_model: type[Tr]
    participant_model: type[Pt]
    state_model: type[St]
# LifecycleReplacementModels / LifecycleEndModels / LifecycleReactivateModels:
# те же пять полей, admission проверяет именно свой operation generic origin.

class LifecycleCreatePipelineOpenPipeline[Q, P]:
    def __init__(self, *, models: LifecycleCreateModels,
                 validator: LifecycleTransitionValidator,
                 builder: LifecycleChangeBuilder) -> None: ...
    def prepare_create(self, request: Q) -> P | LifecycleFieldError | LifecycleLogicError: ...
```

Q/P/Tr/Pt/St — технические переменные типов model classes, не payload BaseModel/Any. Каждый bound экземпляр использует конкретные аргументы из roster; runtime принимает только type(request) is models.request_model. Для остальных трёх pipeline сигнатуры аналогичны с собственными Models и prepare_replacement/end/reactivate. Их construction не выбирает операцию по payload. Builder получает models при своём construction; pipeline проверяет identity его binding относительно собственного, а не допускает рассогласованные builder/model sets.

Exact construction примера: LifecycleCreateModels[CreateRequestA,CreateA,CreateTransitionA,ParticipantA,EntityStateA](request_model=CreateRequestA, prepared_model=CreateA, transition_model=CreateTransitionA, participant_model=ParticipantA, state_model=EntityStateA). После проверки builder строит state через state_model(entity=...,active=...,last_transition=...), participant через participant_model(before=...,after=...), transition через transition_model(intent=request.intent,participants=...), result через prepared_model(base=request.capture.publication,transition=...). Возвращается type(result) is CreateA, не PreparedLifecycleCreate[TestEntityA,TestAReason]. Никакого создания bare generic с последующим coercion в A/B. Intent и validated before refs переиспользуются, не пересоздаются по строковому kind.

Все Models admission проверяют: named concrete origin/закрытые args, strict/frozen/extra-forbid/revalidate; согласованность T/R всех полей; operation literal; request.intent class и transition.intent class identity; transition.participants и participant.after annotation identity; prepared.transition exact class. Полный roster immutable, ошибки configuration fail-fast до runtime. Класс не из roster и subclass от разрешённого named child отвергаются, fallback по issubclass нет.

Для секции: LifecyclePatchModelBinding[P,N] frozen record с prepared_model:type[P], patch_model:type[N]. Immutable tuple восьми bindings строит read-only exact-type map; patch_model.prepared должен иметь annotation is prepared_model. LifecycleSectionModels[Q,S] содержит request_model:type[Q], section_model:type[S], bindings:tuple[LifecyclePatchModelBinding,...], contract:SectionContract[S]. Здесь гетерогенность bindings описывается закрытым construction roster, не открытым runtime payload. Constructor проверяет равенство множеств request.changes union / keys map и section.patches union / values map, отсутствие повторов и exact contract.section_model. LifecycleSectionPipelineOpenPipeline[PrepareLifecycleSectionAB,LifecycleSectionAB].prepare_section(request) → LifecycleSectionAB | LifecycleSectionRefused.

Builder: для каждого prepared выбирает patch_model = exact_map[type(prepared)], создаёт patch_model(header=constructed_header, prepared=prepared); затем section_model(header=constructed_section_header,patches=tuple(...)). Все named classes вызываются как обычные model constructors; arbitrary factories/callbacks не принимаются. Numeric canonical RECORD IDs назначаются отдельной manifest-сверкой test-support. Codec выбирает concrete class по RECORD ID, не по nested полям. kind/operation служат только coherence проверками после typed construction/decode. Неразмеченный dict и smart-union coercion не являются public construction API.

#### C2. Lookup принятых переходов отдельно от capture

LifecycleCapture[T] остаётся только current entities/last_transitions. Никакой history lookup/completeness в этот POJO не добавляется. Предлагается собственный минимальный storage read-контракт в dataModel/lifecycle/storage/acceptedChanges.py (generic owning types, закрытые AB children только tests):

| Модель | Exact поля |
|---|---|
| AcceptedChangesQuery | publication:WorldPublicationRef; refs:NonEmpty[LifecycleTransitionRef] |
| AcceptedChangeAbsent | kind:Literal['absent']; ref:LifecycleTransitionRef |
| AcceptedChangeFound[C] | kind:Literal['found']; ref:LifecycleTransitionRef; transition:C |
| AcceptedChangesResult[E] | publication:WorldPublicationRef; entries:tuple[E,...] |

C — closed union восьми named Transition classes из C1, не Prepared/native wrapper и не полный capture. Found ref совпадает с change UID/scope transition. AcceptedChangesResultAB допускает только named Absent и FoundAB; полный ответ имеет ровно одну запись на каждый queried ref, в порядке query, без extra/duplicate/missing; publication равна query.publication. Query refs unique. Это completeness конкретного набора ключей, не обещание полной истории. Confirmed absence — отдельный record. Нет record/None/частичный ответ не трактуется как absence.

application/lifecycle/storage/participantPort.py:

```python
class ILifecycleAcceptedChangesReader[Result]:
    async def lookup_accepted_changes(
        self, request: AcceptedChangesQuery, *, scope: CommitReadScope,
    ) -> Result: ...
```

Result в mock binding — AcceptedChangesResultAB. Reader читает собственный accepted view exact publication в borrowed scope; никогда current/latest. Он не получает writer другого домена. Incomplete/unavailable/corrupt view — infrastructure exception, не бизнес-отказ и не AcceptedChangeAbsent. Handler проверяет полноту/соответствие ключей результата до semantic checks; нарушение — contract fault с сохранением причины через existing Snapshot infrastructure transport. Новый diagnostics carrier для unknown storage не создаётся.

Соседний current read_for_section возвращает tuple[CaptureA | CaptureB,...], один capture на представленный в section вид, каждый с exact publication и полным набором требуемых текущих entity observations. Это отдельный result от accepted-change lookup; оба результата читаются в одной borrowed transaction. Synthetic participant может реализовать оба узких собственных reader-протокола. Snapshot не должен аннотировать ни один из них голым LifecycleCapture как полноценную history view.

Порядок проверки: получить accepted lookup для всех change refs; Found → сравнить semantic transition по D7; равный → no-op по этому переходу, НЕ требовать совпадения его исторического before с уже изменённой current projection; различный → CHANGE_PAYLOAD_CONFLICT. Absent → проверять current capture/before и evidence до append. Новый transition той же сущности не блокируется историческим повтором другого change_uid сверх принятых batch invariants. Lookup не заменяет Snapshot expected-context/CAS и не объявляет успех всей новой публикации.

#### C3. Apply diagnostics и append/no-op result

Pure LifecycleSectionRefused остаётся только prepare_section refusal с paths её request. В apply он не используется и не расширяется кодом CHANGE_PAYLOAD_CONFLICT.

Новая owning специализация existing error base в dataModel/lifecycle/results/applyIssue.py:

```python
class LifecycleApplyCode(StrEnum):
    CHANGE_PAYLOAD_CONFLICT = 'lifecycle.change_payload_conflict'
    BEFORE_STATE_MISMATCH = 'lifecycle.before_state_mismatch'
    EVIDENCE_MISMATCH = 'lifecycle.evidence_mismatch'

class LifecycleApplyIssue(FieldPathError[LifecycleApplyCode]):
    pass  # только унаследованные code/path/message, без второй схемы ошибок
```

Exact paths строятся existing CheckedPath/FieldRef относительно concrete native LifecycleSectionAB, а не PrepareLifecycleSectionAB:

- CHANGE_PAYLOAD_CONFLICT: patches[i].prepared.transition.intent.change_uid. Причина относится к предъявленному UID, уже занятому другим принятым переходом; путь к stored history не выдумывается.
- BEFORE_STATE_MISMATCH: patches[i].prepared.transition.participants[j].before. Свидетельство не соответствует accepted состоянию exact base.
- EVIDENCE_MISMATCH: header.depends_on[k] для несовместимой проверки prepared section binding; если нарушена semantic relation конкретного участника — patches[i].prepared.transition.participants[j].before либо .after по реально нарушенному operand. Нет пути domain_evidence: этого поля у native section нет. Проверка, которую нельзя адресовать существующему operand, не маскируется этим кодом; malformed shape/неполный source view — contract/infrastructure fault.

Carrier — existing SectionRefused(category=CONFLICT, diagnostics=tuple[LifecycleApplyIssue,...]) для конфликтов принятых UID/исходного состояния; EVIDENCE_MISMATCH → category=REJECTED. При mixed diagnostics category CONFLICT если есть хотя бы один conflict code, иначе REJECTED. Порядок диагностики — patch index/participant index; validation собирает независимые ошибки, не вызывает append при отказе. LifecycleApplyIssue — concrete FieldPathError, поэтому совместим с actual nongeneric SectionRefused; в H2 закрывается existing SectionRefused[LifecycleApplyIssue]. Новый LifecycleApplyRefused или копия pure carrier не вводятся. SectionValidation = existing SectionAccepted | SectionRefused; H2 specialization задаётся composition.

Numeric IDs в этом документе не назначаются. Synthetic manifest обязан включать LifecycleApplyCode/Issue и closure реальных paths/model identities; D roster terminal transport содержит эту concrete issue. Нельзя добавлять её молча в production TimeSnapshotApplyResult/root20150. Test-only result specialization/manifest проверяется H2 composition без нового формата transport, legacy support и без изменения принятых Time IDs. Неизвестный diagnostic class отвергается existing admission, не превращается в строку.

dataModel/lifecycle/publication/appendResult.py::LifecycleAppended — ровно proposed Snapshot record: state:SectionStateRetention | None; history:SectionHistoryRetention | None; changed:tuple[PatchRef,...]. Это postcondition операции записи, не committed result. LifecycleAppendResult = LifecycleAppended | SectionRefused (в H2 с LifecycleApplyIssue); чистый LifecycleSectionRefused сюда не входит.

В полностью повторном batch: LifecycleAppended(state=None,history=None,changed=()). Handler возвращает SectionApplyReceipt(section_key=section.header.key,states=(),history=(),changed=()). Snapshot наследует pinned state по своим C2 правилам. Никакого new state на assigned target и inherited history receipt не создаётся. В смешанном batch changed содержит только входные PatchRefs новых переходов в исходном порядке; state/history относятся к assigned target, history содержит только новые transitions, state сохраняет остальные сущности. Для row-like mock artifacts=(). Неравный повтор — refusal до writes. Writer повторяет lookup/precondition проверку в том же scope перед записью, без независимого commit.

SectionHandler.validate → SectionAccepted | SectionRefused; apply → SectionApplyReceipt | SectionRefused. Writer append(section:L, expected:WorldPublicationRef, target:WorldSnapshotRef) → LifecycleAppendResult в уже bound CommitScope. Handler переводит state/history None в пустые tuples, иначе singleton, changed переносит неизменно. Receipt не завершает публикацию: другие секции, C2/CAS и confirmed commit обязательны; all-no-op Lifecycle не означает no-op всего PatchSet. Unknown outcome остаётся инфраструктуре Snapshot/Publication.

#### Проверяемый результат технической сверки

1. Восемь bindings возвращают exact named prepared child; bare generic, subclass impostor и wrong A/B отклоняются. Map нельзя изменить после construction, generic алгоритм не ветвится по TestEntityA/B.
2. Все восемь wrappers round-trip по RECORD ID с exact types; nested coherence не выполняет dispatch.
3. Accepted lookup возвращает found/confirmed absent ровно для requested refs; missing/extra/duplicate/base mismatch — contract fault. Capture не обещает историю.
4. Same semantic transition с переставленными сторонами участников → no-op без before-state false conflict; изменённый reason/before/after → SectionRefused(CONFLICT) с реальным change_uid path. Publication exact fingerprint не нормализуется.
5. No-op receipt проходит actual C2 inheritance правила без нового state/history; mixed batch пишет только новые history operations. Любой refusal/CAS failure не оставляет частичных writes.

Это документальный ответ, не запущенные тесты. Новые owning типы не дублируют identity/base/errors: reused refs и FieldPathError, отдельная completeness семантика accepted lookup, existing SectionRefused/receipt. Техническая совместимость construction и synthetic manifest проверяется PatchSet, atomic participant — Snapshot, final node registration — координатором. OUT и D1–D7 не переоткрываются.

D1–D7 закрыты пользовательским решением. Owning ответы на оставшиеся construction/lookup/apply стыки приведены в C1–C3 ниже. На сверке остаются совместимость named construction/manifest с PatchSet, typed participant mapping со Snapshot и final registration координатором. Active coverage имеет только две prepared ветви; NoMutation и order-sensitive domain equality исключены. OUT не gate, код и fixture ещё не созданы.
