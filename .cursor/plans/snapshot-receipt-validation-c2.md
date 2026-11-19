# Snapshot C2: проверка результата применения секции

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
| ReceiptSectionMismatch | expected_section_key:SectionKey; actual_section_key:SectionKey | Ключи различаются; association с входной секцией. Frozen/strict/extra-forbid/revalidate-always; нет IO |
| ReceiptChangedPatchNotInInput | section_key:SectionKey; changed_index:Annotated[StrictInt,Field(ge=0)]; patch_ref:PatchRef | Полный changed ref отсутствует во входе. Индекс — receipt.changed, bool/negative запрещены; членство проверяет validator, не POJO |
| ReceiptContractIssue | alias: ReceiptSectionMismatch \| ReceiptChangedPatchNotInInput \| SnapshotMetadataFieldIssue \| SnapshotMetadataRelationIssue | Alias не новый envelope; exact admitted classes, не произвольный FieldPathError/BaseModel |

Existing metadata issues переиспользуются для прежних malformed/provenance причин; поля/code semantics не дублируются. Новые records описывают сравнение с input section, которого прежняя metadata диагностика не выражала. Existing FOREIGN_OPERATION не требуется дополнительно выдавать за тот же changed ref, если exact membership уже сообщает нарушение; окончательная карта совместимости диагностики — gate §6, не разрешение молча удалить existing reports.

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

**C2-R1, вариант А — ACCEPTED пользователем 2026-11-19 («Ок, давай А»).** AS-IS _append_metadata читает bases после цикла handlers. Целевой путь: после успешной validation всех секций, но до первого handler.apply, WorldSnapshotService один раз читает все exact pinned bases через существующий ISnapshotHistoryStore в read facet той же общей publication transaction. Отдельная transaction/connection не открывается. Один набор прочитанных metadata затем передаётся receipt validator и metadata builder; повторное чтение тех же bases на metadata-этапе не выполняется.

Порядок базы: world expected snapshot_head, затем expected_players в их принятом порядке; None head не требует чтения и не является missing base. При sections=() необходимые базы всё равно читаются для наследования metadata. Refused handler.validate прекращает зависимый путь до этих reads. Terminal replay не входит в эту фазу и не читает targets/bases заново.

Missing/corrupt persisted base — infrastructure fault до любых handler.apply, не invalid receipt и не business refusal. Принята поведенческая дельта: прежнее обнаружение на metadata-этапе переносится раньше apply. При одновременной потенциальной ошибке handler.apply/receipt она не исследуется: apply не вызывается, вымышленные diagnostics не формируются. Unknown outcome/rollback не маскируется. Exact aggregation нескольких missing bases и carrier/detail mapping уточняются в R3/R5, без возврата к выбору момента чтения.

Решение фиксирует owner/момент reads и изменение приоритета фаз. Exact helper/метод service, representation bases и передача в existing callers ещё требуют внутренней детализации C2-G1; это не повторное согласование варианта А. До кода требуется синхронизация owning ТЗ. Validator остаётся pure; откладывать required receipt provenance до metadata запрещено.

## 5. Целевой trace и evidence

Сохраняются admission → fingerprint → binding/replay → outer transaction → expected heads/context checks → handler.validate всех секций. Для новой попытки после успешной validation выполняется принятый вариант А: чтение всех exact pinned bases один раз в этой transaction; failure исключает любые handler.apply. Затем:

1. handler.apply(section, context).
2. SectionRefused — existing business rollback path; не receipt validation.
3. Successful receipt → строгая модель → section association → changed membership в порядке changed → history → states/provenance. Независимые причины собираются; branch с malformed предусловием пропускается, остальные доступны для проверки.
4. Только после успеха receipt добавляется в accumulator, затем следующий handler.
5. Existing metadata/handoff/world CAS/player CAS/terminal/commit в принятом порядке.

Fault выходит из outer transaction; подтверждённый rollback сохраняет execution fault. Нет record_refusal и публичного COMMITTED. Unknown rollback имеет приоритет; public transport ещё OPEN.

Проверки: чужой ordinal при том же operation/section; допустимое подмножество и пустой no-op; неправильный section/target; изменённый inherited closure; несколько независимых faults с исходными индексами; malformed known field и wrong root; нет следующего handler/metadata/handoff/CAS после fault; writes предыдущего handler откачены (два соединения); missing base не переименован в invalid receipt; existing metadata/provenance regression. Для варианта А: reads идут после всех успешных validations и до первого apply; missing/corrupt base → ноль apply; validation refusal → нет base reads; None head → нет lookup; пустой sections сохраняет чтение необходимых родителей; metadata reuse не делает повторных lookups; terminal replay не читает базы. Отдельно проверить отсутствие копий predicates и неизменность C1 interfaces.

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
