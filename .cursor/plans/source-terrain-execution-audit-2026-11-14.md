# Source: статическая проверка Terrain execution

2026-11-14. Шаг 1 [основного плана](world-source-versioning.md). **IN PROGRESS / NOT ACCEPTED.** Это evidence по текущему коду, не новый контракт и не разрешение реализации. Owning решения фиксируются в [Terrain dossier](terrain-source-execution-contract-dossier.md).

## Подтверждённые пути совместимости

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

1. Terrain: окончательные legacy schema/serializer и strict POJO правила; полный generic caller inventory. Одобрение пользователем поля hills_authored уже отражено в dossier, повторно выбирать representation не требуется.
2. Terrain и владельцы ссылок: точный ref-integrity roster, nullable/missing/foreign и inbound delete semantics. Отсутствие проверки в найденном caller не доказывает отсутствие ссылки.
3. Terrain/Source/Artifacts: окончательные manifest/format, membership semantics, execution binding и canonical vectors; отсутствие неявных settings/dependency reads.
4. Source: сверить owning ответ с этим evidence и обязательными критериями проекта; закрыть шаг только после устранения конкретных OPEN.

Owning ответ получен и записан в §5a Terrain dossier. Он подтверждает caller/bootstrap зависимости, добавляет существующие canonical registrations и ref candidates. Ref candidates не равны принятым scoped mutation guards. Разделение legacy input и canonical validation context, совместимость ID 17, stored-authored/effective-normalized bootstrap и оставшиеся owning решения требуют закрытия до приёмки. Runtime код, SQL и DAG не изменены; runtime tests/golden vectors не запускались. Полный контракт и шаг 1 не приняты.
