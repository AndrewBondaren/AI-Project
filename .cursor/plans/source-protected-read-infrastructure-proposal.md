# Source — отложенный вариант общего защищённого storage-механизма

2026-11-21. Отдельное предложение по поручению пользователя. **DEFERRED; не принято для реализации и не prerequisite текущего Source.**

## Контекст и действующее решение

Для текущей архитектуры пользователь выбрал первый вариант: Artifacts получает/проверяет exact данные через собственную публичную операцию, DAG передаёт согласованный owning результат в Source. Source вычисляет semantic proof/closure по переданным данным, не вызывает публичную операцию Artifacts. Полнота переданного набора, authority, форматы BLOB/SQL_ROWS и непрерывная защита исторических captures требуют exact контрактов владельцев через координатора Between domain operations. Ни новый универсальный bytes-container, ни фиктивный пустой набор не вводятся.

Отложенный второй вариант: Source получает exact данные через явно разрешённый общий storage-механизм с подтверждённой защитой. Его нельзя считать разрешённым на основании слова «инфраструктура», DI или расположения классов. Это возможное будущее решение, а не способ сохранить запрещённый прямой междоменный вызов.

## Условие возврата

Вернуться только при подтверждённой потребности: стоимость передачи/материализации данных первого варианта, объём closure или повторные exact reads. Предъявить измерения либо конкретный сценарий. Не расширять текущую реализацию Source ради гипотетической оптимизации.

## Порядок проектирования

1. Инвентаризировать существующие Artifacts/Publication POJO, public методы, storage contracts и владельцев; исключить дубли.
2. Предъявить границу общего механизма: кто выполняет IO, semantic admission и authority, какие вложенные вызовы разрешены. Публичные методы/пайплайны доменов не называть frontend API.
3. Установить exact Input/Result/Error, version/identity, protection lifetime и coverage root→dependencies; Source по-прежнему определяет semantic closure, Artifacts — защиту/GC.
4. Проверить concurrent DAG invocations отдельно от domain workers: task/thread/connection ownership, cancellation/drain, отсутствие ambient scope authority и выдачи результата до cleanup.
5. Подтвердить отсутствие окна GC и совместимость с вариантом А публикации: атомарный target retention/publication без Source calls из publication.
6. Передать координатору общую цепочку; решение пользователя и отдельная архитектурная приёмка до implementation-plan.

## Отказ в приёмке

Скрытый междоменный pipeline, новый transaction/holder engine без основания, mirror DTO, неподтверждённый borrowed scope, потеря original diagnostics, latest fallback, неизвестная protection authority или ослабление cleanup. Прямой Snapshot→Source adoption остаётся запрещённым.

Код, сигнатуры нового storage port, новые DAG-ноды и порядок реализации этим предложением не назначаются. Источники: source-technical-debt.md; source-core-public-boundaries.md; interdomain-contract-coordination.mdc.
