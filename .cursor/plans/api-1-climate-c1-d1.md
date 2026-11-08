# Climate C1 · D1 к согласованию

Предлагается читать настройки выбранного мира одним снимком и менять его климатические скаляры одной командой с обязательной ожидаемой ревизией. Это вертикальный срез [карточки C1](./api-1-transport-boundary.md#api-1-c1). Изменение реестров, initial и reset остаются следующими операциями карточки.

## Что исполняется сейчас

| Вход | Wire → application → storage |
|---|---|
| GET /api/worlds/{world_uid} | [get_world](../../backend/app/api/routes/worlds.py#L68) → container.world_service().get_by_id → SqliteWorldRepository.get_by_id → fetch_one по world_uid → dataclass World → asdict(world). Ответ содержит весь мир. Токен ревизии настроек не выдаётся. |
| PUT /api/worlds/{world_uid} | [update_world](../../backend/app/api/routes/worlds.py#L80) принимает dict[str, Any] → WorldService.update/_update отделяет force, нормализует partial, читает World, выбирает изменяемые ключи, вызывает merge_world_patch, normalize_world и prepare_import. После проверки invalidated_world_tables возвращает requires_force либо вызывает _save → repo.update → BaseRepository.save. Handler может очистить map_cells и возвращает asdict(result.world). Проверки expected_revision здесь нет. |
| Внутреннее чтение | [worldRow](../../backend/app/application/jsonValidation/worldRow.py) использует resolve_multi_column_world для climate_scalars и resolve_registry_list_world для climate_zones/weather_types по [WORLD_SLICES](../../backend/app/application/jsonValidation/worldSlices.py). climateRuntimeAssembler получает проекцию для исполнения. Фасад реестров применяет canonical_registry_wire, для зон также wire_adapter. Для редактирования требуется захват authored списка до runtime дополнений. |

## Источник каждого значения

Во всех строках таблицы источник сегодня — одноимённая колонка текущей строки worlds выбранного world_uid. У отдельных колонок и у этого чтения нет settings revision. В D1 каждое значение, включая дочерние поля JSON, фиксирует одна публикация World с токеном R. Read возвращает POJO-проекцию этой публикации. При восстановлении публикации нужны также соответствующие ей правила декодирования. [Модель и defaults](../../backend/app/dataModel/climate/worldClimateScalars.py) · [проектор SQL и authored mapping](../../backend/app/dataModel/worldScalarWire.py).

| Колонка / ключ wire | Тип и источник значения при отсутствии |
|---|---|
| default_climate_zone | str, temperate |
| climate_temperature_peak_min | int или null, default null. Runtime resolve_peak_bounds подставляет −40 |
| climate_temperature_peak_max | int или null, default null. Runtime подставляет 45 |
| climate_pole_mode | str, autoresolve |
| climate_pole_preset | str, binary |
| climate_local_influence_fraction | float в [0,1], 0.1 |
| precipitation_liquid | str, water. Проверяется по material registry того же capture |
| climate_parallel_workers | int или null, default null. Решение runtime о числе workers в read не входит |
| season_temp_offsets | JSON → SeasonTempOffsets. winter, spring, summer, autumn читаются по своему ключу, каждый missing при создании даёт 0. Canonical fixture задаёт −12/0/8/−4 |
| climate_zone_registry | отдельная JSON-колонка → WorldClimateZoneRegistry, список ClimateZoneEntry. system_climate и значения температуры, высоты, осадков и вариаций берутся из соответствующей записи. Runtime profile_for может дополнить значения |
| weather_type_registry | отдельная JSON-колонка → WorldWeatherTypeRegistry, список WeatherTypeEntry. Из каждой записи читаются обязательный system_weather, nullable display_weather, temp_max, temp_min, rainfall_min, glossary_ref (missing → null), priority (99), travel_modifier (1.0), need_modifiers (пустой словарь). Обоим спискам соответствует тот же R |

SQL-проектор скаляров пропускает None у атрибутов строки, а в словаре сохраняет присутствующий ключ с None. Read показывает нормализованные значения и не восстанавливает историю авторского omission. Некорректную публикацию нельзя молча чинить или заменять fixture. Девять строк до реестров исчерпывают WorldClimateScalars. Десятым станет elevation_lapse_rate только после переноса колонки-проекции, default/resolver и callers из WorldTerrainScalars. Сегодня climateGeneratorService получает его через terrain_scalars, fallback 0.65 °C/100 м. До переноса запрос изменить lapse получает UnsupportedField.

## Публичные операции D1

Имена и типы ниже предлагаются к принятию. R — непрозрачный идентификатор принятой публикации, привязанный к миру и его инкарнации. Capture включает версии входов проверки ссылок. Actor поступает из доверенного контекста вызова. API переводит path/body/header в запрос и ошибки в HTTP. Решения о defaults, ссылках и допустимости candidate принимает Climate, авторизацию и приёмку публикации обеспечивает World.

| Операция | Input | Output | Error |
|---|---|---|---|
| read_climate_settings | world_uid: EntityUid, actor: ActorContext, source: Current или At(R) | View(world_uid, revision: R, scalars: WorldClimateScalars, zones: WorldClimateZoneRegistry, weather: WorldWeatherTypeRegistry). Current разрешается один раз. At читает ровно R | WorldNotFound, Forbidden, PublicationUnavailable, InvalidStoredSettings(issues) |
| update_climate_settings | world_uid, actor, expected_revision: R, operation_id: идентификатор команды, patch: непустой PatchClimateScalars, validate_only: bool = false | При true — Preview(base_revision, candidate: ViewState, consequences). При false — Receipt(operation_id, previous_revision, view: View, consequences). ViewState содержит те же три POJO. Для no-op предлагается сохранить R. Повтор принятой идентичной команды возвращает сохранённую квитанцию | Ошибки read плюс RevisionConflict(expected,current), InvalidPatch(issues), UnsupportedField(path), InvalidReference(issues), InvalidSettings(issues), OperationIdConflict, UnsupportedLifecycle |

issues — tuple[FieldPathError,...]. consequences — ClimateConsequences из C1. Ошибка I/O передаётся как infrastructure failure. При потере ответа после commit вызывающий повторяет тот же operation_id. API может отобразить Forbidden в 403, отсутствие мира в 404, конфликт в 409, ошибки входа в 422. Production URL и HTTP DTO для этой пары ещё не выбраны.

Patch имеет девять именованных optional-by-presence полей с типами из таблицы. season_temp_offsets принимает непустой patch по четырём сезонам. Общий preparation pipeline сохраняет множество переданных ключей, применяет existing resolver и проверяет полный detached candidate. Примеры для исходных peak_min = −35 и winter = −12:

| Фрагмент команды | Результат |
|---|---|
| patch = {"season_temp_offsets":{"spring":2}} | peak_min остаётся −35, winter остаётся −12 |
| patch = {"climate_temperature_peak_min":null} | authored peak_min становится null, read возвращает null, при расчёте применяется runtime fallback |
| patch = {"climate_temperature_peak_min":0} | read возвращает 0 при допустимой итоговой паре границ |
| patch = {"climate_local_influence_fraction":null} | InvalidPatch с путём поля. Значение 0 на том же месте допустимо |
| validate_only = false | обычная guarded acceptance. true даёт preview без записи. Среди девяти скаляров bool отсутствует, false в числовом поле отклоняется до coercion |

## Writers и проверка на гонку

| Путь к worlds | Требование к World при реализации |
|---|---|
| WorldService.create → create/insert, PUT и edit_region → _update/_save, import_from_json → upsert/replace. WorldSectionHandler.import_section обслуживает bundle, включая worldCopyImport с новым UID | Начальная публикация при создании/копировании, guarded replacement при импорте в существующий мир. Region patch также достигает full-row save. Delete завершает инкарнацию |
| WorldService.repair_defaults → ensure_world_climate_defaults → repo.update | Repair может менять Climate и Materials. Выделить явную guarded операцию. Read и preview не вызывают repair |
| raceService и worldPerkService, привязка и отвязка записей → _worlds.update; templateLibrary/packs/write/writeExecutor → apply_prepared_world_columns → _worlds.update | Даже запись чужой колонки может затереть свежий Climate. Ограничить SQL write-set либо защищать общим row CAS |
| pack/bake/finalize/packBakeFinalize → require_world → deepcopy → save_manifest → world_repository.update(updated) | Финализатор пишет grid и pack metadata через целую строку. Исключить stale overwrite. terrain_pack_hash описывает manifest и не служит R |
| SqliteWorldRepository.increment_tick | SQL меняет только current_tick. Изолировать от full-row overwrite, тик не выдавать как settings revision |

World acceptance повторно проверяет authority, expected_revision и версии прочитанных зависимостей в точке записи. Сначала проверяется квитанция идентичного retry. Для нового operation_id при чтении R7 и принятой конкурентом R8 возвращается RevisionConflict(R7,R8), даже если patch затрагивает другое поле. Между сверкой и установкой новой публикации другой writer не может вклиниться. Сохранение защищённых колонок, новой ревизии, записи о consequences и квитанции имеет один commit. При конфликте остаётся целиком R8, без частичной записи, выделения публикации, очистки map_cells или запуска задач. Preview проверяет свежесть на момент capture, прав на будущий commit не даёт. SourcePublicationGuard для SurfacePlanningView не покрывает весь этот read-set.

## Решение к согласованию и первый срез

**D1.** Принять пару read_climate_settings / update_climate_settings в указанном объёме. До закрытия World acceptance доступна реализация только чтения и чистого prepare. Persistent update требует согласованного DAG/publication path из C1.

**Открытые решения.** World должен выбрать durable источник R, хранение исторического состояния и квитанций, механизм атомарной проверки read-set и trusted authority. Climate должен утвердить политику отсутствующего authored registry, проверки допустимых зон и material refs, обратных peak-границ и диапазона workers. Climate/Pack/Snapshot должны определить поддержанные lifecycle и применимые последствия публикации. Для lapse отдельно требуется принять миграцию reader/writer и правила finite/null. Эти зависимости нельзя закрыть одним сравнением хеша SQL-строки.

**Первый срез после согласования.** Реализовать типы View/Patch и чистый prepare поверх выбранного capture и существующих resolver, затем read через owner interface на том же capture. Приёмка среза — совпадение девяти ключей с model_fields, вложенный patch сезона, отдельные случаи null/0/false, отсутствие repair и записи в preview, привязка результата к R. Следующий storage gate проверяет гонку двух команд и stale bake/race writer в интеграции. Подключение endpoint требует отдельного решения.
