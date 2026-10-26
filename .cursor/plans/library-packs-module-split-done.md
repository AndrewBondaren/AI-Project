# Library packs — сплит packService.py и domainAdapters.py

ТЗ: [`docs/tz_template_library_packs.md`](../../docs/tz_template_library_packs.md) §0.2
(граница CRUD-сервиса); rules `class-size-limit`, `layer-boundaries`.

## Проблема

- `packService.py` — **1091 строка**, пять зон: contract DTO, scope/гейты,
  member write path, pack write path, remap job, facade.
- `domainAdapters.py` — **663 строки**, пять зон: ABC contract,
  два mixin, remap-helpers, три адаптера, factory.

Каждый класс < 300, но файл копит зоны — тот же сигнал, что и у
`class-size-limit`. Внешних импортёров всего два: `container.py`
(`LibraryPackService`, `build_pack_domain_adapters`) и
`packService`→`domainAdapters` — сплит безопасен, тесты internals не импортируют.

## Целевой layout

```text
libraryPacks/
  packResults.py        # PackDeleteResult/MemberDeleteResult/PackImportResult/PackRemapResult
  packScope.py          # _PackScope + _coerce_kind (гейты + shared scope)
  memberOps.py          # _MemberOps + _validate_local_uid + _pin_usages
  packOps.py            # _PackOps + _validate_dependencies
  remapOps.py           # _RemapOps + _instance_system_name + _uid_map_for
  packService.py        # LibraryPackService facade (~220 строк)

  domainAdapters/           # подпакет — весь adapter kit (правка: не свалка в корне)
    __init__.py             # re-export контракта: PackDomainAdapter, RemappedMember,
                            # DomainLibrary, DomainOutline — старый путь импорта работает
    contract.py             # ABC + unions + константы (~185)
    mixins.py               # _LibraryBodyMixin + _RegistryPointerMixin (~122)
    remapRefs.py            # _remap_structure_refs + _remap_relief_pick_policy (~101)
    relief.py               # ReliefPackAdapter (~140)
    structure.py            # StructurePackAdapter (~120)
    building.py             # BuildingPackAdapter (~109)
    factory.py              # build_pack_domain_adapters (~54)
```

Зависимости односторонние, без циклов: ops → packScope/packResults;
adapters → domainAdapters.contract + mixins + remapRefs;
factory → конкретные adapters; `contract.py` адаптеры
**не** импортирует (иначе цикл ABC↔adapter).

`container.py`: импорт `build_pack_domain_adapters` →
`domainAdapters.factory`. `packService` импортирует
`PackDomainAdapter`/`RemappedMember` из `domainAdapters` —
пакетный `__init__` сохраняет путь без правок.
Имена `_*` (приватные по пакету) сохраняются как есть.

## Шаг 1 — сплит domainAdapters.py

**Цель.** ABC + mixins + helpers + адаптеры + factory по зонам.

**ТЗ.** §0.2; `layer-boundaries` (adapter = domain body/pointer contract).

**Файлы.** Новые `adapterMixins.py`, `remapRefs.py`,
`reliefPackAdapter.py`, `structurePackAdapter.py`,
`buildingPackAdapter.py`, `adapterFactory.py`; урезанный
`domainAdapters.py`; `container.py` (1 импорт).

**Контракт.** Только перенос: сигнатуры, тексты ошибок, MRO
(`Adapter(Mixins, PackDomainAdapter)`) и поведение не меняются;
`_POINTER_UID_FIELD`/`_SYSTEM_NAME_FIELD` остаются в `domainAdapters.py`
рядом с ABC (импортируются потребителями оттуда).

**Проверка.** `python -m compileall app` + unittest (ниже).

**Done.** Файлы ≤ ~200 строк каждый; 108/108.

## Шаг 2 — сплит packService.py

**Цель.** Facade + scope + три job-класса + DTO по файлам.

**ТЗ.** §0.2; `layer-boundaries` (facade = только порядок вызовов).

**Файлы.** Новые `packResults.py`, `packScope.py`, `memberOps.py`,
`packOps.py`, `remapOps.py`; урезанный `packService.py`.
Импорты результатов в facade — из `packResults`.

**Контракт.** Только перенос; `LibraryPackService` API не меняется;
модульный docstring (ownership semantics §1.1) остаётся на facade,
job-классы несут свои docstrings.

**Проверка.** `compileall` + unittest.

**Done.** `packService.py` ≤ ~250 строк; 108/108.

## Проверка обоих шагов

`cd backend && python -m unittest tests.test_library_packs_4a
tests.test_library_packs_4b tests.test_library_packs_b3
tests.test_library_packs_schema` + `python -m compileall app`.
