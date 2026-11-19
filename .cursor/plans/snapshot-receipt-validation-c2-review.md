# C2: отдельная проверка противоречий

2026-11-19. Scope: [детализация C2](snapshot-receipt-validation-c2.md), принятый section-codec-receipt-contract.md, Snapshot owning plan, docs/tz_world_snapshot.md §«Snapshot.apply, результаты и порядок проверок» и фактические service/builder/provenance/receipt declarations. Проверка документов и кода чтением; тесты не запускались, runtime не менялся.

**Итог: C2 architecture ACCEPTED; детальный implementation contract OPEN, готовность к реализации не подтверждена.** Ниже конкретные пробелы, не повторная приёмка C1/ядра PatchSet.

## C2-R1: источник и фаза bases — OPEN

План §4 требует bases до early receipt validation, но existing WorldSnapshotService._append_metadata читает их после всех handler.apply. ТЗ §§5–7 фиксирует validation → apply → metadata, а current missing-base diagnostics агрегируются с builder issues (owning план, scoped D1 metadata). Перенос чтения раньше может изменить набор уже выполненных handlers и доступных diagnostics при missing/corrupt base.

Это не доказанное противоречие самому C2: C2 явно требует ранний отказ на invalid receipt. Но сохранение старого порядка без уточнения reads не доказано. Gate C2-G1 обязателен: точная позиция чтения, MissingPersistedSnapshotBase semantics, signature delta и исход при одновременно missing base/invalid receipt. Не выдавать перенос за механический error refactor; не менять ТЗ автоматически.

## C2-R2: индекс receipt не проходит через proposed validator — OPEN

План §2: collect_receipt_provenance принимает receipt_index, а SnapshotReceiptValidator.validate принимает только section/receipt/context/bases. Existing SnapshotMetadataFieldIssue.destination и relation address привязаны к original receipt index. Из этих аргументов нельзя надёжно получить индекс среди секций/receipts.

До кода выбрать явный внутренний параметр индекса либо согласованный иной адрес. Не искать индекс по равенству объектов, не ставить 0 для всех receipts и не терять адрес при revalidation. Это внутренняя signature delta, не новая публичная DTO.

## C2-R3: агрегирование malformed receipt ещё не замкнуто — OPEN

Existing builder при ValidationError сохраняет доступные независимые поля и продолжает проверки; proposed helper принимает полностью валидный SectionApplyReceipt. План требует aggregation независимых причин, но не определяет способ передачи частично доступных фактов без unchecked trust и дублирования predicates. Root mismatch также не имеет окончательного carrier.

Gate C2-G2/G3: определить structural admission/доступные проверки и точный typed путь для wrong root. Existing collector принимать только перечисленные concrete types. Нельзя ловить любой TypeError/ValueError как invalid receipt, применять зависимый predicate к повреждённому полю или молча перейти к first-error semantics.

## C2-R4: две provenance-границы требуют exact extraction map — OPEN

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

Порядок следующего разбора: R1 (доступность базы и trace) → R2/R4 (внутренние входы и единые predicates) → R3/R5 (diagnostics/aggregation/transport). Это порядок проектирования, не перестановка runtime. После решений обновить детализацию C2, сверить ТЗ и выполнить повторную документальную приёмку до кода.
