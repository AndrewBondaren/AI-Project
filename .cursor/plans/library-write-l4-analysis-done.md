# L-4: анализ application orchestration и атомарного применения ✅ DONE

Обновление 2026-10-13: L-4 реализован и проверен. Ниже сохранён исходный
анализ перед реализацией; актуальные компоненты и результаты — в
[архитектуре §10](library-write-l4-architecture.md#10-реализованные-швы-и-проверка--2026-10-13)
и [основном плане L-4](library-write-policy-done.md#l-4--application-orchestration-и-атомарное-применение--выполнен-2026-10-13).

Дата: 2026-10-12. Статус: анализ по фактическому коду; реализация не начата.
Основа: `plan-dependency-graph.md`, `library-write-policy-done.md`,
`docs/tz_template_library_packs.md` §0.3, §2–4, §6.

Целевая архитектура: [компоненты, контракты и UOW](library-write-l4-architecture.md).
Ниже факты кода и предложения анализа; архитектурный документ отдельно
отделяет требования ТЗ от внутренних деталей интеграции и preview.

Повторная сверка 2026-10-12: ранее принятые решения 4a–4c, ревью 4c,
4d и W2 перечислены в архитектурном документе. Их семантика не считается
открытым вопросом; ниже предложения применяются с этими уточнениями.

## Вывод и место в графе

L-4 разблокирован: L-1…L-3 реализованы. Он обязательно предшествует 4d.
5a не блокирует L-4; 5b и W2-4 требуют координации writer/adapter файлов.
Объём L-4 — новый application pipeline плюс перевод существующих входов,
а не только создание `writeService.py`/`writeExecutor.py`.

Для завершения нужны строгий persistence подготовленного плана, защищённая
проверка состояния, единый результат переговоров и устранение альтернативных
application write paths. HTTP-сериализация и UI остаются L-5. Подключение
библиотечных секций архива к world-import остаётся 4d.

## Что уже пригодно для переиспользования

Пути к Python-модулям ниже относительно
`backend/app/application/worldData/libraryPacks/`, если не указано иначе.

- `writeInspector.py`: read snapshot, источники SQL/parsed import,
  fingerprint состояния, списковые совпадения members.
- `writePolicy.py`: единственная чистая политика всего batch;
  stale/неполный выбор не выдаёт executable actions.
- `writePlanner.py`, `packWritePlanner.py`, `memberWritePlanner.py`,
  `writeRetentionPlanner.py`: фиксированные UID, подготовленные тела,
  composition/dependencies/provenance/retention и world before/after.
- `writePlanContracts.py`: typed pack/member/world actions и diagnostics.
- `backend/app/db/database.py`: `transaction_if_needed()` присоединяется
  к caller transaction; `transaction_on()` использует BEGIN IMMEDIATE.
- `backend/app/db/guardedConnection.py`: gate общей connection удерживается
  на весь UOW; конкурентные корутины не вклиниваются между statements.
- Pack/member repositories уже различают strict insert и служебный
  insert-missing. Pack metadata и member local key обновляются отдельно.

Транзакционный фундамент есть. Нужен проверяемый контракт его использования,
а не новая параллельная инфраструктура транзакций.

## Пробелы, которые нельзя скрыть фасадом

### 1. Persistence тел сейчас повторяет подготовку и делает upsert

`domainAdapters/structure.py:write_body` повторно вызывает `prepare_body`,
затем `StructureTemplateLibraryService.upsert_outline`. Аналогичные доменные
сервисы сохраняют через `_repo.upsert`; базовая реализация в
`backend/app/db/repositories/sqlite/base.py` — INSERT OR REPLACE.

Новый executor должен сохранять уже подготовленный typed outline, различая
insert и update. Проверять нужно занятость не только membership UID, но и
body row: body без membership нарушает инвариант 4a, а не является штатным
legacy-состоянием до 5b. Проверка защищает от захвата повреждённых данных.
Иначе новая identity
может молча перезаписать существующее тело до обнаружения конфликта.

Предложение: отдельный внутренний prepared-persistence контракт адаптера.
Create использует strict INSERT; replace — UPDATE существующей точной цели
с проверкой результата. SQL-конфликт откатывает batch, не запускает новый
выбор политики и не приводит к повторной генерации UID внутри apply.
Служебный insert-missing остаётся отдельным canonical контрактом.

### 2. FS parsing и запись связаны

`structureTemplateFsImport.py` и `reliefTemplateFsImport.py` читают файл и
немедленно вызывают callback upsert. `_PackOps.import_fs_pack` вызывает
adapter import, затем attach catalog. Доменные `import_path` также имеют
свои пишущие пути. Оборачивание этих функций новым сервисом не обеспечит
no-write preview.

Нужно выделить read/parse результат, преобразуемый в существующий
`WriteImportSource`; весь выбранный набор читается до решения и apply.
Повторный запрос заново читает FS; fingerprint должен отражать новые тела,
manifest и dependencies. Executor не открывает файлы заново: сохраняет
ровно подготовленный снимок. Изменение файла после этого чтения относится
к следующему импорту, а не меняет применяемый plan.

Single-member FS import должен оставаться member-операцией. Нельзя представить
один файл частичным pack replace и удалить остальных членов пака.

### 3. Перевод явного редактирования по UID в общий механизм

ТЗ §0.3 допускает редактирование однозначной цели без отдельного выбора
copy/replace. Сейчас `LibraryWriteRequest` описывает source/destination и
selections; `LibraryWritePolicy` требует preview token при replace с matches.
У него нет отдельного признака explicit edit.

Это задача интеграции существующего входа `update_member_body` с общими
access/validation и replace planner по §0.3. Отсутствие отдельного edit-признака
не доказывает необходимость нового публичного DTO или API. Предложенные
в обсуждении EditMemberRequest/edit_member/expected_token не приняты и
не входят в требования L-4. Нельзя выдавать фиктивный клиентский confirm
либо помещать вторую policy в compatibility wrapper.
Создание пустого пака, metadata/dependencies update и delete также требуют
явно очерченной общей write-границы; текущий import/copy request не описывает
весь CRUD. Для удаления сохраняется собственный usage/force контракт §0.2,
его не нужно превращать в copy/replace negotiation.

### 4. PolicyRequired с preview последствий ещё не собран

Форма обмена согласована 2026-10-12: UID целей + options/reasons + preview
последствий + token в первом policy_required. Полные тела доступны отдельным
чтением по UID при необходимости; обязательный отдельный preview-запрос
не нужен. Остаётся подключение общей pure подготовки, а не выбор протокола.

`WriteDecision` содержит choices/issues/token, но не concrete diff.
`LibraryWritePlanner.prepare` принимает только READY. Поэтому первый запрос
с совпадениями пока не может просто вызвать planner для получения preview.

Нужно определить typed application result: applied, policy_required,
rejected; stale остаётся признаком policy_required. Preview может показывать
последствия конкретных разрешённых replace-вариантов через существующие
pure planners. Неизвестная новая copy identity не должна генерироваться
и выдаваться за окончательную до `copy_system_name` пользователя.
Preview не является сохранённым разрешением на apply: повторный запрос
снова inspect/decide/prepare. В apply UID уже не меняются.

### 5. Старые операции содержат собственные решения и результатные DTO

`packService.py` делегирует `_MemberOps`, `_PackOps`, `_RemapOps`;
`reinstantiateOps.py` имеет собственные confirm/token и execution loop.
Их нужно перевести на application service, сохранив пригодные pure helpers.
Новые persistence методы должны быть нижним слоем, иначе возникнет цикл:
writeService → executor → domain service → writeService.

Старый `confirm=True` нельзя трактовать как безусловное согласие на любой
replace. Если временный compatibility adapter нужен, он переводит точную
цель и общий token в общий request; старый fingerprint/protocol удаляется.
Полное удаление confirm из wire относится к L-5.

## Предлагаемый транзакционный контракт

1. Read/parse контейнера формирует immutable parsed input до записи.
2. `LibraryWriteService.execute(request, imports=...)` входит в
   `transaction_if_needed()` и внутри неё выполняет inspect → decide.
3. Для policy_required/rejected возвращает typed результат без mutations.
4. Для READY строит plan один раз, проверяет полный набор new pack/member/body
   identities и применяет его до выхода из той же транзакции.
5. `LibraryWriteExecutor.apply(plan)` требует активной caller UOW и сам
   не делает BEGIN/COMMIT. Он не выполняет normalize/decide/UID allocation.

Для будущего 4d тот же execute вызывается внутри общей world-import UOW.
Если preview готовится раньше, перед apply выполняется повторная инспекция
внутри UOW; проверять только token внутри самого plan недостаточно — plan
не содержит request/import source для перечитывания.

Ошибки apply должны выходить из внешней транзакции и откатывать весь импорт.
Нельзя поймать SQL exception внутри caller UOW и вернуть успешный/preview
результат после частичных библиотечных writes. Если caller намерен продолжать
после ошибки, ему нужен отдельно определённый rollback/savepoint контракт;
для 4d требуемый режим — rollback всего мира.

## Порядок применения подготовленного плана

- До mutations проверить занятость всех новых identities и наличие целей.
- Вставить все новые packs до members и dependency edges.
- Сохранить подготовленные тела и membership с явным insert/update.
- Обновить существующие pack metadata и точный набор dependencies.
- Удалить только `plan.removed`; held/preserved повторно не вычислять.
- Применить подготовленные world changes, включая refs/pins и временные
  registry pointers, в общей UOW.
- Вернуть фактические UID/maps/composition и diagnostics; не сообщать
  успешную запись до завершения собственной транзакции. Во внешней UOW
  application result ещё подчинён её будущему commit/rollback.

`WorldWrite` хранит целый before/after World. Full-row save допустим только
если before прочитан в той же защищённой UOW непосредственно перед plan.
Для интеграции 4d и W2 подготовленные изменения колонок накладываются на
актуальный World в caller UOW с одним repo.update, как требует паттерн B.
Resolve/валидация выполняются при prepare; executor не нормализует повторно.
Scoped-контракт не требует нового SQL column-patch API. Writer не должен
затереть entity/config изменения внешнего импорта.

## Последовательность реализации L-4

1. Оформить result/preview по §0.3 и перевод существующего CRUD; отделить prepared
   persistence от публичных domain services. Не менять правила владения.
2. Реализовать strict executor и проверки caller-UOW/identity collisions.
3. Подключить service inspect/decide/prepare/apply и DI в `core/container.py`.
4. Перевести pack/member copy, instantiate/publish/reinstantiate и edit;
   убрать альтернативный application confirm/execution protocol.
5. Разделить FS readers/writers, подключить user imports, сохранить отдельный
   canonical insert-missing. Проверить прямые доменные callers и routes.
6. Прогнать интеграционные проверки и зафиксировать готовый шов для 4d/L-5.

Это предлагаемые внутренние подшаги, а не изменение общего DAG или статуса.

## Приёмка

- Preview, stale, неполные selections, rejected batch: ноль SQL mutations.
- Изменения SQL source/target/body/deps/refs/pins и перечитанных FS тел
  инвалидируют прежний preview.
- Ошибка на втором pack/member/body/dependency/world write откатывает первый.
- Внешняя UOW: entity write → library apply → ошибка entity даёт полный rollback;
  executor не делает отдельного COMMIT/BEGIN.
- Конкуренция: две задачи на общей connection и две Database connections
  к одному файлу; подтверждение старого состояния не перезаписывает новое.
- Занятый new UID в чужом scope и body без membership дают конфликт без upsert.
- Copy оставляет source неизменным; replace сохраняет owner/UID/provenance;
  pins/references удерживают members по готовому plan.
- Несколько local-key совпадений требуют точной цели; FS single-member
  import не удаляет остальных; multi-pack batch remap сохраняет связи.
- Canonical повторный attach не меняет существующие тела/состав и сохраняет
  атомарность; пользователь не получает canonical write-mode.
- Аудит callers: user writes не используют прежние upsert/import loops;
  HTTP negotiation сериализуется на шаге L-5 без собственной policy.

Основной новый набор: `test_library_write_service.py`; регрессии L-1…L-3,
schema, 4b/4c, lifecycle, FS import, canonical и scoped write.

В ходе этого анализа тесты не запускались; результаты старых проверок
в основном плане не считаются новой верификацией. Backend не запускался,
код и общий граф не изменялись, commits не создавались.
