"""Owning codes for PatchSet compatibility admission facts."""
from enum import StrEnum


class PatchSetAdmissionCode(StrEnum):
    REQUEST_VERSION_UNSUPPORTED = "patch_set.admission.request_version_unsupported"
    SECTION_KEY_UNKNOWN = "patch_set.admission.section_key_unknown"
    SECTION_MODEL_MISMATCH = "patch_set.admission.section_model_mismatch"
    SECTION_VERSION_UNSUPPORTED = "patch_set.admission.section_version_unsupported"
