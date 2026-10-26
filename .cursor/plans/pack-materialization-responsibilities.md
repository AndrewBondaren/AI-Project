# Pack materialization: перенос composition и publication

Статус: выполнено.

Цель: оставить `PackMaterializationOrchestrator` владельцем последовательности L0-операции, перенести сборку зависимостей в DI и выделить владельца публикации pack. Поведение light/full и порядок стадий сохраняются.

## 1. Перенести composition в DI

- Использовать существующую сборку `entry_refine_orchestrator()` в `backend/app/core/container/worldData.py`; явно передавать готовые entry и climate в pack.
- Удалить `_default_entry_stack()` и параметры pack, обслуживающие только эту сборку (`terrain`, `scene_path`, `rect_drain`, `job_repo`). Проверить оставшиеся конструкторные defaults и оставить только локальные простые defaults, без сборки refine-графа.
- Передавать готовый detailed-оркестратор в `WorldSurfaceMaterializationOrchestrator`; relief loader передавать ему явно, поскольку он нужен и detailed planning path.
- Удалить свойства pack `terrain`, `relief_loader`, `relief_grade_repo` после переноса всех потребителей. Остальные свойства оценивать по реальным вызовам.
- Обновить все direct/test callers на явное внедрение зависимостей; отдельную фабрику совместимости без потребителей не создавать.

## 2. Выделить владельца L0 publication

- Добавить `PackBakePublisher` в `application/worldData/pack/bake/finalize/` и собрать его в DI.
- Зависимости publisher: DB, world repository, `SourcePublicationGuard`, получение read context для мира.
- Контракт `publish(...)`: captured view, mountain template inputs, request resolve context и writer. Типы брать из существующих planning-контрактов.
- Перенести в publisher получение read context и блок `transaction_if_needed → require_fresh → recalc_manifest_counters → finalize_pack_on_world`. Существующую функцию finalize использовать повторно.
- В pack оставить условие публикации и один вызов publisher. Для существующих сценариев без публикации — явный `publisher=None`; комплект зависимостей настоящего publisher проверять при его создании.
- Убрать из pack DB, world repository, publication guard и read-context wiring, если после шага 1 других потребителей не осталось.

## 3. Сохранить границы операции

- Capture/prepare, один region-state snapshot, tile planning, drain, coarse climate, locations index, L0 bake, relief grades, fine climate остаются в прежнем порядке.
- Frozen bundle и working refs передаются тем же потребителям; вычисления остаются вне короткой publication UOW.
- Freshness guard выполняется до сохранения manifest; публикация использует актуальный world. Сохранить существующую инвалидацию read cache, включая ошибки SQL после записи файлов.
- Этот перенос не добавляет атомарность между файловой системой и SQL и не меняет detailed publication path.
- Отчёт и метрики пока оставить в pack: отдельный report builder в этот перенос не входит.

## 4. Проверки и приёмка

- Запустить существующие проверки в `backend/tests/planning/consumers/test_revisions.py` и `backend/tests/test_region_state_contract.py`, а также найденные тесты finalize/light/full и сборки контейнера.
- Проверить, что stale source запрещает публикацию manifest, вычисления идут без publication lock, snapshot региона читается один раз и передаётся в drain/L0 без замены.
- Для publisher покрыть только отсутствующие проверки поведения: порядок guard/manifest, инвалидацию при ошибке сохранения world и отклонение неполной конфигурации до bake.
- Выполнить поиск оставшихся старых параметров и свойств, проверить diff на изменение порядка стадий и значений отчёта.

Результат: один L0 orchestration owner, один L0 publication owner, сборка execution-графа в контейнере; без изменения API bake и форматов pack.

## Выполнение и проверка

- Добавлен `PackBakePublisher`; сборка publisher и detailed перенесена в контейнер. Удалены fallback entry stack и свойства pack, служившие для сборки других объектов.
- `entry`, `climate_bake` и `publisher` передаются явно; отсутствие публикации задаётся `publisher=None`.
- Обновлены direct/test callers. Добавлены проверки неполной конфигурации publisher, его DI-связей и инвалидации cache при SQL failure через L0 operation.
- Пройдено 98 тестов через `unittest`: planning consumers revisions/request boundary, region state contract, pack finalize, detailed C11, bake modes, light cleanup и WP13 entry-first. Для запуска из `backend` в `PYTHONPATH` добавлена папка `backend/tests`, используемая существующими тестовыми helper imports.
- Проверка diff whitespace пройдена с `core.whitespace=cr-at-eol`, учитывая существующие CRLF-файлы проекта.
