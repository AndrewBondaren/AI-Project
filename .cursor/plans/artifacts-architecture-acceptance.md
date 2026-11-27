# Artifacts: архитектурный пакет на приёмку

2026-11-28. PLAN-ONLY. Этот документ — входная карта актуального пакета, а не разрешение реализации. Согласованные семейство, девять нод, WorkflowNode/Node и каталоги сохраняются. Источники деталей: artifacts-stage-recovery-complete-chain.md, artifacts-dag-orchestration-contracts.md, artifacts-stage-persistence-contract.md. Исторические редакции не являются альтернативными механизмами.

## 1. Решения и порядок

| Граница | Актуальное решение | Единственный владелец |
|---|---|---|
| Подготовка и запись | PrepareAndStageArtifactWorkflowNode → prepare → StageRecoveryWorkflowNode | DAG |
| Один stage | begin → stage; unknown → recover; новый stage только после Allowed | DAG выбирает CALL; Artifacts выдаёт решение |
| Отмена operation | Publication close → Artifacts inventory/finalize workflow → Publication final cancel | Внешний DAG; terminal/holds только Publication |
| Persistent stage facts | Binding/generation/acquisition/link/prohibition/completion/release, scoped UOW и exact replay | SqliteStageAttemptStore |
| Физические эффекты | Host job владеет worker futures и guard; adapter не получает право самостоятельно release | Artifacts physical host |
| Потеря host | Same-boot restart запрещён latch; после полного reboot — reconciliation, не повтор WRITE | Предложенная Windows composition; требует решения пользователя |
| Outcome/checkpoint | Один invocation graph и codec; typed bindings, без domain branches | Engine |
| Failure transport | Один neutral envelope/codec, Artifacts owning payload, Engine correlation отдельно | Общий transport + owning payload Artifacts |

Приоритет деталей: основной план §15 заменяет старые Engine-specific error codec и domain terminal checks; §§10.1–10.2 заменяют ранний session-owned gate; §§12.2–12.4 задают concrete wrappers и wire ExpectedCall. Уточнения §§2–3 ниже закрывают оставшиеся стыки двух новых workflows. Не вводить прежние варианты как compatibility fallback.

## 2. Результат вложенного workflow: точный generic mapping

PrepareAndStageOutput содержит только route_source, primary StageRouteResult остаётся terminal ребёнка. Нельзя возвращать скопированный RouteSuspended и применять к нему правила проверки direct failed child верхнего parent.

Статическая registration PrepareAndStageArtifactWorkflowNode объявляет output slot route с target StageRecoveryWorkflowNode и допустимым CALL key stage-route. PrepareAndStageTerminalBinding.project(output) возвращает DependencyReference(slot=route,source=route_source). InvocationCoordinator.finish допускает источник только если он SUCCEEDED, exact returned child этой invocation, совпадают key/target/version/attempt и объявленный output slot. В одной checkpoint CAS создаёт edge, retention marker и terminal. Если slot существовал, source обязан совпасть; менять edge нельзя. Это расширяет прежнее правило «только existing edge» одним явно зарегистрированным returned-CALL случаем, не произвольной ссылкой.

Получатель внешнего результата использует declared dependency mapping: source target — PrepareAndStageArtifactWorkflowNode, inherited_slots=(route,), same_execution=True; caller обязан законно видеть terminal верхнего parent. Engine переносит source из authoritative edge, а не из непроверенного DTO. Pure typed input binding помещает StageRouteResult в именованный input consumer, без lookup внутри start. Конкретный production consumer вне scope, но его registration обязана объявить этот slot и output type. Без такого mapping вызов consumer отвергается. Сохранение edge не означает разрешения всем callers читать его source.

Responsibilities: terminal binding только проектирует ссылки; coordinator проверяет graph и атомарно сохраняет; codec восстанавливает closure; consumer выбирает действие по typed result. Дополнительные resolver, mutable result cache, domain-specific Engine branches и error journal запрещены. Acceptance: success/refusal/suspension child → outer terminal → cold restore → законный consumer; foreign source и иной child key отклоняются; suspended source сохраняет исходные prepared/error dependencies.

## 3. Batch continuation: без нового reference-codec

Для finalization inventory НЕ требуется Python object identity. Нормативная форма WaitExecution: request, batch: OperationStageFinalizationBatch, inventory_source, next_index, expected. Batch в continuation — immutable snapshot операндов текущего обхода; сериализуется обычным concrete state codec. Это не новый storage authority и не второй реестр executions: каждый finalize сам проверяет exact binding/generation и состояние, Publication повторно проверяет всю operation.

На первом переходе inventory → WaitExecution parent сохраняет tuple ровно как выдал domain. На restore node-specific state validation сверяет batch по полному значению с удержанным exact inventory terminal, request и next_index; не заменяет результат свежим запросом и не сортирует. Требование is остаётся только для prepared transport, на inventory не переносится. Реализация проверки — статический typed continuation binding с pure validate(state, admitted_dependency_output), зарегистрированный на slot inventory; Engine передаёт только разрешённый exact producer и не знает поля batch. Если такого generic validation hook ещё нет, оформить его как ограниченную pure state-validation дельту рядом с ContinuationContract, без нового способа encode/decode и без IO. До implementation предъявить его сигнатуру в Engine-контракте; это остаётся конкретным пунктом архитектурной проверки, не разрешением скрытого callback.

Slot inventory объявлен для returned inventory CALL. Retention этого producer действует пока continuation/terminal содержит inventory_source; completed output означает завершение данного набора, не drain proof. Ошибка/mismatch даёт RestoreFailure до finalize; никакого repair. Sequential order, остановка на первом неуспехе, fresh inventory только при новом explicit запуске сохраняются.

## 4. Классы, границы и проверки

| Классы | Допустимая ответственность | Основание отказа |
|---|---|---|
| Девять DAG node classes | Три workflow с CALL, шесть leaves с одним public method | SQL/host imports; прямой domain call из workflow; два public calls в leaf |
| StageAttemptService / public OpenPipeline | Validation и передача одному owning job | Междоменная оркестрация, selection следующего DAG CALL |
| Stage writer/recovery/finalizer | Owning sequence одной операции, exact authority/evidence | Самостоятельная issuance вне store, retry без owning решения |
| Host dispatcher/session/jobs | Один owner accepted tasks; dedup, close/join, exact physical effects | TTL/timeout как proof, detached cleanup, повтор WRITE после failure |
| StageAttemptStore/catalog scoped primitives | Один writer facts, atomic seal+C и local release+X | Physical IO, nested independent commit, X без evidence |
| Publication lifecycle adapters | Final all-fence local/full recheck и terminal | Освобождение holds по portable batch/Finalized |
| Registry/physical adapter/encoder | Один registered contract, общие physical primitives, pure encode | Второй backend registry, повтор local acquire, local fallback |
| Engine coordinator/codec | Generic graph references, checkpoint/CAS/outcomes | Импорты Artifacts DTO, выбор domain recovery policy |

## 5. Граница legacy и поставки

Existing packs.py / TypedArtifactStager / preparedManifest сохраняют legacy composition и не объявляются HOST_BOOT_V1. Новый authorized writer не получает backend/catalog write ports; при недоступном host возвращает ошибку, не пишет локально. Stage capability регистрируется на том же backend instance, но доступна только host jobs. Для перенесённого caller старый route/factory удаляется после появления принятой замены, не остаётся параллельным fallback.

Production caller/cutover карта требует выбранного production binding и потому не может считаться выполненной сейчас. Она не prerequisite исследования общего BLOB механизма и не повод выбирать Manifest/Climate по удобству. Архитектурная приёмка общего механизма и production activation — отдельные решения. Tests/support binding не выдаётся за production маршрут.

## 6. Остаток на приёмку

1. Пользовательское решение о Windows service/latch и обязательном full reboot даже после clean stop. Не принимать это молча из разрешения править планы.
2. Для пункта §3 предъявляется конкретная дельта: `ContinuationDependencyBinding[S: BaseModel,O: BaseModel]` в `application/engine/contracts/invocation/continuationDependencyBinding.py`, immutable binding_id/version/state_type/source_target/slot и pure `validate(state: S, source: O) -> None`. `ContinuationContract` получает tuple таких bindings с пустым default для existing nodes; ids/versions входят в fingerprint. Coordinator при accept и codec при restore после разрешения declared edges вызывают validation до dispatch. Node-local `FinalizationInventoryStateBinding` проверяет exact batch/request/index, без IO и изменения state. Live mismatch — contract failure, restore mismatch — RestoreFailure. Других способов записи/чтения state не вводится. Сигнатура определена, требуется приёмка этой proposed дельты вместе с п.3.
3. Совместная проверка returned-output dependency mapping (§2) с terminal references основного плана; это proposed API, не existing capability.
4. Concrete test registration C/errors/versions для проверки всех маршрутов; production IDs не назначаются. Production cutover отдельно после выбора binding.

Не считать эти пункты закрытыми лишь по наличию документа. Архитектура resources/authority и порядок описаны; весь пакет ещё не code-go. Следующая проверка должна оценить названные API и failure model, а не добавлять новые домены или начинать ноды в обход приёмки.
