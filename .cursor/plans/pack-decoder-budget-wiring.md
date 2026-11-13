# Pack: передача output cap в format admission и read

Статус PROJECT, REV-02. Только документация; продолжение [bounded zstd проекта](pack-zstd-output-binding.md). Численные настройки не выбираются заново.

## Existing trace

[ArtifactFormatContract](../../backend/app/application/artifacts/contracts/formatBackend.py) содержит pure `encode(content)` и `decode(bytes, version)` без request budget. Уже есть пример захвата явного лимита при создании binding: [manifest_format(max_bytes)](../../backend/app/application/worldData/pack/encoding/manifestFormat.py).

Climate сейчас отличается: [CLIMATE_FIELD_FORMAT](../../backend/app/application/worldData/pack/encoding/climateFieldFormat.py) — глобальный экземпляр без output cap; его encode/decode вызывают decode_climate_field. [ContentAddressedBlobBackend.write](../../backend/app/storage/artifacts/blobBackend.py) вызывает contract.encode до записи. `read_verified` проверяет physical bytes, но не выполняет semantic decode; `verify` тоже нельзя считать полным climate admission.

[PacksWiring.register_climate_field_format](../../backend/app/core/container/packs.py) регистрирует глобальный контракт. [ArtifactFormatRegistryBinding](../../backend/app/application/artifacts/registry/artifactRegistry.py) требует identity объекта: backend.contract is contract при register и тот же экземпляр при resolve. Повторная фабрика с равными key/version не эквивалентна уже зарегистрированному contract.

[StagedClimateFields](../../backend/app/application/worldData/pack/encoding/stagedClimateFields.py) проверяет `backend.contract is CLIMATE_FIELD_FORMAT`, читает bytes и вызывает отдельный decode_climate_field без cap. Значит изменение только read_part или только format factory оставляет неподключённый путь либо ломает identity check.

Согласование владельцев 2026-11-13: этот документ описывает механизм передачи согласованных лимитов, а не право Pack назначать новые пределы формата. Значения и источник недостающего профиля определяются с владельцем payload; общий перенос всех profiles в world_pack снят. Существующие Hydrology limits и Pack request IO budget сохраняются. См. [решение](pack-budget-enforcement.md#источники-значений-сверка-2026-11-13).

## Concrete target для climate

В `encoding/climateFieldFormat.py` проектируется один внутренний `ClimateFieldCodec`:

| Член | Назначение |
|---|---|
| `__init__(*, max_output_bytes: int)` | Захватывает positive strict int на весь lifetime. Никаких defaults, live settings lookup или IO |
| `contract: ArtifactFormatContract[bytes]` (read-only) | Один экземпляр, созданный при construction. Существующие key/kind/version/content_model сохраняются |
| `decode_payload(payload: bytes) -> ClimateFieldWire` | Existing header/kind/schema проверки и bounded TileCodec.decode с захваченным cap |
| Internal callbacks contract.encode/decode | Проверяют bytes/version, вызывают тот же decode_payload, возвращают исходные exact bytes; не re-encode и не меняют hash |

Это implementation class, не публичный pipeline, settings service или новый payload POJO. Единственное новое configuration поле — захваченный output cap; ArtifactFormatContract и ClimateFieldWire переиспользуются. Per-call zstd context не разделяется между конкурентными декодированиями. Дублирующая неограниченная реализация decode_climate_field не остаётся после миграции callers.

Composition создаёт codec один раз, передаёт `codec.contract` в ContentAddressedBlobBackend и регистрирует **этот же** contract/backend. Тот же codec передаётся в StagedClimateFields; target constructor: `StagedClimateFields(backend: ReadableBlobBackend, catalog: IArtifactCatalog, holders: IArtifactHolders, *, codec: ClimateFieldCodec)`. Constructor сверяет `backend.contract is codec.contract`, validate вызывает codec.decode_payload. Public part-read climate adapter получает тот же codec через composition. Не создавать новый экземпляр контракта на каждый request.

Таким образом producer stage через contract.encode, storage contract.decode, candidate climate admission и public payload read используют одну политику output limit. Pure codec не вызывает backend; StagedClimateFields остаётся I/O admission, read operation владеет pin/guard/request accounting. Никаких публичных междоменных вызовов из codec или Pack pipeline.

## Что именно передаётся и что не меняется

PackPartReadBudget остаётся request encoded-IO budget из четырёх полей. Захваченный format output cap — другая величина; не брать его из max_payload_bytes, ref.nbytes или CachePolicy capacity. Его нельзя ослабить значением caller request.

Startup composition должна передать явное значение в codec constructor до регистрации формата. Конкретное поле persisted configuration/число ещё не предъявлено: этот документ **не добавляет** ключ в WorldPackCacheSettings и не назначает default. [Settings disposition](pack-settings-crud-disposition.md) сохраняет source/lifetime решения и формальный остаток приёмки. Для создания ограниченного climate binding отсутствие аргумента является configuration error; изменение поведения всего startup при неполной конфигурации отдельно не принимается.

Для остальных payload используется тот же принцип owning format binding с захваченным cap и общий bounded TileCodec, без создания общего зеркального PackLimits DTO. Settlement передаёт единый остаток всем frames. Manifest/grade slots plain bytes cap и existing Hydrology DecodeLimits сохраняют свои единицы и владельцев. Миграция legacy WorldPackReader/Writer должна удалить неограниченные decode callers; producer orchestration не переносится в Pack.

## Приёмка и остаток

[Trace обязательности admission](pack-climate-preparation-admission.md) подтверждает: existing finish_pack_preparation уже отвергает отсутствие climate_fields при climate refs до stage/finish. Остаток — production binding и миграция final-state parts; optional аргумент сам по себе не является bypass.

Реализация должна проверить: oversized climate отвергается при contract.encode до записи и при read до JSON parse; один payload одинаково принимается/отклоняется storage admission и candidate/read; два отдельно созданных contract не проходят registry identity; неверный codec/backend отвергается constructor; bytes/hash не меняются; typed ZstdOutputLimitError не теряется в callbacks; нет повторного чтения settings внутри decoder. Existing optional StagedClimateFields в подготовке кандидата не доказывает production wiring: этот путь нужно проверить отдельно.

Новые численные output/window caps требуют обоснования допустимыми payload и измерениями; тесты здесь не запускались. Обязанности нового implementation class перечислены, public contract не расширяется, CRUD и схема ошибок не дублируются. DAG по-прежнему выбирает операции; порядок sources → evidence → manifest → codec/readers неизменен. Статус остаётся PROJECT до реализации, проверки callers и общей приёмки. Не объявлять выбор wiring согласованным исключением из settings CRUD.
