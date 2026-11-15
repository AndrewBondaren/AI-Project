# Pack: четыре принципа массовых writes и проверка решений

2026-11-15. Зафиксировано по прямому поручению пользователя после согласования batch-направления и поиска первичных источников. Это требования к конкретизации массовой операции, не приёмка её отсутствующей реализации. Runtime-код не меняется.

## 1. Одна сборка immutable state на пакет

Один исходный state, tuple однотипных изменений, один новый итоговый state. Полное admission базы — до применения пакета, проверка результата — после сборки. Нельзя реализовать batch циклом публичных одиночных writes, каждый из которых создаёт и валидирует целый state. Конструкторы request/state и вложенные validators тоже входят в измеряемый маршрут: одна строка вызова admission не доказывает один обход.

Исходные state и вложения неизменны; при любой ошибке пакет не выдаёт частичный результат. Независимые ошибки собираются с исходными индексами элементов, duplicate addresses отклоняются без last-wins. Single/batch при допустимых unique inputs должны использовать общую семантику преобразования, без двух расходящихся алгоритмов. Конкретный способ общего объявления ещё проверяется при приёмке batch-контракта.

Основание: [Immer: Pull produce as far up as possible](https://immerjs.github.io/immer/performance/#pull-produce-as-far-up-as-possible) — объединять изменения в одной операции формирования нового состояния. Это аналогия подхода, не предложение включить JS-библиотеку в Pack и не перенос её benchmark-чисел в Python.

## 2. Immutable снаружи; локальные изменяемые структуры внутри

Локальные dict/list/set допустимы как детали одного pure метода: индекс address→position строится один раз, изменения применяются к новым локальным контейнерам, затем собираются immutable tuples/POJO. Исходные контейнеры и вложенные records не мутируются. Рабочие контейнеры не возвращаются, не сохраняются в service/cache/session, не передаются caller и не используются параллельно другими вызовами. Локальная мутация не превращает функцию в оркестратор.

Это не публичный mutable builder, callback API или hidden session store. Запрет таких механизмов в write-плане не запрещает локальный индекс. Metadata группируется по затронутым owning адресам; один tile не сканируется целиком повторно для каждого его chunk. Порядок результата и существующие preserve/None/status/provenance semantics сохраняются, не выводятся из порядка произвольного dict.

Основание: [Clojure Transients](https://clojure.org/reference/transients) — ограниченная локальная изменяемость при сохранении immutable исходного и конечного значений. Python dict/list не получают автоматически гарантий Clojure transients: отсутствие утечек/aliasing доказывается Pack-тестами.

## 3. Переиспользовать валидаторы, не кешировать доверие к значениям

Повторно использовать TypeAdapter для стабильных owning annotations, вместо построения нового validator/serializer на каждом вызове. Cache key должен различать exact owner/field/type specialization; кеш не содержит state, пользовательские values или результат «уже валиден». Не принимать forged objects по object identity и не отключать strict nested revalidation ради скорости. Не вводить Any/model_construct как обход admission и не заменять агрегацию независимых ошибок fail-fast режимом.

Переиспользование adapters уменьшает постоянные затраты; полное копирование и обход state от этого не перестают быть линейными на каждый вызов. Изменения количества проверок требуют отдельного trace всех структурных/семантических invariants и negative tests; предполагаемая избыточность проверки не доказывает её ненужность.

Основание: [Pydantic: TypeAdapter instantiated once](https://docs.pydantic.dev/latest/concepts/performance/#typeadapter-instantiated-once). Применяем только совместимые с проектными гарантиями рекомендации.

## 4. Persistent collections — запасной вариант

Сначала batch, локальные индексы, однократная сборка и reuse adapters; затем измерение полного пути. Не заменять публичные tuples и owning POJO на HAMT/новую библиотеку без доказанного остаточного bottleneck и отдельного решения. Structural sharing сам по себе не устраняет full validation или serialization всего state.

Основание: [MagicStack immutables](https://github.com/MagicStack/immutables) описывает HAMT map с O(log N) get/set. Map не сохраняет требуемую Pack последовательность автоматически; миграция затронет canonical encoding, типы и границу доверия. Эта зависимость не выбрана.

## Проверка текущих решений на соответствие

| Решение / реализация | Результат проверки | Что требуется |
|---|---|---|
| Однотипный batch; один state, atomic output | Соответствует принципу 1 на уровне согласованного направления | Named inputs/errors и реальный алгоритм пока не предъявлены; это не implementation PASS |
| Duplicate address reject и агрегация ошибок | Соответствует 1/3 | Проверить несколько независимых ошибок разных items и сохранение исходного state при отказе |
| Общие immutable parts/assembly/provenance | Совместимо с 1/2 | Не копировать state в каждый batch item; не мутировать разделяемые nested records |
| Запрет публичного mutable builder/session | Совместим с 2 | Не трактовать как запрет локальных dict/list; их lifetime ограничен одним вызовом |
| Текущие write_coarse_climate/replace_locations_index | Не соответствуют массовому пути принципа 1 при N single calls: полный scan/copy/validation на каждый вызов | Существующие single методы не объявляются функционально неверными; не использовать их циклом как batch implementation |
| errors.valid_preparation_field / valid_preparation_items | Принцип 3 пока не выполнен: TypeAdapter создаётся при вызове | Отдельная локальная оптимизация с exact cache key и negative tests; не доказательство достаточной скорости batch |
| preparation/nestedAdmission.py::_field_adapter | Уже пример reuse через lru_cache(model,name) | При переносе проверить exact annotation/owner semantics, не копировать кеш blindly |
| Chunk refine_role=None, provisional status, metadata invalidation | Семантика уже задана; batch-выдержка ещё НЕ ДОКАЗАНА | Сгруппировать работу по tile, доказать итоговую эквивалентность unique single writes; не пересчитывать все chunks tile K раз |
| Source proofs и inherited/new admission | Нельзя ослаблять ради batch | Batch не обрезает proof, не создаёт его, не вызывает Source public API; отсутствие inherited binding не скрывается batch интерфейсом |
| DAG определяет порядок/границы batches | Соответствует 1/2 и существующей ответственности | Много одноэлементных пакетов сохраняют повторный обход; transport и реальные границы проверяются на последнем DAG этапе |
| Persistent collections не вводятся | Соответствует 4 | Возвращаться только по измеренному результату и отдельному решению |
| Ранее заявленное O(N + K) | Недостаточно без размера nested данных | Формулировка уточнена ниже; не обещать линейность по числу parts при растущем proof |
| Замеры 1000/4000/16000 | Подтверждают проблему старого пути; НЕ проверяют batch | Новые batch additions/replacements, heavy provenance, counters/peak memory обязательны перед массовой приёмкой |

Проверенные code paths: backend/app/application/worldData/pack/preparation/packPreparationService.py; packPreparationValidator.py; errors.py; backend/app/dataModel/worldPack/preparation/nestedAdmission.py. Сведения о runtime — [отдельный отчёт](pack-write-scaling-measurement-2026-11-15.md); новых замеров в этом документальном проходе нет.

## Уточнённый критерий стоимости

N и K сами по себе недостаточны. Оценивать полный объём обхода базы B, входных изменений U и результата R, включая metadata/provenance, а также суммарный размер ключей/хеширования. Цель — ограниченное число полных проходов, стоимость порядка O(B + U + R) при ожидаемой константной цене indexed lookup и фиксированной сложности owning leaf checks. Для сопоставимой ограниченной формы records это сокращается до O(N + K).

Если нужны canonical sorting, разрешение графовых зависимостей или другие нелинейные owning проверки, их стоимость предъявляется отдельно, а не скрывается обещанием O(N + K). Фиксированный маленький batch не даёт общей линейности всего workflow: m batches с повторным обходом всей базы могут суммарно стоить O(mN) и больше по растущему составу. Размер пакета не назначается произвольным числом; выбирается по семантике операции и измеренным времени/памяти. Нет обещания O(1) памяти или времени.

Итог: согласованное направление выдерживает четыре принципа. Текущая реализация single-write цепочки принципу массовой сборки не соответствует; reuse adapters и metadata batch trace ещё предстоят. Следующий результат — конкретный chunk batch contract и его приёмка, затем реализация и повторные измерения. Код, внешние Snapshot/Source/DAG контракты этим документом не меняются.
