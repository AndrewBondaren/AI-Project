# Три замечания Source: исполнение и внешняя приёмка

Дата: 2026-11-14. Реализация runtime не выполняется. Это контроль фактического выполнения поручения, не заявление общей приёмки.

| Действие | Выполнено | Остаток |
|---|---|---|
| Учесть Source responses и единый SourceFailure | Exchange учитывает select correspondence, grouped admission, full closure и internal adoption; активные Source signatures/SourceNodeError в DAG families исправлены; transition roster больше не требует proof error mirrors | Исторические отозванные схемы и явные запреты создавать SourceProofFailure сохранены как история, не runtime contracts |
| Привязка DAG result к исполненному запросу | Получен [ответ владельца DAG](dag-pack-source-binding-response-2026-11-14.md): существующий CALL подходит; caller/order сохраняются. Sequential wait получил next_index/completed; bind fields сведены к source_request/source_result | Полная приёмка отклонена: A1 — все семь continuation-фаз, A2 — exact upper contracts/registration, A3 — Pack errors, A4 — trusted entry/store/restore и lifetime. Предложение сузить upper unions ещё не согласовано |
| Внешний adoption и closure до READY | Получен [ответ Artifacts/publication](pack-source-adoption-publication-response-2026-11-14.md): предложен PackPreparationRetention.adopt_and_finish, OperationHolder и scoped finish в единой transaction | DESIGN OPEN: trusted caller и полномочия sources, immutable preparation binding/replay evidence, operation kind, scoped finish port, Pack error mapping, post-READY holder lifetime. Принятого готового внешнего entry в проверенном коде нет |

Review передан 2026-11-14 в существующие чаты: DAG — 01a1d598-f2e7-7fc1-8c3a-f4386cbfa6a6; Artifacts/publication — 01a1a0c5-931c-77a0-96a5-cb5b6ca6766f. Runtime/новые ноды/хранилища не поручались. Конкурирующие правки Pack документов не поручались.

Документы: [exchange](pack-source-exchange-contract.md), [engine binding](pack-source-dag-execution-binding.md), [leaf acceptance A1–A4](pack-source-leaf-acceptance.md). A1 partially corrected (prefix накопления), A3 field divergence исправлена; full errors/phase/registration acceptance этим не закрыта.

## Результат согласования

Первое замечание выполнено в активных документах. По второму подтверждён механизм, но не полный маршрут. По третьему получено конкретное предложение владельца, а не приёмка внешнего entry. Все три замечания закрытыми не считать; runtime реализация и её приёмка не выполнялись.

Принятый Source internal adopt не меняется. Предложенная publication transaction выполняет все adopts, затем scoped finish и COMMIT; ошибка любого adopt откатывает новые holds всех предыдущих, source holds не снимаются, READY возвращается только после подтверждённого COMMIT. Это предложение инфраструктурной границы, не разрешение Pack вызывать Source и не новый порядок DAG. Успешный READ не является live hold.

Дальнейший объём разделён по владельцам: DAG — полный continuation/upper/restore контракт; Pack — semantic errors, final-state proof coverage и immutable preparation identity; publication/Artifacts — authority источников, scoped finish, operation lifecycle и retention handoff совместно с Pack. Независимая работа Pack этим не блокируется. Сужение общих upper unions и новый publication entry нельзя молча считать утверждёнными изменениями контрактов.
