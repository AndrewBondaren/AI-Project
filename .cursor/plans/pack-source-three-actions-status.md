# Три замечания Source: исполнение и внешняя приёмка

Дата: 2026-11-14. Реализация runtime не выполняется. Это контроль фактического выполнения поручения, не заявление общей приёмки.

| Действие | Выполнено | Остаток |
|---|---|---|
| Учесть Source responses и единый SourceFailure | Exchange учитывает select correspondence, grouped admission, full closure и internal adoption; активные Source signatures/SourceNodeError в DAG families исправлены; transition roster больше не требует proof error mirrors | Исторические отозванные схемы и явные запреты создавать SourceProofFailure сохранены как история, не runtime contracts |
| Привязка DAG result к исполненному запросу | Получены [ответ DAG](dag-pack-source-binding-response-2026-11-14.md) и [дополнение](dag-pack-source-binding-addendum-2026-11-14.md): CALL подходит; семь фаз exchange описаны; широкие upper unions сохранены | A1 — внешний continuation caller, A2 — freeze upper/caller contracts и unsupported policy, A3 — повторная приёмка исправленного Pack mapping, A4 — production trusted entry/store/restore и lifetime |
| Внешний adoption и closure до READY | Получен [ответ Artifacts/publication](pack-source-adoption-publication-response-2026-11-14.md): предложен PackPreparationRetention.adopt_and_finish, OperationHolder и scoped finish в единой transaction; PACK_ACTIVATION и preparation fingerprint подтверждены | DESIGN OPEN: trusted caller и полномочия sources, durable exact candidate mapping/replay, scoped finish port, Pack error mapping, post-READY holder lifetime. Принятого готового внешнего entry в проверенном коде нет |

Review передан 2026-11-14 в существующие чаты: DAG — 01a1d598-f2e7-7fc1-8c3a-f4386cbfa6a6; Artifacts/publication — 01a1a0c5-931c-77a0-96a5-cb5b6ca6766f. Runtime/новые ноды/хранилища не поручались. Конкурирующие правки Pack документов не поручались.

Документы: [exchange](pack-source-exchange-contract.md), [engine binding](pack-source-dag-execution-binding.md), [leaf acceptance A1–A4](pack-source-leaf-acceptance.md). A1 partially corrected (prefix накопления), A3 field divergence исправлена; full errors/phase/registration acceptance этим не закрыта.

## Результат согласования

Первое замечание выполнено в активных документах. По второму подтверждён механизм, но не полный маршрут. По третьему получено конкретное предложение владельца, а не приёмка внешнего entry. Все три замечания закрытыми не считать; runtime реализация и её приёмка не выполнялись.

Принятый Source internal adopt не меняется. Предложенная publication transaction выполняет все adopts, затем scoped finish и COMMIT; ошибка любого adopt откатывает новые holds всех предыдущих, source holds не снимаются, READY возвращается только после подтверждённого COMMIT. Это предложение инфраструктурной границы, не разрешение Pack вызывать Source и не новый порядок DAG. Успешный READ не является live hold.

Дальнейший объём разделён по владельцам: DAG — полный continuation/upper/restore контракт; Pack — semantic errors, final-state proof coverage и immutable preparation identity; publication/Artifacts — authority источников, scoped finish, operation lifecycle и retention handoff совместно с Pack. Независимая работа Pack этим не блокируется. Сужение общих upper unions и новый publication entry нельзя молча считать утверждёнными изменениями контрактов.

## Следующий проход 2026-11-14

[Pack A3 / identity](pack-source-error-identity-contract.md) конкретизирует operation-specific diagnostics без новых carriers и повторной Source проверки. Это proposal для приёмки, не объявление A3 закрытым. Уточнение publication подтвердило уже принятый PACK_ACTIVATION и единый preparation digest из body/lease: эти два вопроса сняты с OPEN. Authority source holders, READY replay и post-READY retention остаются открытыми. Предложение пересобирать manifest на READY противоречит действующему запрету ТЗ и возвращено владельцу как требующее отдельного решения; автоматически не принято.

Владельцу DAG передан запрос на полный continuation, exact upper bindings с сохранением общих unions и конкретный trusted restore. Новые Source methods и изменение принятого порядка 1–7 не запрошены.

Получено [дополнение DAG A1/A2/A4](dag-pack-source-binding-addendum-2026-11-14.md): семь phase POJO, кандидаты upper contracts/factories/registration без сужения unions, явный предложенный отказ unsupported до CALL, трассировка существующих store/restore. Оно не закрывает внешний continuation detailed_initialization, producer metadata Planning, полный Source union и production authorized entry/store/lifetime binding. Unsupported через runtime failure — предложение для приёмки, не уже принятое поведение. Следующая проверка использует это дополнение вместо повторного запроса «описать семь фаз».

**Уточнение scope следующего прохода:** metadata Planning уже отложен пользователем и не блокирует текущий Pack. [Решение и повторный trace](pack-v2-public-write-operations.md#отложенный-вопрос-pack-metadata-planning--разрешённая-заглушка-проекта) являются основанием продолжения; новый вопрос пользователю об отсрочке не нужен. В итоговых списках остатка его указывать только как внешнюю интеграционную тему, не смешивать с A3 Pack diagnostics. Следующий локальный пункт — проверка предложенного A3 mapping и его согласованности с owning Pack inputs; readiness production entry/holders проверяется отдельно.

**A3 уточнён:** ошибки/пути сверены; binding размещён только в metadataDependencies.py; empty fields/entries usage-операций отклоняются через существующий проектный METADATA_GROUP_MISMATCH. Основной write-план, exchange и execution binding синхронизированы. Локальные неопределённости устранены, результат предъявлен к повторной приёмке; полный маршрут и runtime не объявлены принятыми.

## Актуальные шаги завершения

Это порядок работы над контрактами и поставкой, не изменение согласованного runtime порядка 1–7. Чекбоксы закрываются по доказательствам, не по наличию проекта документа.

1. [x] **Повторная приёмка A3 — Pack.** A3-R1/R2 устранены: четыре кода внесены в ТЗ, SourceFailure mapping унифицирован. [Повторная проверка](pack-source-a3-reacceptance-2026-11-14.md) закрывает A3 в объёме локальной согласованности bind/diagnostics. Это не независимая агентская или runtime приёмка и не готовность полного маршрута.
2. [ ] **Завершить A1/A2 — DAG.** Принять внешний continuation detailed_initialization, полный caller/upper I/O и error contract, identities/registration и unsupported policy. Использовать уже описанные семь фаз; сохранить общие unions, родство и утверждённый порядок.
3. [ ] **Завершить A4 — DAG/application composition.** Указать конкретные production initiating/resume entry, authorized execution binding, server-owned store/registry и lifetime pinned/prepared refs. Доказать границу доверенного restore; test-only store не закрывает production контракт.
4. [ ] **Завершить publication boundary — Artifacts/publication совместно с Pack и Source.** Уточнить полномочия source holders, scoped adoption→finish→READY с rollback, durable сохранённый candidate для replay без пересборки manifest, post-READY retention/handoff/release и error mapping. Повторно не выбирать уже подтверждённые kind/fingerprint.
5. [ ] **Реализация принятого среза.** После приёмки его плана выполнить через implement-plan; конкретные изменения и проверки определяет принятый scope. Внешние интеграционные пункты не задерживают независимый принятый Pack-срез.
6. [ ] **Отдельная приёмка кода.** Проверить фактические callers, вложенные вызовы, POJO/errors, неизменность порядка и необходимые тесты по правилам проекта. Имплементация и приёмка — отдельные этапы; документальная приёмка не заменяет runtime доказательства.

Ближайший шаг — пункт 2, DAG A1/A2. PACK-METADATA-PLANNING остаётся разрешённой неблокирующей отсрочкой текущего Pack; новый Source proof API для описанного exchange не требуется. Полный маршрут не считается готовым до закрытия его зависимых пунктов.
