# Ревью контракта SourceDurableProof

Дата: 2026-11-13. Итог: **NOT ACCEPTED**.

Основной план: `world-source-versioning.md`. Спецификация: `source-proof-v2-contract-spec.md`, §10 совместно с §3, §6 и §9. Критерии: `.cursor/rules/dag-generator-interface.mdc`. Статическая проверка; runtime-тесты не запускались. Код, исходные планы, ТЗ и DAG не изменялись. Номера строк относятся к версии, прочитанной при ревью.

Отсутствие реализации само по себе не основание отклонять схему. Ниже отдельно отмечены дефекты проекта, незавершённая реализация и внешние зависимости. Отчёт не разрешает исправления или изменение согласованного порядка.

## Findings по приоритету

### 1. P1 — Не определён исполнимый lifecycle удержания finalized capture

Категория: незакрытый внутренний контракт; блокирует durable API.

Места: `.cursor/plans/source-proof-v2-contract-spec.md:198`, `:569`, `:575`.

§10 требует приобрести source capture holds на witness и closure, но не определяет конкретный holder, его корневое удержание и release lifecycle. §5 прямо оставляет выбор открытым. Требование «holding witness защищает dependencies» ещё не является конкретным binding.

В текущем `backend/app/db/repositories/sqlite/artifacts/holderStore.py:185` метод acquire принимает конкретный ArtifactHolderRef; retention owner должен быть sealed. Запись Source witness сама по себе такого владельца не создаёт.

Сценарий: finalize сохраняет witness, staging operation завершается, её holds снимаются. Без долговременного владельца capture/body могут стать доступны GC; restart-safe proof перестаёт читаться. Вечное self-hold, напротив, оставляет неописанным освобождение.

Рекомендация: закрепить holder/root, создание и seal witness в общей транзакционной модели, зависимости root→closure, release/GC и recovery. Показать signatures и rollback boundary. Это требуется для durable API, не для объявления полей POJO.

### 2. P1 — Каноническое представление и fingerprints не имеют закреплённого schema binding

Категория: незавершённый контракт сериализации.

Места: `.cursor/plans/source-proof-v2-contract-spec.md:457`, `:461`, `:587`.

Порядок определяется через CanonicalCodec.encode, но type IDs и manifest version оставлены зависимостью до реализации. От bytes зависят порядок atoms, indices selections и fingerprint.

Сценарий: две регистрации типов кодируют одинаковый логический proof разными bytes. После обновления composition прежняя selection получает другой fingerprint либо другую адресацию atoms.

Рекомендация: закрепить named canonical manifest, версии и IDs участвующих типов, import paths и сохранение старых bindings. Добавить эталонные векторы proof→bytes→fingerprint→atoms. Новый hash engine не нужен.

### 3. P2 — Диагностики не сведены в один принятый контракт

Категория: дефект полноты POJO/error-контракта.

Места: `.cursor/plans/source-proof-v2-contract-spec.md:184`, `:258–266`, `:463`.

§4 предлагает SourceFieldIssue и общие Source errors, §6 — proof-specific carriers с пересекающимися кодами. §6 прямо требует выбрать единую декларацию до реализации. Для descriptor registration, key adapter и finalize полного согласованного error mapping нет.

Сценарий: неизвестный descriptor или неправильный world получает разные carriers в identity validation и proof admission; независимые ошибки невозможно стабильно агрегировать в обещанный единый failure.

Рекомендация: предъявить единый roster: semantic condition → owning code → field/logic carrier → typed path → операция. Разделение ошибок по операциям допустимо; дублирование одной семантики без явного обоснования — нет.

### 4. P2 — Совместно читаемые разделы содержат несовместимые нормативные утверждения

Категория: дефект документации контракта.

Места:

- `.cursor/plans/source-proof-v2-contract-spec.md:206`: удержание всего capture как обязательная политика «не принято».
- Тот же файл `:237–239`, `:573`: полный capture closure — выбранный обязательный v1.
- `.cursor/plans/world-source-versioning.md:503`: label внутри SourceRevision.
- `.cursor/plans/source-proof-v2-contract-spec.md:547`, `:551`: revision содержит только seq/hash, label вынесен.

Сценарий: одна реализация SELECT удерживает только выбранные bodies, другая — весь capture; один codec включает label в revision representation, другой исключает поле. Обе могут ссылаться на действующие формулировки.

Рекомендация: явно пометить прежние решения superseded и синхронизировать основной план. Указание §10 о замене неопределённых identity/witness не устраняет автоматически все противоречия closure и revision.

### 5. P2 — Ответственность классов описана, но storage bindings недостаточно конкретны

Категория: незавершённый проект реализации.

Места: `.cursor/plans/source-proof-v2-contract-spec.md:404`, `:579–587`.

Для новых классов есть обязанности и признаки отказа. Однако signatures внутренних ports и diagnostics отложены; часть существующих участников представлена общими ролями Artifact ports и publication/Snapshot owner.

Сценарий: SourceCaptureFinalizationStore реализуют поверх неподходящего transaction adapter; witness commit и holders.acquire получают разные scopes. Названия ролей соблюдены, атомарность нарушена.

Рекомендация: до приёмки runtime-среза указать конкретные зависимости и методы, scope ownership, вложенные вызовы и ошибки. Сохранить запрет смешивания legacy UOW и unbound publication transaction.

## Корректно определённые свойства проекта

- Object и collection refs разделены типами; membership не подменяется набором выбранных объектов.
- Историческая live revision допустима после удаления latest; tombstone не используется как доказательство отсутствия.
- Witness доверен только через committed owning Source record. Seal или пользовательский JSON недостаточны.
- Multi-capture сохраняет разные исторические revisions одной identity.
- VERIFY_GROUPS проверяет exact union и соответствие каждой selection своей группе.
- Полный storage closure отделён от logical usage.
- SourceProofResult не является hold/token; acquisition и handoff вынесены из read-only proof operations.
- Pack хранит Source proof и отдельные Planning dependencies; зеркальные Pack DTO не предлагаются.

## Матрица обязательных критериев

PASS означает достаточность проектного правила, не подтверждение реализации.

| Критерий | Статус | Основание |
|---|---|---|
| Нет pipeline, выбирающего следующие операции | PASS | §6.D/G, §9.1: пять атомарных read-only операций; retry и следующие операции принадлежат DAG |
| Нет скрытой оркестрации | OPEN | Прямой DAG-вызов предписан, конкретный согласованный маршрут отсутствует |
| Нет прямых междоменных вызовов: проектное правило | PASS | Передача через DAG задана; Source не вызывает Pack |
| Нет прямых междоменных вызовов: concrete bindings | OPEN | Storage и Pack bindings ещё открыты |
| Роль, зависимости, эффекты, DoD и признак нарушения каждого класса | OPEN | §6.E, §10.5 покрывают новые классы частично; §7 оставляет роли вместо полного списка |
| Public contract → pipeline → internals, включая nested calls | OPEN | Пять signatures заданы; внутренние ports/storage errors не завершены |
| Утверждённый порядок, условия и зависимости | OPEN | Основной порядок сохранён декларативно; места SELECT/VERIFY_GROUPS в Pack не согласованы |
| Данные: Create | OPEN | §4 описывает алгоритм, не полный concrete CRUD API; вне узкого read-only proof-среза |
| Данные: Read, proof API | PASS | Concrete класс, методы и request/result/failure названы |
| Данные: Read, exact source/storage | OPEN | Exact source read/storage binding ещё проектный |
| Данные: Update | OPEN | Есть expected revision semantics, нет полного concrete CRUD-контракта |
| Данные: Delete | OPEN | Есть tombstone semantics, нет полного concrete CRUD-контракта |
| Настройки: Create | OPEN | Нет полного owning API/disposition; §4 отсылает к владельцам |
| Настройки: Read | OPEN | То же |
| Настройки: Update | OPEN | То же |
| Настройки: Delete | OPEN | То же; исключение для Source не предъявлено |
| Междоменный CRUD: источник → точные POJO → mapping → DAG | OPEN | §9.5 подтверждает потребности Pack, не exact result→bind/adoption |
| POJO: владельцы, поля, immutable-структура, отсутствие пересечений | OPEN | Основные records конкретизированы; diagnostics и canonical bindings не приняты |
| POJO типизированных field errors | OPEN | Finding 3 |
| POJO типизированных logic errors | OPEN | Finding 3 |
| Согласованность спецификации и основного плана | FAIL | Finding 4 |
| Конкретность durable storage/holds/recovery | OPEN | Findings 1 и 5 |

## Граница решения

**Схема: NOT ACCEPTED** из-за противоречий и незавершённых canonical/error bindings. Для её принятия не требуется мигрировать всех Source writers или реализовать весь CRUD домена. Строки полного CRUD в матрице не превращаются в блокер узкой схемы автоматически.

**Durable API: NOT ACCEPTED** дополнительно из-за незакрытого retention/finalization binding. В текущем коде при ревью объявления SourceDurableProof и SourceCaptureWitness не обнаружены — это отсутствие реализации, не самостоятельный дефект предлагаемой модели.

**Внешняя интеграция: OPEN** — точные Pack inputs, scoped adoption и согласованные DAG bindings. Их нельзя заменять прямым Pack→Source вызовом или требовать от Source самостоятельно изменить порядок DAG.
