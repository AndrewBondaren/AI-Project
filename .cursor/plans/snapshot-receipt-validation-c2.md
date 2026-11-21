# Snapshot C2: проверка результата применения секции

**Уточнение R3/R4/R5 после повторного ревью, 2026-11-21:** [точный контракт admitted facts и диагностики](snapshot-receipt-facts-diagnostics.md) заменяет прежние недетализированные предложения fully-valid-only extraction и подавления FOREIGN_OPERATION. Это PROPOSED для приёмки, не код. Общий no-op запрет касается нового state, а не history с assigned ref; Lifecycle no-op history — owning правило Lifecycle.

Синхронизация 2026-11-21: принятый trace source reads → all validations → remaining bases → apply/immediate receipt checks отражён в docs/tz_world_snapshot.md. Lifecycle-specific synthetic scope и обязанности добавлены в §8; это не пересмотр общих C1/C2/H2 и не code-go.

2026-11-19. Пользователь принял предложение и поручил закрепить его, расписать план, затем отдельно проверить противоречия. Архитектура C2 ACCEPTED; код не начат. Это документальная детализация, не разрешение обходить Snapshot ARCH-0 или открытые gates ниже.

Источники: [C2](section-codec-receipt-contract.md), [Snapshot ARCH-0](world-domain-patches-snapshots.md), docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок», existing SectionApplyReceipt, SnapshotMetadataBuilder и receiptProvenance. Применяется implement-plan перед кодом. При расхождении с ТЗ зависимый код не начинается; ТЗ не исправляется попутно.

## 1. Scope и принятая граница

Snapshot проверяет каждый successful receipt относительно входной секции до добавления в accumulator, metadata/handoff и следующего handler. changed — допустимое подмножество полных входных PatchRef. Пустое changed само по себе не ошибка; new-state/no-op ограничения сохраняются. Time-specific equality/ordinal/cardinality здесь нет.

Invalid receipt — execution contract fault, не SectionRefused/business refusal. Прекратить зависимое исполнение, откатить общую transaction. Unknown outcome не маскируется; COMMITTED и terminal refusal ради receipt fault не создаются.

Не входят: C1 codec/registry split (отдельный чат 01a1f4da-ecd0-74e1-89a1-fedb93bf26f8), DAG, production union, Time payload, новый public apply lifecycle, SQL/DDL, gameplay start, artifacts policy. Публичные interfaces C1 не менять из этого среза. Перед кодом повторить inventory shared файлов и убедиться, что C1 не меняет используемые declarations одновременно.

## 2. Методы и ответственность

Все пути относительно backend/app. TARGET signatures ниже задают предложение реализации принятого поведения; незакрытые детали явно перечислены в §6.

| Класс/модуль | Метод / ответственность / зависимости | Приёмка и отказ |
|---|---|---|
| SnapshotReceiptValidator — application/worldSnapshot/validation/snapshotReceiptValidator.py, новый | `validate[S: DomainSection](self, section: S, receipt: SectionApplyReceipt, context: SnapshotApplyContext, bases: tuple[SnapshotEnvelope, ...], *, section_index: int) -> None`. Pure проверка контракта successful результата; owning models, shared provenance helper и локальный collector | Exact membership, section association, provenance; нет IO/codec/handler/commit, sorting входа или Time-specific rules. Нарушение → SnapshotReceiptContractError; section_index проходит отдельный strict nonnegative admission по R2 |
| SectionApplyReceipt — dataModel/patch/results/sectionResult.py, existing | Existing model validation отвечает за uniqueness, section ownership вложенных refs и changed | Revalidate, не копировать predicates. Malformed экземпляр не использовать как trusted input dependent checks |
| SnapshotMetadataBuilder — application/worldSnapshot/service/snapshotMetadataBuilder.py, existing | build строит metadata из context/receipts/pinned bases; per-receipt provenance делегирует единому helper | Нет второй реализации перенесённых predicates; сохраняются independent diagnostics и итоговая проверка envelope |
| receiptProvenance.py — application/worldSnapshot/validation/, existing модуль функций | Выделить pure `collect_receipt_provenance(receipt: SectionApplyReceipt, context: SnapshotApplyContext, bases: tuple[SnapshotEnvelope, ...], *, section_index: int) -> tuple[SnapshotMetadataRelationIssue, ...]`. Existing validate_receipt_provenance(metadata, receipts, base, operation_id) сохраняет итоговую envelope/base consistency | Один источник per-receipt predicates. Не копировать их в итоговую проверку. Exact extraction и адреса до кода сверить по §4; section_index передаётся без перенумерации, bool запрещён |
| WorldSnapshotService — application/worldSnapshot/service/worldSnapshotService.py, existing | _apply_to_target вызывает validator сразу после успешного handler.apply; SectionRefused идёт прежним путём. Service поставляет pinned bases, не validator | Нет append receipt/следующего handler/metadata после fault. Порядок CAS/handoff/terminal не меняется. Exact internal signature delta для передачи bases остаётся gate §6 |
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

Решение фиксирует owner/момент reads и изменение приоритета фаз. Exact helper/метод service, representation bases и передача в existing callers ещё требуют внутренней детализации C2-G1; это не повторное согласование варианта А. До кода требуется синхронизация owning ТЗ. Validator остаётся pure; откладывать required receipt provenance до metadata запрещено.

## 5. Целевой trace и evidence

Сохраняются admission → fingerprint → binding/replay → outer transaction → expected heads/context checks. По принятой поправке H3 от 2026-11-20 далее Snapshot разрешает необходимые section sources с чтением exact source metadata и сохранением её в текущей попытке → handler.validate всех секций → дочитывание остальных exact pinned bases до первого apply. Ранее прочитанные metadata переиспользуются; failure исключает любые handler.apply. Точная предлагаемая граница resolver/context: [H3 binding](snapshot-time-source-binding-h3.md). Затем:

1. handler.apply(section, context).
2. SectionRefused — existing business rollback path; не receipt validation.
3. Successful receipt → строгая модель → section association → changed membership в порядке changed → history → states/provenance. Независимые причины собираются; branch с malformed предусловием пропускается, остальные доступны для проверки.
4. Только после успеха receipt добавляется в accumulator, затем следующий handler.
5. Existing metadata/handoff/world CAS/player CAS/terminal/commit в принятом порядке.

Fault выходит из outer transaction; подтверждённый rollback сохраняет execution fault. Нет record_refusal и публичного COMMITTED. Unknown rollback имеет приоритет; public transport ещё OPEN.

Проверки: чужой ordinal при том же operation/section; допустимое подмножество и пустой no-op; неправильный section/target; изменённый inherited closure; несколько независимых faults с исходными индексами; malformed known field и wrong root; нет следующего handler/metadata/handoff/CAS после fault; writes предыдущего handler откачены (два соединения); missing base не переименован в invalid receipt; existing metadata/provenance regression. Для варианта А с принятой поправкой H3: source metadata reads идут после expected-context checks до validations; остальные base reads — после всех успешных validations до первого apply; missing/corrupt source или base → ноль apply; validation refusal → нет дочитывания остальных bases, ранние source reads допустимы; None head → нет snapshot metadata lookup (publication-bound payload читает домен); пустой sections сохраняет чтение необходимых родителей; metadata reuse не делает повторных lookups; terminal replay не читает sources/bases. Отдельно проверить отсутствие копий predicates и неизменность C1 interfaces.

## 6. Gates и поставка

До реализации OPEN:

- C2-G1: internal helper/signature/caller delta для принятого варианта А. Owner/фаза/приоритет missing-base приняты; runtime evidence ещё отсутствует.
- C2-G2: extraction map каждого existing predicate, shared helper inputs и итоговая envelope validation без дублей; stable diagnostic order/address и совместимость existing aggregation.
- C2-G3: malformed root carrier, exact typed diagnostic roster, boundary transport и приоритет unknown rollback. Новые публичные поля не вводятся предположением.
- C2-G4: синхронизация с owning ТЗ после проверки расхождений; inventory shared файлов после C1.

Порядок поставки после gates и разрешения кода: C2-I1 — единый pure provenance helper/typed errors/validator плюс адресные tests и миграция existing pure consumers; C2-I2 — service wiring с доступными bases, regression rollback/call-order и полный затронутый Snapshot test scope. I1 не означает выполненный runtime C2. I2 не начинает новый public apply lifecycle.

Для каждого класса/метода/POJO отчёт: exact declaration, imports/nested calls/effects, проверка, PASS/OPEN/FAIL. Любой пропуск или нарушение исключает приёмку. Before code — полный текущий inventory, implement-plan, SoT и diff; без сервера/commit/push. Gate общего Snapshot ARCH-0 не снят этим документом.

## 7. Статус отдельной проверки противоречий

Отдельный review выполнен: [C2-R1…R5](snapshot-receipt-validation-c2-review.md). R1 закрыт на уровне выбора owner/фазы/приоритета ошибок принятием варианта А; R2 закрыт по источнику и передаче section_index. Internal wiring и evidence ещё требуются. Детальный implementation contract OPEN: malformed aggregation, exact extraction map и diagnostic compatibility/упаковка адресов требуют уточнения. Архитектурное согласие не является PASS реализации или всех деталей. Не менять C1 и ТЗ ради устранения найденного расхождения без соответствующего согласования.

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
