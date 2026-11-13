# SourceDurableProof для Pack: конкретный проект контракта

Дата: 2026-11-13. Статус: PROPOSED, не принят пользователем, код не разрешён этой записью. Документ конкретизирует отдельный контракт, а не реализацию всей Source migration. Основания: [Source design](world-source-versioning.md), [Source appendix](source-proof-v2-contract-spec.md), [Pack SoT](../../docs/tz_world_pack_storage.md), [обязательная приёмка](../rules/dag-generator-interface.mdc).

## 1. Решение, требующее принятия

**Результат повторной проверки:** [Source/Pack DAG review](source-pack-dag-contract-review.md) выявило блокирующие R1–R6. В частности, single-capture схема ниже не покрывает metadata из pinned base и новых входов, а results проверки/closure не имеют полного Pack input mapping. Схема остаётся кандидатом для исправления; начинать её реализацию до устранения этих находок нельзя.

**Уточнение пользователя:** Source — вспомогательный модуль, не отдельный полноценный домен CRUD. Порядок поставки, legacy callers и условия переключения вынесены в [отдельный план перехода](source-module-transition.md). Владельцы исходных данных сохраняют их revisions/CRUD, Artifacts/publication — физическое хранение и удержания. Предлагаемые пути sourceVersioning пока не приняты как окончательное размещение. Упоминания общей Source migration ниже обозначают внешние зависимости, а не scope этого модуля.

SourceDurableProof — immutable значение: точный ref завершённого Source capture и позиции фактически прочитанных object/collection revisions внутри него. Сам capture хранится в существующем Artifacts; новый proof artifact, blob store, receipt или Pack DTO не вводится. Capture содержит стабильные канонические массивы объектов и коллекций. Позиция имеет смысл только вместе с полным capture ArtifactRef; это не identity Source-объекта и не замена SourceVersionRef.

Это новое **предложение представления**, а не ранее принятое решение. Оно позволяет отделить схему proof от полного SourceObjectId union. Proof требует owning capture format и verifier; произвольный ArtifactRef без проверки формата и содержимого не принимается.

Выбран консервативный closure: сохранять полный capture и все исторические тела, необходимые для разрешения его содержимого. Dependencies остаются точным подмножеством реально использованных входов. Избыточное удержание не превращает непрочитанные записи в dependency. Оптимизация до closure только выбранного subset — вне среза, требует другого согласованного правила доказательства membership. Стоимость полного capture closure и размер manifest необходимо измерить до runtime acceptance.

## 2. Точная схема POJO

Все перечисленные модели — Pydantic BaseModel с ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always"). Все поля обязательны, defaults отсутствуют. Tuple вместо list; mutable values, dict, Any, Python class, codec, lease, storage handle в полях запрещены.

Публичный импорт: `from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof`. Ниже определение проекта, runtime файла пока нет.

| Модуль под app.dataModel.sourceVersioning | Тип | Все поля |
|---|---|---|
| sourceCaptureRef.py | SourceCaptureRef | `world_uid: EntityUid`, `artifact: ArtifactRef` |
| sourceCaptureSelection.py | SourceCaptureSelection | `object_indices: tuple[StrictInt, ...]`, `collection_indices: tuple[StrictInt, ...]` |
| sourceDurableProof.py | SourceDurableProof | `capture: SourceCaptureRef`, `selection: SourceCaptureSelection` |
| sourceProofRequests.py | SourceProofVerifyInput | `expected_capture: SourceCaptureRef`, `proof: SourceDurableProof` |
| sourceProofRequests.py | SourceProofClosureInput | `proof: SourceDurableProof` |
| sourceProofResults.py | SourceProofVerification | `proof: SourceDurableProof` |
| sourceProofResults.py | SourceProofClosure | `proof: SourceDurableProof`, `refs: tuple[ArtifactRef, ...]` |

Отдельный SourceProofCreateInput отклонён при проверке: он полностью совпадал бы с SourceDurableProof. Для create использовать непосредственно SourceDurableProof как заявленное значение; успешная проверка возвращает SourceProofVerification. SourceProofVerification — результат успешной операции, а не автономный security token: caller может сконструировать POJO, поэтому на границе доверия требуется owning проверка. Временная валидность holds не кодируется bool внутри proof.

Переиспользуются `EntityUid` из `app.dataModel.identity.uid`, `ArtifactRef` из `app.dataModel.artifacts.references`. В SourceCaptureRef world_uid даёт публичную world boundary и обязательно сравнивается с содержимым capture; не становится вторым источником истины.

### Ошибки

Модуль `sourceProofErrors.py`, владелец Source:

- `SourceProofOperation(StrEnum)`: CREATE, VERIFY, COLLECT_REFS.
- `SourceProofFieldCode(StrEnum)`: INVALID_VALUE, NEGATIVE_INDEX, DUPLICATE_INDEX, NON_CANONICAL_ORDER, WRONG_CAPTURE_FORMAT.
- `SourceProofFieldIssue(FieldPathError[SourceProofFieldCode])`: наследует ровно `code`, `path: ValidatedFieldPath`, `message: StrictStr`. Сам FieldPathError не клонируется.
- `SourceProofLogicCode(StrEnum)`: CAPTURE_MISMATCH, WORLD_MISMATCH, CAPTURE_NOT_FINALIZED, INDEX_OUT_OF_RANGE, CAPTURE_CONTENT_INVALID, BODY_MISSING, BODY_CORRUPT, BODY_UNSEALED, UNSUPPORTED_CAPTURE_SCHEMA, INCOMPLETE_CLOSURE.
- `SourceProofLogicIssue`: `code: SourceProofLogicCode`, `path: ValidatedFieldPath`, `related_ref: ArtifactRef | None`. Все поля обязательны, None допустим только когда ошибка не относится к конкретному artifact. expected/actual не копируются: вход операции уже содержит сравниваемые значения; path указывает несовпадение.
- `SourceProofFailure`: `operation: SourceProofOperation`, `field_issues: tuple[SourceProofFieldIssue, ...]`, `logic_issues: tuple[SourceProofLogicIssue, ...]`. Хотя бы один tuple непустой. Field issues описывают форму входа, logic issues — разрешение и семантическое соответствие валидного входа; один дефект не выдаётся в обоих доменах.

Exception adapter не является POJO и не попадает в wire. Методы возвращают success | SourceProofFailure. Ошибки соединения, SQL и неизвестный outcome не преобразуются в BODY_MISSING. Ошибки удержаний принадлежат отдельному existing Artifacts/adoption контракту, не дублируются в SourceProofLogicCode.

## 3. Валидация и канонизация

1. Revalidate все вложенные модели. Bool не принимается как index. Индексы неотрицательны, уникальны и строго возрастают отдельно в каждом tuple. Нормализатор может сортировать только после диагностики duplicates с исходными путями. Пустые tuples разрешены: они означают заявленное отсутствие чтений, а не автоматически доказанную полноту producer dependencies.
2. Capture ref допускает только BLOB owning Source capture format. Предлагаемые registration values: `source.capture.json`, format_version=1; новые значения требуют регистрации в Artifacts и принятия capture schema. Arbitrary BLOB, Source body artifact и Planning artifact не принимаются как capture.
3. Capture bytes должны соответствовать полному ArtifactRef, world_uid, версии schema, finalized capture representation и каноническому owning codec. Source capture не может ссылаться на latest, mutable SQL row или transient session. Финализация должна быть подтверждаема durable состоянием, а не caller boolean.
4. Каждый индекс находится в границах своего массива. Object index не адресует collection. В capture запрещены две revisions одной identity, неоднозначные duplicates и несовместимые body mappings. Membership восстанавливается из точного collection body, включая семантически значимый порядок и authored-presence.
5. VERIFY сравнивает весь expected_capture с proof.capture. Совпадение hash при другом world/format/version/nbytes не достаточно. Latest не читается и не сравнивается.
6. COLLECT_REFS возвращает root capture artifact и полный транзитивный owning Source closure. Циклы/неразрешимые ссылки дают отказ, а не частичный успех. Refs уникальны по полному ArtifactRef, сортировка по canonical encoding существующего ArtifactRef. Все children должны быть sealed и проверены по owning формату; нет предположения, что любой ref внутри произвольного JSON — dependency.
7. Нельзя вернуть пустой closure даже для пустой selection: capture artifact обязателен. Pack не повторяет traversal и не сортирует поля source proof самостоятельно.
8. Fingerprint proof вычисляется общим CanonicalCodec по зарегистрированным schema entries всех перечисленных records/enums. Отдельное поле proof_hash не хранится. Numeric canonical type IDs и storage schema vectors необходимо выделить без конфликтов с действующим manifest до реализации codec; данный документ не выдумывает свободные IDs.
9. Независимые field errors собираются существующим ValidatorAggregationHelper; после нарушенного предусловия пропускается только зависимая проверка. Это specification проверки, не утверждение о готовности Pydantic error translation.

## 4. Конкретный публичный API и границы

Предлагаемый concrete класс `SourceProofReadPipelineOpenPipeline`, модуль `app.application.sourceVersioning.sourceProofReadPipelineOpenPipeline`. Интерфейс `ISourceProofReadPipelineOpenPipeline` в `app.application.sourceVersioning.interfaces.sourceProofReadPipelineOpenPipeline` имеет те же сигнатуры:

```python
def create(self, request: SourceDurableProof) -> SourceProofVerification | SourceProofFailure: ...
def verify(self, request: SourceProofVerifyInput) -> SourceProofVerification | SourceProofFailure: ...
def collect_refs(self, request: SourceProofClosureInput) -> SourceProofClosure | SourceProofFailure: ...
```

CREATE создаёт проверенное значение proof из заявленного selection существующего finalized capture; не создаёт capture или revisions и не пишет artifact. VERIFY проверяет принадлежность именно ожидаемому capture. COLLECT_REFS полностью разрешает Source closure. Каждая операция имеет единый request/result/error, read-only эффекты и линейную локальную реализацию; одна публичная операция не вызывает другую. Повторные локальные проверки реализуются внутренним helper, а не nested public pipeline.

Вызывающая сторона — непосредственно согласованная DAG-нода, ещё не назначенная пользователем. Result возвращается DAG; DAG переносит proof в PackStoredProvenance.source_proof, closure result — в согласованный Pack admission input. Последний точный consumer field ещё не принят: запрещено выдавать этот маршрут за готовый binding. Pack не вызывает этот публичный Source API. HTTP routes этим срезом не вводятся.

### Ответственность классов реализации

| Класс / модуль под app.application.sourceVersioning | Ответственность, зависимости и эффекты | DoD / основание отказа |
|---|---|---|
| SourceProofReadPipelineOpenPipeline / sourceProofReadPipelineOpenPipeline.py | Одна запрошенная read операция; зависит от внутреннего validator и read binding. Не выбирает следующую публичную операцию | Точный result либо typed failure; отказ при запуске producer/Pack/capture/latest-read |
| SourceProofValidator / proof/sourceProofValidator.py | Чистые проверки полей и decoded capture, selection bounds и world binding; зависит от Source POJO и ошибок | Нет IO, writes, orchestration; отказ при самостоятельном получении missing inputs |
| SourceProofClosureCollector / proof/sourceProofClosureCollector.py | Локальное вычисление полного графа refs из owning decoded capture/body records; зависит от внутреннего read binding | Полный детерминированный refs tuple; отказ при частичном success или чтении произвольных чужих JSON |
| SourceProofReadBinding / proof/sourceProofReadBinding.py | Exact immutable read и owning decode в стабильной внутренней read boundary; зависимости — принятый scoped storage binding и capture codecs | Нет latest fallback, публичного междоменного pipeline или нового blob store; конкретный storage adapter требует приёмки до runtime |

POJO из §2 только хранят и структурно проверяют данные. ArtifactRef не отвечает за удержания, SourceCaptureSelection не отвечает за object identity, SourceDurableProof не доказывает выполнение producer, verification result не заменяет lease. Эти границы являются критериями отказа по каждому соответствующему классу.

## 5. Durability и атомарная передача удержаний

Вызов COLLECT_REFS доказывает состав на момент чтения, но не владение refs после возврата. Transient Source capture hold и durable Pack version hold — разные вещи. OperationLeaseRef/ArtifactHolderRef не сохраняются в SourceDurableProof.

При подготовке/активации полный refs set проверяется и удерживается через принятый внутренний scoped adoption binding в одной commit boundary: проверка seal и исходного live holder → приобретение destination holds → освобождение передаваемого исходного hold → commit. Предварительно полученный SourceProofVerification не разрешает пропустить эту проверку. Два независимых удержания одинакового capture освобождаются независимо. Ни фиктивный PinHolder, ни self-hold capture root не предлагаются.

Точная публичная/внутренняя сигнатура adoption определяется владельцем Artifacts/publication; существующий ArtifactRetentionHolder(artifact) годится для children, но сам по себе не доказывает root lifetime. Это конкретный **runtime blocker**, не причина оставлять SourceDurableProof без полей. До закрытия seam интегрированный Pack путь не принимается. SourceProofFailure не зеркалит ошибки Artifacts.

## 6. Сверка PackStoredProvenance и отсутствие зеркал

`PackStoredProvenance(source_proof: SourceDurableProof, planning: tuple[PlanDependency, ...])` сохраняется без новых полей. PlanDependency используется из `app.dataModel.planning.contracts.planDependency`, canonical slot validation сохраняется. Source proof не включает Planning dependencies.

Новая часть: owning producer сообщает selection реально использованных входов, Source проверяет capture/selection, DAG переносит owning результат в Pack. Полноту чтений и связь address/artifact с результатом вычисления подтверждает producer binding; она не выводится из hash или двух caller-копий proof. Нельзя объявить весь producer route закрытым данным контрактом.

Наследуемая часть: Pack сверяет address/artifact/полный provenance с pinned base, сохраняет прежний proof; expected_capture текущей подготовки к ней не применяется. COLLECT_REFS принимает сохранённый proof без текущей session. Новый manifest удерживает closure независимо от старого. Один ref на двух адресах сохраняет два provenance use, даже если GC refs дедуплицированы.

Metadata: тот же proof указывает Source reads, а producer binding отдельно подтверждает конкретную semantic projection. Source не импортирует Pack address или metadata DTO.

Отличие от существующих моделей: SourceCaptureRef — typed ref одного finalized capture, ArtifactRef — универсальная content identity; selection — локальные позиции этого capture, SourceDependencySet — owning semantic revisions; conversion выполняет Source и не хранит оба представления внутри proof. SourceCaptureRef не становится вторым SourceVersionRef. SourceProofClosure — вычисленный результат read, не новый persisted aggregate. Verification — ответ операции, не persisted proof второго формата. Новые exception/diagnostic mirrors Planning/Artifacts не создаются.

## 7. Приёмка и минимальная поставка

| Обязательный критерий | Результат проекта |
|---|---|
| Три запрета DAG | §4: только прямой DAG вызов публичной операции, без междоменных public calls, callbacks или выбора следующей операции. Конкретные ноды OPEN |
| Ответственность классов | §2–4 задают поля, зависимости, эффекты и признаки отказа; конкретный storage adapter OPEN |
| Public/internal boundary | §4: в Input/Output нет read binding, codec, lease или scope |
| Утверждённый порядок | Existing L0→topology и L2→materialization не изменяются. Порядок новой поставки ниже — предложение для принятия, не утверждённый DAG |
| CRUD данных/настроек | Это read/validation value contract, не приёмка Source целиком. Update/delete сохранённого proof не вводятся: новый provenance создаёт новое значение, release относится к holder. CRUD Source данных и настроек остаётся внешним обязательством; отсутствие его реализации не скрыто |
| Междоменный протокол | Pack mapping source_proof точен; consumer поля для closure/admission и scoped adoption OPEN. Интегрированный маршрут не принят |
| POJO и ошибки | Схема §2 конкретна, duplicate create input отклонён, field/logic separation определено. Canonical schema registration и полный capture codec требуют отдельной проверки |

Предлагаемый порядок после принятия решения §1:

1. **Срез P: POJO и чистая структурная валидация** из §2, без отклонённого SourceProofCreateInput. Включает ошибки, canonical registration и vectors. Не создаёт пригодных к runtime использованию фиктивных captures. Реализация через implement-plan только после принятия этого среза и выделения schema IDs. Полная Source migration для этого не нужна.
2. **Срез C: owning capture format/codec и exact reader**. Source identities/projections, canonical object/collection order, immutable body references, finalized boundary и authoritative revision mapping должны стать конкретными. Здесь позиции proof получают проверяемый смысл. Не назначать capture layout по порядку SQL rows.
3. **Срез V: реализация §4** поверх C. Структурно корректный, но поддельный capture/selection отвергается; closure полностью разрешим после restart.
4. **Срез R: scoped retention/adoption** в принятом Artifacts/publication контракте, затем согласование DAG/producer/Pack bindings. R может проектироваться заранее, но без принятого порядка не распараллеливать реализацию. Полный operational proof нельзя объявить поставленным до C/V/R.

Проверки: mutation всех вложений; bool/negative/duplicate/out-of-order indices; две независимые field errors с путями; wrong world/format/capture; out-of-range object и collection; membership и authored-presence после restart; пропущенный child, corrupt/unsealed body; одинаковый proof после latest change; inherited proof после release базы; release racing adoption; один ref на двух адресах; пустая selection с непустым closure; deterministic round-trip и изменение каждого semantic поля.

**Итог:** определён конкретный кандидат POJO/API. Он не объявлен принятым и не реализован. В отличие от прежнего аудита, отсутствие полного Source runtime не мешает обсуждать и отдельно принимать срез P. Полная приёмка этого плана пока не пройдена из-за явно перечисленных C/R/binding/schema gates; документационная фиксация не означает разрешение их обхода.
