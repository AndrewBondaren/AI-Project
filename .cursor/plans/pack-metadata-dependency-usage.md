# Pack metadata: фактически использованные зависимости и передача через DAG

Дата: 2026-11-13. Статус: SEMANTICS ACCEPTED / POJO PROPOSAL. Пользователь согласовал три решения ниже; конкретная схема POJO подготовлена для проверки, runtime реализация не разрешена этой записью. Основания: [R1/R3](source-pack-dag-contract-review.md), [write-план](pack-v2-public-write-operations.md), [Pack admission](pack-source-admission-boundary.md), [кандидат Source proof](source-durable-proof-contract.md).

## Согласованные решения пользователя

1. Происхождение детализируется по независимо обновляемым полям; группа разрешена только для совместно вычисляемых и сохраняемых полей с общим usage.
2. Разрешено подготовить необходимые изменения Pack POJO: transient карту state, describe с subject + usage, проверку usage в bind и durable детализацию metadata provenance. PackStoredProvenance и Source proof не дублируются. Это согласование направления изменений, не принятие непредъявленных полей внешнего типа.
3. Старая база без детализации допускает чтение и наследование неизменной строки. Partial update, для которого неизвестно происхождение сохранённых полей, отклоняется. Полная замена разрешена при предъявлении всех необходимых новых зависимостей. Избыточное покрытие полным старым proof вместо точного usage не выбрано.

Конкретный [проект POJO и mapping](pack-metadata-dependency-pojo.md) подготовлен по этим решениям. Предложения §4 ниже читать в этом статусе; внутреннюю схему Source по-прежнему определяет его владелец.

## 1. Принятые границы и обнаруженный пробел

Сохраняются: DAG оркестрирует; Pack исполняет одну запрошенную операцию и вычисляет собственную metadata; Source проверяет свои исторические зависимости, не знает Pack metadata DTO. Pack не вызывает публичный Source API. Start/write/bind формируют state, final prepare получает конечный state и не повторяет writes. Settings, порядок writes и отложенный PACK-METADATA-PLANNING этим документом не пересматриваются.

Текущий проект state содержит base_publication, parts, assembly, assembly_provenance. При изменении projection stale proof удаляется. Describe возвращает PackMetadataSubject(base_publication, address, value_fingerprint); bind принимает subject и provenance. Subject идентифицирует значение, но не фактически использованные inputs. В этих полях нет согласованного носителя связи результата с сохранёнными и новыми зависимостями между write и describe. Из итогового значения или fingerprint восстановить эту связь нельзя.

Поэтому R3 не закрывается наличием describe/bind. R1 требует от Source представления нескольких исторических captures либо доказанной эквивалентной модели. Single-capture кандидат не является таким доказательством. Это незавершённая интеграционная граница, не повторный отказ принятому локальному scope Pack и не запрет независимой работы.

## 2. Трассировка смешанного происхождения

| Операция | Сохраняемые и новые значения / сценарий | Основание |
|---|---|---|
| write_settlement_structure | Новый territory_volume; packed_district_uids=None и structure_status=None сохраняют соответствующие поля предыдущей строки. Явный пустой packed tuple очищает список. После нескольких writes предыдущая строка может происходить уже из B, а не только из pinned A | [publish_settlement_structure](../../backend/app/application/worldData/pack/io/worldPackWriter.py): prev, packed/status resolution, создание SettlementStructureEntry |
| sync_grid_metadata | Новые fine_cells_per_map_cell/world_map_cells_per_tile при сохранении прочих header scalars | Там же, sync_world_metadata; перенос на target sync_grid_metadata описан write-планом. Legacy codec assignments не входят в target public metadata inputs |
| write_map_tile / set_last_l0_mode | Фактический side последнего tile write или новый mode сочетаются с оставшимися header scalars | Там же, write_world_map_tile; set_last_l0_mode — target операция write-плана |
| write_wilderness_chunk / recalculate_wilderness_status | Wilderness status вычисляется из текущего состава chunks и expected_chunks конкретного вызова; climate_status сохраняется. Состав может включать inherited и новые chunks | Там же, commit_chunk/recalc_wilderness_status. Provisional/final порядок сохраняется |
| write_fine_climate | climate_status=fine при сохранении wilderness status существующего tile | Там же, write_climate_tile |
| delete_wilderness_chunk / delete_fine_climate | Меняется один аспект tile status, соседние поля сохраняются; отсутствие/удаление является входом решения, а не неявным чтением Source | [Chunk delete](pack-delete-wilderness-chunk-contract.md), [climate delete](pack-delete-fine-climate-contract.md). Это target contracts, не доказательство наличия legacy delete |

Новая строка с defaults требует происхождения и основания правила; значение default не означает inheritance. Pack-owned константа/правило не превращается в фиктивную Source dependency. Полная замена location/region row сама по себе не доказывает смешение с базой: основания нового результата предъявляет producer. Незатронутые rows и projections сохраняются вместе с действующим provenance.

Для status не следует автоматически включать Source dependencies содержимого всех chunk payload: фактически читается состав/количество и expected. Нужны основания membership и соответствующих control inputs; полный payload proof может быть лишь консервативным покрытием. Source reads, Pack structural inputs и Planning dependencies различаются.

## 3. Требования к решению

1. Pack фиксирует dependency usage одновременно с вычислением результата, до потери старого provenance. Учитываются сохранённые значения текущего state, новые inputs, прочитанные условия ветвления, membership/absence и materialized параметры вычисления. Равенство значений не означает равенство происхождения.
2. Новые typed inputs имеют проверяемую связь с owning producer evidence. Нельзя считать payload proof автоматическим свидетельством для territory_volume, явного packed list, expected_chunks, grid parameters или mode. Нельзя требовать proof ещё не вычисленной metadata на входе write.
3. Usage проходит через immutable промежуточное состояние без side store, command log, callback или повторного выполнения writes. DAG не вычисляет зависимости и не интерпретирует metadata.
4. Describe отдаёт exact subject и связанный с ним usage. Bind проверяет оба аспекта: актуальность значения и соответствие proof ожидаемому usage. Подмена при одинаковом value_fingerprint также обнаруживается.
5. Для требования точного usage детализация сохранённых полей должна переживать публикацию/restart/start_from_base. Whole-row proof не позволяет восстановить dependencies одного сохранённого поля. Нельзя объявлять полный proof строки точным subset без доказательства.
6. Исторические revisions сохраняются даже при наличии более нового capture. Indices имеют смысл только в своём capture; одинаковые числовые indices разных captures не объединяются. Разные исторические revisions одного объекта не являются автоматически конфликтом: provenance описывает смешанный результат, а не один согласованный snapshot.
7. Source подтверждает заявленные source зависимости и closure, но не полноту чтений алгоритма Pack. Pack/producer binding отвечает за фактическое использование inputs. Caller-constructed success record, fingerprint или tuple refs не дают сами по себе доверенной проверки.
8. Readiness и atomic retention остаются отдельными: успешный metadata bind не удостоверяет holds и не создаёт READY. Внешние недостающие bindings ограничивают интеграционный маршрут, не всю доступную работу Pack.

## 4. Предлагаемое решение — требует отдельного принятия

Рекомендуется детализация по независимо сохраняемым/заменяемым полям или группам полей, вычисляемым совместно. Для settlement минимально различать territory_volume, packed_district_uids, structure_status; для header — каждый независимо обновляемый scalar; для tile — wilderness status и climate status. Группа допустима, только если её поля всегда имеют общий usage и обновляются вместе. Полный реестр адресов/групп ещё нужно предъявить; произвольные string paths не вводятся.

### Предлагаемые носители и ответственность

Ниже имена кандидатов, не существующие runtime POJO и не новая утверждённая схема. Source-owned типы предъявляет Source; Pack не копирует их поля.

| Носитель | Предлагаемые данные | Владелец и назначение |
|---|---|---|
| PackMetadataDependencyState | Tuple записей по metadata address и typed field/group selector; для каждой — связь с текущим значением/использованными typed inputs и source usage | Pack. Transient карта в preparation state; не второй manifest и не история вызовов. Точная форма связи с inputs и граница доверия требуют приёмки |
| PackMetadataDescription | subject: PackMetadataSubject; dependencies: tuple[PackMetadataDependencyUse, ...] | Pack. Кандидат output describe вместо одного subject; возвращается DAG |
| PackMetadataDependencyUse | group: Pack-owned typed selector; source_usage: Source-owned usage | Pack оборачивает owning usage для одной группы. Source не получает group/subject и не импортирует этот DTO |
| Source usage | Ссылки на готовые owning зависимости новых inputs и сохраняемых групп; способность представить несколько captures | Source. Точная схема, нормализация, validation и equivalence принадлежат Source. Не объявлять здесь копию capture/selection |
| Source admission result | Связанные исходный usage и проверенный durable proof либо owning эквивалентная проверяемая связь | Source. Используется для точного сопоставления запроса и результата; не capability и не доказательство исполнения Pack |
| Metadata binding | Exact subject и результаты Source для ожидаемых groups; итоговый stored provenance | Pack. Кандидат дополнения текущего PackMetadataProofBinding, а не молчаливое изменение принятой пары subject/provenance |
| Durable metadata attribution | Соответствие typed groups owning durable evidence, достаточное для дальнейшего partial preserve | Pack владеет group mapping, Source владеет proof. Размещение относительно PackStoredAssemblyProvenance и устранение дублирования общего proof требуют отдельного schema решения |

Write сохраняет прежнюю форму возврата state; новый PackWriteResult не предлагается. Однако добавление transient карты в state и evidence binding новых inputs — реальные изменения контракта, которые необходимо принять до реализации. Нельзя разместить их в неописанном private singleton или скрытом поле. Persisted group mapping тоже является изменением схемы, а не внутренней оптимизацией.

На write Pack переносит usage неизменённых групп из текущего состояния, заменяет usage перезаписанных групп и формирует usage вычисленных групп из реально использованных оснований. При B→C не возвращается автоматически к базе A. Удаление значения удаляет его attribution; зависимости факта удаления сохраняются в usage результата, если этот факт участвовал в его вычислении. Накопление всех предыдущих inputs без учёта использования не считается точным usage.

Opaque Source usage можно передавать как отдельные owning компоненты для последующей проверки Source. Pack не объединяет capture-local indices, не читает Source bodies и не нормализует Source revisions. Как композиция компонентов представляется публичным Source input, определяет Source; это отдельная точка согласования, не разрешение Pack вызвать Source helper с IO.

### Передача через DAG

1. Producer возвращает typed значения и evidence их входных зависимостей; DAG передаёт готовое соответствие в конкретный Pack write. Для inherited значений start_from_base получает durable group attribution закреплённой версии.
2. Pack write вычисляет значение и одновременно обновляет transient карту usage. Последующие writes получают этот state в прежнем порядке.
3. DAG вызывает describe после нужных writes. Pack возвращает subject и готовые dependency uses по groups. Fingerprint вычисляет Pack.
4. DAG передаёт каждое source_usage в согласованную публичную операцию Source. Сохраняет готовую корреляцию subject/group с запросом; не выбирает зависимости, не объединяет selections и не повторяет merge. Batch допустим только после отдельного принятия его API, не подразумевается этим документом.
5. Source возвращает proof с проверяемой связью с usage. Source не удостоверяет territory/status и не получает Pack DTO.
6. DAG возвращает результаты в bind вместе с исходной корреляцией. Pack сверяет текущие subject, groups и ожидаемый usage; применяет owning proof admission через принятый binding. Нельзя принимать доказательство другого usage только из-за равного результата вычисления.
7. Pack сохраняет достаточный durable group mapping; final prepare проверяет полноту и closure всего конечного состава. Prepare не запускает describe/bind/Source и не достраивает отсутствующие зависимости.

Конкретные NodeId, новые DAG deps или иной порядок здесь не назначаются. Возможность локально проверить owning usage/proof relation без публичного Source вызова должна быть предъявлена binding; пока этого нет, semantic admission нельзя объявлять реализованным. Возможность подделать переданный state/usage также требует явной границы доверия; совпадение двух caller-копий не закрывает её.

## 5. Source proof и переход существующей базы

Рекомендуемое требование к SourceDurableProof — представлять конечное множество использованных исторических зависимостей нескольких captures, сохраняя capture-local meaning. Это не утверждение конкретной tuple schema. Одного capture достаточно лишь при доказанном покрытии всех нужных исторических входов; автоматический новый capture ради этого не вводится. Closure включает необходимое для восстановления всех компонентов, без latest fallback и с независимым удержанием после release базы.

Существующий whole-row proof не даёт точной field attribution. Пользователь выбрал: чтение и неизменное наследование разрешены; partial update с неизвестным происхождением сохранённых полей отклоняется; полная замена допустима при наличии всех новых зависимостей. Новые/пересчитанные строки публикуются с достаточной детализацией. Консервативное покрытие старым whole-row proof вместо точного usage не выбрано. Самовольное восстановление по значениям, повторная генерация и тихая замена historical proof текущим capture запрещены.

Не переносить Planning dependencies внутрь Source proof. PACK-METADATA-PLANNING остаётся отложенным; данный документ не объявляет точное Planning mapping готовым и не использует эту отсрочку для потери Source происхождения.

## 6. Приёмка предлагаемого среза

Перед кодом отдельно принять точные state/input/output/stored schema изменения, полный field/group roster, owning Source usage/result/equivalence, ошибки и доверенную boundary. До этого таблица кандидатов не является готовым контрактом для implement-plan. Все обязательные критерии проекта применяются к выбранному срезу; данный документ не объявляет их пройденными.

Проверки после согласования:

- A содержит прежние packed/status, B даёт territory: итоговое attribution сохраняет нужные A и B зависимости; явный пустой packed отличается от None.
- A→B→C без промежуточного bind: сохраняемые поля получают usage из предыдущего state, не из исходной A и не из последнего capture целиком.
- Одинаковое итоговое значение при разных usages и A→B→A не позволяют подставить stale proof.
- Header partial writes, independent tile statuses, provisional/final expected, chunk membership и delete используют действительные основания; payload content dependencies не добавляются только по наличию chunk.
- Два captures с одинаковыми indices; разные revisions одного объекта; wrong world; missing/extra/duplicate groups и swapped Source responses проверяются по owning правилам, без неявной потери historical inputs.
- Restart и последующий partial update сохраняют field/group attribution; старая whole-row база обрабатывается по явно выбранной политике.
- Immutable/forged state и неподтверждённые success records не обходят provenance admission. Hold release race остаётся отдельной lifecycle проверкой.
- Масштабирование 1000/4000/16000 частей учитывает новую transient/durable детализацию и её копирование по [write benchmark gate](pack-v2-public-write-operations.md#стоимость-последовательных-writes--отдельная-проверка-масштабирования); command history и неограниченное накопление dependencies не вводятся.

Следующий предмет проверки — конкретный проект POJO, Source binding и durable schema. Семантика детализации, направление изменения Pack POJO и политика старой базы согласованы выше; повторно их не открывать. R1/R3 не объявляются закрытыми до проверки конкретного обмена и owning bindings.
