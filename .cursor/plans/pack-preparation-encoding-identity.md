# Pack prepare — связь identity с manifest encoding

Перенесено 2026-11-13 в [отдельный план сериализации/десериализации](pack-serialization-deserialization.md). Ниже сохранён вариант решения, не самостоятельный блокер текущего Pack и не принятое решение о новой revision. Выбор и приёмка выполняются в новом плане.

2026-11-13, PROJECT для согласования. Runtime и owning ТЗ не изменены. Закрывает проектное направление F2 из [сверки цепочки](pack-lifecycle-chain-review.md), не добавляя candidate store или новую публичную стадию.

## Найденный пробел

Write-план описывает preparation_fingerprint как digest полного semantic body. Manifest envelope/serializer выбираются внутренним binding. Одинаковый body после изменения этого binding может дать другие bytes и ArtifactRef. Existing encode_candidate_manifest использует model_dump_json(indent=2): порядок/форма сериализации также влияют на bytes. Само равенство body fingerprint не гарантирует старый manifest ref. Current helper сравнивает stage ref с вычисленным digest, но не реализует READY replay.

## Предлагаемая identity

PackPreparationIdentityCodec использует существующий canonical digest над `(preparation_contract_revision, OperationKind.PACK_ACTIVATION, body)`. Revision — внутренняя constant Pack preparation-контракта, не параметр DAG; первая версия нового контракта предлагается равной 1. Это отдельная revision от activation identity. Operation_id и предъявленный preparation_fingerprint не входят в собственный digest. Body остаётся единственным составом state/capture/scope/согласованного evidence; новая копия его полей не создаётся.

Revision закрепляет совместный контракт: shape/canonical IDs body, pure assembly rules, manifest wire/storage descriptor, сериализацию и её порядок/defaults. Смена любого из этих свойств, меняющая получаемые bytes или смысл, требует изменения revision. Runtime resource caps не включаются в identity: нехватка ресурсов попытки не должна менять identity данных. Новые numeric defaults лимитов не назначаются.

Правило revision — требование совместимости, не автоматическое доказательство детерминизма. Для каждой поддержанной revision нужны фиксированные body→manifest bytes/ref vectors; если реализация меняет bytes без смены revision, это дефект и приёмка не пройдена. Внешний proof/capture не подменяется snapshot текущего registry; если owning контракты не обеспечивают стабильное кодирование, зависимый prepare binding остаётся незавершённым.

## READY replay

1. Повторно проверить typed request и вычислить fingerprint закреплённым поддержанным binding, сверить предъявленный fingerprint и durable operation identity. При несовпадении — существующий identity conflict до staging, без reopen и перепривязки старого ID.
2. При READY построить manifest тем же pure assembler из конечного state, без повторного write/generate/bind и latest lookup. Кодировать тем же закреплённым manifest encoder, применить бюджет; получить полный ожидаемый ArtifactRef через existing content_digest/len и owning descriptor.
3. Проверить наличие exact ref в leased_artifacts; под owning guard проверить seal/hold и verified bytes. Сверить полный требуемый closure с подтверждённым набором. Совпадение только digest или format недостаточно.
4. Вернуть PreparedPackCandidate с теми же operation_id/ref/preparation_fingerprint. Reserve/stage/seal/finish_preparation не вызываются. Если matching ref отсутствует, не брать другой manifest и не исправлять record.

Если deployment поддерживает только новую revision, старый body/fingerprint не совпадёт: операция отклоняется, а не выдаёт новый candidate под прежним ID. По одному digest нельзя достоверно определить, причина ли в старой revision или изменённых данных; не обещать отдельную точную ошибку «unsupported revision» без доступного version binding. Автоматический перебор старых codec, новый version-selection endpoint или поддержка исторических revisions этим предложением не вводятся. Terminal replay activate — отдельный путь; он не пересобирает manifest через prepare.

## Приёмка и согласование

Нужны проверки: тот же body/revision после restart даёт тот же manifest ref; изменение bytes/descriptor требует новой revision и меняет fingerprint; новое resource cap не меняет identity; потеря ответа READY не вызывает writes; второй подходящий по format ref не выбирается; forged request не достигает codec; недостаточный бюджет не возвращает candidate. Доступность refs/atomic adoption остаётся в owning Artifacts binding.

Предлагается согласовать добавление внутренней preparation revision в fingerprint. После этого синхронизировать формулу write-плана/ТЗ. Полный контрольный вектор подготовки пока не вычисляется: concrete body/proof schema ещё не зафиксирована. Это не изменение старой генерации, порядка updates или source ownership.
