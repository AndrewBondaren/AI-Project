# worldData — вынос HTTP из application-слоя — DONE (2026-10-11)

Все три шага сданы: `worldData/errors.py` + `api/errorMapping.py`,
de-HTTP `worldService` (+guard'ы `import_list`/`buildingTemplateLibraryService`),
de-HTTP siblings + `seed.py` → 400. `grep fastapi application/worldData` = 0.

Правило: в `application/worldData/` HTTP **не существует** — ни HTTPException,
ни fastapi-импортов, ни PATCH-семантики с кодами статусов. Доменные ошибки,
маппинг в коды — только `api/` слой. Конвенция уже действует:
`reliefErrors.py` («map to HTTP only in routes»), `libraryPacks/errors.py`,
`bundle/errors.py` — шесть файлов её нарушают.

## Проблема

`from fastapi import HTTPException` + raise — 6 файлов, ~19 сайтов:

| Файл | Сайтов | Коды |
|---|---|---|
| `worldService.py` | 11 | 404 `get_by_id`; 422 `update`/`_validate`/`_normalize_world_data` |
| `namedLocationService.py` | 1 | 404 |
| `stateService.py` | 1 | 404 |
| `playerService.py` | 1 | 404 |
| `gameSessionService.py` | 4 | 404 |
| `seedService.py` | 1 | 400 |

Следствие: HTTPException протекает во внутренние вызовы —
`bundle` (prepare_import → except ValueError-хак), `reliefWorldImportService`,
`buildingTemplateLibraryService`, pack `_MemberOps.world_for`,
`worldPerkService`/`raceService` через `worlds.update`. Application-слой
вынужден знать коды статусов; `prepare_import` уже содержит костыль
«CRUD adapter uses HTTPException → ValueError» для non-HTTP caller'а.

## Целевой контракт

```python
# application/worldData/errors.py  (новый, по образцу libraryPacks/errors.py)
class WorldDataError(Exception)
class WorldDataNotFoundError(WorldDataError)          # entity + uid в message
class WorldDataValidationError(WorldDataError, ValueError)  # ValueError — см. ниже
```

- `WorldDataValidationError` наследует `ValueError` — сохраняет шов
  `worldBundleService`: `prepare_import` больше не конвертирует
  HTTPException→ValueError, доменная ошибка сама попадает в bundle-ветку
  `except ValueError → ImportValidationError`. Без двойных классов.
- `get_by_id` контракт не меняется: был raise-on-miss, остаётся raise —
  только доменный класс вместо HTTPException.
- `ImportValidationError` (jsonValidation) — уже доменная ошибка;
  `_normalize_world_data` перестаёт её заворачивать в HTTPException.

## Маппинг в api-слое — один шов

```python
# api/errorMapping.py (новый) + вызов install_error_handlers(app) в core/app.py
WorldDataNotFoundError      → 404 {detail: str(exc)}
WorldDataValidationError    → 422 {detail: str(exc)}
ImportValidationError       → 422 {detail: import_validation_http_detail(exc)}
```

`add_exception_handler` вместо размазывания try/except по ~8 роутам —
пропущенный сайт не станет 500. Route-level `raise HTTPException` для проверок
формы запроса остаётся — это легитимная зона api. Существующие per-route
catch (`ReliefValidationError`, `BundleValidationError`) не трогаем.

Исключение по коду: `seedService` сегодня даёт 400 — роут `seed.py` ловит
`WorldDataValidationError` → `HTTPException(400)`, публичный контракт сохраняется.

## Шаг 1 — контракт ошибок + api-шов

**Цель.** `worldData/errors.py`, `api/errorMapping.py`,
`install_error_handlers(app)` в `core/app.py` (line ~85, `app = FastAPI`).

**ТЗ.** `tz_json_validation.md` § Import path → «HTTP — ошибки» (таблица 422);
rule `layer-boundaries.mdc` (api = только HTTP).

**Файлы.** Новые `worldData/errors.py`, `api/errorMapping.py`; `core/app.py` (+1 call).

**Контракт.** Три класса ошибок и таблица маппинга — выше.

**Проверка.** `compileall`; существующие тесты не ломаются (поведение ещё не переключено).

**Done.** Хендлеры зарегистрированы, коды из таблицы ТЗ сохранены.

## Шаг 2 — de-HTTP `worldService.py`

**Цель.** Убрать fastapi-импорт и 11 raise/catch-сайтов:
`get_by_id`→`WorldDataNotFoundError`; `_validate` (6×)→`WorldDataValidationError`;
`update`/`_normalize_world_data` — `ImportValidationError` без wrap;
`import_from_json`/`prepare_import` — `except` на доменные классы
(порядок: domain errors re-raise → `except Exception` → row `ImportResult`,
как сегодня с HTTPException). Адаптер `prepare_import`
(HTTPException→ValueError) удаляется целиком — `WorldDataValidationError`
уже `ValueError`, bundle-шов (`worldBundleService` except ValueError)
работает без конвертации.

**ТЗ.** `tz_json_validation.md` § Import path → «HTTP — ошибки», «Normalize vs reject»;
`tz_world_bundle.md` (preflight через `prepare_import`).

**Файлы.** `worldService.py`; `import_helpers.py` +
`buildingTemplateLibraryService.py` — guard `except WorldDataError: raise`
перед per-row `except ValueError` (доменная ошибка из `_ensure_registry` →
`worlds.update` — не row-ошибка; иначе `WorldDataValidationError` как
`ValueError` проглатывается в `ImportResult` → 207 вместо 422);
`tests/test_import_validation_policy.py`
(2 сайта `assertRaises(HTTPException)` на прямой вызов `worlds.update` →
assert доменного класса); `tests/test_building_registry_mixed.py`
(`assertRaises(HTTPException)` на `import_from_json` → `ImportValidationError`,
assert по `errors` вместо `.detail`); аудит internal callers — `except HTTPException`
в `application/` отсутствует (проверено), domain error propagates → api-шов.

**Контракт.** Сигнатуры публичных методов и семантика не меняются;
меняется только класс исключения. Порядок except:

- `update()`: `except WorldDataError: raise` → `except ValueError →
  WorldDataValidationError` — прочий `ValueError` (`prepare_import_row`
  TypeError→ValueError) остаётся wrap, не голый 500 через глобальный хендлер.
- `import_from_json()`: `except WorldDataError: raise` → `except Exception →
  ImportResult row` (как сегодня `except HTTPException: raise`).

ASGI-тест `validate_only` (реальный роут)
должен остаться зелёным — глобальный хендлер даёт тот же 422.

**Проверка.** `python -m unittest tests.test_import_validation_policy` +
pack-suite (world_for path) + `compileall`.

**Done.** `grep fastapi worldService.py` = 0; тесты зелёные.

## Шаг 3 — de-HTTP siblings

**Цель.** `namedLocationService`, `stateService`, `playerService`,
`gameSessionService`, `seedService` → доменные ошибки; `seed.py` route:
catch `WorldDataValidationError` → `HTTPException(400)` в **трёх**
endpoint'ах (`get_all`, `upsert_one`, `delete_one`) — helper по образцу
`_http_from_relief` или try per endpoint.

**ТЗ.** `layer-boundaries.mdc`; `tz_json_validation.md` § «HTTP — ошибки».

**Файлы.** 5 сервисов + `api/routes/seed.py`. Роуты
locations/sessions/characters/map — без правок: глобальный хендлер
даёт тот же 404/422.

**Контракт.** Тексты сообщений (`"Location 'x' not found"` и т.д.)
не меняются — только класс.

**Проверка.** `compileall`; `grep -rn "fastapi\|HTTPException"
application/worldData` = 0; `python -m unittest discover -s tests`.

**Done.** Ноль HTTP в `application/worldData/`; публичные коды 400/404/422
сохранены.

## Замечания

- Независим от `library-packs-module-split` (другие файлы); порядок любой.
- Не снимает D9 (`building-registry-mixed-column`) и не вводит scoped
  write-seam — это отдельный вопрос из разбора `worlds.update`.
- `tests/test_settlement_volume_separation.py` (`except HTTPException: fail`)
  — dead-catch после рефактора, чистится при касании, не blocker.
- ASGI-тесты монтируют голый `FastAPI()` без `install_error_handlers`
  (`test_import_validation_policy.py`); сейчас зелёные за счёт per-route
  catch в `worlds.py`. Новым проверкам глобального маппинга — монтировать
  `install_error_handlers(app)` в тесте, не `create_app()`.
- Мёртвые `if world is None` после `get_by_id` (~15 сайтов `map.py`,
  `debug.py`, `worlds.py`) и импорт `app.api.schemas.imports` в
  application-слое — осознанно вне скоупа, чистка при касании.
