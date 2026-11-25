# Publication: pregame mutation phase boundary

## Архитектурный план поставки — актуальное дополнение 2026-11-25

Пользователь поручил дополнить контракт планом, связанным со Snapshot. Раздел ниже задаёт две отдельные части: A — public POJO/exception, B — internal phase admission. Это разрешение документирования, не реализации. Общий план B пока НЕ ПРИНЯТ: конкретные construction/authority зависимости ниже остаются OPEN. Узкий проектный PASS A не переносится на B.

### Связь со Snapshot и источники истины

- [Snapshot ТЗ](../../docs/tz_world_snapshot.md): publication identity, phase и transaction/terminal semantics; Publication не новый домен.
- [Snapshot atomic boundary](snapshot-lifecycle-atomic-boundary.md): scope/lifetime и outer transaction; используется для сверки границ, не как разрешение переиспользовать Snapshot runtime apply для Source mutation.
- [Snapshot public apply trace](snapshot-public-apply-atomic-trace.md): отличие exact replay от новой попытки и unknown от refusal. Этот план не меняет его порядок и не подключает Source к apply_snapshot.
- [Source mutation contract](source-core-mutation-contract.md), §8.1/INT-WRITER, и [node POJO card](source-mutation-node-pojo-card.md): потребитель exception, его return union и границы pregame mutation.
- Existing `application/worldSnapshot/contracts/commitScope.py`, `application/worldSnapshot/storage/publicationStore.py`, `application/publication/errors.py`: переиспользуемые контракты, не новые копии.

Перед будущей реализацией применить implement-plan, прочитать актуальные ТЗ и сверить их с этим планом. При конфликте не исправлять ТЗ или контракт молча. Сейчас Python-код не меняется.

### A. Public POJO и exception

Состав и exact signatures приведены ниже в разделе «Exact POJO и exception». Размещение:

| Файл / класс | Ответственность, зависимости, эффекты | Приёмка / критерий отказа |
|---|---|---|
| `backend/app/dataModel/publication/pregameMutationRefusal.py::PregameMutationRefusalCode` | Owning wire vocabulary; StrEnum; без IO | Один GAMEPLAY_STARTED с указанным wire; отказ при plain string code или новом OperationKind |
| Тот же файл, `PregameMutationRefusal` | Immutable факт фазового отказа; existing EntityUid/RevisionHex; без IO | Все четыре required поля, exact enum, strict config; отказ при nullable/default, scope/token/traceback или Source mirror |
| `backend/app/application/publication/errors.py::PregameMutationRefusedError` | Runtime перенос строго проверенного payload; existing application error module | `.refusal` exact owning POJO; отказ при преобразовании в infrastructure, записи terminal или логировании в constructor |
| `SourceRegistryMutationPipelineOpenPipeline.apply` — existing proposal потребителя | Пропускает exception unchanged; не копирует payload | Source явно подтверждает roster; отказ при SourceFailure/durable refusal вместо phase exception |

POJO inventory/reuse: EntityUid и RevisionHex не переобъявляются; OperationBindingMismatch описывает другое нарушение immutable request binding, SnapshotPublicFault имеет другой operation/issue roster, SourceFailure — Source-owned диагностику. Новый phase fact их не расширяет и не зеркалит. Constructor exception не является вторым контейнером бизнес-полей: единственный payload `.refusal`.

Порядок A:

1. Зафиксировать подтверждение Source по exact import/propagation и окончательное пользовательское решение по public дельте. Node Error оформляется DAG отдельно и не блокирует самостоятельный owning POJO.
2. После разрешения реализации создать enum/POJO, затем exception в existing errors.py. Runtime сервис/guard и Source mutation implementation не входят в эту поставку.
3. Проверить в proposed `backend/tests/snapshotCore/contracts/test_pregame_mutation_refusal.py`: exact Python enum принимается, plain str/foreign same-value enum отвергаются; JSON round-trip возвращает owning enum; schema содержит wire const, required roster и запрет extra; все невалидные identity/пропущенные поля отвергаются; exception отвергает чужую модель и corrupt constructed instance. Проверить positive/negative typing для payload.
4. Отдельно предъявить diff, фактические команды и результаты. Этот результат доказывает только A, не работоспособность Source mutation/phase guard.

### B. Internal phase admission

Exact proposed класс/метод и mapping исходов приведены ниже. Его scope — одна проверка phase внутри owning attempt; это не публичный DAG pipeline и не permission token issuer.

| Зависимость | Existing кандидат / exact факт | Что требуется до реализации B |
|---|---|---|
| Scope authority | CommitScope.assert_active(), read_scope; concrete registry проверяет task/connection/lifetime | Owning composition предъявляет exact API проверки operation/world/request binding в том же UOW; простого assert_active недостаточно |
| Authoritative phase read | IWorldPublicationStore.read(world_uid: EntityUid, *, scope: CommitReadScope \| None = None) -> WorldPublicationRef; поле gameplay_started | Подтвердить этот источник для Source world, обязательную передачу того же scope.read_scope и missing/corrupt handling. Наличие метода не доказывает serialization |
| Attempt binding | IOperationStore.read(operation_id) не принимает scope | Не использовать independent latest read. Нужен exact accepted internal scoped verification contract; private _load не становится public port автоматически |
| Constructor PregameMutationAdmission | Ещё не назначен | Publication/Snapshot owner предъявляет точную сигнатуру с принятыми collaborators, identity checks и проверкой graph; не вводить Any/callback/второй coordinator ради заполнения пробела |
| Lifetime и serialization | Existing outer transaction infrastructure | Зафиксировать защиту phase-read → mutation-write относительно gameplay transition в том же UOW. Не выдавать success по preview/fixture flag |
| Caller | Owning новой попыткой infrastructure; конкретное место OPEN | Назвать existing/proposed concrete caller/method и вложенную цепочку без прямого Source→foreign public pipeline, скрытого orchestration или нового DAG маршрута |

Внешняя реализация gameplay/generator OUT; внутреннюю гарантию serialization нельзя объявлять OUT. Проверить её можно synthetic caller с настоящей owning transaction authority и конкурирующим storage participant, без реализации gameplay pipeline. Synthetic scope/token, не выданный infrastructure, пригоден только для negative case.

Порядок B: сначала закрыть таблицу exact contracts/constructor/caller и архитектурную приёмку, затем отдельное разрешение реализации. Только после этого owning реализация assert_allowed и проверки same-scope pregame success, typed gameplay refusal, binding/task/connection mismatch, missing/corrupt state, race phase-transition vs mutation, rollback/unknown/cancel. Exact replay не вызывает guard. Guard не коммитит, не делает claim и не выполняет Source writes. Test path proposed: `backend/tests/snapshotCore/storage/publication/test_pregame_mutation_admission.py`; тесты не создаются вместо ещё не принятого контракта.

### Архитектурная приёмка и границы

Три запрета DAG: A не исполняет маршрутов; B не выбирает следующую операцию, не запускает foreign pipeline и не добавляет скрытый worker/callback. Конкретный caller B пока OPEN, поэтому полная архитектурная приёмка B не заявляется. Не назначаются ноды/NodeId/CALL и порядок внешнего процесса. Node Input/Error не содержат CommitScope.

CRUD: A — value/error types, не сервис хранения и не настройки; CRUD API не создаётся. B — admission существующей операции, не writer phase/state/settings; authoritative read boundary указана отдельно и требует подтверждения. Это локальная проверка среза, не приёмка полного CRUD Snapshot.

Источники порядка: existing Source replay/new-attempt distinction и Snapshot transaction/unknown guarantees, перечисленные выше; новая ошибка не отменяет exact replay и не подтверждает durability. Конкретное placement B нельзя объявить принятым до предъявления caller. Ответственности, public/internal границы и критерии отказа A указаны в таблице; для B незакрытые constructor/caller гарантии — явный отказ общей приёмки, не разрешение stub-реализации.

Без отдельного разрешения не менять Source/DAG/shared coordination файлы, production composition, terminal manifest/IDs, SQL, gameplay/generator. Для A достаточна самостоятельная поставка POJO/exception после её решения; B не blanket blocker A. Основной координатор проверяет POJO→node Error, а не внутреннюю архитектуру B. Полная готовность плана не выводится из его узкого PASS.

Дата: 2026-11-25. Статус: конкретный owning PROPOSAL для обязательной сверки основным координатором. Пользователь потребовал определить метод вместе с POJO/Error и зафиксировать контракт. Прежнее сообщение «контракт согласован» отозвано: согласованной общей границы и реализации пока нет. Этот документ не выдаёт code-go.

## Scope и владелец

Publication — инфраструктурная часть Snapshot. Здесь определяется только фазовый допуск новой pregame mutation и его typed публичный отказ. Source сохраняет собственные mutation predicates. Gameplay/generator implementation, новые DAG routes/NodeIds, SQL, recovery, retention и terminal representation OUT. Их отсутствие не блокирует рассмотрение этой границы.

Источники: source-mutation-node-pojo-card.md, source-core-mutation-contract.md §8.1/INT-WRITER; existing application/publication/errors.py и application/worldSnapshot/contracts/commitScope.py. Existing ошибки не содержат подходящего gameplay-started payload; SnapshotPublicFault имеет другой operation/diagnostic roster и не расширяется этим предложением.

## Exact owning метод — proposed, не existing

Модуль: `app.application.publication.service.pregameMutationAdmission`.
Конкретный класс: `PregameMutationAdmission`.

```python
async def assert_allowed(
    self,
    scope: CommitScope,
    *,
    operation_id: EntityUid,
    world_uid: EntityUid,
    request_fingerprint: RevisionHex,
) -> None: ...
```

Типы переиспользуются: CommitScope — app.application.worldSnapshot.contracts.commitScope; EntityUid — app.dataModel.identity.uid; RevisionHex — app.dataModel.validation.diagnostics.runtimeIssueContext. Нового input DTO/token нет: именованные identity operands и existing issued scope имеют разные обязанности.

Ответственность метода: в текущей owning write attempt проверить допустимость новой pregame mutation относительно authoritative gameplay phase. Успех — None, а не persisted outcome или transferable permission. Метод не запускает Source, не вызывает gameplay pipeline, не делает claim/commit/rollback, не пишет terminal и не решает следующий маршрут.

Вызов принадлежит owning инфраструктуре разрешённой новой попытки после exact replay resolution и до mutation writes; не прямому Source→foreign public pipeline и не отдельной ноде. Это ограничение существующего процесса, не назначение нового DAG порядка. Existing terminal replay фазовым отказом не заменяется.

Обязательная гарантия: issued scope принадлежит текущей task/connection/UOW и той же operation; operation/world/request fingerprint соответствуют admitted persisted attempt. Переданные строки не являются authority. Проверка phase и subsequent permitted mutation должны оставаться в одной защищённой owning transaction относительно gameplay transition. None не может использоваться после окончания scope или в другом UOW. Если это нельзя обеспечить, данная реализация не соответствует контракту и не выдаёт фазовый допуск по stale preview.

## Exact POJO и exception — proposed

Модуль `app.dataModel.publication.pregameMutationRefusal` содержит proposed owning enum и POJO:

```python
class PregameMutationRefusalCode(StrEnum):
    GAMEPLAY_STARTED = "publication.pregame_mutation.gameplay_started"
```

Класс `PregameMutationRefusal`:

| Все обязательные поля | Тип |
|---|---|
| code | Literal[PregameMutationRefusalCode.GAMEPLAY_STARTED] |
| operation_id | EntityUid |
| world_uid | EntityUid |
| request_fingerprint | RevisionHex |

Config: strict=True, frozen=True, extra="forbid", revalidate_instances="always". Поля required, без defaults/nullable. Enum принадлежит Publication; новый OperationKind не вводится. Это один public immutable refusal fact; Source mirror и новый canonical ID не вводятся.

Python admission поля code принимает exact owning enum member; голая строка и foreign StrEnum с равным wire value отклоняются, несмотря на equality строковых enum. JSON admission принимает прежнюю wire string и восстанавливает owning PregameMutationRefusalCode.GAMEPLAY_STARTED. JSON serialization сохраняет эту строку, schema — string const с этим значением. Нельзя вводить общий before-validator, который запрещает JSON строку вместе с Python строкой. При будущей реализации отдельно проверяются Python exact member/foreign same-value/plain string, JSON round-trip и schema; конкретный validation hook здесь не объявляется реализованным.

Модуль `app.application.publication.errors`, класс `PregameMutationRefusedError(Exception)`:

```python
def __init__(self, refusal: PregameMutationRefusal) -> None: ...
# Public typed payload:
refusal: PregameMutationRefusal
```

Constructor строго revalidates exact owning payload. `PregameMutationAdmission.assert_allowed` поднимает этот exception исключительно когда authoritative state запрещает новую mutation из-за начавшегося gameplay. Это expected phase refusal, не PublicationInfrastructureError/OperationBusyError. Payload сохраняет identity предъявленной попытки, но не утверждает durable terminal, confirmed rollback или отсутствие прошлых эффектов.

## Полный mapping этой узкой границы

| Исход | Контракт |
|---|---|
| Valid bound attempt, pregame permitted | return None |
| Valid bound attempt, gameplay started | raise PregameMutationRefusedError(refusal) |
| Malformed typed identity operands | existing Pydantic ValidationError; не phase refusal |
| Foreign/expired/read-only scope, attempt binding mismatch, corrupt/missing authoritative state | PublicationInfrastructureError; причина сохраняется; не утверждать gameplay started |
| Unknown owning transaction outcome/quarantine | UnknownCommitOutcome без понижения категории |
| Invocation cancellation | asyncio.CancelledError, не OperationCancelled |
| Unexpected programming failure | распространяется; не сериализуется как business payload |

Exact mapping Source boundary: `SourceRegistryMutationPipelineOpenPipeline.apply(request)` распространяет `PregameMutationRefusedError` неизменным. Return union SourceMutationApplied | SourceMutationRefused | SourceFailure | OperationCancelled не меняется. Отказ не превращается в SourceFailure либо durable SourceMutationRefused. Наружу используется только .refusal, не args/traceback. Если outer attempt имела effects, phase exception не является свидетельством rollback: owning unknown имеет приоритет; вопрос terminal persistence не решается этим POJO.

## Ответственности и критерии отказа

- PregameMutationAdmission: одна phase admission; отказ при claim/commit/Source execution, stale-state success или непроверенной attempt identity.
- PregameMutationRefusal: только immutable identity/code; отказ при storage handles, Python class objects, tracebacks или Source mirror.
- PregameMutationRefusedError: перенос exact payload; отказ при logging/persistence/orchestration в constructor.
- Source public boundary: propagation без перекодирования; отказ при synthetic success/terminal или превращении infrastructure в phase refusal.

## Сверка и точные оставшиеся границы

На согласование предъявлены exact module/class/method/Input/Output/Error и Source exception roster delta. По уточнению координатора 2026-11-25 его verdict ограничен POJO → node Error: поля identity, immutable config и raise/propagation совместимы; замечание о code уточнено выше owning StrEnum. Прямой поиск координатора не обнаружил duplicate carrier, но это не глобальная архитектурная приёмка. Source должен подтвердить exact propagation и обновить свой roster; DAG отдельно определяет node Error carrier. CommitScope не входит ни в node Input, ни в Error.

Основной координатор в этой сверке НЕ принимает assert_allowed, его placement/construction/authority/transaction. Это отдельный owning infrastructure scope; ожидание такого verdict не является gate узкой публичной POJO/Error дельты. Имена enum/POJO/метода остаются proposal, не runtime факт.

Реализация метода отсутствует. Его construction dependencies, authoritative phase access и serialization mechanism с gameplay transition не утверждены этим документом; требуется отдельная внутренняя runtime сверка до реализации, без задания gameplay/generator и без fake authority. Данная POJO/Error сверка не доказывает готовность INT-WRITER или полной mutation.

Координаторский verdict 2026-11-25: **PASS проектной форме enum/code и POJO → exception payload**, замечание о строковом code снято. Wire значение неизменно; Python exact-member и JSON decoding разделены явно. Это документационная сверка, не runtime/schema admission PASS и не окончательное пользовательское ACCEPTED. Foreign same-value enum/JSON остаются требованиями будущих tests, а не доказательством реализованного guard.

Статусы вести раздельно: публичная POJO/Error дельта ожидает подтверждения Source по final proposed roster/unchanged propagation и решения пользователя; node Error carrier — отдельная DAG дельта. Внутренний assert_allowed/authority/transaction остаётся owning proposal и в verdict не входит. Проверки реализации в будущем: exact payload/schema; отсутствие phase refusal на replay; malformed vs gameplay-started vs infrastructure/unknown/cancel; запрет чужого scope/binding; отсутствие writes в самом методе. Сейчас runtime tests не заявлены.
