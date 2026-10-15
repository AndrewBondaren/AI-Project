# ТЗ: Архитектурный стиль (TODO)

> **Статус:** черновик-todo. `architectural_style` сейчас используется только как метаданные для LLM.  
> Полноценная реализация — создание шаблонов зданий с геометрией под конкретные стили.

---

## 1. Текущий статус

**Opt-out global canonical attach lore (library-packs, шаг 7, 2026-10-16):**
`worlds.lore_registry` — inline map мира, identity — ключ map (`glossary_ref` /
`lore_ref`). Источник — world map; при пустом реестре применяется
`WorldLoreRegistry.canonical_defaults()` через WorldSlice. SQL library/FS-паков
и global spec нет; T-29 list merge не применяется. Pack migration lore deferred.

`architectural_style` — поле `CitySkeleton` и `NamedLocation` поселения.  
Используется **только LLM** для визуального языка описаний через `lore_registry[glossary_ref]`.

Генератор зданий и ассемблеры **не используют** `architectural_style` при выборе материалов или алгоритмов — это зона `economic_tier` и пользовательских реестров.

---

## 2. Реестр (`worlds.architectural_style_registry`)

```json
[
  { "system_style": "medieval_stone",  "glossary_ref": "style_medieval_stone"  },
  { "system_style": "nordic_wood",     "glossary_ref": "style_nordic_wood"     },
  { "system_style": "mediterranean",   "glossary_ref": "style_mediterranean"   },
  { "system_style": "cyberpunk",       "glossary_ref": "style_cyberpunk"       },
  { "system_style": "brutalist",       "glossary_ref": "style_brutalist"       }
]
```

`display_*` и описание — из `lore_registry` по `glossary_ref`.

---

## 3. TODO: шаблоны с геометрией под стиль

Идея: подготовить наборы `building_template` с геометрией характерной для конкретного стиля.  
Пользователь импортирует шаблоны нужного стиля в мир.

Примеры:
- `medieval_stone` → арочные проёмы, толстые стены, узкие окна-бойницы, башни
- `nordic_wood` → деревянные фасады, крутые скатные крыши, резьба
- `cyberpunk` → плоские крыши, панорамное остекление, внешние конструкции
- `brutalist` → массивные прямоугольные объёмы, минимум декора, бетон

Механика выбора шаблона по стилю — не описана. Открытый вопрос: фильтр в библиотеке шаблонов мира (pack membership; `building_template_registry` удалён в B7) по тегу стиля или отдельный реестр шаблонов на стиль.

---

## 4. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Фильтр шаблонов по стилю — тег на шаблоне или отдельный реестр | не описан |
| Один город = один стиль или районы могут иметь разные стили | не описан |
| Геометрические параметры стиля (пропорции, формы проёмов) — в шаблоне или в реестре стиля | не описан |
