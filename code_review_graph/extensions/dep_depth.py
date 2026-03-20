"""Analyze dependency depth (longest import chain)."""

EXTENSION_NAME = "dep_depth"
EXTENSION_DESCRIPTION = "Compute dependency depth — longest import chain from entry points to leaves"


def run(repo_root: str | None = None, limit: int = 20, **kwargs) -> dict:
    from ..graph import GraphStore
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path
    import networkx as nx

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Build module-to-file mapping for resolving import targets
        module_to_file: dict[str, str] = {}
        file_nodes = store._conn.execute(
            "SELECT file_path FROM nodes WHERE kind = 'File'"
        ).fetchall()
        for row in file_nodes:
            fp = row["file_path"]
            # Generate module paths from file path
            candidates = store.file_path_to_module(fp, str(root))
            for mod in candidates:
                if mod not in module_to_file:
                    module_to_file[mod] = fp

        # Build file-level import DAG (file → file)
        import_graph = nx.DiGraph()
        edges = store._conn.execute(
            "SELECT DISTINCT file_path, target_qualified FROM edges WHERE kind = 'IMPORTS_FROM'"
        ).fetchall()

        for e in edges:
            source_file = e["file_path"]
            target_mod = e["target_qualified"]
            # Resolve module target to file path
            target_file = module_to_file.get(target_mod)
            if target_file and target_file != source_file:
                import_graph.add_edge(source_file, target_file)

        if not import_graph.nodes():
            return {
                "status": "ok",
                "summary": "No import dependencies found",
                "max_depth": 0,
                "entry_points": 0,
                "depth_ranking": [],
            }

        # Use BFS from each node to compute max depth
        depths: dict[str, int] = {}
        for node in import_graph.nodes():
            # Depth = length of longest path ending at this node
            try:
                rel = str(Path(node).relative_to(root))
            except (ValueError, TypeError):
                rel = node

            # Use BFS backwards to find max depth (longest incoming path)
            max_d = 0
            visited = {node}
            frontier = [node]
            d = 0
            while frontier:
                next_f = []
                for n in frontier:
                    for pred in import_graph.predecessors(n):
                        if pred not in visited:
                            visited.add(pred)
                            next_f.append(pred)
                if next_f:
                    d += 1
                    max_d = max(max_d, d)
                frontier = next_f
                if d > 50:  # Safety cap
                    break

            if max_d > 0:
                depths[rel] = max_d

        # Sort by depth descending
        ranked = sorted(depths.items(), key=lambda x: -x[1])
        result = [{"file": f, "depth": d} for f, d in ranked[:limit]]
        max_depth = ranked[0][1] if ranked else 0

        return {
            "status": "ok",
            "summary": f"Max dependency depth: {max_depth} layers, {len(depths)} files analyzed",
            "max_depth": max_depth,
            "entry_points": len([n for n in import_graph.nodes() if import_graph.in_degree(n) == 0]),
            "depth_ranking": result,
        }
    finally:
        store.close()
