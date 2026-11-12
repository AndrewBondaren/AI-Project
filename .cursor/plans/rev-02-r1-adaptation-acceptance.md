# Приёмка адаптации capture/proof к Pack, 2026-11-12

**Вердикт: НЕ ПРИНЯТО как законченный контракт R1 / исполнимый план адаптации.** Проверены `source-proof-v2-contract-spec.md` §6–7 и `rev-02-r1-public-pipelines.md` §1–5 относительно `.cursor/rules/dag-generator-interface.mdc` § «Обязательная приёмка плана любого домена» и протокола междоменного CRUD. Это приёмка документов, не runtime. Согласованные ранее решения не отменяются; недостаток конкретности не означает необходимости новой архитектуры или переноса внешней реализации в Pack.

## Результат Pack-owned доработки после проверки

По поручению пользователя выполнена доступная документальная конкретизация в `rev-02-r1-public-pipelines.md` §2.1 и §3.1. Это не runtime реализация и не приёмка внешних ports. Новые требования междоменной границы учитываются при миграции соответствующих доменов, не расширяют автоматически scope Pack.

| Находка | Что исправлено со стороны Pack | Остаток |
|---|---|---|
| A1 | Зафиксировано соответствие собственного producer output → Pack input, без обязательного Pack DTO внутри producer | Concrete Source/producer schema и bindings — внешняя миграция |
| A2 | Поля шести metadata addresses, PackAssemblyProvenanceInput/PackStoredAssemblyProvenance, exact proof coverage, проекции из одной assembly и ошибки заданы явно. Structural materialization coverage отделён от external proof | External coverage/source proof и полный codec/binding roster; не мешают считать Pack-owned поля определёнными |
| A3 | Sync validate_input/base/metadata/coverage, конкретные входные модели, IO-free ответственность и порядок prerequisites заданы. Existing VerifiedManifestBytes переиспользован; source/hold проверки вынесены из pure validator | Concrete R2 guard/adoption lifecycle и full payload bindings — отдельные зависимости; не объявлены принятыми |
| A4 | Metadata использует существующие coordinate/payload/provenance carriers; отдельные metadata new/inherited и VerifiedBase не введены; Pack diagnostics переиспользованы. Для validator/decoder/storage binding/assembler/wrapper/operation заданы effects и признаки отказа | Общая приёмка внешних field/logic errors и codec roster после предъявления owning контрактов |

Локальные недостатки конкретности metadata wrappers и pure/IO разделения в описании устранены. Полный R1 остаётся OPEN по внешним контрактам и зависимым bindings; исходные находки ниже сохранены как основание проверки, их актуальный остаток задан этой таблицей. Отсутствие внешней миграции не переоткрывает готовые Pack-owned декларации. Исполнимость и тесты ещё не подтверждены.

## Исходные находки, препятствовавшие приёмке

1. **R1-A1 / P1 — отсутствует полная внешняя сигнатура и POJO mapping.** Source appendix §6.1 называет `SourceDurableProof`, а карта pipelines §5 прямо оставляет поля/identity/codecs открытыми. Не предъявлен concrete owner method с Input/Output/field-error/logic-error, возвращающий этот proof. Для producer mapping перечислены смысловые данные, но не точные поля конкретных result POJO. Это нарушает критерий междоменного контракта до стадии DAG. Закрытие: получить контракт владельца Source/producer и сопоставить каждое используемое поле с Pack input, включая membership и immutable bodies. Разработка внешних типов не является задачей Pack.
2. **R1-A2 / P1 — неполные Pack-owned metadata/coverage контракты.** В карте pipelines §2 для `PackAssemblyProvenanceInput` не задан полный состав полей, для coverage proof осталась внешняя незавершённая схема. Не завершён общий roster metadata types/codec registrations. Нельзя объявить schema freeze по одному списку class names. Закрытие: concrete Pack-owned projection/address wrappers и их сопоставление с owning типами; внешний proof использовать после предъявления, без локального дубля.
3. **R1-A3 / P1 — не определена граница IO и pure admission.** Карта pipelines §3 требует от pure validator проверки inherited base, coverage соответствия payload и source availability, но не задаёт concrete input результата предшествующего verified read/admission. Внутренние ports названы «принятыми», при этом строка 96 прямо оставляет их R2. Это не доказанное нарушение в коде, а отсутствие данных для приёмки классов/вложенных effects. Закрытие: показать конкретные operation collaborators/ports и immutable данные, которые они передают pure validator; перечислить IO/effects и отказ каждого. Не делать validator orchestration и не вводить публичный service/callback в POJO.
4. **R1-A4 / P1 — не завершена приёмка POJO и ошибок.** Source appendix §7 остаётся таблицей ролей; Source/producers errors не имеют полного field/logic roster. Переиспользование PlanRef/PlanDependency/ArtifactRef подтверждено, но оно не доказывает отсутствие пересечений остальных типов. Закрытие: concrete module/owner/fields/семантика каждого задействованного типа и сравнение с existing/planned моделями. Исключения дублирования не заявлены и не разрешены.

## Полная матрица обязательных критериев

| Критерий | Проверенное место и основание | Результат |
|---|---|---|
| Запрет ветвления маршрута внутри pipeline | Source appendix §6.1; pipelines §3, §4: retry/выбор операции только DAG; локальные проверки одной prepare отделены | Соблюдён в заявленной архитектуре; полная проверка internals OPEN A3 |
| Запрет скрытой оркестрации | Там же: запрет facade/callback/worker обхода, wrapper делегирует одну операцию | Правило применено; concrete callers/маршрут OPEN отдельно |
| Запрет прямых междоменных вызовов | Legacy NativeRiverReliefPublicationJob nested calls прямо исключены как target path; Source/producer/Pack обмениваются через DAG | Не предложен новый обход; concrete внешний binding OPEN A1/A3 |
| Ответственность каждого класса, deps/effects, acceptance/rejection | Pipelines §3 перечисляет validator/assembler/codec/operation/wrapper; Source §7 оставляет роли, internal ports не перечислены полностью | НЕ ПРОЙДЕН, A3/A4 |
| Public contract → open pipeline → internals и вложенные вызовы | Pipelines §1 и §3 задают форму; §5 признаёт отсутствующие inputs/errors; storage admission не конкретизирован | НЕ ПРОЙДЕН, A1/A3 |
| Неизменность порядка | Pipelines §4: full L0 → topology, detailed location L2 → settlement, wilderness без settlement; Source §6.1: capture не запускает compute; prepare не запускает activate | Порядок внешних операций сохранён. Детальные IO/admission prerequisites OPEN A3 |
| CRUD данных C/R/U/D | Prepare/read описаны частично; activate/release вынесены в Pack gates; полного набора concrete методов и POJO нет | Приёмка всего домена OPEN R3; не отдельное требование реализовать весь CRUD ради этой документальной поправки |
| CRUD настроек C/R/U/D | Нет отдельной законченной матрицы конкретных методов; исключение Cache на Pack не распространяется | Приёмка всего домена OPEN R3 |
| Owner method → output POJO → consumer fields → DAG | Source appendix §6.1 описывает смысл, но concrete Source/producer output ещё не предъявлен | НЕ ПРОЙДЕН, A1. Отсутствие нод само по себе не мешает отдельной приёмке готового доменного контракта |
| POJO, typed field/logic errors, отсутствие дублей | Existing Planning/Artifact типы переиспользованы; PackProducedPartEvidence исключён; полного roster нет | НЕ ПРОЙДЕН, A2/A4 |

**Что можно считать установленным:** существующие capture/canonicalization/Planning proof механизмы пригодны для адресного переиспользования; отдельный outcome artifact не обоснован; оркестрация остаётся в DAG по действующим правилам; PackStoredProvenance хранит Source proof и existing Planning dependencies; new/inherited не сохраняются как условия чтения. Это согласованное направление, не полный принятый набор контрактов.

**Следующий шаг без нового архитектурного выбора:** Pack завершает собственные metadata/coverage wrappers и внутреннюю границу validator/operation (A2/A3); внешний владелец предъявляет concrete Source proof/producer contracts (A1), затем выполняется общая проверка POJO/errors (A4). При получении результата владельца перепроверить актуальные файлы, не считать эту запись доказательством вечного отсутствия типа. Если контракт ещё не передан, пользователь должен уточнить у владельца именно результат метода, schema/codec и ошибки; повторного согласования старых границ не требуется. Сквозной DAG маршрут принимается отдельно после согласования нод. R1 остаётся OPEN.
