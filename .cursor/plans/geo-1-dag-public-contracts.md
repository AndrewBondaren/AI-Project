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

## 7. Требования к DAG-контрактам GEO из принятых контрактов Snapshot (2026-11-16)

Основания: [snapshot-public-contracts-dag-integration.md](snapshot-public-contracts-dag-integration.md) §3–§7, [gen-dag-snapshot-node-contracts.md](gen-dag-snapshot-node-contracts.md) §1–§4, `docs/tz_world_snapshot.md` § «Staged artifacts», § «ArtifactRef, staging и domain SQL rows». Здесь только требования к контрактам GEO; NodeId, bindings и состав нод не назначаются (§0).

| # | Требование к GEO | Основание в Snapshot |
|---|---|---|
| S1 | Запись: GEO не пишет в Snapshot и не импортирует его stores/commit scope. Мутирующие операции §1 (create/update/delete body/union/river) и P5 возвращают typed результат в DAG; DAG передаёт его в `apply_snapshot` (`ApplySnapshotInput.patch_set: PatchSet[S]`). | integration §3, §9; nodes §1 |
| S2 | Для apply GEO поставляет собственный concrete `DomainSection[P]` (header + `patches: tuple[P, ...]`) с owning patch DTO `P`; без подстановки `DomainSection`/`BaseModel` как универсальной секции. Concrete hydrology section в `app` сейчас отсутствует — **OPEN**, отдельный contract freeze. | nodes §1 «Конкретизация apply»; integration §5 |
| S3 | **Решено 2026-11-16:** `PatchSet` собирает оркестратор DAG из результатов доменных операций; нода сборки пока не определена. GEO не генерирует operation_id и не выбирает expected heads; контракт GEO — только своя `DomainSection` и её patches (S2), его можно фиксировать до ноды. | nodes §3; integration §5 |
| S4 | CRUD над immutable историей: update/delete = новый patch в новой публикации, не перезапись строки и не физическое удаление истории. Невозможность выразить операцию через patch предъявляется пользователю. | integration §4 «CRUD данных» |
| S5 | **Решено 2026-11-16:** хранение R1/G1 — по принятому SP-PACK-V1-B ([spatial-distribution-domain.md](spatial-distribution-domain.md) §7): initial bake — immutable Hydrology root `ArtifactRef` в `WorldPackManifest`; runtime — staged immutable refs Snapshot поверх базового pack. Малые typed факты (UID, liquid, level, links) — в patch/section. **Решено 2026-11-16 (формат):** переиспользовать существующий `OPEN_WATER_PACK_SCHEMA_V1` (`HydrologyPackRoot` + шарды `HydrologyPackShard` 64×64 с `bed`/`wet_runs`/`shore_rows`, ключи `hydrology.open_water.root.tlv` / `shard.tlv`) поверх общего проектного `CanonicalCodec` TLV v1; новый формат не вводить. Runtime-правка = новые ref только изменённых шардов + новый root. Сжатие поверх TLV — оптимизация после измерений. | tz_world_snapshot § Staged artifacts, § ArtifactRef; SP-PACK-V1-B |
| S6 | Чтение: Read-методы §1 принимают exact ref (`SnapshotRef` / `WorldPublicationRef`), полученный DAG из `read_snapshot`; без latest/head fallback, без repair; missing → явный found/missing, corrupt → ошибка, не `None`. Read — наблюдение, не pin/hold. Snapshot не выдаёт hydrology payload — его читает GEO по ref (**OPEN**: точный state-reference read). | integration §4, §9; nodes §1 |
| S7 | Public Input/Output: strict, frozen, `extra="forbid"`, `revalidate_instances="always"`, все поля обязательны; без Any/dict/services/scope/lease/SQL/callbacks/registry. Для регистрации — named nongeneric классы, union не передаётся как input_type. **Уточнение 2026-11-16:** S7 — уточнение контракта (не замена существующих POJO вторым DTO); существующие `WaterBody`/`PhysicalWaterUnion` ужесточаются в рамках freeze. Чтение данных мира в runtime работает независимо от набора полей в мире: отсутствие/лишние/неразрешимые поля — `WarningError` + log через доменный log sink по [tz_runtime_world_edit_policy.md](../../docs/tz_runtime_world_edit_policy.md), без падения и без молчаливых подстановок. | nodes §1, §2; integration §3; runtime/worldEdit policy |
| S8 | Ошибки: один owning public fault на сервис/pipeline; node error оборачивает его без перекодирования и без дубля field errors. Structural ошибки POJO — existing engine validation. Бизнес-отказ — в typed результате (как `SnapshotApplyResult` и решение §4.3), не исключение. Любые исключения не превращаются в success/refusal. | nodes §3 |
| S9 | Отмена/повтор: `asyncio.CancelledError` не перехватывается и не превращается в fault; скрытых retry нет; операции детерминированы по входу, чтобы engine replay не давал новых эффектов. | nodes §3 |
| S10 | Нет прямых вызовов GEO → Snapshot/Source/Pack/Cache; каждая стрелка между доменами — DAG. Существующие прямые пути помечаются legacy и удаляются при cutover (как `SNAPSHOT-V1` маркеры). | integration §3, §7, §9 |

Следствие для §1: STUB-сигнатуры body/union/river должны иметь вид «exact ref + typed команда → typed результат с section patch / `ArtifactRef` | owning fault». Точные поля — при freeze каждого сервиса.

### 7.1. Полный CRUD от клетки до объектов L0 (решено 2026-11-16: A + B, L0 только read-проекция)

- **A. По пространству** (`WaterSpatialService`, рабочее имя). Read — existing `SpatialReadRequest` (`request_id`, `window: SpatialWindow`, `revision: PlanRef | WorldPublicationRef`, `mode`); одна клетка = окно из одного box. Create/Update/Delete — typed команда над окном (wet↔dry с привязкой к body, уровень, bed) → section patch (дельта R1 runs + G1) | отказ. Путь runtime — принятый SP-H3: Physics → DAG → Hydrology → patch → Snapshot.
- **B. По объектам** — `WaterBodyService` / `WaterUnionService` / `RiverService` (§1). Для больших объектов read отдаёт метаданные, bbox, coverage; runs — через A по окнам.
- **L0 (решено)** — только read-проекция canonical facts (роль, `z_water_level` на light cell); прямой записи нет. Перевод `LightCellRef` → `SpatialWindow` (решено 2026-11-16) — **Spatial**: чистая геометрия сетки рядом с `LightGridScale`/`SpatialWindow` (`dataModel/spatial/grid`); Hydrology получает готовое окно. DAG не имеет реализаций — только оркестрация и контракты. OPEN: источник z-диапазона окна L0 (topology или параметр).
- **Пересыхание — решено ранее (2026-10-21)**, SoT `docs/tz_terrain_hydrology.md` § «Пересыхание и восстановление водоёма», `docs/tz_entity_lifecycle.md` § «Доменное состояние и существование сущности», [hydrology-water-systems.md](hydrology-water-systems.md) «Пересыхание и восстановление»: пересохший водоём сохраняет UID, lifecycle, котловину и authored-данные; нулевой объём и пустой wet footprint — гидрологическое состояние, не завершение lifecycle и не delete B. Восстановление — прежний UID. Изменение состава системы создаёт систему-преемник. В CRUD это update membership (A) → hydrology state patch; точное поле состояния — freeze W0/W1.
- **Разделение водоёма — lifecycle (решено 2026-11-16, дополнение к принятому):** в текущей ревизии создаются 2 новых UID с историей — преемники ссылаются на предшественника, предшественник переводится в исторический статус и не удаляется (`docs/tz_entity_lifecycle.md` § «Инварианты»). Patch содержит преемников и смену статуса предшественника атомарно; повтор с тем же change идемпотентен.
- **Состояние воды `WaterBody` (сухой/наполненный)** — STUB до W0/W1 ([hydrology-water-systems.md](hydrology-water-systems.md)); контракт GEO ссылается, не замораживает поле.
- **UID водоёма (решено 2026-11-16: править).** Сейчас `WaterBody.water_body_uid: StrictOnWire[str]`, а `WaterMembershipRun.body_uid: EntityUid`; `UidKind.WATER_BODY` отсутствует; позиционные `auto-*` не durable. Требуется единый тип UID водоёма и `UidKind`; точный срез — через implement-plan.
- **История — STUB.** `EntityLifecycle`/`LifecycleReplacement` есть только в `docs/tz_entity_lifecycle.md`, кода нет. История — отдельный домен; связь GEO ↔ история только через DAG (S10). Разделение/delete с историей до него — STUB.
