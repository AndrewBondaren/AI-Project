# Source core — публичные границы и методы

**Решения пользователя 2026-11-21:** целевой layout — пять отдельных публичных методов/пайплайнов ниже, а не единый многометодный owner. Термин frontend API к этим Python-контрактам не применяется. Старый единый класс в spec — baseline до адресной синхронизации через координатора, не второй целевой вариант. Для protected reads выбран путь Artifacts public operation → DAG → переданные данные → Source; exact named IO и полнота набора ещё согласуются. Предложение общего storage-механизма отложено в source-protected-read-infrastructure-proposal.md. Выбран вариант А публикации; Source включается только при конкретном producer/consumer mapping. АР-2…АР-6 выполняются в прежнем порядке, без новых локальных срезов.

Следствие для методов: текущие proof-only inputs и scope-based collector нельзя считать окончательными для выбранного data-input пути. Требуется owning результат Artifacts и адресная дельта Source input/collector, без mirror payload или скрытого дочитывания. Пользователь принял направление, не отсутствующие exact POJO, их реализации или всю междоменную цепочку.

**Согласование 2026-11-15:** пользователь ответил «Ок» после предъявления документа. Согласовано направление отдельных proof operation owners с существующими POJO. Полная архитектура, constructor dependencies и реализация не приняты. Разделения check_coverage/adoption preflight зафиксированы как предложение для явной синхронизации S1/S2; действующие спецификации и код этим ответом молча не переписаны. DRAFT ниже относится к незавершённой полной архитектуре и оставшимся дельтам.

Layout актуализирован 2026-11-21 и синхронизирован со spec §9.1: пять concrete owners ниже — выбранная целевая структура. Историческое предложение 15 ноября о замене единого класса больше не требует повторного выбора. DRAFT относится к оставшимся техническим bindings, не layout. Код не разрешён; POJO/semantics/errors/wire IDs этой синхронизацией не изменяются.

## 1. Пять отдельных публичных классов

Предлагаемый корень: `app.application.worldData.sourceVersioning.operations`. Каждый модуль содержит один concrete operation owner с одним публичным методом. Интерфейс, если необходим DI-контракту, повторяет только этот метод; универсальный пятиоперационный facade не добавляется. Caller — согласованная нода DAG; назначение нод и wiring отложены INT-DAG. Pack не получает доступ к внутренним алгоритмам.

```python
# operations/proofAdmissionPipelineOpenPipeline.py
class SourceProofAdmissionPipelineOpenPipeline:
    async def admit(self, request: SourceProofInput) -> SourceProofResult | SourceFailure: ...

# operations/proofReadPipelineOpenPipeline.py
class SourceProofReadPipelineOpenPipeline:
    async def read(self, request: SourceProofReadInput) -> SourceProofResult | SourceFailure: ...

# operations/proofGroupAdmissionPipelineOpenPipeline.py
class SourceProofGroupAdmissionPipelineOpenPipeline:
    async def admit_groups(self, request: SourceProofGroupsInput) -> SourceProofGroupsResult | SourceFailure: ...

# operations/proofGroupVerificationPipelineOpenPipeline.py
class SourceProofGroupVerificationPipelineOpenPipeline:
    async def verify_groups(self, request: SourceProofGroupsVerifyInput) -> SourceProofGroupsResult | SourceFailure: ...

# operations/proofSelectionPipelineOpenPipeline.py
class SourceProofSelectionPipelineOpenPipeline:
    async def select(self, request: SourceProofSelectInput) -> SourceProofResult | SourceFailure: ...
```

Public метод не принимает SourceOperation, codec/manifest, backend, transaction или выбор режима. Operation для diagnostics фиксирована самим владельцем. Все пять методов read-only: не создают revision/capture/holds, не запускают producers, не вызывают другие публичные Source операции. Локальные проверки и циклы обхода одного request не являются выбором внешних операций.

## 2. Точные существующие импорты POJO

### АР-1: зависимости владельцев и data-input boundary (актуализация 2026-11-21)

Это детализация целой архитектуры, не локальный implementation-срез. Предлагаемый обязательный набор constructor dependencies пяти concrete owners:

| Public owner | Pure dependencies (каждый отдельный параметр конструктора) | Closure dependency |
|---|---|---|
| SourceProofAdmissionPipelineOpenPipeline | validation: SourceAdmissionRequestChecker; normalizer: SourceProofNormalizer | closure: SourceProofClosureCollector по переданным данным; exact data-input/protection binding OPEN |
| SourceProofReadPipelineOpenPipeline | validation: SourceReadRequestChecker | тот же collector по переданным данным |
| SourceProofGroupAdmissionPipelineOpenPipeline | validation: SourceGroupAdmissionRequestChecker; union: SourceProofGroupUnionBuilder | тот же collector по переданным данным |
| SourceProofGroupVerificationPipelineOpenPipeline | validation: SourceGroupVerificationRequestChecker; matcher: SourceProofGroupMatcher | тот же collector по переданным данным |
| SourceProofSelectionPipelineOpenPipeline | validation: SourceSelectionRequestChecker; extractor: SourceProofSelectionExtractor | тот же collector по переданным данным |

Source не открывает и не заимствует storage scope в этом пути. Artifacts выполняет protected read; DAG передаёт owning результат Source. Collector проверяет Source relations/closure по этим данным и evidence, не дочитывает storage и не приобретает holds. Наличие данных не заменяет protection evidence. Exact owning типы и полные constructors остаются прежним незавершённым binding; private scope или новый DTO-зеркало его не заменяют.

#### Собственные constructor contracts Source — проект 2026-11-22

Следующие signatures конкретизируют таблицу выше; foreign reader, authority issuer и scope не являются constructor dependencies этих owners. Все параметры обязательны и keyword-only, сохраняются неизменными; request/paths/diagnostics не сохраняются между вызовами. Это проект composition, не обещание runtime import или завершения X-READ. Тип SourceProofClosureCollector обозначает уже предусмотренный internal owner, а не новый Protocol/placeholder; его data-input метод до согласования owning inputs остаётся незавершённым.

```python
# operations/proofAdmissionPipelineOpenPipeline.py
def __init__(self, *, validation: SourceAdmissionRequestChecker,
             normalizer: SourceProofNormalizer,
             closure: SourceProofClosureCollector) -> None: ...

# operations/proofReadPipelineOpenPipeline.py
def __init__(self, *, validation: SourceReadRequestChecker,
             closure: SourceProofClosureCollector) -> None: ...

# operations/proofGroupAdmissionPipelineOpenPipeline.py
def __init__(self, *, validation: SourceGroupAdmissionRequestChecker,
             union: SourceProofGroupUnionBuilder,
             closure: SourceProofClosureCollector) -> None: ...

# operations/proofGroupVerificationPipelineOpenPipeline.py
def __init__(self, *, validation: SourceGroupVerificationRequestChecker,
             matcher: SourceProofGroupMatcher,
             closure: SourceProofClosureCollector) -> None: ...

# operations/proofSelectionPipelineOpenPipeline.py
def __init__(self, *, validation: SourceSelectionRequestChecker,
             extractor: SourceProofSelectionExtractor,
             closure: SourceProofClosureCollector) -> None: ...
```

Назначение __init__ — только связать collaborators одной операции; constructor не проверяет request, не читает storage и не открывает lifetime. Origins принадлежат одному вызову: checker возвращает их, operation передаёт через общие index/project/localize функции; это не отдельный mutable service dependency. Canonical schema принадлежит внутренним algorithms, не public constructor. Empty/default dependencies, service locator и скрытое создание альтернативного validator запрещены.

Проверки composition: отказ validation не вызывает transform/closure; ADMIT вызывает свой normalizer, GROUPS — общий union, SELECT — extractor; READ не вызывает transform; VERIFY использует matcher и exact closure comparison. Ни один owner не вызывает публичный метод другого owner. Параллельные requests с разными worlds/origins не разделяют mutable diagnostics. Применимость collector к полностью материализованным owning inputs проверяется после X-READ; до этого constructors нельзя объявлять исполнимой полной runtime composition.

Статус АР-1: отсутствие собственных имён/параметров этих пяти constructors устранено как проект. Не закрыты contract acceptance, collector constructor/data-input method, programming-error transport и внешняя цепочка полного materialized набора. Приёмка пяти owners не выводится из заполнения constructor signatures.

#### История проверки scope-based дизайна, 2026-11-16 (superseded)

Следующие записи до раздела «АР-1: ошибки и завершение публичной операции» объясняют прежние gaps. Требования собственного Source read lifetime, borrowed scope и collector IO отозваны выбранным data-input путём; их нельзя брать как constructor contract. Разделение validation и original-request mapping сохраняется в актуальных разделах ниже.

Все параметры обязательны, без fallback/service locator/режимов. Operation фиксирована конкретным public owner, не constructor flag. Exact тип read lifetime binding пока не определён: таблица **не является полной готовой сигнатурой конструктора**. Не создавать пустой Protocol или private implementation, чтобы скрыть этот пробел. Общие pure dependencies имеют собственные constructors в source-core-internal-api.md и source-core-request-composition.md; никакого второго набора validators для public owner не вводится.

**Обнаруженные конкретные разрывы до принятия АР-1:**

1. Spec §12.1 требует `SourceProofClosureCollector.collect(scope: CommitReadScope, request: SourceProofReadInput, *, operation: SourceOperation)`. Public методы не принимают scope. Для обычных admit/read/groups/select ещё нужно определить, кто открывает read lifetime, кто выполняет bind/reset, какой scope допускается и кто гарантирует его освобождение. Borrowed writer scope adoption не является автоматическим решением public read. Это Source-owned требование к boundary; exact infrastructure contract подтверждает владелец, не Source.
2. Collector по принятому design повторно запускает SourceProofValidator для persisted proof. Request checker уже проверил исходный request. Нужно явно разделить structural/canonical validation нового normalized proof и проверки original request, чтобы не получить второй алгоритм либо повторные diagnostics. Повторная проверка security/authority после IO не отменяется оптимизацией pure checks.
3. Collector принимает SourceProofReadInput, тогда как ADMIT_GROUPS/VERIFY_GROUPS требуют diagnostics с исходными group/use positions. Синтетический read request может быть транспортом canonical proof, но не diagnostic root. Exact механизм передачи происхождения и отображения logic issues должен быть Source-owned, typed и без нового универсального context/Any. Сейчас он не задан; один operation enum его не обеспечивает. До решения нельзя обещать сохранение original paths всего pipeline.

Это не задача создать ещё один facade. Требуемый выход — одна конкретная Source read-lifetime boundary и один provenance-preserving internal contract closure, согласованные с §11.3/12.1 спецификации. Если нужна дельта collector signature, сначала предъявить её явно; существующую принятую signature молча не менять. Запрет прямых междоменных calls также применим к выбранной infrastructure composition; scoped lifetime не является исключением сам по себе.

**Проверка существующей реализации, 2026-11-16:** `db/repositories/sqlite/artifacts/access/artifactScope.py::SqliteArtifactScope.read_scope()` уже открывает read scope через SqlitePublicationCommitStore, устанавливает task-local binding и сбрасывает его в finally. При existing binding он вместо открытия возвращает read-only facet живого scope. Поэтому «нужного механизма нет» — неверно; не подтверждены его допустимость на Source public boundary и политика borrowed/ambient scope. `_require_unbound` — private, Source не получает права вызывать его. Точный вопрос владельцам записан как INT-SOURCE-READ-LIFETIME в source-technical-debt.md. Не создавать замену этим классам.

**Повторная validation:** оригинальный request проверяется до transformation. Collector по §12.1 сохраняет проверку переданного persisted proof и authority/membership после IO. Проверки не запускаются дважды над исходным request: collector получает canonical output как отдельное внутреннее значение и использует те же invariant implementations, не второй набор правил. Если output normalizer/union/extractor не проходит pure invariants, это нарушение postcondition реализации, не ошибка исходного пользовательского поля. Ни synthetic SourceProofReadInput, ни его field paths не выдаются за исходный root. Это требование к будущей collector дельте; текущая signature/поведение spec не переписаны.

**Конкретный остаток provenance:** operation enum и SourceLogicIssue.source/artifact недостаточны для однозначного обратного отображения, когда одна dependency встречается в нескольких исходных groups/uses либо IO issue относится к capture целиком. Нельзя выбирать первый совпавший ref или восстанавливать origin по сообщению ошибки. Требуется явный internal контракт, сохраняющий связь каждого canonical capture/atom со всеми original occurrences и отдельно proof-level failures. Этот контракт должен сопровождать normalization/union/selection и collector; один post-processing SourceFailure без такой связи не решает проблему. Публичные error POJO не расширяются молча. Это собственная работа Source АР-1, не долг Snapshot/Artifacts.

### АР-1: ошибки и завершение публичной операции

**Принято пользователем 2026-11-17 — разделение request и collector validation.** Request checker проверяет исходный запрос и формирует пользовательские diagnostics от actual root. Normalizer/union/extractor запускаются только после успешной проверки. Collector проверяет canonical proof теми же единственными реализациями правил; некорректный вычисленный Source proof — programming/postcondition failure, не SourceFailure по синтетическому пользовательскому полю. Для READ/VERIFY/SELECT некорректный предъявленный persisted proof диагностируется на request boundary до зависимых вычислений; это не ошибка реализации только потому, что proof persisted.

Collector обязательно проверяет finalized captures, membership и полный durable closure по переданным данным и owning evidence доступности/integrity/protection. Ранняя pure validation и occurrence mapping этих проверок не заменяют. Source не управляет read scope и не воспроизводит проверки хранения Artifacts. Повторный invariant check не создаёт второй набор правил или повторные пользовательские diagnostics. Выбор ответственности принят; exact programming-error transport, data-input/protection binding и приёмка реализации остаются прежними незавершёнными пунктами. Не вводить skip_validation/trusted_proof.

### Требования к occurrence mapping — proposal 2026-11-17

Точные private tuple aliases и функции index/project/localize предъявлены в [source-core-occurrence-mapping.md](source-core-occurrence-mapping.md). Normalizer/union/extractor сохраняют existing signatures; карта сопоставляется с их фактическим результатом без повторного вычисления proof. Scoped collector signature отозвана; data-input дельта требует сверки допустимых callers. Прежние adoption callers исключены по source-s1-s2-adoption-disposition.md, а не ожидают реализации.

До выбора нового carrier проверить существующие `SourceProofGroupProjection`, FieldRef/CheckedPath, SourceProofSelection и SourceLogicIssue: projection/selections описывают вычисленный proof/subset, но не заменяют позиции всех повторов исходного request. Не вводить зеркальный proof, публичный provenance DTO либо новый универсальный context. Связь существует только внутри одного вызова Source, не сериализуется и не передаётся Pack.

Обязательные связи: canonical capture → все original (group_index, use_index); canonical object/collection atom → все original (group_index, use_index, dependency_index, typed path). Object/collection ветви различаются existing concrete ref type, не строковым tag. Exact capture входит в ключ связи: одинаковый source ref из разных captures не сливается. Отдельно сохраняется actual request root для proof-level failures; ему не приписывается фиктивный use=0.

Normalizer/union не выбирает один origin среди повторов: сохраняется полный набор occurrences в исходном порядке. Selection оставляет mappings только выбранных atoms и их captures; canonical ordinal результата не заменяет исходный ordinal. READ использует исходные proof positions. VERIFY не смешивает expected и presented origins: IO collector проверяет presented canonical proof, а group matching диагностирует expected groups своей стадией.

Предлагаемая кратность: capture-level IO issue распространяется на все соответствующие original uses; dependency-level — на все uses, где заявлен этот exact capture+dependency. Повтор одной dependency внутри одного use не создаёт одинаковые SourceLogicIssue: existing carrier не содержит dependency_index, поэтому одинаковые итоговые logic diagnostics сводятся при отображении, сохраняя первый исходный порядок. Field diagnostics сохраняют каждый точный path и не объединяются по одному коду. Это явное уточнение семантики для приёмки, не уже утверждённая дельта §11.3.

Ошибка инфраструктуры/декодирования не превращается в field error исходного request. Structural/canonical отказ вычисленного proof — нарушение postcondition Source, а не ошибка пользователя; исходный persisted proof проверяется до преобразования. Проверки Source authority/membership/closure по owning evidence остаются обязательными и не заменяются ранее построенным mapping. Lifetime защищённого набора обеспечивает внешняя owning операция, не Source scope.

До приёмки нужны exact функции построения/проекции mapping и дельта collector, позволяющая отличить capture/atom/proof-level issue до потери контекста. Текущую `collect(scope, SourceProofReadInput, operation)` нельзя объявлять достаточной лишь на основании наличия SourceLogicIssue.source/artifact. Минимальные сценарии: один atom в двух группах; повтор atom в одном use; один source ref в разных captures; capture-wide refusal; subset с изменившимися ordinals; VERIFY expected/presented; proof-level failure без use. Все случаи проверяются без IO и без новых публичных POJO; runtime read lifetime проверяется отдельно.

### Таблица ошибок публичной операции

#### Внутренние programming failures — проект transport, 2026-11-22

Фактические pure checkers уже используют TypeError для неподходящих structural internal operands и ValueError для некорректных diagnostic positions/facts. Предлагается сохранить эту границу без нового Source error DTO:

| Ситуация | Transport | Ответственный / проверка |
|---|---|---|
| Неверный тип обязательного internal operand/dependency | TypeError | Компонент, принимающий operand; не преобразовывать в INVALID_IDENTITY/SourceFailure |
| Неверные internal positions, counts или противоречивые facts | ValueError | Компонент, принимающий facts; original user failures обрабатываются request checker до него |
| Собственный вычисленный proof нарушил проверяемую postcondition | RuntimeError | Public operation owner после внутреннего transform и до result; не выдаёт synthetic пользовательский path и не возвращает успех |
| Сбой owning IO/authority, cancellation или unknown outcome | Исходный owning exception/cancellation | Не оборачивать все exceptions в RuntimeError и не подменять доменным отсутствием |

RuntimeError здесь — программная ошибка реализации, не типизированная бизнес-диагностика. Переход manual POJO ValueError к согласованным SourceFieldIssue/SourceLogicIssue/SourceFailure этим не закрывается. Не анализировать текст исключения для выбора code. Не использовать assert как единственную production проверку postcondition. Checks выполняют общие invariant owners, не новый validator с копиями правил. В error message не включать сырые bodies/request; исходную причину сохранять там, где операция действительно переводит известное нарушение своего результата в postcondition failure.

Приёмочные сценарии: подменённый transform выдаёт invalid computed proof → RuntimeError и отсутствие result; invalid исходный persisted proof → исходные typed request diagnostics; плохой internal fact index → ValueError; infrastructure failure/cancellation проходят без изменения класса. Это concrete предложение Source transport, не уже принятый внешний error contract. До его приёмки прежний пункт programming-error transport остаётся proposal, а не неназванной задачей.

| Граница | Результат / отказ | Что запрещено |
|---|---|---|
| Некорректный root без представимого field path | Предусмотренный Pydantic structural отказ | Фиктивный path, пустой SourceFailure |
| Представимые ошибки исходного request | Existing SourceFieldIssue/SourceLogicIssue → SourceFailure с фиксированной operation | Разбор текста ValueError, сокращение исходных indices, прекращение независимых checks |
| Pure преобразование | Internal value после успешной validation | SourceProofResult с fake/пустыми refs вместо collector |
| Exact read/closure | Полный SourceProofResult либо SourceFailure по принятой mapping | Latest fallback, read failure как отсутствие без evidence, потеря original diagnostic context |
| Infrastructure/cancel/invalid scope | Existing infrastructure exception/cancellation | Превращение в MISSING_BODY или успешный domain result |

Обязательные Source-сценарии: original group error после union; selection из historical capture; empty foreign-world proof; noncanonical input без вызова transform; несколько независимых issues до dependent computation; отсутствие nested public calls и storage IO. Внешний protected read/cleanup проверяется у владельца и на согласованной цепочке, не как обязанность Source owner. Это будущие критерии проверки границ, не выполненные runtime tests.

Все пути под `app.dataModel.sourceVersioning`:

| Модуль | Используемые типы |
|---|---|
| sourceProofInput | SourceProofInput, SourceProofReadInput |
| sourceProofGroups | SourceProofGroupsInput, SourceProofGroupsResult, SourceProofGroupsVerifyInput |
| sourceProofSelection | SourceProofSelectInput, SourceProofSelection |
| sourceProofResult | SourceProofResult |
| sourceDurableProof | SourceDurableProof |
| sourceErrors | SourceFailure, SourceOperation, SourceFieldIssue, SourceLogicIssue |

Новые carriers не создаются. Frozen/strict/deep immutability уже поставлены G1.1/G1.2. Semantic boundary и агрегация ошибок ещё не реализованы: существующие TODO на ValueError не считаются закрытыми. Structural invalid-root Pydantic failure допустим по spec §11.3; доступные независимые semantic failures должны собираться с исходными paths. Infrastructure exceptions не переводятся в MISSING_BODY или domain success.

## 3. Вложенные стадии одной операции

| Owner | Линейная цепочка | Проверяемый результат |
|---|---|---|
| Admission | Проверки исходного request → normalizer → exact capture/closure evaluation → SourceProofResult | Declared repetitions обработаны, нормализованный proof соответствует usage, refs полный closure |
| Read | Проверки исходного request и canonical proof → exact capture/closure evaluation → SourceProofResult | Noncanonical proof отвергнут, исходный proof не исправлен |
| Group admission | Проверки всех исходных groups → union builder → exact capture/closure evaluation → groups result | Union точный, selections в исходном порядке, ошибки не теряют group/use indices |
| Group verification | Проверки исходного verify request → group matcher → exact capture/closure evaluation → сравнение предъявленных durable refs → groups result | Не только subset, но exact union, соответствие каждой группы и exact closure |
| Selection | Проверки исходного select request/proof/selection → extractor → exact capture/closure evaluation выбранного proof → SourceProofResult | Самостоятельный proof выбранных dependencies и его полный closure |

Closure evaluation — общий internal алгоритм из spec, а не вызов публичного read. Перенос диагностик в original request принадлежит request-specific стадии, без синтетического read input как diagnostic root. Проверки witness/captured mapping выполняются до утверждения durable result. Concrete IO ports и constructor wiring принимаются отдельно; до этого эти operation owners не могут быть реализованы с fake refs или stub collectors. Дальнейшая реализация следует только после завершения архитектуры целого ядра; нового независимого кандидата этот документ не разрешает.

## 4. Disposition прежней S1/S2 дельты

При сверке spec §13 обнаружены две обязанности, которые нельзя потерять при декомпозиции:

- `SourceProofSelector.check_coverage(input: SourceProofCoverageCheckInput) -> None | SourceFailure` — принятый internal контракт S1. Предложение разделения: отдельный `SourceProofCoverageChecker.check_coverage` с тем же input/result/semantics. Это отдельная проверка включения, не group matching и не origin authority. Перенос требует явного принятия дельты S1; прежнее размещение автоматически не меняется, forwarding facade ради сохранения смешанной ответственности не предлагается.
- `SourceCaptureRetentionBinding.collect_for_adoption/adopt` и предложенный `SourceAdoptionPreflight` — исторические компоненты отклонённого scoped маршрута. Они исключены из целевого Source roster; SRP-перенос не является заданием реализации. Semantic checks остаются в Source, acquisition/target retention — в согласуемой границе Artifacts/Publication без вызова Source из publication.

Эти обнаруженные границы уточняют декомпозицию пункта 1. Они не разрешают менять код Pack/Snapshot/DAG или начинать S1/S2 runtime.

Сохраняется только предложение pure coverage checker с прежним semantic смыслом. Последовательность старого adopt не переносится в target; coordinator сверяет уже зарегистрированную замену варианта А. Эта корректировка устраняет противоречие текущей карты с решением пользователя, не открывает новый вопрос и не меняет чужие contracts самостоятельно.

## 5. Остальные операции ядра: точная граница дальнейшей работы

| Область | Что уже известно | Что предъявить до её реализации |
|---|---|---|
| Revision classification/transition | Разделены pure решение и append; semantic evidence приходит готовым | Конкретные Source input/result/error и инварианты seq/hash/unchanged, без выдуманного owning projector |
| Mutation/recovery | Новое изменение и разрешение unknown outcome — отдельные обязанности | Отдельные публичные классы, методы и точные POJO; error/preflight/receipt/логирование, без автоматического retry mutation |
| Capture | SourceCaptureFinalizer.finalize(request: SourceCaptureWitness, *, lease: OperationLeaseRef) → SourceCaptureRef или SourceFailure — существующий internal контракт spec §12.2 | Не превращать его в публичный DAG API без отдельного решения; assembler/checker signatures и фактическая входная граница ещё нужны |
| Explicit prune | Source policy отделена от Artifacts GC | Exact request/decision/error для pure policy; holders и Source root — INT-ARTIFACTS-RETENTION |
| Descriptor configuration | Existing immutable SourceDescriptorRegistry | Точный lifecycle конфигурации/операции в архитектуре; отсутствие runtime CRUD не объявлять исключением из обязательных критериев без основания |

Это открытые Source design-задачи, не интеграционный техдолг. Неизвестные внешние реализации отложены отдельно; их отсутствие не оправдывает пропуск собственных типов и обязанностей.

## 6. Статус и приёмка

Предъявлена конкретная дельта публичного размещения пяти proof-операций с неизменными POJO и гарантиями. Проверка: одна функция каждого метода; отсутствие nested public calls; exact root diagnostics; read-only эффекты; нет новых DTO или wire IDs. Обязательные проверки DAG маршрута и CRUD всего домена не объявляются завершёнными этим документом.

До полной приёмки архитектуры остаются concrete constructor dependencies и typed internal signatures, собственные контракты revision/mutation/recovery/prune/configuration. Предложенные public names и переносы S1/S2 требуют согласования; independent review не выполнялся. Следующий шаг — предъявить internal pure signatures и Source-owned входы/результаты без IO; интеграции не разрабатывать автоматически.
