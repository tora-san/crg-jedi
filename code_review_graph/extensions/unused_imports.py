"""Find unused imports in the codebase."""

EXTENSION_NAME = "unused_imports"
EXTENSION_DESCRIPTION = "Find IMPORTS_FROM edges where the imported name has no downstream usage"


def run(repo_root: str | None = None, limit: int = 50, **kwargs) -> dict:
    from ..graph import GraphStore
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Get all import edges
        import_edges = store._conn.execute(
            "SELECT * FROM edges WHERE kind = 'IMPORTS_FROM'"
        ).fetchall()

        unused = []
        for ie in import_edges:
            source_file = ie["file_path"]
            import_target = ie["target_qualified"]

            # Check if any CALLS edge from this file references the import target
            file_call_edges = store._conn.execute(
                "SELECT COUNT(*) as cnt FROM edges WHERE kind = 'CALLS' "
                "AND file_path = ? AND target_qualified LIKE ?",
                (source_file, f"%{import_target.split('.')[-1]}%"),
            ).fetchone()

            if file_call_edges["cnt"] == 0:
                try:
                    rel_path = str(Path(source_file).relative_to(root))
                except ValueError:
                    rel_path = source_file
                unused.append({
                    "file": rel_path,
                    "import": import_target,
                    "line": ie["line"],
                })

        unused.sort(key=lambda u: (u["file"], u["line"]))

        return {
            "status": "ok",
            "summary": f"Found {len(unused)} potentially unused imports",
            "unused_imports": unused[:limit],
            "note": "Some may be used indirectly (re-exports, type annotations). Verify before removing.",
        }
    finally:
        store.close()
