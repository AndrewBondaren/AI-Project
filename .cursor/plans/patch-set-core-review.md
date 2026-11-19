# Независимое ревью ядра PatchSet — PS-I1 → PS-I2

Дата: 2026-11-19.

Объект: реализация `.cursor/plans/patch-set-core-implementation.md`.

**Актуальный итог — принято, 2026-11-19.** Пользователь передал результат: «Новых существенных находок P1/P2/P3 не обнаружено. Прежний P2 закрыт. Ядро PS-I1 → PS-I2 принимается в согласованном scope».

Источник итоговой приёмки — сообщение пользователя; новых прогонов тестов этой записью не заявляется. Приёмка ограничена общим ядром PatchSet и не закрывает production producers, capture/identity/union, DAG wiring или реализацию Snapshot admission.

Ниже сохранена история первоначального частичного ревью и исправления. Формулировки «не принимается» и OPEN в ней относятся к состоянию до итоговой приёмки и не являются текущим отказом в приёмке ядра.

## Находки

### P2 — construction binding допускает секцию с ослабленными structural constraints

Место: `backend/app/application/patch/assembly/patchSetAssembler.py:44`.

Проверка модели секции сверяет аннотации `header` и `patches`, но не сохраняет ограничение `min_length=1`, объявленное в `DomainSection`.

Воспроизведение из каталога `backend`:

```python
from app.application.patch.assembly.patchSetAssembler import PatchSetAssembler
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection
from tests.snapshotCore.support.fakeSection import HeaderOnlyPatch
from tests.snapshotCore.contracts.test_patch_invariants import section, values

class EmptySection(DomainSection[HeaderOnlyPatch]):
    patches: tuple[HeaderOnlyPatch, ...]

class Input(PatchSetAssemblyInput[EmptySection]):
    pass

class Result(PatchSet[EmptySection]):
    pass

s = EmptySection(header=section('x').header, patches=())
a = PatchSetAssembler(Input, Result)
r = a.assemble(Input(**values((s,))))
print(type(r).__name__, r.sections[0].patches)
```

Фактический вывод: `Result ()`. Binding и assemble успешно принимают пустую секцию.

Нарушенный контракт: архитектура §3.2 и план реализации §2 требуют сохранения structural/nested constraints native specialization; секция содержит непустой tuple patches. Повторная validation использует уже ослабленную схему и дефект не предотвращает.

Последствие: успешная сборка подтверждает структурно недопустимую секцию.

Минимальное исправление: при construction admission проверять сохранение обязательных ограничений inherited section fields, включая metadata `patches`. Добавить негативный тест специализации, удаляющей `min_length`. Изменение внешнего контракта для этого не требуется.

Текущие тесты этот случай не обнаруживают.

## Критерии приёмки

| Критерий | Результат и основание |
|---|---|
| Три запрета DAG внутри просмотренной цепочки assemble | PASS: нет выбора внешних стадий, скрытого запуска pipeline или foreign application service calls |
| Ответственность всех новых и затронутых классов | OPEN: основная цепочка просмотрена, полный индивидуальный аудит всех соседних классов не завершён |
| Public/internal граница | PASS для просмотренной цепочки: owning input/result, внутренние validator/checker, без registry/storage в запросе |
| Нормативный порядок операции | PASS: exact input → revalidation → core → prepared-order → diagnostics → refusal/result |
| Историческое выполнение PS-I1 перед PS-I2 | OPEN: по конечному коду последовательность выполнения работ не доказать |
| CRUD данных и настроек | PASS: принятого assemble достаточно; дополнительные CRUD не требуются |
| Междоменные зависимости и координация | OPEN для полной приёмки; новых контрактных предложений и изменений не внесено |
| POJO: единый родитель и два ребёнка | PASS: девять полей объявлены в PatchSetData, дети их наследуют; пометки об авторизации присутствуют |
| Сохранение constraints concrete моделей | FAIL: воспроизведён описанный дефект |
| Единый источник predicates | PASS: core/prepared проверки в PatchSetInvariants; presentation преобразует facts |
| Ordinal независимо от identity | PASS: отдельные проверки, mismatch не подавляет duplicate ordinal |
| Prepared-order и неоднозначные targets | PASS: отсутствующий/последующий target диагностируется; неоднозначный target не получает выдуманный порядок |
| Exact root и structural exceptions/refusal | PASS для проверенных случаев: неверный request class — TypeError, повреждённый exact instance — ValidationError |
| Девять details, индексы и checked paths | PASS по просмотренному коду и контрактным тестам |
| Canonical identities/bytes/hash и исторические codec cases | OPEN: текущие тесты проходят, но независимое сравнение с исходным diff не выполнено |
| Достаточность тестов | FAIL: отсутствует негативный случай ослабления section constraints |

## Фактические проверки

Команды запускались из `backend` через `.venv/Scripts/python.exe -B`.

- `-m unittest discover -s tests/snapshotCore/contracts -t .` — 91 тест, OK, включая positive/negative Pyright gate.
- `-m unittest discover -s tests/snapshotCore -t .` — 207 тестов, 100 ошибок. В показанных traceback причина — `PermissionError [WinError 5]` при создании временных SQLite-каталогов в `backend/tests/.tmp_snapshot_core`. Это не доказательство регрессии кода; успешной полной регрессии в этом ревью нет.
- Дополнительный probe ослабленной section schema — дефект подтверждён, результат `Result ()`.
- Дополнительный probe `PatchSetAssembler(PatchSetAssemblyInput, PatchSet)` — `ModelIdentityError`, не TypeError. Отдельной находкой не оформлен: точное требование TypeError для этой разновидности неверного construction binding не установлено; контракт TypeError для неверного request object этим не опровергается.

## Ограничения и границы вывода

Git возвращал `fatal: this operation must be run in a work tree`, включая попытки с явными путями и настройками рабочего дерева. Поэтому чужие изменения не удалось надёжно отделить через diff, а неизменность golden fixtures относительно базы не подтверждена.

Прежние PASS и §6 плана доказательством не использовались. Полное независимое ревью всех перечисленных пользователем источников и классов не завершено; локальные PASS в таблице не означают общей приёмки. Часть чтений источников вернулась с усечённым выводом, поэтому полнота проверки нормативных документов также не заявляется.

При проведении ревью код и документы не менялись, сервер не запускался. Этот файл создан позднее по отдельному поручению пользователя сохранить результат.

Production producers, capture/identity, production union, Snapshot admission implementation и DAG wiring не считаются дефектами PS-I1/PS-I2. Constructor/decode обязан обеспечивать check_core; дополнительная prepared-order гарантия относится к успешному assemble. Реализация вызова общего checker в Snapshot остаётся ответственностью Snapshot.

**Решение: не принимать ядро до устранения P2 и закрытия обязательных OPEN проверок.**

## Исправление владельцем PatchSet — 2026-11-19

P2 исправлен в PatchSetAssembler construction admission: обязательность inherited section fields и их metadata проверяются по owning DomainSection. Удаление MinLen или ослабление его minimum отклоняется с TypeError; усиление minimum допускается. Константа минимального размера не копируется из модели в application.

Добавлен test_construction_retains_section_minimum в tests/snapshotCore/contracts/test_patch_assembly.py: снятый minimum, min_length=0 и допустимый min_length=2. До исправления первые два case воспроизводимо падали (TypeError не возникал), после исправления проходят. Контрактный discover — 92 tests, OK, включая Pyright. Diff исправления просмотрен.

Это результат исправления и локальной проверки владельцем, не завершение независимого ревью. Остальные OPEN и исходный объём независимой проверки сохранены; полная регрессия в этом проходе не повторялась.
