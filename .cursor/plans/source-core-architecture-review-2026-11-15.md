# Source core architecture — review 2026-11-15

**Verdict: CHANGES REQUIRED.** Собственное архитектурное ревью автора плана, не независимая приёмка. Scope: checker signatures, request traversal/aggregation, pure algorithm prerequisites и выбор независимого среза. Код/ТЗ/внешние контракты не изменены; runtime/typing tests не выполнялись. Проверены проектные документы и existing Source values/shared diagnostics.

## R1 — P1: partial structural failure теряет проверяемые dependencies

Места: [conflict API](source-core-checker-signatures.md#3-конфликты-usage), [request composition §2](source-core-request-composition.md#2-последовательность-и-prerequisites).

SourceUsageConflictChecker принимает tuple целых SourceCaptureUsage. План одновременно требует не передавать повреждённую ветвь как валидный usage и собирать все доступные independent errors. Не задан transport пригодных facts внутри повреждённого usage.

Контрпример: недоверенный nested экземпляр после model_construct имеет пригодный capture ref C, objects=(None, A@r1); другой usage той же full capture C содержит A@r2. Shape ошибка у первого элемента не мешает доказать конфликт r1/r2. Но отбрасывание первого usage теряет конфликт, а передача его целиком нарушает объявленный typed prerequisite. Исправленная копия usage с удалённым None не предусмотрена и создаёт риск потери original indices/маскировки повреждения.

Требуется до implementation выбрать точный внутренний вход conflict checks из доступных facts с исходными indices либо конкретный typed traversal API, позволяющий проверить доступные atoms без признания повреждённого usage валидным. Общие слова «проверить пригодные ветви» недостаточны. Не требуются изменения public DTO или новый error carrier.

Критерий закрытия: один original request даёт INVALID_SHAPE и REVISION_CONFLICT с правильными исходными индексами; отдельный случай missing capture пропускает только зависимый conflict; normalization/union не вызываются. Подобную политику применить к доступным частям selection, не потеряв independent diagnostics.

## R2 — P2: независимость normalizer среза противоречит его prerequisites

Места: [internal API §2](source-core-internal-api.md#2-preconditions-и-зависимости-проверки), [request composition §5](source-core-request-composition.md#5-constructor-graph-и-граница-независимого-среза), [карта §6](source-core-architecture.md#6-ближайший-ограниченный-срез-для-архитектурной-проверки).

Normalizer объявлен вызываемым только после world/descriptor/key checks. Все пять request checkers зависят от SourceIdentityChecker с owning key adapter. Одновременно normalizer/union/extractor предлагаются независимым первым срезом, но не отделено, какие preconditions нужны математическому преобразованию, а какие нужны только public admission.

Это не запрещает реализовать pure normalizer. Но в текущем виде конкретный independent scope ещё не задан: implementation либо подставит adapter, либо ослабит записанный prerequisite самостоятельно. Нельзя выдавать algorithm tests на вручную подготовленных values за закрытие всей validation цепочки.

Требуется выбрать один конкретный срез: (a) invariant components, не зависящие от owning checks, либо (b) pure algorithms с явно разделёнными algorithm safety preconditions и public admission requirements. Во втором случае сами public operations по-прежнему обязаны выполнять owning checks. Нужна единая таблица methods → обязательные prerequisites → владелец проверки → результат среза. Без allow_partial/skip_keys и production stubs.

Критерий закрытия: точный список файлов/методов независимого среза, отсутствие owning binding в constructor graph этого среза, явно ограниченные гарантии результата и адресная проверка preconditions. Полная request admission остаётся отложенной интеграцией.

## Обязательная архитектурная сверка

| Критерий | Результат / основание |
|---|---|
| Одна ответственность, один метод — одна функция | В выбранных checker/pure API явного смешения не найдено. Request checker собирает одну проверку конкретного request, не делает transformation/IO. Предложения убрать лишние wrappers ещё не считать принятой реализацией |
| Три запрета DAG | В этом pure-проекте ноды/public cross-domain вызовы не вводятся; internal private calls допустимы. Runtime route не проверен и не принимается |
| Public/internal | Existing POJO переиспользуются; internal result не выдаётся за durable evidence. R2 препятствует конкретной границе первого implementation-среза |
| Порядок | Ядро перед интеграциями сохранено; ошибки R1/R2 собственные и не перекладываются на владельцев внешних доменов |
| POJO/errors | Existing CheckedPath/Source issues используются без зеркал. R1 требует exact internal transport пригодных facts, не новой публичной модели |
| CRUD/settings | Не входят в ограниченный pure-срез, полная приёмка домена невозможна без ранее отмеченной disposition/configuration работы |
| Concrete responsibility evidence | Таблицы ответственности есть; structural partial-input поведение R1 недоопределено. Архитектурная приёмка этого среза отклонена |
| Implementation readiness | NOT READY до исправления R1/R2 и отдельного implementation-плана. Independent review не заявлен |

## Следующее действие

Сначала исправить R1 и R2 в архитектурных документах, затем повторно проверить конкретный независимый срез. Не расширять задачу на Terrain/Artifacts/Snapshot и не начинать реализацию по текущему proposal. Замечания в этом проходе не исправлялись; они предъявлены отдельно от реализации.

## Ответ на замечания и собственная повторная проверка — 2026-11-16

**R1 — исправлено в design.** SourceUsageConflictChecker получает отдельные captures/dependencies tuples с original group/use/dependency positions. При malformed соседнем ref пригодный A@r1 участвует в batch рядом с A@r2; repaired SourceCaptureUsage не строится. Missing capture исключает лишь capture-relative проверку. Request composition и матрица дополнены обоими контрпримерами. Требования согласованности facts отдельно определены как programming invariants. Полная request boundary пока не реализована, runtime regression не заявлен.

**R2 — исправлено в design вариантом (a).** source-core-independent-slice.md перечисляет пять concrete files/classes/methods, prerequisites, владельцев проверок и гарантии. Срез содержит world/conflict/canonical/selection и atom enumeration, но не normalizer/union/extraction/matching либо full request checkers. Единственная algorithm constructor dependency — SelectionChecker→AtomIndex, owning key adapter отсутствует. Требование owning admission для последующих операций не отменено и не заменено stub.

Повторно сверены signatures, composition, границы результата и карта среза. Исходные R1/R2 устранены на уровне документации; новых находок в рамках этой повторной проверки не зафиксировано. **Это собственная проверка исправлений, не independent PASS и не общая архитектурная приёмка.** Следующий шаг — принятие конкретного independent subset и отдельный implementation-план через implement-plan. Full request diagnostics, mutation/capture/prune/configuration и интеграции не объявляются завершёнными.

## Последующее ревью implementation-плана и правки — 2026-11-16

Вердикт последующего собственного ревью: **CHANGES REQUIRED**. Он относится к source-core-invariants-implementation.md и его обязательным ссылкам; предыдущая запись о R1/R2 не является допуском новой реализации.

| Замечание | Исправление документа / предел статуса |
|---|---|
| P1: повтор правил persisted_shape/increasing_indices в application при запрете правок dataModel | В implementation-план §3.A0 добавлен конкретный proposal общих Source dataModel функций, двух POJO wrappers и потребителей-checkers. Public shape/manifest сохраняются. Новый scope/порядок требует принятия; A0 не реализован, дублирование в текущем коде не объявлено устранённым |
| P1: capture_uid исключён из реализации, но оставлен в критериях independent subset | Приёмка и таблица subset синхронизированы: только revisions exact capture. Capture uid conflict остаётся Source witness/finalization, без расширения ref и без обещания проверки в этом срезе |
| P1: документы отрицают наличие кода, а implementation evidence утверждает соблюдение порядка | Основной план, карта и implementation-план фиксируют написанный, но непринятый код и отсутствие зафиксированного отдельного допуска исправленной архитектуры. Прежние tests сохранены как историческое evidence; утверждение о соблюдении принятого порядка снято. Текущее «Правь» разрешает документы, не дальнейший код |
| P2: AtomIndex одновременно обещает отказ и полагается на caller | Выбран caller-owned prerequisite без defensive exception guarantee. Tests B→C — только pure использование; production guard обязателен в будущем request traversal, его готовность не заявляется |

Повторная сверка правок документов: scope остаётся Source; storage/DAG/foreign APIs не добавлены; новые public DTO и error roster отсутствуют; дельта A0 названа явно, а не выдана за прежний утверждённый порядок. Это проверка внесённых правок автором, **не приёмка плана и не независимый PASS**. Следующий шаг — ревью и принятие исправленной редакции с A0; затем корректировка кода через implement-plan и отдельная независимая приёмка реализации.
