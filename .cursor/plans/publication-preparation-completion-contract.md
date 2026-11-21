# Publication preparation completion

## Решение пользователя — 2026-11-21

Пользователь согласился продолжить с предложенной границей после объяснения кейса переиспользования артефактов Pack. Принято направление: один публичный completion Publication и одна внутренняя scoped-операция Artifacts. Это не приёмка полного контракта, не code-go и не новый blocker независимого переноса записи.

Источник предложения: [Artifacts completion](artifacts-public-staging-dag.md#completion-один-public-entry-и-scoped-acquisitionfinish--proposed-2026-11-21). Этот документ фиксирует решение отдельно; owning Artifacts-файл здесь не переписывается.

## Кейс и гарантия

Исходный Pack содержит A/B, для нового подготовлен C, целевой набор — A/C. Исходная protection удерживает A, staging удерживает C. Completion в одном UOW приобретает target hold для A, проверяет exact target set A/C, сохраняет immutable candidate binding и READY. До confirmed commit внутренний результат provisional. Это завершение подготовки, публикация выполняется отдельной операцией.

Publication владеет authoritative admission, UOW, persisted candidate, replay и recovery. Artifacts выполняет scoped acquisition/finish через существующие primitives без собственного commit, Source calls и release исходной protection. Изменяемые fences/cancel/source lifetime/writers проверяются внутри UOW повторно. Existing standalone finish нельзя присоединить простой обёрткой bind(scope).

Confirmed rollback отменяет новые holds/candidate/READY вместе, сохраняя прежние holds. Unknown outcome требует reconciliation до cleanup. Cancel-first отвергает completion; completion-first означает готовность на момент commit, а последующий cancel подчинён lifecycle. Exact повтор при READY использует persisted binding без повторного acquisition; другой candidate/set конфликтует. Повтор после cancel/publication не создаёт подготовку заново. Освобождение исходной protection — отдельный lifecycle шаг после confirmed outcome и drain.

## Точный owning контракт к предъявлению Publication

1. Модуль/класс/signature public completion; concrete Input/Result/Error с reuse Pack candidate/evidence, без mirror DTO или Any. Разделить business refusal, infrastructure failure, unknown и cancellation.
2. Representation source protection: пригодность OperationLeaseRef, issuer, authority связи source/target, lifetime; какие проверки выполняются до и внутри UOW.
3. Exact persisted candidate binding и результат повторов при READY/cancel/publication; durable evidence для reconciliation после возможного освобождения holds. Membership/fingerprint не заменяют нужное exact comparison.
4. Сопоставить public input с ArtifactPreparationCompletionInput и указать место candidate persistence относительно scoped acquisition/finish внутри единого UOW. Новые NodeId и изменение утверждённого порядка не подразумеваются.

Полные signatures, POJO inventory, errors и runtime evidence остаются OPEN до owning ответа и общей сверки. Проверки реализации: partial acquisition rollback, fault injection до/после COMMIT, concurrent cancel в обеих очередностях, lost ACK, mismatched replay и отсутствие premature cleanup при unknown. Здесь код и тесты не создаются.
