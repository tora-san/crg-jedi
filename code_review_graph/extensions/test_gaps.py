"""Find functions missing test coverage."""

EXTENSION_NAME = "test_gaps"
EXTENSION_DESCRIPTION = "Find functions with no TESTED_BY edges and no transitive test coverage"


def run(repo_root: str | None = None, min_lines: int = 3, **kwargs) -> dict:
    from ..graph import GraphStore, node_to_dict
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Get all non-test functions
        rows = store._conn.execute(
            "SELECT * FROM nodes WHERE kind = 'Function' AND is_test = 0"
        ).fetchall()

        untested = []
        for r in rows:
            node = store._row_to_node(r)
            # Skip small helpers
            if (node.line_end - node.line_start) < min_lines:
                continue
            # Skip __init__ and dunder methods
            if node.name.startswith("__") and node.name.endswith("__"):
                continue

            # Check for direct TESTED_BY
            tested_edges = [
                e for e in store.get_edges_by_target(node.qualified_name)
                if e.kind == "TESTED_BY"
            ]
            if tested_edges:
                continue

            # Check for transitive: any caller has TESTED_BY?
            callers = [
                e for e in store.get_edges_by_target(node.qualified_name)
                if e.kind == "CALLS"
            ]
            transitively_tested = False
            for caller_edge in callers:
                caller_tests = [
                    e for e in store.get_edges_by_target(caller_edge.source_qualified)
                    if e.kind == "TESTED_BY"
                ]
                if caller_tests:
                    transitively_tested = True
                    break

            if not transitively_tested:
                # Calculate fan-in for priority ranking
                fan_in = len([
                    e for e in store.get_edges_by_target(node.qualified_name)
                    if e.kind == "CALLS"
                ])
                d = node_to_dict(node)
                d["fan_in"] = fan_in
                d["lines"] = node.line_end - node.line_start
                untested.append(d)

        # Sort by fan_in descending (high fan-in = highest priority)
        untested.sort(key=lambda d: -d["fan_in"])

        return {
            "status": "ok",
            "summary": f"Found {len(untested)} untested functions",
            "untested_functions": untested[:100],
        }
    finally:
        store.close()
