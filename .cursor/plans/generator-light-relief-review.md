# LIGHT-RELIEF-REVIEW — ревизия рельефа в light_bake

**Дата:** 2026-11-02. **Статус:** документальная ревизия / OPEN, не implementation acceptance.

Предмет: классы рельефа и фактический light-путь, описанные в [инвентаре LIGHT-RELIEF](./generator-light-relief-classes.md). Owning requirement: [GEN-SURFACE-PLAN](./generator-public-surface-planning.md).

Этот документ хранит выводы ревизии отдельно от инвентаря. Он не меняет зафиксированные ноды, их контракты/родство или имена ещё не принятых Pipeline.

## 1. Метод и пределы подтверждения

Проверены исходники HTTP caller, DI, registry registration/dispatch, planning entry/assembler, relief providers, mountain geometry pipeline, L0 contributor factory/order и writer/publisher calls.

**Подтверждение статическое:** найденные caller→callee связи существуют и согласуются с проверенным DI. Bake не запускался; runtime trace, производительность, численная корректность рельефа и end-to-end recovery не проверены. Подтверждение вызова не означает, что операция действительно исполнилась в конкретной сессии.

На cache hit PlanningService возвращает проверенный envelope без повторного provider build. GEO/native пути не объявляются активными по одному наличию класса. Исследованы backend/app связи; отсутствие найденного caller там не доказывает отсутствие callers в tests/scripts или иных конфигурациях.

## 2. Подтверждённые факты

1. HTTP pack bake получает `surface_materialization_orchestrator`, вызывает `bake_pack`; mode=light делегирует в `PackMaterializationOrchestrator.materialize_light_pack`.
2. Проверенный DI регистрирует baseline `TerrainPlanProvider`, `ReliefPlanProvider`, `RiverReliefPlanProvider` через `register_world_plan_providers`.
3. SurfacePlanningAssembler получает планы через PlanningService/PlanRegistry; provider build вызывается при необходимости вычисления, а не безусловно.
4. ReliefPlan содержит coarse surface, mountain layout и frozen light effects. Геометрия гор растеризуется при подготовке light relief.
5. L0 contributors применяют frozen base/mountain/ravine effects. `MountainContributor.apply` вызывает `apply_plan`, а не повторную `materialize` горной формы.
6. NativeRiverReliefPublicationJob оформляет проверенный PlanEnvelope; просмотренная реализация не является world/pack activation.

Поштучные evidence links и цепочки вызовов находятся в [разделах 1–5 инвентаря](./generator-light-relief-classes.md#1-подтверждённый-вход-и-управление).

## 3. Подтверждённые расхождения с целевыми требованиями

Это миграционные разрывы AS-IS → target, не утверждение о новых production-регрессиях. Первые два уже обсуждались в общем light-разборе; здесь зафиксированы их конкретные места в relief/light цепочке.

### LR-R1 / P1 — подготовка не отделена от writes/publication

**Факт:** общий L0 pipeline пишет locations index и world-map tiles, сохраняет relief-grade records и вызывает publisher. Наружу возвращается диагностический MaterializationJobReport, а не целостный staged light result.

**Evidence:** [вызовы L0 и relief persistence](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:217), [publisher](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:254), [WorldMap writer](../../backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py:161).

**Следствие:** текущую операцию нельзя напрямую принять за target «child готовит — parent публикует». Успех compute/число клеток не подтверждает подготовленный или опубликованный комплект.

**Условие закрытия:** domain-owned prepared result связывает L0 artifacts и обязательные сопутствующие records с scope/source evidence; публикация выполняется отдельным принятым entrypoint под управлением DAG parent. Старые writers не удаляются до согласованного cutover.

### LR-R2 / P1 — incremental preparation не ограничена missing-частями

**Факт:** `_materialize_l0_pack` передаёт все planned tiles в `bake_tiles`; комментарий явно указывает overwrite всех planned tiles. Проверка актуальности и вычитание готовых частей перед этим вызовом в просмотренном методе отсутствуют.

**Evidence:** [all planned tiles overwrite](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py:220).

**Следствие:** метод не удовлетворяет target требованию «из 10 требуемых тайлов при 7 актуальных готовить 3». Один planning cache не устраняет повторную запись L0.

**Условие закрытия:** принятый domain contract использует authoritative missing/reuse evidence и готовит требуемые недостающие части. Stale/corrupt не считаются normal missing. Scope/diff не вычисляется самодельным алгоритмом в DAG; readers не получают новых обязанностей.

## 4. Вопросы, которые ревизия не объявляет багами

### LR-Q1 — полный planning extent и scoped light preparation

`naturalRelief.light_relief` разворачивает light cells для всех coarse cells переданного TerrainPlan, до ограничения результата requested tiles в contributors. Evidence: [полный обход terrain.surface_z](../../backend/app/application/worldData/generators/terrain/relief/planning/naturalRelief.py:57).

Это может быть намеренным world-scoped planning/cache решением. Не доказано, что его нужно ограничить request scope: такой cut может изменить детерминизм и граничные эффекты. До приёмки нужно явно определить planning scope, reuse и допустимую стоимость; performance claim без измерения не делается.

### LR-Q2 — диагностики и успех публичного Pipeline

Relief provider может вернуть payload с diagnostics disposition ERROR. Exact admission policy будущего публичного Pipeline не принята. Evidence: [создание diagnostics](../../backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py:99), [report boundary](../../backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py:174).

Нужно определить, какие diagnostics запрещают успешный Output, а какие допускают согласованный degraded result. Ревизия не утверждает, что всякая diagnostics сейчас ошибочно допускается: полный exception policy `report_issues` здесь не аудирован.

### LR-Q3 — coarse/light/river relief coherence

ReliefPlan содержит natural light effects и coarse pre-river relief; RiverReliefPlan вычисляется позже по routes. Нельзя считать все поля одним и тем же состоянием поверхности только по общему слову relief.

До freeze нужны явные семантики результатов и точные refs, потребляемые hydrology/L0. Ошибка численной согласованности ревизией не доказана; для неё нужен отдельный сквозной геометрический разбор.

### LR-Q4 — baseline/GEO/native activation

Проверенная цепочка использует baseline providers. Соседние GEO/native классы требуют самостоятельного wiring/activation evidence. Будущий Pipeline не должен смешивать варианты контрактов по усмотрению caller.

## 5. Архитектурные выводы и предел разрешения

- Подтверждённого отдельного ReliefOrchestrator в просмотренной цепочке нет; межоперационное управление находится в более широких surface/pack orchestrators.
- По решению пользователя такие orchestrators декомпозируются на линейные доменные Pipeline, управление которыми находится в DAG. Простое переименование не закрывает LR-R1/R2.
- Внутренние providers, геометрические функции и contributors не становятся DAG-нодами автоматически.
- Уже зафиксированное имя — `ISurfacePlanningPipeline.prepare_surface_plan`. Отдельный публичный Relief Pipeline, его имя/DoD и изменение composition остаются OPEN.
- Полнота вызовов подтверждена для указанного baseline среза, но не для всего генератора. Принятие inventory не означает приёмку implementation/cutover.

## 6. Что потребуется проверить при реализации

- [ ] Утвердить exact prepared-result и publication contract, включая relief side records.
- [ ] Подтвердить scoped missing/reuse без повторной записи актуальных частей.
- [ ] Принять diagnostics/no-extent/cancel/failure outcomes публичного Pipeline.
- [ ] Зафиксировать baseline/GEO/native выбор по owning contract.
- [ ] После разрешённой реализации проверить фактическое исполнение cold-cache/cache-hit, partial scope и failure до/после staging/publication.

Эти проверки не выполнены данным документом. Код, contracts и runtime behavior ревизией не изменены.
