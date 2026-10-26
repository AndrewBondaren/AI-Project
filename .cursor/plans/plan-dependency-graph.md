# Граф зависимостей актуальных планов

Карта межплановых зависимостей. Внутриплановый порядок — в секции
«Порядок имплементации» каждого плана; здесь — только картина между
планами и критический путь.

## Граф

```text
Открыто / активно (2026-10-17):

  Реструктура worldData — линейный порядок 1→19, активный трек:

    [1–10, 13, 16, 17, 17a] ✅ ──→ [11 container] в работе ──→ [12 refine]
      ──→ [14 worldPack] ──→ [15 render] ──→ [18 tests] ──→ [19 doc sync]

  D jsonValidation — независим, любое окно:

    [1 ТЗ] ✅ ──→ [2 детект] ──→ [3 аудит call sites]

  E worldEdit → wilderness-семейство:

    [E0–E5] ✅ ──→ [E6: поля ✅, consumer/ref открыты] ──→ [wilderness: ТЗ ✅, шаги 0–10c]
                                                              │          ▲
                     ┌──────────────────────┬─────────────────┤          │ шаг 4 ждёт
                     ▼                      ▼                 ▼          │ surface-topology [1–2]
             [deep-layer draft]    [surface-topology ───────────────────┘   [LOD/время
                                    draft, §0 контракт]                      deferred, плана нет]

    Пересечения по файлам: wilderness шаги 4/8/9 трогают
    `dataModel/worldPack/*` (restructure шаг 14 — подпапки wire/meta) и
    `pack/refine/` (restructure шаг 12) — пути в wilderness уже целевые.

  Deferred (вне критического пути):

    5c ──→ docs/tz_library_contextual_fallback.md
    N+1-домены ──→ библиотеки (см. library-packs-model-done.md)
```

## Placement → HY-12 → водные системы; общий lifecycle (2026-10-20)

Ниже актуальные связи выделенных треков. Исторические статусы других планов выше не пересматривались этим изменением.

```text
runtime/worldEdit + WorldTopology (HY-11)
    → placement P0 → P1 (контракт) → P2 (resolver) → P3 (водный adapter)
                       │                             │
                       ▼                             ▼
                 HY-12 шаг 2 ────────────────→ HY-12 шаги 3 → 4 → 5 → 6
                       ▲                                      │
HY-12 шаг 1 ↔ согласование coastline с P1                       │ факты воды
                                                              ▼
lifecycle L0 → L1 → L2 ───────────────────────────────→ W3 + L3 интеграция
               │     │                                       ▲
               ▼     └──────────────→ W2 consumer ────────────┘
              W1 POJO ──────────────→ W2
               ▲
              W0: объём / физический контакт / ранги

HY-12 роли/индексы → HY-10 (L0 bands/wire и полный L0 smoke)
placement + relief/continental field → GEO-1 (отдельного плана пока нет)
HY-12/GEO-1 контракты → актуализация HY-9 (формы берегов)
```

### Владельцы и входные gates

- [generator-placement.md](generator-placement.md): единый resolve всех объектов; первые шаги — inventory и общий typed контракт. HY-12 не создаёт локальный placement. P1 и HY-12 шаг 1 согласуют один контракт до кода; это совместный contract gate, не цикл исполнения.
- Уточнение мастера P1: до relief 1.4 совместно разрешаются подготовленные мировые intent; поздние зависимые размещения вызывают тот же resolver с готовыми опорами без пересмотра ранее принятых решений. Missing/null specificity означает auto по явно утверждённой adapter policy; отсутствие такой политики — unresolved. P1 использует существующий ResolveContext/report и INFO-лог нормализации; validate_only остаётся read-only, дополнительного обхода defaults и второго worldEdit pipeline нет.
- [hy-12-sea-elevation-contract-done.md](hy-12-sea-elevation-contract-done.md): шесть шагов физической гидрологии; relief владеет дном, hydro — уровнями/ролями/водными фактами. Шаг 2 ждёт P1, шаг 3 — P2 и водного adapter P3. Полная миграция остальных placement consumers учитывается отдельно.
- [entity-lifecycle.md](entity-lifecycle.md): общий домен актуальности/замещения/истории. L0–L2 независимы от placement и HY-12; готовность физической воды не требуется для разработки общего контракта.
- [hydrology-water-systems.md](hydrology-water-systems.md): W0 → W1 → W2 → W3; W1 требует L1, W2 использует L2, W3 требует реальные producers HY-12 шагов 4–5. L3/W3 — совместная интеграционная точка после L2/W2, не взаимный prerequisite завершённых шагов.
- [coastline-forms.md](coastline-forms.md): старый procedural-spine/bbox flood требует пересмотра; natural-only HY-12 не размещает океан. HY-9 не реализуется по прежнему алгоритму поверх нового контракта без синхронизации.
- HY-10 и GEO-1 пока не имеют отдельных delivery-планов; ссылки на долг не считаются готовым планом. HY-12 coarse acceptance не закрывает их.

Placement P0–P2 выполнены; P3 W1–W2 adapter declared basin/coastline готов: bounded pre-carve footprint → общий batch → ResolvedWaterPlacement (приёмка 184 tests OK в placement-плане). Открыты остальные adapters P3 и production wiring общего прохода/spec-apply в HY-12/3; объём, физическая связность, место INLAND_SEA/RIVER (W0); технические identity/scope/retry контракты lifecycle (L1). Решение «новые UID, предшественники и сохранение старых систем» закрыто. Зависимость HY-12/3 от отсутствующего водного adapter снята; сам HY-12/3 и остальные треки не объявлены готовыми. Coarse snapshot нельзя передавать как world-fine; общий pass не заменяется water-only вызовом.

## Закрытые треки (история — в `-done` планах)

- **Pack-модель библиотек** — закрыт 2026-10-16 целиком:
  `canonical-defaults-engine-done.md` (A), `library-packs-model-done.md`
  (B, шаги 1–7 + HTTP-smoke), `world-bundle-archive-done.md` (C-1..6),
  `library-write-policy-done.md` (L-1..5),
  `domain-template-libraries-5b-implementation-done.md` (A0–A7, B1–B7).
- **worldData слои** — закрыт 2026-10-16: `worlddata-http-decoupling-done.md`
  (W1), `world-scoped-column-write-done.md` (W2-0..4), G-1
  (`world-grid-settings-g1-analysis-done.md`), PBF-1..3
  (`pack-bake-finalize-scoped-write-done.md`).

Отложенные остатки pack-трека (не блокируют ничего):

- **5c** — базовый POJO default сохраняется; world/pack override отложен
  в `docs/tz_library_contextual_fallback.md`.
- Все каталожные N+1-домены → библиотеки — deferred-расширение
  (см. `library-packs-model-done.md` «Целевое расширение»).

## Активный трек: `worlddata-domain-restructure.md`

Линейно 1→19. **Статус на 2026-10-17:** шаги 1–10, 13, 16, 17, 17a
выполнены; шаг 11 (разрез `core/container.py` на wiring-mixin'ы) — в
работе. Открыты: 12 (`pack/refine/`), 14 (`dataModel/worldPack/`),
15 (`worldData/render/`), 18 (`tests/`), 19 (синк документов/правил).

Условие входа (закрытие pack-трека) снято 2026-10-16 — пересечений с
активными треками по файлам нет; пути шагов 3+ уже финальные.

Housekeeping: скиллы `.agents/skills/source-command-impl-libpack-6`,
`-impl-5b-b7`, `-impl-4d-l5` описывают сданные шаги и ссылаются на
старые пути — удалить/поправить при уборке (зафиксировано в плане
реструктуры).

## Отдельные треки

- **`json-validation-unknown-keys.md`** — независимый линейный план
  (ТЗ → детект → аудит call sites); любое окно. Шаг 1 (раздел контракта
  в `tz_json_validation.md` + ссылка из packs-ТЗ §0) выполнен; шаги 2–3
  (детект в `resolve`, аудит call sites) открыты — в коде
  `split_unknown_keys`/`UNKNOWN_FIELD` пока нет.
- **`runtime-world-edit-policy.md`** (E0→E6, в работе; E0–E5 и миграция
  полей E6 выполнены, consumer/ref boundaries E6 открыты) →
  **`wilderness-regions-mechanic.md`** — ТЗ sync (шаг 1) выполнен
  2026-10-17, ревью закрыло 8 открытых вопросов; шаги 0–10c готовы к
  поштучному согласованию, разрешения на код нет. **Шаг 4 зависит от
  surface-topology шагов 1–2** (`WorldTopology`); шаг 0 — перенос
  `seeded_u01`/`seeded_index` в `app/ids` (не пересекается с restructure).
- **`deep-layer-topology.md`** — draft-исследование, выделено из
  wilderness; разрешения на код нет.
- **`surface-topology.md`** — реализация `world_topology_mode` /
  `WorldTopology`, выделено из wilderness 2026-10-16; контракт зафиксирован
  в wilderness §0; единственный владелец `worldPack/wire/worldTopology.py`;
  пункт raster порядка миграции = wilderness шаг 4. Разрешения на код нет.
- **Единая LOD/время механика** — отложенный трек (2026-10-17): общая
  синхронизация времени/LOD для механик (триггер оценки state-change,
  `elapsed_ticks`, события во времени). Плана нет — выделено из
  wilderness #11; до него `elapsed_ticks` — рабочая заглушка-параметр.
