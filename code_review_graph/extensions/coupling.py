"""Calculate coupling metrics (fan-in, fan-out, instability)."""

EXTENSION_NAME = "coupling"
EXTENSION_DESCRIPTION = "Get fan-in/fan-out coupling metrics for functions and classes"


def run(repo_root: str | None = None, limit: int = 50, **kwargs) -> dict:
    from ..graph import GraphStore, node_to_dict
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        rows = store._conn.execute(
            "SELECT * FROM nodes WHERE kind IN ('Function', 'Class')"
        ).fetchall()

        metrics = []
        for r in rows:
            node = store._row_to_node(r)
            if node.is_test:
                continue

            fan_in = len([
                e for e in store.get_edges_by_target(node.qualified_name)
                if e.kind == "CALLS"
            ])
            fan_out = len([
                e for e in store.get_edges_by_source(node.qualified_name)
                if e.kind == "CALLS"
            ])

            total = fan_in + fan_out
            instability = fan_out / total if total > 0 else 0.0

            if total > 0:
                metrics.append({
                    **node_to_dict(node),
                    "fan_in": fan_in,
                    "fan_out": fan_out,
                    "instability": round(instability, 3),
                    "coupling_score": fan_in * fan_out,
                })

        metrics.sort(key=lambda m: -m["coupling_score"])

        return {
            "status": "ok",
            "summary": f"Coupling metrics for {len(metrics)} functions/classes",
            "metrics": metrics[:limit],
        }
    finally:
        store.close()
