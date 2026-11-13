# Переход к вспомогательному модулю Source

Дата: 2026-11-13. Статус: PROJECT / NOT ACCEPTED. Основание: пользователь определил Source как вспомогательный модуль и потребовал отдельный план перехода. Это разрешение подготовить план, не реализовать его. Каждый принятый срез реализуется через implement-plan.

## 1. Ответственность и границы

Проверка контракта и конкретные точки интеграции: [Source/Pack DAG review](source-pack-dag-contract-review.md). R1–R6 входят в gate S0; single-capture POJO нельзя реализовывать по S1 до решения mixed-capture metadata и точного mapping Source results → Pack admission.

Source предоставляет SourceDurableProof, проверку его связи с зафиксированными источниками и определение durable refs для closure. Это вспомогательный модуль, не новый домен универсального CRUD мира. Изменение исходных данных и назначение revisions остаются у их владельцев; физическое хранение, seal, holds и GC — у Artifacts/publication; состав и публикация пакета — у Pack; запуск самостоятельных операций — у DAG.

Source не создаёт зеркало PackStoredProvenance, не импортирует Pack addresses, не запускает producer, не владеет head мира, не заменяет Planning fingerprints и не вводит второй blob store. Малый scope не гарантирует отсутствие внешних зависимостей.

Предлагаемое размещение пока сохраняет пути [контракта](source-durable-proof-contract.md): `app.dataModel.sourceVersioning` и `app.application.sourceVersioning`. Имя пакета не делает модуль самостоятельным доменом; окончательное размещение принимается на шаге S0. Переименование в source либо перенос под worldData без отдельного решения не выполнять.

## 2. Проверенный AS-IS и disposition

Каталоги целевого модуля отсутствуют. SourceDurableProof не реализован. Прежний planning capture нельзя переименовать в durable capture: он формирует projection из переданных World/locations, не исторический held record.

| Класс/функция и источник | Текущая ответственность и зависимости | Решение перехода / критерий отказа |
|---|---|---|
| [SurfacePlanningCapture](../../backend/app/application/worldData/planning/composition/surfacePlanningCapture.py) | Формирует typed planning projections и fingerprint из World/locations, resolve context и domain helpers | Не переносить целиком в Source. Переиспользование конкретных projections/codecs обосновать отдельно. Отказ: объявить view завершённым durable capture |
| [SurfacePlanningView](../../backend/app/application/worldData/planning/contracts/surfacePlanningView.py) | READY/NO_EXTENT view с StateViewRevision и typed inputs | Сохранить до owning Planning cutover; не копировать в proof и не заменить Source revision fingerprint-ом |
| [SourcePublicationGuard](../../backend/app/application/worldData/planning/guards/sourcePublication.py) | require_fresh читает current World/locations, повторяет capture и сравнивает revision | Убрать из переведённых publication путей после замены на pinned proof/adoption; не переносить latest-read в новый Source verifier |
| [require_current_source / SurfacePlanningStale](../../backend/app/application/worldData/planning/guards/sourceRevision.py) | Чистое сравнение view world/revision, отказ при устаревании | Удалить после ухода всех соответствующих callers; не использовать как семантику historical proof |
| [PackBakePublisher](../../backend/app/application/worldData/pack/bake/finalize/packBakePublisher.py) | transaction_if_needed → require_fresh → counters → finalize_pack_on_world | Owning Pack/DAG cutover. Source не наследует publisher/UOW. Отказ: подмена guard новым сервисом без устранения обходной orchestration |
| [WorldSurfaceMaterializationOrchestrator](../../backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py) | Использует SurfacePlanningEntry, capture и require_fresh перед публикацией | Декомпозиция в owning плане; здесь только миграция source boundary. Не переименовывать оркестратор в Source pipeline |
| [PackMaterializationOrchestrator](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py) | Передаёт capture в SurfacePlanningEntry | Producer/DAG binding вместо самостоятельного Source orchestration; конкретная замена OPEN |
| [SurfacePlanningEntry](../../backend/app/application/worldData/planning/composition/surfacePlanningEntry.py) | capture и подготовка planning bundle | Не переносить planning execution в Source; owning decomposition вне этого среза |
| [PackLoadingProgressFacade](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py), [packReadServices](../../backend/app/application/worldData/pack/read/packReadServices.py) | Принимают dependency SurfacePlanningCapture | До удаления capture проверить фактическое использование, не считать сигнатуру доказательством отсутствия поведения |
| [WorldDataContainer](../../backend/app/core/container/worldData.py) | Создаёт capture/guard и передаёт зависимости | Обновить DI после готовности принятой замены; убрать неиспользуемые provider/cache fields. DI не запускает операции |

Это проверенный инвентарь прямых ссылок, не доказательство полноты всех routes и косвенных callers. Полная цепочка API→DAG→операция обязательна перед S5.

## 3. Контракт и классы целевого модуля

Единственный источник полей и сигнатур — [SourceDurableProof contract §§2–4](source-durable-proof-contract.md). Здесь они не дублируются. Кандидат representation capture ref + selection по индексам и удержание полного capture closure ещё требуют принятия, не являются следствием решения о небольшом модуле.

| Класс | Допустимые зависимости / эффекты | Приёмка |
|---|---|---|
| SourceDurableProof, SourceCaptureRef, SourceCaptureSelection | Existing EntityUid/ArtifactRef, immutable значения; без IO | Точные поля, strict validation и глубокая immutable структура; нет альтернативного Source/Pack DTO |
| SourceProofVerifyInput, SourceProofClosureInput, SourceProofVerification, SourceProofClosure | Source proof и existing refs; без capabilities | Input/result не дают caller управлять внутренними стадиями; verification POJO не считается hold token |
| SourceFailure и единый owning roster sourceErrors из актуального source-proof-v2-contract-spec.md | Existing FieldPathError/ValidatedFieldPath; без storage exceptions в wire | Старые зеркальные proof error types не создаются; ошибки Artifacts не клонируются; независимые ошибки агрегируются |
| ISourceProofReadPipelineOpenPipeline / SourceProofReadPipelineOpenPipeline | create/verify/collect_refs по точным сигнатурам контракта; внутренние validator/read binding | Прямой вызов из принятой DAG-ноды, read-only операция; ни nested public calls, ни выбор следующей операции |
| SourceProofValidator | Source POJO, decoded inputs | Чистые проверки; не читает latest, не получает недостающие inputs |
| SourceProofClosureCollector | Owning decoded graph и внутренний read binding | Полный детерминированный closure либо отказ; не partial success |
| SourceProofReadBinding | Exact reader, owning capture/body codecs, принятый storage binding | Стабильное чтение, без latest fallback; конкретный adapter и его вложенные вызовы принимаются в S2 |

Existing ArtifactRef отвечает за content identity, PlanDependency — за Planning dependency, CanonicalCodec — за encoding, ValidatorAggregationHelper — за агрегацию. Они переиспользуются без зеркал. Capture identity/layout, canonical registration и внешние ошибки требуют проверки на S0/S2; отсутствие сведений запрещает объявлять POJO gate пройденным.

## 4. Внешние зависимости и mapping

| Владелец | Что нужно Source/Pack | Подтверждено / открыто |
|---|---|---|
| Владельцы исходных данных | Исторические revisions, тела, membership и authored-presence в завершённом capture | Existing SurfacePlanningCapture этого не обеспечивает. Concrete owner method, Input/Output/Error и формат capture OPEN; Source не подменяет владельцев универсальным writer |
| Artifacts/publication | Exact immutable read, seal, stable read boundary, capture root lifetime, scoped adoption | Existing ArtifactRef/ArtifactRetentionHolder доступны; полный binding с concrete методами/ошибками и независимыми holders OPEN |
| Producer | Фактически прочитанный selection и доказуемая связь output с proof | Не выводить из hash или списка выбранных members; concrete output mapping OPEN |
| Pack | SourceDurableProof → PackStoredProvenance.source_proof; existing Planning tuple сохраняется | Mapping proof определён проектом; SourceProofClosure.refs → конкретный Pack admission input пока OPEN |
| DAG | Передача owning результатов между самостоятельными публичными операциями | Ноды, deps и binding определяет пользователь; не изобретать их в этом плане |

## 5. Последовательность перехода

Это предлагаемый порядок поставки для согласования; он не меняет утверждённые L0→topology и L2→settlement materialization и не устанавливает новый порядок исполнения DAG.

### S0 — принятие границы и схемы

Принять размещение, capture-ref/selection representation либо скорректировать его; проверить цену полного capture closure. Закрыть дублирование POJO и field/logic errors, выделить canonical schema IDs и зафиксировать точные capture semantics. DoD: конкретный принятый контракт и scope первого implementation среза. До этого код не писать.

### S1 — POJO и чистая валидация

Реализовать только принятые модели/ошибки/encoding и structural validation. Никаких fake captures, success placeholders или подключения к Pack. Проверить immutable nesting, bool/negative/duplicate indices, canonical ordering, independent errors, round-trip. DoD: работоспособная схема; это не готовый durable proof runtime.

### S2 — exact capture/read dependency

Получить от владельцев конкретный finalized capture codec и reader, revision/body/membership mapping и источник root retention. Проверить все их классы, вызовы и эффекты. Реализовать принятый Source read binding поверх этих контрактов. Если отсутствует owning capability, оформить отдельный необходимый срез у владельца, не писать replacement CRUD в Source. DoD: исторический capture разрешается после restart и изменения latest, с сохранением authored-presence.

### S3 — проверка и closure

Реализовать публичные операции и их чистые internals. Проверить exact capture equality, foreign world, bounds, corruption/missing/unsealed body, полный closure и отсутствие latest reads. DoD: typed success/failure без IO orchestration соседних доменов. Не выдавать результат предварительной проверки за защиту от release.

### S4 — атомарное удержание

Принять и подключить Artifacts/publication scoped adoption: проверка исходного holder и seal → destination holds → release передаваемых holds → commit. Проверить rollback, restart, concurrent release и независимые holders одного capture. Эта стадия не делает Source commit owner. DoD: новый владелец сохраняет closure независимо от старого. Без этого operational путь не допускается.

### S5 — принятый DAG/producer/Pack cutover

Пользователь принимает ноды и передачу exact outputs в inputs. Проследить API→engine DAG→согласованные операции и все nested calls. Перевести выбранный маршрут с require_fresh на исторический proof/adoption; сохранить producer/planning semantics. В том же принятом cutover убрать старый обход для этого маршрута. Не удалять действующий путь до готовности замены и не оставлять fallback после переключения. DoD: нет прямого публичного вызова Source из Pack, нет callback/worker orchestration, inherited provenance не переписан текущим capture.

### S6 — удаление остаточных зависимостей и приёмка

Повторить поиск всех callers/routes/imports/DI. Guard, stale exception и capture удалять только согласно disposition и после ухода последнего соответствующего caller; полезные Planning projections не удалять автоматически. Проверить старые manifest refs: отсутствующий proof не восстанавливается из fingerprint; обработка старых публикаций — отдельно принятый Pack переход без молчаливого удаления/миграции. DoD: переведённые маршруты не имеют legacy обхода, runtime и документы согласованы, весь заявленный scope проверен.

## 6. Приёмка и ограничения

Три запрета DAG, ответственность каждого класса, public/internal boundary, неизменность утверждённого порядка, междоменные контракты и отсутствие пересечения POJO обязательны на каждом срезе. Source не получает собственные CRUD мира/настроек: в принятой пользователем вспомогательной роли таких данных у него нет. Это не освобождает owning домены от их CRUD критериев и не отменяет приёмку операций Source.

Обязательные сценарии: capture A проходит после latest B; чужой мир/подмена capture/недостающий body отвергаются; membership и authored-presence воспроизводятся; несколько errors возвращаются вместе; два адреса с одним ref сохраняют разные provenance uses; inherited часть сохраняет старый proof; новая версия читается после release базы и restart; release racing adoption не оставляет опубликованный head без closure.

**Приёмка плана пока не пройдена:** S0 representation/schema, S2 owner contracts/adapter, S4 adoption и S5 конкретный DAG/consumer mapping OPEN. Указанные зависимости — условия перехода, а не поручение реализовать весь world-source-versioning. SQL, writers всех доменов, новые DAG-ноды, runtime cutover и изменения Pack не разрешаются самим созданием этого плана.
