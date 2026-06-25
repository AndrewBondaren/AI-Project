# ТЗ: Lazy Simulation (LOD-симуляция мира)

> **Статус:** концепция зафиксирована, детали реализации открыты.

## Принцип

Симуляция мира работает по принципу LOD (Level of Detail) — как рендеринг в 3D играх. Максимальная детализация вблизи игрока, агрегированное поведение на средней дистанции, системный уровень на дальней.

**Аналогия рендера:** движок не рендерит дальние объекты попиксельно — он рендерит их упрощённой версией или вообще не рендерит. Симуляция работает так же.

---

## Приоритет NPC — поверх зон

Зона симуляции определяется дистанцией, но **не для всех NPC**:

| Приоритет | Кто | Режим симуляции |
|---|---|---|
| `essential` | Сюжетно-важные NPC (квест-гиверы, фракционные лидеры, ключевые антагонисты) | Полный тик **всегда**, независимо от дистанции |
| `linked` | NPC с которыми `essential` взаимодействуют прямо сейчас (`system_current_target` указывает на них) | Полный тик пока взаимодействие активно |
| `ambient` | Все остальные | По зоне (near → medium → far) |

`is_essential` — поле на `npcs`; задаётся вручную или LLM-нодой при старте квеста.  
`linked` — динамический статус; вычисляется движком по `system_current_target.target_uid` essential-NPC.

**Следствие:** essential-NPC в far-зоне всё равно получают полный тик. Их `system_location`, потребности, цели обновляются каждый тик.

### Фоновый LLM для essential NPC — per-event

`essential` NPC получают LLM-вызов **по событию**, не по расписанию. Каждый NPC настраивается индивидуально: какие события его триггерят.

#### Конфигурация NPC (`npc_llm_triggers`)

```sql
npc_llm_triggers (
    npc_uid,           -- FK → npcs
    event_type,        -- ref → npc_llm_event_type_registry
    filter,            -- nullable JSON; доп. условие: радиус, локация, фракция, тег
    PRIMARY KEY (npc_uid, event_type)
)
```

#### Реестр типов событий (`worlds.npc_llm_event_type_registry`, N+1)

```json
[
  { "system_event_type": "location_state_change",  "display_name": "Изменение состояния локации" },
  { "system_event_type": "linked_npc_death",        "display_name": "Смерть связанного NPC"       },
  { "system_event_type": "linked_npc_goal_change",  "display_name": "Смена цели связанного NPC"   },
  { "system_event_type": "player_action_nearby",    "display_name": "Действие игрока рядом"        },
  { "system_event_type": "faction_influence_shift", "display_name": "Сдвиг влияния фракции"       },
  { "system_event_type": "resource_depleted",       "display_name": "Ресурс исчерпан"             },
  { "system_event_type": "world_history_event",     "display_name": "Событие мировой истории"     }
]
```

`filter` на `npc_llm_triggers` — доп. условие под конкретный тип:
- `location_state_change`: `{ "states": ["besieged", "fire"] }` — только эти состояния
- `player_action_nearby`: `{ "radius": 5 }` — радиус в map_cells
- `faction_influence_shift`: `{ "delta": 20 }` — минимальный порог изменения
- `world_history_event`: `{ "event_type": "war" }` — только события этого типа

Пользователь добавляет кастомные типы через N+1.

#### Поток выполнения

```
Событие происходит в мире
    ↓
EventBus публикует event_type + affected_uid
    ↓
движок: SELECT npc_uid FROM npc_llm_triggers
        WHERE event_type = :event_type
          AND filter matches affected_uid
    ↓
для каждого найденного essential NPC вне сцены:
    контекст = {
        npc_state:    system_current_needs, system_npc_goal, system_traits
        trigger:      что случилось, кто затронут
        linked_npcs:  состояния linked-персонажей
        world_state:  активные location_states, world_history (последние N)
    }
    LLM → решение → пишется в БД (не блокирует основной pipeline)
```

**Примеры решений:**
- Антагонист получает триггер `location_state_change: besieged` на союзный город → LLM решает выдвинуть армию
- Квест-гивер получает `player_action_nearby` → LLM решает покинуть город или остаться ждать
- Лидер фракции получает `faction_influence_shift` → LLM заключает новый союз

**Ограничения:**
- Фоновый LLM не создаёт сцены и не блокирует основной pipeline
- Один NPC не может получить два LLM-вызова одновременно — очередь per NPC
- Результат пишется в БД как обычный `post_llm`-патч

**Открытый вопрос:** EventBus для фоновых триггеров — тот же персистентный EventBus что в мультиплеере, или отдельный.

---

## Три зоны симуляции

### Зона 1 — Сцена (near)

**Граница:** текущая `named_location` игрока + непосредственно смежные локации (parent + siblings на том же уровне иерархии).

**Что симулируется:**
- Полный тик каждому NPC в сцене (`system_current_needs`, `increment_per_tick`)
- `map_cells` загружены полностью (eager + буфер ±10z)
- `cell_states` активны и обновляются (пожар распространяется, затопление растёт)
- `location_weather.remaining_ticks` декрементируется, погода пересчитывается
- `location_resources.regen_per_tick` применяется каждый тик
- `system_current_target` вычисляется для каждого NPC индивидуально
- `scene_participants` имеют полный AI-контекст
- Структурная целостность зданий пересчитывается при изменениях

**Частота:** каждый тик мирового времени (1 тик = 1 час).

---

### Зона 2 — Средняя дистанция (medium)

**Граница:** settlement/district в котором находится игрок, плюс соседние settlements в радиусе N map_cells (N — открытый вопрос).

**Принцип:** NPC не симулируются по отдельности каждый тик. Их действия **агрегируются** — последовательность тиков сворачивается в один батч-результат.

**Что симулируется:**
- NPC перемещаются между `home_location_uid` → `work_location_uid` → `home_location_uid` по расписанию без пошагового движения
- Потребности (`system_current_needs`) пересчитываются батчем: `value += increment_per_tick × N_ticks_elapsed`
- Торговые NPC агрегируют "пошёл на рынок, купил, вернулся" за один проход
- `location_states` обновляются (осада продолжается, эпидемия распространяется) — через системные события, не покрытийно
- `location_weather` тикует нормально (глобальный процесс, не per-NPC)
- `location_resources` регенерируются батчем

**Что НЕ симулируется:**
- Точные x, y, z NPC — только `system_location` (named_location UID)
- Индивидуальные конфликты между NPC (только системные: восстание, бой фракций)
- `cell_states` — не обновляются (пожар "заморожен" пока не стал событием системного уровня)

**Частота:** раз в N тиков (батч). N — открытый вопрос.

---

### Зона 3 — Дальняя дистанция (far)

**Граница:** всё за пределами medium-зоны.

**Принцип:** индивидуальные NPC **не симулируются**. Их поведение агрегируется в **системные показатели** на уровне settlements, factions, regions.

**Что симулируется:**
- Фракционное влияние (`location_faction_influence`) изменяется по системным событиям (война, торговый договор)
- `location_states` на settlement-уровне (осада города, экономический кризис)
- Торговые потоки между settlements — агрегированный показатель, не отдельные купцы
- Прирост/убыль населения settlements — системная формула
- Условия дорог (`connection_edge.condition`) деградируют по `condition_degradation` без per-NPC действий

**Что НЕ симулируется:**
- `ambient` NPC — их состояние "замораживается" на момент перехода в far-зону
- `essential` и `linked` NPC — исключение, симулируются полным тиком всегда
- Внутренние конфликты локаций без системного значения
- `map_cells` — не генерируются и не обновляются

**Частота:** по событиям или очень редко (раз в M тиков). M >> N.

---

## Переходы между зонами

При перемещении игрока:
```
Локация переходит near → medium:
  - NPC в ней "замораживаются" (last_tick записывается)
  - При следующем обращении: батч-пересчёт за elapsed_ticks

Локация переходит medium → far:
  - NPC агрегируются в системные показатели
  - Индивидуальное состояние сохраняется в БД, не симулируется

Локация переходит far → near (игрок возвращается):
  - Батч-пересчёт за всё elapsed_time
  - NPC "разворачиваются" из агрегата в индивидуальные состояния
  - map_cells lazy-генерируются если нужны
```

**Инвариант:** при возвращении игрока в локацию мир должен выглядеть **консистентно** с прошедшим временем — NPC состарились, ресурсы восстановились, событие "осада" изменило состояние города.

---

## Открытые вопросы

| Вопрос | Статус |
|---|---|
| Точные границы near/medium/far в единицах map_cells или named_location depth | открыт |
| Батч-алгоритм агрегации NPC на medium — детерминированный или с rnd-компонентом | открыт |
| "Разворачивание" NPC из far-агрегата — как восстановить индивидуальный стейт | открыт |
| Системные события far-зоны — как инициируются (threshold на показателях?) | открыт |
| cell_states на medium — полное замораживание или упрощённая симуляция | открыт |
| Обработка конфликта: NPC из near взаимодействует с NPC из medium | открыт |

## Связи

- [project_data_storage_tz.md](project_data_storage_tz.md) — `npc_needs_registry.increment_per_tick`, `system_current_needs`, `system_current_target`
- [tz_locations.md](tz_locations.md) — `map_cells` lazy-инициализация, `location_states`, `location_weather`
- [tz_multiplayer.md](tz_multiplayer.md) — тиковая система, `action_available_at_tick`
- [tz_structure_connections.md](tz_structure_connections.md) — `condition_degradation` дорог в far-зоне
