# Переход Pack на публичные staging и completion

## Новое разрешение пользователя и разграничение поставки — 2026-11-25

**Owning зависимости проверены:** Pack подтвердил отсутствие нового Pack IO/Error prerequisite generic prepare/stage при отсутствии Pack specialization registration, изменений manifest_format и consumer cutover. Publication подтвердил: новый public writable issuer нужен маршруту получения lease, не реализации stage с уже выданным lease. Existing issuance с persisted authority допустима для positive tests; closed lease обязан получить отказ stage без reopen. Closed/stale/foreign negatives обязательны. Оба ответа — PASS разграничению core/route, не приёмка runtime; standalone/composition/persisted-first/Error obligations остаются у Artifacts. Таким образом concrete Pack endpoints и public issuer не являются текущими внешними blockers разрешённого generic implementation-среза.

Пользователь прямо поручил Artifacts реализовать ядро/публичные методы. Основной координатор подтвердил PASS разграничению implementation scope: независимый owning срез prepare_stage(ArtifactPrepareStageInput[C]) → PreparedArtifact[C] и stage(ArtifactStageInput[C]) → ArtifactRef с exact declared errors разрешён этим поручением. Повторное разрешение не требуется. Полный foreign producer → nodes → consumer маршрут не blanket prerequisite реализации этого среза. Это приоритетное уточнение прежнего запрета ниже только в названных пределах.

Реализация owning core, приёмка публичного контракта и приёмка node route — отдельные статусы. Разграничение не является PASS реализации ядра или полного ARCH-STAGE, не отменяет гарантий методов и не разрешает несогласованные междоменные POJO. Domain storage/codec/error internals и их implementation-план принадлежат Artifacts, не DAG-координатору.

Остаются отдельно OPEN: concrete Pack specialization, foreign producer/consumer cutover, node wrappers/registration/activation и сквозная приёмка. Generator/gameplay и scoped Snapshot handoff OUT этого разрешения. Generic C не доказывает конкретный format binding; явно названные concrete test fixtures допустимы без выдачи их за принятую Pack specialization.

Stage authority/lifetime доказывается real lawful lease infrastructure, не fake authority. Если действительно отсутствует exact issuer Input → OperationLeaseRef/declared refusal boundary, Artifacts предъявляет конкретный незамкнутый вход stage; этот вопрос не блокирует independent prepare_stage и прочую работу без такой зависимости. Новые producer/issuer APIs не назначаются автоматически ради generic core.

## Приоритетная граница пользовательского задания — 2026-11-24

Пользователь: «Пока маршрут не закрыт, я не даю добро», затем поручил замкнуть маршрут с явным исключением генератора и gameplay. Текущая работа — контрактная сверка полного маршрута в границах плана; локальный PASS не означает разрешение зависимой реализации/активации. Прежние положения о независимых работах не заменяют это решение для незакрытого маршрута.

Генераторы, gameplay, их алгоритмы, подготовка входов верхнего процесса и production rollout — EXTERNAL / OUT. В рамках этого плана их реализация, новые APIs/ноды и интеграционные задания не выдаются. На входе рассматриваются готовые типизированные данные; синтетический caller проверяет точную входную границу, но не изображает реализованный генератор/gameplay. Отсутствие этих внешних реализаций не критерий отказа в приёмке данного маршрута.

Внутренние обязанности нельзя выносить в OUT: concrete content/format binding, owning validation, lawful lease issuer и его ошибки, exact Output→Input, сохранение identity и гарантии stage должны быть названы. Внешний caller предоставляет declared identity/context; право записи подтверждает owning инфраструктура, не произвольный fixture token. Для каждого незакрытого пункта фиксируются owner, exact deliverable и связь с шагом маршрута. Если решение выходит за утверждённый scope, оно отмечается внешней зависимостью без задания на реализацию в этом плане.

Отдельно вести scoped handoff Snapshot.apply: он не замыкается PASS standalone staging. Запрос Snapshot→Artifacts должен содержать existing method/signature либо exact недостающую дельту, scope/holders/ref sets, rollback/unknown и отсутствие собственного commit; полный Pack completion или верхний gameplay flow к этому запросу не добавляются.

## Узкая координаторская сверка ARCH-STAGE — 2026-11-24

### Единая карта контрактного закрытия: standalone route

Все IN ниже — обязанности контрактной поставки, не разрешение запускать зависимую реализацию. Candidate specialization не принимается от наличия этой таблицы.

| Шаг | Scope / владелец | Точная граница и адресный deliverable |
|---|---|---|
| Получение верхних данных | EXTERNAL OUT: генератор/gameplay/caller | Вход рассматривается готовым typed request/context. Не проектировать их алгоритмы/APIs/ноды и не выдавать им задачи |
| Подготовка manifest material | IN: Pack | Candidate PackManifestPreparationOpenPipeline.prepare_material(PackPreparationInput) → PackManifestMaterial.content:bytes. Зафиксировать accepted producer fields/error и semantic checks; готовые inputs не заменяют owning validation |
| Связь content с format | IN: Pack + Artifacts composition | Existing manifest_format, world_pack.manifest.json/BLOB/storage v1 — candidate. Pack предъявляет consumer-safe перенос semantic decode/checks из storage callback в свои producer/consumer; Artifacts фиксирует concrete C/budget/version binding без выбора по payload |
| Выдача staging lease | IN: Publication/Artifacts lifecycle, identity/context supplied caller | Existing open_operation(oid,world,kind,preparation_fingerprint) → OperationLeaseRef — кандидат, не accepted writable issuer. Предъявить authoritative immutable binding/fence, PREPARING/open issuance и точные Errors/repeat semantics. Не заменять fixture token или claim_publication |
| Prepare | IN: существующая согласованная роль DAG + Artifacts | ArtifactPrepareStageInput[bytes].content → prepare_stage → PreparedArtifact[bytes]. Сохранение того же content instance; pure/no IO. Новых node IDs/порядка не назначать |
| Stage | IN: существующая согласованная роль DAG + Artifacts | ArtifactStageInput(lease,prepared) → stage → ArtifactRef. Same in-memory content/prepared identity через реальные wrappers/registration; standalone fenced write/seal, не READY. Target storage/error п3 принят отдельно |
| Admission staged manifest | IN: Pack | PackStagedManifestInput(material,lease,artifact:ArtifactRef) → admit_staged → PackStagedManifest. Candidate public endpoints требуют owning принятия; exact descriptor/material checks, без заявления live holds/READY |
| Completion/публикация и верхний rollout | Отдельный согласуемый маршрут; вне данной standalone поставки | Не выдавать staged result за готовый candidate. Existing completion контракт не расширять задачами генератора/gameplay; ссылки на external dependencies не являются разрешением реализации |

Остатки standalone строки: принятие concrete producer/consumer и format semantic cutover; exact writable issuer/Errors; Artifacts выбранный POJO/error closure (ответственность Artifacts); фактическая in-memory registration/identity спецификация. Нормативное и runtime состояния различать; локальный PASS п3 не замыкает эту строку.

### Отдельная scoped цепочка Snapshot handoff

Scope IN — подключение authority lookup и existing handoff внутри принятой Snapshot attempt; верхняя генерация/gameplay и production inputs EXTERNAL OUT. Artifacts предъявил [read_operation_held](artifacts-scoped-held-refs-contract.md), Publication поддержал internal boundary без расширения своего API, Snapshot дал документальный consumer PASS.

Точный consumer placement: внутри yield _apply_to_target после всех handler.apply/immediate receipt checks → однократный build envelopes → append всех этих metadata → read_operation_held(context.scope,owner.lease) → intersection returned held refs с union retention_closure **тех же envelopes**, сохраняя порядок held → existing handoff → world CAS → player CAS → terminal → outer commit. Snapshot делает результат одного build доступным closure calculation и не принимает supplied transferred как full-apply authority. Existing private subset helper не объявляется полной public policy.

Artifacts: полный проверенный unique active set в той же UOW, registry scope operation accessor, immutable lease/current fence/APPLYING/closed/drained, persisted-first/corruption/orphan/seal checks, no mutations/no own commit. Lookup fault откатывает appended metadata/domain writes через outer owner; handoff/CAS не вызываются. Existing handoff сохраняет собственные checks и subset semantics; scoped lookup не заменяет их и не становится переносимым permit. Standalone guard к этому маршруту неприменим.

Адресные deliverables: Artifacts — exact internal lookup contract/Errors (предъявлен); Snapshot — same-envelope intersection/placement (подтверждён документально); Publication — unchanged owning UOW/claim authority и guards; координатор — общая узкая сверка. Зависимый код/активация ждут закрытия маршрута и решения пользователя; synthetic caller допустим для границы, но не имитирует authority.

Основной координатор подтвердил **PASS TARGET пункта 3 storage/error ответственности** после owning ответа Publication: standalone guard проверяет тот же graph; exact identity fail-fast до IO; private operations links допустимы только внутри SQLite composition, не в public port/DAG; persisted-first _lease проверяет corruption/orphan до requested binding→fence; writable и closed modes сохраняют отдельные правила. Repeated codec fault до seal и post-seal logging fault не обещают rollback/compensation/unknown. H2 single-R identity не переносится и не дублируется в writer.

Это архитектурный PASS, не runtime: actual early catalog comparisons, новый stage graph и negative evidence требуют реализации. Не переоткрывать этот согласованный пункт как общий OPEN; проверять реализацию его условий.

**Пункт 1 — concrete specialization остаётся OPEN адресно:** принятие Pack producer/consumer endpoints; semantic codec cutover; exact writable lease issuer Input/Output/Error; runtime content/prepared identity и регистрации; owning POJO/error closure выбранного binding. Candidate Pack manifest bytes / world_pack.manifest.json / BLOB / existing storage v1 не принят автоматически. Полный completion/Source не являются blanket prerequisite независимого stage. Пункт 3 не закрывает ARCH-STAGE/ARCH-0 целиком.

**Не смешивать маршруты:** standalone staging не является scoped handoff Snapshot.apply. Этот PASS не закрывает atomic handoff/retention; standalone guard не переносится на handoff внутри caller transaction. Completion и Snapshot handoff сохраняют собственные scoped контракты.

## Скоуп — 2026-11-21

Пользователь поручил оформить рекомендации после сверки Artifacts staging architecture. Это адресная контрактная работа без кода. Независимый staging-срез продолжается при сохранении действующих lifecycle-контрактов; весь completion не становится его автоматическим prerequisite. Удаление старого фасада и готовность полного Pack-маршрута требуют отдельного завершённого cutover.

Источники: [Artifacts architecture](artifacts-staging-architecture.md), [completion](publication-preparation-completion-contract.md), [Pack public operations](pack-v2-public-write-operations.md), [H2](publication-h2-persistence-proposed.md).

## Узкая зависимость Artifacts writer

Владелец Artifacts предъявляет exact constructor ArtifactStageWriter и минимальную границу lease admission/writer claim. Сначала reuse существующего подходящего интерфейса. Если его нет — предложить минимальный structural protocol только реально используемых методов, реализуемый existing adapter. Новые lease engine/store/state machine и зеркала POJO не вводятся. Exact API ещё OPEN, эта запись его не назначает.

Новый stage возвращает ArtifactRef и не переносит terminal R. Concrete lifecycle adapter сохраняет single-R и owning configuration validation; existing lifecycle consumers сохраняют record_model/result_binding identity. Узкий тип зависимости writer не отменяет этих construction checks и не означает удаления lifecycle реализации.

## Карта перехода к owning уточнению

| Текущий участок | Целевая граница | Вход / результат и оставшееся уточнение | Условие замены |
|---|---|---|---|
| finish_pack_preparation: manifest encoding и Pack checks | Owning Pack операция; результат передаётся DAG | Exact owning output с content/evidence предъявляет Pack; semantic checks остаются у Pack | Проверено сохранение состава, descriptor и provenance checks |
| Прямой manifest_stager.stage | DAG вызывает Artifacts prepare_stage, затем stage | ArtifactPrepareStageInput → PreparedArtifact; ArtifactStageInput(lease, prepared) → ArtifactRef; concrete binding и identity gates у Artifacts | Зарегистрированный путь проверен; callers старого helper учтены |
| Прямой staging.finish_preparation | Один public completion Publication | Exact public Input/Result/Error OPEN; внутренние acquisition/exact set/candidate/READY в одном UOW | Owning контракт согласован и реализован; rollback/unknown/cancel/replay проверены |
| Конструирование PreparedPackCandidate в helper | Выдача готового candidate только после confirmed completion | Кто возвращает existing candidate и как сохраняется exact binding, подтверждают Pack/Publication без mirror DTO | Нет выдачи готового candidate до commit и повторного staging при READY replay |

Таблица задаёт границы, не новые NodeId и не разрешение изменить утверждённый порядок. Полный producer/input-preparation rollout сюда не включается.

## Адресные результаты владельцев

1. Artifacts: exact writer constructor/lease boundary, источник существующего интерфейса либо минимальная proposed дельта; подтверждение сохранения H2 identity на lifecycle стороне.
2. Pack: inventory production/test callers finish_pack_preparation; disposition описания PackPreparationOperation со stage/finish внутри; exact owning producer/consumer поля и момент формирования candidate. Старый путь обозначить existing до cutover, не целевым DAG-контрактом.
3. Publication: пакет по [completion](publication-preparation-completion-contract.md), включая authoritative source protection и persisted replay после release/cancel/publication. Запрос уже направлен; signatures не выдумываются до ответа.
4. Координатор: свести Output → Input и последовательность после owning ответов; предъявить ограниченный вердикт пользователю. Общая приёмка ARCH-STAGE/ARCH-0 этой записью не выдаётся.

До consumer cutover старый ArtifactStagingService/IArtifactStaging сохраняется. Его удаление не включается скрыто в extraction writer. Незавершённый переход Pack не считается доказательством готовности всего runtime и не блокирует независимые работы без этой зависимости.
