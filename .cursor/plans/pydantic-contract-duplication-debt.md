# Техдолг Pydantic / POJO / enum: дубли контрактов dataModel

Дата: 2026-10-30. Статус: **OPEN — инвентаризация и предложения; реализация не начата**.

Основание — запрос мастера проверить POJO/enum в dataModel и вынести результат
в отдельный документ. Статически просмотрены 560 Python-файлов,
777 классов, включая 175 enum: имена, поля/типы/defaults, значения enum;
для кандидатов проверены реализации и потребители. Это поиск структурных
совпадений с ручной оценкой смысла, не доказательство отсутствия всех
возможных семантических дублей. Runtime-тесты в рамках аудита не запускались.

Название охватывает семейство контрактов dataModel. Подтверждённые пары
ниже — **frozen dataclass**, а не Pydantic BaseModel. Их устранение не
требует перевода в Pydantic. Массовая смена model_config/strict/frozen,
типизации полей или форматов сериализации в этот долг не входит.

## Подтверждённый структурный долг

### PD-1 — RoomSizePreset / _RoomSizeBuiltin

Приоритет: **P2, композиция контрактов**. Оба класса находятся в
[roomSize.py](</E:/AI Project/backend/app/dataModel/locations/structure/enums/roomSize.py:10>).
Оба frozen dataclass содержат width_range, depth_range, z_range одинаковых
типов. _RoomSizeBuiltin.to_preset только копирует эти поля в RoomSizePreset;
дополнительных данных или инвариантов у private payload нет.

Предлагаемое решение: RoomSize хранит существующий RoomSizePreset как
значение enum; private _RoomSizeBuiltin удаляется после проверки всех usages.
RoomSize.to_preset, preset_map, size_type/from_size_type и exports сохраняются.
Владелец — structure room sizing, слой dataModel; точный путь остаётся прежним.
Новых публичных типов, модулей или альтернативной таблицы диапазонов нет.

### PD-2 — StaircaseSizePreset / _StaircaseBuiltin

Приоритет: **P2, композиция контрактов**. Оба класса находятся в
[staircaseSize.py](</E:/AI Project/backend/app/dataModel/locations/structure/enums/staircaseSize.py:10>).
Совпадают width_range, depth_range и default depth_range=None;
private to_preset только копирует значения в публичный preset.

Предлагаемое решение: StraightSize/UShapeSize/SpiralSize используют
существующий StaircaseSizePreset; _StaircaseBuiltin удаляется после поиска
всех usages. Сохраняются публичные preset API, maps, wire keys и смысл
depth_range=None — глубина вычисляется по высоте. Владелец — structure
staircase sizing, слой dataModel, файл остаётся прежним.

В PD-1/PD-2 подтверждена избыточность описания структуры. Расхождения
самих диапазонов или воспроизведённая функциональная ошибка не заявляются.

## Кандидаты, требующие отдельного решения

- **PD-3 — одинаковые registry pointer fields.**
  [PerkTemplateRegistryEntry](</E:/AI Project/backend/app/dataModel/perks/perkTemplateRegistryEntry.py:10>)
  и [RaceTemplateRegistryEntry](</E:/AI Project/backend/app/dataModel/races/raceTemplateRegistryEntry.py:10>)
  имеют одинаковые поля/defaults/config, но принадлежат разным доменам.
  Это кандидат на общую базу полей при сохранении concrete типов, не
  подтверждённая ошибка и не основание заменить оба одним типом.
  Новый общий владелец/путь и польза выделения пока не согласованы;
  реализация PD-3 не разрешена этим документом.
- **PD-4 — параллельные поколения placement contracts.**
  [PlacementBatch / PlacementBatchV2](</E:/AI Project/backend/app/dataModel/placement/batch.py:17>)
  и [PlacementBatchResult / PlacementBatchResultV2](</E:/AI Project/backend/app/dataModel/placement/result.py:98>)
  имеют общую оболочку, но разные object/outcome types и validators.
  Оба поколения используются. Варианты V2 уже предусмотрены GEO-1 G0-P
  в [существующем плане](</E:/AI Project/.cursor/plans/geo-1-designed-water.md:9664>).
  Решение — завершать соответствующий consumer cutover в owning треке;
  alias/слияние классов или удаление V1 отдельно от него недопустимы.

## Совпадения, которые не следует устранять как дубли

- [SectionStateRef / SectionHistoryRef](</E:/AI Project/backend/app/dataModel/worldSnapshot/sections/refs.py:10>):
  одинаковые поля, разные state/history semantics и canonical type IDs.
  World/player snapshot metadata и refs также сохраняют отдельные типы.
- [ClimatePoleMode](</E:/AI Project/backend/app/dataModel/climate/enums/climatePoleMode.py:10>) /
  [PoleSource](</E:/AI Project/backend/app/dataModel/climate/enums/poleSource.py:8>):
  manual/autoresolve описывают соответственно входной режим и происхождение
  результата. Совпадение значений не обосновывает объединение.
- [WallProvenance](</E:/AI Project/backend/app/dataModel/locations/structure/wallRegion.py:14>) /
  [WaterSide](</E:/AI Project/backend/app/dataModel/hydrology/enums/waterSide.py:6>):
  interior/exterior относятся к различным доменам.
- ClimateZoneEntry / ClimateZoneProfile: частичные авторские overrides
  и разрешённый полный профиль отличаются обязательностью полей.
  LibraryPackManifest / LibraryArchiveManifest различают FS author input
  и lossless archive transport, включая requiredness и extra policy.
- RegionIndexBounds / GridBBox / WorldBounds имеют разные назначения,
  координатные контексты, validation и API. Четырёх совпавших полей
  недостаточно для взаимозаменяемости.

Подтверждённых смысловых дублей enum при этой проверке не обнаружено.
Совпадения целочисленных значений enum сами по себе не являются дублями.

## Порядок будущего устранения и приёмка

Этот документ фиксирует долг; отдельной команды писать код пока нет.
После согласования — **PD-1 и PD-2 по одному за заход**. До правок сверить
актуальный код, usages, imports/reexports и enum.value consumers;
при обнаружении нового публичного контракта сначала уточнить план.

Норматив: docs/tz_building_generator.md (room/staircase size presets),
.cursor/rules/contract-creation.mdc, dataModel-no-hardcode.mdc и refactor-safety.mdc.
Для реализации определить применимые existing tests и их точные команды
после актуальной инвентаризации; текущий документ не отмечает их PASS.

Проверить неизменность enum members/aliases, wire keys, диапазонов,
depth_range=None, size lookup, preset maps, exports и frozen поведения;
положительную/отрицательную статическую типизацию и существующую
сериализацию затронутых потребителей. Решение об identity/fresh copy
результата to_preset принимается по реальным caller contracts, не молча.
Новые runtime файлы в PD-1/PD-2 не планируются; counts папок не растут.

Done: лишний private payload удалён, публичный preset остаётся единственным
описанием структуры, потребители проверены, проверки зелёные, evidence
добавлен и результат принят мастером. Snapshot 4C2-O/4C3, Container/DAG
и посторонние изменения в рамках этого долга не затрагиваются.
