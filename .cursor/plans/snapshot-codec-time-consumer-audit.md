# Time — аудит потребления Snapshot codec

2026-11-14. Документальный аудит по запросу владельца Snapshot. R1 остаётся НА СОГЛАСОВАНИИ. Код, canonical IDs, версии и T5 не изменялись. Этот аудит не является приёмкой реализации R1 или доказательством эксплуатации.

## Реальные зависимости

Все пути ниже относительно корня репозитория.

1. `backend/app/application/time/composition/factory.py`, `make_time_reader(source: ITimeReadSource | SqlitePublicationCommitStore)` при передаче SQLite coordinator создаёт `SqliteSnapshotHistoryStore`, `AcceptedStateReader`, `SnapshotTimeReadSource` и `SqliteTimeStateReader`. При передаче готового source возвращает `TimeReader(source)`.
2. `backend/app/application/time/reads/snapshotSource.py`: current сравнивает expected с фактической публикацией в одном read scope; pinned разрешает exact publication; historical разрешает exact snapshot. Все payload reads используют тот же scope.
3. `backend/app/application/worldSnapshot/service/acceptedStateReader.py`: `resolve_publication` проверяет exact publication и gameplay_started. Head своей timeline разрешается через `resolve_snapshot`; отсутствие head либо inherited head другой timeline возвращает publication для чтения отдельного binding. `resolve_snapshot` читает metadata и непосредственно перебирает **metadata.state_refs**, выбирает section_key и проверяет world/timeline владельца. Это непосредственная точка зависимости от заменяемого R1 layout.
4. `backend/app/db/repositories/sqlite/snapshotCore/history/snapshotHistoryStore.py` и `history/rowProjection.py`: read декодирует immutable metadata через `SnapshotEnvelopeCodec`, проверяет checksum, ref, row/body projection, operation owner/kind и parent. Time получает адрес состояния после этих проверок.
5. `backend/app/application/worldSnapshot/encoding/snapshotCodec.py`: поддерживается envelope version 1, manifest объединяется с SNAPSHOT_CORE_SCHEMA; допускаются только World/Player metadata. Это codec metadata. Clock payload читается отдельно из JSON в `backend/app/db/repositories/sqlite/timeStateReader.py` с exact ref/binding проверкой.

Поиск `make_time_reader` по backend выявил callers в `backend/tests/time/test_time_core.py` и `backend/tests/time/test_snapshot_read_source.py`; production wiring вызова фабрики не найден. Реальная реализация адаптера существует, факт runtime activation из этого не следует.

`StoredTerminalCodec` не входит в Time read path. Его использует `SqliteOperationStore`; history read проверяет строку publication_operations, но не декодирует terminal outcome. Прямых обращений к StoredTerminalCodec/receipt/flat retention в просмотренных Time application/dataModel и worldData/timeSettings не найдено. Тестовый publish helper и Snapshot fixtures используют receipt/operation storage косвенно.

## Гарантии, которые необходимо сохранить

- current — exact expected publication, конфликт при изменившейся публикации; pinned — exact сохранённая публикация; historical — exact snapshot, без подстановки latest.
- Clock ref может принадлежать предку той же world/timeline. При наследовании Time читает payload владельца ref, а не требует нового payload на каждом child snapshot.
- Для ветки с inherited head другой timeline читается publication binding этой ветки. В соответствующем тесте часть publication/history ports замокана; это не доказательство полного branch lifecycle.
- `SqliteTimeStateReader.read_section` принимает только CLOCK_SECTION и CLOCK_FORMAT=1, проверяет точное равенство payload.ref запрошенному ref. StoredTimeState проверяет world/timeline точки; PublicationTimeState проверяет coherence publication/point.
- Отсутствующий snapshot возвращает SNAPSHOT_MISSING, неразрешённая секция/payload или неподдерживаемый clock format — SOURCE_UNRESOLVED. Повреждённые metadata/payload/identity приводят к infrastructure error, а не к default времени.

## Evidence и пределы

`backend/tests/time/test_snapshot_read_source.py` содержит проверки current/pinned/historical, inherited section, второй SQLite connection, immutable payload triggers, missing/unsupported clock и corrupt head. `backend/tests/snapshotCore/storage/publication/test_accepted_state_reader.py`, `test_history.py` и `backend/tests/snapshotCore/contracts/test_codec.py` покрывают смежные readers/history/codec.

Это тестовые данные: `backend/tests/snapshotCore/support/fixtures.py:live_database` создаёт TemporaryDirectory и seeded SQLite; Time тесты вставляют PublicationTimeState/StoredTimeState вручную, publish выполняет тестовый helper. Тесты в этом аудите прочитаны, но заново не запускались. Эксплуатационные БД, выгрузки bytes и журналы запуска не исследовались. Доказательств существования исторических production envelopes, требующих dual decode/миграции, аудит не предъявляет. Отсутствие таких доказательств также не доказывает отсутствие данных.

Проверены git status, последние коммиты затронутой Time области (`bda52ad2`, `29b29aec`, `e32b331b`), реализации и callers поиском rg. Чужие изменения сохранены.

## Минимальное влияние принятия R1

1. В Snapshot-owned `AcceptedStateReader.resolve_snapshot` заменить обход flat state_refs на обход proposed typed states с извлечением exact SectionStateRef. Сохранить world/timeline checks и возможность ссылки на предка. Time по-прежнему получает SectionStateRef; retention closure остаётся ответственностью Snapshot.
2. Snapshot обновляет metadata/receipt модели, manifest и history projection/validation по отдельно принятому формату. Фабрика Time и SnapshotTimeReadSource не требуют изменения при сохранении сигнатур и семантики AcceptedStateReader/history store.
3. Адаптировать fixtures/helper publish и assertions к новому metadata/receipt layout. Повторно проверить перечисленные Time read scenarios, включая inherited ref с сохранённым retention closure и отказ при недоступном payload. Само наличие retention record не удостоверяет наличие clock bytes.
4. Нет обоснования менять TimeCapture, HistoricalTimeCapture, TimePoint, TimeInterval, TimeAdvanceProposal, TimeClockState, CLOCK_FORMAT или JSON clock payload из-за изменения metadata retention. Envelope format, terminal format и clock section format — разные контракты.
5. Требования Time не обосновывают обязательную version 2 или перенумерацию canonical IDs. Изменение layout меняет canonical bytes; выбор стратегии требует отдельного решения Snapshot после инвентаризации реально поддерживаемых старых данных. Если такие данные должны читаться, нужен явно согласованный механизм совместимости; молчаливое чтение несовместимого layout недопустимо.

T5, новые writers, DAG wiring, runtime activation и temporal observation proposals этим аудитом не реализуются и не принимаются.
