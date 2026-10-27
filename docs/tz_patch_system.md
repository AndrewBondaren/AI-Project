---
name: tz-patch-system
description: "Единая patch-система движка — доменный интерфейс изменений, patch set на ход, commit в snapshot, world/player цепочки"
metadata:
  node_type: memory
  type: project
---

## Назначение

**Patch System** — общая инфраструктура движка для **всех изменений состояния**: мир (cells, regions, structures, …), игрок, сессия. Отдельный механизм — **не часть генератора и не часть конкретного домена**.

Мотивация: только домен знает семантику своих изменений, поэтому патч готовит реализация домена, а применяет подготовленные patches только Snapshot.

| Принцип | Смысл |
|---|---|
| **Patch = интерфейс** | Домен получает параметры изменения в своих терминах → **реализация домена** формирует `Patch` |
| **Один механизм на все состояния** | cells, region_states, player stats/inventory/history — один контракт, разные доменные реализации |
| **Patch set на ход** | За ход накапливается набор патчей, **секционированный по доменам** (не плоский blob) → передаётся Snapshot → только Snapshot применяет набор и фиксирует состояние/операции |
| **Rollback = branch, не discard** | Откаченные snapshot'ы не удаляются — ссылаются на ветку в другом временном отрезке (`parent_snapshot_id`, `ON DELETE RESTRICT`) |

**Append-only SQL/pack (мастер, 2026-10-27):** модификации состояния добавляют
новые SQL-записи/версии и новые immutable pack-артефакты. Исторические данные
не перезаписываются; доменный delete отражается новым изменением/маркером.
Patch хранит историчность перехода для SQL и pack: исходное состояние,
модификацию и результирующую версию/данные либо удерживаемые ссылки.
Только Snapshot оборачивает и применяет набор, фиксируя согласованное состояние.
Формат истории и append-only publication/head contract ещё согласуются;
прежняя SQL write реализация этим не объявляется совместимой.

**Владение двумя фазами (мастер, 2026-10-27):** домен реализует как
write-free CRUD preparation, так и запись своих SQL/pack данных. Подготовку
инициирует DAG/debug API; применение и запись инициирует только Snapshot.
Домен не запускает обе фазы самостоятельно и не переключает их автоматически.
Patch принимает prepared domain result без повторного изменяющего CRUD;
Snapshot вызывает domain storage contract, не реализуя его mapping/SQL/pack
логику. Запись не означает самостоятельный commit всего PatchSet.

**Статус:** target design ⬜

---

## Что это **не** является

| Сущность | Что это | Связь |
|---|---|---|
| `map_cell_patches` (SQL) | Таблица применённых дельт cells-домена | Один **доменный patch-формат**, не система; может стать persist-целью patches |
| `pending_patches` / `PatchApplier` (engine) | Ephemeral копии node_results LLM-фазы | Не patch-система; кандидат на удаление/замещение |
| `SessionSnapshot` | Resume пайплайна чата | Не modification snapshot |
| `WorldSnapshot` blob | Полный слепок состояния на ход | Commit-артефакт — **приёмник** patch set, не патч |

---

## Мутация и данные её планирования

Мутация — изменение состояния мира; patch — типизированное доменное
описание изменения. Данные планирования мутации и её materialization
различаются: первые служат входом для последующего воплощения изменения
в конкретных данных мира. Snapshot обязан сохранять данные планирования
мутаций; если materialization уже выполнена по запросу, сохраняются план
и соответствующий результат. Создание snapshot само по себе materialization
не запускает. Решение мастера 2026-10-26 и пояснение —
[`tz_world_snapshot.md`](./tz_world_snapshot.md), раздел «Мутация, её
планирование и materialization». Эта запись не приравнивает журнал патчей
к полному набору данных планирования мутации и не меняет владение доменными
форматами.

## Владельцы сбора патчей — только DAG и debug API (уточнение мастера, 2026-10-27)

Контракт Patch/PatchSet сохраняется. **Сбор патчей и формирование patch set
разрешены только DAG и debug API.** Доменная patch implementation формирует
отдельный typed patch из доменного результата без изменения состояния.
Только Snapshot применяет собранный набор, вызывая доменные реализации
поведения, и сохраняет результирующее состояние/историю. Самостоятельного
общего patcher как второго входа применения нет. Snapshot набор не собирает.

PatchSet может временно кэшировать подготовленные результаты для передачи
в Snapshot. Кэш не является применением patch или зафиксированным состоянием;
владение, lifetime, соответствие patch/revisions и освобождение ресурсов
определяются общим контрактом до реализации.

Генератор возвращает доменный output. Он не формирует и не собирает patches,
не вызывает patcher/snapshot CRUD и не пишет через патчи напрямую в
snapshots. Запись инициируется через debug API либо DAG на application
границе. Debug API имеет право самостоятельно собирать patch set своего
сценария; делегирование сбора DAG не является обязательным. Ни один из этих
входов не переносит сбор patch set в генератор или доменный handler. Наличие общего
контракта не даёт генератору write capability к истории snapshots.

**Любой домен, обходящий DAG или debug API как application-вход записи
в рамках WS, создаёт критическую архитектурную ошибку. Исключений для
internal/debug/import/batch callers нет.** Это проверяется на каждом
шаге WS по writer/caller ledger и фактическим calls/imports: разрешённый
entry → подготовка/сбор PatchSet → Snapshot apply → domain implementation → storage. Вызовы storage внутри
этого сценария допустимы; самостоятельный альтернативный вход — нет.
Затронутый шаг не принимается при наличии обхода; весь WS не завершается,
пока остаётся хотя бы один обход в его scope. Проверка не откладывается
до итогового ревью или интеграции.

## Архитектура

```mermaid
flowchart LR
  GEN[Generator: domain output] --> ENTRY[DAG / debug API]
  ENTRY --> DOMAIN[Domain: подготовка Patch без записи]
  DOMAIN --> ENTRY
  ENTRY --> SET[PatchSet: patches и временный кэш результатов]
  SET --> SNAP[Snapshot: единственный владелец применения]
  SNAP --> BEHAVIOUR[Domain implementation: поведение Patch]
  BEHAVIOUR --> SNAP
  SNAP --> STORE[Результирующее состояние и история]
```

**Инварианты:**

- **Snapshot immutable**: записанный snapshot никогда не мутируется. Любое изменение состояния — новый узел; «откат»/re-simulation — новая ветка, не правка существующей. Нарушение = баг хранилища (checksum это ловит).
- Patch — immutable, typed (Pydantic); не SQL-строка и не `MapCell`.
- Patch set секционирован по доменам (`sections`); Snapshot вызывает domain implementations при применении секций; доменный payload не интерпретируется общим кодом.
- Порядок патчей внутри секции — ответственность домена; порядок секций — явная доменная зависимость; инфраструктура не переупорядочивает.
- Compose/merge полей (кто перекрывает чьё поле) — собственность домена-владельца поля, не generic-кода.
- Патчи — не источник состояния при restore: blob snapshot **authoritative**; patch set внутри snapshot — audit/diff/regen-вход (закрывает deferred «incremental vs full» из `tz_world_snapshot`).

## Контракт (черновик)

Уточнение мастера 2026-10-27: **интерфейс Patch — общий поведенческий
контракт, передаваемый доменам на реализацию.** Схема полей ниже сама по себе
не определяет этот интерфейс. До реализации необходимо согласовать смысл
адресата/изменения, предусловия, validation, этапы применения/сохранения,
результаты, отказы, повторное применение, зависимости/effects и передачу
данных в snapshot. Общая семантика принадлежит интерфейсу, доменная логика
её выполнения — домену. Критерии отдельной приёмки —
[новый план, §3 и §8](../.cursor/plans/world-domain-patches-snapshots.md).

**Критическая приёмка каждого класса Patch (мастер, 2026-10-27):** при
изменении доменного CRUD с сохранением публичного контракта модификации
класс Patch, его типы/payload/format version не меняются. CRUD и сопоставление
модификации с физическими записями принадлежат домену. Проверка обязательна
для каждого конкретного класса, не только базового интерфейса или одного
patch на домен. Сценарий и evidence — новый план §3.4. Интерфейс требует
строгой связки domain/семантика/target/inputs/change/result от реализации.
Провал этой проверки означает дефект реализации. До его устранения и
повторной успешной проверки не принимаются затронутый шаг и план целиком;
отложенный долг или ослабление критерия не заменяют исправление.

Прямая запись мутации из Patch в обход Snapshot — критический дефект,
включая косвенный вызов existing CRUD writer/repository. Подготовка patch,
validation и кэш PatchSet не меняют authoritative state. Запись доменной
инфраструктурой допустима только внутри применения под владением Snapshot,
без независимого commit. Сохранить CRUD-изменение и затем добавить историю
snapshot недостаточно; версионирование не заменяет этот gate.

Схема ниже — исторический эскиз состава данных, не типизированный контракт
к реализации: bare domain string/raw payload не удовлетворяют этому требованию.

```python
class Patch(BaseModel):  # frozen
    domain: str        # владелец изменения
    target: ...        # адресат в терминах домена: cell (x,y,z) / region_uid / player path / …
    payload: ...       # доменная дельта — формат определяет владелец
    # meta: provenance (чем вызвано), revision tokens

class PatchSet(BaseModel):  # дельта одного хода
    turn_id: int
    # секционировано по доменам — НЕ плоский список:
    sections: dict[str, list[Patch]]   # climate | economy | npc | flora | war | politics | resources | …
```

**Зачем секции:** плоский набор патчей из всех систем (климат, экономика, NPC, флора, война, политика, ресурсы) — неконтролируемый blob. Секция = владение:

- **apply** — только Snapshot вызывает patch impl соответствующего домена; самостоятельного domain apply entry нет;
- **валидация** — домен проверяет только свою секцию;
- **diff/diff на restore** — «что изменилось в climate между N и N−1» читается без разбора всего набора;
- **аудит/диагностика** — патч всегда адресуем доменом, orphaned payload невозможен.

**Кросс-доменный порядок внутри patch set** — явная зависимость (domain-level `depends_on` / фиксированный порядок секций), не порядок записи. Независимые секции применяются независимо.

## Границы слоёв

| Слой | Делает | Не делает |
|---|---|---|
| generator | доменный output | patch, snapshot, SQL |
| domain patch impl | подготовка Patch без записи; поведение своего patch по вызову Snapshot | самостоятельное применение, чужие доменные правила |
| DAG | сбор патчей и формирование patch set хода | доменная семантика payload, физическое хранение snapshot |
| debug API | внешний application-вход сценария записи, сбор патчей и формирование patch set | генераторная логика, доменная семантика payload |
| snapshot service | единственный apply PatchSet через domain implementations; состояние/история, serialize / commit / restore / branch | сбор набора, генерация, доменные алгоритмы, LLM payload |

См. правило `layer-boundaries.mdc` — persist и LLM не в генераторе; patch-система расширяет это до всех изменений состояния.

### Доменное чтение, patches и WS (решение мастера, 2026-10-27)

DAG напрямую вызывает read и patch соответствующего домена. Контракт
чтения принадлежит домену; WS не задаёт общий read-контракт, не оборачивает
и не маршрутизирует domain.read. Прямой доступ WS к БД запрещён.
Прежние central CRUD, WS DB adapters и WorldStateUnitOfWork отменены.

Доменная patch implementation готовит изменение metadata/planning либо
результат materialization без записи состояния. Она реализует доменные
правила поведения patch, вызываемые только Snapshot при применении.
Generator возвращает domain output и сам patches не формирует/не применяет.

Только DAG/debug API собирают PatchSet. Он может временно кэшировать
результат для передачи в Snapshot. Только Snapshot применяет patches и
сохраняет состояние/операции всех доменов; набор он не собирает, доменные
алгоритмы не воспроизводит и materialization не запускает.

Атомарность domain mutation, набора/хода и snapshot commit должна быть
определена архитектурой до реализации. Самостоятельные частичные commits
не доказывают атомарность сценария; SQL transaction не равна file publication.
Конкретные coordinator/UOW классы сейчас не выбираются.

Selective cell delta сохраняет Keep/SetValue/ResetOverride и незатронутые
поля, reset не удаляет base pack cell. Эти правила принадлежат cell-домену,
не общему WS storage adapter. Runtime fluid model этим не вводится.

[Актуальный новый план](../.cursor/plans/world-domain-patches-snapshots.md).
Прежний world-state-crud-transition.md помечен ARCHIVED / SUPERSEDED.
Прежние WS-0A/ledger — архив, не действующий контракт общего CRUD.

---

## Две цепочки snapshot — world и player

`world_snapshots` и `player_snapshots` — **параллельные цепочки**, синхронизированные по ходу (`turn_id`), но раздельные сущности.

**Причина разделения:** игрок отделён от мира ради **export/import** и **time travel** — переносится между мирами и ветками; его состояние не живёт внутри world blob.

**Односторонняя зависимость:** player state может ссылаться на world-факты; world никогда не ссылается на player state. World snapshot остаётся самодостаточным.

### Player state = memory + intrinsic

| Часть | Семантика |
|---|---|
| **memory** | История/события, в т.ч. других веток; timeline-агностична; переживает откат мира; опционально `origin_timeline` («трактирщик из другого мира») |
| **intrinsic** | Статы, скиллы, инвентарь — свойства персонажа, не привязки к миру |

**Placement (pos/location) не входит в player state** — это свойство привязки `player↔world`, владелец — **session** (world blob, секция «active session»). Export игрока = персонаж без места; attach создаёт привязку в целевом мире (spawn-анкор или reconcile координат — открыт).

Мир не знает player-историю из других веток; игрок её помнит. Ослабленная форма односторонней зависимости: **world знает session-bindings, но не знает player state**.

### Attach к раннему snapshot мира

`attach(player, world_snapshot)` — операция session-домена:

- memory + intrinsic переносятся как есть (против мира не валидируются — они не его собственность);
- создаётся session-binding: привязка игрока к целевому миру (позиция);
- результат оформляется **session-патчем** — та же машина изменений.

### Scope migration: player ↔ npc

Персонаж может пересекать границу цепочек: player переключился на другого персонажа → бывший становится NPC; обратный кейс — взять NPC под управление.

- **Identity сохраняется:** `character_uid` персонажа не меняется при миграции — ссылки (отношения, история, упоминания) остаются валидными.
- `demote_player_to_npc` = пара патчей в одном patch set хода:
  - `player` секция: завершение session-binding, player-цепочка персонажа запечатывается (terminal node — история сохраняется);
  - `npc` секция (world): adopt — player intrinsic → NPC state: stats → `character_sheet`, inventory → possessions, memory → биография/backstory (домен npc решает, что поглощать; полная memory остаётся в архиве player-цепочки).
- `promote_npc_to_player` — зеркально: NPC state → player intrinsic + новый session-binding.
- Мир и player-секции затронуты одним patch set — согласованность через существующую commit-семантику пары цепочек.

---

## Решённые вопросы

| Вопрос | Решение |
|---|---|
| Items/инвентарь | Часть player state — идут с игроком между ветками/мирами; provenance «из другой ветки» хранится как memory-метка (`origin_timeline`) |
| Reconcile на attach | Формирует **session-домен** (владелец placement): привязка создаётся/правится в целевом мире; player state reconcile не требует — его live-части нет |
| Patch set хранение | **Отдельная лёгкая таблица** (patch log, секционированная по доменам, keyed by snapshot/turn) + blob несёт ссылку — SQL-запросы по дельтам без распаковки blob (regen-diff, audit) |

## Открытые вопросы

| Вопрос | Статус |
|---|---|
| Владелец позиции игрока | **решено**: позиция — свойство привязки `player↔world`, владелец — **session** (world blob, секция «active session»). Player state = memory + intrinsic (stats, inventory); placement в него не входит |
| Точка входа при attach: spawn-анкор целевой ветки vs reconcile координат | открыт (зависит от владельца позиции) |
| Атомарность commit пары цепочек при сбое одной стороны | открыт |
| Версионирование формата патчей (читаемость старых snapshot) | открыт — мягкая деградация, пока blob authoritative |

### Timelines: нет cross-timeline sync

Решение по «синхронизации событий между таймлайнами» (было открыто в storage TZ):

- **Между ветками перемещается только игрок** — через свою `player_snapshots` цепочку (memory + intrinsic идут с ним).
- **Ветки не синхронизируются и не симулируются в фоне**: продвигается только тот таймлайн, где находится игрок. Заброшенная ветка заморожена на точке ухода.
- Время таймлайн-локальное (свой `turn_id`); общих часов между ветками нет.
- `attach` в ранний snapshot другой ветки — та же операция session-домена, цель просто в другой ветке.
- Следствие: изменения, которые игрок внёс в старой ветке, никуда не распространяются — они остаются историей ветки и memory игрока.

**Почему нет cross-timeline sync:**

- **Нет ретроактивного пересчёта.** Изменение события в прошлом = новая ветка от точки ответвления, а не переигровка N ходов зависимой истории. Пересчёт (а) дорог по ресурсам, (б) недостижим по точности — ходы содержат LLM/RNG-ветвления, replay не воспроизводит ту же историю.
- **Нет фоновой симуляции веток.** Замороженная ветка не тратит ресурсы — симулировать то, что игрок не видит, незачем. Тот же принцип, что lazy generation: мир существует только там, где игрок.
- Ветка при возврате продолжается со своей замороженной точки (её `turn_id` не тикал); «мир жил без игрока» — отдельный продуктовый кейс (lazy unfold на re-entry), не часть этой модели.

**Короткая дистанция — ветка пересчёта (re-simulation).** Time travel на небольшой промежуток (порядка игрового дня) может **переписать историю**, но исходная ветка при этом **не мутирует**: `restore(W_{N-k})` → k ходов переигрываются заново с изменённым контекстом (повторные LLM-вызовы, новые результаты) → результат оформляется **новой веткой** (recompute branch), исходная остаётся целиком.

**Safe по построению:** пересчёт пишет только в новую ветку — при сбое/неприемлемом результате она отбрасывается, исходная история не затронута. Player попадает в recompute-ветку только по явному выбору после завершения пересчёта.

**Граница — техническая, не концептуальная:** честный пересчёт N ходов стоит ~N повторных LLM-запросов (контекст каждого зависит от изменённого мира). Прыжок на день — приемлемо; на 1000 ходов — нет. Поэтому дальняя дистанция всегда = чистый branch без переигровки.

**Patch replay** (переигровка записанных patch sets поверх blob) — отдельно: воспроизводит старое будущее точно и дёшево (патчи — данные, не генерация), но это inspect/regen-diff, не переписывание.

---

## Связанные документы

- [`tz_world_snapshot.md`](./tz_world_snapshot.md) — snapshot service, blob, timelines
- [`project_data_storage_tz.md`](./project_data_storage_tz.md) — schema `world_snapshots` / `player_snapshots`
- [`tz_world_pack_storage.md`](./tz_world_pack_storage.md) — Patch Store (`map_cell_patches`) как доменный patch-формат cells; pack = immutable base
- [`tz_runtime_world_edit_policy.md`](./tz_runtime_world_edit_policy.md) — единый resolver/политика для доменных изменений


## PC-0 — planning cache и публикация изменений (2026-10-23)

**G0-S, 2026-10-27:** нижеследующий publication guard — current PC baseline,
не готовый target append-only/Snapshot-owned commit. Для GEO-1 заморожен
[input/revision seam](./tz_terrain_generation.md#geo-1-g0-s--source-revision-и-snapshot-seam):
caller передаёт coherent typed closure; cache/strategy не читает Patch Store,
не назначает source revisions и не применяет patches. Planning digest описывает
effective inputs, отдельно от SourceRevision и pinned snapshot revision set.
Future adapter меняет origin/provenance, сохраняя domain I/codec/ref contracts.
Применение инициирует только Snapshot по действующему
[внешнему плану](../.cursor/plans/world-domain-patches-snapshots.md), §6–7.2;
старый центральный WS CRUD/самостоятельный общий patcher не возвращаются.
Concrete capture/apply/staging/commit contracts того трека не реализуются G0-S.

[Норматив PC-0](./tz_terrain_generation.md#surface-planning-cache-pc0):
planning cache содержит только derived immutable envelopes. Edit сначала
меняет authoritative domain inputs, затем replan affected dependency closure;
L0/L2 материализуются по запросу. Cache eviction/restart не является edit и
не меняет UID/seed/geometry. Invalidation event не источник correctness:
expected keys/refs строятся от authoritative source projection.

Write-owner сверяет captured source revision под authoritative write guard
перед публикацией pack/manifest или соответствующей patch boundary. Mismatch
отклоняет write и требует replan; cache не выполняет commit и не публикует
stale как latest. PC-0 готовит caller seam для будущего WorldSnapshot/Patch
adapter, не реализует platform patch runtime. Immutable pack и terrain_delta/
climate_delta precedence сохраняются; генераторы не читают Patch Store сами.
