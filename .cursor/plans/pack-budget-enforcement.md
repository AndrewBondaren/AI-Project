# Pack — источники лимитов и точки проверки

Статическая сверка текущего Pack; продолжение P2 из [сводки приёмки](pack-local-acceptance-status.md). Новые числовые defaults не назначаются. Размер мира, количество locations/tiles и Cache capacity не заменяют ограничения конкретного чтения/кодирования. Planning остаётся неблокирующей отложенной темой.

## Подтверждённые источники

| Объект | Источник | Где проверяется / что ещё требуется |
|---|---|---|
| Manifest storage bytes | `WorldPackCacheSettings.manifest_max_bytes`, explicit положительное deployment значение | `PacksWiring.initialize_pack_storage` передаёт его в manifest_format и ManifestBlobBackend. При None регистрация Pack storage пропускается; None не означает бесконечный бюджет |
| Manifest staging | `manifest_format(max_bytes)` | Проверяет bytes length до decode_manifest; TypedArtifactStager.encode выполняется до reserve. Oversized bytes не создают reservation |
| Manifest read | `ManifestPinRead.max_bytes` / проектный max_manifest_bytes плюс backend cap | ManifestBlobBackend использует min(request, configured). ContentAddressedBlobBackend должен пропустить descriptor только в пределах этого cap, затем read_verified_file читает ровно ref.nbytes с проверкой лишнего байта и digest |
| Spatial root | owning `hydrology/pack/profile.py::ROOT_V1` | Existing 16 MiB, 524288 nodes; depth=64, container items=65536. Descriptor admission и owning bounded decode, без копии limits в Pack |
| Spatial shard | owning `SHARD_V1` | Existing 4 MiB, 262144 nodes; те же depth/items. Каждый shard ограничивается отдельно; request total учитывает сумму фактических чтений |
| Pack read request | Проект `PackPartReadBudget` из ТЗ | Положительные strict max_manifest_bytes/max_index_bytes/max_payload_bytes/max_total_bytes. Это запросные IO budgets, не существующая реализация decoded memory limits |
| Cache | Existing CachePolicy/PackReadPolicy | Ограничивает удержание в RAM по своему контракту. Не использовать как разрешённый размер decoder input/state и не менять принятую Cache policy |

Точное deployment значение manifest_max_bytes не выбирается по profile root/shard: это разные форматы. Existing регистрация применяется к прежней схеме manifest; принятая новая wire/storage пара должна сохранить явный параметр budget при миграции binding, а не молча унаследовать иной формат.

## Лимит encoded bytes не равен пределу памяти

`finish_pack_preparation` сначала вызывает encode_candidate_manifest и получает bytes, затем stage. Действующий manifest encoder строит полный JSON string и bytes; ограничение manifest_format срабатывает уже после этого выделения памяти. Поэтому утверждение «manifest budget гарантирует ограничение памяти ещё до encoding» неверно. Он доказан как storage/pre-reservation/read bound. Для encode-memory отдельно требуется bounded sink/preflight либо измеренная допустимая память на заданный максимум; не выдавать post-encode len за pre-allocation защиту.

`TileCodec.decompress` вызывает zstandard decompressor без явного лимита выхода, затем decode выполняет orjson.loads полного результата. Этот путь используется map_tile, fine terrain и climate, а framing settlement проверяется его отдельным binding. Encoded descriptor budget не ограничивает decompressed output. Проверка len после полной распаковки не устраняет перерасход. При целевой реализации нужен отдельный лимит decompressed bytes, применяемый во время bounded decompression, затем ограничения/оценка памяти parser/POJO. При многокадровом формате проверять совокупный объём, а не разрешать полный budget каждому кадру независимо.

JSON без сжатия (locations_index и grade sidecars) требует encoded cap до parse и отдельной проверки expansion в Python objects. Отсутствие compression не означает равенство размера bytes и RAM. Для fine terrain возвращать owning runs, не разворачивать z-интервалы в клетки внутри read_part ради валидации.

## Единое правило read budget

На физическое чтение лимит — минимум: cap зарегистрированного binding, соответствующий request cap и остаток max_total_bytes. Для промежуточных индексов дополнительно расходуется общий max_index_bytes. Проверять ref.nbytes против доступного остатка до чтения и decode; descriptor сам по себе не является бюджетом. Каждый фактический повторный read расходует total. Общий ref в нескольких logical addresses не означает двойной расход, если физически читается один раз; повторный read не становится бесплатным только из-за совпадения ref.

При исчерпании лимита — существующий проектный BUDGET_EXCEEDED для read, без fallback на latest, частичного payload или пропуска проверки. Для oversized итогового manifest — MANIFEST_OVERSIZE/MANIFEST_LIMIT_EXCEEDED по prepare-контракту. Не классифицировать отсутствие нужной конфигурации как повреждение пользовательского payload. Runtime failure/IO сохраняет собственный исход.

## Источники значений: сверка 2026-11-13

| Лимит | Подтверждённый источник | Решение для текущего проекта |
|---|---|---|
| Manifest encoded bytes | WorldPackCacheSettings.manifest_max_bytes → AppSettings.world_pack → PacksWiring | Существующий путь сохраняется; None не означает unlimited. Конкретное deployment значение здесь не назначено |
| Hydrology root/shard | Owning ROOT_V1/SHARD_V1 и DecodeLimits | Сохраняются существующие значения 16/4 MiB, nodes 524288/262144, depth 64, items 65536; не копировать их в настройки остальных payload |
| Request encoded IO | PackPartReadBudget запроса | Не источник фиксированного decoder profile; caller не увеличивает format cap |
| JSON/zstd payload profiles | Новых persisted полей в WorldPackCacheSettings не найдено | Источник и численные значения ещё проектируются; наличие параметра constructor не доказывает production configuration |

В просмотренном backend/config.toml секции [world_pack...] не найдены. ConfigManager._to_flat/_to_nested и AppSettings.update умеют читать/сохранять существующий WorldPackCacheSettings; добавление произвольных TOML-ключей сейчас не подключит decoder — модель extra=forbid. PackBakeDefaults.zstd_level/codec_version и debug max_tiles не являются лимитами распаковки. Файлы конфигурации этой сверкой не изменялись.

**Владение лимитами — согласовано пользователем 2026-11-13.** Ограничения одного артефакта и его формата определяет домен-владелец payload; Pack применяет этот контракт без собственного переопределения. Существующие профили Hydrology сохраняются. Новые фиксированные пределы остальных payload сейчас не вводятся. Недостающие ограничения распаковки/структуры согласуются с владельцами форматов и остаются явно незакрытой защитой до такого согласования. Pack владеет своим manifest и бюджетом чтения одной операции PackPartReadBudget, включая суммарный encoded IO; этот бюджет не определяет допустимый размер данных чужого домена. Превышение даёт явный отказ, без обрезания, пересэмплирования или изменения генерации.

Предложение хранить все profiles в world_pack снято. Источник конфигурации определяется после установления владельца конкретного ограничения; существующий manifest_max_bytes и CachePolicy этим не меняются. Наличие механизмов DecodeLimits/JsonDecodeBudget/zstd cap в проекте не разрешает Pack самостоятельно назначать их значения. В публичный запрос не передаются Python owner types или callbacks; не сериализовать RecordLimits/FieldRef как пользовательские имена классов и не создавать зеркальный PackDecodeLimits ради TOML.

**Основания для чисел.** До назначения новых caps нужен набор допустимых producer outputs по каждому формату: encoded bytes; для zstd — decoded bytes и window; для settlement — суммарные frames; для JSON — nodes/depth/максимальная ширина контейнера; отдельно peak memory parse + POJO. Размер текущего sample не является верхней границей поддержанного мира. Обоснование включает поддержанный масштаб, запас и поведение при превышении; если масштаб не ограничен контрактом, конечный cap является эксплуатационной политикой отказа, а не доказанным максимумом данных. Не вводить ограничение мира или менять генерацию для подгонки под выбранное число.

Числа и production fields недостающих owning profiles остаются OPEN у соответствующих владельцев. Это не новая задача Pack по назначению чужих лимитов. Выбор источника не разрешает автоматически менять lifecycle настроек или распространять Cache CRUD-исключение на Pack budgets; [settings disposition](pack-settings-crud-disposition.md) сохраняет этот отдельный критерий. Независимая работа над Pack contracts может продолжаться, но отсутствие ограничений распаковки/структуры нельзя объявить закрытым одним request IO budget.

## Промежуточный state

PackPreparationState содержит metadata, refs и provenance, а не payload bytes. manifest_max_bytes относится к кодированному итоговому manifest и автоматически не ограничивает живой state, несколько одновременно существующих immutable state или транспорт DAG. В просмотренном публичном OutputRef указан тип результата, но нет byte cap; это не доказательство наличия либо отсутствия лимита всего engine.

Текущий Pack не вводит session store, произвольный state_max_bytes или ограничение числа locations для закрытия этой строки. При подключении реального способа передачи нужно зафиксировать: передаётся ли объект в памяти или serialized value, сколько состояний удерживается одновременно и какие существующие ограничения применяет owning transport. Затем проверить максимальный фактический состав и peak memory. Это отдельная интеграционная проверка транспорта, а не основание проектировать новый протокол хранения сейчас. До измерения не заявлять, что размер state ограничен manifest budget.

## Оставшаяся локальная работа bindings

### Конкретный контракт лимитов binding/decoder

Использовать уже предложенный `PackPartReadBinding[T].max_payload_bytes` как **encoded** предел одного payload. Не добавлять рядом max_encoded_bytes с тем же смыслом. Публичный PackPartReadBudget ограничивает IO вызова; decoder/классы/профили в него не передаются. PackReadPolicy LRU capacities и PackBakeDefaults debug max_tiles не являются источником byte limits.

Структурные параметры переиспользуют `dataModel/encoding/decodeLimits.py::DecodeLimits(max_bytes, max_nodes, max_depth, max_items, field_sizes)` и existing RecordLimits/CollectionLimit с owning FieldRef. Это внутренние данные composition, не public POJO: RecordLimits содержит Python owner type. Новый PackDecodeLimits с копией полей не вводится.

Конкретный decoder получает immutable limits через constructor/factory. Existing проектный port сохраняет `decode(payload: bytes, format_version: FormatVersion) -> T` и `validate(value: T) -> T`; caller не меняет decode profile в запросе. Registry immutable после composition. Hydrology использует owning ROOT_V1/SHARD_V1.decode_limits и существующий bounded decoder.

| Семейство | max_payload_bytes binding | DecodeLimits.max_bytes и структурная проверка |
|---|---|---|
| map_tile, wilderness_chunk/location_terrain, climate_coarse/fine | Encoded bytes с заголовком и compressed body | Decompressed bytes до JSON parse, затем nodes/depth/items и owning constraints |
| settlement framed | Полный blob с header, length prefixes и всеми frames | Совокупные decompressed bytes/nodes/items на все records; следующий frame расходует остаток, не получает свежий максимум |
| locations_index, tile/location grade slots | Полные JSON bytes | JSON input bytes и структурные limits/expansion. Роли одного формата используют один decoder/profile |
| spatial root/shard | Existing owning max_bytes соответствующего формата | Existing bounded TLV decode_limits без копии schema |

**Предел переиспользования:** DecodeLimits является носителем параметров, не bounded JSON parser. Передача limits в объект рядом с orjson.loads не ограничивает память; проверка после parse не предотвращает уже случившееся выделение. Для JSON/framed требуется применение ограничений во время разбора с определённым способом подсчёта nodes/depth/items. Existing canonical TLV decoder не объявляется decoder другого wire format. Peak-memory проверяется отдельно.

**Admission configuration:** existing DecodeLimits — frozen dataclass без проверки положительности чисел. Composition проверяет exact int, не bool, положительные byte/node/depth/item caps и согласованные collection minimum/maximum до регистрации. Не требовать decoded cap >= encoded cap: заголовки/framing делают такое общее неравенство неверным. Numeric defaults не назначаются; explicit values поступают из owning profile/deployment. Отсутствие profile не трактуется как unlimited.

Read и final prepare используют один зарегистрированный decoder/profile для данного формата. Staging encode validation согласуется с тем же admission; ArtifactFormatContract не превращается в callback публичного read pipeline. Manifest сохраняет отдельный manifest_max_bytes. Регистрация двух расходящихся policies для одного binding недопустима.

Приёмка: invalid limits дают composition error до IO; request budget не меняет fixed decode profile; framed counters не обнуляются между records; shared format не получает разные codecs для разных address roles; hydrology limits сохраняются. Контракт описан, runtime проверки не запускались, числовые значения новых profiles не назначались.

Для map_tile, fine terrain, settlement, climate, locations_index и grade sidecars ещё требуется зафиксировать explicit per-format encoded/decompressed/decoded bounds там, где их нет, и production wiring. Значения должны происходить из owning settings/profile или обоснованной настройки deployment; не назначать общий 16 MiB только потому, что он существует у hydrology root. Существующий PackPartReadBudget задаёт границы вызова, но не закрывает отсутствующие production/decode limits. Ни P2 целиком, ни runtime protection этой инвентаризацией не объявляются выполненными.

Проверки реализации: boundary ровно cap проходит, cap+1 отказывает до parse/reserve; request выше backend не повышает лимит; маленький compressed payload с большим output прерывается в процессе decode; несколько индексов/кадров расходуют совокупный budget; repeated read расходует total; отсутствие manifest настройки не создаёт unbounded storage; peak-memory проверяется отдельно от encoded len. Тесты в этом срезе не запускались, код не менялся.
