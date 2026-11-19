# Section codec / handler и проверка receipt

## Решение пользователя — 2026-11-19

Приняты два архитектурных решения после междоменной сверки: отдельный codec представления секции и Snapshot-owned проверка receipt относительно входной секции. Пользователь поручил записать контракт отдельно, создать чат на имплементацию первого решения и сообщить владельцам оба решения. Это не приёмка полного Snapshot runtime и не повторное открытие принятого ядра PS-I1 → PS-I2.

Источники: [Snapshot, DEC-2 и SN-Q1.1](world-domain-patches-snapshots.md), [PatchSet](patch-set-domain-architecture.md), [TIME-PATCH-1](patch-set-external-contracts.md), [Time](time-domain.md), [общая карта](dag-multidomain-patch-publication-draft.md). Этот раздел уточняет статус прежнего предложения split: выбран целевой раздельный вариант; конкретная реализация ещё требует gates ниже.

## C1. Отдельное представление и поведение — ACCEPTED

| Компонент | Контракт / единственная ответственность |
|---|---|
| SectionContract[S] | Единая декларация key, concrete section model, supported versions и canonical manifest |
| SectionCodec[S] | encode(section:S) → bytes; decode(payload:bytes, version:FormatVersion) → S. Canonical представление и проверка concrete root при восстановлении |
| DomainSectionHandler[S] | async validate(section:S, context:SnapshotValidationContext) → SectionValidation; async apply(section:S, context:SnapshotApplyContext) → SectionApplyReceipt \| SectionRefused. Предметное поведение без encode/decode |
| SectionRegistry | register(contract, handler, codec): одна согласованная регистрация. Проверяет key/model/versions/manifest и совместимость компонентов; частичный binding не публикуется |
| PatchSetCodec | Через registry использует зарегистрированные SectionCodec; не запускает handler validation/apply |

Это целевые интерфейсы; exact concrete classes/modules/constructors/error roster и способ проверки совместимости предъявляются перед правками по обязательным критериям. Публичные DTO не получают registry/codec/callback.

Разрешённая pure инфраструктурная зависимость: PatchSetCodec → зарегистрированный SectionCodec. Она не является разрешением произвольных прямых междоменных calls. Codec не вызывает публичные Time/Source/Pack pipelines, readers/writers, не делает IO, не ветвит workflow и не получает transaction authority. Точное typed binding и вложенные вызовы проверяются при приёмке.

Отдельная ранее принятая зависимость сохраняется: SnapshotRequestValidator.validate → PatchSetInvariants.check_prepared_order напрямую. Этот общий pure helper модели не заменяется codec и не требует wrapper.

Последовательность: DAG → owning prepare_section → DAG → PatchSetAssembler → DAG → Snapshot.apply: structural/dependency admission → canonical fingerprint через PatchSetCodec/SectionCodec → binding/replay → для новой попытки handler.validate/apply. Assembler codec не вызывает. Новые DAG-ноды и самостоятельные encode/decode стадии не вводятся. Existing persisted formats/type IDs/versions не меняются по факту split; совместимость подтверждается evidence.

**Нормативная синхронизация C1 согласована и выполнена 2026-11-19.** В docs/tz_patch_system.md закреплены separate codec, exact declaration identity/atomic registration и lookup capabilities. Поддерживаемый read-upgrade относится к codec, без переписывания persisted bytes/fingerprint и без разрешения новых legacy adapters. Existing ошибки сохраняются по конкретным случаям после проверки mapping; blanket acceptance roster не дан. Исторический DEC-2 вопрос disposition upgrade закрыт в этой границе, inventory compatibility evidence остаётся обязательным.

### C1: конкретный error mapping и ограниченное исключение — ACCEPTED

2026-11-19 пользователь подтвердил «Ок» после предъявления mapping исполнителем и рекомендации координатора. Только для C1 split сохраняются existing fail-fast registration/admission и наблюдаемый error transport; новые два codec-binding checks симметричны handler checks. Это явное ограниченное исключение из требования агрегации независимых проверок implement-plan. Оно не распространяется на доменную валидацию, C2 receipt checks или другие операции проекта; нового error framework не вводить.

| Место / причина | Принятый transport C1 |
|---|---|
| SectionContract: invalid key/versions/manifest schema | Existing Pydantic ValidationError |
| SectionContract: empty supported_versions / concrete model отсутствует в manifest | Existing ValueError |
| SectionContract: nonconcrete/unbound/non-strict model, неверный header/patch tuple/concrete patch type | Existing TypeError |
| BoundSectionHandler: неверный handler type / другая contract identity | Existing TypeError / ValueError соответственно |
| BoundSectionCodec: объект не SectionCodec / codec.contract is not contract | TypeError / ValueError соответственно; два новых симметричных binding checks |
| Checked semantic/representation admission: wrong exact root / invalid model fields / key-version mismatch | TypeError / ValidationError / ValueError соответственно |
| BoundSectionCodec.encode: результат не bytes | Existing TypeError |
| BoundSectionCodec.decode: payload не bytes, version не int или неподдерживаемая | Existing ValueError; decoded root проходит тот же checked admission |
| register: повтор key/model / merge manifest type-ID-owner collision | Existing ValueError / CanonicalEncodingError соответственно |
| require/require_codec unknown key | ValueError; resolve/resolve_codec сохраняют checked admission mapping выше |
| PatchSetCodec: projection/format/order/key errors / model validation | Existing CanonicalEncodingError / ValidationError; delegated codec exceptions распространяются, не превращаются в SectionRefused |
| CanonicalCodec и concrete test codec | Existing CanonicalEncodingError с сохранением cause; fixture payload-header.version mismatch сохраняет CanonicalEncodingError |

Fail-fast не ослабляет atomic registration: все проверки выполняются до публикации bindings, при любом отказе registry остаётся неизменным. Существующие canonical IDs/bytes/version semantics не меняются. Выявленное отличие actual call-site от этой карты предъявляется отдельно, не исправляется blanket catch или новым carrier.

## C2. Receipt относительно входных patches — ACCEPTED

Владелец общей проверки — Snapshot. После каждого успешного handler.apply проверить receipt до его использования metadata/handoff и до следующего зависимого применения. SectionRefused сохраняет свой owning путь; не превращается в receipt.

Проверяются: receipt.section_key соответствует входной секции; каждый changed полностью совпадает с одним из input section.patches[*].header.ref; states/history соответствуют разрешённым assigned targets и owning provenance. Общая проверка допускает подмножество patches, не требует изменения каждого входного patch. Existing model uniqueness/invariants не копируются; existing provenance/metadata checks переиспользуются без потери необходимых данных и гарантий. Если часть проверки требует ещё не доступных данных, конкретный nested trace обязан это показать до реализации, а не молча ослаблять критерий.

Time отвечает за более сильный контракт успешного положительного advance: changed == (input_patch.header.ref,). Адрес берётся из принятого patch, не реконструируется. Time-контракт использует актуальные states/history с retention records вместо старых state_refs/history_refs/retained_artifacts. Общий validator Snapshot не содержит Time-specific ordinal/cardinality rules.

Невалидный receipt — нарушение контракта исполнения, не business refusal пользователя. Прекратить зависимое применение, откатить общую transaction; не выдавать COMMITTED. Exact owning issue/carrier, paths/aggregation и transport задаёт Snapshot до реализации. Unknown rollback/commit не маскируется. Это не разрешение нового error framework.

## Объём реализации и владельцы

- Новый чат реализует C1 как отдельный срез: инвентарь actual interfaces/registrations/callers → exact class/error/binding карта и проверка согласованного контракта → раздельный codec/handler/registry и необходимые consumers → meaningful tests/typing/diff. Применяется implement-plan; неподтверждённые контракты не реализуются предположением. Если ТЗ противоречит принятому решению, предъявить точные места для синхронизации до зависимого кода.
- Snapshot владеет C2 и его реализационным планом; этот файл фиксирует архитектурное решение, не передаёт C2 новому чату C1 и не разрешает параллельные правки одних файлов.
- Time предъявляет свою concrete representation/handler дельту и исправляет проектный receipt mapping в рамках owning согласования. Принятие C1/C2 не означает автоматического принятия всей TIME-PATCH-1 payload/version дельты.
- PatchSet предоставляет существующий общий header/assembly контракт и consumers codec, ядро повторно не принимается.
- Координатор DAG согласует междоменные дельты; финальная приёмка — пользователь.

Не в scope: DAG wiring/новые NodeId, production union по предположению, gameplay/start, Source/Pack workflow, persistence migrations, новый public apply lifecycle, изменение утверждённого порядка.

## Открытые детали и проверка

OPEN C1: точные modules/interfaces/constructors и codec/registration errors, inventory всех concrete handlers и manifests, representation compatibility. OPEN C2: конкретный Snapshot validator/method, typed diagnostics/transport и полнота provenance относительно доступного context. Это локальные gates зависимой реализации, не отмена выбранной архитектуры.

Для C1 проверить: отсутствие semantic apply/IO при encode/decode; отказ несовместимого binding без частичной регистрации; exact concrete round-trip без потери header/payload; сохранение existing golden bytes/hash/version semantics; обновление фактических consumers, без сохранения второго обходного механизма.

Для C2 проверить: чужой changed ref при совпадающих operation/section; допустимое подмножество; неправильный target; несколько независимых нарушений с owning diagnostics; отсутствие следующего dependent handler/metadata writes и rollback уже сделанных writes. Time отдельно проверяет exact equality единственному входному ref.
