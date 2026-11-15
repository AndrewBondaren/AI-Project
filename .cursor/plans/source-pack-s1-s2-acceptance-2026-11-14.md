# PACK-S1/S2: общая статическая проверка проектного среза

## Итог совместной проверки редакции 2

**Ограничение применимости акта, 2026-11-16:** исторический verdict ниже не является текущим разрешением реализации scoped composition. В строке «Нет прямых междоменных public calls» использован более узкий критерий, чем абсолютный запрет dag-generator-interface.mdc. Соответствие этому критерию не доказано; требуется решение пользователя и владельцев DAG/Snapshot по INT-DAG-SCOPED. Кроме того, размещение coverage/preflight/adopt требует адресной SRP-дельты из source-core-public-boundaries.md §4. Остальные принятые semantics/POJO не отменяются; новые исключения этим дополнением не вводятся.

2026-11-14: **ACCEPTED DESIGN только S1/S2**, единая редакция — source-pack-s1-s2-contract.md, редакция 2. Ниже сохранена история первой и повторной Source проверки. Pack выявил дополнительный S12-PACK-ERR-1: неназванный pin/manifest rollback carrier и success-only read signatures. Snapshot конкретизировал исправление в owning proposal §12; оно внесено в редакцию 2. Pack и Snapshot/Artifacts подтвердили точный перенос и закрыли finding; Source сверил границу и неизменность S1/S2/adopt. Snapshot evidence — snapshot-review-source-pack-s1-s2-r2.md; Pack verdict — сообщение чата 01a1cfce-ff7d-7e30-b738-f075bf490f13 от 2026-11-14 по редакции 2.

Итог по обязательной matrix ниже: scoped dependencies и typed error boundary конкретизированы, три запрета DAG/ownership/порядок/public-internal/CRUD ограничения соблюдены в указанном internal design scope. Новые read union используют existing ManifestReadRefusal; named PackPreparationReadAbort хранит его, поднимается внутри writer и ловится только после confirmed rollback/revoke. Unknown outcome не переводится в refusal; late failure откатывает earlier acquisitions. Открытых findings этой совместной проверки нет.

Это не runtime acceptance, не разрешение кода и не приёмка всей production интеграции. Public DAG/Pack mapping, trusted acquisition admission/finalizer hookup и authored writer остаются вне scope. Следующий шаг — синхронизация accepted Source specification с принятой дельтой, затем отдельный implementation-план с проверкой prerequisites. Код/тесты в этом проходе не менялись и не запускались.

## История Source проверки до единой редакции

2026-11-14. **Повторная статическая проверка: S2-TRACE-1 CLOSED, открытых замечаний в проверяемом S1/S2 design-срезе нет.** Это результат проверки Source, не независимый reviewer verdict и не совместная приёмка всей интеграции. Основания: source-pack-boundary-response-2026-11-14.md S1/S2, pack-preparation-source-authority-contract.md §9–11, source-proof-v2-contract-spec.md §11–12 и перечисленные ниже исходники. Pack и Snapshot дали адресные consumer reviews. Новые declarations остаются proposal до синхронизации единой принимаемой редакции; код этим актом не разрешён.

## История замечания — S2-TRACE-1 (CLOSED)

§9–10 Snapshot proposal требуют explicit scoped catalog/holder reads при unbound helper, но конкретные owning adapter declarations и полный nested trace для require_open_manifest, manifest reader и register/resolve не предъявлены. Требование «не открывать UOW/bind» задаёт запрет, а не доказательство допустимого пути. Existing SqliteArtifactHolders.holders открывает scopes.read_scope(), is_held использует holders; при unbound helper этот public путь нельзя считать заимствующим outer writer автоматически. Private _holders(scope, ref) существует, но его использование другими классами нельзя молча объявить принятым новым port.

Нужно только в рамках S2: владелец Snapshot/Artifacts называет exact proposed/existing methods/modules для scoped catalog/holder reads, caller→callee trace через общий read facet и registry guards, результат/refusal/infra propagation, отсутствие own UOW/bind/guard. Если нужна новая internal declaration — явно proposal с ответственностью и критериями отказа. Source её самостоятельно не назначает. Origin admission/finalizer hookup в этот вопрос не входят.

**Повторная проверка:** Snapshot предъявил §11 с точными proposed IScopedArtifactRead, IScopedArtifactHolderRead, IScopedOperationRead, concrete adapters, сигнатурами, scope guards и отказами. Объявлены nested paths require_open_manifest, manifest reader, register/resolve. Новые methods не выдаются за existing API. Этого достаточно для закрытия замечания о конкретности design.

Статически сверены следующие existing primitives (пути относительно backend/app):

- db/repositories/sqlite/artifacts/catalogStore.py: _find/_descriptor/_storage используют explicit scope; текущий _find при descriptor mismatch выдаёт ValueError. Предложенный infrastructure refusal нового port — требуемое изменение, не текущее поведение.
- db/repositories/sqlite/artifacts/holderStore.py: _holders → _chain/_hydrate; operation hydration → SqliteOperationStore._load, snapshot hydration → SqliteSnapshotHistoryStore.resolve_ref(scope=...), artifact hydration → catalog._by_id. Public holders/is_held с открытием read_scope в новый trace не входят.
- db/repositories/sqlite/snapshotCore/operations/operationStore.py: _load → _event, SqliteOperationArtifacts.read, terminal codec decode, SqlitePublicationEvidence.check. Evidence → world._by_id/player._for_operation → explicit ScopedSqliteAccess. В проверенных read branches нет собственной transaction/bind/guard.
- db/repositories/sqlite/worldPack/executionPins.py: _binding/_closed читают pin identity/state через переданный scope; новый require_open_manifest обязан явно обработать отсутствие binding и сохранить owning отказ.
- storage/artifacts/manifestBlobBackend.py: ManifestBlobBackend.read_verified → ContentAddressedBlobBackend.read_verified → read_verified_file. Existing concrete backend ограничивает размер configured budget, проверяет длину/digest, не открывает artifact guard/UOW и не вызывает leases на read path. Это допустимый concrete backend для предложенного reader; произвольная реализация ReadableBlobBackend автоматически не принимается.
- db/repositories/sqlite/shared/access/scopedAccess.py проверяет registry перед SQL и после execute; proposed reader дополнительно проверяет lifetime после physical await. Scope registry/DB/coordinator должны совпадать у всех adapters.

Закрыт пробел declarations/nested calls, а не runtime evidence. При реализации обязательны проверки wrong task/database/revoked scope, sequential bind cleanup, two-connection GC/pin-close serialization, late rollback, PREPARING restart и READY replay. Ни один новый scoped method ещё не объявляется реализованным.

## Матрица обязательных критериев

| Критерий | Evidence и вывод |
|---|---|
| Нет ветвящегося orchestration pipeline | S1 pure, S2 локальный read-only preflight; outer trace Snapshot §9 — одна атомарная storage операция. Новая межоперационная ветка не вводится |
| Нет скрытой orchestration | Нет нового публичного pipeline/worker/callback. Internal-only scope явно указан. Публичная DAG интеграция не принимается этим срезом |
| Нет прямых междоменных public calls | Source получает собственные POJO, не Pack DTO; public READ не вызывается. Internal scoped trace конкретизирован в Snapshot §11 и сверен с existing primitives; production public маршрут этим не принимается |
| Ответственность/зависимости/effects/отказ каждого класса | Source selector/input/retention/collector описаны; ownership issuer/provider и rollback carrier — Snapshot. Scoped adapter classes/methods/guards/errors конкретизированы в §11; S2-TRACE-1 CLOSED |
| Public/internal граница | Новых public operations нет; scope/internal input/evidence не выходят в public payload. Pack verified reader извлекает все provenance proofs. Не принимаем public prepare/DAG целиком |
| Утверждённый порядок | Origin/manifest → coverage → preflight bind/reset → provenance checks → adopt bind/collect/check/acquire/reset → READY/commit. Accepted adopt не заменён; sequential binds — явно новый proposal, не уже accepted функция |
| CRUD данных C/R/U/D | C/U/D публичные не добавляются; R — новый internal preflight, public READ не меняется. Это не приёмка общего Source CRUD. Dependency trace внутреннего чтения конкретизирован и статически проверен |
| CRUD настроек C/R/U/D | Все четыре операции отсутствуют в данном срезе; selector использует immutable configured schema/descriptor bindings, не ambient mutable settings. Новая settings CRUD не заявлена |
| Протокол междоменных зависимостей | Pack/Snapshot ответы и статусы зафиксированы. Scoped reader dependency конкретизирована owning proposal §11; новых доменов и публичных операций не добавлено |
| POJO и typed field/logic errors без дублей | Internal named relation input использует existing request/proof, не mirror. Exact ModelIdentity и typed paths заданы. Existing SourceFailure reused; CHECK_COVERAGE и применимость кодов явно предложены. Consumer замечание root закрыто. Cold diagnostic owner allowlist — обязательная задача конкретного error transport при реализации, не изменение proof manifest |

## Что не является замечанием этого среза

S1 coverage/world/empty/historical/extra-atom semantics согласуются с заявленной потребностью Pack; новых замечаний в этой проверке нет. Реальные runtime tests не требуются для признания текста проектом, но необходимы для приёмки реализации. Отсутствие authored writer/bootstrap, cell-state разработки или новых generator/DAG контрактов не используется как основание расширить S1/S2.

Trusted acquisition admission и finalizer hookup остаются отдельным непринятым участком: S1/S2 не обещают работоспособность полного operation-origin пути. Их исключение не позволяет обходить этот gap при будущей production реализации.

S2-TRACE-1 закрыт повторной проверкой owning ответа и соответствующих строк матрицы. Следующий шаг — свести S1/S2 и scoped dependency declarations в единую редакцию для совместной приёмки, сохранив различие accepted proof и новых предложений. Accepted proof specification пока не менялась. До этого не объявлять совместный ACCEPTED и не начинать код; затем нужен отдельный конкретный implementation-план через implement-plan. Новый объём работы автоматически не добавляется.
