# Pack: потребители Snapshot/Artifacts canonical codec

2026-11-14. Статическая адресная проверка, без изменения кода, запуска приложения или тестов. Не является приёмкой R1/R3. Bump/перенумерация не согласованы этим ответом.

## Реальные зависимости

- `backend/app/core/container/packs.py::initialize_pack_storage` создаёт `SqliteOperationStore(..., StoredTerminalCodec(), ...)`, затем `SqliteArtifactLeases`. Wiring условный: нужны world_pack и manifest_max_bytes. Это реальная зависимость Pack storage от codec, но не доказательство наличия записанных terminal outcomes в эксплуатации.
- `backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py::_load` читает `publication_outcomes` и вызывает codec.decode; запись terminal вызывает codec.encode. Поэтому несовместимый сохранённый terminal может нарушить загрузку operation через storage dependencies, даже если Pack не читает Snapshot metadata непосредственно.
- `backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py::StoredTerminalCodec` объединяет SNAPSHOT_CORE_SCHEMA с extension. Принимает только row.format_version=1; encode пишет 1. Варианты: SnapshotApplyResult, PackActivationResult, GameplayStarted, OperationCancelled. Checksums и row/body identity проверяются. Новый номер без reader/cutover решения не делает старые bytes читаемыми.
- `backend/app/application/worldData/pack/encoding/manifestCacheKey.py::manifest_cache_key` делает strict ArtifactRef admission и digest(ref, ARTIFACT_CORE_SCHEMA). Caller — `worldData/pack/read/pinnedManifestReader.py`: resolve/read_verified/admit_cached. Это ключ bytes cache, не Snapshot metadata codec.

## Что меняет bytes и что не меняет

`backend/app/encoding/canonicalCodec.py` кодирует конкретные records как type_id + ordered name/value fields; enum — type_id + wire value. Decoder требует поля owning record. Сам roster manifest целиком в каждый payload не включается.

Поэтому добавление registrations других owners или изменение World/PlayerSnapshotMetadata/SectionApplyReceipt не меняет digest ArtifactRef при неизменных ArtifactRef/ArtifactKind IDs, полях, значениях и canonical algorithm. Pack не требует bump cache key/contract из-за такого изменения. Перенумерация ArtifactRef=20107 либо ArtifactKind=20003, изменение полей ArtifactRef или canonical encoding изменит ключ и может сделать старые refs нечитаемыми; это отдельное воздействие, которого R1/R3 не обосновывают.

R1: изменение полей SectionApplyReceipt (PATCH_CORE_SCHEMA, ID20132) и World/PlayerSnapshotMetadata (SNAPSHOT_CORE_SCHEMA, IDs20133/20134) меняет encoding этих записей и содержащих их графов. Если существуют bytes прежней формы, новый exact decoder не обеспечивает их совместимость автоматически. Сам факт присутствия типов в общей schema не меняет encoding независимого PackActivationResult.

R3: добавление concrete typed relation issue требует registration самого типа и его nested/path owners в реально используемой composition, иначе exact-type encoder/restore не работает. Если существующие diagnostics поля и прежние concrete variants сохраняют форму, добавление нового варианта само по себе не требует изменения bytes старых outcomes. Старый reader не знает новый type ID; необходимость поддержки смешанных readers/writers должна быть отдельным подтверждённым требованием. Если меняется форма SnapshotApplyResult, воздействие шире и нужно сравнить exact fields. Реализация R3 в этом аудите не предъявлена.

## Fixtures и гарантии

- `backend/tests/snapshotCore/contracts/test_codec.py`: round-trip terminal, format_version=1, exact ID roster/число declarations, независимость encoding от порядка manifest entries, merge shared declarations, metadata round-trip и отказы malformed/unsupported envelope. Добавление registrations потребует обновить roster assertions; это не доказательство необходимости production migration.
- `backend/tests/snapshotCore/support/fixtures.py` и `support/diagnostics.py`: создают SqliteOperationStore со StoredTerminalCodec(TEST_ISSUE_SCHEMA); данные генерируются тестовыми fixtures. `storage/publication/test_atomicity.py` и `lifecycle/test_capabilities.py` также используют production codec.
- `backend/tests/cache/test_container_v2.py`: manifest key воспроизводится из восстановленного ArtifactRef, изменение descriptor даёт miss. Это проверка identity по полному ref, не закреплённый binary Snapshot fixture.
- В поиске файлов backend/tests с расширениями bin/sqlite/db/hex обнаружены только нерелевантные Planning wire hex fixtures. Это ограниченный поиск, не утверждение отсутствия любых embedded/golden bytes во всём проекте.
- Эксплуатационная БД, backup, rollout со старыми readers и сохранённые пользовательские outcomes в этой проверке не исследовались; наличие или отсутствие таких данных НЕ установлено. Wiring и свежие test fixtures не доказывают необходимость legacy совместимости.

## Вывод для владельца Snapshot

Pack не предъявляет требования автоматически вводить version 2 или перенумеровывать shared owners из-за R1/R3. Сохранить ArtifactRef/ArtifactKind identities и unrelated Pack terminal shapes. Для изменённых persisted records сначала определить требование чтения существующих bytes и exact изменение формы. При подтверждённой необходимости их сохранения нужен явный совместимый reader/migration/cutover; один bump недостаточен. Если старые данные не должны поддерживаться по принятому проектному решению, это решение фиксируется явно — не выводится из отсутствия найденного fixture. Общее требование пользователя «один итоговый код» сохраняется; параллельный legacy codec этим аудитом не предлагается.
