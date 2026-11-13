# SourceDurableProof — исправления повторного ревью

Дата: 2026-11-13. Текущий статус: **ACCEPTED для проектных исправлений R1/R2 по независимому reviewer**. Основание и точная граница — [акт приёмки](source-durable-proof-contract-acceptance-2026-11-13.md). Runtime durable API и весь Source этим не приняты. Findings/матрица ниже описывают состояние до исправлений и сохранены как история.

Основание: повторное независимое ревью `source-proof-v2-contract-spec.md` (§11 совместно с §3, §6, §9–10), основного плана `world-source-versioning.md` и текущих Artifacts adapters. Предыдущее ревью: `source-durable-proof-contract-review-2026-11-13.md`.

## Скоуп поручения

Исправить проект контракта по двум findings ниже. Уточнить Source-owned signatures, ответственность и вложенную цепочку; синхронизировать затронутые формулировки спецификации. Основной план менять только в части необходимого устранения противоречий этих уточнений. Это поручение на исправление проектной документации, не на реализацию runtime, SQL, Pack DTO или DAG. Не менять утверждённый порядок операций и не назначать новые ноды.

Применить все обязательные критерии `.cursor/rules/dag-generator-interface.mdc`. Все ручные правки — через apply_patch. Для любых последующих изменений кода обязателен implement-plan; данный план их не разрешает. Исходный отчёт первого ревью не переписывать. Исправление не считать самостоятельной приёмкой.

## R1 / P1 — Проверяемая полнота closure при adoption

Места повторного ревью: `source-proof-v2-contract-spec.md:608`, `:641`, `:668` (номера до исправления).

Метод `adopt(scope, refs, source, target)` получает только tuple refs и holders. При этом описание обещает проверку exact complete closure и world/capture. В сигнатуре нет proof/capture, относительно которого устанавливается полнота; происхождение tuple от owning Source closure read описано словами, но не замкнуто конкретной цепочкой вызовов.

Сценарий нарушения: caller передаёт witness и capture body, пропустив обязательный object body. Все переданные refs sealed и held. По доступным аргументам adopt приобретает target holds, не обнаружив пропуск. После release исходного holder пропущенное тело собирается GC.

### Требуемое исправление

Выбрать и однозначно описать один вариант:

1. Передать точный proof и выполнять owning closure verification внутри защищённого scope.
2. Ограничить adopt приобретением уже проверенного множества и предъявить конкретного caller, который получает полный closure и вызывает acquisition в одной защищённой границе.

Не создавать зеркальные DTO или фиктивные tokens лишь ради переноса tuple. Не заявлять проверку полноты у метода, которому недоступно её основание. Показать typed input/result/error, source/target holder checks, порядок проверки до первого append, rollback при ошибке после записи и защиту от concurrent release/GC. Release остаётся отдельной обязанностью owning lifecycle.

### Критерий приёмки

По concrete signatures и вложенной цепочке можно проследить основание полноты каждого refs набора до exact proof/capture. Missing/extra ref отклоняется либо исключён построением множества внутри owning boundary; untrusted tuple не принимается за удостоверенный closure. Проверка и acquisition не разделены незащищённым окном GC. Сценарий выше не приводит к успешному неполному adoption.

## R2 / P2 — Конкретный владелец атомарной finalize-операции

Места повторного ревью: `source-proof-v2-contract-spec.md:630`, `:659–670` (номера до исправления).

Последовательность reserve → writer claim → transaction → revision verification → append → verify → seal → holds → commit/recovery определена, но concrete класс и метод, выполняющие её целиком, не названы. SourceCaptureFinalizationStore.append отвечает только за SQL state; read-only proof pipeline не может стать finalize owner.

Сценарий нарушения: callers самостоятельно собирают finalize из внутренних стадий и по-разному обрабатывают отказ после append, закрытие writer claim или неизвестный исход commit. Все отдельные ports существуют, но атомарная операция не обеспечена единым владельцем.

### Требуемое исправление

Назвать concrete internal finalize owner, модуль и полную сигнатуру. Указать caller, typed input/result/errors и допустимые зависимости/эффекты. Проследить все вложенные вызовы и принадлежность общей transaction capability.

Явно определить ранний путь идемпотентного возврата ранее committed результата, same uid/different content conflict, поведение после GC, rollback после первого write, закрытие writer claim и unknown commit recovery. Не подменять успешный historic lookup проверкой latest revisions. Сохранить источник доверия committed witness и невозможность признать один seal финализацией.

Не вводить новую DAG-ноду или публичный Source orchestrator. Caller не должен управлять внутренними стадиями finalize.

### Критерий приёмки

Одна concrete атомарная операция владеет полной последовательностью и имеет проверяемые границы ответственности. Store не становится orchestration owner, proof pipeline остаётся read-only. После любой ошибки нет частично committed witness/holds; неизвестный commit outcome разрешается через существующий recovery и exact capture identity, а не новым uid.

## Уже закрытые замечания — сохранить

- Canonical manifest v1, IDs, field order, schema_version и fixed vectors определены в §11.4; runtime round-trip ещё предстоит.
- Единый Source error roster и mapping определены в §11.3; не возвращать дубли SourceProofFailure/SourceFieldIssue разных семантически совпадающих семейств.
- Противоречия полного closure и label устранены: full capture closure v1 отделён от logical usage; label вынесен из SourceRevision.
- OperationHolder удерживает каждый ref явно; hold witness не удерживает зависимости автоматически.
- Object/collection refs, exact historical revisions, multi-capture, exact union и per-group selections сохраняются.

## Матрица повторного ревью до исправлений

PASS означает проектное правило, не готовность runtime.

| Критерий | Статус | Основание |
|---|---|---|
| Запрет pipeline с выбором следующих операций | PASS | Proof read-only; retry/следующие операции у DAG |
| Запрет скрытой оркестрации | OPEN | Concrete DAG binding не согласован |
| Запрет прямых междоменных вызовов | PASS | Проект сохраняет передачу через DAG |
| Ответственность каждого класса | OPEN | R2: отсутствует finalize owner |
| Public contract → pipeline → internals | OPEN | R1/R2 |
| Утверждённый порядок | OPEN | Source-порядок сохранён; места SELECT/VERIFY_GROUPS в Pack — внешний gate |
| Данные: Create | OPEN | Полный Source CRUD вне узкой proof-схемы |
| Данные: Read | PASS | Concrete proof signatures; runtime не предъявлен |
| Данные: Update | OPEN | Полный CRUD не предъявлен |
| Данные: Delete | OPEN | Полный CRUD не предъявлен |
| Настройки: Create | OPEN | Полный owning CRUD/disposition не предъявлен |
| Настройки: Read | OPEN | То же |
| Настройки: Update | OPEN | То же |
| Настройки: Delete | OPEN | То же |
| Междоменный CRUD: источник → POJO → mapping → DAG | OPEN | Pack adoption/inputs и DAG bindings — внешние зависимости |
| POJO: поля, immutable, ownership, отсутствие дублирования | PASS | Для proof-схемы конкретизировано |
| Field errors | PASS | Единый carrier и typed paths |
| Logic errors | PASS | Единые SourceLogicIssue/SourceFailure |
| Canonical equality/fingerprints/selections | PASS | Versioned manifest, exact union и per-group matching |
| Согласованность по прежним closure/label findings | PASS | Синхронизировано |
| Конкретность finalize/adoption/rollback | FAIL | R1/R2 |

## Порядок работы и результат

1. Сверить R1/R2 с актуальными файлами и текущими storage contracts; сохранить чужие изменения.
2. Уточнить R1, затем R2, не меняя runtime порядок стадий.
3. Синхронизировать повторяющиеся signatures/обязанности в спецификации и необходимые ссылки основного плана.
4. Показать diff и трассировку двух сценариев нарушения, указать точные места исправлений и оставшиеся внешние gates.
5. Предъявить исправленный проект для независимой повторной приёмки; не выставлять ACCEPTED самостоятельно.

Полной миграции writers и завершения внешней Pack/DAG интеграции для приёмки полей proof не требовать. При этом durable API не объявлять готовым без реализации и проверки требуемых механизмов. Отсутствие runtime отделять от дефектов проекта.

## Исполнение Source — предъявлено для повторной приёмки

**Последующее независимое решение:** R1/R2 приняты; новых блокирующих дефектов в проверенных изменениях нет. Формулировки NOT ACCEPTED/«ожидает review» в записи предъявления ниже относятся к моменту до этого решения. Текущий verdict и оставшиеся OPEN зафиксированы в отдельном акте; заново исправлять R1/R2 не требуется.

2026-11-13: проектные исправления внесены в `source-proof-v2-contract-spec.md` §12, signatures и ответственность синхронизированы в §7, §10.5 и §11.1–2. Исходные findings и матрица выше сохранены как результат проверки до исправлений. Статус остаётся NOT ACCEPTED до независимого review.

- R1: `SourceCaptureRetentionBinding.adopt(scope, request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef, ...], target) -> SourceProofResult | SourceFailure`. Exact closure вычисляет owning collector внутри того же write scope; sources проверяются против него до первого acquire. Missing/extra pairs отклоняются; release не выполняется. Точный nested trace и сценарий пропущенного body — §12.1.
- R2: `SourceCaptureFinalizer.finalize(request: SourceCaptureWitness, *, lease: OperationLeaseRef) -> SourceCaptureRef | SourceFailure`, caller — internal SourceCaptureAdapter.finalize_capture. Finalizer владеет ранним replay, повторным find под writer scope, new-finalize transaction, rollback, writer cleanup и правилами unknown outcome. Store остаётся SQL-only, proof pipeline read-only. Подробный trace — §12.2.
- Canonical IDs/version/vectors, error roster, full closure v1 и label решение не менялись. Дополнительные persisted DTO, tokens, OperationKind, runtime/SQL, Pack DTO или DAG-ноды не создавались. Основной план не потребовал изменения.
- Внешние gates: Pack/Snapshot mapping, public capture/DAG binding и pregame revision staging. Они не подменяют внутренние обязанности R1/R2.

Проверка текущего шага — статическая сверка документа с signatures Artifacts и перечитывание diff. Runtime-тесты не запускались: изменений кода нет. Повторную независимую приёмку выполняет reviewer, не автор исправления.
