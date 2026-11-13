# Приёмка Source mutation recovery: проектный срез

2026-11-14. **NOT ACCEPTED для реализации.** Проверены source-pregame-revision-staging-design.md P1–P2.12, source-mutation-artifacts-publication-response-2026-11-13.md (полный recovery и актуальный logging roster), world-source-versioning.md (порядок поставки), docs/tz_logging.md и действующие IArtifactLeases/IOperationStore/OperationLedger/CommitScope. Проверка статическая; runtime recovery отсутствует. RLOG-1–4 закрыты отдельно и здесь не переоткрываются. Принятые SourceDurableProof/R1/R2 не пересматриваются.

## REC-1. Неполная привязка durable request к семантике исполнения — Source

P1.1/P2.1 SourceRegistryMutationInput содержит operation/world/changes/membership, но не фиксирует owning semantic projector/descriptor execution version. Раздел «Durable записи и состояния» ответа прямо требует такого binding при зависимости от версии. Контрпример: после crash обновлён projector, те же body bytes дают другой semantic hash и revision decision. Сохранённый checksum запроса этого не обнаружит. Owning body ArtifactRef.format_version не доказывает неизменность semantic projector или ref-integrity rules.

Нужно принять конкретный immutable execution contract binding для выбранного registry: owning projector/body codec/descriptor semantics и все influencing settings либо точное доказательство их отсутствия. Указать, что происходит при недоступности прежнего исполнения после restart; silent latest-version fallback запрещён. Определить отдельные replay inputs и checks текущего состояния: original expected неизменны, а сравнение с текущей revision может законно дать новый конфликт. Не замораживать всё окружение без необходимости и не подменять agreed recovery восстановлением прежнего in-memory результата. До этого canonical request roster/fingerprint не окончателен.

## REC-2. Hold transfer ещё описан намерением — Artifacts/publication

В разделе «Holds и смена fence» требуется atomic transfer всех operation holds, но прямо оставлен непринятый internal lease-transfer primitive. В текущем IArtifactLeases такого метода нет. Без точного input/output/error, заимствованного scope, полного состава transferred refs и prewrite guards нельзя доказать отсутствие GC окна или сохранение чужих holders.

Нужны точный port/module/implementation owner, nested trace и atomicity: сверка old/new lease/attempt, closed admission/drain, full hold set, append-only события/guards и rollback/unknown. Смена fence и transfer должны быть в одной transaction. Подмена отсутствующих holds новым acquire не является восстановлением исходной защиты.

## REC-3. Противоречивый результат CAS и неполный recovery input — Artifacts/publication

«Ownership и fenced takeover» обещает при CAS mismatch возврат актуального recovery state. Но claim_recovery возвращает только PublicationAttemptOwner | SourceMutationApplied | SourceMutationRefused, а далее ATTEMPT_CHANGED описан как RecoveryContractError. Эти варианты требуют разных callers и логирования. Выбрать одно поведение, привести всю документацию к нему.

Logging добавляет обязательный RecoveryReason в input, но показанная SourceMutationRecoveryInput signature его не содержит. Нужен единый окончательный POJO roster с модулями, strict/frozen/nullable/union discriminators и вариантами absent operation, PreparationRequired, Active, Terminal. inspect, claim и terminal replay должны иметь однозначные input/result/error contracts; не изобретать дополнительный mirror outcome.

## REC-4. Attempt acquisition и durable single-start — Artifacts/publication

Проект связывает одну domain() с runtime registry, но передаваемый PublicationAttemptOwner — serializable DTO, а transaction_for_attempt(owner) объявлен отдельным входом. Требуется точное доказательство запрета получить новую runtime capability для той же attempt после rollback в другом coordinator/registry экземпляре того же процесса. Фраза «registry помнит issued attempt» недостаточна без ownership/composition ограничения и lifecycle этого факта. Нельзя объявлять багом неизбежное завершение с commit: проверяется именно rollback/ошибка до terminal и повторный вход прежнего owner.

Указать единственного capability issuer, связь claim result с runtime attempt, запрет повторной выдачи и поведение при restart/нескольких DB coordinators. Recovery должен выдавать новую attempt/fence и отзывать старую authority; raw owner DTO сам её не даёт. Source require_domain_attempt должен читать тот же authoritative binding. Внешние публичные payload не содержат capability/scope.

## REC-5. Срез ещё не имеет полного delivery/operation map — совместно

P2.9 оставляет «Source apply implementation» и «Artifacts root adapter» как роли, прямо откладывая concrete классы/порты на P3. Внешний mutation/recovery entry и approved DAG binding не описаны полностью; sourceUsage/prune/bootstrap/selected-registry projector gates открыты. Поэтому допустима продолженная контрактная проработка, но не объявление всего плана implementation-ready.

Нужна одна карта для конкретного среза: public Input/Outcome/Error → direct DAG caller (либо явно ограниченный internal-only scope) → exact internal классы, зависимости/effects/отказ → shared transaction/terminal/holds/logging. Согласованный пользователем порядок inventory→projector→revisions→capture сохраняется. Новый набор нод/порядок агент не назначает. Explicit prune может быть отдельной поставкой только с явно принятым ограничением, а не скрытым отсутствием release.

## Матрица обязательных критериев

| Критерий dag-generator-interface | Evidence / вывод |
|---|---|
| Нет pipeline с межоперационным ветвлением | Локальные new/replay/recovery branches описаны; полный public/internal map не завершён (REC-5), соответствие всего среза не доказано |
| Нет скрытого orchestration / direct DAG вызов | Новые ноды не назначены, runtime не менялся; production caller binding OPEN, приёмка не пройдена |
| Нет прямых междоменных public calls | Source использует предполагаемые internal storage bindings; окончательный nested trace не завершён (REC-2/5) |
| Роль, эффекты, зависимости и критерий отказа каждого класса | P2.9 и response задают часть ролей; missing concrete map/single-start ownership (REC-4/5) |
| Public contract / open pipeline / implementation boundary | CommitScope остаётся internal; неполные union/signatures и caller map (REC-3/5) |
| Утверждённый порядок | Основной порядок и explicit recovery + обязательное logging приняты; prerequisites inventory/projector не закрыты (REC-1/5) |
| CRUD данных: create/read/update/delete отдельно | Registry create/update/delete предложены; exact read/ref ошибки частично заданы. Tombstone hash/codec и bootstrap не приняты. Полная CRUD приёмка отсутствует |
| CRUD настроек: create/read/update/delete отдельно | Не входит в ограниченный registry срез; статус полного Source остаётся OPEN, общего settings CRUD этим review не принимаем |
| Междоменный CRUD/data dependency protocol | Owning ответ получен; semantic projector/settings и hold-transfer contract требуют завершения (REC-1/2) |
| POJO, typed field/logic errors, отсутствие дублей | Proof принят отдельно; logging findings закрыты. Mutation/refusal canonical manifest и recovery union ещё неполны (REC-1/3); runtime typing не проверялась |

## Порядок закрытия

1. Source конкретизирует выбранный registry execution binding и последствия для durable request/canonical schema (REC-1).
2. Artifacts/publication закрывает transfer, единые recovery signatures и single-start authority (REC-2–4). Эти проектные уточнения не разрешают код инфраструктуры автоматически.
3. Собрать P3 concrete operation/delivery map с dependency gates (REC-5), повторить обязательную приёмку.
4. Только принятый implementation slice выполнять через implement-plan с реальными rollback/replay/GC/sink проверками.

Новых решений пользователя по уже согласованной recovery semantics и logging не требуется. Исправления внешних contracts запрашиваются у владельца; Source-owned gaps не перекладываются на Pack.

## Повторная статическая сверка REC-2–4

В owning response появились IOperationHoldTransfer.transfer(scope, previous, successor) с полным computed set, CONTROL generation, guards и единым fence/holds commit; REC-2 как отсутствие конкретного port/trace закрыт проектно. REC-3 приведён к ATTEMPT_CHANGED exception при CAS mismatch, полным InspectInput/RecoveryInput с reason и discriminated result; REC-4 заменён durable start-claim CAS, единственным PublicationAttemptIssuer и одноразовым PublicationExecutionGrant. Исходные замечания к этим трём разделам устранены статически. Runtime atomicity/fencing не проверялись.

**REC-6, OPEN — cancelled terminal replay:** окончательный recovery union допускает OperationCancelled, но logging terminal_kind и terminal field invariants пока рассчитаны только на Applied/Refused и требуют attempt pair. Отмена до первого claim может не иметь attempt. Нужно корректное представление durable cancelled replay без фиктивной attempt и без смешивания с отменой текущего invocation. Запрошено у Artifacts/publication. Это следствие уточнения union, не переоткрытие закрытых RLOG-1–4.

Source REC-1 продвинут через execution_version (P2.13), Terrain dossier/presence (P2.14–16), candidate tombstone (P2.17). Полнота owning execution registration/callers/manifest остаётся OPEN. REC-5 не закрыт. Итог всего среза по-прежнему NOT ACCEPTED для implementation.

## Последующая сверка REC-6 и Source map

REC-6 закрыт статически по owning подразделу «Replay cancellation»: existing OperationCancelled сохраняется; TERMINAL_REPLAYED/CANCELLED имеет typed cancellation_reason, отсутствующая ранняя attempt не фабрикуется. При отсутствии immutable request registration request-specific API выдаёт INVALID_REQUEST_BINDING; generic ledger read остаётся доступным. Отмена invocation логируется отдельно и не становится cancellation terminal.

Source P3.1–P3.3 предъявляет конкретные ExecutionRegistry/RegistryMutationApplier/AttemptRunner, required_refs/apply_in_scope/run и nested success/refusal trace. REC-5 остаётся PARTIAL: revision store, owning row writer и public caller/error map ещё нужны. Это конкретные оставшиеся зависимости, не повтор ранее закрытых infrastructure/logging findings. Полная приёмка implementation остаётся NOT ACCEPTED.
