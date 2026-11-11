# World Pack V2: проект контракта единого manifest

Связь: [§15.69 основного плана](spatial-distribution-domain.md), [результат ревью](world-pack-v2-pojo-independent-review-2026-11-11.md). Дата: 2026-11-11.

Статус: конкретизация Pack-owned части для последующей приёмки. Пользователь принял переход на новую storage version с единственным целевым decoder (2026-11-11). Это не разрешение реализации незакрытых внешних контрактов. Код не изменяется.

## Принятое решение о формате и переходе

- Сохраняются ключ `world_pack.manifest.json`, JSON-представление и существующий класс `WorldPackManifestV2`. Полный состав хранится inline в одном manifest.
- Целевая storage version — 2 вместо текущей 1. Binding после переключения принимает только новую версию и новую схему; прежние bytes не переинтерпретируются под новым descriptor. Один целевой encoder/decoder, без fallback на прежнюю схему.
- `pack_version` сохраняется как обязательная wire semver World Pack. Она не дублирует `ArtifactRef.format_version` или `TileCodec.codec_version`. Точное значение для новой схемы и допустимая пара wire/storage versions определяются при окончательной спецификации; прежнее `2.0.0` автоматически не переносится. Storage version 2 не означает автоматически изменение версии кодеков payload или имени класса.
- До переключения инвентаризировать прежние manifest refs в heads, pins и поддерживаемой snapshot history. Для каждой живой зависимости определить пересборку либо доказуемую отдельную миграцию. Из path/hash нельзя синтезировать недостающие source proofs. Если доказательств нет, требуется новая подготовка по источникам; прежняя историческая версия не подменяется новым bake.
- После переключения runtime не содержит второго decoder старой схемы. Если нужна миграция данных, её scope и способ выделяются отдельно до переключения; автоматического converter или разрешения удаления данных это решение не создаёт. Неразрешённые живые зависимости блокируют переключение.
- При обновлении binding одновременно меняются validator PreparedPackCandidate, codec, readers/admission, retention, composition и fixtures. Cache key уже включает полный ArtifactRef, поэтому версия формата участвует в identity; старый cache entry не допускается обходным путём.
- Сохраняется явный budget одного manifest. Измерение полной схемы с реальными proofs обязательно; второй contents object автоматически не вводится. Отдельный шаг удаления V1 сохраняется.

## Единственный сохраняемый агрегат

Владелец — World Pack. Эволюционирует существующий `dataModel/worldPack/meta/worldPackManifest.py::WorldPackManifestV2`. Полный состав версии хранится непосредственно в нём. `PackVersionContents`, `versionContents.py`, отдельный contents ArtifactRef и отдельный lifecycle contents не нужны.

Логическое тело целевого manifest:

| Поле | Тип | Источник и инвариант |
|---|---|---|
| world_uid | EntityUid | Один мир для всех refs/proofs; совпадает с publication и подготовкой |
| parts | tuple[PackStoredPart, ...] | Полный итоговый набор адресованных частей, не дельта; адреса уникальны |
| assembly | PackAssemblyInput | Единственная декларация effective параметров и metadata из ТЗ; request_mode отсутствует |
| assembly_provenance | tuple[PackStoredAssemblyProvenance, ...] | Ровно один proof на header и каждую metadata-проекцию |

Помимо четырёх полей доменного тела manifest обязательно содержит `pack_version`: wire semver, проверяемую по точному разрешённому значению. Физическое представление остальных служебных полей определяется будущим binding. Текущие значения не утверждаются для новой схемы автоматически. Self content_hash не добавляется: digest/nbytes находятся во внешнем ArtifactRef. Это состав доменного тела, но не окончательная wire schema до закрытия перечисленных ниже gates.

## Минимальный wire-envelope — конкретное предложение

Сверка callers: V1 writer присваивает manifest.codec_version из PackBakeDefaults/TileCodec и payload_format="json". Целевые payload refs уже содержат собственные format_key/format_version; JSON manifest не является TileCodec BLOB. Поэтому перенос этих двух полей в новый header создаёт неясную вторую версию формата. [Writer](../../backend/app/application/worldData/pack/io/worldPackWriter.py) · [TileCodec](../../backend/app/application/worldData/pack/io/tileCodec.py) · [ArtifactRef](../../backend/app/dataModel/artifacts/references.py).

Решение 2026-11-11: предложение удалить `pack_version` отозвано после трассировки V1 и текущего admission. Целевой JSON содержит четыре обязательных поля доменного тела world_uid, parts, assembly, assembly_provenance и обязательное поле `pack_version`. Отдельный сохраняемый envelope POJO не нужен. Ключ и storage version берутся из внешнего ArtifactRef и зарегистрированного binding; decoder дополнительно проверяет точную разрешённую wire semver. Имя Python-класса WorldPackManifestV2 сохраняется и не становится wire discriminator. Исключение codec_version/payload_format остаётся отдельным предложением, требующим проверки всех payload bindings и consumers; решение о pack_version его не утверждает.

Основания: [ТЗ, таблица manifest.json: pack_version — wire semver](../../docs/tz_world_pack_storage.md); [текущий decoder](../../backend/app/application/worldData/pack/encoding/packManifestCodec.py) выбирает wire-схему и защищает legacy save; [manifest binding](../../backend/app/application/worldData/pack/encoding/manifestFormat.py) отдельно проверяет storage version и pack_version; [TileCodec](../../backend/app/application/worldData/pack/io/tileCodec.py) проверяет версию бинарного заголовка blob. В исходном коммите `496b064d` pack_version и codec_version уже объявлены отдельно. Это разные контракты совместимости.

[Текущий ZIP import](../../backend/app/application/worldData/pack/import_/packImportService.py) требует manifest.json, но не внешний ArtifactRef и не выполняет wire admission. Поэтому import/export не доказывает возможность заменить pack_version внешним descriptor. Целевой import/export ещё должен определить перенос и проверку descriptor вместе с точными bytes; наличие pack_version само по себе не доказывает происхождение, digest или удержание. Единственный целевой decoder проверяет согласованность wire/storage versions без legacy fallback и без угадывания по наличию полей.

Предлагаемые внутренние pure signatures в существующем packManifestCodec.py:

- `encode_candidate_manifest(manifest: WorldPackManifestV2, *, max_bytes: int) -> bytes` — проверяет полное immutable дерево и canonical порядок; возвращает deterministic UTF-8 JSON; превышение бюджета отклоняет до reservation.
- `decode_manifest(payload: bytes, *, storage_version: FormatVersion, max_bytes: int) -> WorldPackManifestV2` — сначала принимает только storage version 2 и положительный budget, затем проверяет длину, UTF-8/JSON и полную строгую схему. Конкретные вложенные типы восстанавливаются без общей legacy модели.

Порядок admission: exact bytes → разрешённая storage version и budget → byte length → JSON без duplicate keys/NaN/Infinity → обязательная pack_version и точная разрешённая пара wire/storage versions → strict schema без extra/default заполнения отсутствующих обязательных полей → constraints/address/provenance consistency. Отсутствующая, неизвестная или несовместимая pack_version отклоняется; исторический default V1 в целевом decoder запрещён. Encode также проверяет разрешённую pack_version. Внешний verified storage read отдельно подтверждает digest/nbytes, seal и удержание. Pure codec не выдаёт гарантию хранения или владения.

Предлагаемая детерминированная запись: owning POJO JSON projection с сохранением порядка массивов после принятой доменной нормализации, сортировка ключей JSON-объектов, UTF-8 без BOM, compact separators, без NaN/Infinity. Конкретные параметры encoder закрепляются fixture bytes при реализации; canonical fingerprint preparation по TLV остаётся отдельным контрактом и не заменяет hash сохранённого JSON. При decode/verify исходные bytes не перекодируются ради вычисления digest. Эквивалентные, но иначе отформатированные валидные bytes имеют другой content hash; identity всегда по точным bytes.

manifest_format(max_bytes) получает fixed storage version 2 из owning constants, вызывает этот codec и возвращает исходные валидированные bytes. Текущие вызовы decode_manifest(payload) без версии/budget в pins, readers и storage admission должны быть мигрированы вместе. Возврат через WorldPackManifest и getattr/default для новых полей запрещён. В migration tests сначала нужен полный roster callers, включая tests/import/export.

Критерии wire-gate: старый JSON с прежними полями отвергается даже при подмене descriptor version на 2; storage version 1 отвергается до JSON parsing; отсутствующая, неизвестная и несовместимая pack_version отвергается даже при корректном внешнем descriptor; encode отвергает неподдерживаемую pack_version; missing/extra keys, duplicate JSON keys и неверные nested types отвергаются; одинаковый нормализованный manifest выдаёт одинаковые bytes; decoder не меняет bytes identity; новая схема round-trip сохраняет pack_version и все поля/proofs. Сохранение pack_version принято; её точное значение, остальные предложения по envelope и окончательный полный schema roster ещё требуют приёмки. Принятая storage version 2 не закрывает их автоматически.

`PackStoredPart` имеет только `address: PackPartAddress`, `artifact: ArtifactRef`, `provenance: PackStoredProvenance`. `PackStoredAssemblyProvenance` имеет только `address: PackAssemblyAddress`, `provenance: PackStoredProvenance`. `PackStoredProvenance.source_proof` получает конкретный durable тип владельца Source; placeholder запрещено превращать в Any/dict/строку. Новые records размещаются в owning модулях частей/provenance, не создают второй сохраняемый агрегат.

## Единственная декларация metadata

### Трассировка codec_version и payload_format (2026-11-11)

**Находка WP-CODEC-01 — OPEN.** Поля manifest не являются действующим источником конфигурации decoder. Более того, V1 допускает расхождение заявленной codec_version и версии заголовка записанного blob. Подтверждено чтением вызовов backend/app; это статическая трассировка, не выполненный runtime-тест и не разрешение удаления полей. Внешние consumers не проверены.

#### V1: создание, запись и чтение

1. [PacksWiring.world_pack_writer_for / world_pack_writer](../../backend/app/core/container/packs.py) создают WorldPackWriter без codec и bake_defaults. Стандартная композиция использует canonical defaults, версия равна 1.
2. [WorldPackWriter.__init__](../../backend/app/application/worldData/pack/io/worldPackWriter.py) принимает `codec: TileCodec | None` и `bake_defaults: PackBakeDefaults | None`. При отсутствии codec создаёт `TileCodec(level=defaults.zstd_level)`: **defaults.codec_version не передаётся**. TileCodec берёт свою версию из canonical_defaults, а не из переданного writer bake_defaults.
3. [worldMapBakeOrchestrator](../../backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py) вызывает sync_world_metadata. Этот метод пишет `manifest.codec_version = self._bake_defaults.codec_version` и `manifest.payload_format = "json"`, не сверяя их с фактическим codec. При явном codec writer также не выводит metadata из него.
4. Контрпример по коду: writer получает bake_defaults с codec_version=2, без codec; metadata объявляет 2, а создаваемый TileCodec пишет header version=1. Обратное расхождение возможно при явно переданном codec другой версии и canonical bake_defaults. Стандартная DI-композиция такого расхождения не демонстрирует; факт существования неконсистентного допустимого пути не означает обнаружение испорченных production-данных.
5. WorldPackWriter.write_world_map_tile, write_wilderness_chunk, write_location_terrain, write_climate_coarse и write_climate_tile вызывают self._codec.encode с соответствующим kind. TileCodec кодирует JSON, сжимает zstd и добавляет header `(codec_version, kind)`. Settlement использует тот же codec через функции packBlobWire, включая framed-представление.
6. [WorldPackReader.__init__](../../backend/app/application/worldData/pack/io/worldPackReader.py) принимает явный codec либо создаёт TileCodec() независимо от manifest. L0/fine/climate читаются через `_decode_file → TileCodec.decode → проверка kind → typed parser`. Settlement вызывает parse_settlement_structure_blob: проверяет header version/kind, затем выбирает framed/обычное представление. Загрузка manifest через PackManifestStore не перенастраивает codec reader.
7. Locations index пишется через LocationsIndexWire.model_dump_json; grade sidecars — через [gradeSlotSidecar](../../backend/app/application/worldData/pack/io/gradeSlotSidecar.py) и собственный schema_id. Они не проходят через TileCodec. Поэтому глобальные поля manifest нельзя считать полным контрактом физического формата всех частей.

#### Текущий V2: фактические вызовы и предел интеграции

| Путь | Фактическая цепочка и проверка |
|---|---|
| Регистрация Climate | PacksWiring.initialize_pack_storage → register_climate_field_format → CLIMATE_FIELD_FORMAT + ContentAddressedBlobBackend. Регистрация формата не означает подключения production prepare |
| Staging Climate bytes | [TypedArtifactStager.stage](../../backend/app/application/artifacts/staging/artifactStaging.py) → registry.encode → CLIMATE_FIELD_FORMAT.encode → _validated_bytes → decode_climate_field. Backend.write повторно вызывает contract.encode и сверяет bytes с reserved descriptor |
| Climate codec | decode_climate_field создаёт TileCodec(codec_version=CLIMATE_FIELD_FORMAT_VERSION), проверяет ожидаемый header/kind, декодирует и валидирует ClimateFieldWire. Поля manifest не читаются. Равенство storage/codec version здесь локально, не универсальное правило |
| Admission подготовленного Climate | [finish_pack_preparation](../../backend/app/application/worldData/pack/encoding/preparedManifest.py) → StagedClimateFields.validate → catalog guard, seal/hold → backend.read_verified → decode_climate_field → проверка coarse/fine и origin. Backend проверяет ref key/version, budget и целостность bytes; typed payload admission выполняет отдельный decoder |
| Manifest write/read | encode_candidate_manifest/decode_manifest сохраняют поля через текущую модель. manifestFormat проверяет storage version и pack_version, а [PinnedManifestReader](../../backend/app/application/worldData/pack/read/pinnedManifestReader.py) — world_uid, pack_version и отсутствие self hash. codec_version/payload_format не выбирают decoder частей и не являются этими проверками совместимости |

В backend/app найдены определения finish_pack_preparation и StagedClimateFields, но не production-вызовы первого или создание второго; вызовы обнаружены в backend/tests/spatial_pack/test_manifest_format.py, test_execution_pins.py и test_climate_field_format.py. Это реализованный helper с тестовыми callers, а не доказательство законченной публичной подготовки через DAG. Нельзя объявлять все V1 payload paths заменёнными на V2 по факту регистрации Climate binding. Трассировка не проектирует DAG-ноды и не разрешает домену вызывать публичные методы других доменов.

#### Закрытие WP-CODEC-01

- До wire freeze завершить карту всех part addresses, format key/version, codec/header/framing, typed payload и readers, включая index/grade/import/export. Отдельно отметить реализованные bindings, тестовые callers и реально подключённые production paths.
- Явно принять судьбу глобальных codec_version/payload_format: удаление остаётся предложением. Если поля сохраняются как гарантия совместимости, определить и проверять их связь с фактическими payload; текущую запись из defaults такой гарантией не считать. pack_version сохраняется независимо от этого решения.
- Для каждого целевого binding проверить round-trip, unsupported artifact/header version, неправильный kind/framing и отказ без fallback. Manifest metadata не должна позволять обходить payload admission.
- Если V1 writer сохраняется на время перехода, закрыть сценарии несовпадения явного codec, bake_defaults и metadata согласованной проверкой/источником версии; если удаляется отдельным утверждённым шагом, подтвердить отсутствие callers. Здесь не назначается новая реализация V1 и не меняется порядок шагов.
- Подключение публичного prepare и DAG callers проверяется отдельно в утверждённом плане. Наличие helper, binding или тестового вызова не закрывает production gate. Новые DAG-ноды согласуются с пользователем.

Результат: OPEN до выполнения применимых критериев; код не изменён, тесты в рамках трассировки не запускались.

#### Последовательность перехода полей — WP-CODEC-01

Зафиксировано по указанию пользователя: отсутствие найденных чтений не разрешает удалять поля или POJO без перехода. Существующий WorldPackManifestV2 эволюционирует; параллельный сохраняемый POJO ради удаления двух полей не вводится. pack_version сохраняется. Целевая ответственность codec_version/payload_format переносится в bindings конкретных payload; до подтверждения полноты замены текущие поля и wire остаются. Последовательность ниже конкретизирует переход внутри существующего плана, не переставляет его утверждённые шаги. Никакой пункт не считается выполненным этой записью.

1. **Архитектурный шаг — первым. Инвентарь и карта замещения.** Зафиксировать назначения текущих полей, все producers/readers, DI, jobs/CLI, сериализацию, import/export и fixtures. Для каждого part address указать owning POJO, format key/version, codec/header/framing, typed decoder и источник версии. Отдельно описать, как binding заменяет прежнюю декларацию manifest. Проверить фактические вложенные вызовы и границы доменов. Выход: полная согласованная карта без непокрытого типа payload; до этого удаление полей и изменение wire запрещены.
2. **Freeze wire и перехода данных.** По карте определить точную pack_version новой схемы и допустимую пару с storage version 2; явно перечислить исключаемые глобальные поля и их замещение. Инвентаризировать сохранённые manifest и живые refs в heads/pins/history, перенос descriptor в import/export. Для каждой зависимости определить доказуемую миграцию либо пересборку с необходимыми proofs. Историческую публикацию нельзя подменять свежим bake, а прежние bytes — маркировать новой версией. Выход: принятый wire-контракт и исполнимый план данных; неразрешённая живая зависимость блокирует cutover.
3. **Реализация целевых контрактов в существующих компонентах.** Согласованно обновить WorldPackManifestV2, assembler, codec, payload bindings и readers. Новый wire использует только принятую схему; прежние поля не остаются вторым источником истины в ней. V1-специфичные объявления/сериализация, ещё необходимые до cutover, учитываются в реестре удаления; это не разрешение вводить новый fallback decoder или дублирующий публичный путь. Выход: реализованная целевая цепочка с проверкой artifact/header versions, kind/framing и всех typed payload, без доменных публичных вызовов других доменов.
4. **Проверка и перенос входов.** Проверить round-trip всех частей, mismatch версий/заголовков, ошибочный kind/framing, отсутствие обязательной pack_version, restart и чтение pinned публикации. Перевести все API World Pack, read/write, DI, jobs/CLI и import/export на V2; отдельно доказать production-подключение публичного prepare. Test-only helper не закрывает этот gate. Публичные методы вызываются DAG; проектирование новых DAG-нод требует совместного согласования с пользователем. Выход: проверенные входы и отсутствие необходимости V1 для поддерживаемых сценариев.
5. **Cutover и готовность к удалению.** Выполнить принятый переход данных, проверить живые heads/pins/history, прекратить V1 writers/workers и проверить инвентарь оставшихся V1 refs/callers. Действующий runtime принимает единственную целевую схему без legacy fallback. Наличие прежних данных не разрешает обход admission или автоматическое заполнение новых proofs. Выход: выполнены условия существующего SP-P-V1-REMOVE; удаление ещё не объявлено завершённым.
6. **Отдельный шаг — удаление V1 (SP-P-V1-REMOVE, §15.50 основного плана).** Удалить оставшиеся V1-only объявления codec_version/payload_format, сериализацию, constructors/defaults, callers, DI и обходные пути по реестру V1-01…07; очистку прежних данных выполнять только по принятому инвентарю и условиям retention. Сохранить pack_version, общий WorldPackManifestV2 и используемые V2 codec/header contracts. Итоговая приёмка: нет мёртвого V1-кода, дублирующих путей или работающего V1-контракта; все API работают через V2, новый процесс читает закреплённую публикацию после restart. Этот шаг не растворяется в обновлении POJO или binding.

Условия 1–5 не обходятся ради удаления полей в шаге 6. Смена целевой wire-схемы на шаге 3 и окончательное удаление оставшейся V1-реализации на шаге 6 — разные результаты; физически удалять ещё используемые объявления раньше нельзя. Общий CRUD/архитектурный gate и внешние OPEN-контракты остаются обязательными.

AS-IS: [WorldPackWriter.sync_world_metadata](../../backend/app/application/worldData/pack/io/worldPackWriter.py) записывает codec_version из PackBakeDefaults и payload_format="json". По поиску backend/frontend не найдено чтения этих полей manifest для выбора decoder. Это не доказательство отсутствия внешних consumers. [TileCodec](../../backend/app/application/worldData/pack/io/tileCodec.py) выбирает версию из собственной конфигурации и проверяет её против бинарного заголовка; payload_format manifest не управляет JSON decoding. Удаление полей manifest не разрешает удалять версию из blob или ослаблять его admission.

Пример уже существующей V2-границы: [climateFieldFormat](../../backend/app/application/worldData/pack/encoding/climateFieldFormat.py) проверяет внешнюю artifact version, затем ожидаемый header version/kind, затем ClimateFieldWire. Здесь формат определяется binding конкретного payload, а не глобальным полем manifest. Равенство чисел artifact version и codec version в этом binding не является общим правилом для всех форматов.

Дополнительное ограничение: [parse_settlement_structure_blob](../../backend/app/application/worldData/pack/io/packBlobWire.py) различает framed и обычное представления после проверки header. Поэтому глобальное payload_format="json" не описывает полностью физическое представление всех частей Pack. Эту особенность нельзя потерять при переходе на ArtifactRef.

Рекомендация остаётся предложением: убрать глобальные codec_version/payload_format из новой схемы только после полной карты part address → format key/version → codec/header/framing → typed payload → reader. Для каждого L0/L2, location, settlement, climate, index и grade binding нужны точный admission, отказ при несовместимой версии/типе и round-trip. Climate — проверенный пример, не доказательство готовности остальных bindings. Import/export и внешние consumers также входят в проверку. До закрытия карты поля текущего кода не удаляются; это отдельный OPEN gate, не основание вновь исключать pack_version.

Assembly использует общий metadata-контракт с существующими manifest entries. Поля и constraints не копируются в независимые модели. Общая часть объявляется у владельца manifest metadata; preparation использует её, storage не переобъявляет. Названия Pack*Assembly в ТЗ обозначают эти проекции, а не обязательные дубли классов.

| Metadata | Поля | Адрес provenance |
|---|---|---|
| Header | last_l0_mode, effective grid scalars, map_subsurface_depth; registry_hash только после отдельного решения | header |
| Tile | gx, gy, climate_status, wilderness_refine_status; chunks — отдельная коллекция | tile(gx, gy), proof исключает chunks |
| Chunk | cx, cy, refine_role | chunk(gx, gy, cx, cy) |
| Location | location_uid, territory_volume, climate_status; z_band только после отдельного решения | location(location_uid) |
| Settlement | location_uid, territory_volume, structure_status, packed_district_uids | settlement(location_uid) |
| Region | существующий WildernessRegionEntry | region(region_uid) |

Assembly содержит tiles, locations, settlements, wilderness_regions в immutable коллекциях по ТЗ. Macro gx/gy, локальные cx/cy и inclusive fine-grid XYZ не взаимозаменяемы. Constraints сетки переиспользуются от владельцев; отсутствующие effective значения не заполняются defaults Pack. Последний L0 mode не изменяется detailed-запросом.

registry_hash, location z_band и wilderness_tiles_total требуют решения владельцев: в этом проекте не вводятся новые значения, типы или молчаливое удаление прежних wire-полей. Наличие этих gates не оправдывает добавление второго объекта хранения.

## Карта устранения второго источника истины

| Текущее представление | Целевой authoritative источник |
|---|---|
| spatial_roots[].root | parts[spatial_root(domain)].artifact; единая существующая проверка domain→format |
| climate_coarse_ref | parts[climate_coarse].artifact |
| tile.climate_fine_ref | parts[climate_fine(gx, gy)].artifact |
| world_map_path/hash | parts[map_tile(gx, gy)].artifact |
| ChunkRef.content_hash/bytes | parts[wilderness_chunk(gx, gy, cx, cy)].artifact |
| terrain_path/hash/bytes | parts[location_terrain(uid)].artifact |
| structure_path/hash/bytes | parts[settlement(uid)].artifact |
| locations_index path | parts[locations_index].artifact |
| tile/location grade paths | соответствующие grade parts |
| top-level grid, bake_mode и metadata collections | assembly; bake_mode соответствует last_l0_mode |
| world_map_cells / wilderness_chunks_baked | Проверяемые производные итогового состава по семантике ТЗ |

Таблица задаёт семантическую миграцию, не политику прежних bytes. В целевой модели прежние refs не остаются независимо заполняемыми копиями. Нужные consumers получают вычисленную проекцию, без второго сохраняемого значения. Counters не заменяют coverage evidence. Payload остаётся owning схемой домена, не встраивается в manifest вместо ArtifactRef.

## Admission и lifecycle

1. Подготовка принимает полный состав, scope и typed evidence через DAG по существующему проекту prepare. Pack не запускает producers, planner или sidecar merge.
2. Pure validation проверяет уникальность до сортировки, соответствие адреса/ref/формата/proof, metadata/status/coverage и разрешённость изменения относительно pinned базы. Проверки, требующие IO, выполняет внутренняя операция через принятые ports; validator не делает IO.
3. При inherited переносится неизменный durable proof базы. При new принимается proof producer, подтверждённый capture. В storage new/inherited, capture holder, operation_id, lease, fence, receipts и base_publication не сохраняются как необходимые условия чтения.
4. Pure assembler строит один WorldPackManifestV2. Нормализация адресов и множеств — по ТЗ; proof нормализует его владелец. Никакого независимого PackPreparationIdentity: canonical input — PackPreparationBody.
5. Существующий lifecycle подготовки удерживает payload refs, transitive refs и proof closure, затем manifest ref. Adoption/READY/publication выполняются только по принятым Artifacts/Publication ports; новые сигнатуры здесь не выдумываются.

Partial refine: база содержит chunks A/B, изменяется A — B/ref/proof остаются идентичными. Изменение tile status меняет только tile metadata proof и затронутые chunk proofs. Отсутствие элемента входа не является разрешением удалить его. Grade producer передаёт полный incoming-first merge; Pack его повторно не вычисляет.

## Codec и read: обязательная эволюция существующего пути

Текущий `decode_manifest` валидирует через WorldPackManifestV2, затем преобразует в WorldPackManifest. `_ManifestFields.extra="ignore"` создаёт риск потери новых полей. Текущий `encode_candidate_manifest` требует exact WorldPackManifest. Одного расширения V2 класса недостаточно.

Целевой внутренний контракт для нового тела: encode принимает WorldPackManifestV2, decode возвращает WorldPackManifestV2 без промежуточной проекции в legacy модель. После переключения dispatch поддерживает только принятую новую схему; прежняя storage version отклоняется до её декодирования. Codec не выбирает backend, не удерживает refs и не обращается к Source.

`manifest_format` проверяет полный объект и бюджет через согласованный codec; зарегистрированный bytes binding не подменяется молча. `PreparedPackCandidate.manifest` остаётся единственным ref версии; его format/version validator обновляется только после выбора binding. `PinnedManifestReader` проверяет pin и точные bytes, admission не отбрасывает новый состав. Read-part разрешает адрес непосредственно в этом manifest, без дополнительного contents read и без legacy paths.

Размер manifest проверяется до reservation/декодирования по явному budget. Нужны измерения полного состава с durable proofs; превышение бюджета — повод для отдельного архитектурного решения, не автоматическое создание contents artifact. Возвращённый typed read value глубоко immutable, не требует IO после закрытия guard.

## Ответственность и критерии отказа

| Компонент | Допустимая ответственность / зависимости | Приёмка / признак отказа |
|---|---|---|
| WorldPackManifestV2 и records | Данные, pure constraints, owning POJO | Нет mutable вложений, второго authoritative ref или services |
| PackPreparationPipelineOpenPipeline | Один прямой вызов операции из DAG | Нет ветвления стадий или callback |
| PackPreparationOperation | Lifecycle одной подготовки, внутренние принятые ports | Не вызывает producer/геометрию и чужой pipeline |
| PackPreparationValidator | Pure admission готовых данных/evidence | IO или запуск materialization — отказ |
| PackManifestAssembler | Pure сборка одного manifest | Повторный planner/merge или второй storage aggregate — отказ |
| Codec | Проверка, encode/decode по binding | Потеря полей, чтение latest, IO — отказ |
| PinnedManifestReader / read-part implementation | Guard, bounded verified read, адресное разрешение | Legacy fallback, unpinned read, domain-call из decoder — отказ |
| Artifacts/Publication | Существующие seal/holds/READY/activation/recovery | Самодельный commit или публичный lease/fence — отказ |

DAG только вызывает публичные операции и передаёт POJO. Ветви принадлежат DAG; прямые междоменные вызовы и скрытая оркестрация запрещены. Утверждённый порядок L2→C11 для settlement-like location не меняется. Этот документ не проектирует новые DAG-ноды и не закрывает полный аудит nested callers.

## Проверки перед разрешением реализации

- Round-trip полного manifest сохраняет все конкретные типы, адреса, refs, metadata и proofs; дополнительного объекта contents нет.
- Поддельные model_construct/model_copy, duplicate addresses и противоречивые проекции отклоняются; нет bool→int/coercion и mutable дерева.
- Partial refine сохраняет B и proof B; пустой incoming grade сохраняет базу; неправильный coverage при равном count отклоняется.
- Restart без запроса и temporary capture, затем release старой версии: новая версия читает свои payload и proofs.
- Pin A→activate B→read A; corruption/missing hold не превращаются в ABSENT.
- Изменение каждого смыслового поля body меняет fingerprint; перестановки множеств не меняют его.
- Проверены manifest budgets, retention closure, replay READY и GC двух версий.

Открытые входы: concrete Source capture/durable proof и codec; producer coverage/policy evidence; atomic adoption; registry_hash/z_band/wilderness_tiles_total; окончательный wire envelope/schema IDs и реализация binding; инвентарь прежних refs и разрешение живых зависимостей до переключения; полный roster callers и CRUD-приёмка. Выбор одного decoder и storage version 2 принят, исполнение перехода ещё не выполнено. До закрытия входов контракт не является полностью принятым исполнимым планом. Заглушки и новые доменные типы вместо внешних согласований запрещены.
