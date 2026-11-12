# Pack — владельцы настроек и CRUD-disposition

2026-11-12. Статическая сверка кода и принятых решений, только документация. Настройки не изменялись, тесты не запускались. Основание: [обязательный CRUD-критерий и явное исключение Cache](../rules/dag-generator-interface.mdc#конкретность-публичного-crud-контракта), [принятые настройки](pack-v2-domain-contract-spec.md#5-crud-и-настройки-не-подменять-семантику), [Cache instance policy](cache-public-contracts.md#конфигурация-экземпляра-cache).

## Принятые решения сохраняются

Источник `[world_pack.manifest_cache]` → WorldPackCacheSettings → AppSettings.world_pack уже выбран. CachePolicy передаётся при создании отдельного manifest CacheService/MemoryCache и действует до пересоздания экземпляра. Пользователь явно исключил публичный CRUD настроек Cache и CacheSettingsService. Не предлагать повторный выбор источника, hot reload, межпроцессное распространение или новый mutable settings store.

Это исключение относится к CachePolicy, а не автоматически ко всем полям Python-пакета worldPack. Название WorldPackCacheSettings само по себе не устанавливает владельца каждого вложенного параметра.

## Что найдено в коде

| POJO / источник | Поля и фактическое использование | Владение и disposition |
|---|---|---|
| [WorldPackCacheSettings](../../backend/app/dataModel/worldPack/bake/worldPackCacheSettings.py) | manifest_cache: CachePolicy; manifest_max_bytes: PositiveInt либо None; strict/frozen/extra forbid | Один composition input с двумя разными обязанностями; не создавать копию CachePolicy ради Pack |
| manifest_cache | [PacksWiring.pack_manifest_cache_service](../../backend/app/core/container/packs.py) создаёт отдельный CacheService/MemoryCache один раз под lock | Cache instance configuration; явное исключение из settings CRUD применяется. Источник конфигурации остаётся app/config composition |
| manifest_max_bytes | initialize_pack_storage передаёт значение в register_manifest_format; если settings или budget отсутствуют, регистрация не выполняется; после создания _pack_formats повторный initialize возвращает без пересборки | Pack storage admission budget. Код подтверждает startup binding, но не формальное исключение из общего Pack settings CRUD. Не смешивать с cache capacity и не объявлять None рабочим безлимитным бюджетом |
| [WorldGridSettings](../../backend/app/dataModel/worldPack/meta/worldGridSettings.py) | authored fine_cells_per_map_cell, constraints/default policy; используется world schema slices и WorldService | Исходные данные мира, которые Pack получает как captured effective значения. Место POJO в worldPack не переносит World CRUD внутрь Pack |
| [WorldMapResolutionSettings](../../backend/app/dataModel/worldPack/meta/worldMapResolutionSettings.py) | authored world_map_cells_per_tile override; фактический side разрешает существующий producer policy | Та же граница: Pack sync_grid_metadata/write_map_tile изменяют состав версии, не редактируют исходный World setting |
| [PackReadPolicy](../../backend/app/dataModel/worldPack/bake/packReadPolicy.py) | capacities старых wilderness/location/settlement decode caches; canonical_defaults | Existing legacy read implementation policy; не CachePolicy manifest Cache. Нужен disposition при reader cutover, не автоматическое новое runtime CRUD API |
| [PackBakeDefaults](../../backend/app/dataModel/worldPack/bake/packBakeDefaults.py) | codec/zstd и отдельные bake/refine/debug/queue значения, fine policy | Смешанные обязанности старого bake stack. Codec/binding параметры остаются у Pack binding, генераторные/очередные — у соответствующих операций/потребителей. Нельзя объявить весь POJO Pack settings CRUD только по пути файла |
| [ParentLightRefinePolicy](../../backend/app/dataModel/worldPack/bake/parentLightRefinePolicy.py), [TerritoryVolumePolicy](../../backend/app/dataModel/worldPack/wire/territoryVolumePolicy.py) | Refine interpolation/z-band и вычисление territory defaults | Политики вычислений producer. Числовой ParentLightRefinePolicy.z_band сохраняется. Pack принимает готовую geometry; новый CRUD этих политик в Pack не вводится |
| [PathHeadingPolicy](../../backend/app/dataModel/worldPack/bake/pathHeadingPolicy.py), AppSettings.path_ahead_depth | Настройка corridor/prefetch, legacy entry refine получает app_settings.path_ahead_depth | World-loading/producer orchestration policy; не настройка immutable manifest. Миграция owning caller отдельно, без запуска entry refine из Pack |

Этот список покрывает просмотренные Pack settings/policy модели и прямые composition пути; он не объявляет все настройки приложения принятыми. Новые decoder budgets из payload roster должны получить явный binding configuration и owning disposition, а не безымянный default или заимствование CachePolicy capacity.

## Реальные операции конфигурации не равны Pack API

[ConfigManager](../../backend/app/core/configManager.py): `load(self) -> dict`, `save(self, settings) -> None`; load создаёт default config при отсутствии файла и может выполнить migration/save. Это core filesystem configuration, не pure typed domain read. WorldPackCacheSettings валидируется в _to_flat, сериализуется в _to_nested.

[AppSettings.update(self, **kwargs)](../../backend/app/core/appSettings.py) валидирует world_pack, но сам AppSettings находится в core и не является Pack dataModel CRUD input/output. [SettingsService.update(self, **kwargs) -> None](../../backend/app/core/settingsService.py) меняет app settings и сохраняет config; named Pack Input/Result/Error у него нет. Он также не пересоздаёт Pack registry/cache при изменении settings.

[GET/PUT /settings](../../backend/app/api/routes/settings.py) не экспонируют world_pack или path_ahead_depth. SettingsUpdate объявлен в API, ответы — dict; handler вызывает core service напрямую. Эти маршруты не предъявляются как целевой Pack DAG CRUD. Перенос общего settings API не входит в текущий Pack срез.

Existing [WorldService](../../backend/app/application/worldData/registries/worldService.py) имеет create(data: dict), update(world_uid, data: dict), get_by_id(world_uid), delete(world_uid). Это фактический владелец операций над World row, но не уже принятый typed CRUD отдельных settings: dict и удаление всего мира не закрывают конкретный settings delete. Pack не должен реализовывать этот внешний контракт вместо владельца.

## Проверка C/R/U/D отдельно

| Объект | C | R | U | D | Вывод |
|---|---|---|---|---|---|
| CachePolicy manifest cache | Конструктор из явной конфигурации | Экземпляр использует захваченную policy | Новый экземпляр получает новую startup policy | Не отдельная доменная операция удаления policy | Все четыре публичные settings операции исключены явным решением пользователя. Это не пробел Cache и не повод создать PackCacheSettingsService |
| Pack manifest_max_bytes / storage budget | Existing composition принимает явное значение | Binding использует своё значение; public typed read settings не предъявлен | Public typed update не предъявлен; existing registry не пересоздаётся сам | Public typed delete не предъявлен; None не означает принятый DELETE контракт | Общая формальная Pack settings приёмка OPEN. Startup-поведение доказано, но полноценный CRUD либо отдельное явно принятое исключение для этого объекта не зафиксированы найденными источниками |
| Authored world grid/resolution | Existing WorldService.create/import | World/schema slice read | WorldService.update/repair | World delete не равен reset/delete одного setting | Внешняя миграция owning World/Source контрактов; не разработка Pack и не запрет готовить собственный immutable состав |
| Legacy Pack read/bake policy objects | canonical_defaults/DI | Использование producer/reader | Отдельный typed mutation API не найден | Отдельный typed delete API не найден | Требуется disposition по роли при cutover: сохранить implementation configuration, перенести владельцу либо удалить legacy. Само наличие frozen POJO не означает исключения CRUD и не разрешает новый сервис |

По общему правилу отсутствие concrete public class/method/Input/Output/Error не считается пройденным критерием. Здесь это явно отражено, а не замаскировано N/A. При этом запрет вводить hot runtime overrides и принятый lifetime CachePolicy остаются в силе; из формального пробела нельзя автоматически вывести необходимость нового runtime settings service.

## Результат и следующий локальный шаг

Подтверждены источник конфигурации, named settings POJO, отдельность CachePolicy и Pack storage budget, фактическое startup-подключение и отсутствие предъявленного typed Pack settings CRUD. Cache исключение закрывает свой объект; весь Pack settings критерий не закрыт. Конкретное deployment значение manifest_max_bytes и budgets payload здесь не выбирались.

Никакой новой policy выбора/изменения настроек этим документом не принимается. Формальный остаток сохраняется в приёмке; независимые Pack-owned contracts можно продолжать. Следующая доступная работа — ответственность классов и dependencies/effects уже описанного API, с сохранением границ public contract / implementation и трёх запретов DAG. Это не требует переоткрывать настройки или перехватывать внешнюю миграцию.
