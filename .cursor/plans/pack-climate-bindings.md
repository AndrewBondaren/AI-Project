# Pack climate — общий формат и ролевой admission

Статическая сверка 2026-11-12 для climate_coarse и climate_fine из [инвентаря Pack](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12). Runtime/SQL не изменялись; найденные тесты не запускались. Это уточнение binding, не приёмка всей реализации.

## Подтверждённая реализация

Обе роли уже используют один [CLIMATE_FIELD_FORMAT](../../backend/app/application/worldData/pack/encoding/climateFieldFormat.py): BLOB, key `world_pack.climate_field.zstd`, версия payload 1, content_model=bytes. `decode_climate_field` проверяет bytes и header TileCodec с PAYLOAD_KIND_CLIMATE, затем вызывает общий parser. Format encode/decode валидируют и возвращают исходные bytes, а не повторно сериализованный payload. Версия этого descriptor не равна версии manifest; её нельзя автоматически заменить значением wire/storage manifest.

[PacksWiring.register_climate_field_format и initialize_pack_storage](../../backend/app/core/container/packs.py) регистрируют этот format с ContentAddressedBlobBackend. Поэтому новый climate format/backend или два отдельных coarse/fine codec не требуются. Typed результат чтения — существующий [ClimateFieldWire с ClimateSampleWire](../../backend/app/dataModel/worldPack/wire/climateFieldWire.py), без зеркального Pack POJO.

[StagedClimateFields.validate](../../backend/app/application/worldData/pack/encoding/stagedClimateFields.py) уже выполняет под catalog.guard проверку seal и OperationHolder точного lease, затем read_verified с max_bytes=ref.nbytes. После чтения проверяет coarse-роль либо fine-роль и origin из tile gx/gy и manifest.fine_cells_per_map_cell. Это внутренний helper с I/O-зависимостями backend/catalog/holders, не чистый validator. Его ValueError и ошибки чтения ещё должны быть сопоставлены с принятым публичным результатом Pack; сам helper не объявляется публичным pipeline.

При переходе на parts выбор ref/address идёт из единственного списка частей: отдельные climate_coarse_ref и tile.climate_fine_ref не остаются вторым authoritative источником. Существующие проверки seal/hold/role/origin переиспользуются. Наличие helper и тестового вызова не доказывает завершённую production-проводку публичного prepare.

## Геометрия и значения

[build_climate_coarse_wire](../../backend/app/application/worldData/pack/climate/climateCoarseBake.py) строит coarse grid в macro-координатах bbox с шагом 1. `build_climate_tile_wire` строит fine grid в fine-координатах: origin=(gx*span, gy*span), width=height=side, шаг берётся из [LightGridScale.from_tile / light_span_for](../../backend/app/dataModel/spatial/grid/lightGridScale.py): max(1, span // max(1, side)). Например, span=1000 и side=32 дают шаг 31; равенство width*step=span не является существующим инвариантом. Не добавлять такую проверку или пересэмплирование в Pack под видом переноса binding.

`ClimateFieldWire.sample_at` использует индекс ly*width+lx. Порядок samples сохраняется; сортировка или заполнение пропусков decoder не допускаются. temperature_base/rainfall допускают None. Pack не вызывает climate generator для восстановления значений и не обращается к live Source/registry при чтении сохранённого числового поля. Сам просмотренный payload не содержит дочерних ArtifactRef; source/provenance dependencies учитываются отдельно по manifest.

Existing admission не проверяет согласованность fine width/height/step с captured assembly, кроме origin. Геометрические требования и область их применения следует явно закрепить до реализации admission; свойства конкретного producer не выдавать за уже реализованную проверку всех сохранённых payload. Producer geometry не переносит orchestration внутрь Pack: DAG передаёт готовый результат, Pack проверяет свой контракт без генерации и скрытых междоменных вызовов. Порядок источники → evidence → manifest → codec/readers сохраняется.

## Конкретизация общего decoder (проект, 2026-11-12)

`ClimateFieldDecoder` получает при сборке binding фиксированные `codec_version` и существующий `DecodeLimits`, как в [общем roster](pack-payload-binding-roster.md). Порт: `decode(payload: bytes, format_version: int) -> ClimateFieldWire`, `validate(value: ClimateFieldWire) -> ClimateFieldWire`. Для coarse/fine используется один decoder. Его ответственность — ограниченное декодирование и проверка самого поля; он не читает manifest, Source, registry, backend или holders и не вызывает генерацию. Признак нарушения ответственности — восстановление samples, выбор актуальной версии мира либо проверка lease внутри decoder.

Последовательность: проверить поддерживаемую версию descriptor и точный header TileCodec с `PAYLOAD_KIND_CLIMATE` → распаковать с ограничением выходных bytes → разобрать JSON с ограничениями структуры → проверить shared `ClimateFieldWire` и вложенные `ClimateSampleWire`. Проверка размера после неограниченного `codec.decode` не выполняет этот контракт. Encoded cap остаётся `PackPartReadBinding.max_payload_bytes`; decoded bytes/nodes/depth/items задаёт захваченный `DecodeLimits`, без второго climate-набора бюджетов. Descriptor по-прежнему хранит bytes: typed read не меняет `content_model` существующего `CLIMATE_FIELD_FORMAT` на модель и не перепаковывает исходные bytes.

Целевой immutable read использует `samples: tuple[ClimateSampleWire, ...]` в owning модели, без `PackClimateField`/копии sample. `validate` не доверяет одному факту наличия экземпляра frozen-модели и применяет тот же профиль структурной проверки, что decode. Отсутствующие width/height/samples отличаются от явно переданного пустого массива. Существующие defaults сохраняются как исходная семантика: origin=(0, 0), шаг=1, status=coarse; в sample отсутствие temperature_base/rainfall даёт None. Явные числовые значения не пересчитываются и не получают придуманных диапазонов температуры/осадков. Порядок samples — row-major; decoder не сортирует, не дополняет и не интерполирует поле.

**Совместимость — согласовано пользователем 2026-11-13.** Сохраняются существующие alias `sample_step_m`, нормализация status через `str(value).strip().lower()`, defaults и преобразования типов shared модели. Их удаление не входит в перенос orchestration и требует отдельного согласованного изменения с проверкой потребителей. Строгость схемы к неизвестным полям не должна скрыто отменять эти разрешённые преобразования; отдельное зеркало модели не создаётся. Сохраняются отказ на удалённый `tier` и существующий приоритет `sample_step_fine` перед `sample_step_m` в `AliasChoices`; сочетание обоих известных ключей проверяется регрессионным примером, а не получает новый отказ из-за перехода на extra=forbid.

**Пустая сетка — решение WP-C7-2 согласовано пользователем 2026-11-13.** Для coarse и fine width/height неотрицательны. Если хотя бы один размер равен нулю, допустим только пустой samples; отрицательные размеры отклоняются независимо от произведения. Для всех допустимых размеров действует `len(samples) == width*height`, без пропуска проверки при нуле. Это согласованное уточнение валидации закрывает пробел текущего `_sample_count`, который при нуле пропускает любую длину, а при двух отрицательных размерах может принять положительное произведение. Пустое поле остаётся существующей частью, не означает удаление или отсутствие; `sample_at` возвращает None. Индексирование непустого поля сохраняется, отсутствующие samples не заполняются. Решение принято; реализация и проверки WP-C7-2 ещё не закрыты.

Ролевой admission после decode остаётся ответственностью Pack: coarse-адрес требует status=coarse; fine-адрес требует status=fine и origin=(gx*span, gy*span), где span взят из captured assembly. Проверки seal/lease/hold выполняются существующим I/O-слоем отдельно. Совпадение width/height с side, coarse step=1 и fine step=max(1, span//side) подтверждены как свойства producer, но пока не являются общим admission всех сохранённых полей. В частности, width*step=span не вводится. Coarse и fine сохраняют разные системы координат; decoder не переводит macro в fine.

Read и prepare применяют одну регистрацию decoder и один профиль ограничений. Неподдерживаемый descriptor/version — `CONTRACT_MISMATCH`; повреждённый frame/JSON/нарушенная согласованная схема — `INVALID_PAYLOAD`; превышение бюджета — `BUDGET_EXCEEDED` по общему контракту Pack. Отказ не превращается в отсутствие части или запрос повторной генерации. Внутренний перенос диагностик использует общий механизм roster, отдельный climate exception-протокол не вводится.

Приёмочные примеры: coarse/fine через один binding; wrong-role и fine-origin mismatch; row-major с различимыми значениями; None в обоих числовых полях; неделимые span=1000/side=32; переполнение decoded budget при небольшом compressed payload; вложенные неизвестные поля; alias/default/status/coercion по явно принятой политике; нулевые/отрицательные размеры и неправильная длина по решению WP-C7-2. Это требования к будущей реализации, не результаты выполненных тестов.

Сверка общего порта 2026-11-13: в сигнатуре используется owning `FormatVersion` вместо сокращённого `int` выше. ClimateFieldDecoder — typed адаптер над единым ClimateFieldCodec из [budget wiring](pack-decoder-budget-wiring.md), без второго semantic decode. Связь output cap и структурных DecodeLimits закреплена в [общем roster](pack-payload-binding-roster.md#сверка-общего-порта-и-профилей-2026-11-13).

## Уже известные незакрытые критерии

### Location climate_status не является tile readiness

Trace [WorldPackWriter.write_location_terrain](../../backend/app/application/worldData/pack/io/worldPackWriter.py): метод создаёт новый LocationTerrainEntry из location_uid/territory_volume/path/hash/bytes, не передавая climate_status. Existing ClimateBakeStatusMixin материализует coarse. Метод заменяет прежнюю metadata row целиком: coarse default действует и при перезаписи ранее существовавшей записи, а не только при первом создании. Это уже сохранено в [write-плане](pack-v2-public-write-operations.md), новое решение о defaults не требуется.

`write_climate_tile` меняет только metadata адресованного tile; записи locations не пересчитывает. [PackFineTerrainReadFacade](../../backend/app/application/worldData/pack/read/packFineTerrainReadFacade.py) возвращает entry.climate_status в location response непосредственно. [PackLoadingProgressFacade](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py) определяет fine-ready по tiles, а не location entries. В просмотренном Pack-коде не найден producer вычисляемого location climate_status из покрытия fine tiles.

Поэтому target PackLocationAssembly.climate_status остаётся сохранённой metadata с существующей семантикой операций, а не новым вычисляемым показателем:

- Inherited location row/provenance переносится без переинтерпретации значения, если операция её не меняет.
- write_location_terrain заменяет row с уже согласованным coarse default и обновлением её metadata evidence; не сохраняет старое fine скрытым merge.
- write_fine_climate/delete_fine_climate изменяют только owning tile climate projection; location status не обновляется каскадом.
- Tile final invariant fine ↔ climate_fine part не применяется к location_uid: отдельной роли location_climate нет. Не требовать fine для всех пересекающих territory tiles по одному значению location status.

Detailed-location scope может требовать обновления определённых tile climate parts по своей явной policy/coverage. Это отдельное evidence от producer через DAG, не вывод Pack из location.climate_status и не разрешение Pack вычислять геометрический план. Наличие coarse location metadata не требует coarse BLOB, как и ранее согласованное значение tile coarse.

Критерии сохранения поведения: повторный write_location_terrain с прежним fine даёт coarse row; untouched inherited fine остаётся без автоматического reset; fine tile write/delete не меняет location metadata; read возвращает сохранённое location значение без поиска latest/пересчёта соседей. Нельзя молча запретить ранее сохранённый location fine только потому, что inspected writer сам его не выставляет, или удалить поле как якобы неиспользуемое: read consumer найден.

Это уточнение existing/proposed mapping, не runtime-реализация. Новых публичных методов/POJO/settings и orchestration нет; локальные изменения и прежний порядок write-операций сохраняются. Реализационные проверки и общая final admission по scope/provenance остаются в соответствующих срезах.

### Межчастные статусы и fallback: сверка existing и target

Проверены [TileManifestEntry.validate_climate_status](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py), [apply_climate_to_view](../../backend/app/application/worldData/pack/climate/climatePackApply.py), [loading progress](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py) и согласованный [delete_fine_climate](pack-delete-fine-climate-contract.md). Нового общего требования иметь coarse одновременно с fine из этих источников не следует.

| Состав/состояние | Подтверждённая гарантия и граница Pack admission |
|---|---|
| Fine ref/part присутствует, tile status coarse | Existing validator отвергает fine ref при status != fine. Target сохраняет это сравнение между parts и owning tile metadata; payload отдельно обязан иметь fine role и правильный origin |
| Fine part есть, coarse отсутствует | Нет безусловного отказа по одному отсутствию coarse. Обязательность coarse должна следовать из принятого scope/coverage |
| Fine отсутствует, coarse присутствует | Это не разрешение вернуть coarse в ответ на read_part(fine). Для отсутствующего fine — typed absent; consumer сам использует разрешённую проекцию |
| Оба parts отсутствуют, tile status coarse | Статус сам не доказывает наличие BLOB. Не синтезировать defaults; допустимость состава определяется scope/coverage |
| Сохранён пустой climate payload | Это существующая часть по принятому WP-C7-2, не удаление/absent. Пустой sample не доказывает corruption или необходимость генерации |
| Tile status fine без fine ref | Existing модель обратное направление не проверяет, loading progress всё же считает такой tile fine-ready. Согласованный delete_fine_climate переводит status в coarse; нельзя выдавать existing validator за уже реализованную двустороннюю гарантию. Для произвольно подставленного final metadata нужны проверки по принятому metadata/coverage контракту, а не автоматическое исправление assembler |

**Уточнение обратной связи по ТЗ и legacy writer.** [ТЗ Pack, поле TileManifestEntry.climate_status](../../docs/tz_world_pack_storage.md) определяет fine как состояние, когда denser climate BLOB готов. [WorldPackWriter.write_climate_tile](../../backend/app/application/worldData/pack/io/worldPackWriter.py) сначала записывает файл через _atomic_write, затем устанавливает fine, но не заполняет climate_fine_ref. [WorldPackReader.read_climate_tile/climate_tile_exists](../../backend/app/application/worldData/pack/io/worldPackReader.py) используют вычисляемый path. Поэтому existing fine без ref может соответствовать реально существующему legacy BLOB; одно это сочетание не доказывает повреждение старого pack.

Для целевого единственного manifest, где authoritative payload refs находятся в parts, существующий смысл готовности переносится в явный **final invariant**: `PackTileAssembly(gx,gy).climate_status == fine` требует part `PackFineClimateAddress(gx,gy)`. В обратную сторону fine part требует соответствующей tile metadata со status fine. Затем verified admission проверяет descriptor/seal/hold/payload role/origin; наличие строки part само по себе не доказывает готовность bytes. Это конкретизация уже заданной готовности и полного состава, а не новая опция Climate или требование coarse BLOB.

Проверка membership/status принадлежит pure `PackPreparationValidator` над конечными parts/assembly; PackPreparationOperation обеспечивает storage admission. Assembler не исправляет fine→coarse, не создаёт part из legacy path и не запускает генерацию. Промежуточный state по согласованному write-плану может быть неполным; проверка итоговой связности не меняет порядок write-вызовов. Inherited fine tile также проходит final invariant; legacy caller/import должен предъявить адресуемый artifact при своём cutover, а не сохранять неучтённую файловую зависимость.

Не ужесточать общий legacy TileManifestEntry обратным validator до миграции существующего writer: это сломало бы показанный путь без устранения причины. Финальный код остаётся одним после cutover/удаления legacy; постоянная вторая схема или fallback path в target read не вводятся. Инвариант относится к **tile** climate status; `PackLocationAssembly.climate_status` не получает выдуманный location_climate address — его semantics/coverage проверяются отдельно.

Добавить приёмочные случаи target: fine tile без part — отказ до stage/READY; fine part без tile либо с coarse status — отказ; fine tile + корректный held/sealed fine part без coarse проходит именно эту связность; missing/corrupt declared artifact не проходит storage admission; legacy writer trace сохраняется до согласованного cutover. Тесты в этом документационном срезе не запускались.

Сохраняются локальные эффекты [write-плана](pack-v2-public-write-operations.md): write_fine_climate устанавливает fine адресованного tile; delete_fine_climate переводит существующий fine status в coarse; write_coarse_climate не сбрасывает fine статусы. Изменение одной роли не запускает другую операцию. Новая boolean policy, дополнительные setters статуса или rebuild pipeline этим уточнением не вводятся.

Consumer trace: уже заданные temperature_base/rainfall сохраняются. Для каждого отсутствующего поля fine sample имеет приоритет, coarse заполняет оставшийся пробел, отсутствие подходящего значения оставляет view неизменённым. Следовательно, один view может содержать температуру из fine и rainfall из coarse; нельзя заменить это выбором одного поля целиком. Для target consumer оба payload берутся из одной pinned publication. Declared-but-corrupt/missing BLOB — отказ чтения, не повод скрыто переключиться на coarse/latest. Эта проекция не становится частью PackPartReadOperation и не разрешает ей запуск чужих публичных методов.

Критерии реализации этого участка: wrong role/origin и fine-part/coarse-status mismatch отклоняются; coarse write сохраняет fine; fine delete не генерирует coarse; valid empty остаётся part; missing declared bytes не становится absent; mixed fine/coarse sample сохраняет порядок выбора отдельно по полям; inherited metadata не исправляется без принятого перехода/provenance. Runtime и тесты в данном срезе не менялись; новые предположения о completeness не приняты.

[Candidate climate admission](pack-climate-preparation-admission.md): наличие refs уже делает admission обязательным в existing helper; вызовы helper найдены в тестах, production call в backend/app не найден. Сохранить эту гарантию при переходе к final-state parts; новый skip-флаг не нужен.

[Передача decoder budget](pack-decoder-budget-wiring.md) конкретизирует проект единого ClimateFieldCodec для format admission/read и изменение identity check StagedClimateFields с глобального singleton на переданный contract instance. Runtime ещё не изменён; output cap и production wiring требуют проверки.

Не новые вопросы настроек: [WP-C7-1…3, шаг 7](cache-public-contracts.md#шаг-7-адресная-приёмка-packclimate-по-замечаниям-независимого-ревью) уже фиксируют вложенные неизвестные поля, пустую сетку и размер после распаковки.

- ClimateFieldWire и samples используют extra=ignore; frozen-модель содержит изменяемый list samples. Нужны строгая вложенная схема и immutable read contract в owning модели, без дублирующих POJO.
- WP-C7-2: политика пустого coarse/fine согласована выше; остаётся реализовать неотрицательность размеров и безусловную сверку длины, включая нулевое произведение.
- max_bytes=ref.nbytes ограничивает compressed bytes, но не decoded allocation. Нужен bounded decode по WP-C7-3, с отказом на превышение лимита/повреждённый frame до выдачи кандидата.
- Сохранение alias sample_step_m, defaults, нормализации status и преобразований типов согласовано выше; остаются регрессионные проверки совместимости. Финальный отдельный аудит версий различает реальные descriptor values и устаревшие имена/комментарии.

[retain_climate_members](../../backend/app/db/repositories/sqlite/worldPack/climateRetention.py) уже выдаёт детям ArtifactRetentionHolder(manifest) в scoped transaction после проверок identity/seal/operation holds. Это основа общего retention, но climate-only множество не заменяет полный closure всех parts/provenance. Новый holder store не требуется.

[test_climate_field_format.py](../../backend/tests/spatial_pack/test_climate_field_format.py) содержит stage/reopen и pinned climate после replacement/restart/GC. Они не закрывают строгую схему, decoded budget, пустые/отрицательные размеры и публичную проводку. Для приёмки дополнительно нужны wrong-role/origin, сохранение row-major порядка, неделимый span/side, неподходящий descriptor и полный retention closure. Результат сверки: существующие format/POJO/role checks подтверждены; полный climate admission остаётся OPEN до перечисленных проверок и решений.
