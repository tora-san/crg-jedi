"""Score files by change risk: coupling × git churn × blast radius."""

EXTENSION_NAME = "change_risk"
EXTENSION_DESCRIPTION = "Rank files by change risk combining graph coupling, git churn, and blast radius"


def run(repo_root: str | None = None, days: int = 90, limit: int = 20, **kwargs) -> dict:
    from ..graph import GraphStore
    from ..incremental import find_project_root, get_db_path
    from pathlib import Path
    import subprocess

    root = find_project_root() if not repo_root else Path(repo_root)
    store = GraphStore(get_db_path(root))

    try:
        # Get git churn data
        churn = {}
        try:
            result = subprocess.run(
                ["git", "log", f"--since={days}.days", "--format=format:", "--name-only"],
                capture_output=True, text=True, cwd=str(root), timeout=30,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    churn[line] = churn.get(line, 0) + 1
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Score each file
        scores = []
        for file_path in store.get_all_files():
            try:
                rel_path = str(Path(file_path).relative_to(root))
            except ValueError:
                rel_path = file_path

            # Coupling: sum of fan-in across all functions in file
            nodes = store.get_nodes_by_file(file_path)
            total_fan_in = 0
            total_fan_out = 0
            for node in nodes:
                if node.kind in ("Function", "Class"):
                    total_fan_in += len([
                        e for e in store.get_edges_by_target(node.qualified_name)
                        if e.kind == "CALLS"
                    ])
                    total_fan_out += len([
                        e for e in store.get_edges_by_source(node.qualified_name)
                        if e.kind == "CALLS"
                    ])

            coupling = total_fan_in + total_fan_out
            commits = churn.get(rel_path, 0)

            # Blast radius (simplified: count impacted files at depth 1)
            impact = store.get_impact_radius([file_path], max_depth=1, max_nodes=50)
            blast = len(impact.get("impacted_files", []))

            # Risk score: coupling × churn × blast (all >= 0)
            risk = coupling * max(commits, 1) * max(blast, 1)

            if risk > 0:
                scores.append({
                    "file": rel_path,
                    "risk_score": risk,
                    "coupling": coupling,
                    "fan_in": total_fan_in,
                    "fan_out": total_fan_out,
                    "commits_90d": commits,
                    "blast_radius": blast,
                })

        scores.sort(key=lambda s: -s["risk_score"])

        return {
            "status": "ok",
            "summary": f"Risk scores for {len(scores)} files (top {limit})",
            "scores": scores[:limit],
        }
    finally:
        store.close()
