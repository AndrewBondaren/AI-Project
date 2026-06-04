# ТЗ: Иерархия ассемблеров

## 1. Структура

```
CityAssembler
    └── DistrictAssembler
            └── StructureAreaAssembler
                    └── StructureAssembler
                            └── StructureGenerator (BuildingGeneratorService)
                                    └── StructureInteriorAssembler
```

Каждый слой самодостаточен. Вход в иерархию — на нужном уровне.

---

## 2. Слои

### CityAssembler
**Знает:** city skeleton (economic_tier, architectural_style, dominant_material, settlement_density)  
**Делает:** сетка улиц, типы кварталов, слоты зданий  
**Подробнее:** [tz_city_generation.md](tz_city_generation.md)

### DistrictAssembler
**Знает:** тип квартала, city skeleton  
**Делает:** назначает `building_template` каждому слоту по structure_type + economic_tier  
**Подробнее:** [tz_city_generation.md](tz_city_generation.md) — раздел 6 (алгоритм заполнения кварталов)

### StructureAreaAssembler
**Знает:** слот (позиция + размер), шаблон, city skeleton, terrain  
**Делает:**
- планировка участка: двор, забор (`barrier_template_registry`), малые постройки
- выводит `StructureContext` из `structure_type` + `architectural_style` + terrain
- вызывает `StructureAssembler`

**Источник `StructureContext`:** этот слой. Только он знает достаточно для вывода контекста.  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11 (StructureAssembler, StructureContext)

### StructureAssembler
**Знает:** `StructureContext`, terrain_cells  
**Делает:** фундамент + крыльцо/ступени + крыша поверх interior box  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — раздел 11

### StructureGenerator (BuildingGeneratorService)
**Знает:** шаблон, world  
**Делает:** interior box — комнаты, стены, проходы, wall_openings  
**Подробнее:** [tz_building_generator.md](tz_building_generator.md) — разделы 3–10

### StructureInteriorAssembler
**Знает:** `BuildingLayout` (готовая геометрия), шаблон, world, city skeleton  
**Делает:** наполнение интерьера — мебель, предметы, атмосфера  
- `location_objects`: столы, стулья, кровати, полки, очаги
- стартовый инвентарь комнат и контейнеров
- декор: факелы, ковры, картины

Размещение NPC — **отдельный слой**, не входит сюда.

**Статус:** нет ТЗ; реализуется после системы предметов

---

## 3. Точки входа

| Сценарий | Точка входа |
|---|---|
| Полная городская генерация | `CityAssembler` |
| Отдельный квартал | `DistrictAssembler` |
| Здание на участке (ручное размещение, редактор) | `StructureAreaAssembler` |
| Корабль, данж, изолированное здание | `StructureAssembler` |
| Срез мегаздания (`foundation="none"`, `roof="none"`) | `StructureGenerator` |
| Наполнение уже сгенерированного здания (предметы, NPC) | `StructureInteriorAssembler` |

---

## 4. Поток данных

```
CityAssembler
  city_skeleton → DistrictAssembler
    district_type + template_slot → StructureAreaAssembler
      StructureContext (выводится здесь) → StructureAssembler
        terrain_cells + context → StructureAssembler._generate_foundation/_generate_roof
        template + world        → StructureGenerator → BuildingLayout
                                      BuildingLayout + world → StructureInteriorAssembler
                                                                    → location_objects, инвентарь, декор
```

Нижние слои **не знают** о верхних. `StructureGenerator` не знает существует ли город.

---

## 5. Открытые вопросы

| Вопрос | Статус |
|---|---|
| `StructureAreaAssembler` — алгоритм вывода `StructureContext` из `structure_type` + `architectural_style` | не описан |
| `DistrictAssembler` — правила выбора шаблона для слота | частично в [tz_city_generation.md](tz_city_generation.md) раздел 6 |
| Малые постройки на участке (`StructureAreaAssembler`) | нет ТЗ |
| `StructureInteriorAssembler` — алгоритм размещения мебели и предметов | нет ТЗ; зависит от системы предметов |
| Размещение NPC — отдельный слой поверх готового интерьера | нет ТЗ |
