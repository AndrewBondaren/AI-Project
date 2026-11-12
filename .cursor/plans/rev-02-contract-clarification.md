# REV-02 — адресное уточнение контрактов, 2026-11-12

Приложение к [основному плану](world-pack-v2-single-manifest-contract.md). Статус: NOT ACCEPTED. Статическая сверка документов и отдельных реализаций; полнота аудита writers/callers не доказана, runtime/race/restart проверки не выполнялись. Сообщения владельцам не отправлялись. Existing ниже означает найденную реализацию, accepted — явно записанное решение пользователя, proposed — проект без приёмки.

## Граница блокеров Pack/Cache

Актуальная [классификация блокеров](world-pack-v2-single-manifest-contract.md#блокеры-pack-и-независимость-cache--фиксация-2026-11-12) отделяет собственные schema/read/activation/release/config задачи Pack от внешних Source/producer/Artifacts контрактов и интеграции DAG. OPEN R1–R5 не означает запрета независимых принятых срезов Pack и не блокирует домен Cache. Для Cache остаются перенос callers (шаг 5) и последующее удаление V1 (шаг 6); отдельные проверки Pack/Climate сохраняются в шаге 7. Отсутствие конкретного поля/port блокирует зависимую операцию, а отсутствие миграции callers — приёмку маршрута. Новые ноды и чужая разработка не включаются в scope Pack.

## Ответы и решения по замечаниям

Все пути backend ниже относительно корня репозитория; номера строк относятся к сверке на указанную дату.

| Замечание | Подтверждённый ответ и источник | Mapping и решение |
|---|---|---|
| R1 — OPEN | Accepted: immutable source bodies через Artifacts; object revision и membership revision различаются, capture не назначает seq (`world-source-versioning.md:221–229`). Proposed: SourceCapture/SourceDependencySet (`source-proof-v2-contract-spec.md:37–67`), producer outcome и persisted proof (`:83–95`) | object identity + revision + body ref должны попадать в capture и зависимости результата; address + exact ArtifactRef либо metadata projection должны быть связаны с этим результатом. Изменение состава кандидатов меняет collection dependency даже при прежнем выбранном body. Concrete producer receipt/coverage и codecs не подтверждены: отклонена приёмка всей цепочки Source → producer → Pack. |
| R2 — OPEN | Existing: `IArtifactHolders.acquire(ref: ArtifactRef, holder: ArtifactHolderRef) -> None`, `holderPort.py:12`; concrete `SqliteArtifactHolders.acquire`, `holderStore.py:185–207`, не принимает source holder. `handoff(scope: CommitScope, lease: OperationLeaseRef, snapshots: tuple[SnapshotRef, ...], retained_refs: tuple[ArtifactRef, ...]) -> None`, `:228–241`, требует APPLYING. Пути: `backend/app/application/artifacts/contracts/`, `backend/app/db/repositories/sqlite/artifacts/` | ArtifactRef + target holder недостаточно для source-owner → writable preparing lease + membership. Existing handoff не принимается как preparing adoption. Sealed owner требуется для ArtifactRetentionHolder (`holderStore.py:200–202`); revision SQL row не становится holder. Durable root и release lifecycle до Pack/Snapshot остаются OPEN. |
| R3 — OPEN | Existing: `backend/app/dataModel/worldPack/activation/input.py:8–14`, `PackActivationInput.from_candidate(candidate: PreparedPackCandidate, expected: WorldPublicationRef) -> Self`; сохраняет operation_id, manifest, preparation_fingerprint и полный expected. Public prepare/activate — проект `docs/tz_world_pack_storage.md:250–258`; Source CRUD — проект appendix §4 | Тройка candidate + полный expected совместимы на уровне POJO. Это не доказательство concrete public activate, release или CRUD настроек. Не принимаются отсутствующие классы/методы по одному Protocol либо описанию семантики. |
| R4 — OPEN | `source-proof-v2-contract-spec.md:97–110` прямо оставляет роли вместо полного roster; §3 оставляет owning descriptors и identity keys открытыми, §4 содержит проект field/logic diagnostics | Нельзя доказать отсутствие дублей Source/Planning/Pack POJO и ошибок без полей и concrete модулей. Классификация всех writers INCLUDE/EXCLUDE/DERIVED не доказана (§1). Приёмка классов и POJO отклонена по недостаточности сведений, а не по доказанному наличию дубля. |
| R5 — OPEN | Existing: `backend/app/application/worldData/pack/encoding/packManifestCodec.py:30–44`, `decode_manifest(payload: bytes) -> WorldPackManifest`, принимает V1 и преобразует V2 в legacy модель. `manifestFormat.py:11–28`, `manifest_format(max_bytes: int) -> ArtifactFormatContract[bytes]`, проверяет budget/version и возвращает исходные bytes. `backend/app/dataModel/worldPack/meta/worldPackManifest.py:91,213`: общие прежние поля и V2 subclass | Existing binding не равен целевому единственному decoder полной схемы parts/assembly/provenance. Registry hash, z band, wilderness total, exact wire version и полный payload/closure roster остаются OPEN. Сохраняются принятые pack_version/codec_version/payload_format; не менять ТЗ для устранения расхождения. |

Закрытый подвыбор (CLOSED): носитель immutable source bodies — Artifacts, без повторного вопроса. Ни одно R1…R5 целиком не закрыто.

## R1 — последовательный разбор, решение ещё не принято

Дополнительно проверены реальные результаты producers:

- `backend/app/dataModel/worldPack/bake/packTilePlan.py::PackTilePlan` возвращает scope, tiles, capped, cap_applied; capture, source revisions и proof происхождения результата отсутствуют. `PackTilePlanner.plan` в `application/worldData/pack/bake/plan/packTilePlanner.py:31` не закрывает этот разрыв.
- `backend/app/application/worldData/pack/refine/fine/fineRefineResult.py::FineRefineResult` содержит persist counts, wilderness_chunks_written, rect_count, fine_surface_z, grade results и timings. Точных ArtifactRef и адресованного completed coverage нет; `FineChunkRunner.refine_rects` (`chunk/fineChunkRunner.py:48`) не позволяет восстановить их из счётчиков.
- `backend/app/application/worldData/settlementOutdoor/settlementOutdoorContract.py::TopologyResult/MaterializeResult` содержат status и counts, но не полный census/packed UID set и не structure ArtifactRef. Публичные методы существующего orchestrator (`settlementOutdoorOrchestrator.py:113,121`) нельзя объявить готовыми V2 producers.
- `backend/app/dataModel/planning/identity/planRef.py::PlanRef` содержит key/output_fingerprint; `planning/contracts/planDependency.py::PlanDependency` — slot/ref. Это зависимости плана, не свидетельство получения конкретного payload из capture.
- `backend/app/dataModel/engine/dag/invocations/record.py:40::CompletedOutcome` содержит result_json. Сам по себе terminal DAG не является typed materialization receipt и не задаёт retention source bodies.

Следовательно, R1 не устраняется переименованием существующего результата или конвертацией counts. Конкретные SourceCapture/SourceDependencySet/PackStoredProvenance в backend поиском не найдены; их объявления в appendix остаются проектом.

**Развилка для согласования:** основной план § «Единственный сохраняемый агрегат» требует `PackStoredProvenance.source_proof` владельца Source, а Source appendix §6 предлагает непосредственно dependencies/planning/source_bodies. Это разные схемы, ни одну нельзя молча принять как уточнение другой.

Предложение для обсуждения: сохранить Source-owned durable proof о точных object/collection revisions и телах; отдельно producer-owned evidence связывает этот proof и Planning dependencies с точным результатом (address/ref либо metadata projection) и coverage. Pack хранит связь результата с durable provenance; transient lease/receipt проверки не становятся обязательной runtime-зависимостью читателя. DAG передаёт готовые результаты, не вычисляет proof. Это пока распределение ответственности, не утверждённые сигнатуры или новая схема.

Пользователь согласовал это разделение ответственности 2026-11-12. Предложение выше принято как основа конкретизации, но не как готовые сигнатуры или wire schema. R1 остаётся OPEN: нужны concrete types/codecs, mapping и admission проверки. R2 не рассматривается в этом последовательном проходе.

### Сверка с Snapshot

Разделение совместимо с `docs/tz_world_snapshot.md:28–54,69–93,365–397`: домены готовят данные, DAG собирает PatchSet, после gameplay только Snapshot валидирует/применяет секции и атомарно публикует metadata, refs, holds и terminal. Source proof не предоставляет право отдельного commit; producer evidence не заменяет Snapshot validation. До gameplay публикация принадлежит Pack; после gameplay базовый Pack заморожен. Snapshot сохраняет данные планирования мутации и уже имеющийся результат; один PlanRef без доступных данных не доказывает выполнение этого требования.

Existing `application/worldSnapshot/validation/receiptProvenance.py::validate_receipt_provenance` проверяет SectionApplyReceipt относительно operation, assigned snapshot и pinned parent. Это receipt применения секции, не producer receipt материализации; он не заменяет Source proof. `application/worldSnapshot/contracts/applyPort.py::IWorldSnapshotApply.apply(PatchSet) -> SnapshotApplyResult` сохраняет owning границу.

**Решение пользователя 2026-11-12 — семантическое расхождение разрешено.** Правило PC-0 в `tz_world_snapshot.md:1150–1151` о перепроверке latest source projection перед публикацией относится только к прежнему пути. Для новой модели действует freeze in-flight из `world-source-versioning.md:316–352`: операция завершается по закреплённым object/collection revisions. При публикации проверяются связь результата с этим captured set, доступность и удержание необходимых тел, а также полный expected publication через CAS. Последующее изменение latest само по себе не отменяет результат и не запускает повторный bake. Несовпадение expected publication сохраняет owning conflict/READY_INACTIVE semantics; решение не разрешает обход CAS или Snapshot-only commit после gameplay.

Статус этого выбора — ACCEPTED; concrete scoped bindings и проверки остаются OPEN в R1/R2. Это не приёмка реализации. Owning ТЗ в рамках этой команды не редактировалось; при его синхронизации требуется явно перенести указанную границу применимости PC-0, сохранив гарантии legacy до cutover.

### R1 — следующий шов: чем подтверждается producer evidence

Проверены `backend/app/dataModel/artifacts/references.py::ArtifactRef` (kind, format_key, format_version, content_hash, nbytes, row_count), `application/artifacts/contracts/stagingPort.py` и `dataModel/artifacts/lifecycle/operation/record.py`. Identity bytes и preparation fingerprint не объявляют конкретных source dependencies/coverage результата. `application/worldData/pack/encoding/stagedClimateFields.py::StagedClimateFields.validate` проверяет seal/operation hold, читает verified bytes и сверяет coarse/fine/origin. Это полезная existing проверка address → payload, но не проверка происхождения из capture.

`dataModel/patch/results/sectionResult.py::SectionApplyReceipt` содержит section_key, history_refs, state_refs, changed и retained_artifacts. Его назначение — результат apply, он не утверждает durable commit и не является receipt producer. Расширять его ради materialization evidence без отдельного решения нельзя.

Отсюда требуется различать два утверждения: «переданный proof структурно согласован с ref» и «этот ref действительно зарегистрирован как результат данной подготовки producer». Свободно собранный caller POJO доказывает только первое. Seal произвольного JSON также сам по себе не доказывает второе.

**Коррекция после проверки DAG, 2026-11-12:** предложение отдельного producer result artifact отозвано как необоснованное. Запрос нового решения пользователю снят. Отсутствие proof в ArtifactRef не доказывает необходимость дополнительного storage object.

Existing механизм передачи результата:

- `docs/tz_engine_node_context.md:24–35` требует переиспользовать Output нод, разрешает хранить малые результаты непосредственно и использовать ссылки для больших. Вторую иерархию копий вводить не следует.
- `backend/app/dataModel/engine/dag/records.py::OutputRecord` связывает immutable typed output с ExecutionIdentity, contract_id/version, DependencyRead и DomainReadEvidence. DependencyRead проверяет принадлежность result производителю; OutputRecord проверяет execution и наличие обязательных reads.
- `backend/app/application/engine/runtime/dag/context/dagContext.py:187,218,275` публикует результат после проверки открытой попытки, зарегистрированного контракта/типа и прочитанных зависимостей. Это существующая инфраструктура происхождения результата в DAG, а не Source proof.
- `backend/app/application/engine/runtime/invocations/sessionFrame.py::SessionFrame.capture/restore` сериализует output вместе с identity/reads и восстанавливает его через зарегистрированный тип. `runtime/dag/lifecycle/executionSnapshotService.py::encode/decode/restore` использует этот формат и вызывает lifecycle.validate_restored для доменных ссылок. Наличие сериализации не доказывает durable сохранение конкретного bake или удержание его artifacts.

Дальнейшая конкретизация R1 должна сначала сопоставить typed доменный outcome producer с этим существующим Output/DependencyRead путём и входом Pack. Source proof, точные refs/адреса и coverage остаются содержимым доменного результата; engine не вычисляет их и не доказывает правильность алгоритма. Engine OutputRecord не переносится в публичный Pack DTO или manifest. Конкретные producer/Pack bindings и domain validation ещё OPEN; новых нод не назначено. Durable provenance готовой версии сохраняется в единственном manifest и не зависит от session frame при чтении payload.

Отдельный outcome artifact, новый ledger и новый lifecycle не являются требованиями R1. Их можно обсуждать только при доказанном ограничении существующего механизма, которого текущая проверка не установила.

### R1 — проверка достаточности существующего пути

Статическая трассировка 2026-11-12: `PublishedDAGReadView.require/_read` (`backend/app/application/engine/runtime/dag/context/dagReadView.py:57–103`) проверяет объявленный producer/type, execution identity и contract version, возвращает именно record.output и фиксирует DependencyRead. `NodeRunner.run_resumable` (`runtime/execution/nodeRunner.py:44–70`) валидирует prepared input/output и возвращает reads в StepEffect; `ContractValidator.validate` (`runtime/validation/contractValidator.py:75`) проверяет declared model, immutable tree и existing models. `DAGContext._validate_publication/_check_reads` (`runtime/dag/context/dagContext.py:218,275`) проверяет попытку, контракт и актуальность прочитанных результатов.

**Граница доказанного:** транспорт typed outcome уже есть. DependencyRead подтверждает факт чтения конкретного результата, но не доказывает, что prepare_input правильно перенёс каждое его поле: он не содержит field mapping, а NodeRunner допускает explicit/prepared input. Поэтому «DAG уже гарантирует весь R1» неверно. Для конкретного маршрута надо предъявить mapping producer outcome → Pack request, проверить сохранение ref/address/proof и отсутствие подстановки внешних значений. Это проверка binding и domain admission, а не основание добавлять отдельный outcome artifact. Engine record не становится доменным proof и не передаётся в manifest.

| Данные | Кто формирует / проверяет | Mapping в Pack и оставшаяся проверка |
|---|---|---|
| Object/collection revisions и source bodies | Source; existing общий concrete capture не найден | Capture подготовки и durable source_proof; точные типы/codecs OPEN |
| Address + exact ArtifactRef + Source proof + PlanDependency | Producer возвращает одним связанным typed результатом; DAG передаёт | PackPartInput и stored provenance; нельзя собрать ref одного outcome с proof другого. Concrete outcome и binding OPEN |
| Expected/completed coverage и policy | Producer, по captured scope/grid; expected не выводится из completed | Pack проверяет уникальность, completed ⊆ expected, соответствие outputs итоговым parts; complete требует полного покрытия. Counts не заменяют множества |
| Обработанная область без payload | Producer, отдельный typed вариант из проекта ТЗ | Pack проверяет evidence without_payload; отсутствие wilderness blob само по себе не означает необработанную область и не разрешает удалить базовую часть |
| Settlement census/packed set | Topology/materialization owners | Pack сверяет UID sets и реальный structure payload; число districts не является census |
| Inherited часть | Pinned base, а не текущий producer/capture | Сохраняются прежние address/ref/proof; Pack проверяет scope и допустимость нового полного состава |

Ограничения coverage уже заданы в `docs/tz_world_pack_storage.md:398–415`; новый выбор политики или носителя для них не нужен. Конкретные PackPreparationInput/PackPartInput/SourceCapture/SourceDependencySet и публичный PackPreparationPipelineOpenPipeline поиском в backend/app не найдены; вызов полного prepare из engine/composition также не найден. Existing `application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation` получает прежний manifest/other_members, проверяет lease, climate, staged bytes и READY live-set; Source proof и полное coverage этим helper не проверяются.

Итог: дополнительное решение пользователя о новом хранилище не требуется. R1 остаётся OPEN по отсутствию конкретных доменных контрактов и проверенного mapping, а не по отсутствию общей транспортной инфраструктуры. Проверки substitution, equal counts/different addresses, missing part, out-of-scope change и inherited proof должны опираться на реальные producer outputs при реализации; здесь runtime тесты не запускались. Последующая работа — конкретизация этих контрактов в согласованных границах; к R2 этот проход не переходил.

### Уточняющий трейсинг source proof после вопроса пользователя

Последнее утверждение о внешнем proof было сформулировано до полного прохода соответствующей цепочки. Теперь отдельно проверены:

1. `application/worldData/planning/composition/surfacePlanningCapture.py:72–113`: `_revision` вычисляет StateViewRevision из canonical projection входов; `SurfacePlanningCapture.capture` возвращает SurfacePlanningView. Это реальные immutable captured values и fingerprint, не seq/object/collection revision index и не удерживаемые body ArtifactRefs.
2. `application/worldData/planning/guards/sourcePublication.py::SourcePublicationGuard.require_fresh`: повторно читает World/locations, вызывает capture и `require_current_source`; `guards/sourceRevision.py` сравнивает world_uid/revision. Caller найден: `application/worldData/pack/bake/finalize/packBakePublisher.py::publish`, внутри transaction_if_needed, затем recalc/finalize. Это действующая legacy freshness-проверка, не accepted freeze-in-flight binding новой схемы.
3. `application/worldData/planning/contracts/surfacePlanBundle.py::SurfacePlanBundle.coherent`: проверяет exact PlanEnvelope dependencies и world/scope/contract. `application/worldData/generators/terrain/relief/planning/river/publication.py:30–75::NativeRiverReliefPublicationJob.publish` действительно проверяет source-bound inputs, expected PlanRefs, input/output fingerprints и water identities. Поэтому говорить «proof в коде вообще нет» неверно. Эти проверки относятся к Planning результату и не дают durable исходные object/collection revisions с body retention для Pack.
4. `application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation` → encode/stage/finish_preparation → PreparedPackCandidate: существующий helper подтверждает bytes и live-set, но не принимает Source proof. Current WorldPackManifestV2 и decoder не содержат целевых parts/provenance. Следовательно, передача durable Source proof в сохраняемый manifest по этой цепочке не найдена.
5. Owning требование установлено `docs/tz_world_pack_storage.md:248,334–337,501`: capture-finalize, source pins и durable proof владельца Source. `source-proof-v2-contract-spec.md:37–67` содержит проект SourceRevision/SourceCapture, а не существующую реализацию. Поиск имён SourceRevision/SourceCapture/SourceDependencySet/SourceDurableProof и source_proof в backend/app не обнаружил соответствующих объявлений/полей; вывод основан также на проверке ближайших существующих альтернатив выше, не только на отсутствии имени.

Вывод ограничен проверенными путями: существующие projection/fingerprints и Planning proofs переиспользуются по их назначению. Не найден полный binding exact source revisions + retained bodies → producer → Pack persisted provenance, требуемый owning контрактом. Это внешний контрактный пробел Source в составе полного schema gate Pack, а не необходимость нового proof storage, нового домена или переделки всей существующей системы. Полнота всех возможных внешних consumers этим аудитом не заявляется. Новый выбор пользователя не требуется; сначала конкретизировать missing binding с переиспользованием найденных механизмов.

## Черновики запросов владельцам — не готовы к передаче

**Source (R1/R3/R4).** Просьба предъявить concrete публичные классы и полные сигнатуры exact read/capture, Input/Output/field-error/logic-error с модулями и полями; owning typed object/settings/collection identities, semantic projection/authored-presence и codecs. Покажите CRUD mapping существующих владельцев на expected revision, эффекты, scope, replay и DoD без центрального Source CRUD-фасада. Уточните единый mutation/capture boundary, revision publication index mapping, staging lifecycle и durable root до Pack/Snapshot: как совместно откатываются body/index/holds/receipts и как exact read работает после restart и удаления latest? Завершите roster writers от repositories/raw SQL назад к callers с INCLUDE/EXCLUDE/DERIVED, включая repair/import/bulk, и concrete roster классов/POJO/ошибок с проверкой отсутствия дублей.

**Producer/materialization (R1).** Просьба предъявить конкретный outcome/receipt, связывающий logical address, exact ArtifactRef либо typed metadata projection, capture и существующие PlanRef/PlanDependency. Какие typed expected/completed coverage и policy evidence отвергают равные counts при разных адресах, подмену ref, missing part и изменение вне scope? Дайте mapping полей через DAG в PackPartInput/assembly provenance; отдельно persisted proof и transient admission evidence, проверки и ошибки. Planning POJO не дублировать.

**Artifacts и publication infrastructure (R2).** Просьба предъявить принятый preparing adoption binding: concrete class/method, полную сигнатуру, typed success/errors, source holder, sealed ref, writable target lease и membership; атомарную защиту от release/GC, replay/conflict/cancel/rollback. Existing acquire и APPLYING handoff этого ответа не заменяют. Уточните допустимый durable source retention root и его собственное удержание/release до Pack/Snapshot. Для Pack.activate предъявите конкретную связку scope + full expected CAS + terminal, recovery unknown outcome и replay после потери ответа. Публичный activate остаётся Pack-owned, второй holder store и новый OperationKind без решения владельца не вводятся.

**Pack (R3/R5).** Просьба зафиксировать конечные address/assembly/provenance schemas, registry_hash/z_band/wilderness_tiles_total, exact wire/storage pair, все payload read/format/closure bindings и concrete activate/release. Дайте отдельно четыре операции C/R/U/D данных и четыре операции настроек с конкретными классами, сигнатурами и POJO ошибок. Read готового payload не должен требовать live Source CRUD. Сохранение pack_version/codec_version/payload_format уже принято.

## Обязательная приёмка

Источник критериев: `.cursor/rules/dag-generator-interface.mdc:10–35,84–124`.

| Критерий | Результат |
|---|---|
| Три запрета DAG: выбор маршрута pipeline, скрытая оркестрация, прямые междоменные вызовы | OPEN: concrete согласованные bindings всей цепочки не предъявлены. Ноды не придумываются; прямой вызов Source/producer из Pack не предлагается. |
| Каждый класс: ответственность, зависимости, эффекты, acceptance/rejection | OPEN R4: таблица ролей не полный concrete roster. |
| Публичный контракт / открытый pipeline / internals, вложенные вызовы | OPEN R1–R3: proposed wrappers и internal binding не подтверждают реализованный маршрут. |
| Утверждённый порядок | Сохранён: источники → evidence → manifest → codec/readers. Незакрытый предыдущий gate не обходится. |
| CRUD данных и настроек, все восемь операций | OPEN R3; семантика immutable update/delete не освобождает от конкретных публичных контрактов. |
| Owner method → POJO → consumer fields → DAG | Частичное соответствие candidate → activation подтверждено; Source/producer mapping и DAG OPEN. Доменный контракт может приниматься отдельно после достаточного доказательства. |
| POJO и field/logic errors, отсутствие пересечений | OPEN R4; полнота сравнения не доказана, исключения не выдавались. |

Приёмка зависимого плана отклонена. Для дальнейшего уточнения пользователь должен получить ответы указанных владельцев; текст предложения не считается их согласием. Это приложение не разрешает runtime/SQL/DAG реализацию и не закрывает полный аудит остальных owning документов и callers.
