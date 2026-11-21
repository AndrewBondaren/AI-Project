# C2: отдельная проверка противоречий

**Исправления повторного ревью 2026-11-21 предъявлены:** [R3/R4/R5 facts/diagnostics](snapshot-receipt-facts-diagnostics.md). Устранены ошибочный общий no-op history запрет в ТЗ, fully-valid-only input boundary, неявный owner-order diagnostics и отсутствие signature operation predicate. Added section_index в proposed input-association issues, FOREIGN_OPERATION не подавляется. Статус — исправленный PROPOSED, не автоматический PASS: независимая документальная сверка нового internal facts contract и evidence реализации впереди. Старые OPEN ниже объясняют происхождение замечаний, не отсутствие нынешнего предложения.

2026-11-19. Scope: [детализация C2](snapshot-receipt-validation-c2.md), принятый section-codec-receipt-contract.md, Snapshot owning plan, docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок» и фактические service/builder/provenance/receipt declarations. Проверка документов и кода чтением; тесты не запускались, runtime не менялся.

**Итог: C2 architecture ACCEPTED; детальный implementation contract OPEN, готовность к реализации не подтверждена.** Ниже конкретные пробелы, не повторная приёмка C1/ядра PatchSet.

## C2-R1: источник и фаза bases — вариант А ACCEPTED

План §4 требует bases до early receipt validation, но existing WorldSnapshotService._append_metadata читает их после всех handler.apply. ТЗ §§5–7 фиксирует validation → apply → metadata, а current missing-base diagnostics агрегируются с builder issues (owning план, scoped D1 metadata). Перенос чтения раньше может изменить набор уже выполненных handlers и доступных diagnostics при missing/corrupt base.

**Решение пользователя 2026-11-19: «Ок, давай А».** WorldSnapshotService читает все exact pinned bases после всех успешных handler.validate, до первого handler.apply, в той же transaction, один раз с reuse для receipt validation и metadata. None head пропускается; пустой sections не отменяет необходимое наследование базы. Missing/corrupt base останавливает путь до apply как infrastructure fault; потенциальные apply/receipt ошибки уже не вычисляются. Это явное согласованное изменение фазы отказа, не механическая миграция ошибок. R1 закрыт в этой области; signature/wiring, diagnostic details и evidence остаются C2-G1/R3/R5, синхронизация ТЗ — G4.

## C2-R2: индекс receipt — explicit section_index ACCEPTED

План §2: collect_receipt_provenance принимает receipt_index, а SnapshotReceiptValidator.validate принимает только section/receipt/context/bases. Existing SnapshotMetadataFieldIssue.destination и relation address привязаны к original receipt index. Из этих аргументов нельзя надёжно получить индекс среди секций/receipts.

**Решение пользователя 2026-11-19 («Ок»):** передавать keyword-only section_index из enumerate исходных sections в validate и далее в helper. Строгий int >= 0, bool запрещён; никакого поиска по равенству, len(accumulator) или constant 0. В последовательном пути индекс соответствует receipts[i]. Public DTO не расширяются. Предложенные signatures исправлены в плане §2; прежнее описание выше — основание замечания. R2 закрыт по источнику/передаче индекса, exact упаковка адресов diagnostics остаётся R3/R5.

## C2-R3: агрегирование malformed receipt ещё не замкнуто — OPEN

Existing builder при ValidationError сохраняет доступные независимые поля и продолжает проверки; proposed helper принимает полностью валидный SectionApplyReceipt. План требует aggregation независимых причин, но не определяет способ передачи частично доступных фактов без unchecked trust и дублирования predicates. Root mismatch также не имеет окончательного carrier.

Gate C2-G2/G3: определить structural admission/доступные проверки и точный typed путь для wrong root. Existing collector принимать только перечисленные concrete types. Нельзя ловить любой TypeError/ValueError как invalid receipt, применять зависимый predicate к повреждённому полю или молча перейти к first-error semantics.

## C2-R4: две provenance-границы требуют exact extraction map — OPEN

2026-11-21: [предложение extraction](snapshot-provenance-extraction-r4.md) задаёт общий owner-local helper(receipt,assigned,base,section_index), пригодный early и final callers без fake apply context. Карта правил и границы global/final checks предъявлены. R4 остаётся PROPOSED до разбора R3 malformed aggregation и R5 carriers/order. Source review выявил ошибку Lifecycle proposal: inherited history в receipt запрещён существующим contract; owning atomic-boundary документ исправлен на history=() при exact no-op.

Existing validate_receipt_provenance получает один metadata/base и полный tuple receipts; proposed collect_receipt_provenance получает apply context и все bases. Первому недостаёт полного context/assigned targets, поэтому прямое переиспользование нового helper не следует из одной ссылки. План запрещает копии predicates, но exact общая pure input boundary ещё не задана.

Требуется сопоставление каждого условия: early receipt association/membership, assigned target/inheritance, итоговое envelope coverage. Проверка history store append не должна потерять fail-closed guarantees и не должна требовать вызова service/application pipeline. Самостоятельные итоговые predicates остаются; пересекающиеся используют единый источник правил.

## C2-R5: совместимость diagnostics и этапов — OPEN

План §3 предлагает не выдавать FOREIGN_OPERATION поверх membership fault; это меняет ранее установленный набор diagnostics. Не объявлять это неавторизованным изменением C2-поведения вообще: C2 является новым принятым contract gate, но точная дельта existing D1 diagnostics не описана. Отдельно зафиксировать existing metadata path и новый early path, порядок сообщений, ownership, отсутствие потерянных независимых причин и допустимые различия. Нельзя автоматически заменить golden diagnostics.

## Что подтверждено

- PASS: changed membership сравнивает полный PatchRef; subset допускается; Time rules не входят в общий validator.
- PASS: invalid receipt не превращается в business refusal; unknown rollback имеет приоритет.
- PASS: нет нового DAG entry, foreign public call, собственного transaction owner или C1 implementation в C2.
- PASS: новые input-association причины имеют отличную от metadata-envelope проверок ответственность; reuse existing POJO указан. Полный POJO/error PASS невозможен до R2/R3/R5.
- OPEN: полный class/method acceptance implementation-плана до закрытия R1–R5; наличие gate не равно его выполнению.

R1 разобран: вариант А принят. R2 разобран: явный section_index принят. Следующий разбор — R4 (единые provenance predicates), затем R3/R5 (diagnostics/aggregation/transport). Это порядок проектирования; принятая runtime-дельта А описана отдельно. После решений сверить ТЗ и выполнить повторную документальную приёмку до кода.
