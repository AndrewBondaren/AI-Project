# Pack: конкретизация массовой записи wilderness chunks

## Актуальный статус — 2026-11-16

**PASS независимой технической приёмки контрактного дополнения.** Источник: чат «Независимая приёмка Pack», thread `01a1e46f-3c4c-7db1-abfc-c7a2eb83d458`, итог повторной проверки контракта. Замечание о полноте class/POJO inventory закрыто; подтверждены обязательные DAG/ответственность/public boundary/порядок/CRUD/междоменные типы/diagnostics критерии, metadata transitions и однократная итоговая материализация basis. Открытый вопрос «массовые writes» закрыт **на уровне контрактного решения**.

Этот статус заменяет прежние «приёмка ещё не завершена» ниже, сохранённые как история. Не означает готовности реализации или доказанной производительности. Следующие delivery gates: отдельный implementation-план, single/batch equivalence и strict admission/aliasing tests, замеры 1000/4000/16000 с полным nested объёмом; DAG-интеграция последняя. Долг типизации существующих тестов не относится к этому контрактному вердикту.

2026-11-16. **Решения согласованы пользователем; техническая приёмка дополнения ещё не завершена.** После конкретизации пользователь явно подтвердил все четыре рекомендации: evidence внутри item с общей декларацией single/batch; последовательное применение metadata в локальном рабочем состоянии; запрет вывода metadata usage из payload proof; приоритет reason. Runtime не меняется. Основание: [write-план](pack-v2-public-write-operations.md), [четыре принципа](pack-bulk-write-principles.md), [status basis](pack-wilderness-status-dependencies.md).

## Публичный контракт

**Актуальная конкретизация собственных переходов Pack:** [chunk metadata transition contract](pack-chunk-metadata-transition-contract.md). В нём закрыты прежние OPEN new-tile/status usage: coarse и provisional status используют явно обоснованный empty usage; chunk item требует ADDRESS и REFINE_ROLE evidence. Прежние условные формулировки и остатки ниже читаются как история до этой конкретизации. Техническая приёмка/реализация отдельно.

Требования к входам, точные границы Source/Snapshot/Cache и ограничение остальных производителей уровнем POJO зафиксированы в [контрактах владельцев для batch](pack-batch-owner-contract-requirements.md). Правила происхождения собственных status/defaults обязан завершить Pack; их нельзя целиком переносить в неопределённый внешний mapping.

Владелец — Pack. Предлагаемые объявления в `backend/app/dataModel/worldPack/preparation/operations.py`:

```python
class PackWildernessChunkWrite(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    part: PackWildernessChunkPartInput
    refine_role: ChunkRefineRole | None
    metadata_inputs: tuple[PackMetadataInputEvidence, ...]

class PackWildernessChunkInput(PackWildernessChunkWrite):
    state: PackPreparationState

class PackWildernessChunksInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    state: PackPreparationState
    entries: tuple[PackWildernessChunkWrite, ...]

def write_wilderness_chunks(self, request: PackWildernessChunksInput) -> PackPreparationState:
    ...
```

Метод принадлежит существующему `PackPreparationService`. Ошибка — существующий `PackPreparationFailure`, несущий `PackPreparationError`; отдельный batch error/result/receipt не вводится. Конструктор DTO не становится публичным маршрутом обхода общей Pack diagnostics boundary.

`PackWildernessChunkWrite` — одна инструкция записи без state, не новый payload/provenance. Его `part` использует существующий `parts.py::PackWildernessChunkPartInput(address: PackChunkAddress, artifact: ArtifactRef, provenance: PackPartProvenance)`. Никаких повторных world/base/capture полей. `refine_role` обязателен: explicit None записывает None, не означает preserve. Оба новых DTO — только immutable данные; IO, нормализация, выбор порядка и вычисление status в них запрещены.

Предлагается разрешить пустой tuple: после обычного admission state операция возвращает эквивалентный state без изменений, пересчётов и инвалидирования. Равенство object identity не гарантируется. Это не способ пропустить проверки forged input.

**Согласованное уточнение metadata-контракта:** `metadata_inputs` размещается внутри item и использует существующий проектный `PackMetadataInputEvidence` из [metadata POJO](pack-metadata-dependency-pojo.md), не новый тип Source proof. В первоначальной форме batch это поле было пропущено; поправка отдельно подтверждена пользователем в пункте 1. Поле обязательное, без default; пустой tuple допустим только по явно установленному owning правилу отсутствия требуемого evidence, а не как обход неизвестного producer binding.

Evidence адресуется локально внутри item: VALUE/ADDRESS → `entries[i].part.address`, VALUE/REFINE_ROLE → `entries[i].refine_role`, включая None. REGION_ENTRY и прочие slots запрещены; duplicate selectors отклоняются. Fingerprint сверяется с фактическим typed значением. Индекс i задаётся положением item, отдельный batch selector/index в evidence не добавляется. Source usage берётся из предъявленного evidence и сохранённых оснований state, не извлекается эвристически из payload proof. Реальный producer binding остаётся отдельной интеграцией.

Одиночный `PackWildernessChunkInput` наследует `PackWildernessChunkWrite` и добавляет только state, как показано выше. Это одно объявление полей записи, без зеркального single carrier и без нового generic base. Batch entries принимаются как точный owning item: single request со state не допускается как элемент пакета. Проверка лишнего поля/подкласса входит в admission и negative tests; сам факт inheritance не даёт разрешения вложить state в entries. Single и batch используют один внутренний алгоритм применения. Batch не вызывает публичный single в цикле; single не должен создавать и повторно валидировать публичный batch request ради переиспользования.

## Применение и порядок

1. Проверить структуру, вложенные значения и invariants исходного state; независимо проверить доступные entries. Выявить все повторные chunk addresses внутри entries, включая одинаковые refs. Совпадение с адресом базы — разрешённый replacement, не duplicate.
2. Только после отсутствия диагностик построить локальные индексы parts и затронутых tiles. Новые локальные контейнеры не разделяются с caller и не сохраняются между вызовами.
3. Применить unique entries в порядке tuple. Предлагаемый порядок parts соответствует текущим pure writes: replacement сохраняет позицию базы; новые адреса добавляются в порядке entries. Для новых assembly rows сохраняется порядок первого появления owning адреса. Legacy `commit_chunk` перемещает заменённый chunk в конец своего списка: его порядок не выдаётся за доказательство нового flat-state порядка. Это различие должно быть явно проверено при приёмке.
4. В порядке entries применять chunk и metadata transitions к локальному рабочему состоянию. Каждый item видит результат предыдущих items, включая pending usage и invalidation. Сохраняются правила provisional перехода и отказа single операции; нельзя пропустить отказ промежуточного write из-за допустимости конечного состава. Промежуточный immutable state и полный tuple basis не собираются на каждом item: локальный membership/index обновляется инкрементально. Это уточняет прежнее требование «пересчитать один раз»: однократной является итоговая материализация, а не обход последовательных семантических проверок.
5. Для каждого затронутого tile один раз материализовать итоговые status/basis и dependency records. Provisional policy использует expected_chunks=None; replacement тоже выполняет этот переход, старый complete не сохраняется автоматически. Climate status и основания незатронутых групп сохраняются. Canonical ordering адресов basis не равен порядку parts и учитывается отдельно в стоимости. Отдельный explicit recalculate с expected остаётся отдельной операцией после batch по решению DAG.
6. Собрать один итоговый immutable state, выполнить финальную проверку допустимого промежуточного state и вернуть его. Final completeness, storage seals/holds и READY этой pure операцией не удостоверяются.

Эквивалентность single/batch проверяется по значениям частей, assembly, актуальным dependencies и пригодности provenance к bind. Не требуется создавать промежуточные states или доказывать историю исполнения. Нельзя объединять в batch записи, между которыми DAG должен выполнить describe/bind, delete, explicit recalculate или другую публичную операцию. Пакет заменяет только непрерывный участок однотипных независимых по адресам writes; не меняет утверждённый междоменный порядок.

## Metadata и provenance

Новый payload сохраняется с предъявленным owning provenance после существующих проверок. Batch не получает metadata proof и не получает новый общий capture для всего пакета.

Изменение projection/basis/фактически использованных dependencies инвалидирует соответствующий прежний binding по существующим metadata правилам. Равный status или fingerprint сам по себе не разрешает preserve proof. Неизменные независимые группы сохраняются; если whole-row attribution не позволяет безопасно сохранить нужные основания, применяется существующий отказ `METADATA_ATTRIBUTION_UNAVAILABLE`, а не выдуманная детализация.

`metadata_dependencies` итогового state хранит актуальные pending descriptions для последующего `describe_metadata`. Перенос и замена выполняются по owning группам; последний item не становится основанием всех полей tile. Полное множество payload proofs не объявляется Source usage status. Неизвестный producer mapping не заменяется пустым proof/planning tuple. Отложенный PACK-METADATA-PLANNING сохраняет статус внешней интеграции, не общего blocker Pack.

DAG передаёт итоговый state в `describe_metadata`, направляет уже описанные зависимости в согласованные Source операции и возвращает результаты в `bind_metadata_provenance`. Алгоритмы projection, basis и invalidation остаются в Pack. Новых Source/Snapshot/Cache контрактов и генераторных bindings batch не вводит.

## Ошибки

Переиспользуются `preparation/errors.py` и existing field diagnostics; пути строятся через owning FieldRef/CheckedPath, строки ниже обозначают ожидаемую адресацию:

| Нарушение | reason / code / path |
|---|---|
| Структура, missing refine_role, неверный nested тип | INVALID_INPUT / существующая field diagnostic / state или entries[i] с точным nested path |
| Повторный адрес внутри пакета | IDENTITY_CONFLICT / DUPLICATE_ADDRESS / entries[i].part.address для каждого повторного появления после первого |
| Неверный artifact format для chunk | DEPENDENCY_MISMATCH / FORMAT_MISMATCH / entries[i].part.artifact |
| Несовместимые world/base/provenance | Существующие owning reason/code single-write admission; path с префиксом entries[i].part либо state |
| Недостаточная детализация сохраняемой metadata | DEPENDENCY_MISMATCH / METADATA_ATTRIBUTION_UNAVAILABLE / соответствующая запись state.assembly_provenance |

Независимые ошибки агрегируются в существующей оболочке и существующем порядке: структура, затем доступные семантические проверки с исходными индексами. Невалидный parent исключает только зависящие от него проверки. Согласованный приоритет reason для этой pure операции: наличие структурных issues → INVALID_INPUT; иначе наличие семантических несовместимостей помимо конфликтов адресов → DEPENDENCY_MISMATCH; иначе только конфликты адресов → IDENTITY_CONFLICT. Все независимые issues сохраняются, в том числе duplicate вместе с format/provenance mismatch. При отсутствии issues ошибки нет. Это явное правило операции, а не утверждение, что существующий helper уже автоматически выбирает такой приоритет. Отказ не возвращает частичный state и не меняет вход. Inherited/new admission не ослабляется; batch не удостоверяет inherited origin самостоятельно.

## Граница реализации и приёмка

`PackPreparationService` отвечает за одну atomic pure операцию; `PackPreparationValidator` — за owning admission и диагностику; существующие immutable state/parts/assembly/dependency POJO — за данные, не orchestration. Внутренний алгоритм использует локальные индексы и существующую status policy; IO и междоменные вызовы отсутствуют. DAG вызывает публичную операцию напрямую и выбирает границы/порядок пакетов; Pack не вызывает DAG или чужие публичные API и не скрывает цепочку междоменных стадий в private orchestration.

Контрактный class/dependency/DoD inventory, mapping diagnostics и CRUD/settings сверка предъявляются в этом дополнении, включая поимённое уточнение ниже; их полнота не откладывается до implementation-плана. Будущий implementation-план сопоставляет принятый inventory с конкретными imports, вызовами и тестами, не определяет заново контрактные обязанности. Приёмка документа не означает приёмки реализации. Настройки batch, лимит числа entries и defaults не добавляются; существующие transport/resource требования сохраняются.

Обязательные проверки этого уточнения:

- single против batch на unique additions/replacements, нескольких tiles и смешанном новом/существующем составе; порядок частей проверяется отдельно;
- explicit None, complete→partial, partial→partial с изменением basis, stale bind, сохранение climate и незатронутых proofs;
- несколько ошибок в разных entries, duplicate addresses, invalid nested/forged state, невозможность безопасного whole-row preserve; отсутствие частичного результата и alias mutation;
- замеры additions/replacements на 1000/4000/16000, один большой tile и много tiles, тяжёлые provenance/basis, полный admission/конструкторы, counters/peak memory;
- ограниченное число проходов по базе/результату, отсутствие K полных обходов tile/state; стоимость O(B+U+R) с отдельно предъявленным sorting basis и owning checks; reuse adapters не превращается в cache доверия;
- describe/bind и финальный DAG transport проверяются в своих последующих срезах. Бенчмарк batch сам по себе их не принимает.

Пользовательские решения по форме и семантике зафиксированы; остаётся техническая проверка конкретных declarations, dependencies и ошибок. Четыре принципа сохраняются как требования к проекту; runtime evidence ещё отсутствует.

## Проверка 2026-11-16: результат и границы доказательства

Пользовательское «Ок, далее» принято как согласие продолжить с предложенными carriers, empty no-op и порядком результата. Это не заменяет обязательную техническую приёмку. **Результат проверки готовности этого дополнения к реализации: НЕ ПРИНЯТО**, по перечисленным ниже конкретным недостающим сведениям. Прежняя приёмка остальных Pack контрактов не отменяется.

### Статическая эквивалентность

Для unique адресов множество chunks затронутого tile после пакета равно объединению исходного множества и адресов additions. Replacement membership не меняет. Каждая непустая последовательность chunk writes оставляет в затронутом tile хотя бы один chunk. `wilderness_refine_status_without_expected` возвращает partial для положительного количества. Поэтому последний single пересчёт и один batch пересчёт дают одинаковый status=partial и одинаковый итоговый basis `(final_addresses, None)`. Для пустого пакета пересчёта нет. Это следует из `bake/wildernessRefineStatus.py` и legacy `commit_chunk/recalc_wilderness_status`, а не из benchmark.

Unique replacements сохраняют последние предъявленные ref/provenance/refine_role каждого адреса независимо от группировки. При принятом порядке flat parts replacements сохраняют позиции, additions следуют порядку entries. Никакой вывод об эквивалентности metadata usage из этой алгебры **не следует**: несколько chunks одного tile разделяют tile metadata, поэтому unique addresses не означают независимость metadata updates. Требуется отдельное правило переноса IDENTITY и WILDERNESS_REFINE_STATUS usage, включая повторное обращение к уже pending группе.

### Обязательные критерии проекта — первоначальная проверка до согласования четырёх рекомендаций

| Критерий | Основание в этом документе | Результат |
|---|---|---|
| Три запрета DAG | «Граница реализации», «Применение и порядок»: atomic pure операция, прямой caller DAG, нет междоменных вызовов/выбора стадий | Соответствует на уровне проекта; runtime wiring не предъявлено и остаётся последним срезом |
| Ответственность каждого класса, зависимости, DoD и признак нарушения | Приведены service/validator и новые carriers, но нет полного поимённого inventory вложенных state/evidence/diagnostics и внутренних helpers | Недостаточно для приёмки implementation-плана |
| Public/internal boundary | Public Input/Output/Error названы; индексы/применение не раскрыты caller | Соответствует границе; общую декларацию single/batch ещё нужно предъявить |
| Утверждённый порядок | Только непрерывные writes, запрет пересечения describe/bind/delete/recalculate | Status/basis эквивалентны статически; dependency usage и отказы промежуточных writes ещё не доказаны |
| CRUD данных: create/update/read/delete | Batch создаёт/заменяет chunk; read/describe и delete остаются существующими отдельными операциями write-плана | Scope определён; этот метод не заменяет read/delete |
| CRUD настроек: create/read/update/delete | Ни одна из четырёх операций настроек batch не добавляется; новый размер пакета/default не вводится | Изменения отсутствуют; действующее решение по настройкам не пересматривается |
| Междоменные данные и настройки | ArtifactRef, Source proof/usage и base publication — owning данные; публичных вызовов владельцев нет | Нового запроса Source не требуется; конкретный producer evidence binding остаётся интеграционным срезом |
| POJO и непересечение ошибок | Existing part/proof/evidence переиспользуются; batch carrier группирует writes | Полный field/error inventory и единый reason при смешанных semantic issues не были предъявлены; до их фиксации PASS запрещён |

### История остатка до конкретизации transitions

После явного согласия пользователя по пунктам 1–4 повторное согласование этих решений не требуется. Остались технические результаты:

1. Предъявить общую декларацию single/batch с уже согласованным item-local `metadata_inputs` и поимённый class/POJO inventory.
2. Конкретизировать последовательное применение dependencies по группам: retained attribution, уже pending usage, evidence текущих entries, stale bindings и whole-row refusal. Проверить эквивалентность, включая отказы промежуточных writes, без повторной полной сборки state/basis.
3. Завершить code/path mapping диагностик и проверить комбинации ошибок по уже согласованному приоритету INVALID_INPUT → DEPENDENCY_MISMATCH → IDENTITY_CONFLICT. Приоритет больше не OPEN; existing helper сам его не реализует.

Это локальные вопросы Pack, а не требование доработать генератор или повторно согласовать SourceDurableProof. После закрытия — повторная проверка только данного дополнения; затем отдельный implementation-план и измерения. Тесты runtime в этом документальном проходе не запускались.

## Конкретизация после согласования четырёх решений

Этот раздел уточняет остаток выше. Предшествующая таблица сохраняется как история проверки, не как актуальный перечень вопросов к пользователю.

### Правила последовательного переноса dependencies

Единица изменения — пара `(metadata address, group)`. Локальный индекс хранит текущие значения и основания; он не является новым публичным DTO, service field или session. Один публичный вызов создаёт и уничтожает свои рабочие контейнеры. Внутренняя реализация — функции модуля `application/worldData/pack/preparation/wildernessChunkWrite.py`, вызываемые service; новый публичный pipeline, класс оркестратора или callback не создаётся.

1. До changes проверить актуальность существующих descriptions относительно base/адреса/projection и полноту групп. Готовая transient description — источник проверенного usage. Durable attribution содержит selections, а не готовый SourceProofInput: batch не преобразует selection/proof в usage.
2. Для сохранения группы использовать текущее рабочее основание: сначала результат предыдущего item, иначе admitted transient description базы. Не перечитывать исходную базу на каждом item, иначе W2 потеряет изменения W1. Если нужны historical группы, их полный набор заранее импортируется существующим `import_metadata_usage` после Source extraction через DAG. Whole-row proof не заменяет отсутствующие group usages.
3. Для изменённой группы проверить evidence typed input, заменить только фактически использованные основания. Equal value не означает preserve. Не объединять все evidence пакета и не присваивать последнему item происхождение всей строки. Если новое значение использует несколько оснований, состав определяется owning правилом поля, не общим union всех payload proofs. Нормализация/семантическая проверка Source остаётся у Source.
4. Если для данного перехода нет достаточных оснований сохранения/вычисления, отказать до dependent изменения. После отказа продолжить независимые input checks; не вычислять последующие transitions, зависящие от несуществующего успешного результата. Внешний результат всего пакета — отказ. Рабочие изменения до отказа отбрасываются.
5. При замене группы убрать старую пригодность row binding, сохранив основания остальных групп в локальной карте. На выходе изменённая строка получает полный pending description с новым subject; её прежний durable row proof не выдаётся за proof нового результата. Неизменённые строки сохраняют provenance. Безопасный whole-row preserve разрешён только при доказанно неизменной строке и её основаниях.
6. Финальные descriptions упорядочены по итоговому owning порядку metadata; группы — по owning roster. Один address имеет один description, одна группа — одну запись. Число промежуточных items не создаёт журнал descriptions. Материализация subject/fingerprint и полного basis выполняется после локальных transitions; доступные для проверки локальные значения не требуют полного immutable state на каждом шаге.

| Изменяемая группа | Правило данных и оснований |
|---|---|
| Chunk IDENTITY | Адрес определяется item.part.address; identity evidence относится именно к нему. Для существующей identity сохранить прежнее основание только по owning preserve правилу, не по равенству координат автоматически |
| Chunk REFINE_ROLE | Записать explicit refine_role, включая None; evidence REFINE_ROLE сверить с этим значением. Предыдущее основание роли заменяется |
| Existing tile IDENTITY | Сохранить текущее основание tile identity; chunk evidence не становится новым основанием существующего tile |
| Existing tile CLIMATE_STATUS | Сохранить значение и usage без изменений. Недоступный historical usage нельзя заполнить payload proof текущего chunk |
| New tile IDENTITY / CLIMATE_STATUS | Создать по существующим owning правилам identity/default climate. Допустимость empty Source usage должна следовать принятому правилу source-independent значения; batch не вводит новый default или фиктивный proof |
| Tile WILDERNESS_REFINE_STATUS | Каждый item выполняет provisional transition над текущим membership. Итоговый basis — final addresses и expected=None. Usage должен соответствовать реально использованным membership основаниям; адреса basis сами по себе не являются Source reads. Для replacement нельзя просто сохранять прежнее expected или proof complete |

**Граница конкретности:** таблица определяет перенос и место данных, но не придумывает отсутствующий producer mapping для source-derived membership/new tile identity. В [status dependencies](pack-wilderness-status-dependencies.md) такой mapping отмечен отдельно. Нельзя объявлять эти случаи семантически принятыми, пока не предъявлено owning правило. Это ограничение зависимого metadata маршрута; оно не отменяет готовность остальных Pack операций и не требует интеграции генератора сейчас.

### Диагностика дополнения

Все paths ниже относительны batch request; single использует те же leaf fields без `entries[i]`. Реализация строит paths через FieldRef/CheckedPath. Структурные ошибки не получают зеркальный Pack semantic code.

| Predicate | Code | Path |
|---|---|---|
| Повторный input chunk address | DUPLICATE_ADDRESS | entries[i].part.address, каждое повторное вхождение после первого |
| Descriptor не соответствует owning wilderness payload format | FORMAT_MISMATCH | entries[i].part.artifact; применяется существующий owning format predicate, версия не дублируется literal в batch |
| New payload proof другого world; inherited input без предусмотренного verified admission | SOURCE_PROOF_MISMATCH | entries[i].part.provenance |
| State description использует другую base publication | BASE_PUBLICATION_MISMATCH | state.metadata_dependencies[k].subject.base_publication |
| Usage другого world | SOURCE_PROOF_MISMATCH | entries[i].metadata_inputs[j].source_usage.world_uid либо state.metadata_dependencies[k].dependencies[g].source_usage.world_uid |
| Обязательный evidence slot отсутствует | METADATA_INPUT_MISMATCH | entries[i].metadata_inputs |
| Лишний/повторный slot или непригодный selector | METADATA_INPUT_MISMATCH | entries[i].metadata_inputs[j].input |
| Evidence fingerprint не соответствует typed значению | METADATA_INPUT_MISMATCH | entries[i].metadata_inputs[j].value_fingerprint |
| Неполный/лишний/повторный набор state groups | METADATA_GROUP_MISMATCH | state.metadata_dependencies[k].dependencies для отсутствующей; dependencies[g].group для предъявленной |
| Неверный/stale status basis | METADATA_BASIS_MISMATCH | state.metadata_dependencies[k].dependencies[g].basis либо state.assembly_provenance[k].attribution.groups[g].basis |
| Preserve требует недоступной historical детализации | METADATA_ATTRIBUTION_UNAVAILABLE | state.assembly_provenance[k].attribution; при отсутствующей записи — state.assembly_provenance без выдуманного индекса |

Остальные state structural/identity checks сохраняют owning validator paths под `state`. Конфликт адресов классифицируется по predicate, не по произвольному тексту message. Для перечисленных issues применяется согласованный reason priority; duplicate evidence/group — semantic metadata mismatch, а не конфликт part addresses. Ошибки, обнаруженные в рабочем переходе, адресуются исходному item либо исходной state записи; индексы локальных контейнеров наружу не выдаются. SourceFailure не возникает как результат вызова Source внутри batch: такого вызова нет.

### Ответственность и проверяемые границы типов

Пути dataModel ниже относительно `backend/app/dataModel/`, application — относительно `backend/app/application/`. Неизменяемые транзитивные типы сохраняют определения owning модулей, batch не объявляет их копии.

| Класс / owning модуль | Роль, зависимости и эффекты | DoD / признак нарушения |
|---|---|---|
| PackWildernessChunkWrite, PackWildernessChunkInput, PackWildernessChunksInput — worldPack/preparation/operations.py | Поля приведены выше; Pack data-only; наследование single, tuple items batch | Один набор declarations; отказ на nested state/extra keys / дублирование полей или IO запрещены |
| PackWildernessChunkPartInput, _PackPartInput — worldPack/preparation/parts.py | address/artifact/provenance, специализация существующего generic | Только chunk address / новый зеркальный payload carrier запрещён |
| PackChunkAddress, PackTileMetadataAddress, PackChunkMetadataAddress — worldPack/preparation/addresses.py | Typed identity соответствующего payload/tile/chunk, координаты из owning деклараций | Exact address scope / вывод source provenance из координат запрещён |
| PackStoredPart — worldPack/meta/parts.py | Итоговые address/artifact/PackStoredProvenance | Адрес совпадает с применённым item / чужой proof или payload mutation запрещены |
| PackPreparationState, _PackCompositionFields — worldPack/preparation/state.py, worldPack/meta/packCompositionFields.py | base, parts, assembly, provenance, pending descriptions; единый immutable результат | S0 неизменен, один результат / command log, state cache или частичный output запрещены |
| PackAssemblyInput, PackTileAssembly, PackChunkAssembly — worldPack/preparation/assembly.py | Existing header/collections; tile coordinates/statuses/chunks; chunk coordinates/refine_role | Незатронутые fields сохраняются / переинициализация climate/header запрещена |
| PackMetadataInputEvidence, PackMetadataValueInputSelector, PackMetadataRegionInputSelector — проект metadata POJO | input selector/fingerprint/usage; в этом методе только VALUE ADDRESS/REFINE_ROLE | Exact field binding / вычисление fingerprint в DAG или REGION_ENTRY в chunk item запрещены |
| PackMetadataSubject — worldPack/preparation/metadataSubject.py | base_publication/address/value_fingerprint | Соответствие итоговой projection / трактовка hash как proof запрещена |
| PackMetadataDescription, PackMetadataDependencyUse — worldPack/preparation/metadataDependencies.py | subject/dependencies; group/source_usage/basis | Полная актуальная карта групп / скрытая история и fake empty usage запрещены |
| PackWildernessStatusBasis — worldPack/meta/metadataAttribution.py | chunk_addresses/expected_chunks, Pack-owned snapshot расчёта | Final membership, expected=None / Source usage из одного count запрещён |
| PackStoredAssemblyProvenance, PackMetadataAttribution, PackMetadataGroupAdmission — worldPack/meta/metadataAttribution.py | address/provenance/attribution; groups; group/selection/basis | Preserve только при выполненных условиях / reinterpret selection как готового usage запрещён |
| PackStoredProvenance, PackNewPartProvenance, PackInheritedPartProvenance — worldPack/preparation/provenance.py | source_proof/planning, discriminated admission mode | Existing new/inherited validation / создание Source proof и ослабление inherited admission запрещены |
| ArtifactRef — artifacts/references.py; WorldPublicationRef — worldSnapshot/identity/publication.py | Внешние immutable artifact/base identities; перенос existing полей | Owning type/identity checks / seal/hold или pin authenticity из pure DTO не доказываются |
| SourceProofInput, SourceDurableProof, SourceProofSelection, PlanDependency | Поимённые owning declarations, поля и границы приведены в уточнении ниже | Нет зеркальных Source DTO / subset verification, normalization, adoption внутри batch запрещены |
| PackPreparationService — application/worldData/pack/preparation/packPreparationService.py | Public single/batch admission → local apply → finalize; зависит от Pack helpers/validator | Atomic result и прямой caller DAG / выбор следующей публичной операции запрещён |
| PackPreparationValidator — application/worldData/pack/preparation/packPreparationValidator.py | Existing structural/identity/group/basis checks, без IO | Aggregation и точные paths / исправление входного state вместо отказа запрещено |
| PackPreparationIssue, PackPreparationError — worldPack/preparation/errors.py; PackPreparationFailure — application/worldData/pack/preparation/errors.py | code/path/message; reason/issues; exception carrier | Существующая единая оболочка / новый batch error union или потеря leaf issues запрещены |
| JsonFieldError, WireShapeIssue, ValidatorAggregationHelper, FieldRef, CheckedPath | Поимённые owning declarations и DoD приведены в уточнении ниже | Исходные индексы и strict validation / fail-fast независимых ветвей или string-built paths запрещены |

Enum types PackMetadataGroup, PackMetadataInputField и owning ChunkRefineRole переиспользуются без новых вариантов. Поимённый admission неизменяемых location/settlement/region records приведён ниже. Полный runtime import inventory проверяется отдельно при реализации, а не выдаётся за выполненный данным документом.

### Поимённое уточнение контрактного inventory

Это часть текущей приёмки дополнения по пунктам 1 и 6 обязательного правила, а не задача будущей реализации. Пути в таблицах относительно `backend/app/dataModel/`, если не указано иное. Поля перечислены для сверки использования, их определения и ограничения остаются только в указанных owning declarations. Все перечисленные POJO — данные без IO; batch повторно проверяет предъявленные значения, включая forged input, и не вызывает публичные операции их владельцев. Критерии ниже нормативны для batch и не утверждают, что его реализация уже предъявлена.

**Source и Planning.** Source владеет формой usage/proof/selection и их owning admission; Pack — соответствием мира базе и применимостью evidence к своей projection. Сохранённая selection не становится usage без согласованного Source SELECT через DAG до зависимой записи. Наличие POJO не доказывает committed capture, subset, seal или retention.

| Класс → owning declaration; поля | Допустимая зависимость / эффект в batch | DoD / критерий отказа |
|---|---|---|
| SourceProofInput → `sourceVersioning/sourceProofInput.py`; world_uid, uses | Pending dependencies и input evidence; перенос объявленного usage с исходным порядком, без нормализации | Повторный structural admission; world соответствует базе и captures. Несовпадение мира — SOURCE_PROOF_MISMATCH; подмена declared usage payload proof запрещена. Empty uses допускается только по правилам transitions |
| SourceDurableProof → `sourceVersioning/sourceDurableProof.py`; schema_version, world_uid, uses | Stored provenance; перенос принятого proof без изготовления нового | Owning schema и persisted-shape constraints, включая единственность captures и dependency identities; мир сверяется с базой. Структурное нарушение — field diagnostic; несовпадение мира — SOURCE_PROOF_MISMATCH. Успех этих проверок не означает Source admission/adoption |
| SourceProofSelection → `sourceVersioning/sourceProofSelection.py`; proof_fingerprint, dependency_indices | Attribution одной metadata-группы; перенос selection как данных | Owning fingerprint shape и strictly increasing unique nonnegative indices. Структурный отказ при нарушении; matching fingerprint, bounds и SELECT не реализуются повторно внутри batch. Недостаточные сохранённые основания — METADATA_ATTRIBUTION_UNAVAILABLE по существующему правилу preserve |
| SourceCaptureUsage → `sourceVersioning/sourceCaptureUsage.py`; capture, dependencies | Вложение uses; immutable ссылка, без разворачивания capture в полный read set | Owning проверка мира objects/collections относительно capture; структурный отказ при нарушении. LibraryMemberId сохраняет owning исключение global identity; Pack не вводит ему world_uid |
| SourceCaptureRef → `sourceVersioning/sourceCaptureRef.py`; world_uid, artifact | Identity capture внутри usage | Owning witness shape artifact (kind/format/version/row_count); structural refusal при несовместимости. Чтение witness, finalization и удержание closure внутри batch запрещены |
| SourceDependencySet → `sourceVersioning/sourceDependencies.py`; objects, collections | Объявленные зависимости capture | Типизированные tuples SourceVersionRef / SourceCollectionVersionRef; structural refusal при неверном вложении. Batch не дедуплицирует и не нормализует declared usage; ограничения persisted proof проверяются его owning декларацией |
| SourceVersionRef → `sourceVersioning/sourceVersionRef.py`; object_id, revision | Точная ревизия объекта в usage | Owning SourceObjectId и SourceRevision из `sourceVersioning/sourceObjectId.py` / `sourceVersioning/sourceObjectRevision.py`; structural refusal при неверном варианте/ревизии. Не заменяет membership revision |
| SourceCollectionVersionRef → `sourceVersioning/sourceVersionRef.py`; collection_id, revision | Точная ревизия membership в usage | Owning SourceCollectionId и SourceRevision из тех же модулей; structural refusal при неверном вложении. Не подменяется набором object refs |
| PlanDependency → `planning/contracts/planDependency.py`; slot, ref | Перенос planning tuple в provenance | Непустой typed slot и PlanRef; structural refusal при нарушении. Batch не строит, не выполняет и не разрешает планы; не заменяет metadata Source usage планом |
| PlanRef → `planning/identity/planRef.py`; key, output_fingerprint | Вложенная identity завершённой ревизии плана | Owning PlanKey из `planning/identity/planKey.py` и ограничения output_fingerprint; structural refusal при нарушении. Наличие ссылки не удостоверяет выполнение producer request |

**Незатронутые assembly records.** Владелец этих форм — Pack. Их tuple-order и все значения сохраняются. Независимая проверка уникальности UID использует валидность самого UID, а не всей записи; неверный статус/volume/bbox не скрывает дубликат. Это тот же admission state, что у single, без новой политики исправления или полноты manifest.

| Класс → owning declaration; поля | Допустимая зависимость / эффект в batch | DoD / критерий отказа |
|---|---|---|
| PackLocationAssembly → `worldPack/preparation/assembly.py`; location_uid, territory_volume, climate_status | `assembly.locations`; EntityUid, TerritoryVolume, ClimateBakeStatus | Strict field admission и уникальность location_uid внутри locations; structural issues и независимый DUPLICATE_ADDRESS агрегируются. Изменение volume/status/UID этой операцией запрещено |
| PackSettlementAssembly → `worldPack/preparation/assembly.py`; location_uid, territory_volume, structure_status, packed_district_uids | `assembly.settlements`; EntityUid, TerritoryVolume, SettlementStructureStatus, tuple EntityUid | Strict field admission и уникальность location_uid внутри settlements; structural issues и независимый DUPLICATE_ADDRESS агрегируются. Изменение district tuple или structure_status запрещено |
| TerritoryVolume → `worldPack/wire/territoryVolume.py`; x0, y0, z0, x1, y1, z1 | Вложенный volume обеих записей; Pack использует `worldPack/preparation/nestedAdmission.py::strict_metadata_record` | Проверка всех integer bounds, обязательных и лишних полей до owning normalization; structural refusal при нарушении формы. Owning упорядочивание bounds не переопределяется этим дополнением. Генерация/перемещение территории и вызов placement policy не входят в batch |
| WildernessRegionEntry → `worldPack/meta/wildernessRegionEntry.py`; region_uid, entry_type, current_type, bbox, status, parent_region_uid, spec_fingerprint | `assembly.wilderness_regions`; TerrainKey, RegionIndexBounds, WildernessRegionStatus | Strict nested admission и owning parent_contract; уникальность region_uid независимо от других полей. Structural issues и DUPLICATE_ADDRESS сохраняются; изменение типа/статуса/parent/fingerprint запрещено. Batch не запускает отдельное разрешение live region state |
| RegionIndexBounds → `worldPack/meta/wildernessRegionEntry.py`; x_min, y_min, x_max, y_max | Вложенный bbox region entry | Integer coordinates и ordered bounds по owning декларации; structural refusal при нарушении. Пересчёт bbox из payload запрещён |

Enum/identity declarations для этих строк: `identity/uid.py::EntityUid`, `worldPack/wire/climateFieldWire.py::ClimateBakeStatus`, `worldPack/meta/worldPackManifest.py::SettlementStructureStatus`, `worldPack/meta/wildernessRegionEntry.py::WildernessRegionStatus`, `terrain/worldTerrainRegistry.py::TerrainKey`. Они задают допустимые значения полей, не новые сервисы или effects; неизвестный вариант отклоняется owning field admission. Проверки полного manifest и отдельные region-index операции не добавляются в batch под видом admission.

**Диагностика и пути.** Владельцы — общие домены validation/fields; Pack владеет только своими semantic codes и reason. Ниже перечислены переиспользуемые носители и инструменты, без второго batch error union.

| Класс → owning declaration; поля / состояние | Допустимая зависимость / эффект | DoD / критерий отказа |
|---|---|---|
| FieldPathError → `validation/diagnostics/fieldPathError.py`; code, path, message | Generic база named JsonFieldError и PackPreparationIssue | Только concrete named subclasses с owning enum; конструирование generic carrier или новый зеркальный batch carrier запрещены |
| JsonFieldError → `validation/importIssues/jsonFieldError.py`; code/path/message, location, wire_path, schema_id, pydantic_type | Ошибка поля известного POJO; JsonValidationCode и typed path | Канонический path и фактический wire_path с исходным индексом; SCHEMA_VIOLATION согласован с pydantic_type. Потеря nested path или повторная semantic ошибка для того же отсутствующего поля — отказ |
| WireShapeIssue → `validation/importIssues/wireShapeIssue.py`; code, location, message, pydantic_type | Структурная ошибка без объявленного POJO-поля | Точная WireLocation и owning JsonValidationCode; не выдумывать FieldRef для extra key. Подмена field issue общей строкой запрещена |
| ValidatorAggregationHelper → `validation/diagnostics/validatorAggregationHelper.py`; admitted classes, локальный список issues | Сбор независимых диагностик одного вызова, snapshot/raise_if_any | Принимает только объявленные concrete immutable issues, сохраняет порядок. Состояние между вызовами, fail-fast независимых ветвей или возврат частичного state запрещены |
| FieldRef → `fields/fieldRef.py`; model, select | Один typed selector для чтения и имени поля, через `fields/fieldBinding.py::bind_field` | Selector относится к owning POJO; отдельные строковые имена полей вместо binding запрещены |
| CheckedPath → `fields/checkedPath.py`; root/current/segments | Локальное построение root/field/item/variant path, freeze в ValidatedFieldPath | Каждый шаг соответствует owning annotation, исходный индекс не перенумеровывается после filtering; неверный шаг — programming error CheckedPathError, не пользовательская ошибка Pack |
| ValidatedFieldPath → `fields/validatedFieldPath.py`; root, segments | Сериализуемый результат CheckedPath, переиспользуется в FieldPathError | ModelIdentity и непустой tuple PathSegment из того же модуля; batch не объявляет альтернативный path carrier и не принимает произвольную строку вместо проверенного пути |
| ModelIdentity → `fields/validatedFieldPath.py`; module, qualname | Identity owning POJO в root/field/variant | Ссылка на owning model, не произвольная подпись; несоответствие модели пути — programming error |
| FieldSegment → `fields/validatedFieldPath.py`; kind, owner, name | Шаг объявленного поля | Owner/name получены из typed binding; выдуманное поле запрещено |
| IndexSegment → `fields/validatedFieldPath.py`; kind, index | Шаг элемента коллекции | Nonnegative exact integer, исходная позиция; перенумерация после filtering запрещена |
| KeySegment → `fields/validatedFieldPath.py`; kind, key | Шаг ключа mapping в общем path carrier | Owning strict string/integer key; подмена field или index произвольным ключом запрещена |
| VariantSegment → `fields/validatedFieldPath.py`; kind, branch | Шаг конкретной POJO-ветви union | Branch ModelIdentity соответствует варианту owning union; неверная ветвь — programming error |
| WireLocation → `validation/importIssues/wireLocation.py`; parts | Положение structural issue в предъявленном документе | Tuple WirePart (strict string / nonnegative strict integer), пустой tuple означает document root; потеря позиции при переносе diagnostics запрещена |

Для всех строк: нарушения формы поступают в существующие JsonFieldError/WireShapeIssue; смысловые нарушения Pack — в PackPreparationIssue, затем в PackPreparationError/PackPreparationFailure с приоритетом из § «Ошибки». Ошибки программирования path/collector не маскируются как некорректный пользовательский input. SourceFailure не создаётся pure batch: это результат отдельной Source-операции через DAG в согласованном exchange.

Основание отсутствия дублей: batch вводит только PackWildernessChunkWrite и PackWildernessChunksInput; single наследует общие поля записи. Usage, proof, selection, planning, незатронутые assembly records и диагностические носители берутся из перечисленных owning declarations. Новых зеркал или исключений на дублирование нет. Данный inventory предъявлен для повторной независимой приёмки документа; фактические imports, strict-admission, equivalence, aliasing и performance остаются проверками реализации, не отложенными требованиями к описанию контракта.

### Повторная проверка дополнения

Закрыты на уровне документа: форма single/batch без повторного объявления полей; последовательность local metadata transitions; источник historical usage и запрет Source-вызова; table code/path и смешанный reason; ответственность перечисленных типов; сохранение CRUD/settings и DAG границ. Нового согласования четырёх решений не требуется.

Статическое доказательство single/batch теперь имеет явное условие: оба используют один переход над одной рабочей моделью групп. По индукции после каждого успешного item значения и основания равны одиночному переходу; на первом зависимом отказе batch не выдаёт результат. Итоговая материализация сохраняет эти значения. Это критерий для реализации, не доказательство существующего кода: single chunk writer с этой metadata семантикой ещё не предъявлен.

**Актуальный статус после конкретизации transitions:** собственные правила membership/new tile описаны в [transition contract](pack-chunk-metadata-transition-contract.md); отсутствие mapping больше не является текущим OPEN этого дополнения. Требуется независимая техническая приёмка самих правил, их согласованности с ТЗ, POJO/error границ и порядка single/batch. PASS заранее не выставляется. Producer execution binding остаётся отдельной интеграцией и не заменяется наличием POJO. Runtime strict-admission/aliasing/performance tests требуются для приёмки будущей реализации, не для предварительной приёмки документа. Долг типизации существующих тестов и результаты manifest/preparation прогонов относятся к другой линии приёмки и не закрывают контракт массовых writes.
