# Pack — canonical registration и контрольные примеры

2026-11-13, PROJECT. Статическая проверка actual canonicalCodec, ARTIFACT_CORE_SCHEMA, PATCH_CORE_SCHEMA, SNAPSHOT_CORE_SCHEMA и StoredTerminalCodec. Runtime и числовые IDs не изменены, тесты не запускались.

## Подтверждённая база

ARTIFACT_CORE_SCHEMA уже регистрирует OperationKind (20004), ArtifactRef (20107), WorldPublicationRef (20103), SnapshotApplyResult (20124), PackActivationResult (20125), OperationCancelled (20127), FieldPathError (20137). Snapshot schema включает эту базу через Patch schema. Эти объявления переиспользуются, их IDs не назначаются повторно.

CanonicalCodec выбирает entry по точному type(value); base FieldPathError не заменяет регистрацию PackActivationIssue или JsonFieldError. RegisteredTypeEntry проверяет положительный ID, manifest запрещает duplicate owner/ID; merge_manifests отвергает конфликтующие объявления. StoredTerminalCodec принимает extension и объединяет его со SNAPSHOT_CORE_SCHEMA. Это existing механизм, новый registry/terminal codec не требуется.

В просмотренных production schema declarations не найдена регистрация PackActivationInput/PreparedPackCandidate и concrete Pack refusal issues. Отсутствие их регистрации не устраняется наличием аннотаций в public API.

## Найденные owning IDs и границы manifests (дополнение 2026-11-13)

В `dataModel/fields/encoding/surfaceBindings.py` уже объявлены: ValidatedFieldPath=303, ModelIdentity=304, FieldSegment=305, VariantSegment=306, IndexSegment=307, KeySegment=308. Это существующие declarations владельца Fields; не нужно повторно изобретать Pack IDs этих классов. В просмотренной SNAPSHOT_CORE_SCHEMA через Patch/Artifacts этих шести owner declarations нет. При добавлении к terminal extension проверяется отсутствие конфликтов во всём реально собранном manifest.

**Нельзя объединять весь SURFACE_MANIFEST с SNAPSHOT_CORE_SCHEMA.** Shared FieldPathError уже имеет разные identities в независимых storage-схемах: surface validation BINDINGS — 106, Artifacts — 20137. ReferenceIssueContext — 107/20138, ReferenceIssueReason — 108/20016, RuntimeIssueContext — 109/20139. merge_manifests отклоняет один owner с разными IDs. Это не новое правило и не основание перенумеровывать сохранённые схемы в Pack-задаче.

Для terminal composition сохраняются существующие Artifacts/Snapshot declarations и добавляются необходимые Fields declarations плюс новые конкретные Pack owners. Импорт owning BINDINGS допустим после проверки состава, а не через копирование чисел в новый Pack roster. Public JsonFieldError/WireShapeIssue и JsonValidationCode/WireLocation в просмотренном validation surfaceBindings не зарегистрированы; их registrations остаются отдельным shared-owner пунктом prepare transport. Activation terminal использует собственный concrete PackActivationIssue, поэтому не должен зависеть от readiness всех preparation diagnostics.

Уточнение предыдущей формулировки «единые IDs shared типов»: равенство требуется внутри объединяемого manifest и сохраняемой схемы. Единый глобальный allocator для всех независимых схем просмотренным кодом не предъявлен. Решение о новых Pack IDs должно учитывать конкретную composition и compatibility contract; не создавать искусственный блокер в виде отсутствующего глобального registry.

## Наборы для composition

| Потребитель | Требуемые конкретные declarations |
|---|---|
| Fingerprint activate | PackActivationInput и shared типы полного candidate/expected; exact root subclass, не только PreparedPackCandidate |
| Durable REJECTED activate | PackActivationIssue, PackActivationIssueCode, вся модель ValidatedFieldPath и её сегменты/ModelIdentity; модели-владельцы всех допустимых путей, прежде всего PackActivationInput, WorldPublicationRef, ArtifactRef |
| Публичный transport refusal | PackActivationRefusal плюс тот же diagnostic graph; этот POJO не становится новым terminal storage variant |
| Prepare diagnostics | PackPreparationError/Issue/enum, existing JsonFieldError/WireShapeIssue/JsonValidationCode/WireLocation и их зависимости; конкретные named inputs и nested owners для CheckedPath |
| Fingerprint prepare | Concrete PackPreparationBody/state/parts/assembly/provenance/scope graph по итоговой декларации; capture/proof definitions поставляет владелец, не зеркальный DTO Pack |

Type alias union не является новым record и отдельного canonical type ID не получает. Enum и concrete record получают разные декларации. Python exceptions PackPreparationFailure/JsonDecodeLimitError и executable codecs не регистрируются как public данные. Builtin tuple/str/int обрабатываются canonical codec, им не придумываются отдельные domain identities.

## Cold restore путей — отдельная обязанность

`canonicalCodec.validate_decoded_identity` проверяет ModelIdentity.module/qualname через allowlist python_type текущего manifest. Следовательно, registration diagnostic graph включает не только сериализуемые path records, но и фактических named владельцев пути. Наличие строки qualname не разрешает динамический import произвольного класса. Исключение не снимается ради старого terminal; нужные исторические schema declarations должны оставаться доступны принятому codec.

Для activate допустимые paths ограничены утверждёнными input fields: operation_id, preparation_fingerprint, expected.world_uid/gameplay_started и manifest. Кодек не разрешает синтетический manifest.world_uid на ArtifactRef. Для prepare roster шире и требует проверки каждого named input и вложенной специализации; raw generic specialization не подменяет concrete owner. Shared path types регистрируются у своего владельца с едиными IDs, а Pack включает declarations в composition; новые PackFieldSegment/PackModelIdentity не создаются.

## Конкретная предлагаемая activation-схема

Сверка 2026-11-13 по backend/app, backend/tests, docs и .cursor/plans не нашла использований IDs 20201–20204. Это локальная проверка текущего дерева, не глобальное резервирование и не основание менять другие схемы. Предлагаются declarations в `dataModel/worldPack/encoding/activationBindings.py`, без executable codec в dataModel:

| ID | Exact owner | Kind / назначение |
|---|---|---|
| 20201 | PackActivationInput | RECORD; полный request fingerprint и allowlist владельца diagnostic path |
| 20202 | PackActivationIssueCode | ENUM; concrete diagnostic code |
| 20203 | PackActivationIssue | RECORD; durable diagnostics в SnapshotApplyResult |
| 20204 | PackActivationRefusal | RECORD; публичный transport, не новый terminal discriminator |

PreparedPackCandidate не получает ID только ради наследования: внутри fingerprint сериализуется exact PackActivationInput с унаследованными полями. Если отдельный transport candidate потребует canonical encoding, его регистрация добавляется отдельным обоснованным потребителем. Type alias и exceptions не регистрируются.

Composition identity codec: merge ARTIFACT_CORE_SCHEMA с declaration PackActivationInput; terminal composition: merge SNAPSHOT_CORE_SCHEMA с owning Fields BINDINGS 303–308 и activation declarations. Оба используют один и тот же ID PackActivationInput и одну декларацию его shape. Surface validation BINDINGS целиком не подключаются. Проверка конфликтов выполняется при сборке до обработки запросов.

Предлагается `PACK_ACTIVATION_IDENTITY_REVISION = 1` как первая версия этого нового identity-контракта. Это не manifest storage/wire version и не caller option. Payload fingerprint: existing canonical digest tuple `(1, OperationKind.PACK_ACTIVATION, request)`; число берётся из одной constant declaration, не дублируется в DAG. Изменение состава/порядка полей, IDs или семантики encoding требует отдельного изменения identity-контракта; старые terminal не переидентифицируются молча.

Shape существующего PackActivationInput: operation_id → manifest → preparation_fingerprint → expected. ArtifactRef: kind → format_key → format_version → content_hash → nbytes → row_count. WorldPublicationRef: world_uid → publication_id → pack_hash → snapshot_head → active_timeline_id → gameplay_started. Поля None включаются в encoding. Это контроль порядка owning declarations, не второй ручной encoder/DTO. Field order меняется только вместе с явной проверкой identity совместимости.

Для будущего baseline vector задать фиксированные валидные UID и hashes, manifest descriptor из owning constants, положительный nbytes и row_count=None; expected pregame с pack_hash/snapshot_head/active_timeline_id=None. Второй vector — валидный expected с gameplay_started=True и согласованными pack/timeline: вычисление identity должно работать и для запроса, который затем получает доменный отказ. Invalid сочетания полей не используются как доказательство чувствительности fingerprint. Конкретные bytes/hash вычисляются после принятия IDs/revision и на существующих owning моделях, без runtime-заглушек proposed classes.

Этот раздел предлагает точные IDs/revision, но не объявляет их зарегистрированными или согласованными владельцем encoding. Новые declarations должны быть повторно проверены на отсутствие конфликтов непосредственно перед реализацией, поскольку workspace изменяется другими агентами.

Экспериментальная проверка 2026-11-13: [baseline bytes/hash и девять вариантов](pack-activation-identity-vector.md) вычислены на существующих моделях с предложенным input ID 20201/revision 1. Отдельный процесс подтвердил exact decode/re-encode. Это конкретный результат проверки проекта, не регистрация runtime или durable refusal тест; оставшиеся gates сохраняются.

## Контрольные примеры до freeze

1. Полный валидный PackActivationInput: закрепить encoded bytes и SHA-256 для уже принятого `(activation_contract_revision, OperationKind.PACK_ACTIVATION, request)`. Изменение каждого смыслового поля на другой допустимый вариант меняет digest; повтор в новом процессе сохраняет его. Не ограничиваться равенством digest двум вызовам одной реализации.
2. REJECTED с двумя различными PackActivationIssue: encode terminal → cold decode → from_terminal сохраняет exact subtype, enum, path owners, message и порядок. Удаление PackActivationInput из manifest должно отвергать восстановление его ModelIdentity.
3. Same ID с другим expected/manifest не восстанавливает прежний success/refusal. Повтор после изменения head/release восстанавливает исход без CAS и чтения payload.
4. Prepare structural variants и domain issue: round-trip каждого concrete variant, nested union path и unknown-key WireShapeIssue; MANIFEST_OVERSIZE с обязательным пустым tuple, остальные reasons с пустым tuple отклоняются.
5. Duplicate ID/owner, base class вместо concrete subclass, неизвестный enum и чужой path owner не обходят admission. Два manifests не получают расходящиеся identity shared типа.

Точные hex-векторы нельзя объявить готовыми до freeze concrete schemas, IDs и revision. Значение activation_contract_revision и новые numeric IDs требуют закрепления в конкретной Pack identity/terminal schema с проверкой объединения у владельца Encoding; существующие числа не перенумеровываются. Это не требование найти несуществующий глобальный registry. После фиксации declarations векторы вычисляются и проверяются обратным восстановлением.

Статус: состав registration graph и критерии cold restore конкретизированы. Остаток — shared declaration ownership/IDs, полный prepare graph после внешних proof типов, контрольные bytes/hash и runtime composition. Это не повторное проектирование ошибок и не разрешение менять pipeline/DAG.
