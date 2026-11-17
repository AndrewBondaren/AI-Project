# Source — occurrence mapping для closure

2026-11-17. Proposal АР-1; не принятая дельта spec §12.1 и не разрешение кода. Публичные Source POJO и imports Pack неизменны. Основание — source-core-public-boundaries.md, раздел occurrence mapping.

## Переиспользование и представление

SourceProofGroupProjection уже предложен для proof/selections и не содержит original occurrences. SourceProofSelection хранит canonical ordinals, а SourceLogicIssue не содержит dependency index/path. Их не расширять для технической карты происхождения. Используются immutable tuples existing values и CheckedPath; никаких новых классов POJO, persisted schema, type ID или универсального context.

Ниже private aliases описывают только tuples в будущем `proof/origins.py`, RootT: BaseModel:

```python
type CaptureOccurrence[RootT: BaseModel] = tuple[
    int | None, int, CheckedPath[RootT, SourceCaptureRef]]
type DependencyOccurrence[RootT: BaseModel, RefT: (SourceVersionRef, SourceCollectionVersionRef)] = tuple[
    int | None, int, int, CheckedPath[RootT, RefT]]
type CaptureOrigins[RootT: BaseModel] = tuple[
    tuple[SourceCaptureRef, tuple[CaptureOccurrence[RootT], ...]], ...]
type ObjectOrigins[RootT: BaseModel] = tuple[
    tuple[SourceCaptureRef, SourceVersionRef,
          tuple[DependencyOccurrence[RootT, SourceVersionRef], ...]], ...]
type CollectionOrigins[RootT: BaseModel] = tuple[
    tuple[SourceCaptureRef, SourceCollectionVersionRef,
          tuple[DependencyOccurrence[RootT, SourceCollectionVersionRef], ...]], ...]
```

Позиции — original group/use/dependency. Group None только для одиночного запроса; dependency_index относится к исходному objects либо collections. Paths строятся существующим traversal от actual request root и не восстанавливаются из indices. Типы object/collection разделены, не различаются строковым tag. Full capture входит в ключ; source ref сравнивается целиком, включая revision. CaptureOrigins не содержит пустые declared usages, исчезнувшие из normalized proof: их ошибки проверены до transformation.

## Функции и preconditions

Все функции sync pure, без constructors/IO/semantic checks. Входные facts уже прошли request validation. Результаты сохраняют порядок original occurrences, ключи упорядочены по единственному existing canonical atom enumeration; новый codec/sort алгоритм не вводится.

```python
def index_captures[RootT: BaseModel](facts: tuple[
    tuple[SourceCaptureRef, CaptureOccurrence[RootT]], ...],
) -> CaptureOrigins[RootT]: ...

def index_objects[RootT: BaseModel](facts: tuple[
    tuple[SourceCaptureRef, SourceVersionRef,
          DependencyOccurrence[RootT, SourceVersionRef]], ...],
) -> ObjectOrigins[RootT]: ...

def index_collections[RootT: BaseModel](facts: tuple[
    tuple[SourceCaptureRef, SourceCollectionVersionRef,
          DependencyOccurrence[RootT, SourceCollectionVersionRef]], ...],
) -> CollectionOrigins[RootT]: ...

def project_origins[RootT: BaseModel](
    atoms: tuple[SourceCaptureUsage, ...], *,
    captures: CaptureOrigins[RootT], objects: ObjectOrigins[RootT],
    collections: CollectionOrigins[RootT],
) -> tuple[CaptureOrigins[RootT], ObjectOrigins[RootT], CollectionOrigins[RootT]]: ...
```

Index-функции группируют occurrences по полному ключу в порядке первого появления. `project_origins` единственная функция, которая упорядочивает/фильтрует ключи по atoms от existing SourceProofAtomIndex.enumerate(output_proof). Это не повтор union/subset: она не выбирает atoms и не строит proof. Каждый output atom обязан иметь хотя бы один original occurrence; выбранный capture обязан иметь origin. Отсутствие связи, неоднозначный origin одного исходного места, неправильные indices/path types — programming error, не SourceFailure. Пустые output atoms возвращают три пустых tuple. Extra input keys отфильтровываются именно здесь, например при SELECT; collector уже требует exact coverage без extras.

Normalizer/union/extractor сохраняют свои signatures и результаты. Request traversal один раз извлекает validated facts; index-функции не обходят request повторно. После pure transformation operation owner вызывает project_origins по фактическому результату. Это сопоставление exact keys, не повтор вычисления proof и не поиск первого совпадения. Изменение identity/revision нормализатором нарушает postcondition и обнаруживается отсутствием origin.

## Явная дельта collector

Предложение **заменить**, а не дополнить optional режимом signature §12.1:

```python
async def collect[RootT: BaseModel](
    self, scope: CommitReadScope, request: SourceProofReadInput, *,
    operation: SourceOperation,
    capture_origins: CaptureOrigins[RootT],
    object_origins: ObjectOrigins[RootT],
    collection_origins: CollectionOrigins[RootT],
) -> SourceProofResult | SourceFailure: ...
```

Все origins обязательны; default/fallback на synthetic read root запрещён. Read input здесь транспорт canonical proof/world, не источник диагностических paths. До IO collector проверяет exact coverage origins относительно proof, а также согласованность original capture/use positions. Некорректная карта или невалидный вычисленный proof — programming/postcondition failure. Authority, witness, membership и полный closure по-прежнему проверяются внутри scope; origins не являются security evidence и не заменяют эти проверки.

Это затрагивает **всех** internal callers: public proof owners, preflight/adopt, finalization consumers при использовании collect. До принятия дельты каждому требуется trace создания origins от его actual input. Не подменять эти callers synthetic SourceProofReadInput, не менять spec/S1/S2 молча. Для plain READ и adoption с actual SourceProofReadInput пути действительно начинаются от этого типа; для ADMIT/GROUPS/VERIFY/SELECT — от их исходных типов. collect_capture_body не получает эту дельту автоматически.

## Где сохраняется причинная связь ошибки

Collector привязывает issue к проверяемому capture/atom **в момент** exact read/membership проверки, пока этот ключ известен. Поиск origin в уже агрегированном SourceFailure по artifact запрещён: один artifact может обслуживать несколько dependencies. Read binding не получает новый публичный request и не приобретает ответственность за original positions.

Функция `locate_logic(issue: SourceLogicIssue, *, occurrences: tuple[tuple[int | None, int], ...]) -> tuple[SourceLogicIssue, ...]` в origins.py заменяет только group/use на явные occurrences, сохраняя code/source/artifact. Пустой occurrences tuple для capture/atom ошибки — programming error; proof-level issue не проходит через эту функцию и сохраняет оба indices=None. Collector получает occurrences из конкретной карты ключа, без enum mode/строкового kind. Для capture-wide отказа используется CaptureOrigins; для dependency — ObjectOrigins/CollectionOrigins. Независимые ветви обходятся после отказа, зависимые не запускаются.

`unique_logic_issues(issues: tuple[SourceLogicIssue, ...]) -> tuple[SourceLogicIssue, ...]` оставляет первое полное равное diagnostic в стабильном исходном порядке после локализации. Не объединяет разные source/artifact/group/use. Это request-local pure функция, не изменение shared ValidatorAggregationHelper. Field issues не дедуплицируются по коду. Порядок исходных позиций задаёт request-specific aggregation по §11.3; canonical IO порядок не становится diagnostic порядком.

## Trace и проверка

ADMIT: original uses → index → normalize → enumerate → project → collect. GROUPS: все original groups → общие indexes → union → enumerate → project → collect. READ: original persisted proof → index → enumerate/project → collect. SELECT: indexes исходного proof → extract → enumerate выбранного proof → project → collect. VERIFY: indexes **presented** result.admission.proof → matcher → enumerate/project → collect; expected groups используются matching стадией, не для IO diagnostics presented proof.

Проверки: один atom в двух groups даёт обе позиции; два повтора в одном use не дают одинаковые logic issues; один ref в разных captures не смешивается; capture-wide refusal сохраняет все original uses; SELECT сохраняет original paths при новых ordinals; VERIFY не переносит IO issue в expected; пустой proof имеет пустые maps; удалённый/лишний origin отклоняется до IO; shared artifact не определяет origin; все paths сохраняют RootT под negative typing. Проверить отсутствие нового request traversal, union/subset и новых публичных DTO.

Статус: конкретный проект решения предъявлен. До закрытия пункта нужны проверка совместимости diagnostic semantics §11.3, trace всех integration callers и принятие signature delta §12.1. Read lifetime/DAG решения остаются отдельными gates. Код, тесты и независимая приёмка этим документом не заявляются.
