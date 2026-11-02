# GEN-BAKE-READ — шпаргалка агента

Основание: прямые уточнения пользователя 2026-11-02. Перед дальнейшим
проектированием GEN-BAKE-READ перечитать этот файл. Это памятка принятых границ,
не новый архитектурный план и не приёмка полного contract freeze.

## Существующие операции — не переизобретать

- light_bake: L0 tiles static location anchors ∪ endpoints declared hydrology
  (при включённой hydrology). Ограниченное покрытие намеренно оптимизирует работу.
  Не расширять до territories, всех segment tiles или water interiors под видом
  уточнения completeness. Positive tile cap — debug, product default uncapped.
- full_bake: тот же L0 pipeline на всех macro tiles world_bounds/resolved AABB;
  full path обрабатывает world seam. Это другая семантика, не синоним light.
- detailed_bake: existing scopes location/wilderness, L2 refinement с обязательным
  parent L0. Location — territory/rects, wilderness — existing tile selection.
  Не вводить новый bake kind для wilderness или coordinates.
- World/request scope — параметры чтения, не новые bake-сущности.
- Семантику уточнять по реализации и callers. Не менять её из-за собственного
  представления о том, какое покрытие было бы «полнее».

Источники: pack/bake/plan/packTileCollect.py, packTilePlanner.py;
pack/bake/l0/packMaterializationOrchestrator.py, worldMapBakeOrchestrator.py;
pack/bake/detailed/detailedBakeScope.py, detailedBakeRefine.py;
dataModel/worldPack/bake/detailedBakeScope.py, packBakeMode.py (от backend/app/).

## Граница домен / DAG — решение пользователя

- Публичные методы в доменах; переиспользуемые публичные read-ноды в DAG.
- Другие ноды вызывают read-ноды через engine CALL/RETURN. В большом DAG должно
  быть видно, что, где и когда вызывается. Не прямой чужой execute().
- Не скрывать композицию самостоятельных domain reads в facade/helper.
  Внутренний blob decode при этом не требует отдельной ноды.
- SQL/files/manifest/storage readers остаются внутри доменов. Нода получает typed
  data/verified refs/missing/errors и не собирает результат из storage internals.
- Не добавлять NodeIds, parents, CALL edges и bindings без отдельного согласования.
- PackFullBakeReader с вложенными light+C23 отозван. Full-check композиция reads
  должна быть видимой; exact bindings ещё OPEN.

## Не смешивать evidence

- Consumer full-check L0+C23 не означает, что body L0 full producer строит C23.
- L2 terrain found не доказывает готовность применимого C11.
- Bake completeness не Spatial wet/dry/unknown. L0 не canonical water source.
- Read не вызывает preparation/compute/write/repair. Error не превращать в missing.
- World completeness не блокирует scoped NamedLocation read.
- Coordinates/wilderness не fake NamedLocation. Отдельный read_wilderness_l2
  не принят: имя было предложено и отозвано как выбранное решение.
- SP-1/GEO EF-1 приняты в записанном scope; SP-P0 целиком/SP-M не приняты.
  Snapshot draft adapters не готовые pin/read ports.

## Статусы и работа с документами

Owning: generator-public-bake-reads.md §§13–14; registry: generator_public_method.md.
Первоначальные proposals в owning §§5–12 не все актуальны: сверять отмены §§13–14.
Принятие отдельного архитектурного принципа не означает приёмку всего freeze.
Новые классы/POJO/ports не создавать до проверки reuse и явной приёмки.
Код, публикация и cutover не разрешены документальным треком.
Другие owning-планы, GEN-DAG и общий граф здесь не менять.

Ошибка агента: расширение light coverage и скрытая full-композиция были предложены
без достаточного основания. Не повторять эти предложения как действующие решения.

## Принято: reader каждого домена

Пользователь принял: domain-owned reader возвращает typed contracts на уровнях
целая сущность → часть/окно → минимальная доменная единица. Whole entity может
быть metadata+refs, дочитываемыми в той же revision. Не навязывать универсальный
DTO/CRUD API. Consumers CALL публичные read-ноды через engine, без hidden read
composition и без storage в ноде. Не каждому внутреннему read методу нужна нода.
До concrete class/file map исследовать existing entities/reuse/contracts.
Owning §15; CRUD evidence — generator-domain-crud-inventory.md. CRUD-метод,
generate/compute и read — разные операции; название get/read не доказывает read-only.
