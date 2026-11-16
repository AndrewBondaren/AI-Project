# GEO-1 (Hydrology / designed water) · открытые контракты для DAG — черновик на согласование (2026-11-16)

**Статус:** DRAFT. Приняты решения пользователя 2026-11-16: представление source R1 + G1 (G2/R3 отложены); выбор стратегии — операция DAG, отдельный pipeline на стратегию; настройки — отдельный `HydrologySettingsService`. CRUD данных — отдельные сервисы body / union / river (вариант B, целевой; пустые места — STUB). Ожидаемый отказ source — типизированный результат pipeline, решение о продолжении — в DAG. Остальное OPEN. Ноды GEO в DAG согласуются только с пользователем.

**Целевое требование (пользователь, 2026-11-16):** прямые междоменные взаимодействия запрещены. Оркестрация и передача данных между доменами — строго через DAG: домен возвращает результат DAG, DAG передаёт его в публичную операцию другого домена (см. `dag-generator-interface.mdc`, запрет №3). Существующие прямые вызовы GEO ↔ Terrain / Placement / Spatial / Planning — legacy, удаляются при cutover соответствующей операции.

Нормы: `.cursor/rules/dag-generator-interface.mdc` — §«Обязательная приёмка плана любого домена», §«Публичные Pipeline», §«Критерий приёмки: доменные CRUD API → DAG», §«Конкретность публичного CRUD-контракта». Ноды DAG пишет пользователь; этот документ **не** предлагает NodeId и bindings — только доменные контракты. Всё ниже — **предложение**, имена новых классов — рабочие (OPEN).
Представление source: R1 + G1 (решение 2026-11-16).

## 1. CRUD данных домена — по сущностям canonical source (решение 2026-11-16: вариант B, целевой)

Источник сущностей: `CanonicalOpenWaterSource` (`dataModel/hydrology/query/source.py`; runs `WaterMembershipRun`; ошибки `WaterSourceIssueCode`), `PhysicalWaterUnion` (`dataModel/hydrology/physicalWaterUnion.py`), реки (`dataModel/hydrology/rivers.py`). Каждая сущность — свой публичный класс с отдельными методами create/read/update/delete. Неизвестное до точных контрактов — **STUB** (явная заглушка; в коде — тип/метод объявлен, реализация отсутствует и это видно, без fallback и без молчаливых дефолтов).

| Сервис (рабочее имя) | Сущность | Create | Read | Update | Delete | Инвариант после операции |
|---|---|---|---|---|---|---|
| `WaterBodyService` | физический водоём: UID, liquid, level, wet runs (R1), bed (G1) | STUB | STUB (в т.ч. bounded window — по контракту SPATIAL-1) | STUB | STUB | union membership и связность пересчитаны; revision source увеличена |
| `WaterUnionService` | `PhysicalWaterUnion`: состав тел, общий уровень, связность | STUB | STUB | STUB | STUB | все члены существуют; одно тело — в одном union |
| `RiverService` | реки: трасса, связь с телами (mouth/drainage) | STUB | STUB | STUB | STUB | ссылки на тела валидны |

Общее для всех сервисов (OPEN до точных контрактов): POJO входа/результата в `dataModel/hydrology/`, конкретный подкласс `FieldPathError[...]` для ошибок, правило revision, проверка целостности source после операции. Пересборка source целиком — не CRUD, а pipeline P5.

## 2. CRUD настроек домена

Существующие POJO: `WaterGenerationSettings` → `WorldWaterGenerationSettings` / `CategoryWaterGenerationSettings` / `BodyWaterGenerationSettings` (`dataModel/hydrology/generation/waterGenerationSettings.py`); `HydrologyCategoryPolicy` (`dataModel/hydrology/category.py`).
**Решение 2026-11-16:** отдельный публичный класс `HydrologySettingsService` с `create/read/update/delete` для world / category / body уровня. OPEN: модуль, сигнатуры, POJO ошибки; граница с cascade (G1/G2) — каскад остаётся механизмом resolve, CRUD настроек — через этот сервис.

## 3. Открытые линейные pipeline (без ветвления; суффикс `Pipeline`)

Каждый — одна доменная операция, единый Input/Output/Error, вызывается напрямую из DAG. Источник порядка — утверждённый в GEO-1 порядок terrain↔water (G10-A «terrain/water order — AGREED 2026-10-31»).

| # | Pipeline (рабочее имя) | Операция | Из чего собирается (существующий код) | Выход |
|---|---|---|---|---|
| P1 | `HydrologyPlacementUniversePipeline` | подготовка placement universe | G8 / G8-A | universe + candidates |
| P2a–P2e | по одному на стратегию (решение 2026-11-16): `AuthoredRegionWaterPipeline` (G5), `CoastlineWaterSourcePipeline` (G5-C2/C3, I11.1–I11.3, `design_native_coastline`), `ContinentalNoiseWaterPipeline` (G6), `PlateWaterPipeline` (G7), `PlateNoiseWaterPipeline` (G7-C) — имена рабочие | draft одного source одной стратегией | G4-C + код стратегии | `FineProceduralWaterDesignDraft` (общий тип результата — OPEN) |
| P3 | `FinePlacementPreparationPipeline` | fine placement preparation (следующий шаг после I11.3) | план, не начат | admitted fine candidates |
| P4 | `FineWaterFillPipeline` | fine fill по frozen terrain window | G10-A «frozen window → accepted fine water», decision-driven fill | materialized fine water |
| P5 | `CanonicalWaterPublicationPipeline` | сборка source R1+G1 | I2 (bed), I3.1 (wet runs), I4.1 (assemble) | `CanonicalOpenWaterSource` |
| P6 | `FineRiverRoutingPipeline` | fine routing рек | G10-A native fine river routing | river facts |

## 4. Точки ветвления — выносятся в DAG (сейчас внутри домена)

1. Решение генерации `HydrologyGenerationDecision` / `HydrologyExecutionMode` (запускать ли генерацию категории) — DAG выбирает, запускать ли P2–P5.
2. Диспатч стратегии — **решено 2026-11-16:** выбор операции в DAG, pipeline P2a–P2e. Существующий strategy dispatch в домене подлежит выносу при cutover.
3. Per-source fail/continue — **решено 2026-11-16 (вариант a):** pipeline стратегии возвращает типизированный результат «draft | отказ с причинами» без исключения для ожидаемого отказа; DAG собирает результаты, передаёт успешные drafts в P3, отказы — в отчёт. Терминальные ошибки (`diagnostics`) остаются исключением и останавливают build. Цикл с `session.fail` в `designPreparation` подлежит выносу при cutover.
4. Порядок terrain → water → relief — порядок узлов DAG, без изменения.

## 5. Междоменные входы (протокол CRUD; все OPEN до согласования нод)

| Потребитель (GEO) | Нужно | Владелец | Операция владельца |
|---|---|---|---|
| P1/P2 | relief spec / frozen pre-water terrain window | Terrain | Read (OPEN: конкретный метод) |
| P3 | P2 admission / конкуренция | Placement | OPEN |
| §1 Read | контракт bounded spatial read | Spatial (SPATIAL-1) | OPEN |
| P5 | revisions / planning revision | Planning (G0-S) | OPEN |

## 6. Вопросы к пользователю

1. ~~Гранулярность CRUD данных~~ — решено: отдельные сервисы (B), STUB до точных контрактов.
2. ~~Диспатч стратегии~~ — решено: DAG.
3. ~~Per-source fail/continue~~ — решено: (a), DAG.
4. ~~Настройки~~ — решено: `HydrologySettingsService`.
