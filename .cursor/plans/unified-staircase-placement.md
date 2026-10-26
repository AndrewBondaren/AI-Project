# Единое размещение лестниц — атомарный план передачи

Статус: проект плана, не согласован к имплементации. Дата: 2026-10-02.
Задача: включить внутреннюю и внешнюю fixed vertical_ladder в существующий
механизм размещения лестниц, без отдельного параллельного плейсера.

## Обязательный предшествующий план — выполнен

`.cursor/plans/structure-wall-materials-done.md` выполнен и принят
2026-10-04. Контракт происхождения стен живой: классификатор
`generators/structure/wallRegions.py` → `WallRegion` (dataModel/locations/
structure/wallRegion.py), selector `wallMaterials.py` → `WallMaterialPlan`,
консьюмеры `application/economy/materialPolicies/`. Использовать их, не
вводить второй классификатор и не переопределять внешнюю оболочку.

Baseline S1 переснять после принятого исправления материалов (все материалы
уже отражают §8.7.1: shell → здание, перегородки → выбор политики §11).
Ранее записанные hashes и число ERROR — историческая справка, не готовый
эталон после изменения.
Использовать согласованный контракт происхождения стен из
`docs/tz_building_generator.md §8.7.1`, не вводить второй классификатор.

## Правила исполнения

Основание: `.cursor/rules/code-gates.mdc`, `refactor-safety.mdc`,
`dataModel-no-hardcode.mdc`, `class-size-limit.mdc`, `layer-boundaries.mdc`.
Один заход = один шаг ниже: изменение → проверки → короткий отчёт → ожидание
«ок» мастера. Не объединять шаги. После согласования не менять состав молча.
Каждый новый факт требует явной правки плана и сообщения мастеру.
Этот файл не является командой начать кодить; нужна явная команда мастера.

**Любое непредусмотренное изменение UShape — критическая регрессия.**
При несовпадении baseline шаг НЕ Done. Найти и устранить причину, не обновлять
ожидания ради зелёных тестов, не ослаблять валидаторы, не делать silent fallback.
Known expectedFailure сохраняется; его исправление не входит в эту работу.

Сначала проверить git status. Сохранить текущие изменения B4 и пользователя;
не делать reset/clean, не начинать backend, не создавать коммит без команды.
Не создавать новый чат/агента автоматически. План предназначен следующему агенту.

## Принятый контракт мастера

- Общий плейсер не знает тип потребителя и не ветвится по staircase_type.
- Каждая лестница нормализует свои требования: размещение внутри/снаружи,
  конкретная зона комнаты, конкретный facing, примыкание к стене, ограждение,
  требуемый footprint и clearance. Плейсер потребляет эти требования.
- Размер/геометрическая вместимость проверяются до записи клеток лестницы.
  Проверка пригодности размеров для конкретного марша остаётся у его потребителя.
- Center + явное требование примыкания к стене: ERROR с подробным контекстом,
  игнорировать требование примыкания. Не смещать центр молча.
- **Актуальное решение S0 о материалах:** существующая стена НЕ переписывается
  на любом Z комнаты. Для собственного ограждения у внутренней стены повторять
  материал host-комнаты; у внешней стены полностью повторять материал фактической
  внешней стены. Не использовать step_material для стены. Если материалы внешней
  стены различаются по клеткам/Z, сохранить фактическое распределение, а не один
  материал по bbox. Настройку override мастер отменил; новое поле не добавлять.
  has_walls остаётся переключателем ограждения; наличие resolved-материала само
  по себе не включает стены и не является признаком authored-настройки.
- Явно заданный center сохраняется и при отсутствии собственного ограждения;
  одновременное требование примыкания игнорируется с ERROR. Подходит любая
  фактическая стена host-комнаты — внешняя или внутренняя; её геометрия,
  происхождение, материал и проёмы сохраняются по всей высоте Z.
- Внутренняя верхняя stop-комната выравнивается по origin XY предыдущего stop.
  Без уменьшения/переноса ради fit. Невместимость → ERROR + target skip,
  включая required=true; лог staircase/from/to/этажи/геометрия/причина.
- Внешнее размещение также входит в общий механизм; сохранять действующий
  EdgeMounted и геометрические ограничения внешней vertical_ladder.

## Нерешённые вопросы — обязательный S0

1. **Решено мастером, последнее уточнение имеет приоритет:** override не нужен.
   Существующие стены не переписываются. Материал собственного ограждения
   наследуется от комнаты при внутренней стене, от фактической внешней стены
   при внешней. Отдельный authored wall_material и override-поле не вводятся;
   существующий has_walls сохраняется. Runtime material truthiness не определяет
   режим размещения или наличие ограждения.
2. **Решено мастером:** center + отсутствие материала → сохранять center.
   Примыкание, если требуется одновременно, игнорировать с ERROR; перенос запрещён.
3. **Решено мастером:** для примыкания подходит любая фактическая стена host-комнаты,
   включая внутреннюю. Не требуется, чтобы стена была наружной оболочкой здания.
4. Для vertical_ladder включение общего внутреннего размещения определяется
   in_a_room=true или её обычным on_the_edge=false? Как сохраняется старый wire,
   где in_a_room не указан? Не менять эти defaults/приоритеты самостоятельно.
5. Что считать размером vertical_ladder при has_walls: тело 1×1, оболочка и
   clearance должны быть отдельными требованиями. Не объявлять техническую
   комнату 3×3 вместо лестницы 1×1 без согласования.
6. Для зон: текущий embed_at допускает только четыре угла и center. Нужны ли
   кардинальные зоны у середины стены? Это новое wire-поведение, не подразумевать.

## Текущее состояние — проверить перед работой

- shaftPlacer.py содержит ShaftPlacer, EmbeddedShaftPlacer,
  AdjacentShaftPlacer, EdgeMountedShaftPlacer и make_shaft_placer.
  Docstring «EdgeMounted TODO» устарел: реализация существует.
- instantiate_shaft_rooms создаёт runtime-комнаты для straight/u_shape/spiral;
  для vertical_ladder/external_vertical_ladder отдельной shaft-комнаты нет.
- verticalLadderHelper.py содержит отдельные _compute_vertical_ladder_anchor
  и _anchor_outside; внутренний поиск может fallback без фильтрации.
  Независимые min(xs), min(ys) не гарантируют членство пары в valid-кандидатах.
  Не переносить эту ошибку в общий контракт. Новые правила ladder требуют
  проверенного результата и ERROR/skip при невозможности, а не такого fallback.
- embeddedUpperLayout.py содержит B1: выравнивание, fit, блокировку clipping/trim,
  подробный ERROR и исключение target. Требует runtime shaft; это надо обобщить
  без превращения ladder в фиктивный is_shaft-объект.
- B4: runtime shaft_has_walls, внутренние open-перегородки не строятся,
  exterior shell сохраняется; автоматические арки только has_walls=true.
- Реальные builders: UShape, fixed vertical_ladder, fixed external_vertical_ladder.
  straight/spiral и movable ladder — заглушки; их пути не реализовывать здесь.
- Последняя проверка: 240 tests OK, 1 существующий expectedFailure;
  13 stdlib templates, 8 ERROR, deterministic ×2.
  `.local/shaft_walls_after.json` и `.local/shaft_walls_tests.log` — справочные
  артефакты, могут отсутствовать у следующего агента; baseline переснять.

## Итоговая архитектура

Один публичный шов размещения на базе существующего ShaftPlacer/factory.
Реестр builders/адаптеров потребителей нормализует StaircaseSpec и создаёт
typed PlacementRequest. Имена DTO ниже предлагаемые, фиксируются в S0/S2.

- PlacementRequest: host/stop identities и геометрия, body footprint,
  envelope/clearance, XYZ диапазон, mode, zone, facing, attachment policy,
  enclosure policy и источники наследования wall material, deterministic seed context.
  НЕТ staircase_type, builder-класса или callback, маскирующего type-dispatch.
- PlacementContext: фактические room/building footprints, занятые объёмы,
  сведения о стенах и проёмах по Z, bounds и building_uid. Общий код не ищет
  subtype в сыром wire и не выбирает размеры конкретной лестницы.
- PlacementResult: проверенные body/envelope координаты, resolved facing/entry,
  actual host, сохранённые wall regions и собственное ограждение. Failure содержит
  структурированную причину/геометрию; caller добавляет staircase/from/to в лог.
- Embedded/Adjacent/EdgeMounted остаются стратегиями единого плейсера.
  Новый общий геометрический helper допустим внутри этого механизма;
  второй orchestration entry point рядом с ним недопустим.
- B1 становится потребителем этого результата и проверяет upper-host независимо
  от вида лестницы. Ladder может иметь body 1×1 без технической shaft-комнаты.
- Стены host/здания и собственное ограждение различаются по происхождению.
  location_uid=building_uid и is_structural сами по себе этого не различают.
  Не выводить wall ownership только из общего bbox или названия материала.
- Общий wall writer пишет только собственное ограждение с наследованным материалом.
  Существующие стены сохраняются по всему диапазону Z без material override.
  Геометрия стены сохраняется; изменение существующего прохода
  выполняется отдельно по согласованному passage-контракту.

Data flow serial: typed spec → требования потребителя/preflight → существующий
плейсер → upper-host contract → клетки здания → builder потребляет placement →
проходы/валидация → сборка. Никаких сетевых вызовов, persistence или нового RNG
в плейсере. Порядок side effects UShape и выбор углов не изменять.

## Проверки, обязательные для каждого production-шага

Рабочая директория для unittest — `E:/AI Project/backend`;
Python — `./.venv/Scripts/python.exe`, не старый `venv`.

U-гейт U: `./.venv/Scripts/python.exe -m unittest tests.test_u_shape_orientation_baseline tests.test_u_shape_facing tests.test_structure_orientation tests.test_debug_structure_rotations tests.test_embedded_shaft tests.test_embedded_upper_layout tests.test_shaft_walls`.

Sweep W из корня: `backend/.venv/Scripts/python.exe .local/rooms_pojo_sweep.py .local/unified_placement_<step>_after.json`.
Сравнить SHA256 cells/passages И ТОЧНЫЙ список ERROR с baseline S1;
13 templates, те же 8 ERROR, deterministic ×2. Число ERROR без сравнения состава
не доказывает отсутствие регрессии. Добавить сравнения runtime XY/facing/якорей,
поскольку sweep их не включает. Проверять не только stdlib seed.
Если переход ladder по новому контракту намеренно меняет её результат, заранее
перечислить в ТЗ/плане конкретные случаи и причину; UShape должен остаться идентичен.
Не маскировать новые ошибки обновлением stdlib baseline. Изолировать причины.

После изменений: compileall изменённых модулей, git diff --check.
Не добавлять тесты, просто повторяющие implementation branches; нужны проверки
наблюдаемого размещения, защиты стен и непрерывности пути.

## Атомарные шаги

### S0 — Зафиксировать доменный контракт (только документация)
- **Цель:** разрешить вопросы выше и сделать ТЗ однозначным до кода.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §2, §8.1, §9, §12 «Архитектура: ShaftPlacer»; уточнить §12.1 «Единое размещение лестниц» внутри архитектурного раздела (в документе уже есть повтор номера 12 — не делать общий renumber).
- **Файлы:** названное ТЗ и этот план.
- **Контракт:** зафиксировать наследование wall material без override, has_walls, зоны, facing, внутреннее/внешнее включение ladder, collision/skip и смысл wall ownership; отделить принятые решения от вопросов.
- **Проверка:** сопоставить каждое правило с typed spec и действующими потребителями; код/тесты/fixtures не менять.
- **Done:** ответы мастера записаны в ТЗ; новые поля/defaults утверждены. До этого S2–S10 не готовы к реализации.

### S1 — Зафиксировать критический baseline UShape (только проверки)
- **Цель:** получить воспроизводимый эталон до миграции API.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §2 «facing», §3, §6 «Тип: u_shape», §8.1, §9; [tz_building_generator.md](<E:/AI Project/docs/tz_building_generator.md>) §8.8.
- **Файлы:** новый backend/tests/test_stair_placement_baseline.py, fixtures только при необходимости; .local/baseline-артефакты.
- **Контракт:** production-код не меняется; snapshots включают runtime XY/facing/entry, anchors, пути ступеней/площадок, cells/passages, точные диагностики.
- **Проверка:** U и W; четырёхсторонние повороты, square/rectangle, single/multi-march, несколько floors, previous-anchor, embedded corner/center, adjacent/external, open/closed, несколько deterministic seeds; внешняя ladder с тоннелем и люком.
- **Done:** сохранены baseline и команды воспроизведения; существующий expectedFailure явно помечен, не исправлен.

### S2 — Ввести typed-контракт общего размещения (только dataModel)
- **Цель:** выразить требования и результат независимо от типа лестницы.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §12.1 (добавлен как целевой контракт, согласование завершается в S0), §2.
- **Файлы:** новый backend/app/dataModel/locations/structure/staircasePlacement.py и tests/test_staircase_placement_contract.py; staircaseSpec.py только для полей, утверждённых S0.
- **Контракт:** PlacementRequest/Context/Result/Failure; body отдельно от оболочки/clearance; typed enclosure policy и источники wall-material наследования, без нового material override поля; enum policies и defaults живут в dataModel.
- **Проверка:** unit-контракт с произвольным потребителем без staircase_type; immutable inputs; guards center+attachment, material policy; compileall.
- **Done:** DTO фиксируют все решения S0, без импортов builders/генераторов в dataModel и без production-routing.

### S3 — Адаптировать существующую точку входа (только facade)
- **Цель:** дать существующему ShaftPlacer единый typed-вход с сохранением U-поведения.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §12, §12.1.
- **Файлы:** staircase/shaftPlacer.py, один локальный compatibility adapter, tests/test_stair_placement_facade.py (пути под backend/app/application/worldData/generators/structure).
- **Контракт:** facade принимает typed-запрос; старый make_shaft_placer и действующие callers делегируют через совместимый adapter. Старые signatures/imports сохранять до явной миграции usages.
- **Проверка:** U, W, baseline S1; новый вход реально вызывается старым caller, без повторного расчёта размещения и потребления RNG.
- **Done:** одна точка маршрутизации, существующие три стратегии; точное равенство U baseline.

### S4 — Обобщить Embedded-стратегию (только внутреннее размещение)
- **Цель:** разместить произвольный body/envelope в host без знания вида лестницы.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §2 embed_in/embed_at, §12.1.
- **Файлы:** EmbeddedShaftPlacer и его helper в staircase/, tests/test_embedded_placement.py.
- **Контракт:** потребляются zone/facing/attachment и фактический footprint; body 1×1 допустим по capabilities запроса, правило shaft>=3 остаётся требованием U-адаптера, не глобальным правилом.
- **Проверка:** произвольные geometry requests, corner/center, concave host, clearance, collisions; center+attachment диагностируется по S0; U/W/S1.
- **Done:** общий внутренний алгоритм единственный; legacy Embedded caller использует его, а U baseline идентичен.

### S5 — Обобщить EdgeMounted-стратегию (только внешнее размещение)
- **Цель:** включить внешний поиск ladder в существующий внешний плейсер.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §8.1 To-anchor-first/угловое ограничение/тоннель, §12 EdgeMounted, §12.1.
- **Файлы:** EdgeMountedShaftPlacer/helper, verticalLadderHelper.py для delegation старого внешнего API; tests/test_external_placement.py.
- **Контракт:** общие геометрические операции; разные требования body/enclosure/corners/entry передаются запросом. Смысл U-facing и внешнего ladder-facing нормализуют их адаптеры, общий resolver не смешивает их.
- **Проверка:** прежние внешние U и ladder anchors, все cardinal sides, запрет external corner, cellar tunnel, occupancy; U/W/S1.
- **Done:** старый _anchor_outside делегирует единому механизму; дублированного external-поиска нет, baseline U идентичен.

### S6 — Обобщить B1 upper-host contract (только выравнивание этажей)
- **Цель:** проверять верхний host для любого placement без обязательной shaft-комнаты.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §2 B1, §12.1.
- **Файлы:** staircase/embeddedUpperLayout.py, его вызов в structureGeneratorService.py, tests/test_upper_placement_contract.py.
- **Контракт:** проверка принимает PlacementResult с footprint/XYZ; физическая shaft-комната и body-only ladder не смешиваются. Сохраняются ERROR+skip, запрет clip/trim/re-place и dependency order.
- **Проверка:** 1×1/оболочка, три floors, cellar→ground, конфликт двух placements, source/target отсутствует, count ambiguity; U/W/S1.
- **Done:** B1 реально потребляет общий result; для U сохраняются coordinates, diagnostics и failure effects.

### S7 — Реализовать защиту чужих стен (только контракт записи ограждения)
- **Цель:** собственное ограждение не заменяет существующие стены здания/host.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §2 has_walls и решения material из S0, §8.1, §12.1.
- **Файлы:** общий geometry/wall-ownership helper, cellBuilder.py и staircase/base.py как потребители, tests/test_staircase_wall_ownership.py.
- **Контракт:** wall regions/provenance по фактическому контуру и всем Z; writer НЕ переписывает existing wall-клетки. Собственное ограждение повторяет материал комнаты у внутренней стены и материал внешней стены у внешней. Ownership/геометрия/openings сохраняются. Нет subtype-dispatch в writer.
- **Проверка:** несовпадающие материалы ступеней/host/exterior, отсутствие собственного ограждения, corner/center, внутренние перегородки и exterior, разные heights, материал меняется на промежуточном Z, точная неизменность существующих стен внутри и вне зоны примыкания; U/W/S1.
- **Done:** полная Z-защита подтверждена; U не теряет стены/арки/clearance, новая политика применяется лишь к заранее согласованным случаям.

### S8 — Добавить требования fixed vertical_ladder (только адаптер потребителя)
- **Цель:** выразить размещение ladder общим typed-запросом вместо специальных эвристик плейсера.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §8.1, §12.1.
- **Файлы:** адаптер/geometry provider verticalLadder, существующий registry потребителей, tests/test_vertical_ladder_placement_request.py.
- **Контракт:** вычисляются body/enclosure/clearance, zone/facing/attachment, upper-host, policies S0. Тип выбирает существующий registry, НЕ общий плейсер.
- **Проверка:** явные/omitted поля, trapdoor alias, has_trapdoor/near_wall/on_the_edge, no material/center conflicts; builder-specific preflight до любой записи клеток.
- **Done:** adapter вызывается через registry и даёт валидный запрос; никакой искусственной shaft-комнаты для передачи 1×1.

### S9 — Подключить внутреннюю fixed ladder (только внутренний consumer)
- **Цель:** builder использует проверенный placement без своего внутреннего поиска позиции.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §8.1, §12.1.
- **Файлы:** verticalLadder.py/verticalLadderHelper.py, staircase/base.py и caller/service для передачи result, tests/test_vertical_ladder_embedded_placement.py.
- **Контракт:** builder получает resolved anchor/geometry; исключены fallback без фильтрации и min(xs)/min(ys). Fit-failure → подробный ERROR+skip согласно ТЗ; никаких silent relocations.
- **Проверка:** оба floors/1×1/ограждение/люк, doorway proximity, headroom, upper-size отказ, target отсутствует в результате; U/W/S1.
- **Done:** production internal ladder реально проходит общий плейсер и B1; старый внутренний поиск не вызывается, U baseline идентичен.

### S10 — Подключить внешнюю fixed ladder (только внешний consumer)
- **Цель:** внешний builder использует результат EdgeMounted без второго поиска.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §8.1, §9, §12.1.
- **Файлы:** externalVerticalLadder.py и external caller/helper, tests/test_vertical_ladder_external_placement.py.
- **Контракт:** anchor из общего result; tunnel/passage builders остаются потребителями, не плейсерами. Существующие external flags/facing не переосмысливаются.
- **Проверка:** четыре sides, non-corner, z_lo<0 tunnel, closed_exit, сохранение building walls, no-fit ERROR; U/W/S1.
- **Done:** обе ladder разновидности используют единую точку размещения; external U baseline идентичен.

### S11 — Закрыть миграцию (только проверка и документация)
- **Цель:** подтвердить отсутствие параллельных механизмов и критических регрессий.
- **ТЗ:** [tz_staircase_generation.md](<E:/AI Project/docs/tz_staircase_generation.md>) §12.1 и затронутые разделы.
- **Файлы:** этот план, ТЗ и structure-technical-debt.md; production-код не править в этом шаге.
- **Контракт:** найти usages старых API/reexports/registry/fixtures; каждое либо compatibility delegation, либо migrated caller. Если найден кодовый хвост — шаг не Done, явная правка плана, отдельный атомарный шаг.
- **Проверка:** полный ранее применявшийся unittest набор с новыми тестами, compileall, diff --check, U/W/S1; exact diagnostics, wire immutability, deterministic×2.
- **Done:** все шаги приняты мастером; все непредусмотренные U differences отсутствуют; задокументированы только согласованные изменения ladder. Переименовать план в unified-staircase-placement-done.md и отметить Done в H1; обновить ссылки. Не реализовывать movable/straight/spiral и другие пункты technical-debt в этой миграции.
