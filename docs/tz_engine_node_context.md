# ТЗ: Типизированные контексты нод (ExecutionState)

## 1. Проблема

`ExecutionState` содержит два свободных поля:

```python
self.node_results: dict[str, object]   # нет типов на результаты нод
self.shared_context: dict              # полностью свободная форма
```

Нода B читает данные ноды A через `shared_context["terrain_data"]` — контракт неявный, узнаётся только при падении в рантайме. Нет статической проверки, нет IDE-подсказок, нет валидации при запуске пайплайна.

**Когда стало актуально:** при реализации первых нод (сцена, terrain, генераторы). До этого ноды не были реализованы.

---

## 2. Решение — типизированные домен-контексты

Вместо `shared_context: dict` — явные типизированные поля на `ExecutionState` по доменам:

```python
self.terrain_context:  TerrainContext  | None = None
self.scene_context:    SceneContext    | None = None
self.combat_context:   CombatContext   | None = None
self.structure_context: StructureContext | None = None
```

Каждый домен — отдельный `dataclass`. Ноды домена пишут только в свой контекст, читают из чужого если объявили зависимость.

---

## 3. Правила для нод

- Нода **пишет только** в контекст своего домена
- Нода **читает** из чужого контекста только если это задекларировано как зависимость ноды
- `shared_context` остаётся как escape hatch для нестандартных случаев, **не используется** как основной канал

---

## 4. Пример — terrain домен

```python
@dataclass
class TerrainContext:
    cell: MapCell
    adjacent_cells: list[MapCell]
    temperature: float
    is_loaded: bool = False
```

Ноды домена: `CheckTerrainNode`, `EagerTerrainNode`, `LazyTerrainNode` — все пишут в `state.terrain_context`.

Нода другого домена (например, `ClassifyMovementNode`) читает `state.terrain_context` — зависимость явная через `REQUIRES = ["terrain_context"]`.

---

## 5. Домены (предварительный список)

| Домен | Контекст | Ноды |
|---|---|---|
| terrain | `TerrainContext` | CheckTerrain, EagerTerrain, LazyTerrain |
| scene | `SceneContext` | CheckScene, SceneInit, SceneLocationChildren |
| structure | `StructureContext` | ноды генератора зданий |
| combat | `CombatContext` | боевые ноды |

Список расширяется по мере добавления нод.

---

## 6. Миграция

`shared_context` не удаляется — остаётся для обратной совместимости. При реализации новой ноды: использовать типизированный контекст, не `shared_context`.

---

## 7. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Механизм декларации зависимостей нод (`REQUIRES`) — ClassVar список или декоратор? | открыт |
| Валидация зависимостей до запуска пайплайна — в `GraphCompiler` или `DAGExecutor`? | открыт |
