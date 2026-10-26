# Общий lifecycle: замещение сущностей и сохранение истории

Статус 2026-10-20: отдельный план общего домена, реализации нет. SoT: [tz_entity_lifecycle.md](../../docs/tz_entity_lifecycle.md). Первый consumer: [hydrology-water-systems.md](hydrology-water-systems.md). Связи: [plan-dependency-graph.md](plan-dependency-graph.md).

## Целевая архитектура

POJO — `dataModel/lifecycle/`; pure consumer переходов — `application/lifecycle/`. Домен рассчитывает новые параметры; lifecycle проверяет замещение, новые UID, ссылки на предшественников и закрытие старых сущностей. Application writer атомарно сохраняет lifecycle и доменные параметры. История не удаляется. Генерация, геометрия и симуляция времени не входят в lifecycle.

Placement и HY-12 не являются входными зависимостями общего lifecycle. Он переиспользует существующие DET-1, runtime/worldEdit и persist infrastructure. Прецеденты is_active/ended_at не означают уже существующий универсальный механизм.

## Шаги

### L0 — инвентаризация общего механизма

Цель: проверить существующие lifecycle/history/result/persist контракты до новых типов.
ТЗ: lifecycle § Расположение и ответственность; § Инварианты; structural mutations §7.
Файлы: этот план; аудит `dataModel/`, `application/`, `db/models/`; код не меняется.
Контракт: карта прецедентов, ownership текущего состояния и истории, world/scope identity, revision, transaction и связи с snapshot/rollback. Миграция государств и cell_states — отдельные будущие срезы, не prerequisite воды.
Проверка: каждый переиспользуемый контракт подтверждён путём и caller; отсутствующие отмечены.
Done: отсутствуют дубли общего механизма под видом гидрологии.

### L1 — typed контракты и identity операции

Цель: довести проекты EntityLifecycle/LifecycleReplacement до проверяемого контракта.
ТЗ: lifecycle § Общий контракт и § Инварианты; DET-1.
Файлы: `docs/tz_entity_lifecycle.md`, `backend/app/dataModel/lifecycle/`; `backend/app/ids/` только при необходимости нового тега по инвентаризации.
Контракт: scope, change_uid, новые entity_uid, predecessor links, active/historical, результат; обязательная идемпотентность повторов и обнаружение разных payload одного change_uid. Сигнатуры фиксируются в ТЗ до consumer.
Проверка: POJO validation, ссылки/циклы, identity/retry, одинаковые runtime/preview facts.
Done: общий контракт пригоден для водных POJO без локальных lifecycle-полей.

**Принято 2026-10-21 — состояние не равно завершению lifecycle.** Пересыхание озера сохраняет его UID и lifecycle; наполнение продолжает тот же объект. Историзируются замещаемые системы, а не сохранившиеся участники. Восстановление прежнего состава после засухи создаёт новую систему, без реактивации исторической. `is_active` не служит wet/dry-флагом. Приёмка L2/L3 совместно с W2/W3: цепочка исходная система → засуха/изменение состава → восстановленная система; новые UID родителей и прямые predecessor links при сохранении identity участников, retry без дублей, атомарная история. SoT: `docs/tz_entity_lifecycle.md` § «Доменное состояние и существование сущности».

**Identity adapter HY-12/4 (2026-10-21):** общий `app/ids/waterSystemIdentity.py` уже задаёт water-system UID по world/change/member fingerprint/system kind. Логический bootstrap change детерминирован только для чистого первого bake/preview; identity runtime-операций и их durable retry/journal по-прежнему принадлежат L1/application caller. Dry/refill не используют bootstrap как новый event. Общий lifecycle POJO/consumer/writer этим не объявляется реализованным.

### L2 — общий consumer переходов

Цель: построить и проверить transition без persist.
ТЗ: lifecycle § Инварианты, контракт L1.
Файлы: `backend/app/application/lifecycle/`, профильные tests.
Контракт: актуальные записи + typed replacement → validated change set либо общий unresolved; ни удаления истории, ни доменной геометрии.
Проверка: merge, split, no-op/retry, cycle, foreign scope, stale input, conflicting operation; отсутствие мутаций при ошибке.
Done: consumer готов к первому domain adapter; storage не объявляется реализованным.

### L3 — общий write boundary и первый consumer

Цель: обеспечить атомарное сохранение lifecycle вместе с доменными параметрами.
ТЗ: lifecycle § Инварианты; гидрология § Контракты домена динамических водных систем.
Файлы: application writer/repository boundary по L0; водный adapter из W3; SQL только `0001_initial.sql` + db models, если storage-решение требует schema.
Контракт: revision и operation identity проверяются одной транзакцией; новые записи и историзация старых коммитятся вместе. Доменный payload не помещается в общий POJO произвольным dict.
Проверка: temporary storage, rollback/failure injection, fresh read истории, повтор операции, stale revision.
Done: W3 подтверждает интеграцию первого consumer. Полная миграция старых доменов не входит в Done.

L3 интегрируется с W3 после независимой подготовки L2 и W2; это одна общая точка приёмки, не цикл prerequisites. Не запускать backend, не менять DAG, не коммитить.
