"""Domain-independent structural diff of already prepared bodies."""
from app.application.worldData.libraryPacks.lifecycleContracts import FieldChange


def body_diff(before, after, path=()) -> tuple[FieldChange, ...]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                changes.append(FieldChange(path + (key,), before.get(key), after.get(key),
                                           key in before, key in after))
            else:
                changes.extend(body_diff(before[key], after[key], path + (key,)))
        return tuple(changes)
    if before == after:
        return ()
    return (FieldChange(path, before, after),)
