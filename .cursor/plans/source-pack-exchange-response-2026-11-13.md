# Source: ответ на Pack consumer exchange

2026-11-13. Уточнение принятого Source API по source-proof-v2-contract-spec.md §§6.0, 11–12. Проверен pack-source-exchange-contract.md. Это не приёмка Pack signatures, DAG binding или runtime; Source proof schema не изменяется.

## 1. SELECT result → заявленный usage

Да: после успешного SELECT допустимо создать SourceProofInput(world_uid=result.proof.world_uid, uses=result.proof.uses). Это механическое копирование owning значений, не вычисление subset в Pack. Input снова является заявленным usage, а не удостоверением выполнения SELECT. Исходная selection остаётся привязанной к исходному общему proof; переносить её на subset proof нельзя. Empty selection даёт пустой usage своего мира; это не доказывает независимость поля от Source.

## 2. Exact correspondence SELECT

Принятый API не имеет отдельного verify_select(request, result). Связь полученного результата с реально исполненным SELECT должна обеспечиваться согласованным execution binding DAG и неизменностью соответствующего Pack state. Пара caller-created requested/result и их структурная валидность этого не доказывают. Source такой binding ещё не принимал.

На недоверенной границе существующий способ — исполнить SELECT через DAG над запросом, сверенным Pack с текущей attribution, и передать непосредственно его успешный результат. Повторное использование предъявленного результата без такого исполнения/доверенного binding не поддержано. READ результата подтверждает Source корректность самого subset proof, но не его соответствие исходной selection. VERIFY_GROUPS не является заменой exact select verification. Новый token/store/helper или endpoint не требуется автоматически и здесь не вводится.

## 3. ADMIT_GROUPS / VERIFY_GROUPS и bind

Да: при принятом доверенном execution path достаточно успешного ADMIT_GROUPS для exact source_request. VERIFY_GROUPS не обязателен вторым вызовом. Для предъявленного недоверенного grouped result применим SourceProofGroupsVerifyInput(expected=source_request, result=source_result); в bind передаётся успешный output VERIFY_GROUPS, а не непроверенный исходный carrier.

Source сохраняет позиции groups/selections; разные группы могут иметь одинаковые selections. Pack проверяет exact текущие ordered usages, subject/basis и связь общего proof с provenance; Source проверяет canonical union/selection semantics/closure. Source не подтверждает полноту фактических чтений producer и правильность metadata algorithm. Доверие к исполнению VERIFY_GROUPS требуется так же, как к исполнению ADMIT_GROUPS.

## 4. READ и полный closure перед prepare

Форма SourceProofReadInput → SourceProofResult соответствует API. READ не нормализует persisted proof; successful result.proof соответствует предъявленному canonical proof. Coverage всех proofs конечного Pack state — обязанность Pack. Dedup exact одинаковых proofs допустим с сохранением coverage; новый hash algorithm не нужен.

durable_refs — полный closure owning capture/format v1, включая обязательные тела, не попавшие в logical selection. Empty proof имеет пустой closure. Объединение closure refs конечных proofs не заменяет проверку exact proof/request correspondence. Успех READ не приобретает holds и не гарантирует сохранность bytes до будущего prepare/adoption; потребуется атомарная повторная проверка и acquisition.

В §12.1 Source уже принят internal SourceCaptureRetentionBinding.adopt(scope, request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef, ...], target: ArtifactHolderRef). Он сам вычисляет closure в borrowed write scope, проверяет exact полный набор source holds и приобретает target holds, не освобождая sources. OPEN именно внешний Pack/Artifacts publication entry и target lifetime, а не наличие owning Source алгоритма adoption. Прямой Pack→Source public pipeline этим не разрешается.

## Конкретное исправление терминологии Pack

В §4 exchange указан SourceProofFailure. Принятый тип — SourceFailure из app.dataModel.sourceVersioning.sourceErrors; отдельный SourceProofFailure не вводится. Успешные carriers не содержат failure. Owning ошибки Source остаются результатом соответствующей Source-операции, их нельзя превращать в successful resolution.

Итог проверки: четыре формы использования совместимы с принятым Source API при описанных условиях. Production readiness, новые Pack публичные методы/ошибки, exact execution binding и внешний atomic adoption остаются предметом отдельной приёмки. Pregame mutation/refusal/recovery не является новым условием семантики этих уже принятых proof операций.
