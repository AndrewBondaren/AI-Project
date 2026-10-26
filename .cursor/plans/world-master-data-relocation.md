# TODO: `worldMasterData` — не dataModel, место в валидаторе

## Проблема

`backend/app/application/worldData/generators/masterData/worldMasterData.py` сейчас лежит в дереве **generators** и по сути делает **resolve**: сырой `world` → parse POJO → fallback на `dataModel.canonical_*()`.

Это **не данные** и **не место в dataModel**:
- `dataModel/` — только POJO, enum, `canonical_defaults()` / `canonical_engine()` (чем заполнить поля по дефолту).
- Логика «пусто / битое → подставить builtin» — **не часть модели данных**.

## Куда переносить

**`application/worldData/jsonValidation/`** (валидатор / normalize-слой), рядом с существующими:
- `normalize/climateDefaults.py`, `normalize/hydrologyDefaults.py`
- `validators/*` + facade/orchestrator

Единая ответственность валидатора при импорте и для генераторов:
1. validate wire
2. normalize + fill defaults из `dataModel`
3. отдать **уже нормализованный** master-data view (typed POJO или dict)

Генераторы после переноса импортируют из валидатора/facade, **не** из `generators/masterData/` и **не** вызывают `canonical_*` напрямую.

## Scope переноса

- [ ] Переместить `worldMasterData.py` → `jsonValidation/` (имя на усмотрение мастера: `normalize/worldMasterData.py` или методы на facade).
- [ ] Обновить ~20 импортов в `generators/` на новый путь.
- [ ] Удалить `generators/masterData/` после миграции.
- [ ] То же для settlement resolve, сейчас вне masterData: `buildingDefaults.merge_*`, `footprint.district_templates`, `footprint.footprint_multiplier` — в валидатор/normalize, не в planner.
- [ ] `climate/registry.profile_for` — resolve поверх нормализованных zones + `ClimateZone` enum; не дублировать parse в generator.

## Не трогать

- `dataModel/` — только данные и дефолты; без `from_world`, без merge.
- Перенос блокировать на рефактор валидатора, если мастер ведёт jsonValidation отдельно — согласовать с текущим rebuild.

## Ссылки

- Текущий модуль: `backend/app/application/worldData/generators/masterData/worldMasterData.py`
- Аналоги в валидаторе: `jsonValidation/normalize/*Defaults.py`, `jsonValidation/facade.py`
