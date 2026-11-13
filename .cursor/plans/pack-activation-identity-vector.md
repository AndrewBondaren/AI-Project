# Pack activation — экспериментальный контрольный вектор

2026-11-13. Вычислен существующим canonical codec на существующем PackActivationInput. Временный manifest в памяти: ARTIFACT_CORE_SCHEMA + input ID 20201, revision=1 по [предложенной схеме](pack-canonical-registration-audit.md). Runtime-файлы не изменены. Это проверка предложенного identity encoding, не production registration или приёмка activate.

## Вход

```json
{
  "operation_id": "activation-vector",
  "manifest": {
    "kind": "blob",
    "format_key": "world_pack.manifest.json",
    "format_version": 1,
    "content_hash": "1111111111111111111111111111111111111111111111111111111111111111",
    "nbytes": 123,
    "row_count": null
  },
  "preparation_fingerprint": "2222222222222222222222222222222222222222222222222222222222222222",
  "expected": {
    "world_uid": "world-vector",
    "publication_id": "publication-vector",
    "pack_hash": null,
    "snapshot_head": null,
    "active_timeline_id": null,
    "gameplay_started": false
  }
}
```

Хэшируется tuple (1, OperationKind.PACK_ACTIVATION, request). Manifest ref — синтетические метаданные для codec vector; соответствующий BLOB не создавался и storage admission не проверялся. Owning storage version в текущем коде равна 1; её нельзя путать с обсуждаемой целевой версией Pack manifest. При изменении схемы/descriptor обязательна новая явная сверка vector.

## Точные bytes и digest

Length: 1028 bytes.

SHA-256: `6cbfa78133ddc85b9ec5cb2ad585232818ffa71bfed3d43f6cfc978415b34968`.

```text
0800000000000003fb020000000000000002000106000000000000002d080000000000000024020000000000000003004e2404000000000000000f7061636b5f61637469766174696f6e0700000000000003b10800000000000003a8020000000000000003004ee908000000000000039308000000000000002f04000000000000000c6f7065726174696f6e5f696404000000000000001161637469766174696f6e2d766563746f7208000000000000018f0400000000000000086d616e696665737407000000000000017508000000000000016c020000000000000003004e8b0800000000000001570800000000000000380400000000000000046b696e64060000000000000022080000000000000019020000000000000003004e23040000000000000004626c6f6208000000000000003404000000000000000a666f726d61745f6b6579040000000000000018776f726c645f7061636b2e6d616e69666573742e6a736f6e08000000000000002204000000000000000e666f726d61745f76657273696f6e020000000000000002000108000000000000005e04000000000000000c636f6e74656e745f686173680400000000000000403131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313108000000000000001a0400000000000000066e6279746573020000000000000002007b08000000000000001b040000000000000009726f775f636f756e740000000000000000000800000000000000690400000000000000177072657061726174696f6e5f66696e6765727072696e7404000000000000004032323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232080000000000000148040000000000000008657870656374656407000000000000012e080000000000000125020000000000000003004e87080000000000000110080000000000000027040000000000000009776f726c645f75696404000000000000000c776f726c642d766563746f7208000000000000003204000000000000000e7075626c69636174696f6e5f69640400000000000000127075626c69636174696f6e2d766563746f7208000000000000001b0400000000000000097061636b5f6861736800000000000000000008000000000000001f04000000000000000d736e617073686f745f686561640000000000000000000800000000000000240400000000000000126163746976655f74696d656c696e655f696400000000000000000008000000000000002304000000000000001067616d65706c61795f7374617274656401000000000000000100
```

## Проверенные изменения

Каждый вариант повторно валидирован owning POJO; encode/decode сохраняет exact PackActivationInput. Все девять digest отличаются от baseline и друг от друга.

| Изменение | SHA-256 |
|---|---|
| operation_id | `c7fdb5a97f3edcaa640c48097dd2b9a79449bc6e7e89734cde8c09539d184d2f` |
| preparation_fingerprint | `11451f540cfca8a68110283e93bc802493ba82fccfe16b6c368a6739fb13b19a` |
| manifest.content_hash | `b06e568dabbdc10d2b1ff132c501262e3e53172cb7939cbc9af6b387921f1ee1` |
| manifest.nbytes | `ce4d0252049b7385d23f89bf96bcb36aa46818e8c3888a4ed0a13469aae9eaff` |
| expected.world_uid | `77b69179095da3d2103e2313002e6bd791ca637f5941dff1b119e92c41bf2853` |
| expected.publication_id | `ac92e5645698a0daefc79a70f6214363e4ed5bc2076e9d982ddb6e6fa661bfcc` |
| expected.pack_hash | `08f42ff4453fc77bfcce40aaf846eca510c3ba9b52582e5502dc0401b11b013d` |
| expected.active_timeline_id | `c20a4f42408c24496acb50777cc6500ea4427dc2e00153e6e90d03aac1deb246` |
| expected.gameplay_started_coherent | `e145a293cd58bfb9f7f6db38d1f813dad17067317ac0324840ac2d9e2264371e` |

Значения вариантов: operation_id=activation-vector-2; preparation_fingerprint=33×32 bytes; manifest.content_hash=44×32 bytes; nbytes=124; world_uid=world-vector-2; publication_id=publication-vector-2; pack_hash=55×32 bytes; active_timeline_id=timeline-vector. Последний вариант совместно задаёт pack_hash=55×32 bytes, active_timeline_id=timeline-vector и gameplay_started=True, чтобы сохранить owning инварианты; он не доказывает независимый эффект каждого из трёх полей.

## Фактически выполненная проверка и пределы

Два отдельных Python процесса с -B: первый построил baseline и девять вариантов с round-trip; второй восстановил baseline только из приведённых bytes и проверил точное re-encode и SHA-256. Репозиторные тесты и activation pipeline не запускались; SQL/storage/lifecycle не использовались. Отсутствие collisions для этих вариантов не является доказательством полноты схемы.

Остаток: concrete diagnostic/refusal schema и durable terminal после restart. Кодов proposed PackActivationIssue ещё нет; создавать временное зеркало класса ради красивого replay-теста нельзя. Numeric IDs/revision остаются проектными до freeze/composition. Этот файл хранит воспроизводимый результат, не заявляет runtime-реализацию.

## Дополнительные проверки snapshot и forged instances

2026-11-13, отдельный in-memory Python запуск с -B. Использованы те же request/candidate и proposed schema. Во всех строках expected.pack_hash=55×32 bytes и active_timeline_id=timeline-vector; остальные baseline поля неизменны. Все четыре typed tuples прошли encode/decode.

| Вариант expected | SHA-256 |
|---|---|
| gameplay_started=False, snapshot_head=None | `46f15c25a5666d51062cc83bb40b8cfd923470f0e2e729ff75866705b6489aec` |
| Только gameplay_started=True | `e145a293cd58bfb9f7f6db38d1f813dad17067317ac0324840ac2d9e2264371e` |
| Предыдущий + WorldSnapshotRef(world-vector, timeline-vector, snapshot-vector), kind=WORLD | `b674b5b2e96f008b6740944a5f3dc39ec738171a0dbbe5ec80301ff54ac1d51d` |
| Предыдущий, только snapshot_id=snapshot-vector-2 | `bba4eee6fe6e8abcb1e8be275fd87e58470eca6702b52cdc8e8ef60d324c0402` |

Таким образом отдельно проверены эффект gameplay_started на согласованном наборе данных, добавление snapshot_head и изменение snapshot_id. Это schema-valid codec vectors, не разрешение activate после начала gameplay.

Повторная `PackActivationInput.model_validate(instance, strict=True)` отклонила семь экземпляров, созданных обходом validation через model_copy: пустой operation_id, неправильный preparation hash, bool вместо manifest.nbytes, row_count у BLOB, неподдержанную manifest storage version, snapshot другого мира, gameplay_started без active_timeline_id. Проверены именно owning validators; production PackActivationIdentityCodec ещё отсутствует. Он обязан выполнить эту проверку до digest/claim: успешное canonical encode само по себе не доказывает доменную валидность экземпляра.

Runtime-файлы, SQL и blob storage не изменялись. Проверка durable errors по-прежнему требует реальных concrete PackActivationIssue/enum и terminal composition; этот результат её не заменяет.

