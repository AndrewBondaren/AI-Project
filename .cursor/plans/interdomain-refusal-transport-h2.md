# H2: типизированный доменный отказ до результата и replay

2026-11-20. Постановка и вопросы сохранены по поручению пользователя. Статус: OPEN / предложения к согласованию, не code-go. Координатор — Between domain operations. H2 является общей границей, используемой IC-1; не новый девятый контракт. Локальный H3 на готовых SQL-данных принят отдельно.

## Проблема и граница

**Фиксация границ write flow пользователем 2026-11-20.** Terminal read/replay относится к внутреннему выполнению Snapshot.apply под нодой apply_snapshot, не к отдельной read_world цепочке. Metadata принадлежат Snapshot; Time handler принадлежит Time и подключается registry/composition, готовая section поступает через assembler. Terminal persistence/replay принадлежат Publication, apply result model — Snapshot, semantic diagnostics — доменам. Metadata/terminal не приходят outputs предыдущих DAG-нод. Общий operation store/claim — рассматриваемая infrastructure dependency; H2 обязан проверить допустимость exact internal port и вложенных вызовов. Полностью согласованным этот путь ещё не объявлен; прямой foreign public pipeline call не разрешён. [Общая карта и таблица](dag-multidomain-patch-publication-draft.md).

**Решения пользователя 2026-11-20 — ACCEPTED в узкой части H2:** (1) TimeSectionRefused сохраняет только структуру и общие инварианты carrier; проверки общего request, отсутствия повторных codes, порядка diagnostics и соответствия category набору причин выполняет Time-owned validator перед возвратом handler. Семантические инварианты отдельного TimeCommitRelationIssue остаются в его owning модели. Registry/Snapshot эти predicates не копируют. Exact имя/метод validator предъявляет Time отдельно. (2) Локальная IC-1 composition переиспользует TimeSectionRefused; второй TimeSnapshotSectionRefused не создаётся. Это не отменяет отдельный Snapshot result model. Решение не выбирает путь/владельца composition, canonical IDs, terminal compatibility и не закрывает H2 целиком; код не разрешён.

Time может вернуть конфликт переданного и фактического состояния. Такая диагностика содержит typed operands и не обязательно адресует поле. Existing SectionRefused.diagnostics допускает только FieldPathError; SnapshotApplyResult — FieldPathError | SnapshotApplyRelationIssue; StoredTerminalCodec фиксирует root SnapshotApplyResult. Поэтому конкретный Time relation issue нельзя провести до результата и replay без согласованного изменения контрактов.

Нужна цепочка: owning domain issue → handler refusal → registry → Snapshot result → terminal encode/store/decode → exact replay → DAG. Сохраняются concrete тип, все operands, category и порядок diagnostics. Семантика и классификация принадлежат домену; DAG только передаёт результат и оркестрирует. Infrastructure/C2 faults, cancellation и unknown commit не превращаются в business refusal.

## Предложенное направление, ещё не принято целиком

PatchSet предложил SectionRefused[D], SectionValidation[D], DomainSectionHandler[S,D] с refusal_model и SectionRegistry[D]. Именованные concrete специализации и закрытый набор diagnostic types определяются composition. Registry проверяет локальный результат и переносит diagnostics в composition carrier без стирания типов/словарификации. Snapshot поддержал SnapshotApplyResult[D] с owning admission diagnostics и доменным D. Terminal codec должен получать согласованную concrete root model и полный manifest. Неподставленный generic, Any/dict/BaseModel как фактический runtime carrier, Time-specific imports в общее ядро и фиктивные field paths не допускаются. BaseModel как generic bound не равен разрешению принимать открытый runtime тип.

## Вопросы для согласования

| ID | Вопрос / требуемое решение | Ответственный |
|---|---|---|
| H2-1 | Exact модули/signatures carrier, handler, bound handler, registry; construction binding, проверка closed types/локального subset, перенос existing field diagnostics, output contract faults | PatchSet |
| H2-2 | Concrete TimeCommitRelationIssue, category/aggregation, локальная refusal model; полный состав operands и достижимых типов для persistence, без переоткрытия native patch IDs | Time |
| H2-3 | Exact SnapshotApplyResult specialization и apply port mapping; перенос refusal после подтверждённого rollback; закрытый admission union; отсутствие повторной интерпретации Time errors | Snapshot |
| H2-4 | Owning terminal codec и persistence boundary: constructor/model binding, encode/decode root/operation-kind/category checks, manifest closure, missing/foreign type errors; подтвердить владельца | Publication совместно со Snapshot |
| H2-5 | Сохранённые outcomes: source inventory supported formats/roots, read compatibility, version/identity policy, replay после изменения composition. Не утверждать отсутствие persisted данных по одному поиску кода, не назначать bump или migration без evidence | Publication, Snapshot; Time даёт closure |
| H2-6 | Где живёт конкретная result/refusal composition и кто её связывает: Time локальный closed набор для IC-1 без выбора полного production union. Один согласованный mapping handler → registry → result → codec; владение подтвердить, не назначать молча | PatchSet, Snapshot, Publication, координатор |

Каждый ответ должен содержать конкретное предложение, existing/proposed/accepted/runtime статусы, пути/методы/Input/Output/Error, роль каждого класса и допустимые зависимости, основание PASS/OPEN/FAIL и точный остаток. Взаимные требования передаются координатору; локальное согласование не закрывает общую цепочку.

## Критерии закрытия дизайна

1. Все переходы Output → Input замкнуты на concrete типах; независимые diagnostics и их порядок сохраняются, чужой тип отвергается execution fault, не новым business refusal.
2. Registry выполняет контрактную проверку, Snapshot не вычисляет Time семантику, core не импортирует Time; pipeline/public/internal границы и все обязательные критерии dag-generator-interface.mdc проверены.
3. Terminal representation и совместимость поддерживаемых сохранённых outcomes определены; replay возвращает сохранённую категорию/diagnostics без чтения state и повторного вызова handler. Политика несовместимой composition явная, без обрезания diagnostics.
4. Не изменяются принятый порядок apply, H3/C2-R1, native section/codec IDs; предлагаемая необходимая дельта предъявляется отдельно. H2 не разрешает миграции или код.
5. Координатор сверяет ответы, итог принимает пользователь. Реализация и evidence round-trip/rollback/replay/foreign-type rejection — отдельный этап, не подмена приёмки дизайна.

## Источники

- [Реестр IC-1](interdomain-contract-register.md).
- [Time H2](time-domain.md).
- [PatchSet внешние контракты](patch-set-external-contracts.md).
- [Snapshot public contracts](snapshot-public-methods-contract.md).
- Existing backend/app/dataModel/patch/results/sectionResult.py, backend/app/dataModel/worldSnapshot/results/apply.py, backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py.
