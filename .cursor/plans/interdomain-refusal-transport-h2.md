# H2: типизированный доменный отказ до результата и replay

## Координаторская сверка последнего Snapshot construction proposal, 2026-11-21

Локальный PASS совместимости с Publication: single-field TimeSnapshotBinding.publication_binding передаётся напрямую Snapshot/codec; operations предъявляет тот же binding и exact record_model; T сохраняется через record/claim/terminal/replay до ApplySnapshotOutput[T]. Generic Snapshot не импортирует Time. Diagnostics annotation против registry — локальная relation check Snapshot, не повторная schema/manifest/limits validation Publication. Output admission остаётся у PatchSet, semantic predicates у Time; дополнительный универсальный validator/factory для этой связи не требуется.

Общая приёмка OPEN: проверенный §3 patch-set-refusal-transport-h2.md всё ещё требует SnapshotApplyBinding, section_adapter и binding.refusal_model/result_model, отменённые актуальной таблицей Snapshot. Snapshot ссылается на этот §3, поэтому это действующее документальное расхождение. Нужно синхронизировать owning PatchSet §3 и проверить consumers отменённого binding, не менять принятый узкий builder.

Второе уточнение: в текущем разделе Publication direct expected-model decode обозначена узкая API delta для admission DecodeLimits, но не приведены её полная сигнатура и вызов из construction/прямого decode. Требуется точная публичная граница; принятые TypeError/ValueError configuration против CanonicalEncodingError payload не пересматриваются. Runtime tests отдельно. Pair(1,20150), IDs, no-legacy, H3 и отложенная durable cancellation не переоткрываются. Это сверка proposals, не code-go или полная приёмка H2.

**УТВЕРЖДЕНО пользователем 2026-11-21: current Snapshot pair `(format_version=1, root_id=20150)`.** Concrete модель `TimeSnapshotApplyResult` применяется для новой записи и exact replay текущего Snapshot-маршрута. Архитектурный выбор пары закрыт; прежние пометки «кандидат», «freeze OPEN» и «требуется утверждение пары» ниже заменены этим решением. Legacy fallback не вводится, прежние IDs не переназначаются, актуальные Pack/Gameplay/Cancelled не меняются. Runtime binding, полный manifest closure/collision audit, strict bounded decode, round-trip/replay и отказ на неподдерживаемые root/format без повторного apply ещё требуют реализации и проверки. Утверждение пары не означает приёмку всего H2 или разрешение на код/миграции.

**Последнее решение пользователя 2026-11-21 — БЕЗ LEGACY.** Поддержка прежних Snapshot terminal representations не требуется. Это заменяет прежнюю W/R compatibility policy: одна целевая concrete модель результата для новой записи и replay текущего маршрута, без OldSnapshotApplyResult union, legacy readers/manifests, old→new adapters, fallback и migration ради совместимости. Вводить два независимых набора W/R только ради legacy больше не нужно; точные упрощённые signatures сводят владельцы. Replay текущих операций сохраняется: те же данные/типы/identity, без повторного handler. Неподдерживаемый сохранённый root/format — явная инфраструктурная несовместимость, не отсутствие terminal и не разрешение повторить операцию. Принятые новые IDs31007/31139/31140/20150 сохраняются; прежние IDs не переназначаются. Pack/Gameplay/Cancelled — отдельные актуальные kinds, не legacy Snapshot, автоматически не удаляются. Legacy roster/corpus больше не gate H2. Новый root-dispatch API не вводится только ради выбора legacy readers: необходимость пересмотреть, сохранив strict expected root/full bounded decode и budgets. Решение не разрешает удалять данные, писать код или миграции; финальная упрощённая цепочка ещё требует сверки.

## Текущее сведение H2 — 2026-11-21

### Принято: узкий TimeSnapshot builder и владельцы construction checks

Решение пользователя 2026-11-21: `build_time_snapshot_binding(*, publication_binding: PublicationResultBinding[TimeSnapshotApplyResult]) -> TimeSnapshotBinding` возвращает только frozen application binding с одним owning полем publication_binding. PublicationResultBinding проверяет собственную schema/format/manifest/limits/record_model при construction; TimeSnapshotBinding — exact Time result/root20150/diagnostic compatibility через публичные данные. Чужой __post_init__ вручную не вызывается, predicates и конфигурация не дублируются. Snapshot проверяет локальную связь registry/refusal/D/result; Publication/Artifacts constructors — локальные identity связей codec/store/ledger/staging/leases. Application composition root соединяет экземпляры через публичные read-only properties. Builder не собирает сервисы, не принимает их для общей проверки и не оркестрирует runtime; новая универсальная factory не вводится.

Источники: [PatchSet §3](patch-set-refusal-transport-h2.md#3-единая-локальная-composition), [Snapshot: актуальные signatures](snapshot-refusal-transport-h2.md#актуальные-упрощённые-signatures--2026-11-21-proposed). Принято только это разделение ответственности; owning validation API и сквозная интеграция остаются H2-уточнениями. H2 сохраняется в отложенном скоупе: решение не блокирует независимую реализацию и не добавляет write_changes, подготовку входов или production composition rollout. Противоречащие исторические требования к универсальному builder ниже заменены этим решением; общей приёмки H2/runtime эта запись не означает.

### Дополнительная сверка SectionHandlerContractError и current pair

По поручению пользователя «Делай» сверены PatchSet H2 output admission, Snapshot H2 owning mapping, Snapshot node boundary, Publication proposal; дополнительно прочитаны actual publication/errors.py, sqlite snapshotCore/commitScope.py и operations/terminalCodec.py. Результат: PASS согласованности предложенной цепочки contract fault в этом ограниченном срезе, не полная приёмка H2 и не runtime evidence.

BoundSectionHandler проверяет returned output и выдаёт SectionHandlerContractError; Snapshot узко переводит его в PublicationInfrastructureError с cause внутри transaction body. Выполнение прекращается, record_refusal/terminal business result не создаются. Transaction owner выполняет завершение/rollback/drain/revoke. Только после owner public boundary различает подтверждённый rollback (INFRASTRUCTURE_FAILURE), UnknownCommitOutcome (OUTCOME_UNKNOWN) и распространяемую runtime cancellation. Затем SnapshotPublicError → PythonNodeError(SnapshotNodeError(error=fault)); успешный ApplySnapshotOutput не создаётся. Доменные predicates остаются в Time, receipt provenance — в Snapshot, output admission — в PatchSet.

Обязательное требование к порядку catch: UnknownCommitOutcome наследует PublicationInfrastructureError в actual коде, поэтому specific unknown mapping выполняется раньше generic infrastructure mapping. Нельзя маскировать неизвестный исход первичным contract fault. Actual transaction owner имеет rollback-on-BaseException и unknown при неподтверждённом rollback; интеграционные сценарии новых output faults ещё требуют проверки при реализации. Exact durable OperationCancelled engine transport по переданному решению пользователя отложен; обычная cancellation/unknown семантика не отложена.

Current pair (snapshot format_version=1, canonical root_id=20150) остаётся рекомендацией к явному утверждению пользователем. Первое обозначает версию сохранённого terminal representation; второе — canonical identity конкретного TimeSnapshotApplyResult, а не OperationRecord, Time state или section. Основание сохранения format1: Publication не меняет row envelope/TLV grammar; новый concrete тип различается root ID. Принятие пары закрепляет одну representation для новых Snapshot outcomes и exact replay текущего маршрута, без legacy fallback. Само по себе не доказывает поддержку existing codec: actual codec ещё выбирает старый SnapshotApplyResult. До runtime acceptance нужны binding snapshot_format_version=1/result_model=TimeSnapshotApplyResult, полный manifest closure без collisions, strict bounded decode и row/body checks, round-trip/replay и отказ на неподдерживаемые root/format без повторного apply. Code-go и freeze пары этим координаторским review не выдаются.

Действует решение БЕЗ LEGACY выше. Legacy diagnostic roster/corpus и поддержка прежнего Snapshot terminal не являются gates. Сохранены принятые IDs, encoding limits/error boundary, полный bounded decode, immutable identity и exact replay текущих операций. Pack/Gameplay/Cancelled не являются legacy Snapshot.

Snapshot и Publication запрошены о точном disposition классов/методов/roots/formats/manifests/config и одной simplified цепочке result → persistence → replay → node output. Final signatures/current-kind coverage остаются OPEN. Не заменять W/R механически и не удалять root-dispatch до owning ответа о необходимости для текущих kinds.

Ниже сохранена история предложений: требования legacy readers/roster/W-R compatibility отменены последним решением; остальные принятые гарантии сохраняются. Историческое ACCEPTED не возвращает отменённый gate. Точные текущие signatures сводятся после owning ответов.

## История решений — encoding / representations / IDs (не текущий список gates)

### Итоговая сверка координатора 2026-11-21 — к приёмке

Проверены ответы Publication/Snapshot и owning-планы; source-level сверены coreManifest registrations20306/20307/20137 и модель SnapshotApplyRelationIssue. Runtime/БД не проверялись.

- SIG: прежние расхождения S-instance и staging record_model устранены в Publication proposal. Один PublicationResultBinding[W,R] содержит write model/format/manifest/readers/record_model/limits; read_models вычисляется из readers. Store/ledger/staging предъявляют тот же binding через read-only property; leases предъявляет record_model. Factory проверяет exact identity до IO, без private introspection. Proposed ApplySnapshotInput[S].patch_set → IWorldSnapshotApply[S,R].apply → ApplySnapshotOutput[R].value сохраняет R без adaptation. Локальная совместимость signatures подтверждена сверкой; final acceptance отдельно, общий cancellation/public-error transport остаётся IC-4.
- DISPATCH: proposed validate_decode_limits(limits)->None + read_record_root_id(data,*,limits)->int конкретизируют принятую границу. Конфигурация проверяется до payload wrapper; header extraction не обещает проверки fields/items/всего nested graph. Full bounded decode обязателен. По прочитанным source и proposal конфликтов с принятой ответственностью не обнаружено; implementation edge-case evidence отдельно. Отдельный агент encoding не обязателен: координаторская проверка выполняется здесь, technical ownership остаётся encoding.
- REP: подтверждённый production diagnostic roster default legacy composition — SnapshotApplyRelationIssue20307 + SnapshotApplyCode20306 и reachable shared types. FieldPathError20137 — carrier, не полный concrete roster. FakeTargetIssue90011/enum90010/path90012–90014 test-only, production manifest ими не расширяется. Неизвестные historical subclasses не считаются отсутствующими или поддержанными. Для одного (1,20124) один непротиворечивый legacy manifest, не несколько trial readers.
- Новая pair (row format1, root20150) рекомендована к freeze: Publication source audit не выявил изменения row envelope/TLV-v1; old/new roots различимы explicit ID. Это рекомендация, не утверждение выполненного codec round-trip.

Один внешний вопрос для завершения legacy roster: должны ли читаться production historical FieldPathError subclasses сверх SnapshotApplyRelationIssue20307? Нужен scope поддержки; если да — exact class/ID/manifest и безопасные fixtures. Без ответа whole legacy compatibility не объявляется закрытой. IDs31007/31139/31140/20150 уже приняты, повторно не назначаются.

ACCEPTED после предъявления предложений координатора. Приоритет над историческими PROPOSED по перечисленным решениям; H2 целиком ещё OPEN, не code-go.

- Конфигурацию DecodeLimits проверяет encoding при создании decoder/codec binding до чтения, значения задаёт application composition. Прямой публичный helper также гарантирует проверку конфигурации. Числовые budgets — strict положительные int без bool; collection bounds 0 ≤ minimum ≤ maximum, field limits соответствуют моделям/полям, противоречивые дубликаты запрещены. TypeError для неверного типа конфигурации, ValueError для неверного значения/отношений; CanonicalEncodingError для malformed bytes/tag/length и превышения корректного бюджета. Publication сохраняет cause при mapping в infrastructure failure, не business refusal.
- Один shared parser. read_record_root_id проверяет размер и внешнюю RECORD-оболочку/границы/положительный canonical ID, применяет budgets к прочитанной части, не создаёт модель и не доказывает корректность nested payload. После dispatch обязателен полный bounded decode с manifest/model и всеми applicable field/items/node/depth checks.
- Порядок terminal read: row/size → checksum → root extraction → exact (format_version, root_id) reader → full decode → row/body identity/category и owning operation checks. Нет пробных decode, fallback или копии parser в SQL codec. Техническая граница остаётся в encoding; coordinator review API и Publication consumer review, без назначения нового предметного домена.
- Принято направление W/R: новая запись W, replay возвращает исходный поддерживаемый concrete член R без old→new adaptation. Сохраняются старые root20124 format1 и roots20125/20126/20127 в существующем формате. Старый root20124 сохраняет declaration/identity/meaning; generic/new W его не подменяет. Полный legacy diagnostic manifest roster должен быть предъявлен отдельно; чтение любого неизвестного historical subclass не обещано. БД не обследованы, отсутствие legacy не предполагается.
- Приняты новые canonical IDs: TimeCommitIssueCode ENUM=31007; PrepareTimeAdvanceSection RECORD=31139; TimeCommitRelationIssue RECORD=31140; TimeSnapshotApplyResult RECORD=20150. Альтернативные 31108/31109 не приняты. Ранее принятые native IDs и 20124/20128/20131 не переназначаются. Runtime-only TimeSectionRefused/validator errors IDs не получают. Это принятие назначений, не evidence runtime registrations/round-trip и не глобальный audit всех внешних хранилищ.
- Новая пара row format/root ещё требует freeze: format1 + root20150 допустим как предложение при подтверждённо неизменной оболочке/encoding; automatic bump не вводится. Самостоятельная serialization support 20128/20131 требует отдельного подтверждённого consumer, не выводится из terminal path.

Остатки: финальная сверка signatures/configuration/node output, encoding API review, полный legacy diagnostic roster и exact новая format/root pair. Реализация/миграции не разрешены этой приёмкой.

**Положение Publication — зафиксировано пользователем 2026-11-21.** Publication является общей инфраструктурной частью ядра Snapshot, а не самостоятельным предметным доменом. Оно обслуживает operation identity/immutable request binding, lifecycle выполнения, транзакционную фиксацию, terminal persistence и exact replay для Snapshot apply, Pack activation и gameplay start. Выражение «владелец Publication» означает владельца этой инфраструктурной части; отдельные чат и каталог application/publication не задают отдельный домен. Snapshot владеет применением готовых изменений и моделью apply result; предметные домены — семантикой своих данных/diagnostics; Artifacts — хранением artifacts и их защитой; DAG — оркестрацией. Зависимость Snapshot → внутренний Publication operation store классифицируется как инфраструктурная связь внутри ядра, но exact capability, nested calls и H2 contracts ещё проверяются. Эта классификация не разрешает произвольные foreign public pipeline calls, не передаёт Publication доменную семантику и не закрывает H2.

2026-11-20. Постановка и вопросы сохранены по поручению пользователя. Статус: OPEN / предложения к согласованию, не code-go. Координатор — Between domain operations. H2 является общей границей, используемой IC-1; не новый девятый контракт. Локальный H3 на готовых SQL-данных принят отдельно.

## Проблема и граница

## Апдейт контракта — сводка ответов 2026-11-20

### Координаторская сверка 2026-11-21 — SIG/DISPATCH в работе

Положение Publication уточнено: инфраструктурная часть Snapshot. После сверки owning-планов к финализации SIG остаются конкретные дельты: (1) Publication должен синхронизировать свой apply port с Snapshot-owned IWorldSnapshotApply[S,R], где S связан с экземпляром; (2) подтвердить ArtifactStagingService keyword record_model и exact identity с record_model store; (3) предъявить проверяемую typed construction configuration W/R/readers/record_model без private introspection; (4) Snapshot предъявляет exact existing apply_snapshot output binding для R. Адресные вопросы направлены Publication/Snapshot. Эти сигнатуры ещё proposal к итоговой приёмке.

DISPATCH: координатор прочитал existing DecodeLimits и boundedCanonicalDecode._Reader. Shared header parser действительно проверяет node/depth/length; proposed read_record_root_id отсутствует. DecodeLimits — dataclass без собственного admission положительных budget значений; контракт нового entry point должен явно назвать место проверки limits, а не считать их автоматически валидными. Root extraction проверяет только внешний record header/type id и структуру оболочки, не canonical validity вложенных полей; полное bounded decode обязательно после выбора reader. Не вводить лишний общий parser или менять формат ради dispatch. Exact limits/error contract и owning encoding review остаются OPEN.

По поручению пользователя фиксируется текущий стейт и следующий проход согласования. **H2 OPEN, не code-go.** Согласие владельцев с направлением не подменяет окончательную приёмку пользователем.

Приняты ранее: reuse TimeSectionRefused без второго carrier; Time-owned validator проверяет набор diagnostics; Registry/Snapshot не копируют Time predicates; H3 и порядок внутренних чтений отдельно приняты.

Сведённое предложение: D — закрытый набор diagnostic types; W — concrete Snapshot result для новых записей; R — закрытый набор читаемых Snapshot roots, включающий W. Publication рекомендует R = прежний root20124 | W без old→new adaptation; Snapshot поддержал. OperationRecord[R]/claims/leases несут читаемый результат; store/ledger/codec, одновременно пишущие и читающие, используют W,R. Exact новые результаты после confirmed rollback сохраняются record_refusal(W); replay возвращает сохранённый R до state reads/handlers. Pack/Gameplay/Cancelled сохраняют свои roots и отдельные правила.

PatchSet и Snapshot сошлись на proposed placement app/composition/snapshotTime/{contracts.py,binding.py}: отдельный TimeSnapshotApplyResult, reuse TimeSectionRefused, один binding registry/result/codec. Назначение владельца и полный construction contract ещё не frozen. TimeRefusalValidator.validate(refusal,expected_request)->None предъявлен; exact API ещё proposed.

Предложенная узкая infrastructure boundary Snapshot → IOperationStore[W,R] ограничена claim/read/terminal persistence и owning SQL/evidence/codec; весь OperationLedger не внедряется, recover/cancel/finish не добавляются в обычный apply. Artifacts подтвердил topology отдельного ledger→leases→store пути для lifecycle, но final nested-call приёмка ещё OPEN.

| Gate | Что свести / закрыть | Владелец |
|---|---|---|
| H2-SIG | Artifacts старые store/ledger[R] согласовать с Publication[W,R]; reader-only leases[R] отличить от concrete adapters[W,R]. Snapshot выбирает final apply[S,R] binding: S у экземпляра либо метода. Единая таблица exact constructors/methods/returns и errors | Publication, Artifacts, Snapshot; PatchSet сверяет registry boundary |
| H2-DISPATCH | Bounded canonical root-tag API owning encoding с exact Input/Output/Error; dispatch по version/root без копии parser или пробных decode. Checksum/unknown/foreign root правила | Publication; encoding owner требуется подтвердить |
| H2-REP | Конкретный список supported format/root/diagnostic manifests, прежний root20124 и новое W; как replay R выходит в DAG. Источники/fixtures отдельно от реально сохранённых БД; неизвестные данные не считаются отсутствующими | Publication, Snapshot |
| H2-IDS | Minimal Time request/issue/enum + W root; collision audit, proposed номера и closure. Старые 20124/20128/20131 не переопределять. OperationRecord persist reachability проверить; runtime refusal/binding/exception не регистрировать без serialization path | Time, PatchSet, Snapshot, Publication |

Следующий порядок: свести signatures → отдельно предъявить root dispatch → поддерживаемые representations → identities и итоговую совместимость. Независимые source inventory допустимы одновременно, зависимые решения не объявляются закрытыми заранее. Нет разрешения на реализацию, migration или изменение storage versions по умолчанию.

### Исходная постановка

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
