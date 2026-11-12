# Pack — публичный release неактивного кандидата

Дата: 2026-11-12. Поручение пользователя: конкретизировать публичный release после [трассировки READY_INACTIVE](pack-inactive-retention-trace.md). Статус PROJECT: Pack-owned контракт описан для приёмки; внутренний atomic binding Artifacts ещё OPEN. Это документальная работа, не разрешение runtime/SQL правок. Write-операции и передача preparation state остаются в [отдельном плане](pack-v2-public-write-operations.md).

## Публичный метод и область действия

Предлагаемый concrete класс `PackCandidateReleasePipelineOpenPipeline` в `backend/app/application/worldData/pack/release/packCandidateReleasePipelineOpenPipeline.py`:

`async release(self, request: PreparedPackCandidate) -> PackCandidateReleaseResult | PackCandidateReleaseRefusal`

Публичный вход — существующий `backend/app/dataModel/worldPack/activation/candidate.py::PreparedPackCandidate(operation_id, manifest: ArtifactRef, preparation_fingerprint)`. Эти три поля не копируются в новый Input. Метод освобождает владение кандидата с durable terminal `PackActivationResult(disposition=READY_INACTIVE)`. READY до активации, ACTIVE (включая исторический ACTIVE, который уже не current head), REJECTED и CANCELLED не обслуживаются этим методом. Их lifecycle не подменяется выбором маршрута внутри release. Прерывание подготовки/cancel и release опубликованной истории остаются отдельными контрактами.

Caller — DAG, прямой вызов этого публичного метода. DAG определяет необходимость release и дальнейшие операции; pipeline делает одну прямую делегацию внутренней `PackCandidateReleaseOperation.release` с той же сигнатурой в `backend/app/application/worldData/pack/release/operation.py`. Публичные вход/выход не содержат CommitScope, lease/fence, backend, callbacks, closure или команды GC. Новый OperationKind и новый release operation_id не вводятся: identity цели — существующий candidate.

## POJO результата и логического отказа

Предлагаемый модуль `backend/app/dataModel/worldPack/release/result.py`:

| Тип | Поля | Смысл |
|---|---|---|
| PackCandidateReleaseResult | candidate: PreparedPackCandidate | Durable владение именно этого кандидата освобождено; повтор возвращает тот же результат. Не обещает physical delete, отсутствие других владельцев или невозможность прочитать тот же ref по другому действующему праву |
| PackCandidateReleaseRefusal | candidate: PreparedPackCandidate; reason: PackCandidateReleaseReason | Валидный запрос не соответствует допускаемому владельцу/состоянию; данный вызов не освобождает владение |
| PackCandidateReleaseReason (StrEnum) | UNKNOWN_CANDIDATE, IDENTITY_MISMATCH, NOT_READY_INACTIVE | UNKNOWN — нет durable операции; IDENTITY — kind/preparation fingerprint/full manifest ref не соответствуют сохранённому кандидату; NOT_READY_INACTIVE — операция существует, но не имеет требуемого terminal disposition |

Все records frozen/strict/extra=forbid/revalidate_instances=always, вложенный candidate также проверяется повторно. Поля EntityUid/RevisionHex/ArtifactRef и их constraints остаются существующими. Для malformed request сохраняются owning field-validation ошибки PreparedPackCandidate; отдельный зеркальный набор field errors не вводится. Перечень field-error POJO и их внешний transport должен быть проверен по общему validation-контракту до приёмки, наличие Pydantic validation само по себе этот gate не закрывает.

`OperationBusyError` переиспользуется для APPLYING/RECOVERY_REQUIRED либо неподтверждённого завершения writers. Infrastructure/cancellation/unknown commit сохраняют существующие owning типы; не становятся UNKNOWN_CANDIDATE или успешным release. Способ восстановления неизвестного результата именно release должен предъявить внутренний binding: historical terminal активации не доказывает commit release.

## Identity, атомарность и повтор

1. Pure admission повторно валидирует request. Внутренняя операция сверяет durable record: OperationKind.PACK_ACTIVATION, operation_id/preparation_fingerprint, terminal READY_INACTIVE и полный terminal.manifest == request.manifest. Мир берётся из record/terminal.publication; новый независимый world_uid входа не нужен. World head не меняется и не используется как замена исторической identity кандидата.
2. Проверка допуска и освобождение выполняются под принятой внутренней атомарной границей, защищённой от конкурентных acquire/release/GC. Предварительный read без такой защиты недостаточен. Из durable binding выводится точный владелец кандидата; caller не выбирает fence.
3. Освобождается только root ownership этого кандидата. Общие связи manifest → children нельзя снимать по одному факту release A: должны сохраняться все права B, publication, pin и history. Владение closure/очисткой принадлежит Artifacts; Pack не обходит children с самостоятельными release и не реализует GC. Условие последнего владельца и атомарный cleanup общих связей входят в требования внешнего binding.
4. Existing holder event chain — кандидат на durable evidence release, а не новый receipt store. Успех первого вызова подтверждается завершённым commit. При повторе проверяются та же identity и сохранённый факт освобождения конкретного владельца, после чего возвращается тот же PackCandidateReleaseResult. Отсутствие hold без доказанного release — нарушение storage-инварианта, не идемпотентный успех.
5. Повтор после удаления физических bytes не должен требовать decode payload, повторный seal или восстановление hold. Binding должен сохранять достаточно metadata/history для проверки полного candidate. Если existing catalog/history этого не гарантируют, это конкретный внешний gap, а не повод добавить Pack-owned журнал.
6. Исторический activation terminal неизменяем. Release не записывает туда CANCELLED/REJECTED и не получает новый publication claim. Replay activate после release возвращает прежний READY_INACTIVE и не приобретает владение заново. Получение нового кандидата/попытка новой активации — решение DAG через соответствующие контракты.

## Ответственность классов и проверка дублей

| Класс | Ответственность / зависимости / эффекты | Отказ в приёмке |
|---|---|---|
| PackCandidateReleasePipelineOpenPipeline (проект) | Публичный direct DAG entry, одна делегация PackCandidateReleaseOperation | Выбор cancel/activate/GC, retry loop, запуск через worker/callback вместо DAG |
| PackCandidateReleaseOperation (проект) | Admission candidate и Pack policy; один внутренний согласованный release binding Artifacts/publication; формирование публичного результата | Прямой вызов публичного чужого домена, отдельный ledger, head mutation, обход дочерних refs с неатомарными release |
| PreparedPackCandidate (existing) | Единственная identity результата подготовки и вход release | Копия его полей/validators в зеркальном Input; раскрытие lease |
| PackCandidateReleaseResult/Refusal/Reason (проект) | Состояние освобождения владения / логический отказ конкретной Pack операции | Приравнивание к physical deletion, cancel или historical activation outcome |
| OperationRecord / PackActivationResult (existing) | Durable identity и исторический исход, внутренние данные проверки | Выдача всего OperationRecord вместо публичного результата; изменение terminal при release |
| SqliteArtifactHolders / SqliteArtifactCatalog (existing, Artifacts) | Exact holds, event chains, storage admission и GC protection; будущий binding переиспользует их у владельца | Pack копирует SQL/holder policy; existing release(ref, holder) выдаётся за доказанный полный atomic candidate release |

Поиск release-result типов в backend/app/dataModel не выявил готового Pack release результата. OperationCancelled сообщает об отмене операции, PackActivationResult — о результате активации, ArtifactHolderRef — о внутреннем владельце: ни один не является публичным подтверждением освобождения неактивного кандидата. Новые result/refusal не копируют их поля и семантику; используют existing candidate. Полная проверка новых типов и field/logic errors по обязательным критериям остаётся частью gate, а не объявляется выполненной одним поиском.

## Внешний binding и критерии приёмки

Подтверждены existing `IArtifactHolders.release(ref, holder)`, `SqliteArtifactHolders.release`, `OperationLedger.read/recover`, holder event chain. Не подтверждён принятый единый scoped method, который проверяет terminal candidate identity, снимает его владение, безопасно обрабатывает shared closure и восстанавливает release outcome. Имя/сигнатура этого внешнего метода здесь не объявляются existing и его разработка не назначается Pack. Разрешение использовать terminal OperationHolder как долгоживущий root также требует owning фиксации.

Требуемая входная связь: existing PreparedPackCandidate → exact durable OperationRecord/PackActivationResult → конкретное удержание root. Выход binding должен различать подтверждённое освобождение (включая replay), отсутствие кандидата, несовпадение identity и недопустимое состояние, сохраняя infrastructure/unknown outcome отдельно. Пока такого concrete Input/Output/Error и ownership atomic scope нет, реализация release зависит от внешнего контракта. Публичный Pack проект можно обсуждать отдельно; полная приёмка этого среза пока OPEN.

Приёмка: A/B с общим manifest → release A сохраняет B и closure; повтор A возвращает равный результат; release B сохраняет права pin/history; неправильный ref/fingerprint/kind ничего не освобождает; READY/ACTIVE/REJECTED/CANCELLED не запускают другой workflow; APPLYING/RECOVERY_REQUIRED не изменяются; rollback не оставляет частичного освобождения; потерянный ответ после commit восстанавливается после restart; GC bytes не ломает replay identity; activate replay не восстанавливает hold. Ни один сценарий здесь не обозначен пройденным тестом.
