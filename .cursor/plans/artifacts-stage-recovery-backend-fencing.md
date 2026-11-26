# Stage recovery: вариант 2 — fencing в месте записи

2026-11-26. Архитектурное направление подробно зафиксировано по поручению пользователя после обсуждения варианта 2. Это описание целевых гарантий и ответственности, не разрешение реализации и не доказательство возможностей конкретного backend. Production binding, storage representation и точные новые port signatures этим документом не назначаются. Общая приёмка междоменного контракта остаётся у DAG-координатора и пользователя.

Связанные документы: [общий контракт и actual аудит](artifacts-stage-recovery-contract.md), [Artifacts owning resolution](artifacts-stage-recovery-owning-resolution.md), [Publication resolution](artifacts-stage-recovery-publication-resolution.md), [Engine transition](dag-stage-recovery-transition-resolution.md), [identity transport](dag-artifacts-identity-transport.md).

## 1. Цель и предел гарантии

После неизвестного исхода stage установить доказанную границу: все ранее принятые эффекты старой execution завершились либо доказанно отменены, а последующие изменения защищённых ресурсов от её имени невозможны. Только после этого Artifacts может оценить completion/частичные эффекты и разрешить successor.

Fencing проверяется атомарно с изменением защищённого ресурса. Проверка operation fence или generation перед IO не обеспечивает эту гарантию. Fencing не отменяет уже совершённые изменения, не доказывает сам по себе отсутствие частичных данных и не делает повтор stage автоматически безопасным.

Operation fence, stage generation, Engine execution attempt — разные идентичности. Stage generation принадлежит Artifacts; operation fence — Publication. Engine attempt не подменяет ни одну из них. StageBinding остаётся неизменяемым; новая stage generation использует тот же логический stage_id. Истечение lease, timeout, отсутствие локального task и потеря доступности процесса не являются доказательством прекращения его эффектов.

## 2. Владельцы и границы

| Участник | Владеет | Допустимые зависимости и эффекты | Критерий отказа |
|---|---|---|---|
| DAG parent, конкретный класс ещё определяется общим workflow | StageBinding в continuation, порядок declared CALL и mapping typed outcomes | Public CallTargets и POJO; begin → stage, при неизвестном исходе recover; successor только после Allowed | Storage reads, вычисление безопасности retry, прямой вызов доменного service или новая identity при retry |
| Engine | Доставка CALL/outcome, checkpoint CAS, existing execution ownership | Generic policy/event/error transport, без Artifacts semantics | Второй lifecycle loop, выбор recovery по имени домена, превращение unknown в success или безусловный stage replay |
| StageAttemptService, Artifacts proposal | Public begin/recover и owning решение по authority/evidence | Собственные storage ports и typed domain facts | Выдача Allowed только по timeout/отсутствию completion, управление operation terminal или прямой public Publication recovery call |
| StageAttemptStore и concrete adapter, Artifacts proposal | Durable binding/generation, permit consumption, claim, completion; атомарные переходы authority | Общая согласованная transaction infrastructure, scoped catalog ports | Раздельные commits для seal/hold/completion; successor без безопасной границы; самостоятельный worker scheduler |
| ArtifactStageWriter | Последовательность одного stage: admission, reserve, backend write, verify, seal | Owning authority, backend и catalog ports | Retry-loop/recovery внутри writer; generation issuance; обход permit либо второй независимый lifecycle |
| Concrete backend | Физические изменения и fencing на каждой границе effects; завершение принятых работ и безопасная disposition частичных данных | Свой storage transaction/worker механизм и exact claim authority | Check-then-write race; эффект без claim; скрытый worker после подтверждённого drain; неподтверждённая совместимость partial effects с повтором |
| StageExecutionDrain, Artifacts proposal | Read-only проверка authoritative доказательства drain | Тот же ScopedSqliteAccess/registry и scoped predicate | Остановка workers, выдача permit, самостоятельная policy/state machine или вывод drained из отсутствия локальной task |
| Publication operation stores/lifecycle | Operation admission, fence, cancel, READY, terminal и guards release | Согласованный Artifacts drain predicate в нужных transitions | Выдача stage generation, самостоятельная интерпретация backend effects или снятие hold по timeout |

Artifacts является владельцем полного stage-attempt протокола. Backend реализует его физическую гарантию; Publication использует подтверждённый результат этой гарантии. DAG не переносит в себя их проверки. Low-level node выполняет один public domain call; выбор дальнейшего CALL остаётся в родителе. Прямые междоменные service calls и скрытая оркестрация запрещены.

## 3. Транзакционный backend: необходимые условия

Этот сценарий применим только если все защищаемые изменения и проверки authority могут быть упорядочены одной транзакционной областью. Наличие SQLite у operation ledger само по себе не означает, что backend удовлетворяет этому условию.

Каждая изменяющая backend транзакция должна:

1. Проверить exact stage binding, действующую generation и consumed permit/claim, а также operation authority для данной записи.
2. Выполнить физическое изменение защищённых данных в той же транзакционной области.
3. Зафиксироваться или откатиться так, чтобы concurrent смена authority не могла вклиниться между проверкой и effect.

Recovery transition и backend writes обязаны конфликтовать/сериализоваться на соответствующей authority. Две независимые проверки в двух transactions недостаточны. Concrete backend должен предъявить используемую isolation/locking/CAS гарантию, обработку конфликтов и unknown commit, а не только последовательность методов в Python.

Если stage пишет несколькими transactions, после crash могут остаться committed partial effects. Backend обязан точно определить их принадлежность, неизменность опубликованных данных и допустимость продолжения/очистки. StageAttemptService принимает решение по owning evidence; Engine не анализирует строки. Точный алгоритм partial-effect handling принадлежит владельцу backend и пока не назначен.

Seal, operation hold и exact stage completion должны быть атомарны в общей согласованной transaction. Scoped seal не делает собственный commit. Backend data writes не объявляются автоматически частью seal transaction: это требует отдельного фактического доказательства.

## 4. Порядок штатного исполнения

1. DAG parent получает готовый prepared и строит StageBinding со стабильным stage_id. Сохранение begin input/continuation и CALL address подтверждается checkpoint до эффектов begin.
2. Public begin регистрирует binding и initial authority до возврата Allowed. Confirmed/Refused/Unresolved обрабатываются по owning таблице; этот документ не меняет порядок prepare → begin → stage.
3. Stage получает permit и тот же admitted/restored prepared по identity transport контракту. Artifacts атомарно потребляет permit и получает полный claim до effects.
4. Writer вызывает backend. Каждая backend запись защищена правилами §3 либо эквивалентной предъявленной physical гарантией. Full claim покрывает workers, verify, seal и cleanup, а не только отдельный write.
5. Seal/hold/completion фиксируются атомарно. Успех подтверждает исторический seal commit; concurrent cancel может позже изменить hold.
6. Claim release подтверждается лишь после завершения всех работ, включая cleanup. Ошибка/отмена не делают consumed permit снова доступным. Unknown release не трактуется как drained.

## 5. Recovery после потери ответа или процесса

Engine сообщает неизвестный исход через согласованную generic transition; parent делает явный public recover CALL с сохранённым binding/generation. Ни Engine, ни node не читают catalog для вывода об успехе.

Artifacts проверяет integrity и exact binding. Если сохранено достоверное completion, возможен historical Confirmed по owning precedence; это не означает, что остаточный worker/cleanup уже drained для Publication.

Для incomplete generation разрешение successor требует всех следующих доказательств:

1. Старой execution закрыт допуск к новым effects в authoritative storage.
2. Все её ранее принятые transactions/works завершены либо подтверждённо отменены. Для единой SQL области это должно следовать из предъявленного порядка serialization; для внешних workers нужен отдельный доказанный механизм.
3. После этой границы повторно проверены completion и partial effects. Если completion обнаружено, новая запись не требуется. Его отсутствие само по себе не разрешает retry.
4. Backend подтвердил безопасную disposition частичных данных; operation всё ещё допускает successor. Cancel/READY/stale operation fence не обходятся stage generation.
5. Retirement предыдущей generation и регистрация разрешённого successor выполняются атомарно и идемпотентно по existing owning proposal. Concurrent recover не выдаёт два successor; lost ACK воспроизводит согласованный outcome exact request.

Точное размещение запрета старой execution, проверки completion и выдачи successor по storage transactions должен предъявить Artifacts. Этот документ не вводит вторую служебную generation или новый журнал ради такой границы. Physical mechanism должен обеспечить невозможность записи старой execution даже если она позже возобновит выполнение.

UnknownCommitOutcome сохраняет неизвестность. Refused/Unresolved не разрешают stage. Если какая-либо обязательная гарантия недоказана, возврат безопасного отказа/Unresolved не объявляется завершённым решением automatic recovery.

## 6. Cancel, READY и освобождение holds

Publication закрывает admission в своём согласованном порядке. Выданный ранее Allowed не является вечным правом записи: consumption и backend effects обязаны уважать актуальную authority.

Перед READY/terminal/release применяются full/local drain guards из Publication resolution. Fencing будущих записей не заменяет завершение ранее принятых workers. Hold не освобождается по возрасту claim или timeout. Исторический Confirmed и готовность снять hold — разные факты.

StageExecutionDrain читает owning evidence в переданном scope без ожиданий и собственного commit. Несколько stateless adapter instances допустимы при согласованном exact implementation и общем access/registry/coordinator; singleton object identity не требуется.

## 7. Файлы, внешние запросы и граница применимости

SQL authority не обеспечивает атомарное fencing filesystem rename/link/unlink, внешнего API или отдельного worker. Current ContentAddressedBlobBackend проверяет writable перед IO и дожидается executor future при обычной cancellation; это не готовый restart-proof вариант 2.

Для каждого эффекта, включая temp creation, placement, fsync, verification с IO и cleanup, требуется предъявить связь с полной execution guarantee. No-overwrite/content addressing защищает содержимое, но не доказывает остановку всех effects. Ограничение старой execution только на seal/publication недостаточно для принятой гарантии полного drain.

Backend с эффектами вне общей transaction области должен предъявить эквивалентный механизм fencing/drain для них. Если его нет, вариант 2 для этого backend не принят. Нельзя выбрать BLOB ради удобства, выдать test.rows fixture за production SQL_ROWS или молча ослабить требование до «не публикует».

## 8. Проверки для приёмки и оставшиеся решения

### Ответственный, варианты решения и следующий результат

**Результат делегирования и координаторская сверка — 2026-11-26:** Artifacts вернул [actual backend audit](artifacts-stage-recovery-owning-resolution.md) с таблицей candidates и effects F1–F8. Сверены actual PacksWiring registrations и общая physical реализация: manifest/climate используют файловый ContentAddressedBlobBackend (manifest через subclass); grade-slots имеет factory, open-water — formats/reader, но их activation в этом маршруте не подтверждена. Production SQL_ROWS implementation для рассматриваемого route не предъявлена. Scoped PASS только фактическому аудиту и соблюдению границ поручения; это координаторская проверка, не окончательная пользовательская приёмка решения.

Для найденных manifest/climate файловых effects SQL-only вариант не закрывает всю гарантию; требуется вариант с physical backend delta. Форматы используют общий physical механизм, поэтому их различие не является само по себе новой fencing архитектурой. Выбор первого production route нужен для фиксации требуемого consumer/binding и объёма приёмки; он не заменяет отсутствующее доказательство fencing и не доказывает возможность предлагаемой дельты.

На совместную приёмку с пользователем выносятся отдельно: (1) actual audit/ownership; (2) выбор первого действительно нужного production route либо ссылка на иной actual writer; (3) после выбора — concrete physical mechanism и минимальный contract cutover. Proposed settle, WRITE/SETTLE authority, AuthorizedArtifactBackend и busy-cancel не приняты автоматически. BF-01: public proposal есть, cancel/DAG integration OPEN. BF-02: typed port есть, concrete guard/constructor OPEN. BF-03: physical exclusion/restart progress не доказаны. Код/SQL/production registration не разрешены; полного PASS цепочки нет.

Зафиксировано по поручению пользователя 2026-11-26: **Artifacts отвечает за целостное решение этого участка** — stage authority, завершение попытки и безопасное решение о повторе. Если concrete backend принадлежит другому домену, его владелец предъявляет physical guarantee; это не переносит ответственность за цельность stage-контракта в Engine или Publication.

| Вариант | Механизм | Условие применимости |
|---|---|---|
| 1. Переиспользовать существующую SQL transaction infrastructure | Проверка generation/claim и изменение данных в одной transaction; recovery через ту же serialization область запрещает old writes, проверяет completion и partial effects | ВСЕ effects необходимого backend охвачены доказанной областью; SQL ledger сам по себе этого не обеспечивает |
| 2. Дополнить concrete backend для effects вне SQL | SQL хранит authority; backend обеспечивает отдельную доказанную связь fencing/drain с файловыми или внешними работами | Предъявлен механизм для каждого внешнего effect и cleanup; общий объём больше, одной предварительной проверки fence недостаточно |

Рекомендация — вариант 1, если фактически нужный backend удовлетворяет условию. Backend ради выбора варианта не меняется. При внешних effects требуется вариант 2 либо явное признание неподдержанного automatic recovery. Это альтернативы реализации выбранного направления «fencing в месте записи», а не выбор другого production формата. Окончательный вариант пока не выбран.

Распределение результата:

- **Artifacts:** предъявляет concrete binding, обосновывает применимость варианта, проектирует settle, передачу claim и owning recovery без второго stage owner.
- **Владелец backend:** доказывает атомарность effects, disposition partial commits и завершение cleanup. Если backend принадлежит Artifacts, это часть того же поручения, не отдельный новый домен.
- **Publication:** согласует только cancel behavior и guards перед hold release; предложенный возврат busy вместо ожидания рассматривается как отдельная observable contract delta.
- **DAG-координатор:** сводит explicit CALL, stage_id, outcomes/errors и проверяет общую цепочку. Новые ноды/порядок не назначаются автоматически.
- **Engine:** предоставляет согласованные transport/checkpoint механизмы; не принимает решение о безопасности повторного stage.

**Следующий обязательный результат от Artifacts:** таблица `нужный production backend → все его effects → существующая защита каждого effect → минимальная недостающая дельта → применимый вариант`. Binding должен назвать content model, format/version, concrete backend class/module, storage resources и writer/workers. Если выбор production binding отсутствует в источниках, Artifacts возвращает координатору ровно этот missing input, не выбирает BLOB/test.rows и не начинает общую переработку storage. Таблица является основанием следующего решения; ещё одна абстрактная архитектура её не заменяет. Текущая фиксация не разрешает код или production activation.

### Границы поручений владельцам

Задача — закрыть три разрыва контракта одного stage. Не перепроектировать Engine, Publication или backend целиком. Результат каждого поручения: небольшая дельта собственного плана с точными контрактами и проверками, отдельно existing/proposed/OPEN.

1. **Artifacts / BF-01:** назвать owning метод, Input/Result/Error и допустимые состояния для подтверждённого завершения старой execution после crash при closed operation или Confirmed с незавершённым cleanup. Не выдавать successor, не открывать operation и не менять terminal. Publication сверяет только совместимость собственного close/release порядка; DAG-координатор определяет место явного CALL. Read-only drain не управляет workers.
2. **Artifacts + владелец backend / BF-02:** показать explicit передачу exact StageWriteClaim к effects и точные внутренние signatures; определить связь existing backend-local claim с полным claim, получение и release. Один владелец полного stage lifetime, никаких claim в node POJO, global registry или восстановления authority по ref.
3. **Владелец backend / BF-03:** для одного реально необходимого production binding предъявить карту effects, transaction/authority границу, поведение partial/unknown commit и crash самого recovery. Если binding не определён, вернуть точный отсутствующий вход координатору; не выбирать BLOB или test.rows самостоятельно.

**OUT:** код, новые ноды, утверждение нового порядка DAG, новые журналы, CRUD/очистка домена, production registration и общий рефакторинг. Ограниченный cleanup exact execution-owned временных ресурсов является частью исследуемого завершения effects, но не разрешением проектировать общий GC/purge. Недостаток existing механизма фиксируется отдельной предлагаемой дельтой; он не даёт разрешения расширять реализацию. Новый public метод или смена cancel waiting behavior требуют общей приёмки, даже если сигнатура cancel не меняется.

### Сопоставление предложений с actual механизмами — 2026-11-26

#### Дополнительная сверка actual call chain с ответом Artifacts

**Владельцы COMP-01…05, зафиксировано и передано по поручению пользователя 2026-11-26:** Artifacts отвечает за цельность stage-решения; чужие контракты изменяются только после owning и общей сверки.

| Пункт | Ответственный | Обязательный результат |
|---|---|---|
| COMP-01 | Artifacts | Exact authorized binding/resolve/verify contract и writer cutover без нарушения existing read/verify/GC consumers |
| COMP-02 | Artifacts | Завершение old local claim при closed/READY/stale fence без reopening, ослабления admission и второго stage owner |
| COMP-03 | Владелец concrete backend; для existing ContentAddressedBlobBackend — Artifacts | Exact execution resource identity после crash, порядок cleanup и исключение конкурентного/устаревшего cleanup; без назначения этого backend production binding маршрута |
| COMP-04 | Publication: cancel contract; DAG-координатор: explicit CALL route | Publication предъявляет waiting/busy/error semantics и caller compatibility; Artifacts предоставляет settle contract; координатор сводит маршрут. Имя файла leaseStore в Artifacts storage не переносит владение operation lifecycle из Publication |
| COMP-05 | Artifacts: seal/completion/claims; Publication: transaction/lifecycle compatibility | Artifacts предъявляет один commit и порядок full/local guards; Publication проверяет existing scope reuse и operation invariants |

Координатор 01a218a4-bfc5-7012-b18b-8ed986cc786d проверяет Output→Input, errors, порядок и отсутствие скрытой оркестрации, затем выносит пакет на совместную приёмку с пользователем. Engine не владеет COMP-01…05: его отдельная граница — согласованный CALL/checkpoint/error transport, без physical fencing и retry verdict. Поручения plan-only, изменения только собственных resolution через apply_patch; общий план меняет координатор. Код, новые ноды/порядок, production binding/activation и общий рефакторинг не разрешены. Ответ владельца не означает автоматического PASS.

По запросу пользователя проверено именно подключение proposed settle/authorized backend к существующей реализации. Следующие пункты — незакрытые контракты миграции, не разрешение на рефакторинг:

| ID | Actual evidence и несовпадение | Что должен уточнить владелец |
|---|---|---|
| COMP-01 / P1 | ArtifactFormatRegistryBinding.register требует isinstance(backend, ArtifactBackend), resolve возвращает ArtifactBackend; callback verify вызывает backend.verify(ref). Proposed sibling AuthorizedArtifactBackend имеет verify(claim,reservation), write(claim,reservation,content). ArtifactStageWriter также проверяет backend.write_admission и вызывает registry.verify(ref). Simple substitution не работает; замена verify ломает также holder-protected verify вне stage | Artifacts: exact authorized binding/resolve/verify path и сохранение существующего read/GC API. Без casts, optional claim fallback, дублирования одного format key или скрытого выбора authority |
| COMP-02 / P1 | SqliteArtifactLeases.writer перед acquire вызывает _lease(writable=True), проверяет hold и отказывает при existing active writer. Поэтому reuse этого guard для SETTLE после closed/READY/stale fence невозможен; новый acquire поверх оставшегося old claim также busy | Artifacts: отдельная точная disposition old local claim и settlement authority, сохраняющая hold/GC predicates без reopening и без ослабления ordinary writer admission. Это не доказанный дефект live WRITE path, а пробел closed settlement path |
| COMP-03 / P1 | BLOB _temp использует random mkstemp с prefix operation/fence; write хранит созданные paths только в local temps list. StagingReservation содержит artifact_id/lease/ref, без stage/generation/temp identity. Proposed cleanup(claim,reservation) не имеет показанного restart-пути к exact old temporary resources. Cleanup сейчас выполняется внутри write до возврата, тогда как proposal показывает cleanup после seal | Backend owner: восстановление exact resource ownership и disposition раннего/финального cleanup, включая crash между creation и фиксацией ownership; запрет широкого удаления по prefix. Не назначать новый журнал без обоснования |
| COMP-04 / P1 | SqliteArtifactLeases.cancel ждёт local writers в цикле; OperationLedger.cancel и ArtifactStagingService.cancel передают этот результат. Existing test_cancel_drains_claim_and_gc_retains_until_release явно ожидает pending cancel до release. Proposed busy return меняет observable behavior, сигнатура не доказывает совместимость | Publication/DAG: inventory callers и согласованный cutover waiting/error semantics; no timeout-based release, no direct Artifacts call inside cancel. Это planned delta, не existing capability |
| COMP-05 / P1 | Catalog.reserve/seal используют shared SqliteArtifactScope.transaction, seal проверяет existing local writer/hold. Нужный shared transaction механизм существует, но stage completion и authority generation там отсутствуют. Existing seal без live local writer отказывает | Artifacts: exact scoped seal/completion и порядок full/local guards, чтобы authorized write→verify→seal не потерял обязательный local claim и completion не получил отдельный commit |

Итог: proposal согласуется с разделением доменов, но ещё не является подключаемым расширением existing classes. Реальный reuse — transaction coordinator/scopes/ACK/quarantine, codec/descriptor validation и отдельные local guards. COMP-01…05 нужны как concrete изменения плана перед приёмкой implementation; главный physical fencing gap также остаётся. Статическая сверка не равна тестовому PASS; runtime код не менялся.

Проверены текущие документы владельцев и actual код; это статическая сверка, не runtime/crash PASS.

| Предлагаемый механизм | Что существует | Реальная дельта и предел reuse |
|---|---|---|
| Общая SQL serialization граница | SqliteTransactionDriver.begin использует BEGIN IMMEDIATE для write; SqlitePublicationCommitStore._transaction удерживает GuardedConnection UOW, запрещает nested/ambient transaction и выдаёт scope | Можно переиспользовать coordinator/driver, а не вводить второй. Нужны stage authority predicates и protected writes в этой же области. Наличие SQLite writer serialization не связывает автоматически file IO с authority |
| Exact runtime authority | SqliteScopeRegistry проверяет выданный scope, task, connection, lifetime, read/write и operation identity | Scope — право текущей SQL transaction, не durable StageWriteClaim и не fencing generation. Его нельзя переносить в worker; explicit execution coordinates тоже не заменяют atomic effect guard |
| Unknown commit и cancellation | Driver ожидает ACK commit/rollback через shield; commit store quarantine/close при непроверенном исходе; registry запрещает дальнейшее использование | Reuse error/transaction lifecycle. Это не подтверждение исхода stage и не доказательство отсутствия внешних effects; повторное чтение требует новой подтверждённой connection. Физическое закрытие не превращает unknown в rollback |
| Полный stage claim | SqliteArtifactLeases.writer пишет acquire/release по artifact/operation/fence; backend.write и последующий writer verify/seal используют отдельные local claims | Нет stage_id/generation/full-stage completion. Proposed StageWriteClaim и AuthorizedArtifactBackend — новая authority/passing boundary. Existing local guard может остаться подчинённым, но его release не является full drain |
| Атомарный seal/completion | SqliteArtifactCatalog.seal уже проверяет lease/live local writer/hold и пишет sealed event через SqliteArtifactScope.transaction | Existing scope joining можно reuse. Exact completion evidence отсутствует; scoped seal_in_scope + запись completion в том же commit ещё proposal. Нельзя получить это двумя последовательными standalone calls |
| Завершение старой execution | _cleanup releases local claim после нормального выхода; BLOB _io ждёт executor future при cancellation; operation recover возвращает observation | Proposed StageAttemptService.settle/StageSettleInput/Result — новый public контракт, existing аналога нет. Требуются доказательство physical settlement и сериализация concurrent settle/normal exit, в том числе cleanup effects после fencing |
| Явный claim в backend | ArtifactBackend.write(reservation,content), verify(ref), delete(ref); write_admission связывает composition | Proposed AuthorizedArtifactBackend.write/verify/cleanup(claim,...) и WRITE/SETTLE mode не реализованы. Проверить, что SETTLE cleanup тоже защищён от конкурентных/устаревших исполнителей; прекращение WRITE само по себе не доказывает этого |
| Cancel → завершение execution → final cancel | Existing cancel закрывает admission, затем ждёт _writers в цикле, далее повторяет guards и освобождает holds | Publication предлагает возврат OperationBusyError после close/observation, отдельный DAG settle и повтор cancel. Это изменение observable waiting behavior всех затронутых callers, а не готовая конфигурация. Busy не доказывает close; точный маршрут и consumer compatibility OPEN |

Источники actual: `backend/app/db/repositories/sqlite/shared/transactions/transactionDriver.py`, `shared/capabilities/scopeRegistry.py`, `snapshotCore/commitScope.py`, `artifacts/access/artifactScope.py`, `artifacts/catalogStore.py`, `artifacts/leaseStore.py`; `backend/app/application/artifacts/contracts/formatBackend.py`, `staging/artifactStageWriter.py`; `backend/app/storage/artifacts/blobBackend.py`. Источники proposals: owning resolution BF-01/02/03 и Publication BF-01.

Уточнение статуса: Artifacts уже предъявил proposed settle и typed backend port; прежнее «пакет отсутствует» ниже относится теперь к concrete mechanism/wiring и общей приёмке. Эти предложения не приняты автоматически. Production binding `(content model, format/version, backend class, resources, workers)` всё ещё не задан; поэтому concrete fencing и progress после crash не доказаны. Existing transaction инфраструктура пригодна для reuse, но не закрывает этот пробел. Порядок штатного stage и прежняя cancel semantics до отдельного решения не меняются.

### Исправления по implement-plan review

**BF-01 / P1 — завершение старой execution при closed operation.** Разрешение successor и завершение старых effects — разные обязанности. Closed admission запрещает новую запись и выдачу permit, но не может делать невозможным подтверждённое завершение уже начатых работ. Нужен явный owning путь Artifacts, который устанавливает безопасную границу и сохраняет drain evidence без reopen, successor и изменения operation terminal. Он также нужен после historical Confirmed, если completion есть, а release/cleanup не завершён. Existing begin/recover precedence из owning resolution пока такого пути не предоставляет: Refused/Confirmed сами по себе не подтверждают drain. Read-only StageExecutionDrain не получает mutation или worker control. Publication не вызывает public Artifacts recovery из cancel. Artifacts должен предъявить конкретный public метод (либо обоснованную дельту recover), Input/Result/Error, internal ports и вызывающую сторону DAG; Publication — совместимый порядок close → owning завершение → проверка drain → release/terminal. До этого автоматическое завершение cancel после crash OPEN; существующий порядок не заменяется молча.

**BF-02 / P1 — передача exact authority в backend.** Full StageWriteClaim создаётся owning attempt authority до reserve и остаётся единственным владельцем полного stage lifetime. Он не передаётся через node DTO. Для authorized backend path требуется явный внутренний типизированный binding этого claim к write/verify/cleanup и проверке в transaction. ArtifactBackend.write(reservation, content) такого binding сейчас не содержит; write_admission подтверждает composition, но не identity stage generation. Владелец обязан предъявить exact signatures и concrete constructors, включая disposition existing backend-local writer claim: reuse как подчинённого storage guard либо его замену, без второго независимого stage owner. Нельзя ограничиться неявным context/global state, восстановлением permit по ref или ещё одним acquire в backend. Legacy consumers не мигрируют автоматически; нужен перечень call sites и целевой cutover.

**BF-03 / P1 — конкретный atomic fencing mechanism.** До приёмки crash-recovery этапа Artifacts предъявляет один concrete backend и карту всех его effects, authoritative representation запрета old execution, конфликтующие write/recovery transactions и их isolation/locking, точку linearization, разбор rollback/unknown и partial commits. Нужны также crash points между закрытием старого допуска, подтверждением drain и successor issuance: повтор recovery должен продолжить сохранённое состояние, а не зависнуть навсегда и не выдать вторую generation. Для closed operation тот же механизм должен завершать drain без выдачи successor (BF-01). Пока этот пакет отсутствует, §§3–5 являются требованиями к реализации, а не готовым алгоритмом. Concrete production binding выбирается по реальной потребности маршрута, не из удобства BLOB или тестового SQL_ROWS.

**BF-04 / P2 — противоречивый drain composition.** Исправлено в Publication resolution: IStageExecutionDrain реализует отдельный SqliteStageExecutionDrain; stage store, operations, leases и holders получают required dependency. Ранний constructor stage store также содержит stage_drain. Store-as-drain и singleton wrapper restriction не действуют.

Статус после исправления документации: BF-04 закрыт на уровне проекта; BF-01/02/03 требуют owning design, передаются Artifacts с Publication-сверкой BF-01. До предъявления пакетов нет общей приёмки для реализации crash recovery. Это не блокирует отдельно принимаемый штатный stage и не означает отказ от выбранного направления fencing.

До реализации владелец backend предъявляет: concrete binding, полный список effects, exact ports и классы с ответственностью, authoritative representation, serialization guarantee, partial-effect disposition и error mapping. DAG предъявляет public stage-id producer и конкретные parent/leaf POJO/CallTargets. Engine предъявляет generic unknown/error transport без Artifacts branching. Обсуждение этих API не означает их автоматическую приёмку.

Обязательные проверки будущей реализации:

- Старый worker остановлен перед физической записью, recovery устанавливает границу, worker возобновляется: защищённые данные не изменяются.
- Старая запись уже принята до границы: recovery учитывает её commit/rollback и не выдаёт successor преждевременно.
- Crash после consumption, между partial commits, после seal до response, после completion до claim release; состояние различается по authoritative evidence.
- Concurrent recover и lost ACK не выдают лишнюю generation; исходный stage_id сохраняется.
- Cancel/READY конкурируют с claim/write/recover; нет effects после запрещающей границы и hold release до drain.
- Cleanup/external workers входят в доказательство; unknown acquisition/release/commit не превращается в отсутствие эффекта.
- Confirmed не запускает stage; Allowed — единственный owning путь новой попытки; categories/cause проходят checkpoint/error transport по согласованному контракту.

Retention текущего среза — retain/no deletion API; fencing не вводит TTL/purge. Штатная запись, workflow integration и automatic crash recovery принимаются отдельно. Actual audit пока доказывает отсутствие готовой полной гарантии, а не невозможность её реализации. Конкретный physical механизм и реализация остаются OPEN до предъявления и решения; новые ноды, порядок workflow, SQL schema и код этим документом не создаются.
