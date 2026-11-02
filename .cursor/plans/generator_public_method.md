# generator_public_method — реестр требований к публичным методам генератора

**Статус:** REQUIREMENTS / OPEN, 2026-11-02. Создан по поручению пользователя; существующего плана с этим именем при поиске не найдено. Не является реализацией новых API или разрешением production cutover.

Публичные reads реализует генераторный/Pack домен; GEN-DAG потребляет принятые контракты. Имена методов ниже — target proposal, не существующие символы кода. Точные владельцы, POJO и файлы требуют contract freeze.

| Имя ноды | Имя публичного метода | Требуемый результат | Техдолг | Отдельный план |
|---|---|---|---|---|
| `read_world_light_bake` | `read_light_bake` (world coverage, exact signature OPEN) | Полный light-комплект мира: data/refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `read_scoped_light_bake` | `read_light_bake` (request scope, exact signature OPEN) | Полный light-комплект запроса: data/refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_full_bake` | `read_full_bake` | Full L0 + требуемая topology: data/refs либо missing | [GEN-READ-2](../../docs/tz_generator_technical_debt.md#gen-read-2) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_detailed_bake` | `read_location_l2` | L2 owning scope выбранной location: data/refs либо missing | [GEN-READ-3](../../docs/tz_generator_technical_debt.md#gen-read-3) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |

Для всех методов: явные world/scope/publication inputs, отдельный Error для corruption/read failure/stale refs; нет генерации, writes, fallback, SQL/filesystem знания в ноде. Это domain reads, не HTTP endpoints и не новый central gameplay facade.

Полные требования, AS-IS evidence, ссылки на readers/classifier/facades и порядок реализации принадлежат [GEN-BAKE-READ](./generator-public-bake-reads.md). Потребители и форма found/missing: [GEN-DAG-NODE-DEPENDENCY §§8–9](./gen-dag-node-dependency.md#9-input--output-трёх-bake-read-нод--уточнение-пользователя).

Изменение названий/контрактов синхронизируется в обеих картах и техдолге; самостоятельно копировать readers в DAG или считать метод принятым по наличию строки здесь запрещено.

**Light readers:** группа light_bake_readers содержит read_world_light_bake и read_scoped_light_bake; смысловые I/O/Error/DoD — [§9.5 реестра нод](./gen-dag-node-dependency.md#95-light_bake_readers--выходные-контракты-и-definition-of-done). Обе читают L0 и обязательные связанные index/climate/metadata для своего coverage. Общий domain reader допустим. check_light_bake сохраняет прежнее родство; replacement bindings новых нод OPEN, нового parent NodeId нет. NamedLocation entry использует scoped reader; world complete не его prerequisite.
