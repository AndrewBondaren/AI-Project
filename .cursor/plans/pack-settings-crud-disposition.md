# Pack — владельцы настроек и CRUD-disposition

2026-11-12. Статическая сверка кода и принятых решений, только документация. Настройки не изменялись, тесты не запускались. Основание: [обязательный CRUD-критерий и явное исключение Cache](../rules/dag-generator-interface.mdc#конкретность-публичного-crud-контракта), [принятые настройки](pack-v2-domain-contract-spec.md#5-crud-и-настройки-не-подменять-семантику), [Cache instance policy](cache-public-contracts.md#конфигурация-экземпляра-cache).

## Принятые решения сохраняются

Источник `[world_pack.manifest_cache]` → WorldPackCacheSettings → AppSettings.world_pack уже выбран. CachePolicy передаётся при создании отдельного manifest CacheService/MemoryCache и действует до пересоздания экземпляра. Пользователь явно исключил публичный CRUD настроек Cache и CacheSettingsService. Не предлагать повторный выбор источника, hot reload, межпроцессное распространение или новый mutable settings store.

Это исключение относится к CachePolicy, а не автоматически ко всем полям Python-пакета worldPack. Название WorldPackCacheSettings само по себе не устанавливает владельца каждого вложенного параметра.

Решение пользователя 2026-11-13: для `WorldPackCacheSettings.manifest_max_bytes` принято отдельное исключение из публичного settings CRUD. Значение задаётся при создании storage binding и действует до его пересоздания; отдельный сервис настроек и горячее обновление не вводятся. Изменение конфигурации существующий binding не меняет. `None` сохраняет отсутствие регистрации, не означает безлимитный размер или публичную DELETE-операцию. Исключение закреплено в общем CRUD-правиле и не распространяется на остальные настройки/лимиты. Числовое deployment-значение не выбиралось.

## Что найдено в коде

| POJO / источник | Поля и фактическое использование | Владение и disposition |
|---|---|---|
| [WorldPackCacheSettings](../../backend/app/dataModel/worldPack/bake/worldPackCacheSettings.py) | manifest_cache: CachePolicy; manifest_max_bytes: PositiveInt либо None; strict/frozen/extra forbid | Один composition input с двумя разными обязанностями; не создавать копию CachePolicy ради Pack |
| manifest_cache | [PacksWiring.pack_manifest_cache_service](../../backend/app/core/container/packs.py) создаёт отдельный CacheService/MemoryCache один раз под lock | Cache instance configuration; явное исключение из settings CRUD применяется. Источник конфигурации остаётся app/config composition |
| manifest_max_bytes | initialize_pack_storage передаёт значение в register_manifest_format; если settings или budget отсутствуют, регистрация не выполняется; после создания _pack_formats повторный initialize возвращает без пересборки | Pack storage admission budget. По решению пользователя 2026-11-13 публичный settings CRUD исключён; lifetime binding сохраняется. Не смешивать с cache capacity и не объявлять None рабочим безлимитным бюджетом |
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
| Pack manifest_max_bytes / storage budget | Composition принимает явное значение при создании binding | Binding использует захваченное значение | Новое значение применяется при пересоздании binding; горячего обновления нет | Публичного удаления настройки нет; None означает отсутствие регистрации | Все четыре публичные settings операции исключены решением пользователя 2026-11-13. Пробел CRUD для этого поля закрыт; другие настройки этим не принимаются |
| Authored world grid/resolution | Existing WorldService.create/import | World/schema slice read | WorldService.update/repair | World delete не равен reset/delete одного setting | Внешняя миграция owning World/Source контрактов; не разработка Pack и не запрет готовить собственный immutable состав |
| Legacy Pack read/bake policy objects | canonical_defaults/DI | Использование producer/reader | Отдельный typed mutation API не найден | Отдельный typed delete API не найден | Требуется disposition по роли при cutover: сохранить implementation configuration, перенести владельцу либо удалить legacy. Само наличие frozen POJO не означает исключения CRUD и не разрешает новый сервис |

По общему правилу отсутствие concrete public class/method/Input/Output/Error не считается пройденным критерием. Здесь это явно отражено, а не замаскировано N/A. При этом запрет вводить hot runtime overrides и принятый lifetime CachePolicy остаются в силе; из формального пробела нельзя автоматически вывести необходимость нового runtime settings service.

## Результат и следующий локальный шаг

Подтверждены источник конфигурации, named settings POJO, отдельность CachePolicy и Pack storage budget и фактическое startup-подключение. Явные исключения закрывают требование публичного settings CRUD для CachePolicy и manifest_max_bytes. Общая приёмка остальных настроек не объявляется: disposition legacy policies и owning configuration новых payload проверяются в соответствующих срезах. Конкретное deployment значение manifest_max_bytes и budgets payload здесь не выбирались.

Решение 2026-11-13 фиксирует исключение для manifest_max_bytes с сохранением существующего поведения. Не открывать повторно вопрос о CRUD этого поля и не выводить из исключения новый API или автоматическое пересоздание binding. Остальные требования проверяются по владельцу и роли; внешняя миграция не переносится в Pack.
