# План: сплит `districtAssembler/planner/tokens.py` (549 строк → 3 модуля) ✅ DONE

**Статус:** имплементировано 2026-10-14.  
**ТЗ:** [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) § «Fat modules»; правило `.cursor/rules/class-size-limit.mdc` (одна зона ответственности). Продукт не менять: поведение packing/`build_tokens` идентично, [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) не трогаем.  
**Scope:** чистое перемещение функций. Без rename публичных имён, без правки callers, без новой логики.

## Цель

`tokens.py` (549 строк) смешивает три зоны: subject resolution (resource/crop/livestock реестры, fallback pool, rng `SUBJECTS`), выбор layout-кандидатов (tier/allowed/enabled фильтры, `_pick_layout_picks`), сборка `PackingToken` + фасад. Развести по зонам, публичный шов оставить в `tokens.py`.

## Целевое состояние

| Файл | Зона | Содержимое | ~строк |
|---|---|---|---|
| `planner/subjects.py` (new) | subjects | `_subjects_for`, `_subject_catalog`, `_fallback_pool`, `_token_in_catalog`, `_subjects_rng`, `_resolve_subjects`, `_resource_kinds_for`, `_crop_kinds_for`, `_livestock_kinds_for` | ~160 |
| `planner/layoutPicks.py` (new) | выбор кандидатов | `_tier_pool`, `_choose_layout`, `_purpose_keys`, `_required_type_keys`, `_layouts_enabled`, `_match_allowed`, `_buildings_rng`, `_pick_layout_picks` | ~230 |
| `planner/tokens.py` | фасад | `build_tokens`, `pick_layout_uids`, `candidate_template_uids`, `_required_for` | ~120 |

Зависимости односторонние: `tokens` → `layoutPicks` → `subjects`. Циклов нет (subjects не импортирует picks/tokens).

## Шаг 1 — сплит (единственный)

| Поле | Содержание |
|---|---|
| Цель | Разнести три зоны `tokens.py` по `subjects.py` / `layoutPicks.py` / `tokens.py` без изменения поведения |
| ТЗ | `tz_generator_technical_debt.md` § Fat modules; `class-size-limit.mdc` |
| Файлы | new `backend/app/application/worldData/generators/assemblers/districtAssembler/planner/subjects.py`, `planner/layoutPicks.py`; rewrite `planner/tokens.py` |
| Контракт | Публичный шов без изменений: `build_tokens`, `pick_layout_uids`, `candidate_template_uids` импортируются из `planner.tokens` как сейчас (`districtAssembler.py`, `buildingCache.py`, `test_city_three_axes.py` — не трогаем). Внутренние `_helpers` переезжают с именами как есть; cross-module вызовы — через импорт (`from .subjects import _resolve_subjects, …`), re-export в `tokens.py` не делаем |
| Проверка | `python -m compileall backend/app/application/worldData/generators/assemblers/districtAssembler/planner` + `python -m unittest backend.tests.test_city_three_axes` (из корня, как принято) — зелёный как до сплита |
| Done | `tokens.py` ≤ ~120 строк; callers не изменены; тесты проходят; импорты в новых файлах только по своей зоне |

## Не в этом плане

- Rename функций / упрощение `_pick_layout_picks` (он ~125 строк, но это один алгоритм — см. debt MR-8 уже resolved).
- Перенос `pick_layout_uids`/`candidate_template_uids` из публичного шва.
- Обновление таблицы Fat modules в tech debt (можно добавить строку после выполнения — отдельной микроправкой по согласованию).
