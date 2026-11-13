# Pack: обязательность climate admission при подготовке

Статус: статический trace REV-02; existing гарантия отделена от target migration. Runtime не изменён, тесты в этом срезе не запускались.

## Existing: optional dependency не означает optional validation

[finish_pack_preparation](../../backend/app/application/worldData/pack/encoding/preparedManifest.py) имеет `climate_fields: StagedClimateFields | None = None`, но при непустом `manifest.climate_artifacts()` отсутствие admission приводит к ValueError. Manifest не staged, finish_preparation не вызывается. Следовательно, новое решение «сделать climate admission обязательным при наличии climate» не требуется: это уже поведение helper.

[WorldPackManifest.climate_artifacts](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py) собирает coarse ref и все fine refs, независимо от status, затем устраняет одинаковые refs. Status не разрешает скрыть существующий ref. [StagedClimateFields.validate](../../backend/app/application/worldData/pack/encoding/stagedClimateFields.py) проверяет каждый адрес: sealed ref и OperationHolder текущей lease под guard, verified bytes, decode, coarse/fine role и origin fine относительно tile. Разделяемый ref проверяется для каждого контекста адреса; дедупликация retention не разрешает пропустить role/origin validation.

Фактический порядок helper: lease/world/kind и self-digest checks → encode_candidate_manifest → сбор members/roots/climate refs → climate admission → manifest stage → проверка descriptor/hash/nbytes → finish_preparation → сверка READY, identity/fence/fingerprint и точного множества leased artifacts → PreparedPackCandidate. Encode до admission — pure работа, не durable запись. Этот trace не является разрешением переставлять утверждённые стадии target-плана.

Manifest без climate refs проходит этот локальный участок без climate dependency. Из этого не следует допустимость любого такого manifest по target scope/coverage: эти правила проверяются отдельно, новые глобальные требования иметь coarse/fine здесь не вводятся.

## Что доказано тестовым кодом, а что не подключено

[test_climate_field_format](../../backend/tests/spatial_pack/test_climate_field_format.py) создаёт StagedClimateFields явно и передаёт его helper; wrong coarse/fine role и wrong origin проверяются с `stage.assert_not_awaited()`. Затем используется кандидат с climate в retention/restart/GC сценарии. Это прочитанные тесты, не результат их запуска в этом срезе.

По поиску `finish_pack_preparation` и `StagedClimateFields(` в Python-файлах backend найдены definition/import и тестовые calls; production construction/call в `backend/app` не найден. [PacksWiring](../../backend/app/core/container/packs.py) регистрирует climate backend, но регистрация сама по себе не подключает candidate admission. Поэтому нет основания объявлять production-маршрут защищённым только по наличию helper.

Также seal/physical backend.verify не доказывает role/origin соответствие candidate. [ContentAddressedBlobBackend](../../backend/app/storage/artifacts/blobBackend.py) проверяет physical size/hash; contextual Pack admission нельзя заменить этой проверкой.

## Target Pack: сохранить гарантию, мигрировать представление

В final prepare из [write-плана](pack-v2-public-write-operations.md) проверять climate parts конечного state, включая inherited/retained refs, а не только список новых write calls. Target refs берутся из parts по coarse/fine address; legacy `climate_coarse_ref`/`tiles[].climate_fine_ref` не становятся вторым источником истины.

Состав обязательных проверок сохраняется: допустимый descriptor → удержание/seal через согласованный lifecycle port → bounded decode → role/address/origin → прочие target provenance/scope/coverage проверки → stage manifest и finish. Конкретный retention/adoption для inherited refs определяется existing preparing contracts, а не переносом предположения «любая чужая ref уже принадлежит OperationHolder». Caller-supplied other_members не считается доказательством полной target closure.

При отсутствии требуемой configured admission dependency prepare не выдаёт READY/candidate и не делает новый stage manifest. Dependency предоставляется composition; Pack pipeline не выбирает генератор climate, не запрашивает latest Source и не восстанавливает недостающий payload. [Budget wiring](pack-decoder-budget-wiring.md) передаёт один configured ClimateFieldCodec storage и contextual admission; обязательность проверки не решает отдельно численные output limits.

Это внутренний валидатор одной Pack prepare-операции, не новый публичный pipeline. Его проверка наличия refs/валидности не выбирает следующую доменную операцию; последующие действия выбирает DAG. Pure preparation methods не получают backend/callback. Новых DTO/CRUD/settings сервисов и дублей payload/errors не вводится; error mapping final prepare не подменяется read-part refusal.

## Приёмка и остаток

Локальный вопрос обязательности **подтверждён существующим кодом**, новую boolean-настройку/флаг skip validation добавлять не нужно. Для target реализации нужны: отсутствие admission при refs прекращает подготовку до stage/finish; без refs не запрашиваются climate bytes; проверки retained refs и всех адресов shared ref; неверные hold/seal/role/origin/budget не дают candidate; фактический production caller не обходит final admission.

Production binding, parts migration, full closure/lifecycle и численные decoder caps остаются OPEN. Отдельный тест missing dependency полезен для фиксации существующей гарантии, но его отсутствие не доказывает обход видимой проверки. Общая приёмка Pack этим trace не закрывается.
