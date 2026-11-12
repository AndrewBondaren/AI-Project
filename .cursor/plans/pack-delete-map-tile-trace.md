# Pack — удаление map_tile через существующий проект delete_part

2026-11-12. Статический trace и уточнение проекта; только документация, тесты не запускались. Связь: [delete_part](pack-delete-part-contract.md), [write-план](pack-v2-public-write-operations.md), [состав assembly](pack-v2-domain-contract-spec.md#64-состав-assembly-после-принятого-исключения-полей).

## Вывод: дополнительная операция не нужна

Удаление одного L0 payload выражается уже предложенным методом:

`PackPreparationService.delete_part(request: PackDeletePartInput) -> PackPreparationState`

В request.address передаётся existing проектный PackMapTileAddress(gx, gy), kind=map_tile; в request.state — текущий PackPreparationState. Class/module/input/result/error остаются из [контракта delete_part](pack-delete-part-contract.md). Новый delete_map_tile, PackDeleteMapTileInput, helper-service или дополнительный pipeline не требуются: специфического изменения metadata для этой роли не найдено.

## Основание в коде и целевой схеме

[WorldPackWriter.write_world_map_tile](../../backend/app/application/worldData/pack/io/worldPackWriter.py) обновляет world_map_path/hash выбранной tile row, сохраняет её chunks/statuses, устанавливает effective side и наполняет parent-light cache. `_upsert_tile` допускает существование tile row без world_map_path, в том числе для других записей. Отдельного legacy удаления L0 в writer нет; целевая delete policy не объявляется перенесённой реализацией.

В принятом проекте path/hash/ArtifactRef вынесены из assembly в parts. PackTileAssembly содержит только gx/gy, climate_status, wilderness_refine_status и chunks. Собственного L0 presence-флага в этой metadata нет. Следовательно, удаление map_tile part не требует удаления tile row, понижения climate или пересчёта wilderness status. Отсутствие L0 определяется по составу parts.

Header содержит effective grid scalars и last_l0_mode. Удаление последнего map_tile не означает пересмотр side/span, возврат defaults или смену последнего bake mode. Эти поля задаются соответствующими отдельными операциями; delete_part их не меняет.

## Точные эффекты и наблюдаемое поведение

- Удаляется только map_tile(gx,gy) и встроенный payload provenance. Остальные адреса с тем же ArtifactRef сохраняются.
- Tile metadata, её proof, все chunk metadata/proofs, fine climate, grade sidecar и другие части сохраняются. Удаление не производит новую tile projection. Сохранённые proof dependencies всё равно входят в общий final admission/retention; нельзя удалить требуемый source artifact из closure по одному отсутствию payload part.
- Locations_index и порядок pins неизменны. Удалённый tile больше не предъявляет своих location_pin references в новой версии, но это не разрешает перенумерацию индекса для остальных tiles.
- world_map_cells вычисляется по окончательным map_tile addresses и effective side в принятом общем расчёте; wilderness_chunks_baked не изменяется только из-за удаления L0. Ручной decrement и новый сохранённый counter не вводятся.
- Если адрес отсутствует — общий proposed no-op после strict проверки state, без создания либо удаления tile metadata. Даже tile row без оставшихся payload не очищается эвристически этим методом: удаление самой metadata — иной смысловой переход.

[PackRenderReadFacade](../../backend/app/application/worldData/pack/read/packRenderReadFacade.py) в legacy пропускает tile rows без world_map_path. [Loading progress](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py) считает tiles_ready по наличию path, а tiles_total по metadata rows. Target presence определяется map_tile part, не просто существованием tile row. После удаления одной L0 части готовность может уменьшиться при сохранённом числе metadata rows — нельзя «исправлять» это автоматическим удалением tile. Это trace наблюдаемой семантики, не утверждение, что текущие readers уже переведены на parts.

Target read_part для удалённого адреса возвращает typed absent, не пустой tile с defaults и не производный L0 из fine chunks. Missing/corrupt bytes заявленного ref остаются refusal. Исторический pin читает прежнюю версию независимо от удаления в новом state.

## Parent light и допустимость сохранения fine

Legacy writer кладёт ParentLightTile в cache, но pure delete_part не вызывает Cache или cache invalidation. При миграции потребителей отсутствие L0 в закреплённой версии не должно маскироваться старым path-keyed cache. Новый контракт producer/read обязан проверять точный pinned input; новый генераторный fallback внутри Pack не вводится.

[Принятый порядок detailed](pack-write-order-trace.md) содержит parent-light barrier. Удаление L0 не разрешает следующему producer запускать refine без нужного входа или переставлять эту стадию. Это проверка последующего маршрута DAG, не скрытый запуск rebuild из delete.

Нельзя автоматически объявить все уже сохранённые fine results недействительными только по удалению L0 part: их actual provenance/dependencies и покрытие проверяются отдельно. Если сохранённая зависимость требует bytes бывшего L0, они остаются в retention closure по этой зависимости. Если scope требует L0 address в конечном составе, prepare отклоняет удаление как missing required part/out-of-scope по фактической причине. Связь «каждому fine payload обязательно нужен присутствующий map_tile part» не вводится без owning contract.

## Приёмка

Проверки: удалить L0 при сохранённых chunk/climate/grade; все metadata/status/proofs и header scalars неизменны; counter пересчитан по parts; последний L0 не сбрасывает grid/mode; empty tile row не исчезает автоматически; same ref на другом адресе сохранён; старый pin читает прежний L0; отсутствие не скрывается cache/defaults; declared corrupt ref не становится absent; обязательные scope/provenance зависимости не теряются и не дают незаконный READY.

Ответственность классов и ошибки полностью наследуются от delete_part: один pure переход PackPreparationService, strict local validator, отдельный final admission PackPreparationOperation и assembler конечного manifest. Ни дополнительного доменного вызова, ни ветвления маршрута, ни запуска через callback/worker не добавлено. Порядок источники → evidence → manifest → codec/readers сохранён. Статус: необходимость отдельного delete_map_tile снята по trace; schema/error/scope/retention и production caller gates остаются в общих срезах.
