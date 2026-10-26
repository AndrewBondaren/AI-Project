# Library packs — техдолг ревью шага 4c (done)

**Статус:** complete; R-1/R-2/R-3 выполнены. Три пункта согласованы пользователем 2026-10-11.
**Источник:** ревью коммита `9a50d4d17feac02b1a7d6909c5525f54a9bcea60`.
**Scope:** исполнение согласовано пользователем 2026-10-11 («Выполняй план»); пункты выполняются последовательно по code-gates.
**SoT:** [tz_template_library_packs.md](../../docs/tz_template_library_packs.md) §1.1, §2, §7; [tz_logging.md](../../docs/tz_logging.md) L1–L8.

## LIBPACK-4C-R-1 — диагностика через общий логгер проекта

**Цель:** сохранить типизированные факты о ссылках и направить их в существующий resolve sink на границе lifecycle-операций.
**Контракт:** `FieldPathError` получает необязательный typed reference-контекст; `report_issues()` становится общей эмиссией существующего policy-resolve, используемой также `reject_unresolved()`. Чистый `reference_index()` возвращает typed issues; DTO сохраняют строковую диагностику, preview дополнительно несёт typed issues до границы reinstantiate. Snapshot/diff/fingerprint и правила apply не меняются.
**Data flow:** pure index → обогащение известным владельцем/world → общий policy-resolve report на границе copy/reinstantiate/usage. Отсутствующие зависимости используют тот же контракт; повторная эмиссия через `diagnose_missing` внутри copy исключается. Общий sink и transcript остаются штатными.
**Проверка (из backend):** `../.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_library_packs_4*.py'`; аналогично `test_library_pack_logging.py`, `test_logging_routes.py`, `test_generation_logging.py`, `test_deterministic_ids.py` — все проходят. Новые проверки: copy/preview/confirm/usage, typed поля, отсутствие дублей, sink + transcript.

**Статус:** resolved (2026-10-11). **Приоритет:** P2.

**Результат:** `reference_index()` возвращает typed `FieldPathError` с `ReferenceIssueContext`; ownership/world дополняются на application-границе. Copy, reinstantiate и usage-path используют общую эмиссию `report_issues()` существующего resolve logger; `reject_unresolved()` использует ту же эмиссию. Missing dependencies в `_PackScope` также направлены в resolve; copy не вызывает второй эмиттер. Строковая диагностика DTO сохранена. Проверено 122 тестами: library packs 68, lifecycle logging 6, logging routes 15, generation logging 4, deterministic IDs 18, import validation policy 11. Проверка sink/transcript подтверждает одну и ту же JSON-запись без повторного вызова logger; другой мир не подавляется. `git diff --check` без ошибок.

**Проблема:** `referenceResolver.reference_index()` возвращает недоступные ссылки строками; copy/reinstantiate передают их в DTO, а `member_usages()` отбрасывает диагностику. Эти события не проходят через существующий policy-resolve эмиттер.

**Решение пользователя:** исправить с использованием общего логгера проекта — фасада `app.core.loggingConfig` и существующего эмиттера `jsonValidation/resolve`. Новые параллельные logger/sink/formatter не создавать. Чистый индекс возвращает типизированные факты; граница операции эмитирует каждое событие один раз. DTO сохраняет диагностику для caller.

**Файлы:** `backend/app/application/worldData/libraryPacks/referenceResolver.py`, `memberCopyOps.py`, `reinstantiatePlan.py`, `reinstantiateOps.py`; существующий контракт policy-resolve в `backend/app/application/jsonValidation/`.

**Готово когда:** недоступная ссылка или отсутствующая зависимость диагностируется с world UID, доменом, requested template UID, известным owner/dependency pack UID, path и причиной по §7; запись направляется в существующий доменный JSON sink и при generation scope копируется в transcript без повторной эмиссии. Проверки покрывают copy/reinstantiate и отсутствие потери диагностики в usage-path.

## LIBPACK-4C-R-2 — единая декларация ref-полей для чтения и remap

**Цель:** устранить расхождение охвата ссылок между reference-index и remap.
**ТЗ:** `tz_template_library_packs.md` §1.1 (referenced), §2 (remap).
**Контракт:** typed `NestedRefField(parent_field, uid_field, library_kind, repeated)` в `domainAdapters/refFields.py` задаёт чтение и преобразование одного вложенного ref-поля. `STRUCTURE_REF_FIELDS` — один набор main/secondary; `RELIEF_POLICY_REF_FIELDS` выводится из typed canonical-модели `WorldReliefPickPolicy`. Публичные методы адаптеров и wire/UID-контракты не меняются.
**Data flow:** adapters → общий набор деклараций → отдельно extraction (`MemberRef`) / remap (`model_copy`). Общий lifecycle-движок не знает доменных полей; разбор plot-layout и определение ref-родителей общие. Relief extraction использует существующий worldRow-resolve, remap сохраняет per-entry валидацию и raw overlay.
**Проверка (из backend):** `../.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_library_pack_refs.py'`; также `test_library_packs_4*.py`, `test_library_pack_logging.py` — зелёные. Проверки охвата main/secondary, всех контекстов relief, внешних UID, pointer/non-layout строк, unknown wire-полей, ошибочной схемы и защиты secondary-ref от удаления.

**Статус:** resolved (2026-10-11). **Приоритет:** P3.

**Результат:** `NestedRefField` — единый контракт извлечения/изменения вложенного UID. `STRUCTURE_REF_FIELDS` используется чтением и remap main/secondary; общий `structure_ref_model()` определяет plot-layout и пропускает pointers/non-layout. `RELIEF_POLICY_REF_FIELDS` выведен из typed canonical-модели, используется `relief_policy_refs()` и per-entry remap. Адаптеры делегируют этим функциям; общий lifecycle-движок доменных полей не получил. Проверено 81 тестом: новые ref/lifecycle проверки 7, library packs 68, lifecycle logging 6. Покрыты main/secondary, все пять relief-контекстов, внешние UID, unknown wire-поля, pointers/non-layout, ошибки схемы и запрет удаления по secondary-ref. `git diff --check` без ошибок.

**Проблема:** `refFields.structure_refs()` и `remapRefs._remap_structure_refs()` отдельно перечисляют `main_building.structure` и `secondary_buildings[].structure`. Аналогично расходятся обходы relief-policy в `ReliefPackAdapter.world_refs()` и `_remap_relief_pick_policy()`. Новое ref-поле приходится добавлять в несколько мест.

**Согласованное решение:** один источник деклараций доменных ref-полей; извлечение ссылок и remap используют его, сохраняя отдельные операции чтения и изменения. Общий lifecycle-движок не получает знания о конкретных доменных полях.

**Файлы:** `backend/app/application/worldData/libraryPacks/domainAdapters/refFields.py`, `remapRefs.py`, `building.py`, `relief.py`.

**Готово когда:** набор полей для reference-index и remap задаётся один раз; проверки подтверждают одинаковый охват main/secondary structure refs и relief-policy, сохранение внешних ссылок и корректность защиты используемого члена от удаления.

## LIBPACK-4C-R-3 — разделение ответственности prepare_update

**Цель:** отделить repository I/O от воспроизводимого построения плана обновления.
**ТЗ:** `tz_template_library_packs.md` §2 (preview/confirm, UID, referenced-set, fingerprint), §3.
**Контракт:** `ReinstantiateSnapshot` — catalog/source/world, тела и членство источника, source/target dependencies, существующие dependency UID, известное членство для UID-конфликтов и ownership diagnostics. `load_update_snapshot(scope, source, instance, world)` загружает данные; синхронный `build_update_plan(snapshot, adapters)` не получает scope/repositories. `prepare_update()` — единственный внутренний orchestration-шов preview/confirm. Typed projection/retention DTO — в `lifecycleContracts`.
**Data flow:** caller UOW → loader (`reinstantiateSnapshot.py`) → подготовка членов (`reinstantiateMembers.py`) → удержание/зависимости (`reinstantiatePolicy.py`) → fingerprint (`reinstantiateFingerprint.py`) → preview. Формулы ID остаются в `app.ids`; адреса lookup конфликтов вычисляет общий pure identity helper. Ownership diagnostics используют общую pure-функцию поверх загруженных данных; apply/логи остаются в `reinstantiateOps`.
**Файлы дополнительно:** внутренние `reinstantiateSnapshot.py`, `reinstantiateMembers.py`, `reinstantiatePolicy.py`, `reinstantiateFingerprint.py`, `tests/test_library_pack_update_plan.py`; нового публичного фасада нет.
**Проверка (из backend):** `../.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_library_pack_update_plan.py'`; также `test_library_packs_4*.py`, `test_library_pack_logging.py`, `test_library_pack_refs.py`, `test_deterministic_ids.py`. Новые проверки: повторное построение snapshot после изменения SQL без I/O, отсутствие мутаций snapshot, глобальный UID collision и ownership diagnostics. Существующие проверки UID, held/removed/preserved, stale-token и rollback остаются зелёными.

**Статус:** resolved (2026-10-11). **Приоритет:** P3.

**Результат:** `prepare_update()` — загрузка snapshot + синхронный `build_update_plan()`. `ReinstantiateSnapshot` и projection/retention DTO живут в `lifecycleContracts`; repository reads — в `reinstantiateSnapshot`, identity/body preparation — в `reinstantiateMembers`, удержание/зависимости — в `reinstantiatePolicy`, значимые входы token — в `reinstantiateFingerprint`. Pure ownership diagnostics разделяют copy/usage и построитель плана. Snapshot включает глобальные коллизии и известных владельцев без расширения доступного каталога. Apply/transaction/логирование сохранили прежнюю границу. Проверено 103 тестами: library packs 68, snapshot/planning 4, logging 6, refs 7, deterministic IDs 18. Новые проверки блокируют SQL при build, воспроизводят прежний snapshot после изменения БД, подтверждают отсутствие мутаций snapshot, global collision, owner diagnostics и fresh stale-confirm. Существующие проверки held/removed/preserved, UID и rollback прошли. `git diff --check` без ошибок.

**Проблема:** `prepare_update()` совмещает загрузку данных, построение UID-map, подготовку тел, политику удержания/удаления, зависимости, fingerprint и сборку preview.

**Согласованное решение:** выделить загрузку полного snapshot и чистое построение плана обновления. Подготовку тел оставить доменным адаптерам; явно отделить политики удержания/зависимостей и построение fingerprint от orchestration. Делить по ответственности, без второго публичного фасада и без механического разрезания функции.

**Файлы:** `backend/app/application/worldData/libraryPacks/reinstantiatePlan.py`, `referenceResolver.py`, `reinstantiateOps.py`, `lifecycleContracts.py`.

**Готово когда:** построение плана работает на готовом snapshot без repository I/O; preview и confirm используют один механизм. Сохраняются UID существующих членов, семантика held/removed/preserved, проверка stale token и атомарность apply; существующие lifecycle-тесты проходят.
