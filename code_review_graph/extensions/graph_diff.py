"""Diff the code graph between two git refs."""

EXTENSION_NAME = "graph_diff"
EXTENSION_DESCRIPTION = "Compare graph structure between two git refs (e.g., main vs HEAD)"


def run(
    base: str = "main",
    head: str = "HEAD",
    repo_root: str | None = None,
    **kwargs,
) -> dict:
    from ..graph import GraphStore
    from ..incremental import find_project_root, get_db_path, get_changed_files
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        import subprocess
        # Get files changed between base and head
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...{head}"],
                capture_output=True, text=True, cwd=str(root), timeout=30,
            )
            changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            changed_files = get_changed_files(root, base)

        if not changed_files:
            return {
                "status": "ok",
                "summary": f"No files changed between {base} and {head}",
                "added": [], "removed": [], "modified": [],
            }

        # Get current graph state for changed files
        current_nodes = {}
        current_edges = {}
        for rel_path in changed_files:
            abs_path = str(root / rel_path)
            for node in store.get_nodes_by_file(abs_path):
                if node.kind != "File":
                    current_nodes[node.qualified_name] = {
                        "name": node.name,
                        "kind": node.kind,
                        "file": rel_path,
                        "line": node.line_start,
                        "params": node.params,
                    }
            for edge in store.get_edges_by_source(abs_path):
                key = (edge.kind, edge.source_qualified, edge.target_qualified)
                current_edges[key] = edge

        return {
            "status": "ok",
            "summary": (
                f"{len(changed_files)} files changed between {base} and {head}, "
                f"{len(current_nodes)} nodes in changed files"
            ),
            "changed_files": changed_files,
            "nodes_in_changed_files": list(current_nodes.values())[:100],
            "note": "Full diff requires building graphs at both refs (not yet implemented)",
        }
    finally:
        store.close()
