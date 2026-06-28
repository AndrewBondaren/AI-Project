---
name: tz-engine-flow
description: "Полный flow выполнения движка от сообщения пользователя до ответа — фазы, ответственность нод, repair, patch"
metadata: 
  node_type: memory
  type: project
  originSessionId: 633eddca-8d16-4119-94ab-ef548d071851
---

# ТЗ: Execution Engine Flow

## Принципиальное разделение фаз

**pre_llm** — проверка предусловий и gate-логика. Единственное место откуда можно сигнализировать `requires_replan`. Примеры: CheckSceneNode (есть ли сцена?), CheckPlayerNode и т.п.

**llm** — генерация контента. Включает контрактную валидацию и repair. Если нужна domain-валидация (IDs из LLM существуют в DB) — она объявляется на LLM-ноде и выполняется внутри `_validate_all` → при провале сразу в RepairOrchestrator, пока conversation `messages` живы.

**post_llm** — фиксация успешного результата. Пишет в DB, считает следующий стейт. **Никогда не верифицирует, никогда не возвращает requires_replan.** Запускается только если pre_llm и llm прошли успешно.

## Полный flow (сообщение → ответ)

### 1. ChatService.handle_message()
- `pending_repo.upsert(message)` — crash recovery
- `engine.run(INTENT_DETECTION, message, session)`

### 2. LLMExecutionEngine — внешний pass loop
```
ExecutionState(message, session, task_type=INTENT_DETECTION)

for pass_num in range(max_passes):
    state.pass_number = pass_num
    plan = graph_compiler.compile(state)
    state = dag_executor.execute(plan, state, context)
    _apply_task_transition(state)
    if not state.requires_replan: break

patch_applier.apply(state)           # атомарно, один раз после всех passes
state.final_result = state.node_results
```

### 3. GraphCompiler.compile(state)
- Фильтр нод: `rule_engine.evaluate(cn, state)` — в основном `supported_tasks` + rules
- Split: pre_llm / llm / post_llm по типу ноды и `phase`
- Kahn's algorithm → уровни параллельности внутри каждой фазы
- LLM-ноды группируются по `temperature` ASC (анализ → генерация)
- Возвращает `ExecutionPlan`

### 4. DAGExecutor.execute(plan, state)
Сбрасывает `requires_replan`, `replan_reason`, `next_task_type` в начале каждого pass.

**Phase 1 — pre_llm** (уровень за уровнем, параллельно внутри уровня):
- `NodeRunner.run()` → `PythonNodeExecutor` → `handler(state, context)`
- `_aggregate_replan()` после каждого уровня — first-wins по `next_task_type`
- Если `requires_replan=True` → **return early**, LLM не запускается

**Phase 2 — LLM-группы** (ASC по temperature):
- Skip группы если `all(nid in state.node_results)` — resume после отмены
- `LLMAggregateExecutor.execute(group, ...)`

**Phase 3 — post_llm** (уровень за уровнем, параллельно внутри уровня):
- Аналогично pre_llm, но **не агрегирует replan** — post_llm никогда не сигнализирует requires_replan

### 5. LLMAggregateExecutor.execute() — repair живёт здесь
```
payload = payload_builder.build(nodes, dsl_keys, state)
messages = [system: global_dsl, user: payload]
raw = client.chat(messages)
messages.append(assistant: raw)

_validate_all(nodes, response):
    llm_validator → контракт каждой ноды (схема + опциональная domain-валидация)

если всё ок:
    state.node_results[node_id] = output
    state.pending_patches.append(...)     # накапливаем, не применяем

если есть failed_nodes:
    state.node_errors[node_id] = [error_codes]
    repair_orchestrator.repair(failed_nodes, messages, client, state)
    мержим repaired → state.node_results + state.pending_patches
```

### 6. RepairOrchestrator.repair() — внутри той же conversation
```
while attempt < repair_iterations:
    DSLFailureProjector → error_codes из state.node_errors
    dsl_resolver.resolve_patches → DSL-патчи под конкретные коды ошибок
    RepairBuilder.build → repair payload с описанием что неправильно

    messages.append(user: repair_payload)
    raw = client.chat(messages)      # LLM видит свой ответ + конкретные ошибки
    messages.append(assistant: raw)

    _validate_failed → если ok → return {node_id: output}
    если нет → shrink current_failed, attempt++

если исчерпан лимит → raise RuntimeError
```

### 7. _apply_task_transition (после DAGExecutor)
- `INTENT_DETECTION`: читает `node_results["intent_detection"]["intents"]` → top intent → новый `task_type` + `requires_replan=True`
- `next_task_type` (из Python pre_llm ноды): `task_type = state.next_task_type` + `requires_replan=True`

### 8. PatchApplier.apply() — один раз после всех passes
- Валидирует все patches структурно
- Атомарно применяет: `state.node_results[node_id] = output`, `state.node_status = "success"`
- Удаляет `node_errors` для починенных нод
- `state.pending_patches.clear()`

### 9. ChatService завершает
- Если не ошибка: `message_repo.create_turn()`, `pending_repo.delete()`
- Возвращает `result` → HTTP/SSE handler → user

## Ключевые инварианты

- `requires_replan` может выставить **только pre_llm** нода через `NodeResult`
- `post_llm` нода **никогда** не сигнализирует replan — она обрабатывает только успешный результат
- RepairOrchestrator работает **внутри LLMAggregateExecutor** пока `messages` и `client` живы
- Domain-валидация LLM-вывода против DB — объявляется на **LLM-ноде**, выполняется в `_validate_all`, попадает в repair в той же conversation
- `state.pending_patches` накапливается по ходу выполнения, `PatchApplier` применяет **атомарно один раз** после всех passes
- `pass_number == 0` → resume-логика (пропускаем уже выполненные)
- `pass_number > 0` → replan-логика (gate-ноды с `skip_on_replan=False` перезапускаются)

## SceneContextBuilderNode — агрегатор сцены для LLM

**Фаза:** `pre_llm`  
**deps:** `["check_scene"]`  
**Назначение:** переводит сырое состояние симуляции (map_cells, cell_states, location_objects) в локализованный нарратив для LLM. Другие ноды читают результат из `state.shared_context["scene_description"]` — не обращаются к БД сами.

**Алгоритм (черновик, детали при реализации):**
```
1. Читает map_cells + активные cell_states текущей сцены
2. Читает location_objects (x, y, display_name) — якоря для привязки ячеек
3. Для каждой ячейки с активным состоянием:
   - nearest_anchor = ближайший location_object по (x, y)
   - key = "scene.state.{system_state}"
   - phrase = string_table[world.language][key].format(anchor=nearest_anchor)
4. Считает structural_integrity если локация — здание с is_structural ячейками
5. Собирает scene_context:
   {
     "location": display_name,
     "objects": [display_name, ...],         -- корневые location_objects
     "hazards": ["...", "..."],              -- локализованные фразы состояний
     "structural": "stable"|"warning"|"critical",
     "actors": [...]
   }
6. state.shared_context["scene_description"] = scene_context
```

**String tables:** `app/scene_descriptions/{lang}.json` — DSL-файлы с `{{placeholder}}`-подстановкой. Движковый нарратив (не LLM-промпты). Пример:
```json
{
  "scene.state.burning":   "{{object}} охвачен огнём",
  "scene.state.flooded":   "Пол возле {{anchor}} затоплен",
  "scene.state.door.open": "{{door}} открыта",
  "scene.structural.warn": "Здание кажется нестабильным",
  "scene.structural.crit": "Стены рушатся"
}
```

LLM получает уже локализованный контекст — не координаты, не system-ключи.  
Детали алгоритма и структура scene_context уточняются при реализации ноды.

Стык generators ↔ DAG — [`tz_world_generation_dag.md`](./tz_world_generation_dag.md) (**черновик**, не дублировать здесь).

---

## Открытые вопросы / будущие расширения
- Domain-валидатор на LLM-ноде: API не определён, нужен когда появится первая нода с ID-верификацией
- `post_llm` phase в DAGExecutor сейчас агрегирует replan так же как pre_llm — нужно убрать эту агрегацию чтобы инвариант был закреплён кодом
