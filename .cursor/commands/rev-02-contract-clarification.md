# REV-02 — уточнение контрактов у владельцев

Выполни техническое уточнение REV-02, без runtime/SQL/DAG правок. Это команда подготовки контрактных решений, не разрешение реализации. Не отправляй сообщения другим людям или чатам автоматически: подготовь адресные запросы и зафиксируй подтверждённые ответы из доступных источников.

Прочитай основной план `.cursor/plans/world-pack-v2-single-manifest-contract.md`, замечания REV-02-R1…R5, `pack-v2-domain-contract-spec.md`, `source-proof-v2-contract-spec.md`, `world-source-versioning.md` в той же папке, `docs/tz_world_pack_storage.md` и обязательные критерии `.cursor/rules/dag-generator-interface.mdc`. Найди owning ТЗ Artifacts/Publication/Snapshot и текущие реализации по ссылкам этих документов. Сверяй планы с кодом; различай existing, proposed и accepted. Не объявляй проект согласованным по одному наличию текста.

Сначала найди конкретный метод владельца и POJO, затем сопоставь результат с входом потребителя, затем проверь путь через DAG. Не придумывай ноды. Если binding отсутствует, оставь маршрут OPEN; отдельный конкретный доменный контракт можно принимать независимо от миграции callers.

## Запрос владельцу Source — R1, R3, R4

1. Предъявить concrete capture и durable proof: модули, поля, typed object/settings/collection identities, SourceRevision, authored-presence, semantic projection и codecs. Как membership change влияет на зависимость при неизменном выбранном теле?
2. Предъявить concrete публичные классы/методы exact read и capture, а также mapping CRUD владельцев исходных данных/настроек на revision mechanism: полные сигнатуры, Input/Output/field-error/logic-error, expected revision, scope, effects, replay и DoD. Не назначать Source центральным CRUD-фасадом чужих доменов.
3. Определить единый mutation/capture publication boundary, revision index mapping, staging lifecycle и durable retention owner до Pack/Snapshot. Как body/index/holds/receipts откатываются совместно? Как обеспечивается historical read после restart и удаления текущего объекта?
4. Дать roster writers с INCLUDE/EXCLUDE/DERIVED и обоснованием, включая repair/import/bulk и прямые repository пути. Дать конкретный roster классов и проверку отсутствия дублей POJO/ошибок.

## Запрос владельцам producer/materialization — R1

1. Какой конкретный outcome/receipt связывает logical address, точный ArtifactRef либо typed metadata projection, capture и зависимости PlanRef/PlanDependency?
2. Каковы typed expected/completed coverage и policy evidence? Как отклоняются равные counts при разных адресах, подмена результата, missing part и изменение вне scope?
3. Какие поля передаются через DAG в PackPartInput/assembly provenance? Разделить transient admission evidence и persisted proof; определить проверки и ошибки, не копировать Planning POJO.

## Запрос владельцу Artifacts и publication infrastructure — R2

1. Предъявить принятый внутренний preparing adoption port: concrete binding, полная сигнатура, typed результаты/ошибки, source holder, sealed ref, writable target lease и membership. Где атомарная защита от release/GC, что происходит при повторе, конфликте, cancellation и rollback?
2. Сопоставить с IArtifactHolders.acquire и handoff: handoff требует APPLYING и сам по себе не является preparing adoption. Не предлагать второй holder store.
3. Определить допустимый source retention owner/root и его release lifecycle до появления Pack/Snapshot. SQL revision row не считать ArtifactRetentionHolder без принятого контракта.
4. Предъявить точный scoped commit/CAS/terminal binding для публичного Pack.activate, включая full expected, unknown outcome/recovery и replay после потери ответа. Публичный activate остаётся Pack-owned.

## Запрос владельцу Pack — R3, R5

Зафиксировать конечные address/assembly/provenance schemas; semantics registry_hash/z_band/wilderness_tiles_total; wire envelope и storage binding; все payload read/format/closure bindings. Предъявить concrete activation/release контракты и отдельную C/R/U/D матрицу данных и настроек. Сохранить принятые pack_version/codec_version/payload_format. Read готового payload не должен требовать live Source CRUD.

## Результат

Обнови только документы плана/его appendix через apply_patch: для каждого R1…R5 укажи подтверждённый ответ, источник с модулем/методом и строками, mapping типов/полей, acceptance/rejection и оставшиеся вопросы владельцу. Не изменяй ТЗ для молчаливого устранения противоречия: вынеси конкретное расхождение на согласование. Не закрывай замечание предположением или synthetic fixture.

Сохрани порядок источники → evidence → manifest → codec/readers. Не запрашивай повторно принятый выбор immutable bodies через Artifacts; не вводи новый OperationKind/lifecycle без решения владельца. Проверь все обязательные критерии DAG/CRUD/classes/POJO и покажи diff. Итог: таблица CLOSED/OPEN по доказательствам и готовые адресные вопросы для оставшихся пробелов. При неизвестном контракте явно попроси пользователя уточнить его у указанного владельца; зависимую часть не принимай.
