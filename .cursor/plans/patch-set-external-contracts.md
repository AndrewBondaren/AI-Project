# PatchSet: внешние контракты и интеграции

Дата: 2026-11-18. Статус: **отдельный реестр интеграционных зависимостей; НЕ БЛОКИРУЕТ приёмку ядра PatchSet**.

Основание: пользователь поручил «Внешние контракты зафиксируй отдельно, но не блокирующими приемку». Архитектура ядра — [PS-ARCH-0](patch-set-domain-architecture.md). Ни один OPEN ниже не возвращается в её блокеры. Каждый контракт уточняется перед подключением соответствующего сценария; Time/Lifecycle приведены как известные кандидаты, не обязательные участники каждого набора.

## Правила закрытия интеграции

Для подключаемого производителя фиксируются владелец, public class/module/method, полная сигнатура и Input/Output/Error POJO, конкретное соответствие Output → PatchSetAssemblyInput, гарантии базы/identity, маршрут передачи через DAG и проверки. Production binding проверяется отдельно. Существование DTO, тестовой специализации или подходящего поля не доказывает готовность всей интеграции. При уточнении не переносить подготовку чужих данных в ядро PatchSet.

## Карта внешних связей (PS-R2)

Повторно проверены `.cursor/plans/time-domain.md`, `docs/tz_entity_lifecycle.md`, actual `dataModel/time`, `application/time`, existing Snapshot apply port и refs. Наличие планируемой section модели не доказывает готовность публичного producer.

| Потребность | Найденное evidence | Чего не хватает для приёмки |
|---|---|---|
| Time section | Time plan описывает TimeAdvanceSection как DomainSection[TimeAdvanceProposal], один proposal на acceptance group; registration и integration имеют OPEN | Exact публичного производителя native section, его Input/Output/Error и подтверждённого mapping с current Time preparation; не конструировать это внутри DAG/PatchSet |
| Lifecycle section | ТЗ Lifecycle: proposed publication/section.py, LifecycleSection; LC-C09 и LC-C11 сохраняют native binding OPEN | Полей concrete section/patch, публичного producer, cardinality/coverage и связи change_uid с publication operation_id; их нельзя приравнять |
| Expected world | Existing WorldPublicationRef; owning Snapshot план имеет read_publication/read_current_publication контракты | Выбор конкретного capture для этого сценария и доказательство согласованности с другими inputs; одиночное current-read не даёт автоматически coherent batch |
| Expected players | Existing PlayerHeadExpectation | Exact метода capture игроков и согласованности с expected_world; не выводится из существования DTO |
| Preparation identity | Existing operation_id/preparation_fingerprint поля; Lifecycle явно отделяет change_uid от общей операции | Публичного producer общего binding и правила повторного использования identity; домен PatchSet не назначает его |
| Consumer | Existing `IWorldSnapshotApply.apply[S: DomainSection](patch_set: PatchSet[S]) -> SnapshotApplyResult` | Native closed union и owning public lifecycle readiness; сама сигнатура подтверждена |

Запрос к владельцам для следующего согласования: для каждого producer предоставить class/module/full method signature, именованные Input/Output/Error, состав native section и identity binding, гарантии coherent base и mapping конкретных output fields в унаследованные поля PatchSetAssemblyInput. Для Time/Lifecycle отдельно подтвердить необходимость producer section как собственной публичной операции; PatchSet не назначает её за владельца.

Пакет generic ядра не должен импортировать Time/Lifecycle ради такого union. Composition root свяжет именованные child models с одним и тем же принятым union. До его получения нет production binding; отсутствие consumer нод само по себе не запрещает отдельную приёмку общего контракта. Междоменные методы сейчас не выдуманы и ни один owner gap не объявлен закрытым.

#### PS-R2: повторная сверка с Between domain operations

По поручению продолжить следующий пункт 2026-11-18 получена повторная консультация агента `Between domain operations` (чат `01a1ef35-3287-7a12-89e2-76273eaa043d`). Она подтверждает OPEN production-маршрута, не принимает за владельцев отсутствующие контракты. Дополнительный источник их статусов — [уточнения владельцев DAG write](dag-write-owner-contract-clarifications.md). Ниже — конкретизация, заменяющая общую формулировку «неизвестны producers».

**Actual Time API:** `application/time/changes/advancePipelineOpenPipeline.py`, `TimeAdvancePipelineOpenPipeline.prepare_advance(request: PrepareAdvance) -> TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow`. Input/успех — `dataModel/time/changes/advance.py`; ошибки — `dataModel/time/results/errors.py`. PrepareAdvance содержит operation_id, base:TimeCapture, duration:TimeDuration; proposal — operation_id, base, interval:TimeInterval. Метод сохраняет переданный operation_id, не назначает общую публикационную identity. TimeAdvanceProposal не является DomainSection и непосредственно в sections не допускается. Публичный producer native section с header/dependencies ещё не подтверждён.

| Поле PatchSetAssemblyInput | Подтверждённый тип / кандидат источника | Неподтверждённая часть и запрет подмены |
|---|---|---|
| sections | tuple[S,...], S — concrete native DomainSection | Exact producers и production union OPEN. Proposal не оборачивается DAG/assembler самостоятельно |
| expected_world | WorldPublicationRef; TimeAdvanceProposal.base.publication имеет этот тип | Это лишь кандидат mapping: общая coherent база всех секций ещё не подтверждена; exact read/capture Input/Output/Error нужен |
| expected_players | tuple[PlayerHeadExpectation,...] | Producer состава участников и captured heads OPEN; пустой tuple не default вместо неизвестного состава |
| operation_id | EntityUid; Time принимает и возвращает значение | Producer общей операции, момент назначения и retry reuse OPEN; change_uid Lifecycle не заменяет эту identity |
| preparation_fingerprint | RevisionHex | Exact immutable inputs, producer и retry/staging binding OPEN; request_fingerprint Snapshot не подставляется вместо него |
| timeline_id | EntityUid; TimeCapture проверяет point.timeline_id относительно своей publication | Совместимость всей общей операции не следует из локального TimeCapture; mapping требует подтверждения |
| turn_id | StrictInt >= 1 | Владелец назначения целевого turn и producer OPEN; не вычислять из duration и не прибавлять один по предположению |
| world_uid | EntityUid | Источник в общем public write request/capture ещё должен быть закреплён; равенство expected_world проверяет assembler, но не создаёт provenance |
| format_version | FormatVersion | Принятое version binding общего запроса ещё требуется для production composition; assembler не выбирает версию автоматически |

**Следующие адресные вопросы владельцам:** Time/Lifecycle — concrete native-section producer с Input/Output/Error, cardinality/dependencies и identity mapping; владелец publication capture — coherent world/player expectations и источник timeline/turn; владелец общей подготовки — operation identity/preparation fingerprint и retry/staging binding; владелец composition root — production union и две именованные child специализации, совместимые со Snapshot. Отсутствующий метод не считается разрешением создать его внутри PatchSet.

**Разделение приёмки принято пользователем:** «делай приемку ядра по архитектуре, дальнейшие контракты могут уточняться». Generic ядро проверяется отдельно без импортов Time/Lifecycle. PS-R2 и production union не блокируют архитектуру ядра; test-only specialization не заменяет production binding. Точный результат проверки ядра — §8 архитектурного плана. Для production-маршрута PS-R2 остаётся OPEN до exact owner contracts и Output → Input.


