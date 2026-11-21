# Source — пакет междоменного согласования

2026-11-19. Для координатора **Between domain operations**, `01a1ef35-3287-7a12-89e2-76273eaa043d`. Статус: OPEN, не приёмка и не разрешение реализации. Правило: interdomain-contract-coordination.mdc. Документ сводит границы и gaps, не заменяет owning specs и не назначает ноды.

## 1. Решения и пределы

- Пользователь отклонил прямые Snapshot → Source check_coverage/preflight/adopt. Internal/DI/borrowed scope не дают исключения.
- Выбрано направление А: Source preparation через DAG, затем publication с атомарным target retention без вызова Source из Snapshot. Exact binding не принят.
- Рекомендована защита исходного удерживаемого набора целиком во время раскрытия closure. Возможны несколько наборов исторических captures. Это требование, не доказательство существования API.
- Source вычисляет semantic closure; Artifacts обеспечивает защиту/holders/GC; Publication владеет transaction/recovery. Точный binding владельцы предъявляют координатору.
- Конкурентность DAG и внутренние domain workers разделены. Scope не переносится workers автоматически. Own read lifetime поддержан ответами DAG/Snapshot как вариант; политика inherited binding требует owning API.
- Полная архитектура Source ещё не принята. Proof POJO/encoding поставлены; A0→D имеет независимый PASS. Public IO runtime отсутствует; новые локальные implementation-срезы запрещены.

## 2. Публичный proof-контракт

Superseded historical — прежний baseline spec §9.1: `app.application.worldData.sourceVersioning.sourceProofPipelineOpenPipeline.SourceProofPipelineOpenPipeline`, интерфейс `app.application.worldData.sourceVersioning.interfaces.sourceProofPipelineOpenPipeline.ISourceProofPipelineOpenPipeline`. Единый класс отозван как целевая структура; эта строка сохраняет только историю design, не доступный runtime и не инструкцию к реализации.

Принятый пользователем 2026-11-21 layout: пять отдельных owners в `app.application.worldData.sourceVersioning.operations`, перечисленных ниже; он синхронизирован с актуальным spec §9.1. Все методы async; signature каждого `method(self, request: Input) -> Output | SourceFailure`. Принятие layout не означает готовность runtime или принятие оставшихся bindings.

| Модуль / класс | Метод / Input | Output |
|---|---|---|
| proofAdmissionPipelineOpenPipeline / SourceProofAdmissionPipelineOpenPipeline | admit / SourceProofInput | SourceProofResult |
| proofReadPipelineOpenPipeline / SourceProofReadPipelineOpenPipeline | read / SourceProofReadInput | SourceProofResult |
| proofGroupAdmissionPipelineOpenPipeline / SourceProofGroupAdmissionPipelineOpenPipeline | admit_groups / SourceProofGroupsInput | SourceProofGroupsResult |
| proofGroupVerificationPipelineOpenPipeline / SourceProofGroupVerificationPipelineOpenPipeline | verify_groups / SourceProofGroupsVerifyInput | SourceProofGroupsResult |
| proofSelectionPipelineOpenPipeline / SourceProofSelectionPipelineOpenPipeline | select / SourceProofSelectInput | SourceProofResult |

Открыты полные constructors, owning data-input binding и protection-контракт; выбор layout и разделение request/persisted validation уже приняты и не являются OPEN. Не реализовывать исторический единый класс параллельно принятому layout.

POJO prefix `app.dataModel.sourceVersioning`: sourceProofInput — Input/ReadInput; sourceProofGroups — GroupsInput/GroupsVerifyInput/GroupsResult; sourceProofSelection — SelectInput/Selection; sourceProofResult — Result; sourceErrors — SourceFailure/SourceFieldIssue/SourceLogicIssue. Имена в этой строке сокращены только для навигации; полные имена — таблица и actual modules. SourceDurableProof — sourceDurableProof; SourceCaptureUsage — sourceCaptureUsage; SourceCaptureRef — sourceCaptureRef.

Producer формирует полноту declared usage. Source нормализует/проверяет usage по finalized captures, exact union/subset и полный durable closure; не удостоверяет алгоритм producer. Все пять операций read-only: не создают captures/revisions/holds и не выполняют adoption. SourceProofResult не lease/retention receipt. Empty/partial/fake proof не заменяет отсутствующее происхождение.

## 3. Mapping процесса и необходимые уточнения

| Граница | Известный mapping / статус | Следующий ответ |
|---|---|---|
| Producer → Source | SourceProofInput(world_uid, uses); groups сохраняют исходный порядок | Owning producer должен назвать конкретный output/поля и completeness guarantee |
| Source → Pack | Result.proof → PackStoredProvenance.source_proof; planning dependencies отдельно | Pack подтверждает конкретный consumer binding; это не обязательная стадия каждой записи |
| Source → общий write_changes | Готовый proof/refs не являются native section | Координатор и consumer определяют конкретную секцию/потребность; source refs сами по себе не требуют Source вызова |
| Artifacts protection → Source IO | Exact Input/Error и разрешённый маршрут OPEN | Artifacts: authority, покрытие roots/dependencies, lifetime, отсутствие окна GC |
| Source result → publication | Variant A; admission evidence и target-retention mapping OPEN | Publication/Artifacts: binding exact proof/closure/operation к публикуемым данным; не verified bool/hash вместо authority |

Source mutation не относится к этой read-only поверхности. source-core-mutation-contract.md §8.1 — proposal apply/recover, новые исполняющие попытки pregame-only. Для общей runtime записи Source revision preparation/native section и atomic write binding OPEN. Не создавать write_source из proof admission.

## 4. Сквозные гарантии для проверки

Защита исходных наборов существует до первого read и покрывает раскрываемые зависимости. Concurrent release не снимает её посередине обхода. Source вычисляет точный closure; его удержание подтверждается до окончания временной защиты. Исходное удержание самой публикации Source не освобождает. Publication атомарно закрепляет target retention и публикацию. Это требования к цепочке, не разрешение прямых междоменных calls.

Каждый invocation имеет локальные diagnostics/state. Нельзя молча очистить inherited binding или выдать его отказ за MISSING_BODY. Infrastructure/cancel/unknown outcome отделены от SourceFailure; неизвестный исход acquire не означает отсутствие удержания. Результат не выдаётся до обязательного cleanup. Workers получают immutable данные; storage reads в workers требуют отдельного owning контракта согласованности версии/connection/retention.

Проверки цепочки: concurrent invocations, root→dependency GC race, несколько historical captures, concurrent release, stale между preparation/commit, replay и payload conflict одной operation, cancellation SQL/compute, rollback/unknown outcome, отсутствие частичной публикации/потери защиты. Тесты этим пакетом не заявлены.

## 5. Конкретные конфликты и порядок закрытия

1. В artifacts-public-staging-dag.md на момент чтения остаётся **proposal** с internal Source adopts и scoped finish. Это несовместимо с отказом пользователя от Snapshot→Source; не считать разрешённым вариантом А. Исправление цепочки — через координатора и владельцев, не Source самостоятельно.
2. Own public read lifetime имеет existing механизм, но exact unbound policy и Artifacts public read/protection не подтверждены. Актуальный чат Artifacts активен; полный ответ по Source запросу не принят.
3. Source-owned occurrence mapping/collector delta — proposal source-core-occurrence-mapping.md. Требует проверки всех callers после замены S1/S2, не переноса старых scoped callers как prerequisites.
4. Сначала владельцы предъявляют existing/proposed публичные POJO/API без дублей; затем координатор сверяет Output→Input, effects, identity/version, lifetime и все обязательные критерии; итог PASS/OPEN/FAIL предъявляется пользователю. Никакой новый code scope не возникает автоматически.

Требуемый результат координатора: disposition K6 (когда Source нужен, когда пропускается), адресные вопросы владельцам, разрешённый target trace без запрещённых calls, список exact контрактных дельт и оставшихся OPEN. Полный Source АР-1…АР-6 и CRUD не принимаются этим пакетом.

Источники: source-proof-v2-contract-spec.md §§9/11.3/12.1; source-core-public-boundaries.md; source-core-occurrence-mapping.md; source-core-mutation-contract.md; source-technical-debt.md; dag-multidomain-patch-publication-draft.md K6; artifacts-public-staging-dag.md. Действующее обязательное правило — interdomain-contract-coordination.mdc.
