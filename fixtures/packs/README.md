# Тестовые библиотеки

Два самостоятельных архива `.wpack` (`kind=library_pack`, format_version=1).
Открываются обычным ZIP-архиватором. Внутри: корневой `bundle.manifest.json`
и `{domain_root}/{pack_uid}/{template_uid}.json` с `pack.manifest.json`
в папке пака. Имена — метаданные; идентичность — UID.

## Пользовательская — user_library.wpack

Источник: [`relief_templates/smoke_003`](../../relief_templates/smoke_003/pack.manifest.json).

- `system_name`: `user.relief.smoke_003`
- `pack_uid`: `4bddeec4-c80f-5106-a854-22724a46cf92`
- 4 шаблона: `open_land_soft`, `ravine_soft`, `road_shoulder_soft`, `shore_soft`.
- Авторская библиотека глобального каталога, не default. Подключается к миру
  явным instantiate с новым world-owned владельцем и remap по lifecycle.

## Движка — engine_library.wpack

Источник: [`structures_templates/base`](../../structures_templates/base/pack.manifest.json).

- `system_name`: `engine.structures.base`
- `pack_uid`: `ecafe65d-aa3b-5083-baee-a1c4b407551c`
- 13 шаблонов: `farm`, `library`, `livestock`, `manor_1`, `mill`, `mine`,
  `smelter`, `tavern_1`, `tavern_2`, `temple`, `theater`, `town_hall`, `workshop`.
- Штатный default движка. Статус определяется существующей доверенной
  декларацией `libraryPacks/defaults.py` по UID, а не флагом внутри архива.
  Обычная пользовательская запись этого пака запрещена существующей политикой.

## Использование и пересборка

Это переносимые тестовые данные. Codec читает оба архива через
`app.application.worldData.bundle.archive.read_archive`;
результат содержит один `library_packs` элемент с manifest и bodies по UID.
SQL/HTTP-импорт библиотечных `.wpack` подключается в 4d/L-5;
`POST /worlds/import` принимает только архив мира и отклоняет эти standalone паки.
Для существующего FS-import используются исходные папки библиотек выше.

Пересборка из корня `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_library_test_fixtures
.\.venv\Scripts\python.exe -m unittest tests.test_library_archive_fixtures tests.test_bundle_library_archive
```

Генератор проверяет FS-manifests, UID-формулы, доменные тела, default-статус
и read-back архива. Время fixture фиксировано (`2026-10-12T00:00:00Z`),
поэтому при неизменных исходниках и codec байты воспроизводимы.
SQL, исходные библиотеки и декларации defaults генератор не изменяет.
