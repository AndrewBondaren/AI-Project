# Pack: полнота зависимостей и точность READY membership

Статус: REV-02, статический trace. Runtime не изменён. Разделение обязанностей уже следует из [Pack contract](pack-v2-domain-contract-spec.md); ниже конкретизировано, что подтверждает existing finish, а чего он не проверяет.

## Existing finish гарантирует точное множество holds

[ArtifactStagingService.finish_preparation](../../backend/app/application/artifacts/staging/artifactStaging.py) валидирует lease/tuple refs и делегирует [SqliteArtifactLeases.finish_preparation](../../backend/app/db/repositories/sqlite/artifacts/leaseStore.py). В одной transaction он:

1. Проверяет writable lease и отсутствие активных writers.
2. Читает OperationRecord; отвергает duplicate refs и любое отличие `set(refs)` от `set(record.leased_artifacts)`.
3. Проверяет sealed storage state каждого ref.
4. Закрывает admission, записывает READY event и возвращает record.

[SqliteOperationArtifacts.read](../../backend/app/db/repositories/sqlite/artifacts/operationArtifacts.py) получает действующие operation holds из holder events. Это фактическое множество удержанных refs, а не список зависимостей manifest. Existing [finish_pack_preparation](../../backend/app/application/worldData/pack/encoding/preparedManifest.py) дополнительно сверяет возвращённые phase/kind/operation/world/fence/fingerprint и members до создания PreparedPackCandidate.

**Следствие:** переданный subset при наличии лишнего operation hold будет отвергнут; переданный superset без соответствующих holds тоже. Но если child одновременно пропущен в refs и никогда не удерживался операцией, equality не обнаруживает пропуск. Semantic closure не следует из READY.

## Что обязан вычислять Pack

Для target final-state prepare исходным является authoritative manifest из конечного state: сам manifest ref, refs всех parts, format-owned transitive children и durable refs provenance частей/assembly. Дедупликация storage refs не удаляет logical addresses и отдельные contextual/provenance проверки. Inherited refs также входят в расчёт; неизменённость part не доказывает удержание после закрытия исходного pin.

Existing helper добавляет spatial roots и climate refs, но доверяет `other_members` для остальных членов. Этот аргумент не становится публичным доказательством полноты target closure. Не заменять расчёт Pack запросом всех operation holds: тогда лишний/пропущенный dependency будет лишь скрыт под формально совпавшим множеством.

[ArtifactFormatContract](../../backend/app/application/artifacts/contracts/formatBackend.py) сейчас содержит encode/decode/row_count, но не children/closure callback; [registry](../../backend/app/application/artifacts/registry/artifactRegistry.py) также не предъявляет generic dependency enumeration. Поэтому слова «registered format closure» в target-плане обозначают требуемый binding, а не готовый existing API. Конкретные leaf/root decoders из payload roster можно переиспользовать; неизвестный формат нельзя автоматически считать leaf. Общий зеркальный ArtifactRef/Closure POJO или новый публичный сервис этим trace не добавляется.

Проверка domain content/evidence принадлежит Pack admission; seal/hold equality — Artifacts. [retain_climate_members](../../backend/app/db/repositories/sqlite/worldPack/climateRetention.py) уже умеет scoped retention для climate children, но не обходит spatial shards или source provenance. Наличие этого механизма не закрывает полный publication handoff target closure.

## Влияние на подготовку

### Результат проверки остальных payload: leaf roster

Для перечисленных ниже текущих owning schemas нет дочерних ArtifactRef в payload. Поэтому отдельный рекурсивный storage resolver для каждой из этих ролей не требуется. Утверждение относится к известной схеме после admission, а не к любому неизвестному JSON/format; permissive extra=ignore ещё не является строгой приёмкой.

| Роли parts | Owning payload и вложенные значения | Storage children |
|---|---|---|
| map_tile | [WorldMapCellWire](../../backend/app/dataModel/worldPack/wire/worldMapCellWire.py): scalar/enum cell fields; wire envelope side/cells | Нет. location_pin — ordinal в отдельном index, не ArtifactRef |
| wilderness_chunk, location_terrain | [FineTerrainChunkWire](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py): columns/runs, coordinates, registry keys/UID | Нет; grade/region UID не storage ref |
| climate_coarse, climate_fine | [ClimateFieldWire](../../backend/app/dataModel/worldPack/wire/climateFieldWire.py): geometry/status и samples | Нет; coarse/fine остаются самостоятельными parts |
| locations_index | [LocationsIndexWire](../../backend/app/dataModel/worldPack/wire/locationsIndexWire.py): LocationsIndexPin с UID, координатами, labels/keys | Нет; location UID не разрешает читать latest entity для построения closure |
| tile_grade_slots, location_grade_slots | [GradeSlotSidecar](../../backend/app/dataModel/terrain/relief/gradeSlot.py): world XY и tuple кодов slots | Нет; связи с terrain/address проверяются отдельно |
| settlement | [SettlementStructureWire](../../backend/app/dataModel/worldPack/wire/settlementStructureWire.py): districts/areas/buildings/cells и inline transitions | Нет в рассмотренной схеме. District frames — записи внутри того же BLOB, не самостоятельные artifacts |

Для settlement дополнительно просмотрены [Transition](../../backend/app/dataModel/locations/transitions/transition.py), [TransitionEndpoint](../../backend/app/dataModel/locations/transitions/transitionEndpoint.py) и [transitionParams](../../backend/app/dataModel/locations/transitions/transitionParams.py): endpoint/level/world/location identifiers, glossary/tag refs и registry type keys не являются ArtifactRef. Не превращать слово ref в имени поля в storage dependency. Необходимый historical transition registry context по [settlement binding](pack-settlement-binding.md) остаётся отдельным admission/provenance binding; leaf status его не отменяет.

**Межчастные связи не пропадают:** map_tile.location_pin проверяется против locations_index из той же authoritative версии; index включён в общий состав как собственный part. UID, status и grade-slot принадлежность проверяются owning правилами. Не объявлять все parts независимыми только потому, что их payload не содержит storage children, и не добавлять повторную recursive загрузку source entities по UID.

Итог roster: 9 из 10 известных part roles имеют пустой payload-child closure; hydrology spatial_root имеет конкретный root→shards проход, а shard — leaf по рассмотренной схеме. Это снимает необходимость новых способов перечисления children для этих payload. Отдельно остаются format registration/admission, межчастная согласованность, source-proof closure и lifecycle. Наличие общего extensible registry может быть implementation выбором, но не является новым обязательным публичным API или блокером для девяти leaf roles.

### Уточнение после трассировки конкретного spatial payload

Для hydrology локальная конкретизация уже есть в [spatial-root binding](pack-spatial-root-binding.md), раздел final admission. Её не нужно заменять новым универсальным resolver: verified bounded root read → owning `decode_root(payload, version)` → `root.shards` → verified bounded shard reads и `decode_shard` → сверка source_ref и `(tx, ty)` с root/entry. Typed `HydrologyShardRef.artifact` даёт точный ArtifactRef; root проверяется относительно candidate world. Все addresses проверяются, хотя физические refs дедуплицируются.

[HydrologyPackRoot](../../backend/app/dataModel/hydrology/pack/root.py) содержит `source_ref: PlanRef`, `dependencies: tuple[PlanDependency, ...]`, `shards: tuple[HydrologyShardRef, ...]`. [HydrologyPackShard](../../backend/app/dataModel/hydrology/pack/shard.py) содержит source_ref/tx/ty/bed/wet_runs/shore_rows; для рассмотренной storage-схемы это leaf artifact. Empty shards допускается только по owning schema, не заменяет отказ decode. Таким образом artifact-рёбра этого payload конкретны: manifest → root → shards. Реализация final admission/retention ещё требуется, но отсутствие generic closure callback само по себе не требует проектировать новый механизм для hydrology.

[PinnedSpatialReader.read_shard](../../backend/app/db/repositories/sqlite/worldPack/pinnedSpatialReader.py) уже декодирует roots и ищет `entry.artifact == ref`; это проверка reachability отдельного requested shard, а не готовое перечисление/проверка всего closure кандидата. Вызывать его как публичную междоменную операцию или считать его bytes-результат доказательством связности root/shard нельзя.

Отдельно [PlanRef](../../backend/app/dataModel/planning/identity/planRef.py) содержит только key/output_fingerprint; [PlanDependency](../../backend/app/dataModel/planning/contracts/planDependency.py) — slot/ref. Они не предоставляют ArtifactRef, storage kind/format/nbytes и не разрешают synthesize ref по fingerprint или искать latest Planning cache. `packSchema._closure` — обход типов/aliases для canonical schema, не traversal storage refs; совпадение имени не делает его retention resolver.

Для provenance использовать границу [Source proof appendix](source-proof-v2-contract-spec.md): PackStoredProvenance содержит owning source_proof и существующие planning dependencies, без копии Source body/dependency fields в Pack. Точное перечисление durable Source artifacts должен предоставить owning proof binding; в просмотренном appendix это проект внешнего контракта, а не готовая runtime-функция. Пока binding не предъявлен, нельзя объявить полный provenance closure вычисленным или считать его пустым. Это ограничивает зависимый integrated маршрут; не блокирует реализацию доступного Pack spatial/payload admission и не переоткрывает отложенный PACK-METADATA-PLANNING.

[Write-план](pack-v2-public-write-operations.md) уже задаёт pure преобразования state и final prepare без исполнения списка write-команд. Сохранить этот порядок. В final preparation lease должны попасть только refs итогового проверенного состава плюс manifest, а не все промежуточные варианты draft.

Если под той же lease уже удержан лишний промежуточный artifact, нельзя просто не передать его в finish — existing equality это отвергнет. Нельзя и включить его в authoritative closure исключительно ради READY. Порядок освобождения/повторной подготовки требует согласованного lifecycle binding, а не скрытого cleanup/retry внутри Pack pipeline. [IArtifactHolders.release](../../backend/app/application/artifacts/contracts/holderPort.py) задаёт ограничения writer admission/drain; этот trace не разрешает обход их через прямой SQL.

До stage manifest проверить доступные schema/evidence/closure условия и admission зависимостей через принятые ports; затем сохранить утверждённый порядок stage/seal → finish → candidate. Ошибка atomic adoption остаётся внешним binding, не повод переложить вычисление содержимого manifest на Artifacts. Pack не запускает producer или публичный Source read для достраивания отсутствующего child.

## Приёмка и остаток

Existing exact READY membership подтверждён кодом; новый аналог finish_preparation не нужен. Требуемые проверки target реализации: omitted child при совпавшем неполном holds set отвергается Pack; лишний operation hold не маскируется расширением manifest closure; shared ref дедуплицируется только физически; все контексты адресов проверяются; неизвестный format closure не пропускается; unsealed/missing hold/active writer не дают candidate; READY result сверяется целиком.

Открыты concrete format/provenance enumeration, exact preparing adoption и общий publication retention binding. Это не новые самостоятельные домены/CRUD и не изменение утверждённых границ: wrapper делегирует одной Pack prepare-операции, DAG выбирает дальнейшие действия, внутренний storage port не запускает чужие публичные pipelines. Тесты здесь не запускались; общая приёмка Pack не объявляется завершённой.
