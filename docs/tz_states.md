---
name: tz-states
description: "ТЗ по государствам — структура, принадлежность локаций, гражданство персонажей, линия правителей, экспорт с миром"
metadata: 
  node_type: memory
  type: project
  originSessionId: 633eddca-8d16-4119-94ab-ef548d071851
---

## Суть

Государство — политическая сущность, контролирующая территорию. Отдельно от фракций: фракция = группа людей с интересами, государство = политический контроль над географией.

---

## Реестры в `worlds` (N+1)

Все реестры — чистые лейблы без механических флагов. Пользователь добавляет свои типы под любой сеттинг (фэнтези, современность, sci-fi).

### `worlds.state_structure_registry`
```json
[
  { "system_structure": "empire",        "display_structure": "Империя"           },
  { "system_structure": "nation",        "display_structure": "Нация"             },
  { "system_structure": "city_state",    "display_structure": "Город-государство" },
  { "system_structure": "confederation", "display_structure": "Конфедерация"      },
  { "system_structure": "tribal",        "display_structure": "Племенной союз"    },
  { "system_structure": "nomadic",       "display_structure": "Кочевое"           },
  { "system_structure": "colonial",      "display_structure": "Колония"           }
]
```

### `worlds.state_governance_registry`

Каждый тип принадлежит `governance_category`. Движок использует категорию для проверок (иерархия, линия правителей, succession и др.). Пользователь добавляет свои типы, указывая категорию.

```json
[
  { "system_governance": "monarchy",                   "display_governance": "Монархия",                      "governance_category": "singular"                      },
  { "system_governance": "dictatorship",               "display_governance": "Диктатура",                     "governance_category": "singular"                      },
  { "system_governance": "imperial",                   "display_governance": "Имперское",                     "governance_category": "singular"                      },
  { "system_governance": "diarchy",                    "display_governance": "Диархия",                       "governance_category": "singular"                      },
  { "system_governance": "oligarchy",                  "display_governance": "Олигархия",                     "governance_category": "oligarchic"                    },
  { "system_governance": "plutocracy",                 "display_governance": "Плутократия",                   "governance_category": "oligarchic"                    },
  { "system_governance": "timocracy",                  "display_governance": "Тимократия",                    "governance_category": "oligarchic"                    },
  { "system_governance": "patricracy",                 "display_governance": "Патрициат",                     "governance_category": "oligarchic"                    },
  { "system_governance": "republic",                   "display_governance": "Республика",                    "governance_category": "democratic"                    },
  { "system_governance": "democracy",                  "display_governance": "Демократия",                    "governance_category": "democratic"                    },
  { "system_governance": "ergatocracy",                "display_governance": "Эргатократия",                  "governance_category": "democratic"                    },
  { "system_governance": "meritocracy",                "display_governance": "Меритократия",                  "governance_category": "meritocratic"                  },
  { "system_governance": "technocracy",                "display_governance": "Технократия",                   "governance_category": "meritocratic"                  },
  { "system_governance": "geniocracy",                 "display_governance": "Гениократия",                   "governance_category": "meritocratic"                  },
  { "system_governance": "noocracy",                   "display_governance": "Ноократия",                     "governance_category": "meritocratic"                  },
  { "system_governance": "theocracy",                  "display_governance": "Теократия",                     "governance_category": "ideological"                   },
  { "system_governance": "magocracy",                  "display_governance": "Магократия",                    "governance_category": "ideological"                   },
  { "system_governance": "communism",                  "display_governance": "Коммунизм",                     "governance_category": "ideological"                   },
  { "system_governance": "kritarchy",                  "display_governance": "Критархия",                     "governance_category": "judicial"                      },
  { "system_governance": "military_junta",             "display_governance": "Военная хунта",                 "governance_category": "military"                      },
  { "system_governance": "stratocracy",                "display_governance": "Стратократия",                  "governance_category": "military"                      },
  { "system_governance": "corporate",                  "display_governance": "Корпоративное",                 "governance_category": "corporate"                     },
  { "system_governance": "megacorporation",            "display_governance": "Мегакорпорация",                "governance_category": "corporate"                     },
  { "system_governance": "anarchy",                    "display_governance": "Анархия",                       "governance_category": "anarchic"                      },
  { "system_governance": "ochlocracy",                 "display_governance": "Охлократия",                    "governance_category": "anarchic"                      },
  { "system_governance": "necrocracy",                 "display_governance": "Некрократия",                   "governance_category": "supernatural"                  },
  { "system_governance": "living_god",                 "display_governance": "Живое божество",                "governance_category": "supernatural"                  },
  { "system_governance": "divine_mandate",             "display_governance": "Божественный мандат",           "governance_category": "supernatural"                  },
  { "system_governance": "ai_governance",              "display_governance": "ИИ-управление",                 "governance_category": "synthetic_ai"                  },
  { "system_governance": "cybercracy",                 "display_governance": "Киберкратия",                   "governance_category": "synthetic_ai"                  },
  { "system_governance": "consciousness_network",      "display_governance": "Сеть сознаний",                 "governance_category": "synthetic_collective"           },
  { "system_governance": "borg_collective",            "display_governance": "Боргоподобный коллектив",       "governance_category": "synthetic_individual_collective"},
  { "system_governance": "ai_federation",              "display_governance": "ИИ-федерация",                  "governance_category": "synthetic_individual_collective"},
  { "system_governance": "fungal_network",             "display_governance": "Грибная сеть",                  "governance_category": "organic_collective"             },
  { "system_governance": "telepathic_collective",      "display_governance": "Телепатический коллектив",      "governance_category": "organic_collective"             },
  { "system_governance": "hive_mind",                  "display_governance": "Улей",                          "governance_category": "organic_collective"             },
  { "system_governance": "insect_hive",                "display_governance": "Насекомый улей",                "governance_category": "organic_individual_collective"  },
  { "system_governance": "zerg_swarm",                 "display_governance": "Рой",                           "governance_category": "organic_individual_collective"  },
  { "system_governance": "sortition",                  "display_governance": "Сортиция",                      "governance_category": "random"                        },
  { "system_governance": "lottery_governance",         "display_governance": "Лотерейное управление",         "governance_category": "random"                        }
]
```

### `worlds.governance_category_registry` (N+1)

Категории — тоже реестр. Пользователь добавляет свои под любой сеттинг.

| `system_category` | Суть |
|---|---|
| `singular` | Один или два правителя, биологический |
| `oligarchic` | Малая группа у власти |
| `democratic` | Большинство / выборная власть |
| `meritocratic` | Способность/знание определяет власть |
| `ideological` | Доктрина первична, не личность |
| `judicial` | Закон и судьи — есть государство |
| `military` | Военная власть |
| `corporate` | Акционеры, прибыль, дочерние структуры |
| `anarchic` | Нет или сломана центральная власть |
| `supernatural` | Нечеловеческие сущности у власти |
| `synthetic_ai` | ИИ управляет, нет биологического правителя |
| `synthetic_collective` | Цифровой коллектив, нет индивидуальных правителей |
| `synthetic_individual_collective` | Цифровой коллектив + индивидуальные правители + верховный |
| `organic_collective` | Биологический коллектив, нет индивидуальных правителей |
| `organic_individual_collective` | Биологический коллектив + индивидуальные правители + верховный |
| `random` | Жребий / случай определяет власть |

Движок проверяет `governance_category` родителя при создании дочернего государства (`parent_state_uid`). Категории без индивидуальных правителей (`synthetic_collective`, `organic_collective`, `anarchic`) — иерархия запрещена.

### `worlds.ruler_title_registry`
```json
[
  { "system_title": "king",       "display_title": "Король"      },
  { "system_title": "queen",      "display_title": "Королева"    },
  { "system_title": "emperor",    "display_title": "Император"   },
  { "system_title": "president",  "display_title": "Президент"   },
  { "system_title": "chancellor", "display_title": "Канцлер"     },
  { "system_title": "consul",     "display_title": "Консул"      },
  { "system_title": "chieftain",  "display_title": "Вождь"       },
  { "system_title": "director",   "display_title": "Директор"    },
  { "system_title": "overseer",   "display_title": "Надзиратель" }
]
```

### `worlds.ruler_end_reason_registry`
```json
[
  { "system_reason": "death",       "display_reason": "Смерть"      },
  { "system_reason": "abdication",  "display_reason": "Отречение"   },
  { "system_reason": "conquest",    "display_reason": "Завоевание"  },
  { "system_reason": "election",    "display_reason": "Выборы"      },
  { "system_reason": "coup",        "display_reason": "Переворот"   },
  { "system_reason": "exile",       "display_reason": "Изгнание"    },
  { "system_reason": "deposition",  "display_reason": "Низложение"  },
  { "system_reason": "merger",      "display_reason": "Объединение" },
  { "system_reason": "dissolution", "display_reason": "Роспуск"     }
]
```

---

## Таблица `states`

```sql
states (
  state_uid,
  world_uid,               -- FK → worlds
  system_name,             -- для движка и LLM
  display_name,
  system_description,
  display_description,
  state_structure,         -- NOT NULL; ref → worlds.state_structure_registry
  state_governance,        -- NOT NULL; ref → worlds.state_governance_registry
  parent_state_uid,        -- nullable; soft ref → states (иерархия: вассал, провинция, автономия)
  capital_location_uid,    -- nullable; soft ref → named_locations
  founder_uid,             -- FK → character_sheet; NOT NULL
  system_founded_date,     -- дата основания в игровом времени
  display_founded_date,
  is_active,               -- bool; false = государство пало, хранится в нарративе
  glossary_ref,            -- nullable; ref → lore_registry
  tag_refs,                -- nullable JSON array
  created_at
)
```

**Правила:**
- `state_structure` и `state_governance` — NOT NULL, обязательны при создании
- `capital_location_uid` — soft ref: если столица удалена → государство не удаляется, движок логирует
- `founder_uid` — жёсткий FK, всегда реальный персонаж в `character_sheet`. Создаётся по упрощённым правилам (не полный флоу генерации персонажа). Детали — отдельная задача
- `parent_state_uid` — soft ref: если родительское государство удалено, дочернее остаётся; движок логирует orphan
- `is_active = false` — государство пало, но остаётся в БД для нарратива и истории

---

## Таблица `state_rulers`

```sql
state_rulers (
  id,
  state_uid,          -- FK → states ON DELETE CASCADE
  character_uid,      -- soft ref → character_sheet; nullable (легендарные/досимуляционные правители)
  display_name,       -- fallback когда character_uid = null
  system_title,       -- ref → worlds.ruler_title_registry
  display_title,
  system_start_date,
  display_start_date,
  system_end_date,    -- nullable = текущий правитель
  display_end_date,
  end_reason          -- nullable; ref → worlds.ruler_end_reason_registry
)
```

**Правила:**
- Текущий правитель = запись с `system_end_date IS NULL`
- Несколько записей с `system_end_date IS NULL` — допустимо (соправители, консулы)
- `end_reason` заполняется только при закрытии правления (`system_end_date NOT NULL`)
- `character_uid` — soft ref: правитель может быть легендарной фигурой без записи в `character_sheet`; тогда `display_name` обязателен

---

## Привязка локаций

Поле `state_uid` (nullable, soft ref) на `named_locations`.

**Правила:**
- Денормализовано: каждый уровень иерархии хранит `state_uid` явно, без наследования от родителя. Settlement может принадлежать другому государству чем его territory (вольный город, оккупация, анклав)
- Orphan-tolerant: `state_uid` указывает на несуществующее государство → локация ничейная, движок логирует, БД не чистится
- Изменение границ кочевых государств — через `world_history`, не через флаги типа

---

## Гражданство персонажей

Поле `system_citizenships` (nullable JSON array of state_uids) на `character_sheet` для обоих типов — player и npc.

**Правила:**
- Массив: персонаж может быть гражданином нескольких государств
- display-версия не хранится — имена резолвятся из `states` при рендере
- Orphan-tolerant: несуществующий state_uid в массиве → движок фильтрует, логирует

---

## Экспорт с миром

Государства — часть world JSON. Если `states` отсутствует в JSON → мир без государств. `state_uid` на локациях остаются в БД, но считаются ничейными (orphan-tolerant).

---

## Открытые вопросы

| Элемент | Статус |
|---|---|
| Правила инициализации founder | упрощённый флоу создания персонажа-основателя; детали отдельно |
| Дипломатия | таблица `state_relations` (мир/война/нейтралитет); отложено |
| Engine flow | когда и как движок подаёт государство в контекст LLM; отложено |
