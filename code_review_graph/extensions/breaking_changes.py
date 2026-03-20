"""Detect function signature changes that may break callers."""

EXTENSION_NAME = "breaking_changes"
EXTENSION_DESCRIPTION = "Find changed function signatures and flag callers that may need updating"


def run(
    base: str = "HEAD~1",
    repo_root: str | None = None,
    **kwargs,
) -> dict:
    from ..graph import GraphStore, node_to_dict
    from ..incremental import find_project_root, get_db_path, get_changed_files
    from ..parser import CodeParser
    from pathlib import Path
    import subprocess

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Get current function signatures from the graph
        changed_files = get_changed_files(root, base)
        if not changed_files:
            return {"status": "ok", "summary": "No changed files", "breaking_changes": []}

        breaking = []
        for rel_path in changed_files:
            abs_path = str(root / rel_path)
            nodes = store.get_nodes_by_file(abs_path)

            for node in nodes:
                if node.kind != "Function":
                    continue

                # Get the old version of this function's params from git
                try:
                    old_source = subprocess.run(
                        ["git", "show", f"{base}:{rel_path}"],
                        capture_output=True, text=True, cwd=str(root), timeout=10,
                    )
                    if old_source.returncode != 0:
                        continue
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue

                # Parse old source to find old params
                parser = CodeParser()
                old_nodes, _ = parser.parse_bytes(
                    Path(abs_path), old_source.stdout.encode()
                )

                old_func = None
                for on in old_nodes:
                    if on.name == node.name and on.kind in ("Function", "Test"):
                        old_func = on
                        break

                if old_func and old_func.params != node.params:
                    # Signature changed! Find callers
                    callers = [
                        e for e in store.get_edges_by_target(node.qualified_name)
                        if e.kind == "CALLS"
                    ]
                    caller_nodes = []
                    for c in callers:
                        cn = store.get_node(c.source_qualified)
                        if cn:
                            caller_nodes.append(node_to_dict(cn))

                    breaking.append({
                        "function": node.name,
                        "file": rel_path,
                        "old_params": old_func.params,
                        "new_params": node.params,
                        "caller_count": len(caller_nodes),
                        "callers": caller_nodes[:10],
                    })

        return {
            "status": "ok",
            "summary": f"Found {len(breaking)} function(s) with changed signatures",
            "breaking_changes": breaking,
        }
    finally:
        store.close()
