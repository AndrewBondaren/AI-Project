# Переход Pack на публичные staging и completion

## Скоуп — 2026-11-21

Пользователь поручил оформить рекомендации после сверки Artifacts staging architecture. Это адресная контрактная работа без кода. Независимый staging-срез продолжается при сохранении действующих lifecycle-контрактов; весь completion не становится его автоматическим prerequisite. Удаление старого фасада и готовность полного Pack-маршрута требуют отдельного завершённого cutover.

Источники: [Artifacts architecture](artifacts-staging-architecture.md), [completion](publication-preparation-completion-contract.md), [Pack public operations](pack-v2-public-write-operations.md), [H2](publication-h2-persistence-proposed.md).

## Узкая зависимость Artifacts writer

Владелец Artifacts предъявляет exact constructor ArtifactStageWriter и минимальную границу lease admission/writer claim. Сначала reuse существующего подходящего интерфейса. Если его нет — предложить минимальный structural protocol только реально используемых методов, реализуемый existing adapter. Новые lease engine/store/state machine и зеркала POJO не вводятся. Exact API ещё OPEN, эта запись его не назначает.

Новый stage возвращает ArtifactRef и не переносит terminal R. Concrete lifecycle adapter сохраняет single-R и owning configuration validation; existing lifecycle consumers сохраняют record_model/result_binding identity. Узкий тип зависимости writer не отменяет этих construction checks и не означает удаления lifecycle реализации.

## Карта перехода к owning уточнению

| Текущий участок | Целевая граница | Вход / результат и оставшееся уточнение | Условие замены |
|---|---|---|---|
| finish_pack_preparation: manifest encoding и Pack checks | Owning Pack операция; результат передаётся DAG | Exact owning output с content/evidence предъявляет Pack; semantic checks остаются у Pack | Проверено сохранение состава, descriptor и provenance checks |
| Прямой manifest_stager.stage | DAG вызывает Artifacts prepare_stage, затем stage | ArtifactPrepareStageInput → PreparedArtifact; ArtifactStageInput(lease, prepared) → ArtifactRef; concrete binding и identity gates у Artifacts | Зарегистрированный путь проверен; callers старого helper учтены |
| Прямой staging.finish_preparation | Один public completion Publication | Exact public Input/Result/Error OPEN; внутренние acquisition/exact set/candidate/READY в одном UOW | Owning контракт согласован и реализован; rollback/unknown/cancel/replay проверены |
| Конструирование PreparedPackCandidate в helper | Выдача готового candidate только после confirmed completion | Кто возвращает existing candidate и как сохраняется exact binding, подтверждают Pack/Publication без mirror DTO | Нет выдачи готового candidate до commit и повторного staging при READY replay |

Таблица задаёт границы, не новые NodeId и не разрешение изменить утверждённый порядок. Полный producer/input-preparation rollout сюда не включается.

## Адресные результаты владельцев

1. Artifacts: exact writer constructor/lease boundary, источник существующего интерфейса либо минимальная proposed дельта; подтверждение сохранения H2 identity на lifecycle стороне.
2. Pack: inventory production/test callers finish_pack_preparation; disposition описания PackPreparationOperation со stage/finish внутри; exact owning producer/consumer поля и момент формирования candidate. Старый путь обозначить existing до cutover, не целевым DAG-контрактом.
3. Publication: пакет по [completion](publication-preparation-completion-contract.md), включая authoritative source protection и persisted replay после release/cancel/publication. Запрос уже направлен; signatures не выдумываются до ответа.
4. Координатор: свести Output → Input и последовательность после owning ответов; предъявить ограниченный вердикт пользователю. Общая приёмка ARCH-STAGE/ARCH-0 этой записью не выдаётся.

До consumer cutover старый ArtifactStagingService/IArtifactStaging сохраняется. Его удаление не включается скрыто в extraction writer. Незавершённый переход Pack не считается доказательством готовности всего runtime и не блокирует независимые работы без этой зависимости.
