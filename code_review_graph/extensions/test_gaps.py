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
            # Skip helper functions defined inside test files
            if "/tests/" in node.file_path or "/test_" in node.file_path:
                continue

            # Check for direct test coverage: TESTED_BY edges or CALLS from test nodes
            incoming = store.get_edges_by_target(node.qualified_name)
            directly_tested = any(
                e.kind == "TESTED_BY" or (
                    e.kind == "CALLS" and (
                        caller := store.get_node(e.source_qualified)
                    ) is not None and caller.is_test
                )
                for e in incoming
            )
            if directly_tested:
                continue

            # Check for transitive: any non-test caller is itself called by a test?
            callers = [e for e in incoming if e.kind == "CALLS"]
            transitively_tested = False
            for caller_edge in callers:
                caller_incoming = store.get_edges_by_target(caller_edge.source_qualified)
                for e in caller_incoming:
                    if e.kind == "TESTED_BY":
                        transitively_tested = True
                        break
                    if e.kind == "CALLS":
                        c = store.get_node(e.source_qualified)
                        if c and c.is_test:
                            transitively_tested = True
                            break
                if transitively_tested:
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
