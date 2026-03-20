"""Detect circular dependencies in the import graph."""

EXTENSION_NAME = "cycles"
EXTENSION_DESCRIPTION = "Find circular import dependencies using NetworkX cycle detection"


def run(repo_root: str | None = None, max_cycles: int = 20, **kwargs) -> dict:
    from ..graph import GraphStore
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path
    import networkx as nx

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Build a file-level import graph
        import_graph = nx.DiGraph()
        edges = store._conn.execute(
            "SELECT * FROM edges WHERE kind = 'IMPORTS_FROM'"
        ).fetchall()

        for e in edges:
            source_file = e["file_path"]
            # Target could be a module path - try to resolve to file
            import_graph.add_edge(source_file, e["target_qualified"])

        # Find cycles
        cycles = []
        try:
            for cycle in nx.simple_cycles(import_graph):
                if len(cycle) >= 2:
                    # Simplify paths for readability
                    simplified = []
                    for p in cycle:
                        if str(root) in p:
                            p = p.replace(str(root) + "/", "")
                        simplified.append(p)
                    cycles.append(simplified)
                    if len(cycles) >= max_cycles:
                        break
        except nx.NetworkXError:
            pass

        return {
            "status": "ok",
            "summary": f"Found {len(cycles)} circular dependency cycle(s)",
            "cycles": cycles,
        }
    finally:
        store.close()
