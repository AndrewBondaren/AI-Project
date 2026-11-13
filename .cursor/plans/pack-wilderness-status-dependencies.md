# Основания wilderness status: Pack membership и Source usage

Дата: 2026-11-13. Статус: TRACE / PROPOSAL. Документационная конкретизация [metadata POJO](pack-metadata-dependency-pojo.md), без изменения runtime или принятой policy. Новые carriers ниже требуют приёмки, не являются Source-контрактами.

## 1. Что читает действующий алгоритм

1. [WorldPackWriter.commit_chunk](../../backend/app/application/worldData/pack/io/worldPackWriter.py) заменяет запись по cx/cy и вызывает recalc_wilderness_status с expected_chunks=None. Меняются состав и provisional status; не выполняется чтение Source или анализ содержимого chunks.
2. recalc_wilderness_status берёт len(tile.chunks). [Pure policy](../../backend/app/dataModel/worldPack/bake/wildernessRefineStatus.py): без expected — partial при положительном количестве, иначе absent; с expected — absent при baked<=0, complete при expected>0 и baked>=expected, иначе partial. Новые bounds для expected не вводятся.
3. [DetailedRefine](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py) вызывает финальный пересчёт после обработки tile только при наличии plan.expected_chunks_for_status. При пустом rects обработка tile пропускается. Порядок и условие вызова сохраняются.
4. [DetailedScope](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py) задаёт callback expected_fine_chunks только wilderness-маршруту; location-маршрут использует None. В target Pack получает готовый int, не callback или World.
5. [expected_fine_chunks](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkGeom.py) возвращает len(rects_for_macro_tile): используются tile coordinates, map_cell_fine_span(world), terrain_chunk_columns(world) и owning grid geometry. Это фактический путь текущего producer, не разрешение Pack вычислять expected заново или DAG повторять этот алгоритм.
6. [PackChunkCoverageEntry](../../backend/app/dataModel/worldPack/preparation/coverage.py) содержит address и structural result materialized/without_payload. У него нет evidence членства в Pack и нет producer proof. Число coverage entries/outputs нельзя подставить вместо len(tile.chunks); final coverage и видимый status — разные проверки.

## 2. Разделение ответственности

| Основание | Кто устанавливает | Что не является доказательством |
|---|---|---|
| Текущие chunk-записи и точное множество их адресов | Pack из переданного state, после local admission; база из pinned read | Количество Source objects, число coverage outcomes, полный payload proof |
| Изменение множества при write/delete | Pack исполняет конкретную локальную операцию; scope и caller binding проверяются соответствующим admission | Source capture не удостоверяет выполнение Pack write/delete |
| Готовый expected_chunks и фактически использованные producer Source inputs | Producer выдаёт значение с usage; Source проверяет исторические dependencies | Равенство числа числу chunks, header latest или повтор алгоритма в DAG |
| Выбор None/provisional и owning status policy | Конкретный Pack input и алгоритм | Фиктивная Source revision для None либо константы partial/absent |
| Соответствие final scope/coverage и удержание refs | Final Pack admission и принятые owning bindings | Успешный расчёт status или success POJO от Source |

Следствие: обязательный Source proof на каждый command address был бы лишним требованием. Адрес удаления/пересчёта задаёт объект операции, но сам по себе не означает чтение Source. Evidence адреса требуется там, где producer действительно утверждает source-derived identity; наличие command coordinate этого не доказывает. Сохранённый Source usage группы также нельзя автоматически расширять всеми dependencies payload content.

## 3. Предложение Pack-owned основания вычисления

Для WILDERNESS_REFINE_STATUS предлагается материализованный immutable `PackWildernessStatusBasis(chunk_addresses: tuple[PackChunkAddress, ...], expected_chunks: StrictInt | None)`. Tile определяется уже существующим subject.address, не повторяется отдельным полем; baked_count вычисляется из unique addresses, отдельного поля count нет. Адреса принадлежат ровно этому tile, имеют детерминированный порядок; дубликаты отклоняются до нормализации.

Это один снимок inputs **последнего фактического вычисления данного status**, не command log, receipt выполнения, дополнительный payload DTO или журнал удалённых chunks. Отсутствие адреса в полном снимке означает отсутствие записи на момент расчёта, а не отсутствие Source entity. Source не получает этот тип. Pack проверяет применимость basis и соответствие результата owning policy в пределах принятой границы доверия.

Предлагаемое размещение конкретизировано ниже: basis принадлежит записи группы WILDERNESS_REFINE_STATUS внутри description/attribution. Он не помещается в SourceProofSelection и не дублирует SourceDurableProof. Универсальный dict с arbitrary operation names не вводится; прочие алгоритмы не получают неописанные basis variants.

Обновление basis выполняется только при реальном вычислении status: chunk write/delete согласно их контрактам и явный recalculate. Write fine climate переносит старые status/basis вместе; final prepare не пересчитывает status. Равный результат partial→partial не доказывает равенства basis/usage. Для stale bind сравниваются текущие value, basis и source usage, а не один fingerprint значения.

Одна только подмена caller state вместе с согласованным basis не выявляется пересчётом policy: нужны принятые pinned/producer/state boundaries. Basis доказывает проверяемую связь входного состава с результатом, но не подлинность входа и не факт исполнения исторической операции. Не выдавать его за receipt или security token.

### Точное размещение и проверка basis

Предлагаемый owning модуль — `dataModel/worldPack/meta/metadataAttribution.py`. Там объявляется один PackWildernessStatusBasis; transient preparation imports этот же тип. Код ещё не создаётся. Обязательные поля strict/frozen/revalidate-always, tuple вместо list, expected=None не имеет default и означает именно provisional расчёт. Zero/negative int допускаются как раньше, bool не допускается.

| Этап | Точный путь данных | Правило |
|---|---|---|
| Pending write state | state.metadata_dependencies[i].dependencies[j].basis | i выбирает tile subject, j — WILDERNESS_REFINE_STATUS. Pack создаёт basis в том же pure переходе, в котором вычисляет status |
| Describe output | descriptions[i].dependencies[j].basis | Возвращается готовый basis из текущего pending record или pinned detailed attribution; describe не восстанавливает expected из результата |
| Запрос в Source | basis не передаётся | Передаётся только source_usage по owning API; DAG сохраняет basis рядом с корреляцией subject/group |
| Bind input | entries[i].groups[j].basis | DAG возвращает исходный basis без пересчёта вместе с Source selection/admission |
| Durable manifest | assembly_provenance[i].attribution.groups[j].basis | Pack сохраняет basis после успешной проверки; общий proof остаётся в provenance.source_proof |
| Следующий start_from_base | Тот же detailed attribution из pinned manifest | Нет переинтерпретации по latest header; basis сохраняется вместе с owning status |

PackMetadataDependencyUse и PackMetadataGroupAdmission получают обязательное nullable поле basis. Для detailed WILDERNESS_REFINE_STATUS basis обязателен non-null; для остальных текущих groups — None. Legacy whole-row режим выражается отсутствующей attribution всей строки, а не fabricated group с basis=None. Новая tile default absent получает basis(empty tuple, None) из проверенного правила создания; её source usage определяется отдельно, не выводится из одного empty tuple.

Проверки bind, в порядке зависимостей:

1. Structural admission; exact base/subject и уникальные допустимые groups. Wrong basis type/group — structural либо METADATA_GROUP_MISMATCH по факту нарушения.
2. Получить authoritative ожидаемый basis текущего state: pending description либо detailed durable attribution. Нельзя выбрать его из возвращённого caller binding. Нельзя сравнить две копии одного неподтверждённого входа и объявить trusted evidence.
3. Сравнить возвращённый basis с ожидаемым по полному typed значению, включая множество адресов и expected. Canonical tuple order задаётся Pack: gx, gy, cx, cy; все адреса одного tile, дубликаты запрещены. Порядок здесь — нормализация множества для identity, не перестановка write-операций.
4. Проверить policy(basis) == текущий wilderness status. Внутренний вызов pure policy является validation, не публичным recalculate и не меняет state. source_usage и source admission проверяются отдельно: одинаковые basis не означают одинаковые Source dependencies.
5. При успехе сохранить проверенный basis в group attribution, удалить только соответствующую pending запись после полного успешного bind строки. Поля metadata/parts не изменяются. При отказе нет частичных записей.

Предлагаемая диагностика: неверная применимость/отсутствие basis в detailed group — METADATA_GROUP_MISMATCH; stale basis или несоответствие policy текущему значению — новый semantic код METADATA_BASIS_MISMATCH в существующем PackPreparationIssueCode, reason=DEPENDENCY_MISMATCH, path entries[i].groups[j].basis. Не называть Pack structural mismatch ошибкой Source proof. Это четвёртый предложенный metadata semantic код, требует приёмки вместе со схемой.

Basis содержит состав **на момент последнего расчёта**, а не требование пересчитать исторический status по любому текущему state. При write/delete, которые по контракту пересчитывают status, Pack строит basis по составу после данного изменения. Остальные операции обязаны сохранить согласованную пару status/basis. Обнаруженный пропуск обязательного пересчёта — ошибка соответствующего writer, не повод prepare молча исправить status. Final coverage/admission продолжает проверять свои отдельные связи.

Пример: A содержит адреса c1,c2, status=complete, basis=([c1,c2],2). Замена payload c2 через chunk write выполняет старый provisional переход: новый status=partial, basis=([c1,c2],None). Удаление c2 затем даёт partial, но basis=([c1],None). Bind от предыдущего partial отвергается несмотря на одинаковый subject value. Fine climate write после этого переносит последний wilderness basis неизменным. Добавление/удаление не превращается в Source capture mutation.

**Граница гарантии:** этот контракт позволяет проверять расчёт и freshness binding относительно переданного state. Подлинность базы/producer/state остаётся за принятыми owning boundaries. Снимок полного множества адресов хранится ради проверяемого состава; scalar policy непосредственно читает его количество. Поэтому все адреса basis не объявляются автоматически Source reads или отдельными source dependencies.

## 4. Как это связано с Source proof

Source usage этой группы перечисляет только реально использованные Source dependencies по предъявленному producer/Pack binding. Готовый expected с producer usage связывается с его точным typed значением; provenance структурного состава Pack не превращается в fictitious capture. Если Pack действительно использует source-derived membership evidence, его owning usage передаётся отдельно и проверяется, а не заменяется целыми proofs всех payload.

До принятия полного mapping нельзя обещать точность source usage: требуется установить, какие membership dependencies producer реально предъявляет и какие из них участвуют в конкретном вычислении. Empty Source usage допустим только при доказанном отсутствии Source reads/dependencies по owning контракту, не как обход незавершённого mapping. Это точечный integration seam, не основание остановить независимые Pack работы.

Старая строка без необходимой детализации продолжает читаться/наследоваться неизменной. Если частичный update требует переносить неизвестный basis/usage соседнего поля, действует согласованный отказ. Нельзя восстановить прежний expected из complete, из текущего header или из значения status. Полная замена с достаточными новыми основаниями остаётся разрешённой.

## 5. Приёмка и стоимость

- Replacement по существующему адресу не меняет membership, но legacy write всё равно выполняет provisional пересчёт: прежний complete не сохраняется автоматически.
- Добавление/удаление при partial→partial меняет basis. Старый bind с прежним basis отклоняется даже при равном value_fingerprint.
- expected None, zero, negative, положительный; baked>expected сохраняет прежнюю policy, без новых clamp/defaults.
- Fine climate write не заменяет basis wilderness status своими source inputs; финальный prepare не запускает recalculate.
- Equal counts с разными addresses дают разные structural bases; membership не выводится из coverage.outputs.
- Restart сохраняет последний basis и точные group dependencies. Old whole-row provenance не даёт invented expected.
- Для Source доказательства command address без source-read не добавляются искусственно. Подмена Source proof при том же числе expected выявляется owning usage binding.
- Tuple адресов создаёт дополнительную стоимость. Измерения 1000/4000/16000 включают построение/копирование basis, transient transport, durable размер и старые удерживаемые states. Предложение не разрешает скрытый store или заявленную линейность без измерений.

Данный trace закрывает вопрос о фактических inputs policy. Exact POJO embedding, Source usage mapping и trusted state boundary остаются предметом приёмки предлагаемого среза. Runtime-тесты в этой сверке не запускались.
