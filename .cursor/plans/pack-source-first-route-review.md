# Первый Pack / Source маршрут: partial settlement update

Дата: 2026-11-13. Статус: CALLER / SEQUENCE ACCEPTED; полная implementation-приёмка ещё не пройдена. Пользователь подтвердил detailed_initialization и порядок шагов 1–7. Основания: [exchange](pack-source-exchange-contract.md), [execution binding](pack-source-dag-execution-binding.md). Код и новые NodeId не создаются.

## 1. Проверенный caller scope и предложение

В [GEN dependency §11.7–11.8](gen-dag-node-dependency.md#117-detailed_bake_initialization) detailed_bake_initialization готовит L2/C11 domain results/refs/evidence; detailed_initialization получает их, проверяет и публикует через owning publication contract. Родство detailed_initialization → detailed_bake_initialization уже зафиксировано. Exact prepared contracts остаются OPEN. В runtime каталоге engine/nodes соответствующих новых Pack/Source coordinating nodes не найдено; наличие legacy terrain nodes не даёт им эту ответственность автоматически.

**Согласовано пользователем:** coordinator этого первого exchange — существующая проектная роль detailed_initialization, после получения prepared child results и до publication. Она передаёт данные через верхние read_pack/read_source/write_pack и engine operation leaves. Child не получает orchestration Pack publication; домены не вызывают друг друга. Новая общая source_pack_publish нода не создаётся. Согласована логическая последовательность CALL; concrete registrations и typed contracts ещё требуют приёмки. Родство не изменяется.

Сценарий ограничен partial settlement write: есть pinned base и полный detailed provenance прежней settlement row, новый подготовленный structure part/territory, packed_district_uids=None и/или structure_status=None. Новая Pack версия ещё не READY. Old whole-row без attribution отклоняется по согласованной policy, не обходится полным proof старой строки.

## 2. Карточка согласованной последовательности

Порядок 1–7 согласован для этого сценария; runtime deps/contract IDs из этого автоматически не назначаются. Повторные payload writes, producers и генерация в exchange не выполняются.

| Шаг | DAG вход / owning цель | Полученный результат / следующая передача |
|---|---|---|
| 1 | read_pack → leaf описания запросов → Pack.describe_metadata_usage_requests(state, fields) | Полный набор PackMetadataUsageRequest групп требуемой settlement строки; Pack сам читает attribution, DAG не обходит её внутреннюю схему |
| 2 | read_source → leaf SELECT → Source.select(request) для запросов шага 1 | SourceProofResult; exact key/target/request/state сохраняются в continuation. Последовательное выполнение, без нового parallel fan-out |
| 3 | write_pack → leaf импорта → Pack.import_metadata_usage(state, entries) | Новый state с готовым usage всех групп строки; metadata/parts/durable proofs не меняются |
| 4 | write_pack → existing candidate write_settlement_structure leaf | PackSettlementStructureInput с импортированным state и готовыми новыми inputs/evidence; Pack применяет preserve semantics один раз |
| 5 | read_pack → describe_pack_metadata | PackMetadataDescription нового результата с сохранёнными и новыми usages/basis |
| 6 | read_source → leaf ADMIT_GROUPS | SourceProofGroupsInput из ordered usages → SourceProofGroupsResult; VERIFY_GROUPS не добавляется вторым обязательным вызовом |
| 7 | write_pack → bind_pack_metadata_provenance | PackMetadataProvenanceInput: exact сохранённый state, subject, groups/basis и успешный Source result; новый bound state |

Последующие closure read/prepare/activate принадлежат отдельной принятой части publication; эта карточка не выдаёт bound state за READY и не меняет их порядок. Для нескольких writes заранее не предписывается повтор шагов 1–3 после каждой записи: pending usage переносится через state; exact batching/deps принимаются по реальному caller scope.

Роли листьев для новых describe-requests/import/Source methods пока не имеют утверждённых NodeId, классов и registry keys. Эти имена должны быть предъявлены владельцем DAG при принятии карточки. Из имени публичного метода нельзя автоматически зарегистрировать node.

## 3. Ответственность и проверки

Coordinator: выбирает вызовы engine и механически связывает outputs с inputs; не считает Source indices/union/fingerprint, не выполняет Pack merge. Отказ при direct public domain call из coordinator в обход domain leaf или прямом node.execute. Верхние read/write nodes сохраняют собственные typed commands и не становятся domain services. Leaf делает один owning вызов и сохраняет его успех/ошибку. Pack выполняет local calculation, Source проверяет source data. InvocationCoordinator/CallResults обеспечивают существующую correlation, но не честность producer evidence или holds.

Всю зависимую цепочку фиксирует один immutable state snapshot на каждом exchange. Foreign result/state, partial Source failure, missing group, stale subject, неверный basis, old attribution refusal и cancellation не запускают следующий зависимый write. Shared input values не являются receipt: output берётся только из соответствующего successful engine child invocation. Resume должен сохранять lineage, exact requests и state, иначе готовый caller-supplied result не принимается.

## 4. Результат обязательной приёмки

Concrete NodeId/class/Input/Output/Error/registration предложения теперь предъявлены в [leaf contracts](pack-source-leaf-contracts.md). Это закрывает отсутствие проекта карточек, но не их приёмку или runtime реализацию; отмеченные ниже OPEN проверяются по этому дополнению.

| Критерий проекта | Результат |
|---|---|
| Три запрета DAG | Предложение сохраняет оркестрацию в DAG, без direct Pack→Source и скрытого pipeline. Runtime trace нового маршрута отсутствует |
| Ответственность каждого класса | Роли owner/engine сформулированы; concrete coordinator/leaf classes и полный class roster ещё не предъявлены — OPEN |
| Public contract / implementation | Pack/Source owning POJO описаны exchange; exact новые DAG commands/outputs/error adapters ещё не приняты — OPEN |
| Неизменность утверждённого порядка | Пользователь согласовал caller и последовательность 1–7; родство и producer/publication разделение сохранены. Runtime соответствие проверяется при реализации |
| CRUD данных/настроек | Это часть Pack update и Source read/admission, не создание нового CRUD/настроек. Принятые исключения не пересматриваются |
| Междоменный протокол | Source подтвердил формы использования; конкретные NodeIds/deps/execution registration/restore остаются OPEN |
| POJO и ошибки без дублей | Owning типы переиспользуются; SourceFailure сохраняется; canonical restore/diagnostic mapping конкретных нод ещё не проверены — OPEN |

**Полная приёмка маршрута не пройдена.** Отсутствующие сведения не заменяются тестовыми заглушками. Caller и порядок уже согласованы, повторно их не открывать. Далее оформляются concrete leaf/command карточки и проверяется полный набор критериев до реализации. Это не остановка независимого Pack scope и не новый запрос владельцу Source о его POJO.
