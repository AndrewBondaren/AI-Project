# C2 R3/R4/R5: admitted facts, единые predicates и порядок diagnostics

## Итог координаторской сверки P1 — 2026-11-21

PASS документальной сверки уточнённого R3/R4/R5 в области facts/provenance/address/order. Основание: прочитаны actual SnapshotMetadataBuilder и validation/receiptProvenance.py, сопоставлены независимые partial-ref checks, operation/history/state predicates и final postconditions. Пользователь поручил принять уточнённый контракт перед подключением consumers. Ниже фиксируется целевой контракт к этому подключению; прежнее «граница не определена» superseded. Это не PASS реализации: код ещё содержит независимые проверки, runtime tests не выполнены. Полная реализация выполняется только через implement-plan с отдельной проверкой scope.

### Обязательное уточнение адаптеров и приоритетов

- retention=None означает «полная closure недопущена», никогда «пустая валидная closure». Valid ref позволяет owner/assigned/membership/replacement проверки; сравнение artifacts closure пропускается, structural issue сохраняется и не допускает успешного builder result.
- changed_empty=None не превращается в True из-за пустой отфильтрованной коллекции. Независимые valid changed refs всё ещё проверяются на operation и input membership с исходными индексами.
- Полностью недопущенный root не используется для извлечения guessed/default полей. Partial facts принадлежат только допускаемой повреждённой owning receipt-модели. Fact collection не заменяет raw receipt реконструированной «валидной» моделью.
- Early получает section_index из исходного enumerate sections. Builder — исходный index receipts. Final — index своего неизменённого receipts tuple; filtered receipts не получают исходные PatchSet адреса без отдельного explicit mapping.
- Один owner helper переиспользует existing _same_owner семантику; owner-selection не сортирует diagnostics по владельцам. Adapters объединяют по phase и original indices, включая world/player interleaving.
- Final checker не выбирает первый код общего helper без учёта прежней фазы. Сохраняются prechecks metadata.operation/parent/duplicate keys/FOREIGN_OPERATION, затем metadata-history equality, затем прежний receipt traversal history→states (new-state NOOP и inherited closure), затем metadata-state equality и final missing/superseded membership. SUPERSEDED_STATE из общего predicate используется в соответствующей final postcondition-фазе, не переносится перед прежним UNREACHABLE или metadata mismatch. SnapshotMetadataBuilder и early используют свой явно заданный агрегирующий порядок ниже. Один predicate может быть вызван/его результат выбран разными adapters без копирования условия.

### План подключения — без изменения общего apply-порядка

1. ReceiptFactsAdmission выделяется из существующей structural/partial admission логики; не создаёт IO, fake closure или новые public receipt поля.
2. Pure predicates operation/owner/history/state получают один источник в validation/receiptProvenance.py. Caller-specific context/base/association/metadata coverage остаются у соответствующего caller.
3. SnapshotReceiptValidator, SnapshotMetadataBuilder и final validate_receipt_provenance переходят на эти facts/predicates; старые параллельные условия удаляются в той же реализации, без fallback с копией правил.
4. Early receipt validation остаётся немедленно после successful handler.apply, перед accumulation/следующим handler. H2 может отвергнуть malformed handler output раньше C2; standalone builder partial diagnostics всё равно сохраняются.
5. Проверки реализации: malformed artifacts + valid foreign ref; несколько независимых причин в одном/нескольких receipts; gaps indices 0/2 после malformed index1; interleaved world/player; wrong operation и outside-input одновременно; changed malformed без ложного NOOP; root mismatch без fake path; verdict parity predicates и сохранение first-error final/order builder. No-op history при assigned ref не запрещается общим Snapshot; Lifecycle owning правило отдельно.

После этих проверок можно заявлять implementation PASS, а не по одному наличию helper. Новые numeric IDs и production domain интеграции не требуются для этой внутренней pure границы.

2026-11-21. PROPOSED исправление повторного ревью. Заменяет fully-valid-only extraction из snapshot-provenance-extraction-r4.md и незамкнутые R3/R5. Не меняет порядок transaction, H2 output admission или public DTO. Код не пишется.

## 1. Внутренние типизированные факты

Новый internal модуль `application/worldSnapshot/validation/receiptFacts.py`; frozen dataclasses, не wire records/публичные POJO и без canonical IDs. Это результат structural admission для доступных фактов, не второй SectionApplyReceipt. Все indices strict int>=0 без bool; factory проверяет их, constructor также отвергает неверные значения. Вложенные ref/retention — строго валидированные existing owning модели, не копии их полей.

| Класс | Поля и смысл |
|---|---|
| AdmittedChanged | index:int; ref:PatchRef |
| AdmittedState | index:int; ref:SectionStateRef; retention:SectionStateRetention \| None. None означает closure не прошёл admission, а не пустой artifacts |
| AdmittedHistory | index:int; ref:SectionHistoryRef; retention:SectionHistoryRetention \| None, тот же смысл None |
| ReceiptFacts | section_index:int; section_key:SectionKey \| None; changed_empty:bool \| None; changed:tuple[AdmittedChanged,...]; states:tuple[AdmittedState,...]; history:tuple[AdmittedHistory,...]; validated:SectionApplyReceipt \| None; structural_issues:tuple[SnapshotBuilderIssue,...] |

`ReceiptFactsAdmission.admit(raw: object, *, section_index:int) -> ReceiptFacts` — pure internal метод. object допускается только на этой unchecked structural boundary; наружу выходят закрытые typed facts. Метод сначала применяет existing SectionApplyReceipt.model_validate(strict=True). При успехе validated заполнен и все facts из валидной модели. При ValidationError сохраняет structural issues в исходном порядке Pydantic; known field → existing SnapshotMetadataFieldIssue/CheckedPath; root/unknown location → SnapshotMetadataRelationIssue(code=INVALID_RECEIPT,location='receipts',address=(section_index,*loc)). Фиктивный FieldPath не создаётся. TypeError/неожиданные programmer errors не blanket-map в malformed receipt.

Если raw не SectionApplyReceipt и owning model validation завершилась неуспешно, зависимые facts пусты: это сохраняет current builder continue для неправильного root/dict. Если raw — повреждённый SectionApplyReceipt, factory независимо валидирует section_key, каждый PatchRef, каждый nested state/history ref и каждый полный retention entry. Неверный tuple-контейнер не обходится как iterable. Missing fields не заполняются фиктивным default. Original indices сохраняются, не enumerate отфильтрованного списка. Валидный ref доступен даже при повреждённых artifacts: retention=None. Отдельный extraction не добавляет повторные structural issues — их уже дал whole-model admission.

changed_empty=True только для структурно допустимого пустого changed tuple; False для валидного непустого changed tuple; None если поле changed не допущено. None запрещает вывод NOOP_STATE, но не мешает FOREIGN_OPERATION для отдельно допустимых changed refs. Parent/base failure не превращается в UNREACHABLE_STATE: зависимая проверка пропускается, owning base diagnostic остаётся.

## 2. Единые pure predicates

В existing `validation/receiptProvenance.py`, без IO/context capability:

`patch_matches_operation(ref:PatchRef, expected_operation_id:EntityUid) -> bool` — одна equality проверка полного operation_id. Все три consumers (early validator, builder, final provenance) вызывают её; expected берётся из context.validation.operation_id либо явного аргумента final checker, не из receipt. UID admission принадлежит owning model/boundary.

`history_uses_assigned(ref:SectionHistoryRef, assigned:SnapshotRef) -> bool` — exact ref.snapshot==assigned для уже выбранного owner. Unknown owner проверяет global caller, выдаёт FOREIGN_HISTORY без вызова owner predicate.

`state_provenance_codes(state:AdmittedState, *, assigned:SnapshotRef, base:SnapshotEnvelope|None, changed_empty:bool|None, replaces_same_owner_section:bool, base_available:bool=True) -> tuple[SnapshotMetadataCode,...]` — единственный алгоритм state rules для early/builder/final. Preconditions: ref того же owner, assigned identity допущена caller-ом. При base_available=True identity base допущена, None означает отсутствие parent. При False base обязан быть None; caller уже сохраняет base failure, зависимые reachability/closure проверки пропускаются (§3). Assigned new state + changed_empty=True → NOOP_STATE. Inherited state + replacement → SUPERSEDED_STATE. При доступной базе inherited ref отсутствует в base либо admitted retention не равен base entry → UNREACHABLE_STATE. При retention=None проверить допустимый ref membership, но не объявлять artifact closure совпавшим. Порядок кодов SUPERSEDED_STATE → UNREACHABLE_STATE; assigned state не проходит inherited branch.

Owner identity/ref selection — один shared pure helper (existing _same_owner/_owner унифицировать), не отдельные copies в callers. `replaces_same_owner_section` вычисляется по admitted state refs с exact assigned snapshot, как existing builder; malformed sibling closure не скрывает известный replacement ref.

`collect_owned_receipt_provenance(facts:ReceiptFacts, assigned:SnapshotRef, base:SnapshotEnvelope|None, *, base_available:bool=True) -> tuple[SnapshotMetadataRelationIssue,...]` — adapter перечисленных predicates для одного owner. Его аргумент теперь facts, не fully validated receipt. Возвращает адреса с facts.section_index и original nested index; structural issues и operation mismatch не добавляет. Final append сначала имеет strict validated receipt, затем получает facts через тот же admission; early и builder используют его также на partial inputs. Нет fallback с копией predicates. base_available передаётся state predicate без переинтерпретации.

Global adapter проверяет неизвестных owners и выбирает owner/base; final caller только одного envelope не получает несуществующие global guarantees. Final envelope↔receipts↔base coverage, metadata.operation/parent, duplicate receipt keys остаются отдельными postconditions. Не строить fake SnapshotApplyContext для final check.

## 3. Стабильная диагностика

### Уточнение архитектурного ревью: общий owner/base adapter

2026-11-21, по поручению пользователя «Правь». Детализация принятого pure контракта, без изменения predicates, фаз или публичного API. Старый global helper с raw receipt заменяется следующими signatures в receiptProvenance.py:

```python
def receipt_owner(ref: SnapshotRef, assigned: tuple[SnapshotRef, ...]) -> SnapshotRef | None: ...

def collect_receipt_provenance(
    facts: ReceiptFacts, context: SnapshotApplyContext,
    bases: Mapping[SnapshotRef, SnapshotEnvelope],
) -> tuple[SnapshotMetadataRelationIssue, ...]: ...
```

`receipt_owner` использует один existing same-owner predicate (world_uid для WorldSnapshotRef, player_uid для PlayerSnapshotRef, kind обязателен). Возвращает единственный assigned ref либо None; дубли owner в assigned — внутренний ValueError, не произвольный первый match. Existing _owner/_same_owner приводятся к одному источнику этой семантики; owner identity не включает равенство snapshot_id. Функция не проверяет ancestry, provenance или metadata и не получает scope.

`collect_receipt_provenance` принимает уже admitted facts, не запускает ReceiptFactsAdmission повторно. Из context берёт только assigned refs/ожидаемые parent refs, не обращается к capability. Context/assigned participant coherence проверяется caller до этого вызова (standalone builder сохраняет собственные предварительные diagnostics). Mapping bases keyed exact pinned SnapshotRef; builder сохраняет свой existing Mapping контракт, early validator принимает такой же Mapping вместо tuple. Не требуется конвертировать bases через потерю ключей или реконструировать fake context в final checker.

Общие prerequisite diagnostics баз формирует один `collect_pinned_base_issues(validation:SnapshotValidationContext,bases:Mapping[SnapshotRef,SnapshotEnvelope])->tuple[SnapshotMetadataRelationIssue,...]` из receiptProvenance.py: missing/identity в world→players порядке, затем extra keys. Exact contract и caller mapping — snapshot-receipt-validation-c2.md §4.1. Builder включает их в прежнюю preliminary aggregation; early/service guard трактуют их как внутренний infrastructure fault до receipt checking. Global adapter не дублирует этот report, а выбирает base_available для зависимых predicates. Storage loader отдельно отвечает за IO/strict decoded envelope admission, не за receipt provenance.

Для каждого owner adapter сопоставляет parent из expectation: None parent означает отсутствие базы; non-None parent с отсутствующим entry либо entry.ref!=parent означает недоступную/некорректную базу. Existing missing/base-identity diagnostics остаются у caller и здесь не добавляются. При такой базе adapter всё равно проверяет независимые assigned history, NOOP_STATE и SUPERSEDED_STATE, но не выполняет зависимую inherited reachability/closure проверку. В частности, нельзя передать base=None в state predicate так, будто parent действительно отсутствует. Чтобы не копировать SUPERSEDED условие в adapter, `state_provenance_codes` получает дополнительный keyword-only `base_available:bool=True`; при False требует base=None, сохраняет assigned/replacement проверки и пропускает только inherited base reachability/closure. False не означает успешную проверку closure; caller обязан сохранить собственный base failure. Final всегда передаёт True после exact parent admission.

Global adapter: history с неизвестным owner → FOREIGN_HISTORY; history известного owner проверяется единым history predicate; state с неизвестным owner → UNREACHABLE_STATE без guessed base; для известного owner выбираются exact parent/base и вызываются единые state predicates. Owner-local `collect_owned_receipt_provenance` принимает тот же keyword-only base_available=True и использует тот же state predicate. Replacement set вычисляется из admitted state refs того же receipt, assigned owner/key, даже если sibling retention недопущен. Алгоритм replacement принадлежит owner-local helper, global adapter его не копирует.

Adapter собирает результаты owner-local checks в порядке history original index, затем state original index с принятой внутри-index последовательностью кодов; не по порядку owners. Original facts.section_index остаётся неизменным. Structural issues, association, input membership, FOREIGN_OPERATION, duplicate receipts и metadata coverage здесь не формируются. Early и builder получают общий tuple provenance issues и включают его в свои заданные фазы. Final использует owner-local predicates с собственными first-error фазами, не global adapter с отсутствующими ему данными.

Критерии ответственности: adapter не читает storage, не строит envelopes, не определяет domain validity и не создаёт второй history/state predicate; неверный base не превращается в UNREACHABLE_STATE, independent replacement issue не теряется. Тест с одновременно missing base, valid inherited ref и valid assigned replacement должен сохранить base failure/SUPERSEDED и пропустить dependent closure issue. Interleaved owners сохраняют original indices. Это точный механизм, а не новое правило принятия ошибочных входов.

Builder сохраняет existing sequence: предварительные turn/context/base issues → для каждого receipt: structural issues → duplicate section → FOREIGN_OPERATION по original changed index → FOREIGN_HISTORY по original history index → state issues по original state index (SUPERSEDED перед UNREACHABLE) → заключительные context/pack checks. Owner-local outputs объединяются по фазе/исходному индексу, а не по порядку owners. Внутри malformed structural issues не сортируются. Общая duplicate receipt проверка не переезжает в per-receipt helper.

Early C2 sequence: structural issues → association → input membership по changed index → FOREIGN_OPERATION по changed index → history по original index → states по original index. **FOREIGN_OPERATION не подавляется:** прежнее предложение «membership достаточно» отозвано. Это разные отношения (input membership и expected operation), независимые факты сохраняются; порядок явно указан. Не сортировать по code/message/UID или состоянию dict. Результаты owner helpers агрегируются с фиксированными phase/index slots, без нового persisted diagnostic envelope.

Existing SnapshotMetadataFieldIssue/RelationIssue и codes переиспользуются. Для новых input-association records в proposed receiptContract.py добавить обязательный section_index:StrictInt>=0 без bool в ReceiptSectionMismatch и ReceiptChangedPatchNotInInput; changed_index остаётся отдельным nested адресом. Это новая ещё не реализованная diagnostic модель, не расширение SectionApplyReceipt/PatchSet. Нет выдуманного field path для relation. SnapshotReceiptContractError.diagnostics остаётся закрытым union указанных records и existing metadata issues.

Final validate_receipt_provenance сохраняет внешний ValueError и порядок собственных prechecks. На shared predicate failure выбирается первая причина в прежнем final traversal (receipt, history, states), её code имеет явное соответствие existing ValueError message; final не начинает выдавать builder aggregation. При наличии нескольких ошибок caller-specific порядок может различаться, но каждый predicate имеет один алгоритм. SnapshotMetadataBuilder сохраняет SnapshotMetadataFailure с полным ordered tuple. Новый early путь выдаёт SnapshotReceiptContractError. Эти adapters не переинтерпретируют бизнес-ошибки и не пишут terminal refusal.

## 4. Ответственность и приёмка

ReceiptFactsAdmission отвечает только за structural admission и доступность независимо валидных фактов; не читает base/operation/section input. Facts constructor не вычисляет lifecycle/provenance. Predicates отвечают только за отдельные relations. Adapters отвечают за owner coverage/address/order и owning error carrier. Builder строит envelopes; final checker проверяет итоговое покрытие. Отказ в приёмке при IO в этих компонентах, копии predicates, фиктивных closure defaults, потере original indices, swallowed programmer error или переносе Time/Lifecycle семантики в C2.

Обязательные scenarios: malformed artifact + valid foreign state ref даёт structural и независимый provenance issue; malformed changed не порождает выдуманный NOOP_STATE; wrong root даёт INVALID_RECEIPT relation без fake path; interleaved world/player history/state сохраняют original phase/index order; wrong operation+outside-input дают оба reports; empty changed+assigned history допустим общему Snapshot при прочих валидных условиях; exact Lifecycle retry отдельно требует no new history. Final и early дают одинаковый verdict каждого общего predicate; existing builder order/independent reports сохраняются. Runtime H2 malformed output останавливается раньше C2, но standalone builder partial-admission coverage не удаляется.

Это закрывает пропущенные declarations в proposal R3/R4/R5, а не объявляет реализацию или архитектурную приёмку. Требуются отдельная документальная сверка owning классов и последующее evidence реализации; новые DTO/порядок reports предъявлены явно. Numeric IDs, transaction order и принятые C1/H2 не меняются.
