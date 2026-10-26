# HY-S-7 — RiverTypeClassify напрямую из POJO — DONE

Статус: согласован мастером («Да»), выполнен 2026-10-21.

## Основание и инвентаризация

Мастер согласовал направление: существующий POJO должен использоваться напрямую,
runtime-копия не нужна. Текущая команда «далее» продолжает HY-S-6 к HY-S-7.
SoT: `docs/tz_generator_technical_debt.md` § HY-S-7;
`docs/tz_terrain_hydrology.md` § U17/U22, RiverTypeClassifier и Глубина (R-4).

- `dataModel/hydrology/rivers.py:RiverTypeClassify` — канонический frozen POJO,
  пять policy-полей с defaults/валидацией.
- `generators/hydrology/types.py:RiverTypeClassify` — dataclass с теми же полями.
- `load/resolveRiverTypeClassify.py` — активный мост: ручное перечисление полей,
  cast, повторные defaults/null fallback и raw dict ветка.
- `jsonValidation/worldRow.py:hydrology` уже возвращает WorldHydrology через
  общий resolver; default_rivers.type_classify в модели имеет конкретный тип.
  Отдельное исправление/дозаполнение POJO в consumer не требуется.
- В ТЗ сохранились старые U22 / § «Import validator — type_classify» с
  обещанием runtime fallback при supplied null. Текущий общий resolver и
  test_null_fields_do_not_use_schema_defaults уже отклоняют такой input.
  До кода синхронизировать эти старые формулировки с действующим POJO и
  согласованной целью HY-S-7: missing использует модельные defaults,
  supplied invalid не исправляется локальным fallback. Это фиксация текущего
  поведения общего resolver, не введение новой строгости.
- Dataclass импортируют planner, classifyRiverSegments, resolveDeclaredRiverPath,
  riverRouteRequests, fineRiverSampling и два test-модуля (edge_cases, relief).
- coarse/fine и autoresolve вызывают resolve_river_type_classify; имя helper
  можно сохранить как typed accessor, не меняя все callers.

## Целевое состояние

Единственный RiverTypeClassify — канонический POJO dataModel. Все type hints и
конструкторы потребителей указывают на него без compat alias в runtime types.
`resolve_river_type_classify` остаётся тонким typed accessor:
общий `hydrology(world)` → `default_rivers.type_classify`, без пересоздания,
ручного копирования полей, raw чтения и локальной обработки defaults/null.

Missing/default, supplied invalid и import/runtime mode policy принадлежат
существующему общему resolver. Значения полей/правила классификации, mountain
depth multiplier/rounding, поиск и геометрия маршрутов не меняются.
Новых полей/классов/параллельных defaults не вводится. Публичные jsonValidation
exports не удаляются в рамках этой задачи без подтверждённой необходимости.

## Шаг 1 — удалить dataclass и переключить consumers на POJO

- **Цель:** устранить runtime-дубль и ручную проекцию policy одним атомарным
  изменением типов, typed accessor и их потребителей.
- **ТЗ:** разделы выше; до кода уточнить в tz_terrain_hydrology прямой POJO
  контракт классификации и отсутствие consumer fallbacks.
- **Файлы:** `generators/hydrology/types.py`,
  `load/resolveRiverTypeClassify.py`, `rivers/{riverNetworkPlanner,
  classifyRiverSegments,resolveDeclaredRiverPath,riverRouteRequests}.py`,
  `shore/fineRiverSampling.py`, `tests/test_hydrology_hy1.py`,
  `tests/test_hydrology_edge_cases.py`, `tests/test_relief_objects_z.py`,
  `docs/tz_terrain_hydrology.md`, `docs/tz_generator_technical_debt.md`.
- **Контракт:** helper возвращает существующий POJO вместо dataclass;
  production callers сохраняются. Пять полей, defaults и wire не меняются;
  невалидный input обрабатывается общим resolver без локального исправления.
- **Проверка:** тип результата/accessor, default и partial/custom policy
  round-trip через import/runtime; supplied null/invalid остаётся ошибкой;
  custom threshold влияет на mountain classification. Регрессии HY-1,
  edge_cases, HY-5a/b/c, depth, routing/topology, fine planning, coarse/fine
  HY-12 и relief. compileall backend/app, git diff --check. Поиск: один
  класс RiverTypeClassify, ноль imports runtime-дубля и функций ручного копирования.
- **Done:** проверки прошли, HY-S-7 resolved с отчётом; план переименован
  в `hy-s-7-river-classify-pojo-done.md`, ссылка из реестра обновлена.

HY-S-6 и HY-S-8, незавершённые шаги HY-12 review-debt — вне этого шага.
Backend не запускать, коммит не создавать. Изменения уже выполненного HY-S-6
и пользовательские записи техдолга сохранить.

## Отчёт шага 1 — выполнен 2026-10-21

Runtime dataclass удалён, все его imports переведены на канонический POJO.
Resolver — typed accessor без ручного перечисления полей, cast, raw parse
и fallback-веток. Модель, её поля/defaults/валидация, классификация и depth
формулы не менялись; public jsonValidation exports сохранены.
В ТЗ U22 синхронизирован с уже действующим missing/invalid контрактом.

126 tests OK: tests.test_hydrology_hy1, test_hydrology_edge_cases,
test_hydrology_hy5a/b/c, test_hydrology_river_depth_policy,
test_hydrology_river_routing, test_hydrology_river_topology_contract,
test_hydrology_fine_river_planning, test_hydrology_coarse_space,
test_hydrology_hy12_rivers, test_hydrology_hy12_smoke, test_relief_objects_z.
compileall backend/app и git diff --check. Поиск: один класс RiverTypeClassify,
ноль старых imports и функций проекции. HY-S-7 закрыт в реестре.
Backend не запускался, коммит не создавался. HY-S-6 сохранён,
HY-S-8 и HY-12 review-debt не выполнялись.
