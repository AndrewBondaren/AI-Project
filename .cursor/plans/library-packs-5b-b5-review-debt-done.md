# План: техдолг ревью шага B5 (5b) — relief reader/pick cutover — ✅ выполнен

> Все шаги 1–5 закрыты (2026-10-15). Итоги по шагам — в конце файла.

## Контекст

Ревью коммита `d3a6c0a5` — шаг **B5** плана
[`domain-template-libraries-5b-implementation-done.md`](domain-template-libraries-5b-implementation-done.md):
`pick_template` переключён с `WorldReliefTemplateRegistry` на
membership-scoped `Mapping[uid, ReliefTemplate]`, reader —
`TemplateSnapshotLoader.load_relief`, оркестраторы — на `relief_loader`.

Оси ревью: неявные контракты · один класс = одна ответственность ·
класс > 250 строк (запрошенный порог; repo-лимит `class-size-limit` —
300) · хардкоды. Контракт шага соблюдён: UID-order, pure pick, без
подстановки, order-diff задокументирован. Блокеров нет; ниже — дефекты
чистоты и семантические сдвиги, сделанные молча.

Проверки каждого шага: `python -m unittest` из `backend/`.

## Карта находок → шаги

| Находка | Файлы | Шаг |
|---|---|---|
| `_templates_by_world` — кэш membership-снимка без инвалидации; семантика изменилась с «строки библиотеки» на «состав membership», оркестратор — синглтон в `Container`; detailed bake при этом грузит заново каждый раз | `fineTerrainRefineOrchestrator.py:70,306-318`, `packDetailedBakeOrchestrator.py:149-156`, `container.py:562` | 1 |
| Inline-фильтр кандидатов `sorted(templates.items())` + `body.context.value == ctx` — контракт «кандидаты = члены context-а, порядок по uid» существует только как анонимный код | `templatePick.py:90-93` | 2 |
| `pick.template_uid or template.system_name` — dead-fallback: pick всегда возвращает uid или reject; name-семантика в uid-поле ×3 | `ribbonGrade.py:78`, `reliefSidesStamp.py:69`, `detailedGradeFrontPick.py:59` | 2 |
| `templates` тип гуляет: `Mapping` в `pick_template`/`pick_front_grade`, `dict` в `grade_ribbon_segments`/`stamp_*` | `templatePick.py:73`, `detailedGradeFrontPick.py:44`, `ribbonGrade.py:55`, `reliefSidesStamp.py:30,81` | 2 |
| `load_relief()` и `load()` — два независимых `catalog.load` на мир; снимки одного bake не атомарны между собой при конкурентной записи; контракт не зафиксирован | `templateSnapshotLoader.py:70-105,107-119` | 3 |
| `warn_template_invalid_geom`: read path передаёт `template_uid=uid` (path = uid), write path — без (path = system_name); один шаблон → разные диагностические пути | `domainAdapters/relief.py:71` vs `:110` | 3 |
| `load_relief` молча фильтрует `isinstance(body, ReliefTemplate)` — member нужного kind с «чужим» телом исчезнет без диагностики (preparation гарантирует тип → defensive, но silent) | `templateSnapshotLoader.py:117-118` | 3 |
| `PackDetailedBakeOrchestrator` — 343 строки (>250 и >300): scope-dispatch + stages + relief loading + grade persist | `packDetailedBakeOrchestrator.py:99-441` | 4 |
| `FineTerrainRefineOrchestrator` — 284; `PackMaterializationOrchestrator` — 263 | `fineTerrainRefineOrchestrator.py:58-341`, `packMaterializationOrchestrator.py:61-323` | 4 |
| `getattr(spec, "relief_pick_policy", None)` + `isinstance` — поле объявлено на `MountainSpec` (`specs.py:100`), getattr избыточен; pre-existing | `reliefSidesStamp.py:49,60` | 5 |
| `mountain_id` fallback — composite identity `f"{x},{y},{r}"` склеена запятыми в одном месте; хрупкий формат, pre-existing | `reliefSidesStamp.py:50-53` | 5 |

## Вне scope (не долг этого коммита)

- `relief_template_registry` pointer dual-write (`ReliefPackAdapter`,
  `reliefWorldImportService`, `reliefSection`) — запланированное
  удаление в **B6**; сами колонны и legacy API — в **B7**.
- Stale fixtures `relief_template_registry=[...]` в
  `test_detailed_grade_generate.py` (~10 мест) — мёртвые данные после
  cutover, чистка принадлежит B7; отдельный сигнал, не блокирует.
- `self._detailed._defaults` — доступ к приватному полю другого
  оркестратора; pre-existing (`worldSurfaceMaterializationOrchestrator.py:126`).
- `int(decision.h) < 1` — магический порог, pre-existing
  (`detailedGradeFrontPick.py:66`).
- Whitespace-нормализация: файлы переписаны целиком (`git show -w`
  схлопывает 538→1 строку в `worldSurfaceMaterializationOrchestrator.py`,
  215→5 в `reliefSidesStamp.py`, 214→8 в `ribbonGrade.py`, 158→6 в
  `detailedGradeFrontPick.py`) — шумит blame и stat коммита. Процессное
  замечание к автору, не код.

## Шаги

### Шаг 1 — кэш снимка: явный контракт или инвалидация

- **Цель:** убрать молчаливый сдвиг семантики `_templates_by_world` —
  либо зафиксировать инвариант «membership заморожена на жизнь
  оркестратора» (docstring + точка, где это гарантируется), либо
  инвалидировать кэш при attach/detach/записи члена пака мира.
- **ТЗ:** `docs/tz_template_library_packs.md` §5/§7 (availability =
  membership, снимок на границе); `docs/tz_terrain_relief.md` R19/R31.
- **Файлы:** `pack/refine/fineTerrainRefineOrchestrator.py`,
  `pack/bake/packDetailedBakeOrchestrator.py` (без кэша — выровнять
  политику: либо оба кэшируют, либо оба грузят заново),
  `core/container.py` (lifetime синглтона).
- **Контракт:** одно поведение на всех потребителей relief-снимка;
  если кэш остаётся — docstring фиксирует инвариант и точку
  инвалидации.
- **Проверка:** `python -m unittest tests.test_library_packs_5b_relief
  tests.test_detailed_grade_generate`.
- **Done:** поведение задокументировано в коде; attach члена между
  двумя refine либо виден, либо явно невиден по контракту.

### Шаг 2 — явный candidates-контракт и тип `templates`

- **Цель:** контракт «кандидаты = члены context-а, порядок по uid»
  получает имя и одно место; снять dead-fallback'и на `system_name`.
- **ТЗ:** `docs/tz_template_library_packs.md` §5 (ordered candidates
  по UID); `docs/tz_terrain_relief.md` R19/R21/R31.
- **Файлы:** `generators/terrain/relief/pick/templatePick.py` (+ helper
  `candidates_for_context`), потребители `ribbonGrade.py`,
  `reliefSidesStamp.py`, `detailedGradeFrontPick.py`.
- **Контракт:** `candidates_for_context(templates, ctx) -> list[str]`;
  `templates: Mapping[str, ReliefTemplate]` единообразно по цепочке;
  `pick.template_uid` не-optional на выходе успешного pick —
  `or template.system_name` удаляется (или оформляется assert).
- **Проверка:** `python -m unittest tests.test_library_packs_5b_relief
  tests.test_relief_pure tests.test_e6_consumers
  tests.test_relief_mountain_stamp`.
- **Done:** фильтрация/порядок кандидатов живут в одной функции;
  тест `test_round_robin_follows_member_uid_order` проходит через неё.

### Шаг 3 — атомарность снимков и единый warn-path

- **Цель:** зафиксировать контракт неатомарности `load_relief`/`load`
  (или шарить один `EffectiveCatalog` на связанные вызовы); выровнять
  `warn_template_invalid_geom` на единый path-ключ между read/write
  boundary; решить silent `isinstance`-фильтр в `load_relief`.
- **ТЗ:** `docs/tz_template_library_packs.md` §5/§7 (одна диагностика
  на границе); `docs/tz_logging.md` (маршрут диагностики);
  `docs/tz_json_validation.md` (issue paths).
- **Файлы:** `templateSnapshotLoader.py`, `domainAdapters/relief.py`,
  `reliefGeomWarn.py` (сигнатура), `loadReliefTemplatesForWorld.py`.
- **Контракт:** либо `load_relief` принимает/шарит снапшот с `load`
  (один `catalog.load` на bake), либо docstring явно фиксирует
  «снимки независимы»; диагностический path ключа шаблона одинаков
  на обоих входах.
- **Проверка:** `python -m unittest tests.test_library_packs_5b_relief
  tests.test_library_packs_4a tests.test_library_packs_4b`.
- **Done:** контракт написан в docstring; один warn → один path-вид;
  фильтр либо убран (тип гарантирован preparation), либо с диагностикой.

### Шаг 4 — размеры классов (>250)

- **Цель:** сплит по зонам ответственности по `class-size-limit`;
  `PackDetailedBakeOrchestrator` (343) — первым, т.к. уже за
  repo-порогом 300.
- **ТЗ:** `docs/tz_generator_technical_debt.md`; правило
  `class-size-limit` (вынести зону до наполнения).
- **Файлы:** `pack/bake/packDetailedBakeOrchestrator.py` (stages /
  scope-dispatch / grade persist — кандидаты на job/contract),
  `pack/refine/fineTerrainRefineOrchestrator.py` (284: cache + persist),
  `pack/bake/packMaterializationOrchestrator.py` (263: passthrough
  properties).
- **Контракт:** каждый вынесенный job — один seam; facade только
  порядок; без `*Part2`-классов с тем же знанием.
- **Проверка:** `python -m unittest tests.test_detailed_grade_generate
  tests.test_library_packs_5b_relief` + compileall.
- **Done:** тела классов ≤ 250 (или обоснование, почему зона
  неделима, внесено в `docs/tz_generator_technical_debt.md`).

### Шаг 5 — мелочи: getattr и composite identity

- **Цель:** прямой доступ к объявленному полю; формат `mountain_id`
  не расползается.
- **ТЗ:** `docs/tz_terrain_relief.md` R33 (mountain sides stamp).
- **Файлы:** `generators/terrain/mountains/reliefSidesStamp.py`.
- **Контракт:** `spec.relief_pick_policy` напрямую (поле объявлено);
  composite id — именованный формат/функция, а не f-строка в теле.
- **Проверка:** `python -m unittest tests.test_relief_mountain_stamp`.
- **Done:** getattr-обёртка снята; формат id — в одном месте.

## Итоги по шагам (2026-10-15)

1. **Кэш снимка** — удалён `_templates_by_world`; `_relief_templates`
   грузит свежий membership-снимок на refine-job (инвалидации нечем
   зацепиться: нет версии тела, `WriteAction.REPLACE` меняет тело под
   тем же uid). Поведение унифицировано с pack/detailed bake —
   «снимок на операцию». `fineTerrainRefineOrchestrator.py`.
2. **Candidates-контракт** — `candidates_for_context()` в
   `templatePick.py`; `PickResult/RibbonGradeResult/PickedFrontGrade.template_uid`
   → `str` (был `str | None`); dead `or template.system_name` снят ×3;
   `templates: Mapping` по pick-цепочке.
3. **Атомарность + warn-path** — docstring-контракт независимых снимков
   в `TemplateSnapshotLoader`; write-path пробрасывает `template_uid`
   в warn (path = uid на обоих входах; name только на import-границе);
   silent isinstance-фильтр в `load_relief` снят (тип гарантирован
   `_prepare`).
4. **Размеры** — `PackDetailedBakeOrchestrator` 343→219 (новые
   `detailedBakeScope.py`: `DetailedScopePlan`/`resolve_detailed_scope`/
   `wilderness_tiles`; `detailedBakeRefine.py`: `DetailedRefineAggregate`/
   `refine_detailed_tiles`/`persist_detailed_grades`; общий `_run`);
   `FineTerrainRefineOrchestrator` 284→232 (`fine_chunk_rect` →
   `fineChunkGeom`, модульные `_run_refine_phase`/`_persist_grade_instances`);
   `PackMaterializationOrchestrator` 263→240 (`_default_entry_stack`,
   `_load_relief_templates`, `_persist_bake_relief_grades`).
   Тестовые швы `orch._refine_tiles`/`_bake_location_scope` сохранены.
5. **Мелочи** — `spec.relief_pick_policy` напрямую (isinstance-guard
   снят), `_mountain_pick_site_id()` для формата id.

**Проверки:** 62 теста (relief suites + detailed grade + c11 gate) + 12
refine + 41 bake — OK. Полный `test_*pack*.py` (445) — 20 errors в
`test_library_packs_5a`, все `world_repository` kwarg — незакоммиченные
правки B6 мастера, не этот план.
