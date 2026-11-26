# Передача Artifacts prepare → stage без потери object identity

Статус: направление решения выбрано пользователем; детализация OPEN, 2026-11-26. Пользователь выбрал вариант 2: восстановить результат prepare один раз и сформировать зависимый вход stage из него, «главное без обходных путей». Выбор не требует повторного согласования. Полная приёмка плана и поручение реализации этим статусом не заявляются.

## 1. Задача и основания

Сохранить исходный content и PreparedArtifact на непрерывном зарегистрированном маршруте prepare → stage при полноценной validation. Передача через JSON создаёт новые экземпляры и нарушает принятый is-контракт.

Источники:
- [Решение об откате Engine](../../docs/artifacts-dag-identity-bug-2026-11-25.md), верхний раздел от 2026-11-26: owning исправления Artifacts сохранены; identity_required/live transport и второй lifecycle откачены.
- [Контракт нод Artifacts](gen-dag-artifacts-node-contracts.md), §§2–4, 6 и P1: public methods, POJO, неизменный Error, exact registered route; restart/durable replay не обещает Python identity.
- [Координация](../rules/interdomain-contract-coordination.mdc) и [обязательная приёмка](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена).

Фактические точки: InvocationCoordinator.encode/view/event и DAGExecutor._invocation_step используют JSON для активной передачи; InvocationRecord.input/terminal — строки. DAGContext уже хранит типизированные OutputRecord. Наличие этого каталога не доказывает его пригодность для всех вложенных invocation: это проверяется первым шагом.

## 2. Предлагаемая граница решения

В активном выполнении должен быть один основной набор типизированных данных invocation. CALL, возврат результата и dependency read используют принятые объекты из него. Checkpoint — сериализованное представление для сохранения и восстановления; создание checkpoint не заменяет активные объекты результатом decode.

Требование распространяется на весь путь content → prepare input → public prepare → output → CALL outcome/read → stage input → public stage после admission. Output.value передаётся непосредственно в owning поле prepared; нода не извлекает и не пересобирает доменные поля. Owning Error переносится целиком. Порядок операций и ошибки остаются заданными owning контрактом.

Не вводить параллельный live-cache, object registry, токены, identity_required, отдельный executor или второй worker/claim/renew/drain/release loop. Не обходить validation, не менять is на equality и не выбирать BLOB вместо model payload для прохождения теста. Изменение представления данных не разрешает переставлять checkpoint/CAS и побочные эффекты.

## 3. Последовательность работ

### A. Закрыть точный контракт и границы классов — до кода

Проследить public DAGEngine.run → admission → existing recovery owner → execution → CALL → parent outcome → следующий CALL. Отдельно сверить root input, prior-phase binding, dependency reads, retries, replan и повторные invocation одного NodeId. Зафиксировать ключ результата с invocation/attempt identity и срок его доступности.

Выбрать одно основное runtime-представление: доказать возможность использовать существующий каталог либо определить минимальную замену строковых payload активного invocation. Приложить exact типы, модули, методы, Input/Output/Error и mapping в существующий wire checkpoint. Не добавлять ещё один каталог с синхронизацией. До этого выбора перечень изменений ниже является картой проверки, а не разрешением редактировать все файлы.

| Класс / группа | Ответственность и критерий приёмки | Основание отказа |
|---|---|---|
| InvocationRecord / InvocationGraph | Данные invocation и принятые переходы состояния; определить runtime/wire границу | Два независимо изменяемых payload одного результата; IO или orchestration в POJO |
| DAGContext / OutputRecord / CatalogSnapshot / PublishedDAGReadView | Каталог, provenance и разрешённое чтение; проверить адресацию вложенных invocation | Коллизия по NodeId, выдача устаревшей attempt, дублирование каталога |
| InvocationCoordinator | CALL bindings и outcomes из основного runtime-состояния | JSON reconstruction при живой передаче; управление claim/worker |
| DAGExecutor | Запуск нод в существующем порядке через зарегистрированный контракт | Альтернативный executor, обход admission или durable start CAS |
| ContractValidator / NodeRunner | Полная проверка зарегистрированных POJO и запуск | model_construct, ослабление rejection или клонирование protected payload |
| CheckpointCodec / SessionFrame | Encode/decode persistence-представления | Decode для обычной активной передачи либо мутация живого результата при encode |
| OwnedExecution | Существующие checkpoint/CAS и взаимодействие с владением | Новый источник payload или изменение fencing ради identity |
| ExecutionAdmission / ExecutionRecovery / PassExecution | Существующие admission, recovery ownership и pass lifecycle | Второй ownership loop; неоговорённые запреты resume/replan |
| Prepare/Stage wrappers и ноды | Один public owning call, mapping результата/ошибки | Доменные проверки, внутренние storage операции или скрытый вызов соседней ноды |

Для каждого реально затронутого класса раскрыть точный модуль, зависимости, вложенные calls и тестовый критерий; перечисленные группы развернуть в окончательной дельте. Неизменяемые классы отметить как проверенные зависимости.

### B. Детализировать выбранное восстановление — вариант 2

Принятое направление: после восстановления результат успешного prepare декодируется и полностью валидируется один раз для соответствующей invocation/attempt. Он становится основным объектом результата в восстановленном выполнении. CALL outcome, dependency read и поле prepared зависимого stage используют этот экземпляр через явный Output → Input mapping.

Identity относительно завершившегося процесса не обещается. В восстановленном выполнении контрольный экземпляр — восстановленный результат prepare; stage.prepared is restored_prepare.value и stage.prepared.content is restored_prepare.value.content обязательны после всех admission. Это явная граница lifetime, а не замена is проверкой equality внутри выполнения. В непрерывном fresh run остаётся полная цепочка original content из P1.

Зависимое поле prepared не восстанавливается независимо из копии сохранённого stage input. В A определить точное описание и сохранение существующей связи producer invocation/attempt → output.value → consumer input.prepared. Это связь DAG, не токен Python-объекта и не object registry. Нельзя находить объект сравнением значений, дедупликацией по hash, interning или особым условием для класса PreparedArtifact. Сопоставление выполняется штатным механизмом DAG; прочие поля stage input, включая lease, сохраняют своих производителей и validation.

Успешный prepare ради identity повторно не запускается. Восстановление mapping не исполняет произвольный parent заново и не повторяет его эффекты. Для уже начатого stage продолжение/повтор определяется существующим owning replay-контрактом и durable статусом; восстановление ссылки само по себе не разрешает новую запись. До кода предъявить таблицу actual состояний: prepare завершён/stage не запущен; stage запущен с неизвестным исходом; stage завершён; cancellation/owner loss. Terminal replay не вызывает ноды повторно.

Детализировать retry/replan и недоступный, устаревший или несовместимый producer result: проверка invocation/attempt/contract до consumer CALL, typed outcome через существующую границу ошибок. Обычные маршруты сохраняют принятые гарантии. Формат mapping, точные API и исходы остаются частью A/B; общий запрет resume, второй lifecycle или скрытый fallback не допускаются.

### C. Реализовать согласованную минимальную дельту

После A/B и пользовательской приёмки выполнить отдельное поручение реализации через implement-plan. Изменить runtime/checkpoint mapping только в принятом перечне файлов; сохранить единственный lifecycle и существующий порядок CAS/checkpoint/CALL. Owning Artifacts identity/P2 исправления повторно не переделывать.

### D. Проверить реальный маршрут

- Через public DAGEngine.run и registered prepare/stage проверить is original для runtime-created bytes и frozen model с revalidate_instances=always на всех звеньях P1, включая аргумент stage после admission.
- Использовать явно названные test-only binding/fixtures в tests/support; никакого app → tests. Storage stub допустим только на storage boundary. Test route не объявлять production activation.
- Проверить rejection wrong/mutable/forged payload и unchanged typed Error с правильными P2 paths.
- Восстановить checkpoint после prepare до stage через публичный маршрут: prepare не вызван повторно, stage получает ровно восстановленный producer object после admission; повторные reads/outcomes возвращают тот же payload. Тест должен обнаруживать независимое decode stage.prepared и подмену equality вместо is.
- Проверить сохранённый mapping для нескольких invocation одного NodeId и разных attempts; несовместимая или отсутствующая связь не допускает consumer CALL. Объекты разных invocation не объединяются по равным значениям.
- Проверить согласованные в B restore/replay, cancellation, owner loss, retry/replan; отсутствие следующего CALL/effects после остановки и устаревших payload после новой attempt.
- Прогнать existing test_world_calls и Artifacts test_content_identity + contracts.test_registry. Добавлять другие проверки только по затронутым гарантиям. PASS тестов не заменяет проверку ответственности.

## 4. Приёмка и оставшиеся решения

Три запрета DAG обязательны: ветвление и запуск остаются в DAG, public domain operation вызывается непосредственно нодой, домены не вызывают друг друга. Leaf выполняет один public call; parent оркестрирует. Production concrete C/binding, manifest IDs и порядок нового маршрута этим планом не назначаются.

Порядок исполнения сверяется с согласованным Artifacts контрактом и существующими start CAS / checkpoint / ownership переходами; до предъявления полной трассы A — OPEN. CRUD доменных данных/настроек не расширяется; существующий ExecutionStore контракт проверяется как зависимость. Если потребуется его изменение, нужен отдельный точный пакет CRUD-контракта до кода. Анализ всех затронутых POJO, field/logic errors и отсутствия дублирования завершается в A.

Текущие OPEN: единое runtime-представление и exact API; конкретный mapping и таблица восстановления начатого stage по выбранному варианту 2; полный inventory классов/POJO и вызовов; сверка общей цепочки назначенным координатором и приёмка конкретной дельты пользователем. Выбор варианта 2 закрыт. Правило по-прежнему назначает чат 01a1ef35-3287-7a12-89e2-76273eaa043d; этот документ назначение не меняет. Без закрытия OPEN план не принят к реализации.

Вне объёма: generator/gameplay, domain storage/authority/transaction design, новая архитектура всего Engine, объединение prepare/stage, изменения других семейств нод и production activation.
