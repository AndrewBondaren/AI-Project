# Pack read_part — concrete модели поверх generic контракта

2026-11-12. PROJECT конкретизации [read-контракта ТЗ](../../docs/tz_world_pack_storage.md) и [POJO аудита](pack-pojo-error-acceptance.md). Только документация; runtime/SQL/DAG не менялись, тесты не запускались. Не вводит новые payload-схемы, public операции или storage formats.

## Подтверждённое ограничение

[is_model_identity_owner / ModelIdentity.of](../../backend/app/dataModel/fields/validatedFieldPath.py) принимают BaseModel только с generic origin=None и без unresolved parameters. [CheckedPath](../../backend/app/dataModel/fields/checkedPath.py) использует ModelIdentity как для корня, так и для поля/ветви union. Прямая параметризация PackPartReadInput[GradeSlotSidecar] поэтому не является достаточным concrete owner. Alias на тот же параметризованный класс это не исправляет.

[CanonicalCodec](../../backend/app/encoding/canonicalCodec.py) ищет registration по exact type, а cold decode ModelIdentity проверяет allowlist manifest. Регистрация базовой модели не заменяет регистрацию наследника. Это отдельные требования: нельзя утверждать, что canonical codec вообще запрещает generics; конкретное ограничение здесь относится к ModelIdentity/CheckedPath и согласованной схеме runtime records.

## Сохранить generic публичный метод

Проектная сигнатура остаётся:

`async def read_part[T: BaseModel](self, request: PackPartReadInput[T]) -> PackPartReadResult[T] | PackPartAbsent | PackPartReadRefusal`

Класс PackPartReadPipelineOpenPipeline, модуль application/worldData/pack/read/packPartReadPipelineOpenPipeline.py; одна делегация PackPartReadOperation. Generic сохраняет статическую связь с payload T. В runtime принимаются только зарегистрированные именованные concrete подклассы; прямые instances generic bases/specializations не становятся допустимыми по одной аннотации.

В `dataModel/worldPack/read/part.py` сохраняются общие объявления:

- PackPartReadContractMetadata: id/version; PackPartReadContract[T] наследует их без executable данных.
- PackPartReadInput[T]: pin/address/contract/budget.
- PackPartReadResult[T]: publication/manifest/address/contract/artifact/value/provenance.
- PackPartAbsent, PackPartReadRefusal, PackPinnedReadIdentity и PackPartReadBudget остаются nongeneric shared records.

Не создавать второй набор полей read request/result и не объединять identity, budgets и payload в один универсальный dict. Общие validators/constraints объявляются один раз. Нужные Source/provenance типы остаются owning моделями, не копиями для read.

## Именованные модели — семь семейств, десять ролей

Предлагаемые модули в backend/app/dataModel/worldPack/read/. Названия concrete классов ниже — PROJECT; это type roster, не назначение новых descriptor IDs/versions.

| Модуль | T — существующий или уже предложенный payload | Concrete Contract / Input / Result | Допустимые роли |
|---|---|---|---|
| worldMapTileContract.py | WorldMapTileWire из проекта wire/worldMapTileWire.py | WorldMapTileReadContract / WorldMapTileReadInput / WorldMapTileReadResult | map_tile |
| fineTerrainContract.py | FineTerrainChunkWire | FineTerrainReadContract / FineTerrainReadInput / FineTerrainReadResult | wilderness_chunk, location_terrain |
| settlementContract.py | SettlementStructureWire | SettlementReadContract / SettlementReadInput / SettlementReadResult | settlement |
| climateFieldContract.py | ClimateFieldWire | ClimateFieldReadContract / ClimateFieldReadInput / ClimateFieldReadResult | climate_coarse, climate_fine |
| locationsIndexContract.py | LocationsIndexWire | LocationsIndexReadContract / LocationsIndexReadInput / LocationsIndexReadResult | locations_index |
| gradeSlotsContract.py — уже предложенный ТЗ модуль | GradeSlotSidecar | GradeSlotsReadContract / GradeSlotsReadInput / GradeSlotsReadResult | tile_grade_slots, location_grade_slots |
| spatialRootContract.py | HydrologyPackRoot | HydrologyRootReadContract / HydrologyRootReadInput / HydrologyRootReadResult | spatial_root(HYDROLOGY_OPEN_WATER) |

Shards — внутренние достижимые артефакты spatial dataset, не одиннадцатая логическая роль. Таблица не вводит публичный read произвольного shard ref. Иной будущий spatial domain требует своего owning payload/binding, а не ложного HydrologyPackRoot для всех domains.

Каждый Contract — named concrete subclass PackPartReadContract[T]. Каждый Input — named concrete subclass PackPartReadInput[T], Result — PackPartReadResult[T]. В concrete Input/Result поле contract **сужается до соответствующего именованного Contract**: иначе nested field path снова встретит прямую generic specialization. Это только уточнение типа поля; поля id/version, defaults и validation policy не копируются. Value имеет конкретный shared T. Address может сохранять shared PackPartAddress union с registry role admission; не требуется зеркальная копия каждого адреса в каждом семействе.

Пример для grade: GradeSlotsReadInput.contract и GradeSlotsReadResult.contract имеют тип GradeSlotsReadContract; result.value — GradeSlotSidecar. GRADE_SLOTS_READ_CONTRACT остаётся одним descriptor ID world_pack.grade_slots/version 1 из ТЗ, но instance создаётся concrete классом GradeSlotsReadContract. Tile/location grade не получают разные descriptors ради разных адресов. Структура wire id/version не меняется; точный canonical type ID требует отдельной регистрации и проверки совместимости, не произвольной замены числа.

WorldMapTileWire ещё PROJECT, а некоторые существующие T пока не deep immutable/strict. Именованный read-result не устраняет эти payload gates; нельзя закрыть read contract одним subclass.

## Registry и восстановление запроса

Существующий проект PackPartReadBinding/PackPartReadBindingRegistry остаётся composition owner. К уже предложенным address_types/artifact format versions/payload_type/decoder/budget добавляется проверяемое соответствие concrete contract_type/input_type/result_type из таблицы. Это внутренние Python type references, не поля public descriptor или новый публичный каталог.

Composition проверяет:

1. Уникальность descriptor id/version; concrete классы пригодны для ModelIdentity, без unresolved TypeVar и generic origin.
2. Input/Result ссылаются на один concrete Contract; result.value соответствует зарегистрированному concrete payload_type. Payload schema/immutability проверяется owning binding.
3. Address roles и artifact format согласованы. Один payload family может обслуживать несколько ролей с различными address admission, не разные workflow.
4. Pure decoder возвращает правильный T; result создаётся именованным result_type. Фиктивный cast не заменяет эти проверки.

При Python-вызове registry проверяет descriptor id/version **и exact runtime class** request/contract. Caller не может изменить decoder через неверную generic specialization, произвольный named subclass или forged model_construct. При wire-входе trusted composition выбирает concrete input_type по зарегистрированному descriptor, затем выполняется строгий parse/admission. Не импортировать класс по строке caller и не возвращать raw dict в domain operation. Неизвестный descriptor отклоняется, не выбирает generic fallback.

Это выбор schema/decoder внутри одной read-операции, не выбор следующей DAG-стадии. Ветвление по success/absent/refusal остаётся у DAG; registry не запускает Cache, Source или producer. PackPartReadOperation читает полный payload и конструирует result без lazy I/O за guard.

## Field paths и canonical registration

Field diagnostics начинаются от фактического concrete input: например, GradeSlotsReadInput → contract: GradeSlotsReadContract → version либо address → named union variant → координата. Для decoded payload owner — owning T, включая GradeSlotSidecar/GradeCellSlots. Нельзя строить путь от generic root, маскировать его строкой или выдумывать field для неизвестного JSON key.

Known-field schema failures используют existing JsonFieldError, undeclared/root shape — WireShapeIssue; semantic contract mismatch — согласованный Pack read refusal/validation mapping. Незавершённый общий error union не закрывается этим документом. Одна причина не выдаётся дважды под разными carriers.

Existing canonical schema manifest регистрирует concrete classes и необходимые shared nested records, enums и ModelIdentity owners. Base registration не покрывает descendants; generic bases не экспортируются как serialized request/result records. Численные type IDs, полный nested closure и контрольные vectors ещё должны быть предъявлены. Cold restore не импортирует arbitrary Python modules и отклоняет незарегистрированный owner. Storage artifact schema и read response schema имеют разные identity; новые response classes не меняют payload bytes/digest автоматически.

## Приёмочные проверки

- ModelIdentity.of/CheckedPath работают для каждого concrete Input/Contract/Result и nested address union; direct generic specialization и alias не принимаются как owner.
- Grade tile/location используют одно семейство; FineTerrain и Climate сохраняют общие payload types для обеих ролей.
- Grade descriptor с Climate input/result/value либо чужим named subclass отклоняется до успешного результата; forged instance повторно валидируется.
- Wire request по descriptor восстанавливает нужный named Input; неизвестное имя/ID не запускает import или fallback decoder.
- Canonical encode/decode concrete records и field paths после cold restore сохраняет exact types; отсутствующая регистрация даёт отказ, не base-class projection.
- Result содержит immutable T с выполненным bounded admission; нельзя сохранить mutable samples/list под видом frozen wrapper.
- Generic public API сохраняет статическую связь T; новый публичный метод на каждую роль, source call и DAG-ноды не вводятся.

Статус: concrete runtime-схема предложена; IDs/vectors, registry implementation, exact error mapping и проверки ещё OPEN. Это устраняет неопределённость формы проекта, но не объявляет runtime готовым. Exact publication guard отдельно описан в [pin mapping](pack-pin-identity-mapping.md); этот документ не меняет его lifetime или утверждённый порядок источники → evidence → manifest → codec/readers.
