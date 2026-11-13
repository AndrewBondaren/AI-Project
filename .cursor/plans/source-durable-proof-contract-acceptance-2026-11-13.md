# SourceDurableProof — независимая приёмка проектного среза

Дата: 2026-11-13. **Вердикт независимого reviewer: ACCEPTED — проектный срез SourceDurableProof и исправления R1/R2.** Новых блокирующих дефектов в проверенных изменениях не найдено.

Этот акт оформлен Source по переданному reviewer результату, не является самоприёмкой автора исправлений. Источник — сообщение reviewer из чата `01a1d65a-a57a-7260-b439-e07f3e220c08`, переданное по прямому поручению пользователя. Проверка статическая, по актуальной спецификации, CommitScope, holder API и bounded blob reader; runtime-тесты reviewer не запускал и файлы не менял.

## Принятый объём

- `source-proof-v2-contract-spec.md`: проект SourceDurableProof, identity/witness POJO, canonical v1, единые diagnostics, full closure v1, scoped acquisition и internal finalize owner; §12 читается совместно с §3, §6, §9–11.
- R1 закрыт: adopt получает SourceProofReadInput; owning collector вычисляет closure независимо от sources внутри того же write scope; missing/extra/duplicate пары отклоняются до первого acquire.
- R2 закрыт: SourceCaptureFinalizer.finalize имеет concrete caller/dependencies, ранний exact replay без latest, повторный find под scope, rollback после write, writer cleanup и unknown-outcome recovery.
- Canonical IDs/version/field order/vectors, единый error roster и разграничение full closure/usage, label/SourceRevision сохранены. Эти findings не переоткрываются как неисправленные.

## Проверенная редакция

Перед служебной синхронизацией статусов Source снял SHA-256 текущих файлов:

| Файл | SHA-256 |
|---|---|
| source-proof-v2-contract-spec.md | `1ff4a88dcb9eec0ceccb3807c29bfe9127986fd48f37818cd090107d1e966aa7` |
| source-durable-proof-repeat-review-fixes.md | `2dafbd37819a23b044a979b20891f06e4548e6c80157fb61ade399f29a31304c` |

Это идентификаторы локальной редакции на момент получения вердикта, а не электронная подпись reviewer. Последующие исправления статусов/ссылок изменяют hashes; изменения самого принятого контракта требуют отдельного review, а не автоматического переноса этого verdict.

## Что не принято этим актом

| Область | Статус / владелец дальнейшей работы |
|---|---|
| Runtime durable API, rollback/restart/GC/recovery | NOT ACCEPTED до реализации и необходимых проверок; Source и owning storage bindings |
| Весь Source, полный CRUD данных и настроек/disposition | OPEN; за пределами принятого proof-среза |
| Внешний capture/DAG route | OPEN; совместная интеграционная приёмка, DAG-ноды не назначаются Source |
| Pack/Snapshot input → publication/adoption | OPEN; точный consumer/publication binding, без прямых междоменных публичных вызовов |
| Pregame revision staging и retention latest до Pack | OPEN; следующий проектный срез Source и требования к существующему Artifacts lifecycle |

Эти OPEN и отсутствие runtime не являются новыми дефектами принятой схемы. Не требуется завершить всю миграцию Source для сохранения её ACCEPTED статуса. В то же время акт не разрешает runtime-миграцию, SQL, Pack DTO или DAG изменения. Код — только через implement-plan после принятия конкретного implementation slice и в порядке основного плана.

## История и дальнейшая работа

Первый отчёт `source-durable-proof-contract-review-2026-11-13.md` сохраняется без изменений. Findings и матрица состояния до исправлений в `source-durable-proof-repeat-review-fixes.md` также сохраняются как история; текущий verdict R1/R2 указан отдельно.

Следующая локальная проектная задача — `source-pregame-revision-staging-design.md`: конкретизировать pregame staging/receipt/root lifecycle выбранного Source mutation, не расширяя работу до всей миграции writers и не меняя принятый proof-контракт.
