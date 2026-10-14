# ТЗ: библиотеки шаблонов plot, building и structure

**Контракт A0, согласования пользователя 2026-10-14.** Целевая архитектура;
наличие текста не означает завершения кодовых шагов A1–B7.
Общая инфраструктура: [паки библиотек](tz_template_library_packs.md).
Это уточнение имеет приоритет над прежними формулировками о builtin plots
вне библиотек, name-based template identity и обязательном превращении
вложенного building template в голую UID-ссылку.

## 1. Домены и композиция

Plot имеет собственный шаблон участка. В нём находятся building templates
главного и остальных зданий. Building описывает здание и содержит structure
UID ref. Structure определяет внутреннюю геометрию: уровни, комнаты,
connections, staircases. Отдельная библиотека каждого домена не отменяет
композицию тела plot и не требует заменять вложенные building templates UID-строками.

Доменная инфраструктура различает plot_templates, building_templates,
structure_templates. Смешанная текущая building_templates library, принимающая
plot и старый outline, — состояние до разделения, а не целевой union доменов.
PlotLayoutTemplate/BuildingBodyTemplate могут использоваться как typed shapes
после сверки полей; вложенность сама по себе не является legacy-ошибкой.
BuildingTemplateOutline не эквивалентен BuildingBodyTemplate.

Вложенный building body принадлежит содержащему plot, если он не является
явной ссылкой на самостоятельного member. Нельзя объявлять его отдельным
member лишь по наличию body. При использовании записи building-библиотеки
доменная подготовка получает её по UID и сохраняет identity отдельно от тела.
Механизм явного использования библиотечного определения не должен стирать
собственные параметры plot и настройки содержащегося в нём здания.

Любое поле, объявленное библиотечной ссылкой, содержит только template_uid.
Читаемое system_name/local_uid не является адресом и может повторяться.
Полное вложенное тело не является ссылкой и не получает фиктивный UID.
Обязательная building.structure — ссылка на конкретный structure member;
в runtime resolve и сохранении применённой структуры используется тот же UID.

## 2. Defaults параметров и подготовка

Каждый домен имеет POJO-контракт, свою библиотеку и адаптер общей pack-системы.
Доменная библиотека подготавливает полный валидный шаблон: применяет defaults
допускаемых полей, явные overrides и межполевые/междоменные ограничения.
Общие CRUD/policy/remap/transaction механизмы не дублируются по доменам.

Field policies — [JSON validation](tz_json_validation.md#field-policy-annotationpolicy):
StrictOnWire обязателен; DefaultWhenMissing получает default только при
отсутствии; supplied invalid value отвергается на импорте. Явные null, 0,
false, [] трактуются по своему полю, не заменяются через truthiness.
Отсутствие main_building означает отсутствие главного здания, а не
неявное создание default building с default structure.

Defaults параметров building (крыша, фундамент, крыльцо и т.п.) принадлежат
его POJO. Defaults geometry принадлежат structure POJO. Defaults plot
принадлежат plot POJO. Нельзя создавать второй набор литералов в generators.
Для cascade-полей nullable authored значение сохраняется до существующего
LocationContext/extend; [cascade §2/4](tz_cascade_context.md) остаётся
единственным механизмом inheritance/terminal default.

Подготовка template body не означает merge с другим одноимённым member.
Нет автоматического field-level override template-члена по local_uid.
Правка самостоятельного member — общий copy/replace по UID; локальные
параметры вложенного body валидируются доменом, не общим неограниченным dict merge.

## 3. Хранение и виды паков

Тела — в доменных SQL-таблицах plot_templates, building_templates,
structure_templates. Каталог membership/owner общий: library_packs,
library_pack_members, library_pack_dependencies. Один member — один пак.
Пак может содержать несколько library_kind; это не смешивает доменные модели.
Body row не дублирует owner_world_uid; owner определяется паком.
До удаления legacy metadata колонки building_templates.structure_type/version
не определяют target building body. Для BuildingTemplate structure_type=NULL;
structure UID хранится в подготовленном data. Тип не выводится из строки UID.

- Engine default: owner_world_uid=NULL, pack_uid входит в доверенную
  декларацию движка. Доступен всем мирам, read-only для пользовательской записи.
- Engine user: owner_world_uid=NULL, UID не объявлен default. Mutable;
  миру доступен после явного полного instantiate в world-owned instance.
- World-owned: owner_world_uid=world UID, authoring/instance только своего
  мира, mutable. Новые UID при копировании, provenance источника сохраняется.

Default-статус не назначается manifest, папкой, display_name или source_file.
Каталог мира = declared defaults + world-owned паки мира. Global list_all
не используется генерацией. Pins — (library_kind, template_uid), маркер
использования; не фильтр доступности и не замена ссылочной целостности.

## 4. Стандартные библиотеки и canonical attach

Стандартные plot/building templates — настоящие members объявленных
дефолтных библиотек с UID. Для явного выбора используется обычный UID;
специальный selector default/drawing_key и отдельные default counts не вводятся.
Structure base остаётся default-паком. Relief default body packs остаются
пустыми; smoke_003 не auto-default.

Canonical provider каждого домена задаёт единственный исходный набор
стандартных шаблонов; POJO задаёт defaults параметров и валидацию; SQL
хранит подготовленные записи. Это не два независимо редактируемых набора
дефолтов. При разделении текущих fixtures/templates standard records
сохраняются по явной identity map и объявленному source provider.
Список default UID задан доверенным spec, не сканированием произвольных FS паков.

Объявленные паки: engine.plots.base, engine.buildings.base,
engine.structures.base. Plot/building зависят от structure base; plot хранит
inline building bodies, поэтому зависимость на building pack из вложенности
не выводится. Единственный источник стандартных plot — явно перечисленные
fixtures/templates; стандартный building с тем же локальным именем получает
тело объявленного main_building этого plot. Произвольные inline bodies
пользовательских шаблонов при этом не извлекаются в библиотечные members.

Существующий CanonicalLibrarySpec/global_fill_missing добавляет отсутствующие
UID/body/membership атомарно. Существующие тела/source_file не перезаписываются;
полнота проверяется по всем объявленным UID/membership, без положительного
бессрочного fullness cache. Публичные reads обеспечивают attach; generators
получают scoped typed snapshot, не читают FS/SQL самостоятельно.

Пользователь меняет стандартный шаблон через собственную копию mutable member
с новым UID. Совпадение имени со стандартным member ничего не заменяет.
Названия default-паков задаются центральной декларацией; UID вычисляет app.ids.

## 5. Runtime и сохранённые ссылки

Async library layer подготавливает scoped immutable snapshot, проверяет
membership/kind/body/deps и согласованность plot/building/structure.
Sync generators принимают typed models/context. Persist остаётся отдельным
сервисом, в общей UOW. Defaults поля, выбор стандартного member и runtime
fallback неразрешимой ссылки — разные механизмы.

NamedLocation.system_template_uid всегда хранит UID реально выбранного
библиотечного шаблона, не имя plot/building. Kind определяется declared
consumer/ref-контрактом, а не угадывается по строке. Уникальность проверяется
PK template_uid; дополнительно проверяются kind, owner и world availability.
Не придумывать building member UID для inline body: сохраняется реальная
identity источника, которую caller передал отдельно от подготовленного тела.

У созданного здания сохраняется system_structure_template_uid — UID
фактически использованного StructureTemplate. При генерации с geometry
он обязателен; None допустим для локаций без structure и legacy-данных,
источник которых нельзя восстановить по явной карте. Не угадывать источник.
Изменение building template не переписывает сохранённый structure UID;
повторная генерация записывает вновь применённый UID. Обычное чтение не
пересчитывает ссылку. UID фиксирует identity, не snapshot версии тела.

SQL/model/bundle DTO меняются согласованно. Export/import и world copy
переносят и remap обе ссылки; применённый structure учитывается usage/
проверкой удаления/удержанием. Не менять семантику прочих location types
без их доменного контракта. Новых generic provenance/version полей нет.

## 6. Recipe refs, legacy и migration

District required_structures[].plot_template — plot UID. Plot_counts и
plot_priority на settlement/district адресуются plot UID. Aliases
building_template/structure_counts/structure_priority не меняют identity.
Required purpose selector не превращается в explicit template ref.

N: required.count → district count → settlement count → 1.
Priority: district priority → settlement priority → 0. Missing key не
равен нулю; explicit 0 и порядок required сохраняются. Все UID keys
участвуют в composed remap и declared ref usage.

Legacy names принимаются только compatibility import: по явной карте или
однозначному доступному совпадению с диагностическим path. Несколько
members — ошибка с кандидатами, не first/last wins; неизвестное required
значение — ошибка, не runtime fallback в importer.

Legacy registry извлекается до world normalization; pointers → pins /
полные instances по owner/default status; authored/edited тела сохраняются.
Извлечение building body в отдельный member не обязательно: действовать
по declared source identity, не по одному наличию вложенности.
Modern world-owned manifests/bodies сохраняются целиком; пользовательский
engine-пак не публикуется world import'ом. Общий writer/policy/token/UOW,
без отдельного миграционного confirm или скрытого hydrate-write.

Pure converter получает raw body до normalization, явно объявленную source
shape, destination member и scoped membership от caller. Legacy plot из
смешанной building-библиотеки переносится в plot_templates вместе с вложенными
main/secondary bodies. Legacy outline можно перенести в building_templates
только с конкретной structure и полями, имеющими target mapping; geometry
и прочие непереносимые поля не отбрасываются молча, а дают ошибку с path.
Modern тела и provenance сохраняются; remap касается объявленных UID refs.
Old → intermediate → final карты композируются с проверкой конфликтов/циклов.
Результат сохраняет все исходники, paths и сведения о resolution legacy names;
при ошибке runnable converted batch отсутствует. Converter не пишет SQL,
не выполняет attach/instantiate и не придумывает identity для inline body.

## 7. Ошибки и ограничения

Невалидное body/владение при import — ошибка. Missing pack dependency —
диагностируемая неполнота, без auto-instance. Runtime unknown/unavailable
ref — одна library diagnostic + объявленный доменный fallback/отказ,
stored ref сохраняется. Relief R21 не подставляет другое тело.
Structure POJO fallback 5c-1 не объявляется реализованным этим контрактом.
Manifest contextual fallback world → pack → POJO остаётся отложенным.

Новые SQL изменения — только 0001_initial.sql + dataclass models; локальная
БД recreate, файловые источники переводятся явной картой. DAG wiring
остаётся под Gate: DAG. Исторические JSON/SQL snippets прочих ТЗ не являются
основанием вернуть name identity или pointer availability после cutover.
