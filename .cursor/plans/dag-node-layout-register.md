# Реестр размещения описанных DAG-нод

2026-11-24. По поручению пользователя привести каждую описанную ноду в порядок. Это единая карта размещения текущих описанных write/Time/Lifecycle/Artifacts нод и используемого Cache-примера, не inventory всех legacy-нoд репозитория. Existing = файл найден, не автоматический PASS тестов/production wiring. Target = путь закреплён для будущего файла. Несоответствующее правилу размещение подлежит переносу по карте ниже; сам перенос кода этой документальной правкой не выполнен.

## Правила

- Одна нода — один .py файл — один класс ноды. Правило обязательно для production и mock/test нод без исключений. POJO и registration размещаются отдельно от реализации ноды.
- У каждого семейства один корневой каталог. Внутри разрешены группы операций в подпапках; родитель и дети соответствующей группы размещаются внутри этого корня. Не создавать соседние семейства по именам отдельных операций. Правило одинаково для production и mock.
- Семейство — логическая группа. Caller не означает parent: самостоятельные Time/Lifecycle/Snapshot leaf вызываются из write flow, но не становятся его дочерним семейством.
- timeSettings — группа внутри Time: N/time/timeSettings/. Папки отражают группировку; parent/child отношения определяются контрактом оркестрации, не любым CALL или импортом.
- NodeId не выводится автоматически из path. Existing IDs сохраняются. Для новых путей идентификаторы остаются proposed/OPEN по node-card, никакой массовой регистрации.
- Generator/gameplay/другие будущие домены OUT. Внутренние методы доменов не становятся строками этого реестра.

Пути таблиц относительно backend/. Обозначения: N=app/application/engine/nodes; P=app/dataModel/engine/nodes; L=tests/lifecycle/support. Это сокращения путей, не новые каталоги.

## Общая запись и mock binding

### Единые корни семейств — уточнение 2026-11-25

| Семейство / процесс | Production root | Mock root в текущем test-support | Организация внутри корня |
|---|---|---|---|
| Общая запись | N/writeChanges/ | Не назначен | write_changes и prepare_changes; один registration.py |
| Time | N/time/ | Не назначен | Clock/read leaf в корне; настройки в timeSettings/; root registration собирает регистрацию группы |
| Lifecycle | N/lifecycle/ (target при появлении production binding) | L/nodes/lifecycle/ | Все девять mock leaf в одном корне; будущие группы только внутри него |
| PatchSet | N/patchSet/ (target при появлении production binding) | L/nodes/patchSet/ | Assembly leaf; будущие группы внутри того же корня |
| Snapshot | N/snapshot/ (target при появлении production binding) | L/nodes/snapshot/ | Apply leaf; будущие группы внутри корня. Publication — часть Snapshot, соседнее семейство нод не вводится |
| Artifacts | N/artifacts/ | Не назначен | Prepare/stage leaf в корне; будущие группы внутри него |
| Cache | N/cache/ | Не назначен | Read/write parents и existing leaf в корне |
| Pack | N/pack/ (target) | Не назначен | Read/write группы, если приняты, размещаются внутри pack/, не как соседние packRead/packWrite |
| Source | N/source/ (target) | Не назначен | Все будущие принятые Source node bindings внутри source/, не отдельные корни по proof/capture операциям |

Это карта каталогов, не принятие новых нод, NodeId, публичных методов или CALL. Pack/Source concrete node roster остаётся в своих контрактных планах; папка не добавляет их в текущий write flow. Production и test-support — разные пространства размещения, synthetic типы не переносятся в app. Для малых семейств дополнительные подпапки не обязательны. Если появляются группы, их registration.py собирает корневой registration.py семейства без повторной регистрации; импорт модулей не должен автоматически регистрировать ноды. Регистрация не исполняет оркестрацию.

POJO остаются отдельно от node implementation. Эта правка не перемещает owning domain DTO и не создаёт новые корни dataModel автоматически. NodeId/ContractId и граф CALL сохраняются при смене каталогов.

| Нода / класс | Семейство; caller | Implementation | POJO / registration | Статус |
|---|---|---|---|---|
| write_changes / WriteChangesNode | запись, root; внешний CALL | N/writeChanges/writeChangesNode.py | P/writeChanges/contracts.py; N/writeChanges/registration.py | Target; exact aggregate IO OPEN |
| prepare_changes / PrepareChangesNode | запись, child write_changes | N/writeChanges/prepareChangesNode.py | P/writeChanges/contracts.py; N/writeChanges/registration.py | Target; exact scenario/CALL IO OPEN |
| assemble_patch_set / AssemblePatchSetNode | PatchSet leaf; write_changes | L/assemblePatchSetNode.py | L/writeNodeContracts.py; L/writeNodeBindings.py | Existing concrete mock only |
| apply_snapshot / ApplySnapshotNode | Snapshot самостоятельный leaf; write_changes | L/applySnapshotNode.py | L/writeNodeContracts.py; L/writeNodeBindings.py | Existing concrete mock only; public target readiness отдельно |

Actual mock NodeId/ContractId: engine.patch.mock_lifecycle.assemble_patch_set и engine.snapshot.mock_lifecycle.apply_snapshot. POJO: MockAssemblePatchSetInput/Output, MockApplySnapshotInput/Output. Actual SnapshotPublicNodeError/SnapshotOperationCancelledNodeError пока в L/writeNodeContracts.py: прежний proposed P/snapshot/contracts.py не объявлять существующим или обязательным параллельным дублем. Production generalization — отдельная контрактная дельта, не перенос mock классов в app.

## Time: самостоятельные leaf без Time parent

Общий target POJO модуль P/time/contracts.py, target registration N/time/registration.py. Caller read-нод в текущем write flow не назначается; это отдельные уже описанные карточки, не расширение read_world.

| Нода / класс | Implementation | Input → Output envelope | Статус |
|---|---|---|---|
| prepare_time_section / PrepareTimeSectionNode | N/time/prepareTimeSectionNode.py | PrepareTimeSectionInput → PrepareTimeSectionOutput | Existing; импорт и общая регистрация проверены 2026-11-25; полная runtime-приёмка отдельно |
| read_current_time / ReadCurrentTimeNode | N/time/readCurrentTimeNode.py | ReadCurrentTimeInput → ReadCurrentTimeOutput | Target, чтение вне текущего среза |
| read_pinned_time / ReadPinnedTimeNode | N/time/readPinnedTimeNode.py | ReadPinnedTimeInput → ReadPinnedTimeOutput | Target, чтение вне текущего среза |
| read_historical_time / ReadHistoricalTimeNode | N/time/readHistoricalTimeNode.py | ReadHistoricalTimeInput → ReadHistoricalTimeOutput | Target, чтение вне текущего среза |

Полные owning payload unions — gen-dag-time-local-node-contracts.md; они не копируются/не меняются размещением. prepare_time_section вызывается prepare_changes, остальные не добавляются автоматически. Новых read error моделей здесь нет.

## Настройки Time

POJO всех existing single leaf: P/timeSettingsContracts.py. Registration: N/time/timeSettings/registration.py. Родитель prepare_world_time_settings_changes — orchestrator; single children вызываются им. Parent вызывается prepare_changes и возвращает prepared/refusal; prepare_changes отдельно вызывает section producer.

| Нода / класс | Implementation | Статус |
|---|---|---|
| prepare_world_time_settings_changes / PrepareWorldTimeSettingsChangesNode | N/time/timeSettings/prepareWorldTimeSettingsChangesNode.py | Target parent; IO/CALL contract OPEN |
| prepare_hours_change / PrepareHoursChangeNode | N/time/timeSettings/prepareHoursChangeNode.py | Existing |
| prepare_calendar_create / PrepareCalendarCreateNode | N/time/timeSettings/prepareCalendarCreateNode.py | Existing |
| prepare_calendar_update / PrepareCalendarUpdateNode | N/time/timeSettings/prepareCalendarUpdateNode.py | Existing |
| prepare_calendar_select / PrepareCalendarSelectNode | N/time/timeSettings/prepareCalendarSelectNode.py | Existing |
| prepare_calendar_remove / PrepareCalendarRemoveNode | N/time/timeSettings/prepareCalendarRemoveNode.py | Existing |
| prepare_epoch_create / PrepareEpochCreateNode | N/time/timeSettings/prepareEpochCreateNode.py | Existing |
| prepare_epoch_update / PrepareEpochUpdateNode | N/time/timeSettings/prepareEpochUpdateNode.py | Existing |
| prepare_epoch_remove / PrepareEpochRemoveNode | N/time/timeSettings/prepareEpochRemoveNode.py | Existing |
| Settings batch leaf / PrepareTimeSettingsBatchNode (project name) | N/time/timeSettings/prepareTimeSettingsBatchNode.py | Target; NodeId/IO freeze OPEN |
| Settings section leaf / PrepareTimeSettingsSectionNode (project name) | N/time/timeSettings/prepareTimeSettingsSectionNode.py | Target; NodeId/IO freeze OPEN |

Existing single NodeId равны указанным logical names; ContractId engine.time.settings.<NodeId>. Exact payload unions и actual error transport — gen-dag-time-settings-method-contracts.md/actual contracts.py. Для target parent/batch/section: отдельный P/timeSettingsWorkflowContracts.py, соответствующие декларации в том же registration.py только после freeze. Новый файл разделяет ещё проектируемый workflow и existing single contracts; owning DTO не дублируются. Проектное имя класса/файла не утверждает NodeId или public method readiness.

## Lifecycle: девять test-only registrations

Семейство Lifecycle, пять logical операций; собственного parent нет. Caller prepare_changes, либо test invocation. Implementation/registration L/nodeBindings.py; node POJO L/nodeContracts.py. Owning DTO находятся в собственных доменных/test-support модулях, здесь не переносятся.

| NodeId | Node class | Input → Output |
|---|---|---|
| engine.lifecycle.test_a.prepare_create | CreateANode | CreateNodeInputA → CreateNodeOutputA |
| engine.lifecycle.test_b.prepare_create | CreateBNode | CreateNodeInputB → CreateNodeOutputB |
| engine.lifecycle.test_a.prepare_replacement | ReplaceANode | ReplaceNodeInputA → ReplaceNodeOutputA |
| engine.lifecycle.test_b.prepare_replacement | ReplaceBNode | ReplaceNodeInputB → ReplaceNodeOutputB |
| engine.lifecycle.test_a.prepare_end | EndANode | EndNodeInputA → EndNodeOutputA |
| engine.lifecycle.test_b.prepare_end | EndBNode | EndNodeInputB → EndNodeOutputB |
| engine.lifecycle.test_a.prepare_reactivate | ReactivateANode | ReactivateNodeInputA → ReactivateNodeOutputA |
| engine.lifecycle.test_b.prepare_reactivate | ReactivateBNode | ReactivateNodeInputB → ReactivateNodeOutputB |
| engine.lifecycle.prepare_section | SectionABNode | SectionNodeInputAB → SectionNodeOutputAB |

Все Existing. Production entity специализации и будущий parent варианта Б не создаются; lifecicle-todo.md остаётся отдельным развитием OUT.

## Artifacts: описанные leaf

| Нода / класс | Implementation | POJO / registration | Статус |
|---|---|---|---|
| prepare_artifact / PrepareArtifactNode | N/artifacts/prepareArtifactNode.py | P/artifacts.py; N/artifacts/registration.py | Target; concrete C/binding OPEN |
| stage_artifact / StageArtifactNode | N/artifacts/stageArtifactNode.py | P/artifacts.py; N/artifacts/registration.py | Target; concrete C/binding OPEN |

Самостоятельные leaf семейства Artifacts, parent не вводится; caller маршрута требует concrete binding. Scope текущей записи не расширяется staging. Полные envelopes/public targets — gen-dag-artifacts-node-contracts.md. Scoped handoff/held-refs не DAG-ноды.

## Cache: existing пример и описанный parent уровень

| Нода | Implementation | POJO / registration статус |
|---|---|---|
| read_cache_entry | N/cache/readCacheEntryNode.py | Existing; P/cache/contracts.py/manifestContracts.py по binding |
| create_cache_entry | N/cache/createCacheEntryNode.py | Existing; те же owning node contracts |
| update_cache_entry | N/cache/updateCacheEntryNode.py | Existing; те же owning node contracts |
| evict_cache_entry | N/cache/evictCacheEntryNode.py | Existing; те же owning node contracts |
| read_cache (orchestration) | N/cache/readCacheNode.py | Target, полный contract в отдельном family плане |
| write_cache (orchestration) | N/cache/writeCacheNode.py | Target, полный contract в отдельном family плане |

Existing manifest Cache registration находится в N/cache/registration.py и использует concrete POJO P/cache/manifestContracts.py. Для новых Cache parents target POJO P/cache/workflowContracts.py; расширение существующего registration.py только после freeze их контрактов. Эта карта не мигрирует existing Cache registration и не подключает Cache к write_changes без принятого сценария. Family contract источник — gen-dag-cache-pack-source-families.md.

## Оставшиеся правила работы

### Обязательная целевая раскладка mock-нод

Предыдущие строки Existing описывают фактическое состояние, а не исключение из правила. Общий корень mock-семейств: L/nodes/. Перенос сохраняет NodeId, POJO и поведение; imports и registration переводятся на единственные новые классы без дублирующих реализаций.

| Семейство | Класс ноды | Целевой файл |
|---|---|---|
| Lifecycle | CreateANode | L/nodes/lifecycle/createANode.py |
| Lifecycle | CreateBNode | L/nodes/lifecycle/createBNode.py |
| Lifecycle | ReplaceANode | L/nodes/lifecycle/replaceANode.py |
| Lifecycle | ReplaceBNode | L/nodes/lifecycle/replaceBNode.py |
| Lifecycle | EndANode | L/nodes/lifecycle/endANode.py |
| Lifecycle | EndBNode | L/nodes/lifecycle/endBNode.py |
| Lifecycle | ReactivateANode | L/nodes/lifecycle/reactivateANode.py |
| Lifecycle | ReactivateBNode | L/nodes/lifecycle/reactivateBNode.py |
| Lifecycle | SectionABNode | L/nodes/lifecycle/sectionABNode.py |
| PatchSet | AssemblePatchSetNode | L/nodes/patchSet/assemblePatchSetNode.py |
| Snapshot | ApplySnapshotNode | L/nodes/snapshot/applySnapshotNode.py |

У каждого из трёх семейств отдельный registration.py в его папке. Тестовые POJO остаются в L/nodeContracts.py и L/writeNodeContracts.py отдельно от классов нод. Прежние nodeBindings.py/writeNodeBindings.py не сохраняют реализации нод: если нужен общий composition entry point, он только вызывает регистрации семейств. Физический перенос и проверка imports/регистраций — оставшаяся задача реализации, не выполненная этим обновлением плана.

Перед выдачей node implementation task обязательна строка этого реестра + конкретная Input/Output/Error card. Для target недостаточно одного имени файла: absent POJO/NodeContract отдельно OPEN. При изменении пути обновить эту карту и owning node plan одним документальным изменением; проверять actual imports, без параллельного дубля класса. Производственные и synthetic регистрации не смешивать.

Общий граф: write_changes CALL prepare_changes, assemble_patch_set, apply_snapshot; prepare_changes CALL самостоятельные domain preparation leaf/settings parent/section producers; settings parent CALL single либо batch. Read Time/Artifacts/Cache ветви не становятся обязательными стадиями по наличию папки. Новых CALL этим реестром не добавляется.
