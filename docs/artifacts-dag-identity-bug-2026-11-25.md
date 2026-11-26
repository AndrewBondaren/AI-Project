# BUG-ARTIFACTS-DAG-IDENTITY — потеря identity на кандидатных маршрутах prepare/stage

## Решение пользователя: откат Engine — 2026-11-26

Пользователь оставил owning исправления Artifacts (identity admission и P2 diagnostic paths), но отклонил изменения Engine: вне плана, с нарушением ответственности классов и без его согласования. Получена явная команда откатить Engine. Ранее записанный scoped PASS отражает только результаты тестов и НЕ является пользовательской приёмкой или разрешением этих изменений.

Адресный откат завершён: удалены введённые для этого бага identity_required/live transport и связанные изменения lifecycle; отдельный test_live_identity.py удалён. Координатор независимо сравнил восемь файлов Engine с baseline dfe665088b56f30986c84e795b1938a721b15db0 через git diff --exit-code — exit 0, различий нет. Поиск identity_required/live_coordinator/clear_live/_coordinator_out пуст. Исполнитель прогнал existing test_world_calls — 29 PASS за 43.550s; координатор независимо прогнал оставленные Artifacts test_content_identity + test_registry — 23 PASS за 2.384s. Owning Artifacts/P2 исправления сохранены. Статус отката — DONE.

Несовместимость требования object identity с прежним JSON транспортом остаётся открытым контрактным вопросом; нового Engine решения в рамках этой задачи не вводится. Исторические записи о реализации и техническом PASS Engine ниже не описывают текущий код: эта реализация откачена по решению пользователя.

## Итог независимой scoped приёмки Engine transport — 2026-11-26

**SCOPED PASS** для реализованного opt-in live transport и проверенного test-only registered маршрута через публичный `DAGEngine.run`. После последнего исправления координатор независимо выполнил `tests.dag_typing.invocations.test_live_identity` — **1 PASS, 0.442s**, затем `tests.dag_typing.invocations.test_world_calls` — **29 PASS, 46.324s**. Прогоны вне sandbox на проектной среде; это не static или pinned-version evidence.

Закрыты последние замечания: при ошибке load после claim ExecutionState освобождается ровно один раз; public cancellation и forced renew OwnershipConflict завершают worker без возврата Stage в Route и без effects, claim освобождается, unfinished resume не запускает ноды. Actual cleanup выполняет clear_live перед release. Forced renew failure проверяет реакцию на отказ владения, не моделирует все возможные конкурентные storage interleavings. Fresh public run сохраняет content/prepared identity; terminal replay без повторных CALL, policy mismatch, unfinished restore и replan refusal проверены.

Прежние OPEN по fresh entry, cleanup и отсутствию public cancellation/owner-loss regressions ниже заменены этим вердиктом. Owning Artifacts identity и P2 diagnostic scoped PASS сохраняются. Полная production регистрация конкретной пары Artifacts и её binding этим synthetic transport тестом не принимаются; это отдельный остающийся интеграционный объём, а не незакрытые замечания к проверенному Engine исправлению.

## Актуальная независимая проверка публичного engine-входа — 2026-11-26

После свежей lifecycle-дельты координатор независимо запустил `tests.dag_typing.invocations.test_live_identity`: **1 PASS, 0.073s**. Проверены public `DAGEngine.run` с сохранением content/prepared identity, terminal resume без новых CALL, policy mismatch, отказ восстановленного незавершённого маршрута и отказ replan до второго прохода. Прежний дефект fresh entry исправлен; отсутствие этих проверок больше не является текущим blocker.

Остаток приёмки этой дельты: public lifecycle cancellation и renew/owner-loss при активном child, drain до release, очистка live payload и отсутствие следующего CALL/effects. Владельцу Engine передана также конкретная cleanup-проверка: исключение `store.load` после успешного claim и до запуска worker должно освобождать ExecutionState; текущий явный release находится только в mismatch-ветке. После исправлений требуется повторная регрессия ordinary CALL/replay. Это проверки изменённого Engine transport, не требования к внутреннему Artifacts storage или production specialization.

Полный engine verdict пока OPEN; owning identity и P2 diagnostic scoped PASS сохраняются. Production Artifacts binding данным тестом не принимается. Нижележащие записи об отсутствии public workflow/replan evidence исторические и заменены этим статусом.

## Исторический residual публичного engine-входа — 2026-11-26

Исполнитель выявил: ExecutionAdmission.run создаёт durable InvocationGraph до PassExecution и вызывает recovery.resume. Для identity_required свежий запуск далее выглядит как restored unfinished graph и отклоняется до нод. Поэтому PASS direct registered DAGExecutor.run_invocation НЕ означает поддержку DAGEngine.run(identity_required=True). Публичная fresh workflow activation пока НЕ ПРИНЯТА; это конкретный integration defect, не только отсутствие теста публикации.

Поручено довести explicit fresh live context handoff через existing create/claim/ownership checks без пропуска checkpoint, без ослабления restored unfinished refusal и без изменения ordinary replay. Проверки должны идти через публичный DAGEngine.run; private workflow публикация отдельно не доказывает работоспособность этого входа. Identity-specific replan coverage остаётся OPEN. Прежние 30 PASS сохраняются только в своём direct/ordinary replay объёме.

## Независимое ревью live engine реализации — 2026-11-26

Повторный независимый прогон ПОСЛЕ ownership/error/stale-key исправлений: `.venv/Scripts/python.exe -B -m unittest tests.dag_typing.invocations.test_live_identity tests.dag_typing.invocations.test_world_calls` вне sandbox — **30 PASS за 110.166s**. Включает расширенный identity fixture (typed error/cancel/runtime failure/retry/private handoff) и 29 ordinary CALL/replay regressions. Это актуальное evidence вместо прежнего 29-test прогона до исправлений. Actual workflow publication under claim и identity-specific replan coverage остаются отдельным OPEN.

`tests.dag_typing.invocations.test_live_identity` независимо запущен вне sandbox: **1 PASS (0.015s)**. Sandbox watchdog 18s с faulthandler показал зависание в Windows socket._fallback_socketpair/accept при создании asyncio loop ДО setUp/test body; это ограничение запуска, не доказательство дефекта DAG. Owning/P2 scoped PASS не переоткрыты.

Исторические code findings исправлены и повторно просмотрены: claim передаётся workflow и удерживается до публикации; clear_live выполняется перед release; workflow typed-error ветка использует live payload; _refresh проверяет предыдущие attempt/revision/step. Эти замечания больше не обозначаются текущими дефектами. Расширенный registered test предъявляет typed error/cancellation/runtime failure без downstream CALL, typed-error retry с сохранением identity и private claim handoff/clear probe. Остаток независимой engine приёмки: actual workflow publication под claim и identity-specific replan test; private handoff сам по себе не покрывает workflow. Полная приёмка остаётся OPEN до этого evidence.

## Engine transport implementation evidence — 2026-11-26

Status: **OPEN** pending independent acceptance of the fresh public workflow and production Artifacts registration. DAG coordinator gave scoped PASS to the proposed transport contract; the test-only runtime route is implemented and bounded, but no production binding or real stage write is claimed.

`InvocationGraph.identity_required` persists the opt-in policy. `InvocationOptions` and `DAGExecutor.run_invocation` match it before node execution. A fresh claimed invocation keeps admitted input, continuation, child terminal, and published output in its coordinator-local live transport after the existing JSON admission checks. The live entries are checked against invocation attempt, revision, step, and exact wire payload. An incomplete restored identity-required graph fails before executing nodes; a terminal direct replay returns its durable terminal without dependent CALL. A restored workflow terminal cannot publish as a live identity route. Default policy retains JSON replay.

Fresh public workflow update: `ExecutionAdmission` creates the durable graph and, for `identity_required=True`, transfers its fresh coordinator through the initial claim into `PassExecution` without treating it as a restored checkpoint. It checks revision/blob/claim, retains the claim through workflow publication, and clears live objects before release. A reopened unfinished graph refuses before node execution; a terminal response is read without another CALL. An identity-required replan is explicitly refused before the next pass because a new pass cannot inherit the old identity context. The test-only registered pair passes through public `DAGEngine.run` with `is` at prepare and stage and exact response; no production Artifacts binding/write is claimed.

The bounded registered test-only `test_live_identity.py` runs Route → Prepare → Stage via actual Engine CALL. It checks `is` for original `FakePrepared` at root/prepare and for the returned `PreparedArtifact` at stage, plus nested content, exact count and one call per operation. It also checks terminal replay without new calls, policy mismatch, incomplete checkpoint refusal, malformed root input refusal, and typed failure/cancellation/runtime failure return to the caller without another CALL. A private handoff probe checks that a second owner cannot claim while live output is read and that cleared live payload refuses after release. An admitted typed-error retry preserves the same stage input/content on its second attempt. The same fixture verifies fresh public `DAGEngine.run` with one Prepare/Stage pair, `is` at both boundaries, exact published response, terminal `resume` without new calls, preexisting unfinished `run`/`resume` refusal, public policy mismatch, and explicit replan refusal before a second pass. Under active child execution, external cancellation and forced owner loss drain before release, do not return Stage to Route, run no effects, and reject unfinished resume. A claimed `store.load` fault releases ExecutionState exactly once and frees the claim. Targeted fixture: 1 PASS in 0.428 seconds with 25-second watchdog. Its Stage spy proves transport only; no artifact write, lease authority, or production binding is claimed. Independent coordinator replay suite after earlier transport corrections: 30 PASS in 110.166 seconds. Seven focused ordinary CALL/continuation/error/retry/restart regressions after latest public lifecycle changes: PASS in 1.328 seconds. Sandbox runs hang before test code in Windows `asyncio` socketpair setup; bounded escalated runs execute.

## Проверка оставшегося engine-стыка — 2026-11-26

Независимый read-only probe после owning/P2 fixes: actual InvocationCoordinator.encode(stage_input, type(stage_input)) → model_validate_json, как в DAGExecutor._invocation_step. Existing FakePrepared/test.rows и реальные owning envelopes: до encode prepared/content identity=True; после восстановления values equal=True, prepared identity=False, content identity=False. Это воспроизведение фактической serialization boundary, не полный зарегистрированный node-run.

Код CALL подтверждает: InvocationCoordinator назначает child.input через encode(request.input,...), DAGExecutor._invocation_step восстанавливает его из JSON. Поэтому проблема относится и к обычному child CALL внутри живого процесса, не только к restart/SessionFrame. Согласованная гарантия identity на этом маршруте нарушена. В проверенных backend/app/application/engine/nodes, backend/app/dataModel/engine/nodes и test-support реализаций/регистраций PrepareArtifactNode/StageArtifactNode не найдено; проверять «готовый registered маршрут» пока нечего. Existing прямой NodeRunner/ContractValidator не выдаётся за поддержку связанной пары.

Вердикт остатка: identity на проверенной engine CALL boundary — FAIL; concrete node registration/production Error binding — NOT IMPLEMENTED/OPEN. Owning identity и diagnostic P2 scoped PASS сохраняются. Следующее решение касается именно engine transport либо явного изменения identity гарантии; не требует повторного исправления Artifacts storage. Код в этой проверке не менялся.

## Независимая повторная проверка P2 — 2026-11-26

Координатор повторил `.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.storage.artifacts.test_content_identity tests.snapshotCore.contracts.test_registry` из backend: **23 PASS**, actual Pydantic 2.13.4. Просмотрены actual admission, descriptor.check, base/generic envelopes и transport test.

**Owning diagnostic P2 — scoped PASS:** prepare content, stage prepared.content, format prepared, descriptor prepared.descriptor имеют согласованные named schema roots и owners каждого сегмента. Ручной generic ModelIdentity/segments в двух producers удалён. Стабильный content→format порядок проверен. Existing generic inputs и success identity сохранены тестами. Полный ArtifactInputError проходит Python/JSON и canonical round-trip внутри test DiagnosticWrapper; отсутствие bases в test-local manifest отвергается.

Прежнее утверждение о текущем неверном stage-пути ниже относится к состоянию 2026-11-25 и заменено этим verdict. P2 больше не является воспроизводимым owning дефектом в проверенном объёме. Test DiagnosticWrapper/manifest не являются production NodeError binding: exact production manifest/IDs и Error transfer фактической зарегистрированной пары ещё не приняты. Static и pinned-version PASS не заявлены. Engine JSON identity gap остаётся OPEN и independently блокирует приёмку всего prepare→stage route; этот документ не объявляет identity bug закрытым.

## Owning diagnostic implementation — 2026-11-26

После согласования schema-base semantics реализованы ArtifactPrepareStageInputBase, PreparedArtifactBase и ArtifactStageInputBase; existing generic envelopes наследуют эти схемы с concrete полями. Admission и DescriptorBuilder.check используют CheckedPath/FieldRef: content, prepared.content, prepared, prepared.descriptor с согласованными root/owners. Ручная сборка ModelIdentity/segments удалена из этих producers. Caller API и success identity сохранены. Проектный `.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.storage.artifacts.test_content_identity tests.snapshotCore.contracts.test_registry -q`: 23 tests PASS. Проверены independent issue order, Python/JSON full Error wrapper и canonical cold round-trip с test-local manifest, включая отказ без referenced bases в allowlist. Production IDs/manifest binding не назначались; static checker pyright в этом окружении отсутствует. Это owning implementation evidence, не независимая приёмка public Error gate. Engine JSON-route и production registration остаются OPEN. Исторические записи ниже описывают состояние до этой дельты.

Дополнение по owning review P1/P2: StageInput.prepared теперь использует instance-preserving schema с полной проверкой вложенных полей, включая forged model_copy content/descriptor. Schema validators получают временный deepcopy validation graph, а не caller-owned вложенные модели; canonical comparison выполняется с неизменённым исходным graph. Это временная validation allocation, не transport replacement: successful prepared/content возвращаются исходными instances. Тот же принцип применён к registry schema precheck и content admission. Регрессии на мутирующий field_validator (object.__setattr__ вложенного frozen child) и forged PreparedArtifact добавлены. Identity+registry suite: 22 tests PASS. Copy/validation overhead требует измерения в performance gate; это не обещание zero-allocation. Произвольные внешние side effects пользовательского Python callback этим не изолируются; проверка защищает переданный ему validation graph, не является sandbox. Engine route/P2 diagnostic-root/full registration остаются OPEN.

## Независимая проверка DAG-координатора — 2026-11-25

### Вердикт приёмки

**Owning identity fix — scoped PASS. Полный публичный контракт и конкретная регистрация пары PrepareArtifactNode → StageArtifactNode — НЕ ПРИНЯТЫ. BUG-ARTIFACTS-DAG-IDENTITY остаётся OPEN.** Причина не в отсутствии разрешения реализации и не во внутренних storage/lease механизмах, а в несоответствии двух проверенных публичных/транспортных границ:

| Граница | Почему не принимается | Владелец закрытия | Необходимое evidence |
|---|---|---|---|
| Межнодовая передача PreparedArtifact | На проверенном JSON route восстанавливается новый объект: равенство значений сохраняется, `stage.request.prepared is prepare.output.value` не гарантируется. Это противоречит принятому in-process identity-контракту | Engine/DAG transport; Artifacts участвует только при предложении изменения публичной гарантии | Actual зарегистрированный prepare→stage execution path с identity на всех шагах, либо отдельно согласованное пользователем изменение transport/гарантии и его регрессии. Отдельные вызовы ContractValidator не заменяют этот тест |
| Публичный Error POJO stage (отдельный P2) | ArtifactInputAdmission выдаёт `content` относительно stage input, где поле находится в `prepared.content`; ручная сборка segment owners также не доказывает корректную типизированную цепочку | Artifacts; Fields/C0 согласует допустимость root/owner binding при необходимости | Корректные prepare `content`, stage `prepared.content`, format `prepared`; root/каждый owner, стабильная агрегация, generic input compatibility и unchanged Error transport через wrapper |

Первый пункт — незакрытая часть identity bug. Второй — отдельный дефект, который независимо препятствует полной приёмке public Input/Output/Error пары; он не отменяет scoped PASS owning identity fix. Новый выбор BLOB, отключение validation, model_construct, object tokens или молчаливая замена identity на equality не являются закрытием.

Что принято в проверенном объёме: owning identity suite и registry suite (20 tests), а также direct in-memory wrapper/ContractValidator handoff для указанного test-only SQL_ROWS-кандидата. Что не доказано: зарегистрированный маршрут пары, real stage write/authority, production binding, static/pinned-version coverage. Последние проверки не подменяются spy/структурным lease и не объявляются причинами новых внутренних DAG workstreams.

Проверено на actual workspace, Pydantic 2.13.4. Команда из backend: `.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.storage.artifacts.test_content_identity tests.snapshotCore.contracts.test_registry` — 20 PASS.

Дополнительный read-only probe с actual FakePrepared, ArtifactPrepareStageInput, PreparedArtifact, ArtifactStageInput и ContractValidator: named probe Input/Output wrappers strict/frozen/extra-forbid/revalidate_instances=always; prepare input content is original=True; output.value is prepared=True и content is original=True; stage input prepared is prepared=True и content is original=True после ContractValidator.validate. Это scoped PASS owning исправления и живой POJO-validation границы. Probe wrappers не являются зарегистрированными Artifacts-нoдами; stage writer/storage не выполнялись, lease только структурный вход.

JSON round-trip того же stage wrapper: equal values=True, prepared is original=False. Actual DAGExecutor (input restore и terminal output restore) и SessionFrame продолжают использовать model_validate_json. Поэтому полный зарегистрированный prepare→stage маршрут и bug closure НЕ приняты.

Отдельно воспроизведён незакрытый P2: forged wrong content + unsupported format version при ArtifactInputAdmission.stage дают ordered paths `(content,)`, `(prepared,)`; первый должен быть `(prepared,content)`. Это самостоятельный дефект публичного Error, не регрессия identity fix. Полный prepare/stage public contract пока не принимается. Static и pinned-version проверки этим прогоном не заявлены.

Статус: **OPEN**. Блокирует приёмку конкретной регистрации `PrepareArtifactNode` и `StageArtifactNode`. Production-маршрут этой пары ещё не введён; баг относится к совместимости проверенных кандидатных маршрутов с owning контрактом Artifacts.

Owning fix 2026-11-25: content envelopes используют отдельные native JSON/Python schemas; Python admission сохраняет исходный concrete instance после schema/deep-immutability/canonical checks. Registry.encode валидирует без присваивания cloned result. Тест `tests.snapshotCore.storage.artifacts.test_content_identity` проверяет bytes/FakePrepared SQL_ROWS identity, strict Python/JSON tuples, wrong/subclass/forged/mutable/missing/normalizing и nested trusted-model negatives. Вместе с registry suite: 20 tests PASS. Расширенный staging suite выявил отдельный mismatch старого ожидания ValueError с actual ArtifactLeaseRefused(ADMISSION_CLOSED) в cancellation test; полный staging PASS не заявляется. Pyright в текущем Python environment не установлен. Engine JSON identity gap и diagnostic-root P2 не закрыты этой owning дельтой; общий статус OPEN сохраняется.

## Ожидаемый контракт

- `ArtifactPrepareStageOpenPipeline.prepare_stage` получает тот же экземпляр `content`, который передал producer: `request.content is content`.
- `ArtifactStageOpenPipeline.stage` получает тот же временный `PreparedArtifact`, который вернул `prepare_stage`: `request.prepared is prepared` на принятом in-memory маршруте.
- `ArtifactStageInput.lease` приходит от внешнего issuer; нода lease не приобретает.

Источники: `.cursor/plans/gen-dag-artifacts-node-contracts.md` §§ 2–4; `.cursor/plans/dag-node-layout-register.md` § Artifacts; `.cursor/plans/artifacts-public-staging-dag.md`.

## Фактическое поведение

### Тестовый SQL_ROWS-кандидат

`FakePrepared` из `backend/tests/snapshotCore/support/fakeSection.py` имеет `revalidate_instances="always"`. Существующий тестовый format binding `test.rows`, SQL_ROWS v1, задан в `backend/tests/snapshotCore/storage/artifacts/test_staging.py`. В read-only проверке использовались настоящие `ArtifactPrepareStageInput[FakePrepared]`, `PreparedArtifact[FakePrepared]`, `ArtifactStageInput[FakePrepared]`, `ArtifactRef`, `OperationLeaseRef` и `ContractValidator`; предполагаемые node wrappers были strict/frozen/extra-forbid/revalidate_instances=never.

| Граница | Результат |
| --- | --- |
| `ArtifactPrepareStageInput[FakePrepared](content=c)` | `request.content is c` → `False` |
| `PreparedArtifact[FakePrepared](content=c, descriptor=ref)` | `prepared.content is c` → `False` |
| `ArtifactStageInput[FakePrepared](lease=lease, prepared=prepared)` с `ContractValidator.validate` | `input.prepared is prepared` → `True` |

Следовательно, `FakePrepared` теряет identity `content` уже при создании owning POJO, до Engine. Локальная передача самого `PreparedArtifact` в stage сохраняет его identity. Существующий тест `test.rows` использует прежний `TypedArtifactStager`, поэтому не служит contract test новых public `prepare_stage`/`stage`.

### JSON-восстановление Engine

`backend/app/application/engine/runtime/dag/dagExecutor.py` восстанавливает input/output через `model_validate_json`; `backend/app/application/engine/runtime/invocations/sessionFrame.py` сохраняет через `model_dump_json` и восстанавливает через `model_validate_json`. Такой маршрут создаёт новый экземпляр `PreparedArtifact` и не удовлетворяет `request.prepared is prepared`. Этот вывод относится к маршруту с JSON-восстановлением; возможный самостоятельный in-memory execution route требует отдельного contract test.

## Влияние и граница исправления

### Owning воспроизведение Artifacts — 2026-11-25

Проверено actual кодом через `python -` из `backend`, CPython текущего workspace; exit code 0 означает успешное **воспроизведение дефекта**, не contract PASS. Использованы existing FakePrepared(values=(1,2)), test.rows SQL_ROWS v1 binding с encode=model_dump_json().encode и row_count=len(values), actual registry/descriptor/admission/prepare pipeline и actual ContractValidator. Backend — create_autospec(ArtifactBackend), только для registry composition; write/verify/lease operations не выполнялись. Structural lease использован исключительно при construction StageInput, не как доказательство authority или успешного stage.

| Последовательность / assertion | Actual |
|---|---|
| c=FakePrepared(values=(1,2)); request=ArtifactPrepareStageInput[FakePrepared](content=c); request.content is c | False |
| prepare_stage(request): encode spy получает объект is request.content | False |
| prepare_stage(request).content is request.content | False |
| ArtifactStageInput[FakePrepared](lease=lease,prepared=result).prepared is result | True |
| ContractValidator.validate(stage,type(stage)): admitted is stage; admitted.prepared is result | True; True |
| result.content == c | True |

Воспроизводимая bounded процедура: создать binding как в existing `tests/snapshotCore/storage/artifacts/test_staging.py::test_sql_row_count_is_owned_by_format_binding`, сохраняя аргумент encode в списке; зарегистрировать autospec backend с `backend.contract=binding`; создать `ArtifactDescriptorBuilder(binding,1,registry)` и `ArtifactPrepareStageOpenPipeline(ArtifactInputAdmission(binding),builder)`; выполнить шесть assertions таблицы. Никаких JSON transport, node wrappers или Engine execution в этом probe нет. Вызов ContractValidator является только проверкой owning stage envelope, не проверкой node route.

Точные места: `dataModel/artifacts/staging/preparedArtifact.py` поля content обоих envelopes запускают schema FakePrepared с revalidate_instances=always; внешний envelope revalidate_instances=never не предотвращает nested clone при его construction. `application/artifacts/registry/artifactRegistry.py::encode` дополнительно присваивает `content = type(content).model_validate(...)`, поэтому codec получает ещё один экземпляр. `artifactDescriptor.py::prepare` конструирует новый PreparedArtifact и повторяет nested clone. `_content` в admission также вызывает model_validate, но результат отбрасывает — это validation allocation, не замена возвращаемого request.

**Минимальная рекомендуемая owning дельта, пока НЕ реализована:** в обоих owning content fields использовать instance-preserving wrap validation: выполнить concrete schema validation и deep immutability/schema проверки исходного экземпляра; не принимать canonicalized/coerced другой объект вместо исходного; после успешных проверок вернуть исходный content. Не отключать nested validation и не менять FakePrepared/domain C. Для существующего PreparedArtifact при stage revalidation сохранить сам экземпляр только после проверки его полей; гарантия не должна зависеть от доверия revalidate_instances=never. Registry.encode должен валидировать concrete content без замены объекта, передаваемого в codec. Временные validation allocations допустимы, transport-copy/serialization/model_construct — нет. Проверка полного immutable graph и canonical equality нужна, чтобы возврат исходного объекта не сохранял невалидное или нормализуемое состояние.

Public Input/Output поля, generic C, descriptor/lease и same-instance гарантия не меняются; новых domain DTO, wire IDs, token/registry объектов не требуется. Invalid-input обработка должна сохранять declared Error categories и stable aggregation; существующий diagnostic-root P2 требует отдельного Fields/C0 решения и не закрывается этой дельтой. Wrap validators не должны превращать ранее объявленный public refusal в необработанный fault внутри pipeline; construction-time schema rejection и public admission проверяются отдельно.

Тест закрытия owning части: все первые три identity assertions становятся True; stage/prepared identity остаются True; malformed/mutable/wrong concrete C по-прежнему отвергаются без codec/IO; schema-normalizing cases не проходят под видом сохранения identity; nested owning instances проверяются без model_construct. Повторить для существующего SQL_ROWS FakePrepared и bytes как дополнительного случая, не замены SQL_ROWS. Затем node owner отдельно проверяет реальный зарегистрированный route; этот локальный результат не закрывает JSON restore incompatibility, регистрацию или full stage activation.

Тестовый `FakePrepared`/`test.rows` нельзя принять как binding пары при действующем требовании identity. Concrete production `C`, format/version binding, NodeId/ContractId и проверенный execution route пока не утверждены. Нельзя назначать BLOB по удобству или обходить валидацию через `model_construct`.

Критерии закрытия:

1. Согласовать concrete existing binding и route с координатором DAG и пользователем.
2. На фактическом registered caller/execution пути проверить `is` для producer `content` на входе `prepare_stage` и для `PreparedArtifact` на входе `stage`, включая owning POJO, node wrappers и `ContractValidator`.
3. Проверить один public call каждой ноды, exact output, все declared errors, cancellation и отсутствие дублей регистрации. Spy не считать доказательством реальной записи artifact.
4. Если выбранный маршрут не может сохранить identity, отдельно согласовать изменение owning контракта или транспорта.
