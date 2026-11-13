# Повторная приёмка A3 — Pack metadata exchange

2026-11-14. **Вердикт: A3 НЕ ПРИНЯТ.** Это документальная проверка, не независимая агентская приёмка и не runtime review. Проверен текущий проект после уточнения размещения binding и empty policy. Код не менялся, тесты не запускались. Основание отказа — два конкретных противоречия ниже, не отсутствие runtime реализации или внешних миграций.

## Незакрытые замечания

### A3-R1. Четыре semantic кода не синхронизированы с owning ТЗ

[ТЗ Pack, errors.py](../../docs/tz_world_pack_storage.md) содержит явный перечень PackPreparationIssueCode (на момент проверки строка 377). В нём нет METADATA_GROUP_MISMATCH, METADATA_ATTRIBUTION_UNAVAILABLE, METADATA_INPUT_MISMATCH, METADATA_BASIS_MISMATCH. [A3 mapping](pack-source-error-identity-contract.md#2-предлагаемая-точная-диагностика-exchange) требует эти коды, в том числе для нового отказа на empty fields/entries. [Metadata POJO §5](pack-metadata-dependency-pojo.md#5-admission-ошибки-и-старая-база) всё ещё называет их предложениями до приёмки.

Следствие: реализация по ТЗ и по exchange получает разный публичный enum ошибок. Одного отсутствия дублей diagnostic classes недостаточно для freeze. Нужно синхронизировать четыре значения и их predicates с owning ТЗ и статусами профильных планов, сохранив существующий diagnostic union. Новая модель ошибки не нужна. Это локальная Pack-задача, не запрос нового Source API.

### A3-R2. Противоречивый перенос Source отказа

[Metadata POJO §5](pack-metadata-dependency-pojo.md#5-admission-ошибки-и-старая-база) предписывает перевод owning admission failure в Pack diagnostic; следующий абзац разрешает Source validation failures → SOURCE_PROOF_MISMATCH. [A3 §3](pack-source-error-identity-contract.md#3-оболочки-и-ответственность-классов) и [leaf §3](pack-source-leaf-contracts.md#3-ошибки-и-mapping) требуют сохранять SourceFailure в SourceNodeError и не вызывать import/bind после failed Source CALL.

Следствие: один owning отказ может получить двух разных владельцев и два error-domain mapping. Исправление — в metadata-плане разделить (а) Source operation failure, сохраняемый на Source leaf без зависимого Pack вызова, и (б) Pack локальное несоответствие успешно переданного input/state, диагностируемое через SOURCE_PROOF_MISMATCH. Pack не проверяет subset/union и не конвертирует SourceFailure. Это согласование уже выбранного пути, не новое архитектурное решение.

## Проверка всех обязательных критериев

Scope A3 — формы metadata exchange и их ошибки. Полный DAG route, production trust, publication и prepare lifecycle остаются отдельными пунктами. Использованы [обязательные критерии](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена).

| Критерий | Источник и вывод |
|---|---|
| Нет выбора следующей стадии в домене | Exchange §§1–2: describe/import/bind — одна локальная pure операция. Failure прекращает её без следующего вызова. В пределах A3 соблюдено |
| Нет скрытой orchestration | Leaf contracts §1: одна публичная операция на leaf; caller/order — first-route-review §2. Новый callback/worker/fallback не вводится. Production binding ещё A1/A2/A4 |
| Нет прямых междоменных вызовов | Exchange header и §§1–2: Pack получает Source DTO через DAG, Source API/helper не вызывает. Соблюдено на уровне предлагаемого маршрута; A3-R2 противоречит переносу ошибок, а не разрешает такой вызов |
| Ответственность каждого класса | A3 §3, metadata POJO §2, exchange §§1–2: records — данные; service — Pack predicates; shared structural classes — shape; SourceNodeError — Source outcome; PackPreparationNodeError — Pack outcome; aggregator — независимые issues. Роль и модуль binding уточнены, но единый error mapping не выполнен из-за A3-R2 |
| Public / OpenPipeline / implementation | Leaf §§1–3 и exchange §§1–2 задают service methods и named inputs/results; не раскрывают Source алгоритм. Typed error enum не совпадает с ТЗ — A3-R1, исходы противоречат — A3-R2 |
| Неизменность утверждённого порядка | First-route-review §2: семь шагов. Empty usage input отвергается; неожиданно пустой describe не позволяет пропустить SELECT/import и перейти к write. Порядок не изменён |
| Данные Create | A3 не вводит отдельный create; создание immutable результата import/bind относится к Update. start/capture creation этим review не принимаются |
| Данные Read | describe_metadata_usage_requests и describe_metadata имеют named input и typed output; Source SELECT/ADMIT_GROUPS описаны owning контрактом. Ошибки новых usage операций не freeze по A3-R1/R2 |
| Данные Update | import/bind возвращают новый state, без partial mutation; точные paths, duplicate groups/address, world/basis/empty checks в A3 §2. Error contract требует двух исправлений |
| Данные Delete | Удаление не входит в A3, новый метод или изменение delete не предлагаются; полная CRUD приёмка Pack не заявлена |
| Настройки Create | Не вводятся; создание binding configuration не относится к A3 |
| Настройки Read | Новых reads/settings не требуется; действующие исключения не пересматриваются |
| Настройки Update | Не вводится hot-update; A3 не меняет manifest budget или другие settings |
| Настройки Delete | Не используется и не проектируется |
| Междоменный CRUD протокол, шаг 1 | Exchange §§1–2: Pack import/bind — потребитель, Source select/admit_groups — владелец данных proof/usage; никакой записи Source из Pack |
| Протокол, шаг 2 | Source contract §6.0 и source-pack-exchange-response-2026-11-13 подтверждают request/result поля. SourceFailure единый, но consumer mapping противоречит ему — A3-R2 |
| Протокол, шаги 3–4 | First-route-review и leaf contracts показывают DAG transfer по порядку; зависимая production registration/restore остаётся A1/A2/A4. Правило допускает отдельную доменную конкретизацию, не полную route-приёмку |
| POJO и типизированные field/logic errors без дублей | Единственный binding в metadataDependencies.py; subject existing, provenance reused; shared JsonFieldError/WireShapeIssue и named FieldPathError subclass сверены с кодом. Новые carriers не нужны. Объявления кодов/владение отказом пока не едины — A3-R1/R2 |

Сверены existing metadataSubject.py, validation/importIssues/jsonFieldError.py, wireShapeIssue.py, validation/diagnostics/fieldPathError.py и проектная PackPreparationFailure(error). По ТЗ exception размещается в application/worldData/pack/preparation/errors.py, а enum/diagnostic POJO — в dataModel/worldPack/preparation/errors.py: эти два слоя не объединять при реализации.

## Что уже исправлено и не открывается повторно

Одна пяти-полевая bind-форма, единый owning модуль, describe возвращает descriptions, empty usage input получает адресный отказ, допустим SELECT всего proof, проверяются duplicate metadata address, мир и порядок groups. Это проверенные локальные исправления; отказ в приёмке их не отменяет. PACK-METADATA-PLANNING сохраняет разрешённую неблокирующую отсрочку.

Следующий шаг: устранить A3-R1/R2, затем повторить проверку согласованности owning ТЗ и error mapping; не начинать новый выбор Source proof или DAG порядка. Приёмка всего маршрута остаётся отдельной даже после закрытия A3.
