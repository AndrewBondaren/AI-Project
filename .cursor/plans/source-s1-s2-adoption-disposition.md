# Source S1/S2 — disposition adoption после решения варианта А

2026-11-21. Синхронизация уже принятого пользователем запрета прямого Snapshot → Source маршрута. Не новая архитектурная альтернатива, не открытие вопроса об исключении DAG и не разрешение реализации. Применяется к старым S1/S2/spec положениям независимо от их исторической отметки ACCEPTED DESIGN. Неизменные proof POJO и pure semantics не переоткрываются.

| Метод / caller | Текущая судьба | Что сохраняется |
|---|---|---|
| SourceCaptureRetentionBinding.collect_for_adoption(scope, request) | Отозван как target; не реализовывать и не переносить в SourceAdoptionPreflight | Проверка proof/closure как Source semantic алгоритм по данным, полученным через DAG |
| SourceCaptureRetentionBinding.adopt(scope, request, sources, target) | Отозван как Source операция acquisition; ни прямой caller, ни facade, ни переименование не разрешены | Требование полного closure и отсутствия окна GC; acquisition/target retention согласуются в Artifacts/Publication |
| SourceAdoptionPreflight.collect_for_adoption | Отозвана предложенная SRP-релокация, класс исключён из целевого roster | Общие pure проверки не дублируются |
| Snapshot/Publication PackPreparationRetention.adopt_and_finish → Source preflight/adopt/check_coverage | Цепочка отклонена; это не допустимый internal/scoped call | Атомарность publication/target retention остаётся требованием варианта А |
| preflight/adopt → collector.collect(scope.read_scope, …) | Старый caller trace исторический; не prerequisite нового collector | Source semantic closure evaluation; новый data-input binding проходит уже зарегистрированный IC-7/X-READ |
| SourceProofCoverageChecker.check_coverage | Допустимый кандидат внутреннего pure алгоритма Source, без acquire/IO/authority | Exact inclusion/world/conflict diagnostics; external caller не получает право прямого вызова |
| normalizer/union/extractor/matcher и origins | Внутренние алгоритмы Source сохраняются | Один владелец каждого алгоритма, typed original diagnostics |

Новая роль Source заканчивается semantic preparation/result; публичные методы не выполняют acquisition, handoff или commit. Порядок выбранного варианта: разрешённая Artifacts подготовка данных/защиты → передача через DAG → Source semantic result → передача через DAG → разрешённая publication boundary с атомарным target retention. Конкретные ноды и новые foreign signatures здесь не назначаются.

Внешняя замена ещё имеет зарегистрированные gaps authority/protection/admission evidence и atomic binding. Их закрывает координатор Between domain operations с владельцами и пользователем. Наличие этих gaps не возвращает силу старому scoped маршруту. Нельзя заменить atomic publication отдельным заранее выполненным retain и объявить гарантию сохранённой.

SourceCaptureFinalizer.finalize/collect_capture_body не переопределяются этим disposition: они не становятся разрешёнными foreign callers adopt и не принимаются целиком. Их собственные функции относятся к существующему АР-3. Retention исторических revisions/prune — прежний INT-ARTIFACTS-RETENTION, не повод восстановить Source adopt.

Затронутые нормативные места: source-proof-v2-contract-spec.md §11.2 (adopt), §12.1 (scoped adoption/collector), §13 S2; source-pack-s1-s2-contract.md §§3–5; source-pack-s1-s2-implementation.md слой B и composition C. Приёмочные акты 2026-11-13/14 остаются историческим evidence той редакции, не разрешением текущего маршрута. Runtime-код этих компонентов данным документом не удаляется/не создаётся; проверка реализации отдельно.

Критерий согласованности: текущий Source roster не содержит acquisition owner, старые методы явно неисполняемы, не предлагаются повторно под SRP-фасадом, а внешняя замена имеет один зарегистрированный путь согласования. Документ не объявляет IC-7/X-RET закрытыми.
