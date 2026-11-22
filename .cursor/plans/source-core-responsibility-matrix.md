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
| SourceProofResultValueChecker | check — локальная пригодность предъявленного result | Общие value rules; pure; exact constructor/signature — traversal-contract §5.1 | Не подтверждает существование bytes или полноту durable closure; проект контракта есть, diagnostic mapping ещё требует приёмки |
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

Карточки с exact class names, файлами, методами, функциями и проверками ответственности: source-core-mutation-contract.md §3 «Карточки исполнителей Source» и source-core-capture-prune-configuration.md §4. Предлагаемые имена SourceRegistryMutationRequestChecker и SourceRevisionBatchBuilder заменяют безымянные роли validation/preparation; это design, не новая runtime-поставка. Незавершённые typed operands/constructors остаются видимыми в карточках.

| Класс/обязанность | Метод и граница | Проверка чистоты | Незавершённость прежнего шага |
|---|---|---|---|
| SourceRevisionTransitionBuilder | build(previous, semantic_hash) → SourceRevision; pure | Equal hash сохраняет revision, другой повышает seq; нет IO/projector/commit | Контракт — mutation-contract §2; статус proposal сохраняется |
| SourceRegistryMutationRequestChecker | check — проверить весь исходный batch до preparation | Нет частичных writes; не подменять source paths group indices | Exact constructor/signature/diagnostic mapping — mutation-contract §6; inspect-functions/nullable facts/trace — source-mutation-traversal-contract.md; проект требует приёмки |
| SourceRevisionBatchBuilder | build — получить provisional SourceRevisionChanges через общий builder | Не выдаёт Applied, не дублирует revision rule | АР-2: exact constructor/operand triples/result и проверки заданы в mutation-contract §3; допуск input до builder и programming-error transport отдельно, проект ещё не принят |
| SourceRevisionAppender | append immutable transitions через принятый port | Не commit, не semantic policy, не latest selection | АР-2: exact signature/port и входные preconditions не завершены |
| SourceMutationOutcomeResolver | resolve authoritative outcome | Не запускает mutation/takeover; unknown не превращает в refusal | АР-2: exact constructor/input/result/error не завершены |
| SourceRegistryMutationPipelineOpenPipeline | apply — pregame mutation; proposal mutation-contract §8.1 | Confirmed/provisional/unknown различимы; gameplay отказ без перенаправления | АР-2: internal graph и owning phase/terminal binding не завершены |
| SourceMutationRecoveryPipelineOpenPipeline | recover — восстановление исхода; proposal §8.1 | Не replay mutation по одному отсутствию terminal | АР-2: internal graph/recovery grant binding не завершены |
| SourceCaptureCandidateChecker | check — отношения capture candidate | Общие relation rules, без второго membership validator | Exact inputs/results/constructor и критерии — capture-prune-configuration §1; shared relation helper — проект дельты, не independent PASS |
| SourceCaptureFinalizer | finalize(witness, lease) — atomic witness finalization | Constructor не finalization; нет собственного SQL/holder engine/partial success | АР-3: внутренний контракт не закрывает acquisition и допустимый nested graph |
| SourceRevisionPrunePolicy | evaluate(requested, latest) — исключить latest из проверенных object revision candidates | Не утверждает foreign reachability по caller bool; не release/GC | АР-4: exact pure signature/предусловия/результат заданы в capture-prune-configuration §2; public missing/pruned errors и confirm binding отдельно |
| Source configuration lifecycle | Различить composition и управляемые settings | Immutable registry не заменяет обязательную CRUD-проверку | АР-5: owner/methods и C/R/U/D либо принятое основание неприменимости не завершены |

SourceRevisionChangeClassifier не добавляется ради сравнения hashes; SourceCaptureAssembler — ради вызова POJO constructor. SourceAdoptionPreflight/SourceCaptureRetentionBinding.adopt исключены по принятому disposition. Не заменять их переименованными wrappers.

## 4. Values и используемые общие классы: обязательная полнота АР-6

Фактическая поимённая инвентаризация Source POJO, полей и собственных методов выполнена 2026-11-22: [source-core-existing-values-inventory.md](source-core-existing-values-inventory.md). Это статическое evidence; shared collaborators и будущие исполнители ещё требуют полного сопоставления. Общий gate не закрывается наличием inventory.

Existing Source identities/revisions/dependencies/capture/proof/input/result/error POJO: каждый отвечает только за собственные immutable значения и локальные инварианты. Методы validation не нормализуют usage, не вычисляют union/closure и не обращаются к application/storage. `_proofValueRules` — единственная реализация общих локальных правил, не второй публичный контракт.

Existing SourceDescriptorRegistry/SourceDescriptorDefinition: immutable definitions и structural constraints; не runtime registration и не owning key projection. SourceRevisionChanges: provisional exact refs, без receipt/scope/committed status. SourceMutationApplied/Refused: подтверждённый outcome по owning evidence, не вычисляемое обещание commit.

Existing CanonicalCodec/content_digest: единое canonical encoding/hash; Source manifests задают регистрации, не второй codec. Existing FieldRef/CheckedPath: типизированная локализация поля, не semantic validation. Existing ValidatorAggregationHelper: request-local агрегация готовых issues, не создание доменных правил или автоматическое устранение одинаковых diagnostics.

Эти групповые записи не заменяют требуемую инвентаризацию каждого concrete POJO/shared класса и его использованных методов. АР-6 должен сопоставить exact модули/поля/методы с accepted spec и G1 evidence, отметить отсутствие дублей и проверить все collaborators каждого constructor. Пока инвентаризация неполна, критерий «для каждого класса» остаётся OPEN. Новые внешние adapters не проектируются вместо владельца; их exact контракт/владелец/условие возврата — source-technical-debt.md.

## 5. Выход проверки

### Явная классификация зависимостей, 2026-11-22

«Собственная» означает незавершённую работу Source, которую нельзя объяснять ожиданием другого домена. «Внешняя» означает конкретный owning контракт, который Source не назначает самостоятельно. В смешанных строках части разделены; внешний долг не блокирует описание собственной ответственности, инвариантов и отрицательных сценариев. Он блокирует только зависимый binding/реализацию. Запрет искусственных локальных implementation-срезов сохраняется отдельно от этой классификации.

| Класс / пункт | Собственная часть — владелец Source | Внешняя зависимость / владелец | Что именно нельзя завершить без неё |
|---|---|---|---|
| IdentityChecker / IdentityKeyAdapter, АР-1 | Descriptor/category/scope/key rules, диагностика, pure key-port и композиция | INT-TERRAIN: owning key contract конкретного descriptor; Terrain только для своего descriptor | Concrete adapter и production admission данного descriptor; не общие Source rules |
| Request checkers, traversal, occurrence maps, АР-1 | Exact functions, paths, aggregation, result relations и tests criteria | Нового foreign контракта для этих правил нет; existing validation helpers переиспользуются | Собственная детализация не зависит от X-READ; typed imports shared helpers надо проверить, не перепроектировать |
| Normalizer/atom index/union/extractor/matcher, АР-1 | Все pure алгоритмы, предусловия, ошибки и единственность реализации | Existing codec/value contracts; новый foreign IO не требуется | Не смешивать отсутствие durable reader с отсутствием pure algorithm design |
| ClosureCollector и пять public proof owners, АР-1 | Source witness/capture/version/membership semantics, full closure v1, origins, postcondition error transport | X-READ: Artifacts — physical read Input/Output/Error; publication infrastructure — authority/retention; producer полного перечислимого набора ещё не назван, назначение через координатора | Exact materialized input, collector signature/constructor и сквозной production proof result. Не разрешает hidden IO. Подробности — source-closure-operands-2026-11-22.md §§1–5 |
| MutationRequestChecker, АР-2 | Request invariants, paths, relation errors и их mapping | Owning key validation только для соответствующего descriptor | Pure batch validation надо закончить в Source; внешняя key integration — отдельный binding |
| RevisionTransitionBuilder / RevisionBatchBuilder, АР-2 | Revision rule, batch correspondence, provisional result; exact operand triples заданы в mutation-contract §3. Проверка live/tombstone допуска предшествует builder | INT-TERRAIN либо иной owning body domain: semantic projector/hash и format evidence | Concrete получение semantic evidence; pure builder signature от foreign carrier не зависит |
| RevisionAppender, АР-2 | Exact Source transition/store contract, append-only инварианты, idempotency/conflict | INT-WRITER: owning data writer + Snapshot/publication — допустимая атомарная write boundary | Production atomic writer binding; Source store schema/метод не определяется чужим writer автоматически |
| MutationOutcomeResolver / recovery owner, АР-2 | Source outcome/error distinctions, request correlation, запрет автоматического replay mutation, safe log projection | INT-ARTIFACTS-TERMINAL: publication/Artifacts — terminal registration/codec/read и recovery grants | Exact receipt/grant transport, reopen/replay integration; не создание Source outcomes и правил их различения |
| Public mutation apply, АР-2 | Pregame-only ограничение, post-game refusal без redirect, внутренние Source обязанности | INT-WRITER/INT-DAG phase boundary: authoritative phase reader/guard и serialization; конкретный owning метод ещё не подтверждён через координатора | Проверка фазы и атомарность с gameplay transition; caller bool не authority |
| CaptureCandidateChecker, АР-3 | Exact relation input/result/errors и reuse membership rules | Owning materialized content/evidence требуется на границе получения данных | Pure candidate relation contract надо закончить в Source; reader не определяет этот алгоритм |
| CaptureFinalizer, АР-3 | Witness identity/conflict/replay semantics, finalization store contract и допустимый собственный call graph | INT-ARTIFACTS-FORMAT/RETENTION + publication: physical registration, writer/retention/commit boundary | Сквозной atomic finalization и public acquisition binding; Source constructor не заменяет evidence |
| RevisionPrunePolicy, АР-4 | Exact candidates/facts/decision/errors, latest/tombstone/history rules | INT-ARTIFACTS-RETENTION: Artifacts holders/GC; Source root release/usage binding согласуется через координатора | Authority deletion/release и atomic confirm. Pure Source candidates не требуют выдуманного held/free bool |
| Descriptor configuration, АР-5 | Lifecycle собственной конфигурации, C/R/U/D либо обоснование неприменимости, конкретные классы/методы | Активного foreign блокера для определения этой границы не установлено | Это собственная незавершённость Source, не ожидание Lifecycle или Snapshot |
| Source POJO и общие predicate owners, АР-6 | Методы локальной validation, инварианты, уникальность правил, typed diagnostics | Existing shared ArtifactRef/identity/diagnostics/codec; владельцы сохраняются | Проверка совместимости existing типов, не новое согласование самого факта их использования; новые foreign поля без контракта не добавляются |

Внешние записи раскрываются в source-technical-debt.md; эта таблица указывает потребителя и ограничение, не дублирует owning contracts. Отменённые adopt/collect_for_adoption и Snapshot → Source не являются зависимостью, которую предстоит восстановить. Time/Lifecycle nodes не ждут завершения Source. Отсутствие назначенного producer/phase метода явно означает OPEN конкретного binding, а не право Source назначить владельца за другие домены.

Для каждой строки фиксировать PASS/OPEN/FAIL с местом контракта и evidence проверки. При изменении ответственности обновлять эту матрицу и нормативную signature вместе; междоменные дельты проходят назначенного координатора. АР-6 не принимается по наличию таблицы: все прежние OPEN должны получить конкретные контракты либо явно принятое исключение. Собственные проверки документов/тесты не являются независимой приёмкой.
