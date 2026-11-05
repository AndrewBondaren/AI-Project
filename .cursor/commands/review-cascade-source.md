---
name: review-cascade-source
description: Code review нормализации источников каскада, запуск регрессий и чтение фактического economic_tier и provenance.
---

Проведи code review и тестирование на текущем HEAD с учётом рабочих правок по [карточке бага](../plans/cascade-source-normalization-bug.md). Укажи ревизию. Код не менять. Проверь возврат нормализованного POJO из validate_source и передачу этого же результата в Link на SETTLEMENT, DISTRICT, AREA, BUILDING и ROOM. Сверь порядок источников, authored presence, отсутствие мутации родителя и сохранение seed/anchor.

Из корня репозитория в PowerShell запусти:

```powershell
Push-Location backend
try {
    ../.venv/Scripts/python.exe -m unittest tests.test_cascade_context_baseline tests.test_cascade_migration_m2 tests.test_context_extend tests.test_runtime_world_edit_policy tests.test_e6_consumers.SourceConsumerTests.test_scope_uses_normalized_range_from_unchecked_source tests.test_e6_consumers.SourceConsumerTests.test_plot_lower_priority_range_and_band_are_not_silently_ignored tests.test_e6_consumers.SourceConsumerTests.test_settlement_payload_material_is_validated_before_extend tests.test_e6_consumers.SourceConsumerTests.test_invalid_authored_source_never_reaches_extend tests.test_e6_consumers.SourceConsumerTests.test_district_range_and_unavailable_registry_reject
    if ($LASTEXITCODE -ne 0) { throw 'Cascade tests failed' }
} finally { Pop-Location }
```

Отдельно пройди полную цепочку города до здания через реальные scope-builder, без пустой подстановки вместо города и без подмены extend, RNG и materializer. Из каталога backend выполни этот Python-код проектным интерпретатором:

```python
from dataclasses import replace
from tests.test_cascade_context_baseline import fixture
from app.application.cascade.locationScope import settlement_context, district_context, area_context, building_context
from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate

world, building, _ = fixture()
city = replace(building, location_uid="city", system_location_type="settlement", system_economic_tier="t1")
district = DistrictTemplateEntry(system_name="d", display_name="D", district_type="residential")
plot = PlotLayoutTemplate(system_name="p", display_name="P")

def source(model, bounds, unchecked):
    if unchecked:
        return model.model_copy(update={"economic_tier_range": bounds})
    return type(model).model_validate({**model.model_dump(exclude_unset=True), "economic_tier_range": bounds})

def walk(unchecked, building_tier):
    city_ctx = settlement_context(world, city)
    d = district_context(world, city_ctx, source(district, {"min": "t3", "max": "t6"}, unchecked), district_uid="d")
    a = area_context(world, d, source(plot, {"min": "t5", "max": "t8"}, unchecked), area_uid="p")
    b = building_context(world, a, replace(building, system_economic_tier=building_tier))
    return [(ctx.level, ctx.economic_tier, ctx.provenance["economic_tier"]) for ctx in (city_ctx, d, a, b)]

for own_tier in (None, "t9"):
    typed, unchecked = walk(False, own_tier), walk(True, own_tier)
    print("building override:", own_tier, "chain:", unchecked)
    assert unchecked == typed
    assert [tier for _, tier, _ in typed] == ["t1", "t3", "t5", own_tier or "t5"]
    assert typed[-1][2][0] == (typed[-1][0] if own_tier else typed[-2][0])
```

В ответе приведи фактические tier и provenance на всех четырёх уровнях для наследования и собственного значения здания, результат unittest и найденные дефекты с файлом, строкой и воспроизведением. Для отсутствующего диапазона, явного null, неизвестной и обратной границы укажи, каким тестом подтверждено поведение. Отдельно отметь всё, что не удалось проверить. Если тесты упали, продолжи независимую пробу чтения каскада.
