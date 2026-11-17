# Жизненный цикл сущностей: актуальность, замещение и история

Решение разработчика 2026-10-20: механизм устаревания выделяется в отдельный общий домен. Гидрология — первый рассматриваемый consumer, но контракт не ограничивается водой. Статус: целевая архитектура и проект контракта до реализации; миграция существующих доменов пока не выполнена.

## Расположение и ответственность

- `backend/app/dataModel/lifecycle/` — общие POJO жизненного цикла.
- `backend/app/application/lifecycle/` — общий consumer переходов жизненного цикла и их проверки.
- `backend/app/application/worldData/hydrology/systems/` — доменный consumer связности воды; определяет необходимость merge/split и новые параметры систем, возвращает предложение перехода DAG. DAG передаёт его публичной операции Lifecycle; прямой вызов из гидрологии запрещён.

Lifecycle владеет актуальностью сущности, связями с предшественниками и сохранением истории замещения. Доменные параметры, связность, физика, размещение и выбор основного объекта остаются в своих доменах. Устаревание здесь означает замещение сущности, а не течение времени или физический износ.

## Классы, папки и видимость — проект архитектуры

Требование пользователя 2026-11-17: архитектура домена первична. До кода принимается полная архитектура, включая данные, публичные и внутренние методы, ошибки, CRUD, чтение/историю и физическую публикацию. Затем она реализуется целиком по плану без частичных срезов. Наличие согласованного pure-контракта не разрешает начать его реализацию при открытой обязательной storage/publication архитектуре. Кандидаты классов ниже уточняются при этой общей приёмке, не становятся обязательными только потому, что перечислены в дереве.

Уточнение 2026-11-17. Ниже конкретное предложение структуры, а не описание существующих Python-классов и не приёмка новых DAG-нод. Публичность означает разрешённого caller-а, а не только отсутствие `_` в имени метода. Все новые типы принадлежат Lifecycle; используемые identity, publication и Snapshot-контракты остаются у своих владельцев. Состав полей новых запросов и результатов проходит отдельную POJO-приёмку L1 до кода.

```text
backend/app/
  dataModel/lifecycle/
    entityLifecycle.py                   EntityLifecycle
    lifecycleReplacement.py              LifecycleReplacement (предложение)
    reads/request.py                     LifecycleReadRequest, LifecycleHistoryReadRequest
    reads/capture.py                     LifecycleCapture, LifecycleHistory
    operations/create.py                 PrepareLifecycleCreate[T]
    operations/replacement.py            PrepareLifecycleReplacement[T]
    operations/end.py                    PrepareLifecycleEnd[T]
    changes/preparedCreate.py            PreparedLifecycleCreate[T]
    changes/preparedReplacement.py       PreparedLifecycleReplacement[T]
    changes/preparedEnd.py               PreparedLifecycleEnd[T]
    results/errors.py                    LifecycleFieldError, LifecycleLogicError
    publication/section.py               LifecycleSection (интеграция OPEN)
  application/lifecycle/
    reads/reader.py                      LifecycleReader
    reads/sourcePort.py                  ILifecycleReadSource
    changes/createPipelineOpenPipeline.py
      ILifecycleCreatePipelineOpenPipeline, LifecycleCreatePipelineOpenPipeline
    changes/replacementPipelineOpenPipeline.py
      ILifecycleReplacementPipelineOpenPipeline, LifecycleReplacementPipelineOpenPipeline
    changes/endPipelineOpenPipeline.py
      ILifecycleEndPipelineOpenPipeline, LifecycleEndPipelineOpenPipeline
    validation/transitionValidator.py    LifecycleTransitionValidator
    changes/changeBuilder.py             LifecycleChangeBuilder
    publication/sectionHandler.py        LifecycleSectionHandler (binding OPEN)
    publication/sectionCodec.py          LifecycleSectionCodec (native codec)
    storage/writePort.py                 ILifecycleWritePort
    composition/factory.py               фабрики wiring, без исполнения операций
```

Папки `reads`, `changes` группируют классы по ответственности. Публичные pipeline не помещаются в универсальный LifecycleService с `execute(kind, payload)`. Класс размещается в собственном модуле; Protocol конкретного pipeline допустим рядом с его реализацией, как в существующем Time. Внутренние классы не реэкспортируются как API для DAG. Конкретный SQLite adapter и pregame Pack adapter назначаются в L3 после выбора storage-контракта, а не создаются по предположению о схеме.

### Публичные методы для прямого вызова из DAG

**Принято пользователем 2026-11-17: отдельные операции с типизированными generic-контрактами.** Create, Replacement и End сохраняют отдельные публичные методы и типы запросов/результатов. Параметр `T` связывает принадлежность ссылок на сущности во входе и выходе; это не domain payload и не выбор предметного алгоритма. На каждую операцию существует одна общая реализация правил Lifecycle. Методы `replace_water_systems`/`replace_states`, ветвления по T с доменными алгоритмами и универсальный `execute(kind, payload)` не вводятся.

Используются имена семейства Lifecycle из этого ТЗ: `PrepareLifecycleCreate[T] → PreparedLifecycleCreate[T]`, `PrepareLifecycleReplacement[T] → PreparedLifecycleReplacement[T]`, `PrepareLifecycleEnd[T] → PreparedLifecycleEnd[T]`. Они соответствуют обсуждённым CreateRequest/ReplacementRequest/EndRequest; параллельные классы-синонимы не создаются. Ранее предложенный единый `PreparedLifecycleChange` заменён этими отдельными результатами, не остаётся четвёртым публичным envelope. Упоминание prepared change ниже обозначает смысл подготовленного изменения, а не дополнительный класс.

Параметризация должна сохраняться во вложенных ссылках, предложении замещения и evidence, иначе generic был бы только декоративным. Конкретный существующий или новый тип ссылки, представление T, ограничения/invariance и runtime discriminator определяются общей POJO-приёмкой без копий EntityUid/PatchRef. Нельзя подставить `Any`, стереть T на публичной границе или считать одну аннотацию Python достаточной для runtime-проверки. Полная схема ещё OPEN; решение использовать generic принято.

На границе каждой согласованной DAG-ноды используются конкретизированные Input/Output/Error, например для водной системы; незамкнутый T в регистрации запрещён. Это не назначает новые NodeId. DAG вызывает prepare целиком; validator/builder закрыты. Гидрология вычисляет предметные параметры и возвращает их через DAG, Lifecycle не принимает доменные callbacks/strategies и не запускает чужую реализацию.

Проверяемые критерии принятого решения: (1) смешанные типы предшественников/преемников отвергаются статической проверкой; (2) неверно типизированный сериализованный вход отклоняется runtime-validation; (3) результат сохраняет конкретный T после native codec round-trip; (4) незамкнутый generic не допускается регистрацией; (5) две специализации используют одну реализацию операции, без domain imports/dispatch; (6) публичный контракт не раскрывает validator/builder/storage. Это требования будущей реализации, тесты не выполнены. Конкретные runtime/codec механизмы согласуются до кода.

Полные сигнатуры ниже — предлагаемый Python-контракт; названия POJO конкретны, но их полная схема ещё OPEN. `LifecycleFieldError | LifecycleLogicError` обозначает типизированные результаты отказа, не строку и не произвольный словарь. Чтение асинхронно; подготовка чистая и синхронная. Ни один prepare-метод не читает БД и не публикует состояние.

| Конкретный класс | Публичный метод | Смысл и эффект |
|---|---|---|
| `LifecycleReader` | `async def read_current(self, request: LifecycleReadRequest) -> LifecycleCapture | LifecycleFieldError | LifecycleLogicError` | Чтение запрошенных сущностей на согласованной публикации; только read |
| `LifecycleReader` | `async def read_history(self, request: LifecycleHistoryReadRequest) -> LifecycleHistory | LifecycleFieldError | LifecycleLogicError` | Чтение истории по явному scope и границе выборки; только read |
| `LifecycleCreatePipelineOpenPipeline` | `def prepare_create[T](self, request: PrepareLifecycleCreate[T]) -> PreparedLifecycleCreate[T] \| LifecycleFieldError \| LifecycleLogicError` | Подготовка первоначального создания, без предшественников |
| `LifecycleReplacementPipelineOpenPipeline` | `def prepare_replacement[T](self, request: PrepareLifecycleReplacement[T]) -> PreparedLifecycleReplacement[T] \| LifecycleFieldError \| LifecycleLogicError` | Подготовка merge/split/замещения: закрыть предшественников и создать преемников |
| `LifecycleEndPipelineOpenPipeline` | `def prepare_end[T](self, request: PrepareLifecycleEnd[T]) -> PreparedLifecycleEnd[T] \| LifecycleFieldError \| LifecycleLogicError` | Отдельная generic-операция завершения принята; точные условия OPEN, это не физическое удаление истории |

Каждый `I…OpenPipeline` повторяет ровно соответствующую публичную сигнатуру. DAG получает экземпляр через composition, вызывает одну принятую операцию и получает результат. Домены не получают эти экземпляры через DI. `prepare_end` не используется для засухи/временной потери функции.

Данные запроса должны содержать identity операции и scope, захваченные исходные lifecycle-факты с revision/publication evidence и конкретное намерение операции. `PrepareLifecycleReplacement[T]` ссылается на типизированное предложение `LifecycleReplacement[T]`, не копирует его поля. Capture содержит записи EntityLifecycle, а не вторую модель актуальности; связывание вложенных ссылок с T должно быть явным. Отдельные PreparedLifecycleCreate/Replacement/End[T] содержат только рассчитанные lifecycle-изменения и доказательства исходной версии; не доменные параметры, не чужие patches и не общий PatchSet. Представление patch должно переиспользовать принятую native Patch-модель; точный состав OPEN до сверки L1. Создание отдельного дублирующего envelope запрещено.

`WorldPublicationRef` уже существует в `dataModel/worldSnapshot/identity/publication.py` и является кандидатом на переиспользование для captured publication; новый аналог revision/head/world binding не вводится. Достаточность capture для проверки циклов и идемпотентности, правила полноты history read и конкретные коды обоих видов ошибок должны быть установлены в L1. Неполные факты не дают права на успешную подготовку и не вызывают скрытый дочитывающий callback.

### Внутренние методы и ответственность классов

| Класс / порт | Методы и caller | Допустимые зависимости / эффекты | Проверка приёмки и признак нарушения |
|---|---|---|---|
| `LifecycleReader` | `read_current`, `read_history`; caller — DAG | Только `ILifecycleReadSource`, POJO; read собственного состояния | Возвращает данные одной подтверждённой версии; отказ, если смешивает версии или вызывает чужой pipeline |
| Три `Lifecycle…PipelineOpenPipeline` и их интерфейсы | По одному prepare-методу выше; caller — DAG | Validator, builder, POJO; без IO | Один вход → один результат, отсутствие изменений входа; отказ при выборе следующей внешней операции или persist |
| `LifecycleTransitionValidator` | `validate_create(request)`, `validate_replacement(request)`, `validate_end(request)`; caller — соответствующий pipeline | Только переданные факты, типизированные diagnostics; без IO | Проверяет scope, identity, актуальность и применимые инварианты; отказ при дочитывании чужого состояния или создании доменных данных |
| `LifecycleChangeBuilder` | `build_create(request)`, `build_replacement(request)`, `build_end(request)`; caller — pipeline после успешной проверки | Только прошедшие проверку входы и POJO; без IO | Детерминированный change, история не теряется; отказ при публикации, генерации геометрии или выборе режима исполнения |
| `ILifecycleReadSource` | `read_current(request)`, `read_history(request)` с результатами Reader; caller — Reader | Binding чтения собственного хранилища; read | Одна захваченная версия и проверяемая полнота фактов; отказ при чужих внутренних SQL-таблицах или инициировании записи |
| `LifecycleSectionHandler` | `validate`, `apply`; кандидат behavior-binding, caller и вложенная цепочка OPEN | Только принятая граница behavior; без codec | Прямой Snapshot → чужой acceptance/writer не считается разрешённым через internal/DI/callback; до проверки native binding подключение запрещено |
| `LifecycleSectionCodec` | `encode`, `decode`; caller — PatchSetCodec после принятия binding | Native schema/canonical codec; без IO и behavior | Отказ при validate/apply, legacy conversion или второй схеме полей |
| `ILifecycleWritePort` | Контракт записи подготовленной секции в bound scope — точная сигнатура OPEN L3; caller — handler | Только собственное storage в переданной границе транзакции | Ошибка откатывает общую публикацию; отказ, если порт открывает независимый commit или вычисляет новый переход |

Внутренние методы validator/builder не являются отдельными операциями DAG. Их последовательность — «проверить вход → построить результат» внутри одной атомарной операции; детализация алгоритма и порядок независимых проверок фиксируются в L1/L2. При отказе builder не запускается. Это не новый порядок междоменных стадий.

Текущий `DomainSectionHandler` в Python ещё совмещает behavior и codec. Это не целевая граница: принятое Snapshot ARCH-DEC-1/2 разделяет `DomainSectionHandler` и `SectionCodec`, связывая их одним `SectionContract` и атомарной registration. Источник: [owning-план Snapshot, ARCH-DEC-1/2](../.cursor/plans/world-domain-patches-snapshots.md). Предлагаемые методы Lifecycle разделяются следующим образом; concrete binding остаётся OPEN:

```python
# LifecycleSectionHandler: behavior only; nested invocation gate OPEN.
async def validate(self, section: LifecycleSection, context: SnapshotValidationContext) -> SectionValidation: ...
async def apply(self, section: LifecycleSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused: ...
# LifecycleSectionCodec: codec only.
def encode(self, section: LifecycleSection) -> bytes: ...
def decode(self, payload: bytes, version: FormatVersion) -> LifecycleSection: ...
```

Эти методы — кандидаты интеграции, не публичный CRUD-вход для DAG и не разрешение прямого междоменного вызова. Общие `SectionContract`, context, result и version не копируются в Lifecycle. Существующий `IWorldSnapshotApply.apply(PatchSet) -> SnapshotApplyResult` остаётся входом публикации; добавлять `Lifecycle.commit()` или вызывать handler из DAG запрещено. Наличие общей handler-инфраструктуры не разрешает Snapshot → Lifecycle acceptance/writer автоматически. Требуется отдельная проверка target nested chain и native binding; общий handler-протокол этим не отменяется. Pregame Pack binding также OPEN.

### Требования к интеграции Snapshot — proposed, не принятый binding

#### Подтверждённые контракты Snapshot и ограничения повторного использования

Сверено по current Python и ответу владельца Snapshot 2026-11-17; это статическая проверка наличия, не runtime evidence. Пути ниже относительно `backend/app/`. Accepted target отдельно указан и не выдается за уже работающий код.

| Статус / путь | Конкретный контракт в наличии | Что покрывает / чего не доказывает |
|---|---|---|
| Current `application/worldSnapshot/contracts/applyPort.py` | `IWorldSnapshotApply.async apply[S: DomainSection](self, patch_set: PatchSet[S]) -> SnapshotApplyResult` | Единый runtime publication-вход; нет нужды в Lifecycle.commit |
| Current `dataModel/patch/request/patchSet.py` | `PatchSet`: `format_version: FormatVersion`, `operation_id: EntityUid`, `preparation_fingerprint: RevisionHex`, `world_uid: EntityUid`, `timeline_id: EntityUid`, `turn_id: int` (strict, ≥1), `expected_world: WorldPublicationRef`, `expected_players: tuple[PlayerHeadExpectation, ...]`, `sections: tuple[S, ...]` | Идентичность подготовки, ожидания и секции; generic evidence поля нет и его добавление не обосновано |
| Current `dataModel/patch/changes/header.py` | `PatchRef(operation_id: EntityUid, section_key: SectionKey, ordinal: PatchOrdinal)`; `PatchHeader(ref: PatchRef, format_version: FormatVersion, depends_on: tuple[PatchRef, ...], artifacts: tuple[ArtifactRef, ...])` | Адресация patches/зависимостей/artifacts; не смысл entity_uid и не защита от подмены payload при прежнем ref |
| Current `dataModel/patch/sections/dependency.py` | `PreparedSectionDependency(section_key: SectionKey, section_fingerprint: RevisionHex)`; `PublishedSectionDependency(section_ref: SectionStateRef)` — значимые поля, discriminator сохраняется из существующей модели | Привязка к подготовленной/опубликованной секции; fingerprint не проверяет предметную согласованность UIDs |
| Current `application/patch/registry/sectionRegistry.py` | `SectionRegistry.register[S: DomainSection](self, contract: SectionContract[S], handler: DomainSectionHandler[S]) -> None` | Registry проверяет concrete model/key/version; current handler совмещает validate/apply/encode/decode |
| Accepted target ARCH-DEC-1/2 | `SectionRegistry.register[S: DomainSection](self, contract: SectionContract[S], handler: DomainSectionHandler[S], codec: SectionCodec[S]) -> None` | Атомарная association одного SectionContract, разделённые behavior/codec; требуется реализация принятой общей delta, не второй registry Lifecycle |
| Current `application/worldSnapshot/contracts/context.py` | `SnapshotApplyContext(validation: SnapshotValidationContext, world_snapshot: WorldSnapshotRef, player_snapshots: tuple[PlayerSnapshotRef, ...], scope: CommitScope, next_publication: WorldPublicationRef)` | Snapshot назначает Q/refs; домен не создаёт competing Q и не публикует под исходной P; context не публичный prepare Input |
| Current `application/worldSnapshot/storage/publicationStore.py` | `IWorldPublicationStore.async compare_append(self, scope: CommitScope, expected: WorldPublicationRef, next_publication: WorldPublicationRef) -> WorldCasResult` | Общий CAS-контракт достаточен; отдельный CAS/commit Lifecycle не нужен |
| Current `dataModel/patch/results/sectionResult.py` | `SectionRefused(category: SnapshotApplyOutcomeKind, diagnostics: tuple[FieldPathError, ...])`, минимум одна диагностика, категория COMMITTED запрещена | Concrete FieldPathError с настоящим path совместим; произвольный LogicError не принят автоматически |
| Current тот же модуль | `SectionApplyReceipt(section_key: SectionKey, states: tuple[SectionStateRetention, ...], history: tuple[SectionHistoryRetention, ...], changed: tuple[PatchRef, ...])` | Ссылки результата применения, не подтверждение commit; новый Lifecycle receipt не требуется |
| Current `dataModel/worldSnapshot/sections/retention.py` | `SectionStateRetention(state: SectionStateRef, artifacts: tuple[ArtifactRef, ...])`; `SectionHistoryRetention(history: SectionHistoryRef, artifacts: tuple[ArtifactRef, ...])` | Типы и проверки дублей существуют; полнота closure не вычисляется автоматически |

Current `WorldSnapshotService._apply_to_target(self, scope: CommitScope, validation: SnapshotValidationContext, sections: tuple[DomainSection, ...], snapshot: WorldSnapshotRef, players: tuple[PlayerSnapshotRef, ...]) -> AsyncIterator[tuple[SnapshotApplyContext, tuple[SectionApplyReceipt, ...]]]` в `application/worldSnapshot/service/worldSnapshotService.py` вызывает зарегистрированные handlers, предоставляет участок metadata/handoff и выполняет CAS. Это факт реализации общего механизма, не разрешение новой цепочки Snapshot → Lifecycle writer. Полная готовность public apply и concrete Lifecycle integration этим не утверждается.

**Архитектурные выводы из проверки владельца Snapshot:**

- `LifecycleEntityPatchBinding(entity_uid, patch_ref)` имеет отдельную семантику и не копирует PatchRef. Один patch может создавать несколько сущностей: повтор ref в bindings не должен автоматически запрещаться. Нужно согласовать кардинальность и exact coverage преемников, допустимость нескольких patches на entity и binding на fingerprint именно проверенной domain section. Соответствие только PatchRef недостаточно при замене его payload.
- Hydrology подтверждает свой публичный output и смысл domain facts. Lifecycle получает их через DAG; Snapshot не начинает вычислять гидрологическую семантику. Owning validator и admission path должны быть названы до принятия архитектуры. Минимальная generic Snapshot delta пока не доказана; сначала проектируется native lifecycle section с existing dependencies.
- Несколько change_uid в одной operation_id допустимы моделью patches/ordinal, но это ещё не принятое mapping Lifecycle. Publication retry не выявляет автоматически повтор change_uid в другой operation_id. Полнота capture и semantic uniqueness определяются Lifecycle без второго execution ledger.
- Pure prepare ошибки возвращаются DAG и не обязаны проходить SectionRefused. Для publication-boundary сначала перечисляются конкретные ошибки. Отношение без настоящего field path нельзя маскировать FieldPathError; при необходимости предлагается точный admitted union/carrier/codec delta владельцу Snapshot.
- Historical domain payload остаётся ответственностью своего владельца. Authoritative state/history closure нельзя вывести из одного receipt или metadata-ref. Новый retention POJO не требуется до доказанного недостатка существующего контракта.
- Разрешённая atomic write chain, физическое представление и pregame binding остаются архитектурными OPEN; initial gameplay-state registration не переносится автоматически на runtime. Общий протокол handler не отменяется, но его наличие не закрывает запрет прямого чужого acceptance/writer.

До закрытия этих вопросов не начинается реализация отдельного pure consumer, codec или writer. Сначала полная архитектура Lifecycle, затем реализация по плану без срезов.

По сверке 2026-11-17 current `PatchSet`, `PatchRef`, `SectionRefused` и `SectionApplyReceipt` существуют; разделение handler/codec принято как target ARCH-DEC-1/2; Lifecycle POJO, admission evidence и concrete write chain ниже предложены и остаются OPEN. Чужие контракты этим текстом не меняются.

**Предлагаемая передача через DAG.** Hydrology публично возвращает типизированные связи созданных доменных сущностей с подготовленными patch refs. DAG передаёт эти факты и lifecycle capture в публичный `prepare_replacement`. Lifecycle проверяет соответствие множеств предшественников/преемников и возвращает подготовленное изменение с конкретным binding к этим фактам. DAG передаёт результат в Snapshot вместе с доменными секциями. Snapshot проверяет identity/publication и привязку evidence к реально поданным refs/fingerprints; не рассчитывает гидрологию и не вызывает Lifecycle для повторного semantic acceptance. Кто и как записывает подготовленные lifecycle-данные в общей транзакции без запрещённого чужого writer — OPEN owning gate; автоматический callback не является решением.

Предлагаемые уточнения Input/Output/Error для L1 (модули относительно `dataModel/lifecycle/`):

| POJO / модуль | Предлагаемый состав и смысл | Ограничение |
|---|---|---|
| `LifecycleReadRequest`, `reads/request.py` | `publication: WorldPublicationRef`, `entity_uids: tuple[EntityUid, ...]` | Scope и exact version обязательны; runtime CommitReadScope не входит в запрос |
| `LifecycleCapture`, `reads/capture.py` | `publication: WorldPublicationRef`, `records: tuple[EntityLifecycle, ...]`, evidence полноты истории/операций | Evidence полноты ещё OPEN; отсутствие записи не доказывает отсутствие предка или повтора |
| `LifecycleEntityPatchBinding`, `publication/entityPatchBinding.py` | `entity_uid: EntityUid`, `patch_ref: PatchRef` | Предлагаемая связь с domain patch, не копия payload; кардинальность и reuse существующего типа проверяются в L1 |
| `LifecycleDomainEvidence`, `publication/domainEvidence.py` | `publication: WorldPublicationRef`, `operation_id: EntityUid`, `predecessor_uids: tuple[EntityUid, ...]`, `successors: tuple[LifecycleEntityPatchBinding, ...]`, зависимости `PreparedSectionDependency`/`PublishedSectionDependency` | Данные публичного owning результата через DAG; fingerprint сам по себе не доказывает согласованность UIDs; точная union/schema OPEN |
| `PrepareLifecycleReplacement[T]`, `operations/replacement.py` | `operation_id: EntityUid`, capture, `replacement: LifecycleReplacement[T]`, domain evidence с тем же T | Предложенные поля; конкретная типизация вложенных ссылок и owning Hydrology output ещё требуют приёмки |
| `PreparedLifecycleReplacement[T]`, `changes/preparedReplacement.py` | Native replacement patch, исходная publication, operation/change mapping и binding на проверенные domain refs с сохранением T | Не второй PatchSet и не execution journal; exact native patch и mapping OPEN. Create/End имеют отдельные результаты в своих модулях |

Предложение кардинальности: одна `PatchSet.operation_id` может включать несколько `change_uid`; каждый переход адресуется своим `PatchRef(operation_id, section_key, ordinal)`. Это не принятое равенство identity: mapping, retry и сравнение payload должны быть согласованы; `preparation_fingerprint` остаётся общей идентичностью подготовки. `EntityUid` в новых предложениях — существующий тип; историческое исключение `str` в EntityLifecycle не меняется молча, согласование совместимости OPEN.

Предлагаемые причины отказа: `INCOMPLETE_CAPTURE`, `PUBLICATION_MISMATCH`, `PREDECESSOR_NOT_ACTIVE`, `ANCESTRY_CYCLE`, `CHANGE_PAYLOAD_CONFLICT`, `SUCCESSOR_DOMAIN_MISMATCH`. Это кандидаты domain logic codes, а не уже зарегистрированные enums. Ошибки формы/типа/полей отделяются от ошибок логики; пути указывают конкретные replacement/evidence entries. Current `SectionRefused.diagnostics` принимает `tuple[FieldPathError, ...]`, не произвольный LifecycleLogicError. Exact variants, typed paths и admitted transport надо согласовать с Snapshot до интеграции; не оборачивать всё в строку/ValueError и не дублировать существующие ошибки.

**Запрашиваемые уточнения Snapshot, не готовые изменения его API:** (1) admission binding подготовленного lifecycle evidence к точным domain patch refs/section dependencies и expected publication; (2) допустимая atomic write chain без прямого чужого acceptance/writer, включая владельца consistency-check; (3) native section registration с разделёнными behavior/codec; (4) admitted transport конкретных lifecycle ошибок; (5) полный state/history retention closure. Если существующий контракт закрывает требование, расширение не нужно; новая универсальная система криптографических доказательств не требуется.

Публикация проверяет stale-between-prepare-and-commit целиком; новую публикацию Q назначает Snapshot через `SnapshotApplyContext.next_publication`, домен не назначает конкурирующую Q и не пишет под старой P. Receipt не означает commit. Semantic refusal возвращается только после подтверждённого rollback; `UnknownCommitOutcome` не превращается в отказ или повторную генерацию. Принятый apply order Snapshot не меняется.

History Lifecycle не дублирует snapshot metadata. Используются существующие `SectionStateRetention`, `SectionHistoryRetention`, `SectionStateRef`, `SectionHistoryRef`, `ArtifactRef` и `SectionApplyReceipt(states, history, changed)`. Полный closure исторических payload/artifacts и его владелец OPEN; одна metadata-ссылка недостаточна. Запрет удаления истории не запрещает очистку временного staging; holds/GC остаются у shared owners.

Фабрики `make_lifecycle_reader`, `make_lifecycle_create_pipeline`, `make_lifecycle_replacement_pipeline`, `make_lifecycle_end_pipeline` собирают зависимости один раз в composition. Они не исполняют запросы и не выбирают операции. Точные constructor-signatures зависят от принятого read/storage binding и фиксируются до реализации.

### CRUD и границы незавершённого дизайна

Предложенные `prepare_create`, `read_current/read_history`, `prepare_replacement` покрывают смысл создания, чтения и изменения lifecycle, но не объявляются принятым полным CRUD до проверки типов и publication effects. `prepare_end` не подменяет обязательный Delete: физическое удаление истории запрещено; отдельный конкретный Delete-контракт и типизированный отказ ещё OPEN. CRUD настроек также OPEN: состав настроек не выдумывается ради заполнения таблицы. До согласования семантики нельзя назначать SettingsService с фиктивными полями. Это явные причины неприёмки всего домена, а не неявное исключение из требований.

## Общий контракт — проект POJO

`EntityLifecycle` (frozen POJO, dataModel/lifecycle/entityLifecycle.py):

- `entity_uid: str` — opaque UID сущности;
- `is_active: bool` — актуальна ли запись;
- `predecessor_uids: tuple[str, ...]` — UID непосредственных предшественников;
- `created_by_change_uid: str` — identity операции создания;
- `ended_by_change_uid: str | None` — identity операции закрытия, None у активной записи.

`LifecycleReplacement` (frozen POJO, dataModel/lifecycle/lifecycleReplacement.py):

- `change_uid: str` — identity одной атомарной операции;
- `predecessor_uids: tuple[str, ...]` — закрываемые сущности;
- `successors: tuple[EntityLifecycle, ...]` — создаваемые сущности с новыми UID.

Это проекты типов, а не уже существующие Python-классы. `str` здесь — осознанное исключение для opaque UID сущностей/операций, не ключей реестра; значения не нормализуются, принадлежность scope и разрешение ссылок проверяются на application-границе. Контекст мира/scope, DI, техническая формула UID операции и result/report должны переиспользовать существующие механизмы после инвентаризации в отдельном плане. Локальные копии полей lifecycle в гидрологии не вводятся: доменный POJO содержит `lifecycle: EntityLifecycle`.

## Инварианты

При merge/split создаются новые сущности с новыми UID и актуальными доменными параметрами. Каждая ссылается на своих предшественников. Предшественники переводятся в неактивный исторический статус и не удаляются; их прежние параметры сохраняются. Merge даёт несколько предшественников одному преемнику; split — одного предшественника нескольким преемникам.

Создание преемников, смена статусов предшественников и сохранение доменных параметров публикуются атомарно: после gameplay через Snapshot, до gameplay через staged Pack publication/activation. Pure consumer не выполняет persist. Отдельный application writer в обход этих границ не допускается. Повтор операции с тем же change_uid не создаёт новые сущности; расхождение payload той же операции диагностируется. Ссылки предшественников не могут образовывать циклы или пересекать недопустимый scope; UID преемника не совпадает с UID предшественника. Историческая запись не участвует в разрешении текущего состава системы, но доступна для истории.

## Оркестрация и публикация (актуализация 2026-11-17)

Единственный владелец оркестрации — engine DAG. Открытые доменные pipeline вызываются непосредственно из согласованных DAG-нод. Домен не выбирает следующую самостоятельную операцию и не запускает другой домен через фасад, DI, callback, событие или worker. Локальные алгоритмы внутри одной атомарной операции остаются внутри реализации.

Предметный домен возвращает DAG свои подготовленные данные и предложение замещения. DAG передаёт предложение и необходимые актуальные lifecycle-факты публичной операции Lifecycle. Lifecycle возвращает подготовленное изменение истории либо типизированный отказ. Чужие данные получаются публичной операцией владельца через DAG, а не чтением его внутреннего хранилища. Это требования к потоку данных, не назначение новых NodeId, deps или порядка графа; bindings остаются OPEN до совместной приёмки GEN-NODE-JOINT-REVIEW.

После gameplay только DAG собирает PatchSet из согласованных доменных результатов. Только Snapshot применяет его через доменные handlers и выполняет commit; Snapshot не запускает materialization или повторное вычисление перехода. До gameplay публикуется immutable pack manifest@hash через Pack activation без snapshot от bake. Bulk-данные передаются artifact refs. Основание: [Snapshot](./tz_world_snapshot.md), § «Staged artifacts и точки публикации» и § «Путь записи и сбор патчей».

При публикации проверяются исходные revision/scope, identity операции и соответствие lifecycle-перехода доменным изменениям: у преемников должны быть соответствующие доменные данные, обе части относятся к одной операции и согласованной исходной версии. Предварительная проверка не заменяет транзакционную проверку актуальности. Конкретные POJO, проверяющий handler и способ связывания секций — OPEN в L1/L3; без них интеграция не принимается. Отказ одной части не оставляет опубликованную вторую часть.

Lifecycle не владеет scheduler, retry исполнения, lease, staging, GC или состояниями публикации. Эти обязанности остаются у Engine, Publication и Artifacts. Lifecycle отвечает за смысл и идемпотентность перехода сущностей, используя подтверждённые общие identity/revision-контракты без второго журнала исполнения.

Публичные контракты принадлежат Lifecycle; POJO входа, результата, ошибок полей и ошибок логики находятся в dataModel. Конкретные классы, методы и полные сигнатуры CRUD данных и настроек должны быть согласованы отдельно по [критериям DAG](../.cursor/rules/dag-generator-interface.mdc). Проекты EntityLifecycle/LifecycleReplacement выше не закрывают этот gate. Семантика Delete не может молча разрешить удаление истории; способ отказа/допустимого удаления и состав настроек пока OPEN. Исключения из обязательного CRUD не предполагаются.

### Доменное состояние и существование сущности (решение мастера 2026-10-21)

Временное прекращение доменной функции не завершает lifecycle существующей сущности. В частности, пересохшее озеро сохраняет UID и продолжающийся lifecycle; сухость/повторное наполнение относятся к гидрологическому состоянию. `is_active` общего lifecycle означает актуальность записи сущности, а не наличие в ней воды. Исключение объекта из текущего состава системы не является удалением объекта.

При изменении состава или merge/split водных систем историзируются замещаемые системы, а не автоматически все их участники. Возвращение прежнего состава после засухи создаёт новую систему с новым UID и ссылками на непосредственных предшественников; исторический родитель не реактивируется. Сохранившиеся участники имеют прежние UID и lifecycle. Уничтожение самого участника — отдельная явная операция. Детали водного состояния и связности принадлежат гидрологии: [пересыхание и восстановление](./tz_terrain_hydrology.md#пересыхание-и-восстановление-водоёма-решение-мастера-2026-10-21).

Прецеденты для согласования миграции: [государства](./tz_states.md) (`is_active=false`), [состояния ячеек](./tz_locations.md) (`ended_at`), [структурные мутации](./tz_structural_mutations.md) (операция, before-image, world_history). Эти механизмы не объявляются уже мигрированными или полностью эквивалентными общему lifecycle. Lifecycle не подменяет world snapshot/rollback или журнал мутаций; связь с ними определяется в плане интеграции.

Первый consumer — [динамические водные системы](./tz_terrain_hydrology.md#контракты-домена-динамических-водных-систем--проект). Порядок поставки: инвентаризация → контракт → общий consumer → первый доменный adapter и интеграция записи в Pack/Snapshot → приёмка истории, идемпотентности и атомарности. Этот порядок не задаёт runtime-граф. Состав HY-12 не расширяется молча на миграцию всех сущностей.

## План и межплановые зависимости

План реализации: [entity-lifecycle.md](../.cursor/plans/entity-lifecycle.md). Первый consumer: [hydrology-water-systems.md](../.cursor/plans/hydrology-water-systems.md). Общие контракты и consumer L0–L2 разрабатываются независимо от HY-12; L3 интегрируется с W3 после готовности pure consumer систем и producers воды. Карта: [plan-dependency-graph.md](../.cursor/plans/plan-dependency-graph.md).
