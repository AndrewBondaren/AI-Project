# Реестр междоменных контрактов DAG

**УТВЕРЖДЕНО пользователем 2026-11-21: current Snapshot pair `(format_version=1, root_id=20150)`.** Concrete модель `TimeSnapshotApplyResult` применяется для новой записи и exact replay текущего Snapshot-маршрута. Архитектурный выбор пары закрыт; прежние пометки «кандидат», «freeze OPEN» и «требуется утверждение пары» ниже заменены этим решением. Legacy fallback не вводится, прежние IDs не переназначаются, актуальные Pack/Gameplay/Cancelled не меняются. Runtime binding, полный manifest closure/collision audit, strict bounded decode, round-trip/replay и отказ на неподдерживаемые root/format без повторного apply ещё требуют реализации и проверки. Утверждение пары не означает приёмку всего H2 или разрешение на код/миграции.

**Последнее решение пользователя 2026-11-21 — БЕЗ LEGACY.** Поддержка прежних Snapshot terminal representations не требуется. Это заменяет прежнюю W/R compatibility policy: одна целевая concrete модель результата для новой записи и replay текущего маршрута, без OldSnapshotApplyResult union, legacy readers/manifests, old→new adapters, fallback и migration ради совместимости. Вводить два независимых набора W/R только ради legacy больше не нужно; точные упрощённые signatures сводят владельцы. Replay текущих операций сохраняется: те же данные/типы/identity, без повторного handler. Неподдерживаемый сохранённый root/format — явная инфраструктурная несовместимость, не отсутствие terminal и не разрешение повторить операцию. Принятые новые IDs31007/31139/31140/20150 сохраняются; прежние IDs не переназначаются. Pack/Gameplay/Cancelled — отдельные актуальные kinds, не legacy Snapshot, автоматически не удаляются. Legacy roster/corpus больше не gate H2. Новый root-dispatch API не вводится только ради выбора legacy readers: необходимость пересмотреть, сохранив strict expected root/full bounded decode и budgets. Решение не разрешает удалять данные, писать код или миграции; финальная упрощённая цепочка ещё требует сверки.

**Положение Publication — зафиксировано пользователем 2026-11-21.** Publication является общей инфраструктурной частью ядра Snapshot, а не самостоятельным предметным доменом. Оно обслуживает operation identity/immutable request binding, lifecycle выполнения, транзакционную фиксацию, terminal persistence и exact replay для Snapshot apply, Pack activation и gameplay start. Выражение «владелец Publication» означает владельца этой инфраструктурной части; отдельные чат и каталог application/publication не задают отдельный домен. Snapshot владеет применением готовых изменений и моделью apply result; предметные домены — семантикой своих данных/diagnostics; Artifacts — хранением artifacts и их защитой; DAG — оркестрацией. Зависимость Snapshot → внутренний Publication operation store классифицируется как инфраструктурная связь внутри ядра, но exact capability, nested calls и H2 contracts ещё проверяются. Эта классификация не разрешает произвольные foreign public pipeline calls, не передаёт Publication доменную семантику и не закрывает H2.

2026-11-19. Пользователь поручил сохранить таблицу и проработать все восемь направлений, затем явно разрешил адресный опрос всех необходимых владельцев. Координатор — Between domain operations. Это реестр контрактной работы, не разрешение реализации, новых NodeId или изменения утверждённого порядка.

## Сводная таблица

**Текущий H2 update 2026-11-21:** действует БЕЗ LEGACY. Encoding limits/error boundary и IDs 31007/31139/31140/20150 сохраняются. Legacy roster/corpus исключён из gates; прежняя W/R policy отменена в части legacy. Snapshot/Publication запрошены о точном disposition и simplified signatures/current terminal codec binding; final API/format pair и node output требуют сверки. [Текущее сведение и история](interdomain-refusal-transport-h2.md). H2 целиком не закрыт.

**H2 — постановка и согласование 2026-11-20:** [отдельный план типизированных отказов](interdomain-refusal-transport-h2.md) фиксирует проблему, H2-1…H2-6 и владельцев PatchSet/Time/Snapshot/Publication. Направление generic carrier предложено, полная цепочка до terminal/replay OPEN. Это общая граница в текущих IC, не дополнительное девятое направление.

**IC-1 — подтверждение PatchSet 2026-11-20:** все шесть принятых IDs допустимы относительно текущего PATCH_CORE_SCHEMA (62 entries, пересечение пустое); merge четырёх existing Time records проверен (66 entries). Полный concrete manifest из шести records ещё не проверен, глобальная резервация не заявляется. Область владения, evidence и remaining gates зафиксированы в [TIME-PATCH-1: canonical IDs](patch-set-external-contracts.md#canonical-ids-решение-пользователя-и-подтверждение-patchset--2026-11-20). Это уточняет следующий исторический OPEN подтверждения registry: owning-проверка PatchSet закрыта в своей области, отдельный глобальный владелец резерваций не установлен.

**IC-1 — решение пользователя 2026-11-20:** приняты canonical IDs TimePoint=31100, TimeInterval=31102, TimeCapture=31103, TimeAdvanceProposal=31104, TimeAdvanceSection=31105, TimeAdvancePatch=31107. Это уточнение имеет приоритет над историческими пометками proposed/отсутствующего ID ниже. Подтверждение владельца общего registry остаётся OPEN: поиск по коду, планам и документации не выявил конфликта 31107, но не доказывает глобальное резервирование. При реализации обязательны проверки merged-manifest collisions и полной transitive closure. Решение не разрешает код/миграции и не закрывает production binding, X-ID/X-BASE или IC-1 целиком.

| ID | Направление | Статус | Что закрыть | Владельцы |
|---|---|---|---|---|
| IC-1 | Time → PatchSet, TIME-PATCH-1 | Native patch-дельта ACCEPTED 2026-11-19; интеграция OPEN | Concrete codec/manifest/IDs и production binding | Time, PatchSet, Snapshot |
| IC-2 | Lifecycle → PatchSet → Snapshot, вариант А | D1–D7 и fingerprint/view приняты; три стыка синхронизированы | Итоговая приёмка closed node/result/manifest bindings и synthetic implementation evidence; реальные producers/adapters OUT | Lifecycle, PatchSet, Snapshot, координатор |
| IC-3 | Общий контекст записи | OPEN | Producers operation/preparation identity, coherent base, timeline/turn; сценарий/union/composition owner | Владелец сценария, Snapshot/Publication, координатор |
| IC-4 | Snapshot admission / receipt | Границы приняты, детализация OPEN | Diagnostics/transport, retry/recovery, C2 validator и rollback | Snapshot |
| IC-5 | Exact initial-read | Вариант 2 принят, binding OPEN | Authority/lifetime, ref→bytes→TimeCapture, exact Time IO/Error | Snapshot/Publication, Artifacts, Time |
| IC-6 | Подготовка / публикация Pack | Частично согласовано, маршрут OPEN | Pack split, pinned read, inherited retention, completion/READY/candidate/replay | Pack, Artifacts, Publication, Source |
| IC-7 | Source proof / retention, K6 | Ответственность согласована, binding OPEN | Public layout, usage/consumer mapping, непрерывная защита closure, publication без Source calls | Source, Artifacts/Publication, consumer |
| IC-8 | Persisted formats Pack | Направление принято, freeze OPEN | Final schema, inventory, descriptor transport/import-export, binary headers, cutover identity | Pack, Artifacts; Snapshot/Cache consumers |

Это восемь направлений, не восемь API. Общие зависимости ниже считаются один раз. Принятое ядро PatchSet PS-I1→PS-I2 не OPEN. C1 codec/handler реализован и проверен координатором (26 профильных tests PASS), рекомендован к приёмке; пользовательская приёмка реализации отдельно. C2 architecture accepted входит IC-4, не девятое направление.

## Общие зависимости без двойного счёта

| ID | Общая граница | Потребители | Недостающий owning результат |
|---|---|---|---|
| X-ID | Operation identity / preparation binding | IC-1/2/3/6/7 | Кто создаёт значения, immutable request, retry reuse; lease issuer не автоматически identity producer |
| X-BASE | Coherent captured publication / participants / target turn | IC-1/2/3/4 | Exact capture method/POJO и гарантии согласованности; не независимые current reads |
| X-READ | Authority + protected physical read | IC-5/6/7 | Public input не только ref/holder/budget; atomic admission, lifetime/drain; BLOB и SQL_ROWS различаются |
| X-RET | Source-set protection → target retention → completion | IC-6/7 | Нет окна GC, сохранение source holds, rollback/unknown, внешний public entry без Source calls |
| X-REP | Native representation / codec registration | IC-1/2/4 | Concrete models/manifest/IDs/versions, один contract и раздельные codec/handler по C1 |

## IC-1 — Time native section

### Сверка на готовых входах — 2026-11-20

**H3 — локальный дизайн на готовых SQL-данных ACCEPTED пользователем 2026-11-20.** Приняты row-only SQL защита (§6 Snapshot H3: append-only ограничения, одна BEGIN IMMEDIATE transaction, owning completion/cancellation/unknown lifetime) и fixed-schema v1 initial row (Time H3-D: JSON PublicationTimeState, strict decode, без silent upgrades/нового поля binding). Обязательное условие: exact Q имеет корректное фактическое Time-состояние активного timeline; Time проверяет запись, missing → REQUIRED_STATE_MISSING, без fallback/zero/rebind. Создание initial/branch-point binding и atomic visibility Q вместе с ним вынесены в [TODO верхнего процесса](multidomain-write-input-preparation-todo.md); отсутствие producer не блокирует локальный H3, но блокирует готовность соответствующего сценария. Совместимость producer с initial artifact/start protocol отдельно OPEN; SQL защита не распространяется на artifact bytes. Эта запись приоритетнее исторических PROPOSED/OPEN по данным пунктам ниже. Закрытие локального дизайна H3 не означает runtime readiness, code-go, приёмку H2 или всего IC-1.

**H3 — решения пользователя 2026-11-20 ACCEPTED:** (1) initial binding ограничен exact Q: source_publication == query_publication, поиск initial-предка не входит в контракт; (2) source передаётся через Time-owned TimeStateAppend, ITimeCommitBinding.bind(scope) сохраняется без source-параметра; (3) преобразование/rebind между timeline не вводится, требуется уже существующее корректное состояние целевого timeline, его наличие для branch-point пути ещё нужно подтвердить; (4) гарантия защиты данных и формат initial row должны быть определены до закрытия дизайна, implementation evidence проверяется отдельно. Эта запись имеет приоритет над прежними несовместимыми proposed формулировками ниже. H3 пока OPEN по указанным гарантиям; H2 и code-go не принимаются.

**H3 / C2-R1 — поправка порядка принята пользователем 2026-11-20.** Snapshot разрешает необходимые привязки принятого состояния после expected-context checks до handler.validate; metadata сохраняется в текущей transaction/попытке. После успешных validations дочитываются остальные pinned bases до первого apply, без повторного чтения уже полученных metadata. Source fault может опередить semantic refusal; прежняя гарантия полного отсутствия base reads при validation refusal уточнена. Отдельная persisted projection не вводится. См. [C2-R1](snapshot-receipt-validation-c2.md). Exact binding Input/Output/Error и подтверждение Time ещё OPEN; H2 не принимается этим решением. Эта запись имеет приоритет над историческим ожиданием решения о порядке ниже.

**Терминология H3 — зафиксировано по решению пользователя 2026-11-20.** `source binding` здесь означает **привязку принятого состояния секции**, а не участие домена Source. В рассматриваемом предложении Snapshot определяет адрес Time-состояния для exact публикации Q (в том числе inherited SectionStateRef либо initial publication binding), Time читает собственные данные по этой привязке в общей borrowed transaction. Домен Source не участвует; зависимости от его публичного контракта в H3 не выявлено. Исторический идентификатор H3-SOURCE сохраняется для трассировки вопроса. Эта фиксация терминологии не принимает proposed DTO/методы, не меняет C2-R1 и не закрывает H3: поправка порядка чтения metadata и exact binding ещё требуют отдельного согласования.

Получены адресные ответы Time, PatchSet и Snapshot; координатор сверил существующие assembly/apply signatures и результат. Это ограниченная сверка цепочки, не приёмка всех owning-планов или runtime.

| Переход | Вывод | Остаток дизайна |
|---|---|---|
| Time.prepare_section(PrepareTimeAdvanceSection) → TimeAdvanceSection или TimeSectionContextMismatch | Принятый локальный контракт подтверждён Time | Нет нового вопроса producer; operation/publication mismatch агрегируются, native admission отдельно; zero/negative advance не допускаются |
| Native sections → IPatchSetAssembly.assemble(PatchSetAssemblyInput[S]) | Owning DESIGN PASS PatchSet; успех PatchSet[S], отказ PatchSetAssemblyRefused | Новых owning gaps assembler нет; structural TypeError/ValidationError не business refusal |
| Успешный PatchSet[S] → IWorldSnapshotApply.apply | Mapping подтверждён обеими сторонами | Передача без adapter/reassembly; при assembly refusal apply не вызывается |
| Snapshot → TimeSectionHandler.validate/apply | Общие signatures/context определены; concrete binding OPEN | Time: точные semantic diagnostics и mapping отсутствующего state/конфликта/integrity faults; transaction-bound reader/writer, initial-base чтение, assigned states/history, closures и cancellation |
| Receipt → публичный результат Snapshot | Архитектура C2 принята; exact Error transport OPEN | Snapshot/IC-4: admission errors и typed C2 fault → public/node error, rollback и unknown outcome без подмены business refusal |

Time handler не коммитит borrowed scope и не вызывает чужие public pipelines. Его storage binding требует проверки допустимых зависимостей, а не считается принятым по наличию интерфейса. Все критерии dag-generator-interface.mdc остаются обязательными при приёмке конкретизации.

**Различать результаты:** SectionApplyReceipt(states, history, changed) — внутренний результат применения секции до commit. DAG получает SnapshotApplyResult(category, operation_id, request_fingerprint, committed, diagnostics). Только COMMITTED подтверждает запись; committed содержит world_snapshot/player_snapshots/publication. Busy/infrastructure/unknown outcome и cancellation не маскируются обычным отказом. Предлагаемый SnapshotPublicError ещё не frozen.

**Остаток дизайна IC-1:** (1) Time handler errors, (2) Time transaction/storage/receipt trace, (3) используемая граница Snapshot admission/C2 → public/node errors, принадлежащая IC-4. Upstream producers, выбор полного production union и сценария не блокируют локальный контракт. Реализация manifest/codec/registration и merge/round-trip/atomicity evidence учитываются отдельно, не выдаются за недостающие решения дизайна. Следующая конкретизация — Time (1–2), затем совместная сверка с Snapshot (3). Полный IC-1 остаётся OPEN.

**Уточнение границы пользователем 2026-11-20:** IC-1 рассматривает запись при уже предоставленных входах: Time.prepare_section → native section → assemble_patch_set → Snapshot.apply → receipt. Происхождение operation_id, исходного состояния и параметров изменения вынесено в [отдельный TODO-план совместной подготовки входов Time и других доменов](multidomain-write-input-preparation-todo.md). X-ID/X-BASE сохраняются в общем учёте IC-3, но отсутствие их producers не блокирует приёмку локального IC-1. В IC-1 остаются требования к переданным значениям, проверки, ошибки и гарантии выполнения. Это уточнение имеет приоритет над прежними формулировками блокеров ниже; оно само по себе не объявляет IC-1 закрытым и не разрешает реализацию.

**Следующее решение пользователя 2026-11-19 — codec/manifest shape ACCEPTED.** Приняты TimeSectionCodec(SectionContract[TimeAdvanceSection]) с pure encode/decode и CanonicalEncodingError для representation; manifest closure = PATCH_CORE_SCHEMA + TimePoint/TimeInterval/TimeCapture/TimeAdvanceProposal/TimeAdvancePatch/TimeAdvanceSection; key time_clock, supported section versions {1}, одна exact contract identity handler/codec/registry. IDs 31100/31102/31103/31104/31105 остаются proposed до подтверждения общего registry; один ID TimeAdvancePatch отсутствует. Это остаток representation freeze, не новый выбор формы. Код/миграции/production composition не разрешены.

**Решение пользователя 2026-11-19: «Ок» после предъявления IC-1.** Принята локальная дельта: TimeAdvancePatch(PatchData) с inherited header и existing proposal без копирования полей; TimeAdvanceSection[TimeAdvancePatch] с одним patch; Time формирует ref общего operation_id/time_clock/ordinal0, отдельную patch version1, empty patch dependencies/artifacts. Native модель проверяет header-инварианты и proposal.operation_id == header.ref.operation_id при создании/revalidation/decode. Existing proposal/prepare_advance и Input/expected refusals prepare_section неизменны. Successful positive advance receipt.changed использует исходный patch.header.ref без реконструкции. Это заменяет статус PROPOSED самой дельты в исторических абзацах и таблицах ниже. Exact codec/manifest/type IDs, production union/X-ID/X-BASE и implementation evidence остаются OPEN; разрешения писать код это решение не даёт.

Основания: time-domain.md, patch-set-external-contracts.md TIME-PATCH-1, section-codec-receipt-contract.md.

Предъявленное владельцем предложение: TimeAdvancePatch(PatchData) содержит existing proposal; TimeAdvanceSection[TimeAdvancePatch] содержит один patch. Input PrepareTimeAdvanceSection(proposal, operation_id, expected_world) и prepare_section → section | TimeSectionContextMismatch сохраняются. Time назначает ref общего operation, time_clock, ordinal 0, patch format 1; empty patch dependencies/artifacts, equality proposal.operation_id/header.ref.operation_id проверяются native моделью. DAG передаёт section неизменной. Это PROPOSED дельта, не ранее принятое без-header представление.

Рекомендация координатора: принять отдельный native patch вместо изменения pure proposal; потребовать exact representation declaration и same input ref в receipt.changed. C1 позволяет отдельный codec, не требует DAG decode-ноды. Production union и X-ID/X-BASE не блокируют ограниченную приёмку producer, но блокируют полный маршрут.

Следующий owning ответ: Time — окончательные fields/invariants/errors и manifest inventory; PatchSet — соответствие bound и checker semantics; Snapshot — receipt/consumer требования. Закрытие дизайна: согласованная дельта и exact schema/codec binding, без объявления runtime readiness. Runtime evidence отдельно.

## IC-2 — Lifecycle native section

Основания: entity-lifecycle.md, docs/tz_entity_lifecycle.md, dag-write-owner-contract-clarifications.md.

Предложение: pure LifecycleSectionPipelineOpenPipeline.prepare_section(PrepareLifecycleSection) → LifecycleSection | owning refusal. Вход: готовые переходы, общий operation_id, достаточная captured base и typed evidence. Каждый LifecycleTransitionPatch наследует PatchData и содержит канонический переход; поля перехода не копируются. Одно направление → одна секция; один переход → один patch; Replacement не дробится; ordinal соответствует входному индексу. change_uid не publication operation_id.

Принято пользователем 2026-11-21, подтверждено owning планом entity-lifecycle.md и docs/tz_entity_lifecycle.md: один переход = один native PatchData patch = одна history operation; Replacement не дробится. На публикацию не более одной непустой Lifecycle section. Текущий scope — независимые переходы от общей базы без пересечения typed entity refs. Ordinal — адрес, не порядок состояний. Явные цепочки intermediate states вынесены в entity-lifecycle-overlapping-transitions.md; это отдельный scope, не запрет расширения навсегда.

Актуальная owning форма предъявлена в entity-lifecycle-local-contracts.md и entity-lifecycle-binding-apply-contract.md: pure requests intent/capture/admission → prepared base/transition без header; prepare_section(operation_id,expected_world,changes,domain_evidence) → native section или LifecycleSectionRefused. Один wrapper header+prepared на переход; domain_evidence сохраняется целиком на секции с исходными индексами. Producer не вызывает четыре prepare или чужие домены. Точные источники и общая схема сведены в актуальном начале dag-multidomain-patch-publication-draft.md.

D1–D7 приняты: explicit many-to-many coverage; NoDomainMutation запрещён в local v1; самостоятельная mock_lifecycle_world fixture с synthetic A/B. Реальные домены/SQL/production producers вне scope и не prerequisites. Subject mock проверяет payload→effect, Lifecycle — relation/coverage; hash/membership не semantic proof. Replacement participant order незначим для domain semantic retry при сохранении representation order/Publication fingerprint.

Приняты и синхронизированы три общих стыка: SectionFingerprint — единственный helper над checked codec exact bytes; actual comparison после claim/replay в новой dependency-binding фазе до validate; SnapshotAttemptContextBuilder создаёт общий AdmittedSectionView для validate/apply, внешний Lifecycle-specific request binding отменён. Последняя документальная сверка Lifecycle/PatchSet/Snapshot — PASS этих стыков. Native field/index preservation и consumer signatures совпадают. Receipt history refs могут адресовать bundle и не равны числу transition operations.

Остаток ограниченного IN: итоговое сведение concrete node/result/manifest registrations, затем synthetic runtime/static checks актуальной схемы; не объявлять весь IC-2 production CLOSED или code-go по документальному PASS. Декларации предъявлены, не отсутствуют. X-ID/X-BASE producers, production adapters, bulk/вариант Б/checkpoint и реальные предметные сценарии OUT; не возвращать их в блокеры локальной приёмки. Полная архитектура требуется в согласованном scope. Исторические opposite OPEN ниже superseded этой редакцией.

## IC-3 — Общая операция и контекст

Основание: patch-set-external-contracts.md PS-R2. Существующие девять полей PatchSetData переиспользуются; новый mirror context не вводится.

Предложение ответственности: общий caller/scenario boundary фиксирует immutable намерение и identity; owning capture возвращает согласованную базу; Publication принимает/связывает identity при lifecycle entry, не назначается её creator по имени домена. Time/Lifecycle используют готовый контекст и проверяют свои relations; DAG его переносит. Это распределение требует exact producers, не готовый API.

По каждому полю предъявить producer class.method/Input/Output/Error: operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, format_version. sections приходят из IC-1/2 и других выбранных owners. turn_id не вычисляется из duration; expected_players=() не заменяет неизвестный состав; fingerprint не подменяет authority.

Следующее решение пользователя: какой реальный production-сценарий интегрируем первым и кто composition owner. Не выбирать автоматически Time-only, gameplay или generators. До ответа можно согласовать общие поля/identity rules и отдельные producers, но нельзя freeze closed union.

Закрытие: одна полная карта Output→Input для конкретного сценария, named input/result specializations одного union, retry/staging binding, без current/latest fallback.

## IC-4 — Snapshot admission и receipt

Основания: world-domain-patches-snapshots.md SN-Q1.1, section-codec-receipt-contract.md C2.

Принято: structural revalidation/check_core → SnapshotRequestValidator.validate напрямую вызывает check_prepared_order → canonical fingerprint → immutable binding/claim/exact terminal replay → новая попытка. Snapshot не вызывает assemble; constructor не усиливается prepared-order.

Принято C2: successful handler receipt проверяется относительно input section и assigned context до использования/следующего dependent apply. changed является подмножеством входных refs; Time имеет более сильную equality для единственного positive advance. Invalid receipt — execution contract fault и rollback, не business refusal. states/history актуальны.

Остаток Snapshot: точные validator classes/methods/diagnostics/aggregation, pre-claim refusal carrier, допустимые recovery callers и original-byte replay. Не повторять predicates существующих моделей или metadata/provenance helpers. Если данных для части checks ещё нет, показать распределение nested checks без ослабления гарантий. Закрытие — полный typed error/trace contract и отдельная runtime проверка.

## IC-5 — Exact initial-read

Основания: time-domain.md TIME-Q1, artifacts-public-staging-dag.md, Snapshot initial binding.

Принято: Snapshot.read_initial_binding(Q) → при binding Artifacts protected verified read → одна Time read операция с decode внутри → TimeCapture initial Q. None не запускает dependent reads; потеря обязательной связи/артефакта не маскируется absence. Exact initial Q не runtime current time и не X-BASE общей записи автоматически.

Вход Time должен сохранить binding и связь owning read result с exact ArtifactRef/bytes. Time сверяет ref/format/version и semantic payload/binding, не выполняет IO или повторный digest/read Artifacts. X-READ обеспечивает admission, budget и непрерывную защиту physical IO; после возврата owned bytes pure decode не требует продления read guard. TimeCapture сам не holder.

Остаток: public authority producer, release race до admission/во время IO, cancellation drain, BLOB format/version binding, exact Time Input/Output/Error и upper absence/result contract. Закрытие — полная Q→binding→ref→bytes→capture цепочка с owning errors и lifetime.

## IC-6 — Pack preparation / READY

Основания: pack-artifacts-boundary-trace.md, world-pack-v2-single-manifest-contract.md PA-2, artifacts-public-staging-dag.md ART-Q1.

Известно: prepare_stage(content) → PreparedArtifact(content,descriptor), stage(lease,prepared) → ArtifactRef; достаточность BLOB-среза согласована. Pack выдаёт semantic-ready bytes/состав и принимает stage result для проверки соответствия. Stage не READY. Pack final material/fence binding, конкретные публичные producer/consumer пока предложены, не приняты.

Подграницы: (a) Pack material→stage→Pack admission; (b) pinned cold/cache-hit reads с X-READ и Pack semantic admission; (c) inherited/source closure через X-RET; (d) внешний public completion, confirmed READY и exact candidate mapping. Cache hit требует актуального admission; callback/guard не DAG input. Runtime тестовые подключения не production evidence.

Запрещённый маршрут internal Source adopts из Publication/Snapshot не принимается; предложение Artifacts с ним требует замены owning контракта. Completion не получает authority из произвольного OperationRecord. Replay не выбирает первый manifest-like ref и не пересобирает payload. Root READY_INACTIVE lifetime определяет владелец; удержание children от root не удерживает сам root.

Закрытие: четыре exact public границы с trusted source READY, error/cancel/unknown и ownership. Общая PatchSet запись не требует Pack activation; candidate не section.

## IC-7 — Source proof / защита

Основание: source-interdomain-coordination-2026-11-19.md.

Пять async read-only API: admit/read/select → SourceProofResult | SourceFailure; admit_groups/verify_groups → SourceProofGroupsResult | SourceFailure. Public owner layout ещё должен заменить baseline явно. SourceProofResult.proof/durable_refs — semantic evidence, не authority или retention receipt. Producer отвечает за полноту declared usage, Source — за проверку заявленного и semantic closure.

Вариант А: Source preparation через DAG, затем publication без Source calls. X-READ/X-RET защищают исходные наборы до первого read и удержание раскрытого closure до завершения временной защиты. Cleanup не снимает последнюю protection до передачи. BLOB body и SQL_ROWS witness требуют owning typed read, не общего dict или необоснованного bytes-only пути.

Остаток: один конкретный producer/consumer mapping (Pack — кандидат, не blanket обязательность), authority нескольких historical captures, concurrent release/drain, partial acquire rollback/unknown, workers/read lifetime. Source mutation/runtime native sections отдельно, proof API их не создаёт. Закрытие K6 — exact public trace без запрещённых calls и typed IO/Error; не приёмка всего Source.

## IC-8 — Формат Pack / descriptor transport

Основание: pack-format-version-ownership.md.

Принято направление: DAG operation version отделена от owning persisted schema; для manifest format_key + ArtifactRef.format_version — единственный указатель, pack_version удалить после transport audit, codec_version/payload_format — после проверки собственной семантики. Binary headers отдельно. Один decoder после полного cutover; числовая версия здесь не назначается.

Предлагаемый предпочтительный archive contract: existing ArtifactRef + exact bytes с проверкой соответствия; это recommendation до owning import/export решения. Descriptor не authority. Если архив нужен без descriptor, владелец предъявляет иной однозначный транспорт, не schema guessing/fallback/new duplicate version.

Остаток: complete consumers/registrations/archives inventory, final schema, retained refs и unresolved operations, cache full-ref identity и exact replay. Изменённые bytes не сохраняют старый ref; смена encoding не меняет payload уже связанной operation. Готовый target → полный переход живых зависимостей с retention → удаление legacy. Закрытие — согласованный schema/transport/cutover пакет, не только удаление полей.

## Порядок контрактной работы

Это порядок уточнения, НЕ runtime DAG: (1) собрать точные ответы владельцев по всем IC; (2) отдельно свести X-ID/X-BASE/X-READ/X-RET/X-REP без противоречий; (3) предъявить локальные решения IC-1/2 и общий scenario choice IC-3; (4) замкнуть зависимые read/retention/READY и receipt mappings; (5) синхронизировать owning источники после принятия; (6) отдельно implementation acceptance.

У каждого решения фиксируются public class/module/signature, named IO/Error, field mapping, scope/identity/version, эффекты, retry/cancel/lifetime и PASS/OPEN/FAIL с evidence. Отсутствие метода означает OPEN, не разрешение coordinator/DAG изобрести доменный алгоритм.

## Опрос владельцев

Разрешён пользователем 2026-11-19 для Time, Lifecycle, PatchSet, Snapshot, Source, Pack, Artifacts, Publication. Все восемь владельцев ответили; результаты ниже. Предложения не становятся ACCEPTED по факту ответа владельца. Ни одно направление не объявлено полностью CLOSED.

## Результат первого общего круга — 2026-11-19

| IC | Полученное конкретное предложение / подтверждение | Verdict координатора и следующий шаг |
|---|---|---|
| IC-1 | TimeAdvancePatch(PatchData){proposal}, header operation/key/ordinal0, patch format1; TimeSectionCodec(SectionContract) отдельно от handler; PatchSet подтверждает совместимость | PASS локальной формы; PROPOSED к пользовательской приёмке. Manifest IDs/closure остаются exact X-REP gap; не назначать номера по предположению |
| IC-2 | Приняты независимый batch, один переход/patch/history operation, неделимый Replacement и не более одной непустой секции | OPEN: exact producer Input/Output/Error/evidence; предметный patch и coverage требуют owning сценариев. Source proof не доказывает entity→patch coverage |
| IC-3 | Snapshot предложил SnapshotCaptureService.capture_write_base(request) с explicit world/player roster, единым read scope и результатом publication/player expectations/target turn | PROPOSED; exact IO/Error и participant semantics OPEN. Scope делает чтение согласованным, но не определяет состав/authority. Publication не создаёт semantic operation ID/body/fingerprint; нужен реальный scenario owner |
| IC-4 | Snapshot подтвердил C2-R1: exact pinned bases читаются один раз после всех handler.validate, до первого apply; C2-R2: section_index из исходного enumerate | Эти решения уже ACCEPTED у владельца, не переоткрывать. R3–R5 diagnostics/provenance extraction/compatibility и public admission/recovery transport OPEN |
| IC-5 | TimeInitialStateReader.read(InitialTimeRead(binding,artifact_read)) → TimeCapture \| InitialTimeReadRejected; corruption/mismatch — отдельные infrastructure carriers | Локальное предложение предъявлено. Foreign ArtifactReadOutput специализация, authority current invocation и final errors OPEN; read_initial_binding не выдаёт право чтения |
| IC-6 | Pack предложил prepare_material(PackPreparationInput)→PackManifestMaterial(request,content), admit_staged(material,lease,artifact)→PackStagedManifest(material,artifact); Publication предложил final completion→existing candidate | PROPOSED, пока request/evidence/errors не freeze. StagedManifest не candidate. Выбор final issuer и root lifetime вынести на решение; не принимать цикл candidate до READY |
| IC-7 | Source предъявил пять отдельных public owners; Artifacts предложил protect целого origin set и retain; обе стороны Artifacts/Publication отозвали internal Source adopts | PASS устранения противоречия на уровне owning позиции; старые строки proposal не permission. Exact authority/protection/closure→request mapping OPEN. Отдельный retain не подменяет atomic completion |
| IC-8 | Pack предложил manifest fields world_uid/parts/assembly/assembly_provenance и transfer(manifest:ArtifactRef,content:bytes); Artifacts поддержал descriptor+exact bytes | PROPOSED schema/transport. Это transfer одного manifest, не полный самодостаточный archive; audit неполон. Полный export roster/retained refs/in-flight operations — до cutover |

### Точные новые предложения и их пределы

- Time IC-5: `dataModel/time/reads/initial.py::InitialTimeRead(binding:AcceptedInitialStateBinding, artifact_read:ArtifactReadOutput)`; `application/time/reads/initialStateReader.py::TimeInitialStateReader.read` — sync pure. Проверяет exact ref, BLOB/time.initial_state.canonical/version1 (owning accepted binding), decode и semantic start/clock/settings coherence. `InitialTimeReadRejected` для supplied ref/format; `InitialTimePayloadCorruptError` с canonical cause и `InitialTimeStateMismatchError` для persisted corruption/mismatch. Exact foreign DTO/checked error mapping ещё согласуются.
- Snapshot X-BASE: `application/worldSnapshot/service/snapshotCaptureService.py::SnapshotCaptureService.capture_write_base(SnapshotWriteBaseCaptureInput) -> SnapshotWriteBaseCaptureResult` — proposed async. Результат не mirror PatchSetData и не pin; retry не заменяет прежнюю базу новой. World UID/timeline берутся из owning publication, target turn вычисляется Snapshot по принятой turn semantics, participant roster задаёт caller. Полный Input/Error ещё OPEN.
- Pack IC-6: proposed `application/worldData/pack/preparation/packManifestPreparationOpenPipeline.py::PackManifestPreparationOpenPipeline` / contracts interface с `prepare_material` и `admit_staged`; модели в `dataModel/worldPack/preparation/manifestMaterial.py`. Existing proposed PackPreparationInput сам не freeze: wrapper не скрывает неизвестные evidence. Pack semantic fingerprint body принадлежит Pack; общий ID создаёт сценарий, Publication связывает lease/fence.
- Artifacts X-READ: proposed `ArtifactReadOpenPipeline[A].read_verified(ArtifactReadInput[A](ref,authority,max_bytes)) -> ArtifactReadOutput[A](request,payload:bytes)`. Generic A только concrete accepted specialization; имя authority не делает DTO capability. Initial binding может быть контекстом адресации, но Publication подтвердил: без admitted execution/session authority его недостаточно. Этот вариант пока не закрывает X-READ.
- Artifacts SQL_ROWS: proposed `ArtifactRowsReadOpenPipeline[A,C].read_verified(ArtifactRowsReadInput[A](ref,authority,max_bytes,max_rows)) -> ArtifactRowsReadOutput[A,C](request,content:C)`. C — existing owning frozen row-set, не новый witness DTO. Exact backend read/model binding/error freeze OPEN.
- Artifacts X-RET: proposed `ArtifactProtectionOpenPipeline[A].protect(lease,origins)` через named input/result и `ArtifactRetentionOpenPipeline.retain(source,target,refs)` через named input/result. Полноту origin membership и authority обязан доказать owning binding; Source payload не читается внутри Artifacts. Это предложения, не принятые публичные APIs.

### Найденные сквозные разрывы

1. **Authority initial Q.** Artifacts предложил reuse AcceptedInitialStateBinding, но Snapshot/Publication подтвердили, что этот result не caller authority. Нужен выбранный existing execution/session source допуска и его exact связь с Q, без нового token по предположению. Проверка persisted hold только защищает данные, не закрывает право вызова.
2. **Protection superset против exact READY set.** Protect целого origin set может удержать больше final closure; standalone finish требует точное равенство refs и operation holds. Нельзя молча освободить лишнее или объявить same-operation готовой. Требуется явное решение lifetime source protection и target completion. Адресные уточнения отправлены Artifacts/Publication.
3. **Retain против атомарного completion.** Раздельный retain может дать временную protection, но не доказывает atomic target acquisition+READY. Рекомендация: source protection сохраняется отдельно, target acquisition/full set/candidate mapping/READY в одном Publication UOW, без Source calls. Точный владелец source protection/ошибки ещё OPEN.
4. **Candidate до READY.** Слово candidate в предварительном входе не должно означать PreparedPackCandidate. До completion — admitted PackStagedManifest; после confirmed READY — существующий PreparedPackCandidate. Рекомендован final issuer Publication при trusted Pack semantic binding, без повторного Pack decode; требует совместного решения.
5. **Неполный archive.** Descriptor+manifest bytes не включает все payload/Source closure. Нужно явно выбрать manifest transfer или self-contained archive, не расширять гарантию автоматически.

### Решения для последовательного предъявления пользователю

| Решение | Рекомендация / варианты | Что не закрывается этим решением |
|---|---|---|
| D1 Native Time delta — ACCEPTED | Отдельный TimeAdvancePatch с existing proposal, header/invariants и same-ref receipt; шесть IDs приняты | Полный concrete manifest evidence и production integration; принятую границу повторно не предъявлять |
| D2 Lifecycle batch | А принят пользователем 2026-11-21: независимые участники от общей базы. Intermediate chains — отдельный план вне текущего scope | Exact coverage/evidence и полная архитектура Lifecycle остаются OPEN |
| D3 Переход без предметного patch | Только если разрешён owning смыслом и предъявлено явное typed evidence отсутствия требуемой предметной записи; пустой tuple не доказательство | Concrete subject owners |
| D4 Coherent capture | Отдельный Snapshot read для explicit roster в одном scope, без pin/identity | Выбор первого production scenario/его composition owner и X-ID |
| D5 Protected reads | Раздельные BLOB и typed SQL_ROWS под owning authority admission; metadata result не authority | Exact authority source/issuer и budget/error freeze |
| D6 Source public layout | Пять owners вместо baseline; не держать оба layout | IO/protection constructors и runtime |
| D7 Completion | Target acquisition+exact candidate mapping+READY в одном owning UOW; final candidate после commit, без Source calls | Source protection authority, root owner/release, error/recovery |
| D8 Pack transfer | ArtifactRef+exact bytes для manifest; необходимость полного archive решается отдельно | Final schema/audit/version/cutover |

Нельзя закрыть IC-3 вопросом «реализовать general context»: требуется назвать реальное намерение caller, immutable body и participant semantics. Первый production scenario не выбран координатором автоматически. D1 уже принят в указанной локальной границе; остальные предложения требуют решения в незакрытой части.

### Дополнительная сверка X-READ/X-RET — ответы получены

Artifacts и Publication подтвердили совместимость следующего предложения; это ещё не пользовательская приёмка:

- Source protection owner отделён от target preparation owner; protected superset не помещается автоматически под target operation и не trim-ится ради exact finish.
- Для этого маршрута отдельный public retain не является обязательным шагом. Уже существующие staging holds сохраняют свой lifecycle; предварительный дополнительный hold не доказывает READY.
- PackStagedManifest — semantic admission result, не candidate. Полный target set включает необходимые staged/inherited refs и не равен автоматически Source closure.
- Publication completion в одном UOW проверяет действующую source protection и target fence, выполняет target acquisition, exact-set check, durable candidate mapping и READY. Посторонние target holds дают отказ, не скрытый release.
- После confirmed commit возвращается existing PreparedPackCandidate; replay читает exact сохранённый mapping. Повторная Pack semantic preparation не вызывается.
- Source protection снимается только явным cleanup после confirmed outcome и drain. При unknown сохраняется до reconciliation. Cleanup не снимает исходные publication holds или target holds.
- Initial binding и publication hold НЕ caller authority; Artifacts подтвердил, что предложенная initial specialization authority:A не закрыта без отдельного owning caller-admission контракта или явно согласованной модели trusted admission.

Remaining owners: Publication — конкретное existing lifecycle представление source protection owner, identity/fence/recovery/cleanup; Publication+Artifacts — exact IO/Error и atomic protected acquisition; Pack — trusted material/full-target-set binding; caller-admission owner — право invocation на exact Q. Эти gaps не закрываются новым token/DTO по предположению.

**Текущая очередь 2026-11-21 (исправление границы скоупа):** свести H2 без legacy по exact ответам Snapshot/Publication и завершать контракт записи на уже предоставленных входах: native section → assembly → Snapshot apply → receipt/result/replay. Происхождение входов, намерение caller, roster, X-ID/X-BASE и верхняя composition относятся к [отдельному TODO-плану подготовки входов](multidomain-write-input-preparation-todo.md); они не следующий обязательный шаг и не блокеры локальной приёмки записи. D1/native IDs повторно не предъявлять. [Смежные read/Pack-процессы](interdomain-adjacent-processes.md) ведутся отдельно, [import/export](pack-import-export-after-current-scope.md) отложен. В текущем контракте остаются требования к переданным значениям, проверки/отказы, точные Output → Input и owning гарантии исполнения. Ответы владельцев не равны полной приёмке интеграции или runtime evidence.

### Идентификаторы owning чатов

Time `01a1a0ba-1bcf-7870-b23c-b0c27d874eca`, Lifecycle `01a1e936-4dfc-7d73-aede-dbfd4d988d81`, PatchSet `01a1f019-67dc-7b10-80f3-a71e28c41fb3`, Snapshot `01a1eeb1-392b-7a02-8aa3-c3fa11482b02`, Source `01a1d566-656d-7f83-b460-bef97bb4a2e7`, Pack `01a1db1a-600b-74b3-a38d-aed8b42317d0`, Artifacts `01a1ea09-2ab4-7f71-9d96-7a29d70269d7`, Publication `01a1ea8d-2bdb-7152-bb40-925c86c041d8`. Все ответы read-only; изменения owning кода этим кругом не разрешены.
