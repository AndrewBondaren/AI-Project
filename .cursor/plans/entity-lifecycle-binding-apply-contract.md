# Lifecycle: единый owning контракт construction / lookup / apply

2026-11-21. Ответ на повторную сверку трёх IN-стыков координатором. Заменяет технические варианты C1–C3 в entity-lifecycle-local-contracts.md. D1–D7 приняты и не пересматриваются. Документальное техническое предложение для общего freeze; утверждение согласия всех владельцев не делается. Код/SQL/реальные producers/production wiring OUT. Общий node-план не редактируется.

## 1. Один construction binding

Принимаю рекомендацию PatchSet как owning технический вариант: application/lifecycle/contracts/preparationBinding.py, frozen LifecyclePreparationBinding[Q,P] содержит только request_model:type[Q], prepared_model:type[P]. Это application configuration, не request POJO. Runtime Q/P — exact named closed models из roster 4 операций × A/B; generic BaseModel bounds не разрешают открытые runtime модели.

```python
class LifecycleCreatePipelineOpenPipeline[Q, P]:
    def __init__(self, *, binding: LifecyclePreparationBinding[Q,P],
                 policy: LifecyclePreparationPolicy) -> None: ...
    def prepare_create(self, request: Q) -> P | LifecycleFieldError | LifecycleLogicError: ...
```

Для Replacement/End/Reactivate — собственный метод prepare_replacement/end/reactivate и тот же двухполевой binding. LifecyclePreparationPolicy — уже описанная immutable owning policy/catalog, не внешний validator callback. Validator/builder — собственная внутренняя реализация, не независимо поставляемые несовместимые model factories.

При construction один раз через public model_fields извлекается цепочка prepared.transition → transition.participants element → participant.after, а из request — intent/capture/admission. Проверяются named concrete классы, закрытые T/R, strict/frozen/extra-forbid/revalidate, соответствие operation, exact identity request.intent и transition.intent, typed refs и before/after. Производные классы хранятся как private immutable construction result. Пяти независимо передаваемых model fields больше нет. Нет reflection по данным запроса или повторного parsing A→B при runtime.

Roster test-support неизменен: CreateRequestA/B → CreateA/B; ReplaceRequestA/B → ReplaceA/B; EndRequestA/B → EndA/B; ReactivateRequestA/B → ReactivateA/B. Concrete named intent/transition/participant/state/ref/capture/reason children находятся в backend/tests/lifecycle/support/mixedContracts.py. Q/P из разных T/R или wrong operation дают construction error. type(request) is binding.request_model обязательно; результат строится непосредственно binding.prepared_model(base=...,transition=named_transition(...)). Проверяется type(result) is prepared_model. Bare generic/subclass impostor не допускается.

Section binding, application/lifecycle/contracts/sectionBinding.py:

```python
class LifecycleSectionBinding[Q,S]:
    request_model: type[Q]
    section_contract: SectionContract[S]
    patch_bindings: tuple[LifecyclePatchModelBinding, ...]

class LifecyclePatchModelBinding[P,N]:
    prepared_model: type[P]
    patch_model: type[N]
```

Отдельного section_model нет: используется section_contract.section_model. Closed map type(prepared)→patch_model создаётся один раз из tuple, read-only. Keys ровно совпадают с request.changes union, values — section_contract.section_model.patches union; patch.prepared annotation exact identity. Native evidence annotation проверяется согласно §2. Никаких дублирующих keys, fallback/issubclass dispatch или произвольных callbacks. Public prepare_section(Q) → S | LifecycleSectionRefused. Wrapper выбирается exact class, codec выбирает RECORD ID. Nested kind/operation только coherence.

## 2. Обнаруженная потеря evidence и минимальная native-дельта

### Решение пользователя о владельце доказательств

2026-11-21, передано координатором по поручению «Отправь обоим владельцам ответ»: Lifecycle определяет свои predicates, необходимые operands, их типы/источники и достаточность. Предметный смысл подтверждений принадлежит synthetic предметным владельцам. Snapshot не достраивает evidence, не вычисляет domain relations и не вызывает чужой pipeline ради недостающих фактов. Он сохраняет общий scope/lifetime, expected publication, assigned refs, admitted dependency boundaries, C2/CAS/commit/rollback/unknown. Распределение ответственности принято; новый capability, DTO или native-дельта автоматически не принимаются.

### Полная карта operands apply

Обозначения источников: N — входная concrete LifecycleSectionAB; C — existing SnapshotValidationContext; Q — AcceptedChangesQuery(N.base, refs из transitions), результат AcceptedChangesResultAB через собственный ILifecycleAcceptedChangesReader.lookup_accepted_changes(Q, scope=C.read_scope); V — tuple[CaptureA | CaptureB,...] из собственного read_for_section(N,publication=C.expected_world,scope=C.read_scope); P — предлагаемый immutable prepared_domain_sections из LifecycleMockValidationContext (§ ниже). P ещё требует подтверждения capability и не выводится из самого наличия resolved_dependencies.

| Apply predicate | Обязательные typed operands | Producer / точный источник | Проверка Lifecycle | Конкретный refusal / fault |
|---|---|---|---|---|
| Допустимая native форма | Exact named patch/prepared/evidence models, versions | Owning constructors/codec → N | Type/operation/kind coherence, принятый native schema | Malformed native — existing structural/contract fault, не domain success |
| Общая база | patch.prepared.base:WorldPublicationRef; C.expected_world | Pure prepare сохраняет base → N; Snapshot предоставляет expectation | Равенство supplied base всех patches и ожидания; фактическую актуальность heads проверяет Snapshot | Расхождение контекста unchecked input — contract fault; actual stale publication — общий Snapshot conflict |
| Publication identity | N.patches[i].header.ref.operation_id; C.operation_id | prepare_section header; admitted Snapshot operation | Равенство, section membership и unique ordinals | Общий native/context admission fault; не новый Lifecycle UID conflict |
| Уникальность и независимость batch | intent.change_uid; typed refs и роли всех transitions | N.prepared.transition | Повторное использование того же pure invariant, без второй реализации | Malformed/direct batch — contract fault; pure producer ранее выдаёт соответствующий pure refusal |
| Историческое наличие change_uid | Requested LifecycleTransitionRef; Found/Absent и canonical transition | Q → exact own lookup, не last_transitions | Ровно один ответ на ключ, exact publication; Found сравнивается по D7 | Неполный/неверный lookup — infrastructure fault; different Found → CHANGE_PAYLOAD_CONFLICT/CONFLICT на intent.change_uid |
| Исходное состояние нового перехода | N.participants[j].before; V entity observation | Pure builder сохраняет before; own reader V читает exact accepted Q | Только для Absent в lookup: before равно принятому состоянию; unknown нельзя считать absence | Complete known mismatch → BEFORE_STATE_MISMATCH/CONFLICT на before; incomplete view → infrastructure fault |
| Reactivate policy | Inactive before; LastTransitionFact.ref/operation; intent.operation | N + V.last_transitions собственного reader | Synthetic правило D5: прежняя ссылка соответствует факту End. После Replacement prepare запрещён | Изменение accepted last transition → BEFORE_STATE_MISMATCH; неизвестный факт → infrastructure fault; malformed prepared bypass D5 → contract fault |
| Полнота coverage | Typed participants/roles/action UID; N.patches[i].evidence[*].effect/change_uid | DomainAdmission/mock producer → request.domain_evidence → native evidence | Ровно один binding на ожидаемый эффект; роли/create/end/reactivate совпадают; D4 запрещает отсутствие patches | Несостоятельная native схема/внутренние relations → contract fault; противоречие complete P → EVIDENCE_MISMATCH/CONFLICT |
| Наличие предметного patch | evidence[j].patch_refs[k]:PatchRef; P sections/patch headers | Synthetic owning producer создаёт предметную native секцию; P предоставляет эту же admitted секцию | Exact ref находится в указанной section, base и operation соответствуют; absent ref в полном P — доказанное противоречие | EVIDENCE_MISMATCH/CONFLICT на evidence[j].patch_refs[k]; отсутствующий promised P — infrastructure fault |
| Соответствие effect предметным данным | evidence[j].effect:DomainEffect[T]; matching P.patch.effects:NonEmpty[DomainEffect[T]]; P.patch.base | Готовые публичные effects сформированы synthetic предметным владельцем и сохранены в его native patch | Сопоставить typed entity/action/role и base; не вычислять предметное решение заново | EVIDENCE_MISMATCH/CONFLICT на effect либо section; отсутствие typed эффекта в complete P — конфликт |
| Связь с проверенным содержимым | evidence[j].section:PreparedSectionDependency; N.header.depends_on; C.resolved_dependencies; exact P section | Owning preparation даёт fingerprint; общая admitted representation граница подтверждает соответствие фактическому объекту | Exact key/fingerprint отношения; никакой проверки hash по одному заявлению RevisionHex | Proven mismatch → EVIDENCE_MISMATCH на evidence.section; отсутствие объявленного подтверждения границы — infrastructure fault, не trusted=True |
| Повторный переход и предметные эффекты | Found+equal Q; прежние N.evidence и complete P | Own lookup и те же подготовленные предметные секции | Lifecycle no-op не пропускает coverage. Synthetic предметный participant отдельно проверяет свой effect retry | Его отказ идёт его carrier; Lifecycle его не вызывает и не переименовывает; общий commit не проходит |
| Append/postcondition | Validated new transitions, assigned target, bound scope | Own writer получает N, expected, target | Записать только новые lifecycle transitions/projections, сохранить остальные; own writer повторно проверяет accepted facts | Semantic conflict — SectionRefused; corrupted scope/output — infrastructure fault |
| Receipt | LifecycleAppended.state/history/changed; N PatchRefs; assigned target | Собственный writer → handler → existing receipt | Перенос значений без переназначения refs; all-no-op даёт пустые tuples | Receipt shape — contract fault; provenance/CAS и durability проверяет Snapshot |

Порядок: native/context admission → accepted lookup → Found semantic comparison → current-state/policy только для Absent → coverage каждого перехода, включая Found+equal → append в общем scope → receipt. Независимые conflicts агрегируются; отсутствие необходимого source не подменяется бизнес-конфликтом. Все пути diagnostics относятся к native N. Snapshot не получает обязанность придумывать Q/V/P contents: первые два — собственные Lifecycle reads, P — точный read-only доступ к уже сформированным public данным, предложенный ниже.

Прежний wrapper(header,prepared) терял связи change→entity/effect→domain patch. SectionHeader.depends_on сохраняет section key/fingerprint, но НЕ участника, роль и конкретные patch refs. Поэтому обещание apply-проверки coverage при таком payload было неверно. Snapshot evidence_index не имел реального operand.

**Явная предлагаемая дельта для сверки**, не молчаливое изменение:

```python
class LifecycleTransitionPatch[P,E](PatchData):
    prepared: P
    evidence: tuple[E,...]  # nonempty, existing PreparedEffectBinding[T]
```

CreatePatchA/ReplacePatchA/EndPatchA/ReactivatePatchA замыкают E=EffectBindingA; B — EffectBindingB. Prepared records не меняются. Собственного второго evidence DTO нет, existing PreparedEffectBinding переиспользуется. Единственный native владелец evidence — patch.evidence, секция не хранит вторую копию. Request остаётся с domain_evidence: builder группирует его по change_uid, сохраняет входной порядок entries и переносит каждый entry ровно в один patch. Duplicate/missing/extra coverage отвергаются до построения. Field change_uid внутри existing evidence обязан совпасть с prepared.transition.intent.change_uid; это связь между существующими POJO, не новый logical UID.

Точная цепочка: request.domain_evidence[k] → patches[i].evidence[j] (i по change_uid; j по исходному порядку этой группы). Оттуда effect сопоставляется с transition participants и ролями; patch_refs — с конкретными предметными patches; section — с header dependencies и resolved dependencies. Header.depends_on содержит unique section dependencies в порядке первого появления native evidence по patches; порядок самого domain_evidence не задаёт порядок transitions. Никаких неиспользуемых dependencies. PatchHeader.depends_on остаётся пустым в текущем варианте: coverage refs не превращаются автоматически в apply-order edges. Snapshot общий assembler сам по себе не доказывает membership отдельных coverage patch refs.

### Что ещё необходимо передать apply

Actual SnapshotValidationContext содержит operation_id, expected_world/players, resolved_dependencies, read_scope. Только resolved_dependencies НЕДОСТАТОЧНО, чтобы доказать наличие patch ordinal и соответствие entity/effect фактическому чужому payload. Native evidence сохраняет заявление, но не делает его истинным. Это оставшаяся точная technical difference, не запрос production storage.

Предлагаемый локальный вариант без foreign calls: test-only LifecycleMockValidationContext наследует existing SnapshotValidationContext и добавляет prepared_domain_sections:tuple[TestDomainSectionA | TestDomainSectionB,...]. Это immutable ссылки на ТЕ ЖЕ concrete sections проверяемого PatchSet. Типы определяет Lifecycle совместно с synthetic предметным контрактом, не Snapshot. Snapshot передаёт готовый binding в общей границе и не строит эффекты, coverage или предметные claims. Запрещены independent supplied copies и подмена после admission. Для apply test-only LifecycleMockApplyContext использует тот же validation subtype. Это точное предложение доступа, не уже предоставленный capability; его совместимость с общим context/lifetime должен подтвердить Snapshot.

Construction API собственного test-support binding: LifecycleMockPreparedEvidenceBinding.from_request(request:MockPatchSetAB) -> LifecycleMockPreparedEvidenceBinding; единственное внешнее construction поле request:MockPatchSetAB, frozen. MockPatchSetAB — named PatchSet с closed union LifecycleSectionAB | TestDomainSectionA | TestDomainSectionB. Binding один раз извлекает ссылки на TestDomainSectionA/B из request.sections; ничего не вычисляет из предметного payload и не создаёт его копию. Derived prepared_domain_sections — read-only property. При подключении к attempt общий scope binding проверяет identity request как того же admitted immutable request и согласованность operation/expected_world; только равенство строкового operation_id не достаточно. Использование binding другого запроса — infrastructure contract fault. Нет произвольного callback, supplied evidence factory или trusted bool. Место передачи готового binding в handler context требует общей сверки, новую ноду оно не назначает.

Минимальные synthetic native модели в tests/lifecycle/support/domainSections.py: TestDomainPatchA(PatchData) имеет base:WorldPublicationRef и effects:NonEmpty[DomainEffect[T_A]]; B аналогично. TestDomainSectionA/B — DomainSection[соответствующий patch]. Их headers/versions/codec binding замыкаются test composition. Это test-owned публичные данные, не production domain payload и не новый real domain. Полный effect содержит typed entity ref, effect kind, reason_action_uid согласно принятой модели. Fake предметный participant проверяет свою операцию/базу и обеспечивает no-op на эквивалентном повторе; Lifecycle не вызывает его validator и не пишет его состояние.

Lifecycle apply сравнивает preserved evidence с public effects/ref/base соответствующего native synthetic patch в view; проверяет exact membership, base, role/action и many-to-many relations. Предметный mock producer отвечает за смысл effects, его participant — за предметную допустимость и idempotence. Lifecycle не вызывает его методы и не пересчитывает предметный алгоритм. Для hash binding Lifecycle предъявляет общему admitted dependency-контракту конкретное требование: resolved dependency должна соответствовать fingerprint фактической секции того же request. Наличие поля RevisionHex в actual context этого не доказывает. Пока гарантия и её synthetic evidence не подтверждены общей сверкой, считать predicate выполненным нельзя. Это не поручение Snapshot достроить доменное evidence: если admitted boundary не предоставляет такой гарантии, Lifecycle должен предъявить другой явный источник, а не скрытый чужой codec/read. Отсутствующий/malformed promised view — infrastructure contract fault.

## 3. Accepted-change lookup — один вариант

Сохраняется owning dataModel/lifecycle/storage/acceptedChanges.py:

- AcceptedChangesQuery(publication:WorldPublicationRef, refs:NonEmpty[LifecycleTransitionRef]); refs unique.
- AcceptedChangeAbsent(kind:Literal['absent'], ref:LifecycleTransitionRef).
- AcceptedChangeFound[C](kind:Literal['found'], ref:LifecycleTransitionRef, transition:C).
- AcceptedChangesResult[E](publication:WorldPublicationRef, entries:tuple[E,...]); exact request order/coverage, без missing/extra/duplicate.

C — closed union восьми named transitions, E — named FoundAB | Absent. application/lifecycle/storage/participantPort.py::ILifecycleAcceptedChangesReader[Result].lookup_accepted_changes(request:AcceptedChangesQuery, *, scope:CommitReadScope) → Result (async), Result=AcceptedChangesResultAB в mock. Не AcceptedChangesRequest, не ILifecycleAcceptedChanges.read. Current read_for_section(section:L, *, publication:WorldPublicationRef, scope:CommitReadScope) → tuple[CaptureA | CaptureB,...] отдельно; captures не являются историей. Один capture на представленный вид, exact requested publication, полный набор requested entity observations. Все чтения собственного accepted view, без foreign read.

Unknown/incomplete/unavailable lookup — infrastructure fault; отсутствие индекса не Absent. Found+equal по D7 → no-op без проверки старого before против изменившейся current projection. Found+different → CHANGE_PAYLOAD_CONFLICT. Absent → current before-state check. Обязательное coverage сохраняется и для equal retry; другой synthetic participant обязан выполнить собственную идемпотентность. No-op Lifecycle не разрешает повторную предметную мутацию.

## 4. Одна apply-диагностика и carrier

Owning выбор: LifecycleApplyIssue(FieldPathError[LifecycleApplyCode]) с existing code/path/message; без proposed/accepted payload copies. Carrier — existing SectionRefused, в H2 замкнутый SectionRefused[LifecycleApplyIssue]. Отдельные три relation DTO и LifecycleApplyRefused не вводятся: у каждого отказа есть реальный native operand. Pure LifecycleSectionRefused не используется в apply. Paths принадлежат concrete LifecycleSectionAB, не prepare request.

| Code | Category | Реальный operand path | Почему |
|---|---|---|---|
| CHANGE_PAYLOAD_CONFLICT | CONFLICT | patches[i].prepared.transition.intent.change_uid | UID в текущем предложении уже занят другим accepted transition; stored payload не нужно копировать в диагностику |
| BEFORE_STATE_MISMATCH | CONFLICT | patches[i].prepared.transition.participants[j].before | Новый переход предъявляет состояние, несовместимое с authoritative exact base |
| EVIDENCE_MISMATCH | CONFLICT | patches[i].evidence[j].patch_refs[k], .effect или .section — по нарушенному отношению | Well-typed binding противоречит фактически admitted совместным данным; конфликт двух проверяемых значений, не ошибка синтаксиса |

Все три — CONFLICT. Прежний выбор REJECTED для EVIDENCE_MISMATCH отозван: в apply здесь диагностируется расхождение с authoritative/admitted view. Malformed input, неизвестная schema, неполный promised view — structural/infrastructure failure existing transport; категория CONFLICT не маскирует отсутствие данных. Неверный coverage до prepare success остаётся pure LifecycleSectionRefused. Если future semantics потребует отдельного REJECTED, нужен отдельный определённый owning predicate, а не переиспользование этого кода.

evidence_index отдельно не хранится: j/k адресуются existing CheckedPath к реальному добавленному native evidence. Relation к одному patch и его эффекту указывает соответствующее поле; отсутствующий referenced ref адресует предъявленный patch_refs[k], не несуществующий чужой элемент. Порядок issues — patch/evidence/ref index. Multiple independent conflicts собираются до записи. No invented path и нет второго класса для той же ошибки.

LifecycleApplyCode/Issue и closure model identities регистрируются в test-only H2 D/result/manifest. Не меняются production TimeSnapshotApplyResult/root20150 или existing numeric IDs. FieldPathError subclass совместим и с actual SectionRefused.diagnostics; H2 generic specialization не требует нового transport. No legacy adapters.

## 5. Append и no-op

LifecycleAppended(state:SectionStateRetention | None, history:SectionHistoryRetention | None, changed:tuple[PatchRef,...]) сохраняется. LifecycleAppendResult = LifecycleAppended | SectionRefused[LifecycleApplyIssue] в H2 (actual carrier — SectionRefused с concrete diagnostics). Handler.validate → SectionAccepted | тот же SectionRefused; apply → SectionApplyReceipt | тот же SectionRefused. Writer bound scope, append(section,expected,target) без commit/rollback.

All-equal batch: state=None/history=None/changed=(); receipt states=()/history=()/changed=(). Snapshot наследует pinned state по C2, новая state/history ссылка не создаётся. Mixed batch пишет только новые transitions; changed — исходные PatchRefs новых переходов в порядке section. Новые refs относятся к assigned target; inherited history не возвращается. Один конфликт запрещает весь append. Writer повторяет authoritative проверки в том же scope перед writes. Snapshot C2/CAS/terminal/confirmed commit остаются обязательными. Domain equality D7 не нормализует Publication immutable request fingerprint.

## 6. Точные remaining differences и тестовые обязательства

Owning выбор един: двухполевой preparation binding; section binding без section_model; AcceptedChangesQuery/lookup_accepted_changes; LifecycleApplyIssue + SectionRefused, все три codes CONFLICT; прежний no-op mapping. Это предложение заменить несовместимые варианты Snapshot/PatchSet, не заявление, что их документы уже синхронизированы.

Для общего freeze требуется техническая сверка двух явных дельт:

1. PatchSet: wrapper prepared+evidence, generic [P,E], восемь concrete bindings и manifest closure. Headers не восстанавливают потерянную entity/effect связь. Numeric IDs отдельно, не назначаются здесь.
2. Snapshot: immutable admitted synthetic sections view для evidence relation и фактическая проверка content fingerprint на общей границе. Actual context без view не достаточен; proposed mock context extension не объявляется существующей API. Вариант передачи через другую accepted capability допустим только при тех же гарантиях exact object/base/no-foreign-IO, без trusted=True.

Synthetic tests для реализации: exact named output/map; неправильный T/R при construction; immutable binding; lossless request evidence→patch evidence; decode с типами; forged ordinal/effect/action/base/fingerprint; well-typed contradiction даёт реальный EVIDENCE_MISMATCH path/CONFLICT; отсутствие promised view даёт contract fault; equivalent accepted retry без отката current projection; mixed/no-op receipts; atomic rollback всех participants. D1–D7, production OUT и порядок DAG не переоткрываются. Реализация не выполнялась; ограниченная проверка codec описана ниже и не заменяет эти тесты.

## 7. Результат технической проверки — 2026-11-21

По поручению пользователя «Проведи» проверены две границы. Это проверка осуществимости предложения и наличия возможностей в текущем коде, не приёмка общей цепочки и не разрешение реализации.

Уточнение после проверки: поступила рекомендация DAG-координатора хранить exact request.domain_evidence на уровне section.domain_evidence (types/values/order), оставив wrapper header+prepared; источник — gen-dag-lifecycle-node-contracts.md, раздел representation/coverage. Описанный ниже smoke относится к прежнему предложению patch.evidence и не выдаётся за проверку новой section-level схемы. Прежние wrapper [P,E] и paths patches[i].evidence[j] не считаются общим freeze. Рекомендация требует синхронизации owning representation и диагностических paths; вывод о недостаточности текущего prepared view/fingerprint остаётся в силе при обоих размещениях evidence.

### Native evidence и canonical codec — ограниченный PASS

Existing `backend/app/application/patch/contracts/sectionHandler.py::SectionContract` допускает concrete PatchData с дополнительными типизированными полями. `backend/app/encoding/canonicalCodec.py` кодирует declared model_fields и восстанавливает concrete RECORD types по manifest. Поэтому предложенное поле patch.evidence не требует изменения общего формата codec.

Выполнен одноразовый in-memory smoke через backend/.venv/Scripts/python.exe -B, без создания файлов: восемь named native вариантов (A/B × четыре операции), prepared и nonempty typed evidence, closed union секции и временный manifest. Проверены construction SectionContract, canonical round-trip с сохранением точных классов native patches/evidence, отказ на evidence другого вида и изменение content digest при изменении evidence patch ordinal. Все проверки прошли. Временные RECORD IDs не регистрировались в проекте.

Граница доказательства: это минимальная форма восьми вариантов, не полные Lifecycle schemas. Не проверены полная closure будущего manifest, назначение постоянных IDs, полный request→native mapping и интеграция atomic apply. Дополнительные поля совместимы с механизмом кодирования; принятие самой native-дельты остаётся предметом общей сверки.

### Prepared view и fingerprint — текущего контракта недостаточно

`backend/app/application/worldSnapshot/contracts/context.py::SnapshotValidationContext` не содержит предметных native sections. `resolved_dependencies` содержит заявления о зависимостях, но не даёт операндов для проверки ordinal/effect. `backend/app/application/patch/encoding/patchSetCodec.py::fingerprint` вычисляет digest всего request; это не доказательство равенства section_fingerprint содержимому конкретной секции. `backend/app/application/patch/registry/boundSectionCodec.py` обеспечивает привязку модели/key/version и encode/decode, но сам не сверяет dependency fingerprint. В просмотренном application-коде вычисление и сравнение section_fingerprint с фактическим содержимым секции не обнаружено.

Узкое предложение для общей сверки: общий admission связывает dependency с конкретной immutable секцией того же request и проверяет её fingerprint по единому согласованному section encoding; Lifecycle получает объявленный read-only view и проверяет собственные отношения evidence с public effects/base/refs. Возможная формула fingerprint — content_digest(bound_section_codec.encode(section)).hex(), но это предложение владельцам representation/admission, а не уже принятый алгоритм. Lifecycle не вызывает чужой codec и не принимает digest всего PatchSet вместо digest секции. Hash доказывает привязку к содержимому; смысл effects всё равно проверяет предметный participant.

Критерии закрытия этого стыка в mock_lifecycle_world: (1) view связан с тем же admitted immutable request; (2) fingerprint проверяется по фактическим bytes соответствующей секции; (3) подмена request/секции или fingerprint не проходит; (4) при верном fingerprint, но неверном claimed effect Lifecycle возвращает EVIDENCE_MISMATCH по реальному native operand; (5) отсутствие обещанного view даёт contract fault. Это локальная synthetic проверка, без production wiring, SQL и новых DAG nodes. До подтверждения capability и representation-гарантии общая apply-интеграция не объявляется PASS; принятые D1–D7 и scope остаются неизменными.
