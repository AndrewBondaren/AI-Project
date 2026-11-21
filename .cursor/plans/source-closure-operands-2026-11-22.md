# Source closure: operands и correlation для X-READ

Требования потребителя Source, 2026-11-22; адресное уточнение существующего AR-1 data-input gap координатору. Не новый DTO, public signature, разрешение нового порядка DAG или принятие foreign контракта. Основание: source-proof-v2-contract-spec.md full capture closure v1 и source-core-public-boundaries.md выбранный Artifacts → DAG → Source путь. Старый collect(scope, ...) не возвращается.

## 1. Что требуется semantic evaluation

| Operand | Correlation, проверяемая Source | Граница владельца |
|---|---|---|
| Проверенный canonical proof | world/schema, полный SourceCaptureRef каждого use, original-request origins | Source; proof не сертификат физического чтения |
| Witness content и evidence committed finalization | exact witness ArtifactRef из capture ref, world/capture_uid/capture_body | Source определяет finalization semantics; generic Artifacts seal недостаточен |
| Полный SourceCapture | exact capture_body ref из witness; world; objects/collections mappings | Source decode/relations; Artifacts подтверждает physical identity/integrity своего результата |
| Все object body mappings capture v1 | exact SourceVersionRef → ArtifactRef; historical revision, не latest | Source mapping; semantic body и required storage refs — owning format contract |
| Все collection bodies capture v1 | exact collection version/body; membership/world/descriptor, SET/SEQUENCE | Source membership semantics; physical verification — owning reader |
| Required storage dependencies каждого body | exact parent ref/format/version и authoritative owning format traversal | Не выводить зависимости из произвольных JSON полей и не писать traversal чужого формата в Source |
| Evidence покрытия protected набора | Физические refs набора покрывают required closure; корреляция с owning результатом, не caller bool | Artifact set/authority/lifetime — Artifacts/publication; capture/history semantics не передаются Artifacts |

Source должен проверить witness → capture → mappings → bodies → required dependencies. Для одного используемого capture v1 полный closure включает также невыбранные body mappings. Subset меняет заявленные atoms; не превращает full capture closure v1 в частичный. VERIFY сравнивает предъявленные refs с вычисленным exact closure. Empty proof не требует выдуманных refs.

## 2. Материализованные данные и раскрываемые ссылки

Один witness read не материализует capture body. Capture body раскрывает object/collection refs; collection content — member identities, сопоставляемые с exact mappings capture; owning format может раскрывать дополнительные physical refs. Ссылка сама по себе не является загруженным содержимым или доказательством доступности.

Законченная Source evaluation должна получить все необходимые immutable значения/owned bytes и owning evidence. Если результат чтения содержит только roots, в нём недостаточно operands для обещанного полного SourceProofResult. Source не дочитывает storage и не запускает очередной Artifacts read из collector. Выбор внешней цепочки получения недостающих operands требует существующего согласованного маршрута DAG; этот документ не вводит рекурсивные ноды, callbacks или новый partial-result API.

Нельзя требовать, чтобы Artifacts сам понимал captures/history или вычислял Source semantic closure. Artifacts получает свои physical identities/sets. Exact способ подготовки достаточного набора остаётся частью X-READ. Source перечислил требуемые данные, не подменил отсутствующий owning transport зеркалом.

## 3. Три разных lifetime

1. **Physical IO:** защищённый исходный набор должен существовать до первого чтения и покрывать все зависимости, которые вправе раскрыть операция. Read protection предотвращает GC между root и последующим чтением зависимости. Owner гарантирует integrity/consistency фактически выданных данных.
2. **Pure evaluation:** когда все необходимые данные полностью материализованы и принадлежат вызову, Source не требует живого DB scope/read guard только ради вычислений над immutable bytes/values. Это не даёт права читать дополнительные refs и не продлевает durability артефактов.
3. **Target acquisition:** если результат нужен для публикации, storage refs должны непрерывно оставаться удержанными до подтверждённого приобретения target holds. Завершение физического чтения не разрешает освобождение последней защиты. Эту гарантию обеспечивает согласованная owning retention/lifecycle цепочка; SourceProofResult не lease и не receipt. Source не освобождает исходный root.

Следовательно, read transaction lifetime и retention lifetime могут различаться. Точный транспорт evidence, bounded reads, ошибки incomplete set/expired authority и handoff принадлежат owning контракту; Source не вводит bool protected и не маскирует инфраструктурный отказ как MISSING_BODY.

## 4. Проверки цепочки до приёмки

- Два historical captures одной identity: различаются full refs, нет latest substitution.
- Witness загружен, capture/body отсутствует в данных: запрещён successful полный result.
- Selection одного atom при нескольких mappings: полный closure capture v1 сохранён.
- Полностью материализованные данные: pure evaluation не обращается к storage и не нуждается в DB scope.
- GC после root read не удаляет ещё не прочитанную зависимость защищённого набора.
- Между evaluation и target acquisition не освобождается последняя retention protection.
- Physical seal без committed Source witness evidence не принимается как finalized.

Ни эти сценарии, ни перечень operands не закрывают X-READ; exact owning IO/Error/protection контракт ожидается через координатора. Это не prerequisite Time/Lifecycle nodes.

## 5. Граница полного materialized input и producer responsibility

Уточнение по ответу координатора 2026-11-22. Предложения Artifacts `read_verified(Input(ref, authority, max_bytes)) → Output(request, payload: bytes)` и отдельного rows reader с max_rows/content пока не accepted: authority/issuer и полный error contract OPEN. Здесь эти имена не объявляются доступными imports.

**Граница:** до запуска законченной semantic closure evaluation должны быть доступны все значения §1. На этой границе нет lazy readers, callbacks, iterators с IO, scope или функции «получить следующий body». Source может обходить только уже материализованные данные. Обнаруженный required ref без соответствующего owning результата означает неполноту входного набора, а не разрешение чтения. Это не доказательство физического отсутствия artifact; код MISSING_BODY по одному отсутствию во входе недопустим. Exact transport такого отказа включён в незавершённую data-input дельту, новый код здесь не вводится.

Полнота проверяется Source по следующему соответствию существующих values:

1. Каждый `SourceCaptureUsage.capture.artifact` соответствует exact witness result и Source finalization evidence. Witness world совпадает с capture ref; capture_uid не заменяется content hash.
2. `SourceCaptureWitness.capture_body` соответствует exact materialized `SourceCapture` и owning physical read result. Все его mappings учитываются для full capture closure v1.
3. `SourceCapture.objects[*].source/body` и `collections[*].source/body` связывают exact revisions с результатами чтения. `SourceCollectionBody.collection/members` проверяются относительно этих mappings и descriptor rules; collection version не подменяется object version.
4. Для каждого required physical ref, определённого owning format contract, имеется exact owning result/evidence. Source не интерпретирует неизвестный формат и не превращает arbitrary bytes в foreign POJO.
5. Coverage результата ограничивается проверенным Source closure. Дополнительные данные защищённого исходного набора не становятся автоматически `durable_refs`; запрещённые/несогласованные duplicates и conflicting values не разрешаются выбором первого результата.

Это mapping существующих Source моделей, не определение нового общего materialized DTO. Witness SQL_ROWS content и BLOB bytes имеют разные owning результаты; их нельзя объединить безтиповым dict или зеркальным Source wrapper. Полный exact публичный input появится только после сверки owning типов.

| Участник | Ответственность producer | Что не входит |
|---|---|---|
| Producer заявленного usage | Передать exact captures/usage и обеспечить полноту заявленных зависимостей своего результата | Не удостоверяет storage authority и не подменяет full Source closure |
| Owning producer исходного retained набора | Предъявить доступный для перечисления физический набор, достаточный для всех разрешённых раскрытий, и законное основание удержания | Не становится владельцем Source membership/history semantics |
| Artifacts readers | Материализовать явно запрошенные refs под допустимой authority; проверить physical integrity/admission/budgets; вернуть owning results | Не находят capture/history dependency graph по Source правилам |
| Source | Декодировать свои форматы, проверить exact relations и полноту по переданным данным, вычислить semantic closure | Не читает foreign storage, не выдаёт authority, не acquisition owner |
| DAG | Передавать owning результаты по согласованному маршруту | Не разбирает witness/capture, не вычисляет refs и не реализует dependency traversal |

**Незамкнутая связь:** identity и публичный метод producer полного перечислимого retained набора пока не предъявлены. Если такой набор уже существует, его owning контракт должен назвать exact refs enumeration, consistency/version, authority и protection lifetime; generic ref/holder этого не доказывает. Если его нет, один reader по одному ref не замыкает цепочку: Source раскрывает следующие refs только после decoding. Выбирать новый discovery protocol, DAG loop или промежуточный публичный Source result этим уточнением нельзя. Это конкретная зависимость X-READ, переданная координатору, а не задача Artifacts угадать Source graph.

До завершения этой связи запрещено объявлять пять proof-only signatures достаточным публичным API выбранного data-input пути. Собственные pure rules и дальнейшая архитектурная детализация Source не требуют выдуманного producer; последовательность АР-1…АР-6 и запрет искусственных implementation-срезов сохраняются.
