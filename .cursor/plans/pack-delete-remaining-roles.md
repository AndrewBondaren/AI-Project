# Pack — удаление оставшихся payload-ролей и итоговый roster

2026-11-12. Статическая сверка, только документация. Runtime/SQL/DAG не менялись; тесты не запускались. Основание: [delete_part](pack-delete-part-contract.md), [payload roster](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12) и соответствующие binding traces.

## Контракт переиспользуется без новых методов

Для climate_coarse, locations_index, spatial_root, tile_grade_slots и location_grade_slots достаточно существующего проекта `PackPreparationService.delete_part(request: PackDeletePartInput) -> PackPreparationState`. Класс — application/worldData/pack/preparation/packPreparationService.py; input — dataModel/worldPack/preparation/operations.py; state — preparation/state.py; named адреса — preparation/addresses.py. Request содержит state и address, не флаг поведения или команду запуска другой операции. Ошибки и strict admission остаются общими по delete_part.

В каждом случае локальный эффект одинаков: исключить только адресованный PackStoredPart вместе с его provenance; сохранить assembly, assembly_provenance и остальные parts. Нет подтверждённого отдельного metadata-эффекта, требующего нового публичного метода. Финальные ролевые проверки выполняются отдельным admission и не превращают delete_part в dispatcher workflow. Отсутствующий адрес — предложенный ранее no-op после валидации state, а не доказательство допустимости всей новой версии.

## Пять адресов и финальные ограничения

| Роль / тип address | Подтверждённая граница | Что требуется до READY |
|---|---|---|
| climate_coarse / PackCoarseClimateAddress | [write_climate_coarse](../../backend/app/application/worldData/pack/io/worldPackWriter.py) не изменяет fine tiles. [Read projection](../../backend/app/application/worldData/pack/climate/climatePackApply.py) сохраняет заполненные поля view и использует coarse только после fine для недостающих значений | Scope/coverage допускают отсутствие coarse. Fine refs и tile statuses не сбрасываются, новый absent-status не вводится. Само слово coarse не доказывает наличие BLOB; нет генерации/заполнения defaults или запроса latest |
| locations_index / PackLocationsIndexAddress | [Pin trace](pack-locations-index-binding.md): индекс позиционный, L0 pins не равны roster L2 terrain/settlement | Ни один сохранённый map_tile не должен иметь используемый location_pin без соответствующего индекса этой версии. Отсутствие pin-зависимостей — необходимая, не достаточная проверка: scope и другие принятые зависимости также проверяются. Pack не перенумеровывает клетки и не удаляет исходные локации |
| spatial_root / PackSpatialRootAddress(domain) | [Spatial trace](pack-spatial-root-binding.md): root-part отдельный; shards входят в transitive closure, [PinnedSpatialReader](../../backend/app/db/repositories/sqlite/worldPack/pinnedSpatialReader.py) проверяет достижимость из pinned manifest | Отсутствие domain root допустимо по scope; полный closure учитывает все оставшиеся parts/proofs. Нельзя удалить общий shard из holds только по исключению одного root. Новый pin не получает право открыть чужой shard по вручную переданному ref, прежний pin сохраняет свой доступ |
| tile_grade_slots / PackTileGradeSlotsAddress(gx,gy) | [Grade trace](pack-grade-slots-bindings.md): отдельный payload, без собственного assembly status | Coverage допускает отсутствие. Terrain/chunks/statuses не меняются; коды не восстанавливаются из z, отсутствующих соседей или старого rays-представления |
| location_grade_slots / PackLocationGradeSlotsAddress(location_uid) | Тот же GradeSlotSidecar, world XY; location terrain/settlement — отдельные parts | Те же ограничения coverage плюс принятые связи с location identity. Удаление sidecar не удаляет location metadata, terrain, settlement или pins |

Запрет READY при dangling location_pin следует уже принятому final index admission. Legacy [pin_at](../../backend/app/application/worldData/render/pack/locationPinOverlay.py), возвращающий None при отсутствии/выходе за диапазон, не является разрешением сохранять такую версию. Аналогично [grade loader](../../backend/app/application/worldData/pack/io/gradeSlotSidecar.py), возвращающий пустой tuple для отсутствующего файла/чужой схемы, не заменяет target absent/refusal контракт.

Для всех ролей различаются три состояния: адрес отсутствует; адрес указывает на валидный пустой payload, если owning схема его допускает; адрес заявлен, но bytes недоступны/повреждены. Только первое выражается delete_part. Второе требует отдельного готового artifact и write-операции. Третье — read/admission отказ, а не silent absence.

## Согласование связанных изменений

Если retained map_tile ссылается на индекс, delete locations_index в промежуточном state ещё не означает незаконную операцию над опубликованным миром: финальный prepare обязан отклонить незавершённый состав. Для допустимого результата DAG передаёт отдельные готовые изменения соответствующих частей. Pack не запускает producer, не дополняет отсутствующий индекс и не придумывает порядок новых нод.

Удаление coarse при сохранённом fine не создаёт прямую зависимость delete от Climate. Удаление root не вызывает Hydrology. Удаление grade не запускает relief validator/generator. Независимые source/provenance dependencies продолжают удерживаться, когда они требуются оставшимся составом. Physical release/GC и отмена/освобождение кандидата остаются отдельными контрактами.

## Итоговый roster удаления всех 10 payload-ролей

| Операция проекта | Роли | Обоснование |
|---|---|---|
| delete_part | map_tile, climate_coarse, locations_index, spatial_root, tile_grade_slots, location_grade_slots | Меняется только part и его встроенный provenance; для map_tile есть отдельный [trace](pack-delete-map-tile-trace.md), для пяти остальных — таблица выше |
| delete_wilderness_chunk | wilderness_chunk | [Payload + chunk metadata/proof + provisional tile status](pack-delete-wilderness-chunk-contract.md) |
| delete_fine_climate | climate_fine | [Payload + согласование tile climate status](pack-delete-fine-climate-contract.md), без генерации coarse |
| delete_location_terrain | location_terrain | [Payload + owning location metadata/proof](pack-delete-location-representations.md), без удаления settlement/pins/source |
| delete_settlement_structure | settlement | [Payload + owning settlement metadata/proof](pack-delete-location-representations.md), без удаления terrain/pins/source |

Generic delete_part может использоваться как промежуточное исключение адреса и для остальных ролей, но не заменяет их обязательные согласованные metadata-эффекты. Ролевые операции нужны для соответствующего завершённого локального перехода; final admission не ослабляется ради универсальности.

Metadata-only wilderness region index не является одиннадцатой payload-ролью. Его полная замена, включая пустой индекс, уже представлена replace_region_index и existing require_region_index. Это не каскадное удаление region paint из сохранённых terrain blobs. Не смешивать этот контракт, удаление source region и delete_part.

## Проверки и статус

Обязательные сценарии: coarse удалён при retained fine; индекс удалён при retained pin — final refusal; без используемых pins отсутствие индекса всё ещё проверяется по scope; shared shard переживает удаление root из нового состава; grade absence не превращается в synthetic slots; missing declared bytes не превращаются в absent; same artifact на другом адресе сохраняется; old pins читают старую версию; input state неизменен; ни одного I/O/публичного вложенного вызова из delete.

Классы и ошибки — общие из delete_part; новые POJO/enum/ports не добавлены. Сервис меняет state, validator проверяет local/final инварианты, preparation operation выполняет verified lifecycle, assembler строит конечный manifest. Три запрета DAG и порядок источники → evidence → manifest → codec/readers сохраняются.

Статус после сверки 2026-11-13: распределение операций удаления по всем 10 payload-ролям конкретизировано на уровне PROJECT и сведено в [CRUD-таблицу](pack-data-crud-roster.md). Metadata describe/bind и closed preparation diagnostic union уже описаны в write-плане; прежние ссылки на отсутствие этих DTO устарели. Это не CLOSED всей приёмки D: остаются concrete scope/coverage evidence, bounded read/closure bindings, полная semantic матрица ошибок и runtime проверки. Отсутствие сведений не заменяется successful default.

Сверка связанных эффектов: шесть ролей используют delete_part с удалением только part/provenance; wilderness удаляет также chunk metadata/proof и пересчитывает provisional status по прежней policy; fine climate согласует status с отсутствием fine без генерации coarse; terrain и settlement удаляют только собственные metadata/proof, сохраняя второе представление и pins. Ни один переход не снимает holds и не запускает следующую публичную операцию. Для изменённой сохраняемой metadata DAG использует describe_metadata → evidence владельца → bind_metadata_provenance; равенство одного status не доказывает применимость прежнего proof. Удалённая metadata не получает фиктивного нового proof: разрешённость удаления проверяется отдельно через scope/evidence финального состава. Внешний evidence mapping не подменяется этой сверкой; PACK-METADATA-PLANNING остаётся отложенным.
