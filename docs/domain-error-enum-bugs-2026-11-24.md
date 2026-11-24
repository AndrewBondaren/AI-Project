# Баги типизации кодов ошибок по доменам

Дата ревью: 2026-11-24.
Основание: требование пользователя — собственные коды и категории ошибок должны быть enum в `dataModel`, а не строками или строковыми `Literal`.

Область: Patch, DAG, Lifecycle, Snapshot, Pack, Time, Physics. Выполнено статическое ревью объявлений и мест использования в рабочем дереве. Тесты не запускались; документ не является полной архитектурной приёмкой доменов.

Статус каждой находки указан в её разделе. Документ фиксирует дефекты и критерии их закрытия; не утверждает новые междоменные контракты. Изменения таких контрактов проходят установленное согласование через координатора DAG и пользователя. Реализация выполняется через `implement-plan`.

## BUG-ENUM-01 — Patch: admission-коды остаются строковыми

- Статус: **OPEN — требует исправления**.
- Источник: `backend/app/dataModel/patch/validation/admissionReasons.py`, классы `PatchSetRequestVersionUnsupported`, `PatchSetSectionKeyUnknown`, `PatchSetSectionModelMismatch`, `PatchSetSectionVersionUnsupported`.
- Дефект: поля `code` объявлены как строковые `Literal` со значениями `patch_set.admission.request_version_unsupported`, `patch_set.admission.section_key_unknown`, `patch_set.admission.section_model_mismatch`, `patch_set.admission.section_version_unsupported`.
- Производители: `backend/app/application/patch/encoding/patchSetCodec.py` и `backend/app/application/patch/registry/sectionRegistry.py` передают эти коды строковыми литералами.
- Последствие: собственный каталог admission-ошибок не представлен owning enum; последняя миграция structural errors закрыла только часть требования.
- Критерий закрытия: owning enum в `dataModel`, поля с enum или `Literal[Enum.MEMBER]`, создание и сравнение через enum; проверена совместимость сериализации и потребителей.
- Уже соответствует: `PatchSetStructuralFailure.error_type` использует `PatchSetStructuralErrorKind`.

## BUG-ENUM-02 — DAG: runtime использует открытый строковый код ошибки

- Статус: **OPEN — требует исправления**.
- Источник: `backend/app/application/engine/validation/nodeValidationError.py`, `NodeValidationError.code: str`.
- Действующие потребители/производители: `backend/app/application/engine/runtime/validation/contractValidator.py` и `backend/app/application/engine/runtime/execution/llmAggregateExecutor.py`.
- Дефект: текущий runtime создаёт собственные коды `invalid_json`, `schema_mismatch`, `missing_section` строками; `_invalid(code: str, ...)` принимает произвольную строку. Это не только неиспользуемый legacy-контракт.
- Последствие: каталог ошибок не закрыт enum и не принадлежит `dataModel`; опечатка или произвольный новый код не ограничены типом поля.
- Критерий закрытия: owning enum в `dataModel`, типизированное поле и сигнатуры производителей, сверка всех callers `NodeValidationError`. При переносе контракта сохранить используемую семантику ошибок и проверить runtime-пути.

## BUG-ENUM-03 — Lifecycle: категории отказов заданы строковыми Literal

- Статус: **FIXED — 2026-11-24**. По поручению пользователя и после PASS DAG-координатора добавлен `dataModel/lifecycle/results/refusalKind.py::LifecycleRefusalKind`; три поля/defaults используют `Literal[Enum.MEMBER]`/members. JSON-значения сохранены. Pure-отказы не входят в текущие native/terminal manifests; IDs и версии не менялись, canonical transport для pure-отказов не добавлен.
- Подтверждение: `tests/lifecycle/test_refusal_enum.py` проверяет exact enum identity defaults/Python/JSON round-trip, три ветки `Output.value`, отказ на неверную категорию и пустые issues. Полный Lifecycle unittest: **50 PASS**; `pyrightconfig.nodes.json`: **0 errors**.
- Источник: `backend/app/dataModel/lifecycle/results/errors.py`.
- Дефект: `LifecycleFieldError.kind`, `LifecycleLogicError.kind`, `LifecycleSectionRefused.kind` используют соответственно строковые `Literal["field_refusal"]`, `Literal["logic_refusal"]`, `Literal["section_refusal"]` и строковые defaults.
- Последствие: собственные категории ошибок не представлены owning enum, хотя коды вложенных issues уже типизированы enum.
- Критерий закрытия: категории объявлены enum в `dataModel`, поля и defaults используют его members; проверены потребители и сериализация отказов.

## BUG-ENUM-04 — Physics: собственные коды валидаторов передаются строками

- Статус: **OPEN — требует исправления**.
- Источники: `backend/app/dataModel/physics/settings/settingsChange.py`, `settingsCapture.py`, `worldPhysicsSettings.py`.
- Mapper: `backend/app/application/physics/settings/capture.py`, функция `validation_failure`.
- Дефект: собственные коды `physics_settings_world`, `physics_settings_schema`, `physics_settings_content`, `physics_settings_immutable` задаются строками в `PydanticCustomError` и распознаются строковыми сравнениями в mapper.
- Последствие: внутренний каталог собственных кодов не представлен enum; связь производителей и mapper поддерживается повторением строк.
- Критерий закрытия: owning enum в `dataModel`; строковое представление используется на границе Pydantic, а собственная классификация опирается на enum. Сохранены typed admission-результаты и отказ при неизвестном custom-коде.
- Уже соответствует: публичные категории admission-ошибок используют `PhysicsSettingsAdmissionKind`.

## Остальные проверенные домены

| Домен | Результат по узкому критерию ревью |
|---|---|
| Snapshot | Несоответствий собственных кодов ошибок не найдено; используются `SnapshotApplyCode`, `SnapshotMetadataCode`, `SnapshotPublicFailureKind`. |
| Pack | Несоответствий собственных кодов ошибок не найдено; используются `PackPreparationIssueCode`, `PackPreparationFailureReason`, `ManifestReadReason`. |
| Time | Несоответствий собственных кодов ошибок не найдено; используются `TimeSectionIssueCode`, `TimeUnavailableReason`, `TimeRefusalCode`. |

Внешние коды Pydantic (`ErrorType`, `float_type` и подобные), тексты сообщений и обычные идентификаторы не включены в баги этого ревью. `Literal[Enum.MEMBER]` соответствует требованию. Отсутствие находок не означает полную приёмку домена.
