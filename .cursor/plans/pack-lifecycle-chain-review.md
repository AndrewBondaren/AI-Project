# Pack prepare → READY → activate/release: сверка цепочки

2026-11-13. Статическая проверка контрактов, не runtime acceptance. Основание: обязательная приёмка `.cursor/rules/dag-generator-interface.mdc`, ТЗ Pack, write-план, activation error contract, candidate release contract, retention trace и existing preparedManifest/OperationRecord. Код и SQL не изменены, новые тесты не запускались.

## Цепочка и обязательные свидетельства

| Переход | Кто выполняет | Необходимая связь / эффект |
|---|---|---|
| S0 → write → S1 | DAG выбирает вызов, PackPreparationService применяет одно изменение | Input state не мутирует; старый порядок обновлений сохраняется; producer/merge не запускается |
| Конечный state → manifest | PackPreparationOperation + pure validator/assembler | Полная schema/provenance/scope проверка, position links и рассчитанный closure; assembler не выбирает workflow |
| Stage/seal → READY | Existing Artifacts staging через внутренний binding | Exact identity/world/fence и equality leased refs с полным набором, writers drained; manifest ref подтверждён отдельно |
| Повтор prepare в READY | PackPreparationOperation | Тот же manifest, без повторного stage/finish; нельзя выбирать первый ref подходящего формата |
| Candidate → claim | DAG передаёт PreparedPackCandidate + expected; Pack internal admission | Отдельная activation identity; неизвестный ID не создаёт подготовку; pre-OWNER refusals не пишут terminal |
| OWNER → CAS/terminal | Внутренняя атомарная реализация Pack/Publication/Artifacts | APPLIED → ACTIVE; MISMATCH → READY_INACTIVE; retention и terminal в одном подтверждённом scope |
| Повтор activate | Pack identity/terminal mapping | Тот же historical outcome; без нового CAS, latest lookup и восстановления holds после release |
| READY_INACTIVE → release | Отдельный вызов DAG → Pack release | Освобождается только владение адресованного кандидата; head/activation terminal не меняются |
| Повтор release после GC | Durable свидетельство release owning binding | Отсутствие файла/hold не заменяет свидетельство; общий manifest/children других владельцев сохраняется |

## F1 — публичный release расходился с ТЗ (синхронизировано 2026-11-13)

ТЗ `docs/tz_world_pack_storage.md`, раздел неактивного кандидата, задаёт InactiveCandidateReleasePipelineOpenPipeline и InactiveCandidateReleaseInput(world_uid, activation_operation_id, manifest), результаты InactiveCandidateReleased/Refusal в activation/release.py. Планы pack-candidate-release-contract.md и pack-data-crud-roster.md задают PackCandidateReleasePipelineOpenPipeline.release(PreparedPackCandidate), результаты PackCandidateReleaseResult/Refusal в release/result.py. Последний вход включает preparation_fingerprint, а мир берёт из durable record; это не простое переименование.

Согласованная консолидация: сохранён release-план с переиспользованием PreparedPackCandidate, сверкой preparation_fingerprint и полным manifest ref; world определяется по durable operation/terminal. ТЗ синхронизировано, две формы/aliases не поддерживаются. Политика release только READY_INACTIVE и atomic/repeat гарантии не меняется. Это закрытие расхождения документации, не приёмка runtime.

## F2 — READY replay не имеет предъявленного exact manifest binding

Existing finish_pack_preparation знает manifest_ref в памяти и выдаёт PreparedPackCandidate после finish; OperationRecord хранит leased_artifacts, но не обозначает роль manifest. Write-план правильно запрещает выбор первого подходящего ref, однако конкретный способ восстановления точного ref после потери ответа ещё не реализован/не доказан. Нужен детерминированный binding от принятого body к exact encoded manifest либо другой согласованный owning механизм. Новый candidate store не следует из этой находки автоматически.

Контрольный случай: в leased_artifacts несколько refs с manifest format; восстановление обязано вернуть именно результат данной подготовки либо отказать, без эвристики. READY replay prepare требует доступности кандидата; terminal replay activate после release её не требует. Смешивать эти два повтора нельзя.

### Направление закрытия F2 без нового store

Предлагается использовать тот же полный prepare request: после проверки preparation fingerprint и READY identity чистый assembler повторно строит manifest из конечного state, а закреплённый encoder получает точные bytes. Из них существующий content_digest и len дают ожидаемый полный ArtifactRef с owning descriptor. Затем проверяется именно этот ref в leased_artifacts и его verified bytes/hold, а также полный ожидаемый closure. Никакой reserve/stage/seal/finish при replay не вызывается; producer/write-операции не повторяются. Посторонние manifest refs не выбираются даже при том же format.

Необходимые предпосылки: assembler и encoding детерминированы; все влияющие значения присутствуют в semantic body либо закреплённом versioned binding; нет latest settings/time/random defaults; порядок canonical manifest одинаков в первой попытке и replay. Если изменённый deployment не умеет воспроизвести прежний binding, требуется явный отказ совместимости, а не выбор другого ref или повторная запись. Конкретное включение binding revision в preparation identity ещё должно быть сверено — сейчас одним body digest это не доказано.

Это проект направления F2, не заявление о готовом replay. Контрольный пример: потеря ответа после READY, новый процесс, тот же request → тот же полный ref без writes; смена encoding binding не выдаёт иной candidate под прежней identity. Содержимое сохранённого manifest может быть прочитано для проверки, но не выбирается по эвристике из произвольных refs.

## F3 — атомарное сохранение владения/release остаётся интеграционным gate

Existing handoff не создаёт destination holder автоматически; terminal не снимает operation hold и cancel terminal не равен release. Точный binding root ownership, shared child links и durable release witness ещё требуется от Artifacts/Publication. Это уже известный внешний остаток, не требование нового holder store. Тесты existing primitives и manual fixture composition не закрывают публичный Pack route.

## Проверка обязательных границ и итог

Три запрета DAG соблюдены в предложенном распределении: wrappers делегируют один раз; orchestration/повтор/новый expected выбирает DAG; public producer/Source вызовы внутри Pack не добавляются. Локальный CAS/admission остаётся алгоритмом одной атомарной реализации. Точный production caller trace при реализации ещё нужен.

Class responsibilities и pure/I/O границы описаны в class roster и проектах операций; неизвестные atomic bindings не заполняются успешными заглушками. Public Input/Output/Error пока не согласованы полностью из-за F1 и внешних error bindings. Порядок старых writes сохраняется по pack-write-order-trace; prepare не переисполняет список writes. CRUD release не принимается при двух разных сигнатурах; settings disposition остаётся отдельным незакрытым критерием. POJO/identity контрольные probes не заменяют полного field/logic/canonical freeze.

Итог: **полная runtime-цепочка пока не принята**. F1 синхронизирован на уровне контракта; F2 перенесён по решению пользователя в [отдельный план сериализации/десериализации](pack-serialization-deserialization.md) и не блокирует независимый текущий Pack scope. F3 ограничивает зависимые atomic операции. Готовность READY recovery не объявляется до приёмки отдельного binding. Отложенный PACK-METADATA-PLANNING не включён в блокеры, source_proof другого агента не перепроектируется.
