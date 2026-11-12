# Pack spatial_root — hydrology root, shards и retention

Статический trace 2026-11-12 для [инвентаря payload](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12). Изменена только документация; тесты не запускались. Existing механизмы ниже не означают приёмку целевого публичного prepare/read.

## Формат и владельцы

[SpatialDomainRootRef.validate_descriptor](../../backend/app/dataModel/worldPack/meta/spatial/domainRoot.py) допускает HYDROLOGY_OPEN_WATER с конкретным BLOB descriptor ROOT_V1. Generic произвольный domain/format сейчас не реализован. В parts переносится тот же root ref по адресу spatial_root(domain), без второго authoritative списка spatial_roots.

Owning hydrology [profile](../../backend/app/dataModel/hydrology/pack/profile.py) определяет root `hydrology.open_water.root.tlv` (16 MiB) и shard `hydrology.open_water.shard.tlv` (4 MiB), format_version=1, tile side=64, ограничения nodes/depth/items. Это реальные payload descriptors; версии manifest не заменяют их автоматически. Имена ROOT_V1/SHARD_V1/require_v1 и комментарии входят в отдельный аудит после удаления legacy; сохранённые значения формата меняются только по согласованному storage contract.

Существующие [HydrologyPackRoot / HydrologyShardRef](../../backend/app/dataModel/hydrology/pack/root.py) и [HydrologyPackShard](../../backend/app/dataModel/hydrology/pack/shard.py) — owning POJO. Root содержит source_ref: PlanRef, dependencies: tuple[PlanDependency, ...], topology, physical tables и shards: tuple[HydrologyShardRef, ...]; shard ref содержит tx/ty/artifact. Shard содержит source_ref, tx/ty, bed, wet_runs, shore_rows. Pack не создаёт зеркальные DTO этих тел и не превращает PlanRef в ArtifactRef по предположению.

Root уже проверяет фиксированные dependency slots/revisions, их world/scope относительно source_ref, порядок/уникальность shard tiles и пересечение с topology frame. Shard проверяет своё покрытие и данные относительно собственного tile. Общий _PackRecord проверяет immutable values, полный набор полей, строгие вложенные значения; [decode_root/decode_shard](../../backend/app/application/worldData/generators/hydrology/encoding/packCodec.py) используют bounded canonical decode. Это готовые механизмы, не основания создавать второй Pack codec.

**Важное различие:** [ROOT_FORMAT/SHARD_FORMAT](../../backend/app/application/worldData/generators/hydrology/encoding/packFormats.py) проверяют только bytes и format_version, возвращая исходные bytes. Они сами не вызывают decode_root/decode_shard. Успешные stage/read_verified/digest поэтому не доказывают semantic admission root/shard. Bounded owning decoder должен быть явно включён в соответствующую проверку; нельзя считать его исполненным лишь по регистрации format.

## Чтение и effects

[OpenWaterBlobReader](../../backend/app/application/worldData/pack/spatial/openWaterBlobReader.py) — внутренний I/O reader с registry/catalog/holders. Проверяет descriptor, профиль и caller budget; под catalog.guard выполняет admission, проверяет точный catalog ref, seal/hold и read_verified. Ошибки представлены SpatialBlobReadError с SpatialReadFailureReason: unsupported format, resource limit, missing, corrupt, unavailable. Он возвращает bytes, не HydrologyPackShard, и не выполняет генерацию.

[PinnedSpatialReader](../../backend/app/db/repositories/sqlite/worldPack/pinnedSpatialReader.py) использует ExecutionPins и manifest backend: root обязан входить в pinned manifest; для shard читает/decode_root и ищет точный entry.artifact. При физическом открытии child повторно проверяет held_manifest через admission callback внутри guard. Holder ребёнка — ArtifactRetentionHolder(manifest), не holder root. Замена текущего head не подменяет выбранный manifest. Чтение сохранённого payload не требует live Source или повторного Planning.

Этот reader пока выбирает roots из manifest.spatial_roots; целевой выбор идёт из parts. В просмотренной реализации нет сравнения декодированного shard.source_ref с root.source_ref и shard.tx/ty с entry.tx/ty: read_shard возвращает bytes. Проверки каждого POJO отдельно этого не доказывают. Связность root→shard, привязка root.source_ref.key.world_uid к manifest.world_uid и соответствие captured assembly/provenance должны быть явно покрыты admission. Семантику hydrology проверяет owning контракт; Pack не запускает публичные операции Hydrology, не достраивает shards и не оркестрирует генераторные стадии. Готовые результаты передаются через DAG.

## Closure и подготовка

Для просмотренной storage-схемы artifact-рёбра payload: manifest → root → root.shards[*].artifact. В inspected shard нет дочерних ArtifactRef. Persisted provenance/source dependencies из общего manifest учитываются дополнительно по принятому контракту; root.source_ref/dependencies не являются готовым списком artifact holds.

[finish_pack_preparation](../../backend/app/application/worldData/pack/encoding/preparedManifest.py) добавляет spatial roots, но transitive refs принимает в other_members от preparing writer. Он не читает root и не сверяет полноту этого множества с root.shards. Проверка равенства leased_artifacts переданному members подтверждает переданный набор, а не его полноту относительно payload.

Pack-owned требование: перед READY сопоставить полный рассчитанный closure с удерживаемыми sealed refs, не доверяя произвольному other_members. Сбор refs и локальная проверка immutable результата — внутренняя часть Pack admission, а не новая междоменная orchestration. Все root/shard children удерживаются от manifest; общий atomic handoff/release использует принятые Artifacts bindings, без второго holder store. Сохранить общий порядок источники → evidence → manifest → codec/readers; этот trace его не переставляет и новые DAG-ноды не вводит.

[PacksWiring.initialize_pack_storage](../../backend/app/core/container/packs.py) регистрирует manifest/climate, но не ROOT_FORMAT/SHARD_FORMAT. Их наличие в hydrology и регистрация в test fixtures не доказывают production composition. Конкретное owning подключение и публичное error mapping остаются OPEN; это не разрешение Pack вызывать публичный pipeline другого домена.

## Приёмка

Найденные [codec tests](../../backend/tests/spatial_pack/test_pack_codec.py), [guarded reads](../../backend/tests/spatial_pack/test_guarded_blob_read.py) и [pin retention tests](../../backend/tests/spatial_pack/test_manifest_pin_retention.py) покрывают отдельные механизмы. Последние вручную собирают root/shard children и выдают ArtifactRetentionHolder(manifest); это доказательство поведения primitives, не автоматического closure в публичном prepare.

До закрытия binding нужны проверки: missing/extra closure member; shard другого source_ref или tile; root другого world; корректный digest некорректного TLV; неверный descriptor/budget; child вне pinned root; shared shard после release одного manifest; первый read после смены head и GC; rollback без частичного handoff. Проверки schema/limits переиспользуют owning codecs, не дублируют их реализацию.

Статус: existing descriptor/POJO/bounded codec/guarded pinned read подтверждены. Полный spatial admission и production composition остаются OPEN. По обязательным критериям домена этот trace не закрывает публичные CRUD-сигнатуры, фактический DAG-путь и atomic lifecycle; они проверяются в соответствующих срезах общего плана. Миграция чужих callers не превращается в запрет выполнять доступную Pack-owned работу.
