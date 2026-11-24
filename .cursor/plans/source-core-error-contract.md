# Source: state admission, materialized input и postconditions

2026-11-25. Консолидированная Source error delta по пункту 2 остатка архитектуры. Статус: OWNER PROPOSAL, передаётся координатору; не принятая смена wire/runtime. Existing SourceFieldIssue/SourceLogicIssue/SourceFailure переиспользуются без новых полей и зеркальных DTO. Файл назначения кодов после приёмки — `backend/app/dataModel/sourceVersioning/sourceErrors.py`.

## 1. Ровно три предлагаемых дополнения SourceLogicCode

Адресное дополнение после ревью: mutation-contract §9.4 предлагает ещё MEMBERSHIP_MISMATCH и MUTATION_REFERENCE_CONFLICT для after-graph проверки; capture-prune-configuration §2 — SourceOperation.PREVIEW_PRUNE/CONFIRM_PRUNE. Следующая таблица сохраняет первоначальные три кода, не полный roster всех последующих proposals. Ни дополнения, ни public prune POJO не считаются принятыми до координации. State-admission не использует after-graph коды; prune owner назначает собственный tag при агрегации REVISION_NOT_FOUND/REVISION_PRUNED, не APPLY_MUTATION.

| Enum member / wire value | Основание | Что не является основанием |
|---|---|---|
| REVISION_NOT_FOUND / revision_not_found | Authoritative Source observation подтверждает отсутствие требуемой exact revision | Нет записи во входном materialized наборе; отсутствует observation |
| REVISION_PRUNED / revision_pruned | Source history подтверждает explicit prune exact revision | Tombstone, отсутствие body в памяти, неизвестный storage outcome |
| MATERIALIZED_INPUT_INCOMPLETE / materialized_input_incomplete | Source выявил required exact ref, для которого не передан необходимый Source value, graph entry или admitted content | Подтверждение физического удаления/отсутствия artifact |

Новый MATERIALIZED_INPUT_INCOMPLETE описывает дефект completeness producer, не ошибку поля пользователя и не факт недоступности storage. INCOMPLETE_CLOSURE не переопределяется: его прежние graph semantics не должны смешиваться с неполнотой предъявленного входа. MISSING_BODY остаётся возможен только по соответствующему owning read evidence. Invalid/expired authority сохраняет owning transport, не превращается в completeness code.

MUTATION_ID_CONFLICT не добавляется для существующего owning ledger binding mismatch: сохраняется owning typed error. MEMBERSHIP_MISMATCH из ранних drafts не принимается этой дельтой и не используется для state-admission; actual before/after membership contract рассматривается отдельно. Таким образом эта правка не разрешает весь прежний error roster автоматически.

## 2. State admission: законченный mapping

SourceMutationStateChecker возвращает SourceFailure(operation=APPLY_MUTATION), group_index/use_index=None, artifact=None. В source записывается exact object/collection ref; synthetic revision для CREATE не создаётся.

| Условие | Код / source |
|---|---|
| CREATE при live current | REVISION_CONFLICT / current |
| CREATE, UPDATE или DELETE при tombstone current | TOMBSTONE / current |
| UPDATE/DELETE при отличающемся live current | REVISION_CONFLICT / expected |
| UPDATE/DELETE при authoritative absence | REVISION_NOT_FOUND / expected |
| Exact expected явно pruned | REVISION_PRUNED / expected |
| Collection expected=None, current существует | REVISION_CONFLICT / current collection ref |
| Collection expected задан, current отличается | REVISION_CONFLICT / expected collection ref |
| Collection expected задан, authoritative current отсутствует | REVISION_NOT_FOUND / expected collection ref |

Для одной change подтверждённый pruned expected имеет приоритет над stale/absence diagnosis; остальные changes и membership продолжают проверяться независимо. Inconsistent observation (например never-created absence вместе с pruned history той же identity), отсутствие обязательного state fact либо дублирующие current categories — internal input contract failure, не business absence. Порядок: original changes → membership, одинаковые issues сводятся стабильно. Identity-only CREATE source не выдумывается: конфликт с current уже имеет реальный ref.

StateFailure не означает persisted terminal refusal. До writes это preflight, после writes требуется owning confirmed rollback/terminal handling; error code сам не доказывает durability результата.

## 3. Неполный materialized input

Collector уже возвращает три typed gap tuples: missing_source_values, missing_graph_entries, missing_admission. Для публичного отказа все они проецируются в существующий SourceLogicIssue с MATERIALIZED_INPUT_INCOMPLETE. Различия gap slots сохраняются внутри операции для проверок; новые reason поля и второй error DTO не добавляются.

Каждый gap `(capture, required_ref)` даёт issue с artifact=required_ref, source=None, исходно group_index/use_index=None. Затем existing locate_logic использует **capture origins**, включая все actual occurrences. Не выводить atom identity из первого совпадения ref: required body может не быть selected logical atom. Одинаковые localized issues сводятся после локализации. SourceFailure.operation фиксирована owner: ADMIT, READ, ADMIT_GROUPS, VERIFY_GROUPS либо SELECT. VERIFY использует presented origins; SELECT — projected origins выбранных atoms.

Для capture candidate FINALIZE_CAPTURE original proof origins отсутствуют: group/use остаются None, artifact указывает недостающий ref. Отсутствующий witness позволяет назвать только witness ref; неизвестный capture_body не синтезируется. Повреждённая форма входа диагностируется structural boundary, а не этим кодом. Полный materialized content с неверными relations даёт прежний semantic код, не MATERIALIZED_INPUT_INCOMPLETE.

Source operation owner формирует единый failure из доступных независимых semantic issues и localized gaps. Ни один gap не допускает успешный result или публикацию частичного refs. Неполная ветвь не запускает зависимые relation checks; независимые captures проверяются. Не строить field path в синтетическом SourceProofReadInput или в пока неизвестном foreign DTO.

Внутренний helper `proof/closureInputs.py::input_gap_issue(required_ref: ArtifactRef) -> SourceLogicIssue` создаёт только нелокализованную issue указанного кода, с остальными context fields None. Он не принимает operation и не выполняет localization/dedup. SourceFailure собирает owner; повторный алгоритм диагностики в candidate/collector не вводится.

## 4. Postcondition и programming transport

| Условие | Transport | Граница |
|---|---|---|
| Неверный тип internal operand/dependency | TypeError | Internal принимающий компонент |
| Неверные positions/counts, противоречивые state facts или duplicate graph parent entries | ValueError | Internal input validation; не raw public request |
| Собственный transform нарушил заявленную postcondition; arithmetic/transition результат не соответствует проверенным operands | RuntimeError | Operation/implementation owner, до возврата результата |
| Обязательный materialized operand отсутствует | MATERIALIZED_INPUT_INCOMPLETE через SourceFailure | Это нормальный обнаруживаемый input gap, не RuntimeError |
| Invalid original proof/request | Existing typed field/logic diagnostics или предусмотренный root structural отказ | Request boundary, до transform |
| IO/authority/cancellation/unknown outcome | Исходный owning transport | Без blanket catch ValueError/Exception и перекодирования |

Новый application exception/class не нужен. RuntimeError не является типизированным бизнес-отказом; его нельзя сериализовать как SourceFailure либо persisted Refused. Текст ошибки не является машинным discriminator. Известную ошибку собственного computed result можно обернуть с cause; произвольный Pydantic/ValueError внешней зависимости не перехватывается как postcondition. Production check не заменяется assert. Не помещать raw bodies/request в exception message.

Manual ValueError существующих POJO и их будущая типизированная request-диагностика остаются отдельной работой G1: данный transport не объявляет эту миграцию выполненной.

## 5. Проверка и принятие

Матрица: authoritative absence → REVISION_NOT_FOUND; explicit prune → REVISION_PRUNED; missing observation → internal failure; missing Source body/leaf graph entry/admitted transitive ref → MATERIALIZED_INPUT_INCOMPLETE, никогда MISSING_BODY; полный content с wrong membership → semantic refusal; два captures с одним missing ref сохраняют все distinct original occurrences; два вида gap одного ref/use дают одну issue; ошибочный computed proof → RuntimeError без result; original invalid proof → typed request refusal; owning unknown/cancellation сохраняются.

Чтобы дельта стала действующей: координатор сверяет consumer error handling и неизменность маршрута; фиксируется решение пользователя; затем source-proof-v2-contract-spec.md §11.3, runtime enum и соответствующие tests синхронизируются в разрешённом implementation-порядке. Здесь код, schema IDs и persisted outcomes не изменены. Собственная семантика и transport предъявлены полностью для этих трёх групп; owning wire/capability transport X-READ не выбирается Source.
