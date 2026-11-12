# Pack delete_part — проект удаления адреса из нового состава

2026-11-12. Только контрактный проект после статического trace, без runtime/SQL/DAG изменений. Связь: [write-план](pack-v2-public-write-operations.md), [остаток приёмки](pack-local-acceptance-status.md), [release кандидата](pack-candidate-release-contract.md).

## Основание и предел

В [WorldPackWriter](../../backend/app/application/worldData/pack/io/worldPackWriter.py) отдельного метода удаления payload-part не найдено. Замена индекса пустым содержимым и удаление всего кандидата имеют другой смысл. [ТЗ Pack](../../docs/tz_world_pack_storage.md), описание parts, разрешает отсутствие/удаление только с проверкой scope и индексов; это не разрешение произвольного каскадного удаления связанных данных. По принятому write-плану отсутствие write-вызова сохраняет базовую часть — оно не выражает удаление.

Ниже предлагается явное удаление одного logical address из промежуточного state. Это новое объявление целевого API, не заявление о legacy parity. Оно не закрывает автоматически весь CRUD: для ролей с обязательной metadata требуется отдельная согласованная семантика её изменения.

## Публичный контракт

Конкретный существующий проектный класс `PackPreparationService` в `backend/app/application/worldData/pack/preparation/packPreparationService.py` получает метод:

`def delete_part(self, request: PackDeletePartInput) -> PackPreparationState`

`PackDeletePartInput` в `backend/app/dataModel/worldPack/preparation/operations.py` содержит ровно:

- `state: PackPreparationState` из preparation/state.py;
- `address: PackPartAddress` из preparation/addresses.py.

Это одна операция над адресом, не execute(kind) и не выбор следующего доменного workflow. PackPartAddress — уже предложенный discriminated union именованных адресов; bool cascade, список команд, callbacks, backend, ArtifactRef для физического удаления и отдельный world_uid не добавляются. Request strict/frozen/extra=forbid с повторной проверкой вложенных экземпляров.

Caller — DAG, напрямую вызывает метод и передаёт результат следующей выбранной операции. Метод синхронный и pure; отдельный pipeline-wrapper или storage service не создаётся. Результат использует тот же PackPreparationState; второй DeleteState/receipt не нужен.

Отказы используют общий проект PackPreparationError/PackPreparationIssue в `dataModel/worldPack/preparation/errors.py` и PackPreparationFailure в `application/worldData/pack/preparation/errors.py`. Структурные ошибки следуют общему незавершённому mapping write-плана; новые зеркальные DeleteFieldError/DeleteLogicError не вводятся.

## Локальная семантика — предложение для приёмки

1. Проверить request, state и address, включая strict nested admission и уникальность существующих parts. Повреждённый state с дубликатами отклоняется через общий DUPLICATE_ADDRESS, а не исправляется удалением всех копий.
2. Удалить единственный PackStoredPart с точным address, включая его встроенный provenance. Не удалять по content hash: один artifact может использоваться несколькими адресами с разным provenance.
3. Остальные parts, base_publication, assembly и assembly_provenance сохранить без изменений. Удаление отсутствующего адреса предлагается как идемпотентный no-op после полной локальной проверки request/state; это не найденная legacy policy и не утверждение, что публикация такого state допустима.
4. Вернуть immutable state. Не читать blob/base, не снимать holds, не менять head, не вызывать prepare/activate/release и не вычислять новую metadata policy.

У каждой операции новый state относится к той же pinned base. Удаление не стирает часть из исторического manifest. Последующий write того же адреса снова добавляет готовую часть по своему контракту; порядок вызовов задаёт DAG. До READY итоговые counters вычисляются по конечному составу, не уменьшаются ручным счётчиком в delete.

## Связанные данные и final admission

| Роли | Что delete_part не имеет права делать автоматически | Оставшееся условие финального состава |
|---|---|---|
| spatial_root | Удалять shard bytes, изменять Hydrology или старый manifest | Scope допускает отсутствие доменного root; closure пересчитан по всем оставшимся parts/proofs, shared shards сохранены при других основаниях |
| tile_grade_slots / location_grade_slots | Генерировать пустой payload либо восстанавливать коды из z | Отсутствие допустимо только по принятому coverage; отсутствие не равно валидному пустому sidecar |
| map_tile | Удалять весь tile вместе с climate/chunks | Связи tile assembly, grid и coverage проверены; отдельная политика удаления tile metadata ещё не определена этим методом |
| wilderness_chunk | Удалять chunk metadata, пересчитывать status по новой неутверждённой policy | Для согласованного изменения предложен отдельный [delete_wilderness_chunk](pack-delete-wilderness-chunk-contract.md), сохраняющий existing provisional policy; общий metadata-output freeze ещё OPEN |
| climate_fine / climate_coarse | Понижать fine→coarse, пересчитывать климат или выбирать fallback | Для fine предложен отдельный [delete_fine_climate](pack-delete-fine-climate-contract.md); coarse не генерируется. Удаление coarse не сбрасывает все fine tiles; допустимость отсутствия определяется scope/coverage |
| location_terrain / settlement | Удалять локацию/поселение, TerritoryVolume, district metadata или pins | Связанные metadata/indexes и их provenance согласованы; простое удаление ref этого не доказывает |
| locations_index | Подменять отсутствие пустым индексом, перенумеровывать pins в map_tile | Обязательность индекса и ссылки location_pin удовлетворены. Замена на пустой индекс — другая existing write-операция |

Это не маршрутизация по ролям внутри delete: локальный алгоритм един, role-specific invariants проверяются общим final admission. Промежуточная неполнота допускается по write-плану, но не разрешает выдавать READY с разорванной связью. Если в публичном roster нет нужной операции согласования metadata, сценарий удаления этой роли остаётся OPEN; caller не получает mutable assembly и не редактирует её вручную.

`PackPreparationOperation` проверяет итог относительно проверенной pinned base, scope и требуемого evidence. Изменение вне scope даёт OUT_OF_SCOPE_CHANGE; обязательный отсутствующий payload/несогласованный статус — существующие MISSING_PART/STATUS_MISMATCH по проверенной причине. Число оставшихся элементов не доказывает допустимость удаления. Не добавлять фиктивный proof для отсутствующего blob: mapping evidence удаления относится к scope/изменению состава и требует конкретного принятого контракта.

## Ответственность и проверки

PackDeletePartInput задаёт только typed boundary, PackPreparationService выполняет одно pure изменение, PackPreparationValidator проверяет структуру и локальные инварианты. PackPreparationOperation выполняет окончательный scope/consistency/retention admission через принятые внутренние ports; PackManifestAssembler кодирует проверенный конечный состав. Любой вызов генератора, другого публичного метода, filesystem delete, GC или обход детей из delete_part нарушает ответственность.

Проверки для реализации: удалить A, сохранив B/ref/provenance; A и B с одинаковым ref — удалить только A; повтор no-op; invalid/duplicate/forged state отклоняется; вход не мутирует; никакого I/O; delete→write восстанавливает только адресованную часть; неподтверждённый scope и dangling metadata не дают READY; старый pin сохраняет доступ; общий shard не теряется при удалении одного root из нового состава. Тесты здесь не запускались.

Порядок источники → evidence → manifest → codec/readers, публичные DAG-вызовы и отдельный release lifecycle сохраняются. Статус PROJECT: конкретный primitive удаления описан; полная приёмка D остаётся открытой по ролевым metadata/scope сценариям и общему error freeze. Это не разрешение реализации или публикации неконсистентного state.
