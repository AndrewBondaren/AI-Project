# GEO-I9.3 — независимое ревью реестра 01–102

**2026-11-04 · FAIL по полноте.** Множества ID в таблице I9.3 и в backend/app по отдельности сверены с 01–102. Пропусков номеров нет. Вердикт [по версии 01–96](geo-i9-3-legacy-registry-review-01-96.md) остаётся историческим FAIL.

Все четыре прежних замечания закрыты на уровне реестра. Строка 97 заменяет проверку прямого relief → river сравнением полных refs двух ветвей и связывает relief inputs с capture. Строки 98/99/102 называют зарегистрированный prepared envelope независимым эталоном для W. Строки 99/100/102 передают boundary canonical source и P2 с точными refs. Строки 101/102 переносят model_config к GEO-классам и требуют проверить холодный импорт.

## Блокирующая находка — manifest зарегистрированного canonical source

**Caller и место.** По строке 100 SurfacePlanningAssembler.prepare_geo вызывает get_or_build для canonical_open_water с GeoHydrologyPlanInput. В backend/app/application/worldData/planning/composition/planProviders.py:64–76 функция declared_binding фиксирует SURFACE_MANIFEST для входа, fingerprint, cache codec и зарегистрированного контракта. PlanningService перепроверяет input fingerprint и публикует output fingerprint через один contract.manifest (backend/app/application/planning/service/planningService.py:115–118,143–145). На чтении RegisteredPlanContract.validate_envelope пересчитывает output с тем же manifest (backend/app/application/planning/providers/planProvider.py:37–47).

**Последствие.** Surface manifest содержит GeoHydrologyPlanInput, но не WaterMembershipRun, CanonicalOpenWaterSource и его envelope. Их wire ID 60004/60007/60008 принадлежат OPEN_WATER_SOURCE_SCHEMA_V1 (backend/app/application/worldData/generators/hydrology/encoding/sourceSchema.py:44–80). У source manifest, в свою очередь, нет GeoHydrologyPlanInput. При буквальном использовании declared_binding кодирование результата в PlanningService не сможет получить ID типа. Подстановка только source manifest переносит отказ на вычисление входного ключа. Дополнительно строка 102 вкладывает source envelope в GeoSurfacePlanBundle, который зарегистрирован в surface manifest под ID 255 (backend/app/application/worldData/planning/encoding/surfaceManifest.py:521).

**Требуемое действие.** Дополнить 91/99/100/102 владельцем manifest для source binding и кодирования содержащего его bundle. Один вариант — совместимый manifest из surface и зафиксированных source entries через существующий merge_manifests (backend/app/application/encoding/canonicalCodec.py:124–138). Сохранить исходные wire IDs и обязательную проверку source diagnostics. Уточнить судьбу wire ID 255 при изменении layout bundle.

**Приёмка.** На подлинном GeoHydrologyPlanInput и семи refs получить source через PlanningService на холодном и прогретом кэше. Независимо пересчитать input fingerprint по SURFACE_MANIFEST и output fingerprint по OPEN_WATER_SOURCE_SCHEMA_V1 с теми же dependencies и diagnostics. Сверить оба значения и полный ref, переданный boundary. Выполнить round-trip нового GEO bundle с непустым wet run и проверить согласованное отклонение старого layout.

Проверка статическая. Приёмка реализации удаления и выполнение перечисленных сценариев остаются отдельным этапом. [Основной план, I9.3](geo-1-designed-water.md#i93-реестр-удаления-старого-пути-гидрологии)
