# Snapshot R1–R3: точное предложение изменения контрактов

2026-11-14. **R1–R3 и текущая таблица encoding приняты к реализации при отсутствии готовых аналогов.** Основание — пользователь: «R1–R3 и эта таблица encoding. Если в текущем коде ничего подобного нет, то можно имплементировать». Проверка новых типов описана ниже. Владелец — Snapshot (включая внутренние Patch/publication/Artifacts bindings). Основание архитектуры: snapshot-public-apply-atomic-trace.md. Код и DDL на момент preflight не изменены. Приёмка старых 4D2 helpers/tests сохраняется в их прежних границах.

### Preflight реализации — 2026-11-14

**Preflight закрыт:** пользователь разрешил синхронизацию двух ТЗ ответом «Да». Реализация контрактов и существующих внутренних путей предъявлена ниже; общий public apply/wiring не объявлен завершённым.

Поиск по backend/app и backend/tests не нашёл SectionStateRetention, SectionHistoryRetention, SnapshotOperationCancelledError, SnapshotApplyRelationIssue, SnapshotApplyCode или OperationBindingMismatch. Существующие SectionStateRef/SectionHistoryRef, OperationCancelled, CasConflictTrace/WorldCasMismatch/PlayerCasMismatch и canonical codecs переиспользуются; создавать их копии не требуется. В SqliteOperationStore.claim_publication immutable mismatch ещё выражен ValueError. WorldSnapshotService содержит private helpers, публичного apply пока нет: нельзя объявлять R2/R3 end-to-end caller mapping выполненным добавлением одних типов.

Перед первой правкой кода обнаружено расхождение принятого предложения с действующими SoT:

- docs/tz_patch_system.md, строки 291–294: SectionApplyReceipt закреплён как history_refs/state_refs/changed/retained_artifacts; R1 заменяет три flat поля на states/history retention records.
- docs/tz_world_snapshot.md, строки 353–355: SnapshotApplyResult.diagnostics закреплён как tuple[FieldPathError, ...]; R3 добавляет SnapshotApplyRelationIssue. R2 также требует явно описать public carrier сохранённой отмены отдельно от cancellation invocation.

По implement-plan, раздел «Истина»: «Расхождение план ↔ ТЗ — стоп, один вопрос мастеру; не “чинить ТЗ заодно”». Поэтому код не начат до разрешения синхронизировать эти точные SoT-пункты с уже принятым R1–R3; повторной приёмки семантики не требуется. Изменение версии 2, legacy decoder, migration, DAG wiring и Time T5 не предлагаются.

Дополнительный обнаруженный R1 consumer: backend/app/db/repositories/sqlite/artifacts/holderStore.py::handoff читает metadata.retained_artifacts. В реализации он должен брать deduplicated union из новых states/history closures, сохраняя caller-owned transaction и explicit transferred. Нельзя ограничить cutover builder/reader и оставить этот consumer старого поля.

Получен также [аудит Source](snapshot-codec-source-consumer-audit.md): прямых runtime Source consumers этих schemas нет; shared ArtifactRef/ArtifactKind и общий canonical алгоритм сохраняются. Это дополняет аудиты Pack/Time, не доказывает отсутствие эксплуатационных БД. Tests в preflight не запускались; выполнены rg и чтение текущих service/store/models/SoT. Чужие изменения сохранены.

Статусы «НА СОГЛАСОВАНИИ» ниже относятся к истории подготовки предложения и заменены указанной выше пользовательской приёмкой; снятый вариант encoding v2 остаётся снятым.

### Реализация и проверка — 2026-11-14

База проверки: HEAD `f3e8650cc9894c81abd200e1c543196f001c70ed` и рабочие изменения. Коммит не создавался. До правок прочитаны implement-plan, DAG acceptance criteria, текущие models/service/SQLite consumers и SoT-пункты. Готовых новых типов не было; refs, cancellation outcome, codecs, CAS traces и transaction coordinators переиспользованы.

**Реализовано:**

- R1: native states/history records с полным artifact closure; strict/frozen/unique-artifacts. Receipt/metadata больше не имеют flat state_refs/history_refs/retained_artifacts. Builder наследует exact states и заменяет только owner/section, не копирует parent history. Provenance проверяет полный результирующий state набор, включая отсутствие потери незатронутых секций и неизменность inherited closure. AcceptedStateReader возвращает прежний SectionStateRef. Holder adapter получает unique union через pure retention_closure; отдельная внешняя карта retained удалена из builder и private service helpers.
- Частично повреждённый receipt: ref проверяется независимо от sibling artifacts, с исходным индексом. Ошибки missing persisted base идут world → players → builder; повторная missing_base подавляется. Старый UNASSIGNED_ARTIFACT случай отдельного flat artifacts больше не представим новым native DTO. Составной regression теперь проверяет missing_persisted_base + invalid_receipt + foreign_history + foreign_operation, без переименования оставшихся owner codes.
- R2/R3: strict carrier OperationBindingMismatchError и его requested/stored POJO вместо одной ValueError-ветки claim_publication. WorldSnapshotService._claim_publication переводит только этот carrier в REJECTED предъявленного запроса без сохранения terminal. Проверяет binding returned claim; terminal cancellation выдаёт SnapshotOperationCancelledError с existing outcome; unrelated ValueError и asyncio.CancelledError не переклассифицируются. Store владеет короткой claim transaction; helper не открывает дополнительную transaction и не читает targets на terminal replay.
- SnapshotApplyResult допускает concrete field или relation issues; SectionRefused не изменён. Concrete issue code/context strict, mixed diagnostics проходят durable codec round-trip. Existing IDs/версии 1 сохранены; зарегистрированы 20301/20302/20306/20307. Legacy decoder, dual-read, migration и изменение общего canonical algorithm не добавлялись.

**Файлы реализации** (пути относительно корня):

- Новые: `backend/app/dataModel/worldSnapshot/sections/retention.py`, `backend/app/dataModel/worldSnapshot/results/applyIssues.py`, `backend/app/dataModel/publication/operationBindingMismatch.py`, пустой `backend/app/dataModel/publication/__init__.py`, `backend/app/application/worldSnapshot/errors.py`, `backend/app/application/worldSnapshot/validation/retentionClosure.py`.
- Модели/encoding: `backend/app/dataModel/patch/results/sectionResult.py`, `backend/app/dataModel/worldSnapshot/metadata/envelope.py`, `backend/app/dataModel/worldSnapshot/results/apply.py`, `backend/app/application/patch/encoding/coreManifest.py`, `backend/app/application/artifacts/encoding/coreManifest.py`.
- Application/storage: `backend/app/application/publication/errors.py`, `backend/app/application/worldSnapshot/service/snapshotMetadataBuilder.py`, `worldSnapshotService.py`, `acceptedStateReader.py` в той же папке; `backend/app/application/worldSnapshot/validation/receiptProvenance.py`; `backend/app/db/repositories/sqlite/artifacts/holderStore.py`, `backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py`.
- Новые tests: `backend/tests/snapshotCore/contracts/test_retention_contract.py`, `backend/tests/snapshotCore/storage/publication/test_claim_mapping.py`.
- Адаптированы tests: contracts `test_models.py`, `test_codec.py`, `test_registry.py`; storage/publication `test_history.py`, `test_cas.py`, `test_atomicity.py`; support `fixtures.py`, `artifactFixtures.py`, `fakeSection.py` — все внутри `backend/tests/snapshotCore/`; `backend/tests/typing/snapshotCore/valid.py`, `invalid.py`.
- Документы: `docs/tz_patch_system.md`, `docs/tz_world_snapshot.md`, этот файл и короткая ссылка из `world-domain-patches-snapshots.md`. Ранее существовавшие SNAPSHOT-V1 комментарии сохранены, в этом срезе не добавлялись заново. Чужие планы/ТЗ/удаления не откатывались.

**Команды и результаты** (cwd `backend`, Python `.venv/Scripts/python.exe`):

1. `-m unittest tests.snapshotCore.storage.publication.test_claim_mapping tests.snapshotCore.contracts.test_retention_contract` — **4 OK**.
2. `-m unittest tests.snapshotCore.contracts.test_typing tests.snapshotCore.contracts.test_retention_contract tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests.test_metadata_handoff_and_heads_share_outer_transaction tests.snapshotCore.storage.publication.test_atomicity.AssignedPublicationTests.test_missing_persisted_bases_preserve_independent_receipt_diagnostics` — **5 OK**; typing positive **0**, negative **58 EXPECT**, включая новые nominal retention и relation error types.
3. `-m unittest discover -s tests/snapshotCore -t .` — финально **182 tests, 0 failures, 0 errors, 1 skip**, 156.311 s. Skip: symlink privilege unavailable on this Windows host, `test_blob_backend.py`. Предыдущий промежуточный full run: 180 OK/1 skip до добавления двух contract tests.
4. Time read/core — **33 OK**, 16.095 s. Обычный combined запуск был прерван на Windows event-loop bootstrap; повтор выполнен через stdin runner ниже, без изменения runtime или Time tests.
5. `-m unittest tests.cache.test_container_v2` — первоначально 1 environmental error (PermissionError записи sandbox Temp config.toml); повтор `-c 'import tempfile, unittest; from pathlib import Path; tempfile.tempdir=str(Path("tests/.tmp_snapshot_core").resolve()); unittest.main(module=None, argv=["unittest", "tests.cache.test_container_v2"])'` — **7 OK**, 0.084 s. Project temp остаётся внутри tests.
6. `git diff --check -- <перечисленные файлы>` — PASS. Вызваны `git diff HEAD -- ...`, показаны новые файлы, отправлен `open_in_codex` review/last-turn (UI вернул queued). Не заявлять, что пользователь уже просмотрел diff.

Повторяемый Time runner (`@' ... '@ | .venv/Scripts/python.exe -` в PowerShell):

```python
import asyncio, selectors, time, unittest
from unittest.mock import patch
from tests.time.test_time_core import ReadPortTests
def no_pipe(loop):
    loop._ssock = loop._csock = None
def factory():
    selector = selectors.SelectSelector()
    selector.select = lambda timeout=None: (time.sleep(min(0.002, timeout) if timeout is not None else 0.002), [])[1]
    return asyncio.SelectorEventLoop(selector)
ReadPortTests.loop_factory = staticmethod(factory)
with patch.object(asyncio.SelectorEventLoop, '_make_self_pipe', no_pipe), patch.object(asyncio.SelectorEventLoop, '_close_self_pipe', lambda loop: None):
    unittest.main(module=None, argv=['unittest', 'tests.time.test_snapshot_read_source', 'tests.time.test_time_core'])
```

**Транзакционные evidence и пределы:** existing service partial-handoff regression использует две независимые connections одной временной SQLite БД. После commit: a — только world SnapshotHolder; b — player SnapshotHolder + исходный OperationHolder; leftover — только исходный OperationHolder. Cancel на player CAS откатывает metadata, world CAS и handoff; отказ на leftover тоже откатывается. Claim mismatch на первой connection виден caller как typed отказ после выхода store transaction; вторая connection подтверждает неизменность исходной operation/terminal. Stored refusal replay и early/bound cancellation проверены через private service admission, без target reads и без дописывания fingerprint.

**Не закрыто этим срезом:** public WorldSnapshotService.apply и его production/DAG composition по-прежнему отсутствуют. Автоматическое вычисление public full-transfer intersection и сквозная привязка всех core codes к public apply фазам не объявляются реализованными лишь наличием новых DTO/helper. Admission mapping реализован внутренним _claim_publication и проверен напрямую. Public full apply — следующий интеграционный срез; terminal/retry recovery, Time T5, crash takeover, real deployment/старые БД не проверялись и не менялись. Пользовательская приёмка реализации и независимое ревью ещё не получены.

| Решение | Статус | Что согласуется |
|---|---|---|
| R1 | НА СОГЛАСОВАНИИ | Retention по exact state/history ref, наследование полного closure и отдельная политика public transfer; изменение receipt/metadata |
| R2 | НА СОГЛАСОВАНИИ | SnapshotOperationCancelledError с существующим OperationCancelled для сохранённой отмены |
| R3 | НА СОГЛАСОВАНИИ | Typed core diagnostics только в SnapshotApplyResult и typed immutable-binding mismatch без изменения исходного terminal |

После решения по семантике отдельно закрепить canonical IDs/formats. Требование поддержки прежнего формата снято решением пользователя ниже. Статус «на согласовании» не означает разрешение миграций, adapters, DAG wiring или terminal/retry recovery.

### Решение пользователя о совместимости — 2026-11-14

Пользователь: «legacy decoder поддерживать не нужно». Для текущего среза остаётся один итоговый codec с новой принятой моделью; прежний layout специально не поддерживается. Не добавлять legacy decoder, dual-read, compatibility adapters или миграции. Отдельного согласования необходимости чтения прежней формы больше не требуется. Это не разрешение удалять существующие данные и не утверждение об их отсутствии.

Предложение обязательного перехода на версии 2 и замены existing IDs **снято как необоснованное**. Отсутствие legacy decoder само по себе не диктует номер версии: final IDs/formats фиксируются по принимаемому контракту, без отдельной ветви совместимости. Shared ArtifactRef/ArtifactKind encoding и unrelated Pack outcomes сохраняются. Новым concrete retention/diagnostic types нужны свои registrations.

R1–R3 остаются НА СОГЛАСОВАНИИ: решение о legacy не является приёмкой их семантики или разрешением на реализацию. Ниже сохранён исторический вариант encoding freeze для прослеживаемости; его таблица замен existing IDs, версии 2 и соответствующие old-version rejection tests **не являются текущим заданием**.

### Текущее предложение encoding — НА СОГЛАСОВАНИИ

Получен [аудит Time](snapshot-codec-time-consumer-audit.md). Time не требует bump/перенумерации; непосредственный потребитель заменяемого поля — Snapshot-owned AcceptedStateReader.resolve_snapshot. При сохранении его результата SectionStateRef Time factory/read source менять не требуется. CLOCK_FORMAT и JSON clock payload остаются прежними. В static inventory вызовы make_time_reader найдены в tests; production activation не подтверждена. Аудит не заявляет отсутствие любых эксплуатационных данных.

С учётом решения пользователя о legacy предлагается один итоговый формат:

| Owner / формат | Предложение |
|---|---|
| SectionApplyReceipt | Сохранить ID 20132, заменить layout после приёмки R1; собственного поля версии нет |
| WorldSnapshotMetadata / PlayerSnapshotMetadata | Сохранить IDs 20133/20134 и envelope_format_version=1, принять окончательный layout без чтения прежнего flat layout |
| SnapshotApplyResult | Сохранить ID 20124 и terminal format_version=1; расширить diagnostics после приёмки R3 |
| Новые SectionStateRetention / SectionHistoryRetention | Candidate IDs 20301/20302; PATCH_CORE_SCHEMA |
| Новые SnapshotApplyCode / SnapshotApplyRelationIssue | Candidate IDs 20306/20307; ARTIFACT_CORE_SCHEMA |
| ArtifactRef, ArtifactKind, Pack/Gameplay/Cancelled outcomes | Сохранить encoding, IDs и версии |

Это явная ревизия проектируемого контракта, не обещание backward compatibility. Старые names/layout не угадывать и не преобразовывать. Не отказывать любому version=1: окончательные records также имеют version=1. Strict decoder отвергает неподходящий layout по фактической форме. IDs 20303–20305 из снятого варианта не назначаются; перед реализацией перепроверить отсутствие конфликтов четырёх новых candidates в актуальном дереве.

Дополнить regression-план командой из backend: `python -m unittest tests.time.test_snapshot_read_source tests.time.test_time_core`. Сохранить exact current/pinned/historical semantics и наследование clock ref предка; обновить только fixtures и Snapshot-owned reader под R1. Это программа будущей проверки; тесты в данном документальном проходе не запускались, T5 не начат.

Осталось согласовать единым предложением: R1 ownership/наследование полного closure и public transfer; R2 carrier сохранённой отмены; R3 typed core issues и immutable-binding mismatch; приведённый окончательный encoding. Вопрос о необходимости legacy закрыт пользователем и повторно не ставится.

### Историческое предложение encoding freeze — СНЯТО

**Уточнение после проверки потребителей 2026-11-14:** приведённые ниже версии 2 и замены existing IDs — неподтверждённый вариант, не необходимое условие R1–R3. Не переносить их в implementation freeze без отдельного основания. [Аудит Pack](snapshot-codec-pack-consumer-audit.md) не предъявил требования bump/перенумерации: изменение других records не меняет ArtifactRef cache digest и независимые Pack outcomes. Эксплуатационные старые bytes не исследованы; наличие shared codec не доказывает их существование. Первоначальное предложение version 2 было сделано до этой проверки.

Прямые зависимости по static search: StoredTerminalCodec → SqliteOperationStore → Pack container; SnapshotEnvelopeCodec → history rowProjection/store → Time composition/AcceptedStateReader; PATCH_CORE_SCHEMA → SectionRegistry; ARTIFACT_CORE_SCHEMA → Pack manifestCacheKey. Общий app.encoding.canonicalCodec также используется Planning, Hydrology, artifact staging и Pack codecs, но это не означает использование ими изменяемого Snapshot layout. Алгоритм canonicalCodec в R1–R3 не предлагается менять.

По запросу пользователя вопросы отправлены агентам Pack, Time и Source. Pack ответил отдельным аудитом; Time на момент этой записи ещё проверяет. Source отказался расширять свой текущий scope, аудит от него не получен. Ответы агентов не подменяют пользовательскую приёмку.

Проверка 2026-11-14: поиск `2030[1-7]` по backend/app, backend/tests, docs и .cursor/plans до этой записи совпадений не дал. Это локальные кандидаты для объединяемой Artifacts → Patch → Snapshot schema, не глобальное резервирование. Перед реализацией повторить поиск, учитывая параллельную работу. Отдельного глобального allocator текущий CanonicalSchemaManifest не требует: он проверяет уникальность owner/ID внутри composition.

| Candidate ID | Exact owner | Где объявляется |
|---|---|---|
| 20301 | SectionStateRetention | PATCH_CORE_SCHEMA вместе с receipt dependencies |
| 20302 | SectionHistoryRetention | PATCH_CORE_SCHEMA вместе с receipt dependencies |
| 20303 | SectionApplyReceipt с новым layout | PATCH_CORE_SCHEMA вместо старого declaration 20132 |
| 20304 | WorldSnapshotMetadata с новым layout | SNAPSHOT_CORE_SCHEMA вместо 20133 |
| 20305 | PlayerSnapshotMetadata с новым layout | SNAPSHOT_CORE_SCHEMA вместо 20134 |
| 20306 | SnapshotApplyCode (ENUM) | ARTIFACT_CORE_SCHEMA вместе с result dependencies |
| 20307 | SnapshotApplyRelationIssue | ARTIFACT_CORE_SCHEMA вместе с result dependencies |

Предложение по версиям:

- Metadata envelope_format_version=2, codec допускает только новый layout/version. Старые 20133/20134 не переназначаются другим классам и не остаются aliases нового owner. Не поднимать версии section payload/SectionStateRef/SectionHistoryRef: их структура не меняется.
- У SectionApplyReceipt нет собственного format_version. Новая identity 20303 различает layout; добавлять поле версии только ради этого не требуется. Старый 20132 не alias нового record.
- SnapshotApplyResult сохраняет 20124: порядок и имена его полей не меняются, расширяется допустимый тип элементов diagnostics. Новые issue types различаются своими IDs. Это additive union, в отличие от R1 replacement layout. Не вводить второй ID для того же python_type: manifest запрещает такой дубль.
- Для terminal outcome_kind=snapshot_apply предлагается storage format_version=2 и отказ версии 1 на этом маршруте. Это явная граница нового набора diagnostics, даже когда конкретный COMMITTED result не содержит их. PackActivationResult, GameplayStarted и OperationCancelled остаются со своими текущими IDs и terminal version=1; codec проверяет версию по discriminator, а не единой константой для всех outcomes.
- R2 application exception и R3 внутренний OperationBindingMismatchError не сериализуются. Их наличие само по себе не требует canonical ID. Record OperationBindingMismatch пока передаётся только внутри процесса; если появится отдельный transport/persistence consumer, его registration согласуется по фактической необходимости.

Почему так: canonicalCodec проверяет exact type ID и точный порядок полей record. Новая identity нужна заменённому layout R1; новый nested issue ID достаточен для расширения union R3. Версия persisted terminal задаёт разрешённый формат хранения отдельно от identity POJO. Unchanged cancellation не становится новым persisted outcome.

Цена предложенного отказа старой формы: ранее сохранённые metadata v1 и snapshot_apply terminals v1 не читаются новым маршрутом. Это **не утверждение, что таких данных нет**, и не разрешение их удалить. Пользователю нужно согласовать эту границу либо поставить отдельную задачу о сохранении читаемости; legacy adapters, dual-read и миграции в текущем срезе запрещены. До решения зависимые codec/store правки не выполняются.

Для future acceptance добавить проверки: old ID/old envelope version отказаны; snapshot_apply v1 отказан; unchanged cancelled/pack/gameplay v1 проходят; смешанные field/relation diagnostics проходят cold round-trip с exact concrete registrations; каждый самостоятельный core manifest замкнут по своим зависимостям. Полный SURFACE_MANIFEST не объединять автоматически: `pack-canonical-registration-audit.md` фиксирует конфликт shared owner IDs между независимыми schemas. Existing field diagnostic declarations включаются через согласованную composition, не копированием всего surface roster.

## R1. Retention привязан к exact state/history ref

### Контрпример и выбранное представление

Плоский retained_artifacts=(a,b) у metadata с секциями X/Y не показывает, какой ref принадлежит X. После замены X нельзя выбрать между удержанием a и b, не зная domain payload. Добавление только destinations world/player в receipt решает первый тик, но не наследование следующего. Сохранение всех старых artifacts навечно под каждым новым snapshot не является решением ownership.

Предлагается заменить предварительный SnapshotArtifactAssignment из S3 двумя concrete records в backend/app/dataModel/worldSnapshot/sections/retention.py:

```python
class SectionStateRetention(BaseModel):
    state: SectionStateRef
    artifacts: tuple[ArtifactRef, ...]

class SectionHistoryRetention(BaseModel):
    history: SectionHistoryRef
    artifacts: tuple[ArtifactRef, ...]
```

Strict/frozen/extra-forbid/revalidate-always; оба поля обязательны; artifacts unique, может быть пустым. Existing SectionStateRef/SectionHistoryRef не копируются, их identity/format_version сохраняются. Две разные обязанности имеют разные поля state/history; не вводится ambiguous union двух одинаковых ref shapes. ArtifactRef, встречающийся и в state, и в history, допустим: он нужен обоим.

**Proposed SectionApplyReceipt** в existing dataModel/patch/results/sectionResult.py:

```python
section_key: SectionKey
states: tuple[SectionStateRetention, ...]
history: tuple[SectionHistoryRetention, ...]
changed: tuple[PatchRef, ...]
```

states/history заменяют state_refs/history_refs; flat retained_artifacts удаляется. Не добавлять параллельные поля со старым и новым смыслом, compatibility properties или dual decoder. Для каждого задействованного owner максимум одна state и одна history entry текущей section; matching section_key, owner, patch operation проверяются как сейчас. History всегда назначен текущему snapshot; no-op не создаёт новый state ref.

**Proposed WorldSnapshotMetadata/PlayerSnapshotMetadata** в existing envelope.py: заменить state_refs/history_refs/retained_artifacts на те же `states: tuple[SectionStateRetention,...]`, `history: tuple[SectionHistoryRetention,...]`. Остальные поля identity/parent/operation/turn/time/base_pack unchanged. Это единственный persisted источник принадлежности; не дублировать flat refs/union в metadata. Общий artifact closure вычисляется чистой проекцией из этих записей. DTO нужны Snapshot и Patch; новые доменные producer contracts этим документом не создаются.

### Точные правила алгоритма

1. Для каждого assigned world/player snapshot загрузить его exact parent metadata в общем writer scope. State mapping ключуется section_key **в пределах owner**, не общей таблицей world/player.
2. Копировать parent.states целиком: inherited state ref и его artifacts остаются exact immutable binding. Parent.history не переносить: оно описывает предыдущий тик и защищено предыдущим snapshot holder.
3. Receipt.states с новым assigned state заменяет только matching owner+section entry. Новый artifacts tuple — **полный storage closure результирующего состояния**, не delta newly staged refs. Owning handler обязан включить inherited dependencies, ещё используемые этим состоянием. Snapshot не вычисляет domain closure.
4. Receipt.states с inherited state ref допускается лишь при full equality с entry pinned parent, включая artifacts. Нельзя изменить closure неизменного ref. Отсутствующая section entry receipt означает сохранение parent state. Empty artifacts — допустимый полный closure только если domain binding действительно не требует artifacts; отсутствие entry и пустой closure не одно и то же.
5. New metadata.history состоит только из receipt.history, каждый history ref назначен текущему owner snapshot. History artifacts — полный closure этой history записи. Они не приклеиваются к следующему state без явной ссылки/зависимости owning handler.
6. SnapshotMetadataBuilder строит metadata и derived map destination→unique union(state artifacts, history artifacts). Foreign assigned refs/duplicate entries/изменённый inherited closure отклоняются до append. Пустой тик наследует state retention каждого owner, без нового history.
7. SnapshotHolder нового snapshot приобретает полный derived union. Старые snapshot holders не снимаются: история immutable. Замена X не снимает hold с parent; она только не добавляет ненужный X artifact в новый snapshot. Общий artifact X/Y сохраняется новым snapshot, пока он нужен хотя бы одной текущей записи.

Полное удаление state section не выводится из отсутствия receipt: deletion должна быть отдельной согласованной domain semantics (например, новый empty/tombstone state). Этот proposal не добавляет generic section delete.

### Handoff и transfer policy

Existing helper _append_metadata_and_handoff сохраняет явный аргумент transferred и **не расширяет его автоматически**. Принятая проверка a-only transfer при назначении a/b остаётся валидной для этого helper. Новый public apply owner должен построить собственный transfer plan до handoff; proposed policy публичного apply: transfer только intersection current operation holds с полным derived closure назначенных snapshots. Не назначенный leftover не передаётся и не освобождается. Уже удерживаемые refs, не принадлежащие operation, приобретаются SnapshotHolder по checked retention, но не считаются transfer из чужого operation.

Это явная новая policy public apply, не изменение поведения existing helper. Она требует пользовательской приёмки: public full apply передаст b, если b в его closure и current operation holds; partial helper тест по-прежнему передаёт только a. Нельзя объявлять historical partial evidence проверкой этой новой public policy.

### Persistence и кодирование — обязательное изменение accepted contract

Receipt и metadata canonical layouts меняются. Перед кодом согласовать текущую encoding-таблицу выше; модели, owning schema и vectors обновить в едином срезе. Новый decoder не читает/не конвертирует старую flat форму. Требование legacy-поддержки закрыто решением пользователя; миграции и adapters запрещены. Здесь заявлено окончательное native представление, не перенос истории.

## R2. Сохранённая отмена отдельно от cancelled invocation

Точная proposed application class в backend/app/application/worldSnapshot/errors.py:

```python
class SnapshotOperationCancelledError(Exception):
    outcome: OperationCancelled
    def __init__(self, outcome: OperationCancelled) -> None: ...
```

outcome — strict-revalidated existing dataModel/artifacts/lifecycle/operation/record.py::OperationCancelled(operation_id, reason). Нового cancellation POJO/code/category нет. Carrier не содержит заявленный request fingerprint как якобы committed binding.

Public apply на PublicationTerminal сначала проверяет world/kind/preparation и existing publication_fingerprint, если он установлен. SnapshotApplyResult возвращается exact. OperationCancelled переносится SnapshotOperationCancelledError; другой terminal type для SNAPSHOT_APPLY — infrastructure corruption. Если отмена до publication binding, совпавший preparation подтверждает отмену operation, не выполнение какого-либо PatchSet. Claim/read не дописывает fingerprint ради replay.

asyncio.CancelledError обозначает отмену invocation; OutcomeUnknown — uncertainty transaction; SnapshotOperationCancelledError — сохранённый terminal. Эти три ветки не преобразуются друг в друга. Этот carrier дополняет public error roster, не расширяет SnapshotApplyOutcomeKind. DAG принимает существующий OperationCancelled POJO через declared control mapping, не field issue.

## R3. Core diagnostics и immutable-binding mismatch

### Existing reuse и необходимое изменение result

Section-owned FieldPathError subclasses и SnapshotMetadataCode/D1 остаются своими owners. Core cross-field/CAS причины нельзя выдавать за случайное поле. Existing SnapshotApplyResult.diagnostics допускает только FieldPathError; это не представляет typed model-level причины без фиктивного path.

**Proposal:** расширить diagnostics только в existing SnapshotApplyResult до `tuple[FieldPathError | SnapshotApplyRelationIssue, ...]`. SectionRefused **не менять**: domain handlers сохраняют свой existing contract; Snapshot добавляет core relation issues на своих фазах. Transport/terminal codec обязан сохранить concrete issue kind и поля, не string message. Existing field issues проходят без копирования/перекодирования.

Новые types в backend/app/dataModel/worldSnapshot/results/applyIssues.py:

- SnapshotApplyCode(StrEnum): OPERATION_BINDING_MISMATCH, UNSUPPORTED_REQUEST_FORMAT, SECTION_BINDING_MISMATCH, DEPENDENCY_MISMATCH, WORLD_EXPECTATION_MISMATCH, PLAYER_EXPECTATION_MISMATCH, GAMEPLAY_NOT_STARTED, ACTIVE_TIMELINE_MISMATCH, TURN_SEQUENCE_MISMATCH, ARTIFACT_UNAVAILABLE.
- SnapshotApplyRelationIssue: code: SnapshotApplyCode; section_key: SectionKey | None; player_uid: EntityUid | None; artifact: ArtifactRef | None. Все поля обязательны, strict/frozen/extra-forbid/revalidate-always. Нет FieldPathError/message/произвольного dict в этом POJO.

Условия полей: SECTION_BINDING_MISMATCH/DEPENDENCY_MISMATCH требуют section_key; PLAYER_EXPECTATION_MISMATCH требует player_uid; ARTIFACT_UNAVAILABLE требует artifact. У остальных все context fields None. Expected request уже имеется у caller; safe observed CAS trace остаётся internal diagnostic/log context, не копируется в generic result. Не добавлять mirrored WorldPublicationRef/heads в каждую issue. Структурно повреждённый ref/input остаётся INVALID_INPUT до IO, а повреждённый persisted chain — infrastructure, не ARTIFACT_UNAVAILABLE.

Codes используются только при доказанном предусловии фазы: gameplay/format/dependency/artifact business refusal → REJECTED; expected head/CAS → CONFLICT; active timeline/turn discrepancy относительно ожидаемого runtime base → CONFLICT. World/player checks идут до handlers. Если независимые section validations вернули разные категории, accepted REJECTED precedence сохраняется. Diagnostic order: общий phase order, sections input order, player expectations canonical order, producer order. Core code не заменяет уже имеющийся typed owner failure при совпадении ситуации; перед реализацией roster сверяется с current frozen domain enums.

### Typed mismatch вместо parsing ValueError

В backend/app/dataModel/publication/operationBindingMismatch.py proposed record `OperationBindingMismatch`:

```python
operation_id: EntityUid
requested_kind: OperationKind
requested_world_uid: EntityUid
requested_preparation_fingerprint: RevisionHex
requested_request_fingerprint: RevisionHex
stored_kind: OperationKind
stored_world_uid: EntityUid
stored_preparation_fingerprint: RevisionHex
stored_request_fingerprint: RevisionHex | None
```

Record strict/frozen/extra-forbid/revalidate-always; минимум одно реально сравниваемое значение различается. stored_request_fingerprint=None само по себе не mismatch: это existing unclaimed preparation. Не включать весь OperationRecord/terminal/holds как лишнюю копию. `OperationBindingMismatchError` в application/publication/errors.py содержит этот record, raised только в existing immutable comparison ветке claim_publication. Остальные ValueError не ловятся как mismatch; corrupt persisted state сохраняет infrastructure outcome.

WorldSnapshotService переводит только этот exact carrier в SnapshotApplyResult(REJECTED, operation_id, request_fingerprint **предъявленного** запроса, committed=None, diagnostics=(SnapshotApplyRelationIssue(OPERATION_BINDING_MISMATCH,...),)). Это preclaim отказ и **не записывается** в terminal исходной операции. Нельзя возвращать чужой terminal или перезаписать ledger. Для claimed body refusal действует existing record_refusal после rollback; два пути различаются фазой и evidence, не новой result category.

Persisted refusal после commit возвращается на exact retry. Preclaim mismatch result не обещает хранения; будущий DAG mapping не должен считать каждый REJECTED долговечным terminal. Unknown/Busy/cancellation остаются control/error carriers из public proposal. Эта семантика совпадает с accepted freeze «иной запрос с тем же ID — rejected без изменения исходной operation».

## Проверки, последствия и приёмка

R1 tests: X/Y replace без потери чужого closure, shared artifact, no-op, history-only artifact, world/player одного section_key, явный multi-owner usage, missing/extra/changed inherited binding, complete resultant closure vs delta. Two-connection проверки full public transfer и existing partial helper — разные сценарии. Старые holders истории остаются; leftovers не освобождаются.

R2 tests: early cancel без publication fingerprint, cancel после binding, mismatched preparation/request, cancellation invocation после подтверждённого commit, same terminal replay без handler calls. Нельзя конструировать fake FieldPathError для cancel.

R3 tests: exact typed mismatch vs unrelated ValueError; no terminal overwrite; all phase/category/context invariants; mixed field/relation diagnostics codec round-trip; invalid model не маскируется domain code; source/domain diagnostics сохраняют свои concrete types. Проверки typing/negative constructor/collector admission обязательны после реализации.

Требуемые изменения: R1 accepted receipt+metadata/layout; R2 новый public control carrier с existing outcome; R3 result diagnostic union, core issues и typed internal mismatch carrier. DDL/schema/code **не менялись**. Ни одна правка не утверждена наличием этого файла. Новые canonical IDs/format values требуют registry inventory перед freeze; runtime tests не запускались. Документ предъявляет контрактные решения и их последствия пользователю, не заявляет PASS реализации.

## Impact audit R1–R3 — 2026-11-14

Статус: static evidence и порядок будущего среза, не приёмка новых DTO. Пути ниже относительно корня репозитория. Publication/Artifacts storage здесь — внутренняя инфраструктура Snapshot; её исправления не передаются внешнему владельцу.

### Codec и storage

| Участок | Наблюдение в текущем коде | Последствие предложения |
|---|---|---|
| `backend/app/application/patch/encoding/coreManifest.py` | SectionApplyReceipt зарегистрирован как 20132 | R1 меняет canonical layout receipt. Новые retention records должны входить в dependency manifest receipt; нельзя зарегистрировать их только в Snapshot manifest, оставив самостоятельный PATCH_CORE_SCHEMA неполным |
| `backend/app/application/worldSnapshot/encoding/coreManifest.py` | WorldSnapshotMetadata=20133, PlayerSnapshotMetadata=20134 | R1 меняет обе persisted формы; исключить незаметное переиспользование старого layout |
| `backend/app/application/worldSnapshot/encoding/snapshotCodec.py` | SUPPORTED_VERSIONS={1}; encode/decode проверяют envelope_format_version | Новый layout требует явного решения о версии и IDs. Это не команда автоматически менять все wire versions на v2 |
| `backend/app/db/repositories/sqlite/snapshotCore/history/rowProjection.py` | metadata кодируется целиком; snapshot_data/checksum и envelope_format_version проецируются отдельно; read сверяет row/body | R1 требует нового codec и regression row/body/checksum. Разносить retention в отдельные SQL-колонки не требуется по текущему устройству |
| `backend/app/application/artifacts/encoding/coreManifest.py` | SnapshotApplyResult=20124, OperationCancelled=20127; этот manifest включён в Patch, затем Snapshot | R3 нельзя ограничить верхним Snapshot manifest: новый issue/enum должен быть доступен самостоятельному manifest результата. Проверить отсутствие циклического импорта. R2 повторно использует имеющийся cancellation record |
| `backend/app/db/repositories/sqlite/snapshotCore/operations/terminalCodec.py` | StoredTerminalCodec принимает только format_version=1, encode пишет 1; typed outcome кодируется canonical codec, row/body category сверяются | Расширение diagnostics должно пройти storage round-trip с concrete issue types. Версия terminal не обязана совпадать с envelope version; решение принимается отдельно. Не менять Pack/Gameplay/Cancelled formats автоматически |
| `backend/app/db/migrations/0001_initial.sql` | metadata и outcome уже хранятся BLOB; version columns допускают положительные значения | Новые таблицы/колонки для предложенных R1–R3 не обоснованы. Это вывод о просмотренной схеме, не доказательство совместимости существующих данных |

Числа выше — **занятые текущие IDs**, не распределение новых. Полного global ID/reservation audit в этом проходе нет. До codec freeze нужны точные новые IDs, версии receipt/envelope/result и политика отказа старой формы. Нельзя молча добавлять dual decoder, миграцию, очищать пользовательскую БД или обещать чтение прежних snapshots. При необходимости сохранять читаемость существующих данных требуется отдельное решение пользователя до зависимого кода.

### Ответственности затронутой реализации

- `backend/app/dataModel/worldSnapshot/sections/retention.py` (новый): только strict state/history closure records; без IO и вычисления чужого domain closure. Отказ — malformed/duplicate binding.
- `backend/app/application/worldSnapshot/service/snapshotMetadataBuilder.py`: объединение pinned parent states с новыми owner+section bindings, сохранение независимых диагностик. Не становится writer/transaction owner.
- `backend/app/application/worldSnapshot/validation/receiptProvenance.py`: проверка соответствия receipt, parent и metadata; необходимо заменить проверки плоских refs/retention. History store продолжает вызывать её перед insert.
- `backend/app/application/worldSnapshot/service/acceptedStateReader.py`: потребитель metadata refs; должен читать refs через новые retention records. Не вводить compatibility properties для старых полей.
- `backend/app/application/worldSnapshot/service/worldSnapshotService.py`: orchestration внутри Snapshot, вычисление назначений holders из полного closure и явная политика transferred. Public entry только из DAG; handler не получает право прямой записи Snapshot.
- `backend/app/db/repositories/sqlite/snapshotCore/history/snapshotHistoryStore.py`: strict validation, provenance и append в переданном scope. Собственного commit при append не появляется.
- `backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py`: typed immutable-binding mismatch вместо одной конкретной ValueError-ветки. Не переводить все ValueError в business refusal; не менять separate record_refusal transaction.
- R2 carrier и R3 error mapping находятся в application; canonical DTO — в dataModel. Exception не сохраняется в terminal BLOB. Для typed mismatch не нужна новая SQL-запись.

### Логи и caller result

`backend/app/dataModel/worldSnapshot/events.py::SnapshotLogRecord` содержит activity/binding/outcome, но не diagnostics. Поэтому R3 не требует добавлять в него копию diagnostics. Existing `backend/app/application/worldSnapshot/logging/snapshotLog.py` остаётся sink; наличие REJECTED event не доказывает запись terminal: preclaim mismatch возвращается без изменения исходной операции.

В текущем enum нет отдельного cancellation activity. R2 не даёт права логировать сохранённую отмену как APPLY_COMMITTED или как asyncio cancellation. Решение о самостоятельном audit event отмены не принято этим предложением; не добавлять новый enum/ID скрытно. Существующий terminal replay и caller carrier проверяются независимо от доставки логов.

### Последовательность будущего implementation-среза

1. Пользователь принимает R1 closure/transfer, R2 carrier, R3 diagnostic/result change и текущую encoding-таблицу. Решение не поддерживать legacy уже принято; повторно его не запрашивать. До приёмки оставшихся контрактов зависимого codec кода нет.
2. Обновить strict модели, dependency manifests и codecs вместе с round-trip/negative tests. Не оставлять промежуточный runtime, где новые модели пишутся старым codec.
3. Перевести builder, provenance, accepted-state reader и history tests на новый closure. Сохранить scoped D1 admitted и порядок world → players → builder, включая malformed input и missing persisted base.
4. Перевести handoff внутри прежнего outer transaction. Existing partial-helper scenario и proposed full public transfer — разные assertions, не замена одного другим. До commit второе соединение не видит публикацию; после commit видит точные holders; rollback сохраняет исходные holds.
5. В согласованном public apply срезе подключить typed mismatch/cancel mapping и terminal codec. Сохранить порядок claim → outer checks/handlers → metadata/handoff → world/player CAS → terminal → commit; refusal записывается только после подтверждённого rollback. Не начинать terminal/retry recovery или Time T5 в рамках этого audit.
6. После адресных regressions выполнить typing и полный snapshotCore. DAG nodes и production wiring — отдельный принятый этап.

### Проверки будущей реализации и пределы evidence

Существующие точки regression: `backend/tests/snapshotCore/contracts/test_models.py`, `test_codec.py`, `test_registry.py`; `backend/tests/snapshotCore/storage/publication/test_history.py`, `test_cas.py`, `test_atomicity.py`; fixtures в `backend/tests/snapshotCore/support/`. В atomicity уже есть `test_metadata_handoff_and_heads_share_outer_transaction` и malformed receipt assertions с исходными индексами — их семантику нельзя потерять при переименовании полей. Проверить также читателя в `test_accepted_state_reader.py`.

Команды будущего среза из `backend` с Python проекта:

```text
python -m unittest tests.snapshotCore.contracts.test_models tests.snapshotCore.contracts.test_codec tests.snapshotCore.contracts.test_registry
python -m unittest tests.snapshotCore.storage.publication.test_history tests.snapshotCore.storage.publication.test_cas tests.snapshotCore.storage.publication.test_atomicity tests.snapshotCore.storage.publication.test_accepted_state_reader
python -m unittest tests.snapshotCore.contracts.test_typing
python -m unittest discover -s tests/snapshotCore -t .
```

Typing gate использует установленный `node_modules/pyright/index.js`, positive/negative configs в `backend/tests/typing/snapshotCore/`; negative diagnostics сверяются с EXPECT, а не просто с ненулевым exit code. Будущие test fixtures хранить в tests, не в корне проекта.

В этом проходе выполнены только чтение файлов и `rg` по codec/storage/consumers/tests. Runtime, typing и crash/GC tests **не запускались**; команды выше — программа проверки, не результаты. Изменён только этот документ, устранена противоречивая фраза о расширении SectionRefused: он остаётся неизменным. Чужие рабочие изменения сохранены.
