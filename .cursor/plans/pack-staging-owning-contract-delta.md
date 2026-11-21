# Pack owning delta: staging / completion cutover

2026-11-21. Документальный пакет для координатора. Направление public Artifacts staging → public Publication completion принято; exact Pack split ниже PROPOSED. Runtime не принят. Общая карта pack-staging-completion-cutover.md не изменяется; input preparation, реальные producers, write_changes и новые NodeIds вне scope.

## Inventory helper

Статический поиск finish_pack_preparation по backend Python-файлам:

- application/worldData/pack/encoding/preparedManifest.py: определение; production callers не найдены. Это результат статического поиска, не доказательство отсутствия динамических вызовов.
- tests/spatial_pack/test_manifest_format.py: один call site (строка 38).
- tests/spatial_pack/test_climate_field_format.py: два call sites (95, 98), отрицательные и успешный сценарии с StagedClimateFields.
- tests/spatial_pack/test_execution_pins.py: один call site (86), подготовка fixture pinned reads.

Existing helper: encode_candidate_manifest → optional climate_fields.validate → manifest_stager.stage → descriptor size/digest checks → staging.finish_preparation → READY/world/kind/fence/operation/fingerprint/exact set checks → PreparedPackCandidate. other_members/spatial_roots/climate refs не доказывают полноту нового authoritative closure. Helper и старый фасад сохраняются до переноса всех его consumers; тестовый helper не доказательство production target wiring. При cutover повторить полный поиск imports/aliases/composition и проверить production-подключение новой цепочки отдельно.

## Единственная целевая граница

Прежний проект PackPreparationOperation.prepare со staging/finish внутри отозван как target. Его local semantic checks/assembly/encoding остаются Pack-owned и переносятся в producer/consumer ниже. Имена старого wrapper/operation не сохраняют право на вызов чужих публичных операций. Existing helper остаётся только existing до cutover, не вторым target. Publication владеет completion UOW, authoritative protection admission и persisted candidate/replay; Pack не делает собственный finish либо подтверждение commit по произвольному OperationRecord. Основание: publication-preparation-completion-contract.md.

## Точные Pack declarations — предложение, не freeze

Public class PackManifestPreparationOpenPipeline, application/worldData/pack/preparation/packManifestPreparationOpenPipeline.py; interface IPackManifestPreparationOpenPipeline в application/worldData/pack/contracts/packManifestPreparationOpenPipeline.py. Методы pure, без IO/callbacks/backends:

```python
def prepare_material(self, request: PackPreparationInput) -> PackManifestMaterial: ...
def admit_staged(self, request: PackStagedManifestInput) -> PackStagedManifest: ...
```

Named records в dataModel/worldPack/preparation/manifestMaterial.py, strict/frozen/extra-forbid:

- PackManifestMaterial(request: PackPreparationInput, content: bytes).
- PackStagedManifestInput(material: PackManifestMaterial, lease: OperationLeaseRef, artifact: ArtifactRef).
- PackStagedManifest(material: PackManifestMaterial, artifact: ArtifactRef).

PackPreparationInput(operation_id, preparation_fingerprint, body) и body(state, capture, scope) — проект существующего write-контракта, не новый mirror. Его полный concrete readiness/evidence admission не доказан данным пакетом; соответствующий стык OPEN. Producer не принимает неподтверждённый body как заведомо semantic-ready. Material не capability и не persisted manifest. Повторная проверка forged records обязательна; один origin request удерживает identity, новые дубли world/fingerprint не вводятся.

Producer валидирует конечный состав и доступные semantic evidence, строит manifest и canonical bytes под trusted budget. Consumer повторно проверяет material, kind/key/version binding, nbytes и content hash artifact. Lease operation/world/preparation должны совпасть с исходным request. Fence не включается в semantic fingerprint; pure consumer не подтверждает актуальность fence, writable lease, seal или holds. Эти изменяемые условия authoritative-проверяет владелец lifecycle. Operation ID producer и authoritative preparation fingerprint producer остаются X-ID, не назначаются Publication только потому, что он выдаёт lease.

Ошибки Pack: existing PackPreparationFailure(error: PackPreparationError), reason/typed issues по owning errors. Descriptor mismatch, request/lease identity mismatch, malformed input и budgets должны получить точные paths/codes до freeze; исчерпывающий mapping пока OPEN, новых generic exceptions не вводится. Infrastructure/Artifacts/Publication ошибки проходят по owning контрактам, не становятся INVALID_INPUT. Pure retry детерминирован по исходному immutable request; никаких storage effects и cleanup в этих методах нет.

## Output → Input и closure

1. material.content передаётся в ArtifactPrepareStageInput[bytes].content. PreparedArtifact[bytes] без замены content вместе с issued lease передаётся ArtifactStageInput(lease, prepared).
2. ArtifactRef результата stage вместе с тем же material и lease поступает PackStagedManifestInput. Успешный PackStagedManifest подтверждает только локальное соответствие, не READY.
3. Publication completion получает через согласованный owning input semantic binding Pack, точный manifest ref, полный target set и authoritative protection inputs. Exact названия/типы полей completion предъявляет Publication; этот документ не объявляет чужую сигнатуру.
4. Полный target set: manifest ref + refs итоговых parts + зарегистрированный transitive payload closure + durable Source refs всех parts/metadata. Pack проверяет coverage своего состава; Source даёт semantic closure через DAG; Artifacts/Publication подтверждают protection. Material/request не заменяют эти foreign results; вычислять closure в DAG или скрыто вызывать Source из Publication запрещено. Exact closure evidence input и его связывание с material — OPEN, не заполнено tuple произвольных refs.

Нельзя выдавать candidate после admit_staged. Рекомендованный целевой disposition: Publication после confirmed outer commit возвращает existing PreparedPackCandidate(operation_id, manifest, preparation_fingerprint) в owning completion result; pending внутреннее значение до commit не имеет публичной семантики готовности. Этот consumer/result mapping требует подтверждения Publication. Нового mirror candidate или дополнительного Pack confirm pipeline не предлагается. Exact replay использует persisted candidate, не rebuild/re-stage; различающийся manifest/set конфликтует. После cancel/release/publication replay не возобновляет подготовку. Unknown outcome сохраняет owning carrier, требует reconciliation до cleanup.

## Gates и остаток

- Publication должен подтвердить exact public IO/Error, выдачу existing candidate после commit, protection authority, full set admission и durable replay. Сигнатуры не выдумываются.
- Pack: final request readiness, concrete semantic evidence/closure mapping и исчерпывающие issue paths/codes до приёмки producer/consumer.
- Координатор: замкнуть lease/material/closure/candidate цепочку, X-ID и неизменность утверждённого порядка; затем решение пользователя. До этого proposal не code-go.
- После реализации owning contracts перенести четыре test call sites с сохранением негативных/ref/READY/pinned checks; предъявить реальные production callers целевого маршрута. Проверить wrong material/ref/fence, missing/extra closure, rollback, cancel, lost ACK и replay. Только после consumer cutover удалить helper/старый фасад в отдельном legacy-шаге.

Статическая сверка выполнена; runtime tests не запускались, код не менялся. Самостоятельный staging-срез не ждёт полного Pack completion, но полный Pack-маршрут без этих gates не объявляется готовым.
