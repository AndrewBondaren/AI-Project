# Source core — декомпозиция ответственности

**Приоритет 2026-11-21:** актуальный roster и критерии — source-core-responsibility-matrix.md, порядок — source-core-architecture.md АР-1…АР-6. Пять public owners уже приняты. SourceCaptureRetentionBinding.adopt и adoption preflight исключены из target по source-s1-s2-adoption-disposition.md. Описания первоначальных кандидатов ниже — история обоснования; они не разрешают реализовывать отменённые классы или локальные срезы. Classifier/assembler не добавляются только ради hash comparison/POJO construction: уточнения — mutation-contract §2 и capture-prune-configuration §1.

2026-11-15. **Разделение ответственности согласовано пользователем** ответом «Ок» после подробного объяснения пункта 1. Основание: world-source-versioning.md, решения пользователя «одна ответственность — одна реализация; один метод — одна функция», ядро до интеграций. Это согласие с декомпозицией обязанностей, не приёмка всей архитектуры, не принятая смена публичного API и не разрешение кода. Имена классов остаются кандидатами; полные signatures, публичные операции и implementation-срез принимаются следующими пунктами архитектуры. Принятые proof POJO/semantics и G1.1/G1.2 сохраняются.

## 1. Что разделяем

Единица ответственности — конкретный инвариант, преобразование или одна атомарная операция Source. Не количество строк или методов. Несколько последовательных внутренних шагов допустимы для одной атомарной операции; управление самостоятельными операциями остаётся DAG. Не создавать отдельные классы для тривиальных действий без собственного инварианта.

| Прежняя проектная группировка | Конфликт / риск | Предлагаемая граница |
|---|---|---|
| SourceProofPipelineOpenPipeline с пятью методами | Admission, persisted read, group admission, verification и selection объединены под общим owner | Пять operation owners, каждый отвечает за одну существующую публичную операцию. Точные public names/пути и изменение интерфейса — отдельное согласование, старую сигнатуру молча не менять |
| SourceProofValidator | Одновременно descriptor admission, persisted order, selection bounds и проверка decoded capture | Отдельные проверяющие компоненты по инвариантам; request-specific стадии только обходят свой исходный request и собирают diagnostics |
| SourceProofNormalizer с private normalization в selector | Риск двух реализаций canonical grouping | Один normalizer; single/group admission используют один алгоритм без повторного кода |
| SourceProofSelector: union_groups/select/match_groups | Построение union, извлечение subset и проверка соответствия — разные преобразования | Group union builder, selection extractor, group matcher; общий enumeration атомов один |
| SourceProofReadBinding | Capture read, collection read и object integrity скрыты в одном binding | Отдельные read/verification ports по виду значения. Concrete backend/dispatch — интеграция |
| SourceCaptureFinalizer | Атомарность смешивается с codec, SQL и holder implementation | Один владелец атомарной finalize-операции; проверка кандидата и инфраструктурные реализации отделены. Транзакцию нельзя разрезать на независимо коммитящие стадии |
| Общий mutation/recovery service | Новое изменение и восстановление исхода имеют разные основания | Отдельные владельцы подготовки revision и восстановления outcome; не повторять mutation автоматически при unknown outcome |

## 2. Pure proof-компоненты

Все кандидаты ниже internal, под `app.application.worldData.sourceVersioning`. Нет IO, holds, DB, owning CRUD, public nested calls или выбора следующей публичной операции. Метод в таблице обозначает одну функцию; точные typed signatures формируются в пункте 2 архитектуры, не через Any/dict. Каждый алгоритм имеет ровно одного владельца.

| Папка / класс-кандидат | Метод / единственная функция | Допустимые зависимости | Проверка / основание отказа |
|---|---|---|---|
| contracts / SourceDescriptorLookup | definition: найти immutable descriptor definition | existing SourceDescriptorRegistry | Unknown не превращается в default; отказ при runtime discovery или записи |
| proof/validation / SourceIdentityChecker | check: проверить соответствие identity descriptor | descriptor lookup, key-validation port | World/category/scope/key checks без latest; отказ при owning body projection |
| proof/validation / SourceUsageConflictChecker | check: выявить несовместимые revisions внутри одного capture usage | Source values | Исторические revisions между captures допустимы; отказ при dedup/repair входа |
| proof/validation / SourceProofCanonicalChecker | check: проверить persisted canonical форму | existing canonical codec/schema | Не исправляет proof; отказ при вызове normalization с заменой входа |
| proof/validation / SourceSelectionChecker | check: проверить fingerprint и индексы selection | canonical codec/schema, atom index | Чужой fingerprint/out-of-bounds отвергается; не строит subset |
| proof/validation / SourceCaptureMembershipChecker | check: проверить usage против предъявленных witness/capture/collection bodies | Source values, descriptor lookup | Exact world/mapping/membership; отказ при утверждении durability без IO evidence |
| proof / SourceProofNormalizer | normalize: получить canonical proof из допустимого declared usage | canonical codec/schema | Единственный grouping/dedup/order алгоритм; отказ при persisted READ repair или выдаче durable refs |
| proof / SourceProofAtomIndex | enumerate: получить стабильную нумерацию dependency atoms proof | Source values/canonical schema | Union/selection/matching используют одинаковую нумерацию; отказ при owning storage lookup |
| proof / SourceProofGroupUnionBuilder | build: получить общий proof и selections групп | normalizer, atom index | Exact union и исходный порядок групп; не создаёт public result с fake closure |
| proof / SourceProofSelectionExtractor | extract: получить proof выбранных atoms | atom index, normalizer при необходимом canonical построении | Самостоятельный subset без изменения исходного proof; не проверяет наличие bytes |
| proof / SourceProofGroupMatcher | match: сравнить предъявленные proof/selections с ожидаемыми группами | group union builder, atom index | Exact corresponding group, без перестановки/подмены request; не вычисляет durable closure |

**Validation не дублируется:** identity checker единственный владелец descriptor/key правил; canonical checker — порядка persisted proof; membership checker — decoded relation. Request-specific стадия не переписывает эти проверки и не делает собственную их версию. Общий normalizer не получает универсальный operation selector и не решает, ADMIT или READ выполняется. Порядок validation → dependent computation сохраняется.

**Diagnostics:** existing SourceFieldIssue/SourceLogicIssue/SourceFailure и shared FieldRef/CheckedPath/ValidatorAggregationHelper. Новых зеркал ошибок нет. У каждой request-specific стадии остаётся original request root, operation и индексы. Все независимые ошибки собираются; повреждённая ветвь не отменяет проверку остальных. Ни checker, ни normalizer не угадывает root из синтетического SourceProofInput.

## 3. Владельцы существующих proof-операций

Это роли предлагаемых отдельных классов; имена публичных OpenPipeline и модули не назначаются этим пунктом. Все пять сохраняют существующие request/result/error POJO. Реализация durability зависит от отдельной принятой read-интеграции, поэтому pure ядро не выдаёт такие результаты самостоятельно.

| Отдельный operation owner | Одна функция | Внутренние зависимости | Запрет |
|---|---|---|---|
| Admission | admit одного SourceProofInput | исходные request checks → normalizer → closure evaluation | Публичный вызов read/admit_groups, создание capture |
| Persisted read | read одного SourceProofReadInput | canonical/request checks → closure evaluation | Нормализация исправлением persisted proof |
| Group admission | admit_groups одного SourceProofGroupsInput | checks всех groups → group union builder → closure evaluation | Собственный union или ранний выход с потерей независимых diagnostics |
| Group verification | verify_groups одного SourceProofGroupsVerifyInput | checks → group matcher → closure evaluation и exact refs comparison | Доверие caller durable_refs без вычисления |
| Selection | select одного SourceProofSelectInput | canonical/selection checks → extractor → closure evaluation | Вызов публичных read/admit или возврат непроверенных refs |

Closure evaluation — одна общая внутренняя ответственность. Она не запускает owning producers и не определяет операцию-потребителя. Pure dependency enumeration отделяется от IO, но production dependency traversal и его точные ports конкретизируются в архитектуре интеграций. Read/admit остаются read-only.

## 4. Revision, capture и retention: границы ядра

Кандидаты отвечают за Source-смысл. Backend, borrowed transaction, artifact holders и recovery infrastructure не реализуются вторым экземпляром внутри них.

| Класс/роль-кандидат | Одна функция | Входная зависимость / эффект | Проверка / отказ |
|---|---|---|---|
| SourceRevisionChangeClassifier | classify: определить semantic изменение относительно предъявленной revision | Готовые identity/semantic evidence; pure | Не вызывает чужой projector, не назначает history seq по latest lookup |
| SourceRevisionTransitionBuilder | build: построить следующий допустимый Source revision transition | Результат классификации и предъявленная предыдущая revision; pure | Не пишет историю; не смешивает seq и artifact content hash |
| SourceRevisionAppender | append: append immutable transition через Source port | Scope-bound write, concrete binding deferred INT-WRITER | Не commit, не вычисляет semantic policy, не вызывает owning writer |
| SourceCaptureAssembler | assemble: построить capture из готовых exact mappings | Предъявленные body/collection revisions; pure | Не выбирает latest и не запускает producers |
| SourceCaptureCandidateChecker | check: проверить полноту/связность кандидата capture | Предъявленные значения и Source checks | Не утверждает committed finalization |
| SourceCaptureFinalizer | finalize: выполнить одну атомарную finalize-операцию | Candidate checker и infrastructure ports; write integration deferred | Не реализует codec/SQL/holders, не даёт partial success, не запускает recovery |
| SourceCaptureRetentionBinding (отозван) | Исторический adopt; не целевой метод Source | Acquire/handoff — внешняя граница варианта А через DAG | Реализация этого owner либо перенос acquire в переименованный Source класс — отказ |
| SourceRevisionPrunePolicy | evaluate: определить допустимость explicit prune | Предъявленные revision/root/hold facts; pure | Не удаляет artifact bytes и не снимает holders самостоятельно |
| SourceMutationOutcomeResolver | resolve: определить исход операции по authoritative receipt | Receipt-read port; recovery integration deferred | Не повторяет mutation при unknown outcome и не выдаёт unknown за отказ/успех |

Это историческое разделение ролей, не завершённый mutation/recovery контракт. Конкретные request/result/error здесь не изобретаются: они должны быть предъявлены соответствующим пунктом архитектуры до кода. Прямые реализации SQL/read ports имеют ответственность хранения/чтения, не принятия доменных решений. Общий transaction owner остаётся внешней инфраструктурой; отменённый adopt не сохраняется под предлогом атомарности.

## 5. Что сохраняется без новых реализаций

- `dataModel/sourceVersioning`: existing immutable values и локальные structural инварианты; без IO, нормализации, union/closure или owning imports.
- `encoding/sourceProofSchemaV1.py` и отдельный request manifest: существующие регистрации, один shared CanonicalCodec. Не создавать Source codec engine, второй hash или зеркальный manifest.
- SourceProofGroupProjection: existing draft internal value `proof + selections`, без durable refs. Не выдаётся вместо public result.
- FieldPathError и typed diagnostic helpers, ArtifactRef, EntityUid, RevisionHex, RegistryKey переиспользуются. Storage capability не помещается в persisted POJO.
- Descriptor/key/body/projector concrete composition, удержание истории, writer и DAG wiring — интеграционный техдолг основного плана, не задача декомпозиции ядра.

## 6. Критерии проверки этого предложения

1. Для каждой строки таблиц существует ровно одна причина изменения — её инвариант/операция. Обнаружение второй самостоятельной обязанности требует разделения, а не переименования.
2. Алгоритмы grouping, atom numbering, matching и revision classification не дублируются между operation owners.
3. Один метод не выбирает режим операции флагом/enum; SourceOperation в diagnostic context не становится dispatch-переключателем.
4. Границы pure / IO / transaction явно различены; splitting не разрушает атомарный результат.
5. Запреты DAG: новые ноды не назначены; public nested calls, выбор межоперационного маршрута и обходные orchestration callbacks запрещены. Фактическая интеграционная цепочка принимается отдельно.
6. Public DTO не меняются этой декомпозицией; нет новых POJO/errors, дублирующих existing. Полная приёмка domain CRUD/settings этим пунктом не заявляется.

**Статус:** направление декомпозиции пункта 1 согласовано пользователем. Полная архитектура ещё не принимается: точные public signatures, все constructor dependencies, транзакционные ports и критерии следующего implementation-среза относятся к оставшимся пунктам. Для архитектурных предложений в §4 нужны точные Source value contracts; внешние неизвестности остаются долгом, не заменяются placeholders. Согласование направления и собственная проверка документа не являются независимой приёмкой всей архитектуры.
