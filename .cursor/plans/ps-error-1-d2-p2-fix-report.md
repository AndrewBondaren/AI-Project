# PS-ERROR-1 D2 — исправление P2, пакет независимого повторного ревью

Дата: 2026-11-05. Base HEAD при воспроизведении и исправлении: `d01cf073967683fe22d0ec8554b837f1c0bf18b4`.

Основание: [независимое ревью P2](./ps-error-1-d2-review.md). Контракт: [Physics §P3.20–P3.21](./physics-spatial-dynamics.md), [ERROR-CONTRACTS-1 / EC-11](./error-contracts-1.md). Исходный независимый отчёт не изменялся. Статус автора исправления: **FIXED candidate / AWAITING INDEPENDENT P2 RE-REVIEW**; это не пользовательская приёмка D2.

## Воспроизведение до исправления

Через каждую публичную операцию отдельно переданы Python-словари `{-1: 1}` и `{"-1": 1}`; использован свежий ResolveContext, в том числе с location=("settings",). Это разные типы ключей, не два варианта одной JSON-строки.

```python
from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.physics.settings.input import (
    validate_world_physics_settings_input,
    resolve_world_physics_settings_input_runtime,
)

for operation, validate_only in (
    (validate_world_physics_settings_input, True),
    (resolve_world_physics_settings_input_runtime, False),
):
    for key in (-1, "-1"):
        ctx = ResolveContext(validate_only=validate_only, collect_only=True)
        # До исправления каждый вызов с int -1 выбрасывал ValidationError.
        result = operation({key: 1}, ctx=ctx)
        print(operation.__name__, type(key).__name__, type(result).__name__)
```

AS-IS подтверждён до изменения production file отдельным перехватом исключений, чтобы проверить все четыре вызова. Для int -1 обе операции выбрасывали Pydantic ValidationError до reporting: `ctx.report.issues` и diagnostics оставались пустыми. Строка "-1" уже давала PhysicsSettingsInputRefused, конкретный WireShapeIssue, code VALIDATION_ERROR и location=("settings", "-1"). Validation не emit warning; runtime emit один WarningError.

Цепочка дефекта: WorldPhysicsSettings.model_validate(raw) → Pydantic `invalid_key`, loc=(-1,) → [_read_full_input](../../backend/app/application/physics/settings/input.py) → [field_issue](../../backend/app/application/jsonValidation/resolution/wireIssues.py) → [WireLocation.child](../../backend/app/dataModel/validation/importIssues/wireLocation.py) → создание parts=("settings", -1). WirePart разрешает строку либо неотрицательный int-индекс. Ошибки `string_type` и `greater_than_equal` возникали уже при конструировании диагностического адреса, до возврата PhysicsSettingsInputRefused и report_issues. Это дефект Physics input mapper, не численного расчёта и не неспособность strict POJO отвергнуть плохой ключ.

## Минимальный diff владельца

Production scope — только [input.py, _read_full_input](../../backend/app/application/physics/settings/input.py:52): 7 добавленных строк, 1 заменённая. invalid_key теперь создаёт структурную причину на containing object. Нестроковой ключ не становится строкой и не интерпретируется как индекс массива. extra_forbidden остаётся прежней веткой с точным wire loc.

```diff
-            elif error["type"] in ("extra_forbidden", "invalid_key"):
+            elif error["type"] == "invalid_key":
+                # A malformed mapping key is not a field/index in WireLocation.
+                issues.append(WireShapeIssue(
+                    code=JsonValidationCode.VALIDATION_ERROR, location=ctx.location,
+                    message="Physics settings keys must be strings",
+                ))
+            elif error["type"] == "extra_forbidden":
```

Общий field_issue, WirePart/WireLocation, shared error types, POJO/schema и операции validate/runtime не изменены. Новые contracts/enum/ports не введены. Недопустимый ключ — структурный F09 отказ в обоих режимах; разрешённый runtime fallback относится только к gravity magnitude. Расширять WirePart отрицательными индексами либо stringify плохой ключ не требуется.

Полный текущий code/test diff для рецензента из корня репозитория:

```powershell
git diff -- backend/app/application/physics/settings/input.py backend/tests/physics/test_settings_policy.py
```

## Регрессии и результат после правки

[test_negative_integer_and_string_keys_return_typed_refusal](../../backend/tests/physics/test_settings_policy.py:42) проверяет 16 комбинаций: две публичные операции × ключи int -1 / str "-1" × root/prefixed location × emit/collect_only. Проверяется точный type(result), type(issue), code, location, равенство result.issues и blocking report, пустые continuation diagnostics, отсутствие мутации и сохранение типа ключа. Значение и location контекста не переписываются. Emit/collect_only возвращают равные результаты.

| Python input | Validate и runtime: точный результат | Причина | location при prefix=("settings",) |
| --- | --- | --- | --- |
| `{-1: 1}` | PhysicsSettingsInputRefused | WireShapeIssue / VALIDATION_ERROR | ("settings",) |
| `{"-1": 1}` | PhysicsSettingsInputRefused | WireShapeIssue / VALIDATION_ERROR | ("settings", "-1") |

Validation — 0 warning. Runtime emit — 1 WarningError для одного структурного отказа; collect_only — 0. В обоих режимах нет settings value/default result и нет diagnostic о применённом fallback. Root prefix=() также проверен.

[test_invalid_key_and_gravity_do_not_publish_a_fallback](../../backend/tests/physics/test_settings_policy.py:73) проверяет обе операции на `{gravity_acceleration_m_s2: None, -1: 1}`: один Refused с concrete PhysicsGravityTypeError и WireShapeIssue в исходном порядке, обе blocking causes в report, пустые continuation diagnostics, input без mutation. Это не runtime success с частично нормализованным объектом.

Существующий профиль дополнительно проверяет корректное имя gravity, missing/default, zero/-0, custom value, прежний fallback null/negative/nonfinite/container/overflow, logging/dedup/silent, identity/prepare/JSON и закрытые typed outcomes. Они не заменены тестами нового malformed-key случая.

## Выполненные проверки

Новая регрессия из backend:

```powershell
.venv/Scripts/python.exe -m unittest tests.physics.test_settings_policy.SettingsPolicyTests.test_negative_integer_and_string_keys_return_typed_refusal tests.physics.test_settings_policy.SettingsPolicyTests.test_invalid_key_and_gravity_do_not_publish_a_fallback
```

**2/2 PASS** после production repair; до исправления воспроизведён ValidationError через обе операции.

Профиль §P3.21 из backend:

```powershell
.venv/Scripts/python.exe -m unittest tests.physics.test_settings_core tests.physics.test_settings_policy tests.physics.test_settings_typing tests.physics.test_codec_compatibility tests.planning.encoding.test_canonical_codec tests.snapshotCore.contracts.test_codec.CanonicalRequestCodecTests.test_raw_digest_is_shared_with_canonical_and_tile_hashing tests.errorContracts.test_import_issues tests.errorContracts.test_resolve_issues tests.errorContracts.test_typing tests.errorContracts.test_core
```

**71/71 PASS** (прежние 69 + две новые регрессии). Typing gate включает positive source/API и точные четыре ожидаемых negative diagnostics. Scoped git diff --check для двух Python files — PASS.

## Граница повторного ревью

Проверить P2 по реальному diff и обоим публичным вызовам, отдельно сохранив различие int -1 / str "-1". Общее независимое ревью D2 и приёмка пользователя этой записью не закрыты. Storage, I0, DAG bindings, production activation, retry/session transport и numerical solver не затронуты. Чужие изменения планов сохранены; исходный review P2 не переписан. Доказательств готовности runtime эта регрессия не добавляет.
