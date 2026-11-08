# DAGEngine — распределение реализации по доменам

Предложение для согласования. Область — весь [DAGEngine](../../backend/app/application/engine/runtime/dagEngine.py), включая поведение до F4. Контракты поведения заданы в [ТЗ engine §§7–10](../../docs/tz_engine_node_context.md) и [плане durable invocation, включая F2–F4](./dag-invocations-bake-admission.md).

## Публичная граница

Сохранить конструктор и сигнатуры run, resume, accept_input, resume_input, cancel_waiting_child, cancel_execution. DAGEngine связывает зависимости и передаёт команды владельцам. resume_input задаёт порядок accept → resume с валидацией запроса до первой записи. Второй публичный движок и общая база с полями прежнего фасада не нужны. Новые компоненты получают только свои зависимости. Их конструкторы не принимают DAGEngine.

Прямые импорты runtime-фасада в backend найдены в [pass tests](../../backend/tests/dag_typing/lifecycle/test_passes.py), [invocation tests](../../backend/tests/dag_typing/invocations/test_world_calls.py) и в typing fixtures [valid](../../backend/tests/dag_typing/typing/valid.py), [invalid](../../backend/tests/dag_typing/typing/invalid.py). Проверки взаимодействия через [input tests](../../backend/tests/dag_typing/invocations/test_input_wait.py) используют тот же engine через fixture. Пробы, патчащие приватные поля фасада, подключать к исходному binding/executor fixture.

## Карта переноса

Все пути ниже относительны к backend/app/application/engine. Каждый шаг включает переключение существующего caller и удаление перенесённой реализации из фасада.

| Шаг | Исходная реализация в DAGEngine | Владелец и целевой файл | Проверяемая граница |
|---|---|---|---|
| 1 | read_header, terminal внутри _restore_durable | runtime/invocations/recovery/terminalReplay.py — чтение checkpoint и типизированного результата. Использовать SessionFrame, InvocationGraph, InputWaitCoordinator.check_owner и тип ответа binding | Finalized → ResolveResult либо Failed до claim, compile, restore и файлового IO. Неверная identity, доступ, checksum или тип отклоняются |
| 2 | drive_to_final и ветки claim / renew / release / takeover в _restore_durable | runtime/invocations/recovery/executionRecovery.py — владелец recovery lease и порядка intent → CLOSED → finalize. Получение либо подтверждение CLOSED после потери ответа инкапсулировать на стороне Pack через текущий порт. Проверка ключа и CAS остаются в ExecutionStore.finalize | Отсутствующий receipt и устаревший fence оставляют intent. После commit повтор читает победителя. Heartbeat действует и во время close |
| 3 | _interaction_settings, _interaction_graph, accept_input, cancel_waiting_child, cancel_execution | runtime/invocations/interaction/executionInteraction.py — authenticated команды и их revision CAS. Правила содержимого wait и принятия payload остаются у существующего InputWaitCoordinator | Чужой owner, повторная доставка, cancel до/после приёма и конкурентный claim. После intent нет новой работы |
| 4 | _drive и _prepare_reuse | runtime/dag/lifecycle/passExecution.py — управление стадиями и переходами pass. Scheduling остаётся у DAGExecutor, invalidation у каталога, разрешение ответа у ResponseResolver, effects у LifecycleBinding | Тот же порядок, бюджет и reuse. Resume с RESPONSE не повторяет effects |
| 5 | Ветви snapshot resume, cancel/capture и _lifecycle_event | runtime/dag/lifecycle/sessionRecovery.py — восстановление/сохранение сессии, проверка cursor и revision и события snapshot; encode/decode у ExecutionSnapshotService | Отмена распространяется после cleanup; ошибки restore/save сохраняют диагностику и прежний snapshot |
| 6 | _enter, подготовка fresh run и выбор durable/snapshot в run/resume | runtime/dag/lifecycle/executionAdmission.py — один активный запуск на execution ID в экземпляре engine, начальная привязка и выбор пути восстановления. Снять допуск в finally | Совпадающий terminal run попадает в replay до compile, обычный fresh run начинает pass только после успешного compile. Независимые ID не блокируют друг друга |

Для взаимодействия владельцев переиспользуются ExecutionId, InvocationOptions, Checkpoint, Claim, ExecutionStopIntent, CloseReceipt, ExecutionResult, ExecutionState, ExecutionPlan и существующие контракты binding/store. Wire-форматы, SQL, коды ошибок и правила удержания pins остаются прежними. В runtime/invocations уже восемь непосредственных файлов; новые recovery и interaction операции размещаются в тематических подпапках.

## Приёмка

После каждого переноса прогнать связанный модуль pass, world_calls, input_wait либо execution_stop_intent. Для Pack проверить также tests.spatial_pack.test_execution_pins. Финально выполнить полный DAG-набор и Pyright по командам [отчёта F4](./sp-p2w-f4-verification.md). Отдельно проверить diff, ответственность и размер каждого изменённого класса. Ни один из вынесенных компонентов не должен повторять весь публичный API DAGEngine.
