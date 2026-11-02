# generator_public_method — реестр требований к публичным методам генератора

**Статус:** EXACT CONTRACT PROPOSAL / НА ПРИЁМКЕ, 2026-11-02. Freeze не принят; implementation OPEN. Создан по поручению пользователя; существующего плана с этим именем при поиске не найдено. Не является реализацией новых API или разрешением production cutover.

Публичные reads реализует генераторный/Pack домен; GEN-DAG потребляет принятые контракты. Имена методов ниже — target proposal, не существующие символы кода. Предлагаемые владельцы, POJO и exact files описаны в GEN-BAKE-READ §§5–10; внешние OPEN contracts — §11. Они ещё требуют приёмки.

| Имя ноды | Имя публичного метода | Требуемый результат | Техдолг | Отдельный план |
|---|---|---|---|---|
| `read_world_light_bake` | `read_light_bake` (world coverage, LightReadRequest, proposal GBR-1) | Полный light-комплект мира: data/refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `read_scoped_light_bake` | `read_light_bake` (request scope, LightReadRequest, proposal GBR-1) | Полный light-комплект запроса: data/refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_full_bake` | `read_full_bake` | Full L0 + требуемая topology: data/refs либо missing | [GEN-READ-2](../../docs/tz_generator_technical_debt.md#gen-read-2) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_detailed_bake` | `read_location_l2` | L2 owning scope выбранной location: data/refs либо missing | [GEN-READ-3](../../docs/tz_generator_technical_debt.md#gen-read-3) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |

Для всех методов: явные world/scope/publication inputs, отдельный Error для corruption/read failure/stale refs; нет генерации, writes, fallback, SQL/filesystem знания в ноде. Это domain reads, не HTTP endpoints и не новый central gameplay facade.

Полные требования, AS-IS evidence, ссылки на readers/classifier/facades и порядок реализации принадлежат [GEN-BAKE-READ](./generator-public-bake-reads.md). Потребители и форма found/missing: [GEN-DAG-NODE-DEPENDENCY §§8–9](./gen-dag-node-dependency.md#9-input--output-трёх-bake-read-нод--уточнение-пользователя).

Изменение названий/контрактов синхронизируется в обеих картах и техдолге; самостоятельно копировать readers в DAG или считать метод принятым по наличию строки здесь запрещено.

**Light readers:** группа light_bake_readers содержит read_world_light_bake и read_scoped_light_bake; смысловые I/O/Error/DoD — [§9.5 реестра нод](./gen-dag-node-dependency.md#95-light_bake_readers--выходные-контракты-и-definition-of-done). Обе читают L0 и обязательные связанные index/climate/metadata для своего coverage. Общий domain reader допустим. check_light_bake сохраняет прежнее родство; replacement bindings новых нод OPEN, нового parent NodeId нет. NamedLocation entry использует scoped reader; world complete не его prerequisite.

## Публичные preparation pipelines — отдельные domain-owned интерфейсы

Эта секция не является read-картой выше. Имена target interface/method фиксируются как требования реализации; наличие строки не означает готовый API или изменение зафиксированных нод.

| Потребляющая операция | Owning domain | Интерфейс / метод | Выход / DoD | Отдельное требование |
|---|---|---|---|---|
| L0 light/full preparation и L2 detailed preparation, когда нужен surface plan; exact node binding OPEN | surface planning | `ISurfacePlanningPipeline.prepare_surface_plan` | Согласованный immutable surface-plan bundle для captured inputs, exact dependency/source evidence и diagnostics; без world publication | [GEN-SURFACE-PLAN](./generator-public-surface-planning.md), [GEN-PLAN-1](../../docs/tz_generator_technical_debt.md#gen-plan-1) |

Capture boundary, exact types/files и baseline/GEO choice требуют domain freeze. Readers не получают обязанности подготовки или передачи настроек. Имена остальных ещё не разобранных pipeline interfaces не назначаются автоматически.

## GBR-1 — синхронизированная карта exact proposal

Нормативный проект, включая поля/enum/errors/lifetime и сценарии:
[GEN-BAKE-READ §§5–12](./generator-public-bake-reads.md#5-exact-contract-freeze-proposal-gbr-1-2026-11-02).
Это документальная спецификация на приёмку, не existing production symbols.

| Операция | Proposed owner / factory | Exact Input → Output |
|---|---|---|
| read_light_bake | PackLightBakeReader; build_pack_read_services.light_bake | LightReadRequest(identity, publication, WorldLight либо RequestLight, control) → BakeReadFound[LightBakeData] либо BakeReadMissing |
| read_full_bake | PackFullBakeReader; build_pack_read_services.full_bake; C23 — SettlementTopologyRead | FullReadRequest(identity, publication, required scope, control) → BakeReadFound[FullBakeData] либо BakeReadMissing |
| read_location_l2 | PackTerrainBakeReader; build_pack_read_services.terrain_bake | LocationL2ReadRequest(identity, publication, target_uid, volumes, TERRAIN_L2, control) → BakeReadFound[LocationL2BakeData] либо BakeReadMissing |

Все методы async; typed BakeReadError exception и cancellation отдельно от
found/missing. Полные schemas и закрытый proposed error enum — owning §7.
Found содержит проверенные разрешимые immutable refs, pinned одной publication;
missing содержит nonempty exact absent/incomplete scope. Valid empty — found.
Declared artifact loss, stale/wrong-world/corruption/unsupported/read failure — Error.

World light = authoritative location anchor/territory ∪ полная declared hydro
geometry tile coverage, не world_bounds, не endpoints-only collector. Request
light проверяет весь request scope плюс обязательные index/climate/metadata;
world completeness не блокирует NamedLocation. Full = required L0 + применимые
целые C23 settlement closures; нет settlements → NOT_APPLICABLE, не missing.
L2 разрешает published leaf→terrain owner mapping, не файл на каждый leaf UID.
L2 found не доказывает C11 или Spatial wet/dry/known; L0 не canonical water source.

Отдельный coordinate/wilderness consumer requirement: предлагается
read_wilderness_l2 за PackTerrainBakeReader, но операция **не добавлена** к трём
принятым именам и требует отдельной приёмки. Fake NamedLocation запрещена.
Pin/absence/retention/GC, coverage producer receipt, immutable C23 publication join,
C11 evidence и coordinate API — конкретные внешние OPEN §11. Snapshot draft adapters
не готовые ports. SP-1/GEO EF-1 и частные SP-P0 §15.17 учтены; SP-P0 целиком/SP-M
не приняты. Ни код, ни bindings, ни публикация/cutover не разрешены этой картой.

## Актуализация: принятое решение о видимой композиции

[GEN-BAKE-READ §13](./generator-public-bake-reads.md#13-решение-пользователя-публичные-read-ноды-и-видимая-композиция-2026-11-02)
имеет приоритет над первоначальной GBR-1 картой выше.

Публичные domain methods читаются через переиспользуемые публичные read-ноды;
другие ноды вызывают их через engine CALL/RETURN. Композиция самостоятельных reads
видна в DAG, а SQL/filesystem остаются внутри domains. Новые NodeIds/связи не приняты.

`PackFullBakeReader` и `build_pack_read_services.full_bake` отозваны. Full-result
предлагается собирать явной композицией light-read и C23-read нод с общей pinned
publication/retention. Строка read_full_bake сохраняет требование результата;
уровень/имя aggregate API и concrete binding OPEN, скрытый Pack composite запрещён.
PackLightBakeReader/PackTerrainBakeReader и topology-owner domain read остаются
proposed targets. Это принятие архитектурного принципа, не всего contract freeze.
