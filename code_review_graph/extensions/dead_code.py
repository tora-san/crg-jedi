"""Find functions with no callers (potential dead code)."""

EXTENSION_NAME = "dead_code"
EXTENSION_DESCRIPTION = "Find functions with no incoming CALLS edges (potential dead code)"


def run(repo_root: str | None = None, **kwargs) -> dict:
    from ..graph import GraphStore, node_to_dict
    from ..incremental import find_project_root, get_db_path

    root = find_project_root() if not repo_root else __import__("pathlib").Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Entry points and special functions to exclude
        _EXCLUDE_NAMES = {
            "main", "__init__", "__new__", "__del__", "__enter__", "__exit__",
            "__str__", "__repr__", "__hash__", "__eq__", "__lt__", "__gt__",
            "__len__", "__getitem__", "__setitem__", "__contains__", "__iter__",
            "__next__", "__call__", "__bool__", "__aenter__", "__aexit__",
            "__aiter__", "__anext__", "setup", "teardown",
        }

        # Get all functions
        all_functions = []
        rows = store._conn.execute(
            "SELECT * FROM nodes WHERE kind IN ('Function', 'Test')"
        ).fetchall()
        for r in rows:
            node = store._row_to_node(r)
            all_functions.append(node)

        # Find functions with no incoming CALLS
        dead = []
        for func in all_functions:
            if func.is_test:
                continue
            if func.name in _EXCLUDE_NAMES:
                continue
            if func.name.startswith("_") and func.name.startswith("__"):
                continue  # dunder methods

            callers = store.get_edges_by_target(func.qualified_name)
            has_caller = any(e.kind == "CALLS" for e in callers)
            if not has_caller:
                dead.append(func)

        # Sort by file path for readability
        dead.sort(key=lambda n: (n.file_path, n.line_start))

        return {
            "status": "ok",
            "summary": f"Found {len(dead)} potentially dead functions (no callers)",
            "total_functions": len(all_functions),
            "dead_functions": [node_to_dict(n) for n in dead[:100]],
        }
    finally:
        store.close()
