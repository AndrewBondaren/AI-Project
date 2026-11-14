# Source: контрольная точка контрактов и будущей реализации

Дата: 2026-11-14. Назначение: исключить дрейф scope и смешение принятого design, предложений и runtime. Основной план остаётся `world-source-versioning.md`; доменные ТЗ определяют семантику. Этот документ — реестр статусов и разрешённых работ, не новый доменный контракт и не разрешение кода. При противоречии документов работа в спорной части останавливается; автоматический выбор удобной версии запрещён.

## 1. Принятый design Source proof

Источник: `source-proof-v2-contract-spec.md`, независимый акт `source-durable-proof-contract-acceptance-2026-11-13.md`. Принят **проектный срез**, не весь Source и не runtime.

| Граница | Зафиксированный контракт |
|---|---|
| Владелец | Source; публичные POJO под app.dataModel.sourceVersioning; зеркала в Pack запрещены |
| Capture ref | SourceCaptureRef(world_uid, artifact); artifact — finalized witness, не capture body, не hold/token |
| Proof | SourceDurableProof(schema_version=1, world_uid, uses); несколько captures и historical revisions; SourceCaptureUsage(capture, dependencies) |
| Вход/результат | SourceProofInput(world_uid, uses); SourceProofReadInput(world_uid, proof); SourceProofResult(proof, durable_refs); groups/selection по §6 спецификации |
| Ошибки | Единый SourceFailure(operation, field_issues, logic_issues); SourceProofFailure не существует в целевом контракте |
| Immutable shape | Frozen, strict, extra-forbid, revalidate-always, tuple; точные поля/порядок/валидация — спецификация |
| Canonical | Source-owned SOURCE_PROOF_SCHEMA_V1, existing CanonicalCodec/content_digest; 71129 capture ref, 71130 usage, 71131 proof; полный transitive roster §11.4 |
| Closure | Witness → full capture → все обязательные bodies/dependencies формата v1. SELECT меняет logical usage, но не сокращает closure использованного capture |
| Adoption | Internal SourceCaptureRetentionBinding.adopt(scope, request: SourceProofReadInput, sources: tuple[VerifiedArtifactRef,...], target) → SourceProofResult или SourceFailure. На входе unbound; один bind внутри; повторный collect, exact source-set/hold/target checks до acquire; без release/own commit |
| Finalization | Internal finalizer §12.2: committed witness authority, exact replay, проверенный общий scope. Внешний capture/DAG entry этим не принят |

В исторической приёмке 2026-11-13 была описана роль pure selector, но не точная операция requested proof против tuple coverage proofs. Дельта S1/S2 принята 2026-11-14 и синхронизирована в proof specification §6/11.3/13: check_coverage с named internal input и collect_for_adoption. Это design, не готовые runtime методы. Durable refs не доказывают logical coverage. Concrete retention authority provider/context не принят как готовая production интеграция.

## 2. Решения пользователя и предложения

| Область | Статус на контрольную дату |
|---|---|
| Запрет старой формы | Принято: никакой адаптации, dual-read, inference обязательных полей или fallback |
| Terrain hills_authored | Representation согласована; подробный strict 19-field/nested roster предъявлен в dossier, не реализован |
| Bootstrap input | Принято: явно подготовленные authored-записи нового контракта; defaults/landcover — отдельные dependencies |
| Terrain projection/membership | Все 19 semantic, exclusions пусты, SEQUENCE — конкретное owning предложение; общей приёмкой не объявлено |
| Danger | Владелец семантики — Locations, явно записано в docs/tz_locations.md |
| Cell-state registry | Оставить как есть, «разобраться отдельно»; вне scope плана. Не требовать нового владельца/контракта для продолжения текущего анализа |
| Source storage | source-revision-storage-design.md — PROPOSED: append-only index/mappings/provenance, no-op/tombstone/prune и bootstrap требования. Не принятый DDL/writer |
| Recovery | Explicit recovery той же операции с исходным request, новая fenced attempt, обязательное logging — решения сохранены. Конкретные infrastructure declarations имеют собственные статусы в pregame/owning response; не считать все предложения реализованными |
| Snapshot authored-write | Общий runtime freeze принят; scoped core частичен. Принятого конкретного pregame Terrain/Source writer binding не найдено. Source latest не равен applied WorldPublicationRef |

## 3. Реализация сейчас

На 2026-11-14 пути `backend/app/dataModel/sourceVersioning` и `backend/app/application/worldData/sourceVersioning` отсутствуют. Поэтому перечисленные Source модули являются целевыми путями design, не доступными импортами. Existing CanonicalCodec, ArtifactFormatRegistryBinding и ReadableBlobBackend проверены как существующие зависимости; это не доказательство готовности Source.

Runtime-код/SQL/DAG в текущих проходах не менялись; runtime tests и новые golden vectors не выполнялись. Историческая статическая приёмка proof не заменяет такие проверки. Shared Terrain POJO пока текущие; укрепление до целевой формы не выполнено.

## 4. Точный запрос Pack — отдельно разрешённый design-срез

**Изменение scope 2026-11-14:** после пояснения участвующих Source/Pack/Snapshot/Artifacts пользователь ответил «Делай». Разрешено проектирование и согласование только PACK-S1/S2. Это не разрешение runtime-кода, DAG, authored writer/bootstrap или принятие всего Snapshot authority proposal. Текущий proposal записан в source-pack-boundary-response-2026-11-14.md, раздел PACK-S1/S2; совместный review ещё не завершён.

**PACK-S1: logical coverage.** Pack просит Source-owned pure internal операцию requested SourceDurableProof против coverage tuple[SourceDurableProof,...]. Нужны typed result/errors, world/canonical validation даже для empty, exact capture/revision/dependency atom matching, несколько historical captures, отказ на extra atom при одинаковом storage closure. Pack сам извлекает proofs из verified exact manifests; Source не получает Pack DTO и не удостоверяет Snapshot pin/origin. Точная новая сигнатура/roster здесь не проектируются.

**PACK-S2: scoped composition.** Pack просит точный допустимый trace issuer/register/resolve → adopt: как получить требуемый closure для provenance mapping, lifetime read facet, ownership bind, ошибки/rollback и запрет acquire до всех checks. Accepted adopt уже сам делает один bind и collect внутри. Предварительный issuer collect и последующий adopt в общей outer transaction отдельно не приняты; одна аннотация CommitReadScope этого не разрешает. Молча менять adopt нельзя.

Оба запроса теперь включены пользователем в ограниченный design scope; прежняя остановка по scope снята только для них. Они не означают принятия `pack-preparation-source-authority-contract.md` и не разрешают реализацию. Поручение из другого чата не отменяет ограничения текущего Source чата. После design/review нужна общая приёмка и отдельный implement-plan.

Адресные reviews получены 2026-11-14: Pack подтвердил S1 semantics/diagnostic root; Snapshot подтвердил S1 consumer compatibility и статическую feasibility sequential binds S2 при условиях §10 своего authority proposal. Общая приёмка ещё не выполнена. Требования explicit scoped readers, private scope-local evidence и единого GC writer guard зафиксированы в Source response. Issuer admission/commit acknowledgement и hookup finalizer остаются отдельным непринятым участком; его нельзя включить в реализацию под видом S1/S2.

Общая статическая проверка и адресная повторная проверка выполнены: [акт S1/S2](source-pack-s1-s2-acceptance-2026-11-14.md). S2-TRACE-1 CLOSED по Snapshot §11 и сверке вложенных scoped reads/physical blob backend с кодом; открытых замечаний этой проверки нет. Это не независимый verdict и не совместный ACCEPTED всей интеграции. Новые методы остаются proposal, accepted spec/runtime не менялись. Далее — единая редакция S1/S2 для совместной приёмки, затем отдельный implementation-план; origin admission/finalizer hookup и authored writer не включаются.

## 5. Будущая работа: порядок и остановки

Единая редакция разрешённого среза: [source-pack-s1-s2-contract.md](source-pack-s1-s2-contract.md), редакция 2, ACCEPTED DESIGN только S1/S2 от 2026-11-14. В редакции 1 Pack нашёл S12-PACK-ERR-1: отсутствовал exact pin/manifest refusal carrier. Редакция 2 включает owning Snapshot исправление §12 (read union, named carrier и rollback boundary); Pack и Snapshot/Artifacts подтвердили её и закрыли finding. Итог зафиксирован в начале акта S1/S2; прежние статусы выше описывают историю. Proof specification синхронизирована в §6/11.3/13; подготовлен [implementation-план](source-pack-s1-s2-implementation.md), NOT EXECUTION-READY: отсутствуют G1 base Source POJO/pure contracts, G2 durable collector/read/adopt и G3 consumer runtime composition. Код не менялся. Полученное отдельно предложение snapshot-source-acquisition-admission.md не рассмотрено и не включено: acquisition admission/finalizer hookup остаются за пределами разрешённого среза.

1. Шаг 1: семантический Terrain dossier подготовлен. Полный caller cutover и runtime acceptance не заявлены; никаких новых междоменных API на этом шаге.
2. Текущий шаг 2: Source storage proposal. Writer/bootstrap конкретизация остановлена на отсутствии принятого authored-write binding Snapshot. Разрешённая адресная сверка существующего решения выполнена; новое apply/set решение **не разрешено автоматически**. Самостоятельную Source accounting часть нельзя представить как атомарную запись applied World.
3. Шаг 3: целевые public/internal границы и DAG совместно с владельцами; не временные APIs из текущих v1 readers. Начало этого шага и включение PACK-S1/S2 не подразумеваются самим получением агентского запроса.
4. Шаг 4: единая проверенная редакция, все обязательные критерии проекта, точный implementation-plan с файлами/порядком/checks; только затем код через implement-plan.

Порядок основного плана сохраняется: inventory → owning contracts/projector → revisions/history/retention → capture finalize → integrations. Выделение нового среза не разрешает его реализацию в обход prerequisites. Нет автоматической миграции Source, Pack internals, generators, state registry или назначения новых владельцев. При выходе за разрешённую таблицу доменов основного плана — остановка и конкретная зависимость пользователю.

## 6. Правило изменений

Перед изменением принятой формы/signature/semantics указать: старое решение и источник, предлагаемое изменение, затронутых consumers, совместимость и требуемую приёмку. Сначала явное решение о scope/изменении, затем синхронизация спецификации и этого реестра; старая рекомендация должна быть удалена либо помечена заменённой. Изменение статуса только по evidence: PROPOSED не становится ACCEPTED из-за переписки, ACCEPTED design не становится IMPLEMENTED от появления файла.

Ответ владельца — датированная сверка, не вечный freeze. Перед приёмкой/implement-plan повторно проверить Snapshot/Artifacts/Pack/Source signatures и текущие SoT. Если владелец изменил зависимость, оценить impact и остановить зависимые edits до согласования, а не подгонять молча Source.

Контрольные SHA-256 на момент записи (не подписи и не повторная приёмка):

| Документ | SHA-256 |
|---|---|
| source-proof-v2-contract-spec.md | 87BA56A8EACF232C1E3D7C1884975C5599280D722BF8CEC98CD082947DD111A9 |
| terrain-source-execution-contract-dossier.md | 29C154CF9F28CC1CBA8C8CAB79C49453068AD9760335AAD168086C8D0CA5E415 |
| source-revision-storage-design.md | C84EF2D434A7D117CC69FD02EF51E74A84A831D34EBE67FCB4E7E4A07431451B |
| snapshot-source-authored-binding-status-2026-11-14.md | E070853411227B6377CF5BFE63BCB40A39291CB0FF89490EA4EF2058795B2B36 |

Hash proof отличается от зафиксированного в историческом акте: акт допускает последующие status/link edits, но это не доказывает автоматически отсутствие semantic delta. Перед новым freeze нужен diff относительно принятой редакции; текущий hash сам по себе не расширяет вердикт reviewer.

После явной синхронизации принятой S1/S2 дельты 2026-11-14 SHA-256 proof specification: 4CB9985B232C820FDDDE3DA45A85DC73AF5E44EA4472E81200DE91F5271E23C6. Дельта: named coverage input/method, CHECK_COVERAGE/error applicability, sequential preflight §13 и ссылки на принятую единую редакцию/план. Canonical IDs, public proof POJO, adopt/finalizer signatures не менялись. Верхняя hash-таблица сохранена как предыдущая контрольная точка; исторический reviewer verdict не распространяется на дельту задним числом.
