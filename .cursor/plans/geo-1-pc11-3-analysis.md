# PC-11.3 — анализ request boundary и lifetime inputs

Дата: 2026-10-26. Статус: ANALYZED, реализация не выполнялась.
Проверен checkout `4eccedda`; рабочее дерево перед анализом чистое.
Delivery SoT: `geo-1-designed-water.md`, PC-11.1-B/D/E/F, R2, PC-11.3.
Нормативные требования: `docs/tz_terrain_generation.md` §Surface planning/cache,
`docs/tz_world_pack_storage.md` §Bake modes/Parent light SoT.

## Вывод и входные gates

PC-11.3 — атомарный caller cutover трёх связанных контрактов: единый
capture/prepare owner, обязательные prepared inputs и region-state read
на время операции. Одного переноса функции из passes недостаточно.
Повторно проектировать domain views и StateSnapshotEntry не требуется.

PC-11.2b в delivery SoT отмечен IMPLEMENTED / VERIFIED, ожидает приёмки.
Текущий запрос на анализ следующего шага сам по себе не меняет эту запись.

Есть внешний integration gate: PC-11.1-E и WS-план §7 требуют сначала
WS-0/WS-0A freeze surface/region/climate reads, затем WS-1 и WS-2a до
подключения общего read port одним WS-3 cutover. В checkout WS transition
имеет статус DESIGN, WS-0A — OPEN; каталогов application/worldState и
dataModel/worldState нет. Следовательно, готовность WS read port по этому
checkout не подтверждена. Snapshot runtime при этом не нужен.

Локальные структурные изменения и перенос lifetime через существующий loader
описаны действующим контрактом. Их нельзя выдавать за выполненный WS cutover
или обходить gate созданием собственного CRUD. Полную приёмку зависимой
интеграции нужно сверять с указанными WS prerequisites; расширять PC-11.3
до реализации всего WS-трека оснований нет.

## Подтверждённые разрывы с target

1. **L0 consumer ещё выполняет self-capture.**
   `pack/bake/worldMapBakeOrchestrator.py:91,216`: оба bake метода принимают
   optional surface_bundle; при None вызывают capture/prepare. Конструктор
   содержит planning/capture только для fallback. В bake_tiles surface_ctx
   игнорируется, в bake_tile игнорируется позиционный surface_ctx.
   Working уже обязательный, поэтому fallback может вдобавок сочетать новый
   bundle с working другого preparation. Удалить обе ветки и мёртвые аргументы;
   готовые bundle/working должны поступать от operation boundary.

2. **У entry ещё два места вызова capture.**
   SurfacePlanningEntry уже имеет capture_view/extent_status/prepare_captured.
   Однако L0 и detailed owners вызывают `_capture.capture` напрямую, а
   standalone require_surface_plan_inputs живёт в generator passes
   (`surfaceTerrainContext.py:49`). require_surface_plan_bundle — wrapper,
   production callers у него сейчас отсутствуют. Три map routes используют
   require_surface_plan_inputs. Перенос должен сохранить пару bundle+working,
   а не вернуть routes к bundle-only API с отдельной сборкой views.

3. **Region-state read не имеет lifetime операции.**
   `_materialize_l0_pack`: internal drain вызывается на строке 249,
   state loader — только на 266, после drain и coarse climate. FineChunkRunner
   отдельно читает repository на каждый непустой refine_rects (строка 68).
   Detailed facade вообще не производит общий state mapping.
   Поэтому scene/path/следующий tile могут увидеть разные состояния одной
   операции, а internal drain и L0 заведомо не разделяют один ref.

4. **Optional inputs скрывают пропущенный state read.**
   L0 bake методы, fineTilePrep, TerrainBatch.build_tile_surface_state и
   finePaint ещё принимают None; L0/finePaint подставляют {}.
   LightGridBakeContext.region_state_snapshot имеет default_factory=dict.
   Loader возвращает mutable dict, хотя StateSnapshotEntry уже frozen.
   В новом operation ledger нужен обязательный keyword-only Mapping без
   default, с readonly backing и без доступной mutable ссылки у consumers.
   Existing optional-repo semantics loader вне этого ledger сохраняются.

5. **Extent-only reads строят полные планы.**
   WorldSurfaceMaterializationOrchestrator.plan_bootstrap_tiles:167 вызывает
   require_surface_terrain_context. PackCompletenessClassifier.classify:39
   делает то же при отсутствии ctx. Сам PackTilePlanner.plan уже игнорирует
   surface_ctx. Preview и loading/completeness должны использовать capture
   и discriminator, без prepare/providers/projectors. Classifier получает
   extent_status явно и лишается planning/capture dependencies.

6. **Capture-only diagnostics требуют отдельного внимания.**
   SurfacePlanningEntry.extent_status сейчас только возвращает view.kind.
   Replay capture_diagnostics находится в prepare_captured_bundle:109,
   после planning.prepare. Простая замена prepare на probe потеряет этот
   report boundary. Нужен общий composition-owned reporting путь для capture
   и prepare, с одним ResolveContext, error dedup и NOTICE ровно один раз.
   Нельзя вызывать prepare ради diagnostics либо копировать report алгоритм
   в preview/classifier. Public extent_status(view) остаётся discriminator.

## Caller ledger реализации

Все следующие пути относительно `backend/app/application/worldData/`.

- **Preparation owner:** planning/composition/surfacePlanningEntry.py.
  Operation owners используют capture_view и тот же captured view для
  prepare_captured и authoritative publication guard. Один entry owner
  не означает один глобальный request object или процессный cache inputs.
- **L0 operation producer:** pack/bake/packMaterializationOrchestrator.py,
  `_materialize_l0_pack`. Один readonly state ref после successful prepare,
  до первого domain drain; тот же ref идёт в world-map bake и internal drain.
- **Detailed operation producer:** materialize/
  worldSurfaceMaterializationOrchestrator.py, materialize_pack_detailed.
  Загружает state ref и передаёт в detailed chain до delegation.
- **Standalone operation producers:** `backend/app/api/routes/map.py`, три
  routes refine-from-entry / refine-chunk / schedule-refine. Один prepared
  tuple и один state ref на запрос; entry и optional schedule разделяют refs.
  CLI/direct callers и default factories проверяются общим поиском call sites;
  отдельный самостоятельный drain получает новый mapping, даже при cache HIT.
- **Detailed forwarding:** PackDetailedBakeOrchestrator.bake,
  _bake_in_log_scope, _bake_location_scope, _bake_wilderness_scope, _run,
  _refine_tiles → detailedBakeRefine.refine_detailed_tiles.
- **Entry/drain forwarding:** EntryRefineOrchestrator.refine_from_entry,
  schedule_chunk_refine, drain_persisted → ChunkRefineWorker.drain_queue /
  drain_persisted → FineTerrainRefineOrchestrator.refine_queued_chunk.
- **Fine forwarding:** FineTerrainRefineOrchestrator.refine_scene_volume,
  refine_rect, _refine_rect, refine_queued_chunk, refine_path_corridor,
  _refine_rects / _run_refine_phase → FineChunkRunner.refine_rects →
  fineTilePrep.prepare_fine_tile → TerrainBatch.build_tile_surface_state →
  existing finePaint. Не оставлять обязательность только внутри **kwargs.
- **L0 holder:** WorldMapBakeOrchestrator.bake_tiles/bake_tile →
  LightGridBakeContext.region_state_snapshot → existing LandcoverInputs.
  Mandatory bundle/working/state refs проверяются и в holder caller ledger.
- **DI:** core/container/worldData.py и packs.py, build_pack_read_services,
  PackMaterializationOrchestrator._default_entry_stack. Удалить repo из
  FineChunkRunner/FineTerrainRefineOrchestrator и их factories; acquisition
  dependencies принадлежат operation producers. WorldMapBakeOrchestrator
  лишается planning/capture; read facade получает entry для probe.

Нельзя добавлять state mapping в queue job, process cache или SurfaceWorkingMaps.
drain_climate_fine не получает игнорируемый region-state параметр.
Непустой store-read с нулём rows даёт readonly empty mapping; отсутствие
обязательного источника/ошибка не превращается в успешное {}.

## Точное поведение probe

- Preview NO_EXTENT → existing ValueError, debug route HTTP 422.
- Preview READY → pure planner; допустимый результат [] сохраняется.
- Manifest отсутствует либо tiles пусты → absent до capture/state reads.
- Непустой manifest + NO_EXTENT → partial; READY → обычная классификация.
- Непустой manifest без explicit extent_status → contract error.
- В extent-only ветках prepare/build/projectors/state reads/publication = 0.

Удаление неиспользуемого planner surface_ctx и обновление всех его callers
нужно выполнить с этим probe cutover. Удаление TerrainBatch preview wrapper
как публичного символа остаётся PC-11.4; не переносить его алгоритмы в entry.

## Границы с соседними шагами

PC-11.3 проводит state ref до действующего consumption пути. Временный
finePaint forwarding не должен reload/copy/default подменять ref.
Перевод finePaint на готовый LandcoverInputs, перенос region input owner,
typed fact refs и domain/pack split остаются PC-11.5/11.6a/11.6b.

to_legacy_context внутри ещё не переведённого L0 допустим до PC-11.7;
мёртвый внешний surface_ctx удаляется уже здесь. Legacy symbols не удаляются
массово до их caller ledger. Outline membership/read/render cutover и
TODO(snapshot) остаются PC-11.6b; gameplay reads не получают planning.

UOW, publication guard, parent-light SoT/error, scope и complete-tile skip
сохраняются у существующих owners. Snapshot freshness, history replay,
incremental chunk skip, новые HTTP routes, SQL и DAG в шаг не входят.
Принятая PC-11.2b frozen climate fallback delta 42→12 сохраняется.

## Порядок и проверка

1. Сверить WS freeze/integration prerequisites и принятую PC-11.2b baseline.
2. Перевести composition entry/reporting и extent-only callers вместе с DI.
3. Атомарно перевести L0 signatures и полный state lifetime ledger, включая
   detailed, entry, direct callers, default stacks, holders и fixtures.
4. Проверить все call sites и tests, затем провести отдельную приёмку PC-11.3.
   Это внутренний порядок правок, не предложение принимать сломанную середину.

Обязательные новые cases: один capture/prepare на N tiles; ноль capture из
consumers; один state read на scene+path+internal drain+L0; `is` identity
всех refs; изменение repository между tiles не меняет текущую операцию;
следующая самостоятельная операция получает новый readonly mapping при HIT;
ошибка mutation mapping; отсутствие mandatory input; empty operation без
domain execution не требует state read; probe матрица выше; diagnostics
runtime/validate-only/NOTICE; fresh/stale publication; parent-light error.

Regression suites: planning consumers (включая no_second_truth/revisions),
pack bake modes, detailed C11, parent light refine, fine parallel, WP13 entry,
wilderness region index, region state contract и coarse/fine climate.
Typing: planning valid0 и exact negative diagnostics. Старые tests, которые
сознательно проверяют self-capture либо прежние compatibility imports,
обновить под новый контракт, сохранив numerical assertions.

Проверка анализа: `PYTHONPATH=backend`,
`backend/.venv/Scripts/python.exe -m unittest
tests.planning.consumers.test_no_second_truth
tests.planning.consumers.test_revisions.RevisionTests` — **26 OK**.
Это baseline существующего checkout, не evidence готовности PC-11.3.
Async suites и полный regression run в рамках анализа не запускались.
Production code, delivery statuses, SQL и DAG не изменены.
