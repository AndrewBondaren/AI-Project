# Общая политика runtime/worldEdit — базовый архитектурный этап

> Карта межплановых зависимостей и критический путь:
> [`plan-dependency-graph.md`](plan-dependency-graph.md) — этот план
> отдельный трек, с библиотечной pack-моделью не пересекается.

**Статус (2026-10-08):** реализованы общая основа, два пилотных поля и import preview (E0–E5). В E6 завершена миграция 578 legacy-default полей и общего resolver; остальные consumer/ref boundaries перечислены ниже; весь репозиторий соответствующим новой политике не объявлен. `validate_only=true` проверяет без записи/изменяющих мир задач; обычный импорт сохраняет транзакцию/rollback. Работа с кодом разрешена последующим запросом мастера «Делаем».

## Базовая политика runtime/worldEdit

SoT: [tz_runtime_world_edit_policy.md](../../docs/tz_runtime_world_edit_policy.md). Общая основа предшествует новым доменным policy в последующих планах, включая wilderness. Один resolver; runtime WarningError без error defaults; worldEdit получает ту же диагностику; неразрешённый результат не является успехом.

## Правила и границы реализации

- Обязательные правила: `dataModel-no-hardcode.mdc`, `json-validation-architecture.mdc`, `pojo-world-row-wire.mdc`, `layer-boundaries.mdc`, `runtime-world-edit-policy.mdc`; доменные нормы — ТЗ общей политики, JSON validation/import, cascade context и logging. Утверждённый target общей политики заменяет старые error-default нормы только в явно мигрируемых потребителях; остальные несоответствия остаются видимым долгом.
- Field annotations, типы, ограничения и defaults — в dataModel. Application использует существующие jsonValidation resolver/catalog/REF-W, не новые normalize/validators-деревья или field-таблицы. Доменные refs проверяются на подготовленном индексе мира; политика и logging не помещаются в POJO.
- API читает флаг и делегирует application; общее место application один раз разрешает контекст. Frontend определяет, отправлять ли флаг. Контекст наследуется явно, не через глобальное состояние; не хранится в SQL/JSON мира.
- Разрешение/генерация не выполняют persist. Запись и transaction остаются в сервисах/repositories. Использовать существующие diagnostic/result и logging contracts после аудита; типизированные DTO не заменять словарями с дублированными wire-ключами/defaults.
- Не менять DAG-ноды, SQL-schema и не запускать backend-сервер. Для проверок — существующий test runner и изолированные fixtures, без рабочей БД.
- Новая общая основа не реализует wilderness placement, flora, forest simulation, topology или полный editor UI; эти домены подключаются позже. Placement priority является доменным правилом, а не универсальным сортировщиком любого поля.

## Этапы и зависимости

**Механизм выбора:** frontend определяет контекст; обычный импорт без policy-флага, авторская валидация через тот же импорт с `validate_only=true`. Имя и no-write семантика флага утверждены. Отдельный worldEdit-mode/endpoint запрещён. «Политики по умолчанию нет» означает отсутствие дополнительной валидационной политики, не отсутствие typed field contracts.

### E0. Аудит актуального кода и фиксация границ

Зависимости: нет. Вход — существующие rules/ТЗ и baseline тестов ниже.

Инвентаризировать `dataModel/annotationPolicy.py`, `jsonValidation/{resolve,types,facade,worldRow,worldSlices,worldSliceMerge}.py`, REF-W index, `worldBundleService`, bundle handlers, world CRUD/import routes, каскадные source factories и существующие domain emitters. Установить реальные способы создания RoomDef и передачи в `extend`: смена annotation сама по себе не подключает общий resolver. Отделить штатные defaults от error defaults и invalid→None/model_construct путей.

Результат: явный список потребителей/вызовов и зависимых операций; текущие public signatures/results, ownership diagnostics/log sinks; список нужных тестов и перечень конфликтующих норм ТЗ. Аудит не меняет поведение consumers.

### E1. Зафиксировать typed контракты до кода

Зависимости: E0.

Определить расширение существующих ResolveContext/field metadata, resolved/unresolved результат, report, reason/path/schema identity и границы объекта/операции. Проверка поля/домена возвращает факт; решение log/return централизовано. Данные реестров и report отделены от request context. Reference index строится из допустимых world-данных до membership checks; недоступный/неразрешённый реестр не заменяется каноном и не интерпретируется как «ссылка отсутствует».

Определить сохранение alias, enum/N1-W различий, вложенных моделей, root/list/dict registries и metadata CascadeChannel при чтении нового маркера. Partial update обрабатывается как patch: отсутствующие поля не материализуются defaults; проверка итогового состояния после merge с существующим объектом не должна путаться с проверкой patch. Не передавать частичный patch как готовую полную POJO.

Для API **до изменения route/write-path** зафиксировать DTO/status диагностики и конкретные side-effect boundaries: validate_only=true не пишет в БД/Pack и не запускает изменяющие мир задачи; отсутствие/false сохраняет обычный bundle import с существующим rollback при failed sections. Частичный persist не вводится. Не реализовывать no-write проверку записью с последующим rollback. Frontend после проверки отправляет обычный импорт, который заново проверяет актуальное состояние. Решение persist/dry-run закрыто; gate E1 требует технической фиксации read-only пути и response-контракта, а не повторного выбора этой семантики.

Gate: технические result/field/ref контракты зафиксированы в ТЗ до E2. Изменяемые нормативные разделы синхронизируются до кода своего этапа, а не только после общей миграции.

### E2. Общая основа resolver и обработки диагностики

Зависимости: техническая часть E1.

Ввести общий DefaultWhenMissing и поддержать его в существующем annotation introspection/resolve. Делегировать типы/ограничения Pydantic; сохранять field policies, nested paths и model-level invariants. Невалидные результаты не маскировать default/пропуском поля/unchecked construct. Единая обработка report: runtime WarningError через существующий emitter/sink либо validation report. Программные/инфраструктурные ошибки не поглощать.

На первом шаге не менять публичный return type `resolve_model` и все worldRow callers несогласованно: выбрать после E0 совместимый путь расширения/миграции, обновить границы вызова вместе с consumer. Допустима временная совместимость старого entry point по явному списку; второй field-policy engine, скрытый error fallback для нового маркера и локальные consumer policy branches запрещены.

Gate: общая основа проверена изолированно; контекст не теряется/не протекает между вызовами; ещё не включается новый публичный import flag.

### E3. Два пробных подключения

Зависимости: E2; необходимые для membership ref contracts из E1.

E3a — обычное `ForestsCategoryPolicy.forest_min_rainfall`; E3b — source `RoomDef.economic_tier` и его реальная граница передачи в `extend`. Оба используют одну основу, готовый request context и отдельный report; details ниже. Source membership по test-world index проверяется до каскада. Не менять declared cascade graph, ordering, RNG или terminal default ради wire-policy.

Gate: новые содержательные тесты каждого случая проходят. Не считать обычный кейс достаточным для разрешения широкой миграции.

### E4. Приёмка обоих подключений и regression

Зависимости: E3a и E3b.

Повторить обе команды baseline ниже и новые tests целевых свойств. Записать результаты отдельно от исходных 166. Старые expectations error fallback менять только для утверждённого изменения, сохраняя tests неизменяемых каскадных свойств. Исправления/повторный прогон — по фактическим failures, а не отключение checks.

### E5. Подключение import API и frontend-контекста

Зависимости: E4 и зафиксированные API response/side-effect boundaries E1.

Один необязательный флаг на существующем import API; общий application entry разрешает context, handlers наследуют его. Согласовать существующие normalize_world/connection normalization, handler signatures, error aggregation, bundle transactions и response DTO; не менять только route. Frontend формирует флаг по своему контексту без второго backend mode. Отдельный validation endpoint/adapter не создаётся.

Gate: integration tests обычного/валидационного вызова, false/omitted/true, вложенных handler paths, недопустимого wire, unresolved зависимости и отсутствия default. Для validate_only проверить **отсутствие** DB writes, Pack writes, persist remap/version allocation и запуска изменяющих задач как при успехе, так и при ошибке; штатные логи допустимы. Для обычного импорта проверить прежнюю transaction/rollback семантику и повторную проверку после preview. Использовать изолированную DB/файлы, не рабочие данные. Новое поведение не считается подключённым после unit tests одного resolve_model.

### E6. Явная миграция остальных потребителей

Зависимости: E5.

Начата миграция полей (2026-10-08). Группы: climate/terrain/hydrology/terrainMasks,
economy/resources/crops/livestock, locations/structures/settlements/transitions,
worldPack/roads/connections, race/perk libraries. Для каждой группы сохраняются
тип, alias, Field constraints, nullable, default_factory и CascadeChannel;
DefaultOnWire заменяется DefaultWhenMissing, enum-вариант сохраняет EnumWire.
Полный объект проходит Pydantic с его before/field/after validators; patch
проверяет только переданные значения и затем полное состояние после merge.
Invalid/null для non-nullable не заменяется default. Коллекции отвергаются
целиком при ошибке строки, включая scalar/enum registries. Legacy map adapters
сохраняют ошибочные строки для общей диагностики. Каноническое дополнение
отсутствующих записей остаётся отдельным штатным контрактом библиотек.
Удаляются invalid→default repair validators room/opening/height/stem;
missing auto/default и разрешённые legacy aliases сохраняются. Проверки
каскадных refs и миграция остальных consumer factories учитываются отдельно:
смена field annotations сама по себе не означает завершение всего E6.

Мигрировать список E0 по границам consumers: source refs/validation → consuming operation → report/logging → persist, с синхронизацией ТЗ каждого участка. Существующие domain-specific defaults не переносить автоматически. Контракты каскадного inheritance/default сохранять; новые no-error-default требования включать без промежуточного ложного успеха.

Gate: regression затронутых потребителей, обновлённый migration status и отсутствие временных compatibility paths в объявленном завершённым scope. Все дальнейшие plans используют принятую основу; доменные алгоритмы остаются в своих планах.

## Приёмка

### Эталон первого подключения: forest_min_rainfall

Зафиксировано мастером и реализовано: заменить семантику `DefaultOnWire[int]` для эталонного поля на общий `DefaultWhenMissing[int]`, сохранив `Field(default=45, ge=0)` и размер POJO в одну строку.

В E2 входят общий маркер в annotationPolicy, делегирование стандартных ограничений Pydantic и общий result/report API. В E3 — пробные подключения `ForestsCategoryPolicy.forest_min_rainfall` и каскадного source; E4 проверяет оба; E6 мигрирует остальных consumers после приёмки API. Не добавлять validator/logging/context в каждый POJO и не переписывать все поля механической заменой без проверки их индивидуальных контрактов.

Контракт и ожидаемые значения — [ТЗ общей политики](../../docs/tz_runtime_world_edit_policy.md#default-только-при-отсутствии-эталон-pojo-утверждено-2026-10-08). Обязательные проверки эталона: missing→45, 60→60, -1/"abc"/null→unresolved без 45; одинаковые ошибки в обычном/валидационном вызове с разной централизованной обработкой; partial missing не меняет поле; вложенный path сохраняется. Нельзя устранять ошибку через пропуск поля, повторное заполнение default или model_construct. Конкретные значения в примерах — expectations теста; implementation читает schema, не копирует 45/ge=0 в resolver.

Контекст ограничен служебными параметрами запроса/обхода; report и доменные зависимости отдельны. Реализацию основы продолжать поверх существующих resolve/field metadata, без второго policy engine.

### Второе пробное подключение: source поля каскада

Реальный source: `RoomDef.economic_tier` (`backend/app/dataModel/locations/structure/room/roomDef.py`), сейчас `Annotated[DefaultOnWire[EconomyTierKey | None], CascadeChannel(ECONOMIC_TIER, ScopeLevel.ROOM)] = None`. Целевая миграция меняет wire-политику на DefaultWhenMissing, сохраняет nullable тип, default=None, CascadeChannel, связи и identity параметра. Не ставить непустой default в каждое звено.

Проверять через общий resolve/report и границу передачи source в существующий `extend`, а не отдельную копию каскада. В тестах допускаются локальные world/source fixtures без записи в рабочую БД. Принадлежность tier проверяется относительно реестра тестового мира, а не только как строковый тип.

- Валидное authored значение ребёнка побеждает наследованное; provenance указывает реальный источник.
- Отсутствующее поле и допустимый None продолжают наследование; partial missing не переписывает существующее authored значение.
- Полностью штатно пустая цепочка использует объявленный terminal default из CascadeDefault source. Это разрешённое доменное поведение, не error fallback; сохраняются существующие snapshot/provenance/logging semantics.
- Невалидный тип или ссылка вне реестра → unresolved и диагностика с source path. **Не** передавать ошибку в каскад как None, пропущенное поле или EmptyLink; не наследовать родителя и не применять terminal default для маскировки ошибки.
- Существующий resolver получает только допустимые source-объекты. Если source unresolved, зависимая операция явно неразрешена по общему контракту; не менять семантику None в LocationContext и не добавлять untyped sentinel в POJO.
- ResolveContext и LocationContext остаются разными сущностями. Отчёт хранится отдельно; при продолжении независимых объектов ошибки не теряются.
- Два API-сценария дают одинаковое разрешение/диагностику; реакция централизована. Повторные extend и sibling branches не меняют ancestors, RNG и provenance.

Новые тесты для обоих подключений писать как regression к согласованным свойствам, а не для проверки существования нового имени marker. Старые ожидания error defaults, если найдены, менять только с явным объяснением согласованного изменения; green baseline не является основанием сохранить ошибочный fallback.

### Прогон существующих тестов до реализации (2026-10-08)

Из backend, текущим `./.venv/Scripts/python.exe`, выполнены:

```text
python -m unittest tests.test_pojo_policies tests.test_location_context_contract tests.test_context_extend tests.test_cascade_context_baseline tests.test_cascade_migration_m2 tests.test_bundle_named_location_wire tests.test_settlement_size_resolve
→ 134 tests, OK

python -m unittest tests.test_world_row_t28 tests.test_terrain_masks tests.test_mask_domain_materialize tests.test_import_created_at_default
→ 32 tests, OK
```

Всего **166 существующих тестов прошли**, оба процесса завершились exit=0. В выводе есть текущие диагностические сообщения/defaults; это не подтверждение соответствия новой no-error-default policy. Код и существующие тесты данным запросом не изменялись. Этот прогон фиксирует **исходное состояние**, а не приёмку ещё не реализованных пробных подключений. В E4 повторить оба набора плюс новые тесты обычного/каскадного случая и записать результат отдельно; E5 требует дополнительных integration tests API.

### Общие проверки

- Одинаковые входы дают одинаковое доменное решение в runtime/worldEdit, включая reason; различаются представление/применение.
- Разрешимый конфликт авторазрешается детерминированно.
- Неразрешимый результат даёт runtime WarningError в существующем sink без defaults; зависимая операция не выдаёт ложный успех.
- Независимые операции продолжаются там, где это допускает контракт; неполнота явно наблюдаема.
- WorldEdit не применяет скрытое исправление авторских данных.
- Штатное отсутствие optional-поля и invalid/unresolved значение различаются.
- Ошибки инфраструктуры/программирования не подавляются доменным WarningError.
- Отсутствие/false флага оставляет обычный импорт; true включает валидационную policy. Выбор выполняется один раз; вложенные handlers получают готовый context. Флаг не записывается в мир; wire/integrity checks действуют в обоих случаях.
- Разные поля сохраняют свои ограничения и reason codes. Missing/null/empty/type/range/ref/domain conflict различаются; вложенные field paths и межполевые ошибки сохраняются. Consumers не выбирают fallback/reject/log локально.

## Открытые технические решения

Имя флага, persist и технические DTO закрыты: validate_only=true — no-write проверка; обычный импорт сохраняет bundle transaction, без partial persist. DTO/status, result/report, ref-index и patch semantics зафиксированы в ТЗ и реализованы. E6 остаётся отдельной поэтапной миграцией полей, а не механической заменой всех aliases.

Зависимости: E0 → технический E1 → E2 → E3a/E3b → E4 → E5 → E6; API-контракты E1 также обязательный вход E5. ТЗ общей политики определяет нормы, этот план — порядок реализации; ссылка ТЗ на критерии приёмки плана не создаёт обратную зависимость исполнения. Wilderness зависит от этой основы, основа не зависит от реализации wilderness/placement.

## Реализация и аудит E0–E5 (2026-10-08)

- `annotationPolicy` / `registryKey`: новый DefaultWhenMissing, сохранение CascadeChannel и nominal registry target при introspection; тип/default/constraints остаются в dataModel.
- `jsonValidation/resolve`: ResolveReport отдельно от служебных параметров; child наследует report/flag/schema/path. UnresolvedModelError и ResolveResult исключают выдачу invalid POJO. Preflight новых contracts до legacy fallback родителей, включая вложенные list/dict; ограничения делегируются Pydantic. `resolve_patch` возвращает supplied mapping; `resolve_model` отказывает в выдаче полной POJO для частичного нового контракта.
- `facade`, `worldSliceMerge`, `worldRow`: invalid pilot прекращает зависимую операцию; независимые import slices сохраняют diagnostics. CRUD blob patch объединяется с текущим состоянием до полной проверки; supplied registries заменяются, не считаются patch отдельной записи.
- `RoomDef.economic_tier` и `locationScope.room_context`: проверка исходного реестра и source через существующий WorldRegistryIndex до extend. Invalid/missing index — unresolved; null/missing source сохраняют inheritance/terminal default. Граф, RNG и provenance не изменены.
- `WorldBundleService`: единый `_prepare_bundle` до любых writes/remap. Все девять production handlers имеют read-only validate_section; подготовка использует реальные prepare_body/prepare_import consumers. World/connection normalization получают один context. Успешный обычный return — прежний tuple; preview — ImportValidationReport. Wire/preflight failures ordinary import → 422; failures при write → прежний rollback/207.
- `worlds/import` + frontend `worldApi.importWorld`: необязательный validate_only; preview 200 `{validate_only, valid, issues}`, остальные HTTP request errors сохраняются. UI редактора по-прежнему placeholder и в этот этап не входит.
- SQL dataclass проверяет constructor shape, не подменяет Pydantic wire schema: в legacy storage annotations есть dict-колонки с list wire. Это сохраняет актуальные fixtures без изменения SQL.

## Оставшаяся миграция E6 — состояние перед consumer-срезом

Исторический статус; выполненный позднее охват указан в разделе «Реализация consumer-среза E6».

1. **Завершено:** 556 dataModel полей (88 модулей) + 22 поля bundle connection DTO. Перечень — [field migration](../../docs/runtime_policy_field_migration.md). В `resolve` удалены fieldwise retry/model_construct, invalid defaults и row skip. Оставшиеся старые alias exports — deprecated имена той же новой policy, не отдельный execution path. Canonical overlays сохраняются только как штатное дополнение отсутствующих записей. SQL World registry metadata приведена к list; NULL/исторический пустой map hydrate корректно, malformed JSON не заменяется пустым реестром. SQL schema не менялась.
2. Прочие каскадные источники (`BundleNamedLocation`, settlement/district/plot и материалы): провести membership/source validation до их extend по той же основе; не менять null/default графа. В этой реализации мигрирован room tier, остальные источники не объявлены исправленными.
3. Domain emitters и standalone library/CRUD пути вне bundle preflight: legacy INFO/WARNING/default conversions и broad catches инвентаризированы, не заменены общим reject. Identity race/perk различает None-auto и invalid пустую строку. Room/opening/height/stem repairs и runtime level row skip удалены; горизонтальный passage type больше не становится doorway при ошибке. Остальные domain-specific auto/repair validators требуют отдельного аудита; например sides filtering, placement-height и material fallback не объявлены мигрированными этим срезом.
4. `ResolveMode` сохранён как совместимый параметр диагностики; в общем field engine больше нет ветвлений решений по IMPORT/RUNTIME. Реакция определяется только request flag. Остальные direct runtime callers мигрировать по границе операции, не копировать ветвления policy в consumers.

## Проверки реализации

- Финальная приёмка после всех изменений: **196 tests, OK** (20.515 s): исходная регрессия, 13 pilot tests, 9 import/API tests, bundle level/remap и все fixture checks с `world_test_002`. Проверены также model-level invariants, authored field presence (`count`/`count_range`) и propagation инфраструктурной ошибки. Результаты промежуточных прогонов ниже — история, counts не складываются.
- Основная регрессия: **192 tests, OK** — исходные 166, оба новых набора, bundle level/remap и четыре standalone fixture checks.
- После уточнения мастером имени `world_test_gen` → `world_test_002` обновлены оба упоминания в `test_fixture_bundle_import`; **24 tests, OK**, включая импорт/export всех восьми fixtures, оба новых набора. Наборы пересекаются; их counts не складывать.
- После подключения generic RegistryKey membership к существующему WorldRegistryIndex повторены **11 pilot tests, OK**.
- `npm run typecheck:cascade`: 0 errors/warnings; 4 ожидаемых negative contracts подтверждены. `npm run build:web`: OK. Изолированная SQLite, без рабочей БД/сервера; Windows asyncio integration tests выполнены вне sandbox из-за блокировки внутреннего socketpair.

## Приёмка миграции полей E6 (2026-10-08)

- Полный ввод передаётся исходной Pydantic-модели: работают before/field/after validators, Field constraints, aliases, explicit null и authored presence. Patch использует compiled field schemas той же модели, не вызывает defaults отсутствующих полей; nested nullable blob patch рекурсивен, supplied collection проверяется полностью. Cross-field invariants — после merge.
- 10 новых тестов `test_policy_field_migration`; 140 целевых synchronous tests, OK. Исходные 196 контрактных тестов после переключения resolver/DB metadata, OK (12.747 s), включая восемь fixtures и no-write preview. Counts пересекаются.
- Широкий контроль исходного HEAD в изолированной копии: 1621 tests, 3 failures + 38 errors + 1 expected failure. Итоговый прогон миграции: **1631 tests, 32 errors + 1 expected failure** (69.942 s); все 32 идентификатора ошибочных тестов присутствуют в baseline; это не доказывает отсутствие новых регрессий поведения (см. повторную проверку ниже). Это не зелёный полный набор: остаются прежние SQL-column и неполные fixture/source ошибки. Тестовые значения civic → town_hall и ожидания invalid→default явно мигрированы; SQL schema и DAG не менялись, tests не отключались.
- `npm run typecheck:cascade`: 0 errors/warnings, 4 ожидаемых negative contracts подтверждены. `git diff --check`: OK. Backend server и рабочая БД не запускались.
- Библиотечный шаблон `7c3a4d5e-6f7a-4b8c-8d9e-1f2a3b4c5d6e` явно задаёт house вместо неизвестного manor, который прежде молча давал house. UID/геометрия сохранены.
- E6 целиком не закрыт: membership остальных cascade sources, standalone library/CRUD и доменные auto/repair boundaries остаются отдельными пунктами выше. Миграция полей не означает проверку всех ссылок/алгоритмов генерации.

## Повторная проверка миграции E6 (2026-10-08): E6-R1–R3 исправлены

Следующие ошибки воспроизведены после приёмки выше и исправлены; ниже сохранены исходные сценарии и критерии. Количество мигрированных полей подтверждено (556 dataModel + 22 bundle DTO = 578), но соответствие заявленному контракту неполное. Эти пункты входят в исправление объявленного scope миграции полей, отдельно от остальных незавершённых consumer/ref boundaries E6.

### E6-R1 — P1: patch выбирает первую модель union и теряет авторские изменения

- **Код:** `backend/app/application/jsonValidation/resolve.py:232` (`_nested_model`), `:213` (рекурсивный `resolve_patch`); compiled patch schema заменяет вложенную схему на `any_schema` в `:130–131`.
- **Причина:** для union выбирается первая найденная BaseModel, без учёта discriminator и текущего состояния. Для `terrain_masks.default_mountains.default_form` это всегда `MountainFormBySides`, хотя допустимы также `StarForm`, `PeakForm`, `PlateauForm`.
- **Воспроизведение:** существующая форма `{"form_type":"star","rays":5,"inner_ratio":0.45}`; patch `{"terrain_masks":{"default_mountains":{"default_form":{"rays":7}}}}`. `normalize_world(..., partial=True)` превращает `default_form` в `{}`; после merge и полной проверки остаётся `rays=5`, без ошибки. Patch с `{"form_type":"star","rays":7}` отвергается с требованием `form_type='by_sides'`, хотя полный ввод такого объекта валиден.
- **Последствие:** потеря авторских изменений либо отказ в допустимом редактировании. Full validation после merge не обнаруживает уже отброшенное поле.
- **Критерий исправления:** сохранить typed union/discriminator contract; для patch без discriminator разрешать ветку с учётом существующего объекта, не отбрасывая переданные поля до merge. Проверить изменение `rays` существующей звезды, явный выбор каждой формы и ошибочные значения полей альтернативных веток. Отсутствующие поля не должны получать defaults на стадии patch.

### E6-R2 — P2: ошибочный rooms вызывает TypeError при подготовке диагностики

- **Код:** `backend/app/dataModel/locations/structure/building/structureTemplate.py:125`; аналогичная обработка в `backend/app/application/worldData/generators/structure/structureGeneratorService.py:405`.
- **Воспроизведение:** у в остальном допустимого шаблона передать `levels[0].rooms=null`, `1` или `false`. `LevelDef` выдаёт ValidationError, но обработчик пытается перебрать это значение для формирования `room_ids`. Вызов `resolve_result(StructureTemplate, raw)` выбрасывает `TypeError: ... object is not iterable`.
- **Последствие:** ошибка пользовательских данных выходит из validation pipeline как программное исключение вместо unresolved/report; preview/import не получает штатную диагностику.
- **Критерий исправления:** формирование контекста ошибки должно быть безопасно для любого wire-типа `rooms`. Проверить оба места обработки и случаи null/int/bool: штатный validation report/GenerationError с контекстом уровня, без TypeError и без пропуска ошибочного уровня.

### E6-R3 — P2: non-nullable HillPolicy.shapes сохраняет null→default repair

- **Код:** `backend/app/dataModel/terrainMasks/hillPolicy.py:30–31`, before-validator `_shapes_tuple`.
- **Воспроизведение:** `resolve_result(HillPolicy, {"shapes": None})` возвращает resolved с `shapes=()`. Ввод `{"terrain_masks":{"default_forests":{"hills":{"shapes":null}}}}` также принимается при полной и partial нормализации.
- **Причина и последствие:** validator заменяет null пустой палитрой до проверки non-nullable `DefaultWhenMissing[tuple[HillShape, ...]]`. Пустая палитра означает весь каталог фигур; недопустимый null молча меняет поведение генерации. Wire-контракт `shapes` разрешает массив; штатные случаи всего каталога — `[]` и отсутствие ключа (`docs/tz_world_pack_storage.md`, L2 hills shapes).
- **Критерий исправления:** null должен давать unresolved с точным путём, одинаково при полном вводе и patch. Сохранить штатное поведение missing/[], допустимые enum-токены и дубликаты как веса; ошибочные элементы не фильтровать.

### Результаты и ограничения повторной проверки

- Повторно прошли 201 тест: 23 migration/pilot, 169 тестов затронутых контрактов и каскада, 9 import/API с временной SQLite. Перечисленные выше сценарии воспроизведены отдельно и существующими тестами не покрыты. Сервер и рабочая БД не использовались.
- Сопоставлены `backend/policy-migration-acceptance.log` и `backend/policy-migration-baseline.log`: все 32 упавших теста acceptance присутствуют в baseline (38 errors + 3 failures); новых упавших тестов по идентификаторам нет. Причины отдельных падений изменились: например, `test_array_and_unknown_dropped` теперь останавливается раньше на неизвестном purpose. Это не доказательство отсутствия новых регрессий поведения; прежнее утверждение «новых регрессий нет» выше следует читать с этим ограничением и с учётом E6-R1–R3.
- Широкий набор заново не запускался. Проверка RNG/provenance ограничена просмотром изменений и целевыми тестами. Остаток E6 (другие cascade sources, standalone library/CRUD, domain repair и direct runtime callers) остаётся открытым.


### Исправление E6-R1–R3 (2026-10-08)

- **R1 закрыт:** compiled patch schemas рекурсивно сохраняют nested field before-validators, aliases, nullable и constraints. Tagged union с явным discriminator проверяет выбранную ветку без defaults отсутствующих полей. При отсутствии discriminator сохраняются все authored keys: ветку выбирает обязательная полная проверка после merge с текущим объектом. Для untagged model union выбор также отложен до merge. `resolve_patch` сам по себе не подтверждает допустимость полного состояния. After/wrap field validators, потребляющие nested POJO, и model validators выполняются при полной проверке после merge; collections по-прежнему содержат полные строки.
- **R2 закрыт:** оба обработчика собирают room IDs только из списка; null/int/bool дают штатный unresolved report либо GenerationError с контекстом уровня, без TypeError.
- **R3 закрыт:** удалён null→empty validator HillPolicy.shapes. Missing/[] сохраняют весь каталог, дубликаты остаются весами; null и ошибочные элементы отклоняются.
- Добавлены 7 regression tests `test_policy_revision_r1_r3` и интеграционный тест сохранения star patch/отсутствия writes при ошибках. **188 synchronous tests, OK**, включая изменённые POJO, resolver, terrain, structure, registry и cascade contracts (`backend/policy-r1-r3.log`); **10 import/API tests, OK** на временной SQLite (`backend/policy-r1-r3-api.log`). Наборы не пересекаются: всего 198 tests. `npm run typecheck:cascade`: 0 errors/warnings, 4 negative contracts подтверждены. `git diff --check`: OK.
- Широкий suite повторно не запускался; его прежние 32 errors не объявляются исправленными. Остальные consumer/ref boundaries E6 остаются открытыми.


## Доведение consumers E6 (2026-10-08)

Дополнение material-контракта: `MaterialRegistryEntry.transparent` переводится
из bool в конечное числовое значение процентов `[0, 100]` (дробные допустимы),
missing default `0`. Schema owns bounds/type; invalid/null/bool не исправляются.
Порядок: профильное ТЗ и POJO → canonical/fixtures (`false→0`, `true→100`) →
проверки full/patch и runtime/preview parity → fixture import/roundtrip.
В коде расчётных потребителей transparent пока нет; FOV-композиция и семантика
vision_block в этот срез не входят. SQL schema и рабочая БД не меняются.
Реализовано: strict numeric transparent, canonical/fixtures и все актуальные ТЗ-
примеры мигрированы. Приёмка: 73 material/cascade/field tests и 16 import/API/
fixture tests OK; проверены дробное сохранение, no-write при ошибках, одинаковые
facts двух режимов, bounds/finite/bool/null, partial patch и воспроизводимость
world_test_all. Typecheck cascade: 0 errors/warnings, 4 negative contracts;
git diff --check OK. Полный suite после этого локального изменения не повторялся.

Базовая политика: docs/tz_runtime_world_edit_policy.md § Миграция полей E6.
Целевой поток: typed source → source membership по CascadeChannel/RegistryKey и WorldSlice → extend/materialize → единый reject_unresolved → граница операции. LocationContext, граф и RNG не меняются; ResolveContext передаётся отдельно. Library/CRUD использует тот же resolve, ловит только ожидаемые data errors; infrastructure exceptions проходят наружу.

1. **Source boundaries:** locationScope + новый helper sourceValidation в jsonValidation. Поля обнаруживаются из CascadeChannel, вложенные refs — RegistryKey; vocabulary из существующего WorldSlice и WorldRegistryIndex. Проверить NL, settlement payload/skeleton, district, plot, room, range/band/material; unknown/unavailable не продолжают наследование. Проверка: source regression + cascade suites.
2. **Library/CRUD boundaries:** structure/relief/building library services и их consumers. Убрать row skip и broad catches там, где они скрывают data/infrastructure errors. Сохранить явное различие outline и plot; не считать outline-only запись повреждённым plot. Проверка: изолированные repository doubles, import/API tests, infrastructure propagation/no-write.
3. **Domain boundaries:** perimeterBarrier sides, tier rank/materialization, materialResolver и placement-height consumers. Различать штатные missing/auto и invalid; domain issues передавать через reject_unresolved без local policy switches. Проверка: malformed/ref/no-candidate cases + существующие geometry/material/placement contracts. По завершении указать точный охват аудита, а не объявлять все domain алгоритмы проверенными по смене annotation.

### Реализация consumer-среза E6 (2026-10-08)

- Source validation подключена к NL, settlement payload/skeleton, district, plot и room до extend. Проверяются model invariants, включая повреждение через model_copy, затем каналы и RegistryKey membership по существующему WorldSlice/WorldRegistryIndex. NL получает location_type_registry конкретного мира при повторной проверке. Неизвестный ключ, недоступный реестр, неверный band/range прекращают зависимую операцию. Null inheritance, DAG, provenance и RNG не менялись.
- Standalone structure/relief/building library и race/perk CRUD используют общий resolve. Race/perk registry включены в WorldSlice; SQL metadata — list без изменения SQL schema. Повреждённые rows и отсутствующие библиотечные pointers не отбрасываются. Runtime inline plot accessor также отказывает всей операции. Валидный outline-only остаётся допустимым видом library body. Preflight сохраняет диагностику shared-context и standalone consumers; infrastructure exceptions не конвертируются в data errors.
- Domain-срез: стороны perimeterBarrier, settlement size, tier rank, tier band/range, выбор материалов, явная высота двери ниже passage_height и C31 relief L/угол. Ошибочные значения не фильтруются и не заменяются default. C31 WARN + угол 20° был явным прежним контрактом; теперь superseded общей политикой: reject при import/preview и runtime boundary. Оба geom-поля отсутствуют → штатный L=1. Правила отражены в профильных ТЗ.
- Объявлены уже используемые terminal default material keys window_glass/porthole_glass/vent_mesh/dirt_road. Без construction tag, поэтому обычный default не добавляет RNG draw. Синхронизированы world_template и производный world_test_all штатным build-скриптом. Тестовые parent_wall/parent_floor переименованы в test_parent_*_material и явно включены в реестр; iron объявлен в тестовом wall-material каталоге. Геометрические сравнения и RNG assertions сохранены.
- Placement audit: columnSurface использует map_z/0 только при отсутствии поверхности, median_surface_z — supplied fallback только при отсутствии sample; это штатный контракт отсутствия. Недопустимая явная door_height теперь unresolved; прежний отказ проёма, достигающего потолка, сохранён. Этот срез не объявляет все coordinate consumers и все R21 relief fallback ветки мигрированными: их аудит остаётся отдельным доменным охватом.
- Целевые synchronous проверки: 227 tests OK, включая исходные cascade/shape/geometry/material assertions и новые consumer cases. Typecheck cascade: 0 errors/warnings, 4 negative contracts подтверждены. Итог широкого прогона фиксируется ниже отдельно; исторические counts не складываются.

### Итоговая проверка consumer-среза

Следующий атомарный шаг E6-R21 (авторизация «E6 дальше»): контракт ошибок выбора
relief/grade/canal. ТЗ: tz_terrain_relief §Политика выбора и §Canal, общая политика
tz_runtime_world_edit_policy. Цель: отказ без SLOPE/first-template/empty-canal
подмены при empty candidates, missing fixed UID/body, schedule hole, unknown canal
и конфликтующих enabled canal rules. Штатные no-condition/slope_none/no-canal
сохраняются. Data flow: typed policy/registry → pure domain resolve → facts через
существующий reject_unresolved → граница вызывающей операции. Дополнительный
ResolveContext передаётся отдельно; никаких новых режимов/field registry/SQL writes.
Файлы: relief/pick/templatePick, gradePass, gradeConstrained; relief/canal/
attachments, seedResolve, obstacleResolve; вызывающие ribbon/mountain/detailed
grade consumers; профильные tests. Сигнатуры получают optional resolve_ctx,
выбранный body больше не возвращает None при ошибочной ссылке. Проверка: R21
parity/no-fallback/no-partial-result + relief/mountain/detailed suites + import API
и full suite. Done: мигрированы старые fallback assertions, сохранены valid RNG/
geometry assertions, перечислены непроверенные boundaries. Coordinate/placement
аудит — следующий самостоятельный шаг E6, не смешивается с этим контрактом.

### Реализация E6-R21 (2026-10-08)

- Переведены ошибки empty candidates/fixed UID/body, schedule hole и canal refs/
  enabled-rule conflict на reject_unresolved. Убраны first-template, all-SLOPE,
  skip-on-missing-body и empty-StructureCanal подстановки у проверенных consumers.
  GradeConstrained проверяет schedule до ontology skip. ResolveContext передаётся
  отдельно; runtime/preview используют одинаковые facts. Штатные declare,
  no-condition/slope_none, no-canal, explicit disable и no-space cut сохранены.
- Старые fallback assertions мигрированы; mountain mask fixtures явно объявляют
  slope-template вместо зависимости от fallback, геометрические assertions
  сохранены. Добавлены parity, no-RNG-on-error и no-mutation проверки.
- 86 целевых relief/mountain/mask tests OK (`backend/policy-e6-r21-sync.log`);
  19 import/API/fixture/domain-root tests OK (`backend/policy-e6-r21-api.log`).
  Typecheck cascade: 0 errors/warnings, 4 negative contracts; compileall и
  git diff --check OK.
- Охват ограничен перечисленными domain resolve paths. Optional ResolveContext
  проверен напрямую в обоих режимах. Новый preflight всех world fixed/canal refs
  через import API не добавлялся; доступность library body зависит от каталога
  вызывающей операции. Вложенные barrier refs, повреждённые typed models и refs
  в неисполняемых ветках требуют отдельного аудита. Coordinate/placement также
  остаётся открытым. Все E6 этим шагом не закрыты; SQL/рабочая БД не менялись.
- Полный прогон: 1661 tests за 77.082 s, 21 errors, 1 expected failure,
  0 assertion failures (`backend/policy-e6-r21-full.log`). Список ERROR IDs
  совпадает с предыдущим `policy-e6-final.log`; suite остаётся незелёным.
  Совпадение IDs не доказывает отсутствие любых регрессий; валидные relief/
  geometry/RNG контракты дополнительно проверены целевым набором выше.

- **236 synchronous tests OK** (`backend/policy-e6-sync-final.log`) и **38 import/API/fixture tests OK** (`backend/policy-e6-api-final.log`). Проверены одинаковые facts и runtime/preview log policy, отказ до extend/write, infrastructure propagation, затенённые invalid sources, custom-world payload context, model_copy invariants, canonical partial overlays без исправления supplied invalid значений, RNG и геометрические сравнения, восемь fixtures и воспроизводимость world_test_all.
- Полный прогон: **1650 tests, 21 errors, 1 expected failure, 0 assertion failures** за 80.542 s (`backend/policy-e6-final.log`). Все 21 идентификатора встречаются в изолированном baseline. Остаток: map_cell_patches без system_grade_uid, несовместимый renderer constructor, старые purpose/plot fixtures с неполными levels и прежний отказ прямого wilderness persist. Полный suite не зелёный; совпадение идентификаторов не объявляется доказательством отсутствия любых регрессий. Последняя корректировка canonical-overlay проверки дополнительно покрыта итоговыми 236 целевыми тестами.
- Явно мигрированы ожидания устаревшего auto-repair: low door_height, unknown settlement rank, invalid perimeter sides, C31 geom и повреждённый topology freeze. Freeze больше не считается отсутствующим и не запускает регенерацию при ошибке. Территориальный geometry-тест объявляет medium, ранее получавшийся неявным fallback для hamlet; проверка геометрии сохранена.
- Typecheck cascade: 0 errors/warnings, 4 negative contracts подтверждены; compileall и git diff --check OK. Backend server и рабочая БД не запускались, SQL schema не менялась. R21 и остальные coordinate consumers не объявлены закрытыми этим срезом.
