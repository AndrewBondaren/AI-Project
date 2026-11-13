# Pack read: внутренний сигнал resource limit

Статус: PROJECT, REV-02; только проект изменения, не реализованный или принятый код. Дополнение к [budget accounting](pack-read-budget-accounting.md) и [матрице отказов](pack-part-read-error-mapping.md).

## Подтверждённый trace

[boundedCanonicalDecode](../../backend/app/application/encoding/boundedCanonicalDecode.py) теряет различие в конкретных местах:

- `_reader`: одной проверкой объединены неверный тип bytes и превышение max_bytes.
- `_Reader.header`: depth/node caps дают обычный CanonicalEncodingError.
- `_Reader.collection`: `min(high, max_items)` и fixed tuple width объединяют schema cardinality и resource cap.
- `_Reader.typed`: неверная граница пары объединена с `max_items < 2`.
- `_Reader.record`: max_items для ширины record даёт обычный CanonicalEncodingError.
- `validate_bounded` и `decode_bounded`: `except (ValueError, ...)` повторно создаёт CanonicalEncodingError. Подтип от него тоже будет пойман, поскольку [CanonicalEncodingError](../../backend/app/encoding/canonicalCodec.py) наследует ValueError.

[Hydrology packCodec](../../backend/app/application/worldData/generators/hydrology/encoding/packCodec.py) вызывает эти функции непосредственно и сам не перехватывает исключения. Existing `DecodeLimits` и `RecordLimits/CollectionLimit` уже содержат необходимые ограничения; новые зеркальные limits POJO не нужны.

## Конкретное изменение encoding, предлагаемое к реализации

В `application/encoding/boundedCanonicalDecode.py` определить `CanonicalDecodeLimitError(CanonicalEncodingError)` без новых полей/enum. Его единственная ответственность — обозначить достоверное превышение resource cap bounded canonical decoder. Это внутренний exception, не публичный Pack result, не canonical wire POJO и не новая версия контракта. Existing catch CanonicalEncodingError сохраняет совместимость; Pack может различить подтип раньше общего catch.

В обеих функциях `validate_bounded`/`decode_bounded` перед общим обработчиком поставить `except CanonicalDecodeLimitError: raise`. Не восстанавливать причину из message или цепочки generic ошибок задним числом.

Разделить условия: неверный bytes type, TLV boundary, fixed tuple width, explicit CollectionLimit minimum/maximum, unknown type и неканоническая форма остаются CanonicalEncodingError. Превышение DecodeLimits max_bytes/max_nodes/max_depth/max_items выдаёт новый подтип. При одновременном достижении explicit schema cardinality и max_items сначала проверяется уже известное нарушение схемы; если ресурс закончился раньше возможности проверить остальное, возвращается resource limit без дальнейшего разбора. Это не утверждение валидности оставшихся bytes.

Численные caps, формат, порядок двух проходов и проверка canonical re-encode не меняются. Этот сигнал не является бюджетом совокупного CPU двух проходов. Некорректная конфигурация самого decoder не должна маскироваться под исчерпание бюджета корректного запроса.

## Mapping в Pack и границы применимости

`PackPartReadOperation` до общего catch CanonicalEncodingError переводит CanonicalDecodeLimitError в существующий `PackPartReadRefusal(reason=BUDGET_EXCEEDED)`. Обычная ошибка canonical admission получает INVALID_MANIFEST/INVALID_INDEX/INVALID_PAYLOAD по роли объекта. Публичный DTO отказа остаётся один; внутренний exception описывает причину decoder, а refusal — исход конкретной Pack-операции с pin/publication/address.

Для request encoded budgets новая exception-иерархия не нужна: операция сама проверяет descriptor против остатков до backend IO и формирует existing refusal при установленном превышении. Generic ValueError backend не переводить в budget по догадке.

[OpenWaterBlobReader](../../backend/app/application/worldData/pack/spatial/openWaterBlobReader.py) уже различает `ref.nbytes > format cap` как SOURCE_CORRUPT и превышение caller budget как RESOURCE_LIMIT. Не менять это публичное поведение автоматически. Invalid format size и request budget — разные основания; proposed Pack mapping не должен принимать любой oversized descriptor за корректный payload с малым бюджетом. SOURCE_UNAVAILABLE по-прежнему не содержит достаточных сведений для полного Pack mapping.

CanonicalDecodeLimitError нельзя применять к zstd/JSON: это иной decoder. [Zstd output binding](pack-zstd-output-binding.md) конкретизирует header preflight перед existing one-shot decoder и внутренний ZstdOutputLimitError; generic zstd exception не означает исчерпание бюджета. Реализация, численные caps и caller binding ещё OPEN.

## Ответственность и приёмка

Encoding владеет pure decoder и сохранением причины; Pack — mapping своей read-границы. Новых публичных операций, CRUD, settings, orchestration или прямых междоменных публичных вызовов нет. DAG по-прежнему выбирает последующий шаг. Нет копии DecodeLimits или PackPartReadRefusal, нет изменения утверждённого порядка sources → evidence → manifest → codec/readers.

До закрытия нужны реализация и проверки: отдельные byte/depth/node/item caps в обеих функциях; сохранение подтипа через wrappers; fixed tuple/explicit collection bounds остаются schema errors, включая совпадающие caps; malformed input не становится budget по одному тексту; legacy catch базового типа продолжает работать; Pack map учитывает роль объекта. Нужен caller audit при реализации, включая legacy spatial adapters, которые могут снова объединить причины. Тесты не выполнялись: runtime не менялся. Общая приёмка Pack и зstd output binding этим проектом не закрыты.
