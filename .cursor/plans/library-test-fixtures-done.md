# Тестовые библиотеки пользователя и движка — DONE (2026-10-12)

Запрос мастера 2026-10-12: нужны две тестовые библиотеки.

Результат: оба `.wpack` собраны из реальных sources, 17 тел прошли domain
validation; default-статус проверен доверенной декларацией. 69 fixture/archive/
manifest/HTTP тестов прошли, включая побайтовую воспроизводимость.

- **Цель:** дать реальные переносимые `.wpack` fixtures для двух классов
  библиотек, используя существующие определения проекта как источник.
- **ТЗ:** `docs/tz_template_library_packs.md` §3–4.2 и §6;
  `world-bundle-archive-done.md` C-5 (UID-layout).
- **Файлы:** `fixtures/packs/user_library.wpack`, `engine_library.wpack`,
  `README.md`; `backend/scripts/build_library_test_fixtures.py`;
  `backend/tests/test_library_archive_fixtures.py`.
- **Контракт:** user = `user.relief.smoke_003`, 4 relief тела, не default;
  engine = `engine.structures.base`, 13 structures, существующий trusted
  default UID. Оба standalone архива `kind=library_pack`; UID и исходные
  тела не меняются. Читаемые имена не используются в archive paths.
  User означает авторскую библиотеку глобального каталога, подключаемую
  к миру явно; world-owned инстанс создаётся lifecycle-операцией.
- **Архитектура:** validated FS manifests/bodies → typed C-5 pack → общий
  archive writer → `.wpack`; read-back и domain models проверяют данные.
  Defaults читаются из доверенной декларации, не назначаются manifest.
  SQL/API/runtime не изменяются; sources не копируются в новый default.
  Сверка на реальных sources выявила уточнение C-5: kind
  `structure_templates` отображается в FS/archive root `structures_templates`.
  Mapping, transport regression и ТЗ исправляются в этом же шаге.
- **Проверка:** генератор из backend:
  `python -m scripts.build_library_test_fixtures`; затем
  `python -m unittest tests.test_library_archive_fixtures
  tests.test_bundle_library_archive`; default/user различаются правильно,
  manifests/UID/bodies совпадают с sources, сохранённые архивы воспроизводимы.
- **Done:** оба архива существуют, читаются codec, проходят domain validation;
  README содержит состав, исходники, команду пересборки и текущие точки входа.
