# Policy annotations — план реализации

Статус: согласован мастером 2026-10-28; P1–P2 сданы, следующий шаг P3.
Дата: 2026-10-28. Нормативный проект: [tz_policy](../../docs/tz_policy.md).
Основание: обсуждение повторов G2-G, включая bool cases и PolicyRuleId.

## Инвентарь текущего дерева

1. `dataModel/hydrology/policy/hydrologyPolicyDefinition.py`: единственная
   доменная definition нового policy API в backend/app; два одинаково устроенных
   bool cases с ручными DirectValueRef/Equal/effect/stage/precedence/id/reason.
   Domain code ещё isolated; production consumers появятся в G10-A.
2. `dataModel/policy/objectAdmissionPolicyDefinition.py`: общий enabled rule
   уже декларативно переиспользуется, но каждому caller нужен внешний FieldRef
   и EnabledGate; ID строится отдельным способом. Zero rule имеет другой формат ID.
3. `dataModel/policy/policySpec.py`: повтор operation/behavior enum при каждой
   сборке spec; field type и wrapper reference описывают одно поле отдельно.
4. `application/policy/policyResolver.py`, `policyResolution.py`: похожие
   участки reasons/provenance/selection для behavior и priority. Это runtime
   механика с разными semantics, а не доменные аннотации; не переносить алгоритм
   в metadata и не менять его «заодно» с authoring layer.
5. `policyReferences.py`, `policyBindings.py`, `policyRead.py`: повторные проверки
   model config/type/binding относятся к разным границам declaration/instance/read.
   Compiler переиспользует действующий контракт; удалять instance validation
   ради отсутствия повторений нельзя.
6. `policyDecision.py`, placement lifecycle: ID нужен для provenance,
   conflict diagnostics, сохранения причины disabled и resume integrity.
   External lookup/SQL ownership/production codec для rule ID не обнаружены.
7. `tests/geo1/contracts/test_policy*.py`, typing planning: большинство прочих
   definition-конструкций — тесты транспорта/engine. Их прямые low-level specs
   сохраняются; domain integration fixtures мигрируют на compiler.
8. `tests/geo1/contracts/test_hydrology_generation.py`: часть runtime fixtures
   использует словари embedded settings. Перевести на typed POJO; dict tests
   сохранять там, где проверяется реальная JSON/wire граница.
9. `masks/collection/defaultCollect.py` и economy/defaultMaterialPolicy.py:
   соседние bool/enum decisions ещё вне общего resolver. Отдельная миграция,
   не текущие consumers нового compiler. G5-CP/G9-S — будущие consumers GEO-1.

## Целевая структура и карта ответственности

Новые файлы — только в подпапках; существующие public module paths сохраняются.

- `backend/app/dataModel/policy/declarations/__init__.py`: namespace, без registry.
- `.../declarations/policyDeclaration.py`: PolicyOwner, ValuePolicy[B,R],
  AdmissionPolicy[B,R], DeclarationDefaults. Common frozen descriptor contracts;
  используют существующие refs/fallbacks/enums, не импортируют application.
- `.../declarations/fieldPolicy.py`: EnabledFor, SelectByValue[T,B,R],
  ValueCase[T,B,R]. Typed field metadata; не читают instances.
- `.../declarations/policyCases.py`: PolicyCaseDeclaration[B,R] для составных
  условий; reused existing predicates/effects, domain enum case key.
- `.../declarations/policyIdentity.py`: общий RuleKind enum, CommonPolicyOwner,
  frozen identity components и единственный pure deterministic ID serializer;
  Python type/field/typed branch contract по tz_policy §3. Доступен existing
  common dataModel builder без обратного импорта application.
- `backend/app/application/policy/declarations/__init__.py`: namespace.
- `.../declarations/compiler.py`: два typed compile entry points, discovery и
  translation в existing specs; enabled/zero rules через common admission owner.
- `.../declarations/verify.py`: verifier field attachments, aliases, generic
  binding, duplicate declarations и enum/stage/operation contracts.
- Existing `dataModel/policy/objectAdmissionPolicyDefinition.py`: common gates,
  zero/default fallback semantics; ObjectAdmissionBindings и bind_value_selection
  принимают optional owner. Compiler передаёт descriptor.owner, low-level вызов
  использует CommonPolicyOwner; все IDs строит policyIdentity, без второго формата.
- Existing `dataModel/policy/policyRules.py`, `policySpec.py`: transport validation;
  public operation variants, stages и generic decision contracts сохраняются.
- Existing `dataModel/hydrology/policy/hydrologyPolicyDefinition.py`: nominal
  HydrologyGenerationPolicy owner, один descriptor и typed metadata constants.
  Удаляется ручная factory generation(); модуль перестаёт импортировать context
  и settings. Они импортируют constants, без cyclic model discovery.
- Existing hydrology generation/{generationContext,waterGenerationSettings}.py:
  только прикрепление metadata к resolved autoresolve/root enabled.

Счёт непосредственных файлов с init: dataModel/policy 9→9 (WARN), новая
declarations 5; application/policy 5→5, declarations 3;
hydrology/policy 3→3, generation 5→5. Existing contracts 5→5; новая test-папка
`backend/tests/geo1/declarations/` — init + test_declarations.py +
test_compiler.py + test_identity.py = 4. Типовые fixtures расширяются на месте.

Default/reason/fallback остаются данными своих владельцев. Нет новой таблицы
«имя поля → поведение», второго execution engine или persisted settings DTO.
Priority sources остаются явными typed refs: роли нельзя вывести по названию.
Complex cases не превращаются в field-local bool mapping насильно.

## Порядок реализации — один шаг за заход

### P0 — согласование нормативного контракта

Цель: зафиксировать authoring/compilation/identity без изменения execution.
ТЗ: tz_policy §1–6; tz_terrain_generation «Общая policy GEO-1»;
tz_cascade_context «GEO-1 — водная ось каскада».
Файлы: этот план, docs/tz_policy.md, ссылки из двух existing ТЗ и GEO-1 плана.
Контракт: annotations → existing specs → existing resolver; ID диагностический,
поведение/reason отдельные; сохранение G10-A production gate.
Проверка: ссылки, inventory фактических callers и import direction review.
Done: мастер согласовал проект; draft status снимается только явно.

P0 AGREED (2026-10-28), команда мастера «Давай» после представления ТЗ/плана.

### P1 — common declaration contracts

Цель: объявить frozen typed descriptor/metadata и identity components.
ТЗ: tz_policy §2–3.
Файлы: dataModel/policy/declarations/* (5 по карте выше);
tests/geo1/declarations/{__init__,test_declarations}.py;
tests/typing/planning/{valid,invalid}.py, pyrightconfig.valid.json.
Контракт: compiler не вызывается из contracts; common enum/default owners
единичны; ValueCase constants доступны static checker вне Annotated.
Проверка: unittest tests.geo1.declarations.test_declarations; planning positive
typing и точное совпадение expected negative diagnostics.
Done: foreign enum/mutable cases/invalid descriptor отвергаются до runtime.

P1 IMPLEMENTED/VERIFIED (2026-10-28). Frozen descriptor/field/compound contracts
и RuleIdentity/ValueBranch components готовы; serializer/compiler остаются P2.
Новые tests 17/17, existing GEO-1 contracts 115/115; positive typing 268 файлов — 0 ошибок.
Negatives planning 97/97 (+7), cascade 16/16; full cascade-check — 16 baseline registry errors, delta 0.
Existing planning config уже включает policy рекурсивно; отдельные include не нужны.

### P2 — compilation, identity и verifier

Цель: один общий перевод annotations в существующие executable specs.
ТЗ: tz_policy §3–4, §6.
Файлы: application/policy/declarations/* (3 по карте);
dataModel/policy/declarations/policyIdentity.py (детерминированный serializer);
policyDeclaration.py (общий nominal-owner guard), policyReferences.py (общий
wire-alias-aware fact detection для verifier и существующих wrappers);
dataModel/policy/objectAdmissionPolicyDefinition.py и при необходимости
policyRules.py/policySpec.py для сохранения transport validation;
tests/geo1/declarations/{test_compiler,test_identity}.py;
existing test_policy.py/test_policy_resolver.py/test_hydrology_generation.py
(assertions старого ID формата), typing fixtures.
Контракт: explicit model tuple, descriptor identity, generated IDs,
object/value overloads; общий enabled/zero owner один. No execution in compiler.
Проверка: unittest discover -s tests/geo1/declarations -t .; existing policy
и lifecycle tests с backend/tests в sys.path; typing positive/negative.
Done: две независимые domain fixtures дают те же decisions одним resolver;
permutations/type collisions/unknown/waiting/zero/conflict покрыты.

P2 IMPLEMENTED/VERIFIED (2026-10-28). Общие compiler/verifier и ID serializer готовы;
common enabled/zero rules переведены на тот же identity builder. Domain migration — P3.
GEO-1 157/157 (+25 P2), positive typing 271 файл — 0 ошибок;
negatives planning 101/101 (+4), cascade 16/16; full cascade-check — 16 baseline registry errors, delta 0.
Проверены alias metadata, inherited binding ambiguity, hash-seed/permutation identity,
unknown/waiting/fallback, authored zero и support resume без повторного resolution.

### P3 — hydrology authoring migration

Цель: убрать ручную сборку G2-G rules при сохранении runtime behavior.
ТЗ: tz_policy §5–6; GEO-1 Q-AUTO-GATES/§6.8-D/E и G2-G.
Файлы: hydrology/policy/hydrologyPolicyDefinition.py;
hydrology/generation/{generationContext,waterGenerationSettings}.py;
tests/geo1/contracts/test_hydrology_generation.py и typing fixtures.
Контракт: metadata enabled/resolved autoresolve; один descriptor; existing
terminal False и reason enum; Python fixtures typed, wire fixtures raw.
Проверка: contracts + declarations suites; full WORLD/CATEGORY/BODY matrix,
StrictBool/enum errors, json round-trip; planning typing и typecheck:cascade.
Done: в domain definition нет PolicyRuleId, Equal, SelectBehaviorEffect,
ручных stage/operation/default precedence и duplicate self-field references.
Production owners остаются за G10-A; enum outcomes/reasons явно объявлены.

### P4 — проверка consumer границ и документация

Цель: закрыть повторный выбор поведения и подготовить будущие consumers.
ТЗ: tz_policy §4–6; GEO-1 G5-CP/G9-S/G10-A.
Файлы: docs/tz_policy.md, docs/tz_{terrain_generation,cascade_context}.md,
.cursor/plans/geo-1-designed-water.md, этот план; tests/geo1/declarations/*
только при выявленной дыре приёмки.
Контракт: future definitions используют declaration API; no second bool gate;
стабильность ID внутри definition revision, no promised external key.
Проверка: поиск handwritten domain rules/ID, full policy/cascade suites,
typing baseline delta; no changes в JSON/SQL/export/production defaults.
Done: один authoring path, один compiler и один executor; inventory явно
отделяет migrated hydrology от ещё не мигрированных masks/economy.

## Baseline и ограничения

На старте G2-G contracts 115/115, planning typing 263 файлов без ошибок,
negative planning 90/90 и cascade 16/16. Full typecheck:cascade имеет 16
existing registry errors. Old CoarseFixtureAcceptance setup вызывает
coarse_snapshot без planning/capture/wait; это отдельная known baseline issue,
не основание менять smoke helper в этом плане.

Включение новых правил в persistent plan cache требует регистрации нужных
decision/enum bindings и согласованной schema/input revision в owning GEO-1
шаге; annotations/compiler эту работу не подменяют. Пока provenance не является
внешним rule-reference API, отдельный registry стабильных строковых ID не вводится.
