# GEO · scoped D1: публикация причин river routing

Статус: **D1 готов к согласованию; D2 не разрешён**. Проверка 7 ноября 2026 года, HEAD `4ed02d60`, с существующим рабочим diff. Выбран один контракт ниже; переход source на целевой контракт и production reporting — явные предварительные зависимости, а не варианты реализации. Основание — [разбор river-route digest](geo-river-route-digest-verification.md). Первый эталон `d632ae06…` принятой миграции WATER_KIND_MISMATCH сохраняется. Здесь изменяется только документация.

## 1. Воспроизведение

Из backend, `PYTHONPATH=.;tests`, штатные `tests.geo1.fine_water.test_routing.scenario(**settings)` и `route(inputs, water)`. Факт наблюдался через `sys.settrace` при входе в `_emit_diagnostic`; аргументы, результат и функции не подменялись. Обе ветви воспроизводились при первоначальной подготовке D1 (6 ноября; в текущей редакции повторно проверены код и source gate):

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

Выбранный контракт на согласование. Он требует предварительной миграции shared Planning/source-контракта (§9); неизменность старого shape lock не обещается. River D2 не реализует эту миграцию попутно.

```python
# dataModel/planning/diagnostics/planDiagnostic.py
IssueT = TypeVar("IssueT", bound=BaseModel, default=FieldPathError[Any])  # typing_extensions
class PlanDiagnostic(BaseModel, Generic[IssueT]):
    issue: SerializeAsAny[IssueT]
    disposition: PlanDiagnosticDisposition

# тот же модуль; локальная функция admission, не новый registry/framework
def require_concrete_diagnostic(value: object) -> PlanDiagnostic[Any]: ...
DiagnosticCarrier = Annotated[
    SerializeAsAny[PlanDiagnostic[Any]], PlainValidator(require_concrete_diagnostic)
]

# dataModel/hydrology/riverRouting.py
class RiverPlanDiagnostic(PlanDiagnostic[RiverRouteDiagnostic]): ...
```

В примере `def` — функция уровня модуля. Обе модели сохраняют `extra="forbid", frozen=True, strict=True, revalidate_instances="always"`. Для `RiverPlanDiagnostic.issue` явно повторить аннотацию `SerializeAsAny[RiverRouteDiagnostic]`. Его after-validator допускает только REDIRECTED/FALLBACK и остальные пять codes/ERROR; NOTICE запрещён.

Admission принимает **только уже восстановленные экземпляры**: (а) `type(value) is PlanDiagnostic`, issue — именованный concrete FieldPathError; (б) именованный негeneric subclass PlanDiagnostic с concrete BaseModel-аннотацией issue, без Any/TypeVar/union и без незакрытых generic parameters. Специализации `PlanDiagnostic[Any]`, `PlanDiagnostic[BaseModel]`, bare BaseModel/dict и незарегистрированный wire ID отклоняются. Проверка конкретной issue-модели выполняется самим concrete carrier, не общей таблицей причин. Admission вызывает `type(value).model_validate(value, strict=True)` и проверяет сохранение точного типа; plain-validator исключает последующее generic slicing. Не доверять model_construct: тестами предъявить повторную проверку вложенного fact. Python admission не занимается codec registration; отсутствие binding отклоняет штатный codec. Сырой JSON envelope не становится новым входным протоколом.

Точные поля/сигнатуры прямой границы:

```python
# planEnvelope.py: одинаково в PlanBuildResult[T] и PlanEnvelope[T]
diagnostics: tuple[DiagnosticCarrier, ...]
# planFingerprints.py
def output_fingerprint(payload: object, dependencies: tuple[PlanDependency, ...],
                       diagnostics: tuple[DiagnosticCarrier, ...],
                       manifest: CanonicalSchemaManifest) -> OutputFingerprint: ...
# riverPrepare.py
def _emit_diagnostic(fact: RiverRouteDiagnostic, disposition: PlanDiagnosticDisposition,
                      emit: Callable[[RiverPlanDiagnostic], None] | None) -> None: ...
```

`_emit_diagnostic` сохраняет return None: при callback создаёт ровно один RiverPlanDiagnostic и передаёт его callback; при emit=None ничего не публикует. В `_invalid_type`, `prepare_river_from_inputs`, `prepare_river_requests_from_inputs` заменить **только** тип параметра emit на `Callable[[RiverPlanDiagnostic], None] | None` (defaults сохранить); в `plan_prepared_routes` collector — `list[RiverPlanDiagnostic]`. Остальные параметры и возвращаемые PreparedRiver/PlanBuildResult[RiverRouteBatch] неизменны. Никаких новых универсальных outcome-классов, dispatch-сервисов или registry для diagnostics.

Это **предложение изменения transport-контракта**, а не уже принятое расширение ERROR-CONTRACTS. До согласования владельцем Planning/ERROR-CONTRACTS нельзя реализовать обход через фиктивный checked path, union с импортом Hydrology в Planning, произвольный BaseModel или message JSON. Другие схемы carrier в этом D1 не предлагаются: утверждается именно generic PlanDiagnostic, concrete RiverPlanDiagnostic и DiagnosticCarrier admission.

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

Изменение shared carrier может затронуть shape locks даже без изменения полей данных: `OPEN_WATER_SOURCE_SCHEMA_V1` регистрирует PlanDiagnostic=105 и имеет его shape lock. Поэтому изменение 105 и closure надо предъявить владельцу source/Pack как прямой переход на целевой контракт без legacy reader. В River D2 source-v1 lock и Pack registry не перегенерировать. Предварительный shared Planning/source срез обязан принять новую schema closure и доказать сохранение существующих field diagnostic bytes; его собственный D1 согласуется отдельно. Простая регенерация lock без анализа изменений и проверки целевого round-trip не является завершённым переходом. Первый mismatch-only digest должен остаться `d632ae06…`.

**Прямые зависимости carrier и следующий consumer.** Помимо planDiagnostic.py нужны planEnvelope.py (PlanBuildResult и PlanEnvelope) и сигнатура planFingerprints.output_fingerprint; общий PlanningService строит ref из result.diagnostics и повторно валидирует envelope через registered contract. Обязательны regressions этой границы, а не только прямой FineRiverPlanner. Обнаружен отдельный downstream gate: `surfacePlanningAssembler.report_surface_diagnostics:178–191` отправляет все non-NOTICE issues в report_issues/resolve_ctx.errors и читает path/message у NOTICE. Он пока рассчитан на field issues и также не различает ERROR/FALLBACK при validate_only. Нельзя просто передать ему RiverRouteDiagnostic или подставить фиктивные path/message. Для выпуска через общий prepare_surface/prepare_geo требуется поставка P2 по выбранному контракту §9: typed operational rejection и typed continuation должны доставляться с сохранением disposition, без записи FALLBACK в блокирующие field errors. В этом D1 boundary ограничена published envelope + codec; runtime/import reporting cutover не объявляется готовым. До такого handoff новый carrier нельзя считать поддержанным всеми surface consumers.

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

Принять reuse RiverRouteDiagnostic и существующих enum как operational facts без искусственного checked path; согласовать generic PlanDiagnostic + hydrology-owned RiverPlanDiagnostic и строгий concrete carrier с владельцем Planning/ERROR-CONTRACTS; согласовать surface IDs 325–328 и границу прямого перехода с владельцем codec. После согласования и поставки P1 (§9) разрешить River D2 только четырёх caller sites общего emitter и необходимых прямых моделей/consumers/tests. Прямые PlanBuildFailure, runtime/import sinks, source/Pack locks и следующий producer не входят. Этот документ не является разрешением на реализацию до принятия D1.


## 8. Атомарная карта D2 (не разрешение начать код)

Нормативные ссылки: [ERROR-CONTRACTS §2.4 F03/F07 и scoped D1 gate](error-contracts-1.md), [ТЗ Hydrology](../../docs/tz_terrain_hydrology.md) (river routing и receiver semantics), [ТЗ DAG: контракты Input/Output](../../docs/tz_world_generation_dag.md#контракты-inputoutput-engine-dag-самостоятельный-dag-typing-1), [ТЗ validation](../../docs/tz_json_validation.md). Ни один шаг не меняет алгоритм маршрутизации. Все пути ниже от корня репозитория; команды — из `backend`, после `$env:PYTHONPATH='.;tests'`. Новые test-файлы явно помечены; команды для них запускаются после их создания в D2.

| Шаг / зависимость | Точные файлы и работа | Норма | Команда | Done |
|---|---|---|---|---|
| 0 / принятие D1 | Этот документ: записать решения O1–O3 из §9; снять baseline до изменений | ERROR-CONTRACTS scoped D1 gate | `.\.venv\Scripts\python -m unittest tests.geo1.procedural_refinement.test_proposals -q` | Записаны фактические ошибки и baseline, согласованы O1–O3; исторический прогноз не выдан за результат |
| 1 / 0 | `backend/app/dataModel/planning/diagnostics/planDiagnostic.py`, `backend/app/dataModel/planning/contracts/planEnvelope.py`, `backend/app/application/planning/service/planFingerprints.py`; контракт §4. Расширить `backend/tests/planning/contracts/test_contracts.py` | F03/F07; ТЗ DAG | `.\.venv\Scripts\python -m unittest tests.planning.contracts.test_contracts -q` | Concrete type сохраняется в build result/envelope; bare/Any/forged input отвергается; прежний field carrier работает |
| 2 / 1 | `backend/app/dataModel/hydrology/riverRouting.py`; RiverPlanDiagnostic, strict fact invariants §4; новый `backend/tests/geo1/fine_water/test_river_diagnostics.py` | ТЗ Hydrology; F03/F07 | `.\.venv\Scripts\python -m unittest tests.geo1.fine_water.test_river_diagnostics -q` | Все шесть code, четырнадцать reason, nullable receiver level и пустая rejected string покрыты; неверные пары disposition отклоняются |
| 3 / 2 | `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; четыре bindings §5. Расширить `backend/tests/planning/encoding/test_canonical_codec.py` | ТЗ DAG; §5 данного D1 | `.\.venv\Scripts\python -m unittest tests.planning.encoding.test_canonical_codec -q` | Новый процесс штатно восстанавливает concrete carrier; bounded decode и unknown-ID negatives; binding 105/его bytes сохранены; принят новый source baseline предварительного среза |
| 4 / 3 | `backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py`; четыре sites §2 и callback signatures §4. Расширить новый `backend/tests/geo1/fine_water/test_river_diagnostics.py` | ТЗ Hydrology; F03/F07 | `.\.venv\Scripts\python -m unittest tests.geo1.fine_water.test_river_diagnostics tests.geo1.fine_water.test_routing -q` | ERROR и FALLBACK доходят до collector; без callback сохранены facts; нет двойного emit, алгоритмическая дельта отсутствует |
| 5 / 4 | `backend/tests/test_hydrology_fine_river_planning.py`, `backend/tests/planning/providers/test_planning_service.py`: mixed water/river, fine/coarse publication через штатный service, fingerprint; production service менять не требуется | ТЗ DAG; §5 | `.\.venv\Scripts\python -m unittest tests.test_hydrology_fine_river_planning tests.planning.providers.test_planning_service -q` | Обе ветви §1 опубликованы; порядок/dedup/type сохранены; изменение cause меняет fingerprint; source compatibility предъявлена |
| 6 / 5 | `backend/tests/geo1/procedural_refinement/test_proposals.py`: два JSON-message reader заменить concrete issue; `backend/tests/geo1/procedural_refinement/river_route_golden.json`: только два разрешённых эталона после анализа §6 | ТЗ Hydrology; §6 | `.\.venv\Scripts\python -m unittest tests.geo1.procedural_refinement.test_proposals.ProceduralRefinementTests.test_declared_membership_and_historical_results_do_not_depend_on_segment_flag tests.geo1.procedural_refinement.test_proposals.ProceduralRefinementTests.test_kind_mismatch_migration_preserves_historical_river_payload -q` | Два независимых запуска совпадают; payload неизменен; mismatch-only d632ae06… сохранён; каждая diagnostic/wire дельта объяснена |
| 7 / 6 | Этот документ: фактический отчёт D2; код вне карты не менять без пересмотра scope | ERROR-CONTRACTS D2 gate | `.\.venv\Scripts\python -m unittest discover -s tests/geo1/procedural_refinement -t . -q`; `.\.venv\Scripts\python -m unittest tests.geo1.fine_water.test_kind_mismatch tests.test_hydrology_river_routing tests.test_hydrology_river_round2 -q` | Новые тесты проходят; прежние ошибки и остаток disabled fine routing предъявлены отдельно; production reporting не объявлен готовым |

В §5 bindings означают точные записи `(325, RiverRouteDiagnostic, CanonicalTypeKind.RECORD)`, `(326, RiverRoutingCode, CanonicalTypeKind.ENUM)`, `(327, RiverRoutingFailure, CanonicalTypeKind.ENUM)`, `(328, RiverPlanDiagnostic, CanonicalTypeKind.RECORD)` в существующем SURFACE_MANIFEST. Imports — из `app.dataModel.hydrology.riverRouting`. ID 105 остаётся привязан к **непараметризованному PlanDiagnostic**, а не к новой специализации; изменение его shape принимается предварительным shared Planning/source срезом. Проверить доступность ID перед D2; конфликт требует нового решения O2, автоматического перенумерования нет. `backend/app/application/worldData/generators/hydrology/encoding/sourceSchema.py` — read-only compatibility boundary; изменение shape lock требует отдельного scope. Совместимость plain-validator alias со штатным codec/schema introspection проверяется в предварительном срезе до River D2; отрицательный результат требует пересогласования D1, а не выбора альтернативы в реализации.

## 9. Выбранные зависимости и consumer reporting

### 9.1 Порядок допуска D2

1. Согласовать этот D1: generic carrier/admission §4, River fact, IDs 325–328, envelope-only границу и неизменность runtime.
2. **P1 — shared Planning/source prerequisite**, владелец Planning + source/Pack: реализовать именно §4 для общего carrier, envelope и fingerprint, принять изменение schema closure отдельным согласованным срезом. Старый source-v1 shape не совместим с новой аннотацией; нельзя требовать одновременно нового carrier и неизменного lock. P1 должен предъявить одну целевую source-схему, согласованное обновление lock, перевод всех действующих consumers и round-trip целевого формата. Восстановление прежнего внутреннего source-формата, старый decoder, aliases и двойное чтение не требуются. Fixtures обновляются или пересоздаются; неизменность bytes незатронутых field diagnostics проверяется отдельно от поддержки старого формата. River D2 не стартует на красном baseline или с молчаливой регенерацией lock. Шаг 1 §8 — поставка P1, не повторная независимая реализация River.
3. После P1 — шаги 2–7 §8: River models, registrations, emitter, публикация и тесты. Перед регистрацией повторить проверку свободных IDs. Новые IDs зарегистрировать до переключения emitter.
4. **P2 — production consumer prerequisite**: до включения нового envelope в prepare_captured_bundle/prepare_captured_geo_bundle выполнить отдельный reporting срез по контракту ниже. Envelope-only D2 допускает проверку через PlanningService/FineRiverPublicationJob; это не разрешение выпускать carrier в старый consumer. Нет скрытого feature flag, suppression или fallback на message JSON.

### 9.2 Точный контракт consumer boundary

Текущее `report_surface_diagnostics` дедуплицирует весь carrier, затем передаёт каждый non-NOTICE issue в `report_issues`; NOTICE читает path/code/message. Поэтому текущий consumer **не поддерживает RiverPlanDiagnostic**. `ResolveContext.errors` — это `ResolveReport.issues`; `ResolveReport.diagnostics` — отдельные continuations. Оба принимают только `ImportIssue = FieldPathError[Any] | WireShapeIssue`. Ни `report_issues`, ни `report_continuation` сейчас не являются sink для RiverRouteDiagnostic. Расширять ImportIssue импортом Hydrology запрещено.

Выбрана следующая граница P2: domain-owned collector получает `RiverPlanDiagnostic` целиком, в стабильном порядке первого появления и ровно один раз за report boundary. Его контракт — `Callable[[RiverPlanDiagnostic], None]`; он не возвращает решение маршрутизации и не возбуждает доменный отказ из disposition. Delivery выполняется после routing. Это новый явный hydrology sink, не утверждение о наличии такого API сегодня. Его подключение и lifetime принадлежат отдельному reporting срезу; до поставки P2 production включение запрещено.

| Вход | Доставка и влияние |
|---|---|
| River ERROR | В domain collector как operational rejection уже отклонённого intent; не в ResolveReport.issues; не создаёт новый отказ всего batch |
| River FALLBACK | В тот же collector с disposition=FALLBACK как разрешённое continuation; не в blocking issues; принятые route/specs/drainage сохраняются |
| River NOTICE | Невозможен: отклоняется RiverPlanDiagnostic validator до публикации |
| Field ERROR | Существующий `report_issues`, существующая реакция validate_only сохраняется |
| Field FALLBACK | `report_continuation`; не включается в список для UnresolvedModelError; usable value уже выбран producer |
| Field NOTICE | Информационная доставка существующего field факта; не blocking issue |

P2 маршрутизирует по concrete carrier до обращения к field path/message. Это точное целевое решение, не альтернативы sinks. `collect_only` подавляет logging, но сохраняет сбор; `validate_only` не переклассифицирует уже принятое continuation в ERROR. Разрешённость river fallback определяет только текущий routing: runtime и not validate_only. Consumer не запускает поиск повторно. Сбой диагностической инфраструктуры нельзя маскировать широким catch; изменение propagation требует отдельного согласования.

Файлы **P2, вне River D2**: `backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py` (dispatch и field continuation); новый `backend/app/application/worldData/generators/hydrology/rivers/riverPlanningReporting.py` (domain collector contract); `backend/tests/planning/providers/test_diagnostics.py` (mixed delivery, dedup, runtime/validate_only/collect_only). ResolveReport/ImportIssue не расширяются. Старый `riverRouteDiagnostics.py::emit_river_diagnostic` остаётся отдельным runtime/import handoff и не объявляется исправленным.

#### Проверка контракта P2, 2026-11-08

**Статус — контракт проверен и зафиксирован.** Проверены потребители, доступность результата при возврате и исключении, четыре сочетания флагов контекста и совместимость с field reporting.

**Владелец и время жизни.** Caller операции surface planning владеет одним hydrology collector на запрос. На входе `prepare_captured_bundle` и `prepare_captured_geo_bundle` передаётся явный keyword callback. Он принимает один целый carrier из закрытого объединения семи operational Water source carriers и RiverPlanDiagnostic и возвращает None. Один collector для обоих семейств сохраняет их взаимный порядок. Конкретный request-owned collector предоставляет caller упорядоченный tuple принятых carriers. Минимальный контракт использования: caller создаёт collector до capture/prepare, передаёт его метод при подготовке и читает tuple после вызова, в том числе после field validation refusal. Ссылку удерживает caller. Локальная переменная, исчезающая внутри prepare, этому контракту не удовлетворяет.

**Проводка.** Передать collector через `SurfacePlanningEntry.prepare_captured`, `require_plan_inputs` и `require_plan_bundle` до lower-level callback. Runtime map/read/bake callers создают его на границе своей операции; callers, передающие режим сбора, передают свой экземпляр по всей цепочке. Сохранить существующие формы результатов: bundle/None, (bundle, working)/None и исключения. Для доступности отчёта не требуются новый HTTP response, внешний storage, поле в cached envelope или зависимость jsonValidation от Hydrology. В карте реализации учесть три вызова в api/routes/map.py, wildernessRegionReadService, L0 и detailed materialization. У GEO helper в этом checkout найдены integration/typing callers; модули app пока не вызывают его напрямую. Оба helper входят в приёмку. `probe_extent` обрабатывает только field capture diagnostics; тип capture view остаётся прежним.

**Dispatch до обращения к issue.path/message.**

| Факт на границе | Доставка и исход |
|---|---|
| Семь concrete Water source carriers, включая WaterWorldOcean NOTICE | Передать collector с исходной disposition. Water ERROR в опубликованном upstream envelope описывает решение producer. Право Fine Water на публикацию остаётся у существующей границы отказа. |
| River ERROR / FALLBACK | Передать тому же collector; частичный результат и принятые маршруты сохраняются. River NOTICE отвергает DTO. |
| Exact field PlanDiagnostic, включая WaterKindMismatchIssue | ERROR → report_issues; FALLBACK → report_continuation; NOTICE → прежняя информационная доставка, если collect_only выключен. В UnresolvedModelError при validate_only включаются только field ERROR этого прохода. |
| WaterPlacementRequiredDiagnostic | Runtime-only факт прямого apply. В контракт source callback не входит. |

Оба режима validate_only и collect_only сохраняют operational facts у владельца. Collect_only подавляет логирование; сам вызов collector остаётся обязательным. Механизм локального Water report из S4 имеет собственную field policy и не заменяет dispatch на этой границе. P2 не требует повторного runtime emit в producer. Сбой callback распространяется как сбой доставки. Исход доменной операции по типу или тексту сообщения повторно не вычисляется.

**Порядок, повторы, отказы.** Обход capture → восемь PC / двенадцать GEO фаз в существующем порядке, внутри envelope — исходный порядок. На одном проходе дедуплицируется полный carrier до dispatch. Один и тот же request-owned collector сохраняет только первое появление равного carrier и при повторе в рамках запроса. Новый запрос со своим collector получает факты и при cache HIT. При успешном build с field ERROR сначала обработать остальные независимые факты, затем применить validate_only refusal. Если сам build поднял PlanBuildFailure до возврата bundle, сохранить исходное исключение и его diagnostics, без replay частично построенных фаз. NO_EXTENT возвращает None после обработки capture facts; в штатном capture operational фактов нет.

**Доказательства до фиксации.** На неизменённом коде проверены пары (validate_only, collect_only) = (0,0), (1,0), (0,1), (1,1). Два одинаковых WaterWorldOcean дают AttributeError при collect_only=False, при collect_only=True возвращается управление и факт теряется при доставке. Реальные River NO_WATER_BODIES и REDIRECTED из scenario/route во всех четырёх случаях дают ValidationError на ImportIssue. Реальный WaterKindMismatch попадает в ctx.errors и при validate_only поднимает UnresolvedModelError. Отдельный вызов report_continuation дважды на том же mismatch во всех четырёх случаях даёт 0 ошибок и 1 continuation. Это baseline до P2.

Проверка предлагаемой проводки в отдельном Python-процессе: на время теста подменён только report_surface_diagnostics наблюдающим dispatcher для фактически предъявленных типов. PC-тест test_pipeline_supplies_pre_river_elevation_to_fine_profiles прошёл со своими численными проверками и передал один WaterWorldOcean NOTICE. Для GEO в fixture GeoBundleReportingTests в relief переданы (ocean, mismatch), в hydrology_routes — (ocean, redirect). Получен GeoSurfacePlanBundle, collector содержит (ocean, redirect) по одному, field report содержит 0 errors / 1 continuation. Это проверяет совместимость предлагаемой доставки с реальными формами вызовов; полный dispatcher и владение collector должны быть реализованы и проверены отдельно.

Повторяемый baseline из backend:

```powershell
$env:PYTHONPATH='.;tests'
.\.venv\Scripts\python.exe -m unittest tests.test_hydrology_hy12_rivers.RiverWaterlineTests.test_pipeline_supplies_pre_river_elevation_to_fine_profiles tests.geo1.integration.test_revisions.GeoBundleReportingTests tests.planning.consumers.test_request_boundary tests.planning.providers.test_diagnostics -q
```

14 тестов, 8 errors. Один — WaterWorldOcean.path, семь — базовый FieldPathError (один через PlanProviderFault). Для P2 обновить конкретные field fixtures и ожидания FALLBACK в GeoBundleReportingTests, сохранив проверки причин и всех фаз. После реализации обязательна независимая приёмка на обоих entry point: mixed ERROR/FALLBACK/NOTICE, два запроса и cache HIT, повтор в одном контексте, оба флага по отдельности и вместе, NO_EXTENT, отказ до bundle и validate refusal после сборки. Проверить также normal production caller и typing fixtures. Вердикт по выпуску выносится по реализации.

### 9.3 Проверка текущего checkout и приёмка зависимостей

7 ноября повторён `require_source_schema_v1()` из backend: **FAIL**, `CanonicalEncodingError: open-water source v1 closure drift`. Это существующий baseline до правок документа. Исходники подтверждают: `_snapshot` учитывает annotations/metadata; PlanDiagnostic=105 входит в source closure, envelope=60008. IDs 325–328 в SURFACE_MANIFEST свободны (max=324). Generic carrier, новые validators и round-trip ещё не реализованы и не тестировались; прежние числа тестов §6 — исторические, не новый PASS.

Команды из `E:\AI Project\backend`, сначала `$env:PYTHONPATH='.;tests'`:

```powershell
.\.venv\Scripts\python -c "from app.application.worldData.generators.hydrology.encoding.sourceSchema import require_source_schema_v1; require_source_schema_v1()"
.\.venv\Scripts\python -m unittest tests.spatial_pack.test_source_schema tests.planning.providers.test_diagnostics tests.planning.encoding.test_canonical_codec -q
```

После P1 эти проверки должны пройти на принятом baseline; затем команды River D2 в §8. Для P2 обязательна матрица всех трёх dispositions и режимов, проверка отдельно issues/diagnostics/domain collector, отсутствия повторной доставки и неизменных результатов маршрутизации. ERROR другого intent не удаляет принятый redirect. Characterization сравнивает routes, receiver, specs, drainage, порядок обработки и продолжение следующего независимого intent; новый fingerprint объясняется только diagnostic bytes.

**Предмет согласования:** принять выбранные контракты и порядок P1 → River D2 → production gate P2. Согласование D1 не означает готовность P1/P2, не разрешает менять runtime и не объявляет текущие consumers совместимыми. Эта задача заканчивается на согласовании D1; код, locks, registrations и golden не меняются.

## Инвариант миграции диагностики: runtime не меняется (2026-11-06)

**Прямое требование пользователя, обязательное для error/logging треков этого домена:** новые типы ошибок, доменные адаптеры, collectors, события и logging integrations не должны переписывать текущую логику runtime. Условия fallback и продолжения обработки не меняются.

- Сохраняются существующие условия допустимости default/None, fallback и выбора альтернативного результата, продолжения batch/независимых проверок, отказа и распространения исключения. Нельзя ужесточать или ослаблять их из-за нового типа диагностики, severity, наличия лога или удобства нового адаптера.
- Сохраняются вычисленные значения/UID, порядок и условия доменных действий, права на запись, commit/rollback, cancellation и retry. Диагностика отражает фактический исход; не становится новой причиной выбора исхода.
- В POJO/import-цепочках переиспользуются ResolveContext/ResolveReport: blocking issues и continuations не смешиваются; collect_only меняет только эмиссию, а validate_only сохраняет принятую политику соответствующего режима. Разрешённое runtime-продолжение не превращается в blocking error после миграции.
- До переключения producer закрепить characterization текущих сценариев: обычный успех, штатный default/None, разрешённый fallback/continuation, blocking отказ и независимая последующая обработка. После переключения сопоставить значения, эффекты и outcome; допустимы только согласованные изменения формы/доставки диагностики. Изменение диагностики в fingerprint проверяется отдельно и не оправдывает изменение доменного payload/маршрута.
- Исправление сломанного конструктора диагностики должно восстановить уже предусмотренную ветвь, а не сохранять случайный TypeError как доменную политику. Где текущая поломка мешает получить результат, evidence берётся из утверждённого доменного контракта, фактов до сбоя и адресных тестов; новый fallback не придумывается.
- Если для реализации требуется изменить runtime-условие, это **отдельный явно согласуемый поведенческий срез**: зафиксировать расхождение и остановить зависимую правку. Не вносить его попутно под названием error migration или logging. Отрицательная проверка нового диагностического контракта не расширяет область перехвата операционных ошибок.

Приёмка каждого затронутого шага включает evidence сохранения runtime-семантики. Это ограничение миграции ошибок и логов, а не запрет ранее согласованной самостоятельной функциональной разработки домена. Статус реализации и пользовательская приёмка этим пунктом не изменяются.


## Решение пользователя: без legacy-компонентов — 2026-11-07

### Проверка допуска Planning/source P1 после команды «Делай»

Повторён исходный набор из §9.3 без изменений production-кода: `tests.spatial_pack.test_source_schema tests.planning.providers.test_diagnostics tests.planning.encoding.test_canonical_codec` — **24 tests, 11 errors, 5 failures**. Это baseline, не результат реализации. Отказ от legacy принят, но не определяет отсутствующие доменные причины.

Фактическая closure текущего source отличается от lock: появились ValidatedFieldPath, ModelIdentity, FieldSegment, IndexSegment, KeySegment, VariantSegment и FieldPathError[Any]; прежние FieldPathError, ReferenceIssueContext, ReferenceIssueReason, RuntimeIssueContext и Facing из неё не достигаются. Из общих зарегистрированных записей изменился shape PlanDiagnostic (105). Регистрировать абстрактный FieldPathError[Any] вместо конкретных причин нельзя.

Дополнительный обязательный freeze до целостного P1: целевой набор concrete water diagnostics и их codec bindings. `water/waterDiagnostics.py::water_issue` продолжает создавать базовый FieldPathError со строковым code и tuple path; `encoding/sourceSchema.py::require_source_diagnostics_v1` требует именно базовый тип и прежние reference/runtime_context/schema_id. Единственный уже реализованный concrete water issue — WaterKindMismatchIssue (surface IDs 323/324); он не заменяет WATER_LEVEL_SPILL, WATER_CANNOT_HOLD и прочие причины. Их поля/семейства и registrations текущим River D1 не определены, а миграция других water producers явно вне River D2.

Поэтому P1 целиком пока BLOCKED на domain freeze, а не на поддержке legacy. Не заменять все причины WaterKindMismatchIssue, не возвращать старый FieldPathError и не удалять проверки source/Pack. До определения concrete source diagnostics не менять shared carrier отдельно так, будто source cutover завершён. Независимый Time TL-1…TL-3 выполняется. Production reporting P2 остаётся отдельной границей.

Reuse принятого смысла WATER_LEVEL_SPILL: [GEO owning-план](geo-1-designed-water.md#L16088) уже определяет владельца resolve_water_levels и факт UID источника + запрошенный уровень + уровень после ограничения по spill; окончательный уровень после физического объединения не подменяет spill-level. Требуется freeze конкретного DTO/enum, переноса producer→materializer→carrier и bindings, а не новое решение об алгоритме перелива.

Для текущего перехода внутренних error/logging и Planning/source контрактов используется один целевой контракт. Не создавать старые декодеры, compatibility adapters/re-exports, двойные readers или параллельные версии компонентов. Действующих потребителей переводить вместе с контрактом; тестовые fixtures обновлять или пересоздавать. Суффикс v1 сам по себе не означает legacy и не требует ни поддержки старого формата, ни косметического переименования.

Для Planning/source P1 проверяются целевая schema closure, явный diff lock, encode/decode и согласованность fingerprint; поддержка прежнего внутреннего source wire не является критерием Done. Изменения bytes объяснять, а не скрывать регенерацией эталонов. Runtime, условия fallback и продолжение обработки сохраняются.

Это решение не отменяет отдельное требование docs/tz_world_snapshot.md §20 к читаемости snapshot-оболочек и доменных секций. Если переход затрагивает именно эту границу, отдельно показать пересечение; не распространять её автоматически на внутренние контракты движка. Код и сохранённые пользовательские данные этой документальной правкой не удаляются. Остальные gates согласования и реализации сохраняются.

### Проверка River в S4, 2026-11-08

Для lake=False и mouth=(8,11) историческая ревизия 9ed3bba6 и два свежих процесса S4 дали одинаковые payload digest соответственно 757adfe9… и 38927c0d…. Для первого результата типизированный NO_WATER_BODIES/DRY_MOUTH сохраняет ERROR и failure_cell=(11,11). Для второго за Water mismatch следует REDIRECTED/DRY_MOUTH с FALLBACK и receiver lake/(10,11). Исторический JSON причины в field issue заменён RiverPlanDiagnostic. Digest пары payload/diagnostics обновлён с 36204c39… до cf066fb1… и с a5fcf7d3… до 8cc13ee8…. Mismatch-only golden d632ae06… проходит. Mixed envelope восстановлен bounded reader в свежем процессе и повторно закодирован побайтно. Проверены redirect и validate rejection через PlanningService. Procedural refinement discover — 9 тестов, 1 исходный error в disabled fine routing. [Приёмка локального S4 и отдельная граница P2](geo-water-diagnostics-source-d1.md#s4--реализация-перед-независимой-приёмкой-2026-11-08).

### Production reporting P2 — исправление замечания 1, 2026-11-08

Первой командой из `backend` на ревизии `45c187b0` воспроизведено падение на валидном WaterWorldOcean NOTICE.

```powershell
.\.venv\Scripts\python -m unittest tests.test_hydrology_hy12_rivers.RiverWaterlineTests.test_pipeline_supplies_pre_river_elevation_to_fine_profiles -q
```

```text
Traceback (most recent call last):
  File "E:\AI Project\backend\tests\test_hydrology_hy12_rivers.py", line 159, in test_pipeline_supplies_pre_river_elevation_to_fine_profiles
    _, working = SurfacePlanningEntry(composition.assembler, SurfacePlanningCapture()).require_plan_inputs(
                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        source, [], wait=RequestPlanWait.unbounded())
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\AI Project\backend\app\application\worldData\planning\composition\surfacePlanningEntry.py", line 95, in require_plan_inputs
    result = self.prepare_captured(view, world=world, wait=wait, resolve_ctx=ctx)
  File "E:\AI Project\backend\app\application\worldData\planning\composition\surfacePlanningEntry.py", line 67, in prepare_captured
    bundle = prepare_captured_bundle(view, planning=self._planning, wait=wait, resolve_ctx=resolve_ctx)
  File "E:\AI Project\backend\app\application\worldData\planning\composition\surfacePlanningAssembler.py", line 158, in prepare_captured_bundle
    report_surface_diagnostics(diagnostics, resolve_ctx=resolve_ctx)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "E:\AI Project\backend\app\application\worldData\planning\composition\surfacePlanningAssembler.py", line 188, in report_surface_diagnostics
    item.issue.path, item.issue.code, item.issue.message)
    ^^^^^^^^^^^^^^^
  File "E:\AI Project\backend\.venv\Lib\site-packages\pydantic\main.py", line 1042, in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
AttributeError: 'WaterWorldOcean' object has no attribute 'path'
```

После исправления та же команда проходит (1 test, OK). Тест проверяет единственный WaterWorldOcean у caller, coarse beds, fine overrides и передачу pre-river surface в fine planner.

Методы SurfacePlanningAssembler.prepare_captured_bundle и prepare_captured_geo_bundle вызывают соответствующую сборку и передают факты в surfaceDiagnosticReporting. Модуль reporting также обслуживает field-only probe_extent. Оба метода принимают обязательный keyword `on_hydrology`. Три map route, outline read, L0, detailed materialization и smoke создают collector до capture. `SurfacePlanningEntry` передаёт его метод по всей цепочке. Свойство `facts` возвращает tuple в порядке первого появления. Dispatch принимает семь operational Water carriers и RiverPlanDiagnostic. Field ERROR поступает в errors, FALLBACK — в continuations, NOTICE — в INFO при выключенном collect_only. После обхода validate refusal содержит только field ERROR текущего прохода. WaterPlacementRequired остаётся в прямом apply.

В интеграционном тесте обоих helper на реальных PlanningService и cache проходят четыре сочетания флагов. Каждый запрос дважды читает те же фазы. Проверены порядок Water NOTICE → River FALLBACK → Water ERROR → River ERROR, дедупликация до вызова callback, первый факт при повторной доставке в тот же collector, доставка на HIT новому collector, доступность полного tuple после field refusal и идентичность исключения при сбое callback или PlanBuildFailure. GEO проверяет все двенадцать фаз и NO_EXTENT. У исходного River-теста сохранились проверки маршрутизации. Логика build, cache и публикации не менялась.

Команды из `backend`:

```powershell
$env:PYTHONPATH='.;tests'
$py='.\.venv\Scripts\python'
& $py -m unittest tests.test_hydrology_hy12_rivers.RiverWaterlineTests.test_pipeline_supplies_pre_river_elevation_to_fine_profiles tests.planning.consumers.test_hydrology_reporting tests.geo1.integration.test_revisions.GeoBundleReportingTests tests.planning.consumers.test_request_boundary tests.geo1.fine_water.test_river_diagnostics -q
& $py -m unittest tests.test_wilderness_region_index.OutlineReadBoundaryTests -q
& $py -m unittest discover -s tests/planning/consumers -t . -q
& $py -m unittest tests.geo1.integration.test_revisions.GeoBundleReportingTests tests.planning.consumers.test_request_boundary tests.planning.providers.test_diagnostics -q
& $py -m unittest tests.geo1.integration.test_revisions.GeoCapturedAssemblerTests tests.test_hydrology_hy12_rivers tests.test_relief_objects_z tests.test_water_placement_pass -q
```

- Целевой набор — 15/15. Outline read через штатный caller — 6/6.
- Surface consumers — 82/87 против 80/85 на исходной ревизии. Совпадают все пять ошибок: четыре в climate registry при неизвестном профиле и одна в water placement adapter при projection collapse (базовый FieldPathError). Асинхронные тесты запущены с доступом к локальному socketpair Windows.
- GEO reporting + request boundary + provider diagnostics — 12/13. В обоих checkout cacheService._failure при имитации отказа cache backend конструирует базовый FieldPathError.
- GEO assembler + HY-12 rivers + relief + Water placement — 31/34. Те же три ошибки Water placement воспроизведены на исходной ревизии в обоих сценариях world_test_004 и в declared projection collapse. Причина — конструирование базового FieldPathError до передачи bundle.

Pyright 1.1.414 запускался из корня checkout с одним интерпретатором backend для исходной ревизии и рабочей копии. Список для исходной ревизии содержит семь существовавших файлов. Рабочий список содержит также collector и модуль reporting.

```powershell
$py=(Resolve-Path backend/.venv/Scripts/python.exe).Path
$files=@(
    'backend/app/api/routes/map.py'
    'backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py'
    'backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py'
    'backend/app/application/worldData/pack/read/wildernessRegionReadService.py'
    'backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py'
    'backend/app/application/worldData/planning/composition/surfacePlanningEntry.py'
    'backend/scripts/smoke_hydrology_hy12.py'
    'backend/app/application/worldData/planning/composition/hydrologyDiagnosticCollector.py'
    'backend/app/application/worldData/planning/composition/surfaceDiagnosticReporting.py'
)
node node_modules/pyright/index.js -p pyrightconfig.cascade.json --pythonpath $py --outputjson $files
node node_modules/pyright/index.js -p pyrightconfig.cascade.json --pythonpath $py --outputjson backend/tests/typing/planning/valid/terrain/geoPipeline.py backend/tests/typing/planning/valid/surface/composition.py
node node_modules/pyright/index.js -p pyrightconfig.cascade.json --pythonpath $py --outputjson backend/tests/typing/planning/invalid.py
```

После переноса методов целевой набор прошёл повторно (15/15). Pyright на восьми модулях app дал 0 ошибок. В smoke_hydrology_hy12.py остались 89 исходных reportArgumentType. У положительных typing fixtures 0 ошибок. У отрицательной 297 диагностик. Для вызова GEO-метода у PC assembler ожидаемая диагностика изменилась с reportArgumentType на reportAttributeAccessIssue: Pyright проверяет семейство через тип self.
