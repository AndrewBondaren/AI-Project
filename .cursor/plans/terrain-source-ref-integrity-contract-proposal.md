# Terrain dependencies: ограниченное semantic evidence

2026-11-14. **OPEN / NOT ACCEPTED.** Название файла сохранено по поручению Source; документ не предлагает новый публичный контракт. Последнее ограничение пользователя и таблица «Разрешённые границы уточнений» в `world-source-versioning.md` отменяют первоначальную просьбу проектировать Input/Outcome/Error и consistency boundary. Здесь только проверенные значения и открытые зависимости. Код, ТЗ и общий dossier не изменяются; владельцы доменов этим обзором не назначаются.

## Основания и предел проверки

Прочитаны AGENTS.md, обязательная приёмка в `.cursor/rules/dag-generator-interface.mdc`, Terrain dossier §5a–5b и `source-terrain-execution-audit-2026-11-14.md`. Пути ниже относительно корня репозитория. Это статическая проверка, без проверки пользовательских БД и исторических artifacts, без утверждения полноты всех динамических ссылок.

Принятое решение сохраняется: bootstrap получает явно подготовленные authored-записи нового строгого контракта; defaults/landcover являются отдельными зависимостями. Адаптация старой формы, dual-read, fallback и восстановление authored presence не разрешены. Nullable поле не означает возможность опустить его из полного целевого body.

## Namespace, scope и отсутствие

| Поле Terrain | Подтверждённая семантика и источник | Что не подтверждено |
|---|---|---|
| `terrain_category` | `worlds.terrain_category_registry`, identity `system_category`; `dataModel/terrain/worldTerrainCategoryRegistry.py`, `terrainCategoryEntry.py`; non-null string в Terrain. `entry_for` ищет точное совпадение и возвращает None при отсутствии. `docs/tz_locations.md` § terrain_category_registry описывает физическую категорию | Canonical defaults не доказывают наличие target в конкретном world. Метод поиска не является атомарной проверкой live target. Дубли identity и пустые значения требуют отдельной проверки owning политики |
| `default_material` | World namespace `worlds.material_registry`, identity `system_material`; `dataModel/materials/worldMaterialRegistry.py`: `MaterialKey = RegistryKey[WorldMaterialRegistry]`, `entry_for(str) -> MaterialRegistryEntry | None`. `docs/tz_locations.md:922`: effective material берётся из cell_material, затем terrain default. Null допустим и означает отсутствие назначенного Terrain default | Null не означает missing target по непустому ключу. Наличие строкового ключа в другом world не удовлетворяет ссылку текущего world. Политика отказа mutation/delete по отсутствующему target не установлена этим value lookup |
| `glossary_ref` | World namespace `worlds.lore_registry`, ключ map, а не поле body. `dataModel/lore/loreRegistry/worldLoreRegistry.py`: key прямо назван lore id (`glossary_ref` / `lore_ref`), `entry_for` использует dict.get. Terrain допускает None. `docs/tz_locations.md:932` берёт display_terrain из lore_registry | `LoreRegistryEntry` явно N1-W-21 stub с display_name/description; полноценного semantic CRUD из него вывести нельзя. Поведение display при null или dangling key и допустимость dangling authored ref не определены найденным текстом |
| `danger_level` | `docs/tz_locations.md` § danger_level_registry задаёт `system_danger`, priority и расширяемые N+1 уровни; `none` — обычная identity с priority=0, не null. Terrain поле non-null. Агрегация danger использует priority | Решением пользователя владелец — Locations (`docs/tz_locations.md:794`). `db/models/world.py` raw dict не заменяет typed owning контракт. Missing target, delete и foreign-scope policy этим назначением не определены |
| `default_state` | Nullable Terrain field; внешняя ссылка на identity `system_state` в `worlds.cell_state_registry` (`docs/tz_locations.md`, § cell_state_registry) | Решение пользователя: «Пока оставляем как есть с пометкой разобраться», затем «Вне скоупа этого плана». Только evidence внешней ссылки, не runtime integrity; дальнейшая проработка state прекращена |

Ссылки world-local по расположению реестров и ТЗ; это не доказательство существования публичной typed world-scoped операции. Нельзя выводить foreign-target detection из одного unscoped `str`. Пустая строка не доказана как синоним null: import validator skips не являются semantic решением для execution v1.

## Regions eligibility.fact

`application/worldData/regions/regionFacts.py` содержит фактически читаемые numeric/bool поля:

- climate: rainfall_mean, rainfall (property того же rainfall_mean), temperature, drought_trend;
- hydrology: water_table, flooding, open_water_fraction;
- relief: elevation_plain, elevation_mean, lowland_fraction;
- declaration: present, strength;
- отдельный elapsed_ticks.

Это **наблюдаемый набор текущего value_for**, не утверждённый execution-v1 vocabulary. `value_for` разрешает домены climate/hydrology/relief/flora/declaration, исключает private names, затем динамически читает numeric/bool значение. Unknown domain, unknown field, отсутствующий объект facts и отсутствующее observation возвращают одинаковый None. `flora` всегда None, consumer прямо отмечен как незарегистрированный. rainfall и rainfall_mean технически доступны одновременно; наличие alias не утверждает обе записи vocabulary для строгого нового контракта.

`application/worldData/regions/coverageResolver.py::_evaluate`: None/nonfinite даёт predicate=false, satisfaction=0; failed required исключает кандидата, optional даёт нулевой вклад. При отсутствии положительного победителя resolve возвращает None и warning; это не выбор default. `docs/tz_map_light_bake.md:910–912` подтверждает required/scoring и unresolved без default, а flora suitability описывает как цель. Следовательно, missing observation — runtime неизвестность, unknown fact — отдельная неразрешённая authored-семантика; совпадение текущего результата None их не делает одним понятием.

## Inbound references для Terrain delete

| Источник | Подтверждённые места использования |
|---|---|
| Locations cells | `docs/tz_locations.md:37,65`: nullable map_cells.system_terrain → worlds.terrain_registry; дальнейшие material/travel/danger вычисления разыменовывают Terrain |
| Locations placement | `dataModel/locations/settlement/district/placementCondition.py`: terrain_types — list[TerrainKey] либо None |
| Regions state | `dataModel/regions/regionState.py`: current_type, pending_target и transition from_type/to_type используют TerrainKey. Исторические transitions нельзя автоматически приравнивать к live блокирующим ссылкам |
| Landcover policy | `dataModel/terrainMasks/landcoverRegionsCategoryPolicy.py`: fallback_terrain, ключи terrain_policies и вложенный system_terrain. Проверять только значения map недостаточно |
| Terrain masks | `dataModel/terrainMasks/worldTerrainMasks.py`: system_terrain у mountain/ravine/road settings |
| Hydrology shore | `dataModel/hydrology/shore.py`: system_terrain; `application/jsonValidation/index/validate.py::_shore_ref_checks` проверяет target, дополнительные проверки ограничивают shore class |

Import checks в `application/jsonValidation/index/validate.py` относятся к normalized import, пропускают некоторые absent/null/empty случаи и недоступный registry; `index/build.py` может использовать canonical defaults. Это не доказательство безопасного Source DELETE и не разрешение переносить skips/defaults. Перечень выше — нижняя граница подтверждённых usages, не сертификат полного inbound inventory. Никакого cascade/remap здесь не согласовано. Historical held bodies и live references должны оставаться различимыми; точное правило блокировки удаления по каждой группе ещё не принято.

## Неразрешённые вопросы для Source review

### Дополнительная проверка двух оставшихся пунктов

**Eligibility body:** существующий `EligibilityRule.fact` — nonempty str, не enum и не registry ref. Source сохраняет точную строку как semantic content; не нормализует rainfall_mean в rainfall, не удаляет unknown rules и не подменяет missing observation default. Текущий consumer способен читать перечисленные выше поля, но это не утверждённый закрытый vocabulary. Следовательно, для POJO/codec inventory вопрос закрыт: сохранить nonempty string без нового Source whitelist. Если будущий execution contract потребует admission по исполнимому vocabulary, это отдельное owning решение Regions/Landcover; оно не выдаётся за уже существующую валидацию. Разработка нового vocabulary в текущем Source-проходе не выполняется.

**RegionState classification:** `dataModel/regions/regionState.py` и `docs/tz_world_pack_storage.md` § Region state store определяют current_type как текущее состояние, pending_target как текущую цель перехода, history как append-only tuple переходов from_type/to_type. `stateChange/consumer.py` разыменовывает current_type через _require_key; `stateChange/history.py` добавляет переход; consumer/regionStateLog читают добавленную history для логирования. Поэтому current_type и non-null pending_target относятся к live state, history.* — к историческим записям. В history хранятся TerrainKey, **не SourceVersionRef**: наличие истории не доказывает pin ревизии/retention. Нельзя автоматически переписывать history при latest rename, но нельзя и объявлять её готовым pinned-графом. Возможная потребность исторического as-of resolve предъявляется отдельно на шаге целевой интеграции, без миграции RegionState здесь. Tombstone RegionState не приравнивается автоматически к активной live usage.

1. Вопрос назначения владельца danger закрыт пользователем: Locations. `cell_state_registry` исключён из scope этого плана; вопрос назначения его владельца снят с текущего этапа. Пометка «разобраться» не является заданием продолжать проработку здесь и не удостоверяет runtime integrity Terrain.default_state.
2. Общий принцип non-null refs уже принят в `world-source-versioning.md`, раздел «Ref-integrity latest и pinned-графов (решение 2026-10-24)» и п.15: исходящие ссылки должны разрешаться в итоговом графе атомарной мутации, неявный fallback запрещён. Повторный вопрос о blanket-разрешении dangling refs снят. Nullable None остаётся отсутствием ссылки; явное непустое значение — ссылкой. Детализация охвата/override не подменяется import skips. State исключён из текущего scope.
3. Какие fact tokens входят в execution v1: rainfall или также rainfall_mean, elapsed_ticks, declaration.*, и допускаются ли ещё не исполнимые flora.*? Рекомендуемую политику не выдаём за принятую. Missing observation уже имеет описанную scoring семантику; решение об unknown token остаётся отдельным.
4. Latest-граф и pinned-графы уже разделены основным планом: исторические held revisions сохраняются, latest rename не переписывает их. Не требуется заново выбирать между общим restrict и автоматическим удалением истории. Для найденных RegionState usages остаётся конкретная классификация live/history; текстовый старый key сам по себе не доказывает pinned ref. На этом этапе фиксируется inventory, механизм проверок относится к целевому исполнению.

Вопросы адресуются через Source владельцам в разрешённых границах. Новые чаты, подагенты и APIs для закрытия пробелов здесь не создаются.

## Статус обязательной приёмки

Приёмка execution ref-integrity и полного доменного плана **не пройдена**. По правилу отсутствие сведений достаточно для отказа: точные классы публичных операций, Input/Outcome/Error, nested calls, согласованный DAG route и consistency guarantees не подтверждены и после сужения scope не проектируются. Наличие перечисленных POJO не удостоверяет CRUD данных и настроек, отсутствие дублей ошибок или атомарность.

Три запрета DAG сохраняются: никаких междоменных public calls, скрытых оркестраторов или ветвящихся pipeline здесь не вводится. Storage scope не передаётся в DTO; зеркальные refs/errors не предлагаются. Порядок основного плана не меняется. Этот evidence завершает только разрешённый обзор; согласование нового boundary относится к отдельному разрешённому шагу, а не является результатом этого документа.
