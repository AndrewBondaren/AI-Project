# Source consumer audit: Snapshot codecs и canonical dependencies

2026-11-14. Выполнено по явному разрешению пользователя на запрос Snapshot. Read-only аудит кода/контрактов; создан только этот отчёт. R1/R3 изменения receipt/metadata layout и SnapshotApplyResult diagnostics остаются НА СОГЛАСОВАНИИ. Версия 2, смена existing IDs и legacy compatibility этим аудитом не принимаются. Основной S1/S2 scope не расширяется до их реализации.

## Итог со стороны Source

**Прямых runtime Source callers StoredTerminalCodec/SnapshotEnvelopeCodec или трёх CORE_SCHEMA не обнаружено:** backend/app/dataModel/sourceVersioning и backend/app/application/worldData/sourceVersioning отсутствуют. Это проверка конкретного целевого Source домена, не утверждение отсутствия других действующих потребителей в проекте.

Source proof design имеет отдельный SOURCE_PROOF_SCHEMA_V1 и зависит от shared ArtifactKind/ArtifactRef с IDs 20003/20107. Он не включает полный SNAPSHOT/PATCH/ARTIFACT lifecycle manifest. Изменение только Snapshot receipt/metadata/diagnostics layout поэтому не обязано менять Source proof bytes/fingerprint. Изменение ArtifactRef/ArtifactKind, их IDs, canonical TLV/field encoding или content_digest затрагивает Source непосредственно и требует отдельной проверки. Добавление несвязанных manifest entries само по себе не меняет encoded value при неизменных достижимых types/fields/IDs.

Будущий Source mutation terminal — отдельная проектная зависимость existing operation ledger/StoredTerminalCodec, пока не runtime caller. Подменять Source outcome SnapshotApplyResult/PackActivationResult ради существующего allowlist запрещено. Доказательств эксплуатационных persisted Source terminal/proof данных в проверенных материалах нет; это не доказательство отсутствия любых пользовательских баз.

## 1. Concrete callers, существующие сейчас

Пути ниже относительно backend/app; строки/поведение проверены на дату аудита.

| Компонент | Фактический путь и эффект | Отношение к Source |
|---|---|---|
| StoredTerminalCodec | db/repositories/sqlite/snapshotCore/operations/operationStore.py: _load → _codec.decode(terminal); _save → _codec.encode(outcome) → storage row. core/container/packs.py: initialize_pack_storage создаёт SqliteOperationStore(..., StoredTerminalCodec(), ...) при наличии Pack settings | Existing инфраструктура/Pack composition, не Source caller |
| SnapshotEnvelopeCodec | db/repositories/sqlite/snapshotCore/history/snapshotHistoryStore.py: default codec; append → rowProjection.encode_history_row; read → decode_history_row | Existing Snapshot history, не Source payload codec |
| Snapshot row projection | db/repositories/sqlite/snapshotCore/history/rowProjection.py кодирует envelope, SHA-256 exact bytes; decode проверяет checksum, version, refs и совпадение SQL columns/body | Layout change затрагивает эти consumers независимо от Source |
| ARTIFACT_CORE_SCHEMA | application/artifacts/encoding/coreManifest.py; включён в PATCH_CORE_SCHEMA; application/worldData/pack/encoding/manifestCacheKey.py: digest(ref, ARTIFACT_CORE_SCHEMA) | Shared ArtifactRef encoding важен Source по design; actual cache-key caller принадлежит Pack |
| PATCH_CORE_SCHEMA | application/patch/encoding/coreManifest.py включает artifact entries + Patch/section/dependency/receipt types; application/patch/registry/sectionRegistry.py объединяет core с domain contract manifest | Existing Patch composition, не реализованный Source mutation binding |
| SNAPSHOT_CORE_SCHEMA | application/worldSnapshot/encoding/coreManifest.py включает PATCH_CORE_SCHEMA + metadata/log types; используется обоими codec | Будущий Source terminal integration может потребовать composition, но сейчас отсутствует |

StoredTerminalCodec принимает exact classes SnapshotApplyResult, PackActivationResult, GameplayStarted, OperationCancelled. Decode требует format_version=1 и известный outcome_kind; encode записывает 1 и checksum. SourceMutationApplied/SourceFailure в allowlist отсутствуют. SnapshotEnvelopeCodec поддерживает только envelope version 1 и WorldSnapshotMetadata/PlayerSnapshotMetadata. Не считать регистрацию класса в manifest достаточной для расширения этих boundaries.

## 2. Freeze и влияние layout

docs/tz_world_snapshot.md, раздел «Контракты ядра Snapshot — freeze шага 2 (2026-10-30)» фиксирует принятый design; наличие freeze не доказывает эксплуатационную запись данных. Текущий codec/manifest и тесты фиксируют v1 implementation behavior, но не разрешают выбирать v2 или менять IDs в рассматриваемом proposal.

Relevant existing IDs: ArtifactKind=20003, ArtifactRef=20107, SnapshotApplyResult=20124 (ARTIFACT_CORE_SCHEMA); SectionApplyReceipt=20132 (PATCH_CORE_SCHEMA); WorldSnapshotMetadata=20133 и PlayerSnapshotMetadata=20134 (SNAPSHOT_CORE_SCHEMA). Даже Snapshot diagnostics находятся в transitive artifact schema: имя manifest не является границей принадлежности всех его records.

app/encoding/canonicalCodec.py: record bytes содержат registered type_id и tuple пар (field name, value) в порядке model_fields/dataclass fields. Frozen manifest хранит python_type binding, не отдельную копию исторического layout. Изменение полей того же Python owner может изменить wire bytes и checksum/fingerprint при прежнем ID. Следовательно, утверждение «IDs не изменились, значит совместимость сохранена» недопустимо. Выбор нового version/ID или поддержки старого layout остаётся отдельным решением владельца; Source его не выводит из риска автоматически.

Canonical digest — SHA-256 exact encoded bytes. При сохранённых bytes checksum проверяется на этих bytes; при новом encode изменённой формы checksum будет иным. Runtime decode/validation и typed error diagnostics требуют отдельной проверки после R1/R3, даже если Source proof schema непосредственно не затронута.

## 3. Source design dependencies — не runtime

| Источник | Зафиксированная зависимость | Ограничение вывода |
|---|---|---|
| source-proof-v2-contract-spec.md §9.2, §11.4 | Fingerprint = content_digest(CanonicalCodec(SOURCE_PROOF_SCHEMA_V1).encode(proof)).hex(); fixed IDs/field order; shared 20003/20107, full lifecycle manifest не требуется | Runtime Source schema ещё не существует. Snapshot metadata/receipt/diagnostics не дети persisted proof |
| Та же спецификация §11.4 | Requests/results/SourceFailure/runtime ports исключены из persisted proof manifest | Нельзя включить новые Snapshot diagnostics или SourceFailure в proof schema «заодно» |
| source-pregame-revision-staging-design.md, terminal dependency и P2.2 | Предложены SourceMutationApplied/source_mutation и регистрация в terminal union, StoredTerminalCodec, manifest, operation validation и SQL checks; возможен merge с SNAPSHOT_CORE_SCHEMA | Это проект будущего binding, не доказанная действующая запись или согласие на конкретный R1/R3 layout |
| source-mutation-artifacts-publication-response-2026-11-13.md | Proposed refusal terminal/source_mutation_refused, Source diagnostics и typed context | Canonical registration/runtime integration нельзя считать существующими по тексту proposal |
| source-pack-s1-s2-contract.md, принятая редакция 2 | SourceFailure проходит отдельный internal rollback carrier; preflight result не authority; accepted adopt проверяет closure/holds | Не вводит persisted SnapshotApplyResult с Source diagnostics и не связывает proof fingerprint с Snapshot receipt layout |

Source mutation request fingerprint по проекту использует отдельный SOURCE_MUTATION_SCHEMA_V1 и Source/Artifact refs; terminal bytes не следует автоматически считать исходным request fingerprint. При будущем merge нужны одинаковые shared IDs/owners/kinds и явная поддержка Source outcome codec/ledger, без второго журнала и без переименования Source success в Pack result.

## 4. Tests и persisted эксплуатационные данные

Найдены concrete test consumers: backend/tests/snapshotCore/contracts/test_codec.py (reserved IDs, manifest merge/order invariance, exact canonical bytes, round-trip, unsupported versions, diagnostics); storage/publication/test_history.py и test_atomicity.py; support/fixtures.py с StoredTerminalCodec(TEST_ISSUE_SCHEMA), support/diagnostics.py и fakeSection.py с дополнительными тестовыми bindings; typing/snapshotCore/valid.py и invalid.py. Это test fixtures/contracts, не production records. Аудит их не мигрирует и не объявляет пригодными для новых Source fixtures.

Source V0/V1 vectors в спецификации §11.4 прямо обозначены как рассчитанные encoding examples без runtime Source POJO/finalization; V1 не существующий finalized artifact. Они подтверждают целевой layout, но не deployment/persisted usage.

Поиск доступных workspace файлов rg --files с расширениями .db/.sqlite/.sqlite3 не дал кандидатов; ignored/external/runtime-created базы этим поиском не покрываются. Базы не открывались, таблицы не опрашивались, telemetry/deployment audit не выполнялись. Наличие persistence кода и DI wiring доказывает возможность записи, не факт эксплуатационных данных. Поэтому нельзя утверждать ни обязательность backward compatibility из-за доказанной эксплуатации, ни гарантированное отсутствие старых данных.

## 5. Ответ Snapshot по R1/R3

1. Со стороны реализованного Source прямых codec callers для миграции не найдено. Новые версии и IDs Source не запрашивает.
2. При изменении только Snapshot receipt/metadata/diagnostics сохранить отдельность Source proof schema; проверить реальные Snapshot/Artifact/Patch consumers выше и согласовать layout у их владельцев.
3. Если затронуты shared ArtifactKind/ArtifactRef/canonical encoding, предъявить exact old/new поля/IDs и влияние на Source fixed vectors; автоматически менять Source fingerprint contract нельзя.
4. Будущий Source terminal binding сверить с итоговым утверждённым Snapshot/Artifacts контрактом перед реализацией. Нынешний proposal не основание для legacy adapter, dual-read или временного mirror DTO.
5. Эксплуатационная совместимость остаётся недоказанной потребностью. Решение по версии/IDs принимать отдельно по owner contract и evidence данных; audit не является приёмкой R1/R3.

Код, схемы, IDs и tests не менялись; тесты не запускались. Исходники прочитаны статически; внешний origin-path вопрос слоя C этим отчётом не закрывается.
