# Pack — удаление location terrain и settlement представлений

2026-11-12. PROJECT после статического trace; только документация, runtime/SQL/DAG не менялись, тесты не запускались. Связь: [write-план](pack-v2-public-write-operations.md), [delete_part](pack-delete-part-contract.md), [locations_index trace](pack-locations-index-binding.md).

## Подтверждённые границы

[WorldPackWriter.write_location_terrain](../../backend/app/application/worldData/pack/io/worldPackWriter.py) записывает terrain payload и отдельную LocationTerrainEntry с TerritoryVolume. `publish_settlement_structure` записывает другой payload и SettlementStructureEntry с отдельными territory/status/packed_district_uids. Одинаковый location_uid не объединяет эти записи. В writer не найдено отдельного метода их удаления; предложенные ниже правила не объявляются legacy parity.

[PackRenderReadFacade](../../backend/app/application/worldData/pack/read/packRenderReadFacade.py) отдельно проверяет наличие terrain/settlement. [SettlementStructureRaster](../../backend/app/application/worldData/pack/read/settlementStructureRaster.py) получает вклад только из settlement entries и соответствующего payload. Удаление представления прекращает его участие в новой Pack-версии; оно не является удалением исходной локации, topology, buildings, district entities или их SQL rows.

LocationsIndexWire содержит L0 pins, а не roster материализованного L2 terrain. Равенство UID-наборов не установлено. Позиция pin используется WorldMapCellWire.location_pin; исключение элемента из середины списка сдвигает позиции. Поэтому удаление terrain/settlement не изменяет locations_index и не переписывает map tiles автоматически. Если требуется изменение исходной локации и pins, соответствующие owning операции возвращают готовый результат через DAG; Pack принимает отдельный согласованный replace_locations_index и проверяет итоговые позиционные связи.

## Два конкретных метода

В проектном `PackPreparationService`, модуль `backend/app/application/worldData/pack/preparation/packPreparationService.py`:

| Метод | Input из dataModel/worldPack/preparation/operations.py |
|---|---|
| `def delete_location_terrain(self, request: PackDeleteLocationTerrainInput) -> PackPreparationState` | state: PackPreparationState; address: PackLocationTerrainAddress |
| `def delete_settlement_structure(self, request: PackDeleteSettlementStructureInput) -> PackPreparationState` | state: PackPreparationState; address: PackSettlementAddress |

State объявлен в preparation/state.py, адреса — в preparation/addresses.py. UID содержится только в address; ref/territory/status/список districts/флаги cascade не передаются. Input strict/frozen/extra=forbid, с повторной проверкой вложенных экземпляров. Имена отличаются по роли, но не дублируют shared payload или state POJO. Один generic метод с mode, запускающий разные публичные операции, не вводится.

Caller — прямой DAG-вызов конкретного метода. Методы синхронные и pure, не вызывают друг друга, delete_part, Source, producers, Cache, prepare или activate. DAG определяет необходимость удаления обоих представлений и порядок вызовов; метод не выбирает следующий шаг.

Ошибки — общие проектные PackPreparationError/PackPreparationIssue из `dataModel/worldPack/preparation/errors.py`; exception PackPreparationFailure из `application/worldData/pack/preparation/errors.py`. Structural diagnostics следует общему mapping write-плана, без зеркальных LocationDeleteError/SettlementDeleteError. Недопустимая специализация адреса отклоняется до изменения; дубли исходного state — DUPLICATE_ADDRESS. Runtime freeze общего error-контракта этим срезом не закрывается.

## Локальные эффекты

| Данные | delete_location_terrain | delete_settlement_structure |
|---|---|---|
| Part и его payload provenance | Исключить только location_terrain(uid) | Исключить только settlement(uid) |
| Metadata | Исключить PackLocationAssembly(uid) целиком | Исключить PackSettlementAssembly(uid) целиком, включая status и packed_district_uids |
| Metadata proof | Исключить запись PackLocationMetadataAddress(uid) | Исключить запись PackSettlementMetadataAddress(uid) |
| Второе представление того же UID | Settlement сохранить | Location terrain сохранить |
| Остальное | Сохранить locations_index, map tiles, chunks, climate, location_grade_slots, прочие metadata и provenance | То же |

Это предложенная семантика удаления целого Pack-представления. Она не равна переводу settlement status в absent при сохранении metadata row и не означает пустой district list в существующем payload. Если нужен такой иной сценарий, он должен быть отдельным согласованным изменением, не скрытым вариантом delete.

Алгоритм: проверить request/state; исключить адресованный part, соответствующую metadata row и её proof; вернуть immutable state. При частично собранном состоянии удалить все присутствующие компоненты именно этой тройки, не скрывая прочие нарушения. Если тройка отсутствует — предлагается no-op после проверки, без создания metadata. Вход не мутирует. Не удалять по UID все роли сразу и не удалять по совпадению artifact hash: разные адреса/владельцы могут использовать один ref.

Новая metadata projection вместо удалённой не создаётся, поэтому новый proof её значения не требуется. Удаление прежнего proof не является evidence разрешённости удаления: scope/coverage и происхождение изменения проверяются final prepare. Если оставшиеся projections или proof dependencies связаны с удалённым представлением, они должны пройти соответствующую финальную проверку; автоматическое переписывание их provenance не разрешено.

## Final admission, чтение и retention

Final prepare проверяет scope и допустимость отсутствия по coverage. Если обязательный terrain/settlement требуется текущим результатом, отсутствие отклоняется; исчезновение из state не считается достаточным разрешением. Проверяется отсутствие orphan metadata proofs и соответствие остальных parts/indexes. Точные foreign producer evidence остаются у владельцев, не создаются внутри Pack.

Location grade sidecar намеренно не удаляется каскадом: он отдельная роль с world XY и собственным provenance. Это не утверждение, что любой orphan sidecar допустим. Если принятый final контракт требует terrain для его использования, DAG должен явно передать согласованное изменение состава; до такой конкретизации допустимость оставшегося sidecar отмечается OPEN. Не расширять delete_location_terrain неявным обходом всех связанных частей.

[Повторный trace sidecar/terrain](pack-grade-slots-bindings.md) не выявил обязательного storage prerequisite из факта совместного чтения renderer. Producer debug validation тоже не является Pack admission. Поэтому условный gate выше не превращается в новый безусловный запрет хранения sidecar без terrain; нужен конкретный принятый scope/dependency контракт.

read_part возвращает отсутствие соответствующего адреса; не восстанавливает terrain/structure и не читает live source вместо удалённого представления. Legacy проверки filesystem exists/перехват FileNotFoundError не заменяют target read semantics: missing bytes заявленного ref — refusal, а не подтверждённое отсутствие части. Миграция consumers не входит в эти pure методы.

Старые manifests/pins сохраняют доступ к старым представлениям. Новый retention set вычисляется по всему конечному составу и proof dependencies; refs не освобождаются из delete. Shared artifact, сохранённый через другой адрес или версию, не теряет владение. Физический release/GC остаётся отдельным owning lifecycle.

## Проверки приёмки

- У UID есть terrain и settlement: каждый метод удаляет только собственную тройку part/metadata/proof; второе представление неизменно.
- Частичная тройка промежуточного state удаляется согласованно; повтор — no-op; duplicate/forged state отклоняется.
- Locations index [A,B] и map_tile.location_pin=0 неизменны после удаления terrain/settlement A: pin всё ещё обозначает A, а не B.
- Не удаляются source location, district entities, SQL rows, grade sidecar или физические blobs; pure метод не делает I/O и не запускает другие публичные операции.
- Обязательное по coverage представление нельзя исключить из READY; изменение вне scope и dangling proof/index dependency отклоняются.
- Input state не мутирует; shared ref на другом адресе сохранён; старый pin читает прежнюю версию после новой публикации.

Роли: Input — typed boundary; PackPreparationService — один pure переход; validator — local/final инварианты; PackPreparationOperation — verified admission/closure/READY; assembler — готовый manifest. Три запрета DAG соблюдаются проектом границ, фактические callers/effects проверяются при реализации. Порядок источники → evidence → manifest → codec/readers не меняется. Статус PROJECT: локальные эффекты конкретизированы; общие schema/errors/scope и sidecar dependency admission ещё не закрывают полную приёмку D.
