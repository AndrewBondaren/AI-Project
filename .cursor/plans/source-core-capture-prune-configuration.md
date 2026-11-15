# Source core — capture, prune и descriptor configuration

2026-11-15. DRAFT продолжения архитектуры ядра. Не разрешает код, CRUD/DAG wiring или исполнение GC. Источники: world-source-versioning.md §GC ревизий; source-proof-v2-contract-spec.md §10–12; existing SourceCapture/SourceDescriptorRegistry.

## 1. Capture assembly: не новый public pipeline

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

Переиспользуется existing SourceDescriptorRegistry(entries) и SourceDescriptorDefinition; frozen lifetime configuration. SourceDescriptorLookup имеет одну функцию definition(key), не owns mutable registration. Configuration structural validation остаётся у existing моделей: unique keys, category/scope/key_kind, member_descriptors. Runtime admission не создаёт definitions при unknown descriptor.

Key adapters/body codecs/projectors — application composition, не поля configuration POJO и не callbacks в proof. Полная concrete composition остаётся отдельной интеграцией. Удерживаемые historical bindings нельзя переназначать новым форматам ради convenience latest lookup.

**CRUD критерий не отменяется:** в правилах нет принятого исключения Source configuration, аналогичного исключениям других доменов. Поэтому один immutable registry не доказывает завершение публичных settings C/R/U/D. Нужно отдельно решить lifecycle этого Source-owned configuration: что является compile-time composition и что реально является управляемыми данными/настройками домена. Не придумывать горячее обновление registry и не переносить на Source чужое исключение. Это собственный design-вопрос, не блокер работы над независимыми алгоритмами proof.

## 4. Архитектурные дельты и следующий шаг

Предложены две корректировки начальной карты ролей: не создавать SourceCaptureAssembler без алгоритма; не назначать SourceRevisionPrunePolicy владельцем external reachability. Public capture/prune entry и settings lifecycle пока не закрыты. Это честные пределы текущей архитектуры, не доказательство готовности домена.

Следующая консолидация должна свести единым списком: принятые роли; новые предложения исключить лишние wrappers; exact checker API; public proof/mutation proposals; собственные открытые контракты; внешний техдолг. После этого — review архитектуры выбранного независимого среза и отдельный implementation-план. Код, external contracts, error roster и accepted public signatures не изменены.
