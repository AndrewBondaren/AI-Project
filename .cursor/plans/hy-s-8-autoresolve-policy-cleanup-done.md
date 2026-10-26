# HY-S-8 — удалить неиспользуемые autoresolve policy-обёртки — DONE

Статус: согласован мастером («Lf», прочитано как «Да»), выполнен 2026-10-21.

## Основание и инвентаризация

SoT: `docs/tz_generator_technical_debt.md` § HY-S-8;
`docs/tz_terrain_hydrology.md` § World template — default_*, global off,
declare/autoresolve и § HydrologyGeneratorService. Мастер согласовал
отсутствие самостоятельного смысла текущих обёрток и регистрацию долга.
После HY-S-6/HY-S-7 команда «Далее» продолжает к HY-S-8.

Повторный поиск Python-кода 2026-10-21:
- `load/hydrologyAutoresolvePolicy.py` определяет три dataclass
  RiversAutoresolvePolicy/LakesAutoresolvePolicy/SeasAutoresolvePolicy,
  helpers и raw/None compatibility-ветки с fallback True.
- Production-callers отсутствуют. Sea/lake helpers используются только
  четырьмя тестами в test_hydrology_hy5a.py / test_hydrology_hy5b.py.
- У river helper нет внешних callers.
- HydrologyGeneratorService и riverNetworkAssembler уже читают POJO напрямую;
  условия scope/enabled/autoresolve вычисляются на действующем пути.

## Целевое состояние

Текущие POJO остаются единственным источником policy/defaults.
Неиспользуемый loader и три обёртки удалены без compat alias, нового DTO
или замещающего effective-policy resolver. Производственная оркестрация
и алгоритмы не меняются. Проверки default/off сохраняются на POJO и
производственном пути с действительно подходящими terrain/water входами.

## Шаг 1 — удалить wrapper API, сохранить проверки действующего поведения

- **Цель:** удалить мёртвый policy API и его локальные defaults одной
  атомарной очисткой с переносом проверок на существующих потребителей.
- **ТЗ:** разделы выше; перед кодом уточнить прямое чтение default_*
  из WorldHydrology, без параллельных autoresolve-policy классов.
- **Файлы:** `generators/hydrology/load/hydrologyAutoresolvePolicy.py`
  (удаление), `tests/test_hydrology_hy5a.py`, `tests/test_hydrology_hy5b.py`,
  `tests/test_hydrology_hy5c.py` (при необходимости coverage river gates),
  `docs/tz_terrain_hydrology.md`, `docs/tz_generator_technical_debt.md`.
- **Контракт:** удаляется только неиспользуемый API; POJO, wire, production
  gates и значения defaults не меняются. Полезные четыре legacy tests
  переводятся на typed POJO. Проверки production подтверждают on/off,
  category/global enabled, scopes и независимость declare от autoresolve
  там, где это соответствует существующему контракту. Уже существующие
  регрессии переиспользуются, а не дублируются ради количества тестов.
- **Проверка:** повторный поиск callers, HY-1 и HY-5a/b/c, hydrology edge
  cases, coarse/fine, routing/depth/topology и HY-12 smoke; compileall
  backend/app, git diff --check. Поиск подтверждает отсутствие старых
  imports/классов/helpers и нового параллельного policy API.
- **Done:** проверки прошли, HY-S-8 resolved с отчётом; план переименован
  в `hy-s-8-autoresolve-policy-cleanup-done.md`, ссылка из реестра обновлена.

HY-S-6/HY-S-7 сохранить. Незавершённые шаги HY-12 review-debt, возможные
независимые ошибки production gates — отдельные задачи, не исправлять молча
в cleanup. Backend не запускать, коммит не создавать.

## Отчёт шага 1 — выполнен 2026-10-21

Удалён hydrologyAutoresolvePolicy целиком; три dataclass/helpers не имеют
замещающего API. Четыре sea/lake policy tests читают канонический POJO через
общий reader. Production и defaults не менялись. Усилены проверки off:
sea terrain below level с положительным on-контролем, lake natural bowl,
global/category/autoresolve/scope gates; river category/autoresolve off
не выпускает русло и не пишет z. Положительные production и declared
autoresolve=False регрессии сохранены.

115 tests OK: HY-1, HY-5a/b/c, edge cases, coarse space, HY-12 rivers/smoke,
river depth/routing/topology и fine planning. compileall backend/app и
git diff --check. Поиск Python-кода: ноль старых classes/helpers/imports.
ТЗ и registry обновлены, HY-S-8 resolved. HY-S-6/HY-S-7 сохранены;
HY-12 review-debt не выполнялся. Backend не запускался, коммит не создавался.
