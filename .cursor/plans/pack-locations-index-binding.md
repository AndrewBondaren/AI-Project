# Pack locations_index — формат и позиционные зависимости

Статическая сверка 2026-11-12. Область — собственный read/admission контракт Pack. Runtime и shared POJO не менялись; миграция внешних callers остаётся у их владельцев. Связь: [роли payload](pack-v2-domain-contract-spec.md#6-роли-payload-сверка-writer--reader--retention-2026-11-12).

## Подтверждённая семантика

`build_locations_index` формирует existing LocationsIndexWire из occupancy winners, пропускает локации без map_x/map_y и материализует map_z=0 при отсутствии исходного значения. Он проверяет membership system_location_type по разрешённому registry при построении. `WorldPackWriter.write_locations_index` записывает его JSON без TileCodec/Zstd. `load_locations_index` читает JSON; legacy render facade при отсутствии файла возвращает пустой индекс. Это не требование к новому read_part: отсутствующий адрес, отсутствующий blob и существующий пустой payload различаются по уже принятому контракту.

`LocationsIndexWire.locations` — список LocationsIndexPin. Pin содержит location_uid, map_x/map_y/map_z, display_name, system_location_type/subtype и system_city_size. В нём нет TerritoryVolume, world_uid или дочерних ArtifactRef. Поэтому storage closure этого payload пуст, а source provenance — отдельная зависимость использования. Нельзя объявлять проверкой payload сравнение world/territory с полями, которых в нём нет. Индекс pins и assembly.locations с materialized terrain имеют разные обязанности; равенство их UID-наборов не установлено и не вводится (L0 pins могут существовать до L2 terrain).

Историческое чтение не проверяет ключи по latest registry: это прямо задано ТЗ Pack в разделе LocationsIndexPin. Existing `overlay_location_pins` — отдельная render-проекция по SQL, сохраняющая длину и порядок. Она не становится частью immutable read_part и не меняет сохранённые bytes версии.

## Порядок locations является смысловыми данными

Цепочка: `SettlementContributor.apply` делает enumerate(ctx.locations_index.locations) и записывает index в WorldMapCellWire.location_pin; при пересечении выбирает меньший index. `render/pack/locationPinOverlay.py::pin_at` возвращает pins[index]; `WorldMapMacroRender.tile_settlement_glyph` использует это разрешение. Owning ТЗ также определяет location_pin как index → locations_index.

Следовательно, canonical codec обязан сохранять порядок locations. Это не множество и не допускающий сортировку список UID. Пример: индекс [A, B], location_pin=0 означает A; замена индекса на [B, A] при неизменном map_tile ref меняет значение той же клетки на B. Одинаковая длина и тот же UID-set не доказывают совместимость. Подтверждено статическим trace, runtime-тест здесь не выполнялся.

Для Pack-owned проверки итогового состава требуется сохранить позиционную связь map_tile ↔ locations_index. Числовой pin должен разрешаться в индекс того же manifest; при inherited map_tile нельзя молча принять переназначение используемой позиции другой локации. Pack не сортирует pins, не перенумеровывает сохранённые L0 клетки и не пересчитывает footprint. Если замена индекса несовместима, producer/DAG должны предъявить согласованный результат обновления зависимых parts; наличие публичного replace_locations_index само по себе не подтверждает совместимость полного candidate.

Точная проверка совместимости входит в final admission полного состояния, а не делает промежуточный write зависимым от немедленного выполнения следующей операции. Новый порядок публичных write-вызовов не вводится. Как именно binding предоставляет проверенные использованные pin positions/зависимость от индекса без нового зеркального evidence POJO, ещё требуется конкретизировать. Простое требование «любой новый ref индекса требует пересборки всех tiles» не вводится: изменение неиспользуемой записи не доказывает несовместимость. Совпадение UID в используемой позиции — необходимая проверка этой связи, но не полное доказательство сохранности остальных producer dependencies.

## Read binding и предел локальной работы

Переиспользовать LocationsIndexWire/LocationsIndexPin, не добавлять вторые frozen-модели с теми же полями. Existing root frozen содержит mutable list, nested extra=ignore допускает потерю неизвестных полей; это ещё не deep immutable strict contract. Миграция общей модели/consumers выполняется отдельным согласованным срезом; сейчас не менять интегрированные методы других доменов и не ослаблять обещание immutable read.

Storage — BLOB bytes binding, typed read T — existing owning LocationsIndexWire после принятой адаптации. Перед JSON parse применяется explicit byte budget; encoded IO учитывается PackPartReadBudget, memory expansion проверяется при приёмке decoder. Декомпрессия этому формату не нужна. Format descriptor/read descriptor, bounded strict codec, concrete typed errors и composition registration пока не предъявлены; leaf closure сама их не заменяет.

Проверки: round-trip сохраняет порядок и значения pins; reorder меняет fingerprint/digest; same count/UID-set с другой индексацией не проходит как доказательство совместимости inherited L0; empty payload отличается от absent и missing blob; повреждение JSON и unknown fields не становятся пустым индексом; исторический custom registry key читается без latest membership lookup; returned value не требует IO после закрытия guard. Список фиксирует требования, не успешные тесты. Полная приёмка binding остаётся OPEN.
