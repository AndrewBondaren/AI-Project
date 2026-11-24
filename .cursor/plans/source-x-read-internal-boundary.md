# X-READ: внутренняя граница Source и внешняя интеграция

Уточнение error mapping 2026-11-25 — source-core-error-contract.md §3: внутренние gaps проецируются в proposed MATERIALIZED_INPUT_INCOMPLETE через existing SourceLogicIssue/SourceFailure, с capture origins. Старые отметки ниже о невыбранном Source transport superseded этим owner proposal; внешние authority errors по-прежнему не переопределяются, приёмка wire delta не заявлена.

2026-11-22. Проект собственной архитектуры; X-READ transport/authority/protection/producer binding — EXTERNAL / DEFERRED. Этот документ не вводит публичный DTO или новый DAG маршрут, не утверждает foreign гарантии и не разрешает локальный implementation-срез. Требования к данным — source-closure-operands-2026-11-22.md; semantic closure v1 — source-proof-v2-contract-spec.md.

## 1. Что Source определяет сейчас

Внутренняя операция работает только с полностью материализованными immutable данными. Она не принимает scope, reader, callback, lazy iterator или authority bool. Typed tuples ниже — локальные связи уже существующих values, не wire DTO/foreign evidence mirrors. Они не удостоверяют происхождение данных: authenticity/physical integrity/finalization evidence допускаются на отдельной интеграционной границе.

Source может сейчас определить:

1. Exact ref→value связи своих witness/capture/collection values, конфликтные mappings и требуемое покрытие входного набора.
2. Правила full capture closure v1, включая невыбранные object/collection mappings каждого используемого capture.
3. Отказ от semantic evaluation при недостающем materialized operand; отличие этого случая от physical absence и semantic membership failure.
4. Pure обход уже предъявленного physical dependency graph, без discovery/IO и без интерпретации чужих bodies.
5. Local provenance и порядок diagnostics для ADMIT/READ/GROUPS/VERIFY/SELECT.
6. Условия сборки результата и postconditions; отсутствие ложного success при незакрытом входе.

## 2. Владельцы внутренних функций

Корень — `backend/app/application/worldData/sourceVersioning/`. Размещение collector остаётся `proof/closure.py` по spec; второй collector не создаётся.

| Владелец / файл | Метод / функция | Что делает / критерий отказа |
|---|---|---|
| Private функции / proof/closureInputs.py (предложение) | missing_refs(required, available) | Сравнивает exact ArtifactRef; возвращает недостающие refs, не SourceFailure/MISSING_BODY; не проверяет storage |
| Private функции / proof/closureInputs.py | capture_roots(witness_ref, witness, capture) | Перечисляет witness ref, capture_body и все body refs mappings данного capture v1; не фильтрует по selected atoms |
| Private функция / proof/closureGraph.py (предложение) | inspect_graph(roots, dependencies, admitted_refs) | Один обход вычисляет достижимость, missing entries и missing admitted content; сохраняет capture contexts |
| SourceCaptureCandidateChecker / capture/captureCandidateChecker.py | check | Общие relations полного candidate content; не finalization/physical integrity |
| SourceCaptureMembershipChecker / proof/validation/sourceCaptureMembershipChecker.py | check | Дополнительно соответствие declared usage предъявленному capture; не повторяет общие relation rules |
| SourceProofClosureCollector / proof/closure.py | collect — точная internal signature ниже | Композиция полноты, Source semantics и pure graph; внешний mapping owning evidence отделён от internal метода |
| Private occurrence functions / размещение по source-core-occurrence-mapping.md | index_*, project_origins, locate_logic, unique_logic_issues | Сохраняют actual root/occurrences; не свидетельствуют о completeness или authority |

Ни одна новая функция не требует отдельного wrapper-класса. Collector не превращается в materializer/decoder чужих форматов/retention manager. Exact public data-input signature не подменяется внутренними tuples.

### Exact pure helper contracts — собственный проект

```python
def missing_refs(
    required: tuple[ArtifactRef, ...],
    available: tuple[ArtifactRef, ...],
) -> tuple[ArtifactRef, ...]: ...

def capture_roots(
    witness_ref: SourceCaptureRef,
    witness: SourceCaptureWitness,
    capture: SourceCapture,
) -> tuple[ArtifactRef, ...]: ...

# Private tuple aliases, не public DTO или evidence token.
type RootRefs[ContextT: (SourceCaptureRef, SourceCaptureWitness)] = tuple[
    tuple[ContextT, tuple[ArtifactRef, ...]], ...]
type RootGaps[ContextT: (SourceCaptureRef, SourceCaptureWitness)] = tuple[
    tuple[ContextT, ArtifactRef], ...]
type CaptureRefs = RootRefs[SourceCaptureRef]
type CaptureRefGaps = RootGaps[SourceCaptureRef]
type DependencyGraph = tuple[tuple[ArtifactRef, tuple[ArtifactRef, ...]], ...]

def inspect_graph[ContextT: (SourceCaptureRef, SourceCaptureWitness)](
    roots: RootRefs[ContextT],
    dependencies: DependencyGraph,
    admitted_refs: tuple[ArtifactRef, ...],
) -> tuple[RootRefs[ContextT], RootGaps[ContextT], RootGaps[ContextT]]: ...
```

missing_refs сохраняет порядок первого появления required, устраняет повторы результата и сравнивает полные refs. Available означает «материализовано/допущено внешней boundary для нужной проверки», а не «лежит в storage». Caller не выводит physical absence из результата.

capture_roots принимает уже structurally пригодные, согласованные значения. Порядок roots: witness artifact, capture_body, object bodies в порядке capture mappings, collection bodies в порядке capture mappings; повторы полного ref снимаются стабильно. Функция лишь перечисляет, не подтверждает ref→value связь или committed witness. Построение canonical final durable_refs выполняется по единственному принятому ArtifactRef ordering, не по repr/строкам и не новым codec.

inspect_graph возвращает (discovered_by_capture, missing_entries, missing_admission). Предварительного обхода полноты нет: один алгоритм обходит граф отдельно в контексте каждого capture, visited имеет ключ (capture, ref). Shared ref учитывается один раз на capture, а не теряет второй origin при глобальном dedup. Для каждого достигнутого ref независимо проверяются outgoing entry и наличие в admitted_refs. Leaf требует явного entry с пустым tuple **и** admitted ref; одно не заменяет другое.

Отсутствующий entry добавляет (capture, ref) в missing_entries и прекращает только раскрытие этого узла; отсутствие admitted content добавляет пару в missing_admission. Если entry уже предъявлен, его edges обходятся даже при missing admission родителя: это позволяет собрать другие известные gaps, но не разрешает success. Нераскрытые descendants неизвестны и не объявляются полным closure. Partial discovered refs используются лишь для внутренней диагностики. Каждый gap сохраняется один раз на capture/ref, в порядке первого обхода.

Дубли parent entries с неоднозначными edges — internal input-shape failure; production admission должен отвергнуть конфликтующие owning результаты до этого метода. Missing entry/admission — обычный вычисленный факт неполного input, **не** programming exception и не MISSING_BODY. Порядок обхода фиксирован: captures в порядке proof, roots в порядке capture_roots, depth-first по порядку edges. Visited завершает циклы, но не подтверждает допустимость цикла в owning format. Graph edges предоставляет owning format evaluation; произвольный caller graph не становится evidence. Canonical final sorting по spec §9.2 выполняется только после отсутствия gaps/semantic failures.

### Internal collector: собственный контракт

```python
class SourceProofClosureCollector:
    def __init__(self, *, membership: SourceCaptureMembershipChecker,
                 candidate: SourceCaptureCandidateChecker) -> None: ...

    def collect[RootT: BaseModel](
        self, proof: SourceDurableProof, *,
        witnesses: tuple[tuple[SourceCaptureRef, SourceCaptureWitness], ...],
        captures: tuple[tuple[ArtifactRef, SourceCapture], ...],
        collections: tuple[tuple[SourceCollectionVersion, SourceCollectionBody], ...],
        dependencies: DependencyGraph,
        admitted_refs: tuple[ArtifactRef, ...],
        capture_origins: CaptureOrigins[RootT],
        object_origins: ObjectOrigins[RootT],
        collection_origins: CollectionOrigins[RootT],
    ) -> tuple[
        tuple[ArtifactRef, ...],
        CaptureRefGaps, CaptureRefGaps, CaptureRefGaps,
        tuple[SourceLogicIssue, ...],
    ]: ...
```

Return slots: canonical_refs, missing_source_values, missing_graph_entries, missing_admission, localized_logic_issues. canonical_refs непусты только при полном успешном непустом proof; при любом gap/issue возвращаются пустые canonical_refs, а не partial closure. Empty proof с пустыми gaps/issues является корректным результатом, поэтому caller обязан проверять все slots, а не только refs. Это private computed facts, не новый result POJO, public API или разрешение интерпретировать gaps как MISSING_BODY. SourceFailure с fixed operation собирает operation owner для semantic issues; public transport completeness gaps остаётся интеграционной дельтой.

Preconditions: canonical proof; origins относятся к фактическому proof и actual root; values structurally пригодны; каждая переданная value/ref пара подтверждена owning admission; refs в admitted_refs получены из успешно допущенных owning результатов для требуемых integrity/content checks. Эти tuples не доказывают authority сами по себе и не принимаются напрямую от public caller. Отсутствующие записи допустимы как неполный input; конфликтные duplicate keys недопустимы. Authority/protection assertions не переносятся в membership checker.

Collector связывает witness по full capture ref, capture по witness.capture_body, collections по full version/body mapping, а не по позиции. Missing witness/capture/decoded collection body записывает exact required ref в missing_source_values с capture context. Если witness отсутствует, будущий capture_body неизвестен: collector не выдумывает ref. Известные roots и независимые captures продолжают проверяться. Membership вызывается только при полном необходимом Source content соответствующего capture; использует общие relation rules, candidate checker второй раз не запускается. Объекты чужих форматов не декодируются Source: body refs и required edges покрывает owning admission + inspect_graph.

Graph вызывается один раз с roots по captures; при успехе refs объединяются и canonical сортируются. Discovered_by_capture сохраняет provenance до завершения checks: каждый transitive ref связан со всеми captures, где достижим. Gaps остаются typed capture/ref facts; semantic issues локализуются existing origins functions, без fake atom для required physical body. Collector не вызывает public operations, не хранит mutable invocation state и не делает IO. Его signature — собственный проект, не новый внешний контракт; evidence→tuple mapping и окончательные пять public inputs по-прежнему EXTERNAL / DEFERRED.

## 3. Внутренний trace без storage

### Candidate closure — адресная дельта 2026-11-25

Graph context generic по двум existing values: finalized SourceCaptureRef и candidate SourceCaptureWitness. Это ключ provenance, не authority или режим. inspect_graph использует visited=(context, ref), без ветвления по классу context и без второго graph engine.

Единственная `proof/closureInputs.py::capture_body_roots(capture_body: ArtifactRef, capture: SourceCapture) -> tuple[ArtifactRef, ...]` перечисляет capture body и все body mappings со stable dedup. Existing capture_roots добавляет witness artifact к результату этой функции, не дублирует enumeration.

В SourceProofClosureCollector добавляется отдельный метод closure candidate body **без witness artifact**:

```python
def collect_candidate(
    self, witness: SourceCaptureWitness, *, capture: SourceCapture,
    collections: tuple[tuple[SourceCollectionVersion, SourceCollectionBody], ...],
    dependencies: DependencyGraph,
    admitted_refs: tuple[ArtifactRef, ...],
) -> tuple[
    tuple[ArtifactRef, ...], RootGaps[SourceCaptureWitness],
    RootGaps[SourceCaptureWitness], RootGaps[SourceCaptureWitness],
    tuple[SourceLogicIssue, ...],
]: ...
```

Slots: canonical body refs, missing Source values/graph entries/admission, semantic issues. При любом gap/issue refs пусты, partial success запрещён. Constructor получает candidate checker; collect использует membership, collect_candidate — candidate, общие relation rules не запускаются дважды. Отсутствие самого capture отклоняет materialized boundary по witness.capture_body до вызова метода; пустой capture не подставляется. Missing collection останавливает зависимые relations, известные graph gaps собираются общим inspect_graph.

Предусловие ref→content correlation и structurally допустимые values сохраняется. Candidate не проверяется как committed witness и не требует witness artifact в admitted_refs. Контекст — actual SourceCaptureWitness, proof origins не выдумываются. Ошибки FINALIZE_CAPTURE имеют group/use=None; completeness использует source-core-error-contract.md.

Новая попытка finalize: completeness → collect_candidate → authoritative exact revision eligibility → exact candidate witness artifact через owning canonical format → добавить его к body closure → permitted atomic append/verify/seal/retention → confirmed result. SourceCaptureRef не создаётся ради входа в proof collect; public READ не вызывается. Committed replay по exact identity не повторяет latest eligibility новой попытки. Foreign capability/atomic binding deferred; этот trace не разрешает прямые foreign domain calls.

Проверки: body closure без committed witness; все mappings включены; один graph algorithm для обоих contexts; missing capture не empty success; никакого fabricated proof; result ref не выдаётся по одному успешному collect_candidate. Старый scoped collect_capture_body не является альтернативной реализацией нового pure метода.

1. Request checker допускает исходный proof/usage и возвращает original maps. ADMIT/GROUPS/SELECT выполняют свой pure transform; READ сохраняет исходный proof; VERIFY различает expected и presented стороны.
2. Operation owner проецирует origins на фактический output proof. Maps не восстанавливаются из synthetic request или первого совпавшего artifact.
3. Materialized boundary должна подтвердить ref→content correlation и передать owning evidence. Это интеграционный prerequisite, не новая Source IO стадия.
4. Source по предъявленным witnesses/captures определяет required Source operands. Отсутствующий body/collection/witness выявляется как неполный вход; relation checks зависимой ветви не запускаются. Доступные независимые проверки сохраняются; окончательного success нет.
5. На полном Source content выполняются общие capture relations и requested membership; неполная ветвь не выдаёт semantic INCOMPLETE_COLLECTION по отсутствию operand.
6. Source перечисляет roots полного capture v1. inspect_graph единым обходом вычисляет достижимость и оба вида graph/admission gaps по captures. Дополнительные unrelated refs не включаются. Глобальный dedup выполняется только для final refs после сохранения capture provenance и проверки отсутствия gaps.
7. Capture/atom relation issues локализуются на actual occurrences, затем стабильно устраняются идентичные итоговые logic issues. SELECT сохраняет только origins выбранных atoms; required physical bodies без logical atom локализуются через owning capture. VERIFY сверяет exact computed refs с presented refs только после успешных проверок.
8. Только после закрытия всех требуемых проверок собирается SourceProofResult/GroupsResult. Pure tuple refs отдельно не считается durable result и не выдаётся наружу в обход public операции.

Этот trace задаёт ответственность, а не второй порядок DAG. Повторный pure обход уже загруженного graph не является новым внешним read. На любом этапе запрещено дочитывание недостающего operand.

## 4. Что внешнее и чего собственные tuples не доказывают

| EXTERNAL / DEFERRED | Владелец | Что Source завершит после получения |
|---|---|---|
| Exact BLOB/SQL_ROWS results, integrity/error transport | Artifacts | Correlation mapping и типы пяти public inputs; без mirror bodies |
| Source witness committed-finalization evidence через разрешённую boundary | Source semantics + owning persistence/publication transport | Проверку admission evidence; seal не заменяет finalized |
| Authority/issuer, защита исходного набора, retention до target | Publication infrastructure / Artifacts | Допустимость owning evidence и её связь с конкретными refs; не собственный holder |
| Producer достаточного перечислимого набора | Назначение через координатора | Completeness binding; не новый Source discovery pipeline |
| Required physical edges foreign форматов | Owning body/format domain | Использование owning результата traversal без интерпретации foreign schema в Source |

Original occurrences — полностью собственная часть Source, не поле foreign authority. Exact transport неполного materialized input и invalid evidence согласуется в public Input/Output/Error дельте: сейчас не вводится новый enum и не выбирается молча SourceFailure/RuntimeError. missing_refs — только внутренний вычисленный факт, не замена такого отказа.

## 5. Что можно сделать сейчас и как принимать

**Сейчас в архитектуре ядра:** проверить и принять helper contracts и их предусловия, общий relation ownership, порядок pure стадий и origin localization; сверить единый canonical ordering; завершить внутренние тестовые сценарии. Это не требует готового Artifacts transport. Код выполняется по общему принятому implementation-порядку ядра, а не отдельным X-READ срезом.

**На интеграционном этапе:** подставить реальные owning типы в public signatures, определить evidence→internal operands mapping и completeness errors, production read/retention цепочку. Internal collector constructor/метод уже предъявлены выше и не требуют выдуманного foreign типа. До завершения integration full proof runtime не готов.

Дополнительная приёмка исправлений: graph entry leaf есть, admitted ref отсутствует → missing_admission без success; admitted ref есть, entry отсутствует → missing_entries; оба отсутствуют → оба gaps; два captures достигают одного transitive ref → два контекста gaps при одном ref итогового успешного union; отсутствие witness не создаёт фиктивный capture_body; graph completeness не проверяется вторым обходчиком до inspect_graph. Missing content не становится programming error по одному факту отсутствия.

Обязательные сценарии: root без collection body не запускает relation check; полный content с неправильным membership даёт semantic issue; пропущенный graph entry не считается leaf; unrelated available ref исключён; SELECT одного atom сохраняет full capture storage closure; shared body двух captures имеет два корректных диагностических контекста; повтор edge/ref не создаёт второй durable ref; historical versions не заменяются latest; empty proof не превращает unknown input в пустой успех. У всех pure helpers ноль IO/holders/foreign domain calls; ошибки completeness не маскируются MISSING_BODY.

Статус: собственный design предъявлен, независимая приёмка не выполнена. Внешний OPEN не блокирует дальнейшую архитектуру Source.
