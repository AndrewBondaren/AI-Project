# Pack activate — конкретизация diagnostics и replay

2026-11-13, PROJECT. Продолжение [activation trace](pack-activation-refusal-trace.md), без изменения runtime и политики исходов ТЗ. Полный scoped atomic binding остаётся отдельной интеграционной задачей.

## Публичные типы

В уже предложенном `dataModel/worldPack/activation/refusal.py`:

- `PackActivationIssueCode` — конкретный StrEnum кодов Pack admission, предлагаемых ниже.
- `PackActivationIssue(FieldPathError[PackActivationIssueCode])` — именованный subclass без копирования code/path/message, frozen/strict/extra forbid/revalidate always через owning carrier.
- `PackActivationRefusal(operation_id: EntityUid, request_fingerprint: RevisionHex, diagnostics: tuple[PackActivationIssue, ...])` — frozen/strict/extra forbid/revalidate always, diagnostics обязателен и непуст. Exact class diagnostics перепроверяется; произвольный FieldPathError или Snapshot issue не принимается.

У refusal нет отдельного reason, поскольку варианты уже выражены issue.code. Не копировать сюда preparation union: структурные JsonFieldError/WireShapeIssue относятся к admission входа до OWNER, а durable SnapshotApplyResult принимает field diagnostics. Путь PackActivationIssue строится от конкретного PackActivationInput через CheckedPath. Публичный тип не содержит claim/fence/lease/backend и не запускает эффектов.

## Различение исходов и предлагаемые коды

| Условие | Исход / код | Путь и граница |
|---|---|---|
| В request.expected уже gameplay_started=True | PackActivationRefusal, `EXPECTED_GAMEPLAY_STARTED` | expected.gameplay_started; после OWNER, до доменных записей |
| Декодированный manifest другого мира относительно expected | PackActivationRefusal, `MANIFEST_WORLD_MISMATCH` | manifest; чужого world_uid внутри Input.manifest нет, синтетический manifest.world_uid запрещён |
| Verified bytes manifest нарушают согласованный Pack codec/schema/связность | PackActivationRefusal, `INVALID_MANIFEST` | manifest; только установленное нарушение, не произвольный exception backend |
| Подтверждённо отсутствует обязательный ref кандидата | PackActivationRefusal, `CANDIDATE_ARTIFACT_MISSING` | manifest как корень представленного кандидата; точная дочерняя причина проверяется внутри admission |
| Подтверждено отсутствие обязательного seal | PackActivationRefusal, `CANDIDATE_ARTIFACT_UNSEALED` | manifest; не выводится из объединённого SOURCE_UNAVAILABLE |
| Подтверждено отсутствие обязательного удержания | PackActivationRefusal, `CANDIDATE_HOLD_MISSING` | manifest; чужие holds не освобождаются |
| expected pregame, но полный CAS не совпал с observed, включая старт gameplay | PackActivationResult(READY_INACTIVE) | Не issue и не REJECTED; сохраняются кандидат и удержания |
| Existing terminal ACTIVE/READY_INACTIVE/REJECTED/Cancelled для той же identity | Исходный результат replay | Без нового CAS или проверки текущей доступности уже освобождённых bytes |
| Busy, infrastructure, cancellation, unknown commit | Existing owning исход | Не превращается в PackActivationIssue; unknown commit требует recovery до записи отказа |

Все коды выше — предложения точных имён, не существующий enum runtime. Нарушения descriptor/типа самого запроса отклоняет schema admission. Совпадение operation_id с другой preparation/publication identity, отсутствие подготовки или не-READY до OWNER не записываются как durable REJECTED чужой/несуществующей операции. Точные existing exception bindings этих pre-claim случаев требуется отдельно предъявить; данный документ не придумывает для них успешный claim ради возможности сохранить отказ.

Если отказ установлен после начала доменных изменений, record_refusal разрешён только после подтверждённого rollback и в допустимой lifecycle фазе по owning контракту. Ошибка handoff сама по себе не доказывает CANDIDATE_HOLD_MISSING; infrastructure и неизвестный исход не классифицируются по тексту исключения.

### Основания для кодов после OWNER и порядок проверок

Сверка 2026-11-13: `ReadableBlobBackend.read_verified` обещает точные bytes по size/digest; `CorruptBlobError` наследует PublicationInfrastructureError. ContentAddressedBlobBackend оборачивает OSError в PublicationInfrastructureError, а неизвестный/превышенный read budget пока сообщает ValueError. Следовательно, general catch этих исключений с возвратом INVALID_MANIFEST/CANDIDATE_ARTIFACT_MISSING недопустим.

| Код после OWNER | Достаточное основание | Что этим кодом не является |
|---|---|---|
| EXPECTED_GAMEPLAY_STARTED | typed request.expected.gameplay_started=True | gameplay_started=True у observed head после CAS race |
| MANIFEST_WORLD_MISMATCH | owning decoder вернул manifest с другим world_uid | предположение о мире по пути файла или имени storage key |
| INVALID_MANIFEST | verified bytes разобраны Pack codec и установлено нарушение schema/связности manifest | CorruptBlobError, generic ValueError, превышение resource budget, ошибка configuration или I/O |
| CANDIDATE_ARTIFACT_MISSING | Принятый storage/catalog port явно подтвердил отсутствие обязательного ref | OSError/PublicationInfrastructureError либо потеря соединения; физический FileNotFoundError не переводится автоматически без owning mapping |
| CANDIDATE_ARTIFACT_UNSEALED | Под защищённым admission is_sealed конкретного существующего ref=False | недоступный catalog или отсутствующий ref |
| CANDIDATE_HOLD_MISSING | Под защищённым admission is_held конкретного ref/точного обязательного holder=False | произвольный отказ handoff либо неопределённый результат commit |

Внутренняя operation сначала проверяет независимый expected predicate; далее descriptor/доступность → seal/hold → verified read → semantic decode → связи root/children. Зависимые проверки не выполняются при отсутствующей предпосылке. Независимые уже доступные diagnostics собираются existing ValidatorAggregationHelper в определённом порядке (expected, root manifest, затем refs в принятом closure order); не запускать дополнительные I/O только для увеличения числа сообщений после инфраструктурного отказа. Один факт не даёт одновременно MISSING, UNSEALED и HOLD_MISSING.

Для child paths публичный Input содержит только root manifest ref, поэтому path=manifest означает непригодность предъявленного кандидата целиком. В message можно указать конкретный child ref для диагностики, но caller не извлекает identity из текста. Машинные поля дочернего контекста не вводятся без потребителя; синтетические manifest.shards[i] не строятся на ArtifactRef.

Набор из шести post-OWNER кодов описывает перечисленные подтверждённые доменные predicates, а не любой возможный сбой. Для resource cap семантика уже согласована в разделе ниже: временная невозможность проверки не становится REJECTED. Остаток — точный owning exception/lifecycle binding, а не повторный выбор исхода. Нельзя назвать такой случай INVALID_MANIFEST или заимствовать read-part refusal. Ошибки конфигурации/codec programming также не становятся durable REJECTED.

RefusalCodec требует однородную допустимую группу diagnostics: четыре согласованных pre-claim кода — только незаписываемый отказ, шесть post-OWNER — кандидаты на REJECTED при законном claim/rollback. Смесь групп отклоняется как дефект формирования. to_terminal/from_terminal проверяют весь tuple, а не первый issue; неизвестный enum value и чужой subtype не пропускаются. При отказе записи terminal операция не сообщает вызывающему durable успех: действует owning infrastructure/recovery исход. Формирование корректного POJO ещё не доказывает commit.

### Бюджет activation: согласованная семантика (2026-11-13)

Фактический PackActivationInput содержит только inherited candidate fields и expected. PackPartReadBudget в нём нет. Бюджет публичного read_part не является автоматически бюджетом activate; добавление нового поля запроса не требуется текущим решением и не выполнено. Проверка отсутствия существующего специализированного resource exception в просмотренных publication/artifacts контрактах не даёт основания использовать generic ValueError как публичный результат.

Согласовано пользователем: различать два основания:

1. Payload нарушает закреплённый контракт формата, подтверждённый владельцем: это непригодность данных по owning admission. Pack не превращает произвольную настройку deployment в такой контракт. Конкретное отображение нарушения зависит от роли и owning проверки; существующий structural resource signal сам по себе не доказывает нарушение схемы.
2. Поддержанный payload не удалось проверить в пределах ресурсов этой попытки: это незавершённая проверка, а не доказательство невалидности кандидата. Не записывать REJECTED, не выдавать READY_INACTIVE/ACTIVE, не менять manifest и не освобождать его holds как при отказе от кандидата. Согласованная семантика — отдельный типизированный отказ исполнения по ресурсу, без нового terminal вида; точный owning exception binding ещё должен быть предъявлен.

До OWNER известное превышение может остановить попытку без claim. После OWNER простой возврат exception не возвращает APPLYING в READY: точный lifecycle продолжения/восстановления обязан определить Publication/Artifacts binding. Нельзя обещать немедленный retry, самостоятельно менять phase или запускать recover внутри OpenPipeline. Unknown commit по-прежнему требует существующего recovery и не подменяется resource отказом.

Семантика согласована и синхронизирована с ТЗ: временная невозможность проверить отличается от окончательного отклонения данных. Новые числа лимитов, budget в PackActivationInput и класс исключения здесь не вводятся. Открыты конкретный owning exception и lifecycle binding, а не повторный выбор исхода. Проверки реализации: resource отказ до OWNER не создаёт claim; после OWNER не пишет REJECTED, не теряет holds и не обещает READY без подтверждённого lifecycle перехода; UnknownCommitOutcome сохраняет собственный recovery. Runtime и тесты не изменялись.

## Отказы до OWNER: согласованное решение (2026-11-13)

Existing OperationLedger.read возвращает OperationRecord | None без создания операции. SqliteOperationStore.claim_publication при None, напротив, создаёт APPLYING; при несовпадении world/kind/preparation fingerprint или уже связанного publication fingerprint бросает общий ValueError; для PREPARING/APPLYING/RECOVERY_REQUIRED возвращает PublicationBusy. Поэтому один вызов общего claim не является достаточным Pack admission READY-кандидата.

Согласовано пользователем: переиспользовать PackActivationRefusal для установленных доменных отказов до OWNER, без второго public DTO. request_fingerprint в нём — вычисленная identity представленного запроса, не свидетельство записи publication binding. До OWNER такой отказ возвращается без record_refusal, terminal и мутации чужой/несуществующей операции. Повтор заново проверяет admission: например, подготовка могла завершиться. После OWNER действует прежнее правило durable REJECTED и точного replay. Durable status не выводится из одного типа public refusal; конкретные коды ниже относятся к pre-claim условиям. ТЗ синхронизировано; runtime не изменён.

| Подтверждённое наблюдение | Предлагаемый исход | Путь |
|---|---|---|
| read(operation_id) вернул None | PackActivationRefusal, `PREPARATION_NOT_FOUND` | operation_id; claim не вызывается |
| kind/world durable записи не соответствуют запросу Pack | PackActivationRefusal, `OPERATION_IDENTITY_MISMATCH` | operation_id либо expected.world_uid по установленному predicate |
| Preparation fingerprint не совпал | PackActivationRefusal, `PREPARATION_IDENTITY_MISMATCH` | preparation_fingerprint |
| Уже связанный publication fingerprint отличается от computed request fingerprint | PackActivationRefusal, `ACTIVATION_IDENTITY_MISMATCH` | operation_id: он уже связан с другим полным запросом; fictitious request_fingerprint field во входе не создаётся |
| Та же identity, phase PREPARING/APPLYING/RECOVERY_REQUIRED | Existing OperationBusyError | Не NOT_READY refusal и не закрытие операции; восстановление/повтор выбирает DAG по owning контракту |
| Та же identity, TERMINAL | Existing terminal mapping | Сначала identity, затем replay; новые holds/CAS не требуются |
| Та же identity, READY | Допуск к остальному candidate admission и claim | Сам по себе phase READY не доказывает role manifest и полный closure |

OperationCancelled может не иметь publication_fingerprint: existing cancellation до claim не привязана к expected/manifest запроса активации. Проверяются world/kind/operation/preparation identity; возвращается исторический OperationCancelled по ТЗ. Нельзя требовать отсутствующий publication fingerprint ради replay отмены или синтезировать его запись. При наличии publication binding он обязан совпадать с текущим запросом.

**Гонка read→claim.** Read — предварительное наблюдение, не блокировка. Claim повторно сравнивает immutable identity и может вернуть BUSY/TERMINAL вместо OWNER; это штатно обрабатывает внутренняя operation, не wrapper pipeline. Generic ValueError claim нельзя переводить в ACTIVATION_IDENTITY_MISMATCH по message: владелец Publication должен предъявить typed конфликт immutable binding или другой точный atomic исход. Аналогично гарантия «не создать исчезнувшую подготовку» требует подтверждения lifetime durable record либо existing-only claim binding; предварительный read сам её не доказывает. Эти зависимости фиксируются владельцу, Pack не переписывает общий store в текущем срезе.

Проверки: unknown ID не создаёт записи; PREPARING даёт busy; changed identity не возвращает чужой terminal; гонка READY→APPLYING даёт busy, READY→TERMINAL восстанавливает исход; cancellation без publication fingerprint возвращается по preparation identity; generic ValueError не становится доменным refusal; pre-claim refusal не вызывает record_refusal. Exact role manifest внутри READY проверяется отдельным candidate binding, leased_artifacts membership не заменяет роль.

## Pure mapping и восстановление

Предлагаемый внутренний `PackActivationRefusalCodec` в `application/worldData/pack/encoding/activationRefusalCodec.py` имеет две pure функции: `to_terminal(refusal: PackActivationRefusal) -> SnapshotApplyResult` и `from_terminal(terminal: SnapshotApplyResult) -> PackActivationRefusal`. Первая сохраняет operation_id/request_fingerprint и исходный tuple concrete diagnostics, ставит category=REJECTED и committed=None. Вторая требует REJECTED, committed=None, непустой tuple точных PackActivationIssue и сохраняет порядок. Она не превращает CONFLICT или чужие Snapshot diagnostics в Pack refusal. Неподдерживаемый terminal — ошибка восстановления, не новый пользовательский отказ.

Внутренняя activation operation до from_terminal проверяет OperationRecord.kind=PACK_ACTIVATION, world/operation/preparation identity и publication fingerprint относительно того же полного запроса. Storage discriminator `snapshot_apply` описывает envelope и не заменяет проверку kind записи операции. Проверки Record и public request не дублируются полями нового DTO в codec. После восстановления не выполняются новый claim OWNER, CAS или доменная валидация по latest head.

Для сохранения используется existing OperationLedger.record_refusal → SqliteOperationStore → StoredTerminalCodec. Последний уже проверяет checksum, row/body operation_id и category, но не заменяет проверку принадлежности запроса конкретной Pack-операции. Exact PackActivationIssue и его enum регистрируются в canonical schema extension, передаваемой existing StoredTerminalCodec. Регистрация FieldPathError не покрывает subclass; стирать subtype нельзя. Новые numeric IDs здесь не назначаются — это следующий encoding срез.

## Обязанности и проверка

PackActivationIssue/Refusal — immutable данные; RefusalCodec — чистое преобразование, без I/O и выбора следующего workflow; внутренняя activation operation — admission, правильная lifecycle точка сохранения и проверка replay identity; ledger/storage — durable запись и целостность terminal. OpenPipeline только делегирует один раз, DAG выбирает дальнейшие действия.

Обязательные случаи: expected.gameplay_started=True против CAS race со стартом игры; два независимых доступных admission issues в стабильном порядке; subtype/code/path/message/order сохраняются после restart; replay после смены head/release без CAS/read bytes; same operation_id с другим request не получает старый terminal; Snapshot CONFLICT/чужой issue/неверный kind не восстанавливаются как Pack refusal; unknown commit не записывает REJECTED. Тесты не запускались.

Статус: shape refusal и durable mapping соответствуют проекту ТЗ; применение refusal до OWNER и четыре pre-claim кода согласованы 2026-11-13. Сверка шести post-OWNER predicates с имеющимися ports завершена ниже; новые коды не требуются для рассмотренных оснований. Typed atomic conflict/resource/lifecycle binding владельца Publication и scoped atomic implementation ещё открыты. Canonical IDs/vectors и READY recovery ведутся в отдельном serialization-плане, не блокируют независимый Pack scope. Runtime не принят; новый storage или изменение READY_INACTIVE policy не требуются.

Ограничение pure mapping: to_terminal не применяется к четырём pre-claim кодам и должно отклонять такой вызов; наличие PackActivationRefusal само по себе не разрешает durable запись. from_terminal также не восстанавливает pre-claim codes из REJECTED как корректный Pack terminal. Законность записи после OWNER дополнительно проверяется lifecycle port. Проверки включают попытку сохранить PREPARATION_NOT_FOUND как terminal и повтор pre-claim отказа после появления/завершения подготовки.

## Итоговая сверка post-OWNER admission с кодом

Проверены [PackActivationInput](../../backend/app/dataModel/worldPack/activation/input.py), [OperationLedger](../../backend/app/application/publication/service/operationLedger.py), [SqliteOperationStore](../../backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py), [publication errors](../../backend/app/application/publication/errors.py), [ReadableBlobBackend](../../backend/app/application/artifacts/contracts/blobRead.py) и [preparedManifest](../../backend/app/application/worldData/pack/encoding/preparedManifest.py). Public activation implementation и proposed enum пока не предъявлены как runtime; эта сверка не объявляет их реализованными.

| Проверяемая причина | Конкретное место получения факта | Локальная достаточность / оставшийся binding |
|---|---|---|
| EXPECTED_GAMEPLAY_STARTED | `request.expected.gameplay_started` после typed input admission | Локальный predicate полностью определён. Observed gameplay после CAS остаётся READY_INACTIVE, не этот issue |
| MANIFEST_WORLD_MISMATCH | `decoded_manifest.world_uid != request.expected.world_uid` | Локальное сравнение после успешного owning decode. Если schema decode невозможен, этот predicate не выполняется |
| INVALID_MANIFEST | Owning manifest/schema validator или final candidate consistency validator установил конкретное нарушение | Catch ограничен этапом/типом semantic admission. Ошибка дочернего payload относится сюда только при установленной непригодности полного кандидата по owning правилу; сам storage exception такого факта не даёт |
| CANDIDATE_ARTIFACT_MISSING | Catalog/read port подтвердил отсутствие конкретного обязательного ref из проверенного состава | Не использовать просто is_sealed=False: это не различает missing/unsealed. Atomic protected observation/physical-missing mapping подтверждает storage owner |
| CANDIDATE_ARTIFACT_UNSEALED | Существующий exact ref, успешное protected наблюдение seal=False | Сначала identity/существование; не классифицировать недоступность catalog как unsealed |
| CANDIDATE_HOLD_MISSING | У существующего ref под принятым guard отсутствует exact обязательный holder | Guard/lifetime и соответствующий holder задаёт atomic binding. Не проверять только «есть хоть какой-нибудь hold» и не превращать общий handoff failure в этот код |

Новые enum variants для каждого дочернего формата/части не добавляются: публичный input предъявляет корневой manifest, поле issue.path остаётся manifest. При нехватке сведений ни один из этих predicates не считается доказанным. Structural malformed input остаётся на входной границе до claim. CorruptBlobError сохраняет owning infrastructure handling: его нельзя включить в catch semantic ValueError. MemoryError, cancellation и UnknownCommitOutcome не превращаются в domain refusal.

**Replay и законность записи.** SqliteOperationStore.record_refusal проверяет exact lease и допускает phase APPLYING либо TERMINAL. Это storage capability, а не разрешение Pack повторить admission и заменить уже зафиксированный результат. Pack сначала проверяет identity/terminal и возвращает исторический исход; to_terminal используется только для законного нового post-OWNER отказа. После доменных effects требуется подтверждённый rollback; UnknownCommitOutcome исключает произвольную запись REJECTED. Не вводить автоматический recover/retry внутри OpenPipeline.

**Что осталось у владельцев, без изменения Pack DTO:** (1) typed atomic immutable-binding conflict для гонки read→claim и existing-preparation admission; (2) exact candidate manifest/closure/hold binding; (3) typed resource execution failure и разрешённый lifecycle исход после OWNER; (4) scoped rollback/terminal/handoff guarantees. Exact manifest recovery/encoding находится в [отдельном плане](pack-serialization-deserialization.md). Каждый неизвестный binding ограничивает зависимую ветвь, а не остальные Pack predicates.

Реализационная проверка должна различать missing/unsealed/no exact hold на одном ref, decoder-invalid и physical corruption, budget failure и invalid data, expected gameplay и observed CAS race. Дополнительно: replay после release не читает bytes; pre-claim code не сериализуется как REJECTED; failure записи terminal не возвращает durable refusal; unrelated infrastructure не подавляется. Нужны production tests соответствующего binding; в этом срезе проведена статическая сверка, код/SQL не менялись.

Локальный review набора причин завершён; обязательная общая приёмка всего Pack плана не подменяется этой таблицей. Class/DTO границы сохранены: pure codec только преобразует, internal operation выполняет admission в законном lifecycle, wrapper делегирует один раз, DAG выбирает последующие действия. Новых CRUD/settings/дублирующих errors и перестановки согласованного workflow нет.
