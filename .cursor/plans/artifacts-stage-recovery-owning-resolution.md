# Artifacts stage recovery — owning resolution SR-03/04/05

## Проверка живого процесса — 2026-11-28, текущая рабочая граница

Статическая сверка actual writer/backend/leaseStore/catalog/transactionDriver и stage-1 trace. Код и тесты не изменялись, runtime PASS не выдан. Этот раздел отделяет applicable штатные требования от исключённого process death. Старые stage-2 finalizer/gate зависимости ниже не являются зависимостями текущего этапа 1.

### Ответственность и actual → target

| Элемент | Actual evidence | Текущая необходимая граница / критерий |
|---|---|---|
| ArtifactStageWriter.write, application/artifacts/staging/artifactStageWriter.py | reserve → backend.write → второй admission.writer → registry.verify → catalog.seal; full claim отсутствует | Stage-1 full context до reserve и после обоих local участков. Никакого ArtifactStageFinalizer/finish_live, OS gate, новой authorized capability или stage-2 local-link prerequisite |
| ContentAddressedBlobBackend._io/write, storage/artifacts/blobBackend.py | shield executor future, repeated cancellation ждёт worker; temp cleanup внутри write; backend владеет первым local context | Не отпускать full lifetime до возврата backend и завершения local cleanup. Ошибка cleanup не означает отсутствие эффектов; file exception и cancellation не превращать в успех |
| SqliteArtifactLeases.writer/_cleanup, db/repositories/sqlite/artifacts/leaseStore.py | Acquisition before yield; cancellation acquisition обрабатывается exact claim; один shielded release task, task.result перед повторным CancelledError | Переиспользовать local механизм; не вводить второй local owner. Unknown local release не считать drained |
| SqliteTransactionDriver._acknowledge, db/repositories/sqlite/shared/transactions/transactionDriver.py | Await worker COMMIT/ROLLBACK ACK под repeated cancellation | Сохранить existing acknowledgement/quarantine ownership. CancelledError после confirmed commit не означает rollback |
| SqliteArtifactCatalog.reserve/seal | reserve атомарно приобретает operation hold; seal standalone transaction проверяет active local writer и hold | Scoped seal + stage completion одним owning UOW ещё target. Предыдущие physical effects не откатываются вместе с SQL seal |
| Proposed StageAttemptStore/full drain | В backend/app файлов stageAttemptStore/stageExecutionDrain при проверке не найдено | Full lifetime и Publication checks требуют реализации и тестов. Нельзя считать existing local tests доказательством отсутствующего full mechanism |

### Один live trace, включая ранние ошибки

Нормально: pure validation → confirmed full acquisition → reserve → backend-local acquisition/write/cleanup/release → второй local acquisition/verify → scoped seal+completion → второй local release → full release → результат/log по existing policy. Это stage-1 trace с двумя local участками, НЕ stage-2 общий local+full release.

| Граница отказа | Допустимое завершение |
|---|---|
| До full acquisition | Нет выданного full handle и backend dispatch; только исходный refusal/error |
| Full acquisition cancelled до выдачи handle | Exact claim_id lookup: confirmed rollback — no release; confirmed acquired без handoff — full release после доказанного no-dispatch. Unknown — no dispatch, no второй acquire, сохранить ошибку/неопределённость |
| Full acquired, reserve ещё не вызывался либо confirmed rollback reserve | Full release НЕ требует reservation/local link: backend не вызывался, workers отсутствуют. No-link здесь законен, не corruption |
| Reserve committed, но backend/local acquire ещё не выполнен | Полный runtime owner прекращает dispatch и завершает full claim; фиктивный local acquire запрещён. Operation hold остаётся у existing lifecycle до lawful cancel/completion; это не автоматически удаляемая утечка |
| Reserve unknown | Backend не запускается. Возможный hold не компенсируется и отсутствие reserve не утверждается. Full release допустим только через lawful usable transaction при подтверждённой full acquisition/no-dispatch; если coordinator quarantined, ошибка сохраняется, release не объявляется выполненным |
| Local acquire cancelled/unknown | При подтверждённом local cleanup и отсутствии dispatch можно завершить full. Если local outcome/release не установлен, full не объявляется drained по одному отсутствию worker |
| Write/verify cancellation или ошибка | Сначала backend join и оба реально открытых local cleanup, затем full release. В промежутке между local участками continuous full claim защищает lifecycle от ложного drain |
| Seal rollback | Нет completion этого commit; earlier file/reserve effects возможны. После live drain full release не означает отмену этих effects |
| Seal unknown | Сохранить UnknownCommitOutcome; не компенсировать, не повторять stage автоматически, не объявлять ref подтверждённым. Завершение живых workers и вопрос SQL исхода различны; release только при законном подтверждении собственной transaction |
| Release/log ошибка после confirmed seal | Completion не отменяется. Unknown release остаётся unknown, log fault не становится unknown seal |

Full release и operation hold release — разные обязанности. Отсутствие leak в happy cancellation path проверяется по confirmed release, но сбой/unknown release не скрывается обещанием обязательного успешного cleanup при неисправном storage. Для ошибки до backend вызова не нужен ни finalizer, ни process-object witness.

### Остаток собственной приёмки живого процесса

#### LIVE-01: exact private handoff — предложение 2026-11-28

Только stage-1 SqliteStageAttemptStore; не новый public API/DTO/engine. Reuse proposed immutable StageAcquisitionRow и existing scopes.commits. Exact private методы:

    _begin_cleanup(claim: StageWriteClaim) -> StageAcquisitionRow
    async _release_acquired(acquisition: StageAcquisitionRow) -> None
    async _drain_release(claim: StageWriteClaim) -> None

_begin_cleanup исполняется синхронно в owning task после завершения body и всех фактически открытых local contexts. Проверяет issuer store, current owner task, активный lifetime и сохранённую exact acquisition; переводит runtime handle в closing (дальнейший dispatch запрещён) и возвращает row, захваченную при подтверждённой acquisition. Row не принимается от DAG/публичного caller; публичного constructor cleanup capability нет. No-reservation/no-local ветка допустима, если body ещё не начал backend call. При неизвестном local release недостаточно одного closing: full release не запускается, error сохраняется.

_drain_release вызывает _begin_cleanup и создаёт РОВНО одну asyncio task для _release_acquired(row) без await между закрытием dispatch и сохранением task. Повторная cancellation только отменяет ожидание shield, но не дочернюю задачу и не создаёт вторую. Parent дожидается завершения task и проверяет task.result(). Confirmed release: full handle закрыт и инвалидирован, затем распространяется накопленная cancellation. Failure/Unknown: full handle остаётся необратимо закрытым для dispatch, durable claim остаётся pending до подтверждения его исхода; неизвестный commit release не объявляется rollback. Наружу передаётся ошибка с сохранением категории/cause, а не успешный результат или замещающая cancellation. Возвращать handle в active, повторять cleanup task либо выдавать новую execution этим путём запрещено. Ветки acquisition-before-handoff используют тот же _release_acquired только после authoritative exact lookup и структурного доказательства no-dispatch; task-affine выданного handle там ещё нет.

_release_acquired получает только frozen row, не StageWriteClaim, scope, connection или callbacks. В дочерней task вызывает existing unbound predicate и открывает собственный UOW через тот же commit store. Все scopes из этого UOW принадлежат ребёнку и завершаются им. Проверяет full persisted integrity и exact acquisition по operation/stage/generation/claim_id; matching release идемпотентен, foreign/orphan — ArtifactStorageInvariantError. Release не требует reservation/link/completion: stage-1 normal context уже последовательно завершил все local contexts либо доказал no-dispatch. Он не удаляет operation holds и не выполняет IO cleanup. Если registry quarantined, existing UnknownCommitOutcome сохраняется; чужая connection автоматически не открывается.

Проверки отказа: parent scope передан ребёнку; row подменена; другой issuer/task пытается закрыть handle; dispatch после closing; вторая cleanup task при повторной cancellation; full release при неустановленном local release; successful result при task.result failure. Тесты должны задерживать child BEGIN/release ACK и отменять parent несколько раз, проверять запрет новых workers и единственную release запись. Exact handoff предъявлен, но runtime/архитектурная приёмка ещё не выдана.

Адресный actual gap: backend.write/verify возвращают None и могут поднять infrastructure exception как из тела, так и из local acquisition/cleanup. Нельзя считать любой raise доказательством confirmed local release. Минимальная owning дельта на приёмку: два nominal exception carrier в existing application.artifacts.errors — ArtifactLiveDrainError(PublicationInfrastructureError) и ArtifactLiveDrainUnknown(UnknownCommitOutcome), без нового payload/POJO/enum. Они означают исключительно неразрешённый исход local acquisition либо неподтверждённое завершение local release/backend cleanup/worker drain. Unknown сохраняет типовую принадлежность UnknownCommitOutcome. Cause/context сохраняют исходные ошибки; ordinary body failure при подтверждённом drain не переименовывается в drain failure.

Conversion boundaries: SqliteArtifactLeases.writer оборачивает неуспех _cleanup, включая acquisition-cancellation cleanup, а также UnknownCommitOutcome acquisition transaction до yield в ArtifactLiveDrainUnknown. До разрешения exact acquisition outcome запрещены dispatch, повторный acquire и full release; отсутствие yield не доказывает rollback. Confirmed rollback без acquired claim сохраняет исходную ошибку без drain carrier. Confirmed cleanup с последующим CancelledError остаётся обычной cancellation. Backend оборачивает только failure своего worker-drain/temp-cleanup участка, не encoder/descriptor/body IO как таковой. Full context при drain carriers сохраняет pending; при ordinary body error после гарантированно завершившихся local/backend contexts может выполнить full release, затем передать body error. Для positive release ветки запрещён backend, не гарантирующий эти boundaries; это локальный binding requirement, не выбор BLOB production route.

### LIVE-01: исправления адресного ревью — 2026-11-28

**Cancellation при оставшемся full claim (P1).** Для этапа 1 применяется узкая дельта existing cancel: после confirmed close admission, вне write UOW, full predicate False немедленно даёт existing OperationBusyError вместо ожидания его изменения. Это относится к любому незавершённому full claim, включая ещё работающий owner: различать live owner и завершившийся с ошибкой owner через новый runtime registry/marker не требуется. Unknown/infrastructure fault самого predicate передаётся без превращения в Busy. Operation holds сохраняются, новый terminal не записывается. Existing ожидание local-only writers сохраняется, но перед каждой его итерацией проверяется full predicate; final UOW повторяет оба guards до releases. Busy не доказывает close и не запускает автоматический retry/finalization в DAG. Конкретная Publication граница синхронизирована в начале [SR-03](artifacts-stage-recovery-publication-resolution.md); это изменение waiting behavior предложения, не уже реализованная гарантия.

Владельцы: Artifacts — authoritative full predicate и необратимое закрытие runtime handle; Publication/SQLite lifecycle — немедленный Busy и same-UOW final recheck. Проверки: body/cleanup завершились с drain carrier, full claim остался → cancel завершается Busy без ожидания release; active full owner → тот же Busy; full False вместе с local writer → Busy, не local wait; unknown predicate → исходный unknown; local-only writer → existing blocking behavior. Во всех отказах holds и отсутствие нового terminal проверяются по storage. Для cleanup task отдельно проверить confirmed release и failure/unknown: dispatch после обоих исходов запрещён, pending не разрешает повторный запуск. Recovery этой execution, timeout release и Stage 2 не добавляются.

Все три исправления принадлежат Artifacts и ограничены живым процессом. Это уточнение существующего stage-1 пути, без нового workflow, journal, recovery service или platform prerequisite.

| Участок / владелец реализации | Обязательная ответственность | Критерий отказа |
|---|---|---|
| SqliteArtifactLeases.writer — local acquisition и cleanup | Маркировать unknown acquisition до yield отдельно от ordinary body failure; сохранить exact claim coordinates и исходный UnknownCommitOutcome. Cleanup использует существующий UOW/ACK механизм | Нет yield интерпретируется как отсутствие claim; unknown acquisition пропускается к full release как обычная ошибка тела |
| ContentAddressedBlobBackend._temp/write — собственный cleanup | На месте ошибки temp cleanup сформировать drain carrier, сохранив ошибку тела в цепочке причин. Покрыть как cleanup внутри _temp, так и finally в write | Ошибка unlink остаётся неотличимым body OSError; поздний cleanup затирает ранее полученный unknown/drain carrier |
| ContentAddressedBlobBackend._io — join accepted future | При repeated cancellation дождаться future и разобрать его результат. Drain carrier из worker передать наружу, даже если ожидание отменено; сохранить cancellation в context. Завершённый worker с обычной ошибкой тела сам по себе не означает failed drain | worker.exception() только извлечён и отброшен, затем выдан CancelledError, скрывающий неподтверждённый cleanup; release до join |
| SqliteStageAttemptStore full context — full lifetime | Не выпускать full claim при неизвестном local acquisition или любом неподтверждённом local/backend drain; не превращать ошибки SQL body в разрешение retry | Отсутствие carrier принимается за drain без проверки всех binding boundaries; carrier подавлен full cleanup |

**Приоритет ошибок на каждой owning boundary.** Если drain не подтверждён и body либо cleanup содержит UnknownCommitOutcome (включая ArtifactLiveDrainUnknown), наружный carrier — ArtifactLiveDrainUnknown. Если drain не подтверждён и SQL unknown отсутствует — ArtifactLiveDrainError. Body UnknownCommitOutcome при подтверждённом local/backend drain сохраняется исходным UnknownCommitOutcome; разрешение full release по lawful UOW не означает подтверждение body commit. Cancellation не подавляет drain fault/unknown. Confirmed seal не превращается в unknown seal из-за последующей cleanup ошибки: сохраняются место и причина неопределённости.

Обе причины сохраняются в явной цепочке: наружный carrier → cleanup failure → body failure с сохранением уже существующих causes/context; cancellation сохраняется как context, а не замена причины. Нельзя заменять уже установленную unknown category обычным infrastructure carrier при следующей обёртке. Новых DTO, enum или универсального error aggregator не вводится. Проверка цепочки причин обязательна вместе с проверкой наружного типа.

**Адресные проверки до приёмки реализации:** unknown COMMIT local acquire до yield → ноль backend dispatch и full release; confirmed rollback acquire → no acquired local claim; body UnknownCommitOutcome + cleanup OSError → ArtifactLiveDrainUnknown с обеими причинами и full pending; body OSError + successful cleanup → исходная ошибка и confirmed full release; cancellation во время _temp с ошибкой его unlink → drain carrier проходит через _io, full pending; repeated cancellation + successful worker/local cleanup → единственный release и затем CancelledError. Проверить оба local участка stage и вложенные обёртки, а также отсутствие двойного release и сохранение причины unknown на каждом выходе.

Критерии: body OSError + successful cleanup → original error и confirmed full release; body error + cleanup error → drain carrier с обеими причинами и full pending; Unknown local release → ArtifactLiveDrainUnknown, no false drain; repeated cancellation + confirmed cleanup → release, затем CancelledError. Новые carriers сохраняют declared infrastructure/unknown public categories, не добавляют expected бизнес-отказ или diagnostic POJO. Это конкретное предложение закрытия ambiguity, не existing runtime и не выполненная приёмка. Actual backend/temp exception aggregation и всех local cleanup callers проверить до кода; blanket catch всех ValueError/IO запрещён.

| ID | Точный оставшийся gap / проверка закрытия |
|---|---|
| LIVE-01 | Full context ещё proposed. Перед реализацией замкнуть task ownership shielded cleanup: immutable exact acquisition coordinates передаются единственному cleanup task после прекращения dispatch; ребёнок открывает собственный UOW, не использует родительский scope/connection. Нельзя просто вызвать task-affine handle из другого task. Exact private signature/проверка handoff и repeated-cancel тест должны быть предъявлены вместе |
| LIVE-02 | Existing full-context текст не должен требовать reservation/link для раннего no-dispatch release. Таблица выше задаёт обязательную семантику; нужны tests до reserve, после reserve и на cancelled/unknown local acquire. Новая stage-2 связь local link для этого не нужна |
| LIVE-03 | Scoped seal/completion и full drain consumers отсутствуют в проверенном runtime. Нужны same-UOW fault injection, actual cancel/READY full checks и gap между двумя local contexts. Это implementation/acceptance delta текущего этапа, не запрос на crash recovery |

Existing regression evidence (тесты прочитаны/найдены, НЕ запущены здесь): test_leases.py::test_twice_cancelled_writer_waits_for_blocked_begin_and_rollback; test_staging.py::test_cancel_drains_claim_and_gc_retains_until_release и ::test_cancel_drains_repeatedly_cancelled_placement_before_gc. Они проверяют existing local/worker путь; новые full-context gates требуют адресного расширения, а не автоматического PASS.

Порядок дальше: принять exact live ownership/private IO/Error → реализовать full context/scoped seal и согласованные lifecycle checks по stage-1 плану → проверить ранние ошибки/repeated cancellation/unknown/concurrency. Public permit/POJO и затронутые Publication границы проходят действующую общую приёмку; платформенная блокировка, restart-finalization и их публичные методы не добавляются. Вопросов пользователю для этой авторской проверки нет; full architecture/runtime готовность не объявляется.

## Текущий скоуп: живой процесс, решение пользователя 2026-11-28

Смерть процесса и восстановление execution после неё пока OUT. Все нижние process-loss proof, surviving witness, crash takeover и restart-finalization предложения — отложенное исследование, не текущая работа и не gate штатной записи. Это исключение сценария, а не доказательство его безопасности или разрешение automatic retry/release. Подробная граница зафиксирована в начале [отложенного плана](artifacts-stage-finalization-deferred.md).

Штатные concurrent calls, отмена задач (включая repeated cancellation), завершение живых workers, cleanup/claims, IO faults, rollback/UnknownCommitOutcome и atomic seal/evidence остаются в applicable текущем контракте. Их самостоятельные gaps не скрываются исключением process death. Windows-specific решение остаётся отклонённым; код/foreign документы не меняются, общая приёмка этапа 1 автоматически не выдаётся.

## Решение пользователя 2026-11-28: Windows-specific physical решение ОТКЛОНЕНО

Пользователь отклонил предложенное решение как неприемлемое. Windows/local NTFS ограничение, WindowsBlobEffectGate/LockFileEx как выбранная основа physical fencing и зависимые от этой основы construction/recovery предложения НЕ являются допустимым target для реализации или приёмки. Нижние описания сохранены как история отклонённого исследования, а не рекомендуемый механизм; прежние PROPOSED/scoped compatibility формулировки не отменяют этот статус. Windows-specific process-object варианты также не могут использоваться для обхода отказа или ограничения платформ проекта.

Проблемы остановки старых effects, restart/unknown и безопасной finalization остаются незакрытыми требованиями. Автоматическая замена на Linux primitive, новый service/IO owner или другой механизм не поручена. Новое решение должно начинаться с платформонезависимого контракта и доказательства необходимости механизма, затем проходить общую приёмку. Этап 2 остаётся отложенным. Отказ не переопределяет существующий код записи и сам по себе не отвергает независимые требования к atomic seal/authority этапа 1. Код этим решением не изменён.

## Q1 / DF-01 — process-object completion barrier, owning proposal 2026-11-27

### Итоговое решение владельца Artifacts по Q1

Итог в текущем scope: **не принимать automatic process-loss finalization общего ContentAddressedBlobBackend; DF-01 OPEN**. Это завершённый вывод текущего исследования, а не завершённая гарантия recovery. Ни получение lock, ни безопасный Unresolved не являются закрытием Q1. Детальное обоснование и таблица классов ниже; прежние RC-01 формулировки о необходимости найти primitive уточняются этим выводом.

1. **Предъявленный механизм:** root gate + exact SQL prohibition/recheck исключают новые неавторизованные batches; live join либо identity-bound process termination barrier подтверждают окончание ранее принятых effects. Для потерянного процесса конкретный barrier — WAIT_OBJECT_0 реального process HANDLE при перечисленных ниже Windows/local NTFS предпосылках. Witness нужен для writer и каждого потерянного cleanup owner. Это условно достаточный механизм, не готовая architecture/composition.
2. **Неустранённый дефект нашего решения:** existing backend/composition не обеспечивает переживающего effect owner владельца HANDLE и полной association execution → все effect owners до dispatch. Поэтому finalizer не может получить требуемое evidence после произвольного process loss. Нельзя заменить этот пробел PID, SQL-флагом, missing temp, timeout или придуманным provider в constructor.
3. **Минимальная дельта выбранного механизма:** определить surviving lifetime owner и протокол association/передачи/освобождения witness до dispatch и до подтверждённого release, включая повторный crash finalizer. Отдельно определить судьбу evidence при потере самого surviving owner. Это необходимая дельта данного механизма, не доказательство её глобальной минимальности среди всех возможных storage protocols. Новый IO service/journal/framework не вводится; owner не назначается скрыто существующему классу.
4. **Решение, вынесенное пользователю через DAG-приёмку:** допускается ли failure model с переживающим writer/cleanup владельцем evidence и изменение composition для него. Если нет, полный automatic process-loss finalizer остаётся недостижимым для предъявленного протокола в текущем scope; ограничение сохраняется явно. Выбор manifest/climate не влияет на этот вывод. Утверждение другого recovery механизма потребует собственного proof, а не ослабления drain.
5. **Граница ответственности:** Artifacts владеет physical proof, перечнем effects, backend/gate/finalizer и критериями отказа. Координатор проверяет влияние дельты на общую цепочку; пользователь принимает scope/failure model. Этот вывод не назначает внешний host, не меняет Publication/Engine API и не закрывает Q2–Q6. Полная архитектурная приёмка отклонена до определения resource owner/lifetime; исследования и документация не дают code-go.

Проверяемое условие повторной приёмки Q1: назван конкретный существующий либо отдельно разрешённый owner; предъявлены его constructor/provider и nested trace от association до dispatch, termination observation и release, включая потерю самого owner; доказано покрытие каждого writer/cleanup без скрытой оркестрации. Затем сверяются OS guarantees и fault cases ниже. До этого cleanup/release/successor без evidence запрещены, claims/holds сохраняются; бессрочное ожидание — признанное ограничение, не успешная реализация.

### Владельцы итогового решения и оставшихся действий Q1

Фиксация по поручению пользователя 2026-11-27. Владелец вопроса Q1/DF-01 — **Artifacts (backend/finalizer)**. Ответственность за доведение предложения сохраняется у Artifacts; отсутствие назначенного runtime owner не переносит архитектурную работу на пользователя или DAG.

| Предмет | Ответственный владелец | Результат / граница полномочий |
|---|---|---|
| Physical mechanism и доказательство completion/fencing | Artifacts: ContentAddressedBlobBackend, gate/guard, ArtifactStageFinalizer | Inventory всех writer/cleanup effects, OS/FS assumptions, exact evidence, crash/unknown semantics и критерии отказа. Предъявленный вывод — условный barrier; DF-01 OPEN |
| Предложение surviving witness owner и его composition | Artifacts как владелец Q1; конкретный runtime host/provider **не назначен** | Artifacts предъявляет конкретного кандидата, constructor/provider, association до dispatch, передачу и release HANDLE, покрытие повторного cleanup и потерю самого owner. Нельзя подменить этот результат названием WindowsBlobProcessWitness или назначить новый service без согласования |
| SQL authority, prohibition, exact association/release predicates | Artifacts: IStageAttemptStore / SqliteStageAttemptStore | SQL-only authority в existing graph. Не владеет OS handles и не ожидает drain; physical evidence не выводится из SQL-факта |
| Live lifetime, join и cancellation handoff | Artifacts: ArtifactStageWriter / ArtifactStageFinalizer; owning вопрос Q4/DF-04 | Согласовать lifetime с Q1 без premature unlock/release. Q1 задаёт требование, но не объявляет Q4 закрытым |
| Сверка затронутых междоменных границ и общей цепочки | Назначенный пользователем DAG-координатор: чат `Between domain operations`, thread ID `01a218a4-bfc5-7012-b18b-8ed986cc786d` | Проверить пакет Artifacts и выдать scoped PASS/OPEN/FAIL по обязательным критериям. Не проектирует backend вместо владельца, не становится runtime witness owner и не меняет порядок DAG самостоятельно |
| Принятие scope/failure model и допустимости дельты composition | Пользователь после предъявления конкретного предложения Artifacts и сверки координатора | Принять либо отклонить точную дельту, включая предел при потере surviving owner. Приёмка документа отдельно от разрешения реализации и production activation |
| Соседние lifecycle/transport последствия, если они появятся в конкретной дельте | Publication — собственные lifecycle guards; Engine — собственный transport; сверка через DAG-координатора | Новых поручений и изменений их API этим Q1 не вводится. Publication/Engine не обязаны создавать отсутствующий physical proof за Artifacts |

Порядок ответственности: **Artifacts предъявляет конкретную дельту → DAG-координатор сверяет затронутую цепочку → пользователь принимает точный scope → владельцы фиксируют принятое**. Это порядок архитектурного согласования, не новые runtime стадии. Таблица не подтверждает состоявшуюся приёмку и не назначает неназванному host обязанности. Передача пакета координатору остаётся через пользователя; сообщения другим чатам не отправлены.

Статус: предъявлено для приёмки пользователем и DAG-координатором; НЕ PASS, НЕ code-go. Этот раздел уточняет RC-01: полный automatic recovery в existing lifetime не доказан. Конкретный Windows barrier существует, но требует переживающего writer владельца process handle. Ни lock, ни Unresolved не закрывают DF-01. Manifest/climate selection не prerequisite. Код, новый IO service/journal/framework, новые платформы и production activation не предлагаются к реализации.

### Классы, методы, ответственность и критерии

Все изменения ниже — proposal, не описание actual API. Existing RC-CONSTRUCTION остаётся основой; следующая таблица задаёт узкую дельту Q1, а не заменяет приёмку Q2–Q6.

| Класс / метод | Ответственность, зависимости, effects | Проверка / основание отказа |
|---|---|---|
| ContentAddressedBlobBackend, storage.artifacts.blobBackend; write_authorized, verify_authorized, cleanup_under_guard | Существующий backend остаётся единственным исполнителем codec/path/temp/place/verify/cleanup. На authorized пути каждый batch принадлежит одному OS process object и guard. Зависимости: existing leases/attempts/contract и proposed gate | Инвентаризировать mkdir, write/flush/fsync, MoveFileExW, unlink, исключения и finally. Любой effect после отдачи guard, дочерний IO process, внешний executor или безусловный stale cleanup — отказ |
| WindowsBlobEffectGate.acquire() -> BlobEffectGuard; BlobEffectGuard.close() | Только root exclusion и lifetime admitted batch, как RC-01. Не объявляет process drain | Lock получен, но нет completion evidence — cleanup/release запрещены. Один стабильный control file; no SQL→OS wait |
| Proposed internal WindowsBlobProcessWitness.wait_terminated() -> None; close() -> None | Узкий владелец РЕАЛЬНОГО Windows process HANDLE с SYNCHRONIZE, привязанного к конкретному effect owner до dispatch. WaitForSingleObject подтверждает termination; close освобождает собственный handle после использования evidence. Это ресурс, не public DTO и не новый authority store | Не PID, не pseudo-handle, не bool из SQL. WAIT_OBJECT_0 — success; WAIT_TIMEOUT — нет evidence; WAIT_FAILED — infrastructure error. Handle не закрывается параллельно wait. Кто обеспечивает surviving lifetime, пока OPEN |
| ArtifactStageFinalizer.finalize_execution(StageFinalizeInput) -> StageFinalizeResult | Exact lookup → existing registry → gate → prohibition → completion barrier для всех прежних effect owners → exact temp cleanup с live join → short release UOW. Зависимости RC-CONSTRUCTION; witness должен предоставляться внутренней composition, не DAG | Учитывать не только writer, но и каждый прерванный finalizer, который уже мог принять cleanup IO. Только writer witness при неизвестном прежнем cleanup — отказ |
| ArtifactStageFinalizer.finish_live(StageWriteClaim) -> None; ArtifactStageWriter | Live остановка dispatch и join остаются основным доказательством нормального окончания. Writer удерживает full/local lifetime до finish_live | Cancellation/shutdown executor не равны join. Повторные отмены и передача ownership остаются DF-04; этот раздел их не закрывает |
| SqliteStageAttemptStore / IStageAttemptStore: assert_effect_allowed, prohibit_effects, release_finalized | Existing authoritative checks и proposed one-way prohibition/link/release. Никаких process handles, OS waits или backend dependencies в SQL store | Unknown commit не превращается в drain. Release только после physical proof и exact authoritative recheck; запрет второго coordinator |
| ArtifactFormatRegistryBinding.resolve_finalizer; ArtifactStageFinalizationBackend | Existing proposed single registration/capability и тот же backend instance/root/authority graph | Нельзя регистрировать отдельный recovery backend или менять format identity ради witness |
| ArtifactStageRecovery.recover; StageAttemptService.finalize_execution/recover | Сохраняют RC-CONSTRUCTION: thin public boundary и один внутренний owning job. Recovery не запускает stage | Не выбирают следующий DAG CALL, не вызывают другой домен, не экспортируют guard/witness |

WindowsBlobProcessWitness — минимальная форма ресурса для обсуждения дельты, не утверждённый новый constructor parameter: назначить provider без владельца переживающего lifetime означало бы скрыть нерешённую часть. Existing constructors не считаются уже дополненными этим ресурсом.

### Actual evidence и необходимость добавок

Actual `backend/app/storage/artifacts/blobBackend.py`: `_io` использует thread executor, shield и join при asyncio cancellation; process loss уничтожает Python future и список `temps`. `_temp` создаёт random mkstemp, пишет/flush/fsync, вызывает verify; `_place` делает MoveFileExW без overwrite и verify; `_verify` также fsync; write finally делает прямой unlink. `_sync_directory` на Windows ничего не делает. Значит, нельзя объявлять существующий путь restart-safe или считать verify чистым чтением. Existing finally переносится под authorized guard только будущей реализацией; legacy path этим предложением не переписывается.

Reuse: SQL claims/holds сохраняют exclusion GC и authority; existing `_io` сохраняет live join; registry сохраняет selection; no-overwrite и hash check сохраняют integrity. Добавки имеют разные обязанности: gate закрывает check/effect гонку cooperating процессов; prohibition запрещает будущие batches старой execution; deterministic temp из RC-01 восстанавливает адрес cleanup; process witness доказывает прекращение уже принятых IO. Ни один из этих механизмов не заменяет другой. Детерминированный temp и SQL prohibition не являются completion evidence.

### Primitive, linearization и trace

Scope: Windows, локальный стабильный NTFS root, same-volume placement, cooperating mutators. Существующий stage-2 gate — exclusive LockFileEx [0,1) на постоянном control file без FILE_SHARE_DELETE, без наследования и replacement. Byte lock не блокирует data IO других файлов автоматически.

**Completion primitive:** WaitForSingleObject на identity-bound реальном process handle с результатом WAIT_OBJECT_0. Microsoft документирует, что terminating process не завершится до completion/cancellation pending IO; TerminateProcess сам асинхронен. Здесь НЕ предлагается убивать общий application process из finalizer. Barrier ожидает уже происходящее termination. Оно может не закончиться за конечное время при проблеме driver/IO. WAIT_TIMEOUT никогда не разрешает release.

Условное доказательство: все batches конкретного владельца выполняются его threads, отсутствуют передача IO handles/работы в другие процессы, mapped writes и remote agents. После подтверждённого termination нет threads этого владельца, способных запустить новый syscall, и его pending IO завершены либо отменены. Это доказательство quiescence, не успешности каждого IO, не hash correctness и не durability при power loss.

WRITE acquire/check/effect/drain/release: full/local association по owning trace → до первого dispatch установить identity-bound witness ownership → acquire root gate → short SQL exact check → close UOW → admitted batch → join всех workers и завершить cleanup/закрытие data handles → release gate. Проверка не кешируется между acquisitions. В живом batch gate нельзя отдать раньше join. Переход full/local release остаётся у finish_live; отдача gate не освобождает claims.

FINALIZE: exact inspect/resolve → acquire gate → confirmed COMMIT prohibition → wait/check termination evidence прежних потерянных effect owners → собственный exact cleanup batch → live join → short authoritative local/full release COMMIT → release gate. OS wait никогда не внутри SQL UOW. COMMIT prohibition — linearization запрета будущих WRITE/VERIFY/seal. WAIT_OBJECT_0 — observation completion для конкретного process object. COMMIT release — lifecycle transition; единой атомарной SQL+FS точки не вводится.

Old worker, ждущий gate, после prohibition не может исполнять ни write, ни свой finally cleanup. Old finalizer после нового acquisition обязан перечитать exact authority: после release — no-op; до release он может cleanup только как текущий lawful finalizer после полного evidence. Обработка stale finalizer не полагается на cached claim. Cleanup finalizer сам является effect owner: если он погиб после dispatch unlink, следующий finalizer обязан доказать completion ЭТОГО процесса до cleanup/release. Нельзя считать original writer witness транзитивным доказательством всех последующих cleanup.

Если прежний процесс жив, lock acquisition сам по себе остаётся лишь exclusion. Live join evidence допустимо только от корректно владеющего batch пути; без него barrier не выдумывается. Нельзя ждать termination своего живого процесса как способ завершить собственный live batch. Q3 определяет допустимость finalization, Q4 — handoff; здесь их policy не добавляется.

### Доказанное ограничение existing scope и минимальная дельта

1. Existing backend хранит worker completion только в памяти процесса. Он не регистрирует identity каждого physical effect owner и не передаёт process HANDLE переживающему владельцу до dispatch.
2. LockFileEx обещает освобождение lock при закрытии handle/termination, но не completion barrier произвольных IO на других файлах. Его документация не даёт требуемого порядка «все effects завершились → recovery получил lock».
3. После потери единственного владельца future/handle restart видит SQL и FS. Одинаковые prohibition/claim/temp наблюдения совместимы как с завершённым batch, так и с отсутствующим evidence о ранее принятом IO. Missing temp не различает «не создан», «перемещён» и «cleanup ещё не подтверждён». Из этих наблюдений требуемое заключение не следует.
4. OpenProcess по PID после restart не восстанавливает гарантированно прежний объект. PID имеет ограниченный lifetime; отказ OpenProcess, отказ доступа, PID reuse и отсутствие процесса в enumeration не принимаются как WAIT_OBJECT_0 нужного объекта. Persisted numeric HANDLE также не переносим между процессами. PID+creation time помогает сверке успешно открытого объекта, но не даёт гарантии его доступности после crash.

Это ограничение доказательства именно existing protocol, не утверждение невозможности любого Windows решения. Для полного пути нужна следующая минимальная дельта: **до любого physical dispatch удерживать реальный process handle во владельце, переживающем каждый writer и cleanup process, и сохранять exact association с execution до подтверждённого release**. Достаточен владелец lifetime/evidence; переносить само IO в новый service не требуется. Но existing composition такого владельца не предъявляет. Назначать его скрыто backend, DAG или SQL store нельзя.

Если допускается только single-writer-process loss, surviving host мог бы владеть witness; failure model должен прямо исключить потерю этого host до передачи/использования evidence. Для arbitrary одновременной потери всех владельцев volatile handles эта дельта недостаточна: необходим отдельно принятый способ восстановления evidence/иная storage discipline. Новый IO service/journal/framework OUT, поэтому такой вариант здесь не проектируется. Нельзя назвать частичное покрытие полноценным DF-01 PASS.

Решение для приёмки: принять конкретный process-object barrier как достаточный при перечисленных предпосылках; отклонить заявление о полном automatic finalization в текущем scope. Отдельное решение пользователя требуется о surviving lifetime и failure model. До него DF-01 остаётся OPEN с конкретным отсутствующим ресурсом, а не неопределённым «исследовать fencing». Unresolved — безопасное поведение, не результат закрытия задачи.

### Crash, unknown, ОС/FS и проверки

Crash до dispatch: отсутствие effects доказуемо только при authoritative ordering/association; no-link окна остаются DF-02. Crash в write/fsync/rename: process barrier означает terminated/cancelled, не success; partial temp допустим, final нельзя удалять. Crash cleanup: требуется его собственный witness. Crash после cleanup до release: replay повторяет evidence и идемпотентный exact cleanup; missing file не заменяет barrier. SQL unknown: existing quarantine/reread, без dependent IO/release до определённого исхода. WAIT_FAILED/ошибка close — infrastructure failure, не Unresolved с выдуманным успешным drain.

Предпосылки FS: root/control file не заменяются; redirects/reparse и remote shares исключены; все authorized mutators соблюдают protocol, legacy GC/holders — existing guards. Убийство отдельного thread не равно termination процесса. FlushFileBuffers/fsync и MOVEFILE_WRITE_THROUGH не являются cross-process completion census. Hardware cache writeback после OS completion не называется новой операцией writer; гарантия отсутствия любой физической активности носителя, power-loss durability или атомарности SQL+FS этим barrier не обеспечивается. Reboot/volume failure вне рассматриваемого process-loss proof. Actual FS/deployment пока не проверены; активация OUT.

Acceptance evidence: первичные API guarantees плюс inventory каждого syscall и ownership. Fault tests нужны для реализации, но не заменяют primitive: crash внутри write/fsync/rename/unlink; old writer после prohibition; crash второго finalizer; PID reuse/access denied; repeated cancellation; unknown prohibition/release; конкурентный legacy GC с holds. Ожидаемый успех — cleanup/release только после всех относящихся к execution barriers или lawful live joins; missing witness, обход gate либо premature release — FAIL. Никаких тестов и runtime изменений этим документом не выполнено.

Публичная граница остаётся StageAttemptService.finalize_execution(StageFinalizeInput) → StageFinalizeResult; guard/witness не входят в DTO. Error mapping RC-01 сохраняется: existing infrastructure/invariant/SQL unknown; отсутствие witness — existing proposed EFFECTS_NOT_QUIESCENT. Новых POJO/settings/CRUD/public операций нет. Источник порядка — deferred §3 и RC-CONSTRUCTION; предлагается конкретизация evidence шага, а не новая DAG стадия. Прямой DAG CALL остаётся прежним; branching следующего CALL — DAG; нет скрытого запуска или foreign public calls. Полная приёмка плана, POJO и цепочки не объявляется: Q2–Q6 и решение о witness lifetime OPEN. Пакет предназначен координатору `Between domain operations` через пользователя; межчатовая отправка этим разделом не выполняется.

Первичные источники (прочитаны 2026-11-27):

- [TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess): pending IO и асинхронное termination, необходимость wait.
- [Process Handles and Identifiers](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers): lifetime handles и PID; pseudo-handle не transferable witness.
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights): SYNCHRONIZE для wait.
- [LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex): предел exclusion, release и mapped views.
- [Canceling Pending I/O](https://learn.microsoft.com/en-us/windows/win32/fileio/canceling-pending-i-o-operations): cancellation не universal completion primitive.

## Приоритетный статус: этап 2 отложен в отдельный план

2026-11-26. По решению пользователя незакрытый execution finalization/crash-recovery этап вынесен в [artifacts-stage-finalization-deferred.md](artifacts-stage-finalization-deferred.md). Новый файл владеет backlog DF-01…04, условиями приёмки и порядком возобновления; описания этапа 2 ниже сохранены как proposal/evidence, а НЕ активное поручение реализации. Это включает finalizer/recovery jobs, OS gate, stage-2 local lifetime, no-link/crash/cancellation вопросы и междоменную интеграцию/новые имена. Их полнота и готовность не объявляются достигнутыми.

Текущий самостоятельный объём — раздел «Этап 1: синхронизация со штатным actual path», с собственной архитектурной приёмкой, continuous full claim/atomic seal и live cancellation guarantees. Этап 2 не является его blanket prerequisite; при этом перенос не снимает реальные требования этапа 1 и не выдаёт code-go или ARCH-0 PASS. Переход к этапу 2 требует отдельного возврата к отложенному плану. Эта запись имеет приоритет над всеми нижними перечнями реализации этапа 2; код/SQL/foreign документы не меняются.

Терминология по решению пользователя 2026-11-26: execution finalization — завершение конкретной stage execution, прекращение её effects, cleanup и освобождение claims. ArtifactStageFinalizer владеет этой ответственностью; штатный finish_live и finalize_execution после прерывания различаются предусловиями. Recovery отдельно решает допустимость следующей попытки. StageExecutionFinalized НЕ подтверждает успешную запись/публикацию или сохранность hold при доставке. Переименование применяется ко всем proposed классам, методам, POJO, mode FINALIZE и discriminator finalized ниже; compatibility aliases не вводятся. Код не меняется. Новые имена междоменных границ требуют синхронизации Publication/DAG через координатора; чужие документы этим owning изменением не переписаны, общий контракт не объявлен принятым.

## RC-CONSTRUCTION / RC-04 — архитектура finalization и lock order этапа 2

2026-11-26. Приоритетная корректировка constructor/ownership и lock-order описаний ниже. Только owning PLAN-ONLY proposal. Этап 1, Publication public API, DAG topology, GC алгоритм и код не меняются. Physical process-loss proof остаётся отдельным RC-01 OPEN. Согласуемый Publication constructor store сохраняется; он НЕ получает backend/registry/gate и НЕ исполняет physical finalization.

### Классы, методы и проверяемая ответственность

| Элемент / модуль | Exact target, зависимости и эффекты | Критерий отказа |
|---|---|---|
| SqliteStageAttemptStore, db.repositories.sqlite.artifacts.stageAttemptStore | Constructor(scopes, operations, catalog, *, stage_drain) без изменений. Только durable authority/inspection/transitions на existing UOW; backend/registry/job не хранит | OS acquisition, physical cleanup, ожидание worker или вызов finalization job из store |
| NEW ArtifactStageFinalizer, application.artifacts.staging.artifactStageFinalizer | Constructor(attempts: IStageAttemptStore, registry: ArtifactFormatRegistryBinding). async finalize_execution(request: StageFinalizeInput) -> StageFinalizeResult; async finish_live(claim: StageWriteClaim) -> None для owning writer после успешного live join/cleanup. Один gate/lifetime алгоритм, без нового persisted состояния | Новый authority issuer, successor/terminal, foreign public calls, fake live evidence или fallback к legacy delete |
| NEW ArtifactStageRecovery, application.artifacts.staging.artifactStageRecovery | Constructor(attempts: IStageAttemptStore, finalizer: ArtifactStageFinalizer), проверяет finalizer.attempts is attempts. async recover(request: StageRecoveryInput) -> StageAttemptResult. Внутренний recovery алгоритм с единственным finalization job и atomic successor recheck | Вызов public finalize_execution/recover, независимый cleanup/повтор SQL policy, запуск stage или выбор следующего DAG CALL |
| StageAttemptService, application.artifacts.staging.stageAttemptService | Constructor(attempts, *, finalizer: ArtifactStageFinalizer, recovery: ArtifactStageRecovery), exact dependency identities до IO. begin/inventory → store; finalize_execution → finalizer.finalize_execution; recover → recovery.recover. Каждый public метод делегирует ровно одному owning job | Branching между public операциями, получение gate/SQL scope в service, callback/worker orchestration |
| ArtifactFormatRegistryBinding, registry.artifactRegistry | Новый internal resolve_finalizer(ref: ArtifactRef) -> ArtifactStageFinalizationBackend. Тот же register_authorized и единственная format registration; check key/kind/version перед возвратом nongeneric capability | Второй registry/format key, default backend, поиск backend по operation/ref hash или cast в caller |
| NEW ArtifactStageFinalizationBackend, contracts.authorizedBackend | Узкий nongeneric ABC, inherited также AuthorizedArtifactBackend[C]. Read-only stage_authority: IStageAttemptStore; effect_gate: WindowsBlobEffectGate для текущего Windows BLOB пакета. async cleanup_under_guard(claim: StageWriteClaim, guard: BlobEffectGuard) -> None | Acquiring gate повторно, выдача claim/permit, seal/release, cleanup shared final. Это роль существующего backend, не новый service/engine |
| ContentAddressedBlobBackend | Required attempts/effect_gate constructor из physical пакета; реализует capability на том же instance, что write_authorized. cleanup_under_guard проверяет guard/root, exact FINALIZE claim и выполняет только deterministic temp cleanup с join | Запуск legacy write/delete, скрытая acquisition или новая authority из ref |
| ArtifactStageWriter, staging.artifactStageWriter | Этап-2 constructor COMP-01 дополнен required keyword finalizer: ArtifactStageFinalizer; finalizer.attempts is attempts, finalizer.registry is registry. После остановки dispatch/join вызывает finish_live до выхода full context | Store/full context пытается сам acquire gate; release до finish_live; дополнительный cleanup алгоритм в writer |

Новые jobs оправданы разделением IO-алгоритма и SQL adapter: store нельзя сделать владельцем backends без цикла. Это не вторые lifecycle/authority: все решения по persisted состоянию остаются в store, jobs не имеют своих записей, retries/очереди или policy. Recovery и finalization не копируют алгоритм друг друга. Отдельная nongeneric capability нужна потому, что cleanup не имеет content C; она не создаёт mirror domain DTO.

### Exact internal store boundaries и registry binding

StageWriteClaim остаётся issued runtime handle. Для FINALIZE он содержит read-only permit, claim_id и существующую StagingReservation для linked execution; это не public transport и не перенос live connection. Issuance само по себе не разрешает physical effect: обязательны gate и current persisted checks.

- async inspect_finalization(request: StageFinalizeInput) -> StageWriteClaim | StageFinalizeResult: coherent integrity/exact binding lookup, выдаёт FINALIZE handle для linked acquisition либо готовый finalized/unresolved. Никакого OS IO, изменения generation или writable acquire. Missing reservation/link не объявляется corruption автоматически: в текущем RC-03 OPEN случае вернуть INSUFFICIENT_EVIDENCE, ничего не release. Полный no-link алгоритм не объявляется закрытым этой корректировкой.
- async prohibit_effects_in_scope(scope, claim, guard) -> None: existing proposed §3.1 predicate/insert. Job владеет gate; store только проверяет issued handle/root correlation, SQL scope/task и facts. Unknown прекращает dependent IO.
- async release_finalized_in_scope(scope, claim, guard) -> None: exact prohibition/link recheck и local/full release одним UOW после выполненного evidence/cleanup контракта. Guard не является evidence; job не вызывает этот метод без доказанного основания.
- async prohibit_effects(claim: StageWriteClaim, guard: BlobEffectGuard) -> None и async release_finalized(claim: StageWriteClaim, guard: BlobEffectGuard) -> None: unbound internal wrappers store, каждый открывает один existing UOW и делегирует соответствующему scoped primitive. Job вызывает эти wrappers и НЕ получает scopes/access в constructor. Ни один wrapper не acquire OS gate. Проверку registered backend/root/gate выполняют job и backend; store проверяет live issued guard/task и собственную claim authority, не объявляет проверенным отсутствующий у него registry.
- async release_live(claim: StageWriteClaim, guard: BlobEffectGuard) -> None: один короткий UOW для exact live owner, linked local/full release после остановки dispatch и успешного backend join/cleanup. Integrity → current issued owner → absence prohibition/release → existing release predicates. При matching already released — no-op; при prohibition — EXECUTION_PROHIBITED без release. Не требует заново writable lease для прекращения завершённых работ; не создаёт completion. Failed cleanup не даёт права вызвать release_live.
- async inspect_recovery(request: StageRecoveryInput) -> StageAttemptResult | StageFinalizeInput: authoritative priority table; result либо existing exact operand требуемого finalization. Не исполняет physical работу.
- async finish_recovery(request: StageRecoveryInput) -> StageAttemptResult: атомарно повторяет completion/current authority/generation/release/partial-safety checks и existing successor transition. Не доверяет переданному bool и не создаёт второй successor. При недостаточном safety evidence возвращает Unresolved.

Для этапа 2 прежние IStageAttemptStore.finalize_execution/recover как полные physical операции WITHDRAWN. Store begin/inventory/claim_stage/seal_stage и stage-1 recover семантика остаются по своим отдельным описаниям. ArtifactStageRecovery вызывает inspect_recovery; только для полученного StageFinalizeInput вызывает internal finalization job, затем finish_recovery после StageExecutionFinalized. Unresolved переносится в owning recovery unresolved outcome без фиктивного успеха. Это локальные стадии одной recovery операции, не выбор следующей доменной операции/DAG маршрута.

register_authorized принимает backend, реализующий AuthorizedArtifactBackend[C] и nongeneric finalization capability, и сохраняет её в ТОЙ ЖЕ registration record наряду с existing contract/backend. Legacy register создаёт record без capability; resolve_finalizer такого формата отказывает до gate/IO, не использует legacy fallback. Перечень keys не дублируется, второй map для authority не создаётся. resolve_finalizer проверяет existing contract validator для ref, затем возвращает typed capability record; contract version/kind mismatch — ArtifactStorageInvariantError на owning finalization boundary с cause. Unknown/unregistered capability не превращается в empty inventory или successful drain.

### Assembly и nested trace без dependency cycle

Assembly: scopes/access → stateless drain → operations/catalog → attempts → leases/holders → Windows gate → backend(attempts, gate, leases) → register_authorized в existing registry → finalizer(attempts, registry) → recovery(attempts, finalizer) → service и writer. Store не имеет обратной ссылки ни на один из последних объектов. Registry не вызывает store при registration; backend constructor не вызывает job. До IO сверяются same scopes/access/coordinator, backend.stage_authority is attempts, backend.write_admission и catalog graph, backend root == gate canonical root; finalizer/recovery/service используют те же attempts/registry. Hot-rebind запрещён.

Caller trace: DAG → service.finalize_execution(request) → attempts.inspect_finalization (scope полностью закрыт) → registry.resolve_finalizer(request.binding.artifact) → target.effect_gate.acquire → attempts.prohibit_effects (short UOW) → evidence gate §P1.1.3 → target.cleanup_under_guard → attempts.release_finalized (short UOW) → close guard. Exact IStageAttemptStore.require_standalone() -> None проверяет existing unbound scopes predicate до lookup/OS acquire; чужой ambient scope не заимствуется. No-link/untracked/released outcomes завершаются до backend dispatch согласно inspect. Historical Confirmed не обходит residual finalization. FINALIZE view инвалидируется owning job в finally; это закрытие runtime handle, не запись full release.

Если evidence после process loss недостаточно, job возвращает Unresolved без cleanup/release. Никакая полнота constructor graph не закрывает RC-01. Normal live exit: writer запрещает dispatch и получает подтверждённое завершение backend workers И cleanup → finalizer.finish_live(claim) acquires gate один раз → attempts.release_live → close guard. Cleanup повторно не запускается. При failed cleanup или prohibition release не производится, pending acquisition сохраняется для exact finalization; основной fault не поглощается. При уже held guard внутри job private участок повторно acquire не делает. Full context store на выходе лишь проверяет подтверждённый exact release либо оставляет pending; не запускает job/OS IO, не выпускает local/full claim через unconditional finally и не пишет второй release. Existing stage-1 exit отдельно сохраняется. Live join не является durable proof после restart.

### RC-04: полный caller inventory и lock order

Gate НЕ добавляется в общий _io, legacy verify(ref), read_verified(ref) или delete(ref). _io_guarded — только authorized write/verify/cleanup. Общие _path/_verify/_place primitives сами lock не приобретают и SQL не вызывают; protection выбирает owning entrypoint.

| Caller → actual/target nested calls | Удерживаемая защита / порядок |
|---|---|
| TypedArtifactStager.stage → legacy backend.write → legacy service.seal | Existing local claim transactions завершены до IO; random legacy temp, no OS gate. Seal local claim → registry.verify без OS → catalog seal SQL; этап 1 неизменен |
| Existing ArtifactStageWriter.write / этап 1 → backend.write → registry.verify → seal | Existing local/full lifetimes не равны live SQL scope; no OS gate на legacy методах. Stage-1 verifier не становится authorized verify |
| Этап-2 writer → backend.write_authorized / verify_authorized | Require standalone → OS gate → short SQL authority → close SQL → awaited IO/join → close gate. Full/local claims удерживаются. SQL seal после physical batch; ни одна SQL transaction не ждёт OS |
| StageAttemptService.finalize_execution / internal recovery → ArtifactStageFinalizer | Lookup scope закрыт → OS gate → short prohibition UOW → evidence/cleanup → short release UOW → close gate. No reentrant gate |
| ArtifactStagingService.verify → catalog.guard → is_sealed/is_held → registry.verify → backend.verify | Existing SQL guard удерживается до конца физической проверки; backend.verify НЕ берёт gate/authority UOW. Holder/GC защита не выносится за scope |
| ArtifactGarbageCollector.collect → catalog.guard → catalog.read/holders.holders → registry.delete → mark_deleted | Existing SQL guard → physical delete без OS gate → mark_deleted в том же guard. Held ref не удаляется. Gate/finalization не вызываются из GC |
| ContentAddressedBlobBackend.read_verified → read_verified_file | Existing bounded read contract без нового gate/SQL. Дополнительная защита lifetime остаётся обязанностью existing caller, этим планом не усиливается |
| _temp exception / write-finally / finalization cleanup | Legacy random temp — existing cleanup без gate. Authorized deterministic temp — только под своим held gate с join; никто не удаляет чужие temps по prefix |

Причина совместимости: legacy writer/verify никогда не изменяют уже опубликованные final bytes; placement no-overwrite, verify только читает/fsync. Finalization удаляет ТОЛЬКО собственный deterministic temp; legacy random namespace с ним не пересекается. Каталожные holds сохраняются до full/local drain, поэтому GC не может удалить защищённый final. Если GC держит SQL, authorized path может ждать SQL с gate, но GC не ждёт gate: цикла ожидания нет. Физические операции legacy с другим artifact могут продолжаться, поэтому root gate НЕ объявляется mutex всех мутаций root. Он исключает только authorized execution effects между участниками этого протокола. Shared mkdir(exist_ok)/immutable placement не превращаются в execution-owned cleanup.

Нельзя подключить gate к legacy verify/delete «для полноты»: это нарушит порядок. Нельзя убрать catalog.guard/holder check: это потеряет existing GC guarantee. Если иной registered backend изменяет shared final in-place или его legacy методы ждут gate, данный composition отклоняется; общего GC redesign/новой платформы здесь нет.

### Порядок реализации и проверки ответственности

До кода принять contracts/jobs/registration capability и store-only boundary; затем реализовать store predicates, capability registration/composition tests, gate, authorized backend, finalization/recovery jobs и thin service. Existing stage-1 порядок не меняется. Код сейчас OUT.

Обязательные проверки: construct graph без late setter; store не импортирует backend/job; resolve exact version/kind/authority и no-capability refusal до IO; store methods не dispatch workers; normal exit не reacquire gate. Две connections: holder verify/GC удерживают SQL, authorized job удерживает OS и ждёт SQL — legacy путь завершается без ожидания OS, затем authorized продолжает. Обратный interleaving, cancellation во время ожидания, no-delete-held-final, shared content address/no-overwrite, namespace isolation и отсутствие gate acquisition в legacy verify/delete/read. Runtime PASS и общий этап-2 PASS не выданы. RC-01 crash proof и RC-03 full no-link finalization остаются отдельными OPEN.

## P1.1 — конкретный physical пакет Windows, архитектура реализации (PROPOSED)

2026-11-26. Только этап 2 общего ContentAddressedBlobBackend. Исследование НЕ зависит от manifest/climate workflow: это один physical implementation. Все прежние «сначала выбрать production binding» ниже снимаются как prerequisite ЭТОГО исследования; выбор/активация workflow остаётся OUT. Код/SQL/foreign contracts не меняются. Рекомендация: один OS effect mutex для backend root + existing SQL authority, без нового coordinator/service/journal. Это конкретный кандидат, но полный process-loss proof пока RESEARCH OPEN в точно указанной ниже границе; не переносить её решение на coding stage.

### 1. Existing / modified / new classes и критерии ответственности

| Элемент | Exact target / роль / deps / effects | Приёмка / отказ |
|---|---|---|
| NEW storage/artifacts/windowsBlobEffectGate.py::WindowsBlobEffectGate | Constructor(root: Path); async acquire() -> BlobEffectGuard. CreateFileW/LockFileEx одного постоянного control file; только OS exclusion, никакой SQL authority/policy | Один file object для root; отказ при redirect/unsupported FS, silent fallback, второй lock namespace |
| NEW в том же модуле BlobEffectGuard | Issued opaque handle, async close() -> None; task-owned lifetime, закрытие после join accepted workers | Не DTO/token/registry; нельзя unlock до завершения workers или использовать после close |
| MODIFIED ContentAddressedBlobBackend(root, contract, leases, *, effect_gate: WindowsBlobEffectGate, attempts: IStageAttemptStore) | Existing codec/path/temp/place/verify primitives; authorized методы используют gate и authority; exact same root/storage graph | Никаких публичных recovery calls, legacy bypass внутри authorized метода или optional guard |
| MODIFIED IStageAttemptStore / SqliteStageAttemptStore | Internal async assert_effect_allowed(claim: StageWriteClaim, guard: BlobEffectGuard) -> None; async prohibit_effects_in_scope(scope: CommitScope, claim: StageWriteClaim, guard: BlobEffectGuard) -> None | Existing UOW/authority, exact claim/root; не создаёт OS lock/worker. Prohibition — durable one-way факт той же execution, не новая generation |
| MODIFIED backend _io | Internal async _io_guarded(guard: BlobEffectGuard, call: Callable[[], T]) -> T, worker join/shield из existing _io; no SQL scope в worker | Проверенный живой guard до dispatch, закрытие guard после completion; contextvars не authority |
| Existing SqlitePublicationCommitStore/ScopedSqliteAccess/registry/driver | Без нового механизма: short UOW, BEGIN IMMEDIATE, scoped predicates, ACK/quarantine | Никогда ждать OS gate внутри SQL transaction; unknown не означает rollback |
| StageAttemptStore full/local contexts + ArtifactStageFinalizer job | Store — единственная durable authority, writer — этап-2 local lifetime; job управляет physical finalization по RC-CONSTRUCTION | Store не получает backend/gate dependencies, backend не acquire local claim, нет второго scheduler |

Guard привязан к конкретному gate/root и выданному handle, а store проверяет согласованную composition, не принимает произвольный похожий объект. Не требуется singleton Python wrapper: все экземпляры открывают тот же постоянный file object. Реализация не использует новый общемировой lock registry. Predicate authority единственный у Artifacts store. Новый class оправдан тем, что existing local SQL claims не блокируют syscall другого процесса; существующие backend IO algorithms не переписываются.

### 2. Concrete primitive и protected scope

Кандидат ограничен Windows/local NTFS, без remote shares/других ОС. Actual deployment FS не подтверждён; до применения проверить локальный том/FS и отсутствие reparse redirects. Root существует и стабилен до допуска workload. Control file `<root>/.stage-effects.lock` создаётся/открывается через CreateFileW OPEN_ALWAYS, GENERIC_READ|GENERIC_WRITE, FILE_SHARE_READ|FILE_SHARE_WRITE, БЕЗ FILE_SHARE_DELETE, без delete-on-close и без наследования handle. Никогда не удалять/заменять control file; это пустой synchronization объект, не journal/evidence. Создание control file — composition bootstrap до stage effects, не permission из permit. Его persistence/name и запрет replacement обязательны; администратор/посторонний процесс, заменяющий root вне протокола, не входят в гарантию.

LockFileEx exclusive range [0,1) с LOCKFILE_FAIL_IMMEDIATELY: contention означает «не приобретено», а не stale owner. Gate делает cancellable попытки без SQL lock и без выдачи worker до успешного захвата. Не использовать таймаут для break lock/объявления drain. Overlapped pending acquisition не создаётся; cancellation после успешного lock до доставки guard требует закрыть точный handle, не потерять его в отменённом executor result. Handle lifetime explicit, близок existing _io cleanup pattern.

Один root-wide gate выбран намеренно: покрывает _temp mkdir/namespace, создание/запись temp, placement, _verify с fsync и cleanup, включая shared directory effects. Per-ref lock не покрывает общие namespace mutations без дополнительных locks. Цена — serialization physical операций этого root; это явный tradeoff узкого механизма, а не новый scheduler. Byte-range lock НЕ блокирует автоматически запись других файлов: гарантия протокольная, все authorized effect paths обязаны взять gate. Не выдавать lock file за kernel fencing каждого path.

Никакой общий GC cutover здесь не вводится. Existing holds/local/full guards должны исключать удаление final artifact во время execution; finalized cleanup удаляет только exact собственный temp, никогда shared final. Если фактический concurrent mutator root не соблюдает эти guards (включая старую версию authorized writer), гарантия не применима — совместимость deployment mutators требуется предъявить до активации, не скрывать её.

### 3. Nested trace / linearization / lifetime

WRITE: full/local claim уже выданы owning path → backend.acquire OS gate → short existing read/UOW assert_effect_allowed exact operation/stage/generation/mode → закрыть SQL scope, сохраняя OS gate → один awaited _io_guarded batch (_temp → _place → exact temp cleanup) → join всех workers/handles → unlock/close OS guard. Verify — аналогичный отдельный gate batch с новой authority check; нельзя cache «allowed» между acquisitions. Seal остаётся SQL-only atomic seal/completion под local/full claims; этот пакет не меняет его owner.

FINALIZE: acquire ТОТ ЖЕ OS gate без SQL lock → existing write UOW проверяет exact execution и записывает prohibition → confirmed COMMIT запрета — linearization fencing → ОБЯЗАТЕЛЬНАЯ проверка evidence завершения already-submitted IO. При отсутствии основания после process loss вернуть StageFinalizeUnresolved(EFFECTS_NOT_QUIESCENT): запрет сохраняется, cleanup/local release/full release/successor НЕ выполняются, закрывается только собственный OS guard. Completion, отсутствие temp и успешный lock acquisition не обходят эту ветку. Только при доказанном основании допустимы exact cleanup под gate → short UOW local/full release → unlock. Prohibition не подтверждает drain. Representation и гонки определены в §3.1; это proposal этапа 2, не существующий stage-1 механизм.

Если old execution уже держит gate, finalize_execution не получает его до окончания batch; при паузе старого процесса ожидание не ограничено. Если old worker ещё только ждёт gate, после fencing он получает gate, повторно читает prohibition и не выполняет НИ write, НИ finally cleanup. Старый cached FINALIZE handle также не даёт права: каждое новое acquisition повторно проверяет authority; два finalize_execution сериализуются gate, второй после первого наблюдает persisted drained/released и ничего не удаляет. Не выполнять unlink в unconditional finally вне guard.

FINALIZE cleanup не требует current writable lease: проверяются exact старый claim/resource ownership и запрет повторного data write, но не reopen. Такой cleanup под gate и SQL authority допускается только для незавершённой exact finalization; ни другой stage, ни old mode не наследуют это право. Это изменение остаётся внутри owning store/backend, Publication public methods не вызываются.

Единый порядок locks: OS gate → short SQL UOW → release SQL → physical batch → optional short SQL → release gate. Нельзя удерживать SQL UOW, ожидая gate, иначе deadlock с worker/recovery. Existing backend-local claims и full lifetime не означают удержание UOW во время physical IO. Live SQL scope в executor не передаётся.

### 3.1. Authority representation и конкурирующие переходы (PROPOSED)

Для этапа 2 предлагаются две insert-only связи в `app.db.models.artifacts.stageAttemptRows`, обслуживаемые единственным SqliteStageAttemptStore. Это storage records без IO, не public mirrors, новый журнал или система holders. SQL сейчас не создаётся.

| Row / table | Поля, инварианты и критерий отказа |
|---|---|
| StageEffectProhibitionRow / artifact_stage_effect_prohibitions | operation_id, stage_id, generation (composite PK), claim_id; composite FK к exact StageAcquisitionRow. Наличие запрещает WRITE/VERIFY/seal этой execution, но не доказывает drain. Foreign/orphan claim — invariant fault; update/delete запрещены |
| StageLocalClaimLinkRow / artifact_stage_local_claim_links | operation_id, stage_id, generation (composite PK), claim_id, local_acquisition_event_id (unique FK к ArtifactWriterClaimRow.event_id), artifact_id. Full acquisition, local acquired event и reservation совпадают по operation/fence/artifact; release event не может быть target. Link и local acquisition создаются одним commit; mismatch/duplicate — invariant fault |

Эти отношения отсутствуют в existing rows: local event не содержит stage/generation, а full release означает завершение и не может обозначать один лишь запрет. Local release остаётся existing release chain; completion/full release — существующие proposed facts. Отдельные copies cleanup/drained status не вводятся.

Точный порядок predicates в existing BEGIN IMMEDIATE/UOW:
- local_writer: persisted integrity → exact full acquisition без release/prohibition → writable operation → local acquisition + link одним commit.
- assert_effect_allowed: issued guard/root/task и claim/mode → persisted integrity/links → WRITE требует отсутствие prohibition/release и current writable authority; FINALIZE требует prohibition, отсутствие release и exact resource ownership. Gate удерживается до конца physical batch.
- prohibit_effects_in_scope: проверить exact acquisition/links; already released означает no-op без cleanup. Иначе insert exact prohibition либо подтвердить совпадение. Completion допустим и сохраняется; writable operation не требуется. Drain не записывается.
- seal_stage: в том же commit, что scoped seal/completion, повторно проверить отсутствие prohibition/release и live linked local claim. Seal первым — historical completion сохраняется; prohibition первым — seal запрещён. Проверка до physical batch не заменяет recheck.
- normal exit: после successful join/cleanup и запрета dispatch вызвать ArtifactStageFinalizer.finish_live по RC-CONSTRUCTION. При prohibition/failed cleanup release запрещён и pending сохраняется; автоматического public finalize_execution/recovery нет. Без prohibition local/full release допустимы под gate. Already released exact execution — no-op после integrity проверки.
- finalization release: после evidence и cleanup одним коротким UOW проверить prohibition/link и записать existing local release + full StageReleaseRow. Unknown не подтверждает release. Crash требует повторного evidence gate, не продолжения по одному prohibition.

Guard не reentrant. Владелец acquisition — internal job/backend entrypoint; private cleanup/release primitives используют уже held guard. Normal finish_live и finalization имеют разные authority predicates по RC-CONSTRUCTION и не вызывают друг друга как public операции. Live join после restart не восстанавливается из prohibition; никакой successor из normal exit не выдаётся.

Предлагаемая public error дельта: `StageAdmissionCode.EXECUTION_PROHIBITED` в owning stageAttempt.py, через ArtifactStageAdmissionRejected(ArtifactStageAdmissionFailure(permit, code)) для exact запрета WRITE/VERIFY/seal. Это ожидаемый отказ, не corruption. Дельта требует координаторской приёмки до зависимой реализации; нода переносит payload целиком. Этап 1 её не использует. Нижний roster StageAdmissionCode дополняется только этим явно PROPOSED code, не считается уже принятым.

### 3.2. Ошибки и conversion boundaries

| Участок | Исход |
|---|---|
| Composition: разные root/authority, unsupported config | TypeError/ValueError до IO по existing composition policy |
| CreateFile/LockFileEx | Только lock contention допускает внутренний повтор acquire; прочие OS failures → existing PublicationInfrastructureError from OSError, не blanket retry |
| Cancellation acquisition | Join acquisition, закрыть действительно полученный handle, затем CancelledError. Ошибка закрытия — infrastructure с сохранением cancellation context |
| Foreign/closed guard, orphan/mismatched facts | ArtifactStorageInvariantError до dispatch |
| Exact prohibition WRITE/VERIFY/seal | Proposed EXECUTION_PROHIBITED carrier §3.1 |
| temp/place/verify/cleanup OS failure | PublicationInfrastructureError from OSError на backend boundary; existing codec/invariant errors сохраняются |
| UnlockFileEx/CloseHandle failure | PublicationInfrastructureError с cause; не UnknownCommitOutcome, собственный guard не считается подтверждённо закрытым |
| SQL uncertainty | Existing UnknownCommitOutcome и quarantine, без замены на refusal/Unresolved |
| Отсутствие process-loss evidence | StageFinalizeUnresolved(EFFECTS_NOT_QUIESCENT), без маскировки неуспешного storage read |

Guard закрывает owning context после join. При основной ошибке и cleanup fault сохраняются обе причины через cause/context. Подтверждённый seal/release не отменяется последующей OS/log ошибкой и не превращается в unknown SQL outcome. Failure-site tests обязательны до подключения backend.

### 4. Resources, crash/unknown и честная граница доказательства

Temp identity: existing random mkstemp/local list не восстановимы. Минимальная proposed дельта без нового ledger: один deterministic basename `.tmp-stage-<claim_id>.part` в existing format directory, где claim_id — уже durable unique StageAcquisitionRow.claim_id, canonical UUID, проверенный до path construction. Generation связано с claim row, новые IDs не выдаются backend. Create-exclusive, только одно temp на execution; existing file не truncate/overwrite, сначала exact ownership и disposition. StageBinding/ref задают directory, поэтому lookup deterministic после crash без prefix scan. Если future backend требует несколько temps — это новая дельта, не произвольный ordinal listing. Final path остаётся existing content address и никогда не удаляется finalizer.

- Crash до create: prohibition + exact missing temp допустимы только после доказанного drain accepted IO; отсутствие файла отдельно не proof.
- Crash после temp write/до placement: только после evidence gate §3 проверить exact temp и выполнить cleanup; иначе Unresolved без cleanup/release. Prior data не означает completion.
- Crash после MoveFileEx/до SQL seal: final может существовать; no-overwrite/full hash verify сохраняются. Не присваивать completion по файлу. Cleanup не удаляет final; retry решается owning recovery.
- Crash recovery после prohibition/до cleanup: следующий finalize_execution читает запрет и снова проходит evidence gate §3; без основания — Unresolved, не продолжение cleanup. Old WRITE не reopen.
- Crash после cleanup/до release: exact cleanup идемпотентен, но missing file не заменяет execution drain. Unknown SQL commit/quarantine запрещает dependent dispatch; новый lawful connection + authoritative reread, не второй fence/generation вслепую.
- Ошибка UnlockFileEx/CloseHandle: guard не объявляет release подтверждённым; неизвестность/infra сохраняются, full drain не повышается только из отсутствия Python task.

Доказано для cooperating ЖИВЫХ процессов: gate взаимно исключает admitted batches, повторная authority проверка предотвращает новые effects от old writer/cleanup после prohibition; existing _io join завершает batch перед explicit unlock. Это inference из lock semantics и указанного порядка, не runtime PASS.

RESEARCH OPEN для полного process-loss proof: LockFileEx документирует освобождение locks при termination/close, но НЕ устанавливает порядок «все kernel/filesystem requests другого файла окончательно drained → release lock control file». Existing worker future/handles после смерти процесса недоступны новому owner. Поэтому acquire root lock после смерти процесса сам по себе НЕ принимается как proof завершения уже submitted rename/fsync/unlink. CancelIoEx только для текущего процесса, не ждёт completion; MoveFileEx вообще не поддерживает такую cancellation. Это конкретный предел предложенного reuse, не утверждение математической невозможности Windows fencing.

Минимальная следующая дельта на решение пользователя, если нужен полный автоматический process-loss finalizer: дополнительное подтверждённое Windows/local-FS completion/barrier основание для already-submitted effects после termination. Его точный primitive должен быть доказан отдельно до кода; если такого in-process основания нет, потребуется surviving IO owner/иной storage placement protocol — оба OUT, здесь НЕ проектируются и НЕ поручаются. Без этой дельты сохраняется Unresolved/no successor/no hold release для непроверенного crash IO; срок ожидания не ограничен. Это не разрешение ослабить гарантию до «не публикует».

### 5. Первичные источники и пределы ОС

- [Microsoft LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex): exclusive byte-range lock, fail-immediate, release при process termination/close с возможной задержкой; mapped view не защищён. Поэтому control lock защищает наш протокол, не arbitrary filesystem mutation; mmap/remote storage не добавляются.
- [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew): sharing flags/lifetime и OPEN_ALWAYS. Запрет FILE_SHARE_DELETE не даёт заменить открытый control file; запрет его удаления между opens — deployment invariant, не абсолютная защита от внешнего администратора.
- [Microsoft MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw): same-volume move без COPY_ALLOWED/REPLACE_EXISTING сохраняет existing no-overwrite placement; WRITE_THROUGH не превращает SQL и файл в одну transaction.
- [Microsoft cancellation guidance](https://learn.microsoft.com/en-us/windows/win32/fileio/canceling-pending-i-o-operations): отменяемость зависит от driver, MoveFileEx среди неподдерживающих cancellation; timeout не proof.
- [Microsoft CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex): запрос отмены только current-process IO, не ожидание завершения. Он не заменяет cross-process drain.

### 6. Последовательность проверки/реализации, не code-go

Порядок этапа 2; следующий слой только после контракта, вызова и проверки предыдущего:
1. Архитектурная приёмка ДО кода: primitive/process-loss evidence либо явно принятая ограниченная гарантия; rows/transitions/association §3.1, errors §3.2, единственный temp mapping, composition и lifetime. Согласовать public EXECUTION_PROHIBITED. Research OPEN не передаётся исполнителю как выбор алгоритма.
2. Скелет принятых contracts/records/errors и composition; затем authority prohibition/link/release/seal на existing UOW. Проверки competing transactions, integrity, rollback/unknown. Один созданный скелет не закрывает слой.
3. Windows effect gate/guard: acquisition/cancellation ownership, dispatch/join/close, root identity, failure mapping.
4. Authorized backend: primitives под guard и authority checks, deterministic temp; затем writer-owned local context и atomic seal/completion. Никакого legacy fallback или backend-owned local acquire на новом пути.
5. Совместные two-connection/process tests: normal exit/finalize_execution, stale cleanup/seal, cancellation/unknown/replay. Crash без evidence обязан дать Unresolved без cleanup/release; тест ограничения не доказывает полный automatic recovery.

Production integration/activation не следуют автоматически из слоя 5. Этап 1 сохраняет собственный порядок ниже и не ждёт physical research этапа 2. Код этим перечнем не разрешён.

Обязательные probes: old process paused до/после gate и до syscall; stale WRITE и stale cleanup после prohibition; второй finalize_execution; cancellation между lock success и выдачей guard; worker cancellation during temp/place/verify/unlink; crash процесса и recovery на каждой из границ §4; no root-lock replacement; forbidden SQL→OS ordering; foreign root/claim; final remains unchanged; full/local release только после подтверждения. Tests подтверждают конкретную implementation, но не заменяют отсутствующую гарантию OS completion порядка. Production format/workflow/activation, другие ОС/FS, DAG/Engine/Publication changes и GC OUT. Этап 1 и blocking cancel неизменны.

## P1.3 / RC-02 — cancellation inventory: exact Output → Input, этап 2

### Q5 — окончательная Artifacts-форма для общей приёмки, 2026-11-27

Приоритетное уточнение RC-02 ниже. Только owning proposal, не runtime и не PASS общей цепочки. Сверено с Publication `artifacts-stage-recovery-publication-resolution.md`, § «Q5 — окончательная Publication-форма». Прежние имена ClosedReady/ClosedPending ниже читать как OperationCloseReady/OperationClosePending; settle не alias finalize_execution. Новый маршрут, NodeId, порядок или worker не вводятся.

**Публичная граница и POJO.** В `app.application.artifacts.staging.stageAttemptService.StageAttemptService`:

```python
async def pending_finalizations(request: OperationCloseInput) -> OperationStageFinalizationResult: ...
async def finalize_execution(request: StageFinalizeInput) -> StageFinalizeResult: ...
```

`OperationCloseInput` импортируется из proposed `app.dataModel.publication.operationClose`: operation_id: EntityUid; fence: strict int >= 1. Это coordinates, не lease и не разрешение effects. Остальные перечисленные здесь POJO принадлежат `app.dataModel.artifacts.staging.stageAttempt`:

| Тип | Полный состав / назначение |
|---|---|
| OperationStageFinalizationBatch | kind: Literal['batch']; request: OperationCloseInput; pending: tuple[StageFinalizeInput, ...] — полный inventory одной operation |
| OperationStageFinalizationRefused | kind: Literal['refused']; request: OperationCloseInput; code: ArtifactLeaseFailureCode, validation разрешает только OPERATION_MISSING, FENCE_MISMATCH, ADMISSION_OPEN |
| OperationStageFinalizationResult | discriminated union Batch / Refused по kind; не exception carrier |
| StageFinalizeInput | binding: StageBinding; generation: strict int >= 1 — существующий exact operand BF-01 |
| StageExecutionFinalized | kind: Literal['finalized']; binding: StageBinding; generation: strict int >= 1 |
| StageFinalizeUnresolved | kind: Literal['unresolved']; binding: StageBinding; generation: strict int >= 1; code: StageFinalizeUnresolvedCode |
| StageFinalizeResult | discriminated union StageExecutionFinalized / StageFinalizeUnresolved по kind |
| StageFinalizeUnresolvedCode | STAGE_UNTRACKED, GENERATION_UNTRACKED, EFFECTS_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE |

Все поля обязательны; records strict/frozen/extra-forbid/revalidate_instances=always. Existing StageBinding и OperationLeaseRef переиспользуются целиком, включая historical identity; их поля не копируются в новый inventory DTO. Batch.request == input; для каждого item binding.lease.operation_id == input.operation_id. Artifacts восстанавливает полный binding из validated immutable StageBindingRow, включая world_uid, kind, preparation_fingerprint и historical fence, и exact generation из acquisition chain. Current request.fence не подставляется в historical lease. Поля binding проверяются по его owning контракту, не реконструируются DAG из отдельных координат.

Нет пересечения с Confirmed (seal), OperationClosePending (operation observation), ArtifactLeaseFailure (обязательный lease) или runtime StageWriteClaim (authority): batch — inventory operands, finalized — confirmed exact release, refusal — отказ inventory без lease. Новых field-error POJO и второго enum ошибок не требуется. Отказ при зеркале foreign POJO, synthetic lease, optional operands/defaults либо экспорте claim/guard/storage scope.

**Exact Output → Input.** Только confirmed `OperationClosePending` с `pending=OperationDrainPending.FULL_STAGE` или `BOTH` поставляет `close_result.request` в explicit DAG CALL `pending_finalizations(close_result.request)`. Для Batch DAG проверяет корреляцию request и передаёт каждый `item` из `batch.pending` целиком отдельному public CALL `finalize_execution(item)`. Никакого конструирования StageFinalizeInput/lease, поиска нового fence, чтения storage либо вызова Publication из Artifacts. Refused не имеет pending. Ошибка корреляции — infrastructure fault, не попытка поправить DTO. LOCAL_WRITERS, Ready, Terminal, Busy и exceptions не создают этот CALL. BOTH сохраняет отдельное требование local drain. Publication final UOW остаётся единственным местом проверки всех local/full claims перед release/terminal operation; batch и результаты items её не заменяют.

**Доказательство полноты на coherent cut S.** Обозначим A(S) — все committed full-stage acquisitions данной operation за все stage_id, generations и historical fences; X(S) — exact confirmed releases, прошедшие integrity checks. Требуемое множество P(S) = A(S) \\ X(S). Release сопоставляется по полной persisted acquisition identity, включая claim_id; DTO unique(stage_id,generation) допустим лишь при доказанной уникальности acquisition этой пары. Два разных acquisitions одной пары — invariant fault, а не dedup. Completion C, current/latest generation, наличие local link/reservation/temp, sealed artifact и current hold НЕ входят в фильтр P. Поэтому historical C с residual cleanup, no-link acquisition и stale generations входят наравне с остальными.

Store читает authority/admission, полную retained history acquisitions/releases и bindings в одном coherent scope. Исходная совокупность — acquisitions, не inner join с optional binding/completion/link, способный потерять повреждённую строку. Для каждого A устанавливаются exact binding и release disposition; dangling X/link/completion и несовместимые цепочки проверяются отдельно. Отсутствие обязательного binding/удалённая history/невозможность установить membership — fault всего вызова. Законное отсутствие ещё не созданных R/L/C не corruption и не основание пропуска. Batch строится и выдаётся только после полной проверки, в стабильном порядке stage_id/generation. Взаимно однозначное отображение P(S) в pending доказывает soundness и completeness; при недоказанной уникальности или полноте результат не выдаётся.

Предпосылки доказательства: close/issuance/consumption сериализованы общим authoritative UOW; acquisition регистрируется до handoff/effects; closed policy запрещает новые acquisitions и не переоткрывается тем же fence; history сохраняется по retain/no-deletion policy; release означает точный confirmed переход, а не completion. Проверяются все callers. Без этих предпосылок Q5 не проходит приёмку: SQL snapshot сам по себе не доказывает запрет будущих acquisitions.

| Гонка / состояние | Обязательный исход |
|---|---|
| Acquisition выиграла до close | A видна на cut после confirmed close; потерянный ACK acquisition не удаляет её из inventory |
| Close выиграл до acquisition | Consumption/acquisition отказывает в своей UOW; старый выданный permit не обходит повторную проверку |
| Close → concurrent release → inventory | X до S исключает item; X после S оставляет item в batch, finalize повторно читает exact X и становится no-op |
| Close → inventory, authority/fence изменились | Повторная проверка current fence в S; FENCE_MISMATCH, без подмены request. Старый batch также не bearer authority |
| Historical completion без X | Включить; finalizer не делает early return по Confirmed и не удаляет published final artifact |
| Unconsumed permit, без A | Не execution, не включать; local-only legacy writers учитывает отдельный operation drain |
| Unknown acquisition/release outcome | Existing authoritative reconciliation/quarantine до результата; нельзя считать unknown отсутствующим A или подтверждённым X |

После успешного S новые A запрещены, releases лишь уменьшают P. Следовательно каждый ещё pending execution содержится в выданном batch, хотя часть items к доставке уже finalized. Это inventory guarantee, НЕ доказательство physical quiescence: Q1/Q2/Q3/Q4 finalizer evidence сохраняются, неизвестный drain не разрешает release.

**Stale/direct/terminal и ошибки (точные owning имена).** Проверка persisted integrity precedes refusal. Clean missing operation без orphan facts → Refused(OPERATION_MISSING); missing operation с stage/admission facts → ArtifactStorageInvariantError. Matching operation со stale request → Refused(FENCE_MISMATCH); открытая законная admission → Refused(ADMISSION_OPEN). Mandatory missing admission или open admission при terminal → ArtifactStorageInvariantError. Direct operation без admission допускает empty только при authoritative policy, запрещающей staging acquisition, и полном отсутствии stage/local facts; противоречие — fault. Direct Ready не trigger inventory. Terminal, наступивший после Pending, не early empty: current fence, terminal prohibition и residual P проверяются полностью. Terminal от close сам по себе не добавляет переход в inventory. Old fence В binding item допустим; old fence В inventory request — refusal.

Publication close сохраняет собственные exceptions: ValidationError, PublicationInfrastructureError (в том числе missing/stale), UnknownCommitOutcome, CancelledError, OperationBusyError. Artifacts НЕ заменяет их своими Refused и не извлекает proof из Busy. Для inventory malformed input → ValidationError; integrity violation → existing `app.application.artifacts.errors.ArtifactStorageInvariantError` (подкласс PublicationInfrastructureError); прочие infrastructure failures → PublicationInfrastructureError с cause; UnknownCommitOutcome/CancelledError распространяются без batch. Refused использует только три названных code. Для finalize сохраняются StageBindingRejected при durable operand mismatch, ValidationError, infrastructure/unknown/cancellation; Unresolved — только подтверждённая недостаточность owning evidence, не catch-all для ошибок storage. Unknown read/commit никогда не маскируется STAGE_UNTRACKED/GENERATION_UNTRACKED.

**Пустой batch, доставка и частичный прогресс.** Empty означает P(S)=∅ после всех проверок, например releases закончились между Pending и S; не противоречит прежнему Pending и не подтверждает local drain/terminal. Duplicate inventory получает новый coherent cut, поэтому pending может уменьшиться. Duplicate delivery item проверяет immutable identity и matching X: confirmed finalized без повторных cleanup/release; concurrent finalizers сериализуют physical работу по existing gate и перечитывают X. Unknown release ACK не success: replay устанавливает X authoritative чтением либо повторяет lawful evidence path. Частично обработанный batch не атомарен: завершённые items сохраняют X, остальные остаются pending. При Unresolved/exception/cancellation нельзя сообщать batch success или operation drain. Повтор exact items безопасен; повтор inventory возвращает остаток только при всё ещё допустимом request. Исчезновение ранее известного binding/history — fault, не successful untracked. Никаких компенсационных reacquire, successor, rollback уже выполненных releases или скрытого фонового retry. Выбор продолжения/остановки и retry — только DAG по согласованному порядку, не service.

**Граница реализации и приёмка.** StageAttemptService — thin validated delegation; IStageAttemptStore/SqliteStageAttemptStore — один read-only coherent inventory без physical IO и foreign public calls; ArtifactStageFinalizer — единственный internal evidence/cleanup/release job через existing registry и SQL primitives RC-CONSTRUCTION. POJO — только данные. Нарушения соответственно: hidden orchestration, latest reads вне scope/пропуск строки, release без evidence/новый authority, IO в модели. Publication остаётся владельцем close/final UOW, DAG — ветвления и явных CALL. Все три запрета DAG сохраняются; утверждённый порядок deferred §3 не переставляется. Это специальное чтение cancellation inventory, не list/CRUD; настройки, create/update/delete API не добавляются. Никаких cursor/page/limit, stream partial results или скрытого усечения. Невозможность материализовать полный batch — ошибка без batch; batching API потребовал бы отдельного принятого контракта.

Acceptance cases: несколько stages и old generations/fences; C без X; no-link A; duplicate pair; missing binding/orphan release; stale/direct/terminal; обе сериализации acquisition/close; release до/после S; lost ACK A/X; empty после concurrent release; duplicate и concurrent finalize; exception после первого из нескольких items; Unresolved с сохранением claims; BOTH с оставшимся legacy local writer; отсутствие любого DAG storage read/lease construction. Ожидаемый inventory всегда exact P(S) либо целиком отказ/exception, никогда частичный список. Это требования к будущим проверкам, не выполненные runtime тесты.

Локальная синхронизация имён и error boundaries с Publication предъявлена. Общая приёмка Q5 остаётся OPEN до сверки всей цепочки назначенным координатором `Between domain operations` и решения пользователя; Q1–Q4/Q6 этим разделом не закрыты. Пакет передаётся через пользователя, чужие планы не изменяются и межчатовая рассылка не выполняется.

2026-11-26. Owning correction для общей приёмки. Прежние OperationStageFinalizationInput(lease) и lease-содержащие inventory outcomes WITHDRAWN. Код и этап 1 blocking cancel не меняются.

### Архитектура и ответственность

| Элемент | Контракт / ответственность / критерий отказа |
|---|---|
| Publication OperationCloseInput, app.dataModel.publication.operationClose | Reuse proposed POJO: operation_id: EntityUid; fence: strict positive int. Artifacts импортирует тип напрямую; mirror coordinates/lease не создаёт |
| StageAttemptService, app.application.artifacts.staging.stageAttemptService | async pending_finalizations(request: OperationCloseInput) -> OperationStageFinalizationResult. Один вызов owning store, без public Publication calls, закрытия admission или запуска finalize_execution |
| IStageAttemptStore / SqliteStageAttemptStore | Та же async signature; один coherent read scope для operation authority и полного inventory. Запрещены latest-read до scope, подмена lease и пропуск corrupt execution |
| OperationStageFinalizationBatch, dataModel.artifacts.staging.stageAttempt | kind='batch'; request: OperationCloseInput; pending: tuple[StageFinalizeInput,...]. Только проверенные полные StageBinding/generation; unique(stage_id,generation), stable order stage_id/generation |
| OperationStageFinalizationRefused, тот же модуль | kind='refused'; request: OperationCloseInput; code: existing ArtifactLeaseFailureCode, только OPERATION_MISSING/FENCE_MISMATCH/ADMISSION_OPEN. Остальные codes запрещены validation |
| StageFinalizeInput / StageBinding / OperationLeaseRef | Reuse existing proposed finalize_execution operands и existing lease; нет второго DTO для возвращаемой execution. Полные поля восстанавливает Artifacts из authoritative immutable stage binding, не DAG |

Новые records strict/frozen/extra-forbid/revalidate_instances=always. OperationStageFinalizationResult — discriminated batch/refused union. ArtifactLeaseFailure НЕ используется для inventory: его mandatory lease отсутствует во входе, фабрикация lease недопустима. Refusal — outcome этой операции с доступными operands, не mirror lease failure; новый enum не нужен. Malformed input → ValidationError; corruption/IO → existing infrastructure category с cause; UnknownCommitOutcome/CancelledError не превращаются в пустой batch/Unresolved. Внутри dataModel нет IO.

### Exact mapping и nested trace

1. Publication public close_for_cancellation возвращает OperationClosePending(request, pending). При pending FULL_STAGE/BOTH единственный inventory input — САМ result.request: OperationCloseInput. operation_id и fence произведены этим confirmed output; дополнительных полей, storage reads и неуказанной continuation нет.
2. DAG передаёт result.request в public StageAttemptService.pending_finalizations. Метод не трактует payload как authority: store повторно проверяет current facts в своём coherent scope.
3. Artifacts возвращает batch.pending. Каждый item уже StageFinalizeInput с полным immutable binding и generation. DAG переносит item целиком в public finalize_execution, не конструирует lease.
4. world_uid, kind, preparation_fingerprint и historical fence внутри item.binding.lease происходят из validated StageBindingRow, зарегистрированной begin до execution. Они сверяются с owning operation/stage facts в storage scope. Missing required binding — corruption; никакого восстановления по ref/latest/fake defaults.
5. Batch.request сохраняет exact request coordinates. Каждая execution относится к request.operation_id; её historical lease.fence НЕ заменяется request.fence. Current fence допускает inventory, а finalization проверяет exact старую execution, без reopen/write authority.
6. После finalization только Publication final UOW проверяет ВСЕ local/full claims перед operation release/terminal. Empty batch и отдельный StageExecutionFinalized этого не заменяют.

Это mapping уже предъявленных операций, не назначение новых NodeIds или порядка workflow. Выбор следующего CALL остаётся DAG. Все nested storage reads — внутри Artifacts, прямых foreign public calls нет.

### Authority, полнота, stale/direct/terminal

Порядок в одной SQLite snapshot: persisted integrity operation/admission и ВСЕХ stage chains → request current fence → отсутствие допуска новых acquisitions → полный inventory. Clean missing operation возвращает OPERATION_MISSING; missing operation с orphan stage/admission — infrastructure fault. Stale request fence → FENCE_MISMATCH. Open admission → ADMISSION_OPEN. Закрытое admission не выдаёт права release.

Batch включает КАЖДУЮ acquired generation без authoritative confirmed release для operation: прежние fences, stage generations и Confirmed с residual cleanup. Unconsumed permit не execution. Completion не фильтр drain; corruption/неразрешённый authoritative outcome не пропускаются и не дают partial batch.

Direct operation без staging admission: пустой batch допустим только если existing authoritative operation policy исключает stage admission и ВСЕ stage/local facts отсутствуют. Не создаётся lease/admission. Если policy допускает stage, но обязательной admission нет, либо direct policy противоречит stage/local facts, это infrastructure fault. Отсутствие lease само по себе не доказывает empty.

Current terminal не используется как early empty/drained: после current fence/integrity checks проверяется весь residual inventory. Terminal должен исключать новые acquisitions по owning lifecycle policy; contradictory open admission — fault. Historical completed execution может остаться pending. Это допустимость Artifacts запроса, НЕ новый workflow переход из Publication Terminal: его mapping остаётся у координатора.

Publication ClosedReady и ClosedPending(LOCAL_WRITERS) не поставляют stage inventory trigger; local-only writer не превращается в stage. Busy/Unknown/exception не считаются close output. Если между close и inventory сменился fence — refusal, никакого чтения нового fence из DAG. Если операция завершилась — Artifacts проверяет terminal/current facts по правилам выше.

### Конкурентность и критерии проверки

Confirmed close и inventory не одна transaction. Полнота обеспечивается повторной current closed/no-future-admission проверкой вместе с полным чтением в ОДНОМ scope; consumption/issuance конфликтуют с close через existing write UOW. Consumption до close виден, после close запрещён. Finalization/release может уменьшать inventory; batch не lock и не bearer authority. Duplicate finalize_execution обязан повторно проверять exact execution и исключать второй cleanup.

Полный batch без pagination/truncation; bounded paging потребует отдельного принятого контракта, молчаливое усечение запрещено. Refusal/unknown не возвращают частичный список. Pending BOTH не означает, что batch перечисляет legacy local-only writers: operation final guard продолжает учитывать их отдельно.

Обязательные тесты: Output.request → exact Input без дополнительных данных; Python/JSON полной пары; stale fence; clean missing/orphan; direct no-admission empty и contradictory direct facts; terminal с residual Confirmed; несколько stages/generations/старых fences; consumption до/после close; concurrent release и repeat inventory; corrupt item не пропущен; ни один lease не создаётся DAG; batch не разрешает release всей operation.

Статус RC-02: Artifacts выбрал reuse OperationCloseInput и предъявил точный mapping, вместо требования полного lease на входе. Publication уже описывает operation_id/fence как inventory input; окончательная междоменная приёмка и решение пользователя ещё нужны. Stage DTO в Publication, новые issuer/lease API и storage reads из DAG не требуются. RC-01 physical crash proof, RC-03 no-link path и RC-04 lock-order проверяются отдельно; этим mapping они не закрыты.

## Этап 1: синхронизация со штатным actual path — приоритетная редакция

2026-11-26. По поручению пользователя после сверки actual механизмов. PLAN-ONLY: этот раздел замыкает target caller trace для локальной приёмки, не объявляет реализацию или весь контракт принятым. Он имеет приоритет над нижними COMP/BF предложениями в отношении ЭТАПА 1. Выбранное пользователем направление — поэтапное расширение, а не одновременная замена backend/registry/local claims/cancel.

### Один штатный trace

1. Public authorized stage: existing pure admission/descriptor check, затем writer. Required permit+prepared остаётся публичной target дельтой; scope/claim не появляются в DAG Input.
2. Writer проверяет standalone/same composition и атомарно потребляет permit через IStageAttemptStore.claim_stage. Полный StageWriteClaim приобретён ДО reserve; выдаётся только после confirmed acquisition. При unknown нет backend dispatch и нет второго claim.
3. Existing catalog.reserve проверяет operation authority и приобретает hold. Full claim не заменяет этих predicates. Reservation сверяется с exact permit binding/ref.
4. Existing backend.write(reservation, content) выполняет свой existing LOCAL writer acquisition, worker IO, cancellation drain и temp cleanup, затем release LOCAL claim. Writer НЕ приобретает внешний local claim вокруг этого вызова: иначе existing no-active-writer check откажет. Content/descriptor/codec semantics сохраняются.
5. Full claim остаётся active в промежутке после backend.write. Writer приобретает existing второй LOCAL writer через admission.writer(reservation) для verify/seal. Нельзя считать отсутствие local claims в промежутке полным drain.
6. Под вторым local claim выполняется общий internal verification job и затем IStageAttemptStore.seal_stage(full_claim,reservation). Последний открывает один existing Publication UOW; проверяет exact stage authority/current operation, live local reservation writer/hold, вызывает единый catalog.seal_in_scope и записывает exact completion в ЭТОМ scope. Ref до confirmed commit provisional.
7. После confirmed commit выходит второй local context; full claim освобождается только после завершения всех вызванных workers/local cleanup. ARTIFACT_SEALED logging сохраняет existing policy и не отменяет completion. Post-commit cleanup/log fault не превращается в rollback/absence.

Это сохраняет два существующих local участка и добавляет непрерывный full lifetime. Полный lifetime не держит долгую SQL transaction на physical IO. Cleanup temp остаётся внутри backend.write ДО verify/seal. Статус success не усиливается до гарантии hold при доставке ответа.

### Конкретные классы и минимальные signatures этапа 1

| Класс/модуль | Target дельта и ответственность | Критерий отказа |
|---|---|---|
| ArtifactStageWriter, application.artifacts.staging.artifactStageWriter | Existing contract/registry/catalog/admission/log dependencies + required attempts: IStageAttemptStore; write(permit: StageAttemptPermit, prepared: PreparedArtifact[C]) -> ArtifactRef (async). Registry.resolve возвращает existing ArtifactBackend; existing write_admission graph checks сохраняются | Optional permit/fake authority; второй local acquire вокруг backend.write; выдача successor/recovery loop |
| IStageAttemptStore, application.artifacts.storage.stageAttemptStore | claim_stage(permit) -> AbstractAsyncContextManager[StageWriteClaim]; async seal_stage(claim, reservation) -> ArtifactRef. Durable initial authority/full claim/completion; собственный generation не заменяет operation fence | Unknown acquisition как отсутствие, release до backend drain, отдельный completion commit |
| ArtifactReservationVerifier, proposed application.artifacts.staging.artifactReservationVerifier | Constructor(registry: ArtifactFormatRegistryBinding, admission: IArtifactWriteAdmission); async verify(reservation: StagingReservation) -> None. Единственная existing последовательность assert_writable → registry.verify(ref) → assert_writable; local claim удерживается caller | Никаких acquisition/commit/публикации/recovery; не второй codec/descriptor algorithm |
| SqliteArtifactCatalog, db.repositories.sqlite.artifacts.catalogStore | async seal_in_scope(scope: CommitScope, reservation: StagingReservation) -> ArtifactRef; existing seal predicates/effects перенесены сюда ОДИН раз. Existing seal открывает existing transaction и делегирует; authorized seal_stage вызывает scoped primitive в своём UOW | Две копии predicates; nested bind/commit; provisional ref выдан как confirmed |
| ArtifactStagingService.seal, application.artifacts.staging.artifactStaging | Existing public signature/legacy consumer сохранены; свой local context → общий ArtifactReservationVerifier → existing catalog.seal. Existing ref/log проверки сохраняются | Вызов public authorized stage, synthetic permit или третья verify/seal реализация |
| ArtifactFormatRegistryBinding / ArtifactBackend / ContentAddressedBlobBackend | На этапе 1 register/resolve/verify/write contracts остаются existing. Обязателен real worker drain при cancellation до возврата/raise; full caller держит lifetime | Legacy method объявлен restart-safe или worker продолжает effects после завершения await |
| SqliteStageExecutionDrain + Publication lifecycle consumers | Existing согласованный scoped predicate: проверять full claims вместе с local; stateless adapter same access/registry; waiting cancel сохранён | True только по отсутствию local claims; global busy-return cutover |

ArtifactReservationVerifier — внутренний job, не pipeline/новая нода. Вложенные calls остаются внутри Artifacts; public фасады не вызывают друг друга. Последовательность verify+seal единая по primitives, transaction owner различается явно: legacy standalone против authorized seal+completion. Existing catalog predicate/ref validation не копируются в verifier.

Registry compatibility этапа 1 не требует AuthorizedFormatBinding/register_authorized/resolve_authorized: существующий backend остаётся явной зависимостью штатного writer. Это ограниченная live-execution гарантия, а НЕ opaque fallback в crash-safe path. Caller full claim покрывает весь awaited write/verify и existing backend drain; backend не интерпретирует stage generation и не обещает atomic physical fencing. Требование COMP-01/02 explicit claim на каждой physical границе остаётся у этапа 2 и не считается выполненным этим trace.

### Что отложено, а что обязательно

### Исправления локального review этапа 1 — durable authority / release / composition

Этот подраздел конкретизирует три замечания review; все storage additions остаются PROPOSED до общей приёмки. Не разрешает SQL/код и не добавляет второй coordinator/operation lifecycle. Прежнее «representation не предъявлено» заменяется следующей предлагаемой моделью этапа 1; физическое crash fencing остаётся OUT.

**1. Persistent facts — минимальная необходимая дельта.** Existing ArtifactLeaseEventRow содержит только operation/fence/admission; ArtifactWriterClaimRow — artifact/operation/fence; ArtifactStorageEventRow — storage seal без stage identity. Ни одна запись не позволяет отличить два logical stage одного ref. Добавлять stage completion в OperationRecord terminal неверно. Поэтому предлагаются отдельные нормализованные facts Artifacts, не generic event journal и не новая система holders. Reuse existing ScopedSqliteAccess/row mapper/transaction driver; операции выполняет один SqliteStageAttemptStore, drain читает те же facts.

Proposed frozen storage rows в `app.db.models.artifacts.stageAttemptRows` (не публичные DTO; перечисленные поля отражают storage shape, публичные lease/ref не зеркалируются новым API):

| Row / proposed table | Поля / constraints |
|---|---|
| StageBindingRow / artifact_stage_bindings | operation_id, stage_id (composite PK); world_uid, operation_kind, preparation_fingerprint, operation_fence; artifact_kind, format_key, format_version, content_hash, nbytes, row_count. Полный immutable binding, FK operation_id к existing operation |
| StageGenerationRow / artifact_stage_generations | operation_id, stage_id, generation (composite PK), predecessor_generation nullable; FK к binding; generation positive. В этапе 1 только generation=1, predecessor=NULL; successor issuance OUT |
| StageAcquisitionRow / artifact_stage_acquisitions | operation_id, stage_id, generation (PK/FK generation), claim_id (unique opaque existing runtime_uid value). Не больше одного consumption на generation |
| StageCompletionRow / artifact_stage_completions | operation_id, stage_id (PK/FK binding), generation, claim_id, artifact_id; FK exact acquired generation/claim и existing catalog. Не больше одного completion на logical stage |
| StageReleaseRow / artifact_stage_releases | operation_id, stage_id, generation (PK/FK acquisition), claim_id exact. Confirmed release значит live execution перестала иметь возможность dispatch и все запущенные работы drained |

Все facts insert-only, no deletion/update в этом срезе. Индексы/FK связывают composite identities, а не только отдельно существующие IDs; uniqueness completion не позволяет второй generation записать второй исход. Состав claim_id не public permit и не право, выводимое из строки. StageWriteClaim проверяется как issued handle текущего store/task/lifetime, correlated с persisted acquisition. Row decoding восстанавливает existing OperationLeaseRef/ArtifactRef через strict validation: malformed enum/hash/count/fence, orphan или несовпадающий operation/catalog binding → ArtifactStorageInvariantError/PublicationInfrastructureError до business refusal. Отсутствие acquisition при completion/release — corruption. Completion без release допустим; release без completion допустим после неуспешной попытки. Issued без acquired не active execution.

begin в одном UOW сверяет operation authority и immutable binding, вставляет binding+generation 1 либо возвращает exact current result. claim_stage в одном UOW проверяет binding/generation/open authority и вставляет acquisition; duplicate consumption → declared stage admission refusal, не второй writer. seal_stage в одном UOW сверяет live issued full handle, acquisition без release, current lease/local writer/hold, scoped seal и completion artifact_id; catalog descriptor должен совпадать с binding. Release не меняет completion. Ни один method не пишет отдельный evidence commit после seal. Drain predicate: acquired без matching release = active; malformed chains = fault; отсутствие acquisition у issued permit не препятствует READY. После process loss active остаётся active, не infer drain.

Partial creation: binding+initial generation atomic; acquisition отдельно подтверждён до dispatch; reservation/physical effects могут существовать независимо от completion. Unknown commit не хранится как ложный status absence: registry quarantine/error сохраняются, authoritative reread выполняется лишь после законного восстановления connection. Stage-1 public recover не выдаёт successors: exact completion → historical Confirmed; incomplete consumed → Unresolved согласно таблице без crash takeover. Generation/predecessor schema оставляет future relation явной, но этап 1 не реализует её переходы.

Эти пять facts — конкретное предложение persistence, не существующие tables. При реализации потребовалась бы отдельная явно разрешённая правка `0001_initial.sql` и sync row models; сейчас их нет и они не создаются. Разделение фактов обосновано insert-only policy и уникальностью отдельных commits; нельзя заменить их неограниченным JSON log, mutable generic status engine или таблицей holders. Критерии: corrupt/orphan/duplicate negatives, atomic begin/consumption/seal, two-connection uniqueness, same-scope rollback и unknown injection.

**2. Cancellation-safe полный context.** `claim_stage(permit)` остаётся async context manager. Concrete private methods SqliteStageAttemptStore: `_acquire(permit: StageAttemptPermit, claim_id: EntityUid) -> StageWriteClaim` (async), `_release_live(claim: StageWriteClaim) -> None` (async), `_drain_release(claim: StageWriteClaim) -> None` (async). Claim_id выделяется один раз до acquisition, exact replay не выделяет новый; callbacks/выдача handle не происходят до confirmed acquisition. Это owning methods, не public nodes/DTO.

State/lifetime внутри context: acquiring → issued → closing → released. Closing запрещает дальнейший dispatch через этот execution owner. Обычный stage последовательно awaits backend/local contexts; backend контракт гарантирует worker drain ДО возврата/raise. Поэтому normal exit и исключение обрабатываются после завершения этих await. Full release производится только после закрытия обоих возможных local contexts; ошибка local release/worker cleanup оставляет full acquisition unreleased, не теряется за generic finally. Seal completion при этом не отменяется.

Acquisition cancellation: commit store может подтвердить COMMIT и затем поднять CancelledError. Context, ещё не выдавший handle, сохраняет original claim_id и через scoped lookup проверяет exact acquisition. Confirmed absent (rollback) → ничего release; confirmed matching acquisition без выдачи handle → `_drain_release` (worker dispatch структурно ещё невозможен); mismatch → fault. Unknown/невозможность lookup → preserve uncertainty, не pretend release и не новая acquisition. Это отличается от process loss: в живом контексте контроль выдачи handle доказан порядком исполнения.

`_drain_release` запускает один защищённый cleanup task и ждёт его завершения через shield-loop по existing SqliteArtifactLeases._cleanup pattern; повторная CancelledError фиксируется, не прерывает ожидание release ACK и не создаёт второй cleanup task. После confirmed release повторно распространяется cancellation. Release проверяет exact acquisition/claim и отсутствие completion ambiguity влияющей на authority; insert matching release в коротком existing UOW. Already present matching release идемпотентен, foreign release corruption. Ошибка/unknown release не поглощается и не превращается в cancellation success: категория infrastructure/UnknownCommitOutcome сохраняется, исходное исключение сохраняется cause/context; store не объявляет drained. Ошибка stage без проблем cleanup распространяется неизменной. Проверка unknown completion не должна запрещать безопасное прекращение live работ, но не разрешает infer rollback/compensation.

Физический backend обязан завершать accepted worker effects до raise; если это не доказано для concrete binding, context НЕ вправе использовать один факт возврата coroutine как evidence. Для existing BLOB local `_io`/finally поведение проверяется tests; для generic backend такое свойство — обязательный binding admission criterion, не blanket PASS. Full context не создаёт scheduler и не занимается чужим worker loop.

**3. Точное подключение общего verifier.** Proposed ArtifactReservationVerifier(registry: ArtifactFormatRegistryBinding, admission: IArtifactWriteAdmission) хранит read-only registry/admission identity; `verify(reservation) -> None` async выполняет только existing assert/verify/assert. Catalog seal predicates остаются только catalog, codec вызывается только registry; verifier не логирует.

Target constructors (required keyword, no default/самосборки второго job):

    ArtifactStageWriter(contract, registry, catalog, admission, log, *, attempts: IStageAttemptStore, verifier: ArtifactReservationVerifier)
    ArtifactStagingService(registry, catalog, leases, holders, gc, ledger, log, *, verifier: ArtifactReservationVerifier)

Оба constructor проверяют verifier.registry is registry и verifier.admission is соответствующий admission/leases до IO. Один verifier instance допускается, но не обязателен: он stateless, важны dependency identities. Writer после второго local acquire вызывает verifier.verify ровно один раз, затем attempts.seal_stage; legacy service.seal внутри своего local acquire — verifier.verify ровно один раз, затем catalog.seal. Проверка возвращённого ref и existing logging остаются на своих границах, без второго emit внутри verifier. Public service methods не вызывают друг друга.

Actual constructor call inventory по `rg` backend: `tests/snapshotCore/storage/artifacts/test_staging.py` — fake lifecycle setup, restarted setup и SqliteBlobLifecycleTests setup; `tests/typing/snapshotCore/valid.py::sqlite_composition`. Все получают verifier из своих registry/admission, включая restarted graph; fake job, скрывающий verify, не заменяет integration tests. Production ArtifactStageWriter/ArtifactStagingService constructor calls в проверенном backend/app не найдены; не назначать PacksWiring их factory по догадке. Новые stage-1 test composition обязаны собрать real attempts + verifier и общий access/scopes/drain graph. Перед implementation повторить call inventory из-за параллельных изменений.

Delivery порядок внутри этапа 1: принять эту storage/transition дельту → row/strict facts + transaction store/drain → cancellation-safe full context → единый scoped catalog seal → общий verifier и явные constructor callers → public authorized writer/pipeline → meaningful integration/typing tests. Каждый следующий слой после контракта и проверки предыдущего. Это внутренний порядок реализации, не изменение DAG процесса. Runtime acceptance по этим описаниям не выдана.

Нижние proposed AuthorizedArtifactBackend, StageLocalWriter, перенос local acquisition из backend, seal_stage(full,local,reservation), FINALIZE mode, durable temp identity, cross-process physical fencing и busy-return cancel относятся к этапу 2 и НЕ являются условиями реализации этапа 1. Их ранние формулировки «заменяет» не заменяют приведённый здесь stage-1 контракт. Нельзя активировать второй этап простым использованием первого без новой приёмки.

Обязательны в этапе 1: durable facts и same-scope binding по review-коррекции выше; single-R/composition checks; correct typed Error; unchanged generic identity; full/local lifecycle guards; concrete live worker-drain evidence. Persistence representation теперь предъявлена как proposal и требует приёмки до code-go storage среза; callback/in-memory registry её не заменяет. Выбор production crash-recovery binding НЕ blanket blocker этих внутренних контрактов.

Publication cancel сохраняет close → wait local+full вне write UOW → final recheck → release/terminal. READY проверяет local+full в своей transaction без ожидания под lock. Close до seal → refusal без completion; seal до close → historical completion, затем cancel ждёт release. После process loss могут остаться бессрочные unresolved claims/holds; никакого auto retry/release/fence takeover. Принятый этап 1 не обещает успешное завершение отмены после crash.

### Проверки локальной приёмки

- Задержать исполнение между backend-local release и second-local acquire: cancel/READY не проходят full guard, GC сохраняет protection.
- Cancel во время worker, repeated task cancellation: backend завершает worker/cleanup до возврата, full release позже; existing waiting tests сохраняются.
- Confirmed acquisition и потеря ACK/cancellation: не второй dispatch; unknown release не считается drained.
- Fault между scoped seal и completion: один rollback; reservation/physical effects не объявляются отсутствующими. Lost ACK commit: UnknownCommitOutcome, без компенсации.
- Foreign scope/operation/admission/registry rejected; standalone entry не заимствует ambient transaction, внутренний seal UOW допускается только owning store.
- Legacy ArtifactStagingService и authorized writer используют один verification job/одни catalog predicates; при migration нет удвоения codec/verify вызовов, событий или commits.
- Full Error/identity regressions сохраняются; никакого изменения Engine/nodes/foreign public contracts из этого среза.

Итог синхронизации: stage-1 caller trace предъявлен для review; proposed persistent authority и реализация ещё не приняты. COMP/BF crash-recovery OPEN не перенесены на штатную запись. Код и foreign планы этим разделом не меняются.

## COMP-01/02/03/05 — concrete composition correction (PROPOSED)

2026-11-26. Приоритет над несовместимыми ранними sibling-port/cleanup формулировками ниже. Только документация; missing production binding НЕ мешает предъявить generic composition delta. Physical file fencing по-прежнему не доказан. COMP-04 принадлежит Publication, новый cancel waiting contract не принят этим пакетом.

### COMP-01 — registry и authorized path

Existing evidence: application/artifacts/registry/artifactRegistry.py::register требует isinstance(backend, ArtifactBackend), backend.contract is contract, уникальный key; resolve возвращает ArtifactBackend[C]; verify(ref) вызывает backend.verify(ref). ArtifactStageWriter.__init__ проверяет backend.write_admission is admission. Sibling ABC из BF-02 этому не соответствует.

Коррекция: proposed `AuthorizedArtifactBackend[C](ArtifactBackend[C])` в contracts/authorizedBackend.py — capability subclass с НОВЫМИ различимыми методами, не несовместимым override:

    @property stage_authority -> IStageAttemptStore
    async write_authorized(claim: StageWriteClaim, reservation: StagingReservation, content: C) -> None
    async verify_authorized(claim: StageWriteClaim, reservation: StagingReservation) -> None
    async cleanup_authorized(claim: StageWriteClaim, reservation: StagingReservation) -> None

Старые write/verify/delete/contract/write_admission остаются отдельным existing API; никакого optional claim, вызова legacy write из authorized метода или inferred authority по ref. Concrete subclass обязан явно реализовать обе поверхности либо не объявлять поддержку legacy writer; consumer cutover должен устранить такой вызов до активации. Существующий unclaimed verify для read/legacy не используется authorized stage.

Proposed immutable internal `AuthorizedFormatBinding[C]` в registry/artifactRegistry.py: contract: ArtifactFormatContract[C]; backend: AuthorizedArtifactBackend[C]. Это runtime DI pair, не domain DTO/новый format key и не durable authority. Новые методы ТОГО ЖЕ registry:

    register_authorized(contract: ArtifactFormatContract[C], backend: AuthorizedArtifactBackend[C]) -> AuthorizedFormatBinding[C]
    resolve_authorized(binding: AuthorizedFormatBinding[C]) -> AuthorizedArtifactBackend[C]

register_authorized выполняет одну existing register (тот же key, одна запись) и возвращает typed binding. resolve_authorized проверяет identity обеих ссылок с единственной existing _bindings записью и возвращает binding.backend, без cast или type-erased value в caller. Самодельный binding не обход: обе identity сверяются с registered objects, unregistered/mismatch → fail-fast TypeError/ValueError до IO, как existing composition. Existing внутренний cast legacy resolve этим предложением не расширяется; новых casts не нужно.

Target ArtifactStageWriter constructor `(binding: AuthorizedFormatBinding[C], registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog, attempts: IStageAttemptStore, admission: IArtifactWriteAdmission, log: ArtifactLifecycleLog)`. Он использует resolve_authorized(binding), проверяет backend.stage_authority is attempts (runtime authority owner) и existing backend.write_admission is admission/catalog graph. Это не требование singleton для stateless drain. DescriptorBuilder/codec reuse existing contract+registry encode; stage verify идёт непосредственно в resolved backend.verify_authorized(claim,reservation), НЕ registry.verify(ref). Registry.validate(ref) сохраняется.

Migration: factories выбранного format переходят на register_authorized ВМЕСТО register, не рядом; authorized writer получает returned binding. Legacy TypedArtifactStager и ArtifactStagingService verify используют existing API до отдельного cutover; новый route не вызывает их. Read/GC consumers прежних verify/delete не получают фиктивный claim. Concrete factories сейчас PacksWiring register_manifest/climate/grade — кандидаты migration только если их binding выбран. Проверки: duplicate key rejected; forged/mismatched DI pair rejected; вызовы authorized stage никогда не попадают в legacy verify/write; same content/descriptor/authority identity. OPEN: concrete capability subclass и его physical guard, не generic registry wiring.

### COMP-02 — existing local claim и closed finalization

P1.2: единственная target модель ЭТАПА 2 — внешний claim_stage(full), внутри него local_writer(full,reservation), внутри ОБОИХ contexts write → verify → seal → finish_live(full). Backend не приобретает и не освобождает local claim. Единственная normal release точка — attempts.release_live из finish_live: existing scoped local release и full StageReleaseRow в ОДНОМ UOW после подтверждённого join/cleanup. Local context остаётся открытым до подтверждения commit. Его __aexit__, как и full __aexit__, только инвалидирует runtime handle и проверяет exact outcome; не пишет release и не запускает cleanup/OS IO. Unknown/failed release оставляет persisted pending, не выдаёт успешный выход. При ошибке seal допустима та же release точка после доказанного join/cleanup, без требования успешного seal и без ложного rollback. No-link path остаётся RC-03 OPEN. Этап 1 сохраняет прежние два local участка. Критерий: один local acquire, один общий release commit, ноль release writes из обоих __aexit__ и backend.

Existing leaseStore.py::writer требует writable lease, exact reservation+hold и отсутствие active writer; выдаёт None, держит ArtifactWriterClaimRow локально и _cleanup освобождает его. _release не требует writable, но принимает только известный acquired row, не получает stage generation. Следовательно новый обычный writer acquire при closed/stale finalize_execution недопустим.

Минимальная target boundary в storage.stageAttemptStore, реализуется concrete SqliteStageAttemptStore:

    local_writer(claim: StageWriteClaim, reservation: StagingReservation) -> AbstractAsyncContextManager[StageLocalWriter]
    async release_local_in_scope(scope: CommitScope, claim: StageWriteClaim, local: StageLocalWriter) -> None

StageLocalWriter — internal issued runtime handle exact existing ArtifactWriterClaimRow, read-only reservation/full-claim correlation; не wire DTO/новая generation. local_writer разрешён только WRITE full claim и open authority. Acquisition existing local row и StageLocalClaimLinkRow из §P1.1.3.1 выполняются в ОДНОМ UOW; handle выдаётся после confirmed commit. Backend повторно local claim не приобретает. Existing row shape/release chain reuse; exact association теперь предложена в §3.1, её приёмка и реализация ещё не выполнены.

Finalization восстанавливает association из authoritative facts и завершает ТУ ЖЕ local claim через scoped release после доказанного physical drain, без writer(reservation), нового acquire или reopen. FINALIZE capability проверяет original binding/generation, ownership row и finalization exclusion; current operation fence может отличаться, но нельзя release чужую/новую row. Already released exact row идемпотентно подтверждается по цепочке; missing association при active row → invariant fault/неподтверждённый drain, не wildcard release. Normal exit и finalize_execution используют одну scoped release проверку; конкуренция завершается одной release записью, без allow_rollback как общего разрешения. Unknown association/release → unknown, повтор не создаёт второй local claim.

Проверки: closed/stale finalize_execution не вызывает ordinary writer; unrelated active claim остаётся; duplicate finalize_execution/normal exit не дают double release; unknown acquire/release не объявляют drained. OPEN: приёмка proposed association §P1.1.3.1 и backend process-loss proof; representation не оставлена на выбор исполнителя.

### COMP-03 — file resource identity и cleanup порядок

Existing blobBackend.py::write хранит temps только в local list, _temp использует random mkstemp prefix hash(operation_id,fence), _place размещает final, finally unlink происходит ДО возврата write и до later verify/seal writer. После crash этот список теряется; prefix не различает stage/generation, и поиск/удаление всех matching temp запрещены. Новый after-seal cleanup не может молча заменить этот actual порядок.

Target для file capability, если выбран: сохранить порядок write_authorized(temp/create/place → cleanup exact temp → return) → verify_authorized → scoped seal. cleanup_authorized используется как общий идемпотентный primitive из write-finally и finalize_execution; post-seal вызов нужен только для реально оставшихся ресурсов, не переносит temp deletion после seal. Исключение cleanup до seal не подтверждает успех; after-seal failure сохраняет durable completion и pending drain.

Для ContentAddressedBlobBackend действует только §P1.1.4: один `.tmp-stage-<claim_id>.part` из durable acquisition и format directory из binding. Create-exclusive/containment обязательны; shared final не принадлежит cleanup. Прежний StageTempResource с ordinal/opaque relative_name, отдельным сохранением имени и resource preparation WITHDRAWN: этот класс/таблица/allocator не создаются. Выбор workflow не prerequisite исследования общего backend. Другие backend с несколькими temps здесь не проектируются.

Даже durable temp identity НЕ решает cleanup fencing: old WRITE cleanup, old FINALIZE cleanup и новый finalize_execution должны атомарно исключаться в МЕСТЕ unlink/rename, а не только проверять SQL до вызова. Exact resource identity решает «что», effect guard решает «кто ещё может менять». Existing backend такого OS guard не имеет. Поэтому нельзя честно объявить COMP-03 закрытым без physical mechanism; новый Python mutex/SQL flag недостаточен. Проверки: crash до create/после create до записи/после placement; одновременный old finally и finalize_execution; shared final никогда не удаляется; отсутствие temp не заменяет drain принятого worker. No broad scans, no new purge.

### COMP-05 — full/local/seal/completion порядок

Existing catalogStore.py::seal проверяет live local writer для reservation, writable lease и hold; собственная SqliteArtifactScope.transaction даёт standalone commit. Если backend освобождает свой local guard и следующий verify/seal не приобретает новый — seal откажет; второй standalone commit evidence запрещён.

Authorized target последовательность: full WRITE context → reserve → local_writer context → backend.write_authorized (включая temp cleanup) → backend.verify_authorized → seal_stage(full,local,reservation) → внутри того же local context finish_live(full) → один commit local+full release → local __aexit__ → full __aexit__. Оба __aexit__ не освобождают persisted claims повторно. Signature seal_stage(claim: StageWriteClaim, local: StageLocalWriter, reservation: StagingReservation) -> ArtifactRef сохраняется. Backend не владеет acquisition/release. На exception-пути finish_live допустим только после доказанного join/cleanup; иначе claims остаются pending, основной fault сохраняется. Порядок repeated cancellation требует отдельного закрытия P2, здесь не объявляется решённым.

seal_stage открывает один existing commits.transaction(operation_id), проверяет exact full generation/claim + exact linked live local row + reservation/hold + current operation authority, вызывает `SqliteArtifactCatalog.seal_in_scope(scope,reservation)` (provisional), записывает exact completion в этом же scope. Возврат ref только после confirmed commit. Local/full claims остаются live во время commit; release после commit не является вторым commit completion и не отменяет completion. Exception/unknown ведёт к drain/cleanup под теми же claims без ложного rollback; unknown release остаётся pending. Никакого await standalone seal внутри UOW.

При closed finalize_execution seal не вызывается, completion не создаётся; после historical Confirmed завершаются только residual effects и linked local/full releases. Publication проверяет совместимость exact guard порядка и cancel; её public services не вызываются writer-ом. Тесты: остановка между write и verify — обе claims удерживаются; fault между scoped seal и completion — общий rollback; lost ACK commit — exact evidence; cancel не освобождает holds до обеих release; foreign local handle отвергается. OPEN: actual scoped implementation/persistence и Publication сверка; statement о необходимости live local guard теперь замкнут в proposed caller trace.

Итог COMP: 01 generic binding/resolve path уточнён; 02 scoped exact local release предложен; 03 resource identity delta и physical exclusion gap разделены; 05 signature/order уточнены. Это не общий PASS и не production выбор. Earlier sibling write/verify names и backend-owned local acquire на target path ЭТАПА 2 WITHDRAWN; этап 1 и legacy paths сохраняют свой явно описанный порядок.

## Actual backend audit для совместной приёмки — 2026-11-26

PLAN-ONLY. Проверены runtime declarations/callers в backend/app, а не только fixtures. Ни один найденный binding не объявляется выбранным для authorized recovery. pack-staging-completion-cutover.md прямо оставляет manifest specialization candidate; backend-fencing.md также не назначает production binding. Ниже existing и необходимая дельта разделены. Все пути в таблицах относительно backend/.

### Реальные кандидаты и единственный недостающий выбор

| Кандидат C / key / storage version | Actual backend, ресурсы и callers | Статус выбора |
|---|---|---|
| bytes / world_pack.manifest.json / 1 | app/storage/artifacts/manifestBlobBackend.py::ManifestBlobBackend(root, leases, max_bytes); inherits ContentAddressedBlobBackend. PacksWiring.initialize_pack_storage → register_manifest_format; root = database parent/artifacts. app/application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation вызывает TypedArtifactStager.stage, затем finish_preparation | Реальный production wiring/legacy caller, но новый route candidate, не accepted specialization |
| bytes / world_pack.climate_field.zstd / 1 | app/application/worldData/pack/encoding/climateFieldFormat.py::CLIMATE_FIELD_FORMAT; PacksWiring.initialize_pack_storage → register_climate_field_format → ContentAddressedBlobBackend(root, contract, leases); тот же disk root/worker механизм | Реальная registration; не доказательство выбора recovery route |
| bytes / world_pack.grade_slots.json / 1 | gradeSlotsFormat.py::grade_slots_format(limits); PacksWiring.register_grade_slots_format → ContentAddressedBlobBackend. В проверенном app вызов этой factory не найден | Реальная factory, activation не подтверждена |
| bytes / hydrology.open_water.root.tlv и hydrology.open_water.shard.tlv / 1 | generators/hydrology/encoding/packFormats.py::ROOT_FORMAT/SHARD_FORMAT; keys в dataModel/hydrology/pack/profile.py; Pack OpenWaterBlobReader — reader caller | Форматы/reader реальны, concrete production writer registration в проверенном app не найдена |
| SQL_ROWS | В проверенном backend/app нет concrete ArtifactBackend subclass для SQL_ROWS; test.rows — fixture, не production binding | Нет основания назначать вариант SQL ради удобства |

Нужен ровно один выбор для продолжения concrete BF-03: **какой реально необходимый production format/backend binding из маршрута является первым предметом crash-recovery приёмки**. Если это иной SQL_ROWS/backend — требуется ссылка на его concrete writer/composition, а не имя теста. Найденные BLOB candidates не выбираются автоматически и не отменяют прежний запрет BLOB-first. Поля C/key/version/class/resources для двух зарегистрированных кандидатов уже предъявлены; повторно спрашивать их вместо выбора не требуется.

### Карта всех effects найденного файлового backend

Строки F1–F8 совместно покрывают полный write/verify/cleanup путь ОБОИХ зарегистрированных candidates и grade-slots factory. Manifest override меняет только read budget; физическая реализация общая app/storage/artifacts/blobBackend.py. Кодеки manifest/climate/grade выполняют pure semantic decode/validation; их перенос — отдельный consumer contract, не physical fencing.

| Backend/effect / actual method | Existing защита | Минимальная недостающая дельта | Применимый вариант |
|---|---|---|---|
| F1 namespace mkdir; _temp: final.parent.mkdir(parents=True) | Path containment, symlink/junction rejection через _contained; предварительный lease check | Effect-time fencing и учёт namespace creation; SQL check до mkdir не атомарен | 2, не реализован |
| F2 _temp: mkstemp, write/flush/fsync, _verify temp | Random temp; prefix hash(operation_id,fence); local reservation writer; hash/size verification | Exact execution/generation ownership temp, fencing создания/записи, durable disposition после crash; prefix не различает stage/generation | 2, не реализован |
| F3 _sync_directory(root.parent/root), _verify directory fsync (POSIX) | Durability sync; на Windows _sync_directory no-op | Включить sync в завершение accepted effects; отсутствие async task не подтверждает окончания IO | 2 |
| F4 _place: Windows MoveFileExW WRITE_THROUGH/no replace либо POSIX os.link | No overwrite; повторный writable check до dispatch; final hash/size verify | Нужна общая с authority atomic physical fencing граница; повторный SQL check и content addressing этого не обеспечивают | 2 |
| F5 _verify final/temp; public verify → _io | Чтение chunks; Windows r+b; file fsync и directory sync, containment | Explicit claim и worker completion; verify не pure/read-only по effects, не выпадать из drain | 2 |
| F6 _temp exception и write finally: unlink(missing_ok=True) | Cleanup известного local Path; normal finally после awaited _io | Cleanup exact execution-owned path после restart; исключение старого/второго cleanup worker; нельзя удалять по broad prefix | 2 |
| F7 _io: run_in_executor(copy_context().run,...), shield/join при cancellation | Local cancellation ждёт завершения executor future; exceptions извлекаются | Не даёт cross-process exclusion/restart proof; copied context не передаёт валидный live SQL scope/task authority | 2 |
| F8 backend.delete: unlink final + directory fsync | Caller GC/holder/writer guard обязан быть удержан | OUT finalizer: нельзя использовать как cleanup опубликованных shared blobs. Сохранить existing GC discipline, не расширять purge | Не часть нового finalize_execution |
| SQL reserve/hold/local claims: catalogStore.py::reserve, leaseStore.py::writer/_cleanup | Existing transaction/lease/fence и reservation guard | Связать с full generation, не выводить authority из ref; local guard subordinate | 1 для SQL facts, не всего BLOB |
| SQL seal: catalogStore.py::seal | Existing local writer/hold predicates, own transaction | scoped seal + exact completion в одном UOW; independent standalone commit forbidden | 1 для SQL facts, не F1–F7 |

Actual ContentAddressedBlobBackend constructor `(root: Path, contract: ArtifactFormatContract[bytes], leases: IArtifactLeases)` не принимает StageWriteClaim/effect guard; ManifestBlobBackend `(root, leases, *, max_bytes)` также не принимает. Рабочие методы write/verify и cleanup therefore НЕ соответствуют proposed authorized port. Это конкретный API gap, не готовый constructor, который можно включить без physical design.

### Что именно можно reuse из SQLite

app/db/repositories/sqlite/shared/transactions/transactionDriver.py::SqliteTransactionDriver.begin использует BEGIN IMMEDIATE для write, BEGIN для read. _acknowledge сохраняет UOW owner и ждёт aiosqlite worker ACK при cancellation; commit/rollback failure не доказывает rollback. snapshotCore/commitScope.py::SqlitePublicationCommitStore._transaction запрещает ambient/nested transaction, берёт GuardedConnection.unit_of_work, выдаёт registry scope и отзывает его в finally; uncertain commit/rollback → quarantine + UnknownCommitOutcome. shared/access/scopedAccess.py::ScopedSqliteAccess проверяет scope через registry до row IO. Reuse этих механизмов предпочтителен, второй coordinator не нужен.

Условная SQL-only реализация (не найденный production binding): каждая backend mutation и проверка generation должны выполняться в одном BEGIN IMMEDIATE UOW над тем же authoritative database. Fencing transition конкурирует с этими transactions; confirmed COMMIT запрета — linearization, ранее захвативший write lock effect уже commit/rollback, следующий writer читает запрет и отказывает. Только если ВСЕ effects, включая cleanup, удовлетворяют этому условию, применим вариант 1. Statements/таблицы generation пока не существуют в принятом binding — их нельзя написать фиктивно вместо evidence. Для F1–F7 BEGIN IMMEDIATE удерживает SQLite writer lock, но не предотвращает OS эффект другого worker и не откатывает file effects.

### Уточнение BF-01/02: normal exit, finalization и cleanup конкуренция

Существующий ниже proposal public StageAttemptService.finalize_execution(StageFinalizeInput) → StageFinalizeResult и internal IStageAttemptStore.finalize_execution сохраняется без повторного проектирования. Publication busy-cancel proposal НЕ принят: automatic close → finalize_execution → drain/release требует отдельного согласования, finalize_execution не вызывается из Publication service/adapter. Historical Confirmed/closed/stale fence не разрешают новые data writes, но finalization exact старой execution не должен early-return до residual cleanup/drain.

Обязательная concrete дельта для выбранного backend: normal-exit cleanup и concurrent finalize_execution должны конкурировать на ОДНОЙ authority завершения exact generation. Issued FINALIZE handle не даёт общего права unlink: каждое cleanup действие проверяет exclusivity/ownership в той же effect boundary; старый WRITE/FINALIZE worker после fencing не должен продолжать cleanup. Если старый cleanup уже принят, новый finalization ждёт его завершения/подтверждённой отмены; SQL флаг сам по себе не разрешает второй physical cleanup. При unknown cleanup/release повтор читает durable evidence и проверяет physical disposition, не объявляет drained из missing temp. Concrete реализация этой границы для file candidates пока отсутствует; добавление mutex только в Python-процессе не закрывает crash fencing.

Для этапа 2 действуют COMP-01 методы write_authorized/verify_authorized/cleanup_authorized с explicit claim. Full claim выдаёт/освобождает owning StageAttemptStore/StageWriteClaim context; LOCAL claim приобретает ArtifactStageWriter через attempts.local_writer один раз до write и удерживает через verify/seal. Backend использует эту защиту, но НЕ вызывает local acquire/release. Освобождение — выход того же owning context после drain; crash finalization завершает exact прежний claim согласно COMP-02. Full claim не снимается между стадиями, local guard не заменяет его. Backend-owned acquisition относится только к actual/этапу 1. Target file adapter не вызывает legacy write как fallback: каждый F1–F7 должен быть подключён к concrete effect guard, который пока OPEN.

### BF-03: проверяемая transaction карта и предел доказательства

Сохраняются точки нижеследующего BF-03 proposal: acquire → effects → fencing → finalization/drain → successor. Для SQL facts reuse UOW/ACK/quarantine доказан чтением actual кода. Для file effects durable prohibition старого WRITE И старого FINALIZE worker не предъявлен, поэтому никакая транзакционная таблица этой записки не закрывает физический слой.

Необходимые crash probes после выбора binding: acquisition commit до ACK (не выдавать второй claim); partial file/SQL commits до seal (не объявлять отсутствие эффекта); fence commit до drain (resume exact finalization без re-open); cleanup commit до release ACK (не второй unguarded cleanup); drain commit до issuance (recheck operation, не bump дважды); issuance commit до ACK (exact predecessor replay); seal commit до cleanup (Confirmed отдельно от drained). Unknown на каждом шаге не компенсируется re-open/unconsume/release. Concurrent normal exit/finalize_execution/recover должны сходиться к одному durable completion/drain и максимум одному successor. Пока concrete physical marker/lock и restart-путь отсутствуют, отсутствие зависания не обещается: Unresolved/hold могут сохраняться бессрочно.

### Рекомендация и результат для решения

Вариант 1 рекомендуется ТОЛЬКО для реально необходимого SQL-only binding, которого в проверенном production app не найдено. Для manifest/climate/grade на existing file backend требуется вариант 2 — адресная physical дельта; её нельзя назвать минимально реализуемой, пока не выбран binding и не предъявлен effect-time fencing mechanism. Не менять storage формат ради удобства fencing. Следующий конкретный вход — выбор production binding из первой таблицы либо ссылка на иной actual writer. Без него остаются BF-02 concrete constructor/guard и BF-03 physical serialization; generic API proposal не выдаётся за решение.

Ownership/nested calls: DAG → public begin/stage/recover/finalize_execution; внутри Artifacts → owning store/backend primitives; scoped Publication infrastructure только transaction/operation authority, без foreign public service. Read-only drain не запускает cleanup. Writer не выбирает recovery branch; finalize_execution не выдаёт successor; маршрутом управляет DAG. Новые ноды/порядок не назначены. Изменён только этот документ; production registration, код, SQL, общий framework/GC OUT. Итог для совместной приёмки: actual audit предъявлен, полный PASS цепочки НЕ выдан.

## Дополнение BF-01/02/03 — предложение crash-recovery этапа

Прочитан artifacts-stage-recovery-backend-fencing.md §8. Нижеследующие additions — PROPOSED, не code-go и не доказательство concrete backend. Они не блокируют отдельно принимаемый штатный stage. Production format/backend binding по-прежнему не назначен; BF-03 не закрывается абстрактной схемой транзакций.

### BF-01. Завершение execution отдельно от replay/выдачи successor

Предложение public `StageAttemptService.finalize_execution(request: StageFinalizeInput) -> StageFinalizeResult` (async, тот же application.artifacts.staging.stageAttemptService). Это отдельная owning операция, не вызов recover из cancel и не изменение ранних Refused/Confirmed в recover. Caller — только явный согласуемый DAG CALL; точный workflow close → finalize_execution → drain/release требует Publication/DAG приёмки. Нынешний blocking cancel сам такой CALL не запускает: интеграция отмены остаётся OPEN, новый вызов внутри adapter запрещён.

Типы в dataModel.artifacts.staging.stageAttempt, strict/frozen/extra-forbid/revalidate_instances=always:
- StageFinalizeInput(binding: StageBinding, generation: positive strict int).
- StageExecutionFinalized(kind='finalized', binding: StageBinding, generation: positive strict int): authoritative drain подтверждён для exact execution; НЕ утверждает успешный stage, сохранность hold или возможность retry.
- StageFinalizeUnresolved(kind='unresolved', binding: StageBinding, generation: positive strict int, code: StageFinalizeUnresolvedCode).
- StageFinalizeUnresolvedCode: STAGE_UNTRACKED, GENERATION_UNTRACKED, EFFECTS_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE.
- StageFinalizeResult: discriminated union StageExecutionFinalized | StageFinalizeUnresolved.

StageBindingRejected применяется к durable mismatch; malformed construction → ValidationError; corruption/unknown/cancellation распространяются без преобразования в Unresolved. Unresolved — подтверждённая недостаточность evidence, а не ошибка запроса к storage. Новый outcome не дублирует Confirmed: он утверждает прекращение effects, а не seal. Новых field paths не нужно: operands логические, existing binding reuse.

Прежний internal IStageAttemptStore.finalize_execution WITHDRAWN для этапа 2: physical алгоритм исполняет ArtifactStageFinalizer(attempts, registry) по RC-CONSTRUCTION; store предоставляет только exact lookup/prohibition/release primitives. Последовательность: integrity/exact binding → registered target/gate → prohibition → evidence → cleanup → durable release. Без process-loss evidence — Unresolved до cleanup/release. Historical completion не даёт early return без residual finalization. Cancel/READY/stale operation fence запрещают data write/successor, но не разрешают менять immutable binding; cleanup только exact execution-owned resources. Operation terminal/fence не меняются. Повтор идемпотентен; absent registration не создаёт stage.

Finalize_execution не выдаёт permit, не переоткрывает lease, не принимает решение о successor и не возвращает ArtifactRef. Recovery incomplete generation использует ТУ ЖЕ внутреннюю реализацию finalizer, не вызывает public finalize_execution; лишь после успешного finalization оценивает partial effects и разрешение successor. Read-only SqliteStageExecutionDrain только читает сохранённый authoritative predicate, никогда не выполняет finalize_execution. Нормальный claim exit и crash finalization обязаны сохранять одинаковый predicate, второго stage owner нет.

### BF-02. Явный runtime claim в backend

Предлагаемый internal sibling port `app.application.artifacts.contracts.authorizedBackend.AuthorizedArtifactBackend[C]`, не замена legacy ArtifactBackend по умолчанию:

    async write(claim: StageWriteClaim, reservation: StagingReservation, content: C) -> None
    async verify(claim: StageWriteClaim, reservation: StagingReservation) -> None
    async cleanup(claim: StageWriteClaim, reservation: StagingReservation) -> None

Все три метода проверяют exact claim issuance/lifetime, binding/generation и reservation. Нельзя восстановить claim по ref, прочитать global context либо самостоятельно acquire полный stage claim. Claim — тот же internal StageWriteClaim, не копия permit и не public DTO. Writer передаёт один handle явно write → verify → seal_stage → cleanup/drain. Cleanup не удаляет опубликованный artifact; только execution-owned временные/частичные ресурсы по concrete backend contract. Completion сохраняется даже при последующем cleanup failure.

StageWriteClaim имеет internal read-only mode: WRITE либо FINALIZE. WRITE выдаётся только confirmed consumption; FINALIZE — owning finalization для той же generation после fencing, без нового permit/generation. FINALIZE не даёт write/verify/seal полномочий, допускает только ограниченный cleanup и завершение работ. Это режим одного runtime capability, не второй lifecycle/token. Worker получает explicit immutable execution coordinates и доступ к backend-owned effect guard, но не live SQL scope/connection родительского task. Concrete guard должен атомарно валидировать координаты с effect; одних скопированных координат недостаточно.

В этапе 2 переиспользуются predicates existing local reservation guard, но управление lifetime принадлежит ArtifactStageWriter через attempts.local_writer по COMP-02/05. Backend-local acquire/release на этом target path запрещены. Guard сохраняет hold/GC predicates; его release не доказывает full drain. Authorized method не вызывает legacy write как fallback. Actual legacy consumers и этап 1 сохраняют backend-owned write участок до отдельного cutover; они не являются restart-safe route. Binding/registry этапа 2 требует explicit authorized port и same authority graph, плюс evidence fencing каждого effect.

Конкретный constructor physical adapter сейчас нельзя указать: нет выбранного production backend. Требуемые входы constructor — existing concrete content contract/storage dependencies плюс проверенный execution authority/effect guard из того же composition; точные классы и signatures предъявляются владельцем выбранного binding до его приёмки. Generic Protocol не считается готовым physical adapter. Этот пункт BF-02 остаётся OPEN в части concrete wiring/call-site cutover, хотя proposed typed передача claim определена.

### BF-03. Транзакционные точки и недостающий concrete input

Условная схема для backend, ВСЕ эффекты которого доказанно находятся в одной serialization области с authority. Это критерий будущего concrete binding, НЕ заявление о существующем SQLite/BLOB/SQL_ROWS:

1. Каждая effect transaction читает и проверяет exact live generation/claim/write admission под конфликтующим authority lock/CAS и меняет ресурс в той же transaction. Commit effect — его linearization. Проверка в предыдущем read scope недостаточна.
2. Fencing transaction конфликтует с каждой такой effect transaction: durable запрещает новые effects old execution. Её confirmed commit — linearization запрета. Принятые раньше transactions должны уже commit/rollback; последующие обязаны отказать. Если хотя бы worker/cleanup effect вне этой области, такого вывода нет и требуется отдельное доказательство.
3. После fencing owning finalization классифицирует committed partial effects, выполняет только разрешённую exact cleanup, затем фиксирует drain. Fencing и drained — разные факты. Для нескольких cleanup commits нужен конкретный идемпотентный resume marker/инвариант existing backend, не произвольный второй журнал. Crash после fence продолжает finalization exact generation, не выдаёт successor и не пытается вернуть old write admission.
4. После confirmed drain recovery повторно проверяет completion и current operation authority. Если completion есть — Confirmed; если closed — Refused без successor; иначе только при доказанной safe partial disposition один atomic transition retire old/register successor. Два recovery одной generation не создают два successor. Finalize_execution останавливается после drain независимо от результата этого решения.
5. Rollback fence оставляет old execution potentially active; rollback cleanup не отменяет прежние partial commits; rollback drain не доказывает release; rollback issuance не разрешает новую generation. Unknown на любой границе сохраняет неопределённость: reread exact durable transition плюс physical evidence перед продолжением. Нельзя компенсировать unknown re-open/unconsume/release или выдать новый номер «на всякий случай». Crash после issuance до ACK использует existing predecessor replay, не вторую issuance.

Конкретный вход, которого НЕ ХВАТАЕТ для BF-03: утверждённая строка production binding `(C, format_key/version, concrete backend class/module, storage resources, writer/worker implementation)` и карта effects с authority storage/lock/isolation, включая reserve/temp/placement/fsync/verify/cleanup. Для неё требуется назвать authoritative representation execution prohibition, конфликтующие transaction statements/locking и committed partial disposition. Existing общая SQLite operation transaction не доказывает fencing чужих physical effects. BLOB и test.rows не назначаются вместо этого входа. Без него нельзя честно указать concrete linearization primitive, constructor или restart progress guarantee; BF-03 остаётся OPEN, durable proof/новый журнал не изобретаются.

Дополнения inventory: StageAttemptService.finalize_execution — thin delegation без successor; StageFinalizeInput/results — correlation/outcomes без IO; ArtifactStageFinalizer — internal algorithm; IStageAttemptStore — SQL authority без physical effects; AuthorizedArtifactBackend — эффекты под explicit claim, не allocator; StageWriteClaim — runtime право, не node DTO. Для каждого нарушение этих ограничений означает отказ. Errors определены в physical пакете и RC-CONSTRUCTION; retain/no deletion policy не ослабляется.

Статусы: BF-01 public/internal предложение предъявлено, Publication cancel workflow и physical finalization остаются на общей сверке; BF-02 typed port предложен, concrete adapter/wiring OPEN; BF-03 concrete binding input отсутствует, automatic recovery не принят. Штатная запись и integration gates остаются раздельными. Основные планы/код этим дополнением не меняются.

2026-11-26. PROPOSED для общей приёмки; не code-go. Единственный изменяемый файл этого поручения. Основание: artifacts-stage-recovery-contract.md, реестр SR-03…05; AGENTS.md и обязательные критерии dag-generator-interface.mdc. Координатор 01a218a4-bfc5-7012-b18b-8ed986cc786d. Код после пользовательского отката не меняется. Этот документ не принимает API, регистрацию или полный домен.

## Приоритетное уточнение границ приёмки — решение пользователя

Три объёма принимаются отдельно; эта запись уточняет общие формулировки OPEN ниже, не меняет контракты и не разрешает код сама по себе.

| Этап | Условия и предел приёмки |
|---|---|
| Внутренняя штатная запись Artifacts | После локальной приёмки IO/Error, authority, полного live claim/drain, atomic seal/evidence и composition допускается независимая реализация. SR-03-BACKEND crash recovery и SR-04-CALLER не являются её blanket blockers. Runtime PASS заранее не выдан |
| Workflow integration | SR-04-CALLER остаётся gate: Engine проверяет existing CALL identity и durable binding до effects. Не блокирует внутреннюю реализацию Artifacts; не разрешает fake authority или потерю correlation внутри Artifacts |
| Automatic recovery после process loss | Отдельный этап SR-03-BACKEND. Нужен доказанный backend quiescence/fencing/drain контракт. До этого consumed incomplete attempt может оставаться Unresolved бессрочно, а holds/claims — удерживаться без ограниченного срока; cancel может не завершить drain. Ни timeout, ни process loss не разрешают retry/release |

Локальная приёмка штатной записи не означает готовность production restart или полного workflow. Известное ограничение отсутствия гарантии завершения восстановления сохраняется явно. По проверке Publication и решению координатора в рамках поручения пользователя «Правим» singleton drain не требуется: разные stateless экземпляры exact owning adapter допустимы при одном access/registry/coordinator и едином scoped predicate; остальные composition требования сохраняются.

## 1. Existing / target и граница

Existing ArtifactStageOpenPipeline.stage принимает ArtifactStageInput[C](lease, prepared); ArtifactStageWriter выполняет reserve/write/verify/seal. IArtifactCatalog.reserve/seal не предоставляют stage generation correlation. Existing OperationLedger.recover возвращает operation observation. Ни один из них не является stage recovery API. Named diagnostic bases уже присутствуют в текущем дереве, но это не evidence production регистрации.

Target A: Artifacts владеет stage binding/generation/admission/completion. Publication владеет operation binding/fence/phase/cancel/terminal. Использование общей transaction infrastructure не разрешает вызовы чужого public service. Новая durable корреляция нужна: existing lease/ref не различают отдельные stage и seal-before-lost-ACK. Физическая схема/новый журнал здесь НЕ назначены; storage-дизайн обязан сначала предъявить reuse existing persistence, либо отдельно обосновать минимальную добавку. Без durable correlation реализация отклоняется, in-memory substitute запрещён.

Прямые callers begin/recover/stage — только согласованный DAG. Каждый public метод исполняет одну owning операцию; begin/recover никогда не запускают stage. Выбор следующего CALL остаётся у DAG. Текущий согласуемый порядок prepare → begin → stage не меняется; восстановление — отдельный recover. Топология, NodeIds и Engine recovery механизм OUT.

## 2. SR-04: identity и persistence

Предложение: ключ stage — (lease.operation_id, stage_id), namespace stage_id локален одной operation, но НЕ одному fence. StageBinding неизменяем целиком, включая fence, world, kind, preparation_fingerprint и полный ArtifactRef. Повтор ключа с другим binding — BINDING_CONFLICT, без перезаписи. Одинаковый ref у разных stage допустим и не объединяет их evidence.

Issuer stage_id — caller логического stage, не stage/recover и не случайный uid при каждом retry. Он обязан выдать EntityUid один раз и durable сохранить вместе с binding ДО первого begin CALL. begin durable регистрирует binding/generation ДО возврата Allowed; эффекты stage до этого невозможны. Artifacts не создаёт новый stage_id при retry. Потерянный ответ begin восстанавливается exact повтором того же binding. Если caller потерял сам stage_id, искать «последний stage по ref» запрещено.

Это точная caller обязанность, но конкретный owning producer и его persistence API пока НЕ предъявлены: внешний gap SR-04-CALLER. Координатор должен сопоставить existing durable call identity с этим требованием либо вернуть отсутствие binding; Artifacts не проектирует Engine и не объявляет issuer реализованным. Генератор/gameplay не назначаются issuer по умолчанию.

### Owning сверка предложения CALL identity — 2026-11-26

Прочитан dag-stage-recovery-transition-resolution.md, секция SR-04-CALLER. Прежняя формулировка «producer не предъявлен» уточняется: Engine предъявил proposal public CallOrigin и parent issuer, но API/проводка ещё не приняты и не реализованы этим документом. Scoped PASS совместимости направления с Artifacts namespace/correlation при следующих точных условиях:

- `dag-stage-call:v1|` + пять length-prefixed компонентов (execution_id, parent_invocation_id, canonical decimal nonnegative parent_step, begin_call_key, begin_target.node_id) является однозначной tuple encoding при фиксированном порядке, длине в Unicode code points и decimal length без leading zeros. Компоненты сохраняются буквально, без Unicode normalization, trim или повторного escaping. Target — именно begin CALL, не stage/recover successor.
- Actual `app.dataModel.identity.uid.EntityUid` — StrictStr с min_length=1 и pattern `^\S(?:.*\S)?$`; max_length не задан. Artifacts не требует UUID, UidKind.STAGE или собственной фиксированной ширины. Полный результат обязан пройти existing EntityUid validation: prefix не делает произвольный component допустимым (в частности, перенос строки внутри может нарушить regex). Невалидный result отвергается до begin, не исправляется hash/alias/обрезанием. Concrete Engine component restrictions и такие negative cases проверяет caller.
- Числовой max length в этой сверке не вводится. Размер равен длине prefix плюс сумме `digits(len(component)) + 1 + len(component)`; storage обязан сохранять exact строку без truncation/case-folding. Stage persistence пока proposal, поэтому compatibility с конкретной будущей колонкой/индексом не объявляется runtime PASS. Если выбранный storage имеет меньший bound, он должен быть предъявлен и согласован до registration, а не скрыт новым allocator.
- Корреляционный ключ Artifacts остаётся `(lease.operation_id, stage_id)`. Operation/world/artifact не обязаны кодироваться в stage_id: authority и связь обеспечиваются immutable полным StageBinding, проверенным existing operation lease и durable exact comparison. Тот же ключ с иными world/kind/fingerprint/fence/ref отвергается как binding conflict; наличие CALL-looking строки не даёт authority. Один stage_id в другой operation попадает в другой namespace; это не replay исходного stage.
- Первый binding сохраняется в begin child/parent continuation до effects, как предлагает Engine; после begin он переносится буквально через stage/recover/successor. Новый CALL address не используется для пересчёта existing stage_id. Replan с новым begin address — новый logical stage, а не продолжение прежнего permit; общее решение о разрешении такого маршрута остаётся у DAG, не у Artifacts.

Итог: namespace и отсутствие собственного max-length совместимы на уровне EntityUid/public proposal; новый allocator не нужен. SR-04-CALLER остаётся integration OPEN до принятия CallOrigin/signatures и доказательства checkpoint-before-effects/exact replay. Этот gap не блокирует внутреннюю штатную запись после её локальной приёмки. Новых Engine API этим owning заключением не принимается.

generation: strict int >=1, относится только к stage. Начальная 1; successor ровно previous+1. Operation fence и Engine attempt не заменяют generation. Для каждой retired generation сохраняется однозначная ссылка на выданного successor; exact recover потерянного ответа не выдаёт ещё одну generation.

## 3. SR-05: POJO, ошибки и публичные signatures

Все новые типы ниже PROPOSED, владелец Artifacts. Модуль `app.dataModel.artifacts.staging.stageAttempt`: strict/frozen/extra-forbid records, positive strict generation, explicit discriminators. Не создаются копии в Publication.

| Тип | Поля / invariant |
|---|---|
| StageBinding | stage_id: EntityUid; lease: OperationLeaseRef; artifact: ArtifactRef |
| StageBeginInput | binding: StageBinding |
| StageRecoveryInput | binding: StageBinding; generation: positive int — восстанавливаемая попытка |
| StageAttemptPermit | binding: StageBinding; generation: positive int; структурный POJO НЕ authority |
| StageAttemptAllowed | kind: Literal['allowed']; permit: StageAttemptPermit |
| StageConfirmed | kind: Literal['confirmed']; binding: StageBinding; completed_generation: positive int |
| StageRecoveryRefused | kind: Literal['refused']; binding: StageBinding; code: StageRecoveryRefusalCode; cancelled: OperationCancelled | None |
| StageRecoveryUnresolved | kind: Literal['unresolved']; binding: StageBinding; code: StageRecoveryUnresolvedCode |
| StageBindingConflict | requested: StageBinding; registered: StageBinding; одинаковый ключ, разные bindings |
| ArtifactStageAdmissionFailure | permit: StageAttemptPermit; code: StageAdmissionCode |

StageAttemptResult = discriminated union Allowed/Confirmed/Refused/Unresolved. Confirmed — исторический seal данной generation, не current hold. cancelled непустой iff code=OPERATION_CANCELLED; operation_id совпадает с binding. StageBindingConflict — отдельная logic issue, не фиктивная ошибка поля.

Enums в том же модуле:
- StageRecoveryRefusalCode: OPERATION_CANCELLED, ADMISSION_CLOSED, STALE_OPERATION_FENCE, STALE_STAGE_ATTEMPT.
- StageRecoveryUnresolvedCode: STAGE_UNTRACKED, ATTEMPT_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE.
- StageAdmissionCode: PERMIT_UNREGISTERED, GENERATION_STALE, GENERATION_ACTIVE, GENERATION_COMPLETED.

Existing ArtifactLeaseFailure используется для stage lease refusal; новые enums не заменяют его и не копируют persisted corruption в business refusal. Recovery refusal — результат решения об операции восстановления, stage admission failure — отказ потребления permit; разделение методов и carriers не позволяет смешать эти значения.

В `app.application.artifacts.staging.stageAttemptService` concrete public StageAttemptService:

    async begin(request: StageBeginInput) -> StageAttemptResult
    async recover(request: StageRecoveryInput) -> StageAttemptResult

Declared expected exception carrier в `app.application.artifacts.staging.stageAttemptErrors`: StageBindingRejected(error: StageBindingConflict). Malformed typed inputs отклоняются Pydantic construction validation; не изобретается JSON endpoint. Infrastructure, UnknownCommitOutcome и CancelledError распространяются, НЕ становятся Unresolved. Unresolved означает успешно установленную недостаточность доказательства.

В `app.dataModel.artifacts.staging.stageInput` предложены ArtifactAuthorizedStageInputBase(permit: StageAttemptPermit, prepared: PreparedArtifactBase) и ArtifactAuthorizedStageInput[C], наследующий base и сужающий prepared до PreparedArtifact[C] с existing instance-preserving validation. Existing generic inputs не изменяются молча.

Target public `ArtifactStageOpenPipeline.stage(request: ArtifactAuthorizedStageInput[C]) -> ArtifactRef`. Единственный окончательный target error roster — таблица ниже. Stage не возвращает Confirmed вместо ArtifactRef.

### Typed diagnostics

Reuse ArtifactInputIssue/ArtifactInputError, FieldPathError, CheckedPath, FieldRef и ValidatorAggregationHelper. Никаких ручных ModelIdentity/segments и mirror lease/ref POJO.

| Нарушение | Root / owners / path |
|---|---|
| Prepare content | existing ArtifactPrepareStageInputBase / content; без изменений |
| Stage content | ArtifactAuthorizedStageInputBase.prepared → PreparedArtifactBase.content |
| Stage format | ArtifactAuthorizedStageInputBase.prepared |
| Descriptor vs encoded content | ArtifactAuthorizedStageInputBase.prepared → PreparedArtifactBase.descriptor |
| permit.binding.artifact vs prepared.descriptor | proposed ArtifactStageBindingIssue: permit + descriptor: ArtifactRef; relation issue, не подмена field path |

ArtifactStageBindingIssue в stageAttempt.py сравнивает два operand одного запроса, а не request против durable registration (StageBindingConflict). Порядок независимой pure проверки: content, format, request binding relation; field issues собираются existing helper. Proposed ArtifactStageInputFailure(fields: ArtifactInputError | None, binding: ArtifactStageBindingIssue | None) требует хотя бы одно непустое поле. Codec descriptor check выполняется только после admission, использует тот же aggregate с fields. Зависимые вычисления после content failure не запускаются. StageInputBindingRejected WITHDRAWN; прямой ArtifactInputRejected на authorized stage WITHDRAWN. Prepare и не мигрированные legacy consumers сохраняют existing carrier.

| Публичная операция | Expected exception carrier / payload (окончательный target) |
|---|---|
| prepare_stage | existing ArtifactInputRejected / ArtifactInputError |
| begin, recover | StageBindingRejected / StageBindingConflict; остальные ожидаемые решения в StageAttemptResult |
| authorized stage: pure input/descriptor | ArtifactStageInputRejected / ArtifactStageInputFailure |
| authorized stage: durable binding | StageBindingRejected / StageBindingConflict |
| authorized stage: permit consumption | ArtifactStageAdmissionRejected / ArtifactStageAdmissionFailure |
| authorized stage: operation lease | existing ArtifactLeaseRefused / ArtifactLeaseFailure |

Новые carriers — stageAttemptErrors; payload — stageAttempt.py, кроме existing ArtifactInputError/ArtifactLeaseFailure. Для всех методов infrastructure/codec/storage corruption, UnknownCommitOutcome и CancelledError сохраняют категории/cause; это не expected result enum. Malformed construction input остаётся Pydantic ValidationError. Эта таблица отменяет промежуточные комбинации carriers, а не existing API вне миграции.

Schema bases и все referenced owners включаются в конкретный cold allowlist; IDs не назначаются этим документом. Python/JSON/canonical full Error round-trip должен сохранить root/owners/order. Новый root требует отдельного Fields/C0 согласования, старый scoped verdict не переносится автоматически.

Уточнение по artifacts-stage-recovery-fields-review.md: получен scoped PASS TARGET цепочкам roots и разделению field/relation, не full SR-05. Authorized base — sibling, НЕ наследник lease-содержащего ArtifactStageInputBase. Все новые logic DTO/aggregate и вложенные StageAttemptPermit/StageBinding: ConfigDict(strict=True, frozen=True, extra='forbid', revalidate_instances='always'). ArtifactStageBindingIssue допускается только при permit.binding.artifact != descriptor; равные operands отклоняются validator. StageBindingConflict требует одинакового ключа и неравных полных bindings. Aggregate требует хотя бы один непустой компонент; relation не дублируется field issue.

Admission сначала собирает content → format через ValidatorAggregationHelper с exact allowed issue classes, затем берёт snapshot(), проверяет доступную relation и только после этого поднимает один ArtifactStageInputRejected. Преждевременный raise_if_any запрещён. Invalid content не отменяет независимые format/relation, если descriptor/permit доступны и типизированы. Если malformed operand отсутствует/невалиден, зависимая проверка пропускается без выдуманных operands; доступные structural/field diagnostics сохраняются. Codec запускается только после успешного pure admission; его exception не превращается в mismatch. Требования Fields к forged model_copy negatives, full Python/JSON/canonical closure и identity остаются gates реализации, не runtime PASS.

## 4. SR-03: exact internal port proposal

`app.application.artifacts.storage.stageAttemptStore.IStageAttemptStore`:

    async begin(request: StageBeginInput) -> StageAttemptResult
    async recover(request: StageRecoveryInput) -> StageAttemptResult
    claim_stage(permit: StageAttemptPermit) -> AbstractAsyncContextManager[StageWriteClaim]
    async seal_stage(claim: StageWriteClaim, reservation: StagingReservation) -> ArtifactRef

begin/recover имеют тот же error contract что service; claim_stage — StageBindingRejected, ArtifactStageAdmissionRejected, ArtifactLeaseRefused плюс infrastructure/unknown/cancellation; seal_stage — те же категории, reservation/claim inconsistency является ArtifactStorageInvariantError. Storage port не public DAG API, service не вызывает другие public методы.

StageWriteClaim в том же internal модуле: read-only permit: StageAttemptPermit; context lifetime; concrete adapter владеет закрытым runtime ownership handle. Пользовательские scope/connection/claim не передаются через DAG и не создаются caller. Quiescence не представляется переносимым bool/proof DTO. recover обязан доказать её и атомарно исключить старые эффекты в рамках одной owning операции; публичный check_quiescence с последующим TOCTOU запрещён.

Full execution claim приобретается до reserve и охватывает write/verify/seal и drain workers. Физическое IO вне длинной SQL transaction. Выход по ошибке освобождает runtime claim только после drain, но НЕ восстанавливает consumed permit автоматически. Process loss не считается drain. Повторное использование consumed permit всегда отказ; решение о successor принимает recover.

seal_stage обязан атомарно проверить operation fence/admission, exact claim/generation/reservation, закрепить seal/hold и completion evidence. Commit confirmed → ref; rollback → нет completion этого commit, предшествующие physical effects возможны; unknown → UnknownCommitOutcome без компенсации/новой generation. Durable completion читается раньше текущего закрытия lease для exact replay Confirmed, но после проверки integrity и exact binding. Concurrent cancel после completion не меняет исторический результат.

## 5. Таблица begin/recover и гонок

Таблица применяется СТРОГО после следующих приоритетных проверок в coherent observation/transaction, а не сверху вниз независимо:
1. Persisted integrity всей доступной operation/stage/chain/evidence; corruption/orphans → fault. Затем exact immutable binding; конфликт → StageBindingRejected.
2. Historical completion: begin возвращает Confirmed; recover возвращает Confirmed только для completed generation или её доказанной predecessor chain. Произвольная future g не получает Confirmed. Cancel/READY/current fence не отменяют этот исторический исход. Retired/tombstone ветви в текущем контракте отсутствуют: deletion запрещён.
3. Если исторический исход запрос не разрешил: current operation authority. При stale operation fence → STALE_OPERATION_FENCE; при matching fence и cancel terminal → OPERATION_CANCELLED; затем READY/closed/другой terminal → ADMISSION_CLOSED. Отсутствующая operation при сохранённом stage — integrity fault, не разрешение повторного begin.
4. Только при current writable authority проверить generation membership/current/successor/consumption и применять строки Allowed/Unresolved ниже. Поэтому unconsumed permit НЕ получает Allowed после cancel/READY. Для отсутствующего stage recover → STAGE_UNTRACKED только после успешной authority проверки; отсутствие operation при отсутствии stage отображается в STAGE_UNTRACKED без регистрации, не в Allowed.
5. Выдача initial/successor и consumption linearize с operation close в общей write transaction; после возврата Allowed consumption повторяет authority проверку. Recovery старой g, successor которой consumed, возвращает ATTEMPT_NOT_QUIESCENT (либо INSUFFICIENT_EVIDENCE при доказанном drain), но НЕ новую generation. Для восстановления successor нужен explicit recover(successor.g).

| Состояние | begin(binding) | recover(binding, g) |
|---|---|---|
| Нет stage registration, operation writable | Durable register g=1 → Allowed | Unresolved(STAGE_UNTRACKED), не создаёт stage |
| Permit текущей g выдан, не consumed | Тот же Allowed | Для g тот же Allowed; не bump |
| g consumed, live writer или quiescence не доказана | Unresolved(ATTEMPT_NOT_QUIESCENT) | То же, без successor |
| g consumed, quiescent, partial effects безопасны, operation writable | Unresolved(INSUFFICIENT_EVIDENCE): begin не делает recovery | Atomic retire g/register g+1 → Allowed |
| g consumed, safety partial effects не доказана | Unresolved(INSUFFICIENT_EVIDENCE) | То же, без retry |
| Completion существует | Confirmed exact completed_generation | Confirmed, если g относится к завершённой попытке либо её записанной predecessor chain |
| Уже выдан successor g+1 после recover(g) | Allowed только если current permit ещё unconsumed; иначе unresolved/confirmed | Exact повтор recover(g) возвращает того же successor, если unconsumed; consumed → unresolved; completed → Confirmed; не выдаёт g+2 |
| g неизвестна, future либо не относится к durable chain | begin рассматривает current registration | Refused(STALE_STAGE_ATTEMPT), без effects |
| Operation cancel terminal, completion отсутствует | Refused(OPERATION_CANCELLED), reuse terminal | То же |
| READY/closed, completion отсутствует | Refused(ADMISSION_CLOSED) | То же |
| Lease fence устарел, completion отсутствует | Refused(STALE_OPERATION_FENCE) | То же |

Два одновременных begin linearize в один g=1. Два recover(g) linearize в один successor. Lost ACK begin/recover повторяет тот же request, не bump. Unknown commit сначала разрешается чтением authoritative durable state внутри owning операции; наличие Unresolved не скрывает exception незавершённого read/commit. Lost ACK seal разрешается только completion evidence. Если successor уже consumed, повтор старого recover не является новым recovery successor: нужен запрос с generation successor. Это обеспечивает bounded idempotency без implicit retry.

Условный Allowed может устареть из-за cancel/READY: claim_stage повторно атомарно проверяет authority до effects. Если cancel опередил claim — refusal; если claim опередил cancel — drain охватывает ВСЕ effects. Точки ordering принимаются для сверки из Publication resolution, раздел «Порядок и совместимость lifecycle»: close admission до ожидания; оба drain predicates до release/terminal; READY проверяет full drain внутри commit без ожидания под SQL lock. Это согласование proposal, не runtime PASS.

## 6. Классы, зависимости, эффекты, критерии отказа

| Класс / модуль | Роль и зависимости; effects | Проверка / отказ |
|---|---|---|
| Все новые records/enums §3, dataModel.artifacts.staging.stageAttempt | Только operands/results/invariants; existing lease/ref/cancel | Никакого IO или lifecycle transition; reject inconsistent discriminator/binding/generation |
| Authorized input/base, dataModel.artifacts.staging.stageInput | Typed immutable input; PreparedArtifact/permit | Полная validation и same-instance; reject silent coercion или mandatory wrapper для старого API |
| Existing PreparedArtifact/Base, preparedArtifact.py | Content/descriptor; unchanged | Нельзя клонировать transport payload или переносить authority в descriptor |
| Existing ArtifactInputIssue/Error, inputErrors.py; Fields CheckedPath/FieldRef | Field diagnostics/path building | Reject ручные owners, новые mirrors, path внутри произвольного C |
| New logic issues/aggregate §3 | Relation operands плюс reuse field diagnostics | Reject потеря независимых issues или ложный field owner |
| Carriers stageAttemptErrors; existing stageErrors/lease refusal | Перенос owning errors, без logging/retry | Reject изменение исхода, duplicate logging |
| StageAttemptService, application.artifacts.staging.stageAttemptService | Этап 1 по прежнему контракту; этап 2: begin/inventory → store, recover → ArtifactStageRecovery, finalize_execution → ArtifactStageFinalizer, exact returned POJO | Нет stage вызова/маршрутизации/чужого public service; store не получает physical callbacks |
| ArtifactInputAdmission, staging.artifactInputAdmission | Pure content/format/request-relation admission | Reject IO; collect stable independent errors до effects |
| ArtifactDescriptorBuilder, staging.artifactDescriptor | Existing encode/descriptor check; registry | Новый authorized schema-root передаётся через owning diagnostic binding, не DAG; reject hardcoded old root |
| ArtifactStageOpenPipeline, staging.artifactOpenPipeline | Admission → descriptor check → writer | Не выбирает recovery branch и не вызывает begin |
| ArtifactStageWriter, staging.artifactStageWriter | IStageAttemptStore, catalog, registry/backend, existing log; full claim IO | Reject standalone seal followed by evidence; post-seal fault не означает rollback |
| IStageAttemptStore / StageWriteClaim, storage.stageAttemptStore | Узкая durable authority boundary §4 | Не expose в public DTO; no fake authority/обход consumed generation |
| SqliteStageAttemptStore, db.repositories.sqlite.artifacts.stageAttemptStore | Concrete owner; scopes/operations/catalog и required stage_drain | Constructor graph §8; несогласованный graph отклоняется до IO; store не является общим drain adapter |
| SqliteStageExecutionDrain, db.repositories.sqlite.artifacts.stageExecutionDrain | Read-only authoritative predicate через ScopedSqliteAccess; implements IStageExecutionDrain | Нет зависимости от operations/leases/stage store и нет второй policy; unknown не превращается в drained |
| Existing IArtifactCatalog/SqliteArtifactCatalog | Reserve и scoped seal implementation reuse | Без второго seal commit; existing standalone API не притворяется scoped |
| Existing IArtifactWriteAdmission/SqliteArtifactLeases | Operation lease admission + drain | Не дублирует stage generation; cancel/READY обязаны видеть full claims |
| Existing ArtifactFormatRegistryBinding / ArtifactBackend | Codec, physical write/verify | Не выдаёт permit; worker drain до release, live scope не переносится workers |
| Existing ArtifactLifecycleLog | Post-outcome event | Не превращает successful seal в false rollback/unknown |
| Existing Publication operation/transaction adapters | Единственный operation lifecycle/transaction owner | Не вызывают Artifacts public service, не вводят параллельный terminal |

Роль каждого existing concrete backend должна быть проверена для выбранного binding; binding не выбирается BLOB-first. Таблица не выдаёт full architecture PASS при OPEN exact composition.

## 7. Consumer migration и приёмка

Сначала принять IO/Error/authority и schema roots; затем реализации/тесты; затем согласованный consumer cutover. Новый route использует только required permit+prepared, без overload lease-only fallback. Existing ArtifactStageInput и legacy стейджеры не удаляются до inventory callers; они не допускаются к новому recovery маршруту. DAG wrappers должны переносить новые owning failures целиком. Pack manifest callers и legacy TypedArtifactStager — отдельный cutover, не скрытый вызов begin внутри них. DescriptorBuilder.check needs authorized-root binding для нового caller; существующие callers сохраняют старую diagnostic семантику до своего явного перехода. Concrete перечень callers и node mapping предъявляет координатор; отсутствие перечня блокирует full migration, не закрывается этим документом.

Тесты: duplicate/concurrent begin/recover; lost ACK каждого commit; future/stale/conflicting bindings; второй consumer permit; old generation после successor; workers+cancel/READY; crash до/после reserve/write/seal; unknown без компенсации; completion after cancellation возвращает historical Confirmed; independent field+relation errors; каждый root/segment owner; Python/JSON/cold allowlist; bytes и concrete SQL_ROWS identity. Fake authority fixtures недопустимы для positive storage tests.

CRUD disposition текущего среза: begin создаёт immutable binding/authority; recover читает и условно обновляет generation; stage записывает artifact. Retention = retain, no deletion API. Artifacts сохраняет binding, predecessor chain, acquisition/release uncertainty и completion после claim release, cancel, READY, terminal и physical artifact GC. Удалять эти facts сейчас не вправе никто; TTL не вводится. Missing обязательные persisted facts — integrity fault, а не основание заново создать g=1. STAGE_UNTRACKED применим только к действительно не зарегистрированному stage. Publication сохраняет operation history по своей append-only границе. Это завершённая target disposition retention, не ожидание будущего retire API. Настройки новые не вводятся; полная CRUD-приёмка домена не заявляется.

Deferred future proposal, OUT текущего API: возможные tombstones, STAGE_RETIRED/PERMIT_RETIRED и retire acknowledgement обсуждаются только если пользователь отдельно потребует удаление. Эти enums НЕ добавляются в §3, ветви НЕ входят в §5, future acknowledgement не блокирует retain-контракт. Будущее удаление потребует cross-owner решения об исключении всех поддерживаемых replay, authority/unknown и operation history; конкретный механизм здесь не назначается.

## 8. SR-03: owning quiescence и сверка предъявленного Publication package

Сверена latest секция «Construction без dependency cycle» в artifacts-stage-recovery-publication-resolution.md. Совместимый TARGET: `SqliteStageExecutionDrain(access: ScopedSqliteAccess)` в db/repositories/sqlite/artifacts/stageExecutionDrain.py — единственный concrete IStageExecutionDrain. Required keyword `stage_drain: IStageExecutionDrain` получают SqliteOperationStore[R], SqliteArtifactLeases[R], SqliteArtifactHolders и `SqliteStageAttemptStore[R](scopes: SqliteArtifactScope, operations: SqliteOperationStore[R], catalog: SqliteArtifactCatalog, *, stage_drain: IStageExecutionDrain)`. Store-as-drain WITHDRAWN. Каждый exact SqliteStageExecutionDrain использует тот же access, что consumer; no-op/default запрещены. Один экземпляр допустим, но object identity между drain adapters не требуется: wrapper stateless, без cache/locks/claims/epoch/hot-rebind и собственной policy. Assembly: scopes/access → drain → operations/catalog → stage store → leases/holders → backend/writer. Сохраняются все Publication same-graph checks до IO и scoped recheck внутри transition transaction. Drain не зависит от stage store/operations/leases и не имеет отдельной state machine; authoritative predicate принадлежит Artifacts, durable representation пока OPEN.

`async SqliteArtifactCatalog.seal_in_scope(scope: CommitScope, reservation: StagingReservation) -> ArtifactRef` остаётся provisional, без собственного commit. seal_stage фиксирует completion в том же scopes.commits.transaction(operation_id), без отдельного evidence service. Concrete composition migration sites принимаются из Publication: PacksWiring.initialize_pack_storage, live_database, artifactFixtures.adapters, typing sqlite_composition и direct test constructors; fake drain True недопустим. Наличие такого перечня не означает runtime соответствия или регистрацию authorized stage.

Protocol `IStageExecutionDrain` объявляется в storage.stageAttemptStore, concrete реализация — отдельный SqliteStageExecutionDrain: `async is_drained(scope: CommitReadScope, operation_id: EntityUid) -> bool`, `async assert_drained(scope: CommitScope, operation_id: EntityUid) -> None`. Scoped authority/task/operation проверяются; no wait/commit внутри. True разрешён только когда каждая acquisition определённо не создала claim либо каждый созданный claim подтверждённо закончил все workers/effects и release. Подтверждённый live execution → False / OperationBusyError. Неразрешённый acquisition/release outcome либо corruption → соответствующий infrastructure/unknown fault, НЕ False/True. Generation fence запрещает будущий SQL admission, но не останавливает уже исполняющийся physical worker.

Proof owner — Artifacts, не Publication. Для штатного выполнения proof составляют: registered exact claim; запрет новых work submissions после начала drain; завершение всех уже submitted workers (включая executor future, rename/fsync и backend cleanup); отсутствие отложенного effect; confirmed release в authority store. Release нельзя подтвердить до worker join. Проверки generation выполняются перед каждым новым эффектом, но не заменяют join уже начатых эффектов.

Cancellation acquisition: до подтверждённого commit handle не выдаётся и workers не запускаются. Подтверждённый rollback означает отсутствие acquisition; потерянный ACK/unknown разрешается exact authoritative claim lookup. До разрешения новый claim/successor не выдаётся. Если acquisition committed, но callback не получил handle, отсутствие worker допускается доказать лишь если протокол handoff однозначно исключает выдачу handle и будущий запуск; одной пустой локальной таблицы tasks недостаточно. Cancellation после выдачи handle запускает owning drain, а не автоматический unconsume. Неизвестный release запрещает вывод quiescence; после authoritative reread требуется также сохранённое доказательство завершения workers, а не только отсутствие claim row.

Точная missing backend capability: existing `ArtifactBackend.write(reservation, content)`/verify/delete и write_admission не имеют контракта установления после restart, что ВСЕ effects конкретной execution identity завершены/не могут продолжиться. Existing BLOB shield/join обеспечивает local cancellation drain, не durable restart proof; concrete SQL_ROWS binding должен отдельно предъявить такую возможность. Нельзя обещать generic fencing physical IO только из operation/generation fence. Пока concrete backend не предъявил mechanism, consumed non-completed generation после потери process → Unresolved(ATTEMPT_NOT_QUIESCENT); successor не создаётся. Cancel также не завершает hold release по timeout. Подтверждённый completion может дать historical Confirmed, но lifecycle drain всё ещё должен доказать завершение оставшегося worker/cleanup.

Минимальная необходимая дельта перед automatic retry после crash — backend-specific контракт durable execution identity и способ исключить/дождаться всех старых physical effects, связанный с StageWriteClaim, включая cancellation acquisition/unknown release. Exact метод/representation нельзя честно назначить generic port без выбранного backend и его capabilities. Это локальный SR-03-BACKEND gap Artifacts, не запрос Publication доказать physical quiescence. Ни новый журнал, ни SQL, ни BLOB binding автоматически не назначены. До закрытия gap safe crash retry не принимается; штатный live drain отдельно проверяем.

Publication предъявил drain/scoped-seal constructor graph, transition inventory и retain/no deletion policy; они сверены как совместимое proposal. Остаётся общая приёмка их полного consumer cutover, а не повторный запрос отсутствующего пакета. Physical quiescence и stage persistence остаются Artifacts; foreign public service calls запрещены.

SR-03: latest Publication drain/constructor ports сверены; Artifacts crash-proof backend capability/persistence и общий cutover OPEN, safe crash retry не принят. SR-04: retain/no deletion target определён; concrete caller issuer/persistence OPEN, future retire acknowledgement OUT и не gate. SR-05: Fields/C0 scoped PASS TARGET roots учтён, invariants/aggregation уточнены; runtime/typing/cold closure и общий consumer cutover OPEN. Ни один SR не CLOSED по факту документа. Недостающие сведения исключают общую приёмку до сверки координатора и решения пользователя.
