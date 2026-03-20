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
        # Build file-level import DAG
        import_graph = nx.DiGraph()
        edges = store._conn.execute(
            "SELECT DISTINCT file_path, target_qualified FROM edges WHERE kind = 'IMPORTS_FROM'"
        ).fetchall()

        for e in edges:
            import_graph.add_edge(e["file_path"], e["target_qualified"])

        # Find entry points (files with no importers)
        entry_points = [
            n for n in import_graph.nodes()
            if import_graph.in_degree(n) == 0
        ]

        # Compute longest path from each entry point
        depths = {}
        for node in import_graph.nodes():
            try:
                rel = str(Path(node).relative_to(root))
            except (ValueError, TypeError):
                rel = node

            # BFS to find max depth
            max_depth = 0
            for ep in entry_points:
                try:
                    paths = list(nx.all_simple_paths(import_graph, ep, node))
                    for p in paths:
                        max_depth = max(max_depth, len(p) - 1)
                except (nx.NodeNotFound, nx.NetworkXNoPath):
                    continue

            if max_depth > 0:
                depths[rel] = max_depth

        # Sort by depth descending
        ranked = sorted(depths.items(), key=lambda x: -x[1])

        result = [{"file": f, "depth": d} for f, d in ranked[:limit]]

        max_depth = ranked[0][1] if ranked else 0

        return {
            "status": "ok",
            "summary": f"Max dependency depth: {max_depth} layers, {len(depths)} files analyzed",
            "max_depth": max_depth,
            "entry_points": len(entry_points),
            "depth_ranking": result,
        }
    finally:
        store.close()
