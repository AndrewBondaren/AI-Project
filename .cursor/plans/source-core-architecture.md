# Source — актуальная карта архитектуры ядра

## Консолидированная архитектура — текущая работа, 2026-11-16

**Статус: DRAFT целого ядра; не принято для новой реализации.** Пользователь запретил локальные срезы и потребовал архитектуру первым этапом. Этот раздел задаёт актуальную архитектурную очередь; прежние рекомендации ниже выбрать независимый subset больше не исполняются. G1.1/G1.2 и A0→D учитываются как поставленные части. Наличие части кода не завершает архитектуру остальных обязанностей.

### Папки, владельцы и допустимые эффекты

Все пути относительно `backend/app`. Source владеет своими values, proof semantics и revision history. Значения чужих объектов, их semantic projection и запись принадлежат owning-доменам. Новые имена в таблице — proposals; exact signatures берутся только из указанных контрактов, не из догадок по названию.

| Папка | Компоненты и единственная функция | Разрешённые зависимости / эффекты | Отказ в приёмке |
|---|---|---|---|
| dataModel/sourceVersioning | Existing identities, revisions, capture/proof, inputs/results/errors; `_proofValueRules` — общие локальные правила | Только values/shared validation; без IO и application imports | Второй DTO того же смысла, mutable nested value, повтор правила в checker |
| application/worldData/sourceVersioning/encoding | Source proof/request manifests | Existing CanonicalCodec/content_digest; pure | Второй codec/hash, случайные type IDs, caller-supplied schema |
| …/contracts | SourceDescriptorLookup.definition(key); SourceIdentityKeyAdapter — отдельная проверка owning key | Immutable registry; подтверждённый key contract; no writes | Lookup создаёт definition либо permissive fallback заменяет отсутствующий adapter |
| …/proof/validation | World, identity, usage conflict, canonical, selection, membership checkers — каждый свой инвариант | Existing values, shared rules/paths/issues; no IO | Normalization/lookup latest/holds внутри checker, дублирование правил |
| …/proof/validation/requests | Пять request checkers: check(request) → SourceFailure либо None | Общие checkers; original root и indices; no transformation/IO | Mode dispatcher, потеря независимых diagnostics, запуск преобразования после refusal |
| …/proof | SourceProofNormalizer.normalize; AtomIndex.enumerate; GroupUnionBuilder.build; SelectionExtractor.extract; GroupMatcher.match | Проверенные inputs; shared алгоритмы; pure | Несколько implementations union/atom order, synthetic durable refs |
| …/proof/closure и read bindings | SourceProofClosureCollector — полный exact durable closure; read binding — проверенное чтение | Подтверждённые Source/Artifacts read ports; read IO | Latest вместо exact, неполный closure, public READ как вложенный вызов |
| …/revision | SourceRevisionTransitionBuilder — вычисление revision по previous и semantic evidence | Existing revision/hash values; pure | Commit, projector или самостоятельный выбор latest |
| …/mutation | Batch validation/preparation, scoped apply, outcome resolution — отдельные владельцы | Typed prepared changes; подтверждённые writer/terminal ports | Один service скрывает preparation/apply/recovery; provisional выдаётся как committed |
| …/capture | Candidate relation checks; SourceCaptureFinalizer.finalize — atomic witness finalization | Общие relation checks, exact read/retention binding | Constructor объявлен finalization; второй mapping validator; fabricated witness |
| …/capture/adoptionPreflight.py (proposal) | SourceAdoptionPreflight.collect_for_adoption — read-only preflight | Borrowed scope/collector, bind/reset | Acquire или собственный commit в preflight |
| …/capture/retentionBinding.py (design) | SourceCaptureRetentionBinding.adopt — acquire после повторной проверки | Подтверждённый borrowed scope; acquire, без outer commit | Пропущенная repeat check, отдельный UOW; scoped call без принятого DAG решения |
| …/operations | Отдельный public owner каждой операции | Собственные internal collaborators; прямой DAG caller после согласования | Public→public вызовы, mode switch, внешняя оркестрация |
| db/repositories/sqlite/sourceVersioning (proposal) | Exact revision/witness persistence adapters | Принятые scoped DB ports; только оговорённые effects | Новый transaction/receipt/holder engine, обход owning writer |

Это не окончательный roster mutation/prune/configuration классов: их exact gaps перечислены ниже. Пока хотя бы один такой gap остаётся, вся архитектура не принимается.

### Публичные границы и последовательности

Proof public owners — пять отдельных классов и signatures из source-core-public-boundaries.md §1: admit(SourceProofInput), read(SourceProofReadInput), admit_groups(SourceProofGroupsInput), verify_groups(SourceProofGroupsVerifyInput), select(SourceProofSelectInput). Results — existing SourceProofResult/SourceProofGroupsResult либо SourceFailure. Все read-only; scope/codec/operation flags в public input не вводятся. Разделение старого общего pipeline требует явной финальной контрактной дельты; оба варианта одновременно не реализуются.

Вложенные цепочки: request validation → соответствующий pure algorithm (для read отсутствует) → exact capture/closure evaluation → result. Отказ отменяет только зависимые стадии; доступные независимые checks агрегируются. VERIFY дополнительно сверяет exact union, selections и предъявленный closure. ADMIT не создаёт capture. Shared collector не вызывает public READ. Точные request constructors и порядок diagnostics — source-core-request-composition.md §§1–4; будущие private traversal функции не заменяют эти контракты универсальным context.

Mutation public proposals — отдельные apply и recover из source-core-mutation-contract.md §8.1. Preparation возвращает provisional changes, только подтверждённый terminal даёт Applied/Refused. Новая исполняющая попытка — pregame-only; historical terminal replay после gameplay допустим по immutable binding. После gameplay commit принадлежит Snapshot. Source не проектирует новый scoped маршрут для обхода DAG-запрета.

Capture finalize остаётся internal `finalize(SourceCaptureWitness, *, lease: OperationLeaseRef) → SourceCaptureRef | SourceFailure` по spec. Публичный capture acquisition этим не определён. Coverage/preflight SRP relocation — отдельная принимаемая дельта S1/S2, не разрешение междоменных calls. Ни одного нового DAG NodeId эта архитектура не назначает.

### Открытые решения целой архитектуры и порядок их завершения

**Решение пользователя 2026-11-17:** граница original-request validation / collector validation принята; нормативная запись решения — source-core-public-boundaries.md, раздел ошибок публичной операции. Пользовательские diagnostics принадлежат request checker; invalid computed proof — нарушение postcondition; durable authority/membership/availability/closure повторно проверяются внутри scope. Выбор ответственности больше не OPEN. Exact error transport и синхронизация spec остаются до приёмки; read lifetime и occurrence-mapping delta этим решением не закрыты.

**Occurrence mapping, 2026-11-17:** [source-core-occurrence-mapping.md](source-core-occurrence-mapping.md) содержит конкретный proposal функций и обязательных typed origins для collector. Нет нового public DTO, повторного request traversal или union/subset. SourceProofGroupProjection не дублируется. Остаток этого пункта теперь — приёмка diagnostic semantics и signature delta со всеми internal callers; это не уже выполненная интеграция и не закрытие всего АР-1.

**Консолидация АР-1, 2026-11-16:** Identity/Selection proposals теперь сведены непосредственно в source-core-checker-signatures.md. Result value relations имеют одного владельца predicates и отдельный SourceProofResultValueChecker в source-core-traversal-contract.md §5.1; его dependency добавлена только GroupVerification request checker. Error mapping этих relations требует явной приёмки уточнения §11.3 spec. Для public read найден existing SqliteArtifactScope.read_scope, точный внешний вопрос вынесен в INT-SOURCE-READ-LIFETIME. Собственный незакрытый контракт Source — occurrence-preserving provenance для collector и его error boundary; его нельзя подменять внешним долгом или mapping по первому совпавшему ref. Ранее перечисленные gaps ниже читаются с этим уточнением, а не как отсутствие подготовленных proposals.

**Детализация SRC-AR-04:** source-core-request-composition.md и [source-core-traversal-contract.md](source-core-traversal-contract.md) содержат proposals верхнего и leaf/root/group обхода, immutable tuples, RootT/path и trace пяти callers. Local UUID/descriptor/witness rules выделены в единственные будущие dataModel predicates; structural traversal их не вызывает. Выявлены необходимые адресные дельты Identity checker (identity независимо от revision) и Selection checker (готовые facts вместо повторного обхода). Они описаны в §4 нового документа, не реализованы. До закрытия SRC-AR-04 нужны их консолидация/приёмка и единственный владелец result value relations; исходный ref без semantic допуска по-прежнему запрещён для conflict/codec. Архитектурный остаток не переносится в implementation.

**Принята форма результата traversal:** immutable facts + existing diagnostics, без callbacks/event stream. Traversal не запускает semantic checks; request checker не дублирует обход и отвечает за порядок проверок/SourceFailure. Решение закреплено в source-core-request-composition.md §2; exact signatures и structural leaf boundary ещё нужны до закрытия SRC-AR-04.

**Решение по traversal 2026-11-16:** пользователь выбрал вариант 2 — strict root boundary и typed обход известных ветвей с сохранением пригодных leaves/исходных indices. Полная предварительная semantic validation и универсальный recursive engine не выбираются. Разделение traversal/checkers/request aggregation/operation owner зафиксировано в source-core-request-composition.md §1. SRC-AR-04 остаётся открытым до exact function contracts; их нельзя откладывать до кода. Это решение внутри целой архитектуры, не новый локальный срез.

**Прогресс АР-1:** в source-core-public-boundaries.md §2 добавлены обязательные pure constructor dependencies пяти owners и таблица error boundaries. При сверке с spec §12.1 выявлены три незакрытые архитектурные связи: public read lifetime при scope-free API; единый владелец request/persisted проверки без duplicate diagnostics; typed original-request provenance после normalization/union при входе collector через SourceProofReadInput. АР-1 остаётся открытым именно по этим пунктам, а не по общему статусу чужих доменов. Следующее действие — конкретизировать эти связи в архитектуре до перехода к реализации. Таблица dependency с OPEN read binding не является готовым constructor contract.

| Порядок | Собственное решение Source, которое нужно предъявить | Что уже есть / внешний предел |
|---|---|---|
| АР-1 | Завершить единую таблицу public/internal owners, exact constructors и error boundary; свести proof operation delta и request traversal | Proof POJO и A0→D приняты; public/request signatures предложены. Owning key binding — INT-TERRAIN, не fake success |
| АР-2 | Довести revision/mutation/recovery до полного roster классов, методов, prepared values и единого error contract | SourceRevisionChanges/outcomes и apply/recover proposals есть; terminal/phase/writer ports — INT-ARTIFACTS-TERMINAL/INT-WRITER |
| АР-3 | Определить Source capture acquisition boundary и relation/finalization ownership без дублирования | Internal finalize принят как design; внешний acquisition authority не назначать Source без согласования |
| АР-4 | Определить собственные revision/prune candidate inputs/results/errors, отделить eligibility от авторитетного освобождения | Exact usage/prune owner и root/hold binding — INT-ARTIFACTS-RETENTION; bool free не authority |
| АР-5 | Определить lifecycle Source configuration и отдельно все C/R/U/D данных и настроек; назвать concrete owners/methods/POJO либо предъявить исключение пользователю | Immutable registry не является автоматически принятым CRUD исключением |
| АР-6 | Свести все решения в единую актуальную редакцию, проверить обязательную матрицу и последовательность реализации целого ядра | Не объявлять PASS по одному наличию таблиц или tests принятых частей |

АР-1…АР-6 — работа над одной архитектурой, не локальные implementation-срезы. Следующее действие — завершать АР-1, не реализовывать ещё один checker. Отсутствие final public signatures или constructor/error facts — конкретное основание отказа в архитектурной приёмке, а не повод заполнить их placeholders.

### Условия приёмки и перехода к коду

Для каждого класса, включая используемые existing классы, должны быть указаны exact signature/вход/выход/ошибка, единственная обязанность, dependencies/effects и отрицательный критерий. Сверяются все три запрета DAG, public/internal и вложенные calls, POJO/error ownership без дублей, C/R/U/D отдельно для данных и настроек и принятый порядок. Внешний неизвестный binding описывается как точная зависимость с владельцем, но собственная незавершённая операция не скрывается внешним долгом. Только после приёмки целого архитектурного результата детализация implementation-порядка из основного плана становится исполнимой. Неизвестный контракт на зависимом шаге останавливает его; новые локальные срезы вместо него запрещены.

**Актуальный итог A0→D, 2026-11-16: независимый PASS, findings отсутствуют.** Evidence и ограничение проверки Git зафиксированы в source-core-invariants-implementation.md. Следующие записи о предстоящем ревью этого среза исторические. Полный G1, production traversal, CRUD и внешние интеграции остаются открытыми.

**Обновление среза A0→D:** после явного принятия пользователем scope/порядка реализованы общие POJO/checker rules и одна bounds-ошибка на selection. Собственные tests/typing прошли; независимая приёмка ещё не выполнена. Предшествующие замечания о непринятой дельте A0 ниже — история до этого решения. Приёмка всей архитектуры и интеграций этим не объявляется.

**Ревью 2026-11-15 и последующие проверки 2026-11-16:** [отчёт](source-core-architecture-review-2026-11-15.md). R1 исправлен facts API без repaired usage; R2 — выбором узкого [independent subset](source-core-independent-slice.md). Пять application-компонентов написаны, но не приняты. После CHANGES REQUIRED предложен A0 для единой реализации общих POJO/checker правил. Исправленный план требует повторного ревью и принятия до продолжения кода; собственные тесты не подтверждают соблюдение допуска и не являются independent acceptance.

2026-11-15. Единая навигационная карта решений и статусов; **архитектура в целом ещё не принята**. Основной план — world-source-versioning.md. Этот документ не превращает proposals в принятые контракты; детальные signatures остаются в указанных ниже спецификациях. Реализация только после приёмки конкретного среза через implement-plan.

## 1. Назначение и границы

Source фиксирует identity/revisions исходных объектов, согласованные captures и зависимости результатов; проверяет proof и определяет полный durable closure для удержания/восстановления. Смысл данных и semantic projection принадлежат owning-домену. Source не рассчитывает Terrain/Hydrology, не собирает Pack, не назначает DAG маршруты и не реализует второй transaction/holder/GC механизм.

Одна ответственность — одна реализация; один метод — одна функция. Public operation owner может выполнять внутренние стадии одной атомарной операции, но не управляет самостоятельными публичными операциями. Никаких permissive adapters, legacy conversion и mirror DTO.

## 2. Карта папок и владельцев ответственности

Пути относительно backend/app; proposed файлы не означают существующую реализацию.

| Область | Компоненты / одна ответственность | Статус |
|---|---|---|
| dataModel/sourceVersioning | Existing identity/revision/ref/capture/proof/input/result/error POJO; локальные structural инварианты | G1.1 independent PASS; semantic diagnostics transition ещё не реализован |
| application/worldData/sourceVersioning/encoding | Existing proof canonical manifest и отдельный request manifest; shared codec | G1.2 proof encoding independent PASS; request registration — отдельный Source 2 scope |
| …/contracts | SourceDescriptorLookup: immutable definition lookup; key validation port отдельно | API proposal; production owning binding — техдолг |
| …/proof/validation | WorldChecker, IdentityChecker, UsageConflictChecker, ProofCanonicalChecker, SelectionChecker, CaptureMembershipChecker | Exact signatures предложены; по одному инварианту, без IO |
| …/proof | Normalizer; AtomIndex; GroupUnionBuilder; SelectionExtractor; GroupMatcher | Exact pure API proposal, общие алгоритмы без дублирования |
| …/operations | Пять отдельных proof operation owners | Разделение согласовано, exact names/constructor wiring и контрактная дельта ещё не frozen |
| …/revision | RevisionTransitionBuilder: previous+semantic hash → revision | Proposal; не пишет историю и не вызывает projector |
| …/mutation | Валидация request, внутренний revision batch, применение через port, outcome resolution — отдельные обязанности | Proposal; public apply/recover и outcome distinctions описаны, не приняты целиком |
| …/capture | Candidate checks и atomic finalizer; retention adoption отдельно | Spec задаёт internal finalize/adopt; новые разделения ещё подлежат сверке |
| …/proof/closure и read ports | Exact чтение/closure evaluation | Архитектура IO-интеграции, не pure ядро; не выдаёт fake refs |
| db/repositories/sqlite/sourceVersioning | Scoped persistence adapters | Отложено; не выбирать за Snapshot transaction binding |

## 3. Что согласовано, что только предложено

**Согласовано пользователем:** ядро до интеграций; single responsibility; направление пяти отдельных proof operations; existing CheckedPath внутри Source без изменения других доменов; SET для Terrain membership. G1.1/G1.2 имеют отдельный independent PASS. Полный Source runtime не принят.

**Предложено, не утверждено автоматически:**

- Шесть checker signatures, включая отдельный world checker.
- Pure signatures и представление одного atom через existing SourceCaptureUsage.
- Исключить SourceRevisionChangeClassifier, если он лишь дублирует hash comparison revision builder.
- Не создавать SourceCaptureAssembler только ради вызова конструктора.
- SourceRevisionChanges как internal provisional payload; Applied/Refused только для подтверждённых terminal outcomes.
- Public apply/recover union, где SourceFailure означает preflight, а SourceMutationRefused — committed refusal.
- Вынести check_coverage и adoption preflight из смешанных classes; требуется явная S1/S2 дельта.

Эти proposals не изменяют существующий public proof wire/API, shared terminal union или error roster. При консолидации нельзя читать ранние таблицы ролей как уже принятую реализацию лишних wrappers.

## 4. Единственный источник каждой детализации

| Предмет | Документ |
|---|---|
| Принятые proof values/semantics/errors/wire | source-proof-v2-contract-spec.md, включая §13 S1/S2 |
| Foundation implementation/evidence | source-g1-values-canonical-implementation.md; source-g1-foundation-review-2026-11-15.md |
| Обоснование разделения обязанностей | source-core-responsibility-decomposition.md; последующие предложения исключить wrappers перечислены в §3 этой карты |
| Public proof операции | source-core-public-boundaries.md |
| Pure algorithm signatures и path approach | source-core-internal-api.md |
| Exact checker signatures | source-core-checker-signatures.md; уточняет ранние общие таблицы validator |
| Request-specific constructors, traversal/aggregation и pure sequencing | source-core-request-composition.md; full key admission отделена от независимого pure-среза |
| Revision/mutation/recovery и outcome delta | source-core-mutation-contract.md; staging design — источник истории, не альтернативная актуальная дельта |
| Capture/prune/configuration границы | source-core-capture-prune-configuration.md |
| Все интеграционные долги и условия возврата | source-technical-debt.md |

## 5. Оставшаяся собственная работа ядра

| Вопрос | Конкретный выход | Что нельзя подменить интеграционным долгом |
|---|---|---|
| Pure validation composition | Exact request-specific traversal/aggregation и constructor graph, сохранение original paths/indices, отсутствие дублирования checks | Source должен определить свои checks; неизвестный Terrain adapter лишь ограничивает dependent admission |
| Mutation batch | Exact Source-owned validation/preparation input/result и применение revision builder без provisional Applied | Не ждать Snapshot для определения смысла Source outcomes |
| Capture boundary | Отличить construction/relations от finalization evidence; установить собственный публичный вход, если он нужен | Internal finalize signature не доказывает готовность public acquisition |
| Prune candidate policy | Source exact revision facts и error conditions, без foreign holders DTO | Не вводить bool free как caller authority; external usage/prune execution отдельно |
| Configuration lifecycle | Различить static composition и управляемые данные/settings, выполнить обязательные CRUD критерии либо предъявить конкретное обоснование границы | Immutable POJO не является автоматическим CRUD исключением |
| Contract deltas | Явно принять/отклонить новые signatures, wrappers removal, S1/S2 relocations и mutation error proposals | Не объявлять направления «Ок» приёмкой всех последующих деталей |

## 6. Ближайший ограниченный срез для архитектурной проверки

После R2 выбран конкретный кандидат: [Source core independent slice](source-core-independent-slice.md) — world/conflict/canonical/selection checkers и atom enumeration. После ревью implementation-плана предложен A0: Source dataModel владеет повторяющимися локальными правилами, POJO и checkers используют одну реализацию; перечень функций/файлов — implementation-план §3.A0. Это дельта на принятие, не уже выполненный рефакторинг. Normalizer/union/extractor/matcher и request-wide checks исключены, их прежние prerequisites не ослаблены. В constructor graph среза нет owning key adapter. Срез не создаёт durable result и не подтверждает capture finalization; CAPTURE_ID_CONFLICT остаётся witness/finalization.

До реализации: проверить ответственность каждой роли, exact inputs/errors, полноту prerequisites каждого алгоритма, original root diagnostics, absence of public nested calls и imports границы. Tests автора и independent acceptance разделены. Готовность всего ядра, настройки/CRUD и интеграции не объявлять по этому узкому результату.

Request-specific composition предъявлена в source-core-request-composition.md как DRAFT. Full request admission зависит от owning key adapter; независимый срез охватывает только явно перечисленные pure инварианты/алгоритмы, не admission с пропущенными checks. AtomIndex не обещает defensive отказ при нарушенном canonical prerequisite; запрет его вызова после ошибок checker — обязанность будущего production caller. Следующий рабочий шаг — повторное ревью исправленного implementation-плана с A0; остальные собственные вопросы §5 остаются видимыми. Исторические tests пяти компонентов не являются приёмкой этой редакции.
