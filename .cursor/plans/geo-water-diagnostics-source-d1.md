# Water diagnostics / Planning source — D1 на приёмку

2026-11-07. D2-0 выполнен. Перенос S1 реализован и предъявлен на приёмку с открытым вопросом проверки source shape ниже. Владелец причин — Hydrology, транспорта — Planning, canonical source/Pack admission — Spatial/Pack. Решение пользователя: один целевой внутренний контракт, без legacy reader, aliases и compatibility adapter; runtime, fallback и продолжение обработки сохраняются. Этот D1 предъявляет контракты на приёмку, но не разрешает автоматически production cutover.

Основания: [GEO owning: spill и handoff](geo-1-designed-water.md#L16086), [River D1 §4 и §9](geo-river-routing-diagnostics-d1.md), [Spatial](spatial-distribution-domain.md#L4963), [ERROR-CONTRACTS F03/F07](error-contracts-1.md), [ТЗ Hydrology](../../docs/tz_terrain_hydrology.md), [ТЗ validation](../../docs/tz_json_validation.md), [ТЗ logging](../../docs/tz_logging.md). Контракты D2-0 зафиксированы в [ТЗ Hydrology](../../docs/tz_terrain_hydrology.md#water-diagnostics--контракты-переноса).

## 1. Фактическая причина и инвентарь

Прочитаны production definitions/callers и tests; новые runtime-прогоны этим документом не заявляются. Исходный прогон root: source_schema + planning providers diagnostics + canonical_codec — 24 tests, 11 errors, 5 failures.

| Старый путь | Реальные callers / роль | Целевой переход и gate |
|---|---|---|
| [waterDiagnostics.water_issue](../../backend/app/application/worldData/generators/hydrology/water/waterDiagnostics.py) создаёт базовый FieldPathError со string code/tuple path | [materialize_water](../../backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py): puddle, cannot-hold, spill, superseded | Четыре concrete facts §2; удалить string factory после всех callers, не alias |
| Тот же factory | [unresolved_water/finalize_water](../../backend/app/application/worldData/generators/hydrology/water/planning/waterAssemblyResult.py): terrain unresolved, no ocean, world ocean | Concrete facts §2; callback-путь отдельно от runtime delivery |
| Тот же factory | [HydrologyGeneratorService](../../backend/app/application/worldData/generators/hydrology/hydrologyGeneratorService.py): WATER_PLACEMENT_REQUIRED без callback | Тип причины определён ниже; переключение caller только после решения §6, не скрытая часть P1 |
| [deliver_water_issue](../../backend/app/application/worldData/generators/hydrology/water/waterDiagnostics.py) | WaterKindMismatchIssue из materializer; без callback вызывает report_issues/log_issues | Сам issue reuse без изменения; новый operational факт не передавать в ImportIssue |
| [ResolvedWaterLevels / resolve_water_levels](../../backend/app/application/worldData/generators/hydrology/water/waterBodyResolver.py) | materialize_water, finalize_water | Добавить готовые spill facts, не менять level resolution |
| [sourceSchema.require_source_diagnostics_v1](../../backend/app/application/worldData/generators/hydrology/encoding/sourceSchema.py) требует exact base FPE и удалённые поля | [packSchema.require_pack_schema_v1 / require_pack_record_v1](../../backend/app/application/worldData/generators/hydrology/encoding/packSchema.py) | Exact concrete roster §4; удалить старую проверку после атомарного cutover |
| [test_source_schema.diagnostics](../../backend/tests/spatial_pack/test_source_schema.py) и [storage fixtures](../../backend/tests/spatial_pack/test_storage_schema.py) | Base FPE, dataclasses.replace, старые reference/runtime_context/schema_id | Пересоздать fixtures на целевых facts; старые bytes не поддерживать |

Действующие коды: WATER_PUDDLE, WATER_CANNOT_HOLD, WATER_TERRAIN_UNRESOLVED, WATER_NO_OCEAN_DEPRESSION, WATER_LEVEL_SPILL, WATER_LEVEL_SUPERSEDED, WATER_WORLD_OCEAN, WATER_PLACEMENT_REQUIRED. Последний отсутствует в прежнем source roster: это runtime admission, не source diagnostic. WATER_KIND_MISMATCH уже имеет concrete owner [WaterKindMismatchIssue](../../backend/app/dataModel/hydrology/waterKindMismatchIssue.py), surface IDs 323/324; не мигрировать повторно.

## 2. Предлагаемый freeze фактов

Новый файл `backend/app/dataModel/hydrology/waterDiagnostics.py`; все модели BaseModel strict/frozen/extra=forbid/revalidate_instances=always. Все поля ниже обязательны, defaults отсутствуют; nullable только явно указанные. EntityUid reuse, уровни StrictInt (единицы существующего z_water_level), счётчики Annotated[StrictInt, Field(ge=0)]. Не создавать fake checked path, message JSON или универсальный failure context.

`WaterDiagnosticCode: StrEnum` — ровно восемь перечисленных WATER_* строк (без KIND_MISMATCH). В каждом fact `code: Literal[соответствующий enum]`, обязательный; plain string до enum conversion отвергается before-validator. Неизвестный code и лишние поля — ошибка контракта.

| Concrete fact | Поля кроме code | Disposition / факт |
|---|---|---|
| WaterPuddle | source_uid: EntityUid; cell_count: nonnegative StrictInt; minimum_cells: positive StrictInt | ERROR; cell_count < minimum_cells; существующий continue компонента |
| WaterCannotHold | source_uid: EntityUid; effective_level: StrictInt | ERROR. Условие из waterMaterialize.py — `source.authored and not any(surface_z[cell] < resolved.levels[i] for cell in source.seeds)`. В факт передаются UID источника и именно `resolved.levels[i]`. Проверка допускает равенство высоты клетки уровню воды как сухой случай. |
| WaterTerrainUnresolved | world_uid: EntityUid; message: StrictStr | ERROR; сообщение исходного ValueError из существующей catch-границы, возвращается прежний empty AssembledWater |
| WaterNoOceanDepression | world_uid: EntityUid; default_water_level: StrictInt | ERROR; существующая проверка auto_seas, без нового abort |
| WaterLevelSpill | source_uid: EntityUid; requested_level: StrictInt; spill_limited_level: StrictInt | FALLBACK; spill_limited_level < requested_level |
| WaterLevelSuperseded | source_uid: EntityUid; declared_level: StrictInt; effective_level: StrictInt; parent_system_uid: EntityUid \| None | FALLBACK; declared_level != effective_level; parent может отсутствовать |
| WaterWorldOcean | world_uid: EntityUid; water_cells: nonnegative StrictInt; world_cells: positive StrictInt | NOTICE; 2 * water_cells >= world_cells; не добавлять cap water_cells <= world_cells сверх producer |
| WaterPlacementRequired | world_uid: EntityUid | ERROR; отсутствует post-carve BasinSpec input; только runtime handoff §6 |

WaterTerrainUnresolved.message — диагностический текст произвольного ValueError, не enum и не управляющий признак; единственная граница преобразования `str(error)` в существующем producer. В ТЗ D2-0 явно записать это исключение StrictStr; не parse текста и не классифицировать произвольные исключения.

Reuse `WaterKindMismatchIssue` и HydrologyMaterializationCode без расширения enum чужими operational codes. Его checked WaterBody.kind сохраняется; новые operation facts — F03/F07, не F01.

## 3. Producer → carrier

`ResolvedWaterLevels` в существующем waterBodyResolver.py получает обязательное `spills: tuple[WaterLevelSpill, ...]`. resolve_water_levels формирует facts после расчёта own_levels в стабильном порядке sources, только для authored source с own_levels[i] < source.spec.z_water_level. Уровни/parents/unions не пересчитываются и алгоритм не меняется. Materializer использует этот готовый fact в прежней точке выдачи spill (сохраняет interleaving cannot-hold → spill → superseded), не выводит spill из итогового union level. Полнота соответствия source UID и повторов проверяется boundary тестами; дополнительный поиск по миру не вводится.

`WaterPlanDiagnostic[FactT]` как новый generic framework НЕ создавать. В том же dataModel файле определить **один concrete** `WaterPlanDiagnostic(PlanDiagnostic[WaterOperationalFact])` невозможно по принятому admission (union запрещён). Поэтому выбранная форма — восемь именованных concrete carriers: `WaterPuddleDiagnostic`, `WaterCannotHoldDiagnostic`, `WaterTerrainUnresolvedDiagnostic`, `WaterNoOceanDepressionDiagnostic`, `WaterLevelSpillDiagnostic`, `WaterLevelSupersededDiagnostic`, `WaterWorldOceanDiagnostic`, `WaterPlacementRequiredDiagnostic`. Каждый наследует PlanDiagnostic[свой fact], повторяет `issue: SerializeAsAny[свой fact]`, after-validator требует ровно disposition из §2. FPE mismatch остаётся в точном PlanDiagnostic с concrete WaterKindMismatchIssue.

`WaterPlanningDiagnostic` — закрытый union первых семи carriers + PlanDiagnostic (последний допускает только mismatch на source admission). Placement carrier исключён из source. Helper `create_water_diagnostic(fact: WaterOperationalFact) -> WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic` в waterDiagnostics.py application формирует carrier исчерпывающим сопоставлением точного типа, без emit. `WaterOperationalFact` — union восьми facts в dataModel; не BaseModel/Any.

Callback пути передают готовый carrier через существующий callback, ровно один раз. Аннотации water callbacks и collectors переходят на `DiagnosticCarrier` из River §4, При успешной публикации диагностика входит в PlanBuildResult, PlanEnvelope и fingerprint. На пути отказа Fine Water собирает ERROR до выпуска ревизии и передаёт их caller через PlanBuildFailure.diagnostics (§7.1). Сам carrier, generic admission и envelope — единый shared Planning slice, не копия в Water.

## 4. Target source/Pack schema и порядок без цикла

Инвентарь surfaceManifest на 2026-11-07: max ID=324; 323/324 заняты mismatch. River 325–328 предложены отдельным D1, кодом не заняты. Предложение Water: 329 WaterDiagnosticCode; 330–337 facts в порядке §2; 338–345 соответствующие carriers в том же порядке. Все RECORD, кроме enum 329. ID 337/345 Placement не включать в source manifest; surface registrations возможны лишь если runtime serialization consumer действительно нужен — этот D1 их резервирует, не требует лишней регистрации. Перед кодом повторить collision check; не перенумеровывать автоматически.

Target source roster: существующие payload/ref/value types + concrete checked-path types для mismatch + WaterKindMismatchIssue/HydrologyMaterializationCode + семь source facts/carriers + RiverRouteDiagnostic/RiverRoutingCode/RiverRoutingFailure/RiverPlanDiagnostic. Источник concrete bindings — согласованные surface IDs, отдельный source manifest остаётся явным subset. Abstract FieldPathError[Any]/BaseModel/PlanDiagnostic[Any] не регистрировать. ID105 exact PlanDiagnostic используется только для конкретного mismatch; другие facts имеют собственные carriers.

Closure больше нельзя выводить только из annotation DiagnosticCarrier[Any]. Проверять closure от `PlanEnvelope[CanonicalOpenWaterSource]` **и явного набора допустимых concrete carriers/facts**. Annotation общего carrier не разрешает произвольную модель; exact root registry/admission задаёт замкнутый набор. Source admission сверяет type, повторно валидирует carrier/fact и disposition; неизвестный registered-but-not-admitted carrier отвергается. Pack closure использует те же roots плюс storage roots; не расширяет source случайно всем SURFACE_MANIFEST.

Порядок: S1 shared Planning carrier → S2 Water facts/provenance + River DTO/registrations (без River producer cutover) → S3 единый source/Pack roster/locks/fixtures → единый S4 Water/River producer cutover вместе с Water reporting и publication refusal из §7.1. River D2 не должен ждать полного source producer cutover, который сам ждёт River D2: его DTO/registration steps выполняются prerequisite S2; source-schema tests на целевых fixtures возможны после S3, но **полный локальный P1 закрывается только после S4**. Source roster не урезать на шесть прежних RIVER codes ради зелёного теста. Production surface reporting P2 из River D1 остаётся отдельным gate: существующий surfacePlanningAssembler не принимает operational carriers. Подключение нового потока к prepare_captured_bundle/prepare_captured_geo_bundle допускается только после согласованного P2; локальные source/codec тесты не доказывают готовность этого consumer.

Не обещать прежние bytes/fingerprint для изменённых схем: для неизменённого доменного payload сравнить значения отдельно, а diagnostic bytes/lock diff объяснить. Старого decoder нет, fixtures пересоздаются; source/Pack guards не удаляются. Snapshot §20 не переносить автоматически на внутренний source; фактическое пересечение с snapshot-секцией требует отдельного решения владельца.

## 5. Файлы и проверяемые шаги

### S3 после приёмки S2 — параллельные треки

**S2 принят, S3 разрешён пользователем.** Выполнение S3 открыто. Ниже уточнён порядок работ строки S3 и проверок §7.0. Первая волна допускает три одновременных задания. У каждого файла один исполнитель.

| Трек | Можно делать сразу | Условие завершения |
|---|---|---|
| A. Source и shape 60008 | Владелец `sourceSchema.py` и `tests/spatial_pack/test_source_schema.py`. Воспроизвести P2 в двух свежих процессах. Реализовать воспроизводимое описание validator, явный перечень concrete roots из §4 и проверку допустимых фактов. Представить diff состава типов, alias и lock. | Два свежих процесса дают одинаковый **полный** shape 60008 и alias lock. Подмена validator обнаруживается. Целевые Water/River/mismatch проходят round-trip, посторонний carrier отклоняется. Передать B фактический roster и контракт тестовых helpers `diagnostics` и `ref`. |
| B. Pack и storage | Владелец `packSchema.py` и `tests/spatial_pack/test_storage_schema.py`. Параллельно с A готовить обход собственных storage roots, проверку дополнительных bindings и отрицательные тесты Pack. Сохранить точку сборки тестовых записей `records()` для C. | После A объединить фактические source roots со storage roots, сверить состав и прогнать source + storage вместе. Передать C проверенные `records()` и действующий Pack manifest. |
| C. Codec и retention | Владелец `tests/spatial_pack/test_pack_codec.py` и двух fixtures из §7.0. Сразу зафиксировать контрольные суммы исходных файлов, изучить replay/retention consumers и подготовить сценарии сравнения декодированных root/shard. | После совместного прохода A+B получить bytes целевым encoder, объяснить дельту каждого fixture, проверить чтение и повторное кодирование, bounded decode и pin retention. |

Причина порядка видна в коде. `require_pack_schema_v1()` вызывает source guard, а Pack manifest включает source entries. Тестовые зависимости идут от `test_source_schema.diagnostics/ref` к `test_storage_schema.records()`, затем к pack codec. Если общий вход ещё не готов, в отчёте трека указывается эта зависимость. Подмена guard, отдельная копия manifest или временный legacy reader исказили бы результат приёмки.

Команды из `backend`, с `$env:PYTHONPATH='.;tests'`:

```powershell
# A — запускать дважды отдельными процессами, сопоставить полный вывод
.\.venv\Scripts\python -c "from app.application.worldData.generators.hydrology.encoding import sourceBindings as b, sourceSchema, sourceShape; sourceSchema.require_source_schema_v1(); shapes, aliases = sourceShape.source_snapshot(); print(next(shapes[t] for i, t, _ in b.SOURCE_BINDINGS if i == 60008), aliases)"
.\.venv\Scripts\python -m unittest -v tests.spatial_pack.test_source_schema
# A + B
.\.venv\Scripts\python -m unittest -v tests.spatial_pack.test_source_schema tests.spatial_pack.test_storage_schema
# C и общая приёмка S3
.\.venv\Scripts\python -m unittest -v tests.spatial_pack.test_pack_codec tests.spatial_pack.test_bounded_decode tests.spatial_pack.test_manifest_pin_retention
.\.venv\Scripts\python -m unittest discover -s tests/planning/encoding/comparison -t . -v
```

Общий отчёт собирается на одной ревизии после C. В нём указать результаты команд, полный shape ID 60008 в двух процессах, изменения roster/locks и сравнение fixtures. Сухой A + корректный B и переключение producers остаются критериями S4. Здесь P2 обозначает дефект source shape; production reporting P2 из River D1 ведётся отдельно.

Все команды из backend, `$env:PYTHONPATH='.;tests'`; Python `./.venv/Scripts/python.exe`. До реализации §2/3/4 переносится в docs/tz_terrain_hydrology.md (раздел Water diagnostics), owning планы синхронизируются. Это D2-0; код до приёмки D1 не писать.

| Шаг | Точные изменяемые файлы относительно backend | Проверка / Done |
|---|---|---|
| S1 Planning | app/dataModel/planning/diagnostics/planDiagnostic.py; app/dataModel/planning/contracts/planEnvelope.py; app/application/planning/service/planFingerprints.py; tests/planning/contracts/test_contracts.py | `python -m unittest tests.planning.contracts.test_contracts`; concrete preservation, forged/Any rejects, mismatch reuse |
| S2 Water | новый app/dataModel/hydrology/waterDiagnostics.py; app/application/worldData/generators/hydrology/water/waterBodyResolver.py; app/application/worldData/planning/encoding/surfaceManifest.py; новый tests/geo1/fine_water/test_water_diagnostics.py; tests/test_hydrology_water_resolver.py | `python -m unittest tests.geo1.fine_water.test_water_diagnostics tests.test_hydrology_water_resolver`; все facts strict, spill before union, levels/UID unchanged |
| S2 River prerequisite | app/dataModel/hydrology/riverRouting.py; тот же surfaceManifest; tests/geo1/fine_water/test_river_diagnostics.py; tests/planning/encoding/test_canonical_codec.py | River D1 steps 2–3, `python -m unittest tests.geo1.fine_water.test_river_diagnostics tests.planning.encoding.test_canonical_codec`; конкретные DTO/IDs, producer ещё прежний |
| S3 source/Pack | app/application/worldData/generators/hydrology/encoding/{sourceSchema,sourceBindings,sourceShape,sourceLocks,packSchema}.py; tests/spatial_pack/test_source_schema.py, test_storage_schema.py | `python -m unittest tests.spatial_pack.test_source_schema tests.spatial_pack.test_storage_schema`; target encode/decode, malformed roster/unknown carrier/alias/shape, concrete closure, никаких старых readers |
| S4 Water callback | app/application/worldData/generators/hydrology/water/waterDiagnostics.py, waterMaterialize.py, planning/waterAssemblyResult.py; tests/geo1/fine_water/test_water_diagnostics.py; tests/geo1/fine_water/test_kind_mismatch.py | `python -m unittest tests.geo1.fine_water.test_water_diagnostics tests.geo1.fine_water.test_kind_mismatch tests.test_hydrology_water_resolver`; порядок фактов, независимый следующий компонент, значения без дельты |
| S4 River callback | exact файлы River D1 steps 4–7 | команды River D1; mixed Water/River source и publication; не новый runtime sink |

Поиск `rg -n 'ResolvedWaterLevels\(' backend --glob '*.py'` 2026-11-07 нашёл один constructor — return в waterBodyResolver.py:155. Других fixtures-конструкторов не найдено; повторить поиск перед S2.

## 6. Выявленные границы, включённые в атомарный S4

**Дополнительный обязательный gate до S4:** [fine/execution.py](../../backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py) и [fine/publication.py](../../backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py) собирают ERROR issues и поднимают PlanBuildFailure; [planningService.py](../../backend/app/application/planning/service/planningService.py) принимает только FieldPathError. Concrete operational facts туда не проходят. Расширение PlanBuildFailure и обработка его callers/catches уже предложены в §7.1 и входят в приёмку S4; расширять field-only исключение произвольным BaseModel запрещено. Пока этот контракт не принят, S4 BLOCKED даже при зелёных carrier/schema тестах. Сохранить отказ публикации Source terrain/water ERROR по ТЗ Hydrology §2250, не путать его с локальным продолжением materializer. Для routing policy иной: отказ одного intent не отменяет все принятые маршруты.

Materializer общий для callback и emit=None: поэтому его атомарный cutover S4 включает reporting §7.1. Нельзя оставить двойной factory/ветку старого FPE под названием промежуточной совместимости. S5 далее — имя reporting области внутри S4, не следующий самостоятельный gate.

**Согласовано пользователем 2026-11-07.** Для WATER_CANNOT_HOLD материализатор передаёт типизированный WaterCannotHold с source_uid, effective_level и прежней disposition=ERROR у carrier. Обработка соседних источников продолжается. На существующей границе Fine Water этот ERROR блокирует публикацию всей водной ревизии, а caller получает причину через PlanBuildFailure.diagnostics. Приёмочный сценарий включает сухой источник A и корректный B: B обработан, ревизия отклонена, в отказе доступна причина A. Формулировка «warning без фиктивного WaterBody» в ТЗ Hydrology (строка 699) отмечена как отдельное расхождение документации.

Для D2-0 уточнить в ТЗ границы слова «warning». Уровень сообщения относится к доставке в runtime-лог. Право Fine Water на публикацию определяет `disposition=ERROR`. Проверку стартовых клеток (`source.seeds`) сохранить буквально. Формулировка ТЗ о footprint и отдельная проверка валидности declare (`floor_z`) не являются заменой предиката producer. [Материализатор](../../backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py#L122), [ТЗ Hydrology](../../docs/tz_terrain_hydrology.md#L699).

Callback producer не логирует: формирует fact → carrier → collector, дальнейшая публикация не дублирует событие. Сериализация идёт из DTO штатным codec, без ручного dict. Сам факт не выбирает исход операции.

Без callback текущий deliver_water_issue при validate_only **или collect_only** отправляет все dispositions в report_issues; иначе log_issues. Новый operational fact не является ImportIssue; расширять ImportIssue зависимостью на Hydrology запрещено. Runtime/import handoff и WATER_PLACEMENT_REQUIRED переключаются атомарно с S4 по §7.1, с сохранением return apply и существующих publication refusal boundaries. ResolveReport остаётся для настоящих field issues; collect_only меняет доставку, не право публикации.

Удаление старого water_issue входит в завершение S4 после проверки нулевых callers. До атомарного cutover прежний сломанный код не превращается в compatibility adapter.

## 7. Приёмка и решения пользователя

### 7.0 Exact дополнительные файлы и нормы

S1 использует [ТЗ DAG: Input/Output](../../docs/tz_world_generation_dag.md#контракты-inputoutput-engine-dag-самостоятельный-dag-typing-1). S2–S4 используют [ТЗ Hydrology: frozen fine terrain](../../docs/tz_terrain_hydrology.md#geo-1-frozen-fine-terrain-input-before-accepted-basin-fill), [PC-0 routes/final water](../../docs/tz_terrain_hydrology.md#pc-0--routes-и-final-water-contracts-2026-10-23), новый Water diagnostics раздел D2-0. Reporting использует [ТЗ validation](../../docs/tz_json_validation.md) resolve/collect policy и [ТЗ logging: два слоя](../../docs/tz_logging.md#два-слоя). Эти ссылки являются колонкой нормы для соответствующих строк §5.

S3 дополнительно меняет `backend/tests/spatial_pack/test_pack_codec.py`, `fixtures/retention-root.tlv`, `fixtures/retention-shard.tlv` в том же tests/spatial_pack. Пересоздать fixtures целевым encoder, не добавлять old reader; проверить `python -m unittest tests.spatial_pack.test_pack_codec tests.spatial_pack.test_bounded_decode tests.spatial_pack.test_manifest_pin_retention`. Diff binary fixtures предъявляется с decoded roster/payload сравнением, не только размером bytes.

S4 River exact files: `backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py`, `backend/tests/geo1/fine_water/test_river_diagnostics.py`, `backend/tests/test_hydrology_fine_river_planning.py`, `backend/tests/planning/providers/test_planning_service.py`, `backend/tests/geo1/procedural_refinement/test_proposals.py`, `backend/tests/geo1/procedural_refinement/river_route_golden.json`; S2 уже поставляет riverRouting.py и surfaceManifest.py. Команды `python -m unittest tests.geo1.fine_water.test_river_diagnostics tests.geo1.fine_water.test_routing tests.test_hydrology_fine_river_planning tests.planning.providers.test_planning_service`; golden команды River D1 §8 отдельно.

**Выбранный direct cutover callback:** в `assemble_water_bodies`, `materialize_water`, `finalize_water`, `unresolved_water` и водных job callbacks keyword `emit: Callable[[DiagnosticCarrier], None]` обязателен, без default/None. Другие параметры/результаты неизменны. Fact construction чистое, передача в callback ровно одна; delivery решает владелец invocation. Direct no-callback вызов больше не контракт; это изменение диагностической сигнатуры, не вычислений. Все repo callers переводятся одновременно: `waterBodyAssembler.py`, `water/planning/waterBodyJob.py`, `water/planning/waterAssemblyResult.py`, `water/planning/fine/execution.py`, `hydrologyGeneratorService.py`, `water/waterMaterialize.py` относительно hydrology; тесты `backend/tests/geo1/fine_water/test_kind_mismatch.py`, `backend/tests/geo1/integration/test_activation.py`, `backend/tests/test_hydrology_water_resolver.py`, `backend/tests/test_hydrology_hy12_rivers.py`. Поиск `rg -l 'assemble_water_bodies\(|materialize_water\(|finalize_water\(' backend --glob '*.py'` подтверждает этот набор 2026-11-07. Тесты передают collector и при необходимости явно вызывают report helper; fake optional compatibility branch не остаётся. Runtime apply владеет collector/report; planning job и fine execution уже владеют collector и не включают logging. S4 включает новые явные collector args в этих тестах. Дополнительная команда `python -m unittest tests.geo1.integration.test_activation tests.test_hydrology_hy12_rivers tests.geo1.fine_water.test_kind_mismatch tests.test_hydrology_water_resolver`.

### 7.1 Выбранный контракт обязательных границ (дополняет §6)

Для приёмки выбран следующий вариант, закрывающий обнаруженные в §6 пробелы Water publication refusal и локального reporting.

**Publication refusal.** Расширить существующий `PlanBuildFailure.__init__(issues: tuple[FieldPathError[Any], ...], *, diagnostics: tuple[DiagnosticCarrier, ...] = ())` в planningService.py. Оба свойства immutable, требуется хотя бы один непустой набор. `issues` сохраняет нынешнюю строгую валидацию; `diagnostics` проходит require_concrete_diagnostic, validate_immutable, допускает только ERROR disposition. Не преобразовывать operational fact в field issue. Прежний positional constructor и его поведение сохраняются; это не legacy wrapper, а два различимых вида причины существующего отказа. Исключение не сериализуется; сериализуются concrete carriers штатным manifest.

Water fine execution/admit_result создают `PlanBuildFailure((), diagnostics=tuple(error_carriers))`; отказ до publication остаётся. PlanningService существующий passthrough не меняет тип. Четыре field-only catches в `app/application/worldData/generators/terrain/designedWater/preparation/{designPreparation.py,coastlineWaterSourceAdapter.py,coastlineConstraintPreparer.py}` и `app/application/worldData/generators/hydrology/boundaries/boundaryPlanner.py` обязаны перед старой обработкой выполнить `if failure.diagnostics: raise`: operational refusal распространяется без потери причины, field-only ветвь остаётся прежней. Эти файлы включены в S4 вместе с water/planning/fine/{execution.py,publication.py}. Тесты: расширить tests/planning/providers/test_planning_service.py, tests/planning/providers/test_diagnostics.py и новый test_water_diagnostics.py: обе причины, forged carrier, ERROR-only, original cause сохранён, никакого успешного envelope/cache entry при отказе.

**Runtime reporting.** Новый локальный `WaterDiagnosticReport` в dataModel/hydrology/waterDiagnostics.py: strict/frozen, обязательные `blocking: tuple[WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic,...]`, `continuations: tuple[WaterPlanningDiagnostic,...]`, `notices: tuple[WaterWorldOceanDiagnostic,...]`; validators проверяют disposition по каждому полю. Это доменный результат одного вызова, не новый общий collector. Конкретный application helper в waterDiagnostics.py `report_water_diagnostics(ctx: ResolveContext, facts: tuple[WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic,...]) -> WaterDiagnosticReport` отделяет накопление от delivery. В collect_only он ничего не emit-ит; validate_only сам по себе не меняет disposition; field mismatch продолжает существующий field reporting. Никакого импорта Hydrology в ResolveReport/ImportIssue.

Точный выбор на приёмку: operational ERROR на runtime/import границе больше не маскируется field issue. `HydrologyGeneratorService.apply` сохраняет возврат результата во всех прежних режимах, без нового raise. В `app/application/worldData/generators/hydrology/types.py::HydrologyResult` добавить `water_diagnostics: WaterDiagnosticReport` с default_factory пустого отчёта. На один apply создаётся локальный список concrete carriers; WATER_PLACEMENT_REQUIRED добавляется туда, assemble_water_bodies вызывается с emit=append; после завершения список единожды классифицируется и записывается в result.water_diagnostics. Результат живёт вместе с HydrologyResult; collect_only не теряет факты и не меняет право записи. Runtime log-and-continue сохраняется, validate_only/collect_only не добавляют raise. Существующие field issues продолжают ctx/report policy. Только уже существующие publication rejection boundaries используют PlanBuildFailure.diagnostics.

Для delivery reuse существующий logger из jsonValidation.resolve через доменные методы waterDiagnostics, как прежний log_issues; уровень WARNING для прежнего noncallback log-and-continue, даже когда fact disposition ERROR. Событие содержит сериализованный concrete carrier, source/world correlation из fact; не весь input/ctx и не traceback заново. Exact field whitelist выводится из validated DTO serialization; ручной dict сборки факта нет. Ошибка DTO не подавляется; sink failure best-effort не меняет outcome. Отдельный новый logging route не вводится этим D1. На типизированный report переводятся hydrologyGeneratorService.apply и его Water helpers атомарно; обязательная дополнительная правка types.py включена в S4. Критерий — прежние conditions и body/cell/UID результаты равны, report содержит concrete facts, independent checks не обрываются раньше. AssembledWater и FineWaterResult не получают вторую копию diagnostics: planning callers уже имеют callback collector.

S5 здесь становится частью единого S4 cutover, не последующим implementation gate. Дополнительные файлы S4: hydrologyGeneratorService.py, waterDiagnostics.py, water/planning/fine/execution.py, water/planning/fine/publication.py, planningService.py и четыре catches выше. Новые тесты в test_water_diagnostics.py проверяют callback/no callback, runtime/validate_only/collect_only, sink failure, следующий независимый компонент и публикацию. Команда `python -m unittest tests.geo1.fine_water.test_water_diagnostics tests.planning.providers.test_diagnostics tests.planning.providers.test_planning_service tests.test_hydrology_water_resolver`.

Уточнение report admission: exact PlanDiagnostic разрешён только с exact WaterKindMismatchIssue; произвольный field fact запрещён. Классификация не теряет общий порядок: добавить обязательное `ordered: tuple[WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic,...]`, а три disposition tuples должны равняться стабильным фильтрам ordered. Пустой отчёт создаётся явным constructor со всеми четырьмя пустыми tuples. Для emission использовать ordered. В PlanBuildFailure.diagnostics на водной границе передавать только ERROR из исходной последовательности в порядке появления. FALLBACK и NOTICE в этом исключении недопустимы. Для этой формы отказа .issues пусто.

Logging signature: `emit_water_diagnostic(diagnostic: WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic) -> None` в существующем application waterDiagnostics.py. Единственный structured extra key — `diagnostic`, значение `type(diagnostic).model_validate(diagnostic, strict=True).model_dump(mode="json", serialize_as_any=False)`; fixed message `water diagnostic`, WARNING по прежней log_issues delivery, без нового activity/code string контракта. Logger reuse `logger`, уже экспортируемый jsonValidation.resolve; никакого нового route. Это единственное создание stdlib extra mapping на границе, не ручная сборка diagnostic payload. `report_water_diagnostics` вызывает emit только при not validate_only and not collect_only. DTO admission выполняется до best-effort sink.

На приёмку предлагаются: (1) facts/carriers §2–3; (2) ID диапазон и exact source roster §4; (3) порядок S1–S3 → единый S4 включая delivery из §7.1; (4) расширение PlanBuildFailure для существующего publication refusal и typed result report без нового raise в apply; (5) обязательный callback direct cutover §7.0. Отказ от legacy и сохранение вычислений/fallback уже приняты, повторного выбора не требуют.

D1 не скрывает границу согласования: §7.1 предлагает конкретное расширение существующего publication refusal и runtime reporting; нового исключения из apply нет. Source/Pack целиком не закрывается одним S1. После принятия каждый шаг предъявляет свой baseline delta; errors старых runtime producers не подавлять.

Обязательные сценарии: puddle продолжает следующий компонент; для сухого authored A и корректного B проверить отдельно (1) материализацию B и один WaterCannotHold для A с точными source_uid/effective_level, (2) возврат HydrologyResult из apply, в том числе при collect_only, (3) отказ Fine Water с тем же содержимым причины и отсутствие успешной ревизии или записи в кеш; spill без union и spill с последующим union различают уровни; superseded хранит оба уровня; unresolved возвращает прежний empty result; no-ocean не вводит abort; world-ocean остаётся NOTICE; mismatch сохраняет concrete identity; обязательный callback выдаёт один факт, пропуск callback отвергается сигнатурой; mixed Water/River сохраняет порядок/дедупликацию; mode/validate_only/collect_only не меняют численные результаты или fallback; повторный encode/decode и повтор операции детерминированы, случайных failure IDs нет.

## Результат D2-0 и S1

D2-0 перенёс в ТЗ условие WATER_CANNOT_HOLD по authored seeds, уровень сообщения, отказ Fine Water и схему доменных фактов для последующих шагов. S1 реализовал generic PlanDiagnostic, строгий приём concrete carrier в PlanBuildResult/PlanEnvelope и соответствующую аннотацию output_fingerprint. Провайдер проверяет конкретный тип повторно. Формула fingerprint сохранена.

Уточнение карты S1 по фактическому caller: boundedCanonicalDecode.py проверял точное совпадение ожидаемого и зарегистрированного типа до Pydantic admission, поэтому отклонял прежний mismatch. Для carrier он теперь использует тот же предикат конкретного класса, а для IssueT записи 105 — его declared default. Входящий ID по-прежнему ищется в manifest до проверки типа. Проверены bounded round-trip operational carrier, отказ для постороннего зарегистрированного record и штатная публикация mismatch с декодированием в отдельном процессе.

Baseline Planning contracts: 14 тестов, 1 error на прежнем конструкторе FieldPathError. После миграции тестовой причины на WaterKindMismatchIssue: 17 OK. Ещё 2 OK в tests.geo1.fine_water.test_kind_mismatch. Общий source_schema / providers diagnostics / canonical_codec — 24 теста, 11 errors и 5 failures до и после. Pyright по четырём затронутым production-модулям — 0 ошибок.

Открытый вопрос приёмки source из River D1 §8–9. В двух отдельных процессах sourceSchema._snapshot() дал разные shape-хеши для ID 60008, начинающиеся с 2f2dbaae и 2b043fc9. Существующий алгоритм хеширует repr аннотации, которая теперь содержит PlainValidator с адресом функции. Для S3 предлагается канонически представлять validator по его типу и module/qualname функции, сохранив остальные структурные проверки. Приёмка требует одинакового shape/alias lock в двух свежих процессах и обнаружения подмены validator. Изменение scope вычисления lock предъявляется владельцу Spatial/source перед регистрацией схемы. Tests S1 подтверждают перенос факта и wire round-trip, полный Planning/source P1 остаётся открыт.

### Независимое ревью 2026-11-07

**D2-0 принят как изменение ТЗ. S1 — REVISE. Переход к S2 отложен до закрытия P1.** Проверен checkout `78ab89bd` относительно `9625139a`. Условие WATER_CANNOT_HOLD в materializer проверяет authored-источник и отсутствие seed-клетки ниже `resolved.levels[i]`. По ТЗ runtime пишет WARNING, materializer продолжает обработку, Fine Water отклоняет публикацию при disposition ERROR. Текущий legacy-конструктор FieldPathError прерывает доставку. Сквозной сценарий «сухой A + корректный B» остаётся в приёмке S4.

- **P1, S1.** В [planDiagnostic.py, строка 38](../../backend/app/dataModel/planning/diagnostics/planDiagnostic.py) проверка ищет Any только в непосредственных аргументах модели факта. Для generic-модели `Fact[T]` с полем `leaf: T` создать именованный carrier `Loose(PlanDiagnostic[Fact[tuple[Any, ...]]])` и передать `leaf=(42,)`. По §4 River D1 admission должен отвергнуть carrier. Фактически PlanBuildResult его принимает, encoder записывает, а bounded decoder при зарегистрированных типах возвращает `wrong canonical field type or tag`.
- **P2, S3.** В [sourceSchema.py, строка 185](../../backend/app/application/worldData/generators/hydrology/encoding/sourceSchema.py) в shape входит repr аннотации diagnostics с адресом функции PlainValidator. Два свежих процесса дали для ID 60008 префиксы `e1bd7b74` и `050196a2` при ожидаемом стабильном хеше. В snapshot также исчез alias PathSegment относительно базы. Для опубликованного Fine Water mismatch на базе и HEAD совпали SHA-256 canonical bytes (`435da91f…`) и output_fingerprint (`4835dc0e…`). При перестановке причин fingerprint изменился на `d3525328…`.

Planning contracts + Fine Water mismatch дали 19/19 OK, Pyright — 0 ошибок. В группе source_schema / providers diagnostics / canonical_codec на обеих ревизиях 24 теста, 11 errors и 5 failures. Совпали имена тестов и причины падений, включая прежний FieldPathError и closure drift. Для допустимых carrier подтверждены тип, поля, disposition, порядок и codec round-trip. Подтверждён отказ для raw dict, PlanDiagnostic[Any], незакрытого generic carrier, подделанного вложенного факта, неизвестного ID и зарегистрированного record недопустимого типа.

**Исправление P1 после ревью.** Контрпример `LeafFact[tuple[Any, ...]]` воспроизведён на PlanBuildResult и PlanEnvelope. Общая для Planning и bounded reader проверка теперь рекурсивно обходит аргументы типов. Оба контейнера отклоняют этот carrier и принимают `LeafFact[tuple[int, ...]]`. Даже при регистрации loose carrier в тестовом manifest bounded decoder отклоняет класс при чтении заголовка записи.

После исправления Planning contracts + Fine Water mismatch — **20/20 OK**, Pyright по четырём production-модулям S1 — **0 ошибок**. Группа source_schema / providers diagnostics / canonical_codec — 24 теста, 11 errors, 5 failures. Исправление P1 предъявлено на повторную приёмку S1. P2 относится к воспроизводимости source shape в S3.

### Повторное независимое ревью S1, 2026-11-07

**REVISE на `f7c5c8b9` относительно `78ab89bd`.** Прямой `LeafFact[tuple[Any, ...]]` теперь отклоняется на обеих границах Planning и в bounded decoder. P1 остаётся воспроизводимым через именованный alias.

- **P1, S1.** В [planDiagnostic.py, строка 34](../../backend/app/dataModel/planning/diagnostics/planDiagnostic.py) вызов `get_args` для `type LooseAlias = tuple[Any, ...]` возвращает пустой кортеж. Объявить именованный carrier для `LeafFact[LooseAlias]` и передать `leaf=(42,)`. По §4 admission должен отклонить этот carrier. Фактически PlanBuildResult и PlanEnvelope его принимают. При полном тестовом manifest bounded round-trip принятого PlanBuildResult завершается `CanonicalEncodingError: wrong canonical field type or tag`. Контрольный `type IntAlias = tuple[int, ...]` проходит тот же round-trip. Bugbot также воспроизвёл пропуск Any в списке параметров `Callable[[Any], int]`.
- **P2, S3.** Два свежих процесса снова дали разные префиксы shape ID 60008, `5370271c` и `ecbe476a`. Изменения вычисления fingerprint, codec и schema locks в diff исправления отсутствуют.

Planning contracts + Fine Water mismatch — 20/20 OK. Pyright — 0 ошибок. В смежной группе 24 теста, 11 errors и 5 failures, имена падающих тестов и причины совпали с предыдущим прогоном, сверенным с базой. D2-0 остаётся принятым, сухой A + корректный B остаётся сценарием S4.

Следующий шаг — закрыть P1 для alias и составных аргументов, закрепив отказ на обеих границах Planning и в bounded decoder с положительным контролем для конкретного alias. Переход к S2 отложен.

**Исправление по повторному ревью.** Регрессия воспроизвела приём LooseAliasDiagnostic и LooseCallableDiagnostic до правки. Общий предикат теперь раскрывает именованные type aliases и обходит список параметров Callable. Для обоих контрпримеров PlanBuildResult и PlanEnvelope отклоняют экземпляр, bounded decoder отклоняет зарегистрированный тип при чтении заголовка. Контрольный IntAlias проходит обе границы Planning и bounded round-trip. Профиль Planning contracts + Fine Water mismatch дал 21/21 OK, Pyright по четырём production-файлам S1 дал 0 ошибок. Смежный набор дал 24 теста, 11 errors и 5 failures. S1 предъявлен на повторную приёмку. Вопрос стабильности source shape остаётся в S3.

#### Проверка исправления на ffc5d01f относительно f7c5c8b9

**S1 — REVISE.** Оба исходных контрпримера закрыты. Начало S2 отложено до исправления чтения конкретного `Box[int]`. Дефект decoder воспроизводится и на базе. До записи отчёта рабочее дерево было чистым.

Для каждого аргумента создан именованный carrier `D(PlanDiagnostic[LeafFact[arg]])`. PlanBuildResult и PlanEnvelope проверялись отдельно. Для bounded round-trip зарегистрированы четыре типа с ID 1–4 по порядку — PlanBuildResult[int], D, LeafFact[arg], PlanDiagnosticDisposition. Для проверки отказа на заголовке использованы валидные bytes положительного контроля с теми же ID и manifest проверяемого carrier. Наблюдение за входом в `_Reader.record` различает отказ при проверке заголовка и отказ внутри leaf.

| Аргумент LeafFact | PlanBuildResult | PlanEnvelope | Bounded decoder |
|---|---|---|---|
| `LooseAlias = tuple[Any, ...]` | отказ | отказ | отказ на заголовке D |
| `Callable[[Any], int]` | отказ | отказ | отказ на заголовке D |
| `IntAlias = tuple[int, ...]` | принят | принят | round-trip OK |
| `Box[Any]`, где `type Box[T] = tuple[T, ...]` | отказ | отказ | отказ на заголовке D |
| `Box[int]` | принят | принят | отказ на элементе leaf |
| `type SimpleChain = IntAlias` | принят | принят | round-trip OK |
| `type Chain[T] = Box[T]`, затем `type ChainInt = Chain[int]` | принят | принят | отказ на элементе leaf |
| `type ChainLoose = Chain[Any]` | отказ | отказ | отказ на заголовке D |

На отрицательных пробах зарегистрирован вход только в корневой record, затем `unexpected canonical record` на строке 167. На базе оба исходных carrier принимались обеими границами Planning, а reader входил в D и LeafFact. На положительных пробах проверены точные классы D и LeafFact, значение `(42,)` и disposition ERROR после повторной строгой валидации обоих контейнеров и bounded round-trip результата.

**P1, S1 — подстановка аргумента generic alias в bounded decoder.** Минимальный пример — `type Box[T] = tuple[T, ...]`, именованный D с `LeafFact[Box[int]](leaf=(42,))`, disposition ERROR внутри PlanBuildResult[int]. Ожидается чтение результата, записанного encoder с полным manifest. На обеих ревизиях encode проходит, а decode_bounded выдаёт `CanonicalEncodingError: wrong canonical field type or tag`. В [boundedCanonicalDecode.py, строка 35](../../backend/app/application/encoding/boundedCanonicalDecode.py) при раскрытии Box[int] остаётся `tuple[T, ...]`. При чтении элемента на строке 133 контекст подстановки T = int уже потерян.

Профильные тесты — 21/21 OK. Pyright — 0 ошибок. На обеих ревизиях в смежном наборе 24 теста, 11 errors и 5 failures. Сопоставлены все 16 записей по полному имени теста и subtest и по конечному исключению с сообщением, расхождений нет. P2 для S3 подтверждён отдельно — два свежих процесса дали префиксы shape ID 60008 `3955c572` и `4ef79728`.

Следующий шаг — сохранить подстановку T = int при чтении вложенной коллекции и закрепить round-trip `Box[int]` и цепочки generic alias в bounded decoder.

**Исправление по результатам проверки.** До правки регрессия воспроизвела оба отказа чтения: для `Box[int]` и для `ChainInt = Chain[int]`. При раскрытии alias bounded decoder теперь специализирует составную аннотацию в области действия её параметров. При последующем чтении элемента кортежа проверяется конкретный тип `int`.

Оба случая проходят encode/decode с проверкой точных классов carrier и fact, значения и disposition. Контроль `Chain[Any]` подтверждает отказ на обеих границах Planning и на заголовке зарегистрированного carrier в bounded decoder. Профильные наборы дали 21/21 OK с расширенными subtests, Pyright по четырём production-файлам S1 — 0 ошибок. В смежной группе из 24 тестов осталось 11 errors и 5 failures. Исправление предъявлено на повторную приёмку S1. Вопрос воспроизводимости shape ID 60008 остаётся в S3.

#### Независимая приёмка S1 после исправления bounded decoder

**Статус по решению пользователя: приёмка не пройдена.** Ниже сохранён технический вердикт независимого ревью по P1. Переход к S2 приостановлен до уточнения замечания пользователя.

**ACCEPT. P1 закрыт, S2 можно начинать.** Сравнение выполнено между базой `ffc5d01f` и рабочим diff поверх неё. Один и тот же независимый тест на базе воспроизвёл `wrong canonical field type or tag` для `Box[int]` и цепочки `ChainInt = Chain[int]`. С исправлением обе схемы прошли bounded round-trip. Для них, `IntAlias` и простой цепочки alias после повторной строгой валидации PlanBuildResult и PlanEnvelope и после декодирования результата сохранены точные классы carrier и fact, значение `(42,)` и disposition ERROR.

Каждый из четырёх аргументов — `LooseAlias = tuple[Any, ...]`, `Callable[[Any], int]`, `Box[Any]` и цепочка до `Chain[Any]` — независимо отвергнут PlanBuildResult и PlanEnvelope. При чтении с зарегистрированным carrier трасса bounded decoder содержит только корневой record PlanBuildResult. Ошибка `unexpected canonical record` возникает на заголовке carrier до чтения полей carrier и leaf. Дополнительная проверка с двумя переставленными параметрами (`Swap[A,B] = Pair[B,A]`, `Pair[A,B] = tuple[A,tuple[B,...]]`) сохранила значение `('x',(42,))` для `Swap[int,str]`. Подстановка строки `'42'` вместо вложенного int на wire была отклонена.

Профильный набор — 21/21 OK. Pyright по четырём модулям — 0 ошибок и 0 предупреждений. В смежном наборе 24 теста, 11 errors и 5 failures. Для всех 16 записей полные имена тестов и subtest, конечные исключения и сообщения совпали с базой. Отдельный P2 для S3 остаётся открытым — shape ID 60008 в двух свежих процессах дал префиксы `960c23a4` и `65b09d9c`. Сценарий сухого A и корректного B остаётся в приёмке S4.

## S2 — реализация на приёмку

Повторяемая проверка разделения манифеста находится в `backend/tests/planning/encoding/comparison/`. Из backend запустить `.\.venv\Scripts\python -m unittest discover -s tests/planning/encoding/comparison -t . -v`. Модули test_domain_bindings, test_manifest_assembly и test_wire_compatibility независимо проверяют декларации каждого владельца, глобальную сборку, байты и fingerprint Water/River. Эталонные ID, полные имена типов, kind и wire-образцы взяты из рабочего манифеста после S2 до его разбиения. При изменении контракта обновлять соответствующий эталон после объяснения дельты.

**Отдельный рефакторинг деклараций после S2, выполнен.** [surfaceManifest.py](../../backend/app/application/worldData/planning/encoding/surfaceManifest.py) теперь собирает 18 явных наборов привязок в порядке числовых ID. Регистрации Water/River принадлежат [Hydrology](../../backend/app/dataModel/hydrology/encoding/surfaceBindings.py). Для последующих шагов, где карта указывает на surfaceManifest.py как место добавления типа, выбирать декларацию владельца. Глобальную уникальность ID и классов проверяет существующий CanonicalSchemaManifest.

Сравнение с рабочим деревом после S2 охватило все 343 записи в исходном порядке: ID равны, python_type и kind идентичны по объекту. Для WaterLevelSpillDiagnostic и RiverPlanDiagnostic полностью совпали canonical bytes и output_fingerprint. Профильные тесты 34/34, Pyright по сборщику и 18 модулям деклараций — 0 ошибок и предупреждений. Изменение source/Pack lock относится к S3.

Пользователь разрешил начать S2 после обсуждения приёмки S1. Реализованы восемь Water facts и их concrete carriers, а также RiverPlanDiagnostic со строгой повторной проверкой RiverRouteDiagnostic. Surface manifest получил ID 325–336 и 338–344. Для runtime-only WaterPlacementRequired и его carrier номера 337/345 зарезервированы.

ResolvedWaterLevels.spills хранит факты в порядке источников. На расчёте с физическим объединением A и B тест получил requested levels 20 и 5, spill-limited levels 2 и 2, общую итоговую высоту 8. Отдельно проверены одиночный перелив 10 → 3 и отсутствие spill при удержании запрошенного уровня.

Проверки S2, Planning и mismatch — **34 OK**. River carrier прочитан bounded decoder в свежем процессе, отсутствие binding 328 проверено отдельно. Pyright по четырём production-файлам S2 — 0 ошибок и предупреждений. Сравнимый набор resolver/routing/canonical_codec до изменений — 31 тест и 17 errors, после — 33 теста и те же 17 errors. Совпали идентификаторы и конечные сообщения всех падений. S3 остаётся следующим срезом со своим открытым P2 для shape 60008. Переключение producer и сценарий сухого A с корректным B относятся к S4.

## Независимая приёмка S2

**REVISE. S3 пока начинать нельзя.** Проверен HEAD `22ddd5a1875d2f7307404c34a57ed8e9cb1f4540` относительно S1 `3b104fddf7255f385ea7cb67b9ebc92b4a1941e5`. До записи отчёта индекс и рабочее дерево были чистыми, включая проверку `git status --short --untracked-files=all`. Все новые файлы деклараций, тестов и fixtures находятся в коммите.

**P1 — River допускает невалидный requested_mouth до сериализации.** [riverRouting.py, строка 47](../../backend/app/dataModel/hydrology/riverRouting.py) принимает экземпляр HydrologyMouth. [declaredRiver.py, строка 21](../../backend/app/dataModel/hydrology/declaredRiver.py) оставляет для него стандартную политику повторной валидации экземпляров. Минимальное воспроизведение на штатных типах:

```python
mouth = HydrologyMouth(x=1, y=2)
fact = RiverRouteDiagnostic(world_uid="w", object_uid="r", object_type=Connection.RIVER,
    requested_mouth=mouth, code=Code.INVALID_SOURCE, reason=Failure.MISSING_GEOMETRY)
bad = fact.model_copy(update={"requested_mouth": mouth.model_copy(update={"x": "bad"})})
carrier = RiverPlanDiagnostic(issue=bad, disposition=D.ERROR)
PlanBuildResult[int](payload=1, diagnostics=(carrier,))
encode(carrier, SURFACE_MANIFEST)
```

Здесь Connection, Code, Failure и D — HydrologyConnectionType, RiverRoutingCode, RiverRoutingFailure и PlanDiagnosticDisposition соответственно. Ожидался отказ при приёме подделанного факта в RiverPlanDiagnostic. Фактически carrier и PlanBuildResult сохранили строку в x. Первым отказал encoder с CanonicalEncodingError для HydrologyMouth.x (int_type). То же воспроизведено с `HydrologyMouth.model_construct(x="bad", y=2)`. С исходным mouth те же bytes проходят bounded round-trip.

**Water.** Все восемь facts и соответствующие concrete carriers проверены по §2–3. Пропуск каждого обязательного поля, лишнее поле, строка вместо enum, bool, строка и дробное число вместо целого отклоняются. Проверены ограничения puddle, spill, superseded и world ocean, включая допустимое превышение water_cells над world_cells. Для каждого carrier проверены disposition и повторная валидация поддельного code через model_construct/model_copy, в том числе на границе PlanBuildResult. Для семи сериализуемых carriers прошёл bounded round-trip. Mismatch использует прежние точные классы и ID 105/323/324. Placement fact и carrier отсутствуют в surface manifest.

**Spill.** Независимый прогон water_sources → depression_tree/resolve_water_levels на обеих ревизиях дал одинаковые порядок, declared_levels, levels, parents и unions. При передаче B, A источники упорядочились A, B. Из requested 20 и 5 получены два spill_limited_level по 2 и конечные levels (8, 8). У обоих parent UID `942b965c-6c71-5adf-a447-1493f91de0d0`, у union member_uids ('A','B'), parent_system_uid=None. Одиночный authored spill дал 10 → 3. При удержании 5 spill отсутствует. На том же одиночном входе с authored=False уровень остался 3, spills пуст. Факты формируются по own_levels, в порядке sources. Сухой A + корректный B остаётся критерием S4.

**River.** Проверены все 84 сочетания шести code и четырнадцати reason с правилом эквивалентности INVALID_CONNECTION_TYPE, а для допустимых пар — все disposition. REDIRECTED требует receiver UID, kind и cell по отдельности, принимает receiver_level=None и только FALLBACK. Пустая rejected_connection_type сохраняется для INVALID_CONNECTION_TYPE. Подделка непосредственных полей факта отклоняется. Свежий Python-процесс со штатным manifest восстановил carrier через decode_bounded и вернул те же bytes; manifest без ID 328 отклонил исходные bytes.

**Манифест.** Для независимого эталона загрузили монолитную декларацию из `git show 3b104fdd:backend/app/application/worldData/planning/encoding/surfaceManifest.py` в тот же интерпретатор и дополнили её 19 привязками по §4 Water и §5 River. Ровно 324 прежние строки сохранились; добавлены только ID 325–336 и 338–344, 337/345 свободны. Все 343 строки реконструированного монолита и сборки из 18 деклараций совпали по позиции, ID, идентичности объекта Python-класса и kind. Дополнительно прошли сравнения с TSV и wire fixtures, по записи автора снятыми с рабочего монолита S2 перед разбиением; отдельной промежуточной ревизии в этом диапазоне нет. Для обеих сборок совпали полные bytes water.hex / river.hex и output_fingerprint: WaterLevelSpillDiagnostic `abf5c963cb2260752c8afe7b193bf7630fc9672bccd7329342383d5beb102c61`, RiverPlanDiagnostic `42fcbf2ba7d6a8e16bab25561c9356c53870c1d90528ad993e7d4bdef3550617`. Все 13 привязок Spatial совпали с базой по ID, точному классу и kind. Wire-эталоны покрывают только два объекта Water/River.

**Прогоны.** Профильный набор 34/34 OK, comparison 4/4 OK, Pyright по четырём указанным модулям и 18 surfaceBindings.py — 0 ошибок, 0 предупреждений. Расширенный набор: на базе 31 тест и 17 errors, на HEAD 33 теста и 17 errors. Совпали полные имена всех 17 падающих тестов и конечное исключение каждого, `TypeError: FieldPathError requires a named concrete domain subclass`.

Следующий шаг — закрыть P1 на границе RiverRouteDiagnostic/RiverPlanDiagnostic и закрепить обе подделки requested_mouth регрессией с положительным bounded round-trip. Известный P2 по воспроизводимости shape ID 60008 остаётся за S3.

**Исправление P1 предъявлено на повторную приёмку S2.** До правки регрессия воспроизвела приём строки в координате вложенного requested_mouth. При построении или повторной валидации RiverRouteDiagnostic поля устья теперь проходят строгую схему HydrologyMouth. Регрессия проверяет подделки через model_copy и model_construct, включая числовую строку, на границах RiverPlanDiagnostic и PlanBuildResult. Валидное устье (1, 2) проходит bounded round-trip с побайтным совпадением после повторного encode.

Профильный набор — 35/35 OK, comparison — 4/4 OK, Pyright — 0 ошибок и предупреждений. В расширенном наборе 33 теста и 17 ошибок с прежним TypeError базового FieldPathError.

### Повторная независимая приёмка S2

**ACCEPT. P1 закрыт, S3 можно начинать.** Проверена правка `dc7d1d75` относительно базы предыдущего ревью `22ddd5a1`. На старте правка находилась в рабочем diff поверх `fd440659` (план, riverRouting.py и test_river_diagnostics.py); untracked-файлов не было. Во время проверки этот diff вошёл в `dc7d1d75`. Перед записью вердикта рабочее дерево было чистым.

Независимый прогон подставлял в координату x значения `"bad"`, `"42"`, `True` и `1.5` через model_copy и model_construct. На базе все восемь вариантов принимались. После исправления каждый вариант отклонён на всех четырёх проверенных границах — при построении RiverRouteDiagnostic, при передаче подделанного факта в RiverPlanDiagnostic и при передаче подделанного carrier в PlanBuildResult и PlanEnvelope. Отказ происходит до сериализации.

Положительный bounded round-trip со штатным SURFACE_MANIFEST прошёл для координат (1, 2), ссылки location_uid, координат (-1, 0, 3) и отсутствующего устья. Проверены тип и значение восстановленного устья, равенство carrier и побайтное совпадение повторного encode. Для каждого образца SHA-256 исходных bytes совпал с базой.

Профильный набор — 35/35 OK, comparison — 4/4 OK, Pyright по четырём указанным модулям и 18 surfaceBindings.py — 0 ошибок и предупреждений. Расширенный набор дал на обеих ревизиях 33 теста и 17 errors. Совпали полные имена всех 17 тестов, конечные типы исключений и сообщения. В S3 остаётся P2 по воспроизводимости shape ID 60008. Сухой A + корректный B остаётся критерием S4.

### Независимая приёмка S3

**Исправления после приведённого ниже ревью, на повторную приёмку.** A: подмены `23 → 23.0` и `CanonicalTypeKind.ENUM → "enum"` воспроизведены до правки. Source guard теперь строго валидирует manifest и его entries до сравнения bindings. C: связанный retention-root пересоздан штатным encoder после расчёта descriptor по фактическим shard bytes, новый SHA-256 `4c2545de0281fa43c24f0187001d2edeac0746dd80631a5d53e250e7df0be40f`, размер 7479 байт. Ту же сумму проверяет pin-retention. Обычный root из records() проверяется отдельным golden `bbb839fac75f0c51408421975df58c48530e36f695e3f889873e937ce92acb47`. Исходный shard совпал побайтно. Объединённый прогон A+B+C и comparison дал **55/55 OK**. Pyright по трём production-модулям дал 0 ошибок и предупреждений. В двух свежих процессах shape 60008 равен `ce6afa80c6b82955a432e4f09cc01c44c09c85de19decb2d9b2bd861274c0bae`, SHA-256 представления alias lock равен `a7a995c5350ae46d838c24f1d36aba29e0c20845dc10462c6196626e582920ac`.

**REVISE. S4 начинать нельзя.** A — REVISE по строгой типизации bindings. B — ACCEPT в пределах ответственности Pack. C — REVISE по двум разным root-эталонам. Первым исправить source guard и закрепить оба случая подмены тестами. Затем обновить связанный retention-root целевым encoder и отдельно golden для обычного records(). Повторить общий прогон.

**Состояние ревью.** HEAD `dc7d1d754d3b119dc9afd10ff6ec2b340cbb976c`. Git blob полного `git diff --binary HEAD` до записи этого раздела — `bc0a23bb9e4604e399c33858957d80e7995b559c`, повторная проверка дала тот же hash. Индекс чист, untracked-файлов нет. Восемь изменённых путей: два плана в .cursor/plans (этот и world-generation-plan-dependency-graph.md), три production-модуля из команды Pyright и три tests/spatial_pack/test_{source_schema,storage_schema,pack_codec}.py. Все результаты A/B/C относятся к этому дереву. Исторические контроли выполнены в отдельных распаковках git archive.

**A.** В двух свежих процессах guard прошёл. Полный shape 60008 в каждом — `ce6afa80c6b82955a432e4f09cc01c44c09c85de19decb2d9b2bd861274c0bae`. Совпали целиком обе последовательности пар (имя, определение) и alias lock. Имена по порядку: AlgorithmVersion, Count, EntityUid, FineX, FineXY, FineY, FineZ, InputFingerprint, MaterialKey, OutputFingerprint, PathSegment, PlanContractId, PlanScope, PlanSlot, PositiveCount, SchemaVersion. Добавлены Count, PathSegment, PositiveCount, исключён RevisionHex. В roster добавлены 89, 303–308, 323–336, 338–344, исключены 106–110. У 60008 прежний lock начинался с 4054d88e. Подмена функции PlainValidator в test_replaced_plain_validator_changes_envelope_shape даёт shape drift: 60008. Тесты пропустили семь Water carriers, River и mismatch, проверили вложенные типы и повторное кодирование. Surface-зарегистрированный посторонний факт и WaterPlacementRequiredDiagnostic отклонены. Абстрактных классов по inspect.isabstract в объединённом manifest нет. ID 105 нужен для конкретной пары PlanDiagnostic + WaterKindMismatchIssue.

**P2 · A · sourceSchema.py:285.** Минимальный repro в sourceSchema: взять m = OPEN_WATER_SOURCE_SCHEMA_V1, отдельно для каждого update из ({"type_id": 23.0}, {"kind": "enum"}) собрать entries = (m.entries[0].model_copy(update=update), *m.entries[1:]); под patch.object(s, "OPEN_WATER_SOURCE_SCHEMA_V1", m.model_copy(update={"entries": entries})) вызвать s.require_source_schema_v1(). Ожидался CanonicalEncodingError на границе source. Оба вызова вернули None: tuple equality не различает равные float/int и str/StrEnum. При encode(next(iter(entries[0].python_type)), подменённый_manifest) обе записи отклоняет уже CanonicalCodec.__post_init__ (canonicalCodec.py:32, пути entries.0.type_id и entries.0.kind). На чистом HEAD обе подмены также проходят сравнение bindings, однако весь guard падает позже на closure drift даже для исходной записи. На базе воспроизводится дефект сравнения; полное успешное прохождение подменённого guard наблюдается в S3. Исправление — строгая повторная валидация manifest и записей на входе source guard, как в Pack.

**B.** Pack включает source entries и пять собственных записей: 60001 root, 60002 descriptor, 60003 shard, 60005 ArtifactRef, 60006 ArtifactKind. packSchema.py:87 вызывает source guard, проверяет storage shapes, строгие bindings, имена полей и замыкание. На границе записи проверяются и диагностики root. Изменение root.py:135 сверх карты оправдано: Pydantic реконструирует diagnostics по объявлению поля; DiagnosticCarrier применяет общий контракт сохранения конкретного carrier. У decode_root(encode_root(records()[0]), 1) сохраняются WaterLevelSpillDiagnostic и WaterLevelSpill, а повторное кодирование возвращает те же bytes. test_roster_and_exact_storage_shapes проверяет идентичность обоих классов через assertIs. Прошли отрицательные тесты пропущенной, лишней, подменённой регистрации, равных неправильно типизированных storage bindings, испорченного вложенного поля и переименования shards даже при пересчитанном shape.

Pyright по трём production-файлам дал одну ошибку в sourceSchema.py:262:36: Field[Any].annotation в _snapshot. На чистом HEAD тот же Pyright с тем же Python воспроизвёл её в sourceSchema.py:178:36. Это исходный долг A; новых ошибок в packSchema.py и root.py не обнаружено.

**C.** SHA-256 вычислен по самим байтам. В колонке «старый» указан результат encoder исторической ревизии e145de78, указанной в pin-тесте; fixture внесена в Git коммитом d01cf073. Для связанного root и shard отдельно прочитаны файлы из проверяемого дерева.

| Образец | Старый размер и SHA-256 | Целевой размер и SHA-256 |
|---|---|---|
| root из records(), descriptor содержит 64 символа a и nbytes=100 | 7518 · ef55146133c7271a635a006aa8d3667511d12bfe4bf114e52a74460cc9caadef | 7478 · bbb839fac75f0c51408421975df58c48530e36f695e3f889873e937ce92acb47 |
| retention-root, descriptor содержит SHA-256 shard и nbytes=1913 | 7519 · 198cc08ac48db7127b9b2f7ae0108fdf32d4fdf7684842304e416a3c3a0dea92 | 7479 · 4c2545de0281fa43c24f0187001d2edeac0746dd80631a5d53e250e7df0be40f |
| shard | 1913 · efc45c2be06b296c3190f3128aa657abda3858d978b2de5448d9eae0f68bb308 | 1913 · efc45c2be06b296c3190f3128aa657abda3858d978b2de5448d9eae0f68bb308 |

Все три старых образца проходят decode → encode байт-в-байт своим reader, все три целевых — текущим. Старый сохранённый shard проходит текущим reader и совпадает с целевым. Старый сохранённый root текущий reader отвергает. Reader e145de78 прочёл тот же файл, восстановил в точности свой связанный records() и вернул исходные 7519 байт.

На уровне полей root дельта между поколениями локализована в diagnostics. Сопоставлены отдельные wire-представления полей records(); остальные десять совпали по контрольным суммам. Между обычным и связанным образцами внутри поколения меняются только content_hash/nbytes descriptor. Старые байты несут PlanDiagnostic (105) → FieldPathError (106) с path=('water', 0), message='spill', code='WATER_LEVEL_SPILL' и пустыми schema_id/reference/runtime_context. Новые — WaterLevelSpillDiagnostic (342) → WaterLevelSpill (334), code=WaterDiagnosticCode.WATER_LEVEL_SPILL (329), source_uid='authored', requested_level=5, spill_limited_level=2. Disposition FALLBACK (111) сохраняется. ID 106 отсутствует в целевом roster.

- **P1 · C · tests/spatial_pack/test_pack_codec.py:53.** Минимальный repro: decode_root(Path('tests/spatial_pack/fixtures/retention-root.tlv').read_bytes(), 1). Ожидался связанный root с concrete spill и побайтовый round-trip; фактически CanonicalEncodingError: unknown or wrong canonical type ID. Пересоздать связанный root после кодирования shard по его фактическим hash и nbytes.
- **P1 · C · tests/spatial_pack/test_pack_codec.py:161 (golden на :156).** Минимальный repro: content_digest(encode_root(records()[0])).hex(). Ожидается ef551461…; фактически bbb839fa… (полные значения выше). Обновить golden обычного root отдельно от retention fixture. Shard уже совпадает.

**Сверка прогона.** 47 тестов source/storage/codec/bounded дали один ERROR в test_retention_fixtures_match_linked_records (root) и один FAIL в test_existing_wire_reconstructed_exactly (HydrologyPackRoot). Comparison 4/4. Отдельный прогон pin-retention вне песочницы 3/3; в песочнице совместный запуск задержался на SQLite-тесте. Итого по тем же 54 тестам — 52 успешных, 1 error, 1 failure, имена и причины совпадают с предыдущим прогоном. В pin-тестах reader возвращает сохранённые root/shard bytes по ссылкам manifest после смены head и GC (test_manifest_pin_retention.py:159–162); декодируется manifest. Читаемость самого retention-root проверяет упавший codec-тест.

### S3 после исправлений A и C

В sourceSchema.py остались две проверки допуска. Декларации типов и пар диагностики вынесены в sourceBindings.py, вычисление фактических сигнатур в sourceShape.py, эталонные значения в sourceLocks.py. Два свежих процесса дали одинаковые 56 сигнатур и 16 alias, включая shape ID 60008 (ce6afa80c6b82955a432e4f09cc01c44c09c85de19decb2d9b2bd861274c0bae). Адресный прогон S3 прошёл 55/55, Pyright по проверенным production-модулям дал 0 errors и 0 warnings. Повторная независимая приёмка A и C остаётся условием входа в S4.
