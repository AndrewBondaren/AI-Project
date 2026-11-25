# Source: остаток архитектуры на 2026-11-24

Единый рабочий список по запросу пользователя. Это консолидация уже выявленных пунктов, не новые требования и не разрешение локальных implementation-срезов. Полная архитектура — CHANGES REQUIRED; внешние интеграции не являются причиной отказа в приёмке независимых контрактов ядра. Новых вопросов пользователю на момент фиксации нет.

## Собственная работа Source

| Пункт | Что осталось | Конкретный результат закрытия |
|---|---|---|
| АР-2: композиция исполнения | Спроектирована; 2026-11-26 after-graph checker включён в общую карту §9.1; нужна приёмка | §9.4 содержит signature, before/after membership, корреляцию surviving_targets с CREATE/UPDATE/DELETE и запрет append при нарушении. §9.1 закрепляет historical execution_version validation. Foreign run/append capability отделён |
| АР-2: единое revision rule | Проект конкретизирован 2026-11-25, нужна приёмка; runtime отсутствует | mutation-contract §2: revision/revisionRule.py::next_revision, exact signature/callers/DELETE precondition и критерии; нет dataModel→application импорта |
| АР-1/2: typed errors | Собственная дельта предъявлена 2026-11-25; требуется координация/приёмка | source-core-error-contract.md: condition→carrier/code/context, три proposed code additions, полнота/localization/postconditions; runtime не изменён |
| АР-3/4: finalization и prune | Исправления F1/F2/F3 предъявлены проектами; требуется повторная приёмка, не повторное проектирование | Candidate closure collect_candidate описан в source-x-read-internal-boundary.md; candidate checker, prune admission/policy, public preview/confirm, Input/ConfirmInput/Preview/Result и operation tags описаны в capture-prune-configuration §1–2. Код/интеграция не заявлены; foreign bindings отдельно |
| АР-5: configuration lifecycle | Архитектурное разграничение принято по предложению пользователя 2026-11-26, §3 capture-prune-configuration | Registry — application composition; definitions — immutable configuration; revisions — domain data; foreign settings — owning CRUD. Runtime settings CRUD Source неприменим. Historical compatibility остаётся критерием реализации; это не PASS всей архитектуры |
| АР-6: консолидация | Синхронизировать signatures, predicates, localizers, actual/proposal/historical статусы | Один нормативный вариант каждого контракта, точные ссылки из матрицы; старый scope/adoption не читается как OPEN задача |
| АР-6: архитектурное ревью | Проверить весь собственный план после консолидации | Для каждого класса/POJO: путь, ответственность, поля/методы/функции, зависимости/эффекты и критерий нарушения; проверены вложенные calls, POJO/error ownership и порядок. Собственная проверка не называется независимой приёмкой |

Подробности: source-core-mutation-contract.md, source-core-capture-prune-configuration.md, source-x-read-internal-boundary.md, source-core-public-boundaries.md и source-core-responsibility-matrix.md. Наличие проектных signatures или тестовых сценариев само по себе не закрывает перечисленные пункты.

## EXTERNAL / DEFERRED

| Зависимость | Владелец | Интеграционный результат |
|---|---|---|
| X-READ materialized transport | Artifacts | Exact BLOB/SQL_ROWS Input/Output/Error; Source затем связывает owning типы с пятью public inputs и internal collector |
| Authority/protection и retention до target | Publication infrastructure / Artifacts | Подтверждённые issuer/evidence/lifetime и handoff; Source не управляет holders |
| Producer полного перечислимого набора | Назначение через координатора | Достаточный исходный набор и consistency/correlation; без hidden Source IO или самовольного DAG loop |
| Owning semantic/format evidence | Соответствующий body/format domain | Exact projection/required dependencies; Source не интерпретирует foreign schema за владельца |
| Writer/terminal/recovery binding | Owning writer + Snapshot/publication/Artifacts в пределах их ответственности | Допустимая write capability, atomicity, terminal registration/read и confirmed/unknown outcomes; без прямого Snapshot→Source adoption |
| Serialization с gameplay start | Owning phase/commit boundary через координатора | Exact authoritative guard и отказ concurrent transition; ранний phase read недостаточен |

Эти зависимости регистрируются в source-technical-debt.md. Они не блокируют собственную детализацию и приёмку независимых контрактов Source, но до их закрытия нельзя объявлять production proof/mutation runtime готовым. Time/Lifecycle nodes не получают prerequisite завершить Source.

## Порядок продолжения

Доработать собственную композицию АР-2; проверить оставшиеся собственные обязанности АР-3/4 и configuration АР-5; затем свести АР-1…АР-6 и предъявить целую архитектуру на ревью. Новая реализация идёт по принятому плану через implement-plan, без искусственных локальных срезов. Прогресс фиксируется изменением конкретной строки этого списка с evidence, а не общим утверждением «всё закрыто».
