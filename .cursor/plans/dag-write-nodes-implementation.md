# Реализация нод записи: Time, настройки Time, Lifecycle

## Mock G5 implementation — 2026-11-25

Исполнитель предъявил tests/lifecycle/support/writeChangesContracts.py и две ноды в tests/lifecycle/support/nodes/writeChanges/ с отдельной registration.py. NodeId: engine.write.mock_lifecycle.prepare_changes / engine.write.mock_lifecycle.write_changes, ContractVersion 1. Scope — subject A + Lifecycle AB, порядок sections=(subject,lifecycle), без Time. Production app paths остаются target; app→tests imports запрещены.

Owner evidence: import/AST PASS, 13 unique mock registrations и rejection duplicate, 4 прежних tests.lifecycle.test_write_nodes PASS. Это не независимая приёмка новых родителей. Новый nested runtime trace с real scenario fixture не завершился более 60 секунд и был удалён исполнителем; причина пока неизвестна. Запрошено восстановление bounded regression coverage с разделением fixture setup и engine CALL. Success/refusal/error/cancellation trace новых родителей остаётся OPEN. Данный статус не означает durable apply или полного write flow PASS.

## Актуальный статус Time — 2026-11-25

- Реализованы 12 нод: prepare_time_section, восемь single leaf настроек, prepare_time_settings_batch, prepare_time_settings_section и prepare_world_time_settings_changes. Файлы трёх новых нод и workflowContracts.py предъявлены исполнителем; owning batch/section API также реализованы по отчёту Time.
- Импорты после переноса исправлены. register_time_nodes() вызывает регистрацию time/timeSettings и успешно регистрирует ровно 12 уникальных NodeId. Это независимо проверенный PASS импортов и локальной регистрации, не production wiring или полная runtime-приёмка.
- Проверка: из backend выполнен импорт register_time_nodes/NodeRegistry, регистрация и чтение registry.ids(); получены все 12 ожидаемых IDs.
- Запуск `.venv/Scripts/python.exe -B -m unittest tests.time.test_settings_leaves` после исправления импортов не завершился за время проверки и был прерван. Итог исполнения неизвестен; ни PASS, ни установленная причина сбоя ему не приписываются. Прежний import failure устранён.
- По отчёту исполнителя parent реализован как ResumablePythonNode с engine CallTarget: single/batch выбор, без section CALL; batch/section leaf E=Never. Это implementation evidence, не независимая проверка всех ветвей. Runtime-тест новых нод с Time fixture не завершился и был прерван; Pyright недоступен по отчёту исполнителя. Runtime/static приёмка OPEN.
- Три Time read-ноды не реализованы и вне текущего write-среза. Семейство целиком не принято.

Остаток этого Time-среза: завершить runtime/static проверку нод, всех owning outcomes и parent CALL/cancellation/error transport. Наличие файлов, локальная регистрация и приёмка исполнения — отдельные статусы. Эта запись имеет приоритет над историческими общими OPEN/Target для указанных двенадцати нод ниже и в связанных планах. Общие prepare_changes/write_changes этим не реализованы и полный write flow не принят.

Уточнение структуры 2026-11-25: для каждого семейства один корневой каталог, допускающий внутренние группы операций. Time settings находятся в nodes/time/timeSettings/, а не в соседнем nodes/timeSettings/. То же правило применяется к Lifecycle/PatchSet/Snapshot/Artifacts/Cache/Pack/Source по таблице единых корней реестра. Одна нода — один .py файл — один класс; registration и POJO отдельно. Группировка папок не меняет CALL/родство или NodeId.

Размещение каждой описанной ноды, её POJO, регистрации и родительских связей: [единый реестр](dag-node-layout-register.md). Реестр различает существующие файлы и целевые пути; размещение не закрывает OPEN контрактов и не означает production wiring.

Concrete node cards и поимённые POJO/связи: [контракты нод записи](dag-write-node-pojo-contracts.md). Первое предъявленное ребро — assemble_patch_set → apply_snapshot в mock_lifecycle_world; concrete mock leaf и локальные bindings уже существуют. Статус каждого нового binding фиксируется отдельно, без общей пометки PROPOSED для реализованных файлов.

## Приоритет работы координатора — решение пользователя 2026-11-24

**Последнее уточнение пользователя, приоритет над прежним широким scope сверок:** ответственность DAG — связывание конкретных POJO входов и выходов нод и согласованная оркестрация этих CALL. Внутреннее устройство доменов, их helpers/storage/transaction/codec и внутренние межкомпонентные контракты не входят в работу DAG-координатора. Владельцы сами отвечают за выполнение своего публичного метода. Координатор запрашивает exact public Input/Output/Error, гарантии метода и статус их готовности, но не проектирует и не принимает внутреннюю реализацию. Старые записи об отдельных внутренних ревью — история, не расширение текущей ответственности.

На каждом ребре проверяются concrete producer Output → concrete consumer Input, mapping полей, сохранение типов/значений/identity по контракту, correlation и передача всех исходов. Если POJO несовместимы, владелец предъявляет публичную контрактную дельту; DAG не компенсирует её доменными вычислениями. Неготовность публичной операции отмечается как статус target соответствующей ноды, без переноса внутреннего backlog домена в план DAG.

Единица работы и отчёта — конкретная нода и её входящий/исходящий контракт. Для каждой ноды фиксируются: имя/NodeId и статус регистрации; семейство/роль; exact named Input с полями и источником каждого поля; exact Output/Error со всеми исходами; публичный owning метод для leaf либо CALL-контракты детей для orchestrator; Output→Input mapping следующего потребителя; конкретный остаток, владелец, evidence. Неназванные wrappers остаются OPEN, не заменяются догадкой или Any.

Статусы вести раздельно: контракт принят; public method реализован; node реализована; binding зарегистрирован; проверки выполнены. Прогресс домена не равен готовности ноды. Локальный PASS не равен закрытому маршруту. Последующее решение пользователя разрешает реализовывать ноды и сводить остаток контрактов в коде; прежний общий запрет зависимой реализации не применяется как blanket gate к этому поручению. Production activation и готовность полного маршрута не следуют автоматически из реализации отдельных нод.

Вход верхнего процесса — готовые typed inputs. Генератор/gameplay и их реализация OUT: новые задания, API и ноды им в рамках этого плана не выдаются. Внутренние доменные методы/transaction/retention helpers не становятся DAG-нодами или их Input-полями. Зависимость домена фиксируется только в привязке к невозможности выполнить конкретный заявленный Output/Error; owner закрывает её в своём плане. Самостоятельные новые domain workstreams из такой зависимости не выводятся.

### Текущая карточка: apply_snapshot

| Поле | Зафиксированная граница |
|---|---|
| Роль | Самостоятельный operation leaf семейства Snapshot; одна публичная операция |
| Вход | Проектный ApplySnapshotInput[S].patch_set:PatchSet[S]; named concrete specialization/registration freeze отдельно OPEN |
| Публичный вызов | await IWorldSnapshotApply[S,T].apply(input.patch_set) → T |
| Выход | Проектный ApplySnapshotOutput[T].value:T; concrete T задаётся принятой composition, не универсальный union всех доменов |
| Входящий producer | Успешный output assemble_patch_set; write_changes переносит exact PatchSet в input.patch_set |
| Исходящий consumer | write_changes возвращает concrete owning результат caller; нода не превращает receipt в committed |
| Отказы/faults | Business outcomes внутри T; SnapshotPublicError, durable SnapshotOperationCancelledError, invocation cancellation/unknown сохраняются раздельно. Exact engine Error mapping OPEN; новый carrier по предположению не создаётся |
| Нельзя помещать в ноду | Claim/transaction/handler dispatch, receipt checks, назначение refs, metadata/CAS, удержания/handoff, rollback/replay |
| Остаток public target | Полный apply ещё должен обеспечивать заявленные outcome/atomic guarantees; принятый admission→claim не равен полному apply |
| Адресная внутренняя зависимость target | Snapshot/Artifacts уточняют scoped held-refs/handoff в owning планах. Это не новая нода, не новый Input и не требование генератора/gameplay |
| Остаток DAG | Concrete Input/Output/NodeContract/NodeId binding и lossless Error mapping, затем проверка одного public call и передачи результата |

Эта карточка фиксирует текущую известную границу, не объявляет OPEN bindings согласованными. Следующий результат координатора — точные node-contract дельты этой карточки и связь assemble output → apply input, а не разбор внутренних алгоритмов Snapshot.

2026-11-21. Составлен по поручению пользователя «Делай план». Статус: план поставки с явными контрактными gates, не общая приёмка новых нод и не начало изменений кода. Отдельные разрешения реализации владельцам не отменяются. Выполненных шагов этим документом не заявлено.

## 1. Результат и границы

Цель — выполнить через типизированные ноды согласованный маршрут write_changes → prepare_changes → assemble_patch_set → apply_snapshot, вернуть owning результат без потери concrete diagnostics и не выполнять зависимые стадии после отказа. Leaf вызывает один публичный метод; родитель вызывает контракты детей через engine. Предметные алгоритмы и storage остаются у доменов.

IN: ready typed inputs, Time advance section, одиночная/batch preparation настроек Time и их section producer, Lifecycle вариант А, typed сборка sections, вызов Snapshot и transport результата. Lifecycle — только synthetic A/B в явно названной фикстуре mock_lifecycle_world. Ветви подключаются по сценарию, не обязательны одновременно. Не вводить общий production union всех доменов ради синтетического теста.

OUT: gameplay/генераторы/NPC, получение ready inputs выше процесса, read_world, Source/Pack/Artifacts новые DAG-ветви, миграции/production wiring, legacy compatibility, Lifecycle вариант Б/overlapping chains, bulk/checkpoint/restart. Cache не требуется вставлять в запись без конкретного принятого producer/consumer. Отсутствие OUT не блокирует этот план. Внутренний terminal replay Snapshot остаётся частью гарантии write, не отдельным read_world.

## 2. Источники и порядок

- Карта и карточки: [общая диаграмма](dag-multidomain-patch-publication-draft.md), её верхний актуальный раздел.
- [Lifecycle ноды](gen-dag-lifecycle-node-contracts.md), [binding/apply](entity-lifecycle-binding-apply-contract.md), [mock result](lifecycle-mock-result-manifest.md), [manifest](patch-set-lifecycle-mock-manifest-roster.md).
- [Time local nodes](gen-dag-time-local-node-contracts.md), [settings methods](gen-dag-time-settings-method-contracts.md), [Time S2–S4](time-domain.md).
- [Snapshot C2](snapshot-receipt-validation-c2.md), [facts/order](snapshot-receipt-facts-diagnostics.md), [H2](interdomain-refusal-transport-h2.md), [Snapshot H2](snapshot-refusal-transport-h2.md).
- Owning ТЗ: docs/tz_world_snapshot.md, docs/tz_entity_lifecycle.md; полный набор Time/PatchSet/engine SoT перед кодом получить из соответствующих owning-планов и прочитать. Этот документ не заменяет их алгоритмы.
- Обязательные правила: ../rules/dag-generator-interface.mdc и ../rules/interdomain-contract-coordination.mdc. Реализация через implement-plan; текущий запрос разрешает составление плана, не снимает GEN-NODE-JOINT-REVIEW.

Порядок исполнения неизменен: подготовить требуемые секции → собрать PatchSet → вызвать Snapshot. Settings single и batch — альтернативные маршруты; несколько команд обрабатывает один публичный Time batch через отдельный leaf. Не вызывать single leaf циклом и не подменять capture промежуточным after. Готовые Lifecycle transitions можно передать section producer без повторного prepare.

Внутри Snapshot: claim/exact replay → expected context/dependency/source binding → все validate → remaining bases → apply каждого handler и немедленная C2 проверка receipt → metadata/CAS/terminal/confirmed commit. DAG не воспроизводит эти стадии. Unknown не трактуется как rollback или разрешение нового apply.

## 3. Контрактные gates с точной областью

| Gate | Решение/артефакт для закрытия | Владелец | Что зависит; что не зависит |
|---|---|---|---|
| G0 | Актуальная инвентаризация code vs target, exact class/module и node registrations; не копировать устаревший engine | DAG, каждый owner | Любая реализация соответствующей ноды; документационная сверка доступна сейчас |
| G1 | Lifecycle 9 registrations: per-node приёмка существующей карты, exact Q/P и runtime target readiness | DAG/Lifecycle | Lifecycle leaf; новые settings контракты не prerequisite |
| G2 | Test allocation 94001–94062,94090–94091 и pair(1,94001): решение пользователя, manifest closure/identity | PatchSet/Snapshot/координатор | Persisted mock round-trip/integration; pure Lifecycle leaf не требует этих IDs |
| G3 | Settings single/batch/section NodeId, named engine I/O, declared errors/cancellation, family/CALL contracts | DAG/Time, пользователь | Settings ноды/parent; не блокирует принятые Time clock/Lifecycle leaf |
| G4 | Settings+advance exact common base/effective_at binding, dependencies, no-op states/retention и history policy | Time/Snapshot через координатора | Совместный apply и settings storage acceptance; pure preparation не требует storage реализации |
| G5 | Named aggregate write/prepare inputs/outputs, correlation, закрытые scenarios/unions, nested refusal transport | DAG/owners, пользователь | Реализация верхних orchestrators; leaf не требует готового parent |
| G6 | Settings native codec/key/version/IDs, handler/refusal/result binding, H2/C2 runtime readiness используемого сценария | Time/PatchSet/Snapshot/Publication | Реальный transactional integration; spies не закрывают этот gate |

Ни один OPEN не заменять Any/dict, fake error, callback в POJO или временным обходом публичной границы. Принятые Time pair(1,20150), no-legacy, Lifecycle D1–D7 и source вариант А не переоткрывать. G2 пока proposed, не автоматически accepted по появлению в таблице.

## 4. Обязательная карта классов и границ

Карта конкретных девяти Lifecycle классов/NodeId/I/O — верхняя таблица gen-dag-lifecycle-node-contracts.md, включена по ссылке без новой копии. Восемь single settings requests/methods/full unions — таблица gen-dag-time-settings-method-contracts.md. Полные concrete имена отсутствующих node-классов и wrappers фиксируются в G3/G5 ДО реализации: эта таблица задаёт обязанности, а не выдаёт неназванные классы за принятый контракт.

| Класс/роль | Допустимые зависимости и эффекты | Приёмка / причина отказа |
|---|---|---|
| Named node Input/Output | Owning request/value; транспортные инварианты, без IO | Exact closed types; FAIL копирование domain полей, открытый union/coercion |
| Lifecycle operation leaf и bindings | Один Lifecycle public pipeline; pure передача request/value | 9 exact registrations, один вызов; FAIL nested kind dispatch или повторная preparation |
| Time clock section leaf | ITimeAdvancePipelineOpenPipeline.prepare_section | Owning output целиком; FAIL Time predicates в ноде |
| 8 settings single leaf | Один закреплённый Time method | Все concrete исходы сохранены; FAIL потеря SettingsInUse/Anchor/Budget |
| Settings batch leaf | Один prepare_batch(PrepareTimeSettingsBatch) | Один вызов; FAIL цикл single public operations или own merge |
| Settings section leaf | Один prepare_section(PrepareTimeSettingsSection) | Success section/refusal без подмены; FAIL сборка native patch в DAG |
| prepare_world_time_settings_changes | CALL single либо batch leaf | Только выбор согласованного маршрута; FAIL локальная календарная логика |
| prepare_changes | CALL требуемых children, declared outputs/context | Возвращает полный typed sections набор либо отказ; FAIL silently skip обязательной секции |
| assemble_patch_set leaf | IPatchSetAssembly.assemble | Передаёт input и owning result; FAIL собственные validation/fingerprint/sorting |
| apply_snapshot leaf | IWorldSnapshotApply.apply | Возвращает exact T/fault по контракту; FAIL второй commit, retry по unknown |
| write_changes | CALL prepare → assemble → apply | Остановка зависимых стадий при отказе; FAIL прямой вызов domain internals |
| NodeContract/NodeRegistry/executor | Existing engine contract admission/CALL | Exact contract identity и output проверка; FAIL новый executor или direct child.execute |
| Owning pipelines/codec/handlers/service | Только принятые owning зависимости | Алгоритмы/IO проверяются в owning delivery; FAIL скрытые foreign public calls |

Для каждого нового concrete класса в implementation diff дополняется exact строка с module, responsibility, dependencies/effects, проверкой и причиной отказа. Отсутствующая строка блокирует приёмку этого класса, не компенсируется успешными тестами.

Lifecycle NodeContract[I,O,Never]: version 1, reads/calls/error_types пустые, остальные параметры — по принятой карте. Не переносить E=Never автоматически на Snapshot/settings: их error transport закрывает соответствующий gate. Owning business refusals остаются значениями; infrastructure/cancellation не превращаются в success/refusal без принятого mapping.

## 5. Шаги реализации и завершение каждого шага

### Обязательная граница оркестрации — поправка архитектурной сверки

Этот подраздел уточняет §4 и обязателен для N0–N5. Нода не получает предметную ответственность только потому, что проверка короткая или её удобно выполнить до CALL. Правило одного public call у leaf необходимо, но недостаточно: вложенная цепочка owning pipeline также проверяется на скрытую оркестрацию и foreign calls.

#### Разрешённые CALL и источники входов

| Caller | Разрешённый child / public target | Источник Input и использование Output | Запрещённый перенос логики |
|---|---|---|---|
| write_changes | prepare_changes → assemble_patch_set → apply_snapshot | Ready input/context → preparation; successful sections/context → assembly input; successful PatchSet → apply input; owning итог → caller | Не выбирает settings single/batch или Lifecycle transition route; не вызывает domain services, не разбирает sections/receipts |
| prepare_changes | prepare_time_section, prepare_world_time_settings_changes, settings section leaf, Lifecycle preparation/section leaf в выбранном сценарии | Typed входы и outputs передаются по заранее объявленным связям; settings prepared → section.change; Lifecycle prepared → section.changes | Не диспетчеризует восемь settings операций, не выполняет batch, не строит native patches, не решает validity/coverage/dependencies |
| prepare_world_time_settings_changes | Один concrete single leaf либо один batch leaf | Одна команда → leaf её объявленного concrete типа; несколько → один PrepareTimeSettingsBatch; success/refusal возвращается prepare_changes | Не вызывает settings section leaf/assembler/Snapshot; не сравнивает base, не вычисляет indices, budget, before/after/effective_at |
| Любой preparation/section leaf | Только закреплённый публичный owning method | input.request → method argument; полный owning result → output.value | Не вызывает другие ноды; не собирает request из hidden reads; не создаёт prepared/section вместо owner |
| assemble_patch_set | Только IPatchSetAssembly.assemble | Переданный PatchSetAssemblyInput → owning PatchSet/refusal | Не вызывает preparation или apply; не реализует проверки/codec/fingerprint |
| apply_snapshot | Только IWorldSnapshotApply.apply | Переданный PatchSet → exact owning result либо согласованный fault | Не вызывает handlers, не делает receipt validation/CAS/replay/rollback/commit самостоятельно |

Сценарий prepare_changes должен быть закрытым типизированным контрактом G5. Наличие ветвей задаётся его declared input, а не анализом предметного payload. Запрещены обнаружение новых доменов по содержимому объекта, plugin discovery во время исполнения, вложенный kind dispatch и универсальный execute(command). Допустимый выбор concrete single settings leaf находится только в settings orchestrator, а Lifecycle A/B binding фиксируется composition. Parent не воспроизводит внутренний маршрут child.

#### Сбор результатов не равен сборке PatchSet

prepare_changes сохраняет successful native sections в объявленные slots/коллекцию исходного сценария и возвращает их. Он может проверить завершение требуемых CALL по engine-контракту; это не проверка предметной полноты publication. Порядок переноса определяется frozen G5 mapping, не сортировкой по содержимому. Нельзя удалять no-op, дубли, пустые или «неподходящие» секции, сливать patches, вычислять SectionDependency или корректировать evidence.

write_changes только связывает этот результат с полями принятого PatchSetAssemblyInput. Создание транспортной оболочки разрешено; вычисление новых доменных значений — нет. Совместимость/уникальность секций, native admission и зависимости проверяет публичная операция PatchSet в пределах собственного контракта. Правила Time/Lifecycle не переносятся даже в assembler. После assembly результат PatchSet передаётся apply без исправлений.

#### Точный transport исходов

G3/G5 должны предъявить для каждого CALL named Input/Output/Error с модулем, полями, closed union, источником каждого поля, invocation correlation и явным mapping каждого owning исхода. До freeze это OPEN, не разрешение добавить Any/dict, строковый reason или общий synthetic domain refusal.

| Исход дочернего CALL | Обязанность родителя |
|---|---|
| Owning success | Передать payload следующему declared потребителю без пересоздания предметного результата |
| Owning refusal/conflict/unavailable, если допускается контрактом | Сохранить concrete payload, diagnostics/paths/order и корреляцию; не вызывать зависимый следующий этап |
| Structural input/output contract failure | Следовать engine failure transport; не подменять доменным отказом |
| Owning infrastructure fault | Только принятый lossless error mapping; без blanket catch/fallback |
| Cancellation / unknown outcome | Сохранить принятый исход; не выдавать rollback/committed и не запускать повторный apply |

Общий отказ подготовки не создаётся путём объединения diagnostics разных доменов без принятого aggregate-контракта. Parent не интерпретирует коды, не меняет категорию и не сокращает reason. Остановка зависимых стадий обязательна; политика продолжения независимых ветвей и порядок их отказов фиксируются в G5, не выдумываются реализацией.

#### Приёмка каждой ноды

Для каждой строки concrete node roster предъявить: (1) allowed CALL/public target; (2) exact Input→argument и result→Output/Error mapping; (3) список фактических imports/dependencies и nested calls; (4) источник порядка; (5) negative trace, доказывающий отсутствие следующей зависимой стадии при отказе. Code review ищет доменные predicates, работу с storage/codec, ручные patch/header/dependency constructions и копирование child dispatch. Наличие любого из них в ноде — FAIL, даже при успешных тестах.

Node-тесты используют заданные owning результаты и проверяют передачу/число вызовов/trace. Пример A,B,A,C→indices(1,3) вычисляется в Time-тесте; node-тест получает готовый SettingsBatchInputMismatch и проверяет неизменность indices, не воспроизводит алгоритм. Аналогично no-op/history/retention/coverage проверяются владельцами и сквозной интеграцией, не становятся implementation predicates ноды.

### N0. Preflight и freeze

- Сверить текущие files/registrations: implemented Cache — пример одной operation boundary, legacy engine не SoT новой архитектуры.
- Сопоставить каждую строку карт с actual public signature и полным nested trace; зафиксировать existing/target/missing.
- Закрыть только gates выбранного следующего шага, предъявить конкретные node cards пользователю по GEN-NODE-JOINT-REVIEW. Не объявлять весь план PASS при отсутствующих G3/G5.
- Зафиксировать actual пути implementation/test modules до создания файлов. Не создавать параллельные каталоги на основе guessed layout.

DoD: per-node контрактная таблица и выбранный ограниченный scope приняты; изменения только документов до этого момента.

### N1. Leaf подготовки Lifecycle и Time clock

После G0/G1 и готовности соответствующего owning public method реализовать thin leaf/binding и reuse Input.request/Output.value. Девять Lifecycle mock node-классов размещаются по одному в файле в backend/tests/lifecycle/support/nodes/lifecycle/, регистрация отдельно в registration.py этой папки; POJO остаются в backend/tests/lifecycle/support/nodeContracts.py. Точные пути заданы реестром. Existing nodeBindings.py — исходное размещение для переноса, не целевой общий implementation файл. Существующие классы переносить без дублирования реализации и изменения NodeId.

Проверки: A/B mismatch, open generic/foreign subtype, duplicate NodeId, contract identity; exact success и все owning refusal; call count=1, no writes, неверный output остановлен engine. Проверить static Never и runtime exception отдельно. DoD: per-node diff/acceptance и typed wiring, не только созданные файлы. G2/G4 не prerequisite pure leaf.

### N2. Leaf настроек Time

После G3 и готовности owning APIs реализовать 8 single leaf, batch leaf и section leaf по одному публичному вызову. Последовательный batch алгоритм реализует Time в своём плане, здесь его не повторять. Batch success PreparedTimeSettingsChange неизменно передать section request.change вместе с общим operation_id/expected_world.

Проверки: все конкретные single outcomes; batch base mismatch A,B,A,C → indices(1,3), отказ execution сохраняет исходный command_index/reason; никаких вызовов producer после отказа. Domain budget/command semantics тестируются Time; node тест проверяет передачу и отсутствие повторного вызова. No-op не удаляется DAG. DoD: все I/O и errors соответствуют frozen G3, пер-нода приёмка.

### N3. Leaf сборки и применения

Связать assemble_patch_set с public assembler, apply_snapshot — с public Snapshot. На уровне CALL допускаются contract spies для проверки передачи, явно без объявления transactional evidence. Реальная интеграция требует G2/G6 для выбранного scenario.

Проверки: входные sections не фильтруются/сортируются, section.domain_evidence сохраняется; assembly refusal не запускает apply; exact result T, fault/unknown/cancel не стираются. Replay/storage тесты не имитировать fake committed ответом. DoD: per-node accepted mapping и distinct результаты contract-only vs real integration.

### N4. Оркестраторы снизу вверх

После G5 и готовности выбранных leaf: prepare_world_time_settings_changes → prepare_changes → write_changes. Это порядок поставки классов, не новый runtime порядок. Runtime остаётся prepare → assemble → apply. Parent CALL использует engine contract, не execute ребёнка.

Settings parent: single→один single leaf; multiple→один batch leaf. prepare_changes вызывает section producer только на success. Lifecycle ready transitions могут миновать pure prepare, но не section producer. Aggregate carries exact owning refusal с корреляцией исходного вызова; schema/mapping должны быть frozen в G5, не runtime string dispatch. Независимую параллельность не добавлять без принятого порядка.

Проверки: recorded CALL trace для каждого сценария; отказ на каждой границе запрещает все зависимые CALL; ни missing section, ни частичный batch не публикуются. DoD: accepted trace + actual nested calls audit без доменных вычислений в parents.

### N5. Сквозная приёмка выбранных сценариев

После готовности реальных участников соответствующего сценария:

1. mock_lifecycle_world: synthetic A/B, 100 независимых transitions; отдельно Replacement с множеством участников; mixed и all-equal retry, evidence mapping, wrong payload при valid hash.
2. Time clock сценарий по существующему IC-1.
3. Settings single, ordered batch и no-op; совместный settings+advance только после G4/G6. Это отдельный scenario binding, не молчаливое расширение Lifecycle mock или Time root.

Проверить actual manifest merge/closure/round-trip, local→composition refusal preservation, C2 immediate check до следующего handler, rollback/CAS/unknown/exact terminal replay без повторного apply. Spy tests N1–N4 не заменяют эти проверки. Runtime faults не требуют legacy compatibility или production producers.

DoD: scope каждого PASS указан, пройдены обязательные checks репозитория и тесты затронутых границ; полный граф не объявляется готовым при исключённой IN-ветви. Не запускать backend, не коммитить/пушить в рамках этого плана.

## 6. Данные, no-op и identities

Готовые Lifecycle результаты живут в typed outputs/коллекции текущего вызова DAG до section producer; service accumulator/staging DB для их временного хранения не вводится. Один native patch/историческая операция на переход, Replacement не дробится. Section evidence переносится целиком с исходными индексами.

Settings batch base: эталон commands[0].base после structural admission; сравнивается весь operation_id/capture/clock/budget, несовпадения i>=1 собираются upfront. Это Time-owned predicate, не доказательство принятого persisted state. No-op: changed=(), new settings version отсутствует; history=() предложено Time, exact states/retention на Snapshot сверке G4. Не подменять states пустым tuple по догадке.

Mock composition classes — tests/lifecycle/support/snapshotContracts.py; subject diagnostic POJO — domainSections.py, поведение — subjectMock.py. Local MockLifecycleSectionRefused и MockSubjectSectionRefused проверяются registry и переносятся в MockSectionRefused с сохранением types/paths/order. Runtime-only carriers/node wrappers не получают wire IDs без serialization consumer. Перед implementation проверить, не изменился ли owning freeze.

## 7. Матрица обязательной приёмки

| Критерий | Где проверяется | Текущий статус |
|---|---|---|
| Три запрета DAG, direct caller/nested trace | §§2,4; N0/N4 | Предписаны; actual evidence после кода |
| Ответственность каждого concrete класса | §4 и per-node owning карты | Частично: G3/G5 остаются OPEN |
| Input/Output/Error, POJO ownership без дубликатов | §§3–4, owning tables | Lifecycle конкретизирован; settings/aggregate transport OPEN |
| Неизменный порядок/эффекты | §2, N4/N5 | Основной порядок принят; settings dependencies G4 OPEN |
| CRUD данных/настроек и междоменные зависимости | §1, G4/G6 и owning ТЗ | План покрывает подготовку/запись; не заявляет полный CRUD доменов |
| Контрактная валидация и failure transport | §4, N1–N5 | Проверки заданы, runtime evidence отсутствует |
| Приёмка master+coordinator до кода новых нод | N0, G1/G3/G5 | По конкретной ноде, не автоматически из этого плана |

План создан, но общая реализационная приёмка OPEN. Закрытие одного gate снимает ограничение только с зависимых шагов. Следующее действие: завершить N0 на конкретизированных Lifecycle/Time clock leaf и параллельно в контрактной работе получить Snapshot G4 и freeze G3/G5; не обещать production готовность по mock evidence.
