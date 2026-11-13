# Pack — приёмка текущего scope

2026-11-13. Проверка **плана**, не runtime. Основание — [все обязательные критерии домена](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена). Итог общей приёмки: **НЕ ПРОЙДЕНА для полной цепочки с зависимыми интеграциями**. Ни отсутствие реализации, ни невыполненные production tests сами по себе не являются причиной отказа в приёмке проекта. Ниже указаны конкретные отсутствующие сведения.

## Границы проверки

Проверены [доменный контракт](pack-v2-domain-contract-spec.md), [write-план](pack-v2-public-write-operations.md), [CRUD roster](pack-data-crud-roster.md), [классы](pack-class-responsibility-roster.md), [POJO](pack-pojo-error-acceptance.md), [порядок writes](pack-write-order-trace.md), payload/admission traces, [activation errors](pack-activation-error-contract.md), [lifecycle chain](pack-lifecycle-chain-review.md), [settings disposition](pack-settings-crud-disposition.md).

Encoding identity, canonical registration и exact READY recovery вынесены пользователем в [serialization/deserialization](pack-serialization-deserialization.md). Source proof ведётся отдельно. PACK-METADATA-PLANNING явно отложен и не блокирует текущую разработку/приёмку. Эти темы не возвращаются в локальные блокеры под другим именем. Внешние callers и новые DAG-ноды не проектируются Pack.

## Обязательные критерии

| Критерий | Проверенное основание | Результат проверки плана |
|---|---|---|
| Нет pipeline-оркестратора | Domain contract и class roster: wrapper → одна internal operation; DAG выбирает следующий вызов/повтор/expected | Локальная граница соблюдена. Admission внутри атомарной операции не становится выбором следующего доменного workflow |
| Нет скрытого запуска | CRUD/write roster задаёт прямые DAG calls, state передаётся явно; нет public callback/worker session | Проектный маршрут описан. Реальные callers проверяются при реализации, их отсутствие сейчас не выдаётся за нарушение проекта |
| Нет прямых публичных междоменных вызовов | Source/producer results → DAG → Pack; декодеры pure, storage ports внутренние | Локальная граница соблюдена. Транзитивные эффекты ещё не предъявленных atomic ports не считаются проверенными |
| Ответственность каждого класса | Class roster + payload/codec traces описывают зависимости, эффекты и признаки отказа; validator/assembler pure, operation делает IO | Для перечисленных локальных классов сведения есть. Конкретная внутренняя atomic activation/release implementation остаётся внешним binding, её ответственность/effects нельзя принять по названию wrapper |
| Public / pipeline / implementation | Write/read/activation/release inputs/results, exact diagnostics, private guard/lease/backend | Локальные формы конкретизированы. Typed atomic conflict/resource outcomes ещё не привязаны к точным owning carriers |
| Неизменность порядка | Write-order trace, local/final validation; sources → evidence → manifest → codec/readers; callers до удаления legacy, затем version audit | Порядок зафиксирован, новых перестановок этим review не принято. Settlement SQL/publish и provisional/final wilderness status сохраняют отдельные стадии |
| CRUD данных: C/R/U/D отдельно | CRUD roster и write/delete traces; prepare/activate и independent release | Операции описаны; старое расхождение двух release signatures устранено. Полный lifecycle C/U/D не принимается без exact atomic binding |
| CRUD настроек: C/R/U/D отдельно | Settings disposition и явные исключения CachePolicy, manifest_max_bytes | По этим двум объектам требование закрыто решениями пользователя. Новые owning payload limits и legacy policy disposition не становятся автоматически Pack CRUD; неизвестные ограничения остаются у владельцев |
| Междоменный CRUD-протокол | Source/producer appendix, activation/retention trace, settlement registry trace | Карта ответственности есть; exact historical Transition context и atomic contracts не предъявлены полностью. Соответствующие интеграционные маршруты остаются непринимаемыми |
| POJO, field и logic errors без дублей | Shared state/manifest fields, named part/read types, owning payload POJO, closed preparation union, activation/refusal reuse | Локальные решения обоснованы. Source proof не копируется; внешние carriers проверяются после предъявления. Canonical restore относится к отдельному scope |

Ни по одной строке наличие документа не объявлено доказательством runtime. Аналогично старое слово OPEN не является доказательством отсутствия решения: сверены более поздние уточнения.

## Точные непринятые интеграционные границы

1. **Artifacts/Publication → prepare/activate/release:** exact preparing adoption; immutable-binding conflict при read→claim; защищённое подтверждение candidate role/holds; scoped CAS/handoff/terminal; durable release witness. Нужны owning методы/сигнатуры, typed outcomes и effects. Existing primitives/fixtures и generic ValueError этого не заменяют. Это остаток соответствующих операций, не всей pure Pack preparation.
2. **Resource execution failure после OWNER:** семантика уже согласована — не REJECTED и не автоматически READY. Нужны точный exception и законный lifecycle transition/recovery от владельца. Не создавать новый terminal или самостоятельный retry.
3. **Historical Transition context:** settlement payload с custom transitions требует конкретного передаваемого pinned контекста и owning validation binding. Latest/canonical fallback не доказывает историческую корректность. Не блокирует другие payload roles.

Числа/configuration недостающих format profiles предъявляют владельцы форматов; mechanisms enforcement уже описаны. Они ограничивают подключение соответствующего decoder, не разрешают произвольный Pack default. State/start transport bound также не считается реализованным одним manifest byte cap; при подготовке конкретного implementation-среза его зависимость должна быть явно разрешена, а не заменена обещанием ограниченного heap.

## Что не является новым остатком проектирования

Preparation diagnostic union согласован; metadata describe/bind описаны; release Input/Result консолидированы; шесть post-OWNER activation predicates сверены. Payload roster, девять leaf roles, hydrology root→shards, pin positions, grade responsibility и status policies конкретизированы. CachePolicy/manifest_max_bytes settings CRUD повторно не открываются.

Ранние заключения CRUD/POJO/write appendices о «metadata outputs отсутствуют», «union не согласован» или «две release signatures» читать с учётом поздних решений и этого review. Они не создают дополнительные вопросы. При этом отсутствующий внешний тип нельзя заменить заглушкой ради формальной общей приёмки.

## Практический результат

Локальные архитектурные критерии рассмотрены; дополнительных требований к policy/defaults/DAG этим review не введено. Полную цепочку нельзя объявить принятой до предъявления перечисленных bindings. Независимые Pack-срезы могут проходить собственную приёмку и реализацию с явным scope; этот результат не является blanket-разрешением обойти implement-plan или зависимые проверки.

Далее нужен конкретный implementation-срез с перечисленными входами/выходами и готовыми зависимостями, либо предъявление owning binding для интеграционного среза. Повторное дробление уже разобранных status/leaf вопросов не требуется. Код/SQL не менялись, новые runtime-тесты в этой приёмке не запускались.
