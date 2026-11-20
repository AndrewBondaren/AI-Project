# PatchSet: слайсы реализации общего ядра

Дата: 2026-11-19. Статус: **PS-I1 → PS-I2 реализованы и приняты в согласованном scope; P2 закрыт по итоговому результату, переданному пользователем.** Проверки и приёмка ответственности — §6. Архитектурный контракт — [PS-ARCH-0](patch-set-domain-architecture.md), нормативный алгоритм только §7.5, predicates/diagnostics — §9. Это отдельные слайсы реализации, не шаги алгоритма assemble.

## 1. Scope, порядок и gates

**Уточнение фактического статуса — 2026-11-20, по поручению пользователя «Зафиксируй это в плане»: реализация ядра выполнена, а не только спроектирована.**

| Срез | Фактический результат | Статус |
|---|---|---|
| PS-I1 | `PatchData`, общий родитель `PatchSetData`, дети `PatchSetAssemblyInput` / `PatchSet`, общий `PatchSetInvariants`, проверки identity и независимой уникальности ordinal, миграция локальных fixtures | Реализован и принят в согласованном scope |
| PS-I2 | `IPatchSetAssembly`, `PatchSetAssembler.assemble`, внутренний validator, типизированные diagnostics/refusal, проверка concrete bindings и сохранение ограничений секций; прежний P2 исправлен | Реализован и принят в согласованном scope |
| Production-интеграция | Native producers, production union/composition, DAG wiring и Snapshot apply lifecycle | Не входит в выполненные PS-I1 → PS-I2; приёмка ядра не означает готовности всей цепочки |

Evidence реализации и ранее выполненных проверок находится в §6; исходное ревью и исправление — в [patch-set-core-review.md](patch-set-core-review.md). Основание итоговой приёмки — переданный пользователем результат: «Новых существенных находок P1/P2/P3 не обнаружено. Прежний P2 закрыт. Ядро PS-I1 → PS-I2 принимается в согласованном scope». Исторические формулировки ниже о предстоящей реализации или проверках не отменяют этот статус. При данной документальной фиксации тесты повторно не запускались.

Внешние зависимости отслеживаются в [отдельном реестре](patch-set-external-contracts.md); их незавершённость не открывает заново приёмку ядра. Изменение междоменных контрактов требует согласования через назначенного координатора DAG.

Порядок: **PS-I1 → PS-I2**. Каждый слайс включает код, миграцию собственных затронутых потребителей и проверки. Нельзя объявить слайс завершённым с заведомо сломанными локальными fixtures или перенести проверку в общий будущий этап.

В scope: generic модели, единый checker, constructor validation, public assembly contract/implementation, typed diagnostics и локальные tests. Не входят production section producers/union, Time migration, DAG wiring, Snapshot apply lifecycle, storage/DDL, codec-handler split, cache. Внешние контракты не блокируют приёмку ядра. DAG binding не является третьим слайсом этого плана.

**Разрешение пользователя 2026-11-19 («Ок»):** отдельная реализация ядра PatchSet по PS-I1 → PS-I2 разрешена при незакрытом общем Snapshot ARCH-0. Разрешение охватывает только scope этого плана, включая необходимые shared model changes, локальную миграцию fixtures и проверки. Повторное разрешение на эту границу не требуется. Оно не закрывает Snapshot ARCH-0 и не разрешает production-интеграции, DAG wiring или другие Snapshot-срезы.

Перед кодом применять implement-plan, читать актуальные owning нормы и проверять рабочее дерево. Сервер, commit/push, DAG и миграционные SQL вне задачи. Разрешение не является evidence выполненной реализации: код на момент фиксации не начат.

## 2. Impact register: уже существующие локальные потребители

Все пути относительно backend/. Перед PS-I1 повторить поиск DomainSection/PatchSet/PatchHeader и расширить register новыми фактическими consumers; этот перечень не заменяет актуальный preflight.

| Файл / модель | Действие в PS-I1 | Сохранение / проверка |
|---|---|---|
| app/dataModel/patch/sections/section.py: DomainSection | Сузить P bound до PatchData | Не менять SectionHeader или порядок patches |
| app/dataModel/patch/request/patchSet.py: PatchSet | Унаследовать PatchSetData, заменить predicates делегированием check_core | Flat fields/order и existing canonical identity; новые identity/ordinal отказы — явная дельта |
| tests/snapshotCore/support/fakeSection.py: FakePatch | BaseModel → PatchData, убрать повтор header; target/change/prepared остаются | module/class identity и порядок header,target,change,prepared; manifest ID 90005 сохраняется |
| Тот же файл: FakeSection / FAKE_SECTION_SCHEMA | Переиспользовать обновлённый FakePatch | Section ID 90001 и IDs 90002–90004 неизменны; base PatchData не регистрируется автоматически |
| tests/snapshotCore/contracts/test_models.py: DomainSection[PatchHeader] | Для позитивных cases заменить на именованную test-only patch модель наследника PatchData с header, объявленную в support/fakeSection.py | PatchHeader сам по себе не patch; не добавлять header в PatchHeader и не отключать новый bound. Негативные cases сохранить по смыслу |
| tests/snapshotCore/contracts/test_codec.py: FakePatch/FakeSection, OtherSection/OldSection | Обновить только native fixture bindings, где требуется; не удалять исторические negative/old-format проверки | Existing reserved IDs/golden bytes/hash и read-upgrade evidence не менять без объяснения конкретной несовместимости |
| tests/snapshotCore/contracts/test_registry.py | Позитивные fixtures используют native PatchData descendants; negative BaseModel/unbound cases сохраняются | Exact type/key/version/manifest admission не ослаблять |
| tests/snapshotCore/support/fixtures.py и consumers fixtures в storage/lifecycle tests | Исправить только несовместимые constructor inputs, выявленные поиском/прогоном | Не менять storage semantics ради нового validator |
| app/application/patch/contracts/sectionHandler.py: SectionContract | Сверить runtime declaration validation с новым P bound; добавить rejection non-PatchData concrete patch model при необходимости | Generic bound не считать достаточным runtime evidence; no change handler/codec ownership |
| app/application/patch/encoding/coreManifest.py, app/application/patch/encoding/patchSetCodec.py | Проверка совместимости; изменение IDs/формата не запланировано | Любая неожиданная golden delta останавливает приёмку, не исправляется перегенерацией эталонов |
| tests/snapshotCore/contracts/test_typing.py и используемые им fixtures | Добавить проверки нового bound/несовместимых child specializations в существующую инфраструктуру | Не менять общий expected baseline вслепую; сверить каждый новый expected diagnostic |

Точное местоположение new test-only minimal модели: tests/snapshotCore/support/fakeSection.py, имя HeaderOnlyPatch(PatchData), без новых полей. Это replacement прежнего использования PatchHeader как payload в tests, не production домен и не wire compatibility adapter. Existing FakePatch сохраняется для codec payload coverage. New classes не получают canonical ID без сценария кодирования и явной declaration.

Preflight PS-I1: tests/typing/snapshotCore/valid.py и invalid.py также используют DomainSection[PatchHeader]. Перевести валидные специализации на HeaderOnlyPatch; для неверного payload сохранить отдельный ожидаемый diagnostic нового bound, а несовместимость двух допустимых специализаций проверять FakePatch против HeaderOnlyPatch. Новых production классов это не вводит.

PS-I2 test specializations (все без IO/production registration): tests/snapshotCore/contracts/test_patch_assembly.py — NativeSection (union HeaderOnlyPatch/FakePatch), OtherSection (другая секция того же payload), AssemblyInput/AssemblyResult (одинаковый закрытый union), SiblingInput (проверка exact root), OtherResult (несовместимый section binding). Каждый класс обязан сохранять поля owning родителя и strict/nested invariants; отказ при копии полей, фиктивной production регистрации или использовании несовместимой пары как позитивного case. tests/snapshotCore/support/fakeSection.py — FakeAssemblyInput/FakePatchSet: именованные children для existing FakeSection в typing harness, с теми же требованиями.

### 2.1. Обязательная приёмка ответственности классов

Эта карта связывает архитектуру с evidence реализации и входит в DoD обоих слайсов. Точные поля/методы/модули берутся из [PS-ARCH-0 §§2–3, 7.4, 9](patch-set-domain-architecture.md); таблица не вводит второй алгоритм. Пути ниже относительно backend/. Для каждого перечисленного класса проверяются фактические imports, вложенные calls, effects и указанный отрицательный сценарий. Объединённая строка применяется к каждому именованному классу отдельно; общий PASS тестового набора не заменяет индивидуальный вывод.

| Класс / источник | Ответственность, допустимые зависимости и эффекты | Слайс: evidence и основание отказа |
|---|---|---|
| PatchData, PatchHeader, PatchRef — PS-ARCH-0 §§3.2/9.1 | Общий header и identity; только owning dataModel/value types, без IO | I1: native fixture сохраняет header/ref и wire layout. Отказ при чтении предметного payload checker-ом или копии header в наследнике |
| PatchSetData — §3.1 | Единственное объявление девяти полей; только structural/nested validation | I1: exact model_fields/order; relation-invalid input создаётся. Отказ при relation checks в родителе или повторных полях детей |
| PatchSetAssemblyInput — §3.1 | Typed запрос до общей relation-проверки; наследует структуру без новых полей | I1: допускает независимые relation failures, отвергает malformed fields. Отказ при подмене родителем или обходе nested validation |
| PatchSet — §§3.1/9.2 | Immutable результат; constructor adapter единого check_core | I1: direct construction/decode отвергают core violations; golden bytes/hash сохранены. Отказ при копии predicates или добавлении prepared-order в constructor |
| PatchSetInvariants — §9.2 | Единственный pure источник check_core/check_prepared_order; только dataModel, immutable facts | I1: operation/section mismatch вместе с duplicate ordinal; стабильный порядок facts. Отказ при application imports, IO, sorting, payload semantics или подавлении независимой ошибки |
| PatchSetInvariantViolation — §9.2 | Internal fact с typed details и допустимой комбинацией индексов | I1: все комбинации, bool/negative rejection. Отказ при FieldPath/presentation логике или неоднозначных индексах |
| PatchSetInvariantCode; WorldMismatchDetails, MissingPackDetails, DuplicatePlayerDetails, DuplicateSectionDetails, MissingPreparedDependencyDetails, PreparedDependencyOrderDetails, PatchOperationMismatchDetails, PatchSectionMismatchDetails, DuplicatePatchOrdinalDetails — §9.4 | Каждый record хранит только свою машинную причину; owning refs/value types, без IO | I1: отдельно проверить discriminator и exact поля каждого record, strict/frozen; причина читается без message/request. Отказ при optional универсальном payload или копировании owning refs |
| DomainSection, SectionHeader — §§3.2/7.4 | Typed секция и её локальные header invariants; P: PatchData, без registry/IO | I1: сохраняются payload type, порядок и nested checks. Отказ при dict/BaseModel fallback, изменении порядка или дублировании header checks в assembler |
| PreparedSectionDependency, PublishedSectionDependency — §7.4 | Разные ссылки prepared/published; только данные | I1: prepared key/order проверяются отдельно от published ref. Отказ при lookup storage, проверке published tuple position или объявлении fingerprint проверенным сборкой |
| WorldPublicationRef, PlayerHeadExpectation, WorldSnapshotRef, PlayerSnapshotRef, SectionStateRef, PatchSectionMetadata, PatchSectionRegistry, ValidatedFieldPath — §7.4 | Для каждого сохраняются owning поля, nested invariants и роль из индивидуальной архитектурной строки; только существующие dataModel dependencies | I1/I2: отдельно подтвердить reuse и сохранение каждой модели; checked paths rooted в concrete child. Отказ при зеркальном DTO, IO, отключении nested validation или вымышленном path |
| SectionContract — application/patch/contracts/sectionHandler.py | Declaration model/key/version/schema; runtime проверка native bound без исполнения handler | I1: принят корректный PatchData binding, отвергнут несовместимый concrete payload. Отказ при ослаблении admission или переносе apply/codec алгоритма в declaration |
| PatchSetCodec — application/patch/encoding/patchSetCodec.py | Canonical representation через существующие schema bindings; не assemble/semantic apply | I1: существующие IDs/bytes/hash/round-trip. Отказ при вызове из assembler, новой identity или замене golden ожиданий ради прохождения |
| SectionRegistry, BoundSectionHandler, DomainSectionHandler — PS-ARCH-0 §2 | Существующие binding lookup, type-safe dispatch и owning section semantics соответственно; вне нового assembler | I1/I2: проверить каждый класс и отсутствие новых assembly callers к semantic validate/apply; registry tests сохраняются. Отказ при скрытом dispatch из сборки или незапланированном codec/handler split |
| HeaderOnlyPatch, FakePatch, FakeSection — tests/snapshotCore/support/fakeSection.py | Test-only native модели: header-only случай, payload coverage и concrete section соответственно; без production регистрации | I1: проверить каждую модель, наследование/поля/IDs по §2. Отказ при fabricated production binding или изменении payload semantics ради нового validator |
| OtherSection, OldSection — tests/snapshotCore/contracts/test_codec.py | Test-only альтернативный и исторический schema binding; существующие negative scenarios | I1: каждый negative/old-format case сохраняет смысл. Отказ при удалении проверки или автоматической смене canonical ожиданий |
| FakeSectionHandler — tests/snapshotCore/support/fakeSection.py | Existing test handler поведения секции; не assembly validator | I1/I2: existing handler tests и отсутствие вызова из assemble. Отказ при переносе core checks в handler либо изменении поведения ради fixture migration |
| IPatchSetAssembly — PS-ARCH-0 §1 | Только public signature, owning Input/Result; никаких execution/storage capabilities | I2: точное соответствие concrete реализации. Отказ при scope/registry/callback в public input |
| PatchSetAssembler — §§1/2/7.5 | Exact binding/admission, один validator, целый result/refusal; только модели и validator, память вызова | I2: wrong root/sibling, mismatched input/output S, неизменность входа, отсутствие partial success. Отказ при IO, codec/handler вызове, defaults контекста или сортировке |
| PatchSetAssemblyValidator — §§2/9.2 | Общий checker → checked paths/diagnostics; локальный collector | I2: одинаковые core facts на обеих границах и полный стабильный tuple issues. Отказ при собственных predicates, повторном сравнении UID/key или изменении facts |
| ValidatorAggregationHelper — app/dataModel/validation/diagnostics/validatorAggregationHelper.py | Request-local накопление только явно admitted concrete issues; существующий helper без нового framework | I2: несколько независимых ошибок; чужой issue отвергается, вызовы не делят collector. Отказ при early exit независимых checks или принудительном exception вместо принятого refusal |
| PatchSetAssemblyRelationIssue, PatchSetAssemblyRefused — PS-ARCH-0 §§3.3/9.4 | Public presentation причины и непустой отказ сборки; shared details/checked paths, без IO | I2: exact details/path/related_path/order, nonempty refusal. Отказ при копии details, fabricated paths, parsing message или Snapshot outcome в отказе сборки |
| WorldSnapshotService, IWorldSnapshotApply — PS-ARCH-0 §2 | Соседний consumer подготовленного PatchSet; lifecycle остаётся вне этих слайсов | I1/I2: отсутствие новых обратных вызовов assemble и изменений apply semantics. Отказ при скрытом расширении scope на public apply |

Для новых concrete test specializations и дополнительных existing классов, обнаруженных preflight, до их изменения добавить отдельное имя/модуль, ответственность, зависимости/effects и критерий отказа в этот реестр. Aliases, manifests и функции не объявлять классами: их совместимость проверяется отдельно по §2. Неизвестный consumer не считается автоматически покрытым групповой строкой.

Отчёт каждого слайса содержит для каждого затронутого класса: ссылку на фактическое объявление, вывод PASS/OPEN/FAIL по ответственности, адрес проверки/trace и результат. Отсутствие сведений или одно нарушение запрещает приёмку слайса даже при зелёных тестах. I2 начинается после закрытия I1. Архитектурный PASS и разрешение реализации не подменяют это evidence.

## 3. PS-I1 — модели, общий checker и немедленная миграция fixtures

**Вход:** архитектура §§3/9 и актуальный impact register. **Результат:** existing PatchSet использует единый check_core, typed input может представлять relation-invalid набор, локальные native fixtures соответствуют PatchData; direct construction/decode сохраняют обязательные гарантии.

Новые файлы app/:

- dataModel/patch/changes/patchData.py — PatchData;
- dataModel/patch/request/patchSetData.py — единственная схема девяти полей;
- dataModel/patch/request/assembly.py — PatchSetAssemblyInput;
- dataModel/patch/validation/invariantDetails.py — PatchSetInvariantCode, девять concrete details и union;
- dataModel/patch/validation/invariantViolation.py — факт и проверка комбинаций индексов;
- dataModel/patch/validation/patchSetInvariants.py — check_core/check_prepared_order;
- необходимые пустые package __init__.py, без reexports для compatibility.

Изменяемые файлы: PatchSet, DomainSection, SectionContract runtime admission при необходимости и локальные consumers из §2. Public assembly ещё не появляется, поэтому её готовность не заявляется.

Внутренний порядок: зафиксировать существующие field order/IDs/golden evidence → добавить данные и checker без application imports → перевести PatchSet и DomainSection → сразу мигрировать positive/negative fixtures → выполнить проверки. Все эти изменения составляют один принимаемый слайс, не промежуточные готовые поставки.

**Проверки в этом слайсе:** existing test_models/test_registry/test_codec; новые tests/snapshotCore/contracts/test_patch_invariants.py для core predicates и dependency facts. Покрыть mismatch operation/section вместе с repeated ordinal; uniqueness scoped по содержащей секции; все combination indices, bool/negative rejection; exact model_fields, module/class identity, canonical bytes/hash. Сверить tests/snapshotCore/contracts/test_typing.py. Новые факты не должны требовать application imports.

**DoD:** нет независимых копий core predicates в PatchSet; input допускает relation failures, result их отвергает; native fixtures migrated без fallback; подтверждены existing golden checks. Неподтверждённая несовместимость schema не переносится молча в PS-I2. Тесты обновляются по смыслу, не ради зелёного результата.

## 4. PS-I2 — публичная сборка и диагностики

PS-I1 evidence 2026-11-19: 69 tests PASS (test_patch_invariants, test_models, test_codec, test_registry, test_typing). Existing baseline до правок — 63 model/codec/registry tests PASS. Golden bytes/hash и IDs не менялись. Diff проверен; runtime admission SectionContract отклоняет non-PatchData. Проверки ответственности перечисленных dataModel классов — существующие AST/no-IO и nested model tests; checker читает только header.ref, общий collector создаётся на вызов. Codec/registry/handlers/Snapshot application не включены в checker. Изменённые fixtures сохраняют native class/module identity. PS-I1 закрыт; подробный итог class-by-class при завершении PS-I2.

**Prerequisite:** PS-I1 завершён. **Результат:** готовый публичный PatchSetAssembler.assemble с exact input/result binding, одним checker и детерминированными typed diagnostics, без IO.

Новые файлы app/:

- application/patch/contracts/assembly.py — IPatchSetAssembly;
- application/patch/assembly/patchSetAssembler.py — публичная реализация;
- application/patch/assembly/patchSetAssemblyValidator.py — fact → checked path presentation, не predicates;
- dataModel/patch/results/assemblyIssues.py — PatchSetAssemblyRelationIssue;
- dataModel/patch/results/assembly.py — refusal и result alias;
- необходимые package __init__.py без регистрации side effects.

Порядок выполнения метода берётся только из архитектуры §7.5; данный слайс его не переопределяет. Общий helper не меняет ответственность ради presentation. Типы concrete test bindings именованные, не являются production union.

**Проверки в этом слайсе:** новый tests/snapshotCore/contracts/test_patch_assembly.py — несколько независимых diagnostics с точными details/path/related_path/order; wrong sibling/root и повреждённый unchecked input; одинаковые core facts при direct construction и assemble; отсутствие partial success, mutation, sorting и вызова handler; отсутствие source request необходимости для машинной причины. Проверить checked selectors унаследованных полей на concrete input и вложенных union patch types. В existing typing harness — несовместимые request/output S и недопустимый родитель вместо ребёнка.

В завершение выполнить существующий snapshotCore discover как совместную регрессию изменённого shared ядра; результаты и skips записать по факту. Не заявлять проверки production DB/серверов. Устранить вызванные изменениями ошибки local consumers в этом слайсе, не создавать compatibility shim.

**DoD:** одна работающая публичная операция, точный result/refusal, structural exceptions отделены от доменных причин; presentation не содержит predicates; tests подтверждают порядок и полную независимую агрегацию. Код не содержит foreign services/IO. Ни одна integration gap не замаскирована default context или fabricated header.

## 5. Отчёт и завершение

Для каждого слайса показать diff затронутых файлов, actual checks и результат DoD. Архитектурный PASS не является PASS реализации. После PS-I2 принимается только общее ядро. Time/другие producers, production composition и DAG wiring оформляются самостоятельными интеграционными работами по [реестру](patch-set-external-contracts.md), не дописываются скрытым третьим слайсом.

## 6. Результаты реализации 2026-11-19

P2 исправлен и локально проверен: construction admission сохраняет required/metadata inherited section fields, MinLen допускает только сохранение или усиление. Регрессионный test_construction_retains_section_minimum сначала воспроизвёл два отказа теста, после исправления весь contracts discover — 92 tests OK, включая typing gate. Итоговая приёмка закрыта результатом, переданным пользователем 2026-11-19: новых существенных P1/P2/P3 нет, прежний P2 закрыт, ядро PS-I1 → PS-I2 принято. Актуальный итог — в patch-set-core-review.md; последующие записи о незавершённой независимой приёмке ниже являются историей исправления.

Коррекция по независимому ревью P2: прежний общий PASS реализации не считается окончательной независимой приёмкой. Проверяется admission обязательных structural constraints DomainSection. Test-only классы EmptySection (снятый minimum), ZeroMinimumSection (ослабленный minimum), StrongerSection (усиленный minimum), Input/Result (именованные bindings этих cases) размещены в test_patch_assembly.py; только данные без IO/регистрации. Критерий: первые две specialization отвергаются при создании assembler, усиление minimum допустимо. Оставшиеся OPEN независимого ревью этим исправлением не закрываются.

PS-I1 и PS-I2 выполнены последовательно; результат проверки ядра — PASS в согласованном scope. Принятый ответ координатора о месте вызова сохранён в архитектуре §9.2 и внешнем реестре SN-Q1.1. Snapshot admission/wiring не реализовывались.

Проверки:
- До изменений: 63 model/codec/registry tests — PASS.
- PS-I1: 69 tests (invariants/models/codec/registry/typing) — PASS.
- Общая регрессия: `python -m unittest discover -s tests/snapshotCore -t .` из backend — 205 tests, OK, skipped=1 (symlink privilege unavailable on this Windows host). Первый sandbox-прогон отказал при создании temporary SQLite directories; повтор с разрешённым доступом завершён успешно.
- После завершающих дополнений и уточнения construction admission: `python -m unittest discover -s tests/snapshotCore/contracts -t .` — 91 tests, OK, включая Pyright positive/negative gates и два дополнительных сценария PUBLISHED/union paths. Это повторное покрытие контрактов, не 91 дополнительный независимый тест сверх общей регрессии.
- Existing canonical manifests, bytes/hash expectations не изменены. Codec fixtures исправлены на согласованные operation/section identities; прежний malformed operation отдельно проверяется как отказ encode.
- Diff затронутых tracked файлов и содержимое новых файлов просмотрены. Сервер, production DB, DAG, Snapshot apply lifecycle, Time, storage/DDL не менялись. Чужие изменения рабочего дерева сохранены.

Trace публичной операции: exact child admission → strict nested revalidation → check_core/check_prepared_order → presentation/collector → отказ либо result constructor/check_core. Повторный core check в constructor использует тот же источник predicates. Порядок входа сохраняется; отказ исключает создание результата. Construction binding проверяет named strict модели и одинаковый закрытый native union.

### Индивидуальная приёмка классов

Пути ведут к фактическим объявлениям; номера строк указаны на момент проверки. Test names относятся к backend/tests/snapshotCore/contracts/. PASS существующих соседних классов означает сохранение их ответственности в рамках этой правки, а не приёмку всех будущих интеграций.

| Класс / объявление | Ответственность: результат чтения imports/calls/effects | Evidence |
|---|---|---|
| [PatchData](../../backend/app/dataModel/patch/changes/patchData.py), строка 8 | PASS — только header/identity, без IO; checker не читает payload | test_models; test_patch_invariants.test_shared_field_schema_and_header_order |
| [PatchHeader](../../backend/app/dataModel/patch/changes/header.py), строка 21 | PASS — только header/identity, без IO; checker не читает payload | test_models; test_patch_invariants.test_shared_field_schema_and_header_order |
| [PatchRef](../../backend/app/dataModel/patch/changes/header.py), строка 13 | PASS — только header/identity, без IO; checker не читает payload | test_models; test_patch_invariants.test_shared_field_schema_and_header_order |
| [PatchSetData](../../backend/app/dataModel/patch/request/patchSetData.py), строка 18 | PASS — общие поля только у родителя; input допускает relation failures, result делегирует check_core | test_patch_invariants; test_models; test_codec |
| [PatchSetAssemblyInput](../../backend/app/dataModel/patch/request/assembly.py), строка 10 | PASS — общие поля только у родителя; input допускает relation failures, result делегирует check_core | test_patch_invariants; test_models; test_codec |
| [PatchSet](../../backend/app/dataModel/patch/request/patchSet.py), строка 14 | PASS — общие поля только у родителя; input допускает relation failures, result делегирует check_core | test_patch_invariants; test_models; test_codec |
| [PatchSetInvariants](../../backend/app/dataModel/patch/validation/patchSetInvariants.py), строка 18 | PASS — pure predicates в одном месте; стабильные facts, ordinal независимо от identity | test_patch_invariants; test_patch_assembly.test_world_player_section_and_patch_key_paths |
| [PatchSetInvariantViolation](../../backend/app/dataModel/patch/validation/invariantViolation.py), строка 8 | PASS — строгие индексы и комбинации; нет presentation paths | test_patch_invariants.test_detail_records_and_every_index_combination |
| [PatchSetInvariantCode](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 15 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [WorldMismatchDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 27 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [MissingPackDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 34 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [DuplicatePlayerDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 40 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [DuplicateSectionDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 46 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [MissingPreparedDependencyDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 52 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [PreparedDependencyOrderDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 59 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [PatchOperationMismatchDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 66 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [PatchSectionMismatchDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 73 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [DuplicatePatchOrdinalDetails](../../backend/app/dataModel/patch/validation/invariantDetails.py), строка 80 | PASS — точный discriminator/состав owning reasons; frozen records без IO и parsing message | test_patch_invariants.test_detail_records_and_every_index_combination; test_patch_assembly |
| [DomainSection](../../backend/app/dataModel/patch/sections/section.py), строка 30 | PASS — typed порядок; nested/self validation сохранены; PUBLISHED не ищется в наборе | test_models; test_patch_invariants.test_prepared_order_and_ambiguous_target_are_separate; test_published_dependency_is_not_looked_up_in_batch |
| [SectionHeader](../../backend/app/dataModel/patch/sections/section.py), строка 13 | PASS — typed порядок; nested/self validation сохранены; PUBLISHED не ищется в наборе | test_models; test_patch_invariants.test_prepared_order_and_ambiguous_target_are_separate; test_published_dependency_is_not_looked_up_in_batch |
| [PreparedSectionDependency](../../backend/app/dataModel/patch/sections/dependency.py), строка 18 | PASS — typed порядок; nested/self validation сохранены; PUBLISHED не ищется в наборе | test_models; test_patch_invariants.test_prepared_order_and_ambiguous_target_are_separate; test_published_dependency_is_not_looked_up_in_batch |
| [PublishedSectionDependency](../../backend/app/dataModel/patch/sections/dependency.py), строка 26 | PASS — typed порядок; nested/self validation сохранены; PUBLISHED не ищется в наборе | test_models; test_patch_invariants.test_prepared_order_and_ambiguous_target_are_separate; test_published_dependency_is_not_looked_up_in_batch |
| [WorldPublicationRef](../../backend/app/dataModel/worldSnapshot/identity/publication.py), строка 12 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [PlayerHeadExpectation](../../backend/app/dataModel/worldSnapshot/identity/publication.py), строка 36 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [WorldSnapshotRef](../../backend/app/dataModel/worldSnapshot/identity/refs.py), строка 16 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [PlayerSnapshotRef](../../backend/app/dataModel/worldSnapshot/identity/refs.py), строка 25 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [SectionStateRef](../../backend/app/dataModel/worldSnapshot/sections/refs.py), строка 10 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [PatchSectionMetadata](../../backend/app/dataModel/patch/registry/sectionMetadata.py), строка 28 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [PatchSectionRegistry](../../backend/app/dataModel/patch/registry/sectionMetadata.py), строка 13 | PASS — existing owning модель переиспользована, поля и nested invariants не скопированы и не изменены | test_models; test_registry; dataModel AST import/IO gates |
| [ValidatedFieldPath](../../backend/app/dataModel/fields/validatedFieldPath.py), строка 77 | PASS — root concrete child, checked поля/union ветки; нет вымышленных путей | test_patch_assembly.test_parent_selector_cannot_be_used_as_concrete_root; test_all_independent_diagnostics_and_checked_union_paths |
| [SectionContract](../../backend/app/application/patch/contracts/sectionHandler.py), строка 19 | PASS — runtime admission требует concrete PatchData; не запускает handler | test_registry; test_typing |
| [PatchSetCodec](../../backend/app/application/patch/encoding/patchSetCodec.py), строка 20 | PASS — existing format/IDs/golden bytes/hash сохранены, assembly не зависит от codec | test_codec |
| [SectionRegistry](../../backend/app/application/patch/registry/sectionRegistry.py), строка 88 | PASS — existing dispatch не изменён и не вызывается сборкой | test_registry; test_codec; чтение imports/calls assembly |
| [BoundSectionHandler](../../backend/app/application/patch/registry/sectionRegistry.py), строка 17 | PASS — existing dispatch не изменён и не вызывается сборкой | test_registry; test_codec; чтение imports/calls assembly |
| [DomainSectionHandler](../../backend/app/application/patch/contracts/sectionHandler.py), строка 56 | PASS — existing dispatch не изменён и не вызывается сборкой | test_registry; test_codec; чтение imports/calls assembly |
| [HeaderOnlyPatch](../../backend/tests/snapshotCore/support/fakeSection.py), строка 32 | PASS — test-only native модели, без повторного header и без изменения canonical IDs | test_models; test_codec; test_patch_invariants |
| [FakePatch](../../backend/tests/snapshotCore/support/fakeSection.py), строка 36 | PASS — test-only native модели, без повторного header и без изменения canonical IDs | test_models; test_codec; test_patch_invariants |
| [FakeSection](../../backend/tests/snapshotCore/support/fakeSection.py), строка 42 | PASS — test-only native модели, без повторного header и без изменения canonical IDs | test_models; test_codec; test_patch_invariants |
| [FakeTarget](../../backend/tests/snapshotCore/support/fakeSection.py), строка 17 | PASS — existing payload модели без изменений, не интерпретируются ядром | test_codec |
| [FakeChange](../../backend/tests/snapshotCore/support/fakeSection.py), строка 22 | PASS — existing payload модели без изменений, не интерпретируются ядром | test_codec |
| [FakePrepared](../../backend/tests/snapshotCore/support/fakeSection.py), строка 27 | PASS — existing payload модели без изменений, не интерпретируются ядром | test_codec |
| [FakeSectionHandler](../../backend/tests/snapshotCore/support/fakeSection.py), строка 61 | PASS — семантика test handler сохранена; assembly его не вызывает | test_registry; test_patch_assembly.test_success_preserves_order_and_payload_without_handler |
| [IPatchSetAssembly](../../backend/app/application/patch/contracts/assembly.py), строка 9 | PASS — только публичная сигнатура с owning Input/Result | test_typing / typed_assembly |
| [PatchSetAssembler](../../backend/app/application/patch/assembly/patchSetAssembler.py), строка 18 | PASS — exact binding/revalidation → validator → целый result/refusal; без IO/codec/handler | test_patch_assembly; test_typing |
| [PatchSetAssemblyValidator](../../backend/app/application/patch/assembly/patchSetAssemblyValidator.py), строка 22 | PASS — facts → checked paths → local collector; relation predicates не повторяются | test_patch_assembly |
| [ValidatorAggregationHelper](../../backend/app/dataModel/validation/diagnostics/validatorAggregationHelper.py), строка 21 | PASS — request-local collector; чужой issue отвергается, независимые причины сохраняются | test_patch_assembly.test_payload_union_path_and_collector_admission; test_all_independent_diagnostics_and_checked_union_paths |
| [PatchSetAssemblyRelationIssue](../../backend/app/dataModel/patch/results/assemblyIssues.py), строка 8 | PASS — shared details, checked paths, обязательный message и непустой отказ без Snapshot outcome | test_patch_assembly |
| [PatchSetAssemblyRefused](../../backend/app/dataModel/patch/results/assembly.py), строка 9 | PASS — shared details, checked paths, обязательный message и непустой отказ без Snapshot outcome | test_patch_assembly |
| [WorldSnapshotService](../../backend/app/application/worldSnapshot/service/worldSnapshotService.py), строка 61 | PASS — соседний consumer без правок; новых обратных вызовов assemble нет; readiness public lifecycle не принимается | чтение imports/calls; snapshotCore regression |
| [IWorldSnapshotApply](../../backend/app/application/worldSnapshot/contracts/applyPort.py), строка 9 | PASS — соседний consumer без правок; новых обратных вызовов assemble нет; readiness public lifecycle не принимается | чтение imports/calls; snapshotCore regression |
| [NativeSection](../../backend/tests/snapshotCore/contracts/test_patch_assembly.py), строка 25 | PASS — именованные test-only bindings; проверки unions, exact siblings и mismatched result | test_patch_assembly |
| [OtherSection](../../backend/tests/snapshotCore/contracts/test_patch_assembly.py), строка 29 | PASS — именованные test-only bindings; проверки unions, exact siblings и mismatched result | test_patch_assembly |
| [AssemblyInput](../../backend/tests/snapshotCore/contracts/test_patch_assembly.py), строка 33 | PASS — именованные test-only bindings; проверки unions, exact siblings и mismatched result | test_patch_assembly |
| [AssemblyResult](../../backend/tests/snapshotCore/contracts/test_patch_assembly.py), строка 37 | PASS — именованные test-only bindings; проверки unions, exact siblings и mismatched result | test_patch_assembly |
| [SiblingInput](../../backend/tests/snapshotCore/contracts/test_patch_assembly.py), строка 41 | PASS — именованные test-only bindings; проверки unions, exact siblings и mismatched result | test_patch_assembly |
| [OtherResult](../../backend/tests/snapshotCore/contracts/test_patch_assembly.py), строка 45 | PASS — именованные test-only bindings; проверки unions, exact siblings и mismatched result | test_patch_assembly |
| [FakeAssemblyInput](../../backend/tests/snapshotCore/support/fakeSection.py), строка 46 | PASS — именованные test-only дети для одного FakeSection, без новых полей | test_typing / typed_assembly и invalid_assembly |
| [FakePatchSet](../../backend/tests/snapshotCore/support/fakeSection.py), строка 50 | PASS — именованные test-only дети для одного FakeSection, без новых полей | test_typing / typed_assembly и invalid_assembly |
| OtherSection в tests/snapshotCore/contracts/test_codec.py | PASS — альтернативный test-only codec binding; header/ref согласованы | test_declared_section_order_is_preserved_and_part_of_fingerprint |
| OldSection в tests/snapshotCore/contracts/test_codec.py | PASS — historical test-only binding без изменений | existing old-format/read-upgrade cases test_codec |

Остаток вне ядра: native producers, capture/identity/production union, DAG binding и внутренние Snapshot diagnostics/transport/coverage. Они не превращаются в третий слайс этого плана.

