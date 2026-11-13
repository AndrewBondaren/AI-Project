# Pack core: admission внешнего provenance и полнота closure

Дата: 2026-11-13. Статус: PROJECT, локальное уточнение Pack; не разрешение runtime cutover. Scope — только ядро Pack. Основания: [актуальная приёмка](pack-current-scope-acceptance.md), [write contracts](pack-v2-public-write-operations.md), [closure trace](pack-preparation-closure-trace.md), [основной Pack план](world-pack-v2-single-manifest-contract.md). Внешние SoT: [world-source-versioning](world-source-versioning.md), [Source integration specification](source-proof-v2-contract-spec.md). Их внутренние модели этим документом не определяются.

## 1. Что уже принято и не открывается повторно

По решению пользователя 2026-11-13 согласованы [семантика metadata dependency usage и политика старой базы](pack-metadata-dependency-usage.md#согласованные-решения-пользователя): детализация полей, необходимые изменения Pack POJO, отказ partial update при неизвестном происхождении сохраняемых полей. Подготовлен [конкретный проект POJO](pack-metadata-dependency-pojo.md); exact carriers/bindings пока не приняты, R1/R3 не закрыты. Формы state/describe/bind ниже описывают исходную схему, которую уточняет этот отдельный срез.

PackPreparationService возвращает PackPreparationState; describe_metadata возвращает PackMetadataSubject(base_publication, address, value_fingerprint); bind_metadata_provenance принимает PackMetadataProofBinding(subject, provenance). Эти локальные контракты существуют в проекте. Они не обещают подтверждение происхождения одним fingerprint. PACK-METADATA-PLANNING сохраняет разрешённую отсрочку, новый lineage/receipt или PackWriteResult не вводится.

PackStoredProvenance хранит внешний owning source_proof и existing Planning dependencies. Source proof не объявляется в Pack. Предложения отдельного Source-дизайна в соседних документах не являются принятыми внешними bindings.

## 2. Точки получения данных через DAG

| Pack операция | Поле / значение | Что проверяет Pack |
|---|---|---|
| start_from_base | Закреплённая база → state.base_publication и полный состав | Истинность pinned base и сохранение её частей/provenance |
| Specialized payload write | request.part.address, artifact, provenance; source proof вложен в общий provenance | Допустимость адреса/ref/payload и локальный provenance admission. Source/producer не запускаются |
| describe_metadata | state + addresses → subjects | Точная текущая projection и база; только pure selector/codec |
| bind_metadata_provenance | entries[].subject и entries[].provenance | Unique addresses, base, актуальный fingerprint, owning provenance admission; не повторяет write |
| final prepare | PackPreparationInput.body.state, capture, scope | Полнота всех payload/metadata proofs конечного состава, scope/coverage, payload bindings, semantic closure и удержание перед READY |
| activate | PreparedPackCandidate + expected publication | Candidate/expected и atomic handoff по accepted lifecycle; capture/materialization повторно не выполняются |

DAG передаёт готовые owning результаты в публичные операции. Pack не вызывает публичные Source операции, не читает latest, DAG не вычисляет manifest или closure. Имя и поля внешнего результата, передаваемого в final prepare, должны быть предъявлены владельцем и сопоставлены с Pack input до принятия integrated binding.

**Не добавлять поле в PackPreparationBody наугад.** Текущая форма state/capture/scope сохраняется. После предъявления внешнего контракта проверить, достаточно ли capture input и принятого внутреннего scoped binding либо нужен отдельный transient input. Сам факт существования внешнего collect_refs не доказывает необходимость нового публичного поля. Ни один из вариантов сейчас не утверждается. Отсутствующий binding не заменяется dict, пустым tuple или Source DTO местного производства.

## 3. Алгоритм Pack-owned полноты

1. Взять конечный authoritative state. Проверить unique addresses, полный обязательный provenance частей и metadata. Неполный intermediate state допустим в writes, но не в final prepare.
2. Для каждого logical use проверить его address/ref/provenance в контексте candidate world, scope и базы. Два адреса с одним ref остаются двумя use. Inherited provenance сверяется с pinned base и не заменяется текущим capture.
3. Выполнить существующий planned payload admission: девять известных leaf roles не дают payload children; hydrology spatial root даёт проверенные root.shards с owning decode и проверкой связи каждого shard. Unknown format не считать leaf.
4. Получить полный durable Source refs набор через предъявленный owning binding для **всех** provenance конечного state, включая assembly и inherited части. Pack проверяет покрытие logical uses и связь результата с точным proof; не интерпретирует внутренние Source indices/revisions. Неизвестный состав означает отсутствие допуска, не пустой closure.
5. Объединить parts refs, payload children и проверенные provenance refs; физические refs дедуплицировать по полной identity. Не конструировать ArtifactRef из PlanRef/output_fingerprint и не читать Planning latest/cache для его восстановления.
6. По принятому prepare lifecycle закодировать и stage manifest, сверить ref с bytes и добавить manifest ref к semantic closure. Stage/adopt/finish должны использовать согласованные atomic ports; этот алгоритм не вводит новую transaction.
7. До READY подтвердить seal и действующее destination удержание всего множества. finish должен подтвердить **точное** equality с operation members, world/operation/fence/fingerprint/phase. Лишние holds не включаются в closure ради прохождения equality; missing ref не удаляется из требуемого множества.
8. Только после всех проверок вернуть existing PreparedPackCandidate. Не запускать activate и retry. Поздний отказ не выдаёт candidate, cleanup принадлежит принятому lifecycle.

Порядок не заменяет detailed staging/atomic choreography основного плана. Особенно важно: проверка composition → independently derived semantic closure → exact holds equality; обратный вывод closure из имеющихся holds запрещён.

## 4. Распределение ответственности и отказы

| Класс / существующий элемент | Ответственность, зависимости и эффекты | Критерий отказа |
|---|---|---|
| PackPreparationValidator | Pure local/final checks по Pack POJO; existing diagnostics | IO, latest-read или выдача provenance validity только по совпадению subject |
| PackPreparationService | Одна запрошенная write/describe/bind операция; start_from_base имеет принятый pinned read | Вызов другой публичной операции, producer/Source либо применение списка команд |
| PackManifestAssembler | Pure построение manifest из проверенного конечного state | Повторное выполнение writes или orchestration |
| PackPreparationOperation | Internal verified reads, external owning binding admission, coordination локальных стадий одной prepare операции | Прямой публичный Source call, самодельный holder store, READY при неизвестном closure |
| finish_pack_preparation, encoding/preparedManifest.py | Сейчас stage bytes и exact READY/member checks; other_members приходит извне | Считать current other_members доказательством полноты target provenance closure |
| PreparedPackCandidate | Existing operation_id/manifest/preparation_fingerprint | Добавление copied Source body/lease или выдача до READY |

Используется существующий согласованный PackPreparationDiagnostic union и PackPreparationFailure. Missing proof, mismatched proof и storage/infra failure не схлопываются в один arbitrary ValueError. Exact mapping owning outcome → Pack issue фиксируется после предъявления owning outcomes; новые generic errors и зеркальные Source/Artifacts коды этим уточнением не вводятся.

## 5. Что требуется от внешнего контракта

Для integrated admission владелец должен предъявить concrete class/method, typed Input/Output/Error и эффекты, позволяющие проверить: exact world/capture/dependencies; полный durable refs набор; исторические inputs при частичном обновлении; связь с действующим независимым holder; scoped adoption без гонки с release. Это требования потребителя, не назначение структуры Source proof или Source implementation.

Результат должен быть пригоден для проверки после restart. Caller-constructed POJO со списком refs не доказывает происхождение. Как именно обеспечивается owning validation/доверенная внутренняя boundary, должен указать согласованный binding; Pack не изобретает подпись, token либо receipt store.

## 6. Проверки и статус приёмки

### Сверка следующего шага 3a с runtime — 2026-11-13

По единой таблице основного плана следующий локальный слой — 3a, а не перескок к 4b/READY. В коде проверены `dataModel/worldPack/preparation/addresses.py` (10 payload address variants) и `coverage.py` (materialized/without_payload, coverage entry). Выполнено `python -B -m unittest tests.spatial_pack.test_preparation_addresses tests.spatial_pack.test_preparation_coverage` из backend: **8 tests, OK**. Проверены existing round-trip, strict shape, nested forgery, immutability и независимые ошибки. Это проверка уже существующей реализации, не новая поставка.

Поиск concrete объявлений PackPreparationState, PackAssemblyInput, PackStoredProvenance, PackPreparationService, PackPreparationValidator, PackPreparationError и PackPreparationIssue в `backend/app` не обнаружил их. Следовательно, pure describe/bind нельзя начать как изолированную правку метода: нужны owning state/assembly/provenance и diagnostics. Создавать их с фиктивным Source полем запрещено; пустой service или новый generic DTO не закрывают 3a.

Для следующего code-среза сначала предъявить точный независимый набор недостающих Pack records с готовыми типами зависимостей либо owning Source binding для полноценного state. Это не требование ждать всю миграцию Source. Не выбирать произвольно слой errors вместо согласованной последовательности; основной план прямо запрещает такой автоматический выбор. Пока конкретный срез не принят, эта сверка не разрешает изменение runtime. Source и сериализация остаются вне текущей ответственности.

Обязательные контрпримеры: child пропущен одновременно в declared refs и operation holds; лишний hold; один ref на двух адресах с разным provenance; inherited proof после release старой версии; отсутствующий metadata proof; совпавший subject с чужой базой; change latest при сохранном capture; release между внешней проверкой и prepare; незавершённый payload admission; readiness record с неверным fence/fingerprint.

Проверка mandatory criteria: DAG orchestration сохранена, публичных междоменных вызовов не добавлено, обязанности классов заданы §4, POJO не дублируются, approved write/order/settings/CRUD решения не изменены. Exact external signatures и scoped effects не предъявлены — **integrated приёмка остаётся OPEN**. Это не повторный отказ независимым pure Pack методам. Source разработку и отложенный Planning mapping в scope Pack не включать. Runtime реализация — после принятия конкретного среза через implement-plan.
