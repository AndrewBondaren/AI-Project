# Snapshot: узкая сверка Time settings S2–S4

2026-11-21. Источник — time-domain.md, решение в начале S2 и S2–S4; actual PreparedTimeSettingsChange (dataModel/world/settings/timeOperations/results.py), TimeSettingsCapture (read.py), TimeAdvanceProposal и TimeCapture; принятые H2/C2/H3. Документальная owning сверка Snapshot для координатора. Не code-go, не новые NodeIds/IDs и не изменение предметной семантики. Исторический §37 Time помечен superseded и не заменяет недостающий active handler/storage контракт.

## 1. Common base и effective_at

Обозначения: Q=context.expected_world, O=context.operation_id; settings change=N.patches[0].change, advance proposal=A.patches[0].proposal. В apply те же Q/O берутся из context.validation, target=context.world_snapshot/context.next_publication — только назначение результата, не источник проверки before.

| Input → consumer | Exact obligation / владелец |
|---|---|
| change.expected → Q | Полное равенство WorldPublicationRef; Snapshot проверяет actual expected heads, Time — соответствие своего prepared контексту |
| change.operation_id и обоих PatchHeader.ref.operation_id → O | Общий PatchSet admission + owning coherence; другое operation_id не исправляется |
| proposal.base.publication → Q | Existing Time advance validation; settings и advance используют один исходный accepted Q |
| TimeAcceptedStateRead(publication=Q,source=clock_binding) → TimeCapture | TimeAcceptedStateReader.read(request,scope=context.read_scope), existing H3 clock source. Time checks decoded payload/source; Snapshot supplies authoritative binding/lifetime |
| change.effective_at → accepted_clock.point | Равенство полного TimePoint, не только timeline. При совместном advance также proposal.base.point==accepted_clock.point и interval.start==base.point; effective_at не interval.end |
| change.before → accepted settings at Q | Time-owned exact scoped reader и owning equality; supplied before не proof. Snapshot не сравнивает календарные payloads |
| writer output → SectionApplyReceipt | Exact исходный PatchRef, assigned refs и retention; C2 сразу после каждого success apply |

У settings handler нет необходимости вызывать advance handler или читать его staged state. Он читает собственный Time clock через принятый H3 reader, независимо от присутствия advance section. Однако settings-only composition должна явно объявить потребность в clock binding: наличие clock handler в registry не условие его доступности. Это registration/input obligation Time к existing source mechanism, не новый H3 resolver. Для settings state нужен отдельный объявленный scoped read/source binding: H3 clock binding не удостоверяет settings storage автоматически. Public read_current без borrowed scope не заменяет этот порт.

S2 pure PrepareTimeSettingsSection(change,operation_id,expected_world) не содержит authoritative clock capture. Producer может проверить scope effective_at, но не его равенство actual clock.point; точное равенство остаётся apply-boundary predicate Time. Snapshot не добавляет clock.point или календарные facts в общий context самостоятельно.

### Expected version — точный input gap

Actual PreparedTimeSettingsChange содержит operation_id/expected/before/after/effective_at; capture.versions в нём отсутствует. Поэтому текущее native change позволяет проверять expected publication Q и before settings at Q, но не отдельное caller-supplied множество CalendarVersionRef. Time должен явно записать, что означает принятая expected-version проверка: если это publication Q — existing expected достаточен при authoritative immutable settings-at-Q binding; если дополнительно calendar versions из capture — owning declaration обязана сохранять этот operand до handler (reuse existing typed refs, без новой версии, выдуманной Snapshot). Нельзя сравнивать capture.versions, которого нет во входе, или считать equality before доказательством version equality. Это уточнение exact operand, не повторный выбор политики no-op. Даже before==after проходит ту же expectation проверку до no-op.

## 2. Dependencies и порядок

В принятой семантике нет обязательного **data edge между settings и advance**: settings effective_at — исходный clock, duration advance не зависит от календаря. Оба результата готовятся от Q; каждый writer читает accepted source Q и пишет только свой section namespace. Значит independent apply без чтения sibling writes совместим со Snapshot. Это не параллельный apply: сохраняется исходный утверждённый порядок sections.

| Предлагаемый edge | Нужен ли / причина |
|---|---|
| settings → advance | Не нужен для duration или чтения after settings: таких зависимостей принятое решение не требует |
| advance → settings | Не нужен для effective_at: settings не использует новую clock.point |
| Оба handler → accepted clock/settings sources Q | Нужны source capabilities/preconditions; это доступ к исходным данным, не prepared sibling dependency и не новый DAG edge |

Snapshot поддерживает freeze пустых mutual prepared dependencies **при подтверждённом Time контракте чтений только Q и записи разных section keys**. Не добавлять PreparedSectionDependency ради совместного commit: атомарность задаёт общий PatchSet/transaction. Нельзя менять accepted порядок sections под предлогом независимости или превращать raw dependency fingerprint в source state. Если Time обнаружит реальное чтение sibling output, он предъявляет operand/source и обоснование edge координатору; скрытое чтение staged after недопустимо. Самостоятельно объявлять пока OPEN dependencies утверждёнными эта сверка не вправе.

Flow: admission → claim/exact replay → общая transaction/expected checks/source bindings по H3 → все validate в принятом порядке → оставшиеся C2 bases → последовательные apply с immediate receipt check → metadata/handoff/CAS/terminal → confirmed commit. Settings refusal в validate запрещает advance apply и наоборот. Отказ второго apply/C2 failure откатывает уже staged writes первого. Никакого commit одного handler или отдельного settings transaction.

## 3. No-op receipt и history

`changed=false` из S2 — словесное описание, не допустимое значение SectionApplyReceipt.changed. Concrete no-op mapping: `changed=()`; новый settings state/version не создаётся. Рекомендуемый минимальный output — `states=()`, Snapshot builder наследует pinned settings state из base; это не потеря состояния. Existing C2 также допускает exact inherited retention при соблюдении provenance/closure, но Time должен выбрать один свой mapping; новый assigned state с empty changed запрещён C2. При headless settings-only исходнике нельзя изобрести SectionStateRef ради receipt: сохранение publication-bound источника требует explicit owning no-op/source contract.

Дополнение Time к этой сверке выбирает no-op policy: changed=(), history=(), календарного события нет, факт операции остаётся в общем ledger; новая settings state/version не создаётся. Snapshot подтверждает совместимость: для pinned snapshot base concrete receipt `SectionApplyReceipt(section_key=N.header.key, states=(), history=(), changed=())` сохраняет прежний settings state через existing builder base inheritance. Его artifacts retention берётся из exact base metadata, не из пустой выдуманной closure. Общий C2 по-прежнему не вводит запрет history при changed=() для остальных доменов. При обычном изменении changed=(N.patches[0].header.ref,), exact исходный ref; state/history относятся к assigned target и проходят common retention rules.

Исторический WorldSettingsAppended(state_ref:SectionStateRef,history_ref:SectionHistoryRef) с обоими обязательными refs не описывает no-op без новой settings version. Нужен owning active append outcome с явным unchanged mapping; history policy уже выбрана дополнением Time. Snapshot не создаёт новый доменный result. Optional refs либо closed changed/unchanged branches — решение Time, перед приёмкой требуется один exact тип и mapping в receipt. Settings versions unchanged остаются прежними при no-op, а не получают next_publication автоматически. Для headless source отсутствие snapshot parent не позволяет builder автоматически унаследовать settings row: Time предъявляет existing publication-bound retention/read continuity к next_publication без новой settings version либо явно ограничивает данный runtime binding pinned snapshot base. Это точный source-retention gap, не требование записывать фиктивный state или переоткрывать H3 clock.

## 4. Errors, atomicity, replay

Actual stale expected publication — existing Snapshot expectation conflict. Complete accepted settings/version/before mismatch при подходящем Q — owning typed Time settings apply conflict, distinct от pure SettingsSectionContextMismatch. Его exact diagnostic code/operands/category/local refusal_model требуется задать Time и замкнуть в H2 composition. Runtime handler.validate → SectionAccepted | local SectionRefused[D_settings]; apply → SectionApplyReceipt | тот же local refusal; bound writer append → owning changed/unchanged outcome | owning conflict, без commit. Имя D_settings здесь обозначает незаполненный owning roster, не новую схему Snapshot.

Missing promised source, corrupt data, wrong scope или malformed returned output — infrastructure/contract failure с cause, не no-op и не expectation business conflict. Bound output error использует принятый H2 SectionHandlerContractError mapping; Snapshot не копирует domain validator. Runtime batch budget и acceptance budget должны иметь declared Time owners и failure mapping; исчерпание не выдаёт успешную section/receipt.

Unknown commit → OUTCOME_UNKNOWN, не утверждение rollback и не новая operation_id; exact terminal replay возвращается до source reads/digests/handlers. Cancellation использует existing scope drain/revoke и H2 путь, сохранённый OperationCancelled engine mapping не переоткрывается. Typed business refusal возвращается после rollback и confirmed refusal persistence; общий success — после confirmed commit. Ни settings-only, ни before==after не обходят эти правила.

## 5. Exact remaining gaps и независимая реализация

| Owning gap | Что требуется для dependent integration |
|---|---|
| Expected-version operand | Time фиксирует Q-only либо explicit CalendarVersionRef operand и preservation до native; Snapshot не изобретает versions |
| Scoped accepted settings read | Concrete class.method Input/Output/Error, exact Q/source и read_scope; required clock binding в settings-only registration; никаких public foreign reads |
| Append no-op result | Один active typed result, unchanged version guarantee; pinned-base receipt states=()/history=()/changed=() подтверждён. History policy закрыта дополнением Time; headless continuity требует отдельного owning source mapping |
| Apply refusal/closed result | D_settings и local refusal_model, contrast pure preparation refusal; общий registry/result/record/manifest closure с advance по H2. Existing Time result/root20150 не расширяется молча |
| Mutual dependency freeze | Time дополнительно подтвердил pinned Q и отсутствие чтения изменённого sibling clock; при сохранении разных write namespaces Snapshot поддерживает пустые mutual deps, координатор фиксирует общий freeze. Общая transaction не требует edge |

Независимы от этих durable gaps: pure S2 native wrapper/producer и S3–S4 batch/candidate helpers в пределах отдельно принятого Time плана и implement-plan; они не требуют готового Snapshot SQL/runtime wiring. Перед ними остаётся обязательная локальная приёмка exact signatures/POJO/размещения/budget semantics владельцем, а не ожидание production integration. Ни новые nodes/IDs, ни код этой сверкой не разрешаются. Независимый C2 facts/predicates срез Snapshot не зависит от settings policy/manifest.

Результат: common Q/effective_at relations, all-validate-before-apply/immediate C2, atomic/unknown/replay совместимы с решением пользователя. Exact settings runtime binding остаётся OPEN только по перечисленным operands/source/result/error/dependency obligations. Нет общего runtime PASS; H2/C2/H3 не переоткрыты. Изменён только owning Snapshot review; time-domain.md и общий coordinator план не редактировались.
