# Pack — удаление fine climate и статус тайла

2026-11-12. PROJECT, только документация и статический trace; runtime/SQL/DAG не менялись, тесты не запускались. Дополняет [climate binding](pack-climate-bindings.md), [delete_part](pack-delete-part-contract.md) и [write-план](pack-v2-public-write-operations.md).

## Подтверждённая семантика

[WorldPackWriter.write_climate_tile](../../backend/app/application/worldData/pack/io/worldPackWriter.py) записывает fine BLOB и устанавливает tile.climate_status=fine. Отдельного delete fine метода нет. [TileManifestEntry.validate_climate_status](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py) проверяет направление «fine ref присутствует → status fine», но не обратное. ClimateBakeStatusMixin по умолчанию задаёт coarse; существующая модель не требует наличия coarse BLOB для этого статуса. Поэтому coarse означает отсутствие заявленной fine-готовности, а не доказанную доступность coarse artifact.

[apply_climate_to_view](../../backend/app/application/worldData/pack/climate/climatePackApply.py) сначала сохраняет уже заполненные temperature_base/rainfall. Для недостающих полей рассматривает fine sample, затем coarse sample; выбор выполняется отдельно для каждого поля. Если нет подходящего значения, view сохраняется. Эта функция не запускает генератор и не обнуляет ранее заполненные значения. Удаление fine BLOB не означает, что все читаемые климатические значения обязательно изменятся.

[PackReadContext.climate_tile_field](../../backend/app/application/worldData/pack/read/packReadContext.py) в legacy возвращает None как при отсутствии файла, так и при некоторых ошибках чтения (ValueError/FileNotFoundError). Это не целевой artifact admission: заявленный ref с повреждёнными/недоступными bytes должен дать типизированный refusal. Только подтверждённое отсутствие части является отсутствием fine, а не любая ошибка. [Loading progress](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py) использует any(tile.climate_status==fine), поэтому оставленный fine после удаления вводил бы наблюдаемую готовность в заблуждение.

## Предлагаемый публичный метод

Класс `PackPreparationService`, `backend/app/application/worldData/pack/preparation/packPreparationService.py`:

`def delete_fine_climate(self, request: PackDeleteFineClimateInput) -> PackPreparationState`

Input в `backend/app/dataModel/worldPack/preparation/operations.py`: `state: PackPreparationState`, `address: PackFineClimateAddress` из preparation/addresses.py. Никаких coarse_ref, нового status, callbacks или generator settings. Идентичность мира берётся из state.base_publication; gx/gy уже находятся в address. Input strict/frozen/extra=forbid с nested revalidation.

Результат — общий проект PackPreparationState. Изменение metadata использует принятое направление typed subject/dependencies → DAG → evidence → отдельный Pack bind. Общий representation этих выходов ещё не завершён; метод не вводит собственный proof/receipt и не объявляет промежуточный state готовым к публикации.

Отказ — общий проект PackPreparationFailure из `application/worldData/pack/preparation/errors.py`, с PackPreparationError/PackPreparationIssue из `dataModel/worldPack/preparation/errors.py`. Structural diagnostics и semantic codes переиспользуются по write-плану; новые ClimateDeleteError не нужны. Caller — прямой DAG-вызов, последующую операцию выбирает DAG.

## Один локальный переход

1. Повторно проверить typed input/state и уникальность адресов. Не исправлять дубликаты удалением всех копий.
2. Удалить только climate_fine(gx,gy) вместе с его payload provenance. Не удалять тот же ref на другом адресе и не снимать physical holds.
3. Если tile существует и имеет fine, установить coarse. Сохранить tile, map_tile, chunks, wilderness status, остальные поля и все другие tiles. Это предложенная policy новой delete-операции, а не найденное legacy поведение.
4. Если fine part отсутствует, но tile всё ещё fine (например, промежуточный результат delete_part), согласовать статус тем же переходом. Если part отсутствует и tile уже coarse либо tile отсутствует, no-op после проверки. Если part был без tile, удалить part без создания tile.
5. Для изменённой tile projection не переносить старый несовместимый proof. Сохранить связь с использованным state/адресом/результатом по общему metadata-output контракту. Если значение осталось равным, применимость proof проверять по semantic dependencies, а не только по строке coarse. Незатронутые proofs сохраняются.

Метод не вызывает публичный delete_part, write_coarse_climate, Source, Climate, Cache, prepare или activate. Внутренняя pure реализация одного перехода не является orchestration. Нет fallback-генерации, чтения текущего мира или очистки legacy path caches. Имена статусов остаются существующими: отдельный absent climate status не вводится.

## Final admission и чтение

Final prepare проверяет scope, допустимость отсутствия fine по coverage, metadata/provenance и полный closure. Если coverage требует fine, удаление отклоняется, даже когда coarse существует. Если fine не требуется, отсутствие coarse само по себе не добавляет новый безусловный запрет; обязательность coarse определяется конкретным принятым scope/coverage, не именем статуса. Подтверждённое отсутствие обоих полей не разрешает синтез defaults в Pack.

Целевой read_part для fine-адреса возвращает typed absent при отсутствии части; он не возвращает coarse BLOB вместо запрошенного fine и не исполняет consumer fallback. Существующий порядок выбора sample относится к consuming read-проекции и её миграции. Для pinned версии её fine/coarse данные должны происходить из той же закреплённой публикации; нельзя искать coarse в latest head после отсутствия fine. Текущий legacy ctx/world/path flow не объявляется готовой pinned реализацией.

Старый manifest/pin продолжает видеть прежний fine. Новый полный closure исключает удалённый ref только если не осталось иных частей/proofs, требующих его. Physical release/GC остаются у owning lifecycle; операция удаления state не изменяет их.

## Приёмка проекта и проверки реализации

- Fine part + fine tile → part отсутствует, tile coarse; map_tile/chunks/wilderness status и другие адреса неизменны.
- После generic delete_part статус fine корректируется; повтор delete_fine_climate — no-op без создания tile.
- Отсутствующий coarse не запускает генерацию и не подменяется пустым BLOB; обязательный fine по coverage приводит к отказу final prepare.
- Changed tile proof не наследуется по совпадению значения; missing required proof не даёт READY.
- Corrupt declared fine даёт read refusal, а не absence с молчаливым coarse fallback.
- Consumer сохраняет существующие значения view и per-field fine→coarse порядок; одно поле может остаться None. read_part не присваивает coarse результат fine-адресу.
- Old pin после удаления/новой публикации читает прежний fine; shared ref не освобождается преждевременно; input state не мутирует; pure метод не делает I/O.

Роли классов: Input — typed boundary; PackPreparationService — один pure переход; PackPreparationValidator — local/final инварианты; PackPreparationOperation — verified admission/holds/READY; assembler — конечный manifest. Прямые междоменные вызовы, выбор последующей стадии и скрытый запуск через callback/worker запрещены. Порядок источники → evidence → manifest → codec/readers сохраняется. Статус PROJECT: поведение удаления конкретизировано, общий output/errors/provenance freeze и runtime приёмка ещё не закрыты.
