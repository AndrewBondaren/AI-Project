# Проверка Source proof и точки интеграции с Pack через DAG

**Уточнение scope после указания пользователя:** работа этого агента ограничена ядром Pack. Source internal предложения R1/R5/R6 не являются поручением реализовать или изменить Source. Актуальное [Pack-owned уточнение admission](pack-source-admission-boundary.md) учитывает позднюю Pack приёмку: describe_metadata/bind уже конкретизированы, PACK-METADATA-PLANNING отложен без блокировки локального scope. R2/R3 ниже — только вопросы integrated mapping, не основание заново отклонять локальные Pack контракты. Требование обязательно добавить transient поле в prepare не принято: сначала предъявляется owning binding.

Дата: 2026-11-13. Статус: REVIEW / NOT ACCEPTED. Проверены [Source contract](source-durable-proof-contract.md), [план перехода](source-module-transition.md), [Pack contract](pack-v2-domain-contract-spec.md), [Pack write contracts](pack-v2-public-write-operations.md), [Pack SoT](../../docs/tz_world_pack_storage.md). Проверка статическая, runtime не изменён. Названия ниже обозначают операции и передачу данных, не новые NodeId или утверждённые deps.

## 1. Находки, препятствующие приёмке

Для R1/R3 подготовлены [требования и предлагаемое решение metadata dependency usage](pack-metadata-dependency-usage.md): трассировка операций, field/group attribution, обмен через DAG и требования нескольких captures. Документ отделяет принятые границы от предлагаемых schema/API изменений; это не закрытие находок и не новый блокер независимого Pack scope.

### R1 / P1 — single-capture proof не покрывает смешанное происхождение

SourceDurableProof содержит ровно один capture + selection. Pack write может сохранить часть значений metadata из pinned base A и получить новые значения от capture B. Например, publish_settlement_structure сохраняет прежний packed список при None, меняя другое поле; header сохраняет часть скаляров базы. Такой результат нельзя удостоверить только B, а подмена старых dependencies текущими нарушает provenance. Inherited целой неизменной строки этого случая не закрывает.

Требуется concrete Source representation зависимостей нескольких captures и правила объединения/конфликтов либо доказанный контракт нового capture, включающего все исторические inputs. Второй вариант сейчас отсутствует и не должен молча создавать новую capture-операцию. Не разрешать DAG объединять selections по индексам разных captures. До решения single-capture схема не принимается как общий proof Pack metadata. Для одного producer с одним capture её применимость также требует owning evidence.

### R2 / P1 — нет входа Pack для результата проверки и closure

SourceProofVerification(proof) и SourceProofClosure(proof, refs) возвращаются DAG, но ни PackPreparationBody(state, capture, scope), ни payload part input, ни metadata binding не имеют согласованного поля для этих результатов. Записать только proof в provenance недостаточно, чтобы передать verified refs. Публичный вызов Source из prepare запрещён; повторить Source traversal внутри Pack также нельзя.

Необходим отдельный согласованный transient admission input final prepare, связывающий результаты Source с **всеми** proof конечного state (payload + metadata, включая inherited). Его точная схема пока не объявлена; добавлять новый persisted field manifest или зеркальный Pack proof нельзя. Pack должен отклонять missing, foreign, duplicate/conflicting и extra результаты по определённой политике, а не доверять caller refs. Согласовать boundary доверия и внутреннюю owning проверку: конструируемый success POJO сам по себе не свидетельство подлинности или полноты closure.

### R3 / P1 — metadata subject не содержит dependency mapping

Проект PackPreparationService.describe_metadata возвращает PackMetadataSubject(base_publication, address, value_fingerprint). Source принимает capture/selection, а не subject. DAG не может вывести selection из fingerprint и не должен повторять Pack merge/status/header алгоритм. Принятое направление требует Pack-owned связи результата с реально использованными inputs; в точном output она ещё не предъявлена.

Закрытие: concrete Pack output должен предъявлять Source dependency usage для exact subject, включая preserved base inputs. Source проверяет только source часть. Pack bind проверяет связь subject с текущим state и inputs, не делегируя Source подтверждение правильности Pack вычисления. Это не требование помещать PackMetadataSubject внутрь Source DTO.

### R4 / P1 — нет предъявленного lifecycle capture и защиты окна между операциями

Proof не содержит временные capabilities — это правильно. Но другой accepted input/binding обязан определять исходное живое удержание, его связь с world/operation и независимый release. Сейчас не предъявлены capture finalization evidence и exact adoption signature. Сбор refs до prepare не защищает от release/GC между стадиями. Только atomic scoped проверка и handoff закрывают этот риск; предварительный verify не даёт READY.

### R5 / P2 — CREATE не имеет самостоятельной семантики относительно VERIFY

create принимает уже собранный SourceDurableProof и возвращает тот же proof в verification wrapper. Он не связывает proof с producer output и не создаёт durable запись. Отличие от verify — отсутствие expected_capture. Это кандидат на одну операцию validation/admission с явным ожиданием, а не доказанный отдельный create lifecycle. До реализации принять минимальный API, не создавать дублирующую операцию ради имени CRUD. Вспомогательный Source не получает CRUD мира.

### R6 / P2 — codec/read/error части ещё недостаточно конкретны

Capture format/layout, finalization marker, canonical IDs, body traversal и конкретный reader не определены. Объявленные синхронные методы выполняют IO: нужно принять sync/async по реальному binding, не скрывать async чтение в sync facade. INVALID_VALUE не определяет перевод всех structural errors в FieldPathError; SourceProofLogicIssue.path требует принятого typed selector для capture/body дефектов. До этого typed error и POJO gate не закрыт. Запрет циклов надо применять к retention traversal по принятому формату, а не автоматически запрещать любые циклические ссылки исходной модели мира.

## 2. Точные точки интеграции в проекте Pack

| Этап | Публичная операция / данные Pack | Передача через DAG и ответственность |
|---|---|---|
| Payload | PackPreparationService.write_world_map_tile / write_wilderness_chunk и прочие specialized write inputs, содержащие part | Producer возвращает artifact, адресуемый результат, source usage и Planning dependencies; DAG передаёт usage в Source, затем переносит подтверждённый proof в part.provenance.provenance.source_proof для new wrapper. Address/artifact берутся из producer mapping, не из Source |
| Сохранённые части | start_from_base → PackPreparationState | Pack читает pinned base и сохраняет полный provenance. DAG не переписывает его новым capture. Проверка принадлежности базе — Pack |
| Metadata subject | PackPreparationService.describe_metadata(request: PackMetadataSubjectsInput) → tuple[PackMetadataSubject, ...] | Вызывается после нужных write-операций. Возвращает base/address/value fingerprint. Для source usage этот output надо конкретизировать по R3 |
| Metadata binding | PackPreparationService.bind_metadata_provenance(request: PackMetadataProvenanceInput) → PackPreparationState | DAG передаёт entries: tuple[PackMetadataProofBinding, ...], каждый с subject и provenance. Pack проверяет exact текущий subject, базу и dependency binding; Source не вызывается внутри |
| Final preparation | async PackPreparationPipelineOpenPipeline.prepare(request: PackPreparationInput) → PreparedPackCandidate | Input содержит operation_id, preparation_fingerprint, body(state, capture, scope). Здесь требуется согласованное transient Source admission дополнение R2, а не поле в manifest. Pack проверяет полноту конечного состава и provenance и атомарное удержание closure перед READY |
| Activation | async activate(request: PackActivationInput) | Отдельный вызов DAG с candidate и expected publication. Source capture/producer повторно не запускаются. Используется принятый atomic handoff; latest не перечитывается |

Пути проектных Pack методов: `application/worldData/pack/preparation/packPreparationService.py` и `application/worldData/pack/packPreparationPipelineOpenPipeline.py`; POJO write/bind — `dataModel/worldPack/preparation/operations.py`, subjects — `metadataSubject.py`. Это проектные пути, не ссылки на готовые реализации. При проверке в runtime preparation найдены addresses.py и coverage.py; наличие отдельных моделей не доказывает готовности указанных операций.

Source методы/результаты берутся из §4 Source contract, с отказом в их окончательной приёмке по R1–R6. Не создавать новый façade между DAG и Pack/Source.

## 3. Передача данных без назначения нод

```text
Готовый закреплённый capture + producer output
    → DAG → Source admission заявленного usage → DAG
    → Pack write(part с полным provenance) → конечный/промежуточный state

Pack write state → DAG → Pack describe_metadata
    → DAG → Source admission source usage [output usage пока OPEN]
    → DAG → Pack bind_metadata_provenance → state

Все proofs конечного state → DAG → Source collect_refs
    → DAG → Pack prepare(state + transient admission [OPEN])
    → PreparedPackCandidate → DAG → Pack activate
```

Это карта требуемого обмена данными, не новая утверждённая sequence нод. Write-порядок остаётся прежним; describe/bind относятся к выбранному пользователем направлению Pack. Источник extraction полного набора proof тоже должен быть concrete Pack result/контрактом, если DAG пришлось бы интерпретировать внутреннюю семантику state. DAG только переносит явно предоставленные поля, не строит manifest, не считает fingerprint/closure и не выбирает source dependencies за producer.

New payload proof привязывается перед соответствующей записью; metadata proof — после вычисления exact projection и до final prepare. Closure нужен для полного **конечного** состава, а не только новых частей. Successful bind не снимает требования повторной проверки holds в prepare/activation по принятому lifecycle.

## 4. Приёмка по обязательным правилам

| Критерий | Вывод |
|---|---|
| Три запрета DAG | Проектируемый обмен не требует direct public междоменных вызовов или hidden orchestration; конкретных нод нет, integrated route OPEN |
| Ответственность классов | Source проверяет source, Pack вычисляет/проверяет свой subject, Artifacts удерживает. R3 не позволяет принять фактическую реализацию границы |
| Public/internal boundary | POJO не содержит backend/lease. Scoped adoption signature и transient prepare admission отсутствуют: R2/R4 |
| Утверждённый порядок | Не изменён; не назначены NodeId/deps/параллельные ветки. Полная будущая цепочка требует совместного принятия |
| CRUD | Source вспомогательный, не новый CRUD owner. Captures/revisions/holds должны поступать от concrete owning операций; они пока не предъявлены |
| Междоменный контракт | Поле persisted source_proof известно; usage/verification/closure mapping неполон: R1–R4 |
| POJO и ошибки | Immutable форма недостаточна; single capture, overlapping API и error/codec gaps R1/R5/R6 блокируют приёмку |

**Итог: контракт и междоменная интеграция не приняты.** Точки интеграции установлены: payload write, metadata describe/bind, final prepare; activate потребляет candidate и выполняет owning handoff. До реализации исправить R1–R6 и предъявить exact producer→Source→Pack field mapping с ошибками, затем пользователь определяет согласованные ноды. Не закрывать отдельный POJO implementation slice, если его схема будет заведомо изменяться из-за mixed-capture требования.
