"""Auto-detect Python subprojects for jedi scoping."""

EXTENSION_NAME = "multi_project"
EXTENSION_DESCRIPTION = "Detect Python subprojects (by pyproject.toml/setup.py) for jedi scoping"


def run(repo_root: str | None = None, **kwargs) -> dict:
    from ..incremental import find_project_root
    from pathlib import Path

    root = find_project_root() if not repo_root else Path(repo_root)

    markers = ["pyproject.toml", "setup.py", "setup.cfg"]
    projects = []

    # Paths to skip (worktrees, vendor, node_modules)
    _SKIP_DIRS = {".worktrees", "node_modules", ".git", "__pycache__", ".venv", "venv"}

    # Check root level first
    for marker in markers:
        if (root / marker).exists():
            projects.append({
                "path": ".",
                "marker": marker,
                "absolute_path": str(root),
            })
            break  # Only one root entry

    # Walk subdirectories (max 3 levels deep)
    for depth in range(1, 4):
        pattern = "/".join(["*"] * depth)
        for marker in markers:
            for p in root.glob(f"{pattern}/{marker}"):
                project_dir = p.parent
                rel = str(project_dir.relative_to(root))
                # Skip vendor/worktree directories
                if any(skip in rel.split("/") for skip in _SKIP_DIRS):
                    continue
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
