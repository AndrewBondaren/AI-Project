# Pack exchange: конкретизация A3 и preparation identity

2026-11-14. Проект для приёмки. Код не изменён. Дополняет [exchange](pack-source-exchange-contract.md) и [A1–A4](pack-source-leaf-acceptance.md), не утверждает новый порядок или внешнюю publication boundary. Четыре metadata semantic кода остаются предложением до приёмки; наличие этой таблицы не означает freeze.

## 1. Уже принятые ограничения

- Единственный состав `PackMetadataProofBinding`: subject, provenance, source_request, source_result, groups. Таблицы exchange и metadata POJO синхронизированы; source_admission отсутствует, alias не допускается.
- [Diagnostic union](pack-preparation-issue-union.md): `JsonFieldError | WireShapeIssue | PackPreparationIssue`; оболочки `PackPreparationError` и `PackPreparationFailure` переиспользуются.
- Source владеет `SourceFailure`; ни import, ни bind не вызывают Source и не исполняют его union/subset алгоритмы. Failed/cancelled Source CALL не становится входом следующего Pack шага.
- [ТЗ, Fingerprint и replay](../../docs/tz_world_pack_storage.md#требования-pack-к-входу-prepare-из-dag): отдельный PackPreparationIdentity исключён. `preparation_fingerprint` — digest canonical encoding нормализованного body; operation_id и fingerprint снаружи digest. Semantic source dependencies включаются; transport receipts, lease/fence и timestamps исключаются.

## 2. Предлагаемая точная диагностика exchange

Все пути ниже — отображение typed CheckedPath относительно конкретного named input; строки не являются path API. Индексы исходные, до нормализации. Семантические строки имеют reason=DEPENDENCY_MISMATCH. Структурные ошибки имеют reason=INVALID_INPUT и existing JsonFieldError/WireShapeIssue, а не код из этой таблицы.

| Метод / корневой input | Установленное нарушение | PackPreparationIssueCode / поле |
|---|---|---|
| describe_metadata_usage_requests / PackMetadataUsageRequestsInput | fields пуст | METADATA_GROUP_MISMATCH / fields |
| describe_metadata_usage_requests / PackMetadataUsageRequestsInput | Чужая база subject | BASE_PUBLICATION_MISMATCH / fields[i].subject.base_publication |
| тот же | Address не существует в assembly | ADDRESS_MISMATCH / fields[i].subject.address |
| тот же | Fingerprint projection устарел | SOURCE_PROOF_MISMATCH / fields[i].subject.value_fingerprint |
| тот же | Пропущена группа строки | METADATA_GROUP_MISMATCH / fields |
| тот же | Повтор/лишняя/неприменимая группа | METADATA_GROUP_MISMATCH / fields[i].group |
| тот же | Для запрошенной строки нет detailed attribution | METADATA_ATTRIBUTION_UNAVAILABLE / state.assembly_provenance[k].attribution; если record отсутствует — state.assembly_provenance |
| import_metadata_usage / PackMetadataUsageImportInput | Чужая база, отсутствующий address или stale projection | BASE_PUBLICATION_MISMATCH, ADDRESS_MISMATCH либо SOURCE_PROOF_MISMATCH соответственно / entries[i].requested.key.subject.base_publication, address либо value_fingerprint |
| тот же | entries пуст | METADATA_GROUP_MISMATCH / entries |
| тот же | Неполный набор групп строки | METADATA_GROUP_MISMATCH / entries |
| тот же | Повтор/лишняя/неприменимая группа | METADATA_GROUP_MISMATCH / entries[i].requested.key.group |
| тот же | Недоступна detailed attribution | METADATA_ATTRIBUTION_UNAVAILABLE / state.assembly_provenance[k].attribution либо коллекция, если record отсутствует |
| тот же | Предъявленные request proof/selection/world не равны запросу, описываемому этим state | SOURCE_PROOF_MISMATCH / entries[i].requested.request.proof, selection либо world_uid |
| тот же | Мир результата не равен миру запроса | SOURCE_PROOF_MISMATCH / entries[i].result.proof.world_uid |
| bind_metadata_provenance / PackMetadataProvenanceInput | Base/address/fingerprint не соответствует текущей projection | BASE_PUBLICATION_MISMATCH, ADDRESS_MISMATCH либо SOURCE_PROOF_MISMATCH / entries[i].subject и конкретное нарушенное поле |
| тот же | Один metadata address предъявлен несколькими entries | DUPLICATE_ADDRESS / entries[i].subject.address для повторного элемента; группы разных строк не объединяются |
| тот же | Мир общего proof не соответствует state.base_publication.world_uid | SOURCE_PROOF_MISMATCH / entries[i].source_result.admission.proof.world_uid |
| тот же | Expected usages не равны source_request.groups | SOURCE_PROOF_MISMATCH / entries[i].source_request.groups |
| тот же | Общий proof не равен provenance либо нарушено локальное соответствие selections | SOURCE_PROOF_MISMATCH / entries[i].source_result.admission.proof либо entries[i].groups[j].selection |
| тот же | Число selections не равно числу ожидаемых groups | METADATA_GROUP_MISMATCH / entries[i].source_result.selections |
| тот же | Пропуск/лишняя/повторная группа | METADATA_GROUP_MISMATCH / entries[i].groups либо entries[i].groups[j].group |
| тот же | Pack basis не соответствует текущей projection | METADATA_BASIS_MISMATCH / entries[i].groups[j].basis |

`SOURCE_PROOF_MISMATCH` здесь означает только установленное Pack несоответствие локальной связи. SELECT result proof не обязан равняться полному requested proof, но может совпасть с ним при выборе всех зависимостей. Ни равенство, ни различие сами по себе не являются ошибкой. Pack проверяет мир, структуру и exact исходный request; соответствие subset обеспечивает trusted DAG → Source execution, а не требование равенства/неравенства full proof и subset и не анализ indices в Pack.

Нельзя отвергать одинаковые Source selections разных Pack groups только за совпадение: группа уникальна по Pack key, а не по selection. Для несовпадения числа selections не строится путь к несуществующему элементу. Некорректная структура родителя исключает только зависимые проверки; остальные ошибки агрегируются до формирования нового state.

При bind порядок groups должен совпадать с ordered dependencies текущего PackMetadataDescription: перестановка корректных group keys с чужими позиционными selections не считается допустимой нормализацией. Неверный group на позиции j даёт METADATA_GROUP_MISMATCH по entries[i].groups[j].group; comparison selection выполняется только после установления корректной группы и существования соответствующего элемента source_result.selections. Common proof сравнивается с entries[i].provenance.provenance.source_proof: внешний provenance — существующий new/inherited wrapper, внутренний — PackStoredProvenance. Поле source_proof не добавляется непосредственно в wrapper.

Полнота import проверяется для каждой представленной строки; entries=() отклоняется по указанному semantic коду. PackMetadataUsageImportInput не содержит отдельного expected subjects, поэтому пропуск целой строки из многострочного batch дополнительно обнаруживается DAG сравнением с полным списком исполненных requests в continuation. Непустой entries не является доказательством этой внешней корреляции. Не добавлять скрытый expected state, новый input field или догадку по последнему CALL. Empty Source selection не означает пустой entries: её группа имеет собственную resolution.

Четыре новых кода внутри существующего enum: METADATA_GROUP_MISMATCH, METADATA_ATTRIBUTION_UNAVAILABLE, METADATA_INPUT_MISMATCH, METADATA_BASIS_MISMATCH. METADATA_INPUT_MISMATCH относится к write evidence, а не к Source operation errors; его predicates/paths остаются в [metadata POJO §5](pack-metadata-dependency-pojo.md). Новый diagnostic variant не создаётся.

## 3. Оболочки и ответственность классов

| Класс / владелец / модуль | Поля, роль, допустимые зависимости и эффекты | Приёмка / признак отказа |
|---|---|---|
| JsonFieldError / validation / dataModel/validation/importIssues/jsonFieldError.py | Existing code/path/message, location, wire_path, schema_id, pydantic_type; структурная ошибка известного поля, без IO | Путь разрешим в named input; отказ при зеркальном Pack type-error для того же нарушения |
| WireShapeIssue / validation / dataModel/validation/importIssues/wireShapeIssue.py | Existing code/location/message/pydantic_type; неизвестный ключ или непредставимый field path, без IO | Нет выдуманного FieldRef; отказ при фиктивном path для extra key |
| PackPreparationIssue / Pack / dataModel/worldPack/preparation/errors.py (проект) | code/path/message, Pack semantic predicate, без Source проверки и IO | Реальное поле и точный predicate из §2; отказ при Source subset/union validation |
| PackPreparationError / Pack / тот же проектный модуль | reason и tuple[PackPreparationDiagnostic,...]; единый отказ этапа | Непустые issues для exchange; отказ при потере structural variant/двойной диагностике одной причины |
| PackPreparationFailure / Pack / существующая проектная оболочка errors | error: PackPreparationError; exception из owning service, не новый return-success carrier | Нет partial state при отказе; не поглощает cancellation/infrastructure |
| PackPreparationNodeError / DAG / размещение из leaf contracts | error: PackPreparationError; адаптация owning отказа leaf | Сохраняет error без копирования полей; отказ при generic INVALID_INPUT вместо исходной причины |
| SourceNodeError / DAG / размещение из leaf contracts | error: SourceFailure; перенос отказа Source CALL | SourceFailure не превращается в PackPreparationIssue и не запускает import/bind |

Структурный адаптер и ValidatorAggregationHelper сохраняются по принятому diagnostic union. Точные runtime Pack error records отсутствуют в просмотренном каталоге preparation; это проект, не свидетельство их реализации. Transport/factory/restore всех вложенных вариантов относятся к A4. Изменение error delivery conventions общего engine здесь не предлагается.

## 4. Final state, closure и identity: границы уже принятого и OPEN

Pack перечисляет proofs из полного конечного state, включая inherited parts и metadata; одинаковый proof допускает один closure request при сохранении покрытия всех использований. DAG передаёт результаты, не обходит state. Source владеет полным closure, включая обязательные невыбранные bodies. Pack проверяет exact покрытие запросами final state; READ не предоставляет live hold.

При изменении state после описания closure прежний набор не допускается по одному совпадению operation_id. Pack заново сверяет состав proofs и пересчитывает preparation_fingerprint по конечному body. Не заводятся отдельные proof-set digest, preparation identity POJO или receipt store. Equality fingerprint сама по себе не доказывает Source execution или право на source holder.

`source_closures` в body пока предложенное поле. До его freeze требуется определить canonical encoding его Source результатов и сохранить правило полного semantic body: нельзя молча исключить поле как transport receipt или считать persisted fingerprint доказательством traversal. Эта детализация и контрольные векторы ещё не предъявлены. Existing manifest/body schema и транспорт DAG — разные регистрации.

Publication предложение должно использовать тот же `PackPreparationInput.preparation_fingerprint` и существующий operation_id, а не новый namespace identity. Durable READY обязан быть связан с exact candidate ref и нормализованной identity по ТЗ. Где и как это хранится, source-holder authority, operation kind и post-READY lifetime уточняет владелец publication в [response](pack-source-adoption-publication-response-2026-11-14.md); Pack не объявляет эти пробелы закрытыми своей таблицей.

**Полученное уточнение publication:** PACK_ACTIVATION уже закреплён текущим finish_pack_preparation; choice kind больше не OPEN. В предложенном internal input fingerprint берётся из проверенного lease, второе поле не нужно. Activation request_fingerprint сохраняется отдельно как publication_fingerprint и не заменяется preparation digest. Это подтверждено OperationRecord и PreparedPackCandidate в текущем коде.

**Ограничение replay:** действующее ТЗ требует READY возвращать сохранённый candidate без повторной сборки manifest. Предложенная publication deterministic reconstruction не принимается автоматически: это альтернатива, меняющая данное требование. До отдельного решения сохраняются исходный запрет и OPEN durable exact candidate mapping. OperationRecord содержит набор leased_artifacts, но не роль candidate manifest; выбор первого ref нужного формата не допускается. Владельцу publication передано это противоречие для явного разделения предложения и принятого решения.

## 5. Статус проверки и следующий gate

Устранено описание двух bind shapes; предъявлен operation-specific error mapping и отделены Source outcomes. Новый публичный метод не реализован. A3 остаётся на приёмке четырёх кодов/путей/оболочек; A1/A2/A4 не закрыты этим документом. Полная обязательная матрица критериев и отказ в приёмке сохраняются в leaf-acceptance, а не заменяются локальным перечнем.

Для проверки нужны cases: wrong base; stale equal-value/different-usage; missing/duplicate group; missing attribution; result другого мира; subset, отличный от full proof, при корректном Source CALL; одинаковые selections разных групп; ошибки числа selections без фиктивного index; independent structural/semantic issues без partial mutation. Для READY отдельно — omitted inherited proof, смена body при том же operation_id, потерянный ответ после READY и restart. Runtime тесты не запускались, код не менялся.

### Результат статической сверки A3, 2026-11-14

Сопоставлены поля PackMetadataUsageRequestsInput/Key/Request/Resolution/ImportInput из exchange, PackMetadataProvenanceInput из write-плана, new/inherited wrappers из rev-02-r1-public-pipelines и SourceProofSelectInput/GroupsResult из owning Source §6.0. Existing JsonFieldError/WireShapeIssue/FieldPathError сверены с кодом; PackPreparationFailure(error) — с owning доменным контрактом.

Исправлено: старый subject-only результат describe в write-плане, старая двухполевая bind-форма, ошибочное требование отличия SELECT subset от полного proof, пропуск duplicate-address диагностики bind. Уточнены реальный вложенный путь provenance.provenance.source_proof, world check, порядок groups и запрет построения пути к отсутствующему selection. Поля таблицы существуют в проектных named inputs; это статическая проверка деклараций, не runtime CheckedPath round-trip.

Четыре кода не дублируют structural diagnostics: group означает состав/порядок группы, attribution — отсутствие исторической детализации, input — связь evidence с typed write input, basis — Pack structural основание. SourceFailure остаётся результатом Source leaf, не новым вариантом Pack diagnostic. Порядок 1–7, public/implementation границы и три запрета DAG не изменены; новые операции данных/настроек и IO в POJO не добавлены. Полная матрица обязательных критериев остаётся в leaf-acceptance.

**Последующее уточнение по поручению пользователя «Делай»:** два локальных пробела проекта устранены. Единственный binding объявляется в metadataDependencies.py, а пустые fields/entries отклоняются через METADATA_GROUP_MISMATCH без изменения полей inputs. Размещение и поведение синхронизированы с exchange, metadata POJO и write-планом. Три запрета DAG соблюдены: Pack проверяет свой input и не выбирает следующий вызов; порядок 1–7 сохранён; POJO остаются данными; Source errors и shared structural diagnostics не дублируются. Код и полный runtime/route freeze этим не объявляются принятыми. A3 подготовлен к повторной приёмке по общей матрице, а A1/A2/A4 сохраняют собственный остаток; новый Source контракт или разрешение отложенного Planning для этих исправлений не требуются.
