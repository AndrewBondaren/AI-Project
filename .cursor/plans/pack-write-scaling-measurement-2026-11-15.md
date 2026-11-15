# Pack: стоимость последовательных writes — первый runtime замер

2026-11-15. Проверен существующий write_coarse_climate на настоящих owning POJO. Runtime-код/тесты не изменялись; Python запускался через stdin с -B из backend. Это частичный performance evidence, НЕ приёмка массовых writes.

## Условия

Python 3.14.4, Pydantic 2.13.4, Windows 11 build 26200; platform.processor: AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD; 16 logical CPUs. GC включён. Машина общая, фоновые процессы не изолированы.

Использован setUp из tests/spatial_pack/test_preparation_climate_write.py как источник валидного partial state/assembly/provenance. Созданы N-1 distinct fine-climate parts (gx=0..N-2, gy=0) и один coarse part последним. Все N parts — настоящие PackStoredPart. Payload bytes не загружаются; одинаковый допустимый ArtifactRef переиспользуется по разным адресам. Proof — реальный SourceDurableProof с empty uses, planning=(); это лёгкий случай, не репрезентативный тяжёлый provenance. Частичная assembly содержит одну tile row как в fixture; полнота final manifest не заявляется.

На каждом update coarse ArtifactRef.content_hash чередуется a/b: это реальная замена, не same-value no-op. Время включает constructor PackCoarseClimateInput и весь production service; подготовка N частей исключена. Во время вызова одновременно живут исходный state, request и результат; история states не удерживается. Четыре последовательных update на каждом размере: первый warm-up, три измеряемых, median/range ниже.

## Измеренные одиночные updates

| N частей | Подготовка state, s | Медиана update, s | Диапазон трёх samples, s | Экстраполяция N updates, НЕ измеренная цепочка |
|---|---:|---:|---:|---:|
| 1000 | 0.034657 | 0.0988085 | 0.096863–0.099319 | 98.8 s |
| 4000 | 0.137130 | 0.4118491 | 0.405684–0.437789 | 1647.4 s (27.5 min) |
| 16000 | 0.498771 | 1.7156631 | 1.684864–1.727746 | 27450.6 s (7.63 h) |

При росте N в 4 раза median одного update вырос в 4.17 и 4.17 раза. Конструктор request занимал примерно 0.018–0.019 / 0.075–0.087 / 0.300–0.332 s; оставшееся время — service. Экстраполяция N updates растёт примерно в 16.67 раза. Это совместимо с Θ(N²) суммарной работой, но экстраполяция не считается выполненным масштабным прогоном.

## Аллокации отдельно от timing

Отдельный процесс: тот же setup, gc.collect(), затем tracemalloc.start() непосредственно перед constructor request и одним service update. После вызова ещё живы request/result, затем tracemalloc остановлен. Timing под tracemalloc не используется.

| N | Current traced bytes | Peak traced bytes | Peak MiB |
|---|---:|---:|---:|
| 1000 | 3091079 | 7656871 | 7.30 |
| 4000 | 12127193 | 30525289 | 29.11 |
| 16000 | 48031709 | 122023988 | 116.37 |

Это новые traced Python allocations во время update, НЕ общий RSS, не размер исходного state и не гарантия верхней границы памяти production процесса. Payload/transport/heavy provenance отсутствуют.

## Полная цепочка

Контрольный прогон N=1000, 1000 последовательных реальных replacements, один повтор: **154.1134604 s**, среднее **0.15411346 s/update**. Промежуточные totals: 250 — 29.3393632 s; 500 — 71.9721272 s; 750 — 113.3348262 s. Итоговый размер и последний ArtifactRef проверены assertions, процесс завершился exit 0. Это примерно в 1.56 раза медленнее экстраполяции короткого пилота; причины расхождения отдельно не профилировались, машина не изолирована. Нельзя выдавать пилотную оценку 7.63 h за гарантированную длительность большого прогона. N=4000 и N=16000 полные цепочки не запускались из-за измеренного масштаба стоимости; плановый критерий не закрыт.

## Trace и вывод

- packPreparationService.write_coarse_climate: input strict validation → check_state_identities/check_metadata_groups → format/world/provenance checks → any по parts → новый tuple → constructor state → validate_state.
- packPreparationValidator.check_state_identities: valid_preparation_items заново валидирует каждый part, затем полный проход uniqueness и полный проход world/proof. Вызывается для входа и выхода.
- errors.valid_preparation_items: TypeAdapter.validate_python(item, strict=True) для каждого элемента; model admission и validate_immutable дополнительно обходят вложения.
- При coarse part последним поиск any и tuple replacement отдельно посещают по N элементов. Поэтому только эти два прохода для N replacements дают ровно 2N² итераций (2 млн / 32 млн / 512 млн). Это статический счётчик явных циклов, не instrumented total всех validations; остальные проходы добавляют работу.

Квадратичная нижняя граница цепочки следует из кода, реальные timings подтверждают линейную стоимость одного update по размеру state. Оптимизация поиска alone не устраняет tuple copying и full revalidation. Массовый путь нельзя считать принятым.

Не выполнены: полные серии с повторами на всех трёх размерах, instrumented полные counters, N additions разных адресов (production write этого семейства ещё отсутствует), heavy provenance, metadata describe/bind/final admission, actual DAG transport. Последнее — отдельный последний этап интеграции. Не вводились модели-заглушки, отключение validation, фиктивный successful Source API или artificial serialization.

Рекомендация для следующего решения: рассмотреть однотипный batch write с одним full admission на пакет, сохранив порядок и семантику операций у DAG. Это лишь направление для согласования, не принятый API. Инкрементальная validation потребует отдельного доказанного trust boundary и не может означать доверие forged records. Пока ни один механизм не реализован.

## Воспроизводимый timing probe

Запуск из backend: передать следующий Python в stdin .venv/Scripts/python.exe -B -u -. Это диагностический script, не production module/fixture API.

```python
import gc,json,time,statistics,platform,os
from tests.spatial_pack.test_preparation_climate_write import PreparationClimateWriteTests
from app.dataModel.worldPack.preparation.addresses import PackFineClimateAddress
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.operations import PackCoarseClimateInput
from app.dataModel.worldPack.preparation.parts import PackCoarseClimatePartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance
from app.dataModel.artifacts.references import ArtifactRef
case=PreparationClimateWriteTests(); case.setUp()
alt=PackCoarseClimatePartInput(address=case.part.address,artifact=ArtifactRef(**(case.part.artifact.model_dump()|{"content_hash":"b"*64})),provenance=case.part.provenance)
print(json.dumps({"phase":"environment","processor":platform.processor(),"logical_cpus":os.cpu_count(),"gc":gc.isenabled(),"proof":"empty same-world; partial assembly from production test fixture; no payload bytes"}),flush=True)
for n in (1000,4000,16000):
    t=time.perf_counter()
    parts=tuple(PackStoredPart(address=PackFineClimateAddress(kind="climate_fine",gx=i,gy=0),artifact=case.fine.artifact,provenance=case.fine.provenance) for i in range(n-1))
    coarse=PackStoredPart(address=case.part.address,artifact=case.part.artifact,provenance=case.part.provenance.provenance)
    state=PackPreparationState(base_publication=case.state.base_publication,parts=parts+(coarse,),assembly=case.state.assembly,assembly_provenance=(),metadata_dependencies=())
    del parts,coarse
    print(json.dumps({"phase":"setup","n":n,"seconds":time.perf_counter()-t}),flush=True)
    measurements=[]
    for i in range(4):
        t=time.perf_counter()
        request=PackCoarseClimateInput(state=state,part=alt if i%2==0 else case.part)
        middle=time.perf_counter()
        result=case.service.write_coarse_climate(request)
        end=time.perf_counter()
        assert len(result.parts)==n and result.parts[-1].artifact==request.part.artifact
        state=result
        del result,request
        row={"request_s":middle-t,"service_s":end-middle,"total_s":end-t}
        if i: measurements.append(row)
        print(json.dumps({"phase":"warmup" if i==0 else "sample","n":n,"sample":i,**row}),flush=True)
    median=statistics.median(x["total_s"] for x in measurements)
    print(json.dumps({"phase":"summary","n":n,"median_update_s":median,"extrapolated_n_updates_s":median*n,"full_chain_measured":False}),flush=True)
```

Memory probe использует тот же setup на каждом N; вместо четырёх timing samples выполняет gc.collect(); tracemalloc.start(); создание request; service update; tracemalloc.get_traced_memory(); tracemalloc.stop(). Исходный state создан до старта tracer. Контрольная полная цепочка использует тот же setup N=1000 и цикл range(N), каждый раз создаёт request, присваивает результат state и удаляет request; общий perf_counter охватывает весь цикл без setup.

