"""Optional TypeScript call resolution via ts-morph."""

EXTENSION_NAME = "ts_resolver"
EXTENSION_DESCRIPTION = "Enhanced TypeScript call resolution using ts-morph (optional, requires Node.js)"


def run(repo_root: str | None = None, **kwargs) -> dict:
    import shutil

    if not shutil.which("npx"):
        return {
            "status": "error",
            "error": "npx not found. TypeScript resolution requires Node.js.",
        }

    return {
        "status": "ok",
        "summary": "TypeScript resolver is a placeholder — Tree-sitter handles TS reasonably well",
        "note": "Full ts-morph integration planned for future release",
    }
