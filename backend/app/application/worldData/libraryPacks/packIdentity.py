"""Existing pack key conventions, shared by inspection and remap (TZ §2)."""


def instance_system_name(world_uid: str, source_system_name: str) -> str:
    return f"world.{world_uid}.instance.{source_system_name}"


def published_system_name(source_system_name: str) -> str:
    return f"{source_system_name}.published"
