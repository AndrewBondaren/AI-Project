# Приёмка семи Pack / Source leaf contracts

Дата: 2026-11-14. Вердикт: **полный маршрут НЕ ПРИНЯТ к реализации**. Проверены [leaf contracts](pack-source-leaf-contracts.md), [exchange](pack-source-exchange-contract.md), [execution binding](pack-source-dag-execution-binding.md), [карточка порядка](pack-source-first-route-review.md), [DAG families](gen-dag-cache-pack-source-families.md) и [обязательные критерии](../rules/dag-generator-interface.mdc). Caller detailed_initialization и последовательность 1–7 уже согласованы, повторного выбора не требуют. Это review документов и статическая сверка engine, без изменения кода/тестов.

## 1. Адресные замечания

### A1 — continuation не завершает последовательный SELECT

В execution binding PackSourceSelectionWait хранит state/calls, но не накопленные PackMetadataUsageResolution, текущую позицию и фазу. [InvocationCoordinator.event](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py) возвращает children только parent.step_index-1. Поэтому после нескольких последовательных вызовов нельзя получить прежние outputs одним CallResults.get для всех сохранённых keys. Параллельный CallGroup вместо накопления нарушил бы согласованную последовательность.

Исправление до реализации: предъявить конкретный immutable continuation с remaining/current position и completed resolutions либо иной exact механизм уже существующего engine для этих outputs. Задать инвариант completed prefix ↔ исходные requests, отсутствие повторного применения, поведeние failure/cancellation/resume. Сохранять Source results как данные DAG continuation, не создавать receipt store. Описать также фазы получения Pack requests, import, write, describe, groups и bind: сейчас три отдельные wait-модели не задают полный resume-контракт coordinating node. Доменный state не должен становиться workflow state.

### A2 — верхние contracts не замкнуты для выбранного среза

Leaf таблица конкретна, но ссылается на верхние read_pack/write_pack/read_source и их unions из общего DAG-плана. Там PackRead/Write охватывают другие операции/all-read, тогда как Source срез предлагает только SELECT/ADMIT_GROUPS. Нет точных NodeContract/ContinuationContract и CallTarget tuples выбранных верхних нод/coordinator, фабрик и bootstrap wiring, а также правила admission для неподключённых вариантов.

Исправление: предъявить точный состав registered commands/outputs/errors/calls этого implementation scope и политику неподключённой команды без успешных заглушек. Не создавать параллельную несовместимую реализацию read_source или скрытый direct leaf bypass. CALL/deps должны воспроизводить утверждённые верхние read/write уровни. Отсутствие runtime новых классов само по себе не дефект плана; дефект — отсутствие необходимых точных binding сведений.

### A3 — два состава PackMetadataProofBinding и неполный freeze ошибок

В metadata POJO указан source_admission: SourceProofResult, а exchange заменяет его парой source_request: SourceProofGroupsInput/source_result: SourceProofGroupsResult. Новая форма помечена кандидатом, leaf-контракт ссылается на оба документа. Для реализации нужна одна нормативная таблица полей с явным статусом и removal старого поля, без alias/dual-input. Также четыре metadata semantic кода пока предложения; acceptance exact error-domain/mapping не завершена.

Исправление: синхронизировать действующую проектную декларацию bind во всех owning references и принять точные errors новых request/import методов. Source уже предъявил единый SourceFailure; не открывать его заново и не вводить SourceProofFailure. Group selection semantics принадлежат Source, Pack basis ошибки — Pack.

### A4 — persistence/restore и жизненный цикл результатов не предъявлены

NodeContract допускает lifecycle=None, leaf proposal не выбирает конкретный restore/lifecycle binding. Все состояния включают вложенные Source/Pack модели, в том числе новые source exchange records и basis. Нет полного registration roster этих transport/continuation типов, exact OutputLifecycle либо обоснованного lifecycle=None и связи с допустимым checkpoint источником. Числовые IDs выдумывать нельзя.

Исправление: предъявить используемый engine transport/codec и полный nested type roster, explicit restore validation и caller lifetime входных refs. Existing engine correlation не доказывает доверие arbitrary imported checkpoint. Source READ/SELECT success не даёт live holds; внешний adoption остаётся отдельным publication scope. Этот пункт не требует реализовать всю Source migration или включать activation в семь шагов.

## 2. Все обязательные критерии

| Критерий | Доказательство / результат |
|---|---|
| Нет выбора следующей стадии в domain pipeline | Leaf §1: ровно один owning вызов; порядок в detailed_initialization. На уровне проекта соблюдено, runtime ещё не предъявлен |
| Нет скрытой orchestration | Engine CALL через верхние nodes, без callback/worker/direct execute. Намерение соответствует; exact registered route не принят из-за A2 |
| Нет прямых междоменных вызовов | Pack получает только PackPreparationService, Source leaf — SourceProofPipelineOpenPipeline; helper Pack→Source исключён. На уровне описанной границы соблюдено |
| Каждый класс: роль/deps/effects/DoD/отказ | Семь leaf, wrappers/errors и existing engine роли заданы. Для coordinator/upper factories/continuation конкретный полный roster отсутствует — A1/A2/A4 |
| Public / OpenPipeline / implementation | Owning calls и IO/sync разграничены, внутренности Source не переданы Pack. Exact публичные Pack inputs ещё не freeze — A3; верхний engine binding — A2 |
| Неизменность порядка | Caller/порядок приняты; A1 не позволяет считать sequential implementation полностью спроектированной. Не разрешено исправлять через parallel fan-out |
| CRUD данных — C отдельно | Создание нового state/proof возможно внутри owning операций, но новые world/capture CRUD leaf не входят в scope. Не считать это приёмкой Create всего Pack/Source |
| CRUD данных — R отдельно | Describe/SELECT/ADMIT_GROUPS — точные цели, types предъявлены; их wrappers не подтверждают owning runtime readiness |
| CRUD данных — U отдельно | Import/write/bind описаны; metadata evidence/ошибки требуют A3. Scope — partial settlement route |
| CRUD данных — D отдельно | Delete не входит в семь шагов, не добавляется ради CRUD симметрии; полная domain CRUD приёмка не заявляется |
| CRUD настроек — C/R/U/D отдельно | Ни одна из четырёх операций настроек не создаётся/не используется этим срезом. Existing service configuration приходит composition; принятые CachePolicy/manifest budget исключения не открываются. Нового config owner нет |
| Междоменный CRUD протокол | Source review exchange получен; owner requests/results и consumers указаны. Exact DAG transport/registration/restore и новый Pack input freeze остаются A2–A4 |
| POJO, field errors, logic errors без дублей | Wrapper kind/request/value имеет engine ответственность; owning типы переиспользуются. Две формы bind и незакрытые error/codec records мешают полной приёмке — A3/A4 |

Отсутствующие runtime tests не являются самостоятельным поводом отвергать проект до реализации. Здесь отказ основан на конкретно недостающих/противоречивых контрактах A1–A4. Тестовые сценарии leaf §5 пригодны как будущая проверка, но не заменяют эти сведения.

## 3. Порядок устранения

**Обновление 2026-11-14 после owner review:** историческое описание A1/A3 выше фиксирует исходную находку, а не текущее наличие дефекта. В execution-binding уже добавлены completed/next_index и single-description проверка; полного continuation ещё нет. Bind field divergence устранено в metadata POJO и exchange. [Конкретизация Pack errors/identity](pack-source-error-identity-contract.md) задаёт mapping для рассмотрения; четыре кода и полный freeze ещё требуют приёмки. [Ответ DAG](dag-pack-source-binding-response-2026-11-14.md) подтверждает механизм CALL, не закрывает A1/A2/A4. [Ответ publication](pack-source-adoption-publication-response-2026-11-14.md) остаётся DESIGN OPEN. Общий вердикт не изменён.

1. A3: свести один Pack bind/input/error контракт — без нового Source API.
2. A1: завершить sequential continuation и mapping каждой resume-фазы по принятому порядку.
3. A2/A4: связать верхние команды/CallTargets/factories с transport registration и restore; затем повторить только затронутые критерии приёмки.

Полученное [дополнение владельца DAG](dag-pack-source-binding-addendum-2026-11-14.md) предъявляет семь фаз exchange и upper binding candidates без сужения общих unions. Остаток A1 теперь включает внешний continuation coordinating node и producer metadata Planning; A2 — полный union/caller contract и приёмку unsupported policy/identities; A4 — production authorized entry/store composition и lifetime. Само наличие новых таблиц не закрывает замечания без проверки оставшихся входов и всех обязательных критериев.

**Граница этого остатка:** producer metadata Planning относится только к полноте будущего интеграционного маршрута. По уже принятому [решению PACK-METADATA-PLANNING](pack-v2-public-write-operations.md#отложенный-вопрос-pack-metadata-planning--разрешённая-заглушка-проекта) он не является gate разработки или приёмки текущего Pack scope. Полная route-приёмка остаётся отдельной, а текущий Pack не должен ждать разрешения этой внешней темы. Нельзя выдавать её за отсутствие Pack-owned алгоритма или заменять фиктивным PlanRef/пустым tuple.

**A3, следующая сверка:** [результат](pack-source-error-identity-contract.md#результат-статической-сверки-a3-2026-11-14) фиксирует исправленные shape/diagnostic расхождения, включая основной write-план. Остались exact owning module обновлённого binding, empty import policy и общий freeze signatures/кодов; transport относится к A4. Правило SELECT допускает как proper subset, так и выбор всего proof. Новая Source операция для этих исправлений не нужна.

**A3, последующее устранение:** owning module теперь однозначно metadataDependencies.py; empty fields/entries отклоняются как METADATA_GROUP_MISMATCH. Эти два пункта больше не OPEN проекта. Неожиданно пустой результат describe не разрешает пропуск фаз DAG. Исправленный A3 предъявлен к повторной приёмке; исторические замечания выше не означают, что сохраняются две формы binding или неопределённая empty policy. Общий вердикт полного маршрута не изменён.

**Повторная приёмка проведена:** [A3-R1/R2 и полная матрица](pack-source-a3-reacceptance-2026-11-14.md). A3 пока не принят из-за отсутствия четырёх новых кодов в owning ТЗ и противоречивого Source failure mapping в metadata-плане. Это конкретный локальный остаток; module/empty policy не открываются повторно, внешняя готовность не подменяет причины отказа.

**Актуальный результат после исправления A3-R1/R2:** ТЗ дополнено четырьмя metadata-кодами; metadata-план сохраняет SourceFailure на Source leaf и не переводит его в Pack diagnostic. Повторная проверка в указанном отчёте закрыла A3 в локальном объёме bind/diagnostics. Исторический отказ выше сохранён для trace. Общий маршрут по-прежнему НЕ ПРИНЯТ: остаток A1/A2/A4 и publication этим не устранён.

После закрытия замечаний оформляется конкретный implementation scope через implement-plan. Этот отказ относится к интеграционному маршруту, не отменяет согласованные Pack/Source решения и не блокирует независимые Pack-срезы.
