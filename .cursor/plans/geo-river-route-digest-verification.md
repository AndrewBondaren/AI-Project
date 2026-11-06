# GEO · river-route digest после WATER_KIND_MISMATCH

6 ноября 2026 года. Проверка на HEAD `6b9e6d13`. Scope: исторический river-route сценарий в `tests/geo1/procedural_refinement/test_proposals.py` и его прямые зависимости. Посторонние изменения рабочего дерева не включены.

## Причина и решение

Изменение digest закономерно следует из [принятого D1 WATER_KIND_MISMATCH](geo-water-kind-mismatch-d1.md): конкретная причина с typed code, checked path и контекстом источника должна доходить до fine-water envelope. `FineRiverPublicationJob.publish` переносит `water.diagnostics` в результат перед вычислением output fingerprint. Исторический тест хеширует `(result.payload, result.diagnostics)`, поэтому наследует эту миграцию.

Штатный точный тест до правки воспроизвёл FAIL: `d632ae064d4cc12d76da2ac032b3a35d7642f40140c1471d99aa02428f2f99a7` вместо `1ccb025f9dbc28083d7751293bec109823d7970836ce4eee6c882aef07c8eeb2`.

Для сравнения `git archive` извлечены в отдельные каталоги, без замены рабочего кода:

- `9ed3bba6`: коммит введения эталона. Все три исторических digest воспроизведены штатными `scenario(**settings)` → `route(inputs, water)`.
- `d01cf073`: непосредственно перед D2. Первый сценарий не получает результата: `waterMaterialize.py:75` → `waterDiagnostics.py:13` → запрещённый базовый `FieldPathError`. Поэтому новая запись FAIL в discover означает снятие этого барьера.
- `6b9e6d13`: первый сценарий публикуется с конкретной причиной. Два запуска capture в отдельных процессах дали одинаковый новый digest; дополнительная регрессия повторяет штатный route и проверяет равенство envelope.

## Полевое и каноническое сравнение

Рекурсивно сравнены все поля Pydantic/dataclass моделей с сохранением конкретных имён типов, enum-значений и bytes. Для первого сценария inputs, полный pre-water window и оба water/river payload совпадают. Совпадают маршруты, координаты, высоты, drainage, идентичности edge/source/receiver, segment metadata и объявленный флаг. Совпадают исходные ключи water, зависимости water и версии контракта/алгоритма. Отдельного поля metadata у envelope нет; вложенные поля включены в сравнение.

Канонические digest до и после совпадают:

| Объект | Digest |
|---|---|
| physical inputs | `4e9f50038f125f59c70f61f05a07cbbd2b1be9aea369e6c2df5ef3b17a66dc70` |
| pre-water window envelope | `ac306d41a800488c05a1fc95f0534658877876db118544c5c78d81e5220271cc` |
| water payload | `30526ce71aa1e754b7f6447b8e194c19a35c96280095278d7ead6051d1cd0c75` |
| river payload | `12843e8818af8ef750edd2fa509d51860e700d34eea4ce4aac5d56cf4f87a533` |

Первое содержательное различие — `water.diagnostics[0].issue`, перенесённое в `result.diagnostics[0].issue`:

| Поле | Исторический контракт | Принятый D1 |
|---|---|---|
| concrete type / wire ID | FieldPathError / 106 | WaterKindMismatchIssue / 323 |
| code | строка WATER_KIND_MISMATCH | HydrologyMaterializationCode.WATER_KIND_MISMATCH / enum ID 324 |
| path | tuple `('hydrology', 'water', 'lake')` | ValidatedFieldPath к WaterBody.kind, root/owner `app.dataModel.hydrology.waterBody.WaterBody`, один FieldSegment `kind` |
| source_uid | отсутствует | `lake` |
| authored_kind | отсутствует | BasinKind.LAKE |
| physical_kind | отсутствует | BasinKind.OCEAN |
| schema_id, reference, runtime_context | все None | поля отсутствуют |

Сообщение `authored kind=lake retained; physical class=ocean`, число диагностик (1), порядок и disposition FALLBACK сохраняются. Физический классификатор и итоговое тело LAKE дают прежние значения.

Registry: все исторические пары ID/type сохранены, добавлено 27 bindings с момента исходного эталона. Для этого изменения используются 323/324 и уже зарегистрированные 303/304/305 (ValidatedFieldPath/ModelIdentity/FieldSegment); BasinKind=41, PlanDiagnostic=105, FineRiverPlan=290 неизменны. Между `d01cf073` и D2 добавлены только bindings 323/324 в surface manifest. Добавление неиспользуемого binding само по себе в digest значения не входит. Канонический codec пишет ID конкретного типа. Размер кодирования пары вырос с 2217 до 2795 bytes; первое сырое отличие на offset 7 — длина внешнего TLV, содержательная причина внутри issue описана выше.

Следствия публикации: water output fingerprint `96f7b91b…` → `92676d6b…`; этот ref меняется в river dependencies, river input fingerprint `f48f1787…` → `b84e3586…`, river output fingerprint `cbe108b6…` → `4338d43a…`. Они не входят непосредственно в проверяемую пару `(payload, diagnostics)`. Причина изменения её digest полностью локализована в diagnostics. Признаков изменения алгоритма маршрутизации в этом сценарии нет.

## Изменения и проверки

В [fixture](../../backend/tests/geo1/procedural_refinement/river_route_golden.json) сохранены payload из `9ed3bba6`, его неизменный digest, старый и новый digest пары. Обновлён только первый эталон. Добавлена проверка полного исторического payload, конкретного типа причины, code, checked path, UID, обоих kinds, message, disposition, повторяемости и encode → decode → encode river envelope. Исторические варианты переведены в subTest, чтобы один барьер не скрывал следующий. Подмен входа или producer в этих проверках нет.

Команды из `backend`, после `$env:PYTHONPATH='.;tests'`:

```powershell
.\.venv\Scripts\python -m unittest tests.geo1.procedural_refinement.test_proposals.ProceduralRefinementTests.test_declared_membership_and_historical_results_do_not_depend_on_segment_flag -q
.\.venv\Scripts\python -m unittest tests.geo1.procedural_refinement.test_proposals.ProceduralRefinementTests.test_kind_mismatch_migration_preserves_historical_river_payload tests.geo1.fine_water.test_kind_mismatch -q
.\.venv\Scripts\python -m unittest discover -s tests/geo1/procedural_refinement -t . -q
```

- Точный тест после обновления: 1 test, 2 errors, 0 failures (0,834 с). Первый subTest проходит, включая равенство результата с coarse proposal `declared=False`.
- Новая регрессия и WATER_KIND_MISMATCH: 3 tests, OK (2,938 с), включая cold codec проверки из test_kind_mismatch.
- Группа: 9 tests, 5 errors, 0 failures (2,082 с). Это 4 метода с ошибками, один содержит два ошибочных subTest.

Оставшиеся барьеры: `{lake: False}` идёт в `riverPrepare.py:145` с ERROR; `{mouth: (8,11)}` — в `riverPrepare.py:187` с FALLBACK. Оба останавливаются в `_emit_diagnostic`, строка 233: `TypeError: FieldPathError requires a named concrete domain subclass`. Их исторические digest не обновлены, поскольку нового штатного результата ещё нет. В группе такой же caller блокирует тесты coarse wet membership и rejected parent; negative disabled branch теста fine classification останавливается на базовом FieldPathError в `fine/execution.py:73`.

Требуется отдельное согласование конкретного River diagnostic и его persisted boundary у владельца Hydrology/codec для следующих producers. Здесь runtime-код, registry, source-v1 и алгоритмы не изменены. Смена первого эталона подтверждена принятым D1; зелёная приёмка всей группы не заявляется. Остановка до следующего producer диагностики.
