# Pack — остаток локальной приёмки после трассировки payload

Сверка 2026-11-12. Основание: [обязательные критерии домена](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена), [основной план](world-pack-v2-single-manifest-contract.md), [контракт Pack](pack-v2-domain-contract-spec.md), [актуальные write-операции](pack-v2-public-write-operations.md). Это сводка проекта и статических traces, не результат запуска тестов или приёмка runtime.

## Актуальный остаток после сверки bindings — 2026-11-13

После исправления консистентности ТЗ и appendix используют единый `PackPreparationBody(state, capture, scope)` с конечным state на входе final prepare. [Единая таблица поставки](world-pack-v2-single-manifest-contract.md#единая-таблица-зависимостей-и-завершения-шагов) фиксирует зависимости и результаты этапов, подключение отдельной сериализации и порядок cutover → удаление legacy → version audit. Старый общий gate write-плана заменён условиями входа конкретного среза; новых согласований уже решённых union/release/settings не требуется.

[Общая приёмка текущего scope](pack-current-scope-acceptance.md) выполнена по всем обязательным критериям. Локальные границы рассмотрены; полная цепочка не принята из-за точечных неподтверждённых atomic/resource/Transition bindings. Preparation union, metadata outputs, release и settings исключения не являются повторно открытыми вопросами. Отсутствие реализации само по себе не использовано как причина отказа в приёмке плана.

Уточнение scope по решению пользователя: encoding identity, canonical registration и exact READY recovery ведутся в [отдельном плане сериализации/десериализации](pack-serialization-deserialization.md). Не перечислять их далее как блокеры независимого текущего Pack scope; они остаются обязательной интеграцией для готовности соответствующего runtime-пути. В отличие от старой сводки ниже, in-memory identity probes уже выполнены и записаны в activation vector; production tests не выполнялись.

Этот раздел уточняет более ранние OPEN ниже: наличие описанного проекта не равно отсутствующему контракту, а наличие контракта не равно выполненной реализации. Runtime и тесты в текущей последовательности не менялись/не запускались. Полная приёмка плана ещё не объявляется.

| Категория | Остаток / состояние | Следующее действие |
|---|---|---|
| Pack: diagnostics конкретизированы | Preparation union согласован; pre-OWNER activation отказы согласованы; шесть post-OWNER predicates сверены с кодом и ports | Реализовать один описанный набор без зеркальных ошибок. Atomic conflict/resource/lifecycle carriers остаются точечными внешними bindings; canonical identity/registration/recovery ведутся в отдельном плане |
| Pack: свести окончательную цепочку | Локальные write, metadata describe/bind, pin mapping, final positions check, closure, prepare/activate/release уже описаны в отдельных документах | Проверить совместно Input/Output/Error и ответственность классов; старое OPEN «metadata outputs отсутствуют» не повторять без сверки актуального write-плана |
| Pack: проект описан, реализация впереди | 10 address roles → 7 bindings, ports/descriptor roster, payload rules, internal resource signals и бюджет чтения | Реализовывать только после обязательной приёмки соответствующего плана; проверять deep immutability, guards, error mapping, composition и сохранение старой логики |
| Pack: доказательства cutover | Реальные callers, порядок writes, отсутствие скрытой orchestration, legacy/version audit | Проверки по правилам проекта при реализации; документальный trace не заменяет runnable evidence |
| Внешний контракт Transition | Исторический validation context для custom transitions | Передать подготовленное уточнение из settlement trace владельцу; Pack не выбирает snapshot/registry API и не использует latest fallback |
| Внешние atomic bindings | Adoption/holds и release — Artifacts; scoped activation — Publication совместно с Pack | Использовать конкретный согласованный порт владельца; не создавать второй transaction/holder store. Ограничивает зависимую операцию, не всю доступную работу Pack |
| Владельцы форматов | Недостающие ограничения одного payload, распаковки и структуры | Согласовывают владельцы payload. Pack не назначает новые fixed caps; предложение собрать все profiles в world_pack снято |
| Отдельная работа Source | Конкретный source_proof | Другой агент; не переопределять тип и не открывать вопрос повторно |
| Явно отложено | PACK-METADATA-PLANNING | Placeholder разрешён; не блокирует разработку или приёмку текущего Pack scope |

Принятые уточнения: climate сохраняет alias/coercion/defaults, нулевые размеры допускают только пустые samples, отрицательные запрещены; grade при правильном schema_id допускает отсутствующий cells; порядок locations index и settlement наложения сохраняется. Hydrology сохраняет owning profiles, Pack — собственный manifest budget и PackPartReadBudget операции. Повторного согласования этих решений не требуется.

Ссылки на актуальные проекты: [bindings](pack-payload-binding-roster.md), [JSON signal](pack-json-budget-signal.md), [владение лимитами](pack-budget-enforcement.md#источники-значений-сверка-2026-11-13), [settlement owner request](pack-settlement-binding.md#уточнение-границы-по-фактическим-callers-2026-11-13), [позиционные связи](pack-locations-index-binding.md#конкретный-final-admission-без-нового-evidence-dto). [Preparation union](pack-preparation-issue-union.md) уже согласован; [локальная сверка activation errors](pack-activation-error-contract.md#итоговая-сверка-post-owner-admission-с-кодом) завершена. Следующий шаг — общая приёмка текущего scope по обязательным критериям с явными внешними зависимостями; при реализации обязателен implement-plan.

## Что не открывать повторно

- Решение пользователя 2026-11-13: публичный CRUD `manifest_max_bytes` исключён отдельным пунктом общего правила. Это конфигурация при создании storage binding до его пересоздания, без hot update/сервиса настроек; `None` означает отсутствие регистрации. Формальный CRUD-пробел именно этого поля закрыт. Исключение не распространяется на остальные settings или payload budgets и не означает полной приёмки Pack.

- Wire/storage manifest и исключение registry_hash/wilderness_tiles_total/строкового location z_band уже согласованы в основном плане. Codec_version/payload_format сохраняются. Это решения, а не выполненная миграция кода.
- [Настройки](pack-v2-domain-contract-spec.md#5-crud-и-настройки-не-подменять-семантику): источник manifest_cache и immutable lifetime CachePolicy приняты. Не предлагать hot settings service из-за общего CRUD-критерия. Остаётся формальная сверка владельца каждой операции, а не повторный выбор политики.
- PACK-METADATA-PLANNING — разрешённый пользователем отложенный mapping; **не блокирует разработку и приёмку текущего объёма Pack**. Не включать его в нижеследующие локальные блокеры под другим названием. Concrete Source proof разрабатывается отдельно; фиктивные proof/PlanRef и всегда успешные проверки не разрешены.
- DAG владеет последовательностью публичных операций. Pack write-методы изменяют immutable state; final prepare не исполняет их список. Defaults и готовые payload, включая grade merge, поступают от producer.
- Миграция внешних callers, Source/producer pipelines и новые DAG-ноды не являются разработкой Pack. Отсутствие такой миграции не запрещает завершать конкретный локальный контракт.

## Остаток Pack-owned работы — пять рабочих групп

Это группировка связанных задач, не утверждение, что осталось ровно пять вопросов или пять правок.

| Группа | Уже зафиксировано | Что ещё предъявить для локальной приёмки |
|---|---|---|
| P1. Согласованная схема и публичные write-контракты | State передаёт DAG; local/final admission разделены; assembler строит manifest из конечного state; shared records не копируются; [write_spatial_root конкретизирован](pack-spatial-root-write-contract.md) как PROJECT | Свести объявления типов и сигнатур в один непротиворечивый набор; завершить Pack-owned fields/error mapping, transport bound и roster. Spatial write добавлен в method/type/disposition roster, общие gates не закрыты этой декларацией. Внешние proof/coverage mappings учитывать отдельно, не изобретать их в Pack |
| P2. Artifact/read bindings всех payload | Все 10 ролей получили отдельный trace либо раздел §6.8–6.10; известны реальные POJO и различия адресов | Конкретные descriptors, bounded decoders, recursive strict admission, immutable typed output, error mapping и composition. Для новых budgets нужны обоснованные значения; existing hydrology limits переиспользуются. Trace не равен готовому binding |
| P3. Full manifest, closure и prepare | Единый parts/assembly/provenance, существующие stage/seal/READY checks; полный closure принадлежит Pack | Реализуемая связка конечного state с codec/readers и полным удерживаемым набором; не доверять other_members как доказательству полноты. Проверить inherited части, metadata dependencies, root→shards и exact READY record. Принятые внешние atomic ports использовать без второго store |
| P4. Activate/release и публичные отказы | Существующие candidate/result/ledger; [activation trace](pack-activation-refusal-trace.md), [retention trace](pack-inactive-retention-trace.md), [release project](pack-candidate-release-contract.md) | Полная Pack-owned диагностика и canonical registration, identity/fingerprint, wrapper→implementation и соответствие внутреннему atomic binding. У release отдельно подтвердить durable repeat после GC, сохранение shared children и отсутствие head mutation; неизвестный atomic binding остаётся внешним ограничением этой операции |
| P5. Консолидация приёмки и cutover | Порядок источники → evidence → manifest → codec/readers; отдельный этап после удаления legacy уже обязателен | Полный class/POJO/error roster, CRUD-disposition и доказательства критериев ниже. В реализации — профильные проверки, затем перенос/удаление в утверждённом порядке и отдельный аудит comments/methods/variables/version markers. Не объявлять единственный runtime завершённым при наличии aliases/fallback |

## Payload: результат инвентаризации
 
### Сводная проверка после write/order/lifecycle срезов

Учитывает [порядок старых вызовов](pack-write-order-trace.md), локальные describe/bind, coverage и lifecycle разделы [write-плана](pack-v2-public-write-operations.md). Вердикт текущей документальной сверки: **направление и локальные обязанности конкретизированы; единый контракт ещё не принят из-за перечисленных ниже собственных несогласованностей**. PACK-METADATA-PLANNING и перенос внешних callers не используются как причина этого вывода. Реализация и runtime тесты не выполнялись.

| Приоритет / находка | Доказательство | Исправление в текущем Pack |
|---|---|---|
| P1 — параметризованный part несовместим с путями диагностик | **Исправлено в проекте:** public fields используют named concrete subclasses общей _PackPartInput; roster всех 10 ролей и spatial appendix синхронизированы. Поля наследуются, ModelIdentity не ослабляется | При реализации проверить nested paths, canonical registration и strict revalidation; runtime-приёмка не заявляется |
| P1 — одновременно описаны две несовместимые формы write inputs | **Исправлено в проекте:** start_empty без initial_provenance; вычисляющие writes без metadata proof; present proofs валидны, изменённые снимаются; отдельный bind и полный final admission. Основная таблица, domain appendix и ТЗ синхронизированы | Реализационные тесты invalidation/preserve/bind остаются обязательными. Planning mapping остаётся отложенным и не блокирует текущий Pack |
| P2 — требования ограничений объёма не сведены в конкретный Pack binding | Transport bound state/start и бюджеты части payload упомянуты как требования, но единая привязка к существующим настройкам/форматам не предъявлена | Инвентаризировать existing limits и их enforcement до allocation/decode; не придумывать лимиты по числу locations/tiles. Зафиксировать конкретный источник каждого локального bound |

Направления, которые не нужно проектировать заново: отдельные public writes и state chaining; shared metadata; describe/bind вместо расчёта metadata в DAG; coverage отдельно от wilderness status; READY replay без повторного finish; полный retention set; spatial root add/replace; сохранение различий batch/single L0 и detailed. Для порядка теперь есть конкретный trace, включая parent-light barrier и callback-order; его нельзя заменять общей фразой «всё по списку».

Остаток P2–P4 в таблице групп выше сохраняется как собственная работа bindings/codec/errors и интеграционные подключения, а не повторный выбор архитектуры. Подтверждение exact READY replay и atomic lifecycle должно соответствовать реальному binding, но не требует от Pack создавать второй store. Полная реализационная приёмка позднее требует профильных проверок; статический trace не отмечается как пройденный тест.

Источники budgets и точки enforcement теперь сведены в [отдельную проверку](pack-budget-enforcement.md): existing manifest/spatial caps отделены от отсутствующих decompression/decoded limits и state transport. Числовые defaults не придуманы. Остаток P2 — конкретные per-format limits/composition и проверка памяти; inventory не считается реализацией защиты. Две P1-несогласованности выше исправлены на уровне документов; это не закрывает остальные группы реализации и не является приёмкой runtime.

### Существующие payload traces

Единая [карта payload bindings](pack-payload-binding-roster.md) связывает 10 ролей с 7 общими payload-контрактами, existing/project descriptor IDs, T и decoder modules. Read и final prepare используют одну регистрацию schema/profile; отдельные direct-domain calls не вводятся. Новые IDs помечены PROJECT; реальная composition, лимиты и strict decoder implementation остаются работой P2.

| Роли | Источник | Существенный оставшийся критерий |
|---|---|---|
| map_tile | [§6.8–6.10 Pack](pack-v2-domain-contract-spec.md#68-следующий-срез-пункта-2-map_tile-formatread-binding) | Immutable WorldMapTileWire, строгие клетки/enums, bounded decode; sparse не запрещается без coverage конкретного результата |
| wilderness_chunk, location_terrain | [FineTerrain](pack-fine-terrain-bindings.md) | Один payload, разные origin/bounds; location lx/ly не ограничивать wilderness chunk_columns |
| settlement | [Settlement](pack-settlement-binding.md) | Framing и cumulative budget; owning historical transition registry, без latest lookup и decoder rebuild |
| climate_coarse, climate_fine | [Climate](pack-climate-bindings.md) | Existing format сохраняется; WP-C7 strict/empty policy/decoded budget, immutable samples; width*step=span не добавлять |
| locations_index | [Locations index](pack-locations-index-binding.md) | Порядок pins влияет на map_tile.location_pin; нельзя сортировать как множество UID |
| spatial_root | [Spatial](pack-spatial-root-binding.md) | Bytes format не выполняет semantic decode; root/shard identity, полный closure и production registration |
| tile_grade_slots, location_grade_slots | [Grade slots](pack-grade-slots-bindings.md) | Один JSON binding; duplicate XY reject по ТЗ; world XY и evidence split, готовый merge от producer |

## Проверка обязательных критериев

| Критерий | Место и вывод |
|---|---|
| Нет выбора следующей стадии в pipeline | Write-план: DAG выбирает метод, PackPreparationService применяет одно изменение; prepare только завершает. Граница сформулирована. Фактический caller trace требуется при реализации |
| Нет скрытой orchestration | Контракт Pack §1–3: одна делегация wrapper, без Cache callback/producer/retry workflow. Worker/event/API обход не разрешён; завершённая production цепочка сейчас не доказана |
| Нет прямых публичных междоменных вызовов | Основной план: Source/producer → DAG → Pack. Внутренние storage/commit ports не разрешают запуск чужих публичных операций. Для каждого concrete binding ещё нужна проверка вложенных effects |
| Ответственность каждого класса | Pack §3, write-plan и release roster дают основу; не весь scope сведён в полный реестр с dependencies/effects/acceptance/rejection. **OPEN**, отсутствие сведений не считается успехом |
| Public contract / pipeline / implementation | Prepare/read/release разделены, state не раскрывает backend/lease/callback. Старые формы body/assembler в общем appendix синхронизированы с write-планом. Полный freeze типов и activation binding ещё **OPEN** |
| Неизменность порядка | Основной план и write disposition: источники → evidence → manifest → codec/readers; sync_grid_metadata → L0 writes → set_last_l0_mode. Не добавлять orchestration в assembler. Callers переносить до удаления обхода, затем отдельный version audit |
| CRUD данных и настроек | Pack §5 и публичные write/release проекты. Нужна финальная построчная C/R/U/D сверка конкретных классов/методов/Input/Output/Error. Принятые Cache/settings решения сохраняются; они не разрешают придумать недостающую API |
| Междоменный CRUD-протокол | Карта владельцев и Source appendix разделяют ответственность. Неподтверждённые exact bindings помечаются внешними; они ограничивают зависимый маршрут, не всю работу Pack. PACK-METADATA-PLANNING сохраняет явную отсрочку |
| POJO и field/logic errors без дублей | Shared payload POJO и существующие errors переиспользуются; write-plan содержит mapping диагностик. Полный реестр всех полей/ошибок/owners и проверка отсутствия пересечений ещё **OPEN**; новый зеркальный DTO не является решением |

**Итог проверки:** полная приёмка Pack не объявлена. Локальные data/CRUD/class/POJO, payload и межчастные traces сведены; preparation union и единый release согласованы, activation predicates сверены. Устаревшие OPEN о выборе этих решений не являются новым рабочим списком. Актуальный остаток указан в верхней таблице: общая приёмка текущего scope, реализация и проверки, точечные внешние bindings. Encoding/registration/exact READY recovery — отдельный план; PACK-METADATA-PLANNING отложен и не блокирует текущий scope. Production runtime readiness требует выполненных проверок и подключения соответствующих bindings, а не одного текста проекта.
