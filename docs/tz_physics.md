# ТЗ: Physics — физическая эволюция мира

**Статус:** разделение доменных границ и перенос требований из [ТЗ материалов](./tz_materials.md) §§4–6, 2026-11-01. **Физические формулы, версии v1/v2 и численные допуски не утверждены для production**: сохранены исходные требования/наброски, а неопределённости названы явно. Реализация, новые POJO/enum, DAL, solver и DAG-ноды требуют отдельных gates [PHYSICS-1](../.cursor/plans/physics-spatial-dynamics.md).

**Нормативное владение:** этот документ — профильный источник требований к физическим процессам и соответствию **свойство материала → применимость процесса → физическая формула/эффект**. [Materials](./tz_materials.md) остаётся отдельным доменом, источником identity, category, свойств, их defaults/validation и принятых изменений. Здесь нет новой Material Registry и копии material property schema.

## 1. Границы и направление взаимодействий

| Владелец | Истина / результат | Запрет |
|---|---|---|
| **Materials** | Идентичность и свойства материалов, валидность ссылок и свойств, приёмка изменений material definitions/properties по своему публичному контракту | Не вычисляет физические потоки, теплообмен, обвалы и перемещение сред |
| **Physics** | Численные/приближённые физические процессы и результат вычислений: typed proposals изменений, transient physical frame и диагностика | Не копирует реестр Materials, не обновляет его напрямую, не записывает чужие volume/geometry/objects, не создаёт PatchSet |
| **Spatial и domain-owned readers** | Согласованные факты о размещении вещества и геометрии из base Pack + принятого Snapshot overlay | Не запускают физику или material mutation при чтении |
| **Hydrology / Geometry / Gas / Objects и иные owners** | Собственные authoritative сведения о размещении и состоянии; валидация и подготовка принятого domain change | Не подменяют Physics при вычислении течения/нагрузок |
| **DAG-нода** | Запуск, FAR/MEDIUM/NEAR policy, получение typed Input через публичные read, вызов Physics, маршрутизация typed proposals в доменные операции и сборка PatchSet | Не содержит физических формул и не делает скрытых SQL/Grade reads от имени solver |
| **Snapshot/Patches** | Атомарное принятие согласованных изменений, версии и историю мира | Не исполняет физические уравнения |

**Маршрут изменения:** `DAG read → typed Physics Input → Physics compute → typed Physics Output → DAG → public domain change operations (включая Materials при изменении его свойств) → domain-owned prepared changes → PatchSet/Snapshot`. Physics не вызывает изменяющие операции Materials, Hydrology или Geometry напрямую. При нескольких затронутых доменах требуются pinned source revision/world time, проверка совместимости и единое принятие либо явный отказ; форма ответа/версии и атомарность — OPEN PH-PUBLISH/Snapshot.

## 2. Свойства Materials и соответствующие физические процессы

Использовать существующие `MaterialRegistryEntry` / `WorldMaterialRegistry` и их публичный typed contract. Значения полей, ограничения и defaults определяет **Materials**, а **Physics** определяет, какие свойства необходимы процессу, как их интерпретировать в формуле и какой результат выдавать. Если обязательное свойство отсутствует, Physics не подставляет скрытое значение и не угадывает по `system_material`/тегам.

| Материальное свойство / внешний факт | Использование в Physics / формула или правило | Состояние контракта |
|---|---|---|
| `material_category` | Eligibility solid/liquid/gas processes; категория сама по себе не выбирает алгоритм по имени материала | Перечень category — Materials; exact process selection — PH-ARCH |
| `density` | Упорядочивание/слоение жидкостей и газов по плотности; плавучесть и гидростатическое давление `p_model = Σ(ρᵢ × hᵢ)` по исходному эскизу §4.3 | Единицы, учёт g/геометрии, приближения и валидная модель давления — OPEN |
| `viscosity` | Влияет на скорость/сопротивление течению; исходное качественное правило: рост вязкости замедляет поток | Поле 0–1 либо null — Materials; численная зависимость/units/error — OPEN |
| `heat_conductivity` | Коэффициент теплового обмена в эскизе дискретной диффузии §5; не источник температуры сам по себе | Поле 0–1 — Materials; физическая размерность, тепловой баланс и source semantics — OPEN |
| `heat_into` + `heat_temp`, `cool_into` + `cool_temp` | Правила eligibility перехода материала при нагреве/охлаждении; ссылка на целевой material identity из registry | Ref/порог — Materials; момент, источник температуры, владелец локального transition и patch — OPEN |
| `structural_strength` | Вход механики/устойчивости: несущая способность, нагрузка, failure proposals | Применимая формула нагрузки, шкала 0–1, состояние повреждения и writer — OPEN |
| `hardness` | Возможный параметр сопротивления воздействию; исходно используется ExcavationNode, не автоматический закон Physics | Использование Physics требует отдельного process contract |
| `flammable`, `corrodible`, `breakable` | Признаки применимости combustion/corrosion/fracture; не самостоятельная формула и не автоматическая замена материала | Trigger, скорость, продукты, damage state и domain operation — OPEN |
| `temp_damage` | Признак возможного контактного температурного урона; не доказательство фиксированного источника тепла | Источник фактической температуры/тепла и связь damage-owner — OPEN |
| `vision_block` и `transparent` | Данные для зрения/scene consumers; физика газа может менять размещение, но не рассчитывает FOV как побочный эффект | Владелец расчёта видимости — профильный consumer; не Physics solver |
| `mineable`, `use_type`, `economic_tier`, `components`, `tags` | Потребители добычи, генерации/экономики/крафта; не служат скрытым выбором физической формулы | Не часть Physics process selection по умолчанию |
| World Environment ambient/vacuum policy | Граничное условие газового расчёта: отсутствие размещённого блока не доказывает наличие воздуха | Owner — World Environment; нельзя молча подставлять `air` |

**Не считать этот список freeze численных физических параметров.** Нынешний `density` — int, `viscosity` и `heat_conductivity` имеют нормированные диапазоны, но это ещё не согласованная система физических единиц. Добавление материала с уже поддерживаемыми свойствами не требует новой ветки `if material == ...` в Physics. Новый physical capability/process оформляется через версионируемый контракт Materials и соответствующий новый/расширенный Physics kernel.

## 3. Физика по категориям (перенесено из Materials §4)

Исходная матрица требований описывает **допустимые процессы**, а не обязательный per-cell tick всего мира:

- **Solid:** падение/обвал при неподдержанной нагрузке, плавучесть относительно жидкости, горение при подтверждённом trigger, коррозия, разрушение, thermal transitions; добыча и FOV принадлежат их профильным consumers. Нет автоматического обвала только по `material_category=solid`.
- **Liquid:** гравитационное течение, перераспределение, слоение по плотности, взаимодействия с объектами/персонажами, thermal transitions. Видимость и контактный урон — отдельные эффекты/consumers, не запись в Spatial при чтении.
- **Gas:** направленное распространение/расслоение по плотности относительно принятой ambient policy, контактные воздействия и изменение локальных gas facts через их владельца; FOV — отдельный consumer.

Process selection опирается на typed свойства и подтверждённое воздействие, не на string-identity `water`/`lava`/`air`. Материал без нужной характеристики возвращает typed unsupported/unresolved outcome согласно будущему контракту, не получает численный default из solver.

## 4. Жидкости: исходные физические требования

### 4.1. Гравитационное течение и слоение (v1, legacy requirement)

Исходное правило: жидкость стремится вниз по Z при доступном пространстве; более плотная жидкость опускается под менее плотную. Больше `viscosity` — медленнее течение; конкретная формула «тики на шаг» в старом ТЗ **не была задана**. В Physics это **не** требование выполнять глобальный per-XYZ шаг: PH-AGG оперирует компактными согласованными объёмами/границами, PH-LOCAL — подготовленным bounded окном.

### 4.2. Solid ↔ liquid и смена material identity

При достижении утверждённого температурного порога используются ссылки `heat_into`/`cool_into` на **существующий** material identity. Исходные цепочки из Materials:

| Материал | `heat_into` | `cool_into` |
|---|---|---|
| `iron_ore` | `molten_iron` | null |
| `molten_iron` | null | `iron` |
| `iron` | `molten_iron` | null |
| `wood` | `charcoal` | null |
| `charcoal` | `ash` | null |
| `ash` | null | null |
| `water` | `steam` | `ice` |
| `steam` | `superheated_steam` | `water` |
| `lava` | null | `stone` |

Это **пример перехода размещённого вещества**, а не автоматическое изменение canonical записи `water`/`iron` во всём `WorldMaterialRegistry`. Physics рассчитывает условие/результат; DAG вызывает Materials и/или owner размещённого состояния для проверки целевого ref, допустимого transition и подготовки patch. Точная граница между Materials change и placed-medium change — OPEN §7.

### 4.3. Гидростатическое давление (v2, исходный эскиз)

В Materials была дана формула:

```text
pressure(cell) = sum(density * height for fluid_cells above)
```

При положительном достаточном давлении возможны подъём жидкости/затопление снизу/трубы. **Формула — историческое упрощение, не production equations freeze:** нужно определить единицы, g, hydrostatic head, границы соседства, geometry, approximation и conservation. PH-AGG не обязан читать все «клетки сверху»; PH-LOCAL может использовать ограниченное materialized окно. Hydrology остаётся владельцем принятого wet footprint/level/coverage.

## 5. Теплообмен и переходы (исходные Materials §4.1–4.2)

Оригинальный эскиз дискретной диффузии для локального шага:

```text
delta = Σ (neighbor.temperature - C.temperature) × neighbor.material.heat_conductivity × dt
C.temperature += delta
```

Исходное ТЗ называло `dt` настраиваемым параметром мира, но точное поле, источник данных `C.temperature` и accepted time-step contract **не утверждены**. Нельзя переносить эту формулу как цикл по всем материализованным клеткам для FAR/MEDIUM.

В исходном ТЗ `temp_damage: true` приравнивался к фиксированному источнику тепла, а `heat_conductivity: 0.0` — к «только отдаёт, не получает». **Это сохранённые legacy assumptions для ревью**, не следствие определения свойства: `temp_damage` сам по себе означает контактный урон, не обязательно генерацию тепла. Нужны отдельные source/energy/conservation semantics перед реализацией.

При подтверждённом тепловом переходе Physics возвращает typed proposal; owning domain проверяет Material refs, локальную область, ревизию, изменение состава/категории и право записи. Нельзя в Physics вызывать `WorldMaterialRegistry.entry_for()` ради скрытого изменения реестра или заменять клетки напрямую.

## 6. Газы (исходные Materials §6)

Исходные требования: плотный газ склонен оседать относительно окружения, менее плотный — подниматься; `vision_block: true` влияет на видимость, `temp_damage: true` — на контактный урон. Динамику газа рассчитывает Physics, размещение и принятый состав газовых объёмов подтверждает Gas Distribution/владелец ambient фактов, эффекты на видимость/здоровье обрабатывают свои consumers.

Отсутствие сохранённой клетки не означает обязательный `air`. Состав фоновой атмосферы/вакуума выбирает World Environment; изменение атмосферной policy не является Solver fallback.

## 7. Изменение свойств материалов под действием физики

**Свойства материалов не считаются навсегда неизменными.** Physics может вычислять воздействие, после которого меняется характеристика, категория, material identity или состояние конкретного объёма/объекта. Но **место хранения и owner принятия зависят от scope изменения**:

1. **Изменение определения материала в мире** (например, явно утверждённое изменение базовой физической характеристики типа материала): owner — **Materials**, с версионированной записью/валидацией, явным scope и downstream invalidation. Такое изменение может затронуть **все** объекты/объёмы, ссылающиеся на запись, поэтому локальный нагрев не должен молча править реестр.
2. **Локальное изменение размещённого вещества/объекта** (температура, повреждение, влажность, деформация, переход identity, состав): Physics вычисляет effect proposal; Materials подтверждает допустимость свойств/transition по своему контракту, а authoritative размещение/состояние изменяет соответствующий владелец (Hydrology/Geometry/Objects/Gas или другой принятой модели). В каком домене/POJO хранится mutable instance-state — **OPEN**, нельзя догадкой назначить его глобальному registry.
3. **Эффективное временное физическое свойство** может вычисляться из Material definition + локального состояния для конкретного шага, не изменяя глобальный тип. Если оно влияет на продолжение симуляции/reload, необходим отдельный согласованный revision/time/dynamic-state contract; кэш solver не становится SoT.

**Междоменный contract:** Physics `Output` различает *proposed property effect*, *proposed identity/state transition*, *transient effect* и источник/допуск расчёта концептуально; это **не объявление новых POJO/enum**. DAG направляет proposals публичным владельцам. Владельцы проверяют актуальность Material version, source world revision, размер области, тип эффекта, права и допустимые диапазоны; отклоняют stale/unsupported и возвращают typed prepared changes/errors. Связанные эффекты должны быть приняты согласованно через Snapshot/Patches; partial commit без согласованного контракта запрещён.

Примеры разграничения:
- Нагрев железной двери не меняет автоматически физические свойства **всех** записей `iron` в мире; локальная температура, повреждение или переход к `molten_iron` — состояние конкретного объекта/размещения.
- Глобальное изменение базовой плотности некоторого материала — операция Materials с явным world scope, а не побочный эффект локальной физики.
- Разрушение опоры: Physics рассчитывает failure, Geometry/Objects готовят изменённую геометрию и состояние, Materials подтверждает нужные material refs/properties; Snapshot принимает итог.

## 8. LOD, Grade и стоимость вычислений

Внешняя Physics DAG-нода через DAG + typed settings выбирает FAR/MEDIUM/NEAR, читает согласованные domain facts и передаёт Physics выбранный compute mode. **PH-AGG и PH-LOCAL — две стратегии, три зоны — policy, не три solver.**

- **FAR/MEDIUM:** не обращаться к Grade/SQL ни напрямую, ни через materialization/fallback. PH-AGG работает на compact facts и bounded elapsed-time/event steps.
- **NEAR:** bounded Grade window и локальная материализация допустимы через публичный reader/L2, а не скрытый SQL внутри Physics.
- Событийный PH-LOCAL вне NEAR возможен **только без Grade**; точные bounds/budgets/criteria и handoff — OPEN PH-ORCH/PH-LOD.

В любом LOD read сам по себе не запускает физику, результат Physics не мутирует существующий SpatialSlice, краткоживущий численный substep не обязан порождать Snapshot.

### 8.1. Причинный порядок междоменных операций — владелец DAG

**Принцип принят:** DAG выбирает **логичный причинный порядок операций по объявленным typed зависимостям и результатам**, а не по жёсткому глобальному списку «сначала тепло, затем жидкости, затем газ». Одна физическая причина может порождать несколько эффектов с разными владельцами, а поздний эффект может изменить условия последующих физических расчётов. Физика возвращает typed causal effects/proposals с необходимой provenance/scope/revision семантикой (точный POJO/enum OPEN); DAG владеет маршрутом и зависимостями, **Physics — внутренней численной связью процессов и substeps**. Запрещено превращать каждый solver microstep в отдельную DAG-ноду.

**Рекомендованная архитектурная модель для дальнейшей приёмки, не freeze API:**
1. DAG вызывает Physics с согласованными исходными фактами на pinned publication/time. Physics рассчитывает одну bounded причинную стадию (включая локально связанные процессы внутри вычисления).
2. DAG использует **существующие объявленные нодами `deps`** для ацикличного порядка операций и отдельные typed output/read requirements для передачи результата: это разные виды зависимости, как принято в [Node Context TZ §2](./tz_engine_node_context.md). Применимость условных веток и повторной Physics invocation ещё требует конкретного PH-ORCH/GEN-DAG контракта; **новый второй граф scheduling не создавать**. Нода не должна угадывать зависимости по имени материала или сериализовать всё по умолчанию.
3. **Связанные эффекты одной стадии**, которым нужна совместная публикация, подготавливаются их domain owners и принимаются Snapshot атомарно (или вся стадия отклоняется). Последующее вычисление не читает наполовину принятый результат. Употребление подготовленных outputs до commit возможно только если его exact typed staged-read contract когда-нибудь будет явно принят; сейчас это **не утверждено**.
4. Если новое принятое состояние запускает встречное воздействие, это **следующая причинная стадия / bounded world-time step** с новой согласованной ревизией, а не цикл внутри одного DAG graph. Ограничения количества стадий, бюджета, cancellation, stopping condition, retries и deterministic replay — OPEN.
5. Независимые непересекающиеся области/эффекты могут выполняться параллельно после проверки dependencies; overlapping writes, конкурирующие material/geometry/water changes, stale/CAS и double-apply требуют координации одним DAG/commit owner. Параллелизм не является автоматическим разрешением конфликтующих PatchSet.

**Доказательные сценарии:**
- **Землетрясение → цунами:** Physics/процесс устойчивости предлагает деформацию/обрушение, Geometry/Terrain принимает новое состояние; после согласованной публикации Physics читает обновлённую геометрию и Hydrology facts, рассчитывает вытеснение/волну; Hydrology принимает постоянные изменения воды, transient волны не обязаны становиться water-level Patch.
- **Пожар → изменение материала + газы:** thermal/combustion physics предлагает local material transition/damage и gas emission; Materials подтверждает свойства/refs, placed-state owner и Gas owner готовят связанные effects. Их требуемая общая публикация атомарна; газовое распространение, зависящее от нового состава, идёт следующей стадией.
- **Наводнение → эрозия → рельеф → вода:** Physical flow вызывает erosion/failure proposal, Terrain/Geometry принимает изменения solid/void, Hydro reader/Physics рассчитывают последствия по новой геометрии. Обратное влияние разворачивается по стадиям/времени, с ограничением повторов и сохранением массы/истории, без циклических DAG-зависимостей.

**OPEN PH-ORCH + GEN-DAG/PH-PUBLISH:** точные declared dependencies/typed causal outputs, mapping физического события в существующие DAG deps/ноды, выбор составных или раздельных нод, порядок domain preparation внутри atomic effect group, Snapshot commit barrier (не смешивать с простым Output-barrier), scheduling/priority, обратные связи и bounded iteration. WORLD-PLAN-GRAPH-1 фиксирует **зависимости разработки**, а не этот runtime causal DAG; добавлять туда «землетрясение → цунами» как hard development edge нельзя.

## 9. Открытые контракты и критерии приёмки

1. **Materials mutable-property contract:** какие свойства изменяются глобально, какие — только для размещённого экземпляра, кто owns instance-state, как версионируются изменения, как Materials валидирует typed effect/transition и как выполнен atomic Snapshot handoff.
2. **Физическая размерность/формулы:** единицы density/temperature/pressure, смысл нормированных viscosity/heat_conductivity/strength, source/sink accounting, гравитация, energy balance, errors и границы допустимых приближений.
3. **Heat and reaction:** температура/нагрев как динамическое поле, принадлежность source, `temp_damage` vs heat source, flammable + `heat_into`, reaction products; legacy simplifications не считать принятыми законами.
4. **Process/LOD implementations:** PH-AGG PH-LOCAL kernels, budget/time, Grade boundary, materialization, parallelism/handoff, deterministic replay.
5. **Domain destination contracts:** явные typed Operations Materials/Hydrology/Geometry/Gas/Objects, effective/instance property resolution, validation/CAS/retry/invalidation/typed errors; никаких invented generic write ports.
6. **Материальные примеры/схемы:** примеры Materials перечисляют `breakable` и transition refs не полностью; `water` в одном примере имеет `viscosity=null` при ожидании liquid viscosity — уточнить **в Materials**, не чинить hidden default в solver.
7. **Фоновая среда:** World Environment ambient/vacuum и отсутствие автоматической подстановки `air`; SP-A приёмка отдельно.
8. **Процессы вне water-first:** gas, thermal, structural/mechanics ждут собственных contracts/gates и не блокируют base Hydrology/SPATIAL/GEN.
9. **Причинная DAG-оркестрация:** declared cross-domain dependencies, fan-out одновременных effects, atomic prepare/commit barriers, повторная Physics invocation после принятого изменения, bounded feedback/time, overlap/parallelism/cancellation и error propagation (§8.1).

**Definition of Done для этого ТЗ:** физические правила имеют одного владельца Physics; свойства — одного владельца Materials; изменения свойств/состояния не обходят domain owners; формулы связаны с конкретными материальными полями и отмеченными OPEN units/assumptions; нет скрытого per-cell global tick и Grade в FAR/MEDIUM. Этот документ — design requirements, **не** разрешение на production.

## 10. Источники и связанные документы

- [Материалы](./tz_materials.md) — реестр, свойства, defaults/validation и их изменения.
- [PHYSICS-1](../.cursor/plans/physics-spatial-dynamics.md) — план архитектуры, file/class map, PH-0/ORCH/LOD/PUBLISH gates.
- [SPATIAL-1](../.cursor/plans/spatial-distribution-domain.md) — domain-owned spatial read, L2, Grade/overlay.
- [World Snapshot](./tz_world_snapshot.md) — принятие изменений/immutability base Pack.
- [World Environment / Aerial](./tz_aerial.md) — ambient/vacuum contracts.
- [Typed DAG Node Context](./tz_engine_node_context.md) — declared `deps`, typed Input/Output, barrier и параллелизм engine DAG.
- [World plan graph](../.cursor/plans/world-generation-plan-dependency-graph.md) — межплановые gates (не runtime causal DAG и не owner формул).
