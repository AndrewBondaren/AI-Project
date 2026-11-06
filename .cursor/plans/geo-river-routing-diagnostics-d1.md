# GEO · scoped D1: публикация причин river routing

Статус: **предложение D1, до согласования и D2**. 6 ноября 2026 года, HEAD `6b9e6d13` с существующим рабочим diff. Основание — [разбор river-route digest](geo-river-route-digest-verification.md). Первый эталон `d632ae06…` принятой миграции WATER_KIND_MISMATCH сохраняется. Здесь изменяется только документация.

## 1. Воспроизведение

Из backend, `PYTHONPATH=.;tests`, штатные `tests.geo1.fine_water.test_routing.scenario(**settings)` и `route(inputs, water)`. Факт наблюдался через `sys.settrace` при входе в `_emit_diagnostic`; аргументы, результат и функции не подменялись. Обе ветви повторены при подготовке этого D1:

| settings | Факт перед отказом |
|---|---|
| `lake=False` | ERROR; code=NO_WATER_BODIES; reason=DRY_MOUTH; world_uid=world; object_uid=river; object_type=RIVER; source_cell=(2,11); requested_mouth=(11,11); failure_cell=(11,11); requested_receiver_uid=None; fallback_reason=None; все receiver-поля=None |
| `mouth=(8,11)` | FALLBACK; code=REDIRECTED; reason=DRY_MOUTH; те же world/object/type/source; requested_mouth=(8,11); failure_cell=(8,11); requested_receiver_uid=None; fallback_reason=None; receiver_uid=lake, receiver_kind=LAKE, receiver_cell=(10,11), receiver_level=0 |

У обеих причин rejected_connection_type=None. Фактический отказ одинаков: `riverPrepare._emit_diagnostic:233` пытается создать базовый FieldPathError и получает `TypeError: FieldPathError requires a named concrete domain subclass`. Во второй ветви альтернативный маршрут уже найден и получил land specs: ошибка происходит при публикации разрешённого продолжения.

Повторяемая команда наблюдения из backend:

```powershell
$env:PYTHONPATH='.;tests'
@'
import sys
from tests.geo1.fine_water.test_routing import scenario, route
def observe(frame, event, arg):
    if event == 'call' and frame.f_code.co_name == '_emit_diagnostic' and frame.f_code.co_filename.endswith('riverPrepare.py'):
        print(frame.f_locals['disposition'], frame.f_locals['fact'].model_dump_json())
    return observe
for settings in ({'lake': False}, {'mouth': (8, 11)}):
    sys.settrace(observe)
    try:
        _, inputs, water = scenario(**settings)
        route(inputs, water)
    except Exception as error:
        print(settings, type(error).__name__, str(error))
    finally:
        sys.settrace(None)
'@ | .\.venv\Scripts\python -
```

## 2. Полная граница общего emitter

В [riverPrepare.py](../../backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py) ровно четыре места вызова `_emit_diagnostic`:

1. `_invalid_type`, строка 74: INVALID_CONNECTION_TYPE / INVALID_CONNECTION_TYPE, ERROR. Вызывается для request.rejected_connection_type, неизвестного типа segment или известного enum, который не RIVER/MOUNTAIN_RIVER. Сохраняет исходную строку и object_type=None.
2. `prepare_river_from_inputs`, строка 145: отклонённая проверка маршрута после выбора кода. ERROR, пустой PreparedRiver с фактом.
3. Там же, строка 183: после выбора/усечения сегментов нет ни одного land spec. INVALID_SOURCE / MISSING_GEOMETRY, ERROR. Даже если поиск нашёл redirect, FALLBACK не публикуется, пока нет принятой сухопутной части.
4. Там же, строка 187: REDIRECTED с первоначальной причиной, FALLBACK, только после получения specs и drainage.

Прямой общий caller — prepare_river_requests_from_inputs. С callback его вызывает plan_prepared_routes; далее coarse/execution вызывает его отдельно для declared и auto, fine/execution — для declared и procedural proposals. PlanBuildResult сохраняет deduplicated diagnostics и допускает одновременно принятые routes и ERROR других intents.

Без callback prepare_river / prepare_river_requests возвращают PreparedRiver.diagnostics. riverNetworkAssembler и shore/fineHydrologyIndex затем вызывают **другую** функцию emit_river_diagnostic из riverRouteDiagnostics.py. Она также использует старый FieldPathError, но её runtime/import sinks — отдельный handoff, не повод включить их миграцию в этот D2. Запретить двойной emit: callback-путь не должен дополнительно логировать/записывать ctx; путь emit=None должен сохранить прежние typed facts в PreparedRiver.

Не входят: прямые PlanBuildFailure в riverPrepare (request/receiver/space/drainage invariants), disabled fine routing в fine/execution:73, другие producers воды, изменение поиска/классификации/bed, Pack и source-v1 cutover.

## 3. Владелец, reuse и семантика причин

Владелец всех перечисленных ниже причин — **Hydrology / river routing**. Переиспользовать [RiverRouteDiagnostic, RiverRoutingCode, RiverRoutingFailure](../../backend/app/dataModel/hydrology/riverRouting.py), HydrologyMouth и RiverReceiverKind; не создавать копию причин в Planning, новый строковый namespace или JSON-контекст. RiverRouteDiagnostic уже хранится в PreparedRiver, AssembledRivers и hydrology results: его сохранение минимизирует миграцию прямых consumers.

Code описывает исход операции; reason — исходный дефект пути; fallback_reason — отдельную причину неудачи альтернативного поиска. Они не взаимозаменяемы. Полный набор code на этом emitter:

| RiverRoutingCode | Условие producer | Disposition |
|---|---|---|
| INVALID_CONNECTION_TYPE | `_invalid_type` | ERROR |
| INVALID_SOURCE | checked.invalid_source либо отсутствие land specs | ERROR |
| TARGET_UNREACHABLE | DRAINAGE_CYCLE; либо провал маршрута при наличии receivers вне runtime | ERROR |
| NO_WATER_BODIES | провал пути, нет bodies/принимающей occupancy, после приоритетных source/cycle ветвей | ERROR |
| NO_REACHABLE_WATER | runtime fallback не нашёл путь при наличии receivers | ERROR |
| REDIRECTED | runtime fallback дал путь и затем принят land route | FALLBACK |

is_runtime_river_context требует mode=RUNTIME и not validate_only. В planning создаётся collect_only=True, но это не меняет mode на validate: runtime planning может перенаправить реку, validate_only не выполняет fallback search. В D2 сохраняется эта политика; severity не вычисляется из наличия reason.

Все члены RiverRoutingFailure достижимы через контракт request/check/search; таблица задаёт provenance и контекст, а disposition определяется таблицей code выше:

| Failure | Где возникает / контекст | Checked path в текущем общем факте |
|---|---|---|
| INVALID_CONNECTION_TYPE | request/segment type; rejected_connection_type, object_type=None | Нет: см. provenance ниже |
| DRAINAGE_CYCLE | приёмник с UID самой реки; failure_cell, object_uid | Нет, отношение в drainage graph |
| MISSING_GEOMETRY | initial_failure, пустой segment либо отсутствие land specs | Нет, подготовленная геометрия операции |
| MISSING_ANCHOR | `_intent_requests` не разрешил location anchor; requested_mouth/UID | Нет, результат разрешения зависимостей |
| MISSING_TERRAIN | source или шаг отсутствует в sampled terrain; source/failure_cell | Нет, покрытие входного snapshot |
| DISCONNECTED_PATH | разрыв сегментов/шага; failure_cell | Нет, связность подготовленного пути |
| UPHILL | z следующего шага выше предыдущего; failure_cell | Нет, физическая проверка пути |
| TURN_LIMIT | river_turn_ok отклонил поворот; failure_cell | Нет, отношение последовательных шагов |
| BLOCKED | source/шаг заняты river bed; failure_cell | Нет, occupancy конфликт |
| DRY_MOUTH | путь закончился без приёмника; requested_mouth/failure_cell | Нет: dry — результат проверки мира, не структурная ошибка mouth |
| WRONG_BODY | встреченный UID не равен requested_receiver_uid | Нет, отношение запроса и occupancy |
| PATH_LIMIT | len(path)>policy.max_path_cells; failure_cell | Нет: лимит policy корректен, нарушено ограничение операции |
| SOURCE_IN_WATER | source уже мокрый; source_cell=failure_cell | Нет, отношение source и состояния мира |
| RECEIVER_METADATA | нет identity/kind либо доказанного выхода receiver river в basin | Нет, полнота доказательства receiver; возможен также fallback_reason |

`initial_failure` может прийти из владельца request; штатный `_intent_requests` создаёт MISSING_ANCHOR/MISSING_GEOMETRY. fallback_route отдельно возвращает source_failure или RECEIVER_METADATA, либо None при отсутствии найденных mouths без metadata failure. `reason` всегда остаётся первоначальной причиной, в том числе при успешном REDIRECTED.

**Почему не FieldPathError.** ERROR-CONTRACTS §2.4 F03/F07 запрещает сводить operation outcome и любой warning к field issue. Здесь нет единственного поля для общего факта. Для authored недопустимого connection_type существует реальный POJO `DeclaredRiverSegment.connection_type`, однако общий request также строится из procedural RiverSegment (dataclass); emitter не получает ни owner/index исходного сегмента, ни доказательство authored origin. Назначать всем причинам путь DeclaredRiver.mouth, RiverRouteDiagnostic.reason или RiverPathSegment.connection_type нельзя. В этом срезе INVALID_CONNECTION_TYPE остаётся operational rejection с исходной строкой. Если нужен точный field issue authored ввода, его владелец — валидатор DeclaredRiverSegment; ему следует отдельно передавать проверенный путь сегмента из caller. Не угадывать этот путь по UID или тексту ошибки.

Координаты source/failure/receiver уже нормализуются diagnostic_cell_for_span: fine оставляется, coarse умножается на span до origin клетки в WORLD_FINE_GRID (не centre). requested_mouth содержит исходное authored/разрешённое описание; оно не подменяется фактическим receiver. Сохранить world_uid, object_uid, object_type, rejected_connection_type, requested_receiver_uid, requested_mouth, source_cell, failure_cell, receiver_uid/kind/cell/level, code, reason, fallback_reason без потерь.

## 4. Решение владельца carrier, необходимое до D2

Текущий PlanDiagnostic.issue = SerializeAsAny[FieldPathError[Any]] не принимает RiverRouteDiagnostic. Изолированная замена конструктора в emitter недостаточна. Предлагается согласовать с владельцем Planning/ERROR-CONTRACTS **параметризацию существующего PlanDiagnostic по конкретной модели причины**, без обратного импорта Hydrology в Planning:

- PlanDiagnostic[IssueT], bound=BaseModel; прежний default — FieldPathError[Any]. Сохранить прежние issue/disposition поля и прежний конкретный wire binding 105 для существующих field diagnostics.
- В hydrology/riverRouting.py объявить именованный `RiverPlanDiagnostic(PlanDiagnostic[RiverRouteDiagnostic])`. Это обёртка доставки существующего факта, не новая копия его полей. Валидатор проверяет точную пару code/disposition: только REDIRECTED/FALLBACK, остальные пять codes/ERROR; NOTICE и несовместимые пары запрещены и при восстановлении.
- На границах PlanBuildResult/PlanEnvelope нужен сохраняющий concrete type carrier, например SerializeAsAny[PlanDiagnostic[Any]], **с обязательной валидацией конкретного carrier**, а не свободный BaseModel/dict/Any. Повторно валидировать в исходном конкретном классе; отвергать bare Any specialization и произвольные модели. Hydrology emitter принимает RiverRouteDiagnostic и возвращает RiverPlanDiagnostic; его сигнатуру не размывать.
- Кодек должен восстановить зарегистрированный concrete carrier до валидации envelope, сохранив точный тип. Generic revalidation Pydantic не должна превращать RiverPlanDiagnostic в PlanDiagnostic[Any] или обрезать issue. Проверка этого — обязательный gate общей зависимости, а не предположение.

Это **предложение изменения transport-контракта**, а не уже принятое расширение ERROR-CONTRACTS. До согласования владельцем Planning/ERROR-CONTRACTS нельзя реализовать обход через фиктивный checked path, union с импортом Hydrology в Planning, произвольный BaseModel или message JSON. Если владелец выберет иной существующий F07 carrier, D1 и wire ID 328 должны быть пересогласованы до D2.

Reuse RiverRouteDiagnostic предполагает strict revalidation, extra=forbid и сохранение frozen; сохранить его текущие ограничения complete redirected receiver и invalid connection type. Дополнительно проверять INVALID_CONNECTION_TYPE iff reason=INVALID_CONNECTION_TYPE с object_type=None и rejected_connection_type != None; сохранять даже пустую исходную строку, если именно она отклонена. Остальные codes требуют RIVER/MOUNTAIN_RIVER и отсутствия rejected_connection_type. Не вводить требование receiver_level != None: приёмником может быть river bed без уровня. Контекст nullable-полей не ужесточать сверх доказательств callers; receiver_uid/kind/cell для REDIRECTED обязательны уже сейчас.

## 5. Publication и точные предлагаемые bindings

Цепочка: `_diagnostic` → `_emit_diagnostic` → callback diagnostics.append в plan_prepared_routes → PlanBuildResult[RiverRouteBatch] → FineRiverJob._route (копирует diagnostics) → FineRiverPublicationJob.publish (water.diagnostics затем river diagnostics, стабильная дедупликация) → output_fingerprint(payload, dependencies, diagnostics, SURFACE_MANIFEST) → PlanEnvelope[FineRiverPlan]. ERROR здесь отклоняет отдельный intent, а не обязательно весь envelope. Coarse execution объединяет declared/auto причины в том же порядке; публикация через PlanningService использует тот же surface manifest. Алгоритм, refs и disposition policy не менять.

На момент проверки максимальный SURFACE_MANIFEST ID=324. Предложение владельцу surface codec (IDs пока **не зарезервированы кодом**, повторно проверить перед D2):

| ID | Тип | Kind |
|---|---|---|
| 325 | RiverRouteDiagnostic | RECORD |
| 326 | RiverRoutingCode | ENUM |
| 327 | RiverRoutingFailure | ENUM |
| 328 | RiverPlanDiagnostic | RECORD |

Переиспользуются HydrologyMouth=89, HydrologyConnectionType=80, BasinKind=41, PlanDiagnosticDisposition=111, существующие envelope/payload/ref bindings. RiverReceiverKind — существующий union двух enum, отдельный ID ему не нужен. Никакого ID для abstract/Any specialization. Существующие enum values и IDs не перенумеровывать.

Изменение shared carrier может затронуть shape locks даже без изменения полей данных: `OPEN_WATER_SOURCE_SCHEMA_V1` регистрирует PlanDiagnostic=105 и имеет его shape lock. Поэтому совместимость 105 и closure надо предъявить владельцу source/Pack. В этом срезе source-v1 lock и Pack registry не перегенерировать. D2 публикует только surface river envelope; source-v1 compatibility остаётся явным handoff, а изменение существующих field diagnostic bytes запрещено без отдельного решения владельца. Первый mismatch-only digest должен остаться `d632ae06…`.

**Прямые зависимости carrier и следующий consumer.** Помимо planDiagnostic.py нужны planEnvelope.py (PlanBuildResult и PlanEnvelope) и сигнатура planFingerprints.output_fingerprint; общий PlanningService строит ref из result.diagnostics и повторно валидирует envelope через registered contract. Обязательны regressions этой границы, а не только прямой FineRiverPlanner. Обнаружен отдельный downstream gate: `surfacePlanningAssembler.report_surface_diagnostics:178–191` отправляет все non-NOTICE issues в report_issues/resolve_ctx.errors и читает path/message у NOTICE. Он пока рассчитан на field issues и также не различает ERROR/FALLBACK при validate_only. Нельзя просто передать ему RiverRouteDiagnostic или подставить фиктивные path/message. Для выпуска через общий prepare_surface/prepare_geo требуется отдельное решение владельца reporting/ERROR-CONTRACTS: typed operational rejection и typed continuation должны доставляться с сохранением disposition, без записи FALLBACK в блокирующие field errors. В этом D1 boundary ограничена published envelope + codec; runtime/import reporting cutover не объявляется готовым. До такого handoff новый carrier нельзя считать поддержанным всеми surface consumers.

## 6. Приёмка D2 и ожидаемая дельта

1. Две штатные ветви из §1 должны достигнуть опубликованного envelope. Для lake=False — пустые routes и RiverPlanDiagnostic(NO_WATER_BODIES/DRY_MOUTH, ERROR). Для mouth=(8,11) — принятый redirect к lake/(10,11), RiverPlanDiagnostic(REDIRECTED/DRY_MOUTH, FALLBACK), плюс прежняя WaterKindMismatchIssue/FALLBACK из water, в прежнем порядке. Проверить все поля §1, конкретные типы, отсутствие повторной доставки.
2. Табличные проверки всех шести code и четырнадцати reason, отдельно всех четырёх caller sites, initial_failure, empty specs и fallback_reason. Для disposition проверять validate_only/runtime: с receivers validate не перенаправляет, runtime выполняет поиск; source/cycle/no-water приоритеты сохраняются. Не требовать накопления альтернативных причин одного поиска: это зависимые этапы, не независимые field validators.
3. Проверить strict model restore, decode и decode_bounded для RiverPlanDiagnostic и полного envelope. `encode → новый Python process со штатным SURFACE_MANIFEST → decode(PlanEnvelope[FineRiverPlan]) → encode`, побайтное равенство, точные типы cause/code/reason/receiver_kind и всех полей. В дочернем процессе не создавать ad-hoc registry. Проверить output_fingerprint и зависимость fine_water; удаление/замена причины меняет proof. Повторить mixed water+river diagnostics и coarse PlanBuildResult через штатную границу публикации.
4. Негативные wire проверки: неизвестные type ID/code/reason; чужая issue-модель; незаконный carrier; REDIRECTED/ERROR, иной code/FALLBACK, NOTICE; incomplete redirect receiver; потерянная rejected string и невалидный object_type. Round-trip существующего mismatch-only envelope не должен изменить bytes/digest. Проверить hashability/stable dedup и отсутствие revalidation slicing в обоих envelope/build-result.
5. Consumers, читающие RiverRouteDiagnostic.model_validate_json(d.issue.message), перевести на конкретный issue в профильных тестах и прямых river consumers. Не сохранять message JSON как второй контракт ради старых тестов. Runtime/import sink из §2 отдельно не считать исправленным.
6. Исторические эталоны для lake=False (`36204c39…`) и mouth=(8,11) (`a5fcf7d3…`) менять **только после** получения штатных результатов, сравнения с `9ed3bba6` по полям payload/diagnostics/metadata/bindings и двух независимых запусков. Сначала сохранить/сверить payload, затем объяснить каждый новый wire/diagnostic факт. Если поменялся payload — остановить обновление golden до разбора. Первый эталон не трогать.

База из предыдущего отчёта: procedural_refinement — 9 tests, 5 errors, 0 failures; точный исторический метод — 2 errors. После D2 и миграции прямых typed consumers **ожидается** снятие 4 из 5 ошибок: двух subTests и coarse-wet/rejected-parent методов. Ожидаемый остаток группы: 9 tests, 1 error в disabled fine routing (`fine/execution:73`, вне scope), если не обнаружатся следующие барьеры. Child WRONG_BODY в rejected-parent пока не достигнут — его результат подтвердить запуском, не выдавать прогноз за PASS. Число новых тестов D2 учитывать отдельно. Полный geo1 сейчас не повторялся; дельта полного discover не обещается.

Команды D2: адресный historical метод; новая regression `test_kind_mismatch_migration_preserves_historical_river_payload`; `tests.geo1.fine_water.test_kind_mismatch`; `unittest discover -s tests/geo1/procedural_refinement -t . -q`; профильные fine/coarse river и planning carrier/codec проверки. Отдельно предъявить результаты прежних failures, новых тестов и ошибок вне scope.

## 7. Решения для согласования

Принять reuse RiverRouteDiagnostic и существующих enum как operational facts без искусственного checked path; согласовать generic PlanDiagnostic + hydrology-owned RiverPlanDiagnostic и строгий concrete carrier с владельцем Planning/ERROR-CONTRACTS; согласовать surface IDs 325–328 и boundary совместимости с владельцем codec. После этого разрешить D2 только четырёх caller sites общего emitter и необходимых прямых моделей/consumers/tests. Прямые PlanBuildFailure, runtime/import sinks, source/Pack locks и следующий producer не входят. Этот документ не является разрешением на реализацию до принятия D1.
