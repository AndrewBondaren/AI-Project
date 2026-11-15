# Source — актуальная карта архитектуры ядра

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

Кандидат — pure proof canonical/normalization/atom/union/extraction/matching и request checks, которые не требуют отсутствующей owning admission/IO. Он не создаёт durable result и не подтверждает capture finalization. Зависимость от concrete key adapter должна быть явно отсечена по реальным checks, а не заменена stub. Выделение именно этого среза ещё требует review и точной implementation-матрицы.

До реализации: проверить ответственность каждой роли, exact inputs/errors, полноту prerequisites каждого алгоритма, original root diagnostics, absence of public nested calls и imports границы. Tests автора и independent acceptance разделены. Готовность всего ядра, настройки/CRUD и интеграции не объявлять по этому узкому результату.

Request-specific composition предъявлена в source-core-request-composition.md как DRAFT. Выявлено ограничение: full request admission зависит от owning key adapter; независимый срез охватывает только явно перечисленные pure инварианты/алгоритмы, не admission с пропущенными checks. Следующий рабочий шаг — архитектурный review и выбор конкретного independent subset для implementation-плана; остальные собственные вопросы §5 остаются видимыми. Runtime/tests/independent acceptance этим документом не заявляются.
