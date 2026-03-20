"""Detect the public API surface of modules."""

EXTENSION_NAME = "api_surface"
EXTENSION_DESCRIPTION = "Find public functions/classes imported by other modules (the public interface)"


def run(repo_root: str | None = None, file_path: str | None = None, **kwargs) -> dict:
    from ..graph import GraphStore, node_to_dict
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        target_files = []
        if file_path:
            target_files = [str(root / file_path)]
        else:
            target_files = store.get_all_files()

        api_surface = []
        for fp in target_files:
            nodes = store.get_nodes_by_file(fp)
            for node in nodes:
                if node.kind not in ("Function", "Class"):
                    continue
                if node.name.startswith("_"):
                    continue  # private
                if node.is_test:
                    continue

                # Check if imported by other modules
                importers = [
                    e for e in store.get_edges_by_target(node.qualified_name)
                    if e.kind == "IMPORTS_FROM" and e.file_path != fp
                ]
                # Also check CALLS from other files
                external_callers = [
                    e for e in store.get_edges_by_target(node.qualified_name)
                    if e.kind == "CALLS" and e.file_path != fp
                ]

                if importers or external_callers:
                    try:
                        rel = str(Path(fp).relative_to(root))
                    except ValueError:
                        rel = fp
                    d = node_to_dict(node)
                    d["file"] = rel
                    d["importer_count"] = len(importers)
                    d["external_caller_count"] = len(external_callers)
                    api_surface.append(d)

        api_surface.sort(key=lambda a: -(a["importer_count"] + a["external_caller_count"]))

        return {
            "status": "ok",
            "summary": f"Found {len(api_surface)} public API entries",
            "api_surface": api_surface[:100],
        }
    finally:
        store.close()
