# Pack: bounded zstd output для существующего формата

Статус: PROJECT, REV-02. Runtime не изменён; проведены небольшие in-memory проверки установленной библиотеки, без записи fixtures. Дополняет [budget accounting](pack-read-budget-accounting.md) и [resource-limit mapping](pack-read-resource-limit-signal.md).

## Доказательства и выбор механизма

[requirements.txt](../../backend/requirements.txt) задаёт `zstandard>=0.22.0`; локально `backend/.venv` содержит 0.25.0, backend cext. Это проверенная среда, не lock всех deployment. [TileCodec](../../backend/app/application/worldData/pack/io/tileCodec.py) использует default ZstdCompressor.compress(bytes), который записывает content size. Decoder вызывает одношаговый decompress без max_output_size. [Settlement frames](../../backend/app/application/worldData/pack/io/packBlobWire.py) создаются тем же compressor, каждый record отдельно.

Локальные наблюдения на payload из 10 bytes:

| Случай | Результат existing API |
|---|---|
| Известный content size, decompress(max_output_size=3) | Вернул 10 bytes: параметр сам по себе не ограничил output |
| Frame без content size, обычный decompress | ZstdError; current reader такой frame не принимает |
| Обрезан последний байт известного frame, обычный decompress | ZstdError |
| Тот же обрезанный frame через stream_reader | Вернул 9 bytes, затем пустой read; это не доказательство полного frame |
| Полный frame + произвольный хвост либо второй frame | Existing decompress вернул только первые 10 bytes |

[Официальная документация API](https://python-zstandard.readthedocs.io/en/0.25.0/decompressor.html) описывает одношаговую проверку полного frame, отдельный режим unknown content size, trailing-data policy и ограничение window. Не подменять проверку завершённости frame одним EOF streaming reader.

**Проект:** использовать header preflight и existing one-shot decompression для уже принимаемых frames с известным размером. Новый streaming маршрут и поддержка unknown-size frames для этой задачи не нужны. Никакой второй версии формата/codec не вводится.

## Конкретная реализация в плане

Изменить существующий pure `TileCodec.decompress(data: bytes, *, max_output_bytes: int) -> bytes`; обязательный budget без неограниченного default. Аналогично `TileCodec.decode` передаёт явный cap. Это target signature для миграции callers, не утверждение о готовности текущего кода.

1. Проверить аргументы; некорректный budget — ошибка входа, не исчерпание бюджета корректного запроса.
2. Получить `zstandard.get_frame_parameters(data)` и content_size. Повреждённый header и CONTENTSIZE_UNKNOWN не являются budget overflow; неизвестный размер остаётся отвергнутым, как у current reader.
3. Если известный content_size больше доступного max_output_bytes, отказать **до** decompression. Внутренний `ZstdOutputLimitError(ValueError)` в `io/tileCodec.py`, без новых полей/публичного enum, обозначает только этот установленный overflow. Нулевой остаток допустим внутри settlement accounting: он допускает только нулевой output, который затем проходит обычный JSON admission.
4. Выполнить existing one-shot decompression с явно закреплёнными `read_across_frames=False, allow_extra_data=True`; проверить равенство фактической длины заявленной и её соответствие budget, затем JSON parse. One-shot проверяет полноту frame; header сам по себе не доказывает валидность body. Не переводить любой ZstdError в budget, не разбирать текст исключения.

Trailing data policy здесь сохраняет наблюдаемое поведение. Запрет хвоста/concatenated frames был бы отдельным ужесточением формата и не включается молча в исправление бюджета. Проверки hash/nbytes охватывают весь сохранённый ArtifactRef, даже если decoder использует первый frame.

ZstdOutputLimitError относится к compressed decoder; CanonicalDecodeLimitError — к canonical TLV. Это разные внутренние причины, не зеркальные public result POJO. `PackPartReadOperation` ловит конкретный output-limit signal до generic ValueError и формирует existing BUDGET_EXCEEDED; malformed zstd/JSON — INVALID_* соответствующей роли. Decoder не создаёт pin/publication refusal и не делает IO.

## Settlement и остальные callers

[Concrete budget wiring](pack-decoder-budget-wiring.md) связывает climate storage admission, candidate validation и read через один configured ClimateFieldCodec и точный экземпляр ArtifactFormatContract. Число/поле persisted configuration остаётся OPEN; не заменяется default.

В `_parse_frames` держать один локальный остаток output budget для header и всех district records. Каждому decompress передавать остаток; вычитать размер успешно полученных bytes до обработки следующей записи. Prefix nbytes ограничивает compressed slice, не заменяет content_size preflight. Порядок header → districts и существующий порядок наложения сохраняются; ничего не сортировать, не распараллеливать и не сбрасывать budget на каждом record.

В legacy single-frame settlement ветви применяется тот же per-artifact cap; решение о её удалении остаётся в legacy migration. Map tile/fine terrain/climate используют тот же ограниченный TileCodec; отдельные копии decoder не создавать. JSON parse и последующее построение immutable POJO происходят только после ограниченной распаковки. Structural schema checks и расходы памяти моделей остаются отдельными требованиями.

[Climate format](../../backend/app/application/worldData/pack/encoding/climateFieldFormat.py) сейчас вызывает decode также при artifact encode/admission. Исправить только read_part недостаточно: cap должен быть явно доступен этому format binding и всем callers TileCodec. Источник/числа caps ещё OPEN; не выводить их из compressed size, LRU или размера мира. [Settings disposition](pack-settings-crud-disposition.md) не переоткрывается.

## Ограничения и приёмка

Известный ограниченный content_size ограничивает output buffer одношаговой распаковки; это не утверждение о полном RAM bound. Window decoder, copies и JSON/POJO allocation требуют отдельного контроля. `get_frame_parameters` предоставляет window_size, но численное ограничение window и его binding здесь не назначены. Не выдавать реализацию output cap за закрытую приёмку памяти процесса.

Нужны реализационные проверки на поддерживаемых версиях/backend: cap и cap+1, сильно сжимаемые данные, ложный declared size, truncated/checksum corruption, unknown-size, empty frame, trailing bytes, несколько settlement records с суммарным overflow; выход отказа до JSON parse; тип исключения сохраняется через format adapters. Локальные probes выше не заменяют эти тесты и измерения peak RAM.

Владелец pure codec — Pack; wrapper делегирует одной read-операции, DAG выбирает следующие операции. Новых публичных pipelines/CRUD/settings POJO и вызовов Source/Cache/producer нет. Порядок sources → evidence → manifest → codec/readers сохраняется. Реализация, caller migration, численные output/window caps и приёмка по всем критериям ещё OPEN; этот документ конкретизирует механизм, а не объявляет Pack готовым.
