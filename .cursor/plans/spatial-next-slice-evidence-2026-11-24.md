# Spatial: следующий срез, сверка 2026-11-24

## Карта gates

| Gate | Реализация и проверка | Приёмка и остаток | Источник |
|---|---|---|---|
| SP-P2W | F3/F5 production pin/close/release и F6 DAG+Pack reopen matrix реализованы; F6 2/2 OK. Existing manifest helper делает stage и finish, production caller не найден статическим inventory. | F6 ACCEPT технический, не пользовательская приёмка SP-P2W. OPEN concrete Pack producer/consumer, format semantic cutover, writable lease issuer, registration/identity, Publication completion. | spatial-f6-finality-report.md; spatial-f5-pack-review.md; pack-staging-completion-cutover.md; pack-staging-owning-contract-delta.md |
| SP-P3I | SP-P0/P1 имеют записи приёмки в собственных границах; GEO S1–S4 и Fields identity имеют более поздний evidence. | Не считать старую запись о S3 текущим фактом. Требуется отдельно подтвердить accepted canonical source и exact root builder/source proof; в этой задаче GEO файлы не менялись. | spatial-distribution-domain.md §§8, 15; geo-water-diagnostics-source-d1.md; geo-water-fields-identity-report.md |
| SP-P3W / SP-P3 | Production binding root к staged publisher и cold Pack round-trip не предъявлены. | После SP-P3I, SP-P2 и SP-H нужен принятый PACK-ENTRY-CONTRACT; затем отдельная проверка и пользовательская приёмка SP-P3. | spatial-distribution-domain.md §§8, 15.69 |
| SP-3 / SP-M / SP-4 | Shared read declarations и тестовый reader SP-1C приняты; SP-M отдельный materialization contract. | SP-3 ждёт опубликованный base root SP-P3. SP-4 ждёт SP-3 и SP-M, включая разделение ответственности TerrainBatchOrchestrator. Runtime SP-3S/SP-4R и gameplay SP-R имеют отдельные gates. | spatial-distribution-domain.md §§8, 14, 16, 15.82 |

## Реальный стык и решение

`preparedManifest.py:finish_pack_preparation` кодирует candidate, вызывает `manifest_stager.stage`, затем `staging.finish_preparation` и выдаёт `PreparedPackCandidate`. Это existing helper; owning Pack inventory нашёл только четыре test call sites и не нашёл production caller. `packManifestCodec.py` содержит `encode_candidate_manifest`; `executionPins.py` обеспечивает execution pin/close/release и не является publication operation. Поэтому DTO/fixture и успешный F6 не закрывают SP-P2W. Ближайший кодовый срез зависит от ещё не принятого междоменного контракта; локальную реализацию не начинали. Точное предложение Input/Output/Error, identity, effects, файлы и проверки внесено в spatial-distribution-domain.md §15.104 как PROPOSED.

Независимо от GEO можно согласовать Pack material/format binding и проверить Pack test callers без изменений hydrology generators, diagnostics, source models, manifests, encoding locks и Fields. Следующий шаг после owning deliverables — передать пакет назначенному координатору и получить решение пользователя. До этого stop boundary: без production DAG, bindings, migrations, publication и cutover.

## Проверки рабочего дерева

Прочитаны AGENTS.md, implement-plan, interdomain-contract-coordination и dag-generator-interface; просмотрены owning reports и реальные definitions/callers через `rg`. `git rev-parse --show-toplevel` вернул `E:/AI Project`, но `git status`, `git diff` и `git diff --check` отвечают `fatal: this operation must be run in a work tree` даже при явных `core.bare=false` и `core.worktree`. Поэтому текущий diff и чистоту изменений подтвердить нельзя; код не менялся и тесты не запускались. Документальные правки внесены через apply_patch.
