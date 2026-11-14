# Source: статическая проверка Terrain execution

2026-11-14. Шаг 1 [основного плана](world-source-versioning.md). **IN PROGRESS / NOT ACCEPTED.** Это evidence по текущему коду, не новый контракт и не разрешение реализации. Owning решения фиксируются в [Terrain dossier](terrain-source-execution-contract-dossier.md).

## Подтверждённые пути совместимости

**Изменение ограничения 2026-11-14:** пользователь строго запретил адаптацию старой формы. Ниже перечислены evidence текущего кода, а не требования сохранить старые входы. Legacy before-validator, serializer compatibility, dual-read/fallback и вывод hills_authored по отсутствующим полям исключены из целевого решения. Проверка callers теперь означает прямой переход на новый строгий контракт. Bootstrap не может обходить это ограничение автоматической нормализацией. Старые bytes не изменяются; наличие исторического формата требует явного решения о границе поддержки, а не скрытого адаптера.

Все пути ниже относительно корня репозитория.

| Путь | Наблюдаемое поведение | Что требуется при приёмке |
|---|---|---|
| `backend/app/dataModel/terrain/terrainRegistryEntry.py` | frozen, но eligibility — list; extra ignore; authored hills определяется через fields_set; with_eligibility копирует list | Проверить глубокую неизменность, strict/revalidation и переход на согласованное явное hills_authored; отсутствие mirror DTO |
| `backend/app/dataModel/terrain/worldTerrainRegistry.py` | RootModel[list], canonical constructors создают lists; entry_for выбирает первое совпадение | Проверить constructors и duplicate identity policy. Текущий порядок списка сам по себе не доказывает принятие SEQUENCE |
| `backend/app/dataModel/terrain/eligibilityRule.py`, `hillPolicy.py` | Frozen nested models; HillPolicy extra ignore; нет общей конфигурации revalidate_instances=always | Проверить вложенные значения и повторную валидацию; frozen верхнего entry недостаточно |
| `backend/app/application/jsonValidation/worldSlices.py::resolve_registry_list_world` | canonical_registry_wire, затем resolve_root_list и _apply_runtime_canonical_merge; последний дополняет canonical defaults и пересобирает list по identity | Не использовать этот read как доказательство stored membership или исходного authored body. Bootstrap должен явно определить источник и момент материализации defaults |
| `backend/app/application/jsonValidation/worldRow.py::terrain` | После registry resolve применяет terrain_masks.default_landcover с исходным raw registry | Это вычисленное представление с зависимостью от masks; оно не равно чистому Source projector. Исторический decode не должен повторять этот lookup |
| `backend/app/application/jsonValidation/facade.py::normalize_world` | После merge/validation применяет landcover policy, затем registry.model_dump(mode="json") | Проверить legacy export/import для absent, explicit null и policy; сериализация должна сохранять согласованную authored semantics |
| `backend/app/application/jsonValidation/terrainHillRegistry.py::apply_landcover_policies` | Presence берётся из raw wire; entries пересобираются через dict и WorldTerrainRegistry(list(...)); есть fallback canonical_defaults | Typed canonical body нельзя направлять в legacy presence helper. Проверить tuple construction и порядок membership |
| `backend/app/application/worldData/generators/terrain/landcover/planning/capturedSources.py::capture_landcover_policy` | Entry создаётся из subset с явным hills, eligibility=list; captured.hills_authored отдельно передаётся apply_to | При новой форме передать captured presence в entry, сохранить отдельный consumer subset. Соседний model_construct относится к LandcoverTerrainPolicy |
| `backend/app/application/templateLibrary/reliefTerrainSync.py::missing_terrain_entries` и `packs/domainAdapters/relief.py::prepare_world_refs` | По stored rows выявляются отсутствующие keys; canonical entries добавляются через model_dump(mode="json") к raw terrain_registry | Включить в writer/serializer inventory. Это templateLibrary путь, не разрешение расширять работу на ядро Pack; revision cutover требует owning writer integration |

## Вывод для первого среза

Stored registry, resolved registry и captured consumer subset — три разных представления. Выбор любого из них в качестве initial bootstrap input должен быть явно обоснован owning контрактом. Достоверную потерянную authored presence нельзя восстановить по текущим defaults. Bootstrap и mutation не должны скрыто зависеть от ambient masks или canonical catalog через обычный resolved-read.

После owning ответа проверен `backend/app/dataModel/terrain/encoding/surfaceBindings.py`: **регистрация уже существует** — ID 16 WorldTerrainRegistry, 17 TerrainRegistryEntry, 18 EligibilityRule, 19 EligibilityOp, 20 HillPolicy, 21 HillShape, 22 TerrainFillRole. Первичный поиск только в общих encoding directories был недостаточен. Добавление hills_authored меняет layout существующего ID 17; укрепление registry затрагивает ID 16. До принятия нужны trace потребляющих manifests и persisted/cache formats, правила совместимости старых bytes и vectors. Сам по себе новый Source format эту зависимость не закрывает. Рекомендация владельца — минимальный entry closure без registry ID 16; она ещё требует совместной приёмки.

## Проверка потребителей ID 17 и старых bytes

Дополнительная статическая проверка 2026-11-14:

* `application/worldData/planning/encoding/surfaceManifest.py` объединяет domain bindings в SURFACE_MANIFEST. `composition/planProviders.py::declared_binding` использует его для input validation/fingerprint и SurfaceEnvelopeCodec; cache namespace/version берутся из SurfacePlanBinding, а не автоматически из состава model_fields.
* `app/encoding/canonicalCodec.py::_decode_one` сверяет точный порядок всех имён полей с текущим model_fields **до** model_validate. Старый record ID 17 с 18 полями после добавления 19-го будет отвергнут как `missing, duplicate, extra or reordered record fields`. Legacy before-validator не может восполнить отсутствующее поле на этом пути. `decode` дополнительно проверяет encode(decoded)==original bytes. Автоматической миграции layout здесь нет.
* Однако наличие binding не доказывает существование валидных старых payloads. Текущий encoder поддерживает tuple/frozenset, но не list: обычный TerrainRegistryEntry содержит eligibility=list и не может пройти полное canonical encoding. WorldTerrainRegistry не frozen и имеет list root. Следовательно, для текущих валидированных моделей непосредственный round-trip IDs 16/17 уже недоступен. Исторические версии кода/внешние данные этим утверждением не покрываются.
* Реальные consumer projections отличаются: SurfaceSupportInput содержит TerrainSupportEntry с tuple eligibility, hills и собственным hills_authored; surfacePlanningCapture для relief создаёт TerrainMergeEntry(key, merge_rank). Изменение полного entry не означает автоматическое изменение layout этих projections. Вложенные EligibilityRule/HillPolicy общие: изменение их validation требует отдельной проверки, даже если поля не меняются.
* `application/worldData/planning/encoding/surfaceEnvelopeCodec.py` валидирует immutable envelope и использует текущий canonical decode без fallback. `application/cache/service/cacheService.py::get` повторно допускает cache hit и превращает невалидный payload в ошибку, а не автоматически в miss.
* `core/container/worldData.py` подключает MemoryCache/LegacyMemoryCache для planning. В проверенном production route не найден disk/SQLite backend, сохраняющий SurfaceEnvelopeCodec bytes. Это предел проверки маршрута, а не доказательство отсутствия любых исторических blobs. Фактические пользовательские БД/артефакты не сканировались.

**Вывод:** несовместимость старого 18-field record с будущим decoder доказана статически; наличие сохранённых таких records не доказано, а текущий encoder их не создаёт из валидного entry. Нельзя объявлять обязательную миграцию всей поверхности лишь по ID 17. Перед freeze нужен ограниченный compatibility gate: зафиксировать отсутствие поддерживаемого старого full-entry формата либо предъявить его конкретный writer/format и согласовать переход у владельца. Отдельно проверить неизменность existing projection bytes/fingerprints и nested validation. Новый Source format и execution_version сами по себе не версионируют existing cache contracts.

## Остаток шага 1

### Результат разрешённого semantic review

Проверка eligibility/RegionState завершена на уровне данных: nonempty fact string сохраняется без Source whitelist/normalization; current_type/pending_target относятся к live state, history.* — к истории. History содержит keys, не revision refs, поэтому автоматическая гарантия pinned resolve отсутствует. Evidence внесено в обзор ссылок и dossier. Это закрывает соответствующие вопросы inventory, не добавляя алгоритмы Regions, новые API или state migration. Runtime vocabulary admission/исторический as-of, если потребуются целевой интеграции, не объявлены готовыми.

Повторная сверка с основным планом закрыла лишний вопрос audit о допустимости dangling non-null refs: раздел «Ref-integrity latest и pinned-графов (решение 2026-10-24)» и п.15 уже определяют итоговый атомарный граф, проверку исходящих ссылок и запрет неявного fallback. Latest и pinned-графы разделены. Это перенесено в semantic evidence и dossier; новая политика/интерфейс не вводились. Для RegionState остаётся классификация конкретных live/history usages, а не повторное проектирование общего принципа.

Последующее решение пользователя 2026-11-14: cell_state_registry оставить как есть с пометкой «разобраться отдельно», **вне скоупа этого плана**. Ранее указанная остановка ради назначения владельца state больше не требует ответа в текущем этапе; дальнейшая проработка state прекращена. Найденные usages остаются evidence внешней зависимости, без объявления её runtime готовой.

Уточнение 2026-11-14 по прямому поручению пользователя: danger_level_registry закреплён за Locations в docs/tz_locations.md; прежние отметки неизвестного владельца danger сняты. Cell-state ownership не назначался. Проверка использования cell_state_registry: Python application consumers по имени не найдены; есть raw World column, SQL registry column и таблица cell_states. Поиск cell_states/CellState/default_state выявил Terrain default_state literals и enum, но не исполняемый resolver состояний. Формулы travel/danger и создание/история состояний описаны в ТЗ; их runtime готовность не подтверждена.

[Обзор ссылок](terrain-source-ref-integrity-contract-proposal.md) получен. Подтверждены namespaces category/material/lore и inbound cells, placement, RegionState, landcover map keys/values, terrain masks, hydrology shore. Это evidence текущих данных, не утверждение целевого API или полного динамического inventory. Отдельно подтверждено: missing observation имеет scoring-смысл, unknown fact token не получает этим разрешения; исторические transitions не равны live блокирующим ссылкам.

Проектирование временных adapter/error/composition signatures удалено из §4 dossier. Остаток семантики: dangling non-null refs, утверждённый vocabulary execution v1, live/history delete policy. Для state/danger владелец не установлен; по прямому ограничению пользователя уточнение этих правил остановлено до его решения. Никакой новый домен/порт для обхода остановки не создаётся. Шаг 1 целиком закрытым не объявляется.

**Коррекция scope 2026-11-14:** прежнее требование закрыть scoped/public API зависимостей до завершения шага 1 снято. Здесь фиксируются семантика ссылок, требования целостности и inventory существующего кода. Проектирование целевых междоменных контрактов/consistency bindings и DAG routes переносится на шаг 3 совместно с DAG. Отсутствие API не блокирует семантический результат; неразрешённая семантика по-прежнему требует решения. Общая приёмка implementation-плана не ослабляется. Агенту ref-integrity отправлена коррекция: временные signatures/ports не разрабатывать.

### Ответ Artifacts: registration/read проверены статически

Ответ владельца в `source-mutation-artifacts-publication-response-2026-11-13.md`, раздел «Terrain source-entry v1: format registration», сверен с текущими `application/artifacts/contracts/formatBackend.py`, `registry/artifactRegistry.py` и `contracts/blobRead.py`.

* Existing `ArtifactFormatRegistryBinding.register(contract, backend)` требует unique format key и exact contract instance у backend. `resolve(contract)` требует ту же identity. Новый registry или Source mirror contract не нужен.
* Кандидат `terrain.source-entry` v1: `ArtifactKind.BLOB`, `ArtifactFormatContract[bytes]`, `content_model=bytes`, `supported_versions=frozenset({1})`, `row_count=None`. Это соответствует existing BLOB constraints. TerrainRegistryEntry нельзя назначить content_model этого BLOB.
* `registry.validate(ref)` проверяет key/kind/version. Physical reader — `ReadableBlobBackend.read_verified(ref, *, max_bytes) -> bytes`; composition обязана предоставить эту capability явно. Затем owning Terrain canonical decoder проверяет форму и семантику. Physical hash/size не удостоверяют Source revision mapping или полноту proof.
* Proposed registration module `application/artifacts/registry/terrainSourceEntryFormat.py` ещё не реализован. Принятый byte budget, exact reader composition, GC protection и vectors остаются условиями приёмки. Format registration не добавляет defaults/landcover в body или closure автоматически.

Закрыт вопрос наличия подходящего registry/read port; runtime registration и полный execution contract этим не приняты. Для ref-integrity открыт ограниченный чат «Terrain dependencies: контракты ref-integrity»: результат ожидается в `terrain-source-ref-integrity-contract-proposal.md`, без реализации и без назначения этому чату владения всеми зависимыми доменами.

### Решение bootstrap и дополнительные результаты текущего прохода

Пользователь выбрал: **первые Source revisions фиксируют явно подготовленные authored-записи нового строгого контракта; defaults и landcover — отдельные зависимости**. Выбор authored/effective закрыт. Это не разрешение нормализовать существующие записи. Нет полного целевого input — нет bootstrap; storage/идемпотентность bootstrap относятся к шагу 2.

Дополнительно проверены прямые constructors в terrainZ, coverageBackground и landcover/collect: они создают WorldTerrainRegistry из list; целевые callers должны создавать tuple непосредственно. `registries/repairWorldDefaults.py::apply_import_normalize_to_world` получает world wire, вызывает normalize_world и изменяет world: этот repair нельзя включать в Source bootstrap. `worldBundle/worldCopyImport.py` проходит через world_handler.import_section, поэтому generic import boundary должен быть проверен до caller cutover. Fixture `fixtures/world_template.json` содержит terrain_registry и требует прямого задания новой формы; runtime converter не допускается. Список не является доказательством завершения всех dynamic/generic writer traces.

Конкретные внешние пробелы ref-integrity:

* `db/models/world.py` хранит cell_state_registry и danger_level_registry как dict; это не typed scoped read/delete contract.
* `dataModel/lore/loreRegistry/loreRegistryEntry.py` прямо обозначает body как stub; map namespace виден в WorldLoreRegistry, но atomic live-target/inbound guards этим не определены.
* `application/worldData/regions/regionFacts.py::value_for` возвращает None как при неизвестном имени, так и при отсутствии observation; flora не имеет зарегистрированного consumer. Метод не заменяет проверку допустимого vocabulary execution v1.

Актуальное распределение: на шаге 1 — данные и семантика, на шаге 2 — owning storage, на шаге 3 — целевые contracts/errors/consistency совместно с DAG, на шаге 4 — полная приёмка. Прежняя последовательность scoped contracts как prerequisite semantic dossier снята. Existing format/read ports сверены выше; это не подтверждает runtime registration.

Обязательные критерии проекта остаются открытыми в части точных dependencies/errors/classes и вложенных вызовов. Новые pipeline/DAG routes не назначались; inventory/projector не перепрыгнуты. Существующий proof не переоткрыт, зеркальные POJO не введены. Даже после очистки dossier шаг 1 нельзя объявлять полностью принятым лишь на основании выбранной representation.

1. Terrain: §5b dossier теперь задаёт строгие constructors/with-методы, полные required rosters и schema/export без адаптации. Остаётся полный generic caller inventory и его приёмка. Legacy schema/serializer не разрабатываются.
2. Terrain и владельцы ссылок: точный ref-integrity roster, nullable/missing/foreign и inbound delete semantics. Отсутствие проверки в найденном caller не доказывает отсутствие ссылки.
3. Terrain/Source/Artifacts: окончательные manifest/format, membership semantics, execution binding и canonical vectors; отсутствие неявных settings/dependency reads.
4. Source: сверить owning ответ с этим evidence и обязательными критериями проекта; закрыть шаг только после устранения конкретных OPEN.

Owning ответ получен; актуальный итог ограниченного этапа собран в §7 Terrain dossier. Семантический dossier подготовлен, а не принят как исполняемый контракт. Ref inventory не равен scoped mutation guards; их проектирование и обязательная приёмка остаются на соответствующих следующих шагах. Runtime код, SQL и DAG не изменены; runtime tests/golden vectors не запускались. Полнота generic caller cutover не заявлена.
