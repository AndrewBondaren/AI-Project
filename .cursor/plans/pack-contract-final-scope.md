# Pack: итоговый объём контрактного плана

2026-11-14. Пользователь уточнил задачу: завершить контрактный план Pack, не реализацию кода. Этот документ — единая точка входа и граница оставшейся приёмки. Он не объявляет отсутствующую реализацию готовой и не заменяет owning ТЗ новыми алгоритмами.

## Граница

**Уточнение пользователя 2026-11-16:** точные контракты можно запрашивать у Source, Snapshot и Cache. Остальные владельцы могут предоставить POJO, но их DAG-интеграция пока отсутствует. Pack явно предъявляет требования к нужным входам/выходам/ошибкам, не выводит готовность integration из наличия POJO и не вызывает чужие домены напрямую. Конкретизация для массовых writes: [требования Pack к владельцам](pack-batch-owner-contract-requirements.md).

**Уточнение пользователя 2026-11-14:** Source, Snapshot и Cache разрешено использовать как зависимости завершения Pack; проверяются их конкретные текущие контракты, а не ожидается абстрактная полная готовность доменов. Интеграция Pack с DAG — последний шаг поставки после завершения и локальной приёмки Pack. Генераторы остаются вне текущего объёма. Это порядок поставки, не разрешение прямых междоменных вызовов.

Pack принимает готовые типизированные результаты, выполняет собственные start/write/delete/describe/import/bind, проверяет конечный состав, формирует manifest и предоставляет prepare/activate/read/release. Оркестрация публичных операций принадлежит DAG. Pack не вызывает генераторы, Source API или другие публичные доменные операции; DAG не выполняет Pack merge/validation/assembly.

Генераторы сейчас не готовы к интеграции через DAG. Их новые inputs/results, ноды, continuation и связи не входят в этот план. detailed_initialization описан только верхнеуровнево: никакое агентское предложение L2/C11 binding не является требованием к Pack. Новые требования consumers учитываются при миграции соответствующих доменов, а не расширяют этот контрактный проход.

## Единственные источники решений

| Предмет | Нормативное основание / конкретизация |
|---|---|
| Семантика Pack и поля | [ТЗ Pack](../../docs/tz_world_pack_storage.md), [domain contract](pack-v2-domain-contract-spec.md) |
| Порядок поставки | [Единая таблица основного плана](world-pack-v2-single-manifest-contract.md#единая-таблица-зависимостей-и-завершения-шагов) |
| Named inputs, операции и локальные predicates | [Write-контракт](pack-v2-public-write-operations.md), [trace прежнего порядка](pack-write-order-trace.md) |
| Metadata usage и binding | [Metadata POJO](pack-metadata-dependency-pojo.md), [exchange](pack-source-exchange-contract.md), [A3 mapping](pack-source-error-identity-contract.md) |
| Read, resource/error contracts | [Concrete read types](pack-read-concrete-models.md), [read errors](pack-part-read-error-mapping.md), [budget accounting](pack-read-budget-accounting.md), [resource signal](pack-read-resource-limit-signal.md) |
| CRUD / настройки | [CRUD roster](pack-data-crud-roster.md), [принятое решение настроек](pack-settings-crud-disposition.md) |
| Activate/release | Domain contract; [activation refusals](pack-activation-refusal-trace.md), [release](pack-candidate-release-contract.md), [inactive retention](pack-inactive-retention-trace.md) |

Исторические OPEN и прежние shape declarations читаются с последующими решениями, а не превращаются в новые вопросы. В случае реального противоречия приоритет имеет owning ТЗ и прямое решение пользователя; противоречие явно фиксируется, а не разрешается новым временным API.

## Зафиксированный Pack-контракт

**Правила массовых операций:** [четыре принципа Pack и проверка решений](pack-bulk-write-principles.md). Документ явно различает принятый batch-подход, существующие single writes и недоказанные implementation свойства; локальные mutable контейнеры допустимы, public state остаётся immutable. Оценка сложности включает metadata/provenance. Это не изменение границ DAG или чужих доменов.

**Массовые writes, решение 2026-11-15:** пользователь выбрал однотипные пакетные операции с одним input-state admission и одним итоговым immutable state; duplicate addresses отвергаются, errors агрегируются, порядок пакетов задаёт DAG. [Точные границы решения и следующей конкретизации](pack-v2-public-write-operations.md#стоимость-последовательных-writes--отдельная-проверка-масштабирования). Первое семейство — chunks; named batch contract ещё предстоит предъявить до кода. [Замеры старого replacement](pack-write-scaling-measurement-2026-11-15.md) частичные, массовая реализация не принята. Существующие pure методы этим решением не переписываются автоматически.

1. Единственный immutable состав: parts, assembly, assembly_provenance; transient metadata dependencies не дублируют значения assembly. Один сохраняемый manifest, без отдельного contents artifact. Partial state ослабляет полноту состава, но не strict types, uniqueness и immutable вложения.
2. PackPreparationService выполняет одну названную pure операцию над state. None-preserve, explicit empty и delete имеют разные, прослеженные semantics. Изменение A сохраняет B/ref/provenance. Устаревшая metadata provenance инвалидируется; write не требует заранее proof ещё не вычисленной projection.
3. describe_metadata возвращает descriptions с subject и dependency usage. Binding объявляется только в metadataDependencies.py: subject/provenance/source_request/source_result/groups. Исторический partial preserve без detailed attribution отклоняется; новое происхождение не выводится из совпадения значений.
4. Source owning DTO переиспользуются без локальных зеркал. Pack проверяет локальную связь request/state/result; Source владеет union/subset. SourceFailure остаётся на Source-вызове; dependent Pack операция после отказа не запускается. Сопоставление результатов с исполненными запросами — требование внешней интеграции, не секретный флаг в Pack state.
5. Final prepare получает уже конечный state, проверяет scope/coverage/base/provenance и полный closure. Не повторяет writes, не запускает producers или activate. Assembler pure. PreparedPackCandidate выдаётся только после подтверждённого READY и exact holds.
6. Activate и release — отдельные публичные операции. ACTIVE/READY_INACTIVE, CAS/terminal replay, release только разрешённого неактивного кандидата и unknown outcome сохраняют owning lifecycle. Logical delete не равен release или GC.
7. Read идёт по exact pinned publication, descriptor и зарегистрированному typed decoder. Нет latest lookup/legacy fallback для нового binding. Encoded IO, decoded output и structural constraints различаются; лимиты передаются явно из owning binding, неподтверждённые числовые defaults не вводятся.
8. Ошибки: единый PackPreparationDiagnostic из existing structural variants и PackPreparationIssue; четыре metadata-кода внесены в ТЗ. Независимые ошибки агрегируются с реальными typed paths до эффектов. Локальный [A3 review завершён](pack-source-a3-reacceptance-2026-11-14.md); это не приёмка всего маршрута или runtime.

## Поставка без расширения scope

Порядок исходного плана сохраняется. Таблица ниже определяет проверяемый результат, а не поручение писать код в этом контрактном проходе.

| Этап | Ответственность Pack / результат | Приёмочное доказательство |
|---|---|---|
| 3a | Shared records и named inputs; start_empty, pure write/delete и metadata operations. Для describe/import/bind и writes с value fingerprints сначала принят минимальный metadata canonical binding из 4a | Нет дублей или скрытой оркестрации; pure методы без IO. Preserve/empty/delete, aggregation, forged instances, mixed metadata origin; локальные измерения 1000/4000/16000. Фактический DAG transport проверяется при последней интеграции |
| 3b | Final admission и manifest assembler | Полный состав, exact coverage и inherited provenance; изменения A не теряют B; неполный state не становится кандидатом |
| 4a — отдельная задача | Минимальный metadata canonical binding принимается до зависимых операций 3a; полный manifest/body codec и READY recovery — после фиксации состава 3b | Один owning encoding, без временного hash. Metadata vectors отдельно от полного round-trip и READY recovery |
| 4b | Подключение codec/read/prepare к готовым bindings, включая IO-ветвь start_from_base | Strict immutable round-trip, budgets до чрезмерной аллокации, pin guard, полный closure и exact candidate после restart. start_from_base не входит в pure-приёмку 3a |
| 4c | Activate/release через принятые internal ports | Atomic CAS/holds/terminal, refusal/replay без второго эффекта, release не затрагивает head/чужие holds |
| Последний шаг — интеграция с DAG | После завершения Pack совместно с пользователем определить/принять ноды и bindings, подключить готовые публичные операции и выполнить сквозную приёмку | Owning контракты Pack/Source/Snapshot/Cache соблюдены; DAG только оркестрирует; новые генераторные bindings не выдумываются |
| Завершение последнего шага: cutover/legacy | По готовности конкретных callers перевести их, затем удалить используемый ими legacy | Не удалять действующий путь до перевода использующих его callers; не сохранять fallback после перевода. Неготовые генераторы не блокируют локальную поставку Pack |
| Отдельный обязательный пункт после удаления legacy | Аудит комментариев, методов, переменных, imports и версионных обозначений | Один код по ответственности. Это cleanup последнего этапа, не новая функциональная интеграция; обязательные persisted wire/storage versions не менять поисковой заменой |

## Отдельные задачи и реальные интеграционные зависимости

- **Serialization/deserialization и exact READY recovery** вынесены пользователем в [отдельный план](pack-serialization-deserialization.md). Не возвращать их как общий блокер pure Pack. Действующий запрет пересборки manifest на READY сохраняется; альтернативы старых encoding-документов не считаются принятыми.
- **PACK-METADATA-PLANNING** разрешённо отложен. Ни фиктивный PlanRef, ни planning=() вместо доказательства не вводятся. Это не gate текущего независимого Pack.
- **Source/Artifacts/publication** реализуют свои proof/retention/scoped ports. Pack фиксирует потребляемые данные и exact closure/hold требования, но не реализует владельцев. [Ответ publication](pack-source-adoption-publication-response-2026-11-14.md) остаётся DESIGN OPEN для зависимого подключения; наличие READ proof не даёт live hold.
- **Payload format/resource binding** — собственная задача Pack/decoder в соответствующем implementation-срезе: строгий codec, явные limits и достоверный resource signal. Ссылки выше задают правила; ещё не выбранные caps/проверки не выдаются за готовые defaults. Генераторы для этого не запускаются.
- **DAG binding и consumer migration** определяются вместе с пользователем, когда соответствующий домен готов. Не принимать новые ноды по переписке агентов. Непривязанный верхнеуровневый detailed_initialization не является дефектом Pack.

## Приёмка и конечный статус

**Принятое решение READY, 2026-11-14:** пользователь согласовал exact candidate в существующем operation ledger, атомарно с READY; replay без пересборки, stage/finish и выбора ref из набора. Сохраняются проверки bytes/identity/holds. Новый holder/version/отдельное хранилище не требуются. [Фиксация решения](pack-serialization-deserialization.md#сверка-с-snapshotartifacts-2026-11-14). Это снимает выбор механизма READY recovery, но не подменяет конкретизацию ports/schema и authority исходных holds.

### Исполнение шагов 1–4 по поручению пользователя

**Актуальный остаток: собственные контракты Pack и зависимости интеграции разделены.** Pinned-origin storage/codec доводит Snapshot; это не общий блокер завершения контрактного плана Pack. Ниже не список обязательных внешних разработок, которые Pack должен закончить самостоятельно.

| Пункт | Зафиксировано | Что действительно осталось |
|---|---|---|
| READY | Exact candidate в existing ledger атомарно с READY принят пользователем; async append/read/finish ports и replay semantics предъявлены Snapshot | Конкретная owning ledger schema и review предложенных faults; runtime evidence относится к последующей реализации |
| Source authority | Capture/proof и adopt; [S1/S2](source-pack-s1-s2-contract.md) конкретизирует coverage, scoped preflight и rollback | Snapshot поставляет pinned-origin provider/storage для зависимого исполняемого пути. Не общий gate контрактного плана Pack; operation-origin/finalizer не включать автоматически |
| Serialization/read | Body/manifest правила, Source declarations, Cache boundary, typed decoder resource signal и cap wiring описаны; test matrix отделена от runtime результатов | Итоговая Pack canonical composition/IDs; caps неподключённых форматов остаются требованиями их будущих bindings, не общим gate Pack; existing activation vectors не заменяют prepare vectors |
| Release | Existing terminal OperationHolder, acquire/release history, scoped release port/outcomes и public mapping предъявлены | Review предложенного owning fault/schema; доказательство atomic eligibility и history после GC проверяется при реализации |

Положительная приёмка всей реализации не объявляется. Собственный документальный остаток Pack — итоговая canonical composition body/manifest и проверка согласованности owning деклараций/критериев приёмки. Внешние storage/fault/runtime задачи выше остаются prerequisites соответствующих integration slices, а не требованием реализовать Snapshot внутри Pack. Генераторы, DAG и разрешённо отложенный Planning в этот остаток не включены.

**Полученное уточнение storage:** Snapshot предъявил exact async append/read/scoped finish/release и единый proposed PackLifecycleFault; [ответ](pack-storage-lifecycle-finalization-response-2026-11-14.md) переписан без прежних holder/version/marker. Public release mapping добавлен в release-контракт без новых public DTO. Отсутствие сигнатур READY/release больше не является замечанием; остаются owning schema/fault review и runtime evidence реализации. По authority установлен точный недостающий контракт: durable mapping preparation identity + SourceProofReadInput → exact исходные VerifiedArtifactRef/holder identities, записанный trusted owner при acquisition и доступный после restart. Source proof/READ/candidate этого mapping не содержат; готовый provider не выдуман.

- Локальный A3 закрыт. Current Cache CRUD/bytes/admission граница сверена с кодом ниже; новый Cache API не нужен.
- Устаревшая реконструкция READY manifest в serialization/identity/lifecycle материалах отмечена как отозванная; действующий путь должен читать exact durable candidate.
- [Snapshot/Artifacts response](pack-storage-lifecycle-finalization-response-2026-11-14.md) предъявил конкретный кандидат durable READY binding и scoped finish/release. Это proposal: необходимость нового holder/version проверяется относительно существующих решений, новые типы не утверждены.
- Ответ Source по exact capture/proof canonical graph получен и зафиксирован ниже. Source schema не дублируется в Pack; durable authority mapping остаётся конкретным вопросом preparation/publication owner.
- Итоговая положительная приёмка шагов 1–4 пока не объявлена: точный READY binding и dependent lifecycle ports должны быть согласованы по полученным предложениям. Это конкретный остаток storage границы, не ожидание генераторов/DAG или абстрактной готовности доменов.

Последующая проверка Snapshot сняла необходимость нового holder/version: сохраняется existing terminal OperationHolder на manifest, для release replay используется existing acquire/release history. Durable exact candidate mapping в existing operation ledger атомарно с READY принят пользователем; конкретная schema уточняется у владельца. Новые PackCandidateHolder/contract_version/отдельный release marker отозваны владельцем и не входят в план. Ответ Source приведён ниже.

### Действующая область междоменных уточнений

По указанию пользователя сейчас к DAG подключаются Cache, Snapshot, Source и Pack. Только их актуальные owning contracts используются для текущих междоменных уточнений. Остальные домены не подключены и не имеют полностью актуального контракта: не проектировать за них DTO, generator bindings или новые числовые caps и не превращать их миграцию в gate независимого Pack. Существующие подтверждённые format profiles сохраняются. Отсутствующий профиль означает незавершённость конкретного будущего format binding, а не unlimited decode и не готовность этого binding. DAG-интеграция сохраняет последнее место в утверждённом порядке.

### Подтверждённая граница Source — 2026-11-14

[Ответ владельца](source-pack-boundary-response-2026-11-14.md) подтверждает SourceCaptureRef(world_uid, artifact) для body.capture: artifact — finalized SQL_ROWS witness, не capture body и не capability. Placeholder заменён этим owning типом в ТЗ/write/domain spec. Полный proof поддерживает historical captures; единый SourceFailure сохраняется. Canonical binding SOURCE_PROOF_SCHEMA_V1 и IDs capture/proof/usage/selection закреплены владельцем; Pack использует их без перенумерации или копии моделей. Source schema не задаёт outer Pack fingerprint recipe.

Internal adopt принят и заново проверяет полный closure/реальные holds в borrowed scope. Актуальная единая [редакция S1/S2](source-pack-s1-s2-contract.md) прошла адресные reviews Pack/Source/Snapshot: typed coverage input, scoped preflight, all-provenance reader и exact read-refusal rollback. Это отдельный design-срез, не готовый authority provider. Ранний общий authority proposal не использовать как альтернативу последующей pinned-only редакции.

### Pinned-origin: актуальное решение и предел поставки

[Pinned-only документ Snapshot](snapshot-pinned-origin-contract-r1.md) сохраняет историческое имя файла, но содержит исправленную редакцию и последующие решения владельца. По сообщению Snapshot пользователь его чата согласовал один полный origin/grant и историческое сохранение binding без post-commit runtime consumer. Это не recovery input store: READY использует exact candidate/target holds; после confirmed rollback нужен повторно предъявленный исходный полный input. Автономная реконструкция потерянного input после crash не поставляется этим срезом.

Несколько historical captures внутри одного proof допустимы; pinned-only issuance требует покрытия всего request одним выбранным manifest. Same request с другим origin конфликтует. Это ограничение конкретного pinned пути, не изменение общего Pack mixed-provenance контракта и не разрешение обрезать dependencies до одного capture.

Pack владеет verified reader: все parts[*].provenance.source_proof и assembly_provenance[*].provenance.source_proof из exact admitted manifest, без union/normalization/фильтра changed. Snapshot владеет issuer, grant, register/resolve, ledger и atomic lifecycle. [Storage/codec proposal](snapshot-pinned-origin-storage-codec-proposal.md) остаётся его зависимым срезом; Pack не обязан доводить его до runtime PASS для завершения своего контрактного плана.

[Pin registration](pack-pin-canonical-registration-proposal.md) конкретизирована отдельно. В коде появился PACK_PIN_SCHEMA RECORD20205 и адресные тесты; Pack выполнил read-only owning review без findings. Самостоятельный повтор tests и полная приёмка implementation не заявлены. Эта регистрация не завершает canonical graph body/manifest и не подключает ledger автоматически. Cache key/Source proof schema не расширяются этой декларацией.

### Проверка Cache: детали

Подтверждены кодом CacheService.get(CacheKey) → CacheLookup, create(CacheEntry) → CacheCreateResult, update(CacheEntry) → CacheUpdateResult, evict(CacheKey) → CacheEvictResult; ошибки — owning CacheFailure(error: CacheError). Данные Pack — bytes под existing MANIFEST_BYTES_CONTRACT; manifest_cache_key выводится из полного ArtifactRef через существующую canonical схему. Pack/Cache не получают новый общий DTO, settings API не меняется.

PinnedManifestReader.resolve возвращает ManifestAddress после guard. read_verified и admit_cached сверяют pinned ref/key; cached путь дополнительно сверяет entry.key, длину и content hash, затем общий manifest admission. Cache hit не заменяет право чтения, не даёт Source hold и не доказывает READY. Эти Pack операции сами CacheService не вызывают; последующая orchestration определяется на последнем DAG этапе. Current decoder ещё не означает готовность целевого нового manifest binding или полного budget admission.

Источники: backend/app/application/cache/service/cacheService.py; cache/contracts/manifestBytesCodec.py; worldData/pack/encoding/manifestCacheKey.py; worldData/pack/read/pinnedManifestReader.py; dataModel/worldPack/meta/manifestCacheContract.py. Результат — существующий контракт можно использовать; новый Cache API для Pack не требуется. Scope/настройки Cache не открываются повторно.

Контрактный материал Pack сведён; дальнейшие обсуждения начинаются с конкретного пункта этого документа, а не нового общего списка внешних блокеров. Разработка генераторов, DAG contracts и повторный выбор настроек исключены.

Для принятия конкретного implementation-среза проверяются все [обязательные критерии](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена): три запрета DAG; каждый класс/роль/deps/effects/критерий отказа; public/pipeline/implementation; неизменность порядка; C/R/U/D данных и настроек отдельно; внешний data contract; POJO и field/logic errors без дублей. Подробные roster/поля не копируются сюда второй декларацией, а используются из owning документов таблицы выше.

**Границы результата:** это завершённая консолидация контрактного плана, не положительная приёмка всех этапов и не готовая реализация. A3 локально принят; полный storage/serialization/lifecycle маршрут не принят и не скрывается под этим статусом. Отсутствие конкретного требуемого port/schema в выбранном зависимом срезе блокирует только его. Независимый Pack не ждёт миграции генераторов. Кодовые изменения требуют отдельного поручения и implement-plan, приёмка кода выполняется отдельно от имплементации.
