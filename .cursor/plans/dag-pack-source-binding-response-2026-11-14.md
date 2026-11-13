# Ответ владельца DAG: Pack / Source result binding

Дата: 2026-11-14. Документальный review, runtime и NodeId не изменены. Проверены exchange, execution-binding, leaf-contracts, leaf-acceptance и first-route-review, а также фактические CallTarget, CallResults, InvocationCoordinator и CheckpointCodec. Общие Pack документы не редактировались.

**Вердикт:** выбранный механизм existing engine CALL подходит. Полная приёмка маршрута пока не пройдена: A1/A2/A4 требуют сведений ниже, A3 остаётся owning Pack freeze. Caller detailed_initialization, родство и последовательность 1–7 приняты и не пересматриваются. SourceFailure — единственная owning ошибка Source; Source proof design повторно не открывается.

## 1. Что подтверждено кодом engine

- InvocationCoordinator.accept разрешает только target из contract.calls, сохраняет input и caller_invocation_id/caller_step/call_key. Повтор того же dispatch с иным input/node либо continuation отклоняется. CallKey локален parent invocation/step, не глобальный идентификатор операции.
- event читает children только шага parent.step_index - 1 и формирует результат из child terminal. get(key, target) проверяет target и тип output/error. Сам get не проверяет request и не содержит отдельного удостоверения исполнения.
- Поэтому цепочка доверия двухуровневая: detailed_initialization CALL → read_source invocation → SELECT/ADMIT_GROUPS leaf invocation → owning output → read_source output → detailed_initialization resume. Каждый верхний output должен быть построен исключительно из собственного успешного leaf CALL; одного правильного kind недостаточно.
- CheckpointCodec.decode сверяет registry identities, типы input/continuation/terminal, parent linkage, уникальность dispatch и допустимость дочернего NodeId. Это не authentication persisted input/output и не доказательство того, что JSON success получен исполнением. CallSuccess/ReturnedCall, созданные caller, не token.

Принимаемое условие trusted resume: внешний entrypoint принимает только initiating input, не graph/terminal/continuation/ReturnedCall; ExecutionStore и production registry/executors контролируются приложением; execution ownership и доступ к checkpoint проверяет конкретный entrypoint/store binding. Нужно назвать эти классы и предъявить маршрут загрузки. Пока этого нет, A4 открыт. Нельзя объявлять arbitrary imported checkpoint допустимым по одному model_validate_json. Новый receipt/token store не требуется.

## 2. Точная граница команд первого маршрута

Ниже **предлагаемый scope registration**, не изменение уже утверждённых общих unions. Принимается только после фиксации exact верхних I/O/continuation/contract identities. Один NodeId в одном registry имеет одну совместимую схему; второй read_source/read_pack с иной специализацией рядом не допускается.

| Верхняя нода | Команды данного scope | declared calls — ровно соответствующие leaf |
|---|---|---|
| read_pack | DescribePackMetadataUsageRequestsInput; DescribePackMetadataInput | describe_pack_metadata_usage_requests; describe_pack_metadata |
| write_pack | ImportPackMetadataUsageInput; WritePackSettlementStructureInput; BindPackMetadataProvenanceInput | import_pack_metadata_usage; write_pack_settlement_structure; bind_pack_metadata_provenance |
| read_source | SelectSourceProofInput; AdmitSourceProofGroupsInput | select_source_proof; admit_source_proof_groups |

У каждого leaf CallTarget input/output/error/ContractId/version должны точно совпадать с таблицами leaf-contracts. Верхние calls не включают domain services; coordinating calls этого exchange включают три верхних target. Существующее родство и вызов prepared child detailed_bake_initialization сохраняются; эта таблица не заменяет целиком contract detailed_initialization.

Вариант для замыкания A2: отдельная явно названная схема первого scope под единственной регистрацией существующей проектной верхней роли. ReadPackInput.command и ReadSourceInput.command допускают только one, request — закрытый union строк выше; outputs только one с соответствующим result union. WritePackInput.command — три указанные команды, WritePackOutput.result — три соответствующих output. Все kind литералы leaf остаются из leaf-contracts; собственные upper one wrappers сохраняют kind="one". All, READ/VERIFY_GROUPS/ADMIT Source и остальные Pack операции отсутствуют в этой схеме и отклоняются input validation до dispatch. Это **предложение сужения проектной схемы**, которое нужно явно согласовать вместо молчаливого изменения широкого общего union. Альтернатива — полная регистрация всех объявленных команд, но она выходит за scope семи leaf. Успешные заглушки, Any и direct leaf bypass не допускаются.

Для каждой верхней ноды нужен отдельный frozen continuation POJO: exact исходная команда и CallKey; фиксированный target определяется вариантом команды и registered contract.calls, не внешним полем. На start выполняется ровно один CALL; на resume get по сохранённому key/target, затем проверяется соответствующий variant результата и формируется upper output. Ошибка SourceNodeError/PackPreparationNodeError сохраняется; cancelled/runtime failure не превращаются в domain success. Нужны точные имена upper классов, factory signatures, NodeContract и ContinuationContract IDs/version/state_type, bootstrap и error mapping. Этих сведений в просмотренных документах нет — A2 не закрыт таблицей leaf.

## 3. Последовательный SELECT и A1

Добавление completed resolutions и next_index — правильное направление. Принимаемая семантика SelectionWait:

- state — исходный immutable Pack snapshot; calls — полный упорядоченный набор PackSourceSelectionCall; completed — tuple[PackMetadataUsageResolution, ...]; next_index — индекс текущего ожидаемого вызова, то есть первого ещё не принятого результата.
- В сохраняемом wait: 0 <= next_index < len(calls), len(completed) == next_index; completed[j].requested == calls[j].requested для каждого j. CallKeys должны быть однозначны в ожидаемом dispatch; distinct keys по всему списку делают корреляцию явной, но engine scope всё равно parent/step.
- Передаётся только calls[next_index].requested.request через read_source SELECT. Resume получает только этот CALL, добавляет одну resolution и увеличивает индекс. Если запросы остались — новый singleton CALL с обновлённым prefix; иначе один import полного completed набора. Пустой список не создаёт WAITING_CALLS/пустой CallGroup: переход к import с entries=() допускается только если owning Pack разрешает пустой набор в данном сценарии; иначе owning отказ.
- Failure/cancel/runtime failure текущего required CALL прекращает зависимый маршрут, не импортирует partial prefix и не запускает следующий SELECT. Replay уже завершённого child не добавляет resolution второй раз: сохранённый индекс/state и engine step определяют единственное ожидаемое продолжение.

ClosureWait может использовать тот же принцип с tuple[PackSourceClosureResolution, ...], body и next_index; closure не включается в шаги 1–7 и не регистрирует READ автоматически.

Два поля закрывают только накопление SELECT/closure. Для закрытия A1 требуется весь discriminated continuation coordinating node: ожидание usage requests → SELECT prefix → import → settlement write → describe → ADMIT_GROUPS → bind. Каждая фаза должна сохранять exact pending key/target/request и нужный state/evidence для следующей фазы. State после import/write берётся из соответствующего Pack output; никакой загрузки latest state между фазами. Указанные wait-модели не должны терять prepared settlement inputs, fields/subject и Planning binding, необходимые следующим шагам.

Есть дополнительная точная несовместимость: describe leaf возвращает tuple[PackMetadataDescription, ...], а PackSourceGroupsWait содержит одну description. Для принятого single settlement сценария нужно явно ограничить subjects одной строкой и проверить ровно один соответствующий description перед ADMIT_GROUPS. Если допускаются несколько descriptions, нужен отдельно принятый последовательный accumulator; молчаливое взятие первого элемента или flatten групп не принимается.

## 4. Transport, lifecycle и границы ответственности

Existing invocation transport — Pydantic JSON через InvocationCoordinator.encode и CheckpointCodec, contract IDs/version — строковые engine identities. Он не требует сам по себе новых numeric CanonicalSchema IDs для каждого nested POJO. Не следует смешивать эту регистрацию с owning canonical content codec. Но нужен полный roster reachable моделей и проверка их JSON round-trip, immutable validation, discriminators и binary полей: inputs/outputs/errors семи leaf, три upper I/O, их continuation, полный coordinating continuation, вложенные Pack state/basis/evidence/exchange и Source request/result/error.

lifecycle=None допустим как явное решение для immutable исторического результата операции, не как обещание живых refs. Runtime validate_restored вызывается только для SUCCEEDED output при наличии lifecycle; input/continuation не получают автоматическую проверку holds этим hook. Поэтому lifetime pinned base/prepared refs должен быть описан для всего exchange и resume. Bound state не READY; closure/publication/adoption не входят в текущую приёмку и не заменяются result binding.

Роли и критерии отказа: leaf — один owning вызов (отказ при другой публичной операции); upper — один typed dispatch/result mapping (отказ при прямом service вызове); detailed_initialization — принятый порядок и перенос state/results (отказ при Source union/subset или Pack merge); POJO — данные, без dispatch/IO; registry/factory — единственная exact binding и DI, без import-time запуска; coordinator/store/codec — адресация, persistence и trusted restore, без признания произвольного success удостоверением; Pack/Source service — owning валидация и алгоритмы, без междоменного вызова. Pack semantic error freeze остаётся A3, SourceFailure не дублируется.

## 5. Условия повторной приёмки

Принимаются caller/порядок, сохранение верхних уровней, семь single-operation leaf как направление binding и reuse owning POJO/errors. Полный маршрут отклонён до закрытия A1/A2/A3/A4 конкретными декларациями выше. Три запрета DAG на описанном маршруте соблюдены; отсутствие exact upper/coordinator/restore сведений не позволяет принять все классы и публичные границы. CRUD настроек не используется; delete и остальной CRUD доменов этим узким маршрутом не утверждаются. Это не блокировка независимой Pack работы.

Будущие runtime доказательства: два экземпляра одного Source NodeId; чужие key/target и конфликт replay input/state; sequential SELECT с минимум двумя запросами и resume после каждого; failure второго без import; подмена upper результата; один tuple description неправильного subject/лишний description; отказ unsupported/all команды до leaf; доверенный checkpoint round-trip и отказ внешнего checkpoint на entrypoint. Тесты с вручную сконструированным CallSuccess не заменяют engine trace. Отсутствие тестов сейчас не самостоятельный дефект проекта: отказ обусловлен отсутствующими exact контрактами.
