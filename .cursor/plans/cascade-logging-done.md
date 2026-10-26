# План (done): логирование каскада через общий фасад

Статус: done (L1–L3). Решение мастера: WARNING эмитит движок,
не POJO-политика.

## Цель

Каскад (`LocationContext` / `extend()`) — консьюмер общего лог-фасада:
файл `logs/cascade/cascadeLog.log`, события через доменный хелпер, в
транскрипте generation. Никаких собственных логгеров/print'ов — только
`logging.getLogger(__name__)` под маршрутом фасада (tz_logging L3/L5).

Сейчас: единственное событие каскада — WARNING `REGISTRY_MEDIAN` из
`worldEconomyTierRegistry.resolve_default` (dataModel) — падает в
`logs/core/runtime.log` (unmatched); `contextResolver.logger` объявлен и
мёртв; `generationLogging` не захватывает `worldData.context`.

## ТЗ

`docs/tz_logging.md` (Инварианты L1–L8, Каталог, Маршрут);
`docs/tz_cascade_context.md` §4 (provenance, «WARNING вместо silent
median»), §8.2 («median + WARNING»).

## Контракт событий (целевой)

| Событие | Уровень | Когда | Поля |
|---|---|---|---|
| `scope_resolve` | DEBUG | конец каждого `extend()` | `level`, типы link-объектов, по каждому параметру `value parent=<src|none> child=<src|none>` (parent=none — параметр главный родитель; child=none — чистое наследование) |
| `default_applied` | WARNING | первый scope, где параметр упал на provisional default (политика `REGISTRY_MEDIAN`) | `param` (field), `level`, `policy`, `value` |
| `default_applied` | DEBUG | то же для `CANONICAL_DEFAULT` (тихие дефолты — текущая семантика тестов) | те же |

Штормов нет: один resolve на scope-границу; DEBUG фильтруется уровнем.
Консольный file-only список не расширяется.

**Точка эмиссии WARNING — движок** (`contextResolver`), не POJO: у
движка есть scope/provenance-контекст, которого у реестра нет; dataModel
не импортирует application-хелпер. `logger.warning` в
`WorldEconomyTierRegistry.resolve_default` снимается (L5: второй logger
на то же событие). §3/§5 tz_cascade правится: политика возвращает
median, WARNING эмитит движок через `cascadeLog`.

## Шаги

### L1 — ТЗ: sink и события

- **Цель:** зафиксировать консьюмера и контракт событий до кода.
- **ТЗ:** tz_logging §Каталог/Маршрут; tz_cascade_context §4, §8.2.
- **Файлы:** `docs/tz_logging.md` — строка каталога
  `cascade | cascadeLog | logs/cascade/cascadeLog.log | server`, строка
  маршрута `app.application.worldData.context → cascade/cascadeLog`,
  запись в Истории; `docs/tz_cascade_context.md` — короткий блок
  «Логирование» в §4 (события таблицей выше) + правка формулировки
  «median + WARNING (POJO)» → WARNING эмитит движок.
- **Проверка:** ревью диффа документов.
- **Done:** sink и события описаны в SoT до реализации.

### L2 — Хелпер + маршрут фасада

- **Цель:** `logs/cascade/cascadeLog.log` открывается сервером, события
  попадают и в файл, и в generation-транскрипт.
- **ТЗ:** tz_logging §Маршрут/Каталог, §Инварианты L2/L3.
- **Файлы:**
  - `backend/app/application/worldData/context/cascadeLog.py` — новый
    хелпер по образцу `packingLog.py`: `logger =
    logging.getLogger(__name__)`, `log_scope_resolve(...)`,
    `log_default_applied(...)`, `activity` в extra;
  - `backend/app/core/loggingConfig.py` — `_PREFIX_ROUTES` +=
    `("app.application.worldData.context", "cascade", "cascadeLog")`;
    `SERVER_SINKS` += `("cascade", "cascadeLog")`;
  - `backend/app/core/generationLogging.py` — `_GENERATION_PREFIXES`
    += `"app.application.worldData.context"`.
- **Контракт:** `route_for("app.application.worldData.context.cascadeLog")
  == ("cascade", "cascadeLog")`; профиль server пишет sink.
- **Проверка:** `python -m compileall` затронутых; smoke —
  `route_for(...)` / `setup_logging` в temp-дире → emit → файл
  `cascade/cascadeLog.log` появляется.
- **Done:** маршрут зарегистрирован; голый emit хелпера пишет в
  `logs/cascade/cascadeLog.log`.

### L3 — Проводка событий в движке

- **Цель:** `extend()` эмитит контрактные события; точка WARNING
  переезжает из dataModel в движок.
- **ТЗ:** tz_cascade_context §4 (provenance, один резолв на scope);
  tz_logging L3/L5.
- **Файлы:**
  - `contextResolver.py` — мёртвый `logger` → вызовы `cascadeLog`:
    `log_scope_resolve` в конце `extend()` (уровень, типы объектов,
    параметры с новым provenance-source); `log_default_applied` в ветке
    `source is None` → `_resolve_default` (дедуп уже есть через
    `_is_default` — WARNING один раз на цепочку);
  - `worldEconomyTierRegistry.py` — убрать `logger.warning` (+ `import
    logging`/logger, если больше не нужны);
  - тесты: `test_context_extend.py` (assertLogs → модуль `cascadeLog`),
    `test_cascade_context_baseline.py` (log_target → `cascadeLog`),
    `test_location_context_contract.py` (прямой вызов `resolve_default`
    больше не предупреждает — кейс переписывается на «median без
    warning», warning покрывается через `extend`).
- **Проверка:** `python -m unittest tests.test_context_extend
  tests.test_cascade_context_baseline tests.test_location_context_contract`;
  WARNING ровно один на пустую цепочку, ноль при authored.
- **Done:** median-WARNING идёт в `logs/cascade/cascadeLog.log` с
  scope-контекстом; `core/runtime` каскад не засоряет; в dataModel нет
  эмиссии события каскада.

## Не scope

- Новые события сверх контракта (per-param materialize-детали и пр.) —
  добавляются в хелпер по мере нужды отдельными правками.
- Маршрутизация прочих dataModel-логгеров — вне этого плана.
- Перенос точки сборки ctx в DAG — не трогается (gate).
