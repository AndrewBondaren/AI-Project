# Pack F3 — проверка закрытия допуска

8 ноября 2026. Реализация §§15.99–15.103. DAG и Pack используют разные файлы SQLite. Тесты публикуют manifest V2, root и shard через SQLite-адаптеры и файловый BLOB backend. Точкой порядка служит commit в Pack.

## Evidence по карте §15.102

| Сценарий | Наблюдаемый результат | Проверка |
|---|---|---|
| Ответ на close потерян | После commit тест закрывает Pack-соединение и создаёт адаптер заново. Повтор возвращает исходную тройку, в таблице одна запись CLOSED, у manifest сохранился pin holder, у root и shard сохранился holder этого manifest. | [test_lost_reply](../../backend/tests/spatial_pack/test_execution_pins.py#L84) |
| Чужая identity или revision | До и после CLOSED проверены чужой UUID, отсутствующий execution и другая revision. Сохраняется прежнее удержание. Два независимых DAG store используют одно имя execution. Закрытие второго до появления pins запрещает его первый acquire и оставляет первый execution доступным. Недоступность DAG при первом close даёт typed unavailable. | [test_conflicts](../../backend/tests/spatial_pack/test_execution_pins.py#L122), [два namespace](../../backend/tests/spatial_pack/test_execution_pins.py#L98) |
| CLOSED первым | Worker уже получил ref и разрешил его через manifest и root. Барьер останавливает его перед guard целевого shard. После commit CLOSED и снятия барьера worker получает PackClosed. За этот интервал вызовов Path.open ровно 0. | [test_stale_worker](../../backend/tests/spatial_pack/test_execution_pins.py#L139) |
| Физический open первым | Барьер стоит внутри открытого файла root. На втором Pack-соединении SQLite trace фиксирует попытку BEGIN IMMEDIATE. close ждёт. В момент INSERT CLOSED stream уже закрыт. Проверены успешное завершение и отмена чтения с drain. Следующее чтение shard отклонено, holds сохранились. | [test_stream_first и вариант с отменой](../../backend/tests/spatial_pack/test_execution_pins.py#L163) |
| Crash после CLOSED, до finalized | Тест моделирует потерю состояния процесса закрытием Pack и созданием новых соединений и адаптеров после commit. До остановки pins двух invocation читают один shard через разные manifest A/B. До reopen отключены DAG get_store_id и load. Новый адаптер восстанавливает namespace из Pack, а повтор close возвращает прежний receipt. Оба acquire и read отклонены. Проверены точные pin holds A/B и независимые удержания общего shard обоими manifest. | [test_crash_and_shared_shard](../../backend/tests/spatial_pack/test_execution_pins.py#L218) |

## Хранение и состав проверки

[Начальная схема 0001](../../backend/app/db/migrations/0001_initial.sql) создаёт таблицы CLOSED и OPEN pins вместе с журналом держателей. Pin binding ссылается на точную пару world/publication и локальный PK manifest. Составной FK журнала связывает pin с тем же manifest. На свежей базе отдельно проверены цепочка acquire/release для operation holder, пустой pin_id у обеих записей и PRAGMA foreign_key_check. [Тест начальной схемы](../../backend/tests/spatial_pack/test_execution_pins.py#L292)

[ExecutionPins.bind](../../backend/app/db/repositories/sqlite/worldPack/executionPins.py) привязывает экземпляр к UUID доверенного ExecutionStore и зарегистрированному manifest contract, версии и бюджету из композиции Pack. При первом acquire проверяется существование execution. При первом close адаптер сверяет типизированную команду с durable stop intent и revision. Для повторного close достаточно привязанного namespace и сохранённой тройки.

При чтении shard адаптер сначала читает pinned manifest и проверяет descriptor в root. Каждый физический read получает отдельный допуск и удерживает Pack writer до возврата backend. Такая проверка closure требует повторного чтения manifest и root для каждого запроса shard. В репозитории существующие прямые вызовы raw OpenWaterBlobReader относятся к тестовым пробам. Execution-bound входы F3 — ExecutionPins.read_root и read_shard.

Команды из backend на Windows:

```text
python -m unittest -v tests.spatial_pack.test_execution_pins
python -m unittest -v tests.spatial_pack.test_execution_pins tests.spatial_pack.test_guarded_blob_read tests.spatial_pack.test_pin_worker_drain tests.spatial_pack.test_pin_binding_replay tests.spatial_pack.test_manifest_pin_retention tests.snapshotCore.contracts.test_codec
```

После переноса схемы в 0001 расширенный прогон на заново созданных временных SQLite-базах завершился успешно. Прошли 35 из 35 тестов за 119,524 с, включая все 8 тестов модуля F3.

Граница отчёта — Pack CLOSED до DAG finalized и release. Сценарий восстановления воспроизводит потерю процесса после подтверждённого SQLite commit; отдельная инъекция сбоя питания не выполнялась.

## Независимая приёмка 2026-11-08 — REVISE

Проверено рабочее дерево с новыми файлами адаптера и тестов. База сравнения до F3 — `0d4260b3`. Во время проверки изменения F3 вошли в `97544aa7`. Обе приведённые выше команды выполнены из backend на Windows. Модуль F3 прошёл 8/8 за 70,017 с, расширенный прогон — 35/35 за 132,344 с.

**Что подтверждено.** При первом acquire адаптер проверяет UUID привязанного store и существование execution. Один Pack writer выбирает публикацию, разрешает manifest по зарегистрированному формату и hash, проверяет seal, мир и версию, вставляет OPEN binding и добавляет PinHolder в общий журнал. Повтор acquire после смены head возвращает прежний manifest. Первый close сверяет committed intent и revision через DAG, затем под Pack writer повторно читает CLOSED и при необходимости вставляет запись. Receipt выходит из метода после commit. Другой store с тем же execution_id сохраняет отдельное право допуска.

- В дополнительной пробе для каждого из root и shard подготовлен отдельный BLOB соответствующего формата и установлен точный ArtifactRetentionHolder закреплённого manifest. Descriptor отсутствовал в его closure. Оба bound read дали PackIdentityConflict, счётчик Path.open для целевого hash равен нулю. По коду read_root сверяет полный ref с manifest, read_shard — с descriptor в root этого manifest. Перед каждым целевым IO guard заново проверяет CLOSED, binding, pin hold, seal и дочерний hold.
- После CLOSED старый worker перед guard shard получил отказ без open. В обратном порядке второе Pack-соединение дошло до BEGIN IMMEDIATE и дождалось закрытия stream root, включая отмену. Дополнительный барьер в read_verified shard задержал возврат backend **после** фактического чтения и закрытия файла. Пока барьер удерживался, независимый SQL reader видел 0 записей CLOSED. После снятия барьера чтение и close завершились.
- В отдельной пробе обёртка над driver.commit сначала выполнила настоящий SQLite COMMIT, затем выбросила OSError. Вызывающий получил UnknownCommitOutcome. После reopen с доступной identity и отключённым DAG load повтор вернул исходную тройку, read_root получил PackClosed, pin hold и обе дочерние связи сохранились. Обычный holders.release для PinHolder отклонён с ValueError. Release F5 и DAG finalized за границей проверки.

### Замечания

1. **Холодное восстановление зависит от доступности DAG уже при bind.** Воспроизведение на fixture ExecutionPinTests — выполнить stop и успешный close, перед `await self.reopen()` подменить `self.dag.get_store_id` на `OSError("offline")`, затем попытаться повторить close. Для локального восстановления по §15.102 ожидается возможность подтвердить сохранённую тройку для ранее доверенно привязанного namespace при недоступном DAG. Фактически `ExecutionPins.bind` падает на строке 61 до чтения Pack. Запись и holds сохраняются, но вызывающий не получает receipt. Штатный test_crash_and_shared_shard выключает только load и только после успешного повторного bind. Для устранения зависимости потребуется сохранить доверие к namespace при восстановлении без принятия UUID из самой команды.
2. **Регрессия статической типизации F3.** Из backend выполнить команду ниже на рабочем дереве, затем тем же Pyright и Python на дереве `0d4260b3`, опустив отсутствовавший там executionPins.py. Ожидалось 0 новых ошибок. На базе 0, сейчас 50. Из них 49 reportAttributeAccessIssue в executionPins.py, начиная со строки 60 (атрибуты экземпляра создаются внутри classmethod bind). Ещё 1 reportArgumentType в openWaterBlobReader.py:84 — в is_held передаётся holder, тип которого допускает None. Остальные четыре файла прошли без диагностик.

```powershell
..\node_modules\.bin\pyright.cmd --pythonpath (Get-Command python).Source app/application/artifacts/encoding/coreManifest.py app/application/worldData/pack/spatial/openWaterBlobReader.py app/dataModel/artifacts/lifecycle/holders.py app/db/models/artifacts/holderRows.py app/db/repositories/sqlite/artifacts/holderStore.py app/db/repositories/sqlite/worldPack/executionPins.py
```

## Исправление замечаний независимой приёмки

Холодный reopen воспроизведён на test_crash_and_shared_shard. До исправления отключение get_store_id перед reopen() завершало bind с OSError до восстановления receipt.

Первый успешный online bind записывает в pack_execution_namespaces стабильный ключ подключения из композиции и UUID, полученный от доверенного DAG store. Таблица входит в 0001_initial.sql. Для одного подключения действует ключ «default». При нескольких DAG store композиция назначает каждому собственный ключ. Попытка зарегистрировать другой UUID под занятым ключом отклоняется. При отказе транспорта повторный bind берёт UUID из этой таблицы. Адаптер в таком режиме может подтвердить существующий CLOSED. Для новой операции, требующей полномочий DAG, после восстановления связи выполняется новый bind.

В тесте отказ get_store_id и load действует до создания новых Pack-соединений и до конца replay. Проверены совпадение receipt, отказ для неизвестного ключа подключения, чужого UUID, другой revision и execution без CLOSED. Число вызовов load — 0. У обоих manifest сохранены pin holds и независимые связи с общим shard.

Инициализация полей ExecutionPins перенесена в типизированный конструктор. Вызов is_held получает проверенный holder. Команда Pyright из независимой приёмки на тех же шести production-файлах вернула 0 errors, 0 warnings, 0 informations.
Расширенный прогон на свежих базах по команде выше — 35/35 OK за 113,422 с.

## Повторная независимая приёмка 2026-11-08 — REVISE

Проверено рабочее дерево поверх `aecef2af`, включая незакоммиченные правки. Обе команды unittest из backend прошли: 8/8 за 86,009 с и 35/35 за 144,764 с. Предыдущее замечание о типизации закрыто. Повтор той же команды Pyright дал 0 ошибок и 0 предупреждений на шести production-файлах, на пяти существовавших в базе `0d4260b3` файлах также 0/0.

На пути через bind два соединения подтвердили порядок физического чтения и CLOSED, включая отмену с drain. Проверки принадлежности root/shard закреплённому manifest сохранились, holder проверяется под guard до dispatch, await backend остаётся внутри guard. Отдельная проба выполнила настоящий driver.commit и сразу выбросила OSError до возврата receipt. После UnknownCommitOutcome и reopen с OperationalError на get_store_id повтор close вернул исходную тройку без DAG load, read_root получил PackClosed, manifest pin и оба дочерних hold сохранились.

1. **P1. Публичный конструктор допускает OPEN pin под неподтверждённым UUID.** На fixture ExecutionPinTests создать `fake = uuid4()` и `direct = ExecutionPins(fake, self.dag, self.bundle[2], self.fixture.holders, self.fixture.service._registry, self.fixture.backend.contract, 1, 100000)`. Выполнить `p = replace(self.intent, store_id=fake, pin_id="foreign-pin")`, `await direct.acquire(p)`, затем `await self.pins.close(await self.stop())` и `await direct.read_root(p, self.root)`. Ожидалось отклонение несовместимой пары UUID/store до создания pin. Фактически acquire вернул manifest, а после подтверждённого CLOSED чтение вернуло bytes root. Конструктор принимает UUID отдельно от источника полномочий. Проверка существования execution использует настоящий DAG, а запись binding и поиск CLOSED используют переданный fake UUID. Для воспроизведения достаточно публичного конструктора и методов адаптера, без изменения SQL или полей адаптера. Штатная фабрика bind отвергает конфликт UUID.
2. **P2. Холодный replay с реально закрытым соединением SQLite по-прежнему недоступен.** На той же fixture выполнить `cmd = await self.stop()`, `await self.pins.close(cmd)`, `self.dag.db.close()`, затем `await self.reopen()` и повторить close. Ожидалось восстановление receipt по ранее зарегистрированному ключу подключения с сохранением holds. Фактически reopen завершился до replay с `sqlite3.ProgrammingError: Cannot operate on a closed database.` Ошибка возникает при чтении identity. Ветка offline в bind обрабатывает OSError и OperationalError, а закрытое соединение SQLite выдаёт другой тип исключения. Сценарий с подставленным OSError теперь проходит.

## Исправления P1 и P2 после повторной приёмки

Обе регрессии воспроизведены до изменения адаптера. В проверке P1 прямой вызов конструктора принял произвольный UUID вместе с настоящим store. В P2 реальный вызов SQLite connection.close() перед холодным reopen привёл к ProgrammingError при чтении UUID.

* **P1.** Конструктор принимает зависимости Pack. Единственное место установки namespace — bind, после подтверждения регистрации или чтения её из Pack при восстановлении. Прямая передача UUID и store конструктору отклоняется. Для созданного напрямую экземпляра acquire возвращает PackIdentityConflict. Проверка обнаружила 0 строк pins под чужим UUID и отсутствие соответствующего PinHolder. После CLOSED штатный адаптер отклонил чтение того же root с чужим pin intent и с прежним pin intent владельца, число вызовов Path.open составило 0. [Тест P1](../../backend/tests/spatial_pack/test_execution_pins.py#L252)
* **P2.** После commit CLOSED тест закрывает настоящее соединение DAG, переоткрывает Pack и получает тот же receipt. DAG load вызван 0 раз, read_root получает PackClosed, manifest pin и оба дочерних hold сохраняются. При get_store_id адаптер распознаёт ошибку закрытого соединения по типу и сообщению CPython sqlite3. Проба с другой ProgrammingError подтверждает её распространение вызывающему. [Тест P2](../../backend/tests/spatial_pack/test_execution_pins.py#L275)

Расширенный прогон на свежих SQLite-базах прошёл 37/37 за 132,747 с, включая 10 тестов F3. Pyright на шести production-файлах из команды выше — 0 ошибок и 0 предупреждений.

## Независимая перепроверка P1 и P2, 2026-11-08 — ACCEPT

Принято текущее рабочее дерево поверх `aecef2af` в границах Pack F3 (§§15.99–15.103). Обе команды из раздела «Хранение и состав проверки» повторены из backend. Модуль F3 прошёл 10/10 за 92,995 с, расширенный прогон — 37/37 за 151,412 с. Pyright на шести production-файлах и на пяти существовавших до F3 файлах из `0d4260b3` выдал по 0 ошибок и предупреждений.

- **P1 закрыто.** Прежний вызов конструктора с отдельным UUID и DAG store получил TypeError. При вызове acquire через непривязанный адаптер получен PackIdentityConflict. Под чужим UUID создано 0 pins, соответствующий PinHolder отсутствует. После CLOSED старый и чужой intent отклонены до Path.open.
- **P2 закрыто.** После закрытия настоящего SQLite-соединения DAG холодный bind восстановил ранее зарегистрированный namespace из Pack. Повтор close вернул исходную тройку без DAG load. Другая ProgrammingError из get_store_id сохранила свой тип и дошла до вызывающего.
- **Независимая проба чтения.** Для посторонних BLOB формата root и shard установлен точный holder закреплённого manifest. Оба запроса получили PackIdentityConflict до открытия целевого файла. Для разрешённого shard барьер задержал возврат read_verified после закрытия файла. Второе Pack-соединение дошло до BEGIN IMMEDIATE, а независимый SQL reader в этот момент видел 0 строк CLOSED. После снятия барьера чтение вернуло bytes и close смог выполнить commit.
- **Независимая проба восстановления.** Сразу после настоящего SQLite COMMIT драйвер выбросил OSError, вызывающий получил UnknownCommitOutcome. Затем закрыто соединение DAG и заново открыт Pack. Повтор close вернул ожидаемые store_id, execution_id и stop_revision. Старый read_shard получил PackClosed до открытия файла. Обычный release для PinHolder отклонён, manifest pin и дочерние holds root/shard сохранились.

Открытых замечаний в границах F3 нет. Проверка заканчивается на durable CLOSED и удержании до отдельного release.
