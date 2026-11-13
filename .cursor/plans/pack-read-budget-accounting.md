# Pack read: учёт byte budgets и распаковки

Статус: PROJECT, уточнение REV-02 по фактическому коду. Runtime не изменён. Основание публичных полей — [ТЗ Pack, PackPartReadBudget](../../docs/tz_world_pack_storage.md); это не новый контракт настроек и не разрешение orchestration внутри Pack.

## Что уже есть

| Механизм | Подтверждённая гарантия | Чего не гарантирует |
|---|---|---|
| [ContentAddressedBlobBackend.read_verified](../../backend/app/storage/artifacts/blobBackend.py) | До IO проверяет `0 < ref.nbytes <= max_bytes`, затем размер и digest | Нет счётчика нескольких объектов одного read_part; `ValueError` не является typed budget signal |
| [read_verified_file](../../backend/app/storage/artifacts/blobRead.py) | Читает до `ref.nbytes`, проверяет лишний байт и digest | `bytearray` и итоговый `bytes` могут одновременно занимать память; лимит encoded bytes не равен пределу heap |
| [TileCodec.decompress/decode](../../backend/app/application/worldData/pack/io/tileCodec.py) | Распаковка zstd, затем JSON parse | Caller output cap отсутствует; размер compressed ArtifactRef не ограничивает decoded bytes |
| [packBlobWire._parse_frames](../../backend/app/application/worldData/pack/io/packBlobWire.py) | Проверяет границы записей settlement и декодирует каждый frame | Нет общего output budget для всех frames; проверка длины compressed frame не ограничивает распаковку |
| [DecodeLimits](../../backend/app/dataModel/encoding/decodeLimits.py), [decode_bounded](../../backend/app/application/encoding/boundedCanonicalDecode.py) | Canonical payload проверяется до построения owner-модели; byte/node/depth/item bounds; затем build и canonical re-encode | Не универсальный JSON/zstd decoder и не точный RAM bound; второй проход и re-encode расходуют CPU/память |
| [Hydrology profile](../../backend/app/dataModel/hydrology/pack/profile.py) | Root: 16 MiB, 524288 nodes; shard: 4 MiB, 262144 nodes; depth 64, container items 65536 | Это существующие ограничения конкретного формата, не defaults для других payload |

## Учёт encoded IO в одной операции

Публичный `PackPartReadBudget` сохраняет четыре поля: `max_manifest_bytes`, `max_index_bytes`, `max_payload_bytes`, `max_total_bytes`. Все положительные strict int. Не переносить LRU capacity/CachePolicy в byte limits.

Проект внутренней реализации `PackPartReadOperation.read_part`: request-local счётчики, без нового публичного POJO, singleton или durable store. Перед каждым verified physical read определить роль открываемого объекта, проверить descriptor и резервировать `ref.nbytes` в остатке total; для intermediate index — также в общем остатке index. Manifest/payload проверяются против своего stage cap. Backend получает не больший допустимого остатка лимит; owning format cap применяется дополнительно, а не заменяет request budget.

Резервирование выполняется до открытия/выделения body; при превышении IO не начинается. Повторное физическое чтение того же ref снова расходует total и, для index, index budget. Нельзя сбрасывать счётчик при переходе к следующему файлу или каждому root/shard. Локальное повторное использование уже проверенных bytes не является новым physical read; повторное декодирование всё равно обязано соблюдать decoder limits. При ошибке операция завершается по [матрице отказов](pack-part-read-error-mapping.md), внутренних retries нет.

Роль определяется этапом чтения, а не названием схемы: запрошенный `locations_index` или `spatial_root` расходует payload budget; индекс, открытый для разрешения другого payload, — index budget. Один physical read не списывается дважды в total из-за нескольких semantic uses. Наличие сложного traversal не разрешает открывать произвольные refs вне проверенной pinned closure.

**Граница точности:** предложенный счётчик учитывает зарезервированные encoded body bytes. Existing backend дополнительно делает `read(1)` для обнаружения лишнего содержимого; overhead IO, этот probe, decoder allocations и copies не покрываются обещанием точного physical/RAM лимита. ТЗ говорит о сумме bytes объектов, но отдельно не определяет probe accounting. До утверждения этой детали нельзя объявлять `max_total_bytes` точным пределом всех байтов OS-read. Проверку лишнего байта не удалять ради соответствия счётчику.

## Распаковка и materialization — отдельная граница

[Конкретный zstd binding](pack-zstd-output-binding.md): проверенный локально header preflight перед existing one-shot decompression; сохраняется отказ unknown-size frames и существующая trailing-data policy. Streaming EOF и один max_output_size не доказали требуемую гарантию. Проект механизма не закрывает численные caps, window/heap и миграцию callers.

Четыре IO-поля не переименовываются и не начинают молча означать decoded bytes. Для zstd/JSON форматов требуется явный owning decoder output cap: ограничение должно действовать во время получения распакованных bytes, до полного JSON parse. Проверка длины уже полностью распакованного результата недостаточна. Конкретный bounded zstd adapter и его поведение на всех принимаемых разновидностях frame ещё не доказаны; нельзя объявить проблему закрытой добавлением одного аргумента без проверок.

Для settlement общий счётчик decoded bytes включает header record и каждый district record; per-frame cap сам по себе недостаточен. Накопленные модели/списки требуют structural admission, даже если каждый frame укладывается в output cap. Существующий порядок frames и семантику сборки не менять.

Для map_tile/fine terrain/climate нужен bounded output до JSON admission; `side²` не является byte limit и не разрешает запрет sparse payload. Для plain JSON locations index/grade slots encoded cap действует до parse, но не заменяет строгую схему и structural bounds. Для canonical hydrology переиспользовать существующий profile/DecodeLimits, не создавать вторую копию числовых ограничений.

Числа для отсутствующих output/structural caps в этом уточнении **не назначены**. Нужны owning format binding, источник явного лимита и обоснование на допустимых данных; фактический peak RAM проверяется отдельно от суммы encoded/decoded bytes. Это локальная задача Pack/decoder, не основание ждать миграцию Source или запускать producer. [Решение по settings](pack-settings-crud-disposition.md) не пересматривается, hot settings service не добавляется.

## Ответственность и приёмка

[Resource-limit trace и проект](pack-read-resource-limit-signal.md) конкретизирует canonical subtype, сохранение через wrappers и прямую проверку encoded IO. Реализация и bounded zstd output signal ещё OPEN.

Публичный wrapper делегирует одной `PackPartReadOperation`; она учитывает ресурсы своего чтения и возвращает existing `PackPartReadRefusal(BUDGET_EXCEEDED)` при достоверно установленном превышении. Pure decoder ограничивает свой output/структуру, backend проверяет bytes, guard сохраняет lifetime до завершения IO. DAG выбирает дальнейшую операцию; Cache/Source/producer не вызываются. Новых публичных методов, зеркальных DTO, CRUD или изменения порядка sources → evidence → manifest → codec/readers нет.

До реализации остаются OPEN: численные output caps и их binding для форматов без них; точный внутренний resource-limit signal вместо разбора текста `ValueError/CanonicalEncodingError`; probe accounting; общий wiring счётчика. Schema-invalid cardinality остаётся INVALID_*; не каждое нарушение структурного правила является resource refusal.

Проверки реализации: exact cap и cap+1 до IO; два допустимых отдельно index, превышающих общий index/total; повтор одного ref; target index как payload; compressed body в бюджете при output overflow; settlement с допустимыми отдельно frames, превышающими общий output cap; malformed frame отдельно от budget; сохранение guard при отмене; отсутствие retries и частично возвращённых моделей. Проверять допустимые реальные payload и peak allocation отдельно. В этой документационной проверке runtime tests/измерения не выполнялись; общая приёмка Pack не объявляется завершённой.
