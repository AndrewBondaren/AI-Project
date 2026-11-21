# PatchSet: внешние контракты и интеграции

Дата: 2026-11-18; актуализировано 2026-11-20. Статус: **отдельный реестр принятых границ и открытых интеграционных зависимостей; НЕ БЛОКИРУЕТ приёмку ядра PatchSet**.

Основание: пользователь поручил «Внешние контракты зафиксируй отдельно, но не блокирующими приемку». Архитектура ядра — [PS-ARCH-0](patch-set-domain-architecture.md). Ни один OPEN ниже не возвращается в её блокеры. Каждый контракт уточняется перед подключением соответствующего сценария; Time/Lifecycle приведены как известные кандидаты, не обязательные участники каждого набора.

## Правила закрытия интеграции

### SN-Q1.1 — принятая зависимость Snapshot от общего checker

**Граница принята пользователем 2026-11-19 после разбора Between domain operations.** Источник решения и актуальный статус внутренних работ — [Snapshot SN-Q1.1](world-domain-patches-snapshots.md#sn-q11--междоменная-гарантия-prepared-order-на-входе-apply); точный контракт helper — [архитектура PatchSet §9.2](patch-set-domain-architecture.md#92-ps-rev-2-один-источник-правил-два-представления-результата).

- Application-маршрут: assemble → результат в DAG → apply Snapshot; отказ сборки исключает apply. Snapshot не вызывает assemble.
- Разрешённая зависимость модели: Snapshot dependency admission → PatchSetInvariants.check_prepared_order в dataModel/patch/validation/patchSetInvariants.py. Входной PatchSet[S] передаётся как PatchSetData[S]; результат — tuple[PatchSetInvariantViolation, ...]. Patch core владеет predicates и facts, Snapshot — адаптацией facts к своей диагностике; копирования predicates и обратной application-зависимости нет.
- Проверка выполняется до immutable binding/terminal replay без IO. Constructor/decode сохраняет только check_core; успех assemble дополнительно гарантирует prepared-order. Fingerprints, PUBLISHED dependencies и предметная допустимость этим checker не подтверждаются.
- SN-Q1-I1…I4 остаются внутренними OPEN Snapshot: место вызова/классы, diagnostics, отказ до claim, recovery/retry trace. Они не блокируют ядро и не требуют повторного согласования неизменной границы. Изменения публичных Input/Output/Error или разрешённых внешних callers согласуются отдельно через координатора.

Сверка с owning SN-Q1.1 выполнена: ответственность, направление зависимости, факты и порядок совпадают. Реализация Snapshot и DAG wiring в PS-I1 → PS-I2 не входят; архитектурная приёмка зависимости не подтверждает runtime readiness.

**Ответ координатора 2026-11-19: место вызова — PASS, вопрос закрыт.** Внутри Snapshot apply: structural revalidation/check_core → dependency admission/check_prepared_order → canonical request fingerprint → immutable binding/claim/exact terminal replay. Поддержана целевая привязка `SnapshotRequestValidator.validate(request: PatchSet[S]) -> None` в `application/worldSnapshot/service/snapshotRequestValidator.py`; это TARGET, не existing runtime. Дополнительный private `_check_prepared_order` необязателен. OPEN остаются owning diagnostic carrier/aggregation/transport и полнота внутренних dependency checks Snapshot; выбор позиции в общей цепочке больше не OPEN. Источник: ответ Between domain operations на адресный запрос пользователя, thread `01a1ef35-3287-7a12-89e2-76273eaa043d`.

### TIME-PATCH-1 — несовместимость проектной секции с PatchData

#### Canonical IDs: решение пользователя и подтверждение PatchSet — 2026-11-20

**ACCEPTED:** пользователь через координатора принял шесть назначений ниже. **Owning-подтверждение PatchSet — PASS в области общего patch manifest и подключения native sections.** Эта запись имеет приоритет над историческими пометками proposed/неназначенного patch ID ниже. Полная интеграция IC-1 остаётся OPEN.

| Тип | Принятый canonical ID | Evidence |
|---|---:|---|
| TimePoint | 31100 | Existing класс; merge с PATCH_CORE_SCHEMA проверен |
| TimeInterval | 31102 | Existing класс; merge с PATCH_CORE_SCHEMA проверен |
| TimeCapture | 31103 | Existing класс; merge с PATCH_CORE_SCHEMA проверен |
| TimeAdvanceProposal | 31104 | Existing класс; merge с PATCH_CORE_SCHEMA проверен |
| TimeAdvanceSection | 31105 | Нет конфликта ID с core; binding будущего concrete класса ещё не проверен |
| TimeAdvancePatch | 31107 | Нет конфликта ID с core; binding будущего concrete класса ещё не проверен |

Фактическая проверка 2026-11-20: поиск этих номеров в backend, .cursor/plans и docs не обнаружил конкурирующих назначений другим типам. Read-only Python probe загрузил [PATCH_CORE_SCHEMA](../../backend/app/application/patch/encoding/coreManifest.py): 62 entries, пересечение с шестью IDs пустое. Реальный [merge_manifests](../../backend/app/encoding/canonicalCodec.py) успешно объединил core с четырьмя existing Time records — 66 entries. Два будущих класса не заменялись заглушками; успешный merge полного manifest из шести Time records не заявляется. Предложенный TimeClockState=31106 не входит в эти назначения.

**Границы владения.** PatchSet отвечает за общий patch manifest и совместимое подключение секций через SectionContract/SectionRegistry; конкретные Time records и representation принадлежат Time. Отдельный глобальный владелец резервации canonical IDs в проверенных источниках не установлен и этой записью не назначается. SectionRegistry — registry конкретной композиции, не глобальный allocator. Решение пользователя о назначениях и подтверждение PatchSet не доказывают глобальную runtime-регистрацию. Если требуется отдельный authoritative реестр резерваций между независимыми compositions, координатор должен установить его владельца.

**Обязательные проверки реализации:**

1. Merge PATCH_CORE_SCHEMA с шестью настоящими concrete Time classes; отсутствие ID→разные declarations и owner→разные identities. Полностью одинаковые shared declarations допускаются existing merge.
2. Полная transitive closure: Section → Patch → Proposal → Capture/Interval → Point плюс shared header/publication/ref/dependency/artifact types. Core уже содержит WorldPublicationRef, WorldSnapshotRef, PatchHeader, PatchRef и SectionHeader.
3. Базы TimeRecord/TimeScope/PatchData не получают ID только из-за наследования; вычисляемые properties не добавляются в manifest как сериализуемые поля.
4. Concrete round-trip всех допустимых nullable/union веток, native invariants и отказы неизвестных ID/version. Успешный merge не является доказательством closure.
5. Повторная collision-проверка с остальными manifests выбранной runtime composition; production union сейчас не назначается.
6. Exact same SectionContract instance у handler/codec/registry, key time_clock и supported section versions {1}, по принятой форме C1.

**Остаток:** concrete manifest/runtime registration и evidence реализации; глобальная резервация отдельным механизмом не доказана. Нового code-go, миграций или повторной приёмки ядра PS-I1→PS-I2 нет. Источники решения — [IC-1](interdomain-contract-register.md#ic-1--time-native-section), [Time-план](time-domain.md); источник owning evidence — проверка PatchSet по адресному запросу координатора 2026-11-20.

#### История согласования формы

**Дополнение 2026-11-19:** пользователь принял форму concrete TimeSectionCodec и manifest из shared PATCH_CORE_SCHEMA + шести Time records (Point/Interval/Capture/Proposal/Patch/Section), time_clock/version1 и exact contract identity по C1. Точный контракт записан в time-domain.md. Canonical IDs пяти Time records пока proposed, нового patch не назначен; общий registry audit/подтверждение и implementation/runtime OPEN. Это не повторная приёмка ядра PatchSet.

**Уточнение 2026-11-19 — локальная дельта ACCEPTED пользователем через координатора.** Приняты TimeAdvancePatch(PatchData){proposal:TimeAdvanceProposal}, TimeAdvanceSection[TimeAdvancePatch] с одним patch и Time-owned header: общий operation_id, time_clock, ordinal0, patch version1, пустые dependencies/artifacts; native equality proposal/header operation проверяется также при decode. Pure proposal/API и Input/expected errors prepare_section сохраняются; successful receipt возвращает исходный patch.header.ref. Ни DAG, ни assembler header не вставляют. Исторический gap формы ниже устранён на уровне решения, не реализации. Concrete Time codec/manifest/IDs и production integration OPEN. См. [IC-1](interdomain-contract-register.md#ic-1--time-native-section).

Зафиксировано 2026-11-19. **OPEN интеграции Time; не блокирует архитектурную приёмку ядра PatchSet.**

В [Time-плане §10](time-domain.md) TimeAdvanceSection задан как DomainSection[TimeAdvanceProposal]. Existing [TimeAdvanceProposal](../../backend/app/dataModel/time/changes/advance.py) содержит operation_id/base/interval, но не PatchHeader и не наследует PatchData. Поэтому эта форма несовместима с принятым целевым bound DomainSection[P: PatchData] из [архитектуры ядра §9.1](patch-set-domain-architecture.md#91-ps-rev-1-patchref--общий-инвариант-ядра).

Перед подключением владелец Time должен согласовать native patch с общим header, его связь с existing proposal, producer Input/Output/Error, operation/section/ordinal binding и codec/manifest. Выбор изменения proposal или отдельного native patch принадлежит владельцу Time; этот реестр его не назначает. DAG и PatchSet не вставляют header через cast/adapter, не угадывают ordinal и не объявляют proposal совместимым по совпадению части полей.

Критерий закрытия: owning Time-план и concrete модели согласованы с принятым общим header contract; section действительно связана с соответствующим PatchData subtype; общий operation/section/ordinal и canonical binding проверены. Actual Time API и его код этой записью не меняются. PatchData реализован в PS-I1 (2026-11-19); TimeAdvanceProposal непосредственно как native patch не допускается. Здесь зафиксирована несовместимость проектной Time-секции с общим контрактом; runtime pure Time proposal этой правкой не изменён.

### Общие требования к внешним контрактам

Для подключаемого производителя фиксируются владелец, public class/module/method, полная сигнатура и Input/Output/Error POJO, конкретное соответствие Output → PatchSetAssemblyInput, гарантии базы/identity, маршрут передачи через DAG и проверки. Production binding проверяется отдельно. Существование DTO, тестовой специализации или подходящего поля не доказывает готовность всей интеграции. При уточнении не переносить подготовку чужих данных в ядро PatchSet.

## Карта внешних связей (PS-R2)

**Актуализация 2026-11-21:** локальный Time producer ACCEPTED: application/time/changes/advancePipelineOpenPipeline.py::TimeAdvancePipelineOpenPipeline.prepare_section(request:PrepareTimeAdvanceSection) -> TimeAdvanceSection | TimeSectionContextMismatch. Вход содержит proposal, operation_id, expected_world; результат — native TimeAdvancePatch внутри секции, header создаёт Time. Источники: Time-план и interdomain-contract-register.md, IC-1. Повторное согласование producer/необходимости операции не требуется. Отдельный остаток — production registration/composition, concrete manifest и runtime wiring/evidence; их статус не означает отсутствия контракта. Исторические записи ниже «producer не подтверждён» заменены этой фиксацией.

Повторно проверены `.cursor/plans/time-domain.md`, `docs/tz_entity_lifecycle.md`, actual `dataModel/time`, `application/time`, existing Snapshot apply port и refs. Наличие планируемой section модели не доказывает готовность публичного producer.

| Потребность | Найденное evidence | Чего не хватает для приёмки |
|---|---|---|
| Time section | Принятый prepare_section(PrepareTimeAdvanceSection) -> TimeAdvanceSection \| TimeSectionContextMismatch; native payload TimeAdvancePatch, не голый proposal | Production registration/composition, manifest/runtime wiring и evidence реализации; контракт producer повторно не открывается |
| Lifecycle section | ТЗ Lifecycle: proposed publication/section.py, LifecycleSection; LC-C09 и LC-C11 сохраняют native binding OPEN | Полей concrete section/patch, публичного producer, cardinality/coverage и связи change_uid с publication operation_id; их нельзя приравнять |
| Expected world | Existing WorldPublicationRef; owning Snapshot план имеет read_publication/read_current_publication контракты | Выбор конкретного capture для этого сценария и доказательство согласованности с другими inputs; одиночное current-read не даёт автоматически coherent batch |
| Expected players | Existing PlayerHeadExpectation | Exact метода capture игроков и согласованности с expected_world; не выводится из существования DTO |
| Preparation identity | Existing operation_id/preparation_fingerprint поля; Lifecycle явно отделяет change_uid от общей операции | Публичного producer общего binding и правила повторного использования identity; домен PatchSet не назначает его |
| Consumer | Target H2: IWorldSnapshotApply[S:DomainSection,T], async apply(self,patch_set:PatchSet[S])->T; S instance-bound, T concrete result. Actual старый порт method-generic | Runtime migration/wiring отдельно; проектирование нод по target Snapshot H2, TimeSnapshotApplyResult без legacy wrapper |

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

**Разделение приёмки принято пользователем:** «делай приемку ядра по архитектуре, дальнейшие контракты могут уточняться». Generic ядро проверяется отдельно без импортов Time/Lifecycle. PS-R2 и production union не блокируют архитектуру ядра; test-only specialization не заменяет production binding. Актуальный результат проверки ядра — §10 архитектурного плана; §8 сохраняет историю первой проверки. Для production-маршрута PS-R2 остаётся OPEN до exact owner contracts и Output → Input.


