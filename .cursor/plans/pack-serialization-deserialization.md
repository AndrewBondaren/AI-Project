# Pack — сериализация и десериализация сохранённой версии

2026-11-13. Отдельный план по решению пользователя. Одна задача с двумя подзадачами; статус PROJECT, runtime не изменён. Цель — сохранить точные данные/identity версии и восстановить того же кандидата после потери ответа или рестарта без повторной генерации и записи.

## Граница с текущим планом Pack

Детальная разработка версии encoding, canonical registration и exact READY recovery переносится сюда. Она не блокирует независимую проработку/реализацию и приёмку оставшегося scope текущего Pack: pure write, assembly, собственные контракты, guards и интеграции с уже принятыми ports. Этот перенос не означает, что новый serialization/replay путь уже готов. Подключение этого пути в production и заявление о полном READY replay требуют приёмки данного плана.

В текущем плане остаётся явная точка интеграции «подключить принятый serialization/deserialization binding». Не добавлять временный успешный decoder, эвристику выбора первого manifest ref, повторное staging при READY или скрытое отключение проверки. Если конкретный шаг прямо требует ещё не готового binding, зависимость отмечается только для этого шага, а не как запрет всей работы Pack.

Точное место поставки — [шаг 4a единой таблицы Pack](world-pack-v2-single-manifest-contract.md#единая-таблица-зависимостей-и-завершения-шагов), после согласования необходимых схем/owning типов шага 3. После совместной приёмки двух подзадач этого плана binding подключается в 4b (codecs/read/prepare/READY recovery), затем используется зависимой lifecycle-интеграцией 4c. Независимые pure-срезы 3a не ждут завершения этого плана; готовность production serialization/replay не объявляется до 4b. Новый порядок sources → evidence → manifest → codec/readers не вводится и не переставляется.

Существующие payload codecs, правила данных, порядок write, lifecycle и source ownership не перепроектируются. Десериализация bytes в POJO и восстановление кандидата — разные части второй подзадачи: одно декодирование не подтверждает operation identity, hold и роль manifest.

## Подзадача 1. Сериализация

- [ ] Свести конкретный состав Pack manifest и semantic prepare body с owning типами, без дублирования state/proof.
- [ ] Закрепить детерминированные assembly/encoding правила, descriptor/wire/storage versions и порядок/defaults. Смена настройки времени запуска не меняет bytes той же версии.
- [ ] Выбрать точную связь preparation identity с encoding binding. [Предложенная внутренняя revision](pack-preparation-encoding-identity.md) — вариант для рассмотрения, не утверждённая этим переносом формула.
- [ ] Зафиксировать canonical declarations/IDs с владельцами shared типов; использовать существующий codec и Fields IDs, не объединять конфликтующие manifests целиком.
- [ ] Вычислить контрольные body→bytes→ArtifactRef/fingerprint vectors на реальных моделях. Лимиты задаются владельцами форматов; Pack не назначает чужие caps.

Результат — конкретный pure serialization contract, воспроизводимые bytes/ref и identity. Ни stage/seal, ни публикация head не становятся эффектами encoder. Критерий отказа: latest lookup, случайные defaults, несовпадение bytes при том же принятом binding, ручной второй DTO состава.

## Подзадача 2. Десериализация и восстановление

- [ ] По exact registered descriptor восстановить owning immutable POJO с bounded/schema admission; сохранить значения, порядок и согласованные defaults.
- [ ] Восстановить concrete diagnostics и ModelIdentity через allowlist; без динамического import, стирания subtype и фиктивных field paths.
- [ ] Определить exact READY manifest binding. Рассмотреть восстановление ref детерминированной сериализацией того же полного prepare request; не принимать этот вариант без проверки предпосылок. Новый candidate store не вводится автоматически.
- [ ] Связать manifest с durable operation/world/preparation identity, sealed bytes, hold и полным closure через принятые внутренние Artifacts ports.
- [ ] Развести READY replay prepare и terminal replay activate: первое подтверждает доступный кандидат, второе возвращает исторический исход и после release не восстанавливает holds.
- [ ] Проверить неподдерживаемую версию, повреждённые bytes, несовпадение identity, потерю ответа READY, restart, несколько refs одного формата и release/GC. Отказ не запускает генерацию, stage/finish или latest fallback.

Результат — точный typed результат либо owning отказ, без частичного success. Pure decoder не делает I/O; Pack operation владеет guard/verified read/lifecycle admission. Wrapper делегирует один раз; дальнейший workflow/повтор выбирает DAG.

## Зависимости, доказательства и завершение

Source proof поставляет другой агент. Общие atomic ports остаются у Artifacts/Publication; их schema не копируется. PACK-METADATA-PLANNING сохраняет ранее согласованную отсрочку и не превращается в блокер этого переноса.

Материалы: [canonical audit](pack-canonical-registration-audit.md), [activation vector](pack-activation-identity-vector.md), [READY finding F2](pack-lifecycle-chain-review.md), [activation errors/replay](pack-activation-error-contract.md). Уже выполненные in-memory codec проверки сохраняются как evidence, но не закрывают новые declaration/recovery реализации.

Приёмка обеих подзадач совместная: exact round-trip и стабильная identity, контрольные bytes/hash, forged-instance checks, отсутствие эффектов pure codec, replay без повторной записи, правильные отказы и удержания. Перед изменением кода применяются implement-plan и все обязательные критерии домена; отдельный план не освобождает от них. Неподтверждённая legacy compatibility не объявляется автоматически поддержанной.
