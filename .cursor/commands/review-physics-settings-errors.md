---
name: review-physics-settings-errors
description: Независимое ревью PS-ERROR-1 D2 — typed ошибки Physics settings, validation/runtime policy и границы evidence.
---

Проведи независимое code review PS-ERROR-1 D2 по [Physics-плану §P3.19–P3.21](../plans/physics-spatial-dynamics.md) и [ERROR-CONTRACTS-1](../plans/error-contracts-1.md), включая EC-11. Соблюдай [правила ревью](../rules/review-split.mdc). Дополнительный scope/ревизия, если переданы: `$ARGUMENTS`.

Зафиксируй HEAD, переданный диапазон и релевантные рабочие изменения, включая untracked files. Учитывай код, уже вошедший в HEAD. Не ограничивай ревью последним коммитом или наличием текста в плане. Чужие параллельные изменения не приписывай Physics.

**Режим read-only:** код, тесты, планы и статусы не менять, коммиты не создавать. Не запускать сервер, solver, production DAG или storage migration; не выполнять runtime activation. GEN-DAG draft не является принятым binding. Ревью не заменяет пользовательскую приёмку D2/PH-ARCH/PH-ORCH.

## Scope и evidence

Исследуй definitions, imports и реальные callers в `backend/app/dataModel/physics/settings/`, `backend/app/application/physics/settings/`, `backend/tests/physics/` и `backend/tests/typing/physics/`. Проследи зависимости общего error core, checked paths, JSON boundary/reporting и canonical codec там, где это нужно для вывода. Для каждой найденной неоднозначности пройди цепочку input → validation → typed result → report/log → view/ref → prepare.

Сверь текущую реализацию с принятыми решениями, учитывая позднейшие уточнения:

- Validation некорректной gravity отказывает; runtime допускает согласованный default fallback с WarningError. Strict value POJO не становится permissive.
- `REVISION_MISMATCH` означает только несовпадение expected/observed refs, а не доказанное устаревание или authoritative freshness.
- Отказ операции не означает отключение пользователя. Retry/skip/session policy и реальные execution boundaries принадлежат внешнему DAG/runtime; их готовность этим срезом не доказана.

## Обязательные контрпримеры

1. **Две политики.** На одном invalid magnitude проверь validation refusal и runtime default 9.80665 с той же concrete причиной/code/path/arguments. Включи null, bool, string, negative, NaN/Inf, container и overflow integer. Проверь missing/full authoring отдельно от partial input; explicit zero/-0 и корректный custom value не должны становиться fallback.
2. **Fixed operations.** Проверь обе публичные input functions и несовместимый ResolveContext: mode, validate_only, partial и collect_only. Wrong policy не выбирает другую operation. Captured POJO/view/ref/checkpoint не принимается как authored mapping для default-repair. Shared resolver policy других доменов не изменена.
3. **Mixed/structural failure.** Unknown key, old g, nonobject root и invalid gravity + unknown key не дают success/continuation. Сохраняются независимые причины и порядок; лог о применённом default не выпускается до полного admission. Нет скрытого truncation или потери field identity.
4. **Общие typed errors.** Проверь F01/F02/F03/F05/F06/F07, concrete FieldPathError subclass, checked exact gravity path, code↔arguments, явные закрытые unions и immutable payload. Попробуй foreign enum, одноимённое значение другого enum, чужой arguments POJO, другой валидный field path, неизвестный discriminator и forged objects. Не требуй новых классов ради симметрии.
5. **Integrity и revision.** Проверь world/schema/content mismatch отдельно от expected/observed revision mismatch. Неверный checkpoint/captured record не должен попасть в input fallback. Подмени значение при прежнем hash, hash при прежнем значении, schema version и world; проверь порядок отказов и отсутствие partial prepared result, mutation, writes или effects. Переданный current view не считать доказательством актуальности принятого мира.
6. **Bypass и restore.** Constructor, model_validate, dict и JSON; model_construct/model_copy, missing/defaulted fields, extras, corrupt nested settings. Проверь, что completeness и digest guards P1/P2 сохранены. Для typed result/error JSON round-trip проверь concrete types и arguments, включая JsonFieldError внутри malformed admission и mixed refusal. Отдельно исследуй JSON-only restore nested tuples в Physics: он не должен ослаблять Python strictness, обходить original model invariants или становиться альтернативной schema/serializer.
7. **Mapper faults.** Unknown Pydantic/custom code, known code с неверными args и неизвестный loc не превращаются в INVALID_GRAVITY/default. Технический codec fault и cancellation не подавляются. Отдельно оцени соответствие PhysicsSettingsBoundaryFault общей F05 boundary; отсутствие production handler фиксируй как scope limitation, а не гарантию session recovery.
8. **Reporting/logging.** Blocking errors и continuation diagnostics разделены. Emit/collect-only дают одинаковые result/value/machine facts. Одна причина даёт один WarningError в request-local report; validation не пишет warning. Selected default присутствует в diagnostic и log presentation; report не теряет concrete F01. Нет второго emitter в POJO/codec/capture/prepare и утечек raw input/exception. Реальный I0 sink/transcript/correlation не выводить из mock logger test.
9. **Callers и ownership.** Проверь, что все callers разобрали новые result unions, неподдержанные reason не остались живым API, dataModel не импортирует application/engine и нет новых SQL/Time/WorldService reads. Codec compatibility и соседние DAG/Snapshot изменения оценивай только как dependencies; не расширяй cleanup на чужие домены.

## Проверки

Из корня репозитория в PowerShell, используя существующий локальный interpreter:

```powershell
Push-Location backend
try {
    .venv/Scripts/python.exe -m unittest tests.physics.test_settings_core tests.physics.test_settings_policy tests.physics.test_settings_typing tests.physics.test_codec_compatibility tests.planning.encoding.test_canonical_codec tests.snapshotCore.contracts.test_codec.CanonicalRequestCodecTests.test_raw_digest_is_shared_with_canonical_and_tile_hashing tests.errorContracts.test_import_issues tests.errorContracts.test_resolve_issues tests.errorContracts.test_typing tests.errorContracts.test_core
    if ($LASTEXITCODE -ne 0) { throw 'PS-ERROR-1 review checks failed' }
} finally { Pop-Location }
```

Typing gate должен проверить positive исходники/API и точные negative diagnostics через project Pyright без сетевой установки. Не считать прошлые 69 PASS доказательством текущего состояния: воспроизведи набор. По необходимости добавляй изолированные in-memory контрпримеры без изменения tracked/untracked файлов. Новую регрессию отличай от existing baseline failure по воспроизводимому evidence; при невозможности сравнения так и укажи.

## Результат

Сначала actionable findings по серьёзности: definition/caller с точным file:line, минимальный вход, expected/actual, нарушенный контракт и последствия. Для каждого finding укажи disposition: OPEN regression, existing defect или external prerequisite; ограничение evidence не выдавай за закрытие дефекта.

Дай отдельные verdict по input policy, typed causes/results, integrity/revision, JSON/bypass, reporting/logging и caller migration. Затем общий verdict D2 и короткий список prerequisites для I0/activation. Отдельно перечисли непроверенные runtime guarantees. Если findings нет — скажи это явно с границами проверки; review PASS не означает пользовательскую приёмку или снятие внешних gates.
