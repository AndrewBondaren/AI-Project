# Source core — публичные границы и методы

**Согласование 2026-11-15:** пользователь ответил «Ок» после предъявления документа. Согласовано направление отдельных proof operation owners с существующими POJO. Полная архитектура, constructor dependencies и реализация не приняты. Разделения check_coverage/adoption preflight зафиксированы как предложение для явной синхронизации S1/S2; действующие спецификации и код этим ответом молча не переписаны. DRAFT ниже относится к незавершённой полной архитектуре и оставшимся дельтам.

2026-11-15. DRAFT пункта 2 архитектуры ядра после согласования разделения ответственности. Это предложение изменения размещения существующих proof-операций; принятый единый SourceProofPipelineOpenPipeline в spec §9 не заменён до отдельного принятия этой дельты. Код не разрешён. POJO/semantics/errors/wire IDs не изменяются.

## 1. Пять отдельных публичных классов

Предлагаемый корень: `app.application.worldData.sourceVersioning.operations`. Каждый модуль содержит один concrete operation owner с одним публичным методом. Интерфейс, если необходим DI-контракту, повторяет только этот метод; универсальный пятиоперационный facade не добавляется. Caller — согласованная нода DAG; назначение нод и wiring отложены INT-DAG. Pack не получает доступ к внутренним алгоритмам.

```python
# operations/proofAdmissionPipelineOpenPipeline.py
class SourceProofAdmissionPipelineOpenPipeline:
    async def admit(self, request: SourceProofInput) -> SourceProofResult | SourceFailure: ...

# operations/proofReadPipelineOpenPipeline.py
class SourceProofReadPipelineOpenPipeline:
    async def read(self, request: SourceProofReadInput) -> SourceProofResult | SourceFailure: ...

# operations/proofGroupAdmissionPipelineOpenPipeline.py
class SourceProofGroupAdmissionPipelineOpenPipeline:
    async def admit_groups(self, request: SourceProofGroupsInput) -> SourceProofGroupsResult | SourceFailure: ...

# operations/proofGroupVerificationPipelineOpenPipeline.py
class SourceProofGroupVerificationPipelineOpenPipeline:
    async def verify_groups(self, request: SourceProofGroupsVerifyInput) -> SourceProofGroupsResult | SourceFailure: ...

# operations/proofSelectionPipelineOpenPipeline.py
class SourceProofSelectionPipelineOpenPipeline:
    async def select(self, request: SourceProofSelectInput) -> SourceProofResult | SourceFailure: ...
```

Public метод не принимает SourceOperation, codec/manifest, backend, transaction или выбор режима. Operation для diagnostics фиксирована самим владельцем. Все пять методов read-only: не создают revision/capture/holds, не запускают producers, не вызывают другие публичные Source операции. Локальные проверки и циклы обхода одного request не являются выбором внешних операций.

## 2. Точные существующие импорты POJO

Все пути под `app.dataModel.sourceVersioning`:

| Модуль | Используемые типы |
|---|---|
| sourceProofInput | SourceProofInput, SourceProofReadInput |
| sourceProofGroups | SourceProofGroupsInput, SourceProofGroupsResult, SourceProofGroupsVerifyInput |
| sourceProofSelection | SourceProofSelectInput, SourceProofSelection |
| sourceProofResult | SourceProofResult |
| sourceDurableProof | SourceDurableProof |
| sourceErrors | SourceFailure, SourceOperation, SourceFieldIssue, SourceLogicIssue |

Новые carriers не создаются. Frozen/strict/deep immutability уже поставлены G1.1/G1.2. Semantic boundary и агрегация ошибок ещё не реализованы: существующие TODO на ValueError не считаются закрытыми. Structural invalid-root Pydantic failure допустим по spec §11.3; доступные независимые semantic failures должны собираться с исходными paths. Infrastructure exceptions не переводятся в MISSING_BODY или domain success.

## 3. Вложенные стадии одной операции

| Owner | Линейная цепочка | Проверяемый результат |
|---|---|---|
| Admission | Проверки исходного request → normalizer → exact capture/closure evaluation → SourceProofResult | Declared repetitions обработаны, нормализованный proof соответствует usage, refs полный closure |
| Read | Проверки исходного request и canonical proof → exact capture/closure evaluation → SourceProofResult | Noncanonical proof отвергнут, исходный proof не исправлен |
| Group admission | Проверки всех исходных groups → union builder → exact capture/closure evaluation → groups result | Union точный, selections в исходном порядке, ошибки не теряют group/use indices |
| Group verification | Проверки исходного verify request → group matcher → exact capture/closure evaluation → сравнение предъявленных durable refs → groups result | Не только subset, но exact union, соответствие каждой группы и exact closure |
| Selection | Проверки исходного select request/proof/selection → extractor → exact capture/closure evaluation выбранного proof → SourceProofResult | Самостоятельный proof выбранных dependencies и его полный closure |

Closure evaluation — общий internal алгоритм из spec, а не вызов публичного read. Перенос диагностик в original request принадлежит request-specific стадии, без синтетического read input как diagnostic root. Проверки witness/captured mapping выполняются до утверждения durable result. Concrete IO ports и constructor wiring принимаются отдельно; до этого эти operation owners не могут быть реализованы с fake refs или stub collectors. Pure algorithms остаются независимым следующим кандидатом ядра.

## 4. Проверка полноты по принятой S1/S2 дельте

При сверке spec §13 обнаружены две обязанности, которые нельзя потерять при декомпозиции:

- `SourceProofSelector.check_coverage(input: SourceProofCoverageCheckInput) -> None | SourceFailure` — принятый internal контракт S1. Предложение разделения: отдельный `SourceProofCoverageChecker.check_coverage` с тем же input/result/semantics. Это отдельная проверка включения, не group matching и не origin authority. Перенос требует явного принятия дельты S1; прежнее размещение автоматически не меняется, forwarding facade ради сохранения смешанной ответственности не предлагается.
- `SourceCaptureRetentionBinding.collect_for_adoption(scope, request)` и `adopt(scope, request, sources, target)` — разные функции: read-only preflight внутри borrowed writer scope и acquire удержаний после повторной проверки. Предложение: preflight вынести в отдельный `SourceAdoptionPreflight`, adopt оставить в retention binding. Сохранить sequential scope lifetime, reset/finally и повторную проверку при adopt. Точные ports и перенос требуют отдельной дельты S2, а не молчаливой смены принятого интеграционного контракта.

Эти обнаруженные границы уточняют декомпозицию пункта 1. Они не разрешают менять код Pack/Snapshot/DAG или начинать S1/S2 runtime.

Адресная дельта S1/S2 для следующего согласования: Source предлагает `SourceProofCoverageChecker.check_coverage` вместо `SourceProofSelector.check_coverage`; `SourceAdoptionPreflight.collect_for_adoption` вместо одноимённого метода retention binding; `SourceCaptureRetentionBinding.adopt` остаётся владельцем acquire. Input/Result/Error и proof semantics прежние, holder authority не передаётся pure checker. Sequence collect/reset → register/resolve → повторные bind/collect/check/acquire/reset в adopt сохраняется. Общие read/check алгоритмы переиспользуются, второй collector не создаётся. Snapshot подтверждает constructor/scoped lifetime и calls; Pack — совместимость consumer результата. Перенос не считается принятым до этих подтверждений; forwarding facade не вводится. Разрешение междоменных scoped calls — отдельный обязательный INT-DAG-SCOPED gate, который SRP-перенос не закрывает.

## 5. Остальные операции ядра: точная граница дальнейшей работы

| Область | Что уже известно | Что предъявить до её реализации |
|---|---|---|
| Revision classification/transition | Разделены pure решение и append; semantic evidence приходит готовым | Конкретные Source input/result/error и инварианты seq/hash/unchanged, без выдуманного owning projector |
| Mutation/recovery | Новое изменение и разрешение unknown outcome — отдельные обязанности | Отдельные публичные классы, методы и точные POJO; error/preflight/receipt/логирование, без автоматического retry mutation |
| Capture | SourceCaptureFinalizer.finalize(request: SourceCaptureWitness, *, lease: OperationLeaseRef) → SourceCaptureRef или SourceFailure — существующий internal контракт spec §12.2 | Не превращать его в публичный DAG API без отдельного решения; assembler/checker signatures и фактическая входная граница ещё нужны |
| Explicit prune | Source policy отделена от Artifacts GC | Exact request/decision/error для pure policy; holders и Source root — INT-ARTIFACTS-RETENTION |
| Descriptor configuration | Existing immutable SourceDescriptorRegistry | Точный lifecycle конфигурации/операции в архитектуре; отсутствие runtime CRUD не объявлять исключением из обязательных критериев без основания |

Это открытые Source design-задачи, не интеграционный техдолг. Неизвестные внешние реализации отложены отдельно; их отсутствие не оправдывает пропуск собственных типов и обязанностей.

## 6. Статус и приёмка

Предъявлена конкретная дельта публичного размещения пяти proof-операций с неизменными POJO и гарантиями. Проверка: одна функция каждого метода; отсутствие nested public calls; exact root diagnostics; read-only эффекты; нет новых DTO или wire IDs. Обязательные проверки DAG маршрута и CRUD всего домена не объявляются завершёнными этим документом.

До полной приёмки архитектуры остаются concrete constructor dependencies и typed internal signatures, собственные контракты revision/mutation/recovery/prune/configuration. Предложенные public names и переносы S1/S2 требуют согласования; independent review не выполнялся. Следующий шаг — предъявить internal pure signatures и Source-owned входы/результаты без IO; интеграции не разрабатывать автоматически.
