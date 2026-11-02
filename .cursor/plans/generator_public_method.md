# generator_public_method — реестр требований к публичным методам генератора

**Статус:** REQUIREMENTS / OPEN, 2026-11-02. Создан по поручению пользователя; существующего плана с этим именем при поиске не найдено. Не является реализацией новых API или разрешением production cutover.

Публичные reads реализует генераторный/Pack домен; GEN-DAG потребляет принятые контракты. Имена методов ниже — target proposal, не существующие символы кода. Точные владельцы, POJO и файлы требуют contract freeze.

| Имя ноды | Имя публичного метода | Требуемый результат | Техдолг | Отдельный план |
|---|---|---|---|---|
| `check_light_bake` | `read_light_bake` | L0 заданного scope: data/immutable refs либо missing | [GEN-READ-1](../../docs/tz_generator_technical_debt.md#gen-read-1) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_full_bake` | `read_full_bake` | Full L0 + требуемая topology: data/refs либо missing | [GEN-READ-2](../../docs/tz_generator_technical_debt.md#gen-read-2) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |
| `check_location_l2` | `read_location_l2` | L2 owning scope выбранной location: data/refs либо missing | [GEN-READ-3](../../docs/tz_generator_technical_debt.md#gen-read-3) | [GEN-BAKE-READ](./generator-public-bake-reads.md) |

Для всех методов: явные world/scope/publication inputs, отдельный Error для corruption/read failure/stale refs; нет генерации, writes, fallback, SQL/filesystem знания в ноде. Это domain reads, не HTTP endpoints и не новый central gameplay facade.

Полные требования, AS-IS evidence, ссылки на readers/classifier/facades и порядок реализации принадлежат [GEN-BAKE-READ](./generator-public-bake-reads.md). Потребители и форма found/missing: [GEN-DAG-NODE-DEPENDENCY §§8–9](./gen-dag-node-dependency.md#9-input--output-трёх-bake-read-нод--уточнение-пользователя).

Изменение названий/контрактов синхронизируется в обеих картах и техдолге; самостоятельно копировать readers в DAG или считать метод принятым по наличию строки здесь запрещено.
