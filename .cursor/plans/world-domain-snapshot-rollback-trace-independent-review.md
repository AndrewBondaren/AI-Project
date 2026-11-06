# Независимое ревью rollback trace — PASS

2026-11-06. Проверено текущее рабочее дерево, включая незакоммиченные изменения DTO, WorldSnapshotService, SqlitePublicationCommitStore и test_atomicity.py. Основания: world-domain-snapshot-rollback-trace.md и исходное world-domain-snapshot-cas-trace-review.md. Production-код и существующие тесты при ревью не изменялись.

## Результаты

- World conflict через штатный WorldSnapshotService: исходные expected/observed, publication provenance и единственный world mismatch сохранены; player CAS не вызывается. Caller получает ROLLED_BACK.
- Конфликт второго игрока: сохранена последовательность world applied / p1 applied / p2 mismatch, цели сопоставлены по UID несмотря на обратный порядок refs. Expected p2 содержит stale ref, observed и provenance отсутствуют. Applied остаётся фактом сравнения, ROLLED_BACK отдельно определяет судьбу попытки.
- Независимое SQLite-соединение подтверждает прежний world head, отсутствие player heads, metadata candidate-world/candidate-p1/candidate-p2 и всех marker-записей handlers после rollback. Claim операции, выполненный до транзакции публикации, не является отменённой записью этой попытки.
- Успешная публикация повторена: peer видит новые heads, metadata и три markers. При отказе второго handler сохранён исходный объект SectionRefused, третий handler и CAS не выполняются; peer не видит записей попытки.
- Проверка существующего head игрока после последующей публикации подтверждает, что trace хранит исходные observed/provenance, а не перечитывает новый head.

## Независимая инъекция rollback

Дополнительный воспроизводимый скрипт: `backend/independent_rollback_probe.py`, запуск из backend: `python independent_rollback_probe.py`. Он вызывает штатный WorldSnapshotService с реальным world CAS mismatch и предварительной SQL-записью внутри той же транзакции. Подменяется только driver.rollback.

Три режима прошли: штатный rollback; OSError до физического rollback; OSError после физического rollback, моделирующий потерю acknowledgement. Проверяется PENDING при входе в rollback и после физической команды до возврата acknowledgement. Только штатный режим даёт caller SnapshotCasConflict с ROLLED_BACK. Оба отказа дают наружу UnknownCommitOutcome, сохранённый исходный конфликт остаётся PENDING. Peer подтверждает исходный head и откат предварительной записи даже после quarantine/close; это наблюдение не превращает неизвестный исход в подтверждение от владельца транзакции.

Существующий тест дополнительно проверяет rollback, оставляющий транзакцию активной, и отсутствие транзакции до rollback: оба дают UnknownCommitOutcome и PENDING. В нём конфликт искусственный; дополнительная проба выше закрывает проверку отказа на конфликте реального сервиса.

По коду DTO неизменяемый trace заменяется через _replace только после успешного driver.rollback и проверки отсутствия активной транзакции. Driver ожидает завершения SQLite worker и вызывает pending.result(), поэтому исключение команды не теряется. CancelledError сохраняет отдельную семантику. Контрпример исходного ревью закрыт.

## Запуски

`python -m unittest -v tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests tests.snapshotCore.storage.publication.test_cas`: **25 tests, OK**, 54.255 s. Лог: `backend/snapshot-independent-targeted.log`.

`git diff --check` по четырём файлам исправления: PASS.

Предел ревью: исправления cancel/GC producers, persisted terminal и retry не выполнялись.

Полный независимый запуск `python -m unittest discover -s tests/snapshotCore -v`: **171 tests / 149.033 s; 8 ERROR, 1 FAIL, 1 SKIP**. Лог: `backend/snapshot-independent-review.log`. Все восемь ID ошибок и ID typing failure совпадают с таблицей исходного ревью: пять ConcreteLeaseTests и два SqliteBlobLifecycleTests падают в cancel на leaseStore.py:165; ArtifactStagingTests.test_gc_io_failure_cancellation_and_uncertainty — artifactGc.py:47. Причина runtime — запрещённое прямое создание FieldPathError. TypingGateTests.test_nominal_refs_keys_and_outcomes сообщает отсутствующий code в artifactGc.py. Windows symlink skip также совпадает. Относительно исходной базы 170 тестов добавлен один прошедший тест rollback; новых падений нет. Это сопоставление с зафиксированной базой, без checkout старой версии.

**Итог: PASS для исправления rollback trace; общий snapshotCore остаётся красным только на зафиксированной базе cancel/GC. Стоп перед исправлением этих producers и изменением terminal/retry.**
