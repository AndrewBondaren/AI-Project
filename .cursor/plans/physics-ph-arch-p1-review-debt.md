# PH-ARCH P1 — техдолг архитектурного ревью

Дата: 2026-11-02. Статус: **OPEN / на согласование**.

Источник: [PHYSICS-1, PH-ARCH P1](./physics-spatial-dynamics.md#ph-arch-p1--предложение-общей-вычислительной-архитектуры-2026-11-02), принятый статический PH-0 того же плана, [Physics TZ](../../docs/tz_physics.md). GEN-DAG draft не использован.

Документ фиксирует результат ревью, а не принимает решения A–E. PH-ARCH не CODE-READY; PH-ORCH и runtime activation не приняты. Код, concrete DAG-ноды и новые production contracts не создаются. Ниже разделены дефекты полноты общей архитектуры, пользовательские решения и последующие owning/process contracts. Подтверждённые дефекты относятся к проекту, не к существующему runtime Physics: его исполнитель не установлен принятым PH-0.

## 1. Подтверждённые дефекты общей архитектуры

### PH-ARCH-P1-01 — временные инварианты request/continuation

**OPEN; блокирует exact freeze.** Основание: план P1.3, строки 475–487; [typed request/result/state](./physics-spatial-dynamics.md#p13-typed-requestresultstateerrors--поля-кандидаты).

`observed_at`, `interval.start/end` и continuation `at` перечислены, но их отношение не определено явно. `end >= start` не исключает повторное продвижение либо пропуск времени. Обязательность continuation при resume заявлена, но способ отличить resume от initialisation не задан.

Нужно согласовать admission-инварианты времени и source bindings; определение initialisation/resume; исход при несовпадении; семантику нулевого интервала. Не выбирать молча равенство всех времён: допустимость иной связи должна быть явным контрактом. Source freshness устанавливает внешний reader, compute проверяет только предоставленные данные.

Evidence reuse: [WorldPublicationRef](../../backend/app/dataModel/worldSnapshot/identity/publication.py#L12) проверяет структурную согласованность, не freshness/ancestry; [publication store read](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py#L95) и [compare_append](../../backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py#L112) — внешний storage/CAS, не разрешённые зависимости compute.

Закрытие: точные правила времени, init/resume и отказов записаны в owning-плане без добавления IO в Physics.

### PH-ARCH-P1-02 — полнота успешного вычислительного интервала

**OPEN; блокирует exact freeze.** Основание: план P1.2, P1.3, строки 481–489; [стадии session](./physics-spatial-dynamics.md#p12-процессы-и-численные-стадии).

Полный interval заявлен, но схема `computed` не закрепляет проверяемое соответствие outputs всем запрошенным process/mode/coverage, запрет дубликатов и достижение конца интервала каждым участником. Поле `issues: tuple[PhysicsComputeIssue, ...]` также не ограничивает отказные issues внутри успешного результата.

Нужно определить общую проверку полноты и допустимые diagnostics успеха: пропуск process, незавершённая coverage или отказ связанного kernel не должны выглядеть как `computed`. Успешное отсутствие изменений должно отличаться от отсутствующего output. Пустой request уже разрешён планом; его no-event результат нужно сохранить отдельным явным случаем. Конкретные балансы/coverage остаются process-owned.

Граница результата: [IWorldSnapshotApply](../../backend/app/application/worldSnapshot/contracts/applyPort.py#L9) принимает PatchSet снаружи; [engine callback caller](../../backend/app/application/engine/runtime/dagEngine.py#L149) не доказывает полноту Physics outcome и не заменяет её проверку.

Закрытие: общий completeness-инвариант и совместимость outcome/issues закреплены; частичные coupled effects не выдаются за успех полного интервала.

### PH-ARCH-P1-03 — точный typed process binding

**OPEN; блокирует exact freeze.** Основание: план P1.1, строка 440, P1.2–P1.3; [file/class map](./physics-spatial-dynamics.md#p11-ownership-и-минимальная-fileclass-map).

Binding связывает ID, modes, contract и callable описательно, но точная типовая связь input → kernel → output → continuation и typed intermediates ещё не зафиксирована. Сочетание «поддерживаемые modes» и «одна binding на комбинацию process/mode» требует однозначной модели ключа/регистрации.

Нужно согласовать общий application binding contract, проверку совместимости и duplicate rejection, границу numerical coupling и принадлежность version metadata. Конкретные liquid POJO не требуется выдумывать для закрытия этого вопроса; незакрытый payload/Any не считается решением.

Существующего PhysicsProcessBinding нет: это новый проектный контракт. [Hydrology assembler caller](../../backend/app/application/worldData/generators/hydrology/waterBodyAssembler.py#L19) и вызываемый [resolve_water_levels](../../backend/app/application/worldData/generators/hydrology/water/waterBodyResolver.py#L42) — bootstrap chain, не образец runtime process binding.

Закрытие: общий typed binding однозначен, process specialization явно отделена, world scheduler внутри compute не появляется.

### PH-ARCH-P1-04 — неполная карта общих типов

**OPEN; блокирует exact freeze.** Основание: план P1.1/P1.3, строки 451–457 и 477–485.

Для используемых `PhysicsTimePoint`, `PhysicsBalance` и typed kernel-version bindings не назначены явно определения/ownership и точный общий состав. Подсчёт файлов подтверждает перечисленные пути, но пока не завершённость exact-contract map.

Нужно назначить владельцев этих типов, определить общий accounting envelope и границу с process quantities, затем пересчитать layout. Отдельный файл на каждый тип не предписывается.

Evidence reuse: [FineZ и координаты](../../backend/app/dataModel/spatial/grid/coordinateTypes.py#L10) не определяют физический time/length scale; [GridBBox](../../backend/app/dataModel/spatial/grid/gridBBox.py#L8) имеет только XY; [MaterialRegistryEntry](../../backend/app/dataModel/materials/materialRegistryEntry.py#L25) не является units/accounting contract.

Закрытие: каждый общий тип имеет owner и определение; counts пересчитаны с полным набором согласованных contracts.

## 2. Решения A–E для пользователя

Все **OPEN**. Источник: [P1.5](./physics-spatial-dynamics.md#p15-решения-для-согласования-и-остаточные-blockers), строка 503. Рекомендации ревью не являются приёмкой.

- **A — общая session и сокращённая file/class map.** Рекомендовано направление; точный freeze после PH-ARCH-P1-03/04. Не вводить симметричные solver-классы без необходимости.
- **B — полный interval либо unresolved.** Рекомендовано после PH-ARCH-P1-01/02. Partial time advancement потребует отдельного явного контракта.
- **C — explicit prepared payload без IO refs.** Рекомендовано; стабильность должна охватывать весь используемый граф входных данных, а не только frozen outer model.
- **D — U1 SI либо U2 model units.** Требуется явный выбор. U1 требует owning versioned conversions; переобозначать текущие registry values как SI нельзя. U1/U2 не смешиваются.
- **E — strict capability refusal.** Рекомендовано; requirements зависят от явно выбранной модели. Необязательное для модели поле не блокирует расчёт. Автоматическая смена модели по нехватке данных запрещена; упрощённые модели требуют отдельного согласования.

Evidence C/D/E: [MaterialRegistryEntry](../../backend/app/dataModel/materials/materialRegistryEntry.py#L25) frozen, но содержит списки и нормированные/неразмеренные properties; [WorldMaterialRegistry](../../backend/app/dataModel/materials/worldMaterialRegistry.py#L17) содержит mutable root list, [entry_for](../../backend/app/dataModel/materials/worldMaterialRegistry.py#L41) — in-memory lookup. [Climate consumer](../../backend/app/application/worldData/generators/climate/precipitation.py#L26) имеет собственные fallback semantics; они не дают разрешения переносить fallback в Physics.

## 3. Последующие process-specific и внешние owning contracts

Это явно отложенные контракты, а не дополнительные найденные дефекты общего замысла. Принятие A–E не закрывает их автоматически. Источник: [P1.4](./physics-spatial-dynamics.md#p14-units-capabilities-и-reuse), P1.5 и [Physics TZ §9](../../docs/tz_physics.md#9-открытые-контракты-и-критерии-приёмки).

- **Liquid process:** concrete input/output/continuation; equations, coupling, stability, boundary/source/sink accounting, tolerances, no-change semantics. [WaterBody](../../backend/app/dataModel/hydrology/waterBody.py#L12) и [PhysicalWaterUnion](../../backend/app/dataModel/hydrology/physicalWaterUnion.py#L10) дают source identity/levels, не готовый volume/velocity state. Numerical reuse bootstrap kernels требует отдельного review.
- **Units и prepared reads:** geometry/material/time scales, versioned conversions, public read bindings, coherent capture, Grade/read budgets и refusal. FAR/MEDIUM без Grade/SQL; NEAR — только будущий approved bounded read. Текущие типы не доказывают runtime coherence или отсутствие SQL.
- **Destination operations:** typed requests и validation Materials/Hydrology/Geometry/Gas/Objects, scope mutable instance properties, revisions, errors. Не заменять generic `{domain, payload}` и не вызывать owners из compute.
- **Continuation lifecycle / handoff:** process transfer laws AGG↔LOCAL, supported versions, post-commit bindings, atomic acceptance с canonical effects, storage/checkpoint/reload. Continuation не второй canonical water/material state.
- **PH-ORCH/PH-PUBLISH:** внешние scheduling/LOD/settings, overlap/cancellation/retry/CAS, domain preparation и atomic publication; serialization/migration. Новые concrete DAG-ноды этим документом не утверждаются.

## 4. Проверенная граница compute

На уровне предложения P1 нарушений не найдено: Physics получает prepared facts, проверяет metadata без IO, выполняет внутренние numerical substeps, возвращает typed proposals/continuation candidate. Read ports, source freshness reads, world scheduler, domain writes, PatchSet и Snapshot publication оставлены снаружи. Это статическая оценка проекта, не runtime guarantee.

Reuse retained: Materials schema/category/lookup, captured WorldPublicationRef, grid/topology semantics, Hydrology bootstrap. Не переносить bootstrap level/fill policy в runtime solver; не приписывать FineZ метры, density SI, temp_damage источник энергии или registry air обязательную ambient среду.

## 5. Порядок закрытия

1. Получить явные решения пользователя A–E, включая выбор D; зафиксировать disposition без молчаливого выбора.
2. Уточнить в owning-плане PH-ARCH-P1-01…04 и повторно проверить общие exact contracts/layout.
3. Предъявить обновлённый PH-ARCH на отдельную приёмку; процессные и внешние gates оставить OPEN до своих contracts.
4. Реализация требует отдельной команды пользователя. Этот документ её не разрешает.

Source links `#L` фиксируют проверенные места на дату ревью; после изменений строки нужно перепроверять. Сервер и тесты не запускались: задача документальная, runtime guarantees не заявляются.
