# PS-ERROR-1 · независимое ревью D2

HEAD `d01cf073967683fe22d0ec8554b837f1c0bf18b4`, 2026-11-05. **Вердикт: контрпример.** На момент проверки рабочие изменения относились только к стороннему GEO-плану.

## Открытая находка

**P2. Обе публичные операции теряют typed refusal на словаре с отрицательным целочисленным ключом.** Это Python-вход API с параметром `raw: object`. Отрицательный ключ здесь целочисленный; JSON-ключ `"-1"` является строкой.

Минимальное воспроизведение из backend:

```python
from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.physics.settings.input import (
    resolve_world_physics_settings_input_runtime, validate_world_physics_settings_input,
)

# Выполнить каждый вызов отдельно. Повторяется также с collect_only=True.
validate_world_physics_settings_input({-1: 1}, ctx=ResolveContext(validate_only=True))
resolve_world_physics_settings_input_runtime({-1: 1}, ctx=ResolveContext())
```

Ожидался `PhysicsSettingsInputRefused` со структурной причиной в `ctx.report.issues`, без значения и без fallback. Фактически каждый вызов выбрасывает Pydantic `ValidationError` при создании `WireLocation(parts=(-1,))`, до reporting. [Physics mapper, строки 52–55](../../backend/app/application/physics/settings/input.py#L52) передаёт loc ошибки `invalid_key` в [field_issue, строка 35](../../backend/app/application/jsonValidation/resolution/wireIssues.py#L35). [WirePart, строка 11](../../backend/app/dataModel/validation/importIssues/wireLocation.py#L11) допускает только неотрицательные индексы. Структурную причину можно привязать к содержащему объекту при непредставимом сегменте. Требуется регрессия для обеих операций.

## Проверки через публичные операции

Свежие request-local contexts для validate и runtime, каждую строку повторили с emit и collect_only. Сравнивались объекты результата, blocking issues и diagnostics целиком. В таблице указано число вызовов warning для validate/runtime при emit. При collect_only оно равно нулю во всех строках.

| Полный ввод, если не указано иное | Validate | Runtime | Warning |
|---|---|---|---|
| Отсутствует gravity, `{}` | Resolved, 9.80665 | Resolved, 9.80665 | 0/0 |
| Явный 0 | Resolved, 0.0 | Resolved, 0.0 | 0/0 |
| `{}`, partial=True | Refused, EXPECTED_OBJECT | Такой же отказ | 0/1 |
| Явный null | Refused, одна PhysicsGravityTypeError | Resolved, 9.80665, одна PhysicsGravityDefaultApplied | 0/1 |
| null и удалённый ключ g | Refused, invalid_gravity и REMOVED_FROM_WIRE | Те же две blocking issues, diagnostics пусты | 0/2 |

Для fallback профильный тест сверяет code, checked path, arguments и location с причиной в validation. В результате есть выбранный default, в отчёте runtime одна continuation и ноль blocking issues. Повтор того же вызова в общем request-local report даёт один WarningError суммарно. Производитель — runtime input operation через report_continuation. Validation записывает blocking issue без warning. Collect_only сохраняет тип, значение и причины.

Для **replace и reset** строились два валидных view мира w с gravity 0 и 3. При expected_ref от первого и current от второго обе операции вернули PhysicsSettingsChangeRefused с REVISION_MISMATCH. Замена current.ref ссылкой первого view при сохранённых settings второго дала PhysicsSettingsAdmissionFailure с SettingsContentMismatch раньше проверки revision. Снимки request/current до и после идентичны; prepared result отсутствует. Профильный тест отдельно сверяет полные expected/observed refs, schema и world mismatch. Расхождение refs устанавливается относительно переданного current.

## Повтор owning gate

Оба списка unittest из §P3.21 выполнены одним запуском из backend локальным интерпретатором: **69/69 OK**. Включён test_settings_typing, который запускает оба project Pyright config и сверяет файл, строку, severity и правило всех четырёх ожидаемых reportArgumentType. Positive diagnostics пусты. Прошли профильные JSON round-trip, bypass/completeness, mapper fault, codec и cancellation cases. Поиск публичных операций в backend/app выявил только определения и внутренние вызовы prepare → capture.

Граница результата — изолированный D2. I0 routing, execution transport, storage/CAS, production bindings и пользовательская приёмка остаются открыты.

## Повторная проверка P2 · 2026-11-06

**P2 — FIXED.** Проверено рабочее дерево с исправлением поверх HEAD `d01cf073`. Прямые вызовы `validate_world_physics_settings_input` и `resolve_world_physics_settings_input_runtime` с отдельным контекстом для каждого входа дали одинаковые результаты для emit и collect_only.

| Python-вход | Возвращённый тип в обеих операциях | Причина и location при префиксе settings |
|---|---|---|
| `{-1: 1}` | PhysicsSettingsInputRefused | WireShapeIssue / VALIDATION_ERROR / `("settings",)` |
| `{"-1": 1}` | PhysicsSettingsInputRefused | WireShapeIssue / VALIDATION_ERROR / `("settings", "-1")` |
| `{"gravity_acceleration_m_s2": None, -1: 1}` | PhysicsSettingsInputRefused | PhysicsGravityTypeError / invalid_gravity, затем WireShapeIssue / VALIDATION_ERROR; location обеих причин `("settings",)` |
| `{"gravity_acceleration_m_s2": 0}` | PhysicsSettingsInputResolved | gravity равна 0.0, issues и diagnostics пусты, предупреждений 0 |

[Physics mapper](../../backend/app/application/physics/settings/input.py#L52) переводит invalid_key в WireShapeIssue на содержащем объекте, а для extra_forbidden сохраняет строковый адрес через field_issue. При каждом отказе причины в report совпали с result.issues, diagnostics пусты. Исходные словари и location контекста сохранились. [Reporting](../../backend/app/application/jsonValidation/resolution/diagnostics.py#L93) дал 0 предупреждений в validation и collect_only. В runtime emit получено по одному WarningError для одиночных причин и два для смешанного отказа. Отдельно для одной gravity=None runtime вернул 9.80665 с одной диагностикой продолжения, validation вернула PhysicsSettingsInputRefused.

Две новые регрессии прошли 2/2; профиль §P3.21 прошёл 71/71. Прямой Pyright valid завершился с кодом 0 и без диагностик; invalid — с кодом 1 и четырьмя ожидаемыми reportArgumentType на строках 13–16 invalid.py. Вердикт относится только к P2. Пользовательская приёмка D2 остаётся открытой.
