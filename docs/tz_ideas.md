# ТЗ: Ideas Registry (импорт паттернов и продуктовые идеи)

**Тип:** living registry / backlog идей (не player-facing).  
**Статус:** концепция ✅ · **impl — по фазам**, не блокирует текущий цикл (generators, JSON validation, DAG topology).  
**Обновлено:** 2026-07 (синтез research + product vision).

**Связанные документы:**

| Документ | Роль |
|---|---|
| [tz_lazy_simulation.md](./tz_lazy_simulation.md) | LOD sim, essential NPC LLM triggers |
| [tz_perception.md](./tz_perception.md) | Геометрический срез для LLM |
| [tz_engine_flow.md](./tz_engine_flow.md) | Pass loop, repair, patch_applier |
| [tz_json_validation.md](./tz_json_validation.md) | Валидация bundle пресетов |
| [tz_world_snapshot.md](./tz_world_snapshot.md) | Snapshot / replay инфраструктура |
| [project_data_storage_tz.md](./project_data_storage_tz.md) | `system_*` / `display_*`, N+1 |
| [tz_frontend.md](./tz_frontend.md) | Player flow vs master tools |

**Внешние референсы (research, не зависимости):**

| Проект | Что взять |
|---|---|
| [AI RPG Engine](https://github.com/mcp-tool-shop-org/ai-rpg-engine) | Simulation-first, presentation channels, rumor propagation |
| [Orchestrated Reality](https://arxiv.org/html/2606.16014v1) | Plan–Diff–Validate–Apply, canonical JSON state |
| [LlamaBrain](https://github.com/michael-tiller/LlamaBrain) | Validation gate, authority hierarchy, graceful fallback |
| [MnesOS](https://github.com/neolaw84/MnesOS) | Director/Narrator split, cartridge distribution, BYOK |
| [Project Lunar](https://github.com/horizonfps/project-lunar) | Witness filter, plot-lock, scene notebook |
| [Omnia](https://github.com/sortedcord/omnia) | Patch merging, world tick, tiered NPC LOD |

---

## Продуктовая рамка

**Две аудитории:**

| Роль | UX | Движок |
|---|---|---|
| **Игрок** | Загрузить пресет мира → интерактивно создать/выбрать персонажа → играть (чат) | Невидим: sim, validation, DAG, N+1 |
| **Мастер** | JSON import, редактор (будущий), debug, баланс, выпуск пресетов | Полный доступ к реестрам и orchestration |

**Принцип мира:** не сухая таблица и не LLM-хаос, а **творческий живой мир** на базе **simulation + validation first**. LLM — propose (события, сюжет, prose); движок — commit.

**Уникальность платформы (ниша):** geometric procedural substrate (terrain / settlement / structure) + validation-first LLM GM + пресеты миров. Аналогов с полной комбинацией в open source нет; отдельные слои — см. референсы выше.

---

## Как читать registry

| Поле | Значение |
|---|---|
| **ID** | Стабильный идентификатор идеи |
| **Priority** | P0 (скоро) … P3 (когда будет время) |
| **Status** | `open` / `partial` / `accepted` / `rejected` / `deferred` |
| **Layer** | `narrative` / `product` / `engine` / `master` |

**Правило:** новая идея → новый ID; `rejected` не удалять (история решений).

---

## ID-1 — Три слоя правды (Facts → Beliefs → Presentation)

**Status:** `open` | **Priority:** P1 | **Layer:** narrative

### Проблема

Есть canonical state (БД, геометрия) и LLM narration. Нет явного слоя **социальной неопределённости**: NPC могут ошибаться, сплетничать, лгать — без мутации фактов.

### Модель

| Слой | Владелец | Пример |
|---|---|---|
| **Facts** | Движок (БД) | Город осаждён; игрок в таверне |
| **Beliefs** | NPC / location aggregate | Трактирщик *думает*, что войск вдвое больше |
| **Presentation** | LLM (narrator) | Prose для игрока из perception + beliefs источника |

```
Facts (engine) → Beliefs (deterministic patches) → Perception filter → Presentation (LLM)
```

### Связь с существующим

- [tz_perception.md](./tz_perception.md) — фильтр **геометрии**; beliefs — фильтр **социальной информации**.
- AI RPG Engine: *presentation channels that can lie*.

### Открыто

- Схема хранения beliefs на NPC (`npc_beliefs` JSON? отдельная таблица?)
- Decay / confidence на belief
- Кто может писать beliefs: только rumor engine + direct observation, не свободный LLM

---

## ID-2 — Rumor engine (детерминированное распространение слухов)

**Status:** `open` | **Priority:** P1 | **Layer:** narrative

### Принцип

Слух — **структурированное событие**, искажаемое правилами при распространении. LLM только **формулирует** речь NPC, не создаёт факт войны.

```
world_history (fact)
    → rumor_engine (distance, zone noise, faction bias, distortion)
    → belief patches на NPC / location
    → LLM: "ты слышишь, что..."
```

### Параметры искажения (черновик)

| Фактор | Эффект |
|---|---|
| Hops (число передач) | Размытие чисел, имён |
| Zone `noise` / `stability` | Скорость и искажение (см. environment в AI RPG Engine) |
| Faction alignment | Bias toward/against источник |

### Не делать

- LLM-generated rumors без anchor в `world_history` или system event

---

## ID-3 — Witness graph (кто что видел / слышал)

**Status:** `open` | **Priority:** P0 | **Layer:** narrative

### Принцип

NPC не «знают» off-screen события без цепочки наблюдения. Закрывает классический провал AI-RPG.

### Модель (черновик)

```sql
event_witnesses (
    event_id,           -- FK → world_history или event log
    entity_uid,         -- NPC или player
    observation_quality -- direct | hearsay | rumor
)
```

### Потребители

- Essential NPC background LLM ([tz_lazy_simulation.md](./tz_lazy_simulation.md) § per-event): контекст только по witness-path
- Belief updates (ID-1, ID-2)
- Perception-adjacent: кто был в сцене при событии

### Референс

Project Lunar: witnessed-by filter.

---

## ID-4 — Scene notebook (volatile state сцены)

**Status:** `open` | **Priority:** P0 | **Layer:** engine

### Проблема

Бой, таймеры, активные эффекты, позиции «прямо сейчас» не должны засорять canonical БД каждым ходом.

### Модель

| Хранилище | Содержимое | TTL |
|---|---|---|
| **Canonical** | `world_history`, `location_states`, `map_cells` | Постоянно |
| **Scene notebook** | Активные эффекты, combat round, временные флаги | Сессия / сцена; сжатие в канон по событию |

### Жизненный цикл

```
Старт сцены / боя → notebook init
Каждый turn → LLM tool / node обновляет notebook (validated)
Конец боя / смена локации → merge релевантного в canonical или discard
```

### Референс

NarrativeEngine-P: Update Scene Notebook; Project Lunar: volatile working memory.

### Связь

- Отдельно от `shared_context` в engine — целевое: typed `SceneContext` ([tz_engine_node_context.md](./tz_engine_node_context.md))

---

## ID-5 — Plot economy (plot-lock, один активный крючок)

**Status:** `open` | **Priority:** P1 | **Layer:** narrative

### Принцип

Творческий сюжет без хаоса «каждый ход новый квест». Движок **авторизует** активные hooks; LLM предлагает в рамках слота.

| Слот | Лимит |
|---|---|
| **Macro arc** | 1 на кампанию / мир |
| **Micro hook** | 1 активный на игрока |
| Остальное | Очередь или seed pool с cooldown |

### Референс

Project Lunar: PlotGenerator + plot-lock + cooldown.

### TaskType (уже в enum)

`GENERATE_QUEST_RELATED_EVENT`, `GENERATE_LOCAL_EVENT`, `GENERATE_WORLD_EVENT` — wiring в DAG отложен; plot economy — gate **до** LLM event nodes.

---

## ID-6 — Preset manifest + smoke gate

**Status:** `open` | **Priority:** P0 | **Layer:** product / master

### Принцип

Игрок загружает **пресет** (validated bundle), не собирает мир. Мастер публикует cartridge с контрактом совместимости.

### Manifest (wire shape, черновик)

```json
{
  "preset_id": "dark_medieval_v1",
  "display_name": "Тёмное Средневековье",
  "engine_min": "0.2.0",
  "validation_schema": "0.1",
  "smoke": {
    "start_location_uid": "...",
    "test_character_template": "..."
  },
  "fallback_narration": {
    "scene_blocked": "...",
    "validation_failed": "..."
  }
}
```

### Smoke gate (перед публикацией пресета)

1. `JsonValidationFacade` — bundle OK  
2. Import transaction  
3. Create session + test character  
4. N turns (intent → scene path) — no fatal in engine log  

### Связь

- [tz_json_validation.md](./tz_json_validation.md), `fixtures/world_template.json`
- MnesOS cartridge model (без копирования формата)

---

## ID-7 — Session action log + master replay

**Status:** `partial` | **Priority:** P1 | **Layer:** master

### Уже есть

- [tz_world_snapshot.md](./tz_world_snapshot.md) — world snapshot, debug replay path
- Engine: `ExecutionTrace`, pass loop

### Добавить

Per-turn log для мастера:

```
turn_id, task_type, node_results_hash, patches_applied, validation_errors
```

**Цель:** воспроизвести сессию игрока на пресете; найти разрыв контекста без «попробуй ещё раз».

### Референс

AI RPG Engine: byte-identical replay; Orchestrated Reality: content-hashed deltas.

---

## ID-8 — Authority hierarchy для конфликтующих патчей

**Status:** `open` | **Priority:** P1 | **Layer:** engine

### Принцип

Validation — не только JSON schema, но и **кто имеет право** менять что.

```
canonical (designer / master preset) > world_state > episodic > beliefs
```

### Примеры

| Proposal | Verdict |
|---|---|
| LLM: «город уничтожен» без `world_history` cataclysm | reject |
| Player action + valid combat patch | world_state |
| NPC rumor | beliefs only |

### Референс

LlamaBrain: authority hierarchy, canonical facts immutable.

### Связь

- `patch_applier` post-pass — единая точка enforcement

---

## ID-9 — Configurable LLM roles (Intent / NPC / Background Planner / Narrator)

**Status:** `open` | **Priority:** P0 | **Layer:** engine

### Принцип

LLM в движке — не одна универсальная роль. Выделяются как минимум четыре функционально разные роли с отдельными контрактами, политиками контекста и настраиваемым model/provider.

| Роль | Назначение | Экземпляры |
|---|---|---|
| **Intent** | Первый разбор player input: намерения, действия, прямая речь и другие элементы → structured intent для DAG | 1 на player input |
| **NPC** | Поведение конкретного NPC в активной сцене: диалог, намерения, действия, интерпретация происходящего | 0..N на scene beat |
| **Background Planner / GM** | Планирование событий и развития мира вне scope непосредственной сцены | по trigger/schedule |
| **Narrator** | Финальная агрегация уже разрешённой сцены в player-facing narration | 1 на завершённый scene beat |

### Общий flow

```
PLAYER INPUT
    ↓
INTENT LLM
    ↓ validated structured intent
ENGINE / DAG
    ↓
perception + knowledge + action context
    ↓
NPC LLM A ─┐
NPC LLM B ─┼→ proposals → ENGINE RESOLUTION / COMMIT
NPC LLM C ─┘                         ↓
                                  NARRATOR LLM
                                      ↓
                                    PLAYER

BACKGROUND PLANNER / GM
    ↓ world-level proposals
ENGINE validate / commit
```

### Intent role

Intent — boundary между свободным языком игрока и формальным DAG.

Обязанности:
- классифицировать player input;
- сохранить порядок действий;
- сохранить прямую речь verbatim;
- отделить intent от результата;
- вернуть строго структурированный contract;
- не считать заявленный игроком outcome свершившимся фактом.

Результат Intent LLM — **candidate IR**, который проходит deterministic validation до исполнения.

### NPC role

NPC — параметризуемая роль, а не отдельный тип модели на каждого персонажа.

```
role = NPC, actor = npc_A
role = NPC, actor = npc_B
role = NPC, actor = npc_C
```

Один и тот же model/provider может обслуживать несколько NPC, но каждый вызов получает отдельную actor-specific projection.

NPC context должен включать только разрешённые конкретному actor данные: perception, beliefs, memories, personality, relationships, needs и релевантные результаты сцены.

**Запрещено:** передавать NPC canonical secrets, мысли игрока, private state других NPC или знания Background Planner / GM, если NPC не получил их через simulation/perception/information layer.

Число NPC-вызовов регулируется отдельно ID-14 (bounded NPC reaction turn): присутствие NPC в сцене не означает обязательный LLM-call.

### Background Planner / GM role

Работает **вне scope непосредственной сцены** и смотрит на более широкий world state.

Задачи могут включать:
- предложение фоновых/world events;
- развитие существующих конфликтов;
- создание narrative pressure/opportunities;
- долгосрочное планирование для мира/фракций/значимых акторов.

Planner не коммитит реальность напрямую:

```
LLM proposal → engine validation → commit/reject
```

Знания Planner не должны автоматически попадать в NPC или Narrator context.

### Narrator role

Narrator получает результат уже обработанной сцены и формирует цельное player-facing представление.

Основной вход:
- committed results;
- player-visible observations;
- разрешённые действия/реплики в правильном порядке;
- verbatim direct speech, где требуется;
- presentation/style context.

Narrator **не является authority для world state** и не должен создавать новые факты, действия NPC или последствия, которых нет в разрешённом результате сцены.

### Конфигурация ролей

Каждая роль должна иметь независимую конфигурацию. Конкретная wire/schema форма определяется при impl, но концептуально:

```
INTENT
  model/provider: configurable
  contract: IntentResult
  context_policy: player_input

NPC
  model/provider: configurable
  contract: NpcProposal
  context_policy: actor_private

BACKGROUND_PLANNER
  model/provider: configurable
  contract: WorldEventProposal
  context_policy: world_planning

NARRATOR
  model/provider: configurable
  contract: SceneNarration
  context_policy: player_visible_scene
```

Пользователь может:
- назначить одну локальную модель на все роли;
- назначить разные локальные модели;
- смешивать local + cloud;
- использовать более дешёвую/быструю модель для Intent и более сильную для отдельных ролей.

### Model-specific DSL + default fallback

Для одной и той же LLM-роли допускаются разные DSL/instruction profiles под разные модели или семейства моделей. Это позволяет адаптировать формулировку инструкции под особенности конкретной модели, **не меняя семантику роли и её output contract**.

Концептуальная структура:

```
INTENT
  ├── exact/<model>.dsl
  ├── family/<family>.dsl
  └── default.dsl

NPC
  ├── exact/<model>.dsl
  ├── family/<family>.dsl
  └── default.dsl

BACKGROUND_PLANNER
  └── default.dsl

NARRATOR
  ├── family/<family>.dsl
  └── default.dsl
```

Resolver выбирает наиболее специфичный доступный DSL:

```
role + exact model
    ↓ not found
role + model family/type
    ↓ not found
role + default DSL
```

**Инвариант:** отсутствие model-specific DSL не должно блокировать роль, если для неё существует `default.dsl`.

Model-specific DSL может оптимизировать:
- формат и жёсткость инструкции;
- особенности tool/structured-output поведения модели;
- repair hints;
- примеры и служебные формулировки;
- известные особенности instruction following конкретного семейства.

Model-specific DSL **не должен** менять:
- authority роли;
- разрешённые категории знаний/context permissions;
- смысл output contract;
- engine validation rules;
- canonical semantics полей.

Таким образом:

```
Role contract / permissions = stable engine API
DSL profile               = model adapter
```

Это позволяет заменить модель без изменения DAG и доменной логики, а новую/неизвестную модель подключить через role default DSL.

### DSL resolver / versioning

При impl нужен отдельный deterministic resolver, чтобы выбор DSL был воспроизводимым и попадал в execution trace:

```
resolve_dsl(role, provider, model, family)
    → selected_profile
    → profile_version/hash
```

Для debug/replay желательно логировать как минимум `role`, фактический `provider/model`, выбранный DSL profile и его version/hash.

### Role = security / knowledge boundary

Роль определяет **не только prompt, model и temperature**, но и то, какие категории данных вообще разрешено помещать в запрос.

```
Role
  → task contract
  → model/provider
  → context policy
  → knowledge permissions
  → output schema
  → validation policy
```

Поэтому агрегация контекста должна быть role-aware: знания, действия и результаты могут агрегироваться отдельно, а затем projection собирает только допустимый для конкретной роли набор.

### Связь с существующим

- [tz_engine_flow.md](./tz_engine_flow.md) — pre_llm / llm / post_llm; роли специализируют llm-фазу.
- [tz_perception.md](./tz_perception.md) + ID-1/ID-3 — ограничивают knowledge projection NPC.
- ID-4 Scene notebook — volatile scene state для NPC/Narrator.
- ID-13 Event Graph Hash — role-specific transport исторических событий.
- **ID-14 Bounded NPC reaction turn** — ограничивает число/цепочки вызовов NPC role.

### Открыто

- Registry/config schema для role → provider/model/settings.
- Формат хранения model-specific DSL profiles и role default DSL.
- Как определяется model family/type для fallback resolver.
- Общий ли repair loop для всех ролей или отдельная policy на contract.
- Fallback модели/provider на роль.
- Допускаются ли custom roles от world preset/master и какие permissions им можно выдавать.


---

## ID-10 — Graceful narration fallback (из пресета)

**Status:** `open` | **Priority:** P1 | **Layer:** product

### Принцип

Игрок пресета не видит технических ошибок. При исчерпании repair — prose из `preset.manifest.fallback_narration`, **без mutation**.

### Референс

LlamaBrain Component 9: author-controlled fallback.

### Связь

- `ResponseResolver` — маппинг `user_error` → fallback key из world preset

---

## ID-11 — BYOK LLM (ключ игрока)

**Status:** `deferred` | **Priority:** P2 | **Layer:** product

### Принцип

Мастер задаёт дефолт (локальный Qwen). Игрок может подставить OpenAI / Anthropic — без хостинга LLM автором пресета.

### Открыто

- Хранение ключа: session-only vs settings (Electron secure storage)
- MnesOS PKCE in-flight — reference, не обязательный impl

### Статус deferred

Пока solo/dev: `settings/backend` достаточно. Вернуться при distribution пресетов.

---

## ID-12 — Plan–Diff–Validate–Apply (именование pipeline)

**Status:** `accepted` | **Priority:** — | **Layer:** engine

### Решение

Текущий engine flow **уже соответствует** PDVA из Orchestrated Reality:

| PDVA | У нас |
|---|---|
| Plan | LLM + intent / event nodes |
| Diff | Structured contract output |
| Validate | `llm_validator`, domain validators, repair |
| Apply | `pending_patches` → `patch_applier` |

**Действие:** использовать терминологию в docs при описании event/plot nodes; код не переименовывать ради термина.

---

## ID-13 — Event Graph Hash (lazy disclosure сюжетного контекста)

**Status:** `open` | **Priority:** P1 | **Layer:** narrative / engine  
**Происхождение:** инженерное решение автора проекта (с самого начала); prior art в LLM-RPG **не исследовалось** — см. § «Происхождение идеи» ниже.

### Происхождение идеи

Идея возникла **до** survey чужих LLM-проектов: закрыть вопрос «как дать модели длинный сюжет без dump всей `world_history` и без дрейфа». Паттерн (ссылка + краткое описание → дозагрузка) в инженерии старый (event log, content-addressing); **протокол expand в той же engine session** для сюжетного графа — самостоятельная формулировка под этот движок.

**Не цель:** claims на оригинальность в ML; цель — зафиксировать контракт до impl.

### Предусловия (инварианты)

1. **Событие уже в движке.** Узел графа ссылается только на запись, которая **существует** в canonical store (`world_history` и связанный state). Нет записи → нет узла, нет expand. LLM не создаёт «события из головы» для transport-слоя — это вымысел → **невалидно** (propose → validate → persist — отдельный pipeline, не expand).
2. **Событие ≠ лор.** ID-13 — transport **сюжетных событий** (что случилось, с кем, от чего следует). **Лор** (энциклопедия мира, flavor text, glossary) — **другая сущность**, другой канал контекста. Сравнение ID-13 с lore-RAG / `multi_lore_lookup` **не применимо**: разные домены, не конкурирующие алгоритмы.

### Проблема

Передавать LLM полную историю событий (`world_history`, квесты, последствия) — дорого по токенам и шумно. Обрезать «последние N» — теряется причинно-следственная цепочка сюжета.

### Идея (компромисс)

**Сюжетный граф событий** в контексте LLM — в **компактном** виде: узлы = content-hash, рёбра = parent links + participants. Детальное описание события **не** в initial payload; движок отдаёт по **запросу уточнения** в той же conversation/session.

```
Initial context:     compact graph (hashes + titles + parent refs + participants)
LLM needs detail:    expand_request(event_hash) → engine injects full event record
Same session:        messages живы — как repair loop в LLMExecutionEngine
```

### Compact node (wire shape, черновик)

Каждый узел в JSON-графе сюжета:

| Поле | Тип | Назначение |
|---|---|---|
| `hash` | string | Идентификатор события (content-addressed или stable surrogate) |
| `title` | string | Подробный **заголовок** события (display-oriented, для ориентации LLM) |
| `parents` | string[] | 1–3 хэша родительских событий (причинная цепочка / ветвление сюжета) |
| `participants` | object[] | Ссылки на участников: `{ "kind": "npc"\|"player"\|"location"\|"faction", "uid": "..." }` |

```json
{
  "story_event_graph": {
    "anchor": "a3f2…",
    "nodes": [
      {
        "hash": "a3f2…",
        "title": "Осада Stone Ford: первая неделя, провиант на исходе",
        "parents": ["91bc…", "c004…"],
        "participants": [
          { "kind": "location", "uid": "loc_stone_ford" },
          { "kind": "faction", "uid": "fac_northvale" }
        ]
      }
    ]
  }
}
```

**Лимиты (v1):** `parents.length ≤ 3`; participants — по контракту ноды (cap TBD).

### Expanded node (on demand)

По `expand_request` движок возвращает полную запись, связанную с canonical storage:

| Поле | Источник |
|---|---|
| `hash` | тот же ключ |
| `system_event_type` / `display_event_type` | `world_history` / N+1 registry |
| `system_description` / `display_description` | полное описание |
| `system_world_date` / `display_world_date` | время в мире |
| `location_uid` | привязка |
| `effects_summary` | опционально: агрегат последствий (location_states, terrain patch uid) |

LLM **не** придумывает детали — только читает expand из движка.

### Протокол в engine session

1. **Gatherer-нода** (pre_llm): строит `story_event_graph` — подграф вокруг anchor (текущая сцена, active quest, последние k hops по parents).
2. **LLM-нода** (event/plot/narration): получает compact graph в `context_data`.
3. **Expand tool / contract field:** LLM запрашивает `event_hash` из **whitelist** (только хэши из выданного графа).
4. **Engine** (в той же `messages` conversation): append expand payload → LLM продолжает turn.
5. **Validator:** reject expand на неизвестный hash; reject если LLM цитирует детали без prior expand (опционально, v2).

Аналогия: repair loop — тот же session, дозагрузка контекста по запросу.

### Связь с существующим

| Сущность | Роль |
|---|---|
| `world_history` ([tz_locations.md](./tz_locations.md)) | Canonical store; hash = fingerprint canonical JSON row (или `id` + content hash) |
| `npc_llm_triggers` ([tz_lazy_simulation.md](./tz_lazy_simulation.md)) | Триггер по `event_type`; graph — **контекст** для LLM, не замена EventBus |
| ID-3 Witness graph | participants + witness edges могут влиять на subset узлов в подграфе |
| ID-5 Plot economy | `anchor` узла графа = активный macro/micro hook |
| [tz_engine_flow.md](./tz_engine_flow.md) | Expand в фазе `llm`, до commit patches |

### Выигрыш

| Метрика | Эффект |
|---|---|
| Токены | Initial context O(узлы подграфа), не O(вся история мира) |
| Качество | LLM видит **структуру** сюжета (parents) без простыни текста |
| Консистентность | Детали только из expand; hash = audit trail |
| Творчество | LLM выбирает, какие ветки «раскрыть» для narration / нового события |

### Открыто (Todo EV-*)

| ID | Вопрос |
|---|---|
| EV-1 | Hash: content-addressed (canonical JSON → sha256) vs surrogate `world_history.id` |
| EV-2 | Алгоритм выбора подграфа (BFS от anchor? max depth? plot-lock root?) |
| EV-3 | Expand: tool call vs dedicated repair-style user message |
| EV-4 | Кэш expand в `state.node_results` на pass (не re-fetch DB) |
| EV-5 | Новые события от LLM: propose → validate → persist → **новый hash** в ответе |
| EV-6 | Отдельное ТЗ `tz_events.md` при старте impl |

### Не путать

- **Не RAG и не lore search:** граф детерминированно собран движком из **событий** в БД; expand = fetch события по hash, не semantic retrieval по тексту мира.
- **Не замена simulation:** compact graph — только **transport** канонических событий в LLM; факты остаются в `world_history` / patches.
- **Не смешивать с лором:** поиск/подгрузка lore — отдельная задача (если понадобится), вне scope ID-13.

### Комментарий: LLM ergonomics (review агента, 2026-07)

Оценка с точки зрения **как модель потребляет контекст** — не вердикт по новизне.

**Почему compact graph удобен модели**

| Элемент | Эффект для LLM |
|---|---|
| `title` | Семантический вес события без простыни; модель решает, нужен ли expand |
| `parents` (1–3) | Причинная структура как outline, не как narrative memory |
| `participants` (uid) | Якоря к сущностям мира; меньше дрейфа имён |
| expand по **whitelist** | Запросы осмысленные; без whitelist — «любопытство» и раздувание контекста |

**Почему идея хорошо стыкуется с simulation-first**

Движок держит факты; модель не обязана «помнить» прошлое в prose — она **запрашивает** канон. Для narration: игрок спрашивает про старое событие → expand одного узла → ответ из фактов, не из додумывания.

**Рекомендации по expanded payload**

- Плотный **структурированный** expand: даты, тип, `effects_summary` (states, accessibility, terrain patch uid).
- Минимум литературной прозы в expand — prose оставить **Narrator**-ноде (ID-9); иначе expand дублирует narration и снова жрёт токены.
- `title` в compact node пишет **движок при persist**, не LLM при создании события — иначе заголовки расплывчатые.

**Риски (на impl)**

| Риск | Митигация |
|---|---|
| Цитирование деталей без expand | Validator v2: детали past events только из expanded nodes |
| Плоский подграф («последние K») | BFS от anchor / plot-lock root, не только timestamp |
| Expand-spam за turn | Лимит 1–3 expand на turn |
| Путаница с RAG | Явный контракт: граф только из БД, детерминированная сборка |

**Первый smoke (когда дойдёт очередь)**

Один квест, 5–7 узлов в графе, ≤1 expand за turn — проверить, хватает ли narrator без полной истории.

**Итог review:** практичный компромисс для длинной кампании; не замена witness / plot-lock / `world_history`, а **транспортный слой** контекста для LLM внутри validation-first архитектуры.

---


## ID-14 — Bounded NPC reaction turn (ограничение автономии NPC в интерактивной сцене)

**Status:** `open` | **Priority:** P0 | **Layer:** engine / narrative

### Проблема

В сцене с несколькими NPC независимые LLM-реакции легко образуют рекурсивную цепочку:

```
player → NPC A → NPC B → NPC A → NPC C → ...
```

Даже если такая цепочка логически допустима, для интерактивной RPG она создаёт три проблемы:

1. растёт число LLM-вызовов и стоимость inference;
2. игрок долго ждёт завершения автономного диалога;
3. NPC начинают играть сцену между собой, отнимая agency и темп у игрока.

### Инвариант интерактивного хода

**По умолчанию одно сообщение / действие игрока открывает не более одного NPC reaction beat.**

```
PLAYER INPUT
    → intent
    → engine / DAG
    → eligible NPC reactions
    → resolve / validate / commit
    → scene aggregation + narration
    → TURN CLOSED
    → wait for player
```

Выход NPC в текущем reaction beat **не имеет права автоматически открыть новый полноценный NPC LLM-turn в рамках того же player turn**.

Новые события (реплика NPC A, жест NPC B, изменение состояния) могут быть зафиксированы движком и восприняты другими NPC, но их следующая семантически нетривиальная LLM-реакция откладывается до следующего разрешённого beat / сообщения игрока.

### Настройка

Черновой world/session setting:

```
npc_autonomous_reaction_beats_per_player_turn = 1
```

| Значение | Семантика |
|---:|---|
| `0` | NPC не получают автономного продолжения диалога |
| `1` | **default:** один общий reaction beat после player intent |
| `N > 1` | разрешить до N последовательных reaction beats (опциональный режим) |

Это **общий бюджет сцены**, а не N вызовов на каждого NPC.

### Multi-NPC сцена

Присутствие NPC в сцене само по себе не означает LLM-call.

До LLM движок фильтрует кандидатов:

```
present
  → perceived event?
  → event relevant?
  → motivation to react?
  → semantic reasoning required?
  → NPC LLM call
```

В одном разрешённом beat несколько релевантных NPC могут получить отдельные role/knowledge projections и сформировать независимые proposals. После этого proposals агрегируются и разрешаются движком, а player-facing сцена склеивается отдельно.

```
                 ┌→ NPC A context → proposal ─┐
PLAYER → INTENT ─┼→ NPC B context → proposal ─┼→ resolve → aggregate → narrator → STOP
                 └→ NPC C context → proposal ─┘
```

### Не путать с background simulation

Ограничение относится к **интерактивному LLM-нарративу**, а не к существованию мира.

Background simulation может продолжать отношения, экономику, распространение информации, встречи и другие процессы без участия игрока. Это не требует разыгрывать каждый NPC↔NPC обмен отдельными LLM-вызовами.

```
continuous simulation != continuous interactive narration
```

Движок может агрегировать фоновые взаимодействия в события / patches / beliefs и поднимать LLM только по существующим trigger/relevance правилам.

### Forced consequences

Физические и детерминированные последствия текущего beat не считаются новым NPC-turn:

- персонаж упал после уже разрешённого удара;
- дверь закрылась;
- NPC услышал уже произнесённую реплику;
- committed action изменил позицию / состояние.

Но такое последствие **не должно рекурсивно запускать новый NPC cognition call** после исчерпания бюджета текущего player turn.

### Связь с существующим

| Сущность | Роль |
|---|---|
| ID-4 Scene notebook | хранит volatile state текущей сцены / turn |
| ID-9 Director vs Narrator | NPC proposals и финальная склейка сцены — разные обязанности |
| R-3 ambient NPC LLM each tick | bounded turn дополняет запрет массовых бессмысленных LLM-вызовов |
| [tz_lazy_simulation.md](./tz_lazy_simulation.md) | relevance / essential NPC triggers до LLM |
| [tz_engine_flow.md](./tz_engine_flow.md) | turn budget должен enforcement-иться orchestration слоем, а не prompt-инструкцией |

### Ключевой принцип

> **NPC presence ≠ NPC LLM call. Simulation may be continuous; interactive narration is bounded by the player's turn.**

Ограничение должно быть **engine invariant**, а не просьбой к LLM «не продолжать слишком долго».

### Открыто

- Где хранить budget: `SceneContext`, session settings или world preset.
- Как маркировать `turn_id` / `reaction_beat_id` в DAG.
- Нужен ли отдельный emergency/interrupt budget для событий, которые обязаны немедленно получить семантическую реакцию.
- Должен ли narrator получать только committed results текущего beat или также краткий deferred-reactions hint (скорее нет в v1).
- Политика параллельных NPC calls: parallel snapshot vs deterministic ordering при конфликтующих proposals.

---


## Rejected / deferred (сознательно не брать)

| ID | Идея | Решение | Причина |
|---|---|---|---|
| R-1 | LLM-generated geometry | `rejected` | Против skeleton-first ([tz_city_generation.md](./tz_city_generation.md)) |
| R-2 | RAG как primary memory | `deferred` | State в БД + snapshot; RAG — опциональный lore lookup |
| R-3 | LLM каждому ambient NPC каждый тик | `rejected` | [tz_lazy_simulation.md](./tz_lazy_simulation.md) LOD |
| R-4 | Спешить world gen DAG wiring | `deferred` | Topology materialization — отдельная фаза ([tz_world_generation_dag.md](./tz_world_generation_dag.md)) |
| R-5 | Multi-agent city sim (AgentCity-style) | `rejected` | Другой продуктовый класс |

---

## Impl queue (рекомендуемый порядок)

Не блокирует текущий цикл generators / JSON validation / DAG topology design.

| Phase | IDs | Зависимости |
|---|---|---|
| **A — Пресеты** | ID-6, ID-10 | JSON validation v0.1+ |
| **B — Engine UX** | ID-9, ID-4, **ID-14** | Scene/narration DAG (когда topology готов) |
| **C — Социальный слой** | ID-3, ID-1, ID-2 | EventBus, `world_history` |
| **D — Сюжет** | ID-5, ID-8, **ID-13** | ID-3, plot TaskTypes, `world_history` |
| **E — Master tools** | ID-7 | world snapshot |
| **F — Distribution** | ID-11 | product |

---

## Todo (документ)

| ID | Задача | Status |
|---|---|---|
| DOC-1 | Ссылка на `tz_ideas.md` из [tz_lazy_simulation.md](./tz_lazy_simulation.md) (witness + beliefs) | open |
| DOC-2 | При impl ID-6 — секция manifest в [tz_json_import.md](./tz_json_import.md) | open |
| DOC-3 | При impl ID-4 — поле `scene_notebook` в [tz_engine_node_context.md](./tz_engine_node_context.md) | open |
| DOC-4 | При impl ID-13 — вынести в `tz_events.md` (graph hash + expand protocol) | open |

---

## История

| Версия | Дата | Изменение |
|---|---|---|
| 0.1 | 2026-07 | Initial registry: research synthesis + product vision (master preset / player play) |
| 0.2 | 2026-07 | ID-13: Event Graph Hash — lazy disclosure сюжета |
| 0.3 | 2026-07 | ID-13: происхождение (independent engineering); § LLM ergonomics review |
| 0.4 | 2026-07 | ID-13: инварианты (событие в движке); событие ≠ лор |
| 0.5 | 2026-09 | ID-14: bounded NPC reaction turn — default 1 beat per player turn, anti-loop invariant |
| 0.6 | 2026-09 | ID-9 expanded: configurable LLM roles — Intent, NPC, Background Planner / GM, Narrator; role-specific context/knowledge boundaries |
| 0.7 | 2026-09 | ID-9: model-specific DSL profiles + deterministic fallback exact model → family/type → role default |
