# LIBPACK-T-2 — снятие interim `import_library_uid_into_world` — DONE 2026-10-11

Оба шага сданы: R34 → `ReliefPackAdapter.remap_world_refs` через общий
helper `reliefTerrainSync` (raw-scan колонки — resolved-scan мёртв под
T-29 overlay, см. LIBPACK-T-7); роут `template_uid` → member→pack→
`instantiate_pack`, interim-метод удалён. Проверка: `test_library_packs_4b`
18/18 (вкл. `test_instantiate_upserts_terrain_registry_keys`,
`test_template_uid_resolves_to_pack_instantiate`), 4a 24/24, b3 44/44.

Закрытие долга **LIBPACK-T-2** (`tz_generator_technical_debt.md` §LIBPACK-T):
interim-метод `ReliefWorldImportService.import_library_uid_into_world`
(копия engine-тела в `legacy` world-пак по одному `template_uid`) заменяется
на `LibraryPackService.instantiate_pack`. Блокирует **W2-3**
(`world-scoped-column-write`): interim-сайт писателя умрёт — мигрировать его
на паттерн A до удаления = мёртвая работа (см. `plan-dependency-graph.md`).

## Решения (согласовано 2026-10-11)

- **Роут — вариант A:** `POST /worlds/{w}/relief-templates/import` сохраняет
  параметр `template_uid`; сервис резолвит member → `pack_uid` →
  `instantiate_pack` (идемпотентно: повторный вызов — `created=False`,
  rewrite членов = шаг 4c). Member-level engine→world не вводится — ТЗ §0.1:
  перенос между scope только операциями пака целиком; §1: частичных
  инстансов нет. Pin-набор (`world.library_pins`) как UX-выбор члена —
  **out of scope** (writer отсутствует, отдельная тема).
- **R34 — вариант a:** upsert `terrain_registry` ключей из
  `outline.conditions` переезжает в `ReliefPackAdapter.remap_world_refs`
  (доменный адаптер владеет последствиями операции, ТЗ §0.2; один
  `world_repo.update` на instantiate, без второго writer-path).
- **Пак назначения** — `world.{uid}.instance.{source}` (контракт
  `instantiate_pack`), не `legacy`: engine-копии — не авторские записи
  (ТЗ §1.1). Смена member UID — не миграция, БД пересоздаётся по
  schema-policy.

## Не меняется

- `import_outlines_into_world` / `_attach_member` — bundle manifest-less
  тела в `legacy` пак остаются (это не interim; R34 для них сохраняется).
- `ReliefWorldImportService` как таковой — `ReliefPackAdapter` использует
  `prepare_body` для доменной валидации (`write_body`).
- Семантика re-import: interim перезаписывал тело; теперь повторное
  «прикрепление» — no-op до шага 4c (preview/confirm rewrite). Принято:
  snapshot-семантика ТЗ §1.1.

## Шаг 1 — R34 terrain sync в relief-адаптер

- **Цель:** instantiate engine relief-пака upsert'ит missing ключи
  `terrain_registry` (canonical, не затирая) — паритет с interim-путём.
- **ТЗ:** `tz_terrain_relief.md` R34 (import шаблона может upsert missing
  ключи); `tz_template_library_packs.md` §0.2, §2.
- **Файлы:**
  - `backend/app/application/worldData/libraryPacks/domainAdapters/relief.py`
    — `remap_world_refs`: сбор `{c.terrain.value for c in outline.conditions}`
    по `RemappedMember`s, merge missing ключей в `world.terrain_registry`
    до единого `world_repo.update`.
  - общий helper (один источник логики для адаптера и legacy-пути):
    `backend/app/application/worldData/reliefTerrainSync.py` — merge
    missing canonical `WorldTerrainRegistry` entries в
    `world.terrain_registry` + `r34_terrain_upsert` warning на ключ.
  - `backend/app/application/worldData/reliefWorldImportService.py` —
    `_sync_terrain_from_outline` переезжает на helper (write-path
    `worlds.update` сохраняется).
- **Контракт:** helper мутирует `world.terrain_registry` (json-список
  dict-рядов) и возвращает добавленные ключи; существующие ключи не
  затираются; ключи вне canonical engine-сета пропускаются (текущее
  поведение `canon.get(key) is None → continue` сохраняется). Лог —
  `relief_warning("r34_terrain_upsert", world_uid, system_terrain,
  source="pack_instantiate"|"relief_import", …)`.
- **Проверка:** `python -m unittest tests.test_library_packs_4b` —
  новый кейс: relief member с `conditions` на terrain, отсутствующий в
  `world.terrain_registry` → после `instantiate_pack` ключ добавлен
  canonical-рядом, чужие ряды нетронуты; member без conditions — no-op.
  `python -m compileall` на затронутые модули.
- **Done:** instantiate upsert'ит terrain-ключи; legacy-путь работает
  через тот же helper; дубли логики нет.

## Шаг 2 — роут → `instantiate_pack`, удаление interim-метода

- **Цель:** единственный caller interim-API переведён на pack-операцию;
  метод удалён — сайт писателя `reliefWorldImportService` для
  engine→world исчезает (разблок W2-3).
- **ТЗ:** `tz_template_library_packs.md` §0.1 (scope member-copy), §1,
  §1.1, §2.
- **Файлы:**
  - `backend/app/api/routes/reliefTemplates.py` — ветка `template_uid`
    (query + `{"template_uid": …}` body): `library_pack_service()
    .get_member(template_uid)` → `instantiate_pack(member.pack_uid,
    world_uid=…)`. Маппинг pack-ошибок (`str(exc)`, `.message` нет):
    `LibraryPackNotFoundError`→404, `LibraryPackValidationError`→422,
    `LibraryPackConflictError`→409, `LibraryPackOwnershipError` /
    `LibraryPackReadOnlyError`→403.
  - `backend/app/application/worldData/reliefWorldImportService.py` —
    удалить `import_library_uid_into_world` + `_import_library_uid`;
    docstring модуля — interim-пометка уходит.
- **Контракт:** response `{"pack_uid", "created": bool, "imported":
  len(members), "uids": [member.template_uid …], "missing_dependencies":
  [...]}` — ключи `imported`/`uids` сохраняют смысл для старых callers.
  Диагностика граничных случаев — честная: `template_uid` члена
  world-owned пака → 422 («only engine libraries instantiate»); члена
  default-пака → 422 («already available»); ownerless-тело без member
  (LIBPACK-T-1) → 404.
- **Проверка:** `python -m unittest tests.test_library_packs_4b` (+ кейс
  member→pack resolve → instantiate, `created=False` при повторе);
  `python -m compileall`; grep `import_library_uid_into_world` — ноль
  ссылок. Smoke мастера: POST с `?template_uid=` на реальном мире.
- **Done:** interim-метод и его caller удалены; engine→world relief —
  только через `instantiate_pack`; W2-3 разблокирован.

## Out of scope

- Pin-write API (`library_pins`) — UX «выбранный член» поверх инстанса.
- Member-copy между паками автора — шаг 4c.
- Re-instantiate rewrite (preview/confirm) — шаг 4c.
- Bundle/routes pack lifecycle — шаг 4d.
