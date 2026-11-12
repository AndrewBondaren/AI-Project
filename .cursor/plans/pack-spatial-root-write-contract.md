# Pack write_spatial_root — проект публичной операции

2026-11-12. Конкретизация Pack-owned пробела из [сводки приёмки](pack-local-acceptance-status.md); дополнение [write-плана](pack-v2-public-write-operations.md). Только проект контракта, не существующая реализация и не новая orchestration. Runtime/SQL/DAG не изменяются.

## Основание и граница

В [WorldPackWriter](../../backend/app/application/worldData/pack/io/worldPackWriter.py) отдельной операции spatial root нет. [WorldPackManifest.ordered_roots](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py) требует уникальные отсортированные domains; [SpatialDomainRootRef](../../backend/app/dataModel/worldPack/meta/spatial/domainRoot.py) проверяет допустимый domain/root descriptor. В текущем application-коде найдены codec/preparation/read consumers spatial_roots; конкретный production writer этого состава не подтверждён. Test fixtures конструируют manifest напрямую — это не публичный метод.

Целевой адрес PackSpatialRootAddress и перенос SpatialDomainRootRef → address + part уже описаны [ТЗ Pack](../../docs/tz_world_pack_storage.md), разделы переиспользования типов и адресов. Поэтому ниже предлагается операция записи одного готового результата по существующему адресу, а не перенос несуществующего legacy метода. Её add/replace-семантика — проект в рамках принятого общего изменения parts по адресу; не заявляется найденным поведением старого writer.

## Конкретный публичный контракт

В существующем проектном классе `PackPreparationService`, модуль `backend/app/application/worldData/pack/preparation/packPreparationService.py`:

`def write_spatial_root(self, request: PackSpatialRootInput) -> PackPreparationState`

Синхронная pure-операция. Caller — прямой вызов из согласованной ноды DAG; DAG передаёт готовый ref/provenance и выбирает следующий вызов. Отдельный wrapper pipeline, Hydrology facade или новый service не вводится. Общий service не вызывает собственные другие публичные write-методы.

Новый именованный input в `backend/app/dataModel/worldPack/preparation/operations.py`:

| Поле PackSpatialRootInput | Тип и владелец |
|---|---|
| state | PackPreparationState из worldPack/preparation/state.py — существующий проект промежуточного Pack state |
| part | PackPartInput[PackSpatialRootAddress] из worldPack/preparation/parts.py с адресом из worldPack/preparation/addresses.py — общая декларация address/artifact/provenance, без копирования полей |

Размещение адреса в preparation/addresses.py уже предложено в ТЗ Pack; второй PackSpatialRootAddress не создаётся. Поля domain/root/shards/world_uid поверх part/state не добавляются. Domain — existing SpatialDatasetKind, root — part.artifact. Input frozen/strict/extra=forbid с повторной проверкой экземпляров, включая вложенные records.

Результат — новый PackPreparationState; исходный state не мутирует. Смысловой отказ использует проектные `PackPreparationFailure` / `PackPreparationError` / `PackPreparationIssue` из `dataModel/worldPack/preparation/errors.py`. Новые SpatialRootWriteError или копия field diagnostics не вводятся. Структурный отказ следует общей схеме write-плана; предлагаемый там закрытый union структурных ошибок ещё требует общего freeze и не объявляется принятым этим документом.

## Локальный алгоритм и ошибки

1. Повторно проверить input/state и точную специализацию адреса. Дубли адресов в исходном state отклоняются, а не исправляются записью. Неверные kind/domain/типы — структурный отказ по общей диагностике.
2. Проверить domain↔artifact descriptor единым owning правилом SpatialDomainRootRef/registered binding. Сейчас поддержан HYDROLOGY_OPEN_WATER и его root BLOB; shard descriptor на входе root отклоняется как FORMAT_MISMATCH. Не поддерживать вторую независимую таблицу domain→format и не принимать произвольный future domain.
3. Проверить локально доступные identity/provenance связи по общей модели PackPartInput. Inherited wrapper не становится подтверждённым только из-за совпадения hash; окончательная сверка с pinned base относится к final admission. Неподходящие доказательства не заменяются defaults. Публичный input не содержит callbacks для получения proof.
4. Построить один PackStoredPart по общему правилу преобразования входного происхождения в абсолютный PackStoredProvenance. При отсутствии адреса добавить часть; при наличии заменить только этот адрес вместе с его provenance. Даже при равном ref нельзя автоматически отбросить новый provenance как no-op. Остальные parts, base_publication, assembly и assembly_provenance сохраняются. Второй список spatial_roots не создаётся.
5. Вернуть новый state с единственным элементом на domain. Canonical порядок — по общему правилу parts после проверки уникальности, а не произвольная сортировка содержимого root. Метод не вычисляет payload closure, не выдаёт READY и не изменяет head/holders.

Отсутствие вызова сохраняет корень базы. None/пустой ref не означают удаление; delete не прячется в этой сигнатуре. Повторная последовательная запись того же domain заменяет его как целый part; никаких merge bodies/shards между корнями. Новый root не удаляет старые artifact bytes и не освобождает их holds. Общие shards сохраняются по полному closure/lifecycle, а не по разности двух root refs внутри write.

Семантические коды переиспользуются из общего Pack контракта: DUPLICATE_ADDRESS, FORMAT_MISMATCH, SOURCE_PROOF_MISMATCH/BASE_PUBLICATION_MISMATCH при проверяемом нарушении соответствующей связи. Field paths строятся от реального PackSpatialRootInput; одно нарушение не выдаётся одновременно как structural и semantic issue. Финальная scope-проверка OUT_OF_SCOPE_CHANGE выполняется в prepare, где доступен полный scope; она не симулируется этим input без scope.

## Final admission и ответственность

[Spatial binding trace](pack-spatial-root-binding.md) остаётся источником требований I/O: bounded decode root/shards, соответствие root world captured state, shard source/tile root-entry, seal/hold каждого ref и полный closure. Из ref нельзя узнать source_ref или координаты shard; pure write не объявляет эти проверки выполненными. ROOT_FORMAT/SHARD_FORMAT проверяют bytes, а semantic codec должен быть вызван явно.

| Класс | Обязанность и зависимости | Приёмка / нарушение |
|---|---|---|
| PackSpatialRootInput | Именованный Pack boundary над shared state/part/address | Exact types, без дублирующих root/domain/shards; Any/dict/lease/backend в public fields — отказ |
| PackPreparationService | Один pure add/replace root-part через внутреннюю локальную валидацию | Сохраняет прочий state; чтение bytes, запуск Hydrology/prepare/activate либо выбор следующей операции — отказ |
| PackPreparationValidator | Pure input/state и проверка доступных связей, отдельно final checks над уже прочитанными данными | Нет I/O и самостоятельного capture; несовместимый descriptor/duplicate не проходит |
| PackPreparationOperation | Final verified admission, authoritative closure, принятые storage ports до READY | Не вызывает write_spatial_root и не достраивает shards; root-only retention — отказ |
| PackManifestAssembler | Преобразование проверенного конечного state в manifest | Не выбирает root, не выполняет write и не запускает producer |

Порядок источники → evidence → manifest → codec/readers сохраняется. Перед вызовом должны быть готовы ref и provenance; положение вызова среди других независимых DAG-операций не придумывается. Existing L0/topology и L2/materialize маршруты не переставляются. Изменение чужого producer/caller выполняет его владелец при миграции.

Проверки для реализации: add на пустой состав; A→B для того же domain даёт одну часть; другой payload/proof не изменяется; повтор не мутирует input; same ref с другим provenance не теряется; duplicate state/wrong address/shard-as-root/forged instance отклоняются; pure write не делает I/O; final prepare отклоняет missing shard, wrong world/source/tile и недостающий hold; старый pinned manifest продолжает читать прежний root после замены.

Статус: конкретный Pack-owned метод и поля описаны как PROJECT. Отсутствие spatial write в roster устранено на уровне проекта; общие schema/errors/provenance freeze, artifact composition и final lifecycle остаются открытыми в своих срезах. Это не приёмка runtime или разрешение создавать второй proof/storage механизм.

## Проверка цепочки текущего Pack

Дополнительная статическая сверка по поручению продолжить список Pack: descriptor → pure write → final admission → pinned read. Публичная сигнатура и специализация part присутствуют также в основном write-плане; второй вариант контракта не создаётся.

- Descriptor: existing SpatialDomainRootRef проверяет domain, BLOB kind, format key/version и положительный размер в пределах ROOT_V1.max_bytes. Это проверка ссылки, не semantic decode root. Повторять эти ограничения отдельной расходящейся таблицей Pack нельзя.
- Write: заменяется part только одного domain вместе с provenance; assembly не меняется. Следовательно, describe_metadata/bind_metadata_provenance не должны запускаться из spatial write для искусственно созданной metadata row. Происхождение root находится в part.provenance.
- Final admission: existing finish_pack_preparation добавляет roots, но получает children через other_members; он не доказывает полноту shards. Перед READY registered binding должен выполнить bounded owning decode, проверить world/source_ref и shard tx/ty относительно root entries, включить полный closure в удержания. Успешного bytes format validator недостаточно.
- Read: existing PinnedSpatialReader проверяет root membership в закреплённом manifest и child membership через decoded root; physical admission повторно проверяет удержание manifest. При переносе spatial_roots в parts сохранить эти гарантии и holder children от manifest. Смена head не меняет выбранную pinned версию.

Локальный контракт записи согласуется с принятой границей ответственности Pack; дополнительного открытого pipeline и изменений алгоритма Hydrology не требуется. Полная runtime-приёмка этим не объявляется: semantic/closure binding и production registration проверяются на этапе подключения. Тесты в этой сверке не запускались, код не изменялся.
