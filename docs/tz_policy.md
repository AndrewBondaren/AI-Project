# ТЗ: декларации общего policy через аннотации

Статус: контракт согласован 2026-10-28; P1 common declarations реализован и проверен.
Compilation, ID serialization и domain migration выполняются следующими шагами P2–P3.
Этот документ задаёт целевой authoring layer над существующими PolicySpec и
PolicyResolver. До его внедрения действует текущий контракт
[GEO-1](./tz_terrain_generation.md#общая-policy-geo-1).

## 1. Владение и поток данных

Домен один раз объявляет policy descriptor, семантику полей и domain cases.
Общий compiler переводит metadata в existing ObjectAdmissionPolicySpec или
ValueSelectionPolicySpec; общий PolicyResolver исполняет spec.

Поток: authored POJO → существующий cascade → resolved POJO/context →
typed PolicySource bindings → compilation из типов → PolicyResolver → decision.
Compilation не читает значения instances, не выполняет cascade, predicates,
fallback, RNG, geometry или scheduling. Spec неизменяем и может переиспользоваться
для одинакового набора типов; исходные instances передаются resolver отдельно.

Contracts и доменные декларации находятся в dataModel; compilation и execution —
в application/policy. Общие модули не импортируют hydrology/economy/terrain.
Python metadata не добавляют persisted поля, JSON/SQL-копии или authored mode.

## 2. Что объявляется один раз

### 2.1. Policy descriptor

`PolicyOwner` — номинальный тип идентичности policy, без методов исполнения.
Один домен объявляет свой owner и один frozen descriptor с этим owner.
Несколько policy могут возвращать один enum; behavior enum не является identity.

`ValuePolicy[B,R]` содержит owner, тип behavior enum B, тип reason enum R,
optional disabled_behavior, tuple existing PolicyFallback[B] и общий
default RulePrecedence. `AdmissionPolicy[B,R]` содержит тот же typed binding,
existing authored/domain/terminal PriorityReference и fallback declarations.
Operation выводится из варианта descriptor; автор не повторяет operation tag.
Disabled behavior применим к value variant по действующему G2-G контракту.

Common default precedence принадлежит одному общему declaration POJO и равен 0.
Домен задаёт override только при смысловой необходимости; несколько одинаково
приоритетных несовместимых cases по-прежнему дают RULE_CONFLICT.
Приоритет размещения и RulePrecedence остаются разными типами и механизмами.

Descriptor не заменяет WaterGenerationDefaults/PlacementPolicyDefaults.
`autoresolve=False` в terminal POJO — default; False в case — сопоставляемое
значение. Они не ссылаются друг на друга и могут меняться независимо.

### 2.2. Metadata на полях

`EnabledFor(policy)` на strict bool field объявляет hard enabled gate.
Compiler получает поле из места прикрепления metadata и подключает existing
общий enabled rule; домен не пишет Equal(False), stage, effect и rule id.
Одна policy может иметь несколько gates; каждый доказанный False отключает её.
None/coercible bool недопустимы на enabled field. Wire alias разворачивается
existing annotationPolicy helper, strict constraints сохраняются при проверке.

`SelectByValue[T,B,R]` на scalar или FactValue[T] field содержит descriptor и
tuple `ValueCase[T,B,R]`. Каждый case задаёт when:T, behavior:B и optional reason:R;
precedence наследуется от descriptor, если явно не переопределён.
Compiler выводит DirectValueRef/FactValueRef из типа поля, создаёт existing
Equal/SelectBehaviorEffect/PolicyRule со stage BEHAVIOR. Имя поля строкой,
FieldRef на это же поле и expected_behavior_type в каждом case не повторяются.

Значения False/True и enum outcomes остаются явной доменной декларацией.
Нельзя выводить смысл по имени `autoresolve`, enum `.value`, default поля,
названию `enabled` или совпадению имён mode/reason. Domain reason сохраняет
самостоятельный тип: результат и объяснение не обязаны соответствовать 1:1.

Metadata константы с typed cases создаются вне Annotated. Static checker
проверяет их constructors; общий verifier дополнительно сверяет T с фактическим
типом поля. Нельзя полагаться на проверку выражений внутри Annotated metadata.
Одно поле может иметь и Cascade metadata, и policy metadata: у них разные
владельцы исполнения. Выбор поведения использует resolved поле, а не три
повторные декларации на WORLD/CATEGORY/BODY источниках.

### 2.3. Составные cases и priority

Многополевые правила используют `PolicyCaseDeclaration[B,R]`: domain-owned
enum member как локальный case key, existing tuple predicates/effect,
optional reason/precedence. Их typed FieldRef остаются вне Annotated.
Behavior/support/priority-default stages выводятся из existing effect типа.
Для DisableEffect stage обязателен: из одного disable нельзя вывести,
является ли запрет абсолютным или зависит от уже разрешённого priority/support.

Составные cases входят в descriptor, а не дублируют field metadata.
Compiler отвергает повторную identity; не удаляет дубли молча.
Это декларативный путь для water support/coating и других будущих правил.
Raw PolicyRule остаётся низкоуровневым executable contract и тестовым инструментом;
новые доменные definitions не должны собирать его вручную.

Priority references остаются явными typed связями в AdmissionPolicy.
Compiler не угадывает authored/default/terminal роли по названиям полей.
Existing ObjectAdmissionPolicyDefinition остаётся владельцем enabled/zero rules
и common UNKNOWN_FACT fallback. Эти правила не копируются в доменные metadata.
Проверка priority=0 в executor остаётся обязательным инвариантом: произвольный
spec/новая аннотация не вправе обойти отключение через выбор behavior.

## 3. Идентичность rules

Rule ID генерируется общим pure identity builder в
dataModel/policy/declarations/policyIdentity.py. Это конструирование адреса
декларации, без исполнения policy; им пользуются compiler и existing common
admission builder, без импорта application из dataModel. Домен не задаёт строку
`hydrology.generation.declared_only` параллельно с полем и outcome.

Identity components:
- policy owner: module + qualified name номинального PolicyOwner;
- rule kind: общий enum ENABLED / VALUE_CASE / COMPOSITE_CASE / ZERO_PRIORITY;
- field rule: module + qualified name source model + bound field name;
- value case: canonical typed representation сопоставляемого значения;
- composite case: module + qualified name domain case enum + member name.

Строковый транспорт: `policy-rule/v1:` + compact canonical JSON array указанных
компонентов, ensure_ascii=True, без whitespace и случайных значений.
Scalar encoding имеет явный type tag: null/bool/int/float/str/enum;
finite float кодируется float.hex(), enum — type module/qualname/member name.
Bool отличается от int; None — от отсутствия case. Неподдержанный composite
input для SelectByValue отклоняется; membership/compound predicate объявляется
existing InSet/IsPresent в составном case. Никаких repr(object), hash(),
memory address, list index, абсолютного пути файла или порядка import/discovery.

ID не включает behavior/reason/precedence: это содержание уже идентифицированного
правила, а не его адрес. Compiler ловит duplicate typed inputs/keys до выдачи spec.
Permutation metadata/models не меняет ID. Общий zero rule остаётся один на
admission spec; переход от его legacy ID выполняется вместе с тестами.

Existing ObjectAdmissionBindings и bind_value_selection получают optional
nominal owner; compiler всегда передаёт descriptor.owner. Для прямого
низкоуровневого вызова используется общий CommonPolicyOwner из этого же
identity-модуля. Даже этот путь использует единственный serializer, без
legacy f-string ID generator. Это совместимость вызова, не второй authoring API.

ID — непрозрачный диагностический адрес, не registry key и не инструмент
разрешения смысловых конфликтов. Existing сортировка по id стабилизирует только
вывод. Equal-precedence conflict не получает lexical winner.

На текущем дереве rule_id передаётся в PolicyProvenance и disabled placement
outcome, участвует в проверке сохранения provenance при resume и в диагностике
конфликтов. Внешние lookup/override API, SQL references и регистрация policy
records в surface canonical manifest не обнаружены. Provenance сериализуем;
это не обещание стабильного публичного ключа между версиями программы.

Переименование owner/model/field/case member меняет ID и является изменением
definition revision. Existing semantic input/schema revision владельца cache
должен инвалидировать старые decisions при их будущем production включении;
до регистрации policy records в persistent cache отдельная миграция ID не нужна.
Если появится внешний rule-reference API, нужен явно versioned stable-key
контракт; скрыто сохранять Python path как публичный ключ запрещено.

## 4. Compilation и verifier

Два typed entry points: compile_value_policy(ValuePolicy[B,R], models) →
ValueSelectionPolicySpec[B,R] и compile_admission_policy(AdmissionPolicy[B,R],
models) → ObjectAdmissionPolicySpec[B,R]. Models — explicit immutable tuple
type[BaseModel], не сканирование всех загруженных классов/глобальный registry.
Descriptor сопоставляется по identity; два descriptor с одним owner — ошибка.
Compiler не получает PolicySource instances и не ищет вложенные source объекты.
Набор обязательных моделей задаёт композиция домена; unrelated metadata игнорируется.

Verifier проверяет frozen/extra-forbid/revalidation contracts sources,
совместимость фактического типа поля и T, strict enabled bool, behavior/reason
enum ownership, duplicate fields/typed case keys/generated ids, допустимость
effect/stage и object/value operation. При наследовании одно effective поле
модели читается один раз; два разных source types с неоднозначной привязкой
не выбираются по порядку MRO/tuple. Ошибка декларации выявляется до execution.

Scalar nullable fields сохраняют known None: при отсутствии явного None case
будет existing RULE_NO_MATCH. Unknown/WaitingFact не превращаются в False.
Все malformed source instances по-прежнему валидируются до hard disable.
Runtime fallback объявляется отдельно по existing PolicyFallback; compiler
не подставляет disabled_behavior при validation error/no-match.

Низкоуровневые specs по-прежнему валидируются самостоятельно. Compiler не
является способом отключить invariant checks или зарегистрировать admission
как value selection. PolicyResolver, PolicyStages и truth table остаются
единственными исполнителями predicates/precedence/support/conflicts.

## 5. Hydrology и границы миграции

Hydrology owner/descriptor, enabled metadata и два typed value cases принадлежат
existing dataModel/hydrology/policy/hydrologyPolicyDefinition.py. Этот модуль
не импортирует settings/context: они импортируют готовые metadata из него.
WaterGenerationContext.autoresolve получает SelectByValue;
WorldHydrologyGenerationFields.enabled получает EnabledFor.
Получается одно объявление False→DECLARED_ONLY, True→AUTORESOLVE и
disabled_behavior=DISABLED без domain PolicyRuleId/Equal/effect builders.

Existing category channels и terminal False не меняются. Python-mode tests
используют typed embedded settings; dict literals остаются в wire tests.
Production world owners/import/export переключаются только GEO-1 G10-A.

Будущие G5-CP и G9-S используют этот же declaration/compiler API. Их
domain predicates/default values остаются в своих доменах. Existing masks
default_collect и economy default_material_policy пока не потребляют общий
PolicyResolver; их перевод требует отдельного consumer migration inventory
и не объявляется выполненным добавлением аннотаций.

## 6. Приёмка

Один compiler и resolver обслуживают hydrology и независимую domain fixture.
Проверяются False/True/None, full cascade truth table, strict wire errors,
gate dominance, unknown/waiting, priority zero, equal-precedence conflict,
явные reasons/fallbacks, decision round-trip и неизменность resume provenance.
Permutation моделей/cases не меняет identity; behavior/reason edit сохраняет
ID, field/owner rename меняет ID; bool/int и foreign enum не сталкиваются.
Metadata не попадает в JSON settings. New positive/negative typing покрывает
constructor constants вне Annotated и rejection неверной field attachment.
Все existing policy/lifecycle tests сохраняют runtime semantics.
