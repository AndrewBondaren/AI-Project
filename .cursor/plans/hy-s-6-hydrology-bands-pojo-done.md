# HY-S-6 — один HydrologyBands POJO — DONE

Статус: согласован мастером («далее»), выполнен 2026-10-21.

## Основание и инвентаризация

Задача мастера: «Начинаем с HY-S-6». SoT: `docs/tz_generator_technical_debt.md`
§ HY-S-6; `docs/tz_terrain_hydrology.md` § U15 «Берег + bands», § HY-12
«HydrologyBands переиспользуется как rim», § Pre-1.4 проход воды.

Два класса с одинаковым смыслом:
- `backend/app/dataModel/hydrology/bands.py`: Pydantic HydrologyBands,
  ограничения и defaults, экспонируется `dataModel.hydrology`.
- `backend/app/application/worldData/generators/hydrology/types.py`:
  frozen dataclass HydrologyBands(min, max).

Единственный app-потребитель dataclass — `load/resolveHydrologyBands.py`.
У `resolve_hydrology_bands` / `clamp_bands` нет production-callers: по поиску
Python-кода репозитория 2026-10-21 остались только два теста в
`backend/tests/test_hydrology_hy1.py`. Реальная bathymetry уже принимает
POJO: BasinSpec / floor_profile_z; policy fields и DeclaredBasin.rim также
используют его. Старые producers из исторической записи HY-S-6 удалены HY-12.

Legacy resolver повторяет bounds литералами, использует raw local_profile,
подставляет max=99 вместо POJO default 5, clamp-ит значения и меняет порядок
перевёрнутых bounds. Мигрировать этот API ради отсутствующих потребителей
не требуется. HY-S-7 (RiverTypeClassify) и HY-S-8 (autoresolve wrappers) отдельно.

## Целевое состояние

Единственный HydrologyBands — существующий POJO из dataModel. Потребители
читают typed policy.bands / resolved BasinSpec.bands / DeclaredBasin.rim.
Defaults, валидация wire и category defaults принадлежат существующим моделям.
Нового category resolver, compat alias, default-map и raw-dict API не создаём.

Удаление мёртвого clamp не меняет semantics действующего POJO: не добавляется
автоматическая сортировка min/max, новый validator или новый local override.
Проверка порядка rim в DeclaredBasin сохраняется. Missing whole section и
supplied partial bands сохраняют соответствующие defaults своих POJO.

## Шаг 1 — удалить legacy-дубль и неиспользуемый resolver

- **Цель:** закрыть HY-S-6 одной атомарной очисткой устаревшего API.
- **ТЗ:** ссылки выше; перед кодом уточнить в tz_terrain_hydrology, что
  bands/rim читаются из POJO без отдельного clamp resolver и local_profile.
- **Файлы:** `generators/hydrology/types.py`,
  `generators/hydrology/load/resolveHydrologyBands.py` (удаление),
  `tests/test_hydrology_hy1.py` (замена двух legacy tests проверками POJO),
  `docs/tz_terrain_hydrology.md`, `docs/tz_generator_technical_debt.md`.
- **Контракт:** удалить dataclass HydrologyBands, clamp_bands,
  resolve_hydrology_bands; production consumers уже используют канонический
  POJO, публичный wire не меняется. Текущий default plain bands max=5,
  whole-category defaults, custom values и существующая валидация сохраняются.
- **Проверка:** новые проверки meaningful policy/wire semantics: missing
  bands, partial bands, supplied custom bounds, невалидные bounds через общий
  resolver, category defaults, rim ordering validation. Затем HY-1,
  bathymetry, water resolver, HY-12 rivers/smoke, water placement tests;
  compileall backend/app и git diff --check. Поиск подтверждает единственное
  определение HydrologyBands и отсутствие imports/callers legacy API.
- **Done:** нет runtime-дубля / legacy resolver / локальных bounds и
  fallback max=99; проверки проходят, HY-S-6 отмечен resolved с отчётом,
  план переименован в `hy-s-6-hydrology-bands-pojo-done.md` со ссылкой из реестра.

Backend не запускать, коммит не создавать. HY-S-7/HY-S-8 и HY-12 review-debt
не выполнять в этом шаге. До согласования этого плана код не менять
(`.cursor/rules/code-gates.mdc`, гейт 2).

## Отчёт шага 1 — выполнен 2026-10-21

Удалены runtime dataclass и неиспользуемый resolveHydrologyBands целиком.
Канонический POJO и его действующие consumers не изменялись. Пять тестов
в test_hydrology_hy1 заменяют два legacy tests, проверяя текущие category /
partial / custom / invalid / rim semantics через общий import/runtime путь.
Строгость преобразования wire не расширялась: HY-S-6 сохраняет существующий
POJO-контракт. Новых resolver/default-map/alias нет.

Проверка: 68 tests OK (HY-1, bathymetry, water resolver, HY-12 rivers/smoke,
water placement); compileall backend/app и git diff --check. Поиск: одно
определение HydrologyBands, ноль legacy resolver/clamp callers/imports.
ТЗ уточнено, HY-S-6 закрыт в реестре. HY-S-7/HY-S-8 не выполнялись.
Backend не запускался, коммит не создавался.
