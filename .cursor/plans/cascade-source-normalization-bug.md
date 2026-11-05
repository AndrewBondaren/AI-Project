# Runtime: каскад получает dict после проверки economic_tier_range

**Статус: OPEN.** Воспроизведено 2026-11-05 в runtime через `area_context`. При построении контекста области (уровень AREA) материализация диапазона падает с `AttributeError: 'dict' object has no attribute 'min'`.

## Воспроизведение

Из корня репозитория перейти в `backend` и выполнить следующий Python-код. Фикстура создаёт мир с зарегистрированными экономическими уровнями `t1` и `t9`.

```python
from tests.test_cascade_context_baseline import fixture
from app.application.cascade.locationScope import area_context, empty_location_chain
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate

world, _, _ = fixture()
plot = PlotLayoutTemplate(system_name="plot", display_name="Plot")
plot = plot.model_copy(update={"economic_tier_range": {"min": "t1", "max": "t9"}})
parent = empty_location_chain(world, ScopeLevel.DISTRICT)
area_context(world, parent, plot, area_uid="probe")
```

## Причина и контракт

`model_copy(update=...)` сохраняет переданный словарь без проверки типа вложенного поля. [validate_source](../../backend/app/application/jsonValidation/sourceValidation.py#L77) повторно проверяет модель через `resolve_model`, но отбрасывает полученный объект и передаёт исходный в `validate_prepared_source`. [area_context](../../backend/app/application/cascade/locationScope.py#L105) также игнорирует возвращённое значение и строит `Link` из исходного `plot`. Поэтому [материализатор](../../backend/app/application/worldData/generators/utils/economicTierBands.py#L62) получает словарь и падает при чтении `raw.min`.

[Поле POJO](../../backend/app/dataModel/locations/structure/building/plotLayoutTemplate.py#L77) имеет default `None` и допускает явный `null`. Когда диапазон задан, [EconomicTierRange](../../backend/app/dataModel/shared/ranges.py#L27) требует обе границы. В примере значения валидны: после проверки каскад должен получить `EconomicTierRange` и построить контекст.

## Цепочка и границы исправления

1. В генерации `derive_structure_context` передаёт готовый `PlotLayoutTemplate` в `area_context` до построения building-контекста. В проведённом поиске по `backend/app` не найден прямой вызов `model_copy(update=...)`, который устанавливает словарь именно в `economic_tier_range`. Воспроизведение доказывает дефект на входе runtime API; частота появления такого объекта при обычной загрузке мира не установлена.
2. `validate_source` проверяет полную модель из `model_dump(exclude_unset=True)`. Затем `validate_prepared_source` разбирает значение канала через `TypeAdapter` в локальную переменную: реестр и порядок min/max проверяются по типизированному диапазону, а возвращается исходная модель. Обе проверки могут пройти успешно при неправильном типе в объекте для `Link`.
3. [extend](../../backend/app/application/cascade/contextResolver.py#L104) проверяет привязку звена к уровню, сохраняет глубокую копию и читает поле выбранного канала через `getattr`. Копирование сохраняет тип вложенного значения. Для RANGE вызывается материализатор; ошибка на `raw.min` возникает **до** выбора кандидатов, привязки к унаследованному tier или вызова RNG.

**Контрольный эксперимент на настоящем каскаде.** Для AREA и DISTRICT созданы модели с одинаковым диапазоном t1–t9 двумя способами: штатный конструктор и `model_copy` со словарём. На втором входе оба публичных scope-builder падают с одинаковым `AttributeError`. В отдельном прогоне в builder передан результат полного resolve и доменных проверок: для каждого уровня при том же родителе и UID совпали tier (t1 на данной фикстуре), provenance и набор явно заданных полей с эталоном. Для неизвестного min оба уровня вернули `REF_W_UNKNOWN`, для обратного диапазона — `DOMAIN_RANGE`; в обоих случаях `extend` не вызывался.

**Предлагаемые изменения.** В `sourceValidation.py` вернуть результат проверки именно разрешённой модели (сохранить тип конкретного POJO). В `locationScope.py` строить звенья из возвращённых объектов: AREA — plot; DISTRICT — сохранить порядок «именованная локация, затем шаблон»; SETTLEMENT — сохранить порядок трёх источников; BUILDING и ROOM — передать проверенный одиночный источник. Для последних трёх уровней обнаружена та же потеря результата по коду, но идентичное падение не воспроизводилось. Не заменять вход новым объектом через мутацию оригинала. Существующие `resolve_ctx`, location и `scope_rng(world_uid, scope_uid, "tier")` сохранить. Алгоритм `extend/_resolve`, snapshot родителя и материализатор диапазона уже дают эталонный результат на правильном входе. Устранение дополнительной валидации в `NamedLocationService._from_wire` и проверка необходимости `TypeAdapter` у прямых callers — отдельная оптимизация.

## Критерии закрытия

- Регрессионный тест вызывает настоящий `area_context` на входе выше. Результат совпадает с результатом для того же шаблона, созданного обычной валидацией, при тех же мире и `area_uid`.
- Отсутствующее поле и явный `None` сохраняют прежнее поведение. Для неизвестной границы проверка выдаёт `REF_W_UNKNOWN` до передачи в `extend`.
- Повторить регрессию на `district_context`; проверить отсутствие мутации исходного шаблона и родительского контекста. Для остальных scope-builder проверить передачу результата и прежний порядок звеньев.
