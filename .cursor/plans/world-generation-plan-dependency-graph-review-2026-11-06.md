# Независимая проверка WORLD-PLAN-GRAPH-1 — 2026-11-06

Вердикт: **GRAPH-AC OPEN; структурная часть PASS, семантическая проверка частичная**. Не выдаётся полная приёмка документа. HEAD a15e502eeb87fe1c51994a08ce0bf1e42071b241. До работы изменён world-domain-artifacts-cancel-gc-d1.md; чужой diff сохранён. Production и owning-планы не изменялись. Тесты production не запускались, чужие результаты не переаттестованы на этот HEAD.

## Подтверждённые исправления

В [графе](./world-generation-plan-dependency-graph.md) §5.2 удалена действующая ложная очередь «4D2 НЕ НАЧАТ / Snapshot D предъявлен»: SN-CORE и 4C3-D приняты 4 ноября, 4D2 продолжается. §§1, 6 и 12 уже фиксировали это. В §7.2 добавлена автоматическая проверка статусного покрытия и backlinks LOD/ERROR. §12.5 явно отделяет локальный F-протокол от абстрактного SP-P2W и от SN-STAGE.

## Передачи результатов и ограничения evidence

| Producer → результат → consumer | Вывод / владелец следующего действия |
|---|---|
| GEO → Hydrology diagnostics → surface codec → Spatial source/Pack | Spatial §15.101 документирует failure базового FieldPathError и source admission drift. Retention 3/3 на старых TLV проверяет bytes, но не совместимость нынешнего decoder. Hydrology и codec owner должны предъявить согласованный producer/admission/cold round-trip; SP-H требует G10-A. Не блокировать проектирование SP-P0. Полный нынешний type/import trace здесь не выполнен. |
| DAG F1/F2 → committed intent → Pack F3 | F1 evidence d01cf073; F2 — diff поверх него, не новый PASS текущего HEAD. [F3 отчёт](./spatial-f3-implementation-report.md) фиксирует принятую карту и get_store_id, тесты не подтверждены. В executionStore.py найдены get_store_id и record_stop_intent. Следующий срез — identity verification, затем F3. |
| Pack CLOSED → DAG F4 finalized → Pack F5 release | Spatial §§15.100–103 и DAG finality steps согласованы. CLOSED сохраняется после release; отсутствие ответа не разрешает cleanup. F6 должен доказать recovery на двух БД. Нельзя принимать checkpoint FAILED за finalized. |
| Snapshot storage core → 4D2 → 4D3 → 4E2 | Storage core принят отдельно. SN-STAGE требует принятого pregame port; SN-RUNTIME — applicable apply handler, без включения read overlay. B-2 после GEN bake integration. |
| Snapshot → Time T4/T5/branch | Time §48: T4 требует SN-TIME-READ и reader; T5 — SN-TIME-APPLY и Time/World handler в CommitScope; новая ветка — SN-TIME-BRANCH. Historical read не требует branch. Все три внешних gates OPEN. |
| ERROR → GEO/Snapshot/Artifacts/Physics | Scoped D1 каждого producer → D2 → применимый I0. Metadata acceptance не мигрирует прочих Snapshot producers. leaseStore.py:165 и artifactGc.py:47 ещё создают FieldPathError. D2 Artifacts не выполнен; его рабочая карта D2-0…4 не новая принятая общая инфраструктура. Physics independent PASS не пользовательская приёмка D2. |
| GEN-BAKE-READ → конкретные GEN bindings | §17.10.3–4 остаётся предложением: R1/R2-L,T,C,X раздельны. Light требует R5-L; full — R5-L(full)+R5-C; named — R5-T; coordinates — R5-X. Immutable membership/locator/hold, coverage и source/frame обязательны по операции. World completeness не prerequisite scoped read. C11 относится к detail/placement, не terrain read. |
| Основная очередь → LEGACY-POST | Аудит после фиксации итоговой ревизии; не prerequisite закрытия основной очереди. Локальные legacy gates владельцев сохраняются. |

## Параллельные границы и ближайшие команды для чатов

Все пути ниже относительно backend; это задания для проверки/дизайна, не выданное координатором разрешение нового production API.

- GEO: «Проверь River scoped D1 и холодную цепочку diagnostic → surface codec → Spatial admission на текущем HEAD. Раздели implementation, independent evidence и приёмку. Предъяви exact file map до кода». Граница — Hydrology producers и surface codec; изменения общих diagnostics согласовать с ERROR owner.
- DAG/Pack: «Повтори identity tests из tests/dag_typing/invocations/test_execution_stop_intent.py; проверь reopen, два соединения, разные БД и intent identity. После PASS продолжай принятый F3 scope, остановись до F4/release». Один координатор F3 владеет migrations/0001_initial.sql, worldPack/executionPins.py, artifact holder journal/coreManifest и Pack reader guard. Не запускать независимые правки этих файлов Artifact/DAG агентами.
- Snapshot: «Независимо проверь rollback trace и ошибку rollback на текущем HEAD; отдельно перечисли baseline cancel/GC и typing. Не закрывай весь 4D2 по адресным тестам». Граница — Snapshot apply/transaction; artifact lifecycle и общий coreManifest зарезервированы отдельно.
- Artifacts: «Проверь актуальный рабочий D1 D2-0…4 и принятие exact contracts; предъяви D2-1 cancel как отдельный срез. Согласуй coreManifest и SQL/holder пересечения с F3 до правок». Cancel: operation/record.py, leaseStore.py; GC: lifecycle/gc.py, artifactGc.py, artifactLog.py; logging routes — отдельная группа.
- Time: «Уточни SN-TIME-READ для T4 отдельно от SN-TIME-APPLY для T5 и SN-TIME-BRANCH. Добавь обратную ссылку на общий граф; pure arithmetic не блокируй production ports». Граница — Time core/read contracts; Snapshot metadata/handler — через владельца Snapshot.
- GEN-BAKE-READ: «Предъяви D1–D7 §17.10.4 на решение, затем R1/R2 отдельно L/T/C/X; не объявляй proposal binding принятым». Только owning read-документы; GEN node graph редактирует его владелец.
- Physics: «Предъяви PS-ERROR-1 D2 после independent PASS на отдельную пользовательскую приёмку; exact GEN/Time bindings оставь OPEN». Граница — Physics contracts; не менять generic diagnostics и Time/Snapshot в этом срезе.

API-1 ведёт пользователь; LOD — документальный A0/C1; DAG-TYPING B ждёт конкретного GEN handoff. Данные об активном процессе агента не проверялись: наличие отчёта не доказывает, что работа выполняется прямо сейчас.

## Решения пользователя

1. GEN-BAKE-READ D1–D7: принять исправленный пакет — открыть пооперационные R1/R2; вернуть конкретные пункты — соответствующие R2 остаются proposals.
2. GEN cutover: water внутри первого switch требует SP-R1 и объединённой приёмки SP-R2; позднее подключение требует evidence допустимости cold/missing поведения текущих consumers. Ни один вариант здесь не выбран.
3. Physics D2: отдельная приёмка после PASS либо адресное дополнительное ревью; PASS не заменяет решение.

Статус принятия последнего рабочего Artifacts D1 требует подтверждения владельца по записи решения, а не автоматического повторного запроса разрешения пользователю. Технические identity/rollback проверки решения пользователя не требуют.

## GRAPH-AC и оставшиеся проверки

2026-11-06: скрипт §7.2 даёт 86 + 12 = 98 уникальных рёбер, 67 вершин; базовый граф и оба отдельных варианта cutover ацикличны. Все hard vertices имеют статусы. Локальные ссылки скрипта проверены на существование файлов, anchors не проверены. §5 и Time §10.3 охвачены; LOD proposals и GBR proposed edges не превращены в hard edges. F/EC локальные зависимости не моделируются этим счётчиком.

Mermaid render **не выполнен**. Полное сопоставление всех Mermaid входов, полный LEGACY-AC, чтение всех owning-планов и всех ссылочных отчётов целиком, полный type/import/caller trace всех активных рёбер и актуальность всех исторических статусов не завершены. Поэтому полный PASS документа не заявляется. У Time отсутствует Markdown backlink — предложение владельцу, файл не менялся. Исторические тестовые числа в §12 остаются evidence своих отчётов, не текущим прогоном.

| План | номер трека | что можно делать сейчас | следующий трек или внешний prerequisite |
|---|---|---|---|
| GEO | River D1 | Freeze диагностики и cold boundary review | D2 → codec/source proof → G10-A/SP-H |
| Spatial/Pack | F3 | Identity verification, принятый F3 scope | F4 после CLOSED; F5 после finalized; F6 |
| DAG | F1/F2, F4 | Проверить новый identity вход; подготовить F4 review | Реальный Pack F3 receipt |
| Snapshot | 4D2 | Независимый rollback review, открытые owning slices | 4D3 → 4E2 → нужный port/handler |
| Time | T4/T5 | Изолированный core, design reader | SN-TIME-READ / APPLY; branch отдельно |
| Artifacts/ERROR | D2-0…4 | Проверить exact D1 acceptance и file reservation | Cancel/GC D2 и локальный I0 раздельно |
| Physics | PS-ERROR-1 D2 | Предъявить independent PASS | Пользовательская приёмка; PH-ARCH отдельно |
| GEN-BAKE-READ | D1–D7 | Решение по пакету | R1/R2-L,T,C,X по операции |
| GEN-DAG | GEN-P0 | Совместный draft design | GEN-CONTRACTS, применимые ports, cutover decision |
| DAG-TYPING | B1 | Подготовить handoff inventory | Concrete GEN integration |
| API-1 | Operation mapping | Пользовательская сверка inputs/outputs | Версия и presence/aliases owner operations |
| LOD | A0/C1 | Inventory и review границы | Concrete Time/Physics/Snapshot agreements |
| LEGACY-POST | Отложен | Не запускать как blocker основной очереди | Итоговая ревизия завершённой очереди |
