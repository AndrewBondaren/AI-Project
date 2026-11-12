# Pack grade slots — sidecar, merge и admission

Статический trace 2026-11-12 для tile_grade_slots и location_grade_slots из [инвентаря Pack](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12). Только документация; runtime не менялся, тесты не запускались. Решения [публичных write-операций](pack-v2-public-write-operations.md) сохраняются: Pack принимает полный готовый payload, не выполняет merge и не запускает grade producer.

## Подтверждённая цепочка

[FineChunkPersist._persist_grade_cell_slots / _write_grade_cell_sidecars](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py) вызывает [pack_cell_slots](../../backend/app/application/worldData/pack/refine/gradeCellSlots.py) для occupancy и height map. Затем producer разделяет клетки между wilderness tile и location через location_for_cell(x, y, z, location_pairs). Отсутствующий packed результат ничего не записывает; группы без incoming cells не очищаются.

[WorldPackWriter.merge_grade_cell_slots_tile / merge_grade_cell_slots_location](../../backend/app/application/worldData/pack/io/worldPackWriter.py) используют общий [merge_grade_slot_sidecar](../../backend/app/application/worldData/pack/io/gradeSlotSidecar.py). Он загружает существующий файл, вызывает merge_grade_cell_slots(incoming, existing) и записывает полный результат. Порядок first-wins на (x, y, position): incoming выше existing, внутри группы первая запись выше последующих. Клетки выдаются в порядке первого появления. Пустой incoming сохраняет существующие клетки; это не операция удаления.

В целевом пути producer получает точную pinned base, выполняет merge до передачи результата Pack. Чтение произвольного текущего файла по path не доказывает происхождение результата от captured base. Если base отсутствует, это должно быть явно отражено evidence; отказ чтения существующего ref не подменяется пустой базой. Pack write-операция не оркестрирует read → generate → merge и не вызывает публичную операцию другого домена. Управление операциями остаётся в DAG; новые ноды этим trace не вводятся.

## Общий payload и координаты

Owning POJO уже существуют в [gradeSlot.py](../../backend/app/dataModel/terrain/relief/gradeSlot.py): GradeSlotSidecar(schema_id, cells: tuple[GradeCellSlots, ...]), GradeCellSlots(x, y, slots: tuple[int, ...]). Для двух ролей используется одно тело, без второго location DTO. Enum-семантика остаётся GradeOctant/GradeSeam/GradeSheer/GradeCouple; единый новый enum вместо них не вводится.

По [locked body ТЗ](../../docs/tz_terrain_relief_consume.md#тело-sidecar-locked): compact JSON, schema_id=SCH-GRADE-CELL-SLOTS, x/y — world XY, ровно восемь кодов 0…10 в порядке NW N NE W E SW S SE. Это отдельный sidecar, не FineTerrain и не zstd raster. Историческое имя grade_rays.json не означает payload rays[]. В blob нет gx/gy, location_uid или z; logical address находится в manifest parts. Поэтому роль нельзя вывести только из payload.

Граница адреса проверяется с captured assembly/evidence. Для location принадлежность producer определяется XY+z, тогда как payload хранит только XY: нельзя заново доказать исходный split одним декодированием sidecar, назначить весь XY-overlap локации или придумать z из terrain. Tile/location используют world XY; не применять к ним chunk-local bounds. Требование равенства набора cells всем terrain columns из этой схемы не следует. Неизвестный completeness policy не закрывать совпадением counts.

## Чтение и найденное расхождение

[WorldPackReader.read_grade_cell_slots_tile / read_grade_cell_slots_location](../../backend/app/application/worldData/pack/io/worldPackReader.py) возвращают tuple через load_grade_slot_sidecar. Текущий path loader возвращает () для отсутствующего файла, не-object JSON или неизвестного/отсутствующего schema_id; синтаксически повреждённый JSON и невалидные slots вызывают ошибку. Это legacy поведение, не готовая политика artifact admission: отсутствующая часть, валидное пустое тело и повреждённый/неподдерживаемый заявленный artifact должны различаться. Missing declared ref нельзя считать пустым sidecar.

ТЗ требует уникальные world XY в файле. GradeSlotSidecar сейчас не проверяет уникальность cells, а [GradeSlotIndex](../../backend/app/application/worldData/render/gradeRayDump.py) при дублях перезаписывает предыдущее значение последующим. Merge, напротив, выбирает первое. **Pack admission должен отклонять duplicate XY**, выполняя существующее ТЗ, а не выбирать новую first/last policy для сохранённого тела. Decoder не исправляет и не дедуплицирует такой payload.

Модели frozen и содержат tuples, но extra=ignore и нестрогие int/defaults сохраняют permissive admission. Требуются явная проверка неизвестных полей на обоих уровнях и строгий wire-контракт целых кодов/координат; без зеркального POJO. Число slots и допустимый диапазон уже проверяются — переиспользовать. Политика отсутствующих schema_id/cells должна быть явной; текущий default в POJO сам по себе не означает приёмку неполного artifact body.

GradeSlotIndex.relative_to/restricted_to/without_couple создают производные render views, не новое persisted тело. Read не генерирует SEAM/COUPLE из z или omitted клетки. DEBUG_GRADE_SLOT_VALIDATE — существующий dev-проход с логированием, не доказательство production admission и не повод переносить генераторный occupancy validator внутрь Pack prepare.

## Binding, retention и приёмка

В просмотренном Pack encoding/composition registered ArtifactFormatContract для grade sidecar не найден. Уточнение по owning ТЗ при CRUD-сверке: проект descriptor уже задан — `dataModel/worldPack/meta/gradeSlotsStorageFormat.py`, key world_pack.grade_slots.json, storage version 1; `encoding/gradeSlotsFormat.py::grade_slots_format(max_bytes)` и `decode_grade_slots` для обеих ролей. Read descriptor — world_pack.grade_slots/version 1 в `dataModel/worldPack/read/gradeSlotsContract.py`. Повторно выбирать имена не требуется. Открыты реализация strict bounded JSON admission, явный budget, error mapping и composition. ТЗ уже требует unique cells/JSON keys и разрешает явно сохранённый empty cells; это не новые вопросы. Нужны ограничения памяти декодирования, не новый глобальный лимит мира.

Payload не содержит дочерних ArtifactRef. Сам sidecar ref входит в полный manifest retention set; captured base/provenance dependencies учитываются по общему контракту отдельно. Новые holder store, lifecycle или публичная операция merge внутри Pack не требуются. Порядок источники → evidence → manifest → codec/readers не меняется.

[test_grade_slot_sidecar.py](../../backend/tests/test_grade_slot_sidecar.py) содержит compact round-trip, legacy rays→empty и incoming-first merge; [test_pack_cell_slots.py](../../backend/tests/test_pack_cell_slots.py) — producer/model проверки. Это найденные тесты, не результат нового запуска и не evidence готового artifact binding.

Для приёмки: duplicate XY reject; invalid count/code/type/unknown fields; missing ref отдельно от valid empty; unsupported schema и broken JSON; bytes/collection budget; incoming-first с сохранением старых cells и пустым incoming; точная pinned base вместо latest; корректный tile/location address с world XY; сохранение slot order; read без генерации из z. Существующий legacy тест rays→empty не переносится автоматически в единственный целевой decoder.

Статус: payload/merge semantics и общие POJO подтверждены; strict bounded artifact binding, address/evidence admission и production wiring OPEN. Публичные CRUD и фактический DAG-путь принимаются по общему плану отдельно; этот trace не объявляет их реализованными и не блокирует доступную Pack-owned работу ожиданием миграции чужих callers.
