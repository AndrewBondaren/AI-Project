# Structure generator — технический долг (находки POJO-миграции)

Инвентарь отложенных проблем, собранный за срезы `entry-point-pojo-done.md`
(E1–E3, 6.1–6.11). Каждый пункт — самостоятельный срез при реализации;
группировка только для обзора. Правило: срез → отчёт → «ок» мастера.

## A. Layout / размещение

| # | Проблема | Источник | Размер |
|---|---|---|---|
| A1 | **Реализован 2026-10-02:** layout проверяет наружную стену обоих входов, ищет смещения вдоль края, защищает уже размещённые входы; runtime fallback с WARNING, отсутствие периметра → GenerationError | entry-point-pojo §4 п.4 | сдан в working tree |
| A2 | **Реализован 2026-10-01:** WARNING при явном `perimeter_required: false` + entry_point/back_entry_point; форсинг True сохранён | ТЗ §286, roomFactory | сдан в working tree |
| A3 | **«no space» варнинги mode_a/mode_b — WARNING**: геометрический fit, не authored-ссылка — оставлены WARNING осознанно; если мастер решит иначе — политика уровней для fit-пропусков | §6.8 scope | вопрос |
| A4 | **`attach_wall` группы берётся от `group[0]`**: комнаты в одной attach-группе (общий `attach_to`) с разными `attach_wall` — используется значение первой. Легально или нет — решить: либо ERROR на разнобой, либо задокументировать | ревизия §6.6 | вопрос |
| A5 | **Z-посадка — единый сдвиг**: здание садится на террейн одним `dz` (`map_z`/`ground_z` + `translate_layout(...,0,0,dz)`; clamp только по уклону подхода `clamp_near_z_to_45`). `foundation_depth` униформен по периметру — на склоне внутри footprint здание висит/утопает; conformance к террейну есть только у street-approach, не у самого здания. Нет: per-column подгонки, подпорных стен/цоколя перепада, мульти-якоря по углам footprint | `structureAreaAssembler` (255–285), `foundationBuilder` | средний |

## B. Лестницы / шахты

| # | Проблема | Источник | Размер |
|---|---|---|---|
| B1 | **Реализован 2026-10-02:** верхний embedded stop-host сохраняет XY предыдущего stop, вмещает шахту без clip/переноса; нарушение → ERROR с лестницей/from/to/геометрией/причиной + target skip | решение мастера, staircase §2/§11 | сдан в working tree |
| B2 | **Реализован 2026-10-02:** u_shape facing определяется по max-score наружных floor-ячеек на z_top, до расчёта ширины арок; score=0 сохраняет fallback | staircase §2 сверка S0 | сдан в working tree |
| B3 | **Реализован 2026-10-02:** building_uid обязателен в make_shaft_placer и вызывающем _place_level_shafts; silent default удалён | §6.11 review | сдан в working tree |
| B4 | **Реализован 2026-10-02:** has_walls управляет внутренними перегородками маршевых шахт; внешняя оболочка здания сохраняется, открытый периметр получает host-floor без автоматических арок; XY/путь/B1 не меняются. straight/spiral получают общий режим стен, их builders маршей остаются заглушками | cellBuilder, shaftFactory, passage builder | сдан в working tree |
| B5 | **Реализован 2026-10-03:** единый проход Orientation поворачивает runtime entry_point.wall/back_entry_point.wall, shaft facing/embedded_entry и кардинальный attach_wall в мировой фрейм; frozen EntryPoint копируется, BOTH/ANY и None сохраняются, authored шаблон не мутируется | `structureOrientation.py:45`, ТЗ §9, `orientation-runtime-facing-done.md` | сдан в working tree |

## C. Проёмы / wall_openings (v2-оси)

| # | Проблема | Источник | Размер |
|---|---|---|---|
| C1 | **`placement` стратегии XY** — поля нет на wire (zone_center единственный); реестр стратегий рядом с `ZADJUSTER_BY_TYPE` | ТЗ §3.11 v2 | средний |
| C2 | **OQ-17/18**: `opening_type` по `room_type`/`structure_type` — сейчас всегда `WINDOW` baseline | ТЗ §3.11 | средний |
| C3 | **OQ-13/14/15/16**: TopWallZAdjuster (парапет), `display_facing`, `cell_states`, arc-length для круглых | ТЗ §3.10 | v2 |
| C4 | **Несколько записей `wall_openings`** — v1: `spec[0]` + ERROR «ignored»; семантика распределения по сторонам не определена | §6.7 | вопрос |
| C5 | **Authored `glass_material` на не-glass элементе** (`arrow_slit`): сейчас применяется как есть — оставить «мастер знает лучше» или substitution+ERROR | §6.7 review | вопрос |
| C6 | **Реализован 2026-10-02:** геометрия и проверка window_z используют единую доступную высоту min(room.z_height, profile.z_height) | §6.7 review | сдан в working tree |

## D. Прочее

| # | Проблема | Источник | Размер |
|---|---|---|---|
| D1 | **`corridorConnector` своя формула** `min(z_height-1, passage_height)` — отдельная семантика, не `resolve_door_height`; осознанно оставлено в §6.9, унифицировать или зафиксировать разницу в ТЗ | §6.9 scope | вопрос |
| D2 | **E4-хвост**: периодический validator sweep по stdlib — baseline ERROR-набор (8 шт.) держать видимым; новые ERROR = регрессия | постоянный gate | — |

## Открытые вопросы к мастеру (решить до имплементации соотв. пунктов)

- A3/A4 — политика уровней логов для geometric-fit и групповой attach_wall.
- C4/C5 — семантика multi-spec и authored-glass на не-glass элементах.
- D1 — унификация или документированная разница формул проёмов.

## Итерация A2 — 2026-10-01

`instantiate_level_rooms` читает typed-свойство
`RoomDef.perimeter_required_explicitly_disabled`; проверка model_fields_set
инкапсулирована в dataModel, чтобы генератор не содержал wire-ключ поля.
Свойство отличает явный false от default при отсутствующем поле. При любом входе пишет один WARNING
на room_def до разворачивания count. Runtime perimeter_required=True сохраняется;
wire/POJO не мутируются, layout и RNG не менялись. Остальные пункты не реализовывались.

205 тестов OK (1 существующий expected failure), включая 3 новых теста A2:
оба типа входа, тихие omitted/true/no-entry случаи, неизменность шаблона,
централизованный транскрипт и однократность при count=2 + обоих входах.
compileall и diff --check чистые. Fingerprints всех 13 stdlib идентичны baseline
среза embedded-shaft; те же 8 ERROR, детерминизм ×2.
Артефакты: `.local/perimeter_required_{before,after}.json`,
`.local/perimeter_required_tests.log`. Backend не запускался, коммит не создавался.

## Итерация B3 — 2026-10-02

Удалён default `building_uid=""` из `make_shaft_placer` и
`StructureGeneratorService._place_level_shafts`: оба требуют keyword-аргумент.
Все существующие вызовы уже передавали uid здания, поэтому RNG и геометрия
не изменились. Вызов factory без uid теперь завершается TypeError;
переданный uid доходит до EmbeddedShaftPlacer. Другие пункты не реализовывались.

26 профильных тестов OK (embedded shaft, staircase spec, structure orientation),
compileall и diff --check чистые. Fingerprints всех 13 stdlib совпадают с baseline
A2; те же 8 ERROR, детерминизм ×2. Артефакты:
`.local/shaft_placer_uid_tests.log`, `.local/shaft_placer_uid_after.json`.
Backend не запускался, коммит не создавался.

## Итерация A1 — 2026-10-02

`layoutEntry.py` проверяет наружную стену по реальному footprint: улица снаружи,
interior изнутри, достаточно кандидатов для ширины входа. `layoutEngine` сохраняет
уже подходящую позицию; при отказе ищет authored-направления и смещения вдоль
смежной стены, затем fallback на другой периметр. Новые комнаты/adjacent shafts
не могут закрывать доступные входы уже размещённых комнат. Обрабатываются оба
входа, isolated-placement, re-place после clipping и итоговая проверка после
mode B. Fallback пишет WARNING и заменяет только runtime-копию EntryPoint,
чтобы builder построил вход на доступной стороне. Отсутствие периметра вызывает
GenerationError, включая optional entry-комнаты. Wire и общий RNG не менялись.
ТЗ уточняет проверку exterior по footprint, включая уступы, вместо переноса
комнаты, у которой нужная стена уже доступна. Другие пункты не реализовывались.

222 теста OK (1 существующий expected failure), включая 8 новых тестов A1:
четыре стены/оба поля, защита main/back входов от соседей и isolated rooms,
сдвиг вдоль занятого края без fallback, WARNING и неизменность authored EntryPoint,
ошибка без периметра у optional start/connected rooms, круглый footprint,
generate×2 с обоими входами и неизменным шаблоном. Fingerprints всех 13 stdlib
идентичны baseline B2; те же 8 ERROR, детерминизм ×2.
compileall и diff --check чистые. Артефакты: `.local/entry_layout_tests.log`,
`.local/entry_layout_after.json`, `.local/entry_layout_sweep.log`.
Backend не запускался, коммит не создавался.

## Итерация C6 — 2026-10-02

`place_wall_openings` вычисляет одну доступную высоту как
`min(room.z_height, profile.z_height)` и передаёт её ZAdjuster, проверке явного
window_z и диагностике fallback. Уменьшенный профиль ограничивает проём;
увеличенный не позволяет поднять потолок комнаты. XY/количество/материалы и
shaft-автоокна не менялись. Остальные пункты не реализовывались.

28 профильных тестов OK (wall opening spec, structure orientation, building/area
assemblers), включая 2 новых теста несовпадающих высот. compileall и diff --check
чистые. Fingerprints всех 13 stdlib совпадают с baseline B3;
те же 8 ERROR, детерминизм ×2. Артефакты:
`.local/wall_opening_height_tests.log`, `.local/wall_opening_height_after.json`.
Backend не запускался, коммит не создавался.

## Итерация B2 — 2026-10-02

Общий `uShape/facingResolver.py:resolve_u_shape_facing` считает для каждой
кардинальной стороны уникальные соседние клетки за footprint на z_top,
учитывая только StructureElement.FLOOR. Facing = opposite стороны с максимальным
положительным score. При score=0 сохраняется authored/runtime fallback.
При равенстве score приоритет имеет opposite fallback, затем стороны по часовой
стрелке относительно него; без RNG и глобальной привязки к NORTH.

`build_passages` резолвит runtime-facing перед арками и передаёт одну ось lower/upper
shaft-экземплярам для расчёта clear width. UShapeBuilder использует тот же helper
для самой геометрии (включая прямые вызовы и legacy без shaft). Wire/спека не
мутируются. Другие типы лестниц, placement и upper host-семантика не менялись.

214 тестов OK (1 существующий expected failure), включая 6 новых: все направления,
нулевой score, только floor/только z_top/только exterior, max-score и ties,
выбранный facing в U-пути, согласование оси арок прямоугольной шахты,
generate×2 и неизменность шаблона. Fingerprints всех 13 stdlib идентичны baseline
C6; те же 8 ERROR, детерминизм ×2. compileall и diff --check чистые.
Артефакты: `.local/u_shape_facing_tests.log`, `.local/u_shape_facing_after.json`.
Backend не запускался, коммит не создавался.

## Итерация B1 — 2026-10-02

По решению мастера верхний embedded stop размещается ровно над предыдущим stop:
origin XY совпадает, размеры/форма могут отличаться. `prepare_embedded_upper`
вызывается до layout уровня; проверяет размещённый source, однозначность stop,
унаследованную шахту, fit без уменьшения в parent bounds, вложенность фактического
shaft footprint и interior-пол у выхода, конфликты с другими комнатами/шахтами.
Успешные host/shaft закрепляются; clipping, re-place и corridor trim не нарушают
контракт. Нижний adjacent fallback сохраняет прежнюю семантику.

Нарушение пишет ERROR с building/staircase/from/to/z/source_z/source XY,
размерами target/shaft, XY шахты, bounds и конкретной причиной. Target не создаётся,
включая required=true, layout_excluded запрещает повторный поиск другой позиции;
соответствующая верхняя шахта и продолжение отключаются. Последующий stop получает
диагностику отсутствующего source. Embedded-зависимости учитываются в порядке
layout, включая cellar → ground. Floor pass вырезает шахту из host-пола; верхняя
арка ограничена выбранной стеной, вместо всего пересечения вложенных footprints.
Wire и RNG не менялись. ТЗ §2/§11 обновлено. Другие пункты не реализовывались.

234 теста OK (1 существующий expected failure), включая 12 новых B1: точные XY,
запрет clipping/reposition/trim, cutout, bounds/shaft-fit/exit-floor/conflict/source
отказы, ERROR в централизованном транскрипте и отсутствие target в результате,
три этажа, отказ промежуточного stop и cellar → ground; generate×2, неизменный wire,
верхний выход на floor. Fixtures embedded v1 теперь задают upper-size, способный
вместить шахту по новому контракту. Все 13 stdlib fingerprints идентичны A1;
те же 8 ERROR, детерминизм ×2. compileall и diff --check чистые.
Артефакты: `.local/embedded_upper_tests.log`, `.local/embedded_upper_after.json`,
`.local/embedded_upper_sweep.log`. Backend не запускался, коммит не создавался.

## Итерация B4 — 2026-10-02

Factory переносит StaircaseSpec.has_walls в runtime shaft_has_walls.
CellBuilder удаляет периметр открытых шахт только внутри объединённого footprint
уровня, в том числе общую перегородку соседней комнаты; exterior shell сохраняется.
При embedded-open host-пол вырезается только из interior шахты, а открытый
периметр остаётся floor. Closed-геометрия не меняется. Passage builder создаёт
автоматические shaft↔room арки только при has_walls=true; открытый переход идёт
через floor. XY, размеры, B1, stair path, wire defaults и RNG сохраняются.
Режим стен общий для straight/u_shape/spiral, однако StraightBuilder/SpiralBuilder
пока NotImplementedError-заглушки — пути этих типов не входят в B4.
Vertical-ladder enclosure не менялся. Другие пункты не реализовывались.

240 тестов OK (1 существующий expected failure), включая 6 новых B4: center/corner
open/closed, сохранение outer shell и удаление общей стены adjacent, floor cutout,
одинаковые runtime XY и U-path при обоих значениях, отсутствие арок у open,
floor-якорь выхода и детерминизм adjacent-open; wall flag всех трёх маршевых типов.
Тест B2 оси арок теперь явно задаёт has_walls=true. Все 13 stdlib fingerprints
идентичны B1; те же 8 ERROR, детерминизм ×2. ТЗ обновлено.
Артефакты: `.local/shaft_walls_tests.log`, `.local/shaft_walls_after.json`,
`.local/shaft_walls_sweep.log`. Backend не запускался, коммит не создавался.

## Итерация B5 — 2026-10-03

Файлы: `docs/tz_building_generator.md` §9, `structureOrientation.py`,
`tests/test_structure_orientation.py`, `orientation-runtime-facing-done.md`.
После origin/bbox/extra_cells единый проход поворачивает entry_point.wall и
back_entry_point.wall через model_copy frozen EntryPoint, shaft facing (str) и
embedded_entry (Facing), кардинальный attach_wall через общий CARDINAL_FACINGS.
None, BOTH/ANY и неразмещённые комнаты сохраняются; authored StructureTemplate
и StaircaseSpec не мутируются. Порядок генерации не менялся.

Четыре новых теста проверяют south main_entrance → west, back entry, неизменность
исходных EntryPoint, shaft metadata, все attach_wall при 0–3 четверть-оборотах,
None, неразмещённые комнаты и нулевой поворот. Существующие тесты дополнены
четырёхоборотной идентичностью runtime metadata и проверками полной генерации
в четырёх направлениях с неизменным шаблоном.

Начальный baseline: 158 тестов, 1 expected failure и ошибка импорта C24 из-за
отсутствующего zstandard. После установки объявленного zstandard 0.25.0 в .venv
итоговый suite из skill: 183 теста OK (1 существующий expected failure);
orientation suite: 9 тестов OK. compileall и diff --check прошли.
Все 13 stdlib fingerprints идентичны baseline; те же 8 ERROR, детерминизм ×2.
Fingerprint содержит cells/passages без заданного facing; runtime-поля и поворот
проверены тестами. Артефакты: `.local/orientation_facing_{before,after}.json`,
`.local/orientation_facing_tests.log`, `.local/orientation_facing_suite.log`.
Backend не запускался, коммит не создавался.
