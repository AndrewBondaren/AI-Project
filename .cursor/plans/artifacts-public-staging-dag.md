# Artifacts — публичный staging и граница с DAG

2026-11-17. **DESIGN OPEN. Первый обязательный этап — ARCH-0: целевая архитектура и её приёмка. До закрытия ARCH-0 реализация последующих этапов запрещена.** Этот документ не является разрешением писать код и не объявляет домен принятым.

## Решения пользователя и источники

**Приоритет редакций:** раздел «Завершённое предложение Artifacts: публичный срез V1» ниже заменяет предварительные stage-specific failures и запросы другим доменам проектировать `_lease`, storage classification и logging. Эти вопросы решаются внутри Artifacts. Исторические записи исследования ниже не являются действующими внешними требованиями. Завершённость предложения среза не означает пользовательскую приёмку ARCH-0 всего домена, реализацию или закрытие CRUD.

## Завершённое предложение Artifacts: публичный срез V1

### Предоставляемые операции

Пути относительно `backend/app`. Все новые классы/типы — TARGET. Public interfaces содержат те же signatures, что concrete classes; executable dependencies задаются composition, не передаются через DAG.

| Concrete public class / модуль | Метод | Input → success | Declared errors |
|---|---|---|---|
| ArtifactPrepareStageOpenPipeline[C], application/artifacts/staging/artifactPrepareStageOpenPipeline.py | `def prepare_stage(self, request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]` | content → тот же content + ожидаемый ArtifactRef descriptor | ArtifactInputRejected; ArtifactIntegrityError для нарушенного codec/format implementation |
| ArtifactStageOpenPipeline[C], application/artifacts/staging/artifactStageOpenPipeline.py | `async stage(self, request: ArtifactStageInput[C]) -> ArtifactRef` | lease + prepared → sealed ref, равный descriptor | ArtifactInputRejected; ArtifactLeaseRefused; existing OperationBusyError, PublicationInfrastructureError (включая ArtifactIntegrityError), UnknownCommitOutcome; CancelledError |

Интерфейсы IArtifactPrepareStageOpenPipeline/IArtifactStageOpenPipeline находятся в одноимённых модулях `application/artifacts/contracts/`. Existing immutable ArtifactFormatContract[C] и поддерживаемая version связываются в composition; prepare и stage обязаны иметь одинаковый binding. BLOB specialization — bytes, SQL_ROWS — concrete owning frozen model. Generic BaseModel не допускается как фактический registered payload. Binding errors отклоняются при composition, не исправляются выбором другого формата.

POJO в `dataModel/artifacts/staging/preparedArtifact.py`: ArtifactPrepareStageInput[C](content:C), PreparedArtifact[C](content:C, descriptor:ArtifactRef). В `staging/stageInput.py`: ArtifactStageInput[C](lease:OperationLeaseRef, prepared:PreparedArtifact[C]). Все strict/frozen/extra-forbid; content deep immutable по existing validate_immutable. PreparedArtifact — временный runtime envelope, не persisted payload и не capability.

**Identity admission:** новый input/envelope не сериализует content и не заменяет существующий concrete instance. Валидация nested content выполняется проверкой его concrete schema/immutability с сохранением исходного admitted экземпляра, по существующему принципу Engine ContractValidator. Для новых wrapper-моделей instance-preserving validator явно возвращает проверенный исходный объект; model_construct и безусловное доверие экземпляру запрещены. Диагностическая validation может создавать временные объекты, но возвращаемый content остаётся исходным. Для bytes identity также проверяется. Это ответственность Artifacts, не требование к соседу изменить revalidate_instances его модели.

**Pure prepare:** без IO, lease, holds, registry mutations и domain calls. Внутренняя реализация применяет fixed pure codec/row_count и existing content digest, возвращает descriptor. **Stage:** сначала проверяет input и пересчитывает полный descriptor тем же внутренним алгоритмом, затем reserve → backend.write → seal. Не вызывает public prepare. При несовпадении descriptor до IO — input refusal. При корректном lease успех означает sealed + operation-held в момент завершения, а не бессрочную гарантию: concurrent cancel/cleanup может затем снять hold; publication обязана выполнить собственный authoritative admission.

Повтор stage допустим только пока lease writable: reused content identity не заменяет проверки. READY/closed не позволяет повторный stage; replay completed preparation принадлежит публичному lifecycle-владельцу. При partial write могут остаться удерживаемые данные. CancelledError распространяется после drain; unknown outcome не становится refusal или success.

### Единые ошибки Artifacts: внутреннее решение

InputRejected и field roster из раздела ошибок ниже сохраняются. Никаких ArtifactStageFailure/ArtifactStageRefused/stageFailure.py не создавать: предварительное предложение отозвано.

Единственный TARGET logic POJO `dataModel/artifacts/lifecycle/leaseFailure.py::ArtifactLeaseFailure`:

- `lease: OperationLeaseRef`;
- `requirement: ArtifactLeaseRequirement` со значениями WRITABLE/CLOSED;
- `code: ArtifactLeaseFailureCode`: OPERATION_MISSING, BINDING_MISMATCH, FENCE_MISMATCH, LEASE_ABSENT, PHASE_NOT_WRITABLE, ADMISSION_CLOSED, ADMISSION_OPEN.

Strict/frozen/extra-forbid, без повторения identity-полей lease. Валидатор совместимости: PHASE_NOT_WRITABLE/ADMISSION_CLOSED допустимы только для WRITABLE, ADMISSION_OPEN — только для CLOSED. TARGET carrier `application/artifacts/lifecycle/leaseErrors.py::ArtifactLeaseRefused(failure: ArtifactLeaseFailure)` валидирует POJO, наследуется от Exception, не ValueError, не логирует и не пишет terminal. Stage и другие Artifacts consumers передают его без stage-wrapper.

Authoritative порядок внутри Artifacts: load/validate operation → missing → сравнение world/kind/fingerprint → сравнение fence → проверка полной persisted admission chain → требуемый режим. Corrupt chain/invalid persisted values дают infrastructure fault, а не ожидаемый refusal. Полное отсутствие chain даёт LEASE_ABSENT: существуют direct-publication операции без staging. Если конкретный persisted workflow обещает обязательную chain, нарушение его гарантии трактуется этим workflow как infrastructure inconsistency. Последний event fence, несовместимый с current operation fence при корректном requested lease, — corruption. WRITABLE требует PREPARING/open; CLOSED требует closed, но сам не утверждает READY/APPLYING или drain.

Это единый внутренний протокол для reserve/seal, leases open/assert/writer/read/finish, holders release/handoff и climate retention. Их изменение выполняется одним согласованным implementation-срезом, включая fixtures/catches; внешним доменам не поручается проектировать `_lease`.

**Integrity:** TARGET `application/artifacts/errors.py::ArtifactIntegrityError(PublicationInfrastructureError)` — узкая категория нарушения целостности артефакта, не новый business refusal. Она не содержит второго descriptor DTO; исходная exception chain сохраняется. Используется при same content-address key с противоречивым descriptor, отсутствующей/чужой внутренней reservation, потере hold/claim при действующем lease, mismatch backend bytes после успешного preflight, нарушении pure codec output contract. Перед классификацией потери reservation/hold/claim в том же storage scope проверяется lease: доказанный cancel/fencing даёт ArtifactLeaseRefused; при действующем lease — integrity. Structural persisted lifecycle corruption остаётся PublicationInfrastructureError; не все infrastructure faults являются content corruption.

Storage OSError на stage нормализуется на owning storage boundary в PublicationInfrastructureError с исходной причиной; cancel и UnknownCommitOutcome не перехватываются этим mapping. Existing verified-read CorruptBlobError не дублируется: при реализации он становится specialization ArtifactIntegrityError с прежним смыслом physical bytes mismatch. GC сохраняет свои утверждённые GcReport/ArtifactGcFailure, не переиспользует stage refusal.

Внешний consumer может различать ArtifactIntegrityError и общий infrastructure fault по публичной категории. Например Pack вправе отобразить именно ArtifactIntegrityError в собственный SOURCE_CORRUPT; catch всех PublicationInfrastructureError как corruption запрещён. Это требование совместимости публичной ошибки, не предписание внутреннего устройства Pack reader.

**Logging:** pure prepare не имеет IO и не пишет лог. Field refusal переносится существующей validation/diagnostics политикой; новый повторный emit не вводится. Storage adapters не логируют rethrow. Stage boundary единожды сообщает lease refusal через existing ArtifactLifecycleLog: TARGET LEASE_REFUSED, optional lease_failure:ArtifactLeaseFailure в existing ArtifactLogRecord (обязателен ровно для этой activity), emit_lease_refusal(failure), WARNING без traceback. Requested operation/world/fingerprint берутся из lease, отсутствующие publication/artifact facts не выдумываются. Infrastructure/unknown логируются owning fault boundary как ERROR с исходным exception; не превращаются в LEASE_REFUSED. Carrier не логирует; повторный emit того же исхода выше по стеку запрещён. Sink failure не меняет outcome, existing UnknownLogConsumerError fail-fast сохраняется. Дельта logging ТЗ входит в реализацию, а не поручается другому домену.

### Ответственность новых внутренних компонентов

TARGET `application/artifacts/staging/artifactDescriptor.py::ArtifactDescriptorBuilder[C]` содержит pure алгоритм encode/digest/row_count, использует fixed contract и existing canonical primitive. Public pipelines зависят от этого внутреннего job, но не реализуют hash/codec. Нарушение — IO, выбор доменной стратегии либо запуск соседней операции. TARGET `application/artifacts/staging/artifactAdmission.py::ArtifactInputAdmission[C]` проверяет input/schema/immutability/binding, агрегирует field diagnostics через существующие helpers, сохраняет instance identity; не открывает lease и не выбирает retry. Нарушение — side effect или копирование payload ради транспорта.

Оба публичных pipeline владеют только линейным порядком одной операции и передачей typed результата/ошибки. Existing registry/backend/catalog/lease/holder/GC роли из реестра ниже сохраняются. DTO/enums имеют только validation; exceptions только carrier/category. Замена hash/backend при неизменном контракте не требует изменения DAG. Нет второго публичного TypedArtifactStager: existing алгоритм переиспользуется/переносится во внутреннюю реализацию на cutover, не остаётся обходным entry доменных callers.

### Требования к другим доменам — только публичные контракты

| Владелец | Что Artifacts получает/предоставляет через DAG | Требуемая публичная гарантия |
|---|---|---|
| Time и другие producers | Получаем конкретный immutable content; для Time это encoded bytes | Successful owning preparation/encode; согласованный формат, никакого lease/hash/storage writer от Time. Одна и та же content-ссылка передаётся prepare_stage и stage |
| Publication initial opening | Получает наш descriptor плюс собственную start identity; возвращает writable OperationLeaseRef либо existing completed-result/refusal | Lease соответствует preparation/world/kind/fingerprint; READY не выдаётся как разрешение stage; concrete result позволяет DAG выбрать дальнейшую операцию |
| Publication initial registration | Получает тот же lease, stage ref и start identity | Success означает проверенную exact registration и завершённую подготовку; no partial success; replay/refusal/unknown outcomes явно различимы; stage ref сам по себе не доказывает semantic identity |
| Publication Pack completion | Получает agreed prepared refs/lease и собственный публичный input | Success READY подтверждает полный принятый retained set, включая необходимые Source dependencies; failure не оставляет частично завершённую подготовку. Внутренние transaction/scoped методы в требования не входят |
| Pack | Передаёт canonical manifest content, получает наш descriptor/ref | Pack проверяет свой состав и соответствие manifest, candidate выдаётся после подтверждённого completion; ArtifactIntegrityError сохраняет отличие от прочих infrastructure ошибок |
| Source | Прямого публичного вызова из Artifacts нет | Его публичные данные/результаты и гарантии удержания согласуются с потребителем completion через DAG; Artifacts не требует конкретного resolver/SQL/UOW устройства Source |
| Engine DAG | Получает конкретные input/output/error types двух операций | Согласованный in-memory маршрут сохраняет content identity; выбирает open/replay/stop/retry по public result, не вызывает reserve/seal/скрытые storage APIs |

Требования к соседям не назначают им SQL, helper classes, scopes, carriers чужого домена и алгоритм хранения. Все ранее отправленные просьбы спроектировать Artifacts lease errors/descriptor/integrity/logging отозваны как внешние требования; полученное исследование использовано в собственном решении выше. Для согласования теперь предъявляется эта редакция публичного среза.

### Что завершено и что не объявлено принятым

Вопросы определения descriptor до lease, внутренней ответственности, общего lease-carrier, source-branch classification и logging **решены в архитектурном предложении V1**. Не требуется повторно спрашивать соседей, как устроить эти механизмы Artifacts. Проверки реализации: instance identity включая revalidation, no IO prepare, descriptor mismatch до reserve, stale/closed modes во всех callers, cancel/drain, integrity отдельно от unavailable, no duplicate logging, retry только по writable lease.

Пользовательская приёмка V1, exact foreign public signatures и совместная DAG-карта остаются отдельными gates. Полные CRUD/read/settings и общий class/POJO closure домена остаются в ART-Q4…Q6: этот срез их не закрывает. Нельзя объявлять весь Artifacts ARCH-0 принятым на основании двух публичных методов. Код не изменён, runtime checks не выполнялись.

**Вариант 1 принят пользователем 2026-11-17 («Давай 1»).** Artifacts предоставляет две самостоятельные публичные операции для DAG: pure `prepare_stage` вычисляет descriptor и возвращает prepared объект с той же ссылкой на content; `stage` принимает lease и этот prepared объект, выполняет reserve/write/seal. Publication открывает и завершает preparation. Это решение заменяет прежнее предложение единственного stage(lease, content); не означает приёмку всех типов ошибок, foreign-контрактов или реализацию. Далее действует редакция двух операций.

**Дополнение решения пользователя, 2026-11-17:** INITIAL-REGISTER переводится на сохранённый ref после отдельного публичного staging через DAG; прежняя bytes-входная форма registrar подлежит нормативному пересмотру. Это принятие границы, не exact нового Input/Output/Error. Требуется согласовать открытие INITIAL_STATE_PREPARATION/lease, identity и format admission, защиту staged ref, атомарную регистрацию/завершение подготовки, replay и cleanup. Time остаётся владельцем pure preparation/encode/decode, registrar не вызывает Time/World. До согласования конкретного протокола прежний accepted bytes-input в Snapshot читается как исходный контракт под замену, а не как разрешение сохранить два публичных пути.

По поручению пользователя начато междоменное согласование с Pack, Publication/Artifacts/Snapshot и Time в существующих чатах владельцев. Каждый сначала сверяет собственные актуальные контракты, затем предъявляет точную дельту и возражения. Ответы по новой границе ожидаются. Направление согласовано пользователем; полная междоменная архитектура ещё не принята.

В обсуждении согласованы публичный атомарный staging, явный вызов через DAG и передача подготовленного объекта по ссылке внутри процесса. Пользователь отдельно потребовал первым пунктом реализации закрепить архитектуру. Подробные сигнатуры, классы, ноды и порядок интеграции ещё требуют архитектурной приёмки.

Нормативные источники: [правила DAG и все критерии приёмки](../rules/dag-generator-interface.mdc), [Snapshot ТЗ](../../docs/tz_world_snapshot.md), [owning-план Snapshot](./world-domain-patches-snapshots.md), [GEN-DAG](./gen-dag-1-post-geo-ws.md). Текущие формулировки ТЗ и правила DAG помещают staging внутрь materialization. Новый публичный staging меняет именно эту границу; ARCH-0 должен подготовить и согласовать точную синхронизацию источников, а не скрыто трактовать старую границу как новую. Остальные утверждённые порядки bake и публикации сохраняются.

## 1. ARCH-0 — архитектура до реализации

**Первый обязательный пункт исполнения плана.** Подготовить целевую архитектуру Artifacts и общей Publication-инфраструктуры в данном срезе, предъявить пользователю и получить явную приёмку. Наличие существующего кода, локальных PASS или принятого D2 не заменяет этот gate. До приёмки разрешены исследование и проектирование, но не создание каркасов API, перенос staging, изменение DAG или storage.

### Целевая граница

```text
DAG → Domain.prepare/owning encode → типизированное immutable content
DAG → Artifacts.prepare_stage(content) → PreparedArtifact(content, descriptor)
DAG → Publication.open_preparation(owning input, descriptor) → lease
DAG → Artifacts.stage(lease, prepared) → ArtifactRef
DAG → следующий публичный потребитель / публикация Pack / Snapshot.apply
```

Названия Domain.prepare и Artifacts.stage здесь обозначают операции архитектуры, а не утверждённые имена новых классов или нод.

Artifacts остаётся общей инфраструктурой ядра патчей; Snapshot, Pack и Source используют единый механизм. DAG владеет порядком публичных операций и выбором следующей операции. Домены владеют содержимым результата. Artifacts не вызывает публичный pipeline другого домена, не выбирает следующую стадию и не запускает materialization. Регистрация кодеков и storage adapters не должна маскировать такие вызовы.

Pure prepare_stage выполняет format admission, encode/hash/размер/row_count и выдаёт descriptor без IO и lease. Stage проверяет соответствие prepared содержимого descriptor и своему binding, затем целиком выполняет reserve, запись и seal/проверку по существующим контрактам. DAG не управляет этими внутренними действиями. Атомарность stage означает единый внешний результат операции; это не обещание одной SQL-транзакции вокруг BLOB IO. До успеха возможны удерживаемые staged данные, но отсутствует опубликованный результат. Transaction scopes, writer drain, fences, holders и защита от GC остаются ответственностью общей инфраструктуры. Строка open_preparation в схеме — зависимость специализированного initial-пути, не разрешение переоткрывать Pack lease для каждого артефакта; Pack сохраняет свой owning preparation binding.

### Передача данных

Передавать между preparation и staging ссылку на тот же типизированный объект в одном процессе. Не копировать и не сериализовать payload лишь ради перехода между нодами. Сериализация для canonical hash и хранения допустима внутри storage-пути; обещание полного отсутствия выделений памяти не даётся.

После передачи содержимое не изменяется, включая вложенные коллекции и буферы. ARCH-0 определяет конкретный способ обеспечения этого условия и владельца времени жизни. Ссылка удерживается до завершения/отмены staging; cleanup не освобождает данные, пока ими пользуется writer. Не вводить универсальный Any/dict payload либо callback, повторно запускающий доменный расчёт.

Ссылка на объект — временная память процесса, ArtifactRef — идентичность сохранённого артефакта. После потери процесса восстанавливаются durable facts; если пригодного результата нет, DAG решает о повторной подготовке. Нельзя сохранять адрес объекта как durable checkpoint. Проверить реальную модель исполнения DAG: сериализацию outputs, worker/process boundaries и checkpoints. Если она не допускает передачу объекта по ссылке, предъявить конкретное противоречие до реализации; не вводить скрытую копию или отдельный registry объектов.

### Обязательные deliverables ARCH-0

1. Полный inventory текущих callers, вложенных вызовов, registries, composition roots, debug/worker путей и storage adapters. Для каждого — existing/target, замена и удаление прежнего маршрута. Особо проверить вызовы TypedArtifactStager.stage из materialization и их перенос.
2. Для каждого задействованного класса: модуль, роль, ответственность, допустимые зависимости/эффекты, проверяемый критерий приёмки и конкретный признак отказа. Включить существующие классы из стартового inventory ниже и весь обнаруженный closure. Общая характеристика подсистемы не заменяет реестр классов.
3. Для каждой операции: конкретный публичный класс и полная сигнатура, модули POJO входа/результата/ошибок, владелец интерфейса, caller, открытый pipeline и внутренняя реализация. Проследить вложенные вызовы; проверить заменяемость реализации без изменения DAG. Не переносить backend, SQL scope или алгоритм в публичный контракт.
4. Полный анализ POJO и типизированных field/logic errors: поля, владельцы, назначение, сравнение с existing/planned типами и отсутствие дублирования. Согласовать конкретный prepared payload и различие временной ссылки и ArtifactRef; не создавать параллельные lease/holder/operation модели.
5. Матрица CRUD данных и настроек: каждая операция отдельно, конкретные методы и POJO по обязательному правилу. Не считать immutable content автоматическим исключением для update и не придумывать настройки ради таблицы. Неизвестный контракт или необходимое исключение остаётся открытым до решения пользователя.
6. Для каждой чужой зависимости выполнить протокол междоменного CRUD из правила: owning-контракты, согласованные маршруты и POJO. Привязку к конкретным DAG-нодам согласовать с пользователем; вымышленные ноды не закрывают gate. Не заменять маршрут прямым вызовом чужого pipeline через DI.
7. Сопоставить существующий утверждённый порядок и целевой порядок каждого маршрута, включая условия запуска, cancel/recovery/GC и вложенные атомарные действия. Сохранить full_bake L0 → C23 и detailed location L2 → C11 при settlement-like. Указать точное место staging относительно каждого результата. Новый порядок остаётся открытым до согласования.
8. Согласовать текст изменения ТЗ/правила о staging внутри materialization и границу с ARCH-0 Snapshot. Не обходить остановку реализации в owning-плане Snapshot.

**Приёмка ARCH-0:** отчёт по каждому обязательному критерию правила DAG с местом в архитектуре и доказательством. Pipeline, выбирающий следующую операцию; скрытый запуск; прямой междоменный публичный вызов — каждый даёт отказ. Неполный реестр классов, неполные контракты/POJO/CRUD, неизвестные маршруты или несогласованный порядок также означают отказ. Сейчас эти deliverables не закрыты: план не готов к приёмке реализации.

## Исходный inventory для ARCH-0

| Existing | Роль, которую нужно сохранить и проверить |
|---|---|
| application/artifacts/staging/artifactStaging.py::TypedArtifactStager | Уже имеет stage(lease, content) → ArtifactRef: encode/hash → reserve → backend.write → seal. Кандидат переиспользования, не доказательство готового DAG-facing API. |
| Там же ::ArtifactStagingService | Делегирует lifecycle/storage операции через существующие порты; не должен становиться междоменным оркестратором. |
| application/artifacts/registry/artifactRegistry.py::ArtifactFormatRegistryBinding | Регистрация и разрешение форматов/backends; без запуска доменных pipelines. |
| application/artifacts/lifecycle/artifactGc.py::ArtifactGarbageCollector | Безопасное удаление кандидатов с учётом удержаний; момент запуска определяет DAG. |
| application/artifacts/contracts/ и storage/ | Existing staging/holder/backend/catalog/lease contracts; проверить публичную и внутреннюю границы по каждому методу. |
| application/publication/service/operationLedger.py и db/repositories/sqlite/artifacts/ | Operation lifecycle и durable adapters; проверить scope, fences, cancel и handoff без переноса SQL в DAG. |

Пути в таблице относительно backend/app. Таблица — старт исследования, не полный реестр для приёмки.

## Последующие этапы — только после ARCH-0

### ARCH-0 — проработка по коду от 2026-11-17

Следующие положения конкретизируют архитектуру выше. Все новые имена ниже — TARGET proposal, не existing и не принятая реализация. Пользователь подтвердил границу первой поставки: prepare → stage в памяти одного процесса; durable/checkpoint-интеграция Engine остаётся открытой. Это не разрешение отключить durable execution существующих маршрутов.

#### Фактическая передача результата в Engine

- `application/engine/runtime/validation/contractValidator.py::ContractValidator.validate` проверяет declared instance, `validate_immutable` и вложенные модели, затем возвращает исходный output. Проверка моделей может создавать временные validation instances; обещается сохранение identity передаваемого результата, а не отсутствие любых allocations.
- `application/engine/runtime/dag/context/dagReadView.py::DagReadView.require` через `_read` возвращает `record.output`, проверив declaration, contract и execution identity. Это подтверждённый механизм передачи ссылки. Новый object registry, handle table или deepcopy не нужны.
- `application/engine/contracts/outputRef.py::OutputRef` — декларация producer/output_type, а не ссылка хранения payload. Не создавать второй аналог OutputRef в Artifacts.
- `application/engine/runtime/dag/dagExecutor.py::DAGExecutor._run_workflow_phase` восстанавливает output через `contract.output_type.model_validate_json(record.terminal_payload())`; non-durable argument в этой workflow-ветке также проходит store/CheckpointCodec. Поэтому одного `durable=None` недостаточно для гарантии identity. Конкретный graph binding должен доказать, что выбран обычный in-memory путь; workflow branch не входит в принятую первую границу.
- `dataModel/validation/immutableValue.py::validate_immutable` допускает bytes, frozen модели, tuple/frozenset и рекурсивно проверяет вложения; list/dict, mutable buffer, opaque handle и циклы отклоняются. Повторно реализовывать deep immutability в Artifacts нельзя.

Владение: producer возвращает frozen prepared POJO; catalog удерживает output до принятой Engine invalidation, stage удерживает аргумент до завершения awaited write/seal. Backend обязан завершить/drain writer до возврата/распространения отмены. Удаление одной catalog-ссылки не освобождает объект, пока stage им пользуется. Нельзя дополнительно обнулять или мутировать содержимое. Restart не сохраняет Python identity; повторное вычисление выбирает DAG по durable facts.

#### Публичная операция staging: конкретный предлагаемый контракт

**Дополнение двухоперационной редакции.** TARGET `application/artifacts/staging/artifactPrepareStageOpenPipeline.py`: concrete `ArtifactPrepareStageOpenPipeline[C: bytes | BaseModel]`; интерфейс `IArtifactPrepareStageOpenPipeline` в `application/artifacts/contracts/artifactPrepareStageOpenPipeline.py`. Публичная сигнатура: `def prepare_stage(self, request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]`. TARGET модели в `dataModel/artifacts/staging/preparedArtifact.py`: `ArtifactPrepareStageInput[C](content: C)` и `PreparedArtifact[C](content: C, descriptor: ArtifactRef)`, frozen/strict/extra-forbid. Format/version задаёт trusted binding с existing ArtifactFormatContract[C], согласованный для соответствующего producer; DAG не получает codec callback/backend. Формат не выбирается по содержимому и не подменяется producer. Подготовленный descriptor — ожидаемая identity, не доказательство записи, seal или удержания. PreparedArtifact не является capability; stage не доверяет вручную собранному descriptor. Публичные ошибки admission/mismatch требуют точного общего error mapping в ART-Q3; завершённый Error freeze этим именованием не объявляется.

Гарантия identity: `prepared.content is request.content`, затем stage использует тот же content. Prepared envelope может быть новым малым объектом; копирование содержимого ради границы запрещено. Pure prepare не открывает operation, не читает SQL и не создаёт holds. Concrete specialized модели и их validation проверяются без обхода model_construct.

Владелец — Artifacts. TARGET модуль `backend/app/application/artifacts/staging/artifactStageOpenPipeline.py`: конкретный класс `ArtifactStageOpenPipeline[C: bytes | BaseModel]`; TARGET интерфейс `IArtifactStageOpenPipeline` в `application/artifacts/contracts/artifactStageOpenPipeline.py`. Метод у обоих: `async stage(self, request: ArtifactStageInput[C]) -> ArtifactRef`. Фабрика composition root `make_artifact_stage_pipeline` связывает один existing `ArtifactFormatContract[C]`, версию и backend; они не передаются DAG как executable значения.

TARGET `backend/app/dataModel/artifacts/staging/stageInput.py::ArtifactStageInput[C]`: frozen/strict/extra-forbid модель с полями `lease: OperationLeaseRef`, `prepared: PreparedArtifact[C]`. Это замена прежнего content-поля, не дополнительная overload. Format key/version определяются зафиксированным binding pipeline и проверяются до записи. Каждый binding использует concrete specialization (например, bytes для BLOB); открытый BaseModel/Any или необъявленная union в DAG запрещены. Request содержит ссылку на prepared и его содержимое, а не копию; при реализации обязательна проверка identity вложенного content после admission/construction, в том числе с existing revalidate_instances=always. Если стандартное создание envelope копирует модель, это блокер реализации контракта, а не основание обходить validation через model_construct.

Для BLOB используется existing bytes-contract; произвольная доменная модель не подаётся existing BLOB backend. Доменный producer подготавливает canonical bytes и помещает их в свой named frozen output; DAG передаёт именно bytes field. Для SQL_ROWS используется конкретная frozen row-set модель owning-домена. PreparedArtifact[C] из принятого варианта 1 — только runtime envelope content+descriptor, не второй semantic/storage payload и не новый ref. Точные producer outputs каждого формата утверждаются у владельца, до их появления SQL_ROWS binding остаётся OPEN.

Успех — existing `dataModel/artifacts/references.py::ArtifactRef`: `kind, format_key, format_version, content_hash, nbytes, row_count`. Новый success DTO с повторением этих полей не вводится. Ref означает sealed/held результат данной подготовки; не READY всей операции и не published state.

#### Контракт ошибок двух операций — редакция для приёмки

2026-11-17. Конкретное предложение Artifacts; заменяет предварительный одноэлементный LEASE_NOT_WRITABLE roster. Типы ниже TARGET, не существующая реализация. Требует приёмки и согласования с владельцем shared lifecycle; не объявляет ART-Q3 закрытым.

Обе операции возвращают только success-тип из signatures выше; ожидаемые отказы передаются именованными application exceptions с concrete dataModel POJO. Не вводить одновременно альтернативный result union с теми же ошибками. Pure prepare_stage не имеет operation_id и не возвращает lease-ошибки.

**Field/input errors.** TARGET `dataModel/artifacts/staging/inputErrors.py`:

- `ArtifactInputIssueCode(StrEnum)`: `CONTENT_NOT_IMMUTABLE`, `CONTENT_TYPE_MISMATCH`, `FORMAT_BINDING_MISMATCH`, `DESCRIPTOR_MISMATCH`.
- `ArtifactInputIssue(FieldPathError[ArtifactInputIssueCode])`: existing обязательные code/path/message без дополнительных копий этих полей.
- `ArtifactInputError`: `issues: tuple[JsonFieldError | WireShapeIssue | ArtifactInputIssue, ...]`, непустой tuple, strict/frozen/extra-forbid; existing JsonFieldError/WireShapeIssue импортируются из validation/importIssues, не копируются.
- TARGET carrier `application/artifacts/staging/stageErrors.py::ArtifactInputRejected(error: ArtifactInputError)`. Это узкий доменный exception carrier, не новый общий error framework.

Structural errors переводятся существующим pydantic_issues механизмом; independent checks собираются existing ValidatorAggregationHelper. FieldRef/bind_field задают канонические пути относительно конкретной специализации input. Если невозможно проверить зависимое поле из-за malformed root, downstream check пропускается, но другие независимые ошибки собираются. Новый валидатор immutable payload не создаётся: reuse validate_immutable с размещением ошибки на content-пути. Backend/codec exception нельзя ловить общим except ValueError и объявлять input issue.

**Lifecycle refusals stage.** TARGET `dataModel/artifacts/staging/stageFailure.py::ArtifactStageFailure`: `operation_id: EntityUid`, `code: ArtifactStageFailureCode`. Enum: `LEASE_MISMATCH`, `ADMISSION_CLOSED`. TARGET `ArtifactStageRefused(failure: ArtifactStageFailure)` в том же application carrier-модуле.

| Ошибка | Точное условие / источник | Где допустима |
|---|---|---|
| CONTENT_TYPE_MISMATCH | Content не соответствует concrete registered specialization | prepare_stage и stage, до reserve |
| CONTENT_NOT_IMMUTABLE | Existing validate_immutable отверг содержимое | prepare_stage и stage, до reserve |
| FORMAT_BINDING_MISMATCH | prepared.descriptor kind/key/version не соответствует binding stage | stage, до reserve |
| DESCRIPTOR_MISMATCH | Вычисленный из prepared.content полный descriptor не равен prepared.descriptor | stage, до reserve |
| LEASE_MISMATCH | Persisted operation отсутствует либо полный OperationLeaseRef, построенный из authoritative record, отличается от входного | Typed replacement конкретной ветки SqliteArtifactCatalog._lease, сейчас строки 90–92; не предварительный cached read |
| ADMISSION_CLOSED | Lease binding совпал и persisted chain валиден, но PREPARING/open admission/current fence условие writable не выполнено | Typed replacement writable ветки _lease, сейчас строки 112–114; проверяется повторно внутри storage transactions |

LEASE_MISMATCH намеренно сохраняет существующую объединённую семантику missing/stale/world/kind/fingerprint mismatch. Не вводить отдельные detailed outcomes без owning решения. Отсутствие/повреждение persisted admission chain требует отдельной классификации владельцем lifecycle перед переносом: текущая реализация часть случаев включает в закрытый admission. Нельзя менять corruption semantics незаметно при типизации. Reserve/writer/seal обязаны распространять typed отказ из актуальной проверки; stage не парсит сообщения исключений и не подменяет защиту повторным read после отказа.

**Existing exception categories сохраняются:** OperationBusyError — занятый writer; PublicationInfrastructureError/CorruptBlobError — инфраструктура и corruption; UnknownCommitOutcome — неизвестный commit/rollback; CancelledError — отмена coroutine после owning drain. Codec programming/configuration errors не выдаются за пользовательский отказ. Ошибки недействительной registration/format binding factory должны выявляться в composition до runtime; неизвестный caller format не используется как runtime dispatcher, поскольку format фиксирован binding. Неперечисленные storage ValueError остаются пунктами inventory для owning classification, а не автоматически классифицируются новым enum.

**Почему не reuse OperationBindingMismatch:** existing `dataModel/publication/operationBindingMismatch.py` требует requested_request_fingerprint публикации, которого у stage нет. Подстановка фиктивного значения или копирование этого POJO недопустимы. ArtifactStageFailure описывает отказ конкретной staging operation, не новую persisted phase/terminal. ArtifactGcFailure относится только к GC, OperationCancelled — к durable отмене; ни один не является carrier staging refusal. PackPreparationError остаётся у Pack; междоменный mapping не переносит его в Artifacts.

**Ответственность новых типов:** InputIssue/InputError лишь хранят типизированные diagnostics, StageFailure — operation refusal, application exceptions лишь переносят эти POJO. Они не читают storage, не выбирают retry и не пишут terminal. Критерий отказа — любое такое поведение либо дубль existing validation field. Independent field checks не обходятся fail-fast для несвязанных полей; hash не вычисляется при malformed/mutable content.

**DoD prepare_stage:** вход проверен, descriptor соответствует binding и canonical содержимому, возвращён PreparedArtifact с исходной content identity; нет storage reads/writes/lease. **DoD stage:** проверено prepared соответствие, reserve/write/seal завершены и ref равен descriptor; результат не обещает READY/registration/publication. При отказе до reserve нет storage effects; при отмене/ошибке после reserve может остаться удерживаемый staged результат — cleanup принадлежит existing lifecycle, отказ не означает rollback всей файловой записи.

Открытые owning вопросы этой редакции сведены к точным пунктам: распространение typed refusals через все lease callers без поломки их контрактов; классификация оставшихся storage ValueError/corrupt-chain ветвей; правила логирования нового доменного carrier по existing error/logging policy. Полный публичный Error freeze требует их закрытия; основной roster больше не оставлен как неназванный «typed mapping».

##### Проверка распространения storage-отказов, 2026-11-17

Статический поиск всех `_lease(` в backend/app выявил общий, а не stage-only механизм. Callers: SqliteArtifactCatalog.reserve/seal; SqliteArtifactLeases.open_operation/assert_writable/writer, чтение состояния lease и finish_preparation; SqliteArtifactHolders.release/handoff; `db/repositories/sqlite/worldPack/climateRetention.py`. Поэтому выбрасывать stage-specific exception прямо из общего `_lease` без пересмотра shared-контракта нельзя. Предыдущая таблица задаёт семантическое соответствие ветвей, не разрешение такого изменения.

Предъявленное Publication требование: владелец shared lifecycle должен определить один typed отказ lease на самой проверке (reuse existing типа, если найден, иначе один owning POJO/carrier), включая writable и closed-admission использование. Stage должен передавать общий отказ либо согласованно адаптировать его без дублирующего error domain. Предварительный ArtifactStageFailure не создавать параллельно общему типу; окончательный выбор имени/формы зависит от ответа владельца. Код и signatures пока не изменяются.

| Источник | Фактическое поведение / целевая классификация для review |
|---|---|
| Catalog._lease: load record/chain | Existing corruption уже PublicationInfrastructureError; не перехватывать как input/lifecycle refusal |
| Catalog._lease: missing/stale; writable condition | Нужен typed shared отказ в authoritative check, не парсинг текста и не повторный read вне транзакции |
| Catalog._lease: writable=False | Release/handoff/climate retention требуют закрытого admission; ADMISSION_CLOSED сюда не подходит. Отдельная shared причина/поле требуемого режима — решение владельца, stage этот режим не использует |
| Catalog._find: тот же key/hash с другим descriptor | Existing ValueError также читается Pack readers как SOURCE_CORRUPT. Нельзя глобально заменить на DESCRIPTOR_MISMATCH входа stage; persisted collision/inconsistency требует owning classification |
| Catalog.seal / leases.writer: missing reservation/hold/claim | Внешний caller stage не передаёт reservation. После внутреннего reserve/claim нарушение — storage/invariant проблема либо конкретная lifecycle гонка; нельзя объявлять malformed public input по общему ValueError |
| BlobBackend.write: content отличается от reserved descriptor | Проверка повторяется после предварительного admission; при immutable content и правильном binding нарушение указывает на codec/backend inconsistency. Не маскировать как пользовательский DESCRIPTOR_MISMATCH после writes |
| Writer busy | Existing OperationBusyError распространяется отдельно; retry выбирает DAG |
| Blob IO/cancel и claim cleanup | Backend/lease cleanup используют shield/drain; не перехватывать CancelledError широким бизнес-carrier, не выдавать success при unknown outcome |

В проверенном stage-пути blanket except ValueError не найден. Но тесты `tests/snapshotCore/storage/artifacts/test_staging.py` и `test_leases.py` ловят ValueError в конкурентных циклах и используют assertRaises(ValueError). Shared typed изменение требует одновременного обновления этих expectations; сохранение ValueError-наследования не заменяет проверку конкретной причины. Pack `spatial/openWaterBlobReader.py` переводит catalog.read ValueError в SOURCE_CORRUPT; этот read-путь не является основанием менять классификацию всех catalog ошибок.

Результат проверки: публичные prepare/stage boundaries определены; прямой перенос двух stage-specific кодов в общий storage **отклонён**. Перед Error freeze нужен ответ shared lifecycle по перечисленным конкретным ветвям. Runtime-тесты в этой документальной проверке не запускались.

##### Зафиксированное состояние согласования — 2026-11-17

По поручению пользователя результат проверки и запрос точной контрактной дельты отправлены владельцу Publication/Artifacts в чат `01a1ea8d-2bdb-7152-bb40-925c86c041d8`, ход `01a1ead0-aa1a-7f51-a614-d8dbb40edbfb`. На момент отправки ответ ещё готовился; его итоговое рассмотрение и перенос в этот план не выполнены. Это отдельная итерация после первоначального owning review ART-Q1.

**Предъявлено со стороны Artifacts:** pure `prepare_stage(ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]` и `stage(ArtifactStageInput[C](lease, prepared)) -> ArtifactRef`; immutable content передаётся по ссылке, format/version задаёт trusted binding, descriptor вычисляется до открытия initial lease. Prepare не имеет IO; stage не открывает/завершает preparation, не вызывает другой public pipeline и не обещает READY. Input-errors proposal передан отдельно от shared lifecycle refusals.

**От Publication запрошены конкретные ответы:**

1. Совместимость descriptor → initial open → stage → reference-based register.
2. Точный replay-aware результат public open: READY не должен выдаваться как разрешение повторного stage.
3. Полный public register контракт: same lease/descriptor, registration и READY в одном UOW.
4. Единый owning typed lease refusal для всех callers, включая writable=False, missing/stale и corrupt/missing chain; без параллельного stage error domain.
5. Классификация reservation/hold/claim нарушений и descriptor collision в конкретных storage-ветвях.
6. Политика логирования новых carriers через existing logging/error infrastructure.

**До рассмотрения ответа:** ART-Q3 и ARCH-0 остаются OPEN; ArtifactStageFailure — предварительное предложение, не разрешение создания типа. Один факт отправки или совместимость направления не означают приёмку точных ошибок. Следующий шаг — прочитать owning ответ, сопоставить каждый пункт с предъявленной редакцией и внести единую дельту; не начинать код и не повторять общее согласование без конкретного расхождения.

Existing `PublicationInfrastructureError`, `UnknownCommitOutcome` и `OperationBusyError` сохраняются как инфраструктурные исходы, а `CancelledError` распространяется после writer drain. Не изобретать второй error framework, не возвращать ложный успех/повтор при неизвестном commit. Конкретный публичный Error-контракт не принимается до закрытия field/refusal mapping.

#### Внутренняя цепочка и ответственность

Принятая граница двух операций: prepare_stage admission → внутренний pure descriptor builder → PreparedArtifact; stage admission → внутренняя проверка descriptor/content/binding → reserve → backend.write → seal → ArtifactRef. Переиспользовать descriptor-алгоритм TypedArtifactStager через внутреннюю реализацию; stage не вызывает публичный prepare_stage, и prepare_stage не запускает stage. Повторная проверка hash при stage допустима и не означает копирования/повторного доменного вычисления. `finish_preparation`, publish, cancel и collect не вызываются автоматически из stage. Domain admission/выбор формата происходит в owning preparation и composition, а не в DAG или общих кодеках.

| Класс / модуль относительно backend/app | Ответственность, допустимые зависимости и эффекты | Проверка / признак отказа |
|---|---|---|
| TARGET ArtifactStageOpenPipeline, путь выше | Только порядок одной stage-операции, typed admission adapter и внутренний stager; storage effects через зависимости | Смена hash/backend не меняет pipeline; вычисление digest, доменная классификация или retry внутри него → FAIL |
| TARGET ArtifactPrepareStageOpenPipeline, путь выше | Одна pure операция подготовки через внутренний descriptor builder, без IO/lease | Открывает operation/пишет данные/запускает stage либо другой домен → FAIL |
| TARGET IArtifactStageOpenPipeline, путь выше | Только публичный контракт | Backend/CommitScope/SQL в signature → FAIL |
| Existing TypedArtifactStager, application/artifacts/staging/artifactStaging.py | Внутренний алгоритм descriptor и staging через registry/IArtifactStaging; сохраняется как implementation, не второй публичный entry | Не вызывает Pack/Source/Snapshot и не выбирает следующую операцию; foreign pipeline → FAIL |
| Existing ArtifactStagingService, тот же модуль | Storage lifecycle facade через catalog/lease/holder/ledger/GC/log; reserve/seal остаются internal для DAG | DAG вызывает reserve/seal по отдельности или сервис запускает domain preparation → FAIL |
| ArtifactFormatContract, contracts/formatBackend.py | Связывает content type, kind, versions и pure codecs/row_count | Callable производит IO/доменные вызовы → FAIL |
| ArtifactBackend, тот же модуль; ReadableBlobBackend, contracts/blobRead.py | Write/verify/delete и verified read за storage-контрактом, writer claim принадлежит write | Удержание writer перенесено в DAG либо write публикует мир → FAIL |
| ArtifactFormatRegistryBinding, registry/artifactRegistry.py | Проверка регистрации, codec/backend dispatch; не межоперационный routing | Подмена key/version либо callback запускает pipeline → FAIL |
| IArtifactCatalog / SqliteArtifactCatalog, storage/artifactCatalog.py / db/repositories/sqlite/artifacts/catalogStore.py | Guard, reservation, seal и catalog facts | Seal без согласованного descriptor; SQL в caller → FAIL |
| IArtifactLeases / SqliteArtifactLeases, storage/artifactLeases.py / db/repositories/sqlite/artifacts/leaseStore.py | Fences, admission, writer drain, READY и cancel; локальные транзакции | Принят stale fence, release до drain или own domain computation → FAIL |
| IArtifactHolders / SqliteArtifactHolders, contracts/holderPort.py / db/repositories/sqlite/artifacts/holderStore.py | Acquire/release/query/handoff в утверждённом scope | Разрыв atomic handoff на ноды или release чужого holder → FAIL |
| SqliteArtifactScope, db/repositories/sqlite/artifacts/access/artifactScope.py | Проверка borrowed scope и доступ к artifact tables | Самостоятельный внешний pipeline/UOW вместо borrowed scope → FAIL |
| SqliteOperationArtifacts, db/repositories/sqlite/artifacts/operationArtifacts.py | Read-only operation-holder projection | Writer/GC внутри read → FAIL |
| OperationLedger, application/publication/service/operationLedger.py | Bookkeeping через IOperationStore/leases, не оркестрация повторной подготовки | Recover запускает producer → FAIL |
| ContentAddressedBlobBackend, storage/artifacts/blobBackend.py | Физическое хранение bytes под DI root, writer lifecycle, verify/read/delete | Изменение published bytes, утечка пути в ArtifactRef или новая state machine → FAIL |
| ArtifactGarbageCollector, artifacts/lifecycle/artifactGc.py | Обработка переданных кандидатов под guards и проверка holders | Сам планирует следующий запуск/игнорирует holder → FAIL |
| ArtifactLifecycleLog, artifacts/logging/artifactLog.py | Типизированная диагностика через общий logging | Delivery меняет outcome либо логгер принимает business-решения → FAIL |
| ContractValidator / DagReadView / DAGExecutor, пути выше | Existing Engine admission/read/execution, не знают artifact codec и SQL | Передача копии, скрытая запись payload или storage алгоритм в Engine → FAIL |

Это реестр непосредственно прослеженного stage/lifecycle контура. Транзитивный publication/store/codec closure для новых lifecycle API и все SQL_ROWS adapters не объявляются проверенными. Эти API не расширяются данным предложением stage; полная приёмка домена остаётся OPEN до их отдельного анализа. Все orchestration-классы проверяются по class-size-limit.mdc независимо от размера: публичный pipeline не собирает descriptor, не выбирает recipe и не классифицирует чужие ошибки; эта работа остаётся в implementation/admission owner.

#### POJO: reuse и отсутствие дублирования

| Тип / dataModel/artifacts | Поля и ответственность | Disposition |
|---|---|---|
| ArtifactPrepareStageInput[C] / PreparedArtifact[C], TARGET staging/preparedArtifact.py | content; content + descriptor соответственно | Временная подготовка без storage guarantees, не второй canonical payload/ref; новый POJO требует проверки общего inventory |
| ArtifactStageInput[C], TARGET staging/stageInput.py | lease + prepared, вход сохранения | Не второй lease/ref: композиция existing identity и prepared; отдельно проверить все planned StageInput перед freeze |
| ArtifactStageFailure, TARGET staging/stageFailure.py | operation_id + LEASE_MISMATCH/ADMISSION_CLOSED | Не GcFailure и не cancellation; owning propagation review OPEN |
| ArtifactInputIssue / ArtifactInputError, TARGET staging/inputErrors.py | code/path/message; nonempty issues из existing structural и owning field diagnostics | Не копировать JsonFieldError/WireShapeIssue; классификация/агрегация в admission, не DTO |
| OperationLeaseRef, lifecycle/lease.py | operation_id/world_uid/kind/preparation_fingerprint/fence | Reuse; public capability, не CommitScope |
| StagingReservation, тот же файл | artifact_id/lease/ref | Internal; не выдавать DAG для управления фазами |
| ArtifactRef, references.py | kind/format_key/format_version/content_hash/nbytes/row_count | Единственная identity результата хранения |
| ArtifactFormatMetadata / ArtifactFormatRegistry, references.py | key/supported_versions; entries | Метаданные форматов, не runtime executable registry |
| OperationHolder / ArtifactRetentionHolder / SnapshotHolder / PinHolder, lifecycle/holders.py | tagged lease / artifact / snapshot / pin соответственно | Existing retention identities; не копировать в StageInput |
| VerifiedArtifactRef, тот же файл | ref/holder | Existing результат проверки удержания; stage не выдаёт его вместо ArtifactRef |
| OperationRecord, lifecycle/operation/record.py | operation/world/kind, preparation/publication fingerprints, phase/fence, leased_artifacts/terminal | Existing наблюдение lifecycle; не output каждой записи bytes |
| OperationCancelled, тот же файл | operation_id/reason REQUESTED | Durable cancellation, не coroutine cancellation |
| ArtifactGcFailure / GcReport, lifecycle/gc.py | failure_id/ref/stage/code/exception_type/message/errno/winerror; deleted/retained/failed | Existing GC results, не общий stage error carrier |

Перечисление не даёт разрешения менять эти формы, canonical IDs и codec manifests. Полная проверка foreign terminal POJO, логовых DTO и planned errors остаётся отдельным незакрытым пунктом общей приёмки, не скрытым PASS.

#### Конкретный existing consumer и междоменный маршрут

Поиск `TypedArtifactStager` в backend/app нашёл definition и Pack `application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation`. Функция сейчас кодирует manifest, собирает members, вызывает `StagedClimateFields.validate`, затем stager.stage, проверяет descriptor, вызывает finish_preparation и собирает PreparedPackCandidate. Это конкретная смешанная цепочка, которую нельзя просто переименовать в OpenPipeline.

TARGET disposition (уточнение по existing контракту): Pack-owned подготовка выдаёт canonical manifest bytes и members → DAG передаёт bytes в Artifacts stage → DAG передаёт ArtifactRef в Pack-owned проверку соответствия → согласованный Publication retention/READY entry → выдача PreparedPackCandidate только после подтверждённого READY. `dataModel/worldPack/activation/candidate.py` определяет candidate как результат durably finished preparation; existing finish_pack_preparation конструирует его после проверки record.phase == READY и полного binding. Конструирование candidate до READY запрещено этим смыслом, даже если POJO технически допускает создание без чтения storage. Точный владелец финальной выдачи и новые публичные signatures ожидают owning-уточнения ART-Q1; промежуточный дублирующий candidate DTO не вводится. Прямой вызов stage из Pack удаляется на согласованном cutover. Проверка соответствия manifest bytes/ref и membership остаётся Pack. Source closure/adoption и READY сохраняют owning-протокол [Pack adoption](./pack-source-adoption-publication-response-2026-11-14.md); stage сам их не доказывает.

Протокол междоменного CRUD: потребитель Artifacts.stage требует подготовленный content от Pack; existing функция не предоставляет отдельного публичного prepare-контракта. Обратный потребитель Pack требует ArtifactRef, формат/версию/hash/nbytes и membership evidence; exact public Pack consumer также ещё не определён. Поэтому PACK-PREPARED-API — OPEN: нужен owning Pack контракт с конкретными POJO/ошибками. Не назначать эти методы Pack из Artifacts. Другие доменные producer contracts нельзя вывести из наличия registry.

Согласованных NodeId для этой новой границы нет. Маршрут выше — proposal операций, не утверждённый граф. По GEN-NODE-JOINT-REVIEW привязка остаётся OPEN до совместной карты и согласования; никаких invented NodeId и прямого Pack→Artifacts pipeline как обхода.

#### CRUD disposition и остаточные blockers

| Объект | Create | Read | Update | Delete |
|---|---|---|---|---|
| Immutable artifact data | TARGET ArtifactStageOpenPipeline.stage; Error mapping OPEN | Existing ReadableBlobBackend.read_verified — storage API, не готовый concrete domain CRUD | Нет принятого публичного метода; replacement по тому же hash запрещён, но это не исключение из правила CRUD | Existing collect → GcReport — guarded GC, не универсальное разрешение удалить held content |
| Artifacts settings | Не определён owning settings POJO/API | Нет публичного контракта | Нет публичного контракта | Нет публичного контракта |

Root/backend registration — existing composition configuration, а не основание самовольно распространять исключения Cache/Pack на Artifacts. Для полной приёмки необходимо либо разработать полный owning CRUD с конкретными моделями, либо получить явное узкое исключение и синхронизировать правило/ТЗ. Это решение не подменяется созданием фиктивных методов и вымышленных настроек.

#### Матрица архитектурной приёмки этой редакции

| Обязательный критерий | Вывод / основание |
|---|---|
| Нет выбора следующих операций в pipeline | TARGET соблюдает: stage не finish/publish/retry; existing Pack chain требует cutover |
| Нет скрытого запуска | TARGET только DAG; фактический новый binding отсутствует, статус OPEN |
| Нет прямых междоменных pipeline calls | TARGET соблюдает; existing Pack→stager под замену, точный Pack API OPEN |
| Каждый класс и ответственность | Stage contour описан; полный foreign/lifecycle closure OPEN |
| Public/Input/Output/Error и implementation | Stage proposal конкретизирован; typed admission/refusal mapping OPEN |
| Неизменность согласованного порядка | Выбор публичного stage и in-memory границы подтверждён; per-route/node порядок OPEN |
| CRUD данных и настроек | FAIL для приёмки всего домена: матрица содержит незакрытые операции |
| Междоменный CRUD-протокол | Pack inputs/consumers выявлены, owning public contracts отсутствуют — OPEN |
| POJO/field/logic errors без дублей | Reuse установлен для основного контура; полный анализ planned/foreign errors OPEN |
| Именование | TARGET класс, интерфейс и модули имеют OpenPipeline |
| Замена implementation без правки orchestration | Целевой контракт изолирует backend/codec; доказательство substitution остаётся проверкой реализации |

**Вердикт: ARCH-0 ещё не принят.** Конкретные blockers: PACK-PREPARED-API, GEN-NODE-JOINT-REVIEW, stage field/refusal contract, complete POJO/class closure и CRUD disposition. In-memory граница подтверждена пользователем; durable интеграция сознательно остаётся вне первой поставки. Это проработанное предложение с выявленными зависимостями, не декларация полного соответствия.

2. **Контракты и нормативная синхронизация.** По принятой архитектуре синхронизировать ТЗ/правила и точные публичные контракты, ошибки, prepared payload и гарантии владения. Проверить reuse TypedArtifactStager; не создавать второй staging. Сохранять порядок согласованных contract groups, переводить producers/consumers согласованно.
3. **Реализация публичного staging.** Реализовать принятый конкретный API поверх единой инфраструктуры; закрыть успешное сохранение, отказ, отмену, конкурентную запись и идемпотентность. Не публиковать Pack/Snapshot из stage.
4. **Перевод preparation и DAG binding.** По согласованному inventory домен возвращает объект без staging; DAG передаёт именно этот объект публичной операции. Перевести composition/debug/worker callers и убрать прежний путь в том же согласованном срезе. Изменение DAG требует явного разрешения на реализацию; этот план его не выдаёт.
5. **Lifecycle и межплановая интеграция.** Подключить согласованные cancel/recover/GC и публикацию без разрыва атомарного holder handoff. Не выводить из успешного stage доказательство Source completeness либо разрешение на публикацию. Не реализовывать открытые соседние контракты по предположению.
6. **Техническая приёмка.** Проверить весь согласованный маршрут, заменяемость реализации, отсутствие старой скрытой оркестрации и сохранение существующих storage-инвариантов. Зафиксировать revision, команды и результаты; отсутствие production binding не маскировать локальными тестами.

Детальное разбиение этапов 2–6 и их классы/методы фиксируются в ARCH-0; сейчас это последовательность подготовки поставки, не готовый список кодовых изменений.

## Проверки целевого поведения

### Реестр открытых вопросов ARCH-0 — 2026-11-17

Все вопросы ниже имеют статус **OPEN**. Закрытие фиксируется здесь ссылкой на точный owning-контракт/решение и проверкой его переноса в архитектуру. Список не означает, что все ответы должен подготовить пользователь: исследование и контрактные предложения выполняются в ARCH-0, пользователь принимает решения и совместный DAG-дизайн.

По ART-Q1 2026-11-17 получены ответы отдельных чатов: Pack `01a1ea8d-1751-70d3-970e-df20d38779f4` и Publication/Artifacts `01a1ea8d-2bdb-7152-bb40-925c86c041d8`. Каждый сначала сверил собственные доменные источники и код. Результат уточнения ниже не означает приёмку предложенного API; ART-Q1 остаётся OPEN.

#### ART-Q1 — результат уточнения владельцев

**Existing, подтверждено обоими:** `finish_preparation(lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord` проверяет writable lease, отсутствие writers, уникальный набор refs, его точное равенство operation holds и seals; закрывает admission и записывает READY в собственной транзакции. Это не доказательство Source closure или корректности Pack manifest. `SqliteArtifactLeases._transaction` требует unbound connection: bind(scope) вокруг existing finish не присоединяет его к внешнему UOW, а отвергается.

`PreparedPackCandidate(operation_id, manifest, preparation_fingerprint)` выдаётся только после confirmed READY и exact Pack checks. Его POJO validator проверяет descriptor, не durability. Existing finish_pack_preparation — внутренний helper; Pack-проверка нашла callers в тестах spatial_pack, production caller не подтверждён. Поэтому не считать его уже включённым публичным pipeline. Часть Pack write-классов уже реализована, несмотря на исторические PROJECT-пометки: статусы проверять по declarations, а не переносить целиком из старого плана.

**Pack proposal, ещё не принят:** `PackManifestPreparationOpenPipeline` / `IPackManifestPreparationOpenPipeline` в `application/worldData/pack/preparation/packManifestPreparationOpenPipeline.py` предлагает prepare_manifest, validate_staged_manifest и confirm_preparation. Первый возвращает материал для stage; второй проверяет descriptor/hash/nbytes/members; третий выдаёт existing candidate после доверенного чтения READY и проверки world/kind/operation/fence/fingerprint/полного набора holds. Произвольный OperationRecord от caller не является доказательством durability. Распределение этих методов по concrete public classes и интерфейсам требует проверки ответственности перед freeze.

Предлагаемый `dataModel/worldPack/preparation/manifestStageMaterial.py::PackManifestStageMaterial` содержит operation_id, world_uid, preparation_fingerprint, content: bytes, members: tuple[ArtifactRef, ...] (полный closure без самого manifest). Он не утверждает READY и не является вторым candidate. Его точный binding с lease/current fence и принятым final request остаётся OPEN; DTO пока не утверждать. Existing PackPreparationInput здесь нельзя считать окончательно зафиксированным новым prepare request только по имени из предложения.

Pack рекомендует reuse `PackPreparationFailure` / `PackPreparationError(reason, issues)` из `dataModel/worldPack/preparation/errors.py`, включая existing field/artifact/budget issues, вместо новых зеркальных CandidateError. Mapping manifest mismatch, READY mismatch и lifecycle refusal остаётся OPEN; infrastructure/cancel/unknown outcome не превращать в validation failure.

**Publication proposal, ещё не принят:** internal `IPackPreparationRetention.adopt_and_finish(request: PackPreparationRetentionInput) -> OperationRecord | SourceFailure`. Input: lease, closures: tuple[SourceClosureAdoption, ...], operation_members: tuple[ArtifactRef, ...]; SourceClosureAdoption: request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef, ...]. Fingerprint брать из lease, отдельное поле не дублировать; PackPreparationBody/recomputation остаются Pack-owned.

Для единого UOW требуется proposed `SqliteArtifactLeases.finish_preparation_scoped(scope: CommitScope, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord`: borrowed scope без собственного commit, общий алгоритм проверки с standalone finish. Порядок: validation/binding → writer UOW → повторная проверка admission/drain → все internal Source adopts → scoped members/seals/READY → confirmed commit → результат. SourceFailure требует rollback всех новых target holds перед возвратом; source holds не снимаются. Unknown commit/rollback остаётся UnknownCommitOutcome.

Internal retention port **не является готовым публичным DAG entry**. Требуются явная внешняя lifecycle boundary, её Input/Output/Error и trusted binding. Нельзя закрыть этот пробел прямым Pack→public Publication pipeline, callback или передачей internal scoped API в ноду. Proposed PackPreparationRetentionError roster и Pack mapping не приняты.

**Рекомендуемый порядок операций:** Pack prepare_manifest → Artifacts stage → Pack validate_staged_manifest → согласованный внешний Publication entry (внутри atomic adoption→READY) → Pack confirm_preparation → отдельная activation. Это proposal, не утверждённые ноды. Stage не завершает operation и не выбирает следующий вызов.

**Незакрытые зависимости:** final Pack request и trusted material/fence binding; Source authority из base/capture context и scoped resolver/pins (VerifiedArtifactRef и произвольный holders lookup не дают authority); scoped finish; обязательный READY producer/version binding; durable exact candidate mapping для replay; внешний public lifecycle entry и ошибки; владелец/освобождение READY_INACTIVE manifest. OperationRecord не хранит роль manifest: recovery не может выбирать первый ref подходящего формата или пересобирать manifest. Retention holder manifest→children не удерживает сам root. Политика in-memory передачи payload не отменяет durable-инварианты записанного READY.

Ответы владельцев уточняют предмет следующего согласования; полного закрытия ART-Q1 и ARCH-0 нет.

| ID | Вопрос, требующий ответа | Владелец ответа / основание закрытия | Что блокирует |
|---|---|---|---|
| ART-Q1 — PACK-PREPARED-API | Какой конкретный публичный Pack prepare-метод выдаёт canonical manifest bytes и members без staging? Какой метод принимает полученный ArtifactRef и проверяет соответствие manifest перед подготовкой candidate? | Pack: модули, конкретные классы, полные сигнатуры, POJO полей/ошибок и порядок; согласование с owning Pack adoption/READY-контрактом | Перевод finish_pack_preparation и приёмку междоменного маршрута |
| ART-Q2 — GEN-NODE-JOINT-REVIEW | Какие согласованные ноды вызывают preparation, stage и consumer; каковы их I/O/Error, deps, условия запуска и lifecycle? Как гарантируется обычный in-memory путь без workflow JSON round-trip? | Пользователь совместно с Engine/DAG: карта маршрута и точные контракты по GEN-NODE-JOINT-REVIEW; агент не назначает NodeId самостоятельно | DAG binding, порядок операций и приёмку интеграции |
| ART-Q3 — STAGE-ERRORS | Какие existing typed field errors обслуживают вход stage? Каким конкретным typed исходом lease adapter сообщает отказ admission, чтобы не классифицировать arbitrary ValueError как LEASE_NOT_WRITABLE? | Artifacts/Publication: полный Input/Output/Error, причины, поля, mapping по конкретным call sites; reuse общей validation infrastructure | Freeze публичного stage и его реализацию |
| ART-Q4 — CLASS-POJO-CLOSURE | Каков полный closure затронутых классов и POJO, включая publication store/codec, foreign terminal types, SQL_ROWS adapters и planned errors? Где доказано отсутствие повторяющихся ответственностей и DTO? | Исследование ARCH-0: полный реестр модулей/полей, dependencies/effects, критерии отказа каждого класса, сопоставление existing/planned типов | Полную архитектурную приёмку; не заменяется начальным inventory |
| ART-Q5 — DATA-CRUD | Какие конкретные публичные read/update/delete методы Artifacts дополняют stage? Каковы допустимые update/delete для immutable и held artifacts? Требуется ли узкое исключение из общего CRUD-правила? | Artifacts готовит контрактное предложение; пользователь принимает семантику либо явное исключение с нормативной фиксацией | Приёмку CRUD и домена целиком; immutable само по себе не освобождает от правила |
| ART-Q6 — SETTINGS-CRUD | Есть ли у Artifacts доменные изменяемые настройки, каков их named POJO и полный CRUD? Если root/registration являются только composition configuration, какое точное исключение требуется? | Artifacts инвентаризирует configuration; пользователь принимает границу и при необходимости исключение. Исключения Cache/Pack автоматически не применяются | Приёмку настроек и домена целиком |
| ART-Q7 — PAYLOAD-IDENTITY | Сохраняет ли создание/admission конкретного ArtifactStageInput[C] identity вложенного content при existing revalidate_instances=always? Какие concrete frozen producer outputs используются для каждого формата? | Artifacts и owning producers: точные POJO и воспроизводимая проверка identity/immutability; без model_construct, Any и скрытого копирования | Freeze input-контракта и утверждение передачи того же объекта |
| ART-Q8 — NORMATIVE-SYNC | Какие точные положения Snapshot ТЗ и DAG-правила заменяют старое staging-inside-materialization, не меняя прочих утверждённых порядков? Как новый срез согласован с ARCH-0 Snapshot? | Artifacts/Snapshot: конкретная нормативная редакция по уже принятому пользователем решению о публичном staging | Согласованность источников и переход к реализации |

**Уже решено, повторно не спрашивать:** staging — публичная атомарная операция; управление вызовами — DAG; передаётся тот же объект по ссылке; первая поставка ограничена одним процессом; архитектура и её приёмка идут первыми. Durable/checkpoint-путь остаётся отложенной интеграцией Engine, не условием для расширения текущего scope. ART-Q2/ART-Q7 проверяют реализацию принятой границы, а не пересматривают эти решения.

### Сценарии проверки

- Preparation и stage получают один объект по identity; между нодами нет encode/decode ради транспорта. Storage encode проверяется отдельно.
- Недопустима мутация payload между hash и записью; контракт обеспечивает стабильность bytes и descriptor.
- Stage возвращает ref только после принятого seal; частичная запись не становится опубликованной.
- Cancel во время записи, повтор cancel, повтор staging, restart и unknown commit сохраняют утверждённые lifecycle гарантии.
- GC не удаляет held/writing результаты; публикация и handoff не имеют окна без удержания.
- Ошибка stage не запускает последующего потребителя; retry выбирает DAG по типизированному исходу.
- Существующие snapshotCore artifact/atomicity/typing и logging проверки остаются регрессионной базой; точные команды определяются по изменённым маршрутам после ARCH-0. Новых runtime-прогонов при составлении этого плана не было.

## Зависимости и границы

[D2](./world-domain-artifacts-cancel-gc-d1.md) и [его проверка](./artifacts-d2-physics-i0-joint-verification.md) — существующая база, не основание переписывать cancel/GC заново. [Pack adoption](./pack-source-adoption-publication-response-2026-11-14.md), [Source mutation](./source-mutation-artifacts-publication-response-2026-11-13.md) и INITIAL-REGISTER в Snapshot сохраняют собственных владельцев и статусы. Новый план не объявляет их закрытыми и не переопределяет их протоколы.

Вне текущего поручения: код, SQL-миграции, перенос папок ради нового названия домена, новые storage/ledger/holder механизмы, коммит и запуск backend. Сейчас создаётся только план; следующий содержательный шаг — ARCH-0.
