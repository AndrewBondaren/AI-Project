# Композиция positive typing planning — DONE

Запрос: valid разросся; сохранить строгое разделение ответственности.
Статус: COMPLETE 2026-10-28, механическое продолжение проверки G4-S.

Один шаг: разнести existing valid.py (~600 строк) по владельцам тестируемых
контрактов, без изменения production API или содержания assert_type.
Основание: tz_terrain_generation §Planning и доставка GEO-1;
code-gates/folder-composition, подтверждённое пользователем разделение ответственности.

Целевые пути (в backend/tests/typing/planning/):

- valid/__init__.py — пустой пакет, без re-exports/выполнения.
- valid/infrastructure.py — generic cache/planning, nominal units, diagnostics.
- valid/policy.py — policy fixtures, declarations, compiler/executor checks.
- valid/placement.py — placement lifecycle.
- valid/surface/{__init__,providers,hydrology,composition,landcover}.py —
  соответственно typed provider bindings, hydrology planning, surface
  composition/views, landcover collector/adapter.
- valid/terrain/{__init__,regions,water}.py — region extent и water contracts.

Непосредственных файлов: planning 5→4; valid 4; surface 5; terrain 3.
Generic fixtures остаются в infrastructure, policy fixtures в policy;
invalid.py получает явные imports этих двух владельцев. Совместимого
aggregator valid.py и wildcard re-exports не будет.
pyrightconfig.valid.json включает весь valid/ рекурсивно; include production
modules остаётся прежним. invalid.py и его диагностики не разделяются этим шагом.

Проверка: AST equality всех перенесённых functions/classes/constants;
positive Pyright без ошибок; negative planning/cascade ровно те же
113/19 ожидаемых диагностик (с учётом новых line numbers).
Done: самостоятельные тематические модули, без потери type assertions,
циклических imports или нового сводного файла. G4 остаётся следующим шагом.

Выполнено: 61 декларация и 74 assert_type сохранены (AST equality),
positive Pyright 302 файла / 0 ошибок; negatives planning 113/113,
cascade 19/19. Максимальный модуль <200 строк; в __init__ нет re-exports.
