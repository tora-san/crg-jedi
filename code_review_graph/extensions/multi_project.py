"""Auto-detect Python subprojects for jedi scoping."""

EXTENSION_NAME = "multi_project"
EXTENSION_DESCRIPTION = "Detect Python subprojects (by pyproject.toml/setup.py) for jedi scoping"


def run(repo_root: str | None = None, **kwargs) -> dict:
    from ..incremental import find_project_root
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)

    markers = ["pyproject.toml", "setup.py", "setup.cfg"]
    projects = []

    # Walk directories (max 3 levels deep)
    for depth in range(3):
        pattern = "/".join(["*"] * (depth + 1))
        for marker in markers:
            for p in root.glob(f"{pattern}/{marker}" if depth > 0 else marker):
                project_dir = p.parent
                rel = str(project_dir.relative_to(root)) if project_dir != root else "."
                if not any(proj["path"] == rel for proj in projects):
                    projects.append({
                        "path": rel,
                        "marker": marker,
                        "absolute_path": str(project_dir),
                    })

    return {
        "status": "ok",
        "summary": f"Found {len(projects)} Python subproject(s)",
        "projects": projects,
    }
