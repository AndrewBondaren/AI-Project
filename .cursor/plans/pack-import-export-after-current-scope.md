# Pack import/export — отдельный этап после текущего скоупа

2026-11-19. Решение пользователя: отложить import/export, зафиксировать границу и создать отдельный план после текущего скоупа. Статус: DEFERRED; это план последующего проектирования и перехода, не готовый implementation contract и не разрешение кода сейчас.

## Граница с текущей работой

Текущий скоуп — общая карта междоменных процессов, основные публичные Pack/Artifacts-контракты и согласование владения версиями. Он продолжается без проектирования нового архивного формата. Целевой указатель формата manifest — format_key + ArtifactRef.format_version; конкретные значения версии не назначаются.

Import/export — отложенная зависимость полного cutover, а не блокер всех текущих контрактов. До отдельного решения нельзя удалять поля/маршруты так, чтобы сломать действующий импорт, или объявлять полный переход завершённым. Сохранение текущего runtime на время отсрочки не разрешает новый legacy adapter, fallback decoder или параллельный целевой формат.

Начать этот этап после завершения текущего контрактного скоупа и явного перехода пользователя к import/export. Автоматического запуска нет. Если конкретная текущая правка затрагивает работающий import/export, отложить зависимую правку либо отдельно согласовать scope; независимую работу продолжать.

## Исходный пробел

Первичный trace: application/worldData/pack/import_/packImportService.py принимает ZIP с manifest.json без обязательного ArtifactRef. Поэтому удаление внутреннего wire marker не закрывает доставку owning format context. Existing descriptor не является authority; его соответствие exact bytes необходимо проверить. Актуальность trace повторно проверить при старте этапа.

## Последовательность будущего этапа

1. **Inventory — Pack.** Установить все import/export/worldBundle/API/fixtures и внешние archive consumers, способы передачи manifest/parts, живые refs и удерживаемые данные. Результат: полный producer→transport→consumer roster, без предположения о совместимости по наличию manifest.json.
2. **Контракт — Pack с координатором DAG и Artifacts.** Предъявить варианты: existing ArtifactRef + exact bytes либо иной явно согласованный архивный контракт. Выбрать один с пользователем. Зафиксировать concrete public class/method/Input/Output/Error, format context, budgets, authority, validation, отсутствие schema guessing и дублирующей версии. Имена методов и POJO сейчас не назначаются.
3. **Междоменные гарантии — Artifacts/Publication/Snapshot/Cache по затронутому маршруту.** Проверить descriptor/hash/size/schema, protection/retention, identity/replay незавершённых операций, cache key/admission и cancellation/unknown. Импорт не разрешает публикацию в обход DAG. Бинарные payload headers рассматриваются отдельно; версия операции DAG не задаёт persisted format.
4. **Синхронизация и приёмка.** Согласовать окончательную manifest/archive schema, конкретный disposition удаляемых полей и старых архивов/refs. Обновить owning ТЗ/планы по разрешению пользователя; проверить все обязательные критерии. До закрытия exact contracts реализация не начинается.
5. **Отдельная реализация по implement-plan.** Готовый целевой путь → переход callers/данных с сохранением требуемой доступности/retention → удаление legacy → отдельный аудит версионных обозначений. Не менять bytes/descriptor существующего артефакта на месте и не подменять replay-payload той же операции.

## Критерии завершения этапа

- Каждый импорт имеет однозначный проверяемый format context, без guessing/fallback и неявного дубля pack_version.
- Export→import сохраняет согласованные exact bytes/identity; несовпадение descriptor, размера, hash или schema отвергается owning контрактом.
- Отсутствующий/неподдерживаемый формат, budgets и ошибки отличаются от authority/infra отказов по принятому mapping.
- Проверены retained refs, cache identity и replay; старые архивы имеют явный согласованный disposition, не молчаливую потерю доступа.
- Удаление pack_version/codec_version/payload_format выполнено только в принятом объёме после перехода потребителей. Binary headers не удаляются автоматически.
- Представлены tests/typing/caller audit и отдельная пользовательская приёмка полного cutover. Наличие этого плана не закрывает этап.

Источники: [владение версиями](pack-format-version-ownership.md), [PA-1](pack-artifacts-boundary-trace.md), [общая карта](dag-multidomain-patch-publication-draft.md), [Pack](world-pack-v2-single-manifest-contract.md).
