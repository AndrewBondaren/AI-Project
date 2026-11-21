# Lifecycle: соответствие текущей логики и целевой архитектуры

Дата фиксации: 2026-11-21. Документ сохранён по поручению пользователя как ориентир миграции. Связан с [основным планом](entity-lifecycle.md) и [ТЗ Lifecycle](../../docs/tz_entity_lifecycle.md).

## Назначение и границы

Таблица сопоставляет проверенное поведение существующего пути регионов с целевой архитектурой. Она помогает сохранить предметные расчёты, основания и наблюдаемый результат при изменении ответственности, orchestration и публикации. Это не полная инвентаризация всех доменов и не утверждение, что вся существующая логика уже использует Lifecycle, native patches или Snapshot.

Основание текущей колонки — статическое чтение кода, без запуска приложения. Срез относится к дате фиксации; перед реализацией его нужно повторно сверить. Общие application/lifecycle и dataModel/lifecycle на момент сверки отсутствовали. Совпадение слова lifecycle в Time, Placement, Artifacts или DAG не означает общий жизненный цикл сущностей.

Статусы: **принято** — согласован принцип, но не обязательно exact API или реализация; **предложение** — требуется решение; **OPEN** — контракт или доказательство отсутствует. Сохранение этой таблицы не принимает её предложенные пункты. Источник нормативных решений — ТЗ и решения пользователя; таблица не создаёт второе ТЗ.

## Таблица соответствия

| Аспект | Как сейчас | Как нужно в новой архитектуре | Что сохраняем / статус |
|---|---|---|---|
| Запуск изменения | HTTP → WorldService → DeclaredRegionEditor → StateChangeConsumer | HTTP → engine DAG → публичные операции владельцев → PatchSet → Snapshot | Предметный результат сохраняется; последовательностью управляет DAG. Exact bindings OPEN |
| Сравнение объявлений | reconcile сравнивает старые и новые регионы, выбирает add/remove/evaluate | Предметный домен рассчитывает typed результат сравнения; DAG запускает необходимые публичные операции | Само сравнение остаётся предметной логикой. Public контракт OPEN |
| Создание региона | add_declared создаёт RegionState и записывает его | Предметный домен готовит создание; Lifecycle — Create identity; связанные изменения публикуются атомарно | Сохраняем создание предметного состояния. Exact mapping OPEN |
| Изменение типа | Меняется current_type, добавляется from/to в историю | Предметный домен сохраняет изменение типа и предметную историю | Не каждый переход типа требует Lifecycle. Классификация сценариев OPEN |
| Постепенное изменение | pending_target/progress накапливаются до порога | Остаются у региона | Динамику региона не переносить в Lifecycle |
| Учёт вычислений | last_eval_tick/spec_fingerprint в RegionState | Предметное состояние или его owning preparation contract | Это не поля общей lifecycle-проекции |
| Завершение | Установка tombstone | Если смысл — завершение существования, домен предлагает End; предметный эффект и переход публикуются вместе | Tombstone не равен End автоматически. Mapping сценариев OPEN |
| Повторное добавление | add_declared формирует свежий RegionState, не Reactivate с сохранением истории | Различать новую сущность и восстановление прежней через Reactivate | Выбор принадлежит предметному домену. Старый add mapping OPEN |
| Замещение | Общего replacement-контракта в проверенном пути регионов нет | Один Replacement содержит всех предшественников и преемников | Принято: один переход, один native patch, одна запись истории |
| Lifecycle-проекция | Отдельной общей проекции нет; используются предметные поля | Typed entity ref, активность, ссылка на последний переход | Принято; exact типы OPEN |
| Предметная история | RegionState.history: изменения типа, причина, маркер времени | Остаётся у предметного домена | Не заменять lifecycle-историей |
| История существования | Отдельной общей истории нет | Одна immutable запись на lifecycle-переход с участниками, before/after и основанием | Принято |
| Основание | DRIFT / DECLARED_EDIT / EVENT; at: str или int | Для Lifecycle — конкретное typed основание, проверенное owning-доменом | Принято. Автоматическая миграция старых причин не подразумевается |
| Хранение | История вложена в состояние; SQL-строка обновляется целиком | Предметный домен хранит payload; Lifecycle — историю и проекцию; общая атомарная публикация | Принята гарантия; physical schema/write chain OPEN |
| Несколько сущностей | evaluate пишет родителя и children одним upsert_bulk | Возможность предметного результата с несколькими сущностями сохраняется | SQL batch не определяет число native patches. Coverage OPEN |
| Пересечение участников | Нет общего lifecycle batch-контракта | В текущем плане участник не повторяется в разных переходах batch | Принято; explicit chains вынесены в отдельный план |
| Identity | У региона есть UID; у предметной history entry нет общего change_uid | change_uid — переход; operation_id — публикация; PatchRef — адрес patch | Принято; миграция старой истории OPEN |
| Повторы | Зависят от операции и текущего состояния; общего retry-контракта нет | Тот же change_uid/смысл не создаёт историю, иной смысл конфликтует | Принято; atomic duplicate-check binding OPEN |
| Применение | Прямые repository calls; при подключённом editor WorldService объединяет save/reconcile в transaction | Подготовка возвращает данные; Snapshot управляет атомарным применением по согласованным контрактам | Принято; старый writer нельзя автоматически подключить callback-ом |
| Чтение | По world_uid/region_uid | Lifecycle read относительно exact publication, различение unknown/absent/inactive | Принято; API/storage binding OPEN |
| Отображение карты | RegionStateOverlay накладывает SQL-состояние на baked membership | Читать предметные изменения из согласованного опубликованного состояния | Сохраняем наблюдаемый эффект; exact read mapping OPEN |
| Pack | Overlay не переписывает Pack | Не считать каждый переход перезаписью базового Pack; runtime через публикационный контракт | Сохраняем различие базовых данных и последующих изменений |
| Физическое удаление | cleanup_orphans удаляет tombstone rows; callers не найдены | Отдельно определить retention, удаление мира и запрет обычного удаления истории | Пункт 12 — предложение, не принято |
| Настройки | Предметные policy/registry регионов | Остаются у регионов; Lifecycle settings только при реальной необходимости | Отсутствие искусственного SettingsService — предложение |
| Ошибки | В частности ValueError и import validation errors | Именованные typed prepare errors отдельно от apply refusals | Принято; exact POJO/codes OPEN |

## Источники текущего поведения

- [HTTP route](../../backend/app/api/routes/worlds.py): edit_declared_region.
- [WorldService](../../backend/app/application/worldData/registries/worldService.py): edit_region, _save, _write_scope.
- [DeclaredRegionEditor](../../backend/app/application/worldData/regions/declaredRegionEdit.py): reconcile и diff объявлений.
- [StateChangeConsumer](../../backend/app/application/worldData/regions/stateChange/consumer.py): evaluate, add_declared, remove_declared, tombstone.
- [RegionState](../../backend/app/dataModel/regions/regionState.py): состояние и история.
- [Расчёт прогресса](../../backend/app/application/worldData/regions/stateChange/progress.py) и [append_transition](../../backend/app/application/worldData/regions/stateChange/history.py).
- [State mapping](../../backend/app/application/worldData/regions/regionStateMapping.py) и [SQL repository](../../backend/app/db/repositories/sqlite/regionStateRepository.py).
- [Read overlay](../../backend/app/application/worldData/pack/read/regionStateOverlay.py): применение current_type/tombstone при чтении.

## Использование при проектировании и миграции

1. Для каждого переносимого сценария назвать старый caller/writer, вход, изменения состояния, историю и наблюдаемый результат чтения.
2. Классифицировать изменения: предметные данные, lifecycle существования/преемственности, подготовка публикации. Не выводить классификацию только из имени поля или метода.
3. Сопоставить exact новые public Input/Output/Error и гарантии с сохранённым результатом. Несовпадения предъявить как отдельные решения, а не исправлять молча.
4. Проверить необходимые записи и атомарность. Не считать SQL batch native patch, tombstone общим End, а изменение типа — обязательным lifecycle-переходом.
5. Междоменные границы сверить у назначенного координатора DAG. Не добавлять ноды/порядок и не обходить запрет прямых междоменных вызовов.
6. Перед реализацией принять полную архитектуру основного плана. Эта таблица не даёт разрешения на срезы, cutover или удаление legacy writers. При изменении исходников обновить evidence и дату, сохранив различие прежнего поведения и принятой цели.

Расширение пересекающихся переходов: [отдельный план](entity-lifecycle-overlapping-transitions.md). Сохранение старой семантики не требует сохранять прежние нарушения целевой архитектуры.
