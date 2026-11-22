# Source core — capture, prune и descriptor configuration

2026-11-15. DRAFT продолжения архитектуры ядра. Не разрешает код, CRUD/DAG wiring или исполнение GC. Источники: world-source-versioning.md §GC ревизий; source-proof-v2-contract-spec.md §10–12; existing SourceCapture/SourceDescriptorRegistry.

## 1. Capture assembly: не новый public pipeline

### Candidate relation contract — проект 2026-11-22

Путь `backend/app/application/worldData/sourceVersioning/capture/captureCandidateChecker.py`:

```python
class SourceCaptureCandidateChecker:
    def __init__(self, *, descriptors: SourceDescriptorLookup) -> None: ...
    def check(
        self, *, witness: SourceCaptureWitness, capture: SourceCapture,
        collections: tuple[tuple[SourceCollectionVersion, SourceCollectionBody], ...],
    ) -> tuple[SourceLogicIssue, ...]: ...
```

Метод проверяет только отношения полностью материализованных, structurally допустимых Source values: witness/capture world, соответствие коллекций capture mappings и полноту membership относительно object mappings. SourceDescriptorLookup задаёт разрешённые member descriptors и SET/SEQUENCE semantics. Empty tuple означает отсутствие найденных relation нарушений, не finalized/held/available. Constructor лишь фиксирует immutable lookup; diagnostics создаются на вызов, operation=FINALIZE_CAPTURE назначает внешний Source owner.

ArtifactRef→decoded content correlation должна быть обеспечена входным binding: этот checker не может доказать её по одному POJO. Поэтому он не возвращает CAPTURE_NOT_FINALIZED для ещё не финализированного кандидата, не проверяет catalog seal, storage existence, physical hash или acquire. Capture_uid conflict с ранее сохранённым witness проверяет finalization store boundary, не pure checker без historical state.

Единая реализация общих relation rules предлагается в `proof/validation/_captureRelationRules.py` как функция `check_capture_relations(*, witness: SourceCaptureWitness, capture: SourceCapture, collections: tuple[tuple[SourceCollectionVersion, SourceCollectionBody], ...], descriptors: SourceDescriptorLookup) -> tuple[SourceLogicIssue, ...]`. Это internal функция с одной ответственностью, не новый service или DTO. Candidate checker и SourceCaptureMembershipChecker вызывают её; membership checker дополнительно проверяет только заявленное usage относительно допустимого capture. Он не копирует membership algorithm и не строит synthetic usage для candidate. Добавление helper — адресная внутренняя дельта на приёмку, не второй набор правил.

Общие issues имеют group_index/use_index=None. Source occurrence localization назначает реальные proof origins только для proof caller; candidate не получает фиктивные group/use=0. World mismatch → WRONG_WORLD; предъявленная collection mapping не соответствует capture → BODY_MAPPING_CONFLICT; отсутствующий required membership материал → INCOMPLETE_COLLECTION по принятому смыслу §11.3. Не добавлять MISSING_BODY по отсутствию элемента materialized input и не считать unrelated collection успехом. Переданный tuple не связывается по позиции: сравнение по exact collection version/body mapping.

Проверки: foreign world; отсутствующий collection body; подмена body под тем же collection identity; member вне exact object mappings; допустимый пустой capture; одинаковый исходный relation через candidate/membership вызывает единственную реализацию и не дублирует diagnostics. Refusal не допускает finalize writes. Exact required physical dependencies owning форматов и их availability остаются вне функции.

Сборка capture не вычисляет revisions, не выбирает latest и не запускает projector. Она принимает готовые mappings. Existing SourceCapture уже содержит world_uid/objects/collections и проверяет локальные structural инварианты.

**Уточнение предложения:** отдельный SourceCaptureAssembler только ради вызова конструктора SourceCapture не обоснован. Не создавать wrapper-класс без собственного алгоритма. Для готовых валидных mappings использовать existing POJO construction. Если при последующей детализации потребуется отдельное canonical преобразование, сначала определить его собственный инвариант и метод; не спрятать выбор source set в assembler.

SourceCaptureCandidateChecker относится к проверке отношений кандидата, а не к сборке модели. Нужен до finalize, однако он не должен дублировать SourceCaptureMembershipChecker: world/descriptor checks и проверка exact mapping имеют единственные общие реализации. Finalization добавляет только evidence, которого нет у pure проверок: exact revision read, artifact identity/seal и атомарное сохранение witness/retention через принятые ports.

Existing internal signature сохраняется как основание:

```python
async def finalize(self, request: SourceCaptureWitness, *,
                   lease: OperationLeaseRef) -> SourceCaptureRef | SourceFailure: ...
```

Это не публичный DAG-вход; SourceCaptureAdapter не становится публичным обходным фасадом. Lease — runtime capability, не поле Source persisted POJO. Public capture acquisition ещё требует отдельного контракта; факт наличия internal finalize его не закрывает.

Проверки границ: capture constructor не читает DB; невалидные world/duplicate mappings отвергаются; создание witness не считается committed finalize; никакая pure проверка не утверждает наличие holds. Capture body/witness POJO не дублируются.

## 2. Prune: не присваивать Source чужой reachability

### Pure candidate contract — проект 2026-11-22

Конкретизируется только Source selection policy, не public preview/confirm и не авторизация удаления. Модуль `backend/app/application/worldData/sourceVersioning/revision/revisionPrunePolicy.py`:

```python
class SourceRevisionPrunePolicy:
    def __init__(self) -> None: ...
    def evaluate(
        self, *,
        requested: tuple[SourceVersionRef, ...],
        latest: SourceVersionRef,
    ) -> tuple[SourceVersionRef, ...]: ...
```

Функция метода — исключить exact latest revision из предъявленного набора object revision candidates; сохранить canonical порядок остальных refs. Пустой requested возвращает пустой tuple. Это узкий existing object-history предмет основного плана, не расширение на collection prune. Для collection history отдельная операция этим методом не подразумевается.

Предусловия internal вызова: refs структурно валидны; requested unique/canonical, все object_id равны latest.object_id; latest получен из authoritative Source revision facts; существование и статус requested revisions проверены до вызова. Разные identities, дубли, противоречивые hashes одной seq или revision новее предъявленного latest — нарушение входного контракта internal policy, не утверждение о свободе revision. Формирование пользовательского отказа missing/pruned принадлежит будущему request/exact-read boundary; его нельзя поручать pure policy без данных хранения.

Результат — кандидаты, а не eligible-for-deletion receipt: live/tombstone статус не заменяет проверку удержаний, наличие в результате не разрешает root release или GC. Latest исключается независимо от статуса; tombstone не означает pruned. При confirm authoritative latest/holds повторно проверяет согласованная owning цепочка, не cached preview. Ни mutation, ни replacement latest здесь не выполняются.

Проверка ответственности: latest в requested исключён; отсутствие latest в requested не добавляет refs; пустой requested допустим; чужая identity/повтор/конфликт same seq отвергаются как internal misuse; другие refs сохраняются без сортировки/repair. Ноль IO/holders calls, ноль writes. Exact public missing/pruned errors, Source root release и confirm binding остаются отдельными прежними пунктами; эта signature их не закрывает.

В основном плане §GC ревизий уже разделены:

- Source dataModel — identity/revision, без holders/usage imports;
- sourceUsage — application reachability index;
- revisionPrune — получает usage evidence и удаляет только free;
- latest всегда удерживается; tombstone и prune — разные операции;
- v1 — explicit preview/confirm, не background sweeper.

Следовательно, ранее предложенный SourceRevisionPrunePolicy нельзя считать готовой самостоятельной реализацией поиска holders. Не создавать второй usage-index и новый Source-held_by DTO. Source может проверять собственные facts exact revision/identity и формировать набор кандидатов; достоверность free/held и выполнение удаления зависят от owning bindings. Preview не является authority для позднего confirm: под принятым scope требуется повторная проверка, иначе появляется окно между preview и новым capture/hold.

**Конкретный пробел:** историческая строка `prune(object_id, policy=keep_latest | revisions=[…])` не задаёт typed request/result/errors, точный модуль owner и атомарное соответствие explicit prune снятию Source root. Не объявлять эту строку готовым API. Историческое Source root удержание не отменяется формулировкой «free»: нужен подтверждённый порядок eligibility → release разрешённого root → GC с сохранением остальных holders.

Собственная следующая работа Source: exact revision candidate input и ошибки отсутствующей/pruned/live/tombstone revision в едином roster. Внешняя часть — INT-ARTIFACTS-RETENTION и отдельный usage/prune binding. Не вводить поля bool free/held в caller request как доказательство отсутствия держателей. До разрешения ownership границы exact public prune class/signature не назначается Source самостоятельно.

## 3. Descriptor configuration

### Собственная граница configuration: уточнение проекта 2026-11-22

Нужно различать два предмета: SourceDescriptorRegistry — schema/composition самого Source; SourceSettingsId — identity настроек другого owning источника. Наличие SourceSettingsId не создаёт Source CRUD для содержимого чужих settings. Следующая таблица конкретизирует собственный lifecycle proposal; не объявляет автоматически принятым исключение обязательного CRUD-критерия.

| Операция над descriptor configuration | Предлагаемый механизм / владелец | Проверка ответственности |
|---|---|---|
| Create | SourceDescriptorRegistry(entries) в composition; SourceDescriptorDefinition валидирует каждую definition | Construction не регистрирует mutable runtime entry и не читает foreign storage |
| Read | SourceDescriptorLookup.definition(key) → definition или None | Exact key, нет default/discovery/latest замены |
| Update | Новый immutable registry для новой composition; existing registry/исторические bindings не мутируют | Замена определения не должна менять интерпретацию ранее сохранённых identity/proof; совместимость требует отдельной проверки owning bindings |
| Delete | Отсутствие definition в новой composition не означает удаление исторических bindings или Source данных | Нельзя делать старый proof нечитаемым через незаметное удаление decoder/descriptor binding |

Это операции composition, не public runtime CRUD. Собственный незакрытый пункт АР-5 теперь сформулирован точно: подтвердить применимость такой границы к требованиям доменного ТЗ и обязательному CRUD-критерию; если управляемая runtime configuration обязательна, предъявить отдельные конкретные operations. До этого не добавлять SourceConfigurationService и не объявлять C/U/D неприменимыми как уже принятое решение. Внешний Lifecycle/Artifacts ответ не заменяет эту проверку Source.

Переиспользуется existing SourceDescriptorRegistry(entries) и SourceDescriptorDefinition; frozen lifetime configuration. SourceDescriptorLookup имеет одну функцию definition(key), не owns mutable registration. Configuration structural validation остаётся у existing моделей: unique keys, category/scope/key_kind, member_descriptors. Runtime admission не создаёт definitions при unknown descriptor.

Key adapters/body codecs/projectors — application composition, не поля configuration POJO и не callbacks в proof. Полная concrete composition остаётся отдельной интеграцией. Удерживаемые historical bindings нельзя переназначать новым форматам ради convenience latest lookup.

**CRUD критерий не отменяется:** в правилах нет принятого исключения Source configuration, аналогичного исключениям других доменов. Поэтому один immutable registry не доказывает завершение публичных settings C/R/U/D. Нужно отдельно решить lifecycle этого Source-owned configuration: что является compile-time composition и что реально является управляемыми данными/настройками домена. Не придумывать горячее обновление registry и не переносить на Source чужое исключение. Это собственный design-вопрос, не блокер работы над независимыми алгоритмами proof.

## 4. Архитектурные дельты и следующий шаг

### Карточки классов и методы, 2026-11-22

Корень application-путей — `backend/app/application/worldData/sourceVersioning/`. Предлагаемое размещение не означает runtime-поставку. Карточка с незавершённой signature не проходит приёмку, даже если ответственность уже названа.

| Класс / файл | Метод и что делает | Зависимости и эффекты | Проверка ответственности / остаток |
|---|---|---|---|
| SourceCaptureCandidateChecker / capture/captureCandidateChecker.py (предлагаемое размещение) | check — проверить отношения witness candidate, полного SourceCapture и его collection mappings до finalization | Общие Source world/descriptor/membership rules; pure | Не повторяет алгоритмы других checkers и не удостоверяет committed witness; exact value/error signature ещё требуется |
| SourceCaptureFinalizer / capture/captureFinalizer.py | finalize — атомарно финализировать предъявленный witness candidate; signature §1 | Candidate checks и принятые persistence/retention bindings | Нет SQL/codec/holder engine внутри finalizer, partial success или fake committed ref; точная допустимая вложенная цепочка и constructors OPEN |
| SourceRevisionPrunePolicy / revision/revisionPrunePolicy.py (предлагаемое internal размещение) | evaluate — определить кандидатов по предъявленным Source revision facts с исключением latest; это не решение о разрешении physical deletion | Pure Source facts; не foreign usage lookup | Не снимает root/holds и не запускает GC; exact facts/decision/error пока OPEN, не public prune API |
| SourceDescriptorLookup / contracts/descriptorLookup.py | definition(key: SourceDescriptorKey) → SourceDescriptorDefinition или None — найти definition в immutable registry | __init__(definitions: SourceDescriptorRegistry); pure | Unknown не становится default; нет регистрации или изменения entries |

Configuration C/R/U/D не назначается искусственному SourceConfigurationService: существующие registry/lookup уже покрывают immutable composition и lookup. Решение о lifecycle управляемых settings и владельцах соответствующих операций остаётся прежним АР-5, а не скрытой обязанностью lookup. До этого полного перечня runtime configuration classes/methods нет; это конкретное отсутствие контракта, не готовая архитектура.

SourceCaptureAssembler не создаётся ради construction; SourceCaptureRetentionBinding/adoption preflight не возвращаются. `__init__` перечисленных исполнителей только фиксирует зависимости, не выполняет finalize/prune/IO. Недостающий foreign port нельзя заменить созданным здесь интерфейсом.

Предложены две корректировки начальной карты ролей: не создавать SourceCaptureAssembler без алгоритма; не назначать SourceRevisionPrunePolicy владельцем external reachability. Public capture/prune entry и settings lifecycle пока не закрыты. Это честные пределы текущей архитектуры, не доказательство готовности домена.

Следующая консолидация завершает карточки классов и POJO, затем проходит review целой архитектуры АР-1…АР-6. Независимый локальный implementation-срез запрещён; прежняя рекомендация такого среза отозвана. Код, external contracts, error roster и accepted public signatures этой детализацией не изменены.
