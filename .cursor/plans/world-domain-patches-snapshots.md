# Доменное чтение, patches и snapshots — новый архитектурный план

Статус: ARCHITECTURE / ДЛЯ ПРИЁМКИ, 2026-10-27.
План фиксирует решения мастера и детали для дальнейшего согласования.
Код, конкретные реализации и DAG wiring этим документом не разрешены.
Заменяет [архивный WS](world-state-crud-transition.md), а не продолжает его
central CRUD/class map и последовательность WS-1…WS-5.

## 0. Базовая политика runtime/worldEdit

SoT: [`docs/tz_runtime_world_edit_policy.md`](../../docs/tz_runtime_world_edit_policy.md).

- Один доменный resolver для import/runtime и worldEdit; patches и snapshot
  не вводят своего policy engine, отдельного worldEdit mode/endpoint/pipeline.
- `validate_only=true` — тот же DAG pipeline без публикации pack, commit
  Snapshot и staging, меняющего мир; не write с rollback.
- Правка мира мастером после старта gameplay — patch в snapshot тем же
  pipeline (`docs/tz_world_snapshot.md` § «Staged artifacts и точки публикации»).
- Неразрешимый результат — WarningError через доменный log sink, без default
  вместо ошибки и без ложного успеха; worldEdit получает ту же диагностику.
- Consumers, unresolved-результат, reason/action и проверки двух режимов
  фиксируются в доменных пунктах плана при приёмке.

## 1. Общая архитектура — главное и критическое требование

**Каждый пункт плана, контракт и будущая реализация обязаны соответствовать
этой архитектуре. Нарушение границ ответственности блокирует реализацию
и приёмку шага. Сначала согласуется архитектура, затем определяются
конкретные типы, классы, файлы и реализации.**

Каждый архитектурный пункт принимается мастером отдельно. Для приёмки нужны
определённая ответственность, границы контракта, поведение и проверяемый
результат; перечня классов/папок или общего согласия с направлением недостаточно.
Уточнение требования к пункту не означает приёмку его ещё не описанной архитектуры.

**Критическая проверка каждого класса Patch:** при изменении доменного CRUD
и сохранении публичного контракта модификации Patch совершенно не меняется.
CRUD принадлежит домену; Patch используется для описания модификации.
Проверка обязательна для каждого класса, а не только для базового интерфейса
или одной представительной реализации. Непроверенный класс не принимается.
Если проверка не проходит, это проблема реализации и нарушение критического
архитектурного требования. До устранения дефекта не принимаются затронутый
класс, шаг и план целиком; остальные успешные проверки этот отказ не перекрывают.

**Критический запрет обхода Snapshot:** Patch не записывает мутацию напрямую
в БД или опубликованное состояние, в том числе через вызов существующего
CRUD writer, repository, callback или вложенного сервиса. Подготовка и кэш
не должны изменять authoritative state. Физическая запись доменной реализацией
допустима только как делегированный этап применения, которым владеет Snapshot,
без самостоятельного commit. Схема «сначала CRUD сохранил, потом Snapshot
записал историю» нарушает этот gate; version stamp сам по себе её не исправляет.

**Критический запрет оркестрации в Snapshot (мастер, 2026-10-27):**
Snapshot применяет и сохраняет только уже подготовленные изменения.
Применение не является вызовом materialization. Snapshot не инициирует
planning, materialization, bake/refine или достроение отсутствующего
результата — ни напрямую, ни через domain apply/storage, callback или
вложенный сервис. Если Snapshot начинает materialization сам, это перенос
оркестрации из DAG и критический баг. Отсутствующий или несовместимый
подготовленный результат даёт явный отказ; Snapshot не достраивает его.

**Критический запрет самостоятельного сохранения доменом:** домен
подготавливает типизированный результат и patch по внешнему вызову, но
не инициирует сохранение patch, его истории или описанного им изменения.
Домен сам сохраняет patch — критический баг. Доменная реализация записи
SQL/pack вызывается только Snapshot при применении подготовленного набора;
владение реализацией хранения не даёт домену права инициировать запись.
Временное удержание результата в patch/PatchSet не является сохранением
patch в authoritative storage и не обходит это ограничение.

**Неизменяемое добавляемое состояние (мастер, 2026-10-27):** изменение
SQL-данных состояния создаёт новые записи/версии, изменение pack — новые
immutable артефакты. Существующие исторические записи и pack не
перезаписываются. Delete доменного объекта отражается новым историческим
изменением/маркером удаления, а не физическим удалением прежнего состояния.
Patch хранит историчность перехода для SQL и pack; Snapshot оборачивает
набор patches и единственный применяет его как согласованное состояние.
Конкретные format/storage/commit механизмы ещё требуют приёмки.

```text
DAG → domain.read(query) → типизированный доменный результат
DAG → domain.patch(change) → подготовленный patch без изменения состояния
DAG / debug API → PatchSet → Snapshot → применение и сохранение состояния/истории
```

Контракт чтения принадлежит соответствующему домену. DAG вызывает его
реализацию напрямую. WS не задаёт domain read contracts, не оборачивает
и не маршрутизирует вызовы. Центральный WorldStateService/IWorldStateRead
и обязательный WS-посредник в read/patch цепочке исключены.
Прямой доступ WS к БД запрещён, в том числе через WS storage adapters,
DB-bound context или собственный SQL UOW.

Домен владеет своими данными, контрактами read/patch, правилами изменения,
валидацией и доменной реализацией поведения patch. Подготовка patch не
изменяет сохраняемое состояние. **Применяет patches только Snapshot**:
он вызывает доменную реализацию поведения в своём lifecycle применения.
Доменные правила остаются у домена; самостоятельного входа apply/persist
для DAG/debug API или домена нет. DB/file IO остаётся за storage-портами.

Generator получает подготовленные inputs/актуальный план и возвращает
доменный результат. Он не читает WS/БД, не формирует patches, не собирает
PatchSet, не сохраняет состояние или историю.

Только DAG и debug API собирают доменные patches в PatchSet и передают его
Snapshot. Snapshot — единственный владелец применения набора, сохранения
результирующего состояния и общей истории операций. Отдельный общий patcher
как самостоятельный вход применения исключён. Доменные алгоритмы, сбор
набора и запуск materialization не переносятся в Snapshot.

GEN DAG обязателен: production вызывается через DAG; debug API — тонкий
инструмент разработчика, вызывающий тот же граф DAG (своего порядка стадий
не держит). Product
CRUD/import нельзя объявить debug-входом для обхода этой границы.
Существующий Gate: DAG G1–G5 не снимается.
Конкретный связанный **план**, а не только ТЗ —
[GEN-DAG-1](gen-dag-1-post-geo-ws.md). Межстадийное управление (выбор,
порядок, зависимости, scope, planning/materialization) принадлежит DAG.
CRUD и его реализация принадлежат генераторному домену. Patch не заменяет
CRUD и не получает спрятанный pipeline через validate/build_result или
вложенный сервис. Внутренние вычисления одной атомарной доменной операции
допустимы; обёртка над несколькими независимыми стадиями — нет.

## 2. Ответственности и потоки

`read`/`patch` ниже — архитектурные операции, не утверждённые Python signatures.

| Владелец | Ответственность |
|---|---|
| DAG | Когда вызвать read/изменение/materialization; порядок доменных операций; сбор PatchSet |
| Debug API | Тонкий developer entry: вызывает тот же граф DAG; своего порядка стадий/сбора не держит |
| Domain read | Данные и domain-owned результаты, missing/fallback/merged/raw semantics; обращение к своей инфраструктуре |
| Domain change/planning | Реализация write-free create/update/delete: смысл изменения, validation, подготовленный typed результат, зависимости и invalidation; запуск по вызову DAG/debug |
| Domain patch | Подготовка typed patch без изменения состояния; реализация доменного поведения, вызываемая только Snapshot при применении |
| Generator/materializer | Pure compute из актуальных prepared inputs; domain output для последующего сохранения |
| Snapshot lifecycle | Единственный владелец применения PatchSet; сохранение результирующего состояния и общей истории; immutable identity/lineage |
| Domain storage | Реализация записи своих SQL/pack данных; запускается только Snapshot при применении подготовленного результата |
| Snapshot storage | Собственное хранение общей snapshot metadata/истории за storage-портом; не реализует SQL/pack запись доменов |

Read не запускает generate/refine. Изменение metadata/planning само по себе
не запускает materialization. Домен определяет актуальность/инвалидацию
зависимых представлений; materialization — отдельный явный запрос.
Snapshot save сохраняет уже имеющиеся результаты, не достраивает мир.

Поток planning/materialization до Snapshot:

```text
DAG → domain planning → prepared typed plan/revision → Patch / PatchSet (кэш)
DAG → domain materialization(готовый plan/revision, scope, LOD) [только по запросу]
    → prepared typed materialization → Patch / PatchSet (кэш)
DAG → Snapshot.apply(подготовленный PatchSet)
    → domain storage по вызову Snapshot → новые версии SQL/pack и история
```

DAG фиксирует порядок и зависимости вызовов; план строит домен. Patch
захватывает результат planning, его inputs/dependencies/revisions и
исторический переход, а не исполняемые стадии. Materialization является
отдельной доменной операцией из готового плана; её результат подготавливается
для последующего сохранения. Snapshot может сохранить metadata/planning
без materialization. Добавление представления другого scope/LOD само по
себе не требует новой semantic revision исходного плана.

Владелец применения закреплён: только Snapshot. Точный atomicity/commit
protocol согласуется в §7. Prepared patch нельзя объявить уже применённым,
а запись отдельного домена — атомарным commit всего набора/хода.

### 2.1. Две фазы: домен владеет реализацией, но не инициирует их

Согласовано мастером: **домен реализует подготовку модификации и физическое
сохранение своих данных в SQL/pack. Самостоятельно фазы не инициирует и
не переключает.** Domain CRUD и storage logic не переносятся в Patch,
Snapshot или DAG.

| Фаза | Кто инициирует | Что реализует домен | Результат |
|---|---|---|---|
| Подготовка | DAG / debug API по публичному domain CRUD контракту | Read/validation и расчёт create/update/delete в рамках выбранной операции, без записи состояния | Typed prepared domain result или явный отказ/конфликт |
| Применение/сохранение | Только Snapshot при применении PatchSet | Проверка применимости и добавление подготовленных SQL-версий/pack-артефактов через свой storage контракт | Typed результат записи и references для согласованного состояния/истории |

Create подготавливает новый объект с предусловием отсутствия; update —
переход от исходной версии; delete — историческое логическое удаление.
Конкретные request/result типы принадлежат домену и семантике операции.
Подготовка не вызывает запись автоматически; доменная запись не вызывает
свою подготовку повторно, не запускает соседние стадии и не коммитит весь
PatchSet самостоятельно. Конкретный commit/publication protocol ещё открыт.

```text
DAG/debug → domain CRUD preparation → prepared domain result
         → domain Patch → PatchSet (возможен временный кэш)
         → Snapshot → domain storage implementation → SQL/pack новые версии
                    → согласованное состояние и общая история
```

Patch принимает подготовленный typed результат и описывает его исторический
переход. Он не вызывает изменяющий CRUD повторно и не содержит repository,
writer callback/SQL-команду или самостоятельный commit. Snapshot вызывает
доменные контракты применения/записи, но не воспроизводит mapping, SQL,
pack layout или бизнес-логику домена. Реализация хранения остаётся целиком
у владельца домена; Snapshot владеет моментом её вызова и согласованностью
набора. Собственная snapshot history storage отделена от domain persistence.

Критическая приёмка для каждого Patch/пути: подготовка без изменений SQL/pack;
запись инициирована Snapshot и делегирована домену; отсутствуют автоматический
переход между фазами, самостоятельный commit и повтор бизнес-операции.

Для каждого класса Patch и каждого пути Snapshot обязательна также проверка
всей вложенной цепочки вызовов:

- planning-only набор сохраняется без единого вызова materializer/bake/refine;
- набор с готовой materialization сохраняет переданный результат без её
  повторного вычисления;
- отсутствующий, stale или несовместимый обязательный результат вызывает
  явный отказ, без planning/materialization fallback внутри Snapshot;
- domain preparation и создание/кэширование patch не сохраняют patch,
  историю или состояние и не вызывают применение самостоятельно;
- domain storage вызывается только в lifecycle применения, инициированном
  Snapshot; домен не инициирует сохранение patch или commit набора.

Прямое или косвенное нарушение любого пункта — критический баг реализации;
приёмка класса, соответствующего шага и плана целиком блокируется до
исправления и повторной проверки. Отложить нарушение как технический долг
или скрыть его внутри доменного сервиса нельзя.

## 3. Patch и PatchSet по доменам

**Общий интерфейс Patch определяет поведенческий контракт изменения,
который домены обязаны реализовать. Одной оболочки с domain/target/payload
недостаточно.** Интерфейс фиксирует общие обязанности, семантику вызовов и
результатов; домены реализуют их для своих данных и правил.
Target, доменные операции и payload принадлежат владельцу домена.
Данные patch immutable и typed; это не SQL-строка, DB row или raw dict.

### 3.1. Общие вопросы поведения Patch

Приёмка интерфейса требует явного контракта по каждому вопросу ниже.
Точные Python signatures и concrete storage implementations определяются
после архитектуры; поведенческие обязанности не откладываются на этот этап.

| Общий вопрос | Что обязан определить интерфейс / реализовать домен |
|---|---|
| Что изменяется? | Адресат, вид изменения metadata/planning/materialization и затронутый scope; домен сообщает свои данные в согласованной форме |
| К какому состоянию применимо? | Как задаются и проверяются предусловия/ревизии; домен проверяет своё состояние, конфликт выражается явным результатом |
| Как проверяется допустимость? | Граница validation и её side effects; домен проверяет свои правила и возвращает диагностику по общему контракту |
| Кто и когда применяет изменение? | Только Snapshot инициирует применение; подготовка доменом не пишет состояние, доменная реализация выполняется внутри snapshot lifecycle; commit outcome определяется общим протоколом |
| Что возвращает применение? | Общие категории результатов и их смысл: изменение, отсутствие изменения, отказ/конфликт; доменный payload и effects сохраняются в typed результате |
| Что происходит при отказе/ошибке? | Какие отказы ожидаемы, как передаётся ошибка, что происходит с уже выполненными effects; домен соблюдает согласованную границу атомарности |
| Что означает повторное применение? | Как определяется повтор/идентичность операции и результат retry; домен реализует согласованную политику без скрытого повторного изменения |
| Каковы зависимости и последствия? | Как сообщаются порядок/зависимости и последствия для planning/materialization; домен определяет содержимое effects, общий механизм не угадывает их |
| Что передаётся snapshot? | Как операция, результат, версии и соответствующие данные/ссылки представляются для общей истории; домен предоставляет свою секцию |

Конкретные политики по этим вопросам ещё требуют проработки и приёмки.
Таблица задаёт обязательный охват интерфейса, а не утверждает существование
idempotency/rollback/conflict механизмов. Общие гарантии обязательны всем
доменам; доменная реализация не меняет смысл общего результата молча.
Неприменимое поведение отражается явно в согласованном контракте.
Общий интерфейс не получает DB API, не интерпретирует доменный payload и
не определяет domain read. Сбор PatchSet остаётся у DAG/debug API.

Типизация конкретного Patch должна связывать домен, конкретную семантику
модификации, target, inputs, change и result. Интерфейс требует такую
декларацию от каждой реализации. Одного domain tag или пары произвольных
generic inputs/result недостаточно; разные операции внутри одного домена
не становятся взаимозаменяемыми. Существующие domain POJO переиспользуются.
Имена CRUD-методов, их аргументы, DB rows и количество физических записей
не определяют типы/формат Patch.

### 3.2. Набор patches

```text
PatchSet
└── sections
    ├── terrain   → terrain patches
    ├── climate   → climate patches
    ├── regions   → region patches
    └── locations → location patches
```

Домены в примере не исчерпывают всю систему. Набор секционирован, не плоский
универсальный payload. Snapshot вызывает domain implementation, не разбирая
чужие доменные поля и не воспроизводя их алгоритмы.
Порядок patches внутри секции определяет домен; междоменные зависимости
и порядок секций задаются явно. Самостоятельной сортировки, hidden retries
или частичных успешных commit общего набора по умолчанию нет.

Patch может описывать сохранение metadata/planning либо результата
materialization. Эти виды изменения различимы в контракте домена;
их нельзя свести к generic upsert клетки или целой DB row.

### 3.3. Временный кэш результатов в PatchSet

Решение мастера: PatchSet может временно кэшировать подготовленные доменные
результаты, включая metadata/planning и результат materialization, для
дальнейшей передачи в Snapshot. Кэш не применяет patches и не изменяет
зафиксированное состояние. **Применение выполняет только Snapshot.**

Результат в кэше связан со своим patch, доменом и исходными inputs/revisions;
его нельзя подменить результатом для другого изменения. Наличие результата
не означает applied/committed outcome. PatchSet — временный носитель до
передачи; authoritative состояние и история фиксируются Snapshot.

При архитектурной приёмке определить ownership/lifetime кэша, передачу данных
или ссылок, проверку соответствия patch, поведение при отказе/повторе и
освобождение ресурсов. Само разрешение кэша не задаёт durable storage,
resume после restart или необходимость включать transient cache в snapshot format.

### 3.4. Независимость от CRUD — приёмка каждого класса Patch

Для **каждого конкретного класса Patch** в implementation map должны быть
указаны его domain/семантика, публичный контракт модификации, связанные типы
и отдельный сценарий проверки независимости от CRUD.

Проверка выполняется так:

1. Зафиксировать класс Patch, его типы/сериализованный формат и публичный
   контракт доменной модификации, используемый при snapshot apply.
2. Заменить реализацию доменного CRUD с сохранением этого контракта:
   например, изменить storage backend, внутренние методы, batching или
   разложение модификации на физические записи. Сопоставление с новым CRUD
   меняется внутри реализации домена.
3. Применить тот же Patch через Snapshot с прежними публичными входами.
   Проверить наблюдаемую семантику изменения, результаты и отказы по
   согласованному контракту, а не совпадение внутренних CRUD-вызовов.
4. Подтвердить отсутствие изменений кода класса Patch, его декларации типов,
   payload, format version и bindings PatchSet/Snapshot. Для такой замены
   не требуется миграция уже подготовленных/сериализованных patches.

Если изменение CRUD требует правки Patch при сохранённом публичном контракте,
граница ответственности нарушена: класс не принимается до устранения связи.
Это дефект реализации, блокирующий приёмку всего плана. Нельзя закрыть план
с таким дефектом, перенести его в отложенный долг или ослабить проверку ради
приёмки. После исправления проверку затронутого класса выполняют повторно.
Нетипизированный CRUD callback/имя метода в payload не считается развязкой.
Изменение самой семантики публичного контракта — другой случай, требующий
отдельного versioning/compatibility решения; им нельзя оправдывать CRUD coupling.

Evidence должно адресовать каждый класс по имени и сценарию. Общий
contract-test допустим как переиспользуемый механизм, но он должен быть
исполнен для каждого класса; один smoke на домен не заменяет эту проверку.
При этом прослеживается фактическая цепочка вложенных вызовов класса:
типизация и functional pass не оправдывают скрытую межстадийную оркестрацию.
Это дополняет независимость от CRUD; per-node приёмка GEN-DAG-1 остаётся
отдельным обязательным gate будущей DAG-интеграции и этим аудитом не закрывается.
Классы/тесты ещё не созданы: это обязательная будущая приёмка, не выполненный test.

### 3.5. Историчность patch для SQL и pack

Patch должен описывать типизированный исторический переход: identity
изменяемого объекта/части состояния, исходную версию/отсутствие, доменную
модификацию и новую версию/результат. Для materialization сохраняются
удерживаемые ссылки на соответствующие immutable pack-артефакты и их
dependencies. Наличие SQL-данных и pack — разные storage representations
одной истории, а не два независимых механизма изменений.

История должна сохранять различие create/update/delete, исходного отсутствия
и удаления. Полные before/after bodies либо ссылки на удерживаемые версии
выбираются после архитектуры; одной ссылки на mutable latest недостаточно.
Старая версия должна оставаться доступной для выбранного snapshot.

Это требование к данным patch, не право patch писать историю самостоятельно.
PatchSet может держать подготовленные результаты в кэше. Snapshot принимает
набор, проверяет применимость и через storage-контракты добавляет новые SQL
версии/pack-артефакты и фиксирует их совместное состояние/историю. Старый
snapshot и его данные остаются неизменными. Хранение immutable ссылок не
означает обязательного копирования всего pack для каждой операции.

Приёмка каждого класса Patch включает сохранность прежнего SQL/pack
состояния после изменения и наличие достаточной истории перехода.
Прямые UPDATE/DELETE старого состояния, in-place pack rewrite или история,
ссылающаяся только на latest, блокируют приёмку. Возможный отдельный prune/GC
не является доменным delete; его политика хранения согласуется отдельно и
не даёт мутации права потерять удерживаемую историю.

## 4. Snapshot по доменам

```text
Snapshot
├── общие metadata: identity, parent, привязка к операции/ходу, format version
├── состояние по доменам
│   └── <domain>
│       ├── metadata / данные планирования
│       └── имеющаяся materialization или удерживаемые ссылки на неё
└── PatchSet
    └── patch-операции по доменам, приведшие к этому состоянию
```

Это логическая структура; физическое хранение пока не выбрано.
Единая snapshot-история секционирована по доменам; самостоятельные terrain/
climate/region snapshot stores не вводятся. Existing world/player chains
сохраняют свою отдельную предметную семантику; секция домена не новая timeline.

Домен определяет формат и подготовку/восстановление своей секции.
Snapshot lifecycle сохраняет общую структуру и историю через storage ports.
Он же единственный применяет переданный PatchSet; DAG/debug/domain preparation
не изменяют состояние до этого. Применение создаёт результирующее состояние,
а не переписывает уже зафиксированный snapshot.
Snapshot immutable; изменение создаёт последующее состояние/ветку.
Журнал patches не заменяет authoritative данные состояния при restore:
восстановление не требует неоговорённого replay всей истории.

## 5. Структура исходников по ответственности

Пути ниже — целевая композиция namespaces, не список файлов к созданию.
`<domain>` сопоставляется существующим доменам после inventory, без
дублирования их моделей. Exact class/method/file map — после архитектуры.

```text
backend/app/
├── dataModel/
│   ├── patch/                  общий контракт Patch/PatchSet
│   ├── worldSnapshot/          identity, manifest, domain sections
│   ├── sourceVersioning/       existing design: identity/revision contracts
│   └── <domain>/
│       ├── patch/              доменные изменения
│       └── snapshot/           данные доменной секции
└── application/
    ├── worldSnapshot/          применение PatchSet, состояние и общая история
    └── <domain>/
        ├── read/               доменное чтение
        ├── patch/              подготовка и поведение patch для вызова Snapshot
        └── snapshot/           подготовка/восстановление своей секции
```

Read contract принадлежит dataModel/application ports своего домена,
реализация — application домена. Общего WS read namespace нет.
Storage implementations размещаются по своим существующим слоям, не
переносятся в application только ради приведённого дерева.
Snapshot domain payload не зависит от concrete snapshot storage.

## 6. Версионирование — переиспользование source versioning

Основа — [world-source-versioning](world-source-versioning.md), согласованный
design 2026-10-24. Его реализация ещё не готова; наличие плана не считается
работающим revision store/capture/publication. Второй механизм не вводится.

| Понятие | Роль |
|---|---|
| SourceObjectId | Existing design identity `(scope, container, key)`; стабильная identity объекта |
| SourceRevision | Existing design `seq + content_hash`; семантическое состояние source-объекта |
| Авторский version label | Метка в теле, не identity и не замена revision |
| Planning fingerprint | Фактические effective inputs алгоритма, версии схемы/алгоритма и зависимости планов |
| Snapshot identity/parent | Узел immutable истории и его lineage; не версия source-объекта |
| Patch/Snapshot format version | Совместимость формата сериализации; отдельно от semantic revision |

Обязательное переиспользование:

- В phase 0 черновые правки сохраняют правила source versioning: revision
  accounting ещё не вводится, но прежнее разрешение свободных SQL UPDATE
  не переносится в новый append-only state contract. Представление черновой
  истории требует согласования. В phase 1 семантическое изменение source
  создаёт новую revision независимо от in-flight. Label-only change не
  означает новую semantic revision; новая identity на каждую версию не создаётся.
- Snapshot закрепляет source revision set и удерживает нужные тела.
  Историческое чтение разрешает ссылки as-of/pinned, не по master latest.
  Player accepted set не подменяется latest мастера.
- Capture закрепляет значения и состав коллекций. Операция не переходит
  на latest посередине compute. Snapshot/artifact — долговечный holder;
  GC не удаляет удерживаемые ревизии/материализацию.
- Source revision и planning fingerprint различаются: нерелевантная для
  алгоритма правка не заставляет перестраивать план автоматически.
- Materialization сохраняет dependency stamps частей/планов. Сохранение
  производного результата само по себе не новая semantic source revision.
- Source mutation использует единую source-versioning boundary/ref-integrity
  через владельца домена. Snapshot/PatchSet не подменяют эту проверку.
- Не каждый runtime patch является source mutation: applicability revision
  checks и отражение runtime state задаются доменным контрактом. Общая
  source-versioning схема не объявляется готовой моделью всех runtime-состояний.

Конкретные patch preconditions, stamps и snapshot revision-set binding
согласуются до реализации. Правила capture-finalize, publication, CAS и
retention переиспользуются по смыслу с проверкой совместимости. Прежний
протокол изменения SQL pointer/latest через UPDATE требует пересмотра под
append-only commit; он не является утверждённым механизмом нового плана.
Snapshot должен закрепить согласованный набор SQL/pack версий без перезаписи
старого состояния. Concurrency/head: один CAS-указатель мира `(pack_hash, snapshot_head)`
(решение B-3, `docs/tz_world_snapshot.md` п. 8).
Одного SQL BEGIN для атомарности SQL+files недостаточно.

## 7. Что ещё определить до реализации

1. **Patch behaviour contract:** закрыть все вопросы §3.1 общими правилами
   интерфейса и обязанностями domain implementations; отдельно определить
   domain-owned read contracts, payload и полный domain scope.
2. **Lifecycle и атомарность:** domain preparation → сбор DAG/debug →
   применение только Snapshot; согласованная единица commit; partial failure/cancellation/retry;
   границы SQL/file publication. Prepared/applied/committed статусы не смешиваются.
3. **Revision integration:** ссылки patches на исходное/результирующее состояние,
   conflict semantics, source/runtime различие, pinned resolve и held data.
4. **Source→plan:** доменный контракт dependencies/revision/invalidation и
   определения актуальности L0/L2; явная materialization из актуального плана.
5. **Existing callers:** domain-by-domain read/write inventory, переход CRUD/
   import к разрешённым entry points, совместимость и Gate: DAG.
6. **Storage contracts:** domain section serialization и snapshot persistence,
   append-only SQL/pack, история переходов в patch, restore полнота и удержание
   references; storage-формат после архитектуры. Пересмотреть mutable latest/
   pointer из source-versioning без введения второго versioning механизма.

### 7.1. Проверка текущих CRUD-контрактов (2026-10-27)

Статическая проверка перечисленных путей, не полный аудит всех доменов и
не runtime/test evidence. Пути ниже относительно `backend/app/`.

| Проверенный путь | Текущее поведение |
|---|---|
| application/worldData/registries/worldService.py: create/update/delete/import_from_json | Валидирует и непосредственно вызывает repository writes; import использует upsert; Snapshot не участвует |
| application/worldData/locations/namedLocationService.py: create/update/delete/import_from_json | Непосредственно вызывает repo.create/update/delete/upsert; подготовка и запись не разделены публичным контрактом |
| application/worldData/mapCells/mapCellService.py: import_from_json/clear/save_generated/save_settlement_surface/save_pass | Запись/удаление SQL patches через repository; это persist methods, не подготовка будущего Patch |
| application/worldData/mapCells/patchStoreService.py: upsert_patch | Непосредственный repo.upsert(MapCell); имя patch не означает реализацию нового интерфейса Patch |
| application/worldData/regions/stateChange/consumer.py: evaluate/tombstone | Расчёт результата и repository write в существующей операции; не write-free preparation |
| db/repositories/sqlite/base.py: insert/save/upsert/delete | Выполняет SQL; вне существующей transaction самостоятельно коммитит; наличие transaction не доказывает Snapshot ownership |
| application/worldData/generators/terrain/terrainGeneratorService.py и generators/hydrology/hydrologyGeneratorService.py (тот же worldData namespace) | Проверенные public compute methods возвращают вычисленные результаты без repository writes; это не полный будущий domain CRUD контракт |

В проверенных цепочках нет вызова общего snapshot apply. Генераторный CRUD
из GEN-DAG-1 — целевая архитектурная boundary; существующие service/repository
методы не объявляются автоматически готовым контрактом для нового пути.
Их прямой вызов из Patch.validate/build_result приведёт к запрещённой записи
до Snapshot и должен блокировать приёмку каждого такого класса.

Object source versioning сейчас описано в world-source-versioning.md;
runtime `SourceObjectId/SourceRevision` и общий `WorldSnapshotService` поиском
в backend/app не обнаружены. Есть schema world_snapshots и отдельная проверка
SurfacePlanningView/StateViewRevision в planning/guards/sourceRevision.py;
это не реализация общего object revision store и snapshot commit lifecycle.
Engine repair/PatchApplier меняет node_results/status, не заменяет этот механизм.

До contract freeze необходимо определить и проверить отдельно:

- write-free подготовку модификации и получение typed результата;
- внутреннюю storage-запись только под Snapshot-owned apply/commit lifecycle;
- ограничения на independent commits и доступность старых write entry points;
- согласованность результирующего состояния, source revisions и snapshot history
  при отказе/отмене. Одна ambient SQL transaction не является правом обхода Snapshot.

Критическая проверка каждого Patch дополняется отсутствием SQL/domain-state
мутации при подготовке/validation/cache без Snapshot, включая все вложенные
CRUD вызовы. При ошибке Snapshot недопустим опубликованный результат без
соответствующего зафиксированного состояния/истории по согласованному протоколу.
Конкретные механизмы ещё не выбраны и не реализованы; legacy paths не исправлены
этим документом. Код в рамках данного аудита не изменялся.

### 7.2. Первичная materialization: обязательная сверка light_bake/full_bake

**Первый bake — job DAG** с domain materialization через staging и
публикацией pack (решение мастера 2026-10-27; не Snapshot apply). Для SQL и
pack действует append-only contract; bootstrap нельзя завершить прямой
записью мимо staging/публикации. Когда запускать bake (в т.ч. auto bake
мира без pack), решает DAG; `POST pack/bake` — caller того же job; gameplay
без опубликованного базового pack не стартует. Встраивание — GEN-DAG-1;
до него `POST pack/bake` — legacy. **B-2 открыт и блокирует приёмку плана:**
legacy route держит оркестрацию стадий (L0 → C23, finalize/публикация) вне
DAG; план не закрывается, пока bake job не встроен в DAG по GEN-DAG-1.

Сохраняются существующие product contracts (`tz_world_pack_storage.md`
§ Bake modes / Job boundaries и `tz_map_light_bake.md`):

| Режим | Подготовленный результат | Что не включается |
|---|---|---|
| light_bake | Общий L0 compose на named_locations ∪ declared hydro tiles, locations_index и climate coarse; прочие климатические результаты только по existing policy | L2, C23 topology, C11 packing, entry job |
| full_bake | Тот же L0 compose на весь world_bounds со швом мира; затем обязательный C23 plan_topology — второй шаг того же product job | L2, C11/settlement geometry, entry job |

Межстадийный порядок L0 → C23 задаёт DAG по GEN-DAG-1; это не основание
спрятать две стадии в Patch, Snapshot или generator CRUD. Локальные алгоритмы
одной стадии остаются в домене. Partial light pack допустим; вход игрока
не должен получить новую обязательную зависимость от полного full_bake.

До architecture/contract freeze отдельно согласовать:

1. **Исходное состояние:** от какого captured source/revision set строится
   первая materialization; как представлены исходно отсутствующие SQL/pack
   результаты и base snapshot. Наличие исходных world/location metadata не
   означает наличие предыдущей materialization; fake base не создаётся.
2. **Передача между стадиями:** как следующий шаг читает подготовленный L0
   из PatchSet cache/рабочего представления, если он ещё не опубликован.
   Для C23 нельзя предварительно публиковать L0 в обход Snapshot только
   ради чтения существующим методом. Domain input contract должен быть явным.
3. **Граница применения:** один commit всего light/full job либо явно
   согласованные промежуточные snapshots/checkpoints. Product full complete
   требует C23; промежуточный L0 нельзя объявить завершённым full_bake.
   Вопрос числа snapshot commits ещё открыт, а не решён названием режима.
4. **Bulk-результаты:** typed patches/results для batch/scope и immutable
   артефактов; не обязательный отдельный patch/CRUD-вызов на каждую клетку.
   Владение domain storage и per-class проверки независимости сохраняются.
5. **Публикация:** initial bake тоже сохраняет SQL версии, pack manifest,
   артефакты и историю только под Snapshot-owned lifecycle. Full после light
   создаёт следующее состояние со ссылками на удерживаемые части, не стирает
   старый pack. Долгая подготовка отделена от короткого commit; source pins
   и staging lifetime должны покрывать весь согласованный сценарий.
6. **Приёмка:** first light, first full, light→full, partial light, source edit
   во время bake, отказ после L0/до C23 и между SQL/pack/history шагами,
   retry и отсутствие публикации до Snapshot. Предыдущие состояния остаются
   читаемыми. GEN-DAG-1 per-node и Patch per-class gates обязательны.

**Решено мастером 2026-10-27 (п.2, п.4, п.5):** bake поставляет мир одним
замороженным pack; snapshot = patches тиков поверх pack, pack не
перезаписывает. Формулировка п.5 «initial bake … под Snapshot-owned
lifecycle» этим заменена: публикация bake — активация pack, не snapshot.
Staged blobs/SQL rows пишет доменная операция materialization через staging
port; Patch несёт hash-ref; L0 → C23 через «опубликованное + staged refs
job». Норматив — `docs/tz_world_snapshot.md` § «Staged artifacts и точки
публикации» (там же: граница — старт gameplay: до него bake дописывает
один pack, после — вся материализация и правки уходят в snapshot; overlay
без replay тиков; LOD-независимые patches; перепечки нет — только расширение: новые тайлы/локации на wilderness без patches). Новая игра продолжает цепочку world-snapshot. Один активный timeline на мир → один overlay; attach к другой ветке — пересборка overlay от keyframe (DAG). B-3, M-1, M-2,
keyframe, rebase (отвергнут), объём snapshot (dedupe по hash) решены там же
(п. 8–13). Схема `world_snapshots` — `docs/project_data_storage_tz.md`, пороги
keyframe — реализация; открытых вопросов ТЗ нет, приёмку блокирует B-2.

Проверенные несовместимые existing paths: `pack/bake/l0/packMaterializationOrchestrator.py`
вызывает WorldPackWriter, `_persist_bake_relief_grades` и PackBakePublisher;
`pack/bake/finalize/packBakeFinalize.py` сохраняет manifest до repo.update(world);
`pack/io/worldPackWriter.py` пишет по целевым путям, включая os.replace.
Пути относительно application/worldData/. Эти механизмы сейчас не являются
Snapshot-owned append-only publication. Это вход migration inventory, не
разрешение переписать их в текущем документальном шаге или считать проблему решённой.

Согласование этого раздела — prerequisite implementation новых patch/snapshot
контрактов для первичного мира. Locked bake scope и DAG wiring сейчас не меняются.

Эти вопросы нельзя оставить разработчику «решить по месту». Concrete SQL,
DB-модели и имена existing services не заменяют архитектурного решения.

## 8. Последовательность проработки и приёмки

1. Проработать и принять каждый архитектурный пункт §1–6 отдельно, закрывая
   относящиеся к нему вопросы §7; только документы. Открытый вопрос поведения
   интерфейса не переносится в concrete implementation.
2. После приёмки — inventory переиспользуемых domain POJO/ports и contract
   freeze **ядра домена патчей**: Patch/PatchSet (только данные, M-1), порт
   `DomainSectionHandler` и реестр секций (M-2), вход Snapshot
   `apply(PatchSet)`, typed artifact ref, staging port, CAS-указатель мира
   `(pack_hash, snapshot_head)` (B-3); поля, результаты, диагностика, atomicity.
3. Подготовить implementation map: каждый класс → domain/layer → точный файл,
   направления зависимостей, folder composition/counts, existing backend binding.
4. Реализация ядра по слоям (решение мастера 2026-10-27): типы → shared infra
   (content-addressed staging adapter, lease, CAS-указатель мира) → Snapshot
   apply/commit → реестр секций в Container → первый доменный handler. Ядро —
   единственный владелец staging и CAS-указателя; world-source-versioning их
   переиспользует, второй механизм не вводится. Ядро не ждёт source-versioning
   и внешней DAG-интеграции.
5. §6 — привязка ревизий patch/snapshot после контрактов identity/revision
   world-source-versioning (его шаги 2–3).
6. Перевод существующих writer'ов на commit Snapshot / публикацию pack по
   inventory: `MapCellService`, `SettlementPersistService`,
   `ConnectionPersistService`, `region_states`/`StateChangeConsumer`
   (wilderness 9a/10a), write boundary entity-lifecycle L3. Новый прямой
   writer мимо Snapshot противоречит §1 и расширяет долг миграции.
7. Закрытие плана — после устранения B-2 (bake job встроен в DAG); это
   внешняя зависимость, не шаг этого плана.

Каждый implementation шаг — отдельно согласованный, с проверкой критического §1.

Критерии отдельной архитектурной приёмки:

| Пункт | Что необходимо для приёмки | Статус |
|---|---|---|
| §1 Общая архитектура | Приняты владельцы read/patch/history и критические границы; нет WS-посредника/DB доступа и обхода GEN DAG | Для приёмки |
| §2 Ответственности и потоки | Подготовка не пишет состояние; только Snapshot применяет набор; определены вход/выход/отказ и commit каждого этапа | Для проработки |
| §3 Интерфейс Patch/PatchSet | Общие правила §3.1 и строгие domain/operation type bindings; временный кэш §3.3; для каждого класса пройдена независимость от CRUD по §3.4 | Для проработки; class checks после реализации |
| §4 Snapshot | Snapshot — единственный вход применения; определены domain behaviour calls, сохранение состояния/операций, held references и restore | Для проработки |
| §5 Размещение | Общие контракты и domain implementations разделены по владельцам/слоям, направление зависимостей однозначно | Для приёмки архитектуры; exact файлы позже |
| §6 Версионирование | Source/runtime/format revisions различены; определены preconditions/stamps, pinning и связь patch→snapshot без второго versioning механизма | Для проработки |

Статус «принят» появляется после явной приёмки мастером соответствующего
пункта. Фиксация текущих требований сама по себе не закрывает эти пункты.
Итоговая приёмка плана требует успешной критической проверки §3.4 для всех
классов Patch. Любой провал блокирует приёмку плана до исправления реализации.

Код сейчас не меняется; ни source versioning, ни snapshot runtime не
объявляются реализованными. Ноды/SQL-schema/backend-start/коммиты не входят
в этот документальный запрос. Новые реализации требуют согласованной карты.

## 9. Норматив и совместимость

- `docs/tz_patch_system.md`: domain patches, сбор PatchSet только DAG/debug API.
- `docs/tz_world_snapshot.md`: immutable история, domain sections, authoritative state.
- `docs/tz_world_generation_dag.md`, `.cursor/rules/dag-generator-interface.mdc`:
  stable domain interfaces, production/debug separation, Gate: DAG.
- [GEN-DAG-1](gen-dag-1-post-geo-ws.md): двусторонняя независимость
  DAG/генератора, CRUD в домене, отсутствие скрытой межстадийной оркестрации
  и приёмка фактической цепочки каждой ноды. Интеграция отложена до принятия
  GEO-1 + WS и отдельного разрешения мастера. Упоминания patcher в его
  integration step требуют синхронизации с текущим решением «применяет только
  Snapshot» при contract freeze; самостоятельный apply entry не вводится.
- `docs/tz_world_pack_storage.md` § Bake modes / Job boundaries и
  `docs/tz_map_light_bake.md`: первичные light/full результаты и C23 порядок;
  обязательная сверка snapshot lifecycle — §7.2 этого плана.
- `world-source-versioning.md`: revisions/capture/retention/publication.
- PC-11: domain application read-owner, operation-wide region state inputs,
  WP-20 fallback/overlay, отсутствие IO в workers и hidden materialization.

Старый TODO(snapshot) со ссылкой на WS §7 остаётся исторической ссылкой в
runtime до отдельной синхронизации callers. Он не возвращает общий WS read
contract в архитектуру. Архивные документы не источник новых implementation требований.
