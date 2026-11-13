# Pack metadata dependency POJO: проект конкретного обмена

Дата: 2026-11-13. Статус: POJO PROPOSAL после согласования [трёх семантических решений](pack-metadata-dependency-usage.md#согласованные-решения-пользователя). Только документация. Имена новых типов ниже — кандидаты, не runtime imports. Новые signatures и persisted schema требуют проверки по правилам проекта; готовность внешних типов не предполагается.

## 1. Единственные объявления и внешние типы

Существующие проектные PackAssemblyAddress, PackMetadataSubject, PackStoredProvenance, PackPartProvenance, PackStoredAssemblyProvenance переиспользуются. Значения metadata остаются в PackAssemblyInput, их второй DTO не создаётся. SourceDurableProof остаётся единственным owning proof; Planning остаётся в PackStoredProvenance.planning.

Три обозначения внешних ролей в таблицах — **SourceDependencyUsage**, **SourceDependencyAdmission**, **SourceProofSelection** — требования к владельцу Source, не принятые имена/схемы или разрешение объявить placeholder. Usage представляет композицию реально использованных исторических зависимостей. Admission связывает exact usage с proof и позволяет проверять эту связь через согласованный owning binding. Selection выбирает subset внутри данного proof, а не индекс Pack и не голые capture-local indices. Если владелец предъявит существующие эквивалентные типы, используются они, без зеркал в Pack.

## 2. Поля Pack POJO

Предлагаемые модули: `dataModel/worldPack/preparation/metadataDependencies.py` для transient records, `dataModel/worldPack/meta/metadataAttribution.py` для durable mapping. Модели strict/frozen/extra-forbid/revalidate-always; вложения immutable; обязательные поля без скрытых defaults. Нет dict/Any, reader, lease, callback, receipt store или счётчика версии state.

| Модель | Все предлагаемые поля | Ответственность |
|---|---|---|
| PackMetadataDependencyUse | group: PackMetadataGroup; source_usage: SourceDependencyUsage | Зависимости одной группы. Нет копии значения metadata |
| PackMetadataDescription | subject: PackMetadataSubject; dependencies: tuple[PackMetadataDependencyUse, ...] | Связанный subject и полный ожидаемый usage его групп |
| PackMetadataInputEvidence | input_field: PackMetadataInputField; value_fingerprint: RevisionHex; source_usage: SourceDependencyUsage | Связь конкретного поля текущего typed write input с producer usage; fingerprint вычисляет producer/Pack owning binding, не DAG |
| PackMetadataGroupAdmission | group: PackMetadataGroup; selection: SourceProofSelection | Соответствие группы subset единственного row proof |
| PackMetadataProofBinding, уточнение | subject: PackMetadataSubject; provenance: PackPartProvenance; source_admission: SourceDependencyAdmission; groups: tuple[PackMetadataGroupAdmission, ...] | Полный bind одной projection. Proof в provenance должен быть тем же proof, который подтверждает admission; Source result не создаёт вторую persisted копию |
| PackMetadataAttribution | groups: tuple[PackMetadataGroupAdmission, ...] | Durable выборка по группам относительно source_proof содержащего record; не самостоятельное хранилище proof |
| PackStoredAssemblyProvenance, уточнение | address: PackAssemblyAddress; provenance: PackStoredProvenance; attribution: PackMetadataAttribution либо None | Один общий row proof, одна карта subset. None допустим только для доказанно неизменного старого whole-row provenance, не для новой/пересчитанной строки |

**State:** к принятым base_publication/parts/assembly/assembly_provenance предлагается добавить `metadata_dependencies: tuple[PackMetadataDescription, ...]`. Это один transient носитель; отдельный PackMetadataDependencyState с теми же записями не нужен. Subject fingerprint и value хранятся не дважды: значение только в assembly, subject лишь идентифицирует его. Для изменяемой projection карта содержит usage всех групп, включая переносимые; старый whole-row record без детализации не получает выдуманную запись.

Для unchanged rows после bind достаточно durable attribution; соответствующая transient запись удаляется. Следующий partial write получает точные dependencies из её subsets через согласованную pure owning операцию над материализованным proof. Если для этого нужен IO, его нельзя скрыть в write: владелец должен предъявить другой допустимый binding до принятия этой схемы. Pending partial writes используют актуальную transient карту, не pinned A повторно.

**Write inputs:** `metadata_inputs: tuple[PackMetadataInputEvidence, ...]` предлагается только тем конкретным inputs, которые получают влияющие на metadata значения. Он описывает исходные поля, а не proof результата. Разрешённый набор input_field зависит от конкретного метода. None-preserve не требует evidence нового значения; explicit empty требует. Для initial assembly требуются основания каждого initial scalar. Связь payload/address/membership evidence с конкретным producer output не заменяется независимым caller tuple.

## 3. Typed groups и предел точности

PackMetadataGroup — закрытый enum, допустимость значения проверяется по виду PackAssemblyAddress. Typed selectors реализации используют существующие owning field definitions; свободные строки путей запрещены.

| Address kind | Предлагаемые группы |
|---|---|
| header | LAST_L0_MODE, FINE_CELLS_PER_MAP_CELL, WORLD_MAP_CELLS_PER_TILE, FINE_CELL_SIZE, MAP_SUBSURFACE_DEPTH, TERRAIN_CHUNK_COLUMNS — каждый scalar отдельно |
| tile | IDENTITY (gx/gy), CLIMATE_STATUS, WILDERNESS_REFINE_STATUS |
| chunk | IDENTITY (cx/cy внутри адресованного tile), REFINE_ROLE |
| settlement | IDENTITY, TERRITORY_VOLUME, PACKED_DISTRICT_UIDS, STRUCTURE_STATUS; остальные поля окончательной owning assembly row должны быть перечислены до freeze, не поглощены неявным OTHER |
| location | Полная строка заменяется одним write, но единая группа WHOLE_ROW допустима только при подтверждённом общем usage всех полей; иначе разнести по owning полям |
| region | То же требование для owning WildernessRegionEntry. Полная замена не доказывает одинаковый usage bbox, status и остальных полей |

IDENTITY usage связывается с основанием создания/сохранения адреса; повтор координат в transient payload не добавляется. Pack constant/rule с отсутствием Source reads требует owning допустимого empty usage и проверки правила, а не отсутствующей обязательной записи. Полный field roster location/region/settlement и PackMetadataInputField по каждому write остаётся технической работой до freeze; произвольные дополнительные поля этим документом не допускаются.

Например, для settlement input_field различает TERRITORY_VOLUME, PACKED_DISTRICT_UIDS, STRUCTURE_STATUS и основание идентичности; для recalculate — EXPECTED_CHUNKS при explicit значении. Основание текущего chunk membership нельзя заменить usage содержимого всех payload. Если membership provenance не выводится из предъявленных owning данных, это конкретный незакрытый binding данной операции.

## 4. Mapping и новые сигнатуры

Кандидат сигнатуры: `describe_metadata(PackMetadataSubjectsInput) -> tuple[PackMetadataDescription, ...]`. Request сохраняет state/addresses. Write по-прежнему возвращает PackPreparationState; bind по-прежнему принимает state/entries и возвращает state, но entries используют уточнённый PackMetadataProofBinding. Новый PackWriteResult не вводится.

1. Pack write проверяет typed inputs/evidence, вычисляет projection и переносит/заменяет usage групп атомарно в новом immutable state. Старый state не изменяется при отказе. Внутренняя проверка inputs не является вызовом другой публичной операции.
2. Describe возвращает текущий subject и готовые usages. Для pending projection использует transient карту, для detailed durable projection — materialized proof/attribution по принятому pure binding. Для старой whole-row projection не выдаёт fabricated group map: unchanged inheritance использует существующий путь переноса полного provenance, запрос точной детализации отклоняется.
3. DAG передаёт usages в Source, сохраняя корреляцию с готовыми группами. Source формирует общий proof и соответствующие selections, не получая Pack group enum/subject: корреляция может быть порядком элементов owning запроса/ответа, но этот порядок должен быть явно гарантирован Source API. DAG механически соединяет результаты с исходными group keys; не вычисляет union/subset. Точный составной Source request/result ещё должен быть предъявлен владельцем.
4. DAG переносит source result в source_admission и proof в общий provenance, возвращает исходный subject и group selections. Planning не вычисляется из Source result; применяется ранее согласованный отдельный binding.
5. Bind проверяет exact subject, полный набор groups, immutable usage текущего state, owning эквивалентность selections ожидаемому usage и equality общего proof/admission. Затем сохраняет общий provenance и attribution; промежуточные usage не пишутся вторым proof в manifest.
6. Final prepare проверяет полный состав, detailed records новых строк и разрешённое exact inheritance старых. Closure собирается по общим owning proofs; group selections не разрешают исключить refs, необходимые owning proof format. READY/holds проверяются отдельно.

## 5. Admission, ошибки и старая база

| Случай | Обязательное поведение |
|---|---|
| Missing/extra/duplicate group; group несовместима с address | Отказ с адресом/полем и индексом; без частичного bind |
| Изменены projection/base или usage при том же значении | Отказ stale/mismatched binding; одного subject hash недостаточно |
| Source result для другого usage/proof/мира; неверный subset | Owning admission failure, переведённый согласованным Pack diagnostic mapping |
| Evidence поля не соответствует typed input или отсутствует | Отказ до вычисления зависимого результата; независимые ошибки агрегируются |
| Старая строка без attribution, без изменения | Разрешены read и exact inherited перенос полного прежнего provenance |
| Partial update старой строки требует неизвестных dependencies сохранённых полей | Отказ до потери старого record. Не подставлять whole-row proof вместо subset |
| Полная замена старой строки | Разрешена при evidence всех требуемых новых inputs; результат получает detailed attribution. Новые inputs не должны скрыто зависеть от неизвестного старого значения |
| Caller подделал state или successful Source DTO | Structural consistency не является доказательством; требуется принятая producer/owning boundary. Без неё semantic acceptance не объявляется |

Используется существующий PackPreparationDiagnostic union, FieldPathError/typed selectors и ValidatorAggregationHelper. Новые конкретные коды для missing attribution/group usage не объявляются наугад: перед freeze сверить existing enum и зафиксировать exact mapping. Это остающаяся техническая часть схемы, не вопрос пользователю о названиях кодов.

## 6. Статус и следующий шаг

Семантика и переход старой базы согласованы. Таблицы конкретизируют кандидат Pack data transfer и способ не дублировать row proof: одна Source proof плюс group subsets. Именно этот способ ещё требует проверки Source selection/admission binding; он не выводится из пользовательского согласия автоматически.

До реализации остаются: полный field/input roster; точные внешние usage/admission/subset типы и pure extraction; trusted producer/state boundary; exact diagnostics и canonical schema registration. Не объявлять их готовыми и не блокировать ими независимые Pack операции. Проверки смешанного происхождения, restart, equal-value/different-usage, отсутствующей attribution и масштабирования заданы в исходном документе. Следующая приёмка применяет все правила проекта к этому конкретному срезу; документ не разрешает изменение кода.
