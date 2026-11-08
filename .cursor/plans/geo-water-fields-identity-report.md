# S2-FOLLOWUP-ID-1 · Приёмка контракта B

Проверено 2026-11-08 в backend/.venv, Python 3.14.4, Pydantic 2.13.4. Историческое воспроизведение на 2.14.2 описано в [owning-плане](geo-water-diagnostics-source-d1.md#s2-followup-id-1--контракт-b-согласован-2026-11-08). В этом прогоне использована 2.13.4.

Fields проверяет класс до чтения module и qualname. Прямой вызов и root принимают обычную модель и именованного конкретного наследника Box[int]. Открытый Box, Box[int], посторонний класс и экземпляр отвергнуты с ModelIdentityError. Проверены отдельные отказы при выборе field owner и variant branch. from_pydantic_loc передал ошибку ветви вызывающему коду.

Оба canonical reader проверены на сохранённых парах с фактическими module и qualname каждой из 39 зарегистрированных специализаций. Для каждой пары оба вернули CanonicalEncodingError. Для четырёх исходных случаев результаты следующие.

| ID | Запись manifest | ModelIdentity.of | Обычный reader | Bounded reader |
|---:|---|---|---|---|
| 287 | PlanEnvelope[FineWaterResult], record | ModelIdentityError | CanonicalEncodingError | CanonicalEncodingError |
| 289 | PlanEnvelope[PlacementBatchResultV2], record | ModelIdentityError | CanonicalEncodingError | CanonicalEncodingError |
| 291 | PlanEnvelope[FineRiverPlan], record | ModelIdentityError | CanonicalEncodingError | CanonicalEncodingError |
| 296 | PlanEnvelope[PreparedNaturalTerrain], record | ModelIdentityError | CanonicalEncodingError | CanonicalEncodingError |

Сверены все 343 ID, типы и kind с TSV и доменными BINDINGS, включая порядок ID и тождество объектов классов в собранном manifest. Сравнение специализаций использует модуль origin, параметризованное имя и повторную подписку с фактическими аргументами.

Cold round-trip полного пути WaterBody.kind прошёл между двумя отдельными процессами. Writer создал PlanEnvelope[FineWaterResult] до импорта manifest, reader первым импортировал manifest. Восстановленный путь равен локально построенному, повторное кодирование побайтово совпало с выводом writer.

| Wire fixture | Совпало байт | output_fingerprint |
|---|---:|---|
| Water spill | 384 | abf5c963cb2260752c8afe7b193bf7630fc9672bccd7329342383d5beb102c61 |
| River refusal | 901 | 42fcbf2ba7d6a8e16bab25561c9356c53870c1d90528ad993e7d4bdef3550617 |

В Fine Water прошли проверки disposition FALLBACK, runtime-доставки WaterKindMismatchIssue, режимов validate_only и collect_only и повторного допуска опубликованного envelope. В негативном тесте чужого пути использован допустимый именованный owner WaterKindMismatchIssue, чтобы проверка по-прежнему доходила до decode.

Команды из backend, всего 64 успешных теста.

```powershell
.\.venv\Scripts\python -m unittest discover -s tests/planning/encoding/comparison -t . -v
.\.venv\Scripts\python -m unittest discover -s tests/errorContracts -t . -q
.\.venv\Scripts\python -m unittest tests.geo1.fine_water.test_kind_mismatch tests.geo1.fine_water.test_water_diagnostics -q
```
