def topo_sort(items: list[dict], uid_key: str, parent_key: str) -> list[dict]:
    """Return items sorted so every parent appears before its children.
    Items whose parent_key points outside the list are treated as roots.
    Cycles are broken by skipping already-in-progress nodes.
    """
    by_uid = {item[uid_key]: item for item in items}
    order: list[dict] = []
    visited: set[str] = set()
    in_progress: set[str] = set()

    def visit(uid: str) -> None:
        if uid in visited or uid in in_progress:
            return
        in_progress.add(uid)
        parent = by_uid[uid].get(parent_key)
        if parent and parent in by_uid:
            visit(parent)
        in_progress.discard(uid)
        visited.add(uid)
        order.append(by_uid[uid])

    for uid in by_uid:
        visit(uid)
    return order
