# Snapshot: публичные контракты и последующая интеграция в DAG

**Актуальный архитектурный gate, 2026-11-15:** этот документ подчинён ARCH-0.1–ARCH-0.6 [owning-плана](world-domain-patches-snapshots.md). До полной целевой архитектурной приёмки code/DAG implementation не продолжается. Прежнее предложение одного WorldSnapshotService для apply и всех reads находится на пересмотре по требованию одной ответственности класса: proposed отдельный read owner, exact имя/port требуют приёмки. Existing DomainSectionHandler behavior+codec также выделен как явная SRP-дельта, не разрешение скрытого refactor. Прочие signatures/evidence сохраняются в своей области; новые классы этим документом автоматически не приняты.

Конкретное предложение первого public-среза: [snapshot-public-methods-contract.md](snapshot-public-methods-contract.md) — apply и два exact reads, поля POJO, public error transport, transaction traces и mapping Source/Pack/Cache. Уточнение первого пункта завершено до contract review: read-UOW issuer — existing SqlitePublicationCommitStore.read_scope через proposed ISnapshotReadScopeFactory, shape errors переиспользуются из existing JsonFieldError/WireShapeIssue. Предложение подлежит пользовательской приёмке; не означает полного CRUD или готового runtime. Current publication read остаётся отдельным срезом.

Дата: 2026-11-14. Статус: DRAFT / CONTRACT DESIGN, не принят к реализации. Авторизация текущего шага — подготовить отдельный план. Код, новые ноды, production wiring, миграции и переписывание принятых срезов не входят в этот шаг.

## 1. Рамки пользователя

1. Snapshot — отдельный домен. Другие домены не вызывают его напрямую и не пишут в Snapshot history/heads/stores. Их результаты получает DAG и передаёт публичному Snapshot entry.
2. Snapshot пока может использовать контракты Source, Pack, Cache при необходимости. Остальные междоменные контракты — только через DAG. Это разрешение не означает, что зависимости обязательны или их ещё открытые предложения уже приняты.
3. Все публичные методы и публичные pipelines, в том числе Source/Pack/Cache, вызываются только через DAG. Допустимые внутренние bindings необходимо отдельно идентифицировать; DI/callback не легализует публичный междоменный вызов.
4. Legacy adapters, миграции, dual-read и fallback запрещены. В уточняемом срезе домены реализуют новые согласованные контракты. По уточнению пользователя остальные домены, включая генераторы, сохраняют свои текущие контракты как v1; их сохранение не является разрешением писать адаптер v1→новый контракт.
5. Порядок: сначала согласовать публичные методы и POJO Snapshot; затем через чат DAG согласовать CRUD-ноды; после отдельной приёмки implementation/cutover. Этот документ не назначает ноды и не переносит эту ответственность в Snapshot.
6. Текущий объём междоменного уточнения — только Source, Pack, Cache. Остальные домены явно отложены с сохранением v1. Их переработка не является prerequisite текущего контрактного среза; зависимая от несовместимого v1 конкретная интеграция остаётся отложенной, без адаптера и без ложного заявления совместимости.

Источники: пользовательские рамки текущего чата; [обязательные критерии](../rules/dag-generator-interface.mdc); [Snapshot ТЗ](../../docs/tz_world_snapshot.md); [Patch ТЗ](../../docs/tz_patch_system.md); [owning-план ядра](world-domain-patches-snapshots.md). Приёмка 4C3/4D2 сохраняется в owning-плане, не переносится автоматически на публичный API. Новый план не меняет принятый порядок ядра, terminal/retry или Time T5 без отдельного согласования.

## 2. Проверенное исходное состояние

Пути далее относительно backend/app/.

| Объект | Факт и граница |
|---|---|
| application/worldSnapshot/contracts/applyPort.py::IWorldSnapshotApply | Existing Protocol: async apply[S: DomainSection](patch_set: PatchSet[S]) -> SnapshotApplyResult. Это не готовый concrete public class |
| application/worldSnapshot/service/worldSnapshotService.py::WorldSnapshotService | Existing внутренние _apply_to_target, _append_metadata, _append_metadata_and_handoff. Публичного apply в просмотренном классе нет |
| application/worldSnapshot/service/acceptedStateReader.py::AcceptedStateReader | Scoped read implementation; application-level union/enum не является согласованным public dataModel result |
| application/worldSnapshot/storage/historyStore.py::ISnapshotHistoryStore | append/read metadata, не публичный CRUD и не domain payload reader |
| application/worldSnapshot/storage/publicationStore.py | World/player CAS и exact publication reader — internal storage ports |
| application/worldSnapshot/contracts/context.py | SnapshotValidationContext/SnapshotApplyContext содержат scope. Не передаются через DAG и публичные DTO |
| application/patch/registry/sectionRegistry.py | Exact section dispatch внутри одной атомарной apply. Требуется аудит каждого handler на отсутствие публичных междоменных pipelines |

ТЗ назначает WorldSnapshotService commit/read/restore/branch. Наличие внутренних primitives не доказывает готовность этих публичных операций. Runtime acceptance публичного среза сейчас OPEN.

## 3. Целевая граница вызовов

Доменная публичная операция → результат в DAG → публичная операция Snapshot → результат в DAG. Все стрелки между доменами принадлежат DAG; Snapshot не запрашивает следующий публичный этап и не запускает producer самостоятельно.

Публичный Snapshot input не содержит CommitScope/CommitReadScope, lease, execution grant, SQL connection, handlers, callback, registry или выбор storage adapter. DAG не вызывает _append_metadata/compare_append/handoff и не назначает внутренние шаги transaction. Snapshot не интерпретирует смысл чужого payload за пределами принятого section contract.

Особо проверить конфликт старых scoped handlers с новой рамкой: handler чужого домена не получает право писать Snapshot metadata/heads. Если handler фактически вызывает публичный метод чужого домена или требует прямой неподтверждённый контракт вне Source/Pack/Cache, этот маршрут блокирует приёмку. Нельзя объявить его infrastructure только переименованием. Не переносить зависимую запись наружу transaction без анализа потери атомарности: предъявить конкретный контрактный конфликт пользователю до изменения.

## 4. Публичные операции — порядок проектирования

WorldSnapshotService в application/worldSnapshot/service/worldSnapshotService.py остаётся целевым owner apply lifecycle. Прежнее предложение назначить его owner всех reads/restore/branch пересматривается в ARCH-0: отдельный exact-read owner и прочие операции требуют точной приёмки. Второй фасад поверх сервиса не вводится. Ниже baseline операций и обязательные результаты проектирования, не утверждённая единая реализация этих операций.

| Операция | Основа | Что предъявить до приёмки |
|---|---|---|
| apply | Existing apply[S: DomainSection](patch_set: PatchSet[S]) -> SnapshotApplyResult | Concrete public method, exact generic admission/registration, публичный error map, terminal/replay/unknown/cancellation semantics, caller DAG |
| read exact snapshot | SnapshotRef и SnapshotEnvelope, existing history.read | Named input/result/error POJO, точный concrete read signature, missing vs corrupt, ownership и отсутствие head/latest fallback. Payload другого домена не выдаётся через чужой storage |
| read publication/state reference | WorldPublicationRef, SectionKey, AcceptedStateReader | Разделить metadata/publication read и чтение чужого payload; согласовать public dataModel result без scope и без копии existing refs |
| restore | Требование ТЗ, не существующий готовый API | Exact expected/target semantics, новая публикация или иная утверждённая операция, CAS, holders, result/error/replay; не перезапись старого snapshot |
| branch | Требование ТЗ; apply не создаёт ветвь автоматически | Exact branch base/timeline/expected contract, result/error, точка публикации и повтор |
| CRUD данных | Immutable snapshots и runtime PatchSet | Отдельно сопоставить create/read/update/delete с доменной семантикой. Не вводить update immutable row или физический delete history ради названий CRUD; при несовместимости предъявить решение/исключение пользователю |
| CRUD настроек | Принятый public Snapshot settings POJO в этом проходе не найден | Инвентарь реальных настроек и их владельцев, concrete named POJO + четыре метода. Отсутствие настроек/исключение требует явного основания, не подразумевается |

Для каждой строки обязательны полная сигнатура, поля Input/Output/Error, их модули dataModel, владелец, вызывающая сторона, invariants и критерий отказа. Пока строка не заполнена и не принята, соответствующий endpoint/node не проектируется как готовый. Статус CRUD/data/settings сейчас OPEN; домен целиком не объявляется принятым.

## 5. POJO и ошибки: reuse сначала

| Existing type / модуль dataModel | Ответственность и решение |
|---|---|
| patch/request/patchSet.py::PatchSet | format_version, operation_id, preparation_fingerprint, world_uid, timeline_id, turn_id, expected_world, expected_players, sections. Единственный existing runtime apply request; не зеркалировать в новом SnapshotWriteInput |
| patch/sections/section.py::DomainSection | База typed section; concrete model принадлежит owning domain. DAG не собирает внутренний payload по dict |
| worldSnapshot/identity/refs.py::SnapshotRef | Existing world/player identity union; повторный snapshot ID DTO не вводить |
| worldSnapshot/identity/publication.py | WorldPublicationRef и PlayerHeadExpectation — expected/CAS identity, не capability |
| worldSnapshot/metadata/envelope.py::SnapshotEnvelope | Existing world/player metadata: exact ref, parent/state/history/retained refs и owning metadata fields. Не выдавать за полный world payload |
| worldSnapshot/results/apply.py::SnapshotApplyResult | category, operation_id, request_fingerprint, committed, diagnostics. Existing COMMITTED/CONFLICT/REJECTED, не смешивать с неизвестным commit |
| worldSnapshot/results/apply.py::SnapshotCommitRefs | world_snapshot, player_snapshots, publication; committed identity только после подтверждённого commit |
| validation/diagnostics/fieldPathError.py::FieldPathError | Existing diagnostics в apply result. Проверить достаточность конкретных field/logic ошибок каждого публичного метода; не создавать зеркальные enums |

Для новых read/restore/branch/settings types выполнить отдельный field-by-field аудит на strict/frozen/extra-forbid, immutable вложения и отсутствие пересечения с таблицей. Никаких Any/dict payload и строковых универсальных errors. Scoped D1 metadata остаётся internal: MissingPersistedSnapshotBase, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue не становятся public errors автоматически. Сохранить исходные коды и порядок причин, не маскировать corruption как NOT_FOUND или обычный отказ.

Public error mapping — отдельный обязательный freeze: malformed input до effects; business refusal/CAS conflict; infrastructure corruption; busy; cancellation; unknown commit. Согласовать точные dataModel POJO и exception carriers с правилами ошибок проекта до кода. Повтор того же request не выполняет бизнес-эффекты повторно; mismatch fingerprint не replay. Конкретную policy terminal/retry этот план не переопределяет.

## 6. Классы, эффекты и пределы ответственности

| Класс / папка | Разрешённая ответственность/зависимости | Проверка; основание отказа |
|---|---|---|
| WorldSnapshotService / application/worldSnapshot/service | Одна публичная атомарная операция, typed request, checked registry и internal publication/history ports | Прямой DAG caller; отказ, если запускает чужой public pipeline или выбирает следующую междоменную операцию |
| SnapshotMetadataBuilder / та же папка | Pure построение metadata из pinned bases/receipts/assignments | Никакого IO/CAS/нового public DTO; отказ при скрытой загрузке latest или утрате diagnostics |
| AcceptedStateReader / та же папка | Exact scoped resolution metadata/state refs | Не public orchestration; отказ при latest fallback, repair либо чужом payload read |
| SectionRegistry/BoundSectionHandler / application/patch/registry | Exact registration/model/version и локальный dispatch принятого порядка | Не route planner; отказ при fallback, произвольном callback или вызове публичной операции другого домена |
| DomainSectionHandler / application/patch/contracts | Только отдельно согласованный internal section binding в общей transaction | Не пишет snapshot heads/history; каждый concrete handler проверяется отдельно до допуска |
| SnapshotEnvelopeCodec / application/worldSnapshot/encoding | Existing canonical envelope encoding | Не новый duplicate codec; стабильные vectors и version admission |
| SnapshotLifecycleLog / application/worldSnapshot/logging | Existing logging facade/typed events, correlation | Не отдельный logging pipeline; неверное объявление durable success блокирует приёмку |
| SqlitePublicationCommitStore / db/repositories/sqlite | Transaction owner, scoped capabilities и rollback/commit по existing contract | DAG/handlers не завершают UOW; unknown не становится success |
| SQLite history/world/player adapters / db/repositories/sqlite/snapshotCore | Append-only metadata и expected CAS | Нет public доступа из доменов; второй connection видит атомарный результат |
| SqliteArtifactHolders / db/repositories/sqlite/artifacts | Existing scoped handoff и общий live-set | Нет producer semantics/нового Pack owner; release только согласованных refs |
| Будущие DAG nodes / application/engine/nodes | Прямой публичный вызов и передача typed результата | Имена/классы согласует DAG; никакого scope/SQL/сборки section payload |

Перед implementation дополнить инвентарём всех реально задействованных классов и точными файлами adapters/composition. Таблица ролей не заменяет проверку вложенных вызовов. Источник времени, ID assignment, dependency resolution и retention destinations также должны получить конкретного владельца, не ambient callbacks.

## 7. Междоменные зависимости

### Граница текущего среза — решение пользователя

Дополнение пользователя: места фактического использования сохраняемого v1 обязательно помечать комментариями в коде. Маркер `SNAPSHOT-V1` должен назвать owning domain/contract, причину сохранения, ссылку на этот раздел и запрет адаптера. Пометка ставится возле конкретного вызова/registration, не только в плане. Она не означает wire version=1 и не утверждает готовность нового integration contract.

В текущем просмотренном Snapshot нет прямых generator calls или concrete production DomainSectionHandler subclasses в application. Поэтому поставлены `SNAPSHOT-V1-BOUNDARY` у generic dispatch в worldSnapshotService.py и у DomainSectionHandler в sectionHandler.py: это ограничения точки подключения, а не ложное обозначение ядра как v1. Decode дополнительно отмечен запретом read-upgrade отложенных доменов в этом срезе. Конкретные future v1 consumers должны получить отдельные локальные комментарии при inventory/подключении. Генераторы и DAG сейчас не менялись.

| Домены | Действие сейчас | Приёмка |
|---|---|---|
| Source, Pack, Cache | Уточнить необходимые Snapshot контракты по актуальным owning-планам: exact class/method, Input/Output/Error, поля mapping, authority/lifetime и effects | Согласовать только реально нужные зависимости; public операции только через DAG |
| Остальные, включая генераторы | Сохранить existing contracts как v1, явно перечислить их при inventory; не перепроектировать и не удалять | Не требовать их новой версии для приёмки текущего Source/Pack/Cache среза. Не утверждать готовность отложенной интеграции |

v1 здесь — статус сохраняемого контракта в плане, не команда изменить wire format_version, canonical IDs или schema. Для каждого отложенного домена inventory фиксирует ссылку на current owner contract и границу, остающуюся v1. Не создавать новые DTO, преобразователи, compatibility wrappers, dual-read или fallback. При отсутствии прямой совместимости нового Snapshot input с v1 отложить этот маршрут до будущего native contract владельца. Сохранение v1 не разрешает прямой domain→Snapshot вызов или запись и не отменяет DAG-only границу публичных методов.

Для Source/Pack/Cache сначала доказать необходимость: требуемые данные/операция → exact owner public/internal method → typed result fields → Snapshot input. Пока нет такого mapping, зависимость не включать автоматически. Публичные операции этих доменов DAG вызывает отдельно и передаёт результаты Snapshot. Internal bindings допустимы лишь в согласованной области и не дают права запускать public pipeline.

Остальные домены: только producer public result → DAG → Snapshot public input. Прямая запись в Snapshot и прямое чтение внутренних чужих stores запрещены. Artifacts/publication storage primitives инвентаризировать как внутреннюю реализацию Snapshot transaction, а не как исключение для любых внешних API. Если нужный primitive фактически является публичной операцией отдельного домена, требуется отдельный согласованный DAG маршрут.

Source/Pack/Cache нерешённые contracts не закрываются этим документом. При отсутствующем owner signature предъявить конкретные требуемые поля/операцию пользователю для согласования у владельца. Нельзя синтезировать новую ноду, mirror receipt или универсальный provider вместо отсутствующего контракта.

## 8. Этапы и gates — порядок обязателен

S3 static trace: [snapshot-public-apply-atomic-trace.md](snapshot-public-apply-atomic-trace.md). Зафиксированы existing separate refusal transaction и отсутствие implicit hold cleanup; предъявлены R1 retention destination/inheritance, R2 cancellation replay carrier, R3 core typed diagnostics. Полная готовность public apply из наличия signatures не следует. Read contracts могут приниматься отдельно; код по R1–R3 не менялся.

1. **S1 inventory:** read ТЗ/owning freeze, полные callers/routes, classes, POJO, настройки, зависимые contracts. Сопоставить existing implementation и новые запреты; конфликт показать до правки.
2. **S2 public contract:** заполнить строки §4, поля/errors §5, CRUD disposition и внутренние traces для уточняемых методов Snapshot. Из междоменных зависимостей прорабатывать только Source/Pack/Cache; остальные явно сохранить v1 по §7. Метод/маршрут, требующий ещё не согласованного нового контракта отложенного домена, пометить DEFERRED, а не блокировать им весь текущий срез. Принять уточнённые публичные методы с пользователем. Existing apply reuse предпочтителен, но не даёт автоматического PASS прочим операциям.
3. **S3 atomic trace:** для каждой операции определить transaction owner, validation/reads/writes/holds/CAS/terminal/commit, результат caller при отказе/отмене/unknown. Порядок apply дословно сверить с docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок» и owning-планом; не переставлять handlers, metadata, handoff и CAS на основании удобства wiring.
4. **S4 DAG agreement:** после принятия S2/S3 передать в чат DAG exact methods/POJO/errors и согласованный порядок/ветви. DAG определяет конкретные CRUD-ноды и result→input edges. Сейчас имён нод нет. Передача в чат — отдельное действие после приёмки контракта, не выполнено этим планом.
5. **S5 implementation plan:** отдельный принятый срез с конкретными файлами/тестами/командами. Перед кодом implement-plan skill. Без адаптеров совместимости и миграций; отложенные v1 сохраняются. Для переносимой операции сначала принятая замена вызова, затем удаление её обходного пути в том же cutover; не оставлять параллельный fallback и не удалять несвязанные v1 контракты.
6. **S6 verification/review:** независимое ревью contract/routes/atomicity и пользовательская приёмка. До этого не объявлять Snapshot полностью интегрированным.

## 9. Обязательное evidence

- Call graph: каждый public Snapshot/Source/Pack/Cache вызов идёт непосредственно из согласованной DAG-ноды. Нет domain→Snapshot, route→Snapshot, worker/callback обхода.
- Negative architecture checks: домены не импортируют Snapshot stores/commit scope для прямой записи; публичные DTO не раскрывают capability; DAG не импортирует metadata builder/SQL adapters.
- Strict POJO: malformed/mixed owner/wrong version, исходные field/logic codes, без old-form conversion.
- Два independent connections одной временной SQLite БД: partial writes rollback; world/player stale CAS; cancel после handoff; exact holds; committed refs только после COMMIT; unknown отдельно от refusal; replay без повторных effects.
- Read не меняет state/holds, не восстанавливает отсутствующую запись и не fallback-ится на latest. Restore/branch/delete/settings tests определяются только после semantics freeze.
- Адресные regression tests, typing и полный snapshotCore, с отдельным списком оставшихся падений и границами crash/GC evidence. Команды фиксируются implementation-срезом по актуальной конфигурации.

## 10. Приёмка текущего документа

Приёмка уточняемого среза Source/Pack/Cache отделена от приёмки всей интеграции Snapshot. Сохранённые v1 других доменов не являются долгом, который обязательно исправлять в этом срезе. Их список и отложенные маршруты должны быть явными; отсутствие нового контракта не закрывается адаптером. Полный domain acceptance по CRUD и полная DAG integration не заявляются частичной приёмкой.

Три запрета DAG закреплены в §1/3/7; роли/границы — §4–6; порядок и источник — §8; CRUD/settings — §4; dependency protocol — §7; POJO/error audit — §5. Сведения для полной приёмки ещё отсутствуют: concrete read/restore/branch/settings/error signatures, CRUD disposition, полный handler/caller inventory, mapping Source/Pack/Cache, DAG nodes. Поэтому текущий результат — отдельный план работ, **не PASS контрактов и не разрешение писать реализацию**.

В этом проходе прочитаны existing apply/service/context/reader/history/registry/DTO и правила DAG. Runtime tests не запускались. Проверка только документа: git diff --check -- .cursor/plans/snapshot-public-contracts-dag-integration.md. Чужие изменения, включая удалённый другим исполнителем план, не восстановлены и не изменены. Owning-план ядра не переписан.
