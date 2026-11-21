# Snapshot / Lifecycle: ограниченная atomic boundary

## Сверка section-level evidence и typed view — 2026-11-21

Источники: [общая рекомендация координатора](gen-dag-lifecycle-node-contracts.md#сведение-с-первым-координатором-representation-и-coverage), [новая owning редакция](entity-lifecycle-binding-apply-contract.md) §§2,4,7 и actual backend/app/application/worldSnapshot/contracts/context.py. Этот раздел уточняет статус нижних технических proposals; распределение ответственности пользователя остаётся в силе.

**Representation:** Snapshot отзывает свой filtered wrapper coverage вариант. Для общего freeze поддерживается рекомендация `LifecycleSection[P,C].domain_evidence:tuple[C,...]` как exact copy request.domain_evidence (типы, значения и порядок), без группировки по patches; wrapper остаётся header+prepared. Это ещё совместно сверяемая дельта, не существующий runtime API. Двухполевой preparation binding Q/P с nested classes из public annotations, section_model только из section_contract и plain union на shared admission boundary совместимы с этой границей; Snapshot не создаёт собственный construction binding.

**Точные remaining differences:** owning единая редакция пока предлагает patch.evidence и grouping по change_uid, тогда как координатор рекомендует section.domain_evidence без изменения порядка. Там же EVIDENCE_MISMATCH изменён с REJECTED на CONFLICT. Нижние записи Snapshot о REJECTED отражают предыдущую owning редакцию и не фиксируют категорию новой схемы. Это не автоматически принятое изменение: Lifecycle синхронизирует normative declarations, paths, issue order и категорию, координатор проверяет общий контракт. После такой синхронизации path должен адресовать реальное `domain_evidence[i].patch_refs[k]`, `.effect` либо `.section`; индекс относится к исходному section tuple. Не использовать несуществующее patch.evidence или абсолютный запрет domain_evidence из старой схемы.

### Совместимость с all-validate-before-apply

Ограниченный immutable typed view/witness **возможен по порядку фаз**, если это заранее подготовленные данные, связанные с точным admitted request, а не результат предыдущего handler.validate. Subject participant проверяет связь собственного payload с заявленными effects; Lifecycle независимо проверяет owning relations по тем же неизменным данным. Успех разрешает apply только после успешного завершения ВСЕХ validates. Поэтому ни source-validate-first, ни mutable proof-cache, ни foreign callback/codec не нужны. Сам факт typed witness, membership или fingerprint не означает semantic proof. Lifecycle no-op не пропускает subject validation и не доказывает предметную идемпотентность.

### Delivery / capability Output→Input — ограниченная проверка owning proposal

| Output / producer | Input / consumer | Snapshot obligation / статус |
|---|---|---|
| Owning `LifecycleMockPreparedEvidenceBinding.from_request(request:MockPatchSetAB)` → frozen binding с read-only prepared_domain_sections | Предложенный `LifecycleMockValidationContext.prepared_domain_sections:tuple[TestDomainSectionA|TestDomainSectionB,...]` | Только sections того же admitted request, без независимых supplied copies, эффектов, вычисленных Snapshot, или ссылок на другой attempt. Это предложенный local view, не semantic certificate |
| Admitted request + expected publication/operation + transaction read facet | Lifecycle validate context | Проверить привязку к точному принятому request и контексту attempt; identity policy должна учитывать admission/decode, не ограничиваться равенством operation_id. Exact способ создания и передачи extended context остаётся OPEN |
| Тот же immutable validation view | `SnapshotApplyContext.validation` для Lifecycle apply | Сохранить тот же admitted набор и контекст; не пересобирать view из latest или промежуточных writes. Read scope/writer lifetime ограничены общей transaction. Actual поле validation уже существует, но доставка subtype ещё не объявлена |
| Subject native payload/view | Subject validate; Lifecycle relational validate | Owning producer/verifier Input/Output/Error и достаточность данных определяют subject/Lifecycle. Snapshot собирает existing accepted/refused outcomes и не запускает чужой verifier из Lifecycle |
| Dependency + фактическая admitted section representation | Общая ref/fingerprint граница | Требуется точный representation/admission контракт fingerprint конкретной section. Digest всего PatchSet и заявленный section fingerprint не заменяют эту проверку. Алгоритм и capability не объявлены принятыми |

Actual SnapshotValidationContext содержит operation_id, expected_world/players, resolved_dependencies и read_scope; typed view/witness отсутствует. Простое объявление subclass не добавляет способ его доставки. Owning proposal уже задаёт from_request и тип view, но не замыкает integration seam: кто и каким exact методом формирует context для bound handler, как общий сервис передаёт его без Lifecycle-specific ветвления и произвольной factory/callback. Snapshot не выдаёт предложение за существующий API и не добавляет параллельный subject schema. После синхронизированного owning proposal этот узкий seam проходит общую сверку.

Synthetic acceptance для доставки: view другого request/attempt отвергается; подмена view между validate/apply невозможна; expired scope не читается; Lifecycle validate до subject validate допустим, но subject refusal запрещает все apply; valid fingerprint при ложном effect не даёт общий успех; equal Lifecycle retry не подавляет subject refusal. Предметные исходы обеспечивает owning mock verifier, Snapshot проверяет запрет writes и общую atomic boundary. Код/тесты не запускались. Статус: фазовая совместимость условно подтверждена; representation sync, exact delivery capability и fingerprint binding OPEN; полной приёмки нет.

## Принятая граница ответственности — решение пользователя 2026-11-21

Источник: решение пользователя «Согласен это не ответственность snapshot», переданное назначенным DAG-координатором (чат Between domain operations, 01a1ef35-3287-7a12-89e2-76273eaa043d). Этот раздел имеет приоритет над предложениями ниже. Принято распределение ответственности, не новые DTO/categories/representation changes и не предоставление capability.

Lifecycle определяет собственные apply predicates, необходимые lifecycle-факты/evidence, их типы, точные источники и достаточность. Для каждой проверки владелец предъявляет таблицу: predicate → необходимые typed operands → точное поле native-контракта либо объявленный метод источника и его result field → связь с участником/effect/base → проверяющий класс/метод → outcome. В таблице прослеживаются prepare_section → native → apply и сохранение требуемых typed связей. Snapshot не проектирует эту доменную таблицу, не восполняет её пробелы новым schema/validator, доменной логикой или скрытыми foreign calls.

Предметный смысл подтверждений принадлежит владельцам предметных данных. Lifecycle проверяет согласованные отношения подтверждений с участниками, эффектами и базой, не реализует вместо них предметный алгоритм. Предложения о representation evidence и его источниках ниже остаются материалом для решения Lifecycle, а не требованиями Snapshot к форме доменного контракта.

После предъявления owning таблицы Snapshot выполняет только следующую сверку Output→Input и общих гарантий:

| Граница | Обязанность Snapshot при сверке |
|---|---|
| Источник → apply operand | Указан точный объявленный capability, тип output совместим с input; проверяются scope/lifetime и допустимый путь вызова, без оценки достаточности доменного доказательства |
| Context → reader/writer | Expected publication передаётся без подмены; общий transaction scope, borrowed facets и завершение доступа сохраняются; нет самостоятельного commit или foreign writer |
| Admitted PatchSet → handler | Patch/dependency refs относятся к принятому входу; нужный доступ явно объявлен и согласован, наличие handler/DI само по себе его не разрешает |
| Assigned refs → append → receipt | Назначенные identities передаются без переназначения; immediate C2 receipt provenance, membership и retention checks остаются обязательными |
| Receipt → публикация | Единая atomic boundary, CAS, commit/rollback/unknown и принятый порядок apply сохраняются; successful receipt ещё не означает commit |

Новый доступ принимается только как точный контракт через общую координацию. Предложенный ниже admitted_patch_refs не считается уже предоставленным и не является обязательным решением до owning таблицы: сначала предъявляется потребность, затем проверяется reuse существующих capabilities либо согласуется минимальная дельта. Snapshot не ослабляет общие проверки в ожидании доменного контракта.

Статус: распределение ответственности ACCEPTED; exact Lifecycle evidence/source contract ожидается от владельца, зависимая интеграционная сверка OPEN. Scope: mock_lifecycle_world, synthetic A/B, готовые inputs, вариант А. Отсутствие реальных producers/SQL adapters/production wiring не blocker. D1–D7 не переоткрываются. Код не поручен.

## Сведение с owning Lifecycle C2/C3 — 2026-11-21, актуальный proposal

Источник: entity-lifecycle-local-contracts.md §§C2/C3. Snapshot принимает owning naming и классификацию, не создаёт второй протокол/ошибки. Этот раздел заменяет конфликтующие proposals ниже. Это документальная совместимость со стороны Snapshot, не заявление полученного обратного согласия на ещё отсутствующую coverage capability.

### Lookup и current captures — единый контракт

Owning `dataModel/lifecycle/storage/acceptedChanges.py::AcceptedChangesQuery(publication:WorldPublicationRef, refs:NonEmpty[LifecycleTransitionRef])`; AcceptedChangeAbsent(kind='absent',ref), AcceptedChangeFound[C](kind='found',ref,transition:C); AcceptedChangesResult[E](publication,entries). В local AB binding конкретный результат AcceptedChangesResultAB, closed FoundAB/Absent; transition C — восемь named owning Transition types, не Prepared/capture.

`application/lifecycle/storage/participantPort.py::ILifecycleAcceptedChangesReader[Result].lookup_accepted_changes(request:AcceptedChangesQuery, *, scope:CommitReadScope) -> Result`, async; Result=AcceptedChangesResultAB. Прежние Snapshot AcceptedChangesRequest/ILifecycleAcceptedChanges.read отменены, ни новый reads/acceptedChanges.py, ни второй wire record не нужны.

`ILifecycleParticipantReader[LifecycleSectionAB].read_for_section(section:LifecycleSectionAB, *, publication:WorldPublicationRef, scope:CommitReadScope) -> tuple[CaptureA|CaptureB,...]`, async. CaptureA/B — owning closed LifecycleCapture специализации. Один capture на представленный вид; те же exact Q и required entity observations, не history completeness. Lookup отдельно обеспечивает полный ответ по запрошенным change refs в исходном порядке. Partial/missing/extra/duplicate result или Q mismatch — infrastructure contract fault, не Absent. Оба reader относятся к собственному Lifecycle persistence в одном borrowed scope.

### Apply outcome — reuse owning H2 carrier

Прежние LifecycleChangePayloadConflict/LifecycleCurrentStateConflict/LifecycleApplyEvidenceConflict, LifecycleApplyDiagnostic и LifecycleApplyRefused **отозваны**, в active roster не входят. Owning тип — `dataModel/lifecycle/results/applyIssue.py::LifecycleApplyIssue(FieldPathError[LifecycleApplyCode])`, только inherited code/path/message.

- CHANGE_PAYLOAD_CONFLICT → path patches[i].prepared.transition.intent.change_uid, category CONFLICT.
- BEFORE_STATE_MISMATCH → patches[i].prepared.transition.participants[j].before, category CONFLICT.
- EVIDENCE_MISMATCH → существующий header.depends_on[k] при несовпадении section binding; либо реальный before/after operand участника для доказанной owning relation ошибки, category REJECTED. Не создавать domain_evidence/evidence_index path: поля в native section нет. Потерянное evidence нельзя переименовать в mismatch известного поля.

Owning mixed refusal: CONFLICT если есть conflict code, иначе REJECTED; это Lifecycle semantic выбор, Snapshot его не вычисляет повторно. Общая Snapshot aggregation нескольких handler refusals сохраняет принятую REJECTED-priority по категориям handler results. Это разные уровни; Snapshot не просматривает Lifecycle codes для изменения local категории.

`validate(section:L,context:SnapshotValidationContext) -> SectionAccepted|SectionRefused[LifecycleApplyIssue]`; `apply(section:L,context:SnapshotApplyContext) -> SectionApplyReceipt|SectionRefused[LifecycleApplyIssue]`; bound writer `append(section:L, *, expected:WorldPublicationRef,target:WorldSnapshotRef) -> LifecycleAppended|SectionRefused[LifecycleApplyIssue]`, async. Exact H2 named specialization принадлежит composition, отдельный новый Lifecycle carrier не назначается. Pure LifecycleSectionRefused остаётся только prepare_section output. Manifest/path registrations должны включить owning apply issue; Time result20150 автоматически не расширяется.

Lookup ordering/no-op mapping подтверждены: Found+equal D7 → не сверять старый before с текущей projection и не писать переход повторно; Found+different → owning conflict; Absent → current preconditions. All-equal: state=None,history=None,changed=(); mixed: только новые входные PatchRefs в исходном порядке, history только новые transitions, state поверх current Q. append повторяет authoritative checks в scope до writes. Snapshot C2 проверяет refs/retention, не Lifecycle semantic equality.

### Exact trace evidence → native: что доступно и что отсутствует

| Этап | Реальные operands / проверка | Что не доказано |
|---|---|---|
| PrepareLifecycleSectionAB | changes и domain_evidence: explicit PreparedEffectBinding A/B, key(change_uid,typed entity,effect), nonempty patch_refs, section fingerprint | Чужое тело patch не читается; hash/semantic correctness не доказаны pure prepare |
| Native builder | wrapper(header,prepared); section.header.depends_on — объединённые prepared section deps | Effect→patch_refs и исходный evidence index не входят в wrapper/section и теряются |
| Snapshot admission | Полный PatchSet, зарегистрированные section bindings/codecs, общие dependency checks | Snapshot не знает semantic effect чужого patch и не восстанавливает потерянное many-to-many mapping |
| Lifecycle handler context | expected_world/operation_id/resolved_dependencies/read_scope, native prepared transitions | Context не содержит PatchSet bodies, per-effect coverage или отдельного proof payload validation |
| Current admitted dependency | Позволяет проверить конкретное несоответствие header.depends_on | Одного section fingerprint недостаточно для проверки exact effect→PatchRef либо предметной допустимости |

Следовательно, прежнее обещание «handler проверяет весь supplied evidence» с текущей native schema **невыполнимо**. Нельзя читать несуществующий section.domain_evidence, подставить fake успешный proof, дернуть foreign codec/pipeline из Lifecycle или расширить scope writer через DI.

**Прежний filtered wrapper coverage вариант отозван.** Актуальная рекомендация координатора — section.domain_evidence exact copy request; см. сверку в начале документа. Решение не превращает evidence в semantic proof и требует синхронизации owning declarations.

**Необязательный вариант Snapshot capability, не существующее поле:** read-only `admitted_patch_refs: tuple[PatchRef,...]` в SnapshotValidationContext из admitted исходных sections/patches. Рассматривается только если owning таблица докажет потребность в таком доступе и невозможность reuse уже объявленного capability. Это immutable refs, не чужие payloads/IO port и не semantic proof. Пока поле не принято, на него нельзя ссылаться как на operand действующего контракта. OPEN относится к точному доступу, необходимому предъявленным проверкам, а не к обязательному принятию этого варианта.

Membership+fingerprint доказывают наличие совместных patches, **не** их semantic effect/base. Synthetic предметный participant обязан сам проверить соответствие собственных native operands actual Q и declared effects, сохраняя checked relation с retained coverage. Точный typed effect projection/binding между synthetic native payload и coverage пока должен предъявить owning synthetic/Lifecycle контракт; metadata/ref не заменяют это доказательство. Без него не объявлять payload verification PASS. Вариант foreign public callback в Lifecycle отвергнут. Отдельный новый DAG этап/NodeId/SQL/world scope не предлагается.

### Вердикт текущей сверки

- Lookup naming/result и tuple current captures: совместимы с owning Lifecycle, Snapshot дубли отозваны.
- Apply diagnostics/category/carrier и no-op: совместимы, pure refusal исключён из apply; новые Snapshot relation DTO отозваны.
- Exact coverage: **OPEN — Lifecycle предъявляет owning таблицу predicates/operands/источников и сохранённых native связей; затем Snapshot проверяет её scope/capability/ref/receipt/atomic guarantees и Output→Input**. Предложенные выше representation/context поля не являются обязательным решением. Это технические IN обязанности, не D3/D4 повторный выбор и не требование реальных domains/SQL.
- После сверки owning таблицы и необходимых capabilities Snapshot проверяет ref/dependency boundaries, scope/lifetime, receipt и атомарные исходы на mock fixture. Lifecycle и synthetic owner задают проверки claimed effects, полноты evidence и semantic retry по своим operands; Snapshot не создаёт второй validator этих predicates. D1–D7/C1/C2/H3 не переоткрываются. Код/общий node-план/рассылка не изменены.

## Архив: прежнее предложение authoritative retry / apply refusal — заменено разделом выше

Этот раздел сохраняется только как история обсуждения. Его naming, отдельные relation DTO/carrier и классификация всех ошибок как CONFLICT отозваны. Для реализации и сверки использовать актуальный контракт в начале документа; нижние исходные signatures также не являются самостоятельным альтернативным контрактом.

Owning source: entity-lifecycle-local-contracts.md. LifecycleCapture содержит только entities/last_transitions, **не полную историю change_uid**. LifecycleSectionRefused — pure prepare_section отказ, **не** Snapshot SectionRefused и не apply carrier. Прежние signatures/утверждения ниже заменяются этим разделом. Требуется подтверждение Lifecycle/координатора, согласование владельца не выдумывается. SQL и production producers вне scope.

### Отдельный accepted-change lookup

Предлагаемый owning модуль `dataModel/lifecycle/reads/acceptedChanges.py`, все модели strict/frozen/extra-forbid/revalidate-always:

- `AcceptedChangesRequest`: publication:WorldPublicationRef; changes:tuple[LifecycleTransitionRef,...]. Unique полные typed refs, мир совпадает с Q; origin_timeline_id не переписывается active timeline. В fixture один timeline; общего branch/rebind правила не добавляется.
- `AcceptedChangeFound[C]`: ref:LifecycleTransitionRef; transition:C. C — closed union восьми существующих concrete LifecycleTransition типов из SyntheticPreparedUnion.transition, без нового mirror payload. Ref совпадает с intent.change_uid и after.last_transition всех participants; world/origin timeline согласованы. Publication metadata не добавляется в semantic transition.
- `AcceptedChangeAbsent`: ref:LifecycleTransitionRef. Это affirmative результат owning lookup, а не inferred None.
- `AcceptedChangesResult[C]`: publication:WorldPublicationRef; entries:tuple[AcceptedChangeFound[C] | AcceptedChangeAbsent,...]. Ровно один entry на request ref, тот же порядок, без extra/duplicate; request/output correlation проверяет consuming handler.

`application/lifecycle/storage/participantPort.py::ILifecycleAcceptedChanges[C].read(request:AcceptedChangesRequest, *, scope:CommitReadScope) -> AcceptedChangesResult[C]`, async. Читает только собственный authoritative accepted change index/history, достижимый из exact Q, включая прежние transitions, уже не last_transition. Absent разрешён только после полного lookup в этой области; incomplete/unavailable/corrupt index — infrastructure failure, не Absent и не conflict. Полнота — обязанность реализации port, не доверенный boolean в DTO. Fake хранит accepted history index отдельно от current entities; негативный тест неполного источника обязателен. Нельзя удовлетворить port через LifecycleCapture.last_transitions.

Existing `ILifecycleParticipantReader.read_for_section` продолжает возвращать closed LifecycleCapture для текущих entities/last_transitions по Q; обещание history completeness из него удалено. Общая transaction даёт обоим readers одну accepted Q view. Источник change lookup namespace — собственный Lifecycle storage; поиск в чужих таблицах/foreign pipeline запрещён. Нужные refs получаются из owning prepared transition identities, не из нового UID allocator.

### Apply carrier на H2

Предлагаемый owning модуль `dataModel/lifecycle/results/apply.py`; это relation diagnostics без prepare request FieldPath:

- `LifecycleChangePayloadConflict[C]`: patch_ref:PatchRef; publication:WorldPublicationRef; accepted_ref:LifecycleTransitionRef; proposed:C; accepted:C. UID/scope каждой transition совпадают с accepted_ref; факт semantic inequality проверяет Lifecycle owning validator, не Snapshot/registry. C — тот же closed transition union.
- `LifecycleCurrentStateConflict[P,Capture]`: patch_ref:PatchRef; proposed:P; observed:Capture. P — SyntheticPreparedUnion, Capture — closed LifecycleCapture[A] | LifecycleCapture[B]; kind/entity correspondence и required observed facts проверяются Lifecycle. Это конфликт фактических preconditions, не доказательство change absence.
- `LifecycleApplyEvidenceConflict`: patch_ref:PatchRef; publication:WorldPublicationRef; evidence_index:StrictInt>=0; referenced_patch:PatchRef. Означает mismatch переданной coverage с admitted совместным patch/source binding; индекс в section evidence, не выдуманный field path. Exact detail enrichment возможен только owning решением; payload не копируется.

`LifecycleApplyDiagnostic` — closed union этих трёх именованных concrete specializations. `LifecycleApplyRefused(SectionRefused[LifecycleApplyDiagnostic])` — named local H2 carrier, только общие structural invariants. Все перечисленные conflicts category=CONFLICT; malformed input/output и недоступный authoritative источник — execution faults, не добавление REJECTED ради обхода. Semantic consistency/category проверяет Lifecycle apply validator до return. Duplicate change_uid внутри batch по-прежнему запрещён pure section invariant/revalidation; отдельного published conflict из malformed batch не фабрикуется.

`LifecycleSectionHandler.validate(section:L, context:SnapshotValidationContext) -> SectionAccepted | LifecycleApplyRefused`; `apply(section:L, context:SnapshotApplyContext) -> SectionApplyReceipt | LifecycleApplyRefused` (оба async). `IBoundLifecycleWriter.append(section:L, *, expected:WorldPublicationRef, target:WorldSnapshotRef) -> LifecycleAppended | LifecycleApplyRefused`, async. Pure LifecycleSectionRefused в этих signatures **не используется**. Generic H2 механика не меняется; текущая TimeSnapshotApplyResult20150 не расширяется Lifecycle типами автоматически. Для mock composition нужен отдельный closed result binding по существующему generic contract; wire IDs/manifest выбираются owning совместно, без переназначения20150. Это техническая integration obligation local IN.

### Authoritative retry → append/no-op

Порядок внутри validate/apply Lifecycle: native/context admission → complete accepted-change lookup → semantic compare найденных transitions → для Absent отдельно actual entity preconditions → evidence/coverage binding. Found+equal по принятому D7 — уже принятый переход: не требовать заново его прежний before-state от текущей projection, не восстанавливать старое состояние и не создавать history operation. Found+different → LifecycleChangePayloadConflict. Absent → обычные owning preconditions; отсутствие current entity не заменяет accepted-change lookup. Сравниваются исходные before/after/roles/reason без publication metadata; порядок participants внутри каждой стороны незначим, порядок представления и Publication exact fingerprint неизменны.

Bound append повторяет lookup/проверки в том же scope перед любыми writes; validate не authority token, mutable кэш не заменяет чтение. Для all-equal batch: LifecycleAppended(state=None,history=None,changed=()); receipt states=(),history=(),changed=(), Snapshot наследует base state. Для mixed independent batch: писать только Absent/new transitions, history bundle содержит только новые operations, changed — точные входные PatchRef новых transitions в исходном порядке; state отражает результат новых transitions поверх current Q, не старые after-state повторов. Conflicting один transition запрещает весь append.

D4 не отменяется для equal retry: обязательные предметные patches/evidence остаются в секции. Atomicity сама по себе не доказывает идемпотентность второго participant. **Local IN obligation:** synthetic предметный participant должен при equivalent covered effect вернуть собственный no-op, а при несовместимом эффекте — отказ до commit; повтор Lifecycle не разрешает повторную побочную мутацию. Покрытие не пропускается потому, что change уже найден. Exact shared proof admitted-patch/source mapping сверяют Lifecycle и synthetic participant owner; Snapshot не исполняет их semantics. Реальный producer/SQL не нужен для доказательства mock case.

Тесты mock_lifecycle_world: accepted transition X перестал быть last_transition после Y, но lookup X остаётся Found; неполный index не выдаёт Absent; одинаковый change_uid другой operation с reordered Replacement participants даёт no-op без отката текущей projection; изменённое reason/roles/before-after даёт typed conflict; mixed retry/new добавляет только новые operations; coverage/domain participant retry не создаёт повторных эффектов; conflict второго participant откатывает всё. Whole-operation terminal replay по-прежнему раньше всех этих reads. Cancellation/unknown/receipt C2 не меняются.

**Остаток согласования:** Lifecycle подтверждает names/reuse/closed aliases и authoritative scope/comparison; PatchSet/composition — closed H2 diagnostic/result binding; synthetic capability input для exact admitted coverage требует совместного frozen mapping. Нет заявления, что pure capture/refusal закрывают эти задачи. D1–D7 не переоткрываются, OUT не blockers.

**Синхронизация принятия D1–D7, 2026-11-21:** источник entity-lifecycle-local-contracts.md. Prepared records pure без header; header появляется единожды в native wrapper. Create/End/Reactivate — singleton, Replacement — многосоставной; explicit many-to-many coverage обязательно; NoDomainMutation запрещён в local v1. Reactivate после End допустим, после Replacement отвергается. Используется отдельная fixture `mock_lifecycle_world` («mock-мир Lifecycle»), с начатым состоянием/одним timeline только в тестовом профиле. Порядок участников каждой стороны Replacement не влияет на domain semantic retry equality, но порядок представления, patches/ordinal и Publication exact request fingerprint сохраняются. D1–D7 больше не OPEN; exact binding/union/регистрации и atomic boundary требуют технической сверки. Fixture ещё не создана; код не разрешён.

2026-11-21, PROPOSED для Lifecycle и координатора. Задание №4 [node-плана](gen-dag-lifecycle-node-contracts.md). Документальный контракт, не code-go. C1/C2/H2, H3 Time, порядок write_changes не пересматриваются. IN — готовая typed LifecycleSection, synthetic TestEntityA/TestEntityB, fake participant и общая atomic boundary. OUT — реальные producers/объекты, SQL/DDL/adapters, production wiring, read_world, bulk, вариант Б, overlapping chains, checkpoint/restart. OUT не blockers этого среза.

## 1. Владельцы проверок и порядок

| Проверка | До transaction | В общей transaction |
|---|---|---|
| Shape/native schema/версии | Owning модели и C1 registry/codec; Snapshot request admission | BoundSectionHandler проверяет output shape по C1/H2; не дублирует semantics |
| operation_id, expected_world, PatchRef/dependencies | Lifecycle prepare_section формирует headers и проверяет supplied evidence; PatchSet проверяет общие invariants | Snapshot сравнивает actual expected heads/context, immutable binding; Lifecycle сверяет свои supplied operands с context |
| Lifecycle source/before-state | Pure prepare использует supplied typed capture, не latest и не IO | Lifecycle handler читает собственное accepted состояние exact Q в borrowed read facet и проверяет preconditions; Snapshot не вычисляет lifecycle status |
| Предметное основание/evidence | Owning synthetic producer проверяет свои факты/typed payload; Lifecycle проверяет structural relation/coverage, не предметную логику | Lifecycle проверяет Q/operation/entity/patch bindings supplied evidence; Snapshot гарантирует общий Q и admitted dependency refs. Нельзя превратить произвольный POJO/trusted=True в proof принятого состояния |
| Duplicate change_uid в batch | Lifecycle prepare_section отклоняет весь batch, даже если повтор равен | Lifecycle handler повторно применяет тот же owning pure invariant для unchecked/direct/decode path, не копирует алгоритм |
| change_uid уже в accepted history | Pure capture не доказывает history completeness; pure prepare не выполняет authoritative lookup | Lifecycle использует отдельный AcceptedChangesQuery/lookup_accepted_changes → AcceptedChangesResultAB в том же scope; owning semantic equality определяет no-op/conflict. Operation replay Snapshot не заменяет эту проверку между разными operation_id |
| Участники пересекаются между переходами | Lifecycle section invariant запрещает; independent transitions сохраняют входной порядок | Owning revalidation того же инварианта; Snapshot не сортирует и не пытается разрешить цепочку |
| Receipt membership/assigned refs/inheritance | Не проверяется по выдуманному будущему snapshot | Snapshot C2 сразу после successful apply до accumulator/следующего handler; PatchSet проверяет лишь output contract |

Trace новой попытки: admission → fingerprint → claim/replay → общая transaction → expected-context checks → предусмотренные принятым порядком source bindings → все handler.validate → дочитывание C2 bases с reuse → последовательные handler.apply и immediate C2 check → metadata/handoff/CAS/terminal → confirmed commit. Lifecycle не получает Time source binding по аналогии. Если ему нужна Snapshot metadata source resolution, предъявляется собственный binding; fake собственного Lifecycle persistence может читать accepted view по exact Q без foreign lookup.

Replay текущей operation выходит до Lifecycle reads/handler. Validation refusal запрещает все apply. Apply refusal/contract fault/CAS conflict откатывает все уже выполненные writes; разделение business/infrastructure/unknown остаётся owning H2. Отказ не выдаёт частичную секцию/успех.

## 2. Точные application port obligations — предложение Lifecycle owner

Сигнатуры используют closed `L` конкретной LifecycleSection и её native patch union, определяемый Lifecycle/PatchSet. Не подставлять DomainSection/BaseModel как runtime L. Current captures и отдельный accepted-change lookup берутся из owning C2, приведённого в начале документа; Snapshot не создаёт второй capture/evidence POJO. Ниже — mapping интеграционных ports, не назначение доменных predicates или источников.

Предлагаемый `application/lifecycle/storage/participantPort.py`:

```python
class ILifecycleParticipantReader[L](Protocol):
    async def read_for_section(
        self, section: L, *, publication: WorldPublicationRef,
        scope: CommitReadScope,
    ) -> tuple[CaptureA | CaptureB, ...]: ...

class ILifecycleCommitBinding[L](Protocol):
    def bind(self, scope: CommitScope) -> IBoundLifecycleWriter[L]: ...

class IBoundLifecycleWriter[L](Protocol):
    async def append(
        self, section: L, *, expected: WorldPublicationRef,
        target: WorldSnapshotRef,
    ) -> LifecycleAppendResult: ...
```

Это узкие ports собственного Lifecycle persistence, не public domain pipelines. Payload read request не содержит чужого store/handler. Writer связывается только с существующим scope и не commit/rollback/retry. `append` повторно проверяет owning preconditions/idempotence в том же exact accepted Q до первого write, затем добавляет Lifecycle operations и projections в общий transactional workspace. LifecycleAppendResult — owning C3 alias `LifecycleAppended | SectionRefused[LifecycleApplyIssue]` на H2. Pure LifecycleSectionRefused здесь не используется. Проверки и необходимые источники определяет Lifecycle, Snapshot сверяет capability/lifetime и атомарность.

Owning C3 `dataModel/lifecycle/publication/appendResult.py::LifecycleAppended`: state:SectionStateRetention | None; history:SectionHistoryRetention | None; changed:tuple[PatchRef,...]. Все поля обязательны, strict/frozen/extra-forbid/revalidate-always. Это storage postcondition, не committed result и не вторая history-operation запись. Новый state и любой возвращённый history ref относятся к assigned target и Lifecycle section key, versions принадлежат Lifecycle. Для local row-like fake artifacts=(). При all-equal retry: changed=(), history=None, state=None; Snapshot builder наследует неперезаписанное base state. Прежние варианты inherited history и отдельного inherited state в no-op append отозваны. Null history на no-op — local Lifecycle contract, не новое общее правило cardinality Snapshot.

LifecycleSectionHandler.validate(section:L,context:SnapshotValidationContext) → SectionAccepted | SectionRefused[LifecycleApplyIssue] использует объявленные owning readers и pure owning checks. apply(section:L,context:SnapshotApplyContext) → SectionApplyReceipt | SectionRefused[LifecycleApplyIssue] использует binding.bind(context.scope).append(section, expected=context.validation.expected_world, target=context.world_snapshot). Handler строит receipt из результата и owning section key: states=() при state=None, иначе (state,); history=() при history=None, иначе (history,); changed передаётся точно. Refs не переназначает. Shape admission — BoundSectionHandler, provenance — Snapshot C2. Snapshot передаёт назначенные world_snapshot/next_publication и принятый operation_id; Lifecycle не выделяет эти identities и не пишет publication heads.

Ошибки ports: malformed request — owning strict admission; semantic stale/precondition/change_uid conflict — concrete Lifecycle refusal; missing required source/completeness, corruption, scope/IO/output inconsistency — infrastructure failure с cause. None не означает автоматически отсутствие entity/истории. Empty current view подтверждается owning current-read result; отсутствие принятого change — отдельным AcceptedChangeAbsent из authoritative lookup, не capture или fallback. Unknown transaction outcome принадлежит transaction owner, не writer. Cancellation не разрешает detached writes; fake/adapter drain обязан завершиться до возврата scope owner.

## 3. Разрешённая capability chain и Output→Input

Разрешённый маршрут: apply_snapshot → Snapshot public apply → registry BoundSectionHandler → LifecycleSectionHandler → Lifecycle-owned reader/pure validators/bound writer → собственное transactional fake state. Fake SQL не симулирует: нет foreign tables/public pipelines. Scope лишь разрешает участие в transaction, **не даёт право писать данные чужого домена**. Writer Lifecycle меняет только Lifecycle history/projections.

При synthetic предметном изменении его fake owning participant регистрируется отдельно через тот же C1 механизм и получает свой ограниченный writer в той же outer transaction. Lifecycle handler не вызывает его, не получает mutable state и не пишет его history. Fixed declared order/dependencies задаются готовым PatchSet. По D3/D4 обязательна explicit many-to-many coverage typed участников и предметных patches; отсутствующий обязательный patch даёт owning coverage refusal. Active local v1 union не содержит NoDomainMutation/no-domain-patch proof. Boolean bypass запрещён. Snapshot проверяет свои admitted dependency/receipt boundaries, Lifecycle — owning coverage, без копии предметной логики.

| Output | Input / обязательное равенство |
|---|---|
| Prepared records + domain_evidence | PrepareLifecycleSection: operation/Q/typed participant scope согласованы, один transition → один patch |
| LifecycleSection | PatchSet.sections: тот же concrete object/value, порядок/headers/dependencies сохраняются; повторной подготовки нет |
| SnapshotValidationContext | reader publication=expected_world, scope=read_scope; каждый CaptureA/B.publication и AcceptedChangesResultAB.publication равен Q; полнота каждого результата определяется owning reader contract |
| SnapshotApplyContext | writer expected=validation.expected_world, target=world_snapshot, capability=scope; без новой transaction |
| LifecycleAppended | Receipt: exact retention entries/changed refs передаются без реконструкции identity |
| Receipt | C2→metadata→CAS: successful receipt ещё не commit; history ref может адресовать bundle многих transitions |
| Confirmed terminal | apply output: только после confirmed commit/refusal persistence; unknown не normal result |

History cardinality: 100 independent Creates → 100 patches/100 новых Lifecycle history operations при первом успешном применении; один Replacement со 100 участниками → один patch/одна operation, число projections по участникам. Число SectionHistoryRef в receipt не равно числу операций: один ref может адресовать section history bundle. Для семантического повторения change_uid новых history operations нет; exact правила changed/no-op retention требуют owner mapping, не автоматического равенства changed всем входным refs.

## 4. Synthetic fake и критерии приёмки

Вся local suite использует `mock_lifecycle_world` («mock-мир Lifecycle»): детерминированные typed world/publication/timeline refs, начатый профиль и один timeline, проверяемые captured facts видов A/B. Это test-support, не production world, не запуск gameplay pipeline и не ограничение общего Lifecycle. FakeTransactionOwner ниже — transaction mechanism этой fixture, не второй мир. Создание fixture выполняется только при разрешённой реализации через implement-plan.

Дополнительные assertions D1–D7: prepared не содержит header, wrapper формирует его единожды; singleton cardinality трёх операций; many-to-many coverage без NoDomainMutation и отказ при missing обязательном patch; Reactivate после End разрешён, после Replacement отказ. Для одного change_uid перестановка участников ВНУТРИ каждой стороны Replacement сохраняет domain semantic equality; изменение ролей/состава/основания — нет. Сериализация сохраняет представленный порядок. Отдельная проверка Publication: тот же operation_id с изменённым exact request не обязан считаться replay и проходит existing binding mismatch независимо от Lifecycle semantic equality. Для проверки domain retry используется новый корректный publication request/capture; Snapshot не сортирует участников или patches ради сравнения.

FakeTransactionOwner — test-only реализация существующей commit capability semantics: один workspace транзакции, отдельные namespaced stores Lifecycle/DomainA/DomainB, accepted immutable baseline Q, commit публикует все namespaces вместе, rollback отбрасывает весь workspace. Он не shared production service и не новый DAG scope. Reader возвращает actual accepted Q view, не заранее заданный ответ на любой запрос. Bound writer проверяет active scope/свой namespace; после завершения owner доступ отклоняется. Baseline не меняется предыдущими staged writes, поэтому validate/apply expected-Q checks сравниваются с той же базой.

Проверки local IN (спецификация будущих проверок, не результаты запуска): пункты 1–4 принадлежат Lifecycle/synthetic owner в части domain predicates; Snapshot проверяет общий commit и сохранение input order из пункта 2, а также общие гарантии пунктов 5–8. Доменные assertions не переносятся в Snapshot validators.

1. Closed A/B native decode сохраняет вид; Snapshot не ветвится по A/B. Переданные source/evidence имеют typed identities и полноценные required поля.
2. 100 Creates и 100-participant Replacement дают указанную cardinality, один общий commit, input order сохраняется.
3. Неверный Q/operation/source revision/coverage ref и duplicate change_uid внутри batch отвергаются owning проверками; отсутствующий required evidence не заменяется mock default.
4. Same change_uid в другой operation: equal semantic transition без второй history operation; different content — typed conflict. Разные publication metadata не должны сами превращать один transition в different content; exact comparison задаёт Lifecycle.
5. Ошибка второго participant после writes первого, malformed receipt и CAS conflict оставляют все accepted namespaces неизменными. Нет следующего handler после отказа; detached writes отсутствуют.
6. Wrong target/foreign changed ref/сфабрикованный inherited retention обнаруживаются C2; writer не может писать чужой namespace или commit напрямую.
7. Commit acknowledgement lost → unknown; тест различает физически совершившийся и не совершившийся commit, не объявляет rollback по исключению. Exact terminal replay не вызывает writers/reader повторно.
8. Cancellation/drain/expired scope, missing/corrupt source, current output type/diagnostic preservation проходят без business маскировки infrastructure faults. Не проверяется deferred durable-cancellation node mapping.

Fake evidence проверяет протокольные обязанности, но не доказывает production storage durability/SQL isolation/cleanup. Для локального дизайна эти OUT не требуются.

## 5. Статус и оставшиеся решения строго внутри IN

Snapshot предъявил владельцев checks, fixed phase order, assigned refs, permitted nested calls, mapping owning ports и synthetic assertions. Сверка с решением пользователя выполнена: доменное доказательство остаётся у Lifecycle/предметных владельцев, общие гарантии Snapshot сохранены. Whole local binding пока **OPEN**; это не полная приёмка плана по обязательным критериям DAG:

- Exact closed L/diagnostic union и codec declarations (задание Lifecycle/PatchSet), без новых numeric IDs здесь.
- Lifecycle предъявляет таблицу apply predicates → typed operands → точные источники/поля native → проверяющий класс/метод → outcomes. Доменные достаточность, semantic comparison и sources определяет владелец; Snapshot проверяет только интеграционные обязанности из принятой границы в начале документа.
- Current captures tuple[CaptureA|CaptureB,...] и отдельный AcceptedChangesResultAB согласованы по owning C2; прежний OPEN «полная история в capture» снят. Проверка конкретного wiring требует exact Q и общего borrowed scope, не нового capture.
- После owning таблицы сверяются реально необходимые capabilities, Output→Input и сохранение accepted order. Ни coverage field, ни admitted_patch_refs не назначены обязательным решением. D7 и запрет NoDomainMutation D4 не переоткрываются.
- LifecycleAppended и SectionRefused[LifecycleApplyIssue] переиспользуются по owning C3; all-equal даёт state=None/history=None/changed=(), mixed — только новые changes. Snapshot проверяет receipt mapping/C2 и отсутствие foreign writer, не вычисляет domain equality.

Это необходимые local схемы/обязанности, не запрос реального producer, SQL adapter, production entity или checkpoint. Lifecycle source binding не считается закрытым Time H3. После owning ответов координатор сверяет ограниченный IN и пользователь принимает; код/общий node-план этим документом не изменены.
