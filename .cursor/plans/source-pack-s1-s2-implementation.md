# Source PACK-S1/S2 — план реализации принятой дельты

**2026-11-21 — STOP старого adoption implementation:** действует [disposition S1/S2](source-s1-s2-adoption-disposition.md). Инструкции слоя B и старого composition C не исполнять: collect_for_adoption, adopt и SourceAdoptionPreflight отозваны как target. Старый порядок coverage→preflight→adopt исторический. Ранее открытый выбор разрешения Snapshot→Source уже решён отрицательно; повторно согласовывать исключение не требуется. Сохраняются pure Source algorithms, не acquisition. Замена — ранее выбранный вариант А через координатора, без новых локальных срезов.

2026-11-14. **DRAFT / NOT EXECUTION-READY:** контракт S1/S2 принят, runtime prerequisites отсутствуют. Этот план не разрешает код до закрытия gates и отдельной приёмки по обязательным правилам проекта. Применять implement-plan; не расширять работу автоматически до базовой реализации всего Source.

Уточнение ревью 2026-11-16: помимо runtime prerequisites открыты два design gates — INT-DAG-SCOPED (абсолютный запрет междоменных calls против Snapshot→Source scoped composition) и адресная SRP-дельта coverage/preflight/adopt из source-core-public-boundaries.md §4. Исторический ACCEPTED DESIGN не закрывает эти замечания. До решения и синхронизации нормативных документов не реализовывать старое размещение методов или proposed replacement; независимый срез invariants рассматривается отдельно.

## 1. Основания и граница

Семантика: source-proof-v2-contract-spec.md §6, §10–13; source-pack-s1-s2-contract.md, редакция 2 с открытыми design gates; акт source-pack-s1-s2-acceptance-2026-11-14.md. Единственный источник очереди — раздел «Действующий порядок: сначала архитектура целиком» world-source-versioning.md. Прежняя inventory→projector→history→finalize очередь не является альтернативным порядком ядра. Этот документ описывает зависимости S1/S2, не разрешает локальную поставку в обход целой архитектуры и последовательных шагов.

Перед кодом прочитать эти документы и применимые разделы доменных docs/tz_*.md, указанные основным планом, целиком в пределах их нормативных ссылок; сверить с текущими POJO/callers. Расхождение — остановка, не правка семантики на ходу. Нынешний проход создаёт документацию, runtime tests не запускались.

Scope Source: pure coverage input/selector/error applicability; read-only adoption preflight; composition regression checks. Не входит: реализация Pack reader/coordinator, Snapshot authority ledger/issuer/scoped ports, Source base proof/storage/finalizer с нуля, authored writer/bootstrap, Terrain/Regions, settings migrations, origin admission, DAG/API, SQL schema и legacy adaptation. Эти зависимости обозначаются как gates, не как задачи текущему агенту. Принятые междоменные internal declarations остаются контрактами зависимости.

## 2. Проверенная готовность и порядок prerequisites

G1 определён единственным образом в [owning-плане](source-g1-values-canonical-implementation.md): values + encoding + полная Source-owned pure composition. G1-BIND — внешние concrete adapters отдельно. G1 не закрыт; G1.1/G1.2 и A0→D существуют и приняты. S1 требует полного G1 и конкретного key-validation binding, если принятой coverage validation он необходим; пока exact binding и его необходимость не подтверждены, зависимость не считать закрытой и не заменять adapter заглушкой. Это отдельный consumer gate, не расширение значения G1. S2 дополнительно требует своих read/format/retention bindings G2.

Соответствие основной очереди: G1 — шаги 1–4 (модель/encoding/validation/proof algorithms); G2-read и настоящий finalizer для G2-fixtures — шаги 6–7 (history/read/capture/closure); G3 — отдельная consumer integration после соответствующих возможностей ядра и архитектурного согласования. Операционный порядок coverage→preflight→adopt остаётся прежним; A→B→C здесь задаёт зависимости приёмки, а не разрешение перескочить основной шаг.

Проверка filesystem 2026-11-14: backend/app/dataModel/sourceVersioning и backend/app/application/worldData/sourceVersioning отсутствуют. Поэтому ни SourceProofReadInput/SourceDurableProof/SourceFailure, ни selector/collector/retention binding не доступны как runtime imports. Совпадающие слова Source в существующих Geo1/Pack тестах не доказывают наличие этих контрактов.

| Gate | Что должно быть реально поставлено | Проверка / влияние |
|---|---|---|
| G1: Source base values/pure | Полный G1.1/G1.2/G1.3 по owning-плану, включая immutable descriptor values и pure port contracts; внешняя concrete registration учитывается отдельно | Точные accepted imports и независимая приёмка полного G1; блокирует S1/S2, но сам по себе не закрывает consumer-specific bindings |
| G2-read: Source durable read/adopt | Existing-design SourceProofClosureCollector, accepted read bindings/formats/committed witness verification, §12.1 adoption и реальные hold checks | Exact/historical/full closure и missing/corrupt/hold tests на реальном storage; блокирует S2. Не заменять fake success collector |
| G2-fixtures: новые Source-owned finalized fixtures | Созданная заново тестовая подготовка по строгим Source-контрактам через настоящий SourceCaptureFinalizer, его storage bindings и подтверждённый commit; необходимые внешние данные — по актуальным контрактам владельцев | Проверенные witness/seal/holds и воспроизводимое получение capture без старой формы, прямой подстановки finalized row или fabricated authority. Блокирует B; старые fixtures gate не закрывают |
| G3: scoped consumer composition | Snapshot/Artifacts реализуют принятые scoped readers/private evidence и outer rollback boundary; Pack реализует verified all-provenance reader | No nested UOW/bind/guard, exact request/target evidence, typed pin/manifest refusal, rollback/unknown tests; блокирует integration acceptance, но не pure S1 |
| G4: production origin capability | Отдельно принятый и реализованный trusted acquisition/origin path | Полный production operation-origin путь не принимается без него. Проектирование G4 не разрешено этим планом |

Утверждённый пользователем порядок поставки (2026-11-14): G1 → реализация и приёмка слоя A (S1); принятый A + G2 → реализация и приёмка слоя B (S2); принятые A и B + G3 → слой C (совместные integration checks). Здесь и далее G2 закрыт только при закрытых G2-read и G2-fixtures. G1 остаётся обязательной предпосылкой B через принятый A. Production wiring дополнительно требует G4 и отдельного разрешения соответствующего public/DAG среза. Production prerequisites G2, включая настоящий finalizer и его storage bindings, поставляются по общему порядку Source (storage/history до finalize/integration), а не создаются внутри этого плана. Отсутствующий authored writer не восполнять автоматическим расширением G2.

**Решение по fixtures (2026-11-14):** новые Source-owned fixtures создаёт Source в backend/tests/sourceVersioning/support/finalizedFixtures.py после приёмки A и готовности production prerequisites G2. Это отдельная тестовая подготовка до начала B, не реализация отсутствующего finalizer/storage. Входные records задаются заново по новым строгим контрактам; запрещены преобразование старых fixtures, compatibility adapters, dual-read, inference отсутствующих полей и fallback. Существующие fixtures не считаются совместимыми по имени или наличию файла.

Если fixture требует payload/codec/manifest другого домена, его актуальный контракт и необходимые тестовые данные подтверждает владелец. До реализации fixture зафиксировать конкретные внешние типы, импорты, версии и источник подтверждения; до получения необходимых данных соответствующий gate остаётся открытым. Не мигрировать чужие fixtures и не объявлять stub нового доменного контракта. Generic Artifact infrastructure допустимо переиспользовать после проверки соответствия принятому контракту; это не разрешение адаптации старой формы данных.

Зависимость начала B от приёмки A — ограничение порядка поставки, не вызов между методами: collect_for_adoption не вызывает check_coverage. Технические зависимости preflight — G1/G2. Порядок исполнения общей операции coverage → preflight → adopt сохраняется отдельно; он не разрешает параллельную разработку A/B вопреки утверждённой последовательности.

Таким образом, изолированная поставка S1 логически возможна после базовых pure contracts G1; прямо сейчас она не исполнима. S2 и end-to-end composition требуют дополнительных перечисленных runtime зависимостей. Принятие design этих зависимостей не равно закрытию gate.

## 3. Слой A — Source logical coverage

Входные gates: G1 закрыт конкретной реализацией и evidence; приняты адресная SRP-дельта S1 и текущая ревизия этого плана. Ниже целевые paths предложения (относительно backend/app), не разрешение кода. Прежний proof/selector.py::SourceProofSelector.check_coverage — историческое размещение редакции 2, не исполняемая инструкция.

- application/worldData/sourceVersioning/proof/coverageCheckInput.py — новый internal named concrete BaseModel с двумя существующими Source fields; exact module/qualname diagnostic root.
- application/worldData/sourceVersioning/proof/coverageChecker.py — предлагаемый SourceProofCoverageChecker.check_coverage с прежним input/result/semantics единой редакции §2. Exact import входит в принимаемую SRP-дельту. Переиспользовать existing validators/canonical enumeration; не создавать второй engine или forwarding selector.
- dataModel/sourceVersioning/sourceErrors.py — existing CHECK_COVERAGE из полного G1 error roster и его applicability; не добавлять значение повторно и не создавать enum-дубли.

Сначала контракт input/operation/diagnostic root, затем complete pure implementation и прямой internal caller contract. Никаких публичных endpoint/DAG/Pack import. Если existing pure helper нуждается в изменении вне этих путей, назвать exact path/роль и согласовать изменение плана до записи; не создавать новый helper по догадке.

Responsibility: input хранит relation/diagnostic context без IO; coverage checker валидирует и сравнивает exact atoms без authority; sourceErrors задаёт единые typed diagnostics без policy. Refusal criteria — violation strict/canonical/world/conflict/subset; infrastructure к pure алгоритму не подключается. Public values не дублируются. Independent field errors агрегировать штатным ValidatorAggregationHelper; typed paths FieldRef/CheckedPath. Root invalid input не фабриковать пустым path.

Тестовый файл: backend/tests/sourceVersioning/test_coverage.py (новый после G1). Cases: multi-capture historical coverage; same-capture revision conflict; same closure/extra atom; foreign empty world; empty/empty и nonempty/empty; repeated valid available proof; inner duplicates/noncanonical; several independent diagnostics с исходными indexes/paths; неизменность входов. Проверить отсутствие storage calls, сравнивать с literal expected atoms/results, не копировать implementation в tests.

Выход: точный import/method/error semantics и regression cases проходят; layer A не заявляет durable/production готовность. Если cold diagnostic restore уже применяется к этим failures, owning transport должен зарегистрировать root до приёмки этого пути; не добавлять proof type ID и не расширять transport самостоятельно.

## 4. Слой B — Source preflight

Входные gates: G1/G2 закрыты, A принят; приняты адресная SRP-дельта S2, exact constructor/scoped lifetime и текущая ревизия этого плана. Предлагаемый production path: application/worldData/sourceVersioning/capture/adoptionPreflight.py, SourceAdoptionPreflight.collect_for_adoption. Exact import входит в принимаемую дельту. Использовать уже поставленный collector и существующий artifact bind. Прежнее добавление collect_for_adoption в capture/retentionBinding.py — историческое размещение редакции 2, не исполняемая инструкция. SourceCaptureRetentionBinding.adopt остаётся владельцем acquire и повторной проверки; signature/error/result не ослаблять. У preflight нет собственного UOW/commit/holder acquisition или origin lookup. INT-DAG-SCOPED остаётся отдельным gate интеграции.

Responsibility preflight — проверить capability/unbound, один lexical bind, передать read facet и ADOPT_CLOSURE collector, гарантировать reset. Collector сохраняет own read/closure ответственность. Foreign/task/revoked/read-only/already-bound scope — infrastructure refusal до IO, SourceFailure возвращается без writes. Body errors/closure semantics переиспользуются, не переписываются.

Тестовый файл: backend/tests/sourceVersioning/test_retention_preflight.py. Использовать новые Source-owned fixtures из support/finalizedFixtures.py, принятые в G2-fixtures: exact result/closure, no acquired/released/appended events именно во время preflight (setup finalization имеет собственные предусмотренные writes), sequential preflight→adopt в одном scope, nested binding rejection, foreign DB/task/read-only/revoked scope, cleanup on SourceFailure/exception/cancellation, повторные adopt checks при изменённом own transaction hold. Не использовать fabricated proof authority/placeholder collector или адаптацию старых fixtures вместо G2.

Выход: preflight корректен, accepted adoption regression tests проходят, call trace соответствует §13. Слой B не подключает Snapshot issuer/finalizer и не завершает READY.

## 5. Слой C — совместная проверка composition

Входные gates: A и B реализованы и приняты, G3 закрыт. Только integration tests, без самостоятельной реализации чужих production adapters. Предлагаемый тестовый файл backend/tests/sourceVersioning/test_scoped_composition.py; Source fixtures переиспользовать из принятого G2-fixtures. Необходимые fixtures Pack/Snapshot/Artifacts получать от владельцев по актуальным контрактам G3; их exact paths и подтверждённые версии зафиксировать в плане перед кодом. Старые fixtures не адаптировать. Пока зависимости не поставлены, этот слой не execution-ready.

Trace строго: owner writer/target/replay → verified origins/manifest → S1 → S2 bind/reset → scoped register/resolve → unchanged adopt bind/collect/check/acquire/reset → READY/commit. Проверить две SQLite connections, GC/pin-close serialization, late failure второго proof с rollback первого, exact evidence task/DB/request/target/lifetime, restart PREPARING, READY replay, read union → PackPreparationReadAbort внутри → catch после confirmed rollback/revoke, unknown outcome precedence. Не подменять проверку полного порядка одними mocked method counts.

Один failure любого слоя прекращает зависимую ветвь; independent validation остаётся агрегированной. При отсутствии lawful origin test fixture отметить gate open, не fabricate holder/grant и не расширять на G4. Public/DAG route не тестируется как будто согласован; отдельная приёмка остаётся открытой.

### C-PIN-1 — сценарий для уточнения у Pack/Snapshot

**Итоговое ревью узкой pinned редакции 2:** [независимый акт 2026-11-14](source-pinned-origin-final-review-2026-11-14.md) — PASS для first-call/explicit retained-input repeat; три design findings закрыты. Приведённые ниже записи об ожидании итогового ревью — история. Полный C-PIN-1, SQL/codec, G1/G2/G3 и runtime gates остаются OPEN; статус этого implementation-плана NOT EXECUTION-READY не меняется.

**Текущая фиксация 2026-11-14:** snapshot-pinned-origin-contract-r1.md содержит исправленную редакцию 2; §9 фиксирует пользовательское согласие на один полный pinned origin и durable historical admission provenance. Ниже сохранена история запроса; прежние OPEN по выбору этих двух вариантов заменены решением §9, но не общим runtime PASS. Итоговое ревью узкого design-среза ещё требуется.

Для сценариев C действует ограничение: один manifest покрывает весь logical request и полный Source closure; ровно один grant на register. Частичные origins не объединяются, fallback/dedup с выбором другого pin отсутствуют. Повтор того же request с другим pin/manifest — IMMUTABLE_BINDING_CONFLICT с rollback всей preparation, включая empty proof. Binding хранит один origin и ordered sources; generic Source adopt и его способность принимать exact пары разных holders не сужаются — ограничение относится к pinned issuer этого среза.

Durable binding сохраняется как история проверенного admission в existing preparation ledger, атомарно с READY. После commit runtime consumer здесь отсутствует; READY/retry её не требуют. Это согласованная цена хранения истории, не recovery mechanism, не новый audit API и не промежуточный PREPARING commit. Ledger matrix обязана проверять identical append/no-op, смену origin/conflict, digest collision/full canonical equality, corrupt bytes/checksum и fence mismatch/no mutation.

Различать два результата приёмки: first-call/explicit repeat с полным исходным input может быть принят отдельно; весь C-PIN-1, включая автономный crash restart, остаётся OPEN без подтверждённого producer полного target/request/pin input. SQL layout/canonical registrations, G1/G2/G3, новые strict fixtures и runtime/typing/race tests также остаются открытыми. Эти решения не разрешают код и не меняют порядок A → B → C.

2026-11-14, по указанию пользователя. Статус: REQUESTED, не дополнительный принятый admission-протокол. Проверить, покрывает ли уже принятый G3 законный pinned-manifest origin для всего C, включая restart, либо имеется конкретная недостающая admission-зависимость. Существующие restart-контракты, включая DAG, сначала сверить и переиспользовать; новый протокол из самого вопроса не выводить.

Исходный сценарий: новый строгий manifest с Source provenance, существующий законно полученный OPEN pin и удерживаемый child closure; target preparation получает proof именно этого manifest. Owning fixtures создаются на актуальных контрактах, без legacy conversion и без ручной подстановки grant/authority. Путь C: exact pin/manifest read → coverage → fresh preflight → register/resolve → adopt → READY/commit.

Владельцы должны подтвердить применимость существующих контрактов отдельно к следующим исходам:

1. Первый запуск с OPEN pin: кто и каким принятым методом доказывает acquisition context, что именно сохранено и связано с execution/invocation/logical key/world/pin/manifest.
2. PREPARING restart после rollback: откуда восстанавливается допустимый origin input; runtime grant/private evidence не сериализуются и не оживают. Если допускается ранее committed registration, назвать её принятую transaction boundary; иначе указать повторный законный acquisition/check path без нового protocol proposal.
3. PREPARING при закрытом pin, утрате hold или чужом binding: typed refusal, без выбора нового origin/latest и без partial success.
4. READY replay, включая закрытый прежний pin: exact committed candidate и target holds; old origin не требуется по принятому S1/S2. Назвать связь с DAG terminal/nonterminal replay и границей закрытия pins, не смешивать execution status с preparation phase.
5. Late refusal второго proof, concurrent pin close/GC и lost commit acknowledgement: rollback всех provisional effects либо existing unknown-outcome recovery, не выдача refusal вместо unknown. Указать, какие из этих проверок покрываются pinned-only fixtures и какие требуют отдельной зависимости.

Evidence для сверки: source-pack-s1-s2-contract.md §4–5; pack-preparation-source-authority-contract.md §9–12; pack-pin-identity-mapping.md; spatial-dag-execution-finality.md и действующие engine ExecutionStore/checkpoint/ExecutionPins contracts. Исторические предложения в этих документах сами по себе не означают accepted/current runtime. dag-pack-source-binding-response-2026-11-14.md явно отзывает прежние proposals upper bindings/continuation: ими нельзя доказывать готовность C или назначать новые ноды.

Форма ответа Pack/Snapshot: exact file/section/class/method и статус (accepted design / implemented / proposed) для каждого сценария; минимальные новые fixtures и их owner; достаточно ли G3 без G4. Если есть gap — назвать отсутствующий контракт и его владельца, остановиться до проектирования за рамками C. До ответа C-PIN-1 OPEN; отсутствие нового admission не объявляется ни доказанным, ни опровергнутым. Сценарий не принимает публичные DAG bindings и не меняет ноды.

**Результат уточнения и разрешённый следующий срез (2026-11-14):** Pack подтвердил применимость existing pins/restart, но оставил lawful registration на подтверждение Snapshot. Snapshot в snapshot-c-pin-1-applicability-audit.md предъявил documentary gap: issue_pinned_manifest, полный PreparationSourceBinding и repeat issuance после rollback остаются proposal. Source проверил документы и отдельного acceptance anchor не нашёл. G3 не считается достаточным для всего C.

Пользователь согласовал следующий узкий design/review-срез: предъявить и проверить существующий pinned-origin proposal для первого запуска и повторного запуска после подтверждённого rollback. Owner — Snapshot; Pack подтверждает authenticated pin boundary. Зафиксировать exact issuer/grant/binding/ошибки, восстановимый исходный input, lifetime/revocation и место выдачи нового grant в принятом transaction trace. Не восстанавливать старый runtime grant из checkpoint. READY replay и unknown-outcome правила сохраняются; промежуточный commit регистрации не добавляется молча.

Разрешение относится к конкретизации и приёмке pinned части, не означает её ACCEPTED и не разрешает runtime-код. Operation-origin G4, Source finalizer hookup, новый DAG restart-протокол, ноды и legacy adaptation исключены. При необходимости выйти за эти рамки — остановка с конкретной зависимостью. C-PIN-1 остаётся OPEN до совместной приёмки предъявленной pinned редакции; runtime gates сохраняются отдельно.

## 6. Команды и обязательная приёмка

После появления тестов из backend: python -m unittest discover -s tests/sourceVersioning -p "test_*.py". Дополнительно запускать существующие G1/G2 и Snapshot artifact/transaction регрессии по фактическому набору изменённых зависимостей, перечень закрепить при снятии gates. Существующие примеры: tests/planning/encoding/test_canonical_codec.py, tests/snapshotCore/storage/artifacts/test_gc.py, tests/snapshotCore/storage/publication/test_atomicity.py. Не объявлять эти тесты выполненными по наличию файлов. Проверить repository typing/lint штатными командами проекта, найденными при preflight; не выдумывать конфигурацию. Backend/server не запускать.

| Обязательный критерий | Решение / gate |
|---|---|
| Три запрета DAG | Нет branching/hidden orchestration/public cross-domain calls в A/B; C проверяет принятую atomic internal composition. Public DAG не вводится |
| Каждый класс, deps/effects/refusal | Роли A/B выше; полный foreign dependency trace единой редакции §4–5. Отсутствие runtime G1/G2/G3 запрещает execution acceptance |
| Public/internal | Только internal input/check/preflight. Existing public POJO reused, нет Pack mirrors; public imports не считаются реализованными |
| Утверждённый порядок | G1 → реализация/приёмка A; принятый A + G2 → реализация/приёмка B; принятые A/B + G3 → C. Зависимость B от A — порядок поставки, не вызов coverage из preflight. Общий Source порядок и runtime transaction порядок неизменны |
| Data C/R/U/D | C/U/D public не добавляются; R public не меняется, internal preflight read-only. Target acquire остаётся existing accepted adopt |
| Settings C/R/U/D | Все четыре операции вне дельты; immutable schema/descriptor dependencies, mutable settings lookup запрещён |
| Междоменные contracts | Accepted S1/S2 r2, exact ports/carriers; G3 runtime evidence отсутствует, G4 явно отдельно. Не придумывать публичный путь |
| POJO/field/logic errors | Exact named relation input; existing SourceFailure/ManifestReadRefusal; один proposed Snapshot rollback carrier; no duplicate types/codes, diagnostic root отдельный от persisted schema |

**Текущий verdict плана: NOT EXECUTION-READY, G1/G2/G3 OPEN.** Это конкретные недостающие зависимости, не новое замечание к принятому S1/S2 design. Нельзя начать «маленький» skeleton, placeholder, mirror DTO или адаптацию старой формы. Перед снятием gates обновить evidence, exact prerequisite implementation refs/test fixtures, проверить отсутствие contract drift и повторно принять план. При выходе за перечисленный scope остановиться и предъявить зависимость пользователю.

Ручные edits только apply_patch; перед отчётом реализации обязательно показать diff. Не commit/push, не менять DAG, не создавать SQL migration, не запускать сервер. При первой реализации применить implement-plan и прочитать все его требования заново.
