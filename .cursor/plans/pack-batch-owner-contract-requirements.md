# Требования Pack к контрактам массовой записи

2026-11-16. Зафиксировано по прямому поручению пользователя. Это требования потребителя Pack и его собственные обязанности; они не объявляют новые внешние API принятыми владельцами и не разрешают кодовые изменения.

## Владельцы и маршрут

**Source, Snapshot и Cache могут предоставить точные контракты.** Неизвестные поля, ошибки или гарантии их операций уточняются у соответствующего владельца по конкретному запросу Pack. Остальные домены могут предоставить owning POJO; их интеграция с DAG пока отсутствует. POJO не доказывает исполнение producer операции, достоверность evidence или готовность DAG binding.

Прямые междоменные вызовы запрещены, включая public API через DI, callback, фасад и pure helper чужого домена. Pack возвращает данные DAG; DAG вызывает операцию владельца и передаёт результат Pack. Импорт owning типов данных не является разрешением вызывать owning сервис. Pack не выбирает следующую доменную операцию; DAG не вычисляет Pack projections, fingerprints, membership, merge или Source subsets. Новые NodeId и генераторные bindings этим документом не вводятся. Интеграция Pack с DAG остаётся последним шагом.

## 1. Вход записи: Pack-owned контракт

Точные объявления single/batch — в [batch-контракте](pack-wilderness-chunk-batch-contract.md#публичный-контракт):

- `PackWildernessChunkWrite(part: PackWildernessChunkPartInput, refine_role: ChunkRefineRole | None, metadata_inputs: tuple[PackMetadataInputEvidence, ...])`;
- `PackWildernessChunkInput` наследует поля записи и добавляет `state: PackPreparationState`;
- `PackWildernessChunksInput(state: PackPreparationState, entries: tuple[PackWildernessChunkWrite, ...])`;
- результат — `PackPreparationState`, отказ — `PackPreparationFailure(PackPreparationError)`.

`PackMetadataInputEvidence(input, value_fingerprint, source_usage)` использует существующий проект [metadata POJO](pack-metadata-dependency-pojo.md). Source usage имеет owning тип `SourceProofInput`; селектор и fingerprint принадлежат Pack-контракту. Все поля обязательны, explicit None является значением. Evidence локален item, не содержит копию state или дополнительный batch index.

## 2. Требования по группам metadata

**Последующая конкретизация Pack:** [точные transitions](pack-chunk-metadata-transition-contract.md) задают значения и usage каждой группы, включая новые tile и provisional status. Указанные ниже обязанности «определить» выполнены этим документом: новый climate=coarse и provisional status имеют Pack-derived empty usage, identity/role получают explicit evidence. Это не изменение контрактов владельцев и не объявление production DAG binding готовым.

| Группа / данные | Владелец смысла | Что требуется передать или определить | Проверка Pack / отказ |
|---|---|---|---|
| Chunk address / IDENTITY | Pack адресует part; producer отвечает за source-derived значение | `part.address`; evidence ADDRESS, когда значение основано на Source. Отсутствие Source-зависимости должно следовать конкретному owning правилу | Typed address и fingerprint выбранного поля; missing/extra/duplicate evidence — METADATA_INPUT_MISMATCH |
| REFINE_ROLE | Producer значения; Pack хранит и заменяет | Explicit refine_role и evidence REFINE_ROLE, включая None. Source-зависимости именно этого значения, не всего payload | Exact typed value/fingerprint и world usage; mismatch — METADATA_INPUT_MISMATCH либо SOURCE_PROOF_MISMATCH |
| Сохраняемые tile IDENTITY / CLIMATE_STATUS | Pack сохраняет прежние значения; Source владеет extraction usage | Готовый импортированный usage каждой сохраняемой группы либо уже актуальная pending description | Subject/base/groups актуальны; недостаточная historical детализация — METADATA_ATTRIBUTION_UNAVAILABLE |
| Новый tile IDENTITY | Pack определяет projection из chunk address | Pack обязан определить связь tile coordinates с ADDRESS evidence. Producer не обязан знать PackTileAssembly | Проверить соответствие coordinates; нельзя объявить весь payload proof основанием tile |
| Начальный CLIMATE_STATUS нового tile | Pack | Pack обязан назвать существующее правило инициализации и фактически используемые входы. Если это Pack constant без Source reads, явно обосновать source-independent usage | Не вводить новый default и не требовать фиктивный producer capture; неизвестное правило не заменять пустым usage |
| Provisional WILDERNESS_REFINE_STATUS | Pack | Policy использует текущий membership и expected=None. Pack обязан определить, использует ли переход какие-либо Source-derived основания membership; basis хранит final addresses/None | Basis и policy согласованы; stale basis — METADATA_BASIS_MISMATCH. Список адресов не является Source proof |
| Payload provenance | Producer результата, Source владеет proof | Existing `PackPartProvenance`, без зеркального batch proof | Existing new/inherited/world admission. Payload proof не подставляется вместо metadata evidence |

**Обязанность Pack, а не запрос генератору:** завершить правила нового tile и provisional status. Если локальный расчёт использует только Pack membership/policy, Pack должен обосновать отсутствие прямых Source-зависимостей и допустимость empty usage. Если использует source-derived membership, Pack должен перечислить конкретные используемые данные и требуемое evidence. Само слово membership не обосновывает ни union всех chunk proofs, ни обязательный новый внешний capture.

## 3. Source: точный обмен через DAG

Переиспользуется [Pack ↔ DAG ↔ Source exchange](pack-source-exchange-contract.md), без нового batch API Source:

1. Pack `describe_metadata_usage_requests(PackMetadataUsageRequestsInput)` возвращает `tuple[PackMetadataUsageRequest, ...]`. Каждый record содержит Pack key и owning `SourceProofSelectInput`. Key остаётся в корреляции DAG; Source не знает Pack metadata DTO.
2. DAG исполняет Source SELECT над выданным запросом. Успех — `SourceProofResult`; отказ — `SourceFailure`. DAG не вызывает зависимый Pack import при отказе.
3. DAG возвращает `PackMetadataUsageImportInput(state, entries: tuple[PackMetadataUsageResolution, ...])`. Resolution сохраняет exact requested и result. Pack импортирует полный набор требуемых групп строки, не вычисляет subset.
4. После записи Pack `describe_metadata` возвращает `PackMetadataDescription`. DAG передаёт ordered usages через `SourceProofGroupsInput`, получает `SourceProofGroupsResult` и передаёт exact request/result в согласованный metadata binding Pack.

Требуемые гарантии: результат относится к реально исполненному запросу; world совпадает; selections соответствуют исходным groups; несколько captures и их revisions не схлопываются в один произвольный capture. Exact union/subset проверяет Source, Pack проверяет свои subject/basis/field связи. Пара DTO requested/result сама по себе не удостоверяет исполнение; это ответственность согласованной границы DAG execution.

Если обнаружено несоответствие owning Source-контракту, Pack направляет владельцу конкретный predicate/Input/Output/Error вопрос. Не создавать `SourceProofFailure`, surrogate proof или собственную реализацию Source SELECT.

## 4. Snapshot и Cache

| Владелец | Что нужно Pack | Что не добавляет batch |
|---|---|---|
| Snapshot | Точный existing контракт pinned base/publication: `WorldPublicationRef` задаёт identity базы; принятый pinned-origin/read маршрут подтверждает происхождение прочитанных parts/metadata. Проверять по [S1/S2](source-pack-s1-s2-contract.md) и [pinned-origin](snapshot-pinned-origin-contract-r1.md) | Новый pin, чтение базы внутри pure batch, признание caller state доверенным по одному WorldPublicationRef |
| Cache | Для этого pure batch нет новой Cache операции или настройки. Если вход получен из Cache, owning результат должен сохранить тип и provenance исходного результата; точные гарантии уточняются по действующему Cache-контракту при соответствующем integration slice | Cache lookup/store внутри Pack, кеш валидности state по identity, подмена metadata evidence признаком cache hit |

Доступность этих владельцев означает возможность получить точный контракт, а не необходимость добавить зависимость от каждого из них в batch. Не выдумывать Cache DTO или дополнительный Snapshot вызов при отсутствии потребности.

## 5. Остальные producer домены: только POJO до интеграции

От владельца можно получить точный тип значения, ограничения полей и описание зависимостей этого значения. Pack фиксирует mapping этих данных в свой input/evidence. Нельзя на этом основании объявлять существующим публичный pipeline, ноду, execution binding или успешный end-to-end маршрут.

Будущая интеграция: producer → DAG → Pack. На текущем этапе не реализуется; прямого producer → Pack или Pack → producer вызова нет. Новые требования интеграции учитываются при миграции владельца. Неизвестные внешние гарантии отмечаются у зависимого сценария, а не блокируют весь Pack.

## Статус и следующий результат

Вход/выход/error требования Pack и границы владельцев перечислены явно. Source exchange переиспользуется; для Snapshot/Cache новых batch API не требуется. Остаток внутри Pack — завершить source-dependency правила собственных new-tile/status переходов и проверить согласованность с описанным reducer. До этого полный semantic PASS этих переходов не объявляется. Отсутствие готового генератора не является причиной остановить эту работу Pack.
