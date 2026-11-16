# Pack: точные metadata transitions chunk writes

2026-11-16. Конкретизация собственной ответственности Pack по поручению пользователя. Уточняет [batch](pack-wilderness-chunk-batch-contract.md) и [требования к владельцам](pack-batch-owner-contract-requirements.md). Runtime не меняется; это не приёмка реализации.

## Основания решения

Трассировка: `application/worldData/pack/io/worldPackWriter.py::_upsert_tile` создаёт `TileManifestEntry(gx, gy)`; `dataModel/worldPack/wire/climateFieldWire.py::ClimateBakeStatusMixin` задаёт climate_status="coarse". `commit_chunk` записывает адрес/refine_role, затем вызывает `recalc_wilderness_status(expected_chunks=None)`. `dataModel/worldPack/bake/wildernessRefineStatus.py::wilderness_refine_status_without_expected` возвращает partial при положительном количестве chunks, иначе absent. Эти вычисления не читают Source, климатический payload, значения terrain, payload proof или producer expected count.

Metadata группы обозначают именно эти поля Pack: climate_status здесь не утверждение о содержимом климата, wilderness status не утверждение о полном покрытии мира или успешном исполнении producer. Подлинность входного state, адресов и результатов контролируется соответствующими owning boundaries, не заменяется данным расчётом.

## Точные правила групп

`W` — world_uid из admitted state.base_publication. `empty_usage(W)` ниже означает обычное значение существующего `SourceProofInput(world_uid=W, uses=())`, не новый тип/helper/API Source. Это явное правило двух Pack-derived групп, не default на случай неизвестного evidence. Pack создаёт данные owning типа, не вызывает операцию Source. Durable Source proof из этого значения Pack не создаёт: admission/binding остаются через DAG.

| Projection / группа | Значение | Source usage | Basis |
|---|---|---|---|
| Новый tile / IDENTITY | gx, gy из item.part.address | Предъявленный ADDRESS evidence текущего item; переносится целиком без попытки выделить gx/gy subset | None |
| Existing tile / IDENTITY | Сохранённые gx, gy | Предыдущее актуальное usage группы; новый chunk не меняет происхождение существующего tile | None |
| Новый tile / CLIMATE_STATUS | "coarse" по фиксированному правилу Pack | empty_usage(W), поскольку правило не читает климатические/Source данные | None |
| Existing tile / CLIMATE_STATUS | Сохранённый status | Предыдущее актуальное usage группы, включая fine; ни значение, ни зависимости не заменяются текущим chunk evidence | None |
| Адресованный chunk / IDENTITY | cx, cy в адресованном tile | ADDRESS evidence данного item; chunk write полностью задаёт адресованную chunk projection. Равенство координат не сохраняет старое основание автоматически | None |
| Адресованный chunk / REFINE_ROLE | Explicit item.refine_role, в том числе None | REFINE_ROLE evidence данного item | None |
| Затронутый tile / WILDERNESS_REFINE_STATUS | partial после успешного chunk write: в tile есть минимум записанный chunk | empty_usage(W). Это характеристика фактического состава Pack, а не значения Source entity; payload и identity usages в status не объединяются | Все текущие chunk addresses этого tile в принятом canonical порядке; expected_chunks=None |

При нескольких items нового tile IDENTITY создаётся первым item и сохраняется последующими. Каждый chunk получает собственное evidence. CLIMATE_STATUS создаётся один раз. WILDERNESS_REFINE_STATUS следует membership после каждого перехода; полный basis материализуется один раз по итоговому составу. Незатронутые chunks/tiles и их provenance сохраняются.

Empty batch не создаёт tile, не заменяет usages и не пересчитывает basis. Explicit recalculate с expected и fine climate writes — другие операции; эти empty-usage правила на них автоматически не распространяются.

## Evidence: минимальная форма без неявного режима

Для single и каждого batch item требуются ровно два VALUE evidence slots: ADDRESS и REFINE_ROLE. ADDRESS связывается с полным `PackChunkAddress`; REFINE_ROLE — с typed nullable значением. Порядок slots не определяет семантику, дубликаты и лишние selectors запрещены. `metadata_inputs=()` для chunk write не допускается.

Для source-independent command address или literal refine_role producer/owning binding предъявляет соответствующий evidence с явно пустым usage правильного мира. Это не требование фиктивного capture и не разрешение caller объявлять любой source-derived input независимым. Pack проверяет local value binding и world; достоверность producer usage обеспечивает принятая граница исполнения. Наличие двух DTO само по себе её не доказывает. До DAG-интеграции остальных доменов их POJO не объявляются production binding.

Такое правило конкретизирует разрешённость ADDRESS slot общим metadata-контрактом: для chunk write evidence обязателен, но Source read/capture не требуется, когда источник значения явно source-independent. Значение fingerprint вычисляется owning producer/Pack binding, не DAG. Pack не читает World, не запускает генератор и не извлекает evidence из payload proof.

## Retained и pending dependencies

Перед partial update существующего tile все сохраняемые группы должны иметь готовый актуальный usage в state.metadata_dependencies. Existing detailed durable attribution сама по себе содержит selection, а не usage: DAG заранее выполняет согласованный extraction/import маршрут. Whole-row attribution не раскладывается Pack на группы.

При replacement chunk прежние IDENTITY и REFINE_ROLE не сохраняются: обе группы полностью заданы новым item, поэтому их историческое usage не требуется для замены. Для existing tile сохраняются IDENTITY и CLIMATE_STATUS; отсутствие их безопасных оснований приводит к METADATA_ATTRIBUTION_UNAVAILABLE, даже если следующее item могло бы изменить конечный результат. Импорт полный по строке, как требует существующий exchange; это не разрешение частичного Description.

После первого item рабочая карта содержит свежие группы; следующий item использует её, а не повторно исходную attribution. Весь old tile row proof становится неприменимым после изменения value/basis/usage; остальные группы сохраняются как pending usage. Final description содержит полный набор tile groups. Chunk description содержит IDENTITY и REFINE_ROLE. Для unchanged независимых строк никакой повторный bind не назначается самим batch.

Даже partial→partial с новым membership меняет basis и требует свежего binding. Даже при пустом status usage basis не исчезает и stale bind не принимается. Empty usage не является empty durable proof, не заменяет Source admission и не позволяет обойти READY/closure.

## Отказы и DoD

Используется batch error table и согласованный reason priority. Отсутствующий ADDRESS/REFINE_ROLE — METADATA_INPUT_MISMATCH по metadata_inputs; duplicate/extra slot — по metadata_inputs[j].input; неверный fingerprint — по value_fingerprint; чужой world — SOURCE_PROOF_MISMATCH; отсутствующие сохраняемые usages — METADATA_ATTRIBUTION_UNAVAILABLE; некорректный basis входа — METADATA_BASIS_MISMATCH. Нет новой ошибки Source и нет прямого вызова Source.

Приёмочные примеры:

1. Новый tile, два chunks с разными captures в evidence: tile identity использует первый ADDRESS usage; каждый chunk свои два usages; climate/status usages пусты; final basis содержит оба адреса. Union всех captures в status запрещён.
2. Existing tile fine/complete: replacement сохраняет fine и его usage, переводит wilderness в partial с expected=None и пустым status usage, полностью заменяет chunk evidence.
3. Existing tile partial: addition меняет basis при том же status и том же пустом usage; прежний bind отклоняется.
4. Existing tile без imported usage сохраняемых групп: single и batch отклоняются одинаково, без Source-вызова и частичного state.
5. None refine_role с корректным evidence записывает None; missing evidence отклоняется. Equal value с другим evidence не объявляется inherited.
6. Пустой пакет оставляет state семантически неизменным после admission. Исходный state и nested records не мутируются при успехе или отказе.

По этим правилам single/batch используют один переход. Membership поддерживается локальным индексом; predicates не требуют промежуточной сборки полного basis/state. После каждого успешного item совпадают values/usages и membership, после последнего — final materialization. Проверка этого свойства в коде и benchmark остаются приёмкой реализации.

## Междоменные последствия

Нового Source/Cache/Snapshot API не требуется: используются SourceProofInput и ранее согласованные exchange/admit/bind, pinned-origin и owning cache границы. Нового вопроса к владельцам для данных Pack-derived правил нет. Если owning API обнаружит несовместимость требуемой формы, Pack направляет конкретный вопрос владельцу; не ослабляет правила молча. Независимая техническая приёмка документа не подменяется этой конкретизацией.
