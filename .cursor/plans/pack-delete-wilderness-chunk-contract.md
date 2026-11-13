# Pack — согласованное удаление wilderness chunk

2026-11-12. PROJECT после статического trace; runtime, SQL и DAG не менялись, тесты не запускались. Дополняет [delete_part](pack-delete-part-contract.md) и [write-план](pack-v2-public-write-operations.md). Это проект новой операции: legacy writer не содержит удаления chunk.

## Что доказано кодом

[WorldPackWriter.commit_chunk](../../backend/app/application/worldData/pack/io/worldPackWriter.py) заменяет chunk по cx/cy внутри gx/gy и вызывает provisional пересчёт без expected. `recalc_wilderness_status` использует единую [policy](../../backend/app/dataModel/worldPack/bake/wildernessRefineStatus.py): без expected ноль chunks → absent, положительное число → partial. С expected: baked<=0 → absent; expected>0 и baked>=expected → complete; иначе partial. Отрицательный/нулевой expected не получает новый запрет в рамках этого среза.

Предложение для удаления переиспользует эти pure функции, но не утверждает, что такое удаление уже реализовано. Нельзя выводить прежний expected из слова complete, общего числа частей или размеров сетки. Final coverage и видимый status остаются разными проверками.

## Конкретная операция

### Повторная проверка status и coverage по actual callers

Выполнен in-memory вызов существующих pure функций `wildernessRefineStatus.py` через backend/.venv Python с `-B`, без изменения runtime/fixtures. Результаты `(baked, expected)`: `(0,0)` и `(0,4)` → absent; `(2,-1)`, `(2,0)`, `(2,3)` → partial; `(2,2)` и `(3,2)` → complete. Без expected: 0 → absent, 1/3 → partial. Это проверка policy, не интеграционный тест подготовки Pack.

В [detailedBakeScope](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py) location route устанавливает `expected_chunks_for_status=None`, wilderness route предоставляет вычисление полного expected для tile. [detailedBakeRefine](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py) вызывает writer.recalc_wilderness_status только при наличии этого значения, после обработки соответствующего tile. Callback остаётся деталью legacy orchestration; target Pack input получает уже materialized expected_chunks через DAG, не callback/World/planner.

Следствия для сохранения поведения:

- Даже замена существующего chunk с прежним числом chunks вызывает provisional пересчёт без expected; прежний complete не сохраняется автоматически. Для положительного числа chunks результат partial, пока DAG явно не выполнит согласованный recalculate.
- Location scope не получает автоматически полный expected tile из геометрии внутри Pack. Отсутствие финального recalculate не исправляется prepare/assembler.
- complete при baked>expected допускается существующей status policy. Это не разрешение лишнего адреса: scope и принадлежность outputs проверяются независимо. Не менять >= на == ради проверки coverage.
- Равные counts при разных logical addresses не доказывают корректность expected/completed. [Локальная coverage-проверка](pack-v2-public-write-operations.md) уже различает адресные множества и materialized/without-payload outputs; она не вычисляет видимый status и не требует безусловного completed=expected во всех scopes.
- Из complete нельзя восстановить прежний expected; delete chunk использует согласованный provisional переход и не придумывает новый census. Новый запрет expected<=0 не вводится.

Нового решения о status policy не требуется. При реализации сохранить порядок write chunk → provisional status → отдельный recalculate только по вызову DAG, а final coverage выполнять без мутации status. Нужны integration проверки этих маршрутов и доказательств metadata; pure probe выше их не заменяет.

Класс: проектный `PackPreparationService`, `backend/app/application/worldData/pack/preparation/packPreparationService.py`.

`def delete_wilderness_chunk(self, request: PackDeleteWildernessChunkInput) -> PackPreparationState`

Input в `backend/app/dataModel/worldPack/preparation/operations.py`: `state: PackPreparationState`, `address: PackChunkAddress` из preparation/addresses.py. Address уже содержит gx/gy/cx/cy; world, координаты, ref и refine_role не дублируются. Expected_chunks и новый готовый статус не принимаются. Strict/frozen/extra=forbid, повторная проверка nested instances обязательна.

Результат — общий проект PackPreparationState, без второго DeleteChunkState/receipt. Формат результата должен поддержать уже принятое направление metadata subject/dependencies → DAG → evidence → Pack bind. Пока общий representation этой связи не завершён, указанная сигнатура — проект, не утверждение готовности runtime DTO. Не вводить локальный обход в виде optional proof или зеркального subject только для удаления.

Ошибки переиспользуют PackPreparationError/PackPreparationIssue в `dataModel/worldPack/preparation/errors.py`, PackPreparationFailure в `application/worldData/pack/preparation/errors.py` и общую structural diagnostics схему write-плана. Дубликаты адресов — DUPLICATE_ADDRESS; scope нарушения проверяет final prepare как OUT_OF_SCOPE_CHANGE. Новый набор delete-errors не требуется.

## Один pure переход state

1. Проверить request и структурные инварианты state. Дубликаты и невалидные owning records не исправляются молча. Вход — промежуточный state по общему контракту, а не уже опубликованный manifest.
2. Найти part wilderness_chunk(gx,gy,cx,cy) и соответствующую chunk metadata в выбранном tile. Если отсутствуют оба, вернуть неизменный state после проверки: не создавать tile и не понижать чужой status. Это предложенная idempotent policy, не найденный legacy delete.
3. Если присутствует хотя бы один из двух элементов, исключить адресованный part с его payload provenance и соответствующую chunk metadata с её отдельным assembly proof. Это допускает завершение промежуточного состояния после delete_part; не разрешает скрыто исправлять остальные несоответствия версии.
4. Если tile существует, сохранить его запись, map_tile, climate, остальные chunks и прочие поля. Вычислить wilderness status pure функцией wilderness_refine_status_without_expected по числу оставшихся chunk metadata. Даже последний chunk не удаляет tile. Если tile отсутствует и был только payload, удалить payload без создания tile. Полнота оставшихся metadata↔parts проверяется final admission.
5. Сохранить все независимые parts/assembly/provenance. Подготовить связь изменённой tile projection с использованным прежним state, адресом удаления и оставшимся составом chunks по общей принятой модели metadata outputs. Вернуть новый immutable state; input не мутирует.

Вызов общего pure helper policy внутри одной операции допустим. Вызов публичных delete_part или recalculate_wilderness_status из этого метода не допускается: implementation выполняет одно изменение напрямую через внутренние helpers. Следующий самостоятельный пересчёт с expected, если нужен, выбирает DAG отдельным вызовом существующего проекта recalculate_wilderness_status; операция удаления не запускает его скрыто.

## Provenance и финальное состояние

Chunk proof удаляется вместе с исчезнувшей metadata projection: в итоговом manifest не остаётся orphan proof. Payload proof удаляется вместе с частью; его source artifacts физически не освобождаются этой pure операцией.

Tile proof нельзя автоматически унаследовать после изменения набора chunks только потому, что результат partial→partial совпал по значению: изменились использованные входы расчёта. Сохранность/повторное использование допускается лишь при проверенной semantic identity и dependencies по общему metadata binding. Операция не делает Source-вызов и не выдаёт старое свидетельство за новое. Неизменные unrelated tile/header/location proofs сохраняются.

Промежуточный результат передаётся по принятому пути metadata subject → DAG → evidence → отдельный Pack bind. Точное представление pending linkage остаётся общим незавершённым контрактом write-плана; этот документ его не подменяет. PACK-METADATA-PLANNING сохраняет разрешённую отсрочку и не объявляется новым блокером текущего Pack. Конкретное source evidence не выдумывается.

Final prepare проверяет разрешение изменения scope, точное соответствие оставшихся chunks и parts, metadata/provenance completeness и полный closure. Wilderness_chunks_baked вычисляется по окончательным уникальным адресам; ручной decrement в delete не вводится. Old pin/manifest неизменяемы. Shared blob или shard сохраняется, если достижим из другого адреса, provenance либо другой удерживаемой версии. Ни release, ни GC в delete_wilderness_chunk нет.

## Критерии приёмки

- Один chunk из complete tile удалён: оставшиеся chunks сохранены, provisional status partial; complete не восстанавливается без явного expected-вызова DAG.
- Удалён последний chunk: status absent, сам tile/map_tile/climate сохранены.
- Отсутствуют part и metadata: no-op без создания tile и изменения status/proofs.
- Только part либо только metadata в допустимом промежуточном state: адресованный остаток удалён; остальные повреждения не скрыты и не проходят final admission.
- Same ref у двух chunk addresses: исчез только запрошенный адрес; blob не удалён.
- Partial→partial после удаления: прежний tile proof не признаётся подходящим только по равенству status.
- Старый pin продолжает читать прежний chunk; input state неизменен; нет I/O, generator calls, публичных вложенных write/recalc или изменения head.
- Missing final metadata evidence, удаление вне scope и dangling оставшаяся metadata не дают READY.

Ответственность: Input — typed boundary; PackPreparationService — один pure переход; PackPreparationValidator — локальная структура и отдельно final связи; PackPreparationOperation — verified lifecycle/closure; assembler — только конечный manifest. Порядок источники → evidence → manifest → codec/readers и прежние DAG-последовательности не меняются. Статус: локальная семантика удаления конкретизирована; общий output/provenance/errors freeze и сквозная приёмка ещё OPEN.
