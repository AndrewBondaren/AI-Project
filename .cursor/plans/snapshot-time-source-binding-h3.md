# Snapshot → Time: exact source binding H3

2026-11-20. **PROPOSED: точные DTO, signatures и ошибки**, для приёмки Time, координатором DAG и пользователем. Только поправка порядка H3/C2-R1 уже ACCEPTED: source metadata после expected-context checks до всех handler.validate; затем дочитывание остальных bases до apply, reuse в одной попытке. Источники: [C2 §4–5](snapshot-receipt-validation-c2.md), [Time IC-1/H3](time-domain.md), [реестр](interdomain-contract-register.md). Не CODE-GO, не приёмка H2/terminal и не закрытие Snapshot ARCH-0.

## 1. Граница и типы

Snapshot владеет соответствием exact publication Q → адрес принятого состояния. Time владеет чтением и проверкой своего payload. SnapshotSectionSourceResolver — внутренний компонент атомарной Snapshot apply, не public pipeline/новая DAG-нода. Внешний порядок write_changes → prepare_changes → assemble_patch_set → apply_snapshot не меняется; upstream inputs не переоткрываются.

Предлагаемый модуль `backend/app/dataModel/worldSnapshot/reads/sectionSource.py`:

| Record | Поля |
|---|---|
| SectionSourceRequest | publication: WorldPublicationRef; section_key: SectionKey |
| SnapshotSectionSource | query_publication: WorldPublicationRef; state_ref: SectionStateRef |
| InitialSectionSource | query_publication: WorldPublicationRef; source_publication: WorldPublicationRef; section_key: SectionKey |
| SectionSourceBinding | alias SnapshotSectionSource \| InitialSectionSource, без общего нетипизированного payload |

Все records: BaseModel с frozen=True, strict=True, extra='forbid', revalidate_instances='always'. Переиспользуются owning refs; ни connection/scope, ни TimePoint/TimeClockState, ни mirror publication fields в records нет. Это ephemeral execution input; новые canonical IDs, persisted binding table и wire endpoint не вводятся.

Локальные инварианты SnapshotSectionSource: Q.gameplay_started; Q.snapshot_head существует и относится к Q.active_timeline_id; state_ref.snapshot — WorldSnapshotRef с теми же world и active timeline. Равенство state_ref.snapshot == Q.snapshot_head НЕ требуется. Ключ binding определяется state_ref.section_key. Format version сохраняется без преобразования; поддержку Time state version проверяет Time.

Локальные инварианты InitialSectionSource: Q.gameplay_started; source_publication == query_publication полным равенством; Q.head отсутствует либо является уже допущенным publication guard branch point другого timeline. Для head текущего timeline initial variant запрещён. Это адрес publication-bound state Q, а не заявление, что Q — первая публикация мира. Поиск initial ancestor и подстановка другого source_publication не входят в этот контракт. Наличие payload доказывает Time read, не constructor.

POJO не доказывает ancestry/retention. Достоверность binding обеспечивается только resolver из exact accepted metadata после owning publication guard. Переданный caller/proposal binding не принимается как источник. При необходимости расширить контракт на player sources требуется отдельная приёмка; эта версия разрешает только world-section source.

## 2. Resolver и чтения

Предлагаемый модуль `backend/app/application/worldSnapshot/service/sectionSourceResolver.py`:

`SnapshotSectionSourceResolver(publications: IExactWorldPublicationReader, metadata: SnapshotAttemptMetadataReader)`

`async resolve(self, request: SectionSourceRequest, *, scope: CommitReadScope) -> SectionSourceBinding`

Ошибки: strict admission ValidationError; SnapshotSourceResolutionError (ниже); owning IO/scope/cancellation exceptions без blanket catch. Метод не возвращает None/business refusal, не начинает transaction, не вызывает Time или public Snapshot reads.

Последовательность:

1. read_exact(request.publication.world_uid, request.publication.publication_id, scope=scope); отсутствующая публикация — PUBLICATION_MISSING; полное несовпадение — PUBLICATION_MISMATCH. Expected-context guard уже выполнен; несогласованность здесь — infrastructure fault, не повторная бизнес-проверка stale head. Не читать latest.
2. Проверить started/active context. Для недопустимого состояния — PUBLICATION_NOT_STARTED или SOURCE_CONTEXT_INVALID; foreign-timeline branch point обязан быть ранее проверен publication guard. Resolver не изобретает новую ancestry policy.
3. Для head текущего timeline прочитать exact WorldSnapshotMetadata через attempt reader. Выбрать ровно одну states entry с request.section_key. Вернуть сохранённый entry.state целиком, включая ancestor snapshot и version. Проверить world/timeline/key. Нет обхода предков в поисках более удобного источника: accepted metadata содержит retained source; missing entry — fault.
4. Для разрешённой publication-bound ветки вернуть InitialSectionSource(Q,Q,key), без snapshot metadata lookup. Никакого zero clock, fake snapshot или fallback после missing/corrupt metadata/section/payload.

`SnapshotAttemptMetadataReader` — новый внутренний application-only класс в `application/worldSnapshot/service/attemptMetadataReader.py`: constructor(history: ISnapshotHistoryStore, scope: CommitReadScope); `async read(self, ref: SnapshotRef) -> SnapshotEnvelope | None`. Экземпляр создаёт service на одну попытку и один read scope. Он проверяет active scope, exact ref и тип envelope (world/player), строго валидирует persisted envelope и кеширует только успешно проверенные envelopes по полному ref. None не кешируется; текущий dependent path прекращается на missing. Повторный read того же ref возвращает тот же проверенный envelope без IO. Resolver обязан передать тот же scope, которым создан reader; несовпадение — ошибка внутреннего вызова. Нет shared/global cache и persisted projection.

После validations service через тот же reader дочитывает world base, затем player bases в исходном порядке, пропуская None heads. Полный упорядоченный набор формирует service из exact expected refs, а не из порядка заполнения кеша. Metadata builder и receipt validator получают этот набор. Для пустых sections раннего source resolution нет, требуемые bases всё равно читаются после пустой validation фазы. Отдельные missing-base diagnostics C2 не перепроектируются этим контрактом.

Existing AcceptedStateReader не внедряется в Time. При реализации owning Snapshot должен переиспользовать/выделить его pure selection и identity checks, а не поддерживать второй расходящийся алгоритм. Его нынешний прямой history read нельзя использовать в новом пути в обход attempt reader. Public query source SnapshotTimeReadSource не меняется этим предложением.

## 3. Точные ошибки resolver

Модуль `backend/app/dataModel/worldSnapshot/diagnostics/sectionSource.py`:

- SnapshotSourceFaultCode(StrEnum): PUBLICATION_MISSING, PUBLICATION_MISMATCH, PUBLICATION_NOT_STARTED, SOURCE_CONTEXT_INVALID, METADATA_MISSING, METADATA_CORRUPT, METADATA_IDENTITY_MISMATCH, SECTION_MISSING, SECTION_AMBIGUOUS, STATE_IDENTITY_MISMATCH. Wire values соответственно `snapshot.source.publication_missing` и остальные имена в lower_snake_case с тем же prefix.
- SnapshotSourceFault: code: SnapshotSourceFaultCode; request: SectionSourceRequest; observed_publication: WorldPublicationRef | None. Strict/frozen/extra-forbid/revalidate-always. observed_publication обязателен только для PUBLICATION_MISMATCH и должен отличаться от request.publication; для остальных кодов None. Это relation fault без выдуманного FieldPath.
- `application/worldSnapshot/errors.py::SnapshotSourceResolutionError(PublicationInfrastructureError)`; constructor(fault: SnapshotSourceFault). Один exact fault, не пустая коллекция и не business result. Cause сохраняется для known persisted decode/validation error. Дополнительные неизвестные IO ошибки не переименовываются в corruption.

METADATA_IDENTITY_MISMATCH — envelope не того owner/type/ref; METADATA_CORRUPT — невалидное persisted представление; SECTION_AMBIGUOUS — несколько допустимых для чтения entries одного key (если strict envelope уже отверг duplicate, первична METADATA_CORRUPT). STATE_IDENTITY_MISMATCH — ref нарушает world/timeline/world-owner constraints. Это стабильный fail-fast порядок, не обещание агрегировать faults после отсутствующего source. Required Time payload missing/corrupt/version mismatch остаётся TimeCommitInfrastructureError, не SnapshotSourceFault. Cancellation/unknown rollback сохраняют установленный приоритет; terminal refusal ради source fault не записывается. Public fault transport/H2 не принят этим разделом.

## 4. Context mapping и lifetime

PROPOSED `SnapshotValidationContext.section_sources: tuple[SectionSourceBinding, ...]` в existing `application/worldSnapshot/contracts/context.py`. Context остаётся application-only capability. Service constructor получает `source_required_keys: tuple[SectionKey, ...]` от composition: уникальные зарегистрированные keys; для IC-1 явно CLOCK_SECTION. Это декларация потребности transaction participant, не callback/foreign pipeline и не чтение Time payload. C1 registry/codec API не расширяются.

На конкретном apply service выбирает пересечение source_required_keys с keys исходных sections, в порядке sections. Для каждого ровно один resolve(SectionSourceRequest(expected_world,key), scope=read_scope); никаких reads для отсутствующих секций. Сначала разрешает все требуемые источники, затем начинает validate. Context construction проверяет уникальность binding keys, полное query_publication == expected_world и точное покрытие выбранных required keys; missing/extra/duplicate binding — внутренняя contract ошибка до handler. Coverage проверяет service, имеющий список requirements, а не POJO в изоляции.

Time mapping: выбрать единственный CLOCK_SECTION из context.section_sources; создать proposed TimeAcceptedStateRead(publication=context.expected_world, source=binding). TimeAcceptedStateReader.read(request, scope=context.read_scope) проверяет query Q/key и читает только Time storage: read_section(binding.state_ref,scope) либо read_binding(binding.source_publication,scope). Capture.publication всегда Q, point берётся из payload; payload.ref/publication сверяется с source отдельно. Metadata/proposal.base.point не заменяют этот read.

Apply использует context.validation.section_sources и context.scope.read_scope, без повторного resolver. Для writer предлагается уточнить Time binding: `ITimeCommitBinding.bind(scope: CommitScope, *, source: SectionSourceBinding) -> IBoundTimeStateWriter`; bound writer хранит source только до окончания scope и повторяет Time read с исходным Q из patch.proposal.base.publication. Это новая PROPOSED Time signature delta, требует Time/координаторской приёмки; existing generic binding интерфейс молча не изменяется. Альтернатива передачи source через другой Time-owned internal метод требует явной фиксации, а не скрытого Snapshot callback.

Snapshot удерживает transaction/предусмотренную existing publication protection до завершения всей попытки; ни resolver, ни Time не acquire/release независимый scope/holder. Чтение metadata не является physical retention authority. При отсутствии необходимой защиты payload cleanup в supplied transaction runtime не принимается. POJO можно инспектировать после возврата, но использовать его как доверенный binding следующей попытки запрещено: заново resolve. Reader/bound writer отвергают доступ после закрытия scope. Replay выходит до source resolution, cancellation прекращает зависимые шаги, owner завершает transaction; Time соблюдает свой drain IO контракт.

## 5. Trace, ответственность и приёмка

Trace: existing admission → fingerprint → claim/binding/replay → outer transaction → expected-context checks → Snapshot source resolver (только metadata/refs) → все handler.validate (Time читает actual payload) → остальные C2 bases с reuse → handler.apply и immediate C2 receipt checks → existing metadata/handoff/CAS/terminal/commit. Source fault может предшествовать semantic refusal — ACCEPTED; validation refusal запрещает дочитывание остальных bases и все apply, но не отменяет уже выполненные source reads.

| Компонент | Ответственность / зависимости / отказ в приёмке |
|---|---|
| Source records / fault | Только strict данные и локальные инварианты; отказ при IO, Time payload mirror, фиктивном path или заявлении ancestry proof конструктором |
| WorldSnapshotService | Порядок, required-key selection, context coverage, одна transaction и reader; отказ при runtime Time-key hardcode, foreign public call, reorder или новом scope |
| SnapshotSectionSourceResolver | Exact Q → retained ref/publication source через Snapshot ports; отказ при latest/fallback, ref=Q.head по предположению или чтении Time SQL |
| SnapshotAttemptMetadataReader | Exact validated metadata reuse в одной попытке; отказ при cross-scope cache, повторном IO на hit или domain payload read |
| Existing exact-publication/history ports, adapters, publication guard | Read-only exact IO в borrowed scope; guard сохраняет owning ancestry/accepted checks. Отказ при самостоятельной transaction или обходе lifecycle protection |
| Existing AcceptedStateReader | Owning selection semantics согласуются с resolver; отказ при копии расходящихся predicates; query scopes не переносятся в handler |
| SnapshotValidationContext / ApplyContext | Неизменная mapping Q/sources/read facet; отказ при public DTO capability leakage, extra/missing bindings или замене sources в apply |
| Time reader/handler/bound writer | Actual payload identity/version/point и Time semantic rules, только Time storage; отказ при Time→Snapshot, foreign SQL, own transaction, fallback или доверии proposal вместо state |
| Existing receipt validator / metadata builder | Получают полный набор bases после validations; не разрешают source и не читают payload; отказ при повторном base IO |

Документальная сверка трёх запретов DAG: нового pipeline route branching нет; скрытого запуска public pipelines нет; Time→Snapshot/foreign public calls запрещены. Handler остаётся принятым transaction participant внутри атомарной apply, не самостоятельной междоменной оркестрацией. Статус локального trace — соответствует принятой поправке; whole-domain PASS не заявляется.

Обязательное evidence перед runtime приёмкой: inherited ref != Q.head; headless source Q с реальным payload; допустимый foreign-timeline branch point читает publication-bound Time state Q; Q mismatch; missing/duplicate/wrong-owner retained source; missing/corrupt/versioned Time payload; отсутствие fallback во всех failure ветках; source fault до validation; validation refusal без remaining base reads; ровно один history read на общий source/base; исходный world/player порядок полного набора; empty sections; replay без sources; отмена/закрытый scope; запрет Time foreign calls и отсутствие copies predicates. Tests ещё не выполнены: код не начат.

OPEN до приёмки: Time подтверждает source-bearing read/bind signatures; координатор проверяет closed composition required keys/context и branch-point lifecycle; owning ТЗ синхронизируется; reuse selection predicates и physical cleanup protection подтверждаются при реализации. H2/terminal, общий C2 diagnostic redesign и upstream producers вне этого решения.
