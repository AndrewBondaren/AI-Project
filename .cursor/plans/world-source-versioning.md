# World source versioning — версионирование объектов N+1 и граница мутации

## Приоритет архитектуры домена — решение пользователя 2026-11-15

**Утверждённая последовательность проектирования:**

1. **Архитектура домена Source — ядро.** Сначала определить собственные модели, операции, классы, методы, внутренние зависимости и границы ответственности Source. Внешние потребности обозначить на границе ядра, но не подменять этот этап конкретной Terrain/Pack/Snapshot/Artifacts composition или DAG wiring.
2. **Архитектура интеграций — последующие отдельные шаги.** После приёмки архитектуры ядра конкретизировать подтверждённые внешние связи в разрешённом scope. Для каждого шага предъявить отдельный scope, входы/выходы/ошибки, владельцев, зависимости и критерии приёмки; не объявлять все интеграции принятыми одним общим gate. Точный порядок этих шагов определяется зависимостями принятого ядра и предъявляется отдельно. Неизвестные или подлежащие переделке интеграции записывать как техдолг Source, а не расширять план разработкой чужих доменов.

**Правило интеграционного техдолга — решение пользователя 2026-11-15:** запись содержит внешний домен/владельца, конкретный недостающий или меняющийся контракт, затронутый Source-срез и условие возвращения к интеграции. До подтверждения не создавать placeholder/mirror/adaptation и не обещать работоспособность этой связи. Такой техдолг не блокирует архитектуру ядра и независимые от него срезы; откладывается только конкретная зависимая интеграция. Закрытие ядра и готовность интеграций учитывать отдельно. Доработка чужого контракта, миграция и новый DAG-протокол не добавляются в Source-план автоматически. Это правило имеет приоритет над прежними широкими требованиями закрыть весь G1-BIND перед любой дальнейшей работой.

Этот порядок имеет приоритет над прежними указаниями «следующая локальная проработка» ниже: сейчас следующий результат — архитектура ядра, не продолжение внешних согласований. Поставленные G1.1/G1.2 не отменяются; прежние проектные имена классов и группировки методов не считаются автоматически принятой архитектурой. Реализация любого следующего среза требует принятой архитектуры относящегося к нему ядра и необходимых интеграций; один этот порядок не разрешает код.

Обязательные ограничения пользователя: **одна ответственность — одна реализация; один метод — одна функция. Классы с множественной ответственностью запрещены.** Не объединять самостоятельные операции под универсальным service/pipeline/методом с переключателем режима. Не дублировать одну ответственность в разных реализациях. Вызов внутренних collaborators сам по себе не разрешает скрыть несколько самостоятельных обязанностей в одном классе.

Архитектурный результат: карта папок; для каждого класса одна конкретная ответственность, допустимые зависимости и эффекты; для каждого метода одна функция, точная сигнатура Input/Result/Error и критерий проверки; разделение публичного контракта, внутреннего алгоритма и storage adapter; вложенные вызовы и границы транзакций; existing/proposed/accepted статусы. Особо проверить прежнюю группировку admit/read/admit_groups/verify_groups/select в SourceProofPipelineOpenPipeline, обязанности validator/read binding/finalizer и mutation/recovery. Не переименовывать и не делить существующий публичный контракт молча: обнаруженное смешение предъявить с конкретной предлагаемой декомпозицией до кода.

Архитектура не принимается при множественной ответственности класса, совмещении самостоятельных функций метода, дублировании реализации ответственности или отсутствии сведений для этой проверки. Все обязательные критерии dag-generator-interface.mdc сохраняются. Решения по полям и алгоритмам других доменов не входят в этот этап; внешние зависимости обозначаются точными контрактами и владельцами. После приёмки архитектуры — конкретный implementation-срез через implement-plan; самостоятельные тесты не заменяют независимую приёмку.

**Статус G1 на 2026-11-15:** G1.1 declarations и G1.2 canonical encoding поставлены и получили **независимый PASS** — [акт проверки](source-g1-foundation-review-2026-11-15.md). Граница проверки: values/encoding, 47 тестов и typing; это не приёмка G1.3, Source 2 registration, storage, finalizer или всего Source. **Общий G1 остаётся открытым.** Следующий этап — архитектура ядра по порядку выше; G1-BIND учитывается отдельно как интеграция. [План G1](source-g1-values-canonical-implementation.md) сохраняет evidence поставки и ранее разрешённое исключение G1.1 → G1.2 перед G1-BIND.

**Контроль дрейфа:** [контрольная точка контрактов и будущей реализации 2026-11-14](source-contract-baseline-2026-11-14.md) разделяет принятый proof design, proposals, runtime evidence и разрешённый scope. Source storage остановлен на отсутствующем authored-write binding; PACK-S1/S2 отдельно разрешены пользователем только для design/review с Source/Pack/Snapshot/Artifacts. Эта запись не заменяет ТЗ/спецификацию и не разрешает реализацию.

PACK-S1/S2: единая редакция 2 принята как ограниченный design и синхронизирована в proof specification §13. [План реализации дельты](source-pack-s1-s2-implementation.md) подготовлен, но NOT EXECUTION-READY: G1 базовые Source POJO/pure contracts, G2 durable collector/read/adopt и G3 consumer composition ещё не реализованы. Порядок основного плана не меняется; эти prerequisites не включаются в дельту автоматически. Заглушки/legacy adapters/зеркальные DTO запрещены.

Проектный срез SourceDurableProof и исправления R1/R2 в [спецификации](source-proof-v2-contract-spec.md) **приняты независимым reviewer**: [акт 2026-11-13](source-durable-proof-contract-acceptance-2026-11-13.md). Это не приёмка runtime durable API или всего Source и не изменение порядка основного плана. Внешние capture/DAG и Pack/Snapshot bindings, полный CRUD/disposition, pregame revision staging и runtime проверки остаются OPEN. Следующая локальная проработка — [pregame staging](source-pregame-revision-staging-design.md). Отдельные Source contract/transition документы не являются альтернативным основным планом.

Статус: DESIGN согласовано в чате 2026-10-24; после критического ревью
согласованы freeze/capture, публикация, GC-защита staging, изоляция
производных SQL, provenance частей, итоговый ref-integrity граф и
разделение source revision / planning fingerprint. Остаток вопросов и
детализация схем/шагов — ниже; план ещё не готов к имплементации.
Заменяет направление «publication guard / require_fresh abort» из
`geo-1-designed-water.md` PC-9 для части «что делать при конкурентной
правке источника». Общий механизм, не привязан к GEO-1.

Связь с patches/snapshots (2026-10-27):
[новый архитектурный план](world-domain-patches-snapshots.md) §6 переиспользует
этот design revisions/capture/retention/publication. Домен владеет read/patch;
snapshot закрепляет source revision set. Второй revision-механизм и центральный
WS CRUD не вводятся. Это связь design-планов, не evidence реализации и не
автоматическое расширение source versioning на все runtime patches.

**Уточнение мастера 2026-10-27 — append-only SQL и pack:** изменения состояния
добавляют новые записи/версии и immutable артефакты; patch содержит историю
перехода, только Snapshot применяет набор и фиксирует согласованное состояние.
Прежние разрешения свободных UPDATE в phase 0 и изменяемый SQL pointer/latest
ниже не являются готовым механизмом для нового плана и требуют согласования.
Identity/revision, fingerprint, pinning и retention переиспользуются; новый
параллельный revision-механизм не вводится. Протокол append-only head/commit
и представление черновой истории пока не выбраны; реализация не разрешена.

## Актуальные следующие шаги (2026-11-15)

Конкретный implementation-кандидат независимого ядра: [source-core-invariants-implementation.md](source-core-invariants-implementation.md), 2026-11-16. Пять компонентов, порядок A→D, exact exclusions и собственные/независимые проверки раздельно. Код пока не поставлен; остальные открытые области Source не включаются в этот срез.

Исправления архитектурного review 2026-11-16: R1 — leaf facts с исходными indices вместо целого повреждённого usage; R2 — [точный первый independent subset](source-core-independent-slice.md). [Повторная собственная проверка](source-core-architecture-review-2026-11-15.md) не заменяет независимую приёмку; implementation-план и код ещё не разрешены.

**Актуальная карта ядра и статусов:** [source-core-architecture.md](source-core-architecture.md). Это единая точка навигации по архитектуре: согласованные направления, конкретные proposals, собственный остаток и отдельный реестр интеграций. При чтении ранних таблиц учитывать перечисленные там дельты; полная архитектура ещё не принята.

Оставшиеся границы ядра — [capture/prune/configuration](source-core-capture-prune-configuration.md): construction без лишнего assembler, отдельная usage/prune ownership граница и незакрытый settings lifecycle. DRAFT, без назначения Source владельцем чужого reachability и без CRUD acceptance.

Консолидация revision/mutation/recovery — [Source core mutation contract](source-core-mutation-contract.md), PROPOSAL: единый input roster, pure revision rule, отдельные provisional/committed/unknown, reuse existing outcome/error proposals. Public mutation/recovery signatures и интеграционный transport ещё не приняты.

Пункт 1 — [декомпозиция ответственности ядра](source-core-responsibility-decomposition.md). Пользователь согласовал разделение обязанностей 2026-11-15. Следующий пункт — точные signatures и публичные границы; имена классов ещё кандидаты, существующий API не изменён. Полная архитектура и реализация ещё не приняты.

Пункт 2 — [публичные границы и методы](source-core-public-boundaries.md), DRAFT: отдельные concrete proof operation owners с существующими POJO; обнаруженные отдельные обязанности check_coverage и adoption preflight; явный остаток собственных контрактов ядра. Предложение ещё не заменяет принятые публичные/S1/S2 signatures.

Продолжение ядра — [внутренние API и dependencies](source-core-internal-api.md): pure signatures, constructor graph и preconditions; CheckedPath approach согласован, concrete checker signatures предъявлены отдельно. Request-specific composition и mutation proposals ещё требуют завершения. Это собственные задачи Source, не внешний техдолг и не готовая реализация.

Шаг 1 детализации checkers — [точные signatures и constructors](source-core-checker-signatures.md): existing typed paths/issues, original indices, отдельная world проверка, пределы decoded membership evidence. DRAFT без кода и без независимой приёмки.

1. Предъявить архитектуру ядра Source: папки, классы с единственной ответственностью, методы с одной функцией, POJO, внутренние зависимости и публичные границы. Проверить прежнюю группировку proof-операций, validation, reads, finalize и mutation/recovery; неподтверждённую декомпозицию не считать принятой.
2. Принять конкретный срез ядра и его implementation-план; реализовать через implement-plan и предъявить отдельно на независимую приёмку. Подтверждать отсутствие зависимости от отложенных интеграций, не заменять их production stubs.
3. Отдельными шагами предъявлять архитектуру подтверждённых интеграций, затем соответствующие implementation-срезы. Неизвестные/меняющиеся внешние связи остаются в реестре техдолга ниже.
4. Проверять готовность ядра отдельно от каждой интеграции. Незавершённые связи не объявлять работающими; общий runtime Source не объявлять готовым по результату pure-среза.

### Интеграционный техдолг Source

Единый актуальный реестр статусов вынесен в [source-technical-debt.md](source-technical-debt.md), включая отдельный INT-ARTIFACTS-TERMINAL. Таблица ниже — навигационная сводка границ; новые evidence/статусы фиксируются в отдельном файле, а не в конкурирующих списках.

| Долг | Владелец / недостающий контракт | Затронутая интеграция / условие возврата |
|---|---|---|
| INT-TERRAIN | Terrain: body/projector/format пока proposal; shared POJO compatibility и vectors не приняты | Concrete descriptor binding; вернуться после принятого owning контракта. Поля других доменов Source не решает |
| INT-ARTIFACTS-FORMAT (часть прежнего INT-ARTIFACTS) | Artifacts/publication + owning body domain: concrete Source/Terrain ArtifactFormatContract, registry/backend instance и borrowed scope composition | Durable reads/finalize/adoption; возврат после подтверждения exact format/version, регистрации и scoped binding, без нового lifecycle/backend |
| INT-ARTIFACTS-RETENTION (часть прежнего INT-ARTIFACTS) | Source владеет политикой истории/explicit prune; Artifacts — holders и GC. Нужен exact binding исторических revision bodies к Source root и правила освобождения root при explicit prune с сохранением остальных holders | Revision retention/prune; возврат после подтверждения holder/root ownership, атомарного acquire/release и проверки, что prune не удаляет bytes, удерживаемые capture/другими roots. Не считать format registration доказательством исторического удержания |
| INT-WRITER | Owning домен данных + Snapshot + Source: отсутствует подтверждённый Snapshot authored-write/borrowed transaction binding, связывающий owning writer/bootstrap и Source revision append в одном scope | Атомарная запись данных и revision; возврат после exact Input/Result/Error, правил заимствования transaction, commit owner, rollback/unknown outcome. Source не мигрирует чужой writer и не создаёт второй commit owner |
| INT-PACK (часть прежнего INT-CONSUMERS) | Pack: mapping declared usage/сохранённой provenance к Source proof/groups/selection и durable refs | Pack consumer binding; возврат после подтверждения соответствия PackStoredProvenance принятому Source proof-контракту и разрешения конкретного интеграционного среза. Поставленные POJO не отменяются |
| INT-SNAPSHOT (часть прежнего INT-CONSUMERS) | Snapshot: exact proof request encoding, pinned origin/adoption input и target scope/fence | Snapshot consumer/retention binding; возврат после приёмки соответствующего encoding/binding и подтверждения передачи proof/holder evidence без подмены origin. Отдельно от authored-write долга INT-WRITER |
| INT-DAG (часть прежнего INT-CONSUMERS) | Владелец DAG: прямые вызовы публичных Source операций, typed input/result/error и порядок передачи результатов между доменами | DAG wiring; возврат после совместной приёмки конкретных нод и маршрутов пользователем. Source не назначает ноды и не вводит обходной orchestrator |

### Историческая последовательность подготовки (2026-11-14, заменена порядком выше)

Следующая таблица сохраняет происхождение вопросов. Она не является текущей очередью задач или разрешённым scope; Terrain execution не первый шаг Source. Её внешние зависимости учитываются как интеграционный техдолг, а не как обязательная разработка чужих доменов.

**Обязательное ограничение пользователя 2026-11-14:** адаптация старой формы строго запрещена. Для Terrain/Source не вводятся legacy compatibility adapters, dual-read, fallback или восстановление обязательных полей из старого input. Callers переходят непосредственно на новый строгий контракт; неполные старые входы отклоняются. Проверка совместимости в шагах ниже означает выявление затронутых consumers и точный cutover, а не сохранение старой формы. Bootstrap подчиняется тому же запрету. Решение не разрешает удалять или переписывать исторические данные.

Статус: **семантический dossier шага 1 подготовлен**, итог и пределы evidence — [§7 Terrain dossier](terrain-source-execution-contract-dossier.md#7-сводный-результат-ограниченного-шага-1). Шаги 2–4 OPEN; общая приёмка implementation-плана не пройдена. Это сводный порядок завершения проектирования, а не разрешение реализации. Первый кандидат — одна world-scoped registry mutation batch с membership; Terrain остаётся выбранным кандидатом до приёмки его owning-контракта. Полная миграция Source и внутреннее устройство Pack в этот срез не входят.

| Шаг | Что завершить | Владелец и проверяемый результат |
|---|---|---|
| 1. Terrain execution | Точные POJO, строгая валидация, codec/manifest и требования к vectors; membership и semantic projection; семантика ссылок и требования целостности; inventory затронутых callers | Terrain подтверждает данные и существующий код, Source сводит требования. Результат: согласованная модель данных и семантический dossier. Новые междоменные API, scoped bindings и DAG routes не проектируются здесь; отсутствие будущего API не блокирует этот результат. Он не является приёмкой исполняемого контракта |
| 2. Source storage | Точный revision store и схема append-only записи; owning writer выбранного реестра; initial bootstrap с сохранением достоверного authored state; revision/body/tombstone mapping и retention | Source владеет revision/history, Terrain — записью своих данных, Artifacts/publication — lifecycle инфраструктурой. Результат: конкретные scoped ports/classes, транзакционные границы, ошибки и bootstrap-порядок без обхода owning writer. Зависит от шага 1 |
| 3. Публичная граница | Единые mutation/recovery Input/Result/Error и публичные пути импорта; initial prepare/stage и recovery entry; различение preflight refusal, committed terminal и unknown outcome; логирование причины, operation_id и результата; точная связь с DAG | Каждый домен утверждает свой контракт; Source сводит карту интеграции. Результат: полный маршрут public input → прямой DAG caller → операция → result/error, включая вложенные вызовы. Scope, grant и executor остаются внутренними. Завершить согласование preflight logging с owning invariant. Зависит от шагов 1–2 |
| 4. Итоговая приёмка | Свести принятые решения в единый актуальный контракт, явно отметить заменённые предложения; проверить все обязательные правила проекта; подготовить конкретный implementation-план с файлами, зависимостями и проверками | Source сводит результат с подтверждениями владельцев внешних контрактов. Результат: приёмка без OPEN в выбранном срезе и отдельный принятый план для implement-plan. Любое нарушение или отсутствие evidence означает отказ. Зависит от шагов 1–3 |

Уточнение границы шагов 2026-11-14: целевые междоменные Input/Result/Error, consistency bindings и маршруты вызовов проектируются на шаге 3 совместно с DAG и владельцами сразу как окончательное решение. Текущие POJO/read paths Terrain — evidence, не гарантия актуальности DAG-контракта. Шаг 2 описывает owning storage, но не вводит временные междоменные API. Обязательная приёмка всего implementation-плана сохраняется на шаге 4; промежуточное завершение inventory/семантики её не заменяет и не разрешает код.

### Разрешённые границы уточнений

**Решение пользователя 2026-11-14:** `cell_state_registry` оставить как есть с пометкой «разобраться отдельно». Определение владельца, семантики, POJO/API и реализация этого реестра **вне скоупа данного плана**. Не запрашивать по нему дальнейшие решения и не включать его разработку в критерии завершения шага 1. Существующая ссылка Terrain.default_state остаётся отмеченной внешней зависимостью; это не подтверждение её runtime integrity и не разрешение на fallback/адаптацию.

Обязательное указание пользователя: **при выходе за перечисленные рамки остановиться до работы вне scope и предъявить пользователю конкретную зависимость; не расширять задачу самостоятельно и не запускать новый домен/чат для обхода ограничения**.

| Домен | Что можно уточнять в текущем шаге 1 | Граница |
|---|---|---|
| Source | Identity/revision, semantic projection, membership, требования к входным данным и proof | Не переоткрывать принятый proof; не проектировать новые междоменные операции |
| Terrain | Существующие POJO, смысл 19 полей и nested values, строгая валидация, canonical manifest, семантика ссылок и inventory callers | Ответ Terrain не удостоверяет целевые DAG API; генераторы/CRUD не реализуются |
| Artifacts/publication | Существующие format registry, ArtifactRef/Kind, verified-read и ограничения bytes storage | Не проектировать новый lifecycle, retention authority resolver или recovery в рамках шага 1 |
| Materials | Только namespace/default_material, смысл отсутствия/nullable target и факты использования | Не проектировать Materials CRUD/scoped ports |
| Lore | Только namespace/glossary_ref, смысл отсутствия/nullable target и факты использования | Не развивать Lore stub в новый доменный контракт |
| Regions/Landcover | Только vocabulary eligibility.fact, различие unknown/missing observation, ссылки на terrain и authored/derived semantics | Не проектировать Regions API, state transitions или генерацию |
| Hydrology | Только существующие shore-ссылки на terrain и требования их целостности | Не менять гидрологию или её pipeline |
| Locations | Только ссылки клеток/placement на terrain и требования целостности | Не проектировать storage/writer/CRUD Locations |
| DAG | Уточнение его ответственности и уже принятых ограничений | Целевые маршруты и междоменные Input/Result/Error — отдельный шаг 3, не текущая работа |
| Pack | Только уже принятые требования потребителя к Source proof/capture | Никакого проектирования внутренностей Pack или расширения текущего Terrain-среза |

По явному поручению пользователя 2026-11-14 владелец семантики danger_level_registry установлен: **Locations**, см. соответствующий раздел docs/tz_locations.md. Допустимы уточнения identity/priority и смысла ссылок, без разработки API. Владелец cell_state_registry пока не назначен: текущее расположение raw поля в World и enum в Terrain не определяет владение. Если для завершения семантики требуется такое решение — остановиться и предъявить вопрос пользователю. Общий dependency-review чат имеет право только собрать evidence в перечисленных границах, а не принимать решения за владельцев.

Детали и evidence остаются в [pregame design](source-pregame-revision-staging-design.md), [ревью среза](source-recovery-slice-review-2026-11-14.md) и [ответе Artifacts/publication](source-mutation-artifacts-publication-response-2026-11-13.md). Для шага 1 начат [статический аудит Terrain callers и bootstrap](source-terrain-execution-audit-2026-11-14.md); owning ответ запрошен, шаг не закрыт. Эта таблица консолидирует остаток; она не переоткрывает принятый SourceDurableProof и закрытые проектные решения recovery/fencing/logging. Закрытие замечания по документам не доказывает готовность runtime.

Шаг 4 обязан покрыть три запрета DAG, ответственность и критерий отказа каждого класса, публичную/внутреннюю границу, утверждённый порядок, отдельные CRUD-проверки данных и настроек, протокол междоменных зависимостей, POJO и типизированные ошибки без дублей — по [обязательным критериям](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена). Порядок реализации основного плана сохраняется: inventory → owning contracts/projector → revisions/history/retention → capture finalize → дальнейшие интеграции. Эта таблица не вводит новые DAG nodes и не меняет порядок вложенных операций.

Другие реестры, library/entity/settings writers, внутренняя миграция Pack и полный переход Source остаются за границей первого кандидата. Explicit prune нельзя молча исключить: его отдельная поставка и режим удержания истории до неё должны быть явно приняты при фиксации среза. Следующее действие — завершить шаг 1, а не начинать runtime storage или расширять scope.

## Проблема

Мир — связка ссылок на объекты N+1 (реестры, шаблоны, библиотеки) +
немного собственных данных (locations, scalars). Конкуренция за источник —
это конкуренция за объекты. Текущие дыры:

1. Публикация manifest до проверки свежести источника (FineChunkPersist
   `finish()` + `maybe_checkpoint_manifest`) — см. PC-9 обсуждение.
2. Удаление объекта, на который ссылаются → неявный fallback позже,
   мастер не видит.
3. Правка ссылочного объекта во время in-flight операции → ретроконн
   или смешанная ревизия без версии объекта.

## Базовая модель (решено)

### Таксономия фаз

- **Фаза 0 — черновик**: мир не инициализирован. Прежнее предложение свободных
  UPDATE снято для нового append-only state contract (уточнение 2026-10-27).
  Режим revision accounting и представление черновой истории согласуются
  отдельно; ref-integrity на границе мутации сохраняется.
- **Фаза 1 — инициализация / эксплуатация**: появились производные
  артефакты (pack) и возможны in-flight операции.
- **Idle после bake**: мутация bump'ит ревизии затронутых объектов,
  pack помечается stale; ребейк — по явному требованию мастера.

### Revision и удержание тела — разные события

В фазе 1 **каждая семантическая правка меняет revision** независимо от
in-flight. Наличие держателей определяет сохранение старого тела, а не
сам факт изменения revision. Держатели — captures, artifacts, snapshots,
accepted sets и latest; отсутствие in-flight не разрешает потерять
ревизию, удерживаемую другим держателем. Учёт начинается с первого
capture при инициализации, до выполнения bake; до этого действует фаза 0.

| Мутация при in-flight | Эффект | Решение |
|---|---|---|
| Добавление независимого объекта | captured set не меняется; меняется latest источника | операция видит прежний состав коллекций |
| Правка/удаление объекта из зависимостей capture | captured set не меняется; latest получает новую ревизию | in-flight держит старое тело |
| Правка объекта вне зависимостей capture | captured set не меняется; latest получает новую ревизию | прежнее тело сохраняется при наличии иных держателей |

Отсутствие объекта в списке выбранных members не доказывает независимость:
учитываются зависимости от состава контейнеров и результатов выборок.

### Версия — свойство объекта, не мира

- Identity: `system_name` (стабильный ключ) + `revision`.
- Ссылки остаются по `system_name`; resolve новых операций → latest.
- Старая ревизия живёт до конца окна in-flight (минимум) либо
  дольше при resolve-as-of политике baked артефактов (решение ниже).
- Tombstone: удаление объекта = последняя tombstone-ревизия; старые
  ревизии продолжают резолвиться до GC. Идеально ложится на модель.
- Форк мира сужается/исчезает: если locations и world scalars тоже
  versioned-объекты — отдельный механизм форка не нужен.

### Mutation boundary — единая точка контроля

Любая правка captured-входов (import, worldEdit, library attach/detach/
member write, правка записи реестра) проходит через одну границу:

1. **Ref-integrity check (до коммита)**: проверяется итоговый граф всей
   атомарной мутации: исходящие ссылки изменённых/добавленных объектов
   и затронутые потребители удаления/смены identity. Batch import,
   rename и `replace_with` проверяются после всех запланированных замен,
   а не по промежуточным состояниям. Проверка и запись выполняются
   в одной транзакционной границе. Неразрешённые ссылки → `ERROR`
   со списком referrers; возможный явный override сохраняет результат
   явно (declared fallback / `replace_with` / «требует починки»).
   **Неявный fallback запрещён.** Точный охват ссылок и допустимые
   override-состояния — детализация п.15.
2. **Revision + retention check**: семантическая мутация создаёт новую
   latest-ревизию; удерживаемое прежнее тело сохраняется до перезаписи.
   Коллизия — изменение источника из зависимостей capture, сам capture
   не меняется. Проверка и запись сериализованы с capture-finalize и prune.
3. **Compatibility**: добавление независимых объектов не считается
   коллизией — fingerprint семантический, по effective inputs
   (revision set), не по байтам таблиц.

### Capture и артефакты

- `SurfacePlanningCapture` фиксирует **revision set** вместе с
  захваченными значениями и frozen-resolver для ленивых чтений.
  Revision set используется для provenance и pinned resolve;
  `fingerprint_inputs` остаётся fingerprint фактической проекции
  входов конкретного planning-контракта, а не всего object revision set.
- Manifest/bundle описывает состав immutable частей; каждая часть
  сохраняет собственный dependency stamp — «построена от X@3, Y@1».
- Baked артефакты: предпочтительно хранить **материализованные
  значения** (включая свойства, которые должны оставаться прежними).
  Сам ключ «гравий» не фиксирует его прежние свойства. Если часть хранит system_ref —
  обязателен pin ревизии и resolve as-of при чтении. **Открытая
  проверка:** что реально хранят bundle/manifest/structure entries.

### Ref-integrity latest и pinned-графов (решение 2026-10-24)

Обычная правка тела также проверяет новые исходящие ссылки: например,
новый `default_material` должен разрешаться в итоговом графе мутации.
Импорт может атомарно добавить материал и ссылающийся на него terrain;
rename может атомарно заменить все затронутые latest-ссылки.

Latest-граф и pinned-графы не смешиваются: старый artifact продолжает
разрешать ссылки через свой revision set, rename latest его не
переписывает. Его holder запрещает физическое удаление нужного тела.
То же относится к accepted sets и другим держателям старых ревизий.
Проверка ref-integrity latest и проверка revision reachability выполняют
разные задачи. Инвентарь ссылок и контракт явного override детализируются
до реализации boundary; override не даёт права потерять held-тело.

### Source revision и planning fingerprint (решение 2026-10-24)

- **Object revision** описывает семантическое состояние источника,
  используется для provenance, удержания тела и pinned resolve.
- **Planning fingerprint** описывает фактические входы конкретного
  алгоритма. Сохраняются проекции входов, версии схемы/алгоритма и
  зависимости планов; execution policy исключается согласно контракту.
  Изменение нерелевантного поля entry не должно само по себе заставлять
  пересчитывать план (например, travel_modifier для построения высот).
- **Canonical source representation** сохраняет семантически значимое
  authored-присутствие полей. Отсутствие поля и явно заданное значение
  по умолчанию не схлопываются, если потребитель их различает:
  `TerrainRegistryEntry.has_authored_hills` зависит от `model_fields_set`.
  Значимое различие должно сохраняться и при хранении/восстановлении
  тела, чтобы pinned resolve воспроизводил ту же семантику.
- **Label-only** изменение не меняет semantic revision (seq/content_hash)
  и planning fingerprints; label сохраняется отдельным stamp на момент
  использования, не участвует в семантическом равенстве revision.
- Точное кодирование authored-присутствия и политика исключений
  semantic hash задаются при детализации п.8/16. Второе hash-ядро
  не вводится: canonical representation передаётся в state_fingerprint.

### Публикация pack после смены модели

Публикацией владеет operation owner: immutable manifest + stamps,
holder handoff, terminal outcome и CAS активного указателя фиксируются
одной короткой DB-транзакцией (протокол ниже). Persist нижнего слоя
только стадирует данные. Один stamp или `save_manifest` публикацией не является.

`require_fresh` удаляется после подключения frozen reads, сохранения
pinned-тел, защиты blobs от GC, изоляции производных SQL и проверки
совместимости частей, а не только после появления CAS-указателя.
Checkpoint owner публикует тем же протоколом как отдельный immutable
результат; незавершённые части не объявляются завершёнными.

## Модель source-объектов (решение мастера 2026-10-24)

Принят вариант: **контракт на entry POJO + минимальное хранилище**.

### Typed source categories (не однородное versioned-покрытие)

| Категория | Identity | Обновление |
|---|---|---|
| Engine-библиотека | `pack_uid` + `system_name` | никогда не меняет инстанс мира автоматически |
| World-owned library member | `template_uid` + provenance `source_template_uid` | только explicit re-instantiate с preview (существующий механизм) |
| Embedded N+1 реестр мира | `(world_uid, registry_key, system_*)` | принятие набора сущностей, не replace `worlds` целиком |
| Locations / собственные объекты | entity uid | граница мутации |
| Pack / baked артефакты | revision set + content hash | новые артефакты рядом; snapshots не переписываются |

### Контракт версионирования — на entry POJO

```python
class TerrainRegistryEntry(BaseModel):
    __source_contract__ = SourceObjectContract(
        key_field="system_terrain",
        exclude_fields=("display_name", "lore_ref"),
    )
```

- `key_field` обязателен для versioned entry; `exclude_fields` — единственный
  механизм исключения (по умолчанию все поля семантические).
- `SourceObjectContract` — typed dataclass/`ClassVar`, не dict и не
  Field-level `Annotated` markers (по cascade-соглашению метаданные вне
  Annotated).
- `WorldSlice` остаётся контейнером: даёт `world_key` (колонка) и `pojo_cls`;
  entry-идентичность и семантика полей — только POJO. Проектор комбинирует:
  `(world_uid, terrain_registry, plains) @ revision`.

### Карта классов и доменов (dataModel)

Новый домен-механизм `dataModel/sourceVersioning/` — общий namespace для
версионирования источников, вне отдельных доменов (domain POJO живут в
своих папках и только импортируют контракт):

| Класс | Ответственность | Слой | Файл |
|---|---|---|---|
| `SourceObjectContract` | декларация key_field + exclude_fields на entry POJO | dataModel | `dataModel/sourceVersioning/sourceObjectContract.py` |
| `SourceObjectId` | typed id `(scope, container, key)` | dataModel | `dataModel/sourceVersioning/sourceObjectId.py` |
| `SourceRevision` | `seq` + `content_hash` | dataModel | `dataModel/sourceVersioning/sourceObjectRevision.py` |
| projector (world → SourceObject set) | применяет contract поверх WorldSlice/library/entity контейнеров | application | `application/worldData/sourceVersioning/` — точный файл в шаге детализации |
| mutation-boundary collaborator | collision re-projection + revision-set stamp | application | `planning/guards/` либо `application/worldData/sourceVersioning/` — решение в шаге детализации |

`dataModel/identity/` не расширяется: там `EntityUid` (кем объект является),
а контракт включает revision-семантику — выходит за identity.

### Принятый носитель тел — уточнение 2026-11-12

Детализация реализации и актуальные границы evidence: [source-proof-v2-contract-spec.md](source-proof-v2-contract-spec.md). Принятие носителя не закрывает указанные там lifecycle staging и durable holder, publication index mapping и типизированные descriptors источников. Этот документ также уточняет переиспользование старых writers и scope-binding без второго generic Source CRUD фасада.

При закрытии Pack REV-02 пользователь принял сохранение immutable source bodies через существующий Artifacts и owning format bindings. Source связывает typed object identity + SourceRevision с body ArtifactRef, отдельно версионирует состав влияющих коллекций. seq назначается при semantic mutation, не при capture. Чтение точной revision не подменяется latest. Используются существующие canonical encoding и artifact retention, второе hash/storage-ядро не вводится. [Порядок поставки и трассировка](world-pack-v2-single-manifest-contract.md#порядок-закрытия-rev-02--поручение-пользователя-2026-11-12).

Это уточнение закрывает выбор носителя тел, но не означает наличия реализации source index и согласованного owner pregame source publication. Конкретный append-only revision index, назначение seq внутри atomic apply, snapshot capture, membership identities, CRUD/error contracts и удержания ещё должны пройти архитектурную приёмку. После gameplay сохраняется исключительное право Snapshot применять подготовленные изменения; отдельный Source commit в обход Snapshot запрещён. Старые формулировки ниже о выборе носителя относятся теперь к детализации индекса/протокола, а не повторному выбору хранения source bodies.

**Уточнение по существующим writers (2026-11-12):** [детальная трассировка V1 до SQL](world-pack-v2-single-manifest-contract.md#детальная-трассировка-v1-mutation-paths-до-sql-2026-11-12) подтвердила WorldService._save + region reconciliation, LibraryWriteService.prepare/apply_prepared + caller-owned LibraryWriteExecutor, общую транзакцию WorldCopyImport и Database.transaction_if_needed. Сначала адаптируются эти механизмы и составляется полный roster обходных writers (locations, persisted defaults repair, pack metadata/dependencies/delete, bulk/import). Они пока изменяют текущие rows и не обеспечивают durable source revisions. WriteRetentionPlanner защищает достижимых members, но не исторические тела. Предложение отдельной pregame source operation было преждевременным: необходимость нового публичного входа/OperationKind не доказана и не является обязательным условием. После gameplay применяется прежний Snapshot-only gate; существование V1 direct writes не отменяет его.

### Revision = seq + content_hash; удерживаемые тела доступны

- Revision — пара `seq` (монотонный на object id) + `content_hash`
  (canonical POJO dump). Hash нужен для детекта коллизии и дедупликации;
  `seq` — для читаемого порядка в диагностике и preview.
- Доступность каждого held-тела обязательна до изменения latest.
  In-flight читает captured значения или pinned-тела; artifacts,
  snapshots и accepted sets сохраняют нужные тела долговечно, включая
  восстановление после перезапуска. Наличие `world_snapshots` само по
  себе не доказывает полноту хранения.
- Конкретная схема (revision store / source snapshots / accepted-копии)
  выбирается при детализации по инвентарю ссылок. Откладывается выбор
  носителя, а не гарантия доступности held-тел. In-flight-only данные
  могут жить в памяти: v1 не возобновляет прерванный bake после restart.

### Source adoption для игры игрока

Игра игрока читает свой **accepted source set**, не latest мастера.
Adoption preview сравнивает три состояния: accepted set игрока,
master latest, player-authored объекты:

- `ADD` — новый объект источника: принять, если не пересматривает
  существующую планировку (планировка и bake — неизменяемые ограничения,
  отсутствие L2 ≠ свободное место);
- `CHANGE` — изменённый объект: не применяется автоматически, решение мастера;
- `REMOVE`/`RETAIN` — удалённый в источнике удерживается, если referenced
  (pinned ∪ referenced ∪ pack/bake-ссылки);
- `PLAYER` — player-authored объекты не трогаются.

Master bake — source snapshot новой редакции для переиспользования
совместимых членов/артефактов, не замена pack игрока. Snapshots immutable:
принятые дополнения попадают в последующие snapshots; restore старого
snapshot возвращает старый pack + revision set.

### Три оси именования (OCI-модель, решение 2026-10-24)

| Ось | Что | Аналог | Кто ставит |
|---|---|---|---|
| Identity | `system_name` / `template_uid` | repo name | движок/автор один раз |
| Version label | `version` строка в теле | image tag | автор свободно, может совпадать/двигаться |
| Revision | `seq` + `content_hash` | digest / lockfile entry | движок вычисляет |

- Refs — только по identity; bump label/контента ссылки не переписывает.
- `version` label вне semantic-hash по умолчанию (exclude_fields для
  template-моделей): label-only bump = тот же digest, новый label-штамп.
- Stamp несёт **копию label на момент штампа**: фронт матчит
  identity ↔ revision ↔ label простым join, доменной логики у клиента нет.
- Bundle manifest = lockfile-аналог: `source_revisions` записей с
  label + digest + seq.
- **uid на версию не создаётся** (решение 2026-10-24): правка тела —
  тот же uid, новый seq; bump label — тот же uid, seq и digest,
  меняется только label-штамп.
  Новый uid только при смене идентичности: переименование `key_field`
  (tombstone старого + новый объект, ref-integrity scan показывает
  referrers), `member_copy`, remap пака. Re-instantiate получает
  дешёвый детект «источник изменился» по расхождению ревизий,
  `body_diff` остаётся для preview.

### GC ревизий (решение 2026-10-24)

Два уровня «используется», не смешивать:

- **Object** (жив/tombstone) — identity-level: pins ∪ referenced ∪
  bake-ссылки, существующий usage-index libraryPacks.
- **Revision** (конкретную ревизию удалить?) — revision-level: кто
  штампует именно её.

Держатели ревизии (reachability-реестр): in-flight captures,
pack/bundle manifests, `world_snapshots`, accepted sets игр,
latest (всегда held).

Разделение доменов жёсткое:

- `dataModel/sourceVersioning` — contract/id/revision, **не знает**
  держателей, не импортирует usage.
- `sourceUsage` (application, отдельный домен) — reachability index:
  сканирует реестр держателей → `held_by[]` | `free`.
- `revisionPrune` (application) — спрашивает usage, удаляет только free.
- routes — preview + confirm, тонкие.

Контракт: `prune(object_id, policy=keep_latest | revisions=[…])` →
preview по ревизиям `free | held(by)` → confirm удаляет только free.
v1 — явный prune из фронта, не фоновый sweeper. Tombstone объекта —
отдельная операция, prune её не делает.

### Freeze in-flight — snapshot isolation (решение мастера 2026-10-24)

**Вопрос** (дополняет открытый вопрос 13): может ли мутация источника
изменить вид операции, которая уже захватила входы и ещё летит?
Блокировать ли правки источников на время операции?

**Решение:** freeze **чтения**, не писателей — snapshot isolation.

- Писатели свободны: правка пишет новую ревизию; блокировки ввода на
  время bake — нет. **Изменение источника, входящего в зависимости
  capture** — коллизия; сам capture остаётся неизменным. Та же мутация
  после конца операции — новый latest.
- Вид операции заморожен на captured revision set: ленивые чтения
  mid-operation резолвятся по pin-ревизиям, не по latest. **Pin
  распространяется на состав коллекций** — `list`/`candidates` видят
  прежнее membership, включая отсутствие добавленного позже объекта;
  pins уже выбранных members недостаточны.
- **Capture-finalize — короткая транзакция**, сериализованная с
  mutation boundary и prune. Значения загружаются заранее; в транзакции
  проверяются captured object revisions и ревизии состава контейнеров,
  регистрируется holder и закрепляются соответствующие тела. Только
  после успешного commit capture готов к выполнению. Между финальной
  проверкой и закреплением нет окна ни для писателей, ни для prune.
- Согласованность снимка — оптимистичная перепроекция в конце захвата,
  до bake. Сдвиг → повтор capture, **максимум три попытки захвата**;
  затем статус `capture_contended`, запуск можно повторить. Проверка
  latest после всего bake запрещена: последующие разрешённые правки
  не перезапускают уже начавшуюся операцию.
- **Новая ревизия требует сохранения pinned-тела до перезаписи** —
  доступное хранилище старых тел обязательно хотя бы для in-flight.
  **V1 после перезапуска процесса не возобновляет незавершённый bake**:
  операция считается прерванной, новый запуск получает новый capture.
  Долговечные pins опубликованных artifacts сохраняются обязательно.
- При успехе pins передаются artifact в commit; при отмене/сбое
  освобождаются после остановки workers операции. Recovery освобождает
  держателей подтверждённо прерванных операций, не действующих writers.
- Активация поверх более нового pack — CAS с `ready_inactive` outcome
  (протокол ниже); повторная активация/мерж требуют явного решения.

## Публикация и транзакционная модель (решение мастера 2026-10-24)

Противоречие «транзакционность vs много записей» решается переносом
точки атомарности: **файлы идемпотентны и не перезаписываются;
транзакционен только указатель**. Файлы — фаза work, долгая и
параллельная; коммит — короткая транзакция из ~3 действий.

### Протокол (5 фаз) — прежний кандидат, commit pointer требует пересмотра

UPDATE/CAS изменяемого указателя в этом эскизе нельзя переносить в новую
append-only архитектуру без пересогласования. Staging/retention требования
остаются входами проектирования, а не доказательством готового commit protocol.

```text
1. STAGE     storage API под межпроцессной блокировкой по hash:
               регистрация staging holder → размещение/проверка blob
               долговечность содержимого и имени → готовая ссылка
2. STAGE-SQL производные записи → привязка к artifact_id, невидимы
3. COMMIT    одна короткая транзакция:
               manifest row (immutable, адресован по hash)
               artifact → manifest_hash + per-artifact stamps
               holder handoff: op → artifact (атомарно)
               CAS pointer: activation_seq == base_seq ?
               terminal outcome операции + manifest_hash
4. OUTCOME   успех → artifact active
             CAS fail → artifact {status: ready_inactive, pins переданы}
5. RETRY     commit idempotent по stable operation_id/artifact_id
```

### Требования

- **Storage adapter:** `stage_blob()` возвращает готовую ссылку только
  после полного размещения и обеспечения долговечности содержимого и
  имени средствами поддерживаемой платформы. Одного `fsync` до rename
  недостаточно для обещания сохранения имени при потере питания.
  DB commit принимает только готовые ссылки. Windows-реализация
  проверяется отдельным crash-тестом.
- **GC и staging:** live-set = `referenced(∪ manifests) ∪
  staged(∪ active leases)`. GC, обходящий только manifests, не должен
  удалить blob до commit. Все операции закрепления, размещения и удаления
  проходят через единый storage API с межпроцессной блокировкой по hash.
  Writer под блокировкой регистрирует holder и размещает либо проверяет
  существующий blob. GC под той же блокировкой повторно проверяет
  держателей непосредственно перед удалением: прежний список кандидатов
  не даёт права удалить файл. Это относится и к повторному использованию
  существующего hash. Порядок блокировок/DB-UOW детализируется единообразно
  для writer и GC. Commit передаёт staging-защиту artifact атомарно;
  отмена снимает её только после остановки всех writers операции.
- **Manifest immutable, hash-адресован:** artifact record ссылается на
  manifest по hash; manifest перечисляет точные hashes blobs. Читатель:
  `active pointer → artifact → manifest@hash → blobs@hash` — дерево
  согласовано конструкцией.
- **CAS:** сравнивается с `activation_seq`, захваченным при выборе
  базового pack; счётчик монотонный, **включая restore**. Fail →
  `ready_inactive` с переданными pins: артефакт сохранён, не активирован;
  повторная активация/мерж — отдельное явное решение.
- **Idempotent commit:** artifact row может существовать в `staging`.
  Признак завершения — сохранённый terminal outcome операции (`active`
  либо `ready_inactive`) вместе с manifest hash, holder handoff и
  результатом CAS. Retry по stable `operation_id` возвращает прежний
  outcome, не пытаясь активировать `ready_inactive` повторно. Повторное
  использование id с другим manifest не является корректным retry.
- **Crash-таблица:** до коммита — сиротские blobs → GC, активный pack
  нетронут; при падении во время commit исход клиенту неизвестен —
  recovery читает terminal outcome в БД, транзакция либо целиком
  состоялась, либо откатилась; после commit — artifact согласован,
  активирован либо сохранён `ready_inactive` согласно исходу CAS.

### Производные SQL — принадлежность artifact (решено)

Генерация заранее пишет производные rows с `artifact_id`; читатели
получают их через выбранный artifact. Финальный commit делает поколение
доступным переключением указателя, без массового merge в общие таблицы.
В рамках чтения artifact фиксируется один раз для SQL и файлов.

Шаг 1 инвентаризации включает все shared rows до commit:
`relief_grade_instances`, `named_locations`, `map_cells`, `connection_*`
и другие фактические writers. **Authored locations и игровые изменения
не становятся производными автоматически**. Создание исходных сущностей
при bake — отдельная source-мутация со своей проверкой конкуренции;
она не должна скрытно менять вход уже замороженной операции.
Точные таблицы, ключи и границы authored/derived — детализация схемы.

### Частичный refine — provenance частей (решено)

Новый artifact сохраняет ссылки на неизменённые immutable части базового
pack и заменяет обновлённые. Каждая часть имеет собственный dependency
stamp, manifest описывает состав; один stamp новой операции не
приписывается унаследованным частям. До активации проверяется совместимость
нового L2 с родительским L0 и других зависимых частей. Конкретные predicates
совместимости и схема наследования производных SQL определяются при
детализации. Удержание artifact охватывает и унаследованные части,
нужные тела и SQL-данные, а не только вновь записанные blobs.

### Открытые уточнения протокола

- Lease формат: `staged_blob(artifact_id, path)` без TTL (мёртвая
  операция = lease мёртв) — предпочтительно, без таймеров.
- `ready_inactive` retention: держатель навсегда или с политикой
  очистки, если не активируется.
- Структура manifest: один per-artifact или index + sub-manifests
  (частичный pack, вопрос 11).

## Контракты и направление зависимостей (черновик, детализация в шагах)

### Направление импортов (жёсткое правило)

```text
domain POJO (terrain/materials/locations/libraryPacks)
        │  импортирует контракт
        ▼
dataModel/sourceVersioning        ← НЕ импортирует доменные POJO,
        │                            иначе цикл domain → contract → domain
        ▼
shared leaf values (EntityUid, ArtifactRef, RevisionHex, RegistryKey)
        + app.ids / pydantic / typing; без owning domain registry imports
```

Application-слой зависит на dataModel в обычном направлении:

Уточнение proof-среза по ревью 2026-11-13: SourceObjectContract остаётся
независимым от доменных моделей. Остальные Source value contracts могут
переиспользовать перечисленные shared leaf values; прежнее «только app.ids»
superseded этой точной границей. RegistryKey[OwningDomainRegistry] связывается
application adapter, не импортом owning registry в Source POJO. Импорты
Pack DTO, holder/usage services и concrete storage в Source POJO запрещены.

- **projector** (`application/worldData/sourceVersioning/`) — импортирует
  `WorldSlice`, контракты, доменные контейнеры; dataModel ничего не знает
  о проекции.
- **mutation boundary** — вызывается из write-путей (WorldService.update,
  library ops, worldEdit), импортирует projector + контракты; возвращает
  typed diagnostics, не решает политику caller'а.
- **capture** — принимает готовый revision set как вход, не вычисляет его
  сам (projection = чужая зона).

### Исторические черновые сигнатуры — не действующий proof-контракт

Сигнатуры этого раздела сохранены как история проектирования. Их нельзя использовать вместо принятого proof-контракта `source-proof-v2-contract-spec.md` (§9–13) или как разрешение реализации. Не покрытые этим proof-контрактом mutation/recovery/adoption границы требуют отдельной архитектурной конкретизации; исторический draft не заполняет пробел автоматически. Декомпозиция классов проверяется по актуальным требованиям ядра; новые публичные signatures не выводятся из старого текста молча.

```python
# dataModel/sourceVersioning/sourceObjectContract.py
@dataclass(frozen=True)
class SourceObjectContract:
    key_field: str                          # имя identity-поля entry POJO
    exclude_fields: tuple[str, ...] = ()    # поля вне revision-hash

# dataModel/sourceVersioning/sourceObjectId.py
SourceObjectId = Annotated[Union[
    "RegistryMemberId",      # (world_uid, registry_column, member_key)
    "LibraryMemberId",       # (template_uid)
    "EntityObjectId",        # (entity_uid)
], Field(discriminator="kind")]

# dataModel/sourceVersioning/sourceObjectRevision.py
@dataclass(frozen=True)
class SourceRevision:
    seq: int            # монотонный на SourceObjectId; носитель — шаг 3
    content_hash: str   # app.ids.state_fingerprint от canonical entry dump

RevisionSet = dict[SourceObjectId, SourceRevision]
```

Уточнение по ревью Source proof (2026-11-13): SourceRevision содержит только
seq и content_hash. Прежнее поле label в этой сигнатуре superseded: author
label хранится в audit metadata мутации и не участвует в semantic equality,
canonical proof или выборе historical revision. Поля строгого POJO и
отдельные object/collection refs определены в source-proof-v2-contract-spec.md
§10.2; canonical binding и удержание capture — §11. Это синхронизация
проекта, не приёмка реализации и не изменение порядка поставки.

- `key_field`/`exclude_fields` — имена полей (декларация), не payload `*_type`;
  это допустимое `str`-исключение по contract-creation.
- `SourceObjectId` — **discriminated union по категориям**, не
  `(str, str, str)` — иначе str-дыра в контракте (type-kind-str-fields).
  `RegistryMemberId.registry_column` — существующий `world_key` из
  `WorldSlice`; `member_key` — значение `key_field` записи.
- `content_hash` — переиспользует `app.ids.state_fingerprint`
  (canonical serialization + SHA-256); второй hash-ядро не вводим.
- Tombstone — ревизия с флагом `deleted`, не отдельная сущность.

### Typed diagnostics (поверх существующих FieldPathError)

```python
class SourceMutationKind(StrEnum):
    REF_INTEGRITY = "ref_integrity"     # referrers списком
    COLLISION     = "collision"         # captured input изменён
    STALE         = "stale"             # stale-состояние артефакта; не abort frozen bake
```

Boundary возвращает `(decision, diagnostics: tuple[FieldPathError, ...])`;
decision — `in_place | new_revision | reject | requires_policy`, выбор
политики (override/declared fallback) остаётся caller'у.

### Data flow

```text
mutation request
  → projector(current world/objects)          [application]
  → diff vs accepted/captured RevisionSet
  → boundary: ref-integrity → collision → decision
  → write new latest revision + retain held bodies
```

Source mutation выполняется внутри write-transaction caller'а,
сериализованной с capture-finalize и prune; projector — чистая функция
над уже загруженными объектами, без своих reads. Долгая генерация,
стадирование и отдельная короткая транзакция публикации artifact —
другой lifecycle, см. протокол выше.

### Нерешённое в контрактах (переносится в шаги)

- `seq`-носитель — детализация вопроса 14: должен учитывать все
  семантические изменения между stamp-операциями.
- Где живёт accepted source set игрока (worlds-поле vs таблица) —
  связано с открытым вопросом 5, отдельный контракт.
- Capture хранит revision set вместе со значениями/frozen-resolver;
  точный shape и canonical authored-presence — детализация вопроса 16.

## Связь с библиотеками и реестром мира

Механизм общий, не только template libraries:

- **Library pack attach/detach/replace** — мутация captured-входов
  (member attach меняет effective catalog) → та же граница; сам пак
  тоже versioned-объект (pack identity + revision).
- **Member write внутри пака** — правка ссылочного объекта → ревизия
  member'а + bump ревизии пака (или членская ревизия достаточна —
  открыто).
- **Реестры мира** (terrain, economic tiers, purpose packs и др.) —
  записи versioned так же.
- **Locations** — кандидат versioned-объект; если да — форк мира
  полностью исчезает, остаётся единый механизм ревизий.

## Открытые решения (зафиксировать до имплементации)

1. ~~Область versioned-объектов~~ **РЕШЕНО 2026-10-24**: typed source
   categories, не однородное покрытие — см. «Модель source-объектов».
2. ~~GC ревизий~~ **РЕШЕНО 2026-10-24**: два уровня проверки (object vs
   revision), reachability-реестр держателей, отдельный домен
   `sourceUsage` + сервис `revisionPrune`, v1 — явный prune.
   См. «GC ревизий». Политика авто-sweeper — позже, отдельным решением.
3. ~~Revision storage — гарантия~~ **РЕШЕНО 2026-10-24**: revision =
   seq + content_hash; held-тела доступны, для artifacts/snapshots/
   accepted sets — долговечно. Конкретная схема хранения и seq-носитель
   детализируются по инвентарю (п.4, 9, 14); хранение не откладывается
   до необязательного будущего этапа.
4. **Что хранят baked артефакты**: инвентаризация — где сейчас
   system_ref без материализованных значений. **Блокер для решения
   о конкретной схеме хранения тел ревизий** (см. п.3).
5. **Stale-политика idle**: мутация в idle — что помечается (pack
   целиком? scope?) и как UI/мастер запускает ребейк. Для игры игрока
   дополнительно: формат и триггер source adoption preview.
6. **In-flight registry — детализация**: схема op holder и определение
   подтверждённо прерванной операции. V1 не возобновляет незавершённый
   bake после restart; очистка ждёт остановки его writers. Pins
   опубликованных artifacts долговечны.
7. **Member vs pack ревизия**: достаточно ли ревизии member'а.
8. **SourceObjectContract**: точный список versioned POJO (какие
   реестры получают `__source_contract__`) и политика exclude_fields
   для display/lore-полей — инвентаризация в шаге 1.

### Вопросы критического ревью 2026-10-24 — решения и остаток

Архитектурные решения внесены в основные разделы; статусы ниже отличают
их от оставшейся детализации. Принципы п.15–16 согласованы; открыты
инвентарь ссылок/override и точный формат canonical representation.
Удаление publication
guard зависит от подключения всего протокола и проверки его гарантий,
а не от появления одного CAS-указателя или stamp.

9. ~~Доступность тел старых ревизий~~ **ГАРАНТИЯ РЕШЕНА**: каждое held-тело
   сохраняется до изменения latest; опубликованные artifacts, snapshots
   и accepted sets обеспечивают долговечный as-of resolve. V1 in-flight
   после restart прерывается. **Детализация:** revision store / source
   snapshots / accepted-копии, полнота snapshot payload и SQL-схема.
   `FineTerrainZRun` хранит ключи, а не свойства записей реестра — это
   обязательный вход инвентаризации, не доказательство материализации тела.

10. ~~Изоляция файлов и атомарность публикации pack~~ **РЕШЕНО
    2026-10-24**: content-addressed storage с долговечностью содержимого
    и имени; межпроцессная блокировка по hash и финальная проверка GC;
    immutable manifest; короткий DB commit с terminal outcome, handoff
    и CAS. Производные SQL принадлежат artifact. Удаление guard — только
    после всех гарантий протокола. **Детализация:** storage adapter,
    Windows crash-тесты и schema/read-фильтры производных таблиц.

11. ~~Provenance частично обновлённого pack~~ **РЕШЕНО**: manifest
    описывает immutable части с собственными dependency stamps; новый
    artifact сохраняет ссылки на неизменённые части базового pack.
    До активации проверяется совместимость, включая новый L2/родительский
    L0. **Детализация:** схема частей/SQL-наследования и predicates
    совместимости для каждого вида зависимости.

12. ~~Зависимости от состава коллекций — принцип~~ **РЕШЕНО**: capture
    фиксирует ревизии состава контейнеров; frozen list/candidates видят
    прежнее membership, включая отсутствие новых объектов. Отсутствие
    объекта среди выбранных members не доказывает независимость.
    **Детализация:** перечень контейнеров/выборок, их stamps и
    проверяемый критерий независимости добавления (связано с п.7).

13. ~~Согласованный capture и порядок активации результатов~~
    **РЕШЕНО 2026-10-24** — freeze чтения (snapshot isolation, см.
    «Freeze in-flight») + CAS-активация с `ready_inactive` outcome и
    монотонным `activation_seq` (см. «Публикация и транзакционная
    модель»). Capture-finalize одной короткой транзакцией проверяет
    revisions, регистрирует holder и pins, сериализован с writers/prune.
    Максимум три попытки capture, затем `capture_contended`. V1 после
    restart прерывает незавершённый bake; новый запуск — новый capture.
    Terminal outcome делает commit идемпотентным без повторной активации.
    **Детализация:** op registry, recovery и реализация сериализации.

14. ~~Revision vs удержание тела~~ **ПРИНЦИП РЕШЕН**: семантическая
    правка меняет revision, держатели определяют сохранение старого
    тела; учитываются и accepted sets/artifacts без in-flight. Учёт
    начинается с первого capture инициализации, до bake.
    **Детализация:** монотонный seq-носитель, учитывающий изменения
    между stamp-операциями; правила canonical hash остаются в п.16.

15. ~~Полнота ref-integrity и атомарная замена ссылок~~ **ПРИНЦИП РЕШЕН**:
    boundary проверяет итоговый граф всей атомарной мутации, исходящие
    ссылки изменённых объектов и затронутых потребителей. Проверка и
    запись в одной транзакционной границе. Latest rename не переписывает
    pinned artifacts/accepted sets: нужные старые тела защищены holders.
    **Открытая детализация:** точный охват/инвентарь ссылок и правила
    явного override; неявный fallback запрещён.

16. ~~Object revision, planning fingerprint и authored-семантика~~
    **ПРИНЦИП РЕШЕН**: revision set — provenance/pinned resolve;
    planning fingerprints — фактические проекции алгоритмов с версиями
    схемы/алгоритма и зависимостями планов. Canonical source representation
    сохраняет значимое authored-присутствие полей, включая round-trip
    старого тела. Label-only bump не меняет semantic revision или
    planning fingerprints, label хранится отдельным stamp.
    **Открытая детализация:** формат authored-presence, политика исключений
    semantic hash по моделям и точные правила семантического равенства
    в типе SourceRevision (label не участвует).

При детализации приёмки зафиксировать сценарии: восстановление accepted
старой ревизии после перезапуска; обратный порядок завершения двух
операций; частичный refine с прежними chunks/L0; добавление кандидата;
сбой между записью blobs и активацией manifest; гонки staging/GC
(включая reuse hash); неизвестный исход commit и повтор по operation_id;
невидимость staged SQL; capture-finalize против writers/prune;
исчерпание трёх попыток capture и остановка workers перед освобождением
pins. Windows crash-тест проверяет долговечность содержимого и имени.
Для п.15: невалидная новая исходящая ссылка; атомарный import target+referrer;
rename+replace_with по итоговому графу; pinned artifact после rename latest.
Для п.16: отсутствующее поле vs явно заданный default с разной семантикой,
round-trip held-тела, label-only bump, нерелевантная плану правка entry,
релевантная правка и изменение версии алгоритма/схемы.
Проверки stamp и diagnostics сами по себе не заменяют проверки
согласованности публикации.

## Рудименты к удалению (anti-rudiment list)

При приземлении этого трека следующее удаляется полностью, без
transitional-остатков:

- `application/worldData/planning/guards/sourcePublication.py::
  SourcePublicationGuard.require_fresh` — transitional OCC.
- `application/worldData/planning/guards/sourceRevision.py::
  require_current_source` и `SurfacePlanningStale` — та же судьба;
  guards/ папка сворачивается или остаётся только для нового
  mutation-boundary collaborator.
- Сайты вызова guard:
  `WorldSurfaceMaterializationOrchestrator.materialize_pack_detailed`
  (require_fresh + recalc + save в transaction_if_needed) и
  `PackMaterializationOrchestrator._materialize_l0_pack`
  (require_fresh + `finalize_pack_on_world`) — `require_fresh`
  заменяется полным owner-side commit-протоколом (manifest/stamps,
  holder handoff, terminal outcome, CAS), после подключения всех его
  гарантий. `finalize_pack_on_world` адаптируется к активации artifact;
  прежний `save_manifest` сам по себе больше не является публикацией.
- DONE PC-9 review cleanup (2026-10-24): `WorldPackWriter.maybe_checkpoint_manifest`
  удалён как мёртвый публичный API вместе с двумя assert_not_called в refine
  tests. Нижний слой не владеет публикацией прогресса; owner при необходимости
  владеет checkpoint. В целевой модели checkpoint использует общий
  commit-протокол. Повторное удаление API в этом треке не требуется.
- `FineChunkPersist.persist_rect` — вызов `maybe_checkpoint_manifest`
  удаляется PC-9; `FineChunkPersist.finish` — `save_manifest`
  выносится PC-9; под этим треком нижняя публикация запрещена
  окончательно.
- `WorldPackWriter.publish_settlement_structure` — собственный
  `save_manifest` уходит на уровень owner'а операции
  (C11/settlement).
- Тесты «guarded stale write rejection» / SurfacePlanningStale-кейсы —
  заменяются вместе с классом только после подключения всего протокола:
  frozen reads, удержание тел, GC-защита blobs, изоляция SQL,
  совместимость частей, CAS и восстановление после сбоев. Одних тестов
  revision-set stamp и mutation-boundary diagnostics недостаточно.
- Аннотации SUPERSEDED в geo-1-designed-water.md — снимаются при
  переименовании плана в -done после сдачи трека.

Standalone-owners, получающие явную публикацию под PC-9 (persist
больше не сохраняет; в целевой модели — общий commit-протокол):
`FineTerrainRefineOrchestrator.refine_rect`
(покрывает `refine_queued_chunk` и debug route `map.py`),
`FineTerrainRefineOrchestrator._run_refine_phase` — НЕ сохраняет
(scene/path идёт под bake op, owner — bake orchestrator),
`ChunkRefineWorker.drain_queue`/`drain_persisted` — не сохраняет
(drain под bake op).

## Исторический implementation-скелет — не текущий scope

Порядок ниже заменён разделом «Актуальные следующие шаги (2026-11-15)». Это карта прежних сквозных зависимостей, не разрешение реализовывать storage Artifacts, publication/Pack или переводить чужие bake/refine/checkpoint producers в Source-плане. Source-owned обязанности разбираются в архитектуре ядра; внешние работы остаются у владельцев и учитываются интеграционным техдолгом. До принятия конкретных срезов этот список не используется как очередь реализации.

1. Инвентаризация: captured inputs, baked-артефакты (system_ref vs
   значения), точки мутации (import/worldEdit/library ops/реестры),
   список versioned POJO для `__source_contract__`; все shared SQL rows,
   пишущиеся до commit, границы authored/derived; зависимости частей
   pack и контейнерных выборок. Детализировать п.15–16: инвентарь ссылок,
   override, canonical authored-presence и исключения semantic hash.
2. `SourceObjectContract` + `__source_contract__` на entry POJO +
   SourceObject projector поверх WorldSlice (контейнер) / library
   membership (member identity) / entity uid; canonical representation
   с сохранением значимого authored-присутствия и отдельным label stamp.
3. Revision set: seq + content_hash; монотонный seq-носитель;
   retained bodies и holders, resolve по pinned/accepted set, tombstone,
   ревизии membership; mutation boundary с проверкой итогового графа
   атомарной мутации согласно п.15. Конкретная схема тел — по итогам п.1, обязательная
   доступность held-тел реализуется уже здесь.
4. Capture-finalize: короткая транзакция проверки и pin, сериализация
   с mutation boundary/prune; frozen reads и candidates; максимум три
   попытки, `capture_contended`; restart/отмена и остановка workers.
   Planning fingerprints — по закрытому решению п.16.
5. Content-addressed storage adapter: долговечность данных/имени,
   staging holders, межпроцессная блокировка по hash, повторная проверка
   GC; защита reuse hash, Windows crash-тест.
6. Artifact/operation records, immutable manifest и dependency stamps
   частей; ссылки на унаследованные части и проверка совместимости
   L2/L0. Производные SQL с artifact_id, невидимые до активации,
   единый выбранный artifact для чтения SQL/файлов.
7. Короткий commit: manifest/stamps, handoff source/blob holders,
   CAS activation_seq (включая restore), terminal outcome active либо
   ready_inactive; idempotent retry и recovery неизвестного исхода.
8. Все owners bake/refine/checkpoint/settlement переводятся на общий
   протокол. Удаление publication guard — после подключения frozen
   reads, retained bodies, GC-защиты, изоляции SQL и совместимости
   частей с проверками конкурентных операций и сбоев.
9. Source adoption preview для игры игрока (ADD/CHANGE/REMOVE/RETAIN/
   PLAYER), GC ревизий и stale-scope политика.

ТЗ требуют правок: `tz_runtime_world_edit_policy.md`,
`tz_template_library_packs.md`, `project_data_storage_tz.md` (N+1 +
версии), `tz_terrain_generation.md` (capture/persist cycle).
