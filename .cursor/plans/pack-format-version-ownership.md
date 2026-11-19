# Pack: владение версиями и единственный формат

2026-11-19. Пользователь согласился с рекомендацией разделить версию операции и формат сохранённых данных. **Принято направление; конкретное удаление полей и междоменный mapping требуют сверки координатора и завершения проверки consumers. Код и данные не изменяются этим документом.**

## Целевая ответственность

**Уточнение скоупа пользователем 2026-11-19:** import/export отложен [отдельным планом после текущего скоупа](pack-import-export-after-current-scope.md). Он не блокирует согласование владения версиями и основных Pack/Artifacts-контрактов. Сейчас новый архивный формат не проектируется. Удаление полей/маршрутов, затрагивающее действующий импорт, и полная приёмка cutover остаются зависимыми от этого последующего этапа; работающий импорт нельзя сломать под видом отсрочки. Это уточнение ограничивает текущую работу в шагах ниже, не отменяя конечные критерии перехода.

- DAG владеет версиями публичных контрактов операций и совместимостью цепочки.
- Owning домен определяет схему своих сохранённых данных; Artifacts использует зарегистрированный format binding и ArtifactRef.format_version. Версия операции DAG не вычисляет версию сохранённого artifact.
- Для manifest целевой единственный указатель версии формата — ArtifactRef.format_version вместе с format_key. Это не разрешение на произвольный bump: точное значение и schema registration согласуются с owning контрактом.
- Pack имеет одну действующую реализацию формата без legacy decoder, dispatch и параллельных версий после полного cutover.
- Предлагается удалить pack_version внутри manifest как дублирующий указатель после проверки descriptor transport в import/export. codec_version/payload_format внутри manifest также подлежат удалению при подтверждении, что смысл полностью задаётся binding и consumers не требуют отдельных полей.
- Версии бинарных заголовков отдельных payload рассматриваются отдельно: это не автоматически дубли manifest и не предмет массового удаления.

## Приоритет над прежними формулировками

Прежние записи «обязательная wire 3.0.0 / storage 2, pack_version и codec_version/payload_format сохраняются, выбор закрыт» описывают предыдущее решение. После нового поручения они не являются основанием обязать конечную схему сохранять дублирующие поля или выполнить изолированный bump. До завершения согласования сохраняется текущий runtime; это не разрешение удалить поля заранее. Число действующего storage binding, окончательный состав manifest и транспорт descriptor проходят отдельную конкретизацию; новая версия здесь не назначается.

## Первичная трассировка consumers

Пути относительно backend/app; статический поиск 2026-11-19, не runtime evidence и не полный аудит внешних архивов.

| Потребитель | Найденное использование | Требуемый результат перехода |
|---|---|---|
| application/worldData/pack/encoding/packManifestCodec.py | pack_version выбирает decoder; legacy/candidate admission проверяет wire marker | Один decoder с проверенным owning format context, без угадывания схемы или fallback |
| dataModel/worldPack/meta/worldPackManifest.py | Поля/литералы, defaults, schema-dependent проверки | Одна модель; сохранить semantic constraints без ветвления по удалённому marker |
| encoding/manifestFormat.py, read/pinnedManifestReader.py, db/repositories/sqlite/worldPack/executionPins.py | Admission проверяет manifest.pack_version | Проверять descriptor/binding и строгую schema, сохранив world/identity/budget/pin checks |
| io/worldPackWriter.py | Записывает manifest.codec_version и payload_format | Удаление вместе с legacy либо целевой заменой; не переносить неиспользуемые поля в новый state |
| import_/packImportService.py | ZIP извлекается, проверяется наличие manifest.json, вычисляется digest. Descriptor не требуется и не возвращается | Нельзя просто удалить wire marker и считать import решённым. Нужен конкретный импорт/экспорт descriptor + exact bytes либо иной явно принятый формат архива, без нового дублирующего version field |
| io/tileCodec.py, io/packBlobWire.py, encoding/climateFieldFormat.py | Читается/пишется версия бинарного payload header; decoder сверяет её | Сохранить payload admission до отдельного owning решения; удаление manifest поля не удаляет binary header |

По первичному поиску чтение manifest.codec_version/payload_format для выбора decoder не найдено. Это не доказательство отсутствия всех внешних consumers. Перед реализацией расширить инвентарь на canonical registrations, fixtures/tests, worldBundle/export, API и живые refs/архивы.

## Следующие результаты

1. Координатор проверяет ownership operation identity против persisted format, совместимость с Artifacts/Snapshot/Cache, сохранение exact bytes identity/replay; возвращает PASS/OPEN/FAIL.
2. Pack уточняет основной consumer/registration roster и целевую manifest schema в текущем скоупе. Полный import/export roster и выбор descriptor transport выполняются по отложенному плану, до зависимого удаления полей и полного cutover.
3. После согласования синхронизировать все нормативные schema/codec/acceptance sections, заменив исторические требования сохранения полей. Затем отдельный implementation slice по implement-plan; не объявлять согласование направления выполненной миграцией.
4. Порядок поставки неизменен: готовый целевой путь → полный переход callers/данных с retention → удаление всего legacy → отдельный аудит версионных обозначений. Новых DAG nodes, генераторов или публичных методов этот документ не назначает.
