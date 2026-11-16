# Pack: конкретизация массовой записи wilderness chunks

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

До реализации отдельный implementation-план должен предъявить полный class/dependency/DoD inventory, exact mapping всех переиспользуемых single diagnostics и CRUD/settings сверку по обязательным критериям проекта. Этот документ не подменяет такую приёмку. Настройки batch, лимит числа entries и defaults не добавляются; существующие transport/resource требования сохраняются.

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

### Остаток именно batch-контракта

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
| SourceProofInput, SourceDurableProof, SourceProofSelection — sourceVersioning owning модули; PlanDependency — planning/contracts/planDependency.py | Existing usage/proof/selection/planning values; Pack их переносит, не исполняет owning операции | Нет зеркальных Source DTO / subset verification, normalization, adoption внутри batch запрещены |
| PackPreparationService — application/worldData/pack/preparation/packPreparationService.py | Public single/batch admission → local apply → finalize; зависит от Pack helpers/validator | Atomic result и прямой caller DAG / выбор следующей публичной операции запрещён |
| PackPreparationValidator — application/worldData/pack/preparation/packPreparationValidator.py | Existing structural/identity/group/basis checks, без IO | Aggregation и точные paths / исправление входного state вместо отказа запрещено |
| PackPreparationIssue, PackPreparationError — worldPack/preparation/errors.py; PackPreparationFailure — application/worldData/pack/preparation/errors.py | code/path/message; reason/issues; exception carrier | Существующая единая оболочка / новый batch error union или потеря leaf issues запрещены |
| JsonFieldError, WireShapeIssue; ValidatorAggregationHelper; FieldRef, CheckedPath — existing validation/fields owning модули | Field diagnostics, сбор независимых issues, typed path construction | Исходные индексы и strict validation / fail-fast независимых ветвей или string-built paths запрещены |

Enum types PackMetadataGroup, PackMetadataInputField и owning ChunkRefineRole переиспользуются без новых вариантов. Неизменяемые location/settlement/region records внутри state проходят прежний admission и сохраняются; batch не добавляет им методов или эффектов. Полный runtime import inventory проверяется отдельно при реализации, а не выдаётся за выполненный данным документом.

### Повторная проверка дополнения

Закрыты на уровне документа: форма single/batch без повторного объявления полей; последовательность local metadata transitions; источник historical usage и запрет Source-вызова; table code/path и смешанный reason; ответственность перечисленных типов; сохранение CRUD/settings и DAG границ. Нового согласования четырёх решений не требуется.

Статическое доказательство single/batch теперь имеет явное условие: оба используют один переход над одной рабочей моделью групп. По индукции после каждого успешного item значения и основания равны одиночному переходу; на первом зависимом отказе batch не выдаёт результат. Итоговая материализация сохраняет эти значения. Это критерий для реализации, не доказательство существующего кода: single chunk writer с этой metadata семантикой ещё не предъявлен.

**Полный PASS на реализацию всего metadata batch пока не выставляется.** Остаток конкретный: owning mapping source usage для membership/new tile defaults не представлен, поэтому переходы этих групп пока не заданы полностью; неизвестное основание не заменяется пустым usage. Внешняя часть mapping остаётся выделенной интеграцией; остальные Pack срезы могут продолжаться. Следующий implementation-план обязан явно отделить доступную Pack работу от этой интеграции, не возвращая генератор в текущий scope. Runtime strict-admission/aliasing/performance tests ещё не выполнялись: они требуются для приёмки реализации, а не как предварительное условие приёмки документа.
