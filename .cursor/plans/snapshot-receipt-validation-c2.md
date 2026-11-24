# Snapshot C2: проверка результата применения секции

**Уточнение R3/R4/R5, 2026-11-21:** [точный контракт admitted facts и диагностики](snapshot-receipt-facts-diagnostics.md) прошёл координаторскую документальную сверку, включая final first-error фазу. Он заменяет fully-valid-only extraction и подавление FOREIGN_OPERATION. Следующий этап — подключение early validator, builder и final checker к одним predicates с regression evidence, не новая архитектурная развилка. Код не изменён. Общий no-op запрет касается нового state, а не history с assigned ref; Lifecycle no-op history — owning правило Lifecycle. Исторические OPEN ниже superseded только в указанном объёме.

Синхронизация 2026-11-21: принятый trace source reads → all validations → remaining bases → apply/immediate receipt checks отражён в docs/tz_world_snapshot.md. Lifecycle-specific synthetic scope и обязанности добавлены в §8; это не пересмотр общих C1/C2/H2 и не code-go.

2026-11-19. Пользователь принял предложение и поручил закрепить его, расписать план, затем отдельно проверить противоречия. Архитектура C2 ACCEPTED; код не начат. Это документальная детализация, не разрешение обходить Snapshot ARCH-0 или открытые gates ниже.

Источники: [C2](section-codec-receipt-contract.md), [Snapshot ARCH-0](world-domain-patches-snapshots.md), docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок», existing SectionApplyReceipt, SnapshotMetadataBuilder и receiptProvenance. Применяется implement-plan перед кодом. При расхождении с ТЗ зависимый код не начинается; ТЗ не исправляется попутно.

## 1. Scope и принятая граница

Snapshot проверяет каждый successful receipt относительно входной секции до добавления в accumulator, metadata/handoff и следующего handler. changed — допустимое подмножество полных входных PatchRef. Пустое changed само по себе не ошибка; new-state/no-op ограничения сохраняются. Time-specific equality/ordinal/cardinality здесь нет.

Invalid receipt — execution contract fault, не SectionRefused/business refusal. Прекратить зависимое исполнение, откатить общую transaction. Unknown outcome не маскируется; COMMITTED и terminal refusal ради receipt fault не создаются.

Не входят: C1 codec/registry split (отдельный чат 01a1f4da-ecd0-74e1-89a1-fedb93bf26f8), DAG, production union, Time payload, новый public apply lifecycle, SQL/DDL, gameplay start, artifacts policy. Публичные interfaces C1 не менять из этого среза. Перед кодом повторить inventory shared файлов и убедиться, что C1 не меняет используемые declarations одновременно.

## 2. Методы и ответственность

**Детализация 2026-11-21 после архитектурного ревью:** global adapter и missing-base preconditions определены в snapshot-receipt-facts-diagnostics.md §3. Единая representation bases для validator/service/builder — `Mapping[SnapshotRef, SnapshotEnvelope]`, ключи — exact pinned refs. Это заменяет tuple bases и raw-receipt global helper в старых предложениях.

Все пути относительно backend/app. TARGET signatures ниже задают предложение реализации принятого поведения; незакрытые детали явно перечислены в §6.

| Класс/модуль | Метод / ответственность / зависимости | Приёмка и отказ |
|---|---|---|
| SnapshotReceiptValidator — application/worldSnapshot/validation/snapshotReceiptValidator.py, новый | `validate[S: DomainSection](self, section: S, receipt: SectionApplyReceipt, context: SnapshotApplyContext, bases: Mapping[SnapshotRef, SnapshotEnvelope], *, section_index: int) -> None`. Pure проверка контракта successful результата; owning models, shared provenance helper и локальный collector | Exact membership, section association, provenance; нет IO/codec/handler/commit, sorting входа или Time-specific rules. Нарушение → SnapshotReceiptContractError; section_index проходит отдельный strict nonnegative admission по R2 |
| SectionApplyReceipt — dataModel/patch/results/sectionResult.py, existing | Existing model validation отвечает за uniqueness, section ownership вложенных refs и changed | Revalidate, не копировать predicates. Malformed экземпляр не использовать как trusted input dependent checks |
| SnapshotMetadataBuilder — application/worldSnapshot/service/snapshotMetadataBuilder.py, existing | build строит metadata из context/receipts/pinned bases; per-receipt provenance делегирует единому helper | Нет второй реализации перенесённых predicates; сохраняются independent diagnostics и итоговая проверка envelope |
| receiptProvenance.py — application/worldSnapshot/validation/, existing модуль функций | Pure `collect_receipt_provenance(facts:ReceiptFacts, context:SnapshotApplyContext, bases:Mapping[SnapshotRef,SnapshotEnvelope]) -> tuple[SnapshotMetadataRelationIssue,...]`; exact owner/base adapter по facts-плану §3. Existing validate_receipt_provenance сохраняет signature и итоговую envelope/base consistency | Один источник predicates; no IO и no fake context для final. section_index из facts без перенумерации; base_available=False не подменяет отсутствие parent |
| WorldSnapshotService — application/worldSnapshot/service/worldSnapshotService.py, existing | _load_pinned_bases читает remaining metadata с reuse; _apply_to_target вызывает validator сразу после success apply; _append_metadata строит/пишет metadata из переданных bases. Exact signatures в §4.1 | Нет повторного base read на metadata-этапе, append receipt/следующего handler после fault. Порядок CAS/handoff/terminal не меняется |
| ISnapshotHistoryStore / SqliteSnapshotHistoryStore — existing history ports/adapters | Exact чтение metadata базы в caller transaction; append проверяет итоговую provenance | Без competing transaction и domain payload reads; не переносят receipt membership в SQL |
| ValidatorAggregationHelper — dataModel/validation/diagnostics/validatorAggregationHelper.py, existing | Request-local collector с exact admitted classes | Независимые ошибки агрегируются, mutable shared collector запрещён |
| SnapshotReceiptContractError — application/worldSnapshot/errors.py, новый | Subclass PublicationInfrastructureError; `__init__(diagnostics: tuple[ReceiptContractIssue, ...]) -> None`, строго валидированный непустой tuple | Не наследует SectionRefused, не обрабатывается как _ApplyRefused; cause malformed model failure сохраняется, unknown rollback не перекрывается |

Публичной операции проверки receipt и отдельной ноды нет. Все вызовы выполняются внутри принятой атомарной Snapshot операции. Импорты owning POJO и pure policy не разрешают foreign public calls.

## 3. POJO/errors

**C2-R2 — ACCEPTED пользователем 2026-11-19 («Ок»).** WorldSnapshotService получает section_index через enumerate исходного sections, начиная с нуля, и передаёт его keyword-only аргументом validator-у; тот передаёт индекс provenance helper без изменения. Это индекс входной секции PatchSet, не ordinal patch и не индекс участника world/player. Нумерация принадлежит service, а не validator.

Внутренняя граница строго проверяет int >= 0 с исключением bool, без coercion. Неверный аргумент — ошибка внутреннего вызова, не обвинение handler receipt; exact carrier относится к G3. Нельзя вычислять индекс через поиск равного объекта, len(accumulator), сортировку или постоянный 0. В принятом последовательном apply один successful handler даёт один receipt, поэтому receipts[i] соответствует sections[i]; после отказа продолжения/переиндексации нет. Эта гарантия не разрешает новые filtered/batch callers: они потребовали бы explicit mapping.

Диагностика сохраняет section_index и отдельный вложенный индекс changed/states/history. Existing receipts[i] paths используют переданный section_index; точная упаковка адреса новых relation records остаётся R3/R5 и не объявлена решённой одним параметром. В PatchSet и SectionApplyReceipt новых public полей нет. Приёмка: нарушение во второй/третьей секции сохраняет исходный индекс, вложенные индексы не смешиваются, bool/negative отвергаются; проверяется отсутствие вычисления номера внутри validator.

Новый модуль dataModel/worldSnapshot/diagnostics/receiptContract.py, owner Snapshot:

| Тип | Точные поля | Смысл и проверка |
|---|---|---|
| ReceiptSectionMismatch | section_index:Annotated[StrictInt,Field(ge=0)]; expected_section_key:SectionKey; actual_section_key:SectionKey | Ключи различаются; original input section index, bool запрещён. Frozen/strict/extra-forbid/revalidate-always; нет IO |
| ReceiptChangedPatchNotInInput | section_index:Annotated[StrictInt,Field(ge=0)]; section_key:SectionKey; changed_index:Annotated[StrictInt,Field(ge=0)]; patch_ref:PatchRef | Полный ref отсутствует во входе; section/nested indices различаются, bool/negative запрещены; членство проверяет validator |
| ReceiptContractIssue | alias: ReceiptSectionMismatch \| ReceiptChangedPatchNotInInput \| SnapshotMetadataFieldIssue \| SnapshotMetadataRelationIssue | Alias не новый envelope; exact admitted classes, не произвольный FieldPathError/BaseModel |

Existing metadata issues переиспользуются для прежних malformed/provenance причин; поля/code semantics не дублируются. Новые records описывают сравнение с input section. Уточнение R5: FOREIGN_OPERATION сохраняется независимо от input membership; прежнее предложение подавления отозвано. Точный early/builder/final порядок и carriers заданы в snapshot-receipt-facts-diagnostics.md, PROPOSED для приёмки.

SectionStateRetention/SectionHistoryRetention, SnapshotEnvelope, SnapshotApplyContext и PatchRef используются без зеркал. Context с capability остаётся application-only. Новый public admission fault/enum не создаётся. Persisted terminal/canonical IDs этих новых diagnostics не назначаются: contract fault не terminal result. Если внешнему transport нужны новые поля, это отдельная согласуемая дельта.

Malformed receipt: использовать existing strict model validation/структурную диагностику, не писать новый decoder. Для неверного root без известного поля не создавать фиктивный FieldPath. Exact root issue и перенос структурных locations остаются gate §6; поэтому union выше ещё не объявлен полным для всех unchecked inputs.

## 4. Перенос predicates и доступность данных

| Existing место | Целевая ответственность |
|---|---|
| SectionApplyReceipt validators | Сохраняются: uniqueness/локальная section coherence; повторный алгоритм не добавляется |
| _apply_to_target: outcome.section_key check | Переносится в SnapshotReceiptValidator как typed ReceiptSectionMismatch |
| Нет existing exact changed membership | Добавляется только в SnapshotReceiptValidator; сравнение полного PatchRef, не только operation/section |
| SnapshotMetadataBuilder: FOREIGN_HISTORY, NOOP_STATE, SUPERSEDED_STATE, UNREACHABLE_STATE | Извлекаются в collect_receipt_provenance; builder и early validator используют один helper. Сохраняются assigned target, pinned owner и полное равенство inherited retention entry |
| Builder: context/base consistency, duplicate receipts, построение metadata | Остаются у builder/owning base checks; не входят в семантику одного receipt |
| validate_receipt_provenance: envelope ↔ receipts ↔ base | Остаётся итоговой проверкой; пересекающиеся per-receipt правила делегируются общему helper после explicit signature/inputs review, не копируются |

**C2-R1 — уточнение H3 ACCEPTED пользователем 2026-11-20 («Делай» после рекомендации поправки порядка).** После expected-context checks в общей transaction Snapshot разрешает необходимые привязки принятого состояния секций до handler.validate. Прочитанная для этого exact metadata сохраняется только в текущей попытке. После успешной validation всех секций, до первого handler.apply, Snapshot дочитывает остальные exact pinned bases; уже прочитанные metadata переиспользуются без повторных reads. Полный набор передаётся receipt validator и metadata builder. Новая transaction/connection и отдельная persisted publication→source projection не вводятся. Это узкая поправка к варианту А от 2026-11-19; exact DTO/resolver/error mapping остаются предметом детализации H3, не объявляются принятыми автоматически.

Порядок полного набора баз: world expected snapshot_head, затем expected_players в их принятом порядке; None head не требует чтения snapshot metadata и не является missing base. При sections=() необходимые базы всё равно читаются для наследования metadata. Refused handler.validate прекращает зависимый путь до дочитывания остальных C2 bases, но необходимая source metadata к этому моменту могла быть прочитана. Source infrastructure fault может опередить semantic refusal; вымышленные последующие diagnostics не формируются. Terminal replay не входит в эту фазу и не читает targets/bases заново. Ранняя metadata задаёт адрес состояния, но не доказывает наличие/валидность доменного payload; его читает и проверяет owning домен.

Missing/corrupt persisted base — infrastructure fault до любых handler.apply, не invalid receipt и не business refusal. Принята поведенческая дельта: прежнее обнаружение на metadata-этапе переносится раньше apply. При одновременной потенциальной ошибке handler.apply/receipt она не исследуется: apply не вызывается, вымышленные diagnostics не формируются. Unknown outcome/rollback не маскируется. Exact aggregation нескольких missing bases и carrier/detail mapping уточняются в R3/R5, без возврата к выбору момента чтения.

Решение фиксирует owner/момент reads и изменение приоритета фаз. Exact методы service, representation bases и caller mapping теперь заданы в §4.1; прежний OPEN об отсутствии детализации C2-G1 снят. Принятый порядок уже отражён в docs/tz_world_snapshot.md; новые internal signatures его не меняют. Validator остаётся pure; откладывать required receipt provenance до metadata запрещено.

### 4.1. C2-G1: internal service signatures и caller mapping

Детализация принятой фазы, не новый public apply lifecycle. Все методы принадлежат existing WorldSnapshotService; IO только через self._history с supplied scope. SnapshotMetadataBuilder.build сохраняет existing Mapping параметр. Обязательные keyword-only bases не имеют default и не восстанавливаются из receipts.

```python
async def _load_pinned_bases(
    self, validation: SnapshotValidationContext, *, scope: CommitReadScope,
    source_bases: Mapping[SnapshotRef, SnapshotEnvelope],
) -> Mapping[SnapshotRef, SnapshotEnvelope]: ...

@asynccontextmanager
async def _apply_to_target(
    self, scope: CommitScope, validation: SnapshotValidationContext,
    sections: tuple[DomainSection, ...], snapshot: WorldSnapshotRef,
    players: tuple[PlayerSnapshotRef, ...], *,
    bases: Mapping[SnapshotRef, SnapshotEnvelope],
) -> AsyncIterator[tuple[SnapshotApplyContext, tuple[SectionApplyReceipt, ...]]]: ...

async def _append_metadata(
    self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
    receipts: tuple[SectionApplyReceipt, ...], *,
    bases: Mapping[SnapshotRef, SnapshotEnvelope],
) -> None: ...

async def _append_metadata_and_handoff(
    self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
    receipts: tuple[SectionApplyReceipt, ...], *,
    bases: Mapping[SnapshotRef, SnapshotEnvelope], holders: IArtifactHolders,
    lease: OperationLeaseRef, transferred: tuple[ArtifactRef, ...],
) -> None: ...
```

`source_bases` — metadata, уже прочитанная owning Snapshot source-resolution фазой в текущем attempt/read scope. Это internal caller-owned cache, не input DAG/handler и не глобальный cache. Loader берёт только exact pinned refs из validation: world, затем expected_players в исходном порядке; None пропускает, одинаковый ref читает один раз. Непривязанные к pinned set entries source-cache не попадают в result. Result — read-only MappingProxyType над новой private dict; исходный mutable cache не публикуется. Не создаются новый wire POJO/base store/source resolver.

При каждом access loader проверяет scope.assert_active(). Для cached entry проверяет strict SnapshotEnvelope admission и exact envelope.ref==requested ref; неверный cache не исправляется повторным read. Для отсутствующего cached ref вызывает self._history.read(ref,scope=scope), строго проверяет полученный envelope/ref и сохраняет результат. IO/decoded corruption/identity mismatch → PublicationInfrastructureError с cause; cancellation распространяется, последующие фиктивные ошибки не вычисляются. None result собирается как existing MissingPersistedSnapshotBase(snapshot=ref,player_index=None|original_player_index); независимые missing refs собираются в world/player порядке через ValidatorAggregationHelper((MissingPersistedSnapshotBase,)), затем raise_if_any(PublicationInfrastructureError) до apply. При IO failure дальнейшая агрегация прекращается. Новые error enums не нужны.

Полная карта передаётся одному call chain как тот же immutable object: caller после успешных всех validates вызывает loader → _apply_to_target(...,bases=bases) → каждый SnapshotReceiptValidator.validate(...,bases,section_index=i) → в yielded body _append_metadata[_and_handoff](...,bases=bases) → SnapshotMetadataBuilder.build(...,bases). _append_metadata больше не вызывает self._history.read, не собирает MissingPersistedSnapshotBase после writes и не имеет fallback загрузки баз. Только build → history.append каждого envelope. Store.append может выполнять собственные defensive provenance reads по своему existing storage contract; они не являются повторным service lookup и не удаляются этим срезом.

Loader гарантирует complete bases до первого apply. Pure consumers продолжают защищать standalone calls: context/base prerequisites проверяет caller validator/builder, а shared global adapter использует только доступные bases и не фабрикует dependent errors. Для early validator missing/invalid supplied bases — внутренний PublicationInfrastructureError до receipt admission, не SnapshotReceiptContractError против handler. Wrong section_index type/bool → TypeError, negative → ValueError до проверки receipt. На штатном service пути эти failures невозможны после корректного loader; негативные harness tests обязаны их обнаруживать. _apply_to_target перед первым handler (включая empty sections) проверяет completeness/exact identity passed bases по тем же pure base-admission правилам consumers; не открывает IO.

Actual callers по inventory: production вызовы _append_metadata_and_handoff→_append_metadata; остальные прямые callers _apply_to_target/_append_metadata — tests/snapshotCore/storage/publication/test_atomicity.py. При I2 эти callers передают bases явно и перестают рассчитывать на metadata-stage lookup. Test harness выполняет existing validate phase, затем loader, затем _apply_to_target; негативные direct-call тесты задают invalid bases явно. Нельзя добавить новый public apply orchestration ради подключения helper или читать remaining bases внутри каждого handler. Будущий full service caller использует тот же seam, но его создание вне C2.

Критерии по методам: loader читает только metadata и ровно недостающие pinned refs; validator/adapter не читают storage; _apply_to_target не накапливает receipt до успешной проверки; _append_metadata не перечитывает service bases; _append_metadata_and_handoff лишь передаёт тот же bases и сохраняет handoff после append. Tests: source cache reuse, missing/corrupt base → zero apply, None heads, empty sections, original player indices, no metadata-stage service reads, second receipt fault → no next handler/handoff/CAS и rollback. Final store checker сохраняет прежние first-error фазы.

Pure base-admission условия (pinned keys, envelope identity, missing/extra entries) переиспользуются validator/builder/service guard через один internal helper `collect_pinned_base_issues(validation:SnapshotValidationContext,bases:Mapping[SnapshotRef,SnapshotEnvelope])->tuple[SnapshotMetadataRelationIssue,...]` в receiptProvenance.py. Он не делает IO, не проверяет receipts/assigned targets и не заменяет strict storage envelope admission loader. Порядок: missing/identity по world→players, затем extra mapping keys в их исходном порядке; existing MISSING_BASE/BASE_IDENTITY/UNEXPECTED_BASE codes/paths сохраняются. Builder включает результат в прежнюю предварительную фазу; early/service guard при непустом tuple поднимают PublicationInfrastructureError. Global receipt adapter только выбирает доступность base, не повторяет выдачу этих issues. Assigned-target/players/self-parent checks остаются у owning context caller, а не переносятся в base helper.

## 5. Целевой trace и evidence

Сохраняются admission → fingerprint → binding/replay → outer transaction → expected heads/context checks. По принятой поправке H3 от 2026-11-20 далее Snapshot разрешает необходимые section sources с чтением exact source metadata и сохранением её в текущей попытке → handler.validate всех секций → дочитывание остальных exact pinned bases до первого apply. Ранее прочитанные metadata переиспользуются; failure исключает любые handler.apply. Точная предлагаемая граница resolver/context: [H3 binding](snapshot-time-source-binding-h3.md). Затем:

1. handler.apply(section, context).
2. SectionRefused — existing business rollback path; не receipt validation.
3. Successful receipt → строгая модель → section association → changed membership в порядке changed → history → states/provenance. Независимые причины собираются; branch с malformed предусловием пропускается, остальные доступны для проверки.
4. Только после успеха receipt добавляется в accumulator, затем следующий handler.
5. Existing metadata/handoff/world CAS/player CAS/terminal/commit в принятом порядке.

Fault выходит из outer transaction; подтверждённый rollback сохраняет execution fault. Нет record_refusal и публичного COMMITTED. Unknown rollback имеет приоритет. Exact public transport определён в §6.1; его подключение к полному public apply ещё требует runtime evidence.

Проверки: чужой ordinal при том же operation/section; допустимое подмножество и пустой no-op; неправильный section/target; изменённый inherited closure; несколько независимых faults с исходными индексами; malformed known field и wrong root; нет следующего handler/metadata/handoff/CAS после fault; writes предыдущего handler откачены (два соединения); missing base не переименован в invalid receipt; existing metadata/provenance regression. Для варианта А с принятой поправкой H3: source metadata reads идут после expected-context checks до validations; остальные base reads — после всех успешных validations до первого apply; missing/corrupt source или base → ноль apply; validation refusal → нет дочитывания остальных bases, ранние source reads допустимы; None head → нет snapshot metadata lookup (publication-bound payload читает домен); пустой sections сохраняет чтение необходимых родителей; metadata reuse не делает повторных lookups; terminal replay не читает sources/bases. Отдельно проверить отсутствие копий predicates и неизменность C1 interfaces.

## 6. Gates и поставка

Актуализация 2026-11-25 по actual code и ограниченному повторному ревью 2026-11-22; прежние preimplementation статусы заменены следующими:

- C2-G1: internal signatures, immutable bases и caller mapping реализованы; ограниченное service wiring проверено synthetic transaction harness. Полный public apply этим не принят.
- C2-G2: реализован общий механизм ReceiptFactsAdmission + receiptProvenance.py, подключён к early validator, SnapshotMetadataBuilder и final validate_receipt_provenance. Extraction/order контракт — snapshot-receipt-facts-diagnostics.md; локальное исправление принято повторным ревью 2026-11-22. Новый параллельный validator не нужен.
- C2-G3: exact roster/root/cause и public mapping зафиксированы в §6.1. Внутренний carrier реализован; подключение и проверка public apply exception boundary остаются задачей реализации Snapshot, не новым выбором диагностики и не зависимостью от production-доменов.
- C2-G4: синхронизация с owning ТЗ после проверки расхождений; inventory shared файлов после C1.

Порядок поставки после gates и разрешения кода: C2-I1 — единый pure provenance helper/typed errors/validator плюс адресные tests и миграция existing pure consumers; C2-I2 — service wiring с доступными bases, regression rollback/call-order и полный затронутый Snapshot test scope. I1 не означает выполненный runtime C2. I2 не начинает новый public apply lifecycle.

Для каждого класса/метода/POJO отчёт: exact declaration, imports/nested calls/effects, проверка, PASS/OPEN/FAIL. Любой пропуск или нарушение исключает приёмку. Before code — полный текущий inventory, implement-plan, SoT и diff; без сервера/commit/push. Gate общего Snapshot ARCH-0 не снят этим документом.

### 6.1. Замкнутый receipt diagnostic route — 2026-11-25

Это детализация existing infrastructure transport из snapshot-public-methods-contract.md §3; состав public fault не расширяется. Ответственность целиком Snapshot, готовых typed inputs и synthetic participants достаточно.

1. ReceiptFactsAdmission.admit(raw, section_index=...) допускает доступные факты, сохраняя original indices и structural order. Malformed root/неразрешимый loc → existing SnapshotMetadataRelationIssue(code=INVALID_RECEIPT, location="receipts", address=(section_index,*loc)); при пустом loc address=(section_index,). Объявленное поле → SnapshotMetadataFieldIssue с CheckedPath и destination=(section_index,). Не создаются fictitious field path, fake receipt или пустая валидная retention вместо недопущенной.
2. Единственный ReceiptContractIssue roster: ReceiptSectionMismatch | ReceiptChangedPatchNotInInput | SnapshotMetadataFieldIssue | SnapshotMetadataRelationIssue (dataModel/worldSnapshot/diagnostics/receiptContract.py и metadata/metadataIssues.py). Первые два сохраняют section_index и exact operands; membership дополнительно changed_index/patch_ref. Порядок: structural → association → membership → FOREIGN_OPERATION → history → states, с исходными индексами. Общие predicates принадлежат receiptProvenance.py; caller-specific association/membership — SnapshotReceiptValidator, final envelope coverage — final checker. Final first-error фазы не заменяются порядком early aggregation.
3. SnapshotReceiptValidator.validate(...) → None либо SnapshotReceiptContractError(diagnostics: tuple[ReceiptContractIssue,...]); tuple непустой и строго проверяется. Existing ValidatorAggregationHelper агрегирует независимые причины. Malformed model сохраняет ValidationError в __cause__; неверный internal section_index/base не обвиняет handler и остаётся отдельным internal prerequisite failure по §4.1.
4. Service вызывает validator немедленно после successful receipt, до accumulator/следующего handler. Receipt fault выходит за transaction context. После подтверждённого rollback public apply переводит его как PublicationInfrastructureError в SnapshotPublicError(fault=SnapshotPublicFault(operation=APPLY, kind=INFRASTRUCTURE_FAILURE, operation_id=checked.operation_id, request_fingerprint=checked_hash, input_issues=())) **from исходный SnapshotReceiptContractError**. Непустой typed diagnostics tuple доступен в исходном exception cause без пересборки/переиндексации. Это runtime exception transport; сериализованный public fault не обещает содержать receipt diagnostics. Не помещать их в admission input_issues и не создавать новый wire carrier.
5. Если cleanup/commit даёт UnknownCommitOutcome, внешний catch ПОСЛЕ выхода transaction выбирает OUTCOME_UNKNOWN с тем же checked binding, input_issues=() и cause=исходный UnknownCommitOutcome. Он не подменяется ранним receipt fault или CONFLICT; existing exception chain сохраняется, diagnostics не копируются в unknown DTO. Invocation cancellation остаётся отдельным cancellation path. Никакого record_refusal, business T или подтверждения commit по receipt fault.

Критерий закрытия runtime G3: synthetic первый handler пишет, второй возвращает чужой PatchRef, третий не вызывается; outer public exception имеет указанный kind/binding и typed cause с exact section/changed indices; второе соединение подтверждает rollback marker writes, metadata/handoff/CAS/terminal не вызываются. Отдельно malformed root сохраняет ValidationError cause, несколько независимых diagnostics сохраняют порядок, rollback failure даёт OUTCOME_UNKNOWN с UnknownCommitOutcome cause. Проверка только конструирования SnapshotPublicFault не заменяет вызов public apply. Existing test_receipt_facts.py/test_attempt_transaction.py покрывают внутренние части; полного public метода пока нет, этот runtime критерий не объявлен выполненным.

## 7. Статус отдельной проверки противоречий

Отдельный review выполнен: [C2-R1…R5](snapshot-receipt-validation-c2-review.md). R1 закрыт выбором owner/фазы/приоритета ошибок; R2 — источником section_index. R3–R5 конкретизированы и реализованы по snapshot-receipt-facts-diagnostics.md. Прежний общий OPEN extraction/root/aggregation устарел. Остаток G3 — фактическое подключение описанного transport к public apply и сквозная проверка; локальный PASS не означает общий runtime/ARCH-0 PASS.

## 8. Lifecycle synthetic integration — 2026-11-21

**D1–D7 ACCEPTED, синхронизация 2026-11-21:** suite использует отдельную fixture `mock_lifecycle_world` («mock-мир Lifecycle»), typed A/B facts, started world/один timeline только test profile. Fixture создаётся при разрешённой реализации, production world не создаётся. Prepared без header, singleton Create/End/Reactivate и многосоставной Replacement, explicit many-to-many coverage, запрет NoDomainMutation local v1, Reactivate после End/отказ после Replacement — owning Lifecycle assertions. Перестановка участников каждой стороны Replacement сохраняет semantic retry equality, но не отменяет Publication exact fingerprint и не меняет порядок patches/ordinal. C2 не реализует эти predicates; проверяет общий receipt/provenance/atomic rollback. D1–D7 не gates повторного пользовательского выбора; exact schemas/регистрации/participant binding ещё требуют технической сверки.

Уточнение source review 2026-11-21: [R4 extraction](snapshot-provenance-extraction-r4.md). Inherited retention в receipt допускается для state, не history. History всегда адресует assigned snapshot; для Lifecycle exact duplicate/no-op history=(), changed=(), states=() либо exact inherited state. Общий C2 не вводит правила history-count == changed-count; отсутствие новой history при Lifecycle повторе обеспечивает Lifecycle. Прежние обобщённые формулировки «inherited entries» этого раздела не разрешают inherited history.

PROPOSED локальный evidence-срез по [Lifecycle atomic boundary](snapshot-lifecycle-atomic-boundary.md), не новая реализация validator и не общий code-go. Порядок поставки C2-I1 → C2-I2 сохраняется: pure receipt assertions входят в evidence I1, fake transaction/service call-order/rollback — в I2. Это можно проверить без real domains/SQL/DDL/producers/checkpoint. Exact local Lifecycle capture/evidence/closed types/idempotence по owning контракту обязательны, отсутствие OUT не blocker.

### Receipt obligations

| Сценарий | Lifecycle обязанность | Snapshot C2 обязанность |
|---|---|---|
| 100 independent Creates | 100 native patches и при первом successful apply 100 history operations; projections по typed участникам | Полные changed refs принадлежат исходным patches, правильные section/assigned refs и retention provenance; НЕ требовать 100 SectionHistoryRef |
| Один Replacement со 100 участниками | Один native patch/одна history operation; projections по участникам | Не выводить число patches/history operations из числа участников или retention entries |
| Mixed synthetic A/B | Сохранить concrete typed inputs и входной порядок; не пересекать участников | Generic receipt validator не ветвится по виду сущности |
| Same change_uid/same semantics | Lifecycle подтверждает повтор по complete accepted history; нет второй history operation, выдаёт owning changed/retention outcome | Проверить subset membership и exact inherited entries; не сравнивать semantic payload/change_uid самостоятельно |
| Same change_uid/different semantics | Typed Lifecycle conflict, не успешный receipt | Общий rollback/business path без receipt validation refused output |
| Empty/partial changed | Lifecycle доказывает соответствующий no-op/частично новые transitions по своему контракту | Не требовать equality changed=input; empty changed запрещает новый state; history проверяется по assigned ref независимо от changed; inherited state closure должен совпадать |

SectionHistoryRef адресует retained section history, который может быть bundle; его cardinality не равна cardinality history operations. C2 проверяет metadata/provenance, но не читает внутренние Lifecycle rows ради пересчёта операций. History-count assertions относятся к owning fake Lifecycle store. LifecycleAppendResult/no-op retention exact mapping остаётся local contract owner, а не новая Snapshot policy.

### Synthetic evidence I1 / I2

I1: valid bundled history receipt; один full PatchRef вне входа; чужой section/assigned target; изменение inherited retention; empty changed с недопустимым новым state. Отдельный положительный общий случай — empty changed с history на assigned ref; запрет такой history для Lifecycle exact повторения проверяется owning Lifecycle тестом. Проверяются исходный section_index и независимые diagnostics по общему C2 контракту. Без копирования predicates в Lifecycle или новых fake-specific validator branches.

I2: fake transaction owner удерживает immutable accepted baseline Q и отдельный staged workspace для Lifecycle и второго synthetic participant. Отдельный namespace writer каждого участника не может писать чужие данные или самостоятельно commit/rollback. Проверить: отказ второго handler после writes первого; invalid receipt до следующего handler; CAS conflict; complete rollback всех namespaces; успешный один commit; lost acknowledgement при физическом commit и при отсутствии commit → unknown без ложного rollback. Exact operation replay не вызывает handlers/source reads. Cancellation требует drain перед revoke; expired capability отвергается. Никакого автоматического деления 100 переходов на commits.

Fake participant — test implementation узкого owning persistence protocol. Регистрация/DI сами по себе не разрешают foreign public pipeline или writer; permitted nested chain задаётся atomic-boundary планом. Snapshot-owned generic checks и Lifecycle semantic checks проверяются раздельно. Fake evidence не доказывает production SQL durability/cleanup и не называется production readiness.

**Приёмка среза:** Snapshot предъявляет call trace/receipt/fault/rollback assertions; Lifecycle подтверждает complete capture, duplicate semantic comparison и evidence/no-op mapping; PatchSet подтверждает closed native union/output admission. Gate local IN закрывается по этим контрактам и synthetic evidence, не по наличию реальных NPC/producer/adapters. Полный C2 остаётся OPEN по ранее указанным G1–G4; новый срез не переоткрывает принятый H3 Time и не объявляет его универсальным Lifecycle binding.
