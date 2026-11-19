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
| SnapshotReceiptValidator — application/worldSnapshot/validation/snapshotReceiptValidator.py, новый | `validate[S: DomainSection](self, section: S, receipt: SectionApplyReceipt, context: SnapshotApplyContext, bases: tuple[SnapshotEnvelope, ...]) -> None`. Pure проверка контракта successful результата; owning models, shared provenance helper и локальный collector | Exact membership, section association, provenance; нет IO/codec/handler/commit, sorting входа или Time-specific rules. Нарушение → SnapshotReceiptContractError |
| SectionApplyReceipt — dataModel/patch/results/sectionResult.py, existing | Existing model validation отвечает за uniqueness, section ownership вложенных refs и changed | Revalidate, не копировать predicates. Malformed экземпляр не использовать как trusted input dependent checks |
| SnapshotMetadataBuilder — application/worldSnapshot/service/snapshotMetadataBuilder.py, existing | build строит metadata из context/receipts/pinned bases; per-receipt provenance делегирует единому helper | Нет второй реализации перенесённых predicates; сохраняются independent diagnostics и итоговая проверка envelope |
| receiptProvenance.py — application/worldSnapshot/validation/, existing модуль функций | Выделить pure `collect_receipt_provenance(receipt: SectionApplyReceipt, context: SnapshotApplyContext, bases: tuple[SnapshotEnvelope, ...], receipt_index: int) -> tuple[SnapshotMetadataRelationIssue, ...]`. Existing validate_receipt_provenance(metadata, receipts, base, operation_id) сохраняет итоговую envelope/base consistency | Один источник per-receipt predicates. Не копировать их в итоговую проверку. Exact extraction и адреса до кода сверить по §4; receipt_index — original nonnegative index, bool запрещён |
| WorldSnapshotService — application/worldSnapshot/service/worldSnapshotService.py, existing | _apply_to_target вызывает validator сразу после успешного handler.apply; SectionRefused идёт прежним путём. Service поставляет pinned bases, не validator | Нет append receipt/следующего handler/metadata после fault. Порядок CAS/handoff/terminal не меняется. Exact internal signature delta для передачи bases остаётся gate §6 |
| ISnapshotHistoryStore / SqliteSnapshotHistoryStore — existing history ports/adapters | Exact чтение metadata базы в caller transaction; append проверяет итоговую provenance | Без competing transaction и domain payload reads; не переносят receipt membership в SQL |
| ValidatorAggregationHelper — dataModel/validation/diagnostics/validatorAggregationHelper.py, existing | Request-local collector с exact admitted classes | Независимые ошибки агрегируются, mutable shared collector запрещён |
| SnapshotReceiptContractError — application/worldSnapshot/errors.py, новый | Subclass PublicationInfrastructureError; `__init__(diagnostics: tuple[ReceiptContractIssue, ...]) -> None`, строго валидированный непустой tuple | Не наследует SectionRefused, не обрабатывается как _ApplyRefused; cause malformed model failure сохраняется, unknown rollback не перекрывается |

Публичной операции проверки receipt и отдельной ноды нет. Все вызовы выполняются внутри принятой атомарной Snapshot операции. Импорты owning POJO и pure policy не разрешают foreign public calls.

## 3. POJO/errors

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

Критический факт AS-IS: _append_metadata читает bases после цикла handlers. Для C2 полного early provenance этого недостаточно. Предложение: service получает exact pinned metadata внутри той же общей transaction до проверки первого successful receipt и переиспользует её для metadata builder. Validator не получает право читать базу. Missing/corrupt persisted base — infrastructure fault, не invalid receipt.

Точный момент reads, helper/метод service, representation bases и передача в existing callers требуют отдельного утверждения trace до кода. Порядок runtime не меняется одной этой записью. Запрещено скрыто отложить required receipt provenance до metadata и объявить C2 выполненным.

## 5. Целевой trace и evidence

Сохраняются admission → fingerprint → binding/replay → outer transaction и accepted validation stages. Для новой попытки после установления разрешённых context/bases:

1. handler.apply(section, context).
2. SectionRefused — existing business rollback path; не receipt validation.
3. Successful receipt → строгая модель → section association → changed membership в порядке changed → history → states/provenance. Независимые причины собираются; branch с malformed предусловием пропускается, остальные доступны для проверки.
4. Только после успеха receipt добавляется в accumulator, затем следующий handler.
5. Existing metadata/handoff/world CAS/player CAS/terminal/commit в принятом порядке.

Fault выходит из outer transaction; подтверждённый rollback сохраняет execution fault. Нет record_refusal и публичного COMMITTED. Unknown rollback имеет приоритет; public transport ещё OPEN.

Проверки: чужой ordinal при том же operation/section; допустимое подмножество и пустой no-op; неправильный section/target; изменённый inherited closure; несколько независимых faults с исходными индексами; malformed known field и wrong root; нет следующего handler/metadata/handoff/CAS после fault; writes предыдущего handler откачены (два соединения); missing base не переименован в invalid receipt; existing metadata/provenance regression. Отдельно проверить отсутствие копий predicates и неизменность C1 interfaces.

## 6. Gates и поставка

До реализации OPEN:

- C2-G1: точный trace pinned-base reads и internal signature/caller delta; подтверждение неизменности либо явное согласование изменения принятого порядка.
- C2-G2: extraction map каждого existing predicate, shared helper inputs и итоговая envelope validation без дублей; stable diagnostic order/address и совместимость existing aggregation.
- C2-G3: malformed root carrier, exact typed diagnostic roster, boundary transport и приоритет unknown rollback. Новые публичные поля не вводятся предположением.
- C2-G4: синхронизация с owning ТЗ после проверки расхождений; inventory shared файлов после C1.

Порядок поставки после gates и разрешения кода: C2-I1 — единый pure provenance helper/typed errors/validator плюс адресные tests и миграция existing pure consumers; C2-I2 — service wiring с доступными bases, regression rollback/call-order и полный затронутый Snapshot test scope. I1 не означает выполненный runtime C2. I2 не начинает новый public apply lifecycle.

Для каждого класса/метода/POJO отчёт: exact declaration, imports/nested calls/effects, проверка, PASS/OPEN/FAIL. Любой пропуск или нарушение исключает приёмку. Before code — полный текущий inventory, implement-plan, SoT и diff; без сервера/commit/push. Gate общего Snapshot ARCH-0 не снят этим документом.

## 7. Статус отдельной проверки противоречий

Отдельный review выполнен: [C2-R1…R5](snapshot-receipt-validation-c2-review.md). Итог — детальный implementation contract OPEN: reads/trace, original receipt index, malformed aggregation, exact extraction map и diagnostic compatibility требуют уточнения. Архитектурное согласие не является PASS реализации или всех деталей. Не менять C1 и ТЗ ради устранения найденного расхождения без соответствующего согласования.
