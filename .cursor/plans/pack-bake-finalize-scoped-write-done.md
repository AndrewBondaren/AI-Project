# packBakeFinalize — анализ и план scoped write ✅ DONE

- Дата: 2026-10-16.
- Статус: PBF-1/PBF-2/PBF-3 выполнены 2026-10-16.
- Контекст: W2-3/W2-4 и G-1 закрыты; финализация pack осталась явным
  исключением из правила «внутренние world writes не вызывают мастерский update».

## Реализация и приёмка

- Добавлены facade WorldPackMetadata и WorldMapResolutionSettings, scalar wire
  helpers и startup guards. L0 override использует общий legacy int-conversion
  helper существующей policy, без новых strict/min ограничений; null/default
  и запись resolved side сохранены. G-1 и terrain_pack_version не изменялись.
- Finalizer использует свежий repository World, detached scoped apply по трём
  колонкам и один update. Container передаёт repo/db; короткая UOW принадлежит
  PackMaterializationOrchestrator. Повторный recalc удалён.
- Общий path formatter сохраняет корректный existing ref, portable managed ref
  или absolute custom root. Cache invalidation работает по actual roots,
  включая старый root и ошибки после manifest save. Identity mismatch и missing
  world отклоняются до finalization side effects.
- Manifest save — same-directory temporary file + replace, cleanup временного
  файла при отказе. При replace failure старый manifest остаётся читаемым.
  SQL rollback не откатывает файлы; publication/recovery protocol не добавлялся.
- Приёмка: 13 новых test_pack_bake_finalize; все 263 regression-теста прошли:
  test_pack*.py 98 (включает новые 13), test_world*.py 105,
  test_light_bake_cleanup 9, test_import_validation_policy 11,
  test_library_world_column_write 6, test_policy*.py 17,
  test_transition_pack_roundtrip 6, test_library_packs_5b_import 11.
- ТЗ и dependency graph актуализированы, временное исключение packBakeFinalize
  снято. Ниже сохранены исходный анализ и критерии приёмки.

## Фактический путь

`WorldSurfaceMaterializationOrchestrator` → light/full methods
`PackMaterializationOrchestrator` → `finalize_pack_on_world`.
В production Container передаёт WorldService; финализация условна при
отсутствии этой зависимости. Detailed/entry refine имеют свои write-пути:
этот helper не является универсальной финализацией каждого изменения pack.

Сейчас helper:

1. Вызывает `recalc_manifest_counters()`.
2. Вызывает `save_manifest()`, который повторно считает counters,
   вычисляет SHA-256 canonical manifest (content_hash исключён) и сохраняет JSON.
3. Инвалидирует PackReadContext по пути старого world.
4. Вызывает `WorldService.update` для `terrain_pack_path`, `terrain_pack_hash`,
   `world_map_cells_per_tile` и возвращает `result.world`.
5. Пишет success-log. Orchestrator возвращаемый World сейчас не использует.

## Найденные границы и проблемы

- Master update нормализует весь документ и проверяет чужие facade-колонки.
  Поэтому корректный bake может упасть при записи metadata уже после записи файлов.
- `world_map_cells_per_tile` — не только metadata: optional master override
  разрешения L0. Policy задаёт default=32, runtime resolve делает
  `max(1, int(override))`; manifest фиксирует side bake. Финализатор сейчас
  записывает resolved side обратно в world (включая замену None на 32).
  Убирать эту запись либо менять null/default/strictness молча нельзя.
- `terrain_pack_version` есть в SQL/World и ТЗ, но helper её не пишет;
  других явных Python-читателей/писателей этой колонки не найдено. Не добавлять
  запись версии автоматически в рамках устранения мастерского update.
- `WorldPackWriter.pack_storage_path()` всегда возвращает
  `worlds/{uid}/pack`, даже если writer открыт для другого root. Path resolver
  поддерживает custom/absolute roots. Финализация такого writer может сохранить
  указатель на другую папку; cache invalidation по старому world тоже не
  гарантирует охват actual writer root.
- `PackManifestStore.save` использует обычный `write_text`, а не temporary
  file + replace. Atomic `_atomic_write` writer применяется к blobs, но не
  к manifest. Это расхождение с заявленным WP-7, отдельное от SQL scoped write.
- SQL transaction не откатывает уже записанные файлы. При SQL failure после
  успешной записи manifest файловая версия остаётся новой; cache должен
  соответствовать файловому состоянию даже при ошибке world save.

## Согласованная декомпозиция

### PBF-1 — убрать master update, сохранить три authored world writes

- Ввести typed coverage для path/hash и независимого L0 override. Предлагаемые
  POJO: `WorldPackMetadata` (path/hash) и `WorldMapResolutionSettings`
  (`world_map_cells_per_tile`). Не расширять одно-полевой WorldGridSettings G-1:
  размер macro-cell и разрешение маски L0 независимы (WP-10 v2).
- Регистрировать facade multi-column slices, использовать общие scalar wire
  helpers, startup guards и общий resolver. Non-facade обход в scoped helper
  не добавлять. Нет SQL migration или переименования колонок.
- Поля metadata nullable, поскольку мир может не иметь pack. Не вводить
  самодельную проверку существования пути в чистом POJO или обязательность
  одновременного path+hash: таких гарантий текущий write-контракт не объявляет.
- До реализации зафиксировать допустимость wire для side в ТЗ, с опорой на
  существующий `WorldMapCellsPerTilePolicy`. Предлагается сохранить текущие
  default/override и запись resolved side. Не добавлять новые strict/min правила
  для master override под видом миграции metadata; не дублировать policy в POJO.
- Финализатор получает IWorldRepository вместо WorldService; DI orchestrator
  переключается на repository, условный режим без SQL dependency сохраняется.
- Для записи загружать свежий world через require_world, а не сохранять объект
  со старта длительного bake. Resolve всех трёх authored колонок на рабочей
  копии → один repository update. Чужие свежие колонки сохраняются без repair
  и без ревалидации. Транзакция принадлежит вызывающей orchestration.
- Убрать повторный recalc из helper: save_manifest уже выполняет его.
- Success-log только после успешной записи world. Формат ошибок scoped resolve
  — ImportValidationError с исходными issues; world lookup — доменная not-found.
- COLUMN_INVALIDATES не расширять автоматически: текущие три поля не имеют
  объявленной очистки доменных таблиц. Финализация не меняет размер macro-cell
  и не требует force.

### PBF-2 — actual root и последовательность ошибок/кэша

- Сохраняемый path обязан round-trip через WorldPackPaths.for_world в actual
  writer.paths.root. Существующий custom path сохранять, если он указывает туда;
  canonical managed root должен остаться переносимым. Конкретный formatter
  расположить рядом с текущим resolver, используя настроенный db/pack root,
  не новый набор path-правил в finalizer.
- Инвалидировать actual writer root и прежний root, если они различаются.
  После успешного manifest save выполнять это и при последующей SQL failure.
  Инвалидация только после SQL success недостаточна: файлы уже изменились.
- Проверить identity world_uid между target world, writer.paths и manifest;
  несовпадение отклонять до finalization side effects. Это проверка операции,
  не обязанность pure world-column POJO.
- Сохранять file-first порядок: world не должен указывать на manifest,
  который ещё не сохранён. Не обещать атомарный commit FS+SQLite; отдельный
  publication/recovery протокол потребовал бы более широкого плана.

### PBF-3 — atomic manifest save (отдельный подшаг WP-7)

- Temporary file в том же каталоге + replace целевого manifest.
- При ошибке до replace прежний manifest остаётся читаемым; SQL world save
  не выполняется. Не выдавать filesystem replacement за общую FS+SQL transaction.
- Проверить всех существующих callers PackManifestStore/WorldPackWriter;
  этот подшаг затрагивает не только light/full финализацию.

## Приёмка

- Невалидная чужая facade-колонка не блокирует finalization; три authored
  поля проверяются до world save, один repository update, чужие свежие поля
  не перезаписываются старым bake snapshot.
- Default side=None → manifest resolved side сохраняется по текущей семантике;
  explicit override проходит без неожиданной смены поведения. Size G-1 и
  terrain_pack_version не меняются.
- В helper/orchestrator больше нет master update; DI проверяется через Container.
- Hash в world совпадает с сохранённым manifest, повторный finalize без новых
  данных даёт тот же hash; counters считаются единственным writer-путём.
- File failure → SQL не меняется; SQL failure после manifest save → ошибка
  наружу, без success-log, disk manifest читаем, необходимые caches сброшены.
- Custom root round-trip, old/new cache roots, world/manifest identity mismatch.
- Manifest replacement failure оставляет прежний JSON читаемым (PBF-3).
- Новые test_pack_bake_finalize; regression test_world_pack_writer_reader,
  test_pack_root_resolution, test_pack_render_read_facade, test_pack_bake_modes,
  test_light_bake_cleanup, world/import/policy tests новых facade slices.

## Что пока не меняется

Version write, обновление world hash после каждого detailed/entry изменения,
атомарный FS+SQL publication protocol, stale-конфигурация всего длительного bake,
валидация всех manifest-полей и полная миграция L0 runtime consumers.
Реализация согласованных PBF-1/PBF-2/PBF-3 завершена; перечисленные выше
расширения за их границей не реализованы.
