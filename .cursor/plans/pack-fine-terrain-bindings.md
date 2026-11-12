# Pack fine terrain — общий payload, разные адресные проверки

Статическая сверка 2026-11-12. Две роли из [инвентаря Pack](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12): wilderness_chunk и location_terrain. Runtime/SQL/shared-модели не менялись; тесты не запускались. Область — конкретизация собственного Pack admission/read, без миграции чужих callers.

## Общая часть формата

Оба writer пути сериализуют existing `dataModel/worldPack/wire/fineTerrainChunkWire.py::FineTerrainChunkWire(cx, cy, chunk_columns, columns)` через `packBlobWire.fine_terrain_chunk_payload` и TileCodec с PAYLOAD_KIND_FINE_TERRAIN. Оба reader пути проверяют тот же kind и вызывают parse_fine_terrain_chunk_payload. Внутри columns — FineTerrainColumnWire(lx, ly, runs, system_facing, system_grade_uid, region_uid), внутри runs — FineTerrainZRun(z0, z1, system_terrain, system_material). Новые зеркальные WildernessPayload/LocationPayload не нужны.

В payload нет world_uid, location_uid, macro gx/gy, TerritoryVolume и ArtifactRef. Он leaf по storage closure. system_grade_uid/region_uid и строковые registry keys не являются storage refs; необходимые зависимости использования хранятся в provenance. Owning model/codec не получают live Source/registry reader. Общий storage descriptor/typed payload decoder допустим для обеих ролей, но admission конкретного адреса зависит от роли и metadata той же закреплённой версии.

## Wilderness: координаты chunk

`FineChunkPersist.persist_rect` вычисляет cx/cy через tile_local_chunk_indices; origin — wilderness_chunk_origin(fine_bbox, cx, cy, chunk_size). В payload попадают wilderness клетки после partition. Колонки получают lx=cell.x-origin_x, ly=cell.y-origin_y. Для этого пути grid size берётся из captured header terrain_chunk_columns; крайние пределы — пересечение chunk с tile по §6.7 основного appendix, а не требование полного C×C payload.

Pack сверяет payload cx/cy с адресом wilderness_chunk и chunk_columns с принятой сеткой; проверяет локальные координаты с учётом обрезанного края. Sparse columns допускаются. World-coordinate resolution использует captured manifest, не latest World. Existing `MapCellQueryFacade._layers_at` использует world_map_cell_span(world)/terrain_chunk_columns(world) — это caller миграции, не образец чтения pinned версии и не задача менять его сейчас в этом срезе.

## Location: координаты territory

`FineChunkPersist.finish` (участок flush location cells) вызывает cells_to_fine_terrain_chunk с cx=cy=0, chunk_columns=ctx.chunk_size, origin=(volume.x0, volume.y0). Все накопленные клетки данной локации попадают в один payload, не в отдельные grid chunks. `WorldPackWriter.write_location_terrain` сохраняет полный payload и TerritoryVolume в manifest entry. `MapCellQueryFacade._layers_at` сначала проверяет volume.contains(x,y,z), затем передаёт в fine_terrain_contribution `(x-volume.x0, y-volume.y0)`.

Следовательно, chunk_columns здесь не ограничивает ширину/высоту location payload. Пример допустимой геометрии producer: C=32, volume.x0=100, volume.x1=199, cell.x=150 → lx=50. Общий валидатор lx<C ошибочно отвергнет эту клетку. Для location admission используются inclusive размеры captured TerritoryVolume: 0<=lx<=x1-x0, 0<=ly<=y1-y0; границы z соотносятся с тем же volume. Pack не вычисляет territory заново из live location или policy defaults.

cx=cy=0 — подтверждённая convention текущего producer; existing low-level reader её не проверяет. Общая схема FineTerrainChunkWire должна оставаться пригодной для wilderness с ненулевыми cx/cy. Превращение location convention в strict role-admission отмечается отдельно при freeze, а не добавляется в shared validator как универсальное ограничение. Равенство chunk_columns и header для location также не использовать как замену territory bounds: происхождение значения подтверждено для просмотренного producer, геометрический смысл отличается от wilderness.

## Runs: сохранить существующую семантику

`_compress_z_runs` сортирует исходные клетки по z и объединяет последовательные равные terrain/material. Однако existing FineTerrainZRun не запрещает z0>z1; `terrainContributions.fine_terrain_contribution` и column_surface используют min/max. При пересечении runs contribution выбирает первый подходящий run, при повторе колонок — первую подходящую column. Поэтому сортировка/слияние runs при decode может менять результат. Нельзя молча вводить z0<=z1, запрещать пересечения или исправлять их только на основании нормального выхода producer. Codec сохраняет порядок и данные; возможное ужесточение конфликтующих runs требует owning решения. Принятая проверка уникальности columns для целевого wilderness admission остаётся отдельно от исторической permissive read-семантики.

read_part возвращает материализованное дерево runs, не раскрывает каждый z в клетку и не вызывает FineTerrainZRun.cells. Byte budget распаковки не является ограничением длины числового z-интервала; полный разворот — другая операция с собственной ответственностью. Пустые columns встречаются в existing writer/reader tests и не объявляются повреждением сами по себе. Полнота определяется coverage, Pack не дописывает defaults.

## Реализация binding и приёмка

### Конкретный FineTerrainDecoder

Проектный класс `FineTerrainDecoder` в `backend/app/application/worldData/pack/encoding/fineTerrainFormat.py` реализует PackPartPayloadDecoder[FineTerrainChunkWire]. Constructor фиксирует registered codec version и existing DecodeLimits; encoded cap находится в общем binding. Методы: `decode(payload: bytes, format_version: FormatVersion) -> FineTerrainChunkWire`, `validate(value: FineTerrainChunkWire) -> FineTerrainChunkWire`. Один экземпляр/profile используется для wilderness_chunk и location_terrain и при read/final prepare. Новые WildernessPayload/LocationPayload либо копия FineTerrainColumnWire не создаются.

Порядок: формат/версия → точный header TileCodec с PAYLOAD_KIND_FINE_TERRAIN → bounded decompression → bounded strict JSON → owning immutable POJO. Не читать Source/World и не вычислять geometry в decoder. Exact registered storage/read descriptors берутся из [общего roster](pack-payload-binding-roster.md); версии manifest не заменяют codec version.

| Общий элемент | Правило decode/validate |
|---|---|
| Корень | Обязательные cx, cy, chunk_columns, columns. Extra/duplicate JSON keys отвергаются до потери данных |
| cx/cy | Exact int, не bool/float/string. Соответствие logical address проверяется отдельно; глобальный запрет nonzero cx/cy сломал бы wilderness |
| chunk_columns | Exact int >=1 по существующей модели; не универсальный bound координат location |
| columns | Обязательный JSON array → tuple[FineTerrainColumnWire, ...]. Порядок и пустой набор сохраняются; missing columns не становится empty |
| Колонка | Обязательные lx, ly, runs; lx/ly exact int, optional fields/defaults по единственной owning декларации. Новые числовые/UID ограничения по именам полей не вводятся |
| runs | Обязательный array → tuple[FineTerrainZRun, ...]; порядок и явно пустой набор сохраняются. Не сортировать, не сливать и не расширять в отдельные z-клетки |
| Run | Обязательные exact integer z0/z1 и owning string system_terrain; system_material nullable/default по модели. Обратные endpoints и пересечения не запрещаются общим decoder |
| system_facing | Каноническое значение существующего Facing либо null на JSON-границе; missing использует owning default. Не приводить произвольное значение через str и не принимать alias/empty вместо канонического значения |

Для deeply immutable output адаптируются единственные owning FineTerrainChunkWire.columns и FineTerrainColumnWire.runs к tuple со strict nested admission; не создавать параллельное дерево StrictFineTerrain*. Это целевое изменение представления коллекций, а не разрешение слепо изменить shared callers. До cutover проверяются producer constructors/serializers и consumers. `validate` проверяет реальные значения forged instances; frozen верхнего объекта не делает существующие lists неизменяемыми. Python instances уже содержат owning Facing, wire strings допускаются только на decode-границе.

### Контекстная проверка двух ролей

Эти проверки выполняет Pack admission над decoded T, адресом и metadata закреплённой версии. Они не меняют значение и не являются новыми публичными стадиями DAG.

| Роль | Проверка |
|---|---|
| Wilderness | payload cx/cy совпадают с PackChunkAddress; chunk_columns согласован с captured terrain_chunk_columns; lx/ly находятся в обрезанном tile/chunk footprint из §6.7 Pack; принятая уникальность columns проверяется до построения lookup map. Sparse/empty не запрещаются без coverage requirement |
| Location | lx/ly проверяются по inclusive TerritoryVolume, не по C; origin берётся из volume.x0/y0 закреплённой metadata. cx=cy=0 фиксируется как существующая producer convention, но новый универсальный strict запрет других значений не добавляется только ради reuse wilderness validator |
| Обе | Нет world_uid/location_uid/gx/gy в bytes — этих полей не выдумывать. Address/provenance обеспечивает связь с частью. z-интервалы сохраняются; clipping к territory или переписывание endpoints в decoder запрещены |

Различие проверок уникальности также не скрывать в shared schema: существующий contribution использует первую совпавшую колонку. Принятый unique-columns invariant wilderness нельзя автоматически расширить на location без отдельного основания. Общий decoder не превращает список колонок в dict с last-wins. Если будущий role contract отклоняет дубли, он делает это явно до потери порядка.

Отказы соответствуют общему read mapping: unsupported contract/format — CONTRACT_MISMATCH; malformed envelope/JSON/fields и нарушение принятого role admission — INVALID_PAYLOAD; превышение бюджета — BUDGET_EXCEEDED. Decoder не создаёт pin/publication refusal; read operation добавляет контекст. Infrastructure/cancellation не маскируются payload ошибкой. Root refs и source closure не извлекаются из строк system_grade_uid/region_uid.

Проверки реализации: один payload проходит общий decoder для обеих ролей; location с C=32/lx=50 и подходящим territory не отклоняется; тот же lx за wilderness footprint отклоняется role admission; reverse z0/z1 и intersecting runs сохраняются в исходном порядке; большой z-интервал не выделяет массив клеток; missing array отличается от empty; explicit invalid facing не нормализуется в None; forged mutable nested instance отклоняется; read/prepare используют одинаковый decoder/profile. Это проект классов/правил, не выполненные runtime тесты.

Предлагаемый Pack-owned модуль `application/worldData/pack/encoding/fineTerrainFormat.py`: один pure decoder общего формата → existing FineTerrainChunkWire; storage остаётся ArtifactFormatContract[bytes], BLOB. Внутренний read registry допускает обе address-роли для одного payload contract. Контекстные проверки address/header/territory выполняются Pack admission над уже декодированным значением и pinned metadata, не через IO внутри codec. Точные format/read descriptors, budget и error port пока не зарегистрированы; их наличие не заявляется.

Existing root/column содержат list, все три модели используют extra=ignore, числовые поля допускают coercion, facing before-validator приводит значения. Поэтому existing decoder не закрывает deep immutable/strict read. Адаптация единственных owning моделей и shared validators требует согласованной миграции; этот документ не разрешает менять интегрированные пути других доменов или создавать второе дерево POJO. Действующий TileCodec также не обеспечивает требуемый предел decompressed output; bounded decoder и memory expansion остаются приёмочными проверками, как для map_tile.

Общие проверки: точный descriptor/header/kind, byte limits до parse/распаковки, неизвестные поля и ошибочные типы, immutable возвращаемое дерево. Ролевые проверки: wilderness address/grid/edge bounds; location captured territory и отсутствие ошибочного chunk-size clamp. Malformed payload — existing INVALID_PAYLOAD, budget overflow — BUDGET_EXCEEDED, unsupported binding — CONTRACT_MISMATCH; отсутствие blob/hold не ABSENT. Field/logic ошибки должны использовать owning типы без копирования enum/полей — конкретный port остаётся в общем gate read bindings.

Приёмочные сценарии: wilderness nonzero cx/cy; крайний обрезанный chunk; location шире C с lx>=C; negative world origin; sparse/empty payload; одинаковые bytes на двух logical addresses с отдельным provenance; обратные endpoints run с сохранённой existing семантикой; сохранение порядка runs; pinned read после изменения latest world; compressed-size/decompressed-size limit; отсутствие expanded z-cell allocation. Здесь перечислены требования, не результаты исполнения. Две роли конкретизированы; implementation/полная приёмка binding остаётся OPEN.
