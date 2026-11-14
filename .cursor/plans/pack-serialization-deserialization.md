# Pack — сериализация и десериализация сохранённой версии

2026-11-13. Отдельный план по решению пользователя. Одна задача с двумя подзадачами; статус PROJECT, runtime не изменён. Цель — сохранить точные данные/identity версии и восстановить того же кандидата после потери ответа или рестарта без повторной генерации и записи.

## Граница с текущим планом Pack

Детальная разработка версии encoding, canonical registration и exact READY recovery переносится сюда. Она не блокирует независимую проработку/реализацию и приёмку оставшегося scope текущего Pack: pure write, assembly, собственные контракты, guards и интеграции с уже принятыми ports. Этот перенос не означает, что новый serialization/replay путь уже готов. Подключение этого пути в production и заявление о полном READY replay требуют приёмки данного плана.

В текущем плане остаётся явная точка интеграции «подключить принятый serialization/deserialization binding». Не добавлять временный успешный decoder, эвристику выбора первого manifest ref, повторное staging при READY или скрытое отключение проверки. Если конкретный шаг прямо требует ещё не готового binding, зависимость отмечается только для этого шага, а не как запрет всей работы Pack.

Точное место поставки — [шаг 4a единой таблицы Pack](world-pack-v2-single-manifest-contract.md#единая-таблица-зависимостей-и-завершения-шагов), после согласования необходимых схем/owning типов шага 3. После совместной приёмки двух подзадач этого плана binding подключается в 4b (codecs/read/prepare/READY recovery), затем используется зависимой lifecycle-интеграцией 4c. Независимые pure-срезы 3a не ждут завершения этого плана; готовность production serialization/replay не объявляется до 4b. Новый порядок sources → evidence → manifest → codec/readers не вводится и не переставляется.

Существующие payload codecs, правила данных, порядок write, lifecycle и source ownership не перепроектируются. Десериализация bytes в POJO и восстановление кандидата — разные части второй подзадачи: одно декодирование не подтверждает operation identity, hold и роль manifest.

## Подзадача 1. Сериализация

**Разделение приёмки плана и реализации, 2026-11-14:** выбор shape/fields/identity/registration и READY port — контрактная работа. Вычисленные vectors и runtime round-trip/GC/перезапуск — свидетельства реализации, не требование написать код в текущем контрактном проходе. Для плана обязателен точный набор проверок и ожидаемых свойств; для поставки — фактические результаты. Незаполненные Pack canonical declarations остаются реальным контрактным остатком, отсутствие ещё не выполненного runtime-теста само по себе им не является.

- [ ] Свести конкретный состав Pack manifest и semantic prepare body с owning типами, без дублирования state/proof.
- [ ] Закрепить детерминированные assembly/encoding правила, descriptor/wire/storage versions и порядок/defaults. Смена настройки времени запуска не меняет bytes той же версии.
- [ ] Выбрать точную связь preparation identity с encoding binding. [Предложенная внутренняя revision](pack-preparation-encoding-identity.md) — вариант для рассмотрения, не утверждённая этим переносом формула.
- [ ] Зафиксировать canonical declarations/IDs с владельцами shared типов; использовать существующий codec и Fields IDs, не объединять конфликтующие manifests целиком.
- [ ] Вычислить контрольные body→bytes→ArtifactRef/fingerprint vectors на реальных моделях. Лимиты задаются владельцами форматов; Pack не назначает чужие caps.

Результат — конкретный pure serialization contract, воспроизводимые bytes/ref и identity. Ни stage/seal, ни публикация head не становятся эффектами encoder. Критерий отказа: latest lookup, случайные defaults, несовпадение bytes при том же принятом binding, ручной второй DTO состава.

## Подзадача 2. Десериализация и восстановление

**Матрица обязательных контрольных случаев:** (1) перестановка только объявленных множеств после проверки duplicates сохраняет fingerprint; (2) изменение каждого semantic body поля меняет fingerprint; (3) изменение operation_id вне body не меняет preparation digest, но меняет lifecycle identity; (4) изменение Source dependency revision меняет digest, selectors не нормализует Pack; (5) повтор bytes→POJO→bytes сохраняет exact bytes зарегистрированного binding; (6) malformed/unknown schema и forged instances отклоняются до зависимых эффектов; (7) два manifest ref одинакового формата в operation не мешают выбрать сохранённый exact candidate; (8) потеря ответа после READY/рестарт возвращает тот же candidate без assembly/stage/finish; (9) terminal activation replay после release не восстанавливает holds. Existing activation vectors в отдельном документе не считаются vectors ещё не составленного prepare schema.

- [ ] По exact registered descriptor восстановить owning immutable POJO с bounded/schema admission; сохранить значения, порядок и согласованные defaults.
- [ ] Восстановить concrete diagnostics и ModelIdentity через allowlist; без динамического import, стирания subtype и фиктивных field paths.
- [ ] Определить exact durable READY manifest binding: вернуть сохранённый candidate по operation/preparation identity, без повторной сборки manifest, stage или finish. Ранее предложенное вычисление ref повторной сериализацией отозвано как основание действующего контракта; оно противоречит принятому запрету и не считается выбранным вариантом. Конкретный binding уточняется у Snapshot/Artifacts; новый candidate store не вводится автоматически.
- [ ] Связать manifest с durable operation/world/preparation identity, sealed bytes, hold и полным closure через принятые внутренние Artifacts ports.
- [ ] Развести READY replay prepare и terminal replay activate: первое подтверждает доступный кандидат, второе возвращает исторический исход и после release не восстанавливает holds.
- [ ] Проверить неподдерживаемую версию, повреждённые bytes, несовпадение identity, потерю ответа READY, restart, несколько refs одного формата и release/GC. Отказ не запускает генерацию, stage/finish или latest fallback.

Результат — точный typed результат либо owning отказ, без частичного success. Pure decoder не делает I/O; Pack operation владеет guard/verified read/lifecycle admission. Wrapper делегирует один раз; дальнейший workflow/повтор выбирает DAG.

## Зависимости, доказательства и завершение

### Сверка с Snapshot/Artifacts, 2026-11-14

**Конкретные declarations предъявлены владельцем:** [актуальный internal contract](pack-storage-lifecycle-finalization-response-2026-11-14.md) заменяет первоначальные варианты. `async append_ready_binding(scope, lease, candidate) -> None`; `async read_ready_binding(scope, operation_id) -> PreparedPackCandidate | None`; `async finish_preparation_scoped(scope, lease, refs) -> OperationRecord`. Scope borrowed; методы не commit-ят. None от read — unknown operation/подготовка без binding (либо ранняя отмена), не допустимое отсутствие записи у READY. READY с отсутствующим/повреждённым binding — infrastructure failure, без реконструкции. Exact запись→finish→outer commit атомарны; public generic finish не должен обходить обязательный PACK binding. SQL declaration и новый internal fault roster ещё требуют owning review, принятый способ хранения не переоткрывается.

**ПРИНЯТО пользователем 2026-11-14:** в существующем operation ledger сохраняется exact PreparedPackCandidate(operation_id, manifest: ArtifactRef, preparation_fingerprint), атомарно с READY после admission/adoption. При replay возвращается сохранённый candidate после проверки identity/bytes/holds; manifest не пересобирается, stage/finish не повторяются. Отдельный candidate store, новый holder, независимый version counter и отдельный release marker не вводятся. Это решение о способе хранения/replay; конкретные port/schema/error declarations и их приёмка остаются у владельца Snapshot/Artifacts. Исторические слова «предложение» ниже не означают повторного выбора этого решения. Runtime ещё не реализован этим документом.

Получен [конкретный owning ответ](pack-storage-lifecycle-finalization-response-2026-11-14.md). Current OperationRecord не выделяет роль manifest, finish_pack_preparation возвращает candidate только в памяти. Поэтому READY replay не закрывается одним existing recover(operation_id).

Предложение владельца — append exact PreparedPackCandidate в existing operation ledger в одной transaction с READY; replay читает сохранённый binding и проверяет identity/hold/bytes без пересборки или staging. Это кандидат решения, не уже принятый port/DDL. Отдельное поле contract_version и новый PackCandidateHolder из ответа не приняты автоматически: запрошено обоснование относительно existing schema/body identity и terminal OperationHolder. Source authority resolver уточняется у Source. Новые DAG/генераторные контракты для этого не нужны.

**Ответ на проверку необходимости:** владелец отозвал новый PackCandidateHolder, независимый contract_version и обязательность отдельного release marker. Рекомендуется existing terminal OperationHolder для manifest root и existing exact release history для replay. Требование durable candidate role в ledger сохраняется; схема/port остаются предложением до согласования. READY binding использует existing preparation_fingerprint, не второй счётчик версии. Удержания children освобождаются owning GC по lifetime manifest, не при release одного кандидата.

Source proof поставляет другой агент. Общие atomic ports остаются у Artifacts/Publication; их schema не копируется. PACK-METADATA-PLANNING сохраняет ранее согласованную отсрочку и не превращается в блокер этого переноса.

**Source schema подтверждена владельцем 2026-11-14:** [точный binding/IDs](source-pack-boundary-response-2026-11-14.md). PackPreparationBody.capture — SourceCaptureRef; композиция использует SOURCE_PROOF_SCHEMA_V1, existing ArtifactRef и их транзитивные declarations без перенумерации. Это снимает неопределённость owning capture/proof schema, но не назначает новые Pack IDs и не закрывает authority sources. Проверка отсутствия collisions производится на конкретной итоговой Pack composition, а не через выдуманный глобальный allocator.

Материалы: [canonical audit](pack-canonical-registration-audit.md), [activation vector](pack-activation-identity-vector.md), [READY finding F2](pack-lifecycle-chain-review.md), [activation errors/replay](pack-activation-error-contract.md). Уже выполненные in-memory codec проверки сохраняются как evidence, но не закрывают новые declaration/recovery реализации.

Приёмка обеих подзадач совместная: exact round-trip и стабильная identity, контрольные bytes/hash, forged-instance checks, отсутствие эффектов pure codec, replay без повторной записи, правильные отказы и удержания. Перед изменением кода применяются implement-plan и все обязательные критерии домена; отдельный план не освобождает от них. Неподтверждённая legacy compatibility не объявляется автоматически поддержанной.
