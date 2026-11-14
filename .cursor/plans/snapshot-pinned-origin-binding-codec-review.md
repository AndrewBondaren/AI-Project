# Snapshot pinned-origin binding / codec: independent review

2026-11-15. **CHANGES REQUIRED**. Scope: семь файлов из запроса, owning storage/codec §11–12 и pinned contract r2. Production и тесты не изменялись.

## Finding BIND-1 — P2: malformed sibling подавляет доступные relation diagnostics

Место: `backend/app/application/publication/validation/preparationSourceBindingValidator.py:17` (вызов из codec: `preparationSourceBindingCodec.py:11`).

Контрпример, воспроизведённый отдельным read-only Python запуском:

```python
v = binding()  # tests.snapshotCore.contracts.test_preparation_source_binding
v = v.model_copy(update={
    "target": v.target.model_copy(update={"world_uid": "foreign"}),
    "sources": (None,),
})
PreparationSourceBindingValidator().validate(v)
```

Фактически: `ValidationError`, единственная диагностика `model_type` по `('sources', 0)`. Проверки world не выполняются. Между тем target, request и origin.pin структурно пригодны: обе world relations нарушены независимо от sources.

Ожидается по требованию implement-plan об агрегации и пункту 2 текущего задания: сохранить structural ошибку sources[0] и доступные WORLD_MISMATCH по request.world_uid и origin.pin.world_uid; пропустить только зависимую проверку malformed source. Исходные индексы сохраняются. Нужен regression с одновременно malformed sibling и доступными relation violations.

**Контрактная оговорка:** реализация буквально соответствует принятой shape-first формулировке §11. Это не самовольное отклонение исполнителя от §11, а незакрытый конфликт этой границы с обязательной агрегацией независимых ошибок. Нельзя молча исправить код новым несогласованным carrier: необходимо согласовать способ совместной доставки structural и relation причин либо явное исключение для этой boundary. До разрешения конфликта полную приёмку не выдаю. Существующий tuple[Issue, ...] описывает только relation ошибки, structural канал — Pydantic ValidationError.

## Подтверждённое поведение и границы

- Новые origin/binding strict, frozen, extra-forbid, revalidate-always; поля обязательны без defaults. Вложенные Artifact/Pack/Source POJO переиспользуются, не копируются. Existing defaults ArtifactRef/holders не являются новыми defaults binding.
- Exact admitted aggregation roster — конкретный PreparationSourceBindingFieldIssue; три enum codes, carrier code/path/message. Для shape-valid values порядок: request world, origin pin world, затем duplicate и holder каждого source. CheckedPath/FieldRef сохраняют исходный индекс. Full ArtifactRef equality используется для duplicates и manifest identity.
- Root требует PinHolder с точным pin_id; child требует ArtifactRetentionHolder с точным manifest. Operation/Snapshot holders не разрешаются relation validator. Empty sources допустимы без обещания coverage. Нет IO, actual hold checks, grant issuance или проверки текущего lease.
- Encode вызывает validator до canonical encode; decode — strict canonical decode, затем validator. Relation failures обеих сторон сохраняют tuple concrete issues в CanonicalEncodingError.args[0], включая codes/paths. Structural encode использует ValidationError; structural decode — canonical exception с cause. Эти каналы не следует объявлять одним унифицированным typed relation result.
- IDs 20308/20309/20310 имеют exact enum/record owners и kinds. Локальный поиск backend/app не нашёл альтернативных registrations этих ID. Composition повторно использует Source request export, Pack pin export и 13 Artifact entries из owning §7; Snapshot refs и все holders нужны полному annotation union, даже если relation validator запрещает часть holders. Runtime authority/errors и terminal roster не добавлены. Exact owner lookup требует единственности; общий merge проверяет conflicts.
- Fixed-layout vector независим от production encoder и model reflection: TLV построен явно и использует accepted REQUEST_V0_HEX. Round-trip и projection проверены. В новых codec tests есть unknown ID, wrong root, truncation/trailing bytes. Отдельные ручные probes подтвердили отказ перестановки root field names, неизвестного nested pin field и nonminimal nested integer. Это не исчерпывающий fuzzing malformed nested values. Постоянного binding-specific теста перестановки полей в новых файлах нет.
- Source/Pack golden regressions прошли. Не утверждается неизменность всех возможных bytes только по этим векторам; Source имеет собственные незавершённые изменения в рабочем дереве.

## DAG, ответственность, порядок

Owning §3/§7/§11–12 и r2 §3–4 задают pure internal slice. Модели хранят historical values; Issue хранит field diagnostic; validator проверяет relations; manifest описывает immutable type roster; codec кодирует values. Отказ в приёмке для этих ролей: IO/authority в value/validator/codec, mirror чужого DTO, coercion/fallback, скрытая orchestration. Такие нарушения в просмотренных файлах не найдены, кроме error aggregation gap BIND-1.

Цепочка codec → validator → shared canonical implementation не выбирает самостоятельные domain operations, не запускает pipeline через callback/worker и не вызывает чужие публичные CRUD. Использование чужих POJO/manifest exports не является междоменной orchestration. Поиск ссылок в backend/app обнаружил только новые модели/diagnostics/validator/codec/manifest; runtime caller этим срезом не поставлен. Три запрета DAG для этого pure slice соблюдены; это не приёмка будущего runtime маршрута.

Публичные data/settings C/R/U/D не добавлены (каждая из восьми операций вне дельты). Нет новых междоменных reads/writes для CRUD-протокола. Источник порядка — r2 §4 и owning §7, затем §11–12: prerequisites → value validation → encoding; store/ledger остаётся следующим отдельным слоем. DTO не дублируют Source proof, Pack pin или runtime authority fault; relation Issue не заменяет actual-hold/coverage faults. Полный Snapshot domain, storage, terminal/retry, Time и runtime wiring не принимаются этим отчётом.

## Команды и evidence

Из backend:

1. `.venv/Scripts/python.exe -B -m unittest tests.snapshotCore.contracts.test_preparation_source_binding tests.snapshotCore.contracts.test_preparation_source_codec tests.snapshotCore.contracts.test_codec tests.sourceVersioning.test_request_canonical` — **27 OK**, 0.127s.
2. `.venv/Scripts/python.exe -B -m unittest tests.sourceVersioning.test_canonical tests.spatial_pack.test_pin_canonical_registration` — **11 OK**, 0.689s.
3. `.venv/Scripts/python.exe -B -m unittest discover -s tests/snapshotCore -t .` — sandbox попытка: **190 tests, 100 errors**, 3.734s; PermissionError при создании tests/.tmp_snapshot_core каталогов. Это environment failure, не 100 доказанных production дефектов. Повтор с доступом к временным файлам: **190 tests, OK (skipped=1), 154.411s**, exit 0. Fixed-layout test включён в текущий полный suite.

Из корня: `node node_modules/pyright/index.js backend/app/dataModel/publication/preparationSourceAuthority.py backend/app/dataModel/publication/preparationSourceBindingIssue.py backend/app/application/publication/validation/preparationSourceBindingValidator.py backend/app/application/publication/encoding/preparationSourceManifest.py backend/app/application/publication/encoding/preparationSourceBindingCodec.py` — **0 errors, 0 warnings**.

`git status --short` и `git diff HEAD --` с семью путями выполнены после повторения чтения вне ограничивавшего git sandbox. Все семь файлов новые untracked, поэтому tracked diff для них пуст; проверено их полное содержимое. Чужие изменения сохранены. Read-only reproducer BIND-1 дал ровно `[('model_type', ('sources', 0))]`.
