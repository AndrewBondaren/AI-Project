"""Existing pack key conventions, shared by inspection and remap (TZ §2)."""

PACK_NAME_SEPARATOR = "."


def instance_system_name(world_uid: str, source_system_name: str) -> str:
    return PACK_NAME_SEPARATOR.join(
        ("world", str(world_uid), "instance", source_system_name)
    )


def published_system_name(source_system_name: str) -> str:
    return f"{source_system_name}{PACK_NAME_SEPARATOR}published"
