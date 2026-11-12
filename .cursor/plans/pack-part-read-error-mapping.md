# Pack read_part — mapping отказов по этапам

2026-11-12. PROJECT по [ТЗ Pack](../../docs/tz_world_pack_storage.md), [pin mapping](pack-pin-identity-mapping.md) и [concrete read-моделям](pack-read-concrete-models.md). Только статическая сверка/документация; runtime/SQL/DAG не менялись, тесты не запускались.

## Один существующий проект публичного отказа

Используется `dataModel/worldPack/read/part.py::PackPartReadRefusal(pin_id, publication, address, reason, artifact)` и PackPartReadReason из ТЗ. Новый PackReadError/ReadStageError DTO, второй набор причин или message-based classifier не вводится. Stage ниже — контекст внутренней операции, не новое поле публичного POJO.

Refusal сохраняет pin_id/publication/address **запроса**; при INVALID_PIN/PUBLICATION_MISMATCH эта publication не объявляется проверенной. Success/Absent возвращают только подтверждённую pinned publication. artifact — точный ref объекта, на котором отказано, если уже известен; иначе None. При invalid manifest это manifest ref, при intermediate index — ref этого индекса, при payload — payload ref. Не заполнять поле предположением о нужном артефакте.

Malformed Python/JSON request проходит shared structural validation и не становится PackPartAbsent. Concrete field diagnostics и их transport следуют общему error freeze. Infrastructure/cancellation не входят в domain refusal union только потому, что ошибка возникла во время read.

## Детерминированная граница проверок

Локальная структура запроса и descriptor admission → exact pin/publication guard → manifest bytes/schema → разрешение адреса и необходимых индексов → payload bytes/schema/provenance → результат. Это локальный алгоритм одной read-операции, не новые стадии DAG. Не открывать следующий объект после отказа предыдущей зависимой проверки. Read не собирает список частичных successes и не возвращает value вместе с refusal.

| Проверяемый факт | Публичный исход | Основание / ограничение |
|---|---|---|
| Запрос не соответствует concrete Input, invalid field/enum/extra | Shared structural validation failure | Не INVALID_PAYLOAD и не ABSENT; input ещё не принят |
| Неизвестный read descriptor, неверная concrete specialization или роль для этого read contract | CONTRACT_MISMATCH | Exact registry binding известен до payload read; caller class не выбирает иной decoder |
| Чужой/неизвестный pin, store/execution/invocation/key identity mismatch | INVALID_PIN | Existing pin identity checks; не PUBLICATION_MISMATCH для любого конфликта |
| Подтверждённое закрытие pin/execution | CLOSED_PIN | Сохранить existing PackClosed distinction |
| Pin принадлежит другой publication либо полный historical expected отличается | PUBLICATION_MISMATCH | Existing row.publication_id + read_exact/full comparison; одинакового pack_hash недостаточно |
| Известный объект не удерживается требуемым владельцем | MISSING_HOLD | Проверяется внутри guard; не выводить из generic unavailable |
| Известный объект не sealed | UNSEALED | Отдельный факт catalog; не подменять corruption/absence |
| Превышен принятый caller/binding byte budget до/во время bounded read | BUDGET_EXCEEDED | Суммарные limits учитывают фактически открытые объекты; не ловить любой ValueError как budget |
| Manifest имеет неверные bytes/digest/schema, несовместимый manifest envelope или некорректный состав | INVALID_MANIFEST | Ref — manifest; повреждённый root документа не разрешает искать address и возвращать absent |
| Intermediate index, необходимый для разрешения requested part, повреждён либо структурно противоречив | INVALID_INDEX | Ref — конкретный промежуточный объект; не смешивать с адресованным payload-индексом |
| Заявленный точный artifact отсутствует в catalog/физически | MISSING_ARTIFACT | Подтверждённое отсутствие, а не недоступность backend. Missing manifest/index тоже не ABSENT |
| Адресованный payload повреждён или нарушает owning schema/role/геометрию | INVALID_PAYLOAD | Includes digest corruption именно payload; role mismatch сохранённых bytes — не ошибка выбора request contract |
| Durable provenance не соответствует адресу/ref/publication либо не проходит owning проверку | INVALID_PROVENANCE | Не выполнять live Source CRUD, не заполнять proof по default. Missing referenced bytes остаются MISSING_ARTIFACT, если отказ именно в их доступности |
| Полный проверенный состав не содержит requested address | PackPartAbsent | Только после достаточной pin/manifest/index проверки, не по исключению или счётчику |
| Backend unavailable, SQLite/I/O malfunction, неизвестный infrastructure failure | Существующий infrastructure exception | Не придумывать SOURCE_UNAVAILABLE в PackPartReadReason и не преобразовывать в absent |
| Task cancellation | Распространить cancellation после освобождения stream/guard | Не возвратить CLOSED_PIN/CANCELLED DTO; не отпускать защиту, пока worker ещё читает файл |

Если одновременно обнаружены hold/seal нарушения, порядок локальных проверок должен быть стабильным и зафиксирован в binding tests. Не требуется дочитывать всё ради второй причины. Внутренние ошибки программирования (неверно сконструированный diagnostic, несовместимая registry composition) не маскируются под ошибку payload пользователя.

## Роль объекта определяет INVALID_*, а не название формата

LocationsIndexWire, запрошенный по locations_index, является **payload** этого read_part; его invalid JSON даёт INVALID_PAYLOAD. Тот же принцип для spatial_root: root, запрошенный как результат, — payload; root, используемый как промежуточный индекс достижимости другого объекта, — index. Filename/format_key сами не определяют stage. Не вводить публичный произвольный shard read только ради наличия INVALID_INDEX.

Ошибочный manifest descriptor относится к INVALID_MANIFEST, ошибочная сохранённая промежуточная ссылка — к INVALID_INDEX, ошибочный payload descriptor в противоречащем manifest составе выявляется при admission состава. CONTRACT_MISMATCH относится к несовместимости **запрошенного read-контракта** с разрешённой ролью/форматом, а не ко всем проблемам любых refs. Конкретные проверки должны выполняться до вызова backend с неподходящим ref.

Отсутствие address нельзя вернуть из частично прочитанного/повреждённого индекса. При простой inline parts схеме отсутствие доказывает validated manifest; decoder не читает все несвязанные payload мира для этого доказательства. Это не ослабляет shape/identity/provenance инварианты, заявленные для выбранной read-границы.

## Existing ошибки: что переиспользовать и чего недостаточно

[PinnedManifestReader](../../backend/app/application/worldData/pack/read/pinnedManifestReader.py) уже возвращает ManifestReadRefusal для pin/identity/budget/schema. CLOSED_PIN, INVALID_PIN, MISSING_HOLD, UNSEALED, BUDGET_EXCEEDED, INVALID_MANIFEST сохраняют соответствующий смысл в part-read. Но его IDENTITY_MISMATCH объединяет ref/cache-key/profile причины и не сравнивает полную expected publication. Поэтому универсальный mapping IDENTITY_MISMATCH → PUBLICATION_MISMATCH неверен. Exact publication mismatch определяется отдельно по [pin guard проекту](pack-pin-identity-mapping.md); остальные identity checks сопоставляются в том этапе, где причина известна. Внутренний cache key mismatch не доказывает другую publication.

[CorruptBlobError](../../backend/app/application/artifacts/contracts/blobRead.py) наследует PublicationInfrastructureError, но имеет конкретный смысл mismatch physical bytes/descriptor. [read_verified_file](../../backend/app/storage/artifacts/blobRead.py) выдаёт его при short/long bytes и digest mismatch. Предлагаемый Pack mapping перехватывает **этот конкретный тип раньше общего infrastructure handler** и выбирает INVALID_MANIFEST/INVALID_INDEX/INVALID_PAYLOAD по текущему объекту. Остальной PublicationInfrastructureError не превращается автоматически в corruption.

[ContentAddressedBlobBackend.read_verified](../../backend/app/storage/artifacts/blobBackend.py) оборачивает OSError в PublicationInfrastructureError с cause. Подтверждённый FileNotFoundError допускает MISSING_ARTIFACT для именно открываемого ref. Permission/IO/device/SQLite ошибки не означают missing. Не разбирать строку «cannot read artifact content» и не исследовать произвольную цепочку исключений ради угадывания причины. Его ValueError может означать invalid ref **или** budget: Pack должен выполнить свои явные prechecks, а не классифицировать по тексту.

Existing backend `_io` дожидается завершения thread worker при cancellation до распространения отмены. Новый wrapper должен сохранить это свойство и lifetime guard; `CancelledError` не ловится как обычный domain refusal.

[OpenWaterBlobReader](../../backend/app/application/worldData/pack/spatial/openWaterBlobReader.py) сейчас объединяет unsealed/missing hold, недоступную registry и infrastructure/OSError в SpatialBlobReadError(SOURCE_UNAVAILABLE). Из этой причины нельзя восстановить нужные разные Pack outcomes. SOURCE_CORRUPT/SOURCE_MISSING/RESOURCE_LIMIT имеют более конкретный смысл, но не дают универсального mapping для всех SpatialReadFailureReason. Поэтому existing spatial facade нельзя подключить как готовый error-complete generic backend: target internal binding должен проверять seal/hold и сохранять infrastructure type до такого объединения. Не менять публичный Spatial error контракт молча и не создавать зеркальную иерархию ошибок.

## Budgets и schema limits

max_manifest_bytes/max_index_bytes/max_payload_bytes/max_total_bytes — отдельные пределы из PackPartReadBudget; повторные physical reads расходуют total, intermediate index budget суммируется. Переполнение проверяется до allocation/open, где возможно. Configured decoder output cap также требует явного typed mapping превышения лимита; compressed ref.nbytes его не заменяет.

Existing [boundedCanonicalDecode](../../backend/app/application/encoding/boundedCanonicalDecode.py) выдаёт CanonicalEncodingError как для malformed wire, так и для depth/node/collection limit. Нельзя различать их по message. Owning **schema constraint** (например, недопустимое количество элементов record) относится к INVALID_* объекта; **resource budget** — BUDGET_EXCEEDED, если причина явно известна boundary. Если decoder не сохраняет нужное различие для resource cap, конкретный внутренний adapter/typed signal остаётся OPEN. Общий mapping всех CanonicalEncodingError в budget либо всех в corruption не закрывает этот gate.

## Приёмка и остаток

Нужны проверки каждой строки mapping, включая: same hash/different publication; corruption отдельно manifest/index/payload; absent address против missing BLOB; missing hold против unsealed; SQLite unavailable не становится domain absence; cached identity mismatch не объявляется публикационным по догадке; locations_index payload имеет INVALID_PAYLOAD; отмена во время worker read сохраняет guard до окончания; cumulative budgets учитывают повторные reads.

Публичный отказ остаётся одним PackPartReadRefusal; подробные причины не восстанавливаются из текста или объединённой Spatial ошибки. Статус PROJECT: матрица сопоставления конкретизирована, но точный internal carrier для publication mismatch/resource cap, guard/backend wiring, общий structural error transport и реализационные tests ещё OPEN. PackPartReadOperation владеет mapping своей read-границы; decoder pure, guard защищает lifetime, backend проверяет bytes, DAG выбирает последующее действие. Новые публичные операции и скрытая orchestration не добавляются.
