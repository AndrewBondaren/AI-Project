# Pack JSON — структурный бюджет и внутренний отказ

2026-11-13, PROJECT. Только проект Pack-owned decoder; runtime не изменён. Дополняет [roster](pack-payload-binding-roster.md), [resource signals](pack-read-resource-limit-signal.md) и [zstd binding](pack-zstd-output-binding.md). Порядок producer/write/prepare не меняется.

## Основание

TileCodec и settlement frames используют orjson.loads после распаковки; grade sidecar — json.loads. Pack manifest codec уже использует object_pairs_hook для уникальных ключей, но callback вызывается после построения содержимого объекта. Найденные механизмы не подтверждают ограничение глубины, числа nodes/items до построения полного JSON-дерева. CanonicalDecodeLimitError относится к TLV, ZstdOutputLimitError — к распаковке; ни один из них не обозначает JSON structural overflow.

## Конкретный внутренний контракт

Проектный модуль `application/worldData/pack/encoding/jsonDecodeBudget.py` объявляет `JsonDecodeLimitError(ValueError)` без полей и публичного enum. Единственная причина его выдачи — установленное превышение max_bytes/max_nodes/max_depth/max_items из существующего DecodeLimits. Неверная конфигурация, синтаксис, payload schema и Python programming errors этим типом не обозначаются. Новые limits POJO и публичный Pack refusal не создаются.

Внутренний `JsonDecodeBudget` создаётся на один payload decode и захватывает validated DecodeLimits. Метод `check(payload: bytes) -> None` проверяет decoded JSON bytes до вызова полноценного JSON parser. Это локальный изменяемый счётчик одного вызова, не shared singleton, публичный input или persisted state. Для обычного JSON — один check; для settlement один экземпляр на header и все district frames. Bytes/nodes расходуются суммарно, depth/items проверяются для каждого контейнера; бюджет не сбрасывается на следующем frame. При отказе весь decode прекращается, частичный POJO не возвращается.

Семантика счётчиков фиксируется для проверки реализации: каждое JSON-значение, включая контейнер, — один node; ключ объекта учитывается в числе members контейнера, но не является отдельным value-node. Root container имеет depth=1, вложенный container увеличивает её на 1; scalar root не создаёт контейнер. max_items ограничивает число непосредственных элементов массива или пар объекта, включая повторные ключи до отдельной duplicate-key проверки. Проверка выполняется до допуска следующего узла/элемента. Равенство лимиту допустимо. max_bytes ограничивает суммарные переданные JSON bytes, включая whitespace; для zstd это уже распакованные bytes. Это не request encoded-IO budget.

Предварительный проход должен быть лексически корректным: различать строки, escape-последовательности и числа, не считать скобки/запятые внутри строк структурой, использовать явный ограниченный стек вместо рекурсии. Не строить dict/list всех значений и не превращать целиком вход в Python str ради подсчёта. Это структурный preflight, не новый semantic parser: окончательную проверку JSON и построение дерева выполняет parser конкретного binding. Preflight не нормализует числа/строки, не добавляет defaults, не отбрасывает ключи и не переписывает bytes. Его грамматика должна согласовываться с parser; расхождение на ранее допустимых значениях — дефект, а не новое правило формата.

После успешного check выполняются существующий/согласованный JSON parse, duplicate-key admission там, где он требуется, и owning schema validation. Повреждённый JSON остаётся ошибкой payload. Если бюджет исчерпан раньше проверки остатка, возвращается limit без утверждения, что остальные bytes корректны. Нельзя получать limit из текста JSONDecodeError, RecursionError, MemoryError либо generic ValueError. DecodeLimits.field_sizes относятся к typed owning collections и не выводятся из произвольного JSON-имени поля; explicit schema cardinality не становится resource overflow.

## Mapping и обязанности

PackPartReadOperation ловит JsonDecodeLimitError до общего ValueError и выдаёт существующий BUDGET_EXCEEDED. Pure helper не знает pin/publication/address. Final prepare использует собственный контракт ошибки с той же причиной, не read refusal. Storage callbacks и codec wrappers сохраняют подтип; не оставляют обход через прямой неограниченный loads. Decode/validate typed-модели различаются: validate не может проверить исходные JSON bytes или повторные ключи, которых в экземпляре уже нет.

JsonDecodeBudget владеет только счётчиками и структурным preflight; I/O, schema/defaults, registry lookup, генерация и выбор следующей операции — нарушение его ответственности. Payload decoder владеет parse/schema; read/prepare владеют контекстом и mapping. Численные caps и их источник конфигурации этим документом не назначаются.

## Приёмка и предел гарантий

Нужны граничные проверки cap/cap+1 для bytes/nodes/depth/items; строки со скобками, escaped quotes/backslashes и Unicode; несколько settlement frames с общим остатком; oversized структура до вызова loads; malformed JSON не классифицируется по тексту исключения; один результат resource mapping через storage/read/prepare; сохранение defaults и числовой семантики каждого payload. Обязательна сравнительная проверка preflight с выбранным parser на поддерживаемом JSON, включая скаляры, пустые контейнеры и числа. Тесты здесь не запускались.

Byte/structure caps ограничивают размер работы, но не являются точным измерением heap или CPU. Не объявлять RAM-бюджет доказанным без измерений parser/model expansion. Реализация preflight, подключение всех callers и конфигурация остаются OPEN; проект сигнала конкретизирован без повторного выбора публичных ошибок.
