# Source — матрица ответственности ядра

2026-11-21. Консолидация существующих решений и критериев, не новые публичные контракты и не разрешение реализации. Порядок: source-core-architecture.md АР-1 → АР-2 → АР-3 → АР-4 → АР-5 → АР-6. Статус всей архитектуры — NOT READY. Наличие строки не означает принятия signature или реализации.

## 1. Как проверять каждую строку

Для каждого класса нужны: точный модуль, одна ответственность, все методы с входом/результатом/ошибкой, constructor dependencies, допустимые эффекты, положительный сценарий и конкретный признак нарушения. Ссылка на signature допустима только на актуальный раздел; при конфликте документов строка не проходит приёмку. Отсутствие факта — OPEN, а не предполагаемый PASS.

Проверка чистоты ответственности включает просмотр всех методов и вложенных calls/imports: нет второго алгоритма того же правила, скрытого IO, mutable состояния между requests, public→public calls, междоменного вызова или выбора следующей публичной операции. Метод реализует одну функцию; последовательные локальные шаги одной операции допустимы. Тест результата не заменяет проверку зависимостей и эффектов. Отрицательные сценарии ниже должны проверять также отсутствие запрещённого действия.

## 2. АР-1: proof

Корень application: `app.application.worldData.sourceVersioning`. Exact модули/signatures — source-core-internal-api.md, source-core-checker-signatures.md, source-core-request-composition.md §1 и source-core-public-boundaries.md §1–3. Статус и evidence существующих A0→D компонентов сохраняются; новые строки не переоткрывают их независимый PASS.

| Класс | Метод и единственная функция | Допустимые зависимости/эффекты | Проверка; конкретное нарушение |
|---|---|---|---|
| SourceDescriptorLookup | definition — найти immutable definition | SourceDescriptorRegistry; pure | Unknown остаётся unknown; default/discovery/write запрещены |
| SourceIdentityKeyAdapter | validate_exact — проверить owning key | Подтверждённая immutable registration; без IO | Missing registration — composition error; permissive успех запрещён; concrete constructor OPEN в INT-TERRAIN |
| SourceWorldChecker | check — сравнить world | Values; pure | Foreign world диагностируется; lookup/repair запрещены |
| SourceIdentityChecker | check — descriptor/category/scope/key admissibility | Lookup и key adapter; pure | Ошибки по исходному path; проекция body/проверка membership запрещены |
| SourceUsageConflictChecker | check — несовместимость refs в одном capture | Typed traversal facts; pure | Historical captures не смешиваются; dedup/repair запрещены |
| SourceProofCanonicalChecker | check — canonical persisted form | Единые value rules/schema; pure | Noncanonical отказ без normalization |
| SourceSelectionChecker | check — fingerprint и допустимость selection | Общие rules и atom index; pure | Bounds отказ без extraction; дублирующиеся одинаковые diagnostics запрещены |
| SourceCaptureMembershipChecker | check — соответствие usage предъявленным mappings | Values/descriptor lookup; pure | Exact relation проверена; pure success не удостоверяет storage durability |
| SourceProofResultValueChecker | check — локальная пригодность предъявленного result | Общие value rules; pure; request composition §1 | Не подтверждает существование bytes или полноту durable closure; exact контракт включить в полноту АР-1 |
| SourceAdmissionRequestChecker | check — проверить SourceProofInput | World/identity/conflict checkers и общий traversal; pure | Все независимые ошибки; успех возвращает три typed origins maps, не None |
| SourceReadRequestChecker | check — проверить SourceProofReadInput | Предыдущие checkers и canonical; pure | Исходный proof не исправляется; origins получены из того же обхода |
| SourceGroupAdmissionRequestChecker | check — проверить все declared groups | World/identity/conflict и общий traversal; pure | Сохраняются group/use indices; раннее прекращение независимых checks запрещено |
| SourceGroupVerificationRequestChecker | check — проверить expected/presented стороны | Зависимости из request composition §1, включая result value checker; pure | Origins относятся к presented стороне; смешение сторон запрещено |
| SourceSelectionRequestChecker | check — проверить select request | Зависимости из request composition §1; pure | Проверяет до extraction; не вычисляет subset/closure |
| SourceProofNormalizer | normalize — canonical grouping declared usage | Values/shared canonical rules; pure | Единый алгоритм; READ repair или durable refs запрещены |
| SourceProofAtomIndex | enumerate — стабильная нумерация atoms | Canonical proof как предусловие; pure | Общая нумерация для потребителей; IO/normalization запрещены |
| SourceProofGroupUnionBuilder | build — union и selections групп | Normalizer/atom index; pure | Exact union и порядок групп; fake closure запрещён |
| SourceProofSelectionExtractor | extract — proof выбранных atoms | Atom index/normalizer; pure | Самостоятельный subset; чтение bytes запрещено |
| SourceProofGroupMatcher | match — соответствие proof/selections ожидаемым groups | Union builder/общие algorithms; pure | Перестановка/подмена request запрещена; не подтверждает closure |
| SourceProofClosureCollector | collect — полный exact Source closure | Переданные через DAG owning данные/evidence; без IO | Нет latest fallback/дочитывания/holds; exact data-input signature OPEN, scoped вариант отозван |
| SourceProofAdmissionPipelineOpenPipeline | admit — одна admission операция | Admission checker → normalizer → collector | Refusal блокирует dependent stages; не создаёт capture |
| SourceProofReadPipelineOpenPipeline | read — одна проверка persisted proof | Read checker → collector | Не вызывает public admit и не исправляет proof |
| SourceProofGroupAdmissionPipelineOpenPipeline | admit_groups — grouped admission | Group checker → union → collector | Не реализует собственный union |
| SourceProofGroupVerificationPipelineOpenPipeline | verify_groups — проверка grouped result | Verification checker → matcher → collector/exact refs comparison | Caller refs не принимаются без проверки |
| SourceProofSelectionPipelineOpenPipeline | select — выделение и проверка subset | Selection checker → extractor → collector | Нет public read/admit и непроверенных refs |

Для пяти owners приняты layout и обязанности; exact data-input/protection и полные constructors остаются OPEN. Единственный внешний caller — согласованный DAG. Owner не получает storage scope. Original request failures, invalid computed postcondition и owning infrastructure failures не смешиваются.

Traversal/occurrence functions не требуют дополнительных классов: извлекают структурно пригодные facts и typed paths; semantic checkers не вызывают. Request checker использует общий traversal, не реализует второй обход. index/project/locate не вычисляют union и не подтверждают authority. Exact functions — source-core-occurrence-mapping.md и request composition; `check` при успехе возвращает tuple трёх maps, пустой успех `((), (), ())`.

## 3. АР-2…АР-5: оставшиеся обязанности

| Класс/обязанность | Метод и граница | Проверка чистоты | Незавершённость прежнего шага |
|---|---|---|---|
| SourceRevisionTransitionBuilder | build(previous, semantic_hash) → SourceRevision; pure | Equal hash сохраняет revision, другой повышает seq; нет IO/projector/commit | Контракт — mutation-contract §2; статус proposal сохраняется |
| Mutation request validation | Проверить весь исходный batch до preparation | Нет частичных writes; не подменять source paths group indices | АР-2: concrete owner, signature, constructor и tests criteria не завершены |
| Mutation batch preparation | Получить provisional SourceRevisionChanges через общий builder | Не выдаёт Applied, не дублирует revision rule | АР-2: concrete owner/method/input/error не завершены |
| SourceRevisionAppender | append immutable transitions через принятый port | Не commit, не semantic policy, не latest selection | АР-2: exact signature/port и входные preconditions не завершены |
| SourceMutationOutcomeResolver | resolve authoritative outcome | Не запускает mutation/takeover; unknown не превращает в refusal | АР-2: exact constructor/input/result/error не завершены |
| SourceRegistryMutationPipelineOpenPipeline | apply — pregame mutation; proposal mutation-contract §8.1 | Confirmed/provisional/unknown различимы; gameplay отказ без перенаправления | АР-2: internal graph и owning phase/terminal binding не завершены |
| SourceMutationRecoveryPipelineOpenPipeline | recover — восстановление исхода; proposal §8.1 | Не replay mutation по одному отсутствию terminal | АР-2: internal graph/recovery grant binding не завершены |
| SourceCaptureCandidateChecker | check — отношения capture candidate | Общие relation rules, без второго membership validator | АР-3: exact inputs/results/errors/constructor не завершены |
| SourceCaptureFinalizer | finalize(witness, lease) — atomic witness finalization | Constructor не finalization; нет собственного SQL/holder engine/partial success | АР-3: внутренний контракт не закрывает acquisition и допустимый nested graph |
| Source revision prune candidate policy | Определить Source revision candidates | Не утверждает foreign reachability по caller bool; не release/GC | АР-4: exact owner/method/facts/decision/errors не завершены |
| Source configuration lifecycle | Различить composition и управляемые settings | Immutable registry не заменяет обязательную CRUD-проверку | АР-5: owner/methods и C/R/U/D либо принятое основание неприменимости не завершены |

SourceRevisionChangeClassifier не добавляется ради сравнения hashes; SourceCaptureAssembler — ради вызова POJO constructor. SourceAdoptionPreflight/SourceCaptureRetentionBinding.adopt исключены по принятому disposition. Не заменять их переименованными wrappers.

## 4. Values и используемые общие классы: обязательная полнота АР-6

Фактическая поимённая инвентаризация Source POJO, полей и собственных методов выполнена 2026-11-22: [source-core-existing-values-inventory.md](source-core-existing-values-inventory.md). Это статическое evidence; shared collaborators и будущие исполнители ещё требуют полного сопоставления. Общий gate не закрывается наличием inventory.

Existing Source identities/revisions/dependencies/capture/proof/input/result/error POJO: каждый отвечает только за собственные immutable значения и локальные инварианты. Методы validation не нормализуют usage, не вычисляют union/closure и не обращаются к application/storage. `_proofValueRules` — единственная реализация общих локальных правил, не второй публичный контракт.

Existing SourceDescriptorRegistry/SourceDescriptorDefinition: immutable definitions и structural constraints; не runtime registration и не owning key projection. SourceRevisionChanges: provisional exact refs, без receipt/scope/committed status. SourceMutationApplied/Refused: подтверждённый outcome по owning evidence, не вычисляемое обещание commit.

Existing CanonicalCodec/content_digest: единое canonical encoding/hash; Source manifests задают регистрации, не второй codec. Existing FieldRef/CheckedPath: типизированная локализация поля, не semantic validation. Existing ValidatorAggregationHelper: request-local агрегация готовых issues, не создание доменных правил или автоматическое устранение одинаковых diagnostics.

Эти групповые записи не заменяют требуемую инвентаризацию каждого concrete POJO/shared класса и его использованных методов. АР-6 должен сопоставить exact модули/поля/методы с accepted spec и G1 evidence, отметить отсутствие дублей и проверить все collaborators каждого constructor. Пока инвентаризация неполна, критерий «для каждого класса» остаётся OPEN. Новые внешние adapters не проектируются вместо владельца; их exact контракт/владелец/условие возврата — source-technical-debt.md.

## 5. Выход проверки

Для каждой строки фиксировать PASS/OPEN/FAIL с местом контракта и evidence проверки. При изменении ответственности обновлять эту матрицу и нормативную signature вместе; междоменные дельты проходят назначенного координатора. АР-6 не принимается по наличию таблицы: все прежние OPEN должны получить конкретные контракты либо явно принятое исключение. Собственные проверки документов/тесты не являются независимой приёмкой.
