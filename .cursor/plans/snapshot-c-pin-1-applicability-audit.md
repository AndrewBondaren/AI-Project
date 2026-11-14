# Snapshot: применимость G3 к C-PIN-1

2026-11-14. Документальная проверка по запросу Source/Pack; код, DDL, DAG и порядок поставки не меняются. Это не новый admission proposal и не runtime acceptance.

## Вывод

**G3 недостаточно, чтобы объявить весь C-PIN-1 execution-ready.** Принятый S1/S2 r2 конкретизирует scoped проверки уже допустимого origin, private evidence, register/resolve и rollback. Однако первая законная выдача pinned grant и полный durable binding contract не получили отдельного однозначного принятия: `PreparationAuthorityIssuer.issue_pinned_manifest`, runtime grant и `PreparationSourceBinding` описаны в §3–4 исходного **PROPOSED FOR ACCEPTANCE** `pack-preparation-source-authority-contract.md`. Единая редакция принимает ограниченный S1/S2 scope и зависимости §4–5, а не весь исходный proposal. Наличие имени issuer в error boundary не принимает автоматически его admission API.

Это узкая недостающая зависимость Snapshot/Artifacts с подтверждением Pack authenticated pin boundary. Она не требует автоматически operation-origin G4 или Source finalizer hookup. Не проектируем их и не предлагаем новый протокол вместо уже имеющегося pinned proposal. Нужна явная фиксация применимости/приёмки именно pinned issuer, durable origin mapping и repeat issuance boundary; затем реализация по отдельному принятому плану. До этого C-PIN-1 остаётся OPEN.

Контрпример: первый target prepare дошёл до provisional register и acquire, второй proof отказал, outer transaction откатилась. В БД остался законный OPEN manifest pin, но target registration отсутствует. `resolve_sources` обязан отказать на отсутствующей регистрации. `require_open_manifest` только проверяет pin и не выдаёт grant. Повторный preflight создаёт evidence, но не acquisition authority. Из DAG checkpoint или совпавшего holder нельзя восстановить grant. Для повторного `register_sources` нужен законный повторный вызов pinned issuer; именно его accepted admission boundary нельзя вывести из G3 read ports.

## Проверенные contracts и runtime

Пути к коду относительно `backend/app/`.

| Элемент | Файл / метод | Статус и предел |
|---|---|---|
| Persistent authenticated pin | `db/repositories/sqlite/worldPack/executionPins.py`, `ExecutionPins._owner/_binding/acquire/held_manifest/hold_open` | IMPLEMENTED. `_binding` проверяет namespace/execution/invocation/logical_read_key/world/pin/OPEN и CLOSED; offline store не считается доступным OPEN context. Повторный acquire существующего binding возвращает прежний manifest при наличии hold. Не target Source registration |
| Pin scoped read | S1/S2 r2 §4, `application/publication/contracts/pinnedManifestAuthority.py`, `IPinnedManifestAuthority.require_open_manifest` | ACCEPTED DESIGN зависимости, NOT IMPLEMENTED. Использует тот же outer scope; нельзя подставить существующие acquire/hold_open с собственным writer UOW |
| Verified all-provenance read | S1/S2 r2 §4, `application/worldData/pack/read/preparationManifestReader.py`, `PackPreparationManifestReader.read_source_proofs` | ACCEPTED DESIGN, NOT IMPLEMENTED. Pack отвечает за exact strict manifest, все parts и assembly proofs, typed refusal |
| Private evidence и target register/resolve | S1/S2 r2 §4–5, `application/publication/service/packPreparationSourceAuthority.py`, `PackPreparationSourceAuthority` | ACCEPTED DESIGN scoped consumer trace, NOT IMPLEMENTED. Требует уже issued grants, exact target/request/evidence и actual holds; не создаёт исходное право |
| Pinned grant issuer и durable records | `pack-preparation-source-authority-contract.md` §3–4: `application/publication/service/preparationAuthorityIssuer.py`, `issue_pinned_manifest`; `dataModel/publication/preparationSourceAuthority.py`, `PreparationSourceBinding` | PROPOSED, NOT IMPLEMENTED. Не выдаём частичную приёмку read dependencies за приёмку всего issuer/record protocol |
| Atomic owner | S1/S2 r2 §5: `application/publication/service/packPreparationRetention.py`, `PackPreparationRetention.adopt_and_finish` | ACCEPTED DESIGN composition, NOT IMPLEMENTED; единственный outer commit/rollback owner |
| DAG checkpoint | `db/repositories/sqlite/dagExecutions/executionStore.py`, `ExecutionStore.read/checkpoint`; `application/engine/runtime/invocations/checkpointCodec.py` | IMPLEMENTED persistence execution checkpoint. Не сохраняет Snapshot `PreparationSourceBinding`, не выдаёт Source authority |

Поиск файлов production authority/issuer/retention/scoped pin port не выявил реализаций. Private primitives и persistent pin таблица существуют; новые классы не считаются реализованными по наличию проекта сигнатур. Старые upper bindings/continuation из `dag-pack-source-binding-response-2026-11-14.md` отозваны и не использованы как evidence.

## Исходы C-PIN-1

1. **Первый OPEN pin.** Existing ExecutionPins сохраняет binding store/execution/invocation/logical key/world/pin/manifest. Root удерживает `PinHolder`; child refs должны иметь реальный `ArtifactRetentionHolder(manifest)`. Принятые read/coverage/preflight проверяют данные; proposed issuer должен выдать fresh grant, а register — сохранить exact target/request/origins. Pin row не заменяет эту регистрацию. Gap описан выше.
2. **PREPARING restart после rollback.** Принятый порядок: новый outer scope → exact origin/manifest → coverage → fresh preflight → register/resolve → повторные adopt checks. Runtime grant/evidence очищаются, не сериализуются. Если target registration откатилась, читать нечего; нужен повторный lawful pinned issuance из того же authenticated input. Сохранённый ранее committed binding можно только заново проверить, но в §5 нет отдельной принятой commit boundary «сохранить registration в PREPARING и выйти»: outer owner делает READY/commit. Нельзя invent такую промежуточную transaction ради fixture. Existing pin persistence позволяет повторно проверить тот же pin, но не доказывает durable target/request/origin mapping или его передачу из DAG.
3. **Closed/missing pin, потерянный hold, чужой binding.** Refusal владельца pin/manifest сохраняется как `ManifestReadRefusal`; глубокий consumer поднимает `PackPreparationReadAbort` внутри outer writer. Authority absence/conflict — owning `PreparationAuthorityError`; повреждённый ledger/invalid scope — infrastructure. Конкретные authority codes исходного proposal не объявляются реализованными. Нет latest/origin substitution, reopen или partial success. Existing ExecutionPins пока использует собственные exceptions, поэтому proposed union требует реализации, а не переименования в отчёте.
4. **READY replay.** S1/S2 r2 §5 требует exact committed candidate и target holds перед origin чтениями; закрытый старый pin не мешает этому replay. Execution `READY` в DAG не равен preparation `READY`. `spatial-dag-execution-finality.md` задаёт порядок stop intent → DAG stop → Pack CLOSED → DAG finalized/replay → release; это lifetime ordering, не source registration. Нельзя привязать его к отозванному public pipeline или выводить из него новые ноды.
5. **Late refusal / close / GC / unknown.** Принятый design требует один непрерывный BEGIN IMMEDIATE общей БД от origin checks до commit, две независимые connections и совместимый writer guard у close/GC physical deleters. Отказ второго proof откатывает registrations и target acquisitions первого. Catch только после confirmed rollback и revoke; unknown commit/rollback выходит как unknown/infrastructure, не превращается в typed refusal. Cleanup evidence выполняется и на cancellation. Pinned-only сценарий достаточен для этих локальных проверок после поставки prerequisites; operation-origin G4 для них сам по себе не нужен. Existing unknown-outcome правила не дают права оживить grant или fabricate persisted registration.

## Fixtures и следующий допустимый шаг

- Source: `backend/tests/sourceVersioning/support/finalizedFixtures.py` из G2-fixtures — новые strict Source records, настоящий finalizer и committed witness/closure/holds. Не переиспользовать fabricated finalized rows или legacy conversion.
- Pack: owning strict manifest с полным Source provenance, реальный published/pinned manifest, root hold и child retention; подтвердить actual imports/schema и получение authenticated pin. Existing старые fixtures не считаются доказательством совместимости автоматически.
- Snapshot/Artifacts: реальные outer scopes/ledger/issuer после принятия узкой pinned зависимости, два соединения одной временной SQLite DB, target rollback/replay/unknown и evidence cleanup. Exact новые fixture paths фиксируются владельцами до кода; здесь не назначаются несуществующие imports.

G1/G2/G3 остаются prerequisites Source implementation-плана; настоящее заключение не меняет порядок A → B → C и не снимает gates. Следующий шаг — решение по указанному pinned acceptance gap. До него не писать C integration с ручным grant/ledger row, не расширять G4/finalizer и не подключать DAG.

## Evidence и ограничения

Прочитаны S1/S2 r2 §1,4–6 и акт приёмки; implementation §2,5 C-PIN-1; authority proposal §1–4,9–12; actual ExecutionPins и ExecutionStore checkpoint references; отзыв DAG bindings. Выполнены read-only `git status --short`, `Get-Content` и `rg` по названным файлам/production paths. Рабочее дерево содержит ранее внесённые Snapshot R1–R3 и чужие изменения; они сохранены. Новые runtime tests для этого документального аудита не запускались, runtime PASS C-PIN-1 не заявлен. Изменение этого прохода — только данный отчёт.
