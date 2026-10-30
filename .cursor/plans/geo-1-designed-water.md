# GEO-1 — designed water: общие стратегии и каскад параметров

Статус: проектирование, не разрешение на код. Принятые решения мастера
от 2026-10-22 перечислены в §1. TARGET specification завершена в §6.25–6.29;
design closure registry — §6.13. Продуктовых вопросов нет; HY-RIV-1 — внешний track.
Первоначальный design-заход менял только этот план. Последующие согласованные
уточнения и нормативный sync PC-0 могут менять профильные ТЗ; код, тесты и
fixtures требуют отдельного implementation шага. Уточнение владельцев и фаз
от 2026-10-22 — §6.30; оно имеет приоритет над прежним baseline описанием.

## 1. Решения мастера

1. Поддерживаются **все** способы: authored region → basin, continental
   noise и plate-модель. Единая абстракция подготовки designed water;
   отдельный проверяемый шаг на каждую стратегию. Выбор одной стратегии
   вместо поддержки остальных не является целевой архитектурой.
2. Доля воды — параметр POJO мира с override отдельного водоёма.
   Terminal fallback — **60%**. Использовать существующий декларативный
   каскад параметров, не ручную цепочку fallback в потребителе.
3. Autoresolve задаётся явно на мире и/или отдельном водоёме и наследуется
   тем же механизмом каскада. Сам факт отсутствия authored water не
   является командой включить autoresolve.
4. Q-5 принят: для глобального процента воды использовать фиксированные
   world_bounds. Они определяют область расчёта, не ocean-edge. Область
   от AABB anchors не должна незаметно менять continental layout.
5. Shore может появляться по собственному условию на границе воды и суши;
   учитывать отсутствие отвесной породы у океана/моря/озера. Уточнение
   реализации ниже: hydrology SHORE и итоговое покрытие берега различаются.
6. Процедурные реки имеют отдельную world-настройку autoresolve по типу
   гидрологии. Выбор истоков учитывает ближайшую наивысшую точку и расстояние;
   точная метрика, опора расстояния и порядок критериев закреплены в §6.10.
7. Q-AREA принят: water_fraction водоёма считается от площади его области
   генерации. Размер/площадь возвращает сам домен региона. Гидрология
   потребляет этот контракт и не вычисляет площадь региона самостоятельно.
8. Q-TARGET принят: процент воды — целевой, не обязательный итог после
   конфликтов/fill. Сохранять authored ограничения и горы, учитывать
   объявленные водоёмы в общей доле, показывать фактический процент.
9. Q-AUTO/default принят после проверки POJO-политик: при отсутствии
   authored autoresolve по всей цепочке terminal fallback False.
   Authored звенья сохраняют None; переход hydrology channels с нынешнего
   concrete True выполняется явно, без изменения общей MaskCategoryPolicy.
10. Настройка strategy следует общей политике каскада world → body.
    Общие настройки гидрологии — отдельный объект настроек мира;
    переиспользуется world.hydrology с общим generation settings POJO,
    без scalar/SQL копий тех же значений.
11. Coastline не вправе переписывать геометрию/топологию гор.
    Missing обязательная опора запрещает создание зависимой coastline.
    Для зависимой boundary без водной опоры effective priority=0, объект
    не создаётся. Source линия создания тела — отдельный input (§5.3).
12. Исключается shore terrain/material покрытие на отвесной породе,
    гидрологическая роль сохраняется. Владелец решения — terrain/relief;
    гидрология потребляет его typed контракт.
13. Система приоритетов принадлежит общему placement-механизму, не
    hydrology/terrain/другому домену. Общее правило всех новых объектов:
    effective placement priority=0 → объект не создаётся. Доменный adapter
    передаёт intent/facts, не определяет смысл нуля и не решает winner.
    Уточнение мастера: домен вправе определять свои default приоритеты
    и поведение policy по контексту. Общий механизм исполняет typed policy,
    не навязывает всем доменам одинаковый default/поведение (§6.8).
14. Рекомендации §5.1/§5.2 приняты мастером: continental_noise — terminal
    strategy default, четыре режима, разделение settings/cascade/field/
    preparation/placement/writer по классам и методам.
15. Обязательный сценарий: autoresolve океана/моря по авторской coastline
    линии. Его нельзя блокировать требованием уже существующего водоёма.
    Архитектурно отделить source линию для создания тела от coastline,
    зависимой от уже принятого/физического тела (§5.3). Приоритеты остаются
    общими; источник не получает скрытый положительный приоритет.
16. Q-AUTO-GATES согласован: enabled=False отключает гидрологию;
    autoresolve наследуется мир → категория → водоём, без скрытого and/or
    после каскада. Autoresolve=False не отменяет authored geometry.
    Все настройки/режимы задать POJO и enum, не raw wire/dict/строками.
17. Уточнение мастера: частные случаи домена **декларируются доменом**,
    но их поведение вместе с приоритетами **разрешает общий policy engine**.
    Domain-local resolve/evaluate с конечным решением запрещены (§6.8).
18. Целевой procedural source search — **по fine/L2 высотам**, не по
    coarse maxima с пересчётом координат. Точный provider, snapshot,
    область и выбор описаны в §6.10; это обязательный контракт HY-RIV-1,
    не альтернативная реализация на усмотрение coding agent.
19. Q-SHORE-UNKNOWN согласован: если допустимость покрытия не разрешена,
    world validation возвращает явную ошибку; runtime сохраняет исходные
    terrain/material и SHORE, не наносит покрытие, выдаёт fallback error
    через существующий WarningError sink (§6.11). Это не тихий success.
20. Для каждого применённого runtime fallback обязателен лог через
    **уже существующий общий logging facade проекта**. Это сквозное
    требование GEO-1/policy, не только shore unknown (§6.12).
21. Snapshot/revision GEO-1 должен допускать замену источника на общий
    WorldSnapshot/Patch System по docs/tz_world_snapshot.md и
    docs/tz_patch_system.md. Локальные terrain snapshots — вычислительные
    immutable views на запуск, не параллельная система capture/restore/
    branch/persist. Граница миграции и требования — §6.15.
22. Общий lifecycle: сначала планировка объекта/набора объектов; любое
    изменение сначала обновляет планировку и зависимые решения;
    материализация только по требованию из актуальной планировки.
    L0/L2 — согласованные представления одной планировки, не независимые
    генерации/placement. Контракты и последствия закреплены в §6.20.
23. Общий planning/cache (§6.21–6.22) согласован как отдельный
    обязательный подготовительный блок PC-0…PC-12. Его реализация и
    приёмка предшествуют основной реализации GEO-1; города/локационные
    кэши остаются вне scope. Нельзя начать G0-PT и последующие code steps
    GEO-1 с намерением добавить общий planning/cache потом.
24. Согласованы выносы A01/A02/A03: междоменная surface composition —
    application/worldData/planning/composition/; общие grid/coordinate
    contracts — dataModel/spatial/grid/. Старые application пути только
    compatibility re-export/delegation, без второй реализации. Exact
    карта и добавленные PC steps обязательны; города не мигрируются.
    Cached payloads — immutable domain plans в dataModel; samplers/
    algorithms в application принимают frozen data и не перечитывают World.

25. Уточнение мастера в PC-0: горы, овраги и геометрия дна моря/океана/озера
    планируются в terrain/relief единым этапом до гидрологии. Общий placement
    сохраняет владение разрешением размещения. Гидрология определяет воду
    и маршруты рек; для прорезки русел повторно вызывается terrain/relief,
    после чего гидрология получает итоговые высоты. L0/L2 потребляют одну
    планировку; повторного выбора гор/оврагов при compose нет. Подробности,
    границы baseline и необходимые уточнения schemas — §6.30.

Ниже указаны целевые поля, размещение типов и шаги; это не существующий
API. Незавершённые contracts явно отмечены в §6.13 и блокируют реализацию.

## 2. Проверенное исходное состояние

- [Долг GEO-1](../../docs/tz_generator_technical_debt.md:504): lowest-component
  synthesis отвергнут; размещение океанского дна принадлежит terrain.
- [Текущий caller](../../backend/app/application/worldData/generators/terrain/passes/surfaceTerrainContext.py:93):
  base surface → pre-1.4 relief snapshot → water placement → relief → hydro.
  HY-12 уже подключён; старые записи о незавершённом wiring не описывают код.
- [Placement pass](../../backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py:60)
  пока вызывается для declared sources; общий batch содержит их prepared
  объекты и пустой accepted. Совместный universe остальных P3 consumers
  ещё не следует считать реализованным.
- [Base terrain](../../backend/app/application/worldData/generators/terrain/passes/surfacePass.py:28)
  строится из elevation pole field и cell noise. Инвентаризация
  dataModel/terrain, hydrology, placement, spatial, topology и ids не
  обнаружила контракта continental/plate generation или water_fraction.
- [BasinSpec](../../backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/basinSpec.py:16),
  [factory](../../backend/app/application/worldData/generators/hydrology/basinSpecFactory.py:15)
  и [relief dispatcher](../../backend/app/application/worldData/generators/terrain/reliefObjects/applyReliefObjectsZ.py:32)
  уже существуют. Дно пишет relief; raised mountain cells передаются как
  reserved. Второй bathymetry writer GEO-1 не нужен.
- [Coastline fact](../../backend/app/application/worldData/placement/adapters/water.py:127)
  сегодня получается по pre-carve высотам кандидата. Будущий fill не опора.
- [Область terrain](../../backend/app/application/worldData/generators/terrain/passes/bbox.py:58)
  может зависеть от anchors при отсутствии authored world_bounds.
- [Legacy producer рек](../../backend/app/application/worldData/generators/hydrology/autoresolve/proceduralRiverAutoresolve.py:22)
  остаётся отдельным downstream; его замена не выполнена GEO-1.

## 3. Каскад: использовать существующий механизм

SoT: [tz_cascade_context §2–4](../../docs/tz_cascade_context.md:110).
Это linked list полей POJO, объявленный через CascadeChannel и
типизированные FieldRef/CascadeLink. Cascade — единый объект параметра;
порядок определяют ссылки, не порядок enum и не список if/elif.
Terminal default читается через CascadeDefault(FieldRef(...)) из POJO.

Переиспользовать [cascadeSpec](../../backend/app/dataModel/cascade/cascadeSpec.py:1),
[cascadeGraph](../../backend/app/dataModel/cascade/cascadeGraph.py:1),
[общий extend](../../backend/app/application/cascade/contextResolver.py:94)
и runtimeChain. Контекст сохраняет snapshots и provenance. Authored None
остаётся наследованием до resolve. False и 0 являются значениями,
а не отсутствием: движок уже проверяет value is not None.

Нельзя молча выдать LocationContext за готовый водный контекст:
[LocationContext](../../backend/app/dataModel/locations/context/locationContext.py:29)
использует ScopeLevel и содержит локационные параметры; root сохраняет
зависимости, но ничего не вычисляет. Нужна проверяемая адаптация общего
контракта контекста под другую ось без копирования resolver.

Целевая ось: WaterGenerationScope на существующем ScopeAxis, путь
ROOT → WORLD → CATEGORY → WATER_BODY. ROOT — технический пустой узел, WORLD —
настоящий вычисляемый канал настроек мира. Это позволяет сохранить
семантику пустого root и выполнять extend сначала для мира, затем
независимо для каждой категории и тела от соответствующего parent context. Соседние водоёмы
не наследуют overrides друг друга. Три декларации Cascade:
WATER_FRACTION, WATER_AUTORESOLVE и WATER_STRATEGY — VALUE,
без RNG/materialize/fold. Default стратегии согласован: continental_noise.
Каждое field-specific graph объявляет свои каналы и явные пустые scopes;
добавление CATEGORY не создаёт второй цикл резолва вне общего extend.

## 4. Явные поля настроек и их семантика

### 4.1 Мир

Использовать существующий отдельный объект настроек `world.hydrology`
(WorldHydrology, одна JSON-колонка worlds.hydrology). Расширить его полем
`generation: WorldWaterGenerationSettings` с model default factory;
общая базовая схема — WaterGenerationSettings (§5.2-A).

- `water_fraction: float | None = None`, конечное число в [0, 1], bool
  недопустим. Wire: `world.hydrology.generation.water_fraction`;
  0.60 означает 60%.
- `autoresolve: StrictBool | None = None`.
  Wire: `world.hydrology.generation.autoresolve`.
- `strategy: DesignedWaterStrategyKind | None = None`, закрытый enum;
  wire: `world.hydrology.generation.strategy`. Все способы поддержаны,
  в том числе plate+noise как явная композиция через общую абстракцию.

Все authored-поля — каналы WORLD с DefaultWhenMissing, сохраняющие None.
Объект уже существует: dataModel/hydrology/worldHydrology.py;
db/models/world.py:101; typed accessor worldRow.hydrology(world):145.
Не добавлять копии в WorldTerrainScalars, верхнеуровневые world scalars
или SQL-колонки. Импорт/export/patch
используют текущую JSON-колонку и общий POJO resolve. Общий settings facade
мира ссылается на этот объект, не сериализует вторую копию.

### 4.2 Отдельный водоём

Общая базовая схема `WaterGenerationSettings`, body-подтип
`BodyWaterGenerationSettings` с собственными cascade channels:

- `water_fraction: float | None = None`, тот же тип/диапазон;
- `autoresolve: StrictBool | None = None`.
- `strategy: DesignedWaterStrategyKind | None = None`, как на мире.

У существующих DeclaredBasin, DeclaredCoastline и DeclaredLake — поле
`generation: BodyWaterGenerationSettings` с model default factory.
Wire, например:
`world.hydrology.declared_basins[].generation.water_fraction` и
`world.hydrology.declared_basins[].generation.autoresolve`.
Те же пути generation используются у coastline и lake. Это единая модель
параметров, а не три реализации наследования. Для procedural body тот же
POJO передаётся как источник WATER_BODY на границе caller. Декларация
полей/validation общая для world/body; authored значения разных уровней
не являются дублированием SoT. Composed source binding в G1/G2 должен
сохранять разные scope tags и не использовать nested FieldRef selector:
FieldRef выбирает только непосредственное поле. Не копировать значения
в дополнительный persisted settings object ради привязки каскада.

Настройки принадлежат source/intent, не resolved WaterBody: последний
описывает физическое тело после fill/merge и не должен менять входы bake.
Существующие required footprint/floor у DeclaredBasin не делают его
готовым носителем всех auto-режимов: необходимый input-контракт для
частично заданного procedural body уточняется до шага типов.

### 4.3 Разрешение

Порядок: поле body → поле категории (для объявленных category channels)
→ поле мира → terminal default POJO. Отсутствующее звено объявляется
явно и передаёт наследование, не устраняется из графа произвольным if.
Для доли воды terminal источник — отдельное поле defaults POJO со
значением **0.60**, доступное через CascadeDefault/FieldRef. Не помещать
0.60 как authored default на каждом звене: это оборвёт наследование.

- world=0.75, body=None → 0.75;
- world=0.75, body=0.30 → 0.30;
- world=None, body=None → 0.60;
- world=0, body=None → 0;
- world autoresolve=True, body=False → False;
- world autoresolve=False, body=True → True;
- body autoresolve=None → значение мира.

Для отсутствующего autoresolve согласован terminal **False**, чтобы
генерация включалась явным True. Authored None проходит весь каскад;
False читается из terminal defaults POJO, не подставляется раньше
в каждую исходную модель.
Patch missing не меняет поле, patch null возвращает наследование.
Потребители получают resolved context с provenance, не читают world/body
параллельно и не используют `body_value or world_value or default`.

Существующие category flags hydrology не становятся вторым каскадом.
Контракт Q-AUTO-GATES согласован в §6.8: existing category значения
подаются как typed каналы того же каскада. False body сохраняется как
override world/category True; явный body True перебивает унаследованный
autoresolve False. Root enabled=False остаётся абсолютным отключением.

## 5. Целевая архитектура и data flow

Единая абстракция `DesignedWaterStrategy`: typed input с seed, topology,
полным pre-hydrology snapshot, ready anchors и resolved generation context;
output — конечный набор prepared candidates и metadata для basin factory,
плюс явные failures на внешней preparation boundary. Внутри стратегии
возвращают WaterDesignDraft; подготовка PreparedPlacement выполняется
один раз общим preparer, а не отдельно в каждом алгоритме (§5.2).

Четыре реализации: AuthoredRegionStrategy, ContinentalNoiseStrategy,
PlateStrategy, PlateNoiseStrategy (композиция двух field producers).
Закрытый strategy kind — новый enum только после
инвентаризации; настройки стратегий — typed POJO, defaults в dataModel.
Абстракция должна принимать существующие формы/identity/placement types,
а не создавать альтернативные Intent, Candidate или resolver.

Последовательность:

1. Собрать полный world snapshot и topological domain; resolve WORLD,
   CATEGORY и затем body contexts через общий cascade engine.
2. Общий admission spec разрешает запреты и priority до дорогого design.
   Disabled admission inputs сохраняются без подготовки геометрии;
   конечный DisabledPlacement выпускает общий P2. Для допущенных
   inputs стратегии строят drafts/профили, общий preparer — candidates,
   не меняя z. Ожидаемые supports обслуживает существующая общая очередь.
   Authored geometry проецируется fine→coarse на существующей границе.
3. Собрать общий конкурирующий universe готовых объектов snapshot.
   Один resolve_placements на границе готовности; не resolve по стратегии.
4. Только accepted placements → existing ResolvedWaterPlacement →
   BasinSpec через расширенный mapper, без второй физики.
5. Terrain relief применяет абсолютное дно до hydrology. Если требуется
   пространственно меняющийся профиль continental/plate, сначала
   расширить существующий spec/writer: текущий BasinSpec имеет scalar
   floor_z и сам по себе не обещает перенос произвольного поля.
6. HY-12 выполняет уровни/merge/fill/classify/shore. Уровень на тело;
   strict z < z_water_level. Natural-only путь остаётся classify-only.

Эта последовательность описывает вычисление/обновление планировки и её
derived terrain/water facts. In-memory field/fill calculations не означают
обязательную материализацию pack/cells. Отдельный запрос L0/L2 consume
актуальную планировку по §6.20; materializer не выполняет новый placement.

Не читать post-carve предыдущего bake. Поле должно воспроизводиться из
seed, входных параметров и pre-hydrology snapshot. Full/partial фильтруют
только выход, не candidates. На wrapped/sphere край bbox не создаёт океан.
Место сохранения coarse_relief_z и доставки новых высот в L0/L2 нужно
проверить явно: текущий snapshot снимается до применения basinZ.

### 5.1 Согласованный выбор стратегий

Единственный enum `DesignedWaterStrategyKind` в
`dataModel/terrain/designedWater/strategyKind.py`:
`authored_region | continental_noise | plate | plate_noise`.
Все четыре варианта поддерживаются целевой архитектурой; это не фазы,
в которых остальные варианты объявляются ненужными.

Согласованный terminal strategy default — **continental_noise**.
Он применяется только после каскада, при effective autoresolve=True
и effective placement priority>0. Выбор стратегии сам по себе не включает
autoresolve и не меняет общего запрета создания при priority=0.
Не переключать алгоритм автоматически при ошибке выбранного способа:
невалидный plate input → явный unresolved, не скрытая генерация noise.

- authored_region: точная authored геометрия/дно, без procedural
  изменения этих явно заданных параметров ради процента воды. При
  autoresolve=False явные declarations обрабатываются существующим
  declared pipeline, без создания procedural кандидатов. Отсутствие
  authored геометрии при выбранном authored_region не заменяется noise.
- continental_noise: низкочастотное поле пригодности под воду внутри
  области terrain-domain; масштаб задаётся в world-fine XY cells,
  а не в числе текущих samples. Выбор порога доли воды делает общий
  preparer, не сам field generator.
- plate: plate layout формирует крупную continental/oceanic структуру
  и профиль-контекст. В GEO-1 не создаёт/не перестраивает горные объекты:
  геологическая связь с mountain generation — отдельный явный контракт.
- plate_noise: сначала plate field, затем ограниченная детализация noise,
  потом один общий water-fraction threshold/preparation. Не объединять
  две независимо вырезанные карты воды и не выполнять два placement pass.

Согласованный принцип композиции: signed continental field в [-1,1];
G4-C единожды преобразует его в quantized wet score по §6.29-F,
большее значение score предпочитает воду. Plate — базовая структура; noise —
нуле-средняя детализация с ограниченной амплитудой из typed POJO.
Точная нормализация/формула/амплитуда закреплены §6.29-F
(clamp(P + detail_weight*N,-1,1), defaults в owning POJO); недопустимо
складывать неизвестные elevation/score единицы напрямую. Нулевой detail
должен давать ровно plate, без смены seed/порога по дополнительному проходу.
Authored constraints применяются одинаково ко всем procedural вариантам
общим constraint adapter до placement. Никаких своих spatial priorities.

Внешний источник про разделение формы,
noise и elevation: [Red Blob Games, Making maps with noise functions](https://www.redblobgames.com/maps/terrain-from-noise/).
Он не является спецификацией нашего plate algorithm, топологии sphere
или общих placement-правил. В частности, ocean-at-bbox-edge shaping
из примеров не переносится в wrapped/sphere мир.

### 5.2 Классы политик и методов: обязательные границы

Все новые типы/файлы этого раздела — проектируемые, не уже существующий
API. Перед кодом G0 фиксирует их контракт в ТЗ. Нельзя объединить эти
ответственности в WaterPolicyService с одним большим resolve().

**A. Authored settings и terminal defaults — dataModel/hydrology.**
`WaterGenerationSettings` в `dataModel/hydrology/generation/waterGenerationSettings.py` — общая базовая
схема параметров/validation. `WorldWaterGenerationSettings` и
`BodyWaterGenerationSettings` — scope-specific подтипы той же схемы,
объявляющие CascadeChannel/CascadeLink на непосредственных полях.
Это два существующих authored уровня, не копии данных в отдельных
хранилищах. WorldHydrology.generation использует world-подтип;
DeclaredBasin/Coastline/Lake.generation — body-подтип. Не делать
nested FieldRef по generation.strategy. Ссылки выбирают непосредственное
поле strategy соответствующего settings POJO. Caller передаёт сам
embedded POJO в общий Link(WORLD/BODY, settings), без проекции значений
в дублирующий DTO. Связи world/body объявлены через typed FieldRef
между scope-specific полями; базовые ограничения/default None общие.

`WaterGenerationDefaults` в `dataModel/hydrology/generation/waterGenerationDefaults.py` — terminal
источник: water_fraction=0.60, autoresolve=False, strategy по решению
§5.1. `canonical_defaults()` возвращает POJO, не dict в генераторе.
Ни settings, ни defaults не вызывают generators/placement и не пишут z.
WorldHydrology не дублирует поля generation в собственных scalars.

Алгоритмические policy POJO — отдельные классы по смыслу:
`ContinentalNoisePolicy`, `PlateGenerationPolicy`, `FieldCompositionPolicy`.
Это validation/настройки, не вычислительные сервисы. Их leaf-параметры
также наследуются через объявленный cascade; nullable nested policy
не разрешает заменить per-field наследование правилом «весь dict ребёнка
побеждает». Typed world/body source подтипы и общий extend используются
для этих leaf-параметров тем же способом. Числовые defaults алгоритмов
определить в G0, не изобретать их в StrategyFactory.

**B. Каскад — существующий общий engine наследования.**
`WaterGenerationContext` (`dataModel/hydrology/generation/generationContext.py`) —
resolved-поля и provenance, transient frozen context на водной оси.
`WaterGenerationContext.root(...)` только инициализирует ROOT.
Существующий `application/cascade/contextResolver.extend(ctx, Link(...))`
обрабатывает WORLD, CATEGORY, затем BODY. Никакого resolve_water_fraction(),
resolve_water_strategy() или водного fallback engine.
Factory/strategies принимают этот context, а не world+body dictionaries.
Общий cascade verifier проверяет обе scope-specific модели до runtime.
Поведение разрешает отдельный application/policy/PolicyResolver (§6.8).
Cascade не исполняет admission, а PolicyResolver не повторяет наследование.

**C. Размер области — terrain, не water policy.**
`terrain/regions/regionExtent.py::prepare_terrain_regions(...)`
возвращает TerrainRegionPlan(snapshot, coverages) по §6.3 и согласованному
G3-R supplement. Этот provider не выбирает
стратегию и не определяет placement specificity. Водный preparer читает
generation_area_fine2 из результата, без своего shape.area()/bbox fallback.

**D. Бюджет покрытия — одна pure policy для всех стратегий.**
`terrain/designedWater/coverage/waterCoverageBudgetPolicy.py::WaterCoverageBudgetPolicy`
с единственным public методом `calculate(world_extent: TerrainRegionExtent,
world_context: ResolvedWaterGenerationContext, body_requests: tuple[BodyCoverageRequest,...],
*, authored_union_fine2: int, available_auto_area_fine2: int) -> WaterCoverageBudget`.
Frozen result type `WaterCoverageBudget` объявляется в
dataModel/terrain/designedWater/coverage/budget.py (шаг G4):
WaterDesignInput ссылается на него, а dataModel не импортирует
application policy.
Он определяет целевую площадь, учтённую authored площадь, остаток для
procedural generation и превышение authored над целью. Площадь union
передаётся геометрическим владельцем, policy не считает bbox/shape.
Authored coverage не режется при превышении цели, residual не отрицателен.
Policy не выбирает winner, не резервирует клетки, не делает fill.
WaterCoverageBudgetPolicy выполняет pure расчёт бюджета, не исполняет
rules. Условный выбор поведения
задаётся декларацией и общим PolicyResolver; calculate использует готовые
параметры и выполняет только арифметику по единому контракту GAP-AREA.
До общего placement это целевой budget по supplied declarations,
не заявление об их будущем принятии. Фактическая статистика — после fill.

**E. Общее protocol стратегий — terrain/designedWater.**
`strategies/strategy.py::DesignedWaterStrategy.design(input: WaterDesignInput)
-> WaterDesignDraft`.
WaterDesignInput содержит source intent/identity, resolved context,
terrain region extent, budget, topology/coordinate scale, seed,
pre-hydrology snapshot и approved authored constraints. Объект immutable;
исходные высоты не предоставлять алгоритмам как mutable write target.
WaterDesignDraft — typed union authored geometry / generated wetness field
с profile metadata/failures; существующие RegionShape/Coord/PlacementIntent
переиспользуются. Никаких dict[str, Any] для profile metadata.
Wetness field хранится на coarse working grid в canonical координатах,
а не как полный fine-cell мир. Профиль дна и wetness score различаются.

Конкретные классы, по одному файлу:
- `strategies/authoredRegionStrategy.py::AuthoredRegionStrategy.design(input)` —
  сохраняет переданную authored geometry и явные floor/level constraints.
- `strategies/procedural/continentalNoiseStrategy.py::ContinentalNoiseStrategy.design(input)` —
  вызывает NoiseFieldGenerator.build(input), возвращает field draft.
- `strategies/procedural/plateStrategy.py::PlateStrategy.design(input)` — вызывает
  PlateFieldGenerator.build(input), возвращает field draft.
- `strategies/procedural/plateNoiseStrategy.py::PlateNoiseStrategy.design(input)` — вызывает
  два field generator и ContinentalFieldComposer.combine(...); не вызывает
  повторно другие strategies/placement, не пишет рельеф.

**F. Field generators и композиция — чистые вычисления.**
`fields/noiseFieldGenerator.py::NoiseFieldGenerator.build(input) -> ContinentalField`.
`fields/plateFieldGenerator.py::PlateFieldGenerator.build(input) -> ContinentalField`.
`fields/continentalFieldComposer.py::ContinentalFieldComposer.combine(plate, noise,
composition_policy) -> ContinentalField`.
Они не читают мировые defaults, не резолвят наследование, не выбирают
конкретный final water percentage и не знают общих priority outcomes.
Случайные каналы стабильны по seed/identity; не используют порядок calls.

**G. Dispatch — без policy semantics.**
`strategies/strategyFactory.py::DesignedWaterStrategyFactory.get(kind)
-> DesignedWaterStrategy` — единственная enum→implementation таблица.
Четыре implementation передаются обязательными именованными constructor
arguments authored_region/continental_noise/plate/plate_noise по G4 supplement.
Она не резолвит settings, не выбирает алгоритм по размеру bake tile,
не хранит дубли defaults. Unknown kind — typed error, без noise fallback.

**H. Подготовка candidates — одна для всех стратегий.**
`preparation/placementPreparation.py::DesignedWaterPlacementPreparer.prepare(input,
draft, *, selection_policy) -> WaterDesignPreparation` — общий region/constraint
boundary: allocated budget→prefix geometry, metadata/ref и floor/profile.
Это immutable geometry result до admission binding, не water adapter transport.
Единственный WaterPlacementPreparation переводится вместе с callers в G8.
Authored geometry сохраняет native world space без rasterize;
для field draft выбирает порог один раз с deterministic ties.
На выходе PlacementCandidate; PreparedPlacement с готовым decision собирает G8.
Общий admission decision до design обязателен (§6.8-C/C3); DISABLED
не передаётся в design/preparer. Домен не реализует свою проверку нуля.
P2 потребляет authoritative decision и обеспечивает non-creation,
не вычисляя повторно смысл priority по domain settings.

**I. Оркестрация и materialize — разные границы.**
`preparation/designPreparation.py::prepare_designed_water(sources, ...) -> preparation`
получает source entries и typed зависимости caller, не готовые
WaterDesignInput с ещё не рассчитанным budget. Выполняет порядок
context → общий admission → для допущенных inputs
extent/budget → factory/design → common preparer; собирает candidates/
metadata/failures и disabled admission inputs. Не вызывает
resolve_placements по одному body или strategy.
WaterDesignInput создаётся только после получения extent и budget;
передавать его как вход этапу, вычисляющему эти же поля, запрещено.
Exact source union и keyword dependencies закрываются GAP-SOURCE/
GAP-SNAPSHOT/GAP-AREA до G4/G8; контрактные стыки — §6.16.
После PC-9 caller общего batch pass —
`application/worldData/planning/composition/surfacePlanningAssembler.py::
SurfacePlanningAssembler.prepare`; `prepare_surface_terrain_context`
остаётся совместимым делегирующим входом. `application/policy/PolicyResolver`
разрешает priority/admission;
`application/worldData/placement/resolver.py::resolve_placements`
исполняет dependency scheduling/ordering/collisions (§6.5), не второй
priority resolver.
Existing `hydrology/basinSpecFactory.basin_specs(...)` строит specs
только из принятых результатов и typed metadata. Existing
`terrain/reliefObjects/bathymetry/basinZ.apply_basin_z(...)` — writer дна.
HY-12 waterBodyAssembler — fill/classify/shore facts; river planning
не включается в эти стратегии.

**J. Фактическое покрытие и береговое покрытие — отдельные consumers.**
`coverage/coverageReport.py::build_water_coverage_report(final_water, regions,
*, budgets)`
считает final union area в тех же единицах, сравнивает target/actual,
не меняет placement или рельеф ради процента. Источник размеров — terrain.
budgets — обязательное typed сопоставление generation region UID →
WaterCoverageBudget того же запуска; target не читается повторно из world.
`terrain/relief/surfaceCoatingSupport.py::surface_coating_support(...)`
из §6.1 предоставляет факты пригодности покрытия, не generation strategy и
не hydrology priority policy. Не объединять его с WaterCoverageBudgetPolicy:
это разные значения слова «покрытие» и разные фазы pipeline.
Решение allow/forbid/unknown принимает общий PolicyResolver по terrain
definition из dataModel/terrain/relief/surfaceCoating/surfaceCoatingPolicyDefinition.py.

**Порядок зависимостей:** shared policy contracts/engine + общая cascade
axis → dataModel settings/types → resolved context/admission →
terrain region extent → budget → field generators/strategy draft →
common placement preparation → общий P2 → existing basin spec/writer →
HY-12 → coverage report/surface composition. Нет обратной зависимости
placement от hydrology facade или extent provider от final SurfaceTerrainContext.

### 5.3 Coastline: два поведения, два pipeline, без циклической опоры

**Причина уточнения контракта.** Существующий
[DeclaredCoastline](../../backend/app/dataModel/hydrology/declaredCoastline.py:15)
уже описан как water-body intent from open line/closed ring. Его kind,
liquid и path определяют вход будущего бассейна. Если обязать этот source
зависеть от уже созданного водоёма, получается цикл и теряется генерация
моря/океана по линии. Предыдущий универсальный запрет «coastline без воды»
был недостаточно точен: обязательную опору имеет dependent boundary,
а не исходное указание создать тело. Новая source схема ниже — изменение
ТЗ, не утверждение, что код уже различает режимы.

**Wire/POJO discriminant.** Расширить DeclaredCoastline:
- `purpose: CoastlinePurpose` — закрытый enum в existing dataModel/hydrology/declaredCoastline.py,
  `water_source | body_boundary`; это не PlacementMode absolute/semantic.
- `target_source_uid: EntityUid | None` — existing strict opaque UID для source identity
  водоёма для body_boundary, не spatial lookup по ближайшей воде.
DefaultEnumWhenMissing для purpose — water_source, поскольку нынешняя модель
обозначает именно источник body intent. body_boundary требует явный target;
water_source не принимает target. Обе комбинации валидируются POJO.
Общий linked body runtime fact переводит target_source_uid в принятые
placement и итоговое физическое тело после merge; source UID и physical
water_body_uid не смешиваются. Нормализация не копирует геометрию линии
в два независимо редактируемых persisted источника.

**A. Water-source линия: создание водоёма по линии.**
Владелец генерации — terrain-side designed water preparation.
Класс `CoastlineWaterSourceAdapter` в
`terrain/designedWater/preparation/coastlineWaterSourceAdapter.py`, public метод
`prepare_source(source: DeclaredCoastline, *, context: WaterGenerationContext,
region: TerrainRegionExtent, budget: BodyCoverageAllocation, topology,
coordinate_space, cell_span_fine, seed_root, snapshot, admission)
-> WaterDesignInput | WaterPreparationFailure`.
Все перечисленные keyword dependencies обязательны; topology использует
WorldTopology, coordinate_space — существующий enum, масштаб — строгое
положительное число fine cells на рабочую клетку. Snapshot/revision и
admission payload types замораживаются G0-S/GAP-POLICY; до этого signature
определена source union/metadata контрактами §6.29-B; Any/raw dict запрещены.
Adapter допускает только purpose=water_source. Он преобразует path,
closed/water_side в authored constraints будущего моря/океана, сохраняет
kind/liquid/source identity и принимает уже resolved generation context
общего каскада. Он не вызывает свой resolver и не рассчитывает бюджет.
Линия здесь — вход, не второй placement-объект с той же identity.
Водоём не имеет dependency на самого себя или на ещё не созданную воду.

Pipeline A: source line → context/terrain region/budget → выбранная
DesignedWaterStrategy → draft → общий preparer → **body PlacementIntent**
в общем pre_relief batch → generic priority/dependency/constraint checks
→ accepted ResolvedWaterPlacement → BasinSpec → relief writer → HY-12.
Для отсутствующей геометрии тела procedural autoresolve требует effective
autoresolve=True. Полностью заданные authored inputs продолжают declared
ветку по agreed declaration contract; False не удаляет authored объекты.
Не создавать поле воды/полный basin из неполной линии в обход False.

У body кандидата свой normal authored/approved-auto placement priority.
Если он 0, общий P2 не создаёт тело. Если None — unresolved. Adapter не
подставляет 1 и не повышает authored 0, чтобы «починить» shoreline.
Отсутствие **будущей** воды само по себе не делает body source dependent
boundary и не понижает его priority до 0. CoastlinePlacementFact о наличии
опоры не применяется к этому body кандидату: это другой тип входа.
Не записывать фиктивный WaterPresence.PRESENT до fill.

Authored path является constraint requested water/land boundary, а не
обещанием переместить горы. Terrain-owned constraints/reserved mountains
имеют силу. Если линия несовместима с защищённой горой и нет разрешённой
альтернативы — явный unresolved/constraint diagnostic; самовольный carve
сквозь гору или сдвиг absolute линии запрещены.

**B. Body-boundary линия: зависимый объект существующего результата.**
Класс `AttachedCoastlinePreparer` в
`application/worldData/placement/adapters/coastline/attachedCoastline.py`, метод
`prepare_boundary(source: DeclaredCoastline, accepted_water, context)
-> PreparedPlacement | WaterPreparationFailure`.
Он допускает только purpose=body_boundary. Обязательная опора —
target_source_uid: принятый placement и соответствующее физическое
водное тело в supplied snapshot. Его собственный будущий fill не опора.
Boundary не создаёт BasinSpec, не расширяет воду и не пишет surface_z.

Pipeline B: accepted body → fill/final body facts → boundary preparation
→ общий resolver в phase=dependent с immutable accepted опорами →
boundary materialize/output. Если тело из pipeline A получено тем же bake,
boundary обрабатывается только после его реального результата, а не
предполагаемого успеха. Если target missing/unresolved/не имеет воды,
boundary не создаётся; независимые объекты продолжают обрабатываться.

Dependency — существующий PlacementDependency, связь/допустимый overlap
— существующие типы P1/P2, без своего coast resolver. Заданный absolute
path не сдвигается молча к фактической воде. Derived boundary без
authored path и её extraction, если нужны, — отдельный input контракт,
не неявная подмена DeclaredCoastline.path.

**C. Общая policy и dry-water fact.**
Общее правило priority=0 → no creation действует в обоих pipeline.
CoastlinePlacementFact/понижение effective priority=0 при отсутствии
водной опоры относится к boundary purpose. Для water_source проверяется
validity requested geometry и ordinary body priority, не наличие воды,
которую этот объект только должен создать. Источник является body intent,
а не исключением из zero policy. Effective priority вычисляет общий
PolicyResolver; placement модель хранит решение, adapters его не вычисляют.

**D. Разделение callers, metadata и identity.**
`designPreparation.prepare_designed_water` принимает только body sources,
включая coastline water_source. Body-boundary entries маршрутизируются
в отдельный dependent caller после HY-12; не попадают в water source
merge (basin>coastline>lake) и basinSpecFactory. Runtime merge source UID
остаётся контрактом body sources, не способом слить boundary с телом.
Общий dispatch по purpose выполняется один раз на входе, не в каждом
field generator. Ни один класс не имеет метода «создать берег, а если
тела нет — создать море»; fallback между pipeline A/B запрещён.

**E. Проверки поведения.**
1. Нет воды, water_source + auto=True + positive priority → body candidate
   допустим, accepted result создаёт море/океан через relief/HY-12.
2. Та же source линия при priority=0 → ни тела, ни carve, ни roles.
3. Та же неполная source линия при auto=False → procedural body не
   синтезируется; явная диагностика недостающих geometry inputs.
4. body_boundary с missing/dry/unresolved target → no boundary и no basin.
5. body_boundary с принятым мокрым target → dependent resolve, no z-write.
6. Береговая линия у protected mountain → гора/grade/topology сохраняются,
   несовместимые constraints не скрываются success пустого footprint.
7. Перестановка inputs, full/partial, preview/runtime дают те же решения;
   нет двойного body UID или двойного carve от source и boundary.

### 5.4 Единая карта модулей и контроль архитектуры

Все пути этого раздела относительно `E:/AI Project/backend/app/`.
Это target расположение, не утверждение о существовании новых файлов.
Сокращённые пути §5.2/§6/§7 разрешаются только по этой карте:
`terrain/...` → `application/worldData/generators/terrain/...`,
`hydrology/...` → `application/worldData/generators/hydrology/...`,
`climate/...` → `application/worldData/generators/climate/...`,
`placement/...` → `application/worldData/placement/...`,
кроме явно указанного префикса `dataModel/`. Общий engine всегда
`application/policy/`, правило сокращения на него не распространяется.
Общие planning/cache модули PC-блока (dataModel/planning, dataModel/cache,
application/planning, application/cache и domain providers) размещаются
по собственному дереву §6.21 — эта карта их не переопределяет.

**Контракты/декларации — dataModel:**
- Правило композиции проверено по текущим папкам: hydrology — 20 файлов,
  hydrology/enums — 10, terrain/relief — 23. Новые flat files туда не
  добавляются. Generation settings/context/defaults размещаются в
  hydrology/generation/ (5 файлов с init, включая legacySettings), planning enums — в
  hydrology/enums/planning/ (до 5 с init), coating facts/definition —
  terrain/relief/surfaceCoating/ (3 с init). Existing source POJO в root
  редактируются, но не создаются их копии. Старые target пути выше лимита
  отменены; эта композиция не требует массовой реорганизации старых файлов.
- `spatial/grid/{gridBBox,coordinateSpace,coordinateTypes}.py`:
  единственные GridBBox/CoordinateSpace/shared coordinate records и
  scalar aliases после PC-0G1/PC-0G2. Существующие определения переносятся,
  не дублируются; topology/WorldBounds сохраняют свой отдельный контракт.
- `climate/planning/climatePlan.py::ClimatePlan`,
  `terrain/planning/terrainPlan.py::TerrainPlan`,
  `terrain/relief/planning/reliefPlan.py::ReliefPlan`,
  `hydrology/planning/hydrologyPlan.py::HydrologyPlan`:
  immutable domain payloads PC-1C/T/R/H; PlanEnvelope[T] не содержит live
  World/application result. Output fields — §6.26; input freeze — §6.27.
- `terrain/planning/waterPlacementPlan.py::WaterPlacementPlan`:
  baseline placement records/specs/topology, producer terrain-side PC-6W.
- `planning/contracts/planContract.py`,
  `planning/diagnostics/planDiagnostic.py`,
  `planning/policy/planningExecutionPolicy.py`:
  metadata registry, immutable diagnostics и planning resource policy §6.25.
- `surfacePlanning/surfacePlanSlot.py::SurfacePlanSlot` — domain StrEnum
  vocabulary surface pipeline (§6.33); owner — междоменное surface planning,
  слой dataModel. Providers/composition используют его declarations;
  общий planning/cache engine не импортирует surfacePlanning.
- `encoding/schemaManifest.py`: `CanonicalSchemaManifest` и
  `RegisteredTypeEntry` — декларации type ids общего canonical codec
  (§6.32), без encode/decode логики.
- `validation/diagnostics/fieldPathError.py`: единственное pure определение
  existing issue/context/reason types, old application путь — re-export.
- `climate/planning/climatePoints.py`: перенесённые existing point/sample
  types и AnchorSource, без дубликатов в application.
- `terrain/relief/bathymetry/basinSpec.py::BasinSpec`: перенесённый existing
  pure contract PC-1R; application старый путь — re-export, единственный
  writer остаётся в application. Spatial profile расширение только G9.
- `policy/{policySpec,policyFacts,policyReferences,policyRules,policyEnums,
  policyDecision,objectAdmissionPolicyDefinition}.py`:
  общие rules, effects, decisions, admission definition (§6.8).
- `cascade/runtimeContext.py::CascadeRuntimeContext[AxisT]` — общий transient
  BaseModel runtime-контракт G1, без water/location параметров; конкретные
  LocationContext/WaterGenerationContext сохраняют свои оси и поля (§6.16-A).
- `hydrology/generation/{waterGenerationSettings,waterGenerationDefaults,generationContext}.py`:
  base/world/body settings, terminal defaults, resolved context (§5.2-A/B).
  Scope-specific settings размещаются в generation/waterGenerationSettings.py,
  не в application и не как копии JSON settings.
- `hydrology/enums/planning/waterGenerationScope.py`: новая ось WaterGenerationScope;
  `hydrology/enums/planning/hydrologyExecutionMode.py`: доменный generation behavior enum;
  `hydrology/enums/planning/coastlinePurpose.py`: source/boundary enum.
  Existing HydrologyScope уже перенесён PC-1H в enums/planning/hydrologyScope.py;
  эти enum не заменяют друг друга.
- `hydrology/policy/hydrologyPolicyDefinition.py`: доменные declarations;
  `hydrology/policy/hydrologyGenerationDecision.py`: typed specialization
  общего decision. Definitions не содержат исполнения rules.
- `terrain/designedWater/{strategyKind,input,draft}.py`,
  `terrain/designedWater/fields/field.py`,
  `terrain/designedWater/coverage/budget.py`:
  strategy enum, input/draft/field/budget (§5.2-D/E).
- `terrain/designedWater/settings/{continentalNoisePolicy,plateGenerationPolicy,
  fieldCompositionPolicy}.py`: алгоритмические settings POJO, не resolvers.
- `terrain/regions/{terrainRegionExtent,terrainRegionsSnapshot}.py`:
  региональные размеры/snapshot (§6.3).
- `terrain/relief/surfaceCoating/surfaceCoatingFacts.py::SurfaceCoatingFacts`: typed support facts;
  `terrain/relief/surfaceCoating/surfaceCoatingPolicyDefinition.py`: terrain declarations.
- `placement/{prepared,result,batch}.py`: существующие placement contracts
  и расширение конечных outcomes. Exact ранний admission input/outcome
  payload определён §6.29-C/D; не выбирать его повторно в coding step.

Дополнение карты §6.28–6.29: neutral dataModel/identity/uid.py;
validation/enums/resolutionMode.py; planning/contracts/planContract.py;
spatial/grid/gridSettings.py; domain planning/inputs по §6.28;
terrain/planning/inputs/geoWaterPlacementInput.py;
hydrology/planning/inputs/geoHydrologyPlanInput.py;
terrain/regions/{coverageGeometry,regionPlanningInput}.py;
hydrology/sources/{proceduralWaterSource,waterDesignSource,waterSourceMetadata}.py;
hydrology/planning/sourceBodyMapping.py; hydrology/boundaries/attachedCoastline.py;
terrain/relief/bathymetry/floorProfile.py;
terrain/relief/surfaceCoating/surfaceSupportInput.py;
materials/enums/materialSubstrateKind.py. Classes/fields/roles и
producers/consumers каждого файла указаны в соответствующих §6.28/6.29.
Один файл может содержать связанные records/enums одного контракта;
никакой общий механизм не помещается в hydrology/terrain.

**Исполнение — application:**
- `policy/policyResolver.py`: единственный общий rule executor.
- `encoding/canonicalCodec.py`: единственный generic TLV v1 encoder
  §6.32 (не сабдомен planning); `planning/service/planFingerprints.py`:
  единственная реализация fingerprint формул §6.31-A.
- `cascade/`: существующее наследование и общий context runtime;
  `jsonValidation/`: существующие POJO resolve/validation/reporting.
- `worldData/generators/hydrology/policy/hydrologyPolicyFacts.py`:
  сбор hydrology facts, без rule resolution.
- `worldData/generators/terrain/regions/regionExtent.py`: extent provider.
- `worldData/generators/terrain/designedWater/`: подпакеты strategies
  (включая procedural), fields, preparation и coverage по дереву §5.4-A;
  точные файлы/методы §5.2. Settings/контракты остаются в dataModel.
  Это вычисления/подготовка, не альтернативный policy/placement engine.
- `worldData/placement/{resolver,dependencies,constraints,diagnostics}.py`:
  существующий placement; `adapters/coastline/attachedCoastline.py`: boundary adapter.
- `worldData/generators/terrain/relief/surfaceCoatingSupport.py`:
  факты поверхности. Здесь нет surfaceCoatingPolicyDefinition: definition
  размещается только в указанном выше dataModel namespace.
- `worldData/planning/composition/surfacePlanningEntry.py::SurfacePlanningEntry`:
  existing request boundary после PC-11.7: capture_view → prepare_captured,
  связывает domain working views; old surfaceTerrainContext/to_legacy_context
  удалены, в GEO-1 не восстанавливаются.
- `worldData/planning/composition/surfacePlanningAssembler.py::
  SurfacePlanningAssembler.prepare`: единственный world surface
  cross-domain assembler, получает domain plans через PlanningService.
- `worldData/planning/composition/planProviders.py::register_world_plan_providers`:
  composition-root bindings climate/terrain/relief/hydrology providers;
  generic PlanningService не импортирует их implementations.
- `worldData/planning/composition/surfacePlanningCapture.py::
  SurfacePlanningCapture`: typed capture baseline/GEO planning inputs из
  authoritative state view по §6.28/§6.29-M; не перечитывает БД на consumer.
- `worldData/planning/contracts/surfacePlanBundle.py::SurfacePlanBundle`:
  immutable aggregate typed plan refs/envelopes; exact поля — §6.25.
- `worldData/planning/contracts/{surfacePlanningView,surfaceWorkingMaps}.py`:
  existing frozen SurfacePlanningView и request-local SurfaceWorkingMaps.
  GeoSurfacePlanningView/GeoSurfacePlanBundle имеют собственные typed поля
  §6.29-M/§6.31-E, без legacy projection/cast.
- `worldData/generators/hydrology/placement/waterPlacementPass.py`:
  existing transitional caller и общий batch invocation; routing preparation
  переносится в designPreparation на G8, не появляются два активных пути.
- `worldData/generators/hydrology/basinSpecFactory.py` и
  `worldData/generators/terrain/reliefObjects/bathymetry/{basinSpec,
  floorProfile,basinZ}.py`: existing mapping/spec/profile/единственный writer.
  После PC-1R application basinSpec.py — re-export общего domain contract;
  перенос выполнен PC-1R. Расширение профиля — GAP-FIELD/G9,
  без второго spec/writer.

**A. Композиция designedWater по ответственностям.**
Ниже target дерево. В каждой указанной Python-папке предусмотрен один
`__init__.py`; он включён в подсчёт. Новые папки/код в этом заходе не
создаются. Сокращённые strategies/fields/preparation/coverage пути §5.2
относятся к application terrain/designedWater; dataModel указан явно.

```text
dataModel/terrain/designedWater/             # 4 файла с __init__.py
├── strategyKind.py
├── input.py
├── draft.py
├── settings/                               # 4 файла с __init__.py
│   ├── continentalNoisePolicy.py
│   ├── plateGenerationPolicy.py
│   └── fieldCompositionPolicy.py
├── fields/                                 # 2 файла с __init__.py
│   └── field.py
└── coverage/                               # 2 файла с __init__.py
    └── budget.py

application/worldData/generators/terrain/designedWater/  # только __init__.py
├── strategies/                             # 4 файла с __init__.py
│   ├── strategy.py                         # общий protocol
│   ├── strategyFactory.py                  # enum dispatch
│   ├── authoredRegionStrategy.py           # authored geometry
│   └── procedural/                         # 4 файла с __init__.py
│       ├── continentalNoiseStrategy.py
│       ├── plateStrategy.py
│       └── plateNoiseStrategy.py
├── fields/                                 # 4 файла с __init__.py
│   ├── noiseFieldGenerator.py
│   ├── plateFieldGenerator.py
│   └── continentalFieldComposer.py
├── preparation/                            # 4 файла с __init__.py
│   ├── coastlineWaterSourceAdapter.py
│   ├── placementPreparation.py
│   └── designPreparation.py
└── coverage/                               # 3 файла с __init__.py
    ├── waterCoverageBudgetPolicy.py
    └── coverageReport.py
```

Strategies задают вычислительный pipeline по уже resolved enum;
fields строят/комбинируют поля; preparation адаптирует inputs и готовит
placement candidates; coverage рассчитывает бюджет/отчёт. Декларации
и settings не переносятся из dataModel в application подпакеты.
Направление imports: dataModel не импортирует application; strategy
implementations используют protocol и fields; factory связывает
implementations; preparation использует factory/protocol и contracts;
fields не импортируют preparation/factory. Ни один подпакет не заменяет
application/policy или общий placement. __init__.py не содержит нового
исполнения/глобального состояния и не скрывает cyclic imports.

Максимум в любой новой designedWater папке — 4 непосредственных файла,
включая __init__.py: WARN-порог >5 и предел >10 не превышаются.
При изменении состава модулей пересчитать итоговые количества, обновить
дерево и точные пути соответствующих G-steps до реализации.
Существующие внешние папки проверяются отдельно в G0-A: эта композиция
не означает автоматического выполнения их реорганизации.

**Незавершённые архитектурные стыки — обязательные blockers:**
Ниже неполная выборка архитектурных стыков, не полный перечень blockers.
Полный обязательный реестр всех 12 gaps — §6.13; отсутствие GAP-AREA,
GAP-FIELD, GAP-SURFACE или GAP-PHASE в этой выборке не снимает их
блокирующее действие и не разрешает соответствующие шаги реализации.
call-site migration ledger (§6.8-C3); ранний admission до geometry и
повторная проверка support существующей очередью (GAP-POLICY/OUTCOME);
generic cascade context против текущего LocationContext (GAP-CASCADE);
source union до footprint (GAP-SOURCE); snapshot content revision/cache
(GAP-SNAPSHOT); post-fill boundary caller/result и source→physical body
mapping (GAP-BOUNDARY); validation entry point/лог emission
(GAP-VALIDATION/LOG); activation/removal старых gates (GAP-CUTOVER).
Для каждого до кода требуются exact file/class/method, producer/consumer,
направление импортов, фаза/identity и step. Надпись «existing consumer»
или «по инвентарю» не закрывает этот контракт.

HY-RIV-1 остаётся отдельным треком: application terrain fineSurfaceBase/
sampling и hydrology rivers sourceSearchRegion/fineSourceSearch — §6.10.
Точные dataModel sampling файлы и pack/revision producer/consumer обязан
закрепить R1 до R2; GEO-1 не выбирает эти недостающие contracts по месту.

Архитектурная приёмка каждого G-step: путь по этой карте, один владелец
решения, typed input/output, реальный production consumer, отсутствие
dataModel→application imports/дублирующих gates и явные prerequisites.
Обязательная проверка folder-composition.mdc: максимум 10 непосредственных
файлов в папке, включая __init__.py. Карта §5.4 задаёт доменных владельцев.
При текущем или планируемом количестве более 5 обязателен WARN разработчику
в чат с путём, текущим/итоговым количеством и рекомендацией композиции.
Сам WARN-порог не блокирует работу и не требует подтверждения.
Перед реализацией G0-A обязан проверить текущие и итоговые количества
и зафиксировать композицию переполненных/расширяемых папок. Плоское
размещение designedWater модулей заменено композицией §5.4-A;
точные подпакеты и пути обязательны для G4–G10-R.
До такой проверки/согласования структуры затронутые шаги заблокированы.
Обязательное общее правило составления планов — code-gates.mdc,
гейты 2/3: каждый новый/изменяемый класс соответствует своему домену,
слою и точному пути. Несоответствие, смешанная ответственность либо
неопределённый владелец/папка блокируют выполнение плана до исправления
и согласования архитектурного контракта; coding agent не решает это по месту.
Конкретные инструкции §6.8 определяют semantics; §5.4 — размещение и
границы. Исторический аудит §6.7 не является альтернативным target.

## 6. Связи и открытые вопросы

- HY-BATH-1: использовать действующий bathymetry writer, новые формы дна
  при необходимости — отдельным атомарным шагом, не z-write в strategy.
- HY-9: формы authored coastline и continental layout — разные входы;
  устаревший bbox-spine algorithm нельзя вернуть через GEO-1.
- HY-10: доставка light roles/bands остаётся отдельным треком; GEO-1
  обязан проверить, что его новые высоты доходят до потребителей.
- P3: полный universe конкурентов не равен только water preparation;
  не объявлять миграцию всех adapters выполненной данным планом.
- TOPO-1: все стратегии используют общий topology domain, включая
  noise/plate continuity; локальный wrap и ocean-edge forbidden.
- HY-RIV-1: downstream intent источника + dependency на принимающее
  тело после появления accepted/resolved water facts. Routing и river
  physics остаются существующим consumer; отдельный мини-план определит
  producer источников. Legacy producer до решения не удалять.

### 6.1 Shore: проверенный статус и требование

Q-SHORE закрыт: мастер явно подтвердил этот пункт 2026-10-22.
Сохраняется гидрологическая роль SHORE; на отвесной породе исключается
итоговое shore terrain/material покрытие. Владелец допустимости — домен
поверхности/рельефа, hydrology — потребитель его typed контракта.
Числовые/материальные критерии уточняются в G0/G9-S; unknown policy
согласована в §6.11, решение не возвращается в hydrology.

[derive_shore](../../backend/app/application/worldData/generators/hydrology/water/shoreDerive.py:11)
сейчас ставит hydrology role SHORE сухому 4-соседу воды по final fill,
сохраняя surface_z, body UID и уровень. Проверки материала породы,
отвесности или grade в этом helper нет. Это согласуется с текущим
[ТЗ: высокая сухая клетка тоже shore](../../docs/tz_terrain_hydrology.md:128).
Следовательно, собственно derived-role уже реализован, но условие
«нет отвесной породы» нельзя объявлять выполненным на основании этого кода.

Принято мастером: исключение относится к итоговому terrain/material
покрытию, а гидрологическая роль SHORE сохраняется. Исключение
не должно понижать cliff к water level или гарантировать песчаную полосу
у любого тела. Граница с HY-7 (mountain × shore precedence) сохраняется.
Проверить путь L0/L2, не ограничиваться coarse role. Приёмочные случаи:
пологая суша у моря/океана/озера; отвесная порода у тех же тел; island
reserved; SHORE на z==level; неизменность высоты и собственного уровня воды.
Владелец критерия — домен поверхности terrain/relief. Он возвращает
контракт допустимости покрытия по typed relief/material facts;
гидрология только потребитель. Локальные cliff threshold, списки пород
и grade lookup в hydrology запрещены. Итоговый surface composer применяет
решение к terrain и material атомарно: нельзя сохранить cliff terrain,
но всё равно записать sand как shore_material.

Конкретное место потребления:
[columnFillPass.py](../../backend/app/application/worldData/generators/terrain/passes/columnFillPass.py:121)
сейчас вызывает hydro apply_shore_surface и отдельно назначает material.
Helper [shoreProfile.apply_shore_surface](../../backend/app/application/worldData/generators/hydrology/shore/shoreProfile.py:95)
сейчас не получает факт допустимости покрытия. Перенести решение
в terrain-owned composition; hydro helper не должен владеть геометрией.
Использовать существующий ReliefSideKind.SHEER и typed material facts;
SHEER сам по себе ещё не определяет материал породы.

Планируемый provider: `terrain/relief/surfaceCoatingSupport.py`, функция
`surface_coating_support(...)`, возвращающая общий typed
`SurfaceCoatingFacts` в `dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py`
с typed наблюдениями и явной неизвестностью. Provider возвращает факты,
не конечное policy-решение; allow/forbid/unknown выдаёт общий
PolicyResolver по terrain definition. Exact facts
и typed decision payload закрываются в GAP-SURFACE.
Его вход — существующие typed surface/grade/material/face facts;
точную схему закрепить в G0, unknown policy — §6.11. Не запускать дорогой mill
ради покрытия; отсутствие system_grade_uid не означает отсутствие cliff.
Добавить отдельный G9-S, не реализовывать внутри continental strategy.

### 6.2 Реки: отдельная policy и единицы расстояния

Отдельный world wire уже существует:
`world.hydrology.default_rivers.autoresolve` — унаследованное поле
MaskCategoryPolicy через HydrologyCategoryPolicy/ HydrologyRiversPolicy.
Использовать его как world channel RIVER_AUTORESOLVE в общем каскаде,
а не вводить второй world river_autoresolve. Не подчинять процедурные
реки автоматически world.hydrology.generation.autoresolve (это общий
контекст designed bodies; river category channel остаётся отдельным).
Миграцию текущего concrete default к принятому nullable channel
закрепить в ТЗ: нельзя потерять None до каскада. Autoresolve=False
сам по себе не выключает явно объявленную геометрию рек.

[find_river_sources](../../backend/app/application/worldData/generators/hydrology/rivers/riverNetworkPlanner.py:83)
берёт локальные максимумы высоты. Однако plan_river_network затем
пересортировывает источники seed-ключом: новый приоритет мастера пока
не реализован. [distance_to_mouths](../../backend/app/application/worldData/generators/hydrology/rivers/riverGeometry.py:24)
считает число D8-шагов рабочей сетки, а не длину в world-fine cells.
Радиус допуска authored mouth уже имеет отдельный POJO
`HydrologyRiversPolicy.mouth_search_radius_fine`; это другая задача,
не использовать его default как радиус поиска истока.

Уточнение после вопроса мастера о fine/L2 (2026-10-22): текущий
**procedural source search выполняется на coarse surface grid**.
Production цепочка: surfaceTerrainContext передаёт coarse_hm в
HydrologyGeneratorService.apply →
[riverNetworkAssembler](../../backend/app/application/worldData/generators/hydrology/riverNetworkAssembler.py:74)
→ autoresolve_river_segments → plan_river_network → find_river_sources.
Истоки выбираются из ключей heightmap.surface_z этого coarse snapshot.

Существующий fine путь —
[apply_declared_fine_river_carves](../../backend/app/application/worldData/generators/hydrology/shore/fineHydrologyIndex.py:26):
он загружает declared river edges/intents, готовит WORLD_FINE_GRID
requests и profiles, но не вызывает find_river_sources или procedural
source producer. В текущем caller base_space=WORLD_SURFACE_GRID;
fineRiverSampling получает sparse fine высоты из coarse snapshot для
authored routes. Это не доказательство поиска procedural вершины по
готовому L2 heightmap. При explicit WORLD_FINE_GRID input helper может
читать fine heights, но production source search от этого fine не становится.

Не смешивать три контракта: единицы radius (world-fine cells), разрешение
высот при выборе максимума (coarse/fine) и существующий mouth snap
radius (mouth_search_radius_fine). Умножение coarse расстояния на scale
не находит истинный fine maximum. Для целевого поиска истока именно на
fine/L2 требуется явно определить provider fine elevations и ограниченный
search region независимо от выбранных bake tiles; полный fine мир
материализовать ради поиска нельзя. Не объявлять новую fine source
генерацию уже реализованной fine declared-river проходом.
Для target этот выбор теперь закрыт: реализовать §6.10, именно fine/L2
source search. Весь предыдущий абзац о coarse описывает текущий code gap,
а не допустимый вариант целевой реализации.

Целевое поле HY-RIV-1:
`world.hydrology.default_rivers.source_search_radius_fraction: ExtentFraction`
— общий wire-тип `dataModel/spatial/extentFraction.py` (float, (0,1],
greater=0/lesser_equals=1), тот же constraint что у fields
dataModel/hydrology/seas.py (max_area_fraction и др.): механизм
«доля extent» один и вынесен в общий тип; seas/lakes fraction fields
переходят на него при re-type без смены wire. Эффективный радиус:
`extent_radius_fine(fraction, extent)` из того же module =
round(fraction × diagonal_fine(extent)); диагональ выбрана как база,
чтобы fraction=1 покрывал весь extent. База — extent принимающего тела
из terrain-owned RegionCoverage accepted placement; при отсутствии
региона — resolved topology extent мира (declared world_bounds не
требуются). Canonical default=0.25, согласовано с масштабом seas
max_area_fraction; default живёт в rivers POJO, не в типе. Радиус —
допустимая область поиска, не длина реки и не число точек polyline.
Новое поле пока не реализуется.

Целевая метрика радиуса/близости: кратчайшее геометрическое XY
расстояние через topologyGeometry.dist2 (швы/полюса), выраженное в
world-fine cells. Source candidates и receiving waterline берутся в
canonical fine координатах одного pre-river snapshot; сравнение
`min(dist2(fine_topology, candidate, waterline_cell)) <= radius_fine^2`
по клеткам waterline, где radius_fine — производное
extent_radius_fine(fraction, базовый extent), вычисленное до сравнения.
Поиск по fine/L2 обязателен, coarse centers и
масштабирование coarse расстояния не заменяют этот контракт. Coarse
index допустим только для conservative enumeration области (§6.10).
Reachability и длина
реального river route проверяются отдельно и не подменяются этой метрикой.

Q-SOURCE закрыт решением мастера 2026-10-22: в пределах радиуса от
принимающей waterline выбрать самую высокую допустимую вершину;
при равной высоте — ближайшую к этой waterline. Расстояние кандидата
до waterline — минимум до допустимых принимающих клеток данного тела,
не до его центра, bbox или произвольного якоря. При полном равенстве
использовать canonical y, затем x (§6.10). Это предпочтение кандидатов истока, а не замена
общего spatial priority specificity → area → UID. Принимающее тело
и возможность реального маршрута остаются обязательными ограничениями.
Проверки HY-RIV-1: высокая вершина внутри радиуса побеждает более близкую
низкую; при равной высоте побеждает ближайшая; вершина вне радиуса не
участвует независимо от высоты; проверяются швы и стабильный полный tie.
Default радиуса закрыт: `source_search_radius_fraction=0.25` от
диагонали extent принимающего тела (fallback — topology extent мира);
contract §6.10. Resolved input остаётся обязательным.
Метрика/единицы и порядок уже закреплены в §6.10.

Q-AREA закрыт решением мастера 2026-10-22: water_fraction отдельного тела —
доля его generation region; на мире — всей фиксированной области мира.
Домен региона сам возвращает размер/площадь через свой typed API.
Гидрология и water strategy получают готовую площадь; локальные вычисления
по bbox, пересчёт shape или подсчёт доступных bake-клеток вместо этого
контракта запрещены. Размер области кандидатов и окончательная область
воды различаются: знаменатель не выводится из уже заполненного footprint.

Контракт региона должен явно обозначать площадь (не смешивать с длиной,
шириной или bbox), её единицы и область действия. Для сравнения с placement
используется площадь полного региона с учётом topology до tile clipping,
в согласованных квадратных единицах; преобразование единиц выполняется
на общей границе координат. Точная граница/provider/тип результата
определены в §6.3 по инвентаризации кода; готового terrain-region extent
API сейчас нет.
Проверки: не прямоугольный регион, регион через шов, full/partial bake —
гидрология получает одну и ту же площадь из доменного результата.

### 6.3 Точная граница выдачи контракта доменом рельефа

Инвентаризация выполнена 2026-10-22 по прямому запросу мастера.
Существующий caller: `terrain/passes/surfaceTerrainContext.py`, функция
`prepare_surface_terrain_context`. Точка выдачи контракта — после
`run_surface_pass_coarse` и создания pre-1.4 `coarse_relief_z`, **перед**
нынешним вызовом `run_water_placement_pass`:
[строки 93–100](../../backend/app/application/worldData/generators/terrain/passes/surfaceTerrainContext.py:93).
Исходные высоты готовы, water carve/fill ещё не выполнялись.

Проверенные существующие результаты не закрывают этот контракт:
- [SurfaceHeightmap](../../backend/app/application/worldData/generators/terrain/types.py:21)
  содержит world_uid/bbox/surface_z, без регионов и их площади.
  [run_surface_pass_coarse](../../backend/app/application/worldData/generators/terrain/passes/surfacePass.py:52)
  возвращает именно её. Не добавлять перечень регионов в каждую coarse/fine
  heightmap: геометрия области и сетка высот — разные контракты.
- [regions/factConsumers/relief.contribute](../../backend/app/application/worldData/regions/factConsumers/relief.py:9)
  возвращает mean elevation/flatness по готовому SurfaceTerrainContext.
  Это downstream; pre-hydrology provider здесь создаст цикл.
- [waterShape.shape_cells](../../backend/app/application/worldData/placement/adapters/waterShape.py:11)
  уже возвращает клетки и shape.area() для water placement input.
  Не назначать этому adapter ответственность за площадь generation region.
- RegionShape.area() и WorldBounds.width/height — существующие примитивы
  реализации, не готовый terrain-domain API для потребителя.

**Terrain provider (реализуется isolated в G3-R):**
`backend/app/application/worldData/generators/terrain/regions/regionExtent.py`
— `prepare_terrain_regions(world: RasterWorld, *, inputs: TerrainRegionPlanningInput) -> TerrainRegionPlan`.
Вход: world/snapshot identity, resolved topology, масштаб coarse→fine,
фиксированные world_bounds, полные region intents и готовые anchors.
Переиспользовать PlacementIntent/RegionShape, без нового геометрического
DSL и spatial resolver. Auto body без собственной области получает
явную ссылку на world region; отсутствующий обязательный регион —
unresolved, не площадь по wet cells. Input частичного auto source — G0/G3.

**Тип результата в dataModel, без application/db импортов:**
- `backend/app/dataModel/terrain/regions/terrainRegionExtent.py`:
  frozen `TerrainRegionExtent(region_uid, generation_area_fine2)`.
  generation_area_fine2 — strict int >=0, квадратные world-fine XY cells.
  Пустой регион имеет0; существующий world region имеет площадь>0.
- `backend/app/dataModel/terrain/regions/terrainRegionsSnapshot.py`:
  frozen `TerrainRegionsSnapshot(world_uid, snapshot_uid, world_region,
  regions)`, где world_region: TerrainRegionExtent | None,
  regions: tuple[TerrainRegionExtent, ...].
  Frozen TerrainRegionPlan содержит snapshot и соответствующие canonical coverages;
  area каждого extent совпадает с мерой его coverage. Возвращается один plan,
  а потребителям water/budget передаётся plan.snapshot вместе с нужной coverage.

Это полная площадь области генерации до tile clipping, не bbox
нерегулярной формы, не количество L0 samples и не площадь готовой воды.
Геометрия остаётся существующим input, extent не создаёт её второй SoT.
UID берутся из переданных identity; новый неоговорённый UID mint запрещён.
Source→region binding передаётся явно, не угадывается гидрологией.

**Target шов caller/callee (activation только G10-A):** SurfacePlanningAssembler.prepare получает topology
на существующей boundary resolveHydrologyTopology, вызывает terrain
provider и передаёт plan.snapshot обязательным keyword
`regions: TerrainRegionsSnapshot` в run_water_placement_pass и подготовку
DesignedWaterStrategy. В water pass передаётся та же topology.
Provider pure: не вызывает hydrology, не пишет surface_z и не выполняет
placement. Caller готовит единый snapshot независимо от bake tiles.

**Размер мира:** provider использует полный canonical world domain;
для текущей равномерной XY-сетки площадь = world_bounds.width ×
world_bounds.height × map_cell_fine_span(world)^2. Bounds/topology
валидируются до измерения, canonical aliases не учитываются дважды.
Сфера здесь означает топологию сетки, не геодезическую площадь в м².
Irregular region измеряется через существующие spatial/topology primitives
без полного rasterize мира в fine cells. Ошибка площади явная,
гидрология не имеет fallback к bbox area.

**Два разных значения:** generation_area_fine2 — знаменатель процента
воды, предоставляемый рельефом. PreparedPlacement.original_area — площадь
footprint конкретного placement-объекта для priority в working-grid cell².
Они могут различаться. Подменять original_area площадью области поиска
запрещено; преобразование единиц выполняется на coordinate boundary.

### 6.4 Остальные вопросы

Q-TARGET закрыт: процент — цель подготовки, а не обязательный итог.
Authored ограничения и reserved горы сохраняются; объявленные водоёмы
учитываются в общей доле. Для фактического процента использовать final
filled water и площадь области из terrain contract §6.3. Перекрытия
водоёмов в общей доле считать как union, без двойного учёта; dry SHORE
не считать водой. Показывать целевой и фактический процент после генерации,
не расширять воду скрыто ради выполнения процента. Единицы числителя
и знаменателя должны совпадать.

Q-AUTO/default и Q-AUTO/gates закрыты: terminal False и §6.8.
Настройки проходят общий каскад; category autoresolve не применяется
вторым скрытым gate после body override. Явные geometry/floor не
переписываются autoresolve без профильного domain policy контракта.

Проверка согласованности с POJO-политиками (2026-10-22):
- [annotationPolicy](../../backend/app/dataModel/annotationPolicy.py:26) и
  [tz_json_validation](../../docs/tz_json_validation.md:603):
  DefaultWhenMissing использует schema default только при missing;
  nullable null сохраняется, invalid не получает fallback.
- Authored-поле: `DefaultWhenMissing[StrictBool | None] = None` с
  CascadeChannel. Terminal defaults POJO содержит отдельный StrictBool
  False; CascadeDefault(FieldRef(...)) читает его в конце цепочки.
- Read-only probe существующего resolve_model на временной in-memory
  Pydantic-модели: missing/null → None, False → False, True → True;
  строка "false" и число 0 отклонены строгим типом.
- Нынешний [MaskCategoryPolicy](../../backend/app/dataModel/masks/maskCategoryPolicy.py:14)
  даёт True при missing и отклоняет null; это подтверждено тем же probe.
  Существующее поведение не объявляется уже совместимым с новым default.
  Переопределить nullable-поля только у включаемых в cascade hydrology
  POJO (river/lake/category, sea channels по решению gates). Не менять
  общий MaskCategoryPolicy и unrelated landcover/landforms.
- Явно сохранённый True остаётся authored True: normalized POJO не
  позволяет восстановить, подставил ли его когда-то старый default.
  Существующие миры с True не переписывать по догадке. Missing/None новых
  контрактов получают принятый fallback через каскад.
- Сырой None не передаётся прежним bool()/and/or gates как готовое
  решение: callers получают resolved cascade context; preview/runtime
  используют один результат. Invalid bool остаётся validation error.

Q-STRATEGY/selection закрыт: strategy наследуется world → body через
каскад; authored geometry ограничивает выбранную noise/plate strategy.
Все способы и композиция plate+noise — через общую абстракцию. Точный
оператор композиции полей/его числовые параметры определить в G0.
Terminal strategy default уже согласован: continental_noise (§5.1).

Q-COAST уточнён архитектурой §5.3: water_source создаёт body intent по
линии без dependency на будущую воду; body_boundary требует готовую
водную опору. Общий priority=0 запрещает создание обоих видов объектов.
Прежнее blanket правило «любой coastline нужен уже готовый водоём»
отменено: оно блокировало обязательный source-line сценарий.
CoastlinePlacementFact absent→effective 0 применяется к dependent
boundary, не к body source; фиктивная pre-fill вода не вводится.
ТЗ/модели/старые тесты корректируются в G0/G0-P/G5-C1…C3 до production wiring.

Защита гор принята независимо от Q-COAST: coastline не меняет mountain
footprint/connectivity/grade и высоты reserved mountain cells. Ссылка
на водоём/разрешённый overlap не разрешает переписать горы. Existing
basinZ reserved raised cells защищает высоту; полная проверка L0/L2
и grade precedence ещё нужна, HY-7 этим не объявляется закрытым.

### 6.5 Общая priority policy: ноль запрещает создание

Общее правило admission принадлежит `dataModel/policy/` и
`application/policy/`; его placement outcomes/исполнение —
`dataModel/placement/` и `application/worldData/placement/`.
Правило действует на все домены
и стратегии; отдельные priority системы воды/гор/континентов запрещены.
Adapter готовит факты и candidates. Effective value/допуск вычисляет
общий PolicyResolver; ordering/dependency scheduling — общий placement;
diagnostics обслуживает существующий reporting. Auto specificity —
только переходный транспорт §6.8-F/G0-P, не target domain resolver.
Для positive priorities остаётся
specificity по убыванию → original_area по убыванию → region_uid.
Приоритет не меняет geometry/topology и не обходит обязательную опору.

Состояния различаются: None — не разрешён auto/вход, 0 — создание
отключено, >0 — можно рассматривать candidates после готовности опор.
0 сохраняется как валидное authored значение; запрещено заменять его
положительным fallback через truthiness. Уже accepted placements не
удаляются/не пересматриваются поздним dependent pass: правило допуска
применяется при создании нового объекта на его исходном snapshot.

Проверенный code gap 2026-10-22:
- [resolver._preflight](../../backend/app/application/worldData/placement/resolver.py:24)
  сегодня при dry coastline только выдаёт notice, не запрещает placement.
- [DependencyQueue._enqueue](../../backend/app/application/worldData/placement/dependencies.py:69)
  принимает любое effective_specificity is not None, включая 0.
- [ResolvedPlacement](../../backend/app/dataModel/placement/result.py:39)
  проверяет None, а не положительность при создании.
- [test_dry_coastline_can_create_water_with_zero_even_when_auto_not_provided](../../backend/tests/test_placement_resolver.py:227)
  прямо ожидает создание с 0. Текущее поведение расходится с решением
  мастера; нельзя сообщать, что правило нуля уже реализовано.

Исправление планируется в общем P2: generic preflight запрет создания
при 0 до перебора candidates, typed non-created result и единая
диагностика причины. Согласованный target: общий DisabledPlacement
отдельно от ResolvedPlacement и UnresolvedPlacement (§6.8-C1),
без water-only skipped outcome. Намеренное отключение не является
ошибкой валидации. Результат не должен попасть в ResolvedWaterPlacement,
BasinSpec, z-write, roles или persist. Не удалять запись из batch молча:
dependent должен получить явный факт непринятой опоры, а независимые
объекты должны продолжить resolve. Runtime/preview возвращают одно решение.

Влияние defaults: dataModel/hydrology/category.py:19 и seas.py:29 сейчас
имеют placement_specificity default=0. После смены общей семантики
они отключат auto placement, а не зададут самый низкий рабочий приоритет.
Инвентаризация найдена и зафиксирована: нужны явные решения для этих
POJO defaults в G0; не менять их молча на 1 в resolver/adapter.
None-наследование source intent остаётся отдельным контрактом.

Q-EXTENT закрыт: фиксированные world_bounds для глобального процента воды;
отсутствующие bounds требуют явной диагностики, не скрытого пересчёта
океана по текущему AABB anchors. Расширение границ — изменение входов мира,
с гарантиями детерминизма при неизменных bounds/seed/settings.

Q-RIVER уточнён: отдельная policy world.hydrology.default_rivers.autoresolve;
новый source producer проектируется в HY-RIV-1 по §6.2. GEO-1 фиксирует
downstream seam, не заменяет legacy producer попутно. Q-SOURCE закрыт:
height-first в радиусе от принимающей waterline, затем distance.
Метрика/единицы закреплены в §6.10: ExtentFraction от extent
принимающего тела (fallback — topology extent мира), default 0.25.

### 6.6 Актуальные оставшиеся решения мастера

Реестр сверён после закрытия Q-SHORE и согласования стратегий. Не
переоткрывать default continental_noise, 60%/False, роль SHORE,
fixed bounds, source/boundary distinction или порядок выбора истока.

1. Q-PRIORITY-DEFAULT/architecture закрыт: explicit default на POJO
   доменной policy, общий terminal fallback=0 (§6.9). Поле priority одно;
   общий PolicyResolver обязан фактически читать default через typed
   источник и передавать decision в P2. Универсальный default 1 не нужен.
   Значения конкретных domain defaults задаются их POJO, без копирования
   в engine. Existing domain 0 нельзя молча объявить положительным.
2. Q-AUTO-GATES закрыт: enabled=False — абсолютное отключение гидрологии;
   autoresolve WORLD→CATEGORY→BODY, typed каналы, body override имеет
   силу; False не отменяет authored geometry. Контракты POJO/enum §6.8.
3. Q-SOURCE-RADIUS закрыт: target §6.10 — fine/L2 scan,
   world-fine XY cells и shortest topology distance до receiving
   waterline. Поле `source_search_radius_fraction: ExtentFraction`
   (доля extent принимающего тела; fallback — topology extent),
   canonical default=0.25; effective radius_fine — производное
   extent_radius_fine до сравнения. Не использовать
   mouth_search_radius_fine как подстановку и не
   давать coding agent выбирать coarse вместо fine.
4. Q-SHORE-UNKNOWN закрыт: validation — явная ошибка; runtime — сохранить
   исходные terrain/material/SHORE без coating и обязательный fallback
   error через existing WarningError sink. Общий критерий и факты
   одинаковые, отличается обработка результата (§6.11).

Критерии terrain-owned coating support закрыты §6.29-H (substrate enum,
canonical mapping, facts/truth table). Формулы/нормализация plate+noise
и значения алгоритмических knobs закрыты §6.29-F (defaults в owning
POJO, noise/plate/composition формулы, wet score quantization, threshold).
Открытых числовых вопросов нет; G7/G7-C реализуют формулы как есть.

### 6.7 Аудит действующего placement policy перед выбором defaults

Выполнен 2026-10-22 по запросу мастера. Ни код, ни общий placement SoT
в этом аудите не менялись. Ниже текущее поведение; отдельно указаны
расхождения с принятым target, а не «исправления по умолчанию».

**1. Авторское значение и подготовленный auto — разные входы.**
[PlacementIntent.placement_specificity](../../backend/app/dataModel/placement/intent.py:43)
имеет default None. Strict integer >=0, без верхнего cap; None означает
auto. [PreparedPlacement](../../backend/app/dataModel/placement/prepared.py:40)
требует явный auto_specificity: int|None. Resolver не вычисляет его по
количеству authored полей, геометрии или типу домена.
Если authored is not None, выбирается оно; иначе supplied auto.
Нет обоих → MISSING_SPECIFICITY/unresolved, без 0/1 fallback.
В действующем механизме нет общего PlacementPolicy POJO с terminal
default и нет связанной с placement priority декларации CascadeChannel.
Не объявлять placement priority уже использующим наш water settings cascade.

**2. Источник auto сейчас — caller policy, не решение общего resolver.**
[waterPlacementPass._auto_specificity](../../backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py:54)
читает default_lakes.placement_specificity для lake, иначе
default_seas.placement_specificity. Оба POJO сейчас default 0:
dataModel/hydrology/category.py:19 и seas.py:29.
Caller передаёт source_uid→value в WaterPlacementContext; adapter
кладёт value в PreparedPlacement. Это не generic auto-ranking algorithm.
Source-specific policy values могут принадлежать исходным POJO, но
правила выбора, eligibility и сравнения должны оставаться общими.
Не смешивать «данные доменного источника» с «домен владеет priority системой».

**3. Общая модель сейчас содержит domain-specific coastline exception.**
[effective_specificity](../../backend/app/dataModel/placement/prepared.py:60)
сначала проверяет coastline.water_presence: unknown → None, absent → 0;
только затем authored/auto. [resolver._preflight](../../backend/app/application/worldData/placement/resolver.py:24)
тоже знает WaterPresence и выдаёт специфический coastline notice.
Это существующее сцепление общей policy с водным фактом. С учётом
требования мастера о domain-neutral priority оно подлежит отдельному
контрактному разбору в G0-P: generic dependencies/eligibility должны
выражать требование опоры, а source-line и boundary различаются §5.3.
Перенести тот же if coast в новый общий класс с другим именем недостаточно.
Не делать отдельный priority resolver в water adapter как «исправление».

**4. Очередь зависит от готовности опор.**
[DependencyQueue](../../backend/app/application/worldData/placement/dependencies.py:52)
собирает dependency graph. В ready queue попадают только объекты,
чьи обязательные опоры уже приняты; среди них heap key:
(-effective_specificity, -original_area, region_uid).
После принятия опоры дочерний объект становится готовым и участвует
в следующем сравнении. Это не общий sort всех объектов заранее и не
правило «все родители всего мира, потом все дети». Уже accepted решения
не вытесняются поздним объектом с высоким priority.
Missing/failed support и SCC-cycle дают typed unresolved.

Проверенный пример, без записи файлов: parent(priority=1) и
rival(priority=50) готовы; child(priority=100) ждёт parent и конкурирует
с rival за ту же клетку. Сначала принимается rival, затем parent;
child проигрывает spatial conflict. При parent priority=60 принимается
parent, затем ставший готовым child=100, и rival проигрывает.
Следовательно, fallback 1 влияет на доступность зависимых объектов
через порядок принятия опор; это не только косметический нижний ранг.

**5. Приоритет не гарантирует геометрическое решение.**
[resolver._place](../../backend/app/application/worldData/placement/resolver.py:43)
пробует candidates по (preference, candidate_uid). Candidate preference
меньше → лучше; object specificity больше → раньше. Это две разные шкалы.
[constraints.check_candidate](../../backend/app/application/worldData/placement/constraints.py:47)
проверяет topology/bounds, геометрические dependency predicates,
separation и collisions/permitted overlaps с accepted objects.
Priority не отменяет ни одной проверки. Нет clip, самовольного сдвига,
backtracking или перекраивания уже принятого объекта.
original_area — исходная площадь footprint, не оставшаяся площадь,
не generation region budget и не terrain merge rank.

**6. Ноль сейчас ещё не отключает создание.**
_enqueue проверяет value is not None, включая 0. _preflight не блокирует
0; ResolvedPlacement также допускает его. Это расходится с новым
согласованным правилом мастера 0=no creation. G0-P должен изменить
этот общий контракт с явным non-created outcome и dependent behavior.
Данный аудит не отменяет принятое новое значение нуля.

**7. Read-only подтверждение действующего поведения.**
Вызваны реальные solve/obj helpers существующих placement tests:
- authored 4 + auto 9 → effective 4, resolved;
- authored 0 + auto 9 → effective 0, сейчас resolved;
- authored None + auto 9 → effective 9, resolved;
- authored None + auto None → unresolved;
- dry coastline authored 99 + auto 9 → effective 0, сейчас resolved;
- dependency пример parent 1/60 выше воспроизведён обоими вызовами.
Это проверки текущего механизма, не приёмка target zero policy.

**8. Что требуется решить до выбора числа.**
Не назначать fallback 1 до фиксации:
- общего источника placement priority policy и его source/cascade
  channels, без повторных defaults в domain adapters;
- разделения generic eligibility/dependency и priority ordering;
- роли positive auto priority: единый ранг, наследование от уровня
  источника либо другая явно утверждённая policy, но не вычисление
  «конкретности» эвристикой по числу полей;
- generic представления отсутствующей опоры вместо water-specific
  ветки внутри PreparedPlacement;
- последствий отключённого объекта для dependents и явных деклараций;
- карты действующих 0/default источников до смены semantics.

Принятые инварианты уже фиксированы: общий механизм policy для всех доменов,
0 запрещает создание, None не подменяется значением молча, positive
priority не обходит зависимость/geometry constraints. Выбор конкретного
Аудит выполнен до последующего решения §6.9: тогда fallback оставался
открытым; теперь общий fallback=0, число 1 не утверждалось.
Уточнение мастера после аудита: defaults и частные случаи принадлежат
контексту домена, а их resolution — общему engine (§6.8). Пункты аудита
об общем источнике defaults не требуют единого числа для всех доменов.

### 6.8 Общий механизм policy и контекстные правила доменов

Этот раздел уточняет target после аудита §6.7. Общий алгоритм не означает
одинаковые defaults у всех доменов. Домен задаёт контекст, параметры и
частные правила; общий policy resolver исполняет их и выдаёт решение.
Нельзя вынести в общий код только sort, оставив конечные if/else решения
в HydrologyPolicy.resolve()/TerrainPolicy.resolve().

**A0. Отключение объекта — общая policy (согласовано).**
Семантика отключения принадлежит общему механизму policy, не hydrology,
terrain или другому домену. Общая `ObjectAdmissionPolicyDefinition`
в `dataModel/policy/objectAdmissionPolicyDefinition.py` методом
`build(bindings) -> PolicySpec` объявляет правила запрета создания:
явный общий запрет/выключенный применимый enabled gate и эффективный
placement priority=0 дают DISABLED. `bindings` — typed ссылки на
применимые настройки и факты, не копия persisted enabled/priority полей.
Правила исполняет общий PolicyResolver; общий placement обеспечивает
не-создание: disabled объект не принимается в ready queue, не резервирует
пространство и не выпускает materialization/carve intent.

Домен задаёт контекстные значения/defaults, ссылки на свои настройки
и частные условия, выраженные общими typed predicates/effects. Он не
объявляет собственную семантику DISABLED, не реализует отключение в
domain resolver/adapter/writer и не может отменить общий запрет.
Domain definition подключает общий admission spec; правило enabled=False
не копируется в каждой domain definition. В частности, гидрология лишь
связывает WorldHydrology.enabled с общим gate. Autoresolve=False само
по себе не отключает authored объект: это выбор режима генерации.
Отсутствующий обязательный вход/сломанная ссылка не превращаются в
намеренное отключение; классификация ошибки и runtime fallback остаются
отдельными от общего результата DISABLED.

Точная схема bindings/effects, композиция specs и зависимые outcomes
закрываются в GAP-POLICY/GAP-OUTCOME; этот пункт фиксирует владельца
и инварианты, но сам по себе не закрывает оба gap.

**A. Три отдельные ответственности.**
1. Domain POJO — параметры/defaults и enum значения поведения;
   source-specific priority defaults разрешены. Например, существующие
   HydrologySeasPolicy/HydrologyLakesPolicy задают свои default priority.
   Их нынешние 0 сохраняются как факт аудита; новые положительные числа
   ещё не выбраны. Обязательного общего default=1 не вводить.
2. Domain policy definition + facts provider — декларации частных случаев
   и типизированные наблюдения. Они не исполняют правила и не возвращают
   конечные placement winner/priority override/режим исполнения.
3. Shared PolicyResolver — единственное место сопоставления cases,
   разрешения effects/приоритетов и формирования typed policy decision.
   Общий placement затем выполняет ready queue и spatial checks, читая
   policy decision, а не повторяя domain conditions.

**B. Конкретные классы и методы (планируемые, сейчас отсутствуют).**
**Расположение папок — обязательный архитектурный контракт (согласовано).**
Корень всех путей ниже — репозиторий `E:/AI Project`:
- `backend/app/application/policy/` — общий механизм исполнения policy,
  включая `policyResolver.py::PolicyResolver`. Папка непосредственно
  внутри application, на одном уровне с application/cascade и
  application/jsonValidation. Не размещать общий engine внутри worldData,
  placement, generators или отдельного домена.
- `backend/app/dataModel/policy/` — общие typed контракты policy,
  enum, decisions и общая ObjectAdmissionPolicyDefinition.
- `backend/app/dataModel/hydrology/policy/` — гидрологические декларации
  policy; другие домены размещают свои декларации в своём dataModel
  namespace и используют общий engine.
- `backend/app/application/worldData/placement/` — существующий общий
  механизм размещения и его интеграция с policy; не папка policy engine.
Domain facts providers остаются в application соответствующего домена
по явным путям этого плана. Направление зависимостей: application
использует dataModel; общий application/policy не импортирует доменные
реализации, а dataModel не импортирует application/policy. Эти пути
обязательны для G0-PT/G0-PE и дальнейшего wiring; coding agent не
выбирает альтернативное расположение по месту реализации.

- `dataModel/policy/policySpec.py::PolicySpec` и
  `dataModel/policy/policyRules.py::PolicyRule` — frozen
  декларации rules: typed condition, effect, явный rule precedence,
  stable identity/reason и источник значения. Правила — engine-owned
  типизированные декларации, не произвольный wire DSL или eval-код.
- `dataModel/policy/policyEnums.py`: enum условий/действий/результатов.
  Общие effects: выбрать typed значение/priority, запретить создание,
  потребовать готовую опору, сообщить unresolved. Общие состояния
  решения: READY, DISABLED, WAITING_SUPPORT, UNRESOLVED. Domain-specific
  water/terrain enum в общий engine не зашивается.
- `dataModel/policy/policyDecision.py::PolicyDecision` — frozen resolved
  result с typed значением/priority, состоянием и provenance сработавшего
  case. Его конкретные специализации задают тип результата: placement
  priority/admission или hydrology execution mode; не dict[str, Any].
- `application/policy/policyResolver.py::PolicyResolver.resolve(
  spec, sources, facts, *, mode: ResolutionMode) -> PolicyDecision` — один исполнитель для доменов.
  Он не импортирует hydrology/terrain policy implementations. Generic
  conditions ссылаются на непосредственные POJO поля через typed FieldRef
  (переиспользовать примитив после проверки зависимостей), не field: str.
- `dataModel/hydrology/policy/hydrologyPolicyDefinition.py` объявляет
  HYDROLOGY_GENERATION_POLICY и field metadata enabled/autoresolve;
  `hydrologyPlacementPolicy.py` (G5-CP) — отдельный placement descriptor/cases,
  source-vs-boundary и domain defaults, без обратного импорта source models
  в generation metadata. Общие `application/policy/declarations/compiler.py::
  compile_value_policy/compile_admission_policy` создают existing specs из
  descriptor и явного tuple source types. Compilation не выбирает case;
  семантику отключения исполняет один resolver.
- `application/worldData/generators/hydrology/policy/hydrologyPolicyFacts.py::
  collect_hydrology_policy_facts(source, snapshot) -> HydrologyPolicyFacts`
  — typed purpose/category/water-support facts. Можно вычислять водную
  геометрию/наблюдения, нельзя решать effective priority или runtime mode.
- Для другого домена — собственные definition/facts/settings по тому же
  protocol. Не нужна копия PolicyResolver и не допускается ветка
  `if domain == hydrology` внутри общего исполнителя.

Это новые контракты по инвентаризации: готового domain-neutral case/policy
resolver в placement нет. Существующие materialPolicies, cascade default
policy и wire policy — другие контракты, не объявлять их этим engine.
Общий cascade продолжает только наследовать параметры; PolicyResolver
читает уже resolved значения. StrategyFactory продолжает только dispatch.

**C. Семантика исполнения, без скрытых порядков.**
**Порядок стадий согласован; исполняется общим механизмом:**
1. Проверить абсолютные запреты через общий admission spec и применимые
   enabled gates. Сработавший запрет завершает решение как DISABLED.
2. Если запрета нет, разрешить необходимые настройки и effective
   placement priority по объявленным typed ссылкам и cascade-контракту.
   Не вычислять доменные defaults повторно внутри placement.
3. Effective placement priority=0 завершает решение как DISABLED.
4. Для положительного priority проверить обязательные зависимости
   и факты: ожидаемая опора того же batch даёт WAITING_SUPPORT,
   отсутствующий обязательный вход/ошибка — UNRESOLVED. При готовности
   всех необходимых входов решение становится READY.
5. Только READY поступает в общую ready queue; placement выполняет
   геометрические constraints и разрешение пространственных конфликтов.
   Положительный priority определяет очередность, но не отменяет проверки.

Это порядок runtime-вычисления, а не порядок регистрации rules.
DISABLED объекту не вычисляют ненужную геометрию и не ожидают его опоры.
Раннее отключение не скрывает ошибки объявленных POJO: schema/world
validation проверяет типы и допустимость значений также у отключённых
объектов. Сломанный вход, необходимый для текущей стадии, нельзя
подменять намеренным DISABLED; обработка ошибки/fallback явная.
Внутренняя схема выбора/конфликтов rules каждой стадии ещё относится
к GAP-POLICY; согласование порядка стадий не закрывает этот gap целиком.

В G0 определить exact enum effects/conditions и их совместимость;
не оставлять вычисление конфликтующих cases порядку Python списка.
Согласовано: hard forbid терминален; required support не может быть
обойдён priority; rules выбора значения сравниваются по явному rule
precedence, при равенстве и несовместимых значениях — typed unresolved.
Rule precedence и placement priority — разные параметры. Одно правило
не вправе обходить общий инвариант placement priority=0 → no creation.
Stable rule identity определяет воспроизводимую диагностику, но не
выбирает победителя при смысловом конфликте равного precedence.
Пропущенный факт/unknown не считается False: WAITING_SUPPORT при
ожидаемой опоре того же batch, UNRESOLVED при отсутствующем обязательном
входе. Ready queue остаётся общей и не принимает незавершённое решение.
Runtime/preview используют тот же spec/facts/decision и разные sinks.
После policy decision не выполняется второй domain-specific if/else,
который тайно меняет priority/режим. Геометрические constraints P2 остаются
самостоятельным обязательным gate, не отменяемым решением policy.

**C1. Конечные placement outcomes (согласовано).**
PlacementOutcome — discriminated union трёх общих контрактов:
ResolvedPlacement(status=resolved), DisabledPlacement(status=disabled),
UnresolvedPlacement(status=unresolved). DisabledPlacement содержит
identity, typed reason и provenance решения; это не accepted placement.
WAITING_SUPPORT — только промежуточное состояние; завершённый batch
его не содержит. Отключённый объект сохраняется в результатах batch,
не резервирует footprint и не порождает spec/carve/materialization.
Намеренно disabled обязательная опора даёт зависимому DisabledPlacement
с причиной SUPPORT_DISABLED и ссылкой на causal outcome; отсутствующая
или unresolved обязательная опора даёт UnresolvedPlacement. Цикл
обязательных зависимостей также unresolved. Уже отключённому объекту
не требуется ждать опору. Независимые объекты продолжают разрешаться.
Exact fields/enum причин, связь outcome с prepared input и агрегирование
нескольких causal outcomes заданы §6.29-C/D.

**C2. Ошибка, нормальное отключение и fallback (согласовано).**
Authored priority=0 и domain POJO default=0 — нормальный DISABLED,
не самостоятельная причина report.valid=False. Provenance явно
различает authored/domain default/common fallback/case и хранит источник.
Применённый общий terminal fallback в runtime обязательно логируется
через существующий проектный emitter по §6.12. Сломанная обязательная
ссылка/некорректная настройка дают явную validation issue; runtime
использует только предусмотренный для данной ошибки typed fallback,
с обязательным логом причины и provenance. Нельзя молча подменить
ошибку числом 0 или выдать её за авторское отключение. Fallback может
привести к disabled outcome, но не удаляет исходную ошибку из diagnostics.
Exact severity/code матрица и validation hook — GAP-VALIDATION/LOG.

**C3. Проверка соседних механизмов (согласованный принцип, аудит кода).**
Общее правило: домен объявляет контекстные правила/данные, общий
исполнитель соответствующего механизма исполняет их. Выбор поведения
выражается PolicySpec и выполняется PolicyResolver. Наследование,
геометрия, scoring и material comparison сохраняют своих общих
исполнителей; их алгоритмы не копируются в PolicyResolver. Общий engine
не превращается в диспетчер всех вычислений генератора.
Размещение общего engine — application/policy, рядом по уровню с
application/cascade и application/jsonValidation, а не внутри worldData:
потребителями могут быть worldData и economy. Placement-specific
интеграция/очередь остаются в application/worldData/placement. Contracts
и definitions — dataModel, исполнение — application; dataModel не
импортирует engine. Wire normalization выполняется jsonValidation,
наследование — cascade, policy получает typed resolved inputs; reporting
использует существующий ResolveContext/report_issues по §6.12.

Production seam: текущий waterPlacementPass готовит геометрию до общего
resolver, а PreparedPlacement требует original_area/candidates. Поэтому
раннее отключение нельзя реализовать только новым preflight над готовым
PreparedPlacement. Нужен typed admission input до geometry preparation;
disabled outcome должен выражаться без фиктивного footprint/area.
Exact POJO и перенос точки вызова — обязательные GAP-POLICY/OUTCOME,
не разрешение вводить lazy callback с доменным решением внутри engine.
После общего разрешения admission/настроек adapter готовит геометрию,
а очередь проверяет готовность dependencies и пространственные constraints.
WAITING_SUPPORT не кэшируется навсегда: при изменении accepted support
facts общий механизм пересматривает зависимое admission, без повторного
cascade/RNG/materialize уже разрешённых значений. Exact protocol этого
взаимодействия закрепить до G0-PE/G0-P; второго dependency scheduler
в PolicyResolver не создавать.

Инвентарь проверенных мест и целевая граница:
- Cascade: [Cascade/FieldRef](../../backend/app/dataModel/cascade/cascadeSpec.py:93)
  объявляют связи; [extend](../../backend/app/application/cascade/contextResolver.py:93)
  исполняет наследование. Это уже разделённый механизм. Existing
  materialize/fold bindings в том же resolver (:66) — специализированные
  операции, не готовый generic policy engine. Не дублировать cascade
  локальными or-цепочками и не переносить наследование в новый engine.
- Placement: [check_candidate](../../backend/app/application/worldData/placement/constraints.py:46)
  исполняет объявленные dependencies/overlaps/separations. Сохранить
  общий geometry gate. В [_preflight](../../backend/app/application/worldData/placement/resolver.py:24)
  остаётся водный special case; G5-CP обязан заменить его общим решением
  по domain-supplied facts, без переноса WaterPresence if в новый engine.
- Masks: [default_collect/run_mask_domain](../../backend/app/application/worldData/masks/runMaskDomain.py:77)
  уже централизуют lifecycle и gates. Их чтение enabled/autoresolve
  ещё не потребляет новый PolicyDecision. Для затронутых GEO-1 путей
  зафиксировать одного владельца gate, не запускать второй независимый
  bool gate после общего решения. Незатронутые домены требуют отдельного
  migration inventory, их перевод не объявлять выполненным этим планом.
- Coverage: [EligibilityRule](../../backend/app/dataModel/terrain/eligibilityRule.py:13)
  задаёт rules, [CoverageResolver](../../backend/app/application/worldData/regions/coverageResolver.py:21)
  централизует predicates/scoring (actual entry — module function resolve,
  не класс CoverageResolver). При этом fact пока str, а missing
  value считается failed/zero; это не target typed unknown-семантика
  общего policy. Не использовать его как новый policy resolver без
  отдельного контракта совместимости. Scoring остаётся одним алгоритмом.
- Materials: [default_material_policy](../../backend/app/application/economy/materialPolicies/defaultMaterialPolicy.py:17)
  локально выбирает MIN/MAX по economic band; это исполняемое доменное
  правило, кандидат на декларацию для общего engine. Само сравнение
  уже общее в [MaterialPolicyConsumer.decide](../../backend/app/application/economy/materialPolicies/materialPolicyConsumer.py:21).
  Его сохранить; перенос выбора поведения оформить отдельным migration
  шагом/треком до заявления о единой policy во всём проекте. Для GEO-1
  shore-coating definition/facts/decision обязаны следовать общей схеме.
- DesignedWaterStrategyFactory (§5.2) — будущий dispatch по уже
  resolved enum; не вычисляет default strategy, admission или fallback.
  Реализации стратегий выполняют алгоритмы поля, не выбирают policy.

До G0-PT/G0-PE нужен ledger затронутых decision call sites: declaration,
facts provider, единственный executor, production consumer, legacy gate
и шаг его удаления. Проверка минимум двух разных domain definitions
одним engine обязательна; unit test изолированного engine не доказывает
отсутствия последующего domain override. Для внешнего migration трека
нужен явный scope и контракт совместимости, без скрытого расширения GEO-1.

**D. enabled/autoresolve: явные POJO и enum контракты.**
`WorldHydrology.enabled` — StrictBool, schema default принадлежит POJO.
Это hard global switch, не nullable autoresolve channel.
`WaterGenerationSettings.autoresolve` и existing category autoregulation
channels — DefaultWhenMissing[StrictBool | None]=None с CascadeChannel;
путь ROOT→WORLD→CATEGORY→WATER_BODY объявлен через ScopeAxis enum и links.
False/True явно заданы, None наследует, terminal False принадлежит POJO.
Existing category поля не копируются во второй persisted settings POJO.

Новый enum `HydrologyExecutionMode` в dataModel/hydrology/enums/planning:
DISABLED, DECLARED_ONLY, AUTORESOLVE. Это computed decision, не вторая
authored настройка, хранящая то же значение, что bool channels.
Typed `HydrologyGenerationDecision` специализирует PolicyDecision этим
enum и provenance. Общая ObjectAdmissionPolicyDefinition обрабатывает
enabled=False → DISABLED независимо от autoresolve; hydrology definition
подключает её typed binding, не дублирует правило. Для допущенного
выполнения domain definition объявляет cases:
- resolved autoresolve=False → DECLARED_ONLY;
- resolved autoresolve=True → AUTORESOLVE, включая
  обработку explicit authored constraints по domain contract.
Только общий PolicyResolver определяет сработавший case/итоговый mode.
Consumers switch по enum готового decision, не повторяют исходные bool.

Existing `HydrologyScope` уже перенесён PC-1H в
dataModel/hydrology/enums/planning/hydrologyScope.py; application types.py
реэкспортирует тот же symbol. Новый enum с тем же смыслом не создавать.
Scope (выбор категории выполнения), cascade level и execution
mode — три разных enum, не смешивать их и не передавать голые str.

**E. Wire граница.**
Raw JSON допустим только в существующем import/normalization/accessor
boundary. Policy definitions, facts providers, strategies и orchestrators
получают POJO/context. Нельзя raw world.hydrology.get(...), dict keys
"enabled"/"autoresolve"/"strategy", локальные string mode или default
literal в потребителе. FieldRef выбирает непосредственное typed поле.
Неверный enum/bool — validation error; ни fallback, ни молчаливое skip.
Выбор алгоритма по enum и создание source identity не дублируются в rules.

**F. Миграция текущего special case.**
Нынешний PreparedPlacement.coastline/effective_specificity и P2 preflight
с WaterPresence заменить чтением результата общего PolicyResolver.
Hydrology definition описывает частный boundary-without-water case;
facts provider передаёт реальное состояние опоры. Common engine применяет
generic effect DISABLE/priority 0 с domain provenance. Для water_source
это правило не подходит по purpose, но никаких локальных исключений
в source adapter/effective property нет. В PreparedPlacement остаётся
одна authoritative policy priority/admission, не два независимо
вычисляемых поля old_effective и new_decision.

**G. Проверки архитектуры.**
Одинаковый spec исполнен одним engine для hydrology и другого домена;
разные domain defaults дают разные решения без изменения engine;
case match/effects/priority разрешает engine; нет domain resolve();
проверяются typed FieldRef/enum, unknown/waiting, конфликт cases,
zero priority, root disabled, category/body overrides, explicit geometry
при DECLARED_ONLY, runtime/preview parity и отсутствие wire raw у consumers.

### 6.9 Одно поле priority: живой POJO default и terminal fallback 0

Решение мастера 2026-10-22: explicit domain default на POJO,
общий fallback 0. Вопрос не требует отдельных полей priority_coastline,
priority_ocean и т.п. Разные domain/category policy экземпляры имеют
одно и то же поле placement_specificity, со своим authored/default
значением по контексту. Их выбор — typed policy definition/domain binding,
разрешение defaults/cases/итогового priority — общий PolicyResolver.

**Цепочка, обязательная в production:**
1. Import/worldRow resolve создаёт source и domain policy POJO. Политика
   wire/schema default принадлежит этим моделям, не генератору.
2. Authored intent сохраняет placement_specificity=None как auto;
   явные 0/positive значения сохраняются без truthiness fallback.
3. PolicySpec ссылается на непосредственное поле domain policy POJO
   через типизированный FieldRef. Исполнитель читает **экземпляр POJO**,
   включая его явный schema default; definition не копирует это число
   в отдельный литерал или собственную таблицу.
4. Общий PolicyResolver разрешает authored value, domain default и
   domain-defined cases по §6.8. При отсутствии авторского значения и
   значения у **корректно разрешённой** domain policy использует terminal
   источник `PlacementPolicyDefaults.placement_specificity=0`.
   Этот defaults POJO — единственная SoT общего fallback, также читается
   через FieldRef; `or 0`/`.get(...,0)` в resolver/adapters запрещены.
5. PolicyDecision содержит effective priority и provenance. P2 читает
   ровно это решение для eligibility/очереди. Generic 0 → no creation;
   positive → сравнение после готовности обязательных опор.
6. Только accepted outcome попадает в ResolvedWaterPlacement/spec/writer.
   Default, использованный лишь при normalize, но не дошедший до policy
   decision/queue, считается неимплементированным контрактом.

**Не делать два SoT.** Существующий PreparedPlacement.auto_specificity
может быть промежуточным compatibility transport при переключении, но
не вторым источником независимо вычисленного priority. G0-P закрепляет
единый authoritative decision/source pointer; старый effective property
не должен перекрывать живой POJO default своим локальным расчётом.

**Fallback не скрывает ошибки.** Invalid priority, неизвестная обязательная
policy reference, отсутствующий required source/context, несогласованные
cases и неизвестный required fact → typed unresolved/error, не 0.
None до завершения resolution означает ожидание/отсутствие значения;
0 после корректного terminal fallback — resolved disabled decision.
Authored/domain explicit 0 — тоже disabled, но provenance отличается
от fallback. Категория с default 0 действительно выключает создание;
не менять значение на 1 внутри adapter ради совместимости.

**Provenance.** Источник решения отражает authored поле, domain POJO
поле/default, terminal defaults POJO либо сработавший policy case.
Закрытые виды источников оформить enum в общих policy контрактах;
имена полей берутся из typed FieldRef binding, не из consumer strings.
Это позволяет отличить реально прочитанный default от fallback 0.

**Проверки против мёртвого кода — обязательны:**
- При omitted/null authored priority результат равен default выбранного
  domain POJO; тест не подсовывает уже вычисленное auto число, а проходит
  production provider → общий PolicyResolver → P2.
- Изменение только default в test policy POJO меняет effective priority
  и при конкуренции — исход placement, без изменения resolver/adapter.
- Явное authored значение побеждает default; authored 0 не заменяется
  положительным domain default.
- Корректная policy без значения приводит к fallback 0 и отсутствию
  spec/carve; provenance указывает terminal defaults POJO.
- Две категории с одним полем placement_specificity, но разными POJO
  defaults разрешаются одним engine с разными результатами.
- Invalid/required source failure остаётся unresolved, не маскируется
  fallback. Runtime/preview и full/partial совпадают.
- Интеграционный тест доказывает, что старый auto_specificity transport
  не перекрывает источник POJO; один source of truth на всём пути.

### 6.10 Целевая реализация procedural source search — fine/L2

Зафиксировано по прямому указанию мастера: coding agent реализует поиск
самой высокой допустимой вершины **на world-fine XY grid L2**, а не
оставляет текущий coarse search, меняя единицу radius. Ниже обязательный
target для отдельного HY-RIV-1; GEO-1 предоставляет готовые body/terrain
входы. Реализация всего river track попутно в GEO-1 не разрешается.

**1. Координаты и область поиска.**
`source_search_radius_fraction: ExtentFraction` — доля extent; эффективный
радиус extent_radius_fine(fraction, extent) в world-fine XY cells.
Метрика — shortest XY distance через topologyGeometry.dist2 на fine
topology, включая wrapped/sphere. Для принимающего тела caller передаёт
`FineReceivingWaterline`: canonical fine клетки его фактической waterline,
уровень и source/body identity из одного body snapshot. Waterline не
заменяется центром, bbox, coastline declaration или центром coarse клетки.
Она выводится из final basin fill и согласованной fine поверхности,
с ограничением extent принимающего тела; global z<level недостаточно.

Для fine кандидата c: d2(c) = min(dist2(fine_topology,c,w)) по клеткам
принимающей waterline; область включает ровно c с d2(c) <= radius_fine².
Радиус не длина русла и не D8-count. radius_fine — производное
extent_radius_fine(source_search_radius_fraction, базовый extent);
база — extent принимающего тела из RegionCoverage accepted placement,
при отсутствии региона — resolved topology extent мира. Default
fraction=0.25 зафиксирован в rivers POJO; radius остаётся обязательным
resolved input по POJO policy. Missing input не заменяется 200 из mouth
policy и не становится скрытым coarse radius.

**2. Владелец fine высот — terrain. Точное место extraction.**
Существующий [TerrainBatchOrchestrator.build_tile_surface_state](../../backend/app/application/worldData/materialize/terrainBatchOrchestrator.py:112)
строит L2 heightmap: parent-light upsample/detail noise, terrain carry,
region paint, hills, hydrology overlays. Отсюда выделить pure
terrain-owned базовую часть в
`generators/terrain/passes/fineSurfaceBase.py::build_pre_river_tile_surface`.
Порядок базовой части фиксирован: parent light z + ParentLightRefinePolicy
detail/clamp → categorical terrain/facing carry → region paint → hills.
Данные water bodies, необходимые для исключения hills из воды, берутся
из basin-only pre-river snapshot. River bed/river mask/fine river overrides
в эту функцию не входят. Требование не запускать mill сохраняется.

`generators/terrain/sampling/fineSurfaceSampler.py::TerrainFineSurfaceSampler`
предоставляет `sample_window(window, snapshot) -> FineSurfaceWindow` и
`iter_windows(region, snapshot)`. Он вызывает ту же pure базовую функцию,
что обычный L2 materialize, а не копирует формулу высот в hydrology.
Типы `PreRiverTerrainSnapshot` и `FineSurfaceWindow` — frozen dataModel
terrain sampling contracts с явными world/snapshot/topology/scale identity.
FineSurfaceWindow содержит fine surface_z и typed terrain/material/support
facts, необходимые для domain policy; не raw wire.

Upsample/hills считаются на полных canonical L2 tiles с нужными соседями,
затем provider возвращает запрошенное окно. Нельзя строить hills только
на clipped search-window: текущий hill placer использует входную область
для origins/whole-footprint admission, и clipping поменяет вершины.
World topology управляет seam/halo. Window — способ доставки данных,
не вход, влияющий на terrain generation. Доступность уже сохранённого L2
не влияет на ответ: read cache допустим только при совпавшем snapshot.

**3. Snapshot и отсутствие river feedback/cycle.**
PreRiverTerrainSnapshot создаётся после accepted basin relief/fill,
до **любого** river bed carve данного generation revision. Включает
версию родительской L0 базы без river contribution, terrain masks/region
state, refine policy и seed, basin water facts/уровни, topology/bounds.
Текущий готовый SurfaceTerrainContext с уже выполненными реками не может
быть входом такого provider: split фаз обязателен в HY-RIV-1.
Порядок: basin planning/fill → frozen terrain/body base → bounded fine
sampling → source selection/common dependent placement → river routing/
spec emission → single relief river writer → river roles/overlays.

Обычный L2 materialize обязан строить ту же pre-river базу и затем
применять готовые river overrides/roles. Не генерировать повторно hills
по маске, уже изменённой этими реками; не искать исток по post-bed terrain.
Final L0 river output не становится входом той же pre-river базы.
В HY-RIV-1 отдельным ранним шагом закрепить хранение/доставку revision
этой базы и overlays в pack/caller contract: без неё production wiring
нельзя объявлять готовым. Нельзя заменить это чтением произвольного
старого L0/L2 или ручным восстановлением coarse значений в гидрологии.

**4. Конкретные river классы и методы.**
`rivers/sourceSearchRegion.py::build_source_search_region(receiver,
resolved_policy, fine_topology) -> FineSourceSearchRegion` готовит
геометрическую область/halo; она не выбирает вершину и не пишет terrain.
`rivers/fineSourceSearch.py::FineRiverSourceSearch.find(receiver, region,
surface_sampler, snapshot, policy_decision) -> RiverSourceSearchResult`
проходит все fine клетки области и использует общий policy engine
для допустимости кандидатов по supplied typed facts. Hydrology задаёт
истоковые частные случаи/параметры, не пишет второй policy resolver.
`RiverSourceCandidate` содержит canonical fine xy, z, distance²,
receiver source/body identity и snapshot identity. Result явно различает
найденных кандидатов и отсутствие допустимого source; fallback к coarse
max/source координате без диагностик запрещён.

Fine-кандидат — максимум по D8 соседям fine поверхности этого snapshot;
для проверки брать fine halo минимум в одну соседнюю клетку за границей
области поиска. Halo клетки не становятся source candidates вне radius.
Равновысотные plateau клетки допустимы по одному и тому же предикату;
из них выбирается ближайшая к receiving waterline, затем canonical
координата. Новую случайную сортировку истоков после ранжирования не делать.
Минимальная высота/тип поверхности/иные eligibility constraints должны
быть объявлены domain policy POJO/rules, не локальными константами поиска.

**5. Порядок выбора и placement.**
Для каждого receiver допустимые кандидаты упорядочены:
(-z, distance² до его waterline, canonical y, canonical x).
Самый высокий в radius первый; при равной высоте ближайший, затем
стабильный canonical tie. Предпочтение вариантов хранится в существующих
PlacementCandidate.preference/candidate identity по этому рангу;
это не новая шкала object placement_specificity.
Source intent имеет dependency на принимающее тело и передаётся общему
resolver в fine working-grid phase=dependent. Common policy priority=0
не создаёт источник, positive не обходит support/geometry constraints.
Невозможность реального river route остаётся явным downstream результатом;
alternative source, если policy разрешает retry, берётся из того же
упорядоченного fine набора, без пересчёта base/seed/ранга по post-carve.
Полный routing/retry контракт описывает HY-RIV-1 до реализации writer.

**6. Ограниченность и детерминизм.**
Обход streaming по canonical tiles/windows, без хранения fine heightmap
всего мира. Нельзя использовать top-K coarse maxima как окончательный
отсев fine области: это может пропустить настоящий fine maximum.
Coarse index допустим только для conservative enumeration области,
не для выбора source z/xy. Full/partial bake и worker count не меняют
receiver set, область, sampled heights или selected source. Resource cap
не может незаметно усечь область/выдать неточный maximum: при превышении
утверждённого лимита — typed resource diagnostic, не другой source.

**7. Обязательная приёмка целевой реализации.**
- В одной coarse клетке две fine вершины: выбирается более высокая,
  а не coarse center. Fine вершина с меньшим coarse background может
  победить более высокий coarse maximum после actual L2 detail/hills.
- Одинаковые fine z → ближайшая к receiving waterline; полный tie
  стабилен. Вершина за radius исключена, halo не сокращает поиск.
- Source xy/z равны высотам обычного L2 provider до river overlays;
  проверяются region paint, hill contribution, noise/clamp и seams.
- Pre-existing/post-carve river data не меняют base/source на re-bake.
- Отсутствующий cached L2 не меняет решение; свежая генерация и cache
  одного revision совпадают. Нет hidden coarse fallback.
- Full/partial, разбиение windows, порядок tiles и workers дают один
  source/receiver identity; peak на границе окна не теряется.
- Declared fine-river/mouth pipeline regression проходит; radius
  источника не подменяется mouth_search_radius_fine.

**8. Порядок работ отдельного HY-RIV-1.**
R1: ТЗ фаз и frozen pre-river snapshot/parent-base revision contract.
R2: выделение pure terrain fine-base builder и sampler, L2 parity tests.
R3: typed source radius/receiver/search-region contracts, policy cases.
R4: FineRiverSourceSearch с exhaustive bounded fine scan/halo/ranking.
R5: общий dependent placement source intents и fine routing/retry seam.
R6: переключение procedural producer с coarse find_river_sources,
single writer/overlay доставка в L0/L2, re-bake/full-partial приёмка.
Каждый — отдельный проверяемый шаг; этот список развернуть в отдельный
delivery-план HY-RIV-1 перед кодом. Текущий coarse producer сохраняется
до атомарного cutover R6, но не считается выполнением fine target.

### 6.11 Unknown shore support: validation error / runtime fallback error

Принято мастером 2026-10-22. Неизвестная допустимость — не запрет по
доказанной отвесной породе и не разрешение. Terrain-owned provider
возвращает typed unknown с причиной/недостающими facts. Общий policy
resolver разрешает domain-defined case и сохраняет provenance; режим
обработки задаёт переданный ResolveContext, не содержимое world JSON.
Hydrology не выводит cliff/material самостоятельно и не меняет решение.

**Validation мира:** existing validate_only pipeline получает
FieldPathError с domain enum code `SurfaceCoatingIssueCode.UNKNOWN_SUPPORT`
(wire-представление кода определить в G0), точным source/settings path,
world/body identity, fine cell/face и причиной отсутствующих данных.
Факт идёт через report_issues в ResolveReport/ImportValidationReport;
результат проверки valid=False, а не valid=True с молчаливым skip покрытия.
Preview не пишет БД/Pack и не наносит fallback coating. Проверка использует
тот же terrain facts provider в памяти; отсутствие готового cached L2
не ошибка само по себе. Error возникает, если обязательные facts нельзя
разрешить общим read-only provider по валидируемому world snapshot.
В G0/G9-S добавить вызов этого доменного check в read-only world validation
boundary; нельзя ограничиться runtime тестом и объявить validation готовой.

**Runtime:** unknown сохраняется диагностируемым фактом. Разрешённый
fallback — оставить исходные terrain и material вместе, сохранить
hydrology SHORE/body UID/level, пропустить только береговое покрытие.
Не выдавать unknown за доказанный policy-запрет покрытия (forbid) и
не считать поверхность установленным cliff. Независимый materialize
продолжается. Обязательная структурированная fallback error содержит
тот же code/path/world/body/cell/reason плюс выбранное действие
KEEP_EXISTING_SURFACE (typed domain fallback enum, не consumer string).

Проверено существующее окружение: отдельного класса FallbackError
в backend/app нет. Использовать existing FieldPathError → log_issues
(WarningError), не создавать параллельный logger/error framework и
не выдавать новое имя класса за существующее. Различать normal
canonical default (обычная policy) и fallback из-за unresolved фактов.
Валидационный и runtime sinks не меняют критерий допустимости/геометрию.

**Приёмка G9-S:** на одинаковом world snapshot одинаковый typed unknown;
validate_only даёт valid=False с конкретной ошибкой, без writes;
runtime даёт WarningError с fallback action, исходные terrain/material
и роль SHORE сохранены; proof-cliff даёт обычный запрет coating без
unknown-error; cache miss с доступной pure генерацией facts разрешается
нормально, не трактуется как отсутствие данных. Никакого hidden success
при неизвестном результате и никакого нового cliff heuristic в hydro.

### 6.12 Все runtime fallback: обязательный существующий project logger

Уточнение мастера 2026-10-22. Требование относится ко всем fallback,
которые выполняются в рамках данного плана: policy/default priority,
generation defaults, degraded geometry/support, shore unknown и иным
согласованным runtime fallback. Возврат fallback value/action без
штатной диагностической записи — незавершённая реализация.

**Единственный logging stack, уже реализованный:**
- [docs/tz_logging.md](../../docs/tz_logging.md:16) — SoT sinks: общий
  facade, domain/service routing, JSON, console queue, generation transcript.
- [core/loggingConfig.py::setup_logging](../../backend/app/core/loggingConfig.py:365)
  настраивает root/domain file router/очередь console/JsonLogFormatter.
  Consumer не вызывает setup_logging повторно и не меняет handlers/level.
- [jsonValidation/resolve.py::log_issues](../../backend/app/application/jsonValidation/resolve.py:94)
  и report_issues — существующий policy/resolve emitter. Ошибочный
  runtime fallback публикуется как FieldPathError через этот маршрут
  с WarningError, не отдельным logging.getLogger/print для того же события.
- Existing route loggingConfig.py для app.application.jsonValidation
  пишет в `backend/logs/jsonValidation/resolve.log`. При активном
  generation_world_log тот же record штатно входит в transcript:
  [generationLogging.py](../../backend/app/core/generationLogging.py:33)
  уже включает namespace app.application.jsonValidation. Второй emit
  ради transcript запрещён.

**Кто и когда пишет:** domain provider/общий PolicyResolver возвращает
typed decision/issue с причиной и provenance; владелец runtime boundary
публикует его существующим emitter ровно один раз при применении fallback.
Consumers не проглатывают issue и не создают второй error-log о том же
решении. Если ctx/report используется для dispatch, не вызывать затем
log_issues повторно для уже опубликованного issue.
Обычное наследование authored значения — не fallback. Штатный terminal
default отражается существующим cascade default_applied/source logging
с уровнем, заданным общим механизмом; не выдавать его за аварийную ошибку.
Fallback из-за unresolved/неполных фактов обязательно WarningError.
Default, не проходящий через cascade, также должен получить provenance
и штатный policy/default event, не остаться немым из-за другой boundary.

**Содержимое записи:** enum code/reason, world/snapshot identity,
domain/source/body identity по месту, field/source path либо cell/face,
недостающий/невалидный вход, применённый fallback/default/action и его
источник. Значения/enum читаются из typed POJO/decision, не добавляются
raw wire dictionary или локальным литералом в consumer. Не логировать
весь world payload вместо конкретных facts.

**Validation:** те же факты идут в existing ResolveReport; обязательная
ошибка не скрывается runtime fallback. validate_only не выполняет
fallback materialize и не считается runtime logging path. Обычная
server/request диагностика остаётся у общего facade, не нового handler.

**Запреты:** новые FileHandler/StreamHandler/basicConfig, собственный
fallback logger framework, новый общий app.log, прямой print/tee,
обход существующего domain helper и двойная запись того же события.
Соблюдать existing dedup/volume policy tz_logging: не создавать per-cell
stdout storm; группировка обязана сохранять scope/count/причину и
выбранное действие, не удалять сам fallback факт.

**Обязательные проверки:** runtime fallback действительно доходит через
existing emitter до configured facade/domain sink; typed context/action
присутствуют; нет второго вызова ради generation transcript. Покрыть
generic policy fallback 0, default source и shore unknown. Preview
возвращает явный issue без runtime fallback materialize. Tests используют
capture/test-config existing logger, не пишут произвольные файлы production
логов. Проверки provenance без проверки реального emission недостаточны.

### 6.13 Реестр design gaps: итоговая проверка TARGET

Статус на 2026-10-22 после §6.25–6.29: 11 DESIGN_CLOSED и один
EXTERNAL_GATE. DESIGN_CLOSED означает конкретный проверенный design,
не реализованный/tested код. Перечень ниже — полный; краткие списки
§5.4/старых audit не заменяют его. Runtime acceptance остаётся §7.

- GAP-POLICY — DESIGN_CLOSED, §6.29-C. Shared dataModel/policy и
  application/policy; finite predicates/effects, typed refs, precedence,
  mode/fallback и truth table. G0-PT/G0-PE реализуют эту схему.
- GAP-CASCADE — DESIGN_CLOSED, §6.29-A. Источники WORLD/CATEGORY/BODY,
  sea/ocean/lake binding и legacy normalize без второго SoT. G1/G2/G3.
- GAP-SOURCE — DESIGN_CLOSED, §6.29-B/L. Discriminated source union,
  procedural source без fake geometry, metadata→factory. G3/G4/G4-C/
  G5/G5-C2/G6/G7/G8 используют один этот контракт.
- GAP-FIELD — DESIGN_CLOSED, §6.29-F. Formulas/defaults/units, topology
  embedding, threshold/ties и absolute floor profile→existing writer.
  G6/G7/G7-C/G9; второй z writer не нужен.
- GAP-AREA — DESIGN_CLOSED, §6.29-E. Terrain-owned exact fine-cell measure,
  union spans, integer allocation cap и post-fill actual. G3-R/G4-P/G10-R.
- GAP-PHASE — EXTERNAL_GATE HY-RIV-1 R1/R2, §6.29-K/§6.10. Handoff types
  и запрет coarse fallback заданы; extraction pre-river base/manifest
  lifecycle делается отдельным river track. GEO-1 G11 не закрывает его
  реализацию и не блокирует свою delivery ожиданием river replacement.
- GAP-CUTOVER — DESIGN_CLOSED, §6.29-J. Contracts-only ранние шаги,
  один G10-A production switch, domain defaults/nullable channels/old
  gate removal одновременно. G0-P до него не включает zero на old0.
- GAP-VALIDATION/LOG — DESIGN_CLOSED, §6.29-I/§6.12. Aggregate draft hook,
  standalone update orchestration, severity matrix и real INFO sink
  acceptance; error не исчезает при runtime fallback. G9-S/G10/G11.
- GAP-SNAPSHOT — DESIGN_CLOSED для GEO-1, §6.25/6.28/6.29-K.
  Exact frozen input closure, content revision отдельно от opaque UID,
  cache key/ref/publish guard и future Patch/WorldSnapshot source seam.
- GAP-BOUNDARY — DESIGN_CLOSED, §6.29-G. Accepted-source→final physical
  many-to-many mapping, dry/missing distinction, derived dependent output
  и bundle consumer. G5-C3/G10; без новой persisted entity.
- GAP-SURFACE — DESIGN_CLOSED, §6.29-H/I. Geometry+typed substrate evidence,
  общий rule engine, known/unknown matrix и read-only producer. G9-S.
- GAP-OUTCOME — DESIGN_CLOSED, §6.29-C/D. Early header без geometry,
  три конечных outcome, uniform identity и multiple-cause propagation;
  один existing DependencyQueue. G0-P/G5-CP.

Post-freeze supplement §6.32 (2026-10-23) — не новый gap реестра:
design fingerprint формул остаётся DESIGN_CLOSED выше; находка при
подготовке PC-4 касалась только отсутствия исполняемого encoder,
типа schema manifest и шага-владельца. Закрыто размещением общего
canonical codec и шагом PC-3E.

Проверка стыков — §6.28 и §6.29-L. Переход к implementation требует
нормативного G0/PC-0 sync и приёмки prerequisites §7; положительная
проверка текста не подменяет будущие executable type/regression suites.

### 6.14 Порядок проверки закрытых контрактов

Сначала нормативные G0/G0-A/G0-S/PC-0 sections по frozen schemas.
Затем neutral UID/geometry/immutable input types, common cache/planning,
production baseline PC-12. Далее shared policy/source/cascade/strategies
contracts-only и один G10-A cutover. Конкретные схемы не выбираются
повторно при coding; новый найденный mismatch требует явного plan diff.
HY-RIV-1 R1/R2 остаётся внешним track с интерфейсом §6.29-K.

### 6.15 Snapshot: совместимость с общей системой патчей

**SoT и статус.** Проверены
[tz_patch_system.md](../../docs/tz_patch_system.md:9),
[tz_world_snapshot.md](../../docs/tz_world_snapshot.md:9) и
[tz_world_pack_storage.md](../../docs/tz_world_pack_storage.md:119).
Patch System — target design; WorldSnapshot runtime service в ТЗ ещё
не реализован. GEO-1 готовит границу замены, не объявляет общий runtime
готовым и не создаёт его локальный аналог ради terrain.

**Разные сущности.** Общий WorldSnapshot — authoritative состояние
мира/сессии; capture/restore/branch принадлежат платформе. TerrainRegionsSnapshot,
pre-relief/pre-river views — производные immutable вычислительные входы
с явной фазой/масштабом, а не world snapshot на ход. Phase snapshot_uid
идентифицирует view, но не доказывает актуальность данных и не является
world snapshot_id, turn_id, patch revision или checksum.

**Одна граница подготовки входа.** После подготовительного PC-блока
request owner — planning/composition/surfacePlanningEntry.py::SurfacePlanningEntry,
pure projection — surfacePlanningCapture.py::SurfacePlanningCapture,
сборка фаз — surfacePlanningAssembler.py::SurfacePlanningAssembler.
Все три пути относительно application/worldData/. Existing методы
capture_view/prepare_captured вызывают capture/prepare; GEO target методы
capture_geo_view/prepare_geo_captured/require_geo_plan_inputs вызывают
capture_geo/prepare_geo по §6.16-A. Legacy context/projector удалён PC-11.7,
не делегирует и не восстанавливается. Caller получает coherent world/locations,
region states/claims и loaded library members до capture; workers/providers
не читают live World/SQL/Patch Store и не захватывают новую view.
Assembler получает frozen view, не authoritative store и не capture callback.

**G0-S: exact ready source closure (target GEO schema).**
GeoSurfacePlanningView находится в planning/contracts/surfacePlanningView.py,
не наследует invariant baseline payload поля. Required fields:
kind=READY, world_uid:EntityUid, revision:StateViewRevision,
climate_base:ClimateBaseInput, terrain_base:TerrainBaseInput,
region_input:TerrainRegionPlanningInput, water_placement:GeoWaterPlacementInput,
relief:ReliefPlanInput, hydrology:GeoHydrologyPlanInput,
river_relief:RiverReliefInput, hydrology_final:HydrologyFinalInput,
climate_local:ClimateLocalInput, boundary_input:CoastlineBoundaryInput,
surface_support:SurfaceSupportInput, coating_input:CoatingPlanInput,
capture_diagnostics:tuple[PlanDiagnostic,...]. Exact domain fields — §6.28,
§6.29-M/§6.31-E; это authored inputs, не results policy/placement/fill.
World bounds/topology/grid/z bounds согласованы между I, required refs
проверены до build; ordered source collections не превращаются в set.

SurfacePlanningCapture.capture_geo(world:World,locations:Sequence[NamedLocation],*,
mode:ResolutionMode,region_states:tuple[RegionState,...],
relief_templates:tuple[tuple[EntityUid,ReliefTemplate],...],
region_claims:tuple[RegionGeometryInput,...],
mountain_templates:tuple[MountainTemplateInput,...],
resolve_ctx:ResolveContext) → GeoSurfacePlanningView|NoExtentSurfacePlanningView.
Все дополнительные sources required: caller явно передаёт empty tuple для
отсутствующей коллекции, не получает synthetic fallback при failed read.
Membership/member UID и actual template body, states/tombstones/fingerprint,
coverage/owner_ref claims входят в соответствующие immutable inputs.
mode должен совпадать с ctx.validate_only. NoExtent сохраняет existing
kind/world_uid/revision/diagnostics: prepare_geo возвращает None, require
выдаёт existing unavailable error; fake topology/geometry/provider builds нет.

До платформенного cutover источник — согласованные typed inputs текущего
caller. После него тот же projection boundary получает восстановленное
состояние/working state и метаданные по общему snapshot/patch контракту.
Меняется получение input и operation provenance, не domain I/algorithms.
Актуальный внешний план — world-domain-patches-snapshots.md §6–7.2;
world-state-crud-transition.md архивирован, его central read/CRUD contract
не вводится. Domain read/patch implementation владеет своими результатами,
Snapshot инициирует применение и согласованный commit. Concrete revision-set/
holder/storage/apply API остаётся внешним freeze; GEO-1 не выдумывает tokens,
не реализует source-version store или локальный snapshot service.

**Revision и cache — одна existing реализация.** StateViewRevision,
InputFingerprint и OutputFingerprint — разные existing 32-byte nominal types.
Для READY Geo view input tuple P имеет ровно следующий порядок:
(climate_base,terrain_base,region_input,water_placement,relief,hydrology,
river_relief,hydrology_final,climate_local,boundary_input,surface_support,coating_input).
S(P) — tuple declared model fields (name,value) каждого I, кроме fields
с metadata SourceFieldRole.EXECUTION_POLICY. revision =
StateViewRevision(digest((world_uid,S(P)),GEO_SURFACE_MANIFEST)); digest —
application/encoding/canonicalCodec.py (SHA-256 canonical TLV v1).
GEO_SURFACE_MANIFEST — binding declaration в existing planning/encoding/
surfaceManifest.py с registered Geo types; не отдельный encoder.
Existing NoExtent projection остаётся (climate_base,climate_local), без
придуманной ready view. Baseline PC revision/vectors не переписываются.
ResolutionMode исключён из source revision по field metadata, но включён
в actual request I/input fingerprint; ClimatePoleMode — authored input,
не execution policy. Display labels/current_tick/timestamps и request-local
capture diagnostics не попадают в planning source revision. Различия None/0/False,
source identity, declared geometry, semantic policy/registry/default values,
claim refs, region state и template membership/body сохраняются.

Canonicalization по существующему codec: declared record field order,
set/frozenset по encoded bytes; unordered unique-key registries/anchors/template
rows/claims/states сортируются по canonical UID/key, grid rows по (y,x), light
по (gy,gx,ty,tx). Ordered paths, manual climate poles и first-match sequences
сохраняют порядок; их перестановка не называется equivalent. Duplicate keys,
nonfinite values, wrong enum/type/space и неканоничные refs rejected.
Не использовать repr/pickle/Python hash или JSON app.ids.state_fingerprint
вместо frozen codec. UID/seed helpers app.ids сохраняют свой existing scope.

Artifact formulas остаются в application/planning/service/planFingerprints.py:
F_in=digest((contract_id,schema_version,algorithm_version,world_uid,scope,I,deps));
F_out=digest((payload,deps,diagnostics)); cache_item_key=digest(PlanKey).
deps — unique tuple, sorted by slot, с exact PlanRef.key/output_fingerprint;
I сохраняет execution policy. Schema/algorithm берутся из registered handle:
PC=1/1, изменённые GEO I/T=2/1, unchanged handles переиспользуются (§6.31-E).
View revision не заменяет per-artifact closure: unrelated edit допускает HIT
неизменного upstream. SourceRevision(seq+content_hash) внешнего revision store
и snapshot/parent identity — provenance/state binding, не эти fingerprints.
Равные effective inputs разных pinned sets могут использовать один derived
artifact; authoritative revision set/branch provenance не теряется и не
выводится из равенства cache entry. Сам cache current pointer не хранит.
Нельзя считать одинаковый world/phase UID, turn number или pack hash
достаточным cache key при изменённых settings/patches/region states.
Внешние snapshot/patch tokens после cutover поступают от их владельца,
не синтезируются terrain. Для текущего запуска они не выдумываются ради
заполнения ещё отсутствующего platform API. Существующий manifest stamp
cache (mtime_ns,size) из WP Read path сохраняет свой контракт; terrain
input fingerprint не заменяет его и не объявляется pack content hash.

**Invalidation/publication.** Edit сначала меняет authoritative input;
новый capture строит expected keys независимо от доставки evict event.
Affected closure следует declared deps: upstream reused, downstream replan;
clear/eviction/restart не меняет UID/seed/geometry. Wrong world/scope/schema/
phase/dependency ref/output digest не становится HIT/empty domain fallback.
Tuple payloads/read-only working projections не позволяют одному consumer
изменить ответ следующего. L0/L2 запрашиваются из coherent bundle, их tile/LOD
не меняет world layout и не создаёт eager materialization после edit.

Existing PC guard sourcePublication.py::SourcePublicationGuard.require_fresh
перечитывает world/locations и re-capture в caller publication UOW;
sourceRevision.py::require_current_source сравнивает world_uid+StateViewRevision.
Это текущая baseline stale-write rejection, не будущий append-only Snapshot
commit protocol. Он сохраняется до отдельного external cutover; capture
не заявляет SQL snapshot isolation всех current источников. Current guard
не перечитывает template repository: operation-wide loaded projections и
membership coherence остаются обязанностью caller. Pinning/GC/историческая
публикация и concurrent edit semantics замещаются source-versioning + новым
snapshot-планом, не ещё одним terrain guard/локальным latest pointer.

**Patch граница.** Generator возвращает typed domain output; domain patch
implementation подготавливает изменение, только Snapshot инициирует apply.
Диспетчеризация/append-only SQL/pack/history commit закрепляются внешним
планом; общий patcher из старого текста не является отдельным apply entry.
При restore authoritative state и удержанные pack refs восстанавливаются
владельцами доменов; patch history не требует replay всего мира ради view.
Pack immutable, gameplay Patch Store overlay сохраняет precedence WP-20;
bake не перезаписывает gameplay edits. Изменение read/write путей —
отдельный согласованный cutover, не побочное действие GEO-1.

Фазовый view выбирает ровно входы своей стадии: pre-hydrology/pre-river
не получает выходы того же carve и не читает произвольный post-carve pack
как базу. Какие authored/gameplay изменения входят в базу, задаётся явной
projection, а не безусловным merge всех текущих overlays; fine split
и доставка pre-river revision остаются GAP-PHASE/HY-RIV-1.

**Приёмка совместимости:** одинаковые resolved inputs текущего caller
и адаптированного общего restored state дают одинаковые views/revision/
placements; изменение значимого effective input меняет revision, перестановка
эквивалентного набора — нет. Старый cache не принимается по одному UID.
Разные branches не смешивают provenance/изменяемое состояние. Проверка
в GEO-1 на typed prepared inputs без требования работающего future service;
реальные capture/restore/branch/patch commit проверяет платформенный трек.
Initial light/full, L0→C23 unpublished inputs, staging и commit границы —
external §7.2; G0-S не объявляет existing WorldPackWriter append-only/Snapshot-owned.
Preview не пишет state/patch/snapshot. В генераторах нет собственного
snapshot storage, patch log, SQL commit или зависимости от player chain.

### 6.16 Явные контракты и точки их схождения

Это обязательный connection ledger G0-A. Пути относительно
`E:/AI Project/backend/app/`, сокращения — §5.4. EXISTING обозначает
проверенный текущий код, TARGET — целевое изменение. На 2026-10-22 все
design gaps §6.13 имеют статус DESIGN_CLOSED (GAP-PHASE — EXTERNAL_GATE):
закрывающие contracts находятся в §6.25–6.29 и указаны в каждой записи.
BLOCKED здесь означает только неисполненную реализацию перечисленных
шагов §7, не отсутствие схемы. Ни один новый transport type/file не
создаётся в обход domain map/composition rule.

**J01. Typed source/settings → cascade.**
Producer: existing application/jsonValidation/worldRow.py::hydrology,
после schema resolve — WorldHydrology и source POJO. TARGET embedded
world/body settings из §4 и category source channels §6.8-D.
Consumer: application/cascade/contextResolver.py::extend(ctx, Link(...)).
Схождение выполняет terrain/designedWater/preparation/designPreparation.py::
prepare_designed_water: ROOT → WORLD → CATEGORY → WATER_BODY, независимый
body context для каждого source. На вход Link передаётся исходный embedded
POJO, не dict проекция; на выходе WaterGenerationContext с provenance.
Ключ сопоставления body context — исходный source_uid/категория; ключи
физического WaterBody ещё не существуют. Контракт: §6.29-A (карта
CATEGORY, generic context compatibility); implementation — G1/G2/G3
(GAP-CASCADE DESIGN_CLOSED).

**J02. Caller input → frozen view/revision/topology.**
Existing request owner: planning/composition/surfacePlanningEntry.py::
SurfacePlanningEntry.capture_view/prepare_captured; pure capture —
surfacePlanningCapture.py::SurfacePlanningCapture.capture, phase assembly —
surfacePlanningAssembler.py::SurfacePlanningAssembler.prepare. После PC-11.7
SurfaceTerrainContext/prepare_surface_terrain_context/to_legacy_context удалены.
TARGET capture_geo/prepare_geo в тех же Capture/Assembler; request owner —
SurfacePlanningEntry, Geo view не проходит через baseline API/cast.
Target методы entry: capture_geo_view делегирует capture_geo с required inputs
§6.29-M; prepare_geo_captured делегирует prepare_geo и связывает working views
существующими domain factories; require_geo_plan_inputs выполняет эту пару один
раз и возвращает (GeoSurfacePlanBundle,SurfaceWorkingMaps), без нового projector.
Consumer: terrain/regions/regionExtent.py::prepare_terrain_regions,
hydrology/placement/waterPlacementPass.py::run_water_placement_pass и
design preparation. Все получают один согласованный input revision,
world_uid, фазу, WorldTopology, coordinate space и coarse→fine scale.
Snapshot identity не заменяет input revision (§6.15). Source current/future
WorldSnapshot адаптируется только здесь. Контракт: §6.28/§6.29-K;
implementation — G0-S (GAP-SNAPSHOT DESIGN_CLOSED для GEO-1).
Не fallback к post-carve data.

**J03. Cascade + domain definition + facts → общее policy decision.**
Producers: J01 WaterGenerationContext;
dataModel/policy/objectAdmissionPolicyDefinition.py::build(bindings);
dataModel/hydrology/policy/hydrologyPolicyDefinition.py::HYDROLOGY_GENERATION_POLICY;
application/policy/declarations/compiler.py::compile_value_policy/compile_admission_policy
(descriptor, explicit source types); placement descriptor — hydrologyPlacementPolicy.py (G5-CP);
hydrology/policy/hydrologyPolicyFacts.py::collect_hydrology_policy_facts.
Единственное схождение rules/facts — application/policy/policyResolver.py::
PolicyResolver.resolve(spec, sources, facts, mode=ResolutionMode) → PolicyDecision.
Consumer до design: prepare_designed_water; consumer dependent admission:
общая placement очередь по J07. Передаются effective priority,
admission state, execution mode через typed specialization, reason и
provenance. Settings boolean не перечитываются после решения.
Контракт: §6.29-C/D (spec/facts/decision schema, staged admission
без геометрии → готовность supports); implementation —
G0-PT/G0-PE/G0-P (GAP-POLICY/OUTCOME DESIGN_CLOSED).
READY должен иметь однозначную стадию; readiness будущей геометрии нельзя
выдать за уже удовлетворённые spatial constraints.

**J04. Region extent + declared union + context → WaterCoverageBudget.**
Producer extent: prepare_terrain_regions → TerrainRegionPlan → plan.snapshot;
prepare_designed_water выбирает TerrainRegionExtent по generation region UID.
Declared coverage union предоставляет terrain/spatial geometry owner,
не hydrology. Схождение: terrain/designedWater/coverage/
waterCoverageBudgetPolicy.py::WaterCoverageBudgetPolicy.calculate(
world_extent, world_context, body_requests, *, authored_union_fine2,
available_auto_area_fine2) → WaterCoverageBudget.
Consumer: сборка WaterDesignInput после budget calculation.
Знаменатель generation_area_fine2 и declared union в world-fine²;
target/declared/residual/excess не подменяют placement original_area.
Контракт: §6.29-E (producer RegionCoverageMeasure, union signature,
allocation); implementation — G3-R/G4-P (GAP-AREA DESIGN_CLOSED).

**J05. Source + ready inputs → WaterDesignInput.**
Join owner: prepare_designed_water; water_source coastline адаптируется
CoastlineWaterSourceAdapter.prepare_source по полной зависимости §5.3-A.
Обязательные поля: source intent/identity и geometry constraints,
WaterGenerationContext, TerrainRegionExtent, BodyCoverageAllocation,
topology/coordinate scale, seed, immutable pre-hydrology view/revision,
authoritative admission. Никакого budget → input → budget цикла.
Consumer: DesignedWaterStrategyFactory.get(resolved strategy enum),
затем выбранный DesignedWaterStrategy.design(input).
Существующие DeclaredBasin/Coastline/Lake не маскируют отсутствие typed
procedural source. Контракт: §6.29-B source union; implementation —
G4/G5/G5-C2 (GAP-SOURCE DESIGN_CLOSED).

**J06. Strategy/field → draft → prepared water entries.**
Producers: четыре design(input) → WaterDesignDraft; noise/plate build
и composer combine → ContinentalField. Contracts находятся в
dataModel/terrain/designedWater/{input,draft}.py и fields/field.py.
Схождение: terrain/designedWater/preparation/placementPreparation.py::
DesignedWaterPlacementPreparer.prepare(input, draft, *, selection_policy)
→ WaterDesignPreparation по согласованному G4-C supplement.
G4-C возвращает geometry/candidates, metadata/profile; G8 связывает этот
результат с admission в единственный WaterPlacementPreparation.
TARGET water preparation переносит source metadata/profile и все policy admission
inputs, включая disabled без geometry; его entries остаются prepared,
не resolved. EXISTING waterTypes.py::PreparedWaterEntry ограничен тремя
declared sources и scalar floor_z; WaterPlacementPreparation содержит
entries/failures/notices и snapshot_revision, но не early disabled payload.
Контракты расширений source/profile/admission transport — §6.29-B/F/D
и §6.28; implementation — G4-C/G8/G0-P (все DESIGN_CLOSED). DataModel
input/draft/result не импортируют application WaterPlacementPreparation:
G4-C возвращает dataModel WaterDesignPreparation; adapter transport собирает G8.

**J07. Подготовка всех sources → один общий placement batch.**
Producer: J06 и сохранённые J03 geometry-free admissions. Existing PC chain:
SurfacePlanningAssembler.prepare → terrain/planning/waterPlacementPlanProvider.py::
WaterPlacementPlanProvider.build → hydrology/placement/waterPlacementPass.py::
run_prepared_water_placement → resolve_placements. Free run_water_placement_pass —
legacy/script boundary, не production join owner. TARGET geo build в том же
waterPlacementPlanProvider.py делегирует prepare_designed_water (G8), а
prepare_geo только связывает envelopes через PlanningService. Единственный executor:
application/worldData/placement/resolver.py::resolve_placements(batch, ctx).
DataModel batch/result — dataModel/placement/{batch,result}.py.
При объединении обязательно совпадение world/input revision/phase,
topology/coordinate space; region_uid уникален. Seed/bounds не меняются
между источниками. Current batch.objects — только PreparedPlacement;
target early input union и outcome identity API — §6.29-D;
implementation — G0-P (GAP-OUTCOME DESIGN_CLOSED).
Только P2 выпускает Resolved/Disabled/UnresolvedPlacement. Queue пересматривает
support readiness, не запускает новый cascade/RNG и не создаёт второй
dependency scheduler. Disabled/failed support не попадают в accepted.

**J08. Batch result + original preparation → ResolvedWaterPlacement.**
Existing join: placement/adapters/water.py::resolved_water_placements(
preparation, result) → tuple[ResolvedWaterPlacement, ...].
EXISTING проверяет world_uid/snapshot_uid и exact prepared equality,
индексирует outcomes по outcome.prepared.intent.identity.region_uid.
TARGET проверяет также revision/phase/space, получает identity общим
outcome API; отсутствие prepared у disabled не является ошибкой.
Prepared equality проверяется для geometry-bearing результата. Только
ResolvedPlacement проецируется в water record; failures/disabled/unresolved
сохраняются в общем batch/report, не исчезают при фильтрации records.
Этот конкретный mapper входит в G0-P/G5-CP/G8 wiring; его нельзя оставить
с assumptions о prepared каждого outcome — контракт §6.29-D/J.

**J09. Accepted water record + metadata → BasinSpec → relief writer.**
Existing join: hydrology/basinSpecFactory.py::basin_specs(preparation,
records, hydrology) → list[BasinSpec]. Current metadata lookup использует
entry.source.location_uid и record.source_uid; TARGET связывает их явным
source identity contract, не предполагает любой auto source NamedLocation.
Metadata kind/liquid/level/profile относятся к тому же принятому placement.
Actual PC writer chain: ReliefPlanProvider.build → _coarse_relief → apply_basin_z
в terrain/relief/planning/reliefPlanProvider.py и bathymetry/basinZ.py;
mountain/ravine effects уже применены до basin writer.
Consumer: terrain/reliefObjects/bathymetry/basinZ.py::apply_basin_z(
heightmap, specs, topology, reserved=...) после apply_relief_objects_z.
Writer получает selected footprint, профиль, уровень и mountain reservations;
пишет высоты один раз. Контракт: §6.29-F profile variants; implementation — G9
(GAP-FIELD DESIGN_CLOSED).
Union geometry/height keys в working-grid units; fine-cell название
существующего placement alias не разрешает ошибочно пересчитать координаты.

**J10. Тот же BasinSpec + post-relief terrain → physical water facts.**
Existing PC consumer: hydrology/planning/hydrologyPlanProvider.py::
HydrologyRoutesPlanProvider.build → planning/assembly/hydrologyRoutesAssembler.py::
HydrologyRoutesAssembler.assemble → hydrology/water/planning/waterBodyPlanner.py::
WaterBodyPlanner.plan. HydrologyGeneratorService.apply — отдельный legacy caller.
Те же specs передаются из water pass и writer, не реконструируются по
post-carve minima. Схождение: hydrology/waterBodyAssembler.py::
assemble_water_bodies(heightmap, specs, topology, policy, ...)
→ AssembledWater(materialized, physical_unions).
HydrologyResult содержит water_bodies, physical_unions и cell_index.
Current materialized.uid_remap — auto alias map, не готовый общий
source→final body mapping. Legacy auto_seas/auto_lakes/category bool gates
заменяются согласованным consumption policy decision — §6.29-J/A;
implementation — G10-A.

**J11. Accepted source + final bodies → dependent coastline.**
Join point по времени — после J10 final fill/merge, до dependent boundary
materialization. Consumer: placement/adapters/coastline/attachedCoastline.py::
AttachedCoastlinePreparer.prepare_boundary, затем общий dependent P2.
Вход: target_source_uid, accepted source placement и authoritative final
WaterBody/PhysicalWaterUnion mapping, wet cells/уровень одной revision.
Source UID не считается physical body UID. Контракт: §6.29-G (SourceBodyMapping, typed boundary result);
production dependent caller/storage — G5-C3/G10
(GAP-BOUNDARY DESIGN_CLOSED). Existing PC HydrologyPlan уже несёт
water_bodies/physical_unions через routes/final envelopes, но ещё не
source_mapping и boundary plan; legacy context для их доставки не создаётся.

**J12. Hydrology role + terrain/material facts → shore surface decision.**
Producers: J10 SHORE/body/level; terrain/relief/surfaceCoatingSupport.py::
surface_coating_support → dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py::
SurfaceCoatingFacts; terrain definition в surfaceCoatingPolicyDefinition.py.
Схождение allow/forbid/unknown — общий PolicyResolver, не hydrology helper.
Existing application consumer для fine columns:
terrain/passes/columnFillPass.py::run_column_fill; прежний вызов
hydrology/shore/shoreProfile.py::apply_shore_surface и отдельная запись
shore material заменяются единым consumption решения для terrain/material.
Unknown не удаляет SHORE. Контракт: §6.29-H/I (facts/decision payload,
L0 counterpart caller, read-only validation hook); implementation —
G9-ST/G9-S/G10-A (GAP-SURFACE и GAP-VALIDATION/LOG DESIGN_CLOSED).

**J13. Final wet union + regions + target → coverage report.**
Producers: J10 фактически wet cells и J04 target/region extent одной
revision. Join/consumer: terrain/designedWater/coverage/coverageReport.py::
build_water_coverage_report(final_water, regions, *, budgets) по §5.2-J.
budgets — обязательное typed сопоставление generation region UID →
WaterCoverageBudget из J04. Это явная передача target, а не повторное
чтение world/defaults. Measure/result schema и result owner — §6.29-E;
implementation — G10-R.
Одинаковая union measure для target/actual, dry SHORE исключён;
отчёт не запускает новый placement/carve.

**J14. Domain issues/fallback → один request report и existing logger.**
Join owner: ResolveContext/ResolveReport исходного caller; одинаковый ctx
передаётся policy/preparation/P2/hydrology и validation counterpart.
Если request ctx не предоставлен, root caller создаёт его один раз;
downstream не получают None для создания собственных независимых reports.
Existing PC providers создают collect_only contexts и возвращают typed
diagnostics; SurfacePlanningEntry/assembler report boundary воспроизводит их
на HIT/MISS. Legacy surfaceTerrainContext удалён; GEO providers сохраняют
этот reporting contract, не захватывают caller ctx в cached payload.
Эмиттер — application/jsonValidation/resolve.py::report_issues/log_issues
по §6.12. Обязательная runtime запись при applied fallback ровно одна;
validate_only не материализует и не логирует runtime fallback.
Severity matrix и validation entry point — §6.29-I;
implementation — G9-S/G10/G11.

**J15. GEO-1 final body facts + frozen terrain → HY-RIV-1 fine search.**
Producer terrain fine base/sampler и receiver facts J10; join —
hydrology/rivers/fineSourceSearch.py::FineRiverSourceSearch.find по §6.10.
FineSourceSearchRegion и FineSurfaceWindow одной pre-river revision/
fine topology; source candidates height-first/distance²/canonical y,x.
Selected intent имеет dependency на receiver и использует общий P2.
GAP-PHASE — EXTERNAL_GATE HY-RIV-1: handoff types и запрет coarse
fallback заданы §6.29-K; lifecycle/base/pack delivery — внешний track.
Это interface отдельного HY-RIV-1, а не реализуемый в GEO-1 producer.

#### A. G0-A: замороженные runtime seams после PC-12 (2026-10-27)

Это нормативное уточнение class/method map, не отчёт об имплементации.
EXISTING paths сверены с кодом; TARGET создаётся только owning G-step,
production consumers переключаются вместе в G10-A. J01–J15 и §6.29 задают
payload schemas; настоящая запись уточняет runtime seams и removal ledger.

**Общий cascade runtime (G1, J01).** Новый dataModel/cascade/runtimeContext.py
содержит frozen BaseModel CascadeRuntimeContext[AxisT:ScopeAxis]: level,
provenance и existing transient _world/_links/_scope_path/_node_results/
_default_sources. Scope-specific значения/provenance типизируются своей осью;
heterogeneous node results остаются private runtime state, не wire/cache.
LocationContext в dataModel/locations/context/locationContext.py наследует
общий контракт с ScopeLevel; его root(world,default_sources=...) и public
поля сохраняются. WaterGenerationContext в hydrology/generation/generationContext.py
наследует его с WaterGenerationScope. Defaults/links snapshots копируются при
extend; siblings не разделяют изменяемые node-results/provenance.
Existing application/cascade/contextResolver.py::{extend,scope_sequence,_check_level}
получают общий контекст, extend сохраняет concrete CtxT на входе/выходе.
_check_bindings(type(ctx)) и cascadeGraph проверяют только параметры данного
контекста/оси. Location-only import-time _check_bindings(LocationContext)
не заменяет runtime проверку water модели. Link/EmptyLink и runtimeChain.bind_chain
переиспользуются; новые water-only resolver/bind_chain не создаются.
Economic materialize/fold bindings сохраняются, water VALUE channels их не вызывают.

**SUPPORT resume (G0-PE/G0-P, J03/J07).** Уточнение API общего executor:
PolicyResolver.resolve(spec,sources,facts,*,mode,resume=None).
resume имеет typed ObjectAdmissionDecision[B,R]|None; допустим только для
той же object-operation/spec/source revision, state=WAITING_SUPPORT и уже
resolved positive priority. При resume ABSOLUTE_GATE/PRIORITY не исполняются
повторно: сохраняются effective priority/provenance, обновляются только
SUPPORT facts, затем при готовности выполняется BEHAVIOR. Другой capture,
operation или отсутствие positive priority — contract error, не fallback.
Binding callback создаётся один раз на PlacementSession.start и удерживает
те же frozen spec/source instances и batch.snapshot_revision. Session проверяет
header identity по своему batch, callback не перепривязывается к свежим inputs;
guard этой operation binding принадлежит caller/session, не generic cache.
Value-selection overload не принимает resume. Это тот же staged engine,
не domain evaluation и не отдельный support scheduler.
PlacementSession.start(batch,*,reevaluate_support) получает request-local
callback с контрактом (PlacementHeader,tuple[PlacementOutcomeRef,...]) →
ObjectAdmissionDecision[Enum,Enum]. Callback связан prepare_designed_water
с frozen spec/sources/prior decision и domain facts provider; вызывает только
PolicyResolver.resolve(...,resume=prior). Session не импортирует hydrology.
После DependencyQueue.settle callback вызывается для новых ready dependents;
missing/failed/cycle и disabled causes обрабатываются по §6.29-C/D. Original
world/settings, cascade и RNG не перечитываются. Новую ready порцию целиком
prepare/submit до следующего heap step; geometry/exclusion — check_candidate.

**Production decision/removal ledger (C3).** Все пути относительно backend/app:
- placement: existing dataModel/placement/prepared.py::effective_specificity,
  application/worldData/placement/resolver.py::_PlacementPass._preflight и
  dependencies.py::DependencyQueue.{_enqueue,settle,fail_cycles}; target
  ObjectAdmissionDecision + lifecycle/session.py::PlacementSession → existing
  queue/constraints.check_candidate. G0-P isolated; old auto_specificity/
  CoastlinePlacementFact/WaterPresence priority branch удаляются в G10-A,
  geometry check и positive ordering сохраняются.
- water prepare: terrain/planning/waterPlacementPlanProvider.py::build и
  hydrology/placement/waterPlacementPass.py::{run_prepared_water_placement,
  _auto_specificity}; target GeoWaterPlacementInput/GeoWaterPlacementPlan,
  build_geo в том же WaterPlacementPlanProvider → designPreparation.prepare_designed_water
  → один PlacementSession/P2. G8 готовит transport; G10-A переключает binding,
  legacy run_water_placement_pass не остаётся вторым active production path.
- water fill: hydrology/water/planning/waterBodyPlanner.py::{plan,_select_specs}
  содержит current enabled/category/autoresolve gates; тот же legacy набор есть
  в HydrologyGeneratorService.apply. Domain descriptor/field metadata → общий
  compiler → spec; spec + typed sources/facts → общий
  value-selection HydrologyGenerationDecision; Geo routes wrapper в existing
  hydrologyPlanProvider.py::GeoHydrologyRoutesPlanProvider.build передаёт решение
  domain assembler/planner. В G10-A оба затронутых caller path читают decision;
  повторные bool gates и competing designed sea discovery удаляются, existing
  waterBodyAssembler.assemble_water_bodies → water/waterMaterialize.materialize_water
  сохраняют fill/classify/merge. Они не выбирают generation policy.
- masks: actual runner pack/bake/lightGrid/maskDomains/runMaskDomain.py::run_mask_domain,
  source collector masks/collection/defaultCollect.py::default_collect. Для
  затронутых water wrappers gate — готовый policy decision (G10-A), не второй
  category_enabled/autoresolve if. Landcover/mountain/ravine/roads и их current
  collector policy остаются вне миграции; общая масочная lifecycle не дублируется.
- shore: terrain/passes/columnFillPass.py::run_column_fill сейчас отдельно
  вызывает shoreProfile.apply_shore_surface и пишет shore_material; L0 counterpart —
  pack/bake/lightGrid/contributors/hydro/{declaredBasins,coarseOpenWater,raster}.py,
  entry HydroContributor.apply. TARGET SurfaceCoatingSupportProvider/CoatingPlanProvider
  в terrain/relief/surfaceCoatingSupport.py → общий PolicyResolver → CoatingPlan.
  G9-ST/G9-S готовят facts/decision, G10-A оба L0/L2 caller применяют готовые
  terrain/material targets без local allow/default/unknown overrides. SHORE/body/level
  остаются hydro facts, не зависят от разрешения coating.
- соседние механизмы: cascade/contextResolver.extend сохраняет inheritance;
  worldData/regions/coverageResolver.py::resolve сохраняет
  EligibilityRule scoring; economy/materialPolicies/{defaultMaterialPolicy,
  materialPolicyConsumer}.py::{default_material_policy,MaterialPolicyConsumer.decide}
  сохраняют economic selection/comparison. Их перевод на общий policy — внешний
  migration scope; G0-PE не объявляет их уже мигрированными и не копирует scoring.

**Остальные named joins.** Source union/metadata — §6.29-B в hydrology/sources/
{proceduralWaterSource,waterDesignSource,waterSourceMetadata}.py; J05 передаёт его
strategy factory, J08 mapper читает uniform outcome.identity (G0-P/G8/G10-A).
Fill mapping producer — water/waterMaterialize.py::materialize_water; routes
сохраняет его, GeoHydrologyFinalPlanProvider переносит без повторного fill
(§6.31-E). Existing HydrologyFactsAssembler.assemble уже переносит bodies/unions.
AttachedCoastlineAdapter.build в placement/adapters/coastline/attachedCoastline.py
получает CoastlineBoundaryInput и exact final GeoHydrologyPlan ref, вызывает
AttachedCoastlinePreparer.prepare_boundary → dependent P2 → CoastlineBoundaryPlan;
SurfacePlanningAssembler.prepare_geo доставляет envelope L0/L2 (G5-C3/G10).
Empty accepted mapping=dry, missing entry=contract error; body UID не source UID.

**Validation и publication joins (G9-S/G10-A).** Existing WorldBundleService._prepare_bundle
в application/worldBundle/worldBundleService.py вызывает handler.validate_section
и затем проверяет ctx.errors; LocationsSectionHandler в entity/sections.py сейчас
только валидирует _from_wire results. TARGET transient draft сохраняет эти typed
NamedLocation и library bodies, не парсит их вторым raw consumer; после всех
section validations injected SurfacePlanValidator.validate(view,bundle,ctx=...)
делает pure aggregate check до ctx.errors, без DB/Pack fallback.
Standalone existing application/worldData/registries/worldService.py::{create,
_update,import_from_json,edit_region} сходятся у _save/row preview. TARGET
planning/validation/worldSurfaceValidationOrchestrator.py::WorldSurfaceValidationOrchestrator.validate
— async entry (world,*,ctx)->None: один coherent repository/UOW read locations
для edited world, тот же capture/validator до save/reconcile; validate_only
ветка edit_region тоже проходит check до return. prepare_import остаётся pure.
Bundle/standalone не запускают repository aggregate check у каждого _save.
Existing WorldCopyImport.run пишет world → libraries → entity rows в одной
DB transaction; final library member_map известна только после common writer.
Поэтому source preflight не выдаётся за проверку уже remapped target draft.
TARGET WorldBundleService._prepare_bundle возвращает existing normalized bundle
transport вместе с validated source receipt; import_bundle передаёт receipt
required keyword surface_draft в WorldCopyImport.run. После выбора target UID
run входит в WorldSurfaceValidationOrchestrator.bundle_write_scope(target_world_uid,
source_draft) ВНУТРИ существующей DB transaction и до world handler import.
Это request-local async context manager, сбрасываемый в finally.
WorldService._save внутри scope сверяет target world UID, откладывает aggregate
check до конца bundle и не читает incomplete location store. После library
member remap/всех entity imports выход scope выполняет тот же validate для
coherent final target world/locations/members внутри UOW ДО commit; mismatch
или validation failure откатывает world/library/entity записи вместе.
Policy-required/failure unwind не коммитит и не публикует receipt успешного target.
Source preview и final copied target — разные revisions/compute runs; final
capture не происходит на каждом row/cell. Вне scope standalone validate читает
coherent locations и выполняется до save/reconcile. Public skip_validation bool нет.
Receipt — frozen application record ValidatedSurfaceDraft(view:GeoSurfacePlanningView,
bundle:GeoSurfacePlanBundle|None) в target planning/validation/surfacePlanValidator.py;
world UID/revision читаются из view, не хранятся вторым значением. Создаётся
только после успешного validate, не сериализуется в JSON/Pack/cache.
Source receipt получается из той же section preparation, сохраняющей typed
world/locations/library draft, без нового raw schema parser. bundle_write_scope
принимает только validated source receipt и target UID операции; final validation
не использует source UID refs как доказательство target revision. Это application
operation scope, не snapshot API/новый store.
Container wiring — core/container/{worldData,worldBundle}.py. Runtime diagnostics
идут existing assembler/report_issues/log_issues boundary; publication остаётся
SourcePublicationGuard, а не PolicyResolver/CacheService. Snapshot/restored-source
seam — G0-S, shared CRUD — внешний WS track; HY-RIV-1 R1/R2 — внешний phase gate.

**Folder map/counts на G0-A.** Новых modules сейчас нет. Planned leaves с init:
dataModel/policy=5; application/policy=2; dataModel/cascade 4→5 (runtimeContext);
hydrology/generation=5, hydrology/policy=3, hydrology/enums/planning 2→5,
hydrology/planning 2→3 (sourceBodyMapping); terrain/regions=5,
terrain/relief/surfaceCoating=4 (включая surfaceSupportInput); placement/lifecycle=4;
application placement/lifecycle=2, adapters/coastline=2, planning/validation=3,
terrain/regions=3 (regionExtent/coverageMeasure), terrain/relief 1→2 (support);
materials/enums 2→3. designedWater leaves — дерево §5.4-A (не более 4).
Existing roots не расширяются: dataModel hydrology20/relief23/placement7,
application placement6/adapters6/registries9/worldBundle12, core/container9,
hydro contributors6, planning/composition5/contracts4. WARN выдан; новые helpers
только у named owner/leaf, __init__ без исполнения и скрытых aliases.
Common terminal PlacementPolicyDefaults (placement_specificity=0) принадлежит
dataModel/policy/objectAdmissionPolicyDefinition.py; definition связывает его
поле через FieldRef, не копирует default в adapter/engine.

**Обязательные проверки схождения до кода:**
- У каждого Jnn один named join owner; нет двух независимых источников
  настроек, admission, геометрии, identity/revision или diagnostics.
- Mismatch world/revision/phase/coordinate space не приводит к merge,
  unchecked cast, synthetic defaults или чтению другой версии базы.
- Доступ к source/region/outcome/body identity явный; порядок entries
  не используется как межконтрактный foreign key.
- Consumer schema принимает все согласованные варианты producer union,
  в том числе disabled без geometry; отсутствующий результат не выдан за
  валидный empty и не выкинут при фильтрации accepted records.
- Exact schemas/signatures зафиксированы §6.25–6.29; G0-A проверяет
  этот ledger на соответствие им и реальным production call sites.
  Наличие схемы не разрешает реализацию вне назначенного шага.

### 6.17 Первичная проверка existing→TARGET до закрывающей спецификации

Исторический audit до §6.28–6.29; актуальный verdict — §6.29-L.
Ниже evidence исходных несовместимостей production, не открытые TARGET design gaps.

Статус: **сквозная совместимость TARGET НЕ ПОДТВЕРЖДЕНА**. Наличие J01–J15
показывает точки соединения, не доказывает совпадение схем producer/consumer.
Проверка 2026-10-22: read-only AST-инвентаризация полей existing POJO/
dataclasses и аргументов конкретных calls; сравнение с target §5/§6.16.
Это не runtime acceptance новых contracts и не typecheck ещё не созданного
кода. Отсутствие target файла само по себе не ошибка: design check возможен
до кода, но требует полного определения полей/типов/инвариантов в плане.

**Подтверждено для существующего пути:** basinSpecFactory.basin_specs
передаёт все 7 полей existing BasinSpec (source_uid/kind/liquid/footprint/
z_water_level/floor_z/bands); source metadata и accepted footprint
соединяются через record/source identity. Это проверка соответствия
конструктору; она не доказывает поддержку generated field profile,
единицы координат либо семантику missing metadata для будущего auto source.

**Конкретные несовместимости existing → TARGET:**
1. J06/J07: WaterPlacementPreparation не имеет revision и early admission
   transport; PlacementBatch.objects принимает только PreparedPlacement.
   Geometry-free disabled input не проходит существующую batch схему.
2. J07/J08: PlacementOutcome содержит только Resolved/UnresolvedPlacement.
   Batch result validator и resolved_water_placements обращаются к
   item.prepared.intent.identity. Disabled без geometry требует изменения
   union, общего identity доступа и обоих consumers одновременно.
3. J05/J06/J09: PreparedWaterEntry.source — только DeclaredBasin/Coastline/
   Lake, floor_z — int. Partially authored auto source и spatial floor
   profile не соответствуют этому input. Factory дополнительно предполагает
   source.location_uid. Нужны source union и единый metadata/profile contract.
4. J10/J11: HydrologyResult содержит bodies/physical_unions, но
   SurfaceTerrainContext их не экспортирует; complete source→final body
   mapping также не предоставлен. Наличие данных внутри service не
   удовлетворяет input зависимого boundary consumer.
5. J14: prepare_surface_terrain_context вызывает water pass без ctx;
   общий ResolveReport теряется на этой ветке. Нужна проводка одного
   непустого request context на весь pipeline, включая validation path.

**До какого уровня TARGET ещё нельзя проверить:**
WaterGenerationContext, PolicySpec/PolicyDecision, source union,
WaterDesignInput/Draft, view/revision и coating facts/decision пока не имеют
полных схем всех полей/типов/union variants/invariants в плане. Именование
классов и ожидаемый смысл полей не заменяют проверяемое определение схемы.
Поэтому J01–J07/J11–J13/J15 остаются BLOCKED в соответствующих частях.
Исправленные порядок budget/input и явный budgets аргумент снимают
конкретные ошибки data flow, но не означают закрытия их contract gaps.

**Gate совместимости:** для каждого стыка до его implementation выписать
точный output producer и input consumer, проверить имена/типы/nullability/
union exhaustiveness, identity/revision/phase/units, validation invariants
и negative mismatch cases. Затем синхронизировать все затронутые consumers
и activation step. Общий статус compatible разрешён только после этой
проверки всех необходимых Jnn; до неё план design-incomplete.

### 6.18 Почему контракты расходятся: причины и направление исправления

Этот разбор уточняет §6.17 по коду. Несовместимость existing → TARGET
не означает, что existing declared pipeline сломан: часть требований
новая. Отдельно различаются расширение модели, потеря данных при передаче,
смысловое различие величин и незавершённая схема самого плана. Исправлять
всё optional полями/Any либо одним adapter cast запрещено.

**R1. Объект до геометрии против объекта после подготовки. J03/J06/J07/J08.**
Existing [PreparedPlacement](../../backend/app/dataModel/placement/prepared.py:41)
обязательно содержит original_area и candidates. Batch/queue принимают
именно такие объекты; outcomes содержат prepared. Это контракт этапа
«геометрия уже подготовлена», а не identity любого source.
TARGET раннее admission должно завершать объект до area/candidates.
Причина: изменилось время существования объекта в pipeline, а план
сначала предложил только новый финальный status без нового входного этапа.
Исправление в GAP-OUTCOME/POLICY: отделить identity/intent/admission от
готовой geometry. Вход P2 — явно типизированные варианты раннего terminal
admission и geometry-bearing prepared, не PreparedPlacement с фиктивной
площадью. Для resolved оставить обязательную выбранную geometry;
для disabled geometry не нужна; unresolved должен представлять также
ошибку до geometry. Общий identity API у всех outcomes; batch validator/
water mapper используют его. Не делать geometry optional повсюду:
варианты union должны сохранять свои обязательные инварианты.

**R2. Третий outcome меняет протокол зависимостей. J07.**
[DependencyQueue._record/settle](../../backend/app/application/worldData/placement/dependencies.py:81)
убирает завершённую опору из waiting, а failure propagation проверяет
только isinstance(UnresolvedPlacement). При добавлении DisabledPlacement
только в union disabled опора ошибочно освобождает child как ready,
хотя опоры нет в accepted; spatial consumer затем ожидает её наличие.
Причина: current queue использует исчерпывающую двухвариантную модель.
Исправление: обработать все три outcomes явно. Только ResolvedPlacement
удовлетворяет опору; Disabled передаёт общий SUPPORT_DISABLED dependent
результат; Unresolved/missing/cycle сохраняют error semantics. Early
terminal admissions учитываются до ready enqueue; _record не может
использовать просто «любой terminal = support satisfied». Это единое
изменение batch/result/queue/mappers в G0-P, не замена одного enum.

**R3. Authored source и нормализованный design intent — разные стадии.
J01/J05/J06/J09.**
DeclaredBasin требует footprint/floor_z; DeclaredCoastline/Lake требуют
location_uid. [PreparedWaterEntry.source](../../backend/app/application/worldData/placement/adapters/waterTypes.py:50)
содержит только эти authored типы. [basin_specs](../../backend/app/application/worldData/generators/hydrology/basinSpecFactory.py:15)
индексирует source.location_uid. Auto design получает геометрию/профиль
только после стратегии и не обязан иметь NamedLocation.
Причина: existing adapter объединяет оригинальную authored запись,
identity, prepared geometry и factory metadata в одной entry; plan
попытался передать через неё более ранний procedural source.
Исправление GAP-SOURCE: явный source union до design и нормализованные
metadata после design; source_uid — единый ключ intent/entry/record/spec.
Authored location reference сохраняется отдельно, не является обязательным
типом identity всех sources. Factory потребляет normalized metadata;
не создаются фиктивный NamedLocation/нулевой footprint/default floor
для удовлетворения authored schema. Конкретные source variants и поля
нужно определить до G4/G5, а не ослаблять DeclaredBasin.

**R4. Wetness, scalar floor и spatial elevation profile не взаимозаменяемы.
J06/J09.**
[floor_profile_z](../../backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/floorProfile.py:11)
из scalar floor_z, boundary distance, bands и kind строит текущий рельеф.
ContinentalField — signed continental samples [-1,1]; wet score вычисляет
общий preparer по §6.29-F/G4 supplement. Поле не является ни floor_z,
ни уже готовой картой высот. Даже совпавшие семь constructor fields
BasinSpec не доказывают сохранение generated profile.
Причина: новый output содержит пространственную информацию, отсутствующую
в существующем spec. Исправление GAP-FIELD: отдельные typed score,
threshold selection и floor-profile payload, согласованные единицы/границы.
Расширить existing spec/profile/writer согласованным вариантом профиля;
scalar authored поведение сохранить отдельным явным вариантом. Не
усреднять field в int floor и не писать высоты непосредственно из strategy.

**R5. Physical facts есть локально, но не доходят до нового consumer.
J10/J11.**
HydrologyGeneratorService.apply возвращает water_bodies/physical_unions;
[prepare_surface_terrain_context](../../backend/app/application/worldData/generators/terrain/passes/surfaceTerrainContext.py:146)
возвращает SurfaceTerrainContext без этих полей. MaterializedWater.uid_remap
— auto-body aliases, не полная связь всех accepted source с final body.
Причина: current context проектировался для terrain/river overlays;
новый dependent boundary требует более богатых post-fill facts.
Исправление GAP-BOUNDARY: final hydrology producer выдаёт typed mapping
accepted source → final physical body/system и wet facts одной revision;
конкретный caller передаёт его boundary preparation после fill. Зафиксировать
transport/result owner и downstream consumer; не угадывать body по совпавшему
UID/ближайшей воде и не делать второй hydrology resolve.

**R6. Optional request context маскирует разрыв reporting. J14.**
[waterPlacementPass](../../backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py:62)
при ctx=None создаёт свой ResolveContext. Caller имеет resolve_ctx,
но [вызов](../../backend/app/application/worldData/generators/terrain/passes/surfaceTerrainContext.py:100)
его не передаёт, тогда как следующая hydrology ветка передаёт.
Причина: signature разрешает пропуск зависимости, поэтому вызов валиден
по типам, но теряет общий report/validate_only. Это реальный разрыв
проводки, а не отсутствие будущего type. Исправление: один ctx в root
caller и явная передача во все ветки; audit всех optional ctx defaults.
G0-A/GAP-VALIDATION/LOG проверяют validation/no-writes path, не только logs.

**R7. Identity объекта не является revision его входов. J02/J06/J07/J10.**
[snapshot_uid](../../backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py:86)
зависит от world+phase. Settings/geometry edit сохраняет этот UID.
Preparation/batch/result не несут общего change-sensitive token; текущее
равенство строк не доказывает одинаковый input двух вычислений.
Причина: existing UID служит идентификации фазы, а target хочет также
контроль cache/replay consistency. Исправление G0-S: не менять смысл UID,
задать единый typed input revision и его producer/consumers на всех join
boundaries; immutable view фиксирует данные, а не только frozen оболочку
вокруг общей mutable dict. Future platform snapshot адаптируется по §6.15.

**R8. Названный будущий context ещё не generic runtime contract. J01/J03.**
Existing cascade extend и _check_bindings имеют LocationContext contract;
текущий context содержит служебные chain/node-results/default-source поля.
WaterGenerationContext добавляет другую ось/параметры, но одного имени
в плане недостаточно для проверки работы engine с тем же протоколом.
Причина: domain metadata graph уже общий, runtime context ещё связан
с действующим location consumer; target protocol не описан до конца.
Исправление G1/GAP-CASCADE: явный общий runtime context protocol/base
с сохранением LocationContext API и snapshots/provenance, water subtype
и verifier другой оси. Не копировать engine и не приводить новый context
к LocationContext через cast. То же требование полноты схем действует
для PolicyDecision/Draft/SurfaceCoatingFacts: без полей и инвариантов
это пока незавершённый план, не обнаруженная ошибка existing producer.

**Порядок устранения причин:** R1/R2 (общий lifecycle) → R8 (context)
и R7 (revision) → R3 (source/metadata) → R4 (profile) → R5 (post-fill
transport), с R6 (единая диагностика) для всех путей. Все причины
сопоставлены существующим 12 gaps; это не новый набор продуктовых вопросов.
После определения target схем каждый Jnn повторно проверяется по §6.17.

### 6.19 Согласованные исправления контрактов и последствия для поведения

Мастер принял следующие рекомендации. Они задают обязательный target
для закрытия причин R1–R8; не являются разрешением писать код и не
заменяют exact поля/типы/union cases и проверки совместимости §6.17.
Нельзя ослаблять все поля до optional/Any ради соединения стадий.

**D1. Admission отдельно от geometry (R1, GAP-POLICY/OUTCOME).**
До geometry объект имеет identity, intent и policy decision. PreparedPlacement
появляется после расчёта площади/candidates и сохраняет обязательность
geometry для размещения. Early disabled и pre-geometry unresolved имеют
собственное typed представление без фиктивных площади/footprint.
Поведение: отключённый объект не запускает дорогой design/preparation;
ошибка до geometry представима явно; resolved всегда имеет выбранную
допустимую geometry. Проверка: disabled без area/candidates, early failure,
невозможность resolved без geometry и отсутствие carve у non-resolved.

**D2. Outcomes и dependencies изменяются согласованно (R2, GAP-OUTCOME).**
Все consumers исчерпывающе обрабатывают Resolved/Disabled/Unresolved.
Только Resolved удовлетворяет опору. Disabled причинно отключает dependent
через общую policy/SUPPORT_DISABLED; unresolved/missing/cycle сохраняют
error semantics. Union/queue/validators/mappers переключаются вместе.
Поведение: нет размещения на отсутствующей опоре; normal disable не
инвалидирует мир, ошибка остаётся ошибкой, независимые объекты продолжают
обработку. Проверка: цепочки/ветвления зависимостей и отсутствие ложного
ready после terminal outcome, с единой диагностикой причин.

**D3. Authored source отдельно от normalized design intent/metadata
(R3, GAP-SOURCE).**
DeclaredBasin/Coastline/Lake сохраняют строгие authored инварианты.
Adapter переводит authored и procedural варианты в общий input design;
после design формируются единые metadata для existing factory.
source_uid — ключ intent/entry/record/spec; NamedLocation reference —
отдельный атрибут, не обязательный вид identity procedural объекта.
Поведение: procedural вода не требует фиктивной локации; authored
ограничения сохраняются; все стратегии проходят единый placement и
metadata mapping. Проверка: declared/auto variants, отсутствие location,
source mapping и сохранение явно заданных geometry/floor constraints.

**D4. Явные варианты профиля existing BasinSpec (R4, GAP-FIELD).**
Предусмотреть параметрический профиль из floor_z/bands и пространственный
профиль высот. Wetness сначала задаёт выбор области; преобразование score
в высоты задаётся отдельно. Existing single relief writer принимает
согласованный вариант профиля; raw score не трактуется как z.
Поведение: authored scalar/bands путь сохраняется; generated profile не
теряется при сведении к одному int; горные reservations и single writer
сохраняются. Проверка: regression параметрического профиля, неоднородный
spatial профиль, units/range и отсутствие z-write из стратегии.

**D5. Final water facts — явный post-fill контракт (R5, GAP-BOUNDARY).**
Producer выдаёт bodies, unions, wet cells и mapping accepted source →
final physical bodies одной revision. Не предполагать one-to-one:
результат может отсутствовать либо содержать несколько частей.
Mapping не выбирает произвольное тело при нескольких результатах;
exact поддержка boundary geometry определяется GAP-BOUNDARY.
Поведение: dependent coastline использует фактически полученную воду;
merge/split/dry не приводят к поиску ближайшего случайного body или
fallback созданию воды. Проверка: 0/1/multiple mapping, merge/split,
dry target, unchanged mountains, no body spec/no z-write boundary.

**D6. Общий request ctx обязателен внутри pipeline
(R6, GAP-VALIDATION/LOG/CUTOVER).**
Root boundary создаёт ResolveContext один раз при необходимости;
внутренние вызовы получают его явно, без независимых default reports.
Поведение: validation получает diagnostics всех стадий, validate_only
сохраняется на всех ветках, applied runtime fallback логируется однократно.
Проверка: report identity от caller до P2/hydrology, no-writes validation,
реальный single log emission и обнаружение пропущенной зависимости.

**D7. Snapshot identity отдельно от input revision
(R7, GAP-SNAPSHOT/G0-S).**
Один caller фиксирует immutable входы и revision запуска; consumers
получают готовый token. Future WorldSnapshot/Patch System подключается
на той же границе по §6.15, без переписывания strategy/placement.
Поведение: значимое изменение input инвалидирует вычисления, одинаковые
inputs воспроизводятся; world/phase UID не разрешает чтение старого cache.
Проверка: input edit/equivalent permutation, immutable backing data,
cache mismatch и совместимость текущего/future adapted input.

**D8. Общий runtime protocol существующего cascade
(R8, GAP-CASCADE/G1).**
Выделить общий protocol/base служебного состояния; LocationContext
сохраняет API, water context использует тот же engine с собственной осью.
Поведение: единая семантика None-наследования, explicit False/0,
terminal defaults, ancestor snapshots и provenance; второго resolver нет.
Проверка: обе оси одним engine, verifier, existing location regression,
отсутствие casts нового контекста в LocationContext.

**Порядок:** D1/D2 → D8 и D7 → D3 → D4 → D5; D6 сопровождает все стадии.
Это порядок определения/согласования contracts и затем dependency-aware
implementation, не разрешение объединить изменения нескольких слоёв в
один code-step. В §7 сохраняются атомарность и activation gates; шаги
до их prerequisites не активируются. Закрытие каждого gap требует exact
target схемы и попарной проверки соответствующих Jnn, а не только Dnn.

### 6.20 Планировка сначала; материализация по требованию

Обязательный общий инвариант мастера, также закреплён в code-gates.mdc.

**1. Планировка.** До materialization строится согласованная планировка
объекта/набора объектов: source/settings, resolved policy/admission,
выбранные geometry/placement, dependencies и profiles/levels, необходимые
для воспроизводимого результата. Планировка имеет явную revision и
сохраняет достаточный typed output/recipe для materializer своего домена.
Disabled/unresolved — результаты planning, не повод материализовать
фиктивную geometry. Derived fill/height/facts в памяти могут требоваться
для planning; это не запрос записи всех L0/L2 клеток/тайлов мира.

**2. Изменение.** Изменение объекта сначала обновляет его планировку.
Обновляется также затронутый набор dependencies и пространственных
конкурентов, если изменение влияет на их разрешение. Старое accepted
решение не становится вечной опорой после изменения входов: immutable
accepted действует внутри одной planning revision, новый revision
получает своё согласованное разрешение. Нельзя применить изменение
напрямую к materialized output, оставив authoritative layout прежней.
Пересборка детерминирована; она может сохранить прежние координаты,
но layout revision и новые параметры должны отражать изменение объекта.

**3. Материализация.** Выполняется только по запросу: bake выбранного LOD/
области, refine/detailed bake или entry. Materializer получает готовую
актуальную планировку и её revision плюс область/LOD запроса. Он не
выбирает повторно strategy, priority, source или победителя placement.
Fine-detail вычисляется из закреплённого layout/recipe, не меняет
принятый footprint/dependencies из-за другого порядка/размера tiles.
Изменение планировки само по себе не запускает eager materialize всего
затронутого мира; подготовка данных и запрос materialize разделены.

**4. L0/L2.** L0 — coarse/light materialized representation, L2 — fine
representation; оба выводятся из одной актуальной domain layout.
L0 не равен всей планировке и не хранит обязательно всю точную geometry.
L2 может использовать L0/base как согласованный вход детализации той же
revision, но не создаёт независимое размещение объекта. Отсутствующий
L0/L2 cache не меняет planning result. Partial/full запросы меняют объём
доставки, не competing universe и не принятые решения planning.

**5. Revision/invalidation.** У layout input revision и готовой layout
revision явная связь. Requested materialization проверяет совместимость
с layout revision; устаревший cache не выдаётся за текущий. После edit
он помечается stale/инвалидируется, rebuilding выполняется по запросу.
Immutable pack и gameplay patch precedence сохраняются; конкретный
update pipeline оформляет domain state/layout и будущий patch output
по §6.15, не создаёт второй persist/snapshot service в генераторе.

**6. Контрактные стыки.** J01–J11 описывают planning и его typed results;
J12/J13 разделяют planning facts/decision/report от физического paint.
L0 compose и TerrainBatchOrchestrator.build_tile_surface_state — consumers
актуального layout/recipe. Exact layout output/owner/revision, доставка
L0/L2, storage/read boundary и запросы должны быть закреплены G0-A/G0-S
и G8/G10 до реализации. Это обязательная часть существующих GAP-SNAPSHOT/
CUTOVER/FIELD/PHASE, не свободное решение materializer при исполнении.
Fine sampling для HY-RIV-1 — bounded read-only вычисление для planning
из того же pre-river terrain recipe; оно не требует eager bake/persist L2.

**Приёмка:** planning без materialize writes; edit → обновление layout
и зависимых решений; отсутствие eager materialize после edit; запрос
L0/L2 использует текущую revision; stale cache не выдаётся за свежий;
повторный materialize не запускает policy/placement снова; full/partial,
разный порядок tiles и cache hit/miss не меняют layout/geometry. Совпадение
неизменившихся координат после edit не заменяет обновление планировки.

### 6.21 Общие planning/cache: размещение, создание и хранение планировок

Согласованная архитектура: общий механизм для climate,
terrain/relief и hydrology; другие домены подключаются через тот же
protocol. **Города/settlement/district/building planners, их contracts
и caches в этой миграции не изменяются.** Это target scope;
exact общие схемы и миграция ещё требуют закрытия G0-A/G0-S.
Кэши городов и локаций — отдельная архитектурная тема, не разновидность
проектируемого здесь planning cache по умолчанию. Этот план не определяет
их backend, ключи, lifetime, invalidation или будущую миграцию. Общие
названия PlanningService/CacheService не означают обязательного переноса
в них городских/локационных кэшей. Текущие потребители общего planning
cache: climate, terrain/relief и hydrology; расширение scope явно планируется.

**Проверенное текущее положение.** Планирование вызывается из
terrain/passes/surfaceTerrainContext.py::prepare_surface_terrain_context;
SurfaceTerrainContext — in-memory агрегат, передаваемый L0/L2 callers.
Общего reusable plan repository/cache для этих доменов пока нет.
application/worldData/pack/read/packReadContext.py хранит readers и decoded
climate fields в RAM; FineTerrainDecodeCache хранит LRU декодированных
terrain chunks. Они кэшируют чтение готового pack, не являются хранилищем
authoritative object layout и не заменяют общий planning lifecycle.

**Механизмы разделены по ответственности.**
- PlanningService управляет получением согласованной планировки,
  revision/dependency refs и публикацией результата. Доменный PlanProvider
  строит typed layout; общий service не вычисляет климат/рельеф/воду.
- CacheService отвечает за хранение/получение/eviction/invalidation
  производных значений через общий typed backend protocol. В cache нет
  правил доменного planning, placement или materialization.
- Общие policy/cascade/placement сохраняют свои механизмы. Provider
  использует их по declared contracts, не создаёт локальные копии.
- Существующий DAG/orchestrator задаёт явный порядок фаз. PlanningService
  не становится вторым универсальным DAG scheduler и не угадывает
  кросс-доменные зависимости по payload.

**Точное расположение предлагаемых модулей**, от backend/app:
```text
dataModel/planning/
├── identity/     planKey.py, planRef.py
└── contracts/    planRequest.py, planDependency.py, planEnvelope.py
dataModel/cache/
├── identity/     cacheKey.py
├── contracts/    cacheContract.py, cacheEntry.py, cacheLookup.py
└── policy/       cachePolicy.py
application/planning/
├── service/      planningService.py
└── providers/    planProvider.py, planRegistry.py
application/cache/
├── contracts/    cacheBackend.py
├── backends/     memoryCache.py
└── service/      cacheService.py
application/worldData/planning/
├── composition/  surfacePlanningAssembler.py, planProviders.py,
│                 surfacePlanningCapture.py
└── contracts/    surfacePlanBundle.py, surfacePlanningView.py
dataModel/surfacePlanning/
                 surfacePlanSlot.py (§6.33, PC-6S; с __init__.py — 2 файла)
dataModel/spatial/grid/
                 gridBBox.py, coordinateSpace.py, coordinateTypes.py,
                 gridSettings.py
```
Общие modules вне worldData и доменов. Каждый root содержит только
__init__.py. Итоговая композиция всех новых leaf folders с актуальными
counts — §6.29-M (planning contracts — 5 с planContract.py,
spatial/grid — 5 с gridSettings.py, composition — 4 с
surfacePlanningCapture.py; добавлены также planning/diagnostics,
planning/policy, validation/, identity/ и domain inputs/ — полный
перечень там же). Existing dataModel/spatial имеет 3 непосредственных
файла и получает подпапку, не дополнительные flat files. WARN >5 не
возникает. Эти выносы выполняются PC-0G1/PC-0G2/PC-9A/PC-9.
Предел >5 не превышен. Domain providers размещаются в своих namespaces:
application/worldData/generators/climate/planning/climatePlanProvider.py;
application/worldData/generators/terrain/planning/terrainPlanProvider.py;
application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py;
application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py.
Domain payload types принадлежат соответствующим dataModel domains,
не common cache: ClimatePlan, TerrainPlan, ReliefPlan и HydrologyPlan
по A03/PC-1C/T/R/H. ClimatePlanSampler находится в
application/worldData/generators/climate/planning/climatePlanSampler.py,
не в dataModel; climate planning application папка — 3 файла с init.
Exact payload schemas и composition-root регистрации
providers фиксируются G0-A; общий service не импортирует implementations.
Existing SurfaceTerrainContext остаётся transitional aggregate adapter,
его определение переносится в worldData/planning/contracts/surfacePlanningView.py;
старый terrain path re-export/delegation. Cross-domain assembly находится
в worldData/planning/composition/surfacePlanningAssembler.py::
SurfacePlanningAssembler.prepare, не в terrain.
Это не второй authoritative plan store. Domain namespace inventory и file
counts проверяются до добавления этих modules.

**Где создаётся план.** Вызов caller → PlanningService.get_or_build
с typed request/immutable resolved inputs и dependency refs. Service
проверяет compatible cached envelope; при miss вызывает зарегистрированный
domain PlanProvider.build, валидирует envelope и публикует результат.
Создаёт layout домен; общая точка доступа/публикации — planning service.
DesignPreparation/strategy/общий P2 остаются внутри domain planning path,
materializers получают готовый PlanEnvelope/PlanRef. Один layout может
иметь несколько LOD representations без повторного placement.

**Где хранится cache.** Начальный backend — bounded process-local RAM
в application/cache/backends/memoryCache.py, один injected instance
на application process/composition root, не новый dict на request и не
модульная mutable глобальная таблица в генераторе. Limits/eviction policy
объявлены typed CachePolicy; числовые defaults не придумываются в consumers.
В cache лежат immutable typed plan envelopes и dependency metadata,
не SQL-сессии/World ORM/ResolveContext. Concurrent одинаковые misses
объединяются по key (single-flight); неуспешный build не публикуется как
валидный план. Worker processes не предполагают общей RAM: inputs/revisions
и детерминизм общие, topology-aware results не зависят от cache hit/miss.

Cache — ускоритель, не authoritative state. После eviction/restart layout
можно детерминированно восстановить из authoritative world/domain inputs
с теми же dependency/algorithm versions либо получить сохранённый layout
через будущий общий WorldSnapshot adapter. До такого восстановления
materialization не начинается. Локальные snapshot файлы, Redis, новая
SQL plan table и durable capture service этим предложением не вводятся.
Долговечное состояние остаётся у существующих domain repositories/pack/
Patch System и будущего WorldSnapshot по §6.15; cache можно заменить backend
без изменения domain providers и L0/L2 consumers.

**Контракты ключа/значения.** PlanKey адресует world/domain/объект или
planning scope и фазу. Cache lookup включает input revision, тип/версию
provider algorithm/schema и dependency refs; payload тип связан с registered
provider, не dict[str, Any]. PlanRef связывает identity, input revision,
готовую layout revision и provenance. Output revision не используется
как единственный lookup key до build: она появляется после результата.
Обязательные scope/phase/domain значения — typed enum/registered contract;
opaque identity tokens не смешиваются с raw wire settings. Namespace
timeline/restored-state определяется общим snapshot contract; никакие
фиктивные turn/snapshot IDs ради current cache не создаются.

**Invalidation и согласованность.** Edit сначала меняет domain inputs и
перестраивает затронутые layouts/dependency closure; затем публикуется
согласованный набор plan refs. Materialized L0/L2 representations старых
refs stale, их rebuilding — только по запросу. Cache eviction при тех же
inputs не равен edit. Build по устаревшей source revision не публикуется
как latest. Один materialization request получает frozen набор совместимых
refs; нельзя соединять новый terrain с hydro старой revision.

Зависимости задаются по фазам, чтобы избежать climate↔terrain↔hydrology
цикла: climate base/poles → terrain base → relief constraints → water
design/placement → post-relief terrain → physical water facts; climate
column resolve потребляет final elevation. Согласно tz_climate §Partial
recalc hydrology z/role edit инвалидирует соответствующий column resolve,
но не climate base field, если его собственные inputs не изменились.
Иные phase dependencies фиксируются явно; HY-RIV-1 использует pre-river
base и не зависит от своего post-carve output.

**Границы внедрения.** Existing PackReadContext/manifest-stamp/decode caches
сохраняют свои read-path contracts; это не скрытый второй planning cache.
Их перенос на общий cache backend требует отдельного явного adapter scope,
не входит автоматически в GEO-1. Города не регистрируются/не мигрируются.
До code activation обязателен ledger current caller → PlanProvider →
PlanningService/CacheService → PlanEnvelope → L0/L2 consumer, с удалением
параллельного re-planning path. G0-S revision contract теперь общий
planning contract, а не отдельная terrain-only cache система.

**Следствие:** layout имеет определённого producer и общую точку доступа;
cache location/lifetime явны; климат, рельеф и вода используют один
revision-aware lifecycle; materialization остаётся по требованию.
Shared contracts/provider wiring/invalidation нужны отдельными атомарными
implementation шагами после согласования exact API; добавления одного
сервиса без production migration недостаточно для объявления готовности.

### 6.22 Cache: единый interface, generic payload и отсутствие второго SoT

Требование мастера: cache не становится второй истиной. Согласованный
контракт — **один generic interface + заменяемые backend implementations**,
а не выбор между interface и generic. Это контракт §6.21;
exact schema/API фиксируются до implementation, cache/layout persistence
не смешиваются.

**A. Типизация.** CacheContract[T] связывает registered namespace,
schema version и payload type/validation contract. CacheKey[T],
CacheEntry[T], CacheLookup[T] сохраняют эту связь до consumer; T для
planning — PlanEnvelope[конкретный domain layout type]. Нет общего
dict[str, Any] и consumer-side cast ради получения domain plan.
Runtime binding проверяется по зарегистрированному контракту, generic
annotation сама по себе не проверяет содержимое backend. Registration
механизм хранит type/provider bindings, не current domain state/revision.

Общий backend protocol в application/cache/contracts/cacheBackend.py:
- get(key: CacheKey[T]) -> CacheLookup[T];
- put(entry: CacheEntry[T]) -> None;
- evict(key: CacheKey[T]) -> None.
CacheLookup явно различает HIT с entry и MISS. CacheEntry содержит
согласованные key и immutable T value. Backend failure/corruption —
отдельная техническая ошибка, не MISS и не валидный пустой plan.
Limits/eviction policy — CachePolicy в dataModel/cache/policy/.
CacheService связывает typed namespace/backend и проверяет соответствие
entry contract/key/revision, не вычисляет доменные значения.

Для climate, terrain/relief и hydrology не нужны три копии MemoryCache:
они используют typed partitions/views одного общего backend/service.
Доменные реализации нужны PlanProvider и domain layouts; общий cache
проверяет registered payload contract. Новые backend (если понадобятся)
реализуют тот же protocol и codec/validation contract; serialization
не определяет свою копию domain semantics. Начальный backend только RAM.

**B. Что является истиной.** Authoritative source — world/domain state,
authorские параметры/identity/seed и нужные dependency/algorithm versions,
позднее общий restored state/Patch System по §6.15. Cache содержит лишь
восстанавливаемую immutable проекцию этих данных. Если результат нельзя
воспроизвести из сохранённых inputs/choices, необходимые choices либо
layout должны стать частью authoritative domain state/snapshot до
использования; держать единственный экземпляр такого результата в cache
запрещено. Общий cache не превращается в plan repository/commit service.

**C. Как cache не определяет актуальность мира.** Root caller получает
current input revision из authoritative состояния/его projection.
PlanningService строит expected cache key из identity/scope/phase,
registered artifact contract, input revision, dependency refs и версий.
Cache не отдаёт «последний plan по world_uid» без expected revision,
не назначает domain revisions из своего счётчика и не подменяет их TTL.
Проверка entry выполняется против expected key, не только entry header
самого cache. Invalidations помогают освобождать stale entries, но
корректность не зависит от доставки invalidation event: другой revision
даёт другой lookup/несовместимость, старый hit не используется как current.
PlanRegistry из §6.21 — registry providers/contracts, не источник latest
world revisions. Публикация вычисленного envelope не коммитит изменения мира.

**D. Read-only и rebuild.** Consumer не мутирует cached payload; frozen
оболочка вокруг общей mutable dict недостаточна. Инварианты immutable
values задаются domain contract и соблюдаются RAM backend. Cache deletion,
eviction/TTL или restart не меняют state/seed/identity/геометрию. На MISS
PlanningService восстанавливает ту же layout из authoritative inputs;
затем materializer читает её без нового локального policy/placement.
Cold rebuild — отдельная planning стадия, не изменение решения ради того,
что materialization запросила другой tile/LOD. Ошибка восстановления
не позволяет использовать несовместимый старый plan как fallback.

**E. Разделение caches.** Planning cache не является materialized L0/L2
pack, Patch Store, WorldSnapshot blob или cache городов/локаций. Иерархия:
authoritative inputs → domain planning → derived plan cache → L0/L2
materialization по запросу. Pack/read decode caches сохраняют свой scope;
переиспользование общего backend не меняет их source-of-truth contracts.

**Приёмка отсутствия второго SoT:**
- Cache целиком очищен → те же authoritative inputs/versions дают те же
  layouts/placement/body identities; мир не теряет изменения.
- Изменение domain state при недоставленном invalidation не возвращает
  старый plan как current; revision берётся вне cache.
- Другой domain/payload type/schema version/revision не принимается за HIT
  нужного typed key; domain consumer не выполняет unsafe cast.
- Попытка mutation результата не меняет планировку следующего consumer.
- Concurrent MISS одного key не создаёт competing authoritative layouts;
  failed build не публикует valid entry и не изменяет domain state.
- L0/L2 на HIT и после cold rebuild совпадают; cache lifetime и worker
  process count не меняют мир. Города/локационные caches не затрагиваются.

### 6.23 Аудит границ общего planning/cache: выносы и оставшиеся стыки

Проверено по текущему коду после выделения PC. Ниже рекомендации к
закрытию PC-0, не объявление новых mechanisms реализованными. До
замораживания API обязательно разрешить эти стыки; готовый общий cache
сам по себе не исправляет владение contracts, mutable inputs или cycles.

**A01. Междоменную сборку вывести из terrain generator (согласовано).**
surfaceTerrainContext.py сейчас вызывает climate, terrain, relief и
hydrology, то есть выполняет cross-domain composition. При общем planning
target assembly:
application/worldData/planning/composition/surfacePlanningAssembler.py::
SurfacePlanningAssembler.prepare. Typed bundle —
application/worldData/planning/contracts/surfacePlanBundle.py::SurfacePlanBundle.
Единственное определение legacy SurfaceTerrainContext переносится в
application/worldData/planning/contracts/surfacePlanningView.py;
старый prepare_surface_terrain_context — compatibility entry/delegation,
не второй активный coordinator. Provider bindings — composition/
planProviders.py::register_world_plan_providers; общий application/planning
остаётся domain-neutral. Registry/provider injection не доменная factory.
Assembler использует явные фазы существующей orchestration, не новый DAG
и не вызов полного materialization другого домена из генератора.
Исполнение: PC-0 фиксирует bundle поля/сигнатуру и current caller ledger;
PC-9A создаёт новую composition boundary, PC-9 переключает callers и
удаляет прежнюю orchestration из terrain. Generators сохраняют доменную работу.

**A02. Shared geometry не принадлежит climate (согласовано).**
Existing GridBBox объявлен в generators/climate/climatePoleField.py,
terrain/types.py делает lazy re-export ради обхода import cycle,
hydrology/types.py также импортирует его из climate. Это общий grid-AABB.
Target: dataModel/spatial/grid/gridBBox.py::GridBBox (PC-0G1),
dataModel/spatial/grid/coordinateSpace.py::CoordinateSpace и
dataModel/spatial/grid/coordinateTypes.py — existing GridX/GridY/FineX/
FineY/FineZ/FineDelta, SurfaceGridCoord/FineGridCoord/SurfaceGridRect/
FineGridRect (PC-0G2). Existing definitions перемещаются с compatibility
re-export, параллельные enum/classes/aliases не создаются. WorldBounds не заменять
GridBBox механически: world domain vs sampled extent и inclusive-cell
semantics различаются. Existing SurfaceGridRect/FineGridRect half-open
semantics и поля GridBBox сохраняются, migration не меняет размеры/границы.
Метрики/coordinate conversion algorithms остаются
у своих application/topology исполнителей. Городские consumers не меняются.

**A03. Cached payload — domain data, не live application object (согласовано).**
ClimatePoleField.sample(world, gx, gy) читает climate_scalars(world) и
profile_for(world, key) при каждом sample. Такой frozen объект всё ещё
зависит от live World/registry и не фиксирует состояние cached plan.
SurfaceHeightmap содержит изменяемую dict; HydrologyResult.heightmap —
Any/same reference, сам result содержит mutable lists/dicts.
Обязательные payloads: dataModel/climate/planning/climatePlan.py::ClimatePlan,
dataModel/terrain/planning/terrainPlan.py::TerrainPlan,
dataModel/terrain/relief/planning/reliefPlan.py::ReliefPlan,
dataModel/hydrology/planning/hydrologyPlan.py::HydrologyPlan.
Sampler/algorithm остаётся в application и
получает эти data/explicit frozen registry inputs, не перечитывает World.
Mutable рабочие heightmaps и результаты materialization не класть в
общий cache по ссылке. Все необходимые facts/recipe inputs попадают в
revision; copy/read-only boundaries проверяются явно. BasinSpec переносится
в dataModel/terrain/relief/bathymetry/basinSpec.py с existing re-export
в PC-1R; writer не переносится. Поля/leaf type inventory замораживаются
PC-0; создание domain payloads — PC-1C/T/R/H до providers PC-5…8.
В каждой новой domain planning/bathymetry папке базово 2 файла с init;
дополнительные leaf contracts из inventory требуют явных путей/file counts.

**A04. Диагностика должна переживать HIT/MISS.**
Existing domain emitters принимают request ResolveContext и могут
логировать во время build. Cache hit пропускает build: если cache хранит
только layout, предупреждения/validation issues исчезнут; при single-flight
чужой request report нельзя использовать для всех ожидающих.
Рекомендация: cached envelope содержит immutable deterministic domain
diagnostic facts (либо явный typed diagnostics component), без request ctx/
logger/transcript. Каждый request переводит их в свой report/runtime sink
ровно один раз по existing reporting contract. Domain build не определяет
своим cache-miss log всю семантическую диагностику request; telemetry
cache hit/miss отдельно. Existing FieldPathError/ReferenceIssueContext
находятся в application/jsonValidation/types.py: перед import в dataModel
нужен inventory/вынос pure definitions с re-export, не новый дублирующий
issue type и не новый logger. ResolveContext/ResolveReport остаются
request-local application objects и не кэшируются.
PC-0/PC-4/PC-12: HIT/MISS/single-flight дают одинаковую domain диагностику,
runtime/validate_only используют разные sinks одного результата.

**A05. Revision запроса и artifact fingerprint — разные уровни.**
Один frozen state view определяет согласованность запроса/ветки. Однако
artifact input revision должен зависеть от собственных domain inputs:
изменение hydro columns не должно автоматически rebuild climate base.
Сравнение всех PlanRefs только по равенству глобальной revision либо
делает cache бесполезным на локальных edits, либо скрывает реальные
dependency mismatches. Рекомендация: отделить state-view provenance и
per-artifact input/dependency revisions; совместимость bundle проверять
явным соответствием declared dependencies выбранному frozen view.
Фразы «одна revision» в J02/J07/PC-9 означают одну согласованную input
view, а не обязательное равенство fingerprints разных доменных artifacts.
PC-0/G0-S замораживают schema/сравнение/канонизацию до кода. Latest state
не берётся из cache; старый, но still-compatible climate artifact может
переиспользоваться без изменения своих физических данных.

**A06. Publish/commit guard принадлежит caller/persist boundary.**
Cache key корректен для captured input, но мир мог измениться во время
долгого build/materialization. Один cache-key check не разрешает записать
результат старой source view как актуальный. Рекомендация: root caller
задаёт expected source ref; owner публикации/существующий writer/UOW
проверяет допустимость commit и revision после compute. Historical frozen
результат можно читать в его scope, нельзя переобозначать как latest.
Generic CacheService не делает SQL commit, не ведёт current-world pointer
и не решает domain конфликт edits. Точный stale/cancel/retry outcome и
guard при existing pack/patch boundaries — PC-0/PC-9/PC-10/PC-11.

**A07. Memory/single-flight contracts ещё не полны.**
Одинаковое число entries не ограничивает размер plan с height/claim maps.
Рекомендация: typed общий memory/cost budget плюс per-entry admission
и lifecycle приоритетов partitions; oversized result можно вычислить и
не хранить, не меняя layout и не обрезая geometry. Numeric policy/defaults
и измерение cost фиксирует PC-0, не потребители. Single-flight должен
различать cancellation одного waiter и самого build: отмена одного
request не должна ломать другие, failed/cancelled build не публикует
валидный entry. In-flight bookkeeping ограничено и освобождается.
PC-3/PC-4/PC-12 проверяют большие artifacts, waiters, failures и eviction.

**A08. Build/materialize distinction закрепить для каждого provider.**
Название waterMaterialize/MaterializedWater в current HY-12 описывает
также вычисляемые в памяти wet facts. Обёртка cache над existing method
не доказывает отсутствие carve side effects, SQL или повторного planning.
PC-0 для каждого provider перечисляет pure frozen input → derived output
и отдельно рабочие mutable buffers/materialization writes. Crop/tile
фильтрует delivery, не planning universe; pre-river sampling не зависит
от финального SurfaceTerrainContext. Смешанные methods раскладываются
по стадиям с сохранением existing domain behavior, не мигрируются как
непрозрачный cached callback с захваченным ORM/request контекстом.

**Что не выносить в новый общий домен:** climate algorithms, relief
profiles/writers, hydrology fill/classify/shore, water settings и их
частные rules остаются своими доменами. Relief пока остаётся terrain
subdomain; ему не нужен отдельный верхнеуровневый общий engine. Cache
не владеет ни domain diagnostics semantics, ни revision sources, ни
конкуренцией placement. City/location cache тема отдельно.

**Gate:** A01–A08 входят в PC-0 freeze и приёмку соответствующих PC steps.
Это уточнение архитектурных условий подготовки; статусы основных 12 gaps
не закрываются этим аудитом автоматически. При изменении domain map
сначала синхронизировать §5.4/§6.21 и все затронутые signatures/steps;
до этого нельзя реализовывать по любому из двух несовпадающих путей.

### 6.24 Первичный audit архитектуры/контрактов по правилам

Исторический verdict до §6.28–6.29; актуальное design closure — §6.13.

Первичный audit PC/A01–A03 завершён спецификациями §6.25–6.29.
Текущий design verdict — 11 закрытых внутренних gaps и отдельный
HY-RIV-1 gate §6.13. Ниже сохраняются проверенные факты existing кода;
они объясняют запланированные изменения, не отсутствие TARGET схем.

**Проверено непосредственно, без правки кода/тестов:**
1. AST сравнение basinSpecFactory constructor kwargs и BasinSpec fields:
   совпадают все 7 полей. Это field correspondence existing scalar path,
   не доказательство generated profile/coordinate semantics.
2. TypeAdapter(PlacementOutcome) на status=disabled: union_tag_invalid.
   Это ожидаемая несовместимость existing union с TARGET; исправление
   должно охватить batch/queue/validators/mappers, не один новый enum.
3. Existing BasinSpec проверяет floor_z < z_water_level; равный уровень
   вызывает ValueError. HydrologyBands frozen не допускает assignment.
4. При этом прямой BasinSpec(kind=None, корректные остальные значения)
   создаётся. TypeAdapter(BasinSpec).validate_python(existing_bad_instance)
   возвращает тот же instance с kind=None. Это диагностический probe,
   не доказательство ошибки production factory, где kind приходит typed.
   **Следствие для TARGET:** strict cache payload validation нельзя
   реализовать только isinstance, frozen=True или adapter без revalidation.
5. Проверены фактические числа файлов и TARGET additions. Нарушения
   в hydrology root/enums и relief root устранены переводом новых типов
   в generation/, enums/planning/ и relief/surfaceCoating/ по §5.4.
   Ни один существующий source-файл в этой проверке не перемещён.

**Closure checklist первичного audit:** полные общие schemas/API —
§6.25; domain outputs/phases — §6.26; DI/diagnostic sinks/commands —
§6.27; immutable concrete inputs/fingerprints/capture — §6.28;
source/policy/coverage/floor/boundary/surface/cutover — §6.29.
Совместимость проверена по полям/types/units/phases/references на уровне
TARGET specification. Executable typecheck/regression — implementation
acceptance; не выдавать ручной design review за запущенные будущие tests.

### 6.25 PC-0: конкретный контракт общего planning/cache

Этот раздел уточняет §6.21–6.24. Ниже TARGET specification, а не
утверждение о наличии классов в коде. Поля без указанного default обязательны;
`X | None` означает обязательное nullable поле, а не разрешение пропустить
его. Внутренние resolved contracts не применяют wire defaults повторно.
Авторские JSON по-прежнему разбираются существующей POJO boundary.

**Типы идентичности и версии.** В `dataModel/planning/identity/planKey.py`:
`InputFingerprint`, `OutputFingerprint` и `StateViewRevision` — разные opaque NewType над
32-byte SHA-256 digest; `AlgorithmVersion`, `SchemaVersion` — разные
NewType над strict positive int (bool запрещён). `PlanSlot` — opaque
nonempty identifier declaration, не свободная строка выбора алгоритма.
Закрытые domain choices остаются enum. Контракт регистрируется заранее;
неизвестный slot/contract — ошибка, не динамическое создание partition.
Neutral UID value contract переносится PC-0U в
`dataModel/identity/uid.py::EntityUid` (existing StrictStr/nonempty/
trimmed constraints без изменения). Existing PlacementUid в
placement/common.py остаётся alias/re-export EntityUid, не второй
definition. Общие planning/cache/validation типы не импортируют домен
placement ради world UID. Generation identity formulas app.ids не меняются.

`PlanContractId = RegistryKey[PlanContractRegistry]` объявляется в
`dataModel/planning/contracts/planContract.py`; это расширяемый реестр
деклараций providers, а не enum всех доменов внутри общего engine.
`PlanContractRegistry` содержит tuple metadata entries с уникальными id:
`id: PlanContractId`, `schema_version: SchemaVersion`,
`algorithm_version: AlgorithmVersion`. Executable codecs/providers живут
в application, не в dataModel. Для cache аналогично
`CacheContractId = RegistryKey[CacheContractRegistry]` в
`dataModel/cache/contracts/cacheContract.py`; metadata entry:
`id`, `schema_version: CacheSchemaVersion`; CacheSchemaVersion —
cache-owned strict positive int type, не импорт planning версии.
Ни registry не хранит current revision мира.

**Полные общие records:**
- `PlanScope` в `identity/planKey.py` — tagged union:
  `WorldPlanScope(kind=WORLD)` либо `RegionPlanScope(kind=REGION,
  region_uid: EntityUid)`. Discriminator `PlanScopeKind` — enum.
  Tile/LOD не входят в scope мирового layout; запроса другого tile
  недостаточно для нового размещения. Существующие scopes потребителей
  не преобразуются в строки и не смешиваются с этой осью.
- `PlanKey` там же: `world_uid: EntityUid`, `scope: PlanScope`,
  `contract_id: PlanContractId`, `schema_version: SchemaVersion`,
  `algorithm_version: AlgorithmVersion`, `input_fingerprint: InputFingerprint`.
- `PlanRef` в `identity/planRef.py`: `key: PlanKey`,
  `output_fingerprint: OutputFingerprint`. Digest имеет тот же 32-byte
  format, но отдельный nominal type от fingerprint входа.
- `PlanDependency` в `contracts/planDependency.py`:
  `slot: PlanSlot`, `ref: PlanRef`. Tuple dependencies уникален по slot,
  канонический порядок — лексикографический UTF-8 slot. Отсутствующая
  обязательная dependency — ошибка до provider build.
- `PlanRequest[I]` в `contracts/planRequest.py`:
  `key: PlanKey`, `inputs: I`, `dependencies: tuple[PlanDependency, ...]`.
  I — конкретный immutable domain input, указанный при регистрации.
  ORM World, NamedLocation, live registry, callback, ResolveContext,
  request cancellation и `dict[str, Any]` запрещены в I.
- `PlanEnvelope[T]` в `contracts/planEnvelope.py`:
  `ref: PlanRef`, `dependencies: tuple[PlanDependency, ...]`, `payload: T`,
  `diagnostics: tuple[PlanDiagnostic, ...]`. Timestamp/current-world
  pointer/source-view revision сюда не входят: один и тот же артефакт
  может быть переиспользован из другого coherent view при тех же inputs.
- `PlanBuildResult[T]` там же: `payload: T`,
  `diagnostics: tuple[PlanDiagnostic, ...]`. Provider не назначает refs
  и не меняет ключ: envelope/ref вычисляет общий PlanningService.
- `CacheContract[T]` в `cache/contracts/cacheContract.py`:
  `id: CacheContractId`, `schema_version: CacheSchemaVersion`.
  Invariant generic T связан с application binding, а не угадывается
  из JSON или имени namespace.
- `CacheKey[T]` в `cache/identity/cacheKey.py`:
  `contract: CacheContract[T]`, `item_key: CacheItemKey`.
  CacheItemKey — opaque validated 32-byte digest в том же cache module.
  Planning binding вычисляет его из canonical PlanKey; cache domain
  не импортирует planning и допускает других typed consumers.
  Начальное применение backend — planning; pack decode cache сюда
  не мигрирует. Envelope validator сверяет ref.key с expected PlanKey.
- `CacheEntry[T]` в `cache/contracts/cacheEntry.py`:
  `key: CacheKey[T]`, `value: T`. Времена LRU/cost — private backend
  metadata, они не меняют equality/value и domain fingerprint.
- `CacheLookup[T]` в `cache/contracts/cacheLookup.py` — tagged union
  `CacheHit[T](status=HIT, entry: CacheEntry[T])` и
  `CacheMiss(status=MISS)`, discriminator `CacheLookupStatus` — enum.
  MISS не имеет nullable entry. Failure не вариант MISS.

**Неизменяемость и строгая admission validation.** Public payload maps —
sorted tuple of `(typed key, typed value)` с уникальными keys; sets —
frozenset immutable элементов. Ordered полилинии/правила сохраняют свой
порядок; их нельзя сортировать ради fingerprint. Temporary mutable maps
разрешены только внутри build/materializer с отдельным владением.
Consumer index строится request-local из immutable tuple и не получает
права менять shared payload. Cache не хранит MappingProxy над чужим dict.

`application/cache/contracts/cacheBackend.py` содержит generic
`CacheBinding[T]`: `contract: CacheContract[T]`,
`codec: CachePayloadCodec[T]`; codec methods:
`validate(value: object) -> T`, `encode(value: T) -> bytes`,
`decode(encoded: bytes) -> T`, `retained_bytes(value: T) -> int`.
Validation рекурсивно проверяет actual поля даже существующих dataclass/
BaseModel instances, включая instances, созданные через construct/copy.
Приёмки только по isinstance либо TypeAdapter без instance revalidation
недостаточно. Обязательны enum membership, strict числовые типы/ranges,
обязательные поля, discriminator, отсутствие лишних полей, координатные
единицы, дубликаты ключей и cross-field invariants. Domain validator
не применяется к отсутствующим fields путём тихого default/fallback.

Canonical encoding использует явные type tags, UTF-8 strings, integer
encoding без bool/int слияния, finite floats с одной canonical encoding,
порядок declared fields, sorted unordered sets/maps. NaN/inf запрещены.
Полный codec schema version участвует в ключе; repr, pickle, Python hash,
порядок dict и pointer identity не являются fingerprint protocol.
Для RAM сохраняется immutable validated T; codec не становится второй
domain-моделью. HIT повторно проверяет entry против expected key/binding,
не доверяет одному header backend. Ошибка encode/decode/admission —
`CacheFailure` с enum reason CONTRACT_MISMATCH / INVALID_PAYLOAD /
BACKEND_FAILURE; не MISS и не молчаливый обход кэша.

**Общий sync API и ошибки.** В application:
- `CacheBackend.get[T](key: CacheKey[T]) -> CacheLookup[T]`,
  `put[T](entry: CacheEntry[T]) -> None`,
  `evict[T](key: CacheKey[T]) -> None` остаются protocol backend.
- `CacheService.get[T](binding: CacheBinding[T], key: CacheKey[T])
  -> CacheLookup[T]`; `put[T](binding, entry) -> CacheAdmission`,
  `evict[T](binding, key) -> None`. `CacheAdmission` enum:
  STORED / SKIPPED_OVERSIZE. Oversize — штатное решение resource policy,
  не повреждение payload и не потеря вычисленного результата.
- `PlanProvider[I,T].build(request: PlanRequest[I],
  dependencies: PlanDependencyReader, control: PlanBuildControl)
  -> PlanBuildResult[T]`. Provider получает готовые dependency envelopes
  только объявленных slots, не вызывает другой provider/PlanningService.
  `PlanDependencyReader.require[I,T](slot: PlanSlot,
  contract: RegisteredPlanContract[I,T]) -> PlanEnvelope[T]`
  проверяет exact ref и payload binding. Consumer cast запрещён.
  I выводится из typed contract handle; reader не вызывает его provider
  и не требует consumer-side cast для стирания input типа.
- `PlanRegistry.register[I,T](contract: RegisteredPlanContract[I,T],
  provider: PlanProvider[I,T]) -> None`; duplicate registration — ошибка.
  `RegisteredPlanContract[I,T]` в `application/planning/providers/planProvider.py`
  связывает pure metadata, input validator/fingerprinter и
  `CacheBinding[PlanEnvelope[T]]`. Его fields: `metadata`,
  `validate_inputs: Callable[[object], I]`,
  `fingerprint_inputs: Callable[[EntityUid, PlanScope, I, tuple[PlanDependency, ...]], InputFingerprint]`,
  `dependency_contracts: tuple[PlanDependencyContract,...]`, `cache_binding`.
  PC-3E/PC-4 уточнение §6.32: required `manifest:CanonicalSchemaManifest`.
  PlanDependencyContract — exact slot/id/schema/algorithm requirements §6.31-A.
  Нет current-world accessor.
- `PlanningService.get_or_build[I,T](contract: RegisteredPlanContract[I,T],
  request: PlanRequest[I], dependencies: PlanDependencyReader,
  *, wait: PlanWaitControl) -> PlanEnvelope[T]`. Повторно вычисляет
  input fingerprint и сверяет request.key; проверяет slots/refs до lookup.
  На HIT/MISS возвращает один тип и одинаковую domain диагностику.
  Отмена waiter — `PlanWaitCancelled`, deadline — `PlanWaitTimeout`;
  provider failure — `PlanBuildFailure(issues: tuple[FieldPathError,...])`;
  неверный binding/ref/request — `PlanContractFailure`. Технические ошибки
  не превращаются в valid empty plan, stale plan или domain fallback.

Failure classes принадлежат тому же service module, что соответствующий
API: CacheFailure — cacheService.py, остальные — planningService.py.
CacheFailure fields: `reason: CacheFailureReason` (перечисленные выше
три enum values), `issues: tuple[FieldPathError,...]`; PlanContractFailure:
`reason: PlanContractFailureReason` enum UNKNOWN_CONTRACT / INVALID_INPUT /
DEPENDENCY_MISMATCH / KEY_MISMATCH, `issues: tuple[FieldPathError,...]`.
PlanBuildFailure issues nonempty; остальные terminal exception types
PlanWaitCancelled/PlanWaitTimeout/PlanningBusy не несут domain payload.
Exception traceback/cause не сериализуется в envelope.

`PlanBuildControl` и `PlanWaitControl` — application-only protocols в
`application/planning/service/planningService.py`:
первый `raise_if_shutdown() -> None`, второй
`raise_if_cancelled() -> None`, `remaining_seconds() -> float | None`.
Existing CancellationToken адаптируется на request side через
`is_cancelled()`; asyncio.Event не переносится в cached данные/worker.
Sync core соответствует current sync callers; async UOW/network/pack
orchestration остаётся снаружи. Этот block не переписывает API в async.

**Single-flight и ресурсы.** Shared service имеет один bounded executor
и таблицу in-flight по exact CacheKey; обе существуют на срок жизни
container. Состояния одного build: ABSENT → BUILDING → READY либо FAILED.
Один worker вычисляет immutable результат; все waiters получают его или
ту же причину failure. FAILED удаляется из in-flight после доставки,
не сохраняется как plan; следующий запрос может повторить build.
Отмена/timeout отдельного waiter удаляет только его ожидание. Даже
отмена initiating waiter не отменяет общий worker. Shutdown останавливает
admission новых builds, будит waiters и отменяет shared work через
PlanBuildControl. Recursive dependency request из worker запрещён;
assembler передаёт готовые dependencies и не создаёт executor deadlock.

`CachePolicy` в `dataModel/cache/policy/cachePolicy.py`:
`max_retained_bytes: strict positive int`,
`max_entry_bytes: strict positive int <= max_retained_bytes`,
`eviction: CacheEvictionPolicy = LRU`, `ttl_seconds: None = None`.
`PlanningExecutionPolicy` там не размещать: это planning responsibility,
путь `dataModel/planning/policy/planningExecutionPolicy.py`, fields
`max_workers: strict positive int`, `max_pending_builds: strict positive int`.
Оба limits — обязательные application configuration inputs без выдуманного
числового fallback. Missing/invalid config — startup validation error.
LRU evicts до admission, entry сверх max_entry не кэшируется. Cost равен
размеру retained object graph (visited identity исключает двойной счёт
внутри entry) плюс retained encoded bytes, если backend их сохраняет.
Между entries shared объекты можно считать повторно: это консервативный
accounting limit, не обещание точного process RSS. In-flight resources
ограничиваются separately max_workers/max_pending_builds; cache byte
budget не объявляется лимитом всей памяти генерации мира. При полной
очереди `PlanningBusy` возвращается как техническая ошибка без изменения
геометрии/coverage. TTL изначально отключён, freshness определяется ключом.

**Revision и отсутствие второй истины.** SurfacePlanningView в
application/worldData/planning/contracts/surfacePlanningView.py — union
ReadySurfacePlanningView/NoExtentSurfacePlanningView с поимёнными
полями §6.28. Generic input bag в TARGET отсутствует.
Revision — SHA-256 canonical projection всех inputs bundle; каждый PlanKey
использует только свой input closure плюс exact dependency refs/versions.
Source revision не входит в domain key, если данный artifact не изменился.

`SurfacePlanBundle` в `.../contracts/surfacePlanBundle.py`:
`view_revision: StateViewRevision`, `world_uid: EntityUid`,
`climate_base: PlanEnvelope[ClimateBasePlan]`,
`terrain_base: PlanEnvelope[TerrainPlan]`,
`water_placement: PlanEnvelope[WaterPlacementPlan]`,
`relief: PlanEnvelope[ReliefPlan]`,
`hydrology_routes: PlanEnvelope[HydrologyRoutesPlan]`,
`river_relief: PlanEnvelope[RiverReliefPlan]`,
`hydrology: PlanEnvelope[HydrologyPlan]`,
`climate_local: PlanEnvelope[ClimateLocalPlan]`.
Все keys принадлежат одному world/scope; coherence проверяется refs
dependencies, а не равенством fingerprints разных доменов. Внешний write
orchestrator перед существующим pack/patch commit повторно проверяет
authoritative projection revision в том же UOW/guard, где защищает write.
Mismatch → отказаться от write/replan, не публиковать stale bundle.
SUPERSEDED (2026-10-24): abort-семантика заменяется штампом revision
set — см. `.cursor/plans/world-source-versioning.md`.
PlanningService не владеет transaction и не выполняет commit check.

### 6.26 PC domain payloads, стадии и стыки

**Замороженный порядок PC после §6.30 — §6.31-E.** Восемь concrete
bindings: climate_base → terrain_base → water_placement → relief →
hydrology_routes → river_relief → hydrology → climate_local. Mountain
selection остаётся внутри relief. Поля ниже дополняются exact schemas
§6.31-B/C/D; текущая legacy реализация не выдаётся за готовый target.
Domain provider не исполняет общий dependency graph: явные calls делает
SurfacePlanningAssembler через PlanningService, без нового generic DAG.

**Climate.** `dataModel/climate/planning/climatePlan.py` содержит два
payload types: `ClimateBasePlan(poles: tuple[ClimatePolePoint,...],
bbox: GridBBox | None, default_zone: ClimateKey,
profiles: tuple[ResolvedClimateProfile,...], blend: ClimatePoleBlendDefaults)`
и `ClimateLocalPlan(anchors: tuple[ClimateAnchorPoint,...])`.
`ClimatePlan` — alias union этих payloads для inventory, не T для
sampler/registration: каждая binding имеет конкретный payload type.
`ClimateKey = RegistryKey[WorldClimateZoneRegistry]`; registry позволяет
custom keys, поэтому ClimateZone enum не заменяет этот тип.
Profiles unique по key и включают default и все pole keys;
неполная/невалидная ссылка разрешается на input boundary с diagnostic,
не через live lookup внутри sampler. `ResolvedClimateProfile` в том же
climatePlan.py: `key: ClimateKey`, `values: ClimateZoneProfileData`.
Existing ClimateZoneProfileData переиспользуется целиком: его пять scalar
fields сохраняются (temperature/elevation/rainfall и variances).
Existing builtin ClimateZoneProfile с system_climate:str не изменяется:
input adapter переносит resolved key и значения в typed projection;
вторая таблица enum defaults не создаётся.
Blend defaults берутся из существующего CLIMATE_POLE_BLEND POJO.

Pure point definitions перемещаются в
`dataModel/climate/planning/climatePoints.py`: ClimatePolePoint сохраняет
gx,gy,base_temperature,weight,location_uid,source,system_climate_zone,
pole_kind; типы gx/gy GridX/GridY, weight finite positive float,
location_uid EntityUid|None, source existing PoleSource,
pole_kind existing PoleKind, system_climate_zone ClimateKey.
ClimateAnchorPoint сохраняет gx,gy,system_climate_zone,location_uid,source;
source — перемещённый existing AnchorSource enum, без копии.
Existing application modules реэкспортируют те же классы.
`ClimatePlanSampler.sample(plan: ClimateBasePlan, gx: GridX, gy: GridY)
-> PoleClimateSample`: не принимает World; sample definition переносится
в тот же climatePoints.py с ClimateKey/EntityUid types и existing
elevation/temperature fields. ClimateAnchorField nearest читает только
ClimateLocalPlan. Frozen base не включает anchors, зависящие от воды.

**Terrain / water placement.** `dataModel/terrain/planning/terrainPlan.py`:
`TerrainPlan(bbox: GridBBox, surface_z:
tuple[tuple[SurfaceGridCoord,FineZ],...])`; ключи unique, внутри bbox,
полное покрытие inclusive GridBBox, значения в resolved world z bounds.
World UID/topology/revisions не копируются из envelope в каждый cell.
`.../planning/waterPlacementPlan.py`:
`WaterPlacementPlan(coordinate_space: CoordinateSpace, topology: WorldTopology,
records: tuple[ResolvedWaterPlacement,...], basin_specs: tuple[BasinSpec,...])`.
Empty records/specs — нормальный результат отключённой/необъявленной воды,
не ошибка build. Диагностика в envelope, preparation/ORM/ResolveContext
не кэшируются. Records/specs имеют одно и то же множество source_uid;
каждый spec связывается с record по source_uid, не по позиции tuple;
пара footprint/level/kind/liquid совпадает у record и spec.
Baseline coordinate_space строго WORLD_SURFACE_GRID; произвольное
enum value здесь rejected cross-field validator, не interpreted fine.
`WaterPlacementPlanProvider` находится в
`application/worldData/generators/terrain/planning/waterPlacementPlanProvider.py`.
Это baseline wrapper существующего common placement path; новый GEO-1
SourceUnion ещё требует §6.29-B, PC baseline schema его не подменяет.

**Relief.** `dataModel/terrain/relief/planning/reliefPlan.py`:
`ReliefPlan(surface_z: tuple[tuple[SurfaceGridCoord,FineZ],...],
mountain_layout: MountainLayout,light:LightReliefPlan)` —
полная post-mountain/ravine/basin, pre-river coarse поверхность;
mountain_layout — единый frozen выбор гор для всех consumers по §6.30
(exact record fields заморожены в §6.31-B/C).
Dependencies хранятся в envelope, включая WaterPlacementPlan.
BasinSpec переносится в `dataModel/terrain/relief/bathymetry/basinSpec.py`
с существующими 7 fields: source_uid EntityUid, kind BasinKind,
liquid MaterialKey, footprint frozenset[Coord], z_water_level int,
floor_z int, bands HydrologyBands. В этом baseline Coord именно
coarse WorldTopology XY. В current pre-1.4 pass объявленные fine данные
проектирует project_declared_hydrology ДО preparation/resolver;
record.footprint_cells уже coarse, хотя alias в common record называется
FineCell. basinSpecFactory лишь передаёт этот же footprint, повторной
проекции не делает. WaterPlacementPlan явно помечает actual coordinate
space; получать его records как fine coordinates без conversion запрещено.
Validator требует непустой footprint,
floor_z < z_water_level, корректные kind/liquid/bands, world z bounds.
Generated profile extension — будущий GEO-1 contract GAP-FIELD,
его нельзя выдать за существующий scalar BasinSpec.

**Hydrology.** `dataModel/hydrology/planning/hydrologyPlan.py`:
`HydrologyPlan(coarse_surface_z:
tuple[tuple[SurfaceGridCoord,FineZ],...], coarse_hydro:
tuple[tuple[SurfaceGridCoord,MapCellHydrology],...], sparse_fine_hydro:
tuple[tuple[FineXY,MapCellHydrology],...], fine_z_overrides:
tuple[tuple[FineXY,FineZ],...], water_bodies: tuple[WaterBody,...],
physical_unions: tuple[PhysicalWaterUnion,...],
declared_paint: DeclaredWaterPaint)`.
FineXY — alias tuple[FineX,FineY] в shared coordinateTypes.py; existing
FineGridCoord с z не используется как ключ XY-колонки.
MapCellHydrology/WaterBody/PhysicalWaterUnion переиспользуются целиком с
recursive validation. DeclaredWaterPaint — frozen L0 declared-geometry
payload (typed records, без ссылок на World/locations); producer/
consumer контракт — §6.29-M, consumer cutover — PC-10. Поверхность
полная, hydro/overrides sparse и unique.
HydrologyPlan не содержит mutable HydrologyResult/heightmap/landforms Any.
River geometry, drainage и waterfall, нужные materialization, уже
представлены final surface/MapCellHydrology; неиспользуемый legacy result
не сериализуется «на всякий случай». RiverRouteDiagnostic конвертируется
в envelope diagnostics. Если caller inventory обнаружит отдельного
consumer river_segments/landforms результата surface preparation,
PC-0 обязан добавить typed payload до cutover, не сохранять Any.

**Producer → consumer сравнение полей baseline:**
- ClimateBasePlan полностью закрывает sample: poles,bbox,default_zone,
  profiles,blend; live World/profile_for в sampler удаляются.
- TerrainPlan выдаёт именно surface_z+bbox, читаемые water pass;
  materializer получает отдельный mutable working copy при необходимости.
- WaterPlacementPlan выдаёт tuple[BasinSpec] и topology для relief;
  здесь record и spec оба coarse, declared fine → coarse conversion
  уже выполнен project_declared_hydrology. Проверка сравнивает actual
  space/value, а не название FineCell alias. Новый GEO-1 fine placement
  не подключается к этому baseline binding без явного adapter.
- ReliefPlan выдаёт pre-river surface для coarse hydro и fine carve;
  последнее не читает уже carved surface. HydrologyPlan coarse_surface_z
  выдаёт final surface для anchors и fine upsample.
- Bundle → legacy SurfaceTerrainContext: pole_field из climate_base;
  local_field из climate_local; coarse_hm и coarse_surface_z из hydrology;
  coarse_relief_z из terrain_base (existing поле означает PRE-1.4 base,
  несмотря на имя); остальные hydro fields — из HydrologyPlan.
  Нельзя подставить ReliefPlan.surface_z в coarse_relief_z: это изменит
  current L0 baseline/double-rise semantics.
- water_bodies/physical_unions сохраняются в bundle через HydrologyPlan;
  старый eight-field context остаётся compatibility view, не единственным
  storage этих данных. Legacy mutable dicts — отдельные copies, не cache T.

### 6.27 Injection, диагностика и исполняемые проверки PC

**Composition root проверен по коду:** `core/container/__init__.py::Container`
соединяет `WorldDataWiring`/`PacksWiring`;
`core/container/worldData.py` создаёт terrain/pack/materialization services;
`core/container/packs.py` создаёт pack read facades. Здесь создаются
один MemoryCache, CacheService, PlanRegistry, PlanningService и
SurfacePlanningAssembler на container, через lazy factory methods в
existing WorldDataWiring. Нового файла в container не требуется
(сейчас 9 файлов). Application singleton cache не создаётся в генераторе.

Целевая signature assembler:
`prepare(view: SurfacePlanningView, *, wait: PlanWaitControl)
-> SurfacePlanBundle | None`; None только для existing случая отсутствия
surface bbox. Capture authoritative input view выполняет caller adapter
перед assembler; сам assembler не загружает ORM/SQL.
`to_legacy_context(bundle: SurfacePlanBundle) -> SurfaceTerrainContext`
в `composition/surfacePlanningAssembler.py` создаёт request-local view.

**Разрешение противоречия old API ↔ injection:** обещание полностью
неизменной signature old free functions уточняется: старые positional и
keyword параметры сохраняются, добавляется обязательный keyword-only
`planning: SurfacePlanningAssembler` и explicit input-view adapter.
Никакого default service locator/global/per-request cache/uncached второго
пути. Это намеренное внутреннее API изменение; все callers и тесты
переключаются атомарно PC-9. Старые type import paths реэкспортируются,
но вызов без planning после cutover должен давать явную TypeError.
`hydrology_generator` у shim убирается после переноса DI на provider
registration; тесты инжектируют provider double через test container.
Сохранение этого аргумента и одновременный cache HIT с другим generator
было бы некорректно, поэтому оно не считается compatibility требованием.

Полный production caller ledger для PC-9:
`materialize/terrainBatchOrchestrator.py`,
`materialize/worldSurfaceMaterializationOrchestrator.py`,
`pack/bake/packMaterializationOrchestrator.py`,
`pack/bake/worldMapBakeOrchestrator.py`,
`pack/bake/packCompletenessClassifier.py`,
`pack/read/wildernessRegionReadService.py`.
Constructor injection проводится также через
`pack/read/packReadServices.py::build_pack_read_services`,
`pack/read/packLoadingProgressFacade.py` и factories WorldDataWiring/PacksWiring.
`api/routes/map.py` создаёт WildernessRegionReadService с полученным
container assembler. Thin route не собирает план и не создаёт cache.
PackCompletenessClassifier принимает готовый context либо injected
assembler; скрытый `prepare(...без DI)` удаляется.

**Диагностика.** Pure `FieldPathError`, `ReferenceIssueContext` и
`ReferenceIssueReason` перемещаются без копии в
`dataModel/validation/diagnostics/fieldPathError.py`; old
`application/jsonValidation/types.py` реэкспортирует те же symbols,
сохраняя reports/HTTP mapping на application side.
`PlanDiagnostic` в `dataModel/planning/diagnostics/planDiagnostic.py`:
`issue: FieldPathError`, `disposition: PlanDiagnosticDisposition` enum
ERROR / FALLBACK / NOTICE. Это immutable факт, не log record.
Build не логирует domain issues и не захватывает request ctx;
существующие emitter helpers в затронутом path переводятся на collect,
без дублирующего вывода из legacy warn_once.

После получения bundle shim/request orchestrator собирает diagnostics
в явном phase порядке §6.26, дедуплицирует existing report_issues semantics
и ровно один раз передаёт ERROR/FALLBACK в request ResolveContext/report_issues;
NOTICE маршрутизирует existing info/default emitter, не в ctx.errors.
Validation: ERROR/FALLBACK дают явную ошибку мира; NOTICE не становится
ошибкой. Runtime: FALLBACK обязательно проходит existing log_issues →
общий project logger/WarningError; ERROR оставляет соответствующий объект UNRESOLVED без его effects;
независимые результаты не удаляются. Producer-level невозможность вернуть
валидный partial payload даёт PlanBuildFailure. Ошибка без declared
fallback не маркируется valid fallback. NOTICE использует existing
default/info semantics. HIT/MISS/in-flight wait не меняют состав или
severity diagnostics. Cache/backend failures проходят существующий
application error logging boundary отдельно; новый logger не вводится.

**Новые leaf folders по правилу композиции:** planning/identity 3 файла
с init; planning/contracts 5 с init; planning/diagnostics 2;
planning/policy 3; validation/diagnostics 3; climate/planning 3;
terrain/planning 3; hydrology/planning 2. В существующие переполненные
roots новые файлы не добавляются. Application provider/controller additions
проверяются по §5.4 и actual count перед implementation каждого шага.

**Планируемые suites и точные команды, из корня репозитория:**
`$env:PYTHONPATH='backend'`, затем:
- PC-1/1C/1T/1R/1H:
  `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/planning/contracts -p "test_*.py"`.
  Files: test_contracts.py (keys/generics/strict validation),
  test_domain_payloads.py (четыре domain groups + placement),
  test_geometry.py (units/old symbol identity), плюс init — 4.
- PC-2/3:
  `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/cache -p "test_*.py"`.
  Files: test_service.py, test_memory_backend.py, test_admission.py,
  плюс init — 4. Wrong binding/corruption не MISS; oversize возвращает
  результат без cache admission; LRU bounded; immutable nested values.
- PC-4…8:
  `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/planning/providers -p "test_*.py"`.
  Files: test_planning_service.py, test_domain_providers.py,
  test_diagnostics.py, test_concurrency.py, плюс init — 5.
  Concurrent same key один build; failed build retry; waiter cancel;
  unrelated view edit HIT; dependency edit MISS; sampler без World.
- PC-9…12:
  `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/planning/consumers -p "test_*.py"`.
  Files: test_wiring.py, test_l0_l2.py, test_revisions.py,
  test_no_second_truth.py, плюс init — 5. Real container path,
  edit→replan→on-demand materialize, guarded stale write rejection,
  cache clear/restart equality и phase-specific baseline comparison.
- Regression:
  `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_water_placement_pass.py"`;
  аналогичная команда с test_relief_objects_z.py, test_hydrology_hy12_rivers.py,
  test_pack_bake_modes.py, test_detailed_bake_c11.py.
- Type checks: новый `backend/tests/typing/planning/pyrightconfig.valid.json` наследует existing
  pyrightconfig.cascade.json и включает только новые contracts/providers
  и `backend/tests/typing/planning/valid/` (тематические positive contracts).
  `npx --no-install pyright --project backend/tests/typing/planning/pyrightconfig.valid.json` — exit 0.
  Executable prerequisite проверяется отдельно: 2026-10-23 local
  node_modules/.bin/pyright.cmd доступен, version 1.1.414. Наличие npx
  само по себе не означает установленный pyright. Отсутствие
  инструмента — failed prerequisite, не успешный typecheck и не основание
  автоматически скачивать зависимости в planning-only заходе.
  Negative config `backend/tests/typing/planning/pyrightconfig.invalid.json`
  включает invalid.py: climate entry под hydro key, wrong provider request,
  wrong dependency payload, FineX вместо GridX, mutation tuple payload.
  `npx --no-install pyright --project backend/tests/typing/planning/pyrightconfig.invalid.json`
  — ожидаемые diagnostic codes для каждого помеченного case, не просто
  произвольный nonzero от пропавшего executable/import.
Эти suites/configs здесь только запланированы, не созданы/не запущены.

**Статус после следующего уточнения:** input freeze/capture/fingerprints
завершены в §6.28; closed design registry — §6.13/6.29-L. Этот раздел
задаёт DI/report/checks и не оставляет input schema на coding-agent choice.

### 6.28 Завершение PC-0: inputs, capture и fingerprints

Нормативное уточнение TARGET от 2026-10-22: полная схема input projections
и capture API для §6.25–6.27. Это
спецификация будущего кода; она не выдаёт текстовую сверку за выполненный
runtime/typecheck. Все поля ниже required; nullable указан явно.

**Повторное использование POJO без mutable вложений.** Не вводить
FrozenWorld/универсальный JSON tree/вторую копию WorldHydrology. Для
передаваемых source POJO использовать существующие модели с immutable
collection fields. Отдельный prerequisite PC-0I переводит:
- `spatial/regionShape.py`: PolygonShape.vertices и CorridorShape.path
  в tuple[Point,...]; остальные формы, EdgeNoise уже scalar/frozen.
- `hydrology/declaredCoastline.py::DeclaredCoastline.path`,
  `declaredLake.py::DeclaredLake.shoreline` — tuple[HydrologyWaypoint,...].
- `hydrology/declaredRiver.py::DeclaredRiver.route_location_uids` — tuple[str,...],
  segments — tuple[DeclaredRiverSegment,...]. Вложенные waypoint/mouth/
  segment models сохраняют existing поля и frozen semantics.
- `terrainMasks/mountain/specs.py`: MountainSpec.sides — tuple[ReliefSideSpec,...];
  MountainRangeSpec.spine — tuple[Point,...], peaks — tuple[MountainSpec,...],
  peak_spacings_m — tuple[int,...], saddles — tuple[MountainSaddleSpec,...].
- `terrainMasks/worldTerrainMasks.py::MountainsCategoryPolicy.sides` —
  tuple[ReliefSideSpec,...]. Form/side/range-side/ObjectReliefPickPolicy
  уже состоят из scalar/frozen fields и переиспользуются, не клонируются.

Это изменения внутреннего collection contract, а не wire schema: JSON
arrays остаются arrays, missing/null/default ограничения сохраняются.
Annotation policies DefaultWhenMissing/StrictOnWire не заменяются общим
приведением. Там, где алгоритм требует list, он создаёт собственный list
из tuple; spec не мутируется. Методы resolved_sides/constructor helpers
обновляются в том же шаге. Общие spatial формы остаются своим единственным
контрактом, в planning не создаётся вторая PolygonShape. City/location
cache/planner не меняется. Wire/list round-trip и все mutating call sites
этих конкретных полей входят в PC-0I acceptance; новые root файлы не нужны.

**Новые input records и владельцы (dataModel):**
- `spatial/grid/gridSettings.py::SurfaceGridSettings`:
  `fine_span: strict positive int`, `light_side: strict positive int`.
  fine_span — fine XY cells на coarse cell; light_side — light cells
  на coarse cell. Значения получаются existing coordinate/settings
  resolver, не из констант cache. Папка grid: 5 файлов с init.
- `climate/planning/inputs/climateBaseInput.py::ManualPoleInput`:
  `location_uid: EntityUid`, `position: FineXY`, `kind: PoleKind`,
  `zone: ClimateKey | None`. ClimateBaseInput:
  `seed: int`, `bbox: GridBBox | None`, `fine_span: int`,
  `mode: ClimatePoleMode`, `preset: ClimatePolePreset`,
  `peak_min: int`, `peak_max: int`, `default_zone: ClimateKey`,
  `manual_poles: tuple[ManualPoleInput,...]`,
  `profiles: tuple[ResolvedClimateProfile,...]`,
  `blend: ClimatePoleBlendDefaults`. profiles включает default/manual/
  preset keys с resolved values; builder не читает registry. Порядок
  manual_poles сохраняется: current first-pole fallback зависит от него.
- `climate/planning/inputs/climateLocalInput.py::ClimateLocalInput`:
  `manual: tuple[ClimateAnchorPoint,...]`,
  `admin: tuple[ClimateAnchorPoint,...]`,
  `feature_policy: ClimateFeaturePolicy`.
  ClimateFeaturePolicy в том же файле: `scale: ProminenceScale`,
  `peak_min: int`, `basin_min: int`, `liquid_min: int`,
  `max_features: int`, `manual_exclusion_grid: int`.
  ProminenceScale/ProminenceThresholds pure definitions перемещаются из
  anchorDetect.py с re-export; existing METRIC/50/25/10/32/2 defaults
  объявляются единственным POJO в этом domain file и потребляются
  обоими путями. Не менять значения при cache migration. Inputs содержат
  только declared manual/admin points; auto anchors создаёт provider
  из final surface dependency, capture не выполняет feature detection.
- `terrain/planning/inputs/terrainBaseInput.py::TerrainBaseInput`:
  `seed: int`, `bbox: GridBBox`, `z_min: FineZ`, `z_max: FineZ`,
  `grid: SurfaceGridSettings`. z_min <= z_max; bbox inclusive.
- `terrain/planning/inputs/waterPlacementInput.py::WaterAnchorInput`:
  `source_uid: EntityUid`, `position: FineXY`,
  `subtype: GeographicSubtype | None`.
  WaterPlacementInput: `enabled: bool`, `resolution_mode: ResolutionMode`,
  `default_water_level: FineZ`,
  `seas: HydrologySeasPolicy`, `lakes: HydrologyLakesPolicy`,
  `basins: tuple[DeclaredBasin,...]`,
  `coastlines: tuple[DeclaredCoastline,...]`,
  `declared_lakes: tuple[DeclaredLake,...]`,
  `anchors: tuple[WaterAnchorInput,...]`, `topology: WorldTopology`,
  `grid: SurfaceGridSettings`, `z_min: FineZ`, `z_max: FineZ`,
  `liquid_keys: frozenset[MaterialKey]`.
  Это baseline PC input, до добавления GEO-1 source union §6.29-B.
  Seas/lakes policy POJO и их bands/shore состоят из frozen scalar
  values; весь WorldHydrology с mutable root lists сюда не передаётся.
- `terrain/relief/planning/inputs/reliefPlanInput.py::MountainAnchorInput`:
  `location_uid: EntityUid`, `position: FineXY`.
  ReliefPlanInput: `seed: int`, `masks_enabled: bool`,
  `mountains: MountainsCategoryPolicy`, `ravines: RavinesCategoryPolicy`,
  `declared_mountains: tuple[MountainDeclareEntry,...]`,
  `anchors: tuple[MountainAnchorInput,...]`,
  `grid: SurfaceGridSettings`, `z_min: FineZ`, `z_max: FineZ`,
  `mountain_templates:tuple[MountainTemplateInput,...]`,
  `mountain_pick:ReliefContextPickPolicy`,
  `terrain_merge:tuple[TerrainMergeEntry,...]`. Exact leaf fields §6.31-B.
  Category_enabled и автораcстановка исполняются существующим mountain
  kernel, не capture. Basin specs/topology приходят из dependency.
- `hydrology/planning/inputs/hydrologyPlanInput.py::HydrologyAnchorInput`:
  `location_uid: EntityUid`, `position: FineXY | None`, `z: FineZ | None`,
  `subtype: GeographicSubtype | None`.
  HydrologyPlanInput: `enabled: bool`, `seed: int`,
  `resolution_mode: ResolutionMode`,
  `scopes: frozenset[HydrologyScope]`,
  `default_water_level: FineZ`, `seas: HydrologySeasPolicy`,
  `lakes: HydrologyLakesPolicy`, `rivers: HydrologyRiversPolicy`,
  `declared_rivers: tuple[DeclaredRiver,...]`,
  `coastlines: tuple[DeclaredCoastline,...]`,
  `declared_lakes: tuple[DeclaredLake,...]`,
  `anchors: tuple[HydrologyAnchorInput,...]`,
  `topology: WorldTopology`, `grid: SurfaceGridSettings`,
  `z_min: FineZ`, `z_max: FineZ`, `liquid_keys: frozenset[MaterialKey]`,
  `change_uid: EntityUid`.
  scopes — existing bootstrap set, не LANDFORMS; новый scope нельзя
  активировать без отдельного typed output contract. HydrologyScope
  переносится из application/types.py в ранее указанную enums/planning/.
  ResolutionMode: RUNTIME / VALIDATE_ONLY в общих validation/enums;
  не domain generation behavior HydrologyExecutionMode.
  Разница legacy reroute допустима только как explicit mode-dependent
  river policy, оба режима имеют разные keys. ResolveContext в I нет.

Отдельные inputs/ подпапки имеют максимум 3 файла с init. Baseline
поля `seas/lakes` сохраняют existing значения; §6.29 задаёт последующую
атомарную замену old flags на generation channels, не обратный импорт
новых nullable полей в старые bool consumers. `MaterialKey` membership
проверяется на capture boundary; список жидкостей fingerprinted там,
где наличие material влияет на допустимость declared inputs.

**Source → input полевая карта, без скрытого World accessor:**
- seed — только `app.ids.seed_int(world)`, current MD5 projection
  seed_root(world)=world_uid сохраняется. Cache digest не становится
  новым generation seed. name/created_at/current_tick/pack timestamps
  и UI labels не читаются этими kernels и не входят в domain keys.
- bbox — existing grid_bbox_from_locations: declared WorldBounds либо
  AABB статических map_x/map_y с resolved grid_bbox_padding; is_mobile
  нужен только при выборе статических anchors. Готовый bbox и span
  входят в inputs, сырые ORM locations не сохраняются.
- grid — resolved global_cell_size_m/fine_cells_per_map_cell через
  existing map_cell_fine_span и world_map_cells_per_tile/light side
  resolver. Источники настроек разрешаются один раз, не двумя truthiness
  цепочками. topology — resolved world_topology_mode + WorldBounds.
- manual poles — только static climate_pole location_uid/map_x/map_y/
  system_location_subtype/system_climate_zone; subtype превращается в
  existing PoleKind через existing infer policy. Manual/admin anchors —
  existing type filters, координаты, climate key и source enum.
- mountains — WorldTerrainMasks.enabled/default_mountains/default_ravines/
  declared_mountains, geographic mountain/peak anchors. Лишние roads/
  landcover настройки не попадают в coarse relief key.
- water — WorldHydrology.enabled/default_water_level/default_seas/
  default_lakes/declarations, geographic anchors; canonical coarse
  projection делается внутри placement provider, не дважды на capture.
- rivers — только WorldHydrology.default_rivers/declared_rivers,
  геометрия coastlines/lakes для existing legacy loader, anchors всех
  location_uid, которые могут быть source/mouth/via refs, sea/lake
  policy для basin classification. RiverTypeClassify уже вложен в
  rivers policy. Connection graph не источник: buildHydrologyMasterInput
  явно игнорирует nodes/edges. Эти ORM rows не входят в fingerprint.
- Source UID/topology/phase поля dependency проверяются по refs; ни
  hydration current pack, ни сохранённый предыдущий carve не источник.

Проверенные места: poleResolve.py::resolve_pole_field;
terrain/passes/{bbox,surfacePass}.py; mountains/collect.py;
hydrology/load/{buildHydrologyMasterInput,loadDeclaredHydrology}.py;
riverNetworkAssembler.py; shore/fineHydrologyIndex.py;
climate/{anchorCollect,anchorAssign}.py. PC-5/7/8 выделяют typed kernels
из этих функций: не создают synthetic ORM World внутри provider и не
вызывают old worldRow accessor по скрытому World.

**Полный capture API и view.** В
`application/worldData/planning/composition/surfacePlanningCapture.py`
класс SurfacePlanningCapture, domain world-surface orchestration,
application layer. Единственный метод:
`capture(world: World, locations: Sequence[NamedLocation], *,
mode: ResolutionMode,mountain_templates:tuple[MountainTemplateInput,...],
resolve_ctx: ResolveContext) -> SurfacePlanningView`.
Он нормализует/валидирует POJO, разрешает refs и координатные настройки,
строит перечисленные projections; НЕ строит poles/heightmap/mountains/
placements/fill/auto anchors и не читает cache/SQL/Pack. Caller передаёт
world/locations из одной draft либо transaction read view. Root query
adapter отвечает за coherent read и loader order.

В `contracts/surfacePlanningView.py` SurfacePlanningView — union:
- ReadySurfacePlanningView: `kind=READY`, `world_uid: EntityUid`,
  `revision: StateViewRevision`, `climate_base: ClimateBaseInput`,
  `terrain_base: TerrainBaseInput`, `water_placement: WaterPlacementInput`,
  `relief: ReliefPlanInput`, `hydrology: HydrologyPlanInput`,
  `climate_local: ClimateLocalInput`, `river_relief:RiverReliefInput`,
  `hydrology_final:HydrologyFinalInput`,
  `capture_diagnostics: tuple[PlanDiagnostic,...]`.
- NoExtentSurfacePlanningView: `kind=NO_EXTENT`, `world_uid`, `revision`,
  `capture_diagnostics`. Discriminator SurfacePlanningViewKind enum
  в том же application contract file. Отсутствие bbox не подменяется
  фиктивной terrain grid. prepare(NoExtent...) возвращает None.

Значения nullable сохраняют authored смысл. Capture issues, зависящие
только от wire/default/reference provenance, публикуются через request
ctx при КАЖДОМ capture, включая будущий HIT. Они не привязываются к
чужому envelope. Provider diagnostics зависят только от frozen I и
dependencies и кэшируются в envelope. Так одинаковые resolved значения
не переносят неправильный authored/default path из другого запроса.
Raw field-presence metadata не требуется в cache key, если оно влияет
только на capture diagnostics. Если provenance меняет domain policy
действие, это explicit typed поле resolved policy input, fingerprinted.

SurfacePlanningAssembler.prepare принимает union выше. Старые free
functions получают required `planning: SurfacePlanningAssembler` и
`capture: SurfacePlanningCapture`, optional existing resolve_ctx; mode
адаптируется из ctx.validate_only в ResolutionMode на boundary.
nodes/edges остаются optional compatibility args, но не provider inputs;
hydrology_generator удаляется по §6.27. Container injects обе зависимости,
без global locator. composition/ содержит assembler/planProviders/capture
и init: 4 файла. Capture не является вторым planning coordinator.

**Exact fingerprint closure.** Для всех восьми PC bindings:
`F = SHA256(canonical(contract_id, input_schema_version,
algorithm_version, world_uid, scope, inputs I, sorted dependencies))`.
Input schema version — зарегистрированная schema_version PlanKey,
не поле JSON мира. Cache key проверяет exact полный PlanKey.
Output digest — SHA256(canonical(payload, dependencies, diagnostics)):
не включает timestamps/view revision/cache-hit marker. Обе функции
используют codec §6.25. Typed NewTypes InputFingerprint/OutputFingerprint
различны, оба 32 bytes; PlanRef.output_fingerprint — OutputFingerprint.

Binding ledger:
- climate_base: весь ClimateBaseInput; dependencies empty.
- terrain_base: весь TerrainBaseInput + climate_base ref.
- water_placement: весь WaterPlacementInput + terrain_base ref.
- relief: весь ReliefPlanInput + climate_base/terrain_base/water_placement refs.
- hydrology_routes: весь HydrologyPlanInput + relief/water_placement refs.
- river_relief: весь RiverReliefInput + relief/hydrology_routes refs.
- hydrology: весь HydrologyFinalInput + relief/hydrology_routes/river_relief refs.
- climate_local: весь ClimateLocalInput + climate_base/hydrology refs.
Скрытых global constants, меняющих ответ без algorithm/schema version,
быть не должно. Legacy algorithm constants остаются именованными
domain POJO/declarations, а изменение их значения меняет соответствующую
version. Если constant разрешён как world policy knob — он входит в I.

StateViewRevision = digest канонической source projection всех восьми
inputs, кроме resolution_mode и request-local capture diagnostics: mode — request policy,
не revision authoritative world state. При guard source пере-capture
выполняется с тем же mode; состояние сравнивается без mode. Не сравнивать
digest только effective hydro result с authoritative source revision.
Эквивалентные неупорядоченные наборы сортируются по UID; ordered paths,
manual anchor order и списки с first-match semantics сохраняют порядок.
Перестановка двух manual poles НЕ считается эквивалентным входом,
пока действует legacy first-only fallback. Validation выявляет multiple
poles; runtime сохраняет fallback с обязательным existing issue/log.

**Контроль совместимости PC (design-level PASS):**
1. Provider registry имеет ровно I/T pairs:
   ClimateBaseInput→ClimateBasePlan; TerrainBaseInput→TerrainPlan;
   WaterPlacementInput→WaterPlacementPlan; ReliefPlanInput→ReliefPlan;
   HydrologyPlanInput→HydrologyRoutesPlan; RiverReliefInput→RiverReliefPlan;
   HydrologyFinalInput→HydrologyPlan; ClimateLocalInput→ClimateLocalPlan.
2. Каждый consumed dependency slot §6.26 имеет ровно такой output type;
   bbox/scale/topology и z units не восстанавливаются из opaque UID.
3. Все world/settings/anchor reads перечисленных kernels покрыты I
   или refs; landforms scope отключён в baseline, nodes/edges ignored.
4. Different execution modes не используют общий river result cache entry;
   unrelated UI edit не меняет I, geometry/policy/registry edit меняет.
5. Existing 7-field BasinSpec mapper сохраняет coarse units; source
   projection и cached output не переопределяют физический WaterBody.
PASS здесь — ручная field/type/semantics сверка TARGET specification.
Executable positive/negative checks выполняются при PC implementation;
они не объявлены запущенными для ещё не созданных modules.

### 6.29 Закрывающие TARGET contracts для реестра §6.13

Ниже окончательная design specification вместо перечисленных в §6.13
недостающих схем. DESIGN_CLOSED означает определённый target с проверкой
стыков и implementation acceptance, а не уже изменённый production код.
Исторические причины gaps сохраняются как evidence; выполнять старые
предложения вместо контрактов этого раздела запрещено.

#### A. CATEGORY cascade и единственный persisted owner

`CategoryWaterGenerationSettings` объявляется в existing target
`dataModel/hydrology/generation/waterGenerationSettings.py` рядом с
World/Body types. У всех трёх типов ровно water_fraction/autoresolve/
strategy с nullable defaults None и общими constraints §4.
Category selector `WaterGenerationCategory` enum SEA / OCEAN / LAKE
находится в `hydrology/enums/planning/waterGenerationScope.py` рядом с
осью. INLAND_SEA использует SEA category, RIVERS в эту ось не добавляется.

Persisted paths:
- WORLD: WorldHydrology.generation.{water_fraction,autoresolve,strategy}.
- CATEGORY SEA: default_seas.sea_generation.{те же три поля}.
- CATEGORY OCEAN: default_seas.ocean_generation.{те же три поля}.
- CATEGORY LAKE: default_lakes.generation.{те же три поля}.
- BODY: source.generation.{те же три поля}.
- ROOT terminal: WaterGenerationDefaults.water_fraction=0.60,
  autoresolve=False, strategy=CONTINENTAL_NOISE.
Default factories создают пустые source settings с None; не назначают
ROOT defaults на WORLD/CATEGORY/BODY. Sea policy больше не наследует
общий MaskCategoryPolicy.autoresolve: у неё остаётся enabled и две
category settings. Lakes policy убирает inherited autoresolve после
перехода на generation.autoresolve; rivers policy сохраняет свой
отдельный default_rivers.autoresolve и не мигрирует вместе с GEO-1.

Для каждого P из {WATER_FRACTION,WATER_AUTORESOLVE,WATER_STRATEGY}
единственная linked-field карта: defaults.P → world_settings.P →
category_settings.P → body_settings.P. Defaults — CascadeDefault,
source scopes — ROOT/WORLD/CATEGORY/WATER_BODY. FieldRef выбирает
непосредственный P у соответствующего source model; nested source
object передаёт caller как экземпляр, не через nested selector.
Один prototype CATEGORY channel связывается с выбранным sea/ocean/lake
экземпляром. Декларация edge ровно на одной стороне; verifier достраивает
reverse edge. BODY siblings получают разные extend parent contexts,
override одного тела не протекает в другое. VALUE semantics, без RNG.

Legacy normalize mapping выполняет owning POJO pre-validator:
autoresolve_coastal_sea → sea_generation.autoresolve;
autoresolve_open_ocean → ocean_generation.autoresolve;
default_lakes.autoresolve → default_lakes.generation.autoresolve.
Only-present legacy keys мигрируются, explicit False сохраняется.
Absent old key не превращается в True. При одновременном old/new key
равные значения допускаются и old удаляется; разные — validation error
GENERATION_SETTINGS_CONFLICT, без runtime guessing. Persist/export
содержит только new paths; patch missing=no change, null=inherit.
Нормализация old keys не становится вторым runtime cascade.

Canonical domain priority defaults: default_seas.placement_specificity=1,
default_lakes.placement_specificity=1; authored source None наследует
именно эти живые POJO fields. Rivers default этим шагом не меняется.
Common terminal PlacementPolicyDefaults.placement_specificity=0.
Positive domain defaults вносятся в код только вместе с production
switch J ниже; включить общий zero-disable на old defaults=0 запрещено.

#### B. Source union и подготовленные metadata

В `dataModel/hydrology/sources/proceduralWaterSource.py`:
`ProceduralWaterSource(source_uid: EntityUid,
generation_region_uid: EntityUid, kind: BasinKind, liquid: MaterialKey,
z_water_level: FineZ | None, generation: BodyWaterGenerationSettings,
placement_specificity: Specificity | None)`.
source_uid/generation_region_uid/kind/liquid required; optional values
имеют None defaults, generation — пустой settings factory. Kind здесь
только SEA/OCEAN/INLAND_SEA/LAKE. Нет fake footprint/floor_z/location.
WorldHydrology.procedural_bodies — tuple[ProceduralWaterSource,...],
default empty, одна persisted коллекция. `source_uid` уникален во всём
water source universe, включая legacy source location_uid.

`.../sources/waterDesignSource.py::WaterDesignSource` — discriminated union:
AuthoredBasinSource(kind=BASIN, value: DeclaredBasin),
AuthoredLakeSource(kind=LAKE, value: DeclaredLake),
CoastlineWaterSource(kind=COASTLINE, value: DeclaredCoastline),
ProceduralSource(kind=PROCEDURAL, value: ProceduralWaterSource).
Discriminator WaterDesignSourceKind enum в том же module. Это derived
typed wrappers существующих source objects, не дополнительный persisted
список и не ослабление DeclaredBasin invariants. Coastline wrapper
принимает только purpose=WATER_SOURCE; BODY_BOUNDARY идёт отдельно.

Authored basin всегда имеет footprint/floor_z; lake — замкнутую shoreline;
coastline water_source — path/closed/water_side по existing constraints;
procedural source — generation region reference. У трёх legacy source
видов generation_region_uid для auto берётся из явного region binding
source settings: `BodyWaterGenerationSettings.generation_region_uid:
EntityUid | None = None`. Это body-only input, не cascade параметр;
при None domain binding выбирает world_region, не ближайший регион.
У ProceduralWaterSource region_uid хранится только на source, не второй
копией в generation; validator требует generation.generation_region_uid=None
даже при совпадающем значении: второе место хранения запрещено.
Authored region strategy на procedural source без shape несовместима:
ошибка SOURCE_STRATEGY_MISMATCH, не автоподмена strategy.

Неявный world auto source создаёт caller из world/region/category и
стабильного declaration slot через existing app.ids entity_uid channel;
identity inputs — world_uid, region_uid, category, slot. Geometry,
floor, target percent и номер найденного компонента в source identity
не входят. Source identity не равна physical WaterBody UID. Для authored
source existing location_uid сохраняется; missing UID — validation error.

В `.../sources/waterSourceMetadata.py::WaterSourceMetadata`:
`source_uid: EntityUid`, `source_kind: WaterDesignSourceKind`,
`body_kind: BasinKind`, `liquid: MaterialKey`, `level: FineZ`,
`bands: HydrologyBands`, `source_path: tuple[str|int,...]`.
Source → metadata mapper — один domain function до strategy dispatch.
PreparedWaterEntry.source меняется на WaterSourceMetadata;
prepared: PreparedPlacement и floor profile приходят после design.
Factory читает uid/kind/liquid/level/bands из metadata, не пытается
распознать новый source через isinstance(DeclaredBasin). Поля
ResolvedWaterPlacement и BasinSpec согласованы по uid/kind/liquid/level;
floor/profile получены из accepted draft, не повторно из world JSON.
sources/ содержит три файла и init (4), hydrology root не расширяется.

Metadata также содержит default_depth:strict positive int от category
basin_depth. WaterDesignDraft имеет required floor_z:FineZ и
floor_profile:BasinFloorProfile|None: authored scalar берётся из source,
auto bound — из F. Exact factory map: spec.source_uid=metadata.source_uid,
spec.kind=metadata.body_kind, spec.liquid=metadata.liquid,
spec.z_water_level=metadata.level, spec.bands=metadata.bands,
spec.footprint=resolved_record.footprint_cells,
spec.floor_z=draft.floor_z, spec.floor_profile=draft.floor_profile.
ResolvedWaterPlacement.kind/z_water_level/liquid равны тем же metadata
values. PreparedWaterEntry compatibility fields проверяются на равенство,
не дают factory выбирать альтернативный источник. BodySource metadata,
placement identity и physical identity не смешиваются.

#### C. Общий rule engine: конечная схема и truth table

В target dataModel/policy/{policySpec,policyFacts,policyReferences,policyRules,
policyEnums,policyDecision}.py:
- PolicyStage enum: ABSOLUTE_GATE / PRIORITY / SUPPORT / BEHAVIOR.
- PolicyRuleId — opaque nonempty identifier; RulePrecedence — strict
  nonnegative int, отдельный тип от Specificity.
- FactValue[T] union: KnownFact(value:T), WaitingFact(support_uids:
  tuple[EntityUid,...]), UnknownFact(issue:FieldPathError).
  FactState enum KNOWN/WAITING/UNKNOWN. KnownFact(None) и UnknownFact
  различаются. Неизвестный source binding даёт Unknown, не False.
- PolicyValueRef[M,T] union: DirectValueRef(field:FieldRef[M,T]) либо
  FactValueRef(field:FieldRef[M,FactValue[T]]). Общий reader превращает
  direct scalar в KnownFact; source settings bool/int не притворяются
  FieldRef на FactValue. Typed predicates Equal[M,T](reference:PolicyValueRef[M,T],
  expected:T), InSet[M,T](reference,values:frozenset[T]), IsPresent[M,T](reference).
  Rule.conditions — tuple predicates, AND; OR выражается несколькими
  rules. Свободного expression/script языка и consumer lambda predicates нет.
- Effects: DisableEffect(reason:PolicyDisableReason),
  SelectPriorityDefaultEffect(ref:PriorityValueRef[M]),
  RequireSupportEffect(support_uids:tuple[EntityUid,...]),
  SelectBehaviorEffect[B:Enum](value:B). Rule generic binding сохраняет
  T expected values/B behavior enum; смешение enum domains отвергается.
- PolicyRule: id, stage, precedence, conditions, effect — required.
  Уточнение G0-PT (2026-10-27): PolicyRule[B,R].domain_reason:R|None=None
  переносит domain explanation §6.8-B/PolicyReason[R]; DisableEffect.reason
  остаётся common enum. ObjectAdmissionFacts.effective_priority:FactValue[Specificity]
  в objectAdmissionPolicyDefinition.py — transient computed fact общего executor
  после PRIORITY selection, не authored/второй priority. Caller не подставляет его;
  общий zero rule ссылается на этот POJO через FactValueRef. Bindings/definitions
  только объявляют refs/rules, resolution остаётся G0-PE.
  PolicySpec: rules tuple с unique ids, authored_priority_ref,
  domain_priority_ref, terminal_priority_ref, expected_behavior_type.
  Source instances привязывает typed application binding; FieldRef
  functions — static declarations, не serialized cache payload.
- PolicyDecision[B:Enum,R:Enum]: state enum READY/DISABLED/WAITING_SUPPORT/UNRESOLVED,
  effective_priority: Specificity|None, behavior: B|None,
  reasons: tuple[PolicyReason,...], waiting_supports: tuple[EntityUid,...],
  provenance: tuple[PolicyProvenance,...], issues: tuple[FieldPathError,...].
  PolicyProvenance: origin enum AUTHORED/DOMAIN_DEFAULT/TERMINAL_DEFAULT/
  RULE/FALLBACK, source_path: tuple[str|int,...], rule_id: PolicyRuleId|None.
  Object-admission READY требует priority>0, DISABLED не допускает geometry reservation;
  WAITING имеет nonempty supports; UNRESOLVED имеет nonempty issues.

PriorityValueRef[M] явно принимает FieldRef[M,Specificity] либо
FieldRef[M,Specificity|None], без invariant-generic cast между ними.
Priority refs могут ссылаться на разные source model types; typed bind
проверяет каждый ref/instance до общего heterogeneous declaration registry.
Поведение B и domain reason R — разные enum параметры: water strategy specialization WaterDesignDecision =
PolicyDecision[DesignedWaterStrategyKind,WaterPolicyReason], generation —
HydrologyGenerationDecision = PolicyDecision[HydrologyExecutionMode,WaterPolicyReason],
coating —
PolicyDecision[SurfaceCoatingAction,SurfaceCoatingReason]. Immutable decision
ковариантен по обоим параметрам; common placement читает только общий
PolicyDecision[Enum,Enum] contract, domain consumer получает конкретную
specialization из своего typed binding. Codec использует зарегистрированный
конкретный enum binding, не dynamic import enum по имени из wire.

Operation contracts также разделены явно: PolicyOperation enum
OBJECT_ADMISSION / VALUE_SELECTION. ObjectAdmissionPolicySpec и
ValueSelectionPolicySpec — два variant PolicySpec; PolicyResolver.resolve
имеет typed overloads на ObjectAdmissionDecision/ValueSelectionDecision.
Общий набор decision fields выше сохраняется, operation — required tag.
У object variant priority refs обязательны, READY priority>0, 0 всегда
disabled. PlacementAdmissionInput/PreparedPlacement принимают только
ObjectAdmissionDecision. Value-selection variant не имеет priority refs,
пропускает PRIORITY stage; READY требует выбранный behavior, priority=None.
Coating и HydrologyExecutionMode selection используют value variant:
иначе terminal0 бессмысленно выключал бы всякое поведение вне placement.
ObjectAdmissionPolicyDefinition нельзя зарегистрировать как VALUE_SELECTION
и тем самым обойти общий zero rule. WaterDesignDecision — object variant
с enum стратегии; HydrologyGenerationDecision — value variant с enum
режима. READY water strategy specialization проверяет behavior!=None;
typed accessor require_behavior()->B отдаёт уже выбранный enum, не
разрешает policy повторно. No-match required value — typed RULE_NO_MATCH,
не READY с behavior=None. Fields sources/facts и fallback matrix общие.

Stages выполняются в enum порядке выше. Общий ObjectAdmissionPolicyDefinition
объявляет enabled=False → Disable, priority=0 → Disable; домен только
привязывает поля/частные rules. Для PRIORITY authored non-None побеждает
selected domain default, затем terminal 0. SelectPriorityDefaultEffect
выбирает source field, не переписывает authored value. Ни один rule не
переопределяет zero-disable. Rule сортируется по (-precedence,id) внутри
stage; id влияет только на стабильный порядок diagnostics. Несовместимые
выборы одинакового precedence → RULE_CONFLICT, не lexical winner.
Higher precedence selection побеждает lower; доказанный Disable
терминален, даже если выбор behavior в этой stage ещё ждёт support.
Malformed declared fields валидируются перед этим независимо от disable.

Truth table predicate AND: known False → False даже при другом Waiting/
Unknown (неиспользуемый факт не нужен); все True → True; нет False,
есть Unknown → Unknown; иначе есть Waiting → Waiting. На applicable
stage proven Disable побеждает Waiting/Unknown неиспользуемого rule;
ошибка обязательного binding/schema не скрывается. Для required support:
accepted → Known; pending same batch → Waiting; disabled → causal Disable;
missing/failed/cycle → Unknown/Unresolved. При нескольких causes любой
failed/missing/cycle даёт UNRESOLVED, даже если другой support disabled;
все disabled causes сохраняются в diagnostics/provenance.

PolicySpec также содержит fallback_rules:tuple[PolicyFallback[B],...];
PolicyFallback: reason:PolicyIssueReason, behavior:B|None,
disable_object:bool. Для обязательного неизвестного факта общее admission
объявляет DISABLE_OBJECT, terrain coating definition — тот же disable
coating object с behavior=KEEP_EXISTING_SURFACE. Rule не удаляет issue.
`application/policy/policyResolver.py::PolicyResolver.resolve(spec,
sources, facts, *, mode:ResolutionMode) -> PolicyDecision` — единственный executor. Domain
definitions возвращают spec; не имеют evaluate/resolve собственного
выбора поведения. FieldRef numeric/enum compatibility проверяет static
suite, runtime binding проверяет source model и actual value types.
В validation mode failure остаётся UNRESOLVED, valid=False; в runtime
engine применяет только объявленный fallback, выдаёт DISABLED с
сохранёнными issues/provenance и выбранным behavior. При отсутствии
fallback остаётся UNRESOLVED. Consumer лишь исполняет decision и sink,
не выбирает fallback вторым if/else. ResolutionMode — общий enum
RUNTIME/VALIDATE_ONLY в dataModel/validation/enums/resolutionMode.py;
HydrologyExecutionMode отдельно остаётся domain enum DISABLED / DECLARED_ONLY /
AUTORESOLVE по §6.8-D. Эти две оси не aliases и не заменяют друг друга;
общий policy engine не импортирует hydrology enum.
Engine не исполняет cascade, geometry, material comparison или scoring.
Coating и water admission — два production consumers одного engine;
economy/незатронутые masks остаются отдельным migration inventory C3.

Generic reason enum не содержит DRY_TARGET/EMPTY_GENERATION_TARGET:
это WaterPolicyReason в
`dataModel/hydrology/policy/hydrologyGenerationDecision.py`.
PolicyDisableReason в dataModel/policy/policyEnums.py содержит только
ENABLED_FALSE/ZERO_PRIORITY/
POLICY_FORBID/SUPPORT_DISABLED/ERROR_FALLBACK/DOMAIN_RULE.
PolicyReason[R](domain_reason:R|None, common_reason:PolicyDisableReason)
сохраняет private domain explanation, не заставляя общий engine знать
water/shore. DisabledPlacement.reason имеет общий enum, а сухость и
нулевой generation quota — domain_reason в decision.

#### D. Admission до геометрии и три конечных outcome

Новые dataModel/placement/lifecycle/{header,admission,causal}.py (4 с init):
PlacementHeader: identity:PlacementIdentity, mode:PlacementMode,
dependencies:tuple[PlacementDependency,...],
permitted_overlaps:tuple[PlacementOverlap,...],
separations:tuple[PlacementSeparation,...]. Geometry/area не нужны.
PlacementAdmissionInput: header, decision:PolicyDecision. Settings/facts
для повторной оценки SUPPORT удерживаются caller binding immutable;
каскад, RNG и уже выбранный priority повторно не вычисляются.
PlacementBatch.objects принимает tuple[PlacementAdmissionInput,...];
geometry подготовка передаётся через session API, не fake candidate.

Existing result.py остаётся владельцем PlacementOutcome union:
- ResolvedPlacement: existing prepared/candidate_uid; identity property
  из prepared.intent; required validated PolicyDecision хранится в
  prepared и определяет effective_specificity, не coastline special case.
- DisabledPlacement: identity:PlacementIdentity,
  reason:PolicyDisableReason — common enum из
  dataModel/policy/policyEnums.py (ENABLED_FALSE / ZERO_PRIORITY /
  POLICY_FORBID / SUPPORT_DISABLED / DOMAIN_RULE / ERROR_FALLBACK),
  decision:PolicyDecision,
  causes:tuple[PlacementOutcomeRef,...], diagnostics tuple default empty.
  reason — единственный SoT причины non-creation; diagnostics несут
  только контекст (ERROR_FALLBACK оборачивает исходную failure
  diagnostic). PlacementIssueCode (existing dataModel/placement/
  result.py) остаётся enum failure-диагностики UnresolvedPlacement:
  disable-семантика в него не добавляется — иначе существующее
  PlacementDiagnostic.unresolved property читало бы disabled как failed.
  Классификация outcome идёт по status/reason, не по unresolved property.
- UnresolvedPlacement: identity:PlacementIdentity,
  prepared:PreparedPlacement|None, diagnostics nonempty,
  causes:tuple[PlacementOutcomeRef,...]. prepared=None только при
  failure до geometry; identity всегда доступна и не выводится из None.
PlacementOutcomeRef: region_uid, status enum RESOLVED/DISABLED/UNRESOLVED;
это ссылки, не рекурсивные outcome objects. Status wire values сохраняются.
Batch validators/mappers читают outcome.identity, не общий
outcome.prepared.intent. ResolvedWaterPlacement создаётся только из
ResolvedPlacement; disabled/unresolved не дают BasinSpec/carve.

`application/worldData/placement/lifecycle/session.py::PlacementSession`
использует СУЩЕСТВУЮЩИЙ DependencyQueue, второго scheduler нет.
API: start(batch); ready_for_preparation()->tuple[PlacementHeader,...];
submit(prepared:PreparedPlacement)->None;
step()->PlacementOutcome|None;
fail(identity, diagnostics)->UnresolvedPlacement;
finish()->PlacementBatchResult. start публикует terminal disable/error;
ready_for_preparation выдаёт READY headers с готовыми supports, stable UID
order лишь для подготовки. Caller готовит ВСЮ эту порцию и submit
добавляет prepared в существующий heap (-priority,-original_area,uid).
Только затем step выполняет existing check_candidate для ОДНОГО
победителя, settles очередь и пересматривает
только SUPPORT facts новых ready objects через тот же PolicyResolver.
Перед следующим step caller готовит/submit новые ready headers; иначе
ожидавший родителя child с большим priority мог бы ошибочно проиграть.
Порядок geometry preparation не решает пространственную конкуренцию.
Caller domain preparer строит geometry, не admission/priority.
finish превращает missing/cycle/remaining waiting в явные unresolved.
Old resolve_placements wrapper делегирует этому же session, не оставляет
старый параллельный `_preflight` с WaterPresence внутри общего resolver.

#### E. Мера площади и budget allocation

Terrain region domain владеет точной дискретной fine-XY мерой. В
`dataModel/terrain/regions/coverageGeometry.py`:
CoverageSpan(y:FineY,x0:FineX,x1:FineX), half-open [x0,x1);
RegionCoverage(region_uid:EntityUid,spans:tuple[CoverageSpan,...]).
Spans canonical, sorted(y,x0), disjoint/non-adjacent в одной row, clipped
world bounds; seam пересекающий интервал разбивается. Area=sum(x1-x0),
единица fine_cells². area/union/intersection/subtract принадлежат
`application/.../terrain/regions/coverageMeasure.py::RegionCoverageMeasure`,
API `area(coverage)->int`, `union(tuple[RegionCoverage,...], *, region_uid)->RegionCoverage`,
`intersection(a,b, *, region_uid)`, `subtract(a,b, *, region_uid)` с merge row intervals.
Result UID всегда явно предоставляет caller, включая empty union; implicit mint
и выбор UID первого operand запрещены согласованным G3-R supplement.
Hydrology/budget не вычисляют площадь bbox/полигона независимо.

RegionExtent provider использует тот же membership predicate, что
RegionRasterizer. Bbox — intervals, ellipse/polygon — row scan conversion
с existing integer-index membership (не неявный сдвиг x+0.5); anchor/corridor — тот же existing predicate.
EdgeNoise: неизменяемая внутренняя область/внешняя область отделяется
доказанным amplitude bound, вычисляются только boundary-band candidates;
claim input читается в его уже заданном размере и сворачивается в spans.
No full-world fine-cell array/materialization. Для патологического
noised/claim input boundary может занимать всю область: гарантировать
сублинейное время для произвольной геометрии нельзя. Требование — точная
мера без независимого приближённого estimator, output-sensitive spans
и bounded working chunks, а не недоказуемая O(perimeter) для всех shapes.

Geometry membership извлекается из existing
application/worldData/masks/regionRasterizer.py::_membership: shape.contains
и edge-noise boundary test остаются общими; paint-density `_density`
не входит в generation extent. Rasterizer по-прежнему накладывает density
ПОСЛЕ geometry. Claim coverage берётся от claim owners до paint density.
Поэтому forest density не меняет площадь региона/целевую долю воды.
RegionCoverage для generation region обязан представлять именно эту
geometry, не sparse painted cells. Тест сравнивает spans с brute-force
existing geometry predicate на малом bounded fixture для всех shape kinds,
а не с другой независимо написанной формулой площади.

BodyCoverageRequest в coverage/budget.py: source_uid, generation_region_uid,
generation_area_fine2:strict nonnegative int, target_fraction:finite float[0,1].
Terrain RegionCoverageMeasure заранее выдаёт authored_union_fine2 и
available_auto_area_fine2=area(union(auto regions)-authored union).
Budget calculator получает числа и contexts, не новый geometry executor.
При сумме request_b=0 все allocations0, остаток остаётся shortfall,
не распределяется делением на0 или искусственными единичными весами.

WaterCoverageBudget fields в coverage/budget.py: region_uid, area_fine2,
target_fraction, target_fine2, authored_union_fine2, residual_fine2,
allocations:tuple[BodyCoverageAllocation,...]. BodyCoverageAllocation:
source_uid, generation_region_uid, requested_fine2, allocated_fine2.
target_fine2=round-half-up(fraction*area) с Decimal от canonical fraction;
residual=max(0,target-authored_union). Authored union — planned authored
water footprints, без повторного суммирования overlap, без подрезания.
Actual после fill не используется для повторной смены initial target.

Для auto sources b: request_b=round-half-up(f_b*area(region_b)), где
f_b — body/category/world cascade. World residual — общий cap, не
выдаётся каждому телу заново. Total allocation cap=min(world residual,
area(union(auto generation regions) minus authored union)). Сначала
пропорциональное распределение по request_b с cap request_b; integer
остаток — largest-remainder, tie source_uid. Явный request=0 получает0.
Overlap regions учитывается union cap, не дополнительным spatial owner
resolver; размещение/конфликты остаются P2. После отказа/конфликта/fill
не перераспределять budget и не расширять authored constraints.

Authored union включает только admitted complete authored body sources,
не root/category disabled, не priority0 и не failed admission. Пока P2
не разрешил конфликты, это planned union; rejected geometry не вызывает
второго распределения после P2. River route generation не запускается
ради budget; окончательная речная вода учитывается final actual union.

Actual coverage provider после hydrology строит union liquid_candidate
cells: coarse cells разворачиваются в fine spans, fine overrides заменяют
соответствующие колонки, dry SHORE не включается. River liquid columns
включаются на той же мере. Отчёт содержит target/allocated/accepted-claim/
final-wet fine² и final_fraction; не называет target обязательным итогом.
Если eligibility не позволяет достигнуть allocated area — явный shortfall
report, без изменения гор/авторских объектов.

#### F. Поля, порог и передача дна единственному writer

Точные числовые defaults в owning POJO, не application literals:
ContinentalNoisePolicy: length_fraction=0.18 (>0), octaves=4 (1..16),
lacunarity=2.0 (>1), persistence=0.5 (0..1).
WaterFieldSelectionPolicy: score_bits=24 (8..30), общий для всех field strategies;
не является noise recipe parameter (согласовано G4-C).
PlateGenerationPolicy: plate_count=12 (>0), blend_length_fraction=0.12
(>0). FieldCompositionPolicy: operator=ADD_CLAMP enum,
detail_weight=0.20 (0..1). Для tiny world effective plate_count=min(count,
число canonical fine cells), штатное policy adjustment с provenance.
Длина — fraction меньшей fine стороны world extent, minimum1 fine cell.
Числовые type/range checks strict, finite. Настройки policy — inputs
контракта соответствующего field producer и fingerprinted.

WaterGenerationDefaults также объявляет implicit_body_kind:Literal[BasinKind.OCEAN]
=BasinKind.OCEAN, не application literal и не второй authored setting.

Identity/RNG extension в existing app/ids/uidKind.py: добавить enum
members WATER_SOURCE и WATER_FIELD, значения water_source/water_field.
Source helper — `app/ids/water/sourceIdentity.py::water_source_uid`,
entity_uid(world_uid,UidKind.WATER_SOURCE,region_uid=...,category=...,slot=...).
Field randomness использует seed_root=world_uid, не строку seed_int:
seeded_u01(seed_root,UidKind.WATER_FIELD,channel=FieldChannel,...keys).
Octave и lattice coordinate tuple — именованные identity keys; для
affine center permutation coefficient enum MULTIPLIER/OFFSET в field.py.
N=1 даёт a=1,b=0; иначе a выбирается seeded start и cyclic scan 1..N-1
до gcd(a,N)=1, b=floor(u*N). Каналы не свободные consumer strings.

Value noise: seeded lattice values [-1,1] по existing app.ids stable
seed/channel/coordinate hash, quintic interpolation
s(t)=6t^5-15t^4+10t^3 по каждой axis. fBm = Σ(persistence^k*N_k)/Σweights,
frequency=lacunarity^k/length. Random channel FieldChannel enum
NOISE_LATTICE / PLATE_CENTER / PLATE_BUOYANCY в fields/field.py.
Sampling uses world-fine coordinates, не tile-local seed.
Planar embedding=(x,y); wrapped embedding — 4D torus
(W*cos(2πu)/2π,W*sin(2πu)/2π,H*cos(2πv)/2π,H*sin(2πv)/2π);
sphere embedding=R*(cosφ*cosλ,cosφ*sinλ,sinφ), R=H/π,
λ=2πu, φ=πv-π/2, u/v нормированы на world extent.
Thus seam/pole aliases sample один canonical world field; tile границы
не seed и не ocean seeds. Grid sampling использует cell centers.

Plate centers — первые effective_count элементов seeded permutation
canonical fine cell indices (affine a*i+b mod N, gcd(a,N)=1, a/b
получены PLATE_CENTER channel); без fine-world enumeration.
Buoyancy_i=2*seeded_u01(PLATE_BUOYANCY,i)-1.
P(c)=Σ(w_i*buoyancy_i)/Σw_i,
w_i=exp(-(dist2(topology,c,center_i)-d_min²)/L²),
d_min²=min_i dist2(topology,c,center_i). Вычитание минимума сохраняет
нормализованный результат и даёт хотя бы один weight=1 без underflow
fallback. Equal-distance iteration order — plate index.
Plate field определяет P, noise field N; plate_noise field
clamp(P + detail_weight*N,-1,1). detail_weight=0 точно равен plate.
Wet score = round-half-up(((1-field)/2)*(2^score_bits-1)). Больший score
кандидат воды. AuthoredRegionStrategy не генерирует noise, сохраняет
authored shape/level/floor, auto поля используются только в недостающих
границах разрешённой стратегии, не переписывают required authored floor.

Threshold: кандидаты working coarse grid получают score из world-fine
центра; пригодны только полные клетки внутри generation region,
weight=точная fine area этой клетки по общему measure. Частичные
boundary cells исключаются, недостаточная capacity даёт shortfall.
Сортировка (-score,canonical y,x); выбрать prefix с суммарным weight,
ближайшим allocated_fine2, equal-error — меньший prefix. Это задаёт ties/
plateau/rounding однозначно; ошибка квантования <=largest candidate weight.
Candidates строятся по всему scope, partial/tile request фильтрует лишь
выход. Объединение выбранных клеток может иметь несколько компонентов;
source UID от этого не меняется, physical split отражает mapping G ниже.

В existing BasinSpec добавить optional `floor_profile: BasinFloorProfile|None=None`.
None сохраняет текущий scalar floor_z + bands algorithm. Новый
`dataModel/terrain/relief/bathymetry/floorProfile.py`:
BasinFloorProfile union SampledFloorProfile(space:CoordinateSpace,
samples:tuple[tuple[Coord,FineZ],...]) / FieldFloorProfile(recipe:WaterFieldRecipe,
level:FineZ,depth:positive int,z_min:FineZ). Discriminator FloorProfileKind
enum SAMPLED/FIELD. WaterFieldRecipe в designedWater/fields/field.py —
union NoiseRecipe(seed_root:EntityUid,topology,noise_policy), PlateRecipe(seed_root:EntityUid,topology,
plate_policy), PlateNoiseRecipe(seed_root:EntityUid,topology,noise_policy,plate_policy,
composition_policy), с explicit strategy enum discriminator.
Field floor(c)=max(z_min,level-max(1,round-half-up(depth*(1+wetness(c))/2))).
Если level<=z_min, валидного дна нет: validation error, runtime typed
DISABLE_OBJECT fallback с обязательным issue/log. Sampled profile
покрывает весь accepted footprint в указанном space, unique cells,
каждый z<level; spec.floor_z — нижняя граница/min profile, не второй writer.

Terrain-owned floorProfile/basinZ потребляют этот payload и выставляют
абсолютный z (не delta); повторное применение идемпотентно. Reserved
mountain cells сохраняются, authored scalar constraints не перезаписываются.
Для overlaps только accepted P2 geometry; permitted overlap с разными
уровнями использует существующее HY-12 level/merge contract, floor writer
применяет min допустимых absolute floors, не суммирует carving.
L2 может вычислять fixed FieldFloorProfile в fine координатах, но не
запускает threshold/placement заново. Hydrology читает готовое z и fill,
не применяет floor recipe. Единственный z writer остаётся terrain.

#### G. Source → physical mapping и attached boundary

В `dataModel/hydrology/planning/sourceBodyMapping.py`:
SourceBodyMappingEntry(source_uid:EntityUid,
body_uids:tuple[EntityUid,...]); SourceBodyMapping(entries tuple).
Его revision — ref внешнего HydrologyPlan envelope, передаваемый consumer
вместе с payload. Собственный output PlanRef внутрь payload не записывается:
иначе output digest рекурсивно зависел бы от самого себя.
body_uids sorted/unique; empty tuple означает
accepted, но фактически сухой source. Отсутствующая entry у accepted
source — ошибка контракта, не dry. Disabled/unresolved source остаётся
в placement outcomes, не придумывает mapping entry мокрого тела.

Producer — existing waterMaterialize.py после FINAL fill/component
classification и всех uid_remap/merge/spill. Для каждого accepted source
сохраняет source provenance, собирает final physical body UIDs клеток
его footprint, у которых liquid_candidate=True, нормализует через final
remap. Не выводит source_uid из совпадения строк с body UID. Mapping
может быть many-to-one после merge и one-to-many после split. При spill
указывается фактический child WaterBody UID; PhysicalWaterUnion/system_uid
не выдаётся за WaterBody UID. HydrologyPlan дополняется source_mapping,
все entries относятся к его же output revision.

В `dataModel/hydrology/boundaries/attachedCoastline.py`:
AttachedCoastline(source_uid:EntityUid,target_source_uid:EntityUid,
parts:tuple[CoastlinePart,...],
coordinate_space:CoordinateSpace,hydrology_ref:PlanRef).
CoastlinePart(body_uid:EntityUid,closed:bool,path:tuple[HydrologyWaypoint,...]).
Каждый part непустой, body_uid принадлежит target mapping; разные rings/
компоненты не склеиваются фиктивным сегментом. All-water target без
wet/dry boundary даёт normal disabled DOMAIN_RULE/NO_BOUNDARY.
CoastlineBoundaryPlan(boundaries:tuple[AttachedCoastline,...],
outcomes:tuple[PlacementOutcome,...]); coordinate_space строго WORLD_FINE_GRID.
Путь пуст только на входном derive-mode source; итоговая accepted
boundary имеет nonempty parts. DeclaredCoastline.purpose/target_source_uid
обязательны по §5.3: BODY_BOUNDARY требует target, WATER_SOURCE не
использует target как prerequisite существующей воды.

Producer: `application/worldData/placement/adapters/coastline/attachedCoastline.py`
потребляет SourceBodyMapping + final water occupancy из того же envelope,
готовит зависимое geometry; общий P2 выполняет dependent phase.
Consumer/output:
`application/worldData/planning/composition/surfacePlanningAssembler.py`
после hydrology запрашивает CoastlineBoundaryPlan и включает
`coastline_boundaries:PlanEnvelope[CoastlineBoundaryPlan]` в GEO-1 bundle.
PC baseline этого binding ещё не активирует. L0/L2 читают одинаковый
derived boundary plan для outline/shore association, не новый BasinSpec.
Plan cache — единственное derived хранение boundary в данном scope;
новая SQL entity/manifest SoT для coastline не вводится.

Derived path — граница final wet union выбранных body_uids в fine grid,
canonical stitched rings/lines topology provider. Absolute path не
сдвигается: каждый rasterized segment обязан лежать на границе target
wet union (adjacent wet/dry fine cells через topology); иначе unresolved
BOUNDARY_OFF_TARGET. target disabled → causal disabled; accepted dry →
DRY_TARGET disabled; unresolved/missing target → unresolved. Source-A
может в том же generation cycle создать ocean, после fill source-B
строит boundary по SourceBodyMapping: этот сценарий не требует заранее
существующего океана и не теряет autoresolve по coastline water_source.

#### H. Surface facts: материал, геометрия и общий executor

Inventory подтвердил: existing MaterialCategory.SOLID сам по себе не
доказывает rock. В `dataModel/materials/enums/materialSubstrateKind.py`
новый enum ROCK / LOOSE_SEDIMENT / OTHER. В existing MaterialRegistryEntry
добавить `substrate_kind: MaterialSubstrateKind|None=None`; None — неизвестно,
не OTHER. Canonical material data в worldMaterialRegistry.py явно
задаёт stone=ROCK, earth/sand/dirt_road=LOOSE_SEDIMENT,
wood/ice/crystal/iron/window_glass/porthole_glass/vent_mesh/water/lava/air/smoke/toxic_gas=OTHER.
Mapping применяется в обоих canonical fixture/engine-delta declarations,
где эти entries существуют, не является runtime таблицей в consumer.
Custom material без указанного факта сохраняет None.
Consumer не узнаёт породу по строкам stone/rock/tags/hardness. Новое поле
не копирует material_category; custom solid должен объявить свой факт.

`dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py`:
SurfaceAspect enum HORIZONTAL / RELIEF_FACE;
SurfaceCoatingFacts(world_uid:EntityUid,support_input_fingerprint:InputFingerprint,
cell:FineXY,face:Facing|None,aspect:FactValue[SurfaceAspect],
side_kind:FactValue[ReliefSideKind],material:FactValue[MaterialKey],
substrate:FactValue[MaterialSubstrateKind]). Evidence provenance:
geometry_ref:PlanRef, material_source_path:tuple[str|int,...].
Horizontal face=None; relief face — explicit facing. Existing source
side spec SHEER — геометрический факт; generic соседняя большая delta z
сама по себе не объявляет отвесную породу.

`application/.../terrain/relief/surfaceCoatingSupport.py::SurfaceCoatingSupportProvider`
метод `facts(request:PlanRequest[SurfaceSupportInput],
dependencies:SurfaceSupportDependencies,*,cells:RegionCoverage)
->tuple[SurfaceCoatingFacts,...]` — read-only,
до нанесения coating. Geometry — relief facts/pre-coating surface,
material — выбранный terrain/material input и typed registry entry.
Mill, current persisted L2, post-coating material и hydrology heuristic
не являются обязательными источниками. Missing required facts дают
UnknownFact с точным path/cell/reason; cache miss вызывает pure facts
builder по тому же captured view, а не unknown по отсутствию pack.

GEO-1 extension view явно дополняет baseline source data полем
`surface_support:SurfaceSupportInput`; baseline PC view этого поля не
имеет и не приводится structural cast к GEO view. Definition в
`dataModel/terrain/relief/surfaceCoating/surfaceSupportInput.py`:
SurfaceSupportInput(seed:int,masks_enabled:bool,
grid:SurfaceGridSettings,topology:WorldTopology,
terrain_entries:tuple[TerrainSupportEntry,...],
materials:tuple[MaterialSupportEntry,...],
declared_regions:tuple[LandcoverDeclareEntry,...],
region_states:tuple[RegionState,...],landcover:LandcoverSupportPolicy,
mountains:tuple[MountainDeclareEntry,...],
relief_policies:tuple[tuple[ReliefContext,ReliefContextPickPolicy],...],
templates:tuple[tuple[EntityUid,ReliefTemplate],...],
refine_policy:ParentLightRefinePolicy).
MaterialSupportEntry: key:MaterialKey, category:MaterialCategory,
substrate:MaterialSubstrateKind|None. TerrainSupportEntry: key:TerrainKey,
category:RegistryKey[WorldTerrainCategoryRegistry],
default_material:MaterialKey|None, merge_rank:int,
eligibility:tuple[EligibilityRule,...], hills:HillPolicy|None, hills_authored:bool.
LandcoverSupportPolicy: enabled:bool, autoresolve:bool,
transition_threshold:float, seed_spacing:int,max_radius:int,
claim_noise:LandcoverClaimNoise,fallback_terrain:TerrainKey,
terrain_policies:tuple[LandcoverTerrainPolicy,...],
terrain_policy_hills_authored:tuple[TerrainKey,...]. Parent masks_enabled и
authored-presence bits сохраняются явно, отдельно от child gates/values. Это projections
existing terrain registry/landcover POJO, не второе persisted состояние.
На snapshot capture источники — typed registry rows, WorldTerrainMasks,
RegionState owner read view и membership-scoped TemplateSnapshotLoader.
Library IO остаётся вне generators: caller предварительно загружает
members, capture принимает готовые typed bodies. Full template body/UID
входят в fingerprint; удаление membership не оставляет старые side facts.

В G9-ST immutable source prerequisites: existing ReliefTemplate.conditions/
structure_refs, MountainSideRecipe.side_kinds, ReliefTerrainCondition.cases,
ReliefRoleCase.bands/structure_refs, ReliefGradeKnobs.structure_refs — tuple
вместо list, сохраняя None/empty и wire arrays. ReliefDeltaBand наследует
тот же immutable knobs. Остальные входные RegionState/LandcoverDeclareEntry/
HillPolicy/ReliefContextPickPolicy уже frozen после PC-0I spatial change.
terrain_policies dictionary превращается в tuple existing entry values
в projection; key проверяется равным entry.system_terrain.
Facts provider использует same region paint/hill/side-stamp pure routines
в bounded canonical tile windows с halo и snapshot-scoped inputs,
без calls live World accessor. Unsupported/missing required side/material
доказательство — Unknown, а не новый slope/cliff heuristic.
Этот контракт не вводит river fine source builder R1/R2: coating facts
потребляют готовый post-river surface и не участвуют в поиске истока.

SurfaceSupportDependencies — typed application record в том же
surfaceCoatingSupport.py: climate_base:PlanEnvelope[ClimateBasePlan],
terrain_base:PlanEnvelope[TerrainPlan],relief:PlanEnvelope[ReliefPlan],
hydrology:PlanEnvelope[GeoHydrologyPlan],climate_local:PlanEnvelope[ClimateLocalPlan].
По §6.31-E hydrology здесь — final (post-river) envelope; relief —
pre-river, дополнительное поле river_relief:PlanEnvelope[RiverReliefPlan]
содержит post-river высоты. Эти типы не подменяются друг другом.
Provider получает их через declared slots, не требует уже собранный
GeoSurfacePlanBundle, который сам содержит его ещё не готовый output.
SurfaceSupportInput mode-independent; mode принадлежит CoatingPlanInput.

Terrain-owned SurfaceCoatingPolicyDefinition объявляет общий predicate:
RELIEF_FACE AND SHEER AND ROCK → DisableEffect(POLICY_FORBID).
Остальные cases проходят общую policy evaluation. Truth table:
horizontal+rock → allow; slope+rock → allow; sheer+rock → forbid;
sheer+known OTHER solid → allow; sheer+unknown substrate → unknown;
unknown geometry+rock → unknown; known non-rock делает rock-conjunction
False без необходимости выдумывать неизвестную геометрию.
Это минимальный запрет rock cliff, не запрет всех solids.
Runtime unknown fallback — KEEP_EXISTING_SURFACE: исходные terrain и
material плюс SHORE/body UID/level сохраняются, пропускается только coat.
Hydrology лишь потребляет decision, не вычисляет substrate/aspect.

#### I. Validation hook, severity и реальные sinks

Existing `WorldService.prepare_import` проверяет одну world row и не
имеет всего location draft. Поэтому aggregate spatial validation нельзя
прятать только в этом classmethod или в REF-W validator.
Новый application owner:
`worldData/planning/validation/surfacePlanValidator.py::SurfacePlanValidator`,
метод `validate(view:SurfacePlanningView,bundle:SurfacePlanBundle|None,
*,ctx:ResolveContext)->None`. Он выполняет read-only coating/support
checks и передаёт issues existing report_issues; no DB/Pack writes.
Capture/build/facts используют те же contracts, что runtime.

Точные activation sites:
1. `WorldBundleService._prepare_bundle` ПОСЛЕ всех handler.validate_section
   и до финального `if ctx.errors`: из уже подготовленных draft world/
   locations создать capture view, readonly planning bundle и facts,
   вызвать injected SurfacePlanValidator. Никакого repository fallback
   вместо отсутствующих draft данных. Required missing draft reference —
   validation error, а не заимствование live объекта из другого world.
   `worldBundle/entity/sections.py::LocationsSectionHandler` отдаёт
   подготовленные NamedLocation objects в общий transient draft context;
   не дублирует schema parsing независимым raw dict consumer.
2. Standalone world edit/import перед `_save`/region edit reconcile:
   injected `worldData/planning/validation/worldSurfaceValidationOrchestrator.py`
   получает edited world и coherent существующие location rows через
   owning repositories/UOW; запускает тот же capture/validator. Новый
   world без locations получает empty set, нужные absent refs — ошибки.
   WorldService.prepare_import сохраняет pure row validation, не лезет
   в repository/Pack и не считается aggregate check сам по себе.
3. Runtime bundle/materialize boundary получает те же facts и policy,
   но публикует согласованный fallback, а не valid=True validation.
Constructor injection — existing container/worldData.py и worldBundle.py;
новый endpoint/библиотека логирования не требуются.

Severity matrix (code enum domain-owned, formatting — FieldPathError):
- authored disabled / valid default priority0 / dry target / known rock
  forbid: normal disabled, valid=True; informational diagnostics, без
  аварийной WarningError.
- valid cascade terminal default: valid=True, provenance/default event
  по existing cascade logging policy; quiet DEBUG не считается error log.
- malformed source/ref, rule conflict, missing required input, unresolved
  support: validation valid=False; runtime предусмотренный DISABLE_OBJECT
  fallback + WarningError, либо typed build failure, если fallback не задан.
- unknown coating support: SurfaceCoatingIssueCode.UNKNOWN_SUPPORT,
  validation valid=False; runtime KEEP_EXISTING_SURFACE + WarningError.
- source collapsed by fine→coarse projection: validation valid=False;
  runtime source disabled с сохранённым GEOMETRY issue + WarningError.
- cache failure/corruption: technical failure, не domain empty/fallback;
  existing application exception logging, не MISS.
Generic policy reason enum включает INVALID_INPUT / UNKNOWN_FACT /
RULE_CONFLICT / MISSING_SUPPORT / FAILED_SUPPORT / DEPENDENCY_CYCLE.
Fallback action enum общего admission: DISABLE_OBJECT; terrain action
KEEP_EXISTING_SURFACE принадлежит coating domain. Ошибка не исчезает
из report из-за того, что итоговый outcome disabled.

На runtime boundary FALLBACK issues передаются ровно один раз в
existing `jsonValidation.resolve.log_issues` через report_issues,
INFO logging profile обязан реально пропускать WarningError. Проверка
использует setup_logging test configuration и capture configured facade,
проверяет domain sink/transcript без второго emit; наличие DEBUG или
issue в Python object не считается доставленным fallback log.
Build diagnostics на failure отдаются request sink из PlanBuildFailure
так же, как envelope diagnostics на success; ошибка до bundle не теряется.

Проверен existing emitter: report_issues добавляет ВСЕ переданные issues
в ctx.errors; severity он не различает. Поэтому ERROR/FALLBACK идут
через report_issues, а NOTICE туда НЕ передаётся: existing cascade/default
info/debug emitter обслуживает normal notices отдельно. Это сохраняет
valid=True для normal disabled/default и не превращает notice в ошибку.

Existing log_issues structured extra сейчас содержит только reference
context, а action/cell/body отсутствуют как отдельные JSON fields.
Расширение существующего DTO/sink, без нового logger:
`dataModel/validation/diagnostics/runtimeIssueContext.py::RuntimeIssueContext[A,R]`
— frozen covariant dataclass, A/R bound StrEnum; fields world_uid:EntityUid,
snapshot_uid:EntityUid|None, content_revision:RevisionHex|None, source_uid:EntityUid|None,
body_uids:tuple[EntityUid,...], cell:tuple[int,int]|None, face:Facing|None,
fallback_action:A, fallback_reason:R. Required fields nullable явно.
RevisionHex — opaque lowercase 64-hex validated string alias в том же
runtimeIssueContext.py; JSON logger не получает необработанные bytes.
FieldPathError получает runtime_context:RuntimeIssueContext[StrEnum,StrEnum]|None=None;
existing reference context не используется как fake library reference.
Existing log_issues добавляет issue_code/issue_path и context fields
в logging extra, enum values сериализует явно. Existing JsonLogFormatter
уже сохраняет extras: core/loggingConfig.py::JsonLogFormatter.format.
No second handler/formatter/framework. На request boundary dedup
по нормализованному issue/context выполняется ДО report_issues: existing
helper устраняет дубли внутри своего аргумента, но сам ctx.errors.extend
не дедуплицирует предыдущие вызовы. Runtime fallback ctx.errors не
запрещает разрешённые независимые результаты; validation rejects их
как valid=False. Уже опубликованный domain issue не логируется повторно
caller exception wrapper ради того же fallback. HTTP existing loc/msg/code
сохраняются, context можно отдать отдельным optional typed полем.
Fallback context не хранит request_id/logger/traceback; request_id
присоединяет существующий formatter на request emission boundary.

#### J. Атомарный production cutover и сохранение baseline

Early contract шаги не меняют active source schema/exports: generation
leaf models, metadata и normalizers тестируются напрямую. Existing
WorldHydrology/Declared*/PreparedPlacement/PlacementBatch production
annotations/constructor paths переключаются только G10-A. Lifecycle V2
admission/header contracts живут в placement/lifecycle, общий geometry
checker/DependencyQueue переиспользуются; старый production facade до
switch сохраняет baseline. Это versioned contract migration, не второй
доменный resolver и не два одновременно активных production алгоритма.
Все old→new constructor updates/root imports выполняются атомарно в
switch. G2/G3/G0-P упоминают target owning files как состав G10-A diff,
а не разрешение сломать old bool/Prepared input на раннем шаге.


PC-0I/types/cache/providers/coordinator реализуют только existing baseline
и явно named DI change. New generation fields, source union и rule engine
после PC создаются contracts-only. G0-PT/G0-PE/G0-P, G1…G9-S до activation
могут проверяться isolated typed tests, но НЕ включают отдельный новый
zero-gate на старом production input. G0-P production wiring переносится
в единый G10-A switch; название раннего шага не означает activation.

Activation ledger, единственный executable production путь:
- До G10-A: existing baseline через общий PC lifecycle, old policy values;
  new strategies/settings/types доступны только pure tests.
- G10-A prerequisites: PC-12, G0-PT/PE/P contracts, G1/G2-P/G2-G,
  G3/G3-R/G4/G4-P/G4-C/G5/G5-CP/G5-C2/G5-C3/G6/G7/G7-C/G8/G9/G9-ST/G9-S.
- В G10-A атомарно: POJO category priority defaults=1; normalize old
  autoresolve paths; source→cascade→общий policy→design→один P2 batch→
  BasinSpec writer→HY-12 fill→source mapping→dependent boundary→coating.
  Old `_auto_specificity`, coastline-special effective property/preflight,
  domain-local enabled/autoresolve bool gates в затронутых water pass,
  HydrologyGeneratorService и masks wrappers удаляются/заменяются чтением
  единственного resolved decision. Old sea/ocean autoresolve discovery,
  создающий конкурирующие designed bodies из post-carve surface,
  отключается на том же cutover. Natural-only classify path сохраняется.
- Registry/schema/algorithm versions меняются вместе с switch; old cached
  envelopes по старым keys не принимаются. No temporary bypass flags и
  двух одновременно активных writers/policy chains.
- G10/G10-R: e2e проверки active path, including coastline source auto,
  normal zero disable, no double carve, dry target, boundary merge/split,
  material unknown log/validation и L0/L2 same plan refs.
Rollback acceptance — предыдущий release читает свой schema/key либо
отклоняет новый schema явно; нельзя обещать обратное чтение удалённых
wire keys без legacy exporter. In-process fallback к old chain не вводится.

#### K. Snapshot compatibility и внешняя HY-RIV-1 граница

GAP-SNAPSHOT локальной GEO-1 части закрывают exact inputs/fingerprints
§6.28, единая capture boundary и source revision guard. Existing
entity_uid(world,TERRAIN_SNAPSHOT,phase) остаётся opaque identity, рядом
обязательно передаётся content revision; equality UID не проверка validity.
Future WorldSnapshot/Patch System заменяет источник capture projections,
не поля domain I, codec refs, generator kernels и роли cache. Patch UOW
владеет source revision/publish guard; cache не становится durable store.

GAP-PHASE — **EXTERNAL_GATE HY-RIV-1 R1/R2**, не незавершённая функция
GEO-1. G11 публикует handoff contract, не объявляет fine river source
search реализованным. Для будущего track закреплены поля
`PreRiverTerrainSnapshot`: world_uid, source_revision, topology, grid,
climate_base_ref, relief_ref, basin_only_hydrology_ref, landcover_ref,
region_state_revision, refine_policy:ParentLightRefinePolicy.
Каждый ref — PlanRef, region state revision — InputFingerprint;
river refs/post-carve overrides отсутствуют. `FineReceivingWaterline`:
target_source_uid, body_uid:EntityUid, hydrology_ref, level:FineZ,
coverage:RegionCoverage в fine XY. FineSurfaceWindow: snapshot_revision,
rect:FineGridRect, surface_z tuple[(FineXY,FineZ)], terrain/material/
support facts из pre-river terrain producer. Radius — resolved fine-cell
input, производное extent_radius_fine(source_search_radius_fraction,
базовый extent) по §6.10; metric shortest topology dist² как §6.10.

R1 должен сначала выделить basin-only hydro output и pre-river landcover/
parent-light base: current SurfaceTerrainContext после рек НЕ подходит.
R2 реализует общий pure fine builder для sampler/materialize и доставку
pre-river base ref/revision через manifest/reader. На cache miss ref сам
по себе не восстанавливает старый state: rebuild только из совпавшего
authoritative captured view либо будущего restored WorldSnapshot;
иначе explicit stale-input error. Без R1/R2 river feature gated отдельным
track, coarse fallback не выдаётся за fine source implementation.
Manifest/base lifecycle и приёмка sampler=materialize=cache остаются
обязательными deliverables того track, их код не добавляется в GEO-1.

FineReceivingWaterline RIV handoff представляет ОДНО physical receiving
body с одним level. Если source mapping содержит несколько physical
тел, RIV caller обязан явно выбрать receiving body по своему typed
request; SourceUID alone не даёт произвольный общий уровень. Этот выбор
не выполняет GEO-1 boundary adapter. SourceBodyMapping body_uids содержит
только UID из final WaterBody records, не river UID и не system UID.

#### L. Статус, проверка стыков и точные acceptance suites

Design closure ledger:
GAP-CASCADE→A; SOURCE→B; POLICY→C; OUTCOME→D; AREA→E;
FIELD→F; BOUNDARY→G; SURFACE→H; VALIDATION/LOG→I;
CUTOVER→J; SNAPSHOT→§6.28/K. Их статус DESIGN_CLOSED: прежние вопросы
имеют finite schema/API/algorithm/owner/activation specification.
GAP-PHASE→K, EXTERNAL_GATE HY-RIV-1; не блокирует GEO-1 delivery,
блокирует только отдельную fine river feature.

Ручная producer→consumer проверка TARGET:
- source union B подходит WaterDesignInput G4 и AuthoredRegionStrategy;
  PreparedWaterEntry/factory используют metadata, не old source union.
- cascade A отдаёт non-null resolved generation parameters; доменный
  category flag не читается параллельно общим engine C.
- policy C может закончиться до geometry; lifecycle D принимает identity
  без PreparedPlacement и outcome.identity есть у всех трёх вариантов.
- draft F отдаёт absolute floor payload terrain writer; HY-12 не ждёт
  scalar-only floor, profile не теряется в metadata→BasinSpec mapping.
- region measure E — один контракт target/actual; budget не сортирует
  spatial winners и не переприсваивает quota после placement/fill.
- physical mapping G строится после remap; boundary target — source UID,
  его body_uids действительно final physical bodies, не union IDs.
- facts H несут evidence, policy C выполняет forbid, sinks I сохраняют
  original issue при fallback; гидрология не определяет rock/cliff.
- shared PC keys §6.28 включают каждый новый source/policy/profile input
  после schema-versioned расширения в G8/G10-A. New generation input
  не передаётся в baseline provider под прежним schema contract.

G8 меняет WaterPlacementInput schema на source union + resolved contexts +
budget/field policies и pre-hydrology refs; HydrologyPlanInput после
G10-A получает resolved allowed kinds/decisions вместо old auto flags.
Из I не удаляются immutable seed/grid/topology/level/river inputs.
Это новые contract versions с explicit adapters, не structural cast
baseline I в GEO-1 I. Old type names могут сохраняться, но registry
schema_versions разные. Main GEO-1 input fields WaterDesignInput:
source:WaterDesignSource, metadata:WaterSourceMetadata,
context:ResolvedWaterGenerationContext, region:TerrainRegionExtent,
budget:BodyCoverageAllocation, pre_hydrology_ref:PlanRef,
seed_root:EntityUid, topology:WorldTopology, grid:SurfaceGridSettings,
field_policy:WaterFieldRecipe у ProceduralWaterDesignInput. AuthoredWaterDesignInput
не имеет field_policy; это отдельный variant, не invalid procedural recipe.
По G5 authored variant обязательно содержит geometry:AuthoredWaterGeometry
от однократной source geometry preparation до metadata; lake level сверяется
с geometry.rim_level. Вход strategy не содержит raw anchors/working context.
WaterDesignInput union discriminator — effective strategy enum из policy decision.
Common fields дополнены actual pre_hydrology envelope и region_coverage по M.
Draft output — geometry footprints/profile/metadata по M; PlacementCandidate
создаёт общий preparer, не разные strategy-local constructors.

Планируемые executable suites (PowerShell, из repo root после
`$env:PYTHONPATH='backend'`), без запуска несуществующих тестов сейчас:
`.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/geo1/contracts -p "test_*.py"`
для A/B/C/D: test_cascade.py, test_sources.py, test_policy.py,
test_outcomes.py + init (5 файлов).
`.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/geo1/geometry -p "test_*.py"`
для E/F/G: test_coverage.py, test_fields.py, test_profiles.py,
test_boundaries.py + init (5).
`.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/geo1/integration -p "test_*.py"`
для H/I/J/K: test_surface_validation.py, test_logging.py,
test_activation.py, test_revisions.py + init (5).
Positive type suite добавляет exact I/T/FieldRef/enum pairs в existing
planned planning valid config; negative — wrong category axis, raw str
strategy, invalid fact type, wrong priority-vs-rule-precedence type,
fine/coarse mix и nullable source passed as authored-ready geometry.

Assertions: no writes validate_only; runtime fallback действительно
WarningError при INFO; same scope tiles/full/partial/restart дают те же
refs/geometry; detail0=plate; seam/pole aliases; equal-score plateau tie;
two overlapping regions cap union once; authored quota unaffected;
disabled support chain/cycle+disabled не маскируют failure; merged/split/
dry target source mapping; no live World reads sampler/provider; no
post-carve feedback и никакой реализации R1/R2 под видом готового G11.

#### M. Последняя сверка input/output и ownership

Все новые records, используемые как FieldRef source (generation settings,
policy facts/inputs), — frozen BaseModel с extra=forbid и instance
revalidation; legacy pure dataclasses сохраняют класс при переносе,
но codec проверяет их actual fields рекурсивно. Не передавать dataclass
как M:BaseModel в FieldRef и не исправлять это consumer cast.
PolicySpec содержит independent behavior и reason enum parameters;
priority/selection operation проверяется placement input validator.


В §6.25 generic payload tuple maps сортируются grid keys по (y,x),
не по repr/dataclass comparison: это сохраняет current row-major
iteration и stable feature ties. Ordered input sequences сохраняют
порядок. Не обещать одинаковый key перестановке списка, если existing
algorithm использует first-match; canonical sort обязателен для sets
и реестров с unique keys, где order семантически незначим.

PC-0I включает `application/jsonValidation/resolve.py::_reference_issues`:
существующий обход list/dict должен обходить также tuple, включая tuple
RegistryKey values. Это не новый validator. Иначе immutable source
POJO потеряли бы REF-W проверки. Existing source field names и paths
сохраняются; wire validation на JSON arrays остаётся strict. AST/rg
аудит прямых `.append/.extend/.sort` на перечисленных source fields
не нашёл mutators; constructor/model_copy helpers всё равно обновляются
так, чтобы не помещать list в tuple field с обходом validation.
Mountain identity_key использует stable origin/radius или tuple(spine),
поэтому этот перенос не меняет формулу identity.

ClimateFeaturePolicy §6.28 дополнительно имеет
synthetic_surface_terrain:TerrainKey и water_feature_terrain:TerrainKey:
existing localFieldFromCoarse использует canonical first terrain,
а anchorDetect отличает liquid_body. Эти значения берутся из owning
terrain defaults/feature policy и входят в I; typed kernel не читает
registry и не забывает ветку определения water feature.

Opaque placement snapshot UID не меняет formula на geometry-dependent
UID. В WaterPlacementContext/WaterPlacementPreparation, PlacementBatch/
PlacementBatchResult добавить snapshot_revision:OutputFingerprint от
terrain dependency. Mapper сверяет world_uid+snapshot_uid+revision;
одинакового старого phase UID недостаточно. Cache ключ при этом —
полный PlanKey. PC-6W переносит revision end-to-end в одном contract
шаге, не активируя GEO-1 zero policy.

GEO schema версии отделены от PC baseline. В
`dataModel/terrain/planning/inputs/geoWaterPlacementInput.py`:
GeoWaterPlacementInput(enabled:bool,resolution_mode:ResolutionMode,
declared_world_bounds:WorldBounds|None,default_water_level:FineZ,
generation:WorldWaterGenerationSettings,defaults:WaterGenerationDefaults,
sea_generation/ocean_generation/lake_generation:CategoryWaterGenerationSettings,
seas:HydrologySeasPolicy,lakes:HydrologyLakesPolicy,
sources:tuple[WaterDesignSource,...],anchors:tuple[WaterAnchorInput,...],
topology:WorldTopology,grid:SurfaceGridSettings,z_min:FineZ,z_max:FineZ,
liquid_keys:frozenset[MaterialKey],noise_policy:ContinentalNoisePolicy,
plate_policy:PlateGenerationPolicy,composition_policy:FieldCompositionPolicy,
selection_policy:WaterFieldSelectionPolicy).
Regions приходят ready dependency `terrain_regions`, не из hidden World.
Domain provider вычисляет cascade/admission/budget/design из этих I/refs;
capture не делает это до cache lookup. Metadata source-path внутри
cached geometry является canonical source UID path; request reporting
адаптирует его к текущему authored collection path, не переносит чужие
array indices. Diagnostic fingerprint не зависит от display labels.

Region provider input в `terrain/regions/regionPlanningInput.py`:
TerrainRegionPlanningInput(snapshot_uid:EntityUid,world_region_uid:EntityUid,
 declared_world_bounds:WorldBounds|None,
topology:WorldTopology,grid:SurfaceGridSettings,
regions:tuple[RegionGeometryInput,...],anchors:tuple[WaterAnchorInput,...]).
RegionGeometryInput(region_uid:EntityUid,geometry:RegionShape|RegionCoverage,
owner_ref:PlanRef|None). Existing claim owner передаёт canonical coverage
и свой ref; authored shape/world region ref=None. Claim от post-hydro
того же generation cycle как pre-water region запрещён cycle check:
validation error, runtime disable affected source с issue, не hidden
post-carve input. Provider выдаёт TerrainRegionsSnapshot + coverages,
площадь каждого extent сверяется с coverage area. World region — из
resolved topology.bounds (включая sphere even-width normalization),
не AABB materialization tile. Application provider использует existing
regionExtent.py::prepare_terrain_regions, тип в своём terrain domain.

В `hydrology/planning/inputs/geoHydrologyPlanInput.py`:
GeoHydrologyPlanInput содержит baseline HydrologyPlanInput fields
§6.28 (полный список там), но sea/lake policies новой schema и
allowed_body_kinds:frozenset[BasinKind], generation:WorldWaterGenerationSettings
and defaults:WaterGenerationDefaults (required captured root sources), plus
sea_generation/ocean_generation/lake_generation:CategoryWaterGenerationSettings
(required captured normalized category sources). Input несёт только capture-time
authored настройки; вычисляемые решения в него не входят и не
capture'ятся. Old sea/ocean autoresolve bool fields в новой schema
отсутствуют. Producer source_decisions — GeoWaterPlacementPlan, поле
source_decisions:tuple[tuple[EntityUid,WaterDesignDecision],...];
hydrology provider читает его через PlanDependencyReader по dependency
`water_placement` и требует decision для каждого accepted source.
Producer classification_decisions — build самого hydrology provider:
общий PolicyResolver разрешает WaterGenerationCategory→
HydrologyGenerationDecision из policy facts до fill; результат —
computed field GeoHydrologyPlan.classification_decisions:
tuple[tuple[WaterGenerationCategory,HydrologyGenerationDecision],...].
Оба решения не являются authored input values и не входят в input
fingerprint; их revision фиксируется dependency envelope ref.
Fill потребляет accepted specs/decisions; rivers policy/mode остаётся
baseline до отдельного HY-RIV-1. SourceBodyMapping — новый required
payload field GEO HydrologyPlan, его reference берётся с envelope.
CoastlineBoundaryInput в hydrology/boundaries/attachedCoastline.py:
sources:tuple[DeclaredCoastline,...] с purpose BODY_BOUNDARY,
resolution_mode:ResolutionMode,grid:SurfaceGridSettings,topology:WorldTopology. Dependencies — final
hydrology и water placement refs, никаких nearest-water guesses.

GeoSurfacePlanningView в existing application contracts/surfacePlanningView.py
имеет те же world_uid/revision/kind и climate/terrain/relief/local fields,
но GeoWaterPlacementInput/GeoHydrologyPlanInput вместо baseline типов,
а также region_input:TerrainRegionPlanningInput,
boundary_input:CoastlineBoundaryInput,
surface_support:SurfaceSupportInput и coating_input:CoatingPlanInput.
`SurfacePlanningCapture.capture_geo(world,locations,*,mode,
region_states:tuple[RegionState,...],
relief_templates:tuple[tuple[EntityUid,ReliefTemplate],...],
region_claims:tuple[RegionGeometryInput,...],resolve_ctx)->GeoSurfacePlanningView`.
Caller получает дополнительные sources из same authoritative read/draft
view; source revision/fingerprints включают их actual values/member UIDs.
Geo view также имеет river_relief:RiverReliefInput и
hydrology_final:HydrologyFinalInput; capture_geo получает required
mountain_templates:tuple[MountainTemplateInput,...] по §6.31-E.
Полный return type capture_geo — GeoSurfacePlanningView|NoExtentSurfacePlanningView
по G0-S §6.15; NoExtent не подменяется constructed READY input.
capture_geo заполняет coating_input из тех же authored shore/
default_shore settings с membership check по контракту ниже; его
actual values входят в revision/fingerprint наравне с остальными
inputs. Assembler передаёт coating_input в PlanRequest[CoatingPlanInput]
provider'у, который не перечитывает world settings.
Source claim ref обязан относиться к этой view. Нет generic raw bag.
GEO assembler order по §6.30: climate_base → terrain_base →
terrain_regions → water_placement → relief (pre-river: суша, горы,
овраги, дно) → hydrology routes/fill → relief (riverbed, второй вызов)
→ hydrology final → climate_local → boundary/support → coating.
Exact envelope/slot shape заморожен в §6.31-E. Shared PlanningService
остаётся generic, эти bindings знает composition.

Factory получает effective strategy из общего policy decision.
Complete authored basin/lake при отсутствии explicit body strategy
имеет domain-declared AUTHORED_REGION case: global procedural strategy
не переписывает его required shape/floor. Явный incompatible procedural
strategy на complete authored source — SOURCE_STRATEGY_MISMATCH, не
потерянный setting. Procedural source требует autoresolve=True; False
даёт normal disabled через общий engine. Coastline auto=True использует
выбранную procedural strategy с path/water_side constraint; auto=False
сохраняет полноценный authored geometry path. Единственный implicit
world source — ocean в world region (kind default owning defaults POJO);
sea/lake sources создаются из объявленных sources/regions, не как три
конкурирующие копии всего world budget. При disabled ocean/auto=False
implicit source не создаётся; это domain-declared admission behavior.

WaterDesignInput из L обязательно содержит actual immutable
pre_hydrology:PlanEnvelope[TerrainPlan] и region_coverage:RegionCoverage,
а не один непригодный для sampling opaque ref. pre_hydrology_ref —
computed property envelope.ref. По согласованному G4 supplement authored
draft возвращает footprints:tuple[frozenset[Coord],...], coordinate_space,
metadata/profile; procedural draft возвращает ContinentalField с recipe,
metadata/profile и без footprints. Threshold/выбор procedural footprints
и existing PlacementCandidate выполняет общий G4-C preparer один раз.
PlacementIdentity.region_uid — per-object identity existing adapter,
не generation_region_uid: несколько тел могут использовать один регион.
Для auto coarse candidate разрешена только полная cell внутри region
(intersection area == cell fine area); boundary partial cells не
прорезают запретную область ради процента. Недостижимый quota даёт
shortfall; authored fine→coarse collapse — отдельный явный issue.
SampledFloorProfile space совпадает с BasinSpec space. Field profile
floor_z bound=max(z_min,level-depth); sampled floor_z=min(samples).
Один floor writer, никаких повторных threshold/placement в L2.

GEO auto требует именно declared fixed world_bounds. Geo input хранит
его отдельно от materialization topology/AABB; совпадение bbox значений
не скрывает отсутствие required authored extent. Region snapshot
world_region:TerrainRegionExtent|None: None при отсутствии declared bounds,
не AABB fallback. Auto source получает validation issue / runtime
DISABLE_OBJECT fallback до field sampling; explicit authored источники
могут продолжить по своему terrain-owned extent без global budget.
Global coverage report тогда status=UNAVAILABLE_WORLD_EXTENT,
actual_fraction=None, не выдуманные 0%/AABB процент. World bounds error
обязателен при запрошенном auto; при authored-only это отсутствие
неиспользуемого global metric. Добавление world_bounds даже равного
старому AABB меняет Geo input/fingerprint (presence теперь explicit).
ResolutionMode исключается из StateViewRevision во ВСЕХ request inputs,
но входит в artifact key каждого mode-dependent provider; field facts,
не зависящие от mode, могут разделять cache. HydrologyExecutionMode
(DISABLED/DECLARED_ONLY/AUTORESOLVE) — отдельное поведение, не эту ось.
Exclusion задаётся конкретными typed field refs, не фильтром имени
mode: ClimateBaseInput.mode:ClimatePoleMode — authored generation input,
он обязательно остаётся в source revision и climate_base key.
Начальные schema/algorithm versions PC bindings =1/1, GEO изменённых
bindings =2/1; cache envelope codec version=1. Изменение формул/POJO
knobs требует соответствующей version либо входного value change.

Источник runtime resource configuration:
`dataModel/planning/policy/planningRuntimeSettings.py::PlanningRuntimeSettings`
с required cache:CachePolicy и execution:PlanningExecutionPolicy;
`core/appSettings.py::AppSettings.planning:PlanningRuntimeSettings|None=None`.
Existing ConfigManager._to_flat/_to_nested/update adapters читают/пишут
TOML [planning.cache]/[planning.execution] через typed POJO normalization;
None означает отсутствие секции, не TOML null и не Unlimited. В PC-3
добавляются schema/IO tests, числовые лимиты не угадываются в коде.
До PC-9 activation deployment обязан передать explicit policy values;
Container проверяет required presence/limits до запуска planning service
и сообщает startup validation error. Нового per-world persisted cache
settings object нет. Common cache/planning consumers получают готовые
policy POJO, не raw config dictionaries. core/ сейчас13→13 файлов:
правятся existing appSettings/configManager, новый файл там не создаётся.

GEO output binding конкретизирован отдельно от baseline:
GeoWaterPlacementPlan в terrain/planning/waterPlacementPlan.py расширяет
WaterPlacementPlan полями outcomes:tuple[PlacementOutcome,...],
metadata:tuple[WaterSourceMetadata,...],
source_decisions:tuple[tuple[EntityUid,WaterDesignDecision],...],
budget:WaterCoverageBudget|None.
GeoHydrologyPlan в hydrology/planning/hydrologyPlan.py расширяет
HydrologyPlan полями source_mapping:SourceBodyMapping (required) и
classification_decisions:tuple[tuple[WaterGenerationCategory,
HydrologyGenerationDecision],...] — computed provider result, не input.
Baseline HydrologyPlan (PC-1H) несёт required
declared_paint:DeclaredWaterPaint — L0-facing frozen payload как typed
records без ссылок на World/locations; поля соответствуют existing
LoadedDeclaredHydrology (lake_specs[].shoreline_segments,
coastline_segments, river corridors). Producer — hydrology provider из
captured authored inputs на revision входа. Consumer —
HydroContributor/apply_declared_basins/apply_declared_rivers: PC-10
переводит их на envelope и убирает load_declared_hydrology из bake
path. Fine→light conversion и tile-scoped paint_role остаются в
contributor.
Ravine/depression detection для L0 — scope-independent: вход — frozen
light-scale surface field полного generation extent, не compose cells
ограниченные ctx.tiles; носитель поля и provider binding (владелец
terrain/relief домен) фиксируются PC-0. Detected ravine cell set —
frozen planning output на revision; RavineContributor красит только
пересечение detected set с requested tiles и применяет
resolve_ravine_surface_z по замороженным cells. Partial re-bake не
изменяет состав депрессий относительно full bake.
TerrainRegionPlan в terrain/regions/terrainRegionsSnapshot.py содержит
snapshot:TerrainRegionsSnapshot,coverages:tuple[RegionCoverage,...].
SurfaceSupportPlan в surfaceCoatingFacts.py: facts:tuple[SurfaceCoatingFacts,...].
CoatingPlan там же: cells:tuple[CoatingCellPlan,...], полный cell/decision/target
контракт ниже. CoatingCellPlan принадлежит тому же surfaceCoatingFacts.py.
FineXY/face unique, decisions computed в planning, materializer применяет
их без нового policy resolve. Surface facts evidence содержит
support_input_fingerprint:InputFingerprint (artifact inputs), не полный
StateViewRevision в кэшируемом payload; coherence — через envelope refs.

`GeoSurfacePlanBundle` — отдельный immutable record в
application/worldData/planning/contracts/surfacePlanBundle.py:
world_uid:EntityUid,view_revision:StateViewRevision,
climate_base:PlanEnvelope[ClimateBasePlan],terrain_base:PlanEnvelope[TerrainPlan],
terrain_regions:PlanEnvelope[TerrainRegionPlan],
water_placement:PlanEnvelope[GeoWaterPlacementPlan],relief:PlanEnvelope[ReliefPlan],
hydrology_routes:PlanEnvelope[GeoHydrologyRoutesPlan],
river_relief:PlanEnvelope[RiverReliefPlan],
hydrology:PlanEnvelope[GeoHydrologyPlan],climate_local:PlanEnvelope[ClimateLocalPlan],
coastline_boundaries:PlanEnvelope[CoastlineBoundaryPlan],
surface_support:PlanEnvelope[SurfaceSupportPlan],coating:PlanEnvelope[CoatingPlan].
Слоты показаны для baseline; §6.30 требует второго relief выхода и
фазового hydrology — состав заморожен §6.31-E до кода.
Нет subclass override invariant PlanEnvelope[T] полей baseline bundle.
SurfacePlanningAssembler.prepare_geo(view:GeoSurfacePlanningView,*,
wait:PlanWaitControl)->GeoSurfacePlanBundle|None; baseline prepare API
не принимает Geo view через cast. После PC-11.7 legacy context/projector удалён;
GEO request entry связывает domain working views из typed Geo refs,
не восстанавливает to_legacy_context или eight-field compatibility transport.
Geo input/output registry pairs: GeoWaterPlacementInput→GeoWaterPlacementPlan,
GeoHydrologyPlanInput→GeoHydrologyPlan, TerrainRegionPlanningInput→TerrainRegionPlan,
CoastlineBoundaryInput→CoastlineBoundaryPlan,
SurfaceSupportInput→SurfaceSupportPlan; coating input:
CoatingPlanInput с resolution_mode и resolved targets по полному контракту ниже,
dependencies surface_support/
hydrology. CoatingPlanInput объявляется в surfaceSupportInput.py; output
CoatingPlan. Новый compile-time pair не подменяет I/T baseline версии.

Typecheck configs оба находятся в backend/tests/typing/planning/:
pyrightconfig.valid.json extends ../../../../pyrightconfig.cascade.json,
include: ../../../app/dataModel/{planning,cache},
../../../app/application/{planning,cache,worldData/planning}, valid.py;
pyrightconfig.invalid.json extends ./pyrightconfig.valid.json, include invalid.py.
Включения в реальном JSON — отдельные пути без shell brace expansion.
Folder содержит два Python cases, два config и init =5 файлов.
Новый root-level config в переполненную папку не добавляется.

Итоговая композиция новых leaf folders (включая init):
identity2; surfacePlanning2 (§6.33); planning/identity3, contracts5, diagnostics2, policy3;
cache/identity2, contracts4, policy2; validation/diagnostics3,enums2;
spatial/grid5; climate/planning3, inputs3; terrain/planning3, inputs4;
terrain/regions5; terrain/relief/planning2, inputs2, bathymetry3,
surfaceCoating4; hydrology/generation5,enums/planning5,policy3,sources4,
planning3,inputs3,boundaries2; application/worldData/planning/composition4,
contracts3,validation3; placement/lifecycle2,adapters/coastline2;
app/ids/water2. Имя inputs относится к ближайшему названному planning.
Отдельный count audit: `dataModel/spatial/extentFraction.py` — новый
файл в existing root dataModel/spatial (3→4 непосредственных файла с
init: facing, regionShape, extentFraction), лимит не нарушается; общий
тип ExtentFraction и extent_radius_fine для §6.10/seas fraction fields.
В existing больших roots иные новые files не добавляются. Directories
считаются отдельно от files; названия классов не создают лишние modules.
Test leafs max5 по §6.27/L, родительские init уже учтены.
Legacy source folders со значениями >5 требуют WARN; current→future
количество direct files неизменно (только edits/re-exports), как сообщено
в чате. Создание дополнительного файла требует повторного count audit.

Последний output join для coating: SurfaceCoatingAction в
surfaceCoatingPolicyDefinition.py имеет APPLY_SHORE_SURFACE и
KEEP_EXISTING_SURFACE. CoatingPlanInput в surfaceSupportInput.py содержит
resolution_mode, default_target:FactValue[ShoreCoatingTarget],
targets:tuple[tuple[HydrologyShoreKind,FactValue[ShoreCoatingTarget]],...].
ShoreCoatingTarget(terrain:TerrainKey,material:MaterialKey) — resolved
projection existing WorldHydrology default_shore/category shore settings;
input capture проверяет membership. Unknown/invalid target — applicable
policy issue с declared KEEP_EXISTING_SURFACE fallback, не consumer
подстановка sand/shore. CoatingPlan output содержит tuple[CoatingCellPlan],
CoatingCellPlan(cell:FineXY,face:Facing|None,
decision:ValueSelectionDecision[SurfaceCoatingAction,SurfaceCoatingReason],
target:ShoreCoatingTarget|None). APPLY требует non-null target, остальным
он не нужен. Materializer получает ключи с decision, не читает заново I/
world policy и не выбирает material по enum действия самостоятельно.

Exact provider methods добавлены к owning classes, без новых modules:
regionExtent.py::TerrainRegionPlanProvider.build(PlanRequest[TerrainRegionPlanningInput],
PlanDependencyReader,PlanBuildControl)->PlanBuildResult[TerrainRegionPlan];
adapters/coastline/attachedCoastline.py::AttachedCoastlineAdapter.build(
PlanRequest[CoastlineBoundaryInput],PlanDependencyReader,PlanBuildControl)
->PlanBuildResult[CoastlineBoundaryPlan];
surfaceCoatingSupport.py::SurfaceCoatingSupportProvider.build(
PlanRequest[SurfaceSupportInput],PlanDependencyReader,PlanBuildControl)
->PlanBuildResult[SurfaceSupportPlan];
в том же terrain/relief/surfaceCoatingSupport.py::CoatingPlanProvider.build(
PlanRequest[CoatingPlanInput],PlanDependencyReader,PlanBuildControl)
->PlanBuildResult[CoatingPlan]. Последний только связывает terrain
PolicyDefinition и общий PolicyResolver, не реализует private resolve.
Composition регистрирует эти I/T pairs вместе с base provider bindings;
их фазовый состав заморожен PC-0 в §6.31-E.

**Готовность после PC-0:** архитектурное уточнение §6.30 заморожено
в конкретных schemas/dependencies §6.31 и нормативных разделах ТЗ.
Это contract/design freeze, не runtime acceptance новых providers;
PC-1…12 и отдельные GEO code steps ещё не выполнены.

### 6.30 Уточнение мастера: terrain/relief до гидрологии и повторный вызов для русел

**Согласовано 2026-10-22.** Нормативный контракт —
[tz_terrain_generation §Terrain/relief и гидрология: порядок планирования](../../docs/tz_terrain_generation.md#terrain-relief-hydrology-planning).
Это фиксация архитектурного решения, не утверждение об уже выполненном
cutover и не закрытие PC-0/PC-12.

1. Terrain/relief — владелец планирования геометрии и изменения высот:
   базовая поверхность, горы, овраги, дно морей/океанов/озёр и русла рек.
   Его первый этап до гидрологии объединяет рельеф суши и дно водоёмов.
   «Один проход» означает один согласованный этап планирования; внутри
   сохраняется явный порядок зависимых вычислений и общий placement.
   Авторские water intents, уровни и принятые placement constraints могут
   быть входами дна; результат будущего fill не становится его опорой.
2. Горы выбираются один раз в terrain/relief, включая authored/anchor/auto
   sources, размещение, форму, разрешённые стороны templates и параметры
   высоты. Coarse/light/fine — проекции этого решения. Готовые гидрология,
   landcover и ctx.tiles не определяют заново состав/геометрию гор.
   Исходные высоты, климат и авторские ограничения остаются входами.
   Та же граница planning/consumption распространяется на овраги и дно.
3. Гидрология читает готовый pre-river рельеф, рассчитывает заполнение,
   физические объединения водоёмов и речные маршруты и завершает свою
   фазу. Повторный вызов terrain/relief с готовыми маршрутами выполняет
   world-surface composition (п.5) — гидрология не вызывает relief
   напрямую и не становится assembler. После прорезки composition
   запускает итоговую фазу гидрологии: водные факты рассчитываются по
   post-river высотам; сама fill/classify/shore surface_z не меняет.
4. Повторный вызов relief не перезапускает горы, овраги и дно водоёмов.
   Фазы имеют явные входные/выходные refs одной coherent source view:
   pre-river terrain → hydrology/routes → river relief → final hydrology.
   Post-river output не подаётся назад в source search/первый relief того
   же run; не вводится неявный итеративный fixed-point loop.
5. World-surface composition задаёт порядок и передаёт typed результаты;
   domain call не превращает HydrologyGeneratorService в cross-domain
   assembler. L0/L2 материализуют соответствующие проекции по запросу,
   без повторного выбора объектов, placement, template pick или формы дна.

**Следствия для frozen contracts и ledger PC-0.** Прежние шесть bindings
§6.26 описывают current-baseline migration и не доказывают готовность
уточнённого target. До кода затронутых providers/cutover PC-0 синхронизирует
полные schemas, версии, dependencies, capture inputs и producer/consumer
paths с этим решением; старый список bindings не расширяется догадками.
Состав implementation шагов не меняется молча, HY-RIV-1 fine source-search
остаётся отдельным треком. Его отсутствие не разрешает выдавать старый
coarse source search за целевой.

**Исторический перечень frozen items, устаревших от §6.30.**
Все перечисленные ниже варианты закрыты конкретным выбором в §6.31;
этот перечень сохраняет причину изменения, не открытый implementation choice:
- слоты SurfacePlanBundle/GeoSurfacePlanBundle выше: один relief и один
  hydrology envelope не выражают две фазы; нужны явные refs на pre-river
  relief, riverbed relief и final hydrology либо phased envelope —
  выбор формы принадлежит PC-0, не коду;
- GEO assembler order выше: между relief и hydrology встают hydrology
  routes → второй relief вызов → final hydrology;
- контракты PC-7/PC-8: relief provider получает вторую фазу (русла),
  hydrology provider разделяется на routes/fill и final водные факты;
- SurfaceSupportDependencies.hydrology обязан ссылаться на final
  (post-river) envelope;
- зависимость «base provider bindings §6.26 / six base providers»
  пересматривается по фазовому составу.

В поимённый PC-10 ledger входят MountainContributor и
MountainMaskMaterializer.collect наряду с RavineContributor и hydro.
collect_mountain_entries_for_coarse и autoresolve_mountain_specs не должны
оставаться двумя независимыми выборами объектов. Carrier общего mountain
layout/light-relief recipe фиксируется до cutover, включая используемые
template inputs и их immutable projection; frozen оболочка ReliefTemplate
с mutable lists не является допустимым cached input. Existing правила
terrain merge остаются своим контрактом; изменение покрытия не запускает
новый выбор гор или неявное изменение их геометрии.

Mountain contract меняется только каналом доставки, не пайплайном:
selection остаётся внутри первого relief этапа (existing порядок
mountain → ravine → basin), новых фаз, provider pairs и dependency
edges не добавляется; hydrology по-прежнему читает готовый post-mountain
surface. Единственное изменение — один frozen output вместо трёх
независимых выборов. Carrier — ReliefPlan.mountain_layout:MountainLayout
(§6.31-B); exact record fields заморожены PC-0. Layout обязан покрывать
все входы трёх named consumers: coarse entries MountainContributor,
specs MountainMaskMaterializer.collect и collect_mountain_entries_for_coarse.
Нужного consumer-поля нет в layout → расширение контракта, не второй
selection path. Смешанное состояние запрещено: PC-10/PC-11 переводят
всех named consumers одним cutover; интервал, где часть читает frozen
layout, а часть повторно выбирает объекты, недопустим. Mountain
identity formula (stable origin/radius или tuple(spine)), selection
inputs и algorithm не меняются; template inputs входят в layout как
immutable projection (связь с PC-0I/G9-ST).

**Приёмка уточнения:** один выбор mountain layout на input revision;
coarse/light/fine имеют согласованные identity/geometry; full/partial и
порядок tiles не меняют горы/овраги; template edit инвалидирует нужный
closure; геометрию дна/русла и surface_z меняет только terrain/relief;
river carve не выполняется дважды; final hydro использует post-river ref,
а source search — pre-river ref. Изменения baseline от устранения двух
выборов принимаются явно, а не маскируются под cache-only equivalence.

### 6.31 PC-0 freeze — точные фазовые контракты (2026-10-23)

**Нормативная фиксация PC-0, без runtime implementation.** Этот раздел
заменяет baseline схемы §6.25–6.29 ровно в перечисленных ниже полях,
bindings, signatures и activation points; остальные полные contracts
§6.25–6.28 сохраняются. Варианты «или phased envelope» из §6.30 закрыты:
выбраны отдельные типизированные envelopes. PC-0 не закрывает PC-12.

#### A. Общие API, canonical encoding и версии

Все общие records, CacheBackend/CacheService/PlanningService API, failures,
single-flight, resource policies, diagnostics и immutable admission из
§6.25/6.27 заморожены. Следующее уточнение устраняет неявный world accessor:
RegisteredPlanContract.fingerprint_inputs имеет signature
`(world_uid:EntityUid,scope:PlanScope,inputs:I,
dependencies:tuple[PlanDependency,...])->InputFingerprint`.
PlanDependencyContract в dataModel/planning/contracts/planDependency.py:
`slot:PlanSlot,contract_id:PlanContractId,schema_version:SchemaVersion,
algorithm_version:AlgorithmVersion`. RegisteredPlanContract дополнительно
имеет required dependency_contracts:tuple[PlanDependencyContract,...].
Slots unique; generic service перед lookup проверяет exact set slots и
metadata каждого ref, PlanDependencyReader — exact selected envelope ref
и registered payload codec. Extra/missing/wrong phase dep rejected на HIT
так же, как на MISS. Списки deps §6.31-E задают эти declarations; engine
не знает названий world domains. Registry принимает один registered handle
на contract id; подмена validate/codec при совпавшем id не разрешается.
Metadata версии берутся из зарегистрированного handle. Service передаёт
world/scope из проверенного request.key и пересчитывает digest до lookup.
Input fingerprint не используется как собственный вход.

Canonical codec v1 — бинарный TLV: tag один byte; длина payload unsigned
64-bit big-endian; payload. Tags: 0=None, 1=bool (один byte 0/1), 2=int
(sign byte 0/1 + минимальная big-endian magnitude; zero — sign byte 0
и один magnitude byte 0, negative zero/leading zeroes rejected),
3=float (IEEE754 binary64 big-endian, finite, -0 нормализуется к +0),
4=UTF-8 str, 5=bytes, 6=enum, 7=record, 8=ordered tuple, 9=frozenset.
Enum payload — codec tuple (registered enum type id, wire value); record —
codec tuple (registered schema type id, tuple(field-name,value) в declared
field order). Tuple payload — concatenation TLV элементов. Set payload —
та же concatenation после lexicographic sort encoded elements. Type ids
задаются binding schema manifest; перенос Python-модуля сам по себе их
не меняет. Maps представлены sorted tuple pairs, grid order (y,x), light
order (gy,gx,ty,tx); paths/manual anchors/first-match rules сохраняют order.
Bool не принимается как int; NaN/inf, duplicate map keys, unknown type ids,
noncanonical encodings и trailing bytes rejected. Bytes digest ровно 32.

F = SHA256(codec((contract_id,schema_version,algorithm_version,world_uid,
scope,I,dependencies_sorted_by_slot))). OutputFingerprint =
SHA256(codec((payload,dependencies,diagnostics))). CacheItemKey =
SHA256(codec(PlanKey)). Не использовать repr/pickle/Python hash либо
legacy JSON state_fingerprint как замену этому encoding. Generation seed
по-прежнему app.ids.seed_int(world), UID formulas unchanged.

Первое исполнение уточнённых PC bindings: schema=1, algorithm=1,
cache envelope codec=1. Старые six-binding schemas никогда не активировались
и не получают runtime compatibility namespace. GEO изменённые I/T bindings
сохраняют отдельную schema=2, algorithm=1; неизменённые используют PC handle.
Phase — registered contract id/slot, не свободное строковое поле payload.
Wire values новых enums: PlanScopeKind WORLD=world/REGION=region;
CacheLookupStatus HIT=hit/MISS=miss; CacheEvictionPolicy LRU=lru;
CacheAdmission STORED=stored/SKIPPED_OVERSIZE=skipped_oversize;
PlanDiagnosticDisposition ERROR=error/FALLBACK=fallback/NOTICE=notice;
ResolutionMode RUNTIME=runtime/VALIDATE_ONLY=validate_only;
SurfacePlanningViewKind READY=ready/NO_EXTENT=no_extent.
CacheFailureReason и PlanContractFailureReason кодируются lower_snake_case
именами перечисленных §6.25 members (contract_mismatch/invalid_payload/
backend_failure и unknown_contract/invalid_input/dependency_mismatch/
key_mismatch). Existing доменные enum wire values не меняются.
CachePolicy TTL=None, LRU; byte/worker/queue limits только required config
из PlanningRuntimeSettings (§6.29-M), числовых fallback нет.

#### B. Единый mountain layout и frozen источники

В `dataModel/terrain/relief/planning/reliefPlan.py`:
- `MountainTemplateInput(template_uid:EntityUid,context:ReliefContext,
  side_recipe:MountainSideRecipe|None)` — projection library member body.
  Передаются mountain-context members, sorted unique по member UID.
  Отсутствующий required template — issue/unresolved, не пустая recipe.
  None recipe на существующем member сохраняет existing Mode D.
- `MountainLayout(entries:tuple[MountainDeclareEntry,...],
  templates:tuple[MountainTemplateInput,...],
  world_pick:ReliefContextPickPolicy,terrain_key:TerrainKey)`.
  Entries — окончательно merged/stamped specs. Для single peaks и peaks
  внутри range sides полностью разрешены; длина равна form_side_count.
  Полные MountainSpec/MountainRangeSpec fields сохраняются, включая form,
  kind, range sides, spine, peaks, spacing, saddles, location_uid и
  object relief_pick_policy. Consumer не восстанавливает потерянное поле.
  Entries unique по прежнему identity_key и сохраняют canonical selection
  order; templates соединяются по UID, не по позиции entries.

Единственный selection kernel — existing
`collect_mountain_entries_for_coarse` с frozen input adapter: enumerate
полного TerrainPlan.bbox row-major, existing coarse ridge candidates,
declared > anchor > auto merge и existing seeded passBuilder. Затем один
template stamp теми же pick/kindRoll/Form/SideFill algorithms. Это
канонический выбор объектов; light `autoresolve_mountain_specs` больше
не выбирает отдельный набор. Seed/identity formulas не меняются.
Новый mountain provider/slot не добавляется: output принадлежит relief.
Light-результат от удаления прежнего отдельного selection — явное изменение
baseline, принимаемое через PC-10/12, а не обещание побитового равенства
обоим несовместимым прежним наборам гор.

В `dataModel/terrain/relief/planning/inputs/reliefPlanInput.py` к полному
ReliefPlanInput §6.28 добавляются required
`mountain_templates:tuple[MountainTemplateInput,...]`,
`mountain_pick:ReliefContextPickPolicy`,
`terrain_merge:tuple[TerrainMergeEntry,...]`.
`TerrainMergeEntry(key:TerrainKey,merge_rank:int)` в том же input file —
resolved projection existing TerrainRegistryEntry.merge_rank; strict int,
unique sorted registry keys. Membership и canonical engine fallback
разрешаются capture, не cached consumer. Existing terrain merge helper
получает typed projection вместо повторного World lookup; отдельный
resolver приоритетов не создаётся.

PC-0I дополнительно переводит **только**
MountainSideRecipe.side_kinds в tuple[ReliefSideKind,...]|None,
с прежними XOR/default/JSON-array semantics. Полный ReliefTemplate с
conditions/structure_refs lists не кэшируется и не мигрирует ради PC.
Existing ReliefContextPickPolicy и ObjectReliefPickPolicy уже scalar/frozen;
member references проверяются capture; их string storage не становится
новым свободным selector в planning API.

#### C. Coarse/light relief outputs и declared-water paint

`LightCellRef` единственным определением переносится из
application/worldData/masks/footprint.py в
dataModel/spatial/grid/coordinateTypes.py в PC-0G2; old module re-exports
тот же class с прежними gx/gy/tx/ty и as_absolute. Strict integer fields;
boundary проверяет 0<=tx,ty<grid.light_side и macro cell внутри bbox.
Это light coordinate record, не FineGridCoord и не WorldBounds.

В reliefPlan.py дополнительные frozen records:
- `LightMountainCell(cell:LightCellRef,surface_z:FineZ,facing:Facing|None)`.
- `LightRavineCell(cell:LightCellRef,surface_z:FineZ)`.
- `LightReliefPlan(base_surface_z:tuple[tuple[LightCellRef,FineZ],...],
  mountain_cells:tuple[LightMountainCell,...],
  ravine_cells:tuple[LightRavineCell,...],ravine_terrain:TerrainKey,
  terrain_merge:tuple[TerrainMergeEntry,...])`.
- `ReliefPlan(surface_z:tuple[tuple[SurfaceGridCoord,FineZ],...],
  mountain_layout:MountainLayout,light:LightReliefPlan)`.

Coarse surface полная post-mountain/ravine/basin pre-river. Light base
полная на том же bbox с grid.light_side² cells на macro cell. Она
воспроизводит existing ReliefContributor base+noise/clamp из terrain_base
и seed. Mountain sparse absolute z/facing проецируются из того же
MountainLayout Form/SideFill/max-rise. Ravine detection выполняется на
полном immutable light base+mountain field, existing NEIGHBORS_8/
min_drop/min_neighbors, с соседями внутри полного extent, без wrap
добавления, которого current detector не делает. Результаты unique,
sorted, z в bounds. False masks/category/autoresolve дают empty effect
tuple, не фиктивный рельеф. Temporary full light buffers — planning RAM,
не L0 pack writes и не full fine-world array; oversize admission следует
общей resource policy без clipping геометрии.

Landcover/terrain paint не выбирают горы и не меняют выбранный height
effect. Contributors читают frozen absolute relief z, а terrain color
проходит existing merge helper; отклонённый color не запускает другой
mountain/ravine selection. Этот target устраняет legacy зависимость z
от успешности mountain paint и проверяется как явный baseline delta.

В `dataModel/hydrology/planning/hydrologyPlan.py`:
- `LakePaint(location_uid:EntityUid|None,
  shoreline_segments:tuple[tuple[FineXY,FineXY],...])`.
- `CoastlinePaint(location_uid:EntityUid|None,
  segments:tuple[tuple[FineXY,FineXY],...])`.
- `SegmentRiverPaint(edge_uid:EntityUid,location_uid:EntityUid|None,
  segment:tuple[FineXY,FineXY],width_fine:FineDelta)`; width strict >0.
- `IntentRiverPaint(river_uid:EntityUid,path:tuple[FineXY,...],width_wire:int)`;
  path >=2; width из existing HydrologyMaskWire clamp, strict valid wire int.
- `DeclaredWaterPaint(lakes:tuple[LakePaint,...],
  coastlines:tuple[CoastlinePaint,...],segments:tuple[SegmentRiverPaint,...],
  intents:tuple[IntentRiverPaint,...])`.

Producer hydrology_routes из authored frozen inputs разрешает location
refs и path exactly как legacy loader/L0 intent adapter. Geometry order
сохраняется. Segment width fine→light dilation и intent width_wire без
dilation сохраняют разные current semantics. Нет живых locations в T.
Invalid/missing geometry даёт deterministic diagnostic без synthetic path.
HydrologyPlan.declared_paint переносится из этого output без нового loader.
HydroContributor делает только fine→light raster/paint, сохраняет порядок
river corridors → lake/coastline → coarse open water и river preservation.

#### D. River routes → terrain riverbed → final water

Все новые records immutable, required fields, no default injection.
`S` ниже — invariant coordinate parameter с двумя зарегистрированными
bindings: SurfaceGridCoord либо FineXY; union разных spaces внутри route
запрещён. Records в hydrology/planning/hydrologyPlan.py:
- `RiverPathSegment[S](path:tuple[S,...],connection_type:HydrologyConnectionType,
  edge_uid:EntityUid|None,location_uid:EntityUid|None,declared:bool)`.
- `RiverRoute[S](river_uid:EntityUid,segments:tuple[RiverPathSegment[S],...],
  receiver_cell:S,drainage:RiverDrainageLink)`; path order и segment order
  meaningful; минимум один land-bed cell; receiver terminal, не bed.
  Drainage existing receiver_cell остаётся fine diagnostic coordinate,
  typed receiver_cell S — рабочая координата. UID/receiver/rooted-drainage
  proof обязательны; ранее отклонённые routes остаются diagnostics.
- `HydrologyRoutesPlan(coarse_open_water:
  tuple[tuple[SurfaceGridCoord,MapCellHydrology],...],
  water_bodies:tuple[WaterBody,...],physical_unions:tuple[PhysicalWaterUnion,...],
  coarse_routes:tuple[RiverRoute[SurfaceGridCoord],...],
  fine_routes:tuple[RiverRoute[FineXY],...],
  fine_base_surface_z:tuple[tuple[FineXY,FineZ],...],
  declared_paint:DeclaredWaterPaint)`.

Provider routes не пишет z и вызывает доменный assembly API по
tz_terrain_generation §PC-D1. Доменные владельцы переиспользуют existing
fill/route validation/fallback/drainage-order semantics из
assemble_rivers/prepare_river_requests
и fineHydrologyIndex. Route feasibility проверяется на pre-river relief;
проверка наличия land-bed cells — проверка path/receiver/missing heights,
а не запись профиля. Fine base — existing sparse terrain sampling тех же
pre-river heights, покрывает все accepted fine route cells и receiver.
Coarse routes используют coarse_open_water; fine sampling учитывает
принятые coarse route occupancy/drainage claims без чтения post-carve z.
Это baseline routing; HY-RIV-1 fine procedural source search не включается.

В dataModel/terrain/relief/planning/inputs/reliefPlanInput.py:
`RiverReliefInput(z_min:FineZ,z_max:FineZ,grid:SurfaceGridSettings,
topology:WorldTopology,channel_depths:
tuple[tuple[HydrologyConnectionType,int],...])`.
Depths strict positive и полностью покрывают типы existing policy;
capture получает их через HydrologyRiversPolicy.channel_depth_for,
не копирует defaults. В reliefPlan.py:
- `RiverBedRecord[S](river_uid:EntityUid,bed_z:tuple[tuple[S,FineZ],...])`.
- `RiverReliefPlan(surface_z:tuple[tuple[SurfaceGridCoord,FineZ],...],
  fine_surface_z:tuple[tuple[FineXY,FineZ],...],
  coarse_beds:tuple[RiverBedRecord[SurfaceGridCoord],...],
  fine_beds:tuple[RiverBedRecord[FineXY],...])`.

RiverReliefPlanProvider — terrain-owned profile computation и single
writer; existing river_bed_spec переносится из hydrology/rivers/
riverBedProfile.py в terrain/reliefObjects/riverBed/riverBedZ.py,
old symbol — compatibility re-export до атомарного cutover. Writer и
RiverBedSpec остаются existing single definitions. Snapshot working copies
создаются из relief.surface_z и routes.fine_base_surface_z. Profile
z=min(pre_z,max(z_min,pre_z-depth)), actual receiver исключён, все specs
вычисляются от pre-river base; overlapping targets merge min один раз,
не последовательный повторный depth subtraction. Не меняются receiver
floors, mountains/basins заново не строятся. Route/bed join по river_uid
внутри space, не zip/entry index. Complete coarse surface и sparse fine
surface включают unchanged sampled cells: legacy fine_z_overrides
передаёт полный sampled output, не только changed bed cells.

Final provider не ищет routes, не делает carve и не открывает новый auto
water discovery. Он сохраняет принятые bodies/unions из routes-stage,
строит river roles/drainage/waterfall facts по actual post-river bed и
передаёт DeclaredWaterPaint. Заполнение/классификация не создают нового
набора водоёмов из post-river minima. Existing HydrologyPlan §6.26 fields
сохраняются: coarse_surface_z из river_relief.surface_z;
fine_z_overrides из river_relief.fine_surface_z; coarse/sparse_fine hydro
из accepted routes+actual beds. Диагностика предыдущих stages не
копируется в новый envelope, request собирает её по ref каждого stage.
Unexpected incomplete bed/receiver mapping — contract/build failure,
не поздний silent reroute. No-river case выдаёт те же complete coarse
heights, empty route/bed tuples; disabled water не выключает terrain.

В hydrology/planning/inputs/hydrologyPlanInput.py новый
`HydrologyFinalInput(enabled:bool,grid:SurfaceGridSettings,
topology:WorldTopology)`; policy decisions/routes/water identities уже
приходят dependencies и повторно не разрешаются. В ReadySurfacePlanningView
добавляются river_relief:RiverReliefInput и hydrology_final:HydrologyFinalInput;
существующее hydrology:HydrologyPlanInput — input routes-stage. Они derived
из того же captured source, не второй read. WaterPlacementInput дополняется
z_max:FineZ для полной world z validation specs. ClimateFeaturePolicy
включает оба TerrainKey поля из §6.29-M.

#### E. Exact bindings, bundles, capture и coherence

Имена surface slots задаёт SurfacePlanSlot (§6.33); строки в списке ниже —
его frozen values. Преобразование в общий PlanSlot выполняется через .value.

Все paths ниже относительно backend/app. Register function остаётся
application/worldData/planning/composition/planProviders.py.
Восемь PC registrations: local slot указан ниже, contract id —
`surface.pc.<slot>`, cache id — `surface.envelope.pc.<slot>`.
Различные payload contracts не делят один CacheContract id; общий backend
один. Указанные dotted ids — registered opaque declarations, не parsed
domain switches внутри generic engine.
1. climate_base: ClimateBaseInput→ClimateBasePlan, deps=();
   climate/planning/climatePlanProvider.py::ClimateBasePlanProvider.
2. terrain_base: TerrainBaseInput→TerrainPlan, deps=(climate_base);
   terrain/planning/terrainPlanProvider.py::TerrainPlanProvider.
3. water_placement: WaterPlacementInput→WaterPlacementPlan,
   deps=(terrain_base); terrain/planning/waterPlacementPlanProvider.py::
   WaterPlacementPlanProvider.
4. relief: ReliefPlanInput→ReliefPlan,
   deps=(climate_base,terrain_base,water_placement);
   terrain/relief/planning/reliefPlanProvider.py::ReliefPlanProvider.
5. hydrology_routes: HydrologyPlanInput→HydrologyRoutesPlan,
   deps=(relief,water_placement);
   hydrology/planning/hydrologyPlanProvider.py::HydrologyRoutesPlanProvider.
6. river_relief: RiverReliefInput→RiverReliefPlan,
   deps=(relief,hydrology_routes);
   terrain/relief/planning/reliefPlanProvider.py::RiverReliefPlanProvider.
7. hydrology: HydrologyFinalInput→HydrologyPlan,
   deps=(relief,hydrology_routes,river_relief);
   hydrology/planning/hydrologyPlanProvider.py::HydrologyFinalPlanProvider.
8. climate_local: ClimateLocalInput→ClimateLocalPlan,
   deps=(climate_base,hydrology);
   climate/planning/climatePlanProvider.py::ClimateLocalPlanProvider.
Provider paths имеют application/worldData/generators/ prefix.
Specs/roles computations не вызывают соседний provider: порядок задаёт
SurfacePlanningAssembler.prepare через общий PlanningService.

SurfacePlanBundle сохраняет все поля §6.25 с теми же concrete T и добавляет
required hydrology_routes:PlanEnvelope[HydrologyRoutesPlan],
river_relief:PlanEnvelope[RiverReliefPlan]. relief всегда pre-river;
hydrology всегда final. GeoSurfacePlanBundle добавляет те же два required
поля с уточнением geo routes output:
`GeoHydrologyRoutesPlan(base:HydrologyRoutesPlan,source_mapping:SourceBodyMapping,
classification_decisions:tuple[tuple[WaterGenerationCategory,
HydrologyGenerationDecision],...])` в hydrologyPlan.py. Его input —
GeoHydrologyPlanInput. Mapping и classification decisions вычисляются в
route-stage по accepted geo placement/fill, не capture и не final rerun.
Geo final input — HydrologyFinalInput, output GeoHydrologyPlan. Geo bundle
hydrology_routes — PlanEnvelope[GeoHydrologyRoutesPlan]; river_relief —
PlanEnvelope[RiverReliefPlan]. Final переносит source_mapping/decisions
из geo routes без повторного policy resolution. Geo routes deps=
(relief,water_placement); geo final deps=(relief,hydrology_routes,river_relief,water_placement).
Geo routes/final/river_relief registrations имеют schema2 и отдельные ids
`surface.geo.<slot>` / `surface.envelope.geo.<slot>`; прежние PC metadata
entries не перерегистрируются под тем же id. Geo river wrapper в том же
reliefPlanProvider.py::GeoRiverReliefPlanProvider получает exact geo handle,
явно передаёт payload.base в общий terrain profile kernel. Аналогично geo
final wrapper в hydrologyPlanProvider.py::GeoHydrologyFinalPlanProvider.
Нет cast/subclass override invariant PlanEnvelope[T]. Geo relief также
имеет schema2 id surface.geo.relief и wrapper GeoReliefPlanProvider в том
же reliefPlanProvider.py: exact GeoWaterPlacementPlan envelope читается
через geo handle, его payload передаётся common terrain kernel как
WaterPlacementPlan value. Неизменённые стадии переиспользуют PC
registrations; water_placement GEO имеет свой schema2 id.
GEO порядок: climate_base→terrain_base→terrain_regions→water_placement→
relief→hydrology_routes→river_relief→hydrology→climate_local→boundary/support→
coating. SurfaceSupportDependencies сохраняет relief:PlanEnvelope[ReliefPlan]
и добавляет river_relief:PlanEnvelope[RiverReliefPlan]; hydrology — только
final GeoHydrologyPlan. ReliefPlan не переобозначается post-river cast.

Capture signature baseline:
`capture(world:World,locations:Sequence[NamedLocation],*,mode:ResolutionMode,
mountain_templates:tuple[MountainTemplateInput,...],resolve_ctx:ResolveContext)
->SurfacePlanningView`. Templates required, пустой tuple означает
действительно пустой loaded member set, не отсутствие loader. Caller
загружает library members и world/locations из coherent authoritative
read/draft view, проецирует UID/context/recipe; capture не делает selection.
capture_geo дополнительно к §6.29-M принимает тот же required
mountain_templates projection; Geo view добавляет river_relief и
hydrology_final. NoExtent вид сохраняется без synthetic terrain grid.
Source revision включает resolved template values/member UIDs и все
новые inputs, исключая только конкретные resolution_mode поля и capture
diagnostics; ClimateBaseInput.mode остаётся включённым. Per-artifact keys
содержат весь собственный I и exact refs списка выше. River depth edit
меняет routes/river_relief/final/local, template edit relief и downstream;
climate_base остаётся HIT при неизменных собственных inputs.

Legacy SurfaceTerrainContext остаётся eight-field working view по §6.26:
pole/local из climate envelopes; coarse_relief_z из terrain_base, не relief;
coarse_hm/coarse_surface_z и hydro/fine fields из final hydrology. New L0
consumers читают bundle.relief.light и mountain_layout, не eight-field
view как единственный носитель новой layout. L2 получает тот же bundle
и parent-light из pack: parent-light SoT/patch precedence неизменны.

#### F. Activation ledger и размещение

PC-1R определяет все relief records B–D в existing planned reliefPlan.py
и inputs/reliefPlanInput.py; PC-1H — все water/route records в hydrologyPlan.py
и FinalInput в existing hydrologyPlanInput.py. PC-7 реализует оба relief
providers в одном planned reliefPlanProvider.py; PC-8 — routes/final
providers в hydrologyPlanProvider.py. PC-8C читает final hydrology.
Уточнение PC-8 DESIGN_ACCEPTED: providers здесь — только integration;
exact domain owner classes/methods/paths задаёт tz_terrain_generation
§PC-D1 и geo-1-pc8-responsibility-refactor-done.md. Прежние counts/запрет
дополнительных owner classes для PC-8 заменены этой class map.
PC-9A регистрирует ровно восемь PC handles, PC-9 переключает callers;
новых implementation steps и standalone mountain provider нет.
PC-0G2 дополнен переносом LightCellRef; PC-0I — tuple recipe.side_kinds.

Production caller ledger PC-9 (пути относительно application/worldData):
- materialize/terrainBatchOrchestrator.py::plan_bootstrap_tiles;
- materialize/worldSurfaceMaterializationOrchestrator.py::
  plan_bootstrap_tiles, materialize_pack_detailed;
- pack/bake/packMaterializationOrchestrator.py::_materialize_l0_pack;
- pack/bake/worldMapBakeOrchestrator.py::bake_tiles, bake_tile;
- pack/bake/packCompletenessClassifier.py::classify;
- pack/read/wildernessRegionReadService.py::outline;
- api/routes/map.py direct require calls (3) — injected capture/planning
  через existing container, не route-local build/cache. Это backend/app/api.
DI transit: core/container/worldData.py и packs.py,
pack/read/packReadServices.py::build_pack_read_services,
pack/read/packLoadingProgressFacade.py. Existing Container lifetime,
один CacheService/MemoryCache/PlanRegistry/PlanningService/assembler/capture
на process; shutdown build control подключается к container lifecycle.

PC-10 атомарно переводит lightGrid/bakeContext.py и contributors
relief.py,climate.py,mountain.py,ravine.py,hydro/{hydro,declaredBasins,
declaredRivers,coarseOpenWater}.py на frozen plans. MountainMaskMaterializer
load/collect получает layout без нового selection/stamp; old public
helper при необходимости делегирует frozen kernel, live World пути в
переключённом path нет. Coarse helper уже provider-only после PC-7/9;
PC-10 не оставляет второго light selection. PC-11 переводит
TerrainBatchOrchestrator.build_tile_surface_state и detailed/entry callers
на bundle refs; зёрна fine detail/parent light storage остаются прежними.
PC-9 shim принимает обязательные keyword-only planning и capture;
hydrology_generator удалён, nodes/edges compatibility-only, None extent
и require ValueError сохраняются. SurfaceTerrainContext type и old
spatial/diagnostic symbols — единственные definitions/re-exports.

Authoritative commit guard — write-owner, не cache. В
PackMaterializationOrchestrator._materialize_l0_pack/WorldMapBakeOrchestrator
и detailed owner WorldSurfaceMaterializationOrchestrator входной source
revision сверяется с authoritative projection под существующим writer/UOW
guard до публикации pack/manifest.
SUPERSEDED (2026-10-24): целевая модель — `.cursor/plans/world-source-versioning.md`
(lazy object revisions + mutation boundary + revision-set capture).
Реализованные `sourcePublication.py`/`sourceRevision.py` —
transitional OCC, удаляются тем треком вместе с rollback-семантикой.
Текст ниже сохранён как исторический контракт transitional слоя.
Re-read + re-capture + check —
collaborator `worldData/planning/guards/sourcePublication.py::require_fresh`
внутри caller'овского `transaction_if_needed`; pure helper в
`worldData/planning/guards/sourceRevision.py`:
`require_current_source(captured:SurfacePlanningView,current:SurfacePlanningView)
->None`; проверяет world_uid и revision, при mismatch поднимает
`SurfacePlanningStale(ValueError)` с required expected/actual:
StateViewRevision. Helper не перечитывает source, не открывает SQL и не
получает свой counter. Current view caller получает под authoritative
publication guard; этот же guard не допускает source edit между check
и публикацией. Existing file writer сам по себе такую транзакционность
не обещает: caller обязан обеспечить guard на capture/check/publication
boundary, а не выполнять незашищённый check-then-write.
Изменившийся source → write rejected,
request требует replan; нет автоматического неограниченного retry и нет
публикации stale как latest. Чтение frozen результата допустимо лишь в
его historical scope. Future snapshot/patch adapter заменяет caller source
view и guard, не API cache/providers; platform WorldSnapshot не создаётся.

Новых flat files в legacy roots нет. Новые leaf paths — §6.29-M, плюс
ни одного нового module для records этого freeze; несколько связанных
classes помещаются в owning planned modules. Counts с init:
surfacePlanning2 (§6.33); spatial/grid5; relief/planning2, inputs2; hydrology/planning2 PC (3 GEO),
inputs2 PC (3 GEO); composition4; application climate/planning3,
terrain/planning3, terrain/relief/planning2, hydrology/planning2;
planning/{identity3,contracts5,diagnostics2,policy3}; encoding2 (§6.32);
cache/{identity2,contracts4,policy2}; validation/{diagnostics3,enums2};
application planning/providers3,service3,encoding2 (§6.32);
cache/contracts2,service2,backends2.
Tests contracts4/cache4/providers5/consumers5/typing5/encoding2 (§6.32) по §6.27.
При implementation пересчитывать counts фактических existing dirs;
лимит класса 300 строк не оправдывает смешение orchestration и codec.

PC-0G1 non-city import ledger (application/worldData prefix):
generators/climate/{climatePoleField,poleResolve}.py,
generators/terrain/{types,passes/bbox}.py,
generators/coordinates/{worldTile,antipode}.py,
generators/hydrology/{types,hydrologyGeneratorService,riverNetworkAssembler,
shore/fineRiverSampling}.py и pack/climate/climateCoarseBake.py.
Old climate/terrain GridBBox import symbols остаются same class re-export;
GridBBox inclusive bounds/diagonal и WorldBounds/topology contracts не
объединяются. PC-0G2 generators/coordinates/{space,types}.py и
masks/footprint.py — re-exports shared definitions, convert/rect algorithms
остаются application. Tests old import paths сохраняют identity checks.

#### G. Проверки и evidence PC-0

Exact future suites/commands §6.27 сохраняются. В существующие planned
test files добавляются cases: MountainLayout complete sides/ranges/
template edit/single selection; light full↔partial fixed extent; route
space mismatch; missing bed by UID; receiver preserved; pre/post refs;
no double carve; final provider не reroute; eight registrations; dependency
closure и stale guard. Positive/negative pyright cases включают coarse
route под fine key, ReliefPlan вместо RiverReliefPlan и final/routes
envelope mismatch. Domain-specific input DTO additions проверяются теми
же configs, не отдельной новой typecheck системой.

Evidence 2026-10-23: runtime Python и local node_modules/.bin/pyright.cmd
доступны (прежнее замечание §6.27 о missing executable историческое).
Typecheck новых modules не объявляется выполненным до их создания.
Текущий baseline проверяется пятью named regression suites §6.27;
результаты: test_water_placement_pass — 5 OK;
test_relief_objects_z — 12 OK; test_hydrology_hy12_rivers — 10 OK;
test_pack_bake_modes — 20 OK; test_detailed_bake_c11 — 12 OK.
Итого 59 existing tests OK. Detailed suite в sandbox зависал в Python
asyncio socketpair до исполнения test body; bounded faulthandler trace
подтвердил environment boundary, повтор той же suite вне sandbox PASS.
Code/test bodies при этом не изменялись. Проверка новых schemas
сейчас документальная producer/consumer/units/dependency сверка, не
runtime приёмка target. SQL/schema/DAG/backend start/commits не входят
в PC-0; города и pack decode caches не мигрируют.

### 6.32 Post-freeze supplement: общий canonical codec и schema manifest (2026-10-23)

Находка при подготовке PC-4, зафиксированная до начала его кода:
§6.31-A замораживает TLV v1 формат и три fingerprint формулы, но не
назначал исполняемый encoder, тип binding schema manifest и шаг-
владельца. `CachePayloadCodec` — только protocol обёртки binding;
`fingerprint_inputs` — Callable без реализации. Эта правка закрывает
размещение и контракт механизма; формат, формулы и enum wire values
§6.31-A не меняются.

**Владение.** Encoder — общий механизм application слоя наравне с
cache/cascade/jsonValidation, не сабдомен planning: он не импортирует
planning-типы и потребляется envelope codec bindings и будущими domain
payload codec'ами. Fingerprint формулы — planning-owned: называют
PlanKey и поля envelope, исполняются RegisteredPlanContract и
PlanningService.

**Файлы и контракт:**
- `dataModel/encoding/schemaManifest.py` — `CanonicalSchemaManifest`,
  `RegisteredTypeEntry`: `type_id` strict positive int, unique в
  manifest; owner type unique; `kind` — закрытый enum RECORD|ENUM.
  Type ids стабильны при переносе Python-модуля (§6.31-A). Manifest —
  декларация/registry без encode/decode логики и без world state.
- `application/encoding/canonicalCodec.py` — единственный generic TLV
  v1 encoder: `encode(value, manifest) -> bytes`,
  `decode(encoded, expected, manifest) -> T`,
  `digest(value, manifest) -> bytes` (ровно 32). Все reject-правила
  §6.31-A исполняются здесь: NaN/inf, bool-как-int, negative zero,
  leading zeroes, unknown type ids, duplicate map keys, unsorted
  unordered encodings, trailing bytes. Decode по manifest type ids и
  declared field order; отсутствующая entry — typed error, не fallback.
- `application/planning/service/planFingerprints.py` — единственная
  реализация трёх формул §6.31-A:
  `input_fingerprint(metadata, world_uid, scope, inputs, dependencies,
  manifest) -> InputFingerprint`,
  `output_fingerprint(payload, dependencies, diagnostics, manifest)
  -> OutputFingerprint`,
  `cache_item_key(key: PlanKey, manifest) -> CacheItemKey`.
  `RegisteredPlanContract.fingerprint_inputs` и `PlanningService`
  используют эту реализацию с manifest соответствующего binding;
  новый домен не пишет собственный fingerprint helper или encoder.

**Границы.** Codec — pure serialization; domain schema validation
остаётся `CachePayloadCodec`/CacheService, encoder её не дублирует.
Projection Pydantic model → canonical value выполняется по declared
field order внутри encoder, не ad-hoc dict в callers. Codec и manifest
не импортируют planning/cache/domain modules: направление
application/encoding ← planning, не наоборот; dataModel/encoding не
импортирует application.

Counts с init: dataModel/encoding2; application/encoding2;
application/planning/service3; tests/planning/encoding2. Реализация —
шаг PC-3E (§7), до PC-4. Обновляет ledger §6.31-F и карту §5.4.

### 6.33 SurfacePlanSlot — единый словарь surface dependencies (2026-10-23)

Согласованное уточнение после PC-6W. Инвентаризация до PC-6S не нашла
SurfacePlanSlot или эквивалентного surface enum; PC-6S реализован 2026-10-23.
Existing PlanSlot в
dataModel/planning/identity/planKey.py — общий NewType над str;
PlanDependency/PlanDependencyContract — существующие POJO связи и
declaration metadata. Они сохраняются. PlacementPhase PRE_RELIEF/DEPENDENT
описывает отдельную ось placement; GradePipelineStages — mill/paint flags.

**Владелец и файл.** Новый `dataModel/surfacePlanning/surfacePlanSlot.py`
содержит `SurfacePlanSlot(StrEnum)`: единый словарь именованных слотов
междоменного world surface pipeline. Это surface-owned declaration,
не общий enum всех возможных consumers PlanningService. Папка
dataModel/surfacePlanning новая, 2 direct files с __init__.py; общие
planning/identity3 и contracts5 не расширяются. Импорты enum — только
stdlib; общие planning/cache не зависят от surfacePlanning. Producers —
domain providers и composition/planProviders.py; consumers — dependency
reader calls, declarations, requests, logical dependency diagnostics и
тесты конкретных surface bindings. Новый POJO/registry не создаётся.

**Точные PC members и values:** CLIMATE_BASE="climate_base",
TERRAIN_BASE="terrain_base", WATER_PLACEMENT="water_placement",
RELIEF="relief", HYDROLOGY_ROUTES="hydrology_routes",
RIVER_RELIEF="river_relief", HYDROLOGY="hydrology",
CLIMATE_LOCAL="climate_local". Это восемь baseline bindings §6.31-E.
При GEO-1 расширение того же enum имеет уже предусмотренные §6.29-M
members TERRAIN_REGIONS="terrain_regions",
COASTLINE_BOUNDARIES="coastline_boundaries", SURFACE_SUPPORT="surface_support",
COATING="coating"; их добавляют owning GEO steps вместе с bindings,
PC-6S не регистрирует и не активирует эти стадии.

**Применение и совместимость.** Domain calls используют
`PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value)` вместо строкового literal;
logical `FieldPathError.path` зависимости —
`(SurfacePlanSlot.TERRAIN_BASE.value, ...)`. Actual JSON/POJO field paths
сохраняют имена полей своей schema; произвольные диагностические строки
не переименовываются по совпадению с slot value. Registration/composition
использует тот же member.value при объявлении surface.pc.<slot> и
surface.envelope.pc.<slot>, deps и requests; generic registry не парсит ids.
Closed enum не передаётся в PlanKey/PlanDependency или canonical payload:
граница получает прежнюю str через .value/PlanSlot. Wire values, slot order,
ids, schema/algorithm versions, canonical bytes и fingerprints неизменны;
enum не требует entry в canonical manifest. Bundle/input attribute names
сохраняются. Generic tests/сторонние домены могут объявлять свои PlanSlot,
не добавляя значения в SurfacePlanSlot.

**Delivery.** Отдельный атомарный PC-6S перед PC-7 переводит existing
PC-5/6/6W surface literals и их domain test fixtures на enum. PC-7/8/8C
и PC-9A сразу используют его; очередность исполнения определяется
assembler calls §6.31-E, не enum iteration и не новым scheduler.
PC-6S реализует восемь PC declarations; GEO additions и production bindings
сохраняют свои отдельные owning steps. Runtime evidence — в статусе PC-6S §7.

## 7. Порядок реализации после согласования

Фиксация состава после финальной сверки: добавлены prerequisites PC-0U,
PC-0I и G9-ST, отдельные PC-6W/PC-8C и атомарный G10-A; общий canonical
codec PC-3E добавлен post-freeze supplement §6.32; PC-6S добавлен после
PC-6W по согласованному enum уточнению §6.33. Точный порядок
ниже и §6.29-J обязательны. Для всех G0-PT…G9-S фразы про production
owners/call sites описывают target G10-A diff: до него действующие source
models/exports не переключаются частями. Typed leaf contracts/helpers
тестируются isolated, runtime baseline продолжает идти через PC service.

Каждый шаг — отдельный заход и ревью по code-gates. Все изменения ТЗ ниже
только планируются; в текущем заходе не выполняются. Открытые Q закрыть
до соответствующего шага, не заполнять решениями агента молча.
Очередность сверена по зависимостям 2026-10-22: `WaterCoverageBudget`
объявляется в dataModel в G4 (используется в WaterDesignInput до policy
G4-P); у G0-P явное предусловие по domain defaults; routing coastline
source до G8 — через существующий caller; e2e autoresolve coastline —
в проверках G10.

**Входной gate основной реализации:** сначала подготовительный блок
PC-0…PC-12 ниже. G0/G0-A/G0-S — нормативная/контрактная подготовка,
её относящаяся к PC часть выполняется до PC-1. Это не требование
имплементировать GEO-1 algorithms ради подготовки общего механизма.
Исполняемый порядок: PC-0 (freeze соответствующих G0/A/S contracts) →
PC-0U → PC-0G1 → PC-0G2 → PC-0I → PC-1 → PC-1C/PC-1T/PC-1R/PC-1H →
PC-2 → PC-3 → PC-3E → PC-4…PC-6 → PC-6W → PC-6S → PC-7 → PC-8 → PC-8C → PC-9A → PC-9…PC-12 →
G0-PT/G0-PE/G0-P и остальные GEO-1 code steps по зависимостям.
G0/G0-A/G0-S — проектные шаги без кода: их относящиеся к GEO-1 части могут
завершаться параллельно с PC-1…PC-12; входной gate закрывает только кодовые
шаги, начиная с G0-PT. Продуктовое согласие с этим порядком не является
командой писать код.

### Подготовительный блок PC — общий planning/cache до GEO-1

Блок составной: один PC-step — одно проверяемое изменение/ревью.
ТЗ для PC-1…12: нормативные разделы, подготовленные PC-0, и ссылки
§6.15/§6.20–6.22, tz_terrain_generation §planning/TR-PAR,
tz_climate §Partial recalc/Climate LOD, tz_map_light_bake §compose,
tz_world_pack_storage §Read path/LOD, tz_patch_system §Границы слоёв,
tz_world_snapshot §Архитектура. Если точного раздела ещё нет, PC-0
обязан его добавить до соответствующего code-step.

**PC-0 — contracts, доменная карта и activation ledger (без кода).**
Статус: **DONE (contract freeze 2026-10-23)** — §6.31 и норматив
[Surface planning/cache](../../docs/tz_terrain_generation.md#surface-planning-cache-pc0).
Runtime/typecheck новых contracts выполняется в последующих шагах.
Цель: заморозить exact API общего механизма и первых consumers.
Файлы-артефакты: этот план и планируемые нормативные разделы docs;
пути target modules — §6.21. Контракт: полные поля PlanKey/PlanRef/
PlanRequest/PlanDependency/PlanEnvelope[T], CacheContract/Key/Entry/Lookup[T],
CachePolicy, PlanProvider.build и PlanningService.get_or_build; current
revision source, dependency closure, scope/phase enum и type bindings.
Указать composition root injection, lifetime, budget/eviction defaults,
single-flight protocol, exact climate/terrain/relief/hydrology payload
types и их providers. По §6.30 в этом же шаге замораживаются поимённо:
exact поля `ReliefPlan.mountain_layout: MountainLayout` покрывающие все
named mountain consumers; immutable template inputs (frozen projection
ReliefTemplate) в составе layout; и точная форма envelopes/dependencies
фазовой цепочки pre-river relief → hydro routes/fill → river relief →
final hydro (slots GeoSurfacePlanBundle, PlanDependency slots, refs
SurfaceSupportDependencies/GeoHydrologyPlanInput). Эти схемы — задача
PC-0, не выбор при написании кода. Composition/geometry target paths из A01/A02
обязательны: SurfacePlanningAssembler/SurfacePlanBundle/legacy view,
GridBBox/CoordinateSpace/shared coordinate records. Old import paths
и L0/L2 callers перечислить поимённо с re-export/cutover шагами.
Приёмка: schema
producer/consumer comparison §6.17, no-second-SoT cases §6.22, file counts,
отсутствие city/cache migration и зависимостей от новых GEO-1 algorithms.
Done: нет placeholders в выполняемых PC contracts; нормативные входы
G0/G0-A/G0-S для этого блока закрыты, общий snapshot runtime не требуется.
Обязательная проверка §6.24: полные schema/API, injection/lifetime,
domain enum/key/version поля, runtime instance revalidation, diagnostics
на HIT/MISS, immutable representation/codec и executable check commands.
Имена будущих классов/проверка одних путей не закрывают PC-0.

**PC-0U — neutral UID value contract.**
Статус: **DONE (2026-10-23)**. Единственный type alias EntityUid находится
в dataModel/identity/uid.py; placement/common.py реэкспортирует этот же
объект как PlacementUid. UID/seed generation helpers не изменялись.
Проверки: planning/contracts test_geometry — 5 OK;
test_placement_contract — 23 OK; test_water_placement_adapter — 37 OK.
Итого 65 tests OK; old/new symbol identity, strict validation и wire
round-trip сохранены.
Цель: общий planning не зависит от placement ради идентичности мира.
ТЗ: G0-A/§6.25, tz_json_validation §POJO value contracts,
project_data_storage_tz §DET-1 и правило deterministic-ids.mdc (формулы identity/seed неизменны).
Файлы: dataModel/identity/{uid,__init__}.py,
dataModel/placement/common.py — alias/re-export EntityUid.
Контракт: прежний strict nonempty/trimmed строковый value contract,
один definition; никакой новой генерации UID.
Проверка: planning/contracts test_geometry.py §6.27 (old/new alias identity,
valid/empty/whitespace/wrong-type); old placement imports работают.
Done: new common contracts импортируют neutral EntityUid.

**PC-0G1 — общий GridBBox вне climate.**
Статус: **DONE (2026-10-23)**. Единственный class definition перенесён
в dataModel/spatial/grid/gridBBox.py; climatePoleField и terrain/types
реэкспортируют тот же symbol, terrain lazy climate import удалён.
Все non-city production imports ledger PC-0 переведены на shared path;
legacy test imports сохранены для проверки compatibility.
Проверки: planning/contracts — 9 OK; hydrology_hy1 — 18 OK;
relief_objects_z — 12 OK; bathymetry_basin_z — 10 OK;
terrain_surface_gap — 2 OK; pack_climate_sample — 6 OK;
light_grid_compose — 6 OK; water_placement_pass — 5 OK.
Итого 68 tests OK. Fresh-process imports terrain→climate и climate→terrain
успешны, общий GridBBox не загружает application. Поля, frozen semantics,
diagonal clamp и inclusive coordinate conversion сохранены.
Цель: перенести shared grid-AABB contract без изменения геометрии.
ТЗ: PC-0 нормативная карта A02, tz_map_light_bake §coordinate units,
tz_terrain_generation §bounds/topology и contract-creation inventory.
Файлы: dataModel/spatial/grid/{__init__,gridBBox}.py;
application/worldData/generators/climate/climatePoleField.py (definition
убрано, compatibility re-export), application/worldData/generators/terrain/
types.py (shared import/re-export вместо lazy climate import),
application/worldData/generators/hydrology/types.py и non-city consumers PC-0.
Контракт: GridBBox поля и diagonal semantics прежние, один class identity;
WorldBounds/SurfaceGridRect не объединяются с GridBBox и не меняют
inclusive/half-open semantics. DataModel не импортирует application.
Проверка: old/new import identity, bbox boundary/diagonal baseline,
отсутствие climate↔terrain type import cycle и existing domain regressions.
Done: common type принадлежит spatial; old imports работают; нет нового
domain algorithm и нет правок city consumers.

**PC-0G2 — общий CoordinateSpace и coordinate records.**
Статус: **DONE (2026-10-23)**. CoordinateSpace и шесть NewType aliases,
SurfaceGridCoord/FineGridCoord/SurfaceGridRect/FineGridRect/LightCellRef
имеют единственные definitions в dataModel/spatial/grid/. FineXY объявлен
там как tuple[FineX,FineY]. Old coordinates/{space,types}.py — re-exports,
masks/footprint.py реэкспортирует тот же LightCellRef, сохраняя MaskFootprint.
Algorithms convert/rect/worldTile и city consumers не изменялись.
Проверки: planning/contracts — 15 OK; region_rasterizer — 18 OK;
placement_contract — 23 OK; relief_mountain_stamp — 3 OK;
mountain_pass_builder — 5 OK; water_placement_pass — 5 OK.
Итого 69 tests OK. Pyright новых shared modules — 0 errors/warnings;
AST перенесённых records/enum неизменён, fresh shared→legacy imports
сохраняют identity без dataModel→application dependency.
Цель: убрать общие координатные contracts из application generators.
ТЗ: PC-0 карта A02, tz_map_light_bake §Placement P1 coordinate space,
tz_terrain_generation §coordinate units.
Файлы: dataModel/spatial/grid/{coordinateSpace,coordinateTypes}.py;
application/worldData/generators/coordinates/{space,types}.py (re-exports),
application/worldData/masks/footprint.py (LightCellRef re-export),
planning/cache payload imports. Grid папка — 4 файла с __init__.py.
Контракт: перенос тех же enum members, NewType aliases и records A02;
convert/rect/worldTile algorithms остаются application, topology geometry
остаётся topology. Нет нового формата coords/coarse-fine coerce.
Проверка: old/new symbol identity, enum wire values, half-open rect и
conversion baseline; city imports прежние и продолжают работать.
Done: planning dataModel не требует application CoordinateSpace/type imports;
вторых definitions и поведения в compatibility modules нет.

**PC-0I — immutable source collections с сохранением wire/REF-W.**
Статус: **DONE (2026-10-23)**. Все перечисленные в §6.28 и §6.31-B
source collections, включая MountainSideRecipe.side_kinds, используют tuple.
Defaults пустых коллекций — tuple; nullable/required и annotation policies
сохранены. resolved_sides возвращает tuple; ridge constructors и два
model_copy в reliefSidesStamp не вносят mutable вложений. Проекция
гидрологических waypoint принимает tuple; corridor distance получает свой
рабочий list для existing geometry API. _reference_issues обходит tuple,
а существующий dataModel/registryKey.py::_peel_aliases дополнен variadic
tuple для распознавания RegistryKey members; отдельного validator нет.
Проверки: planning/contracts — 19 OK; domain/water/pack regression suites —
140 OK; locations_index_type_key + detailed_bake_c11 — 27 OK (вне sandbox
из-за temp-file PermissionError и ранее подтверждённого async socketpair).
Итого 186 tests OK, включая все пять PC baseline suites. Pyright девяти
изменённых modules — 0 errors/warnings; на declaredCoastline/declaredLake
сохраняются две baseline assignment ошибки default "water" к MaterialKey.
Девять JSON schemas после раскрытия generated $defs эквивалентны HEAD;
меняются только generated list/tuple definition labels. AST обоих mountain
identity_key неизменён. Прямых mutators source collections в app не найдено.
Цель: inputs не удерживают mutable вложения существующих source POJO.
ТЗ: §6.28/6.29-M; tz_json_validation §POJO/REF-W,
tz_map_light_bake §RegionShape, tz_terrain_hydrology §Declare.
Файлы: ровно owner files коллекций §6.28, existing
application/jsonValidation/resolve.py::_reference_issues,
constructor/model_copy helpers этих source types. Метод identity_key
сохраняет текущую формулу. Это один collection-contract migration с
необходимой consumer adaptation, не изменение geometry algorithms.
Контракт: JSON array ↔ tuple, None/empty/required семантика unchanged,
REF-W продолжает проверять каждый tuple member. Проверка:
`.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/planning/contracts -p "test_*.py"`;
source wire round-trip, existing malformed child reference rejected,
nested mutation rejected, unchanged identity и all PC baseline fixtures.
Done: перечисленные models можно включать в immutable I без frozen-shell
исключения; list не попадает в tuple field через model_copy bypass.

**PC-1 — общие dataModel contracts planning/cache.**
Статус: **DONE (2026-10-23)**. Созданы frozen generic records, nominal
digest/version/slot identities, tagged scopes и HIT/MISS, pure metadata
registries, dependency declarations, diagnostic dispositions, resource
policies и ResolutionMode по §6.25/6.27/6.31-A. Metadata entries имеют
имена PlanContractMetadata и CacheContractMetadata в соответствующих
existing planned contract modules; CacheAdmission находится в cacheEntry.py,
CacheEvictionPolicy — cachePolicy.py, PlanScopeKind — planKey.py.
Проверяются strict positive versions/limits, 32-byte key/ref digests,
unique registry ids и unique/canonical UTF-8 dependency slots. Generic
CacheContract/Key/Entry/Lookup и PlanRequest/Envelope сохраняют invariant T/I.
FieldPathError/ReferenceIssueContext/Reason имеют единственные definitions
в dataModel/validation с re-exports старого application пути; добавлены
covariant RuntimeIssueContext и validated RevisionHex. Reports/HTTP mapping
остались application; logger/capture/provider/service wiring не активированы.
Проверки: planning/contracts 30 OK; baseline water/relief/hydro/pack и
locations_index_type_key 62 OK; relief_canonical + detailed_bake_c11 18 OK.
Итого 110 tests OK, все пять PC baseline suites включены. Async/temp-file
регрессии запущены вне sandbox; relief_canonical требует PYTHONPATH
backend;backend/tests для existing sibling test helper import.
Pyright valid config — 0 errors/warnings; invalid — ровно 8 ожидаемых
diagnostics (4 reportArgumentType, 1 reportIndexIssue, 3 reportReturnType).
Configs пока включают существующие common dataModel modules и valid.py;
application providers/services и concrete domain cases добавляются при
их создании в следующих PC шагах, не выдаются за проверенные сегодня.
Actual leaf counts с init: planning identity3/contracts5/diagnostics2/
policy2 (третий файл PlanningRuntimeSettings — PC-3); cache identity2/
contracts4/policy2; validation diagnostics3/enums2; tests contracts4/typing5.
Цель: создать typed vocabulary без исполняющей логики.
Файлы: dataModel/planning/{identity,contracts,diagnostics,policy}/;
dataModel/cache/{identity,contracts,policy}/;
dataModel/validation/diagnostics/{fieldPathError,runtimeIssueContext}.py,
validation/enums/resolutionMode.py и application/jsonValidation/types.py re-export;
точные definitions §6.25–6.29. PlanningRuntimeSettings создаётся PC-3.
Контракт: PC-0 frozen fields/unions/generics, immutable payload refs;
нет application/domain implementation imports. Проверка: positive/negative
типизация, key/entry consistency, revision/namespace/schema mismatch,
immutability. Done: consumer types связаны с T без Any/unsafe cast.

**PC-1C — immutable climate planning contract.**
Статус: **DONE (2026-10-23)**. Созданы ClimateBaseInput/ManualPoleInput,
ClimateLocalInput/ClimateFeaturePolicy, ClimateBasePlan/ClimateLocalPlan,
ResolvedClimateProfile и ClimatePlan union в planned climate/planning paths.
ClimateKey имеет единственное определение в climatePoints.py и использует
RegistryKey[WorldClimateZoneRegistry]. Point/sample/AnchorSource и
ProminenceScale/ProminenceThresholds перенесены с old-path re-exports;
point fields получают GridX/GridY/EntityUid/PoleKind/ClimateKey, weight —
finite positive float. Legacy constructor boundary принимает существующие
строковые enum keys и валидирует их в тот же enum. Алгоритмы не перенесены.
ClimateZoneProfileData и ClimatePoleBlendDefaults переиспользуются целиком.
Profiles unique, покрывают default/pole или default/manual/preset keys;
manual order сохраняется. Feature policy — единственный SoT прежних
METRIC/50/25/10/32/2 defaults, legacy constants читают его class defaults.
Оба TerrainKey required; local input принимает только manual/admin source.
Проверки: contracts 36 OK; climate sample/parallel/apply + пять PC baseline
suites 75 OK (async вне sandbox из-за known socketpair limitation).
Итого 111 tests OK. Pyright valid — 0 errors/warnings; invalid — ровно
9 ожидаемых diagnostics. Проверены old/new identity, nested immutability,
no application/db imports, пропавшие/повторные profiles и изменение полного
input projection при profile edit. Actual canonical digest/ключ проверяется
после реализации codec/service; JSON projection не заменяет fingerprint.
AST всех функций четырёх затронутых legacy leaf modules совпадает с HEAD.
Planning leaf3/inputs3; новых файлов в existing climate roots нет.
Цель: отделить climate data от live sample(world) объекта.
ТЗ: PC-0/A03, tz_climate §field cache/Climate LOD.
Файлы: dataModel/climate/planning/inputs/{climateBaseInput,climateLocalInput}.py; climatePoints.py;  dataModel/climate/planning/climatePlan.py и __init__.py;
existing pure climate leaf definitions по frozen inventory PC-0 с
re-export при переносе, без дублирующих point/zone contracts.
Контракт: ClimatePlan фиксирует нужные poles/anchors/scalars/profile
inputs или их immutable recipe/refs, без ORM/service/callback захвата.
Проверка: отсутствие application imports/live World, nested immutability,
покрытие всех dependencies, revision меняется при значимом profile edit.
Done: PC-5 получает полный typed input для pure sampler; existing runtime
sampling поведение переключается в PC-5, не переписывается в этом шаге.

**PC-1T — immutable terrain planning contract.**
Статус: **DONE (2026-10-23)**. Созданы SurfaceGridSettings,
TerrainBaseInput/TerrainPlan и WaterAnchorInput/WaterPlacementInput/
WaterPlacementPlan по замороженным schemas. Terrain surface unique,
row-major и полностью покрывает inclusive bbox; mutable working copy
не меняет plan. Resolved z bounds находятся в input и проверяются при
build/admission вместе с output (output schema новых z-limit полей не
получает). Water records/specs unique и соединяются по source_uid,
footprint/level/kind/liquid совпадают, space baseline WORLD_SURFACE_GRID.
Empty records/specs валидны. Input хранит frozen source tuples, policies,
topology, scale, z bounds и liquid vocabulary; declared levels/keys
проверяются без live World. BasinSpec перенесён по согласованному ниже
уточнению; прежние семь полей и __post_init__ сохраняются, source_uid
использует EntityUid. Recursive cache admission остаётся PC-2/PC-6W.
Проверки: planning/contracts 42 OK; basin_spec_factory/bathymetry_basin_z/
bathymetry_stub + пять PC baseline suites 78 OK. Итого 120 tests OK.
Async regression вне sandbox из-за known socketpair limitation.
Pyright valid — 0 errors/warnings; invalid — ровно 10 ожидаемых diagnostics
(6 reportArgumentType, 1 reportIndexIssue, 3 reportReturnType).
Old/new BasinSpec identity и old invariants проверены; imports новых
dataModel modules не загружают application/db. Leaf counts с init:
spatial/grid5, terrain/planning3/inputs3, relief/bathymetry2.
Уточнение мастера (2026-10-23): перенос единственного BasinSpec из
application/.../reliefObjects/bathymetry/basinSpec.py в
dataModel/terrain/relief/bathymetry/basinSpec.py с old-path re-export
выполняется в начале PC-1T. Это снимает зависимость WaterPlacementPlan от
будущего PC-1R без обратного dataModel→application import. PC-1R использует
уже перенесённый тип; остальные relief contracts остаются в PC-1R.
Цель: отделить cached base от рабочей mutable heightmap.
ТЗ: PC-0/A03, tz_terrain_generation §planning/coordinate units.
Файлы: dataModel/terrain/planning/inputs/{terrainBaseInput,waterPlacementInput}.py; spatial/grid/gridSettings.py;  dataModel/terrain/planning/{terrainPlan,waterPlacementPlan}.py и __init__.py.
Контракт: TerrainPlan и WaterPlacementPlan имеют exact fields §6.26;
topology/scale входят в inputs/keys соответствующего artifact,
dependencies — в envelope, не shared SurfaceHeightmap.surface_z dict.
Проверка: изменение working-copy после materialization не меняет cached
base и следующего consumer; reconstruct/base heights воспроизводимы.
Done: PC-6 готовит TerrainPlan, mutable buffers создаются отдельно.

**PC-1R — immutable relief planning contract и domain BasinSpec.**
Статус: **DONE (2026-10-23)**. Созданы exact reliefPlan.py records
§6.31-B/C/D: MountainTemplateInput/MountainLayout, LightMountainCell/
LightRavineCell/LightReliefPlan, ReliefPlan, RiverBedRecord[S]/RiverReliefPlan.
В inputs/reliefPlanInput.py — TerrainMergeEntry, MountainAnchorInput,
ReliefPlanInput и RiverReliefInput. Все frozen; cached contracts не
получают World/ORM/callback. MountainLayout сохраняет full specs и order,
проверяет unique identity_key и полные sides каждого peak, включая ranges.
Templates unique/sorted, context=mountain; None recipe сохраняет Mode D.
Merge keys unique/sorted. Coarse/fine/light карты unique/canonical;
light effects принадлежат base, coarse/light macro extent согласован;
river UIDs unique внутри space, beds принадлежат соответствующей surface.
River depths strict positive, покрывают оба типа channel_depth_for;
numeric defaults не дублируются. Input допускает ещё unstamped source specs.
Полнота относительно captured bbox/grid.light_side и z bounds проверяется
provider/admission с input/dependency context; поля outputs не расширены
synthetic limits. BasinSpec ранее перенесён в PC-1T и повторно не менялся.
Проверки: contracts 49 OK; пять PC baseline suites + relief_mountain_stamp/
mountain_pass_builder 67 OK; итого 116 tests OK. Async suite вне sandbox
из-за known socketpair limitation. Pyright positive 0 errors/warnings;
negative ровно 12 ожидаемых diagnostics (7 reportArgumentType,
1 reportIndexIssue, 4 reportReturnType). Fresh imports обоих public entry
points в обоих порядках не загружают application/db. Leaf counts с init:
relief/planning2, planning/inputs2. Selection/carve algorithms не менялись.
Перенос BasinSpec выполнен в PC-1T по согласованному уточнению выше;
PC-1R повторно тип не переносит и не создаёт.
Цель: закрепить terrain-owned relief/profile data без writer behavior.
ТЗ: PC-0/A03, tz_terrain_relief §контракты, HY-12 bathymetry contract.
Файлы: dataModel/terrain/relief/planning/inputs/reliefPlanInput.py;  dataModel/terrain/relief/planning/reliefPlan.py,
dataModel/terrain/relief/bathymetry/basinSpec.py и __init__.py новых папок;
existing application/.../bathymetry/basinSpec.py — re-export.
Контракт: ReliefPlan — frozen post-relief/pre-river surface по §6.26;
BasinSpec переносится единственным определением с прежними 7 полями и
инвариантами. Floor profile algorithms и basinZ writer остаются application.
Проверка: old/new BasinSpec class identity, constructor/floor-level
regression, immutable nested values, no dataModel→application imports.
Done: PC-7 использует domain data; G9 расширяет этот же spec, не второй.
Cache admission не доверяет одному isinstance/TypeAdapter(existing instance):
по §6.24 existing dataclass принимает kind=None и не перепроверяется
автоматически. Field-level enum/range/invariant проверка payload на общей
typed boundary обязательна; legacy constructor semantics не объявлять
эквивалентными полной проверке cache contract.

**PC-1H — immutable hydrology planning contract.**
Статус: **DONE (2026-10-23)**. Созданы exact declared-paint records,
RiverPathSegment[S]/RiverRoute[S], HydrologyRoutesPlan/HydrologyPlan и
HydrologyAnchorInput/HydrologyPlanInput/HydrologyFinalInput. Generic S
invariant; coarse/fine bindings не смешиваются. Routes сохраняют path/
segment order, terminal receiver, matching river UID/drainage, минимум
один non-receiver cell. Route-plan проверяет unique river UID внутри
space, конечную drainage-chain до accepted body/union, отсутствие cycles
и согласованность receiver kind; fine base покрывает accepted path вместе
с receiver. Диагностическая fine receiver_cell остаётся в RiverDrainageLink.
Final maps unique/canonical; coarse facts принадлежат final surface;
body/union identity и declared geometry сохраняются без live World.
Intent width проверяется через existing HydrologyMaskWire clamp без
копирования numeric bounds; segment width_fine strict positive.
Existing HydrologyScope/HYDROLOGY_BOOTSTRAP_SCOPES перенесены в
dataModel/hydrology/enums/planning/hydrologyScope.py с same-symbol
re-exports старого types.py. Enum LANDFORMS сохранён, но planning input
принимает только bootstrap subset. ResolveContext/working result не кэшируются.
Проверки: contracts 56 OK; пять PC baseline suites + hydrology_pojo_updates/
hydrology_declared_wire 67 OK; итого 123 tests OK. Async suite вне sandbox
из-за known socketpair limitation. Pyright positive 0 errors/warnings;
negative ровно 14 ожидаемых diagnostics (8 reportArgumentType,
1 reportIndexIssue, 5 reportReturnType). Проверены JSON round-trip,
detached working map, nested immutability, body/level identity, rooted
drainage и no application/db imports. Input/dependency bbox/z/space
контекст проверяется provider/admission позже; новые поля лимитов не введены.
Leaf counts с init: hydrology/planning2, planning/inputs2, enums/planning2.
Routing/fill/carve algorithms и legacy resolve_scopes не изменены.
Цель: отделить frozen water facts от HydrologyResult working state.
ТЗ: PC-0/A03, tz_terrain_hydrology §water bodies/levels/fill.
Файлы: dataModel/hydrology/planning/inputs/hydrologyPlanInput.py;  dataModel/hydrology/planning/hydrologyPlan.py и __init__.py.
Контракт: HydrologyPlan сохраняет необходимые bodies/unions/roles/levels/
dependencies, recipes из PC-0 и declared_paint:DeclaredWaterPaint для
L0 declared пути (§6.28/§6.29-M), не содержит Any heightmap, mutable
HydrologyResult, ResolveContext или ссылки на live domain service.
Проверка: working result mutation не меняет cache; body/level identity
сохраняется; serial/rebuild representations эквивалентны по контракту.
Done: PC-8 создаёт frozen payload; current mutable result только local adapter.

**PC-2 — общий cache interface/service.**
**DONE (2026-10-23).** Добавлены application/cache/contracts/cacheBackend.py
(CacheBackend, CachePayloadCodec, frozen CacheBinding) и service/cacheService.py
(CacheService, CacheFailure/Reason). Sync get/put/evict используют explicit
binding/expected key, повторную проверку records/discriminator и codec validation;
service рекурсивно отклоняет mutable/opaque/cyclic values, missing/extra fields
и non-finite числа. Технические ошибки не становятся MISS; oversize возвращает
SKIPPED_OVERSIZE без записи. Schema invariants валидирует concrete binding codec;
его canonical encode/decode и production registration остаются следующим шагам.
ТЗ: docs/tz_terrain_generation.md §Surface planning/cache — норматив PC-0,
§Неизменяемость и строгая admission validation, §Общий sync API и ошибки.
Проверки: cache suite 9 tests; contracts suite 56 tests; pyright valid —
0 errors/warnings, invalid — 17 ожидаемых diagnostics (11 reportArgumentType,
1 reportIndexIssue, 5 reportReturnType). Leaf counts с init:
application/cache/contracts2, service2; tests/cache2. PC-3 RAM backend,
production DI и domain codec implementations в этот шаг не включены.
Цель: один typed storage API независимо от backend/domain.
Файлы: application/cache/contracts/cacheBackend.py,
application/cache/service/cacheService.py.
Контракт: get/put/evict и HIT/MISS/technical-error semantics §6.22;
domain revision не вычисляется cache. Проверка: contract mismatch,
namespace isolation и ошибка backend не превращается в MISS.
Done: backend подменяется через protocol, consumer не знает его реализации.
Проверка включает crafted already-typed invalid instance: поля/инварианты
и nested values реально проверены, не только Python class/schema tag.

**PC-3 — bounded RAM backend.**
**DONE (2026-10-23).** MemoryCache реализует sync CacheBackend: один
thread-safe OrderedDict LRU для всех typed namespaces, exact address
(contract id/schema/item digest), byte budget, replacement/evict/clear.
Private heterogeneous values остаются object; выдача проходит concrete
codec validation в CacheService, без Any/cast и domain imports.
Общий retained_entry_bytes в cache/service/cacheService.py считает owned
instance graph с visited identity, включая entry/key metadata и Pydantic
instance storage; encoded copy RAM не хранит. Admission учитывает максимум
codec estimate и graph cost до backend.put; backend использует тот же graph
cost для общего budget. Oversize через service не вытесняет старые entries.
PlanningRuntimeSettings требует cache/execution policies; AppSettings.planning
и TOML adapters сохраняют отсутствие секции как None, без numeric defaults
и TOML null. WorldDataWiring лениво создаёт один backend/service на container
под RLock и фиксирует immutable policies; отсутствие settings блокирует запуск
planning path (activation остаётся PC-9), обычный startup пока не меняется.
ТЗ: docs/tz_terrain_generation.md §Surface planning/cache — норматив PC-0,
§Single-flight и ресурсы и источник runtime configuration (§6.29-M плана).
Проверки: cache suite 20 tests OK (включая TOML IO вне sandbox из-за Temp ACL),
contracts suite 56 tests OK; pyright valid 0 errors/warnings,
negative — прежние 17 ожидаемых diagnostics. Tests: cache/{test_service,
test_memory_backend,test_admission}.py + init (4 файла); policy3/backends2
с init. WARN core13/container9 выдан до правок; новые файлы туда не добавлены.
Остаток: PC-4 PlanningService/registry/single-flight; production caller
activation и domain codec implementations остаются последующим шагам.
Цель: хранение derived immutable values с явным lifetime/eviction.
Файлы: core/{appSettings,configManager}.py,
dataModel/planning/policy/planningRuntimeSettings.py;  application/cache/backends/memoryCache.py, composition root
по PC-0; typed CachePolicy из PC-1. Контракт: injected instance на process,
typed partitions, limits из POJO, не глобальная таблица генератора.
Проверка: bounded eviction, complete clear, independent keys, immutable
result, несколько logical domains без копий cache algorithm.
Done: backend готов, очистка не меняет authoritative domain state.

**PC-3E — общий canonical codec и schema manifest.**
**DONE (2026-10-23).** Добавлены dataModel/encoding/schemaManifest.py,
application/encoding/canonicalCodec.py и planning/service/planFingerprints.py
по §6.32. Manifest имеет unique positive integer type ids, python_type и
CanonicalTypeKind RECORD/ENUM; generic encoder не импортирует домены.
TLV v1 encode/decode/digest использует declared field order и manifest ids;
строгая проверка fields/map invariants переиспользует POJO, не копирует rules.
Нестандартные bytes (trailing/unknown tags/ids, negative zero/leading zeroes,
unordered/duplicate sets, missing/extra/reordered fields) отклоняются.
Проверки: encoding suite 7 tests OK, дополнительные vectors в providers suite;
pyright valid — 0 errors/warnings; полный negative suite после PC-4 —
21 ожидаемых diagnostics (13 reportArgumentType, 1 reportIndexIssue,
7 reportReturnType). Leaf counts с init — encoding2 в обоих слоях,
planning/service3; tests/planning/encoding2. Этот prerequisite и PC-4
выполнены по явной команде мастера продолжить общий codec и затем PC-4.
Цель: исполняемый encoder для замороженных fingerprint формул до PC-4.
ТЗ: docs/tz_terrain_generation.md §Surface planning/cache — норматив
PC-0 (canonical encoding, Exact fingerprint closure); §6.31-A и
§6.32 плана. Файлы: dataModel/encoding/{schemaManifest,__init__}.py;
application/encoding/{canonicalCodec,__init__}.py;
application/planning/service/planFingerprints.py;
tests/planning/encoding/{test_canonical_codec,__init__}.py.
Контракт: §6.32 — manifest деклараций, TLV v1 encode/decode/digest и
три fingerprint функции одной реализацией; binding передаёт свой
manifest, service/binding не имеют своих копий формул. PlanningService
и provider registry в этот шаг не входят. Проверка: canonical bytes
стабильны для эквивалентных unordered входов и различимы для
order-sensitive последовательностей; все reject-правила §6.31-A
(NaN/inf, bool-как-int, negative zero, noncanonical encodings, unknown
type ids, duplicate map keys, trailing bytes); round-trip
encode→decode по manifest; три формулы — distinct 32-byte digests,
меняются при изменении любого входного поля; pyright valid/negative
configs. Done: PC-4 вычисляет CacheItemKey, InputFingerprint и
OutputFingerprint общим codec без ad-hoc serialization.

**PC-4 — PlanningService и provider registry.**
**DONE (2026-10-23).** RegisteredPlanContract/PlanProvider находятся в
application/planning/providers/planProvider.py; PlanRegistry и immutable
PlanDependencyReader — planRegistry.py; PlanningService, failures/controls,
private flight records — service/planningService.py. Один bounded executor
на service; максимум worker+pending distinct flights; exact-key single-flight,
same failure всем waiters, independent cancel/deadline, failed retry,
cooperative shutdown без публикации cancelled output. Recursive calls из
provider worker запрещены. Проверяются trusted handle identity, metadata,
input fingerprint, exact declaration/selection refs/world/scope и output digest
на HIT/MISS; cache не содержит current/latest pointer. Generic heterogeneous
adapters используют object и actual validation без consumer cast/Any.
WorldDataWiring предоставляет lazy singleton plan_registry/planning_service
и shutdown_planning; domain registration и lifecycle/caller activation — PC-9.
Проверки: providers 27, encoding 7, contracts 56, cache 20 tests OK (110 всего).
Cache IO suite запущен вне sandbox из-за known Temp ACL. Pyright valid —
0 errors/warnings; negative — 21 ожидаемых diagnostics (13 argument,
1 index, 7 return); git diff --check OK. Tests/providers5/service3/providers3
с init; existing container9 без новых файлов, класс WorldDataWiring <300 строк.
ТЗ: docs/tz_terrain_generation.md §Surface planning/cache — норматив PC-0,
§Общий sync API и ошибки, §Single-flight и ресурсы; §6.32/PC-3E этого плана.
Остаток: PC-5 climate provider; real domain bindings/callers не переключены.
Уточнение, согласовано мастером 2026-10-23 («делай далее»): общий
canonical codec и fingerprint helpers размещаются по §6.32/PC-3E.
RegisteredPlanContract получает required manifest:CanonicalSchemaManifest;
CachePayloadCodec.encode/decode остаются concrete envelope serialization API.
Stable positive integer record/enum ids не выводятся из Python module paths.
Типы и schema validation принадлежат POJO/concrete validators. PlanDependencyReader и private
registered provider adapters живут в providers/planRegistry.py; protocols и
RegisteredPlanContract — planProvider.py. Реестр хранит trusted handles/adapters,
не world state. Service validates exact handle, inputs, fingerprint, dependency
set/refs/world/scope и output digest на HIT/MISS; worker получает ограниченный
reader только объявленных dependencies. Private flight records принадлежат
service/planningService.py. Shutdown запрещает новые запросы, будит waiters и
передаёт cooperative build cancellation; cancelled work не публикуется.
Новые leaf counts с init: encoding2, planning/providers3, service3;
tests/planning/providers5 (test_planning_service/test_concurrency/test_diagnostics/
test_domain_providers + init). Domain production wiring остаётся PC-9.
Цель: единое получение/rebuild/publication derived layout.
Файлы: application/planning/service/planningService.py,
application/planning/providers/{planProvider,planRegistry}.py.
Контракт: explicit frozen request/dependencies, current revision извне,
single-flight одного key, typed envelope validation, no latest из cache,
no new DAG scheduler; fingerprints вычисляются общим codec PC-3E,
не локальной реализацией. Проверка: HIT/MISS same output, failed/concurrent
build, устаревший build не публикуется как current, cache deletion/restart
equivalence. Done: registry содержит bindings, не world state.
Shared spatial prerequisites — PC-0G1/PC-0G2. Domain composition bindings
создаются в worldData/planning/composition/planProviders.py (PC-9A),
не добавляются в generic PlanRegistry или terrain generator.

**PC-5 — climate planning provider.**
Коррекция по ревью мастера (2026-10-23): diagnostic codes и field paths
не объявляются строками в application provider. Existing
dataModel/climate/planning/inputs/climateBaseInput.py владеет
ClimateBaseIssueCode (StrEnum с existing wire values), typed FieldRef
declarations для ClimateBaseInput.manual_poles/ManualPoleInput.zone и
diagnostic_issue(code,message)->FieldPathError. Используется existing
FieldRef/bind_field introspection без нового механизма или cascade channels.
Provider собирает PlanDiagnostic из готового issue модели; существующие
wire codes/paths и severity сохраняются. Проверка: existing climate tests,
path assertions и pyright valid; новые serialized поля/версии не вводятся.
**DONE (2026-10-23).** ClimateBasePlanProvider строит ClimateBasePlan только
из ClimateBaseInput; diagnostics (multiple poles/missing zone/manual-empty)
возвращаются как immutable PlanDiagnostic, без live World/logger/cache.
ClimatePlanSampler.sample(plan,gx,gy) использует captured profiles/blend;
single fade, weighted blend и first-wins tie-break сохранены. Existing
climatePoleField.sample — live boundary adapter к тому же pure profile kernel;
alias→resolved profile key сохраняет legacy unknown-key fallback.
poleResolve manual/autoresolve строители делегируют общим frozen helpers;
math.World импорт стал TYPE_CHECKING-only. Legacy logging остаётся снаружи.
Обнаруженный при первом real domain consumer rich enum case исправлен
в общем application/encoding/canonicalCodec.py: enum payload использует
wire_value, если он объявлен (иначе value), decode сверяет exact wire member;
служебный builtin object ClimatePolePreset не становится wire-контрактом.
ТЗ: docs/tz_climate.md §Pole field/field cache/Partial recalc;
docs/tz_terrain_generation.md §Surface planning/cache — норматив PC-0.
Файлы дополнительно: existing climate/{climatePoleField,poleResolve,math}.py,
application/encoding/canonicalCodec.py, tests/planning/providers/test_domain_providers.py,
typing/planning valid/invalid/config. Shared planning/service не изменены.
Проверки: providers37 + contracts56 + encoding7 + pack_climate16 =116 tests OK;
pack async smoke вне sandbox (known socketpair boundary). Pyright valid:
0 errors/warnings; negative:22 expected (14 argument,1 index,7 return).
Проверены explicit layout/sample goldens, rich enum input/envelope round-trip,
custom registry keys, negative floor coords, capture blend, manual diagnostics
HIT/rebuild, profile/seed/bbox/scale edit MISS и unchanged base при стороннем
hydrology/anchor edit. Existing root climate20 не расширен; WARN выдан,
новый climate/planning3 с init. Production registration — PC-9A, caller
cutover — PC-9; climate_local/anchor invalidation — PC-8C, не PC-5.
Цель: первый реальный domain consumer общего механизма.
Файлы: climate/planning/{climatePlanProvider,climatePlanSampler}.py,
ClimatePlan из PC-1C и existing climate caller seam по PC-0.
Контракт: ClimatePlanSampler.sample(plan, gx, gy) использует frozen plan
и его explicit dependencies, не World/registry accessor; climate base field/poles
и явные dependencies; elevation-dependent column resolve отдельная фаза.
Проверка: existing climate baseline, anchor edit invalidation, гидрологический
z edit не rebuild base field без изменения его inputs.
Done: provider выдаёт typed envelope через общий service, без своей RAM map.

**PC-6 — terrain base planning provider.**
Статус: **DONE (2026-10-23)**. TerrainPlanProvider принимает typed
RegisteredPlanContract[ClimateBaseInput,ClimateBasePlan] через constructor;
build получает готовый envelope слота climate_base через dependency reader.
Frozen TerrainBaseInput + ClimatePlanSampler + existing cell_z_noise дают
row-major TerrainPlan с полным inclusive bbox и clamp по z_min/z_max.
Provider не читает World/registry, не вызывает climate provider/service,
не пишет cells/pack; temporary buffer не разделяется с immutable payload.
Shutdown проверяется до/после build и на каждой строке сетки.
ТЗ: docs/tz_terrain_generation.md §Surface planning/cache — норматив PC-0,
§Terrain / water placement; docs/tz_map_light_bake.md §Coarse planning ↔ light compose.
Файлы дополнительно: terrain/planning/__init__.py,
tests/planning/providers/test_domain_providers.py, typing/planning
valid/invalid/config. Новая application terrain/planning — 2 файла с init
(3 после PC-6W); providers tests5, typing5, existing roots не расширены.
Проверки: providers45 + contracts56 + пять named baseline suites59 =
160 tests OK; async regression повторена вне sandbox после known
socketpair boundary. Pyright valid: 0 errors/warnings; negative23 expected
(15 argument,1 index,7 return). Legacy heights равны при planar/wrapped/sphere;
baseline kernel не потребляет topology, потому одинаковая base projection
сохраняет HIT. Seed/bbox/z bounds/grid scales и exact climate dependency edit
меняют key; HIT/evict/rebuild/fresh service с одним worker дают одинаковые
refs/payload/diagnostics. Full/partial delivery сохраняет полный world plan,
request-local buffers не мутируют payload; input/envelope codec round-trip OK.
Production registration остаётся PC-9A, caller cutover — PC-9.
Цель: terrain base из того же immutable request/revision.
Файлы: terrain/planning/terrainPlanProvider.py, TerrainPlan из PC-1T и existing
surfacePass/caller seam по PC-0. Контракт: принимает явный climate base
ref, не строит его независимо, не пишет materialized pack/cells.
Проверка: base heights baseline, seed/bounds/topology/scale edit,
HIT/MISS/full-partial deterministic equivalence.
Done: terrain base planning подключён без нового placement/континентального поля.

**PC-6W — baseline water placement provider на terrain-side.**
Статус: **DONE (2026-10-23)**. WaterPlacementPlanProvider принимает
typed terrain_base handle; build читает exact TerrainPlan envelope,
передаёт его output_fingerprint как snapshot_revision и возвращает
WaterPlacementPlan без preparation/context/ORM или mutable maps в cache.
Shared run_prepared_water_placement в existing waterPlacementPass.py
переиспользует fine→coarse projection, prepare_water_placements,
общий resolve_placements и basin_specs, без нового resolver/carve/fill.
Provider проверяет согласованность terrain extent/z с captured inputs;
disabled/no-sources дают typed empty records/specs, не запускают placement.
Snapshot UID сохраняет phase-формулу. Required snapshot_revision проходит
WaterPlacementContext/Preparation → PlacementBatch/Result; mapper сверяет
world_uid + snapshot_uid + revision и exact preparation. В Pydantic batch
revision — strict 32-byte OutputFingerprint; JSON transport — hex с round-trip.
До PC-9 legacy caller не имеет terrain envelope: compatibility bridge
legacy_surface_revision кодирует actual TerrainPlan projection existing
canonical codec/output_fingerprint с local explicit three-record manifest.
Это не registered plan/cache binding и не current-world revision; после
cutover provider всегда использует exact terrain ref, bridge не применяется.
ResolveContext.collect_only отделяет сбор diagnostics от validate_only:
дети и root adapters наследуют флаг; projection/preparation/resolver
собирают existing facts без warning/info emission в build. Runtime/validation
семантика прежняя. Unresolved source → ERROR без effects; existing cap,
merge, kind mismatch, degenerate ring и lowered priority → explicit FALLBACK.
Structural context failure → PlanBuildFailure, не cached empty plan.
Файлы дополнительно: dataModel/placement/{batch,result}.py,
application/worldData/placement/{resolver,diagnostics,adapters/water,adapters/waterTypes}.py,
hydrology/placement/projectDeclaredHydrology.py, jsonValidation/resolve.py,
existing placement contract/resolver/adapter tests, planning providers/diagnostics,
typing valid/invalid. basinSpecFactory переиспользован без правок.
Counts application terrain/planning3 с init; providers tests5, typing5;
legacy roots не расширены (WARN hydrology7/adapters6/dataModel placement7).
Проверки: providers55 + contracts56 + placement contract/resolver/water
adapter/pass86 + import-validation13/remaining four baseline suites54 =
264 tests OK. Async import/regression повторены вне sandbox после known
socketpair boundary. Pyright valid0; negative24: каждый marked code/location
проверен. Legacy basin/specs равны; lake interior и negative floor projection,
wrapped/sphere seam, diagnostics HIT/evict/rebuild, partial-invalid sources,
immutable derived geometry, exact dependency edit/mismatch и input/envelope
canonical round-trip проверены. Production activation остаётся PC-9A/PC-9;
GEO-1 autoresolve/zero policy не включены.
Цель: отдельно кэшировать существующее pre-1.4 placement решение, не fill.
Вход: PC-6, PC-1R (BasinSpec), WaterPlacementPlan из PC-1T.
ТЗ: §6.26 stage 3, tz_map_light_bake §Placement, existing HY-12 mapping.
Файлы: application/worldData/generators/terrain/planning/waterPlacementPlanProvider.py,
existing hydrology/placement/waterPlacementPass.py и basinSpecFactory.py:
input/output adapters, without alternate resolver. Контракт: exact
terrain_base dependency; topology/records/specs frozen; snapshot identity
привязана к input revision, не одному world_uid/phase. Проверка:
providers suite §6.27 + test_water_placement_pass.py; отсутствие derived
geometry mutation после HIT и сохранение coarse/fine conversion.
Done: same prepared input → same specs/records; новое GEO-1 поведение
ещё не включается, hydrology fill не вызывает placement повторно.

**PC-6S — SurfacePlanSlot и замена surface slot literals.**
Статус: **DONE (2026-10-23)**. Создан SurfacePlanSlot(StrEnum) с восемью
PC members; новый dataModel/surfacePlanning содержит 2 файла с init.
Terrain/water providers используют .value/PlanSlot для require и logical
dependency error path. Domain fixtures climate/terrain/water используют
enum при metadata/cache ids и dependency declarations. Общие PlanSlot,
dependency POJO, generic planning/cache и schema field names не изменены.
Typecheck включает surfacePlanning; valid boundary подтверждает PlanSlot,
negative assignment общего PlanSlot в закрытый SurfacePlanSlot rejected.
Проверки: providers55 + contracts59 =114 tests OK; pyright valid0;
negative25 expected code/location (16 argument,1 index,8 return).
Exact members/values и independent foreign-domain slot проверены; enum
не включён в canonical manifest. Canonical bytes/input/output/cache
fingerprints равны прежним strings; отдельно сохранены до правок и
сверены после actual input/output fingerprints + SHA256 encoded envelopes
ClimateBase/TerrainBase/WaterPlacement fixtures — все 9 значений совпали.
AST audit generic planning/cache не нашёл surface imports; enum импортирует
только stdlib. Folder counts соблюдены; production registration остаётся
PC-9A. Следующий шаг PC-7; GEO-1 stages не активированы.
Цель: один domain enum задаёт surface slot names для providers, bindings
и логических dependency diagnostics, сохраняя generic planning contracts.
Вход: PC-5, PC-6, PC-6W; normative supplement §6.33.
ТЗ: docs/tz_terrain_generation.md §SurfacePlanSlot — словарь surface pipeline;
docs/tz_map_light_bake.md §Surface planning/cache — surface slot vocabulary.
Файлы: dataModel/surfacePlanning/{__init__,surfacePlanSlot}.py;
existing application/worldData/generators/terrain/planning/{terrainPlanProvider,
waterPlacementPlanProvider}.py; existing tests/planning/providers/test_domain_providers.py,
tests/planning/contracts/test_contracts.py и tests/typing/planning/{valid,invalid,
pyrightconfig.valid.json}. Climate provider не читает dependencies, его
registration literals сейчас есть только в domain test fixture и мигрируют там.
Контракт: SurfacePlanSlot(StrEnum) с восемью exact PC members §6.33;
PlanSlot/PlanDependency/PlanDependencyContract и их поля не меняются.
Enum lives в dataModel surfacePlanning; application преобразует member.value
в PlanSlot и dependency error path. Новая папка2, providers3/tests5/contracts4/
typing5 сохраняют лимиты; flat files в existing roots не добавляются.
Проверка: providers/contracts suites и pyright valid/invalid командами §6.27;
добавить проверки exact enum members/values, соответствия прежним строкам,
равенства canonical inputs/keys/output fingerprints до/после замены и
отсутствия импортов SurfacePlanSlot в generic planning/cache. Проверить
все existing surface usages регистраций/require/deps/logical paths; generic
test slots и schema field paths не подпадают под literal migration.
Done: existing PC-5/6/6W bindings используют один vocabulary; enum/string
boundary сохраняет runtime и canonical representation. PC-7/8/8C/9A
обязаны использовать enum; GEO additions только в owning GEO steps.

**PC-7 — relief planning provider.**
Статус: **DONE (2026-10-23)**. ReliefPlanProvider принимает три typed
handles climate_base/terrain_base/water_placement; require через
SurfacePlanSlot. Проверяет upstream refs между envelopes, общий extent
и world z bounds; structural mismatch даёт PlanBuildFailure.
Один frozen collector/stamp формирует MountainLayout. Missing required
template → immutable ERROR diagnostic, объект исключён без effects;
independent declared entries сохраняются. None recipe реального template
сохраняет seeded Mode D; object policy имеет прежний приоритет над world.
Coarse height pipeline mountain → ravine → basin использует existing
Form/SideFill/elevationResolve/depressionDetect/basinZ; поднятые mountain
cells зарезервированы от basin carve. Light base вычисляется из terrain_base
и seed по existing ReliefContributor noise/scale; mountain absolute z/facing
проецируются из того же stamped layout без нового selection. Ravines
вычисляются на полном light base+mountain field; новые wrap-соседи не
добавляются. Terrain merge/color не меняет height effects или выбор объектов.
RiverReliefPlanProvider реализован в том же модуле, по §6.31-F: deps=
relief/hydrology_routes, routes обязаны ссылаться на exact relief ref.
Профили coarse/fine строятся от immutable pre-river copies; общий
river_bed_spec перенесён в terrain/reliefObjects/riverBed/riverBedZ.py,
old hydrology/rivers/riverBedProfile.py — same-symbol re-export.
Принятый receiver исключён из профиля своей реки, profile не reroute'ит.
Overlapping absolute targets объединяет existing writer через min один
раз; bed records соединены с routes по UID в каждом space и содержат
actual итоговые z. Полный coarse output и весь sparse fine sample set
сохраняются, включая unchanged cells. No-river case не запускает первый
relief заново; missing path/receiver heights дают PlanBuildFailure.
No World/registry lookup/SQL/pack write/eager L2/mill в providers;
mutable buffers принадлежат build, payload immutable. Shutdown checks —
между фазами/objects и при перечислении full light base.
Legacy wrappers делегируют прежним kernels. Нельзя сортировать старый
set-input collector до PC-9: дополнительная сверка с HEAD выявила смену
selection world_test_004 при такой сортировке, затем legacy iteration
сохранён и повторная сверка четырёх entries полностью совпала с HEAD.
Row-major — явный frozen input из TerrainPlan, общий kernel сохраняет
переданный order. Окончательный unified selection/height-color baseline
delta принимается PC-10/12 по §6.31-B/C, legacy callers пока не переключены.
Проверки: providers72 + contracts59 + пять baseline suites59 + existing
mountain stamp3/pass builder5/fine river12 =210 tests OK. Async regression
вне sandbox по known socketpair boundary. Pyright valid0; negative27 exact
code/location (18 argument,1 index,8 return). Проверены coarse legacy equality с declared
sides, light base vs existing contributor, reservation/basin, full-grid
ravines/no-wrap, full/partial delivery, immutable base, one selection,
HIT/clear/rebuild/fresh single-worker equality, seed/policy/merge/ref edits,
range spine/sides/peaks/saddles/spacing и canonical input/envelope round-trip;
river overlap/no-double-subtract, receiver exclusion, z_min clamp, coarse/
fine space, unchanged sparse samples, missing heights, no-river/no-replan,
profile symbol identity и RiverReliefPlan envelope round-trip.
Новая application relief/planning2 с init; helper owner files без новых
flat files, WARN mountains24→24, relief/pick8→8 и hydrology/rivers15→15
выдан; riverBed3 не расширен. Production
registration/caller activation остаётся PC-9A/PC-9; следующий шаг PC-8.
Вход дополнительно: PC-6S; dependency slot names через SurfacePlanSlot §6.33.
Исполняемая детализация существующих relief seams (2026-10-23):
collect.py выделяет pure prepared collector; existing World caller делегирует
ему с прежним set iteration до PC-9. Frozen provider перечисляет ridge input
cells row-major по полному TerrainPlan extent. Ordering — явный input kernel,
не второй selection algorithm. Сверка с HEAD world_test_004 выявила, что
общая сортировка изменила бы legacy selection: она остаётся только на
frozen boundary и не активируется в legacy path этим шагом. reliefSidesStamp.py
выделяет prepared stamp с typed template projections/world mountain policy;
templatePick.py переиспользует существующий pick для resolved context policy
и MountainTemplateInput без создания World/полного ReliefTemplate.
Один provider в relief/planning/reliefPlanProvider.py собирает coarse и light
outputs из stamped layout, переиспользует formPipeline, depressionDetect,
elevationResolve и basinZ; исключает повторный selection для light.
Файлы дополнительно: existing terrain/mountains/{collect,reliefSidesStamp}.py,
terrain/relief/pick/templatePick.py; tests/planning/providers/test_domain_providers.py,
terrain/reliefObjects/riverBed/riverBedZ.py и old
hydrology/rivers/riverBedProfile.py (profile relocation + re-export);
typing/planning/{valid,invalid,pyrightconfig.valid.json}. Новая application
relief/planning2 с init; existing mountains24 и relief/pick8 остаются без
новых flat files (WARN выдан). Классы-владельцы и frozen contracts прежние;
shared helper functions размещаются в существующих owner modules.
Цель: post-relief/pre-river поверхность через общий API.
Файлы: terrain/relief/planning/reliefPlanProvider.py, ReliefPlan/BasinSpec из PC-1R
и current relief preparation seam PC-0. Контракт: dependencies §6.26,
existing mountain → ravine → basin; без eager L2/mill; второй relief
вызов для русел и фазовый состав bindings — по §6.30/PC-0. Проверка:
mountain reservations,
immutable input base, baseline relief и отсутствие phase dependency cycle.
Done: relief layout обновляется при input edit, materialization по запросу.

**PC-8 — hydrology planning provider.**
Статус реализации: **DONE (2026-10-23)** — R1–R5 исполнены,
реализация принята мастером.
Статус целевой архитектуры: **DESIGN_ACCEPTED (2026-10-23)**.
R1 **DONE (2026-10-23)**: intermediate stage POJO и strict/space/claims/sample
validators; contracts69 OK, pyright valid0/negative34 exact. R2 **DONE (2026-10-23)**: WaterBodyPlanner,
DeclaredWaterPaintProjector и explicit producer water diagnostics; providers96/
regression59 OK, pyright valid0/negative37 exact. R3 **DONE (2026-10-23)**:
coarse/fine owners, pure route-only boundary и procedural producer;
providers110/regression59 OK, pyright valid0/negative40 exact. R4 **DONE (2026-10-23)**:
assembly owners и constructor DI, оба providers атомарно переключены на
require/ref-check/delegate; old domain helpers удалены. Providers116/
contracts69/regression59 OK, pyright valid0/negative42 exact; extended
hydrology241/242 с прежним list/tuple failure.
R5: **техническая проверка пройдена (2026-10-23)**, providers118/contracts69/
cache20/regression59 OK, pyright valid0/negative42 exact. ERROR/FALLBACK
diagnostics, geometry/UID/ref сохраняются на HIT/clear/codec/fresh composition
и при max_workers=1/2; размеры всех восьми classes20–70, карта методов
подтверждена. Extended hydrology241/242 — прежний list/tuple failure.
Реализация принята мастером; PC-8 закрыт, следующий шаг — PC-8C.
Согласованная детализация: [geo-1-pc8-responsibility-refactor-done.md](geo-1-pc8-responsibility-refactor-done.md),
§1–6 — exact owning classes/methods/contracts, §7 — R1–R5 внутри PC-8.
Норматив: [tz_terrain_generation.md §PC-D1](../../docs/tz_terrain_generation.md#pc8-responsibility-boundaries).
Эта карта заменяет прежнее размещение domain work в provider module для
PC-8; PC-8C разблокировано принятием исправленного PC-8.

Цель: разделить planning lifecycle integration и domain work, сохранив
existing water planning/facts, identity/geometry и общий cache lifecycle.
ТЗ: tz_terrain_generation §PC-D/PC-D1/PC-E/PC-F, tz_map_light_bake §PC-0.
Файлы: existing hydrology/planning/hydrologyPlanProvider.py;
новые application hydrology/planning/assembly/{hydrologyRoutesAssembler,
hydrologyFactsAssembler}.py, hydrology/water/planning/waterBodyPlanner.py,
hydrology/rivers/planning/{coarseRiverPlanner,fineRiverPlanner}.py,
hydrology/load/paint/declaredWaterPaintProjector.py; init files по карте.
Новые intermediate POJO: dataModel/hydrology/planning/stages/
{openWaterPlan,riverRoutePlans}.py; existing water/river producer emission
и pure prepared APIs изменяются в owner modules по §2.9/3 детализации.
Tests/typing: existing planned suites/configs §6.27, новые flat roots нет.

Контракт:
- HydrologyRoutesPlanProvider.build -> require envelopes/check refs ->
  HydrologyRoutesAssembler.assemble -> PlanBuildResult[HydrologyRoutesPlan].
- Routes assembler вызывает WaterBodyPlanner.plan, CoarseRiverPlanner.plan,
  FineRiverPlanner.plan, DeclaredWaterPaintProjector.project; знает только
  их public DTO, не PreparedRiver/AssembledWater/FineRiverSampling buffers.
- HydrologyFinalPlanProvider.build -> require three envelopes/check refs ->
  HydrologyFactsAssembler.assemble -> PlanBuildResult[HydrologyPlan].
- Facts assembler един: coverage, actual bed UID join, receiver validation,
  вызов river_bed_roles и final facts — одна ответственность. Он не
  вычисляет новые hydrology rules/roles/receivers/levels/routes локально.
- Disposition выбирает producer доменного решения одновременно с
  reject/fallback/notice. Наружу передаётся готовый PlanDiagnostic;
  классификация по code и отдельный HydrologyDiagnosticsAdapter запрещены.
- Координаты, immutable inputs/results, phase refs и legacy kernels
  сохраняются; materializers получают принятые планы по запросу, не
  повторяют selection. RiverReliefPlanProvider — external terrain boundary.
- Существующие generic PlanBuildResult и PlanDiagnostic переиспользуются;
  нового дублирующего Result/Diagnostic DTO нет. Provider constructors
  получают assembly collaborators; production factory wiring PC-9A.

Проверка: exact commands §6.27 плюс structural boundary tests, explicit
producer severity/HIT-MISS preservation, kernel-role delegation без
пересчёта, class bodies <=250 строк. Existing baseline/cache/fine/coarse/
receiver/identity/determinism проверки сохраняются.
Done: исполнены R1–R5, реализация соответствует class/method/contract map,
обязательные проверки пройдены и архитектурная реализация принята.
Новые GEO-1 strategies/autoresolve policy/HY-RIV-1, SQL/DAG/commits вне scope.

Историческое evidence незавершённой версии (не проверка принятой target):
Проверки: providers84, contracts59, пять обязательных regression suites59
OK; regression async вне sandbox по known Windows socketpair boundary.
Hydrology extended: 241/242 OK; existing test_hydrology_hy12_contract
ожидает list вместо immutable tuple footprint.path. Тот же failure
воспроизведён с loader из HEAD в отдельном процессе; тест/POJO не менялись.
Pyright valid0; negative31 exact code/location (22 argument,1 index,8 return).
Проверены declared coarse/fine equality с legacy, baseline procedural
seed/UID/path equality, endpoints/via anchors, rooted tributary/receiver,
physical unions, partial failures/runtime-vs-preview, disabled/scopes,
cache HIT/clear/fresh single-worker, canonical envelopes round-trip,
upstream edits, missing bed/receiver mapping, no final reroute/refill/carve.

**PC-8C — local climate provider после hydrology.**

**DONE (2026-10-23) — реализация принята мастером.**
ClimateLocalPlanProvider добавлен в existing climate/planning/climatePlanProvider.py
(20 строк тела): require CLIMATE_BASE/HYDROLOGY через SurfacePlanSlot,
проверка точного множества request refs против выбранных envelopes,
делегирование build_local_plan_from_coarse, shutdown до/после сборки.
Base provider/input/payload и повторное pole planning не менялись.
Production registration/composition не активированы; PC-9A не начат.

Pure seam реализован в existing owner modules, без новых классов/DTO:
- climate/localFieldFromCoarse.py::build_local_plan_from_coarse (4 строки)
  передаёт только final HydrologyPlan.coarse_surface_z;
- assemblers/climateAssembler/passes/anchorCollectPass.py::collect_resolved_local_anchors
  (26 строк): existing collect-порядок, feature policy, frozen diagnostics;
- climate/anchorDetect.py::terrain_feature_candidates/select_terrain_features
  (41/13 строк): общий с legacy extrema/cap kernel, stable prominence ties;
- climate/anchorAssign.py::resolved_auto_anchors (5 строк): ClimatePlanSampler,
  без ClimateGeneratorService/World/registry reads;
- climate/anchorCollect.py::merge_local_anchors (6 строк): общий с legacy
  manual-first merge и inclusive exclusion radius. Legacy projection получила
  explicit RegistryKey/coordinate guards для проверки типов, без новых defaults.

Local seam сохраняет synthetic terrain policy: coarse hydro roles не
подменяют terrain-key синтетических клеток; water feature branch зависит
от frozen synthetic_surface_terrain/water_feature_terrain. METRIC/GRID,
manual/admin order, active-pole admin suppression, cap и tie order сохранены.
Cap/admin-skipped NOTICE выпускаются producer'ом как PlanDiagnostic;
upstream diagnostics не копируются. Legacy logging остаётся в legacy path.
Импорт local owner выполняется при local build: poleResolve импортирует
base helpers этого же provider-модуля во время ранней инициализации.
**Долг PC-8C → PC-9:** lazy import `build_local_plan_from_coarse` в
`ClimateLocalPlanProvider.build` — workaround цикла
poleResolve→climatePlanProvider→localFieldFromCoarse. Устранить при
cutover caller seams PC-9: вынести `autoresolve_base_poles`/`manual_base_pole`
в climate owner kernel (poleResolve перестанет импортировать provider
module) и вернуть top-level import; либо удалить legacy chain целиком.
Не считается закрытым до устранения — записано в контракт PC-9.

Проверки §6.27: providers126 (8 новых local cases), contracts69,
пять обязательных regression suites59 OK. Regression перезапущен вне
sandbox после зависания на известной Windows asyncio/socketpair boundary.
Pyright valid0, включая все шесть изменённых executable modules;
negative45 exact code/location: 32 reportArgumentType, 1 reportIndexIssue,
12 reportReturnType. Тесты покрывают legacy coarse anchors/pole zones,
manual exclusion/admin fallback, custom feature thresholds/water/GRID/cap,
final z edit → new local key/rebuild при unchanged climate_base HIT,
exact refs/missing deps/shutdown, отсутствие live reads, acyclic восемь
bindings, HIT без build, clear/rebuild, codec и fresh single-worker service.
Folder direct counts: climate20→20, planning3→3, assembler passes6→6,
tests providers5→5, typing5→5, plans155→155; WARN выданы, новых файлов нет.
SQL/DAG/backend/commits/GEO algorithms не затронуты. PC-8C принят;
следующий шаг — PC-9A по отдельной команде.

Цель: сохранить существующую зависимость anchors от final surface.
Вход: PC-5 base climate provider и PC-8 hydrology provider.
ТЗ: §6.26 stage 6, tz_climate §local field.
Файлы: climate/planning/climatePlanProvider.py::ClimateLocalPlanProvider,
localFieldFromCoarse.py/anchorCollectPass.py — pure input adapter seam.
Контракт: build выдаёт ClimateLocalPlan, slots climate_base/hydrology;
не изменяет ClimateBasePlan и не вызывает повторный base pole planning.
Проверка: providers suite §6.27, anchor baseline и отсутствие цикла
climate_base → hydrology → climate_base. Done: final z edit инвалидирует
local anchors; неизменный climate base сохраняет свой cache key.

**PC-9A — междоменный assembler и typed bundle вне generators.**

**Review correction PC-9A (2026-10-23), по замечаниям мастера.**
Цель: устранить второй SoT bindings и domain policy на capture boundary.
ТЗ: tz_terrain_generation §Surface planning/cache, §6.31-E/§6.28 этого плана.
Точные владельцы и файлы:
- dataModel/surfacePlanning/surfacePlanBindings.py::SurfacePlanBinding — frozen
  surface declaration (slot/upstreams/metadata/cache contract); единственная
  таблица PC bindings. _binding и SurfacePlanBundle читают её; explicit calls
  assembler не превращаются в scheduler.
- dataModel/planning/identity/sourceFieldRole.py::SourceFieldRole — neutral
  declaration EXECUTION_POLICY для input field metadata; water/routes inputs
  отмечают resolution_mode, capture не знает имён/типов request policy.
- application/worldData/generators/climate/registry.py::resolve_base_profiles —
  climate-owned key selection/profile resolve/fallback/disposition и request report;
  capture получает готовые profiles/typed diagnostics, не классифицирует ctx.errors.
- application/jsonValidation/worldSlices.py::resolve_world_slice — публичная
  typed normalization boundary с ctx; private merge остаётся внутри владельца.
- application/cache/service/cacheService.py::validate_immutable — публичный
  admission API поверх existing validator; underscore не пересекает boundary.
- application/worldData/planning/encoding/{surfaceManifest,surfaceEnvelopeCodec}.py
  и __init__.py — перенос manifest (IDs сохраняются) и codec без новой логики.
- application/worldData/planning/guards/sourceRevision.py и __init__.py —
  SurfacePlanningStale/require_current_source; capture больше не владеет guard.
- composition/surfacePlanningCapture.py — orchestration + per-slot projection
  methods, delegation domain policy; assembler — один union validation до narrowing,
  docstring явно говорит о делегировании cache/scheduling PlanningService.
Контракт: signatures/plan keys/output fingerprints/legacy import identity сохранены;
capture diagnostics сохраняют producer dispositions, source revision bytes прежние.
Проверка: consumers/contracts/providers/cache/encoding, пять regression suites,
pyright valid и exact negative, stable manifest IDs и byte-level key/revision tests.
Done: замечания high/medium закрыты, explicit PC-9 cleanup для legacy view остаётся
ниже. Counts: surfacePlanning2→3, identity3→4, composition4→4, encoding3/guards2
(новые dirs), contracts3→3, consumers4→4; climate20/jsonValidation14 без новых файлов.
PC-9 cleanup: отделить transitional SurfaceTerrainContext от frozen contracts,
убрать generator imports из contracts/surfacePlanningView, сохранив old type identity;
адаптер to_legacy_context остаётся module-level, commit description должен это отражать.

Review correction IMPLEMENTED / VERIFIED (2026-10-23): consumers35/providers126/
contracts69/cache20/encoding7/regression59 — OK, всего316; cache/regressions вне
sandbox по подтверждённым Windows temp/socketpair ограничениям. Pyright valid0,
включая public worldSlices и climate registry; negative48 exact на 47 EXPECT
code/location pairs. Дополнительные проверки: правка declaration metadata/graph
синхронно меняет wiring и bundle admission; producer ERROR/NOTICE/FALLBACK
сохраняются; execution-policy marker работает для нового имени/типа input;
invalid copied view отвергается до build; исходные revision и все16 input/output
fingerprints совпадают. AST manifest declaration неизменён (165 IDs).
Крупнейший новый executable class — SurfacePlanningCapture120 строк;
planProviders461→96, capture211→196. Folder counts соответствуют карте выше.
Для включения worldSlices в typecheck добавлен явный missing-mapper guard
в existing world_wire_from_row: отсутствие mapper — ошибка declaration.

**ACCEPTED (2026-10-24) — приёмка PC-9A после review correction подтверждена мастером.**
Boundary готова к PC-9; production callers остаются на legacy orchestration,
второй активный путь не включён.

Исходное evidence PC-9A до review correction (текущая карта путей — выше):
- composition/surfacePlanningAssembler.py::SurfacePlanningAssembler — восемь
  explicit PlanningService calls в frozen phase order. to_legacy_context
  создаёт request-local maps: coarse_relief_z из terrain_base, final maps из hydro.
- composition/planProviders.py::register_world_plan_providers — восемь bindings;
  WorldPlanProviders — frozen exact I/T handle holder; SurfaceEnvelopeCodec —
  typed admission/round-trip через общий canonical codec. SURFACE_MANIFEST —
  явные 165 stable type IDs, без runtime discovery; IDs/versions по §6.31-E.
- composition/surfacePlanningCapture.py::SurfacePlanningCapture — source adapter:
  WorldSlice normalization с request ResolveContext, frozen inputs, resolved
  profiles/materials/terrain merge ranks/templates; без generation/SQL/pack/cache.
  Source revision исключает только water/routes resolution_mode и diagnostics,
  сохраняет ClimateBaseInput.mode и порядок manual poles. require_current_source
  сверяет world/revision; SurfacePlanningStale несёт expected/actual revisions.
  Authoritative read/publication guard принадлежит caller.
- contracts/surfacePlanningView.py::ReadySurfacePlanningView/
  NoExtentSurfacePlanningView и SurfacePlanningViewKind — immutable discriminated
  view с проверкой extent/grid/topology/execution policy. SurfaceTerrainContext —
  единственное eight-field определение; старый terrain module реэкспортирует его.
- contracts/surfacePlanBundle.py::SurfacePlanBundle — immutable typed envelopes,
  проверки world/scope/phase/version и exact dependency refs всех фаз.

Размеры тел классов: assembler51, capture101, stale4, codec20, handles9,
bundle36, Ready33, NoExtent7, discriminator3, legacy context13 строк.
Direct counts: planning1, composition4, contracts3, consumers4;
terrain/passes9→9, typing5→5, plans155→155, docs67→67. WARN выданы;
новых flat root files нет.

Проверки §6.27: consumers26/providers126/contracts69/cache20/encoding7/
regression59 — OK, всего 307 tests. Cache20 перезапущен вне sandbox после
PermissionError на TemporaryDirectory; regression59 — после известного
Windows sandbox asyncio/socketpair зависания. Pyright valid0, новый namespace
включён; negative48 diagnostics на 47 EXPECT code/location pairs (строка162
имеет два reportArgumentType), без непредусмотренных кодов/мест. Три новых
negative cases проверяют source↔bundle и final↔routes несовместимость.
Acceptance: phase order, HIT без build, NoExtent без providers, old type identity,
mutable-map isolation, legacy dry/basin baseline, accepted coarse+fine
river→beds→final, codec corruption/round-trip, mode≠source revision, UI→HIT,
river depth/template edits→точный downstream rebuild, stale guard,
worker-count/cache-clear equality, отсутствие live reads/domain imports в engine.
SQL/DAG/backend/commits/GEO не затронуты. Container/caller cutover и lazy-import
долг PC-8C остаются PC-9; следующий шаг — после приёмки мастером.

Цель: создать единственную world surface composition boundary.
ТЗ: PC-0 нормативная карта, §6.21/§6.25–6.28, tz_map_light_bake §compose.
Вход: PC-4, PC-6S и providers PC-5/6/6W/7/8/8C; schemas/signatures заморожены PC-0.
Файлы: application/worldData/planning/composition/{surfacePlanningAssembler,
planProviders,surfacePlanningCapture}.py; application/worldData/planning/contracts/{surfacePlanBundle,
surfacePlanningView}.py и __init__.py каждой новой папки.
Контракт: SurfacePlanningAssembler.prepare выполняет явные phase calls
PlanningService с coherent dependencies, один frozen input view;
ResolveContext остаётся вне assembler/cache на request report boundary;
register_world_plan_providers задаёт bindings через SurfacePlanSlot §6.33
без domain imports в engine.
SurfacePlanBundle — typed immutable refs/envelopes; единственное определение
SurfaceTerrainContext переносится в surfacePlanningView с прежним public API.
Legacy mutable working views получают копии, не cached mutable references.
Проверка: phase/dependency order/no cycles, bundle compatibility,
immutability/no IO из domain providers, generic engine не знает world domains.
Done: composition находится в worldData/planning; новая boundary готова
к переключению, второй активный путь не включается. Это assembler
existing phases, не дополнительный DAG scheduler.

**PC-9 — cutover surface caller, compatibility entry и publication guard.**

Уточнение карты cleanup PC-9 (2026-10-24, согласовано в чате):
- application/worldData/planning/legacy/surfaceTerrainContext.py::SurfaceTerrainContext —
  transitional application working view для ещё не переведённых L0/L2 consumers;
  единственное eight-field определение. Old terrain/contracts imports — re-export;
  to_legacy_context остаётся в composition/surfacePlanningAssembler.py.
  Новая legacy/ содержит __init__.py + surfaceTerrainContext.py (0→2).
- application/worldData/generators/climate/planning/basePoleLayout.py —
  climate-owned pure autoresolve_base_poles/manual_base_pole kernel;
  consumers: poleResolve и climatePlanProvider; planning/ 3→4 файлов.
  provider импортирует localFieldFromCoarse на module level, без lazy import.

Историческое evidence первого cleanup-среза PC-9 (2026-10-24): выполнены
указанные выше переносы. Existing terrain/contracts imports сохраняют identity одного класса;
to_legacy_context остаётся module-level adapter. Проверки: consumers37,
providers126, contracts69, encoding7 — OK (239 tests); pyright valid0;
git diff --check — OK. Новые executable classes не добавлялись.
На этом промежуточном этапе caller/DI cutover и publication guard ещё не были реализованы.
РЕШЕНО (2026-10-24): production adapter PlanWaitControl —
`application/cancellation/requestPlanWait.py::RequestPlanWait`
(frozen dataclass: `token: CancellationToken | None`,
`deadline_monotonic: float | None`). Adapter живёт в cancellation/ как
адаптер к существующей request-side инфраструктуре; planningService
остаётся зависимым только от Protocol, импорта CancellationToken в
planning нет. `raise_if_cancelled` → PlanWaitCancelled при
token.is_cancelled(); `remaining_seconds` → None либо
max(0, deadline - time.monotonic()). Фабрика
`RequestPlanWait.unbounded()` (token=None, deadline=None) — явное
бессрочное ожидание. `wait` у prepare/get_or_build остаётся обязательным;
token/deadline опциональны внутри адаптера. Каждый waiter получает свой
экземпляр на request boundary — отмена одного не отменяет общий build.
Проводка: `wait` создаётся только на внешней границе (route / UOW /
chat-engine entry — chat использует existing ExecutionState.cancel_token)
и передаётся параметром во внутренние sync callers; внутренние callers
сами wait не конструируют. pack/map routes пока создают unbounded().
Deadline: текущий дефолт — None (у callers нет request lifetime);
`PlanningExecutionPolicy.wait_timeout_seconds: float | None = None` —
зарезервированное поле архитектуры: вводится вместе с request
cancellation/timeout для pack API или cap на chat turn; тогда boundary
вычисляет deadline_monotonic = monotonic() + wait_timeout_seconds.
Числовой fallback запрещён; без включённого конфига поведение = unbounded.
Реализация адаптера и caller cutover разрешены по этому контракту.

Пересмотр publication guard (2026-10-24): обсуждение нижней публикации
manifest (FineChunkPersist finish/maybe_checkpoint_manifest до
require_fresh) выявило, что корневая проблема — отсутствие
версионирования объектов N+1 и единой границы мутации источника.
Модель «require_fresh → abort publish» заменяется общим механизмом:
lazy object revisions + mutation boundary + revision-set capture —
см. `.cursor/plans/world-source-versioning.md`. PC-9 в части
publication ownership реализуется упрощённо (persist не публикует
manifest — финальный save от operation owner со штампом revision set),
без abort-семантики и без флага publish_manifest.

Цель: переключить callers на PC-9A и убрать старую междоменную orchestration
из terrain; authoritative commit guard под existing UOW на границах
публикации pack/manifest. Файлы: terrain/passes/surfaceTerrainContext.py
(type re-export, prepare/require delegation),
worldData/planning/composition/planProviders.py, named caller/import seams
PC-0, worldData/planning/guards/sourcePublication.py (новый, guards 2→3),
packMaterializationOrchestrator.py, worldSurfaceMaterializationOrchestrator.py,
packDetailedBakeOrchestrator.py. Bundle/view types не дублируются.
Контракт: prepare_surface_terrain_context/require получают explicit injected
planning dependency по §6.27; None/error semantics сохраняются.
Все внутренние callers/test doubles обновляются атомарно; вся сборка — в
SurfacePlanningAssembler.prepare через общий PlanningService. Один ctx,
одна captured state view, dependency fingerprints проверяются по A05.

**Publication ownership (пересмотрено 2026-10-24, заменяет ранее
согласованный «require_fresh → abort» как целевую форму).** Целевая
модель — `.cursor/plans/world-source-versioning.md`: lazy object
revisions + mutation boundary; публикация всегда валидна от своего
revision set, abort-семантики нет. До приземления того трека PC-9
фиксирует только границу владения публикацией:

- **Persist нижнего слоя не публикует manifest вообще** — без флага и
  без режима. `FineChunkPersist.finish()` выполняет только blobs +
  `recalc_manifest_counters()` в памяти; `persist_rect` не вызывает
  `maybe_checkpoint_manifest` (checkpoint-публикация из нижнего слоя
  удаляется; progress-публикация — решение operation owner'а, при
  необходимости он сам вызывает save_manifest между шагами).
- **Operation owner сохраняет manifest на своей границе**: L0 bake —
  `finalize_pack_on_world` внутри существующей `transaction_if_needed`;
  detailed bake — owner (`WorldSurfaceMaterializationOrchestrator`)
  после возврата `PackDetailedBakeOrchestrator.bake`; drain/scene/path
  под bake op — тем же owner'ом bake.
- **Standalone runtime refine** (debug route `map.py`, прочие входы вне
  bake op): его entry point — сам себе owner, вызывает
  `writer.save_manifest()` в конце операции. Refine API параметра
  публикации не получает.
- `guards/sourcePublication.py` и `require_fresh` остаются как
  **transitional OCC** до world-source-versioning: stale source в
  guarded op → `SurfacePlanningStale` → rollback без publish
  (blobs-сироты допустимы). После перехода на revision-set модель guard
  заменяется штампом revision set в manifest; abort-семантика и
  re-read check удаляются этим треком.
- Тот же класс нижней публикации отмечен у settlement write path
  (worldPackWriter settlement save) — вне scope PC-9, долг
  world-source-versioning.

Зависимости без изменений: PackMaterializationOrchestrator +=
INamedLocationRepository (+ guard); WorldSurfaceMaterializationOrchestrator
+= db + guard. Captured view доходит от entry-шва до publication-блока
через injected `capture`, не через legacy ctx. Карта методов:
`FineChunkPersist.__init__/persist_rect/finish`,
`FineChunkRunner.refine_rects`, `_run_refine_phase`,
`FineTerrainRefineOrchestrator.refine_rect/refine_queued_chunk`,
`ChunkRefineWorker.drain_queue/drain_persisted`,
`EntryRefineOrchestrator` scene/path, debug route `map.py`.

Проверка: old/new entry equivalence, old type import identity,
edit → replan affected closure, stale aggregate не выдаётся за current,
stale source → SurfacePlanningStale → rollback без publish (L0 и
detailed; критерий transitional — действует до world-source-versioning,
итоговый критерий: manifest штампует revision set, abort отсутствует),
fresh source → publish в той же UOW, no-writes validation,
в compatibility module и guard нет direct climate/hydro/relief planning
кода. City/location caches не меняются.
Долг PC-8C: убрать lazy import `build_local_plan_from_coarse` в
ClimateLocalPlanProvider.build — вынести base pole helpers из provider
module или удалить legacy chain; после правки import должен быть
top-level.
PC-9A cleanup: отделить transitional SurfaceTerrainContext от frozen
contracts — убрать generator imports (ClimatePoleField/ClimateAnchorField/
SurfaceHeightmap) из contracts/surfacePlanningView, сохранив old type
identity и восьмиполевой public API.
Done: current callers идут через одну boundary; old path лишь shim;
publish защищён revision check внутри caller UOW.

**PC-9 IMPLEMENTED / VERIFIED (2026-10-24), ожидается приёмка мастером.**

Review cleanup DONE (2026-10-24, по замечанию мастера): удалён мёртвый public
WorldPackWriter.maybe_checkpoint_manifest из pack/io/worldPackWriter.py и
два assert_not_called в test_pack_fine_terrain_refine_parallel.py. Владелец
публикации не меняется; новых файлов нет (io11→11, test root без добавлений).
Проверка: refine parallel + planning boundary suite — 14 tests OK;
production references=0, git diff --check OK.


Итоговая реализация:
- application/cancellation/requestPlanWait.py::RequestPlanWait — frozen
  request-side token/deadline adapter; unbounded() только на внешних
  pack/map/CLI boundaries. PlanningExecutionPolicy.wait_timeout_seconds
  optional finite positive, default None; TOML round-trip проверен.
  Поле зарезервировано: pack/map пока явно unbounded по принятому контракту.
- terrain/passes/surfaceTerrainContext.py — prepare/require shim с required
  keyword-only planning/capture/wait, без hydrology_generator; nodes/edges
  compatibility-only. None/ValueError и восьмиполевой type identity сохранены.
- composition/surfacePlanningAssembler.py::prepare_captured_context —
  module-level request report + working-view adapter; phase diagnostics
  replay одинаков на HIT/MISS, dedupe и validate_only rejection.
  Capture/bundle не получают mutable request/cache state. mountain_template_inputs
  в surfacePlanningCapture.py замораживает caller-loaded mountain subset.
- Все ledger callers/transits переключены: terrainBatch,
  worldSurfaceMaterialization, packMaterialization, worldMapBake,
  completeness, wilderness outline, packReadServices/loading, map routes.
  Existing Container создаёт process-scoped registration/assembler/capture/guard
  поверх одного registry/service/cache; startup требует explicit resource
  policies, lifespan/CLI закрывают planning executor. Numeric defaults нет.
- guards/sourcePublication.py::SourcePublicationGuard — repositories
  IWorldRepository + INamedLocationRepository и injected capture, без своей
  txn/SQL writes. L0/detailed: одна entry capture, compute без publication lock,
  caller transaction_if_needed {authoritative re-capture/check → publish}.
  Stale → SurfacePlanningStale/rollback, без auto-retry и без manifest save;
  blobs могут оставаться. OCC transitional до world-source-versioning.
- WorldMapBake/PackDetailedBake/FineChunkPersist не публикуют manifest.
  FineChunkPersist сохраняет blobs/sidecars и recalc в памяти; вызов checkpoint
  удалён. Scene/path/drain остаются compute/persist под operation owner.
  FineTerrainRefineOrchestrator._refine_rect — общий unpublished single-chunk
  kernel; refine_rect — standalone owner с final save, refine_queued_chunk
  использует kernel без публикации (worker drains не публикуют). Standalone
  debug entries публикуют один раз через finalize_pack_on_world в конце;
  исправлена передача world repository/db_path вместо WorldService.
  Флага publish_manifest нет. Settlement publication остаётся вне PC-9.
- Legacy context — planning/legacy/surfaceTerrainContext.py, old paths
  re-export того же определения; climate helpers — climate/planning/basePoleLayout.py,
  local provider import top-level. Cache/fingerprint vectors и manifest IDs сохранены.
- Offline bake/smoke callers получили explicit lifecycle/DI/wait. Offline
  smoke читает frozen accepted river routes/beds; legacy waterfall-drop
  diagnostics больше не выдаёт (они не входят в PC payload).

Проверки (из корня, PYTHONPATH=backend):
- unittest discover backend/tests/planning/{consumers,providers,contracts,encoding}:
  consumers48/providers129/contracts69/encoding7 — OK; tests/cache21 — OK.
  Итого planning/cache 374 tests.
- Обязательные test_water_placement_pass, test_relief_objects_z,
  test_hydrology_hy12_rivers, test_pack_bake_modes, test_detailed_bake_c11 —
  59 OK. Дополнительно parent_light_refine, pack_fine_terrain_refine_parallel,
  wilderness_region_index, region_state_contract, map_cell_query_facade,
  light_bake_cleanup, region_state_overlay, pack_root_resolution,
  hydrology_river_round2 — OK. Всего уникальных regression tests139;
  суммарно 513 tests. SQLite/cache/temp/async suites вне sandbox после
  подтверждённого Windows asyncio/socketpair ограничения; backend не стартовал.
- Реальная SQLite UOW: fresh check/publish в одной transaction; stale L0
  и detailed → ROLLBACK, bytes manifest прежние; изменение named_locations
  замечается guard; validate_only не materialize/publish. Проверены independent
  token cancellation/deadline/shared build, container singleton/shutdown,
  no-extent, frozen view imports, legacy maps isolation, no lower save/checkpoint.
- Local pyright --project backend/tests/typing/planning/pyrightconfig.valid.json:
  0 errors; invalid config --outputjson: 48 diagnostics, exact 47 EXPECT
  code/location pairs, missing/unexpected/other files = 0.
- AST compile всех изменённых Python modules, git diff --check — OK.
  Executable class bodies: WorldDataWiring274, PackMaterialization268,
  WorldSurfaceMaterialization247, FineTerrainRefine246, PackDetailed217,
  FineChunkPersist213, TerrainBatch201, WorldMapBake168, Capture120;
  новые RequestPlanWait18/SourcePublicationGuard14, legacy context13; все ≤300.
  Direct counts: cancellation5→6 (WARN), climate/planning3→4,
  planning/legacy0→2, guards2→3, composition4/contracts3; fine10/chunks4/entry4
  без новых файлов; container9, materialize11, bake16, read22, routes16,
  terrain/passes9 без новых файлов (WARN). Test modules расширены на месте.

PC-9 завершён как implementation/verification; PC-10 автоматически не начинать.
World-source-versioning/revision-set stamp/удаление OCC — отдельный трек,
никакие schema/DAG/city/location-cache изменения и commits не выполнялись.

**PC-10 — L0 consumer cutover.**

**DONE (IMPLEMENTED / VERIFIED, 2026-10-24; ожидает приёмки мастером).**
L0 получает `SurfacePlanBundle` через `LightGridBakeContext.surface_bundle`;
`require_surface_bundle()` явно отклоняет отсутствие плана, чужой world и
несовместимый light side. Eight-field `surface_planning` сохранён для
landcover/road/settlement без новых полей и без смены их lifecycle.

Исполняемая детализация ledger: existing
`composition/surfacePlanningAssembler.py::prepare_captured_bundle` — общая
request diagnostic boundary, возвращающая bundle; `prepare_captured_context`
делегирует ей и создаёт legacy working copy. Existing
`packMaterializationOrchestrator.py::_materialize_l0_pack` передаёт этот же
bundle в `WorldMapBakeOrchestrator`, не делает второй capture/build.
Standalone `bake_tiles`/`bake_tile` используют injected capture/planning при
отсутствии bundle; legacy context всегда выводится из полученного bundle.
Publication guard PC-9 не изменён. Это необходимые transport seams PC-10,
не новый provider, slot или отдельный шаг.

ReliefContributor копирует `light.base_surface_z`, ClimateContributor
семплит frozen climate_base через `ClimatePlanSampler`. MountainContributor
вызывает stateless `MountainMaskMaterializer.apply_plan`; `collect` читает
только stamped `mountain_layout.entries`, paint/z/facing — frozen light
effects. Нет load/stamp/selection/накопления `_base_z`. Отдельный
`autoresolve_mountain_specs` удалён. Canonical prepared coarse collector
остаётся единственным selection kernel provider'а; исторический World-wrapper
`collect_mountain_entries_for_coarse` доступен legacy kernel regression tests,
но production L0 его не вызывает после PC-9/PC-10.
RavineContributor применяет scope-independent absolute effects без detection
по compose tiles. Existing `masks/terrainMerge.py` и
`lightGrid/paintTerrain.py` принимают typed `tuple[TerrainMergeEntry,...]`;
алгоритм rank merge общий, без World lookup или синтетического rank.

HydroContributor читает final `HydrologyPlan`: ready DeclaredWaterPaint и
post-river coarse hydro/z. Нет live enabled/autoresolve/locations reads,
loader или повторного разрешения anchors. Порядок corridors → lake/coastline
→ coarse open water сохранён; segment dilation, intent width_wire без
dilation и `_PRESERVE_DECLARED_RIVER` сохранены. Fine overrides/sparse hydro
не переключались (PC-11).

**Явные baseline delta по §6.31-B/C:** L0 больше не выбирает свой набор
auto mountains, а проецирует единый coarse layout. Mountain/ravine z
применяется независимо от успеха terrain paint (включая preserved hydro),
без повторного rise/drop. Не заявляется равенство прежним двум несовместимым
mountain selections. Pre-mountain light base/noise/clamp сверены с
pre-cutover формулой; climate wire и declared raster/width semantics сохранены.

Проверки: consumers56 (8 новых PC-10 cases), providers129, contracts69,
encoding7, cache21; пять обязательных regression suites59; дополнительные
L0 suites47 (wilderness_region_index, light_grid_compose, mask_domain_materialize, bathymetry_stub,
light_bake_cleanup, terrain_merge) — **388 tests OK**. Consumer/cache/async
regressions повторены вне sandbox после подтверждённых Windows
socketpair/TemporaryDirectory ограничений. Pyright valid0 включает оба
bake orchestrators, context, paint helpers и все switched contributors;
negative48 exact на 47 EXPECT code/location pairs (строка162 — два diagnostics).
HIT/clear/rebuild/fresh single-worker wire equality, full/partial mountains,
ravines и declared hydro, no-live-read/no-second-selection, immutable payload,
height при отклонённом paint, standalone DI HIT/MISS, light/full writer path,
edit→replan без eager compose и existing stale publication guard — проверены.
Старые L0 fixtures переведены на frozen caller inputs; отсутствие bundle
теперь явная contract error вместо пропуска sampler/fill.

Counts: lightGrid11→11, contributors10→10, hydro6→6, mountains24→24,
masks13→13, bake16→16, composition4→4, providers tests5→5,
typing5→5; consumers4→5 (`test_l0_l2.py` по §6.27), tests root278→278.
WARN для переполненных/более5 каталогов выданы; новых flat modules в них нет.
Все затронутые executable classes <300 строк (PackMaterialization269,
WorldMapBake184).
SQL/DAG/backend/коммиты/GEO algorithms/city-location caches не затронуты.
PC-11 и PC-12 не начинались; следующий шаг — только после «ок» мастера.

Цель: L0 compose получает готовые planning results.
Файлы: worldMapBakeOrchestrator.py, lightGrid/bakeContext.py и только
named climate/relief/hydro/ravine/mountain contributors ledger PC-0;
в ledger также входят MountainMaskMaterializer.collect,
collect_mountain_entries_for_coarse и autoresolve_mountain_specs по
§6.30 (не два независимых выбора объектов).
Контракт: layout/ref consumption без локального повторного planning;
contributors не читают World/locations и не выводят результаты из
ctx.tiles-scope — detection/geometry inputs только из frozen plan refs
(DeclaredWaterPaint для hydro declared path, scope-independent ravine
cell set, единый mountain layout); paint остаётся tile-scoped. Existing
pack writer/manifest cache contracts сохраняются.
Проверка: light/full L0 baseline, HIT/MISS equality, partial re-bake
равен full bake на пересечении tiles (ravine/hydro declared/mountains),
materialize
только на bake request, edit без eager materialization. Done: общий
planning работает на реальном L0 пути, не только в изолированном
service test; RavineContributor, HydroContributor и
MountainContributor поимённо переведены на frozen inputs.

**PC-11 — L2 consumer cutover и исправление архитектурных границ.**

**DONE / ACCEPTED (2026-10-27): мастер разрешил переход к PC-12 («Далее»).**
PC-11.1…PC-11.8 закрыты; семь review находок проверены повторно, evidence ниже.
Блокировка PC-12 снята. Исторический design gate PC-11.1 закрыт
согласованной class map и caller ledger соответствующего подпункта.

**Историческое evidence функционального cutover (не архитектурный DONE).**

**Review correction PC-11 (2026-10-24).** Замечания 1/3: compose warning
проверяет frozen bundle; L2 fine overrides обходятся как tuple rows, hydro/
climate working maps ограничиваются текущим tile (без мировой dict-копии
на каждый tile). Поля/порядок/выход materialization не меняются; существующие
baseline/order/production tests и pyright проверяются повторно. Общая
индексация rows на request boundary не вводится в этот fix: обход мировых
rows остаётся. Каталоги без новых модулей.
Замечания 2/4 входят в обязательные PC-11.3/PC-11.2 ниже: убрать игнорируемый surface_ctx
из WorldMapBakeOrchestrator.bake_tiles/bake_tile атомарно с callers; отдельно
согласовать domain owners/API проекций для legacy и climate consumers.
До cleanup параметр явно помечен transitional compatibility-only.
Review correction VERIFIED: L2 surface tests4 + production/parent-light/parallel/
climate/compose suites24 = 28 уникальных tests OK; multi-tile climate baseline
и tile-local coarse-map assertion дополнительно повторены. Pyright valid0;
git diff --check OK. Новых файлов и backend-start нет.


**Функциональная реализация проверена 2026-10-24; архитектурно не принята.**

`TerrainBatchOrchestrator.build_tile_surface_state` и chunk generate API получают
`SurfacePlanBundle`; fine_z_overrides и sparse_fine_hydro читаются из final
hydrology envelope в request-local maps. Порядок upsample/clamp → override
с base±z_band → terrain/facing carry → region paint → hills → hard corridor
→ gap analysis сохранён. Parent light по-прежнему загружается из persisted
pack через require_parent_light; reconstruction из ReliefPlan не добавлена.

Bundle проходит атомарно через WorldSurfaceMaterializationOrchestrator →
PackDetailedBakeOrchestrator/detailedBakeRefine → FineTerrainRefineOrchestrator
→ FineChunkRunner → FineTileContext/fineTilePrep/fineChunkCompute, а также
scene/path, ChunkRefineWorker drain_queue/drain_persisted и climate-fine drain.
Три standalone map entry используют require_surface_plan_bundle в existing
compatibility entry module: одна capture/prepare на входе, downstream
не вызывает planning/capture/to_legacy_context. Existing publication guard
и ownership manifest не менялись. save_z_slice/plan_bootstrap_tiles вне L2
ledger и сохраняют прежний контракт.

LandcoverInputs проецирует local anchors из climate_local, relief observations
из **terrain_base.surface_z** (не ReliefPlan), hydro/extent из final hydrology.
FactConsumerContext получил typed observation fields; карты строятся один раз
на вызов prepare_landcover_inputs, то есть **на тайл**, а не на запрос.
Это незакрытый perf/ownership дефект PC-11.2/PC-11.5; legacy surface
не передаётся в L2, но остаётся в других production paths. Transitional fallback сохранён
для остальных consumers. Region collection/state snapshot и climate profile/
tier/weather recipe не менялись. ClimatePackBakeOrchestrator получает bundle
и строит отдельные working indexes/fields из payloads без legacy aggregate.

Две необходимые type-only правки consumer seam: ColumnBounds использует
read-only properties для frozen bounds; fineTilePrep явно проецирует GridBBox
в ColumnRect с теми же четырьмя координатами. Runtime geometry не менялась.
Старые fixtures переведены на captured bundles/новые keyword и patch names;
slot-render fixture публикует manifest на своей operation boundary после
FineChunkPersist.finish (сам lower persist по-прежнему не публикует).

Проверки (из корня, PYTHONPATH=backend; asyncio/SQLite вне Windows sandbox
после воспроизведённого ограничения socketpair/event loop):
- planning discover: contracts69/providers129/encoding7/consumers63; cache21 —
  **289 уникальных tests OK**. Полный запуск содержал 267 planning tests;
  добавленный climate baseline case и усиленный relief-facts case проверены
  отдельно; финальный production test повторён после добавления persisted drain.
- Пять обязательных regression suites и десять дополнительных L2 suites:
  **159 уникальных tests OK** после исправления двух устаревших fixtures;
  affected region-state/slot-render modules повторены: 17 OK.
  Итого planning/cache/regressions: **448 уникальных tests**.
- HIT/clear/rebuild/fresh-service equality; reverse tile order; full sampled
  fine overrides с clamp и hard corridor; pre-relief facts trap; immutable
  bundle; existing fresh/stale publication tests — OK. Реальный L0 disk →
  detailed → cold-cache queued → entry → queue/persisted drains даёт одинаковый
  wilderness wire, без второго capture/planning/legacy aggregate.
- Baseline: implementation из исходного d14c5f21 загружена независимо;
  dry/declared-region/river дают точное равенство TileSurfaceState на 27 tiles.
  Coarse/fine climate wires сверены с прежними field-based builders.
  **Baseline delta PC-11: нет** (PC-10 deltas не переоцениваются).
- Local pyright valid: 169 files, 0 errors; negative: 48 diagnostics,
  exact 47 EXPECT code/location pairs, missing/unexpected/other files=0.
  AST compile изменённых Python modules и git diff --check — OK.

Новых production/test modules нет. Direct counts без роста:
materialize11, bake16, refine/fine10, refine/detailed14, routes16,
terrain/landcover9, terrain/passes9, lightGrid/contributors10, pack/climate7,
pack/refine8, tests root278, consumers5, typing5. WARN выданы в чат.
Все изменённые production classes <300 исполняемых строк (TerrainBatch191,
WorldSurface239, PackDetailed206, PackMaterialization252, ClimatePack227,
EntryRefine212, FineTerrainRefine232).
SQL/DAG/backend-start/GEO algorithms/city-location caches не затронуты;
агент коммитов не создавал. PC-12 не начат.

Цель: L2 использует тот же planning result/revision.
Файлы: terrainBatchOrchestrator.py и named detailed/entry callers PC-0.
Контракт: актуальный layout передаётся до materialization; fine details
согласованы с domain recipe, новый placement не запускается.
Проверка: detailed/entry baseline, порядок tiles, HIT/MISS, stale revision,
climate/terrain/hydro consistency; не трогать city/location cache consumers.
Done: общий план потребляется L0/L2 без второго independent planning path;
все PC-11.1…PC-11.8 приняты. Прежний факт прохождения тестов сам по себе
не является основанием вернуть DONE.



#### Обязательные подпункты PC-11 после архитектурного review

**Граница snapshot/materialization (решение мастера, 2026-10-25).**
Каждый snapshot, включая начальный при инициализации, иммутабелен;
последующие модификации образуют последовательность snapshots. Владение
этой последовательностью, определение актуального состояния и способ его
получения относятся к отдельному snapshot-треку, не к PC-11. Не проектировать
здесь новый snapshot lifecycle или способ свёртки истории; связь с существующим
треком world-source-versioning уточняется в том треке.
Snapshot runtime пока не реализован: имеющиеся ТЗ и SQL-схема не являются
готовым сервисом. Общий snapshot CRUD (единый интерфейс и реализация),
включая адресацию объекта/чанка/области вплоть до fine_cell, проектируется
в отдельном треке на основе docs/tz_world_snapshot.md и world-source-versioning;
не создавать второй snapshot service внутри planning/materialization.
Адресуемая область/единица данных и LOD результата задаются отдельно.
**Порядок LOD-чтения (уточнение мастера, 2026-10-25):** сначала прочитать
запланированные метаданные для запроса, затем проверить наличие пригодной
материализации нужного scope/LOD. На текущем этапе проверяется фактическая
материализация по existing pack/CRUD правилам, без snapshot provenance или
новой классификации STALE/UNVERIFIED. Read переиспользует готовые слои;
недостающее создаёт отдельный explicit write/refine запрос, не скрытый generate
в read. Проверка соответствия snapshot относится к будущему отдельному треку.
В будущем этот путь также проверяет наличие snapshot через общий CRUD;
точное место проверки и семантика отсутствия snapshot определяются отдельным
snapshot-треком. В PC-11 не вводить фиктивный snapshot lookup или новое
хранилище ради будущей проверки.
Задел в коде PC-11 — явный TODO в application owner метода LOD-чтения,
рядом с metadata/materialization lookup, со ссылкой на
план `.cursor/plans/world-state-crud-transition.md`, §7 «Связь с PC-11 и
будущими snapshots» (WS):
`TODO(snapshot): integrate snapshot existence lookup via the shared CRUD;
see .cursor/plans/world-state-crud-transition.md, section 7 (PC-11 and future snapshots).`
Комментарий ставится в соответствующем существующем методе при его cutover,
не во всех callers и не в доменном алгоритме. Это обозначение будущего шва,
без нового interface/service, no-op метода, synthetic snapshot или ветки
«snapshot существует». Read-owner в PC-11 — WildernessRegionReadService.outline,
с последовательностью и early-return исключением по PC-11.1-D/E ниже.
EntryRefineOrchestrator.refine_from_entry — write-owner, этот read TODO ему
не назначается. Готовность PC-11 не зависит от реализации snapshot CRUD.
Материализация читает метаданные того, что запланировано, из последних
актуальных данных последовательности snapshots и выполняется только по
запросу на нужную область/объект и LOD. Создание snapshot само по себе не
является запросом материализации: 1000 snapshots не означают 1000 пересборок
или материализацию всей истории при одном запросе.
PC-11 разбирает доменных владельцев, методы подготовки/потребления метаданных
и границы materialization, не реализуя snapshot-механизм. Topology принадлежит
домену топологии; наличие отдельных методов получения WorldTopology для
planning и materialization само по себе не является дефектом. Не требовать
передачи topology именно через bundle.water_placement.payload.topology:
расположение ссылки в водном payload не делает water placement владельцем
топологии.
**Переходное состояние реализации, не новое решение о snapshots:** PC-11
не меняет существующие revision/publication guards. Их текущая реализация
не объявляется целевой snapshot-архитектурой; соответствующий cutover
рассматривается отдельно в world-source-versioning.

Все подпункты **OPEN**. Выполнять по одному, с отчётом и приёмкой мастера;
не объединять весь остаток в один кодовый заход. Новые алгоритмы GEO-1,
изменения city/location caches, SQL, DAG и запуск backend вне scope.

Карта находок: ответственность TerrainBatch (1) → PC-11.4;
self-capture/мёртвый surface_ctx (2) → PC-11.3;
неверное размещение require_surface_plan_bundle (3) → PC-11.3;
generators → pack.bake в landcover (4) → PC-11.6;
доменные операции/повторные мировые maps в contributor adapter (5) → PC-11.5/11.2;
двойной FactConsumerContext.surface (6) → PC-11.7;
три владельца bundle→working projection (7) → PC-11.2.

**PC-11.1 — зафиксировать домены, владельцев, папки и швы переноса.**
Статус: **design принят для старта реализации (2026-10-26)**: мастер закрыл
вопросы review и явно выбрал начало реализации по шагам. Отдельный WS
integration gate сохраняется; это не DONE реализации всего PC-11.
Сначала карта ниже, затем проверка
контрактных пробелов; не начинать с проектирования универсального context.
Цель: каждой операции назначить единственного владельца и правильное место.
ТЗ: docs/tz_terrain_generation.md §Surface planning/cache и §Multi-pass terrain
skeleton; docs/tz_map_light_bake.md §MaskDomain materialize, §Регионы покрытия,
§L0/L2 и §Surface planning/cache; docs/tz_world_pack_storage.md §Parent light SoT
и §L2 refine module layout.
Файлы: настоящая карта/§5.4/§6.31-F и указанные ТЗ; код пока не менять.

**Карта ответственности и целевых файлов.** Все пути в таблице относительно
`backend/app/`; новые файлы перечислены явно, это план размещения, не создание
новой общей инфраструктуры. Существующие algorithms/POJO перемещаются или
переиспользуются с сохранением identity/семантики, не переписываются заново.

| Домен / владелец | Единственная ответственность | Целевой файл / папка | Разрешённые зависимости и граница |
|---|---|---|---|
| Surface request entry / `SurfacePlanningEntry` | На входе запроса подготовить согласованные planning inputs и domain views через existing capture → prepare | `application/worldData/planning/composition/surfacePlanningEntry.py` (новый) | Capture, assembler, публичные domain projectors; без управления последовательностью snapshots, climate/relief/hydro алгоритмов, SQL writes и paint |
| Surface request contract / `SurfaceWorkingMaps` | Только неизменяемые ссылки `climate`, `terrain`, `hydrology` на request-owned domain views | `application/worldData/planning/contracts/surfaceWorkingMaps.py` (новый) | Application DTO: без World/SQL, domain logic, resolve/projector методов и самостоятельных maps; не cached payload |
| Surface planning / existing `SurfacePlanningAssembler` | Получить согласованные frozen envelopes | `application/worldData/planning/composition/surfacePlanningAssembler.py` | PlanningService/providers; не становится владельцем рабочих полей всех доменов |
| Climate / `ClimateWorkingFields` и его domain projector | Pole/local views и resolved climate profiles | `application/worldData/generators/climate/materialize/climateWorkingFields.py` (новый leaf с `__init__.py`); profile resolution остаётся в existing `application/worldData/generators/climate/registry.py` | Climate payloads и request-bound intra-domain profile resolver; ни hydro maps, ни region selection, ни pack |
| Terrain / `TerrainWorkingFields` и его domain projector | Индекс pre-relief terrain base для наблюдений | `application/worldData/generators/terrain/materialize/terrainWorkingFields.py` (новый leaf с `__init__.py`) | TerrainPlan; не подменяет его ReliefPlan и не владеет final hydro surface |
| Hydrology / `HydrologyWorkingFields` и его domain projector | Final coarse surface/hydro и tile-indexed fine overrides/corridors | `application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py` (новый leaf с `__init__.py`) | HydrologyPlan + captured grid parameters; без повторного routing/carve и чтения World |
| Region observations / existing fact consumers | Из готовых domain views вычислить запрошенные региональные факты | `application/worldData/regions/factConsumers/{context,climate,relief,hydrology}.py` | Публичные climate/terrain/hydro views; не создаёт их, не читает World/registry/pack |
| Landcover input composition / `prepare_landcover_inputs` | Связать готовые observations, доменную topology и region-state snapshot в LandcoverInputs | `application/worldData/regions/inputs/landcoverInputs.py` (новый leaf с `__init__.py`) | Готовые domain views + `collect_facts`; получение topology через контракт её домена, без собственной topology policy, profile_for, мировых dict-копий, collection/paint; зависимости от водного payload не требует |
| Landcover / `LandcoverMaterializer`, `LandcoverCollectContext` | Declared/anchor/auto region collection, coverage/precedence и raster footprints | `application/worldData/generators/terrain/landcover/{types,materializer,collect}.py` | Собственный typed context/recipe, LandcoverInputs и общий rasterizer; без LightGridBakeContext/LightGridCompose и pack imports |
| Landcover fine / `paint_regions_fine` | Применить region winners к fine terrain в пределах запроса | `application/worldData/generators/terrain/landcover/finePaint.py` | Подготовленные LandcoverInputs/context/background keys; не фабрикует pack context и не готовит климат/гидрологию |
| Coverage policy / existing `surface_coverage` | Выбрать background terrain по coverage policy и готовому climate profile | `application/worldData/regions/coverageBackground.py` | Terrain registry/policy и resolved profile; не читает climate registry и не декодирует pack wire IDs |
| L0 landcover adapter / `LandcoverContributor`, `LandcoverLightAdapter` | Адаптировать L0 context к domain API и записать готовый результат в canvas | `application/worldData/pack/bake/lightGrid/contributors/landcover/{contributor,apply,background}.py` + `__init__.py` | Domain materializer/coverage policy + pack canvas; не содержит selection/scoring/profile resolution |
| L0 mask execution / `run_mask_domain`, pack-facing `MaskDomainMaterializer` | Только gate/lifecycle/delegate вызовы L0 adapters | `application/worldData/pack/bake/lightGrid/maskDomains/runMaskDomain.py` + `__init__.py` (перенос из masks) | Pack canvas/context и adapter protocol; collection/selection алгоритмы не поглощает |
| L0 footprint writer / `apply_terrain_footprint` | Записать готовый footprint/победителя в L0 canvas | `application/worldData/pack/bake/lightGrid/maskDomains/applyFootprint.py` (перенос из masks) | Готовые footprint/registry и pack canvas; не делает planning/coverage selection |
| Общая коллекция источников / `default_collect`, `MaskSourceCollector` | Только merge declared → anchors → auto через callbacks | `application/worldData/masks/collection/defaultCollect.py` + `__init__.py` (новый leaf) | Generic typed source/context protocol и mergeDeclare; без pack/bake типов. L0 execution runner принадлежит отдельному pack owner |
| Light-grid geometry / `LightGridScale` | Чистый scale/coordinate contract | `dataModel/spatial/grid/lightGridScale.py` (новый) | Только spatial primitives; общий `light_span_for` имеет один canonical owner здесь, прежний wire path при необходимости re-export того же symbol |
| Light-grid coordinate operations | Pure conversion fine ↔ light ↔ macro, без bake policy | `application/worldData/generators/coordinates/light/grid.py` + `__init__.py` (новый leaf) | LightGridScale/spatial primitives; existing `pack/bake/lightGrid/coords.py` может re-export тех же symbols без второй реализации |
| L0 materialization / `WorldMapBakeOrchestrator` | Выполнить compose готового плана для заданных tiles | `application/worldData/pack/bake/worldMapBakeOrchestrator.py` | Обязательные prepared inputs и domain contributors; без capture/prepare fallback и мёртвого surface_ctx |
| L2 materialization / `TerrainBatchOrchestrator` | Parent-light upsample, применить готовые domain effects, generate chunk cells | `application/worldData/materialize/terrainBatchOrchestrator.py` | Parent light и необходимые готовые domain inputs; без planning/capture, bootstrap preview и MapCellService persist |
| Tile-set selection / existing `PackTilePlanner` | Light/full expected tile set | `application/worldData/pack/bake/packTilePlanner.py` | World/locations и tile-selection policy; surface_ctx сейчас не используется — убрать его, capture к planner не переносить |
| Bootstrap preview / operation facade | Применить entry extent-probe R2 и делегировать tile-set selection | existing `application/worldData/materialize/worldSurfaceMaterializationOrchestrator.py::plan_bootstrap_tiles` | NoExtent → прежняя ошибка, READY → pure PackTilePlanner; без prepare. TerrainBatch method удаляется |
| ~~Z-slice import entry~~ | ~~Скоординировать climate input → generate_z_slice → save_pass~~ | **УДАЛЯЕТСЯ** (мастер, 2026-10-24): `save_z_slice`/`generate_z_slice` мёртвы с 803ff40a; `mapCells/imports/` не создаётся | — |
| Terrain generation / existing `TerrainGeneratorService` | Генерировать клетки | `application/worldData/generators/terrain/terrainGeneratorService.py` | Собственный recipe/готовые inputs; без repository/persist/planning entry |
| Map-cell persist / existing `MapCellService` | Сохранить переданные клетки | `application/worldData/mapCells/mapCellService.py` | Repositories; без pole resolve и terrain generation |
| Region outline render | Представить готовую region geometry | `application/worldData/render/regions/regionOutline.py` | Domain inputs/materializer/общая геометрия; без фабрикации LightGridBakeContext и profile resolve |
| Operation publication / existing L0/detailed owners | UOW, authoritative freshness guard и manifest publication | existing `pack/bake/packMaterializationOrchestrator.py`, `materialize/worldSurfaceMaterializationOrchestrator.py`, standalone owners | Делегирование request entry и materializers; не копировать capture/prepare или domain projection алгоритмы |

Контракт: один владелец **каждой ответственности**, а не один класс на весь
мир. Повторная механическая проекция одних climate fields у разных consumers
заменяется вызовом climate owner; аналогично terrain/hydrology. Composition
вызывает эти public APIs и передаёт результаты, но не присваивает их операции.
Агрегат refs сам по себе допустим, если нужен caller contract: его форма
выводится из этой карты, он не разрешает данные и не становится новым SoT.
По принятому решению стыка 2 используется SurfaceWorkingMaps; его три refs
не переносят операции доменов в composition/DTO.

Уточнение ownership (2026-10-25): WorldTopology и её операции принадлежат
домену топологии. SurfacePlanningCapture.capture и подготовка inputs для
materialization решают разные задачи; наличие двух способов получить значение
WorldTopology не доказывает дублирование доменной логики. Конкретный шов
получения topology для materialization остаётся предметом точных signatures
PC-11.1, а не автоматически выбранным чтением water_placement payload.
Capture view, frozen planning payload, request working view и region-state
snapshot имеют разные назначения; ни один из этих терминов здесь не вводит
владельца последовательности snapshots мира.

**Методные контракты PC-11.1 (design для приёмки, 2026-10-25).**
Этот раздел детализирует карту владельцев; код не разрешает и статус OPEN
не снимает. При расхождении с прежними формулировками подпунктов применяется
данная детализация. Пути ниже относительно backend/app/. Существующие свободные
функции обозначены module.function; класс только ради записи Class.method не
создаётся. Новые методы помечены «target», остальные сохраняют существующее
назначение. Нельзя переносить алгоритм в entry/adapter под видом helper.

**A. Общий snapshot CRUD — чей домен и граница PC-11.**
- **Уточнение разделения (мастер, 2026-10-25):** общий CRUD текущего
  состояния — IWorldStateCrud/WorldStateService в платформенном worldState,
  вне generators. Поклассовый переход existing CRUD/read consumers —
  отдельный план world-state-crud-transition.md, WS-0…WS-5. Домены внутри
  generators — потребители read-контракта/готовых DTO, не его implementations.
  Нижеследующий IWorldSnapshotCrud относится ТОЛЬКО к lifecycle snapshots;
  прежняя трактовка его как общего CRUD всех данных мира отменена.
- Владелец общего lifecycle/API — платформенный домен worldSnapshot по
  docs/tz_world_snapshot.md. Не planning, не pack, не terrain и не topology.
  Общий интерфейс IWorldSnapshotCrud — application/worldSnapshot/contracts/
  snapshotCrud.py (target), единая реализация WorldSnapshotService — existing
  target application/worldSnapshot/worldSnapshotService.py. Разделение
  внутренней реализации по ответственности не создаёт второго публичного CRUD.
- DTO identity/query/mutation/result принадлежат dataModel/worldSnapshot/;
  доменные payload/patch типы остаются у своих доменов. Spatial scope — общий
  dataModel/spatial/query/worldScope.py, не тип внутри terrain или snapshot
  blob. Scope не содержит LOD; SnapshotQuery передаёт scope и requested LOD
  раздельно. Всё перечисленное здесь — target отдельного трека, файлов/API
  в PC-11 не создавать. Полный storage/file freeze проводится в snapshot-треке.

| Target метод интерфейса и реализации | Вход → выход | Разрешённая ответственность |
|---|---|---|
| IWorldSnapshotCrud.create / WorldSnapshotService.create | SnapshotCreate → SnapshotRef | Создать начальное immutable состояние из согласованных доменных данных; без materialization |
| IWorldSnapshotCrud.read / WorldSnapshotService.read | SnapshotQuery → SnapshotReadResult | Прочитать metadata/заданный scope из выбранного состояния; вернуть resolved SnapshotRef, не создавать отсутствующие cells |
| IWorldSnapshotCrud.update / WorldSnapshotService.update | SnapshotUpdate(base_ref, typed_changes) → SnapshotRef | Создать новый immutable snapshot; исходный не менять; делегировать доменную проверку и применение typed changes |
| IWorldSnapshotCrud.delete / WorldSnapshotService.delete | SnapshotDelete(base_ref, typed_targets) → SnapshotRef | Логически удалить адресованные данные в новом snapshot; не стирать историю или held-тела |

SnapshotRef идентифицирует world/timeline/snapshot; чтение latest и чтение
точного ref — разные typed selectors. Latest разрешается один раз на запрос,
result возвращает выбранный ref; последующие scoped reads не перескакивают
на новый latest посреди операции. В игре selector учитывает принятый source
set; latest мастера не подставляется вместо состояния игрока. SnapshotReadResult
различает найденное состояние и отсутствие snapshot, а также отсутствие
адресованного объекта в существующем snapshot. Ошибка/отсутствие не запускает
restore/materialize и не превращается в synthetic READY. Проверка существования
пользуется тем же read-контрактом, не отдельным store/источником истины.
SnapshotUpdate/SnapshotDelete сохраняют исходный base_ref; конфликт изменения
head не разрешается скрытой перезаписью latest. Конкретная conflict/branch
политика относится к отдельному треку, а не к PC-11.

WorldScope — typed union ObjectScope(domain, object_uid), ChunkScope
(координаты/идентичность chunk в его системе координат), AreaScope (typed
bounds + coordinate space), FineCellScope(FineGridCoord). Значение chunk size
берётся из метаданных, не зашивается в CRUD. ObjectScope не требует geometry;
преобразование object→footprint принадлежит домену объекта. Переход fine→chunk,
соседи и каноникализация принадлежат coordinate/topology APIs. Запрос одной
fine_cell не гарантирует физическую запись одной ячейки: формат chunk может
требовать read/modify/write chunk, но логическая дельта и результат адресованы
только запрошенной ячейке. Scope ≠ LOD ≠ единица физического хранения.

CRUD владеет lineage, immutable refs, атомарным сохранением и scoped чтением.
Он не содержит coverage selection, climate resolve, routing, carve, paint,
object placement или вычисление LOD. Доменные handlers валидируют и применяют
свои typed changes; repository/serializer владеют storage/encoding. GC/prune
held-ревизий — отдельная операция retention, не SnapshotService.delete.
Read доменных planning views/pack artifacts не превращается в новую реализацию
snapshot CRUD: это проекции/производные результаты общего состояния.
Имплементация и интеграция CRUD, точные DTO поля/дискриминаторы/версии и
transaction/storage protocol фиксируются в snapshot-треке; архитектурное
владение и четыре публичных операции зафиксированы здесь для его входа.

**B. Capture/preparation: один owner последовательности, без domain kernels.**

| Метод | Вход → выход / контракт | Что метод НЕ поглощает |
|---|---|---|
| SurfacePlanningEntry.capture_view (target) | Те же World, locations, mode, mountain_templates, ResolveContext, что SurfacePlanningCapture.capture → SurfacePlanningView | Делегирует capture; не создаёт world snapshot, не разрешает profile/topology повторным kernel |
| SurfacePlanningEntry.extent_status (target) | SurfacePlanningView → SurfacePlanningViewKind | Только discriminator; ни prepare, ни projectors |
| SurfacePlanningEntry.prepare_captured (target) | view, world, wait, resolve_ctx → tuple[SurfacePlanBundle, SurfaceWorkingMaps] или None | Порядок assembler → diagnostics → domain projectors → DTO; без loops по climate/terrain/hydro rows и без paint/persist |
| SurfacePlanningCapture.capture | Согласованные source inputs → immutable SurfacePlanningView | Существующий source projection; не snapshot CRUD и не materialization |
| SurfacePlanningAssembler.prepare | SurfacePlanningView, wait → SurfacePlanBundle или None | Existing explicit phase calls; не world-state manager и не owner working maps |

prepare_captured вызывает existing prepare_captured_bundle/report boundary,
а не копирует её алгоритм. При удалении legacy entry helpers в PC-11.7
единственный report boundary остаётся в composition; legacy shim не является
вторым owner. Capture-only diagnostics R2 и prepare diagnostics проходят один
request ResolveContext: ошибки дедуплицируются, NOTICE не логируется второй раз
для того же capture. NoExtent не создаёт SurfaceWorkingMaps. Foreign world
между view/bundle и bound world отвергается до projectors; «исправление» refs
или подстановка defaults в entry запрещены.

**C. Domain working views: точные публичные методы (target).**
Расположение каждого класса — *WorkingFields.py из карты. Factory classmethod
принадлежит тому же domain class, не helper в entry и не новый общий projector.
Параметры/результаты не Any/raw dict. Для существующих карт используется
Mapping[Coord, int] / Mapping[Coord, MapCellHydrology], где Coord — existing
tuple[int,int] в соответствующей системе координат. Read-only обеспечивается
реализацией (private dict + MappingProxyType либо immutable backing), не одной
аннотацией Mapping. Consumers не получают изменяемые private buffers.

| Метод / readonly property | Вход → выход | Ответственность |
|---|---|---|
| ClimateWorkingFields.from_plans | ClimateBasePlan, ClimateLocalPlan, bound profile_resolver: Callable[[ClimateKey], ClimateZoneProfile] → ClimateWorkingFields | Один раз подготовить pole/local views и frozen profiles через ClimateZoneProfile.from_data; private memo/lock по R3 |
| ClimateWorkingFields.profile_for_key | ClimateKey → ClimateZoneProfile | Frozen hit, иначе принятый request-bound registry resolver; ни I/O, ни capture, ни fallback собственного изготовления |
| ClimateWorkingFields.sample_pole | GridX, GridY → PoleClimateSample | Делегировать ClimatePlanSampler.sample_prepared с один раз подготовленными profiles; без per-cell пересборки profile index и live pole resolve |
| ClimatePlanSampler.sample_prepared (target в existing climatePlanSampler.py) | ClimateBasePlan, Mapping[ClimateKey,ClimateZoneProfile], GridX, GridY → PoleClimateSample | Один existing pole kernel; sample_resolved_profiles принимает готовый Mapping, не строит dict на каждый sample; old live adapter и ClimatePlanSampler.sample переводятся на тот же kernel |
| ClimateWorkingFields.local_field / ClimateWorkingFields.pole_field | readonly ClimateAnchorField / ClimatePoleField | Готовая domain geometry; pack-контур не вызывает live ClimatePoleField.sample |
| TerrainWorkingFields.from_plan | TerrainPlan → TerrainWorkingFields | Единственная request projection terrain_base.surface_z |
| TerrainWorkingFields.relief_z | readonly Mapping[Coord,int] | Pre-relief observation base, НЕ ReliefPlan.surface_z |
| HydrologyWorkingFields.from_plan | HydrologyPlan, SurfaceGridSettings → HydrologyWorkingFields | Один coarse index и tile-indexed fine maps за request; tile принадлежность по captured fine_span |
| HydrologyWorkingFields.coarse_hydro / HydrologyWorkingFields.coarse_surface_z | readonly Mapping[Coord,MapCellHydrology] / Mapping[Coord,int] | Final post-river данные и extent; полностью пустой hydro = unknown; только при непустом hydro sparse miss внутри surface extent = dry, вне extent = unknown |
| HydrologyWorkingFields.fine_z_for_tile | GridX, GridY → Mapping[Coord,int] | Readonly полный sampled fine-z output данного tile, без world-row scan |
| HydrologyWorkingFields.fine_hydro_for_tile | GridX, GridY → Mapping[Coord,MapCellHydrology] | Readonly sparse hard corridors данного tile, без world-row scan |
| HydrologyWorkingFields.fine_z_overrides / HydrologyWorkingFields.sparse_fine_hydro | readonly Mapping[Coord,int] / Mapping[Coord,MapCellHydrology] | Полные request-local indexes тех же frozen rows для transitional legacy copies; tile consumers используют indexed tile methods, payload schema не меняется |

Factory гидрологии может читать payload один раз и готовить tile indexes;
Fact consumer сохраняет existing test_region_fact_consumers semantics:
полностью пустой coarse_hydro означает отсутствие наблюдений, не доказанную
сушу/open_water_fraction=0, в том числе при disabled hydrology. При непустой
карте отсутствие записи означает dry только внутри coarse_surface_z extent;
вне extent наблюдения unknown. Working view не создаёт synthetic water/dry
entries для изменения этой семантики. Baseline delta по этому cutover нет;
existing тест пустого hydro корректен и сохраняется.
tile lookup — пустой readonly map при отсутствии rows, без синтетических
высот/воды. Consumer делает отдельный mutable buffer только если алгоритм
действительно его меняет. R3 binding live profiles остаётся переходным
принятым PC-11 контрактом; это не реализация snapshot isolation. Замена bound
resolver на чтение pinned source set — отдельный snapshot/source-versioning трек.

ClimateGeneratorService.resolve_surface_sample и tierResolve.resolve_tier_sample
получают keyword-only working: ClimateWorkingFields | None. Pack/refine callers
обязаны передать working; existing live-only callers оставляют None. При working
pole sample идёт через ClimateWorkingFields.sample_pole, каждый profile lookup
— через ClimateWorkingFields.profile_for_key. Helpers tierResolve получают тот
же accessor; алгоритм tier blend/influence остаётся единственным в tierResolve,
не копируется в WorkingFields. ClimateGeneratorService.weather_at_elevation
также принимает working для pack callers, чтобы registry lookup не остался
обходным путём. Weather/precipitation recipe прежний, за рамки profile access
этот шаг не расширяется. ClimatePackBakeOrchestrator получает climate view и
нужные hydrology view refs; hydrology projections в climate коде не появляются.

**D. Regions/landcover: данные, domain context и execution.**
- FactConsumerContext target: cells: tuple[Coord,...],
  climate: ClimateWorkingFields | None, terrain: TerrainWorkingFields | None,
  hydrology: HydrologyWorkingFields | None. Наличие None — явно отсутствующие
  observations, не пустая synthetic поверхность. В PC-11.5 ввести refs и
  перевести typed consumers; удалить legacy surface и временные старые typed
  maps/local_field/climate_profiles атомарно с остатком callers в PC-11.7.
  На промежуточном этапе dual fields строго migration-only, новый reader
  использует один объявленный канал, не field-by-field смешивание источников.
- climate.contribute вызывает local_field.nearest/profile_for_key своего
  climate view; relief.contribute читает TerrainWorkingFields.relief_z;
  hydrology.contribute читает final hydro/surface extent. Existing collect_facts
  агрегирует готовые facts, не resolve World/registry и не выбирает terrain.
- LandcoverCollectContext в existing landcover/types.py — frozen application
  DTO: world: World, locations: tuple[NamedLocation,...], scale: LightGridScale,
  tiles: tuple[Coord,...]. World здесь — existing domain recipe input, не
  snapshot API. Landcover owner читает только свой terrain/masks/seed recipe;
  поля pack writer/manifest/canvas/planning entry/bundle отсутствуют. tiles —
  scope/diagnostics, не ограничитель world-level autoresolve/seed selection.
  LandcoverInputs содержит topology/facts_at/state_snapshot/anchor_specs по
  existing контракту. Одни refs state_snapshot проходят L0/L2/outline запроса;
  immutable world snapshots и read snapshot region_states не отождествляются.

**Region-state lifetime (согласовано мастером 2026-10-26).** Operation owner
один раз загружает состояния через existing load_region_state_snapshot и
передаёт один readonly Mapping[str,StateSnapshotEntry] во все L0/L2 ветки
операции. Для L0 и запускаемых им entry/internal drains owner —
PackMaterializationOrchestrator, для detailed —
WorldSurfaceMaterializationOrchestrator; standalone
drain/CLI owner загружает свой mapping на входе отдельного запроса. Outline
сохраняет отдельный owner WildernessRegionReadService.outline и early-return
контракт ниже. Пустая операция без domain execution не требует state read.
Публикация и region-state single writer не меняются; это согласованный read
на время операции, не общий immutable snapshot мира или новый store.

Обязательный typed input region_state_snapshot проходит operation owner →
PackDetailedBakeOrchestrator/detailedBakeRefine либо EntryRefineOrchestrator →
FineTerrainRefineOrchestrator/ChunkRefineWorker → FineChunkRunner.refine_rects →
fineTilePrep → landcover inputs; L0 передаёт тот же ref через bake context.
FineChunkRunner больше не читает repository сам; consumer не выполняет
reload, не заменяет отсутствующий input на {} и не получает mutable backing.
Все tiles, scene/path и drains внутри одной операции используют тот же ref.
Mapping не сохраняется в queue job или process cache: следующий самостоятельный
drain-запрос получает новый read даже при HIT planning cache. Existing loader
optional-repo API вне этого caller ledger не меняется; новый prepared-input
контракт не маскирует отсутствие обязательного input.
Реализация: lifetime/signature thread-through входит в PC-11.3, domain
LandcoverInputs consumption — PC-11.5/11.6b без повторного чтения. Проверки:
один repository load на N tiles/scene+path+internal drain, одинаковая identity
во всех consumers, новый mapping в следующем запросе; изменение repository
между tiles не меняет уже полученные state inputs текущей операции.

**Привязка существующих POJO/WS contracts, без нового DTO (2026-10-26).**
Canonical domain POJO — `dataModel/regions/regionState.py::RegionState`;
materialization projection — existing `generators/terrain/landcover/types.py::
StateSnapshotEntry`; read capability/query/result — WS-план §3 и WS-0A §8.
Их поля не переопределяются в PC-11. RegionState → StateSnapshotEntry mapping:
ключ = state.region_uid; current_type = state.current_type;
tombstone = state.tombstone; spec_fingerprint = state.spec_fingerprint.
pending_target/progress/last_eval_tick/overrides/history в эту existing
проекцию не входят. None у spec_fingerprint сохраняется, tombstones не
фильтруются. Это точная existing projection, без нового domain state типа.

Producer до WS cutover — existing regionStateSnapshot.load_region_state_snapshot
на operation boundary; после cutover — IWorldStateRead.read → existing
RegionQuery/RegionResult family → WorldRegionAdapter → get_by_world и
state_from_row. Требуется полный world-scoped read, включая tombstones,
не get_many по уже известным/попавшим в тайл UID (WS §7, WS-0A §8.1).
Existing regions/regionStateSnapshot.py остаётся единственным owner этой
projection: при WS cutover async loader получает read capability вместо repo
и делегирует существующему RegionState → StateSnapshotEntry mapping там же;
operation owners и WS adapter не копируют projection. Mapping закрывается
readonly backing до передачи workers. Один Found-пустой результат означает
успешно прочитанный пустой store; Missing/UnsupportedOperation/storage error
не превращаются в пустую mapping. Чужой world отвергается на read/mapping
boundary; partial selected-UID result не принимается за полный read.
Target WS signature существующего loader:
`async load_region_state_snapshot(*, read: IWorldStateRead, world_uid: str)
-> Mapping[str, StateSnapshotEntry]`. Внутри один WS read полного world scope;
успешный payload содержит existing RegionState POJO. До атомарного WS cutover
сохраняется existing repo signature; dual repo/read fallback не вводится.

**Точный параметр и method ledger (target PC-11.3/11.5/11.6b).** Для всех
перечисленных ниже методов, кроме holders/функций с уже готовым LandcoverInputs,
добавляется/уточняется обязательный keyword-only параметр
`region_state_snapshot: Mapping[str, StateSnapshotEntry]` без default/None.
Остальные параметры и return type сохраняются; обязательность не заменяется
`**kwargs` без проверки вызывающей сигнатуры.
- pack/bake/packMaterializationOrchestrator.py::_materialize_l0_pack — producer
  local ref после successful prepare, до любых internal drains/ветвей L0/L2;
  не новый аргумент public HTTP operation. Один ref передаётся bake и entry.
- materialize/worldSurfaceMaterializationOrchestrator.py::materialize_pack_detailed
  — producer local ref после successful prepare, до detailed delegation.
  Scene/path, запускаемые из light/full operation, получают ref от
  PackMaterializationOrchestrator; второй loader в facade не добавляется.
- pack/bake/worldMapBakeOrchestrator.py::{bake_tiles,bake_tile} → existing
  LightGridBakeContext.region_state_snapshot: тот же обязательный ref.
  Standalone callers готовят его на своей async operation boundary.
- pack/bake/packDetailedBakeOrchestrator.py::{bake,_bake_in_log_scope,
  _bake_location_scope,_bake_wilderness_scope,_run,_refine_tiles} →
  pack/bake/detailedBakeRefine.py::refine_detailed_tiles → тот же ref runner.
- pack/refine/entry/entryRefineOrchestrator.py::{refine_from_entry,
  schedule_chunk_refine,drain_persisted} → scene/path и internal drains.
- pack/refine/chunks/chunkRefineWorker.py::{drain_queue,drain_persisted} →
  refine_queued_chunk. Самостоятельный operation caller загружает свежий ref,
  worker его только принимает. drain_climate_fine не читает region state и
  не получает новый игнорируемый аргумент; enqueue/job schema не меняется.
- pack/refine/fine/fineTerrainRefineOrchestrator.py::{refine_scene_volume,
  refine_rect,_refine_rect,refine_queued_chunk,refine_path_corridor} и existing
  forwarding _refine_rects/_run_refine_phase → runner без reload/copy.
- pack/refine/fine/fineChunkRunner.py::refine_rects →
  pack/refine/fine/fineTilePrep.py::prepare_fine_tile →
  materialize/terrainBatchOrchestrator.py::build_tile_surface_state.
  FineChunkRunner.__init__ лишается region_state_repo и _region_state_repo;
  FineTerrainRefineOrchestrator.__init__ и DI/default stack factories больше
  не принимают/не передают repo только ради runner. Repository dependency
  остаётся лишь у transitional operation loader до WS cutover.
- После PC-11.6b build_tile_surface_state передаёт ref в existing
  LandcoverInputs.state_snapshot через regions/inputs/landcoverInputs.py::
  prepare_landcover_inputs (mandatory state_snapshot из таблицы ниже);
  finePaint.paint_regions_fine получает готовый LandcoverInputs, не второй
  snapshot параметр. Новый holder/поле SurfaceWorkingMaps не вводится.
- pack/read/wildernessRegionReadService.py::outline — local producer один
  раз после membership gate; LandcoverInputs получает тот же readonly ref.
  Render не делает повторного read. Extent-only/absent пути loader не вызывают.

WS read contracts и существующие POJO — SoT формы данных; приведённый ledger
фиксирует лишь acquisition/projection и parameter thread-through. Повторный
freeze уже определённых полей не является дополнительным design gate PC-11.

| Метод / существующая функция | Target вход → выход / граница |
|---|---|
| landcoverInputs.prepare_landcover_inputs | topology: WorldTopology, grid: SurfaceGridSettings, working: SurfaceWorkingMaps, state_snapshot: Mapping[str,StateSnapshotEntry], anchor_specs: tuple[AnchoredRegion,...] → LandcoverInputs; closure fine→macro и collect_facts, без World/pack reads |
| LandcoverMaterializer.load_declared / LandcoverMaterializer.load_anchor_specs / LandcoverMaterializer.autoresolve_specs / LandcoverMaterializer.collect | LandcoverCollectContext + existing policy → existing ResolvedRegion collections; signatures не принимают pack context |
| LandcoverMaterializer.materialize / LandcoverMaterializer.claim_index | Existing resolved geometry/scale → footprint/index; domain raster operations, не canvas write |
| LandcoverLightAdapter.apply (target, existing planned pack landcover/apply.py) | Pack canvas + готовый footprint/spec + pack ctx → canvas write через existing apply_region/apply_terrain_footprint; без region selection |
| LandcoverContributor.apply | Compose + pack ctx → собрать domain context/делегировать collect/materialize/apply; не profile resolve, bounds policy или world maps |
| finePaint.paint_regions_fine | Existing fine/parent inputs + готовые LandcoverInputs и LandcoverCollectContext; bundle/locations для фабрикации bake context больше не принимает; background profile lookup через переданный climate view |
| regionOutline.render_region_outline | LandcoverInputs, LandcoverCollectContext, region_uid → existing outline или None; pack context не создаёт |

Topology input для preparation: operation owner передаёт доменный WorldTopology
macro-scale. В PC-11 разрешено собрать его из уже resolved mode/bounds у
границы подготовки domain inputs через existing WorldTopology constructor;
neighbor/canonicalize и macro→fine принадлежат WorldTopology и existing
fineTopology.fine_topology. Не вводить topology planner в composition и не
требовать чтения через water payload. Режим/границы/scale берутся из inputs
одной операции, без повторного запроса источника на каждый fine tile.
Конкретное получение mode/bounds на entry остаётся existing source capture
contract; snapshot CRUD при этом не вызывается и не симулируется.

WildernessRegionReadService.outline (target async): existing проверка baked membership →
SurfacePlanningEntry.capture_view/prepare_captured → готовые LandcoverInputs/
LandcoverCollectContext → regionOutline.render_region_outline. Для baseline
сохраняется existing full prepare; оптимизация до subset envelopes не вводится.
Ранняя проверка membership — явное исключение из общего порядка LOD-read:
это debug selector по уже baked индексу, а не gameplay cell/volume read.
Нет pack или region_uid в индексе → прежний None, без capture/prepare,
projectors и region-state read. Для найденного UID подготовка metadata/inputs
выполняется до render; не найденная в текущих inputs геометрия по-прежнему
даёт RegionOutlineStaleError. Render вычисляет outline для ответа, не создаёт
и не публикует материализацию L0/L2. Отсутствие в baked индексе не является
командой materialize/refine. Проверки обоих порядков заданы в PC-11.1-E.
Pack membership/ошибки RegionOutlineStaleError остаются pack read обязанностью,
render не проверяет наличие pack. В подготовку inputs входит existing region
state read boundary: WildernessRegionReadService получает injected
IRegionStateRepository и делегирует existing
regionStateSnapshot.load_region_state_snapshot ровно один раз. Сам сервис
не реализует SQL/state mapping. API map.get_wilderness_region_outline делает
await service.outline; DI обновляется атомарно в PC-11.6b. Отсутствующий repo
не заменяется {} fallback; конфигурационная ошибка явная. Existing
load_region_state_snapshot optional-repo semantics для других callers этим
контрактом не переписываются. Async caller diff входит в ledger PC-11.6b.
DeclaredRegionEditor.reconcile создаёт FactConsumerContext(cells=(), climate=None,
terrain=None, hydrology=None); surface planning ради declaration edit не запускает.
StateChangeConsumer.evaluate получает context через RegionEvaluation от caller,
не self-capture. Runtime simulation source/fact acquisition вне PC-11, новые
входы симуляции не добавляются; existing consumer tests исполняют typed context.

**E. LOD entry и шов snapshot TODO: не второй CRUD.**
Целевой общий вход к состоянию — IWorldStateRead.read, реализованный тем же
WorldStateService, что IWorldStateCrud. Переход к нему, concrete backend
adapters и class ledger находятся в world-state-crud-transition.md. Existing
pack/patch classes ниже — backend этой общей реализации, а не альтернативный
публичный CRUD. PC-11 не добавляет самостоятельно ещё один общий интерфейс;
Порядок согласован мастером 2026-10-26: сначала WS-0/WS-0A замораживают
read DTO/capabilities, errors и caller ledger для surface/region/climate;
существующие POJO и уже определённые WS contracts переиспользуются по
PC-11.1-D, повторное проектирование их полей не требуется. Freeze здесь —
проверка покрытия выбранных reads и привязка producer/consumer к WS-контракту.
Затем PC-11 выполняется с согласованными входами. Pure factories/working
views не ждут snapshot runtime. Подключение общего read port — один
согласованный WS-3 cutover тех же boundaries PC-11.3/11.5/11.6b после готовности
WS-1 и read implementation WS-2a; второй последующий entry API не строится.
Это dependency/integration gate, а не разрешение объединить все PC-11 шаги
в один кодовый заход. Каждый шаг сохраняет свою приёмку; на каждом
переключённом consumer остаётся один источник, с parity/typing проверками.
WorldSurfaceMaterializationOrchestrator.materialize_pack_light/full/detailed
остаются explicit operation facades. EntryRefineOrchestrator.refine_from_entry
отвечает за scene/path запрос; FineTerrainRefineOrchestrator — за refine
запрошенного scope. Для gameplay LOD-read owner сначала получает metadata,
затем делегирует проверку фактического наличия материализации existing pack
read API; outline имеет явное early-return исключение по PC-11.1-D. Разделение
read/write уже нормативно задано docs/tz_world_pack_storage.md § WP-20/WP-13:
MapCellService — existing cell/patch CRUD; MapCellService.get_scene_volume
делегирует pack read, MapCellQueryFacade.get_cell/get_scene_volume читает готовые
слои через MapCellQueryFacade._layers_at с L0 fallback и patch merge, без generate.
WorldPackReader.chunk_exists/read_wilderness_chunk проверяет/читает L2,
WorldPackManifest.chunk_ref даёт metadata; PatchStoreService.upsert_patch и
MapCellService.save_pass записывают дельты, не заменяют pack на read.
detailedBakeScope.wilderness_tiles уже пропускает complete тайлы (resume);
EntryRefineOrchestrator.refine_from_entry — explicit write, не query cache miss.
Пропуск отдельных существующих chunks в incomplete tile/entry и auto-resume
нельзя объявлять реализованными: incremental skip имеет existing backlog WP-28.
PC-11 сохраняет эти правила и cutover inputs, не создаёт второй read CRUD или
PackMaterializationInspector с provenance/status schema. Snapshot freshness
и STALE/UNVERIFIED не являются новым блокером PC-11. Existing publication guards
и явно заданные domain invalidation/patch правила этим не отменяются.
**Method/caller ledger read и write (уточнение 2026-10-26).**
- Gameplay read: MapCellQueryFacade.get_cell/get_cells/get_scene_volume и
  _layers_at остаются canonical merged-read backend WP-20. Подготовленные
  metadata → lookup существующих слоёв → region overlay/patch merge/L0 fallback;
  missing сохраняет existing read semantics, не вызывает refine. PC-11 не
  добавляет capture/prepare на каждый cell read и не переводит эти backend
  методы в public CRUD. Их общий application read-entry и перенос внешних
  callers принадлежат WS-3/WS-4 по WS-плану.
- Debug outline: WildernessRegionReadService.outline — read-owner cutover
  PC-11.6b. Membership gate → при отсутствии None без planning; при наличии
  один capture/prepare → один region-state read → domain inputs → render;
  при отсутствии matching geometry RegionOutlineStaleError. Ни write/refine,
  ни pack publication в этом read нет.
- Explicit write: WorldSurfaceMaterializationOrchestrator.materialize_pack_*
  и EntryRefineOrchestrator.refine_from_entry получают запрос scope/LOD,
  готовят/получают planning inputs → применяют existing scope/parent-light/
  materialization gates → делегируют bake/refine → existing publication guard
  и publication у operation owner. Наличие read cache miss само по себе этот
  путь не вызывает. Missing parent light сохраняет existing error; complete
  tile skip и отсутствие incremental chunk skip остаются прежними.

Обязательный TODO(snapshot) ставится при cutover PC-11.6b в
WildernessRegionReadService.outline рядом с membership/metadata boundary,
до early return, чтобы обозначить и отсутствующий результат. Точный текст —
из начала PC-11, ссылка на `.cursor/plans/world-state-crud-transition.md`, §7.
Он не обещает будущий порядок snapshot lookup: его и missing semantics
определяет отдельный WS/snapshot design. При последующем WS cutover TODO
переносится в общий application read-owner с записью в caller ledger;
дублировать его в low-level readers, всех callers или write/refine не нужно.
Snapshot CRUD не содержит materialize метода, а LOD entry не реализует
snapshot create/update/delete.

Проверки контракта отдельно для read/write: gameplay missing/L0 fallback/patch
precedence без вызовов compute/refine; outline absent — None и ноль capture/
prepare/projectors/state reads, present — один prepare/state read и render,
stale geometry — прежняя ошибка, без pack writes; explicit write — existing
scope, parent-light error, complete-tile skip и publication guard. Outline
render не запрещается тестом «no compute»: запрет касается bake/refine и
записи материализации, а не вычисления геометрии read-ответа.
Объект/chunk/fine_cell scope для будущего общего CRUD не означает добавление
новых public fine_cell entry routes и rewrite физического chunk storage в PC-11.

**F. Anti-pattern gate и промежуточная приёмка.**
- Review каждой правки проверяет method→owner по таблицам B–E отдельно от
  line count. В entry/adapters нет imports внутренних hydrology buffers/jobs,
  climate tier kernels или region scorer и нет новых свободных helper-сирот.
- PC-11.2: factories/views и accessor thread-through, old boundary временно
  делегирует новым factories; snapshot API нет. PC-11.3: атомарная передача
  bundle+working refs через existing callers; consumers сами их не строят.
- PC-11.5: typed facts/domain input preparation; PC-11.6a: pure symbols/context;
  PC-11.6b: caller/adapter cutover. После каждого этапа исполняются затронутые
  regressions/typing, следующий этап не служит оправданием сломанного состояния.
- PC-11.7 удаляет compatibility fields/aliases только после исполняемого
  caller ledger. PC-11.8 проверяет no-second-truth, no-eager-materialize,
  read существующей материализации по WP-20, method ownership и TODO(snapshot)
  отдельно; snapshot freshness и incremental skip не входят в этот cutover.
- Числовой baseline, patch precedence, parent-light SoT и domain state writer
  не меняются архитектурным переносом. Возможный baseline delta требует
  отдельной записи/приёмки, не объясняется «новым CRUD».

**Папки и порядок размещения.** Сначала согласовать карту и переносы, затем
сигнатуры. Новые root modules в переполненных папках не добавлять:
- composition 4→5; contracts 3→4 (surfaceWorkingMaps.py — только DTO трёх refs);
  climate/planning 4→4, terrain/planning 3→3, hydrology/planning 2→2.
  Request working views принадлежат materialization, поэтому у каждого домена
  новый generators/{climate,terrain,hydrology}/materialize/ leaf = 2 файла
  (init + соответствующий *WorkingFields.py), а не добавление в planning owner.
- regions 8→8, factConsumers 5→5; новый regions/inputs = 2 файла с init.
- contributors 10→7: existing landcover.py → landcover/contributor.py;
  landcoverInputs.py переносится по owner'у в regions/inputs, pack helper удаляется;
  landcoverBackground.py разделяется: selection → regions/coverageBackground.py,
  canvas application → landcover/background.py. Новый landcover leaf = 4 файла
  (init/contributor/apply/background); generator landcover/apply.py переносится
  в этот pack leaf, generator landcover 9→8. LandcoverLightAdapter делегирует
  domain materializer и связывается с pack-owned mask execution runner.
- masks 13→11: runMaskDomain.py/applyFootprint.py уходят в
  pack/bake/lightGrid/maskDomains/ (3 файла с init); чистый default_collect
  выделяется в masks/collection/ (2 с init). Не оставлять pack writer/runner
  в общем masks namespace. Generator imports идут на pure collection/geometry,
  pack callers — на pack-owned execution/writer. Все callers обновляются атомарно.
- dataModel/spatial/grid 5→6; generators/coordinates 11→11, новый light/ = 2;
  LightGridScale/coordinate functions не копируются, imports raster/context
  переводятся на canonical owners с сохранением symbol identity.
- materialize 11→11, pack/bake 16→16, lightGrid 11→11, mapCells 6→6;
  новый mapCells/imports НЕ создаётся — z-slice API удаляется (мастер).
Предупреждения по >5/переполненным папкам выданы в чат. Перед кодом сверить
counts повторно; новые файлы только по указанным доменным leaf paths.

**После карты — конкретные пробелы на её стыках:**
1. Climate owner: полное множество resolved profiles для local/custom anchors
   не гарантируется текущими frozen payloads. Здесь выбрать явный source/
   revision contract; composition/facts не должны скрывать пробел live fallback.
   **РЕШЕНО (2026-10-24, мастер): вариант A — request-scoped resolve.**
   `ClimateWorkingFields.profile_for_key(zone)` — единственный accessor:
   сначала `climate_base.profiles` (frozen, покрывает default_zone + poles),
   при miss — `profile_for(world)` через climate registry; memoized один раз
   на request. Frozen payload schema и fingerprint НЕ меняются. Контракт:
   lookup обязан покрывать anchor-зоны И зоны клеток (landcoverBackground
   резолвит profile по cell zone из wire id), не только anchors.
   Семантика «профиль по живому реестру на момент запроса» сохраняется;
   composition/facts не выполняют свой resolve.
2. Request entry → consumers: выписать минимальные typed signatures/ref ownership
   и lifetime domain indexes. Решить, нужен ли контейнер refs, по callers;
   не добавлять туда операции или поля других владельцев «для удобства».
   **РЕШЕНО (2026-10-24, мастер): aggregate refs.** Flat контейнер
   `SurfaceWorkingMaps{climate, terrain, hydrology}` строится один раз на
   request entry рядом с bundle и передаётся параллельно ему; это контейнер
   views без методов-доступа к World и без domain logic. Однодоменные
   consumers (climate bake) могут принимать свой working field напрямую.
   Фактура: `classify` и `PackTilePlanner` не читают поверхность вообще —
   extent проверяется у request entry (capture view → NoExtent check), НЕ полный
   prepare; `outline` потребляет тот же LandcoverInputs/scale контракт,
   что L0/L2. Lifetime: request-scoped; drain в последующих запросах
   получает свежий bundle+maps с entry того запроса.
3. Z-slice: production callers save_z_slice при текущей проверке не найдены.
   Явно выбрать сохранение import API с указанным owner либо удаление мёртвого
   метода без создания неиспользуемого нового сервиса.
   **ФАКТУРА:** route `generate_z_slice_route` удалён в 803ff40a при переходе
   на pack/parent-light; `save_z_slice` — сирота с нулём callers, запись шла
   в legacy map_cells в обход pack.
   **РЕШЕНО (2026-10-24, мастер): удалить.** `save_z_slice` и
   `generate_z_slice` сносятся в scope PC-11.4; `terrainSliceImport.py`
   и leaf `mapCells/imports/` НЕ создаются. Атомарно с удалением из
   `TerrainBatchOrchestrator` уходит dep `MapCellService` (конструктор —
   generator-only) и dep `planning`/`capture` (вместе с переносом
   `plan_bootstrap_tiles` на facade).
4. Migration edges: полный ledger outline/completeness/road/settlement/scripts,
   символы координат/масок и canonical encoding/import identity; никакой правки
   DAG nodes без отдельного gate. Authoritative guard re-capture сохраняется.
   **РЕШЕНО (2026-10-24, мастер): ledger принят как полный** —
   `passes/surfaceTerrainContext` (compat entry), `bakeContext.surface_planning`,
   `packCompletenessClassifier` (extent-probe only, ctx не читается),
   `packTilePlanner` (unused param, `del surface_ctx` уже в коде),
   `worldMapBakeOrchestrator` (surface_ctx args + to_legacy_context + hist),
   `packMaterializationOrchestrator` (to_legacy_context → planner),
   `worldSurfaceMaterializationOrchestrator` (preview probe),
   `wildernessRegionReadService.outline`, `factConsumers/context.py` (surface),
   `surfacePlanningAssembler` (to_legacy_context/prepare_captured_context),
   `surfacePlanningView` (re-export), `planning/legacy/surfaceTerrainContext`;
   non-production: `smoke_hydrology_hy12.py`, fixtures в `tests/planning/
   consumers/test_l0_l2.py`. Других потребителей не существует.
Эти пункты уточняют **связи уже назначенных владельцев**, а не являются поводом
вернуть всё в общий helper. Изменение payload schema требует явного решения о
version/fingerprint/encoding последствиях; cache/state/parent-light SoT прежние.
Проверка: ownership/import review этой карты, затем закрытие четырёх стыков,
  точные signatures/caller ledger и нормативный diff перед реализацией.
Done: карта владельцев/папок принята; на каждом стыке выбран контракт без
  скрытой чужой операции. Никакой новый общий класс не вводится автоматически.
  Стыки 1/2/3/4 решены мастером 2026-10-24; остаётся приёмка карты и
  нормативный diff точных signatures перед кодом.

**Закрытие оставшихся замечаний review (2026-10-24; решения для PC-11.1).**

**R1 — SurfaceWorkingMaps: owner, файл, поля и lifetime.**
- Owner — surface request composition, слой application; точный файл
  `backend/app/application/worldData/planning/contracts/surfaceWorkingMaps.py`.
  Это не dataModel/cached plan: domain views содержат request-local state.
- `@dataclass(frozen=True, slots=True)` с ровно тремя полями:
  `climate: ClimateWorkingFields`, `terrain: TerrainWorkingFields`,
  `hydrology: HydrologyWorkingFields`. Контейнер не хранит World, копии maps,
  bundle или дублирующие domain defaults; методов resolve/lookup/project нет.
  Frozen означает неизменяемость refs, а не запрет private memoization внутри
  climate view. Объект не сериализуется в pack/canonical plan cache, не получает
  schema id и не меняет frozen payload/fingerprint контракты.
- Lifetime DTO относится к исполнению запроса materialization. Создание
  request views не создаёт snapshot мира и не материализует его историю;
  DTO не хранит последовательность snapshots и не выбирает latest/as-of.
- `SurfacePlanningEntry` в existing planned composition/surfacePlanningEntry.py
  вызывает каждый domain projector один раз, создаёт DTO и возвращает его
  рядом с тем же bundle. Весь entry/refine/drain одного запроса переиспользует
  эти объекты; consumer их не пересобирает. Другой запрос создаёт новые views,
  memo/lock и DTO даже при HIT frozen planning cache. Domain-specific consumer
  вправе получать только свой field, без лишних трёхдоменного DTO/bundle.
- Folder counts: contracts 3→4, composition 4→5; новых framework/owner classes
  сверх карты нет. Проверки: один вызов каждого projector на N tiles, object
  identity при передаче через callers, новые request objects при cache HIT;
  import check запрещает World/registry/pack IO в DTO module.

**R2 — extent-probe: единственный owner и результаты каждого входа.**
- Owner — `SurfacePlanningEntry`, файл
  `backend/app/application/worldData/planning/composition/surfacePlanningEntry.py`.
  Его `capture_view(...) -> SurfacePlanningView` делегирует existing capture
  с теми же required source inputs; `extent_status(view: SurfacePlanningView)
  -> SurfacePlanningViewKind` читает READY/NO_EXTENT уже captured view.
  На запрос один capture, не capture плюс повторный capture ради probe.
- capture_view готовит входы операции через существующий capture API;
  это не операция создания нового snapshot мира. Выбор актуальных метаданных
  последовательности snapshots и их восстановление принадлежат отдельному
  треку. Здесь не вводятся traversal/replay истории или snapshot manager.
- Extent-only путь не вызывает assembler.prepare/PlanningService/providers,
  domain projectors, создание SurfaceWorkingMaps, collect/materialize или IO
  публикации. Capture diagnostics проходят существующую request-report boundary
  ровно один раз; probe не ослабляет validators и не создаёт synthetic view.
- Materialization использует отдельный метод entry
  `prepare_captured(view, *, world, wait, resolve_ctx)
  -> tuple[SurfacePlanBundle, SurfaceWorkingMaps] | None` на том же view;
  `world` нужен только для binding принятого climate live resolver. NoExtent
  остаётся None/require error по виду внешней операции. Captured view остаётся
  доступен operation owner'у для existing authoritative publication guard.
- Bootstrap preview: facade сначала получает extent status от entry.
  NO_EXTENT → прежний `ValueError("surface terrain context unavailable")`,
  debug route сохраняет HTTP 422. READY → pure PackTilePlanner.plan без
  surface_ctx, bundle/maps или planning. Сам planner не вызывает probe/capture;
  его direct-call результат [] при отсутствии bounds не переопределяется.
- Completeness: отсутствующий manifest или пустой manifest.tiles → прежний
  `absent`, до capture/probe. Для непустого manifest read request boundary
  (`PackLoadingProgressFacade`, включая его standalone classifier callers)
  получает probe у entry: NO_EXTENT → `partial`; READY → обычная классификация
  light/full/detailed. Classifier не делает self-capture и не вызывает prepare.
  Его `extent_status: SurfacePlanningViewKind | None` — явный вход: None
  разрешён лишь в ветке absent, при непустом manifest отсутствие status —
  contract error, без скрытой подготовки или synthetic READY/NO_EXTENT.
- Проверки: preview NoExtent/READY (включая [] при валидном extent), route 422;
  classifier absent/пустой manifest/NoExtent partial/READY; счётчики capture и
  prepare/build/projectors. Для extent-only prepare/build/projectors = 0;
  absent не делает capture. Старый unused context и новый probe не сосуществуют
  как два канала принятия решения.

**R3 — конкурентная memoization принадлежит только ClimateWorkingFields.**
- Owner/file — `backend/app/application/worldData/generators/climate/materialize/
  climateWorkingFields.py`; никакого process-wide memo, CacheService или нового
  общего cache/single-flight механизма. Lifetime — один request-owned view.
- До запуска workers frozen profile entries подготавливаются domain owner'ом
  по принятому accessor contract. Payloads не мутируются. Все pack/refine
  profile accesses проходят `profile_for_key(zone)`; клиенты не читают memo.
- Один private `threading.Lock` на ClimateWorkingFields защищает целиком
  последовательность lookup → при miss `registry.profile_for(bound_world, zone)`
  → store → return. Frozen hit не читает registry. Конкурирующие вызовы одного
  ключа получают один сохранённый результат; успешный live resolve этого ключа
  выполняется не более одного раза на request. Это обычный короткий sync lookup,
  без await под lock и без глобальной блокировки climate registry.
- Исключение resolver'а не превращается в профиль/None и не записывается в memo:
  lock освобождается, исходное исключение выходит наружу. Следующий вызов может
  повторить resolve; правило «не более одного» относится к успешно сохранённому
  результату. Существующие fallback/logging semantics resolver'а сохраняются.
- Проверки в existing consumer/provider tests: concurrent same-key miss даёт
  один успешный registry call и тот же result object; frozen same-key hit —
  ноль registry calls; разные keys не путаются; resolver failure → нет memo
  entry → успешный retry; два requests изолированы даже с одинаковым bundle.
  Дополнительно serial/parallel climate wire equality и новый запрос видит
  новое live значение для ключа, отсутствующего в frozen base profiles.

Решения R1/R2/R3 входят в следующие подпункты; они закрывают замечания review
о размещении DTO, extent semantics и memo concurrency. Приёмка design для
старта реализации подтверждена мастером 2026-10-26; PC-11 в целом не DONE.

**PC-11.2 — доменные проекции и request-scoped индексы у своих владельцев.**
Зависимость: PC-11.1.
Implementation split (2026-10-26): PC-11.2a — pure domain views/factories,
SurfaceWorkingMaps, SurfacePlanningEntry и prepared climate kernel, без
production caller cutover; PC-11.2b — existing compatibility delegation,
production projection reuse и climate accessor thread-through из тела шага.
Это два последовательных атомарных захода с отдельной приёмкой; состав
родительского PC-11.2 не сокращается, DONE только после обоих подпунктов.
PC-11.2a не меняет runtime read boundaries и не требует новой WS реализации;
PC-11.2b/PC-11.3 сохраняют согласованный WS integration gate PC-11.1-E.

**PC-11.2a — ACCEPTED (2026-10-26, мастер: «Ок» перед PC-11.2b).**
- Добавлены domain-owned ClimateWorkingFields/TerrainWorkingFields/
  HydrologyWorkingFields в утверждённых materialize leafs. Climate frozen
  profiles проецируются один раз, успешные live misses memoized под одним
  request lock, exception не сохраняется. Pole sampling использует один
  existing kernel с prepared Mapping без per-sample index allocation.
- Terrain index берётся только из TerrainPlan (pre-relief); hydrology coarse
  и tile-indexed fine maps — из final HydrologyPlan. Вложенные maps readonly,
  пустые tile results readonly; negative fine coordinates делятся captured
  fine_span через floor division. Ни dry defaults, ни изменение фактов нет.
- SurfaceWorkingMaps — ровно три frozen refs; SurfacePlanningEntry делегирует
  capture/prepare/reporting существующим owners и вызывает три factories.
  Foreign-world/mismatched-bundle отбрасываются до projectors; NoExtent не
  строит views. Новый request создаёт новые views/memo/lock при cache HIT.
- ClimatePlanSampler.sample и legacy ClimatePoleField.sample делегируют тому
  же Mapping-based kernel. Production callers пока не подключены к entry;
  legacy projections/accessor thread-through остаются PC-11.2b, mandatory
  request boundary и region-state lifetime — PC-11.3. PC-11.2/PC-11 не DONE.
- Новые checks в existing consumers/test_wiring.py: factory call counts,
  HIT request isolation, immutable refs/maps, concurrent same-key miss и
  frozen hit, exception/retry, distinct keys, prepared/live sampling equality,
  fine negative tile boundaries, empty readonly results, NoExtent/foreign world.
  Existing typing valid/invalid fixtures расширены readonly/nominal checks.
- Проверки из корня, PYTHONPATH=backend, backend/.venv/Scripts/python.exe:
  `-m unittest discover -s backend/tests/planning/consumers -p test_*.py`
  (68 OK), аналогичные discover providers (129 OK), contracts (69 OK),
  encoding (7 OK). Команда `-m unittest
  tests.planning.consumers.test_wiring.WorkingFieldsTests
  tests.test_pack_climate_sample tests.test_pack_climate_parallel
  tests.test_water_placement_pass tests.test_relief_objects_z
  tests.test_hydrology_hy12_rivers tests.test_pack_bake_modes
  tests.test_detailed_bake_c11 tests.test_region_fact_consumers` — 78 OK.
  Итого 346 уникальных tests (5 новых входят и в consumers, и в regression run).
  Async suites запущены вне Windows sandbox после воспроизведённого зависания
  минимального asyncio.run(asyncio.sleep(0)); зависшие sandbox runs прерваны.
- `node_modules/.bin/pyright.cmd --project
  backend/tests/typing/planning/pyrightconfig.valid.json --outputjson`:
  177 files, 0 errors. Invalid config: 53 diagnostics, exact 51 EXPECT
  code/location pairs, missing/unexpected/foreign=0. AST/import inspection и
  git diff --check OK. Новые классы 4–31 строк; domain leafs по 2 файла,
  contracts 3→4, composition 4→5; WARN по переполненным roots выдан.
  SQL/DAG/backend-start/коммиты/city caches не затронуты. Baseline delta нет.

**PC-11.2b: уточнение compatibility transport (2026-10-26).**
**IMPLEMENTED / VERIFIED (2026-10-26), ожидает приёмки мастера.**
Родительский PC-11.2 реализован; architectural DONE PC-11 и PC-12 этим не
объявляются. PC-11.3/WS read-port integration/region-state lifetime не выполнены.
- `to_legacy_context(bundle, *, working: SurfaceWorkingMaps)` собирает
  собственные mutable copies только из готовых domain indexes; frozen plan
  payloads повторно не проецирует. `prepare_captured_context` принимает
  существующие world/capture dependencies и делегирует entry; новых capture
  instances, повторного capture и альтернативного projector нет.
- Existing passes/surfaceTerrainContext.py получает transitional
  `require_surface_plan_inputs(...) -> tuple[SurfacePlanBundle,SurfaceWorkingMaps]`:
  те же аргументы capture/wait/resolve, один capture → existing entry.prepare.
  Три standalone map routes используют tuple и передают refs дальше.
  `require_surface_plan_bundle` пока compatibility wrapper над тем же путём;
  перенос entry API из passes/удаление fallback — по PC-11.3/11.7, не здесь.
- Mandatory keyword-only `working: SurfaceWorkingMaps` проведён через
  L0/detailed/entry/refine/drain callers и FineTileContext до compute. Climate
  sampling helpers и climate service/tier получают `working: ClimateWorkingFields
  | None = None`; pack callers всегда передают view, live-only callers сохраняют
  прежний default. ClimatePackBakeOrchestrator читает climate/hydro views,
  TerrainBatch берёт fine data по tile indexes, landcover typed observations
  используют те же terrain/hydro maps. Отдельные landcover profile/background
  ownership cleanup и удаление legacy observation channel остаются PC-11.5–7.
- Common WS read port не подключается этим transport change; source acquisition
  остаётся existing. Согласованные WS integration gate, region-state lifetime
  PC-11.3, parent-light/publication guards и следующий ownership cleanup
  сохраняют свои dependencies и не объявляются выполненными.

**Принятая baseline delta PC-11.2b (мастер, 2026-10-26).** Для неизвестного
ключа, уже разрешённого capture в frozen climate profile с fallback values,
pack climate использует именно эти значения. Старый live pole adapter мог
вернуть canonical fallback alias, а следующий weather lookup повторно
разрешал alias через изменённый world registry. Пример regression case:
manual mode без полюсов, default_climate_zone="missing-profile", registry
temperate.base_temperature=42: старый live wire temperature_base=42,
prepared wire temperature_base=12 (frozen fallback); rainfall прежний.
Мастер явно принял 12 из frozen plan. Ни live re-resolve frozen hit, ни
новое alias поле/schema/fingerprint version ради сохранения 42 не вводятся.
Valid-key baseline/порядок стадий/гидрологические unknown semantics прежние;
это отдельная явно принятая delta, не утверждение «baseline delta нет».

**Evidence PC-11.2b (2026-10-26).**
- New production case: один capture/prepare и один вызов каждого domain factory
  на три L0/L2 tiles; reverse tile order; serial/parallel climate wire equality.
  Тест запрещает live ClimatePoleField.sample и profile_for bypass в tier/weather.
  Existing detailed → cold queued → scene/path → queue/persisted drain case
  передаёт один working ref без второго planning/capture/legacy L2 context.
  Baseline coarse/fine climate и fine clamp/hard-corridor cases сохранены.
- `PYTHONPATH=backend`, `backend/.venv/Scripts/python.exe -m unittest discover
  -s backend/tests/planning/consumers -p test_*.py` — 70 OK; те же discover для
  providers — 129 OK, contracts — 69 OK, encoding — 7 OK.
- Итоговый `-m unittest` с модулями tests.test_water_placement_pass,
  tests.test_relief_objects_z, tests.test_hydrology_hy12_rivers,
  tests.test_pack_bake_modes, tests.test_detailed_bake_c11,
  tests.test_pack_climate_sample, tests.test_pack_climate_parallel,
  tests.test_parent_light_refine, tests.test_pack_fine_terrain_refine_parallel,
  tests.test_pack_wp13_entry_first, tests.test_landcover_fine_paint,
  tests.test_open_land_hills, tests.test_region_state_contract,
  tests.test_terrain_hills_registry_cutover, tests.test_wilderness_region_index,
  tests.test_pack_tz_slot_l2_render_e2e, tests.test_detailed_grade_generate —
  174 OK. Итого 449 уникальных tests; async suites вне sandbox по ранее
  подтверждённому asyncio ограничению. Failed intermediate runs из-за старых
  mock/preparation signatures исправлены и заменены указанными final runs.
- `node_modules/.bin/pyright.cmd --project
  backend/tests/typing/planning/pyrightconfig.valid.json --outputjson` —
  181 files, 0 errors. Invalid config: 53 diagnostics, exact 51 EXPECT
  code/location pairs, missing/unexpected/foreign=0. AST всех изменённых
  Python modules и git diff --check OK; изменённые production classes ≤300.
- Новых файлов нет, folder direct counts без роста; WARN по затронутым
  переполненным папкам выдан. Новых Any/raw-dict/cast/synthetic defaults,
  SQL/DAG/backend-start/коммитов, изменений city/location caches нет.
  Hydrology hard-corridor API только расширен с dict до readonly Mapping;
  алгоритм merge не менялся. Source acquisition/revision/publication guards,
  parent light SoT, operation scope и materialization ordering прежние.

Цель: убрать дублирование каждой domain projection и повторные мировые
  allocations/scans на каждом tile, сохранив разделение ответственности.
ТЗ: tz_terrain_generation §Surface planning/cache; tz_map_light_bake
  §Surface planning/cache; настоящий план §6.20/§6.26/§6.31-E/F.
Файлы: domain-owned climateWorkingFields.py, terrainWorkingFields.py,
  hydrologyWorkingFields.py по карте PC-11.1; contracts/surfaceWorkingMaps.py,
  composition/surfacePlanningEntry.py,
  surfacePlanningAssembler.py; TerrainBatchOrchestrator, ClimatePackBakeOrchestrator
  и region fact input builder как consumers этих публичных API.
Контракт: SurfaceWorkingMaps создаётся по R1 PC-11.1; private climate memo
  и конкурентный resolve — по R3 (один request-local lock, failure не memoized).
  Climate owner проецирует только climate inputs, terrain owner —
  pre-relief base, hydrology owner — final coarse/fine outputs. Каждый индекс
  строится один раз на request и принадлежит своему domain view; tile lookup
  использует его без повторного world scan. Composition только вызывает owners
  и передаёт результаты. Consumers не реализуют собственные копии их проекций.
  Индексы — производные рабочие данные текущего запроса, не snapshots мира
  и не отдельный источник актуальности. Построение индекса по уже готовому
  payload не означает материализацию предыдущих snapshots. Шаг не добавляет
  подписку «snapshot создан → materialize» и не запускает перебор истории.
  to_legacy_context до удаления в PC-11.7 может собирать compatibility view из
  этих результатов, но не содержит второй реализации domain projection.
  Нет нового cache/SoT, World reads в pure projectors, synthetic defaults или
  нового planning. Semantic profile resolve остаётся исключительно у climate.

  **Climate accessor thread-through (обязательная часть PC-11.2, review
  2026-10-24).** `profile_for` НЕ остаётся параллельным обходным путём в
  pack/refine контуре. Поимённые call sites, переводимые на working-field
  accessor / plan-based sampler:
  - `pack/climate/climatePackSample.py::resolve_pack_zone_sample` →
    `ClimateGeneratorService.resolve_surface_sample` →
    `generators/climate/tierResolve.py::resolve_tier_sample` — live
    `profile_for(world, …)` per cell заменяется accessor от working fields
    через `ClimateWorkingFields.sample_pole` →
    `ClimatePlanSampler.sample_prepared` с `climate_base.profiles`
    (один kernel в `generators/climate/planning/climatePlanSampler.py`;
    точные методы определены в PC-11.1-C, альтернативной реализации нет).
  - `generators/climate/climatePoleField.py::sample` — live resolve всех
    pole-профилей на каждый вызов; в pack-контуре заменяется plan-based
    sampler через `ClimateWorkingFields.sample_pole`; existing
    `ClimatePoleField.sample` остаётся live-only API для callers без bundle.
    В pack/refine его не вызывают; второй resolve-реализации не создаётся.
  - `landcoverBackground`/`landcoverInputs` `profile_for` — закрывается
    PC-11.5/11.6 через готовый climate view.
  Граница scope: `profile_for` остаётся intra-domain API climate registry
  для live-generation путей БЕЗ bundle (`terrainGeneratorService`,
  `surfacePass`, `heightmapPass`, `columnFillPass`, `mountains/collect`,
  `climateGeneratorService.weather_at_elevation` для не-pack callers) —
  они не мигрируются на working fields; миграция ограничена потребителями
  pack/refine, у которых bundle уже есть. Различие типов
  `ClimateZoneProfile` (live) vs `ClimateZoneProfileData` (frozen
  `ResolvedClimateProfile.values`) фиксируется в контракте accessor —
  недостающие поля решаются domain owner'ом, не обходным resolve.
Проверка: consumers/test_l0_l2.py — baseline/HIT/MISS/order/immutability;
  instrumentation: каждый domain projector вызывается один раз на N tiles,
  свои индексы переиспользуют terrain/climate/facts; нет N world rebuilds/scans.
  Concurrent memo cases R3 обязательны; pyright valid0/negative exact по §6.27. Дополнительно: rg-profile ledger
  подтверждает, что в pack/refine контуре не осталось `profile_for`
  вне working-field accessor; climate wire baseline (coarse/fine) совпадает
  с pre-cutover.
Done: у каждой проекции один domain owner, данные подготовлены один раз;
  composition/DTO не поглотили domain logic и не стали общим mutable blob;
  pack/refine не содержит live `profile_for` обхода — единственный climate
  accessor проведён через вызывающую цепочку.

**PC-11.3 — одна request boundary, обязательный bundle и честные L0 signatures.**
Зависимости: PC-11.1/11.2.
Входной read freeze и WS-3 integration gate — по PC-11.1-E; обязательный
region_state_snapshot и полный lifetime caller chain — по PC-11.1-D.
Цель: удалить self-capture из materialization consumers и разместить entry
  preparation вне terrain generator passes.
ТЗ: tz_terrain_generation §Surface planning/cache; tz_world_pack_storage
  §Bake modes/Parent light SoT; настоящий план §6.27/§6.31-F.
Файлы: planning/composition (точный request-entry owner из PC-11.1),
  generators/terrain/passes/surfaceTerrainContext.py, pack/bake/
  worldMapBakeOrchestrator.py, packMaterializationOrchestrator.py,
  materialize/worldSurfaceMaterializationOrchestrator.py, api/routes/map.py,
  core/container/worldData.py и packs.py, pack/read/packLoadingProgressFacade.py,
  pack/bake/packCompletenessClassifier.py; standalone/CLI callers по ledger.
Контракт: extent-only callers используют probe и статусы R2 PC-11.1,
  без assembler/providers/working maps. require_surface_plan_bundle переносится
  в утверждённую application
  boundary planning/composition, generator pass не является planning-entry API.
  Одна реализация entry capture/prepare, а operation owners делегируют ей и
  сохраняют свои UOW/publication обязанности. L0/L2 consumers требуют готовый
  bundle/working refs; нет optional-bundle → self-capture ветки и DI planning/
  capture ради такого fallback. surface_ctx удаляется из bake_tiles/bake_tile
  и всех callers атомарно; не заменять его новым игнорируемым параметром.
  Подготовка entry выполняется для явного запроса, а не по событию создания
  snapshot. Capture/prepare в этом шаге — существующий transport/planning шов;
  создание, хранение, выбор актуального состояния и свёртка последовательности
  snapshots здесь не реализуются. Prepared inputs относятся к запрошенной
  операции; consumers не получают историю для поочерёдной материализации.
Проверка: consumers/test_no_second_truth.py и test_revisions.py — один entry
  capture/prepare, отсутствие вызовов из consumers; fresh/stale guard и
  exact NoExtent/absent/error semantics R2; light/full/detailed/standalone paths.
Done: один preparation owner вне generators; mandatory inputs у consumers;
  мёртвых аргументов нет; authoritative guard и publication ownership прежние.

**PC-11.4 — разделить три зоны TerrainBatchOrchestrator.**
**IMPLEMENTED / VERIFIED (2026-10-26), ожидает приёмки мастера.**
- `TerrainBatchOrchestrator` оставлен с одной зоной L2 surface/chunk
  materialization: build_tile_surface_state, generate_chunk_cells(_sync),
  refresh_tile_gaps, TileSurfaceState. Удалены мёртвый plan_bootstrap_tiles
  (единственный caller map.py вызывает копию на preview facade) и
  save_z_slice вместе с dep MapCellService; _planning/_capture удалены,
  конструктор — generator-only.
- z-slice цепочка удалена атомарно: TerrainGeneratorService.generate_z_slice,
  build_surface_heightmap (живых callers не осталось) и
  columnFillPass.run_column_fill_single. Новый owner/import module не
  создаётся — решение стыка 3 PC-11.1.
- Bootstrap preview tile sets остаются у WorldSurfaceMaterializationOrchestrator:
  entry extent-probe → NO_EXTENT ValueError → pure PackTilePlanner.plan без
  materialization prepare и неиспользуемого context. Файлы
  worldSurfaceMaterializationOrchestrator.py, pack/bake/packTilePlanner.py и
  api/routes/map.py не менялись — контракт уже выполнялся после PC-11.3.
- DI `terrain_batch_orchestrator()` в core/container/worldData.py возвращает
  `TerrainBatchOrchestrator()` без planning/capture/map_cell_service.
- Boundary закреплён в consumers/test_no_second_truth.py: модуль добавлен в
  transit-path assertion (нет SurfaceTerrainContext/to_legacy_context/
  prepare_captured/surface_ctx/SurfacePlanBundle) и новый
  test_terrain_batch_has_single_l2_zone запрещает map_cells/MapCellService/
  save_z_slice/generate_z_slice/plan_bootstrap_tiles/
  prepare_surface_terrain_context/planning.composition/ImportResult/
  PlanWaitControl в модуле и фиксирует signature `__init__(self, generator)`.
- surfaceTerrainContext.py — только docstring: transitional legacy-context
  producer (до PC-11.6b); prepare/require helpers сохранены для existing
  callers до PC-11.7.
- Проверки `PYTHONPATH=.:tests .venv314/bin/python -m unittest`: discover
  tests/planning/consumers — 71 OK; regression
  test_water_placement_pass + test_relief_objects_z +
  test_hydrology_hy12_rivers + test_pack_bake_modes + test_detailed_bake_c11 —
  59 OK; связанные suites (terrain_hills_registry_cutover,
  landcover_fine_paint, region_state_contract, detailed_grade_generate,
  l0_l2, open_land_hills, parent_light_refine и detailed/pack callers) —
  56 + 81 OK. Единственный failure
  test_container_repository_wiring_and_caller_rollback — pre-existing на base
  (воспроизведён через git stash до diff): окружению не хватает
  [planning.cache]/[planning.execution] конфигурации, не связан с изменением.
- pyright §6.27 — failed prerequisite: node_modules/.bin/pyright и node/npx
  в окружении отсутствуют; зависимости автоматически не скачивались.
- Новых файлов нет; WARN по затронутым переполненным папкам выдан в чат
  (materialize/=11, pack/bake=16, refine/fine=10, refine/detailed=14).
  SQL/DAG/backend-start/коммитов нет. Baseline delta нет.
Зависимости: PC-11.1/11.3.
Цель: оставить классу только L2 surface/chunk materialization.
ТЗ: tz_terrain_generation §Multi-pass terrain skeleton и §Surface planning/cache;
  tz_world_pack_storage §L2 refine module layout.
Файлы: materialize/terrainBatchOrchestrator.py,
  materialize/worldSurfaceMaterializationOrchestrator.py,
  pack/bake/packTilePlanner.py, api/routes/map.py, core/container/worldData.py;
  bootstrap owner existing WorldSurface facade; z-slice удаляется по
  решению стыка 3 PC-11.1 — новый owner/import module НЕ создаётся.
Контракт: plan_bootstrap_tiles принадлежит preview facade и делегирует pure
  PackTilePlanner после entry extent-probe R2 (NoExtent → прежний ValueError),
  без materialization prepare и неиспользуемого context. Planner не получает
  planning responsibility; _planning/_capture удалены из TerrainBatch.
  Фактура 2026-10-24: `TerrainBatchOrchestrator.plan_bootstrap_tiles` —
  тоже мёртвый метод (единственный caller map.py:84 вызывает копию на
  facade); удаляется, а не переносится.
  save_z_slice удаляется вместе с dep MapCellService (конструктор —
  generator-only); generate_z_slice на TerrainGeneratorService удаляется
  атомарно, если не остаётся иных callers. Публичные callers обновляются
  атомарно.
Проверка: bootstrap preview tile sets, parent-light/refine baseline;
  boundary tests и DI checks подтверждают, что TerrainBatch не импортирует
  planning entry или import/persist service и не содержит map_cells.
Done: одна зона L2 в TerrainBatch; bootstrap у preview facade без planning
  в неиспользуемый context; z-slice удалён, живых callers не осталось.

**PC-11.5 — domain-owned факты; contributor adapter только передаёт inputs.**
**IMPLEMENTED / VERIFIED (2026-10-26), ожидает приёмки мастера.**
Варианты решения мастера: 1-A (topology/grid — поля LightGridBakeContext,
заполняются один раз owner'ом при построении ctx, adapter — pure transit) +
2-A (legacy surface/profile_for ветка помечена migration-only и остаётся до
PC-11.7).
- FactConsumerContext получил typed refs climate/terrain/hydrology
  (ClimateWorkingFields/TerrainWorkingFields/HydrologyWorkingFields) как
  dual migration-only канал: инстанс несёт либо их, либо legacy
  surface/climate_profiles поля, без смешивания; legacy поля удаляются
  атомарно в PC-11.7.
- Consumers переведены на domain-owned views: climate.contribute →
  working.climate.local_field.nearest + profile_for_key(zone) лениво на
  клетку (мировая dict-проекция profiles убрана из working path);
  relief.contribute → working.terrain.relief_z; hydrology.contribute →
  working.hydrology.coarse_hydro/coarse_surface_z. Legacy fallback ветки
  сохранены до PC-11.7.
- Новый regions/inputs/landcoverInputs.py — canonical domain prepare;
  после PC-11.5-R актуальный контракт:
  prepare_landcover_inputs(working, state_snapshot, anchor_specs) →
  LandcoverInputs. LandcoverObservations с fine→macro + collect_facts
  подготавливается один раз на request, state snapshot привязывается отдельно.
  prepare_landcover_inputs_legacy — migration-only
  surface канал, удаляется в PC-11.7.
- LightGridBakeContext += topology: WorldTopology и
  grid: SurfaceGridSettings; заполнены один раз operation owners при
  построении ctx: worldMapBakeOrchestrator.bake_tiles/bake_tile,
  landcover/finePaint.py bake ctx, wildernessRegionReadService outline ctx
  (через manifest fine_cells_per_map_cell/world_map_cells_per_tile).
- surface_world_topology(world, locations) добавлен в
  planning/composition/surfacePlanningEntry.py: один world-scoped topology
  resolve на request (bounds=None → ValueError), callers передают готовый
  результат.
- Pack adapter contributors/landcoverInputs.py — thin transit: require
  ctx.topology/ctx.grid + state snapshot → domain fn; без
  world_bounds_from_world, topology policy/bounds resolve и мировых
  dict-проекций в working path. Legacy-ветка (surface_planning +
  profile_for dict) помечена migration-only для outline caller, у которого
  нет working views; surface_bundle без working → осмысленный ValueError.
- Фикстуры обновлены: tests/planning/consumers/test_l0_l2.py (context(),
  parents(), facts-site, bind_frozen_context re-resolve после rebuild
  ctx.world), test_landcover_{contributor,materializer}, test_terrain_merge,
  test_light_bake_cleanup, test_light_grid_compose,
  test_mask_domain_materialize — готовые topology/grid (synthetic
  SimpleNamespace worlds получают WorldTopology напрямую, без world resolve).
- Проверки `PYTHONPATH=.:tests .venv314/bin/python -m unittest`: discover
  tests/planning/consumers — 75 OK; затронутые suites
  (landcover_materializer/contributor, mask_domain_materialize,
  light_grid_compose, terrain_merge, light_bake_cleanup) — 57 OK;
  regression (pack_bake_modes, wp13_entry_first, parent_light_refine,
  fine_terrain_refine_parallel, detailed_bake_c11) — 48 OK; regions
  (fact_consumers, coverage_resolver, coverage_contract, state_change,
  state_contract, state_overlay, wilderness_region_index) — 69 OK.
  compileall app+scripts — чисто.
- Pre-existing на base (воспроизведены через git stash до diff):
  test_container_repository_wiring_and_caller_rollback (не хватает
  [planning.*] конфига окружения) и
  RegionGeometryTests.test_polygon_concave_both_windings_and_explicit_closure
  (tuple vs list в shape.vertices, к diff отношения не имеет).
- pyright §6.27 — failed prerequisite: node_modules/.bin/pyright и node/npx
  в окружении отсутствуют; зависимости автоматически не скачивались.
- WARN folder-composition выдан в чат по затронутым папкам >5 файлов;
  новых файлов в папки >10 не добавлено (regions/inputs — 2 файла).
  SQL/DAG/backend-start/коммитов нет. Baseline delta нет.
Зависимости: PC-11.1/11.2.
Цель: убрать climate/relief/hydro подготовку из pack contributor helper и
  повторный world-scoped resolve на каждом L2 tile.
ТЗ: tz_map_light_bake §Регионы покрытия/§L0/L2 и §Surface planning/cache;
  tz_terrain_generation §Surface planning/cache.
Файлы: pack/bake/lightGrid/contributors/landcoverInputs.py,
  regions/factConsumers/{context,climate,relief,hydrology}.py,
  climate-owned profile producer и composition owner из PC-11.1;
  regions/inputs/landcoverInputs.py и existing LandcoverInputs в
  generators/terrain/landcover/types.py.
Контракт: climate domain готовит climate observations/profiles по выбранному
  контракту PC-11.1, relief/hydro domains — свои observations из frozen refs;
  regions определяет запрос/сбор фактов. Общая boundary только соединяет готовые
  inputs. prepare_landcover_inputs в pack не выполняет world_bounds_from_world,
  собственное определение topology policy/bounds, profile_for или мировые dict
  projections; он становится thin transit либо удаляется. Ограничение связано
  с ролью pack adapter: отдельное получение WorldTopology доменным методом
  для materialization само по себе допустимо. Точный шов задаётся в PC-11.1;
  чтение bundle.water_placement.payload.topology не является обязательным
  решением. Метаданные topology принадлежат домену топологии, не water placement.
  Подготовка общих наблюдений — один раз на request,
  а не «один раз до facts_at на каждый tile». State snapshot writer не меняется.
Проверка: eligibility/facts baseline (включая terrain_base trap, custom/local
  profiles и water extent), resolve/projection call counts для N tiles,
  structural tests отсутствия чужих доменных операций в contributor adapter.
  Проверять владельца операций topology и происхождение inputs, а не запрещать
  разные методы их получения или любое повторное создание WorldTopology.
Done: ответственность и стоимость подготовки наблюдений принадлежат явно
  назначенным owners; pack adapter не содержит доменного resolve.

**PC-11.5-R — исправления ревью a3254409 (разрешены мастером).**
Статус: IMPLEMENTED / VERIFIED, ожидает приёмки мастера. ТЗ: tz_map_light_bake §Регионы покрытия/§L0/L2,
tz_terrain_generation §Surface planning/cache; контракт PC-11.5 выше.
- Цель: request-owned observations вместо N повторных topology resolve и
  fact-context preparation на N L2 tiles; устранить reportArgumentType.
- Класс `LandcoverObservations`: владелец regions, слой application,
  `regions/inputs/landcoverInputs.py`; immutable runtime view готовых topology,
  grid и FactConsumerContext с fine→macro accessor. Не читает World/БД.
- `SurfacePlanningEntry.prepare_captured` создаёт observations один раз из
  captured topology/grid и тех же domain views, что входят в SurfaceWorkingMaps.
  SurfaceWorkingMaps переносит готовый ref; snapshot региона остаётся отдельным
  входом LandcoverInputs и не сохраняется между requests.
- Файлы: regions/inputs/landcoverInputs.py, planning/contracts/surfaceWorkingMaps.py,
  planning/composition/surfacePlanningEntry.py, generators/terrain/landcover/finePaint.py,
  pack/bake/{l0/worldMapBakeOrchestrator,lightGrid/contributors/landcoverInputs}.py;
  shared fixture test_wiring.py и regression/call-count tests test_l0_l2.py;
  tz_terrain_generation §Surface planning/cache — sync нового application ref.
- Контракт surface_world_topology согласован с bounds API; последующее расширение
  всей цепочки до Sequence[NamedLocation] — locations-sequence-contract-done.md;
  working-path больше не выполняет его на каждом tile. Legacy outline до PC-11.7
  сохраняет прежний канал. Полный PC-11.6 cutover в этот fix не входит.
- Новых файлов нет; contributors 10→10 (WARN в чат), regions/inputs 2→2,
  planning/contracts 4→4, planning/composition 5→5.
- Проверка/Done: один observation producer на N L0/L2 tiles и отсутствие
  per-tile topology resolve, fresh refs следующего request, сохранение snapshot,
  eligibility/wire baseline; unittest затронутых suites, pyright valid 0 и
  negative exact по §6.27. Невыполненные проверки указываются явно.
- Evidence: 83 теста (planning L0/L2/wiring, landcover contributor/materializer/
  fine paint, region state contract) + 99 (region index, fine parallel,
  detailed C11, parent light, WP13, fact consumers, light compose/masks/merge/
  cleanup, planning revisions) — OK. Production test включает landcover,
  проверяет один producer на L0 + 3 L2 tiles, запрещает повторный topology
  resolve; отдельный тест — fresh observations следующего request и сохранение
  identity каждого переданного state snapshot.
- Pyright valid: 0 ошибок; negative exact: все 51 помеченных case покрыты
  53 ожидаемыми diagnostics, missing/unexpected отсутствуют. Существующие
  6 устаревших include paths в valid config выдают предупреждения инструмента
  и этим исправлением не изменялись. Backend/DAG/SQL не запускались/не менялись.

**PC-11.6 — убрать landcover dependency generators → pack.bake.**
Зависимости: PC-11.1/11.5 → PC-11.6a → PC-11.6b.
Реализовывать и ревьюить двумя отдельными заходами. Родительский PC-11.6
закрывается только после приёмки обоих; общий scope/owners не меняются.
Цель: L0, L2 и outline используют один landcover input contract без
  фабрикации LightGridBakeContext внутри генератора.
ТЗ: tz_map_light_bake §MaskDomain materialize, §Регионы покрытия/§L0/L2;
  tz_world_pack_storage §L2 refine module layout.
Файлы: generators/terrain/landcover/{finePaint,materializer,types}.py,
  pack/bake/lightGrid/contributors/landcover/{contributor,apply,background}.py
  (перенос existing root modules), regions/inputs/landcoverInputs.py,
  materialize/terrainBatchOrchestrator.py, pack/refine/fine/fineTilePrep.py,
  render/regions/regionOutline.py и read/outline callers по ledger PC-11.1.
Контракт: paint_regions_fine получает подготовленные LandcoverInputs и
  domain-owned materialization scope/context; не создаёт LightGridBakeContext
  и не импортирует pack contributor helper. Инвентаризировать collect/
  materializer transitive deps, чтобы не оставить ту же инверсию уровнем ниже.
  Pure scale/coordinate/collection types и операции переносятся к owners карты
  PC-11.1. Pack runner и footprint writer уходят из masks в
  pack/bake/lightGrid/maskDomains/, canvas apply/background — в pack landcover
  adapter; selection остаётся в regions/coverageBackground. Не оставлять
  инверсию транзитивно в collect/materializer. Исправить surface_planning comment.
Проверка: landcover_fine_paint, region_state_contract, wilderness_region_index,
  outline baseline и structural import checks полного затронутого landcover path.
Done: generator не зависит от pack bake context/adapters; все три входа
  применяют один доменный контракт и тот же state snapshot.

**PC-11.6a — перенос общих контрактов, геометрии и pure collection.**
Статус: **IMPLEMENTED / VERIFIED, responsibility gate PASS (2026-10-26), готов к приёмке мастера.**
Вариант мастера: A — generic MaskSourceCollector[CtxT, SpecT] (узкий
source-протокол); MaskDomainMaterializer удовлетворяет ему структурно,
callers не менялись.
- dataModel/spatial/grid/lightGridScale.py (новый) — canonical owner
  LightGridScale + light_span_for; worldMapCellsPerTile.py re-export того же
  symbol (wire path сохранён), pack/bake/lightGrid/coords.py → re-export
  LightGridScale + light_span_for + coordinate fns, __all__ зафиксирован.
- generators/coordinates/light/grid.py + __init__.py (новый leaf) — canonical
  owner пяти pure fine↔light↔macro fns (fine_to_light, light_to_macro_local,
  light_cell_origin_fine, light_cell_center_fine, fine_to_macro_local); без
  bake policy и pack-типов.
- masks/collection/defaultCollect.py + __init__.py (новый leaf) — canonical
  owner MaskSourceCollector[CtxT, SpecT] (load_declared/load_anchor_specs/
  autoresolve_specs) и default_collect generic по ctx; без pack/bake типов.
  runMaskDomain.py re-export default_collect; merge_declare_over_auto остался
  в masks/mergeDeclare.py; run_mask_domain + MaskDomainMaterializer не
  переносились (PC-11.6b — runner/footprint writer в pack maskDomains).
- generators/terrain/landcover/types.py += LandcoverCollectContext (frozen
  record: world/locations/scale/tiles) — declare-only, signatures consumers
  не переключались; world — domain recipe input, tiles — scope/diagnostics.
- Symbol identity проверена исполнением: old/new import paths дают
  идентичные объекты (is) для LightGridScale, light_span_for, fine_to_light,
  default_collect; callers не трогались (cutover — PC-11.6b).
- Проверки `PYTHONPATH=.:tests .venv314/bin/python -m unittest`: discover
  tests/planning/consumers — 76 OK; затронутые suites (mask_domain_materialize,
  landcover_materializer/contributor, light_grid_compose, terrain_merge,
  light_bake_cleanup, region_rasterizer, region_fact_consumers) — 80 OK;
  regression (pack_bake_modes, detailed_bake_c11, wp13_entry_first,
  parent_light_refine, wilderness_region_index, world_topology) — 63 OK.
  compileall app — чисто.
- Первоначальный запуск не выполнил pyright из-за отсутствия executable в
  том окружении; повторная проверка ниже выполнена локальным pyright 1.1.414.
- WARN folder-composition выдан в чат; итоговые counts в пределах карты
  PC-11.1: dataModel/spatial/grid 5→6, coordinates 11→11 (+light/=2),
  masks 13→13 (+collection/=2), landcover без новых файлов.
  SQL/DAG/backend-start/коммитов нет. Baseline delta нет.
Повторная проверка и исправления для приёмки (2026-10-26):
- Проверены implementation commits 64b5d349/fd79acf6 и фактические тела
  операций, не только import graph. Canonical owners: spatial/grid/
  lightGridScale.py — размерность и локальный rim по Facing; coordinates/
  light/grid.py — пять арифметических преобразований; masks/collection/
  defaultCollect.py — порядок вызовов source loaders и merge; mergeDeclare.py
  — подавление коллизий ключей. Defaults world-map policy остались в wire
  policy; новых policy defaults/fallback в spatial/collection нет.
- LandcoverCollectContext: только world (existing recipe), locations (anchor
  geometry), scale, tiles (scope/diagnostics). Frozen application record,
  пока без consumers. Нет context factory, services, callbacks, canvas,
  plan refs/working maps, topology resolution или snapshot lifecycle.
  Это не копия LightGridBakeContext. LandcoverInputs отдельно несёт готовые
  topology, facts reader, anchor specs и явную state mapping, не capture API.
- Проверена цепочка default_collect → LandcoverMaterializer loaders:
  declarations/anchors дают identity/spec; autoresolve → coverage_registry →
  autoresolve_regions → seedGrid/mergeSublocations/ClaimOwnersIndex даёт
  доменные seed/claim/area, сохраняя существующий pass-local owners cache.
  Эти операции принадлежат landcover/regions/raster, не generic collector.
  В callbacks нет pack run/apply, planning request или repository writes.
- Проверены collect.resolve_collected → regionRevision/regionCoverageValidation/
  coverageResolver: fingerprint authored spec, read-only state overlay,
  REF-W validation и anchor geometry остаются доменными операциями.
  region state не захватывается/не сохраняется; topology не разрешается
  из World. fine_topology — геометрическое масштабирование готовых bounds
  в dataModel/topology, neighbor/canonicalize принадлежат WorldTopology.
- Проверен facts_at через LandcoverObservations → factConsumers climate/
  relief/hydrology: только чтение готовых domain working views и агрегация
  наблюдений. Нет planning/materialize/canvas/SQL или lifecycle snapshots.
  Проверены также source policy/identity, raster noise/density/precedence,
  L0 contributor/input adapter, finePaint, outline, apply/applyFootprint.
  Новой или перенесённой чужой ответственности в PC-11.6a не обнаружено;
  существующее смешение из списка PC-11.6b ниже не выдано за исправленное.
- Исправлена типизация fd79acf6: protocol context контравариантен
  (CtxContraT), у default_collect отдельный CtxT; SpecT инвариантен,
  поскольку возвращается mutable list[SpecT]. Прежняя ковариантность SpecT
  давала reportInvalidTypeVarUse при явной проверке нового модуля.
  key получил Callable[[SpecT], object]. Поведение сборки не менялось.
- Добавлены positive cases structural MaskDomainMaterializer → source protocol,
  contravariant context narrowing и list result; negative cases запрещают
  обратное расширение context, ковариантность mutable spec и чужой context.
  В existing negative case sample_pole(1, 2) явно указаны две diagnostics
  (по одной на GridX/GridY), вместо неявной кратности.
- Identity tests проверяют is всех пяти coordinate fns, scale, span и
  default_collect на old/new путях. Geometry vectors включают отрицательные
  границы, неделимый 1000/32, origin/center и прежний clamp; collection test
  проверяет declared > anchors > auto, skip auto, дубликаты, identity и
  неизменность source lists без pack context. AST-сверка с 64b5d349^:
  scale/coordinates/span и тело collection прежние (нормализовано только
  переименование receiver materializer → collector); методы landcover
  materializer/collect/claim/seedGrid/mergeSublocations не изменены.
- Проверки из корня, PYTHONPATH=backend;backend/tests,
  .venv/Scripts/python.exe -m unittest:
  geometry/raster/mask-domain/landcover/materializer/contributor/compose/
  facts/state/fine-paint/index/topology + canonical codec — 124 OK;
  повтор geometry с новыми identity/vectors и TestMergeDeclare, consumer
  wiring/fingerprint vectors, topology_unrolled_geometry/light_bake_cleanup
  — 72 OK; discover tests/planning/consumers — 77 OK. Группы пересекаются.
  Canonical encoding и фиксированные revision/ref fingerprint vectors прежние.
- node_modules/.bin/pyright.cmd --project
  backend/tests/typing/planning/pyrightconfig.valid.json --outputjson:
  185 files, 0 errors / 0 warnings; новые spatial/light/collection/types
  явно добавлены в include. Negative config: 56 diagnostics на 54 EXPECT
  строках; exact multiset (file, line, rule, multiplicity) совпал,
  missing/unexpected=0. Шесть прежних несуществующих include paths valid
  config дают stderr notices; новые модули реально проанализированы.
- Явно остаётся PC-11.6b: pack runner run_mask_domain/footprint writers
  пока в masks; LandcoverMaterializer.apply → landcover/apply → canvas writer;
  collect/materializer signatures принимают LightGridBakeContext;
  finePaint фабрикует bake context и использует pack background/input adapter;
  outline/read цепочка ещё pack-context based; RegionRasterContext и
  regionRasterizer импортируют pure scale/coordinate aliases через pack path.
  Включая types → regionRasterContext → pack coords, это существующие aliases
  тех же pure объектов, без нового pack execution. Caller cutover не выполнен.
  Отдельный legacy observation channel остаётся PC-11.7, не часть приёмки 11.6a.
- Нерешённых нарушений responsibility gate или блокеров PC-11.6a нет.
  Родительский PC-11.6 и PC-11.6b не закрыты. Код не коммитился.
Зависимости: принятые PC-11.1/11.5.
Цель: подготовить нижележащие pack-free контракты без переключения всего
  L0/L2/outline caller chain в этом же diff.
ТЗ: tz_map_light_bake §Координаты, §MaskDomain materialize и §L0/L2;
  tz_world_pack_storage §L2 refine module layout.
Файлы: dataModel/spatial/grid/lightGridScale.py;
  application/worldData/generators/coordinates/light/{grid,__init__}.py;
  application/worldData/masks/collection/{defaultCollect,__init__}.py;
  existing generators/terrain/landcover/types.py для LandcoverCollectContext;
  old pack/bake/lightGrid/coords.py и masks/runMaskDomain.py только как точки
  re-export переносимых symbols; existing typing/geometry/boundary tests.
Контракт: LightGridScale/light_span_for/coordinate functions и default_collect
  имеют по одному canonical owner из карты PC-11.1. Нижние modules не импортируют
  pack. Старые import paths временно re-export тех же symbols; никаких второй
  реализации, новых defaults, fallback branch или изменения frozen payload.
  Объявление domain context не означает переключения signatures consumers.
  Pack runner/footprint writer пока не переносятся: это PC-11.6b.
  Перенос scale/coordinate symbols не переносит ownership WorldTopology из
  домена топологии. Macro→fine преобразование координат не является replay
  snapshots; domain context не приобретает snapshot lifecycle.
**Обязательный gate разделения ответственности (PC-11.6a).**
  Приёмка проверяет фактических владельцев операций и данных во всей зоне
  влияния реализации: новые и изменённые modules, DTO, helpers, adapters,
  вызываемые callbacks и транзитивные зависимости на затронутых стыках.
  LightGridScale/light_span_for описывают spatial scale; coordinate functions
  выполняют только геометрические преобразования. default_collect и узкий
  MaskSourceCollector отвечают только за сборку/merge источников; доменные
  loaders сохраняют свою ответственность у соответствующих owners. Сам
  default_collect вызывает loaders и потому не заявляется строго pure.
  Общая сборка не приобретает pack execution, canvas/footprint write,
  planning, topology resolve или snapshot lifecycle. LandcoverCollectContext
  несёт только доменный collection scope/recipe; копия LightGridBakeContext
  под новым именем или универсальный контейнер зависимостей недопустимы.
  Антипаттерн: перемещение кода либо сокрытие зависимости за generic protocol,
  callback, context или re-export при сохранении смешения ответственности
  в переносимой операции или его вытеснении в соседний helper/adapter.
  Отсутствие прямого import pack и прохождение тестов сами по себе gate
  не выполняют. Если реализация создаёт, переносит или маскирует такое
  смешение в любой затронутой точке, PC-11.6a НЕ МОЖЕТ БЫТЬ ЗАКРЫТ.
  Существующие зависимости, явно отложенные в PC-11.6b, перечисляются
  отдельно и не считаются исправленными этим шагом; это исключение не
  разрешает добавлять или переносить в них новые чужие обязанности.
  Исправления выполняются в scope PC-11.6a; необходимость архитектурного
  решения или расширения scope фиксируется как блокер приёмки, а не
  обходится скрытым caller cutover или формальным переносом symbols.
Проверка: symbol identity old/new import paths, geometry/raster/collection
  baseline, canonical encoding/fingerprint vectors и pyright valid0/negative exact.
  В diff нет смены L0/L2/outline поведения и caller cutover.
  Обязателен review gate выше: отчёт содержит owners операций и данных,
  проверенные стыки/транзитивные зависимости, найденные нарушения и их
  исправления, отдельно отложенные зависимости PC-11.6b и открытые блокеры.
Done: pure нижние контракты и owners готовы; production поведение прежнее.
  Gate разделения ответственности пройден; нерешённых нарушений и блокеров
  в зоне влияния реализации нет. Без этого DONE/закрытие шага запрещены.
  Это промежуточная приёмка контракта, не закрытие инверсии всего PC-11.6.

**PC-11.6b — разделение domain/pack исполнения и атомарный caller cutover.**
Статус: **IMPLEMENTED / VERIFIED, responsibility gate PASS (2026-10-26), готов к приёмке мастера.**
Зависимость: принятый PC-11.6a. Родительский PC-11.6 ожидает приёмки 11.6b;
PC-11.7 этим заходом не выполнялся. Код не коммитился.

Приёмочный отчёт PC-11.6b:
- DI follow-up (согласовано мастером): WildernessRegionReadService получает
  готовый SurfacePlanningEntry через keyword-only entry, а не assembler/capture.
  Создание entry остаётся existing container.surface_planning_entry(); outline
  только вызывает entry.require_plan_inputs. Snapshot-only service сохраняет
  возможность отсутствия entry; present outline без entry — явная ошибка,
  после прежнего membership gate. Новый orchestrator/интерфейс не вводится.
  Файлы: pack/read/wildernessRegionReadService.py, api/routes/map.py,
  tests/test_wilderness_region_index.py. Проверки: outline/HTTP/state baseline,
  вызов именно injected entry один раз, absent gate и missing-entry error;
  Результат: внедрение entry выполнено, snapshot-only route entry не создаёт.
  unittest test_wilderness_region_index/test_region_coverage_contract/
  test_region_state_contract — 37 OK, включая HTTP 200/404/409, ранний gate,
  injected-entry call/no-construction, missing-entry error и real prepare.
  Planning pyright valid — 210 files, 0 errors/warnings; negative exact —
  58 diagnostics на 56 EXPECT строках, missing/unexpected=0. Шесть прежних
  stale include notices неизменны. Коммитов нет.
- LandcoverMaterializer/collect получают LandcoverCollectContext. Домен
  владеет declarations/anchors/autoresolve, identity, coverage, read-only
  state overlay, claim cache и rasterization. У materializer больше нет
  canvas apply, L0 winners или imports pack. Context сохранил четыре поля;
  services, planning/working refs и callbacks в него не добавлялись.
- Pack-owned LandcoverLightAdapter в contributors/landcover/apply.py
  владеет картой L0 winners и apply_region. Его collect только проецирует
  pack scope в domain context и делегирует; materialize/category/begin
  делегируют прежнему domain owner. Доменная selection не переехала в adapter.
  Contributor собирает готовые inputs, запускает pack runner через adapter,
  передаёт resolved_regions в existing index writer и применяет background.
- run_mask_domain/MaskDomainMaterializer и applyFootprint перенесены в
  pack/bake/lightGrid/maskDomains/. Runner protocol содержит только реально
  исполняемые операции; source loaders остаются отдельным collection protocol.
  masks/runMaskDomain.py сохранил исключительно identity re-export
  default_collect. Других implementations runner/writer по старым путям нет.
- background_key_for_zone теперь принадлежит regions/coverageBackground.py:
  получает готовый profile, не World или pack context. L0 canvas background
  находится в contributors/landcover/background.py. Frozen L0/L2 consumers
  берут profiles из ClimateWorkingFields; existing live legacy ветка L0
  остаётся явно ограничена отсутствием working до PC-11.7.
- finePaint принимает LandcoverCollectContext, LandcoverInputs, parent/fine
  buffers и ClimateWorkingFields. Фабрикация LightGridBakeContext, bundle,
  locations и отдельный snapshot параметр из finePaint удалены. Подготовка
  выполняется в TerrainBatchOrchestrator через existing domain inputs owner;
  fineTilePrep/runner продолжают передавать один operation snapshot ref.
  Новой фабрики/контейнера зависимостей вместо bake context не введено.
- render_region_outline получает тот же domain context/input contract.
  WildernessRegionReadService.outline стал async: baked membership → existing
  SurfacePlanningEntry capture/full prepare → один region-state read → inputs
  → render. Нет membership — прежний None без prepare/projectors/state read;
  нет matching geometry — прежний RegionOutlineStaleError. Repository обязателен
  на present outline path; None не превращается в пустой store. Map route
  передаёт container.region_state_repository() и await-ит outline. Existing
  loader/read-only projection переиспользованы; SQL/publication не добавлялись.
  TODO(snapshot) установлен перед membership gate в read owner по §11.1-E.
- Проверены все production usages materializer/runner/paint/render и
  транзитивные callbacks facts_at → LandcoverObservations → factConsumers,
  loaders → seedGrid/mergeSublocations/ClaimOwnersIndex, collect → revision/
  REF-W/coverage, raster → noise/density/topology, pack apply → shared writer.
  Raster/context imports переключены на canonical spatial/coordinate owners.
  Обнаружена также type-only цепочка FactConsumerContext → old surface entry
  → planning → pack alias: ссылка переведена на canonical legacy DTO, без
  удаления legacy канала и без исполнения PC-11.7. Structural test обходит
  imports, parent package initializers, relative imports и TYPE_CHECKING edges
  из collection/materializer/types/finePaint/raster/coverage/inputs/facts/outline;
  до application pack не доходит ни одна из этих цепочек.
- Topology приходит готовой через LandcoverInputs: L0 adapter передаёт
  existing resolved metadata; L2/outline используют working.landcover.
  Ни domain collection, ни fine paint, ни render не требуют accepted water
  plan, не вызывают placement/topology resolve или snapshot lifecycle.
  Common capture/input projection и frozen payload schemas не менялись.
- Type coverage расширен на весь landcover (включая autoresolve), raster,
  новые pack leaves, coverage/inputs, render/read owner и terrain batch caller.
  Выявленные прежние typing defects исправлены на этих стыках: TerrainKey
  вместо str в seed DTO, явное brand-преобразование authored keys,
  readonly world_uid в RasterWorld и доказанные non-None инварианты.
  Алгоритмы/RNG/порядок выбора/fallback defaults не менялись; suppressions нет.
  Positive fixtures проверяют domain collector и pack adapter structural
  contracts; negative запрещают pack context в domain collect и canvas apply
  на domain materializer.
- Проверки (из корня, PYTHONPATH=backend;backend/tests,
  .venv/Scripts/python.exe -m unittest):
  test_landcover_materializer/contributor/fine_paint/cutover,
  test_wilderness_region_index, test_region_state_contract,
  test_region_rasterizer, test_terrain_merge, test_mask_domain_materialize,
  test_region_fact_consumers, test_region_coverage_contract — 120 OK;
  discover -s backend/tests/planning/consumers -p test_*.py — 78 OK;
  no_second_truth + contracts.test_geometry + encoding.test_canonical_codec +
  light_bake_cleanup/pack_bake_modes/detailed_bake_c11/pack_wp13_entry_first/
  parent_light_refine — 90 OK (группы пересекаются). Фиксированные canonical
  revision/ref fingerprint vectors сохранены.
- Новые boundary tests: одинаковый snapshot ref до L0/fine domain inputs;
  outline передаёт ref результата единственного loader в render без copy,
  mapping readonly; absent membership/no extent не читают state; missing repo
  — явная ошибка. Real capture/prepare/render outline повторно читает state
  и учитывает tombstone при HIT planning cache. HTTP baseline 200/404/409
  и stale index removal после bake сохранены.
- node_modules/.bin/pyright.cmd --project
  backend/tests/typing/planning/pyrightconfig.valid.json --outputjson:
  210 files, 0 errors / 0 warnings. Negative config: exact multiset
  (file,line,rule,multiplicity) — 58 diagnostics на 56 EXPECT строках,
  missing/unexpected=0. Шесть прежних stale include paths дают stderr notices;
  новые/изменённые owner modules явно включены. git diff --check с
  core.whitespace=cr-at-eol — чисто.
- Actual folder counts: contributors 10→7, contributors/landcover=5,
  maskDomains=3, domain landcover 9→8, masks 13→12. Последний count сохраняет
  existing source-collection compatibility module; root masks не расширялся.
  Старые scale/coordinate aliases оставлены для внешних callers и identity
  tests; затронутый domain path ими не пользуется.
- Нерешённых нарушений responsibility gate и блокеров PC-11.6b не осталось.
  Для PC-11.7 отдельно оставлены surface_planning/SurfaceTerrainContext и
  dual observation поля/fallback readers. Общий WS read/snapshot CRUD,
  source-version isolation и snapshot lifecycle не реализовывались здесь.

Цель: применить готовые контракты во всех L0/L2/outline callers и убрать
  generators → pack.bake, включая транзитивные зависимости.
ТЗ: tz_map_light_bake §MaskDomain materialize, §Регионы покрытия/§L0/L2;
  tz_world_pack_storage §L2 refine module layout.
Файлы: generators/terrain/landcover/{finePaint,materializer,collect,types}.py;
  перенос apply.py в pack/bake/lightGrid/contributors/landcover/apply.py;
  contributor/background в том же pack leaf; regions/coverageBackground.py,
  regions/inputs/landcoverInputs.py; masks/{runMaskDomain,applyFootprint}.py →
  pack/bake/lightGrid/maskDomains/; raster/context callers координат;
  terrainBatch/fineTilePrep, render/regions/regionOutline.py и outline service.
Контракт: L0 canvas write/runner принадлежит pack, coverage selection — regions,
  region collection/fine paint — landcover. light/fine/outline используют готовые
  LandcoverInputs/domain context. Caller signatures переключаются атомарно;
  не оставлять новый domain API с production callers старого pack API.
  Все три входа получают нужные доменные метаданные для запрошенной операции;
  ни один не обязан получать topology через water placement. Шаг не добавляет
  материализацию всей последовательности snapshots или пересборку по каждому
  изменению. Region-state snapshot сохраняет свой existing read-контракт и не
  отождествляется с последовательностью immutable snapshots мира.
  Фабрикация LightGridBakeContext внутри generator и stale comments удалены.
  Temporary re-exports PC-11.6a проверяются по ledger: generator больше не идёт
  через pack path; оставленные внешние aliases делегируют canonical symbols,
  не выполняют доменную работу. Legacy surface chain удаляется отдельно в 11.7.
Проверка: L0/L2/outline baseline, landcover_fine_paint/region_state_contract/
  wilderness_region_index, state snapshot и import-graph checks; нет прямых
  или транзитивных imports pack.bake в затронутом domain path. Folder counts
  сверяются с картой PC-11.1, pyright valid0/negative exact.
Done: все callers переведены, domain/pack обязанности разведены по папкам;
  только после этого родительский PC-11.6 допускается к закрытию.

**PC-11.7 — удалить второй канал наблюдений и production legacy chain.**
Статус: **IMPLEMENTED / VERIFIED, responsibility gate PASS (2026-10-27), готов к приёмке мастера.**
PC-11.8 и весь PC-11 не закрыты. Код не коммитился.

Матрица удаления legacy (составлена до удаления symbols):

| Caller/owner | Старый input | Единственный target input | Исполняемый regression case |
|---|---|---|---|
| WorldMapBakeOrchestrator.bake_tiles/bake_tile, L0 logging/context | to_legacy_context, surface_planning | готовые bundle + SurfaceWorkingMaps; logging читает hydrology view, pole field из climate view | planning/consumers/test_l0_l2, test_pack_bake_modes, test_light_grid_compose |
| Landcover L0 inputs/background | surface_planning/profile/live fallback | mandatory working views, existing state mapping и climate.profile_for_key | test_landcover_contributor, test_region_state_contract |
| LandcoverObservations / factConsumers climate/relief/hydrology | surface/maps/profiles dual channel | FactConsumerContext(cells, climate, terrain, hydrology), explicit None=unknown | test_region_fact_consumers, consumers/test_l0_l2 |
| DeclaredRegionEditor.reconcile | FactConsumerContext(None, ()) | cells=(), все domain observations None | test_declared_region_edit |
| StateChangeConsumer / RegionEvaluation | caller context со старой shape | тот же caller-owned context с typed views/None; self-capture не добавляется | test_region_state_change |
| Outline/read | уже typed domain inputs + injected entry | тот же единственный contract, без legacy renderer fallback | test_wilderness_region_index, OutlineReadBoundaryTests |
| Classifier / tile planner / loading progress | уже extent_status / готовый tile scope | сохранить готовые inputs; surface capture/materialize на read не добавлять | consumers/test_request_boundary, test_pack_bake_modes |
| HY12 smoke script | to_legacy_context/coarse_hm | prepared working.hydrology/terrain + captured topology | backend/scripts/smoke_hydrology_hy12.py, replay + baseline acceptance.json |
| Legacy entry regression fixtures и geometry comparisons | prepare/require_surface_terrain_context, legacy type aliases | existing SurfacePlanningEntry.capture/prepare/require_plan_inputs + domain views | consumers/test_wiring, test_water_placement_pass, test_relief_objects_z, test_hydrology_hy12_rivers |
| Compose/facts fixtures | synthetic SurfaceTerrainContext | explicit frozen plans/domain working factories; отсутствующие views=None, без нового универсального DTO | test_light_grid_compose, test_landcover_contributor, test_region_fact_consumers |
| Typing / compatibility tests | old projector/aliases и mutable legacy копии | typed bundle/working results; negative cases запрещают удалённые поля | typing/planning valid/invalid, consumers/test_no_second_truth |

До удаления пройден baseline typed production entrances: 55 tests
(consumers.test_l0_l2/test_request_boundary, wilderness_region_index,
region_fact_consumers, region_state_change). Новые paths каждого оставшегося
caller проверяются до удаления obsolete modules. Совместимость старых symbols
не сохраняется: все in-repo callers переводятся; production shims и aliases
удаляются, исторические записи плана остаются историей. Новых DTO/фабрик,
переносящих legacy агрегат под другим именем, не вводить.

Приёмочный отчёт PC-11.7:
- FactConsumerContext теперь имеет ровно четыре поля: cells, climate, terrain,
  hydrology. Поля surface/local_field/relief_z/hydro/surface_z/climate_profiles
  удалены. Consumers читают только свои domain working views; None остаётся
  unknown. Сохранены sparse-hydro semantics (пустая карта = unknown, sparse
  miss внутри extent = dry), empty-scope и отсутствие partial averages.
- LandcoverObservations строит тот же typed scope; legacy input factory
  удалена. L0 input adapter только передаёт working и operation snapshot.
  В L0 background и climate contributor удалены alternate/live пути при
  отсутствии working. require_working в pack context только требует готовую
  ссылку, ничего не создаёт/не разрешает. Доменные алгоритмы в context,
  pack adapter или entry не переносились; универсального replacement DTO нет.
- WorldMapBakeOrchestrator больше не создаёт legacy maps: logging читает
  HydrologyWorkingFields, pole metadata — ClimateWorkingFields. Bundle
  revalidation сохранена. LightGridBakeContext.surface_planning удалён.
  L0/L2/outline продолжают получать прежние bundle/working/state refs.
- Удалены to_legacy_context и prepare_captured_context, old terrain
  prepare/require_surface_terrain_context module, сам SurfaceTerrainContext,
  planning/legacy/__init__ и alias из surfacePlanningView. Все in-repo test/
  script callers переведены; ни stub, ни compatibility projector не оставлены.
- DeclaredRegionEditor явно передаёт empty cells и None domain observations;
  StateChangeConsumer по-прежнему потребляет caller-owned RegionEvaluation,
  без self-capture/planning. Outline/read использует уже внедрённый entry,
  один state read и domain render; classifier/planner уже typed и не менялись.
  NoExtent/diagnostics HIT/MISS cases перенесены с obsolete shim на реальный
  SurfacePlanningEntry, readonly checks — на actual domain views.
- HY12 script читает готовые terrain/hydrology maps и topology observation,
  не фабрикует coarse_hm/замену удалённому агрегату. Frozen plan schemas,
  manifest IDs, algorithm/schema versions, RNG, region identity и precedence
  не менялись. Expected facts в fixtures сохранены через явные исходные
  profiles/anchors; новый input проверяется собственными expected values,
  а не сравнением двух observation channels.
- До удаления modules исполнены новые пути оставшихся callers: typed facts/
  landcover/entry — 16 OK; water placement/relief/HY12 rivers — 27 OK.
  После удаления: discover backend/tests/planning/consumers — 79 OK;
  region facts/state-change/declaration edit, landcover materializer/contributor/
  fine-paint/index/state, compose/cleanup/bathymetry, light/full/detailed,
  entry-first/parent-light regression group — 151 OK;
  planning/contracts — 71 OK; planning/encoding — 7 OK. Canonical revision/
  ref fingerprint vectors в test_wiring сохранены. compileall app/scripts — OK.
  Команды: PYTHONPATH=backend;backend/tests, .venv/Scripts/python.exe -m
  unittest с указанными existing modules/discover folders; backend не запускался.
- Fresh-process HY12 smoke function с явно внедрёнными existing test planning
  resources: world_test_004 before/after acceptance JSON совпадает полностью,
  replay при HIT совпадает: 25 клеток, 11 water, 10 shore. Два существующих
  warnings cap/duplicate source сохранены. Прямой CLI main без resources
  остановился на прежнем требовании [planning.cache]/[planning.execution];
  production config/defaults не менялись, standalone CLI success не заявлен.
- Production+scripts AST проверяет отсутствие imports/definitions/usages
  удалённых symbols; structural test проверяет ровно четыре observation поля
  и отсутствие surface_planning в bake context. Полная transitive domain
  dependency проверка (включая TYPE_CHECKING/package initializers) проходит.
  Оставшиеся surface_planning()/surface_planning_capture() — legitimate
  container factories, не удалённое поле/legacy observation channel.
- Pyright 1.1.414 valid: 208 files, 0 errors/warnings; actual L0 orchestrator
  явно добавлен в include, deleted module исключён. Negative exact multiset
  (file,line,rule,multiplicity): 65 diagnostics на 63 EXPECT строках,
  missing/unexpected=0; новые cases запрещают все удалённые observation kwargs
  и доступ к old context fields. Шесть прежних stale include notices остались.
- Нормативные descriptions синхронизированы в tz_terrain_generation,
  tz_map_light_bake, tz_terrain_hydrology и tz_world_pack_storage. Исторические
  phase diagrams/backlog descriptions явно отмечены историческими; чужие
  backlog IDs не закрывались. Новых application modules нет; composition=5,
  contracts=4, legacy=0, terrain/passes=8 (было 9), factConsumers=5, inputs=2,
  pack landcover=5. Новых файлов в existing folders не добавлялось.
- Нарушений разделения ответственности и блокеров реализации PC-11.7 не
  осталось. DAG/SQL/data fixtures/WS read/snapshot lifecycle не менялись.
  Общая повторная приёмка PC-11 остаётся отдельным PC-11.8 после приёмки шага.

Зависимости: принятые PC-11.1…11.5 и PC-11.6a/11.6b.
Это capstone миграции, а не ранний cleanup: до его начала новые пути должны
работать, mandatory bundle из PC-11.3 и caller cutover PC-11.6b приняты.
Цель: оставить единственный typed способ передачи фактов и убрать ненужные
  legacy aggregates после миграции всех production callers.
ТЗ: tz_terrain_generation §Surface planning/cache; tz_map_light_bake
  §Surface planning/cache/§Регионы покрытия; настоящий план §6.26/§6.31-F
  (transitional разрешения заменяются этой целевой записью после PC-11.1).
Файлы: regions/factConsumers/context.py и consumers, regions/stateChange/
  contracts.py/consumer.py, regions/declaredRegionEdit.py;
  pack/read/wildernessRegionReadService.py, render/regions/regionOutline.py,
  pack/bake/lightGrid/bakeContext.py, packCompletenessClassifier.py,
  packTilePlanner.py, planning/composition/surfacePlanningAssembler.py,
  planning/legacy/surfaceTerrainContext.py и old re-exports/entry shims;
  остальные surface_planning/SurfaceTerrainContext callers из полного ledger.
Контракт: FactConsumerContext.surface удаляется вместе с legacy fallback
  branches; typed observations — единственный канал, в том числе outline и
  state-change. Допустимое отсутствие наблюдений выражается явно typed
  контрактом, не синтетическим SurfaceTerrainContext. Атомарно убрать
  LightGridBakeContext.surface_planning и production to_legacy_context path;
  obsolete prepare_captured_context/prepare|require_surface_terrain_context
  удаляются после миграции потребителей. Судьба import aliases/compatibility
  tests и всех historical references явно решается в PC-11.1; сохранить shim
  «на всякий случай» без caller запрещено. Не удалить поле, оставив reader,
  и не расширять правки на DAG без его отдельного gate.
Перед удалением составить матрицу для каждого named caller, outline,
  classifier, state-change и scripts: старый input → новый input → regression
  case → отсутствие legacy fallback. Пустой rg сам по себе недостаточен:
  новый путь каждого входа должен быть исполнен тестом до удаления old symbol.
Проверка: production rg/import ledger без legacy consumers и dual-input
  branches; outline/region facts/state-change/light/full/detailed regressions;
  updated typing checks запрещают старый input contract.
Done: production legacy context/projector отсутствует, все callers используют
  единый typed input; нет outline-only fallback или пустых compatibility entry.

**PC-11.8 — повторная функциональная и архитектурная проверка PC-11.**
Статус: **DONE / ACCEPTED (2026-10-27), переход к PC-12 разрешён мастером («Далее»).**

Повторная проверка семи review находок (новое evidence, не прежние 448 tests):

| Находка | Фактический owner / проверенный контракт | Evidence |
|---|---|---|
| TerrainBatch смешивает L0/CRUD/L2 | materialize/terrain/TerrainBatchOrchestrator: только L2 surface и chunk generation; L0 и publication у operation owners | test_terrain_batch_has_single_l2_zone; parent-light/fine-parallel/C11 regressions |
| self-capture и dead surface_ctx | SurfacePlanningEntry: один capture/prepare; refine-chain получает готовые refs | multitile request counter; real detailed/scene/path/queue/persisted-drain test с запретом повторного capture/prepare |
| misplaced require helper | require_plan_inputs в planning/composition/SurfacePlanningEntry; lower callers без entry/planning | test_refine_transits_have_no_legacy_context_or_planning_entry; actual owners добавлены в typing include |
| generator → pack.bake | landcover collect/materializer/fine paint, raster и outline используют domain inputs; pack runner/apply остаются в pack | transitive import test, включая relative/TYPE_CHECKING/package initializers; L0/fine/outline regressions |
| domain operations / world maps в adapter | ClimateWorkingFields/TerrainWorkingFields/HydrologyWorkingFields — единственные domain factories; contributor только передаёт working/state refs | production L0 + 3 L2 tiles + serial/parallel climate: factories=(1,1,1), observations=1; tile indexes readonly |
| dual fact input | FactConsumerContext(cells,climate,terrain,hydrology), None=unknown; legacy symbols/shims отсутствуют | structural fields/import/usages checks; facts/state-change/outline regressions; negative typing |
| три bundle→working projector | composition связывает готовые domain views; LandcoverObservations владеет facts_at; DTO SurfaceWorkingMaps только refs | HIT получает новые request views; concurrent climate memo/failure retry/isolation; request projection counts |

Проверены тела операций, а не только imports: domain factories строят readonly
maps/индексы и climate accessor memo; entry только связывает результаты.
Landcover loaders/collect владеют source merge/identity/coverage/raster;
pack contributor/runner/apply владеют canvas/footprint writes. Callback
facts_at → typed factConsumers не планирует и не пишет; state mapping не
приобретает lifecycle. TerrainBatch потребляет tile-indexed outputs и persisted
parent light, сохраняет fine recipe; не повторяет selection/placement.

Дополнены existing tests, новых modules нет:
- No-eager-materialize: реальный capture/prepare на MISS/HIT/edit с запретом
  L0 bake, L2 surface/refine и pack writes/publication.
- Gameplay read: metadata → chunk_exists → existing fine → merged read;
  соседняя клетка без L2 использует L0, patch имеет приоритет. Capture/prepare,
  refine и writes запрещены; bytes всех pack files до/после совпадают.
- Outline: existing absent membership/present/stale/NoExtent branches, один
  prepare/state read и свежий state при planning HIT. TODO(snapshot) проверяется
  до membership early return, со ссылкой на WS-план §7; в write entry TODO нет.
- Lifetime: один capture/state load на operation с 3 tiles, общий snapshot и
  working ref для внутреннего drain и L0; следующий operation/drain получает
  новый load. Real detailed/scene/непустой path/queued/persisted drains передают
  те же bundle/working/readonly state refs до TerrainBatch и дают тот же wire.
  FineChunkRunner не импортирует state repositories/loader и не читает state.
- Detailed scope сохраняет complete-tile skip, stable order/cap и explicit
  requested tile; без persisted L0 — ошибка. Incremental chunk skip не добавлен.
  Topology проверяется по mode/bounds как world input, не identity с water plan.

Команды из корня (`$env:PYTHONPATH='backend;backend/tests'`):
- `.venv/Scripts/python.exe -m unittest discover -s backend/tests/planning -p 'test_*.py'`
  — 290 OK; после final scope case consumers повторно проверены отдельно,
  итоговый состав planning: consumers84/providers129/contracts71/encoding7.
- `.venv/Scripts/python.exe -m unittest discover -s backend/tests/planning/consumers -p 'test_*.py'`
  — final consumers84 OK (30.929s); дополнительный focused real path/ref test — OK.
- `.venv/Scripts/python.exe -m unittest discover -s backend/tests/cache -p 'test_*.py'`
  — 21 OK. Encoding7 включены в общий planning discover (не tests/encoding).
- `.venv/Scripts/python.exe -m unittest test_water_placement_pass test_relief_objects_z test_hydrology_hy12_rivers test_pack_bake_modes test_detailed_bake_c11 test_parent_light_refine test_pack_fine_terrain_refine_parallel test_wilderness_region_index test_landcover_materializer test_landcover_contributor test_landcover_fine_paint test_landcover_cutover test_region_state_change test_region_state_contract test_region_fact_consumers test_pack_climate_sample test_pack_climate_parallel test_pack_climate_apply test_pack_wp13_entry_first test_map_cell_query_facade test_pack_fine_terrain_read_facade test_pack_bake_finalize test_light_grid_compose test_light_bake_cleanup test_declared_region_edit`
  — 225 OK. Итого final состав 537 tests, повторные запуски не суммируются.
- `node_modules/.bin/pyright.cmd --project backend/tests/typing/planning/pyrightconfig.valid.json --outputjson`
  — 212 files, 0 errors/warnings. Шесть stale include paths заменены четырьмя
  actual owners; ещё два owner paths уже были в include, дублей не добавлено.
- Та же команда с `pyrightconfig.invalid.json`: 65 diagnostics на 63 EXPECT
  строках; exact multiset(file,line,rule,multiplicity), missing/unexpected=0.
  Nonzero pyright ожидаем; JSON диагностики проверены отдельно от exit code.
- `python -m compileall -q backend/tests/planning/consumers` и
  `git -c core.whitespace=cr-at-eol diff --check` — OK.

Sandbox async-запуски остановлены: faulthandler показал зависание Windows
asyncio в socket._fallback_socketpair/accept при создании event loop.
Зачтены только успешно завершённые повторные unittest-запуски вне sandbox.
Ошибочный discover tests/encoding (фактический путь planning/encoding)
не засчитан; encoding реально выполнены общим planning discover.

Baseline delta этого шага **нет**. Принятая PC-11.2b delta unknown climate
profile (frozen fallback 12 вместо live alias 42) сохранена отдельным case;
PC-10 deltas не переоцениваются. HIT/MISS/clear/restart/reverse order,
canonical revision/ref vectors, stale UOW rejection и parent-light disk SoT — OK.
Новых production files/изменений algorithms, RNG, schemas и defaults нет.
Folder counts: consumers6→6 (WARN в чат), typing5→5, composition5,
domain working leaves2, region inputs2, terrain materialize3, fine chunk5.
Проверенные production classes: TerrainBatch160, SurfacePlanningEntry67,
ClimateWorking31/TerrainWorking6/HydrologyWorking28, LandcoverObservations27,
LandcoverMaterializer60, LandcoverContributor13, WildernessRegionRead33,
EntryRefine249, FineChunkRunner102 строк; все <300.
Existing domain landcover8 и pack/read22 не расширялись и не правились.
WS §7 integration freeze сверён: existing read backend не стал вторым CRUD,
snapshot API/lookup/history replay не добавлены; будущие existence/freshness
семантики не заявлены реализованными. DAG/SQL/backend-start/коммитов нет.

Зависимости: принятые PC-11.1…11.7.
Цель: разрешить возврат DONE только после закрытия семи review находок.
ТЗ: перечисленные разделы PC-11.1; настоящий план §6.20/§6.27/§6.31-F.
Файлы: existing tests/planning/consumers/{test_l0_l2,test_no_second_truth,
  test_revisions,test_wiring}.py, typing/planning configs/fixtures, существующие
  regression suites §6.27; evidence и статус настоящего шага/связанных ТЗ.
Контракт: архитектурные инварианты проверяются отдельно от численного baseline:
  single request preparation, один projector на каждый домен, no self-capture,
  no generator→pack.bake,
  no dual fact input/legacy chain, TerrainBatch только L2, owners соответствуют
  class map; existing UOW/revision guards и parent light SoT сохранены.
  Дополнительно: архитектурные проверки затронутых entry/callers подтверждают
  materialization только по запросу, в нужном scope/LOD из актуальных
  запланированных метаданных; нет связи «создать snapshot → materialize» и
  replay всей истории ради одного результата. Не создавать snapshot API или
  lifecycle fixtures ради этой проверки: полноценная проверка последовательности
  и выбора актуального snapshot относится к отдельному треку. Здесь проверить
  существующие no-eager-materialize cases, явный scope/LOD и отсутствие нового
  snapshot orchestration. Проверка topology касается ownership/контракта inputs,
  не object identity с topology внутри водного payload.
  Для gameplay LOD-read проверить порядок metadata → проверка существующих
  слоёв → merged read/L0 fallback по PC-11.1-E, без нового planning на каждую
  клетку. Для outline отдельно проверить разрешённый membership early return
  и present/stale ветки по PC-11.1-D/E. Read не запускает bake/refine и не
  записывает материализацию; вычисление outline для read-ответа допустимо.
  Explicit write/refine проверяется отдельно по своему ledger PC-11.1-E.
  Existing skip complete в detailed bake сохраняется; incremental
  chunk skip/auto-resume не добавляется молча к scope PC-11. Будущую snapshot
  existence/freshness проверку здесь не считать реализованной или проверенной.
  Проверить TODO со ссылкой на WS-план world-state-crud-transition.md §7
  в WildernessRegionReadService.outline у membership/metadata boundary;
  read TODO не размещается в EntryRefineOrchestrator.refine_from_entry.
  Отсутствие snapshot runtime не блокирует PC-11;
  фиктивные lookup/API ради задела запрещены.
Проверка: точные commands §6.27 — consumers/providers/contracts/cache/encoding,
  пять mandatory regressions + detailed_bake/parent_light_refine/fine parallel,
  outline/landcover/state-change/climate; pyright valid0/negative exact;
  HIT/MISS/order/baseline, fresh/stale/no-eager-materialize, request allocation/
  projection counts и folder/class limits.
  Region-state lifetime проверяется отдельно: один load на операцию с N tiles,
  общие refs для scene/path/internal drains, новый read следующего drain-запроса
  и отсутствие repository reads в FineChunkRunner. WS read freeze/integration
  сверяются с PC-11.1-E и WS-планом §7, без второго entry/source path.
  Отчёт содержит фактические команды, результаты и все baseline deltas;
  прежние 448 tests не считать новым evidence.
Done: все семь находок закрыты evidence и приняты мастером; только затем
  вернуть DONE PC-11 и снять блокировку PC-12. PC-12 остаётся отдельной приёмкой,
  а не контейнером для незавершённых fixes.

#### Открытые риски PC-11.x (зафиксированы review 2026-10-24)

Не блокируют старт PC-11.1, но обязаны быть учтены в его карте/стыках
или явно отклонены мастером:

- **R-11.6-scope:** PC-11.6 тянет три связанных переноса (masks →
  maskDomains, разбиение landcoverBackground, LightGridScale → dataModel).
  Если diff перестаёт помещаться в один просмотр — шаг обязан быть
  разбит: перенос контрактов/symbols отдельно от caller cutover.
- **R-outline-input:** целевой источник domain inputs для
  `wildernessRegionReadService.outline` не выписан — сейчас это полный
  capture+prepare восьми envelopes ради одного рендера. Решение — часть
  стыка 2 PC-11.1; «переиспользуем старый ctx» не является решением.
- **R-ledger-completeness:** PC-11.7 доказывает «production legacy
  отсутствует» только если ledger callers полон — включая scripts
  (`smoke_hydrology_hy12.py`), compatibility tests и re-exports.
  Неполный ledger = шаг не закрыт.
- **R-verify-env:** asyncio/socketpair ограничение Windows sandbox уже
  воспроизводилось на planning suites. Если в PC-11.8 оно повторится на
  async suites — нужен признанный мастером способ верификации; молчаливый
  skip не засчитывается как evidence.
- **R-drain-units:** `ChunkRefineWorker.drain_persisted` складывает в
  `processed` chunks и fine-tiles — смешение единиц в одном счётчике.
  Pre-existing, вне семи находок; отдельный мелкий долг, не включать
  молча в scope PC-11.x.
- **R-transitional-permanence:** пока PC-11.7 не закрыт, все dual-каналы
  (`surface_planning`/`surface`, `to_legacy_context`, помеченные
  transitional параметры) — отступление от layer-boundaries, действующее
  строго в scope PC-11.x. Новый код не должен их расширять или
  опираться на них.

**PC-12 — приёмка входного блока (без новых domain algorithms).**
**DONE / ACCEPTED (2026-10-27): мастер разрешил следующий шаг GEO-1 («Далее»).**
Production Container acceptance в existing test_wiring: 8 namespaces → один backend, HIT без build, edit без invalidation → точная downstream closure, clear/restart и workers=1/4 → одинаковые envelopes.
Проверки §6.27 (`PYTHONPATH=backend;backend/tests`, `.venv/Scripts/python.exe -m unittest`): planning discover — 292 OK, cache discover — 21 OK, пять mandatory + parent-light/fine-parallel/outline/landcover/state/climate/entry regressions — 182 OK; compileall и diff --check — OK. Async suites выполнены вне sandbox по причине socketpair из PC-11.8.
Pyright valid — 212 files, 0 errors/warnings; negative exact — 65 diagnostics, missing/unexpected=0. Cases §6.22 покрыты existing suites + новым production-root case; TTL=None по frozen policy.
Baseline delta нет; production/городские/локационные caches не менялись, новых modules нет (consumers6→6, WARN выдан). Переход к нормативному G0 разрешён мастером; activation остаётся G10-A.
Цель: доказать production wiring и отсутствие второго SoT.
Файлы: acceptance tests/evidence с composition root/providers/consumers;
test modules группировать в tests/cache и tests/planning/{contracts,
providers,consumers}, exact suites/commands заморожены PC-0 и file counts
не превышают folder-composition rule.
Проверка: все cases §6.22, generic type-negative checks, coherent refs,
edit/replan closure, L0/L2 запросы, cache clear/restart equivalence,
single-flight/error propagation и existing domain regressions.
Done: PC-0U/PC-0G1/PC-0G2/PC-0I/PC-1C/PC-1T/PC-1R/PC-1H/PC-6W/PC-6S/PC-8C/PC-9A и PC-1…11 приняты,
реальные три доменные группы используют общую
infra, города/локационные caches прежние. Только после этого разрешён
старт основной GEO-1 реализации по отдельной явной команде мастера.

**Граница готовности:** завершённый PC не закрывает автоматически
GAP-SOURCE/FIELD/AREA/SURFACE/OUTCOME нового designed-water target.
Основной GEO-1 использует готовые общие lifecycle/cache/revision contracts
и расширяет domain layouts по согласованным G-steps, не создаёт второй
cache и не переопределяет общий planning API внутри terrain.

### G0 — нормативный контракт
Статус: **DONE / ACCEPTED (2026-10-27), мастер разрешил G0-A («Далее»).**
Синхронизированы tz_terrain_generation/cascade_context/map_light_bake/terrain_hydrology: settings/units/owners, общий policy/zero, priority defaults=1 и единый G10-A switch; baseline до switch явно отделён.
Проверка: сверка с §4/§5.4/§6.8–6.9/§6.29-A…M, локальные ссылки и diff --check. Только документы; production defaults/код не менялись, baseline delta нет. G0-A/G0-S/G0-PT не выполнялись этим шагом.
Цель: закрепить решения и закрыть Q перед кодом.
ТЗ: tz_cascade_context §2–4; tz_map_light_bake §Placement P1/P2/P3;
tz_terrain_hydrology §Declare, SeaLevelPolicy, Procedural sea;
tz_terrain_generation §generate-surface. Добавить точный раздел GEO-1.
Файлы: перечисленные docs; актуализация статусов placement/graph отдельно
от алгоритмов. Контракт: поля/единицы/гейты/области/стратегии/инварианты.
Проверка: согласованный diff ТЗ и отсутствие противоречий каскаду/HY-12.
Done: все входные решения явно записаны, нет неподтверждённых defaults;
в частности, назначены новые domain defaults placement_specificity
в target POJO владельцев seas/lakes; production изменение только G10-A.

### G0-A — фиксация архитектурных стыков и decision call sites
Статус: **DONE / ACCEPTED (2026-10-27), мастер разрешил G0-S («Далее»).**
Актуализированы class map/J01–J15 после PC-12; нормативный §6.16-A фиксирует cascade runtime, SUPPORT resume, validation draft/UOW seam и removal owners, включая WaterBodyPlanner. Код не менялся.
Проверка: AST existing paths/methods, новые target leaf counts, ссылки и diff --check; placeholders на проверенных seams закрыты. G0-S остаётся отдельным шагом, HY-RIV-1/WS — внешними треками.
Цель: убрать архитектурные placeholders до создания новых contracts.
ТЗ: G0, §5.4, §6.8-C3, закрываемые записи §6.13.
Артефакт: нормативные contracts и ledger в документации/плане; это
проектирование, не реализация новых services. Для каждого затронутого
пути указать exact producer → typed input → executor → typed output →
consumer, папку/файл/класс/метод, phase/revision и legacy gate removal step.
Обязательные стыки: admission до geometry без фиктивного PreparedPlacement,
supports/re-evaluation через existing DependencyQueue, context genericity,
source union, dependent boundary caller/result, validation entry point,
snapshot revision/cache и activation defaults/nullable channels.
Обязательный lifecycle §6.20: explicit domain layout output/revision,
edit/replan затронутого набора и L0/L2 consumers по запросу, без повторного
placement в materializer и без eager bake после изменения.
Контракт: расположение §5.4/§6.8-B, направление dataModel←application,
общий engine вне worldData; untouched mechanisms получают явный scope.
Проверка: для каждого OPEN/PARTIAL architecture gap — точная спецификация
либо внешний prerequisite с замороженным interface; нет фразы «выберем
при написании кода». G0-PT/G0-PE/G0-P ждут своих закрытых стыков;
остальные шаги ждут соответствующих им закрытых gaps.
Done: ledger проверяем по реальным production call sites, путь каждого
нового модуля однозначен, необходимые contracts согласованы.

### G0-S — общая planning revision и граница будущего snapshot/patch cutover
Статус: **IMPLEMENTED / VERIFIED (2026-10-27), готов к приёмке мастера.**
В §6.15 заморожены Geo view/capture closure, TLV source/artifact fingerprints, canonical order, dependency invalidation и current/future publication seam; нормативы terrain/patch/snapshot/pack синхронизированы с действующим внешним snapshot-планом.
Проверки: 23 existing revision/codec/capture tests OK; ссылки, AST owners и diff --check. Это design freeze, не реализация Geo capture/restore adapter или snapshot/append-only runtime; future-source equivalence остаётся executable acceptance следующих code steps. Код/SQL/UID формулы не менялись.
Цель: определить change-sensitive generation input без локальной системы
world snapshots и подготовить замену источника общим platform contract.
ТЗ: GEO-1 §6.15, tz_patch_system §Архитектура/Границы слоёв,
tz_world_snapshot §Архитектура/Расположение/World regen,
tz_world_pack_storage WP-1…WP-7 и Read path.
Артефакт до кода: exact typed view/revision payload, canonicalization,
producer/consumer signatures/пути в карте G0-A и invalidation semantics.
Target owner: application/worldData/planning/composition/surfacePlanningAssembler.py::
SurfacePlanningAssembler.prepare_geo; request owner SurfacePlanningEntry,
capture — SurfacePlanningCapture.capture_geo. Legacy terrain/passes/surfaceTerrainContext.py
и prepare_surface_terrain_context удалены PC-11.7 и не восстанавливаются;
hydrology/placement/waterPlacementPass.py; fingerprints — existing
application/encoding/canonicalCodec.py и application/planning/service/planFingerprints.py,
не JSON app.ids.state_fingerprint; доменные view contracts §5.4/§6.3/§6.15.
Контракт: single capture of inputs per compute run; stable identity отдельно
от content revision; будущий adapter общего restored state подключается
на caller boundary. Platform service/patch schemas не реализуются в GEO-1.
Проверка: input edit vs equivalent permutation, cached mismatch, одинаковый
результат двух typed input sources, no-writes preview/no patch IO из generator.
Done: GEO-1 часть GAP-SNAPSHOT закрыта точным контрактом; platform runtime
cutover остаётся внешним треком с явно описанной границей замены.
Prerequisite для G3-R/G8/G10 и downstream fine snapshot delivery.

### G0-PT — typed контракты общего policy
Цель: описать policy cases/effects/results независимо от hydrology.
ТЗ: G0, общий placement policy раздел, §6.8.
Файлы: dataModel/policy/{policySpec,policyEnums,policyDecision,policyFacts,
policyReferences,policyRules,objectAdmissionPolicyDefinition}.py;
typed FieldRef reuse после проверки import boundaries.
Уточнение композиции, согласовано командой «Вынеси» (2026-10-27):
в общем dataModel/policy факты KnownFact/WaitingFact/UnknownFact/FactValue
и проверка immutable values принадлежат policyFacts.py; typed refs и их
протоколы — policyReferences.py; predicates/effects/PolicyRule/PolicyFallback
— policyRules.py; policySpec.py оставляет обе спецификации и их проверку.
Зависимости: facts → references → rules → spec; все остаются в dataModel,
исполнение не добавляется. Обновить все импорты без compatibility re-export.
Папка: 5 → 8 файлов с init (WARN выдан); проверка — существующие runtime
contracts, positive typing и точное совпадение negative diagnostics.
Композиция выполнена: policySpec 384 → 68 строк; contracts 14/14,
positive typing 220 файлов без ошибок; negative 80/80 без лишних/пропусков.
Контракт: §6.8-B/C, без raw DSL/dict conditions, domain enum в engine
и дублирования authoritative priority.
Проверка: типизация rules/effects/FieldRef, конфликты деклараций,
совместимость generic decision с priority и enum mode.
Вход: call-site migration ledger §6.8-C3, включая владельца каждого
gate/decision и границы внешних migration треков.
Done: definitions можно объявлять из разных доменов без нового engine.

### G0-PE — единый исполнитель policy
Цель: разрешать приоритеты и domain-defined cases одним механизмом.
ТЗ: G0 и §6.8-B/C.
Файлы: application/policy/policyResolver.py и shared tests.
Уточнение реализации G0-PE (2026-10-27): общий dataModel/policy/policyBindings.py
владеет PolicySource[M] (проверяемые model/instance/path), PolicyInputs,
PolicyFacts и PolicySupportFact; PolicySupportState в policyEnums.py различает
accepted/pending/disabled/missing/failed/cycle. Это наблюдения caller, не scheduler.
Source model уникален в binding; FieldRef выбирает его по типу. Malformed POJO
проверяется до gates; отсутствующий referenced binding даёт Unknown на нужной
стадии. ObjectAdmissionFacts разрешён только как computed input executor.
application/policy/{policyRead,policyStages,policyResolution,policyResolver}.py
(5 файлов с init): чтение/AND predicates; сопоставление стадии/precedence;
priority/fallback/result assembly; public staged facade соответственно.
Карта application-классов: PolicyReader/ConditionResult → policyRead.py,
StageResult/PolicyProblem → policyStages.py, request-local PolicyResolution
→ policyResolution.py, PolicyResolver → policyResolver.py. Первые records
— промежуточные результаты исполнения; они не создают второго SoT.
Все перечисленные классы — общий policy домен, dataModel хранит frozen данные,
application исполняет. dataModel/policy: 8 → 9 файлов; contracts tests: 2 → 3
(test_policy_resolver.py). WARN по dataModel выдан. Bindings/resume revision
проверяет caller/session по §6.16-A; resolver проверяет waiting/positive/op tag.
Диагностика возвращается в decision для existing report_issues/emitter caller;
исполнитель не создаёт logger и не подключается к production до G10-A.
Контракт: PolicyResolver.resolve(spec, sources, facts, mode=ResolutionMode, resume=None) → PolicyDecision,
rule precedence отдельно от object priority, unknown/waiting явно.
Object SUPPORT resume и operation binding — точный контракт §6.16-A;
повторные cascade/priority/RNG и второй support executor запрещены.
Проверка: разные domains/defaults, case conflicts, hard forbid,
required supports, одинаковый preview/runtime result, без domain imports.
Production acceptance: решение потребляется затронутыми adapters и
writers без повторного domain resolve/override; существующие cascade,
geometry/scoring/material executors не дублируются (§6.8-C3).
Done: domain definitions не имеют своего resolve/evaluate; runtime
fallback логируется существующим emitter/facade по §6.12, без нового logger.

G0-PE IMPLEMENTED/VERIFIED (2026-10-27), isolated до G10-A.
Проверка: contracts 41/41, cascade/placement regressions 77/77;
positive typing 226 файлов без ошибок, negative 85/85 (baseline 80 + 5),
без лишних/пропущенных diagnostics. SUPPORT resume сохраняет priority/provenance;
production wiring и session revision binding остаются у своих следующих шагов.

### G0-P — общая семантика priority=0 в placement P2
Уточнение G0-P по §6.29-J: существующие constructors/root exports сохраняют
baseline; target variants PreparedPlacementV2 (prepared.py), PlacementBatchV2
(batch.py), ResolvedPlacementV2/DisabledPlacement/UnresolvedPlacementV2,
PlacementOutcomeV2/PlacementBatchResultV2 (result.py) используются isolated.
Новые lifecycle/{header,admission,causal}.py владеют PlacementHeader,
PlacementAdmissionInput и PlacementOutcomeRef/PlacementOutcomeStatus (4 с init).
Application lifecycle/{session,outcomes}.py (3 с init) — PlacementSession
(порядок prepare/submit/step), terminal/cause construction соответственно.
Existing DependencyQueue получает deferred preparation API для этой session;
graph/heap/check_candidate остаются общими. Structural geometry protocols
в lifecycle/header.py связывают existing и V2 prepared/resolved contracts.
Root placement imports становятся lazy с теми же именами: это разрывает
цикл placement.common → policy → placement без изменения production schema.
Текущие папки 7/6 файлов (WARN выдан), новые подпапки 4/3.
Integration fix policyResolution.py: выбранный priority-default rule сохраняет
domain_reason также при результате 0; dry explanation не теряется в placement.
Тесты: geo1/contracts/test_placement_lifecycle.py (contracts 3 → 4 файла),
existing typing/planning cases/config; новые модели не экспортируются из root.
Цель: применять отсутствие создания при 0 одинаково ко всем доменам.
ТЗ: tz_map_light_bake §Placement priority/P1/P2 и синхронизация G0;
tz_terrain_hydrology §Coastline priority ссылается на общий SoT.
Предусловие: G0 назначил положительные domain defaults
placement_specificity в POJO владельцев (default_seas/default_lakes).
Без этого решения шаг блокируется: effective 0 из нынешних defaults
остановит создание всей существующей declared воды, и ни один
последующий шаг этой регрессии не исправляет.
Файлы: dataModel/placement/{prepared,result,batch}.py;
application/worldData/placement/{resolver,dependencies,diagnostics}.py
и application/worldData/placement/adapters/water.py (outcome identity
projection J08); tests/test_placement_resolver.py/contract.py.
Контракт: §6.5/§6.8/§6.9, живой domain POJO default и terminal fallback 0;
0 не создаёт, None unresolved, >0 участвует; generic
typed reason, authored value сохранён, dependent не получает ложную опору.
Раннее admission и disabled input/outcome payload по закрытому G0-A
обязательны: не требовать geometry/positive original_area ради disable.
PlacementOutcome/PlacementBatchResult расширяются в result.py, включая
identity validation трёх outcomes. batch.py изменяется для early admission
input, не для переноса union; exact schema — §6.29-D.
Граница шага: generic 0-semantics и чтение policy decision в P2;
transport auto_specificity и водный факт WaterPresence→0 внутри
effective_specificity остаются переходно — их замена чтением результата
общего PolicyResolver завершается в G5-CP (§6.8-F).
Проверка: одинаковый нулевой объект воды/горы/другого домена, authored
и effective 0, dry coastline, independent progress, runtime/preview
parity, отсутствие spec/carve для non-created. Старое ожидание dry
coastline creation заменено, positive ordering и accepted immutability
сохранены; default mutation через production путь меняет decision и
placement outcome, explicit 0 сохранён, invalid не получает fallback.
Done: ноль трактуется общим P2, не hydrology filter;
isolated V2 semantics проверены; production default changes и export switch только G10-A.

G0-P IMPLEMENTED/VERIFIED (2026-10-27), isolated до G10-A.
Contracts 62/62; existing placement/water suites 108/108 (world_test_004 включён).
Positive typing 245 файлов без ошибок; negative 88/88 (85 + 3), без лишних/пропусков.
Production constructors/defaults/zero behavior сохранены; проверка изменения
реальных category defaults через active pipeline остаётся acceptance G10-A.

### G1 — общий контекст каскада для водной оси
Уточнение G1: generationContext.py на этом шаге задаёт water runtime/root,
его domain fields/production channel declarations добавляются G2/G2-P.
Bool/float VALUE channels WORLD→CATEGORY→WATER_BODY проверяются isolated
в tests/geo1/contracts/cascade/test_runtime.py (перенос при композиции G2).
CascadeRuntimeContext переносит private runtime snapshots без Any/cast полей;
provenance сохраняет существующий public dict, параметризованный осью.
extend сохраняет concrete CtxT; стирание параметра оси допустимо только на
generic bound application-функций, не в public fields конкретных контекстов.
Verifier ограничивает сбор nodes параметрами проверяемого context model;
unrelated loaded domains не создают ложные duplicate/axis ошибки.
Новые папки generation (2 файла с init) / planning enums (2 → 3),
cascade dataModel (4 → 5); existing application/cascade и locations/context
не расширяются новыми файлами.
Existing materialResolver.py::fold_dominant_material принимает opaque runtime
world и проверяет World на своей domain boundary; алгоритм fold не меняется.
Цель: использовать существующий extend на новом typed контексте.
ТЗ: tz_cascade_context §2–4 + дополнение G0.
Файлы: dataModel/cascade/runtimeContext.py (CascadeRuntimeContext[AxisT]),
existing locations/context/locationContext.py и application/cascade/contextResolver.py
(один runtime с сохранением concrete context type по §6.16-A);
dataModel/hydrology/enums/planning/waterGenerationScope.py (новая ось),
dataModel/hydrology/generation/generationContext.py (WaterGenerationContext);
dataModel/cascade и application/cascade (общий context runtime contract
и адаптация existing engine к новой оси по §5.4, без копии resolver).
Контракт: ROOT/WORLD/CATEGORY/WATER_BODY, context snapshots/provenance, без второго
resolver; urban LocationContext сохраняет свой действующий API.
Проверка: существующие cascade baseline/migration tests, новая ось,
world-level channel, scalar bool/float, independent body contexts,
contract verifier и typecheck:cascade. Done: оба домена на одном механизме.

G1 IMPLEMENTED/VERIFIED (2026-10-27). Runtime contracts 73/73, existing
cascade/context regressions 119/119; planning positive typing 253 файлов — 0 ошибок.
Cascade negatives 8/8 (4 + 4); полный typecheck:cascade сохраняет 16 baseline
ошибок worldLocationTypeRegistry, подтверждён тот же список по HEAD config (delta 0).
Водные source fields/channel wiring остаются G2/G2-P, activation — G10-A.

### G2 — настройки мира
Уточнение G2 по §6.29-J: active WorldHydrology/import/export не меняются.
dataModel/terrain/designedWater/{__init__,strategyKind}.py владеет enum;
hydrology/generation/waterGenerationDefaults.py — WaterFraction constraint,
WaterGenerationDefaults и canonical_defaults; waterGenerationSettings.py —
базовая nullable схема, три Cascade declarations и WORLD/CATEGORY/BODY
prototype types/typed FieldRef edges. Полный leaf graph объявляется вместе
для проверки common verifier; legacy normalization/category owner wiring —
G2-P, source owner wiring — G3/G10-A. generationContext.py получает три
resolved fields и canonical terminal POJO на root, если default_sources=None;
явный tuple источников сохраняет caller injection, root ничего не resolve.
Common cascadeGraph.py unwrap nullable constrained VALUE aliases по base type.
Папка generation: 2 → 4 файла; designedWater: 2. Tests contracts: 5 → 4,
cascade/{__init__,test_runtime,test_settings}.py: 3 — G1 fixture переносится
и наследует общий base с водной осью, чтобы не дублировать G2 declarations.
Цель: ввести authored world channels и terminal default POJO.
ТЗ: раздел GEO-1 из G0 и tz_cascade_context §3–4.
Файлы: dataModel/hydrology/worldHydrology.py; общий WaterGenerationSettings;
water cascade parameter/default declarations; текущий JSON import/export.
Контракт: world.hydrology.generation.{water_fraction,autoresolve,strategy},
единая базовая схема и world/body source подтипы по §5.2-A,
None-наследование без persisted копий,
0.60 и False — terminal fallbacks через POJO/CascadeDefault.
Проверка: round-trip missing/null/0/False, диапазон и finite числа,
отсутствие scalar/SQL копий; composed source binding без nested FieldRef;
generic cascade contract. Done: мир даёт resolved context из одного объекта.

G2 IMPLEMENTED/VERIFIED (2026-10-27), isolated до G10-A.
Contracts 90/90; cascade/context regressions 119/119, water/placement/template 79/79.
Positive typing 258 файлов — 0 ошибок; cascade negatives 13/13 (8 + 5).
Общий typecheck:cascade сохраняет 16 прежних ошибок worldLocationTypeRegistry.
Active WorldHydrology/schema/defaults не переключены; следующий шаг — G2-P.

### G2-P — category channels и legacy normalization contract
Уточнение G2-P: waterGenerationSettings.py добавляет SeasGenerationFields
(sea_generation/ocean_generation) и LakesGenerationFields (generation) —
frozen reusable base POJO для будущих owning policies, не persisted копии.
Их before validators делегируют normalize_seas_generation/normalize_lakes_generation
в legacySettings.py; raw dict разрешён только на этой wire boundary, без Any/cast.
Legacy old bool проверяется строго (null/числа/строки invalid); nullable new
autoresolve сохраняет None. Presence/equality проверяются без bool-coercion.
Unrelated wire keys сохраняются; typed nested POJO проверяется до нормализации.
Папка generation 4 → 5 файлов; cascade tests 3 → 4 (test_legacy.py).
Production owner annotations, rivers и MaskCategoryPolicy не меняются.
Full POJO validation вызывает before-validator; partial patch сначала
канонизируется тем же pure helper, затем resolve_patch валидирует только
переданные canonical fields. Общий patch engine/model-invariant policy не меняется.
Цель: подготовить single-owner SEA/OCEAN/LAKE channels по §6.29-A.
ТЗ: tz_json_validation §Field policy, tz_cascade_context §2–4, GEO-1 G0.
Файлы: hydrology/generation/{waterGenerationSettings,legacySettings}.py;
legacySettings — pure boundary normalize, не новый generator resolver.
Контракт: nullable generation fields в category source models; old flags
мигрируются по presence, equal old/new допускается, conflict — ошибка.
Rivers autoresolve и общая MaskCategoryPolicy не меняются. Early stage
проверяет новые source models/normalizer isolated; production worldHydrology/
seas/lakes source annotations, удаление old flags и новый export только G10-A.
Проверка: geo1/contracts test_cascade.py, missing/null/False/True,
conflicting paths, round-trip без двух persisted копий.
Done: typed channel contracts готовы; старые consumers не получают None
вместо прежнего bool до единого switch.

G2-P IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
Contracts 105/105, water/placement/template regressions 79/79; positive typing 259 файлов — 0 ошибок.
Cascade negatives 16/16 (13 + 3), planning negatives 88/88; общий cascade-check — 16 прежних registry errors.
Old/new presence, strict bool, explicit new null, conflict code и canonical round-trip проверены;
production annotations/defaults сохранены. Следующий шаг — G2-G.

### G2-G — декларации hydrology enabled/autoresolve behavior
Follow-up по обсуждению 2026-10-28: общий authoring layer через annotations,
generated rule IDs и migration G2-G реализованы в [policy-annotations-done](./policy-annotations-done.md)
по [tz_policy](../../docs/tz_policy.md), согласованы 2026-10-28. Production gate
G10-A сохраняется; будущие G5-CP/G9-S используют общий declaration/compiler API.
Уточнение G2-G: isolated до G10-A, как G2/G2-P. Root fields объявляются
reusable WorldHydrologyGenerationFields в existing waterGenerationSettings.py;
active WorldHydrology и category owners не переключаются. Category channels
используют уже объявленные SeasGenerationFields/LakesGenerationFields.
HydrologyExecutionMode — enums/planning/hydrologyExecutionMode.py;
WaterPolicyReason и HydrologyGenerationDecision (value alias) —
hydrology/policy/hydrologyGenerationDecision.py; generation cases —
hydrology/policy/hydrologyPolicyDefinition.py::HYDROLOGY_GENERATION_POLICY
и HYDROLOGY_ENABLED/HYDROLOGY_AUTORESOLVE, прикреплённые к source/resolved полям.
Общий compile_value_policy создаёт value spec с generated IDs, без domain factory.
Общий ObjectAdmissionPolicyDefinition.bind_value_selection переиспользует
те же enabled rules без PRIORITY stage; ValueSelectionPolicySpec.disabled_behavior
задаёт enum для доказанного DisableEffect. PolicyResolution.stop исполняет
эту общую декларацию; no-match/invalid input остаются unresolved без fallback.
Это не регистрация ObjectAdmissionPolicySpec как VALUE_SELECTION.
Новые папки: hydrology/policy 3 файла с init; enums/planning 3 → 4;
generation остаётся 5, contracts 4 → 5; common policy остаётся 9,
application/policy остаётся 5. Новые файлы включаются в planning typing suite.
Цель: выразить принятые gates через POJO/enum и общий policy engine.
ТЗ: G0, Q-AUTO-GATES, §6.8-D/E.
Файлы: WorldHydrology/WaterGenerationSettings и category source POJO;
dataModel/hydrology/policy/hydrologyPolicyDefinition.py (generation cases
и binding общей ObjectAdmissionPolicyDefinition); HydrologyExecutionMode,
HydrologyGenerationDecision; перенос existing HydrologyScope в dataModel,
если enum нужен source POJO, без второго определения.
Контракт: enabled hard switch, WORLD→CATEGORY→BODY cascade,
PolicyResolver выбирает DISABLED/DECLARED_ONLY/AUTORESOLVE.
Проверка: root off + body true, world/category/body overrides,
missing/null, StrictBool/enum invalid, no raw wire, no second and/or gate.
Done: execution mode выводится общим resolver, не local hydrology resolve.

G2-G IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
Contracts 115/115; positive typing 263 файлов — 0 ошибок; negatives planning 90/90, cascade 16/16.
231 regression tests passed; existing CoarseFixtureAcceptance setup broken: coarse_snapshot
не получает planning/capture/wait (test/helper совпадают с HEAD). Общий cascade-check — 16 прежних registry errors.
Production owners/defaults не переключены; следующий шаг — G3.

### G3 — overrides водоёма
Уточнение G3 по §6.29-J: contracts-only, без active Declared* annotations/export
и без нового source-family facade. Existing waterGenerationSettings.py получает
BodyGenerationFields — reusable frozen owner field generation с factory
BodyWaterGenerationSettings. Уже объявленные BODY→CATEGORY→WORLD FieldRef edges
переиспользуются без новых CascadeChannel nodes. Basin/coastline/lake composition
проверяется isolated test subclasses existing owners в
tests/geo1/contracts/cascade/test_body_generation.py через общий resolve_model/
resolve_patch, без собственного normalizer/resolver. Тот же embedded settings
служит procedural caller; его source union остаётся последующим контрактом.
Папки generation 5→5, cascade tests 4→5; новые production файлы не создаются.
Owner wiring и source constructors/import/export входят только в G10-A.
Цель: добавить один reusable POJO и body channels для существующих inputs.
ТЗ: GEO-1, tz_terrain_hydrology §Declare, tz_cascade_context §2–4.
Файлы: dataModel/hydrology source POJO; shared generation overrides;
load/normalization boundary. Контракт: generation.water_fraction/autoresolve/strategy,
typed FieldRef links к world channels; source identity сохраняется.
Проверка: все примеры §4.3, три source типа, provenance, explicit False/0,
preview/runtime parity. Done: потребители не резолвят параметры вручную.

G3 IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
BodyGenerationFields переиспользует готовые BODY channels; три source compositions,
§4.3, provenance/0/False, shared import/patch и preview/runtime parity проверены.
GEO-1 170/170 (+10), location/cascade 52/52; positive typing 271 файл — 0 ошибок.
Negatives planning 103/103, cascade 19/19 (+3); full cascade-check — 16 baseline registry errors, delta 0.
Active Declared*/WorldHydrology/schema/exports не менялись; следующий шаг — G3-R.

### G3-R — площадь области генерации от домена региона
Входной аудит 2026-10-28: §6.3 и поздний §6.29-M задают разные return types
prepare_terrain_regions (snapshot vs plan с coverages); §6.29-E не задаёт
region_uid результата mixed-UID coverage algebra. Предложение точных signatures,
owning paths и contracts-only границы — [G3-R contract](./geo-1-region-extent-contract-done.md),
согласован 2026-10-28. Return type и coverage identity ниже уточняются этим supplement.
Цель: предоставить потребителям готовый размер региона через его домен.
ТЗ: GEO-1 из G0, tz_terrain_generation §generate-surface,
tz_map_light_bake §Placement P1 и coordinate units.
Файлы: новые dataModel/terrain/regions/{terrainRegionExtent,terrainRegionsSnapshot}.py;
terrain/regions/regionExtent.py;
application/worldData/planning/composition/surfacePlanningAssembler.py;
hydrology/placement/waterPlacementPass.py (передача typed input).
Target caller wiring: application/worldData/planning/composition/
surfacePlanningAssembler.py и terrain provider; old surfaceTerrainContext
не расширяется новой orchestration, его shim contract сохраняется.
Контракт: §6.3 + согласованный supplement — prepare_terrain_regions возвращает
TerrainRegionPlan(snapshot:TerrainRegionsSnapshot, coverages)
до water placement; generation_area_fine2 отдаёт домен рельефа.
Не изменять SurfaceHeightmap и не брать площадь из downstream ReliefFacts.
Проверка: irregular region, seam, full/partial parity и отсутствие
локального bbox/shape/cell-count fallback у consumers; coarse→fine² scale,
world/snapshot identity, missing region — явный unresolved, неизменность
surface_z и различие generation area/placement original_area.
Done: один terrain provider возвращает typed extent/coverage до водного прохода;
водные consumers принимают его без самостоятельного расчёта размера.

G3-R IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
TerrainRegionPlan + exact span algebra, общий geometry predicate без density,
anchor/claim input и identity/missing-region guard готовы; active assembler/water pass не переключены.
GEO-1 192/192 (+22), location/cascade 52/52, rasterizer 18/18; positive typing 280 файлов — 0 ошибок.
Negatives planning 107/107 (+4), cascade 19/19; full cascade-check — 16 baseline registry errors, delta 0.
§6.3/§6.29-E приведены к согласованным signatures; следующий шаг — G4.

### G4-S — dataModel prerequisites стратегий
Согласован 2026-10-28 по [уточнению G4](./geo-1-strategy-boundary-contract.md).
Цель: source/metadata, resolved field policies, recipes/field и floor profile
до input/output/protocol. ТЗ: §6.29-B/F/L/M и tz_terrain_generation §Planning
и доставка GEO-1. Точные файлы/контракты/проверки — supplement, раздел G4-S.
Source/body region binding не является cascade-параметром; ни одна модель
не выполняет policy, threshold, placement, sampling или запись высот.
Composition: sources 4, settings 4, fields 2, bathymetry 2→3 файла;
tests/contracts/sources 2 и tests/geometry 3, roots не расширяются.
G4-S IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
GEO-1 209/209 (+17), location/cascade/rasterizer 70/70; positive typing
291 файл — 0 ошибок; negatives planning 113/113 (+6), cascade 19/19.
dataModel→application imports отсутствуют в 11 новых модулях; active
sources/capture/BasinSpec/writer не переключены. Следующий шаг — G4.
По замечанию о размере valid.py выполнена [композиция positive fixtures](./planning-positive-typing-composition-done.md):
61 декларация/74 assert_type сохранены, positive typing 302 файла / 0 ошибок;
negative planning/cascade остаются 113/19. G4 ещё не выполнялся.

### G4-I — immutable результат cascade
Согласован 2026-10-28 («Далее») по последнему разделу
[supplement](./geo-1-strategy-boundary-contract.md). Runtime WaterGenerationContext
содержит live _world/links и mutable provenance; strategy получает вместо него
ResolvedWaterGenerationContext через общий freeze_resolved_context.
Точные пути/контракт/проверки/композиция — supplement. Механический перенос
existing immutable validator в dataModel/validation устраняет обратный импорт.
Нет новых World Snapshot identity/revision/IO/commit APIs и повторного resolve.
G4-I IMPLEMENTED/VERIFIED (2026-10-28): GEO-1 219/219 (+10),
location/cascade/rasterizer 70/70; positive typing 304 файла / 0 ошибок;
negative planning 113/113, cascade 23/23 (+4). Shared immutable admission
проверяет также nested private values, без дублирования validator.
Existing cache/planning API сохранён; следующий шаг — G4.

### G4 — абстракция стратегий
Prerequisite — G4-I; input.context:ResolvedWaterGenerationContext.

Контракт уточнён согласованным [supplement](./geo-1-strategy-boundary-contract.md).
Prerequisites — G4-S. Procedural draft несёт поле без footprints;
threshold и procedural footprints создаёт G4-C. Factory получает четыре
обязательных implementation через constructor DI; production binding G10-A.

Цель: единый typed preparation interface без spatial resolve/z-write.
ТЗ: GEO-1 и tz_map_light_bake §Placement P1/P2.
Файлы: dataModel/terrain/designedWater/{strategyKind,input,draft}.py,
dataModel/terrain/designedWater/fields/field.py,
dataModel/terrain/designedWater/coverage/budget.py;
terrain/designedWater/strategies/{strategy,strategyFactory}.py.
Контракт: §5.1/§5.2-E/G, design(input) → WaterDesignDraft,
единственный enum→implementation dispatch. `WaterCoverageBudget` —
frozen dataModel тип этого шага; WaterDesignInput принимает BodyCoverageAllocation
из того же coverage/budget.py по §6.29-L,
а dataModel не импортирует application policy (§5.2-D).
Алгоритмы в этом шаге не писать.
Проверка: одинаковые boundary invariants всех implementations, failures
явны; нет нового placement resolver и default в factory.
Done: protocol/input/output/dispatch готовы, отдельные алгоритмы ниже.

G4 IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
Input/draft unions, coverage records и explicit DI dispatch готовы; validate_draft
проверяет metadata/recipe, complete canonical coarse samples и authored floor/profile.
GEO-1 238/238 (+19), location/cascade/rasterizer 77/77; positive Pyright — 0 ошибок,
negative planning 124/124 (+11), cascade 23/23. Algorithms/threshold/budget calculator/
production wiring не менялись. Composition: dataModel root4, coverage2, strategies3, tests5.

### G4-P — общая policy целевого бюджета воды
Цель: один расчёт целевой/остаточной площади для всех способов.
ТЗ: GEO-1 G0, §5.2-D, Q-TARGET и terrain extent contract.
Файлы: terrain/designedWater/coverage/waterCoverageBudgetPolicy.py;
тип WaterCoverageBudget объявлен в G4 (dataModel) — здесь только policy.
Контракт: calculate(world_extent, world_context, body_requests,
*, authored_union_fine2, available_auto_area_fine2) по §5.2-D/§6.29-E;
площади от геометрического владельца, authored union учитывается один раз.
world_context — immutable ResolvedWaterGenerationContext уровня WORLD по G4-I;
extent/requests — existing typed records, площади — existing strict FineArea.
Проверка: 0/60/100%, превышение authored над целью, overlapping declares,
несовпадающие единицы — ошибка; никаких writes/resolve/candidates.
Done: алгоритмы не рассчитывают свои бюджеты или defaults доли воды.

G4-P IMPLEMENTED/VERIFIED (2026-10-28), isolated до G10-A.
Pure typed policy: exact Decimal half-up, общий union cap, largest-remainder
с tie по source_uid; geometry/cascade/admission/placement/wiring не выполняются.
GEO-1 251/251 (+13), positive Pyright — 0 ошибок, negative planning129/129 (+5).
Composition: application coverage2, tests/geo1/coverage2; raw records и runtime
context отклоняются, shared region measures валидируются без пересчёта geometry.

### G4-C — общий preparer draft → placement candidates
Уточнение [контракта](./geo-1-placement-preparation-contract.md) APPROVED
2026-10-28 («Ок»): geometry result G4-C, единый adapter cutover G8,
accepted profile→spec/writer G9. Параллельный water V2 transport не вводить.
Цель: единый порог/constraint boundary после любой стратегии.
ТЗ: GEO-1 G0, §5.2-H, tz_map_light_bake §Placement P1/P2.
Файлы: terrain/designedWater/preparation/placementPreparation.py;
dataModel/terrain/designedWater/preparation/result.py (+init),
settings/fieldSelectionPolicy.py; existing continentalNoisePolicy.py,
terrain/regions/coverageMeasure.py. Adapter types — owning G8, не G4-C.
Контракт: prepare(input, draft, *, selection_policy) → WaterDesignPreparation;
finite candidates, immutable original_area, metadata/profile для adapter G8.
Проверка: общий threshold один раз, ties детерминированы, authored
constraints сохраняются, нет resolve_placements/z-write в preparer.
Done: ни одна стратегия не имеет своего placement/post-fill threshold.

G4-C IMPLEMENTED/VERIFIED (2026-10-28), geometry stage до adapter G8.
Typed WaterDesignPreparation + explicit selection policy; score_bits перенесён
из noise. Exact weights — RegionCoverageMeasure; prefix/shortfall/empty failure,
native authored geometry/profile сохранены. Admission/P2/z-write не добавлялись.
GEO-1 273/273 (+22), existing placement/water/factory67/67 (world_test_004),
positive Pyright — 0 ошибок, negative planning137/137 (+8). Composition:
dataModel preparation2/settings5, application preparation2, tests preparation4.

### G5 — authored region strategy
[G5 boundary supplement](./geo-1-strategy-boundary-contract.md#g5--незамкнутый-authored-geometry-input)
APPROVED 2026-10-28 («Давай»): typed geometry request/result до metadata,
обязательное geometry-поле authored input; пояснения объектов в коде/ТЗ.
Defaults/working WorldHydrology внутри strategy и реконструкция fine
heightmap из coarse surface запрещены.
Цель: провести authored input через общий strategy boundary.
ТЗ: GEO-1 и tz_terrain_hydrology §Declare.
Файлы: terrain/designedWater/strategies/authoredRegionStrategy.py,
dataModel/terrain/designedWater/geometry/authoredGeometry.py (+init),
existing input.py, water adapter/geometry helpers и projectDeclaredHydrology.py.
Контракт: существующие RegionShape/placement types, source metadata;
заданные geometry/floor не меняются без согласованного autoresolve правила.
Проверка: declared basin/lake/coastline regression и constraints.
Coastline здесь работает по нынешнему контракту — разделение purpose
вводится в G5-C1, ожидания для coastline уточняются в G5-C1/G5-CP.
Done: authored strategy реализует общий контракт без второго carve.

G5 IMPLEMENTED/VERIFIED (2026-10-28): AuthoredWaterGeometryRequest/result,
required input.geometry, typed single-source projection и explicit helper seed;
strategy сохраняет geometry/metadata/floor без rasterize/clamp/WorldHydrology.
Роли объектов выделены комментариями в коде и ТЗ по просьбе мастера.
GEO-1 295/295 (+22), existing placement/water/factory67/67 (world_test_004),
positive Pyright — 0 ошибок, negative planning144/144 (+7).
Composition: geometry2, strategies4, adapters6 (WARN), authored tests5.

### G5-C1 — typed source/boundary purpose coastline
Цель: сделать два поведения явными в source contract до алгоритмов.
ТЗ: GEO-1 G0/§5.3, tz_terrain_hydrology §Declare,
tz_map_light_bake §Placement P1/P2 после sync G0.
Файлы: DeclaredCoastline, CoastlinePurpose enum, existing waterTypes/source
classification и wire validator. Контракт: water_source/body_boundary,
target_source_uid и их несовместимые комбинации; source vs physical UID.
Enum размещается рядом с POJO в declaredCoastline.py (root20→20, enums10→10).
Единственная classification property is_water_source используется wrapper,
water adapter merge, declared loader и existing body-presence guards. Bulk body
projection сохраняет boundary без fine→coarse изменения. Wire validation —
existing POJO resolver, без отдельного validator. Новый enum зарегистрировать
в existing planning/encoding/surfaceManifest.py для typed canonical encoding.
Target existence/admission/final-body mapping — owning G5-CP/G5-C3, не REF-W
по physical WaterBody registry или неполному набору declared sources.
Проверка: legacy declaration → water_source, enum/refs/required target,
body-boundary не попадает в body source merge. Done: варианты различимы
без чтения current terrain/угадывания по наличию воды.

G5-C1 IMPLEMENTED/VERIFIED (2026-10-28): typed purpose/target, existing wire
resolver и единая is_water_source classification; boundary исключён из body
wrapper/merge/load/guards, absolute path сохранён для dependent стадии.
CoastlinePurpose зарегистрирован в canonical manifest; нового persisted списка нет.
GEO-1 310/310 (+15), existing placement/water/wire80/80 (world_test_004),
positive Pyright — 0 ошибок, negative planning148/148 (+4).
Composition: hydrology20/enums10/adapters6/load9 неизменны, tests coastline3.

### G5-CP — hydrology placement cases и facts
Входной аудит 2026-10-28: live source/category POJO не проходят existing
Policy FieldRef admission; coast/lake не имеют authored priority поля,
source→physical mapping/support snapshot ещё не определены в коде.
Согласовано [уточнение](./geo-1-strategy-boundary-contract.md#g5-cp--уточнение-policy-sources-и-support-snapshot),
DONE 2026-10-28, согласовано «Ок». Не ослаблять generic validator,
не копировать default1 и не выводить source mapping по равенству UID.
Цель: описать source/boundary domain behavior для общего policy engine.
ТЗ: G0, §5.3, §6.8-F. Вход: purpose enum G5-C1 и engine G0-PE.
Файлы: dataModel/hydrology/policy/hydrologyPlacementPolicy.py (placement descriptor/cases;
отдельно от generation metadata, hydrology/policy 3 → 4 файла);
application/worldData/generators/hydrology/policy/{__init__,hydrologyPolicyFacts,hydrologyPlacementBinding}.py;
dataModel/hydrology/placement/{__init__,placementFields}.py;
dataModel/hydrology/planning/sourceBodyMapping.py;
existing declaredBasin/declaredCoastline/declaredLake/sources/proceduralWaterSource,
seas/lakes/category/rivers — single field owners, baseline rivers сохранён;
tests/geo1/placement_policy/{__init__,fixtures,test_placement_policy}.py;
typing/planning valid/policy.py, invalid.py, pyrightconfig.valid.json.
Контракт: домен задаёт AdmissionPolicy/PolicyCaseDeclaration, defaults и typed
water-support facts; общий compile_admission_policy создаёт existing spec.
Field-local rules задаются metadata, compound rules используют typed FieldRef;
ни один domain case не задаёт ручной строковый PolicyRuleId.
PolicyResolver вычисляет effective priority/admission, без water if в P2.
Проверка: одинаковый engine для generic/водного случая, water_source
не требует будущей воды, boundary missing support disabled/waiting,
authored 0 не переписан, domain default не заменён общим литералом 1.
Done: typed binding отдаёт compiled spec/inputs/facts existing PolicyResolver;
source/boundary adapters подключаются в G5-C2/G5-C3/G8, production switch G10-A.
Target support case отдельно компилируется без field metadata и объединяется
с main spec: descriptor identity и generic validator не ослаблены.
Проверено: GEO-1 338/338 (+28), existing placement/water/factory80/80
(offline world_test_004), positive Pyright0, negative153/153 (+5).
Actual category default0/values, authored0/terminal0, wet/dry/unknown/support,
world/ref coherence, deep immutability и runtime issue/provenance покрыты.
SourceBodyMapping — контракт final fill; production producer этим шагом не заявлен.

### G5-C2-G — generic source contract (DONE 2026-10-29)
Согласовано пользователем: «давай generic». Отдельный проверяемый срез
G5-C2 до adapter wiring; input type blocker устраняется, линия как terrain
constraint и activation не объявляются реализованными.
ТЗ: tz_terrain_generation GEO-1 §5.3-A, main §6.29-B/L/M;
tz_terrain_hydrology §GEO-1. До кода синхронизировать generic contract.
Связанный owner: dataModel terrain/designedWater/draft.py —
ProceduralWaterDesignDraft принимает PROCEDURAL и COASTLINE source_kind;
форма результата описывает алгоритм, не происхождение source. Поле metadata
сохраняется целиком, recipe/floor invariants не меняются.
Owner/layer/path: dataModel terrain/designedWater/input.py — общий
WaterDesignInput[S], authored/noise/plate/plate_noise generic subclasses.
Допустимые source: authored — existing AuthoredWaterSource; procedural
strategies — ProceduralSource | CoastlineWaterSource. TypeVar bounds и defaults
явные, без Any; source kind discriminator сохраняется при специализации.
WaterStrategyInput — closed runtime union этих же четырёх variants с явными
полными source unions. Это один transport, прежние consumers обновляются
вместе; отдельный V2 input не вводится. Typed source сохраняет identity и
path, no synthetic ProceduralSource. Strategy/recipe и geometry validators
остаются; общий generic base не заменяет runtime union validation.
Application consumers: existing terrain/designedWater/strategies/{strategy,
authoredRegionStrategy}.py, preparation/placementPreparation.py — принимают
WaterStrategyInput, не исполняют новую policy и не меняют preparation semantics.
Tests: existing tests/geo1/contracts/strategies/test_input.py (5 files остаются5),
existing typing/planning/valid/terrain/water.py и invalid.py; typing config
уже включает owning input/consumers. Новые файлы/папки не добавляются.
Проверки: специализации сохраняют source type/path; valid procedural и coastline
для трёх algorithms; source/strategy bounds static и runtime (включая явное
недопустимое generic parameterization), invalid recipe и body_boundary;
round-trip closed union; copied/cross-specialization instances revalidated;
GEO-1 regression и positive/negative Pyright. Done: generic контракт проверен,
G5-C2 adapter/constraints остаются отдельным шагом.

Итог: WaterDesignInput[S] + bounded generic variants + один WaterStrategyInput;
procedural draft сохраняет coastline-origin metadata. Consumers обновлены.
Проверено: GEO-1 345/345 (+7), с warnings-as-errors; positive Pyright0,
negative160/160 (+7). Constraints execution/adapter G5-C2 не активированы.

### G5-C2-K — coastline field constraints (DONE 2026-10-29)
Явная команда пользователя «делай» после generic закрывает следующий срез:
применение coastline constraints, без преждевременного production join G8.
ТЗ: GEO-1 §5.3-A/C, §6.29-B/L/M; tz_terrain_hydrology §GEO-1.
Точная карта owners до кода:
- dataModel/terrain/designedWater/geometry/waterDesignConstraints.py:
  WaterDesignConstraints — frozen strict derived terrain mask, source:
  WaterDesignSource (actual normalized source), pre_hydrology_ref:PlanRef,
  grid:SurfaceGridSettings, allowed_cells:frozenset[Coord],
  required_cells:frozenset[Coord], notices:tuple[FieldPathError,...].
  Координаты canonical WORLD_SURFACE_GRID; required subset allowed, обе
  коллекции непусты. Derived result, не persisted source/accepted placement.
- application/worldData/generators/terrain/designedWater/preparation/
  coastlineConstraintPreparer.py::CoastlineConstraintPreparer.prepare(
  request:AuthoredWaterGeometryRequest)->WaterDesignConstraints.
  Только CoastlineWaterSource; existing G5 geometry вычисляется один раз.
  allowed — existing water-side claim/caps. Required — allowed клетки в
  8-neighborhood authored rasterized line (через topology canonicalize).
  Каждый rasterized line cell должен иметь water-side neighbor, иначе
  geometry diagnostic; boundary purpose и projection collapse отклоняются.
  Absolute source/path не меняются, hydro presence/admission не вычисляются.
- existing placement/adapters/coastlineShape.py::coastline_segments — typed
  export уже существующей segment assembly для общего использования.
  Не дублировать water-side/flood/centroid алгоритмы в terrain preparer.
- existing WaterDesignInput[S] в input.py получает optional constraints;
  procedural coastline требует constraints, authored inputs используют свою
  готовую geometry. Валидировать full source equality, ref, grid, canonical
  coords. Не выдумывать геометрию для недостающего constraints input.
- existing DesignedWaterPlacementPreparer (placementPreparation.py) только
  общий mask/prefix consumer. Required клетки включаются целиком; их fine²
  площадь должна помещаться в allocation и полную region coverage. Остальные
  allowed полные клетки выбираются существующим signed-score quantization/
  deterministic prefix. При нехватке required budget — CONSTRAINT_CONFLICT;
  при capacity shortfall — прежний notice. Allowed mask не является budget,
  priority или support. Без constraints прежняя selection семантика сохраняется.
- existing strategyKind.py: WaterDesignIssueCode.CONSTRAINT_CONFLICT.
- tests/geo1/preparation/test_coastline_constraints.py; existing generic input
  tests/typing fixtures обновить для required ready constraints.
Composition: dataModel geometry2→3, application preparation2→3,
placement/adapters6→6 (WARN), tests preparation4→5; roots без additions.
Проверки: open/closed, interior/exterior, dry terrain, span/negative/seams,
source/ref/grid mismatch, immutable/strict, required budget conflict,
land-side high score exclusion, strip preservation, unavailable partial region,
no writes/no policy/no fake support; generic + Geo1 + positive/negative typing.
Done: constraint producer и consumer проверены как один typed contract;
G5-C2 adapter/join/auto policy activation — дальнейшая часть G5-C2/G8.

Итог G5-C2-K: typed producer + captured constraints + единственный общий
mask/prefix consumer; no live World/hydro support/policy/Z writes.
Проверено: GEO-1 361/361 (+16), water adapter/factory/wire47/47,
positive Pyright0, negative165/165 (+5), warnings-as-errors, diff-check.
Authored geometry/carve/production callers не переключались; adapter/join
с готовыми region/budget/context/admission остаётся дальнейшей частью G5-C2.

### G5-C2 adapter/join — DONE (2026-10-29)
Продолжение по команде пользователя «Далее». Typed captured join принадлежит
CoastlineWaterSourceAdapter в уже согласованном application terrain пути.
Новых транспортов placement/V2 и default settings blobs не вводить.
Owner/class map до кода:
- dataModel/terrain/designedWater/input.py: CoastlineWaterDesignInput — alias
  четырёх existing generic variants, параметризованных CoastlineWaterSource.
- application/worldData/generators/terrain/designedWater/preparation/
  coastlineWaterSourceAdapter.py::CoastlineWaterSourceAdapter.prepare_source(
  source:DeclaredCoastline, *, geometry_request:AuthoredWaterGeometryRequest,
  context:ResolvedWaterGenerationContext, generation:HydrologyGenerationDecision,
  region:TerrainRegionExtent, budget:BodyCoverageAllocation,
  region_coverage:RegionCoverage, metadata:WaterSourceMetadata,
  admission:PlacementAdmissionInput, field_policy:WaterFieldRecipe|None)
  ->CoastlineWaterDesignInput. Все kwargs обязательны, None — только explicit
  отсутствие procedural recipe для authored. Geometry request группирует
  actual source/pre-hydrology envelope/topology/grid/seed/anchors/seas/z_min.
- Source-normalization через existing wrapper, request source должен совпадать
  полностью. Admission world/source/mode, context/decision strategy и generation
  mode сверяются как structural invariants. Self support/source dependency
  запрещены. Не вычислять priority/admission/cascade/coverage budget в adapter.
- Non-READY admission/generation отклоняются до geometry. Production caller
  обязан передавать только offered ready headers. Zero priority пропускает
  preparation через existing PlacementSession. Missing/invalid input → existing
  PlanBuildFailure/FieldPathError, без отдельного failure framework.
- Полная authored coastline в этом join — closed ring с явной water_side;
  open line не становится authored через legacy expansion. Authored допускает
  DECLARED_ONLY; procedural input требует готовое AUTORESOLVE решение общего
  engine, согласованное с context. При несовместимых ready decisions — diagnostic,
  adapter не превращает их в другой policy decision или effective strategy.
- По effective strategy adapter делегирует только existing geometry owner
  (authored) либо CoastlineConstraintPreparer (procedural), затем связывает
  готовые поля existing typed constructor. Recipe должен соответствовать
  strategy; actual source UID/kind/liquid/path сохраняются.
- tests/geo1/coastline_source/{__init__,fixtures,test_adapter,test_batch}.py
  (новая папка4 файла), existing typing valid/terrain/water.py и invalid.py.
  Common lifecycle tests используют существующий executor/transport и supplied
  test fields: реальные noise/plate implementations ещё G6/G7, без runtime stub.
Composition: application preparation3→4, dataModel root4→4; test новая папка4.
Уточнение порядка: legacy run_water_placement_pass не имеет captured inputs;
его production caller cutover требует всего G8 universe и единого transport
switch. Поэтому G5-C2 поставляет готовый join adapter и проверяет общий batch,
production routing выполняется одним cutover G8/G10-A. Не добавлять optional
legacy/target switch или промежуточный raw mapping в legacy caller.
Проверки: dry/autoTrue/positive source → input + common batch ready;
closed authored/autoFalse, incomplete open/DECLARED_ONLY fail before geometry,
authored0 no preparation, disabled/unresolved admissions, mismatched refs/source/
world/grid/strategy/recipe, mountain conflict без сдвига, wrapped/sphere seams,
preview/runtime equality, no policy/no budget calculation/no Z writes.

Итог adapter/join: supplied generation/admission проверены до geometry;
готовые typed inputs → existing generic input, без raw kwargs/новых transport.
Проверено: GEO-1 378/378 (+17), adapter/factory/wire47/47, positive Pyright0,
negative169/169 (+4), warnings-as-errors. Общий batch: dry source accepted,
zero skips geometry, reserved competitor rejects whole candidate; no Z writes.
Production routing — один G8/G10-A cutover, actual auto generation G6/G7/G9/G10.

### G5-C2 — coastline как источник body generation
Статус 2026-10-29: isolated typed source join DONE. G5-C2-G/K и adapter/join
реализованы и проверены через existing общий placement lifecycle.
Production acceptance зависит от G8/G9/G10; source routing переносится
одним cutover G8, без optional legacy/target пути. Ниже — исходный аудит
2026-10-28, сохранённый как контекст уже закрытых type/constraint блокеров.
G4 implemented input.py допускает CoastlineWaterSource только в
AuthoredWaterDesignInput; Noise/Plate/PlateNoiseWaterDesignInput.source
ограничены ProceduralSource. Их field recipes/общий G4-C preparer не несут
coastline constraints. Поэтому literal signature §5.3-A ещё не замкнута:
нельзя передать исходный coastline в procedural strategy, не потеряв его
path/identity или не подменив его искусственным ProceduralSource.
Наличие существующего authored helper для open line не делает его
процедурным strategy input и не доказывает правило autoresolve=False
для неполной геометрии. Existing G5 helper не исполняет эту policy.
Также run_water_placement_pass имеет только legacy World/location/heightmap
входы и не получает captured region/budget/resolved context/admission;
подключение нового adapter туда без input join продублирует будущий G8.

Предложение на согласование перед кодом (не новый V2 путь):
1. Сохранить исходный CoastlineWaterSource в существующих procedural
   variants input.py; field constraints имеют terrain-owned typed контракт,
   который явно сохраняет authored path/closed/water_side и identity/ref.
   Семантику исполнения ограничений закрепить перед G6/G7/G4-C cutover;
   одного расширения source union недостаточно.
2. CoastlineWaterSourceAdapter в уже заданном application terrain path
   только связывает готовые inputs. Admission/header — existing
   PlacementAdmissionInput, context — ResolvedWaterGenerationContext,
   snapshot — PlanEnvelope[TerrainPlan], topology/grid — existing types;
   actual metadata/geometry/recipe должны поступать через явные typed
   зависимости. Budget/cascade/policy resolution/relief writer не дублировать.
3. Уточнить complete authored geometry vs incomplete procedural coastline:
   authored ветка сохраняется при autoresolve=False, неполная линия не
   расширяется в полный basin в обход False. Не объявлять любую open line
   полностью authored только потому, что legacy helper умеет её расширять.
4. Transitional caller должен получить тот же captured join, который G8
   затем переместит в designPreparation.py. До этого нельзя объявлять
   production wiring или подменять недостающие данные defaults/raw dict.
Нужное решение: подтвердить сохранение coastline как procedural source с
явными terrain constraints и уточнение prerequisite G5-C2 до adapter wiring.
Точные поля/владельцы нового constraints contract и его producer/consumer
подлежат фиксации и согласованию; этот аудит не разрешает выбирать их
молча при написании кода.

Цель: сохранить autoresolve моря/океана по authored линии.
ТЗ: GEO-1 §5.3-A/C, общий priority contract §6.5.
Файлы: terrain/designedWater/preparation/coastlineWaterSourceAdapter.py;
routing через существующий caller
run_water_placement_pass — designPreparation создаётся только в G8,
перенос caller туда входит в G8; existing common preparation helpers и
placement fact mapping.
Контракт: prepare_source → WaterDesignInput; обычный body priority,
без self dependency и fake WaterPresence.PRESENT. Методы §5.3-A.
Проверка: dry world/auto True/positive priority → body candidate
подготовлен и принимаем общим batch; e2e создание тела на этой позиции —
только полностью authored геометрия через существующий declared path
(autoresolve-e2e перенесён в G10: требует G6/G9). Source 0, auto False,
mountain conflict, seam, no double carve. Done: source-line scenario
работает через общий batch и single relief writer.

### G5-C3 — implementation contract, absolute authored boundary (DONE 2026-10-29)
Продолжение по «Далее». Current DeclaredCoastline требует nonempty path;
этот шаг реализует absolute BODY_BOUNDARY. Empty derive-mode/ring extraction
и production capture/cache/provider activation остаются G10; не подменять
исходный path derived shoreline. Ни coarse hydro, ни отсутствие fine sample
не доказывают fine dryness.
Точная карта owners перед кодом:
- dataModel/hydrology/boundaries/attachedCoastline.py: CoastlinePart(body_uid,
  closed,path), AttachedCoastline(source_uid,target_source_uid,parts,
  coordinate_space:WORLD_FINE_GRID,hydrology_ref), CoastlineBoundaryInput
  (sources,resolution_mode,grid,topology), CoastlineBoundaryPlan(boundaries,
  outcomes:tuple[PlacementOutcomeV2,...],issues:tuple[FieldPathError,...]).
  BoundaryIssueCode enum: INVALID_INPUT, UNKNOWN_FINE_WATER, BOUNDARY_OFF_TARGET.
  Typed output/diagnostics owned by hydrology; no new generic placement transport.
- dataModel/hydrology/boundaries/boundaryWaterSnapshot.py (+__init__):
  FineBoundaryWaterCell(cell:FineXY,body_uid:EntityUid|None),
  BoundaryWaterSnapshot(hydrology:PlanEnvelope[HydrologyPlan],source_mapping,
  mapping_hydrology_ref,placement_ref,water_outcomes:tuple[PlacementOutcomeV2,...],
  fine_cells:tuple[FineBoundaryWaterCell,...],grid,topology).
  accepted — readonly projection resolved outcomes, остальные сохраняют actual
  source→region identity для causal refs, без повторного policy execution.
  Fine samples sorted unique canonical; None is explicit dry; absent unknown.
  Physical UIDs must exist in final WaterBody. Mapping ref equals hydro ref;
  placement ref must be an exact dependency of hydro envelope, same world.
  Accepted supports explicitly expressed in WORLD_FINE_GRID by the captured
  producer; no guessing/projection in consumer. Actual producer is post-fill
  fine capture (G9/G10); tests supply explicit captured evidence now.
- application/worldData/generators/hydrology/boundaries/boundaryGeometry.py
  (+__init__): BoundaryGeometry.prepare(source,snapshot)->AttachedCoastline.
  Public BoundaryGeometryResult (frozen application dataclass в том же модуле)
  содержит boundary:AttachedCoastline и уже вычисленные canonical cells:frozenset[Coord].
  prepare возвращает этот result, adapter не растеризует parts повторно.
  Only geometry: raster original unrolled fine path, canonicalize for IO,
  require self+every existing cardinal neighbor sample (planar void is not dry).
  Every path cell must see mapped wet plus explicit dry. Off-target is an issue,
  no nearest-water snapping. Associate all supporting body UIDs, not arbitrary1.
  Each body yields contiguous runs; closed runs stitch tail/head cyclically.
  Whole-line body retains original authored waypoints exactly. Split runs use
  original Bresenham cells with deterministic linear Z interpolation (no surface
  Z writes); their union equals original raster, disconnected runs not bridged.
- application/worldData/placement/adapters/coastline/attachedCoastline.py
  (+__init__): AttachedCoastlinePreparer.prepare_boundary(source,accepted_water,
  admission)->PreparedCoastlineBoundary (frozen application result: prepared
  existing PreparedPlacementV2 + AttachedCoastline metadata). Structural validation
  of READY header/world/source/absolute mode, explicit source→accepted region ID,
  CONNECTED_TO dependency and SHARED_BOUNDARY overlap. Delegate BoundaryGeometry;
  build one absolute candidate. No policy/no basin/floor/carve/fake support.
- application/worldData/generators/hydrology/boundaries/boundaryPlanner.py:
  CoastlineBoundaryPlanner.prepare(input,snapshot,admissions,*,snapshot_uid)
  ->CoastlineBoundaryPlan. Post-water domain caller: existing PlacementSession,
  phase DEPENDENT, immutable accepted fine supports. Only ready headers call
  adapter. Disabled/unresolved/missing/failed support keep common lifecycle
  behavior. Preparation issues retained verbatim in plan.issues and forwarded
  as generic constraint diagnostics; generic placement enums remain domain-neutral.
  Only resolved candidates emit boundary records; no geometry/selection repeated.
  Admissions already computed by G5-CP using captured mode; no policy executor2.
- tests/geo1/boundaries/{__init__,fixtures,test_geometry,test_adapter,test_planner}.py
  and existing typing planning valid/placement.py + invalid.py.
Composition: new dataModel boundaries3, application hydrology boundaries3,
adapters/coastline2 (parent adapters6→6 WARN), new tests folder5. No root additions.
Проверки: wet/dry/missing/failed/disabled target, zero skip, unknown fine evidence,
world/ref/scale/source mismatch, no UID equality inference, merge/split parts,
seams/poles, no path shift/no phantom segment/no Z changes, immutable supports,
full/partial independent same inputs, common dependent phase collision behavior.
Production mapping/fine capture/provider activation не заявляется этим шагом.

Итог G5-C3 authored: typed final-water snapshot + fine geometry/parts +
AttachedCoastlinePreparer + post-water caller через existing dependent session.
Actual source→region causes добавляются из water_outcomes без смены решений;
prepared support geometry immutable, domain issue codes сохранены в plan.issues.
Проверено: GEO-1 406/406 (+28), adapter/factory/wire47/47, positive Pyright0,
negative177/177 (+8), warnings-as-errors. Split/merge, unknown fine, zero,
missing/failed/disabled support, unchanged path, wrapped seam/sphere pole.
Empty derive-mode, actual post-fill fine capture и provider/cache activation
остаются G10; canonical codec registration выполняется при том же activation.

### G5-C3 — attached coastline dependent preparation
Статус: DONE для absolute authored boundary, 2026-10-29.
Production capture/activation и empty derive-mode — G10.

Цель: подготовить только boundary с обязательным готовым water target.
ТЗ: GEO-1 §5.3-B/C, Placement P1/P2 dependent phase.
Файлы: placement/adapters/coastline/attachedCoastline.py; post-water dependent caller;
typed metadata/result mapping без basin spec emission.
Контракт: prepare_boundary → PreparedPlacement/failure; accepted source
и final body facts, unchanged absolute path, immutable опоры.
Проверка: missing/dry/unresolved target, valid wet target, no body spec
и no z-write, zero priority, full/partial parity.
Done: зависимый boundary не создаёт воду и не запускает pipeline A fallback.

### G6 — implementation contract (DONE 2026-10-29)
Продолжение по «Далее». Норматив §6.29-F: seeded value noise [-1,1], quintic
интерполяция, normalized fBm; planar2D/wrapped4D torus/sphere3D embedding.
Перед кодом замыкается недостающий ready input z_min, не выводить его из
min(surface_z) и не добавлять application default.
Точная карта owners:
- existing dataModel/terrain/designedWater/input.py: _ProceduralWaterDesignInput[S]
  (общий generic base для Noise/Plate/PlateNoise) владеет required z_min:FineZ,
  strict, level>z_min, all pre-hydrology z>=z_min. Authored использует свой
  geometry.z_min. Input.validate_draft сверяет procedural field profile
  z_min/depth с input.z_min и metadata.default_depth. Это structural validation.
- existing preparation/coastlineWaterSourceAdapter.py: передаёт actual
  geometry_request.z_min в три procedural typed constructor, без defaults.
- existing app/ids/uidKind.py: UidKind.WATER_FIELD="water_field" для
  existing seeded_u01; channel=FieldChannel.NOISE_LATTICE,
  octave и lattice tuple — named keys. Source/body/material/tile UID не RNG keys.
- application/worldData/generators/terrain/designedWater/fields/
  noiseFieldGenerator.py (+__init__): NoiseFieldGenerator.build(
  input:NoiseWaterDesignInput)->ContinentalField; sample(recipe:NoiseRecipe,
  *,x:float,y:float)->ContinentalFieldValue, real world-fine positions (centers).
  build validates once, samples coarse center ((gx+.5)*span,(gy+.5)*span)
  в canonical row-major order. Public sample для G9 fine floor evaluator,
  тот же алгоритм, без threshold/terrain queries/field regeneration.
  length=max(1,min(fine width,height)*length_fraction), frequency=lacunarity**k/length,
  octave weights=persistence**k, sum weighted N / sum weights. Zero weights
  не вычисляются. Local lattice memo ограничен текущей coarse row; не plan cache.
  Wrapped continuous positions modulo W/H перед torus embedding;
  sphere fold modulo2H в fine units с half-turn longitude, R=H/pi;
  exact poles=(0,0,+/-R) без longitude roundoff. Canonical aliases cell centers
  совпадают. Quintic и final convex sum clamp только numerical range [-1,1].
  Nonfinite/unrepresentable arithmetic → existing typed PlanBuildFailure,
  без frequency/default/field fallback и без переноса policy в generator.
- application/.../strategies/procedural/continentalNoiseStrategy.py (+__init__):
  ContinentalNoiseStrategy.design(WaterStrategyInput)->ProceduralWaterDesignDraft.
  Requires Noise input, delegates field build, binds FieldFloorProfile(recipe,
  level=metadata.level, depth=metadata.default_depth, z_min=input.z_min),
  floor_z=max(z_min,level-depth). Никаких footprints/threshold/placement/Z writes.
- ContinentalNoisePolicy defaults не меняются; docstring единиц/формулы в owner.
- tests/geo1/noise/{__init__,fixtures,test_field,test_strategy,test_replay}.py;
  existing generic/procedural fixtures получают explicit test-world z_min;
  existing typing planning valid/terrain/water.py и invalid.py.
Composition: новые application fields2, strategies/procedural2;
existing ids6→6 WARN, dataModel root4→4, tests noise5, no root additions.
Проверки: 0/.60/1 allocation через existing common preparer; field независим
от fraction/budget/source identity/heights, settings override changes field;
seed replay/process hash seeds, analytical lattice/quintic/fBm, row-order,
planar/wrapped/sphere aliases/seam/poles, fine/coarse center equivalence,
tiny/negative worlds, nonfinite rejection, profile bounds/readonly snapshots,
coastline constraints через common preparer, no policy/budget/relief writes.
Production factory composition/cutover remains G8/G10-A; no runtime stubs.

### G6 — continental noise strategy
Статус: DONE 2026-10-29. Noise field producer + strategy + shared procedural
z_min input, без production factory activation (G8/G10-A).
Проверено: GEO-1 427/427 (+21), adapter/factory/wire47/47, positive Pyright0,
negative183/183 (+6), warnings-as-errors, replay PYTHONHASHSEED=0/1/42.
Quintic/fBm formula, topology aliases/poles, exact fine/coarse sampling,
0/.60/1 common selection и floor profile bounds покрыты.

Цель: реализовать signed continental field producer и noise strategy.
ТЗ: GEO-1 (формула и семантика доли воды согласованы в G0).
Файлы: terrain/designedWater/strategies/procedural/continentalNoiseStrategy.py,
terrain/designedWater/fields/noiseFieldGenerator.py,
dataModel/terrain/designedWater/settings/continentalNoisePolicy.py.
Контракт: NoiseFieldGenerator.build → ContinentalField,
ContinentalNoiseStrategy.design → field draft; candidates строит G4-C.
Проверка: 0/0.60/1, overrides, seam/pole continuity, permutation replay,
отсутствие post-carve input. Done: стратегия проверена независимо от plate.

### G7 — implementation contract (DONE 2026-10-29)
Продолжение по «Далее», норматив §6.29-F. Plate producer не создаёт mountains,
не выбирает quota/threshold и не пишет Z. Geometry helper не дублируется.
Точная карта owners перед кодом:
- dataModel/terrain/designedWater/fields/plateLayout.py: PlateCenter(index,
  cell:FineXY,buoyancy:ContinentalFieldValue) и PlateLayout(recipe:PlateRecipe,
  multiplier,offset,centers tuple,notices:tuple[FieldPathError,...]). Frozen strict.
  effective_count — readonly len(centers); requested count остаётся в recipe.
  Проверить gcd/range affine coefficients, centers row-major-index formula,
  indices0..k-1, k=min(requested,N), canonical unique positions, immutable data.
- existing fields/field.py: ContinentalField.notices tuple default empty — computed
  normal notices, не settings/fallback. validate_immutable output. Existing
  strategyKind.py: PLATE_COUNT_ADJUSTED code. Producer уже классифицирует
  adjustment как notice полем notices; downstream не угадывает severity по code.
- application/.../designedWater/fields/plateFieldGenerator.py: PlateFieldGenerator
  layout(recipe:PlateRecipe)->PlateLayout, build(input:PlateWaterDesignInput)
  ->ContinentalField, sample(layout:PlateLayout,*,x:float,y:float)->ContinentalFieldValue.
  layout один раз на build; sample reusable для fine floor/composition G9/G7-C.
  N=fine width*height, k=min(requested,N). N1: a1,b0; иначе seeded start
  a in1..N-1, cyclic scan до gcd(a,N)=1; b=floor(u*N).
  named RNG keys channel=PLATE_CENTER, coefficient=AffinePermutationCoefficient,
  cell_count=N; buoyancy channel=PLATE_BUOYANCY, plate_index=i. Floor u*n
  считается exact integer-ratio арифметикой, без float rounding до N.
  cell_i=row-major((a*i+b)%N) по canonical fine extent, O(k) без range(N).
  p — real fine position, common topologyGeometry.dist2 получает p-(.5,.5)
  и integer center cell, т.к. его frame — cell-center indices. Существующий
  folded/wrapped distance owner сохраняется; own metrics/polar guesses нет.
  L=max(1,min(fine W,H)*blend_length_fraction). Weight_i=exp(-(d2_i-min_d2)/L²),
  divided sequentially by L twice без L² overflow; nearest has weight1.
  fsum in plate-index order, no underflow/nearest/random fallback. Finite/range
  validation, unrepresentable arithmetic → existing typed PlanBuildFailure.
- application/.../strategies/procedural/plateStrategy.py: PlateStrategy.design(
  WaterStrategyInput)->ProceduralWaterDesignDraft, требует Plate input; field
  producer + FieldFloorProfile level/depth/z_min от ready input, scalar bound
  max(z_min,level-depth). No noise imports/defaults/mountain construction.
- existing preparation/placementPreparation.py: сохраняет field.notices вместе
  с constraints/cap/shortfall notices; selection algorithm не меняется.
- tests/geo1/plate/{__init__,fixtures,test_field,test_strategy,test_replay}.py;
  existing typing planning valid/terrain/water.py и invalid.py; existing
  geometry/test_fields.py фиксирует новый computed notices field.
Composition: dataModel fields2→3, application fields2→3, procedural strategies2→3,
new tests plate5, existing roots без additions. PlateGenerationPolicy defaults
не меняются; docstring clarifies world-fine length/owning defaults.
Проверки: exact permutation/coprime scan, N1/non-coprime N/full uniqueness,
large N only k centers, prefix stability by requested count, analytical Gaussian
blend/ties, fine/coarse identical sampler, negative/tiny/zero/full quota,
wrapped/sphere fold aliases/continuity, recipe/seed replay across hash seeds,
notice provenance through common prep, floor bounds, real coastline constraints,
no noise/policy/budget/selection/Z operations in strategy. Production factory G8/G10-A.

### G7 — plate strategy
Статус: DONE 2026-10-29. Seeded affine layout + shared topology blend +
PlateStrategy/floor profile; computed tiny-world notices сохранены до preparer.
Проверено: GEO-1 446/446 (+19), adapter/factory/wire47/47, positive Pyright0,
negative190/190 (+7), warnings-as-errors; replay PYTHONHASHSEED=0/1/42.
Large N without fine enumeration, permutation uniqueness/prefix, Gaussian/ties,
fold aliases, quota0/.60/1, no-noise/no-policy/no-writes покрыты.
Production factory composition/cutover остаётся G8/G10-A.

Цель: реализовать plate producer через тот же интерфейс.
ТЗ: GEO-1 (plate algorithm и отношение к mountain contracts из G0).
Файлы: terrain/designedWater/strategies/procedural/plateStrategy.py,
terrain/designedWater/fields/plateFieldGenerator.py,
dataModel/terrain/designedWater/settings/plateGenerationPolicy.py.
Новые pure geometry helpers при необходимости сначала включить в карту
G0-A с подсчётом файлов, не добавлять в произвольную папку.
Контракт: PlateFieldGenerator.build → ContinentalField,
PlateStrategy.design → field draft; plate параметры в POJO,
не вводить свои priorities и не перестраивать mountain objects.
Проверка: topology continuity, детерминизм, authored constraints, invariants
общей strategy boundary. Done: standalone plate реализован.

### G7-C — implementation contract (2026-10-29)
Продолжение по «далее». Формула §6.29-F: clamp(P + detail_weight*N,-1,1),
operator только ADD_CLAMP. Zero detail сохраняет plate samples побитно;
noise не вычисляется, captured noise settings остаются в full recipe/profile.
Owner map перед кодом:
- existing dataModel/.../fields/field.py: readonly PlateNoiseRecipe.plate_recipe
  и .noise_recipe — explicit typed projections actual values, без model_dump,
  defaults/cascade/resolution и без изменения persistent fields.
- existing application fields/noiseFieldGenerator.py::build принимает
  NoiseWaterDesignInput|PlateNoiseWaterDesignInput; concrete input revalidation,
  для mixed использует .noise_recipe, остальной единый алгоритм/row memo прежний.
  fields/plateFieldGenerator.py::build аналогично Plate|PlateNoise input и
  .plate_recipe. Component field сохраняет собственный recipe/actual samples;
  не конструировать fake component inputs с другим context.strategy.
- application/.../fields/continentalFieldComposer.py::ContinentalFieldComposer:
  combine(plate:ContinentalField,noise:ContinentalField|None,recipe:PlateNoiseRecipe)
  ->ContinentalField. Signature уточняет прежний composition_policy argument до
  полного captured recipe: без него нельзя сохранить actual inactive noise
  settings при noise=None/weight0. Это один API, compatibility overload не нужен.
  Strict recipe/fields validation; plate.recipe == recipe.plate_recipe,
  noise.recipe == recipe.noise_recipe и exact coordinate tuple equality.
  None noise допустим только при weight0; не подменять отсутствующий компонент
  zero field. Final recipe — actual PlateNoiseRecipe. Notices: plate плюс noise
  при weight>0; при weight0 только plate. No budget/threshold/placement.
  sample(recipe:PlateNoiseRecipe,layout:PlateLayout,*,x:float,y:float)->field value:
  validates layout.recipe projection, delegates existing public plate/noise
  samplers, same formula; reusable G9 fine floor evaluator. No private kernels.
- application/.../strategies/procedural/plateNoiseStrategy.py::PlateNoiseStrategy
  .design(WaterStrategyInput)->ProceduralWaterDesignDraft: requires mixed input,
  invokes component generators (noise only weight>0), then composer, binds
  FieldFloorProfile with full recipe/captured level/depth/z_min; same scalar bound.
  Does not invoke other strategies, policy, coverage, spatial selection or writer.
- existing FieldCompositionPolicy owning defaults unchanged; owner docstring
  states formula/zero semantics. Final factory composition remains G8/G10-A.
- tests/geo1/composition/{__init__,fixtures,test_composer,test_strategy,test_replay}.py;
  existing typing planning valid/terrain/water.py + invalid.py.
Composition: application fields3→4, procedural strategies3→4,
existing dataModel fields3→3, tests new folder5, no root additions.
Проверки: formula/clamp/zero bit identity and no noise calls, strict component
alignment/recipe rejects, full recipe/profile survives, exact coarse/fine
sampling, wrapped/sphere aliases, tiny-world/cap notices, 0/.60/1 common quota,
real coastline masks and unchanged path, requested policy/seed overrides,
hash seed replay, no duplicate policy/budget/threshold/Z writes.

### G7-C — plate + noise composition — DONE (2026-10-29)
Цель: поддержать явную композицию через тот же strategy interface.
ТЗ: GEO-1 G0, §5.1, §5.2-E/F.
Файлы: terrain/designedWater/strategies/procedural/plateNoiseStrategy.py,
terrain/designedWater/fields/continentalFieldComposer.py,
dataModel/terrain/designedWater/settings/fieldCompositionPolicy.py.
Контракт: plate base → bounded noise detail → единый draft;
calculate budget/threshold/resolve не повторяются.
Проверка: detail=0 даёт plate field, диапазон/единицы scores,
topology seams, deterministic channels, authored/mountain constraints.
Done: все четыре enum режима реализованы без второго writer/resolver.

G7-C IMPLEMENTED/VERIFIED: typed component recipes + one composer/strategy;
zero detail skips noise exactly, full floor recipe/notices preserved.
Checks: GEO-1 461 passed; composition 16 passed (includes added seed replay);
legacy adapter/basin/wire 47 passed; pyright valid 0, negative 197/197; diff clean.
Production factory/caller cutover remains G8/G10-A.

### G7-C follow-up — typed diagnostic operations — DONE (2026-10-29)
User approved local Literal annotations after review of repeated _failure calls.
Owner/layer: existing terrain application fields; no shared cross-domain enum.
Files: fields/plateFieldGenerator.py::PlateFieldGenerator._failure operation
Literal["layout","build","sample"]; fields/continentalFieldComposer.py::
ContinentalFieldComposer._failure operation Literal["combine","sample"].
TZ: tz_terrain_hydrology.md GEO-1 G7-C; diagnostic paths/behavior unchanged.
Check: planning valid pyright, diff --check. Done: arbitrary operation strings
are rejected statically; no runtime contract or folder composition changes.
Verified: planning valid pyright 0 errors; diff --check clean.

### G8 execution split / G8-A — single metadata transport — DONE (2026-10-29)
Code audit: active caller still constructs legacy PreparedWaterEntry from three
source POJOs; basin_specs repeats source/category selection after P2. Geo input/
provider activation belongs to G10-A; doing both joins now would conflate domain
preparation with production activation. Execute G8 in atomic reviewable slices:
G8-A replaces the existing metadata transport/consumer; G8-B performs captured
cascade/admission/budget/design universe join, using this same transport. No
Water V2 transport, compatibility overload or second source list is introduced.
TZ: tz_terrain_hydrology GEO-1 source metadata boundary; §6.29-B/F, J06/J08/J09.
Exact owner map before code:
- NEW application/worldData/generators/hydrology/sources/{__init__,waterSourceMetadataFactory}.py:
  WaterSourceMetadataFactory.build(source:WaterDesignSource,*,default_water_level:FineZ,
  seas:HydrologySeasPolicy,lakes:HydrologyLakesPolicy,rim_level:FineZ|None,
  source_path:tuple[str|int,...])->WaterSourceMetadata. Hydrology application owner
  maps origin/kind/liquid/bands/depth and resolved source/rim/default level once;
  no geometry, cascade, policy execution, placement or height writes.
- existing placement/adapters/waterTypes.py::PreparedWaterEntry: source becomes
  WaterSourceMetadata; prepared remains current PreparedPlacement until common
  admission binding in G8-B/G10-A; floor_z:FineZ, floor_profile:BasinFloorProfile|None
  required. Remove duplicated entry level/kind/liquid. Validate source identity,
  strict floor and typed profile; no new defaults. Existing preparation unchanged.
- existing placement/adapters/water.py::_build_entry: wrap actual source, compute
  lake rim once, delegate metadata mapping before entry; source_path UID-based.
  resolved_water_placements maps level/kind/liquid from metadata; existing
  ResolvedWaterPlacement fields already satisfy this projection, no new record.
- existing hydrology/basinSpecFactory.py::basin_specs(preparation,records): remove
  WorldHydrology argument and source union branching; exact metadata/accepted
  placement join and scalar BasinSpec mapping. Profile remains in entry; actual
  spec/profile writer migration belongs to G9 before production field activation.
  Scalar factory rejects non-None profiles explicitly, never silently drops them.
- existing hydrology/placement/waterPlacementPass.py updates the sole app caller.
- existing test_water_placement_adapter/test_basin_spec_factory and geo1/coastline/
  test_routing follow new contract; planning pyright config includes new source factory;
  tests/geo1/transport/{__init__,test_metadata_transport}.py covers metadata capture,
  procedural source (no location_uid), bad joins and profile retention.
Composition: adapters6→6 and hydrology root7→7 WARN announced; new sources2,
new transport tests2; no existing overfull folder gains files. No source schema,
production gates, common resolver or writer algorithms change in G8-A.
Provider regression exposed a stale test-only canonical manifest: DeclaredCoastline
already contains CoastlinePurpose (production surfaceManifest registers it), but
WaterPlacementProviderTests omitted the enum. Add it to that existing fixture;
HydrologyProviderTests inherits it. No production schema/version change.
Additional existing file: tests/planning/providers/test_domain_providers.py (5→5).
Checks: relevant legacy water/placement/provider regressions, GEO-1, positive
planning typing and exact negative diagnostics; diff --check.
Done: one PreparedWaterEntry metadata representation and one consumer path;
all calls use the two-argument factory; G8 remains open for G8-B universe join.

G8-A IMPLEMENTED/VERIFIED: existing entry now stores metadata/profile; one
source mapper and metadata-only scalar factory; former source POJO/duplicated
entry fields and factory WorldHydrology argument removed with all callers.
GEO-1 472 passed (+10 transport); legacy water/placement + providers 173 passed;
planning pyright valid 0 errors, negative 201/201; diff --check clean.
Baseline fixture delta: registered existing CoastlinePurpose in test manifest;
production manifest already correct. G8-B/G9/G10-A remain open as specified.

### G8 — единая подготовка placement universe — G8-A DONE / G8-B at G10-A
Цель: объединить strategy outputs и доступных competitors на одной границе.
ТЗ: tz_map_light_bake §Placement P1/P2/P3 и GEO-1.
Файлы: terrain/designedWater/preparation/designPreparation.py;
existing waterPlacementPass callers; перенос routing coastline
water_source из transitional caller G5-C2.
Контракт: общий batch, source metadata, accepted dependencies; авто-настройки
разрешены до strategy call; J01–J09 §6.16, один revision и request ctx,
early admission transport без geometry, никакого budget/input цикла.
Authored после READY: geometry request→однократный geometry result→metadata
(lake level из rim_level)→authored input.geometry→design; helpers не дублируются.
По G4-C supplement: заменить единственный water adapter contract вместе
с callers/ResolvedWaterPlacement и metadata consumer basinSpecFactory;
удалить переведённый старый путь, без параллельных water V2 records.
Проверка: конкуренты/overlap/dependencies,
dry coastline, full/partial одинаковый prepared universe, preview без writes.
Done: нет отдельного resolve для plate/noise/authored.

### G8-B dependency audit / G9 execution contract (2026-10-29)
Active PreparedWaterEntry/ResolvedWaterPlacement and resolve_placements still use
legacy geometry-bearing PreparedPlacement. PlacementSession uses V2 admission
contracts; WorldHydrology/Declared*/seas/lakes do not yet inherit the generation
owners (waterGenerationSettings explicitly reserves this for G10-A). A standalone
G8-B activation would need duplicate transport/cascade projection or premature
zero/default changes. G8-B domain join and removal stay part of atomic G10-A;
G10-A prerequisite G8 now means completed G8-A + ready leaf algorithms, not a
preactivated G8-B caller. No new bridge/union/alternate water transport is allowed.
Execution order: G9 → G9-ST → G9-S → G10-A including G8-B → G10-R/G11.
Target ownership/algorithms remain §6.29; this records the actual dependency order.

G9 exact implementation map (TZ tz_terrain_hydrology GEO-1 floor boundary; §6.29-F):
- existing dataModel/terrain/relief/bathymetry/basinSpec.py::BasinSpec adds
  floor_profile:BasinFloorProfile|None=None, strict typed validation, sampled full
  footprint/level/min, field level/lower-bound invariants. Existing None path stays.
- existing hydrology/basinSpecFactory.py forwards accepted profile unchanged;
  remove temporary G8-A rejection, no policy/bands resolution.
- existing application terrain/reliefObjects/bathymetry/floorProfile.py adds
  BasinFloorEvaluator(profile:FieldFloorProfile,*,topology:WorldTopology,
  coordinate_space:CoordinateSpace,grid:SurfaceGridSettings|None), sample(cell:Coord)
  ->FineZ. Terrain owns absolute floor math, existing public samplers own field;
  plate layout once per evaluator. Signed water wetness=-continental field F;
  round-half-up(depth*(1-F)/2), clamp depth>=1 and z>=z_min. Decimal(str(F))
  integer ratio prevents binary tie drift; this is independent of placement score.
- existing basinZ.apply_basin_z accepts explicit coordinate_space (default existing
  WORLD_SURFACE_GRID) and grid:SurfaceGridSettings|None=None for legacy scalar;
  field/coarse requires captured grid, fine uses centers x+.5/y+.5. Validate recipe
  topology against lifted coarse topology (or exact fine topology). Sampled space
  must match working frame. Existing scalar distance/bands unchanged; field/sample
  bypass distance bands, min absolute overlap, reserved untouched, transactional
  writes only after all specs evaluate. No hidden scale/default strategy/selection.
- existing relief/planning/reliefPlanProvider.py passes inputs.grid;
  reliefObjects/applyReliefObjectsZ.py accepts optional captured grid and forwards.
- existing planning/encoding/surfaceManifest.py appends IDs167..177 for two floor
  models, floor kind, three recipe models, strategy, three policies and operator.
  Existing dataModel/surfacePlanning/surfacePlanBindings.py::_declare accepts
  schema_version:SchemaVersion=1; WATER_PLACEMENT schema/cache2. Downstream refs
  invalidate via changed dependency key. No legacy/GEO parallel factory is added.
- tests/geo1/bathymetry/{__init__,fixtures,test_profiles,test_writer,test_transport}.py
  (5 files); update geo1/transport regression and planning valid/invalid typing;
  pyright valid config explicitly includes the application bathymetry folder.
Composition: application bathymetry5→5, dataModel bathymetry3→3,
relief planning2→2, reliefObjects6→6 WARN, hydrology root7→7 WARN,
encoding3→3, surfacePlanning3→3; new test folder5, existing transport2→2.
Schema2 verification updates the existing tests/planning/consumers/test_wiring.py
fixed revision/ref vectors and labels them G9 schema2 (consumer folder6→6 WARN).
The previous vector explicitly predates source/schema changes; actual current
vectors are captured with real bindings. No generic codec behavior is changed.
Schema1 control still yields capture revision d6417f... (old 941978... fixture
already stale before this schema bump); climate/terrain vectors stay exact.
Schema2 changes water input key and downstream dependency refs as intended.
Checks: GEO-1; existing bathymetry/water/placement/provider regressions;
planning consumer cache/codec and typing checks. Test formula/half ties/clamp,
all recipes/topologies, coarse/fine parity, no reselection, replay/idempotence,
reservations/overlaps, invalid frame/profile no partial writes, full codec profile
round-trip and water schema/cache2. G8-B remains OPEN until atomic G10-A.

### G9 — перенос accepted field в relief spec — DONE (2026-10-29)
Цель: представить принятый профиль через действующий single writer.
ТЗ: GEO-1 и tz_terrain_hydrology §Расположение кода / HY-12.
Файлы: dataModel/terrain/relief/bathymetry/basinSpec.py (перенесён в PC-1R),
existing basin factory и application profile/writer; old application
basinSpec.py остаётся re-export. Расширение того же spec строго в его
доменном контракте. Контракт: абсолютная запись accepted
профиля, per-body level, reserved cells, без z-write в strategy/hydrology.
Проверка: replay/idempotence, пересечения, горные reservations,
floor < level, clamp/invalid-input правила из G0.
Done: field не теряется при преобразовании в scalar BasinSpec.
Metadata/scalar consumer migration — G8; здесь перенос accepted profile
в единственный spec/writer, без потери profile и без повторного выбора bands.

G9 IMPLEMENTED/VERIFIED: accepted profile reaches the same BasinSpec/writer;
field/sample absolute floors, explicit frame/scale, reserved/min-overlap/replay;
water schema/cache2 and appended stable profile recipe type IDs.
GEO-1 487 passed (+15 bathymetry); legacy bathymetry/water/providers183 passed;
wiring/codec30 + selected L0 parity2 passed; pyright0, negative205/205; diff clean.
Full consumer L0/L2 discovery was interrupted after prolonged execution without
new output; not counted as passed. Fixed vectors refreshed with schema1 control
and unchanged climate/terrain vectors. G8-B remains assigned to atomic G10-A.

### G9-ST execution contract (2026-10-29)
No feature/coating activation; existing source closure is made immutable now.
TZ: §6.29-H/M; tz_materials §2, tz_terrain_relief R26/R32/R33,
tz_json_validation POJO/REF-W. Exact owner map before code:
- existing materials/materialRegistryEntry.py adds nullable enum substrate_kind;
  NEW materials/enums/materialSubstrateKind.py owns ROCK/LOOSE_SEDIMENT/OTHER.
  existing worldMaterialRegistry.py canonical fixture+engine declarations carry
  explicit classification from §6.29-H, custom rows remain None. No heuristics.
- existing terrain/relief/{reliefTemplate,reliefTerrainCondition,reliefRoleCase,
  reliefGradeKnobs}.py list fields become tuples, tuple defaults, overlap helper
  accepts tuple; frozen model revalidation enabled for these source bodies and
  existing MountainSideRecipe/ReliefDeltaBand (already immutable side pattern).
  JSON arrays/None/empty distinction preserved; no change to Mode A/B or refs.
- NEW dataModel/terrain/relief/surfaceCoating/{__init__,surfaceSupportInput}.py:
  frozen strict SurfaceSupportInput, MaterialSupportEntry,TerrainSupportEntry,
  LandcoverSupportPolicy as §6.29-H; immutable nested data, unique sorted keyed
  collections, actual full templates+memberUID. No domain computation/IO.
  Refinement: TerrainSupportEntry.hills_authored:bool and LandcoverSupportPolicy.
  terrain_policy_hills_authored:tuple[TerrainKey,...] are required derived facts.
  Existing has_authored_hills uses model_fields_set, which canonical encoding
  does not include; these explicit bits preserve omitted versus explicit None
  and prevent equal fingerprints for different domain behavior. SurfaceSupportInput
  also captures required masks_enabled:bool (raw parent gate); it is not folded
  into landcover.enabled in wiring. Global mask edits must change the input key.
  Presence flags and this parent gate are not
  persisted settings and do not apply policies inside wiring.
- NEW application/worldData/planning/composition/support/{__init__,surfaceSupportCapture}.py:
  SurfaceSupportCapture.capture(world_uid,*,seed,grid,topology,terrain:WorldTerrainRegistry,
  materials:WorldMaterialRegistry,masks:WorldTerrainMasks,region_states:tuple[RegionState,...],
  relief_policy:WorldReliefPickPolicy,templates:ReliefTemplateSnapshot,
  refine_policy:ParentLightRefinePolicy)->SurfaceSupportInput. Caller-owned pure
  projection, rejects foreign world membership, retains only supplied members,
  checks terrain_policy dictionary key equals value.system_terrain; no loader,
  apply_to, mill, world accessor, policy execution or generator calls.
- existing planning/encoding/surfaceManifest.py appends stable IDs for the new
  support source closure, full relief templates and immutable region/state models;
  old IDs/active schema unchanged (new input binding activates in G10-A).
- tests/geo1/support_sources/{__init__,fixtures,test_input,test_capture,test_relief}.py;
  existing planning valid/terrain/water.py + invalid.py/config includes the new
  application capture and contracts/changed source models.
Composition: relief root23→23 WARN, new surfaceCoating2, composition root5→5,
new support capture2, material enums2→3; new tests5, encoding3→3. Existing
material root count checked before edits; no new file added there.
Integration baseline repair: tests/test_relief_canonical.py imports smoke_003 from
the obsolete repo-root relief_templates path although the checked-in user fixture
is backend/relief_templates/smoke_003. Keep default-domain-root assertions; add a
separate explicit fixture source root for import/copy only. No runtime FS fallback
or default pack activation. This existing test file changes, no root file added.
Windows sandbox asyncio socketpair blocks before setUp; embedded SQLite integration
checks run outside sandbox (automatic review approved the test-only execution).
Checks: GEO-1, targeted material/relief/ref validation and library snapshot tests,
production codec closure/fingerprint edits, positive/negative planning typing,
diff check. G9-S provider/policy and G10-A capture activation remain separate.

### G9-ST — immutable источники доказательств surface support — DONE (2026-10-29)
Цель: typed template/material/region source closure для facts provider.
ТЗ: §6.29-H/M, tz_materials §2, tz_terrain_relief §R26/R32/R33,
tz_json_validation §POJO/REF-W. Файлы: surfaceCoating/surfaceSupportInput.py;
existing ReliefTemplate/MountainSideRecipe/ReliefTerrainCondition/
ReliefRoleCase/ReliefGradeKnobs collection fields §6.29-H;
materials/materialRegistryEntry.py, materials/enums/materialSubstrateKind.py,
materials/worldMaterialRegistry.py; caller membership-snapshot projection.
Контракт: typed source facts, tuple collections, unchanged JSON arrays,
один canonical material classification owner, нет live library IO в kernel.
Проверка: geo1/contracts и integration suites §6.29-L, template/member edit
меняет support fingerprint, same-view validation/runtime получают same facts,
нет REF-W regression после tuple conversion.
Done: G9-S получает весь explicit SurfaceSupportInput; отсутствие
material/recipe доказательства не подменяется consumer rock heuristic.

G9-ST IMPLEMENTED/VERIFIED: immutable full source closure + caller membership
projection; material-owned substrate enum/classification; tuple relief collections
with unchanged JSON arrays/None/empty; explicit parent gate/authored-presence bits.
GEO-1 505 passed (+18 support source checks), targeted material/relief/contracts/
wiring/codec119 passed, SQLite membership/canonical12 passed; pyright0,
negative209/209, diff clean. Test fixture import path fixed without runtime FS
fallback. New support binding/provider/policy activates in G9-S/G10-A as specified.

### G9-S execution contract (2026-10-29)
User authorized isolated implementation; activation remains atomic G10-A.
Owners/paths: dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py
owns immutable facts, enums, surface/support/coating outputs and resolved target;
surfaceCoatingPolicyDefinition.py owns ValuePolicy/case declarations
and metadata. Existing surfaceSupportInput.py adds mode/target input.
application/worldData/generators/terrain/relief/surfaceCoatingSupport.py
owns typed dependency binding, read-only facts and coating plan providers;
relief/surfaceCoating/{geometry,sources}.py own pure captured-source sampling,
using existing mountain side/region raster/precedence/scorer routines.
No live World, mill, library, pack, SQL or persisted L2 reads.
Dependencies use existing final HydrologyPlan and separate RiverReliefPlan;
GEO binding/schema activation and Geo transport are G10-A.
surfaceManifest appends IDs for the full isolated output closure; old IDs
and active versions stay unchanged. New tests/geo1/coating/ has at most
5 files; positive/negative planning typing gains this I/T pair.
Counts: dataModel surfaceCoating 2→4; application relief 1→2 with new
surfaceCoating leaf 3; tests coating 5. Checks: GEO-1, policy/compiler,
source/codec replay, planning positive+negative typing, diff check.
Unknown remains a typed issue in validation and runtime fallback; runtime
reporting is exposed by planning/validation/surfacePlanValidator.py::
SurfacePlanValidator.validate_coating for G10-A (new validation leaf 2 files).
SurfacePlanSlot keeps its exact eight-slot baseline; isolated support uses
SURFACE_SUPPORT_SLOT until the atomic GEO binding activation.

### G9-S — terrain-owned допустимость берегового покрытия — DONE isolated (2026-10-29)
Цель: исключить terrain/material покрытия на отвесной породе, сохранив SHORE.
ТЗ: GEO-1 G0; tz_terrain_hydrology §Derived shore;
tz_terrain_relief §Граница слоёв; HY-7 после синхронизации G0.
Файлы: dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py (SurfaceCoatingFacts);
terrain/relief/surfaceCoatingSupport.py (typed facts provider);
dataModel/terrain/relief/surfaceCoating/surfaceCoatingPolicyDefinition.py (terrain-owned
ValuePolicy/PolicyCaseDeclaration + field metadata → общий compile_value_policy → PolicySpec;
unknown/cases §6.11 разрешает общий PolicyResolver, не compiler/provider);
terrain/passes/columnFillPass.py;
hydrology/shore/shoreProfile.py (снятие чужой ответственности);
L0/L2 consumers по трассировке. Контракт: §6.1, terrain provider,
typed relief/material facts, unknown без local heuristic hydrology.
Проверка: SHORE сохраняется, rock terrain/material не затираются;
на допустимой поверхности применяется пара shore terrain/material;
нет запуска mill ради покрытия; §6.11 unknown validation error /
runtime WarningError с fallback, read-only world validation hook,
no-writes preview и L0/L2 parity.
Done: решение покрытия одно, hydrology — consumer; mountain geometry
и per-body level не меняются. Согласованная unknown policy реализована
на обоих путях, а не только в runtime materializer.

G9-S IMPLEMENTED/VERIFIED (isolated): captured-only facts, shared terrain policy,
typed unknown + KEEP_EXISTING_SURFACE with retained issues/reporting, full codec
closure and registry provider builds. Wrapped sides, state/tombstone and missing
member/structural/post-river evidence covered. GEO-1 525 passed (+20); planning
contracts71 + codec7 passed; pyright0, negative213 diagnostics/all211 annotations
covered, diff clean. Production L0/L2 consumers, aggregate capture/validation
injection, gates and schema activation remain G10-A; no mill/pack/DB reads/writes.

### G10-A prerequisite correction — AGREED / IMPLEMENTED isolated (2026-10-29)

Read-only readiness audit found an unresolved binding seam in §6.31-E.
`ClimateLocalPlanProvider` currently requires the PC final hydrology handle;
`surface.pc.climate_local` declares `surface.pc.hydrology` as its dependency.
GEO final hydrology has a different contract ID and payload type. Reusing the
PC local registration fails `PlanDependencyReader.validate_for/require`, even
though ClimateLocalInput/ClimateLocalPlan themselves do not change. Similarly,
G9-S support/coating constructors and SurfaceSupportDependencies currently use
the invariant PlanEnvelope[HydrologyPlan]/RegisteredPlanContract[...,HydrologyPlan].
The §6.31-E GEO envelope cannot be passed through those baseline annotations.
This is a dependency-contract correction, not an additional activation phase.

Agreed ownership/API amendment (user approval after domain-boundary clarification):
- dataModel surface-planning owner, existing
  `backend/app/dataModel/surfacePlanning/surfacePlanBindings.py`:
  SurfacePlanBinding stores explicit upstream contract metadata rather than
  deriving every dependency through the PC-only slot lookup. Keep baseline
  lookup and add `geo_surface_plan_binding(slot:SurfacePlanSlot)` over
  GEO_SURFACE_BINDINGS. Only climate_base/terrain_base reuse PC registrations;
  climate_local gets `surface.geo.climate_local` /
  `surface.envelope.geo.climate_local`, schema/cache 2, algorithm 1, with exact
  PC climate_base and GEO final hydrology dependencies. Other GEO registrations
  retain the target identities/dependencies in §6.29-M/§6.31-E.
- application climate owner, existing
  `backend/app/application/worldData/generators/climate/planning/climatePlanProvider.py`:
  parameterize ClimateLocalPlanProvider[H:HydrologyPlan]; constructor takes
  RegisteredPlanContract[HydrologyFinalInput,H]. Its build binds that exact
  handle and delegates unchanged local-climate computation to the existing kernel.
- application terrain/relief owner, existing
  `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py`:
  parameterize SurfaceSupportDependencies[H:HydrologyPlan],
  SurfaceCoatingSupportProvider[H:HydrologyPlan] and CoatingPlanProvider[H:HydrologyPlan].
  Hydrology envelope/handle fields consistently use H; GEO instantiation uses
  GeoHydrologyPlan, isolated baseline tests use HydrologyPlan. Coherence checks,
  evidence computation, policy resolution and diagnostics remain unchanged.
- application composition owner, existing
  `backend/app/application/worldData/planning/composition/planProviders.py`:
  bind the GEO local/support/coating instances to the same exact final GEO
  hydrology handle. No envelope reconstruction, type cast, widened object/Any,
  PC fallback or second facts/policy implementation.

Domain responsibility constraint (clarified with the user, 2026-10-29):
H preserves the exact registered envelope/handle type at the provider boundary;
it does not grant the consumer ownership of GEO hydrology operations. Provider
adapters validate upstream identity/coherence and pass the existing HydrologyPlan
payload interface to domain kernels. No new cross-domain DTO/protocol or copy of
the payload is introduced solely for this binding correction.

Audited producer/consumer field map (paths relative to backend/app):
- climate/planning/climatePlanProvider.py::ClimateLocalPlanProvider validates
  dependency refs; generators/climate/localFieldFromCoarse.py::
  build_local_plan_from_coarse reads only HydrologyPlan.coarse_surface_z and
  delegates to collect_resolved_local_anchors. Climate owns anchor/climate
  computation; no water classification, body association or coating selection.
  Both application paths have the worldData/generators/ prefix.
- generators/terrain/relief/surfaceCoatingSupport.py::shore_cells reads only
  coarse_hydro/sparse_fine_hydro (MapCellHydrology), preserving the final sparse
  override precedence. SupportSources in the existing surfaceCoating/sources.py
  uses the existing hydrology/materialize/hydrologyWorkingFields.py::
  HydrologyWorkingFields.from_plan projection: coarse_surface_z/coarse_hydro/
  fine_z_overrides/sparse_fine_hydro. This is read-only source evidence for
  existing landcover fact consumers, not a new hydrology calculation.
- SurfaceCoatingSupportProvider owns terrain support evidence: relief geometry,
  material/substrate and typed unknowns. CoatingPlanProvider uses final SHORE and
  shore_kind to select the captured target and resolves the terrain-owned policy;
  it does not classify water, change SHORE/body/level or carve heights.
- hydrology remains the sole owner of fill/classification/physical unions and
  source_mapping/classification_decisions. The owning attached-boundary operation
  may consume source_mapping for its explicit target association. Climate,
  support, coating and landcover kernels must not inspect either GEO-only field,
  branch on GeoHydrologyPlan identity or rerun generation/admission decisions.
- planning/composition/planProviders.py only binds exact handles; assembler only
  orders stages and passes refs. Neither selects climate anchors, derives support
  facts, evaluates coating rules nor computes hydrology mapping/classification.

Acceptance adds a field-access audit of those consumer paths and their delegated
kernels, including HydrologyWorkingFields.from_plan. For the same common payload
and coherent dependency refs, changing GEO-only mapping/classification metadata
must preserve computed climate anchors, support observations and coating actions/
targets. Artifact keys/refs and evidence fingerprints may change with upstream
provenance and invalidate caches; whole-envelope/payload equality is not required.
Integration tests use real handles; kernels keep their
HydrologyPlan argument type and cannot gain GEO-only field access via H.

Composition for these corrections: surfacePlanning 3→3; climate/planning 4→4;
terrain/relief 2→2; planning/composition 5→5. No new production modules.
Validation belongs to the already planned geo1/integration/test_activation.py
and test_revisions.py (leaf max5), plus existing planning typing fixtures:
GEO final→local→support→coating builds through real registered contracts;
PC envelope/handle rejection, coherent refs after cold/warm cache, changed
hydrology invalidates all three downstream artifacts, unchanged climate_base/
terrain_base stay HIT. Positive typing accepts exact GEO instantiations;
negative typing rejects PC/GEO handle substitution. Full G10-A activation and
its acceptance criteria below remain required; this audit does not close them.

Implementation boundary: explicit GEO metadata declarations and generic consumer
bindings are implemented, with the required GeoHydrologyPlan in the already
planned hydrology/planning/hydrologyPlan.py and codec IDs225–233 appended in
existing planning/encoding/surfaceManifest.py. New enum slots are declarations;
production register_world_plan_providers still registers the eight PC stages.
PC declarations retain their existing metadata lookup; GEO declarations store
explicit dependencies, so no GEO dependency is inferred through the PC lookup.
declared_binding in existing planProviders.py binds either explicit declaration
through the same validator/fingerprint/cache-codec mechanism.
Hydrology planning3→3, encoding3→3, slot declaration3→3; integration root3 new
files (init/test_activation/test_revisions), support/{init,fixtures}2. This leaves
the two planned validation/logging tests within the root limit5. Contracts tests4→4, typing
root4→4 and valid/terrain3→3. No new production modules or additional activation.
The frozen terrain_regions input contains all geometry/owner refs, hence its
metadata has no generated dependency; GEO water depends on terrain_base plus
terrain_regions. Other phase deps follow §6.31-E and the correction above.
Integration fixtures supply frozen upstream envelopes and execute the three
consumer providers via the real registry/cache. They do not claim production
capture, upstream generation or complete G10-A activation evidence.

Correction VERIFIED: GEO-1 532 passed (+7 seam tests), planning contracts71,
consumers85 and codec7 passed; pyright valid0, negative219 diagnostics/all217
expected annotations covered. Consumer suite requires execution outside sandbox:
Windows asyncio socketpair otherwise stalls in event-loop setup before test code.
PC production bindings/revision vectors remain covered; full G10-A stays OPEN.

### G10-A typed pipeline closure — IMPLEMENTED / VERIFIED (2026-10-29)

Implement the frozen §6.29-M/§6.31-E input/output contracts before caller wiring:
new dataModel terrain/planning/inputs/geoWaterPlacementInput.py and hydrology/
planning/inputs/geoHydrologyPlanInput.py own captured authored water/route inputs;
existing terrain/planning/waterPlacementPlan.py owns GeoWaterPlacementPlan,
hydrology/planning/hydrologyPlan.py owns GeoHydrologyRoutesPlan and final facts;
existing application planning/contracts/{surfacePlanningView,surfacePlanBundle}.py
own the independent GeoSurfacePlanningView/GeoSurfacePlanBundle with exact phase
types and coherence checks. Paths are under backend/app; application paths have
application/worldData/ prefix. WaterDesignDecision is the existing object-policy
specialization, named in hydrology/policy/hydrologyGenerationDecision.py.
No policy, cascade, geometry or placement algorithms belong to these records.
Register the complete concrete codec closure in existing surfaceManifest.py;
cover immutable input admission, mismatched mode/grid/topology/bounds/refs,
codec replay and static PC/GEO separation. Tests use the planned integration/
test_surface_validation.py and integration/support fixtures; root4→4 (future5),
support2→3; terrain inputs3→4, hydrology inputs2→3, all other counts unchanged.
Owning source schema and runtime activation remain one subsequent G10-A switch;
these contracts do not enable an alternate production path.

Verified: concrete codec IDs234–281 appended without changing IDs1–233;
full view/bundle/phase replay, nonempty placement variants and input/ref rejection.
GEO-1 545 passed (+13), planning contracts71/consumers85/codec7 passed; pyright valid0,
negative225 vs baseline219, all expected rejections covered, surplus unchanged.
Production source schema/capture/providers remain pending in atomic G10-A.

### G10-A boundary provenance correction — IMPLEMENTED / VERIFIED (2026-10-29)

Readiness replay found two concrete blockers: BoundaryWaterSnapshot requires an
exact direct water_placement dependency, absent from the frozen GEO final graph;
both boundary/policy snapshots reject the exact GeoHydrologyPlan envelope.
Amend §6.31-E before activation: GEO final deps add water_placement; PC final
remains unchanged. This is explicit accepted-placement provenance, not a second
fill or policy pass. Boundary deps remain (hydrology,water_placement).

Owner map, all existing files under backend/app:
- dataModel/surfacePlanning/surfacePlanBindings.py: GEO final declares the exact
  GEO water metadata. GeoHydrologyFinalPlanProvider in
  application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py
  takes the exact water handle, checks relief/routes/river refs before delegating
  common final facts to HydrologyFactsAssembler, and carries mapping/decisions
  unchanged. Registration remains part of atomic activation. prepare_geo in
  application/worldData/planning/composition/surfacePlanningAssembler.py passes
  the same water envelope. Neither copies geometry nor reevaluates admission.
- dataModel/hydrology/boundaries/boundaryWaterSnapshot.py and
  dataModel/hydrology/policy/hydrologyPlacementPolicy.py parameterize their
  existing snapshots by H:HydrologyPlan (default HydrologyPlan). GEO binds H to
  GeoHydrologyPlan; hydrology fields retain invariant PlanEnvelope[H].
  Boundary provenance checks the water_placement slot, not any matching ref.
- Existing application/worldData/generators/hydrology/boundaries/{boundaryGeometry,
  boundaryPlanner}.py, hydrology/policy/{hydrologyPolicyFacts,hydrologyPlacementBinding}.py
  and application/worldData/placement/adapters/coastline/attachedCoastline.py
  preserve H in their snapshot parameters/revalidation. Domain computation and
  policy execution remain with their current owners; no cast or envelope copy.

TZ: tz_terrain_hydrology §GEO-1; tz_map_light_bake §Placement; plan §6.16-A/§6.29-G.
Checks: geo1/integration/{test_activation,test_revisions}.py, the existing
planning provider architecture guard and planned typing fixtures
cover exact GEO final→policy→geometry→dependent P2, PC/GEO substitution, wrong
water ref/slot and bundle provenance. No new files; directory counts unchanged.
Done for this group: isolated seam verified; source/capture/provider activation
remain atomic G10-A deliverables; the final provider is implemented isolated.

Verified: GEO-1 555 passed (+10), planning292 passed; pyright valid0.
Negative230 vs baseline219, all227 expected annotations covered; surplus unchanged.
New final provider is isolated; production registration remains the eight PC stages.

### G10-A relief provider binding — IMPLEMENTED / VERIFIED (2026-10-30)

Goal: implement the frozen §6.31-E GeoReliefPlanProvider and
GeoRiverReliefPlanProvider before composition activation. TZ:
tz_terrain_generation §GEO-1/terrain layers; tz_terrain_hydrology §HY-12;
plan §6.16 J09/§6.31-E. Both are application terrain/relief boundary adapters in
existing backend/app/application/worldData/generators/terrain/relief/planning/
reliefPlanProvider.py. Exact GEO water/routes handles are required; adapters
validate upstream refs and delegate payloads to the existing terrain computation.
Shared _plan_relief and _plan_river_relief in that same owning module hold the
unchanged pre-river/profile recipes currently embedded in PC build methods.
Both PC and GEO adapters call those kernels; Geo river passes routes.payload.base.
No policy resolution, mapping inspection, envelope rebuilding or widened handle.

Files: the existing provider above; geo1/integration/{test_activation,
test_revisions}.py and support/pipeline.py; existing planned typing fixtures.
Check: real registry/cache builds, PC-equivalent basin/river geometry, receiver
preservation, wrong refs/PC handles rejected, cache replay and source immutability;
existing planning regressions and positive/negative type configurations.
Done: both exact GEO relief adapters verified; production registration remains
part of atomic G10-A. No new files; direct folder counts unchanged.

Verified: GEO-1 564 passed (+9), planning292 passed; pyright valid0.
Negative234 (+4 this group), all231 expected annotations covered; surplus unchanged.
PC-equivalent mountains/basins/coarse+fine beds, receiver preservation, exact refs,
cache replay and real GEO relief→river→final build verified; production still PC.

### G10-A final source mapping producer — IMPLEMENTED / VERIFIED (2026-10-30)

Goal: implement the existing §6.29-G/J10 producer before GEO route-stage wiring.
TZ: tz_terrain_hydrology §GEO-1/source-to-body mapping; plan §6.16-A/§6.29-G.
Owner: application hydrology final materialization, existing backend/app/
application/worldData/generators/hydrology/water/waterMaterialize.py. Its existing
MaterializedWater result gains required source_mapping:SourceBodyMapping.
materialize_water derives it from final wet occupancy after classification/remap:
for every supplied accepted spec (WaterSource.authored=True, including designed
procedural specs), inspect its footprint and collect sorted final physical body
UIDs of liquid_candidate cells. Explicit empty entry means accepted dry. Natural
sources discovered outside the supplied placement specs do not become accepted
placement entries. No UID-string equality inference or PhysicalWaterUnion IDs.
No second mapping DTO/helper module, fill, classification or geometry writer.

Existing waterBodyAssembler.py empty/error result supplies an empty typed mapping;
its union-parent normalization preserves the materializer result. Failed terrain
resolution does not claim that accepted sources are dry. Existing PC outputs and
cache schema are unchanged; GEO routes will consume materialized.source_mapping
inside the atomic G10-A join. SourceBodyMapping stays owned by dataModel/hydrology/
planning/sourceBodyMapping.py; no new files or independently persisted provenance.
Checks: existing geo1/integration/test_activation.py plus HY-12 regressions and
planning typing fixtures. Cover split/merge/tied ownership/dry SHORE/spill,
accepted dry and no accepted source, natural UID remap, topology/reorder replay,
immutable heights and final physical-body membership.
Done: real final fill produces canonical accepted-source mapping; route/provider
activation remains atomic G10-A. Direct counts: water10→10, hydrology root7→7,
integration4→4, typing terrain4→4; no new files.

Verified: GEO-1 573 passed (+9), planning292 passed; pyright valid0, negative235
(all232 expected annotations covered; diagnostic surplus unchanged).
HY-12 249 tests: same baseline2 failures/1 error reproduced with HEAD runtime
modules: coarse_snapshot injection missing in smoke/determinism, tuple/list
expectation in contract test. Route-stage consumption/activation remain pending.

### G10-A route-stage transport closure — IMPLEMENTED / VERIFIED (2026-10-30)

Readiness found missing route-stage transport: GeoHydrologyPlanInput cannot
resolve the root generation cascade without captured generation/defaults, while
OpenWaterPlan discards the mapping already produced by materialize_water.
TZ: tz_terrain_hydrology §GEO-1; plan §6.29-M/§6.31-E. Extend existing owners:
- backend/app/dataModel/hydrology/planning/inputs/geoHydrologyPlanInput.py adds
  required generation:WorldWaterGenerationSettings and defaults:WaterGenerationDefaults;
  no computed decisions or live source objects enter input. Existing
  application/worldData/planning/contracts/surfacePlanningView.py enforces
  equality with the captured GeoWaterPlacementInput generation/defaults.
  capture_geo will supply both projections from the same read view at activation.
- backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py adds required
  source_mapping:SourceBodyMapping; validator requires actual physical-body UIDs.
  application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py
  passes the exact materialized.source_mapping, with explicit empty mapping only
  for its disabled result. No second mapping computation or new DTO.
- Planned integration tests and typing fixtures verify missing/forged inputs,
  cross-phase mismatch, generation/default edit fingerprints/revision, source-map
  handoff and invalid physical UID rejection. Existing codec concrete types cover
  the added inputs; PC envelopes and eight production registrations stay unchanged.

Done: authored inputs and final water provenance survive the hydrology stage
boundary; GEO route policy/provider composition remains atomic G10-A. No new files.

Verified: GEO-1 579 passed (+6), planning292 passed; pyright valid0, negative236
(all233 expected annotations covered; diagnostic surplus unchanged).
Existing strict OpenWaterPlan fixtures now supply required explicit mapping;
classification policy/GEO route provider and production activation remain open.

### G10-A generation policy binding — IMPLEMENTED / VERIFIED (2026-10-30)

Route readiness requires one typed binding for the existing common cascade/value
policy, shared by category classification and body-source preparation. This
execution group does not activate source owners or the GEO production graph.
TZ: docs/tz_cascade_context.md §4 (extend), docs/tz_policy.md §5
(metadata/compiler); hydrology contract frozen in this plan §6.16 production decision ledger and §6.29-M captured inputs.
Owner: application hydrology policy. New exact file
backend/app/application/worldData/generators/hydrology/policy/hydrologyGenerationBinding.py:
HydrologyGenerationBinding holds compiled ValueSelectionPolicySpec, PolicyInputs,
PolicyFacts and resolved WaterGenerationContext. bind_hydrology_generation_policy
accepts required root enabled/generation/defaults/category settings and paths,
optional body settings. It delegates inheritance to extend/Link, compiles existing
HYDROLOGY_GENERATION_POLICY and binds root/context; only caller PolicyResolver
executes rules. No legacy category bool adaptation, World read, selection, fill,
placement or water-specific policy/cascade evaluator. Category binding stops at
CATEGORY; body binding extends WATER_BODY. Captured defaults are explicit.
Files: new binding above; existing tests/geo1/contracts/test_hydrology_generation.py
and positive/negative planning typing fixtures plus valid pyright include. Folder policy 3→4, contracts 5→5;
no new files in overfull directories. Verify cascade overrides/defaults, disabled
root, strict forged inputs, provenance/roundtrip and sibling isolation through
real PolicyResolver, then GEO/planning/type suites. Done: reusable exact binding
verified; route caller/provider activation remains G10-A.
Evidence: GEO-1 585 OK (+6), planning 292 OK; positive pyright 0;
negative 239 diagnostics (+3), all 236 expected annotations covered, baseline
surplus unchanged. git diff --check clean. Full G10-A remains OPEN.

### G10-A decision-driven water fill — IMPLEMENTED / VERIFIED (2026-10-30)

Goal: consume resolved generation decisions at the existing hydrology water owner,
without re-running legacy gates or reconstructing accepted geometry.
TZ: docs/tz_terrain_hydrology.md HY-12 / natural-only classification;
plan §6.16 water-fill ledger, §6.29-J activation, J10 accepted BasinSpec join.
Owner/layer/path: application hydrology, existing
backend/app/application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py.
WaterBodyPlanner.plan_geo accepts GeoHydrologyPlanInput, GeoWaterPlacementPlan,
complete canonical classification_decisions (existing category/decision tuple),
pre-river surface and control; returns existing PlanBuildResult[OpenWaterPlan].
Validate terminal decisions and exact input/placement topology before fill.
Accepted specs are already admitted: no enabled/autoresolve/category bool re-read
or spatial selection. DISABLED stops fill; active decisions preserve all accepted
specs (declared-only is not disabled). Natural-only lake discovery follows LAKE
AUTORESOLVE and captured allowed_body_kinds; sea/ocean discovery is false in GEO.
The existing PC plan retains its gates. Both entry points delegate one common
materialization helper for heightmap/policy construction, one kernel call,
diagnostics and exact final mapping; no new kernel, source model or cache DTO.
Tests: existing geo1/integration/test_activation.py and planning typing fixtures;
real binding/PolicyResolver decisions, one fill/no carve, dry mapping, invalid
inputs before kernel, legacy-gate independence, natural lake/sea behavior and
unchanged PC regressions. Folder water/planning 2→2; integration 4→4.
Done: isolated decision consumer verified; GEO routes provider and atomic
production activation remain open.
Evidence: GEO-1 593 OK (+8), planning 292 OK; positive pyright 0;
negative 240 diagnostics (+1), all 237 expected annotations covered, baseline
surplus unchanged. git diff --check clean. G10-A production path remains OPEN.

### G10-A GEO route assembly — IMPLEMENTED / VERIFIED (2026-10-30)

Goal: join decision-driven open water with the existing river/paint operations.
TZ: docs/tz_terrain_hydrology.md HY-12 / river planning; plan §6.29-M route-stage
producer and §6.31-E immutable phase contract. Owner/layer: application hydrology.
Exact existing paths under backend/app/application/worldData/generators/hydrology/:
- planning/assembly/hydrologyRoutesAssembler.py: HydrologyRoutesAssembler gains
  assemble_geo(world_uid, inputs:GeoHydrologyPlanInput, relief:ReliefPlan,
  placement:GeoWaterPlacementPlan, classification_decisions, control)
  -> PlanBuildResult[GeoHydrologyRoutesPlan]. It calls water.plan_geo once,
  delegates common coarse/fine/paint order to one shared method, and preserves
  the water stage's source_mapping and exact supplied classification decisions.
- rivers/planning/{coarseRiverPlanner,fineRiverPlanner}.py: existing owner plan
  accepts HydrologyPlanInput | GeoHydrologyPlanInput; only common captured river
  fields are read. No cast/reconstruction of GEO input into PC, new DTO, algorithm,
  river policy migration, policy evaluation or repeated fill/carve.
Tests: existing geo1/integration/support/pipeline.py extracts its accepted-water
GEO evidence helper for reuse; test_activation.py verifies real coarse/fine
routes vs PC, immutable heights/mapping/decisions, single stage ordering,
diagnostics and failure/shutdown boundaries. Existing positive/negative planning
typing fixtures verify exact GEO assembly/river inputs and reject PC placement.
Folders: assembly 3→3, rivers/planning 3→3, integration 4→4, support 3→3;
no new files. Verify GEO-1 + planning suites, valid/invalid pyright and diff check.
Done: isolated route assembly verified; provider generation/source-owner binding
and atomic production wiring remain open in G10-A.
Evidence: GEO-1 600 OK (+7), planning 292 OK; positive pyright 0;
negative 241 diagnostics (+1), all 238 expected annotations covered, baseline
surplus unchanged. git diff --check clean. G10-A production remains OPEN.

### G10-A captured category generation — IMPLEMENTED / VERIFIED (2026-10-30)

Readiness fact: isolated GEO inputs carry root generation/defaults but no sea,
ocean or lake category generation source. A provider cannot synthesize these
from old bool gates or use settings outside its input fingerprint.
TZ: docs/tz_cascade_context.md §4 (linked category sources), docs/tz_policy.md §5;
plan §6.29-M source capture / §6.31-E exact phase inputs.
Owner/layer: dataModel source projection; exact existing files
backend/app/dataModel/{terrain/planning/inputs/geoWaterPlacementInput.py,
hydrology/planning/inputs/geoHydrologyPlanInput.py}. Both add required
sea_generation, ocean_generation, lake_generation:CategoryWaterGenerationSettings.
These are immutable captured projections of normalized owning settings, not new
authored channels or computed decisions; root/body source ownership is unchanged.
No conversion from legacy enabled/autoresolve fields and no implicit defaults in
captured input. Atomic capture_geo will read the future owning category fields
from the same source view used for physical category knobs.
application/worldData/planning/contracts/surfacePlanningView.py requires exact
cross-phase equality. application/worldData/planning/encoding/surfaceManifest.py
appends existing CategoryWaterGenerationSettings at ID282; IDs1..281 unchanged.
Update existing geo1 integration fixtures, test_surface_validation.py and typing
fixtures. Folders: dataModel input leaves unchanged; composition/contracts and
encoding unchanged; integration 4→4; no new files. Verify required/strict/forged
inputs, per-category cross-phase mismatch, inheritance/override truth table via
real common binder/PolicyResolver, source revision/artifact key sensitivity and
codec closure. Run GEO-1, planning, positive/negative pyright and diff check.
Done: complete category-source capture contract; provider and production wiring
remain open. This amends §6.29-M with explicit category projections needed by
both placement and hydrology route requests.
Evidence: GEO-1 604 OK (+4), planning 292 OK; positive pyright 0;
negative 242 diagnostics (+1), all 239 expected annotations covered, baseline
surplus unchanged. Existing manifest IDs unchanged; only282 appended.
git diff --check clean. GEO routes provider / G10-A production remain OPEN.

### G10-A GEO routes provider — IMPLEMENTED / VERIFIED (2026-10-30)

Goal: produce the GEO route envelope from exact relief/water dependencies and
captured category sources, using existing common policy and domain assembly.
TZ: docs/tz_policy.md §5 (metadata/compiler/common executor),
docs/tz_terrain_hydrology.md HY-12; plan §6.16 water-fill ledger / §6.29-M.
Owner/layer/path: application hydrology planning adapter, existing
backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py.
GeoHydrologyRoutesPlanProvider(relief:RegisteredPlanContract[ReliefPlanInput,ReliefPlan],
water_placement:RegisteredPlanContract[GeoWaterPlacementInput,GeoWaterPlacementPlan],
assembler:HydrologyRoutesAssembler, policy:PolicyResolver) has build with exact
PlanRequest[GeoHydrologyPlanInput] -> PlanBuildResult[GeoHydrologyRoutesPlan].
Require typed deps and relief's exact water-placement ref before any policy/fill.
For canonical LAKE/OCEAN/SEA captured settings, delegate to existing
bind_hydrology_generation_policy and supplied generic PolicyResolver with the
captured resolution_mode; pass typed decisions to assembler.assemble_geo once.
No domain rule/algorithm, source default, World read, placement or carve in
provider; root/category/body algorithms stay in existing common engines/owners.
Tests: existing geo1/integration/test_revisions.py uses real registry/cache and
kernels; exact geometry/routing vs PC, cold policy calls / warm cache, category
and dependency edits, bad refs rejected before policy/fill, codec and actual
routes→river-relief→final chain preserving decisions/mapping. Update existing
planning provider boundary test and positive/negative typing fixtures.
Folders: hydrology/planning 2→2, integration 4→4; no new files.
Verify GEO-1 + planning suites, valid/invalid pyright and diff check. Done: isolated
GEO route provider verified; production composition/capture activation remains
atomic G10-A, with no PC registry switch in this group.
Evidence: GEO-1 611 OK (+7), planning 292 OK; positive pyright 0;
negative 244 diagnostics (+2), all 241 expected annotations covered, baseline
surplus unchanged. git diff --check clean. Production G10-A remains OPEN.

### G10-A terrain regions provider — IMPLEMENTED / VERIFIED (2026-10-30)

Goal: expose the existing pre-water region kernel through the declared cached
planning contract, retaining explicitly supplied identities.
Readiness fact: prepare_terrain_regions currently receives snapshot_uid and
world_region_uid outside TerrainRegionPlanningInput. The provider cannot use
hidden identities outside the key or mint replacements (§6.3 identity rule).
TZ: docs/tz_terrain_generation.md GEO-1 region extent; this plan §6.3 / §6.29-M
and exact provider method §6.31-E. Owner/layer/path:
- dataModel terrain, existing terrain/regions/regionPlanningInput.py:
  TerrainRegionPlanningInput gains required snapshot_uid, world_region_uid:EntityUid,
  moving the already required kernel identity parameters into one frozen input.
- application terrain, existing generators/terrain/regions/regionExtent.py:
  prepare_terrain_regions(world:RasterWorld,*,inputs:TerrainRegionPlanningInput)
  reads these identities from input; all direct callers migrate together.
  TerrainRegionPlanProvider.build accepts exact PlanRequest[TerrainRegionPlanningInput],
  PlanDependencyReader,PlanBuildControl and returns PlanBuildResult[TerrainRegionPlan].
  It delegates once to that kernel using request.key as its existing RasterWorld
  projection (world_uid/seed_root); no World read, UID mint, new DTO or geometry.
  Registered terrain_regions binding has no dependencies. Shutdown checked before/after.
Exact application paths relative to backend/app/application/worldData/; input
path relative to backend/app/dataModel/. Capture remains responsible for freezing
its supplied phase/world-region identities, rather than choosing them inside cache.
Tests: existing geo1/regions/test_extent.py, integration/support/pipeline.py and
integration/test_revisions.py; positive/negative planning region/GEO typing fixtures.
Verify real registry/cache, kernel parity/codec, warm reuse, identity/geometry key
invalidation, absent world extent (no AABB fallback), canonical topology and
failure/shutdown boundaries. No new files (region application 4→4, model 5→5,
region tests 4→4, integration 4→4). Run GEO-1/planning/type checks and diff check.
Done: isolated region provider verified; atomic capture/composition remains open.
Evidence: GEO-1 618 OK (+7), planning 292 OK; positive pyright 0;
negative 245 diagnostics (+1), all 242 expected annotations covered, baseline
surplus unchanged. git diff --check clean. Production G10-A remains OPEN.

### G10-A — атомарное включение GEO-1 production path
Цель: включить согласованные контракты без промежуточной потери объектов.
ТЗ: §6.29-J/M, G0 normative sections и tz_map_light_bake §Placement.
Файлы: owning seas/lakes/worldHydrology/source POJO, worldRow normalization,
surfacePlanningCapture/Assembler/planProviders, waterPlacementPass,
placement resolver/prepared/dependency queue, HydrologyGeneratorService,
затронутые masks gates и production call sites ledger §6.27.
Контракт: одновременно positive defaults/new channels/source dispatch/
common admission/one placement/floor writer/final mapping; старые gates
удаляются. Versions меняются; old envelopes не маскируются под новые.
Owning policies подключают существующие metadata/descriptor; production caller
компилирует spec по explicit source types и передаёт typed instances resolver.
Повторное чтение enabled/autoresolve после execution decision запрещено;
точный remaining legacy gate inventory — tz_policy §7.
Prerequisites — полный список §6.29-J, включая G9-ST и isolated G9-S.
G8 prerequisite: G8-A/leaf contracts complete; G8-B join/removal is implemented
inside this atomic step before activation, per dependency audit above.
Проверка: geo1/integration test_activation.py + test_revisions.py и
existing regressions §6.27; declare priority=None не исчезает из-за old0,
authored0 отключён, autoFalse не включает implicit ocean, field0=plate,
source coastline auto создаёт body, dependent boundary не делает carve.
Done: единственный новый production path активен, rollback/schema
behavior явное; не остаётся временного legacy switch/fallback chain.

### G10 — pipeline и доставка высот
Цель: встроить подготовку/resolve/relief до HY-12 и провести высоты в L0/L2.
ТЗ: GEO-1, tz_map_light_bake §Coarse planning ↔ light compose,
tz_terrain_hydrology §HY-12. Файлы: application/worldData/planning/composition/
surfacePlanningAssembler.py, domain providers и актуальные relief/light
consumers. Old surfaceTerrainContext — только compatibility seam.
Prerequisite: G10-A. Контракт: порядок §5/§6.29-M и сохранение нужных snapshots.
Граница input/revision и future platform compatibility — G0-S/§6.15;
нет самостоятельного snapshot/patch storage в terrain или hydrology.
Planning/materialization разделены по §6.20: после edit обновляется layout;
L0/L2 consume готовую актуальную revision только по запросу, без re-placement.
Проверка: мир без declare при явном auto; coastline water_source +
auto=True e2e создаёт тело (перенесено из G5-C2 — требует G6/G9);
auto off; body overrides;
natural-only regression; одинаковый результат full/partial и повторного bake;
offline L0/L2 evidence. Done: новые океаны видны на продуктовых путях.

### G10-R — отчёт целевой и фактической доли воды
Цель: показать фактическую площадь после fill без коррекции мира ради процента.
ТЗ: GEO-1 G0, Q-TARGET, §5.2-J.
Файлы: terrain/designedWater/coverage/coverageReport.py и existing diagnostics/result
boundary. Контракт: build_water_coverage_report(final_water, regions, *, budgets),
target/actual с одинаковыми единицами, final union без dry SHORE.
Проверка: overlap/merge, authored превышение цели, reserved islands,
full/partial одинаковый полный report, immutable heights/placement result.
Done: отчёт показывает отклонение, не запускает повторный carve/placement.

### G11 — итоговая приёмка и downstream seam
Цель: подтвердить весь GEO-1 и описать вход HY-RIV-1 без реализации рек.
ТЗ: GEO-1, HY-12, Placement P1/P2, cascade §8.
Файлы: acceptance evidence и план, downstream interface documentation.
Контракт: §6.10 обязателен для целевого HY-RIV-1 — actual fine/L2 surface
provider, frozen pre-river base, bounded fine search и explicit radius;
source intent → dependency receiving body → existing routing;
legacy producer остаётся до отдельного решения.
Проверка: planar/wrapped/sphere, все стратегии, 60% fallback/overrides,
обязательная runtime fallback logging emission через existing project
facade/domain sink и штатная generation transcript доставка (§6.12),
autoresolve False/True/None, world/body provenance, worker/hash-seed replay,
HY-12/placement/cascade regression. Команды точных suites закрепить после
разбиения новых тестов; не объявлять HTTP evidence без разрешённого запуска.
Done: согласованные критерии выполнены; отдельные HY-9/10/RIV не закрыты
ложно; план переименован в -done только после реализации и приёмки.
