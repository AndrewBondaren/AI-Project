# Дефолты is_inhabited: тип → subtype → экземпляр — DONE

Статус: выполнено 2026-10-07 по запросу пользователя «Делаем план и затем имплементируем».

## Цель и границы

Один атомарный шаг D1 меняет контракт authored-флага и разрешение его дефолта.
Базовый default False; builtin settlement задаёт True данными типа.
Экономический гейт НЕ подключать: у поля оставить явный комментарий о его
назначении и текущем отсутствии подключения, с требованием перепроверить статус.
Существующие гейты специализаций/подбора районов сохраняются.
Не менять cascade engine, DAG, SQL, рабочую БД или родительскую иерархию.

## Целевая архитектура и контракт

- SettlementPayloadFields.is_inhabited: DefaultOnWire[bool] = False — общий
  источник поля/default для payload и skeleton, комментарий непосредственно у поля.
- LocationTypeEntry.is_inhabited: IgnoreOnWire[bool] = False; builtin settlement
  явно True; location_complex и пользовательские типы по умолчанию False.
- LocationTypeSubtypeEntry.is_inhabited: IgnoreOnWire[bool | None] = None;
  None наследует настройку типа, bool её переопределяет. Builtin recipes наследуют тип.
- Merge реестра сохраняет отсутствующий override и принимает явный False/True;
  subtype explicit None сбрасывает override к наследованию типа.
- Сериализация записей POJO сохраняет отсутствие override is_inhabited, чтобы
  normalize_world → JSON → runtime merge не превращал отсутствие в explicit False/None.
  fixture_identity сохраняет настройку типа.
  Настройки реестра используют существующий IgnoreOnWire: resolve_model не
  добавляет отсутствующий override в model_fields_set. Default остаётся на POJO.
- BundleNamedLocation.bind_payload: если поле отсутствует у экземпляра,
  subtype bool → type bool → default модели. Явные bool экземпляра имеют приоритет;
  explicit None на экземпляре остаётся ошибкой bool-контракта.
- Import/create сохраняют итоговый bool в location_payload; CRUD сохраняет его
  при частичных изменениях и принимает явный override. Прежние строки без поля
  не мигрируются: прямое typed-чтение использует default False.
- settlementSkeletonAccess передаёт поле существующей POJO-проекцией, без нового
  списка полей и повторного resolve. Специализации при False по-прежнему запрещены.

## Data flow

World registry POJO + builtin defaults → merge с сохранением отсутствия overrides
→ BundleNamedLocation + instance wire → typed payload validator → JSON persist
→ typed payload read → skeleton projection → существующие consumers.
Приоритет: экземпляр > subtype > тип > базовый False. Дефолты не вычисляет planner.

## D1 ✅ — контракт и проводка дефолтов

- ТЗ: docs/tz_locations.md §Payload per type; docs/tz_city_generation.md §1.2.
- Файлы: settlementPayload.py; locationTypeEntry.py; locationTypeSubtypeEntry.py;
  worldLocationTypeRegistry.py; bundleNamedLocation.py; pyrightconfig.cascade.json;
  tests/test_location_payload.py, test_location_payload_schema.py, test_city_three_axes.py
  и необходимые runtime-fixtures без is_inhabited.
- Порядок: обновить ТЗ → POJO defaults/serializer/merge → bind_payload → fixture wiring
  и behavioral tests → обязательные проверки.
- Проверки: bare payload/skeleton False; settlement без subtype/с subtype True;
  complex/custom False; type/subtype/instance overrides, explicit False/None;
  world overlay и normalize_world roundtrip; import/CRUD/persist/skeleton roundtrip;
  прежние специализации и planner; npm run typecheck:cascade; git diff --check;
  full unittest suite сравнением ID ошибок с nl-payload-s2-tests.log.
- Done: весь приоритет работает без условий по имени типа в binder/planner;
  комментарий поля описывает неподключённый economic gate (проверен перед записью);
  профильные тесты и typecheck проходят, полный набор не добавляет ошибок к baseline.

## Результат и проверки

- Контракт реализован; экономический гейт не подключён. Комментарий поля
  SettlementPayloadFields.is_inhabited фиксирует статус и требование перепроверки.
- Runtime/CRUD сохраняют итоговый bool; skeleton получает его общей POJO-проекцией.
- Override-поля реестра используют IgnoreOnWire и wrap serializer, чтобы
  нормализация не превращала отсутствие настройки в explicit False/None.
- 193 focused tests OK (6 новых тестов с матрицами приоритета/roundtrip).
- npm run typecheck:cascade: 0 ошибок positive, 4 ожидаемых negative.
- Full suite: 1580 tests, те же 21 ERROR ID baseline, 1 expected failure;
  новых ошибок/FAIL нет. Лог: .local/inhabited-defaults-tests.log.
- git diff --check OK. Экономические фильтры, движок каскада и БД не изменены.
